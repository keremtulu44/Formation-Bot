# Formation-Bot — Telegram Product & Live Readiness Audit

**Sonuç:** Aşama 1 ve cache tabanlı Aşama 2 tamamlandı; Aşama 3 kod/deployment incelemesi tamamlandı. **Karar: NO-GO — canlıya geçiş önerilmiyor.** Başlıca nedenler: cache 13 takvim günü eski ve evrenin 20/48 sembolü cache’te yok; gerçek provider, Supabase ve Telegram delivery doğrulanmadı; bozuk OHLCV için genel ingest bariyeri yok; takvim dışı günlerde scheduled mesaj davranışının ürün politikası karara bağlanmadı.

**Güvenlik sınırı:** Gerçek bot başlatılmadı/durdurulmadı; Telegram’a mesaj/API çağrısı yapılmadı; Yahoo/provider çağrısı yapılmadı; production credential/Supabase verisi okunmadı veya değiştirilmedi. Tam test suite geçici repo kopyasında, credential ortam değişkenleri unset edilerek çalıştırıldı. Commit/push yapılmadı; branch değiştirilmedi.

## 1. Başlangıç ve korunmuş çalışma ağacı

- Branch: `arena/956879bf-formation-bot`; HEAD: `f97c15cde20997b2f2d67e55b853a850832bfd07` (`fix: preserve order block rolling parity`). HEAD değiştirilmedi.
- Önceki audit’in başlangıç kaydı temiz olmayan çalışma ağacı olduğunu gösteriyordu. Bu turda hiçbir başlangıç değişikliği silinmedi/revert edilmedi; `TELEGRAM_SYSTEM_AUDIT.md` ve diğer mevcut debug/audit dosyaları da korunuyor.
- Bu tur sonunda da çalışma ağacı değişiklik içeriyor. Son `git status` ile güncel liste aşağıda rapor sonuna kaydedildi.
- Önceki audit raporları commit history değil, uncommitted workspace dosyalarıdır; başlangıç raporundaki sayıların tekrar üretilebilir kanıt olmadan doğru olduğu varsayılmadı.

## 2. Aşama 1 — event → delivery güvenilirliği

### Dört adayın kanıtı ve kapanış durumu

Kullanıcı dört sorunun önceden tanımlandığını belirtti, ancak bu oturuma aktarılan bağlamda sabit dört maddelik liste yok. Bu nedenle aşağıdakiler “kanıtla seçilmiş güçlü adaylar”dır; başka bir gizli liste olduğu varsayılmıyor.

| Aday | Önce / kök neden | Değişiklik ve test kanıtı | Durum / kalan risk |
|---|---|---|---|
| FVG parity test helper/API | Önce test helper’ı olmayan `_calculate_atr_series()` metodunu çağırıyordu. Bu, production FVG hesabında kanıtlanmış fark değil, test/engine API uyumsuzluğuydu. | Helper gerçek `_calculate_series()` API’siyle hizalandı; üretim FVG matematiği değiştirilmedi. `test_domain_incremental_parity.py` hedef suite’te geçti. | **Test helper hatası kapandı.** Pine/TradingView veya canlı bağımsız seriyle production parity kanıtlanmış değildir; parity farkı “ölçülmedi”, yok denmiyor. |
| Formation kararı → kalıcı enqueue aralığı | Önce sembolün domain/context işi tamamlanmadan notifier’a geçilmiyordu; aradaki crash olayın outbox’a yazılmamasına yol açabilirdi. | `main.py`, her uygun Formation olayını context işleminden önce Formation-only fallback metniyle `prepared` outbox’a yazar. Aynı taramada yalnızca güncel context eklendikten sonra etkinleşir; sembol hatasında fallback etkinleştirilir; restart’ta hazırlık kaydı fallback ile pending olur. Fake transport/store ve geçici dosya testleri var. | **Pratik crash window daraltıldı ve test edildi.** Durable enqueue’in kendisi başarısızsa kayıt garanti edilemez; scan/restart tekrarına bağımlılık kalır. Kontrollü fault injection var, gerçek process-kill/production restart yok. |
| Telegram kabulü → `sent` kalıcılığı | Dış servis kabulü ile yerel/Supabase `sent` commit’i atomik değildir. HTTP sonucu kaybolabilir veya process, kabulden sonra kapanabilir. | `sending` claim’i transport’tan önce kalıcı; cooldown/outbox recovery yolları var. Claim sonrası crash, Telegram başarı dönüşünden `sent` yazımına kadar crash ve application-ack persistence arızası fake transport/store ile test edildi. | **At-least-once/duplicate riski kalır; exactly-once iddiası yok.** Telegram tarafında idempotency garantisi kanıtlanmadı. Cooldown da yazılamazsa tekrar riski sürer; duplicate ile event loss ayrı risklerdir. |
| Watch/digest restart ve bozuk state | Önce beklenmeyen `pending`/`reported` koleksiyon tipleri restore sırasında hata çıkarabilirdi. | Restore artık liste/tuple olmayan koleksiyonları reddedip boş kabul ediyor. Fake store, replacement instance, aynı gün, gün değişimi ve malformed snapshot; digest/ack persistence senaryoları test edildi. | **Test kapsamındaki durumlar kapandı.** Remote store erişilemiyorken gerçek çoklu-process davranışı ve production snapshot tutarlılığı ölçülmedi. |

### Ek kanıtlı düzeltme: cooldown/cap kaynak ve timezone tutarlılığı

