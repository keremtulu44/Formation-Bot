"""İki yönlü Telegram (komut) ve canlı durum testleri — ağ erişimi GEREKMEZ.

Kapsam:
- `telegram_commands.komut_coz` / `kirp` yardımcıları
- Yetki: yalnızca kayıtlı chat_id komut verebilir
- Bilinmeyen komut, komut olmayan metin, işleyici hatası, hız sınırı
- `getUpdates` onayı (offset ilerler), backlog atlama, 401/409'da durma
- `LiveState` tampon davranışı (tarama sürerken eski liste yayında kalır)
- `main.py` komut işleyicileri: /durum, /formasyonlar (filtre + sınır), /tara
"""

import json
import re
import time

import pytest

import main as main_mod
from live_state import LiveState
from telegram_commands import TelegramCommandListener, kirp, komut_coz

CHAT_ID = "1857000000"


@pytest.fixture(autouse=True)
def _temizle_analiz_istegi():
    main_mod._scan_job_active.clear()
    main_mod._scan_istegi.clear()
    main_mod._scan_job_request = None
    main_mod.last_run_stats.clear()
    yield
    main_mod._scan_job_active.clear()
    main_mod._scan_istegi.clear()
    main_mod._scan_job_request = None
    main_mod.last_run_stats.clear()


class SahteYanit:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("JSON gövde yok")
        return self._payload


class SahteSession:
    """requests.Session yerine: çağrıları kaydeder, sıradaki yanıtı döner."""

    def __init__(self, get_yanitlari=None, post_yanitlari=None):
        self.get_cagrilari = []
        self.post_cagrilari = []
        self._get_yanitlari = list(get_yanitlari or [])
        self._post_yanitlari = list(post_yanitlari or [])

    def get(self, url, params=None, timeout=None):
        self.get_cagrilari.append((url, dict(params or {})))
        if not self._get_yanitlari:
            return SahteYanit(200, {"ok": True, "result": []})
        yanit = self._get_yanitlari.pop(0)
        return yanit if isinstance(yanit, SahteYanit) else SahteYanit(**yanit)

    def post(self, url, json=None, timeout=None):
        self.post_cagrilari.append((url, dict(json or {})))
        if not self._post_yanitlari:
            return SahteYanit(200, {"ok": True, "result": {"message_id": 1}})
        yanit = self._post_yanitlari.pop(0)
        return yanit if isinstance(yanit, SahteYanit) else SahteYanit(**yanit)

    @property
    def gonderilenler(self):
        return [govde.get("text", "") for _, govde in self.post_cagrilari]


def _guncelleme(update_id, metin, chat_id=CHAT_ID, tarih=None):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": int(time.time()) if tarih is None else int(tarih),
            "chat": {"id": int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id, "type": "private"},
            "text": metin,
        },
    }


def _dinleyici(session, handlers=None, help_text="YARDIM METNI"):
    return TelegramCommandListener(
        token="111:AAA",
        allowed_chat_id=CHAT_ID,
        handlers=handlers if handlers is not None else {"durum": lambda _a: "durum cevabi"},
        help_text=help_text,
        session=session,
    )


# --- yardımcılar ---------------------------------------------------------
def test_komut_coz_varyasyonlari():
    assert komut_coz("/formasyonlar") == ("formasyonlar", "")
    assert komut_coz("/formasyonlar 1h") == ("formasyonlar", "1h")
    assert komut_coz("/formasyonlar@bist_bot THYAO") == ("formasyonlar", "THYAO")
    assert komut_coz("  /DURUM  ") == ("durum", "")
    assert komut_coz("merhaba") == ("", "")
    assert komut_coz("") == ("", "")


def test_kirp_mesaj_sinirini_asla_asmaz():
    uzun = "x" * 5000
    kirpilmis = kirp(uzun)
    assert len(kirpilmis) <= 4000
    assert "kesildi" in kirpilmis


# --- yetki ve dağıtım ----------------------------------------------------
def test_yetkisiz_sohbetten_gelen_komut_yok_sayilir():
    session = SahteSession()
    dinleyici = _dinleyici(session)
    sonuc = dinleyici.handle_update(_guncelleme(1, "/durum", chat_id="999999"))
    assert sonuc is None
    assert session.post_cagrilari == []


def test_yardim_komutu_cevap_dondurur():
    session = SahteSession()
    dinleyici = _dinleyici(session, handlers={"yardim": lambda _a: "komut listesi"})
    cevap = dinleyici.handle_update(_guncelleme(1, "/yardim"))
    assert cevap == "komut listesi"
    assert session.gonderilenler == ["komut listesi"]


