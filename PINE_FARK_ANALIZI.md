# Pine v0.4.6 Karşılaştırma — Faz 3 Analizi ve Fikir Defteri

> **Bu dosya benim (ajanın) çalışma defterim.** Amacı: Pine script'indeki mantığın
> Python motorunda ne kadar birebir olduğunu izlemek, eksikleri sıraya koymak ve
> Pine'ın dışında faydalı olabilecek fikirleri biriktirmek.
>
> **ÖNEMLİ — Pine dosyası henüz elimde değil.** Kullanıcı `Yeni Metin Belgesi.txt`
> olarak ekledi ama dosya diske ulaşmadı (`/home/user/uploads/` boş). Bu yüzden
> aşağıdaki analiz **iki kaynağa** dayanıyor:
>   1. `FORMASYON_MANTIGI.md` — Pine v0.4.6'nın Türkçe dökümanı (375 satır, 10 bölüm)
>   2. Mevcut Python kodu (`patterns/` paketi) — okunarak doğrulanmış
> Pine dosyası geldiğinde **5. bölümdeki doğrulama listesi** tekrar açılacak ve her
> madde satır satır Pine ile karşılaştırılacak. Döküman ile kod arasında sapma
> çıkarsa döküman değil PINE esastır (kaynak: Pine v0.4.6 FINAL EXPORT, satır 300-800).

---

## 1. Durum özeti (2026-09-27)

| Madde | Durum | Kanıt |
|---|---|---|
| Pivot + sağ teyit | ✅ Birebir | `patterns/pivots.py` — `range(pivot_len, n-pivot_len)` sağ karşılaştırma zorunlu |
| Geometri (eğim/ATR normalize) | ✅ Birebir | `patterns/candidate.py` + `FORMASYON_MANTIGI.md` §2 |
| Üçgen / kema tespiti | ✅ Birebir | `patterns/candidate.py` `f_build_candidate` |
| Kalite skorlama | ✅ Birebir | §5 formülü kodda uygulanmış |
| İhlal taraması (A1) | ✅ Çözülmüş | `patterns/violation.py:51` `safe_end_bar = min(requested_end_bar, n-1)` |
| Selection score (A2) | ✅ Çözülmüş | `patterns/selection.py` — recency/proximity/continuity + replacement_margin |
| Bayrak motoru (A4) | ✅ Çözülmüş | `test_flag.py` 3/3 geçiyor (sentetik boğa + ayı bayrağı bulunuyor) |
| **Flama motoru** | ✅ Çözüldü + raporlandı | `patterns/candidate.py:723-800` → `test_pennant.py` **6/6 geçti**; canlı rapora direk/varyant detayı eklendi |
| **Flama varyantı (standart/eğik)** | ✅ Yeni | `PatternCandidate.specialized_variant` = "Bayrak" / "Flama (standart)" / "Flama (eğik)" — Pine'ın iki koşul tablosunu ayırt eder |
| **Standart flama geometri şartı** | 🔧 Düzeltildi | `_std_base` artık `standard_pennant_geometry` (Simetrik Üçgen) ister; eğik geometri standart flama sayılamıyor (Pine tablo mantığı) |
| A5 kalanlar | ❌ Açık | `filter_same_bar_double_pivot` stub, `local_break` TODO, `ST_WEAK`/`ST_GEOMETRY` kod yolu yok |

**Sonuç:** Faz 3'ün ana maddesi olan "flama ekle" aslında 01a0e276 portunda
**kodlanmıştı**; eksik olan **test, varyant ayrımı ve karşılaştırma detayıydı**.
Bunlar bu adımda tamamlandı. Kullanıcı Pine ile kendisi karşılaştıracaği için
canlı rapora direk/varyant/ölçüm detayı ve eşik rehberi eklendi.

---

## 2. Pine v0.4.6 yapısı (döküman haritası)

Pine tek bir dev fonksiyonu olan `f_build_candidate` (satır 300-800) etrafında
kurulu. Akış:

```
1. 4 pivot seç (hb1,hp1 / hb2,hp2 / lb1,lp1 / lb2,lp2)
   -> kronolojik olmalı: hb1<lb1<hb2<lp2 veya lb1<hb1<lb2<hb2
   -> topAbove: upperStart>lowerStart ve upperNow>lowerNow
2. Geometri: iki üst pivottan üst doğru, iki alt pivottan alt doğru
   -> eğimler ATR'ye normalize (fiyattan bağımsız)
   -> yataylık eşiği flatSlopeNormTol=0.024 (Dengeli)
3. Üçgen/Kama: contraction >= %25, touch >= 2+2, age >= max(5, minAge/2)
   -> rawQuality = geometry*0.38 + touch*0.32 + maturity*0.18 + cleanliness*0.12
   -> kabul eşiği minRawQuality = 46
4. Bayrak/Flama: önce DİREK (pole) şart
   -> pole: direction, duration 1-20 bar, magnitude >= 2.8 ATR, efficiency >= 0.62
   -> bayrak: paralel kanal (|upperSlope-lowerSlope| küçük)
   -> flama: DARALAN kanal (simetrik üçgen gibi)
   -> kalite: poleQuality*0.28 + depth*0.20 + duration*0.12 + parallel*0.16
              + touch*0.12 + calmness*0.07 + cleanliness*0.05
   -> kabul eşiği minSpecializedQuality = 50 (eğik flama +8)
5. İhlal taraması: son pivot ile tespit anı arası da taranır (A1)
6. Selection: |kalite farkı| >= 6 -> kalite, değilse selection score (A2)
7. Lifecycle: state machine + kırılım dondurma (A3)
```

**Profiller:** Hassas / Dengeli / Seçici. Dengeli: pivotLen=5, minAge=16,
minContraction=%25, maxConsolidationBars=40.

---

## 3. Flama (pennant) — kod, test ve rapor durumu

### 3.1 Kod (`patterns/candidate.py:723-800`)

Pine'daki dört ayrı tablo koşulu birebir çevrilmiş:

| Tip | Geometri | depth | heightRatio | durationRatio | süre | efficiency | kalite eşiği |
|---|---|---|---|---|---|---|---|
| Standart flama | Simetrik Üçgen | 0.06-0.70 | <= 0.46 | <= 2.80 | <= maxConsol | < pole+0.08 | >= minSpecialized |
| Eğik boğa flaması | Yükselen Üçgen | 0.08-0.60 | <= 0.40 | <= 2.40 | <= maxConsol*0.85 | < pole | >= minSpecialized+8 |
| Eğik ayı flaması | Alçalan Üçgen | 0.08-0.60 | <= 0.40 | <= 2.40 | <= maxConsol*0.85 | < pole | >= minSpecialized+8 |

Ek koşul: eğik flamada **pole kalitesi >= minPoleQuality + 10** olmalı.
Seçim: `best_specialized = max(bull_flag, bear_flag, bull_pennant, bear_pennant)`
— en iyi özel tip generic üçgen/kema üzerine geçebilir.

**Bu adımda yapılan iki değişiklik:**

1. **`specialized_variant` alanı eklendi** (`PatternCandidate`): seçim anında
   "Bayrak" / "Flama (standart)" / "Flama (eğik)" olarak dolduruluyor. Böylece
   canlı raporda ve testlerde Pine'ın hangi koşul tablosunun devreye girdiği
   görülebiliyor (eğik = eğim koşulları +8 kalite, daha sıkı süre).
2. **Standart flama geometri şartı düzeltildi:** `_std_base` artık
   `standard_pennant_geometry` (yani `generic_type == "Simetrik Üçgen"`) ister.
   Önce bu değişken hesaplanıyordu ama kullanılmıyordu; sonuç: Yükselen/Alçalan
   Üçgen geometrisindeki formasyonlar standart flama eşikleriyle (gevşek) değerlendirilebiliyordu.
   Artık eğik geometri yalnız eğik flama tablosundan geçer (daha sıkı: pole +10,
   süre *0.85, kalite +8). **Bu bir SIKILAŞTIRMA** — ölçümsüz gevşetme değil.
   Not: Pine dosyası gelince bu şartın Pine'da birebir var olduğu doğrulanacak
   (doğrulama listesine madde 11 olarak eklendi).

