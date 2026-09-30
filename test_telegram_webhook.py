"""Telegram webhook modu testleri — ağ erişimi GEREKMEZ.

Kapsam:
- `_telegram_webhook_url_olustur`: TELEGRAM_WEBHOOK_URL / RENDER_EXTERNAL_URL
  önceliği, secret yoksa modun kapalı kalması, https zorunluluğu, log maskeleme
- `_telegram_set_webhook` / `_telegram_delete_webhook`: giden payload ve hata yolları
- `_telegram_komut_katmanini_kur`: webhook / yoklama / kapalı seçimi (tek mod kuralı)
- `_telegram_webhook_isle`: 503 (bot hazır değil) / 200 / 500 sözleşmesi
- `health_server` uçtan uca: /webhook/<secret> secret doğrulama + header + JSON parse
- Tam zincir: gerçek HTTP POST → /panel ve /canli komutu → Telegram'a giden cevap
"""

import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import main as main_mod
from health_server import WEBHOOK_YOL_ONEK, start_render_health_server
from live_state import LiveState
from telegram_commands import TelegramCommandListener

CHAT_ID = "1857000000"
SECRET = "s3cr3t-test-abc"
RENDER_URL = "https://formation-bot.onrender.com"


# --- yardımcılar ---------------------------------------------------------
class SahteYanit:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("JSON gövde yok")
        return self._payload


class SahteSession:
    """requests.Session yerine: çağrıları kaydeder (Telegram'a hiç çıkılmaz)."""

    def __init__(self, get_yanitlari=None, post_yanitlari=None):
        self.get_cagrilari = []
        self.post_cagrilari = []
        self._get_yanitlari = list(get_yanitlari or [])
        self._post_yanitlari = list(post_yanitlari or [])

    def get(self, url, params=None, timeout=None):
        self.get_cagrilari.append((url, dict(params or {})))
        if not self._get_yanitlari:
            return SahteYanit(200, {"ok": True, "result": []})
        yanit = self._get_yanitlari.pop(0)
        return yanit if isinstance(yanit, SahteYanit) else SahteYanit(**yanit)

    def post(self, url, json=None, timeout=None):
        self.post_cagrilari.append((url, dict(json or {})))
        if not self._post_yanitlari:
            return SahteYanit(200, {"ok": True, "result": {"message_id": 1}})
        yanit = self._post_yanitlari.pop(0)
        return yanit if isinstance(yanit, SahteYanit) else SahteYanit(**yanit)

    @property
    def gonderilenler(self):
        return [govde.get("text", "") for _, govde in self.post_cagrilari]


class SahteNotifier:
    enabled = True
    token = "111:AAA"
    chat_id = CHAT_ID


class SahteIsleyici:
    """TelegramCommandListener yerine: ağa çıkmayan sahte komut işleyici."""

    def __init__(self):
        self.basladi = False
        self.guncellemeler = []

    def start(self):
        self.basladi = True
        return True

    def handle_update(self, guncelleme):
        self.guncellemeler.append(guncelleme)
        return "cevap"


def _guncelleme(update_id, metin, chat_id=CHAT_ID):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": int(time.time()),
            "chat": {"id": int(chat_id), "type": "private"},
            "text": metin,
        },
    }


def _post(port, yol, govde, basliklar=None):
    veri = json.dumps(govde).encode("utf-8")
    istek = Request(
        f"http://127.0.0.1:{port}{yol}", data=veri, method="POST",
        headers={"Content-Type": "application/json", **(basliklar or {})},
    )
    try:
        with urlopen(istek, timeout=5) as yanit:
            return yanit.status, json.loads(yanit.read().decode("utf-8"))
    except HTTPError as hata:
        return hata.code, json.loads(hata.read().decode("utf-8"))


def _get(port, yol):
    try:
        with urlopen(f"http://127.0.0.1:{port}{yol}", timeout=5) as yanit:
            return yanit.status, json.loads(yanit.read().decode("utf-8"))
    except HTTPError as hata:
        return hata.code, json.loads(hata.read().decode("utf-8"))


