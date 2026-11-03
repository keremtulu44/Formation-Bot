"""Stabil güçlü YUKARI mum okları + kadraj/causal OHLCV regresyonları.

Kapsam:
1. `▲` yalnız destek geri alımına değil, replay eşikli güçlü yukarı muma da gelir.
2. Destek yukarı basamak yapıp `fixed_support=False` olduğu barda işaret kaybolmaz.
3. Domain projeksiyonu grafikten kısa/cleaned ise ok, kapanış zamanıyla hizalanır.
4. `prepare_causal_ohlcv` NaN satırdan sonra `is_closed/is_complete` maskelerini kaydırmaz.
5. Yeni sınıflandırma gelecekteki mumu görmez.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Sequence

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd

from data import mum_kapanis_anlari
from domain_engines.stabil import (
    STABIL_GUCLU_YUKARI_MOMENTUM_TURLERI,
    SupportBarPoint,
    StabilSupportLifecycleSnapshot,
    SupportDynamics,
    SupportProgression,
    SupportValidity,
    evaluate_bar_behaviors,
    prepare_causal_ohlcv,
)
from grafik.render import _stabil_ciz
from grafik.tarama import _stabil_verisi

_IST = "Europe/Istanbul"


def _zamanlar(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-09-01", periods=n, freq="D", tz=_IST)


def _kapanis_zamanlari(labels: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return list(mum_kapanis_anlari(pd.DatetimeIndex(labels), "1d"))


def _snapshot(as_of: pd.Timestamp, level: float, age: int,
              progression: SupportProgression) -> StabilSupportLifecycleSnapshot:
    return StabilSupportLifecycleSnapshot(
        as_of=as_of,
        support_level=level,
        support_floor=level - 5.0,
        support_origin_at=as_of,
        support_confirmed_at=as_of,
        support_available_at=as_of,
        validity=SupportValidity.ACTIVE,
        dynamics=SupportDynamics.FLAT,
        progression=progression,
        distance_pct=None,
        distance_atr=None,
        distance_delta_atr=None,
        bars_since_support=age,
        bars_above_support=age,
        bars_below_support=0,
        reclaim_count=0,
        intrabar_below_support=False,
        close_below_support=False,
        close_below_floor=False,
        events=(),
    )


def _projeksiyon(close_times: Sequence[pd.Timestamp], levels: Sequence[float],
                 progressions: Sequence[SupportProgression],
                 daily_as_of: pd.Timestamp) -> tuple[SupportBarPoint, ...]:
    return tuple(
        SupportBarPoint(
            bar_index=i,
            bar_close_time=close_times[i],
            daily_as_of=daily_as_of,
            support_level=levels[i],
            validity=SupportValidity.ACTIVE,
            dynamics=SupportDynamics.FLAT,
            progression=progressions[i],
            color_role="above",
        )
        for i in range(len(close_times))
    )


def _cerceve(step_up: bool, ek_bar: bool = False) -> pd.DataFrame:
    """29 sakin bar + son barda güçlü gövdeli/tepede kapanan hacimli alıcı mumu."""
    rows = [{
        "open": 100.4, "high": 101.1, "low": 99.6,
        "close": 100.6, "volume": 100.0,
    } for _ in range(29)]
    if step_up:
        rows.append({
            "open": 101.4, "high": 102.3, "low": 101.3,
            "close": 102.2, "volume": 250.0,
        })
    else:
        rows.append({
            "open": 100.8, "high": 101.7, "low": 100.7,
            "close": 101.6, "volume": 250.0,
        })
    if ek_bar:
        rows.append({
            "open": 101.6, "high": 101.9, "low": 100.9,
            "close": 101.1, "volume": 90.0,
        })
    return pd.DataFrame(rows)


def _senkron(step_up: bool, *, ek_bar: bool = False):
    n = 31 if ek_bar else 30
    labels = _zamanlar(n)
    closes = _kapanis_zamanlari(labels)
    timeline = tuple(
        _snapshot(
            closes[i],
            101.0 if step_up and i == 29 else 100.0,
            0 if step_up and i == 29 else i,
            SupportProgression.REBASED_HIGHER if step_up and i == 29 else SupportProgression.SAME,
        )
        for i in range(n)
    )
    levels = [101.0 if step_up and i == 29 else 100.0 for i in range(n)]
    progressions = [
        SupportProgression.REBASED_HIGHER if step_up and i == 29 else SupportProgression.SAME
        for i in range(n)
    ]
    projection = _projeksiyon(closes, levels, progressions, timeline[-1].as_of)
    frame = _cerceve(step_up, ek_bar=ek_bar)
    return labels, closes, timeline, projection, frame


def _davranislar(step_up: bool, *, ek_bar: bool = False):
    _labels, _closes, timeline, projection, frame = _senkron(step_up, ek_bar=ek_bar)
    return evaluate_bar_behaviors(
        "ASTOR", "1d", frame, projection, timeline, min_tick=0.01,
    )


def test_guclu_yukari_mum_uzun_yatay_zeminde_ok_uretir_ve_geri_alim_degildir():
    bhvs = _davranislar(step_up=False)
    isaretli = [i for i, b in enumerate(bhvs) if b.momentum_kind is not None]
    assert isaretli == [len(bhvs) - 1]
    son = bhvs[-1]
    assert son.momentum_kind in STABIL_GUCLU_YUKARI_MOMENTUM_TURLERI
    assert son.momentum_kind == "long_base_breakout"
    assert son.reclaim_kind is None and not son.weak_reclaim
    assert son.fixed_support is True


def test_guclu_yukari_mum_destek_yukari_basamak_yaparken_kaybolmaz():
    bhvs = _davranislar(step_up=True)
    isaretli = [i for i, b in enumerate(bhvs) if b.momentum_kind is not None]
    assert isaretli == [len(bhvs) - 1]
    son = bhvs[-1]
    assert son.momentum_kind == "upward_rebase_momentum"
    assert son.reclaim_kind is None and not son.weak_reclaim
    # Asıl regresyon: güçlü mum yeni basamağın geldiği barda `fixed_support=False`.
    assert son.fixed_support is False


def test_momentum_sinifi_gelecekteki_mumu_gormez():
    once = _davranislar(step_up=False)
    sonra = _davranislar(step_up=False, ek_bar=True)
    assert [b.momentum_kind for b in sonra[:len(once)]] == [b.momentum_kind for b in once]
    assert [b.reclaim_kind for b in sonra[:len(once)]] == [b.reclaim_kind for b in once]


def test_momentum_oklari_cizime_ve_meta_ya_tasir():
    bhvs = _davranislar(step_up=False)
    n = len(bhvs)
    katman = {
        "hazir": True,
        "seviyeler": [100.0] * n,
        "renkler": ["ust"] * n,
        "reclaim_barlar": [],
        "momentum_barlar": [n - 1],
        "son_seviye": 100.0,
        "son_renk": "ust",
    }
    fig, ax = plt.subplots()
    try:
        meta = _stabil_ciz(
            ax, {"stabil": katman}, n, (98.0, 104.0),
            dusuk=[99.6] * (n - 1) + [100.7],
        )
        assert meta["cizildi"] is True
        assert meta["momentum_isaret"] == 1
        assert meta["reclaim_isaret"] == 0
        assert any(c.get_gid() == "grafik-stabil-momentum" for c in ax.collections)
    finally:
        plt.close(fig)


def test_kisa_domain_projeksiyonu_kapanis_zamaniyla_hizalanir():
    labels, closes, timeline, projection, frame = _senkron(step_up=False)
    bhvs = evaluate_bar_behaviors(
        "ASTOR", "1d", frame, projection, timeline, min_tick=0.01,
    )
    # Grafikte 2 ek ileri mum var; domain kesimi ilk 30 kapalı mumda bitiyor.
    genis_labels = _zamanlar(32)
    assert list(genis_labels[:30]) == list(labels)
    kayit = SimpleNamespace(
        error=None,
        skipped=False,
        details={
            "bar_projection": projection,
            "bar_behaviors": bhvs,
            "latest_support_relation": "destek üstünde",
        },
    )
    gorunen_zamanlar = list(genis_labels[2:32])
    st = _stabil_verisi({"stabil": kayit}, "1d", 2, 32, gorunen_zamanlar)
    assert st is not None and st["hazir"] is True
    # Son güçlü mum projeksiyon indeksi 29 -> görünür kadraj indeksi 27.
    assert st["momentum_barlar"] == [27]
    assert st["reclaim_barlar"] == []
    assert st["seviyeler"][-2:] == [None, None], "Kesim sonrası destek uydurulmamalı"


def test_prepare_causal_ohlcv_flag_maskeleri_nan_satirdan_sonra_kaymaz():
    labels = _zamanlar(5)
    raw = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [101.0, np.nan, 103.0, 104.0, 105.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "volume": [100.0] * 5,
            "is_closed": [True, True, False, True, True],
            "is_complete": [True, True, True, False, True],
        },
        index=labels,
    )
    out, err = prepare_causal_ohlcv(raw, symbol="ASTOR", timeframe="1d")
    assert err is None
    # 1 NaN, 2 kapalı değil, 3 tamamlanmamış; yalnız 0 ve 4 kalır.
    assert out["close"].tolist() == [100.5, 104.5]
    assert "_source_row" not in out.columns
    assert bool(out["is_closed"].all()) and bool(out["is_complete"].all())
