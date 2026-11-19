# Formasyon Sonuçları — FRM-01…20 cevap kartları

> **Durum:** üretilen rapor · **Katman:** L1 tanımlayıcı ölçüm (kural değişikliği yok)
> **Kaynak:** `arastirma_cikti/frm.jsonl` + `frm_olay.jsonl`
> **Kolon sözlüğü:** [KOLON_SOZLUGU.md](KOLON_SOZLUGU.md) §13 · **Soru sicili:** [YASAM_TABLOSU.md](YASAM_TABLOSU.md) §4.1

## Kapsam

| Kalem | Değer |
|---|---|
| Seri (sembol × TF) | 176 |
| Sembol | 44 |
| Formasyon | 6455 |
| Formasyon olayı | 48088 |
| Hâlâ açık (sansürlü) | 43 |
| Doğum aralığı | 2024-11-29 → 2026-11-19 |


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
**ÇIKTI**     : son 20 bar getirisi medyan -0.23 ATR (ÇGA -1.83–+1.39) · yukarı olanlar %45.5 (GA %44.3–%46.8) · direk (pole) tabanlı %0.1 (GA %0.1–%0.3)
**TABAN**     : tüm formasyonlar (n=6455, öncül getiri n=6455)
**YAN SÜTUN** : — (ana çıktı zaten doğum öncesi)
**KARAR**     : tanımlayıcı; eşik yok


### FRM-02 · Tip, kalite ve doğum genişliği

**SORU**      : FRM-02 · Hangi formasyon tipi ne sıklıkta doğuyor, kalitesi ve boyu ne?
**AŞAMA**     : S1 (doğum)
**ANA ÇİZGİ** : formasyon tipi
**ÇIKTI**     : dağılım + tip başına medyan kalite/genişlik
**TABAN**     : tüm formasyonlar (n=6455)
**YAN SÜTUN** : n<50 tipler yalnız sayım; oran yorumu yok
**KARAR**     : tanımlayıcı; eşik yok

| tip | n | pay | medyan kalite | medyan genişlik (ATR) |
|---|---|---|---|---|
| Alçalan Üçgen | 1801 | %27.9 | 85 | 0.83 |
| Yükselen Üçgen | 1323 | %20.5 | 85 | 0.82 |
| Alçalan Kama | 1189 | %18.4 | 79 | 0.97 |
| Simetrik Üçgen | 1093 | %16.9 | 78 | 0.90 |
| Yükselen Kama | 1040 | %16.1 | 83 | 0.81 |
| Ayı Bayrağı | 5 | %0.1 | 83 | 1.09 |
| Boğa Bayrağı | 3 | %0.0 | 92 | 7.26 |
| Boğa Flaması | 1 | %0.0 | 85 | 2.81 |


### FRM-03 · Doğumda en yakın korunan seviye ne kadar uzakta?

**SORU**      : FRM-03 · Formasyon doğduğunda en yakın PH/PL seviyesi kaç ATR uzakta?
**AŞAMA**     : S1 (doğum)
**ANA ÇİZGİ** : mesafe kovası (<0.5 · 0.5–1 · 1–2 · 2–3 · ≥3 ATR)
**ÇIKTI**     : kova başına formasyon sayısı + kırılıma varma oranı
**TABAN**     : MS rolü açık olan formasyonlar (n=6429)
**YAN SÜTUN** : rol ucu PH/PL
**KARAR**     : tanımlayıcı; kırılım oranı sütunu keşif niteliğinde

| mesafe | n | kırılım oranı | GA |
|---|---|---|---|
| <0.5 | 101 | %94.1 | %87.6–%97.2 |
| 0.5–1 | 181 | %92.3 | %87.4–%95.3 |
| 1–2 | 576 | %94.3 | %92.1–%95.9 |
| 2–3 | 898 | %92.1 | %90.1–%93.7 |
| ≥3 | 4673 | %92.9 | %92.1–%93.6 |



---

## S2 · Olgunlaşma

### FRM-04 · Daralma ne kadar, kaç barda?

**SORU**      : FRM-04 · Formasyon kırılıma kadar ne kadar daralıyor ve kaç bar sürüyor?
**AŞAMA**     : S2 (olgunlaşma)
**ANA ÇİZGİ** : daralma oranı: 1 − genişlik(son gözlem barı)/genişlik(doğum)
**ÇIKTI**     : medyan daralma %74.1 (ÇGA %59.8–%85.2) · geometri fazı medyan 2 bar
**TABAN**     : tüm formasyonlar (n=6455)
**YAN SÜTUN** : geometri fazı kısa: formasyon apeksine yakın doğuyor
**KARAR**     : tanımlayıcı; eşik yok


