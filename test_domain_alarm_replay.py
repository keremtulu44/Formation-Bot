"""Domain alarm replay testleri (ağsız).

Kilitlenen sözleşmeler:

1. **Canlı eşikler birebir.** Replay, canlı `bot/domain_alarm_service.py`
   içindeki sabitleri yeniden yorumlamaz; aynı değerleri kullanır.
2. **Anti-lookahead.** Ölçüm tetik barından *sonraki* bardan başlar; tetik
   barının kendisi hiçbir uzanıma katılmaz.
3. **Sağdan sansür.** Pencere veri sonuna takılırsa `sansur=True` ve satır
   temiz kümeden düşer.
4. **Kontrol (taban) örneklemi** tetik barlarına denk gelmez ve yön verilmez.
5. **Yön 0 satırı ikiye ayrılır** (hem yukarı hem aşağı ölçüm), hiçbir orana
   tek yönlü karışmaz.
6. **Kanal tespiti** canlı kuralla aynı sonucu verir: OB içinde olma, FVG
   reaksiyonu, BOS/CHoCH son-2-bar penceresi, RVOL 5×/10×.
"""

from __future__ import annotations

import pandas as pd
import pytest

from research import domain_alarm_replay as dar


def _frame(kapanislar, yuksekler=None, dusukler=None, hacimler=None, baslangic="2026-01-05 10:00"):
    n = len(kapanislar)
    yuksekler = yuksekler if yuksekler is not None else [c + 0.05 for c in kapanislar]
    dusukler = dusukler if dusukler is not None else [c - 0.05 for c in kapanislar]
    hacimler = hacimler if hacimler is not None else [100.0] * n
    ts = pd.date_range(baslangic, periods=n, freq="1h", tz="Europe/Istanbul")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": kapanislar,
            "high": yuksekler,
            "low": dusukler,
            "close": kapanislar,
            "volume": hacimler,
        }
    )


# ---------------------------------------------------------------------------
# 1) Canlı eşikler birebir
# ---------------------------------------------------------------------------


def test_canli_esikleri_birebir_ayni():
    """Replay sabitleri canlı koddaki değerlerle aynı olmalı."""
    import config
    from bot import domain_alarm_service as canli

    assert dar.RVOL_ESIK_5X == 5.0
    assert dar.RVOL_ESIK_10X == 10.0
    assert dar.RVOL_SUPHE == 50.0
    assert dar.BOS_PENCERE_BAR == 2
    # Canlı servis bu eşikleri config'ten okur; varsayılanlar aynı olmalı.
    assert float(getattr(config, "YENI_DOMAIN_ALARM_HACIM_5X", 5.0)) == dar.RVOL_ESIK_5X
    assert float(getattr(config, "YENI_DOMAIN_ALARM_HACIM_10X", 10.0)) == dar.RVOL_ESIK_10X
    assert float(getattr(config, "YENI_DOMAIN_ALARM_HACIM_SUPHE", 50.0)) == dar.RVOL_SUPHE
    # Canlı BOS/CHoCH penceresi `frame_len - 2`; replay 2 bar.
    assert "esik_bar = max(0, frame_len - 2)" in open(canli.__file__, encoding="utf-8").read()


def test_fvg_reaksiyon_state_sabiti():
    """Replay FVG reaksiyon eşiği motorun REACTION state'i ile aynı olmalı."""
    from domain_engines.fvg.fvg_engulfing_models import FvgState

    assert dar.FVG_REAKSIYON_STATE == int(FvgState.REACTION)


# ---------------------------------------------------------------------------
# 2) Anti-lookahead ve ölçüm yönü
# ---------------------------------------------------------------------------


