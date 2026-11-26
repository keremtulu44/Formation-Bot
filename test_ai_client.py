"""Exhaustive tests for `ai_prompt.client` (ApiWrapper SSE spec + 2× Free Gemini fallback + normal alarm)."""
from __future__ import annotations

import json

import httpx
import pytest

import deploy_check
from ai_prompt import (
    AIClientRouter,
    ApiWrapperClient,
    DEFAULT_CONNECT_TIMEOUT_S,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_READ_TIMEOUT_S,
    GeminiFreeClient,
    build_api_prompt,
    build_from_local_cache,
)
from secrets_redaction import redact_sensitive_text


SAMPLE_COMMENTARY = (
    "🧭 Mevcut durum\n" + " ".join(["görüş"] * 45)
    + "\n\n🔎 Bağlam\n" + " ".join(["bağlam"] * 45)
    + "\n\n🕯️ Replay notu\n" + " ".join(["temas"] * 45)
    + "\n\n[AI_SONUC egilim=yukari | guc=orta | mtf_uyum=karma | risk=orta | yayin_degeri=izle]"
)


def test_api_wrapper_request_contract_wait_comments_unknown_fields_and_ascii_turkish():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.method == "POST"
        # NEVER call anything other than /v1/ask!
        assert str(request.url) == "https://wrap.example.test/v1/ask"
        assert request.headers["authorization"] == "Bearer super-secret-key"
        assert request.headers["content-type"] == "application/json"
        body = json.loads(request.content.decode("utf-8"))
        assert body == {"prompt": "hisse verisi", "system": "sabit talimat"}
        assert "model" not in body  # omitted when not configured

        # ASCII-escaped Turkish chars (\u0131, \u015f, \u00e7, \u011f, \u00fc, \u00f6) + extra fields + comments
        done_json = json.dumps(
            {
                "status": "done",
                "text": "Işık çağrısı başarılı: güncel görünüm.",
                "elapsed": 47.1,
                "id": "job-42",
                "model": "auto-v2",
                "future_field": {"nested": True},
            },
            ensure_ascii=True,
        )
        assert "\\u0131" in done_json
        sse = (
            ": ping\n"
            "\n"
            "event: message\n"
            'data: {"status": "wait", "elapsed": 30, "id": "job-42"}\n'
            "\n"
            ": another comment\n"
            'data: {"status": "wait", "elapsed": 45, "future": 123}\n'
            "\n"
            f"data: {done_json}\n"
        )
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})

    client = ApiWrapperClient(
        "https://wrap.example.test/",  # trailing slash normalized cleanly
        "super-secret-key",
        transport=httpx.MockTransport(handler),
    )
    assert client.connect_timeout == DEFAULT_CONNECT_TIMEOUT_S == 10.0
    assert client.read_timeout == DEFAULT_READ_TIMEOUT_S == 45.0

    text, rec = client.ask("hisse verisi", system="sabit talimat")
    assert len(seen) == 1
    assert rec.ok is True
    assert rec.outcome == "done"
    assert rec.http_status == 200
    assert rec.wait_events == 2
    assert text == "Işık çağrısı başarılı: güncel görünüm."


def test_api_wrapper_normalizes_url_and_passes_optional_model():
    captured_bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://wrap.example.test/v1/ask"
        captured_bodies.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, text='data: {"status":"done","text":"tamam"}\n')

    # Passing URL already ending with /v1/ask must not double it.
    client = ApiWrapperClient(
        "https://wrap.example.test/v1/ask",
        "key-1",
        model="custom-model-x",
        transport=httpx.MockTransport(handler),
    )
    text, rec = client.ask("soru")
    assert rec.ok is True and text == "tamam"
    assert captured_bodies[0] == {"prompt": "soru", "model": "custom-model-x"}
    assert "system" not in captured_bodies[0]


