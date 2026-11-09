# Stabil sistemi — destek/direnç mantığı, ok kuralları ve replay kanıtı incelemesi

**Tarih:** 2026-11-08 · **Durum:** İnceleme + iki gerçek hata düzeltmesi. **Ok kuralları, eşikler ve alarm
davranışı değiştirilmedi**; ok tarafı bu turda yalnız anlaşıldı ve ölçüldü.
[Ana rehber](STABIL_REHBERI.md) · [replay hatları](STABIL_REPLAY_HATLARI.md) · [davranış modeli](STABIL_DAVRANIS_MODELI.md) ·
[dikey uyarı](../tasarim/STABIL_DIKEY_UYARI_2026-11-05.md) · [direnç ön kontrolü](../tasarim/STABIL_DIRENC_CANLI_TEST_ON_KONTROL_2026-11-06.md)

> Bu dosya yatırım tavsiyesi veya kârlılık iddiası değildir. Bütün oranlar betimleyicidir; olaylar
> aynı hisse/gün içinde kümelenir, bağımsız değildir ve seçim yanlılığı giderilmemiştir.

---

## 0. Kısa cevap

1. **Stabil'in çekirdeği yalnızca destektir.** `domain_engines/05_stabil.txt` günlük teyitli pivot
   diplerinden tek bir günlük destek seviyesi, bir ATR tabanı (`support_floor`), bir yaşam döngüsü
   olay akışı ve ayrı bir trend bağlamı (haftalık / günlük / 4s) üretir. Kaynakta direnç, skor, alarm
   veya "birleşik sinyal" **yoktur**.
2. **Direnç sonradan, "tam zıttı" olarak yazıldı** ama yeni bir indikatör değil: aynı native desteğin
   fiyat ekseninde aynalanmış hâli (`O'=-O, H'=-L, L'=-H, C'=-C`). Seviye, teyit anı, taban/tavan,
   reklam (`rebase`) olayları ve dikey/yatay aday rejimleri birebir aynı matematikten gelir; yalnız
   yorum ("güvenli taraf") ters çevrilir. Replay'ler iki tarafın **temel temas tepkisinde benzer**
   olduğunu gösterdi (destek %41,3 / direnç %42,1 tepki-yönü-önce); bu yüzden katman grafiklere
   bağlandı. Ama simetri *her alt grupta* doğrulanmadı ve hiçbir işlem avantajı kanıtlanmadı.
3. **Ok sistemi üç ayrı sınıftır:** dolu yeşil `▲` (güçlü geri alım), içi boş altın `▲` (güçlü yukarı
   momentum), mercan `▼` (dikey destek üzerinde yukarı deneme = yapı uyarısı). Dirençte aynaları
   vardır (`▼` dolu = güçlü aşağı dönüş, `▼` içi boş = aşağı momentum, `▲` içi boş = yukarı deneme).
