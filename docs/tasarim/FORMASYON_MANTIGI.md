# ARGENT Formasyon Mantığı - Türkçe Döküman

> Pine v0.4.6'daki `f_build_candidate` fonksiyonunun adım adım açıklaması
> Neden bu kadar karmaşık? Çünkü her filtre bir sahte sinyali elemek için

## 1. GİRİŞ - 4 Pivot ile Formasyon

Formasyon = 2 üst pivot + 2 alt pivot

```
hb1, hp1 = ilk üst pivot (bar, fiyat)
hb2, hp2 = ikinci üst pivot
lb1, lp1 = ilk alt pivot
lb2, lp2 = ikinci alt pivot
```

**Kronolojik olmalı**: `hb1 < lb1 < hb2 < lb2` veya `lb1 < hb1 < lb2 < hb2`
- Neden? Pivotlar sırayla oluşmalı, rastgele değil
- Kontrol: `f_chronological_swings`

**TopAbove**: Üst sınır alt sınırın üstünde olmalı
```
upperStart > lowerStart ve upperNow > lowerNow
```

## 2. GEOMETRİ HESAPLARI

Her pivot çiftinden bir doğru geçer:

```
upperSlope = (hp2 - hp1) / (hb2 - hb1)
lowerSlope = (lp2 - lp1) / (lb2 - lb1)
```

ATR'ye normalize edilir (fiyatdan bağımsız):
```
upperSlopeNorm = upperSlope / geometryAtr
lowerSlopeNorm = lowerSlope / geometryAtr
slopeGapNorm = upperSlopeNorm - lowerSlopeNorm
```

**Neden normalize?** THYAO 300 TL, GARAN 100 TL - aynı eğim farklı fiyatlarda farklı görünür, ATR ile normalize edince karşılaştırılabilir

### 2.1 Yataylık ve Kesin Yön

```
flatSlopeNormTol = 0.024 (Dengeli) -> |slopeNorm| <= 0.024 ise yatay
minSlopeNormTol = 0.006 -> minimum eğim eşiği
parallelSlopeNormTol = flat * 0.75 = 0.018 -> paralel için
```

- `horizontalUpper`: Üst yatay mı? |upperSlopeNorm| <= flatTol
- `horizontalLower`: Alt yatay mı?
- `strictUpperDown`: Üst kesin aşağı mı? upperSlopeNorm < -flatTol
- `strictUpperUp`: Üst kesin yukarı mı? > flatTol
- `strictLowerUp`, `strictLowerDown` aynı

## 3. ÜÇGEN VE KAMA TESPİTİ

### Ön Koşullar (touchBasics)

```
- chronological = true
- bar_index >= knownBar (son pivot teyit edilmiş)
- topAbove = true
- age >= max(5, minAge/2) -> en az 8 bar (Dengeli minAge=16)
- upperTouches >=2 ve lowerTouches >=2
- touchDistribution: en az 4 temas, ve son temas start'tan yeterince uzak
```

### Daralma (Contraction)

```
startWidth = upperStart - lowerStart (başlangıç genişliği)
currentWidth = upperNow - lowerNow (şimdiki genişlik)
contraction = (startWidth - currentWidth) / startWidth

Örn: start 10 TL, now 6 TL -> contraction %40
minContraction = %25 (Dengeli)
```

**Converging**: Daralıyor mu?
```
startWidth > 0, currentWidth > 0, contraction >= %25, slopeGapNorm < -0.006
```
Yani üst eğim alt eğimden küçük (daralıyor)

**ParallelLike**: Paralel mi?
```
|slopeGapNorm| <= 0.018 -> eğimler birbirine yakın, paralel kanal
```

### Apex (Üçgenin ucu)

İki doğru nerede kesişir?
```
apexFloat = startBar - startWidth / slopeGap
apexBar = yuvarla(apexFloat)
```

**Apex OK mi?**
```
apexBar > bar_index (gelecekte) ve apexBar <= startBar + max(minAge*8, 260)
Dengeli: start + max(128, 260) = start+260 bar içinde olmalı
```

**Progress**: Apex'e ne kadar ilerledik?
```
progress = (bar_index - startBar) / (apexBar - startBar) -> 0.0 ile 2.0 arası
%50 = ortası, %100 = apex'e geldik, >%100 = apex geçti (geçersiz)
```

### Formasyon Tipleri

#### Yükselen Üçgen
```
- horizontalUpper = true (üst yatay)
- strictLowerUp = true (alt yukarı)
- lowsHigher = true (lp2 >= lp1 - tol) -> dipler yükseliyor
```
Neden? Üst direnç yatay, alt destek yükseliyor -> boğa

#### Alçalan Üçgen
```
- horizontalLower = true (alt yatay)
- strictUpperDown = true (üst aşağı)
- highsLower = true (hp2 <= hp1 + tol) -> tepeler alçalıyor
```

#### Simetrik Üçgen
```
- strictUpperDown = true (üst aşağı)
- strictLowerUp = true (alt yukarı)
```
İkisi birbirine doğru -> sıkışma

