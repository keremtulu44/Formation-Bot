# -*- coding: utf-8 -*-
"""GÖRSEL-5 Paket 1: doluluk cetveli, `%50` orta çizgisi, kutu künyesi, `qNN` kalktı.

Kullanıcı kararları (2026-10-15, ikinci tur):
  * ölçüm: çizilen 56 kutu etiketinin 21'i açıklamasız `qNN`, 23'ü çıplaktı →
    `qNN` TAMAMEN kaldırıldı; doluluk bilgisi hem SAYI (%X) hem GEOMETRİ
    (dolan kısım koyu bant + sınır çizgisi) olarak gösterilir.
  * FVG'ye `%50` orta çizgisi (consequent encroachment) eklendi.
  * Kutu künyesi: oluşum tarihi (`16 Eyl`) ikinci satır — yalnız sığdığında.

Dolgu yönü MOTORDAN doğrulandı; testler o yönü çakıyor (uydurma geometri yok).
"""

from __future__ import annotations

import pytest

import grafik


def _zone_kayit(tip="ob", yon=1, alt=100.0, ust=110.0, x0=10, x1=40, **ek):
    kayit = {"tip": tip, "yon": yon, "alt": alt, "ust": ust, "x0": x0, "x1": x1,
             "durum": "ACTIVE", "vurgu": "alt" if yon >= 0 else "ust"}
    kayit.update(ek)
    return kayit


def _eksen(n=60, alt=90.0, ust=120.0):
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10.8, 8.1), dpi=100)
    ax = fig.add_axes([0.075, 0.1, 0.8, 0.8])
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_ylim(alt, ust)
    return fig, ax


# --------------------------------------------------------------- etiket metni


def test_qnn_etiketi_kalkti_doluluk_kaldi():
    """`qNN` artık ÜRETİLMEZ; doluluk varsa `%X`, yoksa yalnız tip+yön."""
    assert grafik._zone_metni(_zone_kayit(tip="fvg", skor=95)) == "FVG↑"   # eski: 'FVG↑ q95'
    assert grafik._zone_metni(_zone_kayit(tip="fvg", doluluk=0.38)) == "FVG↑ %38"
    assert grafik._zone_metni(_zone_kayit(tip="ob", yon=-1, doluluk=0.7)) == "OB↓ %70"
    assert grafik._zone_metni(_zone_kayit(tip="eng", skor=88)) == "ENG↑"
    assert "q" not in grafik._zone_metni(_zone_kayit(tip="fvg", skor=100))


# ------------------------------------------------------------- dolgu geometrisi


def _dolgu_bandi(ax):
    """DOLAN kısmı bulur — GÖRSEL-8: dolan kısım AÇIK tonda çizilir.

    Kullanıcı kararı: "koyu taraf = doldurulmamış, açık taraf = dolan kısım".
    Kutu çerçevesi dolgusuz bir dikdörtgendir (`facecolor="none"`); ölçüme
    yalnız DOLGULU dikdörtgenler girer, en düşük alfa = dolan bant.
    """
    from matplotlib.patches import Rectangle

    kutular = [p for p in ax.patches
               if isinstance(p, Rectangle) and p.get_facecolor()[3] > 0]
    alpha = [(p.get_alpha() or 0.0, p.get_xy(), p.get_height()) for p in kutular]
    if len(alpha) < 2:
        return None
    return min(alpha, key=lambda x: x[0])          # en AÇIK olan = dolan kısım


def test_boga_kutusunda_dolgu_ustten_asagi():
    """Boğa OB: motor `fill = (top - boundary)/height` → dolan kısım ÜSTTE."""
    fig, ax = _eksen()
    grafik._zone_ciz(ax, {"cizilen": [_zone_kayit(doluluk=0.30)]}, 60, (90.0, 120.0), [])
    band = _dolgu_bandi(ax)
    assert band is not None
    _, (_, y0), yuk = band
    assert abs((y0 + yuk) - 110.0) < 1e-6          # üst kenar kutunun tepesinde
    assert abs(y0 - 107.0) < 1e-6                  # %30 dolgu aşağı doğru


