"""dz_yukleme eşleme katmanı birim testleri (ağsız, arşivsiz)."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from scripts.backfill.dz_yukleme import (
    _temizle,
    bars_satirlari,
    boundary_anchored,
    dokunus_satiri,
    event_satiri,
    sema_kolonlari,
    swing_grup_satiri,
    zone_satiri,
)


class SahteBaglam:
    """SeriBaglam'ın sürümlenen arayüzü (duck-typing)."""

    def __init__(self, symbol="TEST", timeframe="1h", bar_sayisi=1000,
                 zamanlar=None, onccekleri=None, ohlc=None):
        self.symbol = symbol
        self.timeframe = timeframe
        self.bar_sayisi = bar_sayisi
        self.first_bar_time = "2025-05-07 10:00:00+03:00"
        self._zamanlar = zamanlar or {}
        self._onccekleri = onccekleri or {}
        self._ohlc = ohlc or {}

    def indeks(self, bar_time):
        if not bar_time:
            return None
        return self._zamanlar.get(bar_time)

    def kapanis_once(self, indeks):
        return self._onccekleri.get(indeks)

    def ohlc(self, indeks):
        return self._ohlc.get(indeks, (None, None, None))


def _zone_ornek(**degisik) -> dict[str, Any]:
    taban = {
        "zone_id": "TEST|OB|1h|bullish|100|10|11",
        "symbol": "TEST", "timeframe": "1h", "family": "OB", "direction": "bullish",
        "dogum_bar_time": "2025-06-01 10:00:00+03:00", "dogum_index": 100,
        "zone_lower": 10.0, "zone_upper": 11.0, "yukseklik_fiyat": 1.0,
        "yukseklik_atr": 0.8, "atr_at_birth": 1.25,
        "native_terminal_state": "REMOVED_BY_NATIVE_LIFECYCLE",
        "native_terminal_reason": "gap_through", "native_terminal_category": "GAP_THROUGH",
        "native_price_violation": True, "native_full_fill": False,
        "terminal_bar_time": "2025-06-02 11:00:00+03:00",
        "sansur": False, "engine_version": "arastirma-olcum-v1", "config_hash": "abc123",
    }
    taban.update(degisik)
    return taban


def _dokunus_ornek(**degisik) -> dict[str, Any]:
    taban = {
        "episode_id": "EP1", "zone_id": "TEST|OB|1h|bullish|100|10|11",
        "symbol": "TEST", "timeframe": "1h", "family": "OB", "direction": "bullish",
        "dokunus_no": 2, "dokunus_baslangic_bar_time": "2025-06-05 10:00:00+03:00",
        "dokunus_bitis_bar_time": "2025-06-05 14:00:00+03:00",
        "dokunus_bar_sayisi": 5, "arrival_side": "FROM_BELOW",
        "approach_direction": "UP_TOWARD_ZONE", "atr_at_touch": 1.1,
        "repoh10_full_window_favorable_excursion_atr": 1.5,
        "repoh10_full_window_adverse_excursion_atr": 0.4,
        "repoh12_full_window_favorable_excursion_atr": 2.0,
        "repoh12_full_window_adverse_excursion_atr": 0.6,
        "repoh12_window_status": "COMPLETE", "repoh12_window_complete": True,
        "kenar_h10": 0.3, "kenar_h12": 0.5,
        "yon_tepe_atr": 2.2, "yon_tepe_bar": 7.0, "yon_pay_1": 0.1,
        "yon_pay_3": 0.5, "yon_pay_5": 0.9, "yon_h10_decay": 0.25,
        "yon_h10": 1.5, "yon_h12": 2.0, "gozlenen_bar": 40,
        "terminal_dokunusta": False, "vp_data_ready": True, "vp_volume_usable": False,
        "vp_rvol": 0.9, "engine_version": "arastirma-olcum-v1", "config_hash": "abc123",
    }
    taban.update(degisik)
    return taban


