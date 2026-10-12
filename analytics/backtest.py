# --- FAZ 3 V1: BACKTEST / HISTORICAL OUTCOME REPORT (SALT-OKUNUR) ---
#
# NE: Oluşmuş formasyonların KAYITLI sonuçlarını raporlar. Gerçek replay DEĞİLDİR:
# hiçbir yerde yeniden hesaplama yapılmaz, hiçbir yerde yeni veri indirilmez.
#
# VERİ KAYNAKLARI (hepsi OKUMA):
#   1) Formation History defterleri (state.formation_history.yukle) — corpus,
#      doğum/_snapshot'lar/olaylar ve KAYITLI outcome (`history.sonuc`, native-TF;
#      P2.5 semantiği gereği BİRİNCİL kaynak).
#   2) Karne defteri satırları — yalnızca `kirilim_var_mi` çapraz kontrolü.
#   3) Opsiyonel Supabase aynası — yalnızca popülasyon sayacı (kabiliyeti olan
#      store verildiyse, tek bir GET denemesi; başarısızsa yerel devam).
#
# ASLA YAPMAZ (test_backtest_v1_spec.py'deki AST bekçisiyle de kilitli):
#   * YAZMA yok: defterlere/aynaya tek bayt dokunmaz; dosya oluşturmaz.
#   * Matematik/eşik/scoring değişikliği yok; config yalnız OKUNUR.
#   * Ağ üzerinden veri kazıma yok (backfill/replay V1 dışı).
#   * Koşu-anı saat YOK: determinizm için `simdi` çağırandan gelir (komut
#     katmanı main.py'de anlık taşıyıp getirir; burada yalnız pd zamanı).
#
# RAPOR KURALLARI: her ölçüm bloğu `n=` taşır; n<15 "betimleyici", 15<=n<30
# "kısmi", n>=30 "yeterli". Küçük örneklem kanıt gibi sunulmaz.

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from statistics import median

import pandas as pd

from config import ALERT_MIN_QUALITY, ALERT_MIN_QUALITY_GLOBAL
from state import formation_history as fh

logger = logging.getLogger(__name__)

__all__ = ["BLOKLAR_TEMEL", "BLOKLAR_DETAY", "KALITE_BANTLARI",
           "KOMPONENT_SKORLARI", "NEAR_MISS_MFE_ATR", "YETERLI_N", "KISMI_N",
           "topla", "metrikler", "rapor_metni", "komut"]

# --- Sözleşme sabitleri (test_backtest_v1_spec.py ile birebir) ---
BLOKLAR_TEMEL = ("KAPSAYICILIK", "GENEL", "TİP", "TIMEFRAME", "KALİTE",
                 "HUNİ", "NOTLAR")
BLOKLAR_DETAY = ("BİLEŞEN", "GEOMETRİ", "VAKA")
KALITE_BANTLARI = ("q≥80", "q70–79", "q<70")     # Karne ile aynı etiketler
ESIK_BANDLARI = ("eşikaltı", "eşik", "eşik+5", "eşik+10")
NEAR_MISS_MFE_ATR = 1.2   # stop olanlarda "hedefi kıl payı kaçırma" eşiği
YETERLI_N = 30
KISMI_N = 15

# Kalite bileşen skorları (STATE snapshot) — "aynı toplam q, farklı vektör" ayrımı.
KOMPONENT_SKORLARI = ("geometry_score", "slope_shape_score", "touch_score",
                      "contraction_score", "maturity_score")
# GEOMETRİ bağlamı: components'taki ek STATE alanları (+ doğumdan geometry_atr).
_GEOMETRI_EK = ("contraction", "correction_depth", "duration_ratio",
                "consolidation_efficiency", "consolidation_height_ratio",
                "upper_touches", "lower_touches", "progress", "violation")
_BILESEN_KARISIMI = tuple(KOMPONENT_SKORLARI) + _GEOMETRI_EK
_KIRILIM_IZI = frozenset({"BREAK_CANDIDATE", "COUNTER_BREAK", "BREAK_CONFIRMED",
                          "TIMEOUT", "BREAK_FAILED", "RETEST_OK", "COMPLETED"})
_BREAK_KEYS = ("break_strength", "break_body_score", "break_close_score",
               "break_penetration_score", "break_expansion_score",
               "break_volume_score", "break_confirmation_strength",
               "frozen_atr_at_break", "frozen_break_buffer",
               "frozen_retest_tolerance", "frozen_raw_quality",
               "break_snapshot_price", "quality_frozen")
_DURUM_KUTULARI = {"hedef": "hedef", "stop": "stop", "nötr": "notr",
                   "bekliyor": "bekliyor", "ölçülemedi": "olculemedi",
                   "kirilim_yok": "kirilimsiz"}
_KARNE_DOSYA = "karne_defteri.json"
_AYNA_KAYIT_LIMI = 5000   # f2_formations popülasyon sayacı üst sınırı


