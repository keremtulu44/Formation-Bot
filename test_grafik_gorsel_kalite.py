# -*- coding: utf-8 -*-
"""Görsel kalite kapıları (görsel-2): ölçülebilir kurallar, piksel hash'i yok.

Kurallar:
  1. Yazı mumun üstüne binmez: gerçek önbellekteki örnek karelerde
     `meta["kalite"]["mum_cakisan"] == 0` (ölçüm: `_mum_cakisma_say`).
  2. Sağ fiyat şeridindeki etiketler dikeyde üst üste binmez ve hiçbiri atılmaz.
  3. Bant teması işareti, temasın gerçekten olduğu bandın tarafındaki fitil
     ucunda çizilir (üst banda yakın mum → tepe, alt banda yakın mum → dip).

Testler `bot_data/` önbelleğini yalnız OKUR.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import grafik
import grafik_uret

IST = timezone(timedelta(hours=3))

# Ölçüm örnekleri: (hisse, tf, mum). Hepsi bot_data'da gerçek veri.
ORNEKLER = [
    ("AKBNK", "1h", 180),
    ("AKBNK", "4h", 120),
    ("THYAO", "1h", 180),
    ("BIMAS", "4h", 120),
    ("ALARK", "4h", 120),
    ("DOHOL", "1h", 180),
]


@pytest.mark.parametrize("hisse,tf,mum", ORNEKLER)
def test_gercek_karelerde_yazi_mumun_ustune_binmez(tmp_path, hisse, tf, mum):
    sonuc = grafik_uret.kare_uret(hisse, tf, veri_dizin="bot_data", zone=True,
                                  mum=mum, formasyon_tara=True,
                                  cikti=str(tmp_path / f"{hisse}_{tf}.png"))
    assert sonuc.get("hata") is None and sonuc.get("yol")
    kalite = sonuc["meta"].get("kalite")
    assert kalite is not None, "çakışma ölçümü üretilmedi"
    assert kalite["yazi"] > 0
    assert kalite["mum_cakisan"] == 0, kalite["cakisan"]


def test_sag_serit_etiketleri_dikeyde_ust_uste_binmez(tmp_path):
    """Aynı seviyedeki dört etiket ayrışır; hiçbiri atılmaz (şerit yeterliyse)."""
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10.8, 8.1), dpi=100)
    ax = fig.add_axes([0.075, 0.1, 0.8, 0.8])
    aralik = (50.0, 60.0)
    ax.set_ylim(*aralik)
    ax.set_xlim(-0.6, 179.6)
    adaylar = [
        {"kaynak": "zone", "x": 179.6, "y": 55.0, "metin": f"OB↑ %{k}",
         "renk": "#2bb673", "sabit": False, "oncelik": 2, "bg": None}
        for k in (10, 20, 30, 40)
    ]
    adaylar.append({"kaynak": "son", "x": 179.6, "y": 55.0, "metin": "55,00",
                    "renk": "#101418", "bg": "#e3e6e8", "sabit": True, "oncelik": 9})
    ozet = grafik._sag_ciz(ax, fig, adaylar, 180, aralik)
    assert ozet["atlanan"] == 0 and ozet["yerlesen"] == 5
    yy = sorted(a["yy"] for a in adaylar)
    # etiket yüksekliği: 8 pt @100 dpi, 1,45 satır; eksen yüksekliği 0,8 × 810 px
    h = 8.0 * 100 / 72.0 * 1.45 / ((0.8 * 810) / 10.0)
    for a, b in zip(yy, yy[1:]):
        assert b - a >= h * 0.999, (a, b, h)
    # sabit son fiyat yerinde kalır
    son = next(a for a in adaylar if a.get("sabit"))
    assert son["yy"] == pytest.approx(55.0)


def test_bant_temasi_dogru_fitil_ucunda(tmp_path):
    """Alt banda yakın temas → dip (low); üst banda yakın temas → tepe (high)."""
    from matplotlib.figure import Figure

    n = 10
    yuksek = [101.0] * n
    dusuk = [99.0] * n
    # 3. mum: alt banda (100) yakın → dip 99.5 seçilmeli (tepe 101 değil)
    yuksek[3], dusuk[3] = 101.0, 99.5
    # 6. mum: üst banda (110) yakın → tepe 111 seçilmeli
    yuksek[6], dusuk[6] = 111.0, 109.0
    goruntu = {
        "formasyon": {"upper_now": 110.0, "lower_now": 100.0, "start_bar": 0},
        "yuksek": yuksek, "dusuk": dusuk,
        "temas": [3, 6], "temas_isaret": [3, 6],
        "isaretler": [], "sol": 0,
    }
    fig = Figure(figsize=(10.8, 8.1), dpi=100)
    ax = fig.add_axes([0.075, 0.1, 0.8, 0.8])
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_ylim(90.0, 120.0)
    grafik._formasyon_ciz(ax, goruntu, n, 300.0, {})
    # temas daireleri: marker='o' ve fillstyle='none' olan çizgiler
    daireler = [ln for ln in ax.lines if ln.get_marker() == "o"
                and ln.get_fillstyle() == "none"]
    veri = {int(ln.get_xdata()[0]): float(ln.get_ydata()[0]) for ln in daireler}
    assert veri[3] == pytest.approx(99.5)
    assert veri[6] == pytest.approx(111.0)
