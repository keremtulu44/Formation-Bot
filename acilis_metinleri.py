# -*- coding: utf-8 -*-
"""Kanal/grup AÇILIŞ METİNLERİ — tek kaynak.

Neden ayrı dosya: açıklama ve sabit mesaj hem `kanal_acilis.py` hem doküman
tarafından kullanılır; metin iki yerde yaşayıp ayrışırsa (biri güncellenip
diğeri unutulursa) kanaldaki gerçek ile depodaki anlatım çelişir.

Telegram sınırları:
  * Sohbet açıklaması (About / setChatDescription): en fazla 255 karakter
  * Tek mesaj: en fazla 4096 karakter (UTF-16 birimi; emoji 2 sayılır)

`test_kanal_acilis.py` bu sınırları ve zorunlu ibareleri doğrular; metin
değiştirilirken sınırın sessizce aşılması engellenir.
"""

# --- Kısa açıklama (kanal "Hakkında" alanı) ---------------------------------
# Üslup: ne olduğu + ne gönderdiği + sorumluluk reddi + X hesabı.
ACILIK_ACIKLAMASI = (
    "BIST formasyon takip panosu · 48 hisse, 4 zaman dilimi: saatlik bülten, "
    "18:45 kapanış özeti, Cuma doğruluk karnesi. Yatırım tavsiyesi değildir. "
    "X: @bisthisseveri"
)

# --- Sabitlenmiş karşılama mesajı -------------------------------------------
# Yeni gelen biri 30 saniyede şunları öğrenmeli: ne, ne zaman, ne YOK,
# sorumluluk kimde, veri nereden geliyor. Ayrıca "sinyal servisi" algısını
# baştan kırar: başarısızların gizlenmediği açıkça yazılır.
ACILIK_SABIT_MESAJ = """📌 BIST FORMASYON TAKİP PANOSU — nasıl çalışır?

Bu kanal bir sinyal servisi değil; otomatik bir formasyon takip panosudur. Bot, BIST'ten 48 hisseyi 4 zaman diliminde (1s · 2s · 4s · günlük) tarar ve YALNIZ kapanmış mumlarla çalışır.

📤 NE GÖNDERİLİR
• Tarama bülteni — yeni tamamlanan formasyon, teyitli kırılım ve başarılı retestler; aynı turda çıkanlar TEK mesajda
• 18:45 kapanış özeti — günün sayıları, yarının izleme listesi (ilk 5) ve "❌ N kırılım başarısız" satırı
• 09:55 sabah notu — o günün izleme listesi
• Cuma 18:45 — haftalık doğruluk karnesi (kaç sinyal, kaçı yönünde kapandı)

🕘 Beklenen hacim: sakin günde 2-3, hareketli günde 8-10 mesaj.

🚫 NE YOK
Al/sat emri, hedef fiyat, "kesin gider" iddiası yok. Başarısız kırılımlar gizlenmez; gün sonu özetinde ve karnede sayısı yayınlanır.

⚠️ YATIRIM TAVSİYESİ DEĞİLDİR
Her şey otomatik formasyon tespitidir: haber, bilanço, KAP veya kişisel görüş içermez. Getiri garantisi yoktur; geçmiş performans geleceği göstermez. Karar ve sorumluluk size aittir. Veri Yahoo Finance üzerinden gelir; gecikme veya kesinti olabilir.

🧭 Bot yalnız fiyat/hacim verisini ve formasyon geometrisini (üçgen, kama, bayrak) görür; bunun dışındaki hiçbir bilgiyi değerlendirmez.

Komutlar yalnızca hesap sahibinin özel mesajında çalışır.
X: @bisthisseveri · Bu mesaj zaman zaman güncellenir."""


def karakter_sayilari() -> dict:
    """Telegram sınırlarına karşı ölçüm (UTF-16 birimi: emoji 2 sayılır)."""
    def br(k: str) -> int:
        return len(k.encode("utf-16-le")) // 2
    return {
        "aciklama": br(ACILIK_ACIKLAMASI),
        "sabit_mesaj": br(ACILIK_SABIT_MESAJ),
        "aciklama_siniri": 255,
        "mesaj_siniri": 4096,
    }


if __name__ == "__main__":
    sayilar = karakter_sayilari()
    print(f"Açıklama : {sayilar['aciklama']}/{sayilar['aciklama_siniri']} karakter")
    print(f"Sabit    : {sayilar['sabit_mesaj']}/{sayilar['mesaj_siniri']} karakter")
    print()
    print(ACILIK_ACIKLAMASI)
    print()
    print(ACILIK_SABIT_MESAJ)