def test_bilinmeyen_komut_yardim_metni_gonderir():
    session = SahteSession()
    dinleyici = _dinleyici(session)
    cevap = dinleyici.handle_update(_guncelleme(1, "/olmayankomut"))
    assert "Bilinmeyen komut" in cevap
    assert "YARDIM METNI" in cevap


def test_komut_olmayan_metin_yardim_metni_gonderir():
    session = SahteSession()
    dinleyici = _dinleyici(session)
    cevap = dinleyici.handle_update(_guncelleme(1, "selam"))
    assert cevap == "YARDIM METNI"


def test_isleyici_hatasi_kullaniciya_yazilir_ve_dongu_devam_eder():
    def patlayan(_arg):
        raise RuntimeError("hesap hatasi")

    session = SahteSession()
    dinleyici = _dinleyici(session, handlers={"durum": patlayan})
    cevap = dinleyici.handle_update(_guncelleme(1, "/durum"))
    assert "çalıştırılamadı" in cevap
    # Dinleyici ölmedi: sonraki komut yine işlenir (hız sınırı 1 sn'yi beklemeden)
    dinleyici._son_komut_zamani.clear()
    dinleyici.handle_update(_guncelleme(2, "/yardim"))
    assert len(session.post_cagrilari) == 2


def test_ayni_komut_saniyede_bir_kez_islenir():
    session = SahteSession()
    dinleyici = _dinleyici(session)
    assert dinleyici.handle_update(_guncelleme(1, "/durum")) == "durum cevabi"
    assert dinleyici.handle_update(_guncelleme(2, "/durum")) is None
    assert len(session.post_cagrilari) == 1


def test_ayni_update_id_iki_kez_islenmez():
    session = SahteSession()
    dinleyici = _dinleyici(session)
    dinleyici.handle_update(_guncelleme(7, "/durum"))
    dinleyici._son_komut_zamani.clear()
    assert dinleyici.handle_update(_guncelleme(7, "/durum")) is None
    assert len(session.post_cagrilari) == 1


# --- getUpdates akışı ----------------------------------------------------
def test_offset_son_update_id_artı_bir_olur():
    guncellemeler = [_guncelleme(10, "/durum"), _guncelleme(11, "/durum")]
    session = SahteSession(get_yanitlari=[SahteYanit(200, {"ok": True, "result": guncellemeler})])
    dinleyici = _dinleyici(session)
    dinleyici._son_komut_zamani.clear()
    assert dinleyici.poll_once() is None
    assert dinleyici._offset == 12
    # İlk çağrı offset'siz, ikinci çağrı offset'li olur
    dinleyici.poll_once()
    assert session.get_cagrilari[-1][1].get("offset") == 12


def test_bayat_backlog_atlanir_ve_eski_komut_calismaz():
    """Gece uyuyan servis sabah açıldığında dünkü /tara yeniden çalışmamalı."""
    bayat = _guncelleme(42, "/tara", tarih=time.time() - 3 * 3600)
    session = SahteSession(
        get_yanitlari=[
            SahteYanit(200, {"ok": True, "result": [bayat]}),
            SahteYanit(200, {"ok": True, "result": []}),
        ],
    )
    calisti = []
    dinleyici = TelegramCommandListener(
        token="111:AAA", allowed_chat_id=CHAT_ID,
        handlers={"tara": lambda _a: calisti.append(1) or "tarandi"},
        session=session, bayat_bildirim=False,   # sessiz mod: bildirim kapalı
    )
    dinleyici._backlog_atla()
    assert dinleyici._offset == 43
    assert calisti == []
    assert session.post_cagrilari == []


def test_bayat_backlog_bildirimi_gonderilir():
    """Atlanan bayat mesaj SESSİZ kaybolmamalı: kullanıcı nedenini görmeli."""
    bayat = _guncelleme(42, "/tara", tarih=time.time() - 3 * 3600)
    session = SahteSession(
        get_yanitlari=[
            SahteYanit(200, {"ok": True, "result": [bayat]}),
            SahteYanit(200, {"ok": True, "result": []}),
        ],
    )
    dinleyici = _dinleyici(session)
    dinleyici._backlog_atla()
    assert len(session.post_cagrilari) == 1
    assert "uyanık değildi" in session.gonderilenler[0]
    assert dinleyici.durum()["bayat_atlanan"] == 1