# ---------------------------------------------------------------------------
# Küçük yardımcılar (sayı/tip toleransı — bozuk veri ASLA exception üretmez)
# ---------------------------------------------------------------------------

def _sayi(deger):
    if isinstance(deger, bool) or deger is None:
        return None
    if isinstance(deger, (int, float)):
        return float(deger)
    return None


def _yuvarla(deger, basamak=2):
    v = _sayi(deger)
    return round(v, basamak) if v is not None else None


def _med(degerler):
    degerler = [v for v in degerler if v is not None]
    if not degerler:
        return None
    return round(float(median(degerler)), 4)


def _veri_dizini(data_dir=None):
    if data_dir:
        return str(data_dir)
    try:
        from config import DATA_DIR
        return str(DATA_DIR)
    except Exception:  # pragma: no cover - config her zaman import edilebilir
        return "bot_data"


def _ts(deger):
    """pd.Timestamp'e indirger; naive ise İstanbul sayılır. Olmazsa None."""
    if deger is None:
        return None
    try:
        t = pd.Timestamp(deger)
        if t.tzinfo is None:
            t = t.tz_localize("Europe/Istanbul")
        return t
    except Exception:
        return None


def _yorum(degerlendirilen: int) -> str:
    if degerlendirilen >= YETERLI_N:
        return "yeterli"
    if degerlendirilen >= KISMI_N:
        return "kısmi"
    return "betimleyici"


def _etiket_yorum(y: str) -> str:
    return {"yeterli": "✓ yeterli örneklem",
            "kısmi": "⚠ kısmi örneklem",
            "betimleyici": "⚠ n<15 — betimleyici, kanıt değil"}[y]


# ---------------------------------------------------------------------------
# 1) TOPLA — dosyalardan corpus (tek geçiş, sıfır yazma)
# ---------------------------------------------------------------------------

def _karne_kirilim_sidleri(dd: str):
    """Karne defterindeki kırılım satırlarının stable_id kümesi (çapraz kontrol).

    KarneDefteri YALNIZ okunur (kaydet/buda çağrılmaz). Dosya yoksa boş küme.
    """
    try:
        from karne import KarneDefteri
        defter = KarneDefteri(data_dir=dd)
        return {k.get("stable_id") for k in defter.kayitlar()
                if isinstance(k, dict) and k.get("tip") == "kirilim"
                and k.get("stable_id")}
    except Exception:  # noqa: BLE001 - çapraz kontrol yoksa corpus yine döner
        return set()


def _ayna_nufus(store):
    """Opsiyonel Supabase aynasından popülasyon SAYISI (salt GET).

    Store'un tablo okuma kabiliyeti yoksa ya da herhangi bir hata olursa None:
    rapor yalnızca yerel pencereyi anlatır ve uyarıya yazılır.
    """
    if store is None or not hasattr(store, "request_table"):
        return None
    try:
        yanit = store.request_table(
            "f2_formations", "GET",
            params={"select": "stable_id", "limit": _AYNA_KAYIT_LIMI})
        satirlar = yanit.json()
        return len(satirlar) if isinstance(satirlar, list) else None
    except Exception:  # noqa: BLE001 - ayna erişilemezse yerel yeter
        return None