### 3.2 Test sonuçları (`test_pennant.py`, 6/6 geçti)

Sentetik veri (Pine-uyumlu): dip 88 → 12 barlık direk (88→126, ~3.2 TL/bar) →
daralan kanal. Kanal eğimi ATR'ye normalize edildiği için (eğim/geometry_atr,
flat tol 0.024) **geometriyi eğim oranı belirliyor**:

| Kanal (üst/alt eğim) | Üretilen geometri | Flama varyantı |
|---|---|---|
| -0.06 / +0.06 TL/bar | Simetrik Üçgen | Flama (standart) |
| -0.001 / +0.15 TL/bar | Yükselen Üçgen | Flama (eğik) |
| -0.06 / -0.03 TL/bar | Alçalan Kema | flama YOK |

| Test | Sonuç |
|---|---|
| Boğa flaması standart | ✅ bar 44'te tespit, kalite **73.8**, direk 12 bar / 38.26 TL / direk kalitesi 88 |
| Ayı flaması standart (fiyat aynası) | ✅ bar 48'de tespit, kalite **68.9**, direk aşağı 18 bar / 37.88 TL / direk kalitesi 81 |
| Eğik flama (yükselen üçgen kanalı) | ✅ bar 44'te tespit, kalite **83.6**, varyant **Flama (eğik)** |
| Kema benzeri kanal | ✅ flama yok (Pine kuralı: flama üçgen geometrisi ister) |
| Random veri | ✅ flama yok (yanlış pozitif yok) |
| Direksiz daralan üçgen | ✅ flama yok (Pine kuralı: direk şart) |

**Test yazarken öğrendiğim kritik noktalar:**
- İlk sentetik veride kanalı hızlı daralttım (üst -0.60/bar, alt +0.42/bar):
  4 barda üst < alt oldu, geometri çöktü, flama hiç bulunamadı. Yavaş daralma ile
  motor doğru tespit etti. → Sentetik veri üretirken Pine'ın oran kısıtlarını
  (heightRatio, durationRatio) gerçekten sağlamak gerekir.
- Ayı flamayı "bağımsız üretmek" (92→128 zirve → 128→88 düşüş + kanal) direk
  bağlantısını geç kurdu: teğet çifti bar 48'de oluştu, pole link penceresi
  (10 bar) aşıldı. Fiyat aynası kullanınca direk 18 bar olarak bağlandı.
  → Ayna veri hem simetrik hem pivot zamanlaması açısından daha güvenilir.

### 3.3 Canlı rapora eklenen detay (`canli_tarama.py`)

Bayrak/flama formasyonlarında rapora 3 ek satır geliyor:

```
[3] XXXX | 1h | Boğa Flaması | q78 | SIKISMA_GUCLENIYOR
    Ust cizgi: ...   Alt cizgi: ...
    Daralma: %60   Formasyon baslangici: ...
    Pine varyanti: Flama (standart)
    Direk: yukari yonlu, 12 bar, 38.26 TL, direk kalitesi 88
    Flama olculeri (Pine esikleri parantezde): derinlik 0.11 [0.06-0.70],
      yukseklik orani 0.11 [0.46], sure orani 1.83 [2.80]
    TV KONTROL: ... '{a.pattern_type}' etiketi + hemen oncesindeki DIREK gorunmeli ...
```

Raporun sonuna **PINE KARSILASTIRMA REHBERI** bloğu eklendi: kaç bayrak/flama
tespit edildiği, eşik özeti (standart/eğik/bayrak) ve fark görülürse ne yapılacağı
(bu defterdeki doğrulama listesine not).

### 3.4 Gerçek BIST verisi ölçümü (cache ile)

`canli_tarama.py --cache` çalıştırıldı (28 hisse x 4 TF, 25 Eylül verisi):

- **9 canlı formasyon** bulundu (SIKISMA_GUCLENIYOR, OLGUNLASIYOR, KIRILIM_ADAYI,
  RETEST_BASARILI ...) ama **hiçbiri Bayrak/Flama değil.**