def test_ayi_kutusunda_dolgu_alttan_yukari():
    fig, ax = _eksen()
    grafik._zone_ciz(ax, {"cizilen": [_zone_kayit(yon=-1, doluluk=0.25)]}, 60,
                     (90.0, 120.0), [])
    band = _dolgu_bandi(ax)
    assert band is not None
    _, (_, y0), _ = band
    assert abs(y0 - 100.0) < 1e-6                  # alt kenar kutunun dibinde
    assert y0 + band[2] <= 110.0 + 1e-9


def test_doluluk_sifir_veya_tam_ise_ek_bant_cizilmez():
    """%0 / %100 uçları: bant eklenmez (kutu zaten o hâli anlatıyor)."""
    for deger in (0.0, 0.005, 1.0, 0.99):
        fig, ax = _eksen()
        grafik._zone_ciz(ax, {"cizilen": [_zone_kayit(doluluk=deger)]}, 60,
                         (90.0, 120.0), [])
        from matplotlib.patches import Rectangle
        dolgulu = [p for p in ax.patches
                   if isinstance(p, Rectangle) and p.get_facecolor()[3] > 0]
        assert len(dolgulu) == 1, "uç değerde kutu tek parça koyu kalmalı"


def test_fvg_orta_cizgisi_yalniz_yeterince_yuksek_kutuda():
    """`%50` çizgisi okunabilir yükseklikteki FVG'de var, ince FVG'de yok."""
    fig, ax = _eksen()
    grafik._zone_ciz(ax, {"cizilen": [_zone_kayit(tip="fvg", alt=100.0, ust=106.0)]},
                     60, (90.0, 120.0), [])
    orta = [ln for ln in ax.get_lines()
            if len(ln.get_ydata()) == 2 and abs(ln.get_ydata()[0] - 103.0) < 1e-9]
    # Not: matplotlib `(0,(1,2))` desenini `--`e normalize ediyor; ayırt edici
    # özellik kalınlık/alfa (0,6 pt · α 0,4) — kutu kenarı 0,8 pt koyu kalır.
    assert len(orta) == 1
    assert orta[0].get_linewidth() == 0.6 and orta[0].get_alpha() == 0.4

    # İnce FVG: kutu ~4 px → orta çizgisi gürültü olur, çizilmez.
    fig2, ax2 = _eksen()
    grafik._zone_ciz(ax2, {"cizilen": [_zone_kayit(tip="fvg", alt=100.0, ust=100.2)]},
                     60, (90.0, 120.0), [])
    esik_alt, esik_ust = 100.0, 100.2
    assert not [ln for ln in ax2.get_lines()
                if len(ln.get_ydata()) == 2
                and esik_alt < float(ln.get_ydata()[0]) < esik_ust]


# --------------------------------------------------------------------- künye


def test_kunye_olusum_tarihini_yazar():
    kayit = _zone_kayit(zaman="2026-09-16T13:00:00+03:00")
    assert grafik._zone_kunye(kayit) == "16 Eyl"
    assert grafik._zone_kunye(_zone_kayit()) == ""          # tarih yoksa satır yok
    assert grafik._zone_kunye(_zone_kayit(zaman="bozuk")) == ""


def test_kunye_ikinci_satir_sigmazsa_tek_satira_duser():
    """İnce kutuda iki satır sığmaz → metin tek satır kalır (taşma yok)."""
    fig, ax = _eksen()
    ince = _zone_kayit(alt=105.0, ust=105.35, doluluk=0.2,
                       zaman="2026-09-16T13:00:00+03:00")
    assert grafik._kutu_yazisi_sigar(ax, ince, 10, 40, 60, (90.0, 120.0), "OB↑ %20") is False
    fig2, ax2 = _eksen()
    kalin = _zone_kayit(alt=100.0, ust=106.0, doluluk=0.2,
                        zaman="2026-09-16T13:00:00+03:00")
    assert grafik._kutu_yazisi_sigar(ax2, kalin, 10, 40, 60, (90.0, 120.0),
                                     "OB↑ %20\n16 Eyl") is True


