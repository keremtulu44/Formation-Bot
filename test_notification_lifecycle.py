from datetime import datetime
from types import SimpleNamespace

import main as main_module
from config import ISTANBUL_TZ, TERMINAL_TAZE_BAR


def _event(kind, state, bar, when, stable_id="formation-1", direction=1, price=101.0):
    return {
        "type": kind,
        "state": state,
        "bar": bar,
        "time": when.isoformat(),
        "stable_id": stable_id,
        "direction": direction,
        "quality": 82.0,
        "price": price,
    }


def _snapshot(events, *, state="BASARISIZ_KIRILIM", reason="Kırılım sonrası formasyon alanına dönüldü",
              bar_index=None):
    return SimpleNamespace(
        events=events,
        state=state,
        invalid_reason=reason,
        bar_index=bar_index if bar_index is not None else max(event["bar"] for event in events),
    )


def test_unconfirmed_break_failure_is_not_classified_as_invalidation():
    now = datetime.now(ISTANBUL_TZ)
    snap = _snapshot([
        _event("BREAK_CANDIDATE", "KIRILIM_ADAYI", 10, now),
        _event("BREAK_FAILED", "BASARISIZ_KIRILIM", 11, now, price=99.0),
    ])

    classified = main_module._classified_lifecycle_events(snap)

    assert [state for state, _event, _time in classified] == []
    assert main_module._invalidation_event_for_snapshot(
        snap, SimpleNamespace(stable_id="formation-1")
    ) is None


def test_only_a_later_same_formation_confirmed_return_inside_is_invalidation():
    now = datetime.now(ISTANBUL_TZ)
    confirmed = _event("BREAK_CONFIRMED", "KIRILIM_TEYITLI", 10, now, price=102.0)
    invalidation = _event("BREAK_FAILED", "BASARISIZ_KIRILIM", 11, now, price=99.0)
    snap = _snapshot([confirmed, invalidation])

    assert [state for state, _event, _time in main_module._classified_lifecycle_events(snap)] == [
        "KIRILIM_TEYITLI", "KIRILIM_GECERSIZLESTI"
    ]
    assert main_module._invalidation_event_for_snapshot(
        snap, SimpleNamespace(stable_id="formation-1")
    ) == invalidation


def test_invalidation_requires_matching_direction_reason_and_fresh_bar():
    now = datetime.now(ISTANBUL_TZ)
    confirmed = _event("BREAK_CONFIRMED", "KIRILIM_TEYITLI", 10, now, direction=1)
    mismatch = _event("BREAK_FAILED", "BASARISIZ_KIRILIM", 11, now, direction=-1)
    mismatch_snap = _snapshot([confirmed, mismatch])
    active = SimpleNamespace(stable_id="formation-1")
    assert main_module._invalidation_event_for_snapshot(mismatch_snap, active) is None

    correct = _event("BREAK_FAILED", "BASARISIZ_KIRILIM", 11, now, direction=1)
    wrong_reason = _snapshot([confirmed, correct], reason="Kırılım teyit alamadı")
    assert main_module._invalidation_event_for_snapshot(wrong_reason, active) is None

    stale = _snapshot(
        [confirmed, correct],
        bar_index=11 + max(1, int(TERMINAL_TAZE_BAR)) + 1,
    )
    assert main_module._invalidation_event_for_snapshot(stale, active) is None


