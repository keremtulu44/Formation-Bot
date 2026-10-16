# GRAFİK TASARIM SÖZLEŞMESİ (G0 → G5)

> **Tarih:** 2026-10-13 · **Dal:** `arena/953e9c1b-formation-bot` · **Dayanak:** 7 soru
> turu + iki öz-eleman turu; sayılar koddan ve ölçümden (her "≈" işaretlidir).
> **Bu dosya repoda yaşar.** Önceki sürüm depo dışında (`~/format-atolye/`)
> tutuluyordu; 2026-10-13 19:23'te sandbox yeniden kurulunca o klasör ve
> `.venv` silindi, doküman kayboldu, git geçmişi uzaktan (`e4b451a`) geri alındı.
> Kural: tasarım/ölçüm dokümanları depo içinde, ölçüm çıktıları (PNG vb.) depo dışında.
> Bu belge tarihli tasarım kararlarını ve uygulamayı taşır; güncel yapı scope'u §38, bölge/temas denetimi §39'dadır.

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
7. **Yapı kapsamları ayrıdır:** ▲/▼ swing okları internal swing'leri; PH/PL/WH/WL cetveli dış rol seviyelerini; BOS/CHoCH çizgileri external olayları gösterir (§38).
8. **Zone seçimi:** OB + FVG + engulfing tek havuzda; OB kaynağı varsa `active_records`,
   FVG/ENG kaynağı varsa lifecycle kayıtlarıdır. Aktif → aday → tamamlanmış sırası,
   yakınlık/ATR ve eşitlikte yeni `source_index` kuralıyla seçilir.
9. **Zone sayısı TF'ye göre:** `1s 3+3 · 2s 3+3 · 4s 2+2 · 1g 1+1` (üst/alt).
   4s'de yan başına en az iki slot varsa tamamlanmamış FVG/ENG için birer görünürlük
   payı ayrılır; kalan slotlar havuz yakınlığıyla doldurulur (§39).
10. **Engulfing kutuları** (mor kesikli) lifecycle `lower_boundary/upper_boundary`
    alanlarını kullanır; olay mumunun `formation_low/high` fitil aralığı kutu sınırı değildir.
11. **Alarm mumu:** gri kesikli düşey çizgi + state yazısı **başlık altında**
    (`alarm: kapanışla teyitli kırılım`), `STATE_TR`/`PUBLIC_STATE_ETIKET` metniyle.
12. **Kutu yazısı minimal:** kutu içinde `OB↑/FVG↑/ENG↑` + varsa `%doluluk`;
    qNN yoktur. Aday `?` ile, tamamlanan kayıt soluk kesikli konturla işaretlenir.
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

### 0.4.1 Kalıcı palet (koyu zemin `#0f151c`, metin/eksen `#e9eef5`)

**GÖRSEL-3 (2026-10-14):** yükselen mum YEŞİL, düşen mum KIRMIZI (neon değil:
iki ton da orta doygunlukta); mum dışı katmanlar nötr grid üstünde koyu **çip**
(panel) ile şeride yazılır. Renk tek başına bilgi taşımaz — doluluk farkı,
işaret ve yazı ikinci kanaldır.

| Katman | Renk | Çizim |
|---|---|---|
| Mum (yükselen) | `#31b184` kenar + `#134237` dolgu | içi BOŞ gövde (koyu yeşil dolgu) + yeşil fitil |
| Mum (düşen) | `#e05c58` | DOLU gövde + kırmızı fitil |
| Order Block | `#2bb673` | %9 dolgu (kutunun yüksekliği görünür aralığın %18'ini aşarsa 0,04'e iner §17.6) + `source_index`'te kalın kenar (1,3 pt, GÖRSEL-4) |
| FVG | `#3f9dec` | %8 dolgu (TARAMA YOK, GÖRSEL-4) + `formation_index`'te kalın kenar |
| Engulfing | `#a78bfa` | kesikli kontur |
| Formasyon çizgileri | `#e0b96a` | 1,6 pt; bant arası α.06 dolgu; son muma kadar projeksiyon; `apex`'te `x` |
| Bant temasları | — | temas sayısı/metadata korunur; mum üstü daire işareti çizilmez (§39) |
| İç ▲/▼ swing + HH/HL/LH/LL | `#8ba0b4` / `#9fb0c0` | aday α.45 / teyitli tam / kırık α.2; oklar `internal_swings` kaynağından |
| Dış PH/PL/WH/WL | `#8ba0b4` | aktif rol seviyesi, ince noktalı yatay kılavuz + sağ cetvel çipi |
| BOS/CHoCH | `#f0885c` | ok + kesikli seviye çizgisi + `BOS↑/CHoCH↓` |
| Katılım şeridi (yükselen spike) | `#2f9e8a` | §2.1; spike MUMUN yönünde renklenir |
| Katılım şeridi (düşen spike) | `#cf5f5f` | §2.1 |
| İhlal / `!` | `#ef5350` | `!` (çaba var-sonuç yok, son 15 mum) ve ihlal işaretleri |
| Izgara | `#212c39` | yalnız yatay, kesikli (§17.7 kalabalığı) |
| Sağ şerit paneli | `#151d27` / kenar `#243040` | etiket çipleri: `#111922` dolgu + katman renginde kenar/yazı |
| Son fiyat çipi | dolu çip | renk SON MUMUN yönünden (yeşil/kırmızı), koyu yazı, kalın |

Kare zemini `#0f151c`, şerit kulvarı `#151d27` (panel); ikisini `#243040` ince
çizgi ayırır. Başlık bloğunun altında `#243040` yatay ayraç vardır.

Renk tek başına bilgi taşımaz: her bölge/katman bir de **yazı** taşır.

### 0.12a–aa · Sonraki turların kararları (özet)

- **a** Alarm barı: gri düşey çizgi + `TEYIT/RETEST/…` yerine **gerçek state metni** (z).
- **b** 180 bar tavanı formasyon eskiyse kalkar; `genişlik = bar × 6 px`,
  taban 1080 / tavan 1440, çökme modu yedek.
- **c** Bölge kutusu yazısı minimal (12) — **GÖRSEL-4:** yazı artık kutunun İÇİNDE; sığmazsa sağ şeride yedeklenir (§32).
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
| Market structure | `output["market_structure"].details` + `export` | Oklar: `internal_swings`/`internal_candidates`; seviye cetveli: `export.external_protected_*`/`external_weak_*` (rol kaydı `external_swings`); BOS/CHoCH: `event_history` (`scope=EXTERNAL`, onaylı/geçerli), `broken_level`, `event_bar` |
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
projeksiyon, `start/end/apex`, bant temas sayısı (mum üstü daire yok; §39), alarm
çizgisi + state metni, başlık/`son kapanan`, lejant, dipnot, çökme modu, `meta`. `eksik_katmanlar`
ve `budama` satırları bu fazda.

