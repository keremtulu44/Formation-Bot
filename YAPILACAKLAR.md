# Formation-Bot — Yapılacaklar / Düzeltilecekler Listesi (tam)

> Kaynak: `FORMATION_BOT_SORUN_RAPORU.md` (teşhis) · Dal: `arena/01a0f318-formation-bot` (push edildi: `0bca8e5`)
> Öncelik: ★★★ merge/şablon öncesi şart · ★★ kısa vadede yapılmalı · ★ fırsat bulunca
> Efor: **1s** = bir satır/birkaç dakika · **K** küçük (yarım gün) · **O** orta (1-2 gün) · **B** büyük (yapısal)

---

## ÖZET TABLO

| ID | ★ | İş | Dosya / satır | Efor |
|---|---|---|---|---|
| A1 | ★★★ | `son_tarama_yukle()` çağrısını main_loop'a geri koy | `main.py:2266-2270` | 1s |
| A2 | ★★★ | Tatil/yarım gün sonsuz döngüsü (next_open=0 → 0 sn uyku) | `data.py:131-158`, `main.py:2515-2526` | K |
| A3 | ★★ | Ölü/yanlış kod yolları (5 kalem) | `notifier.py:211,255,582`, `main.py:2147,2166` | K |
| A4 | ★★ | TZ tutarlılığı (cooldown/kap sayaçları naive; kota 03:00'te sıfırlanıyor) | `notifier.py:144,294-330,370-393` | K |
| A5 | ★★ | `send_text()` 4096 koruması yok + başarısız gönderimde retry yok | `notifier.py:176-191` | K |
| A6 | ★★ | Gönderim sağlığı görünürlüğü (mock True dönüyor, /health hep 200) | `notifier.py:639-646`, `main.py:311-354` | K |
| A7 | ★★ | URL yolunda sır (`/test?k=`, `/webhook/<secret>`) + uçlarda rate limit yok | `health_server.py:33,88` | K |
| A8 | ★★ | Git'teki 28 `.pkl` + `pickle.load` yüzeyi | `data.py:549`, `bot_data/*.pkl` | K |
| A9 | ★ | `patterns_found` slot-bazlı tekrar sayacı (yanıltıcı metrik) | `main.py:1848` | 1s |
| A10 | ★ | Kap sayaçları komut/özet/digest'i saymıyor | `notifier.py:294-301` | K |
| B1 | ★★★ | "Bastırılan aday" sayacı + `/durum`'da tek satır | `main.py:167-192,427-500` | K |
| B2 | ★★★ | Digest şeffaflığı (12/21 göster) + limit env'e taşı | `main.py:2104,1937,2397` | 1s |
| B3 | ★★ | Digest tamponunu kalıcı yap (restart/kaçırma telafisi) | `telegram_alert_flow.py` | O |
| B4 | ★★ | Cooldown/kap engeline takılan acil olaylar için kuyruk+retry | `notifier.py:370-393` | O |
| B5 | ★★ | Tarama içi yazma amplifikasyonu (~4 MB/tarama, ~45 MB/gün) | `data.py:499-538,727-737`, `main.py:311-354` | O |
| B6 | ★★ | Kalite eşiği altı adaylar için sayaç + panel satırı | `main.py:1892`, `main.py:1026+` | K |
| B7 | ★★ | WATCH state'lerinin anlık/toplu kararı netleşsin (davranış değişikliği) | `config.py:295`, `main.py:1886-1895` | K |
| B8 | ★★ | Evren büyürse: pacing, panel 3800 bütçesi, digest/özet limitleri | `main.py:836-837`, `telegram_alert_flow.py:87` | K |
| B9 | ★ | Public kanal akışının netleştirilmesi | `notifier.py:211-221` | K |
| B10 | ★ | Çoklu örnek koruması (webhook'ta 409 yok, anahtarlar namespace'siz) | `telegram_commands.py:170`, `supabase_store.py:107` | K |
| C1 | ★★★ | Pazar/sağlayıcı sabitlerini config'e taşı (`.IS`, seans, takvim, evren, log dizini) | `data.py:992,1087`, `config.py:23-125,302` | O |
| C2 | ★★★ | `main.py` (2582 satır) katmanlara ayır; import yan etkilerini kaldır | `main.py:51-91` | B |
| C3 | ★★ | Supabase anahtarlarına proje namespace'i | `data.py:534`, `supabase_store.py:107` | K |
| C4 | ★★ | `DATA_DIR`'ı repo dışına al (canlıda `git pull` veriyi eziyor) | `.gitignore` dipnotu, `config.py:305` | K |
| C5 | ★★ | Test boşlukları: tatilde next_open, açılışta hydrate, digest limitleri | `test_tarama_zamani.py`, yeni testler | K |
| C6 | ★ | Doküman/şema senkronu (README 90/90→199, eski dal adı, `state:son_tarama`) | `README.md:168-190`, `supabase_schema.sql:20` | 1s |
| C7 | ★ | Ölü kod/araç temizliği | `data.py:952,1120`, `repo_teshis.py`, `logrotate.conf`, `.ps1` | K |

---

## A) DÜZELTİLMESİ GEREKENLER

### A1 ★★★ — `son_tarama_yukle()` çağrısı bu dalda yok (merge edilirse regresyon)
`main` (canlı) `main.py:1758`'de `supabase_store.ping()`'ten hemen sonra çağırıyor; bu dalda satır düşmüş, fonksiyon ve testleri duruyor ama hiçbir üretim yolu çağırmıyor.
**Etki:** bu dal `main`'e merge edilirse restart/gece uykusu sonrası `/panel`, `/canli`, 09:55 özeti boş gelir (PR #9'un çözdüğü sorun geri gelir).
**Yap:** `main.py:2266` (`supabase_store.ping()`) ile `2270` (`StockDequeManager(...)`) arasına `son_tarama_yukle(supabase_store)` ekle. + "açılışta çağrılıyor mu" regresyon testi (C5b).

