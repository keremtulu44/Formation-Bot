"""Restart gün sürekliliği testleri (canlı denetim bulguları A/B).

NEDEN: Render'da gün ortasında restart/deploy olunca şu iki hata canlıda
ölçülmüştü (02.10 denetimi):
  * BUG A — 09:55 kanal sabah notu ikinci kez gidiyordu (guard yalnız bellekte).
  * BUG B — 18:45 kanal kapanışı "❌ 8 başarısız / 8 tarama" diyordu; günün
    gerçeği "9 / 10" idi (günlük sayaçlar bellekte sıfırlanıyordu).
Ayrıca public bütçe sayaçları ve gönderilememiş bülten kuyruğu kayboluyordu.

Bu dosya ağa ÇIKMAZ: gerçek HTTP yok, dosya I/O'su tmp_path'e yazılır.
"""

import json
from datetime import datetime, timedelta

import pytest

import config
import main as main_mod
import notifier as notifier_mod
from config import ISTANBUL_TZ
from state import persistence as P


@pytest.fixture
def veri_dizini(monkeypatch, tmp_path):
    """config.DATA_DIR'i tmp'ye çevirir (paths modülü çağrı anında okur)."""
    hedef = tmp_path / "data"
    hedef.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", str(hedef))
    monkeypatch.setattr(config, "SEED_DATA_DIR", str(hedef))
    return str(hedef)


@pytest.fixture(autouse=True)
def gunluk_sayac_koru():
    """daily_stats global: test sonrası önceki değerlere döndürülür."""
    onceki = dict(main_mod.daily_stats)
    onceki_keys = set(main_mod._daily_basarisiz_keys)
    try:
        yield
    finally:
        main_mod.daily_stats.clear()
        main_mod.daily_stats.update(onceki)
        main_mod._daily_basarisiz_keys.clear()
        main_mod._daily_basarisiz_keys.update(onceki_keys)


def _gun_geri(gun_sayisi=1):
    return (datetime.now(ISTANBUL_TZ) - timedelta(days=gun_sayisi)).date()


# --- 1) kalıcılık katmanı ----------------------------------------------------

def test_gunluk_durum_gun_degisince_sifirlanir(veri_dizini):
    d = _gun_geri()
    P.gunluk_durum_guncelle({"sayaclar": {"tarama_sayisi": 7}}, gun=d, data_dir=veri_dizini)
    assert P.gunluk_durum_yukle(gun=d, data_dir=veri_dizini)["sayaclar"]["tarama_sayisi"] == 7
    # Ertesi gün aynı kayıt geçersiz: sayaçlar düne ait, bugüne taşınmaz.
    assert P.gunluk_durum_yukle(gun=d + timedelta(days=1), data_dir=veri_dizini) == {}


def test_gunluk_durum_eski_gunu_ezmez(veri_dizini):
    """Yeni günün ilk yazımı kaydı baştan kurar (dünün işaretleri kalır mı?)."""
    dun = _gun_geri()
    P.gunluk_durum_guncelle({"ozet_gunleri": {"09:55": dun.isoformat()}}, gun=dun, data_dir=veri_dizini)
    P.gunluk_durum_guncelle({"sayaclar": {"tarama_sayisi": 1}}, gun=dun + timedelta(days=1), data_dir=veri_dizini)
    kayit = P.gunluk_durum_yukle(gun=dun + timedelta(days=1), data_dir=veri_dizini)
    assert kayit["sayaclar"]["tarama_sayisi"] == 1
    assert "ozet_gunleri" not in kayit          # dünün işaretleri bugüne taşınmaz


def test_gunluk_durum_diger_anahtarlari_korur(veri_dizini):
    """post_close damgası ve günlük kayıt aynı dosyada çakışmadan yaşar."""
    assert P.gonderim_durumu_kaydet({"post_close_analizi_gun": "2026-09-25"}, data_dir=veri_dizini)
    P.gunluk_durum_guncelle({"public": {"gun_sayac": 3}}, data_dir=veri_dizini)
    P.gonderim_durumu_kaydet({"post_close_analizi_gun": "2026-09-25"}, data_dir=veri_dizini)
    assert P.gunluk_durum_yukle(data_dir=veri_dizini)["public"]["gun_sayac"] == 3
    assert P.gonderim_durumu_yukle(data_dir=veri_dizini)["post_close_analizi_gun"] == "2026-09-25"