def test_cok_satirli_metin_kutunun_icinde_kalir():
    fig, ax = _eksen()
    kayit = _zone_kayit(alt=100.0, ust=107.0, zaman="2026-09-16T13:00:00+03:00")
    grafik._zone_ciz(ax, {"cizilen": [kayit]}, 60, (90.0, 120.0), [])
    yazilar = [t for t in ax.texts if str(t.get_gid() or "") == "kutu-ici"]
    assert len(yazilar) == 1 and "\n" in str(yazilar[0].get_text())


# ------------------------------------------------------------- meta sayaçları


def test_meta_yeni_sayaclari_her_durumda_tasir():
    bos = grafik._zone_meta(None)
    assert {"dolgu", "orta", "kunye"} <= set(bos)
    assert bos["dolgu"] == 0 and bos["orta"] == 0 and bos["kunye"] == 0
    dolu = grafik._zone_meta({"cizilen": [], "dolgu": 2, "orta": 3, "kunye": 1})
    assert (dolu["dolgu"], dolu["orta"], dolu["kunye"]) == (2, 3, 1)


@pytest.mark.parametrize("hisse", ["GARAN", "TUPRS"])
def test_kare_uret_sayaclari_ve_cakisma_olcumu(hisse):
    import grafik_uret

    sonuc = grafik_uret.kare_uret(hisse, "4h", veri_dizin="bot_data", zone=True,
                                  mum=140, cikti=f"/tmp/kare/_p1_{hisse}.png")
    z = sonuc["meta"]["zone"]
    assert z["dolgu"] <= z["cizilen"] and z["orta"] <= z["cizilen"]
    assert grafik.SABITLER["sag_serit_px"] > 0
    assert sonuc["meta"]["kalite"]["mum_cakisan"] == 0


# ============================ Paket 2: okunurluk =============================
# Ölçüm: kritik dışı BOS/CHoCH çizgileri aynı stil/alfada olduğu için üst üste
# iki soluk çizgi ayırt edilemiyordu; şeritte aynı seviyedeki kutu çipleri
# yığılıyordu (TCELL'de 3 kutu + son fiyat).


def _olay_goruntusu(olaylar):
    from datetime import datetime, timedelta, timezone

    ist = timezone(timedelta(hours=3))
    return {
        "sembol": "TEST", "tf": "1h", "tf_kisa": "1s", "acilis": [100.0] * 60,
        "yuksek": [101.0] * 60, "dusuk": [99.0] * 60, "kapanis": [100.5] * 60,
        "zamanlar": [datetime(2026, 9, 1, 9, 30, tzinfo=ist) + timedelta(hours=i)
                     for i in range(60)],
        "formasyon": {}, "alarm": {}, "zone": {}, "temas": [], "isaretler": [], "serit": {},
        "olay": {"swinglar": [], "olaylar": olaylar, "kritik": {}},
    }


def test_choch_noktali_bos_kesikli():
    """İki olay türü stil olarak ayrışır (arşivde `:` ve `--` olarak ölçülür)."""
    fig, ax = _eksen()
    goruntu = _olay_goruntusu([
        {"bar": 20, "seviye": 104.0, "yon": "ust", "tur": "BOS"},
        {"bar": 35, "seviye": 102.0, "yon": "alt", "tur": "CHoCH"},
    ])
    grafik._olay_ciz(ax, goruntu, 60, [])
    stil = {}
    for ln in ax.get_lines():
        y = ln.get_ydata()
        if len(y) == 2 and y[0] == y[1] and abs(ln.get_linewidth() - 0.9) < 0.01:
            stil[float(y[0])] = str(ln.get_linestyle())
    assert stil[104.0] == "--"      # BOS kesikli
    assert stil[102.0] == ":"       # CHoCH noktalı


