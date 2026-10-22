# FVG / OB puanlama prototipi ve ilk aşama denetimi

**Durum:** 1d FVG için 40 bar warm-up değişikliği ve yerel sınır doğrulaması tamamlandı. Puanlama prototipi üretim tarama/bildirim veya Supabase akışına bağlanmadı; canlıya alma yapılmadı. `reports/` altındaki 15 CSV/Markdown çıktı yerel üretim artefaktıdır ve stale cache içerdiğinden bilerek commit dışı bırakılmıştır.

> **Rapor/denetim tarihi: 11 Ekim 2026. Veri tarihi uyarısı:** Yalnızca yerel `bot_data/` JSON cache'i kullanıldı; son tamamlanmış 1h bar **25 Eylül 2026 17:30 +03:00**. Aşağıdaki fiyatlar ve bölgeler `as_of=25 Eylül 2026 18:35 +03:00` snapshot'ıdır; denetim tarihinde yaklaşık **16 takvim günü** geridedir ve güncel piyasa fiyatı olarak kullanılamaz.

## Kısa sonuç

- Kapsam, cache JSON'larında bulunan 28 sembolle sınırlandı. Her sembolde 360/360 OHLCV satırı geçti; toplam **10.080 geçerli 1h bar** var. Pickle cache'leri açılmadı/deserialize edilmedi.
- FVG motorunda warm-up eşiği 2h/4h için 100 bar olarak korundu; 1d için 40'a indirildi. Cache'teki 28 sembolün tamamında 40 tamamlanmış 1d bar ile kalite `OK` oldu. FVG 1h desteklenmiyor.
- İzole prototip, her temas için en fazla 10 tamamlanmış barı kullanıyor; fiyat yakınlığı, reaksiyon, timeframe örneklemi ve MTF örtüşmesini ayrı bileşenler olarak sunuyor. **Bileşik skor ve olasılık üretilmiyor.**
- Güncellenmiş yerel replay CSV'sinde **2.862** native-lifecycle bölgesi var; snapshot sonunda 576'sı aktifti (41 FVG, 535 OB). 1d'de 10 FVG formation'ı 10 aktif bölgeye dönüştü, ancak 40 barlık pencerede bunların temas/reaksiyon örneği yok. Ölçülen değerler betimseldir, başarı olasılığı değildir.
- Supabase denetimi yalnızca repo SQL/Python kodundan yapıldı. Gerçek Supabase/Yahoo/Telegram uçlarına gidilmedi ve hiçbir kayda yazılmadı.

## Kapsam ve değişiklik sınırı

Kullanılan sembol listesi cache dosyalarından geldi: `AKBNK, ALARK, ASELS, BIMAS, DOHOL, EKGYO, EREGL, FROTO, GARAN, GUBRF, HALKB, HEKTS, ISCTR, KCHOL, KRDMD, PETKM, PGSUS, SAHOL, SASA, SISE, TAVHL, TCELL, THYAO, TOASO, TTKOM, TUPRS, VAKBN, YKBNK`.

`config.py` AST üzerinden kontrol edildi: `BIST_50` 48 sembol ve `ACTIVE_STOCKS = BIST_50` olarak kalıyor. 28 cache sembolü uygulamanın tarama evreni olarak kullanılmadı veya `ACTIVE_STOCKS`'e yazılmadı. Tek izinli runtime değişikliği 1d FVG warm-up geçmişini 100'den 40 bara indirmektir; 2h/4h geçmiş eşiği 100, diğer timeframe/OB eşikleri, formasyon matematiği ve bildirim davranışı değişmedi.

Önceki izole prototipe ek olarak bu turda değişen/yenilenenler:

- `domain_engines/fvg/fvg_engulfing_models.py` — 1d için 40 barlık warm-up helper'ı; global/varsayılan 100 sabiti korunur.
- `domain_engines/fvg/fvg_engulfing_engine.py` ve `domain_engines/fvg/fvg_engulfing.py` — base detector ve public facade aynı timeframe'e bağlı eşiği kullanır.
- `domain_engines/fvg/__init__.py` ve `domain_engines/runner.py` — helper export edilir; warm-up log'u timeframe'e göre gerçek eşiği yazar.
- `test_domain_engines.py` — 39/40 günlük ve 99/100 2h/4h sınır testleri, public engine ve detector için.
- `ZONE_SCORING_AUDIT.md` ile `reports/zone_scoring_*asof_2026-09-25.csv` — günlük FVG eşiği sonrası yerel snapshot sonuçlarıyla güncellendi.
- Önceki turda eklenen `zone_scoring.py` ve sentetik prototip testleri bu değişiklikte üretim akışına bağlanmadı.