# --- 2) BUG B: günlük sayaçlar restart'ta korunur ---------------------------

def test_sayaclar_restart_sonrasi_geri_yuklenir(veri_dizini, monkeypatch):
    main_mod.daily_stats["tarama_sayisi"] = 9
    main_mod.daily_stats["basarisiz_kirilim"] = 4
    main_mod.daily_stats["alerts_sent"] = 5
    main_mod.daily_stats["stocks_scanned"] = 280
    main_mod._gunluk_sayac_kaydet()

    # Restart taklidi: bellek sıfırlanır, disk kalır.
    main_mod.daily_stats["tarama_sayisi"] = 0
    main_mod.daily_stats["basarisiz_kirilim"] = 0
    main_mod.daily_stats["alerts_sent"] = 0
    main_mod.daily_stats["stocks_scanned"] = 0
    main_mod._daily_basarisiz_keys.clear()
    main_mod._gunluk_sayac_yukle()

    assert main_mod.daily_stats["tarama_sayisi"] == 9
    assert main_mod.daily_stats["alerts_sent"] == 5
    assert main_mod.daily_stats["stocks_scanned"] == 280
    # Kırılım sayacı düşmez; yeni olaylar tabanın ÜSTÜNE eklenir (çift sayım yok).
    assert main_mod.daily_stats["basarisiz_kirilim"] == 4
    main_mod._note_basarisiz_kirilim("THYAO", "1h", "2026-09-25 16:30")
    assert main_mod.daily_stats["basarisiz_kirilim"] == 5
    main_mod._note_basarisiz_kirilim("THYAO", "1h", "2026-09-25 16:30")
    assert main_mod.daily_stats["basarisiz_kirilim"] == 5   # aynı olay tekrar sayılmaz


def test_gun_degisimi_sayaci_sifirlar(veri_dizini):
    """Gün değişince kalıcı kayıt yeni güne kurulur ve sayaç sıfırlanır."""
    dun = _gun_geri()
    P.gunluk_durum_guncelle({"sayaclar": {"tarama_sayisi": 11}}, gun=dun, data_dir=veri_dizini)
    assert main_mod.daily_stats is not None
    bugun = datetime.now(ISTANBUL_TZ).date()
    assert P.gunluk_durum_yukle(gun=bugun, data_dir=veri_dizini).get("sayaclar") is None
    main_mod.daily_stats["last_reset"] = dun
    main_mod.daily_stats["tarama_sayisi"] = 11
    main_mod.reset_daily_if_needed()
    assert main_mod.daily_stats["tarama_sayisi"] == 0
    assert main_mod.daily_stats["last_reset"] == bugun


# --- 3) BUG A: özet işaretleri restart'ta korunur ---------------------------

def test_ozet_isareti_restart_sonrasi_okunur(veri_dizini):
    bugun = datetime.now(ISTANBUL_TZ).date()
    main_mod._ozet_isaret_kaydet("09:55", bugun)
    main_mod._ozet_isaret_kaydet("09:55", bugun, public=True)
    dm, public = main_mod._ozet_isaretlerini_yukle()
    assert dm == {"09:55": bugun}
    assert public == {"09:55": bugun}
    # Anahtar ayrımı dosyada korunur (aynı slot adı iki yayın yolu).
    ham = json.load(open(P.gonderim_durumu_yolu(veri_dizini), encoding="utf-8"))
    assert set(ham["gunluk"]["ozet_gunleri"]) == {"09:55", "public:09:55"}


def test_ozet_isareti_dunku_gunu_tasimaz(veri_dizini):
    dun = _gun_geri()
    main_mod._ozet_isaret_kaydet("09:55", dun, public=True)
    dm, public = main_mod._ozet_isaretlerini_yukle()
    # Dün gönderilmiş özet BUGÜN için engel değildir: yeni gün yeniden gönderilir.
    assert public.get("09:55") == dun
    assert datetime.now(ISTANBUL_TZ).date() != dun


