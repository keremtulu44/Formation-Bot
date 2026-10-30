"""Komutlar tarama/sonuç gönderimi sırasında da çalışır; ağ kullanılmaz."""

import threading
import time

import pytest

import main as M
from live_state import LiveState
from telegram_commands import TelegramCommandListener

DM = "12345"
GROUP = "-100987654321"


class Session:
    def __init__(self):
        self.posts = []

    def post(self, _url, json=None, timeout=None):
        self.posts.append(dict(json or {}))
        return type("Response", (), {"status_code": 200})()


class Notifier:
    enabled = True
    chat_id = DM

    def __init__(self):
        self.dm = []
        self.groups = []

    def send_text(self, text):
        self.dm.append(text)
        return True, "ok"

    def send_to_chat(self, text, chat_id):
        self.groups.append((chat_id, text))
        return True


def message(update_id, text, chat_id=DM, *, age=0):
    group = str(chat_id).startswith("-")
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": int(time.time() - age),
            "chat": {"id": int(chat_id), "type": "supergroup" if group else "private"},
            "from": {"id": 55},
            "text": text,
        },
    }


def formation(stock, quality=80):
    return {
        "stock": stock, "timeframe": "1h", "pattern_name": "Üçgen",
        "quality": quality, "state": "SIKISMA_GUCLENIYOR", "break_dir": 1,
        "upper": 110, "lower": 100, "critical_price": 110,
    }


@pytest.fixture
def environment(monkeypatch):
    monkeypatch.setattr(M, "_scan_request_lock", threading.Lock())
    monkeypatch.setattr(M, "_scan_job_active", threading.Event())
    monkeypatch.setattr(M, "_scan_istegi", threading.Event())
    monkeypatch.setattr(M, "_scan_job_request", None)
    monkeypatch.setattr(M, "_scan_job_queue", [])
    monkeypatch.setattr(M, "_live_state", LiveState())
    monkeypatch.setattr(M, "ACTIVE_STOCKS", ["THYAO", "GARAN", "AKBNK"])
    monkeypatch.setattr(M, "last_run_stats", {})
    notifier = Notifier()
    monkeypatch.setattr(M, "_notifier_ref", notifier)
    session = Session()
    listener = TelegramCommandListener(
        token="111:AAA", allowed_chat_id=DM, handlers=M.TELEGRAM_KOMUTLARI,
        help_text=M.KOMUT_YARDIM, session=session,
        komutlari_yoksay=lambda: M._scan_job_active.is_set(),
        public_chat_ids=[GROUP],
        public_commands={"durum", "panel", "formasyonlar", "yardim", "tara"},
        admin_checker=lambda _chat, _user: True,
    )
    return listener, session, notifier


def start_scheduled_scan():
    state = M._live_state
    state.begin_scan(beklenen_hisse=3)
    state.record_formation(formation("THYAO"))
    state.finish_scan(son_tarama_hissesi=3, son_tarama_beklenen_hisse=3)
    state.begin_scan(beklenen_hisse=3)
    state.update_scan_progress(2, "GARAN")
    state.record_formation(formation("AKBNK", 99))  # yalnız yarım tamponda
    M._scan_job_active.set()
    return state


def complete_scheduled_scan(state):
    state.finish_scan(son_tarama_hissesi=3, son_tarama_beklenen_hisse=3)
    M._scan_job_active.clear()  # otomatik tarama finally bloğu


def install_fake_scanner(monkeypatch, calls):
    def scan(_manager, _lifecycle, _notifier, *, manuel, stocks, send_alerts):
        calls.append((list(stocks), manuel, send_alerts))
        state = M._live_state
        state.begin_scan(beklenen_hisse=len(stocks), scope=stocks,
                         replace_all=set(stocks) == set(M.ACTIVE_STOCKS))
        state.record_formation(formation(stocks[0], 87))
        state.finish_scan(son_tarama_hissesi=len(stocks),
                          son_tarama_beklenen_hisse=len(stocks))
        return {"status": "tamamlandi", "processed": len(stocks),
                "requested": len(stocks), "failed": 0}

    monkeypatch.setattr(M, "scan_all_stocks", scan)


def test_scheduled_scan_keeps_status_help_and_previous_snapshot_available(environment):
    listener, session, _ = environment
    state = start_scheduled_scan()

    status = listener.handle_update(message(1, "/durum@Bisthisseveri_bot", GROUP))
    assert "Formation-Bot durum" in status
    assert "Analiz sürüyor" in status and "2/3" in status and "GARAN" in status
    assert "çalıştırılmadı" not in status
    assert session.posts[-1]["chat_id"] == GROUP
    assert session.posts[-1]["reply_to_message_id"] == 1

    listing = listener.handle_update(message(2, "/formasyonlar", GROUP))
    assert "THYAO" in listing and "AKBNK" not in listing
    assert "son tamamlanan" in listing
    assert "AKBNK" not in {f["stock"] for f in state.formations()}
    assert "/durum" in listener.handle_update(message(3, "/yardim"))
    assert listener.durum()["mesgul_atlanan"] == 0


