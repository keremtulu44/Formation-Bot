"""Public grup (Faz 1) testleri — DM'den bağımsız yayın, sade şablon, bütçe, 429.

Bu dosya ağa ÇIKMAZ: `requests` modülü sahte bir modülle değiştirilir.
"""

import json
import sys
import types

import pytest

import karne as K
import notifier as notifier_mod
import telegram_commands as tc


# --- sahte requests ---------------------------------------------------------

class _SahteYanit:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"ok": True}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


class _SahteRequests(types.ModuleType):
    def __init__(self, yanitlar=None):
        super().__init__("requests")
        self.yanitlar = list(yanitlar or [])
        self.cagrilar = []

    def post(self, url, json=None, timeout=None):
        self.cagrilar.append((url, dict(json or {})))
        if self.yanitlar:
            yanit = self.yanitlar.pop(0)
            return yanit if isinstance(yanit, _SahteYanit) else _SahteYanit(**yanit)
        return _SahteYanit(200)


@pytest.fixture
def grup_notifier(monkeypatch):
    """Token + group_id var, DM chat_id YOK: DM'siz public mod."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-1001234567890")
    n = notifier_mod.TelegramNotifier()
    n.public_min_aralik_sn = 0            # testte bekleme yok
    n.retry_bekleme_sn = 0
    return n


def _olay(stock="ISMEN", tf="4h", state="KIRILIM_TEYITLI", q=86, **ek):
    veri = {"stock_name": stock, "timeframe": tf, "pattern_name": "Alçalan Üçgen",
            "state": state, "confidence_score": q, "critical_price_level": 30.75,
            "break_dir": -1, "contraction": 0.8}
    veri.update(ek)
    return veri


# --- 1) DM'den bağımsızlık --------------------------------------------------

def test_public_hedef_dm_olmadan_calisir(monkeypatch, grup_notifier):
    n = grup_notifier
    assert n.enabled is False            # DM yolu kapalı
    assert n.public_enabled is True      # public yol açık
    sahte = _SahteRequests()
    monkeypatch.setitem(sys.modules, "requests", sahte)
    assert n.send_to_public("deneme") is True
    assert len(sahte.cagrilar) == 1
    assert sahte.cagrilar[0][1]["chat_id"] == "-1001234567890"


def test_public_hedef_yoksa_mock_modda_kirilmaz(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_GROUP_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)
    n = notifier_mod.TelegramNotifier()
    assert n.public_enabled is False
    assert n.send_to_public("deneme") is True   # mock: bot çökmez


# --- 2) Kalite eşiği TF bazlı ----------------------------------------------

def test_public_tf_esikleri_dm_ile_ayni(grup_notifier):
    n = grup_notifier
    assert n.should_send_to_public(_olay(tf="1h", q=79)) is False
    assert n.should_send_to_public(_olay(tf="1h", q=80)) is True
    assert n.should_send_to_public(_olay(tf="2h", q=78)) is True
    assert n.should_send_to_public(_olay(tf="4h", q=74)) is False
    assert n.should_send_to_public(_olay(tf="1d", q=70)) is True


def test_public_basarisiz_kirilim_gruba_gitmez(grup_notifier):
    """Politika: ❌ tek tek gruba gitmez; 18:45 özetinde sayı olarak görünür."""
    n = grup_notifier
    assert n.should_send_to_public(_olay(state="BASARISIZ_KIRILIM", q=95)) is False


# --- 3) Bülten: toplama + tekilleştirme ------------------------------------

def test_public_kuyruk_tekillestirir(grup_notifier):
    n = grup_notifier
    assert n.public_kuyruk(_olay()) is True
    assert n.public_kuyruk(_olay()) is False          # aynı hisse/tf/state
    assert len(n._public_kuyruk) == 1


def test_public_bulten_tek_mesajda_birlesir(monkeypatch, grup_notifier):
    n = grup_notifier
    for i, stock in enumerate(["ISMEN", "GARAN", "TTRAK"]):
        assert n.public_kuyruk(_olay(stock=stock, tf="4h" if i != 2 else "1h",
                                     state="FORMASYON_TAMAMLANDI", q=80 + i))
    sahte = _SahteRequests()
    monkeypatch.setitem(sys.modules, "requests", sahte)
    assert n.public_bosalt() == 3
    assert len(sahte.cagrilar) == 1                   # 3 olay -> 1 mesaj
    metin = sahte.cagrilar[0][1]["text"]
    assert "3 gelişme" in metin
    for stock in ("ISMEN", "GARAN", "TTRAK"):
        assert stock in metin
    assert "yatırım tavsiyesi değildir" in metin
    assert n._public_kuyruk == []


def test_public_bulten_ic_notu_tasimaz(grup_notifier):
    metin = grup_notifier.format_public_batch([_olay(state="KIRILIM_TEYITLI")])
    for yasak in ("teyit bekleniyor", "Retest tutarsa", "Diğer izleme adayları"):
        assert yasak not in metin


# --- 4) Bütçe, pacing, 429, kırpma -----------------------------------------

def test_public_saatlik_butce_asilinca_engellenir(monkeypatch, grup_notifier):
    n = grup_notifier
    n.public_max_saatlik = 2
    sahte = _SahteRequests()
    monkeypatch.setitem(sys.modules, "requests", sahte)
    assert n.send_to_public("bir") is True
    assert n.send_to_public("iki") is True
    assert n.send_to_public("üç") is False       # bütçe dolu
    assert n.public_engel == 1
    assert len(sahte.cagrilar) == 2


def test_public_429_retry_after_ile_tekrar_dener(monkeypatch, grup_notifier):
    n = grup_notifier
    sahte = _SahteRequests([
        {"status_code": 429, "payload": {"ok": False, "parameters": {"retry_after": 0}}},
        {"status_code": 200, "payload": {"ok": True}},
    ])
    monkeypatch.setitem(sys.modules, "requests", sahte)
    assert n.send_to_public("deneme") is True
    assert len(sahte.cagrilar) == 2


def test_public_uzun_mesaj_kirpilir(monkeypatch, grup_notifier):
    n = grup_notifier
    sahte = _SahteRequests()
    monkeypatch.setitem(sys.modules, "requests", sahte)
    assert n.send_to_public("x" * 9000) is True
    assert len(sahte.cagrilar[0][1]["text"]) <= 4000


# --- 5) Public kapanış özeti ------------------------------------------------

def test_public_ozet_sade_ve_dogru_satirlar(grup_notifier):
    n = grup_notifier
    aktif = [
        {"stock_name": "ISMEN", "timeframe": "4h", "state": "FORMASYON_TAMAMLANDI",
         "confidence_score": 87},
        {"stock_name": "GARAN", "timeframe": "4h", "state": "FORMASYON_TAMAMLANDI",
         "confidence_score": 86},
        {"stock_name": "TTRAK", "timeframe": "1h", "state": "FORMASYON_TAMAMLANDI",
         "confidence_score": 83},
        {"stock_name": "KCHOL", "timeframe": "4h", "state": "FORMASYON_TAMAMLANDI",
         "confidence_score": 84},
        {"stock_name": "AKSEN", "timeframe": "1d", "state": "RETEST_BASARILI",
         "confidence_score": 85},
        {"stock_name": "GUBRF", "timeframe": "4h", "state": "SIKISMA_GUCLENIYOR",
         "confidence_score": 82, "contraction": 0.81},
    ]
    izleme = [{"stock": f"SYM{i}", "timeframe": "2h", "pattern_name": "Üçgen",
               "quality": 85 - i} for i in range(8)]
    metin = n.format_public_summary(aktif, {"basarisiz_kirilim": 3}, izleme=izleme,
                                    tarama_turu=9)
    assert "Tamamlanan 4 (ilk 3)" in metin
    assert "Retest başarılı 1" in metin
    assert "❌ 3 kırılım başarısız oldu" in metin
    assert "Sıkışan 1" in metin and "GUBRF" in metin
    assert "Yarının izleme listesi (ilk 5)" in metin
    assert metin.count("• SYM") == 5          # listede yalnız ilk 5
    assert "48 hisse × 4 zaman dilimi · 9 tarama" in metin
    # Grup metninde iç teknik döküm olmamalı
    assert "defter" not in metin and "n=" not in metin and "/tmp" not in metin


def test_public_ozet_bossa_bos_mesaj_vermez(grup_notifier):
    metin = grup_notifier.format_public_summary([], {}, tarama_turu=0)
    assert "öne çıkan formasyon olmadı" in metin
    assert "henüz" not in metin or "tarama" in metin


# --- 6) Kısa karne ----------------------------------------------------------

def test_karne_kisa_metni_teknik_dokum_icermez():
    metrik = {"kirilim_toplam": 13, "degerlendirilen": 10, "pozitif": 6,
              "ort_mfe_pct": 0.9, "ort_mae_pct": 1.3,
              "huni": {"FORMASYON_TAMAMLANDI": 45, "RETEST_BASARILI": 12,
                       "BASARISIZ_KIRILIM": 47}}
    metin = K.karne_kisa_metni(metrik, "28.09–02.10.2026")
    assert "Haftalık doğruluk · 28.09–02.10.2026" in metin
    assert "6/10 (%60)" in metin
    assert "Tamamlanan 45 · retest başarılı 12" in metin
    assert "garantisi değildir" in metin
    for yasak in ("defter", "n=", "/tmp", "hedef", "nötr"):
        assert yasak not in metin


# --- 7) Grup sohbetine cevap verme -----------------------------------------

def _grup_guncellemesi(update_id, metin, tip="supergroup", chat_id=-1001234567890):
    return {"update_id": update_id,
            "message": {"message_id": update_id, "date": 1,
                        "chat": {"id": chat_id, "type": tip}, "text": metin}}


def test_grup_sohbetine_bot_cevap_vermez():
    """Admin bot grup mesajlarını görür; komut olmayan metne /yardim BASMAZ."""
    class SahteSession:
        def __init__(self):
            self.post_cagrilari = []

        def post(self, url, json=None, timeout=None):
            self.post_cagrilari.append((url, dict(json or {})))
            return _SahteYanit(200)

    session = SahteSession()
    dinleyici = tc.TelegramCommandListener(
        token="111:AAA", allowed_chat_id="-1001234567890",
        handlers={"durum": lambda _a: "durum"}, help_text="YARDIM", session=session)
    cevap = dinleyici.handle_update(_grup_guncellemesi(1, "selam millet"))
    assert cevap is None
    assert session.post_cagrilari == []


def test_grup_sohbetinde_komut_calisir():
    class SahteSession:
        def __init__(self):
            self.post_cagrilari = []

        def post(self, url, json=None, timeout=None):
            self.post_cagrilari.append((url, dict(json or {})))
            return _SahteYanit(200)

    session = SahteSession()
    dinleyici = tc.TelegramCommandListener(
        token="111:AAA", allowed_chat_id="-1001234567890",
        handlers={"durum": lambda _a: "durum cevabi"}, help_text="YARDIM", session=session)
    cevap = dinleyici.handle_update(_grup_guncellemesi(2, "/durum"))
    assert cevap == "durum cevabi"
    assert len(session.post_cagrilari) == 1
