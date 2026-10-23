# -*- coding: utf-8 -*-
"""Kova fazı ölçümü (P2-2): faz kaymasının etki ölçümü + düzeltme doğrulaması.

Canlıda 2s/4s serisi, 360 barlık kayan deque penceresinden üretilir. Pencere
her yeni 1s barda 1 kaydığı için ilk barın gün-içi saati değişir ve kova
fazları döner. Bu betik etkiyi İKİ seviyede ölçer (ağ yok; veri
`backfill_data/*_1h.csv.gz`):

  Seviye 1 (kova): aynı pencere sonu, pencere başı 0..8 bar kaydırma.
    - Kaç farklı faz çıkıyor, kaymaların kaçı doğru (09:30) fazda?
    - Eski seri ile sabit-çapalı serinin etiket/OHLVC çakışması ne kadar?

  Seviye 2 (motor): aynı pencerede `ArgentEngine.process(tam_yeniden=True)`
    nihai kararı fazlar arasında ne sıklıkta değişiyor? Canlı tarama da her
    turda tam yeniden oynattığı için "bir saat arayla iki tarama aynı hissede
    farklı karar" oranı doğrudan buradan okunur.

Sabit çapa (`offset="9h30min"`) ölçüm referansıdır.

GÜNCELLEME (2026-10-23): FAZ düzeltmesi uygulandi; üretim `resample_ohlcv`
artık aynı sabit çapayı kullanıyor. Betik bu hâliyle regresyon denetimidir:
beklenen `dogru_faz_oran = 1.0`, motor durum/desen farkı ~0 (kalan imza
farkı yalnız pencere başındaki kısmi kovadan gelen kalite ±0,1 oynaklığı).
Düzeltme öncesi taban: 2s %55,6 / 4s %33,3 doğru faz; durum farkı
%19,2 / %33,3. Rapor: docs/arastirma/KOVA_FAZI_OLCUMU_2026-10-23.md

Kullanım:
    python scripts/kova_fazi_olcumu.py [--semboller ALARK,AKBNK] [--motorsuz]
                                       [--json sonuc.json]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import pandas as pd  # noqa: E402

import data as data_mod  # noqa: E402

logging.disable(logging.WARNING)

DOGRU_ETIKET = {
    "2h": {"09:30", "11:30", "13:30", "15:30", "17:30"},
    "4h": {"09:30", "13:30", "17:30"},
}
VARSAYILAN_SEMBOLLER = [
    "ALARK", "AKBNK", "KCHOL", "TTKOM", "EREGL", "KRDMD", "DOHOL", "AYDEM",
    "TOASO", "ENKAI", "DOAS", "ARCLK", "TAVHL", "CIMSA", "SASA", "THYAO",
    "ASELS", "GARAN", "SISE", "TCELL",
]
MOTOR_SEMBOLLERI = ["ALARK", "AKBNK", "KCHOL", "TTKOM", "EREGL", "DOHOL"]


def yukle_1h(sembol: str) -> pd.DataFrame | None:
    yol = REPO / "backfill_data" / f"{sembol}_1h.csv.gz"
    if not yol.exists():
        return None
    df = pd.read_csv(yol)
    df.index = pd.to_datetime(df.pop("bar_time"))
    return df.sort_index()


def resample_sabit(df_1h: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """`data.resample_ohlcv` ile aynı toplama, tek fark: SABİT 09:30 çapası."""
    df = df_1h.copy()
    df.columns = [c.lower() for c in df.columns]
    agg = {"open": "first", "high": "max", "low": "min",
           "close": "last", "volume": "sum"}
    cols = {k: v for k, v in agg.items() if k in df.columns}
    out = df.resample(timeframe, offset="9h30min").agg(cols)
    out.dropna(inplace=True)
    return out


def etiketler(df: pd.DataFrame) -> set[str]:
    return {f"{t.hour:02d}:{t.minute:02d}" for t in df.index}


def seviye1_kova(semboller, pencere=360, bitisler=(0, 150, 300), kaymalar=range(9)):
    ozet = {tf: {"senaryo": 0, "dogru_faz": 0, "faz_cesidi": set(),
                 "etiket_kesisim": [], "ortak_ohlc_fark": []}
            for tf in ("2h", "4h")}
    for sembol in semboller:
        df = yukle_1h(sembol)
        if df is None or len(df) < pencere + max(bitisler) + max(kaymalar):
            continue
        for geri in bitisler:
            son = len(df) - geri
            baz = df.iloc[son - pencere:son]
            for tf in ("2h", "4h"):
                sabit = resample_sabit(baz, tf)
                for k in kaymalar:
                    w = baz.iloc[k:]
                    eski = data_mod.resample_ohlcv(w, tf)
                    if eski.empty:
                        continue
                    et = etiketler(eski)
                    o = ozet[tf]
                    o["senaryo"] += 1
                    o["faz_cesidi"].add(tuple(sorted(et)))
                    if et <= DOGRU_ETIKET[tf]:
                        o["dogru_faz"] += 1
                    ortak = eski.index.intersection(sabit.index)
                    o["etiket_kesisim"].append(
                        len(ortak) / max(1, len(sabit)))
                    if len(ortak):
                        a = eski.loc[ortak, ["open", "high", "low", "close"]]
                        b = sabit.loc[ortak, ["open", "high", "low", "close"]]
                        fark = (a - b).abs().max(axis=1) > 1e-9
                        o["ortak_ohlc_fark"].append(float(fark.mean()))
    cikis = {}
    for tf, o in ozet.items():
        n = max(1, o["senaryo"])
        cikis[tf] = {
            "senaryo": o["senaryo"],
            "dogru_faz_oran": round(o["dogru_faz"] / n, 4),
            "farkli_faz_sayisi": len(o["faz_cesidi"]),
            "fazlar": [list(f) for f in sorted(o["faz_cesidi"])],
            "etiket_kesisim_ort": round(
                sum(o["etiket_kesisim"]) / max(1, len(o["etiket_kesisim"])), 4),
            "ortak_bar_ohlc_fark_oran_ort": round(
                sum(o["ortak_ohlc_fark"]) / max(1, len(o["ortak_ohlc_fark"])), 4),
        }
    return cikis


def _imza(snap):
    a = snap.active
    return (
        str(snap.state),
        (a.pattern_type if a is not None else None),
        int(snap.break_dir or 0),
        (round(float(a.raw_quality), 1) if a is not None else None),
    )


def seviye2_motor(semboller, pencere=360, bitis_adim=75, bitis_sayisi=5):
    from patterns.lifecycle import ArgentEngine

    sayaç = {tf: {"pencere": 0, "eski_vs_sabit_farkli": 0, "eski_vs_sabit_toplam": 0,
                  "ardisik_kayma_farkli": 0, "ardisik_kayma_toplam": 0,
                  "durum_farkli": 0, "desen_farkli": 0}
             for tf in ("2h", "4h")}
    ornekler = []
    for sembol in semboller:
        df = yukle_1h(sembol)
        if df is None:
            continue
        for j in range(bitis_sayisi):
            son = len(df) - j * bitis_adim
            if son - pencere - 3 < 0:
                continue
            baz = df.iloc[son - pencere:son]
            for tf in ("2h", "4h"):
                imzalar = {}
                for k in range(4):
                    seri = data_mod.resample_ohlcv(baz.iloc[k:], tf)
                    if len(seri) < 40:
                        continue
                    motor = ArgentEngine(profile="Dengeli", timeframe=tf)
                    imzalar[k] = _imza(motor.process(seri, tam_yeniden=True))
                sabit_seri = resample_sabit(baz, tf)
                if len(sabit_seri) < 40 or not imzalar:
                    continue
                motor = ArgentEngine(profile="Dengeli", timeframe=tf)
                sabit_imza = _imza(motor.process(sabit_seri, tam_yeniden=True))
                s = sayaç[tf]
                s["pencere"] += 1
                onceki = None
                for k in sorted(imzalar):
                    imza = imzalar[k]
                    s["eski_vs_sabit_toplam"] += 1
                    if imza != sabit_imza:
                        s["eski_vs_sabit_farkli"] += 1
                        if len(ornekler) < 8:
                            ornekler.append({
                                "sembol": sembol, "tf": tf, "kayma": k,
                                "bitis": str(baz.index[-1]),
                                "eski": imza, "sabit": sabit_imza})
                    if imza[0] != sabit_imza[0]:
                        s["durum_farkli"] += 1
                    if imza[1] != sabit_imza[1]:
                        s["desen_farkli"] += 1
                    if onceki is not None:
                        s["ardisik_kayma_toplam"] += 1
                        if imza != onceki:
                            s["ardisik_kayma_farkli"] += 1
                    onceki = imza
    cikis = {}
    for tf, s in sayaç.items():
        t = max(1, s["eski_vs_sabit_toplam"])
        a = max(1, s["ardisik_kayma_toplam"])
        cikis[tf] = {
            "pencere": s["pencere"],
            "eski_vs_sabit_farkli_oran": round(s["eski_vs_sabit_farkli"] / t, 4),
            "durum_farkli_oran": round(s["durum_farkli"] / t, 4),
            "desen_farkli_oran": round(s["desen_farkli"] / t, 4),
            "ardisik_saat_karar_degisimi_oran": round(
                s["ardisik_kayma_farkli"] / a, 4),
            "karsilastirma_sayisi": s["eski_vs_sabit_toplam"],
        }
    cikis["ornekler"] = ornekler
    return cikis


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--semboller", default=",".join(VARSAYILAN_SEMBOLLER))
    ap.add_argument("--motorsuz", action="store_true")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    semboller = [s.strip().upper() for s in args.semboller.split(",") if s.strip()]
    sonuc = {"seviye1_kova": seviye1_kova(semboller)}
    if not args.motorsuz:
        motor_sembolleri = [s for s in MOTOR_SEMBOLLERI if s in semboller]
        sonuc["seviye2_motor"] = seviye2_motor(motor_sembolleri or semboller[:6])

    print(json.dumps(sonuc, ensure_ascii=False, indent=2, default=str))
    if args.json:
        Path(args.json).write_text(
            json.dumps(sonuc, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
