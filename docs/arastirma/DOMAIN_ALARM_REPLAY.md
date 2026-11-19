# Domain alarm replay — tetikleyiciler ne kadar değerli?

> **Tür:** Ölçüm (replay) · **Sürüm:** `domain-alarm-replay-v1` · **Tarih:** 2026-11-19
> **Kaynak:** `backfill_data/` native arşiv — 1h/2h/4h/1d, resample yok.
> **Çapa:** tetiğin oluştuğu mumun kapanışı; ölçüm bir sonraki bardan başlar. Tetik barı hiçbir uzanıma katılmaz.
> **Birim:** ATR — tetik anındaki ATR dondurulur, tüm ufuklarda sabit.

## 0 · Tek ekran

<<<<<<< HEAD
- **Örneklem:** 176 sembol × 4 zaman dilimi = 704 seri · **510820 satır** (sansürsüz 497001; bunun 334191 satırı tetik, 162810 satırı taban)
- **Bar başına tetik:** 36.03% — her 100 mumda ortalama bu kadar kart.
- **Cooldown (canlı 6 bar):** 116047 kart gönderildi, 218144 tekrar susturuldu (%65.3 tetiğin kartı basılmadı).
  - Gönderilen: ≥1 ATR 67.4% · medyan tepe 3.23 · iki yöne de 30.1%
  - Susturulan: ≥1 ATR 66.1% · medyan tepe 3.17 · iki yöne de 30.7% → fark -1.3 pp
- **Tetik vs taban (12 bar, lehte ≥1 ATR):** 66.5% vs 64.1% → **fazla +2.4 pp**
- **Yön farkı (lehte − aleyhte, 12 bar):** tetik +4.1 pp · taban +0.0 pp
- **Belirsizlik:** tetik satırlarının 30.5% kadarı 12 barda **her iki yöne de** ≥1 ATR görüyor; tabanda bu oran 30.4%.

| Kanal | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de | güven |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| TÜM TETİKLER | 334191 | 66.5% | +2.4 pp | 53.4% | 3.19 | 62.4% | 30.5% | YETERLI |
| BOS | 3730 | 62.1% | -2.0 pp | 50.1% | 2.77 | 73.5% | 36.2% | YETERLI |
| CHoCH | 269 | 65.1% | +0.9 pp | 49.4% | 2.28 | 62.5% | 28.6% | YETERLI |
| OB | 186541 | 65.8% | +1.7 pp | 53.2% | 3.13 | 62.8% | 30.0% | YETERLI |
| FVG | 29578 | 66.9% | +2.8 pp | 53.4% | 3.29 | 60.1% | 29.1% | YETERLI |
| FORMASYON | 142458 | 67.0% | +2.9 pp | 53.3% | 3.22 | 62.2% | 31.0% | YETERLI |
| HACIM | 8213 | 71.4% | +7.3 pp | 60.2% | 3.40 | 67.2% | 40.2% | YETERLI |
| TABAN (kontrol) | 162810 | 64.1% | — | 49.8% | 2.97 | 64.1% | 30.4% | YETERLI |
=======
> **KAPSAM UYARISI:** Bu koşu arşivin **44/176** sembolünü kapsıyor (%25) — alfabetik ilk N değil, **her 4. sembol** (sektör/kapula dağılsın diye). Sayılar bu semboller için geçerlidir; arşivin tamamına genelleme yapılmadan önce tam koşu gerekir.
- **Örneklem:** 44 sembol × 4 zaman dilimi = 176 seri · **131224 satır** (sansürsüz 127697; bunun 87299 satırı tetik, 40398 satırı taban)
- **Bar başına tetik:** 37.05% — her 100 mumda ortalama bu kadar kart.
- **Cooldown (canlı 6 bar):** 30104 kart gönderildi, 57195 tekrar susturuldu (%65.5 tetiğin kartı basılmadı).
  - Gönderilen: ≥1 ATR 67.6% · medyan tepe 3.20 · iki yöne de 30.7%
  - Susturulan: ≥1 ATR 66.5% · medyan tepe 3.18 · iki yöne de 31.0% → fark -1.1 pp