def test_olay_cizgisi_yasla_soler():
    """En yeni olay en koyu; eski olaylar daha soluk (aynı stil içinde kademe)."""
    fig, ax = _eksen()
    goruntu = _olay_goruntusu([
        {"bar": 10, "seviye": 106.0, "yon": "ust", "tur": "BOS"},
        {"bar": 25, "seviye": 104.0, "yon": "alt", "tur": "BOS"},
        {"bar": 45, "seviye": 102.0, "yon": "ust", "tur": "BOS"},
    ])
    grafik._olay_ciz(ax, goruntu, 60, [])
    alfa = {float(ln.get_ydata()[0]): float(ln.get_alpha() or 1.0)
            for ln in ax.get_lines()
            if len(ln.get_ydata()) == 2 and ln.get_ydata()[0] == ln.get_ydata()[1]
            and abs(ln.get_linewidth() - 0.9) < 0.01}
    assert alfa[102.0] > alfa[104.0] > alfa[106.0]     # yeni → eski soluklaşır
    assert alfa[106.0] >= 0.38                          # taban okunur kalır


def test_ayni_seviyedeki_kutu_cipleri_birlesir():
    fig, ax = _eksen()
    adaylar = [
        {"kaynak": "zone", "x": 59.6, "y": 105.0, "metin": "OB↑", "renk": "#2bb673",
         "sabit": False, "oncelik": 2, "bg": None, "yeni": 50.0},
        {"kaynak": "zone", "x": 59.6, "y": 105.2, "metin": "FVG↓", "renk": "#3f9dec",
         "sabit": False, "oncelik": 2, "bg": None, "yeni": 48.0},
    ]
    ozet = grafik._sag_ciz(ax, fig, adaylar, 60, (90.0, 120.0))
    metinler = [str(t.get_text()) for t in ax.texts if t.get_bbox_patch() is not None]
    assert len(metinler) == 1, metinler              # tek çip
    assert " · " in metinler[0] and "OB↑" in metinler[0] and "FVG↓" in metinler[0]
    assert ozet["birlesik"] == 1 and ozet["birlesen_kutu"] == 1


def test_kritik_ve_son_fiyat_birlesmez():
    """Anlamı ayrı olan çipler birleşmez: `kritik X` ve son fiyat kendi çipinde."""
    fig, ax = _eksen()
    adaylar = [
        {"kaynak": "olay", "x": 59.6, "y": 105.0, "metin": "kritik 105,00", "renk": "#f0885c",
         "sabit": False, "oncelik": 5, "bg": None, "yeni": 50.0},
        {"kaynak": "zone", "x": 59.6, "y": 105.1, "metin": "OB↑", "renk": "#2bb673",
         "sabit": False, "oncelik": 2, "bg": None, "yeni": 50.0},
        {"kaynak": "son", "x": 59.6, "y": 105.15, "metin": "105,05", "renk": "#31b184",
         "sabit": True, "oncelik": 9, "bg": "#134237", "yeni": 60.0},
    ]
    ozet = grafik._sag_ciz(ax, fig, adaylar, 60, (90.0, 120.0))
    metinler = sorted(str(t.get_text()) for t in ax.texts if t.get_bbox_patch() is not None)
    assert metinler == ["105,05", "OB↑", "kritik 105,00"]      # birleşme YOK
    assert ozet["birlesik"] == 0


def test_uc_kutu_birlesince_dordu_dolmaz():
    """Üç kutu çipi bir çipte toplanır; kılavuz çizgisi tek kalır."""
    fig, ax = _eksen()
    adaylar = [{"kaynak": "zone", "x": 59.6, "y": 105.0 + 0.05 * i, "metin": f"OB↑ {i}",
                "renk": "#2bb673", "sabit": False, "oncelik": 2, "bg": None,
                "yeni": 50.0 - i} for i in range(3)]
    ozet = grafik._sag_ciz(ax, fig, adaylar, 60, (90.0, 120.0))
    metinler = [str(t.get_text()) for t in ax.texts if t.get_bbox_patch() is not None]
    assert len(metinler) == 1
    assert ozet["birlesen_kutu"] == 2