# --- webhook adresi ------------------------------------------------------
def test_webhook_url_render_external_url_ile_uretilir():
    adres = main_mod._telegram_webhook_url_olustur(
        secret=SECRET, render_url="https://formation-bot.onrender.com/")
    assert adres == f"{RENDER_URL}{WEBHOOK_YOL_ONEK}{SECRET}"


def test_webhook_url_secret_yoksa_mod_kapali():
    assert main_mod._telegram_webhook_url_olustur(secret="", render_url=RENDER_URL) == ""
    assert main_mod._telegram_webhook_url_olustur(secret="   ", render_url=RENDER_URL) == ""


def test_webhook_url_taban_adres_yoksa_kapali():
    assert main_mod._telegram_webhook_url_olustur(secret=SECRET, render_url="") == ""


def test_webhook_url_tam_adres_verilirse_aynen_kullanilir():
    tam = f"{RENDER_URL}{WEBHOOK_YOL_ONEK}{SECRET}"
    assert main_mod._telegram_webhook_url_olustur(secret=SECRET, webhook_url=tam) == tam
    # /webhook ile biten adrese sır eklenir
    assert main_mod._telegram_webhook_url_olustur(
        secret=SECRET, webhook_url=f"{RENDER_URL}/webhook") == tam
    # taban adres verilirse yol + sır eklenir
    assert main_mod._telegram_webhook_url_olustur(
        secret=SECRET, webhook_url=RENDER_URL) == tam


def test_webhook_url_https_zorunlu():
    assert main_mod._telegram_webhook_url_olustur(
        secret=SECRET, webhook_url="http://formation-bot.onrender.com") == ""


def test_webhook_adres_gizle_sirri_maskeler():
    adres = f"{RENDER_URL}{WEBHOOK_YOL_ONEK}{SECRET}"
    gizli = main_mod._webhook_adres_gizle(adres, SECRET)
    assert SECRET not in gizli
    assert gizli.endswith("/***")
    # sır yoksa adres aynen kalır
    assert main_mod._webhook_adres_gizle(adres, "") == adres


# --- setWebhook / deleteWebhook ------------------------------------------
def test_set_webhook_dogru_payload_gonderir(monkeypatch):
    cagrilar = []

    def sahte(method, token, payload, timeout=15):
        cagrilar.append((method, token, payload))
        return SahteYanit(200, {"ok": True, "result": True, "description": "Webhook was set"})

    monkeypatch.setattr(main_mod, "_telegram_api_cagri", sahte)
    adres = f"{RENDER_URL}{WEBHOOK_YOL_ONEK}{SECRET}"
    assert main_mod._telegram_set_webhook(url=adres, secret=SECRET, token="111:AAA") is True

    method, token, payload = cagrilar[0]
    assert method == "setWebhook"
    assert token == "111:AAA"
    assert payload["url"] == adres
    assert payload["secret_token"] == SECRET
    assert payload["allowed_updates"] == ["message"]
    # Bayat komutlar (dünkü /tara) webhook kurulunca çalışmasın
    assert payload["drop_pending_updates"] is True


def test_set_webhook_hatali_yanitta_false_doner(monkeypatch):
    monkeypatch.setattr(main_mod, "_telegram_api_cagri",
                        lambda *a, **k: SahteYanit(400, {"ok": False, "description": "Bad Request"}))
    assert main_mod._telegram_set_webhook(url="https://x.onrender.com/webhook/s", secret="s",
                                          token="111:AAA") is False

    def patlat(*_a, **_k):
        raise OSError("ağ yok")

    monkeypatch.setattr(main_mod, "_telegram_api_cagri", patlat)
    assert main_mod._telegram_set_webhook(url="https://x.onrender.com/webhook/s", secret="s",
                                          token="111:AAA") is False


def test_set_webhook_token_veya_adres_yoksa_false_doner(monkeypatch):
    monkeypatch.setattr(main_mod, "TELEGRAM_WEBHOOK_SECRET", "")
    monkeypatch.setattr(main_mod, "RENDER_EXTERNAL_URL", "")
    assert main_mod._telegram_set_webhook(token="") is False          # token yok
    assert main_mod._telegram_set_webhook(token="111:AAA") is False   # adres üretilemez


