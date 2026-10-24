# -*- coding: utf-8 -*-
"""Her etiket varyantı için ayrı rastgele taban üret.

SALT OKUNUR (fiyat verisi) → `var/replay/taban_<leh>_<ters>_<ufuk>.csv` yazar.

Neden gerekli: `kontrol_eslesmis.py` tabanı tek bir etiket tanımıyla (2/1/24)
üretmişti. "Fazla" farklı etiketlerle karşılaştırılınca elma-armut oluyor;
taban ile gözlem aynı tanımı kullanmak zorunda. Bu betik 7 varyantın hepsini
tek fiyat geçişinde üretir.

Kullanım:
    python scripts/taban_uret.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from data import resample_ohlcv  # noqa: E402
from patterns.indicators import calculate_atr  # noqa: E402
from kontrol_deneyi import ilk_vurus, etiketle_np, endeks, UFUK_MAX  # noqa: E402

VARYANTLAR = [
    (1.0, 1.0, 12), (1.0, 1.0, 24), (1.5, 1.0, 24), (2.0, 1.0, 24),
    (2.0, 1.5, 24), (2.0, 1.0, 48), (3.0, 1.0, 48),
]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Etiket varyantı başına rastgele taban")
    ap.add_argument("--semboller", default="")
    ap.add_argument("--cikti", default="var/replay")
    args = ap.parse_args(argv)

    if args.semboller:
        semboller = [s.strip() for s in args.semboller.split(",") if s.strip()]
    else:
        semboller = sorted(p.name.split("_1h.csv.gz")[0]
                           for p in (REPO / "backfill_data").glob("*_1h.csv.gz"))
    print(f"{len(semboller)} sembol · {len(VARYANTLAR)} varyant", flush=True)

    kayit: Dict[str, List[Dict]] = {f"{a:g}_{b:g}_{c}": [] for a, b, c in VARYANTLAR}
    for i, sembol in enumerate(semboller, 1):
        p = REPO / "backfill_data" / f"{sembol}_1h.csv.gz"
        if not p.exists():
            continue
        d1h = pd.read_csv(p, compression="gzip", parse_dates=["bar_time"]).set_index("bar_time")
        d1h = d1h[~d1h.index.duplicated(keep="last")].sort_index()
        for tf in ("1h", "2h", "4h", "1d"):
            d = d1h if tf == "1h" else resample_ohlcv(d1h, tf)
            n = len(d)
            if n < 120:
                continue
            atr = calculate_atr(d, 14).to_numpy(float)
            high = d["high"].to_numpy(float)
            low = d["low"].to_numpy(float)
            close = d["close"].to_numpy(float)
            egim = endeks(tf)
            idx_ns = pd.to_datetime(egim.index, utc=True).astype("int64").to_numpy()
            son = n - UFUK_MAX - 1
            if son < 50:
                continue
            idx = np.arange(0, son)
            idx = idx[(atr[idx] > 0) & np.isfinite(atr[idx])]
            if len(idx) < 50:
                continue
            konum = np.searchsorted(idx_ns, pd.to_datetime(d.index[idx], utc=True)
                                    .astype("int64").to_numpy(), side="right") - 1
            ok = (konum >= 0) & (konum < len(egim))
            isaret = np.zeros(len(idx))
            isaret[ok] = np.sign(egim.to_numpy()[konum[ok]])
            gecerli = ok & (isaret != 0)
            pencere = np.arange(1, UFUK_MAX + 1)
            kollar = np.clip(idx[:, None] + pencere[None, :], 0, n - 1)
            yukari = high[kollar] - close[idx][:, None]
            asagi = close[idx][:, None] - low[kollar]
            a = atr[idx]
            ay = d.index[idx].strftime("%Y-%m")
            for leh, ters, ufuk in VARYANTLAR:
                up_leh = ilk_vurus(yukari, leh * a)
                up_ters = ilk_vurus(yukari, ters * a)
                dn_leh = ilk_vurus(asagi, leh * a)
                dn_ters = ilk_vurus(asagi, ters * a)
                y_long = etiketle_np(up_leh, dn_ters, ufuk)
                y_short = etiketle_np(dn_leh, up_ters, ufuk)
                anahtar = f"{leh:g}_{ters:g}_{ufuk}"
                for yon, y in ((1, y_long), (-1, y_short)):
                    m = gecerli & np.isfinite(y)
                    if m.sum() < 20:
                        continue
                    sub = pd.DataFrame({"ay": ay[m], "y": y[m]})
                    for a_, g in sub.groupby("ay"):
                        kayit[anahtar].append({"sembol": sembol, "tf": tf, "ay": a_,
                                               "yon": yon, "n": len(g),
                                               "basari": int(g.y.sum())})
        if i % 20 == 0 or i == len(semboller):
            print(f"  {i}/{len(semboller)}", flush=True)

    for anahtar, satirlar in kayit.items():
        r = pd.DataFrame(satirlar)
        hedef = REPO / args.cikti / f"taban_{anahtar}.csv"
        r.to_csv(hedef, index=False)
        print(f"{hedef.name}: {len(r)} hücre · %{r.basari.sum()/r.n.sum()*100:.1f} taban")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
