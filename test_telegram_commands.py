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
import time

import pytest

import main as main_mod
from live_state import LiveState
from telegram_commands import TelegramCommandListener, kirp, komut_coz

CHAT_ID = "1857000000"


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
    dinleyici = _dinleyici(session, handlers={"tara": lambda _a: calisti.append(1) or "tarandi"})
    dinleyici._backlog_atla()
    assert dinleyici._offset == 43
    assert calisti == []
    assert session.post_cagrilari == []


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
    assert "Canlı formasyon: 2" in cevap


def test_tara_komutu_piyasa_kapaliyken_istek_kuyruklamaz(monkeypatch):
    monkeypatch.setattr(main_mod, "tarama_penceresi_acik_mi", lambda _now: False)
    monkeypatch.setattr(main_mod, "_live_state", LiveState())
    main_mod._scan_istegi.clear()
    cevap = main_mod._komut_tara("")
    assert "kapalı" in cevap.lower()
    assert not main_mod._scan_istegi.is_set()


def test_tara_komutu_piyasa_acikken_istek_olusturur(monkeypatch):
    monkeypatch.setattr(main_mod, "tarama_penceresi_acik_mi", lambda _now: True)
    monkeypatch.setattr(main_mod, "_live_state", LiveState())
    main_mod._scan_istegi.clear()
    cevap = main_mod._komut_tara("")
    # Not: `.lower()` Türkçe "İ" harfini "i̇" yaptığı için düz metin karşılaştırılır.
    assert "Tarama isteği alındı" in cevap
    assert main_mod._scan_istegi.is_set()
    main_mod._scan_istegi.clear()


def test_tara_komutu_tarama_surerken_bekletir(monkeypatch):
    durum = LiveState()
    durum.begin_scan()
    monkeypatch.setattr(main_mod, "tarama_penceresi_acik_mi", lambda _now: True)
    monkeypatch.setattr(main_mod, "_live_state", durum)
    main_mod._scan_istegi.clear()
    cevap = main_mod._komut_tara("")
    assert "sürüyor" in cevap.lower()
    assert not main_mod._scan_istegi.is_set()


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
