# -*- coding: utf-8 -*-
"""Fazla modeli — formasyonun katkısını çok değişkenli ayrıştır.

SALT OKUNUR. Girdi: `var/replay/ozellikler177.csv` + `var/replay/taban_*.csv`

Hedef (Y): eşleştirilmiş fazla = sonuç − aynı sembol×TF×ay×yön rastgele tabanı.
Böylece trend, mevsim, yön ve sembolün ortalama seviyesi Y'den düşülmüş olur;
kalan varyans "bu formasyon bu bağlamda ne kadar ekledi" sorusudur.

Model: doğrusal, katmanlı kuklalar (referans seviyeleri raporda).
  fazla ~ aile + tf + mtf_uyum + yapi_uyum + mesafe + kalite + atr_yuzdelik
        + hacim_orani + breadth + saat + gün + retest

Katsayı = o seviyenin referansa göre fazlası (puan). Güven aralıkları
**sembol kümesi bootstrap** ile (aynı sembolün onlarca kırılımı bağımsız değil).

Ayrıca her faktör için kısmi R² (tek başına açıkladığı varyans) verilir.

Kullanım:
    python scripts/fazla_model.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from puan_analiz import etiketle  # noqa: E402

VARYANTLAR = [(1.0, 1.0, 12), (1.0, 1.0, 24), (1.5, 1.0, 24), (2.0, 1.0, 24),
              (2.0, 1.5, 24), (2.0, 1.0, 48), (3.0, 1.0, 48)]


def fazla_serisi(d: pd.DataFrame, leh: float, ters: float, ufuk: int) -> pd.Series:
    yol = REPO / "var/replay" / f"taban_{leh:g}_{ters:g}_{ufuk}.csv"
    r = pd.read_csv(yol)
    t = r.groupby(["sembol", "tf", "ay", "yon"]).agg(n=("n", "sum"), b=("basari", "sum")).reset_index()
    t["taban"] = t.b / t.n
    t.loc[t.n < 30, "taban"] = np.nan
    yed = r.groupby(["sembol", "tf", "yon"]).agg(n=("n", "sum"), b=("basari", "sum"))
    yed["taban_y"] = yed.b / yed.n
    x = d[["_idx", "sembol", "tf", "ay", "yon"]].copy()
    x["y"] = etiketle(d, leh, ters, ufuk).to_numpy()
    x = x[x.y.notna()]
    x = x.merge(t[["sembol", "tf", "ay", "yon", "taban"]],
                on=["sembol", "tf", "ay", "yon"], how="left")
    x = x.merge(yed[["taban_y"]], on=["sembol", "tf", "yon"], how="left")
    x["taban"] = x.taban.fillna(x.taban_y)
    x = x[x.taban.notna()]
    return (x.y - x.taban).set_axis(x._idx).reindex(d.index)


def faktorler(d: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=d.index)
    f["aile"] = np.where(d.aile == "Kama", "Kama", "Üçgen")
    f["tf"] = d.tf.astype(str)
    f["mtf"] = d.mtf_uyum.clip(0, 4).astype("Int64").astype(str)
    f["yapi"] = d.yapi_uyum.astype("Int64").astype(str)
    f["mesafe"] = pd.cut(d.bant_mesafe_atr, [-1, 0.3, 1, 2, 1e9],
                         labels=["≤0.3", "0.3-1", "1-2", ">2"]).astype(str)
    f["kalite"] = pd.qcut(d.kalite.rank(method="first"), 3, labels=["K1", "K2", "K3"]).astype(str)
    f["atr_pct"] = pd.qcut(d.d_atr_yuzdelik.rank(method="first"), 4,
                           labels=["A1", "A2", "A3", "A4"]).astype(str)
    f["hacim"] = pd.qcut(d.hacim_orani.fillna(d.hacim_orani.median()).rank(method="first"), 4,
                          labels=["H1", "H2", "H3", "H4"]).astype(str)
    f["breadth"] = pd.cut(d.p_breadth, [-1, .45, .55, .65, 2],
                          labels=["B1", "B2", "B3", "B4"]).astype(str)
    f["saat"] = pd.cut(d.seans_saati, [-1, 11, 13, 15, 17, 20],
                       labels=["10-11", "11-13", "13-15", "15-17", "17-18"]).astype(str)
    f["gun"] = d.gun.astype("Int64").astype(str)
    f["retest"] = d.retest_var.astype("Int64").astype(str)
    f["yon"] = np.where(d.yon > 0, "L", "S")
    return f


def tasarla(f: pd.DataFrame) -> Tuple[np.ndarray, List[str], Dict[str, List[str]]]:
    ref = {"aile": "Üçgen", "tf": "1h", "mtf": "4", "yapi": "1", "mesafe": "0.3-1",
           "kalite": "K1", "atr_pct": "A1", "hacim": "H1", "breadth": "B3",
           "saat": "13-15", "gun": "1", "retest": "0", "yon": "L"}
    kolonlar = [np.ones(len(f))]
    adlar = ["sabit"]
    for k in f.columns:
        for seviye in sorted(f[k].unique()):
            if seviye == ref[k] or seviye == "nan":
                continue
            kolonlar.append((f[k] == seviye).to_numpy(float))
            adlar.append(f"{k}={seviye}")
    return np.column_stack(kolonlar), adlar, ref


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Fazla modeli")
    ap.add_argument("--girdi", default="var/replay/ozellikler177.csv")
    ap.add_argument("--rapor", default="var/replay/fazla_model.md")
    args = ap.parse_args(argv)

    d = pd.read_csv(REPO / args.girdi, low_memory=False)
    d["tarih"] = pd.to_datetime(d["tarih"], utc=True, errors="coerce").dt.tz_localize(None)
    d = d[d.tarih.notna()].reset_index(drop=True)
    d["ay"] = d.tarih.dt.to_period("M").astype(str)
    d["_idx"] = np.arange(len(d))

    y_all = {}
    for leh, ters, ufuk in VARYANTLAR:
        y_all[f"{leh:g}/{ters:g}/{ufuk}"] = fazla_serisi(d, leh, ters, ufuk)
    anahtar = "2/1/24"
    y = y_all[anahtar]
    f = faktorler(d)
    m = y.notna().to_numpy() & (f.aile != "nan").to_numpy()
    X, adlar, ref = tasarla(f[m])
    yv = y.to_numpy()[m]
    sem = d.loc[m, "sembol"].to_numpy()
    print(f"gözlem {m.sum()} · parametre {len(adlar)} · sembol {len(np.unique(sem))}")

    XtX = X.T @ X
    XtX_inv = np.linalg.pinv(XtX)
    beta = XtX_inv @ (X.T @ yv)
    r2 = 1 - ((yv - X @ beta) ** 2).sum() / ((yv - yv.mean()) ** 2).sum()

    # sembol kümesi bootstrap
    rng = np.random.default_rng(5)
    semler = np.unique(sem)
    konum = {s: np.where(sem == s)[0] for s in semler}
    bs = []
    for _ in range(400):
        sec = rng.choice(semler, len(semler), replace=True)
        idx = np.concatenate([konum[s] for s in sec])
        Xb = X[idx]
        bs.append(np.linalg.pinv(Xb.T @ Xb) @ (Xb.T @ yv[idx]))
    bs = np.array(bs)
    lo = np.percentile(bs, 2.5, axis=0)
    hi = np.percentile(bs, 97.5, axis=0)

    # faktör bazında kısmi R² (faktör gruptan çıkarılınca R² kaybı)
    gruplar: Dict[str, List[int]] = {}
    for i, ad in enumerate(adlar):
        if "=" in ad:
            gruplar.setdefault(ad.split("=")[0], []).append(i)
    kisitli = {}
    for g, idx in gruplar.items():
        kalan = [i for i in range(len(adlar)) if i not in idx]
        b2 = np.linalg.pinv(X[:, kalan].T @ X[:, kalan]) @ (X[:, kalan].T @ yv)
        r2b = 1 - ((yv - X[:, kalan] @ b2) ** 2).sum() / ((yv - yv.mean()) ** 2).sum()
        kisitli[g] = r2 - r2b

    # varyant tutarlılığı (yalnız ana katsayılar)
    tut = np.zeros(len(adlar))
    for k, seri in y_all.items():
        if k == anahtar:
            continue
        yy = seri.to_numpy()[m]
        ok = ~np.isnan(yy)
        if ok.sum() < 3000:
            continue
        b = np.linalg.pinv(X[ok].T @ X[ok]) @ (X[ok].T @ yy[ok])
        tut += np.sign(b) == np.sign(beta)
    tut = tut / (len(y_all) - 1) * 100

    out = [f"# Fazla modeli — ne kadar eklediğini ne belirliyor?\n",
           f"gözlem {int(m.sum())} · parametre {len(adlar)} · R² {r2:.3f} · "
           f"ortalama fazla {yv.mean()*100:+.1f} puan\n",
           "Katsayılar puan cinsinden (×100). Referans seviyeler: " +
           ", ".join(f"{k}={v}" for k, v in ref.items()), "",
           "| faktör | seviye | etki (puan) | %95 GA | 7 varyantta aynı işaret | kısmi R² |",
           "|---|---|---|---|---|---|"]
    siralama = sorted(range(1, len(adlar)), key=lambda i: -abs(beta[i]))
    for i in siralama:
        g = adlar[i].split("=")[0]
        seviye = adlar[i].split("=", 1)[1]
        yildiz = " ✅" if (lo[i] > 0 or hi[i] > 0) and (lo[i] > 0 or hi[i] > 0) else ""
        isaret_ok = (lo[i] > 0 and hi[i] > 0) or (lo[i] < 0 and hi[i] < 0)
        out.append(f"| {g} | {seviye} | **{beta[i]*100:+.1f}** | "
                   f"[{lo[i]*100:+.1f}, {hi[i]*100:+.1f}] | %{tut[i]:.0f} | "
                   f"{kisitli.get(g, 0)*100:.1f}% |{'' if isaret_ok else ' ⚠️'}")
    out.append("\n## Faktör önemi (kısmi R²)\n")
    out.append("| faktör | kısmi R² |")
    out.append("|---|---|")
    for g, v in sorted(kisitli.items(), key=lambda t: -t[1]):
        out.append(f"| {g} | {v*100:.1f}% |")

    metin = "\n".join(out)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(metin[:3000])
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
