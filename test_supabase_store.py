import supabase_store as supabase_store_module
from supabase_store import SupabaseStore


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_from_env_requires_both_values():
    assert SupabaseStore.from_env({}) is None
    assert SupabaseStore.from_env({"SUPABASE_URL": "https://demo.supabase.co"}) is None
    store = SupabaseStore.from_env({
        "SUPABASE_URL": "https://demo.supabase.co/",
        "SUPABASE_SERVICE_ROLE_KEY": "test-secret",
    })
    assert store.rest_url == "https://demo.supabase.co/rest/v1/bot_store"


def test_rest_api_url_variant_is_normalised():
    # Dashboard'da REST API uc noktasinin tamamini kopyalayan kullanici var;
    # /rest/v1 iki kez eklenip 404 donuyordu.
    for ham, beklenen in [
        ("https://demo.supabase.co", "https://demo.supabase.co/rest/v1/bot_store"),
        ("https://demo.supabase.co/", "https://demo.supabase.co/rest/v1/bot_store"),
        ("https://demo.supabase.co/rest/v1", "https://demo.supabase.co/rest/v1/bot_store"),
        ("https://demo.supabase.co/rest/v1/", "https://demo.supabase.co/rest/v1/bot_store"),
    ]:
        store = SupabaseStore(ham, "test-secret", session=FakeSession([]))
        assert store.rest_url == beklenen, ham


def test_ping_returns_false_and_keeps_running_on_missing_table():
    session = FakeSession([FakeResponse(status_code=404, text="relation missing")])
    store = SupabaseStore("https://demo.supabase.co", "test-secret", session=session)

    assert store.ping() is False
    method, url, kwargs = session.calls[0]
    assert (method, url) == ("GET", "https://demo.supabase.co/rest/v1/bot_store")
    assert kwargs["params"] == {"select": "store_key", "limit": 1}


def test_get_many_returns_payload_map_and_uses_in_filter():
    session = FakeSession([FakeResponse(payload=[
        {"store_key": "cache:1h:THYAO", "payload": [{"close": 1}]},
    ])])
    store = SupabaseStore("https://demo.supabase.co", "test-secret", session=session)

    result = store.get_many(["cache:1h:THYAO", "cache:1d:THYAO"])

    assert result == {"cache:1h:THYAO": [{"close": 1}]}
    method, _, kwargs = session.calls[0]
    assert method == "GET"
    assert kwargs["params"]["store_key"] == "in.(cache:1h:THYAO,cache:1d:THYAO)"


def test_upsert_uses_merge_conflict_and_refreshes_updated_at():
    session = FakeSession([FakeResponse()])
    store = SupabaseStore("https://demo.supabase.co", "test-secret", session=session)

    assert store.upsert("state:telegram_caps", {"gunluk_sayac": 2}) is True

    method, _, kwargs = session.calls[0]
    assert method == "POST"
    assert kwargs["params"] == {"on_conflict": "store_key"}
    assert "resolution=merge-duplicates" in kwargs["headers"]["Prefer"]
    row = kwargs["json"][0]
    assert row["store_key"] == "state:telegram_caps"
    assert row["payload"] == {"gunluk_sayac": 2}
    assert row["updated_at"].endswith("+00:00")


def test_bad_credentials_disable_repeated_requests():
    session = FakeSession([FakeResponse(status_code=401, text="invalid key")])
    store = SupabaseStore("https://demo.supabase.co", "test-secret", session=session)

    assert store.get_many(["state:heartbeat"]) is None
    assert store.enabled is False
    assert store.upsert("state:heartbeat", {}) is False
    assert len(session.calls) == 1


def test_transient_server_error_uses_circuit_breaker(monkeypatch):
    monkeypatch.setattr(supabase_store_module.time, "sleep", lambda _seconds: None)
    session = FakeSession([
        FakeResponse(status_code=503, text="temporary"),
        FakeResponse(status_code=503, text="temporary"),
    ])
    store = SupabaseStore("https://demo.supabase.co", "test-secret", session=session)

    assert store.get_many(["state:heartbeat"]) is None
    assert len(session.calls) == 2
    assert store.get_many(["state:heartbeat"]) is None
    assert len(session.calls) == 2
