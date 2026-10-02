"""Açılış paketi testleri: metin sınırları + kanal_acilis.py davranışı (ağ yok)."""

import pytest

import acilis_metinleri as metinler
import kanal_acilis as K


# --- 1) Metin denetimi ------------------------------------------------------

def test_aciklama_sinir_icinde_ve_zorunlu_ibareler():
    metin = metinler.ACILIK_ACIKLAMASI
    sayilar = metinler.karakter_sayilari()
    assert sayilar["aciklama"] <= sayilar["aciklama_siniri"]
    assert "Yatırım tavsiyesi değildir" in metin
    assert "@bisthisseveri" in metin          # X hesabı bağlantısı
    assert "formasyon" in metin.lower()


def test_sabit_mesaj_sinir_icinde_ve_durust():
    metin = metinler.ACILIK_SABIT_MESAJ
    sayilar = metinler.karakter_sayilari()
    assert sayilar["sabit_mesaj"] <= sayilar["mesaj_siniri"]
    # Türkçe küçük harf: Python'un .lower()'ı 'İ'yi 'i̇' yapar; önce sadeleştir.
    kucuk = metin.replace("İ", "i").replace("I", "ı").lower()
    for zorunlu in ("yatırım tavsiyesi değildir", "sinyal servisi değil",
                    "başarısız kırılımlar gizlenmez", "18:45", "09:55",
                    "@bisthisseveri", "yahoo finance"):
        assert zorunlu in kucuk, f"eksik ibare: {zorunlu}"
    # Al/sat vaadi gibi okunacak ifade olmamalı: "hedef fiyat"/"kesin gider"
    # İFADELERİ yalnızca "NE YOK" uyarı bloğunda geçebilir.
    ne_yok_bloku = False
    for satir in metin.splitlines():
        if "NE YOK" in satir:
            ne_yok_bloku = True       # başlık + hemen altındaki uyarı satırı
            continue
        if ne_yok_bloku:
            if not satir.strip():
                ne_yok_bloku = False
            continue
        satir_k = satir.replace("İ", "i").replace("I", "ı").lower()
        for yasak in ("hedef fiyat", "kesin kazanç", "kâr garantisi",
                      "kesin gider", "kesin yükselir"):
            assert yasak not in satir_k, f"vaat gibi okunan ifade: {yasak}"


# --- 2) Sahte Telegram API --------------------------------------------------

class SahteOturum:
    def __init__(self, yanitlar=None, hata=None):
        self.cagrilar = []
        self.yanitlar = dict(yanitlar or {})
        self.hata = hata or {}

    def post(self, url, json=None, timeout=None):
        method = url.rsplit("/", 1)[-1]
        self.cagrilar.append((method, dict(json or {})))
        if method in self.hata:
            return _Yanit({"ok": False, "description": self.hata[method]})
        return _Yanit({"ok": True, "result": self.yanitlar.get(method, {"ok": True})})

    def metotlar(self):
        return [m for m, _ in self.cagrilar]


class _Yanit:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


def _api(yanitlar=None, hata=None, token="123:ABC"):
    return K.TelegramAPI(token, oturum=SahteOturum(yanitlar, hata))


def _kanal_yanitlari(yonetici=True):
    return {
        "getMe": {"id": 555, "username": "bist_takip_bot"},
        "getChat": {"id": -1001, "title": "BIST Formasyon", "type": "channel",
                    "username": "bisthisseveri", "member_count": 3, "description": ""},
        "getChatMember": {"status": "administrator" if yonetici else "left",
                          "can_post_messages": yonetici, "can_pin_messages": yonetici,
                          "can_change_info": yonetici},
        "sendMessage": {"message_id": 42},
    }


