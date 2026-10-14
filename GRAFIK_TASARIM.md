# GRAFİK TASARIM SÖZLEŞMESİ (G0 → G5)

> **Tarih:** 2026-10-13 · **Dal:** `arena/953e9c1b-formation-bot` · **Dayanak:** 7 soru
> turu + iki öz-eleman turu; sayılar koddan ve ölçümden (her "≈" işaretlidir).
> **Bu dosya repoda yaşar.** Önceki sürüm depo dışında (`~/format-atolye/`)
> tutuluyordu; 2026-10-13 19:23'te sandbox yeniden kurulunca o klasör ve
> `.venv` silindi, doküman kayboldu, git geçmişi uzaktan (`e4b451a`) geri alındı.
> Kural: tasarım/ölçüm dokümanları depo içinde, ölçüm çıktıları (PNG vb.) depo dışında.
> **Kod değişikliği yoktur; bu doküman tek kaynaktır.** Uygulama sırası §3.

Amaç (kullanıcının cümlesiyle): kartın söylediği her şey grafikte de görünsün —
her OB hangi mumdan başlıyor, her FVG nerede başlıyor, formasyon hangi mumlara
dokundu, piyasa yapısı (PH/PL, HH/HL/LH/LL) ve BOS/CHoCH nerede oldu. **Uydurma
alan yok:** çizilen her etiket motorun gerçek çıktısına dayanmak zorunda (§1).

---

## 0 · Kararlar

1. **Kanal:** yalnız DM. Grup/kanal hattı kökten iptal (§9). Bilgi kaybı yok:
   grup içeriği DM'de zaten duruyor.
2. **Mesaj akışı:** "1 olay = 1 mesaj" kuralı **metin** için değişmez. Görseller
   alarm metninin **altına** ek mesaj olarak gelir (kare başına 1 mesaj; albüm
   v2 adımı). Metin kaybı hiçbir koşulda olmaz.