def test_olcum_tetik_barindan_sonra_baslar():
    """Tetik barındaki tepe ölçüme GİRMEMELİ.

    Kurgu: 20 ısınma barı düz, **21. bar tetik** ve o barda fitil 12.0'a
    fırlıyor, sonraki 4 bar 10.25 tavanında. Ölçüm tetik barından sonra
    başlarsa tepe 10,25'ten gelir (~1 ATR); tetik barı sızarsa 12,0'den
    gelir (~8 ATR). Eşik bu iki değeri kesin ayırır.
    """
    kapanis = [10.0] * 25
    yuksek = [10.05] * 20 + [12.0] + [10.25] * 4
    dusuk = [9.95] * 21 + [10.15] * 4
    frame = _frame(kapanis, yuksek, dusuk)
    tetik = {
        "symbol": "TEST", "timeframe": "1h", "bar_index": 20,
        "bar_time": "2026-01-05 20:00", "close": 10.0,
        "kanallar": ["OB"], "kanal_sayisi": 1, "yon": 1,
        "formasyon_state": None, "formasyon_tip": None, "hacim_tier": None,
        "rvol": 1.0, "kontrol": False,
    }
    satirlar = dar.seri_olcumu([tetik], frame)
    assert len(satirlar) == 1
    satir = satirlar[0]
    assert 0 < satir["yon_tepe_atr"] < 3, "tetik barının tepesi ölçüme sızmamalı"


def test_negatif_yon_asagi_olcer():
    """Aşağı yönde "lehte" = düşük fiyat. Fiyat düşerse tepe pozitiftir."""
    kapanis = [10.0] * 24
    yuksek = [10.05] * 24
    dusuk = [9.95] * 20 + [9.90, 9.80, 9.70, 9.60]
    frame = _frame(kapanis, yuksek, dusuk)
    tetik = {
        "symbol": "TEST", "timeframe": "1h", "bar_index": 20,
        "bar_time": "x", "close": 10.0, "kanallar": ["CHoCH"],
        "kanal_sayisi": 1, "yon": -1, "formasyon_state": None,
        "formasyon_tip": None, "hacim_tier": None, "rvol": None, "kontrol": False,
    }
    satir = dar.seri_olcumu([tetik], frame)[0]
    assert satir["yon_tepe_atr"] > 0
    assert satir["yon_dip_atr"] <= 0


def test_yon_sifir_iki_yone_ayrilir():
    """Yön belirlenemeyen tetik hem yukarı hem aşağı satır üretir."""
    kapanis = [10.0] * 26
    yuksek = [10.05] * 21 + [10.24, 10.05, 10.05, 10.05, 10.05]
    dusuk = [9.95] * 21 + [9.90, 9.95, 9.95, 9.95, 9.95]
    frame = _frame(kapanis, yuksek, dusuk)
    tetik = {
        "symbol": "TEST", "timeframe": "1h", "bar_index": 20, "bar_time": "x",
        "close": 10.0, "kanallar": ["HACIM"], "kanal_sayisi": 1, "yon": 0,
        "formasyon_state": None, "formasyon_tip": None, "hacim_tier": "5x",
        "rvol": 6.0, "kontrol": False,
    }
    satirlar = dar.seri_olcumu([tetik], frame)
    assert len(satirlar) == 2
    assert {s["yon"] for s in satirlar} == {1, -1}
    # İkisi de aynı bardan ölçülür; tepe farklı taraflardan gelir.
    assert satirlar[0]["yon_tepe_atr"] != satirlar[1]["yon_tepe_atr"]


# ---------------------------------------------------------------------------
# 3) Sansür
# ---------------------------------------------------------------------------


def test_veri_sonuna_takilan_tetik_sansurlu():
    kapanis = [10.0] * 25
    frame = _frame(kapanis)
    tetik = {
        "symbol": "TEST", "timeframe": "1h", "bar_index": 23, "bar_time": "x",
        "close": 10.0, "kanallar": ["OB"], "kanal_sayisi": 1, "yon": 1,
        "formasyon_state": None, "formasyon_tip": None, "hacim_tier": None,
        "rvol": None, "kontrol": False,
    }
    satir = dar.seri_olcumu([tetik], frame)[0]
    # Yalnız 1 bar sonrası var; 40 bar ufku dolmadı.
    assert satir["sansur"] is True
    assert satir["gozlenen_bar"] == 1
    assert satir["yon_h40"] is None