- Önce Supabase state dict’i mevcutsa yerel cooldown/kap state’i kaynak olarak okunmuyordu; eski Supabase snapshot yerel daha yeni kaydı gölgeleyebilirdi. Cap/cooldown çakışması test edilmemişti.
- Şimdi cooldown state’i local + Supabase kaynaklarından retention içindeki her key için en yeni zamanla birleştiriliyor. Aynı İstanbul günündeki cap sayacı kaynaklar arasında maksimum, saatlik timestamp’ler birleşim olarak seçiliyor; daha yeni tarih eski tarihi geçersiz kılıyor. Bu seçim fail-closed taraftadır ve biraz fazla throttling yapabilir, gözlenen gönderim izini silmez.
- Ayrıca Render/systemd tanımında `TZ` sabitlenmediği halde eski `datetime.now()` state’i host timezone’una bağlıydı. Cap reset/cooldown pencereleri artık Europe/Istanbul wall clock ile çalışıyor; yeni cooldown ve cap timestamp’leri `+03:00` offset ve cap timezone işaretiyle yazılıyor. Eski naive saatler host-local olarak çevriliyor; UTC-host gün sınırında eski cap sayacı erken sıfırlanmasın diye geçici olarak İstanbul gününe taşınabiliyor (güvenli tarafta fazla throttling riski).
- Fake local/remote çakışması, UTC→İstanbul gece yarısı, explicit-offset persistence testleri eklendi. Production Supabase state’i okunmadı; gerçek geçmiş naive kayıtların host timezone’u kesinleştirilmedi.

### Outbox / route / failure-point sonuçları

- Formation fallback metni durable `prepared` kayda domain/context hesaplarından önce yazılır; mevcut tarama sonunda DM ve uygun public channel metni ayrı job olarak etkinleşir. Formation ana olay olarak kalır; MS/Volume/FVG/OB/BOS bağımsız Telegram olayı yapılmadı.
- DM ve public-channel route kimlikleri ayrı. Özet kanalı ile DM özeti ayrı idempotency key taşır. Public policy/formatter davranışı bu audit’te değiştirilmedi.
- Transport dönüşü belirsizliği ortadan kaldırılamaz. `sending` durumundan restart recovery retry’si duplicate üretebilir; persisted cooldown ile teyit bazı belirsiz pencereleri kapatır. Her iki mekanizmanın failure’ı halinde exactly-once yoktur.
- Outbox yazım hatasında kuyruğa ekleme başarısız olarak döner; fake-store testi bunu doğrular. Retry/dead-letter davranışı unit fault-injection kapsamındadır; market replay’de transport/retry/dead-letter ölçümü yapılmadı.

### FVG parity ayrımı

1. **Helper/API uyumsuzluğu:** testte olmayan metoda çağrı; düzeltildi.
2. **Production davranışı eksik kanıt:** canlı/bağımsız TradingView referansı kullanılmadı; parity kararı verilmedi.
3. **Gerçek parity farkı:** bu aşamada ölçülmedi/kanıtlanmadı. Test helper’ın geçmesi production equality kanıtı sayılmıyor.

### Aşama 1 testleri

- Derleme: `python -m py_compile notifier.py main.py notification_outbox.py telegram_alert_flow.py test_telegram_notification_delivery.py test_supabase_integration.py` — geçti.
- Hedef regresyon paketi: `.venv/bin/pytest -q test_telegram_notification_delivery.py test_telegram_alert_flow.py test_formation_dm_context.py test_domain_incremental_parity.py test_supabase_integration.py` — **61 passed**.
- Son tam repo suite’i Aşama 3 kod değişikliklerinden sonra ayrıca çalıştırıldı; sonuç Bölüm 5’te.
- Hiçbir hedef test gerçek Telegram, gerçek Supabase veya gerçek state dosyası kullanmadı.

## 3. Aşama 2 — cache, replay ve mesaj yoğunluğu

### Dataset doğrulaması

| Özellik | Kanıtlanan değer |
|---|---|
| Kaynak | `bot_data/*.pkl` ve karşılık gelen `.json`; yalnızca mevcut cache, dış provider çağrısı yok |
| Cache sembol sayısı | 28; config’te aktif evren 48. Cache’te olmayan 20 sembol: AKSA, AKSEN, ARCLK, ASTOR, AYDEM, BRSAN, CIMSA, CWENE, DOAS, EGEEN, ENKAI, ISMEN, KONTR, ODAS, OTKAR, SKBNK, SMRTG, SNGYO, TSKB, TTRAK |
| 1H satırları | Sembol başına 360; toplam 10,080; tüm sembollerin timestamp dizisi aynı |
| Takvim | 2026-08-03 09:30:00+03:00 → 2026-09-25 17:30:00+03:00; 40 seans günü, her sembol/gün 9 bar |
| Tazelik | Audit tarihi 2026-10-08’e göre son cache bar 13 takvim günü eski. Güncel piyasa verisi değildir; ancak canlı taramayı sınırlamaz — Bölüm 5’te düzeltildi. |
| JSON/Pickle | Her alan/timestamp için karşılaştırmada 0 fark |
| OHLCV kontrolleri | Eksik/nonfinite alan 0; pozitif olmayan OHLC 0; `high<low`, high’ın open/close altında, low’ın open/close üstünde, duplicate timestamp veya sıra ihlali 0; intraday 1 saatlik gap anomalisi 0 |
| Volume | Missing 0, negatif 0; 1,094/10,080 satır explicit zero (%10.85); 1,083 zero 09:30 ilk barında, kalan 11 diğer saatlerde. Değerler değiştirilmedi. |
| Timeframe kapsamı | Kaynak cache 1H. 2H/4H ve 1D replay 1H’den resample edildi; ayrı deep-1D cache dosyası yok. Bu nedenle 1D geçmişi yalnızca yaklaşık 40 bar, production’daki ayrı günlük provider verisinin yerine geçmez. |

100 sembol değerlendirmesi kapsam dışıdır. 48 sembol için provider desteği/açılış cache durumu gerçek provider’a gitmeden doğrulanamaz. Cache eski olduğundan bu replay performansı güncel piyasa sonucu değildir.

### Tekrarlanabilir replay ve event gruplaması

- Aynı 28 sembol, aynı tarih aralığı, aynı completed-bar filtresi, aynı lifecycle policy/quality eşiği ve İstanbul scan zamanlarıyla replay edildi. Önceki 477→310 hipotezi bu kez 645 saniyelik tam history replay’de yeniden üretildi; önceki sayı körlemesine kabul edilmedi.
- Resample edilmiş tam dataset ile prefix replay’in tamamlanmış barları 1H/2H/4H/1D için örnek scan anlarında (40/100/200/359) eşleşti. Replay cache’in kendi değerlerini okudu; OHLCV değiştirilmedi.
- **5,541** aktif Formation snapshot gözlemi 15 state’e dağıldı. Bu, event/enqueue sayısı değil; aynı oluşumun çoklu taramalardaki snapshot gözlemleridir.