Prototip, `data.py`'deki `tamamlanmis_mumlar` filtresinden geçirilmiş frame'leri bekler. Verilen `as_of` sonrasındaki timestamp'ler replay'den önce atılır; varsa `is_closed=False` veya `is_complete=False` satırları reddedilir. OHLCV tek başına günlük mumun tamamlanıp tamamlanmadığını kanıtlayamayacağı için tamamlanmış-mum ön filtresi API sözleşmesidir. Universe analizinde tüm semboller için ortak `as_of` zorunludur.

## Ayrı ölçüm bileşenleri

| Bileşen | Prototipteki tanım |
|---|---|
| Fiyat bölgesi | Aktif kayıtta motorun kalan/etkin aralığı; tamamlanmış kayıtta özgün aralık. CSV'de ikisi de `lower/upper` ve `original_lower/original_upper` alanlarında bulunur. |
| Oluşum ve kullanılabilirlik zamanı | `formation_time` oluşum timestamp'idir. `available_at`, bölgenin motor tarafından ilk kez kullanılabilir olduğu tamamlanmış bardır; özellikle OB'de eski kaynak mumuyla sonradan doğrulama mumunu ayırır. |
| Mevcut fiyata uzaklık | Her sembol için `as_of` anına kadarki son tamamlanmış 1h kapanışı ortak referans alınır. `distance_atr = bölge dışındaki fiyat boşluğu / ilgili timeframe ATR(14)`. Fiyat bölgenin içindeyse uzaklık 0'dır. Sabit yakınlık çarpanı yoktur. |
| Yakınlık sıralaması | Aktif bölgeler, aynı `zone_type + timeframe + direction` grubunda normalize uzaklıklarına göre ampirik sıra yüzdeliği alır. `proximity_rank_n` grup büyüklüğüdür. Bu bir olasılık değildir; n=1 ise sıra yüzdeliği verilmez. |
| Temas | `available_at` sonrasındaki tamamlanmış barın OHLC aralığı bölgeyle kesişirse temas sayılır. Bitişik temas barları tek temas epizodu sayılır; oluşum barının kendi iç hareketi reaksiyona katılmaz. |
| ATR-normalize reaksiyon | Temas epizodu bittikten sonraki bardan başlar; en çok 10 kendi-timeframe tamamlanmış barı izler. Yeni temas veya native lifecycle terminali pencereyi erken bitirebilir. Olumlu/adverse hareket, bölgenin karşı kenarının ötesindeki yüksek/düşük fiyat mesafesinin temas sonundaki ATR(14)'e oranıdır. CSV'de medyanlar, maksimum olumlu hareket, örnek adedi ve sansürlü temas adedi ayrıdır. |
| Geçersizleşme/terminal | FVG için motorun `invalid` bayrağı, terminal state'i ve native nedeni korunur; `FULL_FILL` terminal durumu `invalid` bayrağıyla karıştırılmaz. OB için native motor kaydının kaldırılması ve gözlenen `gap_through` / `fill_cancel_threshold` nedeni raporlanır. |
| Timeframe ölçümü | Her zone type/timeframe için temas ve örnek sayısı ile olumlu/adverse ATR hareketlerinin ampirik medyanı ayrı sunulur. Timeframe'e katsayı veya önceden belirlenmiş güç çarpanı uygulanmaz. |
| MTF ilişki | Yalnızca aynı sembolde, farklı timeframe'lerdeki mevcut aktif bölgeler ikili karşılaştırılır. Aralık örtüşmesi `intersection / union (IoU)`; aralık boşluğu ve merkez farkı `sqrt(ATR_a × ATR_b)` ile normalize edilir. Yön uyumu ayrıca tutulur. Mesafe eşiği veya örtüşme ağırlığı yoktur. |
| Skor / olasılık / veri yeterliliği | Yakınlık sıra bileşeni dışında bileşik skor yoktur. `probability` daima boş, `probability_status=NOT_CALIBRATED` kalır. Örnek adedi, sıfır örnek ve sansürlü temaslar ayrı gösterilir; örnek yeterliliği adına keyfî bir minimum n seçilmedi. |

