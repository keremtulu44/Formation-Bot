# -*- coding: utf-8 -*-
"""Sağ boşluk (FAZ 2 §"Sağ Boşluk Kuralı"): son mumun sağında HER ZAMAN 12-15 mum.

Kararlar (2026-10-15; kullanıcı planı FAZ 2 + önceki §37 kararlarının yerine):
  1. Boşluk artık MUM SAYISIDIR (varsayılan 15; önerilen aralık 12-15), eksen
     yüzdesi değil: "her grafiğin sağında 12-15 mumluk boş alan".
  2. Fiyat etiketleri, seviye çizgileri, 🎯 hedef kutusu ve AKTİF BOS/CHoCH
     hedefi bu alana çizilir — mumların üzerine yazı binmez.
  3. Bant çizgileri, OB/FVG kutuları ve bant işaretleri boşluğa DEVAM eder;
     devam KESİKLİ değildir (bant çizgisinin kendisi, tek parça).
  4. `GRAFIK_SAG_BOSLUK_MUM=0` boşluğu kapatır; eski oran anahtarı
     (`GRAFIK_SAG_BOSLUK`) yalnız o tanımlıysa kullanılır (geri uyumluluk).

Asıl ölçü GERÇEK eksen sınırıdır: `meta` tek başına yetmez. Şerit (sharex) en son
çizilip ortak x sınırını sıfırlayabildiği için `meta` doğru, piksel yanlış olabilir
(sınırı yalnız `meta`dan okuyan testler bunu göremez). Bu yüzden tam kare testleri
figürün son halini yakalar ve `ax.get_xlim()` okur.
"""

from __future__ import annotations

import unittest.mock as mock

import pytest
from matplotlib.patches import Rectangle

import grafik
import test_grafik_formasyon_cizgi as fc
from patterns.mathutil import f_line_price
from test_grafik_gorsel4 import _bolge, _eksen, _olay_goruntusu
from test_grafik_iskelet import _cerceve, _cift, _goruntu, _png_olcu


@pytest.fixture(autouse=True)
def _ortam_temiz(monkeypatch):
    """Dışarıdan gelen boşluk anahtarları varsayılan ölçümleri bozmasın."""
    monkeypatch.delenv("GRAFIK_SAG_BOSLUK", raising=False)
    monkeypatch.delenv("GRAFIK_SAG_BOSLUK_MUM", raising=False)


def _kareyi_ciz(g, tf, tmp_path, **secenek):
    """Kareyi GERÇEKTEN çizer: `(fig, meta, png_yolu)` — son eksen sınırları okunabilsin."""
    yakalanan: list = []
    orijinal = grafik._metin_ciz

    def sarmal(fig, *a, **k):
        yakalanan.append(fig)
        return orijinal(fig, *a, **k)

    with mock.patch.object(grafik, "_metin_ciz", sarmal):
        yol, meta = grafik.ciz(g, tf, {"cikti": str(tmp_path / "kare.png"), **secenek})
    assert yol and yakalanan, meta
    return yakalanan[-1], meta, yol


# ------------------------------------------------------------ boşluğun tanımı


def test_bosluk_mum_sayisi_ve_tf_matrisi_ile_sabit():
    """Boşluk her karede 15 mum (12-15 aralığı) — mum sayısı hesabı etkilemez."""
    assert grafik.sag_bosluk_mum(180) == 15
    assert grafik.sag_bosluk_mum(80) == 15
    for n in (35, 62, 80, 180, 240):
        assert grafik.sag_bosluk_mum(n) == 15, n


@pytest.mark.parametrize("ham, beklenen", [
    ("0", 0), ("-4", 0),                         # kapalı: eski görünüm
    ("", 15), ("abc", 15), ("nan", 15), ("inf", 15),     # bozuk → varsayılan, çizim engellenmez
    ("12", 12), ("99", 40),                      # üst sınır 40 bar
])
def test_env_degerleri_mum_anahtari(monkeypatch, ham, beklenen):
    monkeypatch.setenv("GRAFIK_SAG_BOSLUK_MUM", ham)
    assert grafik.sag_bosluk_mum(180) == beklenen


@pytest.mark.parametrize("ham, beklenen", [
    ("0", 0),                                    # eski oran anahtarı: kapatır
    ("5.3", 10),                                 # 180 mumda ≈10 bar (eski davranış korunur)
    ("abc", 10),                                 # bozuk oran → oran varsayılanı (5,3)
])
def test_eski_oran_anahtari_geri_uyumlu(monkeypatch, ham, beklenen):
    """`GRAFIK_SAG_BOSLUK` (eski oran) yalnız tanımlıysa kullanılır."""
    monkeypatch.setenv("GRAFIK_SAG_BOSLUK", ham)
    assert grafik.sag_bosluk_mum(180) == beklenen