- **Tetik vs taban (12 bar, lehte ≥1 ATR):** 66.9% vs 64.6% → **fazla +2.2 pp**
- **Yön farkı (lehte − aleyhte, 12 bar):** tetik +4.3 pp · taban +0.0 pp
- **Belirsizlik:** tetik satırlarının 30.9% kadarı 12 barda **her iki yöne de** ≥1 ATR görüyor; tabanda bu oran 31.3%.

| Kanal | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de | güven |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| TÜM TETİKLER | 87299 | 66.9% | +2.2 pp | 53.6% | 3.19 | 62.5% | 30.9% | YETERLI |
| BOS | 963 | 63.0% | -1.6 pp | 50.9% | 3.11 | 73.5% | 36.8% | YETERLI |
| CHoCH | 83 | 62.7% | -2.0 pp | 51.8% | 2.23 | 63.9% | 28.9% | YETERLI |
| OB | 49677 | 65.8% | +1.1 pp | 53.0% | 3.10 | 63.2% | 30.2% | YETERLI |
| FVG | 7218 | 68.0% | +3.3 pp | 52.9% | 3.22 | 59.3% | 29.4% | YETERLI |
| FORMASYON | 37169 | 67.6% | +2.9 pp | 53.7% | 3.28 | 62.1% | 31.3% | YETERLI |
| HACIM | 2105 | 73.0% | +8.4 pp | 60.9% | 3.34 | 67.0% | 41.0% | YETERLI |
| TABAN (kontrol) | 40398 | 64.6% | — | 50.2% | 2.96 | 64.6% | 31.3% | YETERLI |
>>>>>>> origin/arena/04f21609-formation-bot

## 1 · Kanal sayısı — çok kanal birlikte ateşlemek daha mı iyi?

| kanal sayısı | n | ≥1 ATR (12b) | ≥1,5 ATR | ≥2 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---:|---:|---:|---:|---:|---:|---:|---:|
<<<<<<< HEAD
| 1 | 298433 | 66.6% | 53.5% | 42.0% | 3.20 | 62.2% | 30.4% |
| 2 | 34930 | 65.8% | 52.7% | 41.3% | 3.12 | 64.0% | 31.3% |
| 3 | 816 | 63.5% | 51.5% | 41.4% | 2.97 | 68.1% | 32.1% |
| 4 | 12 | 66.7% | 58.3% | 41.7% | 2.50 | 83.3% | 50.0% |
=======
| 1 | 77619 | 67.0% | 53.7% | 42.1% | 3.20 | 62.4% | 30.9% |
| 2 | 9445 | 65.6% | 52.2% | 41.1% | 3.13 | 63.8% | 30.8% |
| 3 | 234 | 65.4% | 52.1% | 42.3% | 2.94 | 70.1% | 35.5% |
| 4 | 1 | 100.0% | 0.0% | 0.0% | 2.22 | 100.0% | 100.0% |
>>>>>>> origin/arena/04f21609-formation-bot

## 2 · Kanal kombinasyonları (n ≥ 30 olanlar)

