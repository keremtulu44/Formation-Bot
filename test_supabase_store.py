import base64
import json
import supabase_store as supabase_store_module
from supabase_store import SupabaseStore, _anahtari_temizle, anahtar_turu, supabase_basliklari


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


def _fake_jwt(role: str) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=")
    return f"{header}.{payload}.signature"


def test_from_env_requires_both_values():
    assert SupabaseStore.from_env({}) is None
    assert SupabaseStore.from_env({"SUPABASE_URL": "https://demo.supabase.co"}) is None
    store = SupabaseStore.from_env({
        "SUPABASE_URL": "https://demo.supabase.co/",
        "SUPABASE_SERVICE_ROLE_KEY": "test-secret",
    })
    assert store.rest_url == "https://demo.supabase.co/rest/v1/bot_store"


def test_rest_api_url_variant_is_normalised():
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
    session = FakeSession([
        FakeResponse(payload=[
            {"store_key": "formation-bot:cache:1h:THYAO", "payload": [{"close": 1}]},
        ]),
        FakeResponse(payload=[]),   # eksik anahtar için legacy (öneksiz) tur
    ])
    store = SupabaseStore("https://demo.supabase.co", "test-secret", session=session)

    result = store.get_many(["cache:1h:THYAO", "cache:1d:THYAO"])

    # Çağıran taraf ÖNEKSİZ adları görür; istek ön ekli anahtarla gider (C3).
    assert result == {"cache:1h:THYAO": [{"close": 1}]}
    method, _, kwargs = session.calls[0]
    assert method == "GET"
    assert kwargs["params"]["store_key"] == \
        "in.(formation-bot:cache:1h:THYAO,formation-bot:cache:1d:THYAO)"


def test_upsert_uses_merge_conflict_and_refreshes_updated_at():
    session = FakeSession([FakeResponse()])
    store = SupabaseStore("https://demo.supabase.co", "test-secret", session=session)

    assert store.upsert("state:telegram_caps", {"gunluk_sayac": 2}) is True

    method, _, kwargs = session.calls[0]
    assert method == "POST"
    assert kwargs["params"] == {"on_conflict": "store_key"}
    assert "resolution=merge-duplicates" in kwargs["headers"]["Prefer"]
    row = kwargs["json"][0]
    assert row["store_key"] == "formation-bot:state:telegram_caps"
    assert row["payload"] == {"gunluk_sayac": 2}
    assert row["updated_at"].endswith("+00:00")


def test_legacy_oneksiz_anahtarlar_okunur():
    """C3: ön ek devreye girerken mevcut (öneksiz) kayıtlar kaybolmaz."""
    session = FakeSession([
        FakeResponse(payload=[]),                                     # ön ekli sorgu boş
        FakeResponse(payload=[{"store_key": "state:heartbeat", "payload": {"a": 1}}]),
    ])
    store = SupabaseStore("https://demo.supabase.co", "test-secret", session=session)
    sonuc = store.get_many(["state:heartbeat"])
    assert sonuc == {"state:heartbeat": {"a": 1}}
    assert session.calls[1][2]["params"]["store_key"] == "in.(state:heartbeat)"


def test_onek_env_ile_kapatilir(monkeypatch):
    monkeypatch.setenv("SUPABASE_STORE_PREFIX", "off")
    session = FakeSession([FakeResponse()])
    store = SupabaseStore("https://demo.supabase.co", "test-secret", session=session)
    store.upsert("state:heartbeat", {})
    assert session.calls[0][2]["json"][0]["store_key"] == "state:heartbeat"


def test_onek_env_ile_ozel(monkeypatch):
    monkeypatch.setenv("SUPABASE_STORE_PREFIX", "proje-x:")
    session = FakeSession([FakeResponse()])
    store = SupabaseStore("https://demo.supabase.co", "test-secret", session=session)
    store.upsert("cache:1h:THYAO", [])
    assert session.calls[0][2]["json"][0]["store_key"] == "proje-x:cache:1h:THYAO"


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