@pytest.mark.parametrize(
    ("label", "handler", "expected_outcome"),
    [
        (
            "rule1_status_problem",
            lambda req: httpx.Response(200, text='data: {"status": "wait"}\ndata: {"status": "problem"}\n'),
            "problem",
        ),
        (
            "rule2_http_401",
            lambda req: httpx.Response(401, text="unauthorized"),
            "http_error",
        ),
        (
            "rule2_http_429",
            lambda req: httpx.Response(429, text="rate limit"),
            "http_error",
        ),
        (
            "rule2_http_502",
            lambda req: httpx.Response(502, text="bad gateway"),
            "http_error",
        ),
        (
            "rule3_read_timeout_45s",
            lambda req: (_ for _ in ()).throw(httpx.ReadTimeout("45s silence")),
            "read_timeout",
        ),
        (
            "rule4_connect_error",
            lambda req: (_ for _ in ()).throw(httpx.ConnectError("refused")),
            "connection_error",
        ),
        (
            "rule4_eof_before_done",
            lambda req: httpx.Response(200, text='data: {"status": "wait"}\n\n'),
            "stream_closed",
        ),
        (
            "rule5_invalid_json",
            lambda req: httpx.Response(200, text="data: {not-valid-json\n"),
            "invalid_payload",
        ),
        (
            "rule5_unknown_status",
            lambda req: httpx.Response(200, text='data: {"status": "weird"}\n'),
            "invalid_payload",
        ),
        (
            "rule5_done_with_empty_text",
            lambda req: httpx.Response(200, text='data: {"status": "done", "text": "   "}\n'),
            "invalid_payload",
        ),
        (
            "rule5_done_missing_text",
            lambda req: httpx.Response(200, text='data: {"status": "done"}\n'),
            "invalid_payload",
        ),
    ],
)
def test_api_wrapper_all_five_problem_rules_trigger_immediate_failure_without_retry(
    label, handler, expected_outcome
):
    del label
    calls = {"n": 0}

    def counting_handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return handler(request)

    client = ApiWrapperClient(
        "https://wrap.example.test",
        "secret-wrapper-token",
        transport=httpx.MockTransport(counting_handler),
    )
    text, rec = client.ask("soru", system="talimat")
    assert calls["n"] == 1  # NEVER retry the same question on ApiWrapper!
    assert text is None
    assert rec.ok is False
    assert rec.outcome == expected_outcome
    assert "secret-wrapper-token" not in str(rec.detail or "")


def test_api_wrapper_optional_wall_clock_cap_closes_and_fails_cleanly():
    ticks = iter([0.0, 0.0, 30.0, 65.0, 65.0])

    def fake_clock() -> float:
        return next(ticks, 65.0)

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        sse = (
            'data: {"status": "wait"}\n'
            'data: {"status": "wait"}\n'
            'data: {"status": "done", "text": "gec kalan"}\n'
        )
        return httpx.Response(200, text=sse)

    client = ApiWrapperClient(
        "https://wrap.example.test",
        "key-1",
        transport=httpx.MockTransport(handler),
        clock=fake_clock,
    )
    text, rec = client.ask("soru", max_wall_seconds=60.0)
    assert text is None
    assert rec.ok is False
    assert rec.outcome == "wall_timeout"


def test_gemini_free_client_uses_header_key_and_filters_thought_parts():
    def handler(request: httpx.Request) -> httpx.Response:
        # API key MUST be in header, NEVER in URL query string!
        assert request.headers["x-goog-api-key"] == "gem-secret-123"
        assert "gem-secret-123" not in str(request.url)
        assert request.url.path == f"/v1beta/models/{DEFAULT_GEMINI_MODEL}:generateContent"
        body = json.loads(request.content.decode("utf-8"))
        assert body["system_instruction"] == {"parts": [{"text": "sabit kural"}]}
        assert body["contents"] == [{"role": "user", "parts": [{"text": "veri"}]}]
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"thought": True, "text": "gizli ic dusunce"},
                                {"text": "Temiz görünür yanıt."},
                            ]
                        }
                    }
                ]
            },
        )

    gem = GeminiFreeClient(
        "gem-secret-123",
        name="gemini_free_1",
        transport=httpx.MockTransport(handler),
    )
    text, rec = gem.ask("veri", system="sabit kural")
    assert rec.ok is True
    assert rec.outcome == "done"
    assert text == "Temiz görünür yanıt."
    assert "gizli ic dusunce" not in text


def test_router_full_fallback_chain_and_primary_first_on_next_question():
    wrapper_state = {"broken": True, "calls": 0}
    gem1_calls = {"n": 0}
    gem2_calls = {"n": 0}

    def wrapper_handler(request: httpx.Request) -> httpx.Response:
        del request
        wrapper_state["calls"] += 1
        if wrapper_state["broken"]:
            return httpx.Response(200, text='data: {"status": "problem"}\n')
        return httpx.Response(200, text=f'data: {json.dumps({"status": "done", "text": SAMPLE_COMMENTARY})}\n')

    def gem1_handler(request: httpx.Request) -> httpx.Response:
        del request
        gem1_calls["n"] += 1
        return httpx.Response(429, json={"error": {"message": "free quota exceeded"}})

    def gem2_handler(request: httpx.Request) -> httpx.Response:
        del request
        gem2_calls["n"] += 1
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": SAMPLE_COMMENTARY}]}}]},
        )

    router = AIClientRouter([
        ApiWrapperClient("https://wrap.example.test", "w-key", transport=httpx.MockTransport(wrapper_handler)),
        GeminiFreeClient("g1-key", name="gemini_free_1", transport=httpx.MockTransport(gem1_handler)),
        GeminiFreeClient("g2-key", name="gemini_free_2", transport=httpx.MockTransport(gem2_handler)),
    ])

    # Question 1: ApiWrapper problem -> NO retry on ApiWrapper -> Gemini #1 429 -> Gemini #2 OK!
    res1 = router.ask("soru 1", system="talimat")
    assert res1.ok is True
    assert res1.provider == "gemini_free_2"
    assert res1.fallback_to_normal_alarm is False
    assert [a.provider for a in res1.attempts] == ["api_wrapper", "gemini_free_1", "gemini_free_2"]
    assert wrapper_state["calls"] == 1
    assert gem1_calls["n"] == 1
    assert gem2_calls["n"] == 1

    # Question 2: ApiWrapper recovers -> router MUST try ApiWrapper FIRST again!
    wrapper_state["broken"] = False
    res2 = router.ask("soru 2", system="talimat")
    assert res2.ok is True
    assert res2.provider == "api_wrapper"
    assert len(res2.attempts) == 1
    assert wrapper_state["calls"] == 2
    assert gem1_calls["n"] == 1
    assert gem2_calls["n"] == 1