| kombinasyon | n | ≥1 ATR (12b) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | güven |
|---|---:|---:|---:|---:|---:|---|
<<<<<<< HEAD
| OB | 156165 | 65.9% | 53.3% | 3.14 | 62.5% | YETERLI |
| FORMASYON | 110685 | 67.4% | 53.5% | 3.25 | 61.7% | YETERLI |
| FORMASYON+OB | 25866 | 65.6% | 52.5% | 3.11 | 63.8% | YETERLI |
| FVG | 22982 | 67.3% | 53.7% | 3.33 | 59.8% | YETERLI |
| HACIM | 5951 | 71.6% | 60.5% | 3.48 | 66.2% | YETERLI |
| FORMASYON+FVG | 3252 | 67.4% | 51.8% | 3.25 | 59.3% | YETERLI |
| FVG+OB | 2689 | 64.0% | 52.5% | 3.10 | 62.8% | YETERLI |
| BOS | 2471 | 62.8% | 50.7% | 2.86 | 72.7% | YETERLI |
| FORMASYON+HACIM | 1307 | 73.2% | 61.2% | 3.33 | 69.1% | YETERLI |
| HACIM+OB | 567 | 67.9% | 57.3% | 3.13 | 72.0% | YETERLI |
| BOS+FORMASYON | 527 | 59.4% | 47.1% | 2.43 | 76.9% | YETERLI |
| BOS+OB | 453 | 61.1% | 48.3% | 2.83 | 74.8% | YETERLI |
| FORMASYON+FVG+OB | 444 | 62.6% | 49.8% | 2.97 | 63.5% | YETERLI |
| CHoCH | 179 | 67.0% | 51.4% | 2.36 | 59.8% | YETERLI |
| FORMASYON+HACIM+OB | 164 | 65.9% | 52.4% | 3.13 | 71.3% | YETERLI |
| BOS+FORMASYON+OB | 110 | 57.3% | 48.2% | 2.37 | 74.5% | YETERLI |
| FVG+HACIM | 99 | 65.7% | 56.6% | 2.81 | 63.6% | YETERLI |
| BOS+FVG | 59 | 71.2% | 55.9% | 3.18 | 57.6% | YETERLI |
| BOS+HACIM | 45 | 62.2% | 55.6% | 3.28 | 64.4% | YETERLI |
| CHoCH+OB | 30 | 66.7% | 43.3% | 2.10 | 70.0% | YETERLI |
=======
| OB | 41380 | 65.9% | 53.3% | 3.09 | 63.1% | YETERLI |
| FORMASYON | 28576 | 68.1% | 54.2% | 3.32 | 61.6% | YETERLI |
| FORMASYON+OB | 7051 | 65.0% | 51.8% | 3.12 | 63.8% | YETERLI |
| FVG | 5472 | 68.5% | 53.3% | 3.22 | 59.0% | YETERLI |
| HACIM | 1507 | 72.9% | 61.3% | 3.41 | 65.8% | YETERLI |
| FORMASYON+FVG | 855 | 67.4% | 50.6% | 3.20 | 58.6% | YETERLI |
| FVG+OB | 715 | 65.3% | 52.6% | 3.17 | 62.0% | YETERLI |
| BOS | 630 | 62.4% | 50.6% | 3.31 | 73.5% | YETERLI |
| FORMASYON+HACIM | 316 | 76.9% | 62.0% | 3.15 | 69.9% | YETERLI |
| HACIM+OB | 175 | 69.1% | 57.7% | 3.13 | 70.3% | YETERLI |
| BOS+FORMASYON | 137 | 62.0% | 51.1% | 2.75 | 76.6% | YETERLI |
| FORMASYON+FVG+OB | 126 | 61.1% | 48.4% | 2.94 | 65.9% | YETERLI |
| BOS+OB | 125 | 60.8% | 46.4% | 2.65 | 72.8% | YETERLI |
| CHoCH | 54 | 63.0% | 51.9% | 2.37 | 64.8% | YETERLI |
| FORMASYON+HACIM+OB | 47 | 66.0% | 48.9% | 3.16 | 78.7% | YETERLI |
| BOS+FORMASYON+OB | 32 | 65.6% | 53.1% | 2.70 | 68.8% | YETERLI |
| FVG+HACIM | 32 | 65.6% | 56.2% | 4.06 | 53.1% | YETERLI |
>>>>>>> origin/arena/04f21609-formation-bot

## 3 · Zaman dilimi kırılımı

| TF | tetik | ham tetik | bar başına (ham) | ≥1 ATR (12b) | taban farkı (pp) | medyan tepe | aleyhte ≥1 ATR |
|---|---:|---:|---:|---:|---:|---:|---:|
<<<<<<< HEAD
| 1d | 28723 | 31528 | 35.7% | 68.1% | +4.0 pp | 3.23 | 61.7% |
| 1h | 137682 | 138714 | 24.5% | 65.8% | +1.7 pp | 3.15 | 62.7% |
| 2h | 81195 | 83600 | 31.7% | 66.3% | +2.1 pp | 3.14 | 61.8% |
| 4h | 86591 | 89445 | 34.0% | 67.4% | +3.2 pp | 3.27 | 62.5% |
=======
| 1d | 7189 | 7913 | 35.8% | 69.2% | +4.6 pp | 3.25 | 60.9% |
| 1h | 36968 | 37332 | 26.1% | 66.1% | +1.4 pp | 3.16 | 63.0% |
| 2h | 21242 | 21858 | 33.1% | 66.5% | +1.8 pp | 3.14 | 62.6% |
| 4h | 21900 | 22629 | 34.3% | 67.9% | +3.3 pp | 3.25 | 62.2% |
>>>>>>> origin/arena/04f21609-formation-bot