def test_gec_gelen_tara_calistirilmaz_ve_neden_soylenir():
    """Bot uykudayken yazılan /tara saatler sonra teslim edilirse çalışmamalı."""
    session = SahteSession()
    calisti = []
    dinleyici = _dinleyici(session, handlers={"tara": lambda _a: calisti.append(1) or "tarandi"})
    cevap = dinleyici.handle_update(_guncelleme(5, "/tara", tarih=time.time() - 2 * 3600))
    assert cevap is not None and "uykudaydı" in cevap
    assert "tekrar gönderin" in cevap
    assert calisti == []
    assert session.post_cagrilari != []      # kullanıcı sessiz kalmaz


def test_gec_gelen_yardim_gecikme_notuyla_yanitlanir():
    """/yardim gibi okuma komutları bot uyanınca da olsa yanıtlanır (kullanıcı cevapsız kalmasın)."""
    session = SahteSession()
    dinleyici = _dinleyici(session, handlers={"yardim": lambda _a: "komut listesi"})
    cevap = dinleyici.handle_update(_guncelleme(6, "/yardim", tarih=time.time() - 90 * 60))
    assert cevap is not None
    assert "uykudaydı" in cevap and "komut listesi" in cevap
    assert dinleyici.durum()["islenen"] == 1


def test_durum_sayaclari_teshis_icerir():
    """`/health` için: mod, sayaçlar ve maskeli yetkisiz sohbet kimliği."""
    session = SahteSession()
    dinleyici = _dinleyici(session, handlers={"durum": lambda _a: "ok"})
    dinleyici.handle_update(_guncelleme(1, "/durum", chat_id="999999"))
    dinleyici.handle_update(_guncelleme(2, "/durum"))
    durum = dinleyici.durum()
    assert durum["yetkisiz_sohbet"] == 1
    assert durum["son_yetkisiz_sohbet"] == "…9999"   # tam kimlik yazılmaz
    assert durum["islenen"] == 1
    assert durum["son_komut"] == "durum"
    assert durum["calisiyor"] is False               # thread başlatılmadı


def test_taze_backlog_korunur():
    """3 dakika önce yazılmış komut kaybolmamalı (yalnızca bayatlar atlanır)."""
    taze = _guncelleme(60, "/durum", tarih=time.time() - 180)
    session = SahteSession(get_yanitlari=[SahteYanit(200, {"ok": True, "result": [taze]})])
    dinleyici = _dinleyici(session)
    dinleyici._backlog_atla()
    assert dinleyici._offset == 60          # komut onaylanmadı, işlenecek


def test_karisik_backlog_ilk_taze_mesajdan_devam_eder():
    bayat = _guncelleme(70, "/tara", tarih=time.time() - 2 * 3600)
    taze = _guncelleme(71, "/durum", tarih=time.time() - 60)
    session = SahteSession(get_yanitlari=[SahteYanit(200, {"ok": True, "result": [bayat, taze]})])
    dinleyici = _dinleyici(session)
    dinleyici._backlog_atla()
    assert dinleyici._offset == 71


def test_401_token_gecersiz_dinleyiciyi_durdurur():
    session = SahteSession(get_yanitlari=[SahteYanit(401, {"ok": False, "description": "Unauthorized"})])
    dinleyici = _dinleyici(session)
    sebep = dinleyici.poll_once()
    assert sebep and "401" in sebep


def test_409_conflict_acikca_soylenir():
    session = SahteSession(get_yanitlari=[SahteYanit(409, {"ok": False, "description": "Conflict"})])
    dinleyici = _dinleyici(session)
    sebep = dinleyici.poll_once()
    assert sebep and "409" in sebep and "başka" in sebep


def test_ag_hatasinda_dinleyici_olmaz_ve_geri_cekilir():
    class PatlayanSession(SahteSession):
        def get(self, url, params=None, timeout=None):
            raise OSError("ağ yok")

    dinleyici = _dinleyici(PatlayanSession())
    assert dinleyici.poll_once() is None  # istisna dışarı sızmaz
    assert dinleyici._backoff > 5.0


# --- LiveState -----------------------------------------------------------
def test_live_state_tarama_surerken_eski_liste_yayinda_kalir():
    durum = LiveState()
    durum.begin_scan()
    durum.record_formation({"stock": "THYAO", "timeframe": "1h", "pattern_name": "Yükselen Üçgen",
                            "quality": 88.0, "state": "SIKISMA_GUCLENIYOR"})
    durum.finish_scan(son_tarama_suresi_dk=1.2, son_tarama_hissesi=48)
    assert len(durum.formations()) == 1
    assert durum.status()["son_tarama_hissesi"] == 48

    durum.begin_scan(manuel=True)
    durum.record_formation({"stock": "GARAN", "timeframe": "1h", "pattern_name": "Bayrak", "quality": 70.0})
    assert [f["stock"] for f in durum.formations()] == ["THYAO"]     # yarım liste görünmez
    assert durum.status()["tarama_suruyor"] is True

    durum.finish_scan()
    assert [f["stock"] for f in durum.formations()] == ["GARAN"]
    assert durum.status()["tarama_suruyor"] is False