### FRM-05 · Sıkışmada hacim kurudu mu?

**SORU**      : FRM-05 · Doğumdan olgunlaşmaya rvol düşüyor mu?
**AŞAMA**     : S2 (olgunlaşma)
**ANA ÇİZGİ** : rvol(olgunlaşma) − rvol(doğum)
**ÇIKTI**     : ölçüm yok · eşleşen çift 799 (vp olgunlaşma kapsaması düşük) · %86.9'inde iki bar birebir aynı
**TABAN**     : hacmi kullanılabilir formasyonlar (n=799)
**YAN SÜTUN** : yan sütun: rvol · ana çıktı değil
**KARAR**     : ölçüm yok (olgunlaşma penceresi doğumla aynı bar)



---

## S3–S4 · Hazırlık ve deneme

### FRM-06 · Direnç yakınlığı kırılım oranını artırıyor mu?

**SORU**      : FRM-06 · Sınıra en çok yaklaşma (kırılım ÖNCESİ) kırılım oranını değiştiriyor mu?
**AŞAMA**     : S3 (hazırlık)
**ANA ÇİZGİ** : min uzaklık kovası (fitil, ATR)
**ÇIKTI**     : kova başına kırılıma varma oranı
**TABAN**     : tüm formasyonlar (n=6455)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı; doz-yanıt eğrisi

| min uzaklık | n | kırılım oranı | GA |
|---|---|---|---|
| 0–0.5 | 5996 | %94.6 | %94.0–%95.2 |
| 0.5–1 | 337 | %76.3 | %71.4–%80.5 |
| 1–1.5 | 92 | %56.5 | %46.3–%66.2 |
| 1.5–2 | 26 | %34.6 | %19.4–%53.8 |
| ≥2 | 4 | — | — |


### FRM-07 · Kaç deneme yapılıyor?

**SORU**      : FRM-07 · Bir formasyon kırılımı kaç kez deniyor?
**AŞAMA**     : S4 (deneme)
**ANA ÇİZGİ** : kırılım fazına giriş epizodu (KIRILIM_DENEMESI + KIRILIM_ADAYI)
**ÇIKTI**     : dağılım (medyan 1 deneme)
**TABAN**     : tüm formasyonlar (n=6455)
**YAN SÜTUN** : zayıf deneme (yalnız KIRILIM_DENEMESI) ayrı kolonda
**KARAR**     : tanımlayıcı

| deneme | n | pay |
|---|---|---|
| 0 | 459 | %7.1 |
| 1 | 5196 | %80.5 |
| 2 | 625 | %9.7 |
| 3 | 136 | %2.1 |
| 4 | 31 | %0.5 |
| 5 | 3 | %0.0 |
| 6 | 4 | %0.1 |
| 7 | 1 | %0.0 |


### FRM-08 · Kırılım yönü en yakın seviyenin tarafıyla uyumlu mu?

**SORU**      : FRM-08 · Kırılım, en yakın korunan seviyeye doğru mu oluyor?
**AŞAMA**     : S4 (deneme)
**ANA ÇİZGİ** : uyum: yukarı kırılım + üstte PH / aşağı kırılım + altta PL
**ÇIKTI**     : uyum oranı %56.9 (GA %55.7–%58.2)
**TABAN**     : kırılımı olan ve MS rolü açık formasyonlar (n=5981)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı



---

## S5 · Teyit

### FRM-09 · Teyit ne kadar gecikiyor?

**SORU**      : FRM-09 · Kırılım anından teyide kaç bar geçiyor?
**AŞAMA**     : S5 (teyit)
**ANA ÇİZGİ** : bar gecikmesi
**ÇIKTI**     : medyan 1 bar (ÇGA 1–1)
**TABAN**     : teyit alan formasyonlar (n=5296)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı


### FRM-10 · Teyit barı hacmi: teyit mi, tuzak mı?

**SORU**      : FRM-10 · Teyit barındaki hacim, teyit sonrası ≥1 ATR hareketi değiştiriyor mu?
**AŞAMA**     : S5 (teyit)
**ANA ÇİZGİ** : hacim skoru kovası
**ÇIKTI**     : kova başına ≥1 ATR MFE oranı (12 bar)
**TABAN**     : teyit alan formasyonlar (n=5293)
**YAN SÜTUN** : yan sütun: hacim — ana çıktı değil
**KARAR**     : tanımlayıcı; zone'da bulunan 'Q4 zayıf' bulgusuyla karşılaştırılacak

