# Formation-Bot — Sorun / Görünürlük Raporu

> **Salt analiz.** Hiçbir kod değiştirilmedi, hiçbir dosya repo içinde oluşturulmadı.
> İnceleme anı: `0bca8e5` (dal `arena/01a0f318-formation-bot`), testler **199/199 yeşil**.
> Ölçümler `bot_data/` içindeki gerçek cache ile ve gerçek fonksiyonlar çağrılarak yapıldı.

---

## 0. Kısa cevap (3 satır)

1. **Evet, "18 üretip 3–5'inden bahsetme" gerçek ve tasarımsal.** Uçtan uca 7 kapı var; en sert olanı günlük özetin `3 + 3 + 5` satırla sınırlı olması ve digest'in sabit `12` ile kırpılması.
2. **"30 ürünün 12'sini kullanmadın" diyen tek yer `/panel`** (`dolu slot 21/192`, `TOP 12 ANLAMLI ADAY (21 kayıt içinden)`). Başka bir yerde *bastırılan* adayların sayısı yok — bu, eklenmesi en kolay görünürlük kazancı.
3. **Temel/şablon olarak kullanırken en riskli 3 şey:** (S1) tatil/yarım gün günlerinde sonsuz döngü, (S2) kalıcılığın yazılıp geri yüklenmemesi, (S3) raporlama katmanındaki ölü/yanlış kod yolları. Gerisi orta/düşük öncelikli.

---

## 1. Üretim → Telegram hunisi (ölçülü)

### 1.1 Kapılar

| # | Kapı | Nerede | Etki |
|---|---|---|---|
| 1 | `state in IMMEDIATE_ALERT_STATES` (yalnız 4 state) | `config.py:295-300`, `main.py:90` | Acil push yalnız: `KIRILIM_TEYITLI`, `RETEST_BASARILI`, `FORMASYON_TAMAMLANDI`, `BASARISIZ_KIRILIM` |
| 2 | TF'e göre kalite eşiği (1h≥80, 2h≥78, 4h≥75, 1d≥70) | `config.py:288-294` | Altındaki her kayıt sessizce düşer (log bile `debug`) |
| 3 | 4 saat cooldown (hisse+desen+TF+state) | `notifier.py:370-393` | Aynı olay 4 saatte bir kez |
| 4 | Saatlik 20 / günlük 120 mesaj kapı | `config.py:169-170` | Aşılırsa yalnız "kritik state"ler geçer |
| 5 | Erteleme tamponu: yalnız 6 WATCH state + kalite eşiği + **`limit=12`** | `telegram_alert_flow.py:16-22, 87`, `main.py:1937, 2397` | Gün içi adayların **en yüksek kaliteli 12'si** gösterilir, kalanı hiç görünmez |
| 6 | Acil mesaja eklenen bağlam **`[:3]`** | `main.py:1939`, `notifier.py:607` | Mesaj başına en fazla 3 yan aday |
| 7 | Günlük özet gövdesi: `tamamlanan[:3]`, `retest[:3]`, `sikisan[:5]` | `notifier.py:261, 265, 269` | Özet **en fazla 11 satır**; gerisi yalnız sayı olarak ("TAMAMLANAN (7)") |

### 1.2 Gerçek veriyle ölçüm (cache taraması, 48 hisse)

```
taranan slot 112 · canlı formasyon kaydı 21 · kalite eşiğini geçen 15
  → acil push adayı  : 3  (yalnız 2'si eşik üstü)
  → digest adayı     : 11 (limit 12'ye takılmadı; 20 olsa 8'i kaybolacaktı)
  → hiçbir push'a girmeyen state: 6  (OLGUNLASIYOR ×3, FORMASYON_ZAYIFLADI ×3)
  → günlük özet metninde listelenen: 4 satır  (21 kayıttan)
```

**Hangi state nereye düşer?**