def test_mum_yoksa_bosluk_yok():
    assert grafik.sag_bosluk_mum(0) == 0
    assert grafik.sag_bosluk_mum(-5) == 0


# --------------------------------------------- GERÇEK eksen sınırı (tam kare)


@pytest.mark.parametrize("n_cerceve, tf, bosluk", [(240, "1h", 15), (120, "4h", 15)])
@pytest.mark.parametrize("secenek, eksen_sayisi", [({}, 1), ({"serit": True}, 2),
                                                    ({"serit": False}, 1),
                                                    ({"sade": True}, 1)],
                         ids=["varsayilan", "panel-acik", "serit-yok", "sade"])
def test_gercek_eksen_sinirinda_bosluk_var(tmp_path, n_cerceve, tf, bosluk, secenek,
                                           eksen_sayisi):
    """Ana eksen VE şerit aynı sınırı taşır; `meta` ile piksel birbirinden kopmaz."""
    g = _goruntu(_cerceve(n_cerceve, tf), tf, cift=None)
    fig, meta, _ = _kareyi_ciz(g, tf, tmp_path, **secenek)
    n = meta["mum_sayisi"]                       # FAZ 2: pencere TF matrisinden (80/68)
    assert n in (80, 68) and meta["kare"]["sag_bosluk"] == bosluk == grafik.sag_bosluk_mum(n)
    beklenen = (-0.6, n - 0.4 + bosluk)
    assert len(fig.axes) == eksen_sayisi     # panel kapalı: tek eksen (FAZ 1)
    for ax in fig.axes:
        assert ax.get_xlim() == pytest.approx(beklenen)
    assert meta["kare"]["x_siniri"] == pytest.approx(list(beklenen))
    assert meta["kare"]["sag_bosluk_yuzde"] == pytest.approx(
        100.0 * bosluk / (n + 0.2 + bosluk), abs=0.01)