## 4 · Hacim kademesi (canlı eşikler: 5× / 10×)

| hacim | n | ≥1 ATR (12b) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR |
|---|---:|---:|---:|---:|---:|
<<<<<<< HEAD
| hacim yok (<5×) | 325978 | 66.4% | 53.3% | 3.18 | 62.3% |
| 5×–10× | 7542 | 71.3% | 59.9% | 3.36 | 66.9% |
| ≥10× | 671 | 73.0% | 64.2% | 4.07 | 70.6% |
=======
| hacim yok (<5×) | 85194 | 66.7% | 53.4% | 3.18 | 62.4% |
| 5×–10× | 1902 | 73.1% | 60.6% | 3.32 | 66.3% |
| ≥10× | 203 | 71.9% | 63.5% | 3.43 | 73.9% |
>>>>>>> origin/arena/04f21609-formation-bot

## 5 · Formasyon state kırılımı (canlı formasyon kanalı)

| state | n | ≥1 ATR (12b) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR |
|---|---:|---:|---:|---:|---:|
<<<<<<< HEAD
| FORMASYON_TAMAMLANDI | 25329 | 67.6% | 53.9% | 3.26 | 61.8% |
| KIRILIM_TEYITLI | 20139 | 68.3% | 54.1% | 3.22 | 63.6% |
| KIRILIM_ADAYI | 19087 | 68.1% | 54.4% | 3.25 | 63.9% |
| SIKISMA_GUCLENIYOR | 16483 | 65.7% | 51.9% | 3.19 | 61.4% |
| FORMASYON_ZAYIFLADI | 15570 | 65.7% | 52.1% | 3.19 | 62.3% |
| BASARISIZ_KIRILIM | 11570 | 66.5% | 53.5% | 3.10 | 61.1% |
| RETEST_BASARILI | 10791 | 66.3% | 53.0% | 3.26 | 61.6% |
| KIRILIM_HAZIRLIGI | 8006 | 66.0% | 52.0% | 3.28 | 60.5% |
| KIRILIM_TEYIT_ALAMADI | 4890 | 67.6% | 54.2% | 3.33 | 61.9% |
| FORMASYON_TANIMLANDI | 4377 | 67.7% | 54.8% | 3.33 | 62.6% |
| OLGUNLASIYOR | 3825 | 66.5% | 51.8% | 3.21 | 61.0% |
| RETEST_BEKLENIYOR | 1080 | 71.6% | 56.1% | 3.20 | 60.6% |
| KIRILIM_DENEMESI | 919 | 67.4% | 52.7% | 3.07 | 61.7% |
| RETEST_EDILIYOR | 391 | 61.6% | 48.1% | 3.01 | 61.6% |
=======
| FORMASYON_TAMAMLANDI | 6796 | 68.0% | 54.8% | 3.35 | 61.9% |
| KIRILIM_TEYITLI | 5311 | 69.3% | 54.1% | 3.27 | 63.7% |
| KIRILIM_ADAYI | 5095 | 68.7% | 55.0% | 3.40 | 63.6% |
| SIKISMA_GUCLENIYOR | 4287 | 65.9% | 51.4% | 3.16 | 61.3% |
| FORMASYON_ZAYIFLADI | 4076 | 66.3% | 52.6% | 3.21 | 61.8% |
| BASARISIZ_KIRILIM | 3038 | 66.6% | 53.7% | 3.15 | 60.9% |
| RETEST_BASARILI | 2866 | 66.7% | 53.7% | 3.27 | 61.8% |
| KIRILIM_HAZIRLIGI | 1809 | 66.2% | 52.1% | 3.24 | 59.9% |
| KIRILIM_TEYIT_ALAMADI | 1176 | 69.4% | 55.8% | 3.55 | 60.5% |
| OLGUNLASIYOR | 1065 | 66.0% | 51.6% | 3.09 | 61.2% |
| FORMASYON_TANIMLANDI | 1061 | 67.5% | 54.9% | 3.43 | 64.7% |
| RETEST_BEKLENIYOR | 278 | 71.2% | 52.5% | 3.04 | 59.7% |
| KIRILIM_DENEMESI | 214 | 71.5% | 57.0% | 3.35 | 60.7% |
| RETEST_EDILIYOR | 97 | 57.7% | 44.3% | 3.74 | 57.7% |
>>>>>>> origin/arena/04f21609-formation-bot

