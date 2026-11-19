# Domain alarm replay — tetikleyiciler ne kadar değerli?

> **Tür:** Ölçüm (replay) · **Sürüm:** `domain-alarm-replay-v1` · **Tarih:** 2026-11-19
> **Kaynak:** `backfill_data/` native arşiv — 1h/2h/4h/1d, resample yok.
> **Çapa:** tetiğin oluştuğu mumun kapanışı; ölçüm bir sonraki bardan başlar. Tetik barı hiçbir uzanıma katılmaz.
> **Birim:** ATR — tetik anındaki ATR dondurulur, tüm ufuklarda sabit.

## 0 · Tek ekran

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

## 1 · Kanal sayısı — çok kanal birlikte ateşlemek daha mı iyi?

| kanal sayısı | n | ≥1 ATR (12b) | ≥1,5 ATR | ≥2 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 77619 | 67.0% | 53.7% | 42.1% | 3.20 | 62.4% | 30.9% |
| 2 | 9445 | 65.6% | 52.2% | 41.1% | 3.13 | 63.8% | 30.8% |
| 3 | 234 | 65.4% | 52.1% | 42.3% | 2.94 | 70.1% | 35.5% |
| 4 | 1 | 100.0% | 0.0% | 0.0% | 2.22 | 100.0% | 100.0% |

## 2 · Kanal kombinasyonları (n ≥ 30 olanlar)

| kombinasyon | n | ≥1 ATR (12b) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | güven |
|---|---:|---:|---:|---:|---:|---|
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

## 3 · Zaman dilimi kırılımı

| TF | tetik | ham tetik | bar başına (ham) | ≥1 ATR (12b) | taban farkı (pp) | medyan tepe | aleyhte ≥1 ATR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1d | 7189 | 7913 | 35.8% | 69.2% | +4.6 pp | 3.25 | 60.9% |
| 1h | 36968 | 37332 | 26.1% | 66.1% | +1.4 pp | 3.16 | 63.0% |
| 2h | 21242 | 21858 | 33.1% | 66.5% | +1.8 pp | 3.14 | 62.6% |
| 4h | 21900 | 22629 | 34.3% | 67.9% | +3.3 pp | 3.25 | 62.2% |

## 4 · Hacim kademesi (canlı eşikler: 5× / 10×)

| hacim | n | ≥1 ATR (12b) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR |
|---|---:|---:|---:|---:|---:|
| hacim yok (<5×) | 85194 | 66.7% | 53.4% | 3.18 | 62.4% |
| 5×–10× | 1902 | 73.1% | 60.6% | 3.32 | 66.3% |
| ≥10× | 203 | 71.9% | 63.5% | 3.43 | 73.9% |

## 5 · Formasyon state kırılımı (canlı formasyon kanalı)

| state | n | ≥1 ATR (12b) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR |
|---|---:|---:|---:|---:|---:|
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

## 6 · Yön (BOS/zone yönü)

| yön | n | ≥1 ATR (12b) | medyan tepe | aleyhte ≥1 ATR |
|---|---:|---:|---:|---:|
| yukarı | 44202 | 67.0% | 3.34 | 62.2% |
| aşağı | 43097 | 66.8% | 3.07 | 62.9% |

## 7 · Tetik anındaki grafik görüntüsü — hangi bağlamda tetik daha değerli?

Aynı kanal çok farklı grafiklerde ateşliyor. Aşağıdaki özellikler **tetik anında bilinen** (geleceğe bakmayan) bağlamdır; sütunlar kanal tablosuyla aynı ölçüdür.

### sıkışma (`bagl_sikisma`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
| daralıyor (0,5–1) | 28825 | 67.1% | +2.5 pp | 53.5% | 3.09 | 62.8% | 31.4% |
| geniş (≥1) | 1730 | 69.0% | +4.3 pp | 56.0% | 3.09 | 57.6% | 29.3% |
| sıkışmış (<0,5) | 56744 | 66.7% | +2.1 pp | 53.5% | 3.24 | 62.5% | 30.6% |

### hacim kuruma (`bagl_hacim_kuruma`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
| canlı (≥1,2) | 20579 | 68.3% | +3.6 pp | 55.2% | 3.17 | 63.2% | 32.8% |
| kurumuş (<0,8) | 30039 | 65.5% | +0.9 pp | 52.1% | 3.10 | 62.5% | 29.7% |
| normal (0,8–1,2) | 36681 | 67.2% | +2.5 pp | 53.9% | 3.27 | 62.1% | 30.8% |

### 6 bar koşu (`bagl_gunici_kosu`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
| aşağı (≤−1A) | 24109 | 66.4% | +1.7 pp | 53.1% | 3.20 | 61.7% | 29.6% |
| yatay | 41999 | 65.9% | +1.3 pp | 52.8% | 3.17 | 61.8% | 29.4% |
| yukarı (≥+1A) | 21191 | 69.4% | +4.8 pp | 55.6% | 3.20 | 64.9% | 35.3% |

### ATR yüzdeliği (`bagl_atr_yuzdelik`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
| fırtına (≥%70) | 27767 | 67.1% | +2.5 pp | 53.5% | 2.99 | 60.1% | 29.1% |
| orta | 26848 | 66.3% | +1.6 pp | 52.4% | 3.07 | 62.9% | 30.6% |
| sakin (<%30) | 32684 | 67.2% | +2.5 pp | 54.6% | 3.51 | 64.3% | 32.6% |

### seans saati (`bagl_seans_saati`)

| kova | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |
|---|---:|---:|---:|---:|---:|---:|---:|
| 09:00 | 15505 | 66.3% | +1.7 pp | 52.7% | 3.16 | 63.0% | 30.9% |
| 10:00 | 4167 | 64.8% | +0.2 pp | 50.2% | 2.99 | 61.6% | 28.7% |
| 11:00 | 7952 | 65.1% | +0.5 pp | 51.3% | 3.06 | 60.8% | 27.9% |
| 12:00 | 3836 | 65.0% | +0.3 pp | 50.9% | 3.03 | 59.6% | 26.6% |
| 13:00 | 14532 | 66.5% | +1.9 pp | 53.2% | 3.17 | 62.0% | 30.0% |
| 14:00 | 4491 | 65.2% | +0.5 pp | 51.8% | 3.21 | 62.7% | 29.7% |
| 15:00 | 8548 | 67.5% | +2.9 pp | 54.9% | 3.25 | 64.3% | 33.0% |
| 16:00 | 4264 | 68.6% | +4.0 pp | 56.0% | 3.36 | 64.5% | 33.7% |
| 17:00 | 16815 | 68.1% | +3.5 pp | 55.8% | 3.27 | 63.6% | 32.7% |

## 7.5 · Hangi alarm türü gerçekten değerli? — kanal × bağlam

Tablo **Wilson %95 alt sınırına** göre sıralı (n ≥ 300); alt sınır az veriyle iyi görünen hücreyi cezalandırır. z, taban oranına karşı anlamlılıktır.

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