def test_live_state_kaliteye_gore_siralar_ve_alarm_isaretler():
    durum = LiveState()
    durum.begin_scan()
    durum.record_formation({"stock": "A", "timeframe": "1h", "quality": 60.0})
    durum.record_formation({"stock": "B", "timeframe": "4h", "quality": 90.0})
    durum.mark_alert_sent("b", "4H")
    durum.finish_scan()
    kayitlar = durum.formations()
    assert [k["stock"] for k in kayitlar] == ["B", "A"]
    assert kayitlar[0]["alert_gonderildi"] is True


def test_live_state_hatali_taramayi_isaretler():
    durum = LiveState()
    durum.begin_scan()
    durum.fail_scan("fetch patladı")
    assert durum.status()["tarama_suruyor"] is False
    assert "fetch" in durum.status()["son_tarama_hatasi"]


# --- main.py komut işleyicileri -----------------------------------------
def _sahte_formasyonlar(durum, adet=3):
    durum.begin_scan()
    for i in range(adet):
        durum.record_formation({
            "stock": f"HISSE{i}", "timeframe": "1h", "pattern_name": "Yükselen Üçgen",
            "quality": 90 - i, "state": "SIKISMA_GUCLENIYOR", "break_dir": 1,
            "upper": 100 + i, "lower": 95 + i, "critical_price": 100 + i,
            "min_quality": 80, "alert_gonderildi": False,
        })
    durum.finish_scan(son_tarama_suresi_dk=1.0, son_tarama_hissesi=48)


def test_formasyonlar_komutu_liste_uretir(monkeypatch):
    durum = LiveState()
    _sahte_formasyonlar(durum, adet=3)
    monkeypatch.setattr(main_mod, "_live_state", durum)
    cevap = main_mod._komut_formasyonlar("")
    assert "CANLI FORMASYONLAR" in cevap
    assert "HISSE0" in cevap and "1h" in cevap
    assert "kalite 90" in cevap


def test_formasyonlar_komutu_bos_listede_yonlendirir(monkeypatch):
    monkeypatch.setattr(main_mod, "_live_state", LiveState())
    cevap = main_mod._komut_formasyonlar("")
    assert "tarama" in cevap.lower()
    cevap2 = main_mod._komut_formasyonlar("THYAO")
    assert "yok" in cevap2.lower()


def test_formasyonlar_komutu_timeframe_filtresi(monkeypatch):
    durum = LiveState()
    durum.begin_scan()
    durum.record_formation({"stock": "A", "timeframe": "1h", "pattern_name": "Üçgen", "quality": 80.0})
    durum.record_formation({"stock": "B", "timeframe": "4h", "pattern_name": "Bayrak", "quality": 81.0})
    durum.finish_scan()
    monkeypatch.setattr(main_mod, "_live_state", durum)
    cevap = main_mod._komut_formasyonlar("4h")
    assert "B" in cevap and "4h" in cevap
    assert "A · 1h" not in cevap


def test_formasyonlar_komutu_15_kayitla_sinirlidir(monkeypatch):
    durum = LiveState()
    _sahte_formasyonlar(durum, adet=20)
    monkeypatch.setattr(main_mod, "_live_state", durum)
    cevap = main_mod._komut_formasyonlar("")
    assert "ve 5 tane daha" in cevap


def test_durum_komutu_ozet_verir(monkeypatch):
    durum = LiveState()
    _sahte_formasyonlar(durum, adet=2)
    monkeypatch.setattr(main_mod, "_live_state", durum)
    cevap = main_mod._komut_durum("")
    assert "Formation-Bot durum" in cevap
    assert main_mod.PROFILE in cevap
    assert "Sonuçtaki formasyon: 2" in cevap


def test_tara_komutu_seans_disi_da_istek_kuyruga_koyar(monkeypatch):
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", ["THYAO", "GARAN"])
    monkeypatch.setattr(main_mod, "_live_state", LiveState())
    cevap = main_mod._komut_tara("")
    assert "Analiz başladı" in cevap
    assert main_mod._scan_istegi.is_set()
    assert main_mod._scan_job_request["hisseler"] == ["THYAO", "GARAN"]