def _swing_satir(**degisik) -> dict[str, Any]:
    taban = {
        "scope": "EXTERNAL", "identity": 3, "side": "LOW",
        "structural_role_final": "NEUTRAL_LOW", "rol": None,
        "swing_class": "PL", "state": "SWING_CONFIRMED",
        "finalized": True, "locked": True,
        "source_bar": 10, "source_bar_time": "2025-06-01 10:00:00+03:00",
        "confirm_bar": 14, "confirm_bar_time": "2025-06-01 15:00:00+03:00",
        "price": 14.57, "atr_at_source": 0.2, "prominence_atr": 1.1,
        "distance_atr": 0.95, "quality": 0.7,
        "broken": False, "broken_bar": None, "broken_bar_time": None,
        "bars_to_break": None, "bars_to_break_sansur": True,
        "deneme_epizot_025": 2.0, "deneme_epizot_015": 4.0, "deneme_epizot_050": 1.0,
        "engelledi_025": True, "red_magnitude_atr": None, "max_yaklasma_atr": -0.1,
        "engine_version": "arastirma-olcum-v1", "config_hash": "abc123",
    }
    taban.update(degisik)
    return taban


def _event_ornek(**degisik) -> dict[str, Any]:
    taban = {
        "event_uid": "EXTERNAL:7", "identity": 7, "scope": "EXTERNAL",
        "event_type": "EVENT_BOS", "direction": "UP",
        "candidate_bar": 20, "candidate_bar_time": "2025-06-02 09:00:00+03:00",
        "event_bar": 24, "event_bar_time": "2025-06-02 14:00:00+03:00",
        "broken_level": 15.5, "broken_swing_identity": 3,
        "origin_price": 14.9, "quality": 0.8,
        "confirmation_status": "CONFIRMED", "validity": "VALID",
        "relevance": "CURRENT", "outcome": "PENDING", "bos_maturity": "INITIAL_STRUCTURE",
        "age_bars": 5, "confirmed_by": None, "failed_by": None,
        "referans_kapanis": 16.73, "atr_at_event": 0.24,
        "devam_h10": 3.1, "devam_h12": 3.3, "ters_h12": 0.3,
        "devam_tepe_bar": 8.0, "devam_pay_5": 0.4, "devam_h12_decay": 0.7,
        "devamlilik_sinifi": "CALISTI", "sansur": False,
        "vp_data_ready": True, "vp_volume_usable": True, "vp_rvol": 1.4,
        "engine_version": "arastirma-olcum-v1", "config_hash": "abc123",
    }
    taban.update(degisik)
    return taban


# ---------------------------------------------------------------------------
# boundary_anchored
# ---------------------------------------------------------------------------

def test_boundary_anchored_kurallari() -> None:
    assert boundary_anchored("FROM_ABOVE") == "UST"
    assert boundary_anchored("FROM_BELOW") == "ALT"
    assert boundary_anchored("INSIDE_ZONE") == "BELIRSIZ"
    assert boundary_anchored("ON_ZONE_BOUNDARY") == "BELIRSIZ"
    assert boundary_anchored("NO_PREVIOUS_BAR") == "BELIRSIZ"
    assert boundary_anchored(None) == "BELIRSIZ"


# ---------------------------------------------------------------------------
# zone
# ---------------------------------------------------------------------------

def test_zone_esleme_ve_k1() -> None:
    ctx = SahteBaglam()
    satir = zone_satiri(_zone_ornek(), ctx, "run-1")
    assert satir["atr_at_dogum"] == 1.25          # atr_at_birth → atr_at_dogum
    assert satir["dogum_bar_index"] == 100        # dogum_index → dogum_bar_index
    assert satir["yukseklik"] == 1.0              # yukseklik_fiyat → yukseklik
    assert satir["terminal_state"] == "REMOVED_BY_NATIVE_LIFECYCLE"
    assert satir["pencere_ilk_bar"] == ctx.first_bar_time
    assert satir["pencere_bar_sayisi"] == ctx.bar_sayisi
    assert satir["kaynak"] == "backfill" and satir["run_id"] == "run-1"
    assert "T" not in satir["dogum_bar_time"]     # K1
    # şemada olmayan kaynak anahtarları sızmaz
    assert "temas_var" not in satir and "native_fill_ratio" not in satir


# ---------------------------------------------------------------------------
# dokunus
# ---------------------------------------------------------------------------

