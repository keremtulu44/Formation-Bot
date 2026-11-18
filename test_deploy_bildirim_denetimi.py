"""2026-11-18 deploy + bildirim uçtan uca denetim regresyonları.

Ağsız kalan senaryolar: public-only Telegram, public ana kuyruğun tarama dışı
flush'ı, /health bildirim gözlemlenebilirliği, dar teslim yedeği, Blueprint/CI
paritesi. Gerçek Render/Telegram/Supabase çağrısı yoktur.
"""
from __future__ import annotations

import json
from datetime import datetime, time as dt_time
from pathlib import Path
from types import SimpleNamespace

import pytest

import deploy_check as D
from config import ISTANBUL_TZ
from notification_delivery import KEY, DeliveryOnlyStore, DeliveryOutbox

ROOT = Path(__file__).resolve().parent


def _env_temizle(monkeypatch, *anahtarlar):
    for anahtar in anahtarlar:
        monkeypatch.delenv(anahtar, raising=False)


def _sayaci_sifirla(monkeypatch):
    monkeypatch.setattr(D, "_sayac", {D.OK: 0, D.WARN: 0, D.FAIL: 0})


# --- 1) Kurulum doktoru: public-only + eksiksiz runtime env görünürlüğü -----

def test_deploy_check_public_only_canli_modda_hata_vermez(monkeypatch, capsys):
    _env_temizle(monkeypatch, "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                 "TELEGRAM_GROUP_ID", "TELEGRAM_CHANNEL_ID", "SUPABASE_URL",
                 "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_DELIVERY_WRITES")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-100999")
    _sayaci_sifirla(monkeypatch)
    degerler = D.kontrol_env({}, canli_mod=True)
    cikti = capsys.readouterr().out
    assert degerler["TELEGRAM_GROUP_ID"] == "-100999"
    assert "Public-only Telegram kurulumu" in cikti
    assert D._sayac[D.FAIL] == 0
    assert "Telegram teslim hedefi yok" not in cikti


def test_deploy_check_eski_kanal_degiskeni_ozette_gorunur(monkeypatch, capsys):
    _env_temizle(monkeypatch, "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                 "TELEGRAM_GROUP_ID", "TELEGRAM_CHANNEL_ID")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@EskiKanal")
    _sayaci_sifirla(monkeypatch)
    degerler = D.kontrol_env({}, canli_mod=True)
    assert degerler["TELEGRAM_CHANNEL_ID"] == "@EskiKanal"
    assert "Public-only Telegram kurulumu" in capsys.readouterr().out
    assert D._sayac[D.FAIL] == 0


def test_deploy_check_tv_port_tz_ve_teslim_yedegi_env_listesinde(monkeypatch, capsys):
    for anahtar in ("TV_YEDEK_AKTIF", "TV_GERCEK_4S_AKTIF", "TV_EXCHANGE",
                    "TV_BAR_SAYISI", "TV_ZAMAN_ASIMI_SN", "PORT", "TZ",
                    "DATA_DIR", "LOG_DIR", "LOCAL_LOG_DIR",
                    "SUPABASE_DELIVERY_WRITES"):
        monkeypatch.setenv(anahtar, "1" if anahtar.startswith("TV_") or anahtar == "SUPABASE_DELIVERY_WRITES" else "deger")
    _sayaci_sifirla(monkeypatch)
    degerler = D.kontrol_env({}, canli_mod=False)
    cikti = capsys.readouterr().out
    for anahtar in ("TV_YEDEK_AKTIF", "TV_BAR_SAYISI", "PORT", "TZ",
                    "DATA_DIR", "LOG_DIR", "LOCAL_LOG_DIR",
                    "SUPABASE_DELIVERY_WRITES"):
        assert anahtar in degerler
        assert f"{anahtar} tanımlı" in cikti


def test_deploy_check_public_only_test_mesaji_kanala_gider(monkeypatch, capsys):
    import requests

    class Cevap:
        status_code = 200
        text = "{}"

        def json(self):
            return {"ok": True, "result": {"id": 7, "username": "deneme_bot"}}

    cagrilar = []

    def post(url, json=None, timeout=None):
        cagrilar.append((url, dict(json or {})))
        return Cevap()

    monkeypatch.setattr(requests, "get", lambda *a, **k: Cevap())
    monkeypatch.setattr(requests, "post", post)
    _sayaci_sifirla(monkeypatch)
    D.kontrol_telegram("123:abc", "", True, public_hedef="-100999")
    assert "Public-only hedef" in capsys.readouterr().out
    assert any(govde["chat_id"] == "-100999" for _, govde in cagrilar)
    assert D._sayac[D.FAIL] == 0


# --- 2) /health: public-only mod ve incelemeye açık kuyruklar ----------------