### A2 ★★★ — Tatil ve yarım gün günlerinde sonsuz döngü
`is_bist_open()` tatili bilmiyor (`data.py:71-93`), `time_until_next_open()` tatil atlamıyor (`data.py:131-158`) → seans saatleri içindeki tatilde pencere kapalı ama `next_open = 0` → `sleep_time = 0` (`main.py:2517`) → döngü hiç uyumuyor.
**Ölçüm:** 2000 yineleme 0.09 sn ≈ **21.500 log satırı/sn**; tatil günü ≈ **600 milyon satır**; 2026'da 11 tatil + 3 yarım gün ≈ **90-100 saat**.
**Yap:** (1) `time_until_next_open` tatil/yarım gün atlasın, (2) kapalı dalda `sleep_time = max(sleep_time, 60)`, (3) test (C5a).

### A3 ★★ — Ölü / yanlış kod yolları
- **a)** `should_send_to_public` içindeki `SIKISMA_GUCLENIYOR` dalı iki yolda da `False` döndürüyor (`notifier.py:211-221`) → kanala sıkışma asla gitmiyor; ya kural netleşsin ya dal silinsin.
- **b)** `_build_active_formations_for_summary` içinde `_live_state.get_formations()` çağrılıyor ama **böyle bir metot yok** (`main.py:2147`; doğrusu `formations()`) → özet sessizce `last_snapshots` yolundan besleniyor, panel ile farklı kaynak.
- **c)** Aynı fonksiyonda `'contraction': None` (`main.py:2166`) → b düzeltilirse günlük özetin `⚡ SIKIŞANLAR` bölümü sessizce boşalır (karşılaştırma `>= 0.80`).
- **d)** `notifier.py:255` hesaplanıp kullanılmayan `[:10]` listesi (ölü niyet).
- **e)** `FORMASYON_GECERSIZ` mesaj şablonu (`notifier.py:582`) yazılmış ama hiçbir akış çağırmıyor.