def test_lejant_bos_ve_choch_ayri_yazar():
    goruntu = {"olay": {"olaylar": [{"tur": "BOS"}, {"tur": "CHoCH"}]}}
    oge = grafik._lejant(goruntu, False)
    assert "┄ BOS" in oge and "┈ CHoCH" in oge
    # Yalnız BOS varsa CHoCH maddesi ÇIKMAZ (çizilmeyen şey lejantta yazılmaz).
    oge2 = grafik._lejant({"olay": {"olaylar": [{"tur": "BOS"}]}}, False)
    assert "┈ CHoCH" not in oge2


# ========================= Paket 3: okuma modları ============================
# `--sade` (mum + formasyon + kritik/son fiyat), `--renk-korugu` (mavi-turuncu),
# `--buyuk-yazi` (×1,25). Mod kapsamı THREAD-LOCAL: tarama ile görsel gönderim
# işçisi aynı anda çizerse birbirinin modunu görmemeli.


def test_renk_korugu_kapsami_mum_renklerini_degistirir():
    normal = grafik.PALET["mum_yukselen"]
    with grafik._mod_kapsami({"renk_korugu": True}):
        assert grafik.PALET["mum_yukselen"] == "#4da3ff"
        assert grafik.PALET["mum_dusen"] == "#f5a05a"
        assert grafik.PALET["ob"] == "#2bb673"        # katman renkleri değişmez
    assert grafik.PALET["mum_yukselen"] == normal     # kapsam çıkışında geri döner


def test_buyuk_yazi_yalniz_puntolari_buyutur():
    with grafik._mod_kapsami({"yazi_olcek": 1.25}):
        assert grafik.SABITLER["eksen_pt"] == pytest.approx(9.0 * 1.25)
        assert grafik.SABITLER["zone_yazi_pt"] == pytest.approx(8.0 * 1.25)
        assert grafik.SABITLER["dpi"] == 100                        # geometri sabit
        assert grafik.SABITLER["zone_kalinlik"]["vurgu"] == 1.3     # kalınlık sabit


def test_mod_kapsami_thread_izole():
    """Ana thread'in modu işçi thread'e SIZMAZ (paralel çizim güvenliği)."""
    import threading

    sonuc = {}

    def isci():
        with grafik._mod_kapsami({"renk_korugu": True}):
            sonuc["isci"] = grafik.PALET["mum_yukselen"]
        sonuc["isci_sonra"] = grafik.PALET["mum_yukselen"]

    with grafik._mod_kapsami({"renk_korugu": False}):
        t = threading.Thread(target=isci)
        t.start()
        t.join()
        assert grafik.PALET["mum_yukselen"] == "#31b184"     # ana thread etkilenmez
    assert sonuc["isci"] == "#4da3ff"
    assert sonuc["isci_sonra"] == "#31b184"


def test_sade_mod_katmanlari_kapatir_ama_veri_kusuru_yazmaz():
    import grafik_uret

    d = grafik_uret.kare_uret("GARAN", "4h", veri_dizin="bot_data", zone=True, mum=140,
                              sade=True, cikti="/tmp/kare/_p3_sade.png")
    meta = d["meta"]
    assert meta["mod"]["sade"] is True
    assert meta["zone"]["cizilen"] == 0 and meta["zone"]["etiket_ic"] == 0
    # Sessiz kayıp yok: kaç kutunun mod nedeniyle çizilmediği yazılır.
    assert meta["mod"]["atlanan_kutu"] >= 1
    assert "zone" not in meta["eksik_katmanlar"]         # bilinçli mod, kusur değil
    assert meta["metin"]["lejant"] == [
        "sade mod: yalnız mum + formasyon bandı + kritik/son fiyat"]
    assert meta["sag"]["yerlesen"] <= 2                  # yalnız kritik + son fiyat


