# İç alarm/istek domain-context API planı

**Durum:** salt-okunur prototip ve araştırma sözleşmesi · **Tarih:** 2026-11-04
**Çalışma kodu:** [`alarm_context_packet.py`](../../alarm_context_packet.py) · **Örnek:** [ASTOR 2026-10-16 13:30](samples/ALARM_CONTEXT_ASTOR_2026-10-16.md) · **Üretici:** [`scripts/diagnostics/alarm_context_sample.py`](../../scripts/diagnostics/alarm_context_sample.py)

## 1. Amaç ve karar sınırı

Alarm ya da kişisel/on-demand isteğinde, o sembol ve zaman dilimi için **zaten üretilmiş** bağımsız domain sonuçlarını okunabilir metin ve tam yapılandırılmış JSON olarak bir araya getirmek; uygun olduklarında arşivdeki replay bulgularını da hangi çalışma, örneklem, yöntem ve sınırlardan geldiğini göstererek eklemek.

Bu, domain motorlarının üstünde duran açıklama/context paketidir. **Yeni sinyal, puan, yön oyu, al/sat kararı, hedef fiyat, stop, pozisyon boyutu, kârlılık tahmini ya da işlem tavsiyesi üretmez.** Bir domain'in diğerine üstün geldiğini varsaymaz; çelişen çıktıları olduğu gibi yan yana verir.

Bu belge ve prototip bir canlı HTTP endpoint değildir. Üretim alarm akışına, Telegram'a, Supabase'e, üyeler/public website'e veya kayıt/kalıcılık katmanına bağlanmamıştır. Mevcut alarmın tetiklenme, filtrelenme, tekilleşme veya teslim davranışı değişmez. Per-request arşiv/replay çalıştırılmaz.

## 2. Kapsam ve kapsam dışı

### İçeride

- `market_structure`, `volume_participation`, `order_block`, `fvg` ve ayrı çalışan `stabil` domain sonuçlarını **aynı sembol + TF + kapanmış-bar kesiti** için kabul etmek.
- Her domain'in tam native `DomainRunResult` yapısını strict JSON'a çevirmek; `result`, `export`, `details`, kalite, atlama, neden ve hata alanlarını sessizce düşürmemek.
- Okunabilir, insan kontrolüne uygun özet metin ve domain'e özel ham JSON'ı aynı pakette sunmak.
- Domain çıktısı yoksa, atlandıysa veya hata verdiyse bu durumları ayrı belirtmek. `empty result`, `missing`, `skipped` ve `error` eş anlamlı değildir.
- Replay kanıtlarını mevcut domain alanına bağlamak; kaynak ve popülasyon metadatasını taşımak; as-of tarihinden sonra üretilmiş/sonrası veri kullanan bulguları tarihsel olarak biliniyormuş gibi sunmamak.
- Saat dilimli as-of/zamanları ve sağlanan native çıktılardaki ileri tarihleri denetlemek.

### Dışarıda

- Tarama başlatma, provider veri çekme, motorları gizlice yeniden çalıştırma veya cache/registry state'ini değiştirme.
- Veritabanı, dosya, audit log ya da kullanıcı/üyelik saklama sistemi ekleme.
- Live webhook, Telegram mesajı, UI, public endpoint, rate-limit, auth ürünü veya deploy.
- Alarm kararını değiştirme; birleşik directional score, trade execution, backtest kârlılığı veya yatırım tavsiyesi.
- Farklı araştırma koşularının sayımlarını toplama ya da yüzdelerini tek bir “başarı oranı” gibi birleştirme.

## 3. Mevcut altyapı incelemesi

`domain_engines/runner.py::run_domain_engines` MS, volume, OB ve FVG'yi bağımsız `DomainRunResult` nesneleri olarak döndürür. Stabil aynı runner'ın beşinci kararı değildir; `run_stabil_domain` ile ayrıca çalışır ve `as_of_close`/izole replay seçeneklerine sahiptir. `notification_context.py` Telegram için seçilmiş, dar bir insan metni üretir; tam native domain JSON paketi değildir.

Mevcut replay belgeleri birbirinden farklı evrenler içerir ve tek bir popülasyon gibi okunmamalıdır:

- **176 × 4 TF = 704 seri**, 2026-10-21 zone/MS rapor seti.
- **177 × 4 TF = 708 seri**, 2026-10-28 DZ refresh'i; BRENT ayrıca içerir.
- **174 × 4 TF = 696 seri**, 2026-10-30 breakout/confirmation replay'i.
- **Stabil 100 sembol / 48 soru** davranış replay'i ve **50/53 canlı non-macro sembol** systematic study'si birbirinden de, yukarıdaki havuzlardan da ayrıdır.

Bu prototipin bulgu sicili `REPLAY_FINDINGS` içinde elle kaynaklandırılmıştır. Ham domain koşularını çalıştırmaz ve arşiv tablolarından otomatik sonuç çıkarmaz. Yeni bulgu eklenirken sayılar kaynak raporla tekrar karşılaştırılmalı, run/popülasyon/ölçüm birimi ve tarih eksikse açıkça `unknown` bırakılmalıdır.

## 4. API biçimi: callable contract (HTTP değil)

Mevcut callable:

```python
packet = build_context_packet(
    symbol="ASTOR",
    timeframe="4h",
    as_of=closed_bar_time,
    domain_results={
        "market_structure": ms_result,
        "volume_participation": volume_result,
        "order_block": ob_result,
        "fvg": fvg_result,
        "stabil": stabil_result,
    },
    trigger=original_trigger_or_none,
    context_kind="alarm",  # veya request / historical_sample
    generated_at=packet_time,
    reference_price=closed_bar_price,
    price_time=closed_bar_time,
    data_source="caller-supplied source label",
)
```

`packet_json(packet)` strict JSON metnini üretir. `as_of` ve verilmiş fiyat/trigger saatleri timezone-aware olmalıdır. Alarm türünde trigger zorunludur; trigger sembolü/TF'si sonuçlarla uyuşmalıdır. Sağlanan `price_time`, trigger zamanı ve serialize edilmiş native domain alanlarındaki ISO tarih/saatleri as-of sonrasındaysa paket üretimi hata verir. Bilinmeyen domain anahtarı da veri düşürmek yerine reddedilir. `closed_bar_count` istenirse negatif olmayan tamsayı olarak kesit doğrulamasına eklenir. `supplemental_replay_findings` çalıştıran tarafa ait sembol-özel kanıtı `replay_evidence.symbol_specific` altında tutar; sembol eşleşmesi, run_id, örneklem, metrik, yöntem, kaynak, caveat ve tarih alanlarını doğrular ve `timeline.available_at_snapshot` ekler. Bu kanıt native domain çıktısına karışmaz.

Yapının şematik özeti (gerçek pakette `native` alanı kısaltılmaz):

```json
{
  "schema_version": "1.1",
  "packet_type": "domain_context",
  "context_kind": "historical_sample",
  "symbol": "ASTOR",
  "timeframe": "4h",
  "as_of": "2026-10-16T13:30:00+03:00",
  "snapshot": {
    "reference_price": 183.2,
    "price_time": "2026-10-16T13:30:00+03:00",
    "closed_bar_count": 1075,
    "closed_bar_cut_required": true
  },
  "trigger": null,
  "domain_outputs": {
    "market_structure": {
      "status": "available",
      "summary": {"...": "readable projection"},
      "native": {"...": "complete serialized DomainRunResult"}
    },
    "volume_participation": {"status": "not_returned", "native": null},
    "order_block": {"status": "skipped", "reason": "...", "native": {"...": "..."}},
    "fvg": {"status": "error", "error": "...", "native": {"...": "..."}},
    "stabil": {"status": "available", "summary": {"...": "..."}, "native": {"...": "..."}}
  },
  "replay_evidence": {
    "market_structure": [{"finding_id": "...", "scope": {"...": "..."}, "timeline": {"...": "..."}}],
    "volume_participation": [],
    "order_block": [],
    "fvg": [],
    "stabil": [],
    "formation_alert": [],
    "symbol_specific": [{"finding_id": "astor-4h-replay", "scope": {"...": "..."}, "timeline": {"available_at_snapshot": false}}]
  },
  "interpretation_policy": {"nature": "descriptive_context_only"},
  "readable_text": "..."
}
```