| State | Aktif snapshot gözlemi |
|---|---:|
| FORMASYON_TANIMLANDI | 50 |
| OLGUNLASIYOR | 397 |
| SIKISMA_GUCLENIYOR | 752 |
| KIRILIM_HAZIRLIGI | 90 |
| KIRILIM_ADAYI | 447 |
| KIRILIM_DENEMESI | 197 |
| KIRILIM_TEYITLI | 301 |
| RETEST_BEKLENIYOR | 1,019 |
| RETEST_EDILIYOR | 11 |
| RETEST_BASARILI | 251 |
| FORMASYON_TAMAMLANDI | 821 |
| BASARISIZ_KIRILIM | 581 |
| KIRILIM_TEYIT_ALAMADI | 61 |
| FORMASYON_ZAYIFLADI | 526 |
| FORMASYON_GECERSIZ | 37 |
| **Toplam** | **5,541** |

### DM/public ayrı sayımlar — teslimat iddiası değildir

| Ölçü | DM | Public channel |
|---|---:|---:|
| Eski state + 4 saat cooldown replay kabulü | 477 | 199 |
| Stable lifecycle-event identity ile tekil event adayı | 310 | 111 |
| Fark | −167 (−%35.0) | −88 (−%44.2) |
| Event adayı state kırılımı | Confirmed 120; retest 41; completed 85; failed 64 | Retest 37; completed 74 |

Bu alert state’leri current `KRITIK_STATELER` içinde olduğu için replay’de saatlik cap tarafından bloklanmadı; DM event’lerinde günlük tepe 22, yapılandırılmış günlük cap 120. Stabil event identity ile 310 DM / 111 public rakamı **policy-level unique event adayıdır**. Public sayısı yalnızca `CHANNEL_ID` bulunması senaryosunda uygun route sayımıdır.

| Ayrı aşama | Sonuç |
|---|---|
| Policy/event replay | 310 unique DM event + 111 eligible public event; 477/199 eski cooldown karşılaştırması |
| Outbox enqueue (market replay boyunca) | **Ölçülmedi.** Replay notifier/outbox’a 310/111 item yazan integration replay değildi. Unit testlerde fake/temp store ile enqueue/prepared/recovery doğrulandı. |
| Mock transport success (market replay boyunca) | **Ölçülmedi.** Replay’de transport hiç çağrılmadı. Fake transport senaryoları hedef testlerde ayrı doğrulandı; sayım replay event toplamı değildir. |
| Gerçek Telegram delivery | **Yapılmadı / ölçülmedi.** Hiçbir gerçek API çağrısı veya test mesajı yok. |
| Retry / dead-letter toplamı | Market dataset’inde **ölçülmedi**; kontrollü fake fault-injection testleri mevcut. |
| Duplicate / loss | Live duplicate/loss ölçülmedi. Eski cooldown replay’den stable identity’ye 167 DM ve 88 public tekrar adayı elendi; bu gerçek delivery metriği değildir. Exactly-once garantisi yoktur. |

### Dağılım, episode ve watch/digest

- 40 replay seans günü içinde stable immediate DM adaylarının dağılımı: ortalama **7.75/gün**, medyan **7**, p25 **3**, p75 **11**, p90 **15**, p95 **16.25**, tepe **22**, sıfır event günü **5**.
- Public immediate event adayları: ortalama **2.775/gün**, medyan **2.5**, p25 **1**, p75 **5**, p90 **6**, p95 **7**, tepe **7**, sıfır event günü **8**.
- Timeframe: 310 DM event adayı — 1H 149, 2H 100, 4H 60, 1D 1. Yön etiketi: yukarı 147, aşağı 163. Quality ham skor medyanı 84.6398; min 73.4857, max 91.3479. Bunlar finansal sonuç değil, replay state alanlarıdır.
- Episode key’i `(symbol, timeframe, pattern, start_bar)` idi: 149 episode’ta 310 tekil immediate mesaj adayı; episode başına ortalama 2.08, medyan 2, p90 3, maksimum 5. Tek adaya sahip 34 episode (%22.8), birden fazla state event adayı olan 115 episode (%77.2). Aynı episode içinde birden fazla distinct immediate state 115 kez görüldü.
- Watch buffer kapanış snapshot’ında **188** aday öğesi **32/40** seans gününde bulundu (günlük tepe 11; limit 12). Bunlar bağımsız Telegram alarmı değildir; 18:45 DM özetinin içine eklenir. Bu ölçü, 18:45 özet mesajının gerçek delivery’sini saymaz.

### Scheduled mesaj yoğunluğu — koddan türetilen ayrı üst senaryo

Ana döngü summary 09:55 ve 18:45’te; akşam bakım DM’i 18:10–19:00 penceresinde; post-close DM’i 20:00’den sonra çalıştırıyor. Bu ana döngülerde hafta sonu/resmî tatil için ortak weekday/holiday guard yok. 20:00 post-close işi ayrıca `scan_all_stocks()` ile 48 sembolün provider fetch/analiz yolunu çağırabilir; hafta sonu provider isteği davranışı ölçülmedi. Sürekli çalışan, enabled botta her takvim günü dört scheduled DM key’i; `CHANNEL_ID` varsa iki scheduled public summary key’i oluşabilir. 2026-08-03…2026-09-25 aralığı 54 takvim günü/40 hafta içi seans günü içerdiğinden bu kod varsayımı **216 scheduled DM + 108 scheduled public** (bunun 14 hafta sonu için 56 DM + 28 public) potansiyeli verir. Bu, replay’de ölçülmüş delivery değildir; event sayımlarına dahil edilmedi. Hafta sonu mesajlarının istenip istenmediği ürün politikası olarak karara bağlanmalı; bu audit public route’u değiştirmedi.

### Format örnekleri

