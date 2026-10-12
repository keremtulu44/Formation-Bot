"""Batch 5: kalıcı digest tamponu (B3) + engellenen acil olay kuyruğu (B4).

Ağ yok; `requests.post` sahtelenir. Supabase bağlantısı yok (store=None),
disk yolu tmp_path'e taşınır.
"""

import json
from datetime import datetime, timedelta

import pytest

import main as main_mod
import notifier as notifier_mod
from config import ISTANBUL_TZ
from notifier import TelegramNotifier
from telegram_alert_flow import DeferredAlertBuffer

TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"


@pytest.fixture(autouse=True)
def _veri_dizini_izole(tmp_path, monkeypatch):
    """Repo içindeki bot_data/ dosyaları testleri kirletmesin (test sırası bağımsız)."""
    monkeypatch.setattr(notifier_mod, "DATA_DIR", str(tmp_path / "bot_data"))
    # `digest_tamponu_kaydet()` argümansız çağrıldığında (telafi yolu) config.DATA_DIR
    # kullanılır; testler repo içindeki bot_data'yı kirletmesin.
    import config as config_mod
    monkeypatch.setattr(config_mod, "DATA_DIR", str(tmp_path / "bot_data"))
    yield


class _Yanit:
    def __init__(self, status_code, text="ok"):
        self.status_code = status_code
        self.text = text


def _aktif(monkeypatch, cevaplar=None):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    n = TelegramNotifier()
    n.retry_bekleme_sn = 0.0
    gonderilenler = []

    def sahte_post(url, json=None, timeout=None):
        gonderilenler.append(json)
        return (_Yanit(200) if cevaplar is None
                else (cevaplar[min(len(gonderilenler) - 1, len(cevaplar) - 1)]
                      if isinstance(cevaplar, list) else cevaplar))

    monkeypatch.setattr("requests.post", sahte_post)
    return n, gonderilenler


def _veri(state="KIRILIM_TEYITLI", stock="THYAO"):
    """Acil (ALERT_STATES) bir olay. Engellemek için GÜNLÜK kap kullanılır:
    acil state'ler kritik sayıldığından saatlik kapıyı bilerek geçer, günlük kap
    ise hiçbir state'i geçirmez."""
    return {"stock_name": stock, "pattern_name": "Yükselen Üçgen", "timeframe": "1h",
            "state": state, "confidence_score": 84, "upper_now": 302.0, "lower_now": 294.0,
            "break_dir": 1, "break_price": 302.0, "critical_price_level": 302.0}


# --- B3: digest tamponu kalıcılığı ---------------------------------------

def _kayit(state="KIRILIM_ADAYI", stock="GARAN", kalite=80, timeframe="1h"):
    return {"stock": stock, "timeframe": timeframe, "pattern_name": "Simetrik Üçgen",
            "state": state, "quality": kalite}


def test_snapshot_yukle_gidis_donus():
    now = datetime.now(ISTANBUL_TZ)
    tampon = DeferredAlertBuffer()
    tampon.observe("GARAN", "1h", _kayit(), now)
    snap = tampon.snapshot()
    assert snap["surum"] == 1 and snap["gun"] == now.date().isoformat()

    yeni = DeferredAlertBuffer()
    assert yeni.yukle(json.loads(json.dumps(snap))) == 1
    assert yeni.gun() == now.date()
    kayitlar = yeni.items(now, limit=5)
    assert kayitlar[0]["stock"] == "GARAN" and kayitlar[0]["quality"] == 80

    # bozuk/eski snapshot sessizce yok sayılır (çökme yok)
    assert DeferredAlertBuffer().yukle({"surum": 99, "bekleyen": [_kayit()]}) == 0
    assert DeferredAlertBuffer().yukle(None) == 0
    assert DeferredAlertBuffer().yukle({"surum": 1, "gun": "bozuk"}) == 0


def test_digest_tamponu_diske_ve_geri_yuklenir(tmp_path, monkeypatch):
    monkeypatch.setattr(main_mod, "_supabase_store_ref", None)
    main_mod._deferred_alert_buffer.clear(datetime.now(ISTANBUL_TZ))
    now = datetime.now(ISTANBUL_TZ)
    main_mod._deferred_alert_buffer.observe("AKBNK", "1h", _kayit(stock="AKBNK"), now)

    assert main_mod.digest_tamponu_kaydet(data_dir=str(tmp_path)) is True
    dosya = tmp_path / main_mod.DIGEST_PENDING_DOSYA
    assert dosya.exists()

    main_mod._deferred_alert_buffer.clear(now)
    assert len(main_mod._deferred_alert_buffer) == 0
    assert main_mod.digest_tamponu_yukle(data_dir=str(tmp_path)) == 1
    assert main_mod._deferred_alert_buffer.items(now, limit=5)[0]["stock"] == "AKBNK"


