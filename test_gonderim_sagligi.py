"""Batch 4: saat dilimi tutarlılığı, uzun mesaj koruması + retry ve gönderim sağlığı.

Ağa çıkmaz: `requests.post` monkeypatch ile sahtelenir.
"""

import json
from datetime import datetime, timedelta

import pytest

import main as main_mod
import notifier as notifier_mod
from config import ISTANBUL_TZ
from notifier import TelegramNotifier


class _Yanit:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


def _notifier(monkeypatch, cevaplar, token="123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"):
    """Aktif notifier + sahte requests.post. `cevaplar` sırayla döner."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    n = TelegramNotifier()
    n.retry_bekleme_sn = 0.0  # testler beklemesin
    assert n.enabled
    cagrilar = []

    def sahte_post(url, json=None, timeout=None):
        cagrilar.append(json)
        if isinstance(cevaplar, list):
            return cevaplar[min(len(cagrilar) - 1, len(cevaplar) - 1)]
        return cevaplar

    monkeypatch.setattr("requests.post", sahte_post)
    return n, cagrilar


# --- A5: uzun mesaj koruması + retry --------------------------------------

def test_uzun_mesaj_4096_sinirina_kirpilir(monkeypatch):
    n, cagrilar = _notifier(monkeypatch, _Yanit(200, "ok"))
    n.send_text("a" * 6000)
    gonderilen = cagrilar[0]["text"]
    assert len(gonderilen) <= 4000, "Telegram sınırına karşı kirp() uygulanmalı"
    assert "kesildi" in gonderilen


def test_gecici_hata_bir_kez_tekrar_denenir(monkeypatch):
    n, cagrilar = _notifier(monkeypatch, [_Yanit(500, "server error"), _Yanit(200, "ok")])
    ok, detay = n.send_text("merhaba")
    assert ok is True and len(cagrilar) == 2
    assert n.son_basarili_gonderim is not None


def test_429_tekrar_denenir_403_denenmez(monkeypatch):
    n, cagrilar = _notifier(monkeypatch, [_Yanit(429, "too many"), _Yanit(200, "ok")])
    assert n.send_text("a")[0] is True and len(cagrilar) == 2

    n2, cagrilar2 = _notifier(monkeypatch, _Yanit(403, "bot was blocked by the user"))
    ok, detay = n2.send_text("a")
    assert ok is False and len(cagrilar2) == 1, "4xx kalıcı hatada tekrar denenmemeli"
    assert "403" in detay


def test_surekli_hata_saglik_alanlarina_yazilir(monkeypatch):
    n, cagrilar = _notifier(monkeypatch, _Yanit(500, "server error"))
    ok, detay = n.send_text("a")
    assert ok is False
    assert len(cagrilar) == 2, "geçici hatada iki deneme yapılmalı"
    # 'hatalar' başarısız GÖNDERİM işlemini sayar (deneme sayısını değil).
    assert n.gonderim_hatasi == 1
    assert n.son_gonderme_hatasi and "500" in n.son_gonderme_hatasi


# --- A6: heartbeat / gönderim durumu -------------------------------------

def test_gonderim_durumu_alanlari():
    n = TelegramNotifier()
    d = n.gonderim_durumu()
    for alan in ("enabled", "gonderilen_alarm", "hatalar", "kanal_hatasi",
                 "engeller", "son_basarili_gonderim", "son_gonderme_hatasi",
                 "gunluk_kap", "saatlik_kap"):
        assert alan in d, alan


def test_heartbeat_gonderim_sagligini_ve_huniyi_yazar(monkeypatch, tmp_path):
    monkeypatch.setattr(main_mod, "_deque_manager_ref", None)
    monkeypatch.setattr(main_mod, "_supabase_store_ref", None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    n = TelegramNotifier()
    main_mod.daily_stats.update(alerts_attempted=5, alerts_failed=1, alerts_sent=4)
    main_mod.write_heartbeat(data_dir=str(tmp_path), notifier=n)

    veri = json.loads((tmp_path / "heartbeat.json").read_text(encoding="utf-8"))
    assert veri["notifier_enabled"] is False
    assert veri["telegram_gonderim"]["enabled"] is False
    assert veri["alerts_attempted"] == 5 and veri["alerts_failed"] == 1
    assert veri["aday_hunisi"]["push"] == 4


def test_durum_pasif_telegrami_soyler(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    eski = main_mod._notifier_ref
    try:
        main_mod._notifier_ref = TelegramNotifier()
        metin = main_mod._komut_durum("")
        assert "Telegram PASİF" in metin
    finally:
        main_mod._notifier_ref = eski


# --- A4: saat dilimi ------------------------------------------------------

def test_gunluk_kap_tarihi_istanbul_saatine_gore():
    n = TelegramNotifier()
    assert n._gunluk_tarih == datetime.now(ISTANBUL_TZ).date()
    # UTC gece yarısı ile İstanbul gece yarısı arasında (00:00-03:00) gün farkı oluşmaz.
    kaynak = open(notifier_mod.__file__, encoding="utf-8").read()
    assert "datetime.now().date()" not in kaynak, "naive now() gün sınırı kalmamalı"


def test_naive_kayitlar_istanbula_normalize_edilir(tmp_path, monkeypatch):
    """Eski (naive) kayıtlar yüklenirken patlamamalı ve gün sınırı kaymamalı."""
    monkeypatch.setattr(notifier_mod, "DATA_DIR", str(tmp_path / "bot_data"))
    # "Şimdi"nin naive kopyası: eski sürüm bu biçimde (UTC/sunucu saati) yazıyordu.
    naive = datetime.now(ISTANBUL_TZ).replace(microsecond=0, tzinfo=None)
    store = {
        "state:telegram_cooldowns": {"THYAO_X_1h_KIRILIM_TEYITLI": naive.isoformat()},
        "state:telegram_caps": {"gunluk_sayac": 1, "gunluk_tarih": naive.date().isoformat(),
                                "saatlik": [naive.isoformat()]},
    }
    n = TelegramNotifier(initial_store_data=store)
    yuklenen = n.last_sent["THYAO_X_1h_KIRILIM_TEYITLI"]
    assert yuklenen.tzinfo is not None
    assert yuklenen.utcoffset() == timedelta(hours=3)
    # can_send naive kayıtla da patlamaz (kıyaslama _istanbul'dan geçer)
    n.max_gunluk, n.max_saatlik = 100, 100
    assert n.can_send("THYAO", "X", "1h", "KIRILIM_TEYITLI") is False


def test_naive_last_sent_karsilastirmasi_patlamaz():
    n = TelegramNotifier()
    n.max_gunluk, n.max_saatlik = 100, 100
    n.last_sent[n._cooldown_key("GARAN", "X", "1h", "KIRILIM_TEYITLI")] = datetime.now()
    assert n.can_send("GARAN", "X", "1h", "KIRILIM_TEYITLI") is False


def test_saatlik_kap_temizligi_istanbul_zamaniyla():
    n = TelegramNotifier()
    n.max_saatlik = 1
    n._saatlik_zamanlar = [datetime.now(ISTANBUL_TZ) - timedelta(hours=2),
                           datetime.now(ISTANBUL_TZ) - timedelta(minutes=5)]
    n._saatligi_temizle()
    assert len(n._saatlik_zamanlar) == 1, "2 saat önceki kayıt temizlenmeli (1 saatlik pencere)"
