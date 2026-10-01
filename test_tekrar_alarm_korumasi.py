"""Tekrar alarm koruması (repeat-guard): tek-seferlik olay hafızası.

Kök neden: motor `tam_yeniden=True` ile pencereyi her taramada baştan oynattığı
için terminal/acil state'ler (config.ALERT_STATES) her tur yeniden üretiliyordu.
Tek koruma 4 saatlik zaman cooldown'ıydı; (1) cooldown dolunca aynı olay tekrar
basılıyordu (4h TF'de 1 bar = 4 saat = cooldown süresi), (2) cooldown'a takılan
olay acil kuyruğa alınıp engel kalkınca bayat kopya ikinci kez gidiyordu,
(3) redploy'da kuyruk/mühür state anahtarları boot remote_keys'te yoktu.

Ağ yok; `requests.post` sahtelenir. Supabase bağlantısı yok (store=None),
disk yolu tmp_path'e taşınır. DATA_DIR izolasyon fixture'ı test_kayip_bildirim.py
ile birebir aynıdır.
"""

import inspect
import json
from datetime import datetime, timedelta

import pytest

import main as main_mod
import notifier as notifier_mod
from config import ISTANBUL_TZ
from notifier import TelegramNotifier

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


def _veri(state="FORMASYON_TAMAMLANDI", stock="THYAO", pattern_name="Yükselen Üçgen"):
    """Acil (ALERT_STATES) bir olay; aynı slot = THYAO + Yükselen Üçgen + 1h."""
    return {"stock_name": stock, "pattern_name": pattern_name, "timeframe": "1h",
            "state": state, "confidence_score": 84, "upper_now": 302.0, "lower_now": 294.0,
            "break_dir": 1, "break_price": 302.0, "critical_price_level": 302.0}


# --- a) cooldown bitse de aynı olay tekrarlanmaz --------------------------

