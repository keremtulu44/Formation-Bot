# -*- coding: utf-8 -*-
"""§38: iç yapı + PH/PL/WH/WL ok-çizgisi + bant teması dairesinin kaldırılması.

Kullanıcı kararları (2026-10-15):
  1. "İç yapı çizilsin ama okla aynı formatta": internal swing ve BOS/CHoCH, dış yapıyla AYNI
     ok, etiket ve çizgi biçiminde çizilir; tek fark etiket öneki `i` (iHL, iBOS↑).
  2. "ph pl wh wl olsun sağa doğru kesikli çizgi ile gitsin": motorun korunan/zayıf rolleri
     (PH/PL/WH/WL) okla etiketlenir ve swing mumundan SAĞA kesikli çizgiyle uzar.
  3. "formasyon temas noktası için yuvarlak konuyor onu silelim": temas dairesi kalktı.

Motor nesneleri `SimpleNamespace` ile taklit edilir (alan adları gerçek çıktıdan; bkz.
`test_grafik_yapi.py`). Gerçek motorla doğrulama alt süreçte yapılır (§14.2).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import grafik
from test_grafik_gorsel4 import _eksen
from test_grafik_iskelet import _cerceve, _cift, ZAMAN
from test_grafik_yapi import _goruntu_yapi, _olay, _swing


# ------------------------------------------------------------------------ yardımcılar


@pytest.fixture(autouse=True)
def _ortam_temiz(monkeypatch):
    """Geliştiricinin kabuğundaki `GRAFIK_IC_YAPI` testleri etkilemesin (kapatma testleri
    anahtarı kendi gövdesinde `setenv` ile kurar; bu fikstür onlardan ÖNCE çalışır)."""
    monkeypatch.delenv("GRAFIK_IC_YAPI", raising=False)


def _baglam(**kimlikler):
    """`StructureContext` taklidi: yalnız dört rol kimliği (0 = yok)."""
    taban = {"protected_high_identity": 0, "protected_low_identity": 0,
             "weak_high_identity": 0, "weak_low_identity": 0}
    taban.update(kimlikler)
    return SimpleNamespace(**taban)


def _ms_ic(dis=(), ic=(), olaylar=(), dis_baglam=None, ic_baglam=None, dis_aday=(), ic_aday=()):
    detay = {"external_swings": tuple(dis), "external_candidates": tuple(dis_aday),
             "internal_swings": tuple(ic), "internal_candidates": tuple(ic_aday),
             "event_history": tuple(olaylar)}
    if dis_baglam is not None:
        detay["external_context"] = dis_baglam
    if ic_baglam is not None:
        detay["internal_context"] = ic_baglam
    return {"market_structure": SimpleNamespace(details=detay), "volume_participation": None}


def _veri(ms, sol=0, sag=100):
    return grafik._olay_verisi(ms, sol, sag)


def _k_swing(bar, fiyat, yon="ust", sinif="HH", durum="teyitli", kapsam="dis", seviye=None,
             seviye_kapsam=None):
    """Çizim katmanının okuduğu swing kaydı (`_olay_verisi` çıktısıyla aynı alanlar)."""
    kayit = {"bar": bar, "fiyat": fiyat, "yon": yon, "sinif": sinif, "durum": durum,
             "kapsam": kapsam, "seviye": seviye, "seviye_kapsam": seviye_kapsam}
    return kayit


def _k_olay(bar, seviye, yon="ust", tur="BOS", kapsam="dis"):
    return {"bar": bar, "seviye": seviye, "yon": yon, "tur": tur, "kapsam": kapsam}


def _goruntu(**olay):
    return {
        "sembol": "TEST", "tf": "1h", "tf_kisa": "1s", "sol": 0, "sag": 120,
        "acilis": [100.0] * 60, "yuksek": [101.0] * 60, "dusuk": [99.0] * 60,
        "kapanis": [100.5] * 60,
        "formasyon": {}, "alarm": {}, "zone": {}, "temas": [], "isaretler": [], "serit": {},
        "olay": {"swinglar": [], "olaylar": [], "kritik": {}, **olay},
    }


def _oklar(ax):
    """Swing okları: `^`/`v` ve 4,5 pt (olay işareti 6,0 pt'tir)."""
    return [ln for ln in ax.lines if ln.get_marker() in ("^", "v")
            and ln.get_markersize() == 4.5]


def _yazilar(ax):
    return [str(t.get_text()) for t in ax.texts if str(t.get_text()).strip()]


def _agg_eksen(n=60, alt=90.0, ust=115.0):
    """Gerçek renderer'lı eksen (etiket kutuları ölçülebilsin)."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10.8, 8.1), dpi=100)
    FigureCanvasAgg(fig)
    ax = fig.add_axes([0.075, 0.1, 0.8, 0.8])
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_ylim(alt, ust)
    return fig, ax


def _kutu(t):
    return t.get_window_extent(t.figure.canvas.get_renderer())


def _kesisim(a, b) -> float:
    w = min(a.x1, b.x1) - max(a.x0, b.x0)
    h = min(a.y1, b.y1) - max(a.y0, b.y0)
    return w * h if (w > 0 and h > 0) else 0.0


# ============================================================ VERİ KATMANI (`_olay_verisi`)


def test_dis_sozlesme_ayni_ic_yapi_ayri_anahtarda():
    ms = _ms_ic(
        dis=[_swing(10, 100.0, kimlik=1), _swing(20, 90.0, "LOW", "HL", kimlik=2)],
        ic=[_swing(15, 95.0, kimlik=11), _swing(25, 92.0, "LOW", "LL", kimlik=12)],
        olaylar=[_olay(30, 99.0, kimlik=3),
                 _olay(40, 91.0, "EVENT_CHOCH", "DOWN", "INTERNAL", kimlik=13)])
    v = _veri(ms)
    assert [b["bar"] for b in v["swinglar"]] == [10, 20]
    assert all(b["kapsam"] == "dis" for b in v["swinglar"])
    assert [b["bar"] for b in v["ic_swinglar"]] == [15, 25]
    assert all(b["kapsam"] == "ic" for b in v["ic_swinglar"])
    assert [b["bar"] for b in v["olaylar"]] == [30] and [b["bar"] for b in v["ic_olaylar"]] == [40]
    assert v["ic_olaylar"][0]["tur"] == "CHoCH" and v["ic_olaylar"][0]["kapsam"] == "ic"
    # dış sayaçlar iç yapıyı SAYMAZ (eski sözleşme); iç yapının kendi sayaçları var
    assert v["cizilen"] == 3 and v["elenen"] == 0
    assert v["ic_cizilen"] == 3 and v["ic_elenen"] == 0
    assert v["kritik"]["bar"] == 30                      # kritik yalnız DIŞ olaydan
    assert v["kapak"] == {"swing": 10, "olay": 6}
    assert v["ic_kapak"] == {"swing": 8, "olay": 3}


def test_ic_swing_dis_yapiyla_ayni_pivotsa_tekrar_cizilmez():
    dis = [_swing(10, 100.0, kimlik=1)]
    ic = [_swing(10, 100.0, kimlik=11),                 # AYNI pivot (kaynak_bar + yön)
          _swing(10, 80.0, "LOW", "HL", kimlik=12),     # aynı bar, ters yön → ayrı pivot
          _swing(14, 97.0, kimlik=13)]
    v = _veri(_ms_ic(dis=dis, ic=ic))
    assert [(b["bar"], b["yon"]) for b in v["ic_swinglar"]] == [(10, "alt"), (14, "ust")]


def test_ic_olay_dis_olayla_ayni_bar_ve_seviyeyse_tekrar_cizilmez():
    olaylar = [_olay(30, 99.0, kimlik=3),
               _olay(30, 99.0, kapsam="INTERNAL", kimlik=13),   # dışla birebir aynı → elenir
               _olay(30, 98.0, kapsam="INTERNAL", kimlik=14),   # seviye farklı → kalır
               _olay(35, 99.0, kapsam="INTERNAL", kimlik=15)]   # bar farklı → kalır
    v = _veri(_ms_ic(olaylar=olaylar))
    assert [(b["bar"], b["seviye"]) for b in v["olaylar"]] == [(30, 99.0)]
    assert [(b["bar"], b["seviye"]) for b in v["ic_olaylar"]] == [(30, 98.0), (35, 99.0)]


def test_ic_olay_yalniz_onayli_gecerli_bos_choch():
    olaylar = [_olay(30, 99.0, kapsam="INTERNAL", kimlik=1, onay="PENDING"),
               _olay(31, 99.0, kapsam="INTERNAL", kimlik=2, gecer="INVALID"),
               _olay(32, 99.0, tur="EVENT_SWEEP", kapsam="INTERNAL", kimlik=3),
               _olay(33, 99.0, kapsam="INTERNAL", kimlik=4)]
    v = _veri(_ms_ic(olaylar=olaylar))
    assert [b["bar"] for b in v["ic_olaylar"]] == [33]


def test_ic_kapaklari_en_yeni_n_ve_elenen_sayilir():
    ic = [_swing(5 + i, 100.0 + i, kimlik=100 + i) for i in range(12)]
    ic_olay = [_olay(10 + i, 90.0 + i, kapsam="INTERNAL", kimlik=200 + i) for i in range(5)]
    v = _veri(_ms_ic(ic=ic, olaylar=ic_olay))
    assert [b["bar"] for b in v["ic_swinglar"]] == list(range(9, 17))      # en yeni 8
    assert [b["bar"] for b in v["ic_olaylar"]] == [12, 13, 14]             # en yeni 3
    assert v["ic_elenen"] == (12 - 8) + (5 - 3)
    assert v["elenen"] == 0                                                # dış sayaç etkilenmez


def test_ic_aday_swing_aday_durumuyla_gelir():
    v = _veri(_ms_ic(ic=[_swing(10, 100.0, kimlik=1)], ic_aday=[_swing(20, 95.0, "LOW", kimlik=2)]))
    assert {b["bar"]: b["durum"] for b in v["ic_swinglar"]} == {10: "teyitli", 20: "aday"}


def test_seviye_rolleri_baglam_kimliginden_swinge_yazilir():
    dis = [_swing(10, 110.0, kimlik=1), _swing(20, 90.0, "LOW", "HL", kimlik=2),
           _swing(30, 108.0, kimlik=3), _swing(40, 92.0, "LOW", "LL", kimlik=4)]
    baglam = _baglam(protected_high_identity=1, protected_low_identity=2,
                     weak_high_identity=3, weak_low_identity=4)
    v = _veri(_ms_ic(dis=dis, dis_baglam=baglam))
    assert {b["bar"]: b["seviye"] for b in v["swinglar"]} == {10: "PH", 20: "PL", 30: "WH", 40: "WL"}
    assert all(b["seviye_kapsam"] == "dis" for b in v["swinglar"])
    assert v["seviye_pencere_disi"] == 0


def test_rol_swing_sinifindan_bagimsizdir():
    """Motorun `swing_class` PH/PL'si (ilk/eşit uç) ROL değildir; rol yalnız bağlamdan gelir."""
    dis = [_swing(10, 110.0, sinif="PH", kimlik=1), _swing(20, 90.0, "LOW", "PL", kimlik=2),
           _swing(30, 108.0, sinif="LH", kimlik=3)]
    v = _veri(_ms_ic(dis=dis, dis_baglam=_baglam(protected_high_identity=3)))
    assert {b["bar"]: (b["sinif"], b["seviye"]) for b in v["swinglar"]} == {
        10: ("PH", None), 20: ("PL", None), 30: ("LH", "PH")}


def test_kirik_ya_da_gecersiz_swinge_rol_yazilmaz():
    """Motorun `active_by_id` kuralı: geçerli ve kırık değil — aksi halde rol çizilmez."""
    dis = [_swing(10, 110.0, kimlik=1, broken=True),
           _swing(20, 90.0, "LOW", "HL", kimlik=2, bozuk=True),
           _swing(30, 108.0, kimlik=3, durum="SWING_BROKEN"),
           _swing(40, 92.0, "LOW", "LL", kimlik=4)]
    baglam = _baglam(protected_high_identity=1, protected_low_identity=2,
                     weak_high_identity=3, weak_low_identity=4)
    v = _veri(_ms_ic(dis=dis, dis_baglam=baglam))
    assert {b["bar"]: b["seviye"] for b in v["swinglar"]} == {10: None, 20: None, 30: None, 40: "WL"}


def test_rol_tasiyan_uc_swing_kapagina_takilmaz():
    dis = [_swing(5 + i, 100.0 + i, kimlik=1 + i) for i in range(14)]    # kapak 10
    v = _veri(_ms_ic(dis=dis, dis_baglam=_baglam(protected_high_identity=1)))   # en ESKİ uç PH
    barlar = [b["bar"] for b in v["swinglar"]]
    assert 5 in barlar and len(barlar) == 11                  # 10 en yeni + rol taşıyan
    assert v["elenen"] == 3
    assert next(b for b in v["swinglar"] if b["bar"] == 5)["seviye"] == "PH"


def test_ic_rol_dis_pivotla_ortusuyorsa_dis_kayda_yazilir():
    dis = [_swing(10, 110.0, kimlik=1), _swing(20, 90.0, "LOW", "HL", kimlik=2)]
    ic = [_swing(10, 110.0, kimlik=11), _swing(20, 90.0, "LOW", "HL", kimlik=12)]
    v = _veri(_ms_ic(dis=dis, ic=ic,
                     dis_baglam=_baglam(protected_low_identity=2),          # dışta yalnız bar 20
                     ic_baglam=_baglam(weak_high_identity=11, protected_low_identity=12)))
    roller = {b["bar"]: (b["seviye"], b["seviye_kapsam"]) for b in v["swinglar"]}
    assert roller[10] == ("WH", "ic")        # dışın rolü yoktu → iç rol dış kayda yazıldı
    assert roller[20] == ("PL", "dis")       # dışın kendi rolü korunur
    assert v["ic_swinglar"] == []            # iki pivot da dışta zaten var


def test_ic_rol_dis_yapida_olmayan_pivotta_ic_kayitta_kalir():
    ic = [_swing(15, 95.0, "LOW", "HL", kimlik=12)]
    v = _veri(_ms_ic(dis=[_swing(10, 110.0, kimlik=1)], ic=ic,
                     ic_baglam=_baglam(protected_low_identity=12)))
    assert v["swinglar"][0]["seviye"] is None
    assert (v["ic_swinglar"][0]["seviye"], v["ic_swinglar"][0]["seviye_kapsam"]) == ("PL", "ic")


def test_ic_rol_kapaga_takilmaz():
    ic = [_swing(5 + i, 100.0 + i, kimlik=100 + i) for i in range(12)]
    v = _veri(_ms_ic(ic=ic, ic_baglam=_baglam(weak_high_identity=100)))     # en eski iç uç WH
    barlar = [b["bar"] for b in v["ic_swinglar"]]
    assert 5 in barlar and len(barlar) == 9                    # en yeni 8 + rol taşıyan
    assert v["ic_elenen"] == 3


def test_pencere_disi_rol_atanamaz_ve_sayilir():
    dis = [_swing(10, 110.0, kimlik=1), _swing(150, 90.0, "LOW", "HL", kimlik=2)]
    v = _veri(_ms_ic(dis=dis, dis_baglam=_baglam(protected_high_identity=1,
                                                 protected_low_identity=2)), sag=100)
    assert [b["bar"] for b in v["swinglar"]] == [10] and v["swinglar"][0]["seviye"] == "PH"
    assert v["seviye_pencere_disi"] == 1                      # sessiz kayıp yok: sayılır


def test_baglam_ve_ic_listesi_yoksa_eski_bicim_calisir():
    """Eski kayıt/test taklidi: yalnız dış liste + olay geçmişi — çökmez, iç yapı boş."""
    ms = {"market_structure": SimpleNamespace(details={
        "external_swings": (_swing(10, 100.0),), "external_candidates": (),
        "event_history": (_olay(30, 99.0),)}), "volume_participation": None}
    v = _veri(ms)
    assert len(v["swinglar"]) == 1 and v["swinglar"][0]["seviye"] is None
    assert v["ic_swinglar"] == [] and v["ic_olaylar"] == [] and v["ic_cizilen"] == 0
    assert v["seviye_pencere_disi"] == 0


def test_ic_yapi_kill_switch_ic_yapiyi_kapatir_rol_okunu_degil(monkeypatch):
    monkeypatch.setenv("GRAFIK_IC_YAPI", "0")
    ms = _ms_ic(dis=[_swing(10, 110.0, kimlik=1)], ic=[_swing(15, 95.0, "LOW", kimlik=12)],
                olaylar=[_olay(30, 99.0, kapsam="INTERNAL", kimlik=13)],
                dis_baglam=_baglam(protected_high_identity=1))
    v = _veri(ms)
    assert v["ic_swinglar"] == [] and v["ic_olaylar"] == [] and v["ic_kapak"] == {}
    assert v["swinglar"][0]["seviye"] == "PH"                 # dış rol oku yine çizilir


def test_ic_yapi_varsayilan_acik(monkeypatch):
    monkeypatch.delenv("GRAFIK_IC_YAPI", raising=False)
    v = _veri(_ms_ic(ic=[_swing(15, 95.0, "LOW", kimlik=12)]))
    assert len(v["ic_swinglar"]) == 1


def test_sabitler_ic_yapi_ve_cetvel_kapaklari():
    assert grafik.SABITLER["ic_swing_maks"] == 8 and grafik.SABITLER["ic_olay_maks"] == 3
    assert grafik.SABITLER["sag_etiket_maks"]["swing"] == 4    # dış ≤2 + iç ≤2 rol çipi


# ============================================================== ÇİZİM (`_olay_ciz`)


def test_ic_swing_dis_ile_ayni_okla_cizilir():
    """Kullanıcı: "okla aynı formatta" → aynı işaret, boyut, renk, solma, yazı biçimi."""
    g = _goruntu(swinglar=[_k_swing(10, 104.0, "ust", "HH", kapsam="dis")],
                 ic_swinglar=[_k_swing(20, 103.0, "ust", "HH", kapsam="ic")])
    fig, ax = _eksen()
    ozet = grafik._olay_ciz(ax, g, 60, [])
    oklar = _oklar(ax)
    assert len(oklar) == 2
    assert {(ln.get_marker(), ln.get_markersize(), ln.get_color(), ln.get_alpha(),
             ln.get_zorder()) for ln in oklar} == {("^", 4.5, grafik.PALET["swing"], 1.0, 6)}
    yazi = {str(t.get_text()): t for t in ax.texts}
    assert set(yazi) == {"HH", "iHH"}                          # tek fark: `i` öneki
    assert yazi["HH"].get_fontsize() == yazi["iHH"].get_fontsize()
    assert yazi["HH"].get_color() == yazi["iHH"].get_color()
    assert ozet["swing"] == 1 and ozet["ic_swing"] == 1


def test_ic_kirik_swing_dis_kirikla_ayni_soluk_ve_yazisiz():
    g = _goruntu(swinglar=[_k_swing(10, 104.0, durum="kirik")],
                 ic_swinglar=[_k_swing(20, 103.0, durum="kirik", kapsam="ic")])
    fig, ax = _eksen()
    grafik._olay_ciz(ax, g, 60, [])
    assert [ln.get_alpha() for ln in _oklar(ax)] == [0.2, 0.2]
    assert _yazilar(ax) == []


def test_seviye_rolu_okla_etiketlenir_ve_saga_kesikli_cizgiyle_uzar():
    g = _goruntu(swinglar=[
        _k_swing(10, 104.5, "ust", "LH", seviye="PH", seviye_kapsam="dis"),
        _k_swing(20, 96.25, "alt", "HL", seviye="WL", seviye_kapsam="dis")])
    fig, ax = _eksen()
    sag: list = []
    ozet = grafik._olay_ciz(ax, g, 60, sag, sag_bosluk=10)
    cizgiler = sorted((ln for ln in ax.lines if ln.get_gid() == "seviye-cizgisi"),
                      key=lambda ln: ln.get_xdata()[0])
    assert len(cizgiler) == 2
    for ln, (bar, fiyat) in zip(cizgiler, [(10, 104.5), (20, 96.25)]):
        assert list(ln.get_xdata()) == [bar, 59 + 10]          # swing mumundan sağ boşluğun sonuna
        assert list(ln.get_ydata()) == [fiyat, fiyat]          # yatay seviye
        assert ln.get_linestyle() == "--"                      # kesikli
    assert {"PH", "WL"} <= set(_yazilar(ax))                   # okla aynı kısa etiket
    assert sorted(a["metin"] for a in sag) == ["PH 104,50", "WL 96,25"]
    assert ozet["seviye"] == 2 and ozet["seviye_ic"] == 0 and ozet["phpl_serit"] == 2


def test_seviye_cizgisi_bosluk_kapaliyken_son_muma_kadar():
    g = _goruntu(swinglar=[_k_swing(10, 104.5, seviye="PH", seviye_kapsam="dis")])
    fig, ax = _eksen()
    grafik._olay_ciz(ax, g, 60, [])
    cizgi = next(ln for ln in ax.lines if ln.get_gid() == "seviye-cizgisi")
    assert list(cizgi.get_xdata()) == [10, 59]


def test_seviye_cizgisi_cip_olmasa_da_cizilir():
    """`sag=None` (şerit yok) → çip yok ama çizgi kalır (çizgi çipe bağlı değildir)."""
    g = _goruntu(swinglar=[_k_swing(10, 104.5, seviye="PH", seviye_kapsam="dis")])
    fig, ax = _eksen()
    grafik._olay_ciz(ax, g, 60, None)
    assert [ln.get_gid() for ln in ax.lines].count("seviye-cizgisi") == 1


def test_ic_rol_i_oneki_tasir_daha_soluk_cizgi_ve_dusuk_oncelik():
    g = _goruntu(
        swinglar=[_k_swing(10, 104.5, "ust", "LH", seviye="PH", seviye_kapsam="dis"),
                  _k_swing(30, 101.0, "ust", "HH", seviye="WH", seviye_kapsam="ic")],
        ic_swinglar=[_k_swing(20, 96.25, "alt", "HL", kapsam="ic", seviye="PL",
                              seviye_kapsam="ic")])
    fig, ax = _eksen()
    sag: list = []
    ozet = grafik._olay_ciz(ax, g, 60, sag)
    assert {"PH", "iPL", "iWH"} <= set(_yazilar(ax))
    oncelik = {a["metin"]: a["oncelik"] for a in sag}
    assert oncelik == {"PH 104,50": 4, "iPL 96,25": 3, "iWH 101,00": 3}
    alfa = {ln.get_xdata()[0]: ln.get_alpha() for ln in ax.lines
            if ln.get_gid() == "seviye-cizgisi"}
    assert alfa[10] > alfa[20] and alfa[10] > alfa[30]        # dış çizgi daha belirgin
    assert ozet["seviye"] == 3 and ozet["seviye_ic"] == 2


def test_sinif_ph_pl_korunan_seviye_degildir_yazisiz_ok():
    """Eski hata: `swing_class` PH/PL korunan sanılıp şerit çipi alıyordu; artık yazısız ok."""
    g = _goruntu(swinglar=[_k_swing(10, 104.5, "ust", "PH"), _k_swing(20, 96.0, "alt", "PL")])
    fig, ax = _eksen()
    sag: list = []
    ozet = grafik._olay_ciz(ax, g, 60, sag)
    assert len(_oklar(ax)) == 2 and _yazilar(ax) == []
    assert sag == [] and ozet["phpl_serit"] == 0 and ozet["seviye"] == 0
    assert [ln for ln in ax.lines if ln.get_gid() == "seviye-cizgisi"] == []


def test_kirik_swing_rol_yazmaz_cizgi_cekmez():
    g = _goruntu(swinglar=[_k_swing(10, 104.5, durum="kirik", seviye="PH", seviye_kapsam="dis")])
    fig, ax = _eksen()
    sag: list = []
    grafik._olay_ciz(ax, g, 60, sag)
    assert _yazilar(ax) == [] and sag == []
    assert [ln for ln in ax.lines if ln.get_gid() == "seviye-cizgisi"] == []


def test_ic_olay_i_oneki_ve_ayni_cizgi_bicimi():
    g = _goruntu(
        olaylar=[_k_olay(40, 102.0, "ust", "BOS"), _k_olay(50, 98.0, "alt", "CHoCH")],
        ic_olaylar=[_k_olay(42, 101.0, "ust", "BOS", "ic"), _k_olay(52, 97.0, "alt", "CHoCH", "ic")])
    fig, ax = _eksen()
    ozet = grafik._olay_ciz(ax, g, 60, [])
    olay_yazilari = sorted(str(t.get_text()) for t in ax.texts if t.get_gid() == "olay-ici")
    assert olay_yazilari == ["BOS↑", "CHoCH↓", "iBOS↑", "iCHoCH↓"]
    assert ozet["etiket_ic"] == 4 and ozet["ic_olay"] == 2
    cizgiler = [ln for ln in ax.lines if ln.get_color() == grafik.PALET["olay"]
                and ln.get_linewidth() == 0.9]
    assert len(cizgiler) == 4                                  # iç olay da AYNI kalınlık/renk
    assert sorted(ln.get_linestyle() for ln in cizgiler) == ["--", "--", ":", ":"]


def test_ic_olay_kritik_vurgusu_almaz():
    dis = _k_olay(50, 98.0, "alt", "CHoCH")
    ic = dict(dis, kapsam="ic")            # veri katmanı bunu ayıklar; çizim yine de vurguyu dışa verir
    g = _goruntu(olaylar=[dis], ic_olaylar=[ic],
                 kritik={"bar": 50, "seviye": 98.0, "tur": "CHoCH", "yon": "alt"})
    fig, ax = _eksen()
    sag: list = []
    grafik._olay_ciz(ax, g, 60, sag)
    assert len([ln for ln in ax.lines if ln.get_linewidth() == 1.4]) == 1     # tek kritik çizgi
    assert [a["metin"] for a in sag if a["metin"].startswith("kritik")] == ["kritik 98,00"]


def test_olay_yasi_kapsam_basina_hesaplanir():
    """İç olay dış olayın yaşını bozmaz: iki kapsamın da tek olayı "en yeni" (alfa 0,85)."""
    g = _goruntu(olaylar=[_k_olay(20, 102.0)], ic_olaylar=[_k_olay(30, 101.0, kapsam="ic")])
    fig, ax = _eksen()
    grafik._olay_ciz(ax, g, 60, [])
    alfalar = [ln.get_alpha() for ln in ax.lines
               if ln.get_color() == grafik.PALET["olay"] and ln.get_linewidth() == 0.9]
    assert alfalar == [0.85, 0.85]


def test_yalniz_ic_yapi_varken_de_cizim_calisir():
    g = _goruntu(ic_swinglar=[_k_swing(20, 103.0, kapsam="ic")],
                 ic_olaylar=[_k_olay(30, 101.0, kapsam="ic")])
    fig, ax = _eksen()
    ozet = grafik._olay_ciz(ax, g, 60, [])
    assert ozet["ic_swing"] == 1 and ozet["ic_olay"] == 1 and ozet["swing"] == 0


# --------------------------------------------------------- etiket çakışmaları (renderer'lı)


def test_swing_etiketi_bolge_yazisina_binmez(monkeypatch):
    def kur() -> float:
        fig, ax = _agg_eksen()
        bolge = ax.text(10, 105.0, "OB↓ %70", ha="center", va="bottom", fontsize=9)
        grafik._olay_ciz(ax, _goruntu(swinglar=[_k_swing(10, 104.5, "ust", "HH")]), 60, [])
        etiket = next(t for t in ax.texts if str(t.get_text()) == "HH")
        return _kesisim(_kutu(bolge), _kutu(etiket))

    with monkeypatch.context() as m:               # kontrol: ayırma kapalıyken etiket biner
        m.setattr(grafik, "_swing_etiketi_ayir", lambda ax, yazi, yukari, ofs, *a, **k: ofs)
        assert kur() > 4.0
    assert kur() <= 4.0


def test_olay_etiketi_swing_etiketinden_kacar(monkeypatch):
    def kur() -> float:
        fig, ax = _agg_eksen()
        g = _goruntu(swinglar=[_k_swing(30, 104.0, "ust", "HH")],
                     olaylar=[_k_olay(30, 104.0, "alt", "CHoCH")])   # ilk aday swing etiketinin üstü
        grafik._olay_ciz(ax, g, 60, [])
        swing = next(t for t in ax.texts if str(t.get_text()) == "HH")
        olay = next(t for t in ax.texts if t.get_gid() == "olay-ici")
        return _kesisim(_kutu(swing), _kutu(olay))

    with monkeypatch.context() as m:               # kontrol: swing kutusu engel olarak yazılmazsa biner
        m.setattr(grafik, "_swing_etiketi_ayir", lambda ax, yazi, yukari, ofs, *a, **k: ofs)
        assert kur() > 4.0
    assert kur() <= 4.0


def test_olay_etiketi_bolge_yazisindan_kacar():
    fig, ax = _agg_eksen()
    # CHoCH↓ için ilk aday: seviyenin hemen üstü → bölge yazısını tam oraya koy
    bolge = ax.text(30, 104.6, "FVG↓ %40", ha="center", va="bottom", fontsize=9)
    g = _goruntu(olaylar=[_k_olay(30, 104.0, "alt", "CHoCH")])
    grafik._olay_ciz(ax, g, 60, [])
    olay = next(t for t in ax.texts if t.get_gid() == "olay-ici")
    assert _kesisim(_kutu(bolge), _kutu(olay)) <= 4.0


def test_renderer_yoksa_etiket_ayirma_sessizce_atlanir():
    """Düz `Figure` (renderer'sız) → ofset aynen döner, çizim çökmez."""
    fig, ax = _eksen()
    assert grafik._yazi_kutulari(ax) == []
    g = _goruntu(swinglar=[_k_swing(10, 104.5, seviye="PH", seviye_kapsam="dis")],
                 ic_swinglar=[_k_swing(20, 100.0, kapsam="ic")])
    grafik._olay_ciz(ax, g, 60, [])
    assert {"PH", "iHH"} <= set(_yazilar(ax))


# ================================================================== LEJANT (§0.12v)


def _lejant_goruntu(**olay):
    return {"olay": {"swinglar": [], "olaylar": [], **olay}, "formasyon": {}, "alarm": {},
            "zone": {}, "serit": {}, "temas": [], "isaretler": []}


def _yapi_maddesi(goruntu):
    madde = [x for x in grafik._lejant(goruntu, False) if x.startswith("yapı:")]
    assert len(madde) <= 1
    return madde[0] if madde else None


def test_lejant_ic_yapi_ve_roller_cizilene_gore():
    g = _lejant_goruntu(
        swinglar=[_k_swing(10, 104.0, seviye="PH", seviye_kapsam="dis")],
        ic_swinglar=[_k_swing(20, 96.0, "alt", kapsam="ic", seviye="WL", seviye_kapsam="ic")])
    assert _yapi_maddesi(g) == "yapı: ▲▼ swing · i = iç yapı · PH korunan · WL zayıf · ━ kritik"


def test_lejant_yalniz_dis_yapi_ic_yapi_ve_rol_yazmaz():
    g = _lejant_goruntu(swinglar=[_k_swing(10, 104.0)])
    assert _yapi_maddesi(g) == "yapı: ▲▼ swing · ━ kritik"


def test_lejant_korunan_ve_zayif_rolleri_yalniz_cizilenleri_sayar():
    g = _lejant_goruntu(swinglar=[
        _k_swing(10, 104.0, seviye="PH", seviye_kapsam="dis"),
        _k_swing(20, 96.0, "alt", seviye="PL", seviye_kapsam="dis"),
        _k_swing(30, 103.0, seviye="WH", seviye_kapsam="dis")])
    madde = _yapi_maddesi(g)
    assert "PH/PL korunan" in madde and "WH zayıf" in madde and "WL" not in madde


def test_lejant_yalniz_ic_olay_varsa_i_oneki_aciklanir_ve_olay_maddeleri_ic_i_sayar():
    g = _lejant_goruntu(ic_olaylar=[_k_olay(30, 101.0, "ust", "CHoCH", "ic")])
    oge = grafik._lejant(g, False)
    assert _yapi_maddesi(g).startswith("yapı: ▲▼ swing · i = iç yapı")
    assert any("CHoCH" in x for x in oge)            # iç CHoCH çizgisi de lejantta anlatılır


def test_lejant_yapi_yoksa_madde_yok():
    assert _yapi_maddesi(_lejant_goruntu()) is None


def test_lejantta_temas_dairesi_ve_eski_seviye_ifadesi_yok():
    g = _lejant_goruntu(swinglar=[_k_swing(10, 104.0, seviye="PH", seviye_kapsam="dis")])
    g["formasyon"] = {"upper_now": 54.0, "lower_now": 47.0, "start_bar": 0}
    g["temas"] = [3, 6, 9]
    metin = " ".join(grafik._lejant(g, False))
    assert "bant teması" not in metin and "○" not in metin
    assert "PH/PL sağda" not in metin and "seviye (PH/PL" not in metin
    # yalnız DIŞ yapı çizildi: iç yapıyı anlatan hiçbir ifade yok (eski "▲▼ iç yapı" yanlış adı da)
    assert "iç yapı" not in metin and "yapı: ▲▼ swing · PH korunan" in metin


# ======================================================== UÇTAN UCA (`anlik_goruntu` + `ciz`)


def _ms_tam():
    """Çerçeve indekslerinde (60–239) iç/dış yapı + roller + iki olay."""
    return _ms_ic(
        dis=[_swing(150, 52.8, kimlik=1), _swing(170, 50.4, "LOW", "HL", kimlik=2)],
        ic=[_swing(160, 52.2, kimlik=11), _swing(180, 50.9, "LOW", "LL", kimlik=12),
            _swing(150, 52.8, kimlik=13)],                   # 13 = dış 1 ile aynı pivot
        olaylar=[_olay(200, 52.0, kimlik=3),
                 _olay(210, 51.5, "EVENT_CHOCH", "DOWN", "INTERNAL", kimlik=14)],
        dis_baglam=_baglam(protected_high_identity=1, protected_low_identity=2),
        ic_baglam=_baglam(weak_high_identity=11))


def test_ciz_meta_ic_yapi_ve_seviye_sayaclari(tmp_path):
    g = _goruntu_yapi(_ms_tam())
    _, meta = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "ic.png")})
    o = meta["olay"]
    assert o["swing"] == 2 and o["bos_choc"] == 1                 # dış sözleşme aynı
    assert o["ic_swing"] == 2 and o["ic_bos_choc"] == 1 and o["ic_cizilen"] == 3
    assert o["seviye"] == 3 and o["seviye_ic"] == 1 and o["phpl_serit"] == 3
    assert o["seviye_pencere_disi"] == 0 and o["ic_kadraj_disi"] == 0
    assert o["ic_olay_barlari"] == [210] and o["olay_barlari"] == [200]
    assert o["ic_kapak"] == {"swing": 8, "olay": 3}
    assert meta["eksik_katmanlar"] == []
    lejant = " ".join(meta["metin"]["lejant"])
    assert "yapı: ▲▼ swing · i = iç yapı · PH/PL korunan · WH zayıf · ━ kritik" in lejant


