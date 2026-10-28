# -*- coding: utf-8 -*-
"""Public (grup) komutları — 2026-10-28.

DEĞİŞEN KURAL: eskiden komutlar YALNIZ `TELEGRAM_CHAT_ID` (DM) sohbetinden
kabul edilirdi ve public grup yalnız yayın alırdı. Artık grup/supergroup
sohbetinde komut çalışabilir — ama üç kilit birlikte:

  1. sohbet `PUBLIC_COMMAND_CHATS` (yoksa `TELEGRAM_GROUP_ID`) içinde olacak,
  2. komut public beyaz listesinde olacak (okuma komutları; alias'lar dahil),
  3. gönderen kişi `getChatMember` ile `creator`/`administrator` çıkacak.

Bu dosya kilitlerin HER BİRİNİ ayrı ayrı kilitler; ayrıca en pahalı iki hatayı:
yanlış sohbete cevap (veri sızıntısı) ve yönetici API'si susunca yetki verme
(fail-open) davranışını hedefler.
"""

from __future__ import annotations

import time

import pytest

import telegram_commands as tc


# --------------------------------------------------------------------- yardımcı


class SahteYanit:
    def __init__(self, kod=200, govde=None):
        self.status_code = kod
        self._govde = govde if govde is not None else {"ok": True}

    def json(self):
        return self._govde


class SahteSession:
    """sendMessage çağrılarını kaydeder (ağa çıkmaz)."""

    def __init__(self):
        self.post_cagrilari = []

    def post(self, url, json=None, timeout=None):
        self.post_cagrilari.append((url, dict(json or {})))
        return SahteYanit(200)

    def get(self, url, params=None, timeout=None):     # pragma: no cover
        return SahteYanit(200, {"ok": True, "result": []})


def _guncelleme(update_id, metin, chat_id=-1001234567890, tip="supergroup",
                kullanici=555, mesaj_id=None):
    """Grup mesajı üretir; `date` GERÇEK zamanlı (bayat kuralına takılmasın)."""
    return {"update_id": update_id,
            "message": {"message_id": mesaj_id if mesaj_id is not None else update_id,
                        "date": int(time.time()),
                        "chat": {"id": chat_id, "type": tip},
                        "from": {"id": kullanici, "is_bot": False,
                                 "first_name": "Test"},
                        "text": metin}}


GRUP = "-1001234567890"
DM = "42"


def _dinleyici(*, admin=True, admin_hata=False, session=None,
               public_chat_ids=(GRUP,), public_commands=None,
               allowed_chat_id=DM, cagrilar=None, handlers=None):
    kayit = cagrilar if cagrilar is not None else []

    def admin_kontrol(chat_id, user_id):
        kayit.append((str(chat_id), str(user_id)))
        if admin_hata:
            raise RuntimeError("api down")
        return admin

    return tc.TelegramCommandListener(
        token="111:AAA",
        allowed_chat_id=allowed_chat_id,
        handlers=handlers or {"durum": lambda _a: "durum cevabi",
                              "panel": lambda _a: "panel cevabi",
                              "tara": lambda _a: "tarama basladi"},
        help_text="YARDIM",
        session=session or SahteSession(),
        public_chat_ids=public_chat_ids,
        public_commands=public_commands if public_commands is not None
        else {"durum", "panel", "yardim"},
        admin_checker=admin_kontrol,
    )


# ------------------------------------------------------- 1) mutlu yol: yönetici


def test_grup_yoneticisi_komutu_calisir_ve_cevap_gruba_gider():
    session = SahteSession()
    d = _dinleyici(session=session)
    cevap = d.handle_update(_guncelleme(1, "/durum"))

    assert cevap == "durum cevabi"
    assert len(session.post_cagrilari) == 1
    _url, govde = session.post_cagrilari[0]
    assert govde["chat_id"] == GRUP            # DM'e KAÇMAZ
    assert govde["text"] == "durum cevabi"


def test_grup_cevabi_istegi_alintilar():
    """Grupta hangi komuta cevap geldiği görünsün: reply + güvenli bayrak."""
    session = SahteSession()
    d = _dinleyici(session=session)
    d.handle_update(_guncelleme(7, "/panel", mesaj_id=777))

    _url, govde = session.post_cagrilari[0]
    assert govde["reply_to_message_id"] == 777
    # Alıntılanan mesaj silinmişse Telegram 400 verirdi; bayrak şart.
    assert govde["allow_sending_without_reply"] is True


