"""Manuel analiz kuyruğu saatli işleri aç bırakmamalı (ağ yok)."""

import threading
from datetime import datetime
from types import SimpleNamespace

import pytest

import main as M
import bot.app as app
from config import ISTANBUL_TZ


@pytest.mark.parametrize("market_open", [False, True])
def test_main_loop_runs_scheduled_checks_between_queued_manual_jobs(monkeypatch, market_open):
    events = []

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            now = datetime(2026, 10, 30, 12, 0)
            return ISTANBUL_TZ.localize(now) if tz else now

    class Manager:
        def __init__(self, **_kwargs):
            pass

        def save_all(self):
            pass

    class Notifier:
        enabled = False
        public_enabled = False

        def __init__(self, **_kwargs):
            pass

        def check_connection(self):
            pass

        def teslimleri_dene(self):
            pass

    monkeypatch.setattr(M, "datetime", Clock)
    monkeypatch.setattr(M, "ACTIVE_STOCKS", [])
    monkeypatch.setattr(M, "_shutdown_requested", False)
    monkeypatch.setattr(M, "_scan_istegi", threading.Event())
    monkeypatch.setattr(M, "_scan_job_active", threading.Event())
    M._scan_istegi.set()
    monkeypatch.setattr(M, "_telegram_listener_ref", None)
    for name in ("_startup_ready", "_supabase_store_ref", "_deque_manager_ref",
                 "_lifecycle_manager_ref", "_notifier_ref", "_telegram_update_processor_ref"):
        monkeypatch.setattr(M, name, getattr(M, name))
    monkeypatch.setattr(app.SupabaseStore, "from_env", lambda **_kwargs: None)
    monkeypatch.setattr(app, "StockDequeManager", Manager)
    monkeypatch.setattr(app, "PatternLifecycleManager", lambda **_kwargs: object())
    monkeypatch.setattr(app, "TelegramNotifier", Notifier)
    monkeypatch.setattr(app, "islem_gunu_mu", lambda _now: False)
    monkeypatch.setattr(app, "time_until_next_open", lambda _now: 120)
    monkeypatch.setattr(app, "tarama_animi_mi", lambda _now, _last: True)
    monkeypatch.setattr(app, "son_kapanan_mum_ani", lambda now: now)
    monkeypatch.setattr(app.time, "sleep", lambda _seconds: None)

    def no_retry(_seconds):
        raise AssertionError("Ana döngü beklenmedik hata nedeniyle yeniden denedi")
    monkeypatch.setattr(app, "_shutdown_bekle", no_retry)
    monkeypatch.setattr(app._state_persistence, "gonderim_durumu_yukle", lambda: {})
    from state import formation_mirror
    monkeypatch.setattr(formation_mirror, "_MIRROR_WRITES_ENABLED", False)

    for name in (
        "setup_logging", "son_tarama_yukle", "_formation_history_baslangic_kontrolu",
        "digest_tamponu_yukle", "_kacirilan_digest_ozeti", "_acil_kuyruk_acilista_isle",
        "_telegram_komut_katmanini_kur", "_karne_uzak_kaydet", "_gunluk_sayac_yukle",
        "_ileri_test_gece", "_gece_denetimi", "son_tarama_kaydet",
        "digest_tamponu_kaydet", "write_heartbeat",
    ):
        monkeypatch.setattr(M, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(M, "_evren_olcek_uyarisi", lambda: "")
    monkeypatch.setattr(M, "_ozet_isaretlerini_yukle", lambda: ({}, {}))
    monkeypatch.setattr(M, "_ozet_slot_gonderilmeli", lambda *_args: False)
    monkeypatch.setattr(M, "create_yahoo_pacer", lambda: object())
    monkeypatch.setattr(M, "fetch_1h_stocks_paced", lambda *_args: ({}, {}, 0, 0))
    monkeypatch.setattr(M, "_karne_al", lambda: SimpleNamespace(buda=lambda: None,
                                                               boyut=lambda: 0, dosya="test"))
    monkeypatch.setattr(M, "_effective_summary_hours", lambda: [])
    monkeypatch.setattr(M, "tarama_penceresi_acik_mi", lambda _now: market_open)
    monkeypatch.setattr(M, "_bekle_veya_tarama", lambda _seconds: M._scan_istegi.is_set())
    monkeypatch.setattr(M, "_istek_tam_evrende_tamamlandi", lambda _result: False)
    monkeypatch.setattr(M, "scan_all_stocks", lambda *_args, **_kwargs: events.append("otomatik"))
    monkeypatch.setattr(M, "_tarama_saglik_kontrolu", lambda *_args: None)
    monkeypatch.setattr(M, "_tekil_ornek_kontrolu",
                        lambda *_args, **kw: events.append("zamanlayıcı") if not kw.get("force") else None)

    def run_manual(*_args):
        events.append("manuel")
        if events.count("manuel") == 2:
            M._scan_istegi.clear()
            M._shutdown_requested = True
        return True

    monkeypatch.setattr(M, "_calistir_istek_taramasi", run_manual)
    app.main_loop()
    expected = ["manuel", "zamanlayıcı"]
    if market_open:
        expected.append("otomatik")
    assert events == [*expected, "manuel"]
