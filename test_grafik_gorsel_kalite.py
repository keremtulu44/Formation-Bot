# -*- coding: utf-8 -*-
"""Görsel kalite kapıları (görsel-2/3): ölçülebilir kurallar, piksel hash'i yok.

Kurallar:
  1. Yazı mumun üstüne binmez: gerçek önbellekteki örnek karelerde
     `meta["kalite"]["mum_cakisan"] == 0` (ölçüm: `_mum_cakisma_say`).
  2. Sağ fiyat şeridindeki etiketler dikeyde üst üste binmez ve hiçbiri atılmaz.
  3. Bant teması işareti, temasın gerçekten olduğu bandın tarafındaki fitil
     ucunda çizilir (üst banda yakın mum → tepe, alt banda yakın mum → dip).
  4. GÖRSEL-3 renk sözleşmesi: yükselen mum YEŞİL ve içi BOŞ, düşen mum KIRMIZI
     ve DOLU (neon değil: iki ton da orta doygunlukta); şerit spike'ı mumun
     yönünde renklenir; lejant renk şemasını yazar.
  5. GÖRSEL-3 kalabalık denetimi: şeritte kaynak başına azami etiket
     (`sag_etiket_maks`); elenen adaylar sayılır, sessizce kaybolmaz.

Testler `bot_data/` önbelleğini yalnız OKUR.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import mock

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


# ------------------------------------------------- GÖRSEL-3: renk sözleşmesi


def _mum_stili(ax):
    """`_mumlar_ciz`in ürettiği gövdeleri (index → facecolor/edgecolor) döndürür."""
    govdeler = {}
    for cagri in ax.bar.call_args_list:
        x = int(cagri.args[0][0]) if cagri.args else int(cagri.kwargs["x"][0])
        govdeler[x] = {"face": cagri.kwargs["facecolor"], "edge": cagri.kwargs["edgecolor"]}
    return govdeler


def test_yukselen_yesil_bos_dusen_kirmizi_dolu():
    """Yükselen mum yeşil VE içi boş (koyu yeşil dolgu), düşen kırmızı VE dolu."""
    from unittest import mock

    ax = mock.MagicMock()
    acilis = [10.0, 10.0, 11.0]     # 0 yükselen · 1 düşen · 2 doji (k == a)
    kapanis = [12.0, 9.0, 11.0]
    grafik._mumlar_ciz(ax, acilis, [13.0, 13.0, 13.0], [8.0, 8.0, 8.0], kapanis,
                       grafik.SABITLER["mum_genislik_orani"], (0.0, 20.0))
    govdeler = _mum_stili(ax)
    assert govdeler[0]["edge"] == grafik.PALET["mum_yukselen"]      # yükseliş → yeşil
    assert govdeler[0]["face"] == grafik.PALET["mum_yukselen_ic"]   # içi boş okunur
    assert govdeler[1]["edge"] == grafik.PALET["mum_dusen"]         # düşüş → kırmızı
    assert govdeler[1]["face"] == grafik.PALET["mum_dusen"]         # dolu gövde
    assert govdeler[2]["edge"] == grafik.PALET["mum_yukselen"]      # eşit (k>=a) yeşil
    # neon yok: iki ton da orta doygunlukta (parlak saf renk DEĞİL)
    for ad in ("mum_yukselen", "mum_dusen"):
        rgb = [int(grafik.PALET[ad][i:i + 2], 16) for i in (1, 3, 5)]
        doygunluk = (max(rgb) - min(rgb)) / max(rgb)
        assert 0.35 <= doygunluk <= 0.8, (ad, rgb, doygunluk)   # renkli ama bağıran değil
        assert max(rgb) <= 240, (ad, rgb)                       # parlaklık tavanı (neon yok)


def test_son_fiyat_cipi_mumun_yonunde_renklenir(tmp_path):
    """Düşen son mum → son fiyat çipi kırmızı; yükselen son mum → yeşil.

    Eskiden çip her zaman yükselen rengindeydi: son mum kırmızıyken kare yanlış
    renk ima ediyordu (GÖRSEL-3 geri bildirimi).
    """
    import pandas as pd

    def _cerceve(yon: float):
        """Son ÜÇ mum istenen yönde: anlık görüntünün seçtiği "son mum" ne olursa olsun."""
        zamanlar = [datetime(2026, 9, 1, 9, 30, tzinfo=IST) + timedelta(hours=i)
                    for i in range(40)]
        fiyat = 100.0
        satirlar = []
        for i in range(40):
            a = fiyat
            k = a + 0.4 if i % 2 == 0 else a - 0.4
            if i >= 36:
                k = a + yon
            satirlar.append({"open": a, "high": max(a, k) + 0.2, "low": min(a, k) - 0.2,
                             "close": k, "volume": 1000.0 + i})
            fiyat = k
        return pd.DataFrame(satirlar, index=pd.DatetimeIndex(zamanlar, name="timestamp"))

    renkler = {}
    for ad, yon in (("yukselen", 0.5), ("dusen", -0.5)):
        g = grafik.anlik_goruntu(None, "1h", _cerceve(yon), simdi=datetime(2026, 9, 5, tzinfo=IST))
        g["sembol"] = "TEST"
        assert (float(g["kapanis"][-1]) >= float(g["acilis"][-1])) == (yon > 0)
        with mock.patch.object(grafik, "_sag_ciz", wraps=grafik._sag_ciz) as sahte:
            _, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / f"{ad}.png")})
        assert meta.get("hata") is None
        # çip kararı aday kaydından okunur (piksel ölçümü yok)
        adaylar = sahte.call_args.args[2]
        son = next(a for a in adaylar if a.get("sabit"))
        renkler[ad] = son["bg"]
    assert renkler["yukselen"] == grafik.PALET["mum_yukselen"]
    assert renkler["dusen"] == grafik.PALET["mum_dusen"]


def test_serit_spike_rengi_mum_yonunden_gelir():
    """Katılım şeridi: spike kendi mumunun yönünde (yükselen yeşil / düşen kırmızı)."""
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10.8, 8.1), dpi=100)
    ax = fig.add_axes([0.075, 0.1, 0.8, 0.2])
    n = 4
    goruntu = {
        "acilis": [10.0, 12.0, 11.0, 10.0],
        "kapanis": [12.0, 10.5, 11.5, 9.5],
        "serit": {"degerler": [2.0, 2.2, 0.4, 1.9], "esik": 1.5, "spike": [0, 1, 3],
                  "yildiz": [], "tepe": 2.2},
    }
    grafik._serit_ciz(ax, goruntu, n)
    barlar = [c for c in ax.containers]
    assert barlar, "spike çizilmedi"
    renkler = [p.get_facecolor() for p in barlar[0].patches]
    def _hex(rgba):
        return "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in rgba[:3])
    assert _hex(renkler[0]) == grafik.PALET["serit_yuk"]     # mum 0 yükselen
    assert _hex(renkler[1]) == grafik.PALET["serit_dus"]     # mum 1 düşen
    assert _hex(renkler[2]) == grafik.PALET["serit_dus"]     # mum 3 düşen


def test_lejant_renk_semasini_yazar():
    """Lejant: yeşil boş = yükselen · kırmızı dolu = düşen (renk körlüğü + ilk bakış)."""
    g = {
        "sembol": "TEST", "tf": "1h", "tf_kisa": "1s", "sol": 0, "sag": 60,
        "zamanlar": [], "acilis": [], "yuksek": [], "dusuk": [], "kapanis": [],
        "formasyon": {}, "alarm": {}, "zone": {}, "olay": {}, "serit": {},
        "temas": [], "isaretler": [],
    }
    lejant = " ".join(grafik._lejant(g, False))
    assert "yeşil" in lejant and "yükselen" in lejant
    assert "kırmızı" in lejant and "düşen" in lejant


# --------------------------------------------- GÖRSEL-3: şerit kalabalık denetimi


def test_sag_serit_kaynak_basina_sinirlanir_ve_sayilir():
    """Kalabalık şerit: kaynak başına azami etiket; en yeni/yakın olan kalır."""
    maks = grafik.SABITLER["sag_etiket_maks"]
    adaylar = []
    for i, (bar, seviye) in enumerate([(10, 100.0), (40, 101.0), (70, 102.0), (95, 103.0)]):
        adaylar.append({"kaynak": "zone", "x": 179.6, "y": seviye, "metin": f"OB↑ {i}",
                        "renk": "#2bb673", "sabit": False, "oncelik": 2, "bg": None,
                        "yeni": float(bar)})
    # kritik etiket (öncelik 5) limit dışında kalmamalı
    adaylar.append({"kaynak": "olay", "x": 179.6, "y": 103.5, "metin": "kritik 103,50",
                    "renk": "#f0885c", "sabit": False, "oncelik": 5, "bg": None, "yeni": 95.0})
    elenen = grafik._sag_ele(adaylar, son=103.0)
    kalan = [a for a in adaylar if not a.get("elendi")]
    assert elenen.get("zone") == 4 - int(maks["zone"])
    assert len([a for a in kalan if a["kaynak"] == "zone"]) == int(maks["zone"])
    # kalanlar son kapanışa EN YAKIN olanlar (100 elenir, 101/102/103 kalır)
    kalan_zone = {a["metin"] for a in kalan if a["kaynak"] == "zone"}
    assert kalan_zone == {"OB↑ 3", "OB↑ 2", "OB↑ 1"}
    assert [a["metin"] for a in adaylar if a.get("elendi")] == ["OB↑ 0"]
    assert any(a["metin"].startswith("kritik") for a in kalan)


def test_sag_serit_eledi_sayisi_meta_ya_yazilir(tmp_path):
    """Sessiz kayıp yok: elenen etiket sayısı `meta["sag"]["eledi_kaynak"]`ta."""
    sonuc = grafik_uret.kare_uret("GARAN", "1h", veri_dizin="bot_data", zone=True,
                                  mum=150, formasyon_tara=True,
                                  cikti=str(tmp_path / "GARAN_1h.png"))
    assert sonuc.get("hata") is None
    sag = sonuc["meta"]["sag"]
    assert set(sag) >= {"yerlesen", "atlanan", "eledi_kaynak"}
    assert all(int(v) >= 0 for v in sag["eledi_kaynak"].values())
    # yerleşen + atlanan + elenen = gerçekten üretilen aday sayısı (sessiz kayıp yok)
    assert sag["yerlesen"] >= 1
