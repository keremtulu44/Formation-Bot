# Formasyon Sonuçları — FRM-01…20 cevap kartları

> **Durum:** üretilen rapor · **Katman:** L1 tanımlayıcı ölçüm (kural değişikliği yok)
> **Kaynak:** `arastirma_cikti/frm.jsonl` + `frm_olay.jsonl`
> **Kolon sözlüğü:** [KOLON_SOZLUGU.md](KOLON_SOZLUGU.md) §13 · **Soru sicili:** [YASAM_TABLOSU.md](YASAM_TABLOSU.md) §4.1

## Kapsam

| Kalem | Değer |
|---|---|
| Seri (sembol × TF) | 704 |
| Sembol | 176 |
| Formasyon | 24615 |
| Formasyon olayı | 183803 |
| Hâlâ açık (sansürlü) | 166 |
| Doğum aralığı | 2024-11-27 → 2026-11-19 |


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
**ÇIKTI**     : son 20 bar getirisi medyan -0.24 ATR (ÇGA -1.86–+1.38) · yukarı olanlar %45.5 (GA %44.9–%46.1) · direk (pole) tabanlı %0.2 (GA %0.1–%0.2)
**TABAN**     : tüm formasyonlar (n=24615, öncül getiri n=24615)
**YAN SÜTUN** : — (ana çıktı zaten doğum öncesi)
**KARAR**     : tanımlayıcı; eşik yok


### FRM-02 · Tip, kalite ve doğum genişliği

**SORU**      : FRM-02 · Hangi formasyon tipi ne sıklıkta doğuyor, kalitesi ve boyu ne?
**AŞAMA**     : S1 (doğum)
**ANA ÇİZGİ** : formasyon tipi
**ÇIKTI**     : dağılım + tip başına medyan kalite/genişlik
**TABAN**     : tüm formasyonlar (n=24615)
**YAN SÜTUN** : n<50 tipler yalnız sayım; oran yorumu yok
**KARAR**     : tanımlayıcı; eşik yok

| tip | n | pay | medyan kalite | medyan genişlik (ATR) |
|---|---|---|---|---|
| Alçalan Üçgen | 7010 | %28.5 | 85 | 0.39 |
| Yükselen Üçgen | 4894 | %19.9 | 85 | 0.45 |
| Alçalan Kama | 4780 | %19.4 | 79 | 0.50 |
| Simetrik Üçgen | 4141 | %16.8 | 78 | 0.51 |
| Yükselen Kama | 3746 | %15.2 | 83 | 0.58 |
| Ayı Bayrağı | 19 | %0.1 | 85 | 1.01 |
| Ayı Flaması | 14 | %0.1 | 83 | 0.76 |
| Boğa Bayrağı | 7 | %0.0 | 91 | 1.52 |


### FRM-03 · Doğumda en yakın korunan seviye ne kadar uzakta?

**SORU**      : FRM-03 · Formasyon doğduğunda en yakın PH/PL seviyesi kaç ATR uzakta?
**AŞAMA**     : S1 (doğum)
**ANA ÇİZGİ** : mesafe kovası (<0.5 · 0.5–1 · 1–2 · 2–3 · ≥3 ATR)
**ÇIKTI**     : kova başına formasyon sayısı + kırılıma varma oranı
**TABAN**     : MS rolü açık olan formasyonlar (n=24483)
**YAN SÜTUN** : rol ucu PH/PL
**KARAR**     : tanımlayıcı; kırılım oranı sütunu keşif niteliğinde

| mesafe | n | kırılım oranı | GA |
|---|---|---|---|
| <0.5 | 422 | %91.9 | %89.0–%94.2 |
| 0.5–1 | 634 | %92.4 | %90.1–%94.2 |
| 1–2 | 2145 | %93.0 | %91.8–%94.0 |
| 2–3 | 3464 | %93.2 | %92.3–%94.0 |
| ≥3 | 17818 | %92.7 | %92.3–%93.1 |



---

## S2 · Olgunlaşma

### FRM-04 · Daralma ne kadar, kaç barda?

**SORU**      : FRM-04 · Formasyon kırılıma kadar ne kadar daralıyor ve kaç bar sürüyor?
**AŞAMA**     : S2 (olgunlaşma)
**ANA ÇİZGİ** : daralma oranı: 1 − genişlik(son gözlem barı)/genişlik(doğum)
**ÇIKTI**     : medyan daralma %74.8 (ÇGA %60.4–%85.8) · geometri fazı medyan 2 bar
**TABAN**     : tüm formasyonlar (n=24615)
**YAN SÜTUN** : geometri fazı kısa: formasyon apeksine yakın doğuyor
**KARAR**     : tanımlayıcı; eşik yok


