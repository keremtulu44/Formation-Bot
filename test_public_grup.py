"""Public grup (Faz 1) testleri — DM'den bağımsız yayın, sade şablon, bütçe, 429.

Bu dosya ağa ÇIKMAZ: `requests` modülü sahte bir modülle değiştirilir.
"""

import json
import sys
import time
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
    """Politika: başarısızlık tek tek gruba ya da public kuyruğa gitmez."""
    n = grup_notifier
    assert n.should_send_to_public(_olay(state="BASARISIZ_KIRILIM", q=95)) is False


def test_public_legacy_completed_queue_entry_is_discarded(monkeypatch, grup_notifier):
    n = grup_notifier
    n.public_states = {"FORMASYON_TAMAMLANDI", "KIRILIM_TEYITLI"}
    n._public_kuyruk.append(_olay(state="FORMASYON_TAMAMLANDI", q=95))
    sahte = _SahteRequests()
    monkeypatch.setitem(sys.modules, "requests", sahte)

    assert n.should_send_to_public(_olay(state="FORMASYON_TAMAMLANDI", q=95)) is False
    assert n.public_bosalt() == 0
    assert n._public_kuyruk == []
    assert sahte.cagrilar == []


# --- 3) Bülten: toplama + tekilleştirme ------------------------------------

def test_public_kuyruk_tekillestirir(grup_notifier):
    n = grup_notifier
    assert n.public_kuyruk(_olay()) is True
    assert n.public_kuyruk(_olay()) is False          # aynı hisse/tf/state
    assert len(n._public_kuyruk) == 1


def test_public_bulten_muhur_aynı_oluşumu_tekrar_gondermez(monkeypatch, grup_notifier):
    n = grup_notifier
    n._public_durum_kaydet = lambda: None
    event = _olay(formation_id="stable-formation-42")
    assert n.public_kuyruk(event) is True
    sahte = _SahteRequests()
    monkeypatch.setitem(sys.modules, "requests", sahte)
    assert n.public_bosalt() == 1

    # Retest state birkaç kapanmış mum boyunca sürebilir; aynı stable formation
    # ikinci bir public bültene alınmaz, fakat yeni oluşum yine alınabilir.
    assert n.public_kuyruk(event) is False
    assert n.public_kuyruk(_olay(formation_id="stable-formation-43")) is True


def test_public_event_muhru_restartta_kalici(monkeypatch, grup_notifier):
    n = grup_notifier
    saved = {}
    monkeypatch.setattr(
        notifier_mod._state_persistence,
        "gunluk_durum_yukle",
        lambda: dict(saved),
    )
    monkeypatch.setattr(
        notifier_mod._state_persistence,
        "gunluk_durum_guncelle",
        lambda updates: saved.update(updates),
    )
    n._public_kuyruk = []
    n._public_alert_markers = {}
    event = _olay(formation_id="persisted-formation-unique")
    assert n.public_kuyruk(event) is True

    sahte = _SahteRequests()
    monkeypatch.setitem(sys.modules, "requests", sahte)
    assert n.public_bosalt() == 1

    restarted = notifier_mod.TelegramNotifier()
    assert restarted._public_alert_markers
    assert restarted.public_kuyruk(event) is False
    assert len(sahte.cagrilar) == 1


def test_public_her_olay_kendi_mesajinda_dm_ile_ayni(monkeypatch, grup_notifier):
    """Kullanıcı kararı (2026-10-22, akşam): "Gelişme olmamalı, DM ile aynı."

    3 olay = 3 mesaj. Hiçbirinde bülten başlığı/sayı/tarih yok; her metin
    DM kartının birebir aynısı (kendi yasal uyarısı dâhil).
    """
    n = grup_notifier
    olaylar = [_olay(stock=stock, tf="4h" if i != 2 else "1h",
                     state="KIRILIM_TEYITLI", q=80 + i)
               for i, stock in enumerate(["ISMEN", "GARAN", "TTRAK"])]
    for olay in olaylar:
        assert n.public_kuyruk(olay)
    sahte = _SahteRequests()
    monkeypatch.setitem(sys.modules, "requests", sahte)
    assert n.public_bosalt() == 3
    assert len(sahte.cagrilar) == 3                   # 3 olay -> 3 mesaj
    for olay, (_url, govde) in zip(olaylar, sahte.cagrilar):
        metin = govde["text"]
        assert metin == notifier_mod._format_lifecycle_alert_kart(olay)
        assert "gelişme" not in metin
        assert "Bülten" not in metin
        assert metin.count("yatırım tavsiyesi değildir") == 1
    assert n._public_kuyruk == []