Tepki penceresi tamamlanmış olsa bile aynı bölge/sembol/timeframe içindeki gözlemler bağımsız değildir; aynı bar birden fazla bölgeye temas edebilir. Bu nedenle toplam temas sayısı istatistiksel olarak bağımsız örnek sayısı gibi yorumlanmamalıdır.

## Yerel veri kapsamı ve replay sonucu

Bütün cache satırları 1h JSON'lardan mevcut temizleme/resample/tamamlanmış-mum fonksiyonlarıyla üretildi. Her 1h cache'in tarih aralığı **3 Ağustos 2026 09:30–25 Eylül 2026 17:30 +03:00**; her sembolde 360 bar ve 0 atlanan OHLCV satırı.

| Timeframe | Tamamlanmış bar / sembol | FVG durumu | Not |
|---|---:|---|---|
| 1h | 360 | Desteklenmiyor | FVG motoru 1h kabul etmiyor; OB replay'i çalışır. |
| 2h | 199 | 28/28 `OK` | FVG'nin 100 bar geçmiş şartını karşılıyor. |
| 4h | 119 | 28/28 `OK` | FVG'nin 100 bar geçmiş şartını karşılıyor. |
| 1d | 40 | 28/28 `OK` | Yeni 1d eşiği 40 bar. Ayrı günlük JSON cache yok; 1d bu denetimde 1h'den resample edildi. |

FVG motorunun ham formation sayıları 2h/4h/1d için sırasıyla 425/87/10 oldu. Lifecycle tablosu yalnızca native lifecycle'a kabul edilen kayıtları içerir: 2h'de 319 tamamlanmış + 16 aktif = 335; 4h'de 53 tamamlanmış + 15 aktif = 68; 1d'de 0 tamamlanmış + 10 aktif = 10. Ham formation adedi ile lifecycle bölge adedinin paydaları aynı değildir.

Aşağıdaki “bölge” sayısı, tüm verilen geçmiş replay'inde en az bir kez native aktif hale gelen ve prototipin ölçtüğü kayıttır; yalnızca replay sonundaki `engine.records` uzunluğu değildir.

| Tür | TF | Lifecycle bölgesi | Son durumda aktif | Temas | Tamamlanmış reaksiyon penceresi | Sansürlü temas | Bölge başına tamamlanmış örnek: 0 / 1 / 2+ | Medyan olumlu / adverse ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FVG | 2h | 335 | 16 | 255 | 238 | 17 | 102 / 228 / 5 | 1.5394 / 0.3796 |
| FVG | 4h | 68 | 15 | 49 | 22 | 27 | 46 / 22 / 0 | 0.9083 / 0.0000 |
| FVG | 1d | 10 | 10 | 0 | 0 | 0 | 10 / 0 / 0 | — / — |
| OB | 1h | 1,173 | 214 | 1,604 | 1,547 | 57 | 181 / 663 / 329 | 1.2063 / 0.0841 |
| OB | 2h | 664 | 136 | 877 | 825 | 52 | 124 / 362 / 178 | 1.2331 / 0.0802 |
| OB | 4h | 437 | 113 | 562 | 497 | 65 | 102 / 230 / 105 | 1.2292 / 0.2169 |
| OB | 1d | 175 | 72 | 161 | 70 | 91 | 120 / 42 / 13 | 2.0211 / 0.9345 |

ATR medyanları yalnızca cache içinde gözlenen tamamlanmış pencerelerin betimsel medyanıdır; gelecekteki başarı olasılığı veya timeframe katsayısı değildir. Tepki ufku her timeframe'de en fazla 10 bardır; dolayısıyla bu bar sayısı farklı timeframe'lerde aynı saat süresini temsil etmez ve değerler cross-timeframe skor olarak birleştirilmemiştir. Aktif bölgelerin as-of fiyatına normalize uzaklık dağılımı da ayrıdır:

| Tür | TF | Aktif bölge | Medyan uzaklık (ATR) | Q25–Q75 (ATR) |
|---|---:|---:|---:|---:|
| FVG | 2h | 16 | 1.3440 | 0.7418–2.0613 |
| FVG | 4h | 15 | 0.8349 | 0.5197–1.4154 |
| FVG | 1d | 10 | 0.3481 | 0.2685–0.3871 |
| OB | 1h | 214 | 5.4570 | 2.3443–8.8895 |
| OB | 2h | 136 | 4.1365 | 2.3038–6.7085 |
| OB | 4h | 113 | 2.8222 | 1.7287–4.3991 |
| OB | 1d | 72 | 1.4657 | 0.8148–2.7702 |