**G2 — zone'lar:** OB kutuları (aktif liste, yakınlık cap'i, `source_index` kalın
kenar), FVG/engulfing lifecycle geometrisi ve durumu, motorun verdiği doluluk.
Ham formation listeleri yalnız eski/harici sonuç şekillerinde fallback'tir; çizim
kaynağı/indeks eşleşmesi, tekrarlar ve durum çizgileri §39'da denetlenir.

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
2. **Tarihsel ikinci budama kuralı:** `temas_isaret_maks = 24` — o sürümde bant
   temasları daireyle işaretleniyor, en yeni 24'e kırpılıyordu. Bu çizim katmanı ve
   budama kuralı **§39'da kaldırıldı**; temas hesabı/sayısı korunur, daire çizilmez.
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
- **Sağ nefes payı** *(bu madde GÖRSEL-2'den beri geçerli değil: etiketler sağ şeride
  taşındı, pay `0` kaldı; sağ boşluk §37'de yeniden tanımlandı)*: bölge çizildiğinde
  x-ekseni `n-0.4+6` bar; son mumun kesilmediği `meta["kare"]["x_siniri"]` ile test
  ediliyor (§0.13).

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
  bütçesi/soft-wrap caption’a uygulanmaz (§6.7 — teste yazıldı). **§40.1 FAZ 1
  güncellemesi:** kareden çıkarılan veri dipnotları (`veri: N bar hacimsiz`,
  `bölge: N kutu kapak dışında`, `eksik: …`) caption’ın İKİNCİ satırına eklenir
  (`ℹ️ …`, ≤200 karakter, `notifier._grafik_dipnotu`); kimlik satırı üç parça kalır.
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

- Bu turda renkler değişmedi (görsel-2). Etiket rengi yalnız metin olarak tekrarlandı; kadraj dışı seviye çizilmediği için palette yeni katman yok.
- **Sonradan (görsel-3, §31) değişti:** monokrom mum paleti yerine yeşil/kırmızı mum şeması geldi; buradaki eski `#e3e6e8`/`#8d949a` değerleri geçersizdir.

### 29.3 Ölçülebilir kurallar (testler)

- `mum_cakisan == 0` gerçek önbellekte altı örnek karede (`test_grafik_gorsel_kalite.py`).
- Şerit etiketleri dikeyde üst üste binmez ve şerit yeterliyken atlanmaz.
- Bant teması işareti doğru fitil ucunda.
- Kadraj dışı seviye çizilmez ve sayılır (`test_grafik_yapi.py::test_kadraj_disi_seviye_cizilmez_ve_sayilir`).

### 29.4 Açık kalanlar

- Olay yoğunluğu (DOHOL 1s'de 7 etiket) için `GRAFIK_OLAY_MAKS` kararı ayrı tur; kullanıcı onayı beklenir.
- Veri 2026-09-25'te bitiyor; bu sözleşme yalnız çizimi kapsar, veri tazeliğini değil.

## 30 · TESLİM: ALBÜM + ALARM DURUMU (2026-10-14) — §4'ün "sendMediaGroup v2" maddesi kapandı

- **Karar:** `/grafik HİSSE` ve alarm karelerinin tamamı tek **albüm** (`sendMediaGroup`) olarak gider. Tek kare → `sendPhoto`. Albüm reddedilirse kareler tek tek yeniden denenir (kare kaybı yok).
- **Araya metin yok:** başarıda ayrı "✅ Bitti" metni kaldırıldı; kabul metni (`⏳ isteği alındı`) ve yalnız gerçek başarısızlıkta özet metin kalır. Üretilemeyen TF'ler albümün ilk altyazısına `⚠` satırı olarak yazılır.
- **Altyazı:** `HİSSE · 1s · 180 mum · son kapanan 25.09.2026 17:30` (ISO tarih ve yerel dosya yolu kullanıcıya gösterilmez).
- **Formasyon uyarısı kaldırıldı:** `/grafik` formasyon dosyası istemez; "formasyon verisi verilmedi" satırı kullanıcıya hata gibi görünüyordu. Formasyon bulunamayınca açık neden yalnız `--formasyon-tara` yolunda yazılır.
- **Alarm:** alarm kareleri olay başına tek albüm. Kill-switch `TELEGRAM_GRAFIK=yok` (varsayılan, `config.py`, `render.yaml`, `.env.example`) iken alarm görseli üretilmez; yalnız `alarm` iken çalışır.
- **Test kapsamı:** `test_grafik_album.py` (9 test), `test_grafik_teslim.py` ve `test_grafik_istegi.py` yeni sözleşmeye çevrildi.

## 31 · GÖRSEL-3 TURU (2026-10-14) — mum renkleri, çipler, kalabalık denetimi

Kullanıcı geri bildirimi: "artan mumları yeşil, düşen kırmızı yapıp neon yapmamalıyız;
diğer katmanlar çok nötr kalmış; sağdaki yazılar alakasız olabiliyor; görselliği
güçlendir". Bu tur yalnız ÇİZİM katmanını değiştirir: kadraj, veri sözleşmesi,
motor çağrısı ve sayı biçimi aynı kalır (§14.2/§15).

### 31.1 Karar değişiklikleri

- **Mum rengi (§0.4.1 tablosu güncellendi):** yükselen `#31b184` + içi BOŞ
  (koyu yeşil `#134237` dolgu), düşen `#e05c58` + DOLU. Eski monokrom palet
  (`#e3e6e8` boş / `#8d949a` dolu) kalktı; doluluk farkı renk körlüğünde ikinci
  kanaldır ve lejantta yazılır (`yeşil boş = yükselen · kırmızı dolu = düşen`).
- **Son fiyat çizgisi ve çipi** son mumun yönünde renklenir (eskiden her zaman
  yükselen rengindeydi → düşen kapanışta yanlış ima).
- **Katılım şeridi spike'ları** mumun yönünde renklenir (`#2f9e8a` / `#cf5f5f`);
  `1×` referans çizgisi etiketsiz, `1,5×` eşiği etiketli (kulvar içinde, solda).
- **Formasyon bandı** `#e0b96a` (sıcak kum) + bant arası α.06 dolgu; bant
  teması işaretleri `#f0d9a8`. Gerekçe: beyaz/somon mum katmanından ayrışsın,
  ama kutu katmanlarının yeşil/mavi/mor kodlarıyla karışmasın.
- **Sağ şerit paneli** (`#151d27`, kenar `#243040`): etiketler koyu çip içinde
  (`#111922` dolgu + katman renginde kenar/yazı); kutu etiketleri kutunun sağ
  kenarından çıkan ince kesikli KILAVUZ çizgisiyle bağlanır ve "son fiyata en
  yakın 3 kutu" ile sınırlanır → yazı ile kutu arasındaki ilişki görünür, liste
  alakasız görünmez. Şerit kulvarı `#151d27` panel zeminli, iki kulvarı ince
  çizgi ayırır.
- **Şerit kalabalık denetimi (`sag_etiket_maks`):** kaynak başına azami etiket
  zone 3 · olay 3 · alarm 1; seçim = öncelik (son > alarm > kritik > yapı >
  kutu) → son kapanışa yakınlık → yenilik. Elenen adaylar silinmez:
  `meta["sag"]["eledi_kaynak"]`ta sayılır (sessiz kayıp yok). Ölçüm: GARAN 1s
  karesi 13 etiketten 7'ye indi.
- **Başlık ayracı:** başlık bloğunun altında `#243040` ince yatay çizgi.
- **Izgara** bir ton açıldı (`#212c39`) ve zemin `#0f151c` oldu; kutu dolguları
  seyrekleşti (OB .14→.09, FVG .12→.08) — mumlar öne çıksın.
- **Çökme modu (px/bar < 5)** çizgisi NÖTR (`#e9eef5`): bu modda yön bilgisi
  mumdan gelmediği için renk yön ima etmez.

### 31.2 Önce/sonra kanıtı

`docs/ornek_kare_gorsel4.png` — aynı veri (GARAN 4s, 140 mum, `--zone`): üstte
görsel-3 (taramalı kutular + şerit etiketleri), altta görsel-4 (sade kutular +
kutu içi yazı, BOS/CHoCH grafikte). Kare, `git archive HEAD` ile alınan eski
ağaçta `grafik_uret.py` çalıştırılarak üretildi (yeniden çizim değil, gerçek
eski çıktı); görsel-3 turunun ayrı kanıt dosyası bu turda bu tek dosyada
birleştirildi.

### 31.3 Ölçülebilir kurallar (testler)

- `test_grafik_gorsel_kalite.py`: yükselen yeşil+boş / düşen kırmızı+dolu; iki
  ton da orta doygunlukta (neon tavanı: kanal max ≤ 240, doygunluk 0,35–0,8);
  son fiyat çipi mumun yönünde; şerit spike rengi mumun yönünden; lejant renk
  şemasını yazar; kaynak başına etiket sınırı ve `eledi_kaynak` sayımı.
- `mum_cakisan == 0` kapısı korunur (çipler/kılavuzlar yazı–mum çakışması
  üretmez: `_mum_cakisma_say` çip kutularını da kapsar).

### 31.4 Açık kalanlar

- `GRAFIK_OLAY_MAKS` (§29.4) hâlâ kullanıcı onayı bekliyor; görsel-3 şerit
  tarafını `sag_etiket_maks` ile sınırladı, çizgi tarafına dokunmadı.

## 32 · GÖRSEL-4 TURU (2026-10-15) — kutu içi yazı, olay etiketi grafikte, geçersizleşme akışı

Kullanıcı geri bildirimi ve kararları (birebir):
  1. "FBG tarafında bir problem vardı… doldurulan yerleri değişik bir çizim alıyordu"
  2. "sağ taraftaki yazılar bazen saçma oluyor"
  3. "önce metin geliyor, 4-5 metin sonra görseller; bir metin → görsel → metin olmalı"
  4. "formasyon geçersizleştiğinde tüm domainlerden bahsedilmesin, sadece formasyon
     infosu gelsin; görsel de sadece geçersizleşen timeframede gelecek"
  5. "OB/FVG için dikdörtgenin İÇİNE yazabiliyor muyuz… BOS/CHoCH için fiyat değil
     mum konumu önemli; PH/PL/korunan seviyeler için fiyat önemli"

### 32.1 Karar değişiklikleri

- **Kutu çizimi sadeleşti:** eğik tarama (hatch) KALKTI (büyük FVG kutularında
  "değişik doldurulmuş alan" görüntüsünün kaynağıydı), vurgu kenarı 2,0 → 1,3 pt.
- **Etiket KUTUNUN İÇİNDE:** `OB↓ %70` / `FVG↑ q95` yazısı kutunun ortasına
  yazılır (koyu kontur ile). Sığmazsa (ince/dar kutu) sağ şeride YEDEKLENİR —
  hiçbir etiket sessizce düşmez. Ölçüm: `meta["zone"]["etiket_ic"/"etiket_serit"]`.
- **BOS/CHoCH etiketi şeritten GRAFİĞE taşındı:** kullanıcı kararı gereği bu
  etiketler olayın MUMUNA ilişir (yukarı kırılımda seviyenin altına, aşağıda
  üstüne; çakışırsa basamaklanır). Fiyat şeridinde artık yalnız `kritik X`,
  alarm ve son fiyat kalır → "saçma/çift" görünen dublike etiket kaynağı kapandı.
- **PH/PL etiketlerine FİYAT eklendi** (`PH 290,50` / `PL 282,50`): korunan uçlar
  için seviye karar verici. İç yapı etiketleri (`HH/HL/LH/LL`) kısa kalır.
- **Metin → hemen o olayın görselleri (teslim akışı):** `_gonder` metni yazdıktan
  sonra kare kuyruğu ARKA PLAN işçisiyle boşaltılır (`notifier._grafik_gonderim_*`);
  tarama bekletilmez, olay sırası korunur (`metin₁ → görsel₁ → metin₂ → görsel₂`).
  Tur sonu boşaltma yedek olarak kalır (kuyruk zaten boşsa hiçbir şey yapmaz).
- **Geçersizleşme (`KIRILIM_GECERSIZLESTI`) kartı:** `domain_bolumleri(...,
  yalniz_tf=True)` — yalnız geçersizleşen TF'nin yapı/bölge/hacim satırları
  (ölçüm: 23 satır → 10 satır). `format_domain_context` de aynı bayrağı alır.
- **Geçersizleşme GÖRSELİ tek kare:** `kare_listesi` `alarm_turu="gecersiz"` iken
  `ek_cerceveler` yok sayılır (diğer TF karelerinde bant/alarm çizilmiyordu →
  neredeyse boş görseller gidiyordu).
- **Çakışma ölçümü iki kanallı:** bilinçli katman yazıları (`kutu-ici`, `olay-ici`)
  kapıdan muaf, ayrı sayılır (`meta["kalite"]["katman_cakisan"]`); şerit/başlık
  yazıları için `mum_cakisan == 0` kapısı aynen yürürlükte.
- **2 boyutlu yerleşim (ölçüm düzeltmesi):** katman yazıları mum kutusuyla
  çakışmasın diye aday konumlar GERÇEK `get_window_extent` ile ölçülür
  (`_olay_yazi_koy`, `_kutu_yazisi_koy`): çakışmasız ilk aday seçilir, hiçbiri boş
  değilse EN AZ çakışan korunur (yazı asla kaybolmaz). Ölçüm: 20 karede BOS/CHoCH
  çakışması 4 → 0; kutu içi yazı çakışması azaldı. Kutu içi adaylar kutunun
  DIŞINA çıkmaz; sığmıyorsa etiket yine sağ şeride gider.

### 32.2 Önce/sonra kanıtı

`docs/ornek_kare_gorsel4.png` (aynı dosya §31.2'de de anılır): üst satır GÖRSEL-3,
alt satır GÖRSEL-4. Fark: kutularda tarama yok, etiket kutunun İÇİNDE (`OB↑ %31`),
`BOS↑`/`CHoCH↓` etiketleri mumun yanında, `PH 290,50` fiyatlı.

### 32.3 Açık kalanlar

- Kutu içi yazı, kutu İNCE olduğunda hâlâ mumun üstüne binebiliyor (kutu alanı
  mumlarla dolu; adaylar kutunun içinde kalmak zorunda). Çakışan yazı sayısı
  `katman_cakisan`da görünür; istenirse sonraki turda "çakışıyorsa şeride" kuralı
  sertleştirilir (bugünkü davranış: etiket kutuda kalır, koyu kontur okunur kılar).
- `GRAFIK_OLAY_MAKS` (§29.4) hâlâ kullanıcı onayı bekliyor.

## 33 · GÖRSEL-5 TURU (2026-10-15) — doluluk cetveli, okunurluk, okuma modları

Tur, kullanıcının "daha iyi yapılabilir hissiyatı" sorusuna **ölçümle** cevap
verilerek açıldı (hiç kod değiştirmeden 15–20 kare tarandı):

| Ölçüm | Bulgu |
|---|---|
| Çizilen 56 kutu etiketi | 21'i `qNN`, 23'ü ÇIPLAK (`OB↑`), 12'si yüzde |
| Kutuların içine sığan etiket | 23/56 (%41) — gerisi sağ şerit yedeğinde |
| Olay çizgileri | kritik dışı BOS/CHoCH aynı stil + aynı alfa (ayırt edilemiyor) |
| Şerit çipleri | 3 kutu çipi + son fiyat aynı bantta yığılıyor (TCELL 4s) |

Kullanıcı kararları: (1) "hem cetvel hem %", (2) "`qNN` tamamen kaldır",
(3) "hepsi, bu sırayla" (üç paket).

### 33.1 Paket 1 — kutu bilgisi

- `qNN` KALDIRILDI (`_zone_metni`); etiket = tip + yön + (varsa) `%doluluk`.
- **Doluluk cetveli:** dolan kısım daha koyu bant + sınır çizgisi. Geometri
  MOTORUN dolgu yönüyle aynıdır ve koddan doğrulandı:
  OB `fill_ratio = (top - fill_boundary)/height` (boğa) → **üstten aşağı**;
  FVG `wick_fill_ratio = (upper - low)/gap` (boğa) → aynı kural; ayıda tersi.
  %2–%98 arası çizilir (uçlarda kutu zaten o hâli anlatıyor).
- **FVG %50 orta çizgisi** (consequent encroachment) yalnız ≥8 px yükseklikte.
- **Kutu künyesi** `16 Eyl` (OB `source_time` / FVG `formation_time`) ikinci satır;
  iki satır sığmazsa tek satıra düşer (`_kutu_yazisi_sigar` satır sayısını ölçer).
- Lejant yeni dili yalnız çizildiğinde yazar: `▨ dolan kısım`, `┈ %50 ortası`.
- `meta["zone"]`: `dolgu`, `orta`, `kunye` sayaçları (boş dönüşte de var).

### 33.2 Paket 2 — okunurluk

- **Olay çizgisi dili:** CHoCH NOKTALI (`":"`), BOS kesikli. Matplotlib dash
  demetlerini `'--'`e normalleştirdiği için stil ayrımı adlandırılmış desenle
  yapıldı (arşiv ölçümü: 26 `--` + 3 `:`).
- **Yaş solması:** kritik dışı çizginin alfası olay yaşıyla azalır (0,85 → 0,38).
- **Şerit çip birleştirme:** aynı seviyedeki `zone` çipleri tek çipte toplanır
  (`OB↑ · FVG↓`; çip başına en fazla 3 kutu, fazlası yeni çip). `kritik`, `alarm`
  ve son fiyat kendi çipinde kalır. Kılavuz çizgisi ortaktır.
  `meta["sag"]`: `birlesik`, `birlesen_kutu` (kayıp yok).
- **Lejant:** `┄ BOS` ve `┈ CHoCH` ayrı yazar, yalnız GÖRÜNEN tür için madde çıkar.
- Ölçüldü: kutu içi yazı ↔ şerit çipi çakışması 8 karede 0 px².

### 33.3 Paket 3 — okuma modları

Mod kapsamı **thread-local** (`_ModKapsami`): `PALET[...]`/`SABITLER[...]` çağrı
yerleri değişmedi, tablolar sarmalayıcıdan okunuyor. Global mutasyon olsaydı
tarama thread'i ile görsel gönderim işçisi birbirinin modunu sızdırırdı.

- `--sade`: veriden keser → yalnız mum + formasyon bandı + kritik/son fiyat.
  Kesilen katman `eksik`e yazılmaz; `meta["mod"]["atlanan_kutu"]` kaç kutunun
  mod nedeniyle çizilmediğini söyler.
- `--renk-korugu`: mum/şerit/son-fiyat renkleri mavi-turuncu (deuteranopia);
  şekil kanalı korunur (yükselen BOŞ / düşen DOLU). Lejant renk ADINI da değişir.
- `--buyuk-yazi`: yalnız `*_pt` ×1,25; dpi/kalınlık/kadraj sabit. Lejant bütçesi
  ölçeği hesaba katar, alt blok satır adımı büyür → taşma/çakışma 0.
- ENV: `GRAFIK_SADE`, `GRAFIK_RENK_KORUGU`, `GRAFIK_YAZI` (canlı akış için);
  CLI bayrağı env'i ezer, bayrak yoksa env devreye girer.

### 33.4 Önce/sonra kanıtı

`docs/ornek_kare_gorsel5.png` — üst satır `git archive d8720cc` ağacıyla üretilen
GERÇEK GÖRSEL-4 çıktısı, alt satır GÖRSEL-5 (aynı veri: GARAN 4s 140 mum `--zone`).
Fark: `q100` kod etiketi gitti, `%doluluk` + cetvel + künye geldi, BOS kesikli /
CHoCH noktalı ayrıştı, aynı seviyedeki kutu çipleri (`FVG↓ · OB↑`) birleşti.
Kanıt kareleri ayrıca modlarla birlikte alındı: `--sade`, `--renk-korugu`,
`--buyuk-yazi` (`/tmp/kare/p3g_*.png`, kalıcı değil).

### 33.5 Açık kalanlar

- Paket 1'de önerilen **kutu künyesi genişletmesi** (kaç kez test edildi) ve
  **seviye cetveli / karar satırı** uygulanmadı — kullanıcı üç paketi seçti.
- `GRAFIK_OLAY_MAKS` (§29.4) hâlâ onay bekliyor.
- Kutu içi yazı ince kutuda mumla kısmen örtüşebilir (bkz. §32.3).

## 34 · GÖRSEL-6 (2026-10-15) — PH/PL seviye cetveli + kutu dolgusu belirginliği

Kullanıcı: *"sadece ben sağ şeritte seviye cetveli istiyorum PH PL için, bir de FVG ile
OB renkleri tam belirgin değil yani onun şeffaflığını biraz azaltır mısın ama çok abartma"*.

### 34.1 PH/PL → sağ şerit seviye cetveli

- Korunan uçlar (`PH`/`PL`) artık **grafikte yazı değil**: fiyat, seviyesiyle hizalı
  tek yerde — sağ şeritteki cetvel çipinde (`PH 290,50`) okunur. Grafikte yalnız ince
  seviye çizgisi kalır; aynı metin iki yerde tekrarlanmaz.
- Çip `oncelik=4` (son fiyat 9 > alarm 6 > kritik 5 > **PH/PL 4** > BOS/CHoCH 3 > kutu 2),
  kaynak başına sınır `sag_etiket_maks["swing"] = 2`.
- Kılavuz çizgisi kutu kılavuzundan **belirgin** (0,8 pt · α 0,38 · `(0,(1,3))`) ama
  kritik/alarm çizgisi kadar kalın değil — uyarı tonu taşımaz.
- **Aynı seviye çifti bastırılır:** son fiyatla aynı bantta kalan PH/PL çipi atlanır
  (ölçüm: THYAO 1s'te `PH 290,50` ile son fiyat `290,50` üst üste biniyordu). Atlama
  `meta["sag"]["atlanan_kaynak"]["swing"]` ile SAYILIR — sessiz kayıp yok.
- İç yapı etiketleri (`HH`/`HL`/`LH`/`LL`) grafikte kısa hâliyle kalır.
- Lejant: `┈ seviye (PH/PL sağda)` + yapı satırı `▲▼ iç yapı · ┄ BOS/CHoCH · ━ kritik · PH/PL sağda`.
- `meta["olay"]["phpl_serit"]` cetvele taşınan PH/PL sayısını verir.

### 34.2 Kutu dolgusu (OB/FVG)

- Kullanıcı isteği: "şeffaflığını biraz azalt, ama çok abartma". Ölçülü artış:
  `doldurma.ob 0.09 → 0.16`, `fvg 0.08 → 0.15` (≈1,8×); kalın/ince kutu kademesi
  `ince 0.04 → 0.07`. Neon DEĞİL: dolgu hâlâ yarı saydam, mum okunurluğu korunur.
- Kenar `0.8 → 0.9 pt` (kutu sınırı bir tık belirgin); vurgu çubuğu 1,3 pt **değişmedi**
  ("havada çubuk" görüntüsü geri gelmesin).

### 34.3 Ölçüm ve kanıt

- 20 kare: cetvele taşınan PH/PL **19**, şeritte 80 çip, atlanan 1 (son fiyat çakışması),
  `mum_cakisan` 0. Kutu dolgu alfa dağılımı: 0,16/0,15 (ana), 0,28 (dolan kısım),
  0,07/0,075 (ince kutu kademesi).
- `docs/ornek_kare_gorsel6.png` — üstte `git archive 9196cce` ağacıyla üretilen gerçek
  önce karesi, altta sonrası (aynı veri: THYAO 1s 180 mum `--zone`).
- Testler: `test_grafik_gorsel5.py` +5 test (cetvel çipi + kılavuz stili, son fiyat
  bastırması ve sayacı, uzak seviyede ikisinin de kalması, dolgu aralığı/neon tavanı,
  kutu içi yazının konturel okunurluğu); GÖRSEL-4'ün PH/PL testleri yeni sözleşmeye
  çevrildi. Tam süit: 1133 passed / 44 skipped.

### 34.4 Açık kalanlar

- Cetvel şu an kaynak sırasına göre diziliyor (son fiyat/alarm/kritik/PH-PL/kutu);
  istenirse başlıklı gruplara ayrılabilir ("SEVİYELER" / "BÖLGELER").
- `GRAFIK_OLAY_MAKS` (§29.4) hâlâ onay bekliyor.

## 35 · GÖRSEL-7 (2026-10-15) — kart metni sadeleşti + geçersizleşme kâresinde üç işaret

Kullanıcı: *"mesaj aşırı karışık / nokta nokta / okunabilirlik kötü"*, ardından
*"iki farklı örnek yazı: biri normal alarm, biri geçersizleşme — geçersizleşmenin görsel
formatı nasıl olacak?"* → onay: **"Tamamdır onaylandı"**. Kart **düz Telegram metni**
kalır (HTML/`parse_mode`/link/hizalama YOK — kullanıcı kararı) ve hedef **8-11 satır**.

### 35.1 Sade kart (`TELEGRAM_KART_SUZGEC`, varsayılan açık)

Ölçülen sorun (gerçek payload, `telegram_measure`): bugünkü kart **34 satır · 735 kr ·
8 girintili devam satırı · 23 `·` · 7 `▪`**; DOMAIN grupları (`◈ yapı`, `▲ OB`, `▤ hacim`,
`▸ TF`) satırların yarısını yiyor ve hepsi aynı görsel ağırlıkta.

- İş bölümü: **kâre ana okuma; metin yalnız kârede OLMAYANI söyler.** Metinden düşen:
  kırılan seviye satırı, temas üst/alt, daralma, `◈ yapı` blokları, `▲ OB/FVG` kutu
  listeleri, `▤ hacim` blokları, `▸ TF` satırları, mum damgası (kâre üst şeridi
  `son kapanan <tarih> · <fiyat>` yazar).
- Metinde kalan ve kârede görünmeyen: **bozulma/teyit sınırı** (`bozulur 38,79 üstü kapanış`),
  **bant yaşı + izlenme başlangıcı** (`bant 94 bar — 30.09'dan beri`), **retest + MTF onayı**,
  **katılım yargısı** (kârede çubuk var, yorum yok) ve **karşı delil**.
- Satır kuralları: satır = TEK konu (≤2 öğe) · `·` zinciri yok, çift ayırıcı `—` ·
  girintili devam satırı yok · her satır ≤283 px (güvenli sınır 269 px). Satır sığmazsa
  `_kart_esik_px()` eşiği devreye girer: `Yükselen Üçgen — bandına dönüş` (270,5 px)
  yerine kısa tire (260,5 px) — **bölünme yoksa girinti de yok**.
- Geçersizleşme kartı: yalnız formasyon + geçersizleşen TF + `teyit sınırı 38,79 üstü`
  (eski `× geçersiz:` cümlesi pozitifleşti). Katılım bölümünden en çok 2 satır gelir.
- Güncelleme kartı: `değişiklik yok — yapı/bölge/hacim aynı` + CTA.
- **İzleme adayları bloğu korundu** (acil mesaj bağlamı; adaptör doldurur): başlık +
  en çok 3 aday satırı. Mum damgası gibi kâreye taşınamaz — bilgi düşürülmedi.
- Kill-switch: `TELEGRAM_KART_SUZGEC=0` → 25 Eyl biçimi (tam kart) aynen geri gelir.

### 35.2 Geçersizleşme kâresi: üç işaret

1. **`✕ geçersizleştiren mum`** — teyidi düşüren mumun işareti (mum eksenin alt
   yarısındaysa 10 px ÜSTÜNE, üst yarısındaysa 17 px ALTINA). Punto `durum_pt × 1,5`
   (9,5 pt küçük kalıyordu) + zemin renkli kontur → mum gövdesi üstünde okunur.
2. **`┈ teyit sınırı`** — noktalı turuncu yatay kılavuz + sağ çip `× 38,79 üstü kapanış`
   (kaynak `gecersiz`, öncelik 5, renk `olay`). Kural **güncel bandı** okur
   (`upper_now`/`lower_now`) — `notifier`deki `× geçersiz` satırıyla birebir aynı.
   Yön bilinmiyorsa eşik ÇİZİLMEZ (uydurma seviye yok).
3. **`✕ eski seviye <kırılan>`** — kırılan dondurulmuş sınır artık geçersiz: çizgi
   soluk (α 0,55) + kesik `(0,(2,4))`, çip metni `✕ eski seviye 70,75`, rengi `eksen`.
   **Ölçülü kural:** iki seviye `0,02 × y-aralığı`ndan (≈12 px) yakınsa soluk çizgi
   ÇİZİLMEZ — üst üste binen iki çizgi okunmaz (AKBNK 4s ölçümü: 70,75 / 70,84 = 1,4 px).
- Lejant: `✕ geçersizleştiren mum` / `✕ eski seviye (artık geçerli değil)` / `┈ teyit sınırı`
  eklenir; teyitli alarmda eski dil (`│ alarm mumu`, `─ seviye`) korunur.

### 35.3 Lejant taşması + şerit etiketi (teknik borç kapandı)

- Taşmada artık **uzun ve düşük öncelikli** maddeler düşer (`yapı:`, `şerit:`, `kutular:`,
  `FVG`, `bant öncesi`, `▨ dolan`); **`✕` / `┈` maddeleri hiçbir koşulda düşmez** (yoksa
  kâre açıklamasız işaret bırakır). Hepsi korunmuşsa en sondan düşülür.
- Kareye yazılan `+N madde sığmadı` ve kırmızı `lejant: N madde sığmadı` dipnotu
  **kaldırıldı**; sayı `meta["lejant_atlanan"]`da durur (sessiz kayıp yok).
- Şeritteki çıplak `×2,9` çipi kendini anlatmıyordu → **`rvol ×2,9`**.

### 35.4 Ölçüm ve kanıt

| | satır | kr | en geniş | girinti | 3+ zincir |
|---|---|---|---|---|---|
| ÖNCE (süzgeç kapalı) | 34 | 735 | — | 8 (%23) | var |
| SONRA normal | 11 | 278 | 242 px | 0 | 0 |
| SONRA geçersizleşme | 9-10 | 228-252 | 260 px | 0 | 0 |

- `docs/ornek_kart_gorsel7.png` — aynı payload'ın eski/yeni metni (satır satır px ölçüsüyle).
- `docs/ornek_kare_gorsel7.png` — gerçek AKBNK 4s zinciri (onay barı 95 → geçersizleşme
  barı 101, `PatternLifecycleManager.scan` bar bar oynatıldı): önce/sonra kâresi + Gelecek Metin.
- Testler: `test_kart_metin.py` (10) · `test_grafik_gorsel7.py` (9). Güncellenen sözleşmeler:
  `test_grafik_iskelet.py` (lejant taşması artık kareye yazılmaz), `test_notifier_mesajlari.py`
  (4 test yeni karta), `test_telegram_alert_flow.py` + `test_tekrar_alarm_korumasi.py`
  (hazırlık çıktısı `domain_bolumleri`), `test_mum_kapanis_penceresi.py` (damga kâre başlığında).
- Tam süit: **1152 passed / 44 skipped**.

### 35.5 Sonraki adım (P1 — veri zenginleştirme)

Kart kısaldı; elde kullanılmayan veri duruyor (`net_progress_atr`, `directional_efficiency`,
`volume/capital_regime`, `break_reference_source`, `evidence_text`, `age_bars`,
`bos_maturity`, `break_frozen_*`) — sıradaki tur **görselde** bu alanları okunur kılacak
(şerit tonu, ilerleme/verim çubuğu, olay kanıtının Türkçesi), metin yine yalnız görünmeyeni söyleyecek.

## 36 · GÖRSEL-8 (2026-10-15) — OB/FVG dolgu tonu tersine döndü

Kullanıcı: *"OB'nin koyu tarafı doldurulmuş taraf oluyor, açık renk olan tarafı
doldurulmamış taraf. Tam tersi olmasını istiyorum."* — **başka değişiklik istenmedi**,
sadece ton yönü döndü.

### 36.1 Ne değişti

- Eskiden: kutu tek parça (`ob 0,16` / `fvg 0,15`) + **dolan kısım üstüne `+0,12` alfa**
  → dolan taraf koyulaşıyordu. Yeni: kutu **iki ayrı dolgu** olarak çizilir —
  **doldurulmamış kalan alan KOYU** (`ob 0,16` / `fvg 0,15`), **dolan bant AÇIK**
  (`alfa = kutu × 0,50`, taban `0,03`). Kullanıcı ölçüsü: *"arttır biraz görünsün ama
  soluk olsun dolmayana göre"* → dolan bant kalan alanın **yarısı** kadar koyu.
- Ölçülen tonlar (GARAN 1s · OB↓ %64 dolu): dolan kısım `(23,67,52) → (17,33,34)`,
  kalan alan `(19,46,41)` **değişmedi**. Geometri aynı: boğa kutuda dolgu üstten aşağı,
  ayı kutuda alttan yukarı (motorun `fill_ratio` formülüyle birebir).
- Dolan bandın **sınır çizgisi** (1,0 pt · α 0,90) ve `%X` etiketi duruyor — dolan
  kısmın geometrisi hâlâ okunur, ton tek bilgi kanalı değil.
- Çerçeve artık dolgusuz ayrı bir dikdörtgen; alfası eskisi gibi `saydam` (görünüm
  birebir korundu), kalınlık `0,9 pt` ve vurgu çubuğu `1,3 pt` **değişmedi**.
- Uçlarda (%0 / %100) bant çizilmez: kutu tek parça koyu kalır (eski davranış).

### 36.2 Testler

- `test_grafik_gorsel5.py`: `_dolgu_bandi` artık **en AÇIK** dolgulu dikdörtgeni bulur
  (çerçeve `facecolor="none"` olduğu için ölçüme girmez); uç değer testi yalnız DOLGULU
  dikdörtgeni sayar. Yeni test: `test_dolan_kisim_acik_doldurulmamis_kalan_koyu`
  (iki ton, dolan < kalan, taban/neon tavanı, hue aynı, sınır çizgisi α 0,90).
  GÖRSEL-6 sayı sözleşmesi (0,14–0,20 ve kenar/vurgu) korunuyor.
- `docs/ornek_kutu_tonu.png` — iki farklı hisse (GARAN 1s, AKBNK 1s), önce/sonra,
  ölçülen ton değerleriyle.

## 37 · SAĞ BOŞLUK (2026-10-15) — son mumlar kenara yapışmasın, çizimler devam etsin

Kullanıcı: son mumlar sağ kenarda aniden bitiyor, çizimler son mumda kesiliyor; sağda
~10 mum boşluk bırakılsın. Sonraki kararları: çizimler boşluğa **devam etsin**; boşluk
"tam 10 mum" olmasın, **görsel pay** olsun ("yalancıktan"); devam **kesikli olmasın**.

### 37.1 Neden böyleydi (kodla doğrulandı)

- `_kare_ciz`'de `sag_bosluk = 0.0`, `_serit_ciz`'de `zone_pay = 0.0` vardı. GÖRSEL-2'de
  (§29) etiketler sağ fiyat şeridine taşınınca pay sıfırlanmış; §23.2'deki `n-0.4+6`
  maddesi o günden beri güncel değildi (o madde işaretlendi).
- Yalnız `axhline` seviyeleri (alarm / kritik / son fiyat) kenara kadar uzuyordu. Bant
  çizgileri, OB/FVG kutuları ve BOS/CHoCH çizgileri son mumda (`n-1`) bitiyordu.
- **Tek satırlık düzeltme işe yaramaz.** Katılım şeridi `sharex` ile ana eksene bağlıdır
  ve EN SON çizilirken `set_xlim`'ini kendi payıyla (0) yeniden yazar: yalnız
  `_kare_ciz`'deki payı değiştirmek `meta["kare"]["x_siniri"]`'nı değiştirir ama şerit
  açıkken piksel AYNI kalır; şerit kapalıyken de çipler boşluğun içine düşer. Ana eksen,
  şerit ve çip kenarı aynı değeri kullanmak zorunda. (`meta` testleri bunu yakalayamaz →
  §37.5: yeni testler çizilmiş eksenleri okur.)

### 37.2 Kararlar

| Konu | Karar |
|---|---|
| Boşluğun ölçüsü | Eksen genişliğinin **%5,3'ü** (`SABITLER["sag_bosluk_yuzde"]`), tam bara yuvarlanır: 180 mumluk karede **10 bar**, 120 mumluk (4s) karede **7 bar**. Sabit 10 bar 4s'de mumları %7,7 daraltırdı, oranla %5,5. Tam sayı bar: kutu/çizgi geometrisi bar ızgarasında kalır. |
| Devam eden çizimler | Son muma uzanan **OB/FVG kutuları**, **BOS/CHoCH çizgileri** ve **bant çizgileri + bant dolgusu**. Son muma uzanmayan (`x1 < n-1`) kutular uzamaz. |
| Devam biçimi | **Kesiksiz, aynı çizgi** (kullanıcı kararı: kesikli olmasın). Bant doğrusu motorun kendi denklemiyle (`f_line_price`) sürer, yeni geometri üretilmez. "Bant öncesi" geriye doğru kesikli uzantı (§0.12e) ayrı bir özelliktir, dokunulmadı. |
| Apex | Daralan bantta çizgiler apex'te kesişir; **uzatma orada biter** (kesişmeyi aşıp ters dönen çizgi uydurma olurdu). Apex geride kaldıysa uzatma yok. Apex boşluğa düşerse ✕ iki doğrunun kesiştiği noktaya konur (veri katmanı mumsuz bar için işaret üretemez). Apex boşluktan uzaktaysa çizgiler boşluğun sonuna kadar gider. |
| Etiketler | Sağ paneldeki çipler eksenin yeni kenarına (`n-0.4+boşluk`) bağlanır; boşluğun içine girmez. |
| Ayar / kapatma | `GRAFIK_SAG_BOSLUK` = yüzde (varsayılan `5.3`, üst sınır 15). `0` → eski görünüm, **PNG bayt bayt aynı**. Sonsuz/NaN/bozuk değer varsayılana düşer, çizim asla engellenmez. |
| Tuval | 1080×810 **değişmedi** (§0.12q, 4:3). Mumlar yaklaşık %5 daralır (aşağıda ölçüm). Boşlukta zaman etiketi yok: gelecek zamanı iddia etmez. |

### 37.3 Kodda ne değişti (`grafik.py`)

- `sag_bosluk_mum(n)`: env'i çağrı anında okur (`_ortam_sayi`; `config.py` değişmedi).
  `g = p·(n+0,2)/(1−p)`, tam sayıya yuvarlanır, `p` 0–15 aralığına kıstırılır.
- `_kare_ciz` payı hesaplar, `set_xlim(-0.6, n-0.4+g)` yazar ve `meta["kare"]` içine
  `sag_bosluk` (bar) ile `sag_bosluk_yuzde` ekler (`x_siniri` zaten vardı).
- `_zone_ciz`, `_olay_ciz`, `_formasyon_ciz`, `_serit_ciz` anahtar-sözcüklü
  `sag_bosluk: int = 0`, `_sag_ciz` ise `x_kenar` alır. **Varsayılanlar eski davranıştır**:
  mevcut çağrılar ve testler değişmedi.
- Yazısı kutuya sığmayıp sağ şeride çip olarak giden kutuya (`seride`) **uzamış** `x1`
  yazılır; yoksa uzamış kutunun üstüne yersiz kılavuz çizgisi çizilirdi (prototipte görüldü).
- Değişmeyenler: `isaretler` veri katmanı ve meta'sı, lejant, PNG boyutu (1080×810).

### 37.4 Ölçüm (gerçek önbellek, aynı veri; önce = `git archive 8e6862a`)

| kare | mum | boşluk | mum başına px (önce → sonra) | PNG (önce → sonra) |
|---|---|---|---|---|
| AKBNK 1s | 180 | 10 bar | 4,58 → 4,34 (−%5,3) | 117,3 → 118,4 KB |
| YKBNK 1s | 180 | 10 bar | 4,58 → 4,34 | 105,9 → 107,1 KB |
| SISE 4s | 120 | 7 bar | 6,86 → 6,48 (−%5,5) | 94,7 → 95,5 KB |
| GARAN 4s | 120 | 7 bar | 6,86 → 6,48 | 89,8 → 90,2 KB |

- Apex: SISE 4s'te apex son mumun **+6 bar** ilerisinde, YKBNK 1s'te **+4**: çizgiler
  orada birleşip duruyor, ✕ oraya konuyor. HALKB 4s'te apex **5 bar geride** (bar 114/120):
  uzatma yok, kutular kenara uzanıyor. AKBNK 1s'te apex yok: çizgiler boşluğun sonuna kadar.
- `GRAFIK_SAG_BOSLUK=0`: 8 karenin 8'i **bayt bayt aynı** PNG (AKBNK/YKBNK/THYAO/DOHOL 1s,
  SAHOL 2s, SISE/GARAN/HALKB 4s); apex işareti görünür aralıkta olan iki kare (HALKB 4s,
  SAHOL 2s) dahil.
- `docs/ornek_sag_bosluk.png` — üstte `git archive 8e6862a` ağacıyla üretilen gerçek önce
  karesi, altta sonrası (aynı veri: AKBNK 1s 180 mum, `--zone --formasyon-tara`).
- PNG tavanı (`deploy_check`, 500 KB) etkilenmedi: artış ≈ 1 KB.

### 37.5 Testler

- `test_grafik_sag_bosluk.py` (**36 test**) çizilmiş eksenleri okur, `meta`'yı değil
  (`_metin_ciz` sarılıp `savefig`den önce figür yakalanır; eksen kapanıştan sonra da
  okunabilir). Kapsam: boşluk ölçüsü ve env tablosu (`0`/`-4` → 0; boş/bozuk/NaN/sonsuz →
  varsayılan; `10` → 20 bar; `99` → %15 tavanı); ana eksen **ve** şerit aynı `xlim`'i
  taşır (1s/4s × şerit açık / `serit=False` / `sade`); formasyon katmanı çökse de boşluk
  kalır; PNG 1080×810 kalır; mum başına piksel oranı ≥ 0,93 (sabit 10 bar'ı eler);
  kutu / BOS / çip / bant çizgisi / bant dolgusu geometrisi; bant çizgisi **kesiksiz**
  (kesikli çizgiler yalnız geriye doğru "bant öncesi" olanlar); apex kuralları (apex
  boşlukta → çizgiler orada biter + tek ✕; apex uzakta → boşluğun sonuna kadar; apex geride
  ya da `GRAFIK_SAG_BOSLUK=0` → uzatma ve ✕ yok); tam karede mutlak apex barının x'e dönüşümü.
- **Mutasyon denetimi:** 11 bilinçli bozma (şerit `zone_pay=0` tuzağı, kutu uzamıyor, BOS
  çizgisi son mumda bitiyor, çipler eski konumda, şerit yedeği kılavuzu sızıyor, apex ✕
  yok, çizgi apex'i aşıyor, sabit 10 bar, kesikli ayrı devam, bant dolgusu uzamıyor,
  `0` kapatmıyor) — her biri en az bir testi kırdı.
- Mevcut 243 grafik testi hem varsayılan boşlukla hem `GRAFIK_SAG_BOSLUK=0` ile geçiyor
  (yeni dosyayla 279 test). Tam süit: **1189 passed / 44 skipped** (181 sn).

### 37.6 Açık kalanlar / bilinçli tercihler

- Boşlukta **zaman etiketi yok**: x ekseni son mumun tarihinde biter.
- `render.yaml` ve `deploy_check.py` anahtar listelerine eklenmedi (§33'ün `GRAFIK_SADE`,
  `GRAFIK_RENK_KORUGU`, `GRAFIK_YAZI` anahtarları gibi): `.env.example`, `RENDER_DEPLOY.md` ve
  bu belgede yazılı.
- ✕ glifi mevcut tasarımda zemin renkli kenarla çiziliyor (çok soluk); boşluktaki ✕ aynı
  çizimi kullanıyor, asıl görünen ucundaki ~9 pt'lik işaret çizgisi. İstenirse ayrı iş olarak
  belirginleştirilebilir.

## 38 · YAPI SCOPE DÜZELTMESİ (2026-10-15) — oklar iç, rol cetveli dış

Kullanıcı, grafikte “iç yapı” diye gösterilen okların doğru olmadığını düşündüğünü
belirtti. Kod incelemesinde eski `_olay_verisi`'nin `external_swings` ve
`external_candidates` kayıtlarını `▲/▼` olarak çizdiği, buna karşın lejantın “iç yapı”
dediği görüldü. Bu bir görsel sözleşme/veri seçimi tutarsızlığıydı; motorun iç swing
hesaplamadığı anlamına gelmiyordu.

### 38.1 Güncel çizim sözleşmesi

- **▲/▼ okları ve kısa HH/HL/LH/LL etiketleri:** yalnız `internal_swings` +
  `internal_candidates`; external swing'ler bu marker listesine karışmaz. İç pivotlar
  motorun internal scope'undan gelir (`internal_pivot_len=2`). Ok `source_bar`'a,
  yani pivotun oluştuğu muma konur; `confirm_bar` daha sonra teyit zamanını belirtir.
- **PH/PL/WH/WL:** dış scope'un aktif rol seviyeleri; önce safety-gated
  `export.external_protected_high/low` ve `export.external_weak_high/low` kullanılır.
  Eski/yalın çıktı nesnelerinde export yoksa yalnız `external_swings.structural_role`
  açıkça eşleşen kayıtlar yedek kaynaktır. `swing_class=PH/PL` tek başına protected
  seviye sayılmaz. Seviye yatay ince kılavuz ve sağ cetvel çipiyle gösterilir.
- **BOS/CHoCH:** mevcut seçim korunur — `event_history` içinde `scope=EXTERNAL`,
  `CONFIRMED` ve `VALID`; lejant artık bunları “dış” olarak adlandırır.
- **Bütçe:** iç oklar için en yeni 10 pivot; sağ cetvel dört dış rolün tamamını
  (PH/PL/WH/WL) taşıyabilir. İç oklar cetvel çip kotasını tüketmez. Son fiyatla aynı
  seviyedeki dış rol çipi bastırılırsa `meta.sag.atlanan_kaynak.swing` bunu sayar;
  seviye çizgisi kalır.
- **Meta:** `olay.swing` internal marker sayısıdır; `olay.dis_seviye` aktif dış rol
  seviyelerini sayar; `phpl_serit` ve `whwl_serit` cetveldeki rol etiketlerini izler.
- `grafik.py` çizimi, `test_grafik_yapi.py` kaynak/scope ve seviye seçimini, görsel
  testleri oklar/etiketler/kılavuzları sınar. Bu değişiklik Telegram kart metinlerine
  dokunmaz.

### 38.2 Not

Bu bölüm §0 karar 7, §24.2'deki eski “swing = external” çizim seçimi ve §34.1'deki
PH/PL sınıfına dayalı cetvel açıklamasını günceller. Tarihsel ölçümler o tarihteki
eski uygulamayı tarif eder; güncel davranış bu bölümdeki kaynak ve scope ayrımıdır.

## 39 · GRAFİK DENETİMİ (2026-10-15) — temas işaretleri, zone kaynağı ve lifecycle

Bu bölüm, mevcut PNG çizimini gerçek önbellek verisiyle inceleyip doğruladıktan
sonra yapılan **yalnız grafik katmanı** düzeltmelerini kaydeder. Engine algoritmaları,
Telegram/kart metinleri ve sinyal üretimi değiştirilmedi.

### 39.1 Görsel ve veri kaynağı sözleşmesi

- **Bant temas daireleri kaldırıldı.** Temas hesap listesi, üst/alt sayıları ve
  meta/girdi özeti korunur; `temas_isaret` geriye uyumluluk için boş liste kalır.
  Temas noktası başına mum üstüne marker çizilmez, lejantta da daire maddesi yoktur.
- **OB kaynağı:** `order_block.details.active_records`. Bu alan mevcut ama boşsa
  eski `records` listesine düşülmez; yalnız eski/harici şemada `active_records`
  alanı hiç yoksa `records` fallback'i kullanılır. `export.bull/bear.fill` yalnız
  aynı `source_bar` ile eşleştiğinde OB doluluk oranına bağlanır.
- **FVG/engulfing kaynağı:** lifecycle alanları varsa aktif yön kayıtları ve
  `completed_*` listeleri kullanılır; `fvg_formations` / `engulfing_formations`
  ham listeleriyle üst üste karıştırılmaz. Lifecycle alanı olmayan eski sonuçlarda
  raw formation kontrollü fallback'tir.
- **FVG doluluğu:** `maximum_fill_ratio` → yoksa `wick_fill_ratio` → eski şemada
  `close_fill_ratio`. Böylece ham FVG'deki eksik `close_fill_ratio`, lifecycle
  doluluğunu silmez; değerin görsel aralığı 0–100% ile sınırlanır.
- **Engulfing geometrisi:** dikdörtgen `lower_boundary/upper_boundary` (yutulan
  önceki gövde) kullanır. `formation_low/high` engulfing mumunun kendi fitil
  aralığıdır; kutu sınırı değildir, yalnız denetim meta'sında ayrı tutulur.
  Bilinmeyen/`NONE` yön bullish varsayılmaz.
- **Tekrar ve seçim:** aynı tip/yön/fiyat sınırı/kaynak indeksiyle yinelenen kayıt
  tek kutuya indirilir; aynı fiyat bandının farklı kaynak barlardaki oluşumları
  ayrı kayıt olarak kalır. Aktif → aday → tamamlanmış sırası korunur. 4s yan
  kapasitesi en az iki ise tamamlanmamış FVG ve ENG'den en yakınına birer slot
  ayrılır; kalanlar ATR yakınlığıyla doldurulur. Kapasite sayıları değişmedi.
- **Durum stili:** aktif kutu solid; aday kutu noktalı ve `?`; tamamlanmış kutu
  soluk/kesik. ENG dolgusuz kalır ama mor sınır artık görünürdür. Kutu etiketinin
  konumu mumlara, mevcut zone etiketlerine, son fiyata, kritik/yapı/alarm
  seviyelerine göre seçilir; bir yatay çizgi metnin içinden geçirilmez.

### 39.2 Gerçek veriyle doğrulama

`.venv/bin/python` ve `bot_data` ile 10 sembolün (`AKBNK`, `THYAO`, `SISE`,
`GARAN`, `EREGL`, `DOHOL`, `TUPRS`, `BIMAS`, `ASELS`, `FROTO`) 4s/1g kareleri
oluşturuldu; her `meta.zone.kayitlar` satırında fiyat sınırı, kaynak indeks, durum,
doluluk ve `kayit_kaynagi` karşılaştırıldı. Örnek PNG'ler `/tmp`'de tutuldu, Git'e
alınmadı.

- **AKBNK 4s:** lifecycle aktif FVG kaydı `source=100`, sınır `65,20–68,85`,
  `maximum_fill_ratio=0` olarak eşleşti; ham formation listesinden seçilmiş yakın
  fakat farklı aday kutular çizim kaynağı yapılmadı. Kutu çizimde gösterildi ve
  `%0` etiketi doğru; kritik `67,20` çizgisi etiketten kaçırıldı.
- **BIMAS 4s:** tamamlanan FVG `source=107`, `423,50–430,75`, doluluk `≈%24`
  olarak lifecycle kaydından geldi ve soluk/kesik biçimde gösterildi. Tamamlanmış
  ENG kaydı `source=106` için yutulan gövde sınırı ile engulfing mumunun kendi
  high/low aralığı meta'da ayrı doğrulandı.
- **ASELS 4s:** aktif FVG'lerin durum/dolulukları ve OB kaynakları doğru fiyat
  sınırlarıyla gösterildi; çizim bölgesi sayısı kapakla sınırlı kaldı. Aynı kaynak
  kimliğiyle gelen yinelenen kayıtlar için tekilleştirme testi eklendi.
- Bu karelerde `meta.zone.cikarim` ham/lifecycle kaynak türünü ve aktif/tamamlanan
  sayıları raporlar; `meta.zone.kayitlar` ise çizilen her kutunun gerçek fiyat
  aralığını ve indeksini taşır. Tamamlanmış kayıt kapak doluysa bilinçli olarak
  elenebilir; `elenen` sayacı bunu görünür kılar.

### 39.3 Testler ve kapsam

- `test_grafik_bolgeler.py`: aktif OB listesi/fallback, duplicate, FVG lifecycle
  doluluğu, FVG'nin yakın OB'lerce tamamen örtülmemesi, ENG boundary-high/low
  ayrımı, kaynak/indeks ve gerçek CLI şekli.
- `test_grafik_gorsel_kalite.py`: temas dairesi yok, ENG konturu görünür, tamamlanan
  kutu soluk/kesik, yatay seviye kutu etiketinden kaçıyor.
- Bu bölümün eklenmesi sırasında mesaj/kart metni ve `domain_engines/` dosyaları
  değiştirilmedi. Önceki iç swing okları/dış yapı ayrımı §38'deki gibi korunur.

---

## 40 · FAZ 1-4: KULLANICI GÖRSEL PLANI UYGULANDI (2026-10-15)

Kullanıcının dört fazlı görsel planı (temizlik → kadraj → SMC motoru → fintech
cila) uygulandı. Bu bölüm planın her maddesini koddaki karşılığı, ölçülmüş
sonucu ve kapatma testiyle eşler. **Motorlara (`domain_engines/`) yazılmadı**:
mitigation oranı motorun kendi `fill_boundary` alanından hesaplanır; kırılım
çizgisinin başlangıcı motorun kendi `origin_source_bar` alanıdır.

### 40.1 FAZ 1 — Temizlik ve alan kazanımı

- **Geliştirici metinleri kareden ÇIKTI.** `veri: N bar hacimsiz`, `bölge: N kutu
  kapak dışında`, `eksik: zone`, lejant satırları artık kareye basılmaz; aynı
  metinler `meta["metin"]`den **kare altı caption dipnotuna** taşınır
  (`notifier._grafik_dipnotu`, tek satır, `ℹ️` öneki, ≤200 karakter). Kazanılan
  dikey alan mumlara kalır: eksen alt kenarı `0,075 → 0,028`.
- **Alt hacim paneli kaldırıldı.** `meta["serit"]["panel"] is False` ve figürde
  TEK eksen kalır. `GRAFIK_HACIM_PANELI=1` eski iki kulvarlı görünümü geri getirir
  (8 karede bayt bayt aynı PNG — kaçış kapısı korunur).
- **RVOL rozeti (2026-10-16'da İKİ YÖNLÜ oldu, §42).** `RVOL > 2,0×` olan mumların
  altına artık `⚡↑ x2,5` (patlama), `RVOL ≤ 0,5×` olanlara `⚡↓ x0,5` (kuruma)
  yazılır (`_rvol_rozetleri`). Üst üste binme denetimleri ölçülmüştür: aynı
  bölgede en sert hacim kalır, pivot etiketi olan mumda rozet fitilin ÜSTÜNE
  taşınır, alt kenara yakın mumda x ekseni etiketine binmesin diye yukarı alınır.
- Kapatma: `test_grafik_faz_kullanici.py::test_faz1_*`, `test_grafik_iskelet.py::test_meta_sozlesmesi_ve_png_olcusu`.

### 40.2 FAZ 2 — Akıllı kadraj

| TF | Formasyon yok (mum) | Formasyon var |
| :--- | :--- | :--- |
| 1g | 62 | formasyon + 10 mum sol tampon, 35-85 arasına kırpılır |
| 4s | 68 | aynı kural |
| 2s | 74 | aynı kural |
| 1s | 80 | aynı kural |

- `SABITLER["kadraj_cerceve"]` TF matrisi; `kare_mum_tavani()` artık TF'e
  duyarlıdır (eskiden dört TF'de de 180'di).
- **Sağ boşluk:** bu turda 15 mumluk sabit alan eklendi (plan: 12-15). **Aynı gün
  §41 ile değişti**: boşluk artık eksen genişliğinin %10-20'si (varsayılan %15);
  sabit mum sayısı kareye göre kayıyordu (80 mumda %16, 35 mumluk formasyon
  karesinde %30). `GRAFIK_SAG_BOSLUK_MUM` yalnız açıkça verilirse sabit mum yolunu
  kullanır; eski `GRAFIK_SAG_BOSLUK` (oran) da yalnız o tanımlıysa geçerlidir.
- Ölçüm: 80 mumluk 1s karesinde px/bar 10,8 → 9,1 (≈%84 korunur); 4s'te 7,3.
- Kapatma: `test_grafik_sag_bosluk.py`, `test_grafik_iskelet.py::test_formasyon_*`.

### 40.3 FAZ 3 — SMC motoru ve çizim revizyonu

- **`mitigated_percentage`** OB kaydına eklendi: boğa `(top − boundary)/yük`,
  ayı `(boundary − bottom)/yük` — `OrderBlockRecord.fill_ratio` ile birebir
  aynı formül. Kaynak sırası: export `fill` → kaydın `fill_boundary`si → yok
  (o zaman `%` yazılmaz). `meta["zone"]["kayitlar"]` alanı taşır.
- **İkili kutu çizimi:** TAZE OB (doluluk ≤ %2) canlı dolgu %25 + düz çizgi;
  KISMEN DOLMUŞ OB'de kalan alan %12 canlı renkte, DOLAN bant mat gri (`#9CA3AF`,
  %8) ve kesikli kontur; KIRILMIŞ/GEÇERSİZ OB'de iç boşalır (%-2 silik iz).
  Dolan bant her durumda kalan alandan soluk kalır (`dolan ≤ kalan × 0,75`).
- **Renk paleti:** OB boğa `#10B981` / ayı `#EF4444`; FVG boğa `#06B6D4` /
  ayı `#8B5CF6`; FVG'de doluluk hesabı YOK (tek ton, ince kesikli kontur) —
  OB ile karışmaz. Ayrım ayrıca kontur stilinde taşınır (düz / kesikli).
- **Doluluk etiketi OB'de anlamlıdır:** `OB↑ · taze` · `OB↓ %41 dolu` ·
  `OB↑ · tükendi`. FVG etiketi yalnız tip + yön (plan §1.B).
- **Line Truncation:** BOS/CHoCH çizgisi motorun pivot barından (`origin_source_bar`)
  başlar ve fiyatın seviyeyi kırdığı mumda biter; **yalnız aktif hedef**
  (en güncel kritik olay) sağ boşluğa kadar uzar. Pivot alanı yoksa çizgi kırılım
  mumundan başlar (uydurma başlangıç yok).
- Kapatma: `test_grafik_faz_kullanici.py::test_faz3_*`, `test_grafik_gorsel5.py::test_dolan_*`, `test_grafik_bolgeler.py::test_mitigated_*`.

### 40.4 FAZ 4 — Fintech cila

- **Pills (rozetler):** sol üst artık düz metin değil, yarı saydam yuvarlatılmış
  çipler: `◆ SEMBOL · TF` · `◈ Formasyon (%q)` · `durum`. Rozet genişliği GERÇEK
  renderer ölçümünden gelir (tahmin 3 rozette üst üste bindiriyordu).
- **Kare içi ikonlar font kapsamasına göre seçilir** (`_ikon`): DejaVu Sans'ta
  📈/📐/🎯 YOK — çizilse "tofu" kutusu olurdu. Font emojiyi taşıyorsa emoji,
  taşımıyorsa `◆ ◈ ◎` kullanılır. Kare böylece her ortamda okunur kalır.
- **Sağ ray Y-Offset + lider çizgisi:** çakışan etiketler dikeyde itilir ve
  gerçek seviyeye **kesikli lider çizgisiyle** bağlanır
  (`meta["sag"]["kaydirilan"]`, `meta["sag"]["lider"]`).
- **Pivot etiketleri:** HH/HL/LH/LL taban ofseti 5 → **11 px** (plan: 10-15 px),
  komşu etiketle basamaklanır.
- **🎯 Hedef projeksiyonu:** TEYİTLİ alarmda hedef = kırılan seviye + yön ×
  formasyon yüksekliği (`current_width`/`start_width`; yoksa çizilmez). Sağ
  boşlukta kesikli çerçeve + `◎ Hedef 55,82` kutusu ve seviyeden hedefe kesikli ok.
- **Formasyon dolgusu** `0,06 → 0,03` (iç alan karartılmaz), sınır çizgileri
  `1,6 → 2,0 pt` (plan §5).
- Kapatma: `test_grafik_faz_kullanici.py::test_faz4_*`.

### 40.5 Doğrulama

- 15 sembolün gerçek `bot_data` önbelleğiyle 1s/4s/1g kareleri üretildi;
  `meta["kalite"]["mum_cakisan"] == 0` (yazı hiçbir mumun üstüne binmiyor),
  `mum_cakisan` kapısı RVOL rozetleri eklendikten sonra da tutuyor.
- Tam paket: `pytest -q` → 1249 geçti, 44 atlandı (333 grafik testi dahil).
  Kare süresi ölçümü: 1s ≈ 590 ms (eski ≈ 540 ms; rozet ölçümü farkı),
  PNG ≈ 55-70 KB.
- Görsel önizleme aracı: `scripts/grafik_onizleme.py` (sentetik veri, motor
  çalıştırmaz, önbelleğe yazmaz) — tasarım turlarında kare bakmak için.
- Turun örnek kareleri: `docs/ornek_kare_faz1_4_1s.png` (GARAN 1s, 80 mum,
  taze/dolmuş OB + kritik + PH/WL cetveli) ve `docs/ornek_kare_faz1_4_4s.png`
  (AKBNK 4s, 68 mum, RVOL rozeti). Ölçüm çıktıları (diğer PNG'ler) depo dışında
  tutulur (§0 kural); yalnız tasarım referansı olan bu iki kare repoda kalır.

## 41 · SAĞ BOŞLUK YÜZDE KURALI (2026-10-16) — %10-20, varsayılan %15

Kullanıcı kararı: *"görselde sağ boşluk diye bir olay var, o şu an %10 %20 yapıp"*.
Boşluk artık **eksen genişliğinin yüzdesi**; sabit mum sayısı değil.

### 41.1 Kural

| Kare | Eski (sabit 15 mum) | Yeni (%15) | Fark |
| :--- | :--- | :--- | :--- |
| 1s 80 mum | 15 mum → %15,8 | 14 mum → %14,9 | −1 mum |
| 4s 68 mum | 15 mum → %18,0 | 12 mum → %15,0 | −3 mum |
| 2s 74 mum | 15 mum → %16,8 | 13 mum → %14,9 | −2 mum |
| 1g 62 mum | 15 mum → %19,5 | 11 mum → %15,0 | −4 mum |
| formasyon 35 mum | 15 mum → **%29,9** | 6 mum → %14,6 | −9 mum |

- `SABITLER["sag_bosluk_orani"] = 0,15`; pencere `sag_bosluk_orani_min = 0,10` /
  `sag_bosluk_orani_maks = 0,20`. Otomatik kural bu pencereye **kırpılır**; oran
  açıkça (`GRAFIK_SAG_BOSLUK_ORANI`) verilirse kırpılmaz (kaçış kapısı).
- Formül: `g = round(o × (n + 0,2) / (1 − o))` bar; eksen `n + 0,2 + g` bar,
  yani boşluğun eksendeki payı tam olarak `o`. Gerçek oran `meta["kare"]["sag_bosluk_yuzde"]`de.
- Öncelik sırası (hepsi yalnız **açıkça verilirse**): `GRAFIK_SAG_BOSLUK_MUM`
  (sabit mum, `0` = kapalı) > `GRAFIK_SAG_BOSLUK` (eski oran) >
  `GRAFIK_SAG_BOSLUK_ORANI` (yeni yüzde) > varsayılan (%15, pencereli).
- Kazanç: formasyon karelerinde 9 muma kadar alan mumlara döndü; **her karede aynı
  görsel oran** (oranlar arası sapma < 1 puan), yani TF/TF gezerken boşluk "zıplamıyor".
- Değişmeyenler: fiyat etiketleri/seviye çizgileri/🎯 hedef kutusu bu alana çizilir,
  OB/FVG kutuları ve bant çizgileri buraya kadar uzar, tuval 1080×810 kalır.

### 41.2 Doğrulama

- `pytest -q` → **1262 geçti, 44 atlandı** (yeni: `test_grafik_sag_bosluk.py`
  yüzde penceresi + öncelik sırası testleri; `test_grafik_faz_kullanici.py`
  `test_faz2_sag_bosluk_eksenin_yuzde_10_20`).
- Gerçek önbellekle ölçüm: GARAN 1s %10 → 9 mum (%10,1) · %15 → 14 mum (%14,9) ·
  %20 → 20 mum (%20,0); AKBNK 4s %10 → 8 mum (%10,5) · %15 → 12 mum (%15,0) ·
  %20 → 17 mum (%19,9). Üç oranda da `mum_cakisan == 0`.
- Karşılaştırma aracı: `scripts/grafik_sag_bosluk_karsilastirma.py`
  (`--kare GARAN:1h --kare AKBNK:4h --oranlar 0.10,0.15,0.20`) — botun kendi
  `kare_uret` yolunu çağırır, satır = oran / kolon = kare tek sayfa üretir.
  Turun çıktısı: `docs/ornek_sag_bosluk_oran.png` (üç oran × iki kare);
  `docs/ornek_kare_faz1_4_1s.png` ve `_4s.png` yeni varsayılanla yenilendi
  (14 ve 12 mum boşluk, `mum_cakisan == 0`).

## 42 · YÖNLÜ RVOL ROZETİ (2026-10-16) — `⚡↑` patlama / `⚡↓` kuruma

Kullanıcı: *"hacim olayını yukarda gösteriyoruz ya, onun pozitif artış veya negatif
olduğunu anlaşılacak şekilde bir düzeltme de yapar mısın … ani artış olduğunda
sadece x3.0 yazıyor ama ani düşüş olduğunda x0.5 yazmıyor"*. Doğru tespit: rozet
tek yönlüydü (yalnız `RVOL > 2,0`), hacim KURUMASI karede hiç görünmüyordu.

### 42.1 Kural

| Durum | Koşul | Rozet | Renk |
| :--- | :--- | :--- | :--- |
| Hacim patlaması | `RVOL > 2,0` (`rvol_rozet_esik`) | `⚡↑ x2,5` | `#31b184` (yeşil) |
| Hacim kuruması | `RVOL ≤ 0,5` (`rvol_rozet_esik_dusuk`) | `⚡↓ x0,5` | `#e05c58` (kırmızı) |
| Hacimsiz bar | `v = 0` / `None` | rozet YOK | — (kart dipnotu: `veri: N bar hacimsiz`) |

- **Yön okla taşınır, renk yalnız pekiştirir** (§0.4.1: renk tek başına bilgi
  taşımaz). Çipin kenarlığı da yön rengini alır.
- **Metin 2 basamak + sıfır kırpma** (`_rvol_katı`): `x2,5` · `x0,5` · `x0,96`.
  Tek basamak `x0,96`ı `x1,0` yapardı — kuruma "normal" görünürdü (yanlış bilgi);
  `x2,04` de eşikle çelişmesin diye `x2,0` değil `x2,04` yazılır.
- **Kuruma rozeti TAVANLI: `rvol_rozet_dusus_maks` = 2.** Kullanıcı ikinci turda
  sınırı koydu: *"çok fazla etiket olmamalı, bu sebepten en fazla 2 tane
  ekleyebiliriz"*. Ölçüm haklıydı: kural ilk yazıldığında sakin 4s karelerinde
  ↓7'ye kadar çıkıyordu (GARAN/TUPRS/AKBNK 4s). En sert iki kuruma seçilir,
  patlamalar kalan bütçeyi doldurur.
- **Bütçe paylaşımı.** Aday havuzu: tüm patlamalar + en sert 2 kuruma; sıra
  `|log(RVOL)|` mantığıyla sertliğe göre (patlamada `v`, kurumada `1/v`). Neden
  sertlik sırası: tamamen kuruma ağırlıklı bir sıralamada belirgin bir hacim
  patlaması (x2,2) kareden atılıyordu — asıl sinyal (kırılımı hacmin teyidi)
  kaybolurdu. Havuz KIRPILMAZ: aralık kuralı eledikçe sıradaki mum devreye girer
  (kırpma + aralık birlikte rozet sayısını 8'den 2'ye düşürüyordu).
- **Komşuluk yarıçapı bar değil piksel:** `ceil(0,5 × rozet_px / px_per_bar) + 1`.
  Sabit ±4 bar, 120 mumluk 4s karesinde (px/bar ≈ 5,8) rozeti komşu gövdenin 1 px
  yanına koyuyordu ve `mum_cakisan` kapısı kırmızı yanıyordu.
- **Eşikler ve tavan ortamla ayarlanır:** `GRAFIK_RVOL_ROZET_ESIK` (2,0),
  `GRAFIK_RVOL_ROZET_ESIK_DUSUK` (0,5), `GRAFIK_RVOL_ROZET_DUSUS_MAKS` (2;
  `0` = kuruma rozeti kapalı). Kuruma rozeti yine gürültülü gelirse eşiği 0,35
  yapın ya da tavanı 1'e indirin.
- **Sağ boşluk %15'te kalıyor** (kullanıcı onayı): `sag_bosluk_orani` 0,15;
  pencere %10-20 yalnız otomatik kuralda kırpar.

`meta["serit"]`: `rozet` (toplam) + `rozet_artis` + `rozet_dusus` sayaçları —
hangi yönden kaç rozet çıktığı sessizce kaybolmaz, ölçümle doğrulanır.

### 42.2 Doğrulama

- `pytest -q` → **1267 geçti, 44 atlandı** (yeni: iki yön, eşik sınırı, hacimsiz
  bar, metin yuvarlaması, bütçe payı, ortam eşikleri).
- Gerçek önbellek (tavan sonrası), 11 karede `mum_cakisan == 0`: GARAN 1s `↑3 ↓2` ·
  GARAN 4s `↑4 ↓2` · TUPRS 4s `↑4 ↓2` · AKBNK 4s `↑1 ↓2` · THYAO 4s `↑1 ↓2` ·
  SASA 1s `↑5 ↓1` · KCHOL 1s `↑3 ↓1` · EREGL 1g `↑0 ↓2`. Kare başına rozet
  sayısı 8 → 3-6'ya indi (kullanıcı: "çok fazla etiket olmamalı").
- Yakın plan doğrulama sayfası: rozetler 1s karede okunur, çipler mumların üstüne
  binmiyor (komşuluk yarıçapı düzeltmesi öncesi/sonrası ölçüldü).
### 42.3 Tazelik önceliği (2026-10-16, ikinci tur)

Kullanıcı: *"bu sistem sadece geçmişi filtreler, yeni geleni geciktirebilir, onu bir
sisteme oturt, yine 3-6 kalsın"*. Doğru teşhis: seçim tamamen sertlik sıralamasıydı,
yani pencereye yeni giren mum eskilerin arasında kaybolabiliyordu.

**Kural:** her yönün **EN YENİ** uygun mumu rozet alır; eskiler kalan yerleri
sertliğe göre doldurur. Taze aday yerleşim listesinde ÖNDE olduğu için onu ne
`rvol_rozet_ara` (aralık) ne `rvol_rozet_maks` (bütçe) düşürebilir.

| Ölçüm | Kural öncesi | Kural sonrası |
| :--- | :--- | :--- |
| GARAN 4s (68 mum) | son uygun bar **çizilmedi** (son bar x0,16) | taze ↓ bar 67 = son bar, çizildi |
| THYAO 4s | son uygun bar **çizilmedi** (x0,18) | taze ↓ bar 67 çizildi |
| AKBNK 4s | son uygun bar **çizilmedi** (x0,17) | taze ↓ bar 67 çizildi |
| GARAN 1s | son uygun bar **çizilmedi** (x0,47) | taze ↓ bar 75 çizildi |

- Ölçüm kanıtı kodda: `_rvol_rozetleri` çizilen barları küme olarak tutar ve
  `meta["serit"]["rozet_taze_artis"] / ["rozet_taze_dusus"]` alanlarına **gerçekten
  çizilen** taze barı yazar (varsayım değil, ölçüm).
- Taze kuruma kotaya uyar: `GRAFIK_RVOL_ROZET_DUSUS_MAKS=0` ise kuruma rozeti
  (taze olan dahil) yazılmaz — kaçış kapısı sürpriz üretmez.
- **Toplam tavan 8 → 6** (`rvol_rozet_maks`): tazelik garantisi bir rozet daha
  eklediği için ölçülen üst sınır 7'ye çıkmıştı (AKBNK 4s 120 mum). Yeni tavanla
  kare başına rozet **3-6** aralığında kalıyor (kullanıcı: "yine 3-6 kalsın").
- Ölçüm (11 gerçek kare, hepsinde `mum_cakisan == 0`): GARAN 4s 6 · TUPRS 4s 6 ·
  AKBNK 4s (120 mum) 6 · GARAN 1s 5 · AKBNK 4s 4 · THYAO 4s 3 · SASA 1s 6 ·
  EREGL 1g 2 · KCHOL 1s 4 · BIMAS 4s 4 · PGSUS 4s 5. Taze izler: GARAN 1s ↑18 ↓75 ·
  AKBNK 4s ↑33 ↓67 · THYAO 4s ↑48 ↓67.
- Kapatma: `test_grafik_faz_kullanici.py::test_faz1_taze_*` (5 test) ve
  `test_faz1_gercek_karede_son_mumun_rozeti_cizilir` (canlı önbellek kapısı);
  tam paket `pytest -q` → **1275 geçti, 44 atlandı**.

