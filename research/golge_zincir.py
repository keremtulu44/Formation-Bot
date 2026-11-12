"""Gölge zincir koşucusu — T1 (sözleşme §8): G1→G5 → TYR → plan → yarış.

Salt replay: canlı registry'ye yazmaz, alarm üretmez, ana sisteme dokunmaz.
Tek çıktı: gölge defter (JSONL) + özet JSON.

Mimari (plan belgesi §1):
* G1  : Stabil tek-geçiş önbelleği (``build_single_pass_history``) — as-of
        sorgu ``support_at/trend_at`` yalnız ≤ t.
* G2  : ``formasyon_kosu`` (causal replay) — yaşam penceresi filtresi.
* G3  : ``MarketStructureEngine`` tek replay — olaylar ``event_bar ≤ i``.
* G5  : ``replay_ob_zones`` / ``replay_fvg_zones`` — as-of aktiflik + tepki.
* G4  : ``senaryo.tyr.tyr_hukmu`` (saf) — yalnız değişimde deftere yazılır.
* Plan: ``senaryo.plan_karti`` → ileri yarış (10 bar, aynı barda çift
        dokunuş → stop, sansür ayrı) → ``IslemSonucu``.

Kullanım:
    python research/golge_zincir.py                 # tüm evren, 4 TF
    python research/golge_zincir.py --limit 3       # duman koşusu
    python research/golge_zincir.py --semboller AEFES,THYAO --tf 4h
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from directional_zone_replay import (  # noqa: E402
    _normalize_frame,
    compute_wilder_atr,
    replay_fvg_zones,
    replay_ob_zones,
)
from domain_engines.adapter import to_domain_frame  # noqa: E402
from domain_engines.market_structure import (  # noqa: E402
    MarketStructureConfig,
    MarketStructureEngine,
)
from domain_engines.stabil import build_single_pass_history  # noqa: E402
from research.arsiv import HAVUZ_DISI_SEMBOLLER, arsiv_sembolleri, tf_frame  # noqa: E402
from research.formasyon import formasyon_kosu  # noqa: E402
from senaryo.defter import GolgeDefter  # noqa: E402
from senaryo.giris_teyidi import giris_teyidi  # noqa: E402
from senaryo.modeller import IslemSonucu  # noqa: E402
from senaryo.plan_karti import plan_karti_uret  # noqa: E402
from senaryo.tyr import TyrDurum, tyr_hukmu  # noqa: E402
from senaryo.zincir import (  # noqa: E402
    G5Durum,
    bildirim_uret,
    g1_durumu,
    g2_durumu,
    g5_durumu,
    ms_uyarilari,
)

VARSAYILAN_CIKTI = KOK / "docs/arastirma/sonuclar/golge_zincir"
ILK_BAR = 40                      # zincirin başladığı minimum bar
KARSIT_YAS_ESIK_BAR = 5           # plan §3: taze karşıt MS olayı yaşı
ZAMAN_STOPU_BAR = 10              # Faz7: --zaman-stopu ile değiştirilir


# --- hazırlık ---------------------------------------------------------------
@dataclass
class SeriHazirlik:
    symbol: str
    tf: str
    norm: pd.DataFrame              # RangeIndex + timestamp (Istanbul)
    atr: tuple[float | None, ...]
    events: tuple[Any, ...]         # MarketStructureEventRecord
    swings: tuple[Any, ...]         # SwingPoint (external)
    ob: list[dict[str, Any]]
    fvg: list[dict[str, Any]]
    frm: list[dict[str, Any]]
    split_i: int
    hata: str = ""


def seri_hazirla(symbol: str, tf: str, frame: pd.DataFrame) -> SeriHazirlik:
    norm = _normalize_frame(frame)
    atr = compute_wilder_atr(norm)

    ms = MarketStructureEngine(config=MarketStructureConfig(profile="Dengeli"))
    ms.replay(to_domain_frame(norm))
    events = tuple(ms.event_history)
    swings = tuple(ms.external_swings)

    ob = list(replay_ob_zones(symbol, tf, norm))
    if tf in {"2h", "4h", "1d"}:
        fvg_zonlari, _durum, _n = replay_fvg_zones(symbol, tf, norm)
        fvg = list(fvg_zonlari)
    else:
        fvg = []  # FVG motoru yalnız 2h/4h/1d (1h'da G5 yalnız OB)

    _frm, _olay, _meta = formasyon_kosu(norm, symbol=symbol, timeframe=tf)
    frm = list(_frm)

    return SeriHazirlik(
        symbol=symbol, tf=tf, norm=norm, atr=atr, events=events,
        swings=swings, ob=ob, fvg=fvg, frm=frm,
        split_i=int(0.7 * len(norm)),
    )


def karsit_yapilar(hazir: SeriHazirlik, i: int, giris: float) -> list[float]:
    """Girişin üstünde, ``i``'ye kadar onaylanmış karşıt yapı seviyeleri."""
    seviyeler: list[float] = []
    for s in hazir.swings:
        if str(getattr(s, "side", "")).lower() != "high":
            continue
        onay = getattr(s, "confirm_bar", None)
        if onay is None or int(onay) > i:
            continue  # gelecek onay okunmaz
        if getattr(s, "broken", False) and getattr(s, "broken_bar", None) is not None \
                and int(s.broken_bar) <= i:
            continue  # i'ye kadar kırılmış tepe hedef değil
        fiyat = getattr(s, "price", None)
        if fiyat is not None and float(fiyat) > giris:
            seviyeler.append(float(fiyat))
    for e in hazir.events:
        if int(getattr(e, "event_bar", 10**9)) > i:
            continue
        if int(getattr(e, "direction", 0)) >= 0:
            continue  # yalnız aşağı olayların kırılan seviyesi direnç sayılır
        lvl = getattr(e, "broken_level", None)
        if lvl is not None and float(lvl) > giris:
            seviyeler.append(float(lvl))
    return sorted(seviyeler)


