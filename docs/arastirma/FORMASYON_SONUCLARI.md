# Formasyon Sonuçları — FRM-01…20 cevap kartları

> **Durum:** üretilen rapor · **Katman:** L1 tanımlayıcı ölçüm (kural değişikliği yok)
> **Kaynak:** `arastirma_cikti/frm.jsonl` + `frm_olay.jsonl`
> **Kolon sözlüğü:** [KOLON_SOZLUGU.md](KOLON_SOZLUGU.md) §13 · **Soru sicili:** [YASAM_TABLOSU.md](YASAM_TABLOSU.md) §4.1

## Kapsam

| Kalem | Değer |
|---|---|
| Seri (sembol × TF) | 704 |
| Sembol | 176 |
| Formasyon | 33964 |
| Formasyon olayı | 229785 |
| Hâlâ açık (sansürlü) | 171 |
| Doğum aralığı | 2024-11-27 → 2026-10-19 |


## Okuma kuralları

- `n < 50` → sayı yazılmaz, **ölçüm yok**.
- Oranlarda **Wilson %95 GA**; farklarda **sembol küme bootstrap**.
- "fark var" yalnız GA sıfırı içermediğinde yazılır.
- Bunlar **tanımlayıcı** bulgulardır; ayrı pencerede tekrar test edilmeden kural hâline gelmez.


---

## S0–S1 · Doğum

### FRM-01 · Öncül hareket

**SORU**      : FRM-01 · Formasyon doğmadan önce öncül hareket var mıydı, yönü neydi?
**AŞAMA**     : S0 (doğum öncesi)
**ANA ÇİZGİ** : doğumdan önceki 20 barın getirisi (ATR) + direk (pole) varlığı
**ÇIKTI**     : son 20 bar getirisi medyan -0.04 ATR (ÇGA -1.91–+1.87) · yukarı olanlar %48.8 (GA %48.2–%49.3) · direk (pole) tabanlı %0.1 (GA %0.1–%0.2)
**TABAN**     : tüm formasyonlar (n=33964, öncül getiri n=33964)
**YAN SÜTUN** : — (ana çıktı zaten doğum öncesi)
**KARAR**     : tanımlayıcı; eşik yok


### FRM-02 · Tip, kalite ve doğum genişliği

**SORU**      : FRM-02 · Hangi formasyon tipi ne sıklıkta doğuyor, kalitesi ve boyu ne?
**AŞAMA**     : S1 (doğum)
**ANA ÇİZGİ** : formasyon tipi
**ÇIKTI**     : dağılım + tip başına medyan kalite/genişlik
**TABAN**     : tüm formasyonlar (n=33964)
**YAN SÜTUN** : n<50 tipler yalnız sayım; oran yorumu yok
**KARAR**     : tanımlayıcı; eşik yok

| tip | n | pay | medyan kalite | medyan genişlik (ATR) |
|---|---|---|---|---|
| Alçalan Üçgen | 9794 | %28.8 | 84 | 0.34 |
| Yükselen Üçgen | 7736 | %22.8 | 84 | 0.38 |
| Yükselen Kama | 6862 | %20.2 | 84 | 0.51 |
| Alçalan Kama | 6556 | %19.3 | 80 | 0.46 |
| Simetrik Üçgen | 2971 | %8.7 | 80 | 0.52 |
| Ayı Flaması | 16 | %0.0 | 84 | 0.82 |
| Ayı Bayrağı | 16 | %0.0 | 86 | 1.01 |
| Boğa Bayrağı | 9 | %0.0 | 91 | 2.10 |


### FRM-03 · Doğumda en yakın korunan seviye ne kadar uzakta?

**SORU**      : FRM-03 · Formasyon doğduğunda en yakın PH/PL seviyesi kaç ATR uzakta?
**AŞAMA**     : S1 (doğum)
**ANA ÇİZGİ** : mesafe kovası (<0.5 · 0.5–1 · 1–2 · 2–3 · ≥3 ATR)
**ÇIKTI**     : kova başına formasyon sayısı + kırılıma varma oranı
**TABAN**     : MS rolü açık olan formasyonlar (n=30983)
**YAN SÜTUN** : rol ucu PH/PL
**KARAR**     : tanımlayıcı; kırılım oranı sütunu keşif niteliğinde

| mesafe | n | kırılım oranı | GA |
|---|---|---|---|
| <0.5 | 524 | %93.1 | %90.6–%95.0 |
| 0.5–1 | 779 | %95.0 | %93.2–%96.3 |
| 1–2 | 2676 | %94.4 | %93.5–%95.2 |
| 2–3 | 4043 | %94.6 | %93.8–%95.2 |
| ≥3 | 22961 | %94.5 | %94.2–%94.8 |