def test_public_sayaci_gelen_komutu_ve_yetki_kapsamini_gosterir():
    """`public_islenen` public YOLDAN gelen komut sayısıdır (yetki kapısına giren)."""
    d = _dinleyici()
    d.handle_update(_guncelleme(1, "/durum"))
    durum = d.durum()
    assert durum["public_islenen"] == 1
    assert durum["islenen"] == 1
    assert durum["public_komut_hazir"] is True
    assert durum["public_komut_hedefi"] == 1


# ------------------------------------------------- 2) yönetici olmayan: sessiz ret


def test_yonetici_olmayan_uye_sessizce_yok_sayilir():
    """Grupta "yetkiniz yok" cevabı bot spam'i olurdu → hiç cevap yok."""
    session = SahteSession()
    d = _dinleyici(admin=False, session=session)
    cevap = d.handle_update(_guncelleme(1, "/durum"))

    assert cevap is None
    assert session.post_cagrilari == []
    durum = d.durum()
    assert durum["yetkisiz_kullanici"] == 1
    assert durum["public_islenen"] == 1


def test_yonetici_olmayan_uye_komutu_CALISTIRILMAZ():
    """Handler gerçekten çağrılmadı mı? Sayaç değil, yan etki üzerinden bak."""
    cagrildi = []
    d = _dinleyici(admin=False, handlers={"durum": lambda _a: cagrildi.append(1) or "x"})
    d.handle_update(_guncelleme(1, "/durum"))
    assert cagrildi == []


# --------------------------------------------- 3) fail-closed: yönetici API'si sustu


def test_yonetici_kontrolu_hata_verirse_komut_calismaz():
    """En pahalı hata: API'ye ulaşılamıyor diye yetki VERMEK (fail-open)."""
    session = SahteSession()
    d = _dinleyici(admin_hata=True, session=session)
    cevap = d.handle_update(_guncelleme(1, "/durum"))

    assert cevap is None
    assert session.post_cagrilari == []
    durum = d.durum()
    assert durum["yetkisiz_kullanici"] == 1
    assert durum["admin_kontrol_hatasi"] == 1


def test_admin_checker_yoksa_public_yol_kapali():
    """Yöneticilik sorucusu verilmezse public komut hiç açılmaz."""
    session = SahteSession()
    d = tc.TelegramCommandListener(
        token="111:AAA", allowed_chat_id=DM, handlers={"durum": lambda _a: "x"},
        help_text="YARDIM", session=session,
        public_chat_ids=[GRUP], public_commands={"durum"}, admin_checker=None)
    assert d.public_enabled is False
    assert d.handle_update(_guncelleme(1, "/durum")) is None
    assert session.post_cagrilari == []


def test_bos_public_komut_kumesi_public_yolu_kapatir():
    d = _dinleyici(public_commands=set())
    assert d.public_enabled is False
    assert d.handle_update(_guncelleme(1, "/durum")) is None


# ------------------------------------------------------ 4) komut beyaz listesi


def test_public_te_kapali_komut_calismaz_ve_neden_soylenir():
    session = SahteSession()
    d = _dinleyici(session=session)
    cevap = d.handle_update(_guncelleme(1, "/tara"))

    assert "public sohbette kapalı" in cevap
    assert "tara" in cevap
    # Cevap yine GRUBA gider (yöneticiye bilgi), komut çalışmaz.
    assert session.post_cagrilari[0][1]["chat_id"] == GRUP
    assert d.durum()["public_kapali_komut"] == 1


def test_public_te_kapali_komut_icin_handler_cagrilmaz():
    cagrildi = []
    d = _dinleyici(handlers={"tara": lambda _a: cagrildi.append(1) or "x"})
    d.handle_update(_guncelleme(1, "/tara"))
    assert cagrildi == []


# ---------------------------------------------------------- 5) DM davranışı sabit


def test_dm_yolu_aynen_calisir_ve_cevap_dm_e_gider():
    session = SahteSession()
    d = _dinleyici(session=session)
    cevap = d.handle_update(_guncelleme(1, "/tara", chat_id=int(DM), tip="private"))

    assert cevap == "tarama basladi"
    _url, govde = session.post_cagrilari[0]
    assert govde["chat_id"] == DM               # public hedefe KAÇMAZ
    # DM'de beyaz liste yok: /tara (public'te kapalı) DM'de çalışır.
    assert "reply_to_message_id" not in govde


def test_dm_de_yetki_kontrolu_yapilmaz():
    cagrilar = []
    d = _dinleyici(admin=False, cagrilar=cagrilar)
    d.handle_update(_guncelleme(1, "/durum", chat_id=int(DM), tip="private"))
    assert cagrilar == []                       # getChatMember hiç çağrılmadı


