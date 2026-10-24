# -*- coding: utf-8 -*-
"""Fazla eğilimi — hangi boyut formasyonun katkısını gerçekten eğriyor?

SALT OKUNUR. Girdi: `var/replay/ozellikler177.csv` + `var/replay/taban_*.csv`

Önceki tarama (`fazla_tarama.py`) her kovayı ayrı test ediyordu; 201 hücrede
ortadaki bir kovanın parlaması çoklukla şans. Burada boyut **bütün olarak**
test edilir:

* sayısal boyut → uçlar arası fark (Q5 − Q1), sembol eşleşmiş bootstrap
* kategorik boyut → hücre − dışarısı

Ek olarak eğimin tekdüzeliği (Spearman) ve 7 etiket varyantında işaret
tutarlılığı raporlanır. Geçme koşulu dördü birlikte ister:
|etki| ≥ 1,0 puan · GA sıfırı dışlıyor · S ve Z doğrulamada aynı işaret ·
≥6/7 varyantta aynı işaret.

Kullanım:
    python scripts/fazla_egilim.py
"""

from __future__ import annotations

import argparse
import sys
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fazla_model import fazla_serisi, VARYANTLAR  # noqa: E402

SAYISAL = [
    "kalite", "bant_mesafe_atr", "bant_genislik_atr", "sure_orani", "daralma",
    "temas_puan", "olgunluk", "geometri", "egim", "ihlal_cezasi", "guc",
    "hacim_orani", "hacim_formasyon", "h_atr_yuzdelik", "h_atr_sikisma",
    "d_atr_yuzdelik", "d_sikisma", "d_yapi_net", "d_engel_atr", "d_zirve_mesafe",
    "d_ust_ma50", "d_ust_ma200", "h_ust_ma20", "h_govde_konum", "h_aralik_atr",
    "p_breadth", "p_dispersion", "beta60", "kore60", "goreli_guc", "akran_mom5",
    "endeks_egim", "e_x_gun_ici", "e_x_ret20", "h_ret20", "d_ret20", "d_ret60",
    "bar_sayisi", "gecikme_bar", "seans_saati", "gun", "st_0",
]

KATEGORIK = ["desen", "aile", "tf", "yon", "yapi_uyum", "mtf_uyum", "zirve_uyum",
             "endeks_uyum", "retest_var"]