def _sahne_etiketleri(g1, g2, g5, h, atr) -> list[str]:
    """FAZ9 A2 — tetik anının as-of sahne etiketleri (yalnız kayıt; filtre değil).

    Tecrübe Envanteri §H1 tohumu: etiketler plan kaydına yazılır, karar
    VERMEZ (sözleşme kırmızı çizgisi: kapılar az ve sığ; etiket = veri).
    """
    etiketler: list[str] = []
    if g1.onayli:
        etiketler.append("zemin_onayli")
    if g1.mesafe_atr is not None and float(g1.mesafe_atr) <= 0.5:
        etiketler.append("zemin_yakin")
    if g1.ilerleme == "REBASED_HIGHER":
        etiketler.append("zemin_kademe_yukari")
    elif g1.ilerleme == "REBASED_LOWER":
        etiketler.append("zemin_kademe_asagi")
    if g2.aktif:
        etiketler.append("formasyon_aktif")
        if g2.olgun:
            etiketler.append("formasyon_olgun")
    if getattr(h, "lehte", 0) >= 5:
        etiketler.append("ms_destek")
    if g5.bant is not None and atr:
        bant_y = (float(g5.bant[1]) - float(g5.bant[0])) / float(atr)
        if bant_y >= 2.0:
            etiketler.append("zone_genis")
        elif bant_y < 0.5:
            etiketler.append("zone_dar")
    if g5.dolu:
        etiketler.append("zone_dolu")
    return etiketler


# --- bir serinin bar bar döngüsü -------------------------------------------
@dataclass
class Sayac:
    bildirim: int = 0
    bitis: int = 0
    hukum: int = 0
    tetik: int = 0
    tetik_geometri: int = 0
    plan: int = 0
    teyit_red: int = 0
    sonuc: dict[str, int] = field(default_factory=lambda: {"hedef": 0, "stop": 0,
                                                           "yok": 0, "zaman": 0})
    hukum_dagilim: dict[str, int] = field(default_factory=lambda: {"BEKLE": 0, "UYGUN": 0, "RET": 0})


