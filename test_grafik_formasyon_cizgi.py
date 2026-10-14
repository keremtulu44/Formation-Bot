# -*- coding: utf-8 -*-
"""Formasyon bant çizgisi: eğim gerçek (motorun doğrusu), yatay değil.

Önceki sürüm sınırları her zaman yatay çizerdi; yükselen üçgenin alt sınırı
yükselirken bu yanıltıcıydı. Şimdi `grafik._formasyon_ciz`, motorun iki çapa
noktasından geçen doğrusunu (`patterns.mathutil.f_line_price`) bar bar değerlendirir.

Ölçülebilir sözler:
  1. Çizginin SON barındaki değeri `upper_now/lower_now` ile aynıdır (sayısal).
  2. Alt sınır yükselen bir çapada gerçekten yükselir (monoton artar).
  3. Çapa yoksa (ör. `--formasyon` JSON) eski yatay yedek kullanılır.
"""

from __future__ import annotations

import pytest
from matplotlib.figure import Figure

import grafik
from patterns.mathutil import f_line_price

N = 25                      # son bar indeksi 24
SOL = 0
UST_CAPA = (5, 10.0, 15, 12.0)   # üst: düz-yukarı eğim 0,2/bar
ALT_CAPA = (5, 8.0, 15, 9.0)     # alt: yükselen 0,1/bar
SON = N - 1


def _goruntu(capali: bool):
    f = {"start_bar": 5, "upper_now": f_line_price(*UST_CAPA, SON),
         "lower_now": f_line_price(*ALT_CAPA, SON)}
    if capali:
        f.update({"hb1": UST_CAPA[0], "hp1": UST_CAPA[1], "hb2": UST_CAPA[2],
                  "hp2": UST_CAPA[3], "lb1": ALT_CAPA[0], "lp1": ALT_CAPA[1],
                  "lb2": ALT_CAPA[2], "lp2": ALT_CAPA[3]})
    return {"formasyon": f, "sol": SOL, "isaretler": [], "temas": [],
            "temas_isaret": [], "yuksek": [], "dusuk": []}


def _bant_cizgileri(ax):
    kalin = grafik.SABITLER["cizgi_kalinlik"]["formasyon"]
    return [ln for ln in ax.lines
            if abs(ln.get_linewidth() - kalin) < 1e-9
            and ln.get_linestyle() in ("-", "solid")]


def _eksen():
    fig = Figure(figsize=(10.8, 8.1), dpi=100)
    ax = fig.add_axes([0.075, 0.1, 0.8, 0.8])
    ax.set_xlim(-0.6, N - 0.4)
    ax.set_ylim(0, 20)
    return ax


def test_son_bar_degerleri_motorun_now_degerine_esit():
    ax = _eksen()
    grafik._formasyon_ciz(ax, _goruntu(True), N, 300.0, {})
    cizgiler = _bant_cizgileri(ax)
    assert len(cizgiler) == 2
    sonlar = sorted(float(ln.get_ydata()[-1]) for ln in cizgiler)
    beklenen = sorted([f_line_price(*UST_CAPA, SON), f_line_price(*ALT_CAPA, SON)])
    assert sonlar == pytest.approx(beklenen, abs=1e-9)


def test_alt_sinir_yukselen_capada_gercekten_yukselir():
    ax = _eksen()
    grafik._formasyon_ciz(ax, _goruntu(True), N, 300.0, {})
    # Alt sınır: alt çapanın başlangıç değeri (8,0 @bar5) ile seçilir.
    alt = [ln for ln in _bant_cizgileri(ax) if float(ln.get_ydata()[0]) == pytest.approx(8.0)]
    assert len(alt) == 1
    y = [float(v) for v in alt[0].get_ydata()]
    assert all(b >= a - 1e-12 for a, b in zip(y, y[1:]))      # monoton artan
    assert y[-1] - y[0] == pytest.approx(0.1 * (SON - 5), abs=1e-9)


