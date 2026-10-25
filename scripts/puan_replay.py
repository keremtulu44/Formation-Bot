# -*- coding: utf-8 -*-
"""Puan replay'i (ölçüm C): kalite skoru sonucu gerçekten ayırıyor mu?

SALT OKUNUR. `backfill_data/*_1h.csv.gz` okunur, motor
`ArgentEngine(...).process(tam_yeniden=True)` ile canlıdaki gibi yeniden
oynatılır. `bot_data/` içine HİÇBİR ŞEY yazılmaz, ağa çıkılmaz.

Ölçüm birimi: bir `BREAK_CONFIRMED` olayı = bir gözlem. Kalite o anda
DONDURULMUŞ değeridir (`frozen_raw_quality`), yani sonuç sızıntısı yoktur.

SONUÇ TANIMLARI (hepsi aynı gözlemde birlikte hesaplanır)
  B' (ANA) — üç bariyer, girişten ölçülür, motordan ve banttan bağımsız:
       giriş = kırılım barı kapanışı, ufuk = 12 bar
       · +0,8 ATR'ye değerse  → başarı   (bb_sonuc=1)
       · -0,8 ATR'ye değerse  → başarısız (bb_sonuc=0)
       · ikisi de değmezse    → çıkış yok (bb_sonuc boş, ayrı raporlanır)
       · ikisi aynı barda     → berabere (bb_berabere=1, AUC'den düşülür)
     Giriş fiyatı referans alınır çünkü ölçüm gözlemlenen kırılımın
     gerçekten devam edip etmediğini sorar; bant referansı, kırılım bandın
     uzağında gerçekleştiğinde (aşağıya bak) sonucu yapay olarak şişiriyor.
  B (İKİNCİL) — dondurulmuş banda dönüş (onaylanan C sayıları):
       kapanış bandın 0,25 ATR içine, üst üste 2 kapanış → iptal
       iptal yok VE lehte zirve >= 0,8 ATR               → başarı
       hiçbiri                                           → belirsiz
     "Oluşum bozuldu mu" ölçüsüdür; banttan uzak kırılımlarda iptal
     neredeyse imkânsız olduğu için tek başına ana metrik yapılmadı.
  A (ÇAPRAZ) — motorun kendi terminal sonucu (COMPLETED / BREAK_FAILED /
       TIMEOUT / INVALID). B' ile ayrışırsa sebep raporda yazılır.

ÖLÇÜLEN RİSK
  `bant_mesafe_atr` = kırılım fiyatının dondurulmuş banda uzaklığı. Bu,
  "alarm seviyeden ne kadar geç/sağda geldi" demektir; ayrıca `dogum_mesafe_atr`
  formasyonun doğduğunda fiyatın bandın kaç ATR dışında olduğunu tutar
  (doğuşta kırık formasyon oranı buradan okunur).

Kullanım:
    python scripts/puan_replay.py --sembol-sayisi 100
    python scripts/puan_replay.py --semboller AKBNK,THYAO --tf 1h
    python scripts/puan_replay.py --sembol-sayisi 100 --cikti var/replay/gozlemler.csv

Çıktı: tek CSV (gözlem başına bir satır) + konsol özeti. Aynı CSV'ye devam
edilir: içinde adı geçen sembol yeniden oynatılmaz (uzun tur yarıda kalırsa
kaldığı yerden sürer).
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pandas as pd  # noqa: E402

import config  # noqa: E402
from data import resample_ohlcv  # noqa: E402
from patterns.candidate import effective_raw_quality  # noqa: E402
from patterns.lifecycle import ArgentEngine  # noqa: E402

# --- önceden taahhüt edilmiş ölçüm parametreleri -----------------------------
# Tablo görüldükten sonra bunlardan biri değiştirilirse o tablo geçersiz sayılır
# ve yeniden hesaplanır.
PENCERE = 12
PENCERELER = (6, 12, 24, 48)
BARİYER_ATR = 0.8     # B' üç bariyer eşiği (her iki yön, simetrik)
# Kademe ızgarası: her gözlem için "lehte/ters yönde k ATR ilk kez kaçıncı
# barda vuruldu" tutulur. Etiket (baraj, ufuk) seçimi replay'i tekrar
# çalıştırmadan buradan türetilir; 48 bar ile sınırlı (0 = hiç vurulmadı).
KADEMELER = (0.5, 0.8, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0)
UFUK_MAX = 48
IPTAL_ATR = 0.25      # B: banda dönüş derinliği
IPTAL_USTUSTE = 2     # B: üst üste kapanış sayısı
BASARI_ATR = 0.8      # B: başarı için lehte zirve

TFLER = ("1h", "2h", "4h", "1d")
KIRILIM = "BREAK_CONFIRMED"
TERMINAL = ("COMPLETED", "BREAK_FAILED", "TIMEOUT", "INVALID")

ALANLAR = [
    "sembol", "tf", "sid", "bar", "zaman", "yon", "desen", "aile", "varyant",
    "kalite", "kalite_ham", "kalite_donuk",
    "geometri", "egim", "temas_puan", "daralma_puan", "olgunluk", "ihlal_cezasi",
    "ust_temas", "alt_temas", "daralma", "ilerleme", "direk", "duzeltme", "sure_orani",
    "guc", "guc_govde", "guc_kapanis", "guc_nufuz", "guc_genisleme", "guc_hacim",
    "bant", "atr", "giris", "bant_mesafe_atr", "dogum_bar", "dogum_mesafe_atr",
    "bant_genislik_atr", "bar_araligi_atr", "gap_atr", "hacim_orani", "gecikme_bar",
    "endeks_egim", "goreli_guc", "seans_saati", "gun",
    "retest_var", "retest_bar", "bar_sayisi",
    # B' ana sonuç
    "bb_sonuc", "bb_bar", "bb_berabere", "bb_mfe", "bb_mae",
    # kademe ızgarası (lehte / ters ilk vuruş barı, 0 = 48 barda vurulmadı)
] + [f"tl_{k:g}" for k in KADEMELER] + [f"tt_{k:g}" for k in KADEMELER] + [
    # B ikincil (bant)
    "bant_iptal6", "bant_iptal12", "bant_iptal24", "bant_belirsiz12", "bant_basari12",
    # ham ölçüler
    "mfe6", "mfe12", "mfe24", "mfe48", "mae12", "mae48", "pencere_tam",
    # A çapraz kontrol
    "motor_sonuc", "motor_kalite", "motor_bar",
]


def _f(x) -> str:
    """CSV için güvenli sayı biçimi (None → boş)."""
    if x is None:
        return ""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    if v != v:  # NaN
        return ""
    return f"{v:.6g}"


# --------------------------------------------------------------------------- #
# gözlem toplama
# --------------------------------------------------------------------------- #

_OBS: List[Dict] = []
_EVENTS: List[Dict] = []
_DOGUM: Dict[str, Dict] = {}
_SARMAL_KURULU = False


def _sarmal_kur() -> None:
    """`_emit_state_events` çağrısını sarar: kırılım anındaki adayın TÜM
    bileşenlerini o anki hâliyle kaydeder (sonradan yeniden hesaplanmaz)."""
    global _SARMAL_KURULU
    if _SARMAL_KURULU:
        return
    _orig = ArgentEngine._emit_state_events

    def sarmal(self, prev_state, started_new_identity):
        once = len(self.events)
        _orig(self, prev_state, started_new_identity)
        for ev in self.events[once:]:
            _EVENTS.append(ev)
            a = self.active
            sid = str(ev.get("stable_id") or "")
            if ev["type"] == "NEW_PATTERN" and sid and sid not in _DOGUM and getattr(a, "valid", False):
                _DOGUM[sid] = {
                    "bar": int(ev["bar"]),
                    "fiyat": ev.get("price"),
                    "ust": getattr(a, "upper_now", None),
                    "alt": getattr(a, "lower_now", None),
                }
            if ev["type"] != KIRILIM or not getattr(a, "valid", False):
                continue
            yon = int(ev.get("direction") or 0)
            atr = getattr(a, "frozen_atr_at_break", None)
            dg = _DOGUM.get(sid)
            dogum_mesafe = None
            if dg and dg["fiyat"] is not None and atr:
                if yon == 1 and dg["ust"] is not None:
                    dogum_mesafe = (dg["fiyat"] - dg["ust"]) / atr
                elif yon == -1 and dg["alt"] is not None:
                    dogum_mesafe = (dg["alt"] - dg["fiyat"]) / atr
            _OBS.append({
                "tf": getattr(self, "timeframe", None),
                "sid": sid,
                "bar": int(ev["bar"]),
                "zaman": ev.get("time"),
                "yon": yon,
                "desen": getattr(a, "pattern_type", "") or "",
                "aile": getattr(a, "family", "") or "",
                "varyant": getattr(a, "specialized_variant", "") or "",
                "kalite": effective_raw_quality(a),
                "kalite_ham": getattr(a, "raw_quality", None),
                "kalite_donuk": bool(getattr(a, "quality_frozen", False)),
                "geometri": getattr(a, "geometry_score", None),
                "egim": getattr(a, "slope_shape_score", None),
                "temas_puan": getattr(a, "touch_score", None),
                "daralma_puan": getattr(a, "contraction_score", None),
                "olgunluk": getattr(a, "maturity_score", None),
                "ihlal_cezasi": getattr(a, "historical_violation_penalty", None),
                "ust_temas": getattr(a, "upper_touches", None),
                "alt_temas": getattr(a, "lower_touches", None),
                "daralma": getattr(a, "contraction", None),
                "ilerleme": getattr(a, "progress", None),
                "direk": getattr(a, "pole_quality", None),
                "duzeltme": getattr(a, "correction_depth", None),
                "sure_orani": getattr(a, "duration_ratio", None),
                "guc": getattr(a, "break_strength", None),
                "guc_govde": getattr(a, "break_body_score", None),
                "guc_kapanis": getattr(a, "break_close_score", None),
                "guc_nufuz": getattr(a, "break_penetration_score", None),
                "guc_genisleme": getattr(a, "break_expansion_score", None),
                "guc_hacim": getattr(a, "break_volume_score", None),
                "bant": (getattr(a, "frozen_upper_boundary_at_break", None) if yon == 1
                         else getattr(a, "frozen_lower_boundary_at_break", None)),
                "atr": atr,
                "giris": ev.get("price"),
                "dogum_bar": dg["bar"] if dg else None,
                "dogum_mesafe_atr": dogum_mesafe,
                "bant_genislik_atr": (
                    (getattr(a, "frozen_upper_boundary_at_break", None)
                     - getattr(a, "frozen_lower_boundary_at_break", None)) / atr
                    if (atr and getattr(a, "frozen_upper_boundary_at_break", None) is not None
                        and getattr(a, "frozen_lower_boundary_at_break", None) is not None) else None),
                "gecikme_bar": (int(ev["bar"]) - int(a.break_snapshot_bar)
                                if getattr(a, "break_snapshot_bar", None) is not None else None),
                "hacim_orani": (
                    (self.volume[ev["bar"]] / self.vol_sma[ev["bar"] - 1])
                    if (0 <= ev["bar"] < len(self.volume) and ev["bar"] - 1 >= 0
                        and ev["bar"] - 1 < len(self.vol_sma) and self.vol_sma[ev["bar"] - 1]) else None),
                "bar_araligi_atr": ((self.high[ev["bar"]] - self.low[ev["bar"]]) / atr) if atr else None,
                "gap_atr": (((self.open[ev["bar"]] - self.close[ev["bar"] - 1]) / atr)
                            if (atr and ev["bar"] - 1 >= 0) else None),
                "seans_saati": (self.index_values[ev["bar"]].hour
                                + self.index_values[ev["bar"]].minute / 60.0),
                "gun": float(self.index_values[ev["bar"]].dayofweek),
                "_ust": getattr(a, "frozen_upper_boundary_at_break", None),
                "_alt": getattr(a, "frozen_lower_boundary_at_break", None),
                "_ust_canli": getattr(a, "upper_now", None),
                "_alt_canli": getattr(a, "lower_now", None),
            })

    ArgentEngine._emit_state_events = sarmal
    _SARMAL_KURULU = True


def _sonuc(obs: Dict, eng: ArgentEngine, n_bar: int) -> None:
    """B' (üç bariyer) + B (banda dönüş) sonuçlarını hesaplar."""
    b = obs["bar"]
    yon = obs["yon"]
    giris = obs.get("giris")
    atr = obs.get("atr")
    if atr is None and 0 <= b < len(eng.atr_array):
        atr = eng.atr_array[b]
        obs["atr"] = atr
    bant = obs.get("bant")
    if bant is None:
        bant = obs.get("_ust_canli") if yon == 1 else obs.get("_alt_canli")
        obs["bant"] = bant
    if not atr or yon == 0 or giris is None:
        return
    en_uzun = max(PENCERELER)
    obs["pencere_tam"] = int(b + UFUK_MAX < n_bar)
    if bant is not None:
        obs["bant_mesafe_atr"] = abs(giris - bant) / atr

    # ---- B' : üç bariyer (giriş referanslı, simetrik) ----
    engel_yukari = giris + BARİYER_ATR * atr
    engel_asagi = giris - BARİYER_ATR * atr
    ilk: Optional[int] = None
    yon_sonuc = None
    berabere = 0
    for k in range(1, PENCERE + 1):
        i = b + k
        if i >= n_bar:
            break
        if yon == 1:
            d_hit, u_hit = eng.low[i] <= engel_asagi, eng.high[i] >= engel_yukari
        else:
            d_hit, u_hit = eng.high[i] >= engel_yukari, eng.low[i] <= engel_asagi
        if d_hit or u_hit:
            ilk = k
            if d_hit and u_hit:
                berabere = 1
                yon_sonuc = None
            else:
                yon_sonuc = 1 if u_hit else 0
            break
    obs["bb_bar"] = ilk
    obs["bb_berabere"] = berabere
    obs["bb_sonuc"] = yon_sonuc

    # ---- kademe ızgarası: lehte/ters yönde k ATR ilk vuruş ----
    ilk_leh = {k: 0 for k in KADEMELER}
    ilk_ters = {k: 0 for k in KADEMELER}
    kalan = {}
    for k in KADEMELER:
        kalan[k] = [False, False]
    for k in range(1, UFUK_MAX + 1):
        i = b + k
        if i >= n_bar:
            break
        leh = (eng.high[i] - giris) if yon == 1 else (giris - eng.low[i])
        ters = (giris - eng.low[i]) if yon == 1 else (eng.high[i] - giris)
        for lv in KADEMELER:
            if not kalan[lv][0] and leh >= lv * atr:
                ilk_leh[lv] = k
                kalan[lv][0] = True
            if not kalan[lv][1] and ters >= lv * atr:
                ilk_ters[lv] = k
                kalan[lv][1] = True
    for lv in KADEMELER:
        obs[f"tl_{lv:g}"] = ilk_leh[lv]
        obs[f"tt_{lv:g}"] = ilk_ters[lv]
    son = min(b + PENCERE, n_bar - 1)
    if son > b:
        lehte = (max(eng.high[b + 1: son + 1]) - giris) if yon == 1 else (giris - min(eng.low[b + 1: son + 1]))
        ters = (giris - min(eng.low[b + 1: son + 1])) if yon == 1 else (max(eng.high[b + 1: son + 1]) - giris)
        obs["bb_mfe"] = lehte / atr
        obs["bb_mae"] = ters / atr

    # ---- B : dondurulmuş banda dönüş ----
    iptal_bar: Optional[int] = None
    ustuste = 0
    for k in range(1, en_uzun + 1):
        i = b + k
        if i >= n_bar:
            break
        c = eng.close[i]
        if bant is None:
            break
        ihlal = ((c < bant - IPTAL_ATR * atr) if yon == 1
                 else (c > bant + IPTAL_ATR * atr))
        ustuste = ustuste + 1 if ihlal else 0
        if ustuste >= IPTAL_USTUSTE and iptal_bar is None:
            iptal_bar = i

    for w in PENCERELER:
        son_w = min(b + w, n_bar - 1)
        if son_w <= b:
            obs[f"mfe{w}"] = None
            obs[f"bant_iptal{w}"] = None
            continue
        lehte = (max(eng.high[b + 1: son_w + 1]) - giris) if yon == 1 else (giris - min(eng.low[b + 1: son_w + 1]))
        obs[f"mfe{w}"] = lehte / atr
        obs[f"bant_iptal{w}"] = int(iptal_bar is not None and iptal_bar <= son_w)

    for w in (12, 48):
        son_w = min(b + w, n_bar - 1)
        if son_w <= b:
            obs[f"mae{w}"] = None
            continue
        obs[f"mae{w}"] = ((giris - min(eng.low[b + 1: son_w + 1])) if yon == 1
                          else (max(eng.high[b + 1: son_w + 1]) - giris)) / atr
    iptal12, mfe12 = obs.get("bant_iptal12"), obs.get("mfe12")
    if iptal12 is None or mfe12 is None:
        obs["bant_basari12"] = None
        obs["bant_belirsiz12"] = None
    elif iptal12:
        obs["bant_basari12"] = 0
        obs["bant_belirsiz12"] = 0
    elif mfe12 >= BASARI_ATR:
        obs["bant_basari12"] = 1
        obs["bant_belirsiz12"] = 0
    else:
        obs["bant_basari12"] = 0
        obs["bant_belirsiz12"] = 1


