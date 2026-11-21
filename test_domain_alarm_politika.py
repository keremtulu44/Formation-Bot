"""Alarm politikası (P0/P6/P4) canlı filtre regresyonları.

Ölçüm: research/alarm_politika.py + docs/arastirma/ALARM_POLITIKA_PILOTU.md.
Canlı uygulama: bot/domain_alarm_service.py::_politika_gecer.
Replay ile birebirlik: sikisma/kosu formülleri baglam_satiri ile aynı;
ATR Wilder 14 (canlı _causal_atr14 == replay compute_wilder_atr, son barda).
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

import config
from bot.domain_alarm_service import (
    _baglam_sikisma_kosu,
    _kanallar_from_sebepler,
    _politika_gecer,
    evaluate_domain_alarm_candidates,
)

ISTANBUL_TZ = config.ISTANBUL_TZ
SIMDI = pd.Timestamp("2026-11-03 19:00", tz=ISTANBUL_TZ).to_pydatetime()


@pytest.fixture(autouse=True)
def _politika_varsayilan(monkeypatch):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_DM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_PUBLIC", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_DIST_ATR_ALT", -3.0)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_HACIM_5X", 5.0)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_HACIM_10X", 10.0)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_HACIM_SUPHE", 50.0)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_TAZE_DK", 10000)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_COOLDOWN_BAR", 6)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_TEKIL_UST_SINIR", 3)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_IMMEDIATE_TEKRAR", True)
    monkeypatch.setattr(config, "MAKRO_ALARM", False)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_POLITIKA", "P0")
    monkeypatch.setattr(
        config, "ALERT_STATES",
        ("KIRILIM_TEYITLI", "RETEST_BASARILI", "KIRILIM_GECERSIZLESTI"),
    )


def _frame(n: int = 60, close: float = 100.0, *, daralan: bool = False,
           kosu_yukari: bool = False) -> pd.DataFrame:
    """60 barlık çerçeve; daralan=son 10 dar, kosu_yukari=son 6 güçlü yukarı."""
    index = pd.date_range("2026-09-01 10:00", periods=n, freq="D", tz=ISTANBUL_TZ)
    closes = [close] * n
    highs = [close + 1.0] * n
    lows = [close - 2.0] * n
    if daralan:
        # Son 10 bar dar (aralık 0.6), önceki 40 geniş (aralık 3.0) → sikisma ~0.2
        for i in range(n - 10, n):
            highs[i] = close + 0.3
            lows[i] = close - 0.3
    if kosu_yukari:
        # Son 6 bar güçlü yukarı: kapanış 100 → 106 (ATR ~1-2 → kosu >> 1)
        for j, i in enumerate(range(n - 6, n), start=1):
            closes[i] = close + float(j)
            highs[i] = closes[i] + 1.0
            lows[i] = closes[i] - 2.0
    return pd.DataFrame(
        {
            "open": [c - 1.0 for c in closes],
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1000.0] * n,
        },
        index=index,
    )


# --- _baglam_sikisma_kosu ----------------------------------------------------

def test_sikisma_kosu_yatay_cerceve():
    sikisma, kosu = _baglam_sikisma_kosu(_frame(60))
    assert sikisma == pytest.approx(1.0)
    assert kosu == pytest.approx(0.0)


def test_sikisma_daralan_cerceve():
    sikisma, kosu = _baglam_sikisma_kosu(_frame(60, daralan=True))
    assert sikisma is not None and sikisma < 1.0
    assert kosu == pytest.approx(0.0)


def test_kosu_guclu_yukari():
    _, kosu = _baglam_sikisma_kosu(_frame(60, kosu_yukari=True))
    assert kosu is not None and kosu >= 1.0


def test_kisa_cerceve_sikisma_none_fail_open():
    # 30 bar: sikisma için 50 bar yok → None (politika 1.0 sayar → geçer)
    sikisma, _ = _baglam_sikisma_kosu(_frame(30))
    assert sikisma is None


def test_bos_cerceve_none():
    assert _baglam_sikisma_kosu(pd.DataFrame()) == (None, None)


def test_atr_14_bar_esigi_replay_ile_ayni():
    """Replay `compute_wilder_atr` ilk ATR'yi 14. barda üretir (index 13).

    11 bar: canlı kosu üretmemeli (replay None der). 14 bar: ikisi de üretmeli.
    """
    from directional_zone_replay import compute_wilder_atr

    _, kosu_11 = _baglam_sikisma_kosu(_frame(11, kosu_yukari=True))
    assert kosu_11 is None

    frame = _frame(14, kosu_yukari=True)
    _, kosu_14 = _baglam_sikisma_kosu(frame)
    assert kosu_14 is not None
    atr = compute_wilder_atr(frame)[-1]
    beklenen = round(float(frame["close"].iloc[-1] - frame["close"].iloc[-7]) / atr, 4)
    assert kosu_14 == pytest.approx(beklenen, abs=1e-3)


# --- _kanallar_from_sebepler -------------------------------------------------

def test_kanal_esleme():
    sebepler = ["BOS ↑", "OB boğa bölge tepkisi", "FVG ayı reaksiyon",
                "formasyon: Üçgen · KIRILIM", "hacim 5×"]
    assert _kanallar_from_sebepler(sebepler) == frozenset(
        {"BOS", "OB", "FVG", "FORMASYON", "HACIM"}
    )
    assert _kanallar_from_sebepler(["CHoCH ↓"]) == frozenset({"CHoCH"})
    assert _kanallar_from_sebepler([]) == frozenset()


# --- _politika_gecer ---------------------------------------------------------

def test_p0_her_zaman_gecer(monkeypatch):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_POLITIKA", "P0")
    assert _politika_gecer(["OB boğa bölge tepkisi"], None, 0.2, 0.0) is True


def test_p6_baglam_kurali(monkeypatch):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_POLITIKA", "P6")
    # Sıkışma geniş → geçer
    assert _politika_gecer(["OB boğa bölge tepkisi"], None, 1.2, 0.0) is True
    # Koşu yukarı → geçer
    assert _politika_gecer(["OB boğa bölge tepkisi"], None, 0.5, 1.5) is True
    # İkisi de zayıf → elenir
    assert _politika_gecer(["OB boğa bölge tepkisi"], None, 0.5, 0.5) is False
    # Sikisma None → 1.0 sayılır → geçer (fail-open, replay ile aynı)
    assert _politika_gecer(["OB boğa bölge tepkisi"], None, None, 0.0) is True
    # Kosu None → 0.0; sikisma zayıfsa elenir
    assert _politika_gecer(["OB boğa bölge tepkisi"], None, 0.5, None) is False


def test_p4_katman_ve_baglam(monkeypatch):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_POLITIKA", "P4")
    # Yalnız OB + bağlam zayıf → elenir (katman)
    assert _politika_gecer(["OB boğa bölge tepkisi"], None, 0.5, 0.5) is False
    # Yalnız OB + bağlam güçlü → yine elenir (katman bağlamı baypas etmez)
    assert _politika_gecer(["OB boğa bölge tepkisi"], None, 1.5, 1.5) is False
    # OB + formasyon + bağlam güçlü → geçer
    assert _politika_gecer(
        ["OB boğa bölge tepkisi", "formasyon: Üçgen · KIRILIM"], None, 1.5, 0.0
    ) is True
    # Hacim ≥5× bağlamı baypas eder
    assert _politika_gecer(["OB boğa bölge tepkisi"], "5×", 0.5, 0.5) is True
    # BOS + OB (ikisi de zayıf kümede) → elenir
    assert _politika_gecer(["BOS ↑", "OB boğa bölge tepkisi"], None, 1.5, 1.5) is False


def test_tanimli_politika_p0a_duser(monkeypatch):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_POLITIKA", "BOGUS")
    assert _politika_gecer(["OB boğa bölge tepkisi"], None, 0.5, 0.5) is True


# --- Entegrasyon: evaluate ---------------------------------------------------

def _behavior(*, dist_atr: float, support: float, close: float = 100.0):
    return SimpleNamespace(
        dist_atr=dist_atr, support_level=support, close_price=close,
        pct_vs_support=(close - support) / support if support else 0.0,
        unchanged_days=30, touch_count=1, vol_ratio=1.2,
        reclaim_kind=None, momentum_kind=None, weak_reclaim=False,
        fixed_support=support, regime="LONG_HORIZONTAL",
    )


def _sonuclar_ob(*, close: float = 100.0):
    bhv = _behavior(dist_atr=1.0, support=90.0, close=close)
    return {
        "1d": {
            "stabil": SimpleNamespace(
                skipped=False, error=None, data_quality="OK",
                details={
                    "latest_behavior": bhv,
                    "latest_support_relation": "destek üstünde",
                    "bar_projection": [SimpleNamespace(support_level=90.0)],
                },
                result=None, export=None,
            ),
            "market_structure": SimpleNamespace(
                skipped=False, error=None, export=SimpleNamespace(events=[]),
            ),
            "volume_participation": SimpleNamespace(
                skipped=False, error=None,
                export=SimpleNamespace(rvol=1.0),
                details={"latest_metrics": SimpleNamespace(volume_usable=True)},
            ),
            "order_block": SimpleNamespace(
                skipped=False, error=None,
                export=SimpleNamespace(
                    bull=SimpleNamespace(top=105.0, bottom=95.0, state=None),
                    bear=SimpleNamespace(top=150.0, bottom=145.0, state=None),
                ),
            ),
            "fvg": SimpleNamespace(
                skipped=False, error=None,
                export=SimpleNamespace(
                    bull_fvg=SimpleNamespace(top=130.0, bottom=125.0, state=2),
                    bear_fvg=SimpleNamespace(top=160.0, bottom=155.0, state=3),
                ),
            ),
        }
    }


def test_evaluate_p6_daralan_yatay_elenir(monkeypatch):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_POLITIKA", "P6")
    frame = _frame(60, daralan=True)
    adaylar = evaluate_domain_alarm_candidates(
        "ASTOR", {}, {"1d": frame}, _sonuclar_ob(), SIMDI,
    )
    assert adaylar == []


def test_evaluate_p0_ayni_cerceve_gecer(monkeypatch):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_POLITIKA", "P0")
    frame = _frame(60, daralan=True)
    adaylar = evaluate_domain_alarm_candidates(
        "ASTOR", {}, {"1d": frame}, _sonuclar_ob(), SIMDI,
    )
    assert len(adaylar) == 1
    assert any(s.startswith("OB") for s in adaylar[0].reasons)


def test_evaluate_p6_kosu_gecer(monkeypatch):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_POLITIKA", "P6")
    frame = _frame(60, daralan=True, kosu_yukari=True)
    # OB bandı 95-105; son kapanış 106 → bant dışında! Bandı son fiyata göre ayarla.
    # Basitlik için OB tepkisini FVG reaksiyonu ile üretelim (fiyat bağımsız).
    sonuclar = _sonuclar_ob(close=106.0)
    sonuclar["1d"]["fvg"].export.bull_fvg = SimpleNamespace(
        top=120.0, bottom=100.0, state=8
    )
    adaylar = evaluate_domain_alarm_candidates(
        "ASTOR", {}, {"1d": frame}, sonuclar, SIMDI,
    )
    assert len(adaylar) == 1


def test_evaluate_p4_yalniz_ob_elenir(monkeypatch):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_POLITIKA", "P4")
    frame = _frame(60, kosu_yukari=True)  # bağlam güçlü ama katman yalnız OB
    sonuclar = _sonuclar_ob(close=106.0)
    sonuclar["1d"]["order_block"].export.bull = SimpleNamespace(
        top=110.0, bottom=100.0, state=None
    )
    adaylar = evaluate_domain_alarm_candidates(
        "ASTOR", {}, {"1d": frame}, sonuclar, SIMDI,
    )
    assert adaylar == []