### Durum sözleşmesi

- `available`: sonuç nesnesi geldi, motor hata/skip bildirmedi. `data_quality` ayrıca korunur; `available` kalite garantisi değildir.
- `not_returned`: çağıran o domain için nesne vermedi. Boş/nötr sonuç diye yorumlanmaz.
- `skipped`: native sonuç nesnesi atlandı olduğunu belirtti; `reason` ve bütün native alanlar korunur.
- `error`: native hata alanı dolu; boş liste/başarısız bulgu gibi gösterilmez.
- Geçerli sonuç içinde aktif OB/FVG bulunmaması, domain durumundan ayrı gerçek bir “aktif kayıt yok” çıktısıdır.

Her paket beş domain anahtarını sabit sırada taşır. Formasyonun alarm adayı native beş domain motorundan biri değil; mevcutsa `trigger` içinde orijinal alarm payload'u olarak bulunur. Formasyon replay bulguları `replay_evidence.formation_alert` altında ayrı tutulur.

## 5. JSON bütünlüğü ve okunabilir özet

`native` tam `DomainRunResult` yapısından üretilir. Dataclass alanları, nested map/liste ve tüm `details` saklanır. DataFrame/Series/Index/ndarray JSON'da tip, indeks/kolon, shape ve dtype metadatası taşıyan etiketli yapılara çevrilir; sayısal olmayan JSON anahtarı olası key-collision yaratmamak için tagged mapping olarak saklanır. `NaN`/Infinity `null` olur; kalan desteklenmeyen Python tipleri sessizce atılmaz, açık hata verir. Son çıktı `allow_nan=False` ile doğrulanır.

`summary` ve `readable_text` ham native verinin yerini almaz. Örneğin OB kısa metninde en yakındaki beş aktif kayıt gösterilirken tam liste `native` JSON'dadır. Stabil'in tüm history/checkpoint ayrıntısı JSON'da korunur; metinde son kapanış, bilinen destek seviyesi, trend/rol hazırlığı ve son davranışın okunur özeti gösterilir. Özet birleştirme/puanlama yapmaz.

**Boyut denemesi:** gerçek ASTOR 4h sonuçlarında native Stabil history dahil strict JSON yaklaşık **7,12 MB**; okunabilir domain metni yaklaşık **15,8 KB** çıktı. Bu, tam JSON'u koruyan prototipin ölçüsüdür; her Telegram mesajına kopyalamak veya public web yanıtı yapmak için bir öneri değildir. Gzip/response-size/SLA kararı bu kapsamda alınmadı; büyük native alanı düşürmek de kullanıcı talebindeki “tam JSON” kabulünü değiştirir.

## 6. Replay kanıt sicili ve yorumlama sınırları

Her bulgu `finding_id`, ilgili domain(ler), başlık/özet, kapsam, ölçüm birimi, örneklem n'si, metrikler, yöntem, sınırlamalar ve kaynak dosyaları taşır. `recorded_at` veya `data_through` yoksa uydurulmaz. Pakette ayrıca her bulgu için `timeline` oluşturulur:

- `available_at_snapshot=true`: kayıt ve ölçüm tarihleri as-of tarihine kadar tamamlanmış.
- `false` / `later_than_snapshot`: rapor veya kullanılan veri kesiti as-of sonrasına geçiyor; tarihsel kesitte bilinmiyordu.
- `null`: rapor tarihi ya da veri sonu eksik/saat düzeyi belirsiz. Bu da “biliniyordu” anlamına gelmez.

### Paketlenen bulgular

