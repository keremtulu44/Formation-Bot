"""Sembol sembol ok denetimi koşusu (salt-okuma).

Kullanım:
    PYTHONPATH=. .venv/bin/python research/stabil_ok_denetimi_tara.py [SEMBOL_SAYISI] [ETIKET]

Çıktı (docs/arastirma/ok_sistemi/):
    ok_denetimi_<ETIKET>.csv        her ok: kural, gerekçe, bayrak, karar
    ok_ozet_sembol_<ETIKET>.csv     sembol başına ok sayıları

Üretim kodunu değiştirmez; yalnız `evaluate_stabil_symbol` çıktısını okur.
"""
from __future__ import annotations

import glob
import os
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd

from data import resample_ohlcv
from domain_engines.stabil.runtime import evaluate_stabil_symbol
from research.stabil_ok_denetimi import aciklama, denetle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/arastirma/ok_sistemi"


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    etiket = sys.argv[2] if len(sys.argv) > 2 else "2026_11_08"
    syms = sorted(os.path.basename(p).split("_")[0] for p in glob.glob(str(ROOT / "backfill_data/*_1d.csv.gz")))[:limit]
    rows: list[dict] = []
    ozet: list[dict] = []
    t0 = time.time()
    for s in syms:
        try:
            d = (pd.read_csv(ROOT / f"backfill_data/{s}_1d.csv.gz", compression="gzip", parse_dates=["bar_time"])
                 .set_index("bar_time").reset_index().rename(columns={"bar_time": "timestamp"}))
            h = (pd.read_csv(ROOT / f"backfill_data/{s}_1h.csv.gz", compression="gzip", parse_dates=["bar_time"])
                 .set_index("bar_time"))
            h4 = resample_ohlcv(h, "4h").reset_index().rename(columns={"bar_time": "timestamp"})
            out = evaluate_stabil_symbol(s, "4h", h4, daily_frame=d, h4_frame=h4)
        except Exception:
            continue
        ks = denetle(out.bar_behaviors)
        for k in ks:
            rows.append(dict(sembol=s, zaman=str(k.bar_close_time)[:16], ok=k.ok, kural=k.kural_adi,
                             karar=k.karar, bayraklar="|".join(k.bayraklar), rejim=k.rejim,
                             mesafe_atr=k.mesafe_atr, govde_atr=k.govde_atr, rvol=k.rvol,
                             temas=k.temas, gerekce=aciklama(k)))
        ozet.append(dict(sembol=s, bar=len(out.bar_behaviors), ok=len(ks),
                         up=sum(1 for k in ks if k.ok == "▲"), down=sum(1 for k in ks if k.ok == "▼"),
                         saglam=sum(1 for k in ks if k.karar == "SAĞLAM"),
                         zayif=sum(1 for k in ks if k.karar == "ZAYIF"),
                         supheli=sum(1 for k in ks if k.karar == "ŞÜPHELİ")))
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / f"ok_denetimi_{etiket}.csv", index=False)
    pd.DataFrame(ozet).to_csv(OUT / f"ok_ozet_sembol_{etiket}.csv", index=False)
    print(f"sembol={len(ozet)} ok={len(df)} süre={time.time()-t0:.0f}s")
    print("kural:", Counter(df.kural).most_common())
    print("karar:", Counter(df.karar).most_common())
    print("bayrak:", Counter(b for x in df.bayraklar if isinstance(x, str) and x for b in x.split("|")).most_common())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