def test_tara_hisse_argumanini_gercekten_kullanir(monkeypatch):
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", ["THYAO", "GARAN"])
    monkeypatch.setattr(main_mod, "_live_state", LiveState())
    cevap = main_mod._komut_tara("THYAO")
    assert "1 hisse × 4 zaman dilimi" in cevap
    assert main_mod._scan_job_request["hisseler"] == ["THYAO"]


def test_tara_bilinmeyen_hisseyi_tarama_baslatmadan_reddeder(monkeypatch):
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", ["THYAO", "GARAN"])
    cevap = main_mod._komut_tara("XYZ")
    assert "hisse bulunamadı" in cevap
    assert not main_mod._scan_istegi.is_set()


def test_tarama_isinde_tum_komutlar_sessizce_yok_sayilir():
    main_mod._scan_job_active.set()
    session = SahteSession()
    dinleyici = TelegramCommandListener(
        token="111:AAA", allowed_chat_id=CHAT_ID,
        handlers={"durum": lambda _a: "durum", "panel": lambda _a: "panel"},
        session=session,
        komutlari_yoksay=lambda: main_mod._scan_job_active.is_set(),
    )
    assert dinleyici.handle_update(_guncelleme(100, "/durum")) is None
    assert dinleyici.handle_update(_guncelleme(101, "/panel")) is None
    assert session.post_cagrilari == []


def test_post_close_saat_istanbul_zamanini_cozer(monkeypatch):
    monkeypatch.setattr(main_mod, "POST_CLOSE_ANALYSIS_TIME", "20:00")
    assert main_mod._parse_post_close_analysis_time().hour == 20
    assert main_mod._parse_post_close_analysis_time().minute == 0


def test_komutlari_gercek_listener_yardim_ile_dogrular():
    """main.py'nin komut tablosu listener ile uyumlu mu (uçtan uca, ağ yok)."""
    session = SahteSession()
    dinleyici = TelegramCommandListener(
        token="111:AAA", allowed_chat_id=CHAT_ID,
        handlers=main_mod.TELEGRAM_KOMUTLARI, help_text=main_mod.KOMUT_YARDIM, session=session,
    )
    cevap = dinleyici.handle_update(_guncelleme(1, "/yardim"))
    assert "/formasyonlar" in cevap and "/tara" in cevap and "/durum" in cevap
    assert json.loads(json.dumps({"text": cevap}))["text"] == cevap  # JSON serileştirilebilir


def test_health_test_ucu_ile_komut_dinleyicisi_ayni_tokeni_paylasir():
    """/test ucu sendMessage, dinleyici getUpdates kullanır: birbirini bozmaz."""
    kaynak = open("telegram_commands.py", encoding="utf-8").read()
    assert "getUpdates" in kaynak and "sendMessage" in kaynak
    assert "setWebhook" not in kaynak  # webhook kurulursa getUpdates 409 alır


# --- /panel komutu (48 hisse x 4 TF slot tablosu) -------------------------
def _panel_doldur(durum, hisseler=None, kayitlar=None):
    """Panel testleri için canlı durum üretir (küçük evren: hızlı ve deterministik)."""
    durum.begin_scan()
    for kayit in (kayitlar or []):
        durum.record_formation(kayit)
    durum.finish_scan(son_tarama_suresi_dk=1.0, son_tarama_hissesi=len(hisseler or []))


def _panel_kayit(stock, tf, state="SIKISMA_GUCLENIYOR", quality=80.0, pattern="Yükselen Üçgen"):
    return {
        "stock": stock, "timeframe": tf, "pattern_name": pattern, "quality": quality,
        "state": state, "break_dir": 1, "upper": 100.0, "lower": 95.0,
        "critical_price": 100.0, "min_quality": 80.0, "alert_gonderildi": False,
    }