## 6 · Yön (BOS/zone yönü)

| yön | n | ≥1 ATR (12b) | medyan tepe | aleyhte ≥1 ATR |
|---|---:|---:|---:|---:|
<<<<<<< HEAD
| yukarı | 172292 | 66.0% | 3.27 | 62.3% |
| aşağı | 161899 | 67.1% | 3.12 | 62.4% |
=======
| yukarı | 44202 | 67.0% | 3.34 | 62.2% |
| aşağı | 43097 | 66.8% | 3.07 | 62.9% |
>>>>>>> origin/arena/04f21609-formation-bot

## 7 · Tetik anındaki grafik görüntüsü — hangi bağlamda tetik daha değerli?

Aynı kanal çok farklı grafiklerde ateşliyor. Aşağıdaki özellikler **tetik anında bilinen** (geleceğe bakmayan) bağlamdır; sütunlar kanal tablosuyla aynı ölçüdür.

### sıkışma (`bagl_sikisma`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
<<<<<<< HEAD
| daralıyor (0,5–1) | 110012 | 66.5% | +2.4 pp | 53.2% | 3.11 | 63.0% | 31.2% |
| geniş (≥1) | 6662 | 69.1% | +5.0 pp | 57.2% | 3.22 | 59.2% | 30.6% |
| sıkışmış (<0,5) | 217517 | 66.4% | +2.3 pp | 53.4% | 3.23 | 62.2% | 30.2% |
=======
| daralıyor (0,5–1) | 28825 | 67.1% | +2.5 pp | 53.5% | 3.09 | 62.8% | 31.4% |
| geniş (≥1) | 1730 | 69.0% | +4.3 pp | 56.0% | 3.09 | 57.6% | 29.3% |
| sıkışmış (<0,5) | 56744 | 66.7% | +2.1 pp | 53.5% | 3.24 | 62.5% | 30.6% |
>>>>>>> origin/arena/04f21609-formation-bot

### hacim kuruma (`bagl_hacim_kuruma`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
<<<<<<< HEAD
| canlı (≥1,2) | 80784 | 67.8% | +3.7 pp | 55.2% | 3.22 | 62.9% | 32.3% |
| kurumuş (<0,8) | 113420 | 65.2% | +1.1 pp | 51.8% | 3.09 | 62.0% | 29.2% |
| normal (0,8–1,2) | 139987 | 66.8% | +2.7 pp | 53.7% | 3.25 | 62.4% | 30.6% |
=======
| canlı (≥1,2) | 20579 | 68.3% | +3.6 pp | 55.2% | 3.17 | 63.2% | 32.8% |
| kurumuş (<0,8) | 30039 | 65.5% | +0.9 pp | 52.1% | 3.10 | 62.5% | 29.7% |
| normal (0,8–1,2) | 36681 | 67.2% | +2.5 pp | 53.9% | 3.27 | 62.1% | 30.8% |
>>>>>>> origin/arena/04f21609-formation-bot

### 6 bar koşu (`bagl_gunici_kosu`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
<<<<<<< HEAD
| aşağı (≤−1A) | 92741 | 66.1% | +1.9 pp | 53.2% | 3.18 | 61.6% | 29.5% |
| yatay | 160478 | 65.6% | +1.5 pp | 52.6% | 3.17 | 61.7% | 29.1% |
| yukarı (≥+1A) | 80972 | 68.9% | +4.7 pp | 55.5% | 3.25 | 64.7% | 34.6% |
=======
| aşağı (≤−1A) | 24109 | 66.4% | +1.7 pp | 53.1% | 3.20 | 61.7% | 29.6% |
| yatay | 41999 | 65.9% | +1.3 pp | 52.8% | 3.17 | 61.8% | 29.4% |
| yukarı (≥+1A) | 21191 | 69.4% | +4.8 pp | 55.6% | 3.20 | 64.9% | 35.3% |
>>>>>>> origin/arena/04f21609-formation-bot