3. **Kare başına 1 PNG = 1 hisse × 1 TF.** 4 TF'yi tek kareye sıkıştırmak
   reddedildi (yazı ~8 px'e düşüyor). Kart metni caption olarak kullanılmaz;
   hangi TF olduğu karenin kendi başlığında yazar.
4. **Kalıcı koyu tema**, bayraksız (§0.4.1). OB yeşil / FVG mavi zorunlu;
   geri kalanı sabit palet.
5. **Veri dürüstlüğü:** kaynakta olmayan hiçbir değer çizilmez. Motor `fill`
   vermediyse kutu kontur kalır, `%` uydurulmaz (§0.12k).
6. **Yalnız kapanmış mumlar** çizilir; sağ üstte `son kapanan 25 Eyl 17:30 · 70,95`.
7. **Piyasa yapısı = yalnız external swing'ler** + BOS/CHoCH (internal/half-swing yok).
8. **Zone seçimi:** OB ve FVG **tek havuzda**, son kapanışa uzaklık ATR'ye
   bölünerek sıralanır (confluence birlikte değerlendirilir); eşitlikte daha yeni
   `source_index` kazanır.
9. **Zone sayısı TF'ye göre:** `1s 3+3 · 2s 3+3 · 4s 2+2 · 1g 1+1` (üst/alt).
   Sabit sayı yerine bar sayısıyla ölçeklenir.
10. **Engulfing kutuları çizilir** (mor kesikli) — motor `bull_engulf/bear_engulf`
    üretiyor, kartta da var.
11. **Alarm mumu:** gri kesikli düşey çizgi + state yazısı **başlık altında**
    (`alarm: kapanışla teyitli kırılım`), `STATE_TR`/`PUBLIC_STATE_ETIKET` metniyle.
12. **Kutu yazısı minimal:** kutunun içinde yalnız `OB↑/OB↓/FVG↑/FVG↓/ENG`;
    `%doluluk` ve `qNN` kutunun dışında, koyu `bbox` ile.
13. **Dikey kadraj:** çizilen her şey görünür (hiçbir kutu/çizgi kesilmez),
    ±%4 pay.
14. **Bar başına piksel korunur:** `genişlik = bar × 6 px`, taban 1080,
    tavan **1440** (§17.2); `px/bar < 5` ise mumlar **kapanış çizgisi + alan**a
    çöker (§17.1). Formasyon 180 bardan eskiyse `GRAFIK_MUM_MAKS` kalkar.
15. **Pencere formasyonun başladığı muma sabitlenir**, geriye doğru MS için
    uzatılmaz; kadraj dışı kalan olaylar `◂ N eski olay` olarak sayılır.
16. **Sayı biçimi:** her yüzeyde Türkçe virgül (`46,37`, `%78`, `q91`); binlik
    ayracı yok. Bu **G0** commit'idir ve grafik kodundan ÖNCE gelir (§15, §19).
17. Katmanlar faz faz gelir; her faz tek commit + tam test yeşil (§3).

### 0.4.1 Kalıcı palet (koyu zemin `#101418`, metin/eksen `#e8e8e8`)

| Katman | Renk | Çizim |
|---|---|---|
| Mum (yükselen) | `#e3e6e8` | içi boş gövde + fitil |
| Mum (düşen) | `#8d949a` | dolu gövde + fitil |
| Order Block | `#2bb673` | %14 dolgu (kutunun yüksekliği görünür aralığın %18'ini aşarsa 0,05'e iner §17.6) + `source_index`'te kalın kenar |
| FVG | `#42a5f5` | %12 dolgu + tarama (hatch) + `formation_index`'te kalın kenar |
| Engulfing | `#b388ff` | kesikli kontur |
| Formasyon çizgileri | `#f5f5f5` | 1,6 pt; son muma kadar projeksiyon; `apex`'te `x` |
| Temas mumları | `#e8e8e8` | açık `o` işareti + temas sayısı |
| PH/PL | `#90a4ae` | aday α.45 / teyitli tam / kırık α.2 |
| HH/HL/LH/LL | `#b0bec5` | küçük yazı |
| BOS/CHoCH | `#ff8a65` | ok + kesikli seviye çizgisi + `BOS↑/CHoCH↓` |
| Katılım şeridi | `#80cbc4` | §2.1 |
| İhlal / `!` | `#ef5350` | `!` (çaba var-sonuç yok, son 15 mum) ve ihlal işaretleri |
| Izgara | `#2a2f35` | yalnız yatay, kesikli (§17.7 kalabalığı) |

Renk tek başına bilgi taşımaz: her bölge/katman bir de **yazı** taşır.

### 0.12a–aa · Sonraki turların kararları (özet)

- **a** Alarm barı: gri düşey çizgi + `TEYIT/RETEST/…` yerine **gerçek state metni** (z).
- **b** 180 bar tavanı formasyon eskiyse kalkar; `genişlik = bar × 6 px`,
  taban 1080 / tavan 1440, çökme modu yedek.
- **c** Bölge kutusu yazısı minimal (12).
- **d** Yalnız kapalı bar (6) · **e** formasyon çizgileri son muma kadar uzatılır
  (apex'e değil) · **f** `kritik` seviye çizgisi VAR, hedef/stop YOK
  (kartta kalıyor; kalabalık gerekçesi) · **g** doluluk = gölge + kısa sayı, ek
  başlangıç çizgisi yok (sol kenar zaten `source_index`) · **h** dil = kısaltalar
  İngilizce (`OB FVG BOS↑ CHoCH↓ RVOL`), cümleler Türkçe.
- **i** MS olay filtresi: `confirmation_status=CONFIRMED` **ve** `validity=VALID`,
  pencere içi, en yeni `GRAFIK_OLAY_MAKS=6` (ölçüm: ham liste 28-56 kayıt).
- **j** Şerit yalnız spike'ları çizer; düşük hacim işareti kaldırıldı.
- **k** `fill` olmayan kutu kontur; `%` uydurulmaz.
- **l** `1s` ve `2s` karelerinde FVG **çizilmez** (`FVG_TIMEFRAMES={2h,4h,1d}` +
  `enable_2h_fvg=False` — botun canlı yolu da False; parite bozulmaz).
- **m** Kare listesi `alarm→1s→2s→4s→1g`, tekilleştirmeli, en fazla 4.
- **n** G0 kapsamı = yalnız ondalık ayracı; `50,00` → `50` olmaz.
- **o** `/grafik THYAO` → 4 kare; `/grafik THYAO 4s` → tek kare (G4'te).
- **p** PNG `/tmp`de üretilir, gönderim sonrası silinir.
- **q** Kare oranı **4:3** (1080×810 taban; §17.1-2 ile `bar_px=6`, tavan 1440).
- **r** Boğa/ayı ayrımı renk değiştirmeden: kalın kenar (boğada alt, ayıda üst) + ok.
- **s** Görsel anlıktır; arşiv yok; meta JSONL alanı hazır (§13).
- **t** Veri köprüsü = tarama anında anlık görüntü (§14).
- **u** `/grafik` G4'te eklenir; üç yardım yüzeyi birden güncellenir.
- **v** Lejant karenin altında tek gri satır.
- **w** Dipnot yalnız veri sorunu varsa.
- **x** Görseller metin kotasından yemez; `_gonder` dönüşü görselden etkilenmez.
- **y** v1'de yalnız 4 env anahtarı; gerisi `grafik.py` sabiti.
- **z** Alarm etiketi gerçek state metninden (`notifier.py:667` tabloları).
- **aa** v1 teslimi sıralı `sendPhoto` ×4; albüm + `reply_parameters` ayrı adım;
  4s `rvol · yerel hesap` şeridi v1'de var.

---

## 1 · Veri envanteri (her etiketin kaynağı)

| Katman | Kaynak | Alanlar (koddan doğrulanmış adlar) |
|---|---|---|
| Mumlar | `bot_data/<SEM>.json` (360 × 1h) → `data.resample_ohlcv(df, tf)` | `open/high/low/close/volume`, tz-aware `Europe/Istanbul` indeks |
| Formasyon | tarama adayı (`cift`) | `start_bar/end_bar/apex_bar`, `upper/lower`, `contraction`, `quality`, `touch_stats`, `state`, `break_price/critical_price_level` |
| Order Block | `domain_engines/runner.py` → `output["order_block"]` | `export.bull/bear → state, top, bottom, fill, source_bar`; tam liste `details["records"]/["active_records"]` → `OrderBlockRecord(source_index, source_time, top, bottom, bullish, base_score, has_imbalance, anchor_high, anchor_low, imbalance_end_index, fill_boundary)` — **record'da `fill` YOK** (§17.12) |
| FVG + engulfing | `output["fvg"].details` | `fvg_formations`, `engulfing_formations`, `active_bullish_fvg/active_bearish_fvg`, `completed_*`; `FvgLifecycleRecord(direction, state, formation_index, timestamp, lower_boundary, upper_boundary, gap_size, gap_atr, formation_atr, quality, embedded_candle_contribution, evidence_count)`; export `bull_fvg/bear_fvg/bull_engulf/bear_engulf` |
| FVG TF kısıtı | `runner.py:33, :339` | `1s`/`2s`de FVG üretilmez; lejantta `FVG · 4s/1g` |
| Market structure | `output["market_structure"].details` | `external_swings`, `event_history` (filtreli çizim §0.12i), `latest_external_event`, `broken_level`, `event_bar`, `swing_class` |
| Katılım | `output["volume_participation"]` | `ParticipationExport(state, rvol, volume_level, volume_regime, quality, effort_result_class, capital_level, up/down_evidence_count, net_progress_atr)`; şerit için `rvol = hacim / SMA(hacim, 20)` |
| TF etiketi | `notification_context.py:15` | `TIMEFRAME_LABELS = {"1h":"1s","2h":"2s","4h":"4s","1d":"1g"}` — yeni eşleme icat edilmez |
| State metni | `notifier.py:661 PUBLIC_STATE_ETIKET` (+ `_bulleten_olay` `:1381`); **`STATE_TR` adında bir tablo YOK** (G1'de düzeltildi) | `KIRILIM_TEYITLI / RETEST_BASARILI / KIRILIM_GECERSIZLESTI` |

Kural: `source_bar` / `formation_index` / `event_bar` **resample edilmiş
çerçeveyi** indeksler → grafik aynı `resample_ohlcv()` çağrısının çıktısını ve
aynı dilimi kullanır; ham 1h cache'ine motor indeksi uygulanmaz.

## 2 · Çizim sözleşmesi

- `anlik_goruntu(cift, tf, ...) -> dict` saf fonksiyonu çerçeveyi, zone/MS
  kayıtlarını, `son_bar_ts`'yi ve alarm bilgisini kopyalar; `ciz(grafik_verisi,
  tf, secenekler) -> (png_yolu, meta)` **hesap yapmaz** (motoru yeniden
  çalıştırmaz, deque'a dokunmaz). `son_bar_ts` uyuşmazsa çizim reddedilir (§14.3).
- Kadraj: `sol = max(0, min(bas_bar - 8, n - GRAFIK_MUM_MAKS))`, `sag = n`.
- `genislik = clamp(bar × 6 px, 1080, 1440)`, `yukseklik = 810`, `dpi = 100`.
- Y: çizilen her şeyin min/maksı ±%4; üstte şerit kulvarı için ayrıca pay.
- X: **bar indeksi** (0..n-1); zaman ekseni çizilmez — ölçüm: 360 barın 32
  aralığı 16 s (gece), 7'si 64 s (hafta sonu); zaman ekseni kadrajı ~%40 yer.
  Tick'ler seans başlarından, **en fazla 8 etiket** (§17.7).
- `meta` (testlerin doğruladığı şey; piksel değil): `{sem, tf, mum_sayisi,
  bar_basina_px, temas:[bar...], cizgiler:{...}, zone:{cizilen,elenen},
  olay:{...}, serit:{acik,esik,spike}, budama:[...], eksik_katmanlar:[...],
  hacimsiz_bar, son_bar_ts, sure_ms, png_kb, uyarilar:[...]}`.

### 2.1 · Katılım (hacim) şeridi

Ayrı hacim ekseni/alt panel **yok**. Şerit, eksenin üstünde ayrı kulvarda
(§17.4) ve yalnız spike'ları çizer:

| rvol | motor sınıfı | çizim |
|---|---|---|
| ≤ 0.60 / 0.60–0.75 | `VERY_LOW` / `LOW` | **çizilmez** (ölçüm: 200 barın 36-74'ü; bilgi taşımıyor) |
| 0.75–1.20 | `NORMAL` | çizilmez (boşluk = normal) |
| ≥ 1.5 ve en sert 12 | `RISING` | teal çubuk + tek `×2,9` etiketi (§17.3) |
| + percentile ≥ `high/abnormal` | `HIGH` / `ABNORMAL` | parlak teal + `▲` — **yalnız motorun dayanağı varsa** |
| `effort_result_class = HIGH/VERY_HIGH_EFFORT_WEAK_RESULT` | motor sınıfı | `!`, yalnız son 15 mum (§0.12a) |
| `volume <= 0` | — | çubuk çizilmez; dipnot `veri: N bar hacimsiz` (ölçüm: 1h'da 39/360; 4s'te agregasyonla 0 → dipnot **kaynak TF oranıyla** hesaplanır, §17.10) |

**`VolumeParticipationConfig.minimum_history=150` düşürülMEZ** (kullanıcı
sordu; ret gerekçesi, kodla doğrulanmış):
1. `volume_long_length=50` 40 barda hesaplanamaz → `volume_regime` çöker.
2. `HIGH/ABNORMAL` sınıfları 100 barlık percentil ile (`percentile_length=100`,
   `_percent_rank`) belirlenir; 40 örneklik percentil'de bar kendini de sayar →
   "anormal hacim" iddiası şişer, yani yalan üretir.
3. Aynı eşikler **alarm metnine** de giriyor → indirim grafikle sınırlı kalmaz.
4. `minimum_history` Pine-parity/veri-kalitesi sözleşmesinin parçası
   (`test_domain_engines.py`, `test_domain_incremental_parity.py`,
   `ZONE_SCORING_AUDIT.md`).
5. BIST saatlik hacminde seans kabarıklığı var; 40 bar 1 haftadan kısa →
   "yükselen hacim" hafta-günü etkisiyle yanıltır.

Bunun yerine grafik kendi `rvol(20)` şeridini çizer (21 bar yeter, her TF'de
çalışır) ve motorun `state/VolumeLevel` sınıfı **yalnız ≥150 bar varsa** basılır.

TF kısıtı (ölçülmüş): `1s` 360 bar (state var) · `2s` 200 (var) · `4s` 120
**(yok → `rvol · yerel hesap` etiketiyle yerel rvol)** · `1g` canlıda ~500
(`GUNLUK_FETCH_PERIOD="2y"`, `GUNLUK_DEQUE_MAXLEN=500`, `config.py:209-210`;
lokal simde `_gunluk.json` yoksa 40) · backtest/parite 400.

### 2.2 · Kalabalık bütçesi (ölçüldü)

Aynı cache ile `run_domain_engines` çalıştırılarak sayılan işaret miktarları:

| Hisse · TF | bar | FVG | OB (aktif) | Engulf | swing | MS olayı (tümü) |
|---|---|---|---|---|---|---|
| AKBNK 2s | 200 | 17 | 3 (2) | 6 | 20 | 56 |
| AKBNK 4s | 120 | 5 | 7 (5) | 1 | 8 | 37 |
| AKBNK 1g | 40 | 1 | 3 (3) | 0 | 4 | 10 |
| THYAO 2s | 200 | 19 | 10 (8) | 4 | 17 | 28 |
| THYAO 4s | 120 | 5 | 11 (10) | 1 | 10 | 16 |
| THYAO 1g | 40 | 1 | 5 (5) | 0 | 4 | 8 |

Kurallar: (1) olay filtresi §0.12i; (2) şerit yalnız spike (§2.1); (3) `fill`
olmayan kutu kontur; (4) **budama = tek kural** `px/bar < 5 → çizgi modu`
(§17.14: üç kademeli merdiven hiçbir gerçek kadrajda tetiklenmiyor);
(5) etiket çakışmasında düşük öncelikli etiket düşer
(`kritik > olay > kutu % > swing sınıfı`). 4 karenin ayrımı en büyük rahatlama.

---

## 3 · Fazlar

**S — spike (yapıldı, commit yok):** `mum + OB + şerit + kadraj` ölçümü; sonuçlar
§17. Spike'ın kodu ve PNG'leri sandbox sıfırlanmasında kayboldu; **ölçümler bu
dosyada duruyor** ve G1'de kod yeniden yazılırken tek referans burasıdır.

**G0 — sayı biçimi (virgül) commit'i:** §15 + §19'daki 10 maddelik liste.
`reporting.format.sayi()` tek standart olur (virgül + `isfinite` koruması);
`notifier._sayı`/`_format_price`, `notification_context._price`,
`analytics/backtest._s()`, `main.py` `/durum` ve `gecen_sure`/panel satırları ona
bağlanır. Kart baytları **değişmemeli** (kart zaten virgüllü). Mesaj içeriği aynı,
yalnız ondalık ayracı.

**G1 — iskelet + formasyon:** `grafik.py` (`ciz`, `anlik_goruntu`, `SABITLER`,
`matplotlib.use("Agg")`, `plt.close`, `MPLCONFIGDIR`), `grafik_uret.py` CLI
(`--hisse --tf --mum --cikti`), `requirements.txt`'e `matplotlib==3.11.2` pin'i,
sim'e `_gunluk.json` seed'i. İçerik: kapalı mumlar, formasyon çizgileri + son muma
projeksiyon, `start/end/apex`, temas mumları (`o` + sayı), alarm çizgisi + state
metni, başlık/`son kapanan`, lejant, dipnot, çökme modu, `meta`. `eksik_katmanlar`
ve `budama` satırları bu fazda.

**G2 — zone'lar:** OB kutuları (tam liste, yakınlık cap'i, `source_index` kalın
kenar, `OB↑/OB↓` + `bbox`), FVG kutuları (`fvg_formations`, `formation_index`
kenarı, `gap_size`, `state` → solid/mitigated/hatched; `1s/2s` yok), engulfing
kutuları (mor kesikli), doluluk yalnız motorun verdiği kutuda.

**G3 — yapı + şerit + bütçe:** external PH/PL + `HH/HL/LH/LL` (aday α.45 /
teyitli tam / kırık α.2), onaylı+geçerli en yeni 6 BOS/CHoCH (ok + kesikli seviye
+ `BOS↑/CHoCH↓`), ihlal/apex kalıntıları, `kritik` çizgisi, §2.1 şeridi (4s yerel
rvol, `rvol · yerel hesap`), `!` son 15 mum, `yetersiz geçmiş` notu,
`evidence_text` yalnız `--etiket-detay`.

**G4 — teslim:** `transport/telegram.py`'ye `foto_gonder` (multipart; mevcut
`api_cagri` `:93` json-only, oradan gidilmez) ve `medya_grubu` (v2 adımı,
`sendMediaGroup` + `attach://`, albüm 2-10 öğe); `notifier._gonder` içinde
`sendMessage` 200 sonrası görsel kuyruğu (tek işçi, mevcut pacing + 429
`retry_after` mantığı public yoldan **silinmeden önce** ortak yardımcıya çıkarılır
`:1234-1240`); `main.py`'de `payload['grafik_verisi']` köprüsü + config anahtarları
+ `.env.example`/`deploy_check.py` güncellemesi; `/grafik` komutu (`KOMUT_YARDIM`
`main.py:990`, yardım satırı `:1162`, `deploy_check.py:489`); görsel hata → görsel
yok, metin gider; `_gonder` dönüşü görselden etkilenmez.

**G5 (opsiyonel):** `/karne` ısı haritası; `GRAFİK_META` JSONL (§13).

**K1/K2 — grup iptali (§9):** grafikle ilgisi yok, ayrı commit'ler.

## 4 · Telegram akışı (G4'te yazılacak kararlar)

- Sıra: alarm metni → (kuyruk) `sendPhoto` ×N; `TELEGRAM_GRAFIK_ARALIK_SN` yerine
  **mevcut pacing yardımcısı** kullanılır (§16.3.3).
- Kota: görseller `max_gunluk`/`max_saatlik` **yemez**; ayrı sayaçlar
  (`gonderilen_grafik`, `atlanan_kota`, `atlanan_hata`, `ort_sure_ms`) →
  `gonderim_durumu()` (`notifier.py:2141`) üzerinden `/durum`'da tek satır.
- v2 adımı: `sendMediaGroup` + `reply_parameters` (ilk kare metni yanıtlar) —
  Telegram dokümanı bu ortamdan doğrulanamadığı için canlı smoke testinden sonra.
- Dosya: `DATA_DIR` dışı, `/tmp/fb_grafik_<SEM>_<TF>_<uuid>.png`; gönderim sonrası
  silinir; açılışta bayat `fb_grafik_*` süpürülür; disk < 200 MB free → üretme.
- Girdi: `/grafik <arg>` sembol desenine uymazsa reddet; cache yoksa
  "önbellekte veri yok" (canlı çekme YOK); `/grafik` ipucusu alarm metninde
  geçmez (`gun_simulasyonu.py:625` YASAK testi).
- `TELEGRAM_GRAFIK=yok` (varsayılan) → davranış bugünküle **bayt bayt aynı**.

## 5 · Config yüzeyi — v1'de yalnız 4 env anahtarı

| Anahtar | Varsayılan | İş |
|---|---|---|
| `TELEGRAM_GRAFIK` | `yok` | kill-switch; `alarm` = metin sonrası kareler |
| `TELEGRAM_GRAFIK_ADET` | `4` | alarm başına en fazla kare (1-4) |
| `GRAFIK_MUM_MAKS` | `180` | kadraj tavanı (formasyon eskiyse kalkar) |
| `GRAFIK_OLAY_MAKS` | `6` | onaylı+geçerli BOS/CHoCH sayısı |

Dokümantasyon borcu: bu 4 satır `.env.example`a ve `deploy_check.py` env tablosuna
eklenir ("her anahtar belgelenmiş mi" testi yok → borç burada izlenir).

```python
SABITLER = {                     # grafik.py — §17 ölçümleriyle
  "genislik_taban": 1080, "yukseklik": 810,
  "bar_px": 6, "genislik_tavan": 1440, "mum_min_px": 5.0,
  "zone_ust": {"1h": 3, "2h": 3, "4h": 2, "1d": 1},
  "zone_alt": {"1h": 3, "2h": 3, "4h": 2, "1d": 1},
  "diverans_mum": 15, "serit": "rvol20", "serit_esik": 1.5, "serit_maks": 12,
  "dipnot": "sorun", "lejant": True,
  "katmanlar": ("formasyon", "ob", "fvg", "ms", "serit"),
  "etiket_detay": False, "drift_tolersans_bar": 0, "meta_jsonl": None,   # §13
  "gorsel_aralik_sn": "mevcut pacing yardımcısı",
  # boyut merdiveni/JPEG fallback YOK: ölçülen 40-99 KB, JPEG daha büyük (§17.9)
}
```

## 6 · Doğrulama planı

1. **Yapı testleri `meta` üzerinden:** kadraj hesabı, `bar_basina_px`, zone
   cap'leri, olay filtresi, `budama`/`eksik_katmanlar`, `drift` reddi
   (`son_bar_ts` kaydır → çizim yok + `kaydi` uyarısı).
2. **Hizalama testi:** `resample_ohlcv` ile aynı dilim → `source_index`/
   `formation_index`/`event_bar` mum indeksine denk gelmeli (regresyon testi).
3. **Kart ↔ kare sayı paritesi:** `meta`'daki kritik/seviye sayısı ile kart
   satırındaki sayı eşit (G0 sonrası virgül biçimiyle).
4. **Kapsam testleri:** `1s/2s`de FVG katmanı çizilmez; `yerel hesap` etiketi
   yalnız `state` yokken; `!` yalnız son 15 mum; lejant/dipnot satırları.
5. **Boyut/format:** PNG ≤ 500 KB (ölçülen 40-99 KB), oran 4:3,
   `metadata={"Software": None}`, `use("Agg")` + `plt.close` (RAM büyümesin).
   Determinizm `meta`'da; piksel hash'i teste bağlanmaz (§12.19).
6. **Matris:** 6 hisse × 4 TF + 1 stres karesi (en kalabalık sembol, çökme
   modu) — 28×4 tam matris gereksiz (§16.2).
7. **Mesaj hatları:** `TELEGRAM_GRAFIK=yok` iken alert byte'ları bugünküle aynı;
   klasik stil etkilenmez; `test_telegram_measure.py` satır bütçesi görseller için
   uygulanmaz (görsel metin değildir — bu ayrım teste yazılır).
8. Her faz sonunda `DATA_DIR=/tmp/fbdata .venv/bin/python -m pytest -q` yeşil.

## 7 · Riskler / bilinçli tercihler

- Motor `details` sözlükleri derin kopya; payload'a eklenen `grafik_verisi`
  bellek içi kalır, hiçbir kalıcılık yoluna yazılmaz.
- `matplotlib` yeni bağımlılık: deploy pin'i + `MPLCONFIGDIR`; lazy import
  (`TELEGRAM_GRAFIK=yok` iken hiç import edilmez).
- 4s yerel rvol motor dışıdır → etikette açıkça `yerel hesap` yazar.
- Kareler 1,2-1,7 s sürer; metni bekletmemek için kuyruk şart (§17.13).
- Albüm/reply davranışı canlıda doğrulanacak (tek kareyle smoke).

## 9 · Grup kanalının kökten iptali (ayrı commit'ler)

- **K1 (geri alınabilir):** varsayılan hedef boş → `public_enabled`
  (`notifier.py:861`) no-op; `PUBLIC_*` anahtarları (`config.py:290-325, 424`)
  durur, davranış DM'e iner.
- **K2 (temizlik):** `send_to_public` (:1205), `format_public_batch` (:1363),
  `format_public_summary` (:1419), `_public_izleme_adaylari`, `PUBLIC_*` ve
  `deploy_check.py:649,709` + `kanal_acilis.py` public adımları kaldırılır;
  **yüzey:** 10 dosya (4 kod: `config.py`, `karne.py`, `main.py`, `notifier.py` +
  6 test dosyası) + `PUBLIC_GRUP_HAZIRLIK.md`, `KANAL_ACILIS_PAKETI.md`,
  `README.md` notları. Silinmeden önce 429/`retry_after` mantığı ortak
  yardımcıya taşınır (§16.1.2).

## 12 · Geniş tarama (durum etiketleriyle)

Kapandı: kota/pacing kararı (§16.1.1-2), hook noktası, `use("Agg")`,
`.env.example` borcu, cache-miss politikası, state etiketi, parite testi,
`/durum` sayaçları, `.gitignore` (`bot_data/*_gunluk.json` zaten ignore'da ✓;
`*.png` kuralı G1'de eklenecek), 1g yıl etiketi, "bölge yoksa `eksik:` yazılmaz".
Açık/karar bekleyen: `--pano` (v1 yok), `GRAFİK_META` (v1 yok, §13), geriye dönük
yeniden çizim (yok). Renk paletinin renk-körlüğü kontrolü **G1'de yapıldı** (§22.6).

## 13 · İleride istenecek ama şimdiden yazılmayan: meta JSONL

`GRAFİK_META=<yol>` açıldığında gönderilen her kare için tek satır JSON:
`{ts, sem, tf, tur, bar_sayisi, bar_basina_px, sure_ms, eksik_katmanlar, budama,
kota_atlandi, zone:{ust,alt,ob,fvg}, olay:{bos_choc}, serit:{kaynak,yerel,spike},
png_kb, mesaj_id}`. Yazma hatası alarmı engellemez; `ensure_ascii=False`;
dosya `DATA_DIR` dışında olabilir; rotasyon kullanıcının işi. Ölçülecek:
kotadan kaç kare yedik, hangi katman en çok buda­nıyor, hangi TF'de render pahalı.

## 14 · Kendine bakış (kodla bulunanlar)

1. Görselin verisi gönderim anında **yok**: kart `main.py:2543`'te tarama
   döngüsünde hazırlanıyor, `notifier.py` yalnız `domain_bolumleri` satırlarını
   okuyor (`:348, :417`) → veri köprüsü ayrı iş kalemi (§0.12t).
2. Çizim yolunda **motoru yeniden çalıştırmak yasak**
   (`runner._advance_incremental_engine` sembol+TF durumunu ilerletiyor).
3. `data.py:843 get_deque()` canlıdır → çizim anlık görüntüden yapılır;
   `son_bar_ts` uyuşmazsa reddedilir.
4. `/grafik` üç yüzeye dokunur (`main.py:990, :1162`, `deploy_check.py:489`);
   `gun_simulasyonu.py:625` YASAK testi nedeniyle komut ipucusu alarm metninde
   yazılmaz.
5. `TIMEFRAME_LABELS` ve state tabloları yeniden kullanılır.
6. `matplotlib` requirements'ta yoktu (venv'de 3.11.2) → G1'de pin.

## 15 / 19 · G0 kapsamı (kod okumasıyla düzeltilmiş nihai liste)

| # | Yer | Ne |
|---|---|---|
| 1 | `reporting/format.py:148 sayi()` | tek standart: virgül + `isfinite` koruması; binlik ayracı YOK |
| 2 | `reporting/format.py:105` | `gecen_sure` `{fark/3600:.1f} sa önce` → `sayi(...,1)` |
| 3 | `reporting/format.py:352` | panel aday satırı `puan {…:.1f}` → `sayi(...,1)` |
| 4 | `notifier.py:100 _format_price` | yerel `_sayı`'ya devret (NaN/None → `""`) |
| 5 | `notifier.py:121 _format_price_tl` | çift `.replace()` kalkar |
| 6 | `notifier.py:188 _sayı` | `sayi(value, basamak, varsayilan="")` |
| 7 | `notifier.py:2245,2253,2261,2269,2277,2284,2299,2316,2353` | 9 satır içi `:.2f` → `_sayı(...)` |
| 8 | `notification_context.py:40 _price` | `sayi()`'ye devret (kart baytları aynı) |
| 9 | `main.py:1046` | `KAPALI · açılışa {x:.1f} saat` → `_sayi(x,1)` |
| 10 | `analytics/backtest.py:574 _s()` | önce kırp, sonra virgül; `yuzde` dalı da |

Dokunulmayan (bilinçli): `karne.py:632`, `notifier.py:280/:334`,
`notification_context.py:597/:650/:652` (zaten virgül; `%`/`×`/işaret mantığı
farklı → bayt riski almaya değmez). `karne.py:371` ve `analytics/backtest.py:80`
`_sayi` **float'a çevirme** yardımcısıdır, metin biçimleyici değil (§15'teki
yanlışımız buydu). `:.0f` olan her yer ayraçsız → değişmez. `data.py`,
`canli_tarama.py`, `scripts/*`, log satırları mesaj yüzeyi değil.
Beklenen test hareketi: `/formasyonlar` `üst/alt/kritik`, `/durum`, panel `puan`,
backtest raporu, legacy alarm gövdesi; **kart/özet satırları değişmemeli**.

## 16 · Revizyon bulguları (özet)

- Kota: görseller metin kotasından yemez; `_gonder` dönüşü görselden bağımsız.
- 429/`retry_after` yeniden kullanılır; public yoldan önce ortak yardımcıya.
- Hook: `notifier._gonder` (`:2474`), `sendMessage` 200 sonrası; `:928` ve `:1205` kapsam dışı.
- v1 config 4 anahtar; `--pano`, albüm-v2, tam matris testi, boyut merdiveni kesildi.
- Düzeltme: K2 yüzeyi "14 çağrı yeri" değil 10 dosya + dokümanlar; G0 kart
  baytlarını değiştirmez; `TELEGRAM_GRAFIK_ARALIK_SN` ayrı `sleep` olmaz.

## 17 · S fazı ölçümleri (2026-10-13)

AKBNK/THYAO gerçek verisi, gerçek `run_domain_engines` OB kayıtları, 1080×810.

| kare | bar | px/bar | süre (ms) | PNG KB | JPEG KB |
|---|---|---|---|---|---|
| AKBNK 4s şeritli | 120 | 9.0 | 279-463 | 43-55 | 56-74 |
| AKBNK 1s 180 bar | 180 | 6.0 | 363-397 | 43-46 | 58-62 |
| AKBNK 1s 360 bar @2160 | 360 | 6.0 | 742 | 61 | — |
| AKBNK 1s 360 bar @1440 → **çökme** | 360 | 4.0 | **194** | **98** | — |

Veri hazırlama (cache + resample + motor) kare başına 40-156 ms.
Glif kontrolü: `↑ ↓ ▲ ▼ ◂ · × ≥ ! % —` + Türkçe → **uyarı yok** (DejaVu Sans).

Deltalar: **1** `bar_px 4→6`, `px/bar<5 → çizgi+alan` · **2** tavan `2160→1440`
(telefonda önizleme 1080'e iniyor) · **3** şerit eşiği `1,20→1,5` + en sert 12
(1,20 barların %25-33'ünü işaretliyor: 45/180, 39/120) · **4** şerit ayrı üst
kulvarda (fitille karışıyor) · **5** bölge etiketleri koyu `bbox` ile ·
**6** kutu opaklığı yükseklikle 0,14→0,05 · **7** x etiketleri ≤8 ·
**8** state yazısı başlık altına (sağ kenardan kırpılıyordu) · **9** JPEG büyük →
boyut merdiveni yazılmayacak · **10** `hacim≤0` dipnotu kaynak TF oranıyla ·
**11** `meta` yeterli; "piksel değil meta" kararı doğrulandı · **12** OB
record'da `fill` yok (§0.12k) · **13** 4 kare ≈ 1,2-1,7 s; darboğaz mesaj hızı,
CPU değil · **14** budama merdiveni tek kurala indi.

## 18 · S'in açık bıraktıkları (G1-G3'te doğrulanacak)

1. FVG/MS/temas/formasyon çizgileri hiç çizilmedi → "en kalabalık kare" ölçümü
   eksik; §2.2.1 olay cap'i G3'te sayılarak doğrulanacak.
2. ~~Alarm mumu sentetikti~~ → **G1**: alan adları `patterns/candidate.py` ve
   `main.py:2487-2500`'den okundu; `start/end/apex` hizası ve nesne↔sözlük yolu
   testte kilitli (`test_isaretler_...`, `test_aday_nesnesi_ile_sozluk_...`).
3. Zone sıralamasında ATR yerine mesafe/son-kapanış proxy'si kullanıldı →
   G2'de `gap_atr`/motor ATR'siyle yazılacak (proxy düşük volatiliteli hissede
   kutuları olduğundan yakın gösterir).
4. FVG `fill`/`gap_size` gölgesi hiç test edilmedi (G2).
5. Yarım seans/tatil (`exchange-calendars`) ölçülmedi (G3'e kaldı); **açık-bar
   paritesi G1'de ölçüldü**: 17:30 etiketli 1s mumu 18:00'de kapanıyor; kapalı
   değilse son bar çizime girmiyor (`test_yalniz_kapanmis_mumlar_cizilir`).
6. 1g ~500 bar kadrajı lokal simde yok → G1 seed'i `bot_data/`a **yazmadı**
   (canlı bot aynı dizini okuyor); sentetik derin çerçeve testte/CLI'da (§22.2.4).
7. Albüm/reply/multipart denenmedi (G4 canlı smoke).
8. Çökme modunda `fill_between` PNG'yi 98 KB'a çıkardı → **G1'de basamaklı
   çizgi denendi**: 299 bar @1440 → 116 KB (§22.4); şerit kulvarı olmadığı için
   çakışma G3'te yeniden bakılacak.

## 20 · Kayıt/izleme borçları

- Bu dosya repoda tutulur; her fazın commit mesajı ilgili § numarasını anır.
- `YAPILACAKLAR.md`'ye G0-G5 maddeleri G1 commit'iyle eklenir.
- Spike çıktıları depo dışında (`~/grafik-spike/`) tutulur, commit edilmez.

## 21 · G0 UYGULANDI (2026-10-13) — kayıt

Kod: `reporting/format.py` (`sayi()` + `gecen_sure` + panel `puan`),
`notifier.py` (`_format_price`, `_format_price_tl`, `_sayı`, legacy gövde
9 satır), `notification_context.py` (`_price` → `sayi()`), `main.py`
(`/durum` açılış süresi), `analytics/backtest.py` (`_s()` — kırpma önce,
virgül sonra). Toplam **6 dosya, +55/−35 satır** + yeni `test_sayi_bicimi.py`
(11 test: ayraç, binlik yok, sıfır kırpma yok, NaN/None, kart/gövde/backtest
yüzeyleri, yardımcıların aynı kuralı üretmesi).

Test beklemeleri: `test_telegram_commands.py` iki satır (`süre: 2,0 dk`,
`kritik 100,00`). Suite: **900 passed / 44 skipped**.

Doğrulanan "dokunulmayan" iddiaları (grep ile, varsayım değil):
- Kalan `:.1f/:.2f` kullanımları ya `.replace(".", ",")` ile zaten virgül
  (`notifier.py:274,328`; `notification_context.py:491,494,604,657,659`) ya da
  **log/konsol** metni (`main.py:701,2148,2708` → `logger.*`; `data.py:1438-1461`
  süreklilik mesajları → yalnız `x['tip']` Telegram'a taşıyor; `deploy_check.py`,
  `canli_tarama.py`, `gun_simulasyonu.py` CLI).
- Motorun `evidence_text` satırları (`RVOL=0.876`) hiçbir Telegram yüzeyine
  girmiyor (grep: `notification_context`/`notifier` içimde kullanım yok) →
  **G1 notu:** grafik `--etiket-detay` modunda bu metni AYNEN basarsa nokta
  ondalık görünebilir; motor metnine dokunulmaz, grafiğin kendi ürettiği
  sayılar `sayi()` ile yazılır.
- `karne.py:371` ve `analytics/backtest.py:80`'deki `_sayi` birer float'a
  çevirme yardımcısıydı; §15'teki "backtest/karne otomatik virgüle geçer"
  satırım yanlıştı — gerçek metin biçimleyici `analytics/backtest.py:_s()`.

Kalan G0 borcu (bilinçli, ertelenmedi — kapsam dışı karar): `%`/`×` ekli
yerel `.replace()` kalıpları (§19 "dokunulmayanlar" satırı). Kart/özet baytları
değişmedi; değişenler `/durum`, `/panel` `puan`, `/formasyonlar` fiyatları,
legacy alarm gövdesi ve backtest raporu.

---

## 22 · G1 UYGULANDI (2026-10-13) — kayıt

**Kod:** `grafik.py` (yeni — `SABITLER`, `PALET`, `anlik_goruntu()`, `ciz()`,
`_kare_ciz`, `_lejant_satirlar`, `_meta_kur`, `girdi_ozeti`, `_pyplot_getir()`
[lazzy import + `use("Agg")` + `MPLCONFIGDIR=/tmp/...` + `plt.close()`]),
`grafik_uret.py` (CLI: `--hisse --tf --mum --cikti --formasyon --alarm-turu
--serit-yok --etiket-detay --tum-tf --demo --json --veri-dizin`),
`test_grafik_iskelet.py` (25 test), `requirements.txt` (+`matplotlib==3.11.2`),
`.gitignore` (+`*.png`/`*.jpg`; repoda zaten tek PNG takipli değildi),
`YAPILACAKLAR.md` (+G bölümü). Suite: **925 passed / 44 skipped** (900 taban + 25 yeni test).

### 22.1 Sözleşme uyumu (§2)
* `anlik_goruntu(cift, tf, cerceve, *, sonuclar, alarm_turu, alarm_bar, sembol,
  zaman_damgasi, simdi, kare_mum) -> dict` ve
  `ciz(goruntu, tf, secenekler) -> (png_yolu, meta)`. Çizim yolu motoru yeniden
  çağırmaz, deque'a dokunmaz (§14.2); hata hiçbir durumda alarmı engellemez —
  `(None, meta)` döner (§4).
* `meta` §2'deki adlarla: `sem, tf, mum_sayisi, bar_basina_px, temas, cizgiler,
  zone, olay, serit, budama, eksik_katmanlar, hacimsiz_bar, son_bar_ts, sure_ms,
  png_kb, uyarilar` + G1 ekleri: `kare{genislik,yukseklik,sol,sag,dpi,cekme}`,
  `temas_isaret`, `isaretler`, `notlar`, `metin{baslik,sag,satirlar,lejant,
  lejant_punto,lejant_atlanan,dipnotlar,notlar,kesilen,butce,genislik}`, `cekme`,
  `girdi_ozeti`, `red`, `surum`. Testler piksel hash'ine değil buna bakıyor (§6.1,
  §12.19): `test_meta_belirleyici_ayni_girdi_ayni_kare` uçucu alanları
  (`sure_ms, png_kb, yol, girdi_ozeti`) düşürüp tamamını karşılaştırır.
* Kadraj `sol = max(0, min(bas_bar-8, n-GRAFIK_MUM_MAKS))`, `sag = n`;
  `genislik = clamp(bar×6 px, 1080, 1440)`, `yukseklik = 810`, `dpi = 100` — üç
  durum da testte (120→1080 taban, 180→1080, 300→1440 + `px/bar 4,8 < 5` çökme).
* X ekseni **bar indeksi**; tick'ler seans başlarından (günlük karede ay
  başlarından), en fazla 8 (§17.7). Saat yazılmıyor: seans başlığı her gün aynı
  saat (09:30) olduğu için bilgiyi tekrarlıyordu — etiket `GG Ay` biçiminde,
  gün değişimi ayrıksı bilgiyi zaten taşıyor (§17.7'den bilinçli sadeleşme;
  ölçümde 360 barın 32 aralığı 16 s'ti, saat yazmak kadrajı boşuna şişiriyor).

### 22.2 Bu turda verilen kararlar (ilk kez burada yazılı)
1. **Temas tanımı.** Motor tekil temas mumu listesi vermiyor (yalnız
   `upper_touches/lower_touches` sayısı + `_touch_episodes` aralıkları). Kural
   uydurulmadı: `zone_scoring._touch_episodes`'ın satır içi tanımı
   (`low ≤ ust and high ≥ alt`) `grafik._bant_temaslari()`nda aynen kullanıldı ve
   `test_temas_kurali_zone_scoring_kuraliyla_ayni` iki yolu birebir eşitliyor.
   Kutuda **iki sayı birlikte**: `bant teması N · üst X · alt Y` — kartın sayısı
   sınır-teğeti (toleranslı), kare'niki bant-delmesi; farklı tanımlar birbirinin
   yerine konmaz.
2. **İkinci budama kuralı** (§2.2'nin tek kuralına eklendi):
   `temas_isaret_maks = 24` — bant çok mumu sardıysa yalnız en yeni 24'ü
   işaretlenir; **sayı asla saklanmaz**, `budama`'ya
   `temas işareti 24'e indirildi (bant 170 mumu sardı)` yazılır.
3. **Bant çizgisi düz çizilir.** `upper_slope/lower_slope` birimi (TL/mum)
   yeniden üretilmedi — §2 "çizim hesap yapmaz". Eğim yazısı kare etiketinden de
   çıkarıldı (300 px'lik etiket bütçesinin ~%40'ını yiyor, kartta yok).
4. **`_gunluk.json` seed'i `bot_data/`a yazılmadı** (§3/§18.6'dan sapma): o dizin
   canlı botun OKUMA yedeği (`SEED_DATA_DIR`); sentetik derin çerçeve testte
   (`_cerceve`) ve CLI'da (`--demo`) üretiliyor. CLI `1d` için önce
   `StockDequeManager.to_gunluk_dataframe()` deniyor → sunucuda gerçek ~500 bar.
5. **`eksik:` satırı çizimden SONRA kurulur:** katmanın patladığı ancak o an
   biliniyor. Alt blok iki kez hesaplanır (yerleşim baştan, içerik sondan);
   `_alt_yerlesim()` bu yüzden 2 satır fazla pay bırakır.
   `test_katman_hatasi_eksik_yazisiyla_gecer` bunu kilitler.
6. **Açık bar dipnot DEĞİL:** kapalı olmayan son bar atılır ve `meta["notlar"]`a
   yazılır (§0.12w: dipnot yalnız veri bozuksa). Alarm mumu kadraj dışında
   kalırsa bilgi kaybı sayılır → `uyarilar` + `meta.cizgiler.alarm.bar_disarida`.
7. **`grafik.py` import yüzeyi ucuz:** `data.bar_kapandi_mi`,
   `notifier.PUBLIC_STATE_ETIKET`/`_tr_tarih`, `notification_context.TIMEFRAME_LABELS`
   `try/except` ile alınır (tarih biçimi yeniden kullanıldı, tablo çoğaltılmadı);
   matplotlib yalnız `_pyplot_getir()` içinde → `TELEGRAM_GRAFIK=yok` iken bot
   süreci matplotlib/pillow import etmez (§7). `kare_mum_tavani()` env'i **çağrı
   anında** okur (`config.py` import'ta donduğu için §6.1 testleri böyle çevrilir).
8. **Kod adları ASCII:** `kare_mum_tavani`, `anlik_goruntu`, `ciz`, `SABITLER`,
   `PALET` (Türkçe ama ASCII) — `grafik.py` içinde noktalı ad yok.

### 22.3 Yazı bütçesi (§2.2'nin kare ölçeğe çevrilmişi)
* Metrik `telegram_measure.genislik()` (DejaVu 16 px tabanlı); kare içi yazı
  9-10,5 pt = 12,5-14,6 px → çarpan `metin_carpani = 0,82`.
* Kare içi tek etiket: `min(etiket_maks_px=300, %28 × genişlik)`; başlık
  `×0,52`, sağ üst `×0,40`, bilgi satırları `×0,88`; sığmayan **`…` ile kırpılır**
  ve `meta["metin"]["kesilen"]`e yazılır.
* Lejant (karenin altında tek gri satır, §0.12v): sığmazsa sırayla punto
  9,0→7,0 → `bol()` ile 2 satır → sondan madde düşür (`lejant: N madde sığmadı`
  dipnotu). 40 maddelik stres senaryosunda test edildi.

### 22.4 Ölçüm (matplotlib 3.11.2 + numpy 1.26.4 — §17 ile aynı sürümler)
| kare | bar | px/bar | süre | PNG |
|---|---|---|---|---|
| sentetik 1g + bant/temas/alarm | 180 | 6,0 | 746 ms (import dahil) → ~250 ms | 76,8 KB |
| gerçek AKBNK 1s (CLI, `bot_data`) | 180 | 6,0 | 454-471 ms | 50,5 KB |
| stres: 299 bar @1440 → çizgi+alan | 299 | 4,8 | ~300 ms | 115,7 KB |

§17'nin 40-99 KB bandıyla uyumlu (§6.5 tavanı 500 KB, JPEG/boyut merdiveni yok).
İlk çağrı matplotlib + font-cache import'unu da içeriyor; bot tarafında tekil
kare ~0,25-0,45 s (§17.13'ün 1,2-1,7 s / 4 kare tahminiyle tutarlı).

### 22.5 Belgede düzeltilenler
* §1'de geçen `STATE_TR` **yok** → doğru kaynak `notifier.PUBLIC_STATE_ETIKET`
  (`KIRILIM_TEYITLI / RETEST_BASARILI / KIRILIM_GECERSIZLESTI`). Tablo dışı iç
  duruma etiket **uydurulmaz** (`alarm.etiket = None`; test edildi).
* §2.1 `FVG_TIMEFRAMES` = `{2h,4h,1d}` (kod: `zone_scoring.py:20`) — `2h` listede
  var ama `enable_2h_fvg=False` olduğu için canlıda üretilmiyor; `grafik._FVG_TIMEFRAMES`
  G2'de motorun export'u boşsa zaten çizmeyecek (§0.12l).

### 22.6 Renk körlüğü kontrolü (§12'nin açık maddesi — G1'de kapandı)
Viénot protan/deuteran dönüşümü + göreli parlaklık farkı (Δ, 0-1):
`OB #2bb673`↔`ihlal #ef5350` deuteran **0,019**; `FVG #42a5f5`↔`şerit #80cbc4`
protan **0,000**; `formasyon`↔`temas` 0,03; `olay #ff8a65`↔`ihlal` 0,048. Yani
**bazı çiftlerde renk tek başına bilgi taşımıyor** — §0.4.1'in kuralı
gevşetilmeyecek: ayrım şekille (kutuya `OB↑/OB↓` yazısı, `!` glifi, FVG taraması,
engulfing kesiklisi) ve kulvarla (şerit ayrı üst kulvarda, §17.4) redundant
veriliyor. Palet bu haliyle kabul; **yeni renk eklenirken aynı Δ kontrolü
tekrarlanacak**.

### 22.7 G2'ye devir
`anlik_goruntu(sonuclar=...)` ve `SABITLER["zone_ust/zone_alt"]` hazır; `sonuclar`
doluysa kare şu an yalnız `bölge/yapı verisi bu fazda çizilmedi (G2/G3)` notunu
düşürüyor (sessiz kabahat yok). G2 işleri: `_zone_sec` (mesafe/ATR sıralaması —
§18.3 proxy reddi), OB kutuları (`source_index` kalın kenar, `OB↑/OB↓` + `bbox`),
FVG kutuları (`formation_index`, `gap_size`, state→solid/mitigated/hatched;
`1s/2s` yok), engulfing (mor kesikli), doluluk yalnız motorun verdiği kutuda
(§0.12k), `meta["zone"] = {cizilen, elenen}` dolu gelecek şekilde.

---

## 23 · G2 UYGULANDI (2026-10-13) — bölge kutuları (OB / FVG / engulfing)

### 23.1 Motor gerçeği (tahmin değil — `run_domain_engines` ile ölçüldü)

Çerçeve: AKBNK `1s` ve `4s`, `profile="Dengeli"`, `enable_2h_fvg=False`.

- **OB.** `sonuclar["order_block"].export = OrderBlockExport(bull, bear)`;
  `OrderBlockSideExport(state, top, bottom, fill, source_bar)`. `fill` **yalnız en
  yakın aktif taraf için** dolu; `export.fill = record.fill_ratio` ve `order_block.py:103-112`
  eşleşmesi `source_bar` üzerinden yapılıyor. `details = {"records", "active_records"}`
  (AKBNK/1s ölçümü: 5 / 4). Kutu `details["records"]`dan alınıyor:
  `OrderBlockRecord(source_index, source_time, top, bottom, bullish, base_score,
  anchor_high, anchor_low, imbalance_end_index, fill_boundary)` — **bu kayıtta doluluk
  alanı yok**, o yüzden `%` yalnız export eşleşirse yazılıyor (§0.12k).
- **FVG / engulfing.** `details["fvg_formations"]` → `FvgLifecycleRecord(...)`
  (`lower_boundary/upper_boundary/formation_index/formation_time/state/quality/
  close_fill_ratio/gap_size/...`), `details["engulfing_formations"]` →
  `EngulfingLifecycleRecord(... formation_low/formation_high ...)`. Ölçüm: **`1s`
  için `fvg.export is None` ve `details == {}`** → §0.12l gerçek veride doğrulandı;
  karede ayrıca `_FVG_YOK_TFLAR = {"1h","2h"}` ile katman çizilmiyor (kayıt yinede
  uydurulmuyor).
- Enum alanları `IntEnum` → **ada göre** eşleştiriliyor (`_BOLGE_DOLU` / `_BOLGE_ARA`);
  sayı sabitleri yazılmadı. `direction` enum olarak gelebildiği için `_yon()` `.value`
  okuyor (sahte nesne testi bunu yakaladı).

### 23.2 Bu turda verilen kararlar (ilk kez burada yazılı)

- **Sıralama (§0.8).** Motor çıktısında OB için ATR yok → `_wilder_atr(cerceve)` =
  `zone_scoring.wilder_atr(cerceve, ATR_LENGTH)` son değeri (saf fonksiyon; §14.2
  bozulmadı, `zone_scoring` canlı yolda hiç kullanılmıyor — grep ile doğrulandı).
  ATR hesaplanamazsa ham fiyat mesafesi ve `meta["zone"]["sirala"] =
  "mesafe (ATR yok → ham fiyat)"`.
- **Tek havuz + kapak.** OB + FVG + engulfing aynı havuzda, son kapanışa yakınlığa
  göre; kapak `SABITLER["zone_ust"]/["zone_alt"]`: 1s 3+3 · 2s 3+3 · 4s 2+2 · 1g 1+1.
  Eşit mesafede **daha yeni `kaynak`** kazanır. Taraf: kutu merkezi kapanışın
  üstündeyse "üst".
- **Kalın kenar (§0.12r) çizimden değil veriden:** seçim turunda `vurgu = "alt"|"ust"`
  kayda yazılıyor, `_zone_ciz` yalnız okuyor (boğada alt kenar, ayıda üst kenar).
- **Motorlar çizim yolunda çağrılmaz.** `anlik_goruntu(..., sonuclar=...)` hazır
  sözlüğü okuyor; `run_domain_engines` çağıran tek yer `grafik_uret.py --zone`
  (CLI). Alan adı regresyonu, CLI'ı **alt süreçte** çalıştıran testle kapandı
  (`test_grafik_bolgeler.py::test_cli_zone_...`) — pytest sürecinde motor çağırmak
  `test_domain_incremental_parity.py` durumunu bozardı.
- **Etiket yerleşimi.** Kutu başına TEK yazı, sol kenarda: `OB↑ %70`, `FVG↑ q95`.
  Çakışan yazı atlanır ve `meta["zone"]["etiket_atlandi"]` sayılır (kutunun kendisi,
  dolgusu, kalın kenarı çizili kalır → bilgi gizlenmez). Geometri `ax.get_position()`
  × figür pikselinden; `transData` çizim turundan önce güvenilmez (ölçüm: 2,8 birimlik
  fiyat farkı 6 px çıktı, tüm etiketler çakışık sayıldı). Ölçü alınamazsa filtre
  kapatılır ve hepsi yazılır (yanlış eleme > üst üste binme).
- **`meta["zone"]` biçimi sabit:** bölge yokken de aynı anahtar seti döner
  (`sirala: "zone verisi yok"`) — §13 JSONL okuyucusu dalgalanmasın.
- **Sağ nefes payı:** bölge çizildiğinde x-ekseni `n-0.4+6` bar; son mumun
  kesilmediği `meta["kare"]["x_siniri"]` ile test ediliyor (§0.13).

### 23.3 Ölçüm (gerçek önbellek + gerçek motor)

| kare | çizilen | elenen | etiket atlandı | PNG | süre |
|---|---|---|---|---|---|
| AKBNK 4s · 110 mum | 4 | 9 | 2 | 59,7 KB | ~410 ms |
| AKBNK 1s · 180 mum | 5 (`tip.fvg = 0`) | 0 | 0 | ~63 KB | ~490 ms |
| THYAO 4s · 110 | 4 | 13 | 2 | 58 KB | — |
| GARAN 4s · 110 | 4 | 4 | 1 | 69,3 KB | — |

Doluluk: 4s AKBNK'ta 4 kutudan 1'i `%70` (`doluluk=0,6957`) aldı, diğerleri `—`
(motor vermedi) → §0.12k beklendiği gibi. Kapak nedeniyle atılanlar dipnotta sayı
olarak görülüyor (`bölge: 9 kutu kapak dışında (üst 2 · alt 2)`).
Tam kapı: `942 passed, 44 skipped in 136 s`.

### 23.4 Belgede/kodda düzeltilenler

- YAPILACAKLAR'daki G1 test sayısı **23 değil 25**ti; G2 sonrası **26** (CLI
  `--veri-dizin` testi eklendi).
- `grafik_uret.py::_veri_dizini()` `sekenek` yazıyordu → `--veri-dizin` verildiğinde
  `NameError` (G1'de test edilmemiş yoldu). Düzeltildi + regresyon testi yazıldı.
- Havuz sıralaması `mesafe` **azalan** tutulmuştu → kapaklar en UZAK kutuları
  tutuyordu; `mesafeler == sorted(mesafeler)` iddiası yakaladı. Düzeltildi.
- `SABITLER["doldurma"]` hem §17.6 adlarını (`golge`, `golge_ince`) hem katman
  adlarını (`ob`, `fvg`, `eng`, `ince`) taşıyor; aynı değerler — §17.6 izlenebilirliği
  için bilinçli tekrar.

### 23.5 G3'e devir (ölçülmüş alan adları)

`ms.details` (AKBNK/1s ölçümü): `external_swings` (48) · `internal_swings` (77) ·
`external_candidates` (2) · `internal_candidates` (2) · `event_history` (98) ·
`latest_external_event` · `latest_internal_event` · `external_context` ·
`internal_context`.
`SwingPoint(valid, identity, scope, side HIGH|LOW, state, swing_class, structural_role,
source_bar, confirm_bar, price, atr_at_source, prominence_atr, distance_atr,
distance_pct, previous_same_side_identity, previous_opposite_identity, finalized,
locked, broken, broken_bar, quality, evidence_text, invalid_reason)`;
`MarketStructureEventRecord(event_uid, identity, scope, event_type EVENT_CHOCH|
EVENT_SWEEP, direction, candidate_bar, event_bar, candidate_at, confirmed_at,
broken_swing_identity, broken_source_bar, broken_source_at, broken_level, origin_*,
quality, evidence_text, confirmation_status, validity, relevance, outcome, age_bars,
confirmation_high/low/close, bos_maturity)`.
G3 işleri: `kritik` çizgisi `broken_level`/`origin_level`dan; `!` yalnız son 15 mum;
`evidence_text` yalnız `--etiket-detay`; `rvol(20)` kulvarı `vp.export`tan ve 4s için
`yerel hesap` etiketiyle; yapı etiketleri **aynı çakışma filtresiyle** yazılacak.

---

## 24 · G3 UYGULANDI (2026-10-13) — yapı (swing/BOS/CHoCH/kritik) + katılım şeridi

### 24.1 Motor gerçeği (ölçüldü — `run_domain_engines`, AKBNK 1s/4s, `Dengeli`)

- **Şerit.** `vp.details["metrics_history"]` **bar bar** seri (1s: 360/360 dolu):
  `VolumeParticipationMetrics(data_ready, rvol, volume_z_score, volume_percent_rank,
  volume_level, effort_result_class, ...)`. 4s ölçümü: `data_ready=False`,
  export `rvol=None`, `state=PARTICIPATION_PENDING` → motor serisi YOK.
  `effort_result_class` dağılımı (AKBNK/1s, 360 bar): `NEUTRAL` 337 ·
  `HIGH_EFFORT_STRONG_RESULT` 11 · `RISING_EFFORT_STRONG_RESULT` 10 ·
  `HIGH_EFFORT_WEAK_RESULT` 1 · `VERY_HIGH_EFFORT_WEAK_RESULT` 1 → `!` zaten
  seyrek bir işaret (§0.12a), son 15 bar filtresiyle çoğu karede 0 olur.
- **Yapı.** `ms.details`: `external_swings` (1s 48 · 4s 8), `external_candidates` (2/2),
  `event_history` (1s 98 · 4s 37). Swing: `side HIGH|LOW`, `state SWING_CONFIRMED|
  SWING_BROKEN`, `swing_class PH|PL|HH|HL|LH|LL`, `structural_role`, `source_bar`,
  `confirm_bar`, `price`, `prominence_atr`, `finalized/locked/broken`, `quality`.
  Olay: `scope EXTERNAL|INTERNAL`, `event_type EVENT_BOS|EVENT_CHOCH|EVENT_SWEEP|
  EVENT_FALSE_BREAK|EVENT_TRANSITION_FAIL`, `confirmation_status CONFIRMED|
  CANDIDATE_FAILED`, `validity VALID|FAILED`, `relevance CURRENT|SUPERSEDED`,
  `outcome PENDING|OBSERVED`, `event_bar`, `broken_level`, `age_bars`, `quality`.
  4s olay dağılımı: BOS 7 · CHoCH 3 · SWEEP 21 · FALSE_BREAK 4 · TRANSITION_FAIL 1
  → kart yalnız BOS/CHoCH gösterdiği için Süpürge/FALSE_BREAK kareye GİRMEZ.

### 24.2 Uygulanan kararlar (ilk kez burada yazılı)

- **Şerit kaynağı:** motor serisi `data_ready` barlarda varsa `kaynak="motor"`,
  yoksa `hacim / SMA(hacim, 20)` (`hacim_uzunluk=20`) ve `kaynak="yerel hesap"`.
  `▲` **yalnız motor serisinde** (`volume_level ∈ {HIGH, ABNORMAL}`) — yerel
  hesapla percentile iddiası yok. `minimum_history=150` düşürülmedi (§2.1).
- **`yerel hesap` etiketinin ölçütü** (kullanıcı kuralı `state` yokken, tur 9):
  `state` tek başına yanıltıyor — 4s motorunda `state=PARTICIPATION_PENDING`
  **var** ama `rvol` yok. Ölçüt „değerler yerel mi” olarak alındı; etiket o
  durumda yazılıyor, motor serisi gelince „· motor”a düşüyor.
- **Spike bütçesi:** `≥ serit_esik (1,5)` içinden en sert `serit_maks (12)` çubuk;
  gerisi `meta["serit"]["elenen_spike"]`ta sayılır (dipnot DEĞİL — bu bir
  gösterim limiti, veri kusuru değil). Şeritte TEK sayı: en sert spike`ın
  `×2,9` çarpanı (§17.3).
- **Yapı filtreleri:** swing = `external_swings` + `external_candidates`
  (aday → α 0,45; `SWING_BROKEN`/`broken` → „kırık” α 0,2 ve YAZISIZ), olay =
  `scope==EXTERNAL` ∧ `event_type ∈ {BOS, CHOCH}` ∧ `CONFIRMED` ∧ `VALID`,
  en yeni `olay_maks=6` · swing `swing_maks=10`. Kapak **en yakınları değil en
  yenileri** tutar (yapı zamanla ilerler; §0.8’deki yakınlık kuralı bölge
  kutularına ait).
- **`kritik` çizgisi = son seçilen olayın `broken_level`ı.** O olayın kendi
  kesikli çizgisiyle AYNI seviyede olduğu için ikinci bir çizgi ÇİZİLMEZ:
  eşleşen olayın çizgisi kalınlaşır (1,4 px) ve etiketi `CHoCH↓ · kritik 67,20`
  olur. Ayrı çizgi yalnız olay çizgisi çizilemediğinde devreye girer; alarm
  seviyesiyle birebir aynıysa o zaman da atlanır (`kritik_atlandi=1`).
  `cizgiler["kritik"]` §2 sözleşmesi gibi yalnız ÇİZİLDİYSE sayı taşır.
- **`_ALT_ADIM = 0,0235`** tek satır adımı: lejant çok satıra düştüğünde gri
  dipnot lejantın üstüne biniyordu (ölçüm: lejant adımı 0,0215 ile rezerv
  0,0235 uyuşmuyordu) → gri/kırmızı blok artık lejant bloğunun ALTINDA başlıyor.
- **Alan adları:** swing/olay `bar`ı ÇİZİM (görünüm) indeksi, `kaynak_bar`ı
  çerçeve indeksi; `meta["olay"]["olay_barlari"]` kart↔kare hizasını denetler.
  §23.5’te yazdığım `origin_level` alanı YOK — gerçek ad `origin_price` (düzeltme).
- **Pencere:** `[sol, sag)` — `sag` kadrajın sağ ucu; `source_bar == sag` olan
  swing çizilmez (testte ölçüldü: `sol=59, sag=239`).

### 24.3 Ölçüm (gerçek önbellek + gerçek motor, `--zone`)

| kare | katmanlar | PNG | süre |
|---|---|---|---|
| AKBNK 4s · 110 (yalnız yapı+şerit+bölge) | 8 swing · 3 olay · 12 spike | 72,3 KB | 452 ms |
| AKBNK 4s · 110 + bant + alarm (tam yığın) | + 28 temas (24’e indirildi) · bölge 4/9 | 96,4 KB | 507 ms |
| AKBNK 1s · 180 | 5 OB kutusu, şerit `motor` | ~63 KB | ~490 ms |

Kritik eşik: tam yığın kare bile 500 KB tavanının beşte biri (§6.3 kapandı).
Etiket çakışması: `etiket_atlandi` 0 (bantlı karede 1) — G2’deki 2 değerinden
iyi, çünkü `kritik` yazısı olay etiketiyle birleşti.
Tam kapı: `960 passed, 44 skipped in 143 s` (`test_grafik_yapi.py` 18 test).

### 24.4 G4’e devir

- Köprü: `payload["grafik_verisi"]` → `anlik_goruntu(cift, tf, cerceve, sonuclar=...)`
  (motorlar tarama sürecinde ÇAĞRILI, kare yalnız kopyayı okur — §14.2).
- `transport/telegram.py:foto_gonder` + `notifier._gonder` kuyruğu; 1 olay = 1 mesaj
  kuralı metinde değişmez, görsel sonra eklenir; `--tum-tf` sıralı 4 `sendPhoto`.
- 4 env anahtarı + `.env.example` + `deploy_check.py:489`; `GRAFIK_OLAY_MAKS` gibi
  kapak sayıları `SABITLER`den okunuyor, env’e çıkmadı (§5’ten farklı: v1’de 4
  anahtar dışındaki her şey sabit).
- `evidence_text` kareye yalnız `--etiket-detay` ile yazılıyor (varsayılan kapalı) —
  G4’te kart metninin tekrarı olmamasına dikkat.

## 25 · G4 UYGULANDI (2026-10-14) — teslim: köprü, kuyruk, `sendPhoto`, `/grafik`

Kullanıcı onayı (bu turun başında, 4 soru): **kareler tarama turu sonunda** gider
(metin bekletilmez) · **görsel kotası = yalnız `TELEGRAM_GRAFIK_ADET`** (ayrı
günlük/saatlik tavan YOK) · **kareler YALNIZ DM** (public/kanal metinde kalır) ·
**`/grafik` önbellekteki her sembolü çizer** (canlı çekme yok, ek hız sınırı yok).

### 25.1 Yüzeyler (tek kod yolu)

- `transport/telegram.py::foto_gonder(yol, *, chat_id/token/notifier, caption, api)`
  → `sendPhoto` multipart; dosya yoksa `"png yok"`, token/chat_id yoksa
  `"token/chat_id yok"`, ağ hatası `“istek hatasi: <tür>”` olarak YUTULUR. Test
  enjeksiyon noktası `_multipart_cagri` (`api_cagri` JSON gönderdiği için görselde
  kullanılamaz — §4’te belirtilen ayrım).
- `notifier.grafik_kuyruga_ekle(data)` → `_gonder`’in BAŞARI dalından çağrılır
  (metin 200 aldıktan sonra); `grafikleri_gonder(sinir=None)` tur sonunda boşaltır;
  `grafik_dosya_gonder(yol, caption)` aynı gönderimi `/grafik` için anında yapar ve
  dosyayı HER YOLDA siler. Sayaçlar: `grafik_gonderilen`, `grafik_atlanan_hata`,
  `grafik_atlanan_kota`, `grafik_kare_sayisi/toplam_ms` → `gonderim_durumu()`
  (`grafik_ort_ms`) → `/durum`’da TEK satır (`🖼 Grafik karesi: …`): şalter açıkken
  sayaçlar sıfır olsa da görünür; kapalı + sıfırda gizlenir, geçmiş/bugünkü aktivite
  varsa `(şalter kapalı)` önekiyle gösterilir (§28).
- `main.py::_grafik_koprusu(payload, outputs)` — `anlik_goruntu`yu tarama anında
  çağırır, `payload['grafik_verisi']`nın içine koyar; `_grafikleri_tur_sonunda`
  public bülteniyle aynı yerde flush eder ve `daily_stats['grafik_kare/‍hata']`nı
  besler. Motor burada ÇAĞRILMAZ: `outputs` zaten `_domain_results_for_notification`
  çıktısı (§14.2).
- `/grafik <SEM> [1s|2s|4s|1g]` — `TELEGRAM_KOMUTLARI` + `KOMUT_YARDIM` + `/durum`
  komut satırı + `deploy_check` “Komutlar açık” satırı (dört yüzey birden); sembol
  desene uymazsa reddeder, önbellekte yoksa “veri yok” der (canlı çekmez). CLI ve
  komut AYNI `grafik_uret.kare_uret()`i çağırır (`cerceve_getir` `VeriYok` kaldırır;
  CLI onu `SystemExit`e çevirir) — iki yüzeyin ayrışmaması için.
- Config: §5’teki 4 anahtar `config.py`de (varsayılanlar `yok/4/180/6`),
  `.env.example`a ve `deploy_check` beklenti tablosuna yazıldı; `TELEGRAM_GRAFIK`
  açıksa `deploy_check` matplotlib/`grafik` katmanını da yokluyor (kurulu değilse
  FAIL + “kare alarmı engellemez, yalnız eksik gider” notu).

### 25.2 Dumanın yakaladığı DÖRT gerçek kusur (test + düzeltme)

1. **`sinir = len(kuyruk)`** → limit OLAY sayısını sayıyordu; tek olay iki kare
   taşıyınca ikincisi kuyrukta kalıyordu. Düzeltme: `sinir` KARE sayısıdır,
   `None` → sınırsız; aşan kısım kuyruğa geri yazılır.
2. **`sonuclar` biçimi** — tarama turu `{tf: çıktı}` taşıyor, `anlik_goruntu` ise
   TEK TF’nin çıktısını bekliyor. Birincil kare iç içe sözlüğü alınca bölge/yapı
   katmanları SESİZCE boş kaldı (kare çizildi, içinde hiçbir şey yoktu). Çözüm:
   `grafik._sonuc_sec()` iki biçimi de tanır; hiçbiri tutmazsa kare çizilir ama
   `uyarilar`a `“motor çıktıları tanınamadı”` satırı düşer (sessiz boş kare yok).
3. **Bant/alarm diğer TF’ye taşınıyordu** — `alarm_bar`/`start_bar` birincil
   çerçevenin MUM İNDEKSLERİDİR; 1s karesine konulunca 273 mumluk kadrajda
   “bant teması 266” gibi uydurma bir sayı ve yanlış yerlerde kesikli çizgiler
   üretiyordu. Düzeltme: `kare_listesi` formasyonu ve alarmı YALNIZ birincil
   kareye verir; diğer karelere `“bant/alarm diğer zaman dilimine ait: bu karede
   çizilmedi (§14.1)”` notu kalır (kadraj tavanı da kalkar: 273 → 180 mum,
   126,4 → 79,2 KB).
4. **Kart paritesi satırı bandın sağ kesikli kenarının ÜSTÜNE biniyordu** —
   yarı saydam zemin (`alpha 0,6`) çizgiyi metnin içine basıyordu; kutu opağa
   çevrildi (`alpha 0,95`, `pad 1,4`, `-3 pt`).

### 25.3 Ölçüm (gerçek önbellek + gerçek motor, `/tmp/g4_smoke.py`)

AKBNK, `TELEGRAM_GRAFIK=alarm`, sahte `foto_gonder`: 2 kare gönderildi ·
**4s · 120 mum · 99,1 KB** (bant + alarm + bölge + yapı + şerit) ve
**1s · 180 mum · 79,2 KB** (bant/alarm yok, kendi OB/şeridi var) ·
üretim ort **533 ms/kare**, flush toplamı **1,07 s** · `atlanan_hata 0`,
`atlanan_kota 0`, kuyruk gönderimden sonra boş, `/tmp`de kalan `fb_grafik_*`
dosyası YOK (gönderim sonrası siliniyor, açılışta `bayat_kareleri_supur()` TTL’i
aşanları topluyor — taze dosyaya dokunmaz, eşzamanlı ikinci kopya koruması).

### 25.4 Sözleşme notları (ilerde değiştirmeyecek olanlar)

- `grafik_verisi` BELLEK İÇİDİR: acil kuyruk kaydına yazılmadan önce
  `notifier._kuyruk_verisi()` ile silinir (`json.dump(..., default=str)` bir
  çerçeveyi okunamaz yığınına çevirirdi); `public_kuyruk` zaten alan beyaz
  listesiyle çalıştığı için sızmaz. Test: `test_kuyruk_jsonu_grafik_verisi_tasimaz`.
- `grafik_verisi` OLSA DA kart metni DEĞİŞMEZ (`test_kart_metni_grafik_verisi_ile_
  bayt_bayt_ayni`) ve `TELEGRAM_GRAFIK=yok` iken `matplotlib`/`grafik` HİÇ import
  edilmez (alt süreçte `sys.modules` kontrolü).
- Caption = `SEM · <tf_kısa> · <N> mum` (ÜÇ parça, kart jargonu/ondalık yok;
  `px/mum` ve `KB` karenin içinde ve `meta`da). Görsel METİN değildir: satır
  bütçesi/soft-wrap caption’a uygulanmaz (§6.7 — teste yazıldı).
- `grafik_uret.kare_uret()` `VeriYok`/çizim reddini `{"yol": None, "hata": …}`
  olarak döndürür; hata fırlatmaz — `/grafik` bunu mesaja çevirir, CLI çıkış kodu.
- §5’ten tek sapma: `GRAFIK_OLAY_MAKS` gerçekten env’den okunuyor (`_olay_verisi` →
  `_ortam_sayi`), `swing_maks` ise bilinçli olarak SABİT’te kaldı (5. anahtar
  uydurulmadı; sapma §24’te de notlu).

### 25.5 Kalanlar

- **v2:** `sendMediaGroup` + `reply_parameters` (ilk kare metni yanıtlar) — canlı
  Telegram’da dumanla doğrulanacak (§4); v1 sıralı `sendPhoto` ile çalışıyor.
- **canlı smoke:** `TELEGRAM_GRAFIK=alarm` ile gerçek bir alarmda uçtan uca deneme
  (token/DM bu ortamda yok); `deploy_check` grafik satırı bunu hazırlıyor.
- **G5 (opsiyonel):** ısı haritası ve §13 JSONL (yalnız kayıt, gönderimle ilgisiz).

---

## 26 · CANLIYA ÇIKIŞ DENETİMİ (2026-10-14) — G4'ten sonra uçtan uca gezinme

Kullanıcının isteği: *"akışı baştan sona izle, canlıya alınca nerede kırılıyor bul."*
Kod değişikliği İKİ yerle sınırlı (aşağıda); kalanı ölçüm, doküman ve kullanıcıda
kalacak işlerin listesi. v2 (`sendMediaGroup` + `reply_parameters`) bu turda da
açılmadı — canlı DM dumanı görilmeden dokunulmayacak (§4).

### 26.1 Ölçülen gerçek maliyet (bu depo, gerçek önbellek)

`python grafik_uret.py --hisse AKBNK --tum-tf --zone` → dört kare de çizildi:

| TF | mum | PNG | süre | kaynak |
|---|---|---|---|---|
| 1h | 180 | 78,1 KB | 568 ms | `bot_data/1s` |
| 2h | 180 | 75,8 KB | 301 ms | `resample(2h)` |
| 4h | 120 | 72,4 KB | 302 ms | `resample(4h)` |
| 1d | 40 | 52,0 KB | 134 ms | `resample(1d)` |

**4 kare ≈ 1,3 sn** (planlama 14 ms dahil) ve süreç tepesi **129 MB** (çizim
sırasında +52 MB). `grafik_aktif_mi()` `yok` iken taze süreçte `matplotlib`
modülü YÜKLENMİYOR (ölçüldü) → kapalıyken sıfır maliyet iddiası duruyor.
Kare başına 27-78 KB, §6.3'teki 500 KB tavanının hâlâ 6-19 katı altında → o kapı
açılmayacak. Not: `1d` kadrajı 40 mum (bu depo için yüzeysel, §18.6).

### 26.2 Denetimin bulduğu ve kapanan İKİ kusur

1. **Bağlam güncellemesi kareyi yeniden gönderiyordu** — aynı olayın kartı
   güncellenince (`_dm_bağlam_değişmedi` yolu) `_gonder` tekrar başarılı sayılıyor
   ve `grafik_kuyruga_ekle` AYNI kareyi (bazen 4 tanesini) ikinci kez kuyruğa
   alıyordu: aynı mumların bayat kopyası, kota israfı. Düzeltme: o bayrakta `0`
   döner; sayaç `grafik_atlanan_baglam` → `gonderim_durumu()` → `/durum`'daki
   `🖼` satırında `· N bağlam güncellemesi` (yalnız sıfır değilken). Test:
   `test_bağlam_güncellemesi_kare_getirmez`.
2. **`deploy_check`te grafik dumanı yoktu** — matplotlib kurulu mu diye BAKILIYORDU
   ama hiçbir kare ÜRETİLMİYORDU, yani canlıda "kare gitmiyor" sessiz kalırdı.
   Eklendi: `kontrol_grafik(...)` + `--grafik-test`; ağdan BAĞIMSIZ (çizim yerel),
   `--send-test-message` olmadan `sendPhoto`ya dokunmaz. Beklenen: `Grafik katmanı
   import edildi (matplotlib 3.11.x)` → `Kare üretildi: AKBNK 4h · 120 mum ·
   ~72 KB · ~300 ms` → `Fotoğraf gönderilmedi`. Sembole veri yoksa FAIL değil
   **WARN** (`veri yok: bot_data/….json okunamadı`) — ilk tarama öncesi normal.

### 26.3 Denetlenip TEMİZ çıkan yerler (neden güvenli — kayıt)

- **env**: `render.yaml` `envVars`ına 4 anahtar EKLENDİ (önce yoktu; blueprint'i
  olan serviste env'i Render dashboard yönetir, yani kullanıcı da elle ekleyecek).
- **build/kütüphane**: matplotlib 3.11.2 cp312 manylinux tekerleği var (kaynak
  derleme → Render build tuzağı yok). Sandbox 3.11.2, Render 3.12 — iki tarafa da
  tekerlek var. Sandbox'ta `numpy 1.26.4` + `matplotlib 3.11.2` birlikte kuruluyor
  (pinned setiyle test kapısı yeşil).
- **kota/huni**: görseller `max_gunluk`/`max_saatlik`i SAYMAZ; `grafik_kuyruga_ekle`
  yalnız metin 200 ALDIKTAN SONRA çağrılıyor → 1 olay = 1 mesaj bozulmadı.
- **acil kuyruk**: `_kuyruk_verisi()` `grafik_verisi`ni düşürdüğü için kuyruktan
  boşalan kartların karesi ÜRETİLMEZ (bilinçli: bayat kadraj çizmek yerine hiç
  çizmemek). `/durum`'da bundan doğan kayıp sayacı yok — kart zaten gitmiş oluyor.
- **grup/kanal**: `foto_gonder` yalnız `notifier.chat_id`yi (DM) kullanır; public
  bülten ve grup yollarına görsel kodu girmiyor.
- **disk**: `disk_uygun_mu()` < 200 MB → üretim wholly atlanır ve kuyruk
  `atlanan`da sayılır; yol `DATA_DIR` DIŞINDA `/tmp/fb_grafik_<SEM>_<tf>_<uid8>.png`,
  gönderimden sonra silinir, açılışta `bayat_kareleri_supur()` TTL'i aşanı toplar.
- **restart**: kare kuyruğu bellek içi → restart'ta kaybolur (kart gitmiştir, kopya
  doğmaz); `grafik_dosya_gonder` dosyayı HER yolda siler, `/tmp` süpürmesi de var.
- **komut çakışması**: tarama sürerken komutlar `tarama_suruyor` kapısına takılır;
  `/grafik`in 0,1-0,6 sn'lik çizimi komut thread'indedir, tarama temposuna
  dokunmaz, kota/hunyayı tüketmez.
- **TF kelime listesi**: tarama/kart `1h/2h/4h/1d`, kullanıcı görünümü `_TF_KISA`
  ile `1s/2s/4s/1g`; `kare_listesi`/`_sonuc_sec` YALNIZ kanonik adı tanır —
  `/grafik` iki yazımı da `_GRAFIK_TF` ile kanonikleştiriyor (görünür adı elle
  yazmak katmansız kare üretirdi; bu yüzden CLI/komut tek yerden geçiyor).
- **diskte kalıntı**: `--tum-tf` CLI çıktısı `/tmp/grafik_*.png` yazıyor (gönderim
  yolu değil, insan provası) — gönderim yolundaki dosyalar siliniyor.

### 26.4 Kullanıcıda kalanlar (kod tarafı bitti)

1. Render dashboard → 4 env anahtarı (`TELEGRAM_GRAFIK=alarm`, `..._ADET=1`,
   `GRAFIK_MUM_MAKS=180`, `GRAFIK_OLAY_MAKS=6`). Free planda ADET=1: 4 kare ~1,3 sn
   + ~52 MB tepe demek, çok alarmın olduğu turda tur uzar.
2. Supabase'i bağla (`SUPABASE_URL`/`ANON_KEY`): yoksa restart'ta günlük sayaçlar
   ve cooldown sıfırlanır (görselden bağımsız ama aynı denetimin parçası).
3. Canlı duman (runbook **4.7**): `python deploy_check.py --grafik-test
   --send-test-message` → DM'de `sendPhoto kabul edildi`; sonra gerçek bir alarmda
   "metin sonra kare" sırasını ve `/durum`'daki `🖼` satırını gözle doğrula.
4. **G5'e bırakılan**: v2 teslim biçimi (media group/reply), ısı haritası ve
   §13 JSONL. (Kartın yapı satırının kareye taşınması bu turda BİTTİ → §27.)

---

## 27 · KARTIN YAPI SATIRI KARENİN ÜSTÜNDE (2026-10-14) — §26.4'ün L11 maddesi

Kare ile kart arasındaki tek gerçek eksik buydu: kutu/markaj çiziliyor ama motorun
**durum cümlesi** (ör. `• 4s yapı: dış aşağı geçiş · iç aşağı geçiş`, `CHoCH ↓ 72,20 ·
iç · geçerli güncel`) yalnız mesajda vardı. Bu turda o satır karenin üst bloğuna
taşındı. (Not: OB doluluk yüzdesi §23'ten beri zaten kutu etiketinde — `%24 dolu`
kartta ne yazıyorsa karede de o; şerit ve `bant teması` paritesi §24/§25'te ölçüldü.)

### 27.1 Sözleşme: uydurma cümle yok, kartın biçimleyicisi çağrılıyor

- `grafik._yapı_satırı(sonuclar, tf, son_kapanis)` → `notification_context.domain_bolumleri(
  {tf: sonuclar}, son_kapanis, stil="klasik", alarm_tf=tf)["yapi"][0]`. Yani kare,
  **kartın kendi satırını** yazıyor; tek fark madde imi: baştaki `• ` düşürülür
  (karenin diğer satırları imsiz). Sayı, kelime, zaman dilimi adı (`4s`) kartla
  birebir aynı — teste de bu bağlandı (`test_gerçek_motorda_kart_satırı_karede_de_var`:
  çizilen satır, kart satırının `• ` önekiyle geri eklenmiş haliyle eşit).
- Motor yok / biçimleyici yok / istisna → `''` ve **dipnot yazılmaz** (§0.12w: yokluk
  veri kusuru değil; izi `meta["eksik_katmanlar"]`da `ms` olarak zaten var).
  Biçimlendirme hatası kareyi ASLA düşürmüyor (test: `Kırık` biçimleyiciyle bile
  `kareyi_yaz` yol üretiyor).
- `yalnızca_mumlar` kipi satırı çizmez (o kip hiçbir yorum satırı çizmiyor).

### 27.2 Yerleşim kuralı (ölçüldü)

Üst blok satırları `y = 1 − 0,032 − 0,040 − 0,031·i` ile iniyor; eksen tepesi
`ust = 0,855` sabitti, yani **3. satır eksene değiyordu** (y=0,866 → 9 pt'lik metin
0,851'e iniyor). Kural: `ust = 0,855 − 0,031 · max(0, satır_sayısı − 2)` — iki satır
ve altında **hiçbir şey değişmez** (bayt kararlılığı + geometri testleri yeşil), üç
satırda eksen 0,031 iner. Dördüncü satıra yer yok: yapı satırı SONDA eklenir ve
`len(satirlar) < 3` değilse çizilmez, `metin["kesilen"]`e yazılır (sessiz kayıp yok).
Sıra: `alarm:` → `formasyon · q · daralma · seviye` → `--etiket-detay` satırı →
yapı satırı.

### 27.3 Ölçüm

`grafik_uret.py --hisse AKBNK --tf 4h --zone --mum 120` → satır çizildi, `kesilen:[]`,
`dipnot:[]`; kare **72,4 → 75,0 KB** (+2,6 KB), süre 302 → ~555 ms (aynı koşuda
ilk ölçüm 302 ms: süreç ısınması; kare başına 0,3-0,6 s bandı §26.1'de duruyor).
Köprü biçiminde (`kare_listesi` + `_cift()` bandı, 3 satır dolu):
`['alarm: kapanışla teyitli kırılım', 'Simetrik Üçgen · q88 · daralma %42 · seviye 52,50',
'4s yapı: dış aşağı geçiş · iç aşağı geçiş']` · 85,8 KB · 1080×810 — görsel kontrol
yapıldı, `bant teması 93` yazısıyla çakışma yok. Ek ikincil kare kendi TF'sinin
satırını alıyor (`{tf: sonuclar}` çözümlemesi kare başına), yani birincil kartin
cümlesi diğer kareye taşınmıyor.

Test: `test_grafik_teslim.py` → 57 (4 yeni: biçimleyici paritesi, hata yutma,
kapasite, gerçek motor ×2 parametrizasyon). Kapı: §26 ile birlikte 1012 → bu turda
yeşil (aşağıda).

---

## 28 · GÖRSEL YOK TEŞHİSİ (2026-10-14)

Alarm metni ulaşıp kare ulaşmadığında `/durum` artık şalter durumunu, kareye
aday alarm sayısını ve kare üretme köprüsündeki kayıpları ayırır. Ana satır
şalter açıkken sıfırlarda da görünür:

`🖼 Grafik karesi: N alarm kartı · N kare gönderildi · N hata · kuyruk N · ort N ms`

Sıfır olmayan ekler: `N adet sınırda kesildi`, `N bağlam güncellemesi`,
`N karesiz (tarama anında şalter kapalı ya da köprü atladı)`,
`köprü hatası N · son neden: …`. Şalter kapalı ve tüm sayaçlar sıfırsa satır
yazılmaz; kapalıyken önceki görsel aktivitesi varsa `(şalter kapalı)` önekiyle
aynı sayaçlar görünür. `grafik_olay` yalnız şalter açıkken normal DM alarmı
başarıyla gönderildikten sonra sayılır; `grafik_olay_karesiz` bunun içinden
köprüden `grafik_verisi`/`goruntular` alamayanları gösterir. Görsel metin kotasına
girmez; mesaj metni ve `1 olay = 1 mesaj` sözleşmesi değişmez.

| Neden | Artık nasıl görünür / ne anlama gelir |
|---|---|
| **Şalter yok/kapalı** (`TELEGRAM_GRAFIK` tanımsız veya `yok`) | Otomatik alarm karesi bilinçli olarak üretilmez. Hiç görsel aktivitesi yoksa `/durum` satırı da yoktur; şalter açılmışken sıfırlar dâhil satır görünür. `/grafik` komutu bu şalterden bağımsızdır. |
| **Tarama anında kapalı** | Köprü `grafik_verisi` eklemeden döner. Gönderim anında şalter açıksa olay `N karesiz (tarama anında şalter kapalı ya da köprü atladı)` altında sayılır; şalter hâlâ kapalı ve sayaçlar sıfırsa satır gizlidir. Render env değişikliği restart gerektirir. |
| **Köprü istisnası** | Alarm yine gönderilir; `grafik_kopru_hata` artar, `grafik_son_neden` tür/mesaj/sembol/TF ile en fazla 120 karakter tutulur ve `/durum`'da görünür. İlk köprü hatası `WARNING` (Render `INFO` logunda görünür), sonrakiler `DEBUG` olur. Olay kare kuyruğuna ulaştıysa karesiz sayacı da artabilir. |
| **Acil kuyruk** | Diskteki acil kayıt `grafik_verisi` taşımaz; kuyruğu boşaltırken `_kuyruktan=True` işaretlenir ve bu kayıt olay/karesiz sayaçlarını şişirmez. Kareyi yeniden çizmek bilerek denenmez (kadraj bayat olur); `/durum`'daki aday hunisinin `N kuyruğa alındı` ve gönderim engeli sayaçları alarm yolunu gösterir. |
| **DM dışı hedef** | Görseller yalnız `TELEGRAM_CHAT_ID` özel sohbetine gönderilir; public grup/kanalda metin olması, orada kare de bekleneceği anlamına gelmez. Fotoğrafı kayıtlı DM'de kontrol et; grup için görsel sayaçları ayrı hedef sayılmaz. |
| **Bağlam güncellemesi** | `_dm_bağlam_değişmedi` olan kısa metin güncellemesi aynı olayın karelerini tekrar göndermez. `/durum`'da `N bağlam güncellemesi` görünür; bu karesiz köprü hatası değildir. |

### Canlı teşhis sırası

1. Render → **Shell**: `python deploy_check.py --grafik-test` — matplotlib ve
   yerel kare üretimini doğrula; bu test ağa çıkmadan çalışır.
2. Env gerekiyorsa mevcut `TELEGRAM_GRAFIK=alarm` değerini ayarla ve servisi
   **restart et** (env değişikliği çalışan sürece uygulanmaz; yeni anahtar yok).
3. Kayıtlı Telegram DM'sinde `/grafik SEM 4s` gönder — cache'ten kare üretimi ve
   doğrudan `sendPhoto` yolunu alarm şalterinden bağımsız test et.
4. Aynı DM'de `/durum` çalıştır — `alarm kartı`, `karesiz`, `köprü hatası · son
   neden`, kare gönderimi ve gerekiyorsa `(şalter kapalı)` önekini birlikte oku.

## 29 · GÖRSEL-2 TURU (2026-10-14) — şerit, kadraj, bant teması (sözleşme güncellemesi)

Bu tur §0.4.1, §0.12, §14–§17 ile çelişen veya onları somutlaştıran kararları kayda geçirir. Ayrıntılı ölçüm: `GRAFIK_YEREL_DOGRULAMA_RAPORU.md` §8.

### 29.1 Karar değişiklikleri (önceki sözleşmeye göre)

- **Etiket yerleşimi (§0.12-c, §2):** zone/olay/alarm/son-fiyat etiketleri veri alanında değil, sağ **fiyat şeridinde** (`sag_serit_px=150`). Ok uçları eksen kenarında (`x=n-0.4`); ok mum gövdesi/fitili üstünden geçmez.
- **Çakışma politikası:** çakışan etiket atılmaz, **dikeyde itilir**. Atılan etiket yalnız şerit dolduğunda olur ve `meta["sag"]["atlanan"]` ile görünür. Atlama sessiz değildir.
- **PH/PL basamaklama:** 14 px'de aynı yönlü etiketler bir satır basamaklanır (`_swing_ofseti`).
- **Kadraj (§17 ölçek ile uyum):** kadraj = mum aralığı + bölge + formasyon + alarm + PH/PL uçları, %6 pay. Dışarıdaki BOS/CHoCH/kritik çizilmez ve `kadraj_disi` ile sayılır. Gerekçe: dışarıdaki seviye eksen aralığını genişleterek mumları küçültüyordu.
- **Kritik (§0.4.1 "kritik" yazımı):** `kritik X` ayrı şerit etiketi; CHoCH metninden ayrıldı (kesilme önlemi).
- **Son fiyat:** kesikli yatay çizgi + sağda etiket (son kapanış, veri tarihi başlıkta).
- **Bant teması (§0.4.1 "temas mumları" satırı güncellendi):** `o` işareti temasın olduğu banda yakın tarafın fitil ucunda; 24 işaret sınırı.
- **Başlık:** `bant teması N` ve alarm kapanış farkı (üstünde/altında).

### 29.2 §0.4.1 paleti için not

- Renkler değişmedi. Etiket rengi yalnız metin olarak tekrarlandı; kadraj dışı seviye çizilmediği için palette yeni katman yok.

### 29.3 Ölçülebilir kurallar (testler)

- `mum_cakisan == 0` gerçek önbellekte altı örnek karede (`test_grafik_gorsel_kalite.py`).
- Şerit etiketleri dikeyde üst üste binmez ve şerit yeterliyken atlanmaz.
- Bant teması işareti doğru fitil ucunda.
- Kadraj dışı seviye çizilmez ve sayılır (`test_grafik_yapi.py::test_kadraj_disi_seviye_cizilmez_ve_sayilir`).

### 29.4 Açık kalanlar

- Olay yoğunluğu (DOHOL 1s'de 7 etiket) için `GRAFIK_OLAY_MAKS` kararı ayrı tur; kullanıcı onayı beklenir.
- Veri 2026-09-25'te bitiyor; bu sözleşme yalnız çizimi kapsar, veri tazeliğini değil.