def _baglam(obs_list: List[Dict], df: pd.DataFrame, tf: str, olaylar: List[Dict]) -> None:
    """Endeks bağlamı, göreli güç ve retest bilgisini gözlemlere işler."""
    try:
        idx = pd.read_csv(REPO / "backfill_data" / "XU100_1h.csv.gz", compression="gzip",
                          parse_dates=["bar_time"]).set_index("bar_time")["close"]
        idx = idx[~idx.index.duplicated(keep="last")].sort_index()
        if tf != "1h":
            idx = resample_ohlcv(idx.to_frame("close"), tf)["close"]
        idx = idx.reindex(df.index, method="ffill")
        egim = (idx / idx.shift(20) - 1.0).to_numpy(dtype=float)
        hisse = (df["close"] / df["close"].shift(20) - 1.0).to_numpy(dtype=float)
        goreli = hisse - egim
    except Exception:
        egim = goreli = None
    retest: Dict[str, int] = {}
    for ev in olaylar:
        if ev["type"] == "RETEST_OK":
            sid = str(ev.get("stable_id") or "")
            if sid and sid not in retest:
                retest[sid] = int(ev["bar"])
    for o in obs_list:
        b = o["bar"]
        if egim is not None and 0 <= b < len(egim):
            o["endeks_egim"] = egim[b]
            o["goreli_guc"] = goreli[b]
        rb = retest.get(o["sid"])
        o["retest_var"] = 1.0 if rb is not None else 0.0
        o["retest_bar"] = (rb - b) if rb is not None else None