| Domain / kaynak | Örneklem, ölçüm ve kısa sonuç | Yöntem / sınır |
|---|---|---|
| Market Structure · `replay-2026-10-21` | 176 sembol/704 seri içinden seçilmiş **4h external BOS n=3.387**; yön uyumu %98,0; rapor tanımındaki CALISTI %71,0; devam-yok %7,5, ters yön %0,9. | Ölçüm çapası `confirmed event_bar`, aday bar değil; sonraki 12 native 4h mum ATR ile ölçülür. İç yapı, CHOCH, sweep ve diğer TF farklıdır; yön uyumu devamın garantisi değildir. BIST havuzu mevcut ASTOR olasılığı değildir; işlem maliyeti/fill/kârlılık ölçülmedi. Kaynak: `REPLAY_OZET_2026-10-21.md` §8, `ARASTIRMA_HATTI.md`. |
| OB + FVG ortak temas · aynı 176×704 rapor seti | **240.484 temas epizodu**; TF'ye göre beklenen yönde ≥1 ATR tepki %65,0–%66,5. OB/FVG birlikte. | 12 sonraki native barın ATR-yolu, epizot başına. Bir aileye özel oran değildir; TF aralığı tek oran olmaz; maliyet/işlem getirisi değildir. Kaynak: `REPLAY_OZET_2026-10-21.md` §3. |
| OB yaşam döngüsü · aynı set | **131.901 OB zone**, **197.521 temas epizodu**; TF'ye göre 3+ temas %10,7–%13,3; terminal fiyat ihlali %85,4–%93,6. | Zone ve temas epizodu ayrı birimlerdir. `native_full_fill` yapısal olarak `False`; ihlal metriği `native_price_violation`. Geçilme, tek temas tepkisini silmez ve kalıcı bariyer garantisi vermez. |
| FVG yaşam döngüsü · aynı set | **55.145 FVG zone**; 12.680 (%23,0) arşivde temas almamış; 3+ temas yalnız **4 zone** (en fazla 5). | Kapsam 2h/4h/1d; bu hat 1h FVG üretmez. Arşivde temas almamak gelecekte temas olmayacağını göstermez. Zone tekrar teması ile ortak OB/FVG temas tepkisi ayrı ölçümlerdir. |
| Hacim/katılım · 176×704 tabloları | 4h zone-touch: Q1 RVOL **n=6.740 / %70,1**, Q4 **n=11.928 / %61,0**. Ayrı 4h MS-event: Q1 **n=5.233 / %66,1**, Q4 **n=8.248 / %69,5**. | Olay aileleri/kohortları farklıdır. Tek “yüksek hacim iyi/kötü” kuralına indirgenmez; Q1/Q4 arşiv kovasıdır, canlı RVOL eşlemesi yaklaşık olabilir. Tam run ID/rapor tarihi tabloya yazılmadı. 177×708 DZ yenilemesiyle karıştırılmaz. |
| Stabil C02 · 100 sembol/48 soru · manifest 2026-11-01 | **n=1.976** temas; tam 8×4h ufuk n=1.943, sağ-sansürlü n=33. Tam ufuk medyan korunan değişim: ilk/ikinci/3+ temas **−0,066 / +0,155 / −0,376 ATR**; gruplar n=1.773/137/33. 3+ grubun tek-sembol payı %81,8. | Tamamlanmış H4 checkpoint, causal D/W input, sabit giriş daily ATR, 0,35 daily ATR aralıklı bağımsız temas. 3+ grup küçük/yoğun; ilk arşiv temas yaşı UNKNOWN olabilir. 100 sembol, 107.441 checkpoint, 10.417 first-seen event, 48 soru, 642 satır; candidate regime mapping **user_confirmed=false**. Manifest kesin data cutoff/source hash saklamıyor. |
| Stabil live-universe systematic · ayrı 50/53 çalışma | 53 canlı non-macro sembolün **50'si** arşivde (XU50/XBANK/XUSIN eksik); 2025-05-07…2026-10-19, **284 sinyal / 75,9 hafta**; sonraki H4 destek tutunması %91,5; 8×4h medyan +0,262 ATR. | 6-bar cooldown; sonraki bar destek üstü kapanış ve ATR kapanış yolu. Erken/geç yarı medyanı +0,426/+0,020 ATR; dönem değişimi var. Aggregate JSON'da kesin run tarihi, hash, sinyal bazlı native paket veya emir/fill/maliyet yoktur. 100/48 davranış replay'iyle birleştirilmez. |
| Formasyon · FRM-19/20 | **33.964 formasyon**, 171 açık/sağ-sansürlü. FRM-19: zone var n=11.905 %75,9 vs yok n=20.232 %77,0 (−1,1 pp). FRM-20: rol uyumlu n=17.103 %79,6 vs uyumsuz n=14.857 %73,2 (+6,4 pp). | İki karşılaştırmanın alt grupları farklı; betimsel kohort ilişkisi, canlı neden/gelecek sonuç değildir. Formasyon doğum aralığı 2026-10-19'a kadar; rapor/run tarihi dosyada belirtilmemiş. Kaynak: `FORMASYON_SONUCLARI.md` §FRM-19–20, `KOLON_SOZLUGU.md` §13. |