def test_yabanci_sohbet_hala_reddedilir():
    session = SahteSession()
    d = _dinleyici(session=session)
    cevap = d.handle_update(_guncelleme(1, "/durum", chat_id=-1009999999999))
    assert cevap is None
    assert session.post_cagrilari == []
    assert d.durum()["yetkisiz_sohbet"] == 1


# ------------------------------------------------------------- 6) kanal istisnası


def test_kanal_gonderisi_komut_olarak_calismaz():
    """`channel_post` gönderisinde gönderen KULLANICI yok → yetki doğrulanamaz."""
    session = SahteSession()
    d = _dinleyici(session=session)
    update = {"update_id": 1,
              "channel_post": {"message_id": 5, "date": int(time.time()),
                               "chat": {"id": -1001234567890, "type": "channel"},
                               "sender_chat": {"id": -1001234567890},
                               "text": "/durum"}}
    assert d.handle_update(update) is None
    assert session.post_cagrilari == []


def test_channel_post_mesaj_olarak_okunur():
    update = {"channel_post": {"message_id": 5, "chat": {"id": -1}, "text": "/x"}}
    mesaj = tc.mesaj_sohbeti(update)
    assert mesaj.get("message_id") == 5


# --------------------------------------------------------- 7) sohbet eşleştirmesi


@pytest.mark.parametrize("yapilandirilan", ["-1001234567890", "@test_grup"])
def test_sohbet_kullanici_adi_ve_sayisal_id_ile_eslesir(yapilandirilan):
    """`TELEGRAM_GROUP_ID=@grup` ile `-100…` aynı sohbeti göstermeli.

    Ham string karşılaştırması yapılsaydı `@grup` hiç eşleşmez ve public
    komutlar sessizce çalışmazdı.
    """
    d = _dinleyici(public_chat_ids=(yapilandirilan,))
    update = _guncelleme(1, "/durum")
    update["message"]["chat"]["username"] = "test_grup"
    assert d.handle_update(update) == "durum cevabi"


def test_sohbet_anahtari_normalize_eder():
    assert tc.sohbet_anahtari("@Grup_Adi") == "grup_adi"
    assert tc.sohbet_anahtari("-1001234567890") == "-1001234567890"
    assert tc.sohbet_anahtari("") == ""


# ------------------------------------------------------- 8) yönetici önbelleği


def test_yonetici_karari_onbelleklenir():
    cagrilar = []
    d = _dinleyici(cagrilar=cagrilar)
    for i in range(3):
        d.handle_update(_guncelleme(i + 1, "/durum"))
    assert len(cagrilar) == 1                   # 3 komut → 1 getChatMember


def test_onbellek_sifirsa_her_komutta_sorulur():
    cagrilar = []
    d = _dinleyici(cagrilar=cagrilar)
    d._admin_cache_sn = 0.0
    for i in range(3):
        d.handle_update(_guncelleme(i + 1, "/durum"))
    assert len(cagrilar) == 3


def test_hata_karari_onbelleklenmez():
    """Geçici ağ hatası yöneticiyi önbellek süresi boyunca kilitlememeli."""
    durum = {"hata": True}

    def admin_kontrol(_c, _u):
        if durum["hata"]:
            raise RuntimeError("gecici")
        return True

    d = tc.TelegramCommandListener(
        token="111:AAA", allowed_chat_id=DM, handlers={"durum": lambda _a: "ok"},
        help_text="YARDIM", session=SahteSession(),
        public_chat_ids=[GRUP], public_commands={"durum"}, admin_checker=admin_kontrol)

    assert d.handle_update(_guncelleme(1, "/durum")) is None
    durum["hata"] = False
    assert d.handle_update(_guncelleme(2, "/durum")) == "ok"


# ------------------------------------------- 9) public-only: DM chat_id olmadan


def test_dm_hedefi_olmadan_da_dinleyici_acilir():
    """Yalnız grup kuran kullanıcıda komutlar eskiden hiç başlamıyordu."""
    d = tc.TelegramCommandListener(
        token="111:AAA", allowed_chat_id="", handlers={"durum": lambda _a: "ok"},
        help_text="YARDIM", session=SahteSession(),
        public_chat_ids=[GRUP], public_commands={"durum"},
        admin_checker=lambda _c, _u: True)
    assert d.enabled is True
    assert d.handle_update(_guncelleme(1, "/durum")) == "ok"


def test_dm_hedefi_ve_public_yoksa_dinleyici_kapali():
    d = tc.TelegramCommandListener(
        token="111:AAA", allowed_chat_id="", handlers={}, help_text="",
        session=SahteSession())
    assert d.enabled is False


# ---------------------------------------------------------- 10) teşhis alanları