def test_env_sifir_eski_gorunumu_geri_getirir(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAFIK_SAG_BOSLUK_MUM", "0")
    g = _goruntu(_cerceve(240, "1h"), "1h", _cift(apex_bar=244))
    fig, meta, _ = _kareyi_ciz(g, "1h", tmp_path)
    n = meta["mum_sayisi"]
    assert meta["kare"]["sag_bosluk"] == 0 and meta["kare"]["sag_bosluk_yuzde"] == 0.0
    for ax in fig.axes:
        assert ax.get_xlim() == pytest.approx((-0.6, n - 0.4))
    # boşluk yokken apex son mumun ötesinde kalır: ✕ çizilmez, çizgi son mumda biter
    assert [ln for ln in fig.axes[0].lines if ln.get_marker() == "x"] == []


def test_katman_hatasinda_bosluk_korunur(tmp_path):
    """Formasyon katmanı çökse de eksen payı kalır (kare yine aynı kadrajda)."""
    g = _goruntu(_cerceve(240, "1h"), "1h")
    with mock.patch.object(grafik, "_formasyon_ciz", side_effect=RuntimeError("test")):
        fig, meta, _ = _kareyi_ciz(g, "1h", tmp_path)
    assert "formasyon" in meta["eksik_katmanlar"]
    n = meta["mum_sayisi"]
    for ax in fig.axes:
        assert ax.get_xlim() == pytest.approx((-0.6, n - 0.4 + 15))


def test_kare_boyutu_degismez(tmp_path):
    """Boşluk tuvali genişletmez (§0.12q: 4:3 oranı korunur); mumlar biraz daralır."""
    _, _, yol = _kareyi_ciz(_goruntu(_cerceve(240, "1h"), "1h"), "1h", tmp_path)
    assert _png_olcu(yol) == (1080, 810)


@pytest.mark.parametrize("n_cerceve, tf", [(240, "1h"), (120, "4h")])
def test_mumlar_gereginden_fazla_daralmaz(tmp_path, monkeypatch, n_cerceve, tf):
    """Boşluk mumları fazla daraltmaz: px/bar eski (boşluksuz) görünümün %80'inde.

    Ölçüm: 80 mumluk 1s karesinde boşluk öncesi ≈10,8 px/bar, boşlukla ≈9,1 px/bar
    (≈%84). Eşik %80: boşluk 12-15 mum aralığında kaldığı sürece rahat geçer,
    oran bozulursa (ör. yüzde bazlı eski hesap 80 mumda %33 kayıp) kırmızı olur.
    """
    g = _goruntu(_cerceve(n_cerceve, tf), tf, cift=None)
    fig_yeni, _, _ = _kareyi_ciz(g, tf, tmp_path)
    monkeypatch.setenv("GRAFIK_SAG_BOSLUK_MUM", "0")
    fig_eski, _, _ = _kareyi_ciz(g, tf, tmp_path)

    def px_bar(fig):
        ax = fig.axes[0]
        sol, sag = ax.get_xlim()
        return ax.get_window_extent().width / (sag - sol)

    assert px_bar(fig_yeni) / px_bar(fig_eski) >= 0.80


# ----------------------------------------------------------------- OB/FVG kutuları


def _sag_kenarlar(ax):
    return sorted({round(p.get_x() + p.get_width(), 6)
                   for p in ax.patches if isinstance(p, Rectangle)})


def test_son_muma_uzanan_kutu_bosluga_devam_eder():
    n, bosluk = 60, 4
    fig, ax = _eksen(n)
    ax.set_xlim(-0.6, n - 0.4 + bosluk)
    grafik._zone_ciz(ax, {"cizilen": [_bolge(x0=10, x1=n - 1)]}, n, (90.0, 115.0), [],
                     sag_bosluk=bosluk)
    assert _sag_kenarlar(ax) == [n - 0.5 + bosluk]       # son mum + boşluk (63,5)


def test_son_mumdan_once_biten_kutu_uzamaz():
    n, bosluk = 60, 4
    fig, ax = _eksen(n)
    grafik._zone_ciz(ax, {"cizilen": [_bolge(x0=10, x1=40)]}, n, (90.0, 115.0), [],
                     sag_bosluk=bosluk)
    assert _sag_kenarlar(ax) == [40.5]


def test_bosluk_yokken_kutu_eski_geometride():
    n = 60
    fig, ax = _eksen(n)
    grafik._zone_ciz(ax, {"cizilen": [_bolge(x0=10, x1=n - 1)]}, n, (90.0, 115.0), [])
    assert _sag_kenarlar(ax) == [n - 0.5]


def _cip(y=105.0, metin="OB↑"):
    return {"kaynak": "zone", "x": 59.6, "y": y, "metin": metin, "renk": "#2bb673",
            "sabit": False, "oncelik": 2, "bg": None, "yeni": 50.0}


def test_serit_yedegi_kilavuzu_uzamis_kutunun_uzerine_cizilmez():
    """Etiketi şeride düşen kutunun kılavuzu, UZAMIŞ kutunun üstünden geçmemeli."""
    n, bosluk = 60, 4
    kenar = n - 0.4 + bosluk
    ince = _bolge(alt=100.0, ust=100.15, x0=10, x1=n - 1, skor=88)    # yazı sığmaz → şerit

    fig, ax = _eksen(n)
    ax.set_xlim(-0.6, kenar)
    sag: list = []
    grafik._zone_ciz(ax, {"cizilen": [ince]}, n, (90.0, 115.0), sag, sag_bosluk=bosluk)
    assert len(sag) == 1 and sag[0]["kilavuz_x"] == n - 1 + bosluk    # kutunun UZAMIŞ ucu
    onceki = len(ax.get_lines())
    grafik._sag_ciz(ax, fig, sag, n, (90.0, 115.0), x_kenar=kenar)
    assert len(ax.get_lines()) == onceki, "kılavuz çizgisi çizilmemeli"

    # Kontrol: kılavuz uzamamış uçtan başlasaydı kutunun üstüne çizgi düşerdi.
    fig2, ax2 = _eksen(n)
    ax2.set_xlim(-0.6, kenar)
    eski = [{**sag[0], "kilavuz_x": float(n - 1)}]
    grafik._sag_ciz(ax2, fig2, eski, n, (90.0, 115.0), x_kenar=kenar)
    assert len(ax2.get_lines()) == 1


# ----------------------------------------------------------- BOS/CHoCH çizgileri


def _yatay_cizgiler(ax):
    return {float(ln.get_ydata()[0]): [float(v) for v in ln.get_xdata()]
            for ln in ax.get_lines()
            if len(ln.get_ydata()) == 2 and ln.get_ydata()[0] == ln.get_ydata()[1]}


def test_bos_choch_cizgisi_pivot_baslar_ve_hedefe_uzanir():
    """FAZ 3 §4.2: çizgi PİVOT noktasından başlar, kırılım mumunda biter; yalnız
    AKTİF hedef (kritik olay) sağdaki boşluğa kadar uzar."""
    n, bosluk = 60, 4
    fig, ax = _eksen(n)
    ax.set_xlim(-0.6, n - 0.4 + bosluk)
    goruntu = _olay_goruntusu()
    for b in goruntu["olay"]["olaylar"]:
        b["pivot_bar"] = 12                        # motorun `origin_source_bar`ı
    goruntu["olay"]["kritik"] = {"seviye": 98.0, "bar": 50, "pivot_bar": 12,
                                 "tur": "CHoCH", "yon": "alt"}
    grafik._olay_ciz(ax, goruntu, n, [], sag_bosluk=bosluk)
    cizgiler = _yatay_cizgiler(ax)
    assert cizgiler[102.0] == [12.0, 40.0]         # BOS: pivot → kırılım mumu, uzatma YOK
    assert cizgiler[98.0] == [12.0, n - 1 + bosluk]     # CHoCH = aktif hedef: sağa uzar


def test_bosluk_yokken_aktif_hedef_son_mumda_biter():
    """Boşluk kapalıyken de kural aynı: pivot → kırılım mumu / aktif hedefte son mum."""
    n = 60
    fig, ax = _eksen(n)
    goruntu = _olay_goruntusu()
    for b in goruntu["olay"]["olaylar"]:
        b["pivot_bar"] = 12
    goruntu["olay"]["kritik"] = {"seviye": 98.0, "bar": 50, "pivot_bar": 12,
                                 "tur": "CHoCH", "yon": "alt"}
    grafik._olay_ciz(ax, goruntu, n, [])
    assert _yatay_cizgiler(ax)[98.0] == [12.0, n - 1.0]


# ---------------------------------------------------------------- sağ fiyat şeridi


def test_cipler_eksenin_sag_kenarina_sabitlenir():
    """Çip, boşluğun İÇİNE girmez: işaret ucu eksen kenarında, yazı kenarın dışında."""
    n, bosluk = 60, 4
    kenar = n - 0.4 + bosluk
    fig, ax = _eksen(n)
    ax.set_xlim(-0.6, kenar)
    grafik._sag_ciz(ax, fig, [_cip()], n, (90.0, 120.0), x_kenar=kenar)
    cipler = [t for t in ax.texts if t.get_bbox_patch() is not None]
    assert len(cipler) == 1
    assert cipler[0].xy[0] == pytest.approx(kenar)
    assert cipler[0].get_position()[0] == pytest.approx(kenar + 0.22)


def test_bosluk_yokken_cip_eski_konumda():
    n = 60
    fig, ax = _eksen(n)
    grafik._sag_ciz(ax, fig, [_cip()], n, (90.0, 120.0))
    cip = [t for t in ax.texts if t.get_bbox_patch() is not None][0]
    assert cip.xy[0] == pytest.approx(n - 0.4)
    assert cip.get_position()[0] == pytest.approx(n - 0.18)


# ------------------------------------------------------------------ bant çizgileri


def test_bant_cizgisi_bosluga_kesiksiz_devam_eder():
    """Devam KESİKLİ değil: bant çizgisi aynı kalınlıkta, tek parça, boşluğa uzar."""
    ax = fc._eksen()
    grafik._formasyon_ciz(ax, fc._goruntu(True), fc.N, 300.0, {}, sag_bosluk=4)
    cizgiler = fc._bant_cizgileri(ax)                 # bant kalınlığı + DÜZ çizgi
    assert len(cizgiler) == 2                         # ayrı bir "devam" çizgisi yok
    for ln in cizgiler:
        xs = [int(v) for v in ln.get_xdata()]
        assert xs == list(range(5, fc.SON + 5))       # bant başı → son mum + boşluk, kesintisiz
    ust = [ln for ln in cizgiler
           if float(ln.get_ydata()[0]) == pytest.approx(f_line_price(*fc.UST_CAPA, 5))][0]
    # her nokta motorun kendi doğrusunda: yeni geometri üretilmedi
    assert float(ust.get_ydata()[-1]) == pytest.approx(f_line_price(*fc.UST_CAPA, fc.SON + 4))
    # kesikli çizgi YALNIZ bant ÖNCESİ geri uzantıdır (§0.12e); sağda kesikli yok
    kesikli = [ln for ln in ax.lines if ln.get_linestyle() not in ("-", "solid", None)
               and len(ln.get_xdata()) > 2]
    assert len(kesikli) == 2 and all(int(ln.get_xdata()[-1]) == 5 for ln in kesikli)


def test_bant_dolgusu_da_bosluga_uzanir():
    ax = fc._eksen()
    grafik._formasyon_ciz(ax, fc._goruntu(True), fc.N, 300.0, {}, sag_bosluk=4)
    xs = ax.collections[0].get_paths()[0].vertices[:, 0]
    assert xs.max() == pytest.approx(fc.SON + 4)


# Daralan bant: üst -0,1/bar, alt +0,1/bar → iki doğru bar 25'te 10,0'da KESİŞİR.
N = 25
SON = N - 1
UST = (5, 12.0, 15, 11.0)
ALT = (5, 8.0, 15, 9.0)


def _daralan(apex_bar):
    f = {"start_bar": 5, "upper_now": f_line_price(*UST, SON), "lower_now": f_line_price(*ALT, SON),
         "hb1": UST[0], "hp1": UST[1], "hb2": UST[2], "hp2": UST[3],
         "lb1": ALT[0], "lp1": ALT[1], "lb2": ALT[2], "lp2": ALT[3], "apex_bar": apex_bar}
    return {"formasyon": f, "sol": 0, "isaretler": [], "temas": [], "temas_isaret": [],
            "yuksek": [], "dusuk": []}


@pytest.mark.parametrize("apex_bar, son_x, isaret_x", [
    (25, 25, 25),       # boşluğun İÇİNDE → çizgiler apex'te biter, ✕ kesişimde
    (40, 28, None),     # boşluğun ÖTESİNDE → çizgiler kenara kadar, ✕ görünmez
    (20, 24, None),     # GERİDE kaldı → uzatma yok (kesişip ters dönen çizgi uydurulmaz)
])
def test_bant_apeks_kurallari(apex_bar, son_x, isaret_x):
    ax = fc._eksen()
    grafik._formasyon_ciz(ax, _daralan(apex_bar), N, 300.0, {}, sag_bosluk=4)
    assert [int(ln.get_xdata()[-1]) for ln in fc._bant_cizgileri(ax)] == [son_x, son_x]
    isaretler = [ln for ln in ax.lines if ln.get_marker() == "x"]
    if isaret_x is None:
        assert isaretler == []
    else:
        assert len(isaretler) == 1
        assert int(isaretler[0].get_xdata()[0]) == isaret_x
        assert float(isaretler[0].get_ydata()[0]) == pytest.approx(10.0)    # iki doğrunun kesişimi


def test_bosluk_yokken_bant_ve_apeks_eski_davranista():
    ax = fc._eksen()
    grafik._formasyon_ciz(ax, _daralan(25), N, 300.0, {})
    assert [int(ln.get_xdata()[-1]) for ln in fc._bant_cizgileri(ax)] == [SON, SON]
    assert [ln for ln in ax.lines if ln.get_marker() == "x"] == []


def test_tam_karede_apeks_bosluga_dusunce_cizgiler_orada_biter(tmp_path):
    """Gerçek kare: apex son mumdan 5 bar sonra → çizgiler orada biter, ✕ kesişimde."""
    ust, alt = (200, 53.0, 244, 51.0), (200, 49.0, 244, 51.0)      # mutlak bar; 244'te kesişir
    cift = _cift(hb1=ust[0], hp1=ust[1], hb2=ust[2], hp2=ust[3],
                 lb1=alt[0], lp1=alt[1], lb2=alt[2], lp2=alt[3],
                 upper_now=f_line_price(*ust, 239), lower_now=f_line_price(*alt, 239),
                 apex_bar=244)
    g = _goruntu(_cerceve(240, "1h"), "1h", cift)
    fig, meta, _ = _kareyi_ciz(g, "1h", tmp_path)
    ax, n = fig.axes[0], meta["mum_sayisi"]
    apex_x = 244 - g["sol"]                                  # 184
    assert n <= apex_x < n + meta["kare"]["sag_bosluk"]
    kalin = grafik.SABITLER["cizgi_kalinlik"]["formasyon"]
    bantlar = [ln for ln in ax.lines
               if ln.get_color() == grafik.PALET["formasyon"] and len(ln.get_xdata()) > 5
               and abs(ln.get_linewidth() - kalin) < 1e-9 and ln.get_linestyle() in ("-", "solid")]
    assert sorted(int(ln.get_xdata()[-1]) for ln in bantlar) == [apex_x, apex_x]
    isaretler = [ln for ln in ax.lines if ln.get_marker() == "x"]
    assert len(isaretler) == 1 and int(isaretler[0].get_xdata()[0]) == apex_x
    assert float(isaretler[0].get_ydata()[0]) == pytest.approx(51.0, abs=1e-6)