def test_panel_komutu_hisse_ve_slot_sayilarini_gosterir(monkeypatch):
    hisseler = ["THYAO", "GARAN", "AKBNK", "EREGL"]
    durum = LiveState()
    _panel_doldur(durum, hisseler, [
        _panel_kayit("THYAO", "1h", "KIRILIM_TEYITLI", 88.0),
        _panel_kayit("GARAN", "4h", "RETEST_BASARILI", 75.0),
    ])
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", hisseler)
    monkeypatch.setattr(main_mod, "_live_state", durum)

    cevap = main_mod._panel_raporu("")
    assert "PANEL" in cevap
    assert "4 hisse x 4 TF" in cevap          # 48 hisse x 4 slot yapısı
    assert "dolu slot 2/16" in cevap          # 4 hisse x 4 TF = 16 slot
    assert "📊 SAYILAR" in cevap
    assert "🚀 kırılım 1" in cevap and "🎯 retest 1" in cevap
    assert "THYAO 1h 88🚀" in cevap           # slot hücresi: TF + kalite + işaret
    assert "2h —" in cevap                    # boş slot görünür kalır
    assert "🔥 TOP 12 ANLAMLI ADAY (puan)" in cevap
    for hisse in hisseler:
        assert hisse in cevap


def test_panel_komutu_top12_kritik_sirasini_uygular(monkeypatch):
    hisseler = ["H00", "H01", "H02"]
    kayitlar = [
        _panel_kayit("H00", "1h", "FORMASYON_TAMAMLANDI", 99.0),
        _panel_kayit("H01", "1h", "KIRILIM_ADAYI", 50.0),
        _panel_kayit("H02", "1h", "RETEST_BASARILI", 70.0),
    ]
    durum = LiveState()
    _panel_doldur(durum, hisseler, kayitlar)
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", hisseler)
    monkeypatch.setattr(main_mod, "_live_state", durum)

    cevap = main_mod._panel_raporu("")
    # Composite puan: kalite %65 + lifecycle durumu + geometrik destek.
    sira = [s for s in cevap.splitlines() if re.match(r"^\s*\d+\)", s)]
    assert "H00" in sira[0] and "Formasyon tamamlandı" in sira[0]
    assert "puan " in sira[0] and "· kritik 100.00" in sira[0]


def test_panel_komutu_top12_ile_sinirlidir(monkeypatch):
    hisseler = [f"H{i:02d}" for i in range(15)]
    durum = LiveState()
    _panel_doldur(durum, hisseler, [
        _panel_kayit(f"H{i:02d}", "1h", "KIRILIM_TEYITLI", 90.0 - i) for i in range(15)
    ])
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", hisseler)
    monkeypatch.setattr(main_mod, "_live_state", durum)

    cevap = main_mod._panel_raporu("")
    assert "(15 kayıt içinden)" in cevap
    numarali = [s for s in cevap.splitlines() if re.match(r"^\s*\d+\)", s)]
    assert len(numarali) == 12                  # TOP 12: fazlası listelenmez


def test_panel_komutu_timeframe_filtresi_kolonlari_daraltir(monkeypatch):
    hisseler = ["THYAO", "GARAN"]
    durum = LiveState()
    _panel_doldur(durum, hisseler, [
        _panel_kayit("THYAO", "1h"),
        _panel_kayit("GARAN", "4h"),
    ])
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", hisseler)
    monkeypatch.setattr(main_mod, "_live_state", durum)

    cevap = main_mod._panel_raporu("4h")
    assert "Filtre: 4h" in cevap
    assert "1/4 TF" in cevap                      # yalnızca 4h kolonu
    assert "GARAN 4h 80⚡" in cevap
    assert "THYAO 4h —" in cevap                  # 1h kaydı 4h filtresinde görünmez
    grid = cevap.split("🗂 SLOTLAR")[1].split("🔥 TOP")[0]
    assert "1h" not in grid                       # yalnızca 4h kolonu çizilir


def test_panel_komutu_hisse_filtresi_satirlari_daraltir(monkeypatch):
    hisseler = ["THYAO", "GARAN", "AKBNK"]
    durum = LiveState()
    _panel_doldur(durum, hisseler, [
        _panel_kayit("THYAO", "1h"),
        _panel_kayit("GARAN", "1h", "KIRILIM_TEYITLI", 85.0),
    ])
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", hisseler)
    monkeypatch.setattr(main_mod, "_live_state", durum)

    cevap = main_mod._panel_raporu("THYAO")
    assert "Filtre: THYAO" in cevap
    assert "1/3 hisse" in cevap
    grid = cevap.split("🗂 SLOTLAR")[1]
    assert "THYAO 1h 80⚡" in grid
    assert "GARAN" not in grid and "AKBNK" not in grid


def test_panel_komutu_bos_evrende_durum_soyler(monkeypatch):
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", ["THYAO", "GARAN"])
    monkeypatch.setattr(main_mod, "_live_state", LiveState())

    cevap = main_mod._panel_raporu("")
    assert "2 hisse x 4 TF" in cevap
    assert "tüm slotlar boş" in cevap
    assert "Henüz başarılı analiz yok" in cevap