def test_dokunus_esleme() -> None:
    zaman = {"2025-06-05 10:00:00+03:00": 50, "2025-06-05 14:00:00+03:00": 54}
    ctx = SahteBaglam(zamanlar=zaman, onccekleri={50: 10.75})
    satir = dokunus_satiri(_dokunus_ornek(), ctx, "run-1")
    assert satir["touch_id"] == "TEST|OB|1h|bullish|100|10|11|touch2|2025-06-05 10:00:00+03:00"
    assert satir["touch_start_index"] == 50 and satir["touch_end_index"] == 54
    assert satir["arrival_previous_close"] == 10.75
    assert satir["boundary_anchored"] == "ALT"    # FROM_BELOW → ALT
    assert satir["favorable_atr_h10"] == 1.5      # repoh10 favorabl
    assert satir["adverse_atr_h12"] == 0.6        # repoh12 adverse
    assert satir["horizon_10_12_farki"] == 0.5    # 2.0 − 1.5
    assert satir["observed_post_touch_bars"] == 12  # min(12, 40)
    assert satir["status"] == "COMPLETE"          # repoh12_window_status
    assert satir["decay_ratio"] == 0.25           # yon_h10_decay (şema: tepe−h10 sonu)
    assert satir["peak_excursion_atr"] == 2.2 and satir["bars_to_peak"] == 7
    assert "T" not in satir["touch_start"]        # K1
    assert satir["vp_volume_usable"] is False     # bayrak korunur (düşürülmez)


def test_dokunus_sansurlu_pencere() -> None:
    ctx = SahteBaglam()
    satir = dokunus_satiri(
        _dokunus_ornek(
            gozlenen_bar=4, repoh12_window_status="RIGHT_CENSORED_DATA_END",
            repoh12_window_complete=False,
            repoh10_full_window_favorable_excursion_atr=None,
            repoh12_full_window_favorable_excursion_atr=None,
        ),
        ctx, "run-1",
    )
    assert satir["observed_post_touch_bars"] == 4
    assert satir["status"] == "RIGHT_CENSORED_DATA_END"
    assert satir["horizon_10_12_farki"] is None   # fav eksik → None


# ---------------------------------------------------------------------------
# swing
# ---------------------------------------------------------------------------

def test_swing_indirgeme_rol_ve_sansur() -> None:
    ctx = SahteBaglam()
    grup = [
        _swing_satir(rol=None, rol_ilk_bar=None),
        _swing_satir(rol="PROTECTED_LOW", rol_ilk_bar=30, deneme_epizot_025=2.0),
        _swing_satir(rol="NEUTRAL_LOW", rol_ilk_bar=80, deneme_epizot_025=5.0),
    ]
    satir = swing_grup_satiri(grup, ctx, "run-1")
    assert satir["swing_id"] == "TEST:1h:external:low:2025-06-01 15:00:00+03:00:14.57"
    assert satir["scope"] == "external"           # şema: external | internal
    assert satir["side"] == "low"                 # şema: high | low
    assert satir["structural_role"] == "PROTECTED_LOW"  # ilk atanan rol
    assert satir["deneme_025_atr"] == 2           # tam sayı (JSONL float)
    assert satir["sansur"] == "SAGDAN_SANSURLU"   # kırılmamış → sağdan sansür
    assert satir["engelledi"] is True


def test_swing_kirilmis_yok_sansur() -> None:
    ctx = SahteBaglam()
    satir = swing_grup_satiri(
        [_swing_satir(bars_to_break_sansur=False, broken=True, broken_bar=90,
                      broken_bar_time="2025-06-03 10:00:00+03:00", bars_to_break=76)],
        ctx, "run-1",
    )
    assert satir["sansur"] == "YOK"
    assert satir["broken"] is True and satir["bars_to_break"] == 76


# ---------------------------------------------------------------------------
# event
# ---------------------------------------------------------------------------