def _motor_sonuc(obs_list: List[Dict], olaylar: List[Dict]) -> None:
    """A (çapraz kontrol): aynı sid'in motor terminal sonucu."""
    son: Dict[str, Dict] = {}
    for ev in olaylar:
        if ev["type"] in TERMINAL:
            sid = str(ev.get("stable_id") or "")
            if sid:
                son[sid] = ev  # son terminal kazanır
    for o in obs_list:
        ev = son.get(o["sid"])
        o["motor_sonuc"] = ev["type"] if ev else ""
        o["motor_kalite"] = ev.get("quality") if ev else None
        o["motor_bar"] = ev.get("bar") if ev else None


# --------------------------------------------------------------------------- #
# sembol oynatma
# --------------------------------------------------------------------------- #

def semboller(adet: int) -> List[str]:
    """En uzun geçmişe sahip `adet` sembol (eşitlikte alfabetik)."""
    yollar = sorted((REPO / "backfill_data").glob("*_1h.csv.gz"))
    uzunluk = []
    for p in yollar:
        try:
            n = sum(1 for _ in p.open("rb"))  # gzip satır sayısı ≈ bar sayısı
        except OSError:
            n = 0
        uzunluk.append((p.name.rsplit("_", 1)[0], n))
    uzunluk.sort(key=lambda t: (-t[1], t[0]))
    return [s for s, _n in uzunluk[:adet]]