### FRM-05 · Sıkışmada hacim kurudu mu?

**SORU**      : FRM-05 · Doğumdan olgunlaşmaya rvol düşüyor mu?
**AŞAMA**     : S2 (olgunlaşma)
**ANA ÇİZGİ** : rvol(olgunlaşma) − rvol(doğum)
**ÇIKTI**     : ölçüm yok · eşleşen çift 2868 (vp olgunlaşma kapsaması düşük) · %87.6'inde iki bar birebir aynı
**TABAN**     : hacmi kullanılabilir formasyonlar (n=2868)
**YAN SÜTUN** : yan sütun: rvol · ana çıktı değil
**KARAR**     : ölçüm yok (olgunlaşma penceresi doğumla aynı bar)



---

## S3–S4 · Hazırlık ve deneme

### FRM-06 · Direnç yakınlığı kırılım oranını artırıyor mu?

**SORU**      : FRM-06 · Sınıra en çok yaklaşma (kırılım ÖNCESİ) kırılım oranını değiştiriyor mu?
**AŞAMA**     : S3 (hazırlık)
**ANA ÇİZGİ** : min uzaklık kovası (fitil, ATR)
**ÇIKTI**     : kova başına kırılıma varma oranı
**TABAN**     : tüm formasyonlar (n=24615)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı; doz-yanıt eğrisi

| min uzaklık | n | kırılım oranı | GA |
|---|---|---|---|
| 0–0.5 | 22960 | %94.3 | %94.0–%94.6 |
| 0.5–1 | 1180 | %77.7 | %75.2–%80.0 |
| 1–1.5 | 352 | %62.5 | %57.3–%67.4 |
| 1.5–2 | 101 | %38.6 | %29.7–%48.4 |
| ≥2 | 22 | %27.3 | %13.2–%48.2 |


### FRM-07 · Kaç deneme yapılıyor?

**SORU**      : FRM-07 · Bir formasyon kırılımı kaç kez deniyor?
**AŞAMA**     : S4 (deneme)
**ANA ÇİZGİ** : kırılım fazına giriş epizodu (KIRILIM_DENEMESI + KIRILIM_ADAYI)
**ÇIKTI**     : dağılım (medyan 1 deneme)
**TABAN**     : tüm formasyonlar (n=24615)
**YAN SÜTUN** : zayıf deneme (yalnız KIRILIM_DENEMESI) ayrı kolonda
**KARAR**     : tanımlayıcı

| deneme | n | pay |
|---|---|---|
| 0 | 1778 | %7.2 |
| 1 | 19671 | %79.9 |
| 2 | 2463 | %10.0 |
| 3 | 517 | %2.1 |
| 4 | 142 | %0.6 |
| 5 | 22 | %0.1 |
| 6 | 15 | %0.1 |
| 7 | 2 | %0.0 |
| 9 | 2 | %0.0 |
| 10 | 3 | %0.0 |


### FRM-08 · Kırılım yönü en yakın seviyenin tarafıyla uyumlu mu?

**SORU**      : FRM-08 · Kırılım, en yakın korunan seviyeye doğru mu oluyor?
**AŞAMA**     : S4 (deneme)
**ANA ÇİZGİ** : uyum: yukarı kırılım + üstte PH / aşağı kırılım + altta PL
**ÇIKTI**     : uyum oranı %56.0 (GA %55.3–%56.6)
**TABAN**     : kırılımı olan ve MS rolü açık formasyonlar (n=22738)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı



---

## S5 · Teyit

### FRM-09 · Teyit ne kadar gecikiyor?

**SORU**      : FRM-09 · Kırılım anından teyide kaç bar geçiyor?
**AŞAMA**     : S5 (teyit)
**ANA ÇİZGİ** : bar gecikmesi
**ÇIKTI**     : medyan 1 bar (ÇGA 1–1)
**TABAN**     : teyit alan formasyonlar (n=20153)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı


### FRM-10 · Teyit barı hacmi: teyit mi, tuzak mı?