def test_ciz_bos_yapida_ic_alanlari_sifir_ve_sabit(tmp_path):
    g = grafik.anlik_goruntu(None, "4h", _cerceve(60, "4h"), simdi=ZAMAN)
    _, meta = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "bos.png")})
    assert set(meta["olay"]) >= {"ic_swing", "ic_bos_choc", "ic_cizilen", "ic_elenen", "ic_kapak",
                                 "ic_olay_barlari", "seviye", "seviye_ic", "seviye_pencere_disi",
                                 "ic_kadraj_disi"}
    assert meta["olay"]["ic_swing"] == 0 and meta["olay"]["seviye"] == 0
    assert "yapı:" not in " ".join(meta["metin"]["lejant"])


def test_kadraj_disi_ic_olay_cizilmez_sayilir(tmp_path):
    ms = _ms_ic(ic=[_swing(160, 52.2, kimlik=11)],
                olaylar=[_olay(210, 5000.0, kapsam="INTERNAL", kimlik=14)])   # fiyat aralığının çok dışı
    _, meta = grafik.ciz(_goruntu_yapi(ms), "4h", {"cikti": str(tmp_path / "kd.png")})
    assert meta["olay"]["ic_bos_choc"] == 0 and meta["olay"]["ic_kadraj_disi"] == 1
    assert meta["olay"]["ic_swing"] == 1                                 # swing her zaman görünür