def seri_kosu(
    hazir: SeriHazirlik,
    hist: Any,
    defter: GolgeDefter,
    sayac: Sayac,
    b2_uyari: bool = False,
    b3_hedef: bool = False,
    b4_karakterli: bool = False,
    b5_olgunluk: bool = False,
) -> None:
    sembol, tf = hazir.symbol, hazir.tf
    norm = hazir.norm
    n = len(norm)
    dusukler = [float(x) for x in norm["low"].tolist()]
    kapanislar = [float(x) for x in norm["close"].tolist()]
    aktif: dict[str, tuple[tuple[str, str, str], int, int, Any]] = {}  # kim → (imza, doğuş i, geçerlilik, bildirim)
    son_hukum: str | None = None
    acik_plan: dict[str, Any] | None = None
    son_plan_i = -10**9

    for i in range(ILK_BAR, n):
        if i >= len(hazir.atr) or hazir.atr[i] is None:
            continue
        atr = float(hazir.atr[i])
        # RangeIndex'te zaman kolondadır (index 0..N-1); bar_zamani index'e bakmaz.
        t_iso = pd.Timestamp(norm.at[i, "timestamp"]).isoformat()
        fiyat = float(norm.at[i, "close"])

        g1 = g1_durumu(hist, pd.Timestamp(norm.at[i, "timestamp"]))
        g2 = g2_durumu(hazir.frm, i)
        ms_list = ms_uyarilari(hazir.events, i, yas_esik=KARSIT_YAS_ESIK_BAR)
        g5 = g5_durumu(hazir.ob, hazir.fvg, norm, i, yon="long")

        # --- bildiri yaşam döngüsü (append-only; değişiklikte yaz) ----------
        adaylar = bildirim_uret(sembol=sembol, tf=tf, t=t_iso, g1=g1, g2=g2,
                                ms_olaylari=ms_list, g5=g5)
        for b in adaylar:
            imza = (b.kim, b.iddia, b.kosul)
            mevcut = aktif.get(b.kim)
            if mevcut is None or mevcut[0] != imza:
                defter.yaz(b)
                sayac.bildirim += 1
                aktif[b.kim] = (imza, i, b.gecerlilik_bar, b)
        for kim in list(aktif):
            _imza, dogus, gec, _b = aktif[kim]
            if i - dogus >= gec > 0:
                defter.yaz({
                    "tip": "sessizlik", "tur": "bitis", "sembol": sembol, "tf": tf,
                    "t": t_iso, "kim": kim,
                    "gerekce": f"gecerlilik doldu ({gec} bar)",
                })
                sayac.bitis += 1
                del aktif[kim]

        # --- TYR (her bar; yalnız değişimde yaz) ----------------------------
        h = tyr_hukmu(TyrDurum(
            sembol=sembol, tf=tf, t=t_iso, g1=g1,
            ms=tuple(ms_list), g2=g2, planda=acik_plan is not None,
            # B2 (FAZ9, opt-in): kademe-yukarı uyarısı — çelişki sayacına +2,
            # TYR tavanı1'i aşınca BEKLE (plan gecikir; kesme değil, erteleme).
            ek_celiski=(2 if (b2_uyari and g1.ilerleme == "REBASED_HIGHER") else 0),
            olgunluk_genis=b5_olgunluk,
        ))
        if h.hukum != son_hukum:
            defter.yaz(h)
            sayac.hukum += 1
            son_hukum = h.hukum
        sayac.hukum_dagilim[h.hukum] = sayac.hukum_dagilim.get(h.hukum, 0) + 1

        # --- tetik + plan döngüsü -------------------------------------------
        # Tetik (kör bazın ham maddesi): G5 bandı + onaylı tepki — hüküm ne
        # olursa olsun, boşluksuz kaydedilir; örtüşmesizlik ölçümde uygulanır
        # (ev stili: 20 bar, açgözlü). Plan = tetik ∧ UYGUN ∧ geometri ∧
        # son plandan ≥20 bar ∧ giriş teyidi (Faz6 Revize1 T1505 — test+hold;
        # FAZ6_GIRIS_TEYIDI_KURALLARI Revize1).
        if acik_plan is None and g5.bant is not None and g5.tepki_onayi:
            donem = "kesif" if i < hazir.split_i else "dogrulama"
            bilinmeyenler = ["hacim doğrulanmadı (sıfır hacim kaydı)"]
            if g2.aktif:
                if b3_hedef and g2.mesafe_ust_atr is not None:
                    bilinmeyenler.append(
                        "formasyon üst sınırı statik G2 mesafesiyle aday (B3, tazelik sınırlı)"
                    )
                else:
                    bilinmeyenler.append("formasyon üst sınırı hedefe dahil edilmedi (G2 bağlam)")
            if not g1.onayli:
                bilinmeyenler.append("onaysız test: kırılma %51,6 (n=1616)")
            # B3 (FAZ9, opt-in): formasyon üst sınırı hedef yarışına aday.
            ust_aday = (
                fiyat + float(g2.mesafe_ust_atr) * atr
                if (b3_hedef and g2.aktif and g2.mesafe_ust_atr is not None)
                else None
            )
            kart = plan_karti_uret(
                plan_id=f"{sembol}-{tf}-{i}",
                sembol=sembol, tf=tf, t=t_iso, bar_index=i, donem=donem,
                giris=fiyat, atr=atr, destek=g1.destek, band=g5.bant,
                karsit_yapilar=karsit_yapilar(hazir, i, fiyat),
                ek_adaylar=(ust_aday,) if ust_aday is not None else (),
                karakter=str(g1.ilerleme or ""),
                karakterli_stop=b4_karakterli,
                hukum_satiri=h.satir,
                kaynak_bildirimler=tuple(f"{k}:{v[0][1]}" for k, v in aktif.items()),
                ek_bilinmeyenler=bilinmeyenler,
                zaman_stopu=ZAMAN_STOPU_BAR,
                aktif_bildirimler=tuple(  # FAZ9 A1: zengin bağlam (yalnız kayıt)
                    json.dumps(
                        {
                            "kim": b.kim, "iddia": b.iddia, "kosul": b.kosul,
                            "kaynak": b.kaynak, "dogrudan": b.dogrudan,
                            "kalan": max(0, int(gec) - (i - int(dogus))),
                            "seviyeler": [round(float(s), 4) for s in (b.seviyeler or ())],
                        },
                        ensure_ascii=False,
                    )
                    for (_imza, dogus, gec, b) in aktif.values()
                ),
                sahneler=tuple(_sahne_etiketleri(g1, g2, g5, h, atr)),  # FAZ9 A2
            )
            # Faz6 giriş teyidi (yalnız planı etkiler; tetik/kör baz değişmez)
            teyit_ok, teyit_neden = True, None
            if kart is not None:
                zemin_hatti = (max(float(g1.destek), float(g5.bant[0]))
                               if g1.destek is not None else float(g5.bant[0]))
                teyit_ok, teyit_neden = giris_teyidi(
                    low=dusukler, close=kapanislar, i=i,
                    zemin=zemin_hatti, atr=atr)
            bosluk_var = i >= son_plan_i + 20
            plan_mi = (kart is not None and h.hukum == "UYGUN"
                       and bosluk_var and teyit_ok)
            if kart is not None and h.hukum == "UYGUN" and bosluk_var and not teyit_ok:
                sayac.teyit_red += 1
            defter.yaz({
                "tip": "zincir_ozet", "tur": "tetik", "sembol": sembol, "tf": tf,
                "t": t_iso, "bar_index": i, "donem": donem,
                "hukum": h.hukum, "g1_kapali": g1.kapali,
                "g1_onayli": g1.onayli, "giris": fiyat, "atr": atr,
                "destek": g1.destek,
                "band_lo": g5.bant[0], "band_hi": g5.bant[1],
                "geometri": kart is not None,
                "stop": kart.stop if kart else None,
                "hedef": kart.hedef if kart else None,
                "R": kart.R if kart else None,
                "plan_id": kart.plan_id if plan_mi else None,
                "teyit": teyit_ok if kart is not None else None,
                "teyit_neden": (teyit_neden
                                if (kart is not None and not teyit_ok) else None),
            })
            sayac.tetik += 1
            if kart is not None:
                sayac.tetik_geometri += 1
            if plan_mi:
                defter.yaz(kart)
                sayac.plan += 1
                son_plan_i = i
                acik_plan = {
                    "plan_id": kart.plan_id, "giris": kart.giris,
                    "stop": kart.stop, "hedef": kart.hedef,
                    "atr": atr, "H": kart.zaman_stopu,
                    "t": t_iso, "donem": kart.donem, "bar_index": i,
                    "mae": 0.0,
                }
            continue

        if acik_plan is None:
            continue  # bant/onay yok: açık plan da yok → yarış bloğuna düşülmez

        # --- açık plan: yarış bar bar sürer (gelecek bar okunmaz) -----------
        # Giriş = plan barının kapanışı; sonraki her bar kapanışı sırayla
        # denenir. Aynı barda çift dokunuş → stop (muhafazakâr). H bar'da
        # çözüm yoksa zaman çıkışı (mark-to-market). Veri biterse sansür.
        k = i - acik_plan["bar_index"]          # girişten sonraki bar sayısı
        c = fiyat
        aday_mae = (c - acik_plan["giris"]) / acik_plan["atr"]
        acik_plan["mae"] = min(acik_plan["mae"], aday_mae)
        hit_stop = c <= acik_plan["stop"]
        hit_hedef = c >= acik_plan["hedef"]
        sonuc = cozunme = pnl = None
        if hit_stop:                            # eşitlik → stop (muhafazakâr)
            sonuc, cozunme = "stop", k
            pnl = -(acik_plan["giris"] - acik_plan["stop"]) / acik_plan["atr"]
        elif hit_hedef:
            sonuc, cozunme = "hedef", k
            pnl = (acik_plan["hedef"] - acik_plan["giris"]) / acik_plan["atr"]
        elif k >= acik_plan["H"]:
            sonuc, cozunme = "zaman", acik_plan["H"]
            pnl = (c - acik_plan["giris"]) / acik_plan["atr"]
        if sonuc is not None:
            defter.yaz(IslemSonucu(
                plan_id=acik_plan["plan_id"], sembol=sembol, tf=tf, t=acik_plan["t"],
                sonuc=sonuc, cozunme_bar=cozunme, pnl_atr=round(pnl, 4),
                mae_atr=round(acik_plan["mae"], 4),
            ))
            sayac.sonuc[sonuc] = sayac.sonuc.get(sonuc, 0) + 1
            acik_plan = None


