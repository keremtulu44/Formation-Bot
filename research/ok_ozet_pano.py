"""Tek sayfalık özet panosu: 2026-11-08 ok sistemi değişiklikleri.

Panoda dört kare (ikisi "önce/sonra" çiftinden), ok sözlüğü, sayılar ve
tabanlı ölçümün sonucu var. Girdi görselleri:

    docs/gorseller/ok_duzeltme_2026_11_08/ikikatman_aghol_ust_uste.png
    docs/gorseller/ok_duzeltme_2026_11_08/ikikatman_garan_dikey.png
    docs/gorseller/ok_hacim_kapisi_2026_11_08/karsilastirma_aghol_geri_alim.png
    docs/gorseller/ok_cizgi_seyreltme_2026_11_08/karsilastirma_cizgi_agrot_uc_atr.png

Kullanım:
    PYTHONPATH=. .venv/bin/python research/ok_ozet_pano.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
GORSEL = ROOT / "docs/gorseller"
OUT = GORSEL / "ok_ozet_2026_11_08"

ZEMIN = "#0e1116"
METIN = "#e6edf3"
SOLUK = "#9aa7b4"
YESIL = "#2cc98d"
TURUNCU = "#f5a05a"

KARELER = (
    ("AGHOL · iki katman birlikte (destek 3 ▲ · direnç 1 ▼ 1 ▽)",
     GORSEL / "ok_duzeltme_2026_11_08/ikikatman_aghol_ust_uste.png"),
    ("GARAN · dikey destek (direnç 4 ▼ · destek 2 momentum)",
     GORSEL / "ok_duzeltme_2026_11_08/ikikatman_garan_dikey.png"),
    ("hacim şartı kalktı · AGHOL 16.01.2025 (yeni ▲)",
     GORSEL / "ok_hacim_kapisi_2026_11_08/hacim_sonra_aghol_geri_alim.png"),
    ("◇ seyreltildi · AGROT 28.03.2025 (6 ◇ → 2)",
     GORSEL / "ok_cizgi_seyreltme_2026_11_08/cizgi_sonra_agrot_uc_atr.png"),
)

HEDEF_ORAN = 1.50


def _kirp(resim):
    """Ortadan kırp: dört kare aynı en-boy oranında dursun."""
    h, w = resim.shape[:2]
    oran = w / h
    if oran > HEDEF_ORAN:
        yeni = int(h * HEDEF_ORAN)
        bas = (w - yeni) // 2
        return resim[:, bas:bas + yeni]
    yeni = int(w / HEDEF_ORAN)
    bas = max(0, (h - yeni) // 2)
    return resim[bas:bas + yeni, :]


def _satir(fig, y, etiket, deger, renk=METIN, boy=10.5):
    fig.text(0.055, y, etiket, color=SOLUK, fontsize=boy, va="center")
    fig.text(0.945, y, deger, color=renk, fontsize=boy, va="center", ha="right")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(8.27, 11.69), facecolor=ZEMIN)
    from matplotlib.lines import Line2D

    fig.text(0.055, 0.968, "OK SİSTEMİ · 2026-11-08", color=METIN, fontsize=20, va="center")
    fig.text(0.055, 0.941, "iki katman birlikte · renk katmanı söylüyor · ok sözlüğü eşitlenmiş",
             color=SOLUK, fontsize=10.5, va="center")

    # --- dört kare (2x2), başlık ALTTA -----------------------------------
    gen = 0.40
    yuk = gen * (8.27 / HEDEF_ORAN) / 11.69
    for i, (baslik, yol) in enumerate(KARELER):
        sat, sut = divmod(i, 2)
        x0 = 0.055 + sut * 0.475
        y0 = 0.725 - sat * 0.220
        eksen = fig.add_axes([x0, y0, gen, yuk])
        if yol.exists():
            eksen.imshow(_kirp(mpimg.imread(yol)))
        eksen.axis("off")
        fig.text(x0, y0 - 0.009, baslik, color=SOLUK, fontsize=8.6, va="top")

    def ayrac(y):
        fig.add_artist(Line2D([0.055, 0.945], [y, y], color="#243040", linewidth=0.8))

    # --- ok sözlüğü ------------------------------------------------------
    ayrac(0.470)
    fig.text(0.055, 0.452, "OK SÖZLÜĞÜ", color=METIN, fontsize=12.5, va="center")
    satirlar = (
        ("▲ / ▼ dolu", "olay: destek geri alımı / direnç dönüşü", YESIL),
        ("▲ / ▼ içi boş", "momentum: güçlü mum — seviye iddiası yok", YESIL),
        ("◇ içi boş", "yapı uyarısı: çizgi basamak yaptı / dikey destek", TURUNCU),
        ("renk", "yeşil = destek katmanı · turuncu = direnç katmanı", METIN),
    )
    for k, (a, b, renk) in enumerate(satirlar):
        yy = 0.429 - 0.0215 * k
        fig.text(0.062, yy, a, color=renk, fontsize=10, va="center")
        fig.text(0.235, yy, b, color=METIN, fontsize=10, va="center")

    # --- sayılar ---------------------------------------------------------
    ayrac(0.335)
    fig.text(0.055, 0.317, "SAYILAR · günlük 50 sembol, 24.549 bar", color=METIN,
             fontsize=12.5, va="center")
    for k, (a, b, renk) in enumerate((
        ("dolu ▲ (hacim şartı kalktı)", "180 → 195", YESIL),
        ("momentum ▲ (değişmedi)", "51 → 51", SOLUK),
        ("◇ yapı uyarısı (zayıf uyarıya 20 bar soğuma)", "737 → 486", YESIL),
        ("toplam işaret", "983 → 732", YESIL),
    )):
        _satir(fig, 0.294 - 0.0215 * k, a, b, renk)

    # --- ölçüm -----------------------------------------------------------
    ayrac(0.212)
    fig.text(0.055, 0.194, "ÖLÇÜM · 176 sembol, tabanlı (kontrol'lü) replay", color=METIN,
             fontsize=12.5, va="center")
    for k, (a, b, renk) in enumerate((
        ("▼ direnç — R1 ±1 ATR (desteğe karşı)", "+7,8 / +9,5  ✓", YESIL),
        ("▼ direnç — R2 2:1 koşu (tüm barlara karşı)", "+8,4 / +10,5  ✓", YESIL),
        ("▼ direnç — R3 10 bar sonra seviye", "+11,9 / +12,3  ✓", YESIL),
        ("▲ destek — R3 10 bar sonra seviye", "+14,0 / +8,8  ✓", YESIL),
        ("▲ destek — R1 ±1 ATR yön yarışı", "+4,5 / +6,5  eşik altı", TURUNCU),
    )):
        _satir(fig, 0.170 - 0.0205 * k, a, b, renk, boy=10)

    fig.text(0.055, 0.058,
             "✓ = keşif ve doğrulamada aynı yönde ve Bonferroni'yi geçti · değerler puan (lift)",
             color=SOLUK, fontsize=8.8, va="center")
    fig.text(0.055, 0.041,
             "doküman: docs/arastirma/OK_SISTEMI_2026-11-08.md §7–§13 · "
             "replay: research/stabil_*_replay.py",
             color=SOLUK, fontsize=8.2, va="center")

    hedef = OUT / "00_pano.png"
    fig.savefig(hedef, dpi=150, facecolor=ZEMIN)
    plt.close(fig)
    print("yazıldı", hedef)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
