# Formation-Bot — Dosya Göremeyen Bir AI'ya Verilecek Tanıtım Paketi

> **Bu dosya ne için:** Projenin görsel tarafı hakkında **dosyalara erişemeyen** bir
> AI'dan öneri almak için. Kullanım: aşağıdaki metnin tamamını yapıştır, sonra
> **§5'teki 5 PNG'yi ekle**. Metin kendi başına yeterlidir; görsel eşleşmeleri
> §5'te açıklanmıştır.
>
> **İçerik:** §1 özet · §2 sistem mantığı · §3 gerçek metin bildirim örnekleri ·
> §4 görsel taraf (mimari + kurallar + ölçümler) · §5 eklenecek görseller ·
> §6 Render deploy süreci · §7 öneri istediğim sorular · §8 kırmızı çizgiler ·
> §9 dosya haritası.

---

## §0 Kopyala-yapıştır istem (alıcı AI'ya)

> Aşağıdaki blok, bu dosyanın özetini tek istem hâline getirir. Dosyanın tamamını
> yapıştırmak daha iyidir; bu blok yalnız hızlı başlangıç içindir.

```
Bir BIST formasyon tarayıcısının Telegram mum grafiği kareleri için görsel
tasarım danışmanlığı istiyorum. Ekli 5 PNG, sistemin ürettiği gerçek kareler
(1080x810, koyu tema) ve karşılaştırma sayfaları. Sana projenin mimarisini,
metin bildirim örneklerini, kare katmanlarını, palet kodlarını, kadraj kurallarını
ve ölçüm kapılarını aşağıda verdim.

Kısıtlar: (1) motorda olmayan veri çizilmez/etiketlenmez, (2) renk paleti sabit ve
neon değil, (3) yazı hiçbir mumun üstüne binmez (ölçüm kapısı: çakışma = 0),
(4) kare 1080x810 sabit, (5) arayüz Türkçe, (6) hedef kitle telefon (Telegram).

İstediğim: §7'deki 9 soruya madde madde, gerekçeli ve uygulanabilir öneriler.
Her öneri için: ne değişecek, hangi katman/parametre, beklenen kazanç, risk.
```

---

## §1 Tek paragrafta proje

**Formation-Bot**, BIST (İstanbul) hisseleri için çalışan bir **formasyon tarama ve
bildirim** sistemidir. ARGENT v0.4.6 Pine Script'inin Python portudur; BIST 50
evrenindeki **48 sembolü 4 zaman diliminde** (1s/2s/4s/1g) saatlik olarak tarar,
üçgen/kama/bayrak/flama formasyonlarını **durum makinesiyle** (aday → sıkışma →
kırılım adayı → teyitli → retest → tamamlandı/başarısız) takip eder ve sonucu
**Telegram'a** metin kartı (+ istenirse mum grafiği karesi) olarak bildirir.
Sistem yalnızca **kapanmış mumlarla** çalışır, motorun üretmediği hiçbir veriyi
yazmaz ve "yatırım tavsiyesi değildir" uyarısını her mesaja ekler. Python 3.12,
~90 modül, ~50 000 satır kod, **1319 test** (1275 geçer / 44 atlanır). Dağıtım:
**Render Free** (Frankfurt) + **Supabase** (kalıcı durum) + **GitHub Actions**
(keep-alive + deploy tetiği).

---

## §2 Sistem mantığı

### 2.1 Veri akışı

```
Yahoo Finance (yfinance)
   │  seri istek, 10 istekte bir 10-15 sn mola, 0,9-1,5 sn aralık
   ▼
OHLCV önbelleği (bot_data/*.json yerelde · Supabase bot_store uzakta)
   ▼  resample → 1h / 2h / 4h / 1d
tamamlanmis_mumlar()  ← KAPANMAMIŞ BAR ASLA MOTORA GİRMEZ
   ▼  (1s: etiket+1sa · 2s/4s: etiket+süre, günün son kovası 18:00 · 1g: 18:30)
Formasyon motoru (patterns/)  →  aday / formasyon nesnesi
   ▼  ATR-normalize geometri, kronolojik pivotlar, temas & daralma filtreleri
Yaşam döngüsü (patterns/lifecycle.py)  →  state geçişleri + olaylar
   ▼
Kalite kapısı + profil eşikleri (config.PROFILE_PARAMS)
   ▼
Alarm politikası (notifier.py)  →  DM anlık / DM digest / public kanal bütçesi
   ▼
Telegram (transport/telegram.py): metin kartı  +  (ops.) grafik karesi PNG
```

### 2.2 Formasyon motoru (patterns/)

