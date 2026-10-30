"""Gerçek dinleyici, arşiv ve çizim hattıyla kullanıcı yolculukları (ağsız)."""
from __future__ import annotations

import io
import json
import random
import threading
import time
from pathlib import Path

from PIL import Image
import pytest

import main as M
from research import replay_egitim as replay
from telegram_commands import TelegramCommandListener
import transport.telegram as telegram_transport

DM = "12345"
GROUP = "-1001234567890"


def _update(number, text, chat=DM):
    chat_id = str(chat)
    return {
        "update_id": number,
        "message": {
            "message_id": number,
            "date": int(time.time()),
            "chat": {"id": int(chat_id), "type": "supergroup" if chat_id.startswith("-") else "private"},
            "from": {"id": 55},
            "text": text,
        },
    }


class _Response:
    status_code = 200

    def json(self):
        return {"ok": True}


class _UserInbox:
    enabled = True
    token = "123456:FAKE_TOKEN_FOR_LOCAL_TEST"
    chat_id = DM

    def __init__(self):
        self.condition = threading.Condition()
        self.messages = []
        self.albums = []

    def send_to_chat(self, text, chat_id):
        with self.condition:
            self.messages.append((str(chat_id), str(text)))
            self.condition.notify_all()
        return True

    def post(self, url, json, timeout=15):
        assert url == f"https://api.telegram.org/bot{self.token}/sendMessage"
        assert len(json["text"]) <= 4000
        self.send_to_chat(json["text"], json["chat_id"])
        return _Response()

    def multipart(self, method, token, fields, files, timeout=20):
        assert method == "sendMediaGroup"
        assert token == self.token and str(fields["chat_id"]) == DM
        media = json.loads(fields["media"])
        assert len(media) == 4 and len(files) == 4
        images = []
        for item in media:
            key = item["media"].removeprefix("attach://")
            name, payload, content_type = files[key]
            assert content_type == "image/png" and payload.startswith(b"\x89PNG\r\n\x1a\n")
            with Image.open(io.BytesIO(payload)) as image:
                image.verify()
            with Image.open(io.BytesIO(payload)) as image:
                assert image.width >= 700 and image.height >= 700
                size = image.size
            images.append((name, item["caption"], size, payload))
        with self.condition:
            self.albums.append(images)
            self.condition.notify_all()
        return _Response()

    def wait_for(self, predicate, timeout=75):
        with self.condition:
            assert self.condition.wait_for(predicate, timeout), (
                f"Telegram beklenirken zaman aşımı: {len(self.messages)} mesaj, "
                f"{len(self.albums)} albüm")