def test_durum_public_alanlarini_sifirlanmis_dondurur():
    d = _dinleyici()
    durum = d.durum()
    for anahtar in ("public_komut_hedefi", "public_komut_hazir", "public_islenen",
                    "yetkisiz_kullanici", "admin_kontrol_hatasi",
                    "public_kapali_komut", "son_public_sohbet"):
        assert anahtar in durum, anahtar
    # Kimlik maskelenir: tam sohbet kimliği /health'e düşmez.
    assert not str(durum["son_public_sohbet"]).startswith("-100")


# --------------------------------------------- 11) kurulum katmanı (transport)


def test_kurulum_public_ayarlari_listener_icerisine_gecer():
    """`komut_katmanini_kur` üç public ayarını da dinleyiciye taşımalı."""
    import transport.telegram as tt

    yakalanan = {}

    def sahte_factory(**kwargs):
        yakalanan.update(kwargs)

        class Sahte:
            enabled = True

            def start(self):
                return True

        return Sahte()

    class SahteNotifier:
        token = "111:AAA"
        chat_id = DM
        enabled = True
        public_enabled = True

    sonuc = tt.komut_katmanini_kur(
        SahteNotifier(), None,
        komutlar={"durum": lambda _a: "x"}, yardim_metni="Y",
        tarama_suruyor=lambda: False, health_server_var=False,
        listener_factory=sahte_factory, adres_olustur=lambda: "",
        gizle=lambda *a: "", secret_ayikla=lambda *a: "", set_webhook_fn=lambda **k: False,
        delete_webhook_fn=lambda **k: False,
        public_sohbetler=[GRUP], public_komutlar={"durum", "panel"},
        admin_kontrol=lambda c, u: True, admin_cache_sn=120.0)

    assert sonuc["mod"] == "yoklama"
    assert yakalanan["public_chat_ids"] == [GRUP]
    assert set(yakalanan["public_commands"]) == {"durum", "panel"}
    assert yakalanan["admin_checker"] is not None
    assert yakalanan["admin_cache_sn"] == 120.0


def test_kurulum_dm_yoksa_public_yoluyla_acilir():
    """DM chat_id boş ama public yol açık: komut katmanı KAPANMAMALI."""
    import transport.telegram as tt

    class SahteNotifier:
        token = "111:AAA"
        chat_id = ""
        enabled = False          # DM kapalı
        public_enabled = True

    class Sahte:
        enabled = True

        def start(self):
            return True

    sonuc = tt.komut_katmanini_kur(
        SahteNotifier(), None,
        komutlar={"durum": lambda _a: "x"}, yardim_metni="Y",
        tarama_suruyor=lambda: False, health_server_var=False,
        listener_factory=lambda **k: Sahte(), adres_olustur=lambda: "",
        gizle=lambda *a: "", secret_ayikla=lambda *a: "", set_webhook_fn=lambda **k: False,
        delete_webhook_fn=lambda **k: False,
        public_sohbetler=[GRUP], public_komutlar={"durum"},
        admin_kontrol=lambda c, u: True)

    assert sonuc["mod"] == "yoklama"


def test_kurulum_public_ayar_yoksa_eski_davranis():
    """Public ayar verilmezse DM yoksa komut katmanı kapalı kalır (regresyon yok)."""
    import transport.telegram as tt

    class SahteNotifier:
        token = "111:AAA"
        chat_id = ""
        enabled = False
        public_enabled = True

    sonuc = tt.komut_katmanini_kur(
        SahteNotifier(), None,
        komutlar={"durum": lambda _a: "x"}, yardim_metni="Y",
        tarama_suruyor=lambda: False, health_server_var=False,
        listener_factory=lambda **k: None, adres_olustur=lambda: "",
        gizle=lambda *a: "", secret_ayikla=lambda *a: "", set_webhook_fn=lambda **k: False,
        delete_webhook_fn=lambda **k: False)

    assert sonuc["mod"] == "kapali"


# ------------------------------------------------- 12) public beyaz listesi


def test_public_beyaz_listesi_aliaslari_da_kapsar():
    """`/p` açıkken `/panel` kapalı kalmamalı: liste İŞLEYİCİ bazlı."""
    import main as main_mod

    adlar = main_mod._public_komut_adlari()
    assert {"panel", "p", "genel", "tablo"} <= adlar
    assert {"ozet", "o", "gunluk"} <= adlar
    assert {"start", "yardim", "help"} <= adlar


def test_public_beyaz_listesi_agir_ve_durum_degistirenleri_kapatir():
    import main as main_mod

    adlar = main_mod._public_komut_adlari()
    for yasak in ("tara", "grafik", "g", "evet", "onay", "kabul",
                  "hayir", "hayır", "red"):
        assert yasak not in adlar, yasak


