"""Delivery policies exercised without Telegram/network access."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from notification_delivery import DeliveryOutbox, freeze
from patterns.lifecycle import ArgentEngine
from patterns.constants import ST_BREAK_FAILED, ST_RETESTING


def alert(stock="TCELL", tf="1h", identity="formation-1", direction=-1):
    return dict(stock_name=stock, timeframe=tf, formation_id=identity,
                state="KIRILIM_TEYITLI", pattern_name="Alçalan Kama", break_dir=direction,
                grafik_verisi={"goruntular": [{"tf": tf, "goruntu": {"tf_kisa": tf}}]})


def owner(events, remote=None):
    return SimpleNamespace(initial_store_data=remote or {}, persistent_store=None,
        can_send=lambda *a, **kw: True,
        format_message=lambda d: "metin:" + d["stock_name"],
        _gonder_metin=lambda d: events.append("text:" + d["stock_name"]) or True,
        chat_id="42", public_chat_id="", _grafik_pace=lambda: None, grafik_gonderilen=0)


@pytest.fixture
def renderer(monkeypatch, tmp_path):
    import grafik
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    calls = []

    def render(snapshot, tf):
        calls.append(tf)
        path = tmp_path / "render.png"
        path.write_bytes(b"fake PNG")
        return str(path), {"mum_sayisi": 30}

    monkeypatch.setattr(grafik, "kareyi_yaz", render)
    return calls


def test_preparation_failure_holds_text_and_survives_restart(tmp_path, monkeypatch, renderer):
    import grafik
    events = []
    box = DeliveryOutbox(owner(events), tmp_path / "state")
    real_render = grafik.kareyi_yaz
    monkeypatch.setattr(grafik, "kareyi_yaz", lambda *a: (None, {}))
    assert not box.submit(alert())
    assert events == []
    monkeypatch.setattr(grafik, "kareyi_yaz", real_render)
    restarted = DeliveryOutbox(owner(events), tmp_path / "state")
    monkeypatch.setattr(restarted, "send_images", lambda r: events.append("album:" + r["data"]["stock_name"]))
    assert restarted.flush(force=True) == 1
    assert events == ["text:TCELL", "album:TCELL"]
    assert restarted.flush() == 0


def test_partial_media_retry_does_not_repeat_text_or_interleave(tmp_path, monkeypatch, renderer):
    events = []
    box = DeliveryOutbox(owner(events), tmp_path)

    def fail(row):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(box, "send_images", fail)
    assert not box.submit(alert())
    assert not box.submit(alert("SISE"))
    assert events == ["text:TCELL"]
    restarted = DeliveryOutbox(owner(events), tmp_path)
    monkeypatch.setattr(restarted, "send_images", lambda r: events.append("album:" + r["data"]["stock_name"]))
    assert restarted.flush(force=True) == 2
    assert events == ["text:TCELL", "album:TCELL", "text:SISE", "album:SISE"]
    assert len(renderer) == 2  # the persisted prepared PNG was not rendered again


def test_first_timeframe_wins_but_new_same_tf_and_opposite_are_distinct(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    events = []
    box = DeliveryOutbox(owner(events), tmp_path)
    assert box.submit(alert())
    assert box.is_cross_duplicate(alert(tf="4h", identity="formation-4h"))
    assert not box.submit(alert(tf="4h", identity="formation-4h"))
    assert box.submit(alert(identity="genuinely-new"))
    assert box.submit(alert(tf="4h", identity="opposite", direction=1))
    restarted = DeliveryOutbox(owner(events), tmp_path)
    assert restarted.is_cross_duplicate(alert(tf="2h"))
    assert events == ["text:TCELL"] * 3


def test_public_dedup_is_independent_of_dm(tmp_path):
    box = DeliveryOutbox(owner([]), tmp_path)
    box.remember_public(alert())
    assert box.public_duplicate(alert(tf="4h"))
    assert not box.is_cross_duplicate(alert(tf="4h"))
    assert not box.public_duplicate(alert(tf="4h", direction=1))
    restarted = DeliveryOutbox(owner([]), tmp_path)
    assert restarted.public_duplicate(alert(tf="2h"))


def test_no_network_side_effect_if_durable_write_fails(tmp_path, monkeypatch):
    box = DeliveryOutbox(owner([]), tmp_path)
    monkeypatch.setattr(box, "save", lambda: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        box.submit(alert())


def test_remote_snapshot_survives_ephemeral_disk(tmp_path, monkeypatch, renderer):
    events, remote = [], {}
    first_owner = owner(events)
    first_owner.persistent_store = SimpleNamespace(upsert=lambda k, v: remote.update({k: v}) or True)
    box = DeliveryOutbox(first_owner, tmp_path / "old")
    monkeypatch.setattr(box, "send_images", lambda r: (_ for _ in ()).throw(RuntimeError()))
    assert not box.submit(alert())
    restored = DeliveryOutbox(owner(events, remote), tmp_path / "new")
    monkeypatch.setattr(restored, "send_images", lambda r: events.append("album"))
    assert restored.flush(force=True) == 1
    assert events == ["text:TCELL", "album"]


def test_timestamp_codec_preserves_chart_datetimes():
    import numpy as np
    stamp = datetime.fromisoformat("2026-10-16T10:00:00+03:00")
    copied = freeze({"zamanlar": [stamp], "close": np.float64(10.3)})
    assert copied == {"zamanlar": [stamp], "close": 10.3}


def test_album_failure_has_no_single_photo_fallback(tmp_path, monkeypatch, renderer):
    import transport.telegram as transport
    events = []
    box = DeliveryOutbox(owner(events), tmp_path)
    data = alert()
    data["grafik_verisi"]["goruntular"].append({"tf": "4h", "goruntu": {}})
    monkeypatch.setattr(transport, "medya_grubu_gonder", lambda *a, **kw: (False, "timeout"))
    monkeypatch.setattr(transport, "foto_gonder", lambda *a, **kw: pytest.fail("no fallback after ambiguous timeout"))
    assert not box.submit(data)
    assert events == ["text:TCELL"]
    assert box.state["rows"][0]["images"]


def test_invalidation_caption_only_symbol_and_tf():
    from notifier import _grafik_basligi
    assert _grafik_basligi({"sembol": "TCELL", "state": "KIRILIM_GECERSIZLESTI"},
        {"tf": "1h", "goruntu": {"tf_kisa": "1s"}},
        {"mum_sayisi": 100, "lejant_atlanan": 3, "metin": {"notlar": ["extra"]}}) == "TCELL · 1s"


def test_date_uses_actual_month_and_turkish_suffix():
    from notifier import _kart_yas_metni
    assert "16 Ekim'den beri" in _kart_yas_metni({"age_bars": 3, "band_baslangic": "2026-10-16"})
    assert "16 Eylül'den beri" in _kart_yas_metni({"age_bars": 3, "band_baslangic": "2026-09-16"})
    assert "16 Mart'tan beri" in _kart_yas_metni({"age_bars": 3, "band_baslangic": "2026-03-16"})


@pytest.mark.parametrize("direction", [-1, 1])
def test_three_consecutive_closes_cancel_on_recovery_and_do_not_double_count(direction):
    e = ArgentEngine()
    e.active.stable_id = "one"
    e.break_candidate_bar = 10
    assert not e._inside_confirmed(11, True)
    assert not e._inside_confirmed(11, True)
    assert not e._inside_confirmed(12, False)
    assert not e._inside_confirmed(13, True)
    assert not e._inside_confirmed(14, True)
    assert e._inside_confirmed(15, True)
    e.active.stable_id = "two"
    assert not e._inside_confirmed(16, True)


@pytest.mark.parametrize("direction", [-1, 1])
def test_retest_failure_requires_three_closes_in_actual_state_transition(direction):
    e = ArgentEngine()
    e.active.stable_id = "one"
    e.active.upper_now, e.active.lower_now = 110, 100
    e.active.geometry_atr = 1
    e.safe_atr = 1
    e.break_candidate_dir = direction
    e.break_candidate_bar, e.break_confirmed_bar = 0, 1
    boundary = 110 if direction == 1 else 100
    e.break_line_x1, e.break_line_x2 = 0, 1
    e.break_line_y1 = e.break_line_y2 = boundary
    e.close = [105.] * 6
    e.high, e.low = [106.] * 6, [104.] * 6
    assert e._retest_step(2) == ST_RETESTING
    assert e._retest_step(3) == ST_RETESTING
    assert e._retest_step(4) == ST_BREAK_FAILED
    assert e.last_failed_bar == 4


def test_notifier_integration_prepares_before_text_and_keeps_stock_packets_together(monkeypatch, renderer):
    import requests
    import transport.telegram as transport
    import notifier
    events = []
    n = notifier.TelegramNotifier()
    n.enabled, n.chat_id, n.token = True, "42", "test-token"
    monkeypatch.setattr(requests, "post", lambda url, json, **kw:
        events.append("text:" + ("TCELL" if "TCELL" in json["text"] else "SISE")) or
        SimpleNamespace(status_code=200))
    monkeypatch.setattr(transport, "foto_gonder", lambda path, **kw:
        events.append("photo:" + kw["caption"].split(" · ")[0]) or (True, "ok"))
    monkeypatch.setattr(n, "_grafik_pace", lambda: None)
    assert n.send(alert())
    assert not n.send(alert(tf="4h", identity="second-tf"))
    assert n.send(alert("SISE"))
    assert events == ["text:TCELL", "photo:TCELL", "text:SISE", "photo:SISE"]
    assert renderer == ["1h", "1h"]
    assert n.gonderim_durumu()["teslim_kuyrugu"]["pending"] == 0


def test_suppressed_formation_stays_suppressed_beyond_merge_window(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    box = DeliveryOutbox(owner([]), tmp_path)
    assert box.submit(alert())
    other_tf = alert(tf="4h", identity="four-hour-formation")
    assert box.is_cross_duplicate(other_tf)
    clock = box.now()
    monkeypatch.setattr(box, "now", lambda: clock + timedelta(hours=6))
    assert box.is_cross_duplicate(other_tf)
    assert not box.is_cross_duplicate(alert(tf="4h", identity="new-four-hour-formation"))
    other_tf["state"] = "KIRILIM_GECERSIZLESTI"
    assert box.is_cross_duplicate(other_tf)


def test_no_retry_storm_before_backoff_elapses(tmp_path, monkeypatch, renderer):
    box = DeliveryOutbox(owner([]), tmp_path)
    attempts = []

    def fail(row):
        attempts.append(row["id"])
        raise RuntimeError("try again")

    monkeypatch.setattr(box, "send_images", fail)
    assert not box.submit(alert())
    assert box.flush() == 0
    assert len(attempts) == 1
    clock = box.now()
    monkeypatch.setattr(box, "now", lambda: clock + timedelta(seconds=31))
    assert box.flush() == 0
    assert len(attempts) == 2


def test_real_chart_snapshot_renders_after_json_roundtrip():
    import grafik
    from test_grafik_iskelet import _goruntu
    from pathlib import Path
    path, meta = grafik.kareyi_yaz(freeze(_goruntu()), "1h")
    try:
        assert path and Path(path).read_bytes().startswith(b"\x89PNG")
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


def test_cached_preparation_cannot_bypass_a_failed_disk_checkpoint(tmp_path, monkeypatch, renderer):
    events = []
    box = DeliveryOutbox(owner(events), tmp_path)
    save = box.save
    calls = []

    def fail_after_acceptance():
        calls.append(True)
        if len(calls) > 1:
            raise OSError("disk full after accepting snapshot")
        save()

    monkeypatch.setattr(box, "save", fail_after_acceptance)
    assert not box.submit(alert())
    assert box.state["rows"][0]["prepared"]
    assert box.flush(force=True) == 0
    assert events == []  # even though the PNG exists in memory, no unsafe send


def test_public_suppressed_formation_does_not_reappear_after_window(tmp_path, monkeypatch):
    box = DeliveryOutbox(owner([]), tmp_path)
    box.remember_public(alert())
    other_tf = alert(tf="4h", identity="public-four-hour")
    assert box.public_duplicate(other_tf)
    restarted = DeliveryOutbox(owner([]), tmp_path)
    clock = restarted.now()
    monkeypatch.setattr(restarted, "now", lambda: clock + timedelta(hours=6))
    assert restarted.public_duplicate(other_tf)
    assert not restarted.public_duplicate(alert(tf="4h", identity="new-public-formation"))


def test_prepared_legacy_engulf_png_is_refreshed_without_repeating_text(tmp_path, monkeypatch, renderer):
    import base64
    events = []
    box = DeliveryOutbox(owner(events), tmp_path)
    data = alert()
    data["grafik_verisi"]["goruntular"][0]["goruntu"]["zone"] = {
        "cizilen": [{"tip": "eng"}]}
    row = {"data": data, "prepared": True, "text_sent": True,
           "images": [{"png": base64.b64encode(b"old chart with engulf").decode()}]}
    box.prepare(row)
    assert renderer == ["1h"]
    assert base64.b64decode(row["images"][0]["png"]) == b"fake PNG"
    assert row["text_sent"] is True and not events
    box.prepare(row)
    assert renderer == ["1h"]  # new policy is checkpointed, no endless regeneration


def _setup_retest_engine(direction=1, tf="1h", atr=2.0):
    e = ArgentEngine(timeframe=tf)
    e.active.stable_id = "formation-tur2"
    e.active.upper_now, e.active.lower_now = 110.0, 100.0
    e.active.geometry_atr = atr
    e.safe_atr = atr
    e.break_candidate_dir = direction
    e.break_candidate_bar, e.break_confirmed_bar = 0, 1
    boundary = 110.0 if direction == 1 else 100.0
    e.break_line_x1, e.break_line_x2 = 0, 1
    e.break_line_y1 = e.break_line_y2 = boundary
    return e


@pytest.mark.parametrize("direction", [-1, 1])
def test_tur2_inside_outside_inside_does_not_invalidate_while_three_deep_closes_do(direction):
    e = _setup_retest_engine(direction=direction, tf="1h", atr=2.0)
    deep_close = 108.0 if direction == 1 else 102.0      # 1.0 ATR inside (>= 0.3 * 2.0)
    outside_close = 112.0 if direction == 1 else 98.0    # recovery outside band
    e.close = [112.0 if direction == 1 else 98.0,
               112.0 if direction == 1 else 98.0,
               deep_close, outside_close, deep_close, deep_close, deep_close]
    e.high = [c + 0.5 for c in e.close]
    e.low = [c - 0.5 for c in e.close]

    # (i) teyit -> 1 bar içeri -> dışarı -> 1 bar içeri = geçersizleşme ÜRETİLMEZ
    assert e._retest_step(2) == ST_RETESTING
    assert e._retest_step(3) != ST_BREAK_FAILED
    assert e._retest_step(4) == ST_RETESTING
    assert e._inside_run == 1

    # (ii) teyit -> 3 derin kapanış içerde (bar 4, 5, 6) = ÜRETİLİR
    assert e._retest_step(5) == ST_RETESTING
    assert e._retest_step(6) == ST_BREAK_FAILED
    assert e.last_failed_bar == 6


@pytest.mark.parametrize("direction", [-1, 1])
def test_tur2b_superficial_graze_does_not_increment_counter_and_switch_restores_legacy(
    monkeypatch, direction
):
    e = _setup_retest_engine(direction=direction, tf="1h", atr=2.0)
    # 0.1 ATR inside (< 0.3 * 2.0 = 0.6), still past hold_buffer
    shallow_close = 109.8 if direction == 1 else 100.2
    e.close = [shallow_close] * 7
    e.high = [shallow_close + 0.3] * 7
    e.low = [shallow_close - 0.3] * 7

    for bar in (2, 3, 4, 5):
        assert e._retest_step(bar) == ST_RETESTING
        assert e._inside_run == 0

    # Also verify _break_attempt_or_candidate_step superficial graze does not advance counter
    e_cand = _setup_retest_engine(direction=direction, tf="1h", atr=2.0)
    e_cand.close = [shallow_close] * 6
    e_cand.high = [shallow_close + 0.3] * 6
    e_cand.low = [shallow_close - 0.3] * 6
    e_cand.vol_sma = [1000.0] * 6
    e_cand.volume = [1000.0] * 6
    e_cand.open = [shallow_close] * 6
    assert e_cand._break_attempt_or_candidate_step(2, is_attempt=False) != ST_BREAK_FAILED
    assert e_cand._inside_run == 0

    # Supap: INVALIDATION_MIN_DEPTH_ATR=0 disables depth filter
    monkeypatch.setenv("INVALIDATION_MIN_DEPTH_ATR", "0")
    e_off = _setup_retest_engine(direction=direction, tf="1h", atr=2.0)
    e_off.close = [shallow_close] * 6
    e_off.high = [shallow_close + 0.3] * 6
    e_off.low = [shallow_close - 0.3] * 6
    assert e_off._retest_step(2) == ST_RETESTING
    assert e_off._retest_step(3) == ST_RETESTING
    assert e_off._retest_step(4) == ST_BREAK_FAILED


def test_tur2c_timeframe_specific_confirm_bars_and_fallback(monkeypatch):
    from patterns.lifecycle import PatternLifecycleManager

    mgr = PatternLifecycleManager()
    eng_1h = mgr.get_engine("THYAO_1h")
    eng_4h = mgr.get_engine("THYAO_4h")
    eng_1d = mgr.get_engine("THYAO_1d")
    assert eng_1h._invalidation_confirm_bars() == 3
    assert eng_4h._invalidation_confirm_bars() == 2
    assert eng_1d._invalidation_confirm_bars() == 2

    # 4h invalidates in 2 deep bars instead of 3
    e4 = _setup_retest_engine(direction=1, tf="4h", atr=1.0)
    e4.close = [105.0] * 5
    e4.high, e4.low = [106.0] * 5, [104.0] * 5
    assert e4._retest_step(2) == ST_RETESTING
    assert e4._retest_step(3) == ST_BREAK_FAILED

    # Fallback when TF map is disabled or TF is unknown
    monkeypatch.setenv("INVALIDATION_CONFIRM_BARS_TF", "0")
    monkeypatch.setenv("INVALIDATION_CONFIRM_BARS", "4")
    assert eng_4h._invalidation_confirm_bars() == 4


def test_tur2a_unannounced_confirmation_skips_instant_push_and_adds_summary_line(
    tmp_path, monkeypatch
):
    import main as main_module
    from reporting.format import format_urgent_alert_queue_summary

    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    events = []
    box = DeliveryOutbox(owner(events), tmp_path)
    fake_notifier = SimpleNamespace(_delivery=box)

    # Confirmation not yet delivered -> gate blocks instant invalidation push
    assert not box.confirmation_delivered("unannounced-fid")
    assert not main_module._invalidation_confirmation_delivered(fake_notifier, "unannounced-fid")

    monkeypatch.setattr(main_module, "_daily_unannounced_invalidation_keys", set())
    monkeypatch.setitem(main_module.daily_stats, "sessiz_gecersizlesme_sayisi", 0)
    monkeypatch.setattr(main_module, "_gunluk_sayac_kaydet", lambda: None)

    main_module._note_unannounced_invalidation("TCELL", "1h", "unannounced-fid")
    main_module._note_unannounced_invalidation("TCELL", "1h", "unannounced-fid")  # dedup
    assert main_module.daily_stats["sessiz_gecersizlesme_sayisi"] == 1

    ozet_satiri = format_urgent_alert_queue_summary(
        [], sessiz_gecersizlesme=main_module.daily_stats["sessiz_gecersizlesme_sayisi"]
    )
    assert "1 geçersizleşme" in ozet_satiri
    assert "anlık push atlandı" in ozet_satiri

    # Once KIRILIM_TEYITLI is delivered in rows, invalidation push is permitted
    assert box.submit(alert(identity="announced-fid"))
    assert box.confirmation_delivered("announced-fid")
    assert main_module._invalidation_confirmation_delivered(fake_notifier, "announced-fid")

    # Supap: INVALIDATION_REQUIRE_DELIVERED_CONFIRM=0 restores instant push without check
    monkeypatch.setenv("INVALIDATION_REQUIRE_DELIVERED_CONFIRM", "0")
    assert main_module._invalidation_confirmation_delivered(fake_notifier, "unannounced-fid")


def test_tur2a_scan_all_stocks_suppresses_invalidation_when_confirmation_not_delivered(
    tmp_path, monkeypatch
):
    import copy
    import pandas as pd
    import main as main_module
    from config import ISTANBUL_TZ

    formation_frame = pd.DataFrame(
        {
            "open": [10.0 + i for i in range(40)],
            "high": [10.5 + i for i in range(40)],
            "low": [9.5 + i for i in range(40)],
            "close": [10.2 + i for i in range(40)],
            "volume": [1000.0 + i for i in range(40)],
        },
        index=pd.date_range(
            "2025-01-02 09:30", periods=40, freq="1h", tz="Europe/Istanbul", name="timestamp"
        ),
    )
    hourly_cache = pd.DataFrame(
        {
            "open": [10.0 + i for i in range(50)],
            "high": [10.5 + i for i in range(50)],
            "low": [9.5 + i for i in range(50)],
            "close": [10.2 + i for i in range(50)],
            "volume": [1000.0 + i for i in range(50)],
        },
        index=pd.date_range(
            "2025-01-02 09:30", periods=50, freq="1h", tz="Europe/Istanbul", name="timestamp"
        ),
    )
    all_timeframes = {
        "1h": pd.DataFrame(),
        "2h": formation_frame,
        "4h": pd.DataFrame(),
        "1d": pd.DataFrame(),
    }
    active = SimpleNamespace(
        raw_quality=92.0,
        pattern_type="Simetrik Üçgen",
        upper_now=60.0,
        lower_now=10.0,
        frozen_upper_boundary_at_break=50.0,
        frozen_lower_boundary_at_break=10.0,
        stable_id="unannounced-slot-1",
        start_bar=4,
        break_strength=91.0,
        contraction=0.6,
        upper_touches=3,
        lower_touches=2,
    )

    class _FakeLiveState:
        def begin_scan(self, *_a, **_k):
            return None

        def record_formation(self, *_a, **_k):
            return None

        def mark_alert_sent(self, *_a, **_k):
            return None

        def finish_scan(self, *_a, **_k):
            return None

        def fail_scan(self, *_a, **_k):
            return None

    class _FakeLifecycle:
        def scan(self, key, _frame, *, tam_yeniden):
            now = datetime.now(ISTANBUL_TZ)
            lifecycle_events = [
                {
                    "type": "BREAK_CONFIRMED", "state": "KIRILIM_TEYITLI",
                    "bar": 38, "time": (now - pd.Timedelta(minutes=5)).isoformat(),
                    "stable_id": active.stable_id, "direction": 1,
                    "quality": 92.0, "price": 51.0,
                },
                {
                    "type": "BREAK_FAILED", "state": "BASARISIZ_KIRILIM",
                    "bar": 39, "time": now.isoformat(),
                    "stable_id": active.stable_id, "direction": 1,
                    "quality": 92.0, "price": float(formation_frame["close"].iloc[-1]),
                },
            ]
            return SimpleNamespace(
                state="BASARISIZ_KIRILIM",
                invalid_reason="Kırılım sonrası formasyon alanına dönüldü",
                events=lifecycle_events,
                break_dir=1,
                log="immediate formation alert",
                active=active,
                effective_quality=92.0,
                bar_index=39,
                retest_seen=False,
            )

        def get_snapshot(self, _key):
            return None

    class _FakeDeferredAlerts:
        def observe(self, *_a, **_k):
            return None

    class _FakeDequeManager:
        sureklilik_sorunlari = {}

        def to_dataframe(self, _stock):
            return hourly_cache.copy(deep=True)

        def gunluk_veri_eksik_mi(self, _stock, _now):
            return False

        def to_gunluk_dataframe(self, _stock):
            return None

        def save_to_disk(self, _stock):
            return None

    sent_payloads = []
    delivered_ids = set()

    class _FakeGateNotifier:
        def teyit_teslim_edildi_mi(self, fid):
            return str(fid) in delivered_ids

        def send(self, alert_data):
            sent_payloads.append(dict(alert_data))
            return True

        def public_bosalt(self):
            return 0

    fresh_stats = copy.deepcopy(main_module.daily_stats)
    for k, v in fresh_stats.items():
        if isinstance(v, bool):
            fresh_stats[k] = False
        elif isinstance(v, (int, float)):
            fresh_stats[k] = 0
    monkeypatch.setattr(main_module, "ACTIVE_STOCKS", ["AUDIT"])
    monkeypatch.setattr(main_module, "daily_stats", fresh_stats)
    monkeypatch.setattr(main_module, "last_run_stats", {}, raising=False)
    monkeypatch.setattr(main_module, "_live_state", _FakeLiveState())
    monkeypatch.setattr(main_module, "_deferred_alert_buffer", _FakeDeferredAlerts())
    monkeypatch.setattr(main_module, "_load_domain_runner", lambda: None)
    monkeypatch.setattr(main_module, "fetch_1h_stocks_paced", lambda *_a, **_k: ({}, {}, 0, 0))
    monkeypatch.setattr(main_module, "create_yahoo_pacer", lambda: object())
    monkeypatch.setattr(main_module, "select_yfinance_1h_period", lambda *_: "5d")
    monkeypatch.setattr(main_module, "resample_all_timeframes", lambda _f: all_timeframes)
    monkeypatch.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_: False)
    monkeypatch.setattr(main_module, "_cache_verisi_kullanilabilir", lambda *_a, **_k: True)
    monkeypatch.setattr(main_module, "reset_daily_if_needed", lambda: None)
    monkeypatch.setattr(main_module, "write_heartbeat", lambda **_k: None)
    monkeypatch.setattr(main_module, "son_tarama_kaydet", lambda: None)
    monkeypatch.setattr(main_module, "_shutdown_requested", False)
    monkeypatch.setattr(main_module, "_daily_pattern_keys", set())
    monkeypatch.setattr(main_module, "_daily_lifecycle_event_keys", set())
    monkeypatch.setattr(main_module, "_daily_basarisiz_keys", set())
    monkeypatch.setattr(main_module, "_daily_unannounced_invalidation_keys", set())
    monkeypatch.setattr(main_module, "_gunluk_sayac_kaydet", lambda: None)
    monkeypatch.setenv("INVALIDATION_REQUIRE_DELIVERED_CONFIRM", "1")

    main_module.scan_all_stocks(
        _FakeDequeManager(),
        _FakeLifecycle(),
        _FakeGateNotifier(),
        stocks=["AUDIT"],
        send_alerts=True,
    )
    assert sent_payloads == []
    assert fresh_stats["sessiz_gecersizlesme_sayisi"] == 1

    # Once the confirmation id is marked delivered, instant invalidation push succeeds
    delivered_ids.add("unannounced-slot-1")
    main_module.scan_all_stocks(
        _FakeDequeManager(),
        _FakeLifecycle(),
        _FakeGateNotifier(),
        stocks=["AUDIT"],
        send_alerts=True,
    )
    assert len(sent_payloads) == 1
    assert sent_payloads[0]["state"] == "KIRILIM_GECERSIZLESTI"


def test_tur4_family_based_mtf_merge_and_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    events = []
    box = DeliveryOutbox(owner(events), tmp_path)

    # 1h Boğa Bayrağı ("direkli") delivered -> 4h Boğa Flaması ("direkli") same dir/state suppressed
    first = alert(stock="THYAO", tf="1h", identity="flag-1h", direction=1)
    first["pattern_name"] = "Boğa Bayrağı"
    assert box.submit(first)

    same_family = alert(stock="THYAO", tf="4h", identity="pennant-4h", direction=1)
    same_family["pattern_name"] = "Boğa Flaması"
    assert not box.submit(same_family)
    assert len(box.state["rows"][0].get("aliases", [])) == 1

    # Different family ("ucgen" vs "direkli") is NOT suppressed
    diff_family = alert(stock="THYAO", tf="4h", identity="tri-4h", direction=1)
    diff_family["pattern_name"] = "Yükselen Üçgen"
    assert box.submit(diff_family)

    # Same "ucgen" family on another TF IS suppressed and increments aliases
    same_tri_family = alert(stock="THYAO", tf="2h", identity="sym-tri-2h", direction=1)
    same_tri_family["pattern_name"] = "Simetrik Üçgen"
    assert not box.submit(same_tri_family)
    assert len(box.state["rows"][1].get("aliases", [])) == 1

    # Opposite direction is NOT suppressed
    opposite_dir = alert(stock="THYAO", tf="2h", identity="bear-tri-2h", direction=-1)
    opposite_dir["pattern_name"] = "Alçalan Üçgen"
    assert box.submit(opposite_dir)

    # Different state (RETEST_BASARILI vs KIRILIM_TEYITLI) is NOT suppressed
    diff_state = alert(stock="THYAO", tf="2h", identity="retest-2h", direction=1)
    diff_state["pattern_name"] = "Yükselen Üçgen"
    diff_state["state"] = "RETEST_BASARILI"
    assert box.submit(diff_state)

    # Supap: MTF_FAMILY_MATCH=0 restores exact pattern_name matching
    monkeypatch.setenv("MTF_FAMILY_MATCH", "0")
    wedge_1h = alert(stock="GARAN", tf="1h", identity="wedge-1h", direction=1)
    wedge_1h["pattern_name"] = "Alçalan Kama"
    wedge_4h = alert(stock="GARAN", tf="4h", identity="wedge-4h", direction=1)
    wedge_4h["pattern_name"] = "Yükselen Kama"
    assert box.submit(wedge_1h)
    assert box.submit(wedge_4h)

