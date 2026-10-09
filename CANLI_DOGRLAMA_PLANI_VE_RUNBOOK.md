# Kontrollü Canlı Doğrulama Planı ve Runbook (Aşama 4)

**Durum:** Plan belgesidir; bu görevde HİÇBİR canlı test çalıştırılmadı. Her adım
`[ONAY GEREKLİ]` etiketi taşıyorsa kullanıcıdan açık izin gerekir. Gizli değerler
(token/anahtar) bu belgede VE çıktılarda asla yazdırılmaz; yalnızca değişken adları
anılır.

## 0. Ortak önkoşullar

- Çalışacak kod: test suite'i geçmiş tek commit'li sürüm + onaylı çalışma ağacı.
- Environment: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, (opsiyonel) `TELEGRAM_CHANNEL_ID`,
  `TELEGRAM_WEBHOOK_SECRET`, `SUPABASE_URL`, `SUPABASE_KEY`, `RENDER_EXTERNAL_URL`.
  Değerler yalnızca Render Environment panelinden girilir; log/mesaj/rapora kopyalanmaz.
- Tek instance: Render'da ikinci servis/worker KAPALI; autoDeploy kararlı.
- Test hedefi ayrımı: Telegram testleri mümkünse ayrı bir test chat'ine; üretim Supabase
  yerine ayrı tablo/schemada test store tercih edilir.
- Saat penceresi: test başlangıç/bitiş saati, seans takvimi (09:30-18:30 İstanbul) önceden yazılır.

## 1. Yahoo Finance doğrulaması

| Adım | Yöntem | Başarı ölçütü | Kanıt türü |
|---|---|---|---|
| 1.1 Sembol eşlemesi | 48 sembol için tek seferlik `yfinance.Ticker("<SYM>.IS").history(period="5d", interval="1h")` betiği (ağ erişimi olan makinede, elle) | 48/48 dolu DataFrame; beklenmedik boş liste yok | STAGING |
| 1.2 `.IS` desteği | 1.1 çıktısında sembol başına bar sayısı ≥ 50 (5d) | eksik sembol yok; eksikse ACTIVE_STOCKS kararı | STAGING |
| 1.3 Tazelik | Son bar zamanı son 1H kapanışına ≤ 10 dk (seans içi) | her sembolde `son_bar_yasi_dk` ≤ 70 dk | STAGING |
| 1.4 Rate-limit / kısmi hata | Bot'u 1 seans boyunca normal taramada çalıştır | heartbeat `fetch_failures` ≤ birkaç; `fetch_retry_recovered` artıyor | ÜRETİM [ONAY GEREKLİ] |
| 1.5 Boş/eski yanıt | Sağlayıcı eski bar döndüğünde `stale_stocks`/`data_stale` heartbeat'te | `VERİ ESKİ` uyarısı görünür; sessiz analiz yok | ÜRETİM [ONAY GEREKLİ] |
| 1.6 Cache fallback | 1.4'te hata çıktığında seans dışı cache 14 gün kuralıyla kullanılır | `Eksik tarama: X/Y` raporu; başarı gibi yayınlanmaz | ÜRETİM [ONAY GEREKLİ] |

Önkoşul: ağ erişimi yalnızca kullanıcı onaylı makinede; bu sandbox'ta çalıştırılmaz.

## 2. Render doğrulaması

| Adım | Yöntem | Başarı ölçütü |
|---|---|---|
| 2.1 Restart davranışı | [ONAY GEREKLİ] Render panelinden Manual Restart (seans dışı) | Bot açılışta Supabase/disk cache yükler; ilk yükleme logu 48 hisseyi listeler; /health 200 |
| 2.2 Disk varsayımı | Restart sonrası `bot_data/*.pkl` sayısı | Free disk kalıcı DEĞİL: sıfırlandıysa Supabase/İLK YÜKLEME devrede; kalıcı disk varsa dosyalar aynı |
| 2.3 Tek instance | Render metric/service listesi | tek çalışan instance; ikinci başlatma denemesi yapılmaz |
| 2.4 Zamanlanmış görevler restart sonrası | Restart 09:30 sonrası yapılırsa | `last_summary_sent` boş başlar; gün içinde aynı `daily-summary` idempotency key'iyle ikinci mesaj gitmez |
| 2.5 Hafta sonu restart | Cumartesi restart | tarama başlamaz (pencere kapalı); post-close koşulundaki risk Bölüm 3'te kullanıcı kararına bağlı |

## 3. Supabase doğrulaması (üretim verisine dokunmadan)