def test_panel_komutu_mesaji_telegram_sinirinda_tutar(monkeypatch):
    """48 hisse x 4 TF tamamen dolu + uzun desen adları: mesaj 4096'yı aşmamalı."""
    hisseler = [f"H{i:02d}" for i in range(48)]
    durum = LiveState()
    durum.begin_scan()
    tfs = ["1h", "2h", "4h", "1d"]
    for i, hisse in enumerate(hisseler):
        for j, tf in enumerate(tfs):
            durum.record_formation(_panel_kayit(
                hisse, tf, "KIRILIM_TEYITLI" if (i + j) % 2 == 0 else "SIKISMA_GUCLENIYOR",
                90.0 - (i % 30), pattern="Simetrik Üçgen (genişleyen dipli formasyon)"))
    durum.finish_scan(son_tarama_hissesi=48)
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", hisseler)
    monkeypatch.setattr(main_mod, "_live_state", durum)

    cevap = main_mod._panel_raporu("")
    assert len(cevap) <= 4096
    assert cevap == kirp(cevap)                 # kirp() kesme yapmıyor
    assert "TOP 12 ANLAMLI ADAY" in cevap
    assert "dolu slot 192/192" in cevap


def test_panel_aliasleri_ve_yardim_metni_tutarlidir():
    for alias in ("panel", "p", "genel", "tablo"):
        assert main_mod.TELEGRAM_KOMUTLARI[alias] is main_mod._komut_panel
    assert "/panel" in main_mod.KOMUT_YARDIM
    assert "/canli" in main_mod.KOMUT_YARDIM and "/formasyonlar" in main_mod.KOMUT_YARDIM


def test_final_panel_shows_completed_state_even_while_busy_gate_stays_active(monkeypatch):
    hisseler = ["THYAO"]
    durum = LiveState()
    _panel_doldur(durum, hisseler, [_panel_kayit("THYAO", "1h", quality=82.0)])
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", hisseler)
    monkeypatch.setattr(main_mod, "_live_state", durum)
    main_mod._scan_job_active.set()

    cevap = main_mod._panel_raporu("", tamamlandi=True)
    assert "Analiz sürüyor" not in cevap
    assert "dolu slot 1/4" in cevap


def test_veri_durumu_zamani_ve_yasi_acikca_yazar():
    from datetime import datetime, timedelta

    bar = datetime.now(main_mod.ISTANBUL_TZ) - timedelta(days=2, hours=1)
    cevap = main_mod._veri_durumu_satiri(bar.isoformat(), 3, 4, 1, 2 * 24 * 60 + 60)
    assert "Son tamamlanmış mum:" in cevap
    assert "veri yaşı 2g 1sa" in cevap
    assert "en eski taranan veri yaşı 2g 1sa" in cevap
    assert "başarılı fetch 3/4" in cevap and "fetch hatası 1" in cevap


def test_gun_sonu_analiz_saatini_istanbul_saatiyle_parse_eder(monkeypatch):
    monkeypatch.setattr(main_mod, "POST_CLOSE_ANALYSIS_TIME", "20:15")
    assert main_mod._parse_post_close_analysis_time().strftime("%H:%M") == "20:15"
    monkeypatch.setattr(main_mod, "POST_CLOSE_ANALYSIS_TIME", "gecersiz")
    assert main_mod._parse_post_close_analysis_time().strftime("%H:%M") == "20:00"


def test_panel_aday_puani_normalize_edilmis_0_100_araliginda():
    kayit = {
        "quality": 100, "state": "KIRILIM_TEYITLI",
        "upper_touches": 3, "lower_touches": 3,
        "contraction": 1, "mtf_destek": True,
    }
    assert main_mod._panel_aday_puani(kayit) == 100.0


def test_final_bos_rapor_busy_gate_acik_kalsa_bile_bos_tarama_der():
    durum = LiveState()
    durum.begin_scan(beklenen_hisse=1, scope=["THYAO"])
    durum.finish_scan(son_tarama_hissesi=1, son_tarama_beklenen_hisse=1)
    main_mod._live_state = durum
    main_mod._scan_job_active.set()

    detay = main_mod._komut_formasyonlar("", tamamlandi=True)
    assert "Analiz sürüyor" not in detay
    assert "canlı formasyon bulunmadı" in detay