`TELEGRAM_FORMAT_COMPARISON_EXAMPLES.md` içinde cache’ten seçilmiş 12 gerçek/replay Formation olayı için A–E beş format bulunur. A verbose `format_message`, B mevcut compact DM formatter’dır; C–E yalnızca sunum önerileridir. Tüm örneklerin ham quality/level/band/contraction/touch/age değerleri ve kaynak timestamp’i tabloda korunmuştur; format otomatik seçilmedi. MTF/domain context veya yeni OHLCV değeri üretilmedi. A–E uzunlukları yalnızca karşılaştırma ölçüsüdür.

## 4. Aşama 3 — canlıya hazırlık ve riskler

### Formation/lifecycle ve chronology

- Formation matematiği, threshold, lifecycle policy veya state transition değiştirilmedi.
- `main.py` her scan’de completed timeframe frame’ini `tam_yeniden=True` ile lifecycle manager’a veriyor; `patterns/lifecycle.py` deterministic replay yapıyor, pencere/kaynak index değişince reset ediyor. Same-timestamp cache güncellemesi `append_dataframe` içinde timestamp key’i üzerinden yeni row ile değişiyor; ardından tam replay yapılıyor.
- `tamamlanmis_mumlar()` 1H/2H/4H kapanış filtresi uygular; 1D için BIST kapanış saati 18:30 kullanılır. 2H/4H resample seans başlangıç etiketiyle hizalanır; OHLC first/max/min/last, volume sum. 1H provider `auto_adjust=False` kullanır.
- Mevcut cache chronology/regularity kontrollerinden geçti. Buna karşın `StockDequeManager.append_dataframe()` input float’larını doğrudan deque’ye alır; genel `NaN/Inf`, nonpositive/invalid OHLC geometry bariyeri yok. Split/gap/şok denetimi bazı süreklilik sorunlarını kaydeder, tüm bozuk OHLCV sınıflarını engellemez. Cache’te problem görülmedi; bozuk provider barı senaryosu canlıda doğrulanmadı. **NO-GO risklerinden biridir.**

### Domain/context bağımsızlığı ve as-of

- `formation_dm_context.py` sonucu yalnızca aynı sembol/timeframe/domain ve beklenen frame timestamp’iyle eşleştiğinde kabul ediyor; sonuç timestamp’i scan as-of sonrasına geçemiyor; hata/skipped sonuç yok sayılıyor. OB/FVG/BOS/Volume destekleyici context üretir, ayrı Telegram event policy’si değildir.
- Formation fallback’i domain/context işinden önce hazırlandığı için context hatası ana Formation olayını tamamen silmemelidir. Taze/aynı frame eşleşmesi fake testlerle doğrulandı; canlı domain providers/cache/state kullanılmadı.
- Domain cache’in as-of ve production persistence davranışı gerçek Supabase state’i olmadan ölçülemedi.

### Provider, timezone, symbol ve cache

- Provider yolu Yahoo Finance `.IS`, 1H ve 1D; transient hata için sınırlı retry ve pacing var. Gerçek sembol destekleri, rate-limit, yfinance response etiketleri veya 48/48 freshness bu audit’te dış provider’a gidilmediği için **ölçülmedi**.
- Europe/Istanbul scheduled market time ve cap/cooldown wall-clock tutarlılığı test edildi. Önceki host-local/UTC belirsizliği cap/cooldown state’inde düzeltildi; legacy timezone’u belirsiz eski state için dönüşüm varsayımı rapor Bölüm 2’dedir.
- Cache 28/48, 13 gün eski. Seans açıkken taze fetch başarısız ve veri 20 saatten eskiyse mevcut kod sembolü atlar; seans dışı cache için varsayılan 14 gün yaş sınırı bulunur ve 120 dakikayı aşan cache warning üretir. Bu koruma geçmiş cache’nin bugün için doğru olduğu anlamına gelmez. **Düzeltme:** cache eksik/eski olması tarama evrenini daraltmaz ve canlı akışı engellemez; ayrıntılı akış incelemesi Bölüm 5’te.

### Delivery, storage, operations, rollback

- Telegram’sız testte fake transport kullanıldı. Token/chat ID, channel ID, webhook/polling, Bot API response, HTTP 429 ve production routing doğrulanmadı.
- Yerel outbox atomic JSON write yapar; production store başlangıç snapshot’ı Supabase’ten gelebilir. Bu raporda gerçek Supabase’i okumadık. Tek aktif bot instance varsayımı önemlidir: process’ler arası distributed lock/at-most-one sender production ortamında doğrulanmadı; aynı JSON outbox ile birden çok replica/instance duplicate veya lost-update riski taşır.
- `prepared` yeni outbox state’idir. Eski release bu state’i tanımıyorsa rollback sırasında bekleyen prepared kayıtları yanlış ele alabilir. Rollback öncesi state snapshot alınmalı; prepared/sending/unacknowledged kayıtlar güvenli şekilde incelenip destekleyen sürümle drain/uyumluya çevrilmeden eski sürüm state üzerine yazılmamalı. Gerçek production schema migration/rollback denenmedi.
- Render blueprint’inde Python 3.12, health endpoint ve autoDeploy belirtilmiş; gerçek Render ayarları, tek instance garantisi, free-plan uyku davranışı ve production alarm/observability görünürlüğü kontrol edilmedi.

## 5. Düzeltme — Render canlı veri akışı ve yerel önbellek

Önceki rapordaki “cache eski ve 20 sembol eksik” bulgusu, canlı veri akışı kodu üzerinden yeniden değerlendirildi. Sonuç: **28 hisselik `bot_data` önbelleği tarama evrenini belirlemez; yalnızca başlangıç hızlandırma + sağlayıcı hatası yedeğidir.** Kanıt: kod okuması + izole testler; gerçek Yahoo/Render ortamında çalıştırma yapılmadı.

### Doğrulanan veri akışı (dosya : fonksiyon)