def test_empty_previous_result_is_not_reported_as_current_or_promised_automatically(environment):
    listener, _, _ = environment
    state = M._live_state
    state.begin_scan(beklenen_hisse=3)
    state.finish_scan(son_tarama_hissesi=3, son_tarama_beklenen_hisse=3)
    state.begin_scan(beklenen_hisse=3)
    M._scan_job_active.set()
    response = listener.handle_update(message(1, "/formasyonlar"))
    assert "son tamamlanan analize ait" in " ".join(response.split())
    assert "tamamlanınca güncel sonuç gönderilecek" not in response


def test_fifo_queues_during_automatic_scan_and_sends_to_requesting_chat(environment, monkeypatch):
    listener, session, notifier = environment
    state = start_scheduled_scan()
    group_response = listener.handle_update(message(1, "/panel THYAO", GROUP))
    dm_response = listener.handle_update(message(2, "/tara GARAN"))
    assert "sıraya alındı" in group_response and "sıra 1" in group_response
    assert "sıraya alındı" in dm_response and "sıra 2" in dm_response
    assert M._scan_job_request["hedef_sohbet"] == GROUP
    assert len(M._scan_job_queue) == 1

    # Aynı istek tekrarlandığında ikinci kez taranmaz.
    listener._son_komut_zamani.clear()
    repeated = listener.handle_update(message(3, "/panel  thyao", GROUP))
    assert "zaten" in repeated and len(M._scan_job_queue) == 1
    assert session.posts[-1]["chat_id"] == GROUP

    complete_scheduled_scan(state)
    calls = []
    install_fake_scanner(monkeypatch, calls)
    assert M._calistir_istek_taramasi(None, None, notifier)
    assert calls[0] == (["THYAO", "GARAN", "AKBNK"], True, False)
    assert notifier.groups and notifier.groups[0][0] == GROUP
    assert not notifier.dm
    assert M._scan_istegi.is_set() and M._scan_job_request["tip"] == "tara"
    assert M._calistir_istek_taramasi(None, None, notifier)
    assert calls[1] == (["GARAN"], True, False)
    assert len(notifier.dm) == 1
    assert M._scan_job_request is None and not M._scan_job_queue
    assert not M._scan_job_active.is_set() and not M._scan_istegi.is_set()


def test_queue_limit_duplicate_and_invalid_symbol_are_explicit(environment):
    start_scheduled_scan()
    assert "sıraya alındı" in M._komut_panel("THYAO")
    assert "sıraya alındı" in M._komut_tara("GARAN")
    assert "sıraya alındı" in M._komut_tara("AKBNK")
    assert "zaten" in M._komut_tara("garAn")
    assert "hisse bulunamadı" in M._komut_tara("YOKSAY")
    response = M._komut_tara("THYAO")
    assert "sırası dolu" in response and "eklenmedi" in response
    assert len(M._scan_job_queue) == 2
    assert M._scan_job_request["tip"] == "panel"


def test_expired_request_notifies_owner_and_next_request_still_runs(environment, monkeypatch):
    _, _, notifier = environment
    state = start_scheduled_scan()
    M._komut_tara("THYAO")
    M._komut_tara("GARAN")
    M._scan_job_request["istek_monotonic"] -= 30 * 60 + 1
    complete_scheduled_scan(state)
    calls = []
    install_fake_scanner(monkeypatch, calls)

    assert M._calistir_istek_taramasi(None, None, notifier)
    assert [c[0] for c in calls] == [["GARAN"]]
    assert "30 dakikayı aştı" in notifier.dm[0]
    assert "çalıştırılmadı" in notifier.dm[0]
    assert "Tarama tamamlandı" in notifier.dm[1]
    assert M._scan_job_request is None and not M._scan_job_active.is_set()


def test_all_expired_jobs_do_not_claim_a_new_scan_or_reuse_old_stats(environment, monkeypatch):
    _, _, notifier = environment
    state = start_scheduled_scan()
    M._komut_tara("THYAO")
    M._scan_job_request["istek_monotonic"] -= 30 * 60 + 1
    complete_scheduled_scan(state)
    monkeypatch.setattr(M, "last_run_stats", {"status": "tamamlandi", "requested": 3})
    calls = []
    install_fake_scanner(monkeypatch, calls)

    assert not M._calistir_istek_taramasi(None, None, notifier)
    assert not calls and "çalıştırılmadı" in notifier.dm[0]
    assert M._scan_job_request is None and not M._scan_istegi.is_set()
    # Ana döngü yalnız True dönüşünde last_run_stats ile mum işaretler.
    assert M.last_run_stats == {"status": "tamamlandi", "requested": 3}