---

## S2 · Olgunlaşma

### FRM-04 · Daralma ne kadar, kaç barda?

**SORU**      : FRM-04 · Formasyon kırılıma kadar ne kadar daralıyor ve kaç bar sürüyor?
**AŞAMA**     : S2 (olgunlaşma)
**ANA ÇİZGİ** : daralma oranı: 1 − genişlik(son gözlem barı)/genişlik(doğum)
**ÇIKTI**     : medyan daralma %76.6 (ÇGA %63.4–%86.2) · geometri fazı medyan 1 bar
**TABAN**     : tüm formasyonlar (n=33964)
**YAN SÜTUN** : geometri fazı kısa: formasyon apeksine yakın doğuyor
**KARAR**     : tanımlayıcı; eşik yok


### FRM-05 · Sıkışmada hacim kurudu mu?

**SORU**      : FRM-05 · Doğumdan olgunlaşmaya rvol düşüyor mu?
**AŞAMA**     : S2 (olgunlaşma)
**ANA ÇİZGİ** : rvol(olgunlaşma) − rvol(doğum)
**ÇIKTI**     : ölçüm yok · eşleşen çift 2260 (vp olgunlaşma kapsaması düşük) · %85.1'inde iki bar birebir aynı
**TABAN**     : hacmi kullanılabilir formasyonlar (n=2260)
**YAN SÜTUN** : yan sütun: rvol · ana çıktı değil
**KARAR**     : ölçüm yok (olgunlaşma penceresi doğumla aynı bar)



---

## S3–S4 · Hazırlık ve deneme

### FRM-06 · Direnç yakınlığı kırılım oranını artırıyor mu?

**SORU**      : FRM-06 · Sınıra en çok yaklaşma (kırılım ÖNCESİ) kırılım oranını değiştiriyor mu?
**AŞAMA**     : S3 (hazırlık)
**ANA ÇİZGİ** : min uzaklık kovası (fitil, ATR)
**ÇIKTI**     : kova başına kırılıma varma oranı
**TABAN**     : tüm formasyonlar (n=33964)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı; doz-yanıt eğrisi

| min uzaklık | n | kırılım oranı | GA |
|---|---|---|---|
| 0–0.5 | 32551 | %95.6 | %95.4–%95.8 |
| 0.5–1 | 1035 | %80.7 | %78.2–%83.0 |
| 1–1.5 | 287 | %56.8 | %51.0–%62.4 |
| 1.5–2 | 74 | %51.4 | %40.2–%62.4 |
| ≥2 | 17 | %17.6 | %6.2–%41.0 |


### FRM-07 · Kaç deneme yapılıyor?

**SORU**      : FRM-07 · Bir formasyon kırılımı kaç kez deniyor?
**AŞAMA**     : S4 (deneme)
**ANA ÇİZGİ** : kırılım fazına giriş epizodu (KIRILIM_DENEMESI + KIRILIM_ADAYI)
**ÇIKTI**     : dağılım (medyan 1 deneme)
**TABAN**     : tüm formasyonlar (n=33964)
**YAN SÜTUN** : zayıf deneme (yalnız KIRILIM_DENEMESI) ayrı kolonda
**KARAR**     : tanımlayıcı

| deneme | n | pay |
|---|---|---|
| 0 | 1813 | %5.3 |
| 1 | 26481 | %78.0 |
| 2 | 4250 | %12.5 |
| 3 | 999 | %2.9 |
| 4 | 289 | %0.9 |
| 5 | 82 | %0.2 |
| 6 | 28 | %0.1 |
| 7 | 9 | %0.0 |
| 8 | 3 | %0.0 |
| 9 | 2 | %0.0 |
| 10 | 4 | %0.0 |
| 11 | 3 | %0.0 |
| 17 | 1 | %0.0 |


### FRM-08 · Kırılım yönü en yakın seviyenin tarafıyla uyumlu mu?

**SORU**      : FRM-08 · Kırılım, en yakın korunan seviyeye doğru mu oluyor?
**AŞAMA**     : S4 (deneme)
**ANA ÇİZGİ** : uyum: yukarı kırılım + üstte PH / aşağı kırılım + altta PL
**ÇIKTI**     : uyum oranı %53.7 (GA %53.1–%54.2)
**TABAN**     : kırılımı olan ve MS rolü açık formasyonlar (n=29297)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı



---

## S5 · Teyit

### FRM-09 · Teyit ne kadar gecikiyor?

**SORU**      : FRM-09 · Kırılım anından teyide kaç bar geçiyor?
**AŞAMA**     : S5 (teyit)
**ANA ÇİZGİ** : bar gecikmesi
**ÇIKTI**     : medyan 1 bar (ÇGA 1–2)
**TABAN**     : teyit alan formasyonlar (n=28624)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı


### FRM-10 · Teyit barı hacmi: teyit mi, tuzak mı?

**SORU**      : FRM-10 · Teyit barındaki hacim, teyit sonrası ≥1 ATR hareketi değiştiriyor mu?
**AŞAMA**     : S5 (teyit)
**ANA ÇİZGİ** : hacim skoru kovası
**ÇIKTI**     : kova başına ≥1 ATR MFE oranı (12 bar)
**TABAN**     : teyit alan formasyonlar (n=28611)
**YAN SÜTUN** : yan sütun: hacim — ana çıktı değil
**KARAR**     : tanımlayıcı; zone'da bulunan 'Q4 zayıf' bulgusuyla karşılaştırılacak

| hacim kovası | n | ≥1 ATR oranı | GA |
|---|---|---|---|
| Q1 (<25) | 15094 | %52.4 | %51.6–%53.2 |
| Q2 (25–50) | 1494 | %54.6 | %52.1–%57.1 |
| Q3 (50–75) | 3631 | %47.6 | %46.0–%49.3 |
| Q4 (≥75) | 8392 | %54.7 | %53.6–%55.8 |


### FRM-11 · Teyit ile MS BOS aynı barda mı?

**SORU**      : FRM-11 · Formasyon teyidi ile yapısal BOS aynı anda mı oluyor?
**AŞAMA**     : S5 (teyit)
**ANA ÇİZGİ** : aynı bar (|gecikme| ≤ 10 bar içinde en yakın BOS)
**ÇIKTI**     : aynı bar oranı %12.3 (GA %11.8–%12.8) · aynı bar + aynı yön %11.6 · medyan |gecikme| 3 bar
**TABAN**     : teyit alan ve ±10 bar içinde BOS bulunan formasyonlar (n=16541)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı



---

## S6 · Retest

### FRM-12 · Retest oranı ne, kaç barda geliyor?

**SORU**      : FRM-12 · Teyitten sonra retest geliyor mu, kaç barda?
**AŞAMA**     : S6 (retest)
**ANA ÇİZGİ** : retest var/yok
**ÇIKTI**     : retest oranı %34.9 (GA %34.4–%35.5) · medyan gecikme 1 bar
**TABAN**     : teyit alan formasyonlar (n=28624)
**YAN SÜTUN** : retest = RETEST_BASARILI state'i (motorun kendi tanımı)
**KARAR**     : tanımlayıcı


### FRM-13 · Retest derinliği başarıyı değiştiriyor mu?

**SORU**      : FRM-13 · Retest sırasında sınıra geri dönüş derinliği ≥1 ATR hareketi değiştiriyor mu?
**AŞAMA**     : S6 (retest)
**ANA ÇİZGİ** : derinlik kovası (ATR)
**ÇIKTI**     : kova başına ≥1 ATR MFE oranı
**TABAN**     : başarılı retest gören teyitli formasyonlar (n=9991)
**YAN SÜTUN** : retest fazına girip geri alamayanlar paydada yok
**KARAR**     : tanımlayıcı

| derinlik | n | ≥1 ATR oranı | GA |
|---|---|---|---|
| <0.25 | 1989 | %60.8 | %58.7–%63.0 |
| 0.25–0.5 | 1448 | %50.8 | %48.2–%53.3 |
| ≥0.5 ATR | 6554 | %33.2 | %32.1–%34.4 |


### FRM-14 · Retest hacmi düşükse başarı artıyor mu?

**SORU**      : FRM-14 · Retest barındaki rvol, teyit sonrası hareketi değiştiriyor mu?
**AŞAMA**     : S6 (retest)
**ANA ÇİZGİ** : rvol medyan bölmesi
**ÇIKTI**     : grup başına ≥1 ATR MFE oranı · fark +4.6 puan (GA +2.5…+6.9) · fark var
**TABAN**     : başarılı retest gören ve rvol'ü ölçülebilen formasyonlar (n=9336)
**YAN SÜTUN** : yan sütun: hacim
**KARAR**     : tanımlayıcı

| grup | n | ≥1 ATR oranı | GA |
|---|---|---|---|
| rvol < medyan | 4668 | %38.8 | %37.5–%40.2 |
| rvol ≥ medyan | 4668 | %43.5 | %42.1–%44.9 |



---

## S7 · Sonuç

### FRM-15 · Sonuç dağılımı (yaşam tablosunun son satırı)

**SORU**      : FRM-15 · Formasyonlar nasıl ölüyor?
**AŞAMA**     : S7 (sonuç)
**ANA ÇİZGİ** : terminal state
**ÇIKTI**     : dağılım + GA
**TABAN**     : ölümle biten formasyonlar (n=32321)
**YAN SÜTUN** : sansür: değiştirilen 1472 · veri sonu 171 (paydaya girmez)
**KARAR**     : tanımlayıcı