def _uretilmis_kayit(rec, stock, tf, karne_sids):
    """Ham history kaydını backtest-kayıt sözlüğüne indirger (saf dönüşüm)."""
    sid = rec.get("stable_id") or ""
    dogum = rec.get("dogum") if isinstance(rec.get("dogum"), dict) else {}
    dal = dogum.get("alanlar") if isinstance(dogum.get("alanlar"), dict) else {}
    snaps = [s for s in (rec.get("snapshotlar") or []) if isinstance(s, dict)]
    olay = [o for o in (rec.get("olaylar") or []) if isinstance(o, dict)]

    sonuc = rec.get("sonuc") if isinstance(rec.get("sonuc"), dict) else None

    # Son (veya outcome'un dayandığı) kırılım snapshot'ı seçilir.
    kir_snaps = [s for s in snaps if s.get("tur") == "kirilim"]
    kir = None
    if kir_snaps:
        kaynak = (sonuc or {}).get("kaynak")
        kir = next((s for s in reversed(kir_snaps) if s.get("bar_time") == kaynak),
                   kir_snaps[-1])
    kir_alan = kir.get("alanlar") if isinstance((kir or {}).get("alanlar"), dict) else {}

    # Bileşen vektörü: kırılım snapshot'ının BAR_TIME'ı ile AYNI geometri
    # snapshot'ı (motor ikisini aynı anda yazar; eşleşme yoksa vektör YOK sayılır).
    geo = None
    if kir is not None:
        geo = next((s for s in reversed(snaps)
                    if s.get("tur") == "geometri"
                    and s.get("bar_time") == kir.get("bar_time")), None)
    geo_alan = geo.get("alanlar") if isinstance((geo or {}).get("alanlar"), dict) else {}
    components = {k: v for k in _BILESEN_KARISIMI
                  if (v := geo_alan.get(k)) is not None} if geo else {}

    # Kırılım donmuş kalitesi: frozen_raw_quality öncelikli, sonra snapshot kalitesi.
    kir_q = kir_alan.get("frozen_raw_quality")
    if kir_q is None:
        kir_q = kir_alan.get("break_snapshot_quality")

    klasik = dal.get("classic_dir") or 0
    kirilim_dir = kir_alan.get("break_snapshot_direction") or 0
    breakout = {k: v for k in _BREAK_KEYS if (v := kir_alan.get(k)) is not None}
    if kir is not None:
        breakout["dir"] = kirilim_dir
        breakout["karsi_yonlu"] = bool(klasik and kirilim_dir and kirilim_dir != klasik)

    # Olay türleri: ilk görülme sırası korunur (dedup), bozuk olaylar atlanır.
    events, gorulen = [], set()
    for o in olay:
        t = o.get("type")
        if isinstance(t, str) and t and t not in gorulen:
            gorulen.add(t)
            events.append(t)

    kirilim_var_mi = bool(gorulen & _KIRILIM_IZI) or kir is not None \
        or (sonuc is not None and sonuc.get("durum") not in (None, "kirilim_yok")) \
        or (sid in karne_sids)

    return {
        "stable_id": sid,
        "stock": stock,
        "tf": tf,
        "pattern_type": dal.get("pattern_type"),
        "family": dal.get("family"),
        "classic_dir": klasik,
        "dogum_quality": _sayi(dal.get("raw_quality")),
        "kirilim_quality": _sayi(kir_q),
        "durum": rec.get("durum"),
        "terminal_state": rec.get("terminal_state"),
        "sonuc": sonuc,
        "kirilim_var_mi": bool(kirilim_var_mi),
        "components": components,
        "breakout": breakout,
        "events": events,
        "dogum_bar_time": dogum.get("bar_time"),
        "geometry_atr": _sayi(dal.get("geometry_atr")),
    }


def topla(data_dir=None, gun=None, simdi=None, store=None):
    """History defterleri (+Karne çapraz kontrolü) → backtest corpus'u.

    - gun: `dogum_bar_time >= simdi - gun` (sınır DÂHİL); bar_time'ı olmayan
      kayıt korunur (veri kaybı yerine belirsizlik işaretlenir).
    - Determinizm: (stock, tf, stable_id) artan sırası.
    """
    dd = _veri_dizini(data_dir)
    kok = os.path.join(dd, getattr(fh, "FORMATION_HISTORY_ALT_DOSYA", "formation_history"))
    dosyalar = []
    if os.path.isdir(kok):
        dosyalar = sorted(f for f in os.listdir(kok) if f.endswith(".json"))

    sinir = None
    if gun:
        referans = _ts(simdi)
        if referans is None:
            referans = pd.Timestamp.now(tz="Europe/Istanbul")
        sinir = referans - pd.Timedelta(days=int(gun))

    karne_sids = _karne_kirilim_sidleri(dd)
    ayna = _ayna_nufus(store)

    kayitlar, bozuk, okunan = [], 0, 0
    for fn in dosyalar:
        stem = fn[:-5]
        try:
            ham = json.loads(Path(os.path.join(kok, fn)).read_text(encoding="utf-8"))
            if not isinstance(ham, dict):
                raise ValueError("defter sözlük değil")
        except Exception:  # noqa: BLE001 - bozuk dosya sayılır, atlanır
            bozuk += 1
            continue
        okunan += 1
        if "_" not in stem:
            continue
        stock, tf = stem.rsplit("_", 1)
        try:
            defter = fh.yukle(stock, tf, dd)
        except Exception:  # noqa: BLE001 - tek slot tüm raporu düşürmez
            continue
        for rec in fh.kayitlar(defter):
            if not isinstance(rec, dict):
                continue
            r = _uretilmis_kayit(rec, stock, tf, karne_sids)
            if sinir is not None:
                bt = _ts(r.get("dogum_bar_time"))
                if bt is not None and bt < sinir:
                    continue   # pencere dışında
                # bar_time okunamaz/boş -> KORUNUR (üstte açık kalan formasyon
                # kaybolmasın; tarih filtresi muhafazakâr çalışır)
            kayitlar.append(r)

    kayitlar.sort(key=lambda r: (str(r["stock"]), str(r["tf"]), str(r["stable_id"])))
    zamanlar = sorted({str(r["dogum_bar_time"]) for r in kayitlar if r.get("dogum_bar_time")})
    tarih_araligi = (zamanlar[0], zamanlar[-1]) if zamanlar else None

    uyarilar = []
    if store is None:
        uyarilar.append("Popülasyon yalnızca YEREL pencereden okundu "
                        "(slot başına en fazla 30 kayıt retention'ı).")
    elif ayna is None:
        uyarilar.append("Supabase aynası okunamadı; yalnızca yerel pencere geçerli.")
    else:
        uyarilar.append(f"Supabase aynası popülasyon sayacı: {ayna} formation.")
    if bozuk:
        uyarilar.append(f"{bozuk} bozuk defter dosyası atlandı.")
    if gun:
        uyarilar.append(f"Tarih filtresi: son {gun} gün (doğum bar_time'ı olmayanlar korunur).")

    return {
        "kayitlar": kayitlar,
        "uyarilar": uyarilar,
        "bozuk_dosya": bozuk,
        "slot": okunan,
        "dosya": len(dosyalar),
        "tarih_araligi": tarih_araligi,
        "kaynak": "local",
        "pencere": (f"son {int(gun)} gün" if gun else None),
        "ayna_kayit": ayna,
    }