def test_health_bildirim_public_only_kuyruklari_sir_olmadan_raporlar(monkeypatch):
    import main as main_mod

    class SahteNotifier:
        enabled = False
        public_enabled = True
        persistent_store = None
        remote_delivery_store = None

        def gonderim_durumu(self):
            return {
                "teslim_kuyrugu": {"pending": 0, "last_error": None, "attempts": 0},
                "acil_kuyruk": 0,
                "public_kuyruk": 2,
                "public_ozel_kuyruk": {"available": True, "pending": 1, "review": 1},
                "dm_ozel_kuyruk": {"available": True, "pending": 0, "review": 0},
                "public_hedef_inceleme": {"available": True, "archives": 0},
                "grafik_kuyruk": 0,
                "son_basarili_gonderim": None,
                "son_public_gonderim": "2026-11-18T12:00:00+03:00",
                "son_gonderme_hatasi": None,
                "public_hatasi": 0,
                "public_kuyruk_tasmasi": 0,
                "public_state_writable": True,
                "public_chat_id": "-100999",  # JSON'a çıkmamalı
            }

    monkeypatch.setattr(main_mod, "_notifier_ref", SahteNotifier(), raising=False)
    b = main_mod._saglik_ozeti()["bildirim"]
    assert b["mod"] == "public-only"
    assert b["enabled"] is False and b["public_enabled"] is True
    assert b["public_kuyruk"] == 2
    assert b["public_ozel_kuyruk"]["review"] == 1
    assert b["durum"] == "inceleme"
    assert any("public özel" in neden for neden in b["nedenler"])
    assert "public_chat_id" not in b
    json.dumps(b)  # /health JSON serileştirmesi güvenli


def test_health_bildirim_notifier_yokken_livenessi_dusurmez(monkeypatch):
    import main as main_mod

    monkeypatch.setattr(main_mod, "_notifier_ref", None, raising=False)
    ozet = main_mod._saglik_ozeti()
    assert ozet["bildirim"]["durum"] == "bilinmiyor"
    assert ozet["bildirim"]["nedenler"] == ["notifier kurulmadi"]


# --- 3) Public ana kuyruk tarama dışında da boşaltılır -----------------------

def test_public_bulten_public_only_ana_dongude_bosaltir(monkeypatch):
    import main as main_mod

    cagrilar = []

    class SahteNotifier:
        public_enabled = True

        def public_bosalt(self):
            cagrilar.append("flush")
            return 3

    monkeypatch.setattr(main_mod, "_shutdown_requested", False, raising=False)
    simdi = ISTANBUL_TZ.localize(datetime(2026, 11, 18, 12, 0))
    adet, yeni = main_mod._public_bulten_bosalt(
        SahteNotifier(), simdi, dt_time(18, 45), 0.0,
    )
    assert (adet, cagrilar) == (3, ["flush"])
    assert yeni > 0


def test_public_bulten_dm_enabled_kapaliyken_bile_public_aciksa_calisir(monkeypatch):
    import main as main_mod

    class SahteNotifier:
        enabled = False  # DM kapalı: eski yanlış kapı buraya bakıyordu
        public_enabled = True

        def public_bosalt(self):
            return 1

    monkeypatch.setattr(main_mod, "_shutdown_requested", False, raising=False)
    simdi = ISTANBUL_TZ.localize(datetime(2026, 11, 18, 17, 0))
    assert main_mod._public_bulten_bosalt(
        SahteNotifier(), simdi, dt_time(18, 45), 0.0,
    )[0] == 1


def test_public_bulten_hafta_sonu_ve_digest_sonrasi_push_yapmaz(monkeypatch):
    import main as main_mod

    class SahteNotifier:
        public_enabled = True

        def public_bosalt(self):
            pytest.fail("kapalı pencerede Telegram'a çıkılmamalı")

    monkeypatch.setattr(main_mod, "_shutdown_requested", False, raising=False)
    for simdi in (ISTANBUL_TZ.localize(datetime(2026, 11, 21, 12, 0)),
                  ISTANBUL_TZ.localize(datetime(2026, 11, 18, 19, 0))):
        assert main_mod._public_bulten_bosalt(
            SahteNotifier(), simdi, dt_time(18, 45), 0.0,
        )[0] == 0


# --- 4) Dar Supabase teslim yedeği: tek anahtar, yerel kayıt korunur ---------