**SORU**      : FRM-10 · Teyit barındaki hacim, teyit sonrası ≥1 ATR hareketi değiştiriyor mu?
**AŞAMA**     : S5 (teyit)
**ANA ÇİZGİ** : hacim skoru kovası
**ÇIKTI**     : kova başına ≥1 ATR MFE oranı (12 bar)
**TABAN**     : teyit alan formasyonlar (n=20149)
**YAN SÜTUN** : yan sütun: hacim — ana çıktı değil
**KARAR**     : tanımlayıcı; zone'da bulunan 'Q4 zayıf' bulgusuyla karşılaştırılacak

| hacim kovası | n | ≥1 ATR oranı | GA |
|---|---|---|---|
| Q1 (<25) | 9464 | %53.8 | %52.8–%54.8 |
| Q2 (25–50) | 1059 | %56.0 | %53.0–%59.0 |
| Q3 (50–75) | 2850 | %47.5 | %45.6–%49.3 |
| Q4 (≥75) | 6776 | %56.2 | %55.1–%57.4 |


### FRM-11 · Teyit ile MS BOS aynı barda mı?

**SORU**      : FRM-11 · Formasyon teyidi ile yapısal BOS aynı anda mı oluyor?
**AŞAMA**     : S5 (teyit)
**ANA ÇİZGİ** : aynı bar (|gecikme| ≤ 10 bar içinde en yakın BOS)
**ÇIKTI**     : aynı bar oranı %13.4 (GA %12.9–%14.0) · aynı bar + aynı yön %13.1 · medyan |gecikme| 3 bar
**TABAN**     : teyit alan ve ±10 bar içinde BOS bulunan formasyonlar (n=12992)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı



---

## S6 · Retest

### FRM-12 · Retest oranı ne, kaç barda geliyor?

**SORU**      : FRM-12 · Teyitten sonra retest geliyor mu, kaç barda?
**AŞAMA**     : S6 (retest)
**ANA ÇİZGİ** : retest var/yok
**ÇIKTI**     : retest oranı %40.8 (GA %40.2–%41.5) · medyan gecikme 1 bar
**TABAN**     : teyit alan formasyonlar (n=20153)
**YAN SÜTUN** : retest = RETEST_BASARILI state'i (motorun kendi tanımı)
**KARAR**     : tanımlayıcı


### FRM-13 · Retest derinliği başarıyı değiştiriyor mu?

**SORU**      : FRM-13 · Retest sırasında sınıra geri dönüş derinliği ≥1 ATR hareketi değiştiriyor mu?
**AŞAMA**     : S6 (retest)
**ANA ÇİZGİ** : derinlik kovası (ATR)
**ÇIKTI**     : kova başına ≥1 ATR MFE oranı
**TABAN**     : başarılı retest gören teyitli formasyonlar (n=8232)
**YAN SÜTUN** : retest fazına girip geri alamayanlar paydada yok
**KARAR**     : tanımlayıcı

| derinlik | n | ≥1 ATR oranı | GA |
|---|---|---|---|
| <0.25 | 1582 | %61.7 | %59.3–%64.1 |
| 0.25–0.5 | 1157 | %49.4 | %46.5–%52.2 |
| ≥0.5 ATR | 5493 | %35.5 | %34.2–%36.8 |


### FRM-14 · Retest hacmi düşükse başarı artıyor mu?

**SORU**      : FRM-14 · Retest barındaki rvol, teyit sonrası hareketi değiştiriyor mu?
**AŞAMA**     : S6 (retest)
**ANA ÇİZGİ** : rvol medyan bölmesi
**ÇIKTI**     : grup başına ≥1 ATR MFE oranı · fark +6.2 puan (GA +4.0…+8.2) · fark var
**TABAN**     : başarılı retest gören ve rvol'ü ölçülebilen formasyonlar (n=7702)
**YAN SÜTUN** : yan sütun: hacim
**KARAR**     : tanımlayıcı

| grup | n | ≥1 ATR oranı | GA |
|---|---|---|---|
| rvol < medyan | 3851 | %39.4 | %37.9–%41.0 |
| rvol ≥ medyan | 3851 | %45.6 | %44.0–%47.2 |



---

## S7 · Sonuç

### FRM-15 · Sonuç dağılımı (yaşam tablosunun son satırı)

**SORU**      : FRM-15 · Formasyonlar nasıl ölüyor?
**AŞAMA**     : S7 (sonuç)
**ANA ÇİZGİ** : terminal state
**ÇIKTI**     : dağılım + GA
**TABAN**     : ölümle biten formasyonlar (n=23012)
**YAN SÜTUN** : sansür: değiştirilen 1437 · veri sonu 166 (paydaya girmez)
**KARAR**     : tanımlayıcı