# ---------------------------------------------------------------------------
# 2) METRIKLER — saf toplulaştırma (hesap yok, okuma+sınıflandırma var)
# ---------------------------------------------------------------------------

def _siniflandir(rec) -> str:
    sonuc = rec.get("sonuc") if isinstance(rec.get("sonuc"), dict) else None
    if sonuc:
        d = sonuc.get("durum")
        if d in _DURUM_KUTULARI:
            return _DURUM_KUTULARI[d]
    if rec.get("kirilim_var_mi"):
        return "olcumemis"
    if rec.get("durum") == "terminal":
        return "kirilimsiz"
    return "devam"


def _outcome_alani(rec, alan):
    sonuc = rec.get("sonuc") if isinstance(rec.get("sonuc"), dict) else None
    if not sonuc:
        return None
    o = sonuc.get("outcome") if isinstance(sonuc.get("outcome"), dict) else {}
    return _sayi(o.get(alan))


def _kare_deger(rec):
    """Band/bant analizi quality'si: kırılımda DONDURULMUŞ kalite öncelikli."""
    q = _sayi(rec.get("kirilim_quality"))
    return q if q is not None else _sayi(rec.get("dogum_quality"))


def _karne_bandi(q):
    if q >= 80.0:
        return "q≥80"
    if q >= 70.0:
        return "q70–79"
    return "q<70"


def _esik_bandi(tf, q):
    es = _sayi(ALERT_MIN_QUALITY.get(str(tf).lower())) or float(ALERT_MIN_QUALITY_GLOBAL)
    if q < es:
        return "eşikaltı"
    if q < es + 5.0:
        return "eşik"
    if q < es + 10.0:
        return "eşik+5"
    return "eşik+10"


def _ozet(grup) -> dict:
    """Tek grubun standart özeti: sayaçlar yalnız DEĞERLENDİRİLENDEN sayılır."""
    siniflar = [_siniflandir(r) for r in grup]
    deger = [s in ("hedef", "stop", "notr") for s in siniflar]
    ev = [r for r, d in zip(grup, deger) if d]
    out = {"n": len(list(grup)),
           "degerlendirilen": len(ev),
           "hedef": sum(1 for s in siniflar if s == "hedef"),
           "stop": sum(1 for s in siniflar if s == "stop"),
           "notr": sum(1 for s in siniflar if s == "notr"),
           "med_son_pct": _med([_outcome_alani(r, "son_pct") for r in ev]),
           "med_mfe_pct": _med([_outcome_alani(r, "mfe_pct") for r in ev]),
           "med_mae_pct": _med([_outcome_alani(r, "mae_pct") for r in ev]),
           "med_mfe_atr": _med([_outcome_alani(r, "mfe_atr") for r in ev]),
           "med_mae_atr": _med([_outcome_alani(r, "mae_atr") for r in ev])}
    out["yorum"] = _yorum(out["degerlendirilen"])
    return out


def _grup_metrik(recs, alan):
    gruplar = {}
    for r in recs:
        etiket = r.get(alan) or "Bilinmeyen"
        gruplar.setdefault(str(etiket), []).append(r)
    return {k: _ozet(v) for k, v in gruplar.items()}


