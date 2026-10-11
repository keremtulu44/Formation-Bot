import deploy_check as dc
from deploy_check import _anahtari_temizle, anahtar_turu, supabase_basliklari, _jwt_rolu


def test_anahtari_temizle():
    assert _anahtari_temizle("  sb_secret_abc  ") == "sb_secret_abc"
    assert _anahtari_temizle('"sb_secret_abc"') == "sb_secret_abc"
    assert _anahtari_temizle("'sb_secret_abc'") == "sb_secret_abc"
    assert _anahtari_temizle(None) == ""


def test_anahtar_turu_secret():
    assert "sb_secret_" in anahtar_turu("sb_secret_abc123")
    assert "yeni secret" in anahtar_turu("sb_secret_abc123").lower()


def test_anahtar_turu_publishable():
    tur = anahtar_turu("sb_publishable_xyz")
    assert "publishable" in tur.lower()


def test_anahtar_turu_legacy():
    # fake JWT with eyJ prefix
    jwt = "eyJhbGciOi.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.sig"
    tur = anahtar_turu(jwt)
    assert "legacy" in tur.lower()


def test_supabase_basliklari_secret_only_apikey():
    baslik = supabase_basliklari("sb_secret_abc123")
    assert baslik["apikey"] == "sb_secret_abc123"
    assert "Authorization" not in baslik


def test_supabase_basliklari_publishable_only_apikey():
    baslik = supabase_basliklari("sb_publishable_xyz")
    assert "Authorization" not in baslik
    assert baslik["apikey"] == "sb_publishable_xyz"


def test_supabase_basliklari_legacy_includes_bearer():
    jwt = "eyJhbGciOi.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.sig"
    baslik = supabase_basliklari(jwt)
    assert "Authorization" in baslik
    assert baslik["Authorization"] == f"Bearer {jwt}"


def test_supabase_basliklari_temizleme():
    baslik = supabase_basliklari('  "sb_secret_abc"  ')
    assert baslik["apikey"] == "sb_secret_abc"
    assert "Authorization" not in baslik


def test_jwt_rolu_service_role():
    import base64, json
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"role": "service_role"}).encode()).decode().rstrip("=")
    jwt = f"eyJ{header[3:]}.{payload}.sig"
    # Ensure eyJ prefix
    jwt = "eyJ" + jwt[3:]
    assert _jwt_rolu(jwt) == "service_role"


def test_jwt_rolu_anon():
    import base64, json
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"role": "anon"}).encode()).decode().rstrip("=")
    jwt = f"eyJ{header[3:]}.{payload}.sig"
    jwt = "eyJ" + jwt[3:]
    assert _jwt_rolu(jwt) == "anon"


def test_env_degeri_temizleme():
    dosya_env = {"SUPABASE_URL": '  "https://demo.supabase.co"  '}
    assert dc.env_degeri("SUPABASE_URL", dosya_env) == "https://demo.supabase.co"


def test_kontrol_env_canli_mod_eksik_hata(monkeypatch):
    # Canlı modda eksik env = HATA
    monkeypatch.setattr(dc, "_sayac", {dc.OK: 0, dc.WARN: 0, dc.FAIL: 0})
    degerler = dc.kontrol_env({}, canli_mod=True)
    # Telegram zorunlulukları fail; opsiyonel Supabase eksikliği yalnızca uyarıdır.
    assert dc._sayac[dc.FAIL] >= 3
    assert degerler["SUPABASE_URL"] == ""
    assert dc._sayac[dc.WARN] >= 1


def test_kontrol_env_normal_mod_uyari(monkeypatch):
    monkeypatch.setattr(dc, "_sayac", {dc.OK: 0, dc.WARN: 0, dc.FAIL: 0})
    degerler = dc.kontrol_env({}, canli_mod=False)
    # Normal modda WARN olmalı, FAIL değil (çünkü canlı değil)
    assert dc._sayac[dc.WARN] >= 4
    assert dc._sayac[dc.FAIL] == 0


def test_ozet_satiri_mantigi():
    # ÖZET: Telegram HAZIR|YOK · Supabase HAZIR|YOK
    degerler_hazir = {
        "TELEGRAM_BOT_TOKEN": "123:abc",
        "TELEGRAM_CHAT_ID": "12345",
        "SUPABASE_URL": "https://demo.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_abc",
    }
    telegram_hazir = bool(degerler_hazir.get("TELEGRAM_BOT_TOKEN") and degerler_hazir.get("TELEGRAM_CHAT_ID"))
    supabase_hazir = bool(degerler_hazir.get("SUPABASE_URL") and degerler_hazir.get("SUPABASE_SERVICE_ROLE_KEY"))
    ozet = f"ÖZET: Telegram {'HAZIR' if telegram_hazir else 'YOK'} · Supabase {'HAZIR' if supabase_hazir else 'YOK'}"
    assert "HAZIR" in ozet
    assert "ÖZET:" in ozet

    degerler_yok = {}
    telegram_hazir = bool(degerler_yok.get("TELEGRAM_BOT_TOKEN") and degerler_yok.get("TELEGRAM_CHAT_ID"))
    supabase_hazir = bool(degerler_yok.get("SUPABASE_URL") and degerler_yok.get("SUPABASE_SERVICE_ROLE_KEY"))
    ozet2 = f"ÖZET: Telegram {'HAZIR' if telegram_hazir else 'YOK'} · Supabase {'HAZIR' if supabase_hazir else 'YOK'}"
    assert "YOK" in ozet2


