# FAZ 3 — Backtest / Historical Analytics: Envanter, Çıktı Tasarımı ve V1 Kapsamı

**Durum:** ÖNERİ / TASARIM — bu turda KOD YOK.
**Dayanak:** `7a88224` (Faz 2.6 mirror + P2.6 final audit) üzerindeki repository incelemesi.
**Kural hatırlatması:** Backtest hiçbir şeyi değiştirmez; scoring/threshold/matematik/ML yok.
Salt-okunur analiz + rapor.

---

## 0) Tek cümlelik cevap

Elimizdeki üç kalıcı veri kümesi — **Formation History** (`state/formation_history.py`),
**Karne defteri** (`karne.py`) ve bunları `stable_id` ile birleştiren **outcome link** (P2.5) +
**Supabase f2\_\* aynası** (P2.6) — *"kayıtlı gözlemlerin tarihi analizi"* (historical analytics)
için **yeterli**; buna karşılık **gerçek bir replay-backtest için yeterli DEĞİL**, çünkü sistemde
tüm geçmişi yeniden üretecek derinlikte OHLCV yok (1H cache 360 bar ≈ 40 iş günü, `DEQUE_MAXLEN`,
`config.py:295`). V1 bunu "Backtest" değil **"taranmış formasyonların kanıtlanmış sonuçlarının
raporu"** olarak konumlandırmalıdır. Bu konumlandırma, kullanıcının "sadece geçmiş veriyi analiz
edip raporla" hedefiyle birebir örtüşür.

---

## 1) ENVANTER — Güvenilir şekilde ne var, nerede, hangi sınırlarla?

### 1.1 Formation History — yerel defter (`bot_data/formation_history/{STOCK}_{TF}.json`)

Her `(stock, tf)` başına kayıt defteri; kayıt başına (`stable_id` anahtarlı):

| Alan | İçerik | Analiz değeri |
|---|---|---|
| `dogum.alanlar` | 32 IDENTITY alanı (`formation_schema.py`): `pattern_type`, `family`, `classic_dir`, `specialized_variant`, `start/apex bar`, pivot koordinatları (hb/hp/lb/lp), `upper_slope`, `lower_slope`, `start_width`, `geometry_atr`, **`raw_quality` (doğum anı)**, pole bloğu (`has_pole`…`pole_quality`) | "hangi formasyon, nasıl doğdu" |
| `dogum.bar_time` | MUTLAK bar zamanı (TEXT) | zaman analizi / hizalama |
| `snapshotlar[]` | `{tur, bar_time, stable_id, state, bar, alanlar}`; tur ∈ {`geometri` (18 STATE), `kirilim` (20 BREAKOUT), `retest` (STATE), `terminal`} | kalite bileşenlerinin EVRİMİ + kırılım anının dondurulmuş kanıtı |
| `olaylar[]` | `{type, name, direction, quality, price, bar, time, state, stable_id}` (lifecycle `_emit`, `patterns/lifecycle.py:999`) — NEW_PATTERN / DEFINED / MATURE / PREP / BREAK_CANDIDATE / COUNTER_BREAK / BREAK_CONFIRMED / RETEST_OK / COMPLETED / TIMEOUT / BREAK_FAILED / WEAK / INVALID | tam yaşam döngüsü zaman çizelgesi |
| `durum` + `terminal_state` + `terminal_zamani` | `acik→kirilim→retest→terminal` (monotonik) | huni/funnel sayımı |
| `sonuc` | `{durum, outcome, deneme, kaynak}` — `sinyal_sonucu()` çıktısının KİLİTLİ kopyası (`outcome_link.bagla` → `sonuc_bagla`; retention bunu ASLA silmez) | hedef/stop/nötr + MFE/MAE + son_pct + hedef_bar/stop_bar, kaynaktan okunabilir |

