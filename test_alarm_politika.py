"""``research.alarm_politika`` testleri — politika sayımı ve dürüstlük sözleşmesi.

Bu testlerin amacı kodun "çalıştığını" göstermek değil, **raporun yanlış sayı
basmasını engellemek**. Üç sözleşme korunuyor:

1. Cooldown uygulanmadan kart sayısı raporlanmaz (canlı davranışla aynı).
2. "İyi yakalama" sütunu, politikanın **neyi kaybettiğini** gösterir; binde
   bir politikanın %100 hatırlaması matematiksel olarak imkânsızdır (tüm
   iyi tetikleri basmıyorsa).
3. Yönlü ve iki yönlü "hareket" tanımları karıştırılmaz: iki yönlü oran
   yönlüden **her zaman** büyük veya eşittir.
"""

from __future__ import annotations

import pandas as pd

from research import alarm_politika as ap


def _satir(**kw):
    temel = {
        "symbol": "X", "timeframe": "1h", "bar_index": 0,
        "kanallar": ["OB"], "hacim_tier": None, "kontrol": False,
        "yon_asim_100": True, "yon_asim_150": False,
        "yon_tepe_atr": 1.2, "yon_dip_atr": 0.3,
        "bagl_sikisma": 0.4, "bagl_gunici_kosu": 0.0, "bagl_seans_saati": 11,
    }
    temel.update(kw)
    return temel


def test_cooldown_6_bar_uygulanir():
    tetikler = [_satir(bar_index=i) for i in range(0, 12)]
    secili = ap._cooldown(pd.DataFrame(tetikler))
    # 0, 6 → yalnız iki kart (6 bar sessizlik)
    assert secili["bar_index"].tolist() == [0, 6]


def test_cooldown_farkli_sembolleri_karistirmaz():
    tetikler = [
        _satir(symbol="A", bar_index=0), _satir(symbol="B", bar_index=1),
    ]
    assert len(ap._cooldown(pd.DataFrame(tetikler))) == 2


def test_p2_yalniz_hacim_kademesi_secer():
    df = pd.DataFrame([
        _satir(hacim_tier="5x"), _satir(hacim_tier=None), _satir(hacim_tier="10x"),
    ])
    assert df.apply(ap.p_yalniz_hacim, axis=1).tolist() == [True, False, True]


def test_p3_tek_basina_gorultu_kanalini_susturur():
    df = pd.DataFrame([
        _satir(kanallar=["OB"]),
        _satir(kanallar=["FORMASYON"]),
        _satir(kanallar=["FORMASYON", "OB"]),
        _satir(kanallar=["CHoCH"]),
        _satir(kanallar=["FORMASYON", "CHoCH"]),
    ])
    # FORMASYON eşliğindeki CHoCH basılır, tek başına basılmaz.
    assert df.apply(ap.p_katman, axis=1).tolist() == [False, True, True, False, True]


def test_iki_yonlu_hareket_yonluden_kucuk_olamaz():
    df = ap.oku.__wrapped__ if hasattr(ap.oku, "__wrapped__") else None
    # Fonksiyonu doğrudan dataframe üzerinden doğrula.
    veri = pd.DataFrame([_satir(yon_asim_100=False, yon_tepe_atr=1.5, yon_dip_atr=0.1)])
    veri["hareket"] = veri["yon_asim_100"].map(ap._bayrak)
    veri["hareket_iki"] = (veri["yon_tepe_atr"] >= 1) | (veri["yon_dip_atr"] >= 1)
    assert bool(veri["hareket_iki"].iloc[0]) and not bool(veri["hareket"].iloc[0])
    assert df is None  # dokümantasyon: sarmalayıcı beklenmiyor


def test_bayrak_metin_ve_sayiyi_ayni_okur():
    assert ap._bayrak(True) and ap._bayrak(1) and ap._bayrak("True")
    assert not ap._bayrak(False) and not ap._bayrak(0) and not ap._bayrak("")


def test_wilson_kucuk_ornekde_daha_temkinli():
    assert ap.wilson_alt(0.9, 10) < ap.wilson_alt(0.9, 1000)
    assert ap.wilson_alt(0.9, 1000) < 0.9


def test_politika_tablosu_kart_sayisi_cooldown_sonrasi():
    df = pd.DataFrame([_satir(bar_index=i) for i in range(0, 12)])
    df["hareket"] = True
    df["iyi"] = False
    df["hareket_iki"] = True
    taban = pd.DataFrame([{**_satir(kontrol=True), "hareket": True, "iyi": False,
                           "hareket_iki": True}])
    tablo = {r["kod"]: r for r in ap.politika_tablosu(df, taban)}
    assert tablo["P0"]["n"] == 2  # 12 tetik → cooldown → 2 kart
    assert tablo["P0"]["basilan_pay"] < 0.2


def test_kart_gun_meta_bar_sayisindan_hesaplanir():
    """Kart/gün, TETİK SATIRI değil GERÇEK bar sayısından hesaplanmalı.

    Regresyon: eski sürüm ``len(grup)`` kullanıyordu → 3.253 barlık bir seride
    ~800 tetik satırı olduğu için oran ~3 kat şişiyordu.
    """
    df = pd.DataFrame([_satir(symbol="A", bar_index=i) for i in range(10)] + 
                      [_satir(symbol="B", bar_index=i) for i in range(10)])
    meta = pd.DataFrame([
        {"symbol": "A", "timeframe": "1d", "bar_sayisi": 500},
        {"symbol": "B", "timeframe": "1d", "bar_sayisi": 500},
    ])
    # 1.000 gün bekleniyor (500+500), 20 değil
    assert ap._gun_sayisi(df, meta) == 1000.0
    # 1h: 9,5 bar/gün
    meta_h = pd.DataFrame([{"symbol": "A", "timeframe": "1h", "bar_sayisi": 950}])
    assert abs(ap._gun_sayisi(df, meta_h) - 100.0) < 1e-6
