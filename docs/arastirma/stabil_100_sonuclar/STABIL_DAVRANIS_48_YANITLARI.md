# Stabil — 48 Davranış Sorusu (`STB-BHV-A01..H06`) Nedensel Replay Raporu

- **Sembol sayısı:** 100 BIST hissesi (`AEFES` .. `KONTR`)
- **Toplam çalışma süresi:** 188.84 sn (tek geçişli O(N) native tarihçe)
- **Kaynak matematik:** `domain_engines/05_stabil.txt` (`StabilTrendEngine` + `StabilSupportLifecycleEngine`, değiştirilmemiş eşikler)
- **Checkpoint birimi:** Kapanmış `4H` mum kapanışları (`daily_close <= h4_close`, tamamlanmış takvim haftası `weekly_close <= h4_close`)
- **Ufuklar:** `1, 4, 8, 10, 12, 16` × `4H` mum; sabit başlangıç günlük ATR birimi
- **Dikey/Yatay eşleme durumu:** ADAY EŞLEME (gerçek grafik örneği üzerinde kullanıcı teyidi bekleniyor; B01-B06 ve F01/F03/F05/F06 kesinleşmiş ölçüm sayılmaz)
- **Karar kapısı notu:** Eski `S01–S32` otomatik karar kapısı uygulanmamıştır; hiçbir sonuç otomatik canlı alarm kuralı üretmez.

## Genel Dağılım Özeti

- **ayrı doğrulama gerekli:** 10 soru
- **belirgin ayrım yok:** 17 soru
- **betimsel ayrım:** 19 soru
- **örnek yetersiz:** 2 soru

## STB-BHV-A01 — Fiyat uzaklaşınca önce destek mi yukarı güncelleniyor, fiyat mı eski desteğe dönüyor?

