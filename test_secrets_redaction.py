"""Credential redaction regression tests; no network or real credentials."""

from secrets_redaction import redact_sensitive_text


def test_explicit_secrets_are_removed_from_error_text():
    token = "123456789:TEST_ONLY_TOKEN_abcdefgh"
    webhook_secret = "test-only-webhook-secret"
    raw = f"send failed for {token}; webhook={webhook_secret}"

    safe = redact_sensitive_text(raw, token, webhook_secret)

    assert token not in safe
    assert webhook_secret not in safe
    assert safe.count("[REDACTED]") == 2


def test_telegram_bot_path_and_secret_query_are_masked_without_explicit_values():
    raw = (
        "https://api.telegram.org/bot123456789:PATH_TOKEN/sendMessage"
        "?secret_token=header-secret&k=test-key"
    )

    safe = redact_sensitive_text(raw)

    assert "PATH_TOKEN" not in safe
    assert "header-secret" not in safe
    assert "test-key" not in safe
    assert "/bot[REDACTED]/" in safe
    assert "secret_token=[REDACTED]" in safe
    assert "k=[REDACTED]" in safe


class _Response:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text

    def json(self):
        return {"ok": False}


def test_notifier_send_redacts_full_response_before_truncating(monkeypatch):
    import requests
    from notifier import TelegramNotifier

    token = "ZZ_AUDIT_TELEGRAM_TOKEN_0123456789"
    response = _Response(500, "x" * 199 + token + "tail")
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: response)
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    notifier.enabled = True
    notifier.token = token

    ok, status, detail, _retry_after, _permanent = notifier._send_text_direct("test", "chat")

    assert not ok and status == 500
    assert "Z" not in detail


def test_notifier_connection_log_redacts_full_response_before_truncating(monkeypatch, caplog):
    import requests
    from notifier import TelegramNotifier

    token = "ZZ_AUDIT_TELEGRAM_TOKEN_0123456789"
    response = _Response(500, "x" * 199 + token + "tail")
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: response)
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    notifier.enabled = True
    notifier.token = token
    notifier.chat_id = "test-chat"

    assert notifier.check_connection() is False

    assert "Z" not in caplog.text


def test_notifier_success_log_does_not_include_channel_identifier(caplog):
    from notifier import TelegramNotifier

    channel_id = "-1001234567890"
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    notifier.enabled = True
    notifier.channel_id = channel_id
    notifier.token = "123456:fake-token"
    notifier._send_text_direct = lambda *_args: (True, 200, "ok", None, False)

    with caplog.at_level("INFO", logger="notifier"):
        assert notifier.send_to_channel("test") is True

    assert channel_id not in caplog.text
    assert "kanal kimliği loglanmadı" in caplog.text


def test_command_reply_redacts_secret_before_message_truncation():
    from telegram_commands import TelegramCommandListener

    token = "ZZ_AUDIT_COMMAND_TOKEN_0123456789"
    listener = TelegramCommandListener(
        token=token,
        allowed_chat_id="test-chat",
        handlers={},
        response_sender=lambda _update_id, _body: True,
    )
    raw = "x" * 3959 + token + "tail" * 20

    safe = listener._cevapla(raw, update_id=1)

    assert safe is not None
    assert "Z" not in safe


def test_supabase_error_redacts_full_response_before_truncating(tmp_path, caplog):
    from supabase_store import SupabaseStore

    secret = "ZZ_AUDIT_SUPABASE_SECRET_0123456789"

    class FakeSession:
        def request(self, *_args, **_kwargs):
            return _Response(401, "x" * 299 + secret + "tail")

    store = SupabaseStore(
        "https://example.supabase.co", secret, session=FakeSession()
    )

    assert store.ping() is False

    assert "Z" not in caplog.text