### ATR yüzdeliği (`bagl_atr_yuzdelik`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
<<<<<<< HEAD
| fırtına (≥%70) | 105786 | 66.6% | +2.5 pp | 53.3% | 3.00 | 60.3% | 28.9% |
| orta | 101817 | 65.9% | +1.7 pp | 52.4% | 3.10 | 62.3% | 29.8% |
| sakin (<%30) | 126588 | 67.0% | +2.9 pp | 54.4% | 3.46 | 64.2% | 32.4% |
=======
| fırtına (≥%70) | 27767 | 67.1% | +2.5 pp | 53.5% | 2.99 | 60.1% | 29.1% |
| orta | 26848 | 66.3% | +1.6 pp | 52.4% | 3.07 | 62.9% | 30.6% |
| sakin (<%30) | 32684 | 67.2% | +2.5 pp | 54.6% | 3.51 | 64.3% | 32.6% |
>>>>>>> origin/arena/04f21609-formation-bot

### seans saati (`bagl_seans_saati`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
<<<<<<< HEAD
| 09:00 | 60207 | 65.9% | +1.8 pp | 52.5% | 3.15 | 62.5% | 30.1% |
| 10:00 | 15697 | 64.3% | +0.2 pp | 50.2% | 3.03 | 61.3% | 27.9% |
| 11:00 | 30017 | 65.0% | +0.9 pp | 51.4% | 3.07 | 60.9% | 28.0% |
| 12:00 | 14164 | 64.8% | +0.7 pp | 51.4% | 3.09 | 60.2% | 27.0% |
| 13:00 | 56312 | 66.2% | +2.1 pp | 53.0% | 3.17 | 61.9% | 29.8% |
| 14:00 | 16651 | 64.6% | +0.5 pp | 50.9% | 3.13 | 62.5% | 29.0% |
| 15:00 | 31868 | 66.7% | +2.6 pp | 54.0% | 3.17 | 64.0% | 32.1% |
| 16:00 | 15934 | 68.4% | +4.3 pp | 56.1% | 3.30 | 64.8% | 34.1% |
| 17:00 | 64618 | 68.3% | +4.1 pp | 56.2% | 3.35 | 63.0% | 32.3% |
=======
| 09:00 | 15505 | 66.3% | +1.7 pp | 52.7% | 3.16 | 63.0% | 30.9% |
| 10:00 | 4167 | 64.8% | +0.2 pp | 50.2% | 2.99 | 61.6% | 28.7% |
| 11:00 | 7952 | 65.1% | +0.5 pp | 51.3% | 3.06 | 60.8% | 27.9% |
| 12:00 | 3836 | 65.0% | +0.3 pp | 50.9% | 3.03 | 59.6% | 26.6% |
| 13:00 | 14532 | 66.5% | +1.9 pp | 53.2% | 3.17 | 62.0% | 30.0% |
| 14:00 | 4491 | 65.2% | +0.5 pp | 51.8% | 3.21 | 62.7% | 29.7% |
| 15:00 | 8548 | 67.5% | +2.9 pp | 54.9% | 3.25 | 64.3% | 33.0% |
| 16:00 | 4264 | 68.6% | +4.0 pp | 56.0% | 3.36 | 64.5% | 33.7% |
| 17:00 | 16815 | 68.1% | +3.5 pp | 55.8% | 3.27 | 63.6% | 32.7% |
>>>>>>> origin/arena/04f21609-formation-bot

## 7.5 · Hangi alarm türü gerçekten değerli? — kanal × bağlam

Tablo **Wilson %95 alt sınırına** göre sıralı (n ≥ 300); alt sınır az veriyle iyi görünen hücreyi cezalandırır. z, taban oranına karşı anlamlılıktır.

<<<<<<< HEAD
**Taban:** 64.1% (n=162810) — rastgele bir barın 12 barda ≥1 ATR görme oranı.