def test_daily_lifecycle_counts_are_unique_and_exclude_unconfirmed_failure(monkeypatch):
    now = datetime.now(ISTANBUL_TZ).replace(microsecond=0)
    events = [
        _event("BREAK_CONFIRMED", "KIRILIM_TEYITLI", 20, now, price=102.0),
        _event("RETEST_OK", "RETEST_BASARILI", 21, now, price=102.2),
        _event("BREAK_FAILED", "BASARISIZ_KIRILIM", 22, now, price=99.0),
        _event("BREAK_FAILED", "BASARISIZ_KIRILIM", 23, now, stable_id="other", price=98.0),
    ]
    snap = _snapshot(events, bar_index=23)
    active = SimpleNamespace(
        stable_id="formation-1",
        pattern_type="Yükselen Üçgen",
        frozen_upper_boundary_at_break=102.0,
        frozen_lower_boundary_at_break=95.0,
        upper_now=103.0,
        lower_now=94.0,
    )
    stats = {
        "kirilim_teyitli_olay_sayisi": 0,
        "retest_basarili_olay_sayisi": 0,
        "kirilim_gecersizlesti_olay_sayisi": 0,
    }
    monkeypatch.setattr(main_module, "daily_stats", stats)
    monkeypatch.setattr(main_module, "_daily_lifecycle_event_keys", set())
    monkeypatch.setattr(main_module, "_gunluk_sayac_kaydet", lambda: None)

    main_module._record_daily_lifecycle_events("THYAO", "1h", snap)
    main_module._record_daily_lifecycle_events("THYAO", "1h", snap)

    assert stats == {
        "kirilim_teyitli_olay_sayisi": 1,
        "retest_basarili_olay_sayisi": 1,
        "kirilim_gecersizlesti_olay_sayisi": 1,
    }


def test_last_successful_full_scan_time_survives_partial_failed_and_restart_states():
    from live_state import LiveState

    full_at = "2026-10-12T18:00:00+03:00"
    state = LiveState()
    state.begin_scan(beklenen_hisse=48)
    state.finish_scan(
        son_tarama_beklenen_hisse=48,
        son_tarama_hissesi=48,
        son_basarili_tam_tarama=full_at,
    )

    state.begin_scan(scope=["THYAO"], replace_all=False, beklenen_hisse=1)
    state.finish_scan(son_tarama_beklenen_hisse=1, son_tarama_hissesi=1)
    assert state.status()["son_basarili_tam_tarama"] == full_at

    state.begin_scan(scope=["THYAO"], replace_all=False, beklenen_hisse=1)
    state.fail_scan("partial scan failure", istek_hisse=1, islenen_hisse=0, hata_hisse=1)
    snapshot = state.snapshot()
    restored = LiveState()
    restored.hydrate(snapshot)

    assert restored.status()["son_basarili_tam_tarama"] == full_at
    assert restored.status()["son_tarama_durumu"] == "basarisiz"


def test_full_universe_guard_requires_each_configured_symbol_exactly_once(monkeypatch):
    monkeypatch.setattr(main_module, "ACTIVE_STOCKS", ["THYAO", "GARAN"])
    assert main_module._is_full_universe_scan(["THYAO", "GARAN"]) is True
    assert main_module._is_full_universe_scan(["thyao", "garan"]) is True
    assert main_module._is_full_universe_scan(["THYAO"]) is False
    assert main_module._is_full_universe_scan(["THYAO", "GARAN", "GARAN"]) is False
    assert main_module._is_full_universe_scan(["THYAO", "ASELS"]) is False


def test_daily_summary_payload_marks_stale_snapshot_without_losing_last_full_scan(monkeypatch):
    now = ISTANBUL_TZ.localize(datetime(2026, 10, 12, 18, 40))
    full_at = ISTANBUL_TZ.localize(datetime(2026, 10, 12, 18, 0)).isoformat()

    class FakeLiveState:
        data = {
            "son_tarama_durumu": "tamamlandi",
            "son_tarama_beklenen_hisse": 2,
            "son_tarama_hissesi": 2,
            "son_tarama_bitis": full_at,
            "son_basarili_tam_tarama": full_at,
        }

        def status(self):
            return dict(self.data)

    fake = FakeLiveState()
    monkeypatch.setattr(main_module, "ACTIVE_STOCKS", ["THYAO", "GARAN"])
    monkeypatch.setattr(main_module, "_live_state", fake)

    fresh = main_module._daily_summary_payload(now)
    assert fresh["tam_tarama_guncel"] is True
    assert fresh["son_basarili_tam_tarama"] == full_at

    fake.data["son_tarama_durumu"] = "basarisiz"
    stale = main_module._daily_summary_payload(now)
    assert stale["tam_tarama_guncel"] is False
    assert stale["son_basarili_tam_tarama"] == full_at