def test_ayni_olay_cooldown_bitse_de_tekrarlanmaz(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    veri = _veri("FORMASYON_TAMAMLANDI")
    assert n.send(veri) is True
    assert len(gonderilenler) == 1

    # 4 saatlik zaman cooldown'u dolmuş gibi last_sent'i 5 saat geri çek:
    # eski dünyada tam bu noktada kopya mesaj basılıyordu.
    key = n._cooldown_key("THYAO", "Yükselen Üçgen", "1h", "FORMASYON_TAMAMLANDI")
    n.last_sent[key] = datetime.now(ISTANBUL_TZ) - timedelta(hours=5)
    assert (datetime.now(ISTANBUL_TZ) - n.last_sent[key]) > timedelta(hours=n.cooldown_hours)

    assert n.send(veri) is False
    assert n._son_engel == "tekrar"
    assert n.engeller["tekrar"] == 1
    assert len(gonderilenler) == 1, "kopya mesaj gitmemeli"
    assert n.kuyruk_durumu()["bekleyen"] == 0, "tekrar engeli nihai redir; kuyruk dolu kalmamalı"


# --- b) yaşam döngüsü ilerlemesi serbest -----------------------------------

def test_state_ilemesi_serbest_kalir(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    # Aynı slot için TEYITLI -> RETEST_BASARILI -> TAMAMLANDI: her biri bir kez.
    for durum in ("KIRILIM_TEYITLI", "RETEST_BASARILI", "FORMASYON_TAMAMLANDI"):
        assert n.send(_veri(durum)) is True, f"{durum} bildirilmeli"
    assert len(gonderilenler) == 3
    assert n.engeller["tekrar"] == 0, "ilerleme tekrar sayılmamalı"

    # Ama son state'in AYNI olayı tekrar: sessizce düşer.
    assert n.send(_veri("FORMASYON_TAMAMLANDI")) is False
    assert n._son_engel == "tekrar"
    assert len(gonderilenler) == 3


# --- c) slot sıfırlama (flicker): aynı gün tekrar bildirim YOK ------------
# KÖK NEDEN (düzeltme sonrası): motorun canlı geometrisi (has_pattern) kayan
# pencerede bir taramada False olup FORMASYON_YOK'a düşüyor (flicker); main bu
# yüzden son_alert_sifirla() çağırıyordu. Eskiden bu fonksiyon MÜHÜRÜ de sildiği
# için formasyon bir sonraki taramada yeniden "doğup" AYNI TAMAMLANDI mesajını
# tekrar basıyordu (kullanıcı günlüğünde ~45 mesajın ~13'ü birebir kopya).
# Artık sıfırlama yalnız ZAMAN cooldown'ını temizler; mühür gün sonuna kadar
# korunur. Yeni formasyonun ilerleme mesajları (TEYITLI/RETEST) yine serbest.

def test_slot_sifirlaninca_ayni_olay_tekrar_gonderilmez(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    assert n.send(_veri("FORMASYON_TAMAMLANDI", stock="THYAO")) is True
    assert n.send(_veri("FORMASYON_TAMAMLANDI", stock="GARAN")) is True

    # Yaşam döngüsü THYAO slotunu sıfırladı (örn. FORMASYON_GECERSIZ):
    n.son_alert_sifirla("THYAO", "1h")
    # Zaman cooldown'ları temizlendi (yeni formasyon 4 saat beklemesin)...
    assert not any(k.startswith("THYAO_") and "_1h_" in k for k in n.last_sent), \
        "slot sıfırlama cooldown anahtarlarını silmeli"
    # ...AMA mühür KORUNUR: aynı gün içinde aynı olay bir daha basılmaz.
    assert n.send(_veri("FORMASYON_TAMAMLANDI", stock="THYAO")) is False
    assert n._son_engel == "tekrar"
    assert n._son_alert.get(n._son_alert_key("THYAO", "1h", "FORMASYON_TAMAMLANDI")) \
        == {"state": "FORMASYON_TAMAMLANDI", "gun": n._son_alert_bugun()}
    assert len(gonderilenler) == 2, "kopya mesaj gitmemeli"

    # Başka slotun (GARAN) mührü de korunur: kopyası hâlâ düşer.
    assert n.send(_veri("FORMASYON_TAMAMLANDI", stock="GARAN")) is False
    assert n._son_engel == "tekrar"
    assert len(gonderilenler) == 2

    # Flicker üst üste gelse bile mühür yerinde (eski davranış: her sıfırlamada
    # mühür silinip kopya basılıyordu).
    for _ in range(3):
        n.son_alert_sifirla("THYAO", "1h")
        assert n.send(_veri("FORMASYON_TAMAMLANDI", stock="THYAO")) is False
    assert len(gonderilenler) == 2

    # Yeni formasyonun FARKLI state'i (ilerleme) yine bildirilir.
    assert n.send(_veri("RETEST_BASARILI", stock="THYAO")) is True
    assert len(gonderilenler) == 3


def test_pattern_etiketi_degisince_ayni_olay_tekrar_sayilmaz(monkeypatch):
    """Aynı slotta motor bazen 'Simetrik Üçgen' bazen 'Alçalan Üçgen' basıyordu.

    Mühür anahtarında pattern OLMAYINCA iki etiket = iki mesaj olmuyor.
    """
    n, gonderilenler = _aktif(monkeypatch)
    assert n.send(_veri("FORMASYON_TAMAMLANDI", stock="PETKM")) is True
    assert n.send(_veri("FORMASYON_TAMAMLANDI", stock="PETKM",
                        pattern_name="Alçalan Üçgen")) is False
    assert n._son_engel == "tekrar"
    assert len(gonderilenler) == 1


def test_muhr_yeni_gunde_bayalar_tekrar_bildirim_serbest(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    assert n.send(_veri("FORMASYON_TAMAMLANDI", stock="THYAO")) is True
    assert n.send(_veri("FORMASYON_TAMAMLANDI", stock="THYAO")) is False

    # Gün değişimi: mühürler bayatlar, aynı olay tekrar bildirilebilir.
    dun = {"state": "FORMASYON_TAMAMLANDI", "gun": "2020-01-01"}
    n._son_alert[n._son_alert_key("THYAO", "1h", "FORMASYON_TAMAMLANDI")] = dun
    n.last_sent.pop(n._cooldown_key("THYAO", "Yükselen Üçgen", "1h",
                                    "FORMASYON_TAMAMLANDI"), None)
    assert n.send(_veri("FORMASYON_TAMAMLANDI", stock="THYAO")) is True
    assert len(gonderilenler) == 2


def test_eski_bicim_muhurler_acilista_tasinir(monkeypatch):
    """Upgrade öncesi düz-string mühürler açılışta yeni biçime taşınır.

    Amaç: deploy anında kopya mesaj dalgası çıkmasın.
    """
    eski = {"THYAO_Yükselen Üçgen_1h": "FORMASYON_TAMAMLANDI",
            "GARAN_Alçalan Kama_4h": "RETEST_BASARILI"}
    yeni = TelegramNotifier(initial_store_data={"state:telegram_son_alerts": eski})
    bugun = yeni._son_alert_bugun()
    assert yeni._son_alert.get("THYAO_1h_FORMASYON_TAMAMLANDI") == \
        {"state": "FORMASYON_TAMAMLANDI", "gun": bugun}
    assert yeni._son_alert.get("GARAN_4h_RETEST_BASARILI") == \
        {"state": "RETEST_BASARILI", "gun": bugun}
    # Eski biçim taşındığı için aynı olay bugün tekrar basılmaz.
    assert yeni.can_send("THYAO", "Yükselen Üçgen", "1h", "FORMASYON_TAMAMLANDI") is False
    assert yeni._son_engel == "tekrar"


# --- d) mühür restart'ta kalıcı (Supabase state satırı) --------------------

def test_muher_restartta_kalicidir(monkeypatch):
    n, _ = _aktif(monkeypatch)
    assert n.send(_veri("FORMASYON_TAMAMLANDI")) is True
    muherler = json.loads(json.dumps(n._son_alert))
    assert muherler, "başarılı gönderim mühür basmalı"

    # Restart simülasyonu: mühür yalnız Supabase state satırından gelir.
    yeni = TelegramNotifier(initial_store_data={"state:telegram_son_alerts": muherler})
    yeni.retry_bekleme_sn = 0.0
    assert yeni._son_alert == muherler

    # Aynı state hâlâ mühürlü: zaman cooldown'undan bağımsız nihai red.
    key = yeni._cooldown_key("THYAO", "Yükselen Üçgen", "1h", "FORMASYON_TAMAMLANDI")
    yeni.last_sent.pop(key, None)  # cooldown'u tamamen kaldır; yalnız mühür kalsın
    assert yeni.can_send("THYAO", "Yükselen Üçgen", "1h", "FORMASYON_TAMAMLANDI") is False
    assert yeni._son_engel == "tekrar"
    # Mühür yalnız AYNI state'i susturur; yaşam döngüsü ilerlemesi serbest.
    assert yeni.can_send("THYAO", "Yükselen Üçgen", "1h", "KIRILIM_TEYITLI") is True


# --- e) kuyruktaki tekrar-mühürlü bayat kopya sessizce düşer ----------------

def test_kuyruktaki_tekrar_muherli_bayat_kopya_duser(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    # Olay normal yoldan gönderildi (mühür basıldı); aynı olayın bayat kopyası
    # kuyruktaymış (örn. redploy'da kuyruk kalıcı state'ten geri yüklendi).
    assert n.send(_veri("FORMASYON_TAMAMLANDI")) is True
    simdi = datetime.now(ISTANBUL_TZ)
    n._acil_kuyruk.append({
        "kuyruk_zaman": simdi.isoformat(),
        "son_deneme": simdi.isoformat(),
        "son_engel": "cooldown",
        "veri": dict(_veri("FORMASYON_TAMAMLANDI")),
    })
    assert n.kuyruk_durumu()["bekleyen"] == 1

    assert n.kuyrugu_bosalt() == 0, "hiçbir şey gönderilmemeli"
    assert n._son_engel == "tekrar"
    assert n.kuyruk_durumu()["bekleyen"] == 0, "bayat kopya sessizce düşmeli"
    assert n.kuyruk_zaman_asimi == 0, "TTL ile değil, tekrar mühürüyle düştü"
    assert len(gonderilenler) == 1, "aynı olay ikinci kez gitmemeli"


# --- f) boot remote_keys iki yeni state anahtarını da içerir ----------------

def test_boot_remote_keys_state_anahtarlarini_icerir():
    """Deploy'da acil kuyruk ve tek-seferlik mühürler kaybolmamalı (kök neden 3)."""
    kaynak = inspect.getsource(main_mod.main_loop)
    assert "state:telegram_acil_kuyruk" in kaynak
    assert "state:telegram_son_alerts" in kaynak