### A4 ★★ — Zaman dilimi tutarsızlığı
Cooldown ve saatlik/günlük kap sayaçları **naive `datetime.now()`** (`notifier.py:144-145, 294-330, 370-393`); tarafın geri kalanı `Europe/Istanbul`. Render'da TZ set edilmediği için (ne `render.yaml` ne `.env.example`) süreç UTC çalışır → günlük kota **03:00 İstanbul**'da sıfırlanır, 00:00-03:00 mesajları "dünün" kotasından düşer.
**Yap:** sayaçları `ISTANBUL_TZ`'ye çevir **ve** Render'a `TZ=Europe/Istanbul` ekle.

### A5 ★★ — 4096 sınırı ve başarısız gönderim koruması
`send_text()` (`notifier.py:176-191`) `kirp()` kullanmıyor → uzun özet/digest sessizce HTTP 400 alabilir; ayrıca başarısız gönderimde retry/kuyruk yok (özet `last_summary_sent` yalnız başarı durumunda işaretlenir, ama acil olaylar kaybolur).
**Yap:** `send_text` içinde `kirp()`, başarısızlıkta sınırlı retry + log.

### A6 ★★ — "Sağlıklı görünme" riski
Token yok/yanlışken `send()` mock modda **`True`** dönüyor (`notifier.py:639-646`) → `alerts_sent` artar, heartbeat temiz görünür; `/health` her koşulda 200.
**Yap:** heartbeat'e `notifier_enabled`, `son_basarili_gonderim`, `son_gonderme_hatasi`, `bekleyen_bildirim`; `alerts_sent` yanına `alerts_attempted/failed`.

### A7 ★★ — Sırlar URL yolunda + uçlarda limit yok
`/test?k=<anahtar>` ve `/webhook/<secret>` sırrı yol/query'de taşıyor (`health_server.py:33, 88`) → Render/proxy erişim loglarına düşer (başlık doğrulaması zaten var, yol sırrı gereksiz). Ayrıca public uçlarda rate limit yok, `ThreadingHTTPServer` thread sayısı sınırsız.
**Yap:** sırrı yalnız başlığa al (yol için ayrı, sırsız bir yol harfi), basit IP/istek limiter ekle.