def eslesmis_fark(a: pd.Series, b: pd.Series, tekrar: int = 1500, rng=None):
    rng = rng or np.random.default_rng(7)
    a = a.dropna()
    b = b.dropna()
    ortak = a.index.intersection(b.index)
    if len(ortak) < 15:
        return float("nan"), float("nan"), float("nan")
    A = a.loc[ortak].to_numpy()
    B = b.loc[ortak].to_numpy()
    idx = rng.integers(0, len(ortak), (tekrar, len(ortak)))
    d = (A[idx] - B[idx]).mean(axis=1) * 100
    return float((A.mean() - B.mean()) * 100), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Fazla eğilimi")
    ap.add_argument("--girdi", default="var/replay/ozellikler177.csv")
    ap.add_argument("--rapor", default="var/replay/fazla_egilim.md")
    args = ap.parse_args(argv)

    d = pd.read_csv(REPO / args.girdi, low_memory=False)
    d["tarih"] = pd.to_datetime(d["tarih"], utc=True, errors="coerce").dt.tz_localize(None)
    d = d[d.tarih.notna()].reset_index(drop=True)
    d["ay"] = d.tarih.dt.to_period("M").astype(str)
    d["_idx"] = np.arange(len(d))
    d["ds"] = d.sembol.apply(lambda s: zlib.crc32(s.encode()) % 2)
    d["z_dogrulama"] = d.tarih > d.tarih.quantile(0.70)

    fazla = {f"{a:g}/{b:g}/{c}": fazla_serisi(d, a, b, c) for a, b, c in VARYANTLAR}
    ana = fazla["2/1/24"]
    ok = ana.notna().to_numpy()

    def sembol_ort(maske: np.ndarray) -> pd.Series:
        return pd.Series(ana.to_numpy()[maske], index=d.index[maske]).groupby(
            d.loc[maske, "sembol"]).mean()

    satir: List[dict] = []
    for kolon in SAYISAL:
        if kolon not in d.columns:
            continue
        try:
            kova = pd.qcut(d[kolon].rank(method="first"), 5, labels=[1, 2, 3, 4, 5])
        except (ValueError, TypeError):
            continue
        alt = (kova == 1).to_numpy() & ok
        ust = (kova == 5).to_numpy() & ok
        if alt.sum() < 200 or ust.sum() < 200:
            continue
        etki, lo, hi = eslesmis_fark(sembol_ort(ust), sembol_ort(alt))
        s_ = float(np.nanmean(ana.to_numpy()[ust & (d.ds == 1).to_numpy()])
                   - np.nanmean(ana.to_numpy()[alt & (d.ds == 1).to_numpy()])) * 100
        z_ = float(np.nanmean(ana.to_numpy()[ust & d.z_dogrulama.to_numpy()])
                   - np.nanmean(ana.to_numpy()[alt & d.z_dogrulama.to_numpy()])) * 100
        isaret = 0
        for v in fazla.values():
            va = v.to_numpy()
            f_ = np.nanmean(va[ust]) - np.nanmean(va[alt])
            isaret += 1 if f_ * etki > 0 else -1
        tekduze = pd.Series(ana.to_numpy()[ok]).groupby(kova.to_numpy()[ok]).mean()
        r = pd.Series(tekduze.values).rank().to_numpy()
        spear = float(np.corrcoef(r, np.arange(1, len(r) + 1))[0, 1]) if len(r) > 2 else float("nan")
        gecti = (abs(etki) >= 1.0 and not np.isnan(lo) and (lo > 0 or hi < 0)
                 and s_ * etki > 0 and z_ * etki > 0 and abs(isaret) >= 6)
        satir.append(dict(boyut=kolon, tur="Q5−Q1", n=int(alt.sum() + ust.sum()), etki=etki,
                          lo=lo, hi=hi, S=s_, Z=z_, varyant=isaret, spear=spear, gecti=gecti))

    for kolon in KATEGORIK:
        if kolon not in d.columns:
            continue
        deger = d[kolon]
        for seviye in pd.unique(deger.dropna()):
            ic = (deger == seviye).to_numpy() & ok
            if ic.sum() < 250 or (~ic & ok).sum() < 250:
                continue
            dis = (~ic) & ok
            etki, lo, hi = eslesmis_fark(sembol_ort(ic), sembol_ort(dis))
            s_ = float(np.nanmean(ana.to_numpy()[ic & (d.ds == 1).to_numpy()])
                       - np.nanmean(ana.to_numpy()[dis & (d.ds == 1).to_numpy()])) * 100
            z_ = float(np.nanmean(ana.to_numpy()[ic & d.z_dogrulama.to_numpy()])
                       - np.nanmean(ana.to_numpy()[dis & d.z_dogrulama.to_numpy()])) * 100
            isaret = 0
            for v in fazla.values():
                va = v.to_numpy()
                f_ = np.nanmean(va[ic]) - np.nanmean(va[dis])
                isaret += 1 if f_ * etki > 0 else -1
            gecti = (abs(etki) >= 1.0 and not np.isnan(lo) and (lo > 0 or hi < 0)
                     and s_ * etki > 0 and z_ * etki > 0 and abs(isaret) >= 6)
            satir.append(dict(boyut=kolon, tur=f"={seviye}", n=int(ic.sum()), etki=etki,
                              lo=lo, hi=hi, S=s_, Z=z_, varyant=isaret, spear=np.nan,
                              gecti=gecti))

    g = pd.DataFrame(satir).sort_values("etki", key=abs, ascending=False)
    out = ["# Fazla eğilimi — boyut bazında (çokluk düzeltmeli)\n",
           f"gözlem {int(ok.sum())} · boyut testi {len(g)} · geçen {int(g.gecti.sum())}\n",
           "| boyut | karşılaştırma | n | etki (puan) | %95 GA | S | Z | varyant | tekdüze ρ | geçti |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for _, s in g.iterrows():
        rho = "" if pd.isna(s.spear) else f"{s.spear:+.2f}"
        out.append(f"| {s.boyut} | {s.tur} | {s.n} | **{s.etki:+.1f}** | "
                   f"[{s.lo:+.1f}, {s.hi:+.1f}] | {s.S:+.1f} | {s.Z:+.1f} | "
                   f"{s.varyant:+d}/7 | {rho} | {'✅' if s.gecti else '—'} |")
    metin = "\n".join(out)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(metin)
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