def test_test_komutu_butun_adimlar_ve_dort_tf_gercek_cizim(monkeypatch, tmp_path):
    """Dört ayrı kullanıcı oyunu: giriş → albüm → TF → tahmin → albüm + sonuç.

    Yalnız Telegram'ın HTTP sınırı sahtedir; dinleyici, işçi, arşiv okuma,
    analiz, normal grafik renderer'ı ve multipart kurulum gerçek kodlardır.
    """
    import requests
    from notifier import TelegramNotifier

    inbox = _UserInbox()
    notifier = TelegramNotifier()
    notifier.enabled, notifier.token, notifier.chat_id = True, inbox.token, DM
    monkeypatch.setattr(requests, "post", inbox.post)
    session = replay.Session()
    monkeypatch.setattr(M, "_notifier_ref", notifier)
    monkeypatch.setattr(replay, "session", session)
    monkeypatch.setattr(telegram_transport, "_multipart_cagri", inbox.multipart)
    real_select = replay.soru_sec
    seeds = iter([7, 11, 17, 23])
    monkeypatch.setattr(replay, "soru_sec", lambda symbol: real_select(symbol, rng=random.Random(next(seeds))))
    responses = []
    listener = TelegramCommandListener(
        token=inbox.token, allowed_chat_id=DM, handlers=M.TELEGRAM_KOMUTLARI,
        help_text=M.KOMUT_YARDIM,
        response_sender=lambda uid, text: responses.append((uid, text)) or True,
        public_chat_ids=[GROUP], public_commands=["test"], admin_checker=lambda *_: True,
    )
    horizons = replay.HORIZONS
    number = 0

    def send(text, chat=DM):
        nonlocal number
        number += 1
        return listener.handle_update(_update(number, text, chat))

    # Soru yalnız yetkili DM'de açılabilir; PUBLIC_COMMAND_EXTRA bunu değiştirmez.
    assert send("/test ASTOR", GROUP) is None
    for index, (tf, horizon, guess) in enumerate([
        ("1s", 8, "yukarı"), ("2s", 10, "aşağı"),
        ("4s", 20, "yatay"), ("1g", 20, "yukarı"),
    ]):
        # Geçerli soru seçimi bütün 20 mumluk ufku kontrol eder; seçimi daha
        # sonra sabitlemek üç farklı sonuç ufkunu deterministik sınar.
        monkeypatch.setattr(replay, "HORIZONS", horizons)
        reply = send("/test ASTOR")
        assert reply and "hazırlanıyor" in reply
        inbox.wait_for(lambda: len(inbox.albums) == index * 2 + 1
                       and len(inbox.messages) >= index * 2 + 1)
        question = session.current
        assert question is not None and question.code in inbox.messages[-1][1]
        assert "aynı ana kadar" in " ".join(inbox.messages[-1][1].split())
        assert [p[1] for p in inbox.albums[-1]] == [
            f"ASTOR · {name} · Soru" for name in ("1s", "2s", "4s", "1g")]

        # Kod yanlışsa ya da mesaj yabancı sohbetten gelirse oturum ilerlemez.
        assert "kod" in send(f"{tf} BADBAD").lower()
        assert send(f"{tf} {question.code}", "99999") is None
        assert question.tf is None
        monkeypatch.setattr(replay, "HORIZONS", (horizon,))
        selected = send(f"{tf} {question.code}")
        assert selected and f"{horizon} kapanmış mum sonra" in selected
        assert question.horizon == horizon
        result = replay.sonuc(question, guess)
        reply = send(f"{guess} {question.code}")
        assert reply and "Sonuç hazırlanıyor" in reply
        inbox.wait_for(lambda: len(inbox.albums) == index * 2 + 2
                       and len(inbox.messages) >= index * 2 + 2)
        result_message = " ".join(inbox.messages[-1][1].split())
        assert f"Tahmin: {guess} · Sonuç: {result['direction']}" in result_message
        assert f"{horizon} kapanmış mum" in result_message
        assert "Kapanış:" in result_message and "ATR:" in result_message
        assert "gönderilebildi" not in result_message
        assert len(inbox.albums[-1]) == 4
        assert all("Sonuç" in item[1] for item in inbox.albums[-1])
        assert session.current is None
        # Uzun ufukların önce/sonra örnekleri yalnız pytest geçici dizininde tutulur.
        if index in {2, 3}:
            for stage, album in (("soru", inbox.albums[-2]), ("sonuc", inbox.albums[-1])):
                for name, _caption, _size, data in album:
                    Path(tmp_path, f"{stage}-{tf}-{name}").write_bytes(data)

    assert all(chat == DM for chat, _ in inbox.messages)
    assert len(inbox.albums) == 8 and len(inbox.messages) == 8
    assert listener._sayac["hata"] == 0


class _DiagnosticResponse(_Response):
    def __init__(self, method):
        self.method = method

    def json(self):
        result = {"url": "https://example.test/webhook", "pending_update_count": 0} if self.method == "getWebhookInfo" else {"id": 55, "username": "TestBot", "status": "administrator"}
        return {"ok": True, "result": result}


class _JourneyInbox(_UserInbox):
    """Gerçek notifier tarafından paketlenen tek fotoğrafı/albümü yakala."""

    def __init__(self):
        super().__init__()
        self.media = []
        self.completed_graphics = 0

    def multipart(self, method, token, fields, files, timeout=20):
        assert token == self.token
        if method == "sendMediaGroup":
            items = json.loads(fields["media"])
            refs = [(item["media"].removeprefix("attach://"), item.get("caption", ""))
                    for item in items]
        else:
            assert method == "sendPhoto"
            refs = [("photo", fields.get("caption", ""))]
        images = []
        for key, caption in refs:
            name, payload, content_type = files[key]
            assert content_type == "image/png" and payload.startswith(b"\x89PNG\r\n\x1a\n")
            with Image.open(io.BytesIO(payload)) as image:
                image.verify()
            with Image.open(io.BytesIO(payload)) as image:
                assert image.width >= 700 and image.height >= 700
                size = image.size
            images.append((name, caption, size, payload))
        with self.condition:
            self.media.append((method, str(fields["chat_id"]), images))
            self.condition.notify_all()
        return _Response()