def test_event_yon_status_ve_kimlik() -> None:
    zaman = {"2025-06-02 14:00:00+03:00": 24, "2025-06-02 09:00:00+03:00": 20}
    ctx = SahteBaglam(zamanlar=zaman, ohlc={24: (16.9, 16.5, 16.73)})
    kaynak = {("external", 3): (10, "2025-06-01 10:00:00+03:00")}
    satir = event_satiri(_event_ornek(), ctx, "run-1", kaynak)
    assert satir is not None
    assert satir["event_id"] == "TEST:1h:external:EVENT_BOS:2025-06-02 14:00:00+03:00:15.5"
    assert satir["direction"] == 1                # UP → +1
    assert satir["status"] == "COMPLETE"
    assert satir["candidate_at"] == "2025-06-02 09:00:00+03:00"
    assert satir["confirmed_at"] == "2025-06-02 14:00:00+03:00"
    assert satir["confirmation_high"] == 16.9 and satir["confirmation_low"] == 16.5
    assert satir["broken_source_bar"] == 10       # swing defterinden join
    assert satir["follow_atr_h10"] == 3.1 and satir["follow_atr_h12"] == 3.3
    assert "T" not in satir["confirmed_at"]       # K1


def test_event_asagi_yon_ve_sansur() -> None:
    ctx = SahteBaglam()
    kaynak: dict = {}
    satir = event_satiri(_event_ornek(direction="DOWN", sansur=True), ctx, "run-1", kaynak)
    assert satir["direction"] == -1
    assert satir["status"] == "RIGHT_CENSORED_DATA_END"
    assert satir["broken_source_bar"] is None     # join bulunamadı → None


def test_event_onay_bar_yoksa_atlanir() -> None:
    ctx = SahteBaglam()
    satir = event_satiri(_event_ornek(event_bar_time=None, event_bar=None), ctx, "run-1", {})
    assert satir is None                           # confirmed_at NOT NULL


# ---------------------------------------------------------------------------
# bars
# ---------------------------------------------------------------------------

def test_bars_k5_bayraklari_ve_k1() -> None:
    df = pd.DataFrame({
        "bar_time": [
            "2025-06-01 10:00:00+03:00",
            "2025-06-02 10:00:00+03:00",   # split: open 100 → 130 (prev close 100)
            "2025-06-03 10:00:00+03:00",   # sıfır hacim + NaN low
        ],
        "open": [100.0, 130.0, 133.0],
        "high": [105.0, 135.0, 136.0],
        "low": [99.0, 128.0, float("nan")],
        "close": [100.0, 132.0, 134.0],
        "volume": [10.0, 12.0, 0.0],
    })
    df["interval"] = "1h"
    satirlar = bars_satirlari("TEST", df, "run-1")
    assert len(satirlar) == 3
    assert satirlar[0]["split_adayi"] is False     # ilk bar: önceki yok
    assert satirlar[1]["split_adayi"] is True      # %30 sıçrama > %10
    assert satirlar[2]["split_adayi"] is False
    assert satirlar[2]["sifir_hacim"] is True
    assert satirlar[2]["nan_ohlc"] is True and satirlar[2]["low"] is None
    assert "T" not in satirlar[0]["bar_time"]      # K1
    assert all(s["kaynak"] == "backfill" and s["run_id"] == "run-1" for s in satirlar)


# ---------------------------------------------------------------------------
# şema sözlüğü
# ---------------------------------------------------------------------------

def test_sema_kolonlari_tam() -> None:
    sema = sema_kolonlari()
    assert len(sema["dz_bars"]) == 14
    assert len(sema["dz_zones"]) == 43
    assert len(sema["dz_zone_touches"]) == 60
    assert len(sema["dz_ms_swings"]) == 41
    assert len(sema["dz_ms_events"]) == 53
    # NOT NULL kolonların hepsi eşleme sözlüğünde üretiliyor
    zone = zone_satiri(_zone_ornek(), SahteBaglam(), "r")
    for kolon in ("symbol", "timeframe", "family", "direction", "dogum_bar_time",
                  "zone_lower", "zone_upper", "sansur", "kaynak"):
        assert zone.get(kolon) is not None, kolon


def test_temizle_alt_cizgi_anahtarlarini_dusurur() -> None:
    assert _temizle({"a": 1, "_yon_h10": 2}) == {"a": 1}


def test_jsonl_cikti_gecerli() -> None:
    satir = dokunus_satiri(_dokunus_ornek(), SahteBaglam(), "r")
    geri = json.loads(json.dumps(_temizle(satir), ensure_ascii=False))
    assert geri["touch_id"].startswith("TEST|OB")