| State | Acil push | 18:45 digest | Günlük özet gövdesi | Sadece `/panel`, `/formasyonlar` |
|---|---|---|---|---|
| ADAY_OLUSUYOR, GEOMETRI_ADAYI, FORMASYON_TANIMLANDI, OLGUNLASIYOR | — | — | — | ✅ |
| SIKISMA_GUCLENIYOR | — | ✅ (≤12) | ✅ (`sikisan[:5]`, daralma ≥ %80) | — |
| KIRILIM_HAZIRLIGI, KIRILIM_DENEMESI, KIRILIM_ADAYI | — | ✅ (≤12) | — | — |
| RETEST_BEKLENIYOR, RETEST_EDILIYOR | — | ✅ (≤12) | — | — |
| KIRILIM_TEYITLI, RETEST_BASARILI, FORMASYON_TAMAMLANDI, BASARISIZ_KIRILIM | ✅ | — | (yalnız tamamlanan/retest sayaç+sınıfı) | — |
| FORMASYON_ZAYIFLADI, FORMASYON_GECERSIZ, KIRILIM_TEYIT_ALAMADI | — | — | — | ✅ |

> Yani "18 çıktı"nın 4'ü push, 12'si sabah/akşam özeti dışında hiçbir yere gitmiyor; **`OLGUNLASIYOR` gibi gerçekten üretilen state'ler Telegram'da hiç görünmüyor.**

### 1.3 Yan bulgu: ölü kod "10'luk liste" beklentisi yaratıyor

`notifier.py:255` → `sirali = sorted(...)[:10]` hesaplanıyor ama **hiçbir yerde kullanılmıyor**; basılan şey `3/3/5`. Yani "top 10 özet" niyeti koda hiç yansımamış (ölü satır). Aynı şekilde `_deferred_alert_buffer.items(..., limit=12)` çağrısı iki yerde sabit kodlu (`main.py:1937, 2397`) — konfigüre edilemiyor.

---

## 2. "Kaç tanesini kullanmadım?" göstergesi var mı?

**Var (kısmen):**

| Yer | Ne söylüyor |
|---|---|
| `/panel` | `dolu slot 21/192` + TF kırılımı (`1h 6/48 ort q84 · …`) + `TOP 12 ANLAMLI ADAY (puan) (21 kayıt içinden)` → **kapsamı en iyi anlatan yer burası** |
| `/formasyonlar` | `… ve 6 tane daha` (ilk 15 gösterilir, `main.py:591`), `Toplam 21 canlı formasyon · son başarılı tarama 48/48 hisse` |
| `/durum` | `Sonuçtaki formasyon: 21`, kapsam `48/48 hisse`, fetch/veri tazeliği |
| `/canli` | Kaliteye göre ilk 20 (`main.py:658`) |

**Yok:**

- **Bastırılan aday sayacı yok.** `daily_stats` içinde `alerts_sent` var, `alerts_skipped`/`alerts_below_threshold`/`alerts_cooldown`/`alerts_digest_overflow` yok (`main.py:167-192`).
- Digest başlığı **"12/21 gösteriliyor"** demiyor (`_format_deferred_alert_summary`, `main.py:2104`).
- Kalite eşiği altında kalan kayıtlar yalnız `logger.debug` ile düşüyor (`main.py:1892`) → normal log seviyesinde **hiç iz yok**.
- Cooldown/kap yüzünden gönderilemeyen acil olaylar hiçbir yerde kuyruklanmıyor; `notifier.send()` `False` dönüyor, sayaç tutulmuyor.