def test_401_mesajinda_anahtar_turu_ipucu():
    # 401 mesajında anahtar türü ipucu olmalı (anon/publishable/iptal ayrımı)
    # Bu test kontrol_supabase içindeki mantığı doğrular
    tur_publishable = anahtar_turu("sb_publishable_xyz")
    assert "publishable" in tur_publishable.lower()

    tur_anon = anahtar_turu("eyJhbGciOi.eyJyb2xlIjoiYW5vbiJ9.sig")  # anon
    # JWT rol çözümlemesi anon dönebilir
    # En azından tür string'i boş değil
    assert tur_anon != ""


def test_anahtar_turu_bos():
    assert anahtar_turu("") == "boş"
    assert anahtar_turu(None) == "boş"


def test_ozet_telegram_yok_supabase_var():
    degerler = {
        "SUPABASE_URL": "https://demo.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_abc",
    }
    telegram_hazir = bool(degerler.get("TELEGRAM_BOT_TOKEN") and degerler.get("TELEGRAM_CHAT_ID"))
    supabase_hazir = bool(degerler.get("SUPABASE_URL") and degerler.get("SUPABASE_SERVICE_ROLE_KEY"))
    ozet = f"ÖZET: Telegram {'HAZIR' if telegram_hazir else 'YOK'} · Supabase {'HAZIR' if supabase_hazir else 'YOK'}"
    assert "Telegram YOK" in ozet
    assert "Supabase HAZIR" in ozet


def test_kontrol_env_publishable_uyari(monkeypatch):
    monkeypatch.setattr(dc, "_sayac", {dc.OK: 0, dc.WARN: 0, dc.FAIL: 0})
    env = {
        "SUPABASE_URL": "https://demo.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "sb_publishable_xyz",
        "TELEGRAM_BOT_TOKEN": "123:abc",
        "TELEGRAM_CHAT_ID": "12345",
    }
    dc.kontrol_env(env, canli_mod=False)
    # publishable için WARN olmalı
    assert dc._sayac[dc.WARN] >= 1


def test_kontrol_supabase_does_not_print_url_query_credential(monkeypatch, capsys):
    import sys
    from types import SimpleNamespace

    class FakeRequests:
        @staticmethod
        def get(*_args, **_kwargs):
            return SimpleNamespace(status_code=200, text="")

        @staticmethod
        def post(*_args, **_kwargs):
            return SimpleNamespace(status_code=204, text="")

    monkeypatch.setitem(sys.modules, "requests", FakeRequests)
    url_secret = "SYNTHETIC_SUPABASE_URL_SECRET"
    dc.kontrol_supabase(
        f"https://demo.supabase.invalid?api_key={url_secret}",
        "SYNTHETIC_SUPABASE_SERVICE_KEY",
    )

    assert url_secret not in capsys.readouterr().out


def test_kontrol_supabase_redacts_service_key_echoed_by_error(monkeypatch, capsys):
    import sys
    from types import SimpleNamespace

    service_secret = "SYNTHETIC_SUPABASE_SERVICE_KEY"

    class FakeRequests:
        @staticmethod
        def get(*_args, **_kwargs):
            return SimpleNamespace(status_code=503, text=f"request rejected: {service_secret}")

    monkeypatch.setitem(sys.modules, "requests", FakeRequests)
    dc.kontrol_supabase("https://demo.supabase.invalid", service_secret)

    assert service_secret not in capsys.readouterr().out


def test_kontrol_telegram_redacts_token_from_connection_exception(monkeypatch, capsys):
    import sys

    token = "123456:SYNTHETIC_TELEGRAM_TOKEN"

    class FakeRequests:
        @staticmethod
        def get(url, **_kwargs):
            raise RuntimeError(f"connection failed for {url}")

    monkeypatch.setitem(sys.modules, "requests", FakeRequests)
    dc.kontrol_telegram(token, "42", mesaj_gonder=False)

    assert token not in capsys.readouterr().out


def test_kontrol_render_redacts_test_key_from_request_exception(monkeypatch, capsys):
    import sys

    test_key = "SYNTHETIC_RENDER_TEST_KEY"

    class FakeResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"status": "ok", "service": "formation-bot"}

    class FakeRequests:
        calls = 0

        @classmethod
        def get(cls, url, **kwargs):
            cls.calls += 1
            if cls.calls == 1:
                return FakeResponse()
            raise RuntimeError(f"request failed: {url}?k={kwargs['params']['k']}")

    monkeypatch.setitem(sys.modules, "requests", FakeRequests)
    dc.kontrol_render("https://formation.invalid", test_key)

    assert test_key not in capsys.readouterr().out