def oynat(sembol: str, tfler) -> List[Dict]:
    global _OBS, _EVENTS, _DOGUM
    _OBS, _EVENTS, _DOGUM = [], [], {}
    df1h = pd.read_csv(REPO / "backfill_data" / f"{sembol}_1h.csv.gz",
                       compression="gzip", parse_dates=["bar_time"]).set_index("bar_time")
    df1h = df1h[~df1h.index.duplicated(keep="last")].sort_index()
    satirlar: List[Dict] = []
    for tf in tfler:
        _DOGUM.clear()
        df = df1h if tf == "1h" else resample_ohlcv(df1h, tf)
        once_obs, once_ev = len(_OBS), len(_EVENTS)
        eng = ArgentEngine(profile=config.PROFILE, timeframe=tf)
        eng.process(df, tam_yeniden=True)
        yeni_obs = _OBS[once_obs:]
        for o in yeni_obs:
            o["sembol"] = sembol
            o["bar_sayisi"] = len(df)
            _sonuc(o, eng, len(df))
        _motor_sonuc(yeni_obs, _EVENTS[once_ev:])
        _baglam(yeni_obs, df, tf, _EVENTS[once_ev:])
        satirlar.extend(yeni_obs)
    return satirlar


def _yaz(yol: Path, satirlar: List[Dict], baslik: bool) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    metin_alanlari = {"sembol", "tf", "sid", "zaman", "desen", "aile", "varyant", "motor_sonuc"}
    with yol.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ALANLAR, extrasaction="ignore")
        if baslik:
            w.writeheader()
        for s in satirlar:
            w.writerow({k: (s.get(k) if s.get(k) is not None else "") if k in metin_alanlari
                        else _f(s.get(k)) for k in ALANLAR})


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Kalite puanı replay'i (salt okunur)")
    ap.add_argument("--sembol-sayisi", type=int, default=100)
    ap.add_argument("--tf", default=",".join(TFLER))
    ap.add_argument("--cikti", default="var/replay/gozlemler.csv")
    ap.add_argument("--semboller", default=None, help="virgülle açık liste")
    args = ap.parse_args(argv)

    tfler = tuple(t.strip() for t in args.tf.split(",") if t.strip())
    cikti = Path(args.cikti)
    if not cikti.is_absolute():
        cikti = REPO / cikti

    if args.semboller:
        liste = [s.strip().upper() for s in args.semboller.split(",") if s.strip()]
    else:
        liste = semboller(args.sembol_sayisi)

    biten = set()
    if cikti.exists() and cikti.stat().st_size > 0:
        try:
            biten = set(pd.read_csv(cikti, usecols=["sembol"])["sembol"].astype(str).unique())
        except Exception:
            biten = set()
    kalan = [s for s in liste if s not in biten]
    if biten:
        print(f"Devam: {len(biten)} sembol zaten ölçülmüş, {len(kalan)} kaldı.")

    _sarmal_kur()
    baslik = not (cikti.exists() and cikti.stat().st_size > 0)
    t0 = time.time()
    toplam_obs = 0
    hatalar = []
    for i, s in enumerate(kalan, 1):
        try:
            satirlar = oynat(s, tfler)
        except Exception as e:  # tek sembol tüm turu düşürmesin
            hatalar.append(f"{s}: {type(e).__name__}: {e}")
            print(f"  HATA {s}: {type(e).__name__}: {e}", flush=True)
            continue
        if satirlar:
            _yaz(cikti, satirlar, baslik)
            baslik = False
        toplam_obs += len(satirlar)
        if i % 5 == 0 or i == len(kalan):
            gecen = time.time() - t0
            print(f"  {i}/{len(kalan)} · {gecen/60:.1f} dk · {toplam_obs} gözlem", flush=True)

    gecen = time.time() - t0
    print(f"\nBitti: {len(kalan)} sembol, {gecen/60:.1f} dk "
          f"({gecen/max(1, len(kalan)):.2f} sn/sembol), hata {len(hatalar)}")
    print(f"Çıktı: {cikti}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