| segment | n | ≥1 ATR | taban farkı | alt sınır | z | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|
| HACIM · 6 bar koşu: yukarı (≥+1A) | 4075 | 74.7% | +10.6 pp | 73.3% | +13.9 | 45.1% |
| HACIM · seans saati: 09:00 | 1514 | 75.4% | +11.3 pp | 73.2% | +9.1 | 45.4% |
| HACIM · seans saati: 17:00 | 381 | 76.9% | +12.8 pp | 72.4% | +5.2 | 44.9% |
| HACIM · ATR yüzdeliği: fırtına (≥%70) | 4013 | 72.4% | +8.3 pp | 71.0% | +10.9 | 40.1% |
| HACIM · sıkışma: daralıyor (0,5–1) | 4102 | 71.9% | +7.8 pp | 70.5% | +10.3 | 40.7% |
| HACIM · hacim kuruma: canlı (≥1,2) | 6391 | 71.4% | +7.3 pp | 70.3% | +12.0 | 39.6% |
| HACIM · yapı yakınlığı: BOS | 6518 | 71.3% | +7.2 pp | 70.2% | +11.9 | 39.5% |
| FORMASYON · 6 bar koşu: yukarı (≥+1A) | 34898 | 69.6% | +5.5 pp | 69.1% | +19.5 | 34.7% |
| FORMASYON · seans saati: 16:00 | 7528 | 69.6% | +5.5 pp | 68.6% | +9.8 | 35.5% |
| FORMASYON · seans saati: 00:00 | 12541 | 69.3% | +5.2 pp | 68.5% | +11.8 | 31.8% |
| FORMASYON · hacim kuruma: canlı (≥1,2) | 32602 | 68.4% | +4.3 pp | 67.9% | +14.9 | 32.7% |
| HACIM · sıkışma: geniş (≥1) | 516 | 71.9% | +7.8 pp | 67.9% | +3.7 | 39.7% |
| OB · seans saati: 17:00 | 33651 | 68.3% | +4.2 pp | 67.8% | +14.7 | 31.1% |
| HACIM · ATR yüzdeliği: orta | 1631 | 70.0% | +5.9 pp | 67.7% | +4.9 | 39.1% |
| HACIM · seans saati: 11:00 | 684 | 71.2% | +7.1 pp | 67.7% | +3.9 | 37.7% |
| HACIM · sıkışma: sıkışmış (<0,5) | 1900 | 69.8% | +5.7 pp | 67.7% | +5.1 | 36.8% |

- **102 segmentin 74'i tabandan anlamlı iyi, 7'i anlamlı kötü, 21'i anlamsız (|z|<2).**
- **Tabandan anlamlı KÖTÜ olanlar** (canlıda susturulacak ilk adaylar): BOS · yapı yakınlığı: BOS (-2.0 pp, n=3730, z=-2.5); BOS · sıkışma: daralıyor (0,5–1) (-3.7 pp, n=1535, z=-3.0); BOS · 6 bar koşu: yukarı (≥+1A) (-4.8 pp, n=1734, z=-4.1); BOS · ATR yüzdeliği: sakin (<%30) (-4.2 pp, n=941, z=-2.7); BOS · hacim kuruma: canlı (≥1,2) (-5.1 pp, n=1453, z=-4.1).
=======
**Taban:** 64.6% (n=40398) — rastgele bir barın 12 barda ≥1 ATR görme oranı.

