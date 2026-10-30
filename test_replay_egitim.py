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