1. **Evren:** `config.py: ACTIVE_STOCKS = BIST_50` — 48 sembol. `bot_data`’daki 28 hisse (`git ls-files` ile doğrulandı; `.gitignore` notu “bilinçli olarak tutuluyor”) evreni tanımlamaz.
2. **Başlangıç:** `main.py: main_loop` → Supabase varsa `get_many(cache:1h/1d:<hisse> for ACTIVE_STOCKS)` + `StockDequeManager.hydrate_from_supabase`; yoksa `get_deque → load_from_disk` ile `bot_data/*.pkl|.json` lazy fallback. Ardından `cache_eksik_hisseler` (koşul: `to_dataframe` None veya <50 bar) için `fetch_1h_stocks_paced(..., periods=None)` → **tam 60d pencereyle Yahoo isteği** → `append_dataframe + save_to_disk`; eksik 1D derin veri de çekilir. İzole test: 28 cache’li kopyada seçim tam olarak 20 eksik sembolü verir; İLK YÜKLEME 20 istek, 0 hata, diskte 48 hisse.
3. **Normal tarama:** `main.py: scan_all_stocks` → `scan_stocks = stocks or ACTIVE_STOCKS` (48). Her sembol için `select_yfinance_1h_period(cached)` (boş/<50 → 60d; >5 gün eski → 60d; taze → 5d) ve **her taramada sağlayıcıya yeni istek** (`fetch_1h_stocks_paced`, pacing + tek retry). Test: temiz başlangıçta 48/48 fetch ve 48/48 analiz; 28 taze + 20 boş kopyada 28×5d + 20×60d istek; tarama sonunda cache’siz 20 hisse canlı veriden yüklü.
4. **Fetch başarısızsa:** seans açık + son mum >120 dk → hisse analiz dışı (`_cache_verisi_kullanilabilir`); seans açık + yaş >20 saat → “veri yok modu”; seans dışı → son mum 14 güne kadar “eski cache” uyarısıyla kullanılır; >14 gün → atlanır; fetch yok + cache boş → atlanır. Test: 28 cache’li seans dışı cache ile analiz edilir, 20 cache’siz atlanır, sonuç “Eksik tarama: 28/48” ile **başarılı sayılmaz**; 180 dk eski cache seans içinde sinyal üretmez; 20 günlük cache seans dışında bile kullanılmaz.
5. **Fetch “başarılı” ama barlar eski (sağlayıcı gecikmesi):** analiz yine de yapılır; ancak VERİ ESKİ uyarısı + `stale_stocks`/`data_stale` sayacı + eski `data_asof` ile işaretlenir (test: 8 saatlik bar, seans içi → işaretli devam). “Eski veri güncelmiş gibi” davranışına en yakın senaryo budur; sessiz değildir ama engellenmez — **operasyonel risk**.
6. **Eski cache ↔ taze canlı seçim:** `append_dataframe` timestamp bazlı birleştirir; test: 20 günlük cache + taze fetch → 55+60 bar kayıpsız birleşir, en yeni mumlar canlıdan, pencere seçimi 60d.
7. **Kapsam raporlama (sessiz eksik evren yok):** `last_run_stats` (requested/processed/failed/fresh_fetch/fetch_failures); başarısız turda `LiveState.fail_scan(“Eksik tarama: X/Y …”)` ve sonuç yayınlanmaz; `write_heartbeat` → `bot_data/heartbeat.json` + Supabase `state:heartbeat` (fetch_ok/fetch_failures/stale_stocks/data_stale/active_stocks=48); Telegram çıktısında `_veri_durumu_satiri` (“başarılı fetch 26/48 · fetch hatası 22”) ve hisse-özel taramada `_kismi_kapsam_notu`. Test: 22 hatalı senaryoda işlenen 26; heartbeat payload’ı ve komut metni eksik kapsamı dışa açık verir.

### Sınıflandırma

**Canlı akış için engel değil:** önbellek hızlandırma/yedeğidir; canlı akış 48 sembolü her taramada sağlayıcıdan tazeler; eksik semboller canlı veriden yüklenir; güvenlik sınırları ve kapsam raporlama izole testlerle doğrulandı. Kalan **operasyonel riskler:** (a) “fetch başarılı ama eski bar” durumunda analiz uyarıyla da olsa devam eder; (b) sağlayıcı tamamen çökerse cache’siz semboller atlanır — kapsam raporlanır ama o sembollerde analiz olmaz; (c) bu davranışlar gerçek Yahoo/Render ortamında değil izole testte kanıtlandı.

### Yeni test kanıtı

`test_live_data_flow.py` — 12 test; sahte `fetch_yfinance_1h/1d`, tmp disk, gerçek `StockDequeManager` + `scan_all_stocks`; **12 passed (~4.5s)**. İlgili grup (yeni dosya + 6 mevcut) **84 passed (18.00s)**; tam suite **281 passed (116.50s)**. Gerçek provider/Telegram/Supabase çağrısı yok; repo `bot_data` değişmedi (56 dosya, git durumu aynı).

### Canlıda henüz doğrulanmamış noktalar (ayrı liste)

1. Gerçek Yahoo `.IS` yanıtları: 48/48 sembol desteği, rate-limit, gerçek bar etiket/tazelik.
2. Render gerçek restart’ı: `bot_data` sıfırlanması, ilk yükleme süresi, Supabase hydrate.
3. Gerçek Supabase: uzak cache/state kalıcılığı, çoklu-instance çakışması.
4. Gerçek Telegram: teslimat, 429, webhook/polling, duplicate/loss.
5. “Fetch başarılı ama eski bar” üretim sıklığı; 120 dk eşiğinin gerçek veriyle yeterliliği.
6. Render Free tek-instance ve uyku davranışının zamanlamaya etkisi.

## 6. Test/kanıt özeti ve durum etiketleri

| Kanıt türü | Sonuç |
|---|---|
| Testle doğrulandı — canlı veri akışı (Bölüm 5) | `test_live_data_flow.py` **12 passed (~4.5s)**; sahte fetch + tmp disk |
| Testle doğrulandı — hedef regression set | **84 passed (18.00s)** (yeni akış dosyası + 6 ilgili dosya) |
| Testle doğrulandı — tam test suite | **281 passed in 116.50s** (önceki tur 269 + 12 yeni akış testi); Telegram/Supabase env key’leri unset. Bu tur suite workspace’te koştu; testlerin yazdığı 2 geçici state dosyası (`bot_data/telegram_delivery.json`, `bot_data/telegram_soguma.json`) sonradan silindi, 56 commitli cache dosyası değişmedi. |
| Replay ile ölçüldü | 28-symbol cache; 477→310 DM / 199→111 public policy-event sayımı; state/day/episode/watch dağılımları Bölüm 3’te. Güncel piyasa sonucu değildir. |
| Kod incelemesiyle doğrulandı | completed bar, resampling, as-of guards, schedule gating eksikliği, cache file kapsamı, outbox state flow; canlı veri akışı zinciri (Bölüm 5) |
| Ölçülmedi (akış) | gerçek Yahoo/Render restart davranışı; Bölüm 5’teki ayrı liste |
| Ölçülmedi | gerçek provider freshness/symbol support, live Telegram delivery, production Supabase state/race/rollback, gerçek duplicate/loss, production FVG→Pine parity, bad-OHLC provider fault |
| Tahmin/koddan türetilen senaryo | 54 takvim gününde scheduled DM/public key üst senaryosu; delivered message count değildir. |

