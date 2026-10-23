# -*- coding: utf-8 -*-
"""GÖRSEL-9 (2026-10-23): kadraj, kırılım marjı ve dar kare yerleşimi.

Kullanıcı: *"grafik çizerken bazı hatalar var; çizimi kısa tutuyor, formasyonda
kırılmanın ne kadar olduğunu göremiyoruz"*. Bu dosya düzeltmelerin ÖLÇÜLEBİLİR
sözlerini kilitler:

  1. Kadraj formasyonu kesmez: üst sınır 180 (85 değil), tavan piksel bütçesinden.
  2. Bant doğrusu y-aralığını ele geçirmez: mumlar karenin çoğunu kaplar,
     kadraj dışına taşan bant parçası ÇİZİLMEZ ve sayılır (sessiz kayıp yok).
  3. Kırılım marjı karede ölçü olarak durur (`meta["cizgiler"]["kirilim"]`).
  4. Başlıkta kart ile çelişen "bant teması (toplam)" sayısı yerine motorun
     `upper_touches`/`lower_touches` alanları yazılır.
  5. RVOL rozet aralığı pikselden gelir (dar karede çipler üst üste binmez).
  6. X tick yoğunluğu eksen genişliğinden gelir (mobilde tarihler binmez).
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
from matplotlib.figure import Figure

import grafik
from patterns.mathutil import f_line_price


# ------------------------------------------------------------------ yardımcılar

def _cerceve(n: int, taban: float = 100.0, salinim: float = 0.6):
    """Basit salınan seri: mum aralığı ~`salinim`, bant ondan çok uzakta."""
    kapanis, acilis, yuksek, dusuk, hacim = [], [], [], [], []
    for i in range(n):
        fiyat = taban + salinim * math.sin(i / 5.0)
        acilis.append(round(fiyat - 0.05, 3))
        kapanis.append(round(fiyat, 3))
        yuksek.append(round(fiyat + salinim * 0.4, 3))
        dusuk.append(round(fiyat - salinim * 0.4, 3))
        hacim.append(1_000_000.0)
    return {"zaman": [SimpleNamespace() for _ in range(n)], "acilis": acilis,
            "yuksek": yuksek, "dusuk": dusuk, "kapanis": kapanis, "hacim": hacim}


def _eksen(n: int, ylim=(90.0, 110.0)):
    fig = Figure(figsize=(10.8, 8.1), dpi=100)
    ax = fig.add_axes([0.075, 0.1, 0.8, 0.8])
    ax.set_xlim(-0.6, n - 0.4 + 5)
    ax.set_ylim(*ylim)
    return ax


def _bant_cizgileri(ax):
    kalin = grafik.SABITLER["cizgi_kalinlik"]["formasyon"]
    return [ln for ln in ax.lines
            if abs(ln.get_linewidth() - kalin) < 1e-9
            and ln.get_linestyle() in ("-", "solid")]


# --------------------------------------------------- 1. kadraj formasyonu kesmez

def test_formasyon_kadraj_tavani_180_ve_piksel_butcesi_icinde():
    """85 → 180: 90-100 barlık formasyonun kırılım tabanı artık kesilmiyor."""
    assert int(grafik.SABITLER["kadraj_formasyon_maks"]) == 180
    # piksel bütçesi: 1440 / 6 = 240 mum; okunurluk için 180'de durulur
    assert int(grafik.SABITLER["genislik_tavan"]) / float(grafik.SABITLER["bar_px"]) == 240
    # 310 barlık formasyon → istenen 320 > tavan 180 → tavan kadar pencere,
    # sağ (güncel) taraf korunur ve kırpma `kirpildi` ile BİLDİRİLİR
    sol, sag, kirpildi = grafik._kadrajla(400, 100, None, tf="1h")
    assert (sag - sol, kirpildi) == (180, True)
    assert sag == 400
    # 110 barlık formasyon (eski tavanın altında) artık TAM görünür
    sol, sag, kirpildi = grafik._kadrajla(400, 300, None, tf="1h")
    assert (sag - sol, kirpildi) == (110, False)
    # 93 barlık formasyon (gerçek karelerin çoğu) ARTIK kırpılmaz
    sol, sag, kirpildi = grafik._kadrajla(360, 267, None, tf="1h")
    assert kirpildi is False and sag - sol == 360 - 267 + 10


# --------------------------------------- 2. bant doğrusu y-aralığını ele geçirmez

def test_gorunur_parcalar_aralik_disi_noktalari_atlar():
    xs = list(range(6))
    ys = [10.0, 5.0, 95.0, 100.0, 200.0, 101.0]
    parcalar = grafik._gorunur_parcalar(xs, ys, (90.0, 110.0))
    assert [p[0] for p in parcalar] == [[2, 3], [5]]
    assert [p[1] for p in parcalar] == [[95.0, 100.0], [101.0]]


def test_gorunur_parcalar_aralik_yoksa_seriyi_bozmaz():
    parcalar = grafik._gorunur_parcalar([0, 1], [1.0, 2.0], None)
    assert parcalar == [([0, 1], [1.0, 2.0])]


def test_kadraj_disi_bant_parcasi_cizilmez_ve_sayilir():
    """Alt sınır karenin ÇOK altında başlıyor: yalnız görünür parça çizilir."""
    n = 60
    # alt çapa: bar 0'da 40, bar 59'da 100 → kare (90-110) dışında bir bölüm var
    ust = (0, 108.0, 59, 106.0)
    alt = (0, 40.0, 59, 100.0)
    formasyon = {"start_bar": 0, "upper_now": f_line_price(*ust, n - 1),
                 "lower_now": f_line_price(*alt, n - 1),
                 "hb1": 0, "hp1": 108.0, "hb2": 59, "hp2": 106.0,
                 "lb1": 0, "lp1": 40.0, "lb2": 59, "lp2": 100.0}
    goruntu = {"formasyon": formasyon, "sol": 0, "isaretler": [], "temas": [],
               "temas_isaret": [], "yuksek": [], "dusuk": []}
    ax = _eksen(n, (90.0, 110.0))
    ozet = grafik._formasyon_ciz(ax, goruntu, n, 300.0, {}, sag_bosluk=0,
                                 aralik=(90.0, 110.0))
    cizgiler = _bant_cizgileri(ax)
    # her çizgi kendi parçasından; hiçbir nokta aralık dışında değil
    for ln in cizgiler:
        for y in ln.get_ydata():
            assert 90.0 - 1e-9 <= float(y) <= 110.0 + 1e-9
    # alt doğru kadrajın altına taşıyor → kırpılan bar SAYILIR (sessiz kayıp yok)
    assert ozet["kirpilan"]["alt"] > 0
    assert ozet["kirpilan"]["ust"] == 0


def test_mumlar_karenin_cogunu_kaplar():
    """Y-aralığı mumdan kurulunca mumlar kareyi doldurur (eskiden %29'du)."""
    n = 85
    kadraj = _cerceve(n, taban=70.0, salinim=3.0)
    # bant fiyattan kopuk: 40-50 bandında başlayıp 100'e çıkıyor
    cift = {"pattern_name": "Simetrik Üçgen", "state": "KIRILIM_ADAYI",
            "start_bar": 0, "end_bar": n - 1, "upper_now": 74.0, "lower_now": 68.0,
            "hb1": 0, "hp1": 74.0, "hb2": n - 1, "hp2": 74.0,
            "lb1": 0, "lp1": 40.0, "lb2": n - 1, "lp2": 68.0}
    goruntu = grafik.anlik_goruntu(cift, "1h", kadraj, simdi=None)
    yol, meta = grafik.ciz(goruntu, "1h", secenekler={"gorsel_aralik": 0})
    try:
        alt, ust = meta["kare"]["y_araligi"]
        hl = [v for v in goruntu["yuksek"] + goruntu["dusuk"] if v is not None]
        kaplama = (max(hl) - min(hl)) / (ust - alt)
        assert kaplama > 0.6, kaplama
        # bant serisi aralık dışında kaldığı için çizim sayacı da görünür
        assert "formasyon" in meta["cizgiler"]
    finally:
        if yol:
            import os
            os.unlink(yol)


# ------------------------------------------------- 3. kırılım marjı (ölçü) çizimi

def _alarm_goruntusu(deger=100.0, kapanis=104.0, tur="teyit", yon=1, bar=40):
    n = 60
    seri = [100.0 + i * 0.02 for i in range(n)]
    if kapanis is not None:
        seri[bar] = float(kapanis)
    goruntu = {"sol": 0, "kapanis": list(seri), "acilis": list(seri),
               "yuksek": [v + 0.5 for v in seri], "dusuk": [v - 0.5 for v in seri],
               "alarm": {"deger": deger, "kapanis": kapanis, "tur": tur, "yon": yon,
                         "bar": bar, "hedef": None}}
    return goruntu


def test_kirilim_marji_sag_boslukta_olcu_olarak_cizilir():
    goruntu = _alarm_goruntusu()
    ax = _eksen(60, (95.0, 110.0))
    meta = grafik._kirilim_olcusu(ax, goruntu, 60, sag_bosluk=8, aralik=(95.0, 110.0))
    assert meta is not None
    assert meta["marj"] == pytest.approx(4.0)
    assert meta["yuzde"] == pytest.approx(4.0, abs=1e-6)
    assert "kırılım +4" in meta["etiket"]
    # çift uçlu ok (annotate) + çip çizildi
    assert any("kırılım" in str(t.get_text()) for t in ax.texts)


def test_kirilim_marji_geri_donuste_iceride_yazar():
    """Yukarı kırılım yönü +1 ama kapanış seviyenin ALTINDA → "içeride"."""
    goruntu = _alarm_goruntusu(deger=100.0, kapanis=98.5)
    goruntu["alarm"]["yon"] = 1
    ax = _eksen(60, (95.0, 110.0))
    meta = grafik._kirilim_olcusu(ax, goruntu, 60, sag_bosluk=8, aralik=(95.0, 110.0))
    assert meta is not None and meta["marj"] < 0
    assert meta["etiket"].startswith("içeride")


def test_gecersizlesen_kirilimda_kirilim_denmez():
    """Geçersizleşmiş olayda ölçü `üstünde/altında` der — kart diliyle aynı."""
    goruntu = _alarm_goruntusu(deger=100.0, kapanis=100.39, tur="gecersiz")
    ax = _eksen(60, (95.0, 110.0))
    meta = grafik._kirilim_olcusu(ax, goruntu, 60, sag_bosluk=8, aralik=(95.0, 110.0))
    assert meta["etiket"].startswith("üstünde")
    assert "kırılım" not in meta["etiket"]


def test_aday_alarminda_mesafe_yazilir():
    """Aday: fiyat seviyeyi henüz kırmadı → `seviyeye …`, marj YOK."""
    goruntu = _alarm_goruntusu(deger=100.0, kapanis=99.94, tur="aday", yon=0)
    ax = _eksen(60, (95.0, 110.0))
    meta = grafik._kirilim_olcusu(ax, goruntu, 60, sag_bosluk=8, aralik=(95.0, 110.0))
    assert meta["mod"] == "mesafe" and meta["marj"] is None
    assert meta["mesafe"] == pytest.approx(0.06, abs=1e-9)
    assert meta["etiket"].startswith("seviyeye")


def test_kirilim_marji_bosluk_yoksa_cizilmez():
    """Sağ boşluk kapalıysa ölçü mumların üstüne binmesin diye çizilmez."""
    ax = _eksen(60, (95.0, 110.0))
    assert grafik._kirilim_olcusu(ax, _alarm_goruntusu(), 60, sag_bosluk=0) is None


def test_kirilim_marji_kapanis_yoksa_mumdan_okunur():
    """Motor `candle_close_price` vermezse karedeki mumun kapanışı kullanılır."""
    goruntu = _alarm_goruntusu(deger=100.0, kapanis=None, tur="kritik")
    goruntu["kapanis"][40] = 101.5
    goruntu["acilis"][40] = 101.0
    ax = _eksen(60, (95.0, 110.0))
    meta = grafik._kirilim_olcusu(ax, goruntu, 60, sag_bosluk=8, aralik=(95.0, 110.0))
    assert meta is not None and meta["kapanis"] == pytest.approx(101.5)


def test_kirilim_marji_meta_sozlesmesi():
    """Gerçek kare: teyitli alarmda `meta["cizgiler"]["kirilim"]` dolu."""
    goruntu = {"sol": 0, "tf": "1h", "tf_kisa": "1s", "sembol": "TST",
               "son_bar_ts": None, "son_kapanis": 104.0, "bar_sayisi": 60,
               "zamanlar": [None] * 60,
               **{ad: [100.0 + i * 0.05 for i in range(60)]
                  for ad in ("acilis", "yuksek", "dusuk", "kapanis")},
               "formasyon": {"ad": "Simetrik Üçgen", "state": "KIRILIM_TEYITLI",
                             "upper_now": 100.0, "lower_now": 96.0},
               "alarm": {"deger": 100.0, "kapanis": 100.8, "tur": "teyit", "yon": 1,
                         "bar": 40, "hedef": None},
               "zone": None, "olay": None, "serit": None, "temas": [], "isaretler": []}
    yol, meta = grafik.ciz(goruntu, "1h")
    try:
        kirilim = meta["cizgiler"].get("kirilim")
        assert kirilim and kirilim["marj"] == pytest.approx(0.8)
        assert "seviye" in kirilim and "kapanis" in kirilim
    finally:
        if yol:
            import os
            os.unlink(yol)


# ------------------------------------------- 4. başlıkta kartla aynı temas sayısı

def test_baslik_motorun_ust_alt_temas_sayilarini_yazar():
    goruntu = {"sembol": "TST", "tf_kisa": "1s", "son_no": 1, "temas": list(range(39)),
               "formasyon": {"ad": "Simetrik Üçgen", "upper_touches": 2,
                             "lower_touches": 3, "upper_now": 100.0, "lower_now": 96.0}}
    meta = {"mum_sayisi": 85}
    metin = grafik._metinler(goruntu, meta, 1080, [], False)
    satir = " · ".join(metin["satirlar"])
    assert "temas üst 2 / alt 3" in satir
    assert "bant teması 39" not in satir


def test_baslik_alan_yoksa_toplam_der():
    goruntu = {"sembol": "TST", "tf_kisa": "1s", "temas": list(range(7)),
               "formasyon": {"ad": "Simetrik Üçgen", "upper_now": 100.0,
                             "lower_now": 96.0}}
    metin = grafik._metinler(goruntu, {"mum_sayisi": 85}, 1080, [], False)
    satir = " · ".join(metin["satirlar"])
    assert "bant teması (toplam) 7" in satir


# ---------------------------------------------- 5. RVOL rozet aralığı (pikselden)

def test_rvol_rozet_araligi_pikselden_genisler(monkeypatch):
    """Dar karede (px/bar ≈ 4,5) sabit 7 bar yetmiyor: aralık rozet genişliğinden."""
    n = 120
    goruntu = {"serit": {"degerler": [2.5 if i % 2 == 0 else 1.0 for i in range(n)]},
               "acilis": [100.0] * n, "kapanis": [100.0] * n,
               "yuksek": [101.0] * n, "dusuk": [99.0] * n,
               "olay": {}, "zone": None, "alam": {}}
    fig = Figure(figsize=(7.8, 11.0), dpi=100)      # mobil kare
    ax = fig.add_axes([0.12, 0.1, 0.6, 0.8])
    ax.set_xlim(-0.6, n - 0.4 + 8)
    ax.set_ylim(95.0, 105.0)
    sayac = grafik._rvol_rozetleri(ax, goruntu, n, goruntu["dusuk"],
                                   goruntu["yuksek"], fig=fig)
    assert sayac["artis"] > 0
    # rozetlerin x konumları arasında en az bir rozet genişliği var (bar cinsinden)
    xs = sorted(float(t.xy[0]) for t in ax.texts if "⚡" in str(t.get_text()))
    assert len(xs) >= 2
    for a, b in zip(xs, xs[1:]):
        assert b - a >= 4.0, (a, b)


# --------------------------------------------------- 6. x tick yoğunluğu (mobil)

def test_tick_yogunlugu_dar_eksende_duser():
    from datetime import datetime, timedelta, timezone

    ist = timezone(timedelta(hours=3))
    n = 100
    zamanlar = [datetime(2026, 9, 1, 10, 0, tzinfo=ist) + timedelta(hours=i) for i in range(n)]
    genis = Figure(figsize=(10.8, 8.1), dpi=100)
    ax_genis = genis.add_axes([0.075, 0.1, 0.8, 0.8])
    ax_genis.set_xlim(-0.6, n - 0.4)
    grafik._tik_etiketleri(ax_genis, zamanlar, "1h")
    dar = Figure(figsize=(7.8, 11.0), dpi=100)
    ax_dar = dar.add_axes([0.12, 0.1, 0.6, 0.8])
    ax_dar.set_xlim(-0.6, n - 0.4)
    grafik._tik_etiketleri(ax_dar, zamanlar, "1h")
    assert len(ax_dar.get_xticks()) <= len(ax_genis.get_xticks())
    assert len(ax_dar.get_xticks()) >= 2


# --------------------------------------------- 7. başlık çakışması (ayrı satır)

def test_dar_karede_son_mum_yazisi_kendi_satirina_iner():
    from datetime import datetime, timedelta, timezone

    ts = datetime(2026, 9, 25, 17, 30, tzinfo=timezone(timedelta(hours=3)))
    goruntu = {"sembol": "GARAN", "tf_kisa": "1s", "tf": "1h", "son_bar_ts": ts,
               "son_kapanis": 129.8,
               "formasyon": {"ad": "Yükselen Üçgen", "quality": 89.0,
                             "state": "KIRILIM_ADAYI", "upper_now": 136.0,
                             "lower_now": 130.0}}
    meta = {"mum_sayisi": 103}
    dar = grafik._metinler(goruntu, meta, 780, [], False)      # mobil genişlik
    genis = grafik._metinler(goruntu, meta, 1080, [], False)
    assert dar["sag_ayri_satir"] is True
    assert genis["sag_ayri_satir"] is False


# ------------------------- 7. alarm mumu pencere koordinatına çevrilir (2026-10-23)

def test_alarm_bar_pencere_koordinatina_cevrilir():
    """`alarm_bar` çerçevenin MUTLAK indeksidir; kare `[sol, sag)` çizer.

    Dönüşüm yapılmadığında düşey alarm çizgisi yalnız mutlak indeks tesadüfen
    pencereye düştüğünde çiziliyordu (gerçek karelerde hiç görünmüyordu) ve
    `_gecersiz_katmani` yanlış muma bakıyordu.
    """
    n = 240
    cerceve = {"zaman": [None] * n,
               "acilis": [50.0] * n, "yuksek": [51.0] * n,
               "dusuk": [49.0] * n, "kapanis": [50.0] * n, "hacim": [1_000_000.0] * n}
    cift = {"pattern_name": "Simetrik Üçgen", "state": "KIRILIM_TEYITLI",
            "start_bar": 150, "end_bar": 200, "upper_now": 50.0, "lower_now": 49.0,
            "break_price": 50.0, "break_dir": 1, "candle_close_price": 50.4}
    goruntu = grafik.anlik_goruntu(cift, "1h", cerceve, alarm_turu="teyit",
                                   alarm_bar=205, sembol="TST")
    sol = goruntu["sol"]
    assert sol <= 205 < goruntu["sag"]        # kurgu: alarm mumu pencerede
    alarm = goruntu["alarm"]
    assert alarm["bar_disarida"] is False
    assert alarm["bar"] == 205 - sol          # pencere içi
    assert alarm["bar_mutlak"] == 205         # çerçeve indeksi korunur
    # pencere dışındaki mum: çizilmez ama SAYILIR
    disari = grafik.anlik_goruntu(cift, "1h", cerceve, alarm_turu="teyit",
                                  alarm_bar=5, sembol="TST")
    assert disari["alarm"]["bar"] is None and disari["alarm"]["bar_disarida"] is True
    assert any("kadraj dışında" in u for u in disari["uyarilar"])