| terminal state | n | pay | GA |
|---|---|---|---|
| FORMASYON_TAMAMLANDI | 24618 | %76.2 | %75.7–%76.6 |
| BASARISIZ_KIRILIM | 6186 | %19.1 | %18.7–%19.6 |
| FORMASYON_GECERSIZ | 1517 | %4.7 | %4.5–%4.9 |


### FRM-16 · Tamamlanma süresi ve hareket

**SORU**      : FRM-16 · Tamamlanan formasyon ne kadar sürüyor ve teyitten sonra ne kadar gidiyor?
**AŞAMA**     : S7 (sonuç)
**ANA ÇİZGİ** : ömür (bar) · teyit sonrası MFE (ATR, 12 bar)
**ÇIKTI**     : medyan ömür 11 bar · medyan MFE 1.23 ATR (ÇGA 0.61–2.14)
**TABAN**     : tamamlanan formasyonlar (n=24618)
**YAN SÜTUN** : uzun pencere (40 bar) ayrı kolonda
**KARAR**     : tanımlayıcı


### FRM-17 · Başarısız kırılım ne kadar geri dönüyor?

**SORU**      : FRM-17 · Başarısız kırılımda teyit sonrası ters hareket ne kadar?
**AŞAMA**     : S7 (sonuç)
**ANA ÇİZGİ** : MAE (ATR, 12 bar)
**ÇIKTI**     : medyan 2.83 ATR (ÇGA 2.00–4.00)
**TABAN**     : başarısız kırılımlar (n=6186)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı


### FRM-18 · Geçersizleşme hangi aşamada oluyor?

**SORU**      : FRM-18 · Formasyon hangi aşamada geçersizleşiyor?
**AŞAMA**     : S7 (sonuç)
**ANA ÇİZGİ** : geçersizleşmeden ÖNCEKİ state
**ÇIKTI**     : dağılım
**TABAN**     : geçersizleşen formasyonlar (n=1517) · ayrıca WEAK olayı: 15631
**YAN SÜTUN** : doğumda ölen 267 (paydada; ayrı satır)
**KARAR**     : tanımlayıcı

| önceki state | n | pay |
|---|---|---|
| FORMASYON_TANIMLANDI | 764 | %50.4 |
| FORMASYON_ZAYIFLADI | 328 | %21.6 |
| DOĞUMDA (ömür 1 bar) | 267 | %17.6 |
| KIRILIM_HAZIRLIGI | 158 | %10.4 |



---

## Çapraz

### FRM-19 · Kırılım noktasında OB/FVG var mı?

**SORU**      : FRM-19 · Kırılım anında fiyat canlı bir OB/FVG zone'u içindeyse sonuç değişiyor mu?
**AŞAMA**     : Çapraz
**ANA ÇİZGİ** : zone var / yok
**ÇIKTI**     : tamamlanma oranı · fark −1.1 puan (GA −2.2…−0.2) · fark var
**TABAN**     : kırılımı olan formasyonlar (n=32137)
**YAN SÜTUN** : OB ve FVG ayrı ayrı (bağımsız kolonlar) altta
**KARAR**     : fark var (GA sıfırı içermiyor)

| grup | n | tamamlanma | GA |
|---|---|---|---|
| zone var | 11905 | %75.9 | %75.1–%76.6 |
| zone yok | 20232 | %77.0 | %76.4–%77.6 |

| ayrıştırma (yan sütun) | n | tamamlanma | fark (GA) |
|---|---|---|---|
| OB var | 11249 | %75.7 | fark −1.4 puan (GA −2.5…−0.4) · fark var |
| FVG var | 859 | %79.0 | fark +2.5 puan (GA −0.1…+5.1) · fark yok |


### FRM-20 · Formasyon yönü ile MS yönü uyumu

**SORU**      : FRM-20 · Kırılım yönü en yakın rol seviyesine doğruysa sonuç değişiyor mu?
**AŞAMA**     : Çapraz
**ANA ÇİZGİ** : uyumlu / uyumsuz
**ÇIKTI**     : tamamlanma oranı · fark +6.6 puan (GA +5.5…+7.7) · fark var
**TABAN**     : kırılımı olan ve MS rolü açık formasyonlar (n=29297)
**YAN SÜTUN** : —
**KARAR**     : fark var (GA sıfırı içermiyor)

| grup | n | tamamlanma | GA |
|---|---|---|---|
| uyumlu | 15724 | %79.7 | %79.0–%80.3 |
| uyumsuz | 13573 | %73.1 | %72.3–%73.8 |