#### Yükselen Kama (Bearish)
```
- strictUpperUp = true (üst yukarı)
- strictLowerUp = true (alt yukarı)
- lowerSlopeNorm > upperSlopeNorm + minTol -> alt daha dik yukarı
```
İkisi de yukarı ama alt daha dik -> daralıyor ama yukarı -> genelde düşüş

#### Alçalan Kama (Bullish)
```
- strictUpperDown, strictLowerDown
- upperSlopeNorm < lowerSlopeNorm - minTol -> üst daha dik aşağı
```

## 4. BAYRAK VE FLAMA - DİREK GEREKLİ

Bayrak/Flama için önce **direk (pole)** olmalı:

### Direk Nedir?

Güçlü, verimli bir impuls:

```
- direction: 1 yukarı, -1 aşağı
- duration: 1-20 bar (Dengeli max 20)
- magnitude: ATR cinsinden büyüklük >= 2.8 ATR
- efficiency: netMove / totalPath >= 0.62 -> düz gitmiş, zikzak değil
- quality: magnitude, efficiency, duration, speed skorlarından
```

**Neden efficiency?** 10 TL'lik hareket 10 TL'lik yolda gittiyse %100 verimli, 30 TL'lik yolda gittiyse %33 verimsiz (çok zikzak)

### Bayrak (Flag)

```
- geometryCanUsePole = touchBasics + historicalGeometryAcceptable + (parallelLike veya üçgen)
- bullSequenceCompatible: hb1 < lb1 (önce üst sonra alt) -> yukarı impuls sonrası
- bullPoleLinked: direk bitişi ile formasyon başlangıcı arası <= maxPoleLinkBars (pivotLen*2)
- Paralel kanal: |upperSlope - lowerSlope| küçük
- bullFlagSlope: ortalama eğim yataya yakın (-0.16 ile +0.35*flatTol arası)
- depth: (poleEnd - consolidationLow) / poleMagnitude -> %8-80 arası
- heightRatio: consolidationHeight / poleMagnitude <= %58
- durationRatio: consolidationDuration / poleDuration <= 3.5
- formedDuration <= maxConsolidationBars (40)
- consolidationEfficiency < poleEfficiency + 0.10 -> konsolidasyon daha sakin
```

**Boğa Bayrağı**: Yukarı direk sonrası paralel aşağı/yan kanal
**Ayı Bayrağı**: Aşağı direk sonrası paralel yukarı/yan kanal

### Flama (Pennant)

```
- standardPennantGeometry = Simetrik Üçgen
- inclined: Yükselen Üçgen (boğa) veya Alçalan Üçgen (ayı) da olabilir ama kalite eşiği +10 yüksek
- depth %6-70, heightRatio <= %46, durationRatio <= 2.8
- formedDuration <= maxConsolidationBars * 0.85 (flama daha kısa)
- consolidationEfficiency < poleEfficiency
```

Flama bayraktan farkı: Kanal paralel değil, daralıyor (simetrik üçgen gibi)

## 5. KALİTE SKORLAMA

Her aday için 0-100 kalite:

### Üçgen/Kama için

```
geometryScore = slopeShapeQuality * 0.65 + contractionScore * 0.35
  - slopeShapeQuality: Eğim şekli ne kadar ideal? (yataylık, daralma)
  - contractionScore: Daralma ne kadar? %25 altı zayıf, %52 üstü güçlü

touchScore = precision *0.42 + count *0.33 + span *0.25
  - precision: Pivotlar çizgiye ne kadar yakın? (tolerance içinde)
  - count: Kaç temas? 4 min, 7 ideal
  - span: Temaslar ne kadar yayılmış? Başlangıçtan uzak mı?

maturityScore = ageQuality *0.58 + progressQuality *0.42
  - age: Yeterince eski mi? minAge=16
  - progress: Apex'e ilerleme %15-82 arası ideal

cleanlinessScore = 100 - violationPenalty
  - violationPenalty: Geçmişte sınır delinmiş mi?

rawQuality = geometry*0.38 + touch*0.32 + maturity*0.18 + cleanliness*0.12
```

**Kabul eşiği**: minRawQuality = 46 (Dengeli)

### Bayrak/Flama için

```
bullFlagQuality = poleQuality*0.28 + depthQuality*0.20 + durationQuality*0.12 + parallelQuality*0.16 + touch*0.12 + calmness*0.07 + cleanliness*0.05
```

- poleQuality: Direk ne kadar kaliteli?
- depthQuality: Düzeltme derinliği ideal mi? %3-82 bandında %16-45 optimal
- parallelQuality: Paralellik ne kadar iyi?
- calmness: Konsolidasyon direktten sakin mi?

**Kabul eşiği**: minSpecializedQuality = 50, ama eğik flama için +8

## 6. İHLAL TARAMASI (Violation)

Neden? Formasyon sınırları geçmişte delinmişse sahte olabilir

```
- Her barda: close > upper + buffer? -> close ihlali
- high > upper + wickBuffer? -> fitil ihlali
- buffer = ATR * 0.06 (close için), ATR*0.15 (fitil için)

- historicalCloseViolations <2 olmalı
- maxHistoricalViolation <= 0.72 ATR
- violationPenalty <62
```