def test_delete_webhook_payload_gonderir(monkeypatch):
    cagrilar = []
    monkeypatch.setattr(
        main_mod, "_telegram_api_cagri",
        lambda method, token, payload, timeout=15: (
            cagrilar.append((method, token, payload))
            or SahteYanit(200, {"ok": True, "result": True, "description": "Webhook was deleted"})),
    )
    assert main_mod._telegram_delete_webhook(token="111:AAA") is True
    method, token, payload = cagrilar[0]
    assert (method, token) == ("deleteWebhook", "111:AAA")
    assert payload["drop_pending_updates"] is True
    # Token yoksa çağrı bile yapılmaz
    assert main_mod._telegram_delete_webhook(token="") is False


# --- mod seçimi: webhook VEYA yoklama ------------------------------------
def test_komut_katmani_webhook_modunda_yoklamayi_kapatir(monkeypatch):
    monkeypatch.setattr(main_mod, "TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(main_mod, "TELEGRAM_WEBHOOK_URL", "")
    monkeypatch.setattr(main_mod, "RENDER_EXTERNAL_URL", RENDER_URL)
    monkeypatch.setattr(main_mod, "_health_server_ref", object())
    monkeypatch.setattr(main_mod, "_telegram_listener_ref", None)
    monkeypatch.setattr(main_mod, "_telegram_update_processor_ref", None)
    cagrilar = []
    monkeypatch.setattr(main_mod, "_telegram_set_webhook",
                        lambda url=None, secret=None, token=None: (
                            cagrilar.append((url, token)) or True))

    isleyici = SahteIsleyici()
    mod = main_mod._telegram_komut_katmanini_kur(SahteNotifier(), isleyici)

    assert mod == "webhook"
    assert cagrilar == [(f"{RENDER_URL}{WEBHOOK_YOL_ONEK}{SECRET}", "111:AAA")]
    assert main_mod._telegram_update_processor_ref is isleyici   # uç bu nesneyi kullanır
    assert isleyici.basladi is False                            # yoklama BAŞLAMAZ
    assert main_mod._telegram_listener_ref is None


def test_komut_katmani_webhook_kurulamazsa_yoklamaya_duser(monkeypatch):
    monkeypatch.setattr(main_mod, "TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(main_mod, "RENDER_EXTERNAL_URL", RENDER_URL)
    monkeypatch.setattr(main_mod, "_health_server_ref", object())
    monkeypatch.setattr(main_mod, "_telegram_listener_ref", None)
    monkeypatch.setattr(main_mod, "_telegram_update_processor_ref", None)
    monkeypatch.setattr(main_mod, "_telegram_set_webhook", lambda **kw: False)
    silinenler = []
    monkeypatch.setattr(main_mod, "_telegram_delete_webhook",
                        lambda token=None: silinenler.append(token) or True)

    isleyici = SahteIsleyici()
    mod = main_mod._telegram_komut_katmanini_kur(SahteNotifier(), isleyici)

    assert mod == "yoklama"
    assert isleyici.basladi is True
    assert silinenler == ["111:AAA"]        # eski webhook silindi (409 olmasın)
    assert main_mod._telegram_listener_ref is isleyici


def test_komut_katmani_http_sunucusu_yoksa_yoklama(monkeypatch):
    monkeypatch.setattr(main_mod, "TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(main_mod, "RENDER_EXTERNAL_URL", RENDER_URL)
    monkeypatch.setattr(main_mod, "_health_server_ref", None)   # PORT yok / sunucu yok
    monkeypatch.setattr(main_mod, "_telegram_listener_ref", None)
    monkeypatch.setattr(main_mod, "_telegram_update_processor_ref", None)
    monkeypatch.setattr(main_mod, "_telegram_delete_webhook", lambda token=None: True)

    isleyici = SahteIsleyici()
    assert main_mod._telegram_komut_katmanini_kur(SahteNotifier(), isleyici) == "yoklama"
    assert isleyici.basladi is True


def test_komut_katmani_secret_yoksa_yoklama_veya_kapali(monkeypatch):
    monkeypatch.setattr(main_mod, "TELEGRAM_WEBHOOK_SECRET", "")
    monkeypatch.setattr(main_mod, "_telegram_listener_ref", None)
    monkeypatch.setattr(main_mod, "_telegram_update_processor_ref", None)
    monkeypatch.setattr(main_mod, "_telegram_delete_webhook", lambda token=None: True)

    isleyici = SahteIsleyici()
    assert main_mod._telegram_komut_katmanini_kur(SahteNotifier(), isleyici) == "yoklama"
    assert isleyici.basladi is True

    class Kapali:
        enabled = False

    assert main_mod._telegram_komut_katmanini_kur(Kapali()) == "kapali"


# --- uç: _telegram_webhook_isle sözleşmesi -------------------------------
def test_webhook_isle_bot_hazir_degilse_503(monkeypatch):
    monkeypatch.setattr(main_mod, "_telegram_update_processor_ref", None)
    assert main_mod._telegram_webhook_isle(_guncelleme(1, "/panel")) == 503


def test_webhook_isle_guncellemeyi_isleyiciye_verir(monkeypatch):
    isleyici = SahteIsleyici()
    monkeypatch.setattr(main_mod, "_telegram_update_processor_ref", isleyici)
    guncelleme = _guncelleme(7, "/panel")
    assert main_mod._telegram_webhook_isle(guncelleme) == 200
    assert isleyici.guncellemeler == [guncelleme]


def test_webhook_isle_isleyici_hatasinda_500(monkeypatch):
    class Patlayan(SahteIsleyici):
        def handle_update(self, guncelleme):
            raise RuntimeError("patladı")

    monkeypatch.setattr(main_mod, "_telegram_update_processor_ref", Patlayan())
    assert main_mod._telegram_webhook_isle(_guncelleme(8, "/panel")) == 500


# --- health_server /webhook/<secret> ucu ---------------------------------
def _webhook_sunucusu(handler, secret=SECRET):
    return start_render_health_server(
        {"PORT": "0", "TELEGRAM_WEBHOOK_SECRET": secret or ""},
        webhook_handler=handler,
    )


def test_webhook_ucu_secret_tanimli_degilse_404():
    cagrilar = []
    server = _webhook_sunucusu(lambda u: cagrilar.append(u) or 200, secret="")
    try:
        port = server.server_address[1]
        kod, govde = _post(port, f"{WEBHOOK_YOL_ONEK}{SECRET}", _guncelleme(1, "/panel"))
        assert kod == 404
        assert "kapali" in govde["error"]
        assert cagrilar == []          # uç kapalıyken işleyici HİÇ çağrılmaz
        assert _get(port, "/health")[0] == 200   # /health etkilenmez
    finally:
        server.shutdown()
        server.server_close()


def test_webhook_yanlis_secret_403_ve_isleyici_cagrilmaz():
    cagrilar = []
    server = _webhook_sunucusu(lambda u: cagrilar.append(u) or 200)
    try:
        port = server.server_address[1]
        kod, govde = _post(port, f"{WEBHOOK_YOL_ONEK}yanlis-sir", _guncelleme(1, "/panel"))
        assert kod == 403
        assert govde["ok"] is False
        assert cagrilar == []
    finally:
        server.shutdown()
        server.server_close()


def test_webhook_dogru_secret_ile_guncellemeyi_iletir():
    cagrilar = []
    server = _webhook_sunucusu(lambda u: cagrilar.append(u) or 200)
    try:
        port = server.server_address[1]
        guncelleme = _guncelleme(11, "/panel")
        kod, govde = _post(port, f"{WEBHOOK_YOL_ONEK}{SECRET}", guncelleme)
        assert kod == 200
        assert govde["ok"] is True and govde["update_id"] == 11
        assert cagrilar == [guncelleme]          # JSON parse edilip işleyiciye verildi
    finally:
        server.shutdown()
        server.server_close()


def test_webhook_secret_token_basligi_da_dogrulanir():
    cagrilar = []
    server = _webhook_sunucusu(lambda u: cagrilar.append(u) or 200)
    try:
        port = server.server_address[1]
        # Telegram secret_token ile kurunca bu başlığı gönderir
        kod, _ = _post(port, f"{WEBHOOK_YOL_ONEK}{SECRET}", _guncelleme(1, "/panel"),
                       {"X-Telegram-Bot-Api-Secret-Token": SECRET})
        assert kod == 200
        kod2, govde2 = _post(port, f"{WEBHOOK_YOL_ONEK}{SECRET}", _guncelleme(2, "/panel"),
                             {"X-Telegram-Bot-Api-Secret-Token": "baska-sir"})
        assert kod2 == 403
        assert govde2["ok"] is False
        assert len(cagrilar) == 1                # yanlış başlıkla gelen işlenmedi
    finally:
        server.shutdown()
        server.server_close()


def test_webhook_bozuk_json_400_dondurur():
    server = _webhook_sunucusu(lambda u: 200)
    try:
        port = server.server_address[1]
        istek = Request(f"http://127.0.0.1:{port}{WEBHOOK_YOL_ONEK}{SECRET}",
                        data=b"{bu json degil", method="POST",
                        headers={"Content-Type": "application/json"})
        try:
            with urlopen(istek, timeout=5) as yanit:
                kod, govde = yanit.status, json.loads(yanit.read().decode("utf-8"))
        except HTTPError as hata:
            kod, govde = hata.code, json.loads(hata.read().decode("utf-8"))
        assert kod == 400
        assert "JSON" in govde["error"]
        # JSON ama nesne değil -> yine 400
        kod2, _ = _post(port, f"{WEBHOOK_YOL_ONEK}{SECRET}", [1, 2, 3])
        assert kod2 == 400
    finally:
        server.shutdown()
        server.server_close()


def test_webhook_bos_govde_400_dondurur():
    server = _webhook_sunucusu(lambda u: 200)
    try:
        port = server.server_address[1]
        istek = Request(f"http://127.0.0.1:{port}{WEBHOOK_YOL_ONEK}{SECRET}",
                        data=b"", method="POST")
        try:
            with urlopen(istek, timeout=5) as yanit:
                kod = yanit.status
        except HTTPError as hata:
            kod = hata.code
        assert kod == 400
    finally:
        server.shutdown()
        server.server_close()


def test_webhook_isleyici_yoksa_503():
    server = _webhook_sunucusu(None)
    try:
        port = server.server_address[1]
        kod, govde = _post(port, f"{WEBHOOK_YOL_ONEK}{SECRET}", _guncelleme(1, "/panel"))
        assert kod == 503
        assert govde["ok"] is False
        # Telegram güncellemeyi tekrar dener; bu yüzden hata 4xx değil 503 olmalı
    finally:
        server.shutdown()
        server.server_close()


def test_webhook_isleyici_hatasi_500():
    def patlat(_u):
        raise RuntimeError("işleyici patladı")

    server = _webhook_sunucusu(patlat)
    try:
        port = server.server_address[1]
        kod, govde = _post(port, f"{WEBHOOK_YOL_ONEK}{SECRET}", _guncelleme(1, "/panel"))
        assert kod == 500
        assert govde["ok"] is False
    finally:
        server.shutdown()
        server.server_close()


def test_webhook_isleyici_503_dondururse_aynen_iletilir():
    server = _webhook_sunucusu(lambda _u: 503)
    try:
        port = server.server_address[1]
        kod, _ = _post(port, f"{WEBHOOK_YOL_ONEK}{SECRET}", _guncelleme(1, "/panel"))
        assert kod == 503
    finally:
        server.shutdown()
        server.server_close()


def test_webhook_get_telefondan_durum_dondurur():
    server = _webhook_sunucusu(lambda u: 200)
    try:
        port = server.server_address[1]
        kod, govde = _get(port, f"{WEBHOOK_YOL_ONEK}{SECRET}")
        assert kod == 200
        assert govde["webhook"] == "hazir" and govde["bot_hazir"] is True
        assert SECRET not in json.dumps(govde)      # sır yanıtta dönmez
        kod2, _ = _get(port, f"{WEBHOOK_YOL_ONEK}yanlis")
        assert kod2 == 403
    finally:
        server.shutdown()
        server.server_close()


def test_webhook_govde_siniri_asilirsa_413():
    server = _webhook_sunucusu(lambda u: 200)
    try:
        port = server.server_address[1]
        istek = Request(f"http://127.0.0.1:{port}{WEBHOOK_YOL_ONEK}{SECRET}",
                        data=b"{}", method="POST",
                        headers={"Content-Type": "application/json",
                                 "Content-Length": str(5_000_000)})
        try:
            with urlopen(istek, timeout=5) as yanit:
                kod = yanit.status
        except HTTPError as hata:
            kod = hata.code
        assert kod == 413
    finally:
        server.shutdown()
        server.server_close()


def test_webhook_yolu_health_ve_test_ile_cakismaz():
    cagrilar = []
    server = start_render_health_server(
        {"PORT": "0", "TELEGRAM_WEBHOOK_SECRET": SECRET, "TELEGRAM_TEST_KEY": "k7m2x9"},
        test_sender=lambda text: cagrilar.append(text) or (True, "ok"),
        webhook_handler=lambda u: cagrilar.append(u) or 200,
    )
    try:
        port = server.server_address[1]
        assert _get(port, "/health")[0] == 200
        assert _get(port, "/test?k=k7m2x9")[0] == 200
        assert _post(port, f"{WEBHOOK_YOL_ONEK}{SECRET}", _guncelleme(1, "/durum"))[0] == 200
        assert len(cagrilar) == 2       # 1 test mesajı + 1 güncelleme
    finally:
        server.shutdown()
        server.server_close()


# --- uçtan uca: webhook -> komut -> Telegram cevabı -----------------------
def _sahte_formasyonlar(durum, adet=4):
    durum.begin_scan()
    tfs = ["1h", "2h", "4h", "1d"]
    for i in range(adet):
        durum.record_formation({
            "stock": f"HISSE{i}", "timeframe": tfs[i % 4], "pattern_name": "Yükselen Üçgen",
            "quality": 90 - i, "state": "KIRILIM_TEYITLI" if i == 0 else "SIKISMA_GUCLENIYOR",
            "break_dir": 1, "upper": 100 + i, "lower": 95 + i, "critical_price": 100 + i,
            "min_quality": 80, "alert_gonderildi": False,
        })
    durum.finish_scan(son_tarama_suresi_dk=1.0, son_tarama_hissesi=48)


def test_webhook_panel_analizini_kuyruga_alir_ve_diger_komutlari_yok_sayar(monkeypatch):
    """Webhook /panel başlangıcını yanıtlar; iş sürerken diğer komutlar sessizdir."""
    monkeypatch.setattr(main_mod, "_scan_job_active", __import__("threading").Event())
    monkeypatch.setattr(main_mod, "_scan_istegi", __import__("threading").Event())
    monkeypatch.setattr(main_mod, "_scan_job_request", None)
    monkeypatch.setattr(main_mod, "_live_state", LiveState())
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", ["THYAO", "GARAN"])

    session = SahteSession()
    dinleyici = TelegramCommandListener(
        token="111:AAA", allowed_chat_id=CHAT_ID,
        handlers=main_mod.TELEGRAM_KOMUTLARI, help_text=main_mod.KOMUT_YARDIM,
        session=session,
        komutlari_yoksay=lambda: main_mod._scan_job_active.is_set(),
    )
    monkeypatch.setattr(main_mod, "_telegram_update_processor_ref", dinleyici)

    server = start_render_health_server(
        {"PORT": "0", "TELEGRAM_WEBHOOK_SECRET": SECRET},
        webhook_handler=main_mod._telegram_webhook_isle,
    )
    try:
        port = server.server_address[1]
        kod, govde = _post(port, f"{WEBHOOK_YOL_ONEK}{SECRET}", _guncelleme(1, "/panel"))
        assert kod == 200 and govde["ok"] is True
        assert "Analiz başladı" in session.gonderilenler[-1]
        assert main_mod._scan_job_request["tip"] == "panel"
        assert main_mod._scan_job_active.is_set()

        onceki = len(session.post_cagrilari)
        kod2, _ = _post(port, f"{WEBHOOK_YOL_ONEK}{SECRET}", _guncelleme(2, "/canli"))
        assert kod2 == 200
        assert len(session.post_cagrilari) == onceki
    finally:
        main_mod._scan_job_active.clear()
        main_mod._scan_istegi.clear()
        main_mod._scan_job_request = None
        server.shutdown()
        server.server_close()
