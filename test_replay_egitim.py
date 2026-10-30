from types import SimpleNamespace

import pandas as pd
import pytest

from research import replay_egitim as eg


def test_real_archive_common_cut_and_future_is_bounded():
    q = eg.soru_sec("ASTOR")
    anchor = q.closes["1h"][q.positions["1h"]]
    for tf in eg.TFS:
        p = q.positions[tf]
        assert q.closes[tf][p] <= anchor
        assert q.closes[tf][p + 1] > anchor
        assert p + 20 < len(q.frames[tf])
    q.tf, q.horizon = "4h", 10
    result = eg.sonuc(q, "yatay")
    assert result["finish"] == q.closes["4h"][q.positions["4h"] + 10]
    assert all(q.closes[tf][q.closes[tf].searchsorted(result["finish"], side="right") - 1] <= result["finish"] for tf in eg.TFS)


def test_classification_inclusive_atr_boundaries(monkeypatch):
    close = [100.0] * 81 + [103.0] * 20
    frame = pd.DataFrame({"open": close, "high": [v + 1 for v in close],
                          "low": [v - 1 for v in close], "close": close})
    q = eg.Soru("TEST", {"1h": frame}, {"1h": pd.date_range("2025-01-01", periods=101, tz="UTC")}, {"1h": 80}, "ABC123", "1h", 8)
    monkeypatch.setattr(eg, "calculate_atr", lambda f, n: pd.Series([2.0]))
    assert eg.sonuc(q, "yatay")["direction"] == "yatay"
    frame.loc[88, "close"] = 103.00001
    assert eg.sonuc(q, "yukarı")["direction"] == "yukarı"
    frame.loc[88, "close"] = 97.0
    assert eg.sonuc(q, "yatay")["direction"] == "yatay"
    frame.loc[88, "close"] = 96.99999
    assert eg.sonuc(q, "aşağı")["direction"] == "aşağı"


def test_future_mutation_cannot_change_question_history_or_atr(monkeypatch):
    q = eg.soru_sec("ASTOR")
    p = q.positions["1h"]
    q.tf, q.horizon = "1h", 8
    first = eg.sonuc(q, "yatay")
    before = q.frames["1h"].iloc[:p + 1].copy(deep=True)
    q.frames["1h"].iloc[p + 1:, q.frames["1h"].columns.get_loc("close")] *= 1.1
    second = eg.sonuc(q, "yatay")
    pd.testing.assert_frame_equal(before, q.frames["1h"].iloc[:p + 1])
    assert first["atr"] == second["atr"] and first["start"] == second["start"]


def test_session_requires_current_code_and_old_session_is_cancelled():
    s = eg.Session()
    s.current = SimpleNamespace(code="ABCD12", tf=None, horizon=None)
    assert "kod" in s.cevap("1h OLD123", None)
    assert "mum sonra" in s.cevap("1h ABCD12", None)
    assert s.current.tf == "1h" and s.current.horizon in eg.HORIZONS
    s.busy = True
    assert "iptal" in s.yeni("ASTOR", None)
    assert s.current is None


def test_missing_symbol_does_not_fetch_or_guess():
    with pytest.raises(ValueError):
        eg.soru_sec("NOTREALSYMBOL")


def test_listener_training_text_only_authorized_dm():
    from telegram_commands import TelegramCommandListener
    called = []
    def test_handler(_): return "started"
    def text_handler(text):
        called.append(text)
        return "training answer"
    test_handler.text_handler = text_handler
    sent = []
    listener = TelegramCommandListener("token", "123", {"test": test_handler},
                                      response_sender=lambda uid, text: sent.append(text) or True,
                                      public_chat_ids=["-1001"], public_commands=["test"],
                                      admin_checker=lambda *_: True)
    def update(i, chat, kind, text):
        return {"update_id": i, "message": {"chat": {"id": chat, "type": kind},
                "from": {"id": 123}, "message_id": i, "text": text}}
    assert listener.handle_update(update(1, -1001, "supergroup", "/test")) is None
    listener.handle_update(update(2, -1001, "supergroup", "1h ABCD12"))
    listener.handle_update(update(3, 999, "private", "1h ABCD12"))
    assert called == []
    assert listener.handle_update(update(4, 123, "private", "1h ABCD12")) == "training answer"
    assert called == ["1h ABCD12"]


