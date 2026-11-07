# Stabil direnç replay — toplu bulgular

Plan önceden sabittir; yüzdeler geçerli tam ufuklu olayların payıdır. Aynı bar belirsiz ve hiçbiri paydada kalır. Tablolar betimseldir, modeller aynı olayları seçmez.

## 20 aday/referans — 2026, TEST sonrası 8 adet 4s bar

| Aday | Hazır bar % | Tüm TEST | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MIRROR_P4 | 100.0 | 1409 | 1241 | 161 | 42.1 | 51.6 | 3.1 | 3.2 | +0.05 |
| P2 | 100.0 | 2167 | 1899 | 162 | 40.7 | 52.5 | 2.8 | 3.9 | +0.00 |
| P3 | 100.0 | 1703 | 1484 | 162 | 42.4 | 51.3 | 2.9 | 3.4 | +0.00 |
| P6 | 100.0 | 1076 | 944 | 159 | 43.1 | 50.3 | 2.9 | 3.7 | +0.03 |
| P8 | 100.0 | 899 | 802 | 156 | 42.3 | 51.2 | 2.9 | 3.6 | +0.05 |
| BODY_P4 | 100.0 | 1562 | 1363 | 161 | 42.5 | 50.6 | 2.7 | 4.3 | +0.08 |
| P4_MAX3 | 100.0 | 831 | 740 | 152 | 43.2 | 51.2 | 2.4 | 3.1 | +0.10 |
| P4_MEDIAN3 | 100.0 | 1144 | 987 | 160 | 40.5 | 53.0 | 2.5 | 4.0 | +0.00 |
| P4_DOUBLE | 18.0 | 257 | 219 | 91 | 44.3 | 52.5 | 1.4 | 1.8 | +0.14 |
| P4_ACTIVE | 83.0 | 1387 | 1222 | 161 | 41.9 | 51.9 | 3.0 | 3.2 | +0.06 |
| P4_CEILING | 100.0 | 1146 | 1001 | 158 | 43.3 | 50.5 | 2.5 | 3.7 | -0.02 |
| ROLL10 | 100.0 | 3379 | 2936 | 162 | 41.4 | 52.1 | 3.2 | 3.3 | +0.05 |
| ROLL20 | 100.0 | 2343 | 2015 | 161 | 41.1 | 52.4 | 3.5 | 3.1 | +0.09 |
| ROLL55 | 100.0 | 1364 | 1242 | 149 | 42.3 | 51.2 | 3.6 | 2.9 | +0.12 |
| ROLL20_CLOSE | 100.0 | 2612 | 2195 | 162 | 42.7 | 51.0 | 2.1 | 4.2 | +0.10 |
| EMA20 | 100.0 | 2889 | 2643 | 162 | 43.1 | 48.8 | 1.6 | 6.6 | -0.10 |
| SHIFT_UP | 100.0 | 1047 | 916 | 159 | 42.4 | 51.5 | 2.3 | 3.8 | +0.00 |
| SHIFT_DOWN | 100.0 | 1746 | 1553 | 162 | 42.0 | 50.6 | 2.3 | 5.1 | +0.00 |
| P4_ZONE0 | 100.0 | 1470 | 1291 | 160 | 44.2 | 49.3 | 2.9 | 3.6 | +0.03 |
| P4_ZONE50 | 100.0 | 1209 | 1073 | 162 | 44.0 | 49.8 | 3.0 | 3.3 | +0.04 |

Hazır bar %, 20 barı sağlam ve günlük kaynak geçmişi geçerli olan 2026 4s barlarında seviyenin bilinmesi oranıdır; olay yüzdesi değildir. EMA20 dinamik bir kıyas, SHIFT seviyeleri sentetiktir.

Ana TEST için eşit-hisse ağırlıklı aşağı-önce oranı **%42.5**; en yoğun beş hisse geçerli olayların **%6.8** bölümünü taşır. Tek bir hisseyi sırayla çıkarınca oran **%41.8…%42.4** olur. Ortak gün/olay korelasyonu bu kontrollerde giderilmez.

### Önceki ve sonraki takvim dilimi — 8 bar

| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MIRROR_P4 / PRE_2026 | 1295 | 1093 | 165 | 42.4 | 50.9 | 2.5 | 4.3 | +0.05 |
| MIRROR_P4 / Y2026 | 1409 | 1241 | 161 | 42.1 | 51.6 | 3.1 | 3.2 | +0.05 |
| ROLL20 / PRE_2026 | 2246 | 1889 | 162 | 44.3 | 49.1 | 2.4 | 4.2 | +0.08 |
| ROLL20 / Y2026 | 2343 | 2015 | 161 | 41.1 | 52.4 | 3.5 | 3.1 | +0.09 |
| SHIFT_UP / PRE_2026 | 955 | 810 | 161 | 42.7 | 50.1 | 2.7 | 4.4 | -0.03 |
| SHIFT_UP / Y2026 | 1047 | 916 | 159 | 42.4 | 51.5 | 2.3 | 3.8 | +0.00 |
| SHIFT_DOWN / PRE_2026 | 1614 | 1335 | 166 | 38.8 | 54.7 | 2.2 | 4.3 | +0.13 |
| SHIFT_DOWN / Y2026 | 1746 | 1553 | 162 | 42.0 | 50.6 | 2.3 | 5.1 | +0.00 |

Bu dilimler bağımsız/kör dış örnek değildir; PRE_2026 için ufku 2026 sınırını aşan olaylar ilgili ufuktan çıkarıldı.

### Takvim çeyreği

| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026Q1 | 583 | 556 | 149 | 39.2 | 54.9 | 3.2 | 2.7 | +0.21 |
| 2026Q2 | 449 | 327 | 133 | 43.4 | 50.2 | 2.4 | 4.0 | -0.04 |
| 2026Q3 | 357 | 340 | 121 | 45.0 | 48.2 | 3.2 | 3.5 | -0.11 |
| 2026Q4 | 20 | 18 | 14 | 55.6 | 38.9 | 5.6 | 0.0 | -0.55 |

### Seans kapanış saati

| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 13:00 | 8 | 8 | 8 | 37.5 | 62.5 | 0.0 | 0.0 | +0.94 |
| 13:30 | 1000 | 881 | 160 | 43.7 | 49.8 | 2.7 | 3.7 | +0.05 |
| 17:30 | 301 | 263 | 126 | 41.4 | 52.1 | 4.6 | 1.9 | +0.03 |
| 18:00 | 100 | 89 | 66 | 29.2 | 66.3 | 2.2 | 2.2 | +0.11 |

### O ana kadar bilinen seviye yaşı

| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0–4 gün | 639 | 569 | 153 | 39.7 | 55.7 | 2.5 | 2.1 | +0.11 |
| 21+ gün | 35 | 28 | 21 | 25.0 | 67.9 | 3.6 | 3.6 | +1.00 |
| 5–20 gün | 735 | 644 | 155 | 45.0 | 47.2 | 3.6 | 4.2 | -0.01 |

### Terslenmiş native aday rejim proxy'si

| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FLAT_AFTER_RESISTANCE_DROP_PROXY | 207 | 168 | 90 | 36.9 | 50.0 | 7.1 | 6.0 | -0.11 |
| FLAT_AFTER_RESISTANCE_RISE_PROXY | 591 | 532 | 145 | 42.5 | 51.7 | 2.8 | 3.0 | +0.09 |
| FLAT_BASE_PROXY | 20 | 12 | 9 | 50.0 | 41.7 | 0.0 | 8.3 | -0.02 |
| LONG_FLAT_PROXY | 17 | 15 | 13 | 26.7 | 73.3 | 0.0 | 0.0 | +1.07 |
| RESISTANCE_BREACHED_FIXED_PROXY | 11 | 9 | 9 | 33.3 | 55.6 | 0.0 | 11.1 | +0.20 |
| RESISTANCE_STEP_DOWN_PROXY | 481 | 432 | 139 | 44.0 | 50.9 | 2.3 | 2.8 | +0.00 |
| RESISTANCE_STEP_UP_PROXY | 82 | 73 | 59 | 43.8 | 54.8 | 1.4 | 0.0 | +0.19 |

### Temas sırası — geçmişi bilinmeyen ayrı

| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2+ gözlenen | 506 | 466 | 135 | 47.2 | 47.0 | 1.9 | 3.9 | +0.08 |
| UNKNOWN | 82 | 20 | 12 | 30.0 | 65.0 | 5.0 | 0.0 | +1.21 |
| ilk gözlenen | 821 | 755 | 161 | 39.3 | 54.0 | 3.7 | 2.9 | +0.03 |

### Önceki 4 bar hareketi

| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0..1 ATR | 466 | 408 | 136 | 43.1 | 51.0 | 3.2 | 2.7 | +0.12 |
| <−1 ATR | 130 | 111 | 77 | 39.6 | 52.3 | 1.8 | 6.3 | +0.15 |
| −1..0 ATR | 273 | 233 | 118 | 48.9 | 43.3 | 2.6 | 5.2 | -0.30 |
| ≥1 ATR | 540 | 489 | 151 | 38.7 | 55.8 | 3.5 | 2.0 | +0.12 |