def test_public_beyaz_listesi_okuma_komutlarini_acar():
    import main as main_mod

    adlar = main_mod._public_komut_adlari()
    for ad in ("formasyonlar", "canli", "panel", "ozet", "sikisanlar",
               "tamamlanan", "retest", "kirilim", "durum", "olcum",
               "karne", "backtest"):
        assert ad in adlar, ad


def test_public_komut_extra_bilinmeyen_adi_yok_sayar(monkeypatch):
    import main as main_mod

    monkeypatch.setattr(main_mod, "PUBLIC_COMMAND_EXTRA", ["tara", "bilinmeyen-komut"])
    adlar = main_mod._public_komut_adlari()
    assert "tara" in adlar                 # bilinen ad açıldı
    assert "bilinmeyen-komut" not in adlar  # bilinmeyen sessizce düşer


def test_public_komut_sohbetleri_grup_ve_kanaldan_turer(monkeypatch):
    import config
    import main as main_mod

    monkeypatch.setattr(config, "TELEGRAM_GROUP_ID", "-100111")
    monkeypatch.setattr(config, "TELEGRAM_CHANNEL_ID", "@kanal")
    assert main_mod._public_komut_sohbetleri() == ["-100111", "@kanal"]


def test_public_komut_sohbetleri_acik_liste_onceliklidir(monkeypatch):
    import config
    import main as main_mod

    monkeypatch.setattr(main_mod, "PUBLIC_COMMAND_CHATS", ["@ozel"])
    monkeypatch.setattr(config, "TELEGRAM_GROUP_ID", "-100111")
    assert main_mod._public_komut_sohbetleri() == ["@ozel"]


def test_public_komutlari_kapatma_anahtari(monkeypatch):
    import config
    import main as main_mod

    monkeypatch.setattr(config, "TELEGRAM_GROUP_ID", "-100111")
    monkeypatch.setattr(main_mod, "PUBLIC_COMMANDS_ENABLED", False)
    assert main_mod._public_komut_sohbetleri() == []


# ------------------------------------------------- 13) yönetici doğrulaması


def _sahte_api(kod=200, govde=None, kayit=None):
    def api(method, token, payload, timeout=15):
        if kayit is not None:
            kayit.append((method, dict(payload)))
        return SahteYanit(kod, govde if govde is not None else {
            "ok": True, "result": {"status": "administrator"}})
    return api


def test_get_chat_member_administrator_true(monkeypatch):
    import main as main_mod

    kayit = []
    monkeypatch.setattr(main_mod, "_telegram_api_cagri", _sahte_api(kayit=kayit))
    monkeypatch.setattr(main_mod, "_telegram_token_al", lambda *_a, **_k: "111:AAA")
    assert main_mod._telegram_yonetici_mi(GRUP, "555") is True
    assert kayit[0][0] == "getChatMember"
    assert kayit[0][1] == {"chat_id": GRUP, "user_id": "555"}


def test_get_chat_member_creator_true(monkeypatch):
    import main as main_mod

    monkeypatch.setattr(main_mod, "_telegram_api_cagri", _sahte_api(
        govde={"ok": True, "result": {"status": "creator"}}))
    monkeypatch.setattr(main_mod, "_telegram_token_al", lambda *_a, **_k: "111:AAA")
    assert main_mod._telegram_yonetici_mi(GRUP, "555") is True


@pytest.mark.parametrize("durum", ["member", "restricted", "left", "kicked", ""])
def test_get_chat_member_uye_yonetici_degil(monkeypatch, durum):
    import main as main_mod

    monkeypatch.setattr(main_mod, "_telegram_api_cagri", _sahte_api(
        govde={"ok": True, "result": {"status": durum}}))
    monkeypatch.setattr(main_mod, "_telegram_token_al", lambda *_a, **_k: "111:AAA")
    assert main_mod._telegram_yonetici_mi(GRUP, "555") is False


def test_get_chat_member_ag_hatasinda_false(monkeypatch):
    import main as main_mod

    def patla(*_a, **_k):
        raise RuntimeError("ag yok")

    monkeypatch.setattr(main_mod, "_telegram_api_cagri", patla)
    monkeypatch.setattr(main_mod, "_telegram_token_al", lambda *_a, **_k: "111:AAA")
    assert main_mod._telegram_yonetici_mi(GRUP, "555") is False


def test_get_chat_member_telegram_hata_donerse_false(monkeypatch):
    import main as main_mod

    monkeypatch.setattr(main_mod, "_telegram_api_cagri", _sahte_api(
        kod=400, govde={"ok": False, "description": "Bad Request: chat not found"}))
    monkeypatch.setattr(main_mod, "_telegram_token_al", lambda *_a, **_k: "111:AAA")
    assert main_mod._telegram_yonetici_mi(GRUP, "555") is False