def test_new_question_cancels_without_waiting_for_inflight_album(monkeypatch):
    import threading
    import transport.telegram as tg

    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    question = SimpleNamespace(sembol="ASTOR", code="ABC123")
    monkeypatch.setattr(eg, "soru_sec", lambda _: question)
    monkeypatch.setattr(eg, "album_hazirla", lambda *args, **kwargs: (["a", "b"], []))
    def blocked_album(*args, **kwargs):
        started.set()
        release.wait(5)
        return True, ""
    monkeypatch.setattr(tg, "medya_grubu_gonder", blocked_album)
    notifier = SimpleNamespace(chat_id="123", send_to_chat=lambda *args: True)
    session = eg.Session()
    session.yeni("ASTOR", notifier).baslat()
    assert started.wait(2)
    def cancel():
        session.yeni("THYAO", notifier)
        finished.set()
    thread = threading.Thread(target=cancel)
    thread.start()
    try:
        assert finished.wait(1), "İptal ağ yanıtını beklememeli"
    finally:
        release.set()
        thread.join(5)
    assert session.current is None


def _inline_jobs(session, monkeypatch):
    monkeypatch.setattr(session, "_schedule", lambda job, generation: job())


def test_training_album_fallback_sends_four_images_and_activates_only_afterward(monkeypatch):
    import transport.telegram as tg

    question = SimpleNamespace(sembol="ASTOR", code="ABC123", tf=None, horizon=None)
    session, messages, deliveries = eg.Session(), [], []
    _inline_jobs(session, monkeypatch)
    monkeypatch.setattr(eg, "soru_sec", lambda _: question)
    monkeypatch.setattr(eg, "album_hazirla", lambda *a, **k: (
        ["a", "b", "c", "d"], ["1s", "2s", "4s", "1g"]))
    monkeypatch.setattr(tg, "medya_grubu_gonder", lambda *a, **k: (False, "HTTP 400"))
    def photo(path, **kwargs):
        assert session.current is None
        deliveries.append((path, kwargs["caption"]))
        return True, ""
    monkeypatch.setattr(tg, "foto_gonder", photo)
    notifier = SimpleNamespace(chat_id="123", send_to_chat=lambda text, _: messages.append(text) or True)
    session.yeni("ASTOR", notifier).baslat()
    assert deliveries == [("a", "1s"), ("b", "2s"), ("c", "4s"), ("d", "1g")]
    assert session.current is question
    assert "4s ABC123" in messages[-1]
    assert "aynı ana kadar" in messages[-1]


def test_incomplete_question_delivery_is_cancelled_and_explained(monkeypatch):
    import transport.telegram as tg

    question = SimpleNamespace(sembol="ASTOR", code="ABC123", tf=None, horizon=None)
    session, messages = eg.Session(), []
    _inline_jobs(session, monkeypatch)
    monkeypatch.setattr(eg, "soru_sec", lambda _: question)
    monkeypatch.setattr(eg, "album_hazirla", lambda *a, **k: (
        ["a", "b", "c", "d"], ["1s", "2s", "4s", "1g"]))
    monkeypatch.setattr(tg, "medya_grubu_gonder", lambda *a, **k: (False, "HTTP 400"))
    monkeypatch.setattr(tg, "foto_gonder", lambda path, **k: (path != "c", ""))
    notifier = SimpleNamespace(chat_id="123", send_to_chat=lambda text, _: messages.append(text) or True)
    session.yeni("ASTOR", notifier).baslat()
    assert session.current is None
    assert "3/4" in messages[-1] and "soru iptal" in messages[-1]
    assert "ABC123" not in messages[-1]


def test_result_text_is_delivered_even_when_result_rendering_fails(monkeypatch):
    session, messages = eg.Session(), []
    _inline_jobs(session, monkeypatch)
    close = [100.0] * 81 + [103.0] * 20
    frame = pd.DataFrame({"open": close, "high": [v + 1 for v in close],
                          "low": [v - 1 for v in close], "close": close})
    session.current = eg.Soru("TEST", {"1h": frame},
                              {"1h": pd.date_range("2025-01-01", periods=101, tz="UTC")},
                              {"1h": 80}, "ABC123", "1h", 8)
    monkeypatch.setattr(eg, "calculate_atr", lambda f, n: pd.Series([2.0]))
    def error(*args, **kwargs):
        raise RuntimeError("render failed")
    monkeypatch.setattr(eg, "album_hazirla", error)
    notifier = SimpleNamespace(chat_id="123", send_to_chat=lambda text, _: messages.append(text) or True)
    session.cevap("yatay ABC123", notifier).baslat()
    assert session.current is None and not session.busy
    assert "Tahmin: yatay · Sonuç: yatay" in messages[-1]
    assert "100,0000 → 103,0000" in messages[-1]
    assert "±3,0000" in messages[-1]
    assert "0/4" in messages[-1]


