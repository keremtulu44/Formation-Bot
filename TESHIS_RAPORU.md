# 🔍 Formation-Bot Teşhis Raporu — Pine→Python Dönüşüm Testi

**Tarih:** 2026-09-27 · **Yöntem:** Mevcut diagnostic'ler çalıştırıldı + `repo_teshis.py` ile ölçüm
**Referans:** `FORMASYON_MANTIGI.md` (Pine v0.4.6 davranışının yazılı hali) + README + commit mesajları

---

## Özet Karar

Kod **çalışıyor ama Pine'ı doğru çevirmemiş**. Matematik yardımcıları (smoothstep, band, apex, line_price) sağlam;
hata ağırlıklı olarak **(1) eksik Pine filtreleri, (2) yanlış referans kullanan lifecycle, (3) keyfi gevşetilmiş bayrak eşiikleri**
üzerinde toplanıyor. Sonuç: tespitçi **rastgele veride %88 pozitif** verirken, **mükemmel sentetik üçgeni %45 kaçırıyor**
ve **kalite skoru gerçek başarı ile ters korelasyonlu**.

---

## KATEGORİ A — Kanıtlanmış Mantık Hataları

### A1. "Fiyat formasyonun içinde mi?" kontrolü yok + ihlal taraması son pivot'ta kesiliyor
- **Döküman §6 (S1 kuralı):** *"Son pivot ile şimdiki bar arası da taranır, ama son kapanmış bar (bar_index-1) kadar."*
- **Kod:** `f_build_triangle_candidate` ihlal taramasını `start_bar..end_bar` ile çağırıyor — `end_bar` **son pivot barı**.
  Son pivot ile tespit anı arasındaki kuyruk (9-35 bar) **hiç taranmıyor**.
- **Sonuç:** Zaten kırılıp uçmuş formasyonlar "geçerli aday" olarak geçiyor.
- **Ölçüm (repo_teshis.py, Teşhis 1):** Gerçek BIST verisinde 10 tespitten **8'inde fiyat formasyon aralığının DIŞINDA**:
  ```
  THYAO  Yükselen Üçgen q88  close=290.50  aralık=[294.32, 302.11]  DIŞARIDA!
  GARAN  Yükselen Üçgen q88  close=129.80  aralık=[130.37, 135.95]  DIŞARIDA!
  ALARK  Yükselen Üçgen q83  close=106.80  aralık=[109.35, 110.47]  DIŞARIDA! (son pivot 35 bar eski)
  ```
- **Bu tek başına** `test_forward.py`'daki **%95 "bar+0" anında kırılım** oranını ve
  **Yükselen Üçgen'in 4/4 aşağı kırılıp 0 başarı** almasını açıklıyor: seçilen formasyonlar zaten kırılmış.

### A2. Selection Score hiç hesaplanmıyor (recency + proximity + continuity eksik)
- **Döküman §7:** Adaylar arasında seçim `|kalite farkı| >= 6 → kalite, değilse selection score` ile yapılmalı;
  recency (`16 - (bar_index-endBar)*0.65`), proximity, continuity (+25/+15/+18.75/...) ve
  replacement margin (ST_PREP:+14 ... ) tanımlı.
- **Kod:** `PatternCandidate.selection_score` alanı var (satır 76) ama **hiçbir yerde yazılmıyor/okunmuyor (0.0)**.
  `find_best_triangle_candidate` saf `max(raw_quality)` seçiyor.
- **Sonuç:** 12 düşük-kaliteli aday arasından "en pahalı görünen" seçiliyor; tazeliği hiçbir şey korumuyor.
- **Ölçüm:** Tespitlerin 4/10'unda son pivot **10+ bar eski** (25 ve 35 bar olanlar var).

### A3. Lifecycle, kırılım anındaki dondurulmuş sınırlar yerine "o an bulunan adayın" sınırlarını kullanıyor
- **Kod:** Kırılım anında `frozen_upper_boundary_at_break`, `frozen_break_buffer` vb. **14 alan yazılıyor ama hiçbir yerde okunmuyor.**
  `update()` içindeki `back_inside` / `returned_inside` kontrolleri parametre olarak gelen `candidate.upper_now`'ı kullanıyor —
  ve `main.py` her taramada adayı **yeniden tespit edip** geçiriyor; bu aday **bambaşka bir formasyon** olabilir.
