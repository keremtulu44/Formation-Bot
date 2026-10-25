# -*- coding: utf-8 -*-
"""Aile içi fazla eğilimi — kama/üçgen etkisini çıkardıktan sonra ne kalıyor?

SALT OKUNUR. Girdi: `var/replay/ozellikler177.csv` + `var/replay/taban_*.csv`

Önceki adım (`fazla_egilim.py`) kama vs üçgen farkını (+6,1 puan) buldu ve
olgunluk / daralma / yapı uyumu gibi boyutların bu farkın **vekili** olduğunu
gösterdi. Burada aynı tarama **aile içinde** tekrarlanır: kama gözlemleri
kendi içinde, üçgen gözlemleri kendi içinde.

Geçme koşulu: Q5−Q1 etkisi iki ailede de aynı işaret, |etki| ≥ 1,0 puan,
sembol bootstrap GA sıfırı dışlıyor, S ve Z doğrulamada aynı işaret,
≥6/7 etiket varyantında aynı işaret.

Kullanım:
    python scripts/fazla_ic_egilim.py
"""

from __future__ import annotations

import argparse
import sys
import zlib
from pathlib import Path
from typing import List, Optional

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fazla_model import fazla_serisi, VARYANTLAR  # noqa: E402
from fazla_egilim import SAYISAL, eslesmis_fark  # noqa: E402


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Aile içi fazla eğilimi")
    ap.add_argument("--girdi", default="var/replay/ozellikler177.csv")
    ap.add_argument("--rapor", default="var/replay/fazla_ic_egilim.md")
    args = ap.parse_args(argv)

    d = pd.read_csv(REPO / args.girdi, low_memory=False)
    d["tarih"] = pd.to_datetime(d["tarih"], utc=True, errors="coerce").dt.tz_localize(None)
    d = d[d.tarih.notna()].reset_index(drop=True)
    d["ay"] = d.tarih.dt.to_period("M").astype(str)
    d["_idx"] = np.arange(len(d))
    d["ds"] = d.sembol.apply(lambda s: zlib.crc32(s.encode()) % 2)
    d["z_dogrulama"] = d.tarih > d.tarih.quantile(0.70)

    fazla = {f"{a:g}/{b:g}/{c}": fazla_serisi(d, a, b, c) for a, b, c in VARYANTLAR}
    ana = fazla["2/1/24"].to_numpy()
    ok = ~np.isnan(ana)
    aile = d.aile.to_numpy()

    def ort(maske):
        return pd.Series(ana[maske], index=d.index[maske]).groupby(d.loc[maske, "sembol"]).mean()

    satir: List[dict] = []
    for kolon in SAYISAL:
        if kolon not in d.columns:
            continue
        kayit = {"boyut": kolon}
        gecerli = True
        for ai, a in enumerate(("Kama", "Üçgen")):
            m_aile = aile == a
            alt_m = np.zeros(len(d), bool)
            ust_m = np.zeros(len(d), bool)
            try:
                kova = pd.qcut(pd.Series(d[kolon]).rank(method="first"), 5, labels=[1, 2, 3, 4, 5])
            except (ValueError, TypeError):
                gecerli = False
                break
            alt_m[(kova == 1).to_numpy() & m_aile & ok] = True
            ust_m[(kova == 5).to_numpy() & m_aile & ok] = True
            if alt_m.sum() < 150 or ust_m.sum() < 150:
                gecerli = False
                break
            etki, lo, hi = eslesmis_fark(ort(ust_m), ort(alt_m))
            kayit[f"etki_{a}"] = etki
            kayit[f"lo_{a}"] = lo
            kayit[f"hi_{a}"] = hi
            kayit[f"n_{a}"] = int(alt_m.sum() + ust_m.sum())
            if ai == 0:
                alt_t, ust_t = alt_m, ust_m
        if not gecerli:
            continue
        a1, a2 = kayit["etki_Kama"], kayit["etki_Üçgen"]
        if np.isnan(a1) or np.isnan(a2) or a1 * a2 <= 0:
            continue
        # birleşik (aile içi ağırlıklı) etki
        birlesik = (a1 + a2) / 2
        s_ = float(np.nanmean(ana[ust_t & (d.ds == 1).to_numpy()])
                   - np.nanmean(ana[alt_t & (d.ds == 1).to_numpy()])) * 100
        z_ = float(np.nanmean(ana[ust_t & d.z_dogrulama.to_numpy()])
                   - np.nanmean(ana[alt_t & d.z_dogrulama.to_numpy()])) * 100
        isaret = 0
        for v in fazla.values():
            va = v.to_numpy()
            f_ = np.nanmean(va[ust_t]) - np.nanmean(va[alt_t])
            isaret += 1 if f_ * birlesik > 0 else -1
        gecti = (abs(birlesik) >= 1.0 and abs(isaret) >= 6 and s_ * birlesik > 0 and z_ * birlesik > 0
                 and ((kayit["lo_Kama"] > 0 and kayit["lo_Üçgen"] > 0)
                      or (kayit["hi_Kama"] < 0 and kayit["hi_Üçgen"] < 0)))
        kayit.update(birlesik=birlesik, S=s_, Z=z_, varyant=isaret, gecti=gecti,
                     n=kayit["n_Kama"] + kayit["n_Üçgen"])
        satir.append(kayit)

    g = pd.DataFrame(satir).sort_values("birlesik", key=abs, ascending=False)
    out = ["# Aile içi fazla eğilimi — kama/üçgen farkı çıkarıldıktan sonra\n",
           f"gözlem {int(ok.sum())} · boyut {len(g)} · geçen {int(g.gecti.sum())}\n",
           "| boyut | kama Q5−Q1 | üçgen Q5−Q1 | birleşik | S | Z | varyant | n | geçti |",
           "|---|---|---|---|---|---|---|---|---|"]
    for _, s in g.iterrows():
        out.append(f"| {s.boyut} | {s.etki_Kama:+.1f} [{s.lo_Kama:+.1f},{s.hi_Kama:+.1f}] | "
                   f"{s.etki_Üçgen:+.1f} [{s.lo_Üçgen:+.1f},{s.hi_Üçgen:+.1f}] | "
                   f"**{s.birlesik:+.1f}** | {s.S:+.1f} | {s.Z:+.1f} | {s.varyant:+d}/7 | "
                   f"{s.n} | {'✅' if s.gecti else '—'} |")
    metin = "\n".join(out)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(metin)
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