Bunlar 25 Eylül snapshot'ındaki aktif zone'ların dağılımıdır; yakınlık eşiği ya da al/sat kararı değildir. 1d eşiği 40 olduğunda 28 cache'in tamamı `OK` oldu; 10 günlük FVG formation'ının tamamı 25 Eylül'deki son günlük barda oluştu ve sonrasında tamamlanmış bar olmadığı için henüz temas/reaksiyon örneği yok. Yani 40 bar **motoru warm-up'tan çıkarıyor**, fakat tarihsel günlük FVG lifecycle örneklemi sağlamıyor. Ayrıca 4h FVG'de **22** tamamlanmış pencere 68 bölgeye dağılmış, 27 temas sansürlenmiş ve hiçbir bölge iki tamamlanmış örneğe ulaşmamıştır. 2h FVG'de yalnızca 5 bölge iki veya daha fazla tamamlanmış örneğe sahiptir. 1d OB'de 175 bölgenin 120'sinde tamamlanmış reaksiyon örneği yoktur. Bu nedenle FVG için per-zone tepki tahmini veya bileşik skor kalibre edilmemiştir.

Aktif cross-timeframe bölgeler arasında aynı sembolde **4.735** farklı-TF çifti karşılaştırıldı. **556** çiftte pozitif fiyat aralığı kesişimi vardı ve bunların tümü aynı yöndeydi. Tür dağılımı: OB/OB 514 çift (28 sembol), FVG/OB 28 çift (14 sembol), FVG/FVG 14 çift (10 sembol). TF çifti dağılımı: 1h–2h 115, 1h–4h 104, 1h–1d 92, 2h–4h 101, 2h–1d 73, 4h–1d 71. Artan günlük FVG çiftleri 40 bar eşiğinden sonra oluşan günlük bölgeleri içerir. Tüm 4.735 karşılaştırmanın normalleştirilmiş boşluk/merkez uzaklığı ve IoU değeri `zone_scoring_mtf_pairs...csv` içinde; yalnızca kesişen 556 çift `zone_scoring_mtf_overlaps...csv` içindedir.

2h/4h FVG/FVG kesişen beş çift (toplam 14 FVG/FVG çifti içinde):

- ASELS bearish 2h/4h — IoU 0.955
- EREGL bullish 2h/4h — IoU 0.538
- ISCTR bearish 2h/4h — IoU 0.684
- TAVHL bearish 2h/4h — IoU 0.250
- TOASO bullish 2h/4h — IoU 0.267

Bu sayılar yeni bir eşik veya “confluence bonus” üretmez; yalnızca geometrik ilişkiyi gösterir.

## Kod ve Supabase şeması denetimi

### Kod akışı

- `data.py` 1h JSON cache'ini temizler; `resample_all_timeframes` ile 2h/4h/1d üretir ve `tamamlanmis_mumlar` ile kapanmamış mumları filtreler. `tamamlanmis_mumlar` içindeki 1h +30 dakika kuralı ve sağlayıcı timestamp'inin start/end semantiği bu repo dışında doğrulanmış değildir; rapor bu mevcut davranışı değiştirmez.
- `domain_engines/fvg` FVG'yi yalnızca 2h/4h/1d'de çalıştırır. Warm-up eşiği 2h/4h'de 100; 1d'de bu değişiklikle 40 bardır. 1h FVG runner tarafından açıkça atlanır.
- `domain_engines/order_block` 1h/2h/4h/1d frame'lerinde native replay yapabilir ve `OrderBlockConfig`/engine içinde global minimum-geçmiş veya warm-up bar şartı yoktur. Aday üretimi en az iki mumluk pair mantığına, aktif OB ise kaynak mum sonrası imbalance doğrulamasına bağlıdır. OB eşiği değiştirilmedi.
- `domain_engines/03_fvg.txt` arşiv/referans metni runtime import akışında kullanılmıyor; eski 100 bar metni bu kapsam içinde olduğu gibi bırakıldı.
- Prototip yeni OB/FVG tanımı, formasyon matematiği, diğer timeframe eşiği, bildirim veya üretim entegrasyonu eklemez.
- Yeni prototip için FVG profile açıkça `Dengeli` verildi (repo varsayılanı). `.env`/çalışan servis profil override'ı okunmadı; bu replay gerçek runtime profilinin kesin teyidi değildir.