- **Kanıt (test_breakout.py adım 4, sayılarla doğrulandı):**
  ```
  Kırılım: aday1 üst çizgisi 170,103.75 → 184,101.88 (eğim -0.133/bar)
  Kırılım sonrası bulunan aday2: FARKLI 4 pivot (130,105.26 → 149,104.03) — "AYNI formasyon mu? False"
  Retest barı: close=100.38 → kırılım çizgisinin (99.61) ÜSTÜNDE, tutunuyor
  Ama aday2'nin düşen üst sınırı 100.67 olduğu için "formasyon alanına dönüldü" → BASARISIZ_KIRILIM ❌
  ```
  Düzgün bir retest, kitabına göre BASARISIZ ilan ediliyor. (Aynı kontrol benim izole senaryomda geçti —
  hatareferans karışımında, retest mantığında değil.)
- **Aynı hata** `BREAK_ATTEMPT/BREAK_CANDIDATE` dalındaki `projected_upper/lower` için de geçerli.

### A4. Bayrak motoru: mimari Pine'a uymuyor, eşikler keyfi gevşetilmiş
- **Kanıt (test_flag.py):** Mükemmel sentetik boğa bayrağı (direk + net paralel kanal) → **225/225 aday RED**.
  Aynı anda gerçek veride 3 "Bayrak" buluyor (yanlış pozitif) → motor ne temizi yakalıyor ne sahteyi eliyor.
