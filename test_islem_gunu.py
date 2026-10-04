"""İşlem günü kapısı: hafta sonu/resmî tatilde kanal ve gece analizi susar.

NEDEN: Özet saatleri (09:55/18:45) ve gece analizi (20:00) takvimden bağımsız
geldiği için, kapı olmadan cumartesi günü kanala "Bugün öne çıkan formasyon
olmadı." mesajı gidiyor ve 20:00'de veri değişmediği hâlde tam evren taraması
çalışıyordu. Testler ağa çıkmaz.
"""

from datetime import datetime, timedelta

import pytest

from config import ISTANBUL_TZ
from data import islem_gunu_mu


def test_hafta_sonu_islem_gunu_degil():
    # 2026-09-26 Cumartesi, 2026-09-27 Pazar
    assert islem_gunu_mu(datetime(2026, 9, 26, 12, 0, tzinfo=ISTANBUL_TZ)) is False
    assert islem_gunu_mu(datetime(2026, 9, 27, 12, 0, tzinfo=ISTANBUL_TZ)) is False


def test_resmi_tatil_islem_gunu_degil():
    assert islem_gunu_mu(datetime(2026, 10, 29, 12, 0, tzinfo=ISTANBUL_TZ)) is False  # Cumhuriyet Bayramı
    assert islem_gunu_mu(datetime(2027, 1, 1, 12, 0, tzinfo=ISTANBUL_TZ)) is False     # Yılbaşı


def test_normal_hafta_ici_islem_gunu():
    assert islem_gunu_mu(datetime(2026, 9, 25, 3, 0, tzinfo=ISTANBUL_TZ)) is True
    assert islem_gunu_mu(datetime(2026, 10, 2, 22, 0, tzinfo=ISTANBUL_TZ)) is True


def test_naive_datetime_istanbul_sayilir():
    assert islem_gunu_mu(datetime(2026, 9, 25, 12, 0)) is True
    assert islem_gunu_mu(datetime(2026, 9, 26, 12, 0)) is False


# --- özet metinleri kapalı günde boş mesaj üretmemeli ------------------------

def _notifier(monkeypatch):
    import notifier as notifier_mod
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "@bisthisseveri")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    return notifier_mod.TelegramNotifier()


def test_bos_ozet_kanala_gonderilmez(monkeypatch):
    n = _notifier(monkeypatch)
    assert n.send_to_public("") is False
    assert n.send_to_public("   \n ") is False


def test_kapali_gun_ozetleri_bilgi_verir(monkeypatch):
    """Kapanış özeti kapalı günde çağrılsa bile 'öne çıkan olmadı' der (boş değil)."""
    n = _notifier(monkeypatch)
    bos = {"stocks_scanned": 0, "patterns_found": 0, "alerts_sent": 0,
           "tarama_sayisi": 0, "basarisiz_kirilim": 0}
    kapanis = n.format_public_summary([], bos, kapanis=True, tarama_turu=0)
    sabah = n.format_public_summary([], bos, kapanis=False, tarama_turu=0)
    assert kapanis.strip() and sabah.strip()
    assert "öne çıkan formasyon olmadı" in kapanis


# --- ana döngü kapısı: kapalı günde döngü bloğu özet GÖNDERMEZ --------------

def test_ana_dongu_ozet_bloklari_islem_gunune_bagli():
    """main.py'de özet ve gece analizi bloklarının ikisi de kapıya bağlı olmalı."""
    import io
    kaynak = io.open("main.py", encoding="utf-8").read()
    assert kaynak.count("islem_gunu_mu(now)") >= 2, "özet ve gün sonu kapıları kurulmalı"
    assert "İŞLEM GÜNÜ KAPISI" in kaynak
    # Kapı, özet döngüsünden ÖNCE ve aynı try içinde olmalı.
    kapi = kaynak.index("İŞLEM GÜNÜ KAPISI")
    dongu = kaynak.index("for sh in summary_hours:")
    assert kapi < dongu


def test_kapanis_ozeti_pazartesi_gonderilir(monkeypatch):
    """Kapı yalnızca hafta sonu/tatili keser; pazartesi normal akış."""
    hedef = datetime(2026, 9, 28, 18, 45, tzinfo=ISTANBUL_TZ)  # Pazartesi
    assert islem_gunu_mu(hedef) is True
    assert islem_gunu_mu(hedef + timedelta(days=5)) is False   # Cumartesi