| Adım | Kural |
| :--- | :--- |
| Pivotlar | `pivot_len = 5` bar sol/sağ onay |
| Formasyon | 2 üst + 2 alt pivot, **kronolojik**: `hb1<lb1<hb2<lb2` veya tersi |
| Geometri | Üst/alt sınır doğruları; eğimler **ATR'ye normalize** edilir (fiyat bağımsız) |
| Yataylık | `flat_slope_norm_tol = 0,024`; paralellik `flat × 0,75`; min eğim `0,006` |
| Daralma | `min_contraction_pct = %25` (üst-alt aralığın başlangıca göre daralması) |
| Temas | `touch_atr_mult = 0,15` tolerans; min temas aralığı 5 bar; genelde 2/2 |
| Bayrak/Flama | Direk (pole): `min_pole_atr = 2,8`, verim `≥0,62`, ≤20 bar; konsolidasyon ≤40 bar |
| Yaş | `min_age = 16` bar |
| Kırılım | `break_atr_mult = 0,06` (kapanış sınırı ATR cinsinden ne kadar aşmalı) |
| Teyit penceresi | `confirm_window = 2` bar |
| Retest | `retest_window = 5` bar, tutma `3` bar |
| Kalite | `min_raw_quality 46` · `min_specialized 50` · `min_pole 49` · kırılma gücü ≥ `50` |