def test_public_mesaji_ic_notu_tasimaz(grup_notifier):
    metin = grup_notifier.format_public_tekil(_olay(state="KIRILIM_TEYITLI"))
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
        {"stock_name": "ISMEN", "timeframe": "4h", "state": "KIRILIM_TEYITLI",
         "confidence_score": 87},
        {"stock_name": "GARAN", "timeframe": "4h", "state": "KIRILIM_TEYITLI",
         "confidence_score": 86},
        {"stock_name": "TTRAK", "timeframe": "1h", "state": "KIRILIM_TEYITLI",
         "confidence_score": 83},
        {"stock_name": "KCHOL", "timeframe": "4h", "state": "KIRILIM_TEYITLI",
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
    assert "Teyitli kırılım 4" in metin
    assert "Retest başarılı 1" in metin
    assert "Sıkışan 1" in metin and "GUBRF" in metin
    assert "Yarının izleme listesi (ilk 5)" in metin
    assert metin.count("• SYM") == 5          # listede yalnız ilk 5
    # Satır bütçesi (≤283 px) " · " ayracından böler: bilgi aynı, iki kısa satır.
    import config
    assert f"{config.evren_ozeti(ayrinti=False)} × 4 zaman dilimi" in metin and "9 tarama" in metin
    # Grup metninde iç teknik döküm olmamalı
    assert "defter" not in metin and "n=" not in metin and "/tmp" not in metin


def test_public_ozet_bossa_bos_mesaj_vermez(grup_notifier):
    metin = grup_notifier.format_public_summary([], {}, tarama_turu=0)
    assert "öne çıkan formasyon yok" in metin
    assert "henüz" not in metin or "tarama" in metin


# --- 6) Kısa karne ----------------------------------------------------------

def test_karne_kisa_metni_teknik_dokum_icermez():
    metrik = {"kirilim_toplam": 13, "degerlendirilen": 10, "pozitif": 6,
              "ort_mfe_pct": 0.9, "ort_mae_pct": 1.3,
              "huni": {"FORMASYON_TAMAMLANDI": 45, "RETEST_BASARILI": 12,
                       "BASARISIZ_KIRILIM": 47}}
    metin = K.karne_kisa_metni(metrik, "28.09–02.10.2026")
    # Başlık/pencere ve olay sayaçları ayrı satırlarda: birleşik halleri 283 px'lık
    # satır bütçesini aşıp ortadan ikiye düşüyordu. Bilgilerin hepsi duruyor.
    assert "Haftalık doğruluk" in metin and "28.09–02.10.2026" in metin
    assert "6/10 (%60)" in metin
    assert "Tamamlanan 45" in metin and "retest başarılı 12" in metin
    assert "garanti" in metin
    for yasak in ("defter", "n=", "/tmp", "hedef", "nötr"):
        assert yasak not in metin


# --- 7) Grup sohbetine cevap verme -----------------------------------------

def _grup_guncellemesi(update_id, metin, tip="supergroup", chat_id=-1001234567890):
    return {"update_id": update_id,
            # Gerçekçi tarih: `date` istemciden değil Telegram'dan gelir; eski
            # (epoch) bir tarih artık "bot uykudaydı" kuralına takılır.
            "message": {"message_id": update_id, "date": int(time.time()),
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


# --- 8) Sabah notu (09:55) --------------------------------------------------

def test_sabah_notu_kapanis_gibi_konusmaz(grup_notifier):
    n = grup_notifier
    aktif = [
        {"stock_name": "ISMEN", "timeframe": "1h", "state": "SIKISMA_GUCLENIYOR",
         "pattern_name": "Simetrik Üçgen", "confidence_score": 79, "contraction": 0.82},
        {"stock_name": "GARAN", "timeframe": "2h", "state": "KIRILIM_HAZIRLIGI",
         "pattern_name": "Üçgen", "confidence_score": 81},
        {"stock_name": "KCHOL", "timeframe": "4h", "state": "KIRILIM_DENEMESI",
         "pattern_name": "Üçgen", "confidence_score": 77},
        {"stock_name": "AKBNK", "timeframe": "4h", "state": "TeyitBekliyor",
         "confidence_score": 88},
    ]
    metin = n.format_public_summary(aktif, {"basarisiz_kirilim": 3}, kapanis=False)
    assert "sabah notu" in metin
    # Bekleme/hazırlık state'i sabah listesinden ve Telegram özetinden gizli.
    assert "Bugünün izleme listesi" not in metin
    assert "GARAN" not in metin and "KCHOL" not in metin
    # ⚡ Sıkışma satırı kalır, fakat aynı hisse ayrı izleme listesine düşmez.
    assert "⚡ Sıkışan 1: ISMEN 1h" in metin and "• ISMEN" not in metin
    assert "AKBNK" not in metin          # WATCH_STATES dışı -> izleme listesine girmez
    assert "Yarının" not in metin
    assert "kapanış" not in metin
    assert "❌ 3 kırılım" not in metin    # gün yeni başladı, dünün sayısı yazılmaz


# --- 9) Tarama turu sonu: kuyruk boşaltma + tur sayacı ---------------------

def test_tarama_turu_sonunda_bulten_bosaltilir(monkeypatch):
    import main as M

    cagrilar = []

    class SahteNotifier:
        def public_bosalt(self):
            cagrilar.append("bosalt")
            return 2

    eski = M.daily_stats.get("tarama_sayisi")
    try:
        M.daily_stats["tarama_sayisi"] = 8
        M._public_turu_kapat(SahteNotifier())
        assert cagrilar == ["bosalt"]
        assert M.daily_stats["tarama_sayisi"] == 9

        # Bülten hatası taramayı/sayacı bozmaz.
        class Patlayan:
            def public_bosalt(self):
                raise RuntimeError("ağ yok")

        M._public_turu_kapat(Patlayan())
        assert M.daily_stats["tarama_sayisi"] == 10
    finally:
        M.daily_stats["tarama_sayisi"] = eski


# --- 6) Bülten = DM kartıyla aynı 7 blok (2026-10-22) -----------------------

def _zengin_olay(stock="ISMEN", **ek):
    """Kartın 7 bloğunu besleyen tam kayıt (bülten biçimi).

    Bar tarihi koşu gününe göre üretilir; aksi halde gün-içi olayları geçmiş
    günün haberi sayan hikâye/bayatlık kuralı bu "taze olay" fikstürünü haklı
    olarak reddeder ve test takvimden geçen gün sayısına bağlı kırılır.
    Sembol açık parametredir; **ek içindeki "stock" anahtarı kayıt alan adı
    ("stock_name") olmadığı için sessizce yutulur ve farklı hisse sanılan
    olaylar aynı hikâyeye düşerdi.
    """
    from datetime import datetime

    from config import ISTANBUL_TZ

    bugun = datetime.now(ISTANBUL_TZ).date().isoformat()
    veri = _olay(stock, break_dir=1, critical_price_level=39.26,
                 confidence_score=81, break_strength=100, age_bars=94,
                 band_baslangic="2026-09-30T16:30:00+03:00", retest_seen=False,
                 mtf_destek=True, upper_now=39.96,
                 bar_time=f"{bugun}T13:30:00+03:00",
                 bar_kapanis=f"{bugun}T17:30:00+03:00",
                 candle_close_price=39.60,
                 domain_bolumleri={
                     "engel": ["▲ direnç · boşluk 4s 41,90 +%5,8"],
                     "yapi_ozet": ["◈ 4s yön yukarı (iç ve dış yapı)"],
                     "hacim": ["hacim 4s hacim 0,45 kat"],
                     "olcum": ["◇ benzer 32.321 kurulum",
                               "   %76'sı devam etti",
                               "◇ tutarsa tepe ~1,05 TL (+%2,6)",
                               "◇ rol uyumlu %80 · 15724"],
                 },
                 domain_karsi=["iç yapı aşağı döndü"])
    veri.update(ek)
    return veri


def test_public_mesaji_dm_kartiyla_ayni_yedi_blok(grup_notifier):
    kayit = _zengin_olay()
    metin = grup_notifier.format_public_tekil(kayit)
    assert metin == notifier_mod._format_lifecycle_alert_kart(kayit)
    # 7 blok: OLAY / ÖNÜNDE / YAPI / ÖLÇÜ / KATILIM / SINIR / CTA
    assert "Alçalan Üçgen — kapanış onaylı" in metin         # 1 OLAY
    assert "▲ direnç · boşluk 4s 41,90 +%5,8" in metin      # 2 ÖNÜNDE
    assert "◈ 4s yön yukarı (iç ve dış yapı)" in metin       # 3 YAPI
    assert "◇ benzer 32.321 kurulum" in metin                # 4 ÖLÇÜ
    assert "%76'sı devam etti" in metin
    assert "hacim 4s hacim 0,45 kat" in metin             # 5 KATILIM
    assert "olumsuz: iç yapı aşağı döndü" in metin           # 6 SINIR
    assert "· teyit düşer: bant 39,96 altı" in metin
    assert "yatırım tavsiyesi değildir" in metin            # 7 CTA


def test_public_olcu_satirlari_dm_ile_ayni_uclu(grup_notifier):
    """Eski kural (public 2 ölçü) kalktı: metin DM'in aynısı → 3 ölçü.

    Kullanıcı kararı (2026-10-22, akşam) *"DM ile aynı olmalı"*: iki kip
    tutmak "aynı" iddiasını sessizce bozuyordu.
    """
    kayit = _zengin_olay()
    metin = grup_notifier.format_public_tekil(kayit)
    # Ölçü bloğu artık "başlık + girintili detay + hareket": üç satırın
    # tamamı sayılır (2026-10-23 sade dil düzeni).
    eşleşme = ("◇", "   ")
    olcum = [s for s in metin.splitlines() if s.startswith(eşleşme)]
    assert len(olcum) == 3, olcum
    assert olcum == [s for s in
                     notifier_mod._format_lifecycle_alert_kart(kayit).splitlines()
                     if s.startswith(eşleşme)]


def test_public_uyari_her_mesajda_bir_kez(grup_notifier):
    """Tek mesaj = tek kart: uyarı her mesajda tam BİR kez (DM ile aynı)."""
    for kayit in (_zengin_olay(), _zengin_olay(stock="GARAN")):
        metin = grup_notifier.format_public_tekil(kayit)
        assert metin.count("yatırım tavsiyesi değildir") == 1


def test_public_mesaji_jargon_tasimaz(grup_notifier):
    metin = grup_notifier.format_public_tekil(_zengin_olay())
    for kisa in ("RVOL", "FVG", "BOS", "CHoCH", "ATR"):
        assert kisa not in metin, (kisa, metin)


# --- 7) Public kuyruk kart bağlamını taşır ----------------------------------

def test_public_kuyruk_kart_baglamini_saklar(grup_notifier):
    n = grup_notifier
    veri = _zengin_olay()
    assert n.public_kuyruk(veri) is True
    kayit = n._public_kuyruk[0]
    assert kayit["domain_bolumleri"]["olcum"], kayit
    assert len(kayit["domain_bolumleri"]["olcum"]) <= 3       # DM kartı sınırı
    assert kayit["domain_karsi"] == ["iç yapı aşağı döndü"]
    # Zaman damgası JSON'a yazılabilir metin olmalı (kuyruk diske yazılır).
    assert isinstance(kayit["bar_time"], str)


def test_public_kuyruk_json_serilestirilebilir(grup_notifier):
    import json as _json
    n = grup_notifier
    assert n.public_kuyruk(_zengin_olay()) is True
    _json.dumps(n._public_kuyruk)          # patlarsa kuyruk diske yazılamaz


# --- 8) Public görsel: 1 kare + üst TF --------------------------------------

def test_public_grafik_bir_kare_arti_ust_tf(monkeypatch, grup_notifier, tmp_path):
    """2 kare TEK albüm gider: ayrı `sendPhoto`'ları Telegram birleştirmez."""
    import transport.telegram as tt

    n = grup_notifier
    yollar = []
    for ad in ("alarm.png", "ust.png"):
        yol = tmp_path / ad
        yol.write_bytes(b"png")
        yollar.append(str(yol))
    albumler, fotolar = [], []

    def sahte_album(yollar_arg, captions=None, chat_id=None, **kw):
        albumler.append({"yollar": list(yollar_arg), "captions": list(captions or []),
                         "chat_id": chat_id})
        return True, "ok"

    def sahte_foto(yol, chat_id=None, token=None, notifier=None, caption="", **kw):
        fotolar.append({"yol": yol, "chat_id": chat_id, "caption": caption})
        return True, "ok"

    monkeypatch.setattr(tt, "medya_grubu_gonder", sahte_album)
    monkeypatch.setattr(tt, "foto_gonder", sahte_foto)
    kayit = _zengin_olay()
    n._public_grafik[str((("ISMEN", "4h", "KIRILIM_TEYITLI")))] = {
        "goruntular": [{"tf": "4h", "goruntu": {"yol": yollar[0]}},
                       {"tf": "1d", "goruntu": {"yol": yollar[1]}}]}
    assert n.public_grafik_gonder(kayit) == 2
    assert len(albumler) == 1 and fotolar == []     # sendPhoto YOK, tek albüm
    assert albumler[0]["yollar"] == yollar          # sıra: olay TF'si, üst TF
    assert albumler[0]["chat_id"] == "-1001234567890"
    assert "üst zaman dilimi" in albumler[0]["captions"][1]
    assert n.public_grafik_gonderilen == 2
    # Dosyalar gönderimden sonra silinir (disk çöpü kalmaz).
    import os
    assert not any(os.path.exists(y) for y in yollar)
    # Defter boşaldı: aynı olay ikinci kez kare göndermez.
    assert n.public_grafik_gonder(kayit) == 0


def test_public_grafik_kareler_diskten_uretilir(monkeypatch, grup_notifier, tmp_path):
    """Regresyon: `kare_listesi()` yol üretmez; public kareyi KENDİ çizmeli.

    Eski kod `kare["goruntu"]["yol"]` arıyordu; alan hiç dolmadığı için grupta
    tek bir görüntü bile çıkmıyordu (sayaç 0, hata yok — sessiz kayıp).
    """
    import grafik
    import transport.telegram as tt

    n = grup_notifier
    yollar = []
    cizilen = []

    def sahte_kareyi_yaz(goruntu, tf, **kw):
        cizilen.append(tf)
        yol = tmp_path / f"{tf}.png"
        yol.write_bytes(b"\x89PNG")
        yollar.append(str(yol))
        return str(yol), {"tf": tf}

    albumler = []

    def sahte_album(yollar_arg, captions=None, chat_id=None, **kw):
        albumler.append({"yollar": list(yollar_arg), "captions": list(captions or []),
                         "chat_id": chat_id,
                         "var": [__import__("os").path.exists(y) for y in yollar_arg],
                         # Albüm çağrısı ANINDA iki kare de çizilmiş olmalı:
                         # çiz-gönder-çiz-gönder sırası albümü imkânsız yapar.
                         "cizilen": list(cizilen)})
        return True, "ok"

    monkeypatch.setattr(grafik, "kareyi_yaz", sahte_kareyi_yaz)
    monkeypatch.setattr(tt, "medya_grubu_gonder", sahte_album)
    monkeypatch.setattr(tt, "foto_gonder",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("sendPhoto yok")))

    kayit = _zengin_olay(formation_id="frm-1")
    n._public_grafik[n._public_kuyruk_anahtari(kayit)] = {
        "sembol": "ISMEN",
        "goruntular": [{"tf": "4h", "goruntu": {"sembol": "ISMEN"}},
                       {"tf": "1d", "goruntu": {"sembol": "ISMEN"}}],
    }
    assert n.public_grafik_gonder(kayit) == 2
    assert cizilen == ["4h", "1d"]                 # kareler gerçekten çizildi
    assert len(albumler) == 1
    assert albumler[0]["cizilen"] == ["4h", "1d"]  # önce İKİ çizim, sonra gönderim
    assert albumler[0]["yollar"] == yollar
    assert all(albumler[0]["var"])                 # gönderim ANINDA dosyalar vardı
    assert albumler[0]["chat_id"] == "-1001234567890"
    assert "üst zaman dilimi" in albumler[0]["captions"][1]
    assert n.public_grafik_gonderilen == 2
    assert n.public_grafik_hatasi == 0
    import os
    assert not any(os.path.exists(y) for y in yollar)   # /tmp'de çöp kalmaz


def test_public_grafik_cizilemeyen_kare_sessiz_kaybolmaz(monkeypatch, grup_notifier):
    """Çizim başarısızsa metin akışı sürer, sayaç artar (sessiz kayıp yok)."""
    import grafik
    import transport.telegram as tt

    n = grup_notifier
    monkeypatch.setattr(grafik, "kareyi_yaz", lambda goruntu, tf, **kw: (None, {}))
    cagrilar = []
    monkeypatch.setattr(tt, "foto_gonder",
                        lambda *a, **k: cagrilar.append(a) or (True, "ok"))

    kayit = _zengin_olay(formation_id="frm-2")
    n._public_grafik[n._public_kuyruk_anahtari(kayit)] = {
        "goruntular": [{"tf": "4h", "goruntu": {"sembol": "ISMEN"}}]}
    assert n.public_grafik_gonder(kayit) == 0
    assert cagrilar == []
    assert n.public_grafik_hatasi == 1
    assert n.grafik_atlanan_hata >= 1


def test_public_grafik_gercek_tasimayla_tek_sendmediagroup(
        monkeypatch, grup_notifier, tmp_path):
    """Uçtan uca: public 2 kare = TEK `sendMediaGroup` HTTP çağrısı.

    Diğer testler taşıma fonksiyonunu sahteyle değiştirir; bu test yalnız en
    alttaki multipart çağrıyı kaydeder, yani Telegram'a gidecek metod adını ve
    gövdeyi birebir görür. İki ayrı `sendPhoto` asla albüm olmaz; kanıt budur.
    """
    import transport.telegram as tt

    n = grup_notifier
    yollar = []
    for ad in ("olay.png", "ust.png"):
        yol = tmp_path / ad
        yol.write_bytes(b"\x89PNG" + ad.encode())
        yollar.append(str(yol))
    cagrilar = []

    class Yanit:
        status_code = 200

        def json(self):
            return {"ok": True, "description": ""}

    def sahte_multipart(method, token, alanlar, dosyalar, timeout=20):
        cagrilar.append({"method": method, "alanlar": dict(alanlar),
                         "dosyalar": sorted(dosyalar)})
        return Yanit()

    monkeypatch.setattr(tt, "_multipart_cagri", sahte_multipart)
    kayit = _zengin_olay(formation_id="frm-http")
    n._public_grafik[n._public_kuyruk_anahtari(kayit)] = {
        "goruntular": [{"tf": "4h", "goruntu": {"yol": yollar[0]}},
                       {"tf": "1d", "goruntu": {"yol": yollar[1]}}]}
    assert n.public_grafik_gonder(kayit) == 2
    assert [c["method"] for c in cagrilar] == ["sendMediaGroup"]
    assert cagrilar[0]["alanlar"]["chat_id"] == "-1001234567890"
    medya = json.loads(cagrilar[0]["alanlar"]["media"])
    assert [m["media"] for m in medya] == ["attach://photo0", "attach://photo1"]
    assert "üst zaman dilimi" in medya[1]["caption"]
    assert cagrilar[0]["dosyalar"] == ["photo0", "photo1"]
    import os
    assert not any(os.path.exists(y) for y in yollar)


def test_public_grafik_album_reddedilince_kare_kare_dener(
        monkeypatch, grup_notifier, tmp_path):
    """Albüm reddi kare kaybına dönüşmez (DM `grafik_toplu_gonder` ile aynı)."""
    import transport.telegram as tt

    n = grup_notifier
    yollar = []
    for ad in ("a.png", "b.png"):
        yol = tmp_path / ad
        yol.write_bytes(b"png")
        yollar.append(str(yol))
    cagrilar = []
    monkeypatch.setattr(tt, "medya_grubu_gonder",
                        lambda *a, **k: (False, "reddedildi"))

    def sahte_foto(yol, chat_id=None, token=None, notifier=None, caption="", **kw):
        cagrilar.append({"yol": yol, "chat_id": chat_id, "caption": caption})
        return True, "ok"

    monkeypatch.setattr(tt, "foto_gonder", sahte_foto)
    kayit = _zengin_olay(formation_id="frm-album-red")
    n._public_grafik[n._public_kuyruk_anahtari(kayit)] = {
        "goruntular": [{"tf": "4h", "goruntu": {"yol": yollar[0]}},
                       {"tf": "1d", "goruntu": {"yol": yollar[1]}}]}
    assert n.public_grafik_gonder(kayit) == 2
    assert [c["yol"] for c in cagrilar] == yollar
    assert all(c["chat_id"] == "-1001234567890" for c in cagrilar)
    assert n.public_grafik_gonderilen == 2
    import os
    assert not any(os.path.exists(y) for y in yollar)


def test_public_grafik_tek_kare_sendphoto(monkeypatch, grup_notifier, tmp_path):
    """Üst TF yoksa (örn. 1g olay) albüm kurulamaz: tek kare `sendPhoto`."""
    import transport.telegram as tt

    n = grup_notifier
    yol = tmp_path / "tek.png"
    yol.write_bytes(b"png")
    albumler, fotolar = [], []
    monkeypatch.setattr(tt, "medya_grubu_gonder",
                        lambda *a, **k: albumler.append(a) or (True, "ok"))
    monkeypatch.setattr(
        tt, "foto_gonder",
        lambda yol_arg, chat_id=None, **k: fotolar.append(
            {"yol": yol_arg, "chat_id": chat_id}) or (True, "ok"))

    kayit = _zengin_olay(tf="1d", formation_id="frm-tek")
    n._public_grafik[n._public_kuyruk_anahtari(kayit)] = {
        "goruntular": [{"tf": "1d", "goruntu": {"yol": str(yol)}}]}
    assert n.public_grafik_gonder(kayit) == 1
    assert albumler == []
    assert len(fotolar) == 1 and fotolar[0]["chat_id"] == "-1001234567890"
    import os
    assert not os.path.exists(yol)


def test_public_grafik_biri_cizilemezse_kalan_tek_gider(
        monkeypatch, grup_notifier, tmp_path):
    """Üst TF çizilemezse albüme zorlanmaz; kalan kare tek gider, hata sayılır."""
    import grafik
    import transport.telegram as tt

    n = grup_notifier

    def sahte_kareyi_yaz(goruntu, tf, **kw):
        if tf == "1d":
            return None, {}
        yol = tmp_path / f"{tf}.png"
        yol.write_bytes(b"\x89PNG")
        return str(yol), {"tf": tf}

    albumler, fotolar = [], []
    monkeypatch.setattr(grafik, "kareyi_yaz", sahte_kareyi_yaz)
    monkeypatch.setattr(tt, "medya_grubu_gonder",
                        lambda *a, **k: albumler.append(a) or (True, "ok"))
    monkeypatch.setattr(
        tt, "foto_gonder",
        lambda yol_arg, **k: fotolar.append(yol_arg) or (True, "ok"))

    kayit = _zengin_olay(formation_id="frm-yarim")
    n._public_grafik[n._public_kuyruk_anahtari(kayit)] = {
        "goruntular": [{"tf": "4h", "goruntu": {"sembol": "ISMEN"}},
                       {"tf": "1d", "goruntu": {"sembol": "ISMEN"}}]}
    assert n.public_grafik_gonder(kayit) == 1
    assert albumler == [] and len(fotolar) == 1
    assert n.public_grafik_gonderilen == 1
    assert n.public_grafik_hatasi == 1          # çizilemeyen üst TF sessiz değil
    import os
    assert not os.path.exists(fotolar[0])


def test_public_kuyruk_kare_defteri_anahtari_ayni(monkeypatch, grup_notifier):
    """Kuyruğa yazılan anahtar ile gönderimde aranan anahtar AYNI olmalı."""
    n = grup_notifier
    kayit = _zengin_olay(formation_id="frm-3")
    kayit["grafik_verisi_public"] = {
        "goruntular": [{"tf": "4h", "goruntu": {"sembol": "ISMEN"}}]}
    assert n.public_kuyruk(kayit) is True
    anahtar = n._public_kuyruk_anahtari(kayit)
    assert anahtar in n._public_grafik
    assert anahtar == "ISMEN|4h|KIRILIM_TEYITLI|frm-3"
    # Kare verisi payload'da KALMAZ: DM teslim kuyruğu aynı sözlüğü diske yazar.
    assert "grafik_verisi_public" not in kayit
    # Kuyruktan düşen kaydın kare verisi bellekte kalmaz.
    n._public_kuyruk = []
    n._public_grafik_buda()
    assert n._public_grafik == {}


def test_public_aralik_varsayilani_iki_saniye():
    """Bülten + kare art arda gidiyor; 1,2 sn grup hız sınırında 429 üretiyordu."""
    import config
    assert config.PUBLIC_MIN_ARALIK_SN >= 2.0


# --- 9) Kuyruk: olay başına mesaj, engelde kayıt bekler ---------------------

def test_kuyruk_bosaltmada_her_olay_tek_mesaj(grup_notifier, monkeypatch):
    """5 olay → 5 mesaj; hepsi DM kartının aynısı, hiçbiri kuyrukta kalmaz."""
    n = grup_notifier
    kayitlar = [_zengin_olay(stock=f"SEM{i:02d}", formation_id=f"f{i}")
                for i in range(5)]
    for kayit in kayitlar:
        assert n.public_kuyruk(kayit)
    gonderilenler = []
    monkeypatch.setattr(n, "send_to_public",
                        lambda metin, deneme=1: gonderilenler.append(metin) or True)
    monkeypatch.setattr(n, "public_grafik_gonder", lambda kayit: 0)
    assert n.public_bosalt(azami=12) == 5
    assert len(gonderilenler) == 5                 # bülten yok: olay = mesaj
    assert n._public_kuyruk == []                  # hiçbir olay kaybolmadı
    for kayit, metin in zip(kayitlar, gonderilenler):
        assert metin == notifier_mod._format_lifecycle_alert_kart(kayit)
        assert len(metin) <= 4096


def test_gonderim_engellenirse_kayitlar_kuyrukta_kalir(grup_notifier, monkeypatch):
    """Bütçe/ağ engeli olayı düşürmez: kuyrukta kalır, sonraki tur dener."""
    n = grup_notifier
    for i in range(3):
        assert n.public_kuyruk(_zengin_olay(stock=f"SEM{i}", formation_id=f"e{i}"))
    denemeler = []

    def engelli(metin, deneme=1):
        denemeler.append(metin)
        return False                                # bütçe dolu

    monkeypatch.setattr(n, "send_to_public", engelli)
    monkeypatch.setattr(n, "public_grafik_gonder", lambda kayit: 0)
    assert n.public_bosalt() == 0
    assert len(denemeler) == 1                      # ilk engelde tur biter
    assert len(n._public_kuyruk) == 3               # hiçbiri düşmedi
    # Engel kalkınca hepsi sırayla gider.
    gonderilenler = []
    monkeypatch.setattr(n, "send_to_public",
                        lambda metin, deneme=1: gonderilenler.append(metin) or True)
    assert n.public_bosalt() == 3
    assert n._public_kuyruk == [] and len(gonderilenler) == 3


# --- 9) Public yapı bloğu: alarm TF'si yoksa üst TF ------------------------

def test_public_mesaji_ust_tf_yapisini_basabilir(grup_notifier):
    """Alarm TF'sinde MS olayı yoksa mesaj yapı bloğunu üst TF'den okur.

    Kullanıcı sorusu (2026-10-22): "public'te gerekiyorsa üst TF MS sorununu
    çözdün mü" — bu test o yedeğin bülten metnine gerçekten ulaştığını
    doğrular (yalnız `domain_bolumleri` birim testi yetmez).
    """
    from types import SimpleNamespace
    import notification_context as nc

    def _ms(dis, ic):
        return SimpleNamespace(
            external_scope=SimpleNamespace(state=dis),
            internal_scope=SimpleNamespace(state=ic),
            events=[], external_protected_high=None, external_protected_low=None,
            external_weak_high=None, external_weak_low=None,
        )

    outputs = {
        "1h": {"market_structure": SimpleNamespace(skipped=True, export=None, error=None)},
        "4h": {"market_structure": SimpleNamespace(export=_ms("STATE_BEARISH",
                                                              "STATE_BEARISH"),
                                                   skipped=False, error=None)},
    }
    bolumler = nc.domain_bolumleri(outputs, 39.60, stil="kart", alarm_tf="1h")
    metin = grup_notifier.format_public_tekil(
        _olay(tf="1h", domain_bolumleri=bolumler))
    assert "◈ 4s yön aşağı (iç ve dış yapı)" in metin
    # Kural: satır kendi TF'siyle yazılır — alarm TF'si gibi etiketlenmez.
    assert "◈ 1s yapı" not in metin


# --- 10) Public DM kapılarından bağımsız: mühür "tekrar" dese de -----------

def test_dm_muhru_tekrar_dediyse_public_yine_de_alir(monkeypatch, grup_notifier):
    """DM mührü olayı ikinci kez göndermezken public boşluğu doldurur.

    Eskiden public kuyruğu `before_send` içinde doluyordu; mühür "tekrar"
    dediğinde `before_send` hiç çalışmıyordu → gruba hiç gitmemiş olay (ağ
    hatası, bülten bütçesi, restart) bir daha denenmiyordu.
    """
    n = grup_notifier
    monkeypatch.setattr(n, "_public_durum_kaydet", lambda: None)
    monkeypatch.setattr(n, "can_send", lambda *a, **k: (
        setattr(n, "_son_engel", "tekrar") or False))

    baglam = []

    def before_send(data):
        baglam.append(1)
        n.public_kuyruk(data)

    olay = _olay(formation_id="stable-public-tekrar")
    assert n.send_with_prepare(dict(olay), before_send=before_send) is False
    assert baglam == [1]                     # bağlam hazırlandı
    assert len(n._public_kuyruk) == 1        # olay public kuyruğa girdi

    # Public'te kayıt artık VAR: motor ikinci kez koşmaz (bedel ödenmez).
    assert n.send_with_prepare(dict(olay), before_send=before_send) is False
    assert baglam == [1]
    assert len(n._public_kuyruk) == 1


def test_tekrar_public_kapaliyken_motor_calistirmaz(monkeypatch, grup_notifier):
    n = grup_notifier
    n.public_enabled = False
    monkeypatch.setattr(n, "can_send", lambda *a, **k: (
        setattr(n, "_son_engel", "tekrar") or False))
    baglam = []
    n.send_with_prepare(dict(_olay(formation_id="x1")),
                        before_send=lambda d: baglam.append(1))
    assert baglam == []


def test_dm_gecersizlesme_kapisi_publici_durdurmaz():
    """Tur 2a kapısı yalnız DM push'unu durdurur; bağlam/public çalışır.

    Yapısal güvence: `dm_gecersiz_engel` dalı `_attach_domain_context(alert_data)`
    çağırır — yani kart bağlamı ve public kuyruğu DM kapısına takılmaz.
    2026-10-26: devamlılık musluğu (`dm_dev_engel`) de AYNI yola bağlandı;
    sözleşme iki bilinçli DM kapısını da kapsar (yalnız DM durur, public akar).
    """
    import ast
    from pathlib import Path

    # 2026-10-26 modülerleştirme: tarama hattı bot/scan.py'de; yapısal güvence
    # main + bot kaynaklarının birleşiminde aranır (taşımaya dayanıklı).
    kok = Path(__file__).parent
    kaynak = "\n".join(
        [ (kok / "main.py").read_text(encoding="utf-8") ]
        + [p.read_text(encoding="utf-8") for p in sorted((kok / "bot").glob("*.py"))]
    )
    agac = ast.parse(kaynak)

    def _cagri_adi(dugum):
        return getattr(dugum.func, "id", getattr(dugum.func, "attr", ""))

    def _kapilari(dugum):
        """Koşulun içinde geçen DM kapısı adları (`x` ya da `x or y`)."""
        if isinstance(dugum, ast.Name):
            return {dugum.id}
        if isinstance(dugum, ast.BoolOp):
            adlar = set()
            for d in dugum.values:
                adlar |= _kapilari(d)
            return adlar
        return set()

    bulundu = []
    for dugum in ast.walk(agac):
        if not isinstance(dugum, ast.If):
            continue
        if not (_kapilari(dugum.test) & {"dm_gecersiz_engel", "dm_dev_engel"}):
            continue
        adlar = [_cagri_adi(c) for c in ast.walk(dugum) if isinstance(c, ast.Call)]
        bulundu.append(adlar)
    assert bulundu, "DM kapısı dalı yok (kapı geri ayrı elif'e taşınmış olabilir)"
    assert any("_attach_domain_context" in adlar for adlar in bulundu), bulundu


# --- 11) Geri alma kalite kapısına takılmaz --------------------------------

def test_public_gecersizlesme_kalite_esigi_altinda_da_gider(grup_notifier):
    """Teyit eşiği geçmiş olayın iptali kalite düşünce bastırılmamalı.

    Aksi hâlde grup, formasyon kalitesi 80'in altına indiği için "geçersizleşti"
    mesajını hiç görmez ve sinyal sonsuza kadar geçerli sanılır.
    """
    n = grup_notifier
    teyit = _olay(tf="1h", q=85, state="KIRILIM_TEYITLI")
    iptal = _olay(tf="1h", q=62, state="KIRILIM_GECERSIZLESTI")
    assert n.should_send_to_public(teyit) is True
    assert n.should_send_to_public(iptal) is True
    # Kapı yalnız YENİ iddialar için: aynı düşük kalite teyit kaydı girmez.
    assert n.should_send_to_public(_olay(tf="1h", q=62, state="KIRILIM_TEYITLI")) is False
    # Env ile state tamamen kapatılmışsa geri alma da gitmez (kullanıcı kararı).
    n.public_states = {"KIRILIM_TEYITLI"}
    assert n.should_send_to_public(iptal) is False


def test_dm_gecersizlesme_kalite_esigine_takilmaz():
    """`main` kalite kapısı geri alma için atlanır (kaynak düzeyi güvence)."""
    import ast
    from pathlib import Path

    kok = Path(__file__).parent
    kaynak = "\n".join(
        [ (kok / "main.py").read_text(encoding="utf-8") ]
        + [p.read_text(encoding="utf-8") for p in sorted((kok / "bot").glob("*.py"))]
    )
    agac = ast.parse(kaynak)
    bulundu = []
    for dugum in ast.walk(agac):
        if not isinstance(dugum, ast.If):
            continue
        for alt in ast.walk(dugum.test):
            if (isinstance(alt, ast.Compare)
                    and getattr(alt.left, "id", "") == "q"
                    and any(getattr(d, "id", "") == "min_q" for d in alt.comparators)):
                kaynak_test = ast.unparse(dugum.test)
                bulundu.append(kaynak_test)
    assert bulundu, "kalite kapısı bulunamadı (yeniden adlandırılmış olabilir)"
    assert any("KIRILIM_GECERSIZLESTI" in t for t in bulundu), bulundu


# --- 12) Geçersizleşme kapısı: kuyrukta bekleyen teyit --------------------

def test_bekleyen_teyit_varsa_ikisi_birlikte_duser(grup_notifier):
    """Teyit henüz gruba gitmediyse geri alma da gitmez — ikisi birden düşer.

    Eski davranış yalnız GÖNDERİLMİŞ mühürlere bakıyordu: ağ/bütçe hatası
    yüzünden kuyrukta bekleyen teyit sonradan gidiyor, geri alma ise kalıcı
    olarak kayboluyordu → grupta yanlış "geçerli" sinyal.
    """
    n = grup_notifier
    n._public_kuyruk = []
    n._public_alert_markers = {}
    teyit = _olay(formation_id="stable-bekleyen")
    assert n.public_kuyruk(teyit) is True
    iptal = _olay(formation_id="stable-bekleyen", state="KIRILIM_GECERSIZLESTI")
    assert n.public_kuyruk(iptal) is False     # ikisi de düşer
    assert n._public_kuyruk == []
    assert n._public_alert_markers == {}


def test_gonderilmis_teyidin_gecersizlesmesi_kuyruga_girer(grup_notifier):
    n = grup_notifier
    n._public_kuyruk = []
    n._public_alert_markers = {}
    teyit = _olay(formation_id="stable-gonderilmis")
    assert n.public_kuyruk(teyit) is True
    n._public_kuyruk = []
    n._public_alert_markers[n._public_event_key(teyit)] = "2026-10-22T17:31:00+03:00"
    iptal = _olay(formation_id="stable-gonderilmis", state="KIRILIM_GECERSIZLESTI")
    assert n.public_kuyruk(iptal) is True
    assert len(n._public_kuyruk) == 1


# --- 13) Metin = DM kartı: kuyruk yolundan birebir ---------------------------

def test_kuyruk_yolundan_giden_metin_dm_kartiyla_ayni(grup_notifier, monkeypatch):
    """Uçtan uca: `public_kuyruk` → `public_bosalt` → Telegram gövdesi.

    Kayıt kuyruğa kopyalanırken bir alan düşerse metin DM'den sessizce
    ayrışırdı; bu test hem kopyalamayı hem biçimlendirmeyi birlikte doğrular
    (5 haneli endeks fiyatı dâhil: satır bölünmesi de burada görünür).
    """
    n = grup_notifier
    kayit = _zengin_olay(stock="XBANK", formation_id="endeks-1",
                         break_dir=1, break_price=13380.0,
                         critical_price_level=13380.0, candle_close_price=13482.5,
                         upper_now=13510.0, lower_now=13120.0,
                         domain_bolumleri={
                             "yapi_ozet": ["◈ 4s yapı dış ↑, iç ↑"],
                             "goreli": ["· 20 mum endekse +1,2 puan"],
                             "olcum": ["◇ 32321 formasyon · %76 tuttu",
                                       "◇ 1651 kırılımın %75'ü sürdü",
                                       "◇ hacim yüksekken %79 sürdü"],
                             "hacim": ["hacim 4s yok (endeks)",
                                       "yön fiyattan okunur"]})
    assert n.public_kuyruk(kayit)
    sahte = _SahteRequests()
    monkeypatch.setitem(sys.modules, "requests", sahte)
    assert n.public_bosalt() == 1
    metin = sahte.cagrilar[0][1]["text"]
    assert metin == notifier_mod._format_lifecycle_alert_kart(kayit)
    assert "hacim 4s yok (endeks)" in metin
    assert "· kapanış 13482,50" in metin and "· kırılan 13380,00" in metin
    assert not [s for s in metin.splitlines() if s.startswith(" ")], metin


def test_public_mesaj_butcesi_dm_tavanindan_dusuk_degil():
    """1 mesaj = 1 olay olduğu için grup, DM'in göremediği alarmı kaçırmamalı."""
    import config
    assert config.PUBLIC_MAX_MESAJ_SAAT >= config.TELEGRAM_MAX_MESAJ_SAAT
    assert config.PUBLIC_MAX_MESAJ_GUN >= config.TELEGRAM_MAX_MESAJ_GUN