4. **En önemli iki bulgu:** (a) 4s grafiklerde direnç katmanı, sağlayıcı kaynaklı tek bir eksik
   saatlik kova yüzünden gerçek arşivde **hiç çizilmiyordu** (fail-closed kapı bütün katmanı
   düşürüyordu; 2026-11-08'de "son kesintisiz bloğa kırpma" politikasıyla çözüldü — §8.1);
   (b) ok gücü eşikleri **4s ATR** biriminde, oysa okları gerekçelendiren araştırma **günlük ATR**
   biriminde konuşuyor — bu yüzden "güçlü mum" sanılan okların çoğu günlük ölçekte zayıf.
5. Bu turda düzeltilen üç gerçek hata: **2025 yarım gün kayıtlarının eksikliği** (takvim/kapanış
   çelişkisi), **kapanmamış son 4s kovasının "kapandı" sayılması** ve **sağlayıcı boşluğunda bütün 4s
   katmanının kararması** (kırpma politikası). Ayrıntı §8.

---

## 1. Bu turda gerçekten yapılanlar

| Kontrol | Sonuç |
|---|---|
| Tam regresyon (`pytest -q`, Python 3.11.2) | **4135 passed, 43 skipped**, çıkış kodu 0 |
| `ruff check .` | All checks passed |
| Ok replay hattı gerçek arşivle çalıştırıldı | 2 sembol (ASTOR, AKBNK) → 39 olay, hata yok |
| **Taze örneklem koşusu (bu dosya için)** | **40 sembol, 1061 olay**, 1 dk 26 sn, 0 hata |
| Direnç grafiği gerçek arşivle sınandı | 1g kare **READY**; 4s kare **DATA_ERROR** (sebep §8.1; aynı gün kırpma politikasıyla **12/12 READY** oldu) |
| Değiştirilen dosyalar | `config.py` (2025 yarım günleri), `domain_engines/stabil/chart_bridge.py` (son kova + teşhis logu), iki test dosyası |

Ok eşiklerine, momentum/sweep kurallarına, dikey uyarı politikasına ve alarm üretimine **dokunulmadı**;
bunlar §10'daki replay planıyla, sonuçlar görülmeden önce tanımlanmış kohortlarla ele alınmalı.

---

## 2. Stabil'in native çalışma mantığı (destek)

### 2.1 İki bağımsız çıktı

| Bileşen | Dosya | Ürettiği |
|---|---|---|
| Trend bağlamı | `domain_engines/stabil/stabil_trend_engine.py` | Haftalık yapı/durum, günlük ham durum (`ADVANCE/PULLBACK/…`), 4s toparlanma kanıtı (`RECOVERY_CONFIRMED/FAILED/SELLING_WEAKENING/…`), pivot teyitleri, gap durumu |
| Günlük destek yaşam döngüsü | `domain_engines/stabil/stabil_support_lifecycle.py` | `DailySupportObservation` (seviye, taban, pivot kökeni/teyidi, ATR), `StabilSupportLifecycleSnapshot` (geçerlilik, dinamik, ilerleme, mesafe, sayaçlar, olaylar) |

Trend ile destek **ayrı** tutulur. "Fiyat destek üstünde" ≠ "yükseliş trendi" ≠ "alım sinyali". Bu
ayrım grafikte de korunur: destek stepline'ı native günlük seviyeden, renkler `ACTIVE/BREACHED`
geçerliliğinden gelir.

### 2.2 Seviye nasıl doğar?

* Günlük mumlarda `daily_pivot_len = 4` ile **iki taraflı teyitli** pivotlar bulunur. Pivotun oluştuğu
  bar (`origin`) ile kullanılabilir olduğu bar (`confirmed/available`) farklıdır; seviye **geriye
  dönük çizilmez** (look-ahead yasağı).
* Son iki teyitli tepe + son iki teyitli dip yapısının sıralı/uygun olması gerekir; güncel son teyitli
  dip = **destek seviyesi**.
* `support_floor = destek − 0,35 × ATR(köken)`. Bu bir tolerans tabanıdır, "kırılma" değildir.
* Aynı mumda seviye değişimi (stepline'ın dikey bağı) ayrı bir olaydır: `REBASED_HIGHER/LOWER`.

### 2.3 Geçerlilik ve olaylar

| Kapanış | Geçerlilik | Grafikteki renk |
|---|---|---|
| ≥ destek | `ACTIVE` | güvenli taraf (destekte yeşil, dirençte kırmızı) |
| destek > kapanış ≥ taban | `BREACHED` | ihlal rengi |
| kapanış < taban | `BELOW_FLOOR` | derin ihlal |

Olaylar: `TESTED` (günlük aralık çizgiyi kapsar), `HELD`, `BREACHED`, `FLOOR_BROKEN`, `RECLAIMED`
(önceki kapanış alttayken üstte kapanış), `LOST`, `REBASED_*`. **Native lifecycle "3. temasta kırılır"
gibi bir temas sayacı üretmez**; grafikteki `touch_count` ayrı, ATR yakınlığına dayanan bir davranış
katmanıdır ve native gerçek temasla eşitlenmemelidir.

### 2.4 "Dikey/yatay" aday rejimleri

`candidate_regime.py` yalnızca **aday** etiketler üretir ve `user_confirmed=False` taşır:
`STEPPING_UP`, `STEPPING_DOWN`, `BREACHED_FIXED_SUPPORT`, `NEWLY_FLATTENED_AFTER_RISE`,
`HORIZONTAL_AFTER_DROP`, `HORIZONTAL_BASE`, `LONG_HORIZONTAL`.

* `STEPPING_UP/DOWN`: reklam sonrası native pivot aralığı (8 günlük bar) boyunca süren basamak.
* `NEWLY_FLATTENED_AFTER_RISE`: 9–23 bar arası "yeni yataylaşmış" evre.
* `LONG_HORIZONTAL`: ≥ 24 bar.
* **`SupportProgression.REBASED_HIGHER` "şu anda yükseliyor" demek değildir**; o seviyenin *bir zamanlar*
  yukarı basamakla kurulduğunu söyler ve seviye yaşadıkça etiketi taşır. Ok kurallarında bu ayrım
  önemli (§4.4).
* Stepline'ın dikey bağlantı çizgisi kullanıcının gözündeki "dikey rejim" ile birebir aynı kabul
  edilmedi; proxy daha geniş olabilir. Bu, metinlerde her yerde açıkça yazılıdır.

---

## 3. Direnç: neden "tam zıttı", nasıl üretiliyor

`domain_engines/stabil/resistance.py` (804 satır, tek başına, yan etkisiz):

1. **Girdi doğrulaması:** OHLC > 0, sonlu, `high ≥ max(open, close)`, `low ≤ min(open, close)`, zaman
   artan ve tekilsiz. Şüpheli seride seviye uydurulmaz, `DATA_ERROR` döner.
2. **Ayna:** `high' = -low`, `low' = -high`, `open'/close' = -open/-close`. Native destek motoru bu seride
   **değiştirilmeden** çalıştırılır. Yani direnç = "desteğin fiyat eksenindeki tersi".
3. **Geri eşleme:** `resistance_level = -support_level`, `resistance_ceiling = -support_floor`,
   olaylar `RESISTANCE_*`, ilerleme `REBASED_HIGHER↔REBASED_LOWER`. Fiyatlar pozitif gerçek fiyattır;
   grafikte `100.000 − fiyat` gibi bir koordinat kullanılmaz.
4. **Renk rolleri:** destekte güvenli taraf yeşil / ihlal kırmızı iken dirençte **ana çizgi kırmızı,
   çizgi üstü yeşil** (yani ters). Çizgi kesikli çizilir; desteğin yerini almaz.
5. **Davranış/ok katmanı** desteğin birebir aynası olarak, **gerçek fiyat koordinatında** yazılmıştır
   (negatif fiyat üretmeden): aynı eşikler, aynı 3 bar momentum tekrar kısıtı, ters yön.
6. **Kalite kapıları (`chart_bridge.py`):** günlük kaynak native olmalı, 1s bileşenleri kontrol
   edilmeli, BIST kapanış takvimiyle uyuşmalı, günlük bölünme (split) ölçeği doğrulanabilmeli.
   Doğrulanamazsa **yalnız direnç gizlenir**; destek katmanı, alarm ve kart değişmez.

### 3.1 Direnç neden kullanıma açıldı?

| Çalışma | Bulgu |
|---|---|
| 50 hisse direnç model testi (2026-11-06) | Temas sonrası tepki: destek %40,2 / direnç %41,7 (2026). Gerçek temasta güvenli kapanış destek %54,0 / direnç %53,2. Eşleştirilmiş 53 çift: **%45,3 / %45,3** (fark 0,0 puan; %95 GA −17,5…+16,7) |
| 174 hisse aynı-veri karşılaştırması (2026-11-06) | TEST tepkisi destek %41,3 / direnç %42,1; eşlenmiş 178 çiftte fark +1,1 puan (GA −9,2…+11,6) |
| Kırılma sonrası ilk yol | Fiyat eski çizgiye önce: destek %63,3 / direnç %69,4; çizgi ters taşınır: %16,1 / %12,5 |

Yorum: **temel davranış benzer**, bazı alt gruplarda (uzaklaşma yarışı, basamak/yataylaşma) ayrışıyor.
Bu "direnç desteğin aynasıdır" iddiasını destekler ama ispatlamaz; hiçbiri işlem avantajı değildir.
Kullanıcı onayıyla katman 2026-11-07'de yerel grafiklere bağlandı; **direnç kendi başına alarm
üretmez** ve 4s alarm kararını etkilemez.

---

## 4. Ok sistemi — bugünkü gerçek kurallar

Kod: `domain_engines/stabil/signals.py::evaluate_bar_behaviors` (destek) ve
`resistance.py::evaluate_resistance_bar_behaviors` (direnç aynası). Tüketen yüzeyler:
`grafik/tarama.py::_stabil_verisi` / `_stabil_direnc_verisi` → `grafik/render.py::_stabil_ciz` /
`_stabil_direnc_ciz`; metin tarafında `signals.describe_behavior_structure_short`,
`summary`/`/stabil` komutu ve 4s alarm servisi (`bot/stabil_service.py`).

### 4.1 Üç sınıf ve kesin koşullar (destek)

| Sınıf | Görsel | Koşullar (hepsi aynı kapalı mumda) |
|---|---|---|
| Güçlü geri alım `close_reclaim` | dolu yeşil `▲` | `fixed_support`, önceki kapanış çizgi altı & şimdiki üstü, **önceki ihlal derinliği ≤ 1,50 ATR**, gövde ≥ 0,32 ATR, kapanış pozisyonu ≥ 0,65, mesafe ≥ 0,05 ATR, hacim ≥ 1,0× **veya** gövde ≥ 0,45 ATR (endekste 0,38) |
| Silkeleme dönüşü `intrabar_sweep_reclaim` | dolu yeşil `▲` | aynı sabit çizgi, fitil çizginin −1,20…−0,08 ATR altına sarkmış, kapanış ≥ 0,08 ATR üstte, gövde ≥ 0,35 ATR, kapanış poz ≥ 0,68, hacim ≥ 1,0× veya gövde ≥ 0,50 ATR |
| Güçlü yukarı momentum `long_base_breakout` / `upward_rebase_momentum` | **içi boş altın** `▲` | geri alım yok + zayıf geri alım yok, fiyat çizgi üstünde, gövde ≥ 0,35 ATR, kapanış poz ≥ 0,65, `touch_count < 3`, hacim ≥ 1,10× veya gövde ≥ 0,50 ATR, geçerlilik `ACTIVE`, **3 bar tekrar kısıtı**; ayrıca ya `unchanged_days ≥ 20` & mesafe 0,15–1,80 ATR, ya da (`STEPPING_UP` **veya** `progression = REBASED_HIGHER`) & mesafe 0,10–1,60 ATR |
| Dikey uyarı `▼` | mercan `▼` | dikey proxy açıkken yukarı deneme (geri alım, zayıf geri alım, momentum veya `touch_from_below`); `reclaim_kind`/`momentum_kind` **null'lanır** |

Dikey proxy: `regime ∈ {STEPPING_UP, STEPPING_DOWN}` **veya** `REBASED_HIGHER` & yaş ≤ 8 **veya**
seviye o mumda değişti (`fixed_support = False`).

### 4.2 ATR ve hacim nereden?

* `ATR14`: **hedef grafiğin** mumlarında nedensel Wilder (4s grafikte 4s ATR).
* Hacim oranı: olay hacmi / **önceki 20 pozitif** barın ortalaması (en az 5 pozitif bar; olay hacmi 0
  ise bilinmiyor).
* 4s kovaları 09:30 / 13:30 / 17:30 etiketlidir; **son kova 17:30→18:00, yani 30 dakikadır**. Bu kova
  ATR ve hacim oranını çağdaşlarıyla karşılaştırılamaz yapar; `18:00` kapanışlı oklar bu yüzden ayrı
  okunmalı (raporda ölçülmüş bir karıştırıcıdır).

### 4.3 Alım/satım yüzeyleri

* **4s alarm yalnızca geri alım** türlerinde üretilir (`reclaim_kind`), 6 bar cooldown + mum başına tek
  bildirim. Momentum `▲` ve `▼` **alarm üretmez**; yalnız grafik/kart bilgisidir.
* Kart `Stabil yapı:` satırı `dikey destek · yukarı deneme` önceliğini taşır; böylece dikey deneme
  yanlışlıkla "güçlü geri alım" diye pazarlanmaz.
* `/stabil` komutu ayrı bir kova sınıflandırıcısı kullanır (`kart_yorum`/`summary`): `guclu_cikis`,
  `saglam_zemin`, `sig_sarkma`, `zayif_dusus`, `notr`.

### 4.4 Ok mantığındaki üç ince (ve riskli) nokta

1. **Birim kayması:** bütün "güçlü mum" eşikleri **4s ATR** ile ölçülüyor; oysa okları ve kart
   etiketlerini gerekçelendiren 100-hisse araştırması **günlük ATR** ile ölçtü
   ("gövde ≥ 0,5 **günlük** ATR"). 40 sembollük taze örnekte `ATR4s / ATR1g` medyanı **0,52**; yani
   0,35 × 4s ATR ≈ 0,18 × günlük ATR. Sonuç: kullanıcının "güçlü görünmeyen mumda ok çıkıyor"
   gözlemi **sayısal olarak doğru** (§7.3).
2. **`upward_rebase_momentum` adı yanıltıcı:** koşul, çizginin *şu anda* basamak yapması değil, o
   seviyenin geçmişte yukarı basamakla kurulmuş olması. Ölçülen 10 olayın **10'u da**
   `NEWLY_FLATTENED_AFTER_RISE` rejiminde, yani çizgi düzleştikten sonra çıktı. Aynı olaylar
   `/stabil` komutunda **hiç görünmüyor**: komuttaki eşdeğer dal `regime == STEPPING_UP` istiyor, oysa
   o rejimde `vertical` bayrağı zaten `True` olduğu için dal **ulaşılamaz** (ölü kod). Grafikte ok var,
   komutta yok — aynı kavramın iki farklı tanımı.
3. **Dikey filtre neyi atıyor?** 174 sembollük kayıtta `▲` adaylarının 838'i `▼`'ye çevrildi. Bu
   bastırılan küme, kalan `▲`'lerden **daha iyi** davrandı: +1 ATR önce %53,4 (kalan `▲` %49,7),
   −1 ATR önce %39,4 (%44,1). Yani mevcut dikey kuralı, incelenen örneklemde *daha kötü* okları
   seçmiyor. Bu, kullanıcının dikey/yatay sezgisini çürütmez (proxy geniş olabilir) ama "dikeyde ok
   basma" politikasının **replay ile yeniden sınanması gerektiğini** gösterir.

---

## 5. Replay sistemi — hangi dosya, hangi iş

| Hat | Dosya | Ne yapar |
|---|---|---|
| Arşiv | `research/arsiv.py` | CSV.gz okur, 1s → 2s/4s seans hizalı çerçeve, manifest (indirme zamanı/süresi) |
| Stabil native geçmiş | `domain_engines/stabil/runtime.py::build_single_pass_history` | Sembol başına **tek geçişte** tüm günlük/haftalık/4s snapshot'ları (O(N²) prefix tekrarı yok) |
| Stabil araştırma tabanı | `research/stabil_replay.py` | Her kapanmış 4s checkpoint'te nedensel projeksiyon, first-seen olay takibi, 1/4/8/10/12/16 × 4s ufuklarda MFE/MAE/kalış/ilk-vuruş, sağ sansür |
| **Ok/uyarı replay'i** | `research/stabil_arrow_context_replay.py` | Kapalı 4s mumda `evaluate_bar_behaviors` → olay sınıfı (`UP_ARROW`, `VERTICAL_*`) + olay anında bilinen hacim/OB/FVG/MS/Stabil bağlamı; 4/8/16 bar sonuç durumları |
| Ok raporu / örnekler / kalite | `research/stabil_arrow_report.py`, `stabil_arrow_examples.py`, `stabil_arrow_quality.py` | Okunabilir tablolar, seçilmiş olay+8 bar görselleri, ham OHLCV/zaman kalite taraması |
| Direnç replay'i | `research/stabil_resistance_replay.py` | Direnç olaylarını aynı nedensel kurallarla ölçer |
| Destek↔direnç karşılaştırma | `research/stabil_support_resistance_compare.py` | Aynı sembol/veri/ufukla iki tarafın eşleştirilmiş karşılaştırması |
| 48 soru cevaplayıcı | `research/stabil_bhv48.py` | Var olan checkpoint çerçevelerinden aggregate tablolar (motoru tekrar çalıştırmaz) |
| Geri alım derin analizi | `research/stabil_reclaim_deep.py` | Sarkma derinliği × çıkış mumu gücü kırılımı |
| Canlı evren testi | `research/stabil_live_systematic.py` | `config.BIST_50` içindeki non-macro sembollerde ayrı 4s sistematik |

### 5.1 Ok replay'inin adım adım mantığı

1. Sembol listesi: yerel arşivde 1s verisi olan, `sembol_turu == "hisse"` ve havuz dışı olmayanlar
   (deterministik sıralama, `--limit`).
2. Her sembol için `build_single_pass_history` bir kez çalışır (native motor).
3. **Yakalama sınırı:** manifestteki indirme bitişinden kayıtlı süre + 1 sn çıkarılır; planlanan kapanışı
   bu sınırdan sonra olan mumlar dışlanır (indirme anında yarım kalmış mumların sızmasını önler).
4. Her kapalı 4s mumda: hedef çerçeve `prepare_causal_ohlcv` ile temizlenir, günlük destek o kapanışa
   göre projekte edilir, `evaluate_bar_behaviors` çağrılır.
5. Olay sınıfı: `reclaim_kind`/`momentum_kind` doluysa `UP_ARROW`; dikey proxy açıksa ve bir deneme
   varsa `VERTICAL_OTHER_WARNING`; dikey proxy'nin bastırdığı eski aday ise
   `VERTICAL_SUPPRESSED_PREVIOUS_UP_CANDIDATE`.
6. **Ölçüm:** giriş = sinyal kapanışı; ATR = olay anındaki 4s Wilder ATR14 (dondurulmuş); ufuklar
   4/8/16 **mevcut** bar; MFE/MAE/kapanış ATR biriminde; `±1 ATR` yarışında aynı barda ikisi de
   görülürse `AMBIGUOUS_SAME_BAR`; ufuk dolmamışsa `RIGHT_CENSORED`; bozuk OHLCV / %30 üzeri kapanış
   sıçraması varsa `BAD_HISTORY`.
7. Zayıf tepki (ön-kayıtlı): 8 tam barın en yükseği `0,5 ATR`'ye ulaşamadıysa `weak_mfe_8`.
8. Yanına **olay anında bilinen** bağlam yazılır: hacim oranı (önceki 20 pozitif bar), öndeki en yakın
   aktif bearish OB ve seçili FVG'nin kalan bölgesi/mesafesi, dış piyasa yapısı (BOS/CHoCH durumu),
   günlük ham Stabil durumu, 4s toparlanma kanıtı.
9. Sembol başına atomik checkpoint (varsayılan `~/formation-stabil-arrow-replay`) → kesintiden sonra
   devam edilebilir; kaynak/kod hash'i değişirse yeniden hesaplanır.
10. Toplama: `events.csv.gz` + `summary.json` (kaynak SHA256, seçim, hata listesi, tanımlar).

Aynı sembolde olaylar örtüşebilir; "bağımsız" alt küme için hisse başına en az 8 bar ayrılmış ilk ok
ayrıca raporlanır. Bu, hisseler arası ortak piyasa günlerini gidermez.

---

## 6. Mevcut ölçüm sonuçları (kayıtlı çalışmalar)

### 6.1 Ok replay'i — 174 hisse, 2026-11-05

| Ölçü | Değer |
|---|---|
| İşlenen sembol | **174/174**, hata 0 |
| Toplam olay | 4.775 → `UP_ARROW` **584**, `VERTICAL_OTHER_WARNING` 3.353, bastırılmış eski aday 838 |
| `▲` 8-bar durumu | `VALID` **555**, `BAD_HISTORY` 15, `RIGHT_CENSORED` 14 |
| Zayıf tepki (MFE < 0,5 ATR) | **138 / 555 = %24,9** (4 bar: %34,6; 16 bar: %18,6) |
| 8 bar ilk ±1 ATR | UP_FIRST 276 (%49,7), DOWN_FIRST 245 (%44,1), aynı-bar 9, hiçbiri 25 |
| Medyan 8-bar kapanış | **−0,10 ATR** |
| Hacim düşük vs yüksek | %25,3 vs %24,6; fark +0,6 puan (bootstrap −8,8…+10,3) → anlamlı ayrışma yok |
| Öndeki yakın bearish OB | %25,1 (uzak %25,9); yakın FVG %30,1 (yok %24,2) — ham farklar, ayarlanmadı |
| Dış MS bearish / bullish | %26,4 / %24,3 |

**Ok türüne göre (555 geçerli olay):**

| Tür | n | Zayıf % | Medyan 8-bar | +1 ATR önce | −1 ATR önce |
|---|---:|---:|---:|---:|---:|
| `close_reclaim` | 255 | 23,1 | −0,21 | 46,3 | 47,5 |
| `intrabar_sweep_reclaim` | 162 | 29,6 | −0,16 | 51,2 | 43,8 |
| `long_base_breakout` | 63 | 28,6 | −0,04 | 49,2 | 42,9 |
| `upward_rebase_momentum` | 75 | 17,3 | **+0,20** | 58,7 | 34,7 |

**Aday rejime göre:** `BREACHED_FIXED_SUPPORT` %17,7 zayıf (med +0,00) · `HORIZONTAL_AFTER_DROP`
%29,6 (−0,30) · `LONG_HORIZONTAL` %24,5 (+0,10) · `NEWLY_FLATTENED_AFTER_RISE` %23,5 (−0,27) ·
`HORIZONTAL_BASE` %40,0 (n=10).

**4s Stabil bağlamı:** `H4_RECOVERY_FAILED` %10,9 zayıf, +1 ATR %63,0 (n=46) · `H4_SELLING_WEAKENING`
%26,8, med −0,39 (n=149) · `H4_BUYERS_EMERGING` %26,4 (n=314).

Bu tabloların hiçbiri nedensellik veya filtre seçimi için yeterli değil: gruplar farklı seçimlerdir,
olaylar örtüşür, OB/FVG/MS "olay anında bilinen" ama ayarlanmamış eş-değişkenlerdir.

### 6.2 Destek çekirdeği — 100 hisse / 48 soru (2026-11-01)

Manifest: 100 sembol, 107.441 kapanmış 4s checkpoint, 10.417 ilk-görülen destek olayı, 642 satır;
kararlar: 10 ayrı-doğrulama, 17 net-fark-yok, 19 betimsel, 2 yetersiz örnek. Öne çıkan betimsel
sonuçlar (düz Türkçe özet dosyası: [100 hisse sentezi](STABIL_100_HISSE_ANALIZ_SENTEZI.md)):

* Yatay çizgi uzun süre korunmuşsa kırılma daha az, tepki daha istikrarlı; **sert yükseliş sonrası ilk
  düzleşme** en riskli evre.
* 2. bağımsız temas en temiz tepki; 3–4. temasta yorulma ve kırılma oranı belirgin artıyor.
* Çizgi altına **bir miktar** sarkıp (`0,5–1,2 ATR`) **güçlü gövdeli** mumla geri alım en iyi kurulum
  (+0,38/+0,41 ATR, üstte kalma %85,9); aynı yerden cılız mumla çıkış tuzak (−0,34 ATR).
* "Üste atınca retest bekleyeyim" kuralı ortalamayı düşürüyor; en güçlü gidenler retest vermiyor.

**Bu sonuçlar günlük ATR ve günlük destek olaylarıyla ölçüldü.** Grafikteki 4s okları bu eşiklerin
birebir uygulaması değildir (§4.4/1).

### 6.3 Geri alım derin analizi — 1.150 olay (16 soru)

Makul sarkma + güçlü gövde + tepeye yakın kapanış + hacim: hisse başına 1,5 yılda 2,7–4,0 ok, ertesi
mum üstte kalma %88–90, 16×4s eşit-hisse ortalaması +0,22…+0,32 ATR. Buna karşılık **bütün** geri
alımlar (filtresiz) hisse başına 11,5 kez çıkıyor ve yarısı cılız. Kart etiketleri de bu kırılıma
göre kalibre edildi.

### 6.4 Canlı evren sistematik (ayrı çalışma)

50/53 non-macro sembol, 284 sinyal, 75,9 hafta; ertesi 4s bar tutunma %91,5, 8×4s medyan +0,262 ATR.
Bu evren 100-sembol/48-soru çalışmasına eklenmez; farklı seçim ve dönemdir.

### 6.5 Sayım uyuşmazlıkları (bilinçle korunur)

Eski konuşma kayıtları 107.446 checkpoint / 390.905–386.017 gözlem / 2.034–4.074 satır derken mevcut
manifest 107.441 / 10.417 olay / 642 satır diyor. Bunlar farklı sürüm/çıktılardır; **tek koşu gibi
toplanmamalı**. Tam native checkpoint paketi (≈80 MB) ve özgün 27-soru çıktıları depoda yok; manifest
kaynak SHA256 ve kesin veri kesimi taşımıyor → birebir yeniden üretilebilirlik iddiası yok.

---

## 7. Bu oturumda üretilen taze kanıt (40 sembol)

**Amaç:** mevcut kayıtların mantığını *aynı kodla, aynı arşivde* yeniden görmek ve ok kalitesi
sorusunu sayıya dökmek. Komut:
`python -m research.stabil_arrow_context_replay --limit 40 --workers 4 --cache /tmp/arrow_cache --output /tmp/arrow_out40`
(86 sn, 0 hata, 1061 olay).

### 7.1 Sınıf dağılımı ve kalite

| Ölçü | Değer |
|---|---|
| Olay | 1061 → `▲` **110**, diğer dikey uyarı 751, bastırılmış eski aday 200 |
| `▲` geçerli 8 bar | 105 |
| Zayıf tepki (MFE < 0,5 ATR) | 24 → **%22,9** (174-sembol kaydı %24,9 ile uyumlu) |
| İlk ±1 ATR | DOWN_FIRST %42,7, UP_FIRST ~%52 |
| Medyan 8-bar kapanış | **−0,27 ATR** |

Tür dağılımı: `close_reclaim` 60, `intrabar_sweep_reclaim` 32, `upward_rebase_momentum` 10,
`long_base_breakout` 8.

### 7.2 Ok gücü hangi birimde ölçülüyor?

| Ölçü | Değer |
|---|---|
| `ATR4s / ATR1g` (olay anı) | medyan **0,52** (p10 0,42 · p90 0,61) |
| Gövdesi < 0,20 günlük ATR olan ok | %1,8 |
| Gövdesi < 0,35 günlük ATR olan ok | **%36,4** |
| Gövdesi < 0,50 günlük ATR olan ok | **%64,5** |

Yani okların üçte ikisi, araştırmanın "güçlü mum" tanımının (≥0,5 günlük ATR) altında. Kullanıcının
gözlemi burada doğrulanıyor: eşikler **doğru sayıda değil, yanlış birimde**.

### 7.3 Betimleyici kırılımlar (n küçük — yön göstergesi, kural değil)

| Kırılım | n | Zayıf % | Medyan 8-bar | UP_FIRST | DOWN_FIRST |
|---|---:|---:|---:|---:|---:|
| `close_reclaim` | 57 | 21,1 | −0,30 | 45,6 | 49,1 |
| `intrabar_sweep_reclaim` | 30 | 20,0 | 0,00 | **63,3** | 33,3 |
| `long_base_breakout` | 8 | 50,0 | −0,68 | 37,5 | 50,0 |
| `upward_rebase_momentum` | 10 | 20,0 | −0,75 | 50,0 | 50,0 |
| Gövde ≥ 0,5 günlük ATR | 38 | 34,2 | **+0,34** | 50,0 | 47,4 |
| Gövde 0,25–0,5 günlük ATR | 57 | 17,5 | −0,58 | 50,9 | 42,1 |
| Hacim ≥ 1,2× | 57 | 24,6 | **+0,17** | **59,6** | 35,1 |
| Hacim 0,8–1,2× | 30 | 20,0 | −0,78 | 36,7 | 56,7 |
| Mesafe 0,3–0,8 ATR | 27 | **3,7** | **+0,48** | **59,3** | 33,3 |
| Mesafe 0,8–1,8 ATR | 51 | 31,4 | −0,70 | 49,0 | 47,1 |

**Dikkat:** 174-sembol kaydında `upward_rebase_momentum` medyanı **+0,20** iken bu 10 olaylık alt
örnekte **−0,75**. İkisi de aynı kodun çıktısı; fark örneklem gürültüsüdür ve tek başına hiçbir
kırılımdan kural çıkarılamayacağını gösterir. 40 sembolde bu türün **10/10'u**
`NEWLY_FLATTENED_AFTER_RISE` rejiminde çıktı (§4.4/2).

---

## 8. Tespit edilen sorunlar

### 8.1 ÇÖZÜLDÜ (2026-11-08, politika C) — 4s direnç katmanı boşluk yüzünden tamamen kapanıyordu

`chart_bridge._intraday_checked` her 4s kovasını kendi 1s bileşenleriyle doğrular; **tek bir eksik
kovada bütün katmanı** `DATA_ERROR` yapıyordu. Gerçek arşivde iki yapısal sağlayıcı boşluğu var:

* **2026-04-20 09:30 ve 10:30** 1s barları tüm sembollerde eksik (o gün 09:30 4s kovası yarım),
* 2025-10-27…2025-11-06 arasında 7 gün **17:30 barı** eksik (günün son 4s kovası yarım; bu barlar
  arşivde genel olarak var — 353/365 gün —, yalnız o haftada yok).

Ölçüm (öncesi): 12/12 sembol 4s için `missing_or_invalid_target_bucket` / `incomplete_hourly_bucket`;
1g kare `READY`. Yani **geçmiş grafiklerde direnç çizgisi ve direnç okları hiç görünmüyordu**.

**Karar (kullanıcı "sence" dedi, uygulanan: C — son kesintisiz bloğa kırpma).** Gerekçe:

* 4s katmanındaki seviye **günlük** geçmişten üretilip bar kapanışlarına projekte ediliyor; 4s
  çerçeve yalnız çizim ızgarası. Dolayısıyla baştaki kovaları atmak seviye hesabını bozmuyor,
  yalnız çizgi daha geç başlıyor — "sessizce yanlış veri çizmek" ile karıştırılmaz.
* A (aynen bırak) özelliği pratikte ölü bırakıyordu; B (son N bar) doğrulanmamış barları çizer;
  D (kova maskesi) `bar_index` hizasını ve davranış zincirini boşluk üzerinden bağlar.
* Politika **doldurmaz, uydurmaz**: yalnız son doğrulanamayan kovanın öncesi bırakılır, kalan blok
  kesintisiz ve toplam-tutarlı olarak doğrulanır; kırpma `WARNING` ile (kova, neden, atılan/kalan)
  loglanır. Ayrıca sondaki doğrulanamayan kova (gecikme/eksik bileşen/uyuşmayan toplam) yalnız o
  barı düşürür — eskiden olduğu gibi bütün katmanı kapatmaz. Kırpma sonrası **2'den az** kova
  kalırsa katman açılmaz: yeni neden `insufficient_continuous_buckets`.

Ölçüm (sonrası, gerçek arşiv): **12/12 sembol `READY`**. Tam arşivde kırpma noktası
**2026-04-20 09:30 (711 kova atıldı, 367 çizildi)**, 2025-12-01+ penceresinde 293 atıldı / 367 kaldı.
Canlı benzeri **son ~120 kova** penceresinde **hiç kırpma yok** (boşluk pencerenin dışında): canlı
tarama davranışı değişmedi, değişiklik yalnız boşluğu kapsayan uzun pencereleri etkiliyor.
Bedel: çizgi görünür pencerede 2026-04-20'den itibaren başlar; bunu kullanıcı gözle görecek.
Maliyet: tam arşiv 4s ≈ 1,0 s/sembol, son 120 kova ≈ 0,2 s/sembol (kova doğrulaması zaten vardı;
kırpma noktası aranırken doğrulama sondan geriye yürüyüp ilk sorunda durur).

### 8.2 DÜZELTİLDİ — 2025 yarım günleri takvimden eksikti (orta-yüksek etki)

`config.BIST_YARIM_GUNLER` yalnız 2026/2027 arefelerini taşıyordu. 2025-06-05 ve 2025-10-28 XIST
takviminde **erken kapanış**; config bilmediği için `seans_sonu_saati` o günlerde **18:00** dönüyordu:

* 1s/4s kova kapanışları ve günlük mumun tamamlanma anı yanlış,
* `chart_bridge._session` "takvim erken kapanış diyor, bizim helper demiyor" diyerek
  `calendar_close_mismatch` ile **bütün direnç katmanını** kapatıyordu (arşivdeki her 4s grafik 2025'i
  kapsadığı için kalıcı etki).

Düzeltme: iki tarih `time(13, 0)` ile eklendi (depodaki 2026 arefe sözleşmesiyle aynı; XIST bu iki gün
için 12:30 der — en fazla 30 dk, yalnız geçmiş kapanış anını etkiler). Ayrıca **XIST'in erken kapanış
bildirdiği her günün config'te bulunmasını zorlayan regresyon testi** eklendi, böylece yeni yıl
eklenmediğinde test kırmızı olur.

### 8.3 DÜZELTİLDİ — kapanmamış son 4s kovası "kapandı" sayılıyordu

`as_of_close` verilmediğinde kesim, son barın **planlanmış** kapanışından türetiliyordu; böylece son
kovanın eksik bileşenleri (arşiv seans ortasında alınmış / sağlayıcı son saati henüz göndermemiş)
"eksik kova" hatasına dönüşüp katmanı düşürüyordu. Artık **penceresi son gözlenen saatlik barın
kapanışından sonra biten kova** sertifikalandırılmıyor: atlanıyor (doldurulmuyor), log'a yazılıyor;
iç boşluklar artık 8.1'deki kırpma politikasıyla ele alınıyor. Kova uyuşmazlığında hangi günün eksik
olduğu loglanıyor (önceden yalnız "gösterilemedi" vardı, teşhis yoktu).

### 8.4 AÇIK — `/stabil` komutu ile grafik oku aynı kavramı farklı tanımlıyor (orta etki)

§4.4/2: `summary`/`/stabil` içindeki "yükselen kademeden güçlü ivme" dalı `regime == STEPPING_UP`
istiyor; o rejimde `vertical` zaten `True` olduğu için **ulaşılamaz**. Grafikte içi boş `▲` çıkan
`upward_rebase_momentum` olayları komutta hiç görünmüyor. Düzeltme, iki yüzeyin *aynı* koşulu
kullanmasıdır; ama bu komut çıktısını değiştireceği (ve ok tarafı bu turda dondurulduğu) için
kullanıcı kararına bırakıldı. Ölçülen etki: 110 okun 10'u, 555 okun 75'i.

### 8.5 AÇIK — ok gücü eşiklerinin birimi (yüksek etki, ok kalibrasyonu işi)

§7.2. Eşikler 4s ATR'de; araştırma günlük ATR'de. Bu, "anlamsız ok" şikâyetinin en olası mekanik
açıklaması. Değişiklik, replay sonuçları görülmeden yapılmamalı (§10).

### 8.6 AÇIK — dikey filtrenin seçiciliği kanıtlanmadı (orta etki)

Bastırılan 838 aday (803 geçerli) kalan `▲`'lerden daha iyi davrandı (§4.4/3). Proxy'nin genişliği
bilinen bir sınır; politika replay ile yeniden sınanmalı.

### 8.7 AÇIK — 4s'in son kovası 30 dakika (bilinen karıştırıcı)

17:30→18:00 kovası ATR ve hacim oranını bozar; 18:00 kapanışlı oklar ayrı kohort olarak okunmalı.

### 8.8 AÇIK — replay yeniden üretilebilirliği depoda değil (düşük-orta etki)

Sembol checkpoint'leri `~/formation-stabil-arrow-replay` altında (depo dışı). 2026-11-05 koşusunun
`events.csv.gz`'si depoda yok; yalnız özet/tablolar var. Aynı 174-sembol koşusunu tekrar üretmek
mümkün ama saatler sürer ve arşiv o günden beri değişmiş olabilir. Bu yüzden bu dosyadaki taze kanıt
40 sembolle sınırlıdır.

### 8.9 AÇIK — direnç alarm üretmiyor (tasarım)

Direnç katmanı yalnız görseldir; mevcut 4s geri alım alarmı yalnız `reclaim_kind` ile tetiklenir.
Beklenen davranış, ama "dirençte de alarm gelsin" istenirse ayrı karar + replay gerekir.

---

## 9. Kullanıcının kendi anlatımının kayıtlı olduğu dosyalar

| Dosya | İçerik |
|---|---|
| [`domain_engines/05_stabil.txt`](../../domain_engines/05_stabil.txt) | Kullanıcının verdiği özgün Python TXT (SHA256 `649896d2…3e6a5e`, 75.710 bayt) — matematiğin tek kaynağı |
| [`STABIL_DAVRANIS_MODELI.md`](STABIL_DAVRANIS_MODELI.md) | **Ana model dosyası:** "dikey" düzeltmesi, yükseliş döngüsü, kırılma sonrası iki yol, "yatay dönmesi Stabil onayı yeter", bilinmeyen kısımlar |
| [`STABIL_BEKLEYEN_ARASTIRMA_NOTLARI_2026_11_06.md`](STABIL_BEKLEYEN_ARASTIRMA_NOTLARI_2026_11_06.md) | Güçlü mum beklenen yukarı oklar, **BOS aşağı** hipotezi, küçük direnç görseli; "şimdi yapma, unutma" notları |
| [`STABIL_DESTEK_SONRASI_DAVRANIS_SORU_PLANI_2026-11-07.md`](STABIL_DESTEK_SONRASI_DAVRANIS_SORU_PLANI_2026-11-07.md) | Konuşarak netleştirilecek 5 karar (u/d sonucu tanımı, rejim tabakaları, gerçek temas vs yakınlık, test sayımı) |
| [`STABIL_100_HISSE_ANALIZ_SENTEZI.md`](STABIL_100_HISSE_ANALIZ_SENTEZI.md) · [`STABIL_GERI_ALIM_VE_KART_ANALIZI.md`](STABIL_GERI_ALIM_VE_KART_ANALIZI.md) | Kullanıcının cümlelerinin ölçümle eşleştirildiği düz Türkçe özetler |
| [`STABIL_REHBERI.md`](STABIL_REHBERI.md) · [`STABIL_CALISMA_GECMISI.md`](STABIL_CALISMA_GECMISI.md) | Belge haritası, tarihli çalışma kayıtları, kanıt sınırları |

---

## 10. Ok sistemini düzenlemek için önerilen sıra (henüz uygulanmadı)

Ön-kayıt kuralı: **kohortlar ve ölçüler sonuçlar görülmeden önce yazılır**; aynı veride deneme
çoğaldıkça yanlış pozitif riski artar.

1. **Temel çizgi:** mevcut `▲` seti ve `▼`'ye çevrilen adaylar, 174 sembol (veya en az 100) üzerinde
   aynı kod/hash ile yeniden üretilir; `events.csv.gz` **depoya** alınır (yeniden üretilebilirlik).
2. **Birim düzeltmesi testi:** "güçlü mum" eşiği 4s ATR yerine *olay anındaki günlük ATR* ile
   tanımlanır (0,35 / 0,5 / 0,7 günlük ATR kohortları). Aynı olay kümesi üzerinde zayıf-tepki oranı,
   UP_FIRST/DOWN_FIRST, medyan 8/16 bar kapanışı karşılaştırılır. Ok sayısındaki düşüş ayrıca raporlanır.
3. **Dikey filtre testi:** `▼`'ye çevrilen adaylar ile kalan `▲`'ler eşleştirilmiş (hisse, çeyrek, seans,
   mesafe, önceki hareket) alt kümede karşılaştırılır; proxy genişliği (8 bar) 0/4/8/12 bar duyarlılığı
   ile sınanır. Amaç: uyarının gerçekten kötü sonucu ayırıp ayırmadığı.
4. **BOS/CHoCH bağlamı:** kullanıcının "BOS aşağı iken ok çıkıyorsa fiyat düşüyor" hipotezi, olay
   anında **bilinen** dış yapı etiketiyle (bearish / bullish / geçiş / bilinmiyor) tabakalanır; bilinmeyen
   ayrı tutulur, tek bir mumla hüküm verilmez.
5. **Momentum türünün ayrılması:** `long_base_breakout` ve `upward_rebase_momentum` ayrı kohort;
   "seviye geçmişte basamak yapmış" ile "çizgi şu anda yükseliyor" ayrımı ölçülür.
6. **Karar:** yalnız (2)–(5) birlikte, ön-kayıtlı eşikle ve yeterli n'de tutarlıysa canlı kural değişir;
   aksi hâlde oklar bilgi olarak kalır, alarm üretmez.

Bu sıra uygulanana kadar §8.5/8.6 için kod değişikliği yapılmaması önerilir; aksi hâlde "hangi
değişikliğin işe yaradığı" ölçülemez.

---

## 11. Sınırlar ve yanlış okuma riskleri

* Bütün oranlar betimseldir; eşleştirme, çoklu karşılaştırma düzeltmesi ve ortak piyasa günü etkisi
  giderilmemiştir. Aynı hisse/gün içindeki olaylar bağımsız değildir.
* 174/100/50 sembollük çalışmalar aynı arşivi ve kısmen aynı sembolleri kullanır; biri diğerinin kör
  doğrulaması değildir. 2026 verisi önceki sonuçlar görüldükten sonra incelendi.
* "Dikey/yatay" hâlâ **aday proxy**'dir; kullanıcının grafikteki gözüyle birebir eşleşmesi
  doğrulanmadı. Native teyide keyfî 2/3/5 bar bekleme eklenmedi ve eklenmemelidir.
* Direnç katmanının grafikte görünmesi kârlılık, alarm veya işlem sinyali değildir; alarm üretmez.
* `▲`/`▼` işaretleri kesin düşüş/yükseliş tahmini değildir. `▲` setinin kendisi, ölçülen örneklemde
  yazı-tura düzeyindedir (UP_FIRST %49,7 / DOWN_FIRST %44,1).
* Bu dosya, §8.4–8.9 kapatılmadan "direnç canlıda doğrulandı" veya "oklar kalibre edildi"
  diye okunmamalıdır.
