# FORMATION-BOT MASTER PROMPT — GELİŞTİRME / SOHBET MODU

> Bu belge, bu projeyi başka bir AI oturumu ile sıfırdan konuşmak için hazırlanmıştır. 
> Dal adı (branch) veya commit bilgisi burada YOKTUR — sadece proje yapısı, matematik, açık işler ve geliştirme amacı vardır. 
> Amaç: sohbet ederek geliştirme yapmak — 100 hisse genişletmesi, XU100 eklenmesi, Telegram kanal akışı, haftalık genişlik raporu.

---

## 1. PROJE KİMLİĞİ (Yapısal — Dal/Commit Yok)

**Ad:** Formation-Bot  
**Repo:** `keremtulu44/Formation-Bot`  
**Dil:** Python 3.12 (`.python-version` sabit; `pandas` ve `numpy` için `cp314` tekerleği yok, 3.14'te build patlıyor)  
**Amaç (kullanıcı):** Bir kitle için Telegram kanalı oluşturmak. Al-sat motoru değil — formasyon/bilgi paylaşan, açıklayıcı bir sistem. 100 hisseye genişletmek, XU100 eklemek, haftalık toplam artış/düşüş çıktıları vermek.

---

## 2. MATEMATİKSEL ALTYAPI — FORMASYON MANTIĞI (Çok Ayrıntılı)

### 2.1 Temel Kavram: Pivot Geometrisi

Formasyon = 2 üst pivot + 2 alt pivot. 4 pivot noktası vardır. Her pivot bir `(bar_index, fiyat)` çifti.

```
hb1, hp1 = ilk üst pivot (bar_index, fiyat)
hb2, hp2 = ikinci üst pivot
lb1, lp1 = ilk alt pivot
lb2, lp2 = ikinci alt pivot
```

**Kronolojik koşul (zorunlu):**
- `hb1 < lb1 < hb2 < lb2` (üst-alt-üst-alt sırası) VEYA
- `lb1 < hb1 < lb2 < hb2` (alt-üst-alt-üst sırası)

Neden? Pivotlar sırayla oluşmalı; rastgele değil, zaman içinde gelişmeli.

**TopAbove koşulu:**
- `upperStart > lowerStart` (başlangıçta üst sınır alt sınırın üstünde)
- `upperNow > lowerNow` (şu anda da aynı durum)

Eğer `TopAbove` sağlanmazsa formasyon reddedilir.

---

### 2.2 Eğim Hesaplaması (Slope)

Her pivot çiftinden bir doğru geçer. Eğim (`slope`) fiyat farkının bar farkına bölünmesiyle hesaplanır.

```
upperSlope = (hp2 - hp1) / (hb2 - hb1)
lowerSlope = (lp2 - lp1) / (lb2 - lb1)
```

**Neden normalize edilir?** THYAO 300 TL, GARAN 100 TL — aynı açısal eğim, farklı fiyat seviyelerinde farklı görünür. ATR (`Average True Range`) ile normalize edilince karşılaştırılabilir hale gelir.

```
geometryAtr = ATR(serinin son N barı — genellikle 14)
upperSlopeNorm = upperSlope / geometryAtr
lowerSlopeNorm = lowerSlope / geometryAtr
slopeGapNorm = upperSlopeNorm - lowerSlopeNorm
```

`geometryAtr` fiyat bağımsız bir ölçek sağlar. `upperSlopeNorm` = `0.024` → yatay anlamına gelir (fiyatın %2.4'ü kadar eğim).

---

### 2.3 Yataylık, Yön ve Paralellik Eşikleri (Dengeli Profil)

`config.py` içinde tanımlı `BOT_PROFILE` (Dengeli / Hassas / Seçici) bu eşikleri değiştirir. Varsayılan `Dengeli` değerleri:

```
flatSlopeNormTol        = 0.024     # |slopeNorm| <= 0.024 => yatay
minSlopeNormTol         = 0.006     # minimum eğim (bu altındaki eğim ihlal sayılır)
parallelSlopeNormTol    = flat * 0.75 = 0.018   # paralel kanal için
```

**Yataylık (`horizontal`):**
- `horizontalUpper`: `abs(upperSlopeNorm) <= flatSlopeNormTol`
- `horizontalLower`: `abs(lowerSlopeNorm) <= flatSlopeNormTol`

**Kesin yön (`strict`):**
- `strictUpperDown`: `upperSlopeNorm < -flatSlopeNormTol`
- `strictUpperUp`: `upperSlopeNorm > flatSlopeNormTol`
- `strictLowerUp`: `lowerSlopeNorm > flatSlopeNormTol`
- `strictLowerDown`: `lowerSlopeNorm < -flatSlopeNormTol`

**Paralellik (`parallelLike`):**
```
abs(slopeGapNorm) <= parallelSlopeNormTol   # 0.018
```
Eğer `slopeGapNorm` sıfıra yakınsa, üst ve alt çizgiler paraleldir (kanal).

**Daralma (`converging`):**
```
startWidth = upperStart - lowerStart
currentWidth = upperNow - lowerNow
contraction = (startWidth - currentWidth) / startWidth
```
- `startWidth > 0` (başlangıçta genişlik pozitif olmalı)
- `currentWidth > 0` (şu an da pozitif)
- `contraction >= minContraction` (`0.25` — %25 daralma)
- `slopeGapNorm < -0.006` (eğim farkı negatif → üst çizgi alt çizgiden daha az eğimli, yani daralıyor)

**Paralellik (`parallelLike`)** için `abs(slopeGapNorm) <= 0.018`.

---

### 2.4 Apex (Üçgen Ucu) Hesaplaması

Üst ve alt çizgilerin kesiştiği nokta. Geometrik olarak:

```
apexFloat = startBar - startWidth / slopeGap
apexBar   = yuvarla(apexFloat)
```

`startBar` = formasyonun başlangıç bar indeksi. `startWidth` = başlangıç genişliği (fiyat). `slopeGap` = `upperSlope - lowerSlope` (normalize edilmemiş veya normalize edilmiş, hesaplama bağlamına göre).

`apexBar` üçgenin ne zaman tamamlanacağını tahmin eder. Eğer `apexBar` çok yakınsa (`age` küçükse) formasyon henüz olgunlaşmamış olabilir.

---

### 2.5 Yaş ve Dokunuş Koşulları (`touchBasics`)

Bir formasyonun geçerli olması için:

- `chronological` = `True` (pivot sırası doğru)
- `bar_index >= knownBar` (son pivot teyit edilmiş — `data.py` içindeki `tamamlanmis_mumlar()` motoru)
- `topAbove` = `True`
- `age >= max(5, minAge / 2)` — Dengeli profilde `minAge = 16` → en az `8` bar
- `upperTouches >= 2` ve `lowerTouches >= 2` (en az 2 temas üst, 2 temas alt)
- `touchDistribution`: en az 4 temas toplam, ve son temas `start`'tan yeterince uzak

---

### 2.6 Kalite Katsayıları (Kritik — Değiştirilmedi)

**Döküman (`FORMASYON_MANTIGI.md` / `PINE_FARK_ANALIZI.md`):**
```
0.28 / 0.20 / 0.12 / 0.16 / 0.12 / 0.07 / 0.05
```

**Python kod (`patterns/` içinde):**
```
0.26 / 0.18 / 0.12 / 0.20 / 0.10 / 0.07 / 0.07
```

**Durum:** `PINE_FARK_ANALIZI.md` §5'te 12 maddelik doğrulama listesi var. `Pine` (`ARGENT v0.4.6` export — `Yeni Metin Belgesi.txt`) henüz bu ortamda bulunmadı. `PINE_FARK_ANALIZI.md`'de belirtilen 12 doğrulama maddesi açılmadan bu katsayılar **değiştirilmez**. Bu, `YAPILACAKLAR.md`'de açık bir kuraldır.

---

### 2.7 Formasyon Tipleri (Geometriye Göre)

Formasyon tipi, `upperSlope` ve `lowerSlope`'un yatay/yukarı/aşağı kombinasyonuna göre sınıflandırılır:

- **Yükselen Üçgen:** Üst yatay (`upperSlope` ≈ 0), alt yukarı (`lowerSlope > 0`)
- **Alçalan Üçgen:** Üst aşağı (`upperSlope < 0`), alt yatay (`lowerSlope` ≈ 0)
- **Simetrik Üçgen:** Üst aşağı, alt yukarı (`upperSlope < 0`, `lowerSlope > 0`) — daralıyor (`converging`)
- **Kema:** Üçgen benzeri ama `parallelLike` değil; genellikle daha geniş açı

`patterns/candidate.py` içinde `f_build_candidate` mantığı bu sınıflandırmayı yapar. `patterns/pivots.py` pivotları bulur; `patterns/pole.py` bayrak/flama için `direk` (pole) hesaplar.

---

## 3. DOSYA YAPISI — MATEMATİKSEL KATMANLAR (Çok Ayrıntılı)

```
Formation-Bot/
├── .env                           # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SUPABASE_URL,
│                                  # SUPABASE_SERVICE_ROLE_KEY, BOT_PROFILE (Hassas/Dengeli/Seçici),
│                                  # STOCK_UNIVERSE (virgülle ayrılmış semboller), MARKET_SUFFIX,
│                                  # LOG_DIR, DATA_DIR, SEED_DATA_DIR, SESSION_OPEN/CLOSE
├── .env.example
├── .python-version                # 3.12
├── requirements.txt               # pandas, numpy, pytz, yfinance
│
├── README.md                      # 24194 bayt; tam durum tablosu (Faz 1-5, batch 1-8),
│                                  # test sonuçları (305 pytest passed), canlı tarama açıklaması,
│                                  # Pine karşılaştırma rehberi
├── FORMASYON_MANTIGI.md           # Pine v0.4.6 matematiksel açıklama; 4 pivot, slope, contraction, apex
├── PINE_FARK_ANALIZI.md           # Çalışma defteri; 12 maddelik doğrulama listesi; kalite katsayı farkı;
│                                  # beklenen Pine dosyası (`Yeni Metin Belgesi.txt`) henüz gelmedi
├── KODLAMA_PLANI.md               # Batch planı; her batch: kapsam / dosya / test / kabul kriteri
├── YAPILACAKLAR.md                 # A (düzeltme) / B (iyileştirme) / C (şablon) — tam iş listesi,
│                                  # öncelik (★★★/★★/★), efor (1s / K / O / B)
├── SORUN_RAPORU.md                 # Ölçümlü teşhis; S1-S11 + ek bulgular; üretim→Telegram hunisi
├── docs/archive/DOGRULAMA_RAPORU.md  # Dış teşhis bağımsız doğrulaması (TRUE / FALSE / PARTIAL) — arşivde
│
├── config.py                      # Merkezi yapılandırma (TEK KAYNAK):
│                                  # - BIST_50 = [48 sembol; KOZAL/KOZAA çıkarıldı]
│                                  # - STOCK_UNIVERSE env (özel evren — 100 hisse eklenebilir)
│                                  # - ACTIVE_STOCKS = _STOCK_UNIVERSE or BIST_50
│                                  # - BOT_PROFILE (Dengeli varsayılan)
│                                  # - SCAN_* pacing ayarları (batch size, delay, pause, retry backoff)
│                                  # - TFLER = ["1h", "2h", "4h", "1d"]
│                                  # - ALERT_STATES (4 anlık olay), WATCH_STATES (6 izleme),
│                                  #   PUBLIC_STATES, PUBLIC_MIN_QUALITY_TF
│                                  # - KARNE_* ayarları (HEDEF_ATR=1.5, STOP_ATR=1.0, HORIZON_BAR=10)
│                                  # - EVREN_BUYUME_UYARI_ESIGI = 48 (100 hisse için güncellenmeli)
│                                  # - POST_CLOSE_ANALYSIS_TIME = "20:00"
│                                  # - DATA_DIR, SEED_DATA_DIR, LOG_DIR
│                                  # - BIST açık/kapanış saatleri (09:50 / 18:10)
│                                  # - ISTANBUL_TZ (Europe/Istanbul)
│                                  # - BIST_YARIM_GUNLER, BIST_TATILLER (takvim)
├── data.py                        # Veri motoru:
│                                  # - fetch_yfinance (Yahoo .IS sembol desteği; seri, paralel değil)
│                                  # - tamamlanmis_mumlar() (kapalı mum filtresi; sadece kapanmış mumlarla besler)
│                                  # - bar_kapandi_mi() (kapalı mum güvenlik kapısı)
│                                  # - is_bist_open() (09:50-18:10 + hafta sonu; tatili BİLMİYOR — A2 kısmen açık)
│                                  # - tarama_penceresi_acik_mi() (tatili BİLİYOR — `bist_tatil_adi()` kullanıyor)
│                                  # - islem_gunu_mu() (tatil + hafta sonu kontrolü)
│                                  # - time_until_next_open() (bir sonraki açılışa kadar saniye; uyku için)
│                                  # - yarim_gun_kapanisi() / seans_kapanis_saati() (yarım gün: 13:00)
│                                  # - bist_tatil_adi() (resmi tatil listesi + Diyanet takvimi)
│                                  # - StockDequeManager (derin deque, 500 bar 1D)
├── main.py                        # 2380 satır (batch-8 sonrası — `main.py` katmanlara ayrıldı):
│                                  # - Ana döngü (tarama + digest + public grup + heartbeat)
│                                  # - `son_tarama_yukle()` çağrısı (`main.py:2624` — A1 çözüldü)
│                                  # - `/panel` komutu (`reporting/panel.py` bağlamı)
│                                  # - `/tara [HISSE]` komutu (seans dışı analiz)
│                                  # - `/karne` komutu (`karne.py`)
│                                  # - `_haftalik_karne_ekle()` (Cuma gün sonu mesajına eklenir)
│                                  # - Digest tamponu (`telegram_alert_flow.py` ile entegre)
│                                  # - `LIVE_STATE` (`live_state.py` — snapshot/hydrate)
│                                  # - Heartbeat (`health_server.py` ile senkron)
│                                  # - `patterns_found` metrik (A9 — yanıltıcı olabilir; slot tekrar sayacı)
├── notifier.py                    # Telegram bildirim katmanı:
│                                  # - `Notifer` sınıfı (DM + public grup)
│                                  # - `_istanbul()` (naive datetime normalize — A4 çözüldü)
│                                  # - `_gunluk_tarih`, `_gunluk_sayac` (günlük sınır)
│                                  # - `_saatlik_zamanlar` (saatlik sınır — son 1 saat)
│                                  # - `_gunu_sifirla_gerekirse()` (`ISTANBUL_TZ` kullanıyor — A4 çözüldü)
│                                  # - `kap_durumu()` (canlı sınır durumu — `/durum` okur)
│                                  # - `send_text()` (4096 sınır + `kirp()` — A5 çözüldü; retry mantığı)
│                                  # - `_build_active_formations_for_summary()` (günlük özet)
│                                  # - `_public_kuyruk` (public grup kuyruğu — tur sonunda TEK bülten)
│                                  # - `public_max_saatlik` / `public_max_gunluk` (bütçe sınırları)
│                                  # - `public_min_aralik_sn` (minimum aralık)
│                                  # - `public_enabled` (`TELEGRAM_GROUP_ID` + token)
│                                  # - `public_hedef_bilgi` (kanal doğrulama önbelleği)
│                                  # - `_public_durum_yukle()` (restart sürekliliği — B3 ile entegre)
│                                  # - `_gonderim_sagligi_kaydet()` (başarı/hata kaydı — A6 çözüldü)
│                                  # - `should_send_to_public()` (`SIKISMA_GUCLENIYOR` dalı — A3 açık)
├── telegram_alert_flow.py         # Digest / Erteleme / Acil Kuyruk:
│                                  # - `WATCH_STATES` (18:45 kapanış özetine ertelenen 6 izleme durumu)
│                                  # - `ALERT_STATES` (anında push edilen 4 kritik olay)
│                                  # - `DEFERRED_ALERT_DIGEST_LIMIT`
│                                  # - `ACIL_KUYRUK_TTL_DK` (varsayılan 180 dk)
│                                  # - `digest_pending` (`state:digest_pending` — kalıcı — B3 çözüldü)
│                                  # - `telegram_acil_kuyruk` (`state:telegram_acil_kuyruk` — kalıcı)
│                                  # - Açılışta `hydrate()` (kaçırılan özet telafisi)
├── telegram_commands.py            # Slash komutları:
│                                  # `/formasyonlar`, `/formasyonlar 1h`, `/formasyonlar THYAO`
│                                  # `/canli`, `/c` (kompakt canlı liste)
│                                  # `/panel`, `/p`, `/genel`, `/tablo` (48 sembol x 4 TF slot tablosu)
│                                  # `/ozet`, `/o` (günlük özet — tamamlanan/retest/sıkışan)
│                                  # `/durum` (piyasa, tarama yaşı, veri sağlığı, günlük alarm/hata)
│                                  # `/tara [HISSE]` (seans dışı; mum kapanışını beklemez)
│                                  # `/karne`, `/karnem`, `/karne 30` (son N gün)
│                                  # `/yardim`
│                                  # Not: aynı token'la ikinci kopya (`Termux` + PC) çalışıyorsa `409 Conflict` alır.
├── reporting/
│   ├── format.py                  # Metin/sayı üretimi (8.1) — saf fonksiyonlar
│   └── panel.py                   # Panel raporu (8.3) — bağlam ile (hisse, TF, filtre)
├── patterns/
│   ├── candidate.py               # `f_build_candidate()` — geometri + bayrak/flama sınıflandırma
│   ├── pivots.py                  # Pivot hesaplama (`f_chronological_swings`, `f_find_pivots`)
│   ├── pole.py                    # `f_pole()` — bayrak/flama direği (yön, süre, büyüklük, kalite)
│   ├── lifecycle.py               # State makinesi (`ADAY_OLUSUYOR` → `TEYITLI` → `KIRILIM_ADAYI` → `KIRILIM_TEYITLI` → `RETEST_BASARILI` / `BASARISIZ` → `TAMAMLANDI`)
│   ├── violation.py               # Kural ihlali (`ST_GEOMETRY`, `ST_WEAK` — A5 açık maddeleri)
│   ├── selection.py               # Aday seçimi (`f_select_best_candidates`)
│   └── mathutil.py                # Matematiksel yardımcılar (`normalize`, `clamp`, `percent_change`)
├── karne.py                       # Haftalık doğruluk karnesi:
│                                  # - `karne_defteri.json` (`DATA_DIR` — atomik yazım, tek dosya)
│                                  # - `DURUM_HEDEF` (`hedefe ulaştı`), `DURUM_STOP` (`stop oldu`), `DURUM_NOTR` (`nötr kaldı`), `DURUM_OLCULEMEDI`
│                                  # - `KARNE_HEDEF_ATR` = 1.5, `KARNE_STOP_ATR` = 1.0, `KARNE_HORIZON_BAR` = 10
│                                  # - `atr_hesapla()` (14 bar ATR; giriş anında saklanır)
│                                  # - `hafta_damgasi()` (`2026-W40` — ISO hafta anahtarı)
│                                  # - `karne_gunu_mu()` (varsayılan Cuma; `KARNE_GUNU` env)
│                                  # - `_dizine_konum()` (bar damgasının serideki konumu)
│                                  # - Her Cuma gün sonu (`18:45`) mesajının ALTINA eklenir
│                                  # - `/karne` komutuyla anlık alınabilir
├── live_state.py                  # `LiveState` sınıfı:
│                                  # - `snapshot()` / `hydrate()` (son tarama durumu)
│                                  # - `get_formations()` / `formations()` (canlı formasyon listesi)
│                                  # - `state:son_tarama` (Supabase yedek — opsiyonel)
├── deploy_check.py                # Kurulum doktoru (`--url`, `--test-key`):
│                                  # - Token biçimi (`token_bicimi_uygun_mu`)
│                                  # - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
│                                  # - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
│                                  # - `TELEGRAM_GROUP_ID` (kanal/grup doğrulama)
│                                  # - `RENDER_EXTERNAL_URL` (webhook adresi)
│                                  # - `/health` (her zaman 200; `strict=1` → 503 eğer heartbeat bayat)
│                                  # - `/test` (`TELEGRAM_TEST_KEY` tanımlıysa gerçek test mesajı)
│                                  # - `/webhook` (`TELEGRAM_WEBHOOK_SECRET` başlık doğrulama)
├── health_server.py               # `HealthServer` (`ThreadingHTTPServer`, `0.0.0.0`):
│                                  # - `/health` (JSON: `heartbeat_age_s`, `heartbeat_stale`, `tarama_suruyor`, `seans_acik`)
│                                  # - `/test?k=<TELEGRAM_TEST_KEY>` (gerçek Telegram test mesajı; 404 yoksa)
│                                  # - `/webhook/<secret>` (`X-Telegram-Bot-Api-Secret-Token` başlığı)
│                                  # - `/durum` (`/durum` komutunun web karşılığı)
│                                  # Not: `ThreadingHTTPServer` sınırsız thread; rate limit yok (A7)
├── canli_tarama.py                # Canlı tarama raporu:
│                                  # - `ACTIVE_STOCKS` (48 sembol) x `TFLER` (4 TF) tarama
│                                  # - Çıktı: her formasyon için tip, kalite, state, üst/alt çizgi seviyeleri,
│                                  #   daralma %, başlangıç tarihi, `Pine varyanti` (standart/eğik),
│                                  #   `Direk` (yön/süre/büyüklük/kalite), `Flama olculeri` (derinlik, yükseklik/süre oranı)
│                                  # - `PINE KARSILASTIRMA REHBERI` rapor sonunda
│                                  # - `--cache` modu (`bot_data/` JSON'leri)
│                                  # Not: `Pine` ekranında eski `TAMAMLANDI`/`BASARISIZ` formlar kalabilir;
│                                  # rapor yalnız canlı olanları listeler.
├── bot_data/                      # Git-tracked JSON cache'leri (`.pkl` artık dışarıda — A8):
│                                  # - Her sembol için `1h` ve `1d` serileri
│                                  # - `SEED_DATA_DIR` (salt-okuma seed; repo dışı `DATA_DIR` varsayılanı)
│                                  # - `DATA_DIR` sırası: `RENDER` → `/tmp/formation-bot-data` → `/var/lib/formation-bot/data`
│                                  #   → `~/.formation-bot/data` → `./bot_data` (en son fallback)
├── state/                         # Runtime durum dosyaları (`.gitignore`'da):
│                                  # - `heartbeat.json` (tarama başına yazma amplikasyonu — B5)
│                                  # - `telegram_soguma.json` (cooldown)
│                                  # - `telegram_kap.json` (günlük/saatlik sınır)
│                                  # - `telegram_son_alerts.json` (tekrar koruması — `repeat-guard`)
│                                  # - `telegram_acil_kuyruk.json` (acil kuyruk — B4)
│                                  # - `telegram_digest_pending.json` (`digest_pending` — kalıcı)
│                                  # - `karne_defteri.json` (`DATA_DIR` — yerel, atomik)
│                                  # - `instances.json` (çoklu örnek tespiti — B10)
├── patterns/                      # Motor katmanı:
│                                  # - `candidate.py`: `f_build_candidate()` — 4 pivot, geometri hesaplama,
│                                  #   daralma, paralellik, `specialized_variant` (standart/eğik ayrımı)
│                                  # - `pivots.py`: Pivot tespiti (`f_find_pivots`, `f_chronological_swings`)
│                                  # - `pole.py`: `f_pole()` — bayrak/flama direği (`pole_height`, `pole_duration`, `pole_quality`)
│                                  # - `lifecycle.py`: State makinesi (`ADAY_OLUSUYOR` → ... → `TAMAMLANDI`)
│                                  # - `violation.py`: `ST_GEOMETRY` / `ST_WEAK` (A5 açık maddeleri — kod yolu yok)
│                                  # - `selection.py`: Aday seçimi (`f_select_best_candidates`)
│                                  # - `mathutil.py`: `normalize()`, `clamp()`, `percent_change()`
├── reporting/                     # Raporlama katmanı:
│                                  # - `format.py`: Saf metin/sayı üretimi (`format_panel_row`, `format_digest_row`)
│                                  # - `panel.py`: Panel raporu (`build_panel_context`) — bağlam ile (`hisse`, `TF`, filtre)
├── transport/                     # Ulaşım katmanı:
│                                  # - `telegram.py` (eğer ayrıldıysa; mevcut `notifier.py` + `telegram_commands.py`)
│                                  # Not: `main.py` 2582 → 2380 satıra indi; katman ayrımı: `reporting/`, `transport/`, `state/`
├── .github/workflows/
│   ├── ci.yml                     # Render eşdeğeri CI: Python 3.12, `pytest`, zamanlama regresyonu,
│                                  # `PORT` verilerek `/health` duman testi
│   ├── deploy.yml                 # Render Deploy Hook (`main` push)
│   └── keepalive.yml              # 5 dk aralık (`cron`), her gün 08:00-23:00 İstanbul (`TZ=Europe/Istanbul`)
│                                  # `/health` pingi; `KEEPALIVE_ALWAYS` (7/24 için)
│                                  # Not: `RENDER` Free 15 dk trafik yoksa uyur; 5 dk aralık pay bırakır.
│
├── RENDER_DEPLOY.md               # Render Free + Supabase + Telegram kurulum rehberi; `build` hatası (`cp314`),
│                                  # `keep-alive`, `PORT`, `TZ`, webhook (`RENDER_EXTERNAL_URL`)
├── PUBLIC_GRUP_HAZIRLIK.md         # Kamu grup hazırlığı; `TELEGRAM_GROUP_ID` bağımsız çalışır
├── KANAL_ACILIS_PAKETI.md         # Kanal açılış metinleri; açıklama, sabitlenmiş karşılama, `kanal_acilis.py`
├── LOCAL_SETUP.md                  # Yerel kurulum (`pip install`, `.env`, `TERMUX`)
├── acilis_metinleri.py             # Açılış metinleri (`SESSION_OPEN` / `SESSION_CLOSE` — C1)
├── kanal_acilis.py                # `--durum` (kuru çalışma, yazmaz) / `--uygula` (yazar)
└── supabase_schema.sql             # `state:...` anahtarları için JSONB şema (`state:karne_defteri`, `state:digest_pending`, vb.)

---

## 4. BUG / AÇIK DURUM (Dal/Commit Bağımsız — Sadece Durum)

Aşağıdaki tablo, bu projenin mevcut durumunu yansıtır. Çözülmüş olanlar zaten kodda; açık olanlar geliştirme için önceliklidir.

| ID | ★ | Açıklama (Matematiksel / Yapısal) | Dosya / Satır | Efor | Durum |
|---|---|---|---|---|---|
| A1 | ★★★ | `son_tarama_yukle()` çağrısı eksik (merge'de regresyon) | `main.py:2266-2270` | 1s | ÇÖZÜLMÜŞ (`main.py:2624`) |
| A2 | ★★★ | `is_bist_open()` (`data.py:100`) tatili (`bist_tatil_adi`) bilmez; `tarama_penceresi_acik_mi()` (`data.py:125`) biliyor. Ana uyku (`time_until_next_open`, `main.py:2515`) tatil gününde 0'a düşebilir. | `data.py:131-158`, `main.py:2515-2526` | K | KISMEN |
| A3 | ★★ | Ölü kod: `notifier.py:211` (`SIKISMA_GUCLENIYOR` iki yolda `False`), `main.py:2147` (`_live_state.get_formations()` — böyle metot yok; doğrusu `formations()`), `main.py:2166` (`'contraction': None`), `notifier.py:255` (`[:10]` hesaplanıp kullanılmaz), `notifier.py:582` (`FORMASYON_GECERSIZ` şablonu çağrılmıyor) | Çeşitli | K | AÇIK |
| A4 | ★★ | `datetime.now()` naive (`notifier.py`) — günlük/saatlik kap `03:00` sıfırlaması (`UTC` sunucu). | `notifier.py:144-393` | K | ÇÖZÜLMÜŞ (`_gunu_sifirla_gerekirse` `ISTANBUL_TZ` kullanıyor) |
| A5 | ★★ | `filter_same_bar_double_pivot` stub (`patterns/`); `local_break` TODO (`patterns/violation.py`); `ST_WEAK` / `ST_GEOMETRY` kod yolu yok (`A5` maddesi) | `patterns/` | K | AÇIK |
| A6 | ★★ | Mock `True` (`notifier.py:639-646`) — token yokken `send()` `True` döner; `alerts_sent` artar. Heartbeat temiz görünür. | `notifier.py`, `main.py` | K | ÇÖZÜLMÜŞ (`_gonderim_sagligi_kaydet`) |
| A7 | ★★ | `health_server.py`: `/test?k=` (URL'de sır) + `/webhook/<secret>`; `ThreadingHTTPServer` sınırsız thread, rate limit yok (`A7` maddesi). | `health_server.py` | K | AÇIK |
| A8 | ★★ | Git'te `.pkl` (28 adet) (`bot_data/`); `pickle.load` (`data.py:549`); `JSON` birincil (`load_from_disk`). `A8`: `.pkl` git'ten çıkarılmalı; okuma JSON'a sabitlenmeli. | `data.py`, `bot_data/*.pkl` | K | KISMEN (okuma JSON; `.pkl` git'te kalmış) |
| A9 | ★ | `patterns_found` slot-bazlı sayaç (`main.py:1848`) — aynı formasyon 4 TF'de tekrar sayılabilir; yanıltıcı metrik. | `main.py:1848` | 1s | AÇIK |
| A10 | ★ | Kap sayaçları (`notifier.py`) komut (`/durum`), özet (`/ozet`), digest (`WATCH_STATES`) gönderimlerini saymıyor; sadece `ALERT_STATES` sayılıyor gibi görünüyor. | `notifier.py:294-301` | K | AÇIK |
| B1 | ★★★ | "Bastırılan aday" sayacı (`main.py`) + `/durum` tek satır (`A4` düzeltmesiyle birlikte; `B1` ayrıca bastırılan aday metrik). | `main.py` | K | AÇIK (kısmen çözülmüş olabilir — `main.py`'de `bastirilan_aday` gibi bir metrik var mı kontrol edilmeli) |
| B2 | ★★★ | Digest şeffaflığı: `12/21` göster + limit env (`DEFERRED_ALERT_DIGEST_LIMIT`). | `main.py`, `telegram_alert_flow.py` | 1s | ÇÖZÜLMÜŞ (digest şeffaf; `DEFERRED_ALERT_DIGEST_LIMIT` env'de) |
| B3 | ★★ | Digest tamponu kalıcı (`state:digest_pending` + `DATA_DIR` dosya; açılışta `hydrate()`). | `telegram_alert_flow.py` | O | ÇÖZÜLMÜŞ |
| B4 | ★★ | Cooldown/kap engeline takılan acil olaylar için kuyruk + retry (`ACIL_KUYRUK_TTL_DK`, `telegram_acil_kuyruk`). | `notifier.py`, `telegram_alert_flow.py` | O | ÇÖZÜLMÜŞ (kuyruk kalıcı; `B5` yazma amplikasyonu ile entegre) |
| B5 | ★★ | Yazma amplikasyonu (`heartbeat` her taramada 48 istek; değişmeyen turda `0`). `content_fingerprint` + `heartbeat_throttle` ile `~50 istek / 2 MB` (değişmeyen tur `0`). | `data.py`, `main.py` | O | ÇÖZÜLMÜŞ (amplikasyon azaltıldı) |
| B6 | ★★ | Kalite eşiği altı adaylar için sayaç + panel satırı. | `main.py`, `reporting/panel.py` | K | AÇIK |
| B7 | ★★ | `WATCH_STATES` anlık/toplu kararı (`ALERT_STATES` ile kesişimi — `config._politika_hatalari` import anında yakalanır). `B7`: karar bekleyen davranış değişikliği. | `config.py` | K | AÇIK (karar bekleyen) |
| B8 | ★★ | Evren büyürse: pacing (`SCAN_*`), panel 3800 bütçe, digest/özet limitleri yeniden ölçülmeli (`EVREN_BUYUME_UYARI_ESIGI` güncellenmeli). | `main.py`, `config.py` | K | AÇIK (evren 48; 100 için güncellenmeli) |
| B9 | ★ | Public kanal/grup akışının netleştirilmesi (`SIKISMA_GUCLENIYOR` dalı — `notifier.py:211`). | `notifier.py` | K | AÇIK |
| B10 | ★ | Çoklu örnek koruması (`state:instances` + heartbeat/`/durum` uyarısı; webhook `409` yok; `SUPABASE_STORE_PREFIX` namespace eksik — eski anahtar okuma var, yeni yazımda `formation-bot:` ön eki eklendi). | `telegram_commands.py`, `supabase_store.py`, `main.py` | K | KISMEN (`instances` var; `namespace` eklendi) |
| C1 | ★★★ | `STOCK_UNIVERSE` env + `MARKET_SUFFIX` + `STOCK_UNIVERSE`; `LOG_DIR` env; `SESSION_OPEN`/`CLOSE` adları; 2027 tatil takvimi. | `config.py`, `data.py` | O | KISMEN (`STOCK_UNIVERSE`, `LOG_DIR`, `MARKET_SUFFIX`, `SESSION_*` env'de; `BIST_50` sabit; 2027 takvimi güncellenmeli) |
| C2 | ★★★ | `main.py` (2582 → 2380 satır) katmanlara ayrıldı (`reporting/format.py`, `reporting/panel.py`, `state/persistence.py`, `transport/telegram.py`, `state/paths.py`). `import main` yan etkisi kaldırıldı (`8.2`). | `main.py`, `reporting/`, `transport/`, `state/` | B | ÇÖZÜLMÜŞ (katman ayrımı tamamlandı) |
| C3 | ★★ | Supabase anahtarlarına proje namespace (`SUPABASE_STORE_PREFIX=formation-bot:`). Eski kayıtlar (`state:karne_defteri`) okunur; yeni yazımda ön ek eklenir (`supabase_store.py`). | `supabase_store.py`, `data.py` | K | ÇÖZÜLMÜŞ (`SUPABASE_STORE_PREFIX` varsayılan `formation-bot:`; eski kayıt iki turlu okunur) |
| C4 | ★★ | `DATA_DIR` repo dışına (`.gitignore` + `state/paths.py` + `state/persistence.py`). `SEED_DATA_DIR` salt-okuma. `bot_data/` git-tracked kalır (`JSON` yedek). | `.gitignore`, `config.py`, `state/` | K | ÇÖZÜLMÜŞ (`DATA_DIR` sırası tanımlı; `SEED_DATA_DIR` salt-okuma) |
| C5 | ★ | Test boşlukları (`is_bist_open` tatil testi; `digest` limit testi; `hydrate` açılış testi). | `test_*.py` | K | AÇIK (test kapsamı genişletilmeli) |
| C6 | ★ | Doküman/şema senkronu (`README` 90/90 → 199; eski dal adı; `state:son_tarama` şema). | `README.md`, `supabase_schema.sql` | 1s | AÇIK |
| C7 | ★ | Ölü kod/araç temizliği (`fetch_with_rate_limit`, mock demo, `repo_teshis.py`, `logrotate.conf`, `.ps1`). | Çeşitli | K | AÇIK (`repo_teshis.py`, `.ps1` hala var gibi görünüyor) |

**Regresyon:** `pytest` **305 passed**; `test_tarama_zamani.py` **100/100**; `test_pennant.py` **6/6**.

---

## 5. CANLI TEST / SANDBOX KISITI

Bu ortamdan (`Formation-Bot` sandbox) **Yahoo Finance** (`yfinance`) ve **Telegram** (`api.telegram.org`) erişimi **yok** (SSL / ağ blok). Bu, `README.md` §7'de açıkça belirtilmiştir.

Sonuç olarak:
- Gerçek zamanlı tarama (`python main.py`) bu ortamda çalışmaz.
- `python canli_tarama.py --cache` (`bot_data/*.json` kullanarak) çalışır.
- `python deploy_check.py --url ...` (`/health`, `/test`) çalışabilir (ağ erişimi yoksa sadece repo/env doğrulaması yapar).
- `python test_tarama_zamani.py` (`pytest`) tam çalışır.
- Gerçek bot testi (`TERMUX`, PC, `Render`) kullanıcının kendi makinesinde yapılmalıdır.

---

## 6. KULLANICININ AMACI — ÇOK AYRINTILI

> **Amaç:** Bir kitle için Telegram kanalı oluşturmak. Sistem bir al-sat motoru değil; formasyon tespiti (üçgen/kema/bayrak/flama) yapar, kalite puanı verir, kırılım teyit eder, retest takip eder, başarısız kırılım kaydeder, haftalık doğruluk karnesi üretir ve Telegram'dan (DM veya grup/kanal) bilgilendirir.

**Geliştirme hedefleri (kullanıcı tarafından ifade edilen):**

### 6.1 Evren Genişletmesi (48 → 100 Hisse)

Mevcut evren: `BIST_50` (`48` sembol; `KOZAL`, `KOZAA` çıkarıldı — `Yahoo` verisi sorunlu).

Genişletme yolu:
1. `STOCK_UNIVERSE` (`.env`) güncellenir:
   ```
   STOCK_UNIVERSE=THYAO,GARAN,...,(100 sembol)...,XU100
   ```
2. `config.py`'de `EVREN_BUYUME_UYARI_ESIGI` (`48`) → `100` güncellenir (`main.py` açılışta uyarı loglar).
3. `SCAN_REQUEST_BATCH_SIZE` (`varsayılan 10`) ve `SCAN_*` delay/pause değerleri (`SCAN_REQUEST_DELAY_MIN_SEC`, `SCAN_BATCH_PAUSE_MIN_SEC`) yeniden ölçülmeli (`B8`). `48` sembol için `96` istek (`1h` + `1d`); `100` sembol için `200` istek.
4. `SCANNING_PACING` (`data.py`) seri fetch (`parallel değil`); `10` istek sonrası `10-15` sn mola; `0.9-1.5` sn rastgele aralık. Bu, `100` sembol için tarama süresini önemli ölçüde uzatır (`B8`).
5. `PUBLIC_MAX_MESAJ_SAAT` (`6`), `PUBLIC_MAX_MESAJ_GUN` (`25`), `DEFERRED_ALERT_DIGEST_LIMIT` (`varsayılan?`) yeniden ölçülmeli. `100` sembol × `4` TF × `5` formasyon = `2000` aday; tek bültende (`public_kuyruk_limit` = `40`) sığmaz. `public_kuyruk_limit` artırılmalı veya `digest` filtrelemesi (`/durum` gibi) eklenmeli.
6. `EVREN_BUYUME_UYARI_ESIGI` (`48`) → `100` güncellenir (`main.py:836` — `config.py:425`).

---

### 6.2 XU100 Ekleme (Endeks Takibi)

`XU100` (`.XU100.IS` veya `XU100.IS` — `Yahoo` sembolü) şu şekillerde eklenebilir:

**A) Bağımsız tarama (`STOCK_UNIVERSE`):**
```
STOCK_UNIVERSE=...,XU100.IS
```
`XU100` kendi başına üçgen/kema/flama oluşturabilir (`patterns/candidate.py` geometri hesaplama fiyat bağımsız; `geometryAtr` normalize eder). `XU100` fiyatı (`~5000-15000 TL`) için `upperSlope`, `lowerSlope` aynı formüllerle çalışır.

**B) Karşılaştırmalı analiz (`patterns/comparison.py` gibi yeni katman):**
- Her formasyonun yönü (`yukarı` / `aşağı` — `lifecycle.py`) `XU100` `1d` trendi (`SMA` veya `slope`) ile karşılaştırılır.
- Örnek: `THYAO` bayrak (`yukarı`) + `XU100` (`yukarı`) = uyumlu (`güçlü` sinyal). `THYAO` (`yukarı`) + `XU100` (`aşağı`) = zıt (`zayıf` veya `dikkat` sinyal).
- Bu yeni bir `WATCH_STATES` dalı (`config.py`) veya `ALERT_STATES` (`zıt sinyal` gibi) olabilir.
- `patterns/comparison.py` yeni bir `patterns/` modülü olabilir: `compare_with_index()` (`XU100` serisini alır, `1d` `slope` hesaplar, her formasyon yönüyle karşılaştırır).

---

### 6.3 Haftalık Toplam Artış / Düşüş (Market Breadth / Genişlik)

Mevcut `karne.py` haftalık doğruluk karnesi (`karne_defteri.json`) şu metrikleri tutar:
- `formasyon` sayısı (`hisse/TF/formasyon` — `48` saat TTL ile tekilleştirme)
- `kırılım` (`giriş = teyit barının kapanışı`, `yön`, `kalite`, `ATR`)
- `olay`: `retest`, `tamamlanma`, `başarısız kırılım` (`huni` sayıları)
- `hedef` / `nötr` / `stop` (`ATR` bazlı; `KARNE_HEDEF_ATR=1.5`, `KARNE_STOP_ATR=1.0`, `KARNE_HORIZON_BAR=10`)
- `lehte` (`MFE`) / `aleyhte` (`MAE`) hareket (`ATR` normalize)
- `kırılım yönünde kapatan` oranı
- `TF` ve `kalite` performansı (`en iyi` / `en kötü` sinyal)
- `huni` sayıları (`retest`, `tamamlanma`, `başarısız`)
- `n < 30` uyarısı (`karne` istatistiksel güvenilirlik için `n` yeterli mi?)

**Genişletme (`GENISLIK` / `BREADTH`):**

`karne.py`'ye yeni bir fonksiyon (`haftalik_genislik()` veya `market_breadth()`) eklenebilir:

```python
def haftalik_genislik(defter_path: str, aktif_hisse_sayisi: int = 100) -> dict:
    # `karne_defteri.json`'dan son 7 gün (`ISO` hafta: `2026-W40`) olaylarını oku.
    # Çıktılar:
    # - "Bu hafta canlı formasyon sayısı"
    # - "Yukarı kırılım: X | Aşağı kırılım: Y"
    # - "Net pozitif hisse (yukarı - aşağı): Z"
    # - "Ortalama kalite (0-1): Q"
    # - "XU100 trend yönü: yukarı / aşağı / yatay"
    # - "Toplam artış yönlü formasyon: ... / Toplam düşüş yönlü: ..."
```

`notifier.py`'de `WATCH_STATES` içine `"GENISLIK"` veya `"BREADTH"` eklenir (`config.py`). `telegram_alert_flow.py` içinde `digest` (`18:45`) bu yeni durumu da içerebilir.

**Public grup (`TELEGRAM_GROUP_ID`) için tek bülten:**
```
📊 Haftalık Genişlik (100 Hisse) — 2026-W40
• Canlı formasyon: 87
• Yukarı kırılım: 52 | Aşağı kırılım: 35
• Net: +17
• Ortalama kalite: 0.34
• XU100: Yukarı (1D)
• En iyi sinyal: THYAO / Simetrik Üçgen / 0.91 kalite / Hedefe ulaştı
• En kötü sinyal: GARAN / Alçalan Kama / 0.18 kalite / Stop oldu
```

`main.py:2104` (`digest` şeffaflığı) zaten `12/21` gösteriyor (`DEFERRED_ALERT_DIGEST_LIMIT` ile sınırlı). `B2` (`digest` şeffaflığı) çözülmüş; `B3` (`digest` kalıcı) çözülmüş.

---

### 6.4 Kanal Açılışı (`kanal_acilis.py`)

`kanal_acilis.py --durum` (kuru çalışma, yazmaz) / `--uygula` (yazar) aracı:
- `KANAL_ACILIS_PAKETI.md`'deki metinleri (`açıklama`, `sabitlenmiş karşılama`) kullanır.
- `TELEGRAM_GROUP_ID` (`.env`) tanımlı olmalı.
- `TELEGRAM_BOT_TOKEN` (`.env`) tanımlı olmalı.
- `kanal_acilis.py` `bot`'u `yönetici` olarak gruba ekler (`TELEGRAM_GROUP_ID`); `kanal` için `channel` ID (`-100...`) kullanılır.
- `TELEGRAM_CHANNEL_ID` (`.env`) tanımlı değilse `kanal_acilis.py` `grup` olarak açar; `kanal` için `channel` ID eklenmeli.

`PUBLIC_GRUP_HAZIRLIK.md` bu süreci ayrıntılı açıklar.

---

### 6.5 Pacing ve Performans (`SCANNING_PACING` — `B8` Açık)

Mevcut (`48` sembol):
- `SCANNING_BATCH_SIZE` = `10`
- `SCANNING_DELAY_MIN` = `0.9` sn, `SCANNING_DELAY_MAX` = `1.5` sn (`0.9-1.5` rastgele)
- `SCANNING_BATCH_PAUSE_MIN` = `10` sn, `SCANNING_BATCH_PAUSE_MAX` = `15` sn (`10-15` mola)
- `SCANNING_RETRY_BACKOFF_MIN` = `30` sn, `SCANNING_MAX` = `60` sn

`100` sembol (`200` seri fetch — `1h` + `1d`):
- `SCANNING_BATCH_SIZE` = `20` (veya `48` için `10`; `100` için `15` gibi — ayarlanmalı)
- `SCANNING_BATCH_PAUSE_*` = `15-20` sn (`10` yerine)
- `SCANNING_DELAY_*` = `1.0-2.0` sn (`0.9-1.5` yerine — `Yahoo` rate limit daha katı olabilir)
- `SCANNING_RETRY_BACKOFF_*` = `45-75` sn (`30-60` yerine)

Ölçüm (`B5` — yazma amplikasyonu):
- `heartbeat` (`48` istek / `42 KB`) → `2` istek / `1.8 KB` (değişmeyen tur)
- `tarama` (`96` istek / `3.26 MB`) → `48` istek / `1.98 MB` (`seans içi`) → `0` istek (`değişmeyen tur`)
- `100` sembol için bu rakamlar `~2x` olur; `heartbeat` `~4` istek, `tarama` `~200` istek (`seans içi` `~100` istek).

---

## 7. CANLI TEST / SANDBOX KISITI (Ayrıntılı)

`README.md` §7:
```
Sandbox kısıtı: bu ortamdan Yahoo Finance ve Telegram'a erişilemiyor (SSL).
Gerçek zamanlı tarama ve canlı bot testi kullanıcının kendi makinesinde yapılmalı;
burada --cache modu ve commit'li bot_data kullanılır.
```

`main.py`'de `fetch_yfinance()` (`data.py`) `Yahoo` API'si (`https://query1.finance.yahoo.com`) çağırır. `TERMUX` veya `PC` ortamında bu erişim açıktır (`SSL` sertifikaları mevcut). `sandbox` (`arena` ortamı) `SSL` blok (`proxy` veya `firewall`) nedeniyle `Yahoo`'ya erişemez.

`deploy_check.py` (`--url`) bu durumu doğrular: `RENDER` sunucusu (`Render` Free) `Yahoo` erişimine sahip olabilir (`Render` `US` veya `EU` sunucuları) veya olmayabilir (`proxy` ayarı gerekebilir). `deploy_check.py` `RENDER_EXTERNAL_URL` (`https://...`) üzerinden `/health` (`200`) ve `/test` (`TELEGRAM_TEST_KEY` tanımlıysa gerçek mesaj gönderir) doğrular.

`bot_data/*.json` (`git-tracked`) `SEED_DATA_DIR` (`salt-okuma`) ve `DATA_DIR` (`canlı yazım`) arasında ayrım yapılır (`C4`). `sandbox`'ta `DATA_DIR` (`./bot_data`) kullanılır (repo dışına çıkmaz). `RENDER`'da `/tmp/formation-bot-data` kullanılır (`C4`).

---

## 8. MATEMATİKSEL FORMÜLLERİN ÖZET TABLOSU (Kopya İçin Hazır)

| Formül / Eşik | Değer (Dengeli) | Açıklama | Kaynak Dosya |
|---|---|---|---|
| `upperSlope` | `(hp2 - hp1) / (hb2 - hb1)` | Üst çizgi eğimi (bar farkına bölünmüş fiyat farkı) | `FORMASYON_MANTIGI.md` §2.2 |
| `lowerSlope` | `(lp2 - lp1) / (lb2 - lb1)` | Alt çizgi eğimi | `FORMASYON_MANTIGI.md` §2.2 |
| `geometryAtr` | `ATR(14)` veya `ATR(N)` | Fiyat bağımsız ölçek (`Average True Range`) | `FORMASYON_MANTIGI.md` §2.2 |
| `upperSlopeNorm` | `upperSlope / geometryAtr` | Normalize edilmiş üst eğim | `FORMASYON_MANTIGI.md` §2.2 |
| `lowerSlopeNorm` | `lowerSlope / geometryAtr` | Normalize edilmiş alt eğim | `FORMASYON_MANTIGI.md` §2.2 |
| `slopeGapNorm` | `upperSlopeNorm - lowerSlopeNorm` | Eğilim farkı (normalize edilmiş) | `FORMASYON_MANTIGI.md` §2.2 |
| `flatSlopeNormTol` | `0.024` | Yataylık eşiği (`Dengeli`) | `FORMASYON_MANTIGI.md` §2.1, `config.py` |
| `minSlopeNormTol` | `0.006` | Minimum eğim (`Dengeli`) | `FORMASYON_MANTIGI.md` §2.1, `config.py` |
| `parallelSlopeNormTol` | `0.018` (`0.024 * 0.75`) | Paralellik (`Dengeli`) | `FORMASYON_MANTIGI.md` §2.1, `config.py` |
| `startWidth` | `upperStart - lowerStart` | Başlangıç genişliği (fiyat) | `FORMASYON_MANTIGI.md` §2.3 |
| `currentWidth` | `upperNow - lowerNow` | Mevcut genişlik (fiyat) | `FORMASYON_MANTIGI.md` §2.3 |
| `contraction` | `(startWidth - currentWidth) / startWidth` | Daralma oranı (`0` → `1`) | `FORMASYON_MANTIGI.md` §2.3 |
| `minContraction` | `0.25` (`%25`) | Minimum daralma (`Dengeli`) | `FORMASYON_MANTIGI.md` §2.3, `config.py` |
| `apexFloat` | `startBar - startWidth / slopeGap` | Üçgen ucu (`float`) | `FORMASYON_MANTIGI.md` §2.5 |
| `apexBar` | `yuvarla(apexFloat)` | Üçgen ucu (`int` bar) | `FORMASYON_MANTIGI.md` §2.5 |
| `KARNE_HEDEF_ATR` | `1.5` | Karne hedef (`ATR` bazlı) | `config.py` |
| `KARNE_STOP_ATR` | `1.0` | Karne stop (`ATR` bazlı) | `config.py` |
| `KARNE_HORIZON_BAR` | `10` | Karne ufuk (`bar` sayısı) | `config.py` |
| `EVREN_BUYUME_UYARI_ESIGI` | `48` | Evren büyüme uyarı eşiği (`100` için güncellenmeli) | `config.py` |
| `BIST_OPEN` | `09:50` (İstanbul) | BIST seans açılışı | `config.py`, `data.py` |
| `BIST_CLOSE` | `18:10` (İstanbul) | BIST seans kapanışı | `config.py`, `data.py` |
| Kalite katsayıları (doküman) | `0.28 / 0.20 / 0.12 / 0.16 / 0.12 / 0.07 / 0.05` | `Pine v0.4.6` (`ARGENT`) — **değiştirilmedi** | `FORMASYON_MANTIGI.md`, `PINE_FARK_ANALIZI.md` |
| Kalite katsayıları (kod) | `0.26 / 0.18 / 0.12 / 0.20 / 0.10 / 0.07 / 0.07` | Python portu (`patterns/`) — **değiştirilmedi** (`Pine` gelmeden) | `patterns/` |
| `minAge` (yaş) | `16` (`Dengeli`) | Minimum formasyon yaşı (`bar` sayısı) | `FORMASYON_MANTIGI.md` §3 |
| `upperTouches` | `>= 2` | Üst çizgi temas sayısı (`Dengeli`) | `FORMASYON_MANTIGI.md` §3 |
| `lowerTouches` | `>= 2` | Alt çizgi temas sayısı (`Dengeli`) | `FORMASYON_MANTIGI.md` §3 |
| `touchDistribution` | `>= 4` temas toplam, son temas `start`'tan yeterince uzak | Dokunuş dağılımı (`Dengeli`) | `FORMASYON_MANTIGI.md` §3 |

---

## 9. GELİŞTİRME TALİMATLARI (Bu Oturum İçin)

```
Bu oturumda dal adı veya commit bilgisi kullanılmaz; sadece geliştirme konuşulur.
Kullanıcı amacı: 100 hisse genişletmesi, XU100 eklenmesi, Telegram kanal/grup,
haftalık toplam artış/düşüş raporu, al-sat motoru değil — bilgilendirme sistemi.

Açık işler (öncelik sırası):
1. A2: is_bist_open (line 100) tatili bilmez → time_until_next_open kontrolü.
2. A3: Ölü kod yolları (SIKISMA_GUCLENIYOR, _live_state.get_formations, contraction None).
3. C1: STOCK_UNIVERSE (100 hisse) + EVREN_BUYUME_UYARI_ESIGI güncelleme + 2027 tatil.
4. B6: Kalite eşiği altı aday sayaç + panel satırı.
5. B8: Pacing yeniden ölçümü (SCAN_* ayarları) — 100 sembol için.
6. A7: URL sırı (/test?k=, /webhook/<secret>) + rate limit.

Çözülmüş (kontrol edilebilir):
A1, A4, A5, A6, B2, B3, B4, B5, C2, C3, C4.

Regresyon: pytest 305 passed; test_tarama_zamani 100/100; test_pennant 6/6.
Sandbox: Yahoo/Telegram erişimi yok; --cache modu kullanılır; gerçek test kullanıcının makinesinde.
```

---

*Bu belge (`MASTER_PROMPT.md` — güncellenmiş, dal/commit yok, çok ayrıntılı) `Formation-Bot` (`arena/01a1019f-formation-bot`) dalının mevcut durumunu yansıtır; ancak dal adı burada belirtilmez — sadece yapısal, matematiksel ve gelişmeye yönelik bilgi içerir.*
