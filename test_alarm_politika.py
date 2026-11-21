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
import pytest

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


def test_ureticiden_rapora_ayni_ufuk_ve_gercek_seanslar(tmp_path):
    from research import domain_alarm_replay as replay

    # İstanbul'da 2 Kasım: gece yarısı UTC tarihine göre bir gün erkendir.
    tarih = "2026-11-01T21:00:00+00:00"
    satirlar = []
    for idx, (ileri, geri) in enumerate([
        ([0.2] * 12 + [2], [0] * 13),  # lehte hareket ancak 13. barda
        ([0.2] * 12, [2] * 12),        # yalnız aleyhe, 12. bar doldu
        ([2] * 12, [0] * 12),          # lehte ≥1,5 ATR
        ([2] * 11, [0] * 11),          # ham hareket var ama ufuk dolmadı
    ]):
        r = _satir(bar_time=tarih, bar_index=idx * 6, bagl_gunici_kosu=1)
        replay.olcum_yaz(r, 1, 10, 1, [10+x for x in ileri], [10-x for x in geri], [10]*len(ileri))
        satirlar.append(r)
    replay._satir_ekle(tmp_path / "tetikler.jsonl", satirlar)
    df = ap.oku(tmp_path)
    assert df.seans.unique().tolist() == ["2026-11-02"]
    assert df.hareket_iki.tolist()[:3] == [False, True, True]
    assert pd.isna(df.hareket_iki.iloc[-1])
    # 3 Kasım kart çıkmayan gerçek seans, 4 Kasım arşivin son günü.
    envanter = {g: 1 for g in ("2026-11-02", "2026-11-03", "2026-11-04")}
    replay._satir_ekle(tmp_path / "meta.jsonl", [
        {"symbol": "X", "timeframe": tf, "seans_bar_sayilari": envanter}
        for tf in ("1h", "2h", "4h", "1d")])
    meta = ap._oku_meta(tmp_path)
    rapor = ap.rapor(df, meta, "2026-11-01", "2026-11-04", ["X", "Y"], ["X"])
    assert "2 ortak İstanbul seansı" in rapor and "Arşiv dışında: Y" in rapor
    assert "2,00 (2,0) | 4 (2026-11-02) | 3 / 1 | 25,0% → 33,3% | 100,0% → 66,7% | 100,0%" in rapor
    with pytest.raises(ValueError, match="eksik veya tekrarlı seri"):
        ap.rapor(df, meta.iloc[1:], "2026-11-01", "2026-11-04", ["X"], ["X"])


def test_seans_basinda_cooldown_sifirlanmaz():
    df = pd.DataFrame([_satir(bar_index=i, seans=str(gun), hareket=True, iyi=True, hareket_iki=True)
                       for i, gun in [(4, 1), (6, 2), (10, 2)]])
    r = ap.politika_tablosu(df, df.iloc[:0], seanslar=["2"], politikalar=ap.POLITIKALAR[:1])[0]
    assert r["n"] == 1 and r["hatirlama"] == 0.5


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


def test_ufku_dolmayan_kart_yuktur_isabet_degil(tmp_path):
    from research.domain_alarm_replay import _satir_ekle

    _satir_ekle(tmp_path / "tetikler.jsonl", [
        _satir(bar_time="2026-10-19T10:00:00+03:00", yon_asim_100=None, yon_asim_150=None, ters_h12=None)
    ])
    df = ap.oku(tmp_path)
    tablo = {r['kod']: r for r in ap.politika_tablosu(df, df[df.kontrol], seanslar=["2026-10-19"])}
    assert tablo['P0']['gunluk'] == 1 and tablo['P0']['olculen'] == 0
    assert pd.isna(tablo['P0']['hareket']) and pd.isna(tablo['P0']['iki'])
    assert pd.isna(tablo['P0']['hatirlama'])
    assert tablo['P6']['gunluk'] == 0 and pd.isna(tablo['P6']['hareket'])