- **TANIM:** Destek üstünde >=1.0 günlük ATR uzaklaşmış 4H kapanışlarında 24x4H içinde ilk yarış sonucu ve ileri getiriler.
- **VERİ:** Toplam checkpoint/olay `n=65955`, 8×4H tam ufuk `n=65774`, sağdan sansürlü `n=181`, ATR geçerli `n=65774`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `1.0-2.0_ATR_uzak` (8×4H n=21266, med=-0.046 ATR, ort=0.043 ATR, MFE_med=0.662, MAE_med=0.581, top1_sembol=1.7%) vs `2.0-3.5_ATR_uzak` (8×4H n=23223, med=-0.056 ATR, ort=0.042 ATR, MFE_med=0.724, MAE_med=0.653, top1_sembol=1.8%) vs `3.5+_ATR_uzak` (8×4H n=21285, med=0.020 ATR, ort=0.085 ATR, MFE_med=0.875, MAE_med=0.724, top1_sembol=2.6%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `1.0-2.0_ATR_uzak` | 1 | 21327 / 21327 / 7 | 100 (1.7%) | +0.004 / -0.010 | +0.004 | 0.150 / 0.149 | 4.2% / 1.8% / 0.0% | 0.000 / -0.013 |
| `1.0-2.0_ATR_uzak` | 4 | 21308 / 21308 / 26 | 100 (1.7%) | +0.025 / -0.034 | +0.024 | 0.431 / 0.389 | 19.1% / 11.2% / 0.1% | 0.000 / -0.068 |
| `1.0-2.0_ATR_uzak` | 8 | 21266 / 21266 / 68 | 100 (1.7%) | +0.043 / -0.046 | +0.042 | 0.662 / 0.581 | 32.9% / 24.2% / 0.1% | 0.019 / -0.118 |
| `1.0-2.0_ATR_uzak` | 10 | 21235 / 21235 / 99 | 100 (1.7%) | +0.048 / -0.045 | +0.049 | 0.754 / 0.656 | 37.6% / 29.1% / 0.1% | 0.039 / -0.136 |
| `1.0-2.0_ATR_uzak` | 12 | 21191 / 21191 / 143 | 100 (1.7%) | +0.052 / -0.048 | +0.052 | 0.839 / 0.726 | 41.1% / 32.8% / 0.1% | 0.031 / -0.142 |
| `1.0-2.0_ATR_uzak` | 16 | 21073 / 21073 / 261 | 100 (1.7%) | +0.072 / -0.042 | +0.073 | 0.998 / 0.834 | 45.9% / 37.6% / 0.1% | 0.060 / -0.163 |
| `2.0-3.5_ATR_uzak` | 1 | 23280 / 23280 / 4 | 100 (1.8%) | +0.006 / -0.010 | +0.004 | 0.174 / 0.164 | 5.2% / 2.6% / 0.0% | -0.015 / 0.000 |
| `2.0-3.5_ATR_uzak` | 4 | 23262 / 23262 / 22 | 100 (1.8%) | +0.024 / -0.035 | +0.019 | 0.488 / 0.439 | 22.4% / 15.5% / 0.2% | -0.015 / -0.059 |
| `2.0-3.5_ATR_uzak` | 8 | 23223 / 23223 / 61 | 100 (1.8%) | +0.042 / -0.056 | +0.036 | 0.724 / 0.653 | 35.8% / 29.9% / 0.2% | -0.012 / -0.095 |
| `2.0-3.5_ATR_uzak` | 10 | 23199 / 23199 / 85 | 100 (1.8%) | +0.049 / -0.056 | +0.042 | 0.824 / 0.745 | 39.8% / 34.6% / 0.2% | 0.000 / -0.106 |
| `2.0-3.5_ATR_uzak` | 12 | 23175 / 23175 / 109 | 100 (1.8%) | +0.052 / -0.062 | +0.043 | 0.908 / 0.826 | 42.7% / 38.1% / 0.2% | 0.000 / -0.128 |
| `2.0-3.5_ATR_uzak` | 16 | 23125 / 23125 / 159 | 100 (1.8%) | +0.052 / -0.077 | +0.041 | 1.070 / 0.971 | 46.5% / 42.1% / 0.2% | 0.017 / -0.181 |
| `3.5+_ATR_uzak` | 1 | 21331 / 21331 / 6 | 100 (2.6%) | +0.015 / +0.000 | +0.005 | 0.200 / 0.181 | 7.4% / 4.5% / 0.3% | 0.000 / 0.000 |
| `3.5+_ATR_uzak` | 4 | 21312 / 21312 / 25 | 100 (2.6%) | +0.047 / +0.000 | +0.003 | 0.602 / 0.484 | 27.9% / 20.1% / 0.9% | 0.000 / 0.000 |
| `3.5+_ATR_uzak` | 8 | 21285 / 21285 / 52 | 100 (2.6%) | +0.085 / +0.020 | -0.004 | 0.875 / 0.724 | 41.1% / 32.7% / 0.9% | 0.029 / 0.000 |
| `3.5+_ATR_uzak` | 10 | 21274 / 21274 / 63 | 100 (2.6%) | +0.104 / +0.024 | -0.008 | 0.992 / 0.825 | 44.8% / 36.5% / 0.9% | 0.035 / 0.000 |
| `3.5+_ATR_uzak` | 12 | 21262 / 21262 / 75 | 100 (2.6%) | +0.121 / +0.025 | -0.015 | 1.097 / 0.920 | 47.4% / 38.9% / 0.9% | 0.043 / 0.000 |
| `3.5+_ATR_uzak` | 16 | 21241 / 21241 / 96 | 100 (2.6%) | +0.148 / +0.052 | -0.026 | 1.282 / 1.065 | 50.2% / 41.8% / 1.0% | 0.078 / 0.024 |

- **KARŞI ÖRNEK:** HALKB (2026-08-25 18:00, kova=2.0-3.5_ATR_uzak): 8x4H korunan=+8.87 ATR (MFE=8.87 / MAE=0.00 ATR) · KLGYO (2026-01-07 18:00, kova=1.0-2.0_ATR_uzak): 8x4H korunan=+9.70 ATR (MFE=10.42 / MAE=0.26 ATR) · BEGYO (2025-05-09 13:30, kova=3.5+_ATR_uzak): 8x4H korunan=-13.23 ATR (MFE=0.05 / MAE=13.23 ATR)
- **SINIR:** Aynı checkpoint'te çakışan olaylar ve 24x4H sağdan sansür ayrı tutulur; örtüşen checkpoint'ler bağımsız işlem değildir.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.076 ATR, MAE farkı 0.143 ATR düzeyinde ayrıştı.

## STB-BHV-A02 — Aynı uzaklığa hızlı veya yavaş çıkmak bu iki yolun oranını değiştiriyor mu?

- **TANIM:** 1.5-3.0 ATR benzer destek uzaklığında son 12x4H hareketi >=1.2 ATR (hızlı) ile <1.2 ATR (yavaş) çıkış karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=27136`, 8×4H tam ufuk `n=27061`, sağdan sansürlü `n=75`, ATR geçerli `n=27061`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `hizli_uzaklasma` (8×4H n=5044, med=-0.067 ATR, ort=0.046 ATR, MFE_med=0.805, MAE_med=0.699, top1_sembol=1.7%) vs `yavas_uzaklasma` (8×4H n=22017, med=-0.070 ATR, ort=0.033 ATR, MFE_med=0.672, MAE_med=0.615, top1_sembol=1.8%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `hizli_uzaklasma` | 1 | 5049 / 5049 / 0 | 100 (1.7%) | +0.014 / +0.000 | +0.007 | 0.186 / 0.182 | 7.1% / 2.9% / 0.0% | -0.025 / 0.000 |
| `hizli_uzaklasma` | 4 | 5047 / 5047 / 2 | 100 (1.7%) | +0.049 / -0.038 | +0.043 | 0.537 / 0.479 | 26.4% / 16.8% / 0.2% | -0.041 / -0.032 |
| `hizli_uzaklasma` | 8 | 5044 / 5044 / 5 | 100 (1.7%) | +0.046 / -0.067 | +0.033 | 0.805 / 0.699 | 39.7% / 31.3% / 0.2% | -0.069 / -0.064 |
| `hizli_uzaklasma` | 10 | 5040 / 5040 / 9 | 100 (1.7%) | +0.053 / -0.072 | +0.043 | 0.912 / 0.791 | 43.0% / 36.1% / 0.2% | -0.057 / -0.091 |
| `hizli_uzaklasma` | 12 | 5034 / 5034 / 15 | 100 (1.7%) | +0.059 / -0.105 | +0.052 | 1.003 / 0.875 | 45.6% / 39.1% / 0.2% | -0.086 / -0.115 |
| `hizli_uzaklasma` | 16 | 5023 / 5023 / 26 | 100 (1.7%) | -0.003 / -0.149 | +0.001 | 1.167 / 1.051 | 48.8% / 42.9% / 0.2% | -0.123 / -0.196 |
| `yavas_uzaklasma` | 1 | 22081 / 22081 / 6 | 100 (1.8%) | +0.004 / -0.013 | +0.004 | 0.159 / 0.153 | 4.4% / 2.1% / 0.0% | -0.013 / -0.013 |
| `yavas_uzaklasma` | 4 | 22056 / 22056 / 31 | 100 (1.8%) | +0.013 / -0.045 | +0.009 | 0.449 / 0.411 | 19.8% / 13.2% / 0.1% | 0.000 / -0.082 |
| `yavas_uzaklasma` | 8 | 22017 / 22017 / 70 | 100 (1.8%) | +0.033 / -0.070 | +0.025 | 0.672 / 0.615 | 33.3% / 27.5% / 0.1% | 0.000 / -0.129 |
| `yavas_uzaklasma` | 10 | 21991 / 21991 / 96 | 100 (1.8%) | +0.045 / -0.065 | +0.034 | 0.763 / 0.698 | 37.6% / 32.3% / 0.1% | 0.000 / -0.143 |
| `yavas_uzaklasma` | 12 | 21964 / 21964 / 123 | 100 (1.8%) | +0.052 / -0.060 | +0.037 | 0.847 / 0.771 | 40.9% / 35.9% / 0.1% | 0.024 / -0.146 |
| `yavas_uzaklasma` | 16 | 21905 / 21905 / 182 | 100 (1.8%) | +0.084 / -0.040 | +0.064 | 1.009 / 0.897 | 45.2% / 40.5% / 0.1% | 0.071 / -0.155 |

- **KARŞI ÖRNEK:** BEGYO (2026-10-12 18:00, kova=hizli_uzaklasma): 8x4H korunan=+7.50 ATR (MFE=7.50 / MAE=0.00 ATR) · HALKB (2026-08-25 17:30, kova=yavas_uzaklasma): 8x4H korunan=+9.00 ATR (MFE=9.00 / MAE=0.02 ATR)
- **SINIR:** Mesafe bandı sabitlenmiştir; yine de rejim ve sembol yoğunlaşması kontrol edilmelidir.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.003 ATR, MAE farkı 0.085 ATR düzeyinde ayrıştı.

## STB-BHV-A03 — Destek takibe başladığında yükselişin ne kadarı geride, ne kadarı ileride?

- **TANIM:** Desteğin yukarı taşındığı (REBASED_HIGHER) ilk bilinen 4H kapanışında geride kalan ATR kazancı ile ileri ufuk getirisi.
- **VERİ:** Toplam checkpoint/olay `n=1185`, 8×4H tam ufuk `n=1177`, sağdan sansürlü `n=8`, ATR geçerli `n=1177`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `buyuk_geride_kalan_artis` (8×4H n=625, med=-0.060 ATR, ort=0.049 ATR, MFE_med=0.707, MAE_med=0.665, top1_sembol=2.1%) vs `ilimli_geride_kalan_artis` (8×4H n=552, med=0.000 ATR, ort=0.066 ATR, MFE_med=0.711, MAE_med=0.532, top1_sembol=2.0%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `buyuk_geride_kalan_artis` | 1 | 627 / 627 / 0 | 100 (2.1%) | -0.023 / -0.038 | -0.042 | 0.202 / 0.229 | 3.2% / 4.8% / 0.0% | -0.036 / -0.050 |
| `buyuk_geride_kalan_artis` | 4 | 627 / 627 / 0 | 100 (2.1%) | +0.044 / +0.000 | +0.029 | 0.490 / 0.463 | 21.2% / 17.5% / 0.0% | 0.046 / -0.073 |
| `buyuk_geride_kalan_artis` | 8 | 625 / 625 / 2 | 100 (2.1%) | +0.049 / -0.060 | +0.056 | 0.707 / 0.665 | 34.2% / 30.2% / 0.0% | 0.027 / -0.115 |
| `buyuk_geride_kalan_artis` | 10 | 625 / 625 / 2 | 100 (2.1%) | +0.090 / +0.014 | +0.098 | 0.855 / 0.770 | 39.8% / 36.6% / 0.0% | 0.133 / -0.149 |
| `buyuk_geride_kalan_artis` | 12 | 625 / 625 / 2 | 100 (2.1%) | +0.073 / -0.017 | +0.073 | 0.943 / 0.849 | 42.6% / 39.7% / 0.0% | 0.127 / -0.155 |
| `buyuk_geride_kalan_artis` | 16 | 625 / 625 / 2 | 100 (2.1%) | +0.109 / +0.021 | +0.096 | 1.077 / 1.011 | 45.4% / 44.2% / 0.0% | 0.140 / -0.166 |
| `ilimli_geride_kalan_artis` | 1 | 558 / 558 / 0 | 99 (2.0%) | -0.016 / -0.017 | -0.028 | 0.172 / 0.205 | 3.4% / 2.0% / 0.0% | 0.000 / -0.032 |
| `ilimli_geride_kalan_artis` | 4 | 557 / 557 / 1 | 99 (2.0%) | +0.064 / +0.025 | +0.056 | 0.468 / 0.409 | 22.3% / 13.3% / 0.0% | 0.079 / -0.028 |
| `ilimli_geride_kalan_artis` | 8 | 552 / 552 / 6 | 99 (2.0%) | +0.066 / +0.000 | +0.036 | 0.711 / 0.532 | 35.5% / 21.6% / 0.0% | 0.056 / -0.049 |
| `ilimli_geride_kalan_artis` | 10 | 552 / 552 / 6 | 99 (2.0%) | +0.065 / +0.030 | +0.057 | 0.852 / 0.651 | 41.5% / 27.2% / 0.0% | 0.083 / -0.086 |
| `ilimli_geride_kalan_artis` | 12 | 550 / 550 / 8 | 99 (2.0%) | +0.106 / +0.089 | +0.107 | 0.969 / 0.706 | 44.9% / 30.9% / 0.0% | 0.193 / -0.013 |
| `ilimli_geride_kalan_artis` | 16 | 550 / 550 / 8 | 99 (2.0%) | +0.061 / -0.096 | +0.061 | 1.103 / 0.857 | 49.5% / 35.8% / 0.0% | 0.290 / -0.256 |

- **KARŞI ÖRNEK:** BRSAN (2025-08-22 13:30, kova=buyuk_geride_kalan_artis): 8x4H korunan=+5.77 ATR (MFE=5.77 / MAE=0.05 ATR) · BTCIM (2025-08-06 13:30, kova=ilimli_geride_kalan_artis): 8x4H korunan=-3.26 ATR (MFE=0.16 / MAE=3.34 ATR)
- **SINIR:** Pivot teyidi 4 günlük sağ bar beklediği için giriş anı teyit kapanışıdır, pivot dibine geri taşınmaz.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.060 ATR, MAE farkı 0.133 ATR düzeyinde ayrıştı.

## STB-BHV-A04 — Destek takip etmeden bekleme uzadıkça fiyatın geri dönüş riski artıyor mu?

- **TANIM:** Yalnız o ana kadar bilinen destek yaşına (0-5g, 6-15g, 16g+) göre yukarıda bekleyen fiyatın MAE ve geri dönüş oranı.
- **VERİ:** Toplam checkpoint/olay `n=65955`, 8×4H tam ufuk `n=65774`, sağdan sansürlü `n=181`, ATR geçerli `n=65774`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `bekleme_0_5g` (8×4H n=28232, med=-0.084 ATR, ort=0.017 ATR, MFE_med=0.718, MAE_med=0.678, top1_sembol=1.4%) vs `bekleme_16g_ustu` (8×4H n=11044, med=0.055 ATR, ort=0.129 ATR, MFE_med=0.799, MAE_med=0.584, top1_sembol=3.1%) vs `bekleme_6_15g` (8×4H n=26498, med=0.000 ATR, ort=0.068 ATR, MFE_med=0.763, MAE_med=0.631, top1_sembol=1.5%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bekleme_0_5g` | 1 | 28262 / 28262 / 1 | 100 (1.4%) | +0.004 / -0.015 | +0.004 | 0.170 / 0.168 | 5.6% / 2.9% / 0.1% | -0.017 / -0.014 |
| `bekleme_0_5g` | 4 | 28259 / 28259 / 4 | 100 (1.4%) | +0.012 / -0.055 | +0.012 | 0.488 / 0.455 | 22.5% / 15.6% / 0.4% | -0.023 / -0.080 |
| `bekleme_0_5g` | 8 | 28232 / 28232 / 31 | 100 (1.4%) | +0.017 / -0.084 | +0.013 | 0.718 / 0.678 | 35.3% / 30.0% / 0.5% | -0.025 / -0.136 |
| `bekleme_0_5g` | 10 | 28186 / 28186 / 77 | 100 (1.4%) | +0.021 / -0.087 | +0.015 | 0.812 / 0.771 | 39.2% / 34.8% / 0.5% | 0.000 / -0.165 |
| `bekleme_0_5g` | 12 | 28126 / 28126 / 137 | 100 (1.4%) | +0.022 / -0.100 | +0.014 | 0.901 / 0.853 | 42.1% / 38.2% / 0.5% | 0.000 / -0.182 |
| `bekleme_0_5g` | 16 | 27973 / 27973 / 290 | 100 (1.4%) | +0.028 / -0.116 | +0.013 | 1.059 / 0.988 | 46.0% / 42.1% / 0.5% | 0.000 / -0.233 |
| `bekleme_16g_ustu` | 1 | 11050 / 11050 / 1 | 100 (3.1%) | +0.016 / +0.000 | +0.013 | 0.177 / 0.159 | 5.7% / 3.2% / 0.1% | 0.000 / 0.000 |
| `bekleme_16g_ustu` | 4 | 11047 / 11047 / 4 | 100 (3.1%) | +0.065 / +0.020 | +0.059 | 0.533 / 0.398 | 23.9% / 15.8% / 0.4% | 0.037 / 0.000 |
| `bekleme_16g_ustu` | 8 | 11044 / 11044 / 7 | 100 (3.1%) | +0.129 / +0.055 | +0.136 | 0.799 / 0.584 | 38.7% / 27.4% / 0.4% | 0.097 / 0.000 |
| `bekleme_16g_ustu` | 10 | 11044 / 11044 / 7 | 100 (3.1%) | +0.153 / +0.061 | +0.164 | 0.913 / 0.672 | 43.4% / 31.6% / 0.4% | 0.119 / 0.000 |
| `bekleme_16g_ustu` | 12 | 11044 / 11044 / 7 | 100 (3.1%) | +0.179 / +0.080 | +0.188 | 1.019 / 0.754 | 46.4% / 34.4% / 0.4% | 0.139 / 0.000 |
| `bekleme_16g_ustu` | 16 | 11044 / 11044 / 7 | 100 (3.1%) | +0.207 / +0.111 | +0.205 | 1.197 / 0.894 | 50.0% / 38.0% / 0.4% | 0.213 / 0.000 |
| `bekleme_6_15g` | 1 | 26626 / 26626 / 15 | 100 (1.5%) | +0.009 / +0.000 | +0.007 | 0.177 / 0.162 | 5.6% / 2.9% / 0.1% | 0.000 / 0.000 |
| `bekleme_6_15g` | 4 | 26576 / 26576 / 65 | 100 (1.5%) | +0.038 / -0.019 | +0.028 | 0.509 / 0.429 | 23.4% / 15.4% / 0.3% | 0.000 / -0.033 |
| `bekleme_6_15g` | 8 | 26498 / 26498 / 143 | 100 (1.5%) | +0.068 / +0.000 | +0.048 | 0.763 / 0.631 | 37.1% / 28.5% / 0.3% | 0.011 / -0.038 |
| `bekleme_6_15g` | 10 | 26478 / 26478 / 163 | 100 (1.5%) | +0.079 / +0.000 | +0.055 | 0.863 / 0.715 | 41.1% / 32.8% / 0.4% | 0.020 / -0.046 |
| `bekleme_6_15g` | 12 | 26458 / 26458 / 183 | 100 (1.5%) | +0.086 / +0.000 | +0.058 | 0.959 / 0.795 | 44.2% / 35.9% / 0.4% | 0.022 / -0.048 |
| `bekleme_6_15g` | 16 | 26422 / 26422 / 219 | 100 (1.5%) | +0.105 / +0.000 | +0.068 | 1.125 / 0.940 | 48.1% / 39.8% / 0.4% | 0.044 / -0.037 |

- **KARŞI ÖRNEK:** BEGYO (2025-05-09 13:30, kova=bekleme_6_15g): 8x4H korunan=-13.23 ATR (MFE=0.05 / MAE=13.23 ATR) · KLGYO (2026-01-07 18:00, kova=bekleme_0_5g): 8x4H korunan=+9.70 ATR (MFE=10.42 / MAE=0.26 ATR) · DMSAS (2025-12-26 18:00, kova=bekleme_16g_ustu): 8x4H korunan=-13.19 ATR (MFE=4.31 / MAE=13.19 ATR)
- **SINIR:** Arşiv başındaki ilk yaşı bilinmeyen epizotlar UNKNOWN olarak dışlanmıştır; gelecekte güncellenmeyecekler baştan seçilmez.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.139 ATR, MAE farkı 0.095 ATR düzeyinde ayrıştı.

## STB-BHV-A05 — Mesafe küçülürken fiyat mı geri geliyor, destek mi fiyatı yakalıyor?

- **TANIM:** Fiyat-destek mesafesinin daraldığı 4H kapanışlarında daralmanın kaynağını destek yükselişi vs fiyat geri çekilmesi olarak ayırır.
- **VERİ:** Toplam checkpoint/olay `n=34629`, 8×4H tam ufuk `n=34466`, sağdan sansürlü `n=163`, ATR geçerli `n=34466`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `destek_yukari_yakaliyor` (8×4H n=1040, med=-0.037 ATR, ort=0.032 ATR, MFE_med=0.674, MAE_med=0.601, top1_sembol=1.7%) vs `fiyat_asagi_cekiliyor` (8×4H n=33426, med=-0.071 ATR, ort=0.007 ATR, MFE_med=0.670, MAE_med=0.629, top1_sembol=1.2%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `destek_yukari_yakaliyor` | 1 | 1048 / 1048 / 0 | 100 (1.7%) | -0.029 / -0.035 | -0.038 | 0.179 / 0.219 | 3.1% / 3.5% / 0.0% | -0.038 / -0.032 |
| `destek_yukari_yakaliyor` | 4 | 1047 / 1047 / 1 | 100 (1.7%) | +0.026 / +0.000 | +0.026 | 0.460 / 0.446 | 19.8% / 15.8% / 0.0% | 0.032 / -0.051 |
| `destek_yukari_yakaliyor` | 8 | 1040 / 1040 / 8 | 100 (1.7%) | +0.032 / -0.037 | +0.029 | 0.674 / 0.601 | 32.8% / 26.4% / 0.0% | 0.021 / -0.066 |
| `destek_yukari_yakaliyor` | 10 | 1040 / 1040 / 8 | 100 (1.7%) | +0.029 / -0.005 | +0.022 | 0.818 / 0.731 | 38.6% / 32.6% / 0.0% | 0.031 / -0.147 |
| `destek_yukari_yakaliyor` | 12 | 1038 / 1038 / 10 | 100 (1.7%) | +0.026 / +0.000 | +0.017 | 0.911 / 0.780 | 41.7% / 36.3% / 0.0% | 0.069 / -0.107 |
| `destek_yukari_yakaliyor` | 16 | 1038 / 1038 / 10 | 100 (1.7%) | +0.019 / -0.100 | +0.002 | 1.041 / 0.950 | 45.7% / 41.3% / 0.0% | 0.148 / -0.264 |
| `fiyat_asagi_cekiliyor` | 1 | 33568 / 33568 / 13 | 100 (1.2%) | +0.004 / +0.000 | +0.004 | 0.154 / 0.144 | 4.4% / 2.4% / 0.1% | 0.000 / 0.000 |
| `fiyat_asagi_cekiliyor` | 4 | 33503 / 33503 / 78 | 100 (1.2%) | -0.003 / -0.046 | -0.005 | 0.444 / 0.415 | 19.5% / 14.7% / 0.1% | -0.027 / -0.064 |
| `fiyat_asagi_cekiliyor` | 8 | 33426 / 33426 / 155 | 100 (1.2%) | +0.007 / -0.071 | +0.002 | 0.670 / 0.629 | 32.8% / 28.6% / 0.2% | -0.022 / -0.115 |
| `fiyat_asagi_cekiliyor` | 10 | 33358 / 33358 / 223 | 100 (1.2%) | +0.012 / -0.081 | +0.006 | 0.755 / 0.715 | 36.9% / 33.5% / 0.2% | 0.000 / -0.144 |
| `fiyat_asagi_cekiliyor` | 12 | 33293 / 33293 / 288 | 100 (1.2%) | +0.013 / -0.085 | +0.006 | 0.840 / 0.800 | 40.1% / 37.2% / 0.2% | -0.009 / -0.158 |
| `fiyat_asagi_cekiliyor` | 16 | 33142 / 33142 / 439 | 100 (1.2%) | +0.032 / -0.080 | +0.022 | 0.992 / 0.935 | 44.2% / 41.5% / 0.2% | 0.000 / -0.173 |

- **KARŞI ÖRNEK:** KLGYO (2026-01-07 17:30, kova=fiyat_asagi_cekiliyor): 8x4H korunan=+9.60 ATR (MFE=10.06 / MAE=0.21 ATR) · BRSAN (2025-08-22 13:30, kova=destek_yukari_yakaliyor): 8x4H korunan=+5.77 ATR (MFE=5.77 / MAE=0.05 ATR)
- **SINIR:** Aynı CONTRACTING etiketi altında iki mekanizma farklı frekansta görülür; örnek sayıları dengesiz olabilir.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.034 ATR, MAE farkı 0.029 ATR düzeyinde ayrıştı.

## STB-BHV-A06 — Destek fiyatı yakalayınca devam mı geliyor, hareket tükenmiş mi oluyor?

- **TANIM:** Yukarı destek güncellemesinde fiyatın yeni desteğe yakın (<=1.2 ATR) yakalandığı durumlar ile hala uzakta olduğu durumların MFE ve kapanış korunması.
- **VERİ:** Toplam checkpoint/olay `n=1185`, 8×4H tam ufuk `n=1177`, sağdan sansürlü `n=8`, ATR geçerli `n=1177`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `destek_fiyati_yakaladi` (8×4H n=427, med=-0.037 ATR, ort=0.052 ATR, MFE_med=0.638, MAE_med=0.534, top1_sembol=2.5%) vs `destek_uzakta_kaldi` (8×4H n=750, med=0.000 ATR, ort=0.059 ATR, MFE_med=0.770, MAE_med=0.614, top1_sembol=1.9%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `destek_fiyati_yakaladi` | 1 | 434 / 434 / 0 | 99 (2.5%) | -0.034 / -0.034 | -0.048 | 0.152 / 0.194 | 3.2% / 3.5% / 0.0% | -0.047 / -0.022 |
| `destek_fiyati_yakaladi` | 4 | 433 / 433 / 1 | 99 (2.5%) | +0.022 / +0.000 | +0.009 | 0.425 / 0.376 | 17.8% / 13.4% / 0.0% | -0.041 / 0.000 |
| `destek_fiyati_yakaladi` | 8 | 427 / 427 / 7 | 99 (2.5%) | +0.052 / -0.037 | +0.036 | 0.638 / 0.534 | 29.3% / 21.8% / 0.0% | -0.086 / 0.087 |
| `destek_fiyati_yakaladi` | 10 | 427 / 427 / 7 | 99 (2.5%) | +0.037 / -0.021 | +0.011 | 0.759 / 0.673 | 36.5% / 27.6% / 0.0% | -0.020 / -0.031 |
| `destek_fiyati_yakaladi` | 12 | 425 / 425 / 9 | 99 (2.5%) | +0.091 / +0.056 | +0.040 | 0.844 / 0.702 | 40.9% / 31.8% / 0.0% | 0.056 / 0.056 |
| `destek_fiyati_yakaladi` | 16 | 425 / 425 / 9 | 99 (2.5%) | +0.073 / +0.000 | +0.002 | 1.017 / 0.824 | 44.7% / 37.6% / 0.0% | 0.150 / -0.166 |
| `destek_uzakta_kaldi` | 1 | 751 / 751 / 0 | 99 (1.9%) | -0.011 / -0.017 | -0.022 | 0.211 / 0.234 | 3.3% / 3.5% / 0.0% | 0.000 / -0.033 |
| `destek_uzakta_kaldi` | 4 | 751 / 751 / 0 | 99 (1.9%) | +0.071 / +0.026 | +0.061 | 0.521 / 0.472 | 24.0% / 16.8% / 0.0% | 0.090 / -0.097 |
| `destek_uzakta_kaldi` | 8 | 750 / 750 / 1 | 99 (1.9%) | +0.059 / +0.000 | +0.060 | 0.770 / 0.614 | 38.0% / 28.7% / 0.0% | 0.159 / -0.181 |
| `destek_uzakta_kaldi` | 10 | 750 / 750 / 1 | 99 (1.9%) | +0.102 / +0.045 | +0.095 | 0.915 / 0.752 | 42.9% / 34.8% / 0.0% | 0.179 / -0.203 |
| `destek_uzakta_kaldi` | 12 | 750 / 750 / 1 | 99 (1.9%) | +0.087 / +0.044 | +0.075 | 0.999 / 0.837 | 45.2% / 37.7% / 0.0% | 0.275 / -0.212 |
| `destek_uzakta_kaldi` | 16 | 750 / 750 / 1 | 99 (1.9%) | +0.094 / -0.071 | +0.073 | 1.200 / 1.006 | 48.8% / 41.7% / 0.0% | 0.318 / -0.354 |

- **KARŞI ÖRNEK:** ERSU (2025-10-08 13:30, kova=destek_fiyati_yakaladi): 8x4H korunan=+4.38 ATR (MFE=4.38 / MAE=0.28 ATR) · GARAN (2026-02-27 13:30, kova=destek_uzakta_kaldi): 8x4H korunan=-5.05 ATR (MFE=0.04 / MAE=5.30 ATR)
- **SINIR:** Yol içi MFE ile kapanışta korunan getiri ayrı okunmalıdır.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.037 ATR) ve MAE farkı (0.080 ATR) sınırlı kaldı.

## STB-BHV-B01 — Yukarı takip sonrası yataylaşmanın ardından devam, bekleme ve kırılma nasıl dağılıyor?

- **TANIM:** Aday eşlemeye göre yukarı basamak (STEPPING_UP), yükseliş sonrası yeni yataylaşma ve uzun yatay kalış kova karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=43682`, 8×4H tam ufuk `n=43531`, sağdan sansürlü `n=151`, ATR geçerli `n=43531`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `PROVISIONAL_CANDIDATE_PENDING_USER_CONFIRMATION`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `LONG_HORIZONTAL` (8×4H n=4248, med=0.100 ATR, ort=0.179 ATR, MFE_med=0.835, MAE_med=0.569, top1_sembol=7.2%) vs `NEWLY_FLATTENED_AFTER_RISE` (8×4H n=13760, med=0.000 ATR, ort=0.085 ATR, MFE_med=0.766, MAE_med=0.614, top1_sembol=2.2%) vs `STEPPING_UP` (8×4H n=25523, med=-0.027 ATR, ort=0.067 ATR, MFE_med=0.744, MAE_med=0.630, top1_sembol=1.6%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `LONG_HORIZONTAL` | 1 | 4248 / 4248 / 0 | 91 (7.2%) | +0.021 / +0.000 | +0.033 | 0.180 / 0.164 | 5.7% / 3.0% / 0.1% | 0.000 / 0.000 |
| `LONG_HORIZONTAL` | 4 | 4248 / 4248 / 0 | 91 (7.2%) | +0.093 / +0.042 | +0.129 | 0.540 / 0.385 | 24.9% / 15.8% / 0.4% | 0.071 / 0.000 |
| `LONG_HORIZONTAL` | 8 | 4248 / 4248 / 0 | 91 (7.2%) | +0.179 / +0.100 | +0.243 | 0.835 / 0.569 | 40.0% / 26.5% / 0.5% | 0.167 / 0.031 |
| `LONG_HORIZONTAL` | 10 | 4248 / 4248 / 0 | 91 (7.2%) | +0.213 / +0.113 | +0.285 | 0.957 / 0.646 | 44.8% / 30.5% / 0.5% | 0.194 / 0.026 |
| `LONG_HORIZONTAL` | 12 | 4248 / 4248 / 0 | 91 (7.2%) | +0.239 / +0.110 | +0.315 | 1.063 / 0.718 | 47.8% / 33.2% / 0.5% | 0.223 / 0.000 |
| `LONG_HORIZONTAL` | 16 | 4248 / 4248 / 0 | 91 (7.2%) | +0.240 / +0.148 | +0.263 | 1.229 / 0.853 | 50.8% / 36.7% / 0.5% | 0.356 / -0.021 |
| `NEWLY_FLATTENED_AFTER_RISE` | 1 | 13777 / 13777 / 2 | 99 (2.2%) | +0.014 / +0.000 | +0.012 | 0.173 / 0.155 | 5.5% / 3.0% / 0.1% | 0.000 / 0.000 |
| `NEWLY_FLATTENED_AFTER_RISE` | 4 | 13769 / 13769 / 10 | 99 (2.2%) | +0.048 / +0.000 | +0.037 | 0.518 / 0.410 | 23.3% / 15.4% / 0.4% | 0.023 / -0.028 |
| `NEWLY_FLATTENED_AFTER_RISE` | 8 | 13760 / 13760 / 19 | 99 (2.2%) | +0.085 / +0.000 | +0.056 | 0.766 / 0.614 | 37.6% / 28.7% / 0.4% | 0.054 / -0.037 |
| `NEWLY_FLATTENED_AFTER_RISE` | 10 | 13758 / 13758 / 21 | 99 (2.2%) | +0.103 / +0.000 | +0.063 | 0.873 / 0.710 | 41.8% / 33.2% / 0.4% | 0.079 / -0.056 |
| `NEWLY_FLATTENED_AFTER_RISE` | 12 | 13756 / 13756 / 23 | 99 (2.2%) | +0.120 / +0.013 | +0.070 | 0.971 / 0.795 | 45.1% / 36.2% / 0.5% | 0.082 / -0.067 |
| `NEWLY_FLATTENED_AFTER_RISE` | 16 | 13752 / 13752 / 27 | 99 (2.2%) | +0.131 / +0.004 | +0.055 | 1.164 / 0.949 | 48.8% / 40.3% / 0.5% | 0.130 / -0.103 |
| `STEPPING_UP` | 1 | 25644 / 25644 / 11 | 100 (1.6%) | +0.009 / +0.000 | +0.006 | 0.170 / 0.160 | 5.6% / 3.0% / 0.1% | 0.000 / -0.015 |
| `STEPPING_UP` | 4 | 25606 / 25606 / 49 | 100 (1.6%) | +0.034 / -0.009 | +0.024 | 0.501 / 0.420 | 23.0% / 15.5% / 0.3% | 0.029 / -0.054 |
| `STEPPING_UP` | 8 | 25523 / 25523 / 132 | 100 (1.6%) | +0.067 / -0.027 | +0.043 | 0.744 / 0.630 | 36.6% / 28.6% / 0.3% | 0.062 / -0.116 |
| `STEPPING_UP` | 10 | 25489 / 25489 / 166 | 100 (1.6%) | +0.080 / -0.015 | +0.052 | 0.847 / 0.717 | 40.8% / 33.2% / 0.4% | 0.106 / -0.150 |
| `STEPPING_UP` | 12 | 25454 / 25454 / 201 | 100 (1.6%) | +0.092 / +0.000 | +0.059 | 0.942 / 0.802 | 44.0% / 36.5% / 0.4% | 0.132 / -0.159 |
| `STEPPING_UP` | 16 | 25382 / 25382 / 273 | 100 (1.6%) | +0.127 / +0.000 | +0.080 | 1.119 / 0.936 | 48.0% / 40.2% / 0.4% | 0.174 / -0.190 |

- **KARŞI ÖRNEK:** CANTE (2025-07-25 17:30, kova=STEPPING_UP): 8x4H korunan=+7.82 ATR (MFE=10.42 / MAE=0.00 ATR) · BEGYO (2025-05-09 13:30, kova=NEWLY_FLATTENED_AFTER_RISE): 8x4H korunan=-13.23 ATR (MFE=0.05 / MAE=13.23 ATR) · DMSAS (2025-12-26 18:00, kova=LONG_HORIZONTAL): 8x4H korunan=-13.19 ATR (MFE=4.31 / MAE=13.19 ATR)
- **SINIR:** DİKKAT: Aday dikey/yatay eşlemesi gerçek grafik örneği üzerinde kullanıcıyla teyit edilene kadar bu ölçüm aday/proxy niteliğindedir.
- **SONUÇ (`ayrı doğrulama gerekli`):** Aday dikey/yatay eşlemesi altında 8x4H medyan farkı 0.127 ATR, MAE farkı 0.062 ATR [LONG_HORIZONTAL: med=+0.100 / MAE=0.569 ATR (n=4248), NEWLY_FLATTENED_AFTER_RISE: med=+0.000 / MAE=0.614 ATR (n=13760), STEPPING_UP: med=-0.027 / MAE=0.630 ATR (n=25523)]; aday rejim eşlemesi debug niteliğinde olduğundan kesin kural sayılmaz.

## STB-BHV-B02 — Yeni yataydan önce yükseliş uzun sürmüşse kırılma daha sık veya sert mi?

- **TANIM:** Yeni yataylaşmış (aday eşleme: 9-23 günlük yaş) destekte önceki yükseliş süresinin >=20 gün vs <20 gün karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=13779`, 8×4H tam ufuk `n=13760`, sağdan sansürlü `n=19`, ATR geçerli `n=13760`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `PROVISIONAL_CANDIDATE_PENDING_USER_CONFIRMATION`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `kisa_yukselis_sonrasi_yeni_yatay` (8×4H n=6147, med=0.029 ATR, ort=0.077 ATR, MFE_med=0.759, MAE_med=0.585, top1_sembol=2.8%) vs `uzun_yukselis_sonrasi_yeni_yatay` (8×4H n=7613, med=0.000 ATR, ort=0.091 ATR, MFE_med=0.772, MAE_med=0.638, top1_sembol=3.3%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `kisa_yukselis_sonrasi_yeni_yatay` | 1 | 6157 / 6157 / 1 | 98 (2.8%) | +0.016 / +0.000 | +0.006 | 0.168 / 0.155 | 5.2% / 2.5% / 0.1% | 0.000 / 0.000 |
| `kisa_yukselis_sonrasi_yeni_yatay` | 4 | 6152 / 6152 / 6 | 98 (2.8%) | +0.052 / +0.012 | +0.028 | 0.518 / 0.395 | 22.2% / 13.9% / 0.3% | 0.045 / -0.015 |
| `kisa_yukselis_sonrasi_yeni_yatay` | 8 | 6147 / 6147 / 11 | 98 (2.8%) | +0.077 / +0.029 | +0.042 | 0.759 / 0.585 | 37.3% / 26.8% / 0.4% | 0.105 / -0.050 |
| `kisa_yukselis_sonrasi_yeni_yatay` | 10 | 6147 / 6147 / 11 | 98 (2.8%) | +0.092 / +0.028 | +0.040 | 0.865 / 0.678 | 41.9% / 31.6% / 0.4% | 0.134 / -0.070 |
| `kisa_yukselis_sonrasi_yeni_yatay` | 12 | 6147 / 6147 / 11 | 98 (2.8%) | +0.104 / +0.053 | +0.030 | 0.976 / 0.767 | 45.6% / 34.8% / 0.4% | 0.171 / -0.096 |
| `kisa_yukselis_sonrasi_yeni_yatay` | 16 | 6147 / 6147 / 11 | 98 (2.8%) | +0.092 / +0.036 | -0.018 | 1.164 / 0.903 | 49.5% / 39.2% / 0.4% | 0.185 / -0.132 |
| `uzun_yukselis_sonrasi_yeni_yatay` | 1 | 7620 / 7620 / 1 | 98 (3.3%) | +0.013 / +0.000 | +0.011 | 0.177 / 0.154 | 5.7% / 3.4% / 0.2% | 0.000 / 0.000 |
| `uzun_yukselis_sonrasi_yeni_yatay` | 4 | 7617 / 7617 / 4 | 98 (3.3%) | +0.044 / -0.015 | +0.027 | 0.518 / 0.424 | 24.2% / 16.5% / 0.4% | 0.000 / -0.027 |
| `uzun_yukselis_sonrasi_yeni_yatay` | 8 | 7613 / 7613 / 8 | 98 (3.3%) | +0.091 / +0.000 | +0.038 | 0.772 / 0.638 | 37.8% / 30.1% / 0.5% | 0.000 / -0.022 |
| `uzun_yukselis_sonrasi_yeni_yatay` | 10 | 7611 / 7611 / 10 | 98 (3.3%) | +0.112 / -0.014 | +0.043 | 0.876 / 0.733 | 41.8% / 34.5% / 0.5% | 0.018 / -0.041 |
| `uzun_yukselis_sonrasi_yeni_yatay` | 12 | 7609 / 7609 / 12 | 98 (3.3%) | +0.132 / -0.023 | +0.049 | 0.967 / 0.821 | 44.7% / 37.4% / 0.5% | 0.000 / -0.046 |
| `uzun_yukselis_sonrasi_yeni_yatay` | 16 | 7605 / 7605 / 16 | 98 (3.3%) | +0.162 / -0.013 | +0.054 | 1.165 / 0.993 | 48.2% / 41.2% / 0.6% | 0.073 / -0.087 |

- **KARŞI ÖRNEK:** ALTNY (2025-07-28 18:00, kova=kisa_yukselis_sonrasi_yeni_yatay): 8x4H korunan=-5.50 ATR (MFE=0.46 / MAE=5.59 ATR) · BEGYO (2025-05-09 13:30, kova=uzun_yukselis_sonrasi_yeni_yatay): 8x4H korunan=-13.23 ATR (MFE=0.05 / MAE=13.23 ATR)
- **SINIR:** Aday yataylaşma eşlemesi kullanıcı grafik onayı beklemektedir; önceki yükseliş süresi yatay yaşından ayrı tutulmuştur.
- **SONUÇ (`ayrı doğrulama gerekli`):** Aday dikey/yatay eşlemesi altında 8x4H medyan farkı 0.029 ATR, MAE farkı 0.053 ATR [kisa_yukselis_sonrasi_yeni_yatay: med=+0.029 / MAE=0.585 ATR (n=6147), uzun_yukselis_sonrasi_yeni_yatay: med=+0.000 / MAE=0.638 ATR (n=7613)]; aday rejim eşlemesi debug niteliğinde olduğundan kesin kural sayılmaz.

## STB-BHV-B03 — Önceki yükselişin şiddeti ve hızı, süreden bağımsız ek bilgi taşıyor mu?

- **TANIM:** Benzer önceki yükseliş süresinde (>=12 gün) yeni yataylaşan destekte ATR kazanç şiddeti >=3.0 vs <3.0 karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=10704`, 8×4H tam ufuk `n=10696`, sağdan sansürlü `n=8`, ATR geçerli `n=10696`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `PROVISIONAL_CANDIDATE_PENDING_USER_CONFIRMATION`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `ilimli_onceki_artis` (8×4H n=5747, med=-0.015 ATR, ort=0.080 ATR, MFE_med=0.753, MAE_med=0.621, top1_sembol=2.8%) vs `yuksek_siddetli_onceki_artis` (8×4H n=4949, med=0.000 ATR, ort=0.077 ATR, MFE_med=0.796, MAE_med=0.651, top1_sembol=3.7%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ilimli_onceki_artis` | 1 | 5747 / 5747 / 0 | 95 (2.8%) | +0.015 / +0.000 | +0.014 | 0.166 / 0.158 | 5.6% / 2.5% / 0.1% | 0.000 / 0.000 |
| `ilimli_onceki_artis` | 4 | 5747 / 5747 / 0 | 95 (2.8%) | +0.047 / -0.021 | +0.039 | 0.511 / 0.416 | 23.3% / 14.6% / 0.4% | 0.025 / -0.062 |
| `ilimli_onceki_artis` | 8 | 5747 / 5747 / 0 | 95 (2.8%) | +0.080 / -0.015 | +0.044 | 0.753 / 0.621 | 37.2% / 28.7% / 0.4% | 0.081 / -0.104 |
| `ilimli_onceki_artis` | 10 | 5747 / 5747 / 0 | 95 (2.8%) | +0.103 / +0.000 | +0.059 | 0.866 / 0.725 | 41.5% / 33.7% / 0.4% | 0.121 / -0.126 |
| `ilimli_onceki_artis` | 12 | 5747 / 5747 / 0 | 95 (2.8%) | +0.132 / +0.016 | +0.083 | 0.971 / 0.810 | 44.6% / 37.0% / 0.4% | 0.156 / -0.135 |
| `ilimli_onceki_artis` | 16 | 5747 / 5747 / 0 | 95 (2.8%) | +0.161 / +0.000 | +0.091 | 1.222 / 0.984 | 48.1% / 41.6% / 0.4% | 0.239 / -0.276 |
| `yuksek_siddetli_onceki_artis` | 1 | 4956 / 4956 / 1 | 91 (3.7%) | +0.010 / +0.000 | -0.021 | 0.186 / 0.153 | 5.7% / 3.9% / 0.1% | 0.000 / 0.000 |
| `yuksek_siddetli_onceki_artis` | 4 | 4953 / 4953 / 4 | 91 (3.7%) | +0.039 / +0.000 | -0.068 | 0.536 / 0.426 | 24.4% / 18.0% / 0.4% | 0.000 / 0.000 |
| `yuksek_siddetli_onceki_artis` | 8 | 4949 / 4949 / 8 | 91 (3.7%) | +0.077 / +0.000 | -0.159 | 0.796 / 0.651 | 38.8% / 31.0% / 0.5% | 0.030 / -0.021 |
| `yuksek_siddetli_onceki_artis` | 10 | 4947 / 4947 / 10 | 91 (3.7%) | +0.086 / +0.000 | -0.222 | 0.894 / 0.746 | 42.6% / 34.9% / 0.5% | 0.047 / -0.047 |
| `yuksek_siddetli_onceki_artis` | 12 | 4945 / 4945 / 12 | 91 (3.7%) | +0.088 / -0.024 | -0.284 | 0.988 / 0.837 | 45.5% / 37.7% / 0.5% | 0.029 / -0.069 |
| `yuksek_siddetli_onceki_artis` | 16 | 4941 / 4941 / 16 | 91 (3.7%) | +0.081 / -0.034 | -0.363 | 1.149 / 0.995 | 48.9% / 41.0% / 0.7% | 0.063 / -0.097 |

- **KARŞI ÖRNEK:** DIRIT (2025-08-13 17:30, kova=ilimli_onceki_artis): 8x4H korunan=+7.95 ATR (MFE=7.95 / MAE=0.00 ATR) · BEGYO (2025-05-09 13:30, kova=yuksek_siddetli_onceki_artis): 8x4H korunan=-13.23 ATR (MFE=0.05 / MAE=13.23 ATR)
- **SINIR:** Aday yataylaşma eşlemesi kullanıcı grafik onayı beklemektedir.
- **SONUÇ (`ayrı doğrulama gerekli`):** Aday dikey/yatay eşlemesi altında 8x4H medyan farkı 0.015 ATR, MAE farkı 0.030 ATR [ilimli_onceki_artis: med=-0.015 / MAE=0.621 ATR (n=5747), yuksek_siddetli_onceki_artis: med=+0.000 / MAE=0.651 ATR (n=4949)]; aday rejim eşlemesi debug niteliğinde olduğundan kesin kural sayılmaz.

## STB-BHV-B04 — Uzun yatay seviyelerde bir sonraki ani aşağı kırılma gerçekten daha az mı?

- **TANIM:** Benzer destek mesafesinde (0-2.5 ATR) yeni yataylaşmış seviye ile >=24 gün uzun yatay seviyenin aşağı MAE ve -1 ATR kırılma oranı.
- **VERİ:** Toplam checkpoint/olay `n=6650`, 8×4H tam ufuk `n=6644`, sağdan sansürlü `n=6`, ATR geçerli `n=6644`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `PROVISIONAL_CANDIDATE_PENDING_USER_CONFIRMATION`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `LONG_HORIZONTAL` (8×4H n=1205, med=0.000 ATR, ort=0.084 ATR, MFE_med=0.658, MAE_med=0.560, top1_sembol=16.4%) vs `NEWLY_FLATTENED_AFTER_RISE` (8×4H n=5439, med=-0.035 ATR, ort=0.046 ATR, MFE_med=0.660, MAE_med=0.569, top1_sembol=2.6%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `LONG_HORIZONTAL` | 1 | 1205 / 1205 / 0 | 62 (16.4%) | +0.004 / +0.000 | +0.030 | 0.150 / 0.175 | 4.0% / 2.2% / 0.2% | 0.000 / 0.000 |
| `LONG_HORIZONTAL` | 4 | 1205 / 1205 / 0 | 62 (16.4%) | +0.042 / +0.000 | +0.186 | 0.417 / 0.397 | 17.8% / 12.5% / 0.2% | 0.043 / -0.024 |
| `LONG_HORIZONTAL` | 8 | 1205 / 1205 / 0 | 62 (16.4%) | +0.084 / +0.000 | +0.317 | 0.658 / 0.560 | 30.6% / 23.7% / 0.2% | 0.168 / -0.116 |
| `LONG_HORIZONTAL` | 10 | 1205 / 1205 / 0 | 62 (16.4%) | +0.088 / +0.000 | +0.393 | 0.733 / 0.618 | 35.7% / 27.8% / 0.2% | 0.172 / -0.264 |
| `LONG_HORIZONTAL` | 12 | 1205 / 1205 / 0 | 62 (16.4%) | +0.080 / -0.052 | +0.398 | 0.842 / 0.718 | 38.8% / 32.1% / 0.2% | 0.220 / -0.353 |
| `LONG_HORIZONTAL` | 16 | 1205 / 1205 / 0 | 62 (16.4%) | +0.048 / -0.077 | +0.328 | 0.949 / 0.874 | 41.7% / 38.2% / 0.2% | 0.253 / -0.396 |
| `NEWLY_FLATTENED_AFTER_RISE` | 1 | 5445 / 5445 / 0 | 98 (2.6%) | +0.005 / +0.000 | +0.011 | 0.154 / 0.141 | 3.8% / 1.9% / 0.0% | 0.000 / 0.000 |
| `NEWLY_FLATTENED_AFTER_RISE` | 4 | 5443 / 5443 / 2 | 98 (2.6%) | +0.020 / -0.027 | +0.031 | 0.446 / 0.369 | 18.5% / 12.0% / 0.1% | 0.028 / -0.085 |
| `NEWLY_FLATTENED_AFTER_RISE` | 8 | 5439 / 5439 / 6 | 98 (2.6%) | +0.046 / -0.035 | +0.036 | 0.660 / 0.569 | 33.0% / 25.3% / 0.2% | 0.077 / -0.161 |
| `NEWLY_FLATTENED_AFTER_RISE` | 10 | 5439 / 5439 / 6 | 98 (2.6%) | +0.059 / -0.038 | +0.037 | 0.745 / 0.657 | 37.5% / 30.8% / 0.2% | 0.115 / -0.177 |
| `NEWLY_FLATTENED_AFTER_RISE` | 12 | 5439 / 5439 / 6 | 98 (2.6%) | +0.065 / -0.033 | +0.029 | 0.830 / 0.729 | 40.8% / 34.7% / 0.2% | 0.148 / -0.234 |
| `NEWLY_FLATTENED_AFTER_RISE` | 16 | 5439 / 5439 / 6 | 98 (2.6%) | +0.051 / -0.030 | -0.017 | 0.989 / 0.874 | 45.4% / 40.2% / 0.2% | 0.208 / -0.287 |

- **KARŞI ÖRNEK:** AKCNS (2026-01-23 17:30, kova=NEWLY_FLATTENED_AFTER_RISE): 8x4H korunan=+8.96 ATR (MFE=8.96 / MAE=0.15 ATR) · IHEVA (2026-09-15 18:00, kova=LONG_HORIZONTAL): 8x4H korunan=-4.74 ATR (MFE=0.00 / MAE=5.31 ATR)
- **SINIR:** Sağ kalım etkisi ve aday yataylaşma eşlemesi birlikte dikkate alınmalıdır; kullanıcı grafik teyidi beklemektedir.
- **SONUÇ (`ayrı doğrulama gerekli`):** Aday dikey/yatay eşlemesi altında 8x4H medyan farkı 0.035 ATR, MAE farkı 0.009 ATR [LONG_HORIZONTAL: med=+0.000 / MAE=0.560 ATR (n=1205), NEWLY_FLATTENED_AFTER_RISE: med=-0.035 / MAE=0.569 ATR (n=5439)]; aday rejim eşlemesi debug niteliğinde olduğundan kesin kural sayılmaz.

## STB-BHV-B05 — Yeni yatayda kırılma sıklığı mı, kırılınca şiddet mi artıyor?

- **TANIM:** 4H kapanışın destek altına ilk indiği anda kırılan desteğin önceki aday rejimine göre koşullu hasar (MAE/korunan zarar).
- **VERİ:** Toplam checkpoint/olay `n=706`, 8×4H tam ufuk `n=692`, sağdan sansürlü `n=14`, ATR geçerli `n=692`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `PROVISIONAL_CANDIDATE_PENDING_USER_CONFIRMATION`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `LONG_HORIZONTAL` (8×4H n=39, med=0.000 ATR, ort=0.001 ATR, MFE_med=0.616, MAE_med=0.610, top1_sembol=20.5%) vs `NEWLY_FLATTENED_AFTER_RISE` (8×4H n=181, med=-0.122 ATR, ort=-0.051 ATR, MFE_med=0.677, MAE_med=0.632, top1_sembol=3.3%) vs `STEPPING_UP` (8×4H n=472, med=-0.135 ATR, ort=-0.105 ATR, MFE_med=0.620, MAE_med=0.743, top1_sembol=1.9%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `LONG_HORIZONTAL` | 1 | 39 / 39 / 0 | 24 (20.5%) | +0.016 / +0.000 | +0.024 | 0.190 / 0.128 | 2.6% / 2.6% / 0.0% | 0.000 / 0.000 |
| `LONG_HORIZONTAL` | 4 | 39 / 39 / 0 | 24 (20.5%) | +0.043 / -0.026 | +0.089 | 0.425 / 0.425 | 15.4% / 10.3% / 0.0% | -0.165 / 0.149 |
| `LONG_HORIZONTAL` | 8 | 39 / 39 / 0 | 24 (20.5%) | +0.001 / +0.000 | +0.085 | 0.616 / 0.610 | 28.2% / 28.2% / 0.0% | 0.182 / -0.102 |
| `LONG_HORIZONTAL` | 10 | 39 / 39 / 0 | 24 (20.5%) | -0.217 / -0.133 | -0.113 | 0.689 / 0.770 | 28.2% / 33.3% / 0.0% | -0.097 / -0.133 |
| `LONG_HORIZONTAL` | 12 | 39 / 39 / 0 | 24 (20.5%) | -0.249 / -0.313 | -0.102 | 0.774 / 0.875 | 28.2% / 41.0% / 0.0% | -0.249 / -0.358 |
| `LONG_HORIZONTAL` | 16 | 39 / 39 / 0 | 24 (20.5%) | -0.248 / -0.256 | -0.025 | 0.851 / 1.161 | 28.2% / 48.7% / 0.0% | 0.165 / -0.448 |
| `NEWLY_FLATTENED_AFTER_RISE` | 1 | 182 / 182 / 0 | 83 (3.3%) | -0.028 / -0.024 | -0.030 | 0.117 / 0.141 | 3.3% / 1.1% / 0.0% | -0.026 / 0.000 |
| `NEWLY_FLATTENED_AFTER_RISE` | 4 | 181 / 181 / 1 | 83 (3.3%) | -0.072 / -0.054 | -0.082 | 0.397 / 0.433 | 15.5% / 17.1% / 0.5% | -0.018 / -0.082 |
| `NEWLY_FLATTENED_AFTER_RISE` | 8 | 181 / 181 / 1 | 83 (3.3%) | -0.051 / -0.122 | -0.059 | 0.677 / 0.632 | 29.8% / 27.1% / 0.5% | -0.125 / -0.103 |
| `NEWLY_FLATTENED_AFTER_RISE` | 10 | 181 / 181 / 1 | 83 (3.3%) | -0.132 / -0.217 | -0.103 | 0.716 / 0.722 | 33.7% / 33.1% / 0.5% | -0.232 / -0.116 |
| `NEWLY_FLATTENED_AFTER_RISE` | 12 | 181 / 181 / 1 | 83 (3.3%) | -0.146 / -0.248 | -0.111 | 0.839 / 0.860 | 35.9% / 36.5% / 0.5% | -0.246 / -0.255 |
| `NEWLY_FLATTENED_AFTER_RISE` | 16 | 181 / 181 / 1 | 83 (3.3%) | -0.216 / -0.307 | -0.327 | 0.899 / 1.002 | 38.1% / 43.6% / 0.5% | -0.293 / -0.348 |
| `STEPPING_UP` | 1 | 485 / 485 / 0 | 100 (1.9%) | -0.051 / -0.028 | -0.052 | 0.136 / 0.162 | 2.3% / 4.3% / 0.0% | -0.011 / -0.048 |
| `STEPPING_UP` | 4 | 474 / 474 / 11 | 100 (1.9%) | -0.048 / -0.064 | -0.051 | 0.424 / 0.499 | 14.1% / 22.6% / 0.2% | -0.047 / -0.084 |
| `STEPPING_UP` | 8 | 472 / 472 / 13 | 100 (1.9%) | -0.105 / -0.135 | -0.090 | 0.620 / 0.743 | 27.5% / 35.8% / 0.4% | -0.050 / -0.252 |
| `STEPPING_UP` | 10 | 471 / 471 / 14 | 100 (1.9%) | -0.139 / -0.206 | -0.124 | 0.717 / 0.852 | 32.7% / 41.6% / 0.4% | -0.155 / -0.256 |
| `STEPPING_UP` | 12 | 470 / 470 / 15 | 100 (1.9%) | -0.202 / -0.193 | -0.191 | 0.777 / 0.951 | 34.5% / 46.2% / 0.4% | -0.138 / -0.243 |
| `STEPPING_UP` | 16 | 468 / 468 / 17 | 100 (1.9%) | -0.097 / -0.111 | -0.102 | 0.923 / 1.026 | 37.4% / 48.3% / 0.4% | -0.066 / -0.212 |

- **KARŞI ÖRNEK:** HALKB (2026-05-21 18:00, kova=STEPPING_UP): 8x4H korunan=+5.11 ATR (MFE=5.46 / MAE=0.03 ATR) · GWIND (2026-04-24 13:30, kova=NEWLY_FLATTENED_AFTER_RISE): 8x4H korunan=+3.24 ATR (MFE=3.24 / MAE=0.04 ATR) · DENGE (2026-05-18 13:30, kova=LONG_HORIZONTAL): 8x4H korunan=-1.99 ATR (MFE=0.19 / MAE=1.99 ATR)
- **SINIR:** Koşulsuz sıklık B04'te, kırılma anındaki koşullu şiddet burada ayrı raporlanır; aday eşleme kullanıcı teyidi bekler.
- **SONUÇ (`ayrı doğrulama gerekli`):** Aday dikey/yatay eşlemesi altında 8x4H medyan farkı 0.135 ATR, MAE farkı 0.133 ATR [LONG_HORIZONTAL: med=+0.000 / MAE=0.610 ATR (n=39), NEWLY_FLATTENED_AFTER_RISE: med=-0.122 / MAE=0.632 ATR (n=181), STEPPING_UP: med=-0.135 / MAE=0.743 ATR (n=472)]; aday rejim eşlemesi debug niteliğinde olduğundan kesin kural sayılmaz.

## STB-BHV-B06 — Yataylaşma fiyat sakinleşmesini mi, pivot teyit gecikmesini mi yansıtıyor?

- **TANIM:** İlk 1-4 günlük doğal pivot teyit penceresi ile 5-12 günlük pencerede sakinleşen vs hareketli kalan fiyatın ayrımı.
- **VERİ:** Toplam checkpoint/olay `n=58459`, 8×4H tam ufuk `n=58118`, sağdan sansürlü `n=341`, ATR geçerli `n=58118`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `PROVISIONAL_CANDIDATE_PENDING_USER_CONFIRMATION`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `hareketli_fiyat_5_12g` (8×4H n=16204, med=-0.052 ATR, ort=0.019 ATR, MFE_med=0.754, MAE_med=0.675, top1_sembol=1.5%) vs `pivot_onay_penceresi_1_4g` (8×4H n=25494, med=-0.117 ATR, ort=-0.030 ATR, MFE_med=0.655, MAE_med=0.657, top1_sembol=1.2%) vs `sakinlesen_fiyat_5_12g` (8×4H n=16420, med=-0.016 ATR, ort=0.078 ATR, MFE_med=0.682, MAE_med=0.574, top1_sembol=1.4%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `hareketli_fiyat_5_12g` | 1 | 16330 / 16330 / 8 | 100 (1.5%) | -0.003 / -0.013 | -0.006 | 0.175 / 0.173 | 5.8% / 3.7% / 0.2% | -0.018 / 0.000 |
| `hareketli_fiyat_5_12g` | 4 | 16292 / 16292 / 46 | 100 (1.5%) | +0.002 / -0.049 | -0.010 | 0.500 / 0.464 | 23.4% / 17.1% / 0.4% | -0.047 / -0.051 |
| `hareketli_fiyat_5_12g` | 8 | 16204 / 16204 / 134 | 100 (1.5%) | +0.019 / -0.052 | -0.004 | 0.754 / 0.675 | 36.3% / 30.3% / 0.5% | -0.055 / -0.048 |
| `hareketli_fiyat_5_12g` | 10 | 16179 / 16179 / 159 | 100 (1.5%) | +0.030 / -0.056 | +0.001 | 0.856 / 0.758 | 40.3% / 34.6% / 0.5% | -0.040 / -0.068 |
| `hareketli_fiyat_5_12g` | 12 | 16161 / 16161 / 177 | 100 (1.5%) | +0.035 / -0.067 | +0.001 | 0.944 / 0.838 | 43.0% / 37.6% / 0.5% | -0.041 / -0.093 |
| `hareketli_fiyat_5_12g` | 16 | 16148 / 16148 / 190 | 100 (1.5%) | +0.037 / -0.066 | -0.008 | 1.107 / 0.986 | 46.6% / 41.5% / 0.5% | -0.031 / -0.103 |
| `pivot_onay_penceresi_1_4g` | 1 | 25547 / 25547 / 5 | 100 (1.2%) | -0.001 / -0.013 | -0.001 | 0.157 / 0.159 | 4.9% / 2.8% / 0.1% | -0.009 / -0.014 |
| `pivot_onay_penceresi_1_4g` | 4 | 25524 / 25524 / 28 | 100 (1.2%) | -0.014 / -0.071 | -0.014 | 0.444 / 0.431 | 19.9% / 14.7% / 0.4% | -0.036 / -0.100 |
| `pivot_onay_penceresi_1_4g` | 8 | 25494 / 25494 / 58 | 100 (1.2%) | -0.030 / -0.117 | -0.031 | 0.655 / 0.657 | 32.2% / 29.0% / 0.4% | -0.045 / -0.186 |
| `pivot_onay_penceresi_1_4g` | 10 | 25468 / 25468 / 84 | 100 (1.2%) | -0.043 / -0.141 | -0.045 | 0.736 / 0.750 | 36.1% / 34.3% / 0.4% | -0.027 / -0.243 |
| `pivot_onay_penceresi_1_4g` | 12 | 25393 / 25393 / 159 | 100 (1.2%) | -0.044 / -0.145 | -0.047 | 0.817 / 0.837 | 39.1% / 38.2% / 0.4% | 0.000 / -0.277 |
| `pivot_onay_penceresi_1_4g` | 16 | 25139 / 25139 / 413 | 100 (1.2%) | -0.022 / -0.151 | -0.026 | 0.968 / 0.976 | 43.5% / 42.6% / 0.4% | 0.000 / -0.320 |
| `sakinlesen_fiyat_5_12g` | 1 | 16555 / 16555 / 14 | 100 (1.4%) | +0.008 / -0.009 | +0.007 | 0.157 / 0.149 | 4.1% / 1.8% / 0.0% | -0.015 / 0.000 |
| `sakinlesen_fiyat_5_12g` | 4 | 16509 / 16509 / 60 | 100 (1.4%) | +0.029 / -0.033 | +0.024 | 0.443 / 0.386 | 19.3% / 12.0% / 0.0% | -0.025 / -0.042 |
| `sakinlesen_fiyat_5_12g` | 8 | 16420 / 16420 / 149 | 100 (1.4%) | +0.078 / -0.016 | +0.070 | 0.682 / 0.574 | 33.4% / 25.1% / 0.1% | 0.017 / -0.057 |
| `sakinlesen_fiyat_5_12g` | 10 | 16350 / 16350 / 219 | 100 (1.4%) | +0.104 / +0.000 | +0.095 | 0.777 / 0.645 | 38.2% / 29.6% / 0.1% | 0.058 / -0.058 |
| `sakinlesen_fiyat_5_12g` | 12 | 16306 / 16306 / 263 | 100 (1.4%) | +0.132 / +0.011 | +0.121 | 0.875 / 0.712 | 42.0% / 32.9% / 0.1% | 0.074 / -0.048 |
| `sakinlesen_fiyat_5_12g` | 16 | 16263 / 16263 / 306 | 100 (1.4%) | +0.165 / +0.043 | +0.154 | 1.050 / 0.831 | 46.7% / 37.3% / 0.1% | 0.119 / -0.036 |

- **KARŞI ÖRNEK:** DIRIT (2026-02-11 17:30, kova=hareketli_fiyat_5_12g): 8x4H korunan=+8.05 ATR (MFE=9.36 / MAE=0.00 ATR) · DIRIT (2025-05-20 17:30, kova=pivot_onay_penceresi_1_4g): 8x4H korunan=+8.67 ATR (MFE=8.67 / MAE=0.00 ATR) · HALKB (2026-08-25 17:30, kova=sakinlesen_fiyat_5_12g): 8x4H korunan=+9.00 ATR (MFE=9.00 / MAE=0.02 ATR)
- **SINIR:** Native günlük pivot L=4 sağ bar onayına sahiptir; görsel yataylaşma tanımı kullanıcı grafik teyidiyle kesinleşecektir.
- **SONUÇ (`ayrı doğrulama gerekli`):** Aday dikey/yatay eşlemesi altında 8x4H medyan farkı 0.101 ATR, MAE farkı 0.101 ATR [hareketli_fiyat_5_12g: med=-0.052 / MAE=0.675 ATR (n=16204), pivot_onay_penceresi_1_4g: med=-0.117 / MAE=0.657 ATR (n=25494), sakinlesen_fiyat_5_12g: med=-0.016 / MAE=0.574 ATR (n=16420)]; aday rejim eşlemesi debug niteliğinde olduğundan kesin kural sayılmaz.

## STB-BHV-C01 — Yukarı takip sonrası ilk temas, temas olmadan devamdan nasıl farklı?

- **TANIM:** Yukarı taşınmış destekte ilk temasın gerçekleştiği 4H kapanışları ile temassız üstte devam eden kapanışların ileri dağılımı.
- **VERİ:** Toplam checkpoint/olay `n=42699`, 8×4H tam ufuk `n=42545`, sağdan sansürlü `n=154`, ATR geçerli `n=42545`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `ilk_temas_ani` (8×4H n=1771, med=-0.052 ATR, ort=-0.017 ATR, MFE_med=0.634, MAE_med=0.636, top1_sembol=2.3%) vs `temassiz_devam` (8×4H n=40774, med=0.000 ATR, ort=0.080 ATR, MFE_med=0.761, MAE_med=0.623, top1_sembol=1.7%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ilk_temas_ani` | 1 | 1795 / 1795 / 0 | 100 (2.3%) | -0.019 / -0.012 | -0.025 | 0.142 / 0.152 | 3.0% / 2.9% / 0.0% | -0.017 / 0.000 |
| `ilk_temas_ani` | 4 | 1791 / 1791 / 4 | 100 (2.3%) | -0.060 / -0.072 | -0.064 | 0.413 / 0.413 | 16.9% / 15.7% / 0.1% | -0.069 / -0.074 |
| `ilk_temas_ani` | 8 | 1771 / 1771 / 24 | 100 (2.3%) | -0.017 / -0.052 | -0.021 | 0.634 / 0.636 | 30.4% / 29.8% / 0.2% | 0.000 / -0.102 |
| `ilk_temas_ani` | 10 | 1770 / 1770 / 25 | 100 (2.3%) | -0.039 / -0.091 | -0.058 | 0.739 / 0.714 | 34.7% / 34.9% / 0.3% | -0.012 / -0.154 |
| `ilk_temas_ani` | 12 | 1767 / 1767 / 28 | 100 (2.3%) | -0.020 / -0.055 | -0.039 | 0.813 / 0.799 | 38.4% / 38.8% / 0.3% | 0.000 / -0.168 |
| `ilk_temas_ani` | 16 | 1759 / 1759 / 36 | 100 (2.3%) | -0.009 / -0.046 | -0.040 | 0.968 / 0.936 | 42.9% / 42.9% / 0.4% | 0.101 / -0.179 |
| `temassiz_devam` | 1 | 40891 / 40891 / 13 | 100 (1.7%) | +0.012 / +0.000 | +0.009 | 0.173 / 0.158 | 5.6% / 2.9% / 0.1% | 0.000 / 0.000 |
| `temassiz_devam` | 4 | 40849 / 40849 / 55 | 100 (1.7%) | +0.043 / +0.000 | +0.030 | 0.514 / 0.416 | 23.4% / 15.4% / 0.3% | 0.026 / -0.036 |
| `temassiz_devam` | 8 | 40774 / 40774 / 130 | 100 (1.7%) | +0.080 / +0.000 | +0.049 | 0.761 / 0.623 | 37.3% / 28.6% / 0.4% | 0.055 / -0.072 |
| `temassiz_devam` | 10 | 40739 / 40739 / 165 | 100 (1.7%) | +0.097 / +0.000 | +0.058 | 0.867 / 0.712 | 41.6% / 33.1% / 0.4% | 0.090 / -0.089 |
| `temassiz_devam` | 12 | 40705 / 40705 / 199 | 100 (1.7%) | +0.111 / +0.000 | +0.065 | 0.964 / 0.795 | 44.8% / 36.3% / 0.4% | 0.107 / -0.101 |
| `temassiz_devam` | 16 | 40637 / 40637 / 267 | 100 (1.7%) | +0.137 / +0.000 | +0.073 | 1.143 / 0.936 | 48.6% / 40.1% / 0.4% | 0.149 / -0.132 |

- **KARŞI ÖRNEK:** FONET (2025-10-08 18:00, kova=ilk_temas_ani): 8x4H korunan=+6.27 ATR (MFE=7.75 / MAE=0.00 ATR) · BEGYO (2025-05-09 13:30, kova=temassiz_devam): 8x4H korunan=-13.23 ATR (MFE=0.05 / MAE=13.23 ATR)
- **SINIR:** Temas yalnız gerçekleştiği anda çapalanır; gelecekte temas edecek olanlar önceden ayrılmaz.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.052 ATR, MAE farkı 0.013 ATR düzeyinde ayrıştı.

## STB-BHV-C02 — İlk ve sonraki bağımsız temaslar aynı tutunmayı mı üretiyor?

- **TANIM:** Aralarında en az 0.35 ATR ayrılma şartıyla sayılan 1., 2. ve 3+ bağımsız destek temaslarının karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=1976`, 8×4H tam ufuk `n=1943`, sağdan sansürlü `n=33`, ATR geçerli `n=1943`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `birinci_temas` (8×4H n=1773, med=-0.066 ATR, ort=-0.005 ATR, MFE_med=0.603, MAE_med=0.598, top1_sembol=4.9%) vs `ikinci_temas` (8×4H n=137, med=0.155 ATR, ort=0.256 ATR, MFE_med=0.723, MAE_med=0.575, top1_sembol=7.3%) vs `uc_ve_uzeri_temas` (8×4H n=33, med=-0.376 ATR, ort=-0.516 ATR, MFE_med=0.417, MAE_med=0.652, top1_sembol=81.8%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `birinci_temas` | 1 | 1804 / 1804 / 2 | 99 (4.9%) | -0.005 / +0.000 | -0.014 | 0.133 / 0.153 | 2.9% / 2.1% / 0.0% | 0.000 / 0.000 |
| `birinci_temas` | 4 | 1799 / 1799 / 7 | 99 (4.9%) | -0.039 / -0.086 | -0.054 | 0.403 / 0.402 | 17.3% / 12.1% / 0.1% | -0.045 / -0.146 |
| `birinci_temas` | 8 | 1773 / 1773 / 33 | 99 (4.9%) | -0.005 / -0.066 | -0.043 | 0.603 / 0.598 | 30.0% / 25.9% / 0.2% | 0.000 / -0.160 |
| `birinci_temas` | 10 | 1770 / 1770 / 36 | 99 (4.9%) | -0.008 / -0.082 | -0.050 | 0.696 / 0.704 | 34.5% / 31.2% / 0.2% | 0.021 / -0.195 |
| `birinci_temas` | 12 | 1763 / 1763 / 43 | 99 (4.9%) | +0.016 / -0.045 | -0.016 | 0.803 / 0.775 | 38.7% / 35.8% / 0.2% | 0.081 / -0.192 |
| `birinci_temas` | 16 | 1749 / 1749 / 57 | 99 (4.9%) | -0.004 / -0.087 | -0.041 | 0.930 / 0.892 | 43.4% / 41.4% / 0.2% | 0.070 / -0.299 |
| `ikinci_temas` | 1 | 137 / 137 / 0 | 38 (7.3%) | +0.016 / +0.000 | +0.038 | 0.157 / 0.154 | 2.9% / 0.0% / 0.0% | 0.000 / 0.000 |
| `ikinci_temas` | 4 | 137 / 137 / 0 | 38 (7.3%) | +0.138 / +0.034 | +0.126 | 0.418 / 0.342 | 19.7% / 8.0% / 0.7% | 0.070 / 0.000 |
| `ikinci_temas` | 8 | 137 / 137 / 0 | 38 (7.3%) | +0.256 / +0.155 | +0.166 | 0.723 / 0.575 | 35.0% / 23.4% / 0.7% | 0.383 / -0.111 |
| `ikinci_temas` | 10 | 137 / 137 / 0 | 38 (7.3%) | +0.327 / +0.279 | +0.149 | 0.883 / 0.642 | 41.6% / 31.4% / 0.7% | 0.609 / 0.106 |
| `ikinci_temas` | 12 | 136 / 136 / 1 | 38 (7.3%) | +0.397 / +0.302 | +0.181 | 1.155 / 0.683 | 46.3% / 36.0% / 0.7% | 0.650 / 0.000 |
| `ikinci_temas` | 16 | 136 / 136 / 1 | 38 (7.3%) | +0.376 / +0.316 | +0.156 | 1.316 / 0.709 | 50.0% / 40.4% / 0.7% | 0.912 / 0.000 |
| `uc_ve_uzeri_temas` | 1 | 33 / 33 / 0 | 5 (81.8%) | -0.052 / +0.000 | +0.188 | 0.136 / 0.309 | 3.0% / 3.0% / 0.0% | 0.000 / 0.000 |
| `uc_ve_uzeri_temas` | 4 | 33 / 33 / 0 | 5 (81.8%) | -0.231 / -0.217 | +0.218 | 0.197 / 0.591 | 9.1% / 12.1% / 0.0% | -0.197 / -0.323 |
| `uc_ve_uzeri_temas` | 8 | 33 / 33 / 0 | 5 (81.8%) | -0.516 / -0.376 | -0.194 | 0.417 / 0.652 | 12.1% / 33.3% / 0.0% | -0.217 / -1.148 |
| `uc_ve_uzeri_temas` | 10 | 33 / 33 / 0 | 5 (81.8%) | -0.571 / -0.294 | -0.186 | 0.439 / 0.834 | 15.2% / 36.4% / 0.0% | 0.000 / -1.446 |
| `uc_ve_uzeri_temas` | 12 | 33 / 33 / 0 | 5 (81.8%) | -0.766 / -0.197 | -0.564 | 0.564 / 0.869 | 15.2% / 39.4% / 0.0% | 0.000 / -1.640 |
| `uc_ve_uzeri_temas` | 16 | 33 / 33 / 0 | 5 (81.8%) | -1.162 / -0.674 | -0.772 | 0.626 / 1.427 | 15.2% / 48.5% / 0.0% | 0.000 / -2.090 |

- **KARŞI ÖRNEK:** AKFYE (2026-09-07 17:30, kova=birinci_temas): 8x4H korunan=+6.74 ATR (MFE=7.63 / MAE=0.36 ATR) · ESEN (2026-09-11 17:30, kova=ikinci_temas): 8x4H korunan=-2.23 ATR (MFE=0.08 / MAE=2.39 ATR) · EBEBK (2026-09-29 17:30, kova=uc_ve_uzeri_temas): 8x4H korunan=+0.47 ATR (MFE=0.81 / MAE=0.55 ATR)
- **SINIR:** Arşiv başındaki ilk epizot temas sayıları UNKNOWN olarak dışlanmıştır.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.531 ATR, MAE farkı 0.077 ATR düzeyinde ayrıştı.

## STB-BHV-C03 — Yavaş yaklaşmakla sert düşerek desteğe gelmek farklı mı?

- **TANIM:** Desteğe temas anında son 4x4H düşüşü >=1.0 ATR (sert geliş) ile <1.0 ATR (sakin yaklaşma) olan temasların tutunma farkı.
- **VERİ:** Toplam checkpoint/olay `n=3944`, 8×4H tam ufuk `n=3849`, sağdan sansürlü `n=95`, ATR geçerli `n=3849`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `sert_duserek_temas` (8×4H n=324, med=-0.051 ATR, ort=-0.041 ATR, MFE_med=0.687, MAE_med=0.661, top1_sembol=2.5%) vs `yavas_yaklasarak_temas` (8×4H n=3525, med=-0.054 ATR, ort=0.010 ATR, MFE_med=0.612, MAE_med=0.596, top1_sembol=3.7%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `sert_duserek_temas` | 1 | 326 / 326 / 0 | 93 (2.5%) | -0.041 / +0.000 | -0.038 | 0.186 / 0.191 | 2.5% / 4.6% / 0.0% | 0.000 / -0.027 |
| `sert_duserek_temas` | 4 | 325 / 325 / 1 | 93 (2.5%) | -0.014 / +0.027 | +0.014 | 0.506 / 0.429 | 22.1% / 18.5% / 0.0% | 0.127 / -0.072 |
| `sert_duserek_temas` | 8 | 324 / 324 / 2 | 93 (2.5%) | -0.041 / -0.051 | -0.029 | 0.687 / 0.661 | 37.0% / 30.2% / 0.0% | -0.012 / -0.090 |
| `sert_duserek_temas` | 10 | 323 / 323 / 3 | 93 (2.5%) | -0.114 / -0.150 | -0.089 | 0.775 / 0.765 | 40.9% / 36.8% / 0.0% | -0.165 / -0.134 |
| `sert_duserek_temas` | 12 | 322 / 322 / 4 | 93 (2.5%) | -0.141 / -0.244 | -0.082 | 0.808 / 0.845 | 41.6% / 41.0% / 0.0% | -0.233 / -0.279 |
| `sert_duserek_temas` | 16 | 321 / 321 / 5 | 93 (2.5%) | -0.023 / -0.080 | +0.013 | 1.020 / 0.983 | 44.2% / 44.2% / 0.0% | 0.043 / -0.209 |
| `yavas_yaklasarak_temas` | 1 | 3616 / 3616 / 2 | 100 (3.7%) | -0.011 / +0.000 | -0.009 | 0.128 / 0.153 | 3.0% / 2.4% / 0.0% | 0.000 / 0.000 |
| `yavas_yaklasarak_temas` | 4 | 3596 / 3596 / 22 | 100 (3.7%) | -0.034 / -0.073 | -0.031 | 0.400 / 0.402 | 16.8% / 13.0% / 0.1% | -0.042 / -0.106 |
| `yavas_yaklasarak_temas` | 8 | 3525 / 3525 / 93 | 100 (3.7%) | +0.010 / -0.054 | +0.013 | 0.612 / 0.596 | 29.7% / 27.0% / 0.1% | -0.006 / -0.094 |
| `yavas_yaklasarak_temas` | 10 | 3513 / 3513 / 105 | 100 (3.7%) | +0.008 / -0.074 | +0.005 | 0.701 / 0.679 | 34.3% / 31.7% / 0.2% | -0.024 / -0.105 |
| `yavas_yaklasarak_temas` | 12 | 3499 / 3499 / 119 | 100 (3.7%) | +0.032 / -0.024 | +0.040 | 0.797 / 0.749 | 38.4% / 35.8% / 0.2% | 0.000 / -0.099 |
| `yavas_yaklasarak_temas` | 16 | 3476 / 3476 / 142 | 100 (3.7%) | +0.038 / -0.044 | +0.061 | 0.941 / 0.874 | 43.0% / 40.9% / 0.2% | 0.066 / -0.158 |

- **KARŞI ÖRNEK:** AKFYE (2026-09-07 17:30, kova=yavas_yaklasarak_temas): 8x4H korunan=+6.74 ATR (MFE=7.63 / MAE=0.36 ATR) · KFEIN (2026-05-22 13:30, kova=sert_duserek_temas): 8x4H korunan=+3.97 ATR (MFE=3.97 / MAE=0.32 ATR)
- **SINIR:** Sert geliş aynı zamanda yüksek kısa vadeli oynaklık taşıyabilir; MAE birlikte okunmalıdır.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.003 ATR) ve MAE farkı (0.065 ATR) sınırlı kaldı.

## STB-BHV-C04 — Temaslardan sonra uzaklaşamamak kırılma riskini biriktiriyor mu?

- **TANIM:** Yalnız geçmişte tamamlanmış cılız tepkiler (<0.75 ATR) biriktikten sonraki yeni temaslar ile ilk temiz temasların karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=3972`, 8×4H tam ufuk `n=3877`, sağdan sansürlü `n=95`, ATR geçerli `n=3877`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `onceki_basarisiz_tepki_var` (8×4H n=55, med=-0.342 ATR, ort=-0.255 ATR, MFE_med=0.604, MAE_med=0.703, top1_sembol=18.2%) vs `onceki_basarisiz_tepki_yok` (8×4H n=3822, med=-0.040 ATR, ort=0.016 ATR, MFE_med=0.623, MAE_med=0.597, top1_sembol=3.5%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `onceki_basarisiz_tepki_var` | 1 | 55 / 55 / 0 | 18 (18.2%) | -0.002 / -0.029 | +0.043 | 0.174 / 0.168 | 3.6% / 0.0% / 0.0% | 0.000 / -0.084 |
| `onceki_basarisiz_tepki_var` | 4 | 55 / 55 / 0 | 18 (18.2%) | -0.078 / -0.093 | -0.012 | 0.443 / 0.431 | 12.7% / 9.1% / 1.8% | -0.040 / -0.142 |
| `onceki_basarisiz_tepki_var` | 8 | 55 / 55 / 0 | 18 (18.2%) | -0.255 / -0.342 | -0.203 | 0.604 / 0.703 | 18.2% / 34.5% / 1.8% | -0.309 / -0.366 |
| `onceki_basarisiz_tepki_var` | 10 | 55 / 55 / 0 | 18 (18.2%) | -0.242 / -0.352 | -0.244 | 0.757 / 0.966 | 27.3% / 45.5% / 1.8% | -0.541 / -0.174 |
| `onceki_basarisiz_tepki_var` | 12 | 55 / 55 / 0 | 18 (18.2%) | -0.218 / -0.467 | -0.310 | 0.855 / 1.162 | 32.7% / 52.7% / 1.8% | -0.580 / -0.133 |
| `onceki_basarisiz_tepki_var` | 16 | 55 / 55 / 0 | 18 (18.2%) | -0.182 / -0.113 | -0.395 | 0.932 / 1.299 | 34.5% / 60.0% / 1.8% | -0.680 / 0.000 |
| `onceki_basarisiz_tepki_yok` | 1 | 3915 / 3915 / 2 | 100 (3.5%) | -0.014 / +0.000 | -0.015 | 0.132 / 0.155 | 3.0% / 2.6% / 0.0% | 0.000 / 0.000 |
| `onceki_basarisiz_tepki_yok` | 4 | 3894 / 3894 / 23 | 100 (3.5%) | -0.030 / -0.065 | -0.027 | 0.404 / 0.404 | 17.3% / 13.5% / 0.1% | -0.029 / -0.101 |
| `onceki_basarisiz_tepki_yok` | 8 | 3822 / 3822 / 95 | 100 (3.5%) | +0.016 / -0.040 | +0.018 | 0.623 / 0.597 | 30.7% / 27.1% / 0.1% | 0.000 / -0.102 |
| `onceki_basarisiz_tepki_yok` | 10 | 3809 / 3809 / 108 | 100 (3.5%) | +0.011 / -0.067 | +0.010 | 0.711 / 0.677 | 35.3% / 31.8% / 0.1% | 0.000 / -0.130 |
| `onceki_basarisiz_tepki_yok` | 12 | 3794 / 3794 / 123 | 100 (3.5%) | +0.029 / -0.030 | +0.037 | 0.804 / 0.749 | 39.0% / 35.8% / 0.2% | 0.000 / -0.136 |
| `onceki_basarisiz_tepki_yok` | 16 | 3770 / 3770 / 147 | 100 (3.5%) | +0.038 / -0.034 | +0.056 | 0.955 / 0.872 | 43.5% / 40.7% / 0.2% | 0.094 / -0.181 |

- **KARŞI ÖRNEK:** AKFYE (2026-09-07 17:30, kova=onceki_basarisiz_tepki_yok): 8x4H korunan=+6.74 ATR (MFE=7.63 / MAE=0.36 ATR) · DERIM (2025-12-25 17:30, kova=onceki_basarisiz_tepki_var): 8x4H korunan=+2.91 ATR (MFE=2.91 / MAE=1.17 ATR)
- **SINIR:** Yalnız olay öncesinde tamamlanmış tepkiler sayılır.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.301 ATR, MAE farkı 0.105 ATR düzeyinde ayrıştı.

## STB-BHV-C05 — Tepkilerin giderek küçülmesi, temas sayısından daha açıklayıcı mı?

- **TANIM:** En az iki tamamlanmış tepki görmüş desteklerde son tepkinin bir öncekine göre %15+ küçüldüğü durumlar ile korunduğu durumlar.
- **VERİ:** Toplam checkpoint/olay `n=33`, 8×4H tam ufuk `n=33`, sağdan sansürlü `n=0`, ATR geçerli `n=33`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `korunan_veya_buyuyen_tepkiler` (8×4H n=25, med=0.000 ATR, ort=-0.149 ATR, MFE_med=0.617, MAE_med=0.617, top1_sembol=76.0%) vs `kuculen_tepkiler` (8×4H n=8, med=-1.616 ATR, ort=-1.661 ATR, MFE_med=0.000, MAE_med=2.263, top1_sembol=100.0%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `korunan_veya_buyuyen_tepkiler` | 1 | 25 / 25 / 0 | 5 (76.0%) | -0.003 / +0.000 | +0.197 | 0.188 / 0.208 | 4.0% / 0.0% / 0.0% | 0.000 / -0.009 |
| `korunan_veya_buyuyen_tepkiler` | 4 | 25 / 25 / 0 | 5 (76.0%) | -0.017 / +0.000 | +0.265 | 0.208 / 0.490 | 12.0% / 0.0% / 0.0% | -0.197 / 0.106 |
| `korunan_veya_buyuyen_tepkiler` | 8 | 25 / 25 / 0 | 5 (76.0%) | -0.149 / +0.000 | -0.104 | 0.617 / 0.617 | 16.0% / 12.0% / 0.0% | -0.376 / 0.211 |
| `korunan_veya_buyuyen_tepkiler` | 10 | 25 / 25 / 0 | 5 (76.0%) | -0.116 / +0.000 | -0.076 | 0.626 / 0.638 | 20.0% / 16.0% / 0.0% | -0.217 / 0.104 |
| `korunan_veya_buyuyen_tepkiler` | 12 | 25 / 25 / 0 | 5 (76.0%) | -0.228 / +0.000 | -0.428 | 0.638 / 0.752 | 20.0% / 20.0% / 0.0% | 0.000 / 0.000 |
| `korunan_veya_buyuyen_tepkiler` | 16 | 25 / 25 / 0 | 5 (76.0%) | -0.457 / -0.188 | -0.598 | 0.652 / 0.869 | 20.0% / 32.0% / 0.0% | -0.149 / -1.147 |
| `kuculen_tepkiler` | 1 | 8 / 8 / 0 | 1 (100.0%) | -0.206 / +0.000 | -0.206 | 0.000 / 0.328 | 0.0% / 12.5% / 0.0% | 0.000 / 0.000 |
| `kuculen_tepkiler` | 4 | 8 / 8 / 0 | 1 (100.0%) | -0.899 / -0.961 | -0.899 | 0.000 / 1.442 | 0.0% / 50.0% / 0.0% | -0.323 / -1.327 |
| `kuculen_tepkiler` | 8 | 8 / 8 / 0 | 1 (100.0%) | -1.661 / -1.616 | -1.661 | 0.000 / 2.263 | 0.0% / 100.0% / 0.0% | -1.616 / -1.990 |
| `kuculen_tepkiler` | 10 | 8 / 8 / 0 | 1 (100.0%) | -1.992 / -1.914 | -1.992 | 0.000 / 2.292 | 0.0% / 100.0% / 0.0% | -1.616 / -1.990 |
| `kuculen_tepkiler` | 12 | 8 / 8 / 0 | 1 (100.0%) | -2.445 / -2.263 | -2.445 | 0.000 / 2.586 | 0.0% / 100.0% / 0.0% | -1.940 / -3.317 |
| `kuculen_tepkiler` | 16 | 8 / 8 / 0 | 1 (100.0%) | -3.365 / -3.556 | -3.365 | 0.000 / 4.311 | 0.0% / 100.0% / 0.0% | -3.556 / -3.648 |

- **KARŞI ÖRNEK:** GSRAY (2026-03-16 18:00, kova=korunan_veya_buyuyen_tepkiler): 8x4H korunan=-1.76 ATR (MFE=0.44 / MAE=1.98 ATR) · GSRAY (2026-09-14 18:00, kova=kuculen_tepkiler): 8x4H korunan=-0.97 ATR (MFE=0.32 / MAE=1.94 ATR)
- **SINIR:** En az iki tamamlanmış tepki şartı örneklem hacmini doğal olarak daraltır.
- **SONUÇ (`örnek yetersiz`):** Yalnız tek kovada (korunan_veya_buyuyen_tepkiler, n=25) yeterli örnek var; karşılaştırmalı ayrım kurulamadı.

## STB-BHV-C06 — Güçlü ilk tepkiye rağmen hızlı yeniden test kazancı geri verdiriyor mu?

- **TANIM:** Önceki tamamlanmış tepkisi >=1.2 ATR olan güçlü desteklerde erken (<=10g) vs geç (>10g) yeniden testlerin sonucu.
- **VERİ:** Toplam checkpoint/olay `n=64`, 8×4H tam ufuk `n=64`, sağdan sansürlü `n=0`, ATR geçerli `n=64`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `gec_yeniden_test` (8×4H n=53, med=-0.134 ATR, ort=-0.056 ATR, MFE_med=0.441, MAE_med=0.626, top1_sembol=45.3%) vs `hizli_yeniden_test` (8×4H n=11, med=1.781 ATR, ort=2.190 ATR, MFE_med=2.055, MAE_med=0.150, top1_sembol=63.6%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `gec_yeniden_test` | 1 | 53 / 53 / 0 | 9 (45.3%) | -0.021 / +0.000 | +0.006 | 0.159 / 0.197 | 1.9% / 0.0% / 0.0% | -0.038 / 0.000 |
| `gec_yeniden_test` | 4 | 53 / 53 / 0 | 9 (45.3%) | +0.053 / +0.000 | +0.180 | 0.313 / 0.425 | 11.3% / 3.8% / 0.0% | -0.188 / 0.000 |
| `gec_yeniden_test` | 8 | 53 / 53 / 0 | 9 (45.3%) | -0.056 / -0.134 | -0.004 | 0.441 / 0.626 | 20.8% / 18.9% / 0.0% | -0.185 / -0.118 |
| `gec_yeniden_test` | 10 | 53 / 53 / 0 | 9 (45.3%) | -0.147 / +0.000 | -0.131 | 0.448 / 0.662 | 20.8% / 30.2% / 0.0% | 0.000 / -0.306 |
| `gec_yeniden_test` | 12 | 53 / 53 / 0 | 9 (45.3%) | -0.205 / +0.000 | -0.120 | 0.564 / 0.787 | 20.8% / 37.7% / 0.0% | 0.000 / -0.684 |
| `gec_yeniden_test` | 16 | 53 / 53 / 0 | 9 (45.3%) | -0.418 / -0.394 | -0.201 | 0.626 / 0.993 | 22.6% / 47.2% / 0.0% | 0.000 / -1.137 |
| `hizli_yeniden_test` | 1 | 11 / 11 / 0 | 3 (63.6%) | +0.075 / +0.000 | +0.027 | 0.155 / 0.150 | 9.1% / 0.0% / 0.0% | 0.000 / 0.075 |
| `hizli_yeniden_test` | 4 | 11 / 11 / 0 | 3 (63.6%) | +0.875 / +0.827 | +0.448 | 1.353 / 0.150 | 63.6% / 9.1% / 0.0% | 0.443 / 0.827 |
| `hizli_yeniden_test` | 8 | 11 / 11 / 0 | 3 (63.6%) | +2.190 / +1.781 | +1.402 | 2.055 / 0.150 | 90.9% / 9.1% / 0.0% | 0.980 / 3.158 |
| `hizli_yeniden_test` | 10 | 11 / 11 / 0 | 3 (63.6%) | +2.925 / +2.877 | +1.738 | 3.098 / 0.150 | 90.9% / 9.1% / 0.0% | 1.302 / 4.962 |
| `hizli_yeniden_test` | 12 | 11 / 11 / 0 | 3 (63.6%) | +2.910 / +3.025 | +1.634 | 5.459 / 0.150 | 90.9% / 9.1% / 0.0% | 1.165 / 4.962 |
| `hizli_yeniden_test` | 16 | 11 / 11 / 0 | 3 (63.6%) | +2.759 / +2.089 | +1.709 | 6.787 / 0.150 | 90.9% / 9.1% / 0.0% | 1.781 / 3.383 |

- **KARŞI ÖRNEK:** GLYHO (2025-10-03 13:30, kova=gec_yeniden_test): 8x4H korunan=+2.29 ATR (MFE=2.29 / MAE=0.58 ATR) · EBEBK (2026-03-06 13:30, kova=hizli_yeniden_test): 8x4H korunan=-0.14 ATR (MFE=0.04 / MAE=1.39 ATR)
- **SINIR:** Destek yaşı bilinen epizotlarla sınırlıdır.
- **SONUÇ (`örnek yetersiz`):** Yalnız tek kovada (gec_yeniden_test, n=53) yeterli örnek var; karşılaştırmalı ayrım kurulamadı.

## STB-BHV-D01 — Küçük ve derin aşağı kırılmalarda geri alım ihtimali farklı mı?

- **TANIM:** Destek altındaki 4H kapanışlarında o ana kadar gözlenen azami ihlal derinliğine göre 24x4H geri alım oranı ve ileri getiri.
- **VERİ:** Toplam checkpoint/olay `n=21892`, 8×4H tam ufuk `n=21498`, sağdan sansürlü `n=394`, ATR geçerli `n=21498`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `derin_kirilma_1.2+_ATR` (8×4H n=14252, med=-0.028 ATR, ort=0.003 ATR, MFE_med=0.629, MAE_med=0.566, top1_sembol=2.7%) vs `kucuk_kirilma_0_0.5_ATR` (8×4H n=2645, med=-0.170 ATR, ort=-0.086 ATR, MFE_med=0.523, MAE_med=0.656, top1_sembol=2.0%) vs `orta_kirilma_0.5_1.2_ATR` (8×4H n=4601, med=-0.054 ATR, ort=0.009 ATR, MFE_med=0.621, MAE_med=0.552, top1_sembol=2.3%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `derin_kirilma_1.2+_ATR` | 1 | 14431 / 14431 / 43 | 100 (2.7%) | -0.004 / +0.000 | +0.005 | 0.137 / 0.135 | 3.5% / 2.8% / 0.0% | 0.000 / 0.000 |
| `derin_kirilma_1.2+_ATR` | 4 | 14325 / 14325 / 149 | 100 (2.7%) | -0.005 / -0.033 | +0.031 | 0.409 / 0.376 | 17.3% / 13.7% / 0.1% | 0.000 / -0.099 |
| `derin_kirilma_1.2+_ATR` | 8 | 14252 / 14252 / 222 | 100 (2.7%) | +0.003 / -0.028 | +0.061 | 0.629 / 0.566 | 31.0% / 26.0% / 0.2% | 0.057 / -0.127 |
| `derin_kirilma_1.2+_ATR` | 10 | 14230 / 14230 / 244 | 100 (2.7%) | +0.011 / -0.013 | +0.080 | 0.725 / 0.634 | 35.1% / 30.1% / 0.2% | 0.091 / -0.144 |
| `derin_kirilma_1.2+_ATR` | 12 | 14213 / 14213 / 261 | 100 (2.7%) | +0.014 / +0.000 | +0.094 | 0.808 / 0.705 | 38.4% / 33.6% / 0.2% | 0.136 / -0.183 |
| `derin_kirilma_1.2+_ATR` | 16 | 14187 / 14187 / 287 | 100 (2.7%) | +0.011 / -0.026 | +0.118 | 0.944 / 0.825 | 42.8% / 38.0% / 0.2% | 0.171 / -0.253 |
| `kucuk_kirilma_0_0.5_ATR` | 1 | 2682 / 2682 / 5 | 100 (2.0%) | -0.035 / -0.026 | -0.036 | 0.112 / 0.140 | 2.4% / 2.4% / 0.0% | -0.030 / -0.022 |
| `kucuk_kirilma_0_0.5_ATR` | 4 | 2663 / 2663 / 24 | 100 (2.0%) | -0.075 / -0.102 | -0.080 | 0.341 / 0.414 | 12.2% / 13.7% / 0.1% | -0.070 / -0.129 |
| `kucuk_kirilma_0_0.5_ATR` | 8 | 2645 / 2645 / 42 | 100 (2.0%) | -0.086 / -0.170 | -0.070 | 0.523 / 0.656 | 25.1% / 28.5% / 0.1% | -0.159 / -0.183 |
| `kucuk_kirilma_0_0.5_ATR` | 10 | 2631 / 2631 / 56 | 100 (2.0%) | -0.088 / -0.173 | -0.065 | 0.593 / 0.737 | 29.0% / 33.8% / 0.1% | -0.186 / -0.166 |
| `kucuk_kirilma_0_0.5_ATR` | 12 | 2618 / 2618 / 69 | 100 (2.0%) | -0.091 / -0.144 | -0.060 | 0.666 / 0.810 | 31.7% / 37.3% / 0.1% | -0.112 / -0.172 |
| `kucuk_kirilma_0_0.5_ATR` | 16 | 2595 / 2595 / 92 | 100 (2.0%) | -0.020 / -0.094 | +0.008 | 0.800 / 0.907 | 36.3% / 41.1% / 0.1% | 0.027 / -0.194 |
| `orta_kirilma_0.5_1.2_ATR` | 1 | 4708 / 4708 / 23 | 100 (2.3%) | -0.012 / -0.017 | -0.013 | 0.127 / 0.144 | 3.3% / 2.1% / 0.1% | -0.017 / -0.017 |
| `orta_kirilma_0.5_1.2_ATR` | 4 | 4644 / 4644 / 87 | 100 (2.3%) | -0.016 / -0.047 | -0.015 | 0.389 / 0.383 | 16.2% / 13.1% / 0.2% | 0.000 / -0.099 |
| `orta_kirilma_0.5_1.2_ATR` | 8 | 4601 / 4601 / 130 | 100 (2.3%) | +0.009 / -0.054 | +0.019 | 0.621 / 0.552 | 29.1% / 25.2% / 0.3% | 0.010 / -0.131 |
| `orta_kirilma_0.5_1.2_ATR` | 10 | 4574 / 4574 / 157 | 100 (2.3%) | +0.030 / +0.000 | +0.034 | 0.724 / 0.623 | 33.9% / 29.9% / 0.3% | 0.071 / -0.107 |
| `orta_kirilma_0.5_1.2_ATR` | 12 | 4556 / 4556 / 175 | 100 (2.3%) | +0.058 / +0.000 | +0.058 | 0.814 / 0.689 | 37.8% / 32.9% / 0.3% | 0.110 / -0.103 |
| `orta_kirilma_0.5_1.2_ATR` | 16 | 4533 / 4533 / 198 | 100 (2.3%) | +0.115 / +0.054 | +0.117 | 0.953 / 0.781 | 42.8% / 36.5% / 0.4% | 0.218 / -0.101 |

- **KARŞI ÖRNEK:** AGROT (2025-11-14 13:30, kova=orta_kirilma_0.5_1.2_ATR): 8x4H korunan=+5.35 ATR (MFE=5.83 / MAE=0.12 ATR) · KARSN (2026-08-31 18:00, kova=derin_kirilma_1.2+_ATR): 8x4H korunan=+7.69 ATR (MFE=7.69 / MAE=0.33 ATR) · KONTR (2026-04-08 18:00, kova=kucuk_kirilma_0_0.5_ATR): 8x4H korunan=+5.80 ATR (MFE=6.66 / MAE=0.13 ATR)
- **SINIR:** Geri almayan ve sansürlü olaylar tabanda dahildir; yalnız başarılı geri alımlar seçilmemiştir.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.142 ATR, MAE farkı 0.104 ATR düzeyinde ayrıştı.

## STB-BHV-D02 — Geri alımdan sonra küçük ve derin kırılmaların kalan tepkisi farklı mı?

- **TANIM:** Sabit desteğin 4H kapanışla geri alındığı ilk anda, geride bırakılan kırılma derinliğine göre geri alım SONRASI kalan hareket.
- **VERİ:** Toplam checkpoint/olay `n=1150`, 8×4H tam ufuk `n=1141`, sağdan sansürlü `n=9`, ATR geçerli `n=1141`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `derin_kirilmadan_geri_alim` (8×4H n=257, med=0.000 ATR, ort=0.099 ATR, MFE_med=0.750, MAE_med=0.634, top1_sembol=3.1%) vs `kucuk_kirilmadan_geri_alim` (8×4H n=509, med=0.000 ATR, ort=0.055 ATR, MFE_med=0.642, MAE_med=0.529, top1_sembol=2.3%) vs `orta_kirilmadan_geri_alim` (8×4H n=375, med=0.000 ATR, ort=0.114 ATR, MFE_med=0.705, MAE_med=0.552, top1_sembol=2.6%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `derin_kirilmadan_geri_alim` | 1 | 257 / 257 / 0 | 95 (3.1%) | +0.001 / +0.000 | +0.016 | 0.131 / 0.157 | 3.5% / 1.2% / 0.0% | 0.000 / 0.000 |
| `derin_kirilmadan_geri_alim` | 4 | 257 / 257 / 0 | 95 (3.1%) | +0.050 / +0.000 | +0.107 | 0.570 / 0.431 | 26.5% / 11.3% / 0.4% | 0.111 / -0.140 |
| `derin_kirilmadan_geri_alim` | 8 | 257 / 257 / 0 | 95 (3.1%) | +0.099 / +0.000 | +0.142 | 0.750 / 0.634 | 39.7% / 25.7% / 0.4% | 0.103 / -0.066 |
| `derin_kirilmadan_geri_alim` | 10 | 257 / 257 / 0 | 95 (3.1%) | +0.065 / +0.066 | +0.110 | 0.869 / 0.750 | 43.6% / 30.7% / 0.4% | 0.040 / 0.085 |
| `derin_kirilmadan_geri_alim` | 12 | 257 / 257 / 0 | 95 (3.1%) | +0.155 / +0.089 | +0.194 | 1.047 / 0.828 | 49.0% / 34.6% / 0.4% | 0.214 / 0.028 |
| `derin_kirilmadan_geri_alim` | 16 | 257 / 257 / 0 | 95 (3.1%) | +0.070 / +0.035 | +0.193 | 1.170 / 0.980 | 52.1% / 37.4% / 0.4% | 0.170 / -0.134 |
| `kucuk_kirilmadan_geri_alim` | 1 | 515 / 515 / 0 | 99 (2.3%) | -0.009 / +0.000 | -0.006 | 0.133 / 0.150 | 2.5% / 2.5% / 0.0% | 0.000 / -0.017 |
| `kucuk_kirilmadan_geri_alim` | 4 | 515 / 515 / 0 | 99 (2.3%) | -0.000 / -0.021 | +0.010 | 0.416 / 0.386 | 16.7% / 11.1% / 0.0% | 0.000 / -0.053 |
| `kucuk_kirilmadan_geri_alim` | 8 | 509 / 509 / 6 | 99 (2.3%) | +0.055 / +0.000 | +0.071 | 0.642 / 0.529 | 33.4% / 25.9% / 0.0% | 0.068 / -0.102 |
| `kucuk_kirilmadan_geri_alim` | 10 | 509 / 509 / 6 | 99 (2.3%) | +0.038 / -0.026 | +0.051 | 0.737 / 0.594 | 37.7% / 30.1% / 0.0% | 0.089 / -0.135 |
| `kucuk_kirilmadan_geri_alim` | 12 | 509 / 509 / 6 | 99 (2.3%) | +0.062 / +0.000 | +0.100 | 0.819 / 0.655 | 40.5% / 35.0% / 0.0% | 0.141 / -0.099 |
| `kucuk_kirilmadan_geri_alim` | 16 | 508 / 508 / 7 | 99 (2.3%) | +0.108 / +0.000 | +0.130 | 1.013 / 0.783 | 46.1% / 38.2% / 0.2% | 0.230 / -0.146 |
| `orta_kirilmadan_geri_alim` | 1 | 378 / 378 / 0 | 96 (2.6%) | +0.019 / +0.000 | -0.004 | 0.134 / 0.141 | 2.9% / 2.9% / 0.0% | 0.000 / 0.000 |
| `orta_kirilmadan_geri_alim` | 4 | 377 / 377 / 1 | 96 (2.6%) | +0.046 / +0.000 | +0.016 | 0.536 / 0.382 | 20.4% / 11.4% / 0.3% | -0.009 / 0.000 |
| `orta_kirilmadan_geri_alim` | 8 | 375 / 375 / 3 | 96 (2.6%) | +0.114 / +0.000 | +0.061 | 0.705 / 0.552 | 33.3% / 25.9% / 0.3% | -0.154 / 0.056 |
| `orta_kirilmadan_geri_alim` | 10 | 375 / 375 / 3 | 96 (2.6%) | +0.059 / -0.118 | -0.009 | 0.781 / 0.669 | 38.9% / 31.2% / 0.3% | -0.192 / -0.104 |
| `orta_kirilmadan_geri_alim` | 12 | 375 / 375 / 3 | 96 (2.6%) | +0.084 / -0.070 | +0.007 | 0.873 / 0.779 | 42.9% / 36.0% / 0.3% | 0.000 / -0.155 |
| `orta_kirilmadan_geri_alim` | 16 | 374 / 374 / 4 | 96 (2.6%) | +0.099 / -0.084 | +0.061 | 1.045 / 0.948 | 47.1% / 42.0% / 0.3% | -0.036 / -0.154 |

- **KARŞI ÖRNEK:** BJKAS (2025-12-18 18:00, kova=derin_kirilmadan_geri_alim): 8x4H korunan=-6.49 ATR (MFE=0.00 / MAE=6.69 ATR) · DMSAS (2026-09-14 18:00, kova=kucuk_kirilmadan_geri_alim): 8x4H korunan=-4.70 ATR (MFE=0.00 / MAE=4.93 ATR) · GRTHO (2025-11-03 13:30, kova=orta_kirilmadan_geri_alim): 8x4H korunan=-3.99 ATR (MFE=0.06 / MAE=4.23 ATR)
- **SINIR:** Dipten desteğe kadar harcanan yol bu ölçüme katılmaz; yalnız geri alım kapanışından sonraki hareket ölçülür.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.000 ATR) ve MAE farkı (0.104 ATR) sınırlı kaldı.

## STB-BHV-D03 — Aynı derinliğe tek mumda ve yavaş düşerek gelmek farklı mı?

- **TANIM:** Benzer ihlal derinliğinde (0.5-1.8 ATR) ilk kırılma mumunda >=0.6 ATR sert düşüşle inenler ile kademeli inenlerin karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=8225`, 8×4H tam ufuk `n=8005`, sağdan sansürlü `n=220`, ATR geçerli `n=8005`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `kademeli_suzulen_kirilma` (8×4H n=5066, med=-0.018 ATR, ort=0.018 ATR, MFE_med=0.631, MAE_med=0.525, top1_sembol=2.4%) vs `tek_mumda_sert_kirilma` (8×4H n=2939, med=-0.055 ATR, ort=-0.007 ATR, MFE_med=0.636, MAE_med=0.595, top1_sembol=4.3%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `kademeli_suzulen_kirilma` | 1 | 5186 / 5186 / 22 | 100 (2.4%) | -0.008 / -0.014 | -0.006 | 0.127 / 0.143 | 3.2% / 1.6% / 0.1% | -0.014 / -0.013 |
| `kademeli_suzulen_kirilma` | 4 | 5127 / 5127 / 81 | 100 (2.4%) | -0.007 / -0.030 | -0.005 | 0.391 / 0.363 | 16.0% / 11.1% / 0.2% | 0.000 / -0.048 |
| `kademeli_suzulen_kirilma` | 8 | 5066 / 5066 / 142 | 100 (2.4%) | +0.018 / -0.018 | +0.019 | 0.631 / 0.525 | 29.7% / 23.0% / 0.3% | 0.000 / -0.056 |
| `kademeli_suzulen_kirilma` | 10 | 5037 / 5037 / 171 | 100 (2.4%) | +0.045 / +0.019 | +0.056 | 0.742 / 0.597 | 34.8% / 27.3% / 0.3% | 0.056 / 0.000 |
| `kademeli_suzulen_kirilma` | 12 | 5021 / 5021 / 187 | 100 (2.4%) | +0.073 / +0.053 | +0.102 | 0.833 / 0.656 | 39.0% / 30.4% / 0.3% | 0.113 / 0.000 |
| `kademeli_suzulen_kirilma` | 16 | 5006 / 5006 / 202 | 100 (2.4%) | +0.112 / +0.091 | +0.169 | 0.978 / 0.761 | 44.4% / 34.8% / 0.4% | 0.165 / 0.000 |
| `tek_mumda_sert_kirilma` | 1 | 2997 / 2997 / 20 | 99 (4.3%) | -0.006 / +0.000 | -0.008 | 0.145 / 0.140 | 3.5% / 3.4% / 0.1% | 0.000 / 0.000 |
| `tek_mumda_sert_kirilma` | 4 | 2946 / 2946 / 71 | 99 (4.3%) | -0.006 / -0.019 | +0.021 | 0.431 / 0.394 | 16.9% / 15.7% / 0.2% | 0.047 / -0.085 |
| `tek_mumda_sert_kirilma` | 8 | 2939 / 2939 / 78 | 99 (4.3%) | -0.007 / -0.055 | +0.050 | 0.636 / 0.595 | 29.7% / 29.0% / 0.2% | 0.000 / -0.126 |
| `tek_mumda_sert_kirilma` | 10 | 2933 / 2933 / 84 | 99 (4.3%) | -0.001 / -0.062 | +0.049 | 0.719 / 0.672 | 33.7% / 33.7% / 0.3% | 0.011 / -0.121 |
| `tek_mumda_sert_kirilma` | 12 | 2926 / 2926 / 91 | 99 (4.3%) | +0.002 / -0.038 | +0.048 | 0.796 / 0.747 | 37.1% / 37.2% / 0.3% | 0.027 / -0.107 |
| `tek_mumda_sert_kirilma` | 16 | 2916 / 2916 / 101 | 99 (4.3%) | +0.014 / -0.044 | +0.037 | 0.918 / 0.868 | 41.4% / 40.9% / 0.3% | 0.117 / -0.155 |

- **KARŞI ÖRNEK:** AKCNS (2026-05-20 17:30, kova=tek_mumda_sert_kirilma): 8x4H korunan=+5.14 ATR (MFE=6.24 / MAE=0.47 ATR) · CWENE (2026-08-03 17:30, kova=kademeli_suzulen_kirilma): 8x4H korunan=+5.61 ATR (MFE=6.61 / MAE=0.08 ATR)
- **SINIR:** Derinlik bandı sabit tutulmuştur.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.037 ATR) ve MAE farkı (0.070 ATR) sınırlı kaldı.

## STB-BHV-D04 — Ana seviye ile native tolerans sınırının kaybı geri dönüşü ayırıyor mu?

- **TANIM:** Yalnız ana destek altında kalan (BREACHED) durumlar ile 0.35 ATR native floor altına da inenlerin geri alım ve getiri farkı.
- **VERİ:** Toplam checkpoint/olay `n=21892`, 8×4H tam ufuk `n=21498`, sağdan sansürlü `n=394`, ATR geçerli `n=21498`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `floor_alti_ihlal` (8×4H n=18604, med=-0.029 ATR, ort=0.008 ATR, MFE_med=0.627, MAE_med=0.562, top1_sembol=2.4%) vs `yalniz_ana_destek_alti` (8×4H n=2894, med=-0.185 ATR, ort=-0.098 ATR, MFE_med=0.534, MAE_med=0.657, top1_sembol=1.7%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `floor_alti_ihlal` | 1 | 18864 / 18864 / 65 | 100 (2.4%) | -0.006 / +0.000 | +0.002 | 0.134 / 0.136 | 3.5% / 2.6% / 0.1% | 0.000 / 0.000 |
| `floor_alti_ihlal` | 4 | 18708 / 18708 / 221 | 100 (2.4%) | -0.006 / -0.037 | +0.025 | 0.406 / 0.377 | 17.1% / 13.5% / 0.1% | 0.000 / -0.097 |
| `floor_alti_ihlal` | 8 | 18604 / 18604 / 325 | 100 (2.4%) | +0.008 / -0.029 | +0.059 | 0.627 / 0.562 | 30.6% / 25.8% / 0.2% | 0.049 / -0.117 |
| `floor_alti_ihlal` | 10 | 18554 / 18554 / 375 | 100 (2.4%) | +0.019 / +0.000 | +0.080 | 0.726 / 0.630 | 34.9% / 29.9% / 0.2% | 0.085 / -0.119 |
| `floor_alti_ihlal` | 12 | 18521 / 18521 / 408 | 100 (2.4%) | +0.028 / +0.000 | +0.100 | 0.813 / 0.697 | 38.4% / 33.3% / 0.2% | 0.133 / -0.152 |
| `floor_alti_ihlal` | 16 | 18473 / 18473 / 456 | 100 (2.4%) | +0.039 / +0.000 | +0.134 | 0.952 / 0.811 | 42.9% / 37.5% / 0.3% | 0.193 / -0.209 |
| `yalniz_ana_destek_alti` | 1 | 2957 / 2957 / 6 | 100 (1.7%) | -0.034 / -0.027 | -0.036 | 0.117 / 0.146 | 2.3% / 2.3% / 0.0% | -0.030 / -0.024 |
| `yalniz_ana_destek_alti` | 4 | 2924 / 2924 / 39 | 100 (1.7%) | -0.080 / -0.106 | -0.088 | 0.344 / 0.420 | 12.6% / 14.0% / 0.0% | -0.061 / -0.145 |
| `yalniz_ana_destek_alti` | 8 | 2894 / 2894 / 69 | 100 (1.7%) | -0.098 / -0.185 | -0.088 | 0.534 / 0.657 | 25.0% / 28.5% / 0.1% | -0.161 / -0.206 |
| `yalniz_ana_destek_alti` | 10 | 2881 / 2881 / 82 | 100 (1.7%) | -0.100 / -0.185 | -0.087 | 0.599 / 0.750 | 29.0% / 34.1% / 0.1% | -0.182 / -0.189 |
| `yalniz_ana_destek_alti` | 12 | 2866 / 2866 / 97 | 100 (1.7%) | -0.105 / -0.162 | -0.091 | 0.667 / 0.818 | 31.6% / 37.7% / 0.1% | -0.132 / -0.199 |
| `yalniz_ana_destek_alti` | 16 | 2842 / 2842 / 121 | 100 (1.7%) | -0.034 / -0.115 | -0.020 | 0.787 / 0.912 | 36.0% / 41.5% / 0.1% | 0.000 / -0.205 |

- **KARŞI ÖRNEK:** KARSN (2026-08-31 18:00, kova=floor_alti_ihlal): 8x4H korunan=+7.69 ATR (MFE=7.69 / MAE=0.33 ATR) · KONTR (2026-04-08 18:00, kova=yalniz_ana_destek_alti): 8x4H korunan=+5.80 ATR (MFE=6.66 / MAE=0.13 ATR)
- **SINIR:** Floor grafikte çizilmez; burada yalnız native motorun iç durumu olarak test edilmektedir.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.156 ATR, MAE farkı 0.095 ATR düzeyinde ayrıştı.

## STB-BHV-D05 — Gap ve seans içi kırılma benzer derinlikte farklı mı?

- **TANIM:** Destek altına ilk geçişte >=0.15 ATR aşağı boşluklu açılışla kırılanlar ile seans içi normal kırılanların karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=1722`, 8×4H tam ufuk `n=1672`, sağdan sansürlü `n=50`, ATR geçerli `n=1672`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `bosluklu_gap_kirilma` (8×4H n=202, med=0.050 ATR, ort=-0.062 ATR, MFE_med=0.744, MAE_med=0.512, top1_sembol=8.2%) vs `seans_ici_normal_kirilma` (8×4H n=1470, med=-0.146 ATR, ort=-0.061 ATR, MFE_med=0.583, MAE_med=0.690, top1_sembol=1.7%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bosluklu_gap_kirilma` | 1 | 232 / 232 / 0 | 88 (8.2%) | +0.060 / +0.000 | +0.059 | 0.173 / 0.124 | 5.2% / 2.2% / 0.0% | 0.059 / 0.000 |
| `bosluklu_gap_kirilma` | 4 | 204 / 204 / 28 | 88 (8.2%) | +0.040 / +0.088 | +0.049 | 0.576 / 0.366 | 22.1% / 15.7% / 0.5% | 0.197 / 0.000 |
| `bosluklu_gap_kirilma` | 8 | 202 / 202 / 30 | 88 (8.2%) | -0.062 / +0.050 | -0.097 | 0.744 / 0.512 | 32.7% / 23.8% / 0.5% | 0.180 / -0.174 |
| `bosluklu_gap_kirilma` | 10 | 202 / 202 / 30 | 88 (8.2%) | -0.117 / -0.057 | -0.208 | 0.828 / 0.648 | 38.1% / 30.2% / 0.5% | 0.040 / -0.239 |
| `bosluklu_gap_kirilma` | 12 | 201 / 201 / 31 | 88 (8.2%) | -0.239 / -0.096 | -0.324 | 0.867 / 0.712 | 40.3% / 34.8% / 0.5% | 0.000 / -0.167 |
| `bosluklu_gap_kirilma` | 16 | 200 / 200 / 32 | 88 (8.2%) | -0.306 / -0.147 | -0.391 | 0.959 / 0.891 | 44.0% / 41.5% / 0.5% | -0.098 / -0.367 |
| `seans_ici_normal_kirilma` | 1 | 1488 / 1488 / 2 | 100 (1.7%) | -0.030 / -0.026 | -0.033 | 0.114 / 0.141 | 3.1% / 3.2% / 0.0% | -0.024 / -0.031 |
| `seans_ici_normal_kirilma` | 4 | 1480 / 1480 / 10 | 100 (1.7%) | -0.077 / -0.102 | -0.084 | 0.366 / 0.456 | 14.1% / 18.2% / 0.1% | -0.064 / -0.126 |
| `seans_ici_normal_kirilma` | 8 | 1470 / 1470 / 20 | 100 (1.7%) | -0.061 / -0.146 | -0.062 | 0.583 / 0.690 | 27.9% / 31.3% / 0.2% | -0.102 / -0.189 |
| `seans_ici_normal_kirilma` | 10 | 1466 / 1466 / 24 | 100 (1.7%) | -0.095 / -0.166 | -0.088 | 0.646 / 0.795 | 31.6% / 37.2% / 0.3% | -0.138 / -0.207 |
| `seans_ici_normal_kirilma` | 12 | 1459 / 1459 / 31 | 100 (1.7%) | -0.108 / -0.151 | -0.102 | 0.733 / 0.898 | 35.2% / 41.0% / 0.3% | -0.091 / -0.217 |
| `seans_ici_normal_kirilma` | 16 | 1452 / 1452 / 38 | 100 (1.7%) | -0.039 / -0.113 | -0.021 | 0.887 / 0.967 | 38.6% / 43.8% / 0.3% | 0.015 / -0.182 |

- **KARŞI ÖRNEK:** KONTR (2026-04-08 18:00, kova=seans_ici_normal_kirilma): 8x4H korunan=+5.80 ATR (MFE=6.66 / MAE=0.13 ATR) · ESEN (2025-10-24 13:30, kova=bosluklu_gap_kirilma): 8x4H korunan=-4.30 ATR (MFE=0.02 / MAE=4.35 ATR)
- **SINIR:** 4H kova açılışı BIST seans/kova sınırına göredir.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.196 ATR, MAE farkı 0.178 ATR düzeyinde ayrıştı.

## STB-BHV-D06 — Geri alıma kadar hareketin çoğu zaten tüketiliyor mu?

- **TANIM:** İhlal dibinden geri alım kapanışına kadar harcanan yol >=1.2 ATR olanlar ile <1.2 ATR olanların geri alım sonrası kalan getirisi.
- **VERİ:** Toplam checkpoint/olay `n=1150`, 8×4H tam ufuk `n=1141`, sağdan sansürlü `n=9`, ATR geçerli `n=1141`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `geri_alima_kadar_buyuk_yol_tuketildi` (8×4H n=394, med=0.029 ATR, ort=0.158 ATR, MFE_med=0.813, MAE_med=0.611, top1_sembol=2.5%) vs `geri_alima_yakin_donduruldu` (8×4H n=747, med=0.000 ATR, ort=0.045 ATR, MFE_med=0.648, MAE_med=0.539, top1_sembol=1.8%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `geri_alima_kadar_buyuk_yol_tuketildi` | 1 | 395 / 395 / 0 | 99 (2.5%) | +0.000 / +0.000 | +0.032 | 0.131 / 0.154 | 3.3% / 2.8% / 0.0% | 0.000 / 0.000 |
| `geri_alima_kadar_buyuk_yol_tuketildi` | 4 | 395 / 395 / 0 | 99 (2.5%) | +0.083 / +0.000 | +0.122 | 0.610 / 0.427 | 28.9% / 12.2% / 0.5% | 0.122 / -0.133 |
| `geri_alima_kadar_buyuk_yol_tuketildi` | 8 | 394 / 394 / 1 | 99 (2.5%) | +0.158 / +0.029 | +0.192 | 0.813 / 0.611 | 42.4% / 25.1% / 0.5% | 0.150 / -0.066 |
| `geri_alima_kadar_buyuk_yol_tuketildi` | 10 | 394 / 394 / 1 | 99 (2.5%) | +0.122 / +0.056 | +0.160 | 0.962 / 0.723 | 46.7% / 29.7% / 0.5% | 0.082 / 0.014 |
| `geri_alima_kadar_buyuk_yol_tuketildi` | 12 | 394 / 394 / 1 | 99 (2.5%) | +0.195 / +0.097 | +0.202 | 1.086 / 0.818 | 50.8% / 34.5% / 0.5% | 0.267 / -0.034 |
| `geri_alima_kadar_buyuk_yol_tuketildi` | 16 | 394 / 394 / 1 | 99 (2.5%) | +0.163 / +0.006 | +0.196 | 1.248 / 0.942 | 53.5% / 37.1% / 0.5% | 0.187 / -0.216 |
| `geri_alima_yakin_donduruldu` | 1 | 755 / 755 / 0 | 100 (1.8%) | +0.004 / +0.000 | +0.002 | 0.133 / 0.150 | 2.6% / 2.1% / 0.0% | 0.000 / 0.000 |
| `geri_alima_yakin_donduruldu` | 4 | 754 / 754 / 1 | 100 (1.8%) | -0.004 / -0.015 | +0.000 | 0.446 / 0.380 | 15.5% / 10.7% / 0.0% | -0.021 / 0.000 |
| `geri_alima_yakin_donduruldu` | 8 | 747 / 747 / 8 | 100 (1.8%) | +0.045 / +0.000 | +0.047 | 0.648 / 0.539 | 30.8% / 26.2% / 0.0% | 0.000 / 0.000 |
| `geri_alima_yakin_donduruldu` | 10 | 747 / 747 / 8 | 100 (1.8%) | +0.013 / -0.077 | +0.010 | 0.714 / 0.623 | 35.6% / 31.1% / 0.0% | -0.023 / -0.114 |
| `geri_alima_yakin_donduruldu` | 12 | 747 / 747 / 8 | 100 (1.8%) | +0.035 / -0.045 | +0.054 | 0.810 / 0.697 | 39.2% / 35.6% / 0.0% | 0.021 / -0.123 |
| `geri_alima_yakin_donduruldu` | 16 | 745 / 745 / 10 | 100 (1.8%) | +0.061 / +0.000 | +0.069 | 0.989 / 0.854 | 44.7% / 40.4% / 0.1% | 0.104 / -0.110 |

- **KARŞI ÖRNEK:** BJKAS (2025-12-18 18:00, kova=geri_alima_kadar_buyuk_yol_tuketildi): 8x4H korunan=-6.49 ATR (MFE=0.00 / MAE=6.69 ATR) · DMSAS (2026-09-14 18:00, kova=geri_alima_yakin_donduruldu): 8x4H korunan=-4.70 ATR (MFE=0.00 / MAE=4.93 ATR)
- **SINIR:** Harcanan yol ile kalan ileri getiri birbirine karıştırılmadan ayrı tutulmuştur.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.029 ATR) ve MAE farkı (0.071 ATR) sınırlı kaldı.

## STB-BHV-E01 — Destek sabitken ilk deneme ne sıklıkla üstte kapanışa dönüşüyor?

- **TANIM:** Sabit destek altındayken desteğe uzanan denemelerin üstte kapanışla sonuçlananları vs fitil/red kalanlarının ileri davranışı.
- **VERİ:** Toplam checkpoint/olay `n=5046`, 8×4H tam ufuk `n=4977`, sağdan sansürlü `n=69`, ATR geçerli `n=4977`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `fitil_veya_yakin_red` (8×4H n=3836, med=-0.102 ATR, ort=-0.028 ATR, MFE_med=0.609, MAE_med=0.613, top1_sembol=1.7%) vs `ustte_kapanis_basarili` (8×4H n=1141, med=0.000 ATR, ort=0.084 ATR, MFE_med=0.699, MAE_med=0.552, top1_sembol=1.7%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `fitil_veya_yakin_red` | 1 | 3889 / 3889 / 7 | 100 (1.7%) | -0.018 / -0.021 | -0.017 | 0.125 / 0.143 | 2.5% / 2.1% / 0.0% | -0.019 / -0.023 |
| `fitil_veya_yakin_red` | 4 | 3859 / 3859 / 37 | 100 (1.7%) | -0.039 / -0.065 | -0.038 | 0.391 / 0.409 | 14.5% / 14.0% / 0.1% | -0.028 / -0.102 |
| `fitil_veya_yakin_red` | 8 | 3836 / 3836 / 60 | 100 (1.7%) | -0.028 / -0.102 | -0.024 | 0.609 / 0.613 | 28.2% / 27.9% / 0.1% | -0.067 / -0.140 |
| `fitil_veya_yakin_red` | 10 | 3824 / 3824 / 72 | 100 (1.7%) | -0.020 / -0.099 | -0.013 | 0.691 / 0.716 | 32.6% / 33.1% / 0.2% | -0.051 / -0.141 |
| `fitil_veya_yakin_red` | 12 | 3810 / 3810 / 86 | 100 (1.7%) | -0.017 / -0.074 | -0.013 | 0.775 / 0.798 | 36.0% / 36.5% / 0.2% | -0.014 / -0.126 |
| `fitil_veya_yakin_red` | 16 | 3789 / 3789 / 107 | 100 (1.7%) | +0.052 / -0.041 | +0.058 | 0.916 / 0.900 | 40.5% / 40.5% / 0.2% | 0.103 / -0.153 |
| `ustte_kapanis_basarili` | 1 | 1150 / 1150 / 0 | 100 (1.7%) | +0.003 / +0.000 | +0.004 | 0.133 / 0.151 | 2.9% / 2.4% / 0.0% | 0.000 / 0.000 |
| `ustte_kapanis_basarili` | 4 | 1149 / 1149 / 1 | 100 (1.7%) | +0.026 / +0.000 | +0.033 | 0.490 / 0.391 | 20.1% / 11.2% / 0.2% | 0.037 / -0.052 |
| `ustte_kapanis_basarili` | 8 | 1141 / 1141 / 9 | 100 (1.7%) | +0.084 / +0.000 | +0.098 | 0.699 / 0.552 | 34.8% / 25.9% / 0.2% | 0.032 / -0.022 |
| `ustte_kapanis_basarili` | 10 | 1141 / 1141 / 9 | 100 (1.7%) | +0.051 / -0.057 | +0.062 | 0.781 / 0.653 | 39.4% / 30.6% / 0.2% | 0.000 / -0.104 |
| `ustte_kapanis_basarili` | 12 | 1141 / 1141 / 9 | 100 (1.7%) | +0.090 / +0.000 | +0.109 | 0.880 / 0.727 | 43.2% / 35.2% / 0.2% | 0.120 / -0.117 |
| `ustte_kapanis_basarili` | 16 | 1139 / 1139 / 11 | 100 (1.7%) | +0.097 / +0.000 | +0.122 | 1.065 / 0.872 | 47.8% / 39.2% / 0.3% | 0.149 / -0.157 |

- **KARŞI ÖRNEK:** EGEEN (2026-09-04 18:00, kova=fitil_veya_yakin_red): 8x4H korunan=+6.28 ATR (MFE=7.90 / MAE=1.05 ATR) · BJKAS (2025-12-18 18:00, kova=ustte_kapanis_basarili): 8x4H korunan=-6.49 ATR (MFE=0.00 / MAE=6.69 ATR)
- **SINIR:** Yalnız kapanmış 4H mum sonundaki durum bilinir.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.102 ATR, MAE farkı 0.061 ATR düzeyinde ayrıştı.

## STB-BHV-E02 — Başarısız denemeden sonra önce destek mi aşağı iner, fiyat mı yeniden dener?

- **TANIM:** Sabit desteği geçemeyen denemelerden sonra 24x4H yarışında desteğin aşağı taşınması (SUPPORT_DOWN_FIRST) vs geri alım (PRICE_RECLAIM_FIRST).
- **VERİ:** Toplam checkpoint/olay `n=11144`, 8×4H tam ufuk `n=10957`, sağdan sansürlü `n=187`, ATR geçerli `n=10957`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=268`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `coklu_basarisiz_deneme_sonrasi` (8×4H n=3747, med=-0.025 ATR, ort=0.047 ATR, MFE_med=0.631, MAE_med=0.520, top1_sembol=4.2%) vs `ilk_basarisiz_deneme_sonrasi` (8×4H n=7210, med=0.000 ATR, ort=0.040 ATR, MFE_med=0.644, MAE_med=0.540, top1_sembol=3.3%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `coklu_basarisiz_deneme_sonrasi` | 1 | 3801 / 3801 / 10 | 96 (4.2%) | -0.001 / +0.000 | +0.026 | 0.129 / 0.130 | 3.2% / 1.9% / 0.1% | 0.000 / -0.012 |
| `coklu_basarisiz_deneme_sonrasi` | 4 | 3775 / 3775 / 36 | 96 (4.2%) | +0.007 / -0.023 | +0.088 | 0.406 / 0.348 | 16.7% / 11.6% / 0.2% | 0.000 / -0.066 |
| `coklu_basarisiz_deneme_sonrasi` | 8 | 3747 / 3747 / 64 | 96 (4.2%) | +0.047 / -0.025 | +0.202 | 0.631 / 0.520 | 31.5% / 23.3% / 0.2% | 0.019 / -0.071 |
| `coklu_basarisiz_deneme_sonrasi` | 10 | 3737 / 3737 / 74 | 96 (4.2%) | +0.062 / +0.000 | +0.230 | 0.750 / 0.599 | 36.4% / 27.6% / 0.2% | 0.067 / -0.066 |
| `coklu_basarisiz_deneme_sonrasi` | 12 | 3729 / 3729 / 82 | 96 (4.2%) | +0.064 / +0.000 | +0.239 | 0.839 / 0.661 | 40.3% / 31.1% / 0.2% | 0.102 / -0.094 |
| `coklu_basarisiz_deneme_sonrasi` | 16 | 3717 / 3717 / 94 | 96 (4.2%) | +0.079 / +0.011 | +0.295 | 0.988 / 0.774 | 44.6% / 35.7% / 0.2% | 0.163 / -0.122 |
| `ilk_basarisiz_deneme_sonrasi` | 1 | 7312 / 7312 / 21 | 100 (3.3%) | -0.004 / +0.000 | +0.009 | 0.137 / 0.141 | 3.1% / 2.1% / 0.0% | 0.000 / 0.000 |
| `ilk_basarisiz_deneme_sonrasi` | 4 | 7263 / 7263 / 70 | 100 (3.3%) | +0.010 / -0.029 | +0.055 | 0.410 / 0.372 | 16.2% / 12.2% / 0.1% | 0.000 / -0.077 |
| `ilk_basarisiz_deneme_sonrasi` | 8 | 7210 / 7210 / 123 | 100 (3.3%) | +0.040 / +0.000 | +0.109 | 0.644 / 0.540 | 30.2% / 24.8% / 0.2% | 0.058 / -0.093 |
| `ilk_basarisiz_deneme_sonrasi` | 10 | 7181 / 7181 / 152 | 100 (3.3%) | +0.067 / +0.010 | +0.150 | 0.736 / 0.612 | 34.8% / 28.6% / 0.2% | 0.114 / -0.091 |
| `ilk_basarisiz_deneme_sonrasi` | 12 | 7163 / 7163 / 170 | 100 (3.3%) | +0.096 / +0.024 | +0.192 | 0.823 / 0.680 | 38.4% / 31.7% / 0.2% | 0.155 / -0.090 |
| `ilk_basarisiz_deneme_sonrasi` | 16 | 7132 / 7132 / 201 | 100 (3.3%) | +0.144 / +0.047 | +0.265 | 0.977 / 0.781 | 44.0% / 35.4% / 0.3% | 0.286 / -0.144 |

- **KARŞI ÖRNEK:** DARDL (2025-05-13 18:00, kova=ilk_basarisiz_deneme_sonrasi): 8x4H korunan=-9.45 ATR (MFE=0.00 / MAE=9.51 ATR) · EGEEN (2026-09-04 18:00, kova=coklu_basarisiz_deneme_sonrasi): 8x4H korunan=+6.28 ATR (MFE=7.90 / MAE=1.05 ATR)
- **SINIR:** Başlangıcı arşiv öncesinde kalan kırılma epizotları UNKNOWN olarak dışlanmıştır.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.025 ATR) ve MAE farkı (0.020 ATR) sınırlı kaldı.

## STB-BHV-E03 — İlk ve birkaçıncı denemede geri alım aynı tepkiyi mi veriyor?

- **TANIM:** Öncesinde başarısız fitil denemesi olmadan doğrudan geri alınan destekler ile başarısız denemeler sonrası geri alınanların karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=1136`, 8×4H tam ufuk `n=1127`, sağdan sansürlü `n=9`, ATR geçerli `n=1127`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=14`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `birden_cok_deneme_sonrasi_geri_alim` (8×4H n=634, med=0.000 ATR, ort=0.074 ATR, MFE_med=0.697, MAE_med=0.565, top1_sembol=2.0%) vs `ilk_denemede_geri_alim` (8×4H n=493, med=0.000 ATR, ort=0.081 ATR, MFE_med=0.693, MAE_med=0.539, top1_sembol=2.2%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `birden_cok_deneme_sonrasi_geri_alim` | 1 | 636 / 636 / 0 | 100 (2.0%) | +0.005 / +0.000 | -0.000 | 0.138 / 0.150 | 3.0% / 2.0% / 0.0% | 0.000 / 0.000 |
| `birden_cok_deneme_sonrasi_geri_alim` | 4 | 636 / 636 / 0 | 100 (2.0%) | +0.002 / -0.029 | -0.011 | 0.502 / 0.392 | 19.3% / 11.2% / 0.3% | 0.035 / -0.068 |
| `birden_cok_deneme_sonrasi_geri_alim` | 8 | 634 / 634 / 2 | 100 (2.0%) | +0.074 / +0.000 | +0.059 | 0.697 / 0.565 | 33.8% / 25.2% / 0.3% | 0.075 / -0.035 |
| `birden_cok_deneme_sonrasi_geri_alim` | 10 | 634 / 634 / 2 | 100 (2.0%) | +0.052 / -0.031 | +0.024 | 0.781 / 0.669 | 39.3% / 29.5% / 0.3% | 0.022 / -0.104 |
| `birden_cok_deneme_sonrasi_geri_alim` | 12 | 634 / 634 / 2 | 100 (2.0%) | +0.111 / +0.000 | +0.084 | 0.924 / 0.750 | 44.0% / 34.2% / 0.3% | 0.211 / -0.099 |
| `birden_cok_deneme_sonrasi_geri_alim` | 16 | 634 / 634 / 2 | 100 (2.0%) | +0.119 / +0.006 | +0.104 | 1.074 / 0.898 | 47.9% / 39.0% / 0.3% | 0.145 / -0.123 |
| `ilk_denemede_geri_alim` | 1 | 500 / 500 / 0 | 99 (2.2%) | -0.001 / +0.000 | +0.002 | 0.123 / 0.154 | 2.8% / 2.8% / 0.0% | 0.000 / 0.000 |
| `ilk_denemede_geri_alim` | 4 | 499 / 499 / 1 | 99 (2.2%) | +0.045 / +0.000 | +0.056 | 0.466 / 0.389 | 21.0% / 11.4% / 0.0% | 0.000 / -0.024 |
| `ilk_denemede_geri_alim` | 8 | 493 / 493 / 7 | 99 (2.2%) | +0.081 / +0.000 | +0.090 | 0.693 / 0.539 | 35.7% / 26.8% / 0.0% | 0.000 / -0.030 |
| `ilk_denemede_geri_alim` | 10 | 493 / 493 / 7 | 99 (2.2%) | +0.035 / -0.075 | +0.052 | 0.780 / 0.631 | 39.4% / 31.9% / 0.0% | 0.000 / -0.127 |
| `ilk_denemede_geri_alim` | 12 | 493 / 493 / 7 | 99 (2.2%) | +0.047 / -0.010 | +0.080 | 0.868 / 0.710 | 42.0% / 36.5% / 0.0% | 0.078 / -0.213 |
| `ilk_denemede_geri_alim` | 16 | 491 / 491 / 9 | 99 (2.2%) | +0.053 / -0.082 | +0.086 | 1.034 / 0.844 | 47.4% / 39.7% / 0.2% | 0.170 / -0.236 |

- **KARŞI ÖRNEK:** DMSAS (2026-09-14 18:00, kova=ilk_denemede_geri_alim): 8x4H korunan=-4.70 ATR (MFE=0.00 / MAE=4.93 ATR) · BJKAS (2025-12-18 18:00, kova=birden_cok_deneme_sonrasi_geri_alim): 8x4H korunan=-6.49 ATR (MFE=0.00 / MAE=6.69 ATR)
- **SINIR:** Deneme sayısı yalnız başlangıcı bilinen kırılma epizotlarında ölçülür.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.000 ATR) ve MAE farkı (0.025 ATR) sınırlı kaldı.

## STB-BHV-E04 — Altta kalma uzarsa sabit seviyenin geri alım tepkisi güçleniyor mu?

- **TANIM:** Sabit desteğin geri alındığı anda altta geçirilen 4H bar sayısına (1-4, 5-12, 13+) göre geri alım sonrası tepki.
- **VERİ:** Toplam checkpoint/olay `n=1150`, 8×4H tam ufuk `n=1141`, sağdan sansürlü `n=9`, ATR geçerli `n=1141`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `kisa_altta_kalma_1_4_4h` (8×4H n=690, med=0.000 ATR, ort=0.068 ATR, MFE_med=0.705, MAE_med=0.540, top1_sembol=2.0%) vs `orta_altta_kalma_5_12_4h` (8×4H n=295, med=-0.035 ATR, ort=0.102 ATR, MFE_med=0.641, MAE_med=0.566, top1_sembol=3.0%) vs `uzun_altta_kalma_13+_4h` (8×4H n=156, med=0.056 ATR, ort=0.121 ATR, MFE_med=0.815, MAE_med=0.584, top1_sembol=3.2%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `kisa_altta_kalma_1_4_4h` | 1 | 699 / 699 / 0 | 100 (2.0%) | +0.002 / +0.000 | +0.002 | 0.136 / 0.154 | 3.1% / 2.9% / 0.0% | 0.000 / 0.000 |
| `kisa_altta_kalma_1_4_4h` | 4 | 698 / 698 / 1 | 100 (2.0%) | +0.011 / -0.015 | +0.011 | 0.459 / 0.394 | 18.3% / 11.3% / 0.0% | 0.000 / -0.041 |
| `kisa_altta_kalma_1_4_4h` | 8 | 690 / 690 / 9 | 100 (2.0%) | +0.068 / +0.000 | +0.077 | 0.705 / 0.540 | 34.4% / 26.7% / 0.0% | 0.035 / -0.004 |
| `kisa_altta_kalma_1_4_4h` | 10 | 690 / 690 / 9 | 100 (2.0%) | +0.042 / -0.041 | +0.050 | 0.780 / 0.626 | 39.0% / 31.0% / 0.0% | 0.010 / -0.106 |
| `kisa_altta_kalma_1_4_4h` | 12 | 690 / 690 / 9 | 100 (2.0%) | +0.070 / +0.000 | +0.095 | 0.868 / 0.699 | 42.5% / 36.1% / 0.0% | 0.116 / -0.095 |
| `kisa_altta_kalma_1_4_4h` | 16 | 688 / 688 / 11 | 100 (2.0%) | +0.049 / -0.042 | +0.078 | 1.030 / 0.826 | 47.2% / 39.5% / 0.1% | 0.093 / -0.175 |
| `orta_altta_kalma_5_12_4h` | 1 | 295 / 295 / 0 | 96 (3.0%) | +0.011 / +0.000 | +0.010 | 0.147 / 0.156 | 2.0% / 1.4% / 0.0% | 0.000 / 0.000 |
| `orta_altta_kalma_5_12_4h` | 4 | 295 / 295 / 0 | 96 (3.0%) | +0.029 / +0.000 | +0.020 | 0.525 / 0.387 | 20.0% / 11.2% / 0.3% | 0.037 / -0.068 |
| `orta_altta_kalma_5_12_4h` | 8 | 295 / 295 / 0 | 96 (3.0%) | +0.102 / -0.035 | +0.115 | 0.641 / 0.566 | 31.9% / 25.1% / 0.3% | -0.023 / -0.045 |
| `orta_altta_kalma_5_12_4h` | 10 | 295 / 295 / 0 | 96 (3.0%) | +0.096 / -0.065 | +0.097 | 0.719 / 0.694 | 36.6% / 30.5% / 0.3% | 0.040 / -0.104 |
| `orta_altta_kalma_5_12_4h` | 12 | 295 / 295 / 0 | 96 (3.0%) | +0.120 / +0.000 | +0.111 | 0.855 / 0.782 | 41.0% / 34.9% / 0.3% | 0.153 / -0.186 |
| `orta_altta_kalma_5_12_4h` | 16 | 295 / 295 / 0 | 96 (3.0%) | +0.233 / +0.111 | +0.213 | 1.048 / 0.973 | 45.4% / 40.7% / 0.3% | 0.202 / -0.084 |
| `uzun_altta_kalma_13+_4h` | 1 | 156 / 156 / 0 | 79 (3.2%) | -0.011 / +0.000 | -0.000 | 0.110 / 0.135 | 3.2% / 1.9% / 0.0% | 0.028 / 0.000 |
| `uzun_altta_kalma_13+_4h` | 4 | 156 / 156 / 0 | 79 (3.2%) | +0.089 / +0.062 | +0.115 | 0.566 / 0.378 | 28.2% / 10.9% / 0.6% | 0.111 / -0.121 |
| `uzun_altta_kalma_13+_4h` | 8 | 156 / 156 / 0 | 79 (3.2%) | +0.121 / +0.056 | +0.137 | 0.815 / 0.584 | 42.3% / 23.7% / 0.6% | 0.145 / -0.043 |
| `uzun_altta_kalma_13+_4h` | 10 | 156 / 156 / 0 | 79 (3.2%) | +0.005 / -0.109 | -0.026 | 0.953 / 0.669 | 46.8% / 28.8% / 0.6% | -0.016 / -0.114 |
| `uzun_altta_kalma_13+_4h` | 12 | 156 / 156 / 0 | 79 (3.2%) | +0.124 / +0.023 | +0.058 | 1.062 / 0.787 | 50.6% / 32.0% / 0.6% | 0.057 / -0.069 |
| `uzun_altta_kalma_13+_4h` | 16 | 156 / 156 / 0 | 79 (3.2%) | +0.046 / -0.053 | +0.052 | 1.279 / 0.957 | 54.5% / 35.3% / 0.6% | 0.170 / -0.247 |

- **KARŞI ÖRNEK:** KONTR (2026-04-08 17:30, kova=orta_altta_kalma_5_12_4h): 8x4H korunan=+5.75 ATR (MFE=6.44 / MAE=0.35 ATR) · DMSAS (2026-09-14 18:00, kova=kisa_altta_kalma_1_4_4h): 8x4H korunan=-4.70 ATR (MFE=0.00 / MAE=4.93 ATR) · BJKAS (2025-12-18 18:00, kova=uzun_altta_kalma_13+_4h): 8x4H korunan=-6.49 ATR (MFE=0.00 / MAE=6.69 ATR)
- **SINIR:** Bu tablo geri alım koşuluna bağlıdır; altta kalma uzadıkça hiç geri alamama oranı D01/E02 ile birlikte okunmalıdır.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.090 ATR) ve MAE farkı (0.044 ATR) sınırlı kaldı.

## STB-BHV-E05 — Güçlü geri alım mumu bilgi mi taşıyor, kalan tepkiyi mi tüketiyor?

- **TANIM:** Geri alım 4H mumunun gövdesi >=0.5 günlük ATR olan güçlü geri alımlar ile daha küçük gövdeli geri alımların SONRAKİ ufuk getirisi.
- **VERİ:** Toplam checkpoint/olay `n=1150`, 8×4H tam ufuk `n=1141`, sağdan sansürlü `n=9`, ATR geçerli `n=1141`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `guclu_geri_alim_mumu` (8×4H n=395, med=0.058 ATR, ort=0.168 ATR, MFE_med=0.840, MAE_med=0.566, top1_sembol=2.8%) vs `ilimli_geri_alim_mumu` (8×4H n=746, med=-0.016 ATR, ort=0.040 ATR, MFE_med=0.643, MAE_med=0.548, top1_sembol=2.2%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `guclu_geri_alim_mumu` | 1 | 396 / 396 / 0 | 99 (2.8%) | -0.003 / +0.000 | +0.018 | 0.129 / 0.154 | 3.0% / 2.5% / 0.0% | 0.000 / 0.000 |
| `guclu_geri_alim_mumu` | 4 | 396 / 396 / 0 | 99 (2.8%) | +0.066 / +0.000 | +0.126 | 0.626 / 0.392 | 29.0% / 12.9% / 0.5% | 0.095 / -0.050 |
| `guclu_geri_alim_mumu` | 8 | 395 / 395 / 1 | 99 (2.8%) | +0.168 / +0.058 | +0.249 | 0.840 / 0.566 | 43.8% / 25.6% / 0.5% | 0.139 / 0.018 |
| `guclu_geri_alim_mumu` | 10 | 395 / 395 / 1 | 99 (2.8%) | +0.155 / +0.057 | +0.210 | 0.992 / 0.621 | 48.1% / 29.6% / 0.5% | 0.054 / 0.074 |
| `guclu_geri_alim_mumu` | 12 | 395 / 395 / 1 | 99 (2.8%) | +0.204 / +0.087 | +0.269 | 1.085 / 0.750 | 50.4% / 34.4% / 0.5% | 0.154 / 0.007 |
| `guclu_geri_alim_mumu` | 16 | 395 / 395 / 1 | 99 (2.8%) | +0.183 / +0.084 | +0.293 | 1.241 / 0.871 | 53.4% / 37.0% / 0.5% | 0.170 / -0.070 |
| `ilimli_geri_alim_mumu` | 1 | 754 / 754 / 0 | 100 (2.2%) | +0.006 / +0.000 | +0.002 | 0.134 / 0.150 | 2.8% / 2.2% / 0.0% | 0.000 / 0.000 |
| `ilimli_geri_alim_mumu` | 4 | 753 / 753 / 1 | 100 (2.2%) | +0.005 / +0.000 | -0.002 | 0.433 / 0.388 | 15.4% / 10.4% / 0.0% | 0.006 / -0.052 |
| `ilimli_geri_alim_mumu` | 8 | 746 / 746 / 8 | 100 (2.2%) | +0.040 / -0.016 | +0.015 | 0.643 / 0.548 | 30.0% / 26.0% / 0.0% | 0.000 / -0.044 |
| `ilimli_geri_alim_mumu` | 10 | 746 / 746 / 8 | 100 (2.2%) | -0.004 / -0.095 | -0.022 | 0.719 / 0.662 | 34.8% / 31.1% / 0.0% | 0.000 / -0.140 |
| `ilimli_geri_alim_mumu` | 12 | 746 / 746 / 8 | 100 (2.2%) | +0.030 / -0.048 | +0.032 | 0.814 / 0.724 | 39.4% / 35.7% / 0.0% | 0.097 / -0.184 |
| `ilimli_geri_alim_mumu` | 16 | 744 / 744 / 10 | 100 (2.2%) | +0.051 / -0.045 | +0.037 | 0.969 / 0.877 | 44.8% / 40.5% / 0.1% | 0.140 / -0.220 |

- **KARŞI ÖRNEK:** BJKAS (2025-12-18 18:00, kova=guclu_geri_alim_mumu): 8x4H korunan=-6.49 ATR (MFE=0.00 / MAE=6.69 ATR) · KONTR (2026-04-08 17:30, kova=ilimli_geri_alim_mumu): 8x4H korunan=+5.75 ATR (MFE=6.44 / MAE=0.35 ATR)
- **SINIR:** Olay mumunun kendi kazancı ileri getiriye dahil değildir.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.074 ATR) ve MAE farkı (0.018 ATR) sınırlı kaldı.

## STB-BHV-E06 — Geri alım sonrası yeniden testte tutunmayı beklemek faydalı mı?

- **TANIM:** Doğrudan geri alım kapanışında ölçüm ile üstte 1-3 gün içinde gelen yeniden test tutunmasını beklemenin getiri/örneklem takası.
- **VERİ:** Toplam checkpoint/olay `n=2383`, 8×4H tam ufuk `n=2340`, sağdan sansürlü `n=43`, ATR geçerli `n=2340`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `dogrudan_geri_alim_kapanisi` (8×4H n=1141, med=0.000 ATR, ort=0.084 ATR, MFE_med=0.699, MAE_med=0.552, top1_sembol=1.7%) vs `ustte_kapanis_sonrasi_yeniden_test_tutunmasi` (8×4H n=1199, med=-0.013 ATR, ort=0.025 ATR, MFE_med=0.612, MAE_med=0.556, top1_sembol=3.1%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `dogrudan_geri_alim_kapanisi` | 1 | 1150 / 1150 / 0 | 100 (1.7%) | +0.003 / +0.000 | +0.004 | 0.133 / 0.151 | 2.9% / 2.4% / 0.0% | 0.000 / 0.000 |
| `dogrudan_geri_alim_kapanisi` | 4 | 1149 / 1149 / 1 | 100 (1.7%) | +0.026 / +0.000 | +0.033 | 0.490 / 0.391 | 20.1% / 11.2% / 0.2% | 0.037 / -0.052 |
| `dogrudan_geri_alim_kapanisi` | 8 | 1141 / 1141 / 9 | 100 (1.7%) | +0.084 / +0.000 | +0.098 | 0.699 / 0.552 | 34.8% / 25.9% / 0.2% | 0.032 / -0.022 |
| `dogrudan_geri_alim_kapanisi` | 10 | 1141 / 1141 / 9 | 100 (1.7%) | +0.051 / -0.057 | +0.062 | 0.781 / 0.653 | 39.4% / 30.6% / 0.2% | 0.000 / -0.104 |
| `dogrudan_geri_alim_kapanisi` | 12 | 1141 / 1141 / 9 | 100 (1.7%) | +0.090 / +0.000 | +0.109 | 0.880 / 0.727 | 43.2% / 35.2% / 0.2% | 0.120 / -0.117 |
| `dogrudan_geri_alim_kapanisi` | 16 | 1139 / 1139 / 11 | 100 (1.7%) | +0.097 / +0.000 | +0.122 | 1.065 / 0.872 | 47.8% / 39.2% / 0.3% | 0.149 / -0.157 |
| `ustte_kapanis_sonrasi_yeniden_test_tutunmasi` | 1 | 1232 / 1232 / 1 | 100 (3.1%) | -0.016 / +0.000 | -0.014 | 0.136 / 0.152 | 3.5% / 3.4% / 0.0% | -0.010 / 0.000 |
| `ustte_kapanis_sonrasi_yeniden_test_tutunmasi` | 4 | 1225 / 1225 / 8 | 100 (3.1%) | -0.001 / -0.034 | +0.017 | 0.400 / 0.395 | 17.7% / 14.8% / 0.1% | -0.053 / -0.012 |
| `ustte_kapanis_sonrasi_yeniden_test_tutunmasi` | 8 | 1199 / 1199 / 34 | 100 (3.1%) | +0.025 / -0.013 | +0.054 | 0.612 / 0.556 | 30.7% / 26.5% / 0.2% | 0.000 / -0.062 |
| `ustte_kapanis_sonrasi_yeniden_test_tutunmasi` | 10 | 1196 / 1196 / 37 | 100 (3.1%) | +0.054 / +0.000 | +0.084 | 0.716 / 0.628 | 35.9% / 29.8% / 0.2% | 0.067 / -0.051 |
| `ustte_kapanis_sonrasi_yeniden_test_tutunmasi` | 12 | 1192 / 1192 / 41 | 100 (3.1%) | +0.071 / +0.000 | +0.083 | 0.843 / 0.699 | 39.7% / 33.1% / 0.2% | 0.128 / -0.043 |
| `ustte_kapanis_sonrasi_yeniden_test_tutunmasi` | 16 | 1187 / 1187 / 46 | 100 (3.1%) | +0.038 / +0.000 | +0.062 | 0.979 / 0.817 | 44.3% / 38.4% / 0.2% | 0.151 / -0.208 |

- **KARŞI ÖRNEK:** BJKAS (2025-12-18 18:00, kova=dogrudan_geri_alim_kapanisi): 8x4H korunan=-6.49 ATR (MFE=0.00 / MAE=6.69 ATR) · FONET (2025-10-08 18:00, kova=ustte_kapanis_sonrasi_yeniden_test_tutunmasi): 8x4H korunan=+6.27 ATR (MFE=7.75 / MAE=0.00 ATR)
- **SINIR:** Yeniden test beklemek hiç test vermeden giden hareketleri dışarıda bırakır (örneklem farkına dikkat).
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.013 ATR) ve MAE farkı (0.005 ATR) sınırlı kaldı.

## STB-BHV-F01 — Hareketli/dikey bölümde yukarı deneme, yataylaşma sonrasından daha mı çok geri dönüyor?

- **TANIM:** Aşağı basamak/iniş (STEPPING_DOWN) evresindeki yukarı tepki denemeleri ile ek gecikmesiz yataylaşma (HORIZONTAL_AFTER_DROP) sonrası denemeler.
- **VERİ:** Toplam checkpoint/olay `n=14125`, 8×4H tam ufuk `n=14097`, sağdan sansürlü `n=28`, ATR geçerli `n=14097`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `PROVISIONAL_CANDIDATE_PENDING_USER_CONFIRMATION`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `HORIZONTAL_AFTER_DROP` (8×4H n=10693, med=-0.099 ATR, ort=-0.012 ATR, MFE_med=0.735, MAE_med=0.693, top1_sembol=1.5%) vs `STEPPING_DOWN` (8×4H n=3404, med=0.024 ATR, ort=0.155 ATR, MFE_med=0.751, MAE_med=0.562, top1_sembol=2.8%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `HORIZONTAL_AFTER_DROP` | 1 | 10713 / 10713 / 1 | 100 (1.5%) | +0.000 / -0.018 | -0.001 | 0.181 / 0.184 | 6.4% / 3.3% / 0.3% | -0.019 / -0.015 |
| `HORIZONTAL_AFTER_DROP` | 4 | 10708 / 10708 / 6 | 100 (1.5%) | -0.003 / -0.078 | -0.008 | 0.508 / 0.476 | 23.4% / 16.3% / 0.7% | -0.062 / -0.100 |
| `HORIZONTAL_AFTER_DROP` | 8 | 10693 / 10693 / 21 | 100 (1.5%) | -0.012 / -0.099 | -0.019 | 0.735 / 0.693 | 35.7% / 30.0% / 0.8% | -0.076 / -0.120 |
| `HORIZONTAL_AFTER_DROP` | 10 | 10680 / 10680 / 34 | 100 (1.5%) | -0.028 / -0.132 | -0.038 | 0.831 / 0.786 | 39.3% / 34.5% / 0.8% | -0.098 / -0.158 |
| `HORIZONTAL_AFTER_DROP` | 12 | 10661 / 10661 / 53 | 100 (1.5%) | -0.029 / -0.156 | -0.040 | 0.915 / 0.876 | 42.0% / 37.7% / 0.8% | -0.098 / -0.202 |
| `HORIZONTAL_AFTER_DROP` | 16 | 10631 / 10631 / 83 | 100 (1.5%) | -0.052 / -0.165 | -0.068 | 1.069 / 1.032 | 45.6% / 42.2% / 0.7% | -0.114 / -0.216 |
| `STEPPING_DOWN` | 1 | 3411 / 3411 / 0 | 100 (2.8%) | +0.026 / +0.000 | +0.025 | 0.162 / 0.155 | 5.6% / 1.9% / 0.1% | 0.000 / 0.000 |
| `STEPPING_DOWN` | 4 | 3411 / 3411 / 0 | 100 (2.8%) | +0.092 / +0.000 | +0.094 | 0.508 / 0.386 | 23.1% / 13.2% / 0.3% | 0.065 / -0.042 |
| `STEPPING_DOWN` | 8 | 3404 / 3404 / 7 | 100 (2.8%) | +0.155 / +0.024 | +0.161 | 0.751 / 0.562 | 38.4% / 25.6% / 0.4% | 0.160 / -0.067 |
| `STEPPING_DOWN` | 10 | 3404 / 3404 / 7 | 100 (2.8%) | +0.169 / +0.039 | +0.194 | 0.861 / 0.652 | 41.9% / 30.2% / 0.4% | 0.231 / -0.111 |
| `STEPPING_DOWN` | 12 | 3401 / 3401 / 10 | 100 (2.8%) | +0.148 / +0.000 | +0.176 | 0.949 / 0.742 | 44.8% / 33.9% / 0.4% | 0.251 / -0.182 |
| `STEPPING_DOWN` | 16 | 3401 / 3401 / 10 | 100 (2.8%) | +0.090 / -0.038 | +0.117 | 1.142 / 0.888 | 49.1% / 37.7% / 0.4% | 0.171 / -0.248 |

- **KARŞI ÖRNEK:** KONTR (2025-12-05 13:30, kova=STEPPING_DOWN): 8x4H korunan=-6.62 ATR (MFE=0.03 / MAE=6.64 ATR) · DIRIT (2026-02-11 17:30, kova=HORIZONTAL_AFTER_DROP): 8x4H korunan=+8.05 ATR (MFE=9.36 / MAE=0.00 ATR)
- **SINIR:** DİKKAT: Kullanıcının 'altı boş' hipotezinin aday eşlemesidir; gerçek grafik örneği üzerinde kullanıcı teyidi alınana kadar kesinleşmiş ölçüm sayılmaz.
- **SONUÇ (`ayrı doğrulama gerekli`):** Aday dikey/yatay eşlemesi altında 8x4H medyan farkı 0.122 ATR, MAE farkı 0.131 ATR [HORIZONTAL_AFTER_DROP: med=-0.099 / MAE=0.693 ATR (n=10693), STEPPING_DOWN: med=+0.024 / MAE=0.562 ATR (n=3404)]; aday rejim eşlemesi debug niteliğinde olduğundan kesin kural sayılmaz.

## STB-BHV-F02 — Üstte görünmeyi fiyat mı, desteğin aşağı taşınması mı oluşturuyor?

- **TANIM:** Fiyatın destek üstüne geçtiği ilk 4H kapanışını: (1) eski desteği fiyatın aşması vs (2) desteğin fiyatın altına inmesi olarak ayırır.
- **VERİ:** Toplam checkpoint/olay `n=1679`, 8×4H tam ufuk `n=1668`, sağdan sansürlü `n=11`, ATR geçerli `n=1668`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `destek_asagi_inerek_ustte_kaldi` (8×4H n=475, med=0.034 ATR, ort=0.074 ATR, MFE_med=0.693, MAE_med=0.424, top1_sembol=2.1%) vs `fiyat_yukselerek_eski_destegi_asti` (8×4H n=1141, med=0.000 ATR, ort=0.084 ATR, MFE_med=0.699, MAE_med=0.552, top1_sembol=1.7%) vs `hem_fiyat_hem_destek_degisti` (8×4H n=52, med=0.481 ATR, ort=0.576 ATR, MFE_med=1.035, MAE_med=0.547, top1_sembol=3.9%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `destek_asagi_inerek_ustte_kaldi` | 1 | 477 / 477 / 0 | 99 (2.1%) | +0.018 / +0.000 | +0.029 | 0.175 / 0.166 | 2.1% / 0.6% / 0.0% | 0.000 / -0.031 |
| `destek_asagi_inerek_ustte_kaldi` | 4 | 477 / 477 / 0 | 99 (2.1%) | +0.155 / +0.040 | +0.169 | 0.455 / 0.320 | 21.0% / 8.2% / 0.4% | 0.211 / -0.060 |
| `destek_asagi_inerek_ustte_kaldi` | 8 | 475 / 475 / 2 | 99 (2.1%) | +0.074 / +0.034 | +0.081 | 0.693 / 0.424 | 31.2% / 19.8% / 0.4% | 0.300 / -0.106 |
| `destek_asagi_inerek_ustte_kaldi` | 10 | 475 / 475 / 2 | 99 (2.1%) | +0.010 / +0.000 | +0.015 | 0.782 / 0.580 | 37.7% / 26.7% / 0.4% | 0.057 / -0.092 |
| `destek_asagi_inerek_ustte_kaldi` | 12 | 475 / 475 / 2 | 99 (2.1%) | +0.009 / +0.000 | +0.030 | 0.832 / 0.649 | 40.2% / 28.2% / 0.4% | 0.179 / -0.091 |
| `destek_asagi_inerek_ustte_kaldi` | 16 | 475 / 475 / 2 | 99 (2.1%) | -0.059 / -0.047 | -0.035 | 0.937 / 0.749 | 43.8% / 33.1% / 0.4% | 0.128 / -0.237 |
| `fiyat_yukselerek_eski_destegi_asti` | 1 | 1150 / 1150 / 0 | 100 (1.7%) | +0.003 / +0.000 | +0.004 | 0.133 / 0.151 | 2.9% / 2.4% / 0.0% | 0.000 / 0.000 |
| `fiyat_yukselerek_eski_destegi_asti` | 4 | 1149 / 1149 / 1 | 100 (1.7%) | +0.026 / +0.000 | +0.033 | 0.490 / 0.391 | 20.1% / 11.2% / 0.2% | 0.037 / -0.052 |
| `fiyat_yukselerek_eski_destegi_asti` | 8 | 1141 / 1141 / 9 | 100 (1.7%) | +0.084 / +0.000 | +0.098 | 0.699 / 0.552 | 34.8% / 25.9% / 0.2% | 0.032 / -0.022 |
| `fiyat_yukselerek_eski_destegi_asti` | 10 | 1141 / 1141 / 9 | 100 (1.7%) | +0.051 / -0.057 | +0.062 | 0.781 / 0.653 | 39.4% / 30.6% / 0.2% | 0.000 / -0.104 |
| `fiyat_yukselerek_eski_destegi_asti` | 12 | 1141 / 1141 / 9 | 100 (1.7%) | +0.090 / +0.000 | +0.109 | 0.880 / 0.727 | 43.2% / 35.2% / 0.2% | 0.120 / -0.117 |
| `fiyat_yukselerek_eski_destegi_asti` | 16 | 1139 / 1139 / 11 | 100 (1.7%) | +0.097 / +0.000 | +0.122 | 1.065 / 0.872 | 47.8% / 39.2% / 0.3% | 0.149 / -0.157 |
| `hem_fiyat_hem_destek_degisti` | 1 | 52 / 52 / 0 | 44 (3.9%) | -0.039 / +0.019 | -0.013 | 0.207 / 0.161 | 0.0% / 3.9% / 0.0% | 0.064 / 0.000 |
| `hem_fiyat_hem_destek_degisti` | 4 | 52 / 52 / 0 | 44 (3.9%) | +0.124 / +0.014 | +0.085 | 0.499 / 0.473 | 15.4% / 15.4% / 1.9% | 0.141 / 0.000 |
| `hem_fiyat_hem_destek_degisti` | 8 | 52 / 52 / 0 | 44 (3.9%) | +0.576 / +0.481 | +0.542 | 1.035 / 0.547 | 44.2% / 25.0% / 1.9% | 0.781 / -0.113 |
| `hem_fiyat_hem_destek_degisti` | 10 | 52 / 52 / 0 | 44 (3.9%) | +0.706 / +0.634 | +0.692 | 1.186 / 0.580 | 46.2% / 28.8% / 1.9% | 1.081 / -0.058 |
| `hem_fiyat_hem_destek_degisti` | 12 | 52 / 52 / 0 | 44 (3.9%) | +0.499 / +0.595 | +0.509 | 1.461 / 0.663 | 50.0% / 30.8% / 1.9% | 0.727 / 0.000 |
| `hem_fiyat_hem_destek_degisti` | 16 | 52 / 52 / 0 | 44 (3.9%) | +0.422 / +0.488 | +0.451 | 1.607 / 0.767 | 51.9% / 34.6% / 1.9% | 0.684 / -0.296 |

- **KARŞI ÖRNEK:** BJKAS (2025-12-18 18:00, kova=fiyat_yukselerek_eski_destegi_asti): 8x4H korunan=-6.49 ATR (MFE=0.00 / MAE=6.69 ATR) · GOLTS (2025-06-11 13:30, kova=destek_asagi_inerek_ustte_kaldi): 8x4H korunan=-3.11 ATR (MFE=0.05 / MAE=3.74 ATR) · BRKVY (2026-02-18 13:30, kova=hem_fiyat_hem_destek_degisti): 8x4H korunan=-1.97 ATR (MFE=0.21 / MAE=2.05 ATR)
- **SINIR:** Bu ayrım tamamen native seviye değişiminden ve kapanış fiyatından nedensel olarak hesaplanır.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.481 ATR, MAE farkı 0.127 ATR düzeyinde ayrıştı.

## STB-BHV-F03 — Kesin yataylaşma anında üstte veya altta olmak sonucu değiştiriyor mu?

- **TANIM:** Yeni aşağı basamak onaylandığı (4 sağ bar teyitli) anda 4H kapanışın yeni seviyenin üstünde vs altında olmasının ileri sonucu.
- **VERİ:** Toplam checkpoint/olay `n=1193`, 8×4H tam ufuk `n=1185`, sağdan sansürlü `n=8`, ATR geçerli `n=1185`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `PROVISIONAL_CANDIDATE_PENDING_USER_CONFIRMATION`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `asagi_basamak_aninda_altta` (8×4H n=28, med=0.131 ATR, ort=-0.042 ATR, MFE_med=0.431, MAE_med=0.451, top1_sembol=6.9%) vs `asagi_basamak_aninda_ustte` (8×4H n=1157, med=-0.022 ATR, ort=0.059 ATR, MFE_med=0.658, MAE_med=0.547, top1_sembol=1.6%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `asagi_basamak_aninda_altta` | 1 | 29 / 29 / 0 | 24 (6.9%) | +0.058 / +0.040 | +0.026 | 0.145 / 0.117 | 3.5% / 0.0% / 0.0% | -0.017 / 0.053 |
| `asagi_basamak_aninda_altta` | 4 | 29 / 29 / 0 | 24 (6.9%) | +0.031 / +0.062 | -0.003 | 0.302 / 0.395 | 17.2% / 20.7% / 0.0% | 0.221 / 0.009 |
| `asagi_basamak_aninda_altta` | 8 | 28 / 28 / 1 | 24 (6.9%) | -0.042 / +0.131 | +0.011 | 0.431 / 0.451 | 28.6% / 21.4% / 0.0% | 0.612 / -0.157 |
| `asagi_basamak_aninda_altta` | 10 | 28 / 28 / 1 | 24 (6.9%) | +0.141 / +0.189 | +0.198 | 0.576 / 0.500 | 32.1% / 21.4% / 0.0% | 0.178 / 0.242 |
| `asagi_basamak_aninda_altta` | 12 | 27 / 27 / 2 | 24 (6.9%) | +0.149 / +0.218 | +0.246 | 0.868 / 0.494 | 33.3% / 25.9% / 0.0% | 0.198 / 0.230 |
| `asagi_basamak_aninda_altta` | 16 | 27 / 27 / 2 | 24 (6.9%) | +0.090 / +0.199 | +0.207 | 0.915 / 0.651 | 37.0% / 25.9% / 0.0% | 0.344 / 0.076 |
| `asagi_basamak_aninda_ustte` | 1 | 1164 / 1164 / 0 | 100 (1.6%) | -0.006 / -0.014 | -0.004 | 0.186 / 0.185 | 2.7% / 1.1% / 0.1% | 0.000 / -0.031 |
| `asagi_basamak_aninda_ustte` | 4 | 1164 / 1164 / 0 | 100 (1.6%) | +0.065 / -0.020 | +0.080 | 0.448 / 0.408 | 20.5% / 13.4% / 0.3% | -0.032 / 0.000 |
| `asagi_basamak_aninda_ustte` | 8 | 1157 / 1157 / 7 | 100 (1.6%) | +0.059 / -0.022 | +0.079 | 0.658 / 0.547 | 32.4% / 25.5% / 0.4% | 0.016 / -0.057 |
| `asagi_basamak_aninda_ustte` | 10 | 1157 / 1157 / 7 | 100 (1.6%) | +0.049 / -0.030 | +0.078 | 0.769 / 0.696 | 37.9% / 33.3% / 0.4% | 0.031 / -0.100 |
| `asagi_basamak_aninda_ustte` | 12 | 1156 / 1156 / 8 | 100 (1.6%) | +0.035 / +0.000 | +0.066 | 0.852 / 0.756 | 40.7% / 34.6% / 0.4% | 0.031 / -0.047 |
| `asagi_basamak_aninda_ustte` | 16 | 1156 / 1156 / 8 | 100 (1.6%) | -0.075 / -0.124 | -0.034 | 0.962 / 0.912 | 43.3% / 39.4% / 0.4% | 0.023 / -0.209 |

- **KARŞI ÖRNEK:** KLGYO (2026-01-07 13:30, kova=asagi_basamak_aninda_ustte): 8x4H korunan=+6.00 ATR (MFE=6.00 / MAE=0.82 ATR) · KONTR (2026-09-18 13:30, kova=asagi_basamak_aninda_altta): 8x4H korunan=-3.78 ATR (MFE=0.00 / MAE=3.78 ATR)
- **SINIR:** Görsel yataylaşma teyidi kullanıcı grafik onayı beklemektedir; burada ek bar gecikmesi eklenmeden native onay anı ölçülmüştür.
- **SONUÇ (`ayrı doğrulama gerekli`):** Aday dikey/yatay eşlemesi altında 8x4H medyan farkı 0.153 ATR, MAE farkı 0.096 ATR [asagi_basamak_aninda_altta: med=+0.131 / MAE=0.451 ATR (n=28), asagi_basamak_aninda_ustte: med=-0.022 / MAE=0.547 ATR (n=1157)]; aday rejim eşlemesi debug niteliğinde olduğundan kesin kural sayılmaz.

## STB-BHV-F04 — Tek büyük aşağı basamak ile birçok küçük basamaktan sonra toparlanma farklı mı?

- **TANIM:** Desteğin aşağı taşındığı anda basamak boyutu >=2.0 ATR (tek büyük basamak) ile <2.0 ATR (küçük basamak) sonrası hareket.
- **VERİ:** Toplam checkpoint/olay `n=1193`, 8×4H tam ufuk `n=1185`, sağdan sansürlü `n=8`, ATR geçerli `n=1185`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `kucuk_kademeli_asagi_basamak` (8×4H n=787, med=-0.015 ATR, ort=0.067 ATR, MFE_med=0.650, MAE_med=0.562, top1_sembol=1.9%) vs `tek_buyuk_asagi_basamak` (8×4H n=398, med=-0.003 ATR, ort=0.035 ATR, MFE_med=0.656, MAE_med=0.505, top1_sembol=1.8%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `kucuk_kademeli_asagi_basamak` | 1 | 795 / 795 / 0 | 100 (1.9%) | -0.017 / -0.018 | -0.020 | 0.188 / 0.189 | 2.5% / 1.3% / 0.1% | 0.000 / -0.037 |
| `kucuk_kademeli_asagi_basamak` | 4 | 795 / 795 / 0 | 100 (1.9%) | +0.032 / -0.032 | +0.046 | 0.450 / 0.435 | 20.1% / 15.1% / 0.1% | -0.021 / -0.057 |
| `kucuk_kademeli_asagi_basamak` | 8 | 787 / 787 / 8 | 100 (1.9%) | +0.067 / -0.015 | +0.076 | 0.650 / 0.562 | 33.7% / 26.1% / 0.1% | 0.011 / -0.057 |
| `kucuk_kademeli_asagi_basamak` | 10 | 787 / 787 / 8 | 100 (1.9%) | +0.083 / -0.030 | +0.102 | 0.779 / 0.714 | 39.3% / 33.7% / 0.1% | 0.041 / -0.100 |
| `kucuk_kademeli_asagi_basamak` | 12 | 785 / 785 / 10 | 100 (1.9%) | +0.068 / +0.000 | +0.073 | 0.873 / 0.770 | 42.3% / 35.2% / 0.1% | 0.090 / -0.082 |
| `kucuk_kademeli_asagi_basamak` | 16 | 785 / 785 / 10 | 100 (1.9%) | -0.022 / -0.079 | -0.003 | 1.040 / 0.923 | 44.7% / 39.9% / 0.2% | 0.057 / -0.296 |
| `tek_buyuk_asagi_basamak` | 1 | 398 / 398 / 0 | 98 (1.8%) | +0.022 / +0.000 | +0.020 | 0.178 / 0.171 | 3.0% / 0.8% / 0.0% | 0.000 / -0.015 |
| `tek_buyuk_asagi_basamak` | 4 | 398 / 398 / 0 | 98 (1.8%) | +0.127 / +0.019 | +0.142 | 0.437 / 0.358 | 21.1% / 10.5% / 0.8% | 0.180 / -0.065 |
| `tek_buyuk_asagi_basamak` | 8 | 398 / 398 / 0 | 98 (1.8%) | +0.035 / -0.003 | +0.049 | 0.656 / 0.505 | 29.6% / 24.1% / 0.8% | 0.270 / -0.222 |
| `tek_buyuk_asagi_basamak` | 10 | 398 / 398 / 0 | 98 (1.8%) | -0.010 / +0.000 | +0.036 | 0.745 / 0.669 | 34.9% / 31.7% / 0.8% | 0.086 / -0.110 |
| `tek_buyuk_asagi_basamak` | 12 | 398 / 398 / 0 | 98 (1.8%) | -0.021 / +0.000 | +0.039 | 0.833 / 0.743 | 36.9% / 32.9% / 0.8% | 0.164 / -0.144 |
| `tek_buyuk_asagi_basamak` | 16 | 398 / 398 / 0 | 98 (1.8%) | -0.169 / -0.118 | -0.085 | 0.883 / 0.802 | 40.2% / 37.4% / 0.8% | 0.047 / -0.288 |

- **KARŞI ÖRNEK:** KLGYO (2026-01-07 13:30, kova=kucuk_kademeli_asagi_basamak): 8x4H korunan=+6.00 ATR (MFE=6.00 / MAE=0.82 ATR) · KARSN (2026-09-01 13:30, kova=tek_buyuk_asagi_basamak): 8x4H korunan=+5.76 ATR (MFE=5.76 / MAE=1.90 ATR)
- **SINIR:** Toplam geçmiş düşüş büyüklüğü hisseden hisseye değişebilir.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.012 ATR) ve MAE farkı (0.057 ATR) sınırlı kaldı.

## STB-BHV-F05 — Yataylaşma sonrası yeni dip yapmamak ek bilgi katıyor mu?

- **TANIM:** Aşağı basamak sonrası ilk tutunma gününde girmek ile 3-6 gün yeni dip yapmadan bekleyip girmek arasındaki getiri ve kaçan hareket farkı.
- **VERİ:** Toplam checkpoint/olay `n=14184`, 8×4H tam ufuk `n=14087`, sağdan sansürlü `n=97`, ATR geçerli `n=14087`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `PROVISIONAL_CANDIDATE_PENDING_USER_CONFIRMATION`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `hemen_ilk_gun_giris` (8×4H n=3223, med=-0.092 ATR, ort=-0.031 ATR, MFE_med=0.632, MAE_med=0.633, top1_sembol=1.5%) vs `yeni_dip_yapmadan_3_6g_sonra` (8×4H n=10864, med=-0.148 ATR, ort=-0.066 ATR, MFE_med=0.606, MAE_med=0.654, top1_sembol=1.6%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `hemen_ilk_gun_giris` | 1 | 3234 / 3234 / 0 | 100 (1.5%) | -0.002 / -0.011 | +0.002 | 0.156 / 0.152 | 4.2% / 3.1% / 0.1% | -0.020 / 0.000 |
| `hemen_ilk_gun_giris` | 4 | 3230 / 3230 / 4 | 100 (1.5%) | -0.028 / -0.085 | -0.014 | 0.417 / 0.415 | 17.6% / 14.8% / 0.2% | -0.044 / -0.114 |
| `hemen_ilk_gun_giris` | 8 | 3223 / 3223 / 11 | 100 (1.5%) | -0.031 / -0.092 | -0.008 | 0.632 / 0.633 | 29.5% / 28.2% / 0.3% | -0.044 / -0.122 |
| `hemen_ilk_gun_giris` | 10 | 3223 / 3223 / 11 | 100 (1.5%) | -0.094 / -0.150 | -0.067 | 0.694 / 0.718 | 33.0% / 33.6% / 0.3% | -0.078 / -0.199 |
| `hemen_ilk_gun_giris` | 12 | 3223 / 3223 / 11 | 100 (1.5%) | -0.141 / -0.211 | -0.106 | 0.763 / 0.801 | 35.3% / 37.6% / 0.3% | -0.117 / -0.273 |
| `hemen_ilk_gun_giris` | 16 | 3223 / 3223 / 11 | 100 (1.5%) | -0.218 / -0.345 | -0.173 | 0.851 / 0.973 | 39.3% / 43.8% / 0.3% | -0.269 / -0.400 |
| `yeni_dip_yapmadan_3_6g_sonra` | 1 | 10950 / 10950 / 0 | 100 (1.6%) | -0.011 / -0.023 | -0.010 | 0.149 / 0.160 | 4.4% / 2.7% / 0.2% | -0.029 / -0.016 |
| `yeni_dip_yapmadan_3_6g_sonra` | 4 | 10944 / 10944 / 6 | 100 (1.6%) | -0.046 / -0.106 | -0.038 | 0.400 / 0.436 | 18.3% / 13.9% / 0.4% | -0.083 / -0.135 |
| `yeni_dip_yapmadan_3_6g_sonra` | 8 | 10864 / 10864 / 86 | 100 (1.6%) | -0.066 / -0.148 | -0.049 | 0.606 / 0.654 | 30.1% / 28.8% / 0.4% | -0.114 / -0.182 |
| `yeni_dip_yapmadan_3_6g_sonra` | 10 | 10787 / 10787 / 163 | 100 (1.6%) | -0.073 / -0.161 | -0.052 | 0.698 / 0.738 | 34.3% / 33.7% / 0.4% | -0.123 / -0.204 |
| `yeni_dip_yapmadan_3_6g_sonra` | 12 | 10695 / 10695 / 255 | 100 (1.6%) | -0.071 / -0.165 | -0.048 | 0.776 / 0.818 | 37.4% / 37.3% / 0.4% | -0.126 / -0.194 |
| `yeni_dip_yapmadan_3_6g_sonra` | 16 | 10511 / 10511 / 439 | 100 (1.6%) | -0.050 / -0.131 | -0.022 | 0.933 / 0.931 | 42.1% / 41.2% / 0.4% | -0.134 / -0.127 |

- **KARŞI ÖRNEK:** KLGYO (2026-01-08 13:30, kova=hemen_ilk_gun_giris): 8x4H korunan=+7.34 ATR (MFE=8.91 / MAE=0.69 ATR) · HALKB (2026-08-25 17:30, kova=yeni_dip_yapmadan_3_6g_sonra): 8x4H korunan=+9.00 ATR (MFE=9.00 / MAE=0.02 ATR)
- **SINIR:** Zorunlu teyit kuralı değildir; aday eşleme kullanıcı grafik teyidi beklemektedir.
- **SONUÇ (`ayrı doğrulama gerekli`):** Aday dikey/yatay eşlemesi altında 8x4H medyan farkı 0.056 ATR, MAE farkı 0.021 ATR [hemen_ilk_gun_giris: med=-0.092 / MAE=0.633 ATR (n=3223), yeni_dip_yapmadan_3_6g_sonra: med=-0.148 / MAE=0.654 ATR (n=10864)]; aday rejim eşlemesi debug niteliğinde olduğundan kesin kural sayılmaz.

## STB-BHV-F06 — Yerleşip tekrar aşağı hareketlenmek tek yerleşmeden farklı mı?

- **TANIM:** İlk kez aşağı yerleşen destek ile öncesinde >=2 kez destek kaybedip tekrar aşağı kayan yapıların karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=1193`, 8×4H tam ufuk `n=1185`, sağdan sansürlü `n=8`, ATR geçerli `n=1185`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `PROVISIONAL_CANDIDATE_PENDING_USER_CONFIRMATION`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `ikinci_veya_sonraki_asagi_kayma` (8×4H n=1108, med=-0.003 ATR, ort=0.065 ATR, MFE_med=0.656, MAE_med=0.533, top1_sembol=1.6%) vs `ilk_asagi_yerlesme` (8×4H n=77, med=-0.119 ATR, ort=-0.061 ATR, MFE_med=0.658, MAE_med=0.731, top1_sembol=9.1%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ikinci_veya_sonraki_asagi_kayma` | 1 | 1116 / 1116 / 0 | 100 (1.6%) | -0.004 / -0.014 | -0.006 | 0.179 / 0.185 | 2.7% / 1.0% / 0.1% | 0.000 / -0.028 |
| `ikinci_veya_sonraki_asagi_kayma` | 4 | 1116 / 1116 / 0 | 100 (1.6%) | +0.073 / +0.000 | +0.075 | 0.443 / 0.400 | 20.0% / 12.9% / 0.4% | 0.062 / -0.065 |
| `ikinci_veya_sonraki_asagi_kayma` | 8 | 1108 / 1108 / 8 | 100 (1.6%) | +0.065 / -0.003 | +0.075 | 0.656 / 0.533 | 32.0% / 24.4% / 0.4% | 0.098 / -0.125 |
| `ikinci_veya_sonraki_asagi_kayma` | 10 | 1108 / 1108 / 8 | 100 (1.6%) | +0.052 / -0.026 | +0.067 | 0.766 / 0.688 | 37.6% / 32.2% / 0.4% | 0.099 / -0.176 |
| `ikinci_veya_sonraki_asagi_kayma` | 12 | 1106 / 1106 / 10 | 100 (1.6%) | +0.044 / +0.000 | +0.056 | 0.855 / 0.751 | 40.5% / 33.7% / 0.4% | 0.124 / -0.100 |
| `ikinci_veya_sonraki_asagi_kayma` | 16 | 1106 / 1106 / 10 | 100 (1.6%) | -0.064 / -0.079 | -0.041 | 0.961 / 0.895 | 43.2% / 38.6% / 0.4% | 0.154 / -0.275 |
| `ilk_asagi_yerlesme` | 1 | 77 / 77 / 0 | 29 (9.1%) | -0.000 / +0.021 | -0.059 | 0.242 / 0.170 | 2.6% / 2.6% / 0.0% | 0.024 / 0.010 |
| `ilk_asagi_yerlesme` | 4 | 77 / 77 / 0 | 29 (9.1%) | -0.063 / -0.199 | -0.149 | 0.449 / 0.562 | 27.3% / 23.4% / 0.0% | -0.246 / 0.071 |
| `ilk_asagi_yerlesme` | 8 | 77 / 77 / 0 | 29 (9.1%) | -0.061 / -0.119 | -0.107 | 0.658 / 0.731 | 36.4% / 40.3% / 0.0% | -0.105 / -0.227 |
| `ilk_asagi_yerlesme` | 10 | 77 / 77 / 0 | 29 (9.1%) | +0.045 / +0.000 | -0.165 | 0.775 / 0.874 | 40.3% / 44.2% / 0.0% | -0.222 / 0.023 |
| `ilk_asagi_yerlesme` | 12 | 77 / 77 / 0 | 29 (9.1%) | -0.045 / -0.010 | -0.174 | 0.881 / 0.985 | 40.3% / 44.2% / 0.0% | -0.018 / 0.029 |
| `ilk_asagi_yerlesme` | 16 | 77 / 77 / 0 | 29 (9.1%) | -0.177 / -0.310 | -0.152 | 0.962 / 1.018 | 42.9% / 45.5% / 0.0% | -0.357 / -0.310 |

- **KARŞI ÖRNEK:** KLGYO (2026-01-07 13:30, kova=ilk_asagi_yerlesme): 8x4H korunan=+6.00 ATR (MFE=6.00 / MAE=0.82 ATR) · KARSN (2026-09-01 13:30, kova=ikinci_veya_sonraki_asagi_kayma): 8x4H korunan=+5.76 ATR (MFE=5.76 / MAE=1.90 ATR)
- **SINIR:** Yalnız olay anına kadar gözlenmiş geçmiş kayıplar kullanılır; aday rejim teyidi kullanıcı onayı bekler.
- **SONUÇ (`ayrı doğrulama gerekli`):** Aday dikey/yatay eşlemesi altında 8x4H medyan farkı 0.116 ATR, MAE farkı 0.198 ATR [ikinci_veya_sonraki_asagi_kayma: med=-0.003 / MAE=0.533 ATR (n=1108), ilk_asagi_yerlesme: med=-0.119 / MAE=0.731 ATR (n=77)]; aday rejim eşlemesi debug niteliğinde olduğundan kesin kural sayılmaz.

## STB-BHV-G01 — Aynı güncel konuma farklı yollardan gelmek fiyatı ayırıyor mu?

- **TANIM:** Destek üstünde 0-1.0 ATR aynı güncel konumdayken bu konuma: geri alımla, aşağı basamakla veya yukarıdan gelişin karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=19594`, 8×4H tam ufuk `n=19369`, sağdan sansürlü `n=225`, ATR geçerli `n=19369`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `asagi_basamakla_yerleserek` (8×4H n=9297, med=-0.066 ATR, ort=-0.028 ATR, MFE_med=0.578, MAE_med=0.517, top1_sembol=2.5%) vs `asagidan_eski_destegi_geri_alarak` (8×4H n=1085, med=0.000 ATR, ort=0.092 ATR, MFE_med=0.684, MAE_med=0.545, top1_sembol=1.8%) vs `yukaridan_cekilerek_veya_yukari_basamakla` (8×4H n=8987, med=-0.070 ATR, ort=-0.007 ATR, MFE_med=0.599, MAE_med=0.558, top1_sembol=1.9%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `asagi_basamakla_yerleserek` | 1 | 9425 / 9425 / 6 | 100 (2.5%) | +0.005 / +0.000 | +0.017 | 0.131 / 0.136 | 3.2% / 1.7% / 0.0% | 0.000 / 0.000 |
| `asagi_basamakla_yerleserek` | 4 | 9395 / 9395 / 36 | 100 (2.5%) | +0.001 / -0.038 | +0.038 | 0.375 / 0.344 | 15.4% / 10.1% / 0.0% | -0.036 / -0.046 |
| `asagi_basamakla_yerleserek` | 8 | 9297 / 9297 / 134 | 100 (2.5%) | -0.028 / -0.066 | +0.029 | 0.578 / 0.517 | 28.0% / 22.4% / 0.0% | -0.054 / -0.082 |
| `asagi_basamakla_yerleserek` | 10 | 9238 / 9238 / 193 | 100 (2.5%) | -0.038 / -0.083 | +0.027 | 0.657 / 0.585 | 32.3% / 27.2% / 0.1% | -0.060 / -0.101 |
| `asagi_basamakla_yerleserek` | 12 | 9172 / 9172 / 259 | 100 (2.5%) | -0.038 / -0.076 | +0.035 | 0.724 / 0.654 | 35.9% / 30.5% / 0.1% | -0.048 / -0.113 |
| `asagi_basamakla_yerleserek` | 16 | 9051 / 9051 / 380 | 100 (2.5%) | -0.035 / -0.087 | +0.050 | 0.861 / 0.761 | 41.3% / 35.5% / 0.1% | -0.025 / -0.146 |
| `asagidan_eski_destegi_geri_alarak` | 1 | 1094 / 1094 / 0 | 100 (1.8%) | +0.012 / +0.000 | +0.011 | 0.136 / 0.150 | 2.9% / 2.0% / 0.0% | 0.000 / 0.000 |
| `asagidan_eski_destegi_geri_alarak` | 4 | 1093 / 1093 / 1 | 100 (1.8%) | +0.032 / +0.000 | +0.040 | 0.482 / 0.386 | 19.2% / 10.7% / 0.0% | 0.038 / -0.048 |
| `asagidan_eski_destegi_geri_alarak` | 8 | 1085 / 1085 / 9 | 100 (1.8%) | +0.092 / +0.000 | +0.106 | 0.684 / 0.545 | 33.8% / 25.6% / 0.0% | 0.031 / -0.016 |
| `asagidan_eski_destegi_geri_alarak` | 10 | 1085 / 1085 / 9 | 100 (1.8%) | +0.060 / -0.043 | +0.069 | 0.766 / 0.640 | 38.6% / 30.5% / 0.0% | 0.000 / -0.104 |
| `asagidan_eski_destegi_geri_alarak` | 12 | 1085 / 1085 / 9 | 100 (1.8%) | +0.096 / +0.000 | +0.112 | 0.868 / 0.710 | 42.6% / 35.0% / 0.0% | 0.132 / -0.105 |
| `asagidan_eski_destegi_geri_alarak` | 16 | 1083 / 1083 / 11 | 100 (1.8%) | +0.097 / +0.000 | +0.119 | 1.047 / 0.859 | 47.4% / 39.1% / 0.1% | 0.160 / -0.138 |
| `yukaridan_cekilerek_veya_yukari_basamakla` | 1 | 9063 / 9063 / 6 | 100 (1.9%) | -0.005 / +0.000 | -0.009 | 0.142 / 0.141 | 3.5% / 2.2% / 0.0% | 0.000 / -0.015 |
| `yukaridan_cekilerek_veya_yukari_basamakla` | 4 | 9039 / 9039 / 30 | 100 (1.9%) | -0.021 / -0.045 | -0.030 | 0.398 / 0.366 | 16.3% / 12.7% / 0.1% | 0.000 / -0.086 |
| `yukaridan_cekilerek_veya_yukari_basamakla` | 8 | 8987 / 8987 / 82 | 100 (1.9%) | -0.007 / -0.070 | -0.017 | 0.599 / 0.558 | 29.7% / 25.4% / 0.2% | 0.021 / -0.160 |
| `yukaridan_cekilerek_veya_yukari_basamakla` | 10 | 8975 / 8975 / 94 | 100 (1.9%) | -0.000 / -0.071 | -0.010 | 0.683 / 0.636 | 34.3% / 30.8% / 0.2% | 0.077 / -0.192 |
| `yukaridan_cekilerek_veya_yukari_basamakla` | 12 | 8969 / 8969 / 100 | 100 (1.9%) | +0.006 / -0.066 | -0.003 | 0.761 / 0.707 | 37.7% / 34.9% / 0.2% | 0.114 / -0.225 |
| `yukaridan_cekilerek_veya_yukari_basamakla` | 16 | 8953 / 8953 / 116 | 100 (1.9%) | +0.019 / -0.067 | +0.018 | 0.914 / 0.844 | 42.4% / 40.1% / 0.2% | 0.167 / -0.280 |

- **KARŞI ÖRNEK:** GWIND (2026-04-27 17:30, kova=yukaridan_cekilerek_veya_yukari_basamakla): 8x4H korunan=+6.76 ATR (MFE=7.94 / MAE=0.33 ATR) · DIRIT (2025-12-10 17:30, kova=asagi_basamakla_yerleserek): 8x4H korunan=+8.11 ATR (MFE=8.11 / MAE=0.00 ATR) · DMSAS (2026-09-14 18:00, kova=asagidan_eski_destegi_geri_alarak): 8x4H korunan=-4.70 ATR (MFE=0.00 / MAE=4.93 ATR)
- **SINIR:** Tek satırlık statik 'destek üstünde' etiketinin arkasındaki yol farkını sınar.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.070 ATR, MAE farkı 0.042 ATR düzeyinde ayrıştı.

## STB-BHV-G02 — Aynı fiyat civarındaki eski ve yeni teyit edilen destek farklı mı?

- **TANIM:** Desteğe 0-1.2 ATR yakınlıkta yeni teyit edilmiş (0-3g) destek ile >=15 günlük eski desteğin ileri davranış farkı.
- **VERİ:** Toplam checkpoint/olay `n=11646`, 8×4H tam ufuk `n=11557`, sağdan sansürlü `n=89`, ATR geçerli `n=11557`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `eski_yasli_destek_15g_ustu` (8×4H n=2680, med=0.000 ATR, ort=-0.000 ATR, MFE_med=0.627, MAE_med=0.539, top1_sembol=6.1%) vs `yeni_teyitli_destek_0_3g` (8×4H n=8877, med=-0.069 ATR, ort=-0.017 ATR, MFE_med=0.585, MAE_med=0.531, top1_sembol=1.9%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `eski_yasli_destek_15g_ustu` | 1 | 2688 / 2688 / 0 | 96 (6.1%) | +0.011 / +0.000 | +0.011 | 0.149 / 0.153 | 4.2% / 1.4% / 0.0% | 0.000 / 0.000 |
| `eski_yasli_destek_15g_ustu` | 4 | 2688 / 2688 / 0 | 96 (6.1%) | +0.019 / -0.007 | +0.027 | 0.410 / 0.369 | 18.7% / 11.6% / 0.1% | 0.029 / -0.058 |
| `eski_yasli_destek_15g_ustu` | 8 | 2680 / 2680 / 8 | 96 (6.1%) | -0.000 / +0.000 | +0.008 | 0.627 / 0.539 | 31.5% / 24.5% / 0.1% | 0.075 / -0.038 |
| `eski_yasli_destek_15g_ustu` | 10 | 2676 / 2676 / 12 | 96 (6.1%) | +0.002 / +0.000 | +0.050 | 0.706 / 0.621 | 36.2% / 29.2% / 0.1% | 0.099 / -0.055 |
| `eski_yasli_destek_15g_ustu` | 12 | 2674 / 2674 / 14 | 96 (6.1%) | -0.003 / +0.000 | +0.044 | 0.780 / 0.692 | 40.0% / 33.2% / 0.1% | 0.095 / -0.112 |
| `eski_yasli_destek_15g_ustu` | 16 | 2674 / 2674 / 14 | 96 (6.1%) | -0.037 / -0.019 | -0.009 | 0.941 / 0.798 | 44.5% / 37.3% / 0.1% | 0.082 / -0.142 |
| `yeni_teyitli_destek_0_3g` | 1 | 8953 / 8953 / 5 | 100 (1.9%) | +0.004 / +0.000 | +0.005 | 0.137 / 0.135 | 3.4% / 2.1% / 0.0% | 0.000 / 0.000 |
| `yeni_teyitli_destek_0_3g` | 4 | 8932 / 8932 / 26 | 100 (1.9%) | -0.001 / -0.029 | +0.004 | 0.390 / 0.346 | 16.4% / 11.7% / 0.1% | -0.020 / -0.037 |
| `yeni_teyitli_destek_0_3g` | 8 | 8877 / 8877 / 81 | 100 (1.9%) | -0.017 / -0.069 | -0.012 | 0.585 / 0.531 | 28.7% / 23.6% / 0.1% | 0.000 / -0.125 |
| `yeni_teyitli_destek_0_3g` | 10 | 8870 / 8870 / 88 | 100 (1.9%) | -0.044 / -0.093 | -0.043 | 0.661 / 0.603 | 32.9% / 28.6% / 0.1% | 0.000 / -0.178 |
| `yeni_teyitli_destek_0_3g` | 12 | 8857 / 8857 / 101 | 100 (1.9%) | -0.067 / -0.099 | -0.061 | 0.725 / 0.680 | 36.2% / 32.7% / 0.1% | 0.046 / -0.248 |
| `yeni_teyitli_destek_0_3g` | 16 | 8773 / 8773 / 185 | 100 (1.9%) | -0.082 / -0.137 | -0.070 | 0.866 / 0.819 | 41.3% / 38.4% / 0.2% | 0.088 / -0.324 |

- **KARŞI ÖRNEK:** BEGYO (2026-10-09 18:00, kova=yeni_teyitli_destek_0_3g): 8x4H korunan=+6.71 ATR (MFE=6.71 / MAE=0.00 ATR) · DARDL (2025-05-12 17:30, kova=eski_yasli_destek_15g_ustu): 8x4H korunan=-9.15 ATR (MFE=0.03 / MAE=9.18 ATR)
- **SINIR:** Yaşı bilinmeyen ilk arşiv epizotları dışlanmıştır.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.069 ATR) ve MAE farkı (0.008 ATR) sınırlı kaldı.

## STB-BHV-G03 — Eski ve yeni destek arasında gidip gelince hangi seviye açıklayıcı?

- **TANIM:** Destek aşağı taşındıktan sonra yeni alt destek ile kırılan eski üst destek koridorunda kalan fiyatın alt/üst yarı davranışı.
- **VERİ:** Toplam checkpoint/olay `n=15543`, 8×4H tam ufuk `n=15369`, sağdan sansürlü `n=174`, ATR geçerli `n=15369`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `eski_ust_destege_yakin` (8×4H n=6651, med=-0.095 ATR, ort=-0.012 ATR, MFE_med=0.626, MAE_med=0.594, top1_sembol=2.5%) vs `yeni_alt_destege_yakin` (8×4H n=8718, med=-0.088 ATR, ort=-0.037 ATR, MFE_med=0.574, MAE_med=0.554, top1_sembol=4.3%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `eski_ust_destege_yakin` | 1 | 6678 / 6678 / 3 | 100 (2.5%) | +0.003 / -0.011 | +0.003 | 0.148 / 0.154 | 4.3% / 2.1% / 0.0% | -0.013 / -0.010 |
| `eski_ust_destege_yakin` | 4 | 6671 / 6671 / 10 | 100 (2.5%) | -0.003 / -0.069 | -0.003 | 0.408 / 0.403 | 17.7% / 12.1% / 0.2% | -0.067 / -0.071 |
| `eski_ust_destege_yakin` | 8 | 6651 / 6651 / 30 | 100 (2.5%) | -0.012 / -0.095 | -0.017 | 0.626 / 0.594 | 30.4% / 24.7% / 0.2% | -0.097 / -0.093 |
| `eski_ust_destege_yakin` | 10 | 6636 / 6636 / 45 | 100 (2.5%) | -0.017 / -0.101 | -0.021 | 0.704 / 0.668 | 34.6% / 29.2% / 0.2% | -0.125 / -0.080 |
| `eski_ust_destege_yakin` | 12 | 6625 / 6625 / 56 | 100 (2.5%) | -0.026 / -0.103 | -0.029 | 0.788 / 0.735 | 37.8% / 32.8% / 0.2% | -0.124 / -0.090 |
| `eski_ust_destege_yakin` | 16 | 6579 / 6579 / 102 | 100 (2.5%) | -0.042 / -0.131 | -0.047 | 0.924 / 0.864 | 43.0% / 38.0% / 0.2% | -0.133 / -0.129 |
| `yeni_alt_destege_yakin` | 1 | 8854 / 8854 / 8 | 100 (4.3%) | +0.001 / +0.000 | +0.010 | 0.132 / 0.141 | 3.2% / 1.9% / 0.1% | 0.000 / 0.000 |
| `yeni_alt_destege_yakin` | 4 | 8818 / 8818 / 44 | 100 (4.3%) | -0.008 / -0.063 | +0.029 | 0.373 / 0.367 | 15.2% / 10.9% / 0.1% | -0.045 / -0.076 |
| `yeni_alt_destege_yakin` | 8 | 8718 / 8718 / 144 | 100 (4.3%) | -0.037 / -0.088 | +0.013 | 0.574 / 0.554 | 27.4% / 24.0% / 0.1% | -0.046 / -0.129 |
| `yeni_alt_destege_yakin` | 10 | 8652 / 8652 / 210 | 100 (4.3%) | -0.047 / -0.091 | +0.016 | 0.652 / 0.626 | 31.8% / 28.9% / 0.1% | -0.038 / -0.144 |
| `yeni_alt_destege_yakin` | 12 | 8575 / 8575 / 287 | 100 (4.3%) | -0.046 / -0.096 | +0.031 | 0.723 / 0.702 | 35.3% / 32.5% / 0.1% | -0.032 / -0.168 |
| `yeni_alt_destege_yakin` | 16 | 8418 / 8418 / 444 | 100 (4.3%) | -0.055 / -0.087 | +0.037 | 0.867 / 0.803 | 40.8% / 37.5% / 0.1% | -0.012 / -0.169 |

- **KARŞI ÖRNEK:** HALKB (2026-08-25 17:30, kova=eski_ust_destege_yakin): 8x4H korunan=+9.00 ATR (MFE=9.00 / MAE=0.02 ATR) · DIRIT (2025-12-10 17:30, kova=yeni_alt_destege_yakin): 8x4H korunan=+8.11 ATR (MFE=8.11 / MAE=0.00 ATR)
- **SINIR:** Her iki seviye de checkpoint anında nedensel olarak bilinmektedir.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.007 ATR, MAE farkı 0.039 ATR düzeyinde ayrıştı.

## STB-BHV-G04 — Önceki başarısız destekler yeni desteğin sonucunu etkiliyor mu?

- **TANIM:** Yeni destek teyidinde arşiv içinde daha önce SUPPORT_LOST yaşamamış olanlar ile yaşamış olanların karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=2401`, 8×4H tam ufuk `n=2384`, sağdan sansürlü `n=17`, ATR geçerli `n=2384`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `gecmiste_en_az_1_kayip_var` (8×4H n=2346, med=-0.022 ATR, ort=0.055 ATR, MFE_med=0.677, MAE_med=0.567, top1_sembol=1.3%) vs `gecmiste_kayip_yok` (8×4H n=38, med=-0.053 ATR, ort=-0.086 ATR, MFE_med=0.718, MAE_med=0.551, top1_sembol=26.3%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `gecmiste_en_az_1_kayip_var` | 1 | 2363 / 2363 / 0 | 100 (1.3%) | -0.013 / -0.019 | -0.014 | 0.183 / 0.201 | 3.0% / 2.2% / 0.0% | 0.000 / -0.026 |
| `gecmiste_en_az_1_kayip_var` | 4 | 2362 / 2362 / 1 | 100 (1.3%) | +0.057 / +0.000 | +0.055 | 0.463 / 0.420 | 20.9% / 14.6% / 0.2% | 0.028 / -0.037 |
| `gecmiste_en_az_1_kayip_var` | 8 | 2346 / 2346 / 17 | 100 (1.3%) | +0.055 / -0.022 | +0.053 | 0.677 / 0.567 | 33.5% / 25.7% / 0.2% | 0.029 / -0.067 |
| `gecmiste_en_az_1_kayip_var` | 10 | 2346 / 2346 / 17 | 100 (1.3%) | +0.063 / +0.000 | +0.063 | 0.816 / 0.718 | 39.2% / 32.6% / 0.2% | 0.056 / -0.108 |
| `gecmiste_en_az_1_kayip_var` | 12 | 2342 / 2342 / 21 | 100 (1.3%) | +0.062 / +0.012 | +0.058 | 0.904 / 0.767 | 42.1% / 34.9% / 0.2% | 0.112 / -0.082 |
| `gecmiste_en_az_1_kayip_var` | 16 | 2341 / 2341 / 22 | 100 (1.3%) | +0.011 / -0.078 | +0.006 | 1.038 / 0.912 | 45.3% / 39.6% / 0.2% | 0.164 / -0.244 |
| `gecmiste_kayip_yok` | 1 | 38 / 38 / 0 | 11 (26.3%) | +0.002 / +0.000 | +0.043 | 0.262 / 0.168 | 2.6% / 2.6% / 0.0% | 0.024 / -0.033 |
| `gecmiste_kayip_yok` | 4 | 38 / 38 / 0 | 11 (26.3%) | -0.043 / -0.079 | +0.167 | 0.552 / 0.335 | 23.7% / 21.1% / 0.0% | -0.238 / 0.107 |
| `gecmiste_kayip_yok` | 8 | 38 / 38 / 0 | 11 (26.3%) | -0.086 / -0.053 | +0.145 | 0.718 / 0.551 | 34.2% / 36.8% / 0.0% | -0.135 / 0.101 |
| `gecmiste_kayip_yok` | 10 | 38 / 38 / 0 | 11 (26.3%) | -0.145 / -0.321 | -0.322 | 0.762 / 0.873 | 34.2% / 42.1% / 0.0% | -0.327 / 0.098 |
| `gecmiste_kayip_yok` | 12 | 38 / 38 / 0 | 11 (26.3%) | -0.183 / -0.208 | -0.500 | 0.762 / 1.266 | 34.2% / 44.7% / 0.0% | -0.423 / 0.163 |
| `gecmiste_kayip_yok` | 16 | 38 / 38 / 0 | 11 (26.3%) | -0.462 / -0.729 | -1.072 | 0.795 / 1.408 | 36.8% / 47.4% / 0.0% | -0.822 / -0.337 |

- **KARŞI ÖRNEK:** KLGYO (2026-01-07 13:30, kova=gecmiste_en_az_1_kayip_var): 8x4H korunan=+6.00 ATR (MFE=6.00 / MAE=0.82 ATR) · ESEN (2025-06-30 13:30, kova=gecmiste_kayip_yok): 8x4H korunan=+3.02 ATR (MFE=3.27 / MAE=0.29 ATR)
- **SINIR:** Arşiv öncesi dönem sıfır sayılmaz; ilk epizotlar dışlanmıştır.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.031 ATR) ve MAE farkı (0.016 ATR) sınırlı kaldı.

## STB-BHV-G05 — İki yönlü savrulma artınca yön avantajı kayboluyor mu?

- **TANIM:** 4H mum aralığı >=0.65 günlük ATR olan yüksek savrulmalı anlar ile daha sakin anlarda MFE/MAE simetrisi ve korunan kapanış.
- **VERİ:** Toplam checkpoint/olay `n=107441`, 8×4H tam ufuk `n=106641`, sağdan sansürlü `n=800`, ATR geçerli `n=106641`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `normal_dar_mum_araligi` (8×4H n=79725, med=-0.041 ATR, ort=0.031 ATR, MFE_med=0.665, MAE_med=0.586, top1_sembol=1.3%) vs `yuksek_iki_yonlu_savrulma` (8×4H n=26916, med=-0.038 ATR, ort=0.032 ATR, MFE_med=0.770, MAE_med=0.682, top1_sembol=1.3%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `normal_dar_mum_araligi` | 1 | 80231 / 80231 / 94 | 100 (1.3%) | +0.006 / +0.000 | +0.006 | 0.153 / 0.143 | 4.9% / 2.6% / 0.1% | 0.000 / 0.000 |
| `normal_dar_mum_araligi` | 4 | 80003 / 80003 / 322 | 100 (1.3%) | +0.019 / -0.028 | +0.019 | 0.439 / 0.387 | 19.3% / 13.1% / 0.2% | 0.000 / -0.070 |
| `normal_dar_mum_araligi` | 8 | 79725 / 79725 / 600 | 100 (1.3%) | +0.031 / -0.041 | +0.033 | 0.665 / 0.586 | 32.9% / 26.4% / 0.2% | 0.029 / -0.117 |
| `normal_dar_mum_araligi` | 10 | 79538 / 79538 / 787 | 100 (1.3%) | +0.041 / -0.033 | +0.043 | 0.755 / 0.662 | 37.0% / 30.9% / 0.2% | 0.059 / -0.130 |
| `normal_dar_mum_araligi` | 12 | 79371 / 79371 / 954 | 100 (1.3%) | +0.046 / -0.035 | +0.049 | 0.835 / 0.733 | 40.2% / 34.2% / 0.2% | 0.071 / -0.150 |
| `normal_dar_mum_araligi` | 16 | 79022 / 79022 / 1303 | 100 (1.3%) | +0.067 / -0.028 | +0.071 | 0.992 / 0.861 | 44.8% / 38.6% / 0.3% | 0.122 / -0.184 |
| `yuksek_iki_yonlu_savrulma` | 1 | 27110 / 27110 / 6 | 100 (1.3%) | -0.006 / +0.000 | -0.006 | 0.168 / 0.183 | 4.3% / 2.9% / 0.1% | -0.006 / 0.000 |
| `yuksek_iki_yonlu_savrulma` | 4 | 27038 / 27038 / 78 | 100 (1.3%) | +0.003 / -0.048 | -0.002 | 0.522 / 0.473 | 24.0% / 18.2% / 0.5% | -0.012 / -0.082 |
| `yuksek_iki_yonlu_savrulma` | 8 | 26916 / 26916 / 200 | 100 (1.3%) | +0.032 / -0.038 | +0.022 | 0.770 / 0.682 | 36.9% / 30.7% / 0.5% | 0.013 / -0.101 |
| `yuksek_iki_yonlu_savrulma` | 10 | 26903 / 26903 / 213 | 100 (1.3%) | +0.032 / -0.057 | +0.021 | 0.876 / 0.786 | 41.3% / 35.5% / 0.5% | 0.028 / -0.137 |
| `yuksek_iki_yonlu_savrulma` | 12 | 26870 / 26870 / 246 | 100 (1.3%) | +0.046 / -0.039 | +0.032 | 0.986 / 0.878 | 44.3% / 38.9% / 0.6% | 0.073 / -0.157 |
| `yuksek_iki_yonlu_savrulma` | 16 | 26819 / 26819 / 297 | 100 (1.3%) | +0.044 / -0.054 | +0.025 | 1.144 / 1.017 | 47.4% / 42.3% / 0.6% | 0.110 / -0.225 |

- **KARŞI ÖRNEK:** ESEN (2025-08-12 17:30, kova=normal_dar_mum_araligi): 8x4H korunan=+11.63 ATR (MFE=11.63 / MAE=0.00 ATR) · ESEN (2025-08-11 17:30, kova=yuksek_iki_yonlu_savrulma): 8x4H korunan=+10.72 ATR (MFE=10.72 / MAE=0.17 ATR)
- **SINIR:** Yalnız yukarı MFE değil, MAE ve aynı mumda çift eşik belirsizliği birlikte okunur.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.003 ATR) ve MAE farkı (0.096 ATR) sınırlı kaldı.

## STB-BHV-G06 — Hacim/4H alıcı kanıtı hangi yolda ek bilgi veya gecikme getiriyor?

- **TANIM:** Destek teması ve geri alım anlarında native H4 bull_displacement + hacim onayı olanlar ile olmayanların karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=4037`, 8×4H tam ufuk `n=3941`, sağdan sansürlü `n=96`, ATR geçerli `n=3941`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `4h_alici_kaniti_yok_veya_hacim_zayif` (8×4H n=3399, med=-0.077 ATR, ort=-0.012 ATR, MFE_med=0.597, MAE_med=0.612, top1_sembol=3.7%) vs `4h_alici_ve_hacim_kaniti_var` (8×4H n=542, med=0.058 ATR, ort=0.150 ATR, MFE_med=0.825, MAE_med=0.537, top1_sembol=2.3%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `4h_alici_kaniti_yok_veya_hacim_zayif` | 1 | 3474 / 3474 / 2 | 100 (3.7%) | -0.014 / +0.000 | -0.020 | 0.134 / 0.155 | 2.9% / 2.4% / 0.0% | 0.000 / 0.000 |
| `4h_alici_kaniti_yok_veya_hacim_zayif` | 4 | 3456 / 3456 / 20 | 100 (3.7%) | -0.035 / -0.073 | -0.034 | 0.394 / 0.404 | 16.2% / 13.3% / 0.0% | -0.033 / -0.121 |
| `4h_alici_kaniti_yok_veya_hacim_zayif` | 8 | 3399 / 3399 / 77 | 100 (3.7%) | -0.012 / -0.077 | -0.018 | 0.597 / 0.612 | 28.9% / 27.8% / 0.1% | 0.000 / -0.142 |
| `4h_alici_kaniti_yok_veya_hacim_zayif` | 10 | 3386 / 3386 / 90 | 100 (3.7%) | -0.014 / -0.091 | -0.026 | 0.684 / 0.697 | 33.6% / 32.6% / 0.1% | 0.000 / -0.166 |
| `4h_alici_kaniti_yok_veya_hacim_zayif` | 12 | 3371 / 3371 / 105 | 100 (3.7%) | +0.003 / -0.062 | +0.006 | 0.776 / 0.761 | 37.5% / 36.6% / 0.1% | 0.000 / -0.184 |
| `4h_alici_kaniti_yok_veya_hacim_zayif` | 16 | 3347 / 3347 / 129 | 100 (3.7%) | +0.016 / -0.047 | +0.036 | 0.916 / 0.885 | 41.9% / 41.6% / 0.2% | 0.084 / -0.207 |
| `4h_alici_ve_hacim_kaniti_var` | 1 | 561 / 561 / 0 | 100 (2.3%) | -0.021 / +0.000 | -0.021 | 0.119 / 0.165 | 3.4% / 4.1% / 0.0% | 0.000 / -0.017 |
| `4h_alici_ve_hacim_kaniti_var` | 4 | 558 / 558 / 3 | 100 (2.3%) | -0.011 / -0.018 | +0.008 | 0.560 / 0.406 | 24.7% / 14.5% / 0.4% | 0.030 / -0.102 |
| `4h_alici_ve_hacim_kaniti_var` | 8 | 542 / 542 / 19 | 100 (2.3%) | +0.150 / +0.058 | +0.238 | 0.825 / 0.537 | 42.1% / 24.0% / 0.4% | 0.140 / 0.000 |
| `4h_alici_ve_hacim_kaniti_var` | 10 | 542 / 542 / 19 | 100 (2.3%) | +0.126 / +0.047 | +0.198 | 0.961 / 0.589 | 46.3% / 29.0% / 0.4% | 0.069 / 0.018 |
| `4h_alici_ve_hacim_kaniti_var` | 12 | 542 / 542 / 19 | 100 (2.3%) | +0.176 / +0.089 | +0.215 | 1.045 / 0.695 | 48.7% / 34.0% / 0.4% | 0.275 / -0.100 |
| `4h_alici_ve_hacim_kaniti_var` | 16 | 542 / 542 / 19 | 100 (2.3%) | +0.179 / +0.027 | +0.288 | 1.187 / 0.833 | 53.1% / 37.6% / 0.4% | 0.321 / -0.206 |

- **KARŞI ÖRNEK:** AKFYE (2026-09-07 17:30, kova=4h_alici_kaniti_yok_veya_hacim_zayif): 8x4H korunan=+6.74 ATR (MFE=7.63 / MAE=0.36 ATR) · BJKAS (2025-12-18 18:00, kova=4h_alici_ve_hacim_kaniti_var): 8x4H korunan=-6.49 ATR (MFE=0.00 / MAE=6.69 ATR)
- **SINIR:** Eksik hacim olumlu teyit sayılmaz.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.135 ATR, MAE farkı 0.075 ATR düzeyinde ayrıştı.

## STB-BHV-H01 — Benzer fiyat düşüşlerinden sonra Stabil olayı olmadan da aynı tepki var mı?

- **TANIM:** Son 12x4H içinde <=-1.2 ATR benzer düşüş yaşamış barlarda Stabil temas/geri alımı olanlar ile olmayan kontrol grubunun tepkisi.
- **VERİ:** Toplam checkpoint/olay `n=17658`, 8×4H tam ufuk `n=17274`, sağdan sansürlü `n=384`, ATR geçerli `n=17274`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `benzer_dusus_stabil_olayi_yok` (8×4H n=16466, med=-0.117 ATR, ort=-0.093 ATR, MFE_med=0.609, MAE_med=0.658, top1_sembol=1.6%) vs `stabil_temas_veya_geri_alim_var` (8×4H n=808, med=-0.125 ATR, ort=-0.016 ATR, MFE_med=0.621, MAE_med=0.644, top1_sembol=2.3%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `benzer_dusus_stabil_olayi_yok` | 1 | 16755 / 16755 / 68 | 100 (1.6%) | -0.018 / -0.011 | -0.015 | 0.141 / 0.151 | 3.6% / 3.6% / 0.1% | -0.016 / 0.000 |
| `benzer_dusus_stabil_olayi_yok` | 4 | 16584 / 16584 / 239 | 100 (1.6%) | -0.065 / -0.082 | -0.053 | 0.402 / 0.434 | 16.8% / 17.7% / 0.2% | -0.082 / -0.083 |
| `benzer_dusus_stabil_olayi_yok` | 8 | 16466 / 16466 / 357 | 100 (1.6%) | -0.093 / -0.117 | -0.076 | 0.609 / 0.658 | 28.7% / 31.5% / 0.3% | -0.139 / -0.096 |
| `benzer_dusus_stabil_olayi_yok` | 10 | 16428 / 16428 / 395 | 100 (1.6%) | -0.083 / -0.100 | -0.064 | 0.687 / 0.742 | 32.7% / 36.0% / 0.3% | -0.127 / -0.067 |
| `benzer_dusus_stabil_olayi_yok` | 12 | 16418 / 16418 / 405 | 100 (1.6%) | -0.066 / -0.078 | -0.044 | 0.761 / 0.820 | 35.7% / 39.2% / 0.3% | -0.107 / -0.042 |
| `benzer_dusus_stabil_olayi_yok` | 16 | 16398 / 16398 / 425 | 100 (1.6%) | -0.036 / -0.042 | -0.009 | 0.912 / 0.939 | 40.2% / 43.0% / 0.3% | -0.038 / -0.047 |
| `stabil_temas_veya_geri_alim_var` | 1 | 835 / 835 / 0 | 99 (2.3%) | -0.019 / +0.000 | -0.035 | 0.150 / 0.164 | 3.2% / 4.0% / 0.0% | 0.000 / 0.000 |
| `stabil_temas_veya_geri_alim_var` | 4 | 826 / 826 / 9 | 99 (2.3%) | -0.079 / -0.114 | -0.070 | 0.409 / 0.456 | 16.1% / 16.3% / 0.0% | -0.121 / -0.105 |
| `stabil_temas_veya_geri_alim_var` | 8 | 808 / 808 / 27 | 99 (2.3%) | -0.016 / -0.125 | -0.020 | 0.621 / 0.644 | 29.0% / 29.9% / 0.1% | -0.187 / -0.015 |
| `stabil_temas_veya_geri_alim_var` | 10 | 805 / 805 / 30 | 99 (2.3%) | -0.022 / -0.152 | -0.022 | 0.674 / 0.741 | 32.4% / 35.2% / 0.1% | -0.264 / 0.052 |
| `stabil_temas_veya_geri_alim_var` | 12 | 804 / 804 / 31 | 99 (2.3%) | -0.015 / -0.131 | +0.013 | 0.751 / 0.824 | 35.3% / 38.9% / 0.1% | -0.234 / 0.000 |
| `stabil_temas_veya_geri_alim_var` | 16 | 804 / 804 / 31 | 99 (2.3%) | -0.041 / -0.109 | +0.015 | 0.859 / 0.964 | 38.7% / 44.9% / 0.1% | -0.181 / -0.059 |

- **KARŞI ÖRNEK:** HEDEF (2026-07-29 13:30, kova=benzer_dusus_stabil_olayi_yok): 8x4H korunan=+8.02 ATR (MFE=8.09 / MAE=0.00 ATR) · FONET (2025-10-08 18:00, kova=stabil_temas_veya_geri_alim_var): 8x4H korunan=+6.27 ATR (MFE=7.75 / MAE=0.00 ATR)
- **SINIR:** Basit düşüş eşleştirmesidir; tam saat/oynaklık ikiz eşleştirmesi ek incelik sağlayabilir.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.008 ATR, MAE farkı 0.013 ATR düzeyinde ayrıştı.

## STB-BHV-H02 — Basit/gecikmeli referans seviyeleri aynı ayrımı yapıyor mu?

- **TANIM:** Stabil günlük pivot destek teması ile önceden sabitlenmiş basit 20-günlük dip yakınlığının ileri getiri ve MAE karşılaştırması.
- **VERİ:** Toplam checkpoint/olay `n=17761`, 8×4H tam ufuk `n=17417`, sağdan sansürlü `n=344`, ATR geçerli `n=17417`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `basit_20g_dip_kontrol_temasi` (8×4H n=13540, med=-0.059 ATR, ort=-0.014 ATR, MFE_med=0.569, MAE_med=0.531, top1_sembol=2.4%) vs `stabil_destek_temasi` (8×4H n=3877, med=-0.046 ATR, ort=0.012 ATR, MFE_med=0.623, MAE_med=0.599, top1_sembol=3.5%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `basit_20g_dip_kontrol_temasi` | 1 | 13759 / 13759 / 30 | 100 (2.4%) | -0.009 / -0.011 | -0.006 | 0.123 / 0.131 | 2.9% / 2.1% / 0.0% | -0.017 / 0.000 |
| `basit_20g_dip_kontrol_temasi` | 4 | 13662 / 13662 / 127 | 100 (2.4%) | -0.026 / -0.049 | -0.011 | 0.362 / 0.350 | 15.0% / 12.4% / 0.1% | -0.039 / -0.058 |
| `basit_20g_dip_kontrol_temasi` | 8 | 13540 / 13540 / 249 | 100 (2.4%) | -0.014 / -0.059 | +0.021 | 0.569 / 0.531 | 28.0% / 24.6% / 0.1% | -0.039 / -0.086 |
| `basit_20g_dip_kontrol_temasi` | 10 | 13483 / 13483 / 306 | 100 (2.4%) | -0.002 / -0.043 | +0.045 | 0.656 / 0.606 | 32.2% / 29.1% / 0.2% | 0.000 / -0.091 |
| `basit_20g_dip_kontrol_temasi` | 12 | 13439 / 13439 / 350 | 100 (2.4%) | +0.010 / -0.021 | +0.063 | 0.738 / 0.677 | 35.5% / 32.4% / 0.2% | 0.036 / -0.086 |
| `basit_20g_dip_kontrol_temasi` | 16 | 13372 / 13372 / 417 | 100 (2.4%) | +0.046 / +0.000 | +0.115 | 0.884 / 0.785 | 40.5% / 36.8% / 0.2% | 0.114 / -0.104 |
| `stabil_destek_temasi` | 1 | 3970 / 3970 / 2 | 100 (3.5%) | -0.013 / +0.000 | -0.015 | 0.132 / 0.155 | 3.0% / 2.6% / 0.0% | 0.000 / 0.000 |
| `stabil_destek_temasi` | 4 | 3949 / 3949 / 23 | 100 (3.5%) | -0.030 / -0.067 | -0.027 | 0.404 / 0.404 | 17.3% / 13.4% / 0.1% | -0.029 / -0.106 |
| `stabil_destek_temasi` | 8 | 3877 / 3877 / 95 | 100 (3.5%) | +0.012 / -0.046 | +0.014 | 0.623 / 0.599 | 30.6% / 27.2% / 0.1% | 0.000 / -0.114 |
| `stabil_destek_temasi` | 10 | 3864 / 3864 / 108 | 100 (3.5%) | +0.007 / -0.072 | +0.005 | 0.712 / 0.681 | 35.2% / 32.0% / 0.2% | -0.011 / -0.131 |
| `stabil_destek_temasi` | 12 | 3849 / 3849 / 123 | 100 (3.5%) | +0.025 / -0.035 | +0.033 | 0.804 / 0.752 | 38.9% / 36.1% / 0.2% | 0.000 / -0.136 |
| `stabil_destek_temasi` | 16 | 3825 / 3825 / 147 | 100 (3.5%) | +0.035 / -0.035 | +0.053 | 0.954 / 0.876 | 43.4% / 41.0% / 0.2% | 0.088 / -0.177 |

- **KARŞI ÖRNEK:** AKFYE (2026-09-07 17:30, kova=stabil_destek_temasi): 8x4H korunan=+6.74 ATR (MFE=7.63 / MAE=0.36 ATR) · AKFYE (2026-09-07 18:00, kova=basit_20g_dip_kontrol_temasi): 8x4H korunan=+6.62 ATR (MFE=7.84 / MAE=0.07 ATR)
- **SINIR:** Kontrol seviyesi sonuçlara bakılmadan 20-günlük dip olarak sabitlenmiştir.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.014 ATR) ve MAE farkı (0.068 ATR) sınırlı kaldı.

## STB-BHV-H03 — Aynı yol farklı piyasa rejimlerinde korunuyor mu?

- **TANIM:** Destek teması ve geri alım olaylarının o anda nedensel olarak bilinen XU100 > EMA34 vs XU100 < EMA34 endeks rejimindeki davranışı.
- **VERİ:** Toplam checkpoint/olay `n=4037`, 8×4H tam ufuk `n=3941`, sağdan sansürlü `n=96`, ATR geçerli `n=3941`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `XU100_ABOVE_EMA34` (8×4H n=1829, med=-0.131 ATR, ort=-0.100 ATR, MFE_med=0.562, MAE_med=0.625, top1_sembol=3.1%) vs `XU100_BELOW_EMA34` (8×4H n=2112, med=0.000 ATR, ort=0.106 ATR, MFE_med=0.668, MAE_med=0.586, top1_sembol=3.9%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `XU100_ABOVE_EMA34` | 1 | 1829 / 1829 / 0 | 100 (3.1%) | -0.019 / +0.000 | -0.023 | 0.126 / 0.150 | 2.8% / 2.1% / 0.0% | 0.000 / 0.000 |
| `XU100_ABOVE_EMA34` | 4 | 1829 / 1829 / 0 | 100 (3.1%) | -0.069 / -0.086 | -0.073 | 0.395 / 0.408 | 16.5% / 13.6% / 0.2% | -0.036 / -0.162 |
| `XU100_ABOVE_EMA34` | 8 | 1829 / 1829 / 0 | 100 (3.1%) | -0.100 / -0.131 | -0.092 | 0.562 / 0.625 | 28.1% / 28.8% / 0.2% | -0.063 / -0.244 |
| `XU100_ABOVE_EMA34` | 10 | 1829 / 1829 / 0 | 100 (3.1%) | -0.126 / -0.176 | -0.138 | 0.640 / 0.729 | 32.3% / 34.5% / 0.2% | -0.087 / -0.308 |
| `XU100_ABOVE_EMA34` | 12 | 1829 / 1829 / 0 | 100 (3.1%) | -0.117 / -0.210 | -0.105 | 0.738 / 0.812 | 36.5% / 38.8% / 0.3% | -0.098 / -0.344 |
| `XU100_ABOVE_EMA34` | 16 | 1829 / 1829 / 0 | 100 (3.1%) | -0.126 / -0.230 | -0.091 | 0.869 / 0.958 | 40.9% / 43.5% / 0.3% | -0.096 / -0.374 |
| `XU100_BELOW_EMA34` | 1 | 2206 / 2206 / 2 | 100 (3.9%) | -0.011 / +0.000 | -0.009 | 0.137 / 0.162 | 3.0% / 3.1% / 0.0% | 0.000 / 0.000 |
| `XU100_BELOW_EMA34` | 4 | 2185 / 2185 / 23 | 100 (3.9%) | -0.000 / -0.046 | +0.016 | 0.415 / 0.404 | 18.0% / 13.4% / 0.0% | -0.047 / -0.046 |
| `XU100_BELOW_EMA34` | 8 | 2112 / 2112 / 96 | 100 (3.9%) | +0.106 / +0.000 | +0.113 | 0.668 / 0.586 | 33.0% / 26.0% / 0.1% | 0.028 / 0.000 |
| `XU100_BELOW_EMA34` | 10 | 2099 / 2099 / 109 | 100 (3.9%) | +0.120 / +0.012 | +0.119 | 0.775 / 0.655 | 38.0% / 30.0% / 0.1% | 0.056 / 0.000 |
| `XU100_BELOW_EMA34` | 12 | 2084 / 2084 / 124 | 100 (3.9%) | +0.155 / +0.041 | +0.163 | 0.864 / 0.708 | 41.2% / 33.9% / 0.1% | 0.151 / -0.004 |
| `XU100_BELOW_EMA34` | 16 | 2060 / 2060 / 148 | 100 (3.9%) | +0.184 / +0.085 | +0.198 | 1.038 / 0.820 | 45.7% / 38.9% / 0.1% | 0.252 / -0.085 |

- **KARŞI ÖRNEK:** DARDL (2025-05-09 17:30, kova=XU100_BELOW_EMA34): 8x4H korunan=-8.30 ATR (MFE=0.20 / MAE=8.33 ATR) · GWIND (2026-04-24 18:00, kova=XU100_ABOVE_EMA34): 8x4H korunan=+5.97 ATR (MFE=5.97 / MAE=0.06 ATR)
- **SINIR:** XU100 EMA34 genel piyasa yönü için sade ve nedensel bir vekildir.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.131 ATR, MAE farkı 0.038 ATR düzeyinde ayrıştı.

## STB-BHV-H04 — Sonucu birkaç hisse/gün/aşırı hareket mi sürüklüyor?

- **TANIM:** Tüm evrende ortalama vs medyan vs eşit-sembol ortalaması, ilk-yarı/ikinci-yarı medyanları ve top-1/top-3 sembol yoğunlaşması.
- **VERİ:** Toplam checkpoint/olay `n=107441`, 8×4H tam ufuk `n=106641`, sağdan sansürlü `n=800`, ATR geçerli `n=106641`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `destek_altinda_tum_evren` (8×4H n=21498, med=-0.053 ATR, ort=-0.006 ATR, MFE_med=0.614, MAE_med=0.573, top1_sembol=2.3%) vs `destek_ustunde_tum_evren` (8×4H n=85143, med=-0.037 ATR, ort=0.041 ATR, MFE_med=0.710, MAE_med=0.617, top1_sembol=1.2%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `destek_altinda_tum_evren` | 1 | 21821 / 21821 / 71 | 100 (2.3%) | -0.010 / +0.000 | -0.004 | 0.131 / 0.138 | 3.4% / 2.6% / 0.1% | 0.000 / -0.009 |
| `destek_altinda_tum_evren` | 4 | 21632 / 21632 / 260 | 100 (2.3%) | -0.016 / -0.046 | +0.009 | 0.396 / 0.381 | 16.5% / 13.6% / 0.1% | 0.000 / -0.105 |
| `destek_altinda_tum_evren` | 8 | 21498 / 21498 / 394 | 100 (2.3%) | -0.006 / -0.053 | +0.038 | 0.614 / 0.573 | 29.8% / 26.1% / 0.2% | 0.017 / -0.132 |
| `destek_altinda_tum_evren` | 10 | 21435 / 21435 / 457 | 100 (2.3%) | +0.003 / -0.032 | +0.058 | 0.707 / 0.645 | 34.1% / 30.5% / 0.2% | 0.053 / -0.132 |
| `destek_altinda_tum_evren` | 12 | 21387 / 21387 / 505 | 100 (2.3%) | +0.010 / -0.022 | +0.074 | 0.790 / 0.715 | 37.4% / 33.9% / 0.2% | 0.099 / -0.160 |
| `destek_altinda_tum_evren` | 16 | 21315 / 21315 / 577 | 100 (2.3%) | +0.029 / -0.016 | +0.114 | 0.928 / 0.828 | 42.0% / 38.1% / 0.2% | 0.172 / -0.213 |
| `destek_ustunde_tum_evren` | 1 | 85520 / 85520 / 29 | 100 (1.2%) | +0.007 / +0.000 | +0.006 | 0.164 / 0.158 | 5.1% / 2.7% / 0.1% | 0.000 / 0.000 |
| `destek_ustunde_tum_evren` | 4 | 85409 / 85409 / 140 | 100 (1.2%) | +0.023 / -0.028 | +0.020 | 0.476 / 0.415 | 21.5% / 14.6% / 0.3% | 0.000 / -0.052 |
| `destek_ustunde_tum_evren` | 8 | 85143 / 85143 / 406 | 100 (1.2%) | +0.041 / -0.037 | +0.035 | 0.710 / 0.617 | 34.9% / 27.8% / 0.3% | 0.000 / -0.086 |
| `destek_ustunde_tum_evren` | 10 | 85006 / 85006 / 543 | 100 (1.2%) | +0.048 / -0.040 | +0.041 | 0.804 / 0.703 | 39.1% / 32.5% / 0.3% | 0.018 / -0.104 |
| `destek_ustunde_tum_evren` | 12 | 84854 / 84854 / 695 | 100 (1.2%) | +0.055 / -0.039 | +0.047 | 0.894 / 0.781 | 42.2% / 35.8% / 0.4% | 0.028 / -0.122 |
| `destek_ustunde_tum_evren` | 16 | 84526 / 84526 / 1023 | 100 (1.2%) | +0.069 / -0.038 | +0.057 | 1.060 / 0.918 | 46.3% / 39.9% / 0.4% | 0.062 / -0.151 |

- **KARŞI ÖRNEK:** ESEN (2025-08-12 18:00, kova=destek_ustunde_tum_evren): 8x4H korunan=+11.63 ATR (MFE=11.63 / MAE=0.00 ATR) · KARSN (2026-08-31 18:00, kova=destek_altinda_tum_evren): 8x4H korunan=+7.69 ATR (MFE=7.69 / MAE=0.33 ATR)
- **SINIR:** Ortalama ile medyan/eşit-sembol ortalaması ayrıştığında uç hareket etkisi var demektir.
- **SONUÇ (`betimsel ayrım`):** Kovalar arasında 8x4H medyan korunan getiri farkı 0.016 ATR, MAE farkı 0.044 ATR düzeyinde ayrıştı.

## STB-BHV-H05 — İlk izleyen 4H kapanışını beklemek farkı yok ediyor mu?

- **TANIM:** Geri alımın ilk 4H kapanışında ölçüm ile bir sonraki 4H kapanışında hala üstteyse ölçüm arasındaki gecikme maliyeti.
- **VERİ:** Toplam checkpoint/olay `n=2068`, 8×4H tam ufuk `n=2054`, sağdan sansürlü `n=14`, ATR geçerli `n=2054`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `ilk_4h_kapanisinda_giris` (8×4H n=1141, med=0.000 ATR, ort=0.084 ATR, MFE_med=0.699, MAE_med=0.552, top1_sembol=1.7%) vs `izleyen_ikinci_4h_kapanisinda_giris` (8×4H n=913, med=-0.029 ATR, ort=0.087 ATR, MFE_med=0.706, MAE_med=0.588, top1_sembol=1.8%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ilk_4h_kapanisinda_giris` | 1 | 1150 / 1150 / 0 | 100 (1.7%) | +0.003 / +0.000 | +0.004 | 0.133 / 0.151 | 2.9% / 2.4% / 0.0% | 0.000 / 0.000 |
| `ilk_4h_kapanisinda_giris` | 4 | 1149 / 1149 / 1 | 100 (1.7%) | +0.026 / +0.000 | +0.033 | 0.490 / 0.391 | 20.1% / 11.2% / 0.2% | 0.037 / -0.052 |
| `ilk_4h_kapanisinda_giris` | 8 | 1141 / 1141 / 9 | 100 (1.7%) | +0.084 / +0.000 | +0.098 | 0.699 / 0.552 | 34.8% / 25.9% / 0.2% | 0.032 / -0.022 |
| `ilk_4h_kapanisinda_giris` | 10 | 1141 / 1141 / 9 | 100 (1.7%) | +0.051 / -0.057 | +0.062 | 0.781 / 0.653 | 39.4% / 30.6% / 0.2% | 0.000 / -0.104 |
| `ilk_4h_kapanisinda_giris` | 12 | 1141 / 1141 / 9 | 100 (1.7%) | +0.090 / +0.000 | +0.109 | 0.880 / 0.727 | 43.2% / 35.2% / 0.2% | 0.120 / -0.117 |
| `ilk_4h_kapanisinda_giris` | 16 | 1139 / 1139 / 11 | 100 (1.7%) | +0.097 / +0.000 | +0.122 | 1.065 / 0.872 | 47.8% / 39.2% / 0.3% | 0.149 / -0.157 |
| `izleyen_ikinci_4h_kapanisinda_giris` | 1 | 918 / 918 / 0 | 100 (1.8%) | +0.029 / +0.000 | +0.030 | 0.134 / 0.135 | 4.9% / 1.1% / 0.0% | 0.000 / -0.014 |
| `izleyen_ikinci_4h_kapanisinda_giris` | 4 | 917 / 917 / 1 | 100 (1.8%) | +0.046 / -0.016 | +0.065 | 0.471 / 0.382 | 20.0% / 11.1% / 0.2% | 0.000 / -0.031 |
| `izleyen_ikinci_4h_kapanisinda_giris` | 8 | 913 / 913 / 5 | 100 (1.8%) | +0.087 / -0.029 | +0.112 | 0.706 / 0.588 | 36.0% / 26.4% / 0.2% | -0.022 / -0.032 |
| `izleyen_ikinci_4h_kapanisinda_giris` | 10 | 913 / 913 / 5 | 100 (1.8%) | +0.073 / +0.000 | +0.097 | 0.781 / 0.642 | 39.8% / 30.3% / 0.2% | 0.019 / -0.094 |
| `izleyen_ikinci_4h_kapanisinda_giris` | 12 | 912 / 912 / 6 | 100 (1.8%) | +0.112 / +0.000 | +0.130 | 0.898 / 0.715 | 42.9% / 34.6% / 0.3% | 0.138 / -0.126 |
| `izleyen_ikinci_4h_kapanisinda_giris` | 16 | 912 / 912 / 6 | 100 (1.8%) | +0.099 / -0.064 | +0.143 | 1.057 / 0.866 | 47.6% / 39.4% / 0.3% | 0.139 / -0.212 |

- **KARŞI ÖRNEK:** BJKAS (2025-12-18 18:00, kova=ilk_4h_kapanisinda_giris): 8x4H korunan=-6.49 ATR (MFE=0.00 / MAE=6.69 ATR) · AKFYE (2026-09-07 18:00, kova=izleyen_ikinci_4h_kapanisinda_giris): 8x4H korunan=+6.62 ATR (MFE=7.84 / MAE=0.07 ATR)
- **SINIR:** Saatlik ara fiyatlarla sahte native teyit üretilmez; gerçek 4H kapanışları kıyaslanır.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.029 ATR) ve MAE farkı (0.036 ATR) sınırlı kaldı.

## STB-BHV-H06 — Ayrımlar yeni dönem/sembol ve komşu eşiklerde korunuyor mu?

- **TANIM:** Sembol evreninin iki bağımsız alt kümesi ve tablodaki erken/geç dönem yarı medyanları arasında yön ve büyüklük tutarlılığı.
- **VERİ:** Toplam checkpoint/olay `n=4037`, 8×4H tam ufuk `n=3941`, sağdan sansürlü `n=96`, ATR geçerli `n=3941`, `UNKNOWN` başlangıç nedeniyle dışlanan `n=0`. Eşleme durumu: `USER_CONFIRMED`.
- **KARŞILAŞTIRMA (8×4H referans kesiti):** `alfabetik_ikinci_yari_semboller` (8×4H n=2002, med=-0.024 ATR, ort=0.003 ATR, MFE_med=0.624, MAE_med=0.589, top1_sembol=6.8%) vs `alfabetik_ilk_yari_semboller` (8×4H n=1939, med=-0.084 ATR, ort=0.018 ATR, MFE_med=0.620, MAE_med=0.613, top1_sembol=4.4%)

| Kova | Ufuk (4H) | n (ATR geçerli / tam / sansür) | Sembol (Top1%) | Ort / Med Korunan (ATR) | Eşit-Sem Ort | Med MFE / Med MAE | +1ATR İlk / -1ATR İlk / Belirsiz | Erken / Geç Yarı Med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `alfabetik_ikinci_yari_semboller` | 1 | 2043 / 2043 / 0 | 50 (6.8%) | -0.005 / +0.000 | -0.003 | 0.131 / 0.160 | 2.9% / 2.4% / 0.0% | 0.000 / 0.000 |
| `alfabetik_ikinci_yari_semboller` | 4 | 2033 / 2033 / 10 | 50 (6.8%) | -0.014 / -0.045 | -0.009 | 0.404 / 0.404 | 17.5% / 13.0% / 0.1% | 0.000 / -0.097 |
| `alfabetik_ikinci_yari_semboller` | 8 | 2002 / 2002 / 41 | 50 (6.8%) | +0.003 / -0.024 | +0.008 | 0.624 / 0.589 | 30.6% / 27.0% / 0.1% | 0.028 / -0.142 |
| `alfabetik_ikinci_yari_semboller` | 10 | 1995 / 1995 / 48 | 50 (6.8%) | +0.004 / -0.044 | +0.004 | 0.706 / 0.665 | 35.2% / 30.8% / 0.2% | 0.030 / -0.162 |
| `alfabetik_ikinci_yari_semboller` | 12 | 1989 / 1989 / 54 | 50 (6.8%) | +0.013 / -0.030 | +0.029 | 0.793 / 0.737 | 39.0% / 35.1% / 0.2% | 0.102 / -0.234 |
| `alfabetik_ikinci_yari_semboller` | 16 | 1976 / 1976 / 67 | 50 (6.8%) | +0.011 / -0.049 | +0.033 | 0.946 / 0.854 | 43.7% / 40.7% / 0.3% | 0.162 / -0.301 |
| `alfabetik_ilk_yari_semboller` | 1 | 1992 / 1992 / 2 | 50 (4.4%) | -0.025 / +0.000 | -0.030 | 0.133 / 0.152 | 3.0% / 2.9% / 0.0% | 0.000 / 0.000 |
| `alfabetik_ilk_yari_semboller` | 4 | 1981 / 1981 / 13 | 50 (4.4%) | -0.050 / -0.087 | -0.046 | 0.408 / 0.406 | 17.2% / 14.0% / 0.1% | -0.060 / -0.128 |
| `alfabetik_ilk_yari_semboller` | 8 | 1939 / 1939 / 55 | 50 (4.4%) | +0.018 / -0.084 | +0.019 | 0.620 / 0.613 | 30.8% / 27.6% / 0.1% | -0.086 / -0.083 |
| `alfabetik_ilk_yari_semboller` | 10 | 1933 / 1933 / 61 | 50 (4.4%) | +0.006 / -0.099 | +0.004 | 0.720 / 0.701 | 35.5% / 33.4% / 0.1% | -0.109 / -0.076 |
| `alfabetik_ilk_yari_semboller` | 12 | 1924 / 1924 / 70 | 50 (4.4%) | +0.042 / -0.043 | +0.049 | 0.817 / 0.772 | 39.0% / 37.3% / 0.1% | -0.050 / -0.041 |
| `alfabetik_ilk_yari_semboller` | 16 | 1913 / 1913 / 81 | 50 (4.4%) | +0.067 / +0.000 | +0.090 | 0.975 / 0.906 | 43.2% / 41.5% / 0.1% | 0.000 / -0.084 |

- **KARŞI ÖRNEK:** AKFYE (2026-09-07 17:30, kova=alfabetik_ilk_yari_semboller): 8x4H korunan=+6.74 ATR (MFE=7.63 / MAE=0.36 ATR) · FONET (2025-10-08 18:00, kova=alfabetik_ikinci_yari_semboller): 8x4H korunan=+6.27 ATR (MFE=7.75 / MAE=0.00 ATR)
- **SINIR:** Aynı arşivde görülmüş 100 sembol tam kör gelecek testi değildir; canlı kural öncesi ileri tarihli doğrulama gerekir.
- **SONUÇ (`belirgin ayrım yok`):** Kovalar arasında 8x4H medyan korunan getiri farkı (0.060 ATR) ve MAE farkı (0.024 ATR) sınırlı kaldı.