# --- Yeni anahtar formatı testleri ---

def test_anahtari_temizle_bosluk_ve_tirnak():
    assert _anahtari_temizle("  sb_secret_abc123  ") == "sb_secret_abc123"
    assert _anahtari_temizle('"sb_secret_abc123"') == "sb_secret_abc123"
    assert _anahtari_temizle("'sb_secret_abc123'") == "sb_secret_abc123"
    assert _anahtari_temizle('  " sb_secret_abc123 "  ') == "sb_secret_abc123"
    assert _anahtari_temizle(None) == ""
    assert _anahtari_temizle("") == ""


def test_anahtar_turu_yeni_secret():
    assert "sb_secret_" in anahtar_turu("sb_secret_abc123")
    assert "yeni secret" in anahtar_turu("sb_secret_abc123")


def test_anahtar_turu_publishable():
    tur = anahtar_turu("sb_publishable_xyz")
    assert "publishable" in tur.lower()
    assert "sb_publishable_" in tur


def test_anahtar_turu_legacy_jwt_service_role():
    jwt = _fake_jwt("service_role")
    # eyJ ile başlatmak için header'ı eyJ yapalım
    jwt = "eyJ" + jwt[3:]
    tur = anahtar_turu(jwt)
    assert "legacy" in tur.lower()
    assert "service_role" in tur


def test_anahtar_turu_legacy_jwt_anon():
    jwt = _fake_jwt("anon")
    jwt = "eyJ" + jwt[3:]
    tur = anahtar_turu(jwt)
    assert "legacy" in tur.lower()
    assert "anon" in tur.lower()


def test_supabase_basliklari_yeni_secret_sadece_apikey():
    baslik = supabase_basliklari("sb_secret_abc123")
    assert baslik["apikey"] == "sb_secret_abc123"
    assert "Authorization" not in baslik
    assert "Content-Type" in baslik


def test_supabase_basliklari_publishable_sadece_apikey():
    baslik = supabase_basliklari("sb_publishable_xyz")
    assert baslik["apikey"] == "sb_publishable_xyz"
    assert "Authorization" not in baslik


def test_supabase_basliklari_legacy_jwt_ikisi_birden():
    jwt = "eyJhbGciOi.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.signature"
    baslik = supabase_basliklari(jwt)
    assert baslik["apikey"] == jwt
    assert "Authorization" in baslik
    assert baslik["Authorization"] == f"Bearer {jwt}"


def test_supabase_basliklari_temizleme():
    baslik = supabase_basliklari('  "sb_secret_abc123"  ')
    assert baslik["apikey"] == "sb_secret_abc123"
    assert "Authorization" not in baslik


def test_store_init_yeni_secret_baslik_kurali():
    session = FakeSession([FakeResponse(payload=[])])
    store = SupabaseStore("https://demo.supabase.co", "sb_secret_test123", session=session)
    assert "Authorization" not in store._headers
    assert store._headers["apikey"] == "sb_secret_test123"


def test_store_init_legacy_jwt_baslik_kurali():
    jwt = "eyJhbGciOi.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.signature"
    session = FakeSession([FakeResponse(payload=[])])
    store = SupabaseStore("https://demo.supabase.co", jwt, session=session)
    assert "Authorization" in store._headers
    assert store._headers["Authorization"] == f"Bearer {jwt}"


def test_from_env_tirnak_temizligi():
    env = {
        "SUPABASE_URL": '  "https://demo.supabase.co/rest/v1/"  ',
        "SUPABASE_SERVICE_ROLE_KEY": "  'sb_secret_abc123'  ",
    }
    store = SupabaseStore.from_env(env)
    assert store is not None
    assert store.project_url == "https://demo.supabase.co"
    assert store._headers["apikey"] == "sb_secret_abc123"
    assert "Authorization" not in store._headers