def test_son_bar_tetigi_satir_uretmez():
    kapanis = [10.0] * 25
    frame = _frame(kapanis)
    tetik = {
        "symbol": "TEST", "timeframe": "1h", "bar_index": 24, "bar_time": "x",
        "close": 10.0, "kanallar": ["OB"], "kanal_sayisi": 1, "yon": 1,
        "formasyon_state": None, "formasyon_tip": None, "hacim_tier": None,
        "rvol": None, "kontrol": False,
    }
    assert dar.seri_olcumu([tetik], frame) == []


def test_atr_yoksa_satir_uretmez():
    """İlk barlarda ATR None; o tetikler sessizce düşer, çökmez."""
    kapanis = [10.0] * 30
    frame = _frame(kapanis)
    tetik = {
        "symbol": "TEST", "timeframe": "1h", "bar_index": 1, "bar_time": "x",
        "close": 10.0, "kanallar": ["OB"], "kanal_sayisi": 1, "yon": 1,
        "formasyon_state": None, "formasyon_tip": None, "hacim_tier": None,
        "rvol": None, "kontrol": False,
    }
    assert dar.seri_olcumu([tetik], frame) == []


# ---------------------------------------------------------------------------
# 4) Kontrol (taban) örneklemi
# ---------------------------------------------------------------------------


def test_kontrol_tetik_barlarina_denk_gelmez():
    frame = _frame([10.0] * 60)
    tetikler = {20, 30, 40}
    kontroller = dar.kontrol_tetikleri("TEST", "1h", frame, tetikler, adim=10)
    indeksler = {k["bar_index"] for k in kontroller}
    assert indeksler.isdisjoint(tetikler)
    assert all(k["kontrol"] is True for k in kontroller)
    assert all(k["yon"] == 0 for k in kontroller)
    assert all(k["bar_index"] >= 20 for k in kontroller)


def test_kontrol_adimi_uygulanir():
    frame = _frame([10.0] * 60)
    kontroller = dar.kontrol_tetikleri("TEST", "1h", frame, set(), adim=10)
    assert [k["bar_index"] for k in kontroller] == [20, 30, 40, 50]


def test_kontrol_kisa_seride_bos():
    frame = _frame([10.0] * 10)
    assert dar.kontrol_tetikleri("TEST", "1h", frame, set(), adim=10) == []


# ---------------------------------------------------------------------------
# 5) Kanal tespiti — canlı kuralla aynı
# ---------------------------------------------------------------------------


def _zone(**kw):
    temel = {
        "family": "OB", "direction": "bullish", "zone_lower": 10.0,
        "zone_upper": 10.5, "dogum_index": 5, "terminal_index": 20,
        "native_full_fill": False,
    }
    temel.update(kw)
    return temel


def test_ob_kanali_fiyat_zone_icindeyse():
    frame = _frame([10.0] * 5 + [10.2] * 5)
    gozlem = {"zone": [_zone()], "event": [], "frm_olay": []}
    tetikler = dar.sembol_timeframe_tetikleri("TEST", "1h", frame, gozlem)
    assert any("OB" in t["kanallar"] for t in tetikler)


def test_ob_kanali_dogumdan_once_tetiklenmez():
    """Zone doğmadan önceki barlarda OB kanalı ateşlenmemeli."""
    frame = _frame([10.2] * 10)
    gozlem = {"zone": [_zone(dogum_index=7)], "event": [], "frm_olay": []}
    tetikler = dar.sembol_timeframe_tetikleri("TEST", "1h", frame, gozlem)
    assert all(t["bar_index"] > 7 for t in tetikler)


def test_ob_kanali_terminal_sonrasi_tetiklenmez():
    frame = _frame([10.2] * 15)
    gozlem = {"zone": [_zone(dogum_index=2, terminal_index=6)], "event": [], "frm_olay": []}
    tetikler = dar.sembol_timeframe_tetikleri("TEST", "1h", frame, gozlem)
    assert all(t["bar_index"] < 6 for t in tetikler)