def test_delivery_only_store_sadece_teslim_anahtarini_yazar(tmp_path):
    cagrilar = []
    uzak = {
        "rows": [{"id": " bekleyen ", "done": False}],
        "public": [],
        "saved_at": "2026-11-18T12:00:00+03:00",
    }

    class Store:
        writable = True

        def get_many(self, keys):
            assert keys == [KEY]
            return {KEY: uzak}

        def upsert(self, key, payload):
            cagrilar.append((key, payload))
            return True

    dar = DeliveryOnlyStore(Store())
    assert dar.writable is True
    assert dar.upsert("state:heartbeat", {"x": 1}) is False
    owner = SimpleNamespace(initial_store_data={}, persistent_store=None,
                            remote_delivery_store=dar)
    outbox = DeliveryOutbox(owner, tmp_path)
    assert outbox.state["rows"] == uzak["rows"]
    outbox.save()
    assert (tmp_path / "notification_delivery.json").exists()
    assert [anahtar for anahtar, _ in cagrilar] == [KEY]


def test_delivery_only_store_read_only_underlying_yazmaz(tmp_path):
    class Store:
        writable = False

        def get_many(self, keys):
            return {}

        def upsert(self, key, payload):
            pytest.fail("salt okunur store'a yazılmamalı")

    dar = DeliveryOnlyStore(Store())
    owner = SimpleNamespace(initial_store_data={}, persistent_store=None,
                            remote_delivery_store=dar)
    outbox = DeliveryOutbox(owner, tmp_path)
    outbox.save()  # yerel atomik kayıt yine yazılır, exception çıkmaz
    assert dar.upsert(KEY, {}) is False
    assert (tmp_path / "notification_delivery.json").exists()


def test_bot_startup_opt_in_delivery_writer_yalniz_dar_store_gecirir(monkeypatch):
    import bot.app as app
    from state import formation_mirror as mirror

    class StopStartup(Exception):
        pass

    pkg = app._pkg
    reader = SimpleNamespace(writable=False, ping=lambda: True,
                             get_many=lambda keys: {}, ornek_bildir=lambda *a, **k: None)
    writer = SimpleNamespace(writable=True, get_many=lambda keys: {},
                             upsert=lambda key, payload: True)
    from_calls = []

    def from_env(*, read_only=False):
        from_calls.append(read_only)
        return reader if read_only else writer

    monkeypatch.setattr(app.config, "supabase_delivery_writes_enabled", lambda: True)
    monkeypatch.setattr(app.SupabaseStore, "from_env", from_env)
    monkeypatch.setattr(mirror, "hydrate_all_open", lambda store: None)
    monkeypatch.setattr(mirror, "_MIRROR_WRITES_ENABLED", True)
    monkeypatch.setattr(pkg, "setup_logging", lambda: None)
    monkeypatch.setattr(pkg, "_evren_olcek_uyarisi", lambda: "")
    monkeypatch.setattr(pkg, "son_tarama_yukle", lambda store: None)
    monkeypatch.setattr(pkg, "_formation_history_baslangic_kontrolu", lambda: {})
    monkeypatch.setattr(pkg, "digest_tamponu_yukle", lambda store: None)
    monkeypatch.setattr(pkg, "_supabase_store_ref", None)
    monkeypatch.setattr(pkg, "_deque_manager_ref", None)
    monkeypatch.setattr(pkg, "_lifecycle_manager_ref", None)
    monkeypatch.setattr(pkg, "_startup_ready", False)

    class FakeDeque:
        def __init__(self, *, persistent_store):
            assert persistent_store is None

        def hydrate_from_supabase(self, stocks, rows):
            return None

    monkeypatch.setattr(app, "StockDequeManager", FakeDeque)
    monkeypatch.setattr(app, "PatternLifecycleManager", lambda **kwargs: object())

    def fake_notifier(**kwargs):
        assert kwargs["persistent_store"] is None
        assert isinstance(kwargs["remote_delivery_store"], DeliveryOnlyStore)
        raise StopStartup

    monkeypatch.setattr(app, "TelegramNotifier", fake_notifier)
    with pytest.raises(StopStartup):
        app.main_loop()
    assert from_calls == [True, False]
    assert not mirror._MIRROR_WRITES_ENABLED


# --- 5) Blueprint + CI parity -------------------------------------------------

def test_render_blueprint_shutdown_ve_teslim_yedegi_pini():
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "maxShutdownDelaySeconds: 120" in blueprint
    assert "healthCheckPath: /health" in blueprint
    assert "SUPABASE_DELIVERY_WRITES" in blueprint
    assert 'value: "0"' in blueprint


def test_ci_health_bildirim_alani_dogrulamasi_var():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert 'd.get("bildirim")' in workflow
    assert 'isinstance(b.get("nedenler"), list)' in workflow
    assert "healthCheckPath" not in workflow  # Blueprint alanı CI YAML'inde olmamalı


def test_env_orneginde_public_only_ve_teslim_yedegi_aciklamasi():
    ornek = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "SUPABASE_DELIVERY_WRITES=0" in ornek
    assert "YALNIZCA state:notification_delivery" in ornek