@pytest.fixture
def archive_journey(monkeypatch, tmp_path):
    """Canlı DB'ye dokunmadan üç hisse arşivini gerçek cache ve motorla tara.

    Tarihsel OHLCV erişimini denemek için sağlayıcılar kapalı ve tazelik kapısı
    bilerek kaldırılmıştır. Ortaya çıkan veriler hiçbir şekilde canlı sayılmaz.
    """
    import copy

    import config
    import karne
    import requests
    from data import StockDequeManager
    from domain_engines import runner as domain_runner
    from live_state import LiveState
    from notifier import TelegramNotifier
    from patterns import PatternLifecycleManager
    from research.arsiv import tf_frame
    from telegram_alert_flow import DeferredAlertBuffer

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", str(runtime))
    monkeypatch.setattr(karne, "DATA_DIR", str(runtime))
    inbox = _JourneyInbox()
    notifier = TelegramNotifier()
    notifier.enabled, notifier.token, notifier.chat_id = True, inbox.token, DM
    monkeypatch.setattr(requests, "post", inbox.post)
    monkeypatch.setattr(notifier, "_public_pace", lambda: None)
    monkeypatch.setattr(notifier, "_grafik_pace", lambda: None)
    monkeypatch.setattr(telegram_transport, "_multipart_cagri", inbox.multipart)
    for name in ("_latest_by_series", "_incremental_states_by_series", "_series_state_locks"):
        monkeypatch.setattr(domain_runner, name, {})

    manager = StockDequeManager(data_dir=str(tmp_path / "cache"))
    stocks = ["ASTOR", "AKBNK", "THYAO"]
    for symbol in stocks:
        assert manager.append_dataframe(symbol, tf_frame(symbol, "1h").tail(360))
        assert manager.append_gunluk_dataframe(symbol, tf_frame(symbol, "1d").tail(400))
        assert not manager.sureklilik_sorunlari.get(symbol)
    monkeypatch.setattr(manager, "gunluk_veri_eksik_mi", lambda *_: False)
    lifecycle = PatternLifecycleManager()
    replacements = {
        "_live_state": LiveState(), "ACTIVE_STOCKS": stocks, "_shutdown_requested": False,
        "_scan_request_lock": threading.Lock(), "_scan_job_active": threading.Event(),
        "_scan_istegi": threading.Event(), "_scan_job_request": None, "_scan_job_queue": [],
        "_grafik_is_kilidi": threading.Lock(), "_grafik_aktif_is": {},
        "_cache_verisi_kullanilabilir": lambda *_: True,
        "tarama_penceresi_acik_mi": lambda *_: False,
        "fetch_1h_stocks_paced": lambda *a, **kw: ({}, {}, 0, 0),
        "reset_daily_if_needed": lambda: None, "write_heartbeat": lambda **kw: None,
        "son_tarama_kaydet": lambda: None, "_gunluk_sayac_kaydet": lambda: None,
        "_notifier_ref": notifier, "_deque_manager_ref": manager,
        "_lifecycle_manager_ref": lifecycle, "_supabase_store_ref": None,
        "_karne_defteri": None, "last_run_stats": {}, "daily_stats": copy.deepcopy(M.daily_stats),
        "_deferred_alert_buffer": DeferredAlertBuffer(), "_daily_pattern_keys": set(),
        "_daily_basarisiz_keys": set(), "_daily_unannounced_invalidation_keys": set(),
        "_daily_lifecycle_event_keys": set(),
        "_telegram_token_al": lambda: inbox.token,
        "_public_komut_sohbetleri": lambda: [GROUP],
        "_telegram_api_cagri": lambda method, _token, *_a, **_kw: _DiagnosticResponse(method),
    }
    for name, value in replacements.items():
        monkeypatch.setattr(M, name, value)
    actual_worker = M._grafik_isi_calistir

    def monitored_worker(*args):
        try:
            return actual_worker(*args)
        finally:
            with inbox.condition:
                inbox.completed_graphics += 1
                inbox.condition.notify_all()

    monkeypatch.setattr(M, "_grafik_isi_calistir", monitored_worker)
    import bot.commands as commands
    monkeypatch.setattr(commands, "_public_hedef_tipi_getir", lambda _ids: [{
        "sohbet": GROUP, "okundu": True, "tur": "supergroup", "komut": True}])

    acknowledgements = []
    listener = TelegramCommandListener(
        token=inbox.token, allowed_chat_id=DM, handlers=M.TELEGRAM_KOMUTLARI,
        help_text=M.KOMUT_YARDIM,
        response_sender=lambda uid, text, *route: acknowledgements.append((uid, text, *route)) or True,
        public_chat_ids=[GROUP], public_commands=list(M.TELEGRAM_KOMUTLARI),
        admin_checker=lambda *_: True,
    )
    return listener, inbox, notifier, manager, lifecycle, runtime