def test_fvg_reaksiyonu_dokunus_ve_tukenmemis():
    frame = _frame([10.0] * 6 + [9.4] * 4)
    yuksek = [10.05] * 6 + [9.45] * 4
    dusuk = [9.95] * 6 + [9.35] * 4
    frame = _frame([10.0] * 6 + [9.4] * 4, yuksek, dusuk)
    zone = _zone(family="FVG", direction="bullish", zone_lower=9.5, zone_upper=9.9, dogum_index=4, terminal_index=None)
    tetikler = dar.sembol_timeframe_tetikleri("TEST", "1h", frame, {"zone": [zone], "event": [], "frm_olay": []})
    assert any("FVG" in t["kanallar"] for t in tetikler)


def test_fvg_tamamen_dolduysa_reaksiyon_yok():
    frame = _frame([9.4] * 10, [9.45] * 10, [9.35] * 10)
    zone = _zone(family="FVG", zone_lower=9.5, zone_upper=9.9, dogum_index=2, terminal_index=None, native_full_fill=True)
    tetikler = dar.sembol_timeframe_tetikleri("TEST", "1h", frame, {"zone": [zone], "event": [], "frm_olay": []})
    assert not any("FVG" in t["kanallar"] for t in tetikler)


def test_bos_iki_bar_penceresi():
    frame = _frame([10.0] * 12)
    event = [{
        "event_type": "EVENT_BOS", "direction": "UP", "event_bar": 5,
        "confirmation_status": "CONFIRMED", "validity": "VALID", "relevance": "CURRENT",
    }]
    tetikler = dar.sembol_timeframe_tetikleri("TEST", "1h", frame, {"zone": [], "event": event, "frm_olay": []})
    barlar = {t["bar_index"]: t for t in tetikler}
    assert 5 in barlar and "BOS" in barlar[5]["kanallar"]
    assert 6 in barlar and "BOS" in barlar[6]["kanallar"]
    assert 7 not in barlar


def test_bos_superseded_atlanir():
    frame = _frame([10.0] * 12)
    event = [{
        "event_type": "EVENT_BOS", "direction": "UP", "event_bar": 5,
        "confirmation_status": "CONFIRMED", "validity": "VALID", "relevance": "SUPERSEDED",
    }]
    tetikler = dar.sembol_timeframe_tetikleri("TEST", "1h", frame, {"zone": [], "event": event, "frm_olay": []})
    assert not any("BOS" in t["kanallar"] for t in tetikler)


def test_choch_ayri_kanal():
    frame = _frame([10.0] * 12)
    event = [{
        "event_type": "EVENT_CHOCH", "direction": "DOWN", "event_bar": 5,
        "confirmation_status": "CONFIRMED", "validity": "VALID", "relevance": "CURRENT",
    }]
    tetikler = dar.sembol_timeframe_tetikleri("TEST", "1h", frame, {"zone": [], "event": event, "frm_olay": []})
    assert any("CHoCH" in t["kanallar"] for t in tetikler)
    assert not any("BOS" in t["kanallar"] for t in tetikler)


def test_hacim_5x_ve_10x_kademesi():
    """RVOL = son hacim / son 20 barın ortalaması (canlı yerel formül)."""
    hacim = [100.0] * 30 + [700.0, 100.0]
    frame = _frame([10.0] * 32, hacimler=hacim)
    tetikler = dar.sembol_timeframe_tetikleri("TEST", "1h", frame, {"zone": [], "event": [], "frm_olay": []})
    assert len(tetikler) == 1
    # ortalama = (19*100 + 700)/20 = 130 → rvol = 700/130 = 5.38
    assert 5.0 <= tetikler[0]["rvol"] < 10.0
    assert tetikler[0]["hacim_tier"] == "5x"
    assert "HACIM" in tetikler[0]["kanallar"]

    hacim10 = [100.0] * 30 + [2000.0, 100.0]
    frame10 = _frame([10.0] * 32, hacimler=hacim10)
    tetikler10 = dar.sembol_timeframe_tetikleri("TEST", "1h", frame10, {"zone": [], "event": [], "frm_olay": []})
    # ortalama = (19*100 + 2000)/20 = 195 → rvol = 10.26
    assert tetikler10[0]["hacim_tier"] == "10x"


