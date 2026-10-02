#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KANAL/GRUP AÇILIŞ PAKETİ — durum kontrolü + açıklama + sabitlenmiş karşılama.

Neden var: kanalı elle kurarken en sık yapılan iki hata (bot yönetici değil /
sabit mesaj unutuldu) yalnızca ilk bültende fark edilir. Bu araç önce NE VAR
NE YOK diye Bakar, sonra istersen açıklamayı yazar ve karşılamayı gönderip
sabitler. Varsayılan davranış HİÇBİR ŞEY YAZMAZ (kuru çalışma).

Kullanım:
    .venv/bin/python kanal_acilis.py --durum
    .venv/bin/python kanal_acilis.py --uygula
    .venv/bin/python kanal_acilis.py --hedef @bisthisseveri --durum
    .venv/bin/python kanal_acilis.py --uygula --atla-sabit      # yalnız açıklama

Hedef seçimi: --hedef > TELEGRAM_GROUP_ID > TELEGRAM_CHANNEL_ID
Token        : --token  > TELEGRAM_BOT_TOKEN
"""

from __future__ import annotations

import argparse
import os
import sys

import acilis_metinleri as metinler

ACIKLAMA_SINIRI = 255


class KanalHatasi(Exception):
    """Telegram API hatası (Türkçe ipucu ile)."""

    def __init__(self, method: str, aciklama: str):
        self.method = method
        self.aciklama = aciklama or "bilinmeyen hata"
        ipucu = _ipucu(method, self.aciklama)
        super().__init__(f"{method}: {self.aciklama}" + (f" — {ipucu}" if ipucu else ""))


def _ipucu(method: str, aciklama: str) -> str:
    a = (aciklama or "").lower()
    if "not enough rights" in a or "chat_admin_required" in a or "not enough rights" in a \
            or "administrator" in a or "method is available for" in a:
        if method == "pinChatMessage":
            return ("Botun 'Mesajları sabitle' izni yok. Kanal → Yöneticiler → bot "
                    "ayarında 'Mesajları sabitle' seçeneğini aç.")
        if method == "setChatDescription":
            return ("Botun 'Bilgiyi değiştir' izni yok. Yönetici ayarında açabilir ya da "
                    "metni acilis_metinleri.py'den kopyalayıp elle yapıştırabilirsin.")
        return ("Bot kanalda yönetici değil ya da gerekli izin kapalı. Kanal → Yöneticiler "
                "→ bot ekle (Mesaj gönderme en az).")
    if "chat not found" in a:
        return ("Hedef bulunamadı. Kullanıcı adını (@kanal) ya da -100… kimliğini kontrol et; "
                "bot kanala eklenmiş olmalı.")
    if "message is not modified" in a:
        return "Açıklama zaten aynı; değişiklik yapılmadı."
    if "chat_write_forbidden" in a or "not enough rights to send" in a:
        return "Bot kanala mesaj gönderemiyor: 'Mesaj gönderme' iznini aç."
    if "ağ hatası" in a:
        return ("Telegram'a ulaşılamadı (internet/DNS/proxy). Ağ bağlantısını kontrol edip "
                "tekrar dene.")
    return ""


class TelegramAPI:
    """Yalnız ihtiyaç duyduğumuz Bot API çağrıları (test edilebilir, tek nokta)."""

    def __init__(self, token: str, oturum=None):
        self.token = (token or "").strip()
        self._oturum = oturum

    def _session(self):
        if self._oturum is None:
            import requests
            self._oturum = requests.Session()
        return self._oturum

    def cagri(self, method: str, **params):
        try:
            yanit = self._session().post(
                f"https://api.telegram.org/bot{self.token}/{method}",
                json=params, timeout=15,
            )
        except Exception as exc:  # noqa: BLE001 - ağ hatası anlaşılır mesaja dönsün
            raise KanalHatasi(method, f"ağ hatası: {type(exc).__name__}: {exc}") from exc
        try:
            veri = yanit.json()
        except Exception:  # noqa: BLE001 - gövde JSON değilse HTTP koduna düş
            veri = {}
        if yanit.status_code != 200 or not veri.get("ok"):
            raise KanalHatasi(method, veri.get("description") or f"HTTP {yanit.status_code}")
        return veri.get("result")

    # --- tek tek işlemler ---
    def bot_bilgisi(self) -> dict:
        return self.cagri("getMe") or {}

    def sohbet(self, hedef) -> dict:
        return self.cagri("getChat", chat_id=hedef) or {}

    def uyelik(self, hedef, kullanici_id) -> dict:
        return self.cagri("getChatMember", chat_id=hedef, user_id=kullanici_id) or {}

    def aciklama_yaz(self, hedef, metin: str):
        if len(metin) > ACIKLAMA_SINIRI:
            raise KanalHatasi(
                "setChatDescription",
                f"metin {len(metin)} karakter; Telegram sınırı {ACIKLAMA_SINIRI}",
            )
        return self.cagri("setChatDescription", chat_id=hedef, description=metin)

    def mesaj_gonder(self, hedef, metin: str) -> dict:
        return self.cagri("sendMessage", chat_id=hedef, text=metin,
                          disable_web_page_preview=True) or {}

    def mesaj_sabitle(self, hedef, mesaj_id):
        return self.cagri("pinChatMessage", chat_id=hedef, message_id=mesaj_id,
                          disable_notification=True)


def durum(api: TelegramAPI, hedef: str, yazdir: bool = True) -> dict:
    """Kanal/grup + bot yetkileri hakkında tek ekranlık özet (yazma YOK)."""
    sohbet = api.sohbet(hedef)
    bot = api.bot_bilgisi()
    bilgi = {
        "hedef": hedef,
        "baslik": sohbet.get("title") or sohbet.get("username") or hedef,
        "tip": sohbet.get("type"),
        "kullanici_adi": sohbet.get("username"),
        "uye_sayisi": sohbet.get("member_count"),
        "aciklama": (sohbet.get("description") or "").strip(),
        "bot_kullanici_adi": bot.get("username"),
        "bot_id": bot.get("id"),
        "yonetici": False,
        "can_post_messages": None,
        "can_pin_messages": None,
        "can_change_info": None,
        "hata": "",
    }
    try:
        uye = api.uyelik(hedef, bot.get("id"))
        bilgi["yonetici"] = uye.get("status") in ("administrator", "creator")
        bilgi["can_post_messages"] = uye.get("can_post_messages")
        bilgi["can_pin_messages"] = uye.get("can_pin_messages")
        bilgi["can_change_info"] = uye.get("can_change_info")
    except KanalHatasi as hata:
        bilgi["hata"] = str(hata)

    if yazdir:
        def isaret(deger):
            return "✅" if deger else ("—" if deger is None else "❌")

        tip_tr = {"channel": "kanal", "supergroup": "grup", "group": "grup"}.get(
            bilgi["tip"] or "", bilgi["tip"] or "?")
        uye_metni = f" · {bilgi['uye_sayisi']} üye" if bilgi["uye_sayisi"] is not None else ""
        unvan = f"@{bilgi['kullanici_adi']}" if bilgi["kullanici_adi"] else "(özel)"
        print(f"📣 Hedef: {bilgi['baslik']} {unvan} · {tip_tr}{uye_metni}")
        print(f"🤖 Bot  : @{bilgi['bot_kullanici_adi']} (id {bilgi['bot_id']})")
        print(f"🛡 Yönetici: {isaret(bilgi['yonetici'])} · "
              f"mesaj gönderme {isaret(bilgi['can_post_messages'])} · "
              f"sabitleme {isaret(bilgi['can_pin_messages'])} · "
              f"bilgi değiştirme {isaret(bilgi['can_change_info'])}")
        mevcut = bilgi["aciklama"]
        yeni = metinler.ACILIK_ACIKLAMASI
        print(f"📝 Açıklama: {('(boş)' if not mevcut else mevcut[:60] + ('…' if len(mevcut) > 60 else ''))}")
        print(f"   → yazılacak metin {len(yeni)}/{ACIKLAMA_SINIRI} karakter"
              + (" (aynı; değişiklik gerekmez)" if mevcut == yeni else ""))
        print(f"📌 Sabit mesaj: gönderilecek karşılama "
              f"{len(metinler.ACILIK_SABIT_MESAJ)}/4096 karakter")
        if bilgi["hata"]:
            print(f"⚠️  Yetki okunamadı: {bilgi['hata']}")
    return bilgi


def acilisi_uygula(api: TelegramAPI, hedef: str, aciklama: str = None,
                   sabit_mesaj: str = None, aciklama_yaz: bool = True,
                   sabit_yaz: bool = True, yazdir: bool = True) -> dict:
    """Açıklamayı yazar, karşılamayı gönderip sabitler. Yazma işlemleri sıralıdır."""
    aciklama = metinler.ACILIK_ACIKLAMASI if aciklama is None else aciklama
    sabit_mesaj = metinler.ACILIK_SABIT_MESAJ if sabit_mesaj is None else sabit_mesaj
    sonuc = {"aciklama_yazildi": False, "mesaj_id": None, "sabitlendi": False}

    if aciklama_yaz:
        api.aciklama_yaz(hedef, aciklama)
        sonuc["aciklama_yazildi"] = True
        if yazdir:
            print(f"✅ Açıklama yazıldı ({len(aciklama)}/{ACIKLAMA_SINIRI} karakter)")

    if sabit_yaz:
        gonderilen = api.mesaj_gonder(hedef, sabit_mesaj)
        sonuc["mesaj_id"] = gonderilen.get("message_id")
        if yazdir:
            print(f"✅ Karşılama gönderildi (message_id {sonuc['mesaj_id']})")
        if sonuc["mesaj_id"] is not None:
            api.mesaj_sabitle(hedef, sonuc["mesaj_id"])
            sonuc["sabitlendi"] = True
            if yazdir:
                print("📌 Mesaj sabitlendi (sessiz bildirim)")
        elif yazdir:
            print("⚠️  message_id gelmedi; mesajı elle sabitle.")
    return sonuc


def hedef_coz(arg_hedef: str = None) -> str:
    for aday in (arg_hedef, os.getenv("TELEGRAM_GROUP_ID"),
                 os.getenv("TELEGRAM_CHANNEL_ID")):
        if aday and str(aday).strip():
            return str(aday).strip()
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Kanal/grup açılış paketi (varsayılan: kuru çalışma)")
    ap.add_argument("--hedef", help="kanal/grup @kullanıcı adı ya da -100… kimliği")
    ap.add_argument("--token", help="bot token (varsayılan: TELEGRAM_BOT_TOKEN)")
    ap.add_argument("--durum", action="store_true", help="yalnız durum (varsayılan davranış)")
    ap.add_argument("--uygula", action="store_true", help="açıklamayı yaz + karşılamayı gönder/sabitle")
    ap.add_argument("--atla-aciklama", action="store_true", help="açıklamayı yazma")
    ap.add_argument("--atla-sabit", action="store_true", help="sabit mesajı gönderme")
    ap.add_argument("--aciklama", help="açıklama metnini geçici olarak değiştir")
    args = ap.parse_args()

    token = (args.token or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    hedef = hedef_coz(args.hedef)
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN yok (--token ile verebilirsin).", file=sys.stderr)
        return 2
    if not hedef:
        print("❌ Hedef yok: --hedef ver ya da TELEGRAM_GROUP_ID/"
              "TELEGRAM_CHANNEL_ID tanımla.", file=sys.stderr)
        return 2

    api = TelegramAPI(token)
    try:
        durum(api, hedef)
    except KanalHatasi as hata:
        print(f"❌ {hata}", file=sys.stderr)
        return 1

    if not args.uygula:
        print("\nℹ️  Kuru çalışma: hiçbir şey değiştirilmedi. "
              "Uygulamak için: --uygula")
        return 0

    print()
    try:
        acilisi_uygula(api, hedef, aciklama=args.aciklama,
                       aciklama_yaz=not args.atla_aciklama,
                       sabit_yaz=not args.atla_sabit)
    except KanalHatasi as hata:
        print(f"❌ {hata}", file=sys.stderr)
        return 1
    print("\n🎉 Açılış paketi uygulandı. İlk bülten bir sonraki tarama turunda düşer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