def test_durum_hicbir_sey_yazmaz(capsys):
    api = _api(_kanal_yanitlari())
    bilgi = K.durum(api, "@bisthisseveri")
    cikti = capsys.readouterr().out
    # Yazma metotları çağrılmadı
    assert "setChatDescription" not in api._oturum.metotlar()
    assert "sendMessage" not in api._oturum.metotlar()
    assert "pinChatMessage" not in api._oturum.metotlar()
    assert bilgi["yonetici"] is True and bilgi["tip"] == "channel"
    assert "kanal" in cikti and "3 üye" in cikti


def test_uygula_aciklama_mesaj_sabitle_sirasiyla(capsys):
    api = _api(_kanal_yanitlari())
    sonuc = K.acilisi_uygula(api, "@bisthisseveri")
    assert sonuc == {"aciklama_yazildi": True, "mesaj_id": 42, "sabitlendi": True}
    metotlar = api._oturum.metotlar()
    assert metotlar == ["setChatDescription", "sendMessage", "pinChatMessage"]
    params = dict(api._oturum.cagrilar)
    assert params["setChatDescription"]["description"] == metinler.ACILIK_ACIKLAMASI
    assert params["sendMessage"]["text"] == metinler.ACILIK_SABIT_MESAJ
    # Sabitleme sessiz olmalı (abonelere bildirim gitmesin)
    assert params["pinChatMessage"]["disable_notification"] is True
    assert params["pinChatMessage"]["message_id"] == 42


def test_uygula_parca_parca_secilebilir():
    api = _api(_kanal_yanitlari())
    K.acilisi_uygula(api, "@k", aciklama_yaz=False, yazdir=False)
    assert "setChatDescription" not in api._oturum.metotlar()

    api2 = _api(_kanal_yanitlari())
    K.acilisi_uygula(api2, "@k", sabit_yaz=False, yazdir=False)
    assert api2._oturum.metotlar() == ["setChatDescription"]


def test_uzun_aciklama_gonderilmez():
    api = _api(_kanal_yanitlari())
    with pytest.raises(K.KanalHatasi) as hata:
        K.acilisi_uygula(api, "@k", aciklama="x" * 300, sabit_yaz=False, yazdir=False)
    assert "255" in str(hata.value)
    assert api._oturum.metotlar() == []        # ağa hiç çıkılmadı


def test_yetki_hatasi_turkce_ipucu_verir():
    api = _api(_kanal_yanitlari(), hata={
        "pinChatMessage": "Bad Request: not enough rights to pin a message"})
    with pytest.raises(K.KanalHatasi) as hata:
        K.acilisi_uygula(api, "@k", aciklama_yaz=False)
    mesaj = str(hata.value)
    assert "sabitle" in mesaj.lower()
    # Açıklama ve mesaj gitti, sabitleme kaldı: kısmi başarı görünür olmalı
    assert api._oturum.metotlar() == ["sendMessage", "pinChatMessage"]


def test_yonetici_degilse_durum_kirmizi_gosterir(capsys):
    api = _api(_kanal_yanitlari(yonetici=False))
    bilgi = K.durum(api, "@k")
    cikti = capsys.readouterr().out
    assert bilgi["yonetici"] is False
    assert "🛡 Yönetici: ❌" in cikti


def test_hedef_coz_oncelik(monkeypatch):
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "@grup_id")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "-100999")
    assert K.hedef_coz("@acik") == "@acik"
    assert K.hedef_coz() == "@grup_id"
    monkeypatch.delenv("TELEGRAM_GROUP_ID")
    assert K.hedef_coz() == "-100999"
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID")
    assert K.hedef_coz() == ""


def test_ag_hatasi_anlasilir_mesaja_doner():
    class PatlayanOturum:
        def post(self, *a, **k):
            raise OSError("DNS çözümlenemedi")

    api = K.TelegramAPI("123:ABC", oturum=PatlayanOturum())
    with pytest.raises(K.KanalHatasi) as hata:
        api.sohbet("@k")
    assert "ağ" in str(hata.value).lower() and "internet" in str(hata.value).lower()