def test_tum_komut_adlari_ve_tara_panel_grafik_kullanici_akislari(archive_journey, tmp_path):
    """Tüm kayıtlı adlar, gerçek listener ve arşivle en az bir kez tamamlanır."""
    import oneri

    listener, inbox, notifier, manager, lifecycle, runtime = archive_journey
    transcript = []
    number = 0

    def send(text, chat=DM):
        nonlocal number
        number += 1
        # Her satır ayrı kullanıcı etkileşimi: bir saniyelik anti-spam penceresi
        # beklenmiş kabul edilir; oran sınırının kendisi ayrı testlerde sınanır.
        listener._son_komut_zamani.clear()
        reply = listener.handle_update(_update(number, text, chat))
        transcript.append(f"> {text} [{chat}]\n{reply}")
        return reply

    # Önce gerçek verilerle dar kapsamlı tarama; böylece kalan rapor komutları
    # yalnız boş durumları değil, gerçek oluşmuş kayıtları da görür.
    assert "1 sembol" in send("/tara ASTOR")
    assert M._calistir_istek_taramasi(manager, lifecycle, notifier)
    assert M.last_run_stats["status"] == "tamamlandi"
    assert M.last_run_stats["processed"] == 1
    assert "1/1" in inbox.messages[-1][1] and "En yeni 1s cache mum etiketi" in " ".join(inbox.messages[-1][1].split())
    assert M._live_state.formations()
    transcript.append(f"[arka plan]\n{inbox.messages[-1][1]}")
    # Yardımda vaat edilen iki tokenlı filtre ve grafikteki 4s takma adı.
    for filter_text in ("ASTOR 4h", "4s ASTOR"):
        filtered = " ".join(send(f"/formasyonlar {filter_text}").split())
        assert "ASTOR · 4h" in filtered and "ASTOR · 2h" not in filtered
    empty = " ".join(send("/sikisanlar").split())
    assert "kısmi kapsam" in empty and "En yeni 1s cache mum etiketi" in empty
    retest = " ".join(send("/retest").split())
    assert "retest bekliyor" in retest and "RETEST_BEKLENIYOR" not in retest
    assert "En yeni 1s cache mum etiketi" in retest and "etiket yaşı" in retest
    status = M._live_state.status()
    assert status["son_is_hisse_basarili"] == status["son_is_hisse_istek"] == 1

    tested = {"tara", "test"}  # /test ayrı testte dört tam oturumla işlendi.
    scan_names = {"panel", "p", "genel", "tablo"}
    chart_names = {"grafik", "g"}
    affirmative = {"evet", "onay", "kabul"}
    negative = {"hayir", "hayır", "red"}
    for name in M.TELEGRAM_KOMUTLARI:
        if name in tested:
            continue
        if name in scan_names:
            before = len(inbox.messages)
            assert send(f"/{name}")
            assert M._calistir_istek_taramasi(manager, lifecycle, notifier)
            assert M.last_run_stats["status"] == "tamamlandi"
            assert M.last_run_stats["processed"] == len(M.ACTIVE_STOCKS)
            assert len(inbox.messages) == before + 1
            assert "3/3" in inbox.messages[-1][1]
            transcript.append(f"[arka plan]\n{inbox.messages[-1][1]}")
        elif name in chart_names:
            before, before_media, before_workers = len(inbox.messages), len(inbox.media), inbox.completed_graphics
            assert "hazırlanıyor" in send(f"/{name} ASTOR 4s")
            inbox.wait_for(lambda: len(inbox.messages) > before and len(inbox.media) > before_media
                           and inbox.completed_graphics > before_workers)
            method, chat, media = inbox.media[-1]
            assert method == "sendPhoto" and chat == DM and len(media) == 1
            assert "ASTOR · 4s" in media[0][1] and "mum" in media[0][1]
            assert "grafik hazır" in inbox.messages[-1][1]
            transcript.append(f"[arka plan]\n{inbox.messages[-1][1]}")
        elif name in affirmative | negative:
            assert oneri.kaydet({"gun": "2026-10-30", "ozet": "yerel test", "durum": "bekliyor"})
            reply = send(f"/{name}")
            expected = "onaylandi" if name in affirmative else "reddedildi"
            assert oneri.yukle()["oneri"]["durum"] == expected
            assert "onaylandı" in reply if name in affirmative else "reddedildi" in reply
        else:
            reply = send(f"/{name}")
            assert reply and len(reply) <= 4096, (name, reply)
            assert "Komut çalıştırılamadı" not in reply
            assert "Komut hatası" not in reply
        tested.add(name)

    assert tested == set(M.TELEGRAM_KOMUTLARI)
    assert listener._sayac["hata"] == 0
    assert str(runtime) in oneri.dosya_yolu() and (runtime / oneri.DOSYA).exists()
    (tmp_path / "transcript.txt").write_text("\n\n".join(transcript), encoding="utf-8")