## 7. GO kararı ve 24 saatlik gözlem/stop/rollback planı

**Karar: NO-GO.** Yerel önbellek bulgusu Bölüm 5’te “engel değil” olarak düzeltildi; ancak diğer gerekçeler bu düzeltmeyle kalkmaz: gerçek provider, Supabase ve Telegram delivery doğrulanmadı (tamamı kod/izole-test düzeyinde); bozuk OHLCV için genel ingest bariyeri yok; hafta sonu/resmî tatil scheduled mesaj politikası karara bağlanmadı; tek-instance garantisi production’da kanıtsız. Başlamak için gereken koşullar: gerçek provider ile 48/48 sembol çekim sağlık kanıtı (yerel cache tazeliği değil); bozuk OHLCV input guard veya açık kabul kriteri; hafta sonu/holiday scheduled policy kararı; production’da tek instance; fake/staging dışında gerçek Telegram’a mesaj atma onayı ve credential/Supabase bağlantısının kullanıcı kontrollü kurulumu. Bu rapor canlıya deploy etmez.

Kullanıcı ileride deploy’a izin verirse 24 saatlik gözlem planı (bu oturumda uygulanmadı):

1. **Başlangıç / preflight:** mevcut state/outbox/cooldown/cap/watch snapshot’larının yedek kopyası; bir replica; deploy’dan önce 48/48 sembol freshness/check sonucu; market zamanı ve summary takvimi; no synthetic Telegram message. AutoDeploy/ikinci instance kapalı olduğunun teyidi.
2. **İlk piyasa saatleri:** her 1H kapanışı için fetched/failed/stale symbol count, completed-bar zamanı, malformed OHLCV, split/gap uyarıları ve tarama süresi kaydı. Piyasa açıkken 120 dk’dan eski veriyle event üretilmesini stop koşulu yap; stale symbol skip edildiğini ayrıca raporla.
3. **Delivery ayrı izleme:** `prepared → pending → sending → sent → acknowledged` sayıları DM ve channel bazında; retry, dead-letter, outbox yaşı, cap/cooldown ve aynı event ID’nin tekrar attempt/delivery göstergeleri. Dış servisin kabulü ile ack farkını duplicate riski olarak açık tut; exactly-once hedefi koyma.
4. **Akşam ve gün değişimi:** 18:45 digest’in tek scheduled DM key’iyle geldiği, watch kayıtlarının ack sonrası restore edildiği, channel summary’nin DM’den bağımsız kaldığı ve weekend/holiday policy’nin uygulandığı doğrulanır. 20:00 post-close task sonucu ayrı kaydedilir.
5. **STOP:** herhangi bir bozuk/nonfinite/impossible OHLCV ile Formation event’i; piyasa açıkken >120 dk stale bar ile event; aynı event ID’nin iki kez Telegram tarafından kabul edildiğine dair kanıt; prepared/pending/sending kayıtlarının 10 dakikadan uzun sahipsiz kalması; açıklanamayan dead-letter/event-loss; iki sender instance; tekrarlayan 429/5xx veya watch/cap state yazım arızası. Önce yeni scan/send’i durdur, state snapshot al; dosyaları silme.
6. **Rollback:** önce enqueue/scheduler’ı güvenli biçimde durdur; local ve Supabase state’ini yalnızca yetkili operatör yedekler; prepared/sending/unacknowledged kayıtları destekleyen sürümde drain/incele; uyumlu eski app sürümüne dön, state/outbox’ı restore etmeden üstüne yazma. Duplicate şüphesinde yeniden gönderme yerine event ID, Telegram kabul izi ve outbox kaydını karşılaştır. Bot restart/deploy işlemi kullanıcı onayı olmadan bu audit’te yapılmaz.

## 8. Bu raporda dokunulan dosyalar / çalışma ağacı

Bu turdaki uygulama/test ekleri: `notifier.py` (cooldown/cap merge ve Istanbul time state), `test_telegram_notification_delivery.py`, `test_supabase_integration.py`; denetim düzeltmesi turunda `test_live_data_flow.py` (yalnız test, üretim kodu değişmedi); ayrı karşılaştırma eki `TELEGRAM_FORMAT_COMPARISON_EXAMPLES.md`; bu rapor. Önceden bu audit kapsamında bulunan Formation/outbox/watch/parity değişiklikleri korunmuştur.

Son durum (commit edilmedi):

- Modified: `main.py`, `notifier.py`, `telegram_alert_flow.py`, `test_domain_incremental_parity.py`, `test_domain_integration_regressions.py`, `test_telegram_alert_flow.py`, `test_supabase_integration.py`.
- Untracked: `TELEGRAM_FORMAT_COMPARISON_EXAMPLES.md`, `TELEGRAM_PRODUCT_AND_LIVE_READINESS_AUDIT.md`, `TELEGRAM_SYSTEM_AUDIT.md`, `formation_dm_context.py`, `notification_outbox.py`, `test_formation_dm_context.py`, `test_live_data_flow.py`, `test_telegram_notification_delivery.py`.
- `bot_data` içinde test state’i oluşturulmadı/silinmedi; akış testleri tmp disk kullandı. Repodaki mevcut log/debug dosyaları temizlenmedi.
- Commit/push yapılmadı; branch `arena/956879bf-formation-bot` olarak kaldı.

---

# AŞAMA 4 — Veri Güvenliği, Takvim Politikası ve Kontrollü Doğrulama

