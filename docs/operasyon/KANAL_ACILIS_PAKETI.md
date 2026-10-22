# KANAL AÇILIŞ PAKETİ (02.10.2026)

Bu belge, **@bisthisseveri** X hesabının Telegram ayağını kurmak için: kanal mı grup mu
kararı, hazır açıklama metni, hazır sabitlenmiş mesaj ve uygulama adımları.

---

## 1) Kanal mı, grup mu? — **Kanal** (net öneri)

| Ölçüt | 📣 Kanal | 👥 Grup (salt-okunur) |
|---|---|---|
| Yazma yetkisi | Doğası gerekti tek yönlü; üye **yazamaz** | "Mesaj gönderme" kapatılmalı; yanlışlıkla açılırsa spam |
| Üye listesi / gizlilik | Üyeler birbirini görmez | Üyeler birbirini görür |
| Moderasyon yükü | Yok | Üye gelince bildirim, davet, isim/avatar denetimi |
| Marka algısı | Kanal adı yazar, paylaşılabilir `t.me/...` | "Sohbet grubu" hissi; sinyal satıcısı algısına daha yakın |
| X (Twitter) bağlantısı | Profil linki için ideal, tek yönlü akış | Bağlantı da olur ama grup sohbeti beklentisi doğar |
| Üye sınırı | Pratikte sınırsız | Supergroup sınırsız ama yönetimi ağır |

**Neden bu hesap için kanal:** içerik zaten tek yönlü (bülten + özet + karne), marka
X hesabıyla taşınacak, soru-cevap ihtiyacı yok. Grup seçilirse kazanç sağlayan hiçbir
şey gelmiyor, buna karşılık her ayarın bozulma riski var.

**İleride yorum istersen:** Kanala bağlı **tartışma grubu** eklenir (Kanal ayarları →
Tartışma Grubu). Akış temiz kalır, isteyen yorum yazar, bot oraya hiçbir şey göndermez.
Yani "kanal mı grup mu" sorusunu şimdi cevaplamak zorunda değilsin: **kanal + (gerekirse)
bağlı tartışma grubu** en esnek yol.

> Teknik not: Bot tarafında ikisi de aynı env değişkenini kullanır
> (`TELEGRAM_GROUP_ID`, eski adı `TELEGRAM_CHANNEL_ID`). Kanal seçersen değer
> `@bisthisseveri` gibi bir kullanıcı adı ya da `-100…` kimliği olabilir. Kodu
> değiştirmeye gerek yok.

---

## 2) Kurulum — 6 adım

1. **Kanal aç:** Telegram → Yeni Kanal. Ad önerisi: `BIST Formasyon Takibi`
   (X hesabıyla uyum için açıklamada @bisthisseveri geçiyor).
2. **Herkese açık kullanıcı adı ver:** `@bisthisseveri` boşsa onu al; doluysa
   `@bisthisseveri_takip` ya da `@bisthisseveri_formasyon`. (Kullanıcı adı olmadan da
   çalışır ama X profilinden link veremezsin.)
3. **Botu yönetici yap:** Kanal → Yöneticiler → Bot Ekle → izinler:
   * **Mesaj gönderme** — zorunlu
   * **Mesajları sabitle** — sabit karşılama için (bu paket)
   * **Bilgiyi değiştir** — bot açıklamayı kendisi yazsın istersen (yoksa metni elle yapıştır)
4. **`.env`'e hedefi yaz:** `TELEGRAM_GROUP_ID=@bisthisseveri`
   (botun DM tarafı `TELEGRAM_CHAT_ID` kalır; DM özetleri de çalışmaya devam eder).
   **Render'da:** `render.yaml` blueprint'inde `TELEGRAM_GROUP_ID` tanımlı (`sync: false`);
   değeri Render → Environment → `TELEGRAM_GROUP_ID` alanına yaz. Blueprint'i
   güncellemeden çalışan servislerde alanı elle eklemek gerekir: canlı denetimde
   bu değişkenin eksik olduğu ölçülmüştü (Bulgu C).