def test_message_delivery_does_not_block_status_or_lose_new_scan_request(environment, monkeypatch):
    listener, _, _ = environment
    delivering = threading.Event()
    finish_delivery = threading.Event()
    scanned = []
    install_fake_scanner(monkeypatch, scanned)

    class BlockingNotifier(Notifier):
        def send_text(self, text):
            delivering.set()
            assert finish_delivery.wait(5)
            return super().send_text(text)

    notifier = BlockingNotifier()
    assert "başlatılıyor" in M._komut_tara("THYAO")
    worker = threading.Thread(target=M._calistir_istek_taramasi, args=(None, None, notifier))
    worker.start()
    try:
        assert delivering.wait(5)
        response = listener.handle_update(message(1, "/durum"))
        assert "Formation-Bot durum" in response and "sonuç hazırlanıyor" in response
        duplicate = listener.handle_update(message(2, "/tara THYAO"))
        assert "iletiliyor" in duplicate and "gönderilecek" not in duplicate
        assert not M._scan_job_queue
        assert "sıraya alındı" in listener.handle_update(message(3, "/panel GARAN"))
        assert M._scan_job_request["tip"] == "tara"
        assert len(M._scan_job_queue) == 1
    finally:
        finish_delivery.set()
        worker.join(5)
    assert not worker.is_alive()
    assert M._scan_job_request["tip"] == "panel" and M._scan_istegi.is_set()
    assert M._calistir_istek_taramasi(None, None, notifier)
    assert len(scanned) == 2
    assert M._scan_job_request is None and not M._scan_job_active.is_set()


def test_delivery_failure_never_leaks_public_result_to_dm_and_releases_queue(environment, monkeypatch):
    listener, _, notifier = environment
    state = start_scheduled_scan()
    listener.handle_update(message(1, "/panel", GROUP))
    listener.handle_update(message(2, "/tara THYAO"))
    complete_scheduled_scan(state)
    calls = []
    install_fake_scanner(monkeypatch, calls)
    notifier.send_to_chat = lambda _text, _chat: False

    assert M._calistir_istek_taramasi(None, None, notifier)
    assert notifier.dm == []
    assert M._scan_job_request["tip"] == "tara" and M._scan_istegi.is_set()
    assert M._calistir_istek_taramasi(None, None, notifier)
    assert len(notifier.dm) == 1


def test_scan_and_error_record_failures_release_queue_and_report_failure(environment, monkeypatch):
    _, _, notifier = environment
    state = start_scheduled_scan()
    M._komut_tara("THYAO")
    M._komut_tara("GARAN")
    complete_scheduled_scan(state)

    def failed_scan(*_args, **_kwargs):
        raise RuntimeError("tarama hatası")

    def failed_error_record(*_args, **_kwargs):
        raise OSError("hata kaydı hatası")

    monkeypatch.setattr(M, "scan_all_stocks", failed_scan)
    monkeypatch.setattr(M, "_analiz_hatasi_kaydi", failed_error_record)
    assert M._calistir_istek_taramasi(None, None, notifier)
    assert "Analiz tamamlanamadı" in notifier.dm[0]
    assert M.last_run_stats["status"] == "basarisiz"
    assert state.status()["son_tarama_durumu"] == "basarisiz"
    assert M._scan_job_request["arguman"] == "GARAN" and M._scan_istegi.is_set()

    calls = []
    install_fake_scanner(monkeypatch, calls)
    assert M._calistir_istek_taramasi(None, None, notifier)
    assert calls[0][0] == ["GARAN"]
    assert M._scan_job_request is None and not M._scan_job_active.is_set()


def test_dm_and_group_are_rate_limited_independently_while_busy(environment):
    listener, session, _ = environment
    start_scheduled_scan()
    assert listener.handle_update(message(1, "/durum", GROUP))
    assert listener.handle_update(message(2, "/durum"))
    assert [p["chat_id"] for p in session.posts] == [GROUP, DM]


def test_old_and_unauthorized_scan_commands_stay_blocked_while_busy(environment):
    listener, _, _ = environment
    start_scheduled_scan()
    assert "çalıştırılmaz" in listener.handle_update(message(1, "/tara THYAO", age=3600))
    assert listener.handle_update(message(2, "/tara THYAO", "999999")) is None
    assert M._scan_job_request is None and not M._scan_job_queue


def test_progress_is_thread_safe_and_not_persisted_as_a_running_scan():
    state = LiveState()
    state.begin_scan(beklenen_hisse=3)
    state.update_scan_progress(2, "garan")
    assert state.status()["aktif_tarama_sirasi"] == 2
    assert state.status()["aktif_tarama_sembolu"] == "GARAN"
    snapshot = state.snapshot()
    assert snapshot["status"]["tarama_suruyor"] is False
    assert "aktif_tarama_sirasi" not in snapshot["status"]
    restored = LiveState()
    restored.hydrate(snapshot)
    assert not restored.status()["tarama_suruyor"]
    assert restored.status()["aktif_tarama_sembolu"] is None
    state.fail_scan("test")
    assert state.status()["aktif_tarama_sirasi"] == 0
    assert state.status()["aktif_tarama_sembolu"] is None
