# -*- coding: utf-8 -*-
"""2026-11-15 grafik adımları: dinamik sağ şerit, veri rozeti, ok kademesi.

Ok kademesi replay desteklidir (stabil_ok_replay_2026_11_05, 555 geçerli ▲):
süpürme %29,6 zayıf → küçük/soluk; upward_rebase %17,3 zayıf → içi boş büyük.
Filtre değildir, yalnız görsel kademedir.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import grafik
from grafik.render import _sag_serit_px_hesapla

IST = timezone(timedelta(hours=3))


def _goruntu(son_bar=True, kapali=True):
    n = 40
    kapanis = [50.0 + i * 0.1 for i in range(n)]
    return {
        "sembol": "THYAO", "tf": "4h", "tf_kisa": "4S",
        "zamanlar": [datetime(2026, 11, 3, 9, 30, tzinfo=IST) + timedelta(hours=4 * i)
                     for i in range(n)],
        "acilis": [k - 0.05 for k in kapanis], "kapanis": kapanis,
        "yuksek": [k + 0.3 for k in kapanis], "dusuk": [k - 0.3 for k in kapanis],
        "son_bar_ts": "2026-11-03T17:30:00+03:00" if son_bar else None,
        "son_bar_kapali": kapali, "son_kapanis": kapanis[-1],
        "zone": {}, "olay": {}, "formasyon": {}, "alarm": {}, "serit": {},
    }


def test_serit_etiketsiz_karede_dar_uzun_etikette_genis():
    dar = _sag_serit_px_hesapla(_goruntu())
    g = _goruntu()
    g["alarm"] = {"deger": 53.9, "hedef": 61.25}
    g["zone"] = {"cizilen": [{"alt": 48.0, "ust": 49.5, "yon": 1, "durum": "AKTIF"}]}
    genis = _sag_serit_px_hesapla(g)
    assert 84.0 <= dar < genis <= 195.0


def test_veri_rozeti_eksik_ve_acik_mumda(tmp_path):
    yol, meta = grafik.ciz(_goruntu(son_bar=False), "4h",
                           {"cikti": str(tmp_path / "a.png")})
    assert yol and meta["veri_rozeti"] == "VERİ EKSİK"
    yol, meta = grafik.ciz(_goruntu(kapali=False), "4h",
                           {"cikti": str(tmp_path / "b.png")})
    assert yol and meta["veri_rozeti"] == "SON MUM AÇIK"
    yol, meta = grafik.ciz(_goruntu(), "4h", {"cikti": str(tmp_path / "c.png")})
    assert yol and meta["veri_rozeti"] is None
    assert 84.0 <= meta["kare"]["sag_serit_px"] <= 195.0


def test_ok_kademesi_turleri_ayirir(tmp_path):
    g = _goruntu()
    seviyeler = [49.0] * 40
    g["stabil"] = {
        "hazir": True, "seviyeler": seviyeler, "renkler": ["ust"] * 40,
        "reclaim_barlar": [10, 12], "momentum_barlar": [20, 22],
        "reclaim_turleri": {"10": "multi_bar_recovery",
                            "12": "intrabar_sweep_reclaim"},
        "momentum_turleri": {"20": "upward_rebase_momentum",
                             "22": "long_base_breakout"},
        "dikey_barlar": [], "dikey_deneme_barlar": [], "son_seviye": 49.0,
        "son_renk": "ust",
    }
    yol, meta = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "ok.png")})
    assert yol
    cizgiler = meta["cizgiler"]["stabil"]
    assert cizgiler["reclaim_isaret"] == 1
    assert cizgiler["reclaim_supurme_isaret"] == 1
    assert cizgiler["momentum_isaret"] == 1
    assert cizgiler["momentum_taban_isaret"] == 1


def test_ok_baglam_halkalari_cizilir(tmp_path):
    """Yapı uyumu (beyaz halka) + yakın engel (kırmızı halka) sayaçları."""
    g = _goruntu()
    g["stabil"] = {
        "hazir": True, "seviyeler": [49.0] * 40, "renkler": ["ust"] * 40,
        "reclaim_barlar": [10, 12], "momentum_barlar": [],
        "reclaim_turleri": {"10": "multi_bar_recovery", "12": "intrabar_sweep_reclaim"},
        "yapi_uyumlu_barlar": [10], "engel_yakin_barlar": [12],
        "dikey_barlar": [], "dikey_deneme_barlar": [], "son_seviye": 49.0,
        "son_renk": "ust",
    }
    yol, meta = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "baglam.png")})
    assert yol
    cizgiler = meta["cizgiler"]["stabil"]
    assert cizgiler["yapi_uyumlu_isaret"] == 1
    assert cizgiler["engel_yakin_isaret"] == 1
