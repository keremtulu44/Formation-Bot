# -*- coding: utf-8 -*-
"""Özellik avı: bağlam özellikleri kırılımın devamını ayırıyor mu?

SALT OKUNUR. Girdi: `var/replay/ozellikler177.csv` (ozellik_deposu çıktısı).

Protokol (ön kayıt ruhuyla):
  * Keşif = ayrık sembol bölmesinin yarısı (S-keşif).
  * Doğrulama = S-doğrulama **ve** Z-doğrulama (uzak dönem, 35 gün boşluklu).
  * Bir özellik "aday" olmak için: keşifte |AUC-0,5| ≥ 0,02, |z| ≥ 3,0
    (35 test için Bonferroni ~ %0,001) ve iki doğrulamada da AYNI işaret.
  * Ürün ölçüsü: keşifte yön öğrenilir, doğrulamada en iyi %30 dilim seçilir,
    devam oranı taban ile kıyaslanır (lift).
  * Hayatta kalanlar 7 etiket varyantında yeniden sınanır (≥ 6/7 şart).

Kullanım:
    python scripts/ozellik_avi.py
    python scripts/ozellik_avi.py --kapsam 0.3 --rapor var/replay/avi.md
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
from puan_tarama import bolmeler  # noqa: E402

VARYANTLAR = [(1.0, 1.0, 12), (1.0, 1.0, 24), (1.5, 1.0, 24), (2.0, 1.0, 24),
              (2.0, 1.5, 24), (2.0, 1.0, 48), (3.0, 1.0, 48)]
ANA = (2.0, 1.0, 24)

# Aday özellikler (domain başlıklarıyla)
ADAYLAR: List[Tuple[str, str, str]] = [
    # (kolon, domain, etiket)
    ("kalite", "puan", "kalite (mevcut puan)"),
    ("mtf_uyum", "trend", "çoklu TF uyumu (0-4)"),
    ("yapi_uyum", "trend", "market structure yönü (HH/HL)"),
    ("d_yapi", "trend", "structure skoru (-2..+2)"),
    ("d_ust_ma50", "trend", "1g fiyat / MA50"),
    ("d_ust_ma200", "trend", "1g fiyat / MA200"),
    ("h_ust_ma20", "trend", "1s fiyat / MA20"),
    ("h_ust_ma50", "trend", "1s fiyat / MA50"),
    ("d_donchian20", "trend", "1g 20-bar zirve kırılımı"),
    ("d_donchian55", "trend", "1g 55-bar zirve kırılımı"),
    ("h_donchian20", "trend", "1s 20-bar zirve kırılımı"),
    ("h_donchian55", "trend", "1s 55-bar zirve kırılımı"),
    ("d_engel_atr", "konum", "üstteki direnç mesafesi (ATR)"),
    ("tf_bos20", "trend", "aynı TF 20-bar yapı kırılımı (BOS)"),
    ("tf_sikisma", "volatilite", "aynı TF ATR sıkışması (10/60)"),
    ("d_sikisma", "volatilite", "1g ATR sıkışması (10/60)"),
    ("h_atr_sikisma", "volatilite", "1s ATR sıkışması (10/60)"),
    ("h_hacim_saat", "hacim", "saat-düzeltilmiş hacim"),
    ("e_x_gun_ici", "piyasa", "endeks gün içi momentum"),
    ("akran_mom5", "kesitsel", "akran momentumu (5g)"),
    ("d_yapi_net", "trend", "structure netliği (-1..+1)"),
    ("d_yapi_net", "trend", "structure netliği (-1..+1)"),
    ("hacim_formasyon", "hacim", "formasyon içi hacim / öncesi"),
    ("d_zirve_mesafe", "konum", "52h zirveye uzaklık (ATR)"),
    ("d_dip_mesafe", "konum", "52h dipten uzaklık (ATR)"),
    ("zirve_uyum", "konum", "zirveye 3 ATR'den yakın"),
    ("h_kosu_atr", "momentum", "kırılım öncesi koşu (ATR)"),
    ("d_ret20", "momentum", "1g 20-bar getiri"),
    ("d_ret60", "momentum", "1g 60-bar getiri"),
    ("h_ret20", "momentum", "1s 20-bar getiri"),
    ("h_ret60", "momentum", "1s 60-bar getiri"),
    ("hacim_orani", "hacim", "kırılım hacmi / 20 ort."),
    ("h_hacim_20", "hacim", "son bar hacim / 20 ort."),
    ("h_hacim_trend", "hacim", "hacim trendi (10/40)"),
    ("h_hacim_kuruma", "hacim", "hacim kuruması (20/60)"),
    ("d_atr_yuzdelik", "volatilite", "1g ATR yüzdelik dilimi"),
    ("h_atr_yuzdelik", "volatilite", "1s ATR yüzdelik dilimi"),
    ("h_aralik_atr", "mikroyapı", "bar aralığı (ATR)"),
    ("h_govde_konum", "mikroyapı", "kapanışın bar içi konumu"),
    ("h_gap_atr", "mikroyapı", "gap (ATR)"),
    ("seans_saati", "mikroyapı", "seans saati"),
    ("p_breadth", "piyasa", "piyasa genişliği (MA20 üstü %)"),
    ("p_dispersion", "piyasa", "enine dağılım"),
    ("e_x_ust_ma50", "piyasa", "endeks / MA50"),
    ("e_x_ust_ma200", "piyasa", "endeks / MA200"),
    ("e_x_ret20", "piyasa", "endeks 20-bar getiri"),
    ("e_x_atr_yuzdelik", "piyasa", "endeks ATR yüzdelik"),
    ("endeks_uyum", "piyasa", "endeks uyumu (yön)"),
    ("beta60", "kesitsel", "endekse beta (60g)"),
    ("kore60", "kesitsel", "endeks korelasyonu (60g)"),
    ("goreli_guc", "kesitsel", "göreli güç (hisse-endeks)"),
    ("bant_mesafe_atr", "formasyon", "seviyeye mesafe (ATR)"),
    ("bant_genislik_atr", "formasyon", "bant genişliği (ATR)"),
    ("gecikme_bar", "formasyon", "kırılım gecikmesi (bar)"),
    ("retest_var", "olay", "retest görüldü"),
    ("dogum_mesafe_atr", "formasyon", "doğumda bant mesafesi"),
    ("daralma", "formasyon", "daralma oranı"),
    ("olgunluk", "formasyon", "olgunluk"),
    ("temas_puan", "formasyon", "temas puanı"),
    ("guc", "formasyon", "kırılım gücü"),
]


def auc(y: pd.Series, x: pd.Series) -> float:
    m = y.notna() & x.notna()
    yy, xx = y[m].to_numpy(float), x[m].to_numpy(float)
    if len(yy) < 100 or yy.min() == yy.max():
        return float("nan")
    r = pd.Series(xx).rank().to_numpy()
    n1 = yy.sum()
    n0 = len(yy) - n1
    return float((r[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def auc_z(y: pd.Series, x: pd.Series) -> float:
    """Hanley-McNeil yaklaşık standart hata ile z."""
    m = y.notna() & x.notna()
    n1 = float((y[m] == 1).sum())
    n0 = float((y[m] == 0).sum())
    a = auc(y, x)
    if not np.isfinite(a) or n1 < 20 or n0 < 20:
        return float("nan")
    se = np.sqrt((n1 + n0 + 1) / (12 * n1 * n0))
    return float((a - 0.5) / se)


def lift(s: pd.DataFrame, kolon: str, yon: int, kapsam: float) -> Tuple[float, float, int]:
    """Keşifte öğrenilen yönde en iyi `kapsam` dilimini seçip devam oranını döndürür."""
    g = s[["y", kolon]].dropna()
    if len(g) < 100:
        return float("nan"), float("nan"), 0
    kes = g[kolon].quantile(1 - kapsam) if yon > 0 else g[kolon].quantile(kapsam)
    sec = g[g[kolon] >= kes] if yon > 0 else g[g[kolon] <= kes]
    if len(sec) < 30:
        return float("nan"), float("nan"), 0
    return float(sec.y.mean()), float(g.y.mean()), len(sec)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Özellik avı")
    ap.add_argument("--girdi", default="var/replay/ozellikler177.csv")
    ap.add_argument("--kapsam", type=float, default=0.30)
    ap.add_argument("--z-esik", type=float, default=3.0)
    ap.add_argument("--auc-esik", type=float, default=0.02)
    ap.add_argument("--rapor", default="var/replay/avi.md")
    args = ap.parse_args(argv)

    d = pd.read_csv(REPO / args.girdi, low_memory=False)
    d["y"] = etiketle(d, *ANA)
    d = d[d.y.notna()].copy()
    d["tarih"] = pd.to_datetime(d["zaman"], utc=True, errors="coerce")
    d = d[d.tarih.notna()].copy()

    b = bolmeler(d)
    S_tr, S_te = b["S"]
    Z_tr, Z_te = b["Z"]
    out = ["# Özellik avı\n",
           f"gözlem {len(d)} · taban %{d.y.mean()*100:.1f} · kapsam %{args.kapsam*100:.0f}\n",
           f"S keşif {len(S_tr)} / doğrulama {len(S_te)} · "
           f"Z keşif {len(Z_tr)} / doğrulama {len(Z_te)}\n",
           "| domain | özellik | AUC (S keşif) | z | S doğr. lift | Z doğr. lift | işaret |",
           "|---|---|---|---|---|---|---|"]
    adaylar = []
    for kolon, domain, etiket in ADAYLAR:
        if kolon not in d:
            continue
        a = auc(S_tr.y, S_tr[kolon])
        z = auc_z(S_tr.y, S_tr[kolon])
        if not np.isfinite(a) or not np.isfinite(z):
            continue
        yon = 1 if a > 0.5 else -1
        l_s, taban_s, n_s = lift(S_te, kolon, yon, args.kapsam)
        l_z, taban_z, n_z = lift(Z_te, kolon, yon, args.kapsam)
        if not (np.isfinite(l_s) and np.isfinite(l_z)):
            continue
        fark_s = (l_s - taban_s) * 100
        fark_z = (l_z - taban_z) * 100
        isaret = "tutar" if (fark_s > 0 and fark_z > 0) else "tutmaz"
        gecti = (abs(a - 0.5) >= args.auc_esik and abs(z) >= args.z_esik
                 and fark_s > 0 and fark_z > 0)
        out.append(f"| {domain} | {etiket} | {a:.3f} | {z:+.2f} | "
                   f"{fark_s:+.1f} puan (n={n_s}) | {fark_z:+.1f} puan (n={n_z}) | "
                   f"{'**GEÇTİ**' if gecti else isaret} |")
        adaylar.append({"kolon": kolon, "domain": domain, "etiket": etiket, "auc": a,
                        "z": z, "yon": yon, "lift_s": fark_s, "lift_z": fark_z,
                        "gecti": gecti})

    ad = pd.DataFrame(adaylar).sort_values("z", key=lambda s: s.abs(), ascending=False)

    # --- hayatta kalanlar: 7 etiket varyantı
    kalan = ad[ad.gecti] if len(ad) else pd.DataFrame()
    out.append("\n## Hayatta kalanlar (çoklu test + iki doğrulama)\n")
    if len(kalan) == 0:
        out.append("Hiçbir özellik keşif eşiklerini geçmedi.")
    else:
        out.append("| özellik | AUC | yön | S lift | Z lift | 7 varyantta tutarlılık |")
        out.append("|---|---|---|---|---|---|")
        for r in kalan.itertuples():
            tutan = 0
            for leh, ters, ufuk in VARYANTLAR:
                dd = d.copy()
                dd["y"] = etiketle(dd, leh, ters, ufuk)
                dd = dd[dd.y.notna()]
                bb = bolmeler(dd)
                l1, _, _ = lift(bb["S"][1], r.kolon, r.yon, args.kapsam)
                l2, _, _ = lift(bb["Z"][1], r.kolon, r.yon, args.kapsam)
                t1, _, _ = lift(bb["S"][1], r.kolon, r.yon, 1.0)
                t2, _, _ = lift(bb["Z"][1], r.kolon, r.yon, 1.0)
                if (l1 - t1) > 0 and (l2 - t2) > 0:
                    tutan += 1
            out.append(f"| {r.etiket} | {r.auc:.3f} | "
                       f"{'yüksek=iyi' if r.yon > 0 else 'düşük=iyi'} | "
                       f"{r.lift_s:+.1f} | {r.lift_z:+.1f} | {tutan}/7 |")

    # --- en iyiler tablosu (eşiği geçmese de)
    out.append("\n## Keşifte en güçlü 12 (z'ye göre)\n")
    out.append("| domain | özellik | AUC | z | S lift | Z lift |")
    out.append("|---|---|---|---|---|---|")
    for r in ad.head(12).itertuples():
        out.append(f"| {r.domain} | {r.etiket} | {r.auc:.3f} | {r.z:+.2f} | "
                   f"{r.lift_s:+.1f} | {r.lift_z:+.1f} |")

    metin = "\n".join(out)
    print(metin)
    p = REPO / args.rapor
    p.write_text(metin, encoding="utf-8")
    print(f"\nRapor: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