def test_sade_modda_ic_yapi_ve_roller_cizilmez(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAFIK_SADE", "1")
    _, meta = grafik.ciz(_goruntu_yapi(_ms_tam()), "4h", {"cikti": str(tmp_path / "sade.png")})
    o = meta["olay"]
    assert o["swing"] == 0 and o["ic_swing"] == 0 and o["ic_bos_choc"] == 0 and o["seviye"] == 0
    assert "yapı:" not in " ".join(meta["metin"]["lejant"])


def test_ic_yapi_kill_switch_uctan_uca(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAFIK_IC_YAPI", "0")
    _, meta = grafik.ciz(_goruntu_yapi(_ms_tam()), "4h", {"cikti": str(tmp_path / "kapali.png")})
    o = meta["olay"]
    assert o["ic_swing"] == 0 and o["ic_bos_choc"] == 0 and o["ic_kapak"] == {}
    assert o["swing"] == 2 and o["seviye"] == 2                    # dış yapı + dış roller sürer
    lejant = " ".join(meta["metin"]["lejant"])
    assert "i = iç yapı" not in lejant and "PH/PL korunan" in lejant


# ------------------------------------------------------- temas dairesi kaldırıldı (§38)


def test_temas_dairesi_cizilmez_ama_sayi_baslikta_kalir(tmp_path):
    g = grafik.anlik_goruntu(_cift(start_bar=200, upper_now=54.0, lower_now=47.0), "1h",
                             _cerceve(240, yon=1.2), simdi=ZAMAN, alarm_bar=239)
    _, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / "temas.png")})
    assert len(meta["temas"]) > 24 and meta["temas_isaret"] == []      # daire listesi boş
    baslik = " ".join(meta["metin"]["satirlar"])
    assert f"bant teması {len(meta['temas'])}" in baslik               # sayı hâlâ yazılır
    lejant = " ".join(meta["metin"]["lejant"])
    assert "○" not in lejant and "bant teması" not in lejant           # lejantta daire maddesi yok
    assert not any("temas işareti" in d for d in meta["metin"]["dipnotlar"] + meta["metin"]["notlar"])


def test_temas_icin_artik_hicbir_isaret_sabiti_yok():
    assert "temas_radyus" not in grafik.SABITLER and "temas_isaret_maks" not in grafik.SABITLER


def test_bant_verisi_yoksa_uyari_temas_sayilmadi_der():
    g = grafik.anlik_goruntu({"pattern_name": "X", "state": "KIRILIM_TEYITLI", "start_bar": 200,
                              "end_bar": 239, "apex_bar": 230, "upper_now": None,
                              "lower_now": None}, "1h", _cerceve(240), simdi=ZAMAN, alarm_bar=239)
    assert any("bant verisi yok: temas sayılmadı" in u for u in g["uyarilar"])
    assert not any("işaretlenmedi" in u for u in g["uyarilar"])