### Önceki 20 bara göre hacim

| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0,8..1,2 | 273 | 246 | 129 | 38.6 | 56.5 | 1.6 | 3.3 | +0.24 |
| <0,8 | 215 | 177 | 89 | 41.8 | 48.6 | 2.8 | 6.8 | +0.08 |
| ≥1,2 | 921 | 818 | 160 | 43.3 | 50.7 | 3.5 | 2.4 | +0.00 |

### TEST anı: zone yaklaşımı / gerçek temas / kapanış

| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GAP_ABOVE_NO_TOUCH | 32 | 28 | 26 | 28.6 | 50.0 | 14.3 | 7.1 | +0.11 |
| NEAR_ONLY | 350 | 324 | 122 | 38.9 | 56.8 | 1.5 | 2.8 | +0.00 |
| TOUCH_CLOSE_ABOVE | 444 | 389 | 149 | 42.7 | 50.9 | 4.9 | 1.5 | +0.11 |
| WICK_TOUCH_CLOSE_AT_OR_BELOW | 583 | 500 | 149 | 44.6 | 48.8 | 2.0 | 4.6 | +0.03 |

### Örtüşme duyarlılığı

| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Tüm TEST | 1409 | 1241 | 161 | 42.1 | 51.6 | 3.1 | 3.2 | +0.05 |
| En az 8 bar aralıklı TEST | 1068 | 947 | 161 | 39.6 | 53.7 | 3.2 | 3.5 | +0.06 |

## Native günlük lifecycle olayları — 2026, olay sonrası 8 günlük bar

| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RESISTANCE_ABANDONED_HIGHER | 491 | 468 | 156 | 48.7 | 48.9 | 0.4 | 1.9 | +0.12 |
| RESISTANCE_BREACHED | 1062 | 1008 | 164 | 40.8 | 53.7 | 3.3 | 2.3 | -0.06 |
| RESISTANCE_CEILING_BROKEN | 922 | 880 | 163 | 40.2 | 54.7 | 3.2 | 1.9 | -0.13 |
| RESISTANCE_CONFIRMED | 27 | 19 | 16 | 57.9 | 42.1 | 0.0 | 0.0 | -0.34 |
| RESISTANCE_HELD | 651 | 609 | 161 | 45.2 | 48.3 | 0.8 | 5.7 | -0.23 |
| RESISTANCE_REBASED_HIGHER | 1099 | 1041 | 164 | 48.3 | 46.8 | 0.5 | 4.4 | -0.18 |
| RESISTANCE_REBASED_LOWER | 1274 | 1083 | 163 | 46.0 | 42.5 | 0.8 | 10.7 | -0.12 |
| RESISTANCE_RETURN_BELOW | 589 | 555 | 161 | 46.1 | 49.7 | 0.2 | 4.0 | -0.18 |
| RESISTANCE_TESTED | 1214 | 1140 | 164 | 45.7 | 50.5 | 0.5 | 3.2 | -0.15 |

Bunlar 4s olaylarla birleştirilmez. Native olay adı ters yön anlamındadır; aynı günlük bar içindeki birden çok olayın işlem sırası bilinmez.

## Yukarı kırılmadan sonra ilk 4s retest — 2026 / 8 bar

Kırılma tüm/geçerli: **1529/1340**. İlk-retest sınıfları, tüm geçerli kırılmaları payda alır:

| Sınıf | n | % |
|---|---:|---:|
| GAP_OR_OPEN_AT_BELOW_FAIL | 60 | 4.5 |
| GAP_OR_OPEN_AT_BELOW_RECLAIM | 50 | 3.7 |
| NO_RETEST | 340 | 25.4 |
| TOUCH_CLOSE_ABOVE | 463 | 34.6 |
| TOUCH_CLOSE_AT_OR_BELOW | 427 | 31.9 |

İzleyen 8 barda en az bir kapanışla çizgiye/altına dönen: **781/1340**. Kırılma mumunun açılışı çizgi üzerinde olan: **216**; bunlar seans içi kesintisiz geçiş değildir.

### Kırılmada gap / çizgide veya altında açılış

| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AÇILIŞ ÇİZGİDE/ALTINDA | 1277 | 1124 | 161 | 42.0 | 52.3 | 3.9 | 1.8 | +0.00 |
| GAP_AÇILIŞ ÜSTÜ | 252 | 216 | 120 | 41.2 | 49.5 | 4.6 | 4.6 | +0.00 |

### Üstten aşağı dönüş — önceki yukarı taşma derinliği

| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0,5..1 ATR | 233 | 208 | 114 | 48.1 | 45.7 | 1.9 | 4.3 | -0.28 |
| 0..0,5 ATR | 157 | 140 | 87 | 52.9 | 44.3 | 0.7 | 2.1 | -0.02 |
| >1 ATR | 643 | 584 | 161 | 49.8 | 44.0 | 2.4 | 3.8 | -0.22 |
| UNKNOWN | 45 | 0 | 0 | — | — | — | — | — |

UNKNOWN: aynı seviye kimliği altında yukarı kırılma ve önceki tüm yol arşivde gözlenmedi veya arada eksik/hatalı bar var. Derinlik kırılma anında sabitlenmiş 4s ATR cinsindendir.

## Fiyat dirençten aşağı uzaklaştığında ilk yol

Başlangıç: fiyat, önceden bilinen ve değişmeyen referansa göre aşağı yönde 1,5 önceki 4s ATR mesafesine ilk geçer. Takip: direnç eski seviyeden >0,01 aşağı güncellenir. Dönüş: fiyat kapanışı eski dirençte/üstte. Aynı 4s checkpoint'te ikisi de varsa belirsiz; ek süre koşulu yok.

| Ufuk | Olay | Geçerli n | Hisse | Çizgi aşağı takip önce | Fiyat dönüş önce | Aynı-bar belirsiz | Hiçbiri | Seviye yok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 × 4s | 1435 | 1264 | 162 | 4 | 171 | 1 | 1088 | 0 |
| 8 × 4s | 1435 | 1242 | 162 | 16 | 304 | 2 | 920 | 0 |
| 16 × 4s | 1435 | 1206 | 162 | 144 | 435 | 7 | 620 | 0 |

Bu mekanik uzaklaşma/izleme yarışı görsel dikey-yatay eşlemesi değildir. Native pivotun dört günlük teyit geometrisi sebebiyle özellikle kısa ufukta yeni çizgi basamağı zaten gecikebilir; bu tablo tek başına fiyatın çizgiyi öngördüğünü göstermez. 1,5 ATR eşiği tek-sembollü teknik pilot sonrasında, tüm evren replay'i öncesinde sabitlendi.

## Çizgi / fiyat katkısına göre üst-alt değişimleri

| Karşı olgusal neden | n |
|---|---:|
| BOTH_REQUIRED | 24 |
| EITHER_SUFFICIENT | 47 |
| LINE_ONLY | 406 |
| PRICE_ONLY | 2566 |

PRICE_ONLY: fiyat tek başına yeterli; LINE_ONLY: çizgi tek başına yeterli; BOTH_REQUIRED: birlikte gerekli; EITHER_SUFFICIENT: ikisi de tek başına yeterli. Bu bir fiyat-tepkisi veya nedensel piyasa etkisi ölçümü değildir.

## Yakındaki sahte-seviye eşleşmeleri — 2026

- **SHIFT_UP:** sonuç görülmeden eşleşen 146 çift; ikisi de tam/geçerli 129 çift, 86 hisse; 17 çift dışlandı.
  Ana/sahte −1 ATR önce: **53/129 (%41.1) / 57/129 (%44.2)**; fark **-3.1 puan**, hisse-kümeli %95 bootstrap **-16.2…+10.0**. Aynı-bar belirsizler ana/kontrol 2/3; bunların uç atamalarıyla fark aralığı **-5.4…-1.6** puan. Eşlerde medyan mutlak mesafe farkı 0.12 ATR, önceki hareket farkı 0.43 ATR.
- **SHIFT_DOWN:** sonuç görülmeden eşleşen 228 çift; ikisi de tam/geçerli 194 çift, 108 hisse; 34 çift dışlandı.
  Ana/sahte −1 ATR önce: **97/194 (%50.0) / 77/194 (%39.7)**; fark **+10.3 puan**, hisse-kümeli %95 bootstrap **+0.0…+19.3**. Aynı-bar belirsizler ana/kontrol 4/4; bunların uç atamalarıyla fark aralığı **+8.2…+12.4** puan. Eşlerde medyan mutlak mesafe farkı 0.14 ATR, önceki hareket farkı 0.34 ATR.

Eşler aynı hisse/çeyrek/seans/mesafe ve önceki 4-bar hareket kovasında; aralarında ≥8 bar, tekrarsız ve en yakın zamanlıdır. Önce yalnız bilinen koşullarla eşleşir, sonra sansür uygulanır. Ortak gün şokları ve çoklu deneme düzeltilmediğinden aralık nedensel güven aralığı değildir.
