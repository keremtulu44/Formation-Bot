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
| State metni | `notifier.py:667 PUBLIC_STATE_ETIKET`, `_bulleten_olay` `:1385`, `STATE_TR` | `KIRILIM_TEYITLI / RETEST_BASARILI / KIRILIM_GECERSIZLESTI` |

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
yeniden çizim (yok), renk paletinin renk-körlüğü kontrolü (G1'de bakılacak).

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
2. Alarm mumu sentetikti (son bar) → gerçek `cift` alanlarıyla hizalama testi
   G1'in ilk işi.
3. Zone sıralamasında ATR yerine mesafe/son-kapanış proxy'si kullanıldı →
   G2'de `gap_atr`/motor ATR'siyle yazılacak (proxy düşük volatiliteli hissede
   kutuları olduğundan yakın gösterir).
4. FVG `fill`/`gap_size` gölgesi hiç test edilmedi (G2).
5. Yarım seans/tatil (`exchange-calendars`) ve açık-bar paritesi (§14.3) ölçülmedi.
6. 1g ~500 bar kadrajı lokal simde yok → G1 `_gunluk.json` seed'i.
7. Albüm/reply/multipart denenmedi (G4 canlı smoke).
8. Çökme modunda `fill_between` PNG'yi 98 KB'a çıkardı → basamaklı çizgi
   denenecek; şerit kulvarı ile fiyat bölgesi 360 barda hafif çakışıyor.

## 20 · Kayıt/izleme borçları

- Bu dosya repoda tutulur; her fazın commit mesajı ilgili § numarasını anır.
- `YAPILACAKLAR.md`'ye G0-G5 maddeleri G1 commit'iyle eklenir.
- Spike çıktıları depo dışında (`~/grafik-spike/`) tutulur, commit edilmez.