def test_sending_result_text_exception_does_not_leave_worker_busy(monkeypatch):
    session = eg.Session()
    _inline_jobs(session, monkeypatch)
    session.busy = True
    q = SimpleNamespace(code="ABC123", tf="1h", horizon=8)
    session.current = q
    monkeypatch.setattr(eg, "sonuc", lambda *a: {
        "tf": "1h", "horizon": 8, "tahmin": "yatay", "direction": "yatay",
        "start": 100.0, "end": 100.0, "diff": 0.0, "atr": 2.0,
    })
    monkeypatch.setattr(eg, "album_hazirla", lambda *a, **k: (_ for _ in ()).throw(RuntimeError()))
    notifier = SimpleNamespace(chat_id="123", send_to_chat=lambda *a: (_ for _ in ()).throw(OSError()))
    session.cevap("yatay ABC123", notifier).baslat()
    assert not session.busy


def test_missing_symbol_error_is_sent_to_user_not_hidden(monkeypatch):
    session, messages = eg.Session(), []
    _inline_jobs(session, monkeypatch)
    monkeypatch.setattr(eg, "soru_sec", lambda *_: (_ for _ in ()).throw(
        ValueError("Bu hisse arşivde yok; /test ASTOR gibi deneyin.")))
    notifier = SimpleNamespace(chat_id="123", send_to_chat=lambda text, _: messages.append(text) or True)
    session.yeni("NOTREAL", notifier).baslat()
    assert "arşivde yok" in messages[-1]
    assert session.current is None


def test_album_fallback_stops_after_cancellation(monkeypatch):
    import transport.telegram as tg

    active, sent = [True], []
    monkeypatch.setattr(tg, "medya_grubu_gonder", lambda *a, **k: (False, ""))
    def photo(path, **kwargs):
        sent.append(path)
        active[0] = False
        return True, ""
    monkeypatch.setattr(tg, "foto_gonder", photo)
    count = eg._album_gonder(["a", "b", "c", "d"], ["1s", "2s", "4s", "1g"],
                             SimpleNamespace(), lambda: active[0])
    assert count == 1 and sent == ["a"]


def _mock_short_archive(monkeypatch, *, hourly_periods, invalid_hour=None):
    monkeypatch.setattr(eg, "MIN_HISTORY", 3)
    monkeypatch.setattr(eg, "HORIZONS", (2, 3, 5))
    monkeypatch.setattr(eg, "arsiv_sembolleri", lambda _: ["ASTOR"])
    monkeypatch.setattr(eg, "mum_kapanis_anlari", lambda index, _: index)
    frames = {}
    for tf, freq, count in (("1h", "1h", hourly_periods), ("2h", "2h", 240),
                            ("4h", "4h", 120), ("1d", "1D", 20)):
        index = pd.date_range("2025-01-01", periods=count, freq=freq, tz="UTC")
        frames[tf] = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0,
                                   "close": 100.0, "volume": 1.0}, index=index)
    if invalid_hour:
        for i in range(invalid_hour, len(frames["1h"]), invalid_hour):
            frames["1h"].iloc[i, frames["1h"].columns.get_loc("close")] = 200.0
    monkeypatch.setattr(eg, "tf_frame", lambda name, tf, root: frames[tf])


def test_selection_rejects_archive_that_ends_before_daily_horizon(monkeypatch):
    # Five daily bars cannot be revealed on 1h even though each TF has >5 bars.
    _mock_short_archive(monkeypatch, hourly_periods=5 * 24)
    with pytest.raises(ValueError, match="ortak geçmiş ve gelecek"):
        eg.soru_sec("ASTOR", rng=__import__("random").Random(7))


def test_selection_checks_hourly_bars_beyond_first_short_horizon(monkeypatch):
    # Invalid hourly bars occur every two days, beyond the first 5 hourly bars
    # but within the 5-day daily horizon that any valid question must cover.
    _mock_short_archive(monkeypatch, hourly_periods=20 * 24, invalid_hour=48)
    with pytest.raises(ValueError, match="ortak geçmiş ve gelecek"):
        eg.soru_sec("ASTOR", rng=__import__("random").Random(7))