**En düşük riskli iyileştirme fikri (kod yazmadan öneri):** `/durum`'a tek satır → `Bugün: 21 aday üretildi · 4 push · 11 digest · 6 eşik altı · 0 cooldown · 3 state kapsam dışı`. Digest başlığına da `(21 adayın en iyi 12'si)` eklenebilir. Bunlar formasyon mantığına hiç dokunmaz.

---

## 3. Temel/şablon olarak kullanırken sorun çıkaracak noktalar

### S1 — Tatil ve yarım gün günlerinde sonsuz döngü (YÜKSEK)

`is_bist_open()` **tatili bilmiyor** (`data.py:71-93`: yalnız hafta sonu + saat). `time_until_next_open()` de tatil atlamıyor (`data.py:131-158`). Sonuç, seans saatleri içindeki bir tatil gününde:

```
data.py: is_bist_open → True   ama   tarama_penceresi_acik_mi → False
main.py:2515  wait_open = time_until_next_open(now)   → 0.0
main.py:2517  sleep_time = min(0.0, 300)             → 0.0
main.py:2526  _bekle_veya_tarama(0.0)                → hemen False
→ döngü hiç uyumadan yeniden başlar (log: "... 0.0dk uyku (açılışa 0.0sa)")
```

Ölçüm: aynı gövde 2000 kez **0.09 sn** → **~21.500 log satırı/saniye**. Bir tatil günü 09:50–18:10 arası ≈ **600 milyon satır** log + tek çekirdek tam dolu. 2026 takviminde 11 tam tatil günü + 3 yarım gün (yarım günde 13:05–18:10 arası **~5 saat** aynı şekilde dönüyor; ölçtüm: 28.10.2026 15:00 → `next_open=0`). Yılda ≈ 90–100 saat.

**Neden testler yakalamıyor:** `test_tarama_zamani.py:243-244` tatilde *pencereyi* test ediyor, `time_until_next_open`'ı tatil için test etmiyor.

**Düzeltme yönü:** `next_open` hesabı tatil/yarım gün atlasın **ve** döngüde taban uyku olsun (`max(sleep_time, 60)`). Şablon açısından kritik: ana döngü "kapanış" dalında asla 0 ile dönmemeli.

### S2 — Kalıcılık yazılıyor ama geri yüklenmiyor (YÜKSEK)

`son_tarama_kaydet()` her başarılı taramada çağrılıyor (`main.py:2017`, `main.py:2555`) → disk + Supabase `state:son_tarama`. Ama **`son_tarama_yukle()` (`main.py:1337`) hiçbir üretim yolunda çağrılmıyor**; yalnız `test_son_tarama_kaliciligi.py` içinden çağrılıyor.

Etkisi: Render her restart / gece uykusu sonrası `_live_state` **boş** başlıyor →
- `/panel`, `/formasyonlar`, `/durum` → "bu oturumda henüz başarılı analiz yok",
- 09:55 sabah özeti → `lifecycle_manager.last_snapshots` de boş olduğu için "Şu an aktif yüksek kaliteli formasyon yok",
- yani yazmak için yazılan snapshot pratikte sadece Supabase'de duruyor, okunmuyor.

### S3 — Raporlama katmanında ölü/yanlış yollar (YÜKSEK-ORTA)

1. `notifier.py:255` → kullanılmayan `[:10]` (bkz. §1.3).
2. `main.py:2137-2170` `_build_active_formations_for_summary()` → `_live_state.get_formations()` çağırıyor; **`LiveState`'te böyle bir metot yok** (yalnız `formations()`, `live_state.py:225`). `hasattr` yüzünden sessizce hep `lifecycle_manager.last_snapshots` yoluna düşüyor → **özet ile `/panel` farklı kaynaklardan besleniyor**, ikisi tutarsız olabiliyor.
3. `notifier.py:211-221` `should_send_to_public()` içindeki `SIKISMA_GUCLENIYOR` özel dalı **iki yolda da `False`** döndürüyor → kanala sıkışma hiç gönderilemez; kod okuyanda "gönderilebilir" izlenimi bırakan ölü dal.
4. Ölü dalın içindeki `'contraction': None` (`main.py:2166`) şu an zararsız (dal hiç çalışmıyor) ama dal düzeltilir/aktive edilirse günlük özetin `⚡ SIKIŞANLAR` bölümü **sessizce boşalır** (karşılaştırma `contraction >= 0.80`).

### S4 — Erteleme (digest) tamponu kırılgan (ORTA)

`DeferredAlertBuffer` tamamen **bellekte ve güne bağlı** (`telegram_alert_flow.py:42-113`): restart/sleep'te içerik kaybolur, gönderim başarısız olursa (429/400) tekrar denenmez, gün değişince silinir. 18:45'te servis uykudaysa (Render Free) digest hiç gitmez ve telafi edilmez. Şablonda "ertelenen bildirim" kalıcı kuyruk olmalı.

### S5 — Tarama döngüsünün içinde ağ I/O + yazma amplifikasyonu (ORTA)

Her hisse için tarama sırasında:
`save_to_disk()` (`data.py:499-538`, ~360 bar JSON ≈ 40 KB → Supabase UPSERT) + `save_gunluk_to_disk()` (~50 KB) + `write_heartbeat()` (`main.py:311-354`, Supabase UPSERT) + tarama sonunda yine `save_all()`.

- Tarama başına ≈ **4 MB yazma**, günde ~9 otomatik + manuel taramalar → **~40-50 MB/gün**.
- Her Supabase isteği 8 sn timeout × 2 deneme (`supabase_store.py:198-225`) → sağlayıcı yavaşlarsa tarama süresi hisse başı ~16 sn'ye kadar uzayabilir (48 hisse için teorik tavan ~13 dk; mum aralığı 60 dk olduğu için görece güvenli ama drift riski burada).
- **Şablon için:** döngü içinde biriktirip tur sonunda tek batch yaz veya yazmayı ayrı thread'e al.

### S6 — Zaman dilimi tutarsızlığı (ORTA)

`notifier.py` cooldown ve saatlik/günlük kap sayaçları **naive `datetime.now()`** kullanıyor (`144-145, 294-330, 370-393`); tarafın geri kalanı `Europe/Istanbul`. Render'da TZ set edilmediği için (ne `render.yaml` ne `.env.example`) süreç UTC çalışır:

- günlük mesaj kotası gece yarısı UTC'de, yani **03:00 İstanbul'da** sıfırlanır,
- `state:telegram_caps.gunluk_tarih` UTC günü yazılır,
- 00:00–03:00 arasındaki mesajlar "dünün" kotasından düşer.

Hata üretmez ama şablonda "gün" kavramı karışır; TZ'yi açıkça sabitlemek doğru olur.

### S7 — "Sağlıklı görünme" riski (ORTA)

`notifier.send()` içinde `enabled == False` iken **`True` dönüyor** (`notifier.py:639-646`, mock mod). Token yanlış/eksik olursa: `alerts_sent` artar, heartbeat temiz görünür, `/health` her koşulda 200 döner; tek iz açılıştaki bir satır (`check_connection`). Şablonda heartbeat'e `notifier_enabled`, `son_basarili_gonderim`, `son_gonderme_hatasi` alanları eklenmeli.

### S8 — Tek pazar/tek sağlayıcı varsayımları (ORTA)

Başka bir projeye temel yaparken birebir taşınacak ve sorun çıkaracak sabitler:

| Sabit | Yer |
|---|---|
| `.IS` sembol eki | `data.py:992`, `data.py:1087` |
| Seans 09:50–18:10 / mum kapanışı :30 / günlük kapanış 18:30 | `config.py:76-89`, `data.py:41-43` |
| Elle bakılan tatil takvimi (2027 İslami bayramlar boş) | `config.py:98-125` |
| 48 sembollük sabit evren | `config.py:23-40` |
| `LOG_DIR=/var/log/bist-bot` | `config.py:302` |
| Supabase anahtar şeması `cache:1h:<SYM>`, tablo `bot_store` (namespace yok) | `data.py:534`, `supabase_store.py:107` |
| BIST'e özel Telegram metinleri/emoji/etiketler | `notifier.py`, `main.py:385-399` |

### S9 — `main.py` (2582 satır) + import yan etkileri (ORTA)

`import main` etmek: kök logger'ı `basicConfig` ile ele geçirir, `/var/log/bist-bot` altına yazmayı dener, `./logs` açar, modül seviyesinde `_live_state`, `_deferred_alert_buffer`, threading primitifleri kurar (`main.py:51-91`). Yeni projede "kütüphane" gibi import edilecekse ilk patlayacak yer burası. Temiz ayrım önerisi: `patterns/` (motor — **zaten bağımsız çalışıyor**) · orchestration (tarama/zamanlama) · reporting (mesaj biçimleri) · transport (telegram/supabase) · state (`live_state`).

### S10 — Çoklu örnek ve ölçek (ORTA-DÜŞÜK)

- Aynı token + aynı Supabase anahtarıyla iki kopya → çift mesaj, cache yarışı; 409 koruması yalnız yoklama modunda (`telegram_commands.py:170-172`), webhook modunda koruma yok. Şablonda anahtarlara örnek adı eklenmeli (namespace).
- **Evren büyürse ölçtüğüm sınırlar:** pacing lineer (48 hisse ≈ 2 dk sadece Yahoo temposu; 120 hisse ≈ 5 dk + analiz). `/panel` 3800 karakter bütçesine 60 hissede takılmaya başlıyor:
  - 48 hisse (192 slot dolu) → 3359 karakter, kırpma yok
  - 60 hisse → `… ve 3 satır daha`, 96 hisse → `… ve 39 satır daha`, 120 hisse → `… ve 63 satır daha`
- Digest/özet sınırları (12 / 3+3+5) evren büyüse de **sabit** → görünürlük oranı doğrusal olarak düşer.

### S11 — Küçük ama yanıltıcı noktalar (DÜŞÜK)

- `daily_stats['patterns_found']` benzersiz formasyon değil, **slot-bazlı tekrar sayacı**; `/durum`'da "günlük formasyon kaydı" olarak şişik görünür (`main.py:1848`).
- `notifier.send_text()` **4096 sınırını kırpmıyor** (komut yolları `kirp()` kullanıyor). Uzun bir özet sessizce 400 alabilir; şu an taşmıyor ama koruma yok (`notifier.py:176-191`).
- Saatlik/günlük kap yalnız `send()` yolunu sayıyor; komut yanıtları, özetler, digest ve `/test` mesajı kap dışında (`notifier.py:294-301` yalnız `send()`'ten çağrılıyor) → "120 mesaj/gün" gerçek toplamı garanti etmiyor.

---

## 4. Nasıl doğruladım

| Adım | Sonuç |
|---|---|
| `pip install -r requirements.txt` (venv) + `pytest -q` | **199/199 geçti** (76 sn) |
| `bot_data/` cache ile 48 hisse × 1h/2h/4h çevrimdışı tarama | 112 slot, **21 canlı formasyon**, eşik üstü 15 |
| Gerçek fonksiyonlarla digest / günlük özet / `/panel` metni üretimi | 21 kayıttan özete **4 satır**, digest'e 11, acil 3 |
| `/panel` 192/192 dolu ve 60/96/120 hisselik evren simülasyonu | 3359 / 3825 / 3826 / 3837 karakter, kırpma sayıları yukarıda |
| Tatil & yarım gün için `is_bist_open` / `time_until_next_open` / `tarama_penceresi_acik_mi` | Tatilde ve yarım gün 13:05 sonrası **`next_open = 0`** |
| Döngü gövdesi maliyeti | 2000 yineleme 0.09 sn ≈ **21.500 satır/sn** |
| Çalışma ağacı | `git status` temiz, **hiçbir kod değişikliği yok** |

---

## 5. Öncelik sırası (öneri, uygulama yapılmadı)

1. **S1** — tatil/yarım gün sonsuz döngüsü (tek satırlık taban uyku + takvim farkındalığı; yaz sezonu dışında fark edilmez ama Render'da CPU/log maliyeti yüksek).
2. **S2** — `son_tarama_yukle()` çağrısını açılışa bağlamak (özellik yazılmış, sadece kablolanmamış).
3. **S3 / §2** — ölü kod temizliği + "kaç aday bastırıldı" sayacı; görünürlük hissini en çok bu düzeltir.
4. **S4–S7** — digest kalıcılığı, yazma batch'i, TZ sabitleme, heartbeat'e gönderim sağlığı.
5. **S8–S10** — yeni projeye taşımadan önce sabitleri config'e taşıma ve anahtar namespace'i.

---

*Bu rapor yalnızca teşhis içerir; hiçbir davranış, eşik veya formasyon mantığı değiştirilmedi.*

---

# EK — 2. tur: git hattı, "pushlanmayan" envanteri ve kalan işler

## E1. S2'yi düzelten kritik bulgu: dallar ayrışmış (YÜKSEK — merge öncesi şart)

`main` (canlıya giden kod) ile bu çalışma dalı aynı hat değil. Ölçüm:

| | `origin/main` | bu dal (`arena/01a0f318…` = `0bca8e5`) |
|---|---|---|
| `son_tarama_yukle(...)` **çağrısı** | **VAR** — `main.py:1758`, `main_loop` açılışında `supabase_store.ping()` sonrası | **YOK** (yalnız tanım `main.py:1337` + testler) |
| `LiveState.snapshot/hydrate`, atomik `.tmp`+`os.replace`, `♻️` panel notu, `test_son_tarama_kaliciligi.py` | var | var |
| `telegram_alert_flow.py` (ertelenmiş digest), panel rapor katmanı, webhook iyileştirmeleri | **yok** | var |
| `notifier.py` ölü `[:10]` | var | var |
| main'e özgü başka eksik fonksiyon | — | **yok** (fonksiyon adı diff'i boş) |

**Sonuç:** PR #9'un kodu bu dalda duruyor ama **tek satırlık aktivasyon çağrısı düşmüş**. Bu dal bugünkü hâliyle `main`'e merge edilirse **restart/uçuş sonrası `/panel`, `/canli`, 09:55 özeti yine boş gelir** — yani §S2 canlıda değil, *bu dalda* regresyon. Merge öncesi geri konmalı; yeri: `main.py:2266` (`supabase_store.ping()`) ile `main.py:2270` (`StockDequeManager(...)`) arası.

## E2. Telegram'da "hiç pushlanmayan" durumların tam listesi

| # | Durum | Kanıt |
|---|---|---|
| 1 | `ADAY_OLUSUYOR`, `GEOMETRI_ADAYI`, `FORMASYON_TANIMLANDI`, `OLGUNLASIYOR` | Ne acil state listesinde (`config.py:295-300`) ne WATCH_STATES'te (`telegram_alert_flow.py:16-22`). Ölçüm: 21 kayıttan **3'ü OLGUNLASIYOR** ve hiçbir push'a girmiyor |
| 2 | `FORMASYON_ZAYIFLADI`, `KIRILIM_TEYIT_ALAMADI`, `FORMASYON_GECERSIZ` | Aynı; yalnız `/panel` + `/formasyonlar` (`FORMASYON_GECERSIZ` metni `notifier.py:582` yazılmış ama **hiçbir akış çağırmıyor**) |
| 3 | WATCH state'leri | Acil gönderilmez; **18:45'te toplu** digest'e girer (`main.py:1886-1892`) — gün içi anlık bildirim yok |
| 4 | Digest 13. ve sonrası | `limit=12` sabit (`telegram_alert_flow.py:87`, `main.py:1937, 2397`) |
| 5 | Acil mesaja eklenen yan adaylar | `[:3]` (`main.py:1939`, `notifier.py:607`) |
| 6 | Günlük özetin 4. tamamlananı, 4. retesti, 6. sıkışanı | `tamamlanan[:3]`, `retest[:3]`, `sikisan[:5]` (`notifier.py:261/265/269`) |
| 7 | Kalite eşiği altı | `logger.debug` (`main.py:1892`) → normal seviyede **hiç log yok**, sayacı yok |
| 8 | Cooldown / saatlik-günlük kap yüzünden gönderilemeyen acil olay | `notifier.can_send` `False` → mesaj **kaybolur**, kuyruk/retry/sayaç yok (`notifier.py:370-393`) |
| 9 | Public kanal | Yalnız `FORMASYON_TAMAMLANDI`/`RETEST_BASARILI` + günlük özet; **WATCH state'leri kanala hiç gitmez** (`notifier.py:211-221`, `main.py:2434`) |
| 10 | Özet/digest anı | 09:55 ve 18:45 sabit (`config.py:190-191`); servis o an uykudaysa özet/digest **hiç gönderilmez**, telafi yok |
| 11 | Kotasız mesaj sınıfları | Komut cevapları, özetler, digest, `/test` — günlük/saatlik kap yalnız `send()` yolunu sayıyor (`notifier.py:294-301`) |
| 12 | Token yok/yanlışken | `send()` mock'ta **`True`** dönüyor (`notifier.py:639-646`) → "gitti" sayılır, `alerts_sent` artar |

## E3. Git'te pushlanmayan dosyalar (bilinçli .gitignore)

| Dosya | Kaybedilirse |
|---|---|
| `bot_data/heartbeat.json` | dış izleme göstergesi (yeniden üretilir) |
| `bot_data/telegram_kap.json`, `telegram_soguma.json` | cooldown + saatlik/günlük sayaçlar sıfırlanır → restart sonrası **spam riski** (Supabase varsa `state:telegram_*` kurtarır) |
| `bot_data/son_tarama.json` | son liste (Supabase `state:son_tarama` varsa kurtarır — **ama bkz. E1: bu dalda okuma çağrısı yok**) |
| `bot_data/*_gunluk.json` | ~500 bar × 28 hisse **1D derin veri**; Supabase yoksa/silinirse her restart 2 yıllık günlük veriyi yeniden çeker |
| `logs/`, `CANLI_FORMASYONLAR.txt` | geçmiş log ve son rapor |

Ek: `bot_data/` içinde **48 hissaden yalnız 28'inin** cache'i commitli (28 json + 28 pkl) → 20 hisse soğuk başlangıçta yeniden indirilir.

## E5. B listesinin niteliği: "yapılmamış" mı, "pushlanmamış" mı?

Üç grup var; ayırt edici ölçüt **canlıdaki `main` ile bu dalın farkı**:

**Grup 1 — Yapılmış ve bilerek böyle (tasarım; hem `main`'de hem bu dalda aynı):**
#5 günlük özetin `3+3+5` satırı (`notifier.py:261/265/269`) + ölü `[:10]` · #6 kalite eşiği altının yalnız `debug` loglanması (`main.py:1894` main / `1892` dal) · #7'nin yarısı (4 saat cooldown + 20/saat + 120/gün kapıları) · #8 kanala yalnız `FORMASYON_TAMAMLANDI`/`RETEST_BASARILI` gitmesi · #11 kap sayaçlarının yalnız `send()`'i sayması · #12 mock modda `send()`'in `True` dönmesi.

**Grup 2 — Yapılmış ama YALNIZ bu dalda; `main`'e (dolayısıyla canlıya) pushlanmamış:**
#2, #3, #4 ve #1'in bir kısmı. Kanıt:

| | `origin/main` (canlı) | bu dal |
|---|---|---|
| `telegram_alert_flow.py` / digest / `watch_context` | **yok** (`git ls-tree` boş) | var |
| Anlık gönderilen state'ler | `ALERT_STATES` = KIRILIM_ADAYI, KIRILIM_TEYITLI, RETEST_BASARILI, FORMASYON_TAMAMLANDI, SIKISMA_GUCLENIYOR **+ kod içinde KIRILIM_HAZIRLIGI** (`main.py:1496`) → **6 state anında** | yalnız 4 state anında (KIRILIM_TEYITLI, RETEST_BASARILI, FORMASYON_TAMAMLANDI, BASARISIZ_KIRILIM — `config.py:295-300`) |
| KIRILIM_ADAYI, SIKISMA_GUCLENIYOR, KIRILIM_HAZIRLIGI | anlık push (cooldown/kap ile) | 18:45 digest'e ertelenir, **limit 12** |
| BASARISIZ_KIRILIM | anlık değil | anlık |

→ Yani "18 üretiliyor, 3-5'inden bahsediliyor" hissinin kaynağı **bu dalın yeni erteleme tasarımı**; canlıdaki sürüm daha çok mesaj atıyor. Bu dal merge edilirse canlı davranış bu tabloya göre değişir (3 state anlıktan toplu mesaja düşer, `BASARISIZ_KIRILIM` anlık olur).

**Grup 3 — Hiç yazılmamış (kod yok):**
bastırılan/atlanan aday sayacı · cooldown/kap/başarısız gönderim için kuyruk + retry · `FORMASYON_GECERSIZ` mesaj şablonu (`notifier.py:582`) yazılmış ama **hiçbir akış çağırmıyor** · digest'in kalıcı olması (RAM'de, restart'ta uçuyor) · N3/N4 (URL'de sır, uçlarda rate limit).

**E1 ayrı kategoride:** `son_tarama_yukle` kod olarak **var** (hem `main`'de hem bu dalda, testleri de var); eksik olan sadece `main_loop` içindeki **çağrı satırı** — yani "yapılmamış" değil, "bu dalda bağlanmamış/düşmüş".

## E4. İlk rapordaki S1–S11'e ek yapılacaklar

| # | Madde | Öncelik |
|---|---|---|
| N1 | **E1'deki `son_tarama_yukle()` çağrısını geri koymak** (merge öncesi şart) | ★★★ |
| N2 | `bot_data/*.pkl` git'te ve `data.py:549` `pickle.load` ile okunuyor → public repo + `main`'den otomatik deploy zincirinde kod çalıştırma yüzeyi; JSON yolu zaten var (yavaş ama güvenli) | ★★ |
| N3 | `/test?k=<anahtar>` ve `/webhook/<secret>` **URL yolunda sır** taşıyor → Render access loglarına/proxy loglarına düşer; başlık doğrulaması zaten var, yol sırrı gereksiz (`health_server.py:33, 88`) | ★★ |
| N4 | Public `/health`, `/test`, `/webhook` uçlarında **rate limit yok**; `ThreadingHTTPServer` sınırsız thread → eşzamanlılık saldırısına açık (düşük riskli ama temel için önemli) | ★ |
| N5 | Doküman/şema kayması: README test sayıları (`90/90`, `6/6`) gerçekle (199) uyuşmuyor, eski dal adı yazıyor; `supabase_schema.sql` anahtar listesinde `state:son_tarama` yok | ★ |
| N6 | Test boşlukları: (a) tatilde `time_until_next_open`, (b) "açılışta `son_tarama_yukle` çağrılıyor mu" (E1'in sessiz kalma sebebi), (c) digest/özet limitlerinin uçtan uca testi | ★★ |
| N7 | Ölü kod: `fetch_with_rate_limit` + `RATE_LIMIT_MIN/MAX` (`data.py:952`, `config.py:207`), `mock_fetch_60d_1h` (yalnız `__main__`), `repo_teshis.py`, `logrotate.conf` (0 referans), `.ps1` dosyaları | ★ |
| N8 | `bot_data/` canlı sunucuda git-tracked olduğu için `git pull` veriyi ezer (bkz. `.gitignore` sonundaki uyarı) — "bu seviyede sabitleyeceğim" planında veri klasörünü repo dışına almak (sadece Supabase/disk) daha güvenli | ★★ |