Tarih: 2026-10-09. Plan: `ASAMA4_CANLIYA_HAZIRLIK_PLANI.md` (kullanıcı onaylı, tam uygulama; hafta sonu politikası kararı sonraya bırakıldı). Runbook: `CANLI_DOGRLAMA_PLANI_VE_RUNBOOK.md`.

## 1. Başlangıç durumu

- Branch `arena/956879bf-formation-bot`, HEAD `f97c15c` (değişmedi). Çalışma ağacı: 7 modified + 8 untracked (P0 kaydı). Önceki tam suite: **281 passed (116.50s)**.
- Bu tur başında izole kopyada tekrar ölçüldü: **281 passed (120.40s)** — başlangıç başarısızlığı yok.
- P0 kod doğrulaması: `bar_kapandi_mi()` repo'da YOK; fiili sözleşme `data.py: tamamlanmis_mumlar()` (analiz katmanında yarım mum elemesi). Notifier zinciri: `prepare_formation` (notifier.py:1159) → `send` (:1226) → outbox `claim` (notification_outbox.py, atomik RLock) → transport → `mark_sent` → `acknowledge_delivery`. Watch buffer'da ayrı TTL yok: İstanbul gün değişimi doğal TTL (`_ensure_day`), stale-day restore reddi mevcut testli.

## 2. İncelenen gerçek kod akışı