**Popülasyon uyarısı:** Ekim 21 baseline, Ekim 28 DZ, Ekim 30 breakout, Stabil 100/48 ve Stabil 50/53 sayıları eklenemez, yeniden ağırlıklandırılamaz veya tek bir başarı yüzdesi yapılamaz. Ayrıca bu sayılar ASTOR/SNGYO'ya özel conditional probability değildir.

## 7. Historical as-of kontrolü: ASTOR denemesi

Seçilen kesit: **2026-10-16 13:30 +03**, son tamamlanmış H4 kapanış **183,20**, 1.075 kapanmış 4h bar. H4 normal domain'leri kesilmiş bu barlardan hesaplandı; Stabil runner'a gerçek veriyle `as_of_close` verildi. Mevcut domain'ler aynı yön skorunda birleştirilmedi:

- MS dış ve iç bağlamı bearish, kaliteler 86/84.
- Volume participation `PARTICIPATION_UP_BREAK_SUPPORTED`; RVOL 2,247×, göreli işlem değeri 2,040×.
- OB 26 kayıt, 25 aktif; metinde en yakındaki beş, JSON'da tüm native kayıtlar.
- FVG geçmiş kayıt sayısı 179, fakat bu kesitte aktif boğa/ayı FVG kaydı yok.
- Stabil günlük destek 172,10, taban 165,512; destek 15 Ekim günlük kapanışında belirlenmiş. Haftalık `WEEKLY_NOT_UP`, günlük `DAILY_PULLBACK_TOO_DEEP`, 4h `H4_BUYERS_EMERGING`; roller ready.

### Aday satırı neden trigger değil?

`docs/arastirma/sonuclar/kirilim_replay/adaylar.csv.gz` içindeki ASTOR/4h `anchor=2026-10-16 13:30+03` satırı, `research/kirilim_denetim.py` tarafından `frame.index[b]` olarak yazılır: H4 barının **açılış etiketidir**. Bu bar 17:30 +03'te kapanır ve ancak o zaman satırdaki candidate-state/strength/quality bilinebilir. 13:30 +03 kesitinde o satır gelecektedir. Bu nedenle örnek pakette trigger `null` ve satırın aday/kalite/kuvvet alanları dahil edilmedi; satırın 19 Ekim teyit/sonuç alanları da pakete alınmadı. Bu, önceki deneme notundaki “13:30 aday tetikleyicisi” varsayımını düzelten as-of kontrolüdür.

Replay araştırmalarının bir kısmı 19 Ekim'e kadar veri kullanır veya 21 Ekim/1 Kasım'da kaydedilmiştir; ASTOR snapshot'ından sonra gelir. Bunlar pakette context olarak gösterilse de her satırda **`SONRAKİ ARAŞTIRMA`** işareti vardır. Tarihsel 13:30 alarmının o an bileceği bilgiyle aynı değildir ve o kesitin domain native JSON'ına karışmaz.

### 7.1. On sembolde tek tek JSON ve replay denemesi

İlk sürümün replay alanında yalnız raporlardaki havuz/koşu düzeyi bulgular vardı; sembole özgü breakout replay özeti yoktu. Bu açık, `schema_version=1.1` içinde ayrı `replay_evidence.symbol_specific` dizisi ve caller-supplied bulgu doğrulamasıyla kapatıldı. Her ek kanıtın `symbol`, `scope.run_id`, `sample`, `metrics`, `method`, `limitations`, `sources`, `recorded_at/data_through` alanları kontrol edilir; tarih bilgisi otomatik `timeline` olarak yazılır. Bu veriler güncel native domain çıktısına karıştırılmaz.