def metrikler(corpus) -> dict:
    """topla() çıktısından (veya ham kayıt listesinden) rapor metrikleri.

    Saf fonksiyon: hiçbir dosya/ağ erişimi yok; her blok n taşır.
    """
    if isinstance(corpus, list):
        corpus = {"kayitlar": corpus}
    recs = [r for r in (corpus.get("kayitlar") or []) if isinstance(r, dict)]

    siniflar = [_siniflandir(r) for r in recs]
    degerli = [r for r, s in zip(recs, siniflar) if s in ("hedef", "stop", "notr")]

    def _g(s):
        return sum(1 for x in siniflar if x == s)

    hedef, stop, notr = _g("hedef"), _g("stop"), _g("notr")
    degerlendirilen = len(degerli)
    oran = round(hedef / (hedef + stop), 4) if (hedef + stop) else None
    near_miss = sum(1 for r, s in zip(recs, siniflar)
                     if s == "stop" and (_outcome_alani(r, "mfe_atr") or 0) >= NEAR_MISS_MFE_ATR)

    genel = {"n": len(recs),
             "terminal": sum(1 for r in recs if r.get("durum") == "terminal"),
             "hedef": hedef, "stop": stop, "notr": notr,
             "bekliyor": _g("bekliyor"), "olculemedi": _g("olculemedi"),
             "kirilimsiz": _g("kirilimsiz"), "olcumemis": _g("olcumemis"),
             "devam": _g("devam"), "degerlendirilen": degerlendirilen,
             "hedef_orani": oran,
             "med_son_pct": _med([_outcome_alani(r, "son_pct") for r in degerli]),
             "med_mfe_pct": _med([_outcome_alani(r, "mfe_pct") for r in degerli]),
             "med_mae_pct": _med([_outcome_alani(r, "mae_pct") for r in degerli]),
             "med_mfe_atr": _med([_outcome_alani(r, "mfe_atr") for r in degerli]),
             "med_mae_atr": _med([_outcome_alani(r, "mae_atr") for r in degerli]),
             # Varış barları ANLAMI OLDUĞU gruptan: hedef-bar yalnız hedefte,
             # stop-bar yalnız stop'ta (stop olan kayıtta hedef_bar sonradan
             # dokunulmuş olabilir; "ulaşılamadı" sayılır).
             "med_hedef_bar": _med([_outcome_alani(r, "hedef_bar")
                                    for r, s in zip(recs, siniflar) if s == "hedef"]),
             "med_stop_bar": _med([_outcome_alani(r, "stop_bar")
                                    for r, s in zip(recs, siniflar) if s == "stop"]),
             "near_miss": near_miss, "near_miss_esik": NEAR_MISS_MFE_ATR}
    genel["yorum"] = _yorum(degerlendirilen)

    # --- kalite bantları (frozen quality öncelikli) ---
    q_degerler = [q for q in (_kare_deger(r) for r in recs) if q is not None]
    band_uyeleri = {b: [] for b in KALITE_BANTLARI}
    for r in recs:
        q = _kare_deger(r)
        if q is not None:
            band_uyeleri[_karne_bandi(q)].append(r)
    karne_bant = {}
    for bant, uyeler in band_uyeleri.items():
        ev = [r for r in uyeler if _siniflandir(r) in ("hedef", "stop", "notr")]
        karne_bant[bant] = {"n": len(uyeler),
                            "degerlendirilen": len(ev),
                            "hedef": sum(1 for r in ev if _siniflandir(r) == "hedef"),
                            "stop": sum(1 for r in ev if _siniflandir(r) == "stop"),
                            "notr": sum(1 for r in ev if _siniflandir(r) == "notr"),
                            "med_son_pct": _med([_outcome_alani(r, "son_pct") for r in ev])}
    esik_goreli = {}
    for r in recs:
        q = _kare_deger(r)
        if q is None:
            continue
        tfk = str(r.get("tf") or "—")
        tablo = esik_goreli.setdefault(tfk, {b: 0 for b in ESIK_BANDLARI})
        tablo[_esik_bandi(tfk, q)] += 1

    kalite = {"karne": karne_bant, "esik_goreli": esik_goreli,
              "dagilim": {"n": len(q_degerler),
                          "min": round(min(q_degerler), 2) if q_degerler else None,
                          "med": _med(q_degerler),
                          "maks": round(max(q_degerler), 2) if q_degerler else None}}

    # --- bileşen imzaları (yalnız vektörü eşleşen, çözümlenmiş kayıtlar) ---
    vektorlu = [r for r in recs if r.get("components")]
    skorlar = {}
    for comp in KOMPONENT_SKORLARI:
        def _degerler(durum):
            return [_sayi((r.get("components") or {}).get(comp)) for r in vektorlu
                    if _siniflandir(r) == durum
                    and _sayi((r.get("components") or {}).get(comp)) is not None]
        hv, sv = _degerler("hedef"), _degerler("stop")
        mh, ms = _med(hv), _med(sv)
        skorlar[comp] = {"n_hedef": len(hv), "n_stop": len(sv),
                         "med_hedef": mh, "med_stop": ms,
                         "fark": round(mh - ms, 4) if mh is not None and ms is not None
                         else None}
    bilesim = {"n_vektorlu": len(vektorlu),
               "eslesmeyen": len(recs) - len(vektorlu), "skorlar": skorlar}

    # --- huni / lifecycle / breakout ---
    def _ev_say(tur):
        return sum(1 for r in recs if tur in (r.get("events") or []))

    def _br_med(alan):
        return _med([_sayi((r.get("breakout") or {}).get(alan)) for r in recs])

    huni = {
        "kirilimi_olan": sum(1 for r in recs if r.get("kirilim_var_mi")),
        "teyitli": _ev_say("BREAK_CONFIRMED"),
        "retest_ok": _ev_say("RETEST_OK"),
        "tamamlandi": _ev_say("COMPLETED"),
        "basarisiz": _ev_say("BREAK_FAILED"),
        "timeout": _ev_say("TIMEOUT"),
        "karsi_yonlu": sum(1 for r in recs
                           if (r.get("breakout") or {}).get("karsi_yonlu") is True),
        "cok_denemeli": sum(1 for r in recs
                            if ((r.get("sonuc") or {}).get("deneme") or 0) >= 2),
        "med_break_strength": _br_med("break_strength"),
        "med_break_confirmation": _br_med("break_confirmation_strength"),
    }

    # --- vaka listeleri (ufuk sonu getiriye göre) ---
    skorlu = [(r, _outcome_alani(r, "son_pct")) for r in degerli]
    skorlu = [(r, p) for r, p in skorlu if p is not None]
    iyi = sorted(skorlu, key=lambda rp: (-rp[1], str(rp[0].get("stable_id"))))[:5]
    kotu = sorted(skorlu, key=lambda rp: (rp[1], str(rp[0].get("stable_id"))))[:5]

    def _vaka(r, p):
        return {"stable_id": r.get("stable_id"), "stock": r.get("stock"),
                "tf": r.get("tf"), "pattern_type": r.get("pattern_type"),
                "son_pct": p}

    vaka = {"en_iyi": [_vaka(r, p) for r, p in iyi],
            "en_kotu": [_vaka(r, p) for r, p in kotu]}

    # --- geometri (detay bloğu; eksik alan toleranslı) ---
    geometrili = [r for r in recs if _sayi(r.get("geometry_atr")) is not None]
    geo_kutular = {b: {"n": 0, "degerlendirilen": 0, "hedef": 0}
                   for b in ("kucik", "orta", "buyuk")}
    for r in geometrili:
        ga = _sayi(r.get("geometry_atr"))
        k = "kucik" if ga <= 1.5 else ("orta" if ga <= 3.0 else "buyuk")
        geo_kutular[k]["n"] += 1
        s = _siniflandir(r)
        if s in ("hedef", "stop", "notr"):
            geo_kutular[k]["degerlendirilen"] += 1
            if s == "hedef":
                geo_kutular[k]["hedef"] += 1
    geometri = {"n": len(geometrili), "kutular": geo_kutular,
                "med_contraction": _med([_sayi((r.get("components") or {}).get("contraction"))
                                         for r in recs]),
                "med_upper_touches": _med([_sayi((r.get("components") or {}).get("upper_touches"))
                                           for r in recs]),
                "med_lower_touches": _med([_sayi((r.get("components") or {}).get("lower_touches"))
                                           for r in recs])}

    kapsayici = {"kayit": len(recs), "dosya": corpus.get("dosya"),
                 "slot": corpus.get("slot"), "bozuk_dosya": corpus.get("bozuk_dosya", 0),
                 "tarih_araligi": corpus.get("tarih_araligi"),
                 "kaynak": corpus.get("kaynak", "local"),
                 "pencere": corpus.get("pencere"), "ayna_kayit": corpus.get("ayna_kayit")}

    return {"genel": genel, "tip": _grup_metrik(recs, "pattern_type"),
            "aile": _grup_metrik(recs, "family"), "tf": _grup_metrik(recs, "tf"),
            "kalite": kalite, "bilesim": bilesim, "huni": huni,
            "vaka": vaka, "geometri": geometri, "kapsayici": kapsayici,
            "uyarilar": list(corpus.get("uyarilar") or [])}


