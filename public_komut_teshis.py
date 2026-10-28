# -*- coding: utf-8 -*-
"""Public (grup) komut teşhisi — 2026-10-29.

NEDEN: "public'te komutlar çalışmıyor" üç ayrı sebeple olabilir ve üçü de
dışarıdan AYNI görünür:

  1. **Hedef KANAL.** Telegram'da üyeler kanala mesaj yazamaz; admin gönderileri
     `channel_post` olarak gelir ve gönderen kişi bilgisi (`from`) YOKTUR →
     yöneticilik doğrulanamaz, komut çalıştırılamaz. Kanaldan komut İMKÂNSIZDIR.
  2. **Bot hedefte değil / kimlik yanlış.** `TELEGRAM_GROUP_ID` başka bir
     sohbeti gösteriyorsa mesajlar hiç gelmez veya "yetkisiz sohbet" sayılır.
  3. **Webhook teslim etmiyor.** `allowed_updates` içinde `message` yoksa ya da
     webhook kaydı ölü adrese bakıyorsa güncelleme hiç ulaşmaz.

Bu script üçünü de Telegram'a SORARAK ayırır ve ne yapılacağını yazar. Ağa
çıkar; hiçbir ayarı DEĞİŞTİRMEZ (salt-okunur).

KULLANIM:
    python public_komut_teshis.py
    python public_komut_teshis.py --grup -1001234567890   # env'i ez
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv opsiyonel
    pass

API = "https://api.telegram.org"
KOMUT_ALABILEN = ("group", "supergroup")


def _maskele(kimlik: str) -> str:
    kimlik = str(kimlik or "")
    return ("…" + kimlik[-4:]) if len(kimlik) > 4 else ("…" if kimlik else "?")


def _cagri(requests, token: str, method: str, govde: dict | None = None):
    try:
        yanit = requests.post(f"{API}/bot{token}/{method}", json=govde or {}, timeout=15)
    except Exception as exc:  # noqa: BLE001 - teşhis ağ hatasını raporlar
        return None, f"istek hatası: {type(exc).__name__}"
    try:
        veri = yanit.json() or {}
    except ValueError:
        return None, f"HTTP {yanit.status_code} (JSON değil)"
    if not veri.get("ok"):
        return None, str(veri.get("description") or f"HTTP {yanit.status_code}")
    return veri.get("result"), ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Public grup komut teşhisi")
    ap.add_argument("--grup", default="", help="Hedef sohbet (@ad ya da -100…); boş = env")
    ap.add_argument("--token", default="", help="Bot token (boş = TELEGRAM_BOT_TOKEN)")
    args = ap.parse_args(argv)

    try:
        import requests
    except ImportError:
        print("❌ requests yok: pip install -r requirements.txt", file=sys.stderr)
        return 2

    token = (args.token or os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN yok.", file=sys.stderr)
        return 2

    acik = os.getenv("PUBLIC_COMMAND_CHATS", "").strip()
    hedefler = [h.strip() for h in acik.split(",") if h.strip()]
    if not hedefler:
        for ad in ("TELEGRAM_GROUP_ID", "TELEGRAM_CHANNEL_ID"):
            deger = os.getenv(ad, "").strip()
            if deger:
                hedefler.append(deger)
    if args.grup:
        hedefler = [args.grup]
    if not hedefler:
        hedefler = ["(tanımsız)"]

    ham_acik = os.getenv("PUBLIC_COMMANDS_ENABLED", "1").strip().lower()
    komut_acik = ham_acik not in {"0", "false", "no", "off", "hayir"}

    print("🩺 Public komut teşhisi")
    print(f"   PUBLIC_COMMANDS_ENABLED = {ham_acik or '1'} → "
          f"{'açık' if komut_acik else 'KAPALI'}")
    print(f"   Hedefler: {', '.join(_maskele(h) for h in hedefler)}")
    print()

    hatalar = []
    for hedef in hedefler:
        print(f"— Hedef {_maskele(hedef)}")
        if hedef == "(tanımsız)":
            print("  ❌ Public komut hedefi yok: TELEGRAM_GROUP_ID / PUBLIC_COMMAND_CHATS")
            hatalar.append("hedef yok")
            continue
        sohbet, hata = _cagri(requests, token, "getChat", {"chat_id": hedef})
        if sohbet is None:
            print(f"  ❌ getChat başarısız: {hata}")
            print("     Bot bu sohbette değil ya da kimlik yanlış.")
            hatalar.append("getChat")
            continue
        tur = str(sohbet.get("type") or "?").lower()
        baslik = sohbet.get("title") or sohbet.get("username") or "?"
        print(f"  tip: {tur} · başlık: {baslik}")
        if tur in KOMUT_ALABILEN:
            print("  ✅ Komut alabilen bir sohbet (grup/supergroup).")
        elif tur == "channel":
            print("  🔴 KANAL: buradan komut ÇALIŞMAZ.")
            print("     • Üyeler kanala mesaj yazamaz (sadece yöneticiler gönderi paylaşır).")
            print("     • Admin gönderileri `channel_post` gelir; `from` alanı yoktur,")
            print("       bu yüzden 'yönetici mi' sorusu CEVAPLANAMAZ.")
            print("     ✅ Çözüm: bir GRUP açın (kanala bağlı tartışma grubu olabilir),")
            print("        botu gruba ekleyip YÖNETİCİ yapın ve grubun kimliğini")
            print("        PUBLIC_COMMAND_CHATS olarak tanımlayın:")
            print("          PUBLIC_COMMAND_CHATS=-1001234567890")
            print("        Kanal yayını TELEGRAM_GROUP_ID ile aynen sürer.")
            hatalar.append("kanal")
        elif tur == "private":
            print("  ⚠️ Bu bir DM sohbeti; public komut hedefi olarak grup beklenir.")

        ben, hata = _cagri(requests, token, "getMe")
        if ben:
            uye, hata2 = _cagri(requests, token, "getChatMember",
                                {"chat_id": hedef, "user_id": ben.get("id")})
            if uye is None:
                print(f"  ⚠️ Bot üyeliği okunamadı: {hata2}")
            else:
                durum = str(uye.get("status") or "?")
                print(f"  bot üyeliği: {durum}")
                if durum in ("left", "kicked"):
                    print("  ❌ Bot bu sohbette DEĞİL → hiçbir mesaj gelmez.")
                    hatalar.append("uyelik")
                elif durum not in ("administrator", "creator"):
                    print("  ⚠️ Bot yönetici değil. Komut için şart olan, komutu YAZAN")
                    print("     kişinin yönetici olmasıdır; botun yönetici olması önerilir.")
        print()

    # Webhook: güncellemeler gerçekten teslim ediliyor mu?
    bilgi, hata = _cagri(requests, token, "getWebhookInfo")
    print("— Webhook")
    if bilgi is None:
        print(f"  ⚠️ Okunamadı: {hata}")
    else:
        url = str(bilgi.get("url") or "")
        print(f"  {'kurulu' if url else 'YOK (yoklama modu)'}")
        if url:
            print(f"  bekleyen güncelleme: {bilgi.get('pending_update_count')}")
        turler = bilgi.get("allowed_updates") or []
        print("  izlenen türler: " + (", ".join(turler) if turler else "hepsi"))
        if turler and "message" not in turler:
            print("  🔴 `message` YOK: GRUP komutları bota hiç gelmez!")
            hatalar.append("allowed_updates")
        son_hata = str(bilgi.get("last_error_message") or "").strip()
        if son_hata:
            print(f"  ⚠️ son hata: {son_hata}")
            hatalar.append("webhook hata")

    print()
    if "kanal" in hatalar:
        print("SONUÇ: hedef KANAL — komut için GRUP gerekiyor (env değişikliği ŞART).")
    elif "hedef yok" in hatalar:
        print("SONUÇ: public komut hedefi tanımsız (TELEGRAM_GROUP_ID / PUBLIC_COMMAND_CHATS).")
    elif not komut_acik:
        print("SONUÇ: PUBLIC_COMMANDS_ENABLED kapalı → public komutlar devre dışı.")
    elif hatalar:
        print(f"SONUÇ: sorun(lar): {', '.join(sorted(set(hatalar)))}")
    else:
        print("SONUÇ: yapılandırma uygun görünüyor. Grupta /durum yazın; cevap gelmiyorsa")
        print("        komutu yazan hesabın o grupta YÖNETİCİ olduğundan emin olun.")
    return 0 if not hatalar else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