Desenler: **Yükselen / Alçalan / Simetrik Üçgen**, **Yükselen / Alçalan Kama**,
**Boğa / Ayı Bayrağı**, **Boğa / Ayı Flaması**. Üç profil: **Hassas / Dengeli /
Seçici** (`Dengeli` varsayılan; yukarıdaki sayılar Dengeli'nindir).

### 2.3 Durum makinesi (lifecycle)

```
ADAY_OLUSUYOR → OLGUNLASIYOR → SIKISMA_GUCLENIYOR → KIRILIM_ADAYI
   → KIRILIM_TEYITLI → RETEST_BEKLIYOR → RETEST_EDILIYOR → RETEST_BASARILI
                                                    ↘ BASARISIZ_KIRILIM
   → FORMASYON_TAMAMLANDI        (hedefe ulaştı)
   → KIRILIM_GECERSIZLESTI       (fiyat banda geri döndü)
   → TIMEOUT                     (süre doldu, karneye yazılmaz)
```

### 2.4 Alarm politikası (kim, ne zaman, hangi bütçeyle)

| Yüzey | İçerik | Bütçe |
| :--- | :--- | :--- |
| **DM anlık** | 4 kritik state: `KIRILIM_TEYITLI`, `RETEST_BASARILI`, `FORMASYON_TAMAMLANDI`, `BASARISIZ_KIRILIM` — TF bazlı kalite eşiği (`1s:80 / 2s:78 / 4s:75 / 1g:70`) | saatlik 20 · günlük 120 mesaj, 4 saat cooldown, tek-seferlik mühür (hisse+TF+state, günde 1) |
| **DM digest** | 6 izleme state'i (sıkışma, hazırlık, aday, deneme, retest bekleyen/edilen) → 18:45 özetine ertelenir; tampon kalıcı, taşma şeffaf ("12/21 gösteriliyor") | — |
| **Günlük özet** | 09:55 sabah notu + 18:45 kapanış özeti; Cuma günü doğruluk karnesi eklenir | — |
| **Public kanal** | Yalnız 3 state: `KIRILIM_TEYITLI`, `RETEST_BASARILI`, `KIRILIM_GECERSIZLESTI` + TF bazlı kalite eşiği; sıkışanlar özeti | saatte ≤6 · günde ≤25, min 1,2 sn aralık |
| **Komutlar** | Yalnız kayıtlı DM sohbetinden; public hedef komut kabul etmez | 1 sn'de 1 komut |

**Metin sözleşmesi (ölçülü):** düz metin (HTML/Markdown yok), satır bütçesi
**≤283 px** (Telegram 360 px telefonda kırılmasın diye üç merkezi gönderim
noktasında ölçülür), mesaj bütçesi **≤1100 karakter**, "1 olay = 1 mesaj",
kaynakta olmayan veri yazılmaz.

### 2.5 SMC / domain motorları (grafikte kullanılan, salt-okunur)

`domain_engines/` altındaki dört motor alarm görselini besler; **çizim kodu bu
motorları değiştirmez**, yalnız çıktısını okur:

| Motor | Çıktı |
| :--- | :--- |
| `market_structure` | swing'ler (HH/HL/LH/LL), **BOS / CHoCH** olayları, kritik seviye |
| `order_block` | OB kutuları (`top/bottom/bullish/base_score/fill_boundary`) |
| `fvg` | FVG bantları (lower/upper boundary, direction, gap_atr, quality, fill oranı) |
| `volume_participation` | bar bar **RVOL**, `volume_level`, `effort_result_class` (zayıf sonuç işareti) |

`zone_scoring.py` bu bölgeleri ölçer (izole prototip; canlı tarama yoluna bağlı
değildir).

---

## §3 Metin bildirimlerinden gerçek örnekler

Aşağıdaki mesajlar **projenin kendi simülatörüyle** üretildi:
`python gun_simulasyonu.py --gun 2026-09-25` — gerçek `bot_data` önbelleği
üzerinden 1 işlem günü (09:00→20:10) koşturuldu, ağ yok, Telegram çağrıları
yakalandı. Yani uydurma değil: botun canlıda ürettiği metinlerin birebir kopyası.

**Ölçüm:** o gün **12 DM + 7 kanal = 19 mesaj**, 10 tarama turu, 28 hisse × 4 TF.

### 3.1 DM — anlık teyitli kırılım (yukarı)

```
▲ BIMAS 4s YUKARI TEYİTLİ
Simetrik Üçgen — kapanışla
kapanış 428,25 (seviye 407,17)
kalite 76/100 — güç 25
bant 96 bar — 12.08'dan beri
retest yok — MTF 1g onayı yok
katılım 4s veri yok
bozulur 406,08 altı kapanış
karşı delil: iç yapı ↓ — hacim
   teyitsiz
› /tara BIMAS
• yatırım tavsiyesi değildir
```

### 3.2 DM — retest başarılı

```
▼ HALKB 4s RETEST BAŞARILI
Simetrik Üçgen
kapanış 45,16 (seviye 46,37)
kalite 83/100 — güç 51
bant 52 bar — 01.09'dan beri
retest var — MTF 1g onayı yok
katılım 4s veri yok
katılım 2s 0,32 zayıf
bozulur 46,90 üstü kapanış
karşı delil: dış yapı ↑ — hacim
   teyitsiz
› /tara HALKB
• yatırım tavsiyesi değildir
```

### 3.3 DM — geçersizleşme

```
▼ TOASO 1s GEÇERSİZLEŞTİ
Yükselen Üçgen - bandına dönüş
teyit sınırı 284,50 üstü
kalite 88/100 — güç 73
bant 71 bar — 15.09'dan beri
retest var — MTF 4s onayı yok
katılım 1s veri yok
karşı delil: iç yapı ↑
› /tara TOASO
• yatırım tavsiyesi değildir
```

### 3.4 DM — aşağı yönlü teyit, hacim aşağıyı koruyor

```
▼ THYAO 1s AŞAĞI TEYİTLİ
Yükselen Üçgen — kapanışla
kapanış 291,50 (seviye 292,07)
kalite 88/100 — güç 73
bant 90 bar — 11.09'dan beri
retest yok — MTF 4s onayı yok
katılım 1s aşağı korunuyor
katılım 2s 0,53 zayıf
bozulur 293,20 üstü kapanış
› /tara THYAO
• yatırım tavsiyesi değildir
```

### 3.5 Public kanal — bülten (tek olay)

```
📊 Bülten · 1 gelişme
   25 Eyl 13:35
🔷 BIMAS 4s · Simetrik Üçgen
   yukarı kapanışla teyitli · 407,17
   kapanış 428,25 · kalite 76
   · temas 2/2
   🕒 25.09 09:30→13:30 mumu

📌 yatırım tavsiyesi değildir
```

### 3.6 DM — 18:45 günlük özet (kırpılmış; tam metin 1989 karakter)

```
📋 Günlük Özet
📊 BIST Formasyon Özeti
   25 Eyl 18:45
────────────────────────

🎯 RETEST BAŞARILI (1):
• ↓ HALKB 1h Alçalan Üçgen q87

⚡ SIKIŞANLAR (3):
• ASELS 2h Simetrik Üçgen q87
   %84
• DOHOL 2h Alçalan Üçgen q85
   %80
• DOHOL 1h Simetrik Üçgen q82
   %90

📈 Gün: 9 tarama · 9 bildirim
   28 hisse × 4 zaman dilimi
🔎 Bugün: 6 teyitli · 2 retest başarılı
   4 geçersizleşme
🕒 Son başarılı tam tarama:
   25 Eyl 18:35 ✓

📌 yatırım tavsiyesi değildir

📡 Gün içi izleme adayları
   en yüksek puanlılar
   sıkışma güçleniyor
• ISCTR 4s Alçalan Üçgen q89
   daralma %73 · 12,08
• ALARK 4s Alçalan Üçgen q89
   daralma %77 · 101,47
• ASELS 2s Simetrik Üçgen q87
   daralma %84 · 370,44
[… 12 aday]

📊 HAFTALIK DOĞRULUK KARNESİ
   21.09–25.09.2026 · 5 seans
🔍 Formasyon tespiti: 19
 TF: 4s 8 · 1s 7 · 2s 4
⚡ Kırılım: 6 · yukarı 2 · aşağı 4
 10 bar: hedef 0 · nötr 5 · stop 1
 ✅ Yönünde kapanan: 1/6 (%17)
⚠️ n=6 küçük · 30+ sinyal gerek
```

### 3.7 Public kanal — kapanış özeti

```
📊 BIST kapanış · 25 Eyl 18:45
🎯 Retest başarılı 1
✅ Teyitli kırılım 0
⚡ Sıkışan 3: ASELS 2h (%84)
   · DOHOL 2h (%80)
   · DOHOL 1h (%90)

📡 Yarının izleme listesi (ilk 5)
• ISCTR 4s Alçalan Üçgen q89
• ALARK 4s Alçalan Üçgen q89
• ASELS 2s Simetrik Üçgen q87
• PETKM 1s Alçalan Üçgen q86

📈 Gün: 9 tarama
   28 hisse × 4 zaman dilimi
🔎 Bugün: 6 teyitli · 2 retest başarılı
   4 geçersizleşme
🕒 Son başarılı tam tarama:
   25 Eyl 18:35 ✓
```

### 3.8 Komut yüzeyi (DM)

`/formasyonlar` · `/canli` · `/panel` (48 hisse × 4 TF + en yüksek puanlı 12
aday) · `/ozet` · `/sikisanlar` · `/tamamlanan` · `/retest` · `/kirilim` ·
`/durum` (bot + piyasa + veri sağlığı) · `/karne [gün]` (doğruluk karnesi) ·
`/backtest [gün] [detay]` · `/tara [HISSE]` · `/grafik HISSE [1s|2s|4s|1g]
[sade|detay]` · `/yardim`. Komutlar yalnız kayıtlı DM sohbetinden kabul edilir.

### 3.9 Grafik karesinin altındaki yazı (caption)

```
GARAN · 1s · 80 mum
ℹ️ veri: 3 bar hacimsiz · bölge: 84 kutu kapak dışında
```

Eski sürümde bu bilgiler **karenin içinde** kırmızı/gri geliştirici metni olarak
duruyordu; kullanıcı isteğiyle kareden çıkarılıp caption dipnotuna taşındı.

---

## §4 Görsel taraf (mum grafiği karesi)

### 4.1 Mimari

- Tek modül: `grafik.py` (~200 KB, ~4400 satır) — veri hazırlama, kadraj, katman
  çizimi, ölçüm (kalite kapıları) ve meta üretimi tek yerde.
- Kare: **1080×810 px** (4:3, dpi 100), koyu tema, tek eksen (alt hacim paneli
  kaldırıldı; dikey alan mumlara verildi).
- Girdi: botun **mevcut çıktısı** (formasyon nesnesi + alarm verisi + seçilen
  TF'nin domain motoru sonuçları). Çizim kodu **hiçbir zaman motor çalıştırmaz**,
  hiçbir veriyi uydurmaz: motor bir alanı vermiyorsa o etiket çizilmez.
- Çıktı: PNG + `meta` sözlüğü (ölçümler: mum sayısı, px/bar, çakışma sayacı,
  katman sayaçları, süre, KB).

### 4.2 Katmanlar (arkadan öne)

| # | Katman | İçerik |
| :--: | :--- | :--- |
| 1 | Zemin | `#0f151c`; ızgara `#212c39` |
| 2 | Formasyon bandı | Üst/alt sınır çizgisi **2,0 pt**, iç alan **karartılmaz** (dolgu ~%3) |
| 3 | OB / FVG kutuları | OB düz kontur, FVG kesikli; dolan kısım mat gri, kalan canlı renk |
| 4 | Mumlar | Yükselen yeşil **içi boş**, düşen kırmızı **dolu** (renk körlüğünde de ayırt edilir) |
| 5 | Yapı (MS) | BOS/CHoCH çizgileri + HH/HL/LH/LL etiketleri (fitilden 11 px) |
| 6 | Alarm | Kırılan seviye çizgisi, hedef projeksiyonu (kesikli kutu + `◎ Hedef`) |
| 7 | Rozetler | RVOL rozetleri (mum altı) + üst başlık pill'leri |
| 8 | Sağ ray | Fiyat etiketleri: PH/PL/WH/WL, kritik seviye, son fiyat; çakışmada **Y-offset + kesikli lider çizgisi** |

### 4.3 Palet (koyu tema, "belirgin ama neon değil")

| Rol | Renk | Rol | Renk |
| :--- | :--- | :--- | :--- |
| Zemin | `#0f151c` | Panel | `#151d27` |
| Metin | `#e9eef5` | Eksen | `#93a1b1` |
| Yükselen mum | `#31b184` | Düşen mum | `#e05c58` |
| OB boğa | `#10B981` | OB ayı | `#EF4444` |
| FVG boğa | `#06B6D4` (turkuaz) | FVG ayı | `#8B5CF6` (mor) |
| Dolan (mitigasyon) | `#9CA3AF` mat gri | Hedef | `#22d3ee` |
| OB taze dolgu | %25 | OB kalan dolgu | %12 |
| OB dolan bant | %8 (gri, kesikli kenar) | FVG dolgu | %15 |

### 4.4 Kadraj (viewport) ve sağ boşluk — son kararlar

| Durum | Kural |
| :--- | :--- |
| Formasyon yok | TF matrisi: **1s 80 · 2s 74 · 4s 68 · 1g 62** mum |
| Formasyon var | formasyon mumları **+10 sol tampon**, toplam **35–85** arasına kırpılır |
| Sağ boşluk | **eksen genişliğinin %15'i** (pencere %10–20; `GRAFIK_SAG_BOSLUK_ORANI`). Fiyat etiketleri, seviye çizgileri ve hedef kutusu buraya çizilir; OB/FVG kutuları ve aktif BOS hedefi buraya kadar uzar. |

### 4.5 RVOL rozeti (hacim) — en son eklenen özellik

Hacim paneli kaldırıldığı için sıra dışı hacim mum altındaki rozete taşındı.
Kullanıcı istekleriyle üç turda olgunlaştı:

| Kural | Değer | Neden |
| :--- | :--- | :--- |
| Patlama rozeti | `⚡↑ x2,5` (RVOL > 2,0) | Hacim teyidi |
| Kuruma rozeti | `⚡↓ x0,5` (RVOL ≤ 0,5) | Kullanıcı: "ani düşüş olduğunda x0.5 yazmıyor" → iki yönlü oldu |
| Kuruma tavanı | kare başına **en fazla 2** | Kullanıcı: "çok fazla etiket olmamalı, en fazla 2 ekleyebiliriz" |
| Toplam tavan | kare başına **3–6 rozet** | Kullanıcı: "yine 3-6 kalsın" |
| **Tazelik önceliği** | her yönün **en yeni** uygun mumu her zaman rozet alır | Kullanıcı: "bu sistem sadece geçmişi filtreler, yeni geleni geciktirebilir" — ölçüm doğruladı: son mumun rozeti 4 karede de düşüyordu |
| Yön kanalı | ok + renk (yeşil/kırmızı) | Renk tek başına bilgi taşımaz kuralı |

### 4.6 Ölçüm kapıları (kalite otomasyonu)

Kare üretimi kendini ölçer; `meta` sözlüğüne yazar. Testler bu sayılara bağlıdır:

| Kapı | Eşik | Anlamı |
| :--- | :--- | :--- |
| `mum_cakisan` | **= 0** | Hiçbir yazı mumun gövde/fitil kutusuna binmiyor (piksel ölçümü) |
| `px/bar` | ≥ 5 | Altına düşerse "çizgi + alan" moduna geçer (mum çizilmez) |
| PNG boyutu | ≤ 500 KB | Telegram yükleme |
| Kare süresi | 400–620 ms | Render Free'de makul |
| Determinizm | aynı girdi → aynı kare | Test: `test_meta_belirleyici_ayni_girdi_ayni_kare` |

### 4.7 Görsel evrim (kısa tarih)

Kullanıcı dört fazlı bir görsel plan verdi ve uygulandı (`docs/tasarim/GRAFIK_TASARIM.md §40`):

1. **FAZ 1 — Temizlik:** geliştirici metinleri (lejant, `veri: N bar hacimsiz`,
   `bölge: N kutu`) kareden çıktı → kart altı dipnotuna; alt hacim paneli kaldırıldı;
   RVOL rozeti eklendi.
2. **FAZ 2 — Akıllı kadraj:** TF matrisi + formasyon odaklı pencere + sağ boşluk.
3. **FAZ 3 — SMC revizyonu:** OB doluluk yüzdesi (`mitigated_percentage`), ikili
   kutu çizimi (dolan gri/kalan canlı), OB yeşil-kırmızı & FVG turkuaz-mor ayrımı,
   BOS/CHoCH **çizgi kısaltma** (pivot → kırılım mumu; yalnız aktif hedef sağa uzar).
4. **FAZ 4 — Fintech cila:** sağ ray etiket çakışma çözümü + lider çizgisi, üst
   başlık yarı saydam pill'ler, pivot etiketleri 10–15 px uzakta, teyitli alarmda
   kesikli hedef projeksiyonu, formasyon iç alanı şeffaf + sınır çizgileri 2 pt.

Sonrasında iki ek tur: **sağ boşluk %10-20** (varsayılan %15) ve **iki yönlü +
tazelik öncelikli RVOL rozeti** (§4.5).

---

## §5 Eklenecek görseller

Bu paketle birlikte **şu 5 PNG'yi ekle** (hepsi depoda `docs/` altında,
1080×810, gerçek önbellekten üretilmiş):

| Dosya | Ne gösteriyor | Ölçüm |
| :--- | :--- | :--- |
| `docs/gorseller/ornek_kare_faz1_4_1s.png` | **GARAN 1s**, formasyon yok: 80 mum, 6 rozet (↑3 ↓2 ... taze dahil), taze OB (yeşil), kısmen dolmuş OB (gri bant + `%54 dolu`), FVG, sağ ray (PH/kritik/WL) | çakışma 0 · 66 KB · ~450 ms |
| `docs/gorseller/ornek_kare_faz1_4_4s.png` | **AKBNK 4s**, 68 mum: OB dolan/boşalan ayrımı, `FVG↑`, `BOS↑/CHoCH↓` çizgileri, `⚡↓` kuruma rozetleri | çakışma 0 · 66 KB · ~500 ms |
| `docs/gorseller/ornek_sag_bosluk_oran.png` | Aynı iki kare, **%10 / %15 / %20** sağ boşlukla (3 satır × 2 kolon karşılaştırma) | boşluk payı ölçülü: %10,1–%20,0 |
| `docs/gorseller/ornek_rozet_yon.png` | Rozet yakın planları: `⚡↑ x5,57` (patlama) ve `⚡↓ x0,2` (kuruma) + 4 karenin rozet sayıları | kare başına 3–6 |
| `docs/gorseller/ornek_rozet_taze.png` | **Tazelik önceliği** kanıtı: her karenin "son mumun rozeti" yakın planı | taze izler: GARAN 1s ↑18 ↓75 · AKBNK 4s ↑33 ↓67 |

Depoda ayrıca eski turların kareleri var (isteğe bağlı ek):
`ornek_kare_gorsel4/5/6/7.png` (katman katman karşılaştırmalar),
`docs/gorseller/ornek_kart_gorsel7.png` (metin kartı px ölçüsü), `docs/gorseller/ornek_kutu_tonu.png` (OB dolgu
tonu önce/sonra), `docs/gorseller/ornek_sag_bosluk.png` (sağ boşluk ilk turu).

---

## §6 Render deploy süreci

### 6.1 Servis

| Ayar | Değer |
| :--- | :--- |
| Tür / plan | Web Service · **Free** (15 dk inbound trafik yoksa uyur) |
| Bölge | **Frankfurt** (Türkiye'ye en yakın) |
| Runtime | Python — sürüm repodaki **`.python-version` = 3.12** ile sabit (Render varsayılanı 3.14 ve pandas 2.2.2/numpy 1.26.4 tekerleği yok → build patlar) |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python main.py` |
| Health Check Path | `/health` |
| Auto-Deploy | açık (kapalıysa her merge sonrası "Manual Deploy") |

### 6.2 Ortam değişkenleri (özet; tam liste `.env.example`, 57 anahtar)

| Anahtar | İş |
| :--- | :--- |
| `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` | Bot + DM komut kanalı (zorunlu) |
| `TELEGRAM_GROUP_ID` | Kanal/grup yayını (opsiyonel; bot orada yönetici olmalı) |
| `SUPABASE_URL` · `SUPABASE_SERVICE_ROLE_KEY` | Kalıcı OHLCV önbelleği + Telegram durumu (opsiyonel ama önerilir) |
| `BOT_PROFILE` | `Hassas` / **`Dengeli`** / `Seçici` |
| `TZ` | `Europe/Istanbul` (log ve kota günü hizası) |
| `MARKET_SUFFIX` · `STOCK_UNIVERSE` | `.IS` · boş = BIST 50 (48 aktif) |
| `DATA_DIR` · `SEED_DATA_DIR` · `LOG_DIR` | `/tmp/formation-bot-data` · `./bot_data` (okuma yedeği) · `./logs` |
| `TELEGRAM_WEBHOOK_SECRET` | Doluysa komutlar webhook, boşsa `getUpdates` yoklaması |
| `TELEGRAM_GRAFIK` · `TELEGRAM_GRAFIK_ADET` | `yok`/`alarm` · alarm başına kare (1-4) |
| `GRAFIK_*` | Kare ayarları: `GRAFIK_MUM_MAKS`, `GRAFIK_OLAY_MAKS`, `GRAFIK_SAG_BOSLUK_ORANI`, `GRAFIK_HACIM_PANELI`, `GRAFIK_LEJANT_KARE`, `GRAFIK_RVOL_ROZET_ESIK(_DUSUK/MAKS/DUSUS_MAKS)` |
| `HEALTH_RATE_LIMIT_PER_MIN` | Public uçlarda IP başına limit (0 = kapalı) |

### 6.3 Ayakta tutma (keep-alive) ve deploy tetiği

- Free plan inbound trafik olmadan uyur; bot kendi çağrılarını **outbound**
  yaptığı için kendini uyandırmaz. Çözüm: `.github/workflows/keepalive.yml`
  **5 dakikada bir** `/health` ucuna ping atar (public repoda Actions dakikaları
  ücretsiz; 60 gün repo aktivitesi olmazsa GitHub zamanlanmış işi sessizce
  kapatabilir → Actions sekmesinden "Enable workflow").
- `.github/workflows/deploy.yml`: `main`'e push'ta Render **Deploy Hook**'unu
  çağırır (`RENDER_DEPLOY_HOOK` secret; yoksa iş kırmızı olmaz, uyarı verir).
  Böylece "merge ettim ama canlı eski sürüm" durumu görünür olur.
- `/health` yanıtı canlı commit'i döner: `{"status":"ok", ..., "commit":"67cadbd",
  "branch":"main"}`.

### 6.4 Doğrulama / teşhis

```bash
python deploy_check.py --url https://<servis>.onrender.com
```

Sırasıyla: repo tarafı (`.python-version`, requirements pinleri, keepalive
workflow'u, yerel önbellek) → env (token/chat id var mı; değerleri **asla**
yazdırmaz) → Supabase tablosu gerçekten var mı (404 = SQL çalıştırılmamış,
401/403 = anahtar yanlış, 200 = hazır) + heartbeat yaşı → Telegram `getMe` ve
`getWebhookInfo` (komut yolu kopuk mu, bekleyen güncelleme birikmiş mi) →
`/health` ayakta mı + canlı commit yerel HEAD ile aynı mı.

### 6.5 Kalıcılık ve sınırlar

- Render diski **geçici** (`/tmp`): kalıcılık Supabase `bot_store` tablosunda
  (`SUPABASE_STORE_PREFIX`), yoksa analiz çalışır ama önbellek/state her yeniden
  başlatmada sıfırlanır.
- BIST tatil/yarım gün takvimi `exchange-calendars` (XIST); **bilinmeyen tarih
  fail-closed** (tarama yapılmaz).
- Yalnız kapanmış mumlar bildirime kaynak olur; tarama anı kayarsa güvenlik
  kapısı anlık push'u sonraki tura bırakır.
- Mobil/Termux kurulumu: `setup-termux.sh`, `requirements-termux.txt`,
  `docs/kurulum/LOCAL_SETUP.md`.

---

## §7 Görsel taraf için öneri istediğim sorular

1. **Katman yoğunluğu:** 8 OB/FVG kutusu + 6 rozet + yapı çizgileri + sağ ray aynı
   karede. Bu yoğunlukta hangi katman sadeleştirilmeli? (ör. kutular yalnız
   fiyata en yakın 3 tanesi mi, kuşak/şerit mantığı mı?)
2. **Rozet tasarımı:** `⚡↑ x2,5` çipleri mumun altında. Alternatif: mumun yanında
   dikey mini barlar, veya yalnız en sert 2 tanesi + dipnot? Hangi düzen 5,5"
   telefonda daha hızlı okunur?
3. **Tarihsel karşılaştırma:** `docs/gorseller/ornek_sag_bosluk_oran.png`'te %10 / %15 / %20
   varyantları var. Görsel denge ve okunurluk açısından hangisi, neden?
4. **Sağ ray hiyerarşisi:** PH/PL/WH/WL + kritik seviye + son fiyat aynı şeritte.
   Hangisi birincil (dolu çip/kalın yazı), hangisi ikincil (soluk) olmalı?
   Çakışma çözümü için mevcut "Y-offset + kesikli lider çizgisi" dışında daha iyi
   bir desen var mı?
5. **Renk sistemi:** OB yeşil/kırmızı, FVG turkuaz/mor, hedef açık mavi, dolan
   mat gri. Neon olmadan (kullanıcı kısıtı) kontrastı artırmanın yolu? Renk
   körlüğü alternatifi (şu an `--renk-korugu` bayrağı mavi-turuncu veriyor)?
6. **Hedef projeksiyonu:** teyitli alarmda kesikli kutu + `◎ Hedef` çipi var.
   Kullanıcı "daha şık ama ASLA uzun açıklama" diyor — fikir?
7. **Tipografi:** 1080×810 Telegram'da küçültülüyor; minimum punto/çoğaltıcı
   önerisi? (şu an rozet 8 pt, eksen 8,5 pt, `--buyuk-yazi` = ×1,25 var)
8. **Bilgi mimarisi:** karede olmaması gerekenler (kullanıcı debug metni
   istemiyor) — sizin ekleyeceğiniz "kesinlikle olmalı" tek şey ne olurdu?
9. **Değerlendirme kontrol listesi:** Bu 5 kareyi tutarlı biçimde notlayabilmem
   için (1-5 puan) hangi kriterleri kullanmalıyım?

---

## §8 Kırmızı çizgiler (öneri verirken ihlal edilmemesi gerekenler)

1. **Uydurma veri yok.** Çizilen her etiket/çizgi motorun gerçek çıktısından
   gelir; motor bir alanı vermiyorsa yazılmaz (boş bırakılır, tahmin edilmez).
2. **Domain motorları (`domain_engines/`) görsel iş için değiştirilmez**; her
   şey mevcut çıktıdan türetilir.
3. **Telefon okunurluğu önce gelir:** yazı hiçbir mumun üstüne binmez, satır
   bütçesi 283 px, kare 1080×810 (4:3) sabit.
4. **Neon yok, ama "tam belirgin":** palet sabit (yukarıdaki hex'ler); tasarım
   önerileri bu paletle uyumlu olmalı.
5. **Türkçe arayüz**, emoji kullanımı: kare içinde yalnız font destekliyorsa
   (DejaVu Sans'ta 📈/📐/🎯 yok → `◆ ◈ ◎` ile değiştirilir; telefonda emoji
   desteklenir).
6. **Mevcut ölçüm kapıları korunmalı:** `mum_cakisan = 0`, `px/bar ≥ 5`,
   PNG ≤ 500 KB, determinizm.
7. **Yasal uyarı** ("yatırım tavsiyesi değildir") ve "AL/SAT aracı değildir"
   ibareleri metin yüzeylerinden kaldırılamaz.

---

## §9 Dosya haritası (depoyu açabilen AI için)

| Konu | Dosya |
| :--- | :--- |
| Mum grafiği karesi (tüm çizim) | `grafik.py` · `grafik_uret.py` (CLI) · `scripts/grafik_onizleme.py`, `scripts/grafik_sag_bosluk_karsilastirma.py` |
| Grafik tasarım sözleşmesi + ölçümler | `docs/tasarim/GRAFIK_TASARIM.md` (§40 FAZ 1-4 · §41 sağ boşluk · §42 rozet) |
| Formasyon motoru | `patterns/` (`detect.py`, `candidate.py`, `lifecycle.py`, `pivots.py`, `mathutil.py`, `pole.py`, `violation.py`) |
| SMC motorları | `domain_engines/` (`market_structure`, `order_block`, `fvg`, `volume_participation`) |
| Bölge puanlama | `zone_scoring.py` |
| Bildirim metinleri | `notifier.py` (`_format_lifecycle_alert_kart*`) · `notification_context.py` · `reporting/format.py`, `reporting/panel.py` |
| Telegram taşıma + komutlar | `transport/telegram.py` · `telegram_commands.py` · `telegram_alert_flow.py` · `telegram_measure.py` |
| Kart biçim sözleşmesi (ölçülü) | `docs/tasarim/TELEGRAM_KART_FORMAT.md` · `docs/denetim/TELEGRAM_FORMAT_COMPARISON_EXAMPLES.md` |
| Tarama döngüsü, durumlar, zamanlama | `main.py` · `canli_tarama.py` · `config.py` · `data.py` · `bist_calendar.py` |
| Simülasyon / ölçüm araçları | `gun_simulasyonu.py` · `deploy_check.py` · `test_accuracy.py` · `karne.py` |
| Dağıtım | `render.yaml` · `docs/kurulum/RENDER_DEPLOY.md` · `.env.example` · `.github/workflows/{ci,deploy,keepalive}.yml` · `supabase_schema.sql` · `supabase_store.py` · `health_server.py` |
| Test (1319) | `test_*.py` (76 dosya) — grafik tarafı: `test_grafik_*.py` (360 test) |

---

*Bu dosya 2026-10-16'da projenin kendi ölçüm araçlarıyla üretilen verilerle
yazıldı: `gun_simulasyonu.py --gun 2026-09-25` (gerçek mesaj metinleri) ve
`grafik_uret.py`/`pytest` (kare ölçümleri: çakışma 0, 3-6 rozet, ~450-620 ms,
55-70 KB).*