def test_capa_yoksa_yatay_yedek():
    ax = _eksen()
    grafik._formasyon_ciz(ax, _goruntu(False), N, 300.0, {})
    for ln in _bant_cizgileri(ax):
        y = [float(v) for v in ln.get_ydata()]
        assert max(y) - min(y) == pytest.approx(0.0, abs=1e-12)   # düz


def test_bant_oncesi_uzanti_ayni_dogru():
    """x0 > 0 iken geriye kesikli uzantı da motorun doğrusu üzerindedir."""
    ax = _eksen()
    grafik._formasyon_ciz(ax, _goruntu(True), N, 300.0, {})
    kesikli = [ln for ln in ax.lines if ln.get_linestyle() not in ("-", "solid", None)
               and len(ln.get_xdata()) > 2]
    assert len(kesikli) == 2
    for ln in kesikli:
        xs = [int(v) for v in ln.get_xdata()]
        ys = [float(v) for v in ln.get_ydata()]
        assert xs[0] == 0 and xs[-1] == 5
        capa = UST_CAPA if ys[-1] == pytest.approx(f_line_price(*UST_CAPA, 5)) else ALT_CAPA
        assert ys[-1] == pytest.approx(f_line_price(*capa, 5), abs=1e-9)


# ---------------------------------------------------------------- grafik kapısı
class _Aday:
    family = "Üçgen"
    pattern_type = "Yükselen Üçgen"


class _Snap:
    def __init__(self, state, q=80.0, minq=46.0, aktif=True):
        self.state = state
        self.active = _Aday() if aktif else None
        self.effective_quality = q
        self.min_raw_quality = minq
        self.min_specialized_quality = 60.0


@pytest.mark.parametrize("durum", ["KIRILIM_ADAYI", "RETEST_BEKLENIYOR", "FORMASYON_TAMAMLANDI",
                                   "SIKISMA_GUCLENIYOR", "KIRILIM_DENEMESI",
                                   "BASARISIZ_KIRILIM", "FORMASYON_ZAYIFLADI",
                                   "FORMASYON_GECERSIZ", "KIRILIM_TEYIT_ALAMADI"])
def test_grafik_kapisi_her_durumda_aktif_formasyonu_cizer(durum):
    """Karar: formasyon varsa çizilir; durum yalnız etiket olur (başarısız dâhil)."""
    import grafik_uret as U
    assert U._grafik_formasyonu_bul(_Snap(durum)) is not None


def test_grafik_kapisi_kalite_ve_aktif_yok_elenir():
    """Durumdan bağımsız, ama motorun kendi geçerlilik ölçütleri yine uygulanır."""
    import grafik_uret as U
    assert U._grafik_formasyonu_bul(_Snap("RETEST_BEKLENIYOR", q=40.0)) is None
    assert U._grafik_formasyonu_bul(_Snap("RETEST_BEKLENIYOR", aktif=False)) is None
    assert U._grafik_formasyonu_bul(_Snap("FORMASYON_YOK", aktif=False)) is None


def test_durum_etiketi_turkce_ve_bilinmeyen_bos():
    assert grafik.formasyon_durum_etiketi("RETEST_BEKLENIYOR") == "retest bekleniyor"
    assert grafik.formasyon_durum_etiketi("BASARISIZ_KIRILIM") == "kırılım başarısız"
    assert grafik.formasyon_durum_etiketi("KIRILIM_ADAYI") == "kırılım adayı"
    assert grafik.formasyon_durum_etiketi("BILINMEYEN") == ""
    assert grafik.formasyon_durum_etiketi(None) == ""


def test_altyazi_formasyon_adi_ve_durum():
    import main as M
    alt = M._kare_altyazisi("THYAO", "1h", {"mum_sayisi": 180, "formasyon_ad": "Yükselen Üçgen",
                                            "formasyon_durum": "RETEST_BEKLENIYOR",
                                            "son_bar_ts": "2026-09-25T17:30:00+03:00"})
    assert alt == "THYAO · 1s · 180 mum · Yükselen Üçgen (retest bekleniyor) · son kapanan 25.09.2026 17:30"