| hacim kovası | n | ≥1 ATR oranı | GA |
|---|---|---|---|
| Q1 (<25) | 2525 | %55.2 | %53.2–%57.1 |
| Q2 (25–50) | 270 | %55.6 | %49.6–%61.4 |
| Q3 (50–75) | 711 | %47.4 | %43.8–%51.1 |
| Q4 (≥75) | 1787 | %56.3 | %54.0–%58.6 |


### FRM-11 · Teyit ile MS BOS aynı barda mı?

**SORU**      : FRM-11 · Formasyon teyidi ile yapısal BOS aynı anda mı oluyor?
**AŞAMA**     : S5 (teyit)
**ANA ÇİZGİ** : aynı bar (|gecikme| ≤ 10 bar içinde en yakın BOS)
**ÇIKTI**     : aynı bar oranı %12.7 (GA %11.6–%13.9) · aynı bar + aynı yön %12.4 · medyan |gecikme| 3 bar
**TABAN**     : teyit alan ve ±10 bar içinde BOS bulunan formasyonlar (n=3433)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı



---

## S6 · Retest

### FRM-12 · Retest oranı ne, kaç barda geliyor?

**SORU**      : FRM-12 · Teyitten sonra retest geliyor mu, kaç barda?
**AŞAMA**     : S6 (retest)
**ANA ÇİZGİ** : retest var/yok
**ÇIKTI**     : retest oranı %41.1 (GA %39.8–%42.4) · medyan gecikme 1 bar
**TABAN**     : teyit alan formasyonlar (n=5296)
**YAN SÜTUN** : retest = RETEST_BASARILI state'i (motorun kendi tanımı)
**KARAR**     : tanımlayıcı


### FRM-13 · Retest derinliği başarıyı değiştiriyor mu?

**SORU**      : FRM-13 · Retest sırasında sınıra geri dönüş derinliği ≥1 ATR hareketi değiştiriyor mu?
**AŞAMA**     : S6 (retest)
**ANA ÇİZGİ** : derinlik kovası (ATR)
**ÇIKTI**     : kova başına ≥1 ATR MFE oranı
**TABAN**     : başarılı retest gören teyitli formasyonlar (n=2177)
**YAN SÜTUN** : retest fazına girip geri alamayanlar paydada yok
**KARAR**     : tanımlayıcı

| derinlik | n | ≥1 ATR oranı | GA |
|---|---|---|---|
| <0.25 | 421 | %63.7 | %59.0–%68.1 |
| 0.25–0.5 | 296 | %45.9 | %40.4–%51.6 |
| ≥0.5 ATR | 1460 | %36.6 | %34.2–%39.1 |


### FRM-14 · Retest hacmi düşükse başarı artıyor mu?

**SORU**      : FRM-14 · Retest barındaki rvol, teyit sonrası hareketi değiştiriyor mu?
**AŞAMA**     : S6 (retest)
**ANA ÇİZGİ** : rvol medyan bölmesi
**ÇIKTI**     : grup başına ≥1 ATR MFE oranı · fark +8.3 puan (GA +4.9…+11.6) · fark var
**TABAN**     : başarılı retest gören ve rvol'ü ölçülebilen formasyonlar (n=2060)
**YAN SÜTUN** : yan sütun: hacim
**KARAR**     : tanımlayıcı

| grup | n | ≥1 ATR oranı | GA |
|---|---|---|---|
| rvol < medyan | 1030 | %39.0 | %36.1–%42.0 |
| rvol ≥ medyan | 1030 | %47.3 | %44.2–%50.3 |



---

## S7 · Sonuç

### FRM-15 · Sonuç dağılımı (yaşam tablosunun son satırı)

**SORU**      : FRM-15 · Formasyonlar nasıl ölüyor?
**AŞAMA**     : S7 (sonuç)
**ANA ÇİZGİ** : terminal state
**ÇIKTI**     : dağılım + GA
**TABAN**     : ölümle biten formasyonlar (n=6018)
**YAN SÜTUN** : sansür: değiştirilen 394 · veri sonu 43 (paydaya girmez)
**KARAR**     : tanımlayıcı