def test_get_chat_member_token_yoksa_api_cagrilmaz(monkeypatch):
    import main as main_mod

    kayit = []
    monkeypatch.setattr(main_mod, "_telegram_api_cagri", _sahte_api(kayit=kayit))
    monkeypatch.setattr(main_mod, "_telegram_token_al", lambda *_a, **_k: "")
    assert main_mod._telegram_yonetici_mi(GRUP, "555") is False
    assert kayit == []


# --------------------------------- 14) gerçek kurulum: main._telegram_komut_katmanini_kur


def _sahte_notifier(token="111:AAA", chat_id=DM, public=True):
    class SahteNotifier:
        pass

    n = SahteNotifier()
    n.token = token
    n.chat_id = chat_id
    n.enabled = bool(token and chat_id)
    n.public_enabled = public
    return n


def test_main_kurulum_public_listener_i_gercekten_kuruyor(monkeypatch):
    """Uçtan uca: `main` gerçek ayarlarla listener'ı PUBLIC yetkili kuruyor mu?

    Webhook yolu seçilir (setWebhook sahte True) → thread açılmaz, ağa çıkılmaz.
    """
    import main as main_mod

    yakalanan = {}

    def sahte_factory(**kwargs):
        yakalanan.update(kwargs)
        return object()

    monkeypatch.setattr(main_mod, "TelegramCommandListener", sahte_factory)
    monkeypatch.setattr(main_mod, "_telegram_set_webhook", lambda **_k: True)
    monkeypatch.setattr(main_mod, "_telegram_webhook_url_olustur",
                        lambda *_a, **_k: "https://ornek.onrender.com/webhook")
    monkeypatch.setattr(main_mod, "PUBLIC_COMMAND_CHATS", [GRUP])
    monkeypatch.setattr(main_mod, "PUBLIC_COMMAND_EXTRA", [])
    monkeypatch.setattr(main_mod, "_health_server_ref", object())

    mod = main_mod._telegram_komut_katmanini_kur(_sahte_notifier())
    assert mod == "webhook"
    assert yakalanan["public_chat_ids"] == [GRUP]
    assert "panel" in yakalanan["public_commands"]
    assert "tara" not in yakalanan["public_commands"]
    assert callable(yakalanan["admin_checker"])


def test_main_kurulum_dm_kapaliyken_public_ile_acilir(monkeypatch):
    """TELEGRAM_CHAT_ID boş + grup tanımlı: komutlar artık başlıyor."""
    import main as main_mod

    yakalanan = {}

    def sahte_factory(**kwargs):
        yakalanan.update(kwargs)

        class Sahte:
            def start(self):
                return True

        return Sahte()

    monkeypatch.setattr(main_mod, "TelegramCommandListener", sahte_factory)
    monkeypatch.setattr(main_mod, "_telegram_delete_webhook", lambda **_k: True)
    monkeypatch.setattr(main_mod, "_telegram_webhook_url_olustur", lambda *_a, **_k: "")
    monkeypatch.setattr(main_mod, "PUBLIC_COMMAND_CHATS", [GRUP])

    mod = main_mod._telegram_komut_katmanini_kur(_sahte_notifier(chat_id=""))
    assert mod == "yoklama"
    assert yakalanan["allowed_chat_id"] == ""
    assert yakalanan["public_chat_ids"] == [GRUP]


def test_main_kurulum_public_kapaliyken_dm_kapaliysa_kapali(monkeypatch):
    """PUBLIC_COMMANDS_ENABLED=0 + DM yok → komut katmanı kapalı (eski davranış)."""
    import main as main_mod

    monkeypatch.setattr(main_mod, "PUBLIC_COMMANDS_ENABLED", False)
    monkeypatch.setattr(main_mod, "_telegram_webhook_url_olustur", lambda *_a, **_k: "")
    mod = main_mod._telegram_komut_katmanini_kur(_sahte_notifier(chat_id=""))
    assert mod == "kapali"


# ============================ 15) KANAL SENARYOSU (2026-10-29 teşhisi) ========
#
# Gerçek vaka: `TELEGRAM_GROUP_ID=@bisthisseveri` bir KANAL. Kanalda komut
# İMKÂNSIZDIR (üyeler yazamaz; admin gönderisinde `from` yok) ama eskiden bu
# SESSİZCE yok sayılıyordu: sayaç artmıyor, log düşmüyordu. Artık görünür.