def test_offsession_cache_fallback_only_respects_explicit_max_age(monkeypatch):
    monkeypatch.setattr(main_mod, "OFFSESSION_CACHE_MAX_AGE_DAYS", 14)
    assert main_mod._cache_verisi_kullanilabilir(24 * 60, False, False)
    assert main_mod._cache_verisi_kullanilabilir(60, False, True)
    assert not main_mod._cache_verisi_kullanilabilir(180, False, True)
    assert not main_mod._cache_verisi_kullanilabilir(15 * 24 * 60, False, False)


def test_unexpected_scan_exception_overwrites_stale_last_run_metrics(monkeypatch):
    durum = LiveState()
    durum.begin_scan()
    durum.record_formation(_panel_kayit("THYAO", "1h", quality=88))
    durum.finish_scan(son_tarama_hissesi=48, son_tarama_beklenen_hisse=48)
    monkeypatch.setattr(main_mod, "_live_state", durum)
    main_mod.last_run_stats.update({"status": "tamamlandi", "requested": 48,
                                    "processed": 48, "data_asof": "old"})

    result = main_mod._analiz_hatasi_kaydi(RuntimeError("provider down"), 2, "test")

    assert result["status"] == "basarisiz"
    assert result["requested"] == 2 and result["processed"] == 0
    assert result["data_asof"] is None
    assert len(durum.formations()) == 1
    assert durum.status()["son_tarama_durumu"] == "basarisiz"


def test_tam_manuel_panel_ayni_kapanisin_otomatik_tarama_sayilmasina_izin_verir():
    assert main_mod._istek_tam_evrende_tamamlandi(
        {"status": "tamamlandi", "requested": 48}, evren_boyutu=48,
    )
    assert not main_mod._istek_tam_evrende_tamamlandi(
        {"status": "basarisiz", "requested": 48}, evren_boyutu=48,
    )
    assert not main_mod._istek_tam_evrende_tamamlandi(
        {"status": "tamamlandi", "requested": 1}, evren_boyutu=48,
    )


def test_durum_basarisiz_deneme_icin_onceki_taze_fetch_sayisini_kullanmaz(monkeypatch):
    durum = LiveState()
    durum.begin_scan()
    durum.finish_scan(
        son_tarama_hissesi=48,
        son_tarama_beklenen_hisse=48,
        son_tarama_taze_veri=48,
        son_tarama_fetch_hatasi=0,
        son_tarama_suresi_dk=10.0,
    )
    durum.begin_scan(scope=["THYAO"], beklenen_hisse=1)
    durum.fail_scan("provider down", hata_hisse=1, islenen_hisse=0,
                     istek_hisse=1, sure_dk=2.0)
    monkeypatch.setattr(main_mod, "_live_state", durum)
    main_mod.last_run_stats.update({
        "status": "basarisiz", "requested": 1, "processed": 0,
        "fresh_fetch": None, "fetch_failures": None, "data_asof": None,
    })

    cevap = main_mod._komut_durum("")
    assert "kapsam: 0/1 hisse, süre: 2.0 dk" in cevap
    assert "başarılı fetch 48/" not in cevap
    assert "fetch hatası 0" not in cevap


def test_filtreli_liste_basarisiz_son_deneme_varsa_eski_kaynagi_belirtir(monkeypatch):
    durum = LiveState()
    durum.begin_scan()
    durum.record_formation(_panel_kayit("THYAO", "1h", "RETEST_BASARILI", 88))
    durum.finish_scan(son_tarama_hissesi=48, son_tarama_beklenen_hisse=48)
    durum.begin_scan(scope=["THYAO"], beklenen_hisse=1)
    durum.fail_scan("fetch failed", hata_hisse=1, islenen_hisse=0, istek_hisse=1)
    monkeypatch.setattr(main_mod, "_live_state", durum)

    assert "önceki başarılı analizdendir" in main_mod._komut_canli("")
    assert "önceki başarılı analizdendir" in main_mod._komut_retest("")


def test_kismi_tarama_bos_sonucu_tam_evrende_bos_gibi_yazilmaz(monkeypatch):
    evren = [f"H{i:02d}" for i in range(48)]
    durum = LiveState()
    durum.begin_scan(scope=["H00"], beklenen_hisse=1)
    durum.finish_scan(son_tarama_hissesi=1, son_tarama_beklenen_hisse=1)
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", evren)
    monkeypatch.setattr(main_mod, "_live_state", durum)

    cevap = main_mod._komut_formasyonlar("")
    assert "1 hisselik kısmi kapsamdaydı" in cevap
    assert "tam evrende formasyon olmadığı sonucu çıkarılamaz" in cevap
    assert "48 hisse ve 4 zaman diliminde uygun canlı formasyon bulunmadı" not in cevap