Aynı kesitte **ASTOR, THYAO, GARAN, ASELS, SISE, TUPRS, BIMAS, EREGL, FROTO, SNGYO** için 10 ayrı packet üretildi. Her birinde beş domain `available`, aynı 1.075 kapanmış H4 barı ve `trigger=null` vardı. Bu, tüm domainlerin çalıştığını gösterir; her state olumlu/kuvvetli ya da veri kalitesi tam demek değildir. Her JSON'a sembolün 4h replay aday satırlarının tamamı ve özet metrikleri ayrı, sonradan tarihli evidence olarak eklendi. Sembole özel 4h breakout replay'inden alınan n ve medyan aşağıdadır:

| Sembol | MS dış state | VP state | Aktif OB | Aktif FVG boğa/ayı | Stabil H4 | Replay aday / valid-nonoverlap | Medyan end ATR* |
|---|---|---|---:|---:|---|---:|---:|
| ASTOR | bearish / aşağı | UP_BREAK_SUPPORTED | 25 | 0/0 | BUYERS_EMERGING | 21/16 | −1,232 |
| THYAO | bearish / aşağı | LOWER_ABSORPTION_INVALIDATED | 16 | 0/1 | BUYERS_EMERGING | 27/25 | −1,140 |
| GARAN | TRANSITION_DOWN / neutral | CONFLICT | 15 | 0/0 | RECOVERY_CONFIRMED | 24/20 | +0,242 |
| ASELS | bearish / aşağı | CONFLICT | 25 | 0/0 | SELLING_WEAKENING | 31/27 | −0,535 |
| SISE | bearish / aşağı | CONFLICT | 10 | 0/0 | BUYERS_EMERGING | 27/22 | −0,197 |
| TUPRS | bullish / yukarı | LOWER_ABSORPTION_CONFIRMED | 29 | 0/1 | SELLING_WEAKENING | 33/26 | +0,300 |
| BIMAS | bearish / aşağı | LOWER_ABSORPTION_CONFIRMED | 20 | 0/0 | SELLING_WEAKENING | 25/22 | −0,462 |
| EREGL | bearish / aşağı | CONFLICT | 18 | 0/0 | BUYERS_EMERGING | 23/21 | −0,216 |
| FROTO | bearish / aşağı | DOWN_BREAK_SUPPORTED | 23 | 0/1 | BUYERS_EMERGING | 25/23 | +1,727 |
| SNGYO | bearish / aşağı | DOWN_BREAK_SUPPORTED | 12 | 0/1 | NO_RECOVERY | 11/9 | −1,224 |

\\* Replay ortancası yalnız sembolün 4h satırlarındaki `outcome_status=VALID` ve `nonoverlap=true` alt kümesi içindir; yönlü 10. kapanışın başlangıç ATR'sine oranıdır. Rapor **2026-10-30**, veri sonu **2026-10-19** olduğundan bu 10/16 kesitinde her sembol için `available_at_snapshot=false`; ne gerçekleşmiş getiri ne olasılık ne de tarihsel alarm bağlamıdır. ASTOR'daki `anchor=2026-10-16 13:30` satırı H4 barının açılışıdır, kapanışı 17:30'dur; sample domain packet'te yoktur. Tam tek tek yorumlar ve JSON'lar: [inceleme](samples/ALARM_CONTEXT_10_SEMBOL_INCELEME_2026-10-16.md), [10 JSON ZIP'i](samples/ALARM_CONTEXT_10_SEMBOL_2026-10-16.zip).

**Contract kontrolü:** On sembolün tamamında `market_structure.data_quality=null`; bu engine üst düzey bu alanı vermiyor, fakat dış/iç scope quality değerleri mevcut. JSON bunu `null` olarak korur, sahte `OK` üretmez. Bu, beş domainin her birinin `available` olduğu sonucu değiştirmez. VP'nin `data_quality` alanı state ile aynı, OB/FVG/Stabil `OK` raporladı.

**Yorum:** ASTOR'da MS bearish iken volume up-break-supported; TUPRS'ta MS bullish iken volume absorption-conflict ve Stabil H4 selling-weakening; FROTO'da MS/VP down-break desteklerken Stabil H4 buyers-emerging. Çelişen domainleri ortak puana sıkıştırmak veri kaybettirirdi. OB/aktif FVG sayıları mevcut durum envanteridir; replay medyanları sonradan elde edilmiş ve sembol başına örnekler küçüktür. Bu nedenle örnekler “var/yok/çelişkili” diye okunur; al/sat sonucu çıkarılmaz.