# ---------------------------------------------------------------------------
# 3) RAPOR — Telegram metni (kirp çağırandan; burada 4000'a pay bırakılır)
# ---------------------------------------------------------------------------

def _s(v, birim="", yuzde=False):
    if v is None or isinstance(v, bool):
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    if yuzde:
        return f"{v:+.1f}%"
    t = f"{v:.2f}".rstrip("0").rstrip(".")
    return t + birim


def _satir(ozet) -> str:
    return (f"n={ozet['n']} · değer n={ozet['degerlendirilen']} · "
            f"{ozet['hedef']}/{ozet['stop']}/{ozet['notr']} (h/s/n) · "
            f"med son {_s(ozet['med_son_pct'], yuzde=True)} · "
            f"{ozet['yorum']}")


def _grup_satirlari(baslik: str, grup: dict):
    satirlar = [f"{baslik} · n={sum(v['n'] for v in grup.values())}"]
    sirali = sorted(grup.items(), key=lambda kv: (-kv[1]["n"], kv[0]))
    for etiket, v in sirali:
        satirlar.append(f" {etiket}: {_satir(v)}")
    return satirlar


def rapor_metni(metrik, detay=False) -> str:
    """Bloklar: KAPSAYICILIK/GENEL/TİP/TIMEFRAME/KALİTE/HUNİ/NOTLAR (+detay)."""
    g = metrik.get("genel", {})
    k = metrik.get("kapsayici", {})
    satirlar = []

    kayit_n = int(k.get("kayit") or 0)
    satirlar.append(f"🧭 KAPSAYICILIK · n={kayit_n}")
    satirlar.append(f" defter: dosya={k.get('dosya')} · slot={k.get('slot')} · "
                    f"bozuk={k.get('bozuk_dosya', 0)} · kaynak={k.get('kaynak', 'local')}"
                    + (f" · ayna={k['ayna_kayit']}" if k.get("ayna_kayit") else ""))
    aralik = k.get("tarih_araligi")
    satirlar.append(f" tarih: {aralik[0][:10] if aralik else '—'} → "
                    f"{aralik[1][:10] if aralik else '—'} · "
                    f"pencere: {k.get('pencere') or 'tüm zamanlar'}")

    satirlar.append("")
    satirlar.append(f"⚡ GENEL · n={g.get('n', 0)} · değerlendirilen n="
                    f"{g.get('degerlendirilen', 0)}")
    if not kayit_n:
        satirlar.append(" corpus boş — veri yok (tarama biriktikçe dolar)")
    else:
        satirlar.append(f" hedef {g['hedef']} · stop {g['stop']} · nötr {g['notr']} · "
                        f"bekliyor {g['bekliyor']} · ölçülemedi {g['olculemedi']} · "
                        f"kırılımsız {g['kirilimsiz']} · ölçülmemiş {g['olcumemis']} · "
                        f"devam {g['devam']}")
        oran = g.get("hedef_orani")
        satirlar.append(f" h/(h+s) {_s(oran * 100, '%') if oran is not None else '—'} · "
                        f"med son {_s(g['med_son_pct'], yuzde=True)} · "
                        f"near-miss n={g['near_miss']} (≥{_s(g['near_miss_esik'])} ATR)")
        satirlar.append(f" MFE med {_s(g['med_mfe_pct'], '%')} / {_s(g['med_mfe_atr'], 'ATR')} · "
                        f"MAE med {_s(g['med_mae_pct'], '%')} / {_s(g['med_mae_atr'], 'ATR')} · "
                        f"varış bar: hedef {_s(g['med_hedef_bar'])} · stop {_s(g['med_stop_bar'])}")
        satirlar.append(f" örneklem: {_etiket_yorum(g['yorum'])}")

    satirlar.append("")
    for baslik, anahtar in (("🧩 TİP", "tip"), ("⏱ TIMEFRAME", "tf"), ("🎯 AİLE", "aile")):
        grup = metrik.get(anahtar) or {}
        satirlar.extend(_grup_satirlari(baslik, grup))
        satirlar.append("")

    kal = metrik.get("kalite", {})
    satirlar.append(f"🎚 KALİTE · n={kal.get('dagilim', {}).get('n', 0)} "
                    f"(kırılım-donmuş kalite öncelikli)")
    dag = kal.get("dagilim", {})
    satirlar.append(f" dağılım: min {_s(dag.get('min'))} · med {_s(dag.get('med'))} · "
                    f"maks {_s(dag.get('maks'))}")
    for bant in KALITE_BANTLARI:
        v = (kal.get("karne") or {}).get(bant, {})
        satirlar.append(f" {bant}: n={v.get('n', 0)} · değer n={v.get('degerlendirilen', 0)} · "
                        f"{v.get('hedef', 0)}/{v.get('stop', 0)}/{v.get('notr', 0)} · "
                        f"med son {_s(v.get('med_son_pct'), yuzde=True)}")
    for tfk, tablo in sorted((kal.get("esik_goreli") or {}).items()):
        parcalar = " · ".join(f"{b} {tablo.get(b, 0)}" for b in ESIK_BANDLARI)
        satirlar.append(f" eşik-göreli {tfk} (n={sum(tablo.values())}): {parcalar}")

    huni = metrik.get("huni", {})
    satirlar.append("")
    satirlar.append(f"🌀 HUNİ · n={huni.get('kirilimi_olan', 0)} (kırılım izli)")
    satirlar.append(f" teyit {huni.get('teyitli', 0)} · retest-ok {huni.get('retest_ok', 0)} · "
                    f"tamam {huni.get('tamamlandi', 0)} · başarısız {huni.get('basarisiz', 0)} · "
                    f"timeout {huni.get('timeout', 0)}")
    satirlar.append(f" karşı-yön n={huni.get('karsi_yonlu', 0)} · çok-deneme n="
                    f"{huni.get('cok_denemeli', 0)} · güc med {_s(huni.get('med_break_strength'))}"
                    f"/{_s(huni.get('med_break_confirmation'))}")

    satirlar.append("")
    if detay:
        bil = metrik.get("bilesim", {})
        satirlar.append(f"🧬 BİLEŞEN · n={bil.get('n_vektorlu', 0)} (vektör eşleşen; "
                        f"eşleşmeyen n={bil.get('eslesmeyen', 0)})")
        for comp in KOMPONENT_SKORLARI:
            v = (bil.get("skorlar") or {}).get(comp, {})
            satirlar.append(f" {comp}: hedef {_s(v.get('med_hedef'))} (n={v.get('n_hedef', 0)}) vs "
                            f"stop {_s(v.get('med_stop'))} (n={v.get('n_stop', 0)}) · "
                            f"fark {_s(v.get('fark'))}")
        geo = metrik.get("geometri", {})
        satirlar.append("")
        satirlar.append(f"📐 GEOMETRİ · n={geo.get('n', 0)} (geometry_atr bucket)")
        for kutu, ad in (("kucik", "≤1.5"), ("orta", "≤3"), ("buyuk", ">3")):
            v = (geo.get("kutular") or {}).get(kutu, {})
            satirlar.append(f" {ad} ATR: n={v.get('n', 0)} · değer n="
                            f"{v.get('degerlendirilen', 0)} · hedef {v.get('hedef', 0)}")
        satirlar.append(f" contraction med {_s(geo.get('med_contraction'))} · dokunuş med "
                        f"{_s(geo.get('med_upper_touches'))}/"
                        f"{_s(geo.get('med_lower_touches'))}")
        vaka = metrik.get("vaka", {})
        satirlar.append("")
        satirlar.append(f"🔬 VAKA · n={len((vaka.get('en_iyi') or [])) + len((vaka.get('en_kotu') or []))}")
        for ad, liste in (("en iyi", vaka.get("en_iyi") or ()),
                          ("en kötü", vaka.get("en_kotu") or ())):
            for v in liste:
                satirlar.append(f" {ad}: {str(v.get('stock'))} {v.get('tf')} "
                                f"{v.get('pattern_type') or '—'} · "
                                f"{str(v.get('stable_id'))[:8]} · son {_s(v.get('son_pct'), yuzde=True)}")
        if not (vaka.get("en_iyi") or vaka.get("en_kotu")):
            satirlar.append(" (çözümlenmiş sonuç yok)")

    satirlar.append("")
    satirlar.append("ℹ️ NOTLAR")
    satirlar.append(" • Betimsel rapordur; öneri/scoring/eşik değişikliği içermez.")
    satirlar.append(" • Gözlemler bağımsız değildir (aynı hisse/TF ve gün korele);")
    satirlar.append("   n= nominal sayıdır, efektif örneklem daha küçüktür.")
    satirlar.append(" • Corpus yalnız botun ayakta olduğu pencereyi kapsar.")
    satirlar.append(" • entry=teyit kapanışı (slippage/komisyon yok): sinyal")
    satirlar.append("   performansının, işlem performansının değil.")
    for u in (metrik.get("uyarilar") or [])[:3]:
        satirlar.append(f" • {u}")
    return "\n".join(satirlar)