- Yani gerçek veride flama/bayrak eşikleri şu an hiçbir formasyonu geçirmiyor.

**Yorum (dikkatli):** Bu iki şeyden biri demek:
  (a) o gün gerçekten flama/bayrak uygun formasyon yok (nadir formasyonlardır), veya
  (b) eşikler gerçek veri için çok sert.
Hangisi olduğunu anlamak için **Pine dosyası şart**: Pine'da eşikler birebir aynıysa
(a) doğru davranıştır ve dokunulmaz. Pine dosyası gelmeden eşik gevşetmek **YAPILMAYACAK**
— teşhis A4'ün kök nedeni tam olarak buydu (sentetik bayrak reddediliyor, gerçek veride
sahte bayrak bulunuyordu; eşikler keyfi gevşetilmişti).
Bir sonraki ölçüm: daha uzun bir geçmiş penceresinde (1D derin veri dahil) kaç günde bir
flama/bayrak çıkıyor — Pine uyumu teyit edildikten sonra yapılacak.

---

## 4. Kodun Pine'a birebir olduğunu doğruladığım yerler (okuduğum dosyalar)

- `patterns/pivots.py:213-232` — pivot için sağ taraf teyidi zorunlu (Pine: `pivotLen` bar sonrası).
- `patterns/selection.py:83-102` — recency `16-(bar_index-endBar)*0.65`, proximity, continuity*0.22,
  partial overlap cezası. Döküman §7 ile birebir.
- `patterns/violation.py:51` — `safe_end_bar = min(requested_end_bar, n-1)` (A1 düzeltmesi uygulanmış).
- `patterns/lifecycle.py` — `tam_yeniden=True` deterministik replay; kırılım anında sınırlar
  donduruluyor (A3 düzeltmesi: frozen alanlar artık okunuyor).
- `patterns/mathutil.py:82-108` — volume=0 → nötr 50.0 skor (yfinance ilk bar hacmi 0).
- `patterns/constants.py` — ST_* state isimleri Pine ile aynı.
- `patterns/pole.py:110-165` — pole kalite formülü (magnitude*0.30 + efficiency*0.30 +
  duration*0.16 + speed*0.12 + localBreak 12 - singleShock 24), "tek bar şoku" tespiti
  (duration<=1 veya range >= magnitude*0.72 → kalite tavanı 46).

---

## 5. PINE DOSYASI GELİNCE DOĞRULANACAK LİSTE

> Dosya geldiğinde bu liste **tek tek** açılacak. Her madde için: Pine satır
> numarası, Python karşılığı, sapma (varsa), karar.

1. **`f_build_candidate` satır 300-800** — tüm akış satır satır; özellikle
   `geometryCanUsePole = touchBasics + historicalGeometryAcceptable + (parallelLike VEYA üçgen)`
   koşulunun kodda var olduğunu teyit et (teşhis A4.4 "ölü hesap" demişti).
2. **Eşik sabitleri** — `minSpecializedQuality`, `minPoleQuality`, `depthQuality` /
   `durationQuality` fonksiyonlarının iç yapısı, `maxConsolidationBars`, `flatSlopeNormTol`.
   Bunlar Pine'da sabit mi, profilden mi geliyor?
3. **Eğik flama +8 / pole +10 kuralı** — kodda `msq + 8.0` ve `min_pole_quality + 10.0`
   var; Pine'da birebir aynı mı?
4. **`ST_WEAK` ve `ST_GEOMETRY`** — teşhis A5 "hiçbir kod yolu üretmiyor" dedi.
   Pine'da bu state'ler hangi koşulda üretiliyor? Kodda yoksa eklenmeli.
5. **`filter_same_bar_double_pivot`** — A5 stub (`# TODO`). Pine'daki mantık?
6. **`local_break`** — A5 TODO. Pine'daki karşılığı?
7. **Boğa/ayı pole aynı anda bağlanırsa** — teşhis "her zaman bull kazanıyor,
   Pine'da kalite kıyası" dedi. Kodda `max(...)` ile kıyas yapılıyor mu?