def test_normal_mod_sade_ile_ayni_veriyi_korur():
    """Sade mod yalnız ÇİZİM kapsamını kapatır; kare verisi değişmez."""
    import grafik_uret

    normal = grafik_uret.kare_uret("GARAN", "4h", veri_dizin="bot_data", zone=True,
                                   mum=140, cikti="/tmp/kare/_p3_normal.png")
    sade = grafik_uret.kare_uret("GARAN", "4h", veri_dizin="bot_data", zone=True,
                                 mum=140, sade=True, cikti="/tmp/kare/_p3_sade2.png")
    assert normal["meta"]["mum_sayisi"] == sade["meta"]["mum_sayisi"]
    assert normal["meta"]["mod"]["sade"] is False and sade["meta"]["mod"]["sade"] is True


def test_env_anahtarlari_cli_bayragini_ezmez(monkeypatch):
    """`GRAFIK_SADE=1` env ile açılır; CLI bayrağı verilirse yine açık kalır."""
    import grafik_uret

    monkeypatch.setenv("GRAFIK_SADE", "1")
    d = grafik_uret.kare_uret("GARAN", "4h", veri_dizin="bot_data", zone=True, mum=140,
                              cikti="/tmp/kare/_p3_env.png")
    assert d["meta"]["mod"]["sade"] is True
    monkeypatch.delenv("GRAFIK_SADE")
    monkeypatch.setenv("GRAFIK_YAZI", "1,5")             # virgüllü ondalık da okunur
    d2 = grafik_uret.kare_uret("GARAN", "4h", veri_dizin="bot_data", zone=True, mum=140,
                               cikti="/tmp/kare/_p3_env2.png")
    assert d2["meta"]["mod"]["yazi_olcek"] == pytest.approx(1.5)


# ------------------- modlar: lejant dürüstlüğü + taşma kapısı -------------------


def test_renk_korugu_modunda_lejant_renk_adi_degisir():
    """Lejant çizileni anlatır: mavi/turuncu modda "yeşil/kırmızı" yazmaz."""
    oge = grafik._lejant({"zone": {"cizilen": []}}, False)
    assert any("yeşil boş" in x for x in oge)
    with grafik._mod_kapsami({"renk_korugu": True}):
        oge2 = grafik._lejant({"zone": {"cizilen": []}}, False)
    assert any("mavi boş" in x for x in oge2)
    assert not any("yeşil" in x for x in oge2)


