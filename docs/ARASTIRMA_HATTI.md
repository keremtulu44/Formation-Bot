# Araştırma Ölçüm Hattı

`backfill_data/` arşivini (177 sembol × 1h/1d, 365 gün) dört zaman diliminde
ölçüp araştırma sorularının cevabını üreten hat. Canlı tarayıcıdan tamamen
bağımsızdır: motorları **değiştirmez**, yalnız çıktılarını okur.

## Çalıştırma

```bash
# Küçük pilot (birkaç sembol, hızlı doğrulama)
python scripts/backfill/arastirma_kosu.py --limit 3

# Tam koşu (~60 dk, 176 sembol × 4 zaman dilimi = 704 iş)
python scripts/backfill/arastirma_kosu.py

# Yalnız rapor: yeni ölçüm yapmadan mevcut JSONL çıktısından üret
python scripts/backfill/arastirma_kosu.py --agrega

# Belirli semboller
python scripts/backfill/arastirma_kosu.py --semboller THYAO,GARAN,ASELS

# Kaldığı yerden devam (varsayılan davranış) / baştan
python scripts/backfill/arastirma_kosu.py
python scripts/backfill/arastirma_kosu.py --zorla
```

Çıktı: `arastirma_cikti/*.jsonl` (ham gözlemler) ve
`docs/ARASTIRMA_BULGULARI.md` (rapor). `arastirma_cikti/` git'e girmez
(`.gitignore`); rapor girer.

Koşu **idempotent**tir: `meta.jsonl` içinde kaydı olan `(symbol, timeframe)`
çiftleri atlanır, dolayısıyla yarıda kesilen koşu aynı komutla devam eder ve
hiçbir iş çift sayılmaz. Bir sembol patlarsa koşu durmaz; hata
`hatalar.jsonl`'e yazılır, rapor sonunda kaç serinin atlandığı açıkça
belirtilir.

## Modüller

| Dosya | Görev |
|---|---|
| `research/arsiv.py` | CSV.gz → zaman dilimi çerçeveleri. 2h/4h repo'nun kendi `resample_ohlcv`'iyle üretilir (seansa 09:30 hizalı). |
| `research/olcum.py` | Ölçüm çekirdeği: uzanım yolları, şekil metrikleri, kenar tespiti, deneme/engelleme, VP örnekleme. |
| `research/kayit.py` | Motor çıktısını gözlem satırlarına çevirir: zone, dokunuş, swing, event. |
| `research/rapor.py` | Gözlem satırlarından soru bazlı Markdown tabloları üretir. |
| `scripts/backfill/arastirma_kosu.py` | CLI: koşu planı, JSONL yazımı, agregasyon. |

## Ölçüm sözleşmesi

**Anti-lookahead.** Her ölçüm yalnız çapadan *sonraki* barları okur; çapa
barının kendisi hiçbir uzanıma katılmaz. MS eventlerinde çapa `event_bar`
(onay) dir, `candidate_bar` değil — aday anından ölçmek geleceği kullanmak
olurdu. `test_lookahead_guard_ufuk_disi_bar_olcumu_degistirmez` bunu kilitler:
ufuk dışına dev bir hareket eklendiğinde 12 barlık ölçüm birebir aynı kalmalı.

**ATR normalizasyonu.** BIST 5 TL ile 500 TL arasında hisse barındırdığı için
TL veya yüzde havuzlanamaz. Her uzanım çapa anındaki ATR'ye bölünür ve o ATR
değeri gözlemle birlikte saklanır.

**Sınırlı tepe.** Tepe metrikleri en büyük ufuk (12 bar) içinde hesaplanır;
40 barlık ayrı bir "uzun tepe" taşınır. Sınırsız gelecekte `max` almak uzun
vadeli sürüklenmeyi tepki gibi gösterir: 12 barda hiç tepki vermeyen bir zone
800 bar sonraki fiyat aralığı sayesinde dev tepe alır ve tepe-payı negatif
çıkar. "Anlık mı yavaş ama kalıcı mı" ayrımı bu iki pencerenin
karşılaştırılmasıyla yapılır.

**Sağdan sansür.** Pencere veri sonuna takıldıysa `sansur=True` olur ve o
gözlem asla "başarılı direnç/destek" sayılmaz. `engelledi` üç değerlidir:
`True` / `False` / `None` (karar verilemez). "Henüz kırılmadı" ile "başarılı
direnç" ayrımı budur ve kararsız satırlar ayrı tabloda raporlanır.

**Ön-tanımlı eşikler.** Ölçümden sonra eşik seçilmez. `ESIK_IZGARA`
(0.25/0.5/1/1.5/2 ATR), `YUKSEKLIK_KOVALARI`, `DENEME_ESIKLERI` (0.25 ana;
0.15/0.50 duyarlılık kontrolü) ve `PAY_PENCERELERI` sabittir; sonuçlar ızgara
olarak verilir. Eşikler değişirse `config_hash` değişir ve her satırda taşınır.

**Güven etiketi.** Her hücrede `n` ve etiket vardır: `n>=30` YETERLI,
`n>=15` KISMI, altı ZAYIF (`analytics/backtest.py` ile aynı eşikler).
Domain × zaman dilimi × yön × kova çaprazları hızla inceldiği için n'siz
yüzde yanıltıcıdır.

**Belirsiz gözlem düşürülmez.** Çapa barı zone'un iki kenarına birden
değiyorsa (`TUM_ZONE`) veya tamamen içindeyse (`ZONE_ICI`) kenar-ancored yön
belirlenemez; bunlar `OLCULEMEDI` kovasında ayrıca raporlanır. Aynı kural
`volume_usable=False` satırlar için de geçerlidir: hacim bayrakları kolon
olarak taşınır, satır filtrelemek için kullanılmaz.