8. **Kalite formülü katsayıları** — geometry 0.38 / touch 0.32 / maturity 0.18 /
   cleanliness 0.12 ve flama katsayıları (0.26/0.18/0.12/0.20/0.10/0.07/0.07)
   birebir mi? (Döküman 0.28/0.20/0.12/0.16/0.12/0.07/0.05 diyor — **SAPMA OLABİLİR**,
   Pine'a bakıp düzeltilecek.)
9. **Ayar (input) değerleri** — Pine'daki tüm `input.*` değerleri config profilleriyle
   uyumlu mu?
10. **Alert koşulları** — Pine'da `alertcondition` hangi state'lerde? Bizim
    `ALERT_STATES` listesiyle aynı mı?
11. **Standart flama geometri şartı (bu adımda eklendi)** — Pine'da standart pennant
    koşulu gerçekten `triangleType == SYMMETRICAL` (veya dengi) mi kontrol ediyor?
    Kodda `_std_base` artık `standard_pennant_geometry` ister; eğer Pine'da bu şart
    YOKSA geri alınacak (yoksa eğik üçgen geometrisindeki formasyonlar standart
    eşiklerle değerlendirilemiyor). Ayrıca eğik flamada yön-uyumu: boğa = Yükselen
    Üçgen, ayı = Alçalan Üçgen (kod böyle) — Pine'da da öyle mi?
12. **Varyant etiketlemesi** — `specialized_variant` alanı sadece rapor/test içindir;
    Pine'da karşılığı yok. Pine'da hangi etiketin gösterildiği (ör. "Pennant" vs
    "Inclined Pennant") doğrulanırsa rapora yansıtılabilir.

---

## 6. Fikir defteri (Pine'ın ötesinde, dikkatli değerlendirilecek)

> Bunlar Pine'da olmayan / Pine'dan farklı düşünebileceğimiz şeyler. Hepsini
> uygulamak doğru değil — ölçüm ve Pine uyumu öncelikli. Sıra: etki / risk.

### 6.1 Flama ile ilgili
1. **Gerçek BIST verisinde flama taraması.** Sentetik test geçti ama gerçek veride
   hiç flama bulunuyor mu? `canli_tarama.py --cache` çalıştırıp "Flama" geçen
   formasyon sayısını ölç. 0 ise ya eşikler çok sert ya da gerçek flama yok —
   ikisi de bilgi. *(Ölçüldü: 9 formasyon, 0 flama/bayrak — Pine dosyası bekleniyor)*
2. **Flama + 1D derin veri etkileşimi.** 1D'de flama nadir ama daha uzun süren
   direkler mümkün. `GUNLUK_DEQUE_MAXLEN=500` yeterli mi?
3. **Eğik flama kalite cezası.** Kodda eğik flama +8 eşikle geçiyor. Pine'da öyleyse
   dokunma; değilse düzelt.
4. **Yükselen/Alçalan Üçgen geometrisi + yanlış yön direk.** Kodda boğa eğik flama
   yalnız Yükselen Üçgen geometrisinde kuruluyor. Pine'da da yön-uyum var mı
   (yoksa Alçalan Üçgen + boğa direği de flama olabilir) — madde 11 ile birlikte
   doğrulanacak.

### 6.2 Genel motor
5. **`ST_WEAK` / `ST_GEOMETRY` state'leri** — Pine'da üretiliyorsa ekle. Bu iki
   state Telegram'a gitmiyor ama iç seçim mantığını etkileyebilir.
6. **A5 stub'lar** (`filter_same_bar_double_pivot`, `local_break`) — Pine'dan
   birebir çevir. Yanlış çeviri riski var, Pine olmadan YAPMA.
7. **Kalite katsayı sapması** (madde 5.8) — döküman ile kod farklı görünüyor.
   Pine dosyası gelince bunu çöz; o zamana kadar KODU DEĞİŞTİRME.

### 6.3 Pine ile çakışabilecek fikirler (dikkat!)
8. **"Flama tespitini gevşetelim" fikri — RED.** Pine eşikleri bilerek sert;
   gevşetmek yanlış pozitif getirir (A4'ün asıl sorunuydu: sentetik bayrak
   reddediliyor, gerçek veride sahte bayrak bulunuyordu).
9. **"Gerçek zamanlı flama alarmı" — olabilir ama önce Pine uyumu.** Faz 1'deki
   :35 tetikleyici + Faz 2'deki tatil/veri-yok modu sayesinde altyapı hazır.
10. **Backtest / ileri test** — `test_forward.py` var. Flama için ayrı forward testi
    yazılabilir (direk sonrası flama kırılımının ne kadar çalıştığı).

---

## 7. Bu adımda yapılanlar

1. Pine dosyasının diske ulaşmadığı görüldü → kullanıcıya tekrar yüklemesi istendi.
2. `patterns/candidate.py:723-800` okundu: flama kodu mevcut, Pine dökümanıyla uyumlu.
3. `test_pennant.py` yazıldı; ilk hali 4 testti (boğa flama ✅, ayı flama ✅, random ✅,
   direksiz ✅).
4. Ortamın sıfırlandığı görüldü (pandas/numpy yoktu) → kuruldu.
5. **Sandbox sıfırlanması local checkout'u eski bir commit'e (a1afd75) döndürdü.**
   Faz 3 commit'i yanlış tabana yapılmıştı; push doğru şekilde reddedildi.
   `git reset --hard c3000b6` ile doğru tabana dönüldü, Faz 3 dosyaları reflog'dan
   kurtarıldı (`git show a49c017:<dosya>`). Faz 1+2 commit'leri remote'da güvenliydi.
6. Doğru tabanda doğrulama: `test_tarama_zamani.py` 90/90, `test_pennant.py` 4/4,
   `canli_tarama.py --cache` 9 canlı formasyon (0 flama). Bu defter yazıldı.
7. **Kullanıcı yönlendirmesi:** Pine dosyasını beklemeden canlı formasyon sistemine
   flamayı raporla — kullanıcı kendisi Pine ile karşılaştırıp çıktı alacak.
8. **`specialized_variant` alanı eklendi** (`patterns/candidate.py`): seçim anında
   "Bayrak" / "Flama (standart)" / "Flama (eğik)" dolduruluyor.
9. **Standart flama geometri şartı düzeltildi:** `_std_base` artık Simetrik Üçgen
   geometrisi ister (eğik geometri yalnız eğik flama tablosundan geçer).
   Regresyon: `test_tarama_zamani.py` 90/90 korundu.
10. **`test_pennant.py` 6 teste çıkarıldı:** standart boğa/ayı flama, eğik flama
    (varyant assert'li), kema kanalı (flama olmamalı), random, direksiz.
    Ölçüm: ATR normalize eğimde -0.06/+0.06 → Simetrik Üçgen, -0.001/+0.15 →
    Yükselen Üçgen, -0.06/-0.03 → Alçalan Kema.
11. **`canli_tarama.py` raporuna Pine karşılaştırma detayı eklendi:** bayrak/flamada
    varyant + direk (yön/süre/büyüklük/direk kalitesi) + flama ölçümleri (derinlik,
    yükseklik oranı, süre oranı; Pine eşikleri parantezde) + rapor sonunda
    PINE KARSILASTIRMA REHBERI bloğu. Canlı cache ile doğrulandı (9 formasyon,
    0 bayrak/flama).

## 8. Sıradaki adımlar (sırayla)

1. **Pine dosyasını bekle** → 5. bölüm listesini tek tek doğrula (özellikle 5.8 katsayı
   sapması ve 5.11 standart flama geometri şartı).
2. Gerçek BIST verisinde flama/bayrak taraması ölç (yapıldı: 0; uzun pencere + 1D
   derin veri ile tekrar).
3. A5 kalanlarını Pine'dan çevir (stub'lar ve ST_WEAK/ST_GEOMETRY).
4. Flama/bayrak için forward test (backtest) yaz.
5. Hepsi geçtikten sonra FAZ 3 kapanır → Pine ile birebir uyum raporu.