# --- ana --------------------------------------------------------------------
def evren(limit: int = 0, semboller: list[str] | None = None) -> list[str]:
    if semboller:
        return sorted(set(semboller))
    hepsi = [s for s in arsiv_sembolleri() if s not in HAVUZ_DISI_SEMBOLLER]
    hepsi = sorted(hepsi)
    return hepsi[:limit] if limit else hepsi


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Gölge zincir replay (T1)")
    p.add_argument("--semboller", default="", help="virgülle ayrılmış sembol listesi")
    p.add_argument("--limit", type=int, default=0, help="ilk N sembol (0 = tümü)")
    p.add_argument("--tf", default="1h,2h,4h,1d", help="izleme TF'leri")
    p.add_argument("--cikti", default=str(VARSAYILAN_CIKTI))
    p.add_argument("--devam", action="store_true",
                   help="mevcut deftere ekle (varsayılan: taze koşu)")
    p.add_argument("--zaman-stopu", type=int, default=10,
                   help="plan zaman stopu, bar (Faz7:15/20 testi)")
    # FAZ9 B-turu bayrakları (varsayılan kapalı → baz davranış aynı)
    p.add_argument("--b2-uyari", action="store_true",
                   help="B2: kademe-yukarı TYR çelişki uyarısı (+2 → BEKLE)")
    p.add_argument("--b3-hedef", action="store_true",
                   help="B3: formasyon üst sınırı hedef yarışına aday")
    p.add_argument("--b4-karakterli", action="store_true",
                   help="B4: dikey-yükselen karakterde stop tamponu 0,10 → 0,30 ATR")
    p.add_argument("--b5-olgunluk", action="store_true",
                   help="B5: onaylı zemin + taze MS desteği birlikte olgunluk yapar")
    args = p.parse_args(argv)

    global ZAMAN_STOPU_BAR
    ZAMAN_STOPU_BAR = max(1, args.zaman_stopu)

    cikti = Path(args.cikti)
    cikti.mkdir(parents=True, exist_ok=True)
    defter_yol = cikti / "golge_defter.jsonl"
    if defter_yol.exists() and not args.devam:
        defter_yol.unlink()

    tfs = [x.strip().lower() for x in args.tf.split(",") if x.strip()]
    semboller = evren(
        limit=args.limit,
        semboller=[s.strip().upper() for s in args.semboller.split(",") if s.strip()],
    )

    bas = time.time()
    sayac = Sayac()
    hatalar: list[dict[str, str]] = []
    seri_sayisi = 0

    with GolgeDefter(defter_yol) as defter:
        for no, sembol in enumerate(semboller, start=1):
            try:
                gunluk = tf_frame(sembol, "1d")
                h4 = tf_frame(sembol, "4h")
                hist = build_single_pass_history(sembol, gunluk, h4)
            except Exception as hata:  # noqa: BLE001 — G1 yoksa zincir başlamaz
                hatalar.append({"sembol": sembol, "adim": "g1", "hata": repr(hata)})
                continue

            for tf in tfs:
                try:
                    frame = tf_frame(sembol, tf)
                    if len(frame) < ILK_BAR + 30:
                        continue
                    hazir = seri_hazirla(sembol, tf, frame)
                    seri_kosu(hazir, hist, defter, sayac,
                              b2_uyari=args.b2_uyari,
                              b3_hedef=args.b3_hedef,
                              b4_karakterli=args.b4_karakterli,
                              b5_olgunluk=args.b5_olgunluk)
                    seri_sayisi += 1
                except Exception as hata:  # noqa: BLE001 — seri hatası zinciri durdurmaz
                    hatalar.append({"sembol": sembol, "tf": tf,
                                    "adim": "seri", "hata": repr(hata)})
            if no % 25 == 0:
                print(f"  {no}/{len(semboller)} sembol · "
                      f"plan={sayac.plan} hukum={sayac.hukum} "
                      f"bildirim={sayac.bildirim} · {time.time() - bas:.0f}s",
                      flush=True)

    ozet = {
        "parametreler": {
            "evren": len(semboller), "tfs": tfs, "ilksar_bar": ILK_BAR,
            "zaman_stopu": ZAMAN_STOPU_BAR, "plan_araligi_bar": 20,
            "bolme": "kesif/dogrulama %70/%30",
        },
        "seri_sayisi": seri_sayisi,
        "sayacler": {
            "bildirim": sayac.bildirim, "bitis": sayac.bitis,
            "hukum_yazim": sayac.hukum, "hukum_dagilim": sayac.hukum_dagilim,
            "tetik": sayac.tetik, "tetik_geometri": sayac.tetik_geometri,
            "plan": sayac.plan, "teyit_red": sayac.teyit_red,
            "sonuc": sayac.sonuc,
        },
        "hatalar": hatalar[:200],
        "hata_sayisi": len(hatalar),
        "sure_sn": round(time.time() - bas, 1),
        "defter": str(defter_yol.relative_to(KOK)) if defter_yol.is_relative_to(KOK) else str(defter_yol),
    }
    (cikti / "ozet.json").write_text(
        json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(ozet["sayacler"], ensure_ascii=False, indent=2))
    print(f"Bitti: {seri_sayisi} seri · {len(hatalar)} hata · {ozet['sure_sn']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