**Sınırlar (raporda dillendirilecek):**
- Retention: `MAX_KAYIT=30` / slot, `MAX_OLAY=200`, `MAX_SNAPSHOT=40` kayıt başına. Sonuçsuz
  terminal kayıtlar ÖNCE silinir; `sonuc` bağlı kayıt korunur (`_silme_onceligi`).
- Snapshot/olay **yalnız anlamlı geçişlerde** yazılır (per-bar dump yok) → "her bar" analizi imkânsız,
  geçiş anı analizi tam.
- Bar indeksleri pencere-relatif; **süre hesapları `bar_time` farkından** yapılmalı, indeks farkından değil.
- Defter yalnız bot ayakta iken dolar (uptime bias'ı).

### 1.2 Karne defteri (`bot_data/karne_defteri.json`, yedek: `bot_store` → `state:karne_defteri`)

| tip | Alanlar | Not |
|---|---|---|
| `formasyon` | stock, tf, pattern, state, **quality**, bar_time, hafta, stable_id | yalnız TANIMLANDI / SIKISMA_GUCLENIYOR / KIRILIM_HAZIRLIGI anlarında; `KARNE_FORMASYON_TTL_SAAT=48` ile hisse+tf+tip başına tekilleşir → **"kaç formasyon bulundu" sayımları alt sınırdır** |
| `kirilim` | + `dir`, `entry` (teyit barı kapanışı), `atr`, `quality` (teyit anı effective/frozen), `mtf_destek`, stable_id | **alarm eşiğinden BAĞIMSIZ kaydedilir** (`main.py:1909-1926` kayıt, eşiği yalnız bildirimi gate'ler) → eşik-altı popülasyon da ölçülebilir. ⚠️ `mtf_destek` fiilen hep `False` (main akışı parametreyi hiç True geçmiyor) → **V1'de analiz dışı** |
| `olay` | state (RETEST_BASARILI / FORMASYON_TAMAMLANDI / BASARISIZ_KIRILIM), bar_time, stable_id | ⚠️ `KIRILIM_TEYIT_ALAMADI` (TIMEOUT) Karne olayı YOK — timeout yalnız history olaylarında var |

Retention: `KARNE_SAKLAMA_GUN=120` gün (açılışta `buda()`, `main.py:2821`).

### 1.3 Outcome motoru (değiştirilmeden kullanılan çekirdek)

`karne.sinyal_sonucu()`: giriş = teyit barı kapanışı; ufuk `KARNE_HORIZON_BAR=10` bar;
hedef `+1.5 ATR` / stop `−1.0 ATR` ilk-dokunuş yarışı; aynı barda ikisi → stop (muhafazakâr).
Çıktı: `durum ∈ {hedef, stop, nötr, bekliyor}`, `mfe_pct/mae_pct`, `mfe_atr/mae_atr`, `son_pct`,
`hedef_bar/stop_bar`, `bar_sayisi`. `outcome` hesaplanmamışsa durum `ölçülemedi` (seri yok) veya
`kirilim_yok` (hiç kırılım yok) — bu ikisi **raporda ayrı sayılır, hiçbir zaman "hedef/stop"a katılmaz**.

⚠️ **Ölçüm semantiği uyuşmazlığı (bilinen, V1'de tek kaynağa bağlanmalı):**
- Haftalık Karne metrikleri `saglayici = 1H deque` kullanır (`_karne_seri_saglayici`, `main.py:2293`)
  → 2h/4h sinyallerinde 10 bar = **10 saat**;
- P2.5 history bağlantısı (`_karne_outcome_bagla`) **kendi TF serisini** (`df_tf`) verir → 10 native bar.
**Öneri:** Backtest V1 birincil outcome kaynağı olarak `history.sonuc`'u (native-TF) kullanır;
Karne tarafı yalnız çapraz kontrol / "ölçülmemiş" tamamlama. Rapor bunun adını yazar.

⚠️ ATR kayıtta yoksa `sinyal_sonucu` `%1 × entry` fallback'i uygular (`karne.py`) → fallback'li
kayıtlar `frozen_atr_at_break` ile ayırt edilip rapor dipnotunda işaretlenmeli.

### 1.4 Supabase aynası (P2.6) — durable süper-küme

`f2_formations` (doğum + durum + `dogum_alanlar` jsonb), `f2_snapshots` (5 kalite bileşeni +
break_strength/frozen_raw_quality DÜZ kolon + `alanlar` jsonb), `f2_events`, `f2_outcome_links`
(`durum`, `deneme`, `kaynak`, `outcome` jsonb). Mirror **upsert-only; DELETE yok** (kodda doğrulandı)
→ local retention'la silinen kayıtlar Supabase'te kalır. `bar_time` TEXT'tir (saat-dilimi koruması).
Okuma için hazır arayüz var: `LocalFormationRepository` + `SupabaseStore.request_table` (salt GET).

**Sonuç:** *Popülasyon* sayımları (kaç formasyon tarandı, kaçı kırılıma ulaştı) için doğru kaynak
Supabase; *outcome* analizleri için yerel `history.sonuc` yeterli ve daha güncel olabilir.
Supabase yapılandırılmamışsa V1 popülasyon bölümleri "yalnızca yerel pencere" etiketiyle verilir.

### 1.5 Kalıcı OLMAYANLAR (V1'de umulmaması gerekenler)

- Tam OHLCV geçmişi (sadece kayar 360×1h + 500×1d cache) → **yeni geçmiş kazıma/backfill yok**.
- `selection_score`, `invalid_reason` (terminal olma NEDENİ metni — P2.6 audit'in tek açık gap'i),
  violation önbellekleri, `historical_violation_penalty` → cleanliness skoru yeniden türetilemez.
- Breakout öncesi formasyon içi MFE/MAE, benchmark/endeks verisi, spread/komisyon, gün-ici path.
- Doğum anı kalite BİLEŞEN skorları (bkz. §3).

### 1.6 Komut yüzeyi

Zaten var olan sahih kalıp: `TELEGRAM_KOMUTLARI` sözlüğü (`main.py:1438`) + yalnız
`TELEGRAM_CHAT_ID`'ye yanıt veren listener (`telegram_commands.py`). `/backtest` bir handler
eklemek, "manuel, sadece DM'den" gereksinimini sıfır yeni altyapıyla karşılar. Ayrıca
`gun_simulasyonu.py` "tam replay" için neyin gerekli olduğunun ölçütünü gösterir — V1 onun
içine girmez.

---

## 2) ONBİR SORU — Hangi çıktı anlamlı, hangisi yanıltır?

Her bölümün başlığında **n** ve **kaynak** (local / Supabase / karne) yazılı olacak; §4'teki
güvenilirlik kuralları tümü için bağlayıcıdır.

### 2.1 Genel outcome istatistikleri — ✅ tam güvenilir
Veri: `history.sonuc` (+ `f2_outcome_links`), birim = `stable_id`.
Çıktı: taranan formasyon n'i; kırılıma ulaşan n'i; çözümlenen (hedef/stop/nötr) n'i;
durum dağılımı (%); `son_pct` medyan/ortalama + min/maks; `mfe_pct`/`mae_pct` medyan;
`mfe_atr`/`mae_atr` medyan (ATR-normalize, TF'ler arası kıyaslanabilir tek metrik budur);
`bekliyor` / `ölçülemedi` / `kirilim_yok` sayıları ayrı satırda (kotaya girmez).
Öneri ek: **hedef-önceliği metrikleri** — `(hedef)/(hedef+stop)` "kaba isabet" ve
medyan `MFE/MAE oranı`.

### 2.2 Formation type bazında — ✅ anlamlı, ama gruplama dikkatli
`pattern_type` (10 değer) + `family` + `classic_dir`. Küçük n gerçeğiyle: rapor **önce family
(Üçgen/Kama/Bayrak/Flama), sonra tip** versin; n<15 olan hücreler "yalnızca betimleyici" bayrağı
alsın. Çıktı: grup başına {n kırılım, hedef oranı, medyan son_pct, medyan mfe_atr/mae_atr}.
Dipnot: "bulunma sayısı" için Karne `formasyon` TTL'si sayımı buduyor → bulunuş sayıları
history/Supabase'tan alınmalı.

### 2.3 Timeframe bazında — ✅ anlamlı
TF başına aynı kırılım; ek olarak **eşik-göreli** okuma: `ALERT_MIN_QUALITY = {1h:80, 2h:78,
4h:75, 1d:70}` (config). Bilinen yapısal fark: 1d, 1h-deque'dan resample ediliyor (~40 bar
pencere) → 1d formasyonları sistemik olarak kısa ömürlü algılanır; 1d yorumları buna göre
 yumuşatılmalı. §1.3'teki horizon semantiği uyarısı yalnız Karne-kaynaklı satırlar için geçerli.

### 2.4 Quality dağılımı ve band→outcome — ✅ en değerli bölüm
İki farklı "quality" nüfusu vardır ve karıştırılmamalı:
1. **doğum kalitesi** (`dogum.alanlar.raw_quality`), 2. **kırılım-donmuş kalitesi**
(`frozen_raw_quality` / Karne `kirilim.quality` — teyit anı `effective_raw_quality`).
Outcome analizi **ikincisini** kullanır (sinyal kalitesi odur).
Çıktı: histogram (10'luk kovalar, tüm kırılımlar); TF-eşiğine göreli bantlar —
`eşik−10 · eşik−5 · eşik · eşik+5 · eşik+10+`; her bant için {n, hedef oranı, medyan son_pct,
medyan mfe/mae_atr}. Karne'nin mevcut `q≥80 / q70–79 / q<70` etiketleriyle uyum korunur
(ayrı satırda). Eşik-altı adayların da kayıtlı olması avantajdır: "eşik gerçekten ayrıştırıyor mu"
sorusu V1'de veriyle görünür — ama **eşik/scoring değişikliği önerisi V1 çıktısı değildir**.

### 2.5 Quality bileşenleri × outcome — ✅ kirilim-teyitli kümede mümkün (§3'te detay)
Hedef küme = kırılımı onaylanmış formasyonlar (popülasyonun outcome'la ölçülebileni).
Bileşenler = `geometri` snapshot'ının 5 skoru (`geometry_score`, `slope_shape_score`,
`touch_score`, `contraction_score`, `maturity_score`) + destek alanları (`contraction`,
`correction_depth`, `duration_ratio`, `consolidation_efficiency`, `upper/lower_touches`,
`violation`, `pole_*`). Çıktı: her bileşen için **hedef-grubu vs stop-grubu medyan farkı** ve
bileşen üçlükleri (tertile) → hedef oranı tablosu. Korelasyon/ regresyon V1 dışı (§6).

### 2.6 MFE / MAE — ✅ zaten kayıtlı, yeniden hesap gerekmez
`outcome` içinde pct ve ATR-normalize hâliyle duruyor. Ek anlamlı türevler: stop olanlarda
"stop'tan önce ne kadar lehte gidildi" (`mfe_atr` dağılımı — neredeyse hedef olanlar mı?);
`hedef_bar`/`stop_bar` → ortalama/varış süresi (bar cinsinden); `bar_sayisi` < horizon olan
bekleyenler. **Yapılamaz:** kırılım-öncesi MFE/MAE, bar-ici (wick path) sırası.

### 2.7 Breakout yönü ve özellikleri — ✅ zengin veri
Yön: `kirilim.dir` (+ `break_snapshot_direction`) ve `classic_dir` ile kıyas → **devam mı /
karşı yönlü mü** (`COUNTER_BREAK` olayları da sayılır). Özellikler (20 BREAKOUT alanı, kırılım
snapshot'ında donmuş): `break_strength`, `break_body_score`, `break_close_score`,
`break_penetration_score`, `break_expansion_score`, `break_volume_score`,
`break_confirmation_strength`, `frozen_break_buffer`, `frozen_retest_tolerance`,
`frozen_atr_at_break`. Çıktı: güç bandı (ör. tertil) → hedef oranı; "karşı yönlü kırılımlar
devam kırılımlarından daha mı kötü?" V1'in en temiz test sorularından biri. Not: `entry` = teyit
kapanışı — kayma/komisyon yok; rapor "sinyal performansı"dır, "işlem performansı" değil.

### 2.8 Lifecycle / retest davranışı — ✅ olay listesi yeterli
`olaylar[]` + `snapshotlar[].state` + `terminal_state` + `deneme`.
Çıktılar: huni: `taranan → tanımlı → kırılım adayı → teyit → retest → tamam/başarısız/zayıf`
(süreler `bar_time` farklarından); RETEST_OK olan vs olmayan kırılımların hedef oranı ve medyan
`son_pct`; `deneme` sayısına göre sonuç (çok denemeli formasyon daha mı iyi?); TIMEOUT oranı
(Karne'de olayı yok — history'den sayılacak); terminal_state dağılımı. Kısıt: `MAX_OLAY=200`
uçları kesilebilir; olaylar yalnız uptime penceresinde.

### 2.9 Geometry özellikleri × outcome — ✅ doğum snapshot'ı yeter
`geometry_atr` (konsolidasyon yüksekliği/ATR), `start_width`, `upper/lower_slope` (eğiklik
simetrisi = üçgen tipi ayracı), `apex_bar−start_bar` (yakınsama hızı), `pole_duration/magnitude/
efficiency/quality` (specialized ailesi). Çıktı: bucket → hedef oranı tablosu
(ör. `geometry_atr` küçük/orta/büyük; `|upper_slope−lower_slope|` simetri skoru).
Kural: tüm bar-farkı hesapları aynı snapshot'ın bar_time'ına sabitlenerek veya Karne
kayıtlarının bar_time'ı ile yapılır; ham indeks çıkarılmaz (§4).

### 2.10 Örneklem büyüklüğü ve güvenilirlik — raporun ilk bloğu olmalı
Bkz. §4. Özet: gerçek n canlı sistemde birkaç hafta birikimle yüzlerce kırılımla ölçülür;
V1'in görevi "sonuç çıkarmak" değil **"sonuç çıkarmaya ne zaman hazır olacağız"ı sayısallaş-
tırmak**. Coverage satırı zorunlu: kaç `(stock,tf)×gün` tarandı, kaç kayıt var, kaçı çözümlendi.

### 2.11 İlk versiyonda kesinlikle gereksiz analizler
Aşağıdakiler V1'den **bilinçli dışarıda** (gerekçe §6'da tek tek):
tüm yeniden-hesap/geri-kazıma (backfill), scoring ağırlık optimizasyonu, eşik ayarı,
ML/regresyon/feature-importance, walk-forward, portföy metrikleri (Sharpe, drawdown, expectancy),
komisyon/slippage simülasyonu, hisse-leaderboard, benchmark/karşılaştırma endeksi, grafik/plot,
MFE/MAE dağılım eğrileri (histogram üstü incelik), saat-ici analiz, otomatik zamanlanmış rapor,
per-bar "neden başarısız oldum" teşhisi (`invalid_reason` persist edilmiyor — P3.1 adayı).

---

## 3) "Aynı toplam Quality, farklı component dağılımı" ayrılabilir mi?

**Kısa cevap: EVET — kirilim-teyitli popülasyonda ve snapshot anlarında; hayır — doğum anı
skorlarında ve cleanliness-alt-bileşeninde.** History bu sorunun ~%80'ine bugün yeterli.

Kanıt zinciri (kod referanslarıyla):

1. `raw_quality` tek skaler değil, tanımlı formül: üçgen/kama =
   `geometry·0.38 + touch·0.32 + maturity·0.18 + cleanliness·0.12`; bayrak =
   `pole·0.28 + depth·0.20 + duration·0.12 + geometry·0.16 + touch·0.12 + calmness·0.07 +
   cleanliness·0.05`; flama aynı 7 bileşen farklı katsayılarla (`patterns/candidate.py:278-289`).
2. Bu bileşenlerden **beşi birebir sayı olarak persist ediliyor**: `geometry_score`,
   `slope_shape_score`, `touch_score`, `contraction_score`, `maturity_score` → STATE snapshot'ları
   (`formation_schema.STATE_FIELDS`) ve Supabase'te DÜZ KOLON (`f2_snapshots`, `supabase_schema.sql`).
   Yani `q=80` iki formasyonun imza vektörü `(95,60,...)` vs `(60,95,...)` sorgulanabilir.
3. Kalan iki bileşen sayı olarak saklanmasa da **girdileri** saklanıyor:
   `depth_quality ← correction_depth`, `duration_quality ← duration_ratio`,
   `calmness_quality ← consolidation_efficiency − pole_efficiency` — hepsi STATE/IDENTITY'te var.
   (Ters dönüşüm formülleri motorun `f_band_quality/f_inverse_smoothstep` yardımıyla P3.1'de
   hesap katmanı eklenerek yapılabilir; V1'de ham girdi zaten yeterince ayırt edici.)
4. **Gerçek boşluklar:**
   a) `cleanliness` girdisi `historical_violation_penalty` **TRANSIENT** — persist edilmiyor; tek
      istisna `violation` (o-bar anlık ihlali) STATE'te var. "Temizlik" alt-bileşeni history'den
      yeniden üretilemez.
   b) `dogum.alanlar` bileşen skorlarını İÇERMEZ (yalnız `raw_quality`) — doğum anı vektörü,
      doğumla ilk geçiş snapshot'ı (`DEFINED` vb.) arasındaki bars'lar kadar kaymalı tahmin edilir.
   c) Snapshot'lar yalnız anlamlı geçiş anlarında var; "herhangi bir bar'daki" bileşen vektörü
      sorulamaz.
5. Pratik eşleme kuralı V1 için: **outcome'un dayandığı kırılım kaydının `bar_time`'ı ile aynı
   `bar_time`'lı `geometri` + `kirilim` snapshot çiftini kullan.** Motor bu ikisini aynı anda
   yazıyor (`patterns/lifecycle.py:_p2_geometri_yakala`, faz=kirilim dalı) — yani "kalitenin
   donduğu andaki bileşen vektörü" fiilen kayıtlı. Rapor eşleşmeyen stable_id'leri
   "vektör-yok" diye ayrıca sayar.

---

## 4) GÜVENİLİRLİK KURALLARI (rapor şablonuna kodlanacak)

1. **Birim = stable_id.** Karne `kirilim` satırları ile history kaydı aynı formasyonun iki
   görünümü; istatistikler stable_id üzerinde, tekrarlar deneme sayısı olarak raporlanır.
2. **n-gate'leri:** oran yorumu için n≥30, medyan-farkı yorumu için grup başına n≥15; altı
   "betimleyici" etiketli. Hücre boşsa "n=0" yazılır, sessiz atlanmaz.
3. **Bağımlılık uyarısı sabit satırı:** aynı hissenin TF'leri ve aynı günün hisseleri korele —
   efektif örneklem nominalden küçük; oranlar "gözlem oranı"dır, bağımsız-çekim güvenilir aralığı
   DEĞİLDİR. (V1 confidence interval üretmez.)
4. **Uptime bias'ı:** corpus botun ilk taramasından başlar; "2026 geneli" gibi genelleme yapılmaz,
   tarih aralığı raporda yazılır.
5. **Retention kaynak ibaresi:** her bölüm hangi kaynaktan okuduysa (local 30-kayıt/slot,
   Supabase tüm-ayna, Karne 120-gün) belirtilir; popülasyon/funnel sayımları local'den okunduy-
   sa "yalnızca yerel pencere" etiketi zorunlu.
6. **Üç "olumsuz" kutusu ayrı sayılır:** `kirilim_yok`, `ölçülemedi`, `bekliyor` — hiçbiri hedef/
   stop paydasına giremez; `ölçülemedi` oranı %20'yi geçerse rapor başlığı "kısmi veri" uyarısı
   taşır.
7. **Semantik notlar:** entry = teyit kapanışı (slippage yok); 2h/4h horizon uyuşmazlığı (§1.3);
   ATR-fallback'li kayıtlar işaretli; `mtf_destek` alanı ölü; volüm kalitesi yfinance ham
   verisinden (ilk bar vol=0 gözlemi) gelir → `break_volume_score` yorumlanırken "ham" notu.
8. **Betimle, önerme:** Rapor "şu farklar görünüyor" der; "eşiği şuna çek" demez. Değişiklik
   planı ayrı bir insan kararıdır (kullanıcının koyduğu kural).

---

## 5) FAZ 3 — BACKTEST V1 KAPSAMI (küçük, uygulanabilir)

### 5.1 Kullanıcı akışı
- `​/backtest` — tam rapor; `​/backtest 60` — yalnız son 60 gün kayıtlar (bar_time/kayıt_zaman
  filtresi); `​/backtest detay` — §5.3'teki F ve H bloklarını ekler. Alias: `/bt`.
- Mevcut sahih kalıba oturur: `TELEGRAM_KOMUTLARI`'na tek handler (`main.py:1438`) +
  `telegram_commands.kirp()` 4000 karakter koruması; uzun rapor 2 mesaja bölünür (yardim
  metnine tek satır ek). Yalnız owner DM çalışır (listener zaten `TELEGRAM_CHAT_ID`'yi zorunlu
  kılıyor). Ağda bekleme: Supabase okuması opsiyonel ve timeout'lu; yoksa yerelle devam.

### 5.2 Veri yolu (salt-okunur, tek geçiş)
1. Popülasyon: `ACTIVE_STOCKS × {1h,2h,4h,1d}` slotları; her slot için `fh.yukle()` → kayıtlar.
   Supabase tanımlıysa `f2_formations` satır sayıları eşlik eder (etiketli).
2. Outcome: `history.sonuc`; yoksa **salt** `outcome_link.formasyon_sonucu(..., saglayici=cache)`
   (mevcut fonksiyon çağrılır, YAZILMAZ — `bagla` V1'de hiç çağrılmaz).
3. Feature vektörleri: eşleşen `geometri`+`kirilim` snapshot'ları (aynı bar_time), `dogum.alanlar`.
4. Karne `kirilim` kayıtları: yön/giriş/ATR çapraz kontrolü + `deneme` sayımı.
5. Gün filtresi: `bar_time`/`kayit_zaman` ≥ kesim.

### 5.3 Rapor blokları (sırayla)
- **A. Kapsayıcılık:** tarih aralığı, slot/kayıt/kirilim/çözümlenmiş sayıları, kaynak etiketleri,
  `ölçülemedi/kirilim_yok/bekliyor` oranları. (Her şey bunun üstüne okunur.)
- **B. Genel outcome:** §2.1.
- **C. Family→type kırılımı:** §2.2 (n-gate'li).
- **D. TF kırılımı + eşik-göreli kalite bantları:** §2.3+§2.4'nin eşik kısmı.
- **E. Quality band → outcome:** §2.4; histogram metin-çubuğu (`████░░`), Karne etiketleriyle uyum.
- **F. Bileşen imzaları:** §2.5/§3 — hedef vs stop medyanları ve tertil tabloları;
  "vektör-eşleşmeyen n=…" satırıyla.
- **G. MFE/MAE + Lifecycle hunisi:** §2.6+§2.7 (breakout güç bantları) + §2.8 (retest, deneme,
  timeout) + §2.9 (geometry bucket'ları — `detay` modunda).
- **H. Vaka listesi:** en iyi/en kötü 5'er stable_id (kısaltılmış) + hisse/tf/tip/kalite/son_pct —
  elle incelemek için.
- **Z. Yapamayız notu:** sabit 3-5 satır (§4.3, §4.4, §4.7).

### 5.4 Kod izi (uygulama turunda; şimdi yazılmıyor)
- Yeni: `analytics/backtest.py` (saf toplanan-veri→metrik fonksiyonları; tek bağımlılık okuyucu
  katmanlar), `analytics/backtest_raporu.py` (metin biçimlendirme, `reporting/format.py`
  konvensiyonu), `test_backtest_v1.py`.
- Dokunuş (ekleme yalnızca): `main.py` handler sözlüğü + `/yardim` satırı.
- **Dokunulmaz:** `patterns/*`, `karne.py` hesap kısmı, `state/formation_history.py`, eşikler,
  config sabitleri.

### 5.5 Kabuller (tanımlanmış DoD)
1. Backtest koşusu ÖNCESİ/SORASI `bot_data/` ve Supabase byte-diff'siz (tek istisna: opsiyonel
   yerel rapor dosyası `bot_data/backtest/` altına).
2. Ağ çağrısı yalnız salt-oku Supabase GET (timeout + fallback).
3. Hiç kayıt yoksa komut çökmez: "corpus boş, şundan sonra tekrar dene" + kapsam bilgisi.
4. Her tabloda n; n-gate altındaysa yorum sütunu "-" olur.
5. Mevcut tam pytest suite'i (638+) değişikliksiz geçer; yeni testler en az: boş corpus,
   sentetik hedef/stop karışımı, eşleşmeyen snapshot'lı kayıt, gün filtresi, 4000-krn kırp.
6. Rapor çıktısında dosya yolu/sır bilgisi yok (`/karne`'deki "📁 kayıt yolu kaldırıldı" dersi).

### 5.6 V1 dışı açık kalanlar → P3.1+ not defteri (söz vermeden)
- Doğuşa component skorlarının eklenmesi (1 alan seti, kontrat genişletmesi) ve
  `invalid_reason`'ın terminal'e yazılması.
- `sonuc`'ta 2h/4h horizon semantiğinin tek tipe bağlanması (davranış değişikliği — ayrı onay).
- Karne `mtf_destek` wiring'i ya da alanın kaldırılması.
- Supabase tarafında `alanlar` jsonb'ye GIN indeks (önce ölç).
- Gerçek replay-backtest (yfinance'tan derin seri + motoru offline koşturma) — `gun_simulasyonu`
  altyapısı çekirdek olabilir; ayrı faz kararı.

---

## 6) Neden V1 bunu YAPMIYOR (kuralın gerekçeleri, tek paragraf)

Yeniden hesap (backfill) mevcut cache derinliğiyle fiziksel olarak imkânsız (§1.5); optimizasyon
ve threshold taraması, §2.10'daki örneklem gerçekleriyle istatistiksel olarak erken ve kullanıcı
kuralına aykırı; bileşen-ağırlığı regresyonu, cleanliness boşluğu (§3.4a) nedeniyle tanımlı hedef
vektörü üretemez; portföy metrikleri pozisyon boyutlandırma tanımı olmayan bir sinyal sisteminde
anlamsız. V1'in ürettiği tek şey **bir sonraki kararın veriye dayanabilmesini sağlayacak dürüst
ölçüm katmanıdır**.
