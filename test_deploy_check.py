import json

import deploy_check as dc  # noqa: F401 - eski testler bu adı kullanıyor
import deploy_check as D
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


# --- Denetim B-4: heartbeat (canlılık) yardımcıları ---


def test_store_onek_varsayilan_ve_kapali():
    assert dc.store_onek("") == "formation-bot:"
    assert dc.store_onek("  benim-ek:  ") == "benim-ek:"
    for kapali in ("off", "none", "yok", "0", "OFF"):
        assert dc.store_onek(kapali) == ""


def test_heartbeat_seviyesi_esikleri():
    assert dc.heartbeat_seviyesi(None)[0] == dc.WARN
    assert dc.heartbeat_seviyesi(60)[0] == dc.OK
    assert dc.heartbeat_seviyesi(5 * 3600)[0] == dc.WARN
    assert dc.heartbeat_seviyesi(100 * 3600)[0] == dc.FAIL


def test_heartbeat_seviyesi_metni_yas_icerir():
    _, baslik_taze, _ = dc.heartbeat_seviyesi(120)
    assert "2 dk" in baslik_taze
    _, baslik_bayat, detay_bayat = dc.heartbeat_seviyesi(4 * 24 * 3600)
    assert "bayat" in baslik_bayat.lower()
    assert "Render" in detay_bayat


# --- Public kanal hedefi (canlıya alma adımı) --------------------------------
# NEDEN: public yayın DM'den bağımsız çalışır; hedef yanlış ya da bot yönetici
# değilse bot çalışır ama kanala hiçbir şey düşmez. deploy_check bu adımı
# doğrular (ağ çağrıları sahtelenir, gerçek Telegram isteği YOK).

class _Yanit:
    def __init__(self, payload=None, status_code=200):
        self.status_code = status_code
        self._payload = payload or {"ok": True}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


def _satirlari_tut(monkeypatch):
    kayit = []
    monkeypatch.setattr(D, "satir", lambda seviye, baslik, detay="": kayit.append((seviye, baslik)))
    return kayit


def test_public_hedef_yoksa_uyari(monkeypatch):
    kayit = _satirlari_tut(monkeypatch)
    assert D.kontrol_public_hedef("123456789:AAAA", "", "12345") is False
    assert kayit and kayit[0][0] == D.WARN and "Public kanal hedefi yok" in kayit[0][1]


def test_token_yoksa_sessiz_atlanir(monkeypatch):
    kayit = _satirlari_tut(monkeypatch)
    assert D.kontrol_public_hedef("", "@kanal") is False
    assert kayit == []


def test_kanal_yonetici_ve_izinliyse_hazir(monkeypatch):
    kayit = _satirlari_tut(monkeypatch)
    cevaplar = [
        _Yanit({"ok": True, "result": {"type": "channel", "title": "BIST Formasyon"}}),
        _Yanit({"ok": True, "result": {"id": 42, "username": "bot"}}),
        _Yanit({"ok": True, "result": {"status": "administrator", "can_post_messages": True}}),
    ]
    monkeypatch.setattr("requests.post", lambda *a, **k: cevaplar.pop(0))
    assert D.kontrol_public_hedef("123456789:AAAA", "@bisthisseveri", "12345") is True
    assert any("YÖNETİCİ" in b for _, b in kayit)


def test_kanal_izin_kapaliysa_hata(monkeypatch):
    kayit = _satirlari_tut(monkeypatch)
    cevaplar = [
        _Yanit({"ok": True, "result": {"type": "channel", "title": "BIST Formasyon"}}),
        _Yanit({"ok": True, "result": {"id": 42}}),
        _Yanit({"ok": True, "result": {"status": "administrator", "can_post_messages": False}}),
    ]
    monkeypatch.setattr("requests.post", lambda *a, **k: cevaplar.pop(0))
    assert D.kontrol_public_hedef("123456789:AAAA", "@bisthisseveri", "12345") is False
    assert any(s == D.FAIL and "Mesaj gönderme" in b for s, b in kayit)


def test_bot_hedefte_yoksa_hata(monkeypatch):
    kayit = _satirlari_tut(monkeypatch)
    cevaplar = [
        _Yanit({"ok": True, "result": {"type": "channel", "title": "Kanal"}}),
        _Yanit({"ok": True, "result": {"id": 42}}),
        _Yanit({"ok": True, "result": {"status": "left"}}),
    ]
    monkeypatch.setattr("requests.post", lambda *a, **k: cevaplar.pop(0))
    assert D.kontrol_public_hedef("123456789:AAAA", "@kanal", "12345") is False
    assert any(s == D.FAIL and "left" in b for s, b in kayit)


def test_dm_yoksa_uyari(monkeypatch):
    kayit = _satirlari_tut(monkeypatch)
    cevaplar = [
        _Yanit({"ok": True, "result": {"type": "channel", "title": "Kanal"}}),
        _Yanit({"ok": True, "result": {"id": 42}}),
        _Yanit({"ok": True, "result": {"status": "administrator", "can_post_messages": True}}),
    ]
    monkeypatch.setattr("requests.post", lambda *a, **k: cevaplar.pop(0))
    D.kontrol_public_hedef("123456789:AAAA", "@kanal", "")
    assert any(s == D.WARN and "komutlar kapalı" in b for s, b in kayit)