5. **Botu yeniden başlat**, sonra kontrol et:
   ```bash
   .venv/bin/python kanal_acilis.py --durum
   ```
   Çıktı; kanal adını, botun yönetici olup olmadığını ve eksik izinleri ✅/❌ olarak
   gösterir. **Hiçbir şey yazmaz.**
6. **Açılış paketini uygula:**
   ```bash
   .venv/bin/python kanal_acilis.py --uygula
   ```
   Açıklamayı yazar, karşılama mesajını gönderir ve **sessiz** şekilde sabitler.
   (`--atla-aciklama` / `--atla-sabit` ile parça parça da uygulanabilir.)

---

## 3) Kanal açıklaması (161/255 karakter)

Açıklama, kanal aramasında ve link önizlemesinde görünen tek satırlık vitrindir.
Metnin kendisi `acilis_metinleri.py: ACILIK_ACIKLAMASI` içinde tek kaynaktır:

> **BIST formasyon takip panosu · 48 hisse, 4 zaman dilimi: saatlik bülten, 18:45 kapanış
> özeti, Cuma doğruluk karnesi. Yatırım tavsiyesi değildir. X: @bisthisseveri**

Neden bu üçleme: (1) ne olduğu, (2) ne sıklıkta ne geldiği, (3) sorumluluk reddi + X
bağlantısı. "Sinyal", "kazanç", "hedef" gibi kelimeler bilinçli olarak **yok** — hem
algı hem de Telegram/şikâyet riski açısından.

---

## 4) Sabitlenmiş karşılama mesajı (1334/4096 karakter)

Sabit mesajın işi: yeni gelenin 30 saniyede "bu ne, ne gelir, ne gelmez, sorumluluk
kimde" sorularını cevaplamak. Tam metin `acilis_metinleri.py: ACILIK_SABIT_MESAJ`:

> 📌 **BIST FORMASYON TAKİP PANOSU — nasıl çalışır?**
>
> Bu kanal bir sinyal servisi değil; otomatik bir formasyon takip panosudur. Bot,
> BIST'ten 48 hisseyi 4 zaman diliminde (1s · 2s · 4s · günlük) tarar ve **yalnız
> kapanmış mumlarla** çalışır.
>
> **📤 NE GÖNDERİLİR**
> • Tarama bülteni — yeni tamamlanan formasyon, teyitli kırılım ve başarılı retestler;
> aynı turda çıkanlar TEK mesajda
> • 18:45 kapanış özeti — günün sayıları, yarının izleme listesi (ilk 5) ve
> "❌ N kırılım başarısız" satırı
> • 09:55 sabah notu — o günün izleme listesi
> • Cuma 18:45 — haftalık doğruluk karnesi (kaç sinyal, kaçı yönünde kapandı)
>
> **🕘 Beklenen hacim:** sakin günde 2-3, hareketli günde 8-10 mesaj.
>
> **🚫 NE YOK**
> Al/sat emri, hedef fiyat, "kesin gider" iddiası yok. Başarısız kırılımlar gizlenmez;
> gün sonu özetinde ve karnede sayısı yayınlanır.
>
> **⚠️ YATIRIM TAVSİYESİ DEĞİLDİR**
> Her şey otomatik formasyon tespitidir: haber, bilanço, KAP veya kişisel görüş
> içermez. Getiri garantisi yoktur; geçmiş performans geleceği göstermez. Karar ve
> sorumluluk size aittir. Veri Yahoo Finance üzerinden gelir; gecikme veya kesinti
> olabilir.
>
> **🧭** Bot yalnız fiyat/hacim verisini ve formasyon geometrisini (üçgen, kama, bayrak)
> görür; bunun dışındaki hiçbir bilgiyi değerlendirmez.
>
> Komutlar yalnızca hesap sahibinin özel mesajında çalışır.
> X: @bisthisseveri · Bu mesaj zaman zaman güncellenir.

