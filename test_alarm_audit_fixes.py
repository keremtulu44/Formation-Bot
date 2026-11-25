"""Regression tests for alarm subsystem audit fixes."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import config
import deploy_check as dc
from bot.domain_alarm_service import (
    DomainAlarmCandidate,
    _bolge_sebepleri,
    _politika_gecer,
    _zaten_gonderildi,
    dispatch_domain_alarm_candidates,
)
from domain_engines.fvg.fvg_engulfing_final import FvgSideExport
from domain_engines.fvg.fvg_engulfing_models import FvgState
from domain_engines.stabil.runtime import prepare_causal_ohlcv
from notification_context import _alarm_tf_zone, _fiyat_zone_icinde
from public_aux_outbox import PublicAuxOutbox, auxiliary_event_id
from research import alarm_politika


def _wrap_fvg(bull=None, bear=None, quality="OK"):
    return {
        "4h": {
            "fvg": SimpleNamespace(
                skipped=False,
                error=None,
                data_quality=quality,
                export=SimpleNamespace(
                    bull_fvg=bull or FvgSideExport(),
                    bear_fvg=bear or FvgSideExport(),
                ),
            )
        }
    }


def test_fvg_real_engine_reaction_event_triggers_even_without_top_bottom():
    # Real FvgEngulfingEngine clears active FVG on REACTION and exports event=±8
    # with state=None, top=None, bottom=None.
    bull_event = FvgSideExport(state=None, top=None, bottom=None, event=int(FvgState.REACTION))
    bear_event = FvgSideExport(state=None, top=None, bottom=None, event=-int(FvgState.REACTION))
    assert _bolge_sebepleri(_wrap_fvg(bull=bull_event), "4h", 100.0) == ["FVG boğa reaksiyon"]
    assert _bolge_sebepleri(_wrap_fvg(bear=bear_event), "4h", 100.0) == ["FVG ayı reaksiyon"]


@pytest.mark.parametrize("bad_state", [
    int(FvgState.NONE),
    int(FvgState.CANDIDATE),
    int(FvgState.FULL_FILL),
    int(FvgState.FAILED_REACTION),
    int(FvgState.INVALID),
    int(FvgState.SUPERSEDED),
])
def test_fvg_non_active_states_do_not_fire_zone_touch(bad_state):
    side = FvgSideExport(state=bad_state, top=105.0, bottom=95.0, event=0)
    assert _bolge_sebepleri(_wrap_fvg(bull=side), "4h", 100.0) == []


@pytest.mark.parametrize("live_state", [
    int(FvgState.ACTIVE),
    int(FvgState.FIRST_TEST),
    int(FvgState.PARTIAL_FILL),
    int(FvgState.DEEP_TEST),
])
def test_fvg_active_states_inside_price_fire_zone_touch(live_state):
    side = FvgSideExport(state=live_state, top=105.0, bottom=95.0, event=0)
    assert _bolge_sebepleri(_wrap_fvg(bull=side), "4h", 100.0) == ["FVG boğa bölge tepkisi"]


def test_p4_live_and_research_handle_both_5x_and_10x_unicode(monkeypatch):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_POLITIKA", "P4")
    for tier in ("5×", "5x", "10×", "10x"):
        assert _politika_gecer(("hacim 10× (12,0×)",), tier, sikisma=0.5, kosu=0.0) is True
        row = {"kanallar": ["HACIM"], "hacim_tier": tier, "bagl_sikisma": 0.5, "bagl_gunici_kosu": 0.0}
        assert alarm_politika.p_yalniz_hacim(row) is True
        assert alarm_politika.p_katman(row) is True
        assert alarm_politika.p_katman_baglam(row) is True
        assert alarm_politika.p_baglam_veya_hacim(row) is True


def test_stabil_prepare_causal_ohlcv_rejects_string_false_flags():
    idx = pd.date_range("2026-09-01 09:30", periods=5, freq="1D", tz="Europe/Istanbul")
    df = pd.DataFrame({
        "open": [10.0, 11.0, 12.0, 13.0, 14.0],
        "high": [11.0, 12.0, 13.0, 14.0, 15.0],
        "low": [9.0, 10.0, 11.0, 12.0, 13.0],
        "close": [10.5, 11.5, 12.5, 13.5, 14.5],
        "volume": [1000.0] * 5,
        "is_closed": [True, "true", "False", False, True],
        "is_complete": ["True", True, True, True, "false"],
    }, index=idx)
    out, reason = prepare_causal_ohlcv(df, symbol="THYAO", timeframe="1d")
    assert reason is None
    assert len(out) == 2
    assert list(out["close"]) == [10.5, 11.5]


def test_runner_reset_generation_blocks_stale_in_flight_publish(monkeypatch):
    import domain_engines.runner as runner

    idx = pd.date_range("2026-09-01 09:30", periods=40, freq="1h", tz="Europe/Istanbul")
    prices = np.linspace(100.0, 110.0, len(idx))
    df = pd.DataFrame({
        "open": prices,
        "high": prices + 1.0,
        "low": prices - 1.0,
        "close": prices + 0.2,
        "volume": np.full(len(idx), 5000.0),
    }, index=idx)

    runner.reset_incremental_domain_states("TESTGEN")
    orig_ob = runner._run_order_block

    def ob_with_concurrent_reset(*args, **kwargs):
        # Simulate nightly reset firing mid-scan before OB & latest write.
        runner.reset_incremental_domain_states("TESTGEN")
        return orig_ob(*args, **kwargs)

    monkeypatch.setattr(runner, "_run_order_block", ob_with_concurrent_reset)
    runner.run_domain_engines("TESTGEN", "1h", df)
    assert runner.get_latest_domain_results("TESTGEN", "1h") is None
    assert ("TESTGEN", "1h") not in runner._incremental_states_by_series


def test_stabil_evaluate_handles_naive_simdiki_zaman():
    from bot.stabil_service import evaluate_stabil_4h_candidate

    idx_4h = pd.date_range("2026-10-01 09:30", periods=30, freq="4h", tz="Europe/Istanbul")
    idx_1d = pd.date_range("2026-09-01 09:30", periods=35, freq="1D", tz="Europe/Istanbul")
    raw_4h = pd.DataFrame({
        "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 1000.0,
    }, index=idx_4h)
    raw_1d = pd.DataFrame({
        "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 5000.0,
    }, index=idx_1d)
    # Naive datetime in Istanbul wall time (would previously raise TypeError).
    naive_now = datetime(2026, 10, 7, 13, 40)
    res = evaluate_stabil_4h_candidate("THYAO", {"4h": raw_4h, "1d": raw_1d}, naive_now)
    assert res is None or hasattr(res, "symbol")


def test_domain_cooldown_naive_istanbul_and_same_batch_dedup(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_COOLDOWN_BAR", 6)

    bars = [f"2026-11-{day:02d}T10:00:00+03:00" for day in range(1, 10)]
    # Naive slot timestamp representing Istanbul local time matches aware bar[0].
    cand = DomainAlarmCandidate(
        symbol="ASTOR", timeframe="1d",
        bar_open=bars[6], bar_close="2026-11-07T18:30:00+03:00",
        bar_label="07.11 18:30", bar_index=45, close_price=100.0,
        support_level=90.0, dist_atr=1.0, relation="destek üstünde",
        reasons=("BOS ↑",), volume_rvol=2.0, volume_tier=None,
        volume_source="motor", data_quality="OK", card_lines=("Stabil destek: 90,00",),
        rank_score=3.0, recent_bar_opens=tuple(bars[:7]),
    )
    assert _zaten_gonderildi({"last_bar_open": "2026-11-01T10:00:00"}, cand) is False
    assert _zaten_gonderildi({"last_bar_open": "2026-11-02T10:00:00"}, cand) is True

    # Two candidates on the same symbol|tf within cooldown in a single batch:
    # only the top-ranked one should be sent; the other must be suppressed.
    older_cand = DomainAlarmCandidate(
        symbol="ASTOR", timeframe="1d",
        bar_open=bars[5], bar_close="2026-11-06T18:30:00+03:00",
        bar_label="06.11 18:30", bar_index=44, close_price=99.0,
        support_level=90.0, dist_atr=1.0, relation="destek üstünde",
        reasons=("OB boğa bölge tepkisi",), volume_rvol=2.0, volume_tier=None,
        volume_source="motor", data_quality="OK", card_lines=("Stabil destek: 90,00",),
        rank_score=2.0, recent_bar_opens=tuple(bars[:6]),
    )

    class _DummyNotifier:
        enabled = True
        public_enabled = True
        dm = []
        public = []

        def send_text(self, text):
            self.dm.append(text)
            return True

        def send_to_public(self, text):
            self.public.append(text)
            return True

    notifier = _DummyNotifier()
    out = dispatch_domain_alarm_candidates(
        [older_cand, cand], notifier, state_path=str(tmp_path / "state.json"),
    )
    assert out["tekil_gonderilen"] == 1
    assert out["filtrelendi"] == 1


def test_notification_context_alarm_tf_zone_skips_non_active_fvg():
    results = _wrap_fvg(
        bull=FvgSideExport(state=int(FvgState.CANDIDATE), top=105.0, bottom=95.0),
        bear=FvgSideExport(state=int(FvgState.FULL_FILL), top=105.0, bottom=95.0),
    )
    assert _alarm_tf_zone(results, "4h", 100.0) is None
    assert _fiyat_zone_icinde(results, 100.0) is None

    active = _wrap_fvg(
        bull=FvgSideExport(state=int(FvgState.ACTIVE), top=105.0, bottom=95.0),
    )
    assert _alarm_tf_zone(active, "4h", 100.0) == ("FVG", 105.0, 95.0, True)
    assert _fiyat_zone_icinde(active, 100.0) is True


def test_public_aux_outbox_separates_paused_and_rejects_new_disabled_domain(monkeypatch, tmp_path):
    from test_public_aux_outbox import FakeOwner

    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", True)
    owner = FakeOwner(["butce"])
    queue = PublicAuxOutbox(owner, tmp_path)
    existing = auxiliary_event_id("domain", [("A", "4h", "bar1")])
    assert queue.submit(existing, "domain-1") == (True, False)
    assert queue.status() == {"available": True, "pending": 1, "review": 0, "completed": 0}

    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", False)
    st = queue.status()
    assert st["pending"] == 0
    assert st["paused"] == 1
    # Brand-new domain event must not enqueue while YENI_DOMAIN_ALARM=0.
    brand_new = auxiliary_event_id("domain", [("B", "4h", "bar2")])
    assert queue.submit(brand_new, "domain-2") == (False, False)
    assert queue.status()["paused"] == 1


def test_deploy_check_flags_enabled_yeni_domain_alarm_and_invalid_policy(monkeypatch):
    monkeypatch.setattr(dc, "_sayac", {dc.OK: 0, dc.WARN: 0, dc.FAIL: 0})
    base_env = {
        "TELEGRAM_BOT_TOKEN": "123:abc",
        "TELEGRAM_CHAT_ID": "12345",
        "SUPABASE_URL": "https://demo.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_test",
        "YENI_DOMAIN_ALARM": "0",
        "YENI_DOMAIN_ALARM_POLITIKA": "P6",
    }
    dc.kontrol_env(base_env, canli_mod=False)
    warns_clean = dc._sayac[dc.WARN]

    monkeypatch.setattr(dc, "_sayac", {dc.OK: 0, dc.WARN: 0, dc.FAIL: 0})
    dc.kontrol_env({**base_env, "YENI_DOMAIN_ALARM": "1", "YENI_DOMAIN_ALARM_POLITIKA": "P99"}, canli_mod=False)
    assert dc._sayac[dc.WARN] >= warns_clean + 2
