"""Do not start new external work after SIGTERM arrives during startup."""

from datetime import time

import pytest

import bot.app as app
import main as M


def test_shutdown_during_startup_prevents_new_telegram_and_provider_work(monkeypatch):
    calls = []

    class Manager:
        def __init__(self, **_kwargs):
            pass

        def save_all(self):
            calls.append("save_all")

    class Notifier:
        enabled = public_enabled = True

        def __init__(self, **_kwargs):
            pass

        def check_connection(self):
            calls.append("connection started")
            M._shutdown_requested = True  # signal while getMe was in flight

        def check_public_connection(self):
            pytest.fail("new public API call after shutdown")

    def forbidden(*_args, **_kwargs):
        pytest.fail("new Telegram/provider work after shutdown")

    monkeypatch.setattr(M, "_shutdown_requested", False)
    monkeypatch.setattr(M, "ACTIVE_STOCKS", [])
    monkeypatch.setattr(M, "_telegram_listener_ref", None)
    for name in ("_startup_ready", "_supabase_store_ref", "_deque_manager_ref",
                 "_lifecycle_manager_ref", "_notifier_ref", "_telegram_update_processor_ref"):
        monkeypatch.setattr(M, name, getattr(M, name))
    monkeypatch.setattr(app.SupabaseStore, "from_env", lambda **_: None)
    monkeypatch.setattr(app, "StockDequeManager", Manager)
    monkeypatch.setattr(app, "PatternLifecycleManager", lambda **_: object())
    monkeypatch.setattr(app, "TelegramNotifier", Notifier)
    monkeypatch.setattr(app._state_persistence, "gonderim_durumu_yukle", lambda: {})
    for name in ("setup_logging", "son_tarama_yukle", "_formation_history_baslangic_kontrolu",
                 "digest_tamponu_yukle", "_gunluk_sayac_yukle", "son_tarama_kaydet",
                 "digest_tamponu_kaydet", "write_heartbeat", "_tekil_ornek_kontrolu"):
        monkeypatch.setattr(M, name, lambda *_args, **_kwargs: None)
    for name in ("_kacirilan_digest_ozeti", "_acil_kuyruk_acilista_isle",
                 "_telegram_komut_katmanini_kur", "fetch_1h_stocks_paced"):
        monkeypatch.setattr(M, name, forbidden)
    monkeypatch.setattr(M, "_render_runtime_status_init", lambda: {})
    monkeypatch.setattr(M, "_evren_olcek_uyarisi", lambda: "")
    monkeypatch.setattr(M, "_ozet_isaretlerini_yukle", lambda: ({}, {}))
    monkeypatch.setattr(M, "_parse_deferred_alert_digest_time", lambda: time(18, 45))
    monkeypatch.setattr(M, "_parse_post_close_analysis_time", lambda: time(20, 0))
    monkeypatch.setattr(M, "_effective_summary_hours", lambda: [])
    monkeypatch.setattr(M, "_gece_mum_yenileme_son_gun_oku", lambda: None)
    monkeypatch.setattr(M, "create_yahoo_pacer", lambda: object())
    app.main_loop()
    assert calls == ["connection started", "save_all"]
    assert M._startup_ready is False
    assert M._telegram_update_processor_ref is None
