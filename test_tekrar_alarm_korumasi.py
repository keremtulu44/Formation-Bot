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


def _veri(state="KIRILIM_TEYITLI", stock="THYAO", pattern_name="Yükselen Üçgen"):
    """Acil (ALERT_STATES) bir olay; aynı slot = THYAO + Yükselen Üçgen + 1h."""
    return {"stock_name": stock, "pattern_name": pattern_name, "timeframe": "1h",
            "state": state, "confidence_score": 84, "upper_now": 302.0, "lower_now": 294.0,
            "break_dir": 1, "break_price": 302.0, "critical_price_level": 302.0}


# --- a) cooldown bitse de aynı olay tekrarlanmaz --------------------------

def test_ayni_olay_cooldown_bitse_de_tekrarlanmaz(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    veri = _veri("KIRILIM_TEYITLI")
    assert n.send(veri) is True
    assert len(gonderilenler) == 1

    # 4 saatlik zaman cooldown'u dolmuş gibi last_sent'i 5 saat geri çek:
    # eski dünyada tam bu noktada kopya mesaj basılıyordu.
    key = n._cooldown_key("THYAO", "Yükselen Üçgen", "1h", "KIRILIM_TEYITLI")
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
    # Kapanışla doğrulanmış kırılım -> başarılı retest: her olay bir kez.
    for durum in ("KIRILIM_TEYITLI", "RETEST_BASARILI"):
        assert n.send(_veri(durum)) is True, f"{durum} bildirilmeli"
    assert len(gonderilenler) == 2
    assert n.engeller["tekrar"] == 0, "ilerleme tekrar sayılmamalı"

    # Ama son state'in AYNI olayı tekrar: sessizce düşer.
    assert n.send(_veri("RETEST_BASARILI")) is False
    assert n._son_engel == "tekrar"
    assert len(gonderilenler) == 2


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
    assert n.send(_veri("KIRILIM_TEYITLI", stock="THYAO")) is True
    assert n.send(_veri("KIRILIM_TEYITLI", stock="GARAN")) is True

    # Yaşam döngüsü THYAO slotunu sıfırladı (örn. FORMASYON_GECERSIZ):
    n.son_alert_sifirla("THYAO", "1h")
    # Zaman cooldown'ları temizlendi (yeni formasyon 4 saat beklemesin)...
    assert not any(k.startswith("THYAO_") and "_1h_" in k for k in n.last_sent), \
        "slot sıfırlama cooldown anahtarlarını silmeli"
    # ...AMA mühür KORUNUR: aynı gün içinde aynı olay bir daha basılmaz.
    assert n.send(_veri("KIRILIM_TEYITLI", stock="THYAO")) is False
    assert n._son_engel == "tekrar"
    muhur = n._son_alert.get(n._son_alert_key("THYAO", "1h", "KIRILIM_TEYITLI"))
    assert muhur is not None, "muhur korunmali"
    assert muhur.get("state") == "KIRILIM_TEYITLI"
    assert muhur.get("tf") == "1h" and muhur.get("zaman")
    assert len(gonderilenler) == 2, "kopya mesaj gitmemeli"

    # Başka slotun (GARAN) mührü de korunur: kopyası hâlâ düşer.
    assert n.send(_veri("KIRILIM_TEYITLI", stock="GARAN")) is False
    assert n._son_engel == "tekrar"
    assert len(gonderilenler) == 2

    # Flicker üst üste gelse bile mühür yerinde (eski davranış: her sıfırlamada
    # mühür silinip kopya basılıyordu).
    for _ in range(3):
        n.son_alert_sifirla("THYAO", "1h")
        assert n.send(_veri("KIRILIM_TEYITLI", stock="THYAO")) is False
    assert len(gonderilenler) == 2

    # Yeni formasyonun FARKLI state'i (ilerleme) yine bildirilir.
    assert n.send(_veri("RETEST_BASARILI", stock="THYAO")) is True
    assert len(gonderilenler) == 3


def test_pattern_etiketi_degisince_ayni_olay_tekrar_sayilmaz(monkeypatch):
    """Aynı slotta motor bazen 'Simetrik Üçgen' bazen 'Alçalan Üçgen' basıyordu.

    Mühür anahtarında pattern OLMAYINCA iki etiket = iki mesaj olmuyor.
    """
    n, gonderilenler = _aktif(monkeypatch)
    assert n.send(_veri("KIRILIM_TEYITLI", stock="PETKM")) is True
    assert n.send(_veri("KIRILIM_TEYITLI", stock="PETKM",
                        pattern_name="Alçalan Üçgen")) is False
    assert n._son_engel == "tekrar"
    assert len(gonderilenler) == 1


def test_muhr_ttl_dolsa_da_teslim_edilmis_olay_tekrarlanmaz(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    assert n.send(_veri("KIRILIM_TEYITLI", stock="THYAO")) is True
    assert n.send(_veri("KIRILIM_TEYITLI", stock="THYAO")) is False

    # A completed durable delivery still prevents replay when the older seal expires.
    bayat = (datetime.now(ISTANBUL_TZ) - timedelta(hours=10)).isoformat()
    n._son_alert[n._son_alert_key("THYAO", "1h", "KIRILIM_TEYITLI")] = \
        {"state": "KIRILIM_TEYITLI", "zaman": bayat, "tf": "1h"}
    n.last_sent.pop(n._cooldown_key("THYAO", "Yükselen Üçgen", "1h",
                                    "KIRILIM_TEYITLI"), None)
    assert n.send(_veri("KIRILIM_TEYITLI", stock="THYAO")) is False
    assert len(gonderilenler) == 1


def test_eski_bicim_muhurler_acilista_tasinir(monkeypatch):
    """Upgrade öncesi düz-string mühürler açılışta yeni biçime taşınır.

    Amaç: deploy anında kopya mesaj dalgası çıkmasın.
    """
    eski = {"THYAO_Yükselen Üçgen_1h": "KIRILIM_TEYITLI",
            "GARAN_Alçalan Kama_4h": "RETEST_BASARILI"}
    yeni = TelegramNotifier(initial_store_data={"state:telegram_son_alerts": eski})
    kayit = yeni._son_alert.get("THYAO_1h_KIRILIM_TEYITLI")
    assert kayit and kayit.get("state") == "KIRILIM_TEYITLI"
    assert kayit.get("tf") == "1h" and kayit.get("zaman")
    kayit2 = yeni._son_alert.get("GARAN_4h_RETEST_BASARILI")
    assert kayit2 and kayit2.get("state") == "RETEST_BASARILI"
    assert kayit2.get("tf") == "4h" and kayit2.get("zaman")
    # Eski biçim taşındığı için aynı olay bugün tekrar basılmaz.
    assert yeni.can_send("THYAO", "Yükselen Üçgen", "1h", "KIRILIM_TEYITLI") is False
    assert yeni._son_engel == "tekrar"


# --- d) mühür restart'ta kalıcı (Supabase state satırı) --------------------

def test_muher_restartta_kalicidir(monkeypatch):
    n, _ = _aktif(monkeypatch)
    assert n.send(_veri("KIRILIM_TEYITLI")) is True
    muherler = json.loads(json.dumps(n._son_alert))
    assert muherler, "başarılı gönderim mühür basmalı"

    # Restart simülasyonu: mühür yalnız Supabase state satırından gelir.
    yeni = TelegramNotifier(initial_store_data={"state:telegram_son_alerts": muherler})
    yeni.retry_bekleme_sn = 0.0
    assert yeni._son_alert == muherler

    # Aynı state hâlâ mühürlü: zaman cooldown'undan bağımsız nihai red.
    key = yeni._cooldown_key("THYAO", "Yükselen Üçgen", "1h", "KIRILIM_TEYITLI")
    yeni.last_sent.pop(key, None)  # cooldown'u tamamen kaldır; yalnız mühür kalsın
    assert yeni.can_send("THYAO", "Yükselen Üçgen", "1h", "KIRILIM_TEYITLI") is False
    assert yeni._son_engel == "tekrar"
    # Mühür yalnız AYNI state'i susturur; yaşam döngüsü ilerlemesi serbest.
    assert yeni.can_send("THYAO", "Yükselen Üçgen", "1h", "RETEST_BASARILI") is True


# --- e) kuyruktaki tekrar-mühürlü bayat kopya sessizce düşer ----------------

def test_kuyruktaki_tekrar_muherli_bayat_kopya_duser(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    # Olay normal yoldan gönderildi (mühür basıldı); aynı olayın bayat kopyası
    # kuyruktaymış (örn. redploy'da kuyruk kalıcı state'ten geri yüklendi).
    assert n.send(_veri("KIRILIM_TEYITLI")) is True
    simdi = datetime.now(ISTANBUL_TZ)
    n._acil_kuyruk.append({
        "kuyruk_zaman": simdi.isoformat(),
        "son_deneme": simdi.isoformat(),
        "son_engel": "cooldown",
        "veri": dict(_veri("KIRILIM_TEYITLI")),
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


# --- f) mühür TTL'i zaman dilimine göre ölçeklenir ------------------------
# KÖK NEDEN (düzeltme sonrası): motor bitmiş (terminal) bir formasyonu
# TERMINAL_TAZE_BAR = 3 bar boyunca "taze" sayar ve raporlamaya devam eder
# (ölü formasyon filtresindeki istisna). Mühür "İstanbul günü" ile bayatıyordu;
# bu yüzden gün sınırını aşan formasyonlar sonraki gün/taramada TEKRAR
# bildiriliyordu — kullanıcının şikayet ettiği tekrar mesajlarının aynısı.
#   1 günlük grafikte 3 bar = 3 gün  -> aynı haber 3 gün daha basılıyordu
#   4 saatlikte     3 bar = 12 saat -> ertesi sabah yine basılıyordu
# Artık TTL bar süresine göre ölçekleniyor: 3 bar + 1 saat pay.

def _muhur_yaz(n, stock, tf, state, saat_once):
    """Slot'a `saat_once` saat önce basılmış bir mühür yerleştirir."""
    zaman = (datetime.now(ISTANBUL_TZ) - timedelta(hours=saat_once)).isoformat()
    n._son_alert[n._son_alert_key(stock, tf, state)] = {
        "state": state, "zaman": zaman, "tf": tf}


def test_muhur_ttl_1d_uc_gun_gecerli_kalir(monkeypatch):
    """1 günlük grafikte 3 bar = 3 gün: dün basılan mühür bugün de geçerli."""
    n, gonderilenler = _aktif(monkeypatch)
    veri = _veri("KIRILIM_TEYITLI")
    veri["timeframe"] = "1d"
    _muhur_yaz(n, "THYAO", "1d", "KIRILIM_TEYITLI", saat_once=20)
    assert n.can_send("THYAO", "Yükselen Üçgen", "1d", "KIRILIM_TEYITLI") is False
    assert n._son_engel == "tekrar"

    # 3 bar + pay = 73 saat geçmişse bayat sayılır.
    _muhur_yaz(n, "THYAO", "1d", "KIRILIM_TEYITLI", saat_once=80)
    assert n.can_send("THYAO", "Yükselen Üçgen", "1d", "KIRILIM_TEYITLI") is True
    assert gonderilenler == []


def test_muhur_ttl_4s_ertesi_sabah_gecerli_kalir(monkeypatch):
    """4 saatlikte 3 bar = 12 saat: akşam basılan mühür ertesi sabah da geçerli."""
    n, _ = _aktif(monkeypatch)
    _muhur_yaz(n, "THYAO", "4h", "KIRILIM_TEYITLI", saat_once=12)
    assert n.can_send("THYAO", "Yükselen Üçgen", "4h", "KIRILIM_TEYITLI") is False
    assert n._son_engel == "tekrar"


def test_muhur_ttl_1s_dort_saat_sonra_bayat(monkeypatch):
    """1 saatlikte 3 bar = 3 saat (+1 pay): 5 saat önce basılan mühür bayattır."""
    n, _ = _aktif(monkeypatch)
    _muhur_yaz(n, "THYAO", "1h", "KIRILIM_TEYITLI", saat_once=5)
    assert n.can_send("THYAO", "Yükselen Üçgen", "1h", "KIRILIM_TEYITLI") is True


def test_muhur_kaydi_yeni_muhur_su_an_ile_damgalanir():
    """Yeni mühür ŞU AN ile damgalanmalı (eski hata: gün başına damgalanıp
    1 saatlik TTL anında bayatıyordu)."""
    kayit = TelegramNotifier._muhur_kaydi("KIRILIM_TEYITLI", "1d")
    assert kayit["state"] == "KIRILIM_TEYITLI" and kayit["tf"] == "1d"
    basma = datetime.fromisoformat(kayit["zaman"])
    yas_dk = (datetime.now(ISTANBUL_TZ) - basma).total_seconds() / 60
    assert 0 <= yas_dk < 1, "yeni mühür şu an ile damgalanmali"


def test_muhur_kaydi_eski_gun_bicimi_gece_yarisina_donusur():
    """Gün bazlı eski kayıt o günün 00:00'ine çevrilir (deploy dalgası çıkmasın)."""
    kayit = TelegramNotifier._muhur_kaydi("KIRILIM_TEYITLI", "1h", gun="2026-10-01")
    basma = datetime.fromisoformat(kayit["zaman"])
    assert basma.hour == 0 and basma.minute == 0 and basma.day == 1



def test_tamamlanma_basarisizlik_ve_deneme_push_edilmez(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    for state in ("FORMASYON_TAMAMLANDI", "BASARISIZ_KIRILIM", "KIRILIM_DENEMESI",
                  "KIRILIM_ADAYI", "KIRILIM_HAZIRLIGI",
                  "RETEST_BEKLENIYOR", "RETEST_EDILIYOR"):
        assert n.send(_veri(state)) is False
        assert not n.kuyrukta_mi(_veri(state))
    assert gonderilenler == []


def test_domain_prepare_only_runs_for_an_unsent_allowed_event(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    calls = []

    def prepare(payload):
        calls.append(payload["state"])
        # GÖRSEL-7 kartı `domain_context` metin bloğunu değil, AYRI bölümleri
        # (`domain_bolumleri`) okur — canlı `_attach_domain_context` de ikisini
        # birden yazar. Test "hazırlık çıktısı mesaja ulaştı mı" sorusunu sürer.
        payload["domain_bolumleri"] = {"hacim": ["katılım 1s fresh"]}

    allowed = _veri("KIRILIM_TEYITLI")
    assert n.send_with_prepare(allowed, before_send=prepare) is True
    assert calls == ["KIRILIM_TEYITLI"]
    assert "fresh" in gonderilenler[0]["text"]

    # Same sealed event is rejected before expensive domain preparation.
    assert n.send_with_prepare(allowed, before_send=prepare) is False
    assert calls == ["KIRILIM_TEYITLI"]
    disallowed = _veri("KIRILIM_DENEMESI")
    assert n.send_with_prepare(disallowed, before_send=prepare) is False
    assert calls == ["KIRILIM_TEYITLI"]


def test_confirmed_break_invalidation_has_its_own_one_time_seal(monkeypatch):
    n, sent = _aktif(monkeypatch)
    assert n.send(_veri("BASARISIZ_KIRILIM")) is False
    assert sent == []

    invalidation = _veri("KIRILIM_GECERSIZLESTI")
    invalidation["formation_id"] = "stable-formation-invalidation"
    assert n.send(invalidation) is True
    assert len(sent) == 1
    # Kart başlığı olayı ilk satırda söyler (bildirim önizlemesi okunabilsin).
    assert "KIRILIM İPTAL" in sent[0]["text"]
    assert n.send(invalidation) is False
    assert len(sent) == 1


def test_domain_prepare_error_does_not_suppress_alert(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)

    def fail_context(_payload):
        raise RuntimeError("simulated formatter failure")

    assert n.send_with_prepare(
        _veri("KIRILIM_TEYITLI"), before_send=fail_context
    ) is True
    assert len(gonderilenler) == 1
    assert "Market Structure" not in gonderilenler[0]["text"]


def test_same_formation_event_remains_sealed_past_legacy_bar_ttl(monkeypatch):
    n, _ = _aktif(monkeypatch)
    old_time = (datetime.now(ISTANBUL_TZ) - timedelta(days=4)).isoformat()
    formation_id = "stable-formation-42"
    key = n._son_alert_key("THYAO", "4h", "RETEST_BASARILI", formation_id)
    n._son_alert[key] = n._muhur_kaydi(
        "RETEST_BASARILI", "4h", zaman=old_time, formation_id=formation_id
    )

    # 4 days is far beyond the old 4h repeat TTL, but this same retest must not
    # become a second Telegram alert. A genuinely new formation may alert.
    assert n.can_send(
        "THYAO", "Yükselen Üçgen", "4h", "RETEST_BASARILI",
        formation_id=formation_id,
    ) is False
    assert n.can_send(
        "THYAO", "Yükselen Üçgen", "4h", "RETEST_BASARILI",
        formation_id="stable-formation-43",
    ) is True


# --- içerik kopyası kapısı (2026-10-23) -------------------------------------
# Kullanıcı bildirimi: ALARK 4s üç kez, KCHOL 2s üç kez AYNI kart basıldı.
# Sebep: mühür `formation_id` ile tekilleşiyor, motor aynı kurulumu her taramada
# yeni kimlikle üretiyor. Artık kartın KENDİSİ de kapı: birebir aynı metin
# TTL içinde ikinci kez gitmez.

def test_ayni_kart_farkli_kimlikle_tekrar_basilmaz(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    # Zaman cooldown'ı devre dışı: sınanan kapı İÇERİK kapısı olsun.
    n.cooldown_hours = 0
    ilk = _veri("KIRILIM_TEYITLI", stock="ALARK")
    ilk.update({"timeframe": "4h", "formation_id": "tarama-1"})
    assert n.send(ilk) is True
    ikinci = _veri("KIRILIM_TEYITLI", stock="ALARK")
    ikinci.update({"timeframe": "4h", "formation_id": "tarama-2"})
    assert n.send(ikinci) is False
    assert n._son_engel == "tekrar"
    assert len(gonderilenler) == 1


def test_kart_degistiyse_yeni_olay_gecer(monkeypatch):
    n, gonderilenler = _aktif(monkeypatch)
    n.cooldown_hours = 0
    ilk = _veri("KIRILIM_TEYITLI", stock="KCHOL")
    ilk.update({"timeframe": "2h", "formation_id": "tarama-1"})
    assert n.send(ilk) is True
    # Kapanış değişti → metin değişti → bu gerçekten yeni bilgi.
    yeni = dict(ilk, formation_id="tarama-2", candle_close_price=305.5)
    assert n.send(yeni) is True
    assert len(gonderilenler) == 2


def test_klasik_stil_de_kopya_kart_basmaz(monkeypatch):
    """Geri dönüş yolu (`klasik`) metni korur; kopya mesaj yine engellenir."""
    monkeypatch.setattr(notifier_mod, "TELEGRAM_ALERT_STYLE", "klasik")
    n, gonderilenler = _aktif(monkeypatch)
    ilk = _veri("KIRILIM_TEYITLI", stock="TTKOM")
    ilk.update({"timeframe": "4h", "formation_id": "tarama-1"})
    assert n.send(ilk) is True
    assert n.send(dict(ilk, formation_id="tarama-2")) is False
    assert len(gonderilenler) == 1
