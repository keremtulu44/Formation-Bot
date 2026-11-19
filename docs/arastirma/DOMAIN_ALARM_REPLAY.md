# Domain alarm replay — tetikleyiciler ne kadar değerli?

> **Tür:** Ölçüm (replay) · **Sürüm:** `domain-alarm-replay-v1` · **Tarih:** 2026-11-19
> **Kaynak:** `backfill_data/` native arşiv — 1h/2h/4h/1d, resample yok.
> **Çapa:** tetiğin oluştuğu mumun kapanışı; ölçüm bir sonraki bardan başlar. Tetik barı hiçbir uzanıma katılmaz.
> **Birim:** ATR — tetik anındaki ATR dondurulur, tüm ufuklarda sabit.

## 0 · Tek ekran

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

## 1 · Kanal sayısı — çok kanal birlikte ateşlemek daha mı iyi?

| kanal sayısı | n | ≥1 ATR (12b) | ≥1,5 ATR | ≥2 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 298433 | 66.6% | 53.5% | 42.0% | 3.20 | 62.2% | 30.4% |
| 2 | 34930 | 65.8% | 52.7% | 41.3% | 3.12 | 64.0% | 31.3% |
| 3 | 816 | 63.5% | 51.5% | 41.4% | 2.97 | 68.1% | 32.1% |
| 4 | 12 | 66.7% | 58.3% | 41.7% | 2.50 | 83.3% | 50.0% |

## 2 · Kanal kombinasyonları (n ≥ 30 olanlar)

| kombinasyon | n | ≥1 ATR (12b) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | güven |
|---|---:|---:|---:|---:|---:|---|
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

## 3 · Zaman dilimi kırılımı

| TF | tetik | ham tetik | bar başına (ham) | ≥1 ATR (12b) | taban farkı (pp) | medyan tepe | aleyhte ≥1 ATR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1d | 28723 | 31528 | 35.7% | 68.1% | +4.0 pp | 3.23 | 61.7% |
| 1h | 137682 | 138714 | 24.5% | 65.8% | +1.7 pp | 3.15 | 62.7% |
| 2h | 81195 | 83600 | 31.7% | 66.3% | +2.1 pp | 3.14 | 61.8% |
| 4h | 86591 | 89445 | 34.0% | 67.4% | +3.2 pp | 3.27 | 62.5% |

## 4 · Hacim kademesi (canlı eşikler: 5× / 10×)

| hacim | n | ≥1 ATR (12b) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR |
|---|---:|---:|---:|---:|---:|
| hacim yok (<5×) | 325978 | 66.4% | 53.3% | 3.18 | 62.3% |
| 5×–10× | 7542 | 71.3% | 59.9% | 3.36 | 66.9% |
| ≥10× | 671 | 73.0% | 64.2% | 4.07 | 70.6% |

## 5 · Formasyon state kırılımı (canlı formasyon kanalı)

| state | n | ≥1 ATR (12b) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR |
|---|---:|---:|---:|---:|---:|
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

## 6 · Yön (BOS/zone yönü)

| yön | n | ≥1 ATR (12b) | medyan tepe | aleyhte ≥1 ATR |
|---|---:|---:|---:|---:|
| yukarı | 172292 | 66.0% | 3.27 | 62.3% |
| aşağı | 161899 | 67.1% | 3.12 | 62.4% |

## 7 · Tetik anındaki grafik görüntüsü — hangi bağlamda tetik daha değerli?

Aynı kanal çok farklı grafiklerde ateşliyor. Aşağıdaki özellikler **tetik anında bilinen** (geleceğe bakmayan) bağlamdır; sütunlar kanal tablosuyla aynı ölçüdür.

### sıkışma (`bagl_sikisma`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
| daralıyor (0,5–1) | 110012 | 66.5% | +2.4 pp | 53.2% | 3.11 | 63.0% | 31.2% |
| geniş (≥1) | 6662 | 69.1% | +5.0 pp | 57.2% | 3.22 | 59.2% | 30.6% |
| sıkışmış (<0,5) | 217517 | 66.4% | +2.3 pp | 53.4% | 3.23 | 62.2% | 30.2% |

### hacim kuruma (`bagl_hacim_kuruma`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
| canlı (≥1,2) | 80784 | 67.8% | +3.7 pp | 55.2% | 3.22 | 62.9% | 32.3% |
| kurumuş (<0,8) | 113420 | 65.2% | +1.1 pp | 51.8% | 3.09 | 62.0% | 29.2% |
| normal (0,8–1,2) | 139987 | 66.8% | +2.7 pp | 53.7% | 3.25 | 62.4% | 30.6% |

### 6 bar koşu (`bagl_gunici_kosu`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
| aşağı (≤−1A) | 92741 | 66.1% | +1.9 pp | 53.2% | 3.18 | 61.6% | 29.5% |
| yatay | 160478 | 65.6% | +1.5 pp | 52.6% | 3.17 | 61.7% | 29.1% |
| yukarı (≥+1A) | 80972 | 68.9% | +4.7 pp | 55.5% | 3.25 | 64.7% | 34.6% |

### ATR yüzdeliği (`bagl_atr_yuzdelik`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
| fırtına (≥%70) | 105786 | 66.6% | +2.5 pp | 53.3% | 3.00 | 60.3% | 28.9% |
| orta | 101817 | 65.9% | +1.7 pp | 52.4% | 3.10 | 62.3% | 29.8% |
| sakin (<%30) | 126588 | 67.0% | +2.9 pp | 54.4% | 3.46 | 64.2% | 32.4% |

### seans saati (`bagl_seans_saati`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
| 09:00 | 60207 | 65.9% | +1.8 pp | 52.5% | 3.15 | 62.5% | 30.1% |
| 10:00 | 15697 | 64.3% | +0.2 pp | 50.2% | 3.03 | 61.3% | 27.9% |
| 11:00 | 30017 | 65.0% | +0.9 pp | 51.4% | 3.07 | 60.9% | 28.0% |
| 12:00 | 14164 | 64.8% | +0.7 pp | 51.4% | 3.09 | 60.2% | 27.0% |
| 13:00 | 56312 | 66.2% | +2.1 pp | 53.0% | 3.17 | 61.9% | 29.8% |
| 14:00 | 16651 | 64.6% | +0.5 pp | 50.9% | 3.13 | 62.5% | 29.0% |
| 15:00 | 31868 | 66.7% | +2.6 pp | 54.0% | 3.17 | 64.0% | 32.1% |
| 16:00 | 15934 | 68.4% | +4.3 pp | 56.1% | 3.30 | 64.8% | 34.1% |
| 17:00 | 64618 | 68.3% | +4.1 pp | 56.2% | 3.35 | 63.0% | 32.3% |

## 7.5 · Hangi alarm türü gerçekten değerli? — kanal × bağlam

Tablo **Wilson %95 alt sınırına** göre sıralı (n ≥ 300); alt sınır az veriyle iyi görünen hücreyi cezalandırır. z, taban oranına karşı anlamlılıktır.

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