**S1 Kuralı**: Son pivot ile şimdiki bar arası da taranır, ama son kapanmış bar (bar_index-1) kadar
- Neden? Son bar gerçek breakout ise ihlal olarak sayılmasın, lifecycle'a gitsin

**Ceza hesabı**:
```
close ihlali: 13 puan (Dengeli)
fitil ihlali: 5 puan
2+ close ihlali: +10 tekrar cezası
maxViolation *18
```

## 7. SELECTION SCORE (Seçim Önceliği)

Birden fazla aday varsa hangisi seçilecek?

**Formation Quality değil, Context Priority**:

```
recencyPriority: Son pivot ne kadar yakın? 16 - (bar_index - endBar)*0.65
  -> Yeni pivot daha öncelikli

proximityPriority: Fiyat sınıra ne kadar yakın? 10 - min(upperDist, lowerDist)*3.5
  -> Fiyat sınıra yakınsa öncelikli

continuityPriority: Önceki aktif formasyonla ne kadar uyumlu?
  - Aynı tip mi? +25
  - Start yakın mı? +15
  - Pivot overlap? 3/4 overlap = +18.75
  - Sınır mesafesi? Yakınsa +20
  - Overlap ratio? +15
  -> Toplam *0.22

partialOverlapPenalty: Kısmen uyumlu ama tam değilse -8
```

**Seçim kuralı**:

```
if |quality farkı| >= 6.0 (Dengeli):
  -> Kalite belirler
else:
  -> Selection score belirler
  -> Eşitse kalite tie-break
```

**Replacement margin**: Aktif formasyon varsa yeni aday ne kadar daha iyi olmalı?
```
ST_PREP: +14
ST_COMPRESSING: +12
ST_MATURING: +10
ST_DEFINED: +8
Diğer: +6
```

## 8. LIFECYCLE (Yaşam Döngüsü)

Formasyon bulunduktan sonra ne olur?

```
CANDIDATE -> GEOMETRY -> DEFINED -> MATURING/COMPRESSING -> PREP
  -> BREAK_ATTEMPT (zayıf ilk çıkış) -> BREAK_CANDIDATE -> BREAK_CONFIRMED
  -> RETEST_WAIT -> RETESTING -> RETEST_OK -> COMPLETED
  -> BREAK_TIMEOUT / BREAK_FAILED / INVALID / WEAK
```

**Breakout tespiti**:

```
close > upper + breakBuffer (ATR*0.06) ve bar kapanmış
breakStrength = body*0.24 + closeLoc*0.28 + penetration*0.25 + expansion*0.15 + volume*0.08
  - body: Gövde ne kadar yönlü? (close-open)/range
  - closeLoc: Kapanış range'in neresinde? Üstte mi?
  - penetration: Sınırı ne kadar geçmiş? ATR cinsinden
  - expansion: Mum ne kadar geniş? ATR'ye göre
  - volume: Hacim ortalamadan fazla mı?

minBreakStrength = 50 (Dengeli)
Altındaysa BREAK_ATTEMPT, üstündeyse BREAK_CANDIDATE
```

**Retest**:

```
RETEST_WAIT: Kırılım teyitli, retest bekleniyor
RETESTING: Fiyat sınıra döndü, tolerans içinde (tol = ATR*0.15)
RETEST_OK: Sınırda tutup yönde kapanış
  -> Yukarı kırılımda: low <= boundary+tol ve close > boundary+holdBuffer
```

## 9. NEDEN REDDEDİLDİ? (Explainable Log)

Her aday için log:

```
[THYAO] Aday hb1=10 hp1=100 hb2=20 hp2=99 lb1=12 lp1=90 lb2=22 lp2=91
  chronological: OK (hb1<lb1<hb2<lb2)
  topAbove: OK
  age: 25 >=16 OK
  touch: upper 2, lower 2 OK, distribution OK
  converging: contraction %20 < %25 FAIL -> RED (daralma yetersiz)
  veya
  apex: 300 > bar_index 250 OK, ama progress %95 > %82 WARN -> zayıf
  historical violation: 1 close, max 0.5 ATR OK ama penalty 28 -> zayıf
  rawQuality 42 < 46 FAIL -> RED
```

Böylece TradingView ile karşılaştırma kolay.

## 10. SONRAKİ ADIM

Bu döküman onaylandıktan sonra:

1. `f_build_candidate` Python'a çevrilecek
2. Her formasyon tipi için ayrı fonksiyon (is_triangle, is_flag vs)
3. Her reddedilme loglanacak (rejected_only)
4. Mock data ile test, sonra gerçek BIST data ile
5. TradingView'den THYAO 1H CSV export alıp karşılaştırma

## Kaynak

- Pine Script: ARGENT v0.4.6 FINAL EXPORT, satır 300-800 arası `f_build_candidate`
- Profil: Dengeli (pivotLen=5, minAge=16, minContraction=%25)