| segment | n | ≥1 ATR | taban farkı | alt sınır | z | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|
| HACIM · 6 bar koşu: yukarı (≥+1A) | 973 | 75.6% | +11.0 pp | 72.8% | +7.1 | 45.2% |
| HACIM · seans saati: 09:00 | 361 | 77.0% | +12.4 pp | 72.4% | +4.9 | 43.2% |
| HACIM · ATR yüzdeliği: fırtına (≥%70) | 993 | 73.2% | +8.6 pp | 70.4% | +5.6 | 40.2% |
| HACIM · hacim kuruma: canlı (≥1,2) | 1640 | 72.6% | +7.9 pp | 70.4% | +6.6 | 39.5% |
| HACIM · yapı yakınlığı: BOS | 1682 | 72.5% | +7.9 pp | 70.4% | +6.7 | 39.7% |
| FORMASYON · 6 bar koşu: yukarı (≥+1A) | 9155 | 70.4% | +5.8 pp | 69.4% | +10.5 | 36.0% |
| FORMASYON · seans saati: 16:00 | 1980 | 71.4% | +6.8 pp | 69.4% | +6.2 | 34.8% |
| FORMASYON · seans saati: 00:00 | 3163 | 71.0% | +6.3 pp | 69.4% | +7.2 | 32.8% |
| HACIM · sıkışma: daralıyor (0,5–1) | 1012 | 71.9% | +7.3 pp | 69.1% | +4.8 | 40.6% |
| HACIM · sıkışma: sıkışmış (<0,5) | 555 | 72.4% | +7.8 pp | 68.6% | +3.8 | 37.3% |
| FORMASYON · hacim kuruma: canlı (≥1,2) | 8251 | 69.2% | +4.5 pp | 68.1% | +7.9 | 33.5% |
| FVG · ATR yüzdeliği: sakin (<%30) | 1912 | 70.0% | +5.3 pp | 67.9% | +4.8 | 30.4% |
| FVG · seans saati: 17:00 | 1491 | 70.2% | +5.5 pp | 67.8% | +4.4 | 31.9% |
| FVG · 6 bar koşu: yukarı (≥+1A) | 1709 | 70.0% | +5.3 pp | 67.8% | +4.5 | 32.9% |
| HACIM · ATR yüzdeliği: orta | 398 | 72.1% | +7.5 pp | 67.5% | +3.1 | 39.7% |
| FORMASYON · sıkışma: daralıyor (0,5–1) | 12827 | 68.1% | +3.4 pp | 67.3% | +7.1 | 31.8% |

- **84 segmentin 55'i tabandan anlamlı iyi, 2'i anlamlı kötü, 27'i anlamsız (|z|<2).**
- **Tabandan anlamlı KÖTÜ olanlar** (canlıda susturulacak ilk adaylar): BOS · 6 bar koşu: yukarı (≥+1A) (-6.0 pp, n=445, z=-2.6); BOS · hacim kuruma: canlı (≥1,2) (-5.7 pp, n=314, z=-2.1).
>>>>>>> origin/arena/04f21609-formation-bot
- **Uyarı:** 84 segment aynı örneklemde denendi. Bonferroni ile anlamlılık eşiği |z|>3,2'ye çıkar; bu eşiği geçen segmentler yukarıdaki tablonun ilk sıralarıdır, ama 'her segment ayrı bir kural' diye okunmamalı.

## 8 · Nasıl okunur / sınırlar

- **'≥1 ATR' bir kazanç değildir.** Tetiğin gösterdiği yönde fiyatın 12 bar içinde
  en az 1 ATR uzanıp uzanmadığıdır; maliyet, kayma, pozisyon ve çıkış kuralı yok.
- **'aleyhte ≥1 ATR' ters taraftaki uzanımdır.** Lehte oranı yüksek ama aleyhte de
  yüksekse tetik *belirsizdir*: iki tarafa da 1 ATR gidiyor, kart yön iddia etmemeli.
- **Sansür** pencere veri sonuna takılan tetikleri dışarıda bırakır (n'ler bu yüzden
  ham satır sayısından küçüktür).
- **Bir tetik tek satırdır.** Aynı barda dört kanal ateşlerse tek satır üretilir;
  kanal sayısı tablosu bu yüzden kanal tablosundan farklı toplam verir.
- **FVG reaksiyonu nedensel türetilir:** arşiv zone satırı doğum anını taşıdığı için
  canlı motorun 'state=REACTION' anı, 'sınıra dokundu ve tükenmedi' ile karşılanır.
- **Seans saati tablosu yalnız intraday TF'ler (1h/2h/4h) içindir.** Günlük barların
  saati 00:00 olduğu için onları katmak 'gece tetikleri daha iyi' gibi sahte bir
  bulgu üretirdi; bu yüzden 1d bu tabloya alınmaz.
- **Bağlam tablolarındaki farklar tek tek anlamlılık testinden geçmedi.** Kova sayısı
  arttıkça şans eseri 5–10 pp fark çıkar; ±5 pp altındaki satırlar **bulgu değildir**,
  yalnız adaydır. Bu tablolar hipotez üretmek için, karar vermek için değil.
- Bu rapor **canlı alarm davranışını değiştirmez**; yalnız hangi tetiğin ölçülebilir
  bir fark ürettiğini gösterir.