def test_router_all_three_fail_falls_back_cleanly_to_normal_alarm():
    router = AIClientRouter([
        ApiWrapperClient(
            "https://wrap.example.test",
            "w-key",
            transport=httpx.MockTransport(lambda req: httpx.Response(200, text='data: {"status":"problem"}\n')),
        ),
        GeminiFreeClient(
            "g1-key",
            name="gemini_free_1",
            transport=httpx.MockTransport(lambda req: httpx.Response(429, text="quota")),
        ),
        GeminiFreeClient(
            "g2-key",
            name="gemini_free_2",
            transport=httpx.MockTransport(lambda req: httpx.Response(503, text="down")),
        ),
    ])
    res = router.ask("soru", system="talimat")
    assert res.ok is False
    assert res.text is None
    assert res.provider is None
    assert res.fallback_to_normal_alarm is True
    assert len(res.attempts) == 3
    assert [a.outcome for a in res.attempts] == ["problem", "http_error", "http_error"]


def test_router_from_env_and_ask_bundle_end_to_end():
    env = {
        "AI_WRAPPER_BASE_URL": "https://wrap.example.test",
        "AI_WRAPPER_API_KEY": "w-secret",
        # Eski/fazla model env'leri verilse bile yok sayılmalı:
        # ApiWrapper otomatik, Gemini #1/#2 sabit dengeli DEFAULT_GEMINI_MODEL.
        "AI_WRAPPER_MODEL": "ignored-wrapper-model",
        "GEMINI_API_KEY_1": "g1-secret",
        "GEMINI_MODEL_1": "ignored-gem-1",
        "GEMINI_API_KEY_2": "g2-secret",
        "GEMINI_MODEL_2": "ignored-gem-2",
    }

    def wrapper_ok(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert "model" not in body
        assert "<veri_paketi" in body["prompt"]
        assert "🧭 Mevcut durum" in body["system"]
        return httpx.Response(200, text=f'data: {json.dumps({"status": "done", "text": SAMPLE_COMMENTARY})}\n')

    router = AIClientRouter.from_env(
        env,
        wrapper_transport=httpx.MockTransport(wrapper_ok),
        gemini_transport=httpx.MockTransport(lambda req: httpx.Response(500)),
    )
    assert router.provider_names() == ("api_wrapper", "gemini_free_1", "gemini_free_2")
    assert router.providers[0].model is None
    assert router.providers[1].model == DEFAULT_GEMINI_MODEL == "gemini-3.8-flash"
    assert router.providers[2].model == DEFAULT_GEMINI_MODEL == "gemini-3.8-flash"

    pkt = build_from_local_cache("BIMAS", as_of="2026-09-25 18:05+03:00", main_tf="4h")
    bundle = build_api_prompt(pkt, include_hidden_verdict=True)
    out = router.ask_bundle(bundle, require_verdict=True)
    assert out["result"].ok is True
    assert out["fallback_to_normal_alarm"] is False
    assert out["parsed"]["ok_for_telegram"] is True
    assert out["parsed"]["verdict"]["egilim"] == "yukari"
    assert "AI_SONUC" not in out["parsed"]["visible_text"]


def test_secret_redaction_and_deploy_check_partial_wrapper_warning(monkeypatch, capsys):
    masked = redact_sensitive_text(
        "Authorization: Bearer abc12345 x-goog-api-key: gem999 ?key=xyz",
    )
    assert "abc12345" not in masked
    assert "gem999" not in masked
    assert "xyz" not in masked

    env = {
        "TELEGRAM_BOT_TOKEN": "123:abc",
        "TELEGRAM_CHAT_ID": "12345",
        "TELEGRAM_GRAFIK": "yok",
        "AI_WRAPPER_BASE_URL": "https://wrap.example.test",
        # AI_WRAPPER_API_KEY intentionally missing -> deploy_check warns!
    }
    monkeypatch.setattr(deploy_check, "env_degeri", lambda name, _dosya: env.get(name, ""))
    deploy_check.kontrol_env({}, canli_mod=False)
    out = capsys.readouterr().out
    assert "AI_WRAPPER_BASE_URL ve AI_WRAPPER_API_KEY birlikte tanımlanmalı" in out