**Kritik cümle:** "Başarısız kırılımlar gizlenmez." Bu, grubu piyasadaki "sinyal
kanallarından" ayıran yer. Karne zaten simülasyonda `3/9 (%33)` gibi kötü sayıları da
yayınlıyor; sabit mesaj bunu baştan söylediği için kötü hafta sürpriz olmuyor.

---

## 5) X (Twitter) tarafı

- **Şimdi:** kanal linki X profiline eklenir (bio → `t.me/bisthisseveri`). Gün içi
  bültenden bir satırı ekran görüntüsü/alıntı olarak X'e taşımak en hızlı yol.
- **Sonra (opsiyonel):** otomatik X paylaşımı yalnız X API'si ile mümkün; ücretsiz
  katmanda yazma izni yok (temel plan ücretli). İstersen Faz 3 olarak konuşuruz:
  günün 18:45 özetini görsel kart olarak üretip X'e elle atmak da yeterli olur.

---

## 6) Yayına alma kontrol listesi

- [ ] Kanal açıldı, kullanıcı adı alındı
- [ ] Bot kanala **yönetici** eklendi (mesaj gönderme ✅)
- [ ] Sabitleme izni açık (sabit mesaj için)
- [ ] `.env` / Render → `TELEGRAM_GROUP_ID=@…` yazıldı, bot yeniden başlatıldı
- [ ] Açılış logunda `✅ Public hedef doğrulandı: <kanal> (channel) · yönetici=True · mesaj gönderme=True`
      satırı var (yoksa `❌` satırı sorunu söyler; heartbeat `public_hedef` alanı da taşır)
- [ ] `kanal_acilis.py --durum` → yönetici ✅, izinler ✅
- [ ] `kanal_acilis.py --uygula` → açıklama + sabit mesaj yerinde
- [ ] İlk bülten düştü (bir sonraki mum kapanışından sonra)
- [ ] X profiline `t.me/…` linki eklendi
- [ ] İlk hafta gözlem: mesaj sayısı, "çok/az" geri bildirimi, 429 var mı

---

## 7) Restart dayanıklılığı (canlı denetim sonrası)

Render gün ortasında yeniden başlatıldığında (deploy/restart) yayın **kaldığı yerden**
devam eder; günlük durum `DATA_DIR/gonderim_durumu.json` içinde `gunluk` anahtarıyla tutulur:

| Korunan | Ne olurdu (düzeltme öncesi) |
|---|---|
| Günlük sayaçlar (`tarama_sayisi`, `basarisiz_kirilim`, `alerts_sent`, `stocks_scanned`) | 18:45 kanal özeti eksik sayı basardı ("❌ 8 / 8 tarama") |
| Özet işaretleri (`09:55`, `18:45` + `public:` kopyaları) | 09:55 sabah notu restart sonrası **ikinci kez** giderdi |
| Public bütçe (`gun_sayac`, `saatlik_ts`) | Günlük/saatlik tavan sıfırlanır, spam koruması zayıflardı |
| Gönderilememiş bülten kuyruğu | Tur ortasında restart'ta bültendeki olaylar kaybolurdu |

Gün değişince kayıt kendiliğinden sıfırlanır (dünün sayaçları bugüne taşınmaz).
"Aynı anda iki örnek" koruması için ayrıca Supabase tekil örnek kontrolü vardır.

## 8) Notlar

- **Bildirim gürültüsü:** Sabitleme `disable_notification=True` ile yapılır; sabit
  mesaj abonelere ekstra bildirim atmaz.
- **Açıklama değişirse:** metni `acilis_metinleri.py` içinde güncelle, testler sınırı
  ve zorunlu ibareleri kontrol eder, sonra `kanal_acilis.py --uygula --atla-sabit`.
- **Mesaj düzenleme:** Sabit mesaj zamanla eskirse (ör. hacim değişirse) yeni metni
  gönderip sabitleyebilirsin; eski sabitleme yeni pin ile otomatik kalkar.