| terminal state | n | pay | GA |
|---|---|---|---|
| FORMASYON_TAMAMLANDI | 17115 | %74.4 | %73.8–%74.9 |
| BASARISIZ_KIRILIM | 4863 | %21.1 | %20.6–%21.7 |
| FORMASYON_GECERSIZ | 1034 | %4.5 | %4.2–%4.8 |


### FRM-16 · Tamamlanma süresi ve hareket

**SORU**      : FRM-16 · Tamamlanan formasyon ne kadar sürüyor ve teyitten sonra ne kadar gidiyor?
**AŞAMA**     : S7 (sonuç)
**ANA ÇİZGİ** : ömür (bar) · teyit sonrası MFE (ATR, 12 bar)
**ÇIKTI**     : medyan ömür 13 bar · medyan MFE 1.27 ATR (ÇGA 0.64–2.18)
**TABAN**     : tamamlanan formasyonlar (n=17115)
**YAN SÜTUN** : uzun pencere (40 bar) ayrı kolonda
**KARAR**     : tanımlayıcı


### FRM-17 · Başarısız kırılım ne kadar geri dönüyor?

**SORU**      : FRM-17 · Başarısız kırılımda teyit sonrası ters hareket ne kadar?
**AŞAMA**     : S7 (sonuç)
**ANA ÇİZGİ** : MAE (ATR, 12 bar)
**ÇIKTI**     : medyan 2.81 ATR (ÇGA 2.03–3.90)
**TABAN**     : başarısız kırılımlar (n=4863)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı


### FRM-18 · Geçersizleşme hangi aşamada oluyor?

**SORU**      : FRM-18 · Formasyon hangi aşamada geçersizleşiyor?
**AŞAMA**     : S7 (sonuç)
**ANA ÇİZGİ** : geçersizleşmeden ÖNCEKİ state
**ÇIKTI**     : dağılım
**TABAN**     : geçersizleşen formasyonlar (n=1034) · ayrıca WEAK olayı: 14978
**YAN SÜTUN** : doğumda ölen 45 (paydada; ayrı satır)
**KARAR**     : tanımlayıcı

| önceki state | n | pay |
|---|---|---|
| FORMASYON_TANIMLANDI | 513 | %49.6 |
| FORMASYON_ZAYIFLADI | 318 | %30.8 |
| KIRILIM_HAZIRLIGI | 158 | %15.3 |
| DOĞUMDA (ömür 1 bar) | 45 | %4.4 |



---

## Çapraz

### FRM-19 · Kırılım noktasında OB/FVG var mı?

**SORU**      : FRM-19 · Kırılım anında fiyat canlı bir OB/FVG zone'u içindeyse sonuç değişiyor mu?
**AŞAMA**     : Çapraz
**ANA ÇİZGİ** : zone var / yok
**ÇIKTI**     : tamamlanma oranı · fark −1.5 puan (GA −2.7…−0.4) · fark var
**TABAN**     : kırılımı olan formasyonlar (n=22831)
**YAN SÜTUN** : OB ve FVG ayrı ayrı (bağımsız kolonlar) altta
**KARAR**     : fark var (GA sıfırı içermiyor)

| grup | n | tamamlanma | GA |
|---|---|---|---|
| zone var | 8984 | %74.0 | %73.1–%74.9 |
| zone yok | 13847 | %75.6 | %74.8–%76.3 |

| ayrıştırma (yan sütun) | n | tamamlanma | fark (GA) |
|---|---|---|---|
| OB var | 8541 | %73.6 | fark −2.2 puan (GA −3.4…−1.1) · fark var |
| FVG var | 584 | %81.0 | fark +6.2 puan (GA +2.9…+9.0) · fark var |


### FRM-20 · Formasyon yönü ile MS yönü uyumu

**SORU**      : FRM-20 · Kırılım yönü en yakın rol seviyesine doğruysa sonuç değişiyor mu?
**AŞAMA**     : Çapraz
**ANA ÇİZGİ** : uyumlu / uyumsuz
**ÇIKTI**     : tamamlanma oranı · fark +9.6 puan (GA +8.4…+10.7) · fark var
**TABAN**     : kırılımı olan ve MS rolü açık formasyonlar (n=22738)
**YAN SÜTUN** : —
**KARAR**     : fark var (GA sıfırı içermiyor)

| grup | n | tamamlanma | GA |
|---|---|---|---|
| uyumlu | 12730 | %79.3 | %78.5–%79.9 |
| uyumsuz | 10008 | %69.6 | %68.7–%70.5 |