| Adım | Yöntem | Başarı ölçütü |
|---|---|---|
| 3.1 Bağlantı | `SUPABASE_URL/KEY` ile `ping()` + `get_many(["state:heartbeat"])` okuma | yanıt hızlı; hata varsa bot yerel cache ile çalışmaya devam eder (KOD: main_loop supabase_store None yolu) |
| 3.2 Snapshot okuma | AYRI bir test anahtarı/tablosuyla (`bist_bot_state_test` gibi) yaz-ok-sil | döngü tamamlanır; üretim tablosuna dokunulmaz [ONAY GEREKLİ] |
| 3.3 Bozuk/kısmi veri | Test tablosuna bozuk JSON satırı yaz | `hydrate_from_supabase` satırı atlar; bot açılır (TEST: satır düzeyi kontroller Aşama 4'te eklendi) |
| 3.4 Disk+Supabase birleştirme | Uzakta eski timestamp, diskte yeni | daha yeni kazanır (KOD: merge faile-closed; notifier cooldown birleştirme testleri) |
| 3.5 Üretim verisi | YALNIZCA okuma; yazma/silme yok | hiçbir upsert üretim tablosuna test sırasında yapılmaz [ONAY GEREKLİ] |

## 4. Telegram doğrulaması

| Adım | Yöntem | Başarı ölçütü |
|---|---|---|
| 4.1 Kimlik | `getMe` çağrısı (bot çalıştırılmadan tek istek) [ONAY GEREKLİ] | token geçerli; bot kullanıcı adı beklendiği gibi |
| 4.2 Chat yapılandırması | `sendMessage` ile TEST hedefine "merhaba" mesajı [ONAY GEREKLİ] | yalnız test chat'ine 1 mesaj; chat_id doğru |
| 4.3 Kabul → sent | 4.2 sonrası outbox JSON'da `status: sent`, `attempts: 1` | yerel kayıt kabul ile eşleşir |
| 4.4 Rate limit | 4.2'yi 3 kez hızlı tekrarla [ONAY GEREKLİ] | 429'da `retry_after` saygılı bekleyiş; dead-letter'a düşmez |
| 4.5 Tekrar/restart | 4.2'yi eden process'i kabul anında sonlandır [ONAY GEREKLİ] | restart sonrası aynı idempotency key ile ikinci mesaj GİTMEZ; ancak 'kabul-sonrası-crash' penceresinde TEK TEKRAR mümkündür — at-least-once sözleşmesi (TEST kanıtı: test_crash_after_remote_acceptance_is_ambiguous_and_at_least_once) |
| 4.6 Public kanal | Test kanalına /canli formatında tek mesaj [ONAY GEREKLİ] | DM formatından farklı, private context içermeyen mesaj |

## 5. Çalıştırma runbook'u

1. **Önkoşullar:** env değişkenleri panelde tanımlı (değerler yazdırılmaz); test hedefi üretimden ayrı; tek instance; başlangıç `git status` + `bot_data` checksum kaydı.
2. **Test aralığı:** başlangıç/bitiş saati İstanbul; test sırasında manuel müdahale yapılmaz; tüm gözlemler log + heartbeat + outbox JSON'dan okunur.
3. **Başlangıç koşulu:** `/health` 200 + ilk tarama `tamamlandi` + `fetch_ok`/48.
4. **Bitiş koşulu:** planlanan pencere dolduğunda ya da herhangi bir STOP kriteri tetiklendiğinde.
5. **Başarı ölçütleri:** (a) 48/48 fetch ok veya eksikler raporlu; (b) DM public ayrımı korunur; (c) outbox `sent`/`dead` oranı beklenen; (d) aynı event ID için tek transport; (e) hafta sonu/tatil davranışı seçilen politikaya uygun.
6. **STOP kriterleri:** imkânsız OHLCV ile üretilen event; seans içinde >120 dk stale veriyle event; aynı event'in iki kez transport edilmesi; `prepared/pending/sending` birikimi (>10 dk); açıklanamayan dead-letter; tekrarlayan 429/5xx; iki sender instance.
7. **Mesaj tekrarlanırsa:** (1) mesajı yoksay, botu durdurma; (2) outbox JSON'da event ID + `attempts` + `sent_at` kaydet; (3) Telegram message_id ile eşleştir; (4) aynı event ID'nin iki kaydı varsa duplicate penceresi olarak raporla; (5) elle yeniden gönderim YAPMA.
8. **Veri güncelliği bozulursa:** heartbeat `stale_stocks`/`data_stale` izle; 2 art arda seansta `fetch_ok < 24` ise inceleme başlat; seans içi >20 saat veri yok modu — semboller raporlanır.
9. **Supabase/sağlayıcı kesilirse:** Supabase erişilemezse bot yerel cache ile devam eder (KOD: `SupabaseStore.from_env()` None yolu); kesinti >1 seans ise önce 1.6 fallback davranışı doğrulanır; bot yeniden başlatılmaz.
10. **Rollback:** önce yeni scan/send'i durdur (Render suspend) [ONAY GEREKLİ]; local + Supabase state yedeği yetkili operatörce; `prepared/sending` kayıtları destekleyen sürümde drain; son bilinen iyi sürüme dön; state restore edilmeden üzerine yazılmaz.
11. **Onaylar:** canlı Telegram mesajı, Render restart/deploy, üretim Supabase erişimi — her biri ayrı ve açık kullanıcı onayına tabidir.

## 6. Bu plandaki kanıt türleri

- **KOD:** kaynak incelemesi (dosya:satır) — bu sandbox'ta yapıldı.
- **TEST:** izole pytest, sahte transport/store, tmp disk — bu sandbox'ta yapıldı.
- **STAGING:** ayrı ortamda gerçek servis çağrısı — YAPILMADI.
- **ÜRETİM:** canlı Render/Supabase/Telegram — YAPILMADI ve bu görevde yasak.