| terminal state | n | pay | GA |
|---|---|---|---|
| FORMASYON_TAMAMLANDI | 4495 | %74.7 | %73.6–%75.8 |
| BASARISIZ_KIRILIM | 1324 | %22.0 | %21.0–%23.1 |
| FORMASYON_GECERSIZ | 199 | %3.3 | %2.9–%3.8 |


### FRM-16 · Tamamlanma süresi ve hareket

**SORU**      : FRM-16 · Tamamlanan formasyon ne kadar sürüyor ve teyitten sonra ne kadar gidiyor?
**AŞAMA**     : S7 (sonuç)
**ANA ÇİZGİ** : ömür (bar) · teyit sonrası MFE (ATR, 12 bar)
**ÇIKTI**     : medyan ömür 13 bar · medyan MFE 1.27 ATR (ÇGA 0.66–2.15)
**TABAN**     : tamamlanan formasyonlar (n=4495)
**YAN SÜTUN** : uzun pencere (40 bar) ayrı kolonda
**KARAR**     : tanımlayıcı


### FRM-17 · Başarısız kırılım ne kadar geri dönüyor?

**SORU**      : FRM-17 · Başarısız kırılımda teyit sonrası ters hareket ne kadar?
**AŞAMA**     : S7 (sonuç)
**ANA ÇİZGİ** : MAE (ATR, 12 bar)
**ÇIKTI**     : medyan 2.79 ATR (ÇGA 1.99–3.80)
**TABAN**     : başarısız kırılımlar (n=1324)
**YAN SÜTUN** : —
**KARAR**     : tanımlayıcı


### FRM-18 · Geçersizleşme hangi aşamada oluyor?

**SORU**      : FRM-18 · Formasyon hangi aşamada geçersizleşiyor?
**AŞAMA**     : S7 (sonuç)
**ANA ÇİZGİ** : geçersizleşmeden ÖNCEKİ state
**ÇIKTI**     : dağılım
**TABAN**     : geçersizleşen formasyonlar (n=199) · ayrıca WEAK olayı: 3898
**YAN SÜTUN** : doğumda ölen 6 (paydada; ayrı satır)
**KARAR**     : tanımlayıcı

| önceki state | n | pay |
|---|---|---|
| FORMASYON_TANIMLANDI | 105 | %52.8 |
| FORMASYON_ZAYIFLADI | 55 | %27.6 |
| KIRILIM_HAZIRLIGI | 33 | %16.6 |
| DOĞUMDA (ömür 1 bar) | 6 | %3.0 |



---

## Çapraz

### FRM-19 · Kırılım noktasında OB/FVG var mı?

**SORU**      : FRM-19 · Kırılım anında fiyat canlı bir OB/FVG zone'u içindeyse sonuç değişiyor mu?
**AŞAMA**     : Çapraz
**ANA ÇİZGİ** : zone var / yok
**ÇIKTI**     : tamamlanma oranı · fark −1.0 puan (GA −3.5…+1.1) · fark yok
**TABAN**     : kırılımı olan formasyonlar (n=5996)
**YAN SÜTUN** : OB ve FVG ayrı ayrı (bağımsız kolonlar) altta
**KARAR**     : fark yok (GA sıfırı içeriyor)

| grup | n | tamamlanma | GA |
|---|---|---|---|
| zone var | 2406 | %74.4 | %72.6–%76.1 |
| zone yok | 3590 | %75.3 | %73.9–%76.7 |

| ayrıştırma (yan sütun) | n | tamamlanma | fark (GA) |
|---|---|---|---|
| OB var | 2298 | %73.9 | fark −1.7 puan (GA −4.4…+0.3) · fark yok |
| FVG var | 151 | %82.8 | fark +8.0 puan (GA +2.1…+14.5) · fark var |


### FRM-20 · Formasyon yönü ile MS yönü uyumu

**SORU**      : FRM-20 · Kırılım yönü en yakın rol seviyesine doğruysa sonuç değişiyor mu?
**AŞAMA**     : Çapraz
**ANA ÇİZGİ** : uyumlu / uyumsuz
**ÇIKTI**     : tamamlanma oranı · fark +10.1 puan (GA +7.6…+12.2) · fark var
**TABAN**     : kırılımı olan ve MS rolü açık formasyonlar (n=5981)
**YAN SÜTUN** : —
**KARAR**     : fark var (GA sıfırı içermiyor)

| grup | n | tamamlanma | GA |
|---|---|---|---|
| uyumlu | 3405 | %79.4 | %78.0–%80.7 |
| uyumsuz | 2576 | %69.3 | %67.5–%71.0 |