### A8 ★★ — Git'te 28 `.pkl` + `pickle.load`
`bot_data/` içinde 28 `.pkl` commitli ve `data.py:549` bunları `pickle.load` ile okuyor; public repo + `main`'den otomatik deploy zincirinde kod çalıştırma yüzeyi.
**Yap:** `.pkl`'leri git'ten çıkar (JSON yolu zaten mevcut, `load_from_disk` fallback'i çalışır) veya okumayı JSON'a sabitle.

### A9 ★ — Yanıltıcı metrik
`daily_stats['patterns_found']` benzersiz formasyon değil **slot-bazlı tekrar** sayacı (`main.py:1848`) → `/durum`'da "günlük formasyon kaydı" olarak şişik görünür.
**Yap:** benzersiz (hisse|TF) say veya satır metnini "slot kaydı" yap.

### A10 ★ — Kap sayaçları eksik sayıyor
Günlük/saatlik kap yalnız `send()` yolundan geçenleri sayıyor (`notifier.py:294-301`); komut yanıtları, özetler, digest, `/test` sayaç dışı → "120 mesaj/gün" tavanı gerçek toplamı garanti etmiyor.
**Yap:** tüm gönderim yollarını tek sayaçtan geçir.

---

## B) YAPILMASINI ÖNERDİĞİM İYİLEŞTİRMELER

### B1 ★★★ — "Kaç tanesini kullanmadım" göstergesi (senin asıl sorunun cevabı)
Bugün hiçbir yerde **bastırılan aday sayısı** yok. Öneri:
- `daily_stats`'e: `alerts_below_threshold`, `alerts_cooldown`, `alerts_cap_blocked`, `alerts_digest_overflow`, `alerts_state_disabled`.
- `/durum`'a tek satır: `Bugün: 21 aday üretildi · 4 push · 11 digest · 6 kapsam dışı state · 0 cooldown · 3 eşik altı`.
- Gün sonu özetine aynı satır.

### B2 ★★★ — Digest şeffaflığı
`📡 Gün içi izleme adayları (12/21 gösteriliyor)` + kesilenler için `… 9 aday daha (tam liste: /formasyonlar)`.
`limit=12` iki yerde sabit (`main.py:1937, 2397`) → `DEFERRED_DIGEST_LIMIT` env'ine taşı.

### B3 ★★ — Digest'i kalıcı yap
`DeferredAlertBuffer` tamamen bellekte (`telegram_alert_flow.py:42-113`): restart/uçuşta kayıp, gönderim başarısızsa tekrar yok, 18:45'te servis uykudaysa hiç gitmez ve telafi edilmez.
**Yap:** Supabase `state:digest_pending` + kaçırılan özet için sonraki uyanışta telafi.

### B4 ★★ — Engellenen acil olaylar için kuyruk
`notifier.can_send` cooldown/kap yüzünden `False` dönerse olay **tamamen kaybolur** (`notifier.py:370-393`).
**Yap:** kritik state'ler kuyruğa girsin, kap açılınca/cooldown dolunca gönderilsin; kuyruk derinliği heartbeat'te görünsün.

### B5 ★★ — Yazma amplifikasyonu
Tarama döngüsü içinde hisse başına: `save_to_disk()` (`data.py:499-538`, ~40 KB JSON/Supabase), `save_gunluk_to_disk()` (~50 KB), `write_heartbeat()` (`main.py:311-354`, Supabase UPSERT) + tur sonunda `save_all()`.
**Ölçüm:** tarama başına ≈ **4 MB**, günde ~9 tarama + manuel → **~40-50 MB/gün**; her Supabase isteği 8 sn×2 deneme → sağlayıcı yavaşsa tarama süresi ~13 dk tavanına yaklaşır.
**Yap:** tur sonunda batch yazım veya ayrı thread'e taşı; heartbeat'i dakikada 1'e sınırla.

### B6 ★★ — Eşik altı adayların görünürlüğü
Kalite eşiğinin altındaki kayıtlar yalnız `logger.debug` (`main.py:1892`) → normal log seviyesinde hiç iz yok, sayacı yok.
**Yap:** günlük sayaç + `/panel`'e `eşik altı N aday` satırı.

### B7 ★★ — WATCH state'lerinin anlık/toplu kararı (davranış değişikliği)
Bu dal `KIRILIM_ADAYI`, `SIKISMA_GUCLENIYOR`, `KIRILIM_HAZIRLIGI`'nı anlıktan **18:45 toplu**ya çevirdi; `BASARISIZ_KIRILIM` anlık oldu. Canlıdaki `main` bu 3 state'i anlık atıyor (`config.py:292-298` + kod içi KIRILIM_HAZIRLIGI).
**Yap:** karar verilip (a) `config.py`'de tek yerde tanımlansın, (b) README'ye davranış notu, (c) teste bağlansın. Şu an iki farklı davranış iki dalda yaşıyor.

### B8 ★★ — Evren ölçekleme (şablona geçmeden önemli)
- Pacing lineer: 48 hisse ≈ 2 dk, 120 hisse ≈ 5 dk (sadece Yahoo temposu).
- `/panel` karakter bütçesi: 48 hisse/192 slot dolu → 3359 karakter (kırpma yok); 60 hisse → `… ve 3 satır daha`, 96 → 39, 120 → 63.
- Digest 12 ve özet `3+3+5` sabitleri evren büyüse de sabit → görünürlük oranı düşer.
**Yap:** sabitleri config'e taşı, panel'i seviyeli raporlamaya çevir (özet ilk N, tam liste komutla).

### B9 ★ — Public kanal akışı
Kanala yalnız `FORMASYON_TAMAMLANDI`/`RETEST_BASARILI` + günlük özet gidiyor; özet kanal mesajında "durum" bilgisi yok.
**Yap:** hangi state'ler kanala gitsin kararı + durum notu.

### B10 ★ — Çoklu örnek koruması
Aynı token + aynı Supabase anahtarı ile iki kopya → çift mesaj + cache yarışı; 409 koruması yalnız yoklama modunda (`telegram_commands.py:170`), webhook modunda yok; anahtarlar namespace'siz.
**Yap:** anahtarlara örnek adı ekle (`formation-bot:cache:1h:...`), webhook moduna da kilit/singleton kontrolü.

---

## C) ŞABLON / YENİ PROJEYE TAŞIMADAN ÖNCE

### C1 ★★★ — Pazar ve sağlayıcı sabitlerini config'e taşı
`.IS` eki (`data.py:992, 1087`) · seans 09:50-18:10, mum kapanışı :30, günlük kapanış 18:30 (`config.py:76-89`, `data.py:41-43`) · elle bakılan tatil takvimi (2027 İslami bayramlar **boş**, `config.py:98-125`) · 48'lik sabit evren (`config.py:23-40`) · `LOG_DIR=/var/log/bist-bot` (`config.py:302`).

### C2 ★★★ — `main.py` katmanlarına ayır (2582 satır)
Şu an `import main` bile yan etkili: root logger'ı `basicConfig` ile ele geçiriyor, `/var/log/bist-bot` ve `./logs` açıyor, modül seviyesinde global thread/state kuruyor (`main.py:51-91`) → kütüphane olarak import edilemez.
**Öneri:** `patterns/` (motor — **zaten bağımsız**) · `orchestration/` (tarama, zamanlama) · `reporting/` (mesaj biçimleri; `_panel_raporu`, `_format_deferred_alert_summary` taşınır) · `transport/` (telegram, supabase) · `state/` (`live_state`, digest tamponu).

### C3 ★★ — Supabase anahtarlarına namespace
`cache:1h:<SYM>`, `state:*`, tablo `bot_store` (`data.py:534`, `supabase_store.py:107`) → proje/örnek adı prefix'i ekle ki ikinci proje aynı tabloyu ezmesin.

### C4 ★★ — Veri klasörünü repo dışına al
`bot_data/` git-tracked ve canlı sunucuda her taramada yeniden yazılıyor; `git pull` çakışır (uyarı `.gitignore` dipnotunda). **Yap:** `DATA_DIR` varsayılanını repo dışına al (örn. `/var/lib/<proje>/data`), repoda yalnız örnek veri tut.

### C5 ★★ — Test boşlukları
(a) tatilde `time_until_next_open` → > 0, (b) açılışta `son_tarama_yukle` çağrısı (A1'in sessiz kalmasının tek sebebi bu testin olmaması), (c) digest/özet limitlerinin uçtan uca testi, (d) yarım gün 13:05 sonrası döngü uykusu.

### C6 ★ — Doküman/şema senkronu
README: test sayıları `90/90` ve `6/6` (gerçek: 199 passed), eski dal adı `arena/01a0e2d0` (`README.md:168-190`). `supabase_schema.sql:20`: anahtar listesinde `state:son_tarama` yok.

### C7 ★ — Ölü kod/araç temizliği
`fetch_with_rate_limit` + `RATE_LIMIT_MIN/MAX` (`data.py:952`, `config.py:207`) · `mock_fetch_60d_1h` (yalnız `__main__` demo) · `repo_teshis.py` (0 referans) · `logrotate.conf` (systemd dışı, 0 referans) · `.ps1` dosyaları (Windows; Linux/Render hattında kullanılmıyor).

---

## D) HIZLI KAZANIMLAR (bugün, ~1 saat, hepsi düşük riskli)
1. **A1** tek satır (merge öncesi şart).
2. **A2** iki satır + test → tatil günü CPU/log felaketini keser.
3. **B2** digest başlığına `(12/21)` + limit env.
4. **B1** bastırılan aday sayaçları + `/durum` satırı.
5. **A3d/A3b** ölü kod ve yanlış metot adı temizliği.
6. **C6** doküman senkronu.

## E) ÖNERİLEN SIRA
1. **Hemen (merge öncesi):** A1 → A2 → A3 → C5 (yeni testler).
2. **Bu hafta:** B1, B2, B6, A4, A5, A9.
3. **Sonraki:** B3, B4, B5, A6, A7, A10, B7, B8.
4. **Şablon öncesi:** C1, C2, C3, C4, C7 (+ B9, B10).

*Bu liste teşhis amaçlıdır; uygulanmadı. A1-A2-B1-B2 hariç hepsi mevcut davranışı koruyan iyileştirmelerdir.*