def test_kanal_gonderisi_sayilir_ve_loglanir():
    d = _dinleyici(session=SahteSession())
    update = {"update_id": 1,
              "channel_post": {"message_id": 5, "date": int(time.time()),
                               "chat": {"id": -1001234567890, "type": "channel"},
                               "text": "/durum"}}
    assert d.handle_update(update) is None
    durum = d.durum()
    assert durum["kanal_gonderisi"] == 1, "kanal gönderisi sayaçsız kalmamalı"
    assert durum["public_islenen"] == 0


def test_kanal_gonderisi_handler_calistirmaz():
    cagrildi = []
    d = _dinleyici(handlers={"durum": lambda _a: cagrildi.append(1) or "x"})
    update = {"update_id": 1,
              "channel_post": {"message_id": 5, "date": int(time.time()),
                               "chat": {"id": -1001234567890, "type": "channel"},
                               "text": "/durum"}}
    d.handle_update(update)
    assert cagrildi == []


def test_izlenen_guncellemeler_channel_post_icerir():
    """Kanal hedefini teşhis edebilmek için channel_post İSTENMELİ."""
    from telegram_commands import IZLENEN_GUNCELLEMELER, IZLENEN_GUNCELLEMELER_JSON

    assert "message" in IZLENEN_GUNCELLEMELER          # grup komutları
    assert "channel_post" in IZLENEN_GUNCELLEMELER     # kanal teşhisi
    assert '"channel_post"' in IZLENEN_GUNCELLEMELER_JSON


def test_set_webhook_izlenen_turleri_gonderir():
    import transport.telegram as tt
    from telegram_commands import IZLENEN_GUNCELLEMELER

    yakalanan = {}

    def api(method, token, govde, timeout=15):
        yakalanan[method] = dict(govde)
        return SahteYanit(200, {"ok": True, "description": "ok"})

    ok = tt.set_webhook(
        url="https://ornek.onrender.com/webhook", secret="s3cret", token="111:AAA",
        api=api, yanit_oku_fn=tt.yanit_oku,
        secret_ayikla_fn=lambda s=None: "s3cret", token_al_fn=lambda t=None: "111:AAA",
        adres_olustur_fn=lambda **k: "https://ornek.onrender.com/webhook",
        gizle_fn=lambda *a: "")
    assert ok is True
    assert yakalanan["setWebhook"]["allowed_updates"] == list(IZLENEN_GUNCELLEMELER)


# ============================ 16) HEDEF TİPİ TEŞHİSİ =========================


def test_hedef_tipi_kanal_komut_alamaz(monkeypatch):
    import main as main_mod

    def api(method, token, payload, timeout=15):
        assert method == "getChat"
        return SahteYanit(200, {"ok": True, "result": {"type": "channel",
                                                       "title": "bisthisseveri"}})

    monkeypatch.setattr(main_mod, "_telegram_api_cagri", api)
    monkeypatch.setattr(main_mod, "_telegram_token_al", lambda *_a, **_k: "111:AAA")
    bilgi = main_mod._public_hedef_tipi_getir(["-1001234567890"])
    assert len(bilgi) == 1
    assert bilgi[0]["tur"] == "channel"
    assert bilgi[0]["komut"] is False
    assert bilgi[0]["okundu"] is True


@pytest.mark.parametrize("tur", ["group", "supergroup"])
def test_hedef_tipi_grup_komut_alabilir(monkeypatch, tur):
    import main as main_mod

    monkeypatch.setattr(main_mod, "_telegram_api_cagri", lambda *a, **k: SahteYanit(
        200, {"ok": True, "result": {"type": tur}}))
    monkeypatch.setattr(main_mod, "_telegram_token_al", lambda *_a, **_k: "111:AAA")
    bilgi = main_mod._public_hedef_tipi_getir([GRUP])
    assert bilgi[0]["tur"] == tur
    assert bilgi[0]["komut"] is True


def test_hedef_tipi_okunamazsa_sessiz_kalmaz(monkeypatch):
    import main as main_mod

    def patla(*_a, **_k):
        raise RuntimeError("ag yok")

    monkeypatch.setattr(main_mod, "_telegram_api_cagri", patla)
    monkeypatch.setattr(main_mod, "_telegram_token_al", lambda *_a, **_k: "111:AAA")
    bilgi = main_mod._public_hedef_tipi_getir([GRUP])
    assert bilgi[0]["okundu"] is False and bilgi[0]["tur"] is None


def test_hedef_tipi_token_yoksa_cagrilmaz(monkeypatch):
    import main as main_mod

    kayit = []
    monkeypatch.setattr(main_mod, "_telegram_api_cagri", lambda *a, **k: kayit.append(1))
    monkeypatch.setattr(main_mod, "_telegram_token_al", lambda *_a, **_k: "")
    assert main_mod._public_hedef_tipi_getir([GRUP]) == []
    assert kayit == []