### Yalnızca repo kod/SQL'inden Supabase bulguları

- `supabase_schema.sql` tek generic `public.bot_store` tablosu tanımlar: `store_key text primary key`, `payload jsonb not null`, `updated_at timestamptz not null default now()`.
- RLS etkin; SQL `public`, `anon` ve `authenticated` rollerinin tablo izinlerini kaldırıp `service_role` için select/insert/update verir. Bilerek policy yoktur. SQL dosyasının Supabase Dashboard'da gerçekten uygulanıp uygulanmadığı bu denetimde sorgulanmadı.
- `supabase_store.py` PostgREST üzerinden `GET` ile `store_key,payload` okur; `POST` upsert `on_conflict=store_key` kullanır. `main.py` başlangıçta 1h/1d cache anahtarlarını mevcut 48 elemanlı `ACTIVE_STOCKS` için ve çeşitli state anahtarlarını yüklemeyi dener. Uygulama kodu cache/state yazımlarını da yapar.
- Repo kodunda görülen anahtarlar: `cache:1h:<SYMBOL>`, `cache:1d:<SYMBOL>`, `state:daily_fetch_attempts`, `state:telegram_cooldowns`, `state:telegram_caps`, `state:telegram_delivery`, `state:heartbeat`, `state:son_tarama`. SQL'deki `store_key` açıklaması `state:telegram_delivery` ve `state:son_tarama` anahtarlarını listelemiyor; bu dokümantasyon yorumu eksik/stale, generic tablo şeması bu anahtarları teknik olarak engellemiyor.
- Supabase'te FVG/OB zone veya puanlama tablosu/şeması yok. SQL lifecycle state'in OHLCV cache'inden yeniden oynatıldığını belirtir. Bu prototip Supabase'e yeni kayıt yazmaz ve üretim keyspace'ine dokunmaz.

## Testler, sınırlar ve yeniden kullanım

- FVG minimum-history sınırları: **9 test geçti**; helper için 1d=40 ve 2h/4h=100, base detector ve public engine için 1d 39/40 ile 2h/4h 99/100 `WARMUP`/`OK` geçişleri doğrulandı.
- Sentetik prototip testleri: `test_zone_scoring.py` — güncel koşumda **12 geçti**. ATR seed, temas sonrası 3 barlık ölçüm, `as_of` ile gelecek barın dışlanması, açıkça incomplete işaretli mumun reddi, FVG warmup, ortak universe `as_of`, OB aralık sıralaması, IoU/ATR MTF ölçümü ve bileşik/olasılık üretmeme kontrolleri var.
- Bu değişiklikle ilişkili beş test modülünün (`test_domain_engines.py`, `test_domain_incremental_parity.py`, `test_domain_integration_regressions.py`, `test_zone_scoring.py`, `test_supabase_store.py`) güncel birleşik koşum: **72 geçti**.
- Supabase testleri FakeSession kullanır; canlı endpoint çağrısı yapılmaz.
- Test bağımlılığı `requests`, yalnızca repo dışındaki geçici `/tmp/formation-bot-zone-venv` ortamına kuruldu; requirements/proje bağımlılık dosyalarına eklenmedi.
- Önbellek replay'i yalnızca 28 `.json` dosyasını okudu. Import sırasında `dotenv` devre dışı bırakıldı ve `os.getenv` config yüklenirken varsayılan değeri döndürdü; credential kullanılmadı. `.pkl` deserialize edilmedi. Supabase `ping`, Yahoo fetch, Telegram isteği, deploy, commit ve push yapılmadı.
- `reports/` içindeki fiyat/zone CSV'leri 25 Eylül snapshot'ı olarak adlandırılmıştır; daha yeni gerçek veri olmadan canlı sinyal/karar girdisi değildir. Mevcut haliyle prototipin uygun sonraki kullanımı daha uzun yerel geçmiş üzerinde aynı sabit `as_of`/tamamlanmış-bar kurallarıyla sample-count ve sansür analizini sürdürmektir. Bileşik skor/olasılık için bu aşamada kalibrasyon yapılmamalıdır.