- **Kök nedenler:**
  1. Direk araması `end_bar = arama penceresindeki pivotun barı`'na zorlanıyor; mock'ta direk bar 34'te bittiği,
     arama penceresindeki pivotlar bar 45+ olduğu için hiçbir direk bağlanamıyor. Pine'da direk bitişi impulsların
     bittiği bardır, arama pivotu olmak zorunda değil.
  2. Sabitler dökümana göre **kat kat gevşetilmiş** (kötü kök nedeni gizliyor):
     | Parametre | Pine (döküman) | Python | Oran |
     |---|---|---|---|
     | Paralel tolerans | `flat*0.75 = 0.018` | `flat*10 = 0.24` | ~13x |
     | Direk bağlantısı | `pivotLen*2 = 10` | `35` | 3.5x |
     | Depth | 0.08–0.80 | 0.05–1.00 | — |
     | heightRatio | ≤ 0.58 | ≤ 0.70 | — |
     | durationRatio | ≤ 3.5 | ≤ 4.0 | — |
  3. `local_break` TODO → direk kalitesinde sürekli **-12 puan** (Pine'da var).

### A5. Tamamlanmamış dönüşümler
- `filter_same_bar_double_pivot` → **stub** (`# TODO: Pine'daki mantığı tam çevir`) — aynı bar çift pivot çözümü yok.
- `local_break` → **TODO** (bkz. A4.3).
- Flama (pennant) yok (README'de biliniyor), `ST_WEAK` ve `ST_GEOMETRY` hiçbir kod yolu üretmiyor.

---

## KATEGORİ B — Davranışsal Belirtiler (yukarıdakilerin ölçülen sonucu)

| Test | Beklenen | Ölçülen | Durum |
|---|---|---|---|
| Random walk yanlış pozitif (test_accuracy) | < %5 | **%88** (50'de 44) | ❌❌ |
| Shuffle testi (sıra bozulunca pattern ölmalı) | 0/5 | **5/5 buluyor (q80-91)** | ❌❌ |
| Mükemmel sentetik üçgen, gürültü 0 | ~%100 | **%55** | ❌ |
| Aynı test, gürültü 1.0 | Daha DÜŞÜK olmalı | **%70 (ARTIYOR)** | ❌ skorlama gürültüyü ödüllendiriyor |
| Gerçek BIST (collective_test) | Makul sayı | **112 taramada 73 pattern (%65)** | ❌ aşırı tespit |
| Kalite ↔ başarı (forward, 1h) | Pozitif korelasyon | Q≥80 → **%44**, Q<80 → **%60** | ❌ TERS korelasyon |
| 360 vs 350 bar stabilite | Aynı | Aynı (üst fark 0.00) | ✅ |

> Not: Commit mesajındaki *"Random %96 FP Pine'da da var (225 kombinasyondan 1), bu normal"* ifadesi
> kombinasyon-başına ~%0.44 demek; Python'da kombinasyon-başına oran ~%0.9 ve tarama-başına positifleşme %88.
> Yani "Pine'da da var" durumu Python'da **kabul edilebilirin kat kat ötesine** büyümüş. Üstelik
> A1+A2 düzelince kombinasyon sayısı fiilen düşecek (zaten kırılmış/tarihsel olarak delinmiş adaylar elenecek).

---

## KATEGORİ C — Küçük / Orta Sorunlar

1. **ATR tohumlama:** `ewm(alpha=1/14, adjust=False)` ilk TR ile başlar; Pine RMA ilk 14'ün SMA'sı ile tohumlar.
   360 barda fark pratikte önemsiz ama TradingView karşılaştırmasında ilk ~50 barda sapma yaratır.
2. **`geometry_atr` her zaman `atr_series.iloc[-1]`** (en güncel ATR) — eğim normalizasyonu ve tolerans
   geçmiş pivotlara göre hesaplanırken Pine muhtemelen formasyonun kendi barındaki ATR'yi kullanıyor.
3. **Sınıflama tolerans-kırılgan:** test_triangle'daki mükemmel simetrik üçgen, son-6-pivot penceresinde alt
   eğim `flat_tol`(0.024) altında kaldığı için **"Alçalan Üçgen"** sınıflandı (README'de de öyle görünüyor).
   Yavaş yükselen alt sınır "yatay" sanılıp tip yanlış belirleniyor. Temiz üretimimde doğru çıktı —
   yani deterministik bir bug değil, seçim+sınıflama kırılganlığı (A2 ile ilişkili).
4. **`f_build_flag_candidate` üçgen adayını hesaplayıp sonucu tamamen çöpe atıyor** (ölü hesap; dökümandaki
   `geometryCanUsePole = ... (parallelLike VEYA üçgen)` koşulu uygulanmamış → daralan flama geometrisi imkânsız).
5. **Bağlılık:** `bull` ve `bear` pole aynı anda bağlanırsa daima bull kazanıyor (Pine: quality kıyası).
6. **Ortam:** requirements `pandas==2.2.2 / numpy==1.26.4` pinli; sandbox'ta pandas 3.0.6 kuruldu ve tüm testler çalıştı —
   şimdilik uyumsuzluk yok, ancak pinned sürümle tek seferlik regresyon testi yapılmalı.

---

## Öncelikli Düzeltme Sırası (önerim)

1. **A1** — İhlal taramasını `start_bar..bar_index-1`'e uzat + "tespit anında close aralık içinde" şartı.
   *(Tek başına FP'yi ciddi kırmalı; önce bunu ölç.)*
2. **A2** — Selection score'u döküman §7'den birebir implemente et; `find_best_*` seçimini ona bağla.
3. **A3** — Lifecycle'ta kırılım sonrası TÜM kontrolleri `frozen_*` değerleriyle yap; gelen aday sadece
   replacement-margin kuralıyla (§7) mevcut formasyonu devralabilsin.
4. **A4** — Bayrak direk aramasını Pine mimarisine döndür (impuls ucu = pivot zorunluluğu yok) ve
   gevşetilmiş eşikleri Pine değerlerine geri al; geçen temiz mock üzerinde doğrula.
5. **A5** — İki TODO'yu kapat, flama ekle.

---

## İhtiyaç: Pine Script

Aşağıdaki başlıklarda döküman yeterince ayrıntılı değil, **yanlış yorumla "düzeltme" yapmamak için** orijinal
Pine koduna ihtiyacım var:

- `f_build_candidate` (satır ~300-800): fiyat-aralık-içinde / topAbove güncel bar kontrolünün tam hali
- İhlal taraması (S1 kuralı + cache'li versiyon) tarama aralığının tam tanımı
- Selection score formüllerinin tam sabitleri (§7'deki sayılar kısmi görünüyor)
- `f_find_pole` / bayrak bağlantısı: direk bitişinin tanımı ve `f_local_extreme_break`
- Lifecycle: kırılım sonrası `returnedInside` referansı (dondurulmuş mu, canlı mı?) ve replacement margin
- `f_choose_same_bar_pivot` (aynı bar çift pivot çözümü)

**Pine dosyasını paylaşırsan** raporun "Pine'a göre kesin hata / Pine'da da olan davranış" ayrımını kesinleştirip
düzeltmelere öyle başlarım.

---

# BÖLÜM 2: DÜZELTME SONRASI DOĞRULAMA (patterns/ paketi, Pine v0.4.6 birebir)

## Mimari
`patterns.py` (2700 satır) → `patterns/` paketi: constants, indicators, mathutil, pivots,
pole, violation, candidate, selection, lifecycle, detect, legacy. Motor artık adayı
kendisi bulur, kırılım anında kalite/sınırları **dondurur** ve retesti kırılım ÇİZGİSİ
üzerinden değerlendirir (A3 mimari olarak imkânsız hale geldi).

## Teşhis → Düzeltme → Kanıt

| Teşhis | Düzeltme | Kanıt (test çıktısı) |
|---|---|---|
| A1: 8/10 tespitte fiyat DIŞARIDA | S1 survival + selection | repo_teshis 1: **0/10 dışarıda** |
| A2: 240/310 bar terminal sonrası "bulundu" | LIVE_STATES + kalite kapısı | test_accuracy shuffle **0/5**; random FP **%10** (son-bar canlı oranı; Pine'da RW'de pivot-çizgili üçgen doğal oluşur) |
| A2b: mükemmel simetrik üçgen Alçalan diye sınıflanıyordu | selection + eğim norm | repo_teshis 3: **"Simetrik Üçgen (GERÇEK: Simetrik Üçgen)"** |
| A3: retest yanlış seviyeden | dondurulmuş çizgi retesti | test_breakout: SIKISMA → KIRILIM_ADAYI → TEYITLI → RETEST_BASARILI → **TAMAMLANDI**; fail vakası ADAYI → **BASARISIZ** |
| A4: bayrak mock'u Pine'da imkânsız direk kullanıyordu | mock Pine mimarisine çevrildi | test_flag: Boğa Bayrağı q86.5 OLGUNLASIYOR, Ayı Bayrağı q88.5, random'da bayrak yok |
| A5: yeni mock'ta %100 FP | kalite kapısı + S1 | shuffle 0/5, sentetik seride tespit **%100** (tüm gürültülerde 20/20) |

## Ölçümler (düzeltme sonrası)
- **Sentetik üçgen "seride tespit": gürültü 0.0→1.0 hepsinde 20/20 (%100)**; son-bar canlı
  25-45% (formasyon mock bitmeden kırılıyor — radar için başarı), kalite 92→77-88
  (gürültüyle zarif düşüş).
- **Shuffle: 0/5** (S1 geçmiş-tarama ihlalleri artık engelliyor).
- **Random walk son-bar canlı: 5/50 (%10)** — 73→6 pattern (collective: hepsi q≥80, ort 85.2).
- **Forward (bar 339 canlı → +20 bar): 1 pattern, bar+3'te kırıldı, klasik yöne uydu,
  2.7 ATR — %100** (eski %50 oranın içindeki %95 "zaten kırılmış" gürültüsü gitti).
- **Performans**: 200-360 bar → 0.10-0.15s; incremental besleme sorunlu değil.
- **main.py**: snapshot akışı (scan→EngineSnapshot), alert effective_quality ile;
  2 hisse × 4 TF smoke: 8 motor, 3 alert, 0 hata.

## Notlar
- LIVE_STATES = aday oluşuyor / geometri / tanımlandı / olgunlaşıyor / sıkışma / kırılım
  hazırlığı. Terminal (tamamlandı/başarısız/geçersiz/zaman aşımı) ve ZAYIF sinyal değildir —
  "canlı radar" kapısı bunları raporlamaz. Bu, Pine'ın gösterdiği hayalet formasyon
  farkının Python karşılığıdır.
- Rastgele yürüyüşte pivot-çizgili üçgenlerin doğal oluşumu Pine'da da vardır; telegram
  gürültüsü ALERT_STATES + kalite eşikleriyle yönetilir.