def test_digest_son_gonderim_gunu_kalicidir(tmp_path, monkeypatch):
    monkeypatch.setattr(main_mod, "_supabase_store_ref", None)
    now = datetime.now(ISTANBUL_TZ)
    main_mod._digest_son_gonderim_gun = now.date().isoformat()
    main_mod.digest_tamponu_kaydet(data_dir=str(tmp_path))

    main_mod._digest_son_gonderim_gun = None
    main_mod.digest_tamponu_yukle(data_dir=str(tmp_path))
    assert main_mod._digest_son_gonderim_gun == now.date().isoformat()


def test_kacirilan_digest_telafisi_gonderir(tmp_path, monkeypatch):
    """Dün 18:45 kaçırıldıysa açılışta telafi edilir; tampon temizlenir."""
    monkeypatch.setattr(main_mod, "_supabase_store_ref", None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    gonderilenler = []
    monkeypatch.setattr("requests.post", lambda url, json=None, timeout=None:
                        (gonderilenler.append(json), _Yanit(200))[1])

    simdi = datetime.now(ISTANBUL_TZ)
    dun = simdi - timedelta(days=1)
    main_mod._deferred_alert_buffer.clear(simdi)
    main_mod._deferred_alert_buffer.observe("GARAN", "1h", _kayit(), dun)
    main_mod.digest_tamponu_kaydet(data_dir=str(tmp_path))
    monkeypatch.setattr(main_mod, "_deferred_alert_buffer", DeferredAlertBuffer())
    main_mod._digest_son_gonderim_gun = None

    assert main_mod.digest_tamponu_yukle(data_dir=str(tmp_path)) == 1
    notifier = TelegramNotifier()
    main_mod._kacirilan_digest_ozeti(notifier, simdi)

    assert len(gonderilenler) == 1
    metin = gonderilenler[0]["text"]
    assert "Kaçırılan kapanış özeti" in metin and "GARAN" in metin
    assert len(main_mod._deferred_alert_buffer) == 0, "telafi sonrası tampon temizlenmeli"
    # Telafi edilen gün damgalanır; bugünün 18:45'i hâlâ bekliyor.
    assert main_mod._digest_son_gonderim_gun == dun.date().isoformat()
    assert main_mod._digest_son_gonderim_gun != simdi.date().isoformat()


def test_bugunun_tamponu_telafi_edilmez(tmp_path, monkeypatch):
    """Aynı günün bekleyen adayları 18:45 özetini bekler, erken gönderilmez."""
    monkeypatch.setattr(main_mod, "_supabase_store_ref", None)
    simdi = datetime.now(ISTANBUL_TZ)
    main_mod._deferred_alert_buffer.clear(simdi)
    main_mod._deferred_alert_buffer.observe("GARAN", "1h", _kayit(), simdi)
    main_mod.digest_tamponu_kaydet(data_dir=str(tmp_path))
    monkeypatch.setattr(main_mod, "_deferred_alert_buffer", DeferredAlertBuffer())
    main_mod.digest_tamponu_yukle(data_dir=str(tmp_path))

    assert main_mod._kacirilan_digest_ozeti(None, simdi) == ""
    assert len(main_mod._deferred_alert_buffer) == 1, "bugünün adayları korunmalı"


# --- B4: engellenen acil olay kuyruğu ------------------------------------

def test_kap_engeli_kuyruga_alir(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    n.max_gunluk = 0  # günlük kap dolu → acil olay engellenir (kuyruk yolu)
    assert n.send(_veri()) is False
    assert notifier_mod.ACIL_KUYRUK_TTL_DK > 0
    assert n.kuyruk_durumu()["bekleyen"] == 1
    assert n.kuyrukta_mi(_veri()) is True
    assert gonderilenler == [], "engel varken hiç mesaj gitmemeli"
    assert n.engeller["gunluk_kap"] == 1


def test_kap_engeli_ayni_olayi_ikinci_kez_kuyruklamaz(monkeypatch):
    n, _ = _aktif(monkeypatch)
    n.max_gunluk = 0
    n.send(_veri())
    n.send(_veri())
    assert n.kuyruk_durumu()["bekleyen"] == 1


def test_engel_kalkinca_kuyruk_gonderilir(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    n.max_gunluk = 0
    n.send(_veri())
    assert n.kuyruk_durumu()["bekleyen"] == 1

    n.max_gunluk = 120  # yeni gün / kap açıldı: engel kalktı
    assert n.kuyrugu_bosalt() == 1
    assert n.kuyruk_durumu()["bekleyen"] == 0
    assert n.kuyruk_gonderildi == 1
    assert len(gonderilenler) == 1 and "THYAO" in gonderilenler[0]["text"]
    assert n.last_sent  # cooldown kaydı da yazıldı


def test_kuyruktan_gonderilen_tekrar_kuyruklanmaz(monkeypatch):
    """Kuyruk gönderimi başarısız olursa (ağ hatası) kayıt korunur, çoğalmaz."""
    n, _ = _aktif(monkeypatch, cevaplar=_Yanit(500, "server error"))
    n.max_gunluk = 0
    n.send(_veri())
    n.max_gunluk = 120
    assert n.kuyrugu_bosalt() == 0
    assert n.kuyruk_durumu()["bekleyen"] == 1, "ağ hatasında olay kaybolmamalı"


def test_bayat_kuyruk_kaydi_atilir(monkeypatch):
    n, _ = _aktif(monkeypatch)
    n.max_gunluk = 120
    n._acil_kuyruk.append({
        "kuyruk_zaman": (datetime.now(ISTANBUL_TZ)
                         - timedelta(minutes=notifier_mod.ACIL_KUYRUK_TTL_DK + 10)).isoformat(),
        "son_engel": "gunluk_kap",
        "veri": _veri(stock="ESKI"),
    })
    assert n.kuyrugu_bosalt() == 0
    assert n.kuyruk_durumu()["bekleyen"] == 0
    assert n.kuyruk_zaman_asimi == 1


def test_kuyruk_kalicidir(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    n = TelegramNotifier()
    n.max_gunluk = 0
    n.enabled = True  # kuyruklama aktif notifier gerektirir
    monkeypatch.setattr("requests.post", lambda *a, **k: _Yanit(500, "kap"))
    # Kap dolu olduğu için kuyruğa girer (enabled=True ama can_send engelli).
    assert n.send(_veri()) is False
    assert n.kuyruk_durumu()["bekleyen"] == 1

    yeni = TelegramNotifier(initial_store_data={"state:telegram_acil_kuyruk":
                                                json.loads(json.dumps(n._acil_kuyruk))})
    assert yeni.kuyruk_durumu()["bekleyen"] == 1
    assert yeni.kuyrukta_mi(_veri()) is True


def test_kuyruk_limiti_asilinca_eskiler_atar(monkeypatch):
    n, _ = _aktif(monkeypatch)
    n.max_gunluk = 0
    limit = notifier_mod.ACIL_KUYRUK_LIMIT
    for i in range(limit + 3):
        n.send(_veri(stock=f"HISSE{i:02d}"))
    durum = n.kuyruk_durumu()
    assert durum["bekleyen"] == limit
    assert n.kuyruk_tasmasi == 3


def test_gonderim_durumu_kuyrugu_raporlar(monkeypatch):
    n, _ = _aktif(monkeypatch)
    n.max_gunluk = 0
    n.send(_veri())
    d = n.gonderim_durumu()
    assert d["acil_kuyruk"] == 1 and d["kuyruk_gonderildi"] == 0
    assert "acil_kuyruk" in d and "bekleyen" in n.kuyruk_durumu()


def test_heartbeat_kuyruk_ve_bekleyen_digest_yazar(tmp_path, monkeypatch):
    monkeypatch.setattr(main_mod, "_deque_manager_ref", None)
    monkeypatch.setattr(main_mod, "_supabase_store_ref", None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    n = TelegramNotifier()
    now = datetime.now(ISTANBUL_TZ)
    main_mod._deferred_alert_buffer.clear(now)
    main_mod._deferred_alert_buffer.observe("GARAN", "1h", _kayit(), now)
    # force=True: throttle penceresi önceki testten taşabilir (üretimde tarama
    # sonunda da force çağrılır).
    main_mod.write_heartbeat(data_dir=str(tmp_path), notifier=n, force=True)

    veri = json.loads((tmp_path / "heartbeat.json").read_text(encoding="utf-8"))
    assert veri["bekleyen_bildirim"] == 1
    assert veri["acil_kuyruk"] == 0
    assert "acil_kuyruk" in veri["telegram_gonderim"]


def test_durum_hunisi_kuyruk_sayacini_gosterir():
    main_mod.daily_stats.update(alerts_kuyruk=2)
    try:
        metin = main_mod._komut_durum("")
        assert "2 kuyruğa alındı" in metin
    finally:
        main_mod.daily_stats.update(alerts_kuyruk=0)