def test_bozuk_isaret_kaydi_botu_durdurmaz(veri_dizini):
    P.gunluk_durum_guncelle({"ozet_gunleri": {"09:55": "bozuk-tarih", "public:": ""}})
    dm, public = main_mod._ozet_isaretlerini_yukle()
    assert dm == {} and public == {}


# --- 4) public bütçe + kuyruk kalıcılığı ------------------------------------

def _public_notifier(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-1001234567890")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    n = notifier_mod.TelegramNotifier()
    n.public_min_aralik_sn = 0
    n.retry_bekleme_sn = 0
    return n


def test_public_butce_ve_kuyruk_restart_sonrasi_korunur(veri_dizini, monkeypatch):
    n = _public_notifier(monkeypatch)
    assert n.public_kuyruk({"stock_name": "ISMEN", "timeframe": "4h",
                            "pattern_name": "Alçalan Üçgen", "state": "KIRILIM_TEYITLI",
                            "confidence_score": 86})
    n._public_gun_sayac = 6
    n._public_saatlik = [datetime.now(ISTANBUL_TZ)]
    n._public_durum_kaydet()

    # Restart: yeni notifier aynı DATA_DIR'i okur.
    n2 = _public_notifier(monkeypatch)
    assert n2._public_gun_sayac == 6
    assert len(n2._public_saatlik) == 1
    assert [k["stock_name"] for k in n2._public_kuyruk] == ["ISMEN"]


def test_public_kuyruk_gonderildikten_sonra_diskte_bos_kalir(veri_dizini, monkeypatch):
    n = _public_notifier(monkeypatch)
    n.public_kuyruk({"stock_name": "ISMEN", "timeframe": "4h",
                     "pattern_name": "Alçalan Üçgen", "state": "KIRILIM_TEYITLI",
                     "confidence_score": 86})

    class _Yanit:
        status_code = 200
        text = "ok"

        def json(self):
            return {"ok": True}

    monkeypatch.setattr("requests.post", lambda *a, **k: _Yanit())
    n.public_bosalt()
    assert n._public_kuyruk == []
    n2 = _public_notifier(monkeypatch)
    assert n2._public_kuyruk == []
    assert n2._public_gun_sayac == n._public_gun_sayac >= 1


def test_public_gun_degisince_butce_sifirlanir(veri_dizini, monkeypatch):
    n = _public_notifier(monkeypatch)
    n._public_gun = datetime.now(ISTANBUL_TZ).date() - timedelta(days=1)
    n._public_gun_sayac = 20
    n._public_saatlik = [datetime.now(ISTANBUL_TZ) - timedelta(days=1)]
    n._public_gun_sifirla_gerekirse(datetime.now(ISTANBUL_TZ))
    assert n._public_gun_sayac == 0 and n._public_saatlik == []
    n2 = _public_notifier(monkeypatch)
    assert n2._public_gun_sayac == 0 and n2._public_saatlik == []


# --- 5) kanal hedef doğrulaması (canlı açılış ön koşulu) ---------------------

class _HttpYanit:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def _hedef_dogrula(monkeypatch, uye_durum, uye_ek=None, tip="channel"):
    n = _public_notifier(monkeypatch)
    cevaplar = [
        {"ok": True, "result": {"id": 42424242, "username": "simulasyon_bot"}},
        {"ok": True, "result": {"type": tip, "title": "BIST Formasyon"}},
        {"ok": True, "result": dict({"status": uye_durum}, **(uye_ek or {}))},
    ]
    monkeypatch.setattr("requests.post", lambda *a, **k: _HttpYanit(cevaplar.pop(0)))
    return n.check_public_connection()


def test_kanal_yonetici_degilse_uyari(monkeypatch, veri_dizini):
    bilgi = _hedef_dogrula(monkeypatch, "member")
    assert bilgi["yonetici"] is False and bilgi["can_post"] is False
    assert bilgi["tip"] == "channel" and bilgi["baslik"] == "BIST Formasyon"


def test_kanal_yonetici_ve_izinliyse_tamam(monkeypatch, veri_dizini):
    bilgi = _hedef_dogrula(monkeypatch, "administrator", {"can_post_messages": True})
    assert bilgi["yonetici"] is True and bilgi["can_post"] is True


def test_kanal_yonetici_ama_mesaj_izni_kapali(monkeypatch, veri_dizini):
    bilgi = _hedef_dogrula(monkeypatch, "administrator", {"can_post_messages": False})
    assert bilgi["yonetici"] is True and bilgi["can_post"] is False


def test_hedef_yoksa_dogrulama_hata_verir(monkeypatch, veri_dizini):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.delenv("TELEGRAM_GROUP_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    n = notifier_mod.TelegramNotifier()
    bilgi = n.check_public_connection()
    assert bilgi["can_post"] is None and bilgi["hata"]


# --- 6) sessiz arıza bekçisi (tarama üst üste başarısızsa sahibe DM) ---------
# NEDEN: veri kaynağı bozulduğunda süreç ayakta kalır, kanal sessizleşir ve
# sahibin haberi olmaz. Bekçi en fazla günde bir DM gönderir.

class _SahteNotifier:
    def __init__(self):
        self.enabled = True
        self.gonderilen = []

    def send_text(self, metin):
        self.gonderilen.append(metin)
        return True, ""


def _tur_sonucu(status, processed):
    main_mod.last_run_stats = {"status": status, "processed": processed}


def test_basarisiz_turlar_esik_asilinca_uyari_gonderir(monkeypatch):
    monkeypatch.setattr(main_mod, "_ardisik_basarisiz_tur", 0, raising=False)
    monkeypatch.setattr(main_mod, "_son_tarama_uyari_gun", None, raising=False)
    n = _SahteNotifier()
    for _ in range(2):
        _tur_sonucu("basarisiz", 0)
        main_mod._tarama_saglik_kontrolu(n)
    assert n.gonderilen == []          # eşik altı: sessiz
    _tur_sonucu("basarisiz", 0)
    main_mod._tarama_saglik_kontrolu(n)
    assert len(n.gonderilen) == 1      # 3. turda uyarı
    assert "üst üste 3 turdur" in n.gonderilen[0]


def test_uyari_gunde_bir_kez(monkeypatch):
    monkeypatch.setattr(main_mod, "_ardisik_basarisiz_tur", 3, raising=False)
    monkeypatch.setattr(main_mod, "_son_tarama_uyari_gun",
                        main_mod.datetime.now(main_mod.ISTANBUL_TZ).date().isoformat(),
                        raising=False)
    n = _SahteNotifier()
    _tur_sonucu("basarisiz", 0)
    main_mod._tarama_saglik_kontrolu(n)
    assert n.gonderilen == []


def test_basarili_tur_sayaci_sifirlar(monkeypatch):
    monkeypatch.setattr(main_mod, "_ardisik_basarisiz_tur", 5, raising=False)
    n = _SahteNotifier()
    _tur_sonucu("tamamlandi", 28)
    main_mod._tarama_saglik_kontrolu(n)
    assert main_mod._ardisik_basarisiz_tur == 0
    assert n.gonderilen == []


def test_bos_tur_basarisiz_sayilir(monkeypatch):
    """status 'tamamlandi' ama hiç hisse işlenmediyse sağlıklı sayılmaz."""
    monkeypatch.setattr(main_mod, "_ardisik_basarisiz_tur", 0, raising=False)
    n = _SahteNotifier()
    _tur_sonucu("tamamlandi", 0)
    main_mod._tarama_saglik_kontrolu(n)
    assert main_mod._ardisik_basarisiz_tur == 1


def test_dm_kapaliysa_uyari_gondermez(monkeypatch):
    monkeypatch.setattr(main_mod, "_ardisik_basarisiz_tur", 2, raising=False)
    monkeypatch.setattr(main_mod, "_son_tarama_uyari_gun", None, raising=False)
    n = _SahteNotifier()
    n.enabled = False
    _tur_sonucu("basarisiz", 0)
    main_mod._tarama_saglik_kontrolu(n)
    assert n.gonderilen == []