def test_grafik_tek_tf_uretimi_basarisizsa_3_4_kismi_ve_neden_gorunur(archive_journey, monkeypatch):
    """Gerçek dört TF isteğinde bir renderer hatası normal başarı gibi görünmez."""
    import grafik_uret as graphics

    listener, inbox, _notifier, _manager, _lifecycle, _runtime = archive_journey
    original = graphics.kare_uret

    def one_failure(symbol, tf, **kwargs):
        if tf == "2h":
            raise graphics.VeriYok("deneme: bu zaman dilimi için veri yok")
        return original(symbol, tf, **kwargs)

    monkeypatch.setattr(graphics, "kare_uret", one_failure)
    reply = listener.handle_update(_update(1, "/grafik ASTOR"))
    assert reply and "hazırlanıyor" in reply
    inbox.wait_for(lambda: len(inbox.media) == 1 and len(inbox.messages) == 1
                   and inbox.completed_graphics == 1)
    method, chat, images = inbox.media[0]
    assert method == "sendMediaGroup" and chat == DM and len(images) == 3
    assert "2s" in images[0][1] and "veri yok" in images[0][1]
    result = " ".join(inbox.messages[0][1].split())
    assert "kısmen tamamlandı" in result and "3/4 kare" in result
    assert "2s" in result and "veri yok" in result
    assert "grafik hazır" not in result


def test_grup_tara_panel_ve_grafik_gercek_sonuclari_gruba_gider(archive_journey):
    """Gerçek yönetici talebi: sonradan gelen metin ve PNG yalnız gruba gider."""
    listener, inbox, notifier, manager, lifecycle, _runtime = archive_journey
    reply = listener.handle_update(_update(1, "/tara ASTOR", GROUP))
    assert reply and "bu sohbete" in " ".join(reply.split())
    assert M._calistir_istek_taramasi(manager, lifecycle, notifier)
    assert inbox.messages[-1][0] == GROUP and "1/1" in inbox.messages[-1][1]

    reply = listener.handle_update(_update(2, "/panel ASTOR 4s", GROUP))
    assert reply and "başlatılıyor" in reply
    assert M._calistir_istek_taramasi(manager, lifecycle, notifier)
    panel = " ".join(inbox.messages[-1][1].split())
    assert inbox.messages[-1][0] == GROUP and "3/3" in panel
    assert "ASTOR" in panel and "4h" in panel

    before = len(inbox.messages)
    reply = listener.handle_update(_update(3, "/grafik ASTOR 4s", GROUP))
    assert reply and "bu gruba" in " ".join(reply.split())
    inbox.wait_for(lambda: len(inbox.messages) > before and len(inbox.media) == 1
                   and inbox.completed_graphics == 1)
    method, target, images = inbox.media[0]
    assert method == "sendPhoto" and target == GROUP and len(images) == 1
    assert inbox.messages[-1][0] == GROUP and "grafik hazır" in inbox.messages[-1][1]
    assert all(chat == GROUP for chat, _ in inbox.messages)