@pytest.mark.parametrize("buyuk", [False, True])
def test_figur_yazilari_tasmaz_ve_cakismaz(buyuk):
    """Alt/üst blok yazıları kare içinde kalır; satırlar üst üste binmez."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import grafik_uret

    kapat_sonra = []
    gercek_close = plt.close

    def sahte_close(*a, **k):        # figürü ölçüm için açık tut
        kapat_sonra.append((a, k))

    plt.close = sahte_close
    try:
        grafik_uret.kare_uret("GARAN", "4h", veri_dizin="bot_data", zone=True, mum=140,
                              buyuk_yazi=buyuk, cikti="/tmp/kare/_p3_tasma.png")
        fig = plt.figure(plt.get_fignums()[-1])
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        w, h = fig.canvas.get_width_height()
        kutular = []
        for t in fig.texts:
            bb = t.get_window_extent(r)
            assert bb.x0 >= -0.5 and bb.x1 <= w + 0.5, str(t.get_text())[:32]
            assert bb.y0 >= -0.5 and bb.y1 <= h + 0.5, str(t.get_text())[:32]
            kutular.append((str(t.get_text())[:20], bb))
        for i, (a1, b1) in enumerate(kutular):
            for a2, b2 in kutular[i + 1:]:
                assert not (b1.x0 < b2.x1 and b1.x1 > b2.x0
                            and b1.y0 < b2.y1 and b1.y1 > b2.y0), (a1, a2)
    finally:
        plt.close = gercek_close
        for fignum in plt.get_fignums():
            plt.figure(fignum).clear()
        plt.close("all")


# ============ GÖRSEL-6: PH/PL seviye cetveli + kutu dolgusu belirginliği ========


def test_ph_pl_sag_seritte_cetvel_olarak_durur():
    """PH/PL ROLÜ şerit cetveline fiyatıyla gider; grafikte okla kısa etiket kalır (§38)."""
    fig, ax = _eksen()
    goruntu = {
        "sembol": "T", "tf": "1h", "tf_kisa": "1s", "acilis": [100.0] * 60,
        "yuksek": [101.0] * 60, "dusuk": [99.0] * 60, "kapanis": [100.5] * 60,
        "formasyon": {}, "alarm": {}, "zone": {}, "temas": [], "isaretler": [], "serit": {},
        "olay": {"swinglar": [
            {"bar": 10, "fiyat": 104.5, "yon": "ust", "sinif": "LH", "seviye": "PH",
             "seviye_kapsam": "dis", "durum": "teyitli"},
            {"bar": 20, "fiyat": 96.25, "yon": "alt", "sinif": "HL", "seviye": "PL",
             "seviye_kapsam": "dis", "durum": "teyitli"},
            {"bar": 30, "fiyat": 103.0, "yon": "ust", "sinif": "HL", "durum": "teyitli"},
        ], "olaylar": [], "kritik": {}},
    }
    sag: list = []
    ozet = grafik._olay_ciz(ax, goruntu, 60, sag)
    assert ozet["phpl_serit"] == 2
    assert sorted(a["metin"] for a in sag) == ["PH 104,50", "PL 96,25"]
    # §38: çizgiyi katman kendisi çizer (sağa kesikli); çip ayrıca kılavuz çizgisi taşımaz
    assert all("kilavuz_stil" not in a for a in sag)
    yazilar = [str(t.get_text()) for t in ax.texts if str(t.get_text()).strip()]
    assert {"PH", "PL", "HL"} <= set(yazilar)         # okla kısa etiket (rol adı)
    assert not any(y.startswith(("PH ", "PL ")) for y in yazilar)   # fiyat grafikte yazılmaz


def test_ph_pl_son_fiyatla_ayni_bantta_ise_atlanir_ve_sayilir():
    """Son fiyat aynı seviyeyi söylüyorsa PH/PL çipi tekrar yazılmaz (sayılır)."""
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10.8, 8.1), dpi=100)
    ax = fig.add_axes([0.075, 0.1, 0.8, 0.8])
    aralik = (90.0, 120.0)
    ax.set_ylim(*aralik)
    adaylar = [
        {"kaynak": "swing", "x": 59.6, "y": 100.0, "metin": "PH 100,00", "renk": "#8ba0b4",
         "sabit": False, "oncelik": 4, "bg": None, "yeni": 40.0},
        {"kaynak": "son", "x": 59.6, "y": 100.0, "metin": "100,00", "renk": "#101418",
         "bg": "#31b184", "sabit": True, "oncelik": 9},
    ]
    ozet = grafik._sag_ciz(ax, fig, adaylar, 60, aralik)
    metinler = [str(t.get_text()) for t in ax.texts if t.get_bbox_patch() is not None]
    assert metinler == ["100,00"]                 # PH tekrarı yok
    assert ozet["atlanan_kaynak"].get("swing") == 1 and ozet["atlanan"] == 1


def test_ph_pl_son_fiyattan_uzaksa_ikisi_de_kalir():
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10.8, 8.1), dpi=100)
    ax = fig.add_axes([0.075, 0.1, 0.8, 0.8])
    aralik = (90.0, 120.0)
    ax.set_ylim(*aralik)
    adaylar = [
        {"kaynak": "swing", "x": 59.6, "y": 96.0, "metin": "PL 96,00", "renk": "#8ba0b4",
         "sabit": False, "oncelik": 4, "bg": None, "yeni": 40.0},
        {"kaynak": "son", "x": 59.6, "y": 110.0, "metin": "110,00", "renk": "#101418",
         "bg": "#31b184", "sabit": True, "oncelik": 9},
    ]
    ozet = grafik._sag_ciz(ax, fig, adaylar, 60, aralik)
    metinler = sorted(str(t.get_text()) for t in ax.texts if t.get_bbox_patch() is not None)
    assert metinler == ["110,00", "PL 96,00"]
    assert ozet["atlanan"] == 0


def test_kutu_dolgusu_belirginlesti_ama_neon_degil():
    """GÖRSEL-6 sayı sözleşmesi korunur: 'şeffaflığı azalt ama abartma'."""
    d = grafik.SABITLER["doldurma"]
    assert 0.14 <= float(d["ob"]) <= 0.20          # doldurulmamış alanın tonu
    assert 0.13 <= float(d["fvg"]) <= 0.20
    assert float(grafik.SABITLER["zone_kalinlik"]["kenar"]) == 0.9
    assert float(grafik.SABITLER["zone_kalinlik"]["vurgu"]) == 1.3   # vurgu değişmedi


def test_dolan_kisim_acik_doldurulmamis_kalan_koyu():
    """GÖRSEL-8 (kullanıcı): "koyu taraf = doldurulmamış, açık taraf = DOLAN".

    Ölçüm: aynı kutuda iki dolgu dikdörtgeni vardır; DOLAN bandın alfası kalan
    alandan KÜÇÜK olmalı (daha açık ton), rengi (hue) aynı kalmalı ve bant
    tabanın altına düşmemeli (görünmez olmasın).
    """
    from matplotlib.patches import Rectangle

    d = grafik.SABITLER["doldurma"]
    # Kullanıcı: "arttır biraz görünsün ama soluk olsun dolmayana göre" → dolan bant
    # kalan alanın YARISI kadar koyu: görünür (≥ 0,35) ama soluk (≤ 0,70).
    assert 0.35 <= float(d["dolan_orani"]) <= 0.70
    assert 0.02 <= float(d["dolan_taban"]) < float(d["ob"]) / 2.0
    fig, ax = _eksen()
    grafik._zone_ciz(ax, {"cizilen": [_zone_kayit(doluluk=0.30)]}, 60, (90.0, 120.0), [])
    dolgulu = [p for p in ax.patches
               if isinstance(p, Rectangle) and p.get_facecolor()[3] > 0]
    assert len(dolgulu) == 2, "dolan + kalan: iki ayrı ton"
    alfa = sorted(round(float(p.get_alpha()), 6) for p in dolgulu)
    acik, koyu = alfa[0], alfa[1]
    assert acik < koyu, "dolan kısım DAHA AÇIK olmalı (kullanıcı kararı)"
    assert acik >= float(d["dolan_taban"]) - 1e-9
    assert koyu <= 0.20 + 1e-9, "neon yok: kalan alan yarı saydam kalır"
    # hue korunur: iki dikdörtgen de kutunun kendi rengi
    renkler = {tuple(round(c, 4) for c in p.get_facecolor()[:3]) for p in dolgulu}
    assert len(renkler) == 1
    # doluluk sınırı çizgisi (cetvel) duruyor mu?
    sinirlar = [ln for ln in ax.get_lines()
                if len(ln.get_ydata()) == 2 and abs(ln.get_ydata()[0] - 107.0) < 1e-6]
    assert sinirlar and abs(float(sinirlar[0].get_alpha()) - 0.9) < 1e-6


def test_kutu_dolgusu_kutu_ici_yazi_okunurlugunu_bozmaz():
    """Dolgu koyulaştı ama kutu içi yazı/kontur aynen duruyor."""
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10.8, 8.1), dpi=100)
    ax = fig.add_axes([0.075, 0.1, 0.8, 0.8])
    ax.set_xlim(-0.6, 59.6)
    ax.set_ylim(90.0, 120.0)
    kayit = {"tip": "ob", "yon": 1, "alt": 100.0, "ust": 106.0, "x0": 10, "x1": 40,
             "durum": "ACTIVE", "vurgu": "alt", "doluluk": 0.31, "zaman": None}
    grafik._zone_ciz(ax, {"cizilen": [kayit]}, 60, (90.0, 120.0), [])
    yazilar = [t for t in ax.texts if str(t.get_gid() or "") == "kutu-ici"]
    assert len(yazilar) == 1 and "%31" in str(yazilar[0].get_text())
    assert yazilar[0].get_path_effects()            # koyu kontur korunuyor