# ---------------------------------------------------------------------------
# 4) KOMUT — argüan ayrıştırma + uçtan uca akış (hiçbir yere yazmaz)
# ---------------------------------------------------------------------------

KULLANIM = ("Kullanım: /backtest · /backtest 30 · /backtest 90 detay\n"
            "(sayı = son N gün, 1-365; 'detay' bileşen+geometri+vaka bloklarını ekler)")


def _argumanlari_coz(arguman):
    parcalar = str(arguman or "").strip().lower().split()
    gun, detay = None, False
    for p in parcalar:
        if p == "detay":
            if detay:
                return None
            detay = True
            continue
        try:
            g = int(p)
        except ValueError:
            return None
        if gun is not None or g < 1 or g > 365:
            return None
        gun = g
    return gun, detay


def komut(arguman="", data_dir=None, simdi=None, store=None):
    """Telegram handler gövdesi: /backtest [gün] [detay] → metin raporu.

    Salt-okunur pipeline: topla() → metrikler() → rapor_metni(). Hata durumunda
    kısa mesaj döner; exception Telegram thread'ine sızMAZ (komut asla çökmez).
    """
    cozulmus = _argumanlari_coz(arguman)
    if cozulmus is None:
        return KULLANIM
    gun, detay = cozulmus
    try:
        korpus = topla(data_dir=data_dir, gun=gun, simdi=simdi, store=store)
        return rapor_metni(metrikler(korpus), detay=detay)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Backtest raporu üretilemedi: %s", exc, exc_info=True)
        return "⚠️ Backtest raporu üretilemedi; ayrıntı bot loglarında."
