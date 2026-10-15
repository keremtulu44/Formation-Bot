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
    """Kutu dolgusundan DAHA KOYU ikinci dikdörtgeni (dolan kısım) bulur."""
    from matplotlib.patches import Rectangle

    kutular = [p for p in ax.patches if isinstance(p, Rectangle)]
    alpha = [(p.get_alpha() or 0.0, p.get_xy(), p.get_height()) for p in kutular]
    if len(alpha) < 2:
        return None
    return max(alpha, key=lambda x: x[0])          # en opak olan = dolan kısım


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
        assert len([p for p in ax.patches if isinstance(p, Rectangle)]) == 1


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