def test_formasyon_kanali_state_ile():
    frame = _frame([10.0] * 10)
    olay = [{
        "olay_type": "BREAK_CONFIRMED", "olay_name": "Kırılım teyitli ↑",
        "state": "KIRILIM_TEYITLI", "bar": 4,
    }]
    tetikler = dar.sembol_timeframe_tetikleri("TEST", "1h", frame, {"zone": [], "event": [], "frm_olay": olay})
    assert len(tetikler) == 1
    assert tetikler[0]["formasyon_state"] == "KIRILIM_TEYITLI"
    assert "FORMASYON" in tetikler[0]["kanallar"]


def test_gecersiz_formasyon_atlanir():
    frame = _frame([10.0] * 10)
    olay = [{"olay_type": "INVALID", "olay_name": "x", "state": "FORMASYON_GECERSIZ", "bar": 4}]
    tetikler = dar.sembol_timeframe_tetikleri("TEST", "1h", frame, {"zone": [], "event": [], "frm_olay": olay})
    assert tetikler == []


def test_tetik_yoksa_bos():
    frame = _frame([10.0] * 40)
    assert dar.sembol_timeframe_tetikleri("TEST", "1h", frame, {"zone": [], "event": [], "frm_olay": []}) == []


# ---------------------------------------------------------------------------
# 6) Toplama / rapor iskeleti
# ---------------------------------------------------------------------------


def test_rapor_kanallar_listesini_hashleyebilir(tmp_path):
    """``kanallar`` JSON'da liste; okuma demet'e çevrilmeli (groupby çökmesin)."""
    import json

    cikti = tmp_path / "cikti"
    cikti.mkdir()
    satir = {
        "symbol": "T", "timeframe": "1h", "bar_index": 1, "bar_time": "x",
        "close": 10.0, "atr": 0.1, "kanallar": ["OB", "FORMASYON"],
        "kanal_sayisi": 2, "yon": 1, "kontrol": False,
        "formasyon_state": "KIRILIM_TEYITLI", "formasyon_tip": "x",
        "rvol": 1.0, "hacim_tier": None, "data_quality": "OK",
        "yon_h3": 0.5, "yon_h12": 1.2, "yon_h40": 1.5, "yon_kap_h12": 0.4,
        "yon_kap_h40": 0.2, "yon_tepe_atr": 1.2, "yon_tepe_bar": 3.0,
        "yon_dip_atr": -0.3, "yon_pay_5": 0.8,
        "yon_asim_050": True, "yon_asim_100": True, "yon_asim_150": False,
        "yon_asim_200": False, "ters_h12": False, "gozlenen_bar": 100.0,
        "sansur": False,
    }
    (cikti / "tetikler.jsonl").write_text(json.dumps(satir) + "\n", encoding="utf-8")
    (cikti / "meta.jsonl").write_text(
        json.dumps({"symbol": "T", "timeframe": "1h", "bar_sayisi": 100}) + "\n",
        encoding="utf-8",
    )

    ozet = dar.topla(cikti)
    assert ozet["tetik"] == 1
    df = ozet["df"]
    assert isinstance(df.loc[0, "kanallar"], tuple)
    metin = dar.rapor_yaz(ozet, cikti, tmp_path / "R.md")
    assert "TÜM TETİKLER" in metin
    # Taban satırı veri yokken de raporda görünür (0 ile).
    assert "TABAN (kontrol)" in metin


def test_rapor_bos_ciktiya_dayanir(tmp_path):
    cikti = tmp_path / "bos"
    cikti.mkdir()
    metin = dar.rapor_yaz(dar.topla(cikti), cikti, tmp_path / "R.md")
    assert "tetik bulunamadı" in metin.lower()