## 8. Çalıştırma ve doğrulama

```bash
.venv/bin/python -m pytest -q test_alarm_context_packet.py
.venv/bin/ruff check alarm_context_packet.py test_alarm_context_packet.py scripts/diagnostics/alarm_context_sample.py scripts/diagnostics/alarm_context_10_symbol_review.py
.venv/bin/python scripts/diagnostics/alarm_context_sample.py \
  --text-output docs/arastirma/samples/ALARM_CONTEXT_ASTOR_2026-10-16.md
.venv/bin/python scripts/diagnostics/alarm_context_10_symbol_review.py
```

Tam native JSON örneği ayrıca, isteğe bağlı ve büyük olduğundan, geçici bir yere üretilebilir:

```bash
.venv/bin/python scripts/diagnostics/alarm_context_sample.py \
  --json-output /tmp/alarm_context_ASTOR_2026-10-16.json
```

ASTOR tek-sembol Markdown örneği 17.832 bayttır. 10 sembolün tam JSON'ları ayrı ZIP üyeleridir; ZIP 6.299.250 bayt, sıkıştırılmamış JSON toplamı 72.232.710 bayt. Büyük çıktılar sebebiyle tek tek 10 gevşek JSON dosyası yerine kullanıcı isteği için JSON üyelerini taşıyan ZIP verildi; `--json-dir` ile ayrı dosyalar da üretilebilir. Hiçbiri DB'ye yazılmaz.

### Mevcut otomatik test kapsamı

`test_alarm_context_packet.py` şu sözleşmeleri sınar:

1. Dataclass/native alanların kayıpsız tutulması ve strict JSON; enum, `NaN`/`Infinity`, ndarray, DataFrame, Series, index/shape/dtype.
2. Her domain için `available`, `not_returned`, `skipped`, `error` durumları ve okunabilir missing/skipped/error metni.
3. Replay bulgusunun doğru domain'e bağlanması; shared OB/FVG bulgusunun her ikisinde görünmesi; örneklem, kapsam, kaynak, yöntem, caveat ve timeline alanlarının zorunluluğu.
4. As-of sonrasındaki trigger, price-time veya native ISO tarih/saatinin reddi; mevcut kesit ile daha sonra kaydedilmiş araştırmanın ayrılması.
5. Naive timestamp/unknown domain reddi ve string dışı mapping key collision'ının önlenmesi.
6. Symbol-specific replay bulgularının zorunlu kaynak/kapsam/metrik/caveat alanları, sembol eşleşmesi ve as-of timeline etiketi.
7. `closed_bar_count` için tamsayı/non-negative doğrulaması.

ASTOR tek-sembol JSON örneği strict biçimde doğrulandı (7.120.527 byte); ayrıca 10 sembollük ZIP içindeki 10 tam JSON ayrı ayrı parse edildi, hash/uzunluk manifestiyle eşleşti ve her birinde 5 domain, 1.075 kapanmış bar, sonradan tarihli sembol replay'i ve sembolün tüm 4h replay satırları bulundu. JSON'daki replay satırları kaynak CSV ile alan/değer düzeyinde eşleşti. Prototip testleri **11 passed**; tam repository **3.382 passed, 43 skipped**, tam Ruff ve `git diff --check` temiz. Önceki ASTOR Stabil spot-check'i 48 soru/552 satır vermişti; 100-sembol replay yeniden koşturulmadı. Bu ölçümler full native archive hashlerini veya production davranışını doğrulamaz.

## 9. Entegrasyon için gelecekteki plan (ayrı onay gerekir)