`fetch_yfinance_1h/1d` (data.py) → `StockDequeManager.append_dataframe/append_gunluk_dataframe` → `tamamlanmis_mumlar` → `resample_all_timeframes` → `scan_all_stocks` (main.py:1795) → lifecycle `scan(tam_yeniden=True)` + domain runner → `prepare_formation` → `send` → outbox → transport → `sent`/`ack`. Zamanlayıcı: `main_loop` (tarama kapısı `tarama_penceresi_acik_mi`), özetler 09:55/18:45, bakım 18:10, post-close 20:00 (inline koşullar, hafta sonu guard'ı yalnız tarama penceresinde).

## 3. OHLCV güvenliği (tek doğrulama sınırı)

**Uygulanan:** `data.py: ohlcv_girdi_sorunlari()` — tek sınır `append_dataframe`/`append_gunluk_dataframe` kapısı. Geçersiz frame deque'ye HİÇ yazılmaz; `scan_all_stocks` bunu fetch-başarısız yolu gibi işler (taze=None → mevcut tazelik politikası; seans içi >120 dk eski cache → analiz dışı). Formation ve domain motorları deque'den beslendiği için ayrı katmanda çoğaltma yapılmadı. Supabase hydrate satır döngülerine (1H/1D) aynı geometri kontrolü eklendi (bozuk satır atlanır). `morning_preload`, İLK YÜKLEME ve post-close çağrıları dönüş değeri kontrolüne bağlandı (geçersizse diske yazılmaz).

**Kural sözleşmesi:** Red = boş frame, eksik sütun, NaN/Inf herhangi bir alan, `high<low`, `high<max(open,close)`, `low>min(open,close)`, ≤0 fiyat, negatif hacim, sayısal olmayan değer. Kabul = sıfır hacim (BIST ilk bar sözleşmesi; cache'te 1.083 satır ölçümlü), duplicate/sırasız timestamp (mevcut idempotent birleştirme), tamlık filtresi `tamamlanmis_mumlar`'da kalır (çift kapı yok).

**Test kanıtı:** `test_ohlcv_guvenligi.py` **17 passed (0.45s)** — spec'in 20 senaryosu karşılandı (13'ü doğrudan validator/entegrasyon, 14-16 mevcut politika sınır testleriyle eşlendi: `_cache_verisi_kullanilabilir` matrisi + `test_live_data_flow::test_saglayici_eski_bar_donerse...`). Geçersiz yeni veri eski cache'i bozmuyor (frame eşitliği + diskten geri okuma), karışık sembolde hatalı sembol diğerini durdurmuyor (GOOD işlenir, BAD 'Eksik tarama' sayılır), cache'siz sembolde lifecycle/domain motorları hiç çağrılmıyor.

**Geriye dönük uyumluluk:** `append_dataframe` artık bool döndürür (eski None dönen çağrılar etkilenmez). Sıfır hacim kabulü, duplicate/sırasız birleştirme ve `tamamlanmis_mumlar` davranışı korunur. Formasyon matematiği, kalite, bildirim politikası ve Telegram formatı değişmedi (diff: yalnız kapı + dönüş değeri kullanan 5 çağrı noktası).

## 4. Hafta sonu/tatil politikası (KOD + TEST; ürün kararı açık)

| Akış | Mevcut davranış | Kanıt |
|---|---|---|
| Otomatik tarama | Hafta sonu/tatil YOK (pencere kapalı → fetch de yok) | `data.py:88/116/263`; TEST `test_cumartesi_pazar_tarama_ve_veri_yok_modu_kapali` |
| Resmî tatil / yarım gün | Tatil taraması yok; yarım gün penceresi 13:00 kapanışına uyarlanır | TEST `test_resmi_tatil_ve_yarim_gun_penceresi` (28 Ekim arefe + 29 Ekim tatil) |
| Scheduled özetler 09:55/18:45 + bakım 18:10 | **Hafta sonu guard'ı YOK** → her takvim günü çalışır; cumadaki `_live_state` kayıtları veri yaşı sorgulanmadan özetlenir | KOD main_loop inline koşullar; TEST `test_cuma_formasyonu_hafta_sonu_ozetinde_guncel_gibi_gorunur` (risk kanıtı) |
| Post-close 20:00 | **Guard yok** → cumartesi 20:05'te de 48 sembole provider isteği gider | KOD + TEST `test_post_close_zamanlayici_guardi_yok_kod_duzeysinde` (48 istek kanıtlandı) |
| Watch/digest bekleyenleri | Gün değişimi doğal TTL; cumartesi observe → pazartesi liste boş; eski gün snapshot restore reddedilir | TEST `test_pazar_gecisi_watch_bufferi_temizlenir` + mevcut `test_same_day_watch_snapshot...` |
| Aynı mesaj restart sonrası | Digest/outbox idempotency key ile tekrar etmez | mevcut TEST `test_scheduled_digest_idempotency_key...`, `test_old_scheduled_digest_expires...` |
| Cooldown/cap | İstanbul yerel günü; hafta sonu da işler (pazar olayı olmadığından etkisiz) | mevcut TEST `test_daily_caps_use_istanbul_calendar...` |
| DST | Europe/Istanbul sabit +03 (2016'dan beri DST yok) | TEST `test_istanbul_tz_dst_kullanmaz_sabit_utc3` |

**Kullanıcı kararı bekleyen:** (1) hafta sonu/tatilde scheduled özet+bakım+post-close: üretilmesin mi, mevcut kalsın mı; (2) README "hafta sonu tarama yapmadan bekler" ifadesiyle post-close fetch davranışı çelişiyor; (3) A–E format seçimi. Bu görevde KOD DEĞİŞİKLİĞİ YAPILMADI.

## 5. Bildirim güvenilirliği

Mevcut hata pencereleri zaten testliydi: claim transport'tan önce kalıcı (`test_send_claim_is_durable...`), gönderim öncesi crash (`test_crash_after_claim...`), Telegram hata + retry (`test_failed_dm_is_durable...`, `test_telegram_429...`), **kabul sonrası sent-yazılamama/crash** (`test_transport_success_then_sent_persistence_crash...`, `test_crash_after_remote_acceptance_is_ambiguous_and_at_least_once`), restore tekrarı (`test_scheduled_digest_idempotency...`), ack hatası (`test_failed_application_ack...`), dead-letter sınırı. **Yeni:** iki taramanın aynı event'i eşzamanlı üretmesi — `test_two_scans_producing_same_event_concurrently_send_once`: outbox `claim` atomik (RLock + yalnız `pending`→`sending`), her hedefe tam bir transport; ikinci thread de True dönebilir (dönüş = "durably sent"). **Garanti tablosu:** süreç içi yarış tek transport; ancak Telegram kabulü → `sent` kalıcı yazımı arası pencerede restart olursa TEK TEKRAR mümkündür — **at-least-once sözleşmesi; exactly-once iddia EDİLMEZ** (Telegram tarafında idempotency kanıtı yok).

## 6. Test sonuçları

| Grup | Sonuç |
|---|---|
| Başlangıç baseline (izole kopya) | 281 passed (120.40s) |
| `test_ohlcv_guvenligi.py` (yeni) | 17 passed (0.45s) |
| `test_takvim_politikasi.py` (yeni) | 7 passed (0.30s) |
| Eşzamanlılık testi (yeni, delivery dosyasında) | 1 passed |
| P2 regresyon grubu (10 dosya) | 124 passed (17.62s) |
| **Tam suite (izole kopya, güncel ağaç)** | **306 passed (119.91s)** |

Tüm testler ağ çağrısız; Telegram/Supabase env unset. Not: ilk izole suite denemesi INTERNALERROR verdi — nedeni script-style `test_tarama_zamani.py`'ın import sırasında çalışıp başarısız kontrolde `sys.exit(1)` atması (brittle yapı); test-hijyen yamaları sonrası aynı suite 306 passed. Başarısızlık gizlenmedi, kök neden düzeltildi.

## 7. Yan etki kontrolü

- `bot_data` 56 commitli dosya checksum karşılaştırması: **bayt-bayt değişiklik yok**.
- Test artıkları: `telegram_delivery.json` + `telegram_soguma.json` bu turda testler tarafından oluştu → kök neden giderildi (`test_notifier_mesajlari.py` ve `test_tarama_zamani.py` gerçek `DATA_DIR` yerine tmp kullanır), dosyalar silindi, tekrar oluşmadığı doğrulandı.
- Yeni değişen dosyalar: `data.py`, `main.py` (yalnız kapı + 5 çağrı noktası), `test_ohlcv_guvenligi.py`, `test_takvim_politikasi.py`, `test_telegram_notification_delivery.py` (+1 test), `test_notifier_mesajlari.py`, `test_tarama_zamani.py` (hijyen). Untracked önceki dosyalar korundu. Commit/push/deploy/gerçek Telegram yok.

## 8. Canlı doğrulama planı

`CANLI_DOGRLAMA_PLANI_VE_RUNBOOK.md` — Yahoo (48/48 eşleme, tazelik, rate-limit, fallback), Render (restart/disk/tek-instance), Supabase (bağlantı, bozuk snapshot, okuma-yazma ayrımı), Telegram (getMe, test hedefi, kabul→sent, 429, restart-tekrar). Üretim adımları `[ONAY GEREKLİ]`; STOP/rollback/tekrar-mesaj playbooks dahil. **Hiçbiri çalıştırılmadı.**

## 9. Kalan riskler (gerçek servis doğrulaması yok)

1. Yahoo `.IS` 48/48 gerçek destek/tazelik/rate-limit (STAGING/ÜRETİM yapilmadı).
2. Telegram kabul→`sent` penceresinde at-least-once tekrarı (Tasarımsal; yalnız test simülasyonu).
3. Hafta sonu scheduled özet/post-close ürün kararı açık (bu tur kodlanmadı).
4. Render gerçek restart/disk/tek-instance davranışı; Supabase gerçek çakışma davranışı.
5. Eski bar "başarılı fetch" üretim sıklığı (izole testte uyarı+kıpıt kanıtlı, üretim sıklığı bilinmiyor).
6. Script-style `test_tarama_zamani.py` yapısı hâlâ kırılgan (import'ta çalışır) — yalnız izole edildi, yeniden yazılmadı.

## 10. Karar

**NO-GO (korunuyor).** Aşama 4, veri güvenliği bariyerini kapattı ve takvim/güvenilirlik davranışını testle sabitledi; ancak GO için gerekli ÜRETİM doğrulamaları (Yahoo 48/48, Render restart, Supabase, Telegram uçtan uca) bu görevin kapsamında yasak ve yapılmadı. Koşullu yol: kullanıcı hafta sonu politikasını kararlaştırır + runbook'taki [ONAY GEREKLİ] adımlar sırayla onaylanır ve STAGING/ÜRETİM kanıtı toplanırsa CONDITIONAL GO değerlendirilir.