**Kimlik `bar_time`.** Pencere içi indeks yeniden koşuda kayar; kalıcı kimlik
`bar_time` metnidir. `source_index`/`identity`/`event_uid` yalnız tanı
amaçlıdır.

## Bulunan iki survivorship tuzağı

İkisi de final snapshot'a dayanan bir ölçümü **sistematik olarak yanlı**
yapar; ikisi de bu hatta çözülmüştür.

### 1. OB motoru dolan zone'ları listesinden siler

`OrderBlockEngine._update_existing` bir zone dolduğunda veya fiyat içinden
geçtiğinde kaydı `self._records`'tan çıkarır. Dolayısıyla replay sonundaki
`records` yalnız **hayatta kalanları** verir; geçmişi tutan bir liste yoktur.

THYAO 4h ölçümü: `replay_ob_zones` ile **138 zone**, final snapshot ile
**18 zone** — 7.7× eksik sayım. Snapshot kullanılsaydı "%kaçı geçildi"
sorusu yalnız *geçilmemiş* zone'lar üzerinden cevaplanmış olurdu; yani cevap
baştan belli olurdu.

Çözüm: repo'nun kendi `replay_ob_zones` fonksiyonu kullanılır. Bar bar
`pre_active`/`post_active` karşılaştırır ve silinen zone'ları
`native_terminal_*` alanlarıyla kaydeder.

### 2. `structural_role` zamanla mutate olur

`market_structure_state.clear_role_if_matches` bir rolü yeni bir swing'e
atadığında aynı rolü taşıyan diğer swing'leri `NEUTRAL_*`'a sıfırlar. Replay
sonundaki `external_swings`/`internal_swings` listesi bu yüzden yalnız
rollerin **güncel** sahibini gösterir.

THYAO 4h ölçümü: final snapshot'ta 359 swing içinde `PROTECTED_HIGH` **2**,
`PROTECTED_LOW` **0**, `WEAK_*` **0**. Yani PH/PL ve WL/WH soruları bu
alanla *hiç* cevaplanamazdı.

Çözüm: MS motoru bar bar `update()` ile koşulur ve her bardan sonra
`StructureContext` üzerindeki rol kimlikleri (`protected_high_identity`,
`weak_low_identity`, …) okunur. Kimlik değişimleri aralık olarak kaydedilir
(`ms_adimli_kosu` + `rol_gecmisi_guncelle`). Maliyet O(bar)'dır, swing
taraması yoktur. Ölçüm birimi **(swing × rol aralığı)** ve çapa rolün
*atandığı* bardır; pencere rolün ne zaman bittiğinden bağımsız sabit
`SWING_PENCERESI` bardır. Bu daireselliği önler: rol genellikle kırıldığında
temizlendiği için pencereyi rol aralığıyla sınırlamak "engelledi mi" sorusunu
baştan cevaplanmış varsaymak olurdu.

Bu düzeltmenin kendisi de bir hata yakaladı: ilk sürüm kimlik değişmediğinde
bile aralık başlangıcını güncelliyordu ve **30.238 aralığın tamamı 1 bar**
görünüyordu. Düzeltme sonrası 305/334 aralık birden uzun (ortanca 10 bar).
`test_rol_araligi_cok_bar_surabilir` bu hatayı kilitler.

## Canlı botta bulunan MS çökmesi

`MarketStructureEngine.replay()` bazı gerçek BIST serilerinde
`ValueError: confirmed break references must still be active` ile patlar
(AEFES 1h, ALFAS 1h ve ALGYO 2h üzerinde doğrulandı). Bu, bu hattın kodundan
kaynaklanmaz: canlı runner'ın `_run_market_structure` içinde kullandığı yolun
birebir aynısıdır ve bar bar `update()` çağrısı da aynı hatayı verir.

`market_structure_runtime_bridge` bu hatayı yakalayıp kurtarmayı deniyor,
ancak kurtarma yolu da başarısız olunca hata yukarı fırlıyor. Canlı botta
`_execute_domain` bunu yakaladığı için bot çökmez; bunun yerine **o sembolün
MS domaini sessizce boş kalır** — BOS/CHOCH sinyali üretilmez ve kullanıcıya
bir uyarı gitmez.

Ölçüm hattı hatayı izole eder (`sembol_timeframe_gozlem` içinde ayrı `try`):
MS başarısız olsa bile OB/FVG/VP ölçümleri üretilmeye devam eder, hata
`meta.ms_hata` alanına yazılır ve raporda `ms_hatali_seri` sütununda
sayılır. AEFES 1h için bu, aksi halde kaybolacak 419 zone ve 710 dokunuş
epizodunu kurtarır.

## Bağımlılık notu

`bist_calendar`, `exchange_calendars` bulunamadığında **fail-closed**
davranır: `SessionStatus.UNKNOWN` döner ve otomatik tarama kapanır. Bu doğru
bir tasarım kararıdır ama `requirements-termux.txt` içinde
`exchange-calendars` **yok**. Ana bot Termux'ta çalıştırılırsa takvim
bulunamaz ve tarama hiç başlamaz; telefon tarafı yalnız
`scripts/backfill/yahoo_backfill.py` için kullanılmalıdır (o betik zaten
hiçbir ağır bağımlılık import etmez).

Test paketi `requirements.txt`'teki tüm bağımlılıkları bekler. Eksik
`matplotlib`/`exchange-calendars` kurulumunda 119 test başarısız görünür;
bunların tamamı ortam eksiğidir, kod hatası değildir. Tam kurulumda:
**1483 passed, 43 skipped, 0 failed**.
