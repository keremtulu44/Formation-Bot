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