1. **Snapshot sahibi:** alarm/request caller'ı güncel sembol/TF OHLCV'yi toplar; `mum_kapanis_anlari` veya eşdeğer kapanış sözleşmesiyle son tamamlanmış mumda keser. Ham çalışma zamanı/erken alarm ile kapanmış-bar context'i karıştırılmaz.
2. **Bağımsız motor çağrıları:** mevcut MS/VP/OB/FVG runner sonuçları ve ayrı Stabil sonucu aynı as-of ile bir defa elde edilir. Builder motor çağırmaz.
3. **Orijinal tetikleyici:** yalnız gerçek alarm payload'u verilir; `triggered_at`/bar zamanı aynı sembol ve TF'ye uyar. `anchor` bar-start ise trigger bilinirlik zamanı candle close'dur.
4. **Builder:** çağıran native results + context metadata'yı builder'a verir. Builder symbol/TF, timezone, timestamp, JSON uyumluluğu ve future ISO değerlerini denetler; replay evidence'ı static sourced registry'den ve verilmişse ayrı, kapsamlı/tarihli symbol-specific ekten alır.
5. **Consumer:** önce okunabilir metin, ardından talep edilirse JSON. Domain native JSON korunur; hiçbir field score/decision'a çevrilmez. Hatalı veya atlanmış motor, paket durumunda açıkça görünür.
6. **Arayüz/HTTP/Telegram/retention:** bu çalışma dışında ve ayrı ürün/güvenlik kararıyla ele alınır. Kullanıcının mevcut kabulü kullanıcıya özel/internal ve kalıcılıksızdır; burada endpoint ya da storage kurulmaz.

## 10. Açık riskler / yapılmadan bırakılanlar

- Builder `as_of` sonrası ISO tarihleri yakalar ama **caller'ın causal engine input'u verdiğini veya her barın gerçekten tamamlandığını tek başına kanıtlayamaz**. `closed_bar_cut_required=true` bir sözleşme işaretidir, veri-soy ağacı doğrulaması değildir. Production bağlamı için source/bar close metadata gerekir.
- Tarihi/run ID'si olmayan bazı replay raporları `available_at_snapshot=null` olarak kalır. Belirsizlik “snapshot'ta biliniyordu” şeklinde çözümlenmemiştir.
- Stabil 100/48 manifesti exact data end/source hash saklamaz; systematic sonuç JSON'ı da tarih/source hashes/signal-level raw packet vermiyor. 50/53 çalışma bilgi notu olarak eklenmiştir, 100/48 sayılarıyla karıştırılamaz.
- Mevcut JSON boyutu HTTP veya mesajlaşma için büyük olabilir. Tam native JSON kabulünü korumak için istemci/transport boyutu ölçülmeli; alan kırpma/gzip/cache kararı kullanıcı onayı olmadan yapılmamalı.
- Bu deney gerçek live trigger ve live delivery görmemiştir. Alarm akışına bağlanma, provider hata fallback'i, retry, kullanıcı istekleri, privacy, auth veya Telegram limitleri doğrulanmadı.
- `REPLAY_FINDINGS` elle güncellenen bilimsel/sürüm kontrollü sicildir. Yeni sonuç eklemek, eski run sayılarını otomatik güncellemek veya “sonuçlar”ı yeniden hesaplamak değildir; her değişiklik kaynak + run manifestiyle çapraz incelenmelidir.
- Regime mapping kullanıcı tarafından onaylanmadığı için Stabil'in dikey/yatay aday sınıflaması context'te kural/etiket gibi sunulmaz.

## 11. Kabul ölçütleri (bu prototip)

- [x] İncelenen mevcut engine/replay sonuçları kaynak ve popülasyonuna göre ayrıldı.
- [x] Beş domain için tam native JSON alanı ve okunabilir özet vardır; unavailable durumları açık.
- [x] Replay kanıtlarında run/scope/n/method/caveat/source yanında kayıt/veri zaman çizgisi vardır.
- [x] Current snapshot, tarihsel replay kanıtı ve sonradan bilinen araştırma ayrı tutulur.
- [x] Strict JSON, candidate/price/native future timestamp guard ve gerçek ASTOR örneği test edildi.
- [x] İç kullanım/prototype sınırında kaldı; canlı alarm, veri saklama, public website veya işlem tavsiyesi eklenmedi.
- [ ] Üretim API'si, live entegrasyon, kalıcılık, deploy veya kullanıcıya otomatik teslim: **yapılmadı; ayrı karar/izin gerekir.**
