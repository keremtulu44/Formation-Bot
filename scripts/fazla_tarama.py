# -*- coding: utf-8 -*-
"""Fazla taraması — formasyona ait katkıyı tüm boyutlarda ara.

SALT OKUNUR. Girdi: `var/replay/ozellikler177.csv` + `var/replay/rastgele_aylik.csv`

Yöntem
------
1. Her gözlem için "fazla" = sonuç − (aynı sembol + TF + ay + yön hücresindeki
   rastgele giriş tabanı). Trend, mevsim ve yön sürüklenmesi böylece çıkar.
2. Ölçüm birimi **sembol**: her sembolün ortalama fazlası alınır, bootstrap
   semboller üzerinden yeniden örneklenir. (Gözlem bazlı bootstrap aynı
   sembolün 40 kırılımını bağımsız sayıp GA'yı yapay daraltıyordu.)
3. Bir hücre ancak şu dördü birlikte sağlanırsa "geçti" sayılır:
   a) sembol bootstrap %95 GA sıfırı dışlıyor,
   b) S ve Z bölmelerinde aynı işaret,
   c) 7 etiket varyantının ≥6'sında aynı işaret,
   d) |fazla| ≥ 1,0 puan.
4. Çoklu karşılaştırma: kaç hücre tarandığı ve beklenen yanlış pozitif sayısı
   raporda açıkça yazılır.

Kullanım:
    python scripts/fazla_tarama.py
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

from puan_analiz import etiketle  # noqa: E402

VARYANTLAR: List[Tuple[float, float, int]] = [
    (1.0, 1.0, 12), (1.0, 1.0, 24), (1.5, 1.0, 24), (2.0, 1.0, 24),
    (2.0, 1.5, 24), (2.0, 1.0, 48), (3.0, 1.0, 48),
]

# (kolon, tür, etiketler) — tür: "kategori" | "kova"
BOYUTLAR: List[Tuple[str, str, Optional[List[str]]]] = [
    ("desen", "kategori", None),
    ("aile", "kategori", None),
    ("tf", "kategori", None),
    ("yon", "kategori", None),
    ("gun", "kategori", None),
    ("kalite", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("bant_mesafe_atr", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("bant_genislik_atr", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("sure_orani", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("daralma", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("temas_puan", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("olgunluk", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("hacim_orani", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("hacim_formasyon", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("h_hacim_saat", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("h_hacim_kuruma", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("h_atr_yuzdelik", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("h_atr_sikisma", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("d_atr_yuzdelik", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("d_sikisma", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("d_yapi_net", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("d_engel_atr", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("d_zirve_mesafe", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("d_ust_ma50", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("d_ust_ma200", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("h_ust_ma20", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("h_govde_konum", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("h_aralik_atr", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("mtf_uyum", "kategori", None),
    ("yapi_uyum", "kategori", None),
    ("zirve_uyum", "kategori", None),
    ("endeks_uyum", "kategori", None),
    ("p_breadth", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("p_dispersion", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("beta60", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("kore60", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("goreli_guc", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("akran_mom5", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("endeks_egim", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("e_x_gun_ici", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("seans_saati", "kategori", None),
    ("gecikme_bar", "kategori", None),
    ("bar_sayisi", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("likidite_tl", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("tf_bos20", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("tf_sikisma", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("h_ret20", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
    ("e_x_ret20", "kova", ["Q1", "Q2", "Q3", "Q4", "Q5"]),
]


def hucrele(d: pd.DataFrame, kolon: str, tur: str, etiketler: Optional[List[str]]):
    if tur == "kategori":
        return d[kolon].astype("Int64").astype(str) if kolon in ("mtf_uyum", "yapi_uyum",
                                                                 "zirve_uyum", "endeks_uyum",
                                                                 "gecikme_bar") else d[kolon].astype(str)
    try:
        return pd.qcut(d[kolon], 5, labels=etiketler, duplicates="drop")
    except (ValueError, TypeError):
        return pd.Series([None] * len(d), index=d.index)


def bootstrap(seri: pd.Series, tekrar: int = 1500, rng=None) -> Tuple[float, float]:
    """Sembol düzeyinde ortalama için %95 GA."""
    v = seri.dropna().to_numpy()
    if len(v) < 20:
        return float("nan"), float("nan")
    rng = rng or np.random.default_rng(7)
    idx = rng.integers(0, len(v), (tekrar, len(v)))
    ort = v[idx].mean(axis=1) * 100
    return float(np.percentile(ort, 2.5)), float(np.percentile(ort, 97.5))


def fark_ga(ic: pd.Series, dis: pd.Series, tekrar: int = 1500, rng=None) -> Tuple[float, float, float]:
    """Hücre − dışarısı farkı, sembol düzeyinde eşleşmiş bootstrap.

    Aynı sembol hem içeride hem dışarıda varsa çift olarak kullanılır; bu,
    sembolün genel eğilimini farktan çıkarır.
    """
    rng = rng or np.random.default_rng(7)
    a = ic.dropna()
    b = dis.dropna()
    ortak = a.index.intersection(b.index)
    if len(ortak) >= 15:
        A = a.loc[ortak].to_numpy()
        B = b.loc[ortak].to_numpy()
        idx = rng.integers(0, len(ortak), (tekrar, len(ortak)))
        fark = ((A[idx] - B[idx]).mean(axis=1)) * 100
        nokta = float((A.mean() - B.mean()) * 100)
    else:
        if len(a) < 10 or len(b) < 10:
            return float("nan"), float("nan"), float("nan")
        idx_a = rng.integers(0, len(a), (tekrar, len(a)))
        idx_b = rng.integers(0, len(b), (tekrar, len(b)))
        fark = (a.to_numpy()[idx_a].mean(axis=1) - b.to_numpy()[idx_b].mean(axis=1)) * 100
        nokta = float(a.mean() * 100 - b.mean() * 100)
    return nokta, float(np.percentile(fark, 2.5)), float(np.percentile(fark, 97.5))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Fazla taraması")
    ap.add_argument("--girdi", default="var/replay/ozellikler177.csv")
    ap.add_argument("--taban", default="var/replay/rastgele_aylik.csv")
    ap.add_argument("--rapor", default="var/replay/fazla_tarama.md")
    args = ap.parse_args(argv)

    d = pd.read_csv(REPO / args.girdi, low_memory=False)
    d["tarih"] = pd.to_datetime(d["tarih"], utc=True, errors="coerce").dt.tz_localize(None)
    d = d[d.tarih.notna()].copy()
    d["ay"] = d.tarih.dt.to_period("M").astype(str)
    d["_idx"] = np.arange(len(d))
    d["ds"] = d.sembol.apply(lambda s: zlib.crc32(s.encode()) % 2)
    kes = d.tarih.quantile(0.70)
    d["z_dogrulama"] = d.tarih > kes

    def taban_oku(leh, ters, ufuk):
        yol = REPO / "var/replay" / f"taban_{leh:g}_{ters:g}_{ufuk}.csv"
        if not yol.exists():
            return None
        r = pd.read_csv(yol)
        anahtar = ["sembol", "tf", "ay", "yon"]
        t = r.groupby(anahtar).agg(n=("n", "sum"), b=("basari", "sum")).reset_index()
        t["taban"] = t.b / t.n
        t.loc[t.n < 30, "taban"] = np.nan
        yed = r.groupby(["sembol", "tf", "yon"]).agg(n=("n", "sum"), b=("basari", "sum"))
        yed["taban_y"] = yed.b / yed.n
        return t, yed

    # --- 7 varyant için fazla serisi (her varyant kendi tabanıyla)
    fazlalar: Dict[str, pd.Series] = {}
    for leh, ters, ufuk in VARYANTLAR:
        okunan = taban_oku(leh, ters, ufuk)
        if okunan is None:
            print(f"UYARI: taban yok {leh}/{ters}/{ufuk}")
            continue
        t, yed = okunan
        x = d[["_idx", "sembol", "tf", "ay", "yon"]].copy()
        x["y"] = etiketle(d, leh, ters, ufuk).to_numpy()
        x = x[x.y.notna()]
        x = x.merge(t[["sembol", "tf", "ay", "yon", "taban"]],
                    on=["sembol", "tf", "ay", "yon"], how="left")
        x = x.merge(yed[["taban_y"]], on=["sembol", "tf", "yon"], how="left")
        x["taban"] = x.taban.fillna(x.taban_y)
        x = x[x.taban.notna()]
        fazlalar[f"{leh:g}/{ters:g}/{ufuk}"] = (x.y - x.taban).set_axis(x._idx).reindex(d.index)
    anahtar_varyant = "2/1/24"

    ana = fazlalar[anahtar_varyant].to_numpy()
    gecerli = ~np.isnan(ana)
    out: List[str] = []
    out.append("# Fazla taraması — formasyona ait katkı\n")
    out.append(f"gözlem {int(gecerli.sum())} · {len(BOYUTLAR)} boyut · ana etiket {anahtar_varyant} · "
               f"ortalama fazla {np.nanmean(ana)*100:+.1f} puan")
    out.append(f"\nGeçme koşulu: |fark| ≥ 1,0 · sembol GA sıfır dışı · S ve Z aynı işaret · "
               f"≥6/7 varyant aynı işaret.\n")

    satirlar: List[dict] = []
    taranan = 0
    for kolon, tur, etiketler in BOYUTLAR:
        if kolon not in d.columns:
            continue
        k = hucrele(d, kolon, tur, etiketler)
        for deger, idx in k.groupby(k, observed=True).groups.items():
            idx = pd.Index(idx)
            m = np.zeros(len(d), dtype=bool)
            m[d.index.get_indexer(idx)] = True
            if (m & gecerli).sum() < 150:
                continue
            taranan += 1
            ic = m & gecerli
            dis = (~m) & gecerli
            fazla = float(np.nanmean(ana[ic]) * 100)
            fark, lo, hi = fark_ga(
                pd.Series(ana[ic], index=d.index[ic]).groupby(d.loc[ic, "sembol"]).mean(),
                pd.Series(ana[dis], index=d.index[dis]).groupby(d.loc[dis, "sembol"]).mean())
            s_ = float(np.nanmean(ana[ic & (d.ds == 1).to_numpy()]) * 100
                       - np.nanmean(ana[dis & (d.ds == 1).to_numpy()]) * 100)
            z_ = float(np.nanmean(ana[ic & d.z_dogrulama.to_numpy()]) * 100
                       - np.nanmean(ana[dis & d.z_dogrulama.to_numpy()]) * 100)
            isaret = 0
            guclu = 0
            for v in fazlalar.values():
                vv = v.to_numpy()
                x1 = vv[ic]
                x0 = vv[dis]
                if np.isnan(x1).all() or np.isnan(x0).all():
                    continue
                f_ = float(np.nanmean(x1) * 100 - np.nanmean(x0) * 100)
                isaret += 1 if f_ * fark > 0 else -1
                guclu += 1 if (f_ * fark > 0 and abs(f_) >= 0.5) else 0
            tutarli = abs(isaret) >= 6 and guclu >= 5
            gecti = (abs(fark) >= 1.0 and not np.isnan(lo) and
                     ((lo > 0) or (hi < 0)) and s_ * fark > 0 and z_ * fark > 0 and tutarli)
            satirlar.append(dict(boyut=kolon, hucre=str(deger), n=int(ic.sum()),
                                 fazla=fazla, fark=fark, lo=lo, hi=hi, S=s_, Z=z_,
                                 varyant=isaret, guclu=guclu, gecti=gecti))

    g = pd.DataFrame(satirlar).sort_values("fark", ascending=False)
    out.append(f"\n## Taranan hücre: {taranan} · geçen: {int(g.gecti.sum())} · "
               f"şansla beklenen yanlış pozitif ≈ {taranan * 0.03:.0f}\n")
    out.append("`fark` = hücre − diğer tüm formasyonlar (eşleşmiş, sembol düzeyi). "
               "`fazla` = hücrenin rastgele tabana göre fazlası (bağlam).\n")
    out.append("| boyut | hücre | n | fazla | fark | %95 GA | S | Z | varyant | geçti |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for _, s in g.iterrows():
        out.append(f"| {s.boyut} | {s.hucre} | {s.n} | {s.fazla:+.1f} | **{s.fark:+.1f}** | "
                   f"[{s.lo:+.1f}, {s.hi:+.1f}] | {s.S:+.1f} | {s.Z:+.1f} | "
                   f"{s.varyant:+d}/7 | {'✅' if s.gecti else '—'} |")

    metin = "\n".join(out)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(metin)
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