def test_komut_durumu_hedef_tiplerini_tasir(monkeypatch):
    import main as main_mod

    monkeypatch.setattr(main_mod, "_public_hedef_bilgisi",
                        [{"sohbet": "…7890", "tur": "channel", "komut": False,
                          "okundu": True}])
    durum = main_mod._komut_durumu()
    assert durum["public_hedefler"][0]["tur"] == "channel"
    assert durum["public_hedefler"][0]["komut"] is False


# ============================ 17) /teshis KOMUTU =============================


def _teshis_ortami(monkeypatch, *, tur="channel", uyelik="administrator",
                   turler=("message", "channel_post")):
    """`/teshis` için sahte Telegram API'si kur."""
    import main as main_mod

    def api(method, token, payload, timeout=15):
        if method == "getChat":
            return SahteYanit(200, {"ok": True, "result": {"type": tur,
                                                           "title": "test"}})
        if method == "getMe":
            return SahteYanit(200, {"ok": True, "result": {"id": 42, "is_bot": True}})
        if method == "getChatMember":
            return SahteYanit(200, {"ok": True, "result": {"status": uyelik}})
        if method == "getWebhookInfo":
            return SahteYanit(200, {"ok": True, "result": {
                "url": "https://ornek.onrender.com/webhook",
                "pending_update_count": 0,
                "allowed_updates": list(turler),
            }})
        return SahteYanit(200, {"ok": True, "result": {}})

    monkeypatch.setattr(main_mod, "_telegram_api_cagri", api)
    monkeypatch.setattr(main_mod, "_telegram_token_al", lambda *_a, **_k: "111:AAA")
    monkeypatch.setattr(main_mod, "PUBLIC_COMMAND_CHATS", [GRUP])
    return main_mod


def test_teshis_kanal_hedefini_ve_cozumu_soyler(monkeypatch):
    main_mod = _teshis_ortami(monkeypatch, tur="channel")
    metin = main_mod._komut_teshis("")
    assert "KANAL" in metin
    assert "PUBLIC_COMMAND_CHATS" in metin
    assert "grup" in metin.lower()


def test_teshis_grup_hedefinde_kanal_uyarisi_vermez(monkeypatch):
    main_mod = _teshis_ortami(monkeypatch, tur="supergroup")
    metin = main_mod._komut_teshis("")
    assert "Komut alabilen" in metin or "supergroup" in metin
    assert "🔴 SEBEP: hedef bir KANAL" not in metin


def test_teshis_allowed_updates_eksikse_uyarir(monkeypatch):
    main_mod = _teshis_ortami(monkeypatch, tur="supergroup", turler=("channel_post",))
    metin = main_mod._komut_teshis("")
    assert "message" in metin and "hiç gelmez" in metin


def test_teshis_bot_grupta_degilse_soyler(monkeypatch):
    main_mod = _teshis_ortami(monkeypatch, tur="supergroup", uyelik="left")
    metin = main_mod._komut_teshis("")
    assert "DEĞİL" in metin


def test_teshis_token_yoksa_kirilmaz(monkeypatch):
    import main as main_mod

    monkeypatch.setattr(main_mod, "_telegram_token_al", lambda *_a, **_k: "")
    metin = main_mod._komut_teshis("")
    assert "TELEGRAM_BOT_TOKEN" in metin


def test_teshis_kayitli_ve_public_beyaz_listede():
    import main as main_mod

    assert main_mod.TELEGRAM_KOMUTLARI["teshis"] is main_mod._komut_teshis
    assert main_mod.TELEGRAM_KOMUTLARI["teşhis"] is main_mod._komut_teshis
    assert "teshis" in main_mod._public_komut_adlari()


def test_katman_kurulumu_hedef_teshisini_baslatir(monkeypatch):
    """Kurulum public hedef varken teşhisi başlatmalı — yoksa `/health` içindeki
    `public_hedefler` hiç dolmaz ve teşhis sessizce ölü kalır."""
    import bot.commands as bc
    import main as main_mod

    baslatildi = []
    monkeypatch.setattr(bc, "_public_hedef_bilgisi_baslat",
                        lambda *a, **k: baslatildi.append(1))
    monkeypatch.setattr(bc._transport_telegram, "komut_katmanini_kur",
                        lambda *a, **k: {"mod": "yoklama", "listener": None,
                                         "processor": None})
    monkeypatch.setattr(main_mod, "PUBLIC_COMMAND_CHATS", [GRUP])

    assert main_mod._telegram_komut_katmanini_kur(notifier=None) == "yoklama"
    assert baslatildi, "public hedef varken hedef teşhisi başlatılmalı"
