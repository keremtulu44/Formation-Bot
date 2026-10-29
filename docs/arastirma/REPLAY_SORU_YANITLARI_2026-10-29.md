# REPLAY SORU SETİ YANITLARI — S01–S32

Üreten: ``python -m research.soru_cevaplama`` · girdi: arastirma_cikti_p1, arastirma_cikti_p2
Sözleşme: docs/arastirma/REPLAY_SORU_SETI_2026-10-29.md (§0 C1–C8, karar ≥12/5–12/<5 pp)

> Her blok: VERİ (n + sansür) → TABLO → ANA SAYI → KARAR (ön-kayıtlı eşikle).
> KARAR = YAZILIR / YALNIZ KART METNİ / RED / KARAR YOK (n<30) / gözlem (sansür>20%).

## §1 ZONE / TEMAS EPİZODU

### S01 · Taze zone (yaş kovası)

- **VERİ**: dokunus_no=1: 167505 epizod (yas>=0); ölçülebilir: 167062; sansür(OLCULEMEDI)%=0.3

| family | CALISTI%(<=10 bar) | n | CALISTI%(>=40 bar) | n | fark pp | karar |
| --- | --- | --- | --- | --- | --- | --- |
| FVG | 65.7 | 13216 | 69.6 | 45 | -3.9 | RED (fark=-3.9pp, |fark|<5) |
| OB | 65.1 | 18697 | 67.9 | 5131 | -2.7 | RED (fark=-2.7pp, |fark|<5) |

- **ANA SAYI**: TF×family hücrelerinde <=10 > >=40 yönü: 0/7 hücre
- **KARAR**: FVG: RED (fark=-3.9pp, |fark|<5); OB: RED (fark=-2.7pp, |fark|<5)
- **Notlar**: Yaş kovası sınırları: [0,10], (10,20], (20,40), [40,inf); 1h FVG yok → 7 TF×family hücresi (OB×4 + FVG×3).

### S02 · Rejim kayması (atr_at_touch / atr_at_birth)

- **VERİ**: rejim_orani dolu satır: 241575; ölçülebilir: 241345

| family | CALISTI%(>=1.5) | n | CALISTI%(0.8-1.2) | n | fark pp | karar |
| --- | --- | --- | --- | --- | --- | --- |
| FVG | 52.9 | 278 | 66.8 | 40349 | -13.9 | YAZILIR (fark=-13.9pp, azalis, n=278/40349, sansur<=20%) |
| OB | 62.3 | 11215 | 66.2 | 139638 | -3.8 | RED (fark=-3.8pp, |fark|<5) |

| rejim kovası (havuz) | n | olçülen | sansür% | CALISTI% | AZ% | YOK% | TERS% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.8-1.2 | 179987 | 179987 | 0.0 | 66.3 | 16.1 | 4.6 | 13.0 |
| 1.2-1.5 | 25813 | 25813 | 0.0 | 62.3 | 14.8 | 5.0 | 17.9 |
| <0.8 | 24052 | 24052 | 0.0 | 69.3 | 13.1 | 3.6 | 14.0 |
| >=1.5 | 11493 | 11493 | 0.0 | 62.1 | 15.5 | 4.8 | 17.6 |

- **ANA SAYI**: rejim_orani medyan=1.00, p90=1.30 (kart eşik adayı)
- **KARAR**: FVG: YAZILIR (fark=-13.9pp, azalis, n=278/40349, sansur<=20%); OB: RED (fark=-3.8pp, |fark|<5)
- **Notlar**: Yükseklik_atr doğumda ölçülür; rejim>=1.5'te kart cümlesi askıya kuralına bağlanır.

### S03 · Kenar ölçülemezliği (yükseklik kovası)

- **VERİ**: tüm epizodlar: 243256; kenar_tepki_sinifi=OLCULEMEDI: 59254 (24.4%)

| yükseklik kovası | n | OLCULEMEDI% | TUM_ZONE/ZONE_ICI% | güven |
| --- | --- | --- | --- | --- |
| 0-0.5 | 44627 | 49.6 | 49.6 | YETERLI |
| 0.5-1 | 102839 | 25.6 | 25.5 | YETERLI |
| 1-2 | 79138 | 12.0 | 11.9 | YETERLI |
| >=2 | 14971 | 5.1 | 4.9 | YETERLI |
| BILINMEYEN | 1681 | 33.5 | 17.2 | YETERLI |

| yukseklik_kovasi   |   ('1d', 'FVG') |   ('1d', 'OB') |   ('1h', 'OB') |   ('2h', 'FVG') |   ('2h', 'OB') |   ('4h', 'FVG') |   ('4h', 'OB') |
|:-------------------|----------------:|---------------:|---------------:|----------------:|---------------:|----------------:|---------------:|
| 0-0.5              |            50.3 |           35.8 |           43.2 |            54.2 |           45.8 |            57.6 |           51.9 |
| 0.5-1              |            20.6 |           19.1 |           25.8 |            23.7 |           26.9 |            27.7 |           28   |
| 1-2                |             8.8 |            8.2 |           12.7 |             8.8 |           13.1 |             9.6 |           12.2 |
| >=2                |             3.7 |            5.1 |            5.4 |             2.9 |            5.3 |             6.6 |            4.8 |
| BILINMEYEN         |           nan   |           32.5 |           35.4 |           nan   |           33.6 |           nan   |           33.3 |

- **ANA SAYI**: 0-0.5 ATR'de OLCULEMEDI=49.6% → kural; >=2 ATR'de 5.1% (karşılaştırma)
- **KARAR**: 0-0.5 ATR'de OLCULEMEDI=49.6% → kural; >=2 ATR'de 5.1% (karşılaştırma)
- **Notlar**: GECERSIZ kenar ayrı sayılır (dokunulan_kenar=GECERSIZ); kenar_olcum_yonu bu satırlarda None.

### S04 · Temas süresi (dokun-kaç vs sürtünme)

- **VERİ**: ölçülebilir epizod: 242668 / 243256 (sansür%=0.2)

| family | CALISTI%(1 bar) | n | CALISTI%(>=7) | n | fark pp | karar |
| --- | --- | --- | --- | --- | --- | --- |
| FVG | 68.5 | 30995 | 47.5 | 844 | +21.0 | YAZILIR (fark=+21.0pp, artis, n=30995/844, sansur<=20%) |
| OB | 69.8 | 107978 | 54.5 | 7511 | +15.3 | YAZILIR (fark=+15.3pp, artis, n=107978/7511, sansur<=20%) |

| family | süre kovası | medyan yon_tepe_atr |
| --- | --- | --- |
| FVG | 1 | 1.73 |
| FVG | 2-3 | 1.57 |
| FVG | 4-6 | 1.24 |
| FVG | >=7 | 0.85 |
| OB | 1 | 1.81 |
| OB | 2-3 | 1.53 |
| OB | 4-6 | 1.37 |
| OB | >=7 | 1.21 |

- **ANA SAYI**: FVG: YAZILIR (fark=+21.0pp, artis, n=30995/844, sansur<=20%); OB: YAZILIR (fark=+15.3pp, artis, n=107978/7511, sansur<=20%)
- **KARAR**: FVG: YAZILIR (fark=+21.0pp, artis, n=30995/844, sansur<=20%); OB: YAZILIR (fark=+15.3pp, artis, n=107978/7511, sansur<=20%)
- **Notlar**: yon_dip_atr negatif korunur (S05 stop sorusuyla birlikte okunur).

### S05 · Yol acısı (|dip|/tepe, CALISTI temaslarda)

- **VERİ**: CALISTI + oran ölçülebilir: 160066

| family | yükseklik | n | |dip|/tepe>=0.5 % | eşik kararı |
| --- | --- | --- | --- | --- |
| FVG | 0-0.5 | 12922 | 23.2 | gözlem |
| FVG | 0.5-1 | 9187 | 24.2 | gözlem |
| FVG | 1-2 | 5147 | 25.5 | stop kuralı |
| FVG | >=2 | 1462 | 25.5 | stop kuralı |
| OB | 0-0.5 | 16193 | 25.5 | stop kuralı |
| OB | 0.5-1 | 58257 | 26.0 | stop kuralı |
| OB | 1-2 | 47267 | 27.4 | stop kuralı |
| OB | >=2 | 8828 | 28.0 | stop kuralı |
| OB | BILINMEYEN | 803 | 26.7 | stop kuralı |

Havuz: medyan dip=0.09 ATR, p90 dip=1.44 ATR, genel >=0.5 payı=26.1%

- **ANA SAYI**: Genel ağır-yol payı 26.1% (eşiği aşıyor)
- **KARAR**: STOP KURALI (havuz) — hücreler tabloda
- **Notlar**: oran eşikleri ESIK_IZGARA içinden (0.25/0.5/1.0).

### S06 · Horizon 10 vs 12

- **VERİ**: her iki horizon tam dolu (sansur=False): 241255

| tf   | family   |     n |   Δmedyan(12−10) |   CALISTI%@10 |   CALISTI%@12 |   Δpp |   geçiş% |
|:-----|:---------|------:|-----------------:|--------------:|--------------:|------:|---------:|
| 1d   | FVG      |  6167 |                0 |          62   |          65.3 |   3.4 |      3.4 |
| 1d   | OB       | 18146 |                0 |          63   |          65.9 |   2.8 |      2.8 |
| 1h   | OB       | 91438 |                0 |          63.8 |          66.2 |   2.4 |      2.4 |
| 2h   | FVG      | 21907 |                0 |          64.1 |          66.5 |   2.4 |      2.4 |
| 2h   | OB       | 54781 |                0 |          63.6 |          65.8 |   2.2 |      2.2 |
| 4h   | FVG      | 14950 |                0 |          64.1 |          66.5 |   2.4 |      2.4 |
| 4h   | OB       | 33866 |                0 |          63.2 |          65.8 |   2.5 |      2.5 |

| family | direction | n | Δmedyan |
| --- | --- | --- | --- |
| FVG | bearish | 23418 | 0.000 |
| FVG | bullish | 19606 | 0.000 |
| OB | bearish | 99421 | 0.000 |
| OB | bullish | 98810 | 0.000 |

- **ANA SAYI**: Δ medyan (havuz)=0.000 ATR; en büyük |Δpp|=3.4
- **KARAR**: TAVSİYE: 10 bar (eşik: Δmedyan>=0.15 ATR ve Δpp>=3)
- **Notlar**: Sınıf geçişi: yon_h10 ve yon_h12 üzerindeki ön-tanımlı tepki sınıfı farkı.

### S07 · Temas anında terminal (terminal_dokunusta)

- **VERİ**: tüm epizodlar: 243256; terminal_dokunusta=True: 158789

| timeframe   | family   |     n |   terminal_pct |   nat_pct | guven   |
|:------------|:---------|------:|---------------:|----------:|:--------|
| 1d          | FVG      |  6313 |           92.7 |      90.5 | YETERLI |
| 1d          | OB       | 18689 |           60.4 |      58.7 | YETERLI |
| 1h          | OB       | 91725 |           59.4 |      59.2 | YETERLI |
| 2h          | FVG      | 21986 |           92.9 |      92.6 | YETERLI |
| 2h          | OB       | 55180 |           59.4 |      59   | YETERLI |
| 4h          | FVG      | 15043 |           91.6 |      91   | YETERLI |
| 4h          | OB       | 34320 |           58.9 |      58.1 | YETERLI |

no_kova × terminal%:
| family   |    1 |    2 |   3+ |
|:---------|-----:|-----:|-----:|
| FVG      | 92.4 | 95.3 | 37.5 |
| OB       | 61.1 | 58.7 | 53.3 |

yükseklik × terminal%:
| family   |   0-0.5 |   0.5-1 |   1-2 |   >=2 |   BILINMEYEN |
|:---------|--------:|--------:|------:|------:|-------------:|
| FVG      |    95.3 |    92.7 |  89.1 |  73.8 |        nan   |
| OB       |    75.4 |    64.5 |  51.6 |  36.7 |         59.7 |

- **ANA SAYI**: havuz terminal_dokunusta=65.3%; NATIVE_TERMINAL_ON_TOUCH(repoh12)=64.8%
- **KARAR**: kural zorunlu (havuz 65.3% vs eşik 10/5/5)
- **Notlar**: repoh12_window_status != COMPLETE satırlarından kart üretilmez (C3).

### S08 · Hedef zone yaşarken mi vuruluyor (repoh12, 1.0 ATR)

- **VERİ**: değerlendirilebilir epizodlar (kategori!=NOT_EVALUABLE); 1p0: 241255

| hedef | family | n | HIT_BEFORE% | AMBIGUOUS% | ONLY_AFTER% | NOT_REACHED% | güven |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5 | FVG | 43024 | 2.3 | 4.8 | 71.9 | 21.0 | YETERLI |
| 0.5 | OB | 198231 | 39.5 | 0.1 | 37.2 | 23.2 | YETERLI |
| 1.0 | FVG | 43024 | 0.9 | 3.7 | 61.7 | 33.6 | YETERLI |
| 1.0 | OB | 198231 | 34.8 | 0.3 | 30.9 | 34.0 | YETERLI |

1p0 TF×family ONLY_AFTER%:
| timeframe   | family   |     n |   only_after |
|:------------|:---------|------:|-------------:|
| 1d          | FVG      |  6167 |         61   |
| 1d          | OB       | 18146 |         31.7 |
| 1h          | OB       | 91438 |         30.7 |
| 2h          | FVG      | 21907 |         62.2 |
| 2h          | OB       | 54781 |         30.9 |
| 4h          | FVG      | 14950 |         61.4 |
| 4h          | OB       | 33866 |         30.8 |

- **ANA SAYI**: FVG: HIT_ONLY_AFTER=61.7% → kural+karne; OB: HIT_ONLY_AFTER=30.9% → kural+karne
- **KARAR**: FVG: HIT_ONLY_AFTER=61.7% → kural+karne; OB: HIT_ONLY_AFTER=30.9% → kural+karne
- **Notlar**: Bu blok kayit.py repoh genişletmesiyle (§8-E1) dokunus satırına geldi.

### S09 · Belirsizlik payı (AMBIGUOUS_ON_TERMINAL_BAR)

- **VERİ**: 1p0 değerlendirebilir: 241255

| family | yükseklik | n | AMBIGUOUS% | kural A: BEFORE% | kural B: BEFORE+AMB% | fark pp | güven etiketi |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FVG | 0-0.5 | 19632 | 1.9 | 0.6 | 2.5 | +1.9 | koru |
| FVG | 0.5-1 | 13840 | 3.2 | 1.1 | 4.3 | +3.2 | koru |
| FVG | 1-2 | 7527 | 5.3 | 1.3 | 6.6 | +5.3 | YETERLİ dusurulur |
| FVG | >=2 | 2025 | 19.0 | 1.3 | 20.2 | +19.0 | YETERLİ dusurulur |
| OB | 0-0.5 | 24675 | 0.4 | 19.6 | 20.0 | +0.4 | koru |
| OB | 0.5-1 | 88323 | 0.3 | 30.0 | 30.3 | +0.3 | koru |
| OB | 1-2 | 71077 | 0.2 | 42.3 | 42.5 | +0.2 | koru |
| OB | >=2 | 12836 | 0.1 | 56.4 | 56.6 | +0.1 | koru |
| OB | BILINMEYEN | 1320 | 0.2 | 34.5 | 34.7 | +0.2 | koru |

- **ANA SAYI**: iki sayım kuralı farkı en yüksek 19.0 pp
- **KARAR**: güven etiketi düşürmesi zorunlu (>=5 pp)

### S10 · Efor–sonuç uçurumu (effort_result_class)

- **VERİ**: kapıdan geçen (ready&usable): 222494; ölçülebilir tepki: 222268; kapalı oran: 8.5%

| family | CALISTI% WEAK(h10+h11) | n | CALISTI% STRONG(h9) | n | fark pp | karar |
| --- | --- | --- | --- | --- | --- | --- |
| FVG | 64.3 | 1617 | 60.7 | 2003 | +3.6 | RED (fark=+3.6pp, |fark|<5) |
| OB | 81.1 | 6383 | 46.8 | 15737 | +34.3 | YAZILIR (fark=+34.3pp, artis, n=6383/15737, sansur<=20%) |

sınıf × family CALISTI%:
| vp_effort_result_class       |   FVG |   OB |
|:-----------------------------|------:|-----:|
| HIGH_EFFORT_STRONG_RESULT    |  60.7 | 46.8 |
| HIGH_EFFORT_WEAK_RESULT      |  66.7 | 88.2 |
| NEUTRAL                      |  67   | 68.3 |
| RISING_EFFORT_STRONG_RESULT  |  61   | 49.6 |
| VERY_HIGH_EFFORT_WEAK_RESULT |  64.2 | 81.1 |

(n)
| vp_effort_result_class       |   FVG |     OB |
|:-----------------------------|------:|-------:|
| HIGH_EFFORT_STRONG_RESULT    |  2003 |  15737 |
| HIGH_EFFORT_WEAK_RESULT      |    51 |     68 |
| NEUTRAL                      | 34556 | 150850 |
| RISING_EFFORT_STRONG_RESULT  |  1780 |   9342 |
| VERY_HIGH_EFFORT_WEAK_RESULT |  1566 |   6315 |

- **ANA SAYI**: FVG: RED (fark=+3.6pp, |fark|<5); OB: YAZILIR (fark=+34.3pp, artis, n=6383/15737, sansur<=20%)
- **KARAR**: FVG: RED (fark=+3.6pp, |fark|<5); OB: YAZILIR (fark=+34.3pp, artis, n=6383/15737, sansur<=20%)
- **Notlar**: WEAK = HIGH_EFFORT_WEAK_RESULT + VERY_HIGH_EFFORT_WEAK_RESULT (§8-E5).

### S11 · Yönlü baskı uyumu (pressure_5 vs zone yönü)

- **VERİ**: uyumlu/ters etiketli: 222092; ölçülebilir: 221866

| family | arrival_side | CALISTI% uyumlu | n | CALISTI% ters | n | fark pp | karar |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FVG | FROM_ABOVE | 74.9 | 8994 | 59.3 | 7972 | +15.6 | YAZILIR (fark=+15.6pp, artis, n=8994/7972, sansur<=20%) |
| FVG | FROM_BELOW | 70.4 | 14791 | 51.9 | 6154 | +18.5 | YAZILIR (fark=+18.5pp, artis, n=14791/6154, sansur<=20%) |
| FVG | ON_ZONE_BOUNDARY | 77.9 | 1367 | 52.6 | 645 | +25.3 | YAZILIR (fark=+25.3pp, artis, n=1367/645, sansur<=20%) |
| OB | FROM_ABOVE | 79.3 | 25057 | 60.4 | 65631 | +18.8 | YAZILIR (fark=+18.8pp, artis, n=25057/65631, sansur<=20%) |
| OB | FROM_BELOW | 77.8 | 39325 | 57.8 | 51930 | +20.0 | YAZILIR (fark=+20.0pp, artis, n=39325/51930, sansur<=20%) |

medyan pressure_5: ters=-0.065, uyumlu=-0.080

- **ANA SAYI**: FVG/FROM_ABOVE: YAZILIR (fark=+15.6pp, artis, n=8994/7972, sansur<=20%); FVG/FROM_BELOW: YAZILIR (fark=+18.5pp, artis, n=14791/6154, sansur<=20%); FVG/ON_ZONE_BOUNDARY: YAZILIR (fark=+25.3pp, artis, n=1367/645, sansur<=20%); OB/FROM_ABOVE: YAZILIR (fark=+18.8pp, artis, n=25057/65631, sansur<=20%); OB/FROM_BELOW: YAZILIR (fark=+20.0pp, artis, n=39325/51930, sansur<=20%)
- **KARAR**: FVG/FROM_ABOVE: YAZILIR (fark=+15.6pp, artis, n=8994/7972, sansur<=20%); FVG/FROM_BELOW: YAZILIR (fark=+18.5pp, artis, n=14791/6154, sansur<=20%); FVG/ON_ZONE_BOUNDARY: YAZILIR (fark=+25.3pp, artis, n=1367/645, sansur<=20%); OB/FROM_ABOVE: YAZILIR (fark=+18.8pp, artis, n=25057/65631, sansur<=20%); OB/FROM_BELOW: YAZILIR (fark=+20.0pp, artis, n=39325/51930, sansur<=20%)
- **Notlar**: INSIDE_ZONE / ON_ZONE_BOUNDARY / NO_PREVIOUS_BAR ayrı kovada (tabloda).

### S12 · Hacim ölçütü çelişkisi (rank vs z)

- **VERİ**: kapıdan geçen ölçülebilir 222268; uç çeyrek kesişimi 97327

| family | hücre (R=rank, Z=z) | n | CALISTI% | güven |
| --- | --- | --- | --- | --- |
| FVG | RQ1ZQ1 | 8154 | 70.4 | YETERLI |
| FVG | RQ4ZQ4 | 5923 | 61.0 | YETERLI |
| OB | RQ1ZQ1 | 41622 | 67.7 | YETERLI |
| OB | RQ4ZQ4 | 41628 | 60.3 | YETERLI |

uç hücre sayıları:
| uç hücre | n |
| --- | --- |
| RQ4Z4 | 0 |
| RQ4Z1 | 0 |
| RQ1Z4 | 0 |
| RQ1Z1 | 0 |

- **ANA SAYI**: ÇELİŞKİ YOK (her iki zıt hücre de 0 satır): volume_percent_rank ve volume_z_score AYNI pencerenin monotone dönüşümüdür — yüksek rank ⇔ yüksek z; iki ölçüt asla ayrışmaz. SONUÇ: 'hangi ölçüt doğru' sorusu yapısal olarak boştur; kart standardı = TEK ölçüt (rvol) yeterlidir, ek ölçüt eklenmez (S12 RED: fark yok).
- **KARAR**: RED / kart standardı: rvol tek ölçüt (çelişki yapısal olarak yok)
- **Notlar**: Çeyrekler içsel sıralama (run içi); zıt hücreler (RQ4Z1/RQ1Z4) aynı pencere-monotonite nedeniyle 0 çıkabilir — bu bir bulgudur.

### S13 · Saat dilimi etkisi (1h, Europe/Istanbul)

- **VERİ**: 1h epizod (10–17 arası saat): 64634

| family | CALISTI% 10:00 | n | CALISTI% 17:00 | n | ref 12–15 ort. | n | Δ10 pp | Δ17 pp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OB | 64.1 | 10076 | 67.0 | 6329 | 66.8 | 22084 | -2.7 | +0.2 |

tüm saatler:
| family   |   10 |   11 |   12 |   13 |   14 |   15 |   16 |   17 |
|:---------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|
| OB       | 64.1 | 65.6 | 66.9 | 67.5 |   66 | 68.1 | 69.6 |   67 |

- **ANA SAYI**: OB: en_iyi−en_kötü +5.5pp → kart metni
- **KARAR**: OB: en_iyi−en_kötü +5.5pp → kart metni
- **Notlar**: 1d'de saat anlamsız → kapsam 1h.

### S14 · Hacim veri kapısı

- **VERİ**: epizod: 243256; run_meta: 708

| timeframe   | family   |     n |   kapali_pct | guven   |
|:------------|:---------|------:|-------------:|:--------|
| 1d          | FVG      |  6313 |         24.9 | YETERLI |
| 1d          | OB       | 18689 |         25.3 | YETERLI |
| 1h          | OB       | 91725 |          4.7 | YETERLI |
| 2h          | FVG      | 21986 |          4.3 | YETERLI |
| 2h          | OB       | 55180 |          7.7 | YETERLI |
| 4h          | FVG      | 15043 |          5.6 | YETERLI |
| 4h          | OB       | 34320 |         11.9 | YETERLI |

vp_data_quality (run_meta): PARTICIPATION_UPPER_ABSORPTION_CONFIRMED=181, PARTICIPATION_CONFLICT=152, PARTICIPATION_LOWER_ABSORPTION_CONFIRMED=115, PARTICIPATION_LOWER_ABSORPTION_INVALIDATED=62, PARTICIPATION_DOWN_ENDED=53, PARTICIPATION_DOWN_BREAK_SUPPORTED=52, PARTICIPATION_UP_BREAK_SUPPORTED=39, PARTICIPATION_UPPER_ABSORPTION_INVALIDATED=34, PARTICIPATION_VOLUME_UNAVAILABLE=7, PARTICIPATION_DOWN_BREAK_UNSUPPORTED=6, PARTICIPATION_NEUTRAL=2, PARTICIPATION_LOW=2, PARTICIPATION_RISING=1, PARTICIPATION_DOWN_CANDIDATE=1, PARTICIPATION_UP_BREAK_RECLAIMED=1

- **ANA SAYI**: en kötü hücre kapanı 25.3%
- **KARAR**: S10–S12 için kapalı hücreler var (max 25.3%) → o hücrelerde karar yok

### S15 · Zone tekrar ziyareti

- **VERİ**: repoh12 tam pencere + CALISTI/YOK: 170362; bayraklı: 45499

| family | dokunus_no | CALISTI'de bayrak% | n | YOK'ta bayrak% | n | fark pp | karar |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FVG | 1 | 1.3 | 28199 | 0.1 | 1817 | +1.2 | RED (fark=+1.2pp, |fark|<5) |
| FVG | 2 | 0.6 | 346 | 0.0 | 17 | +0.6 | KARAR YOK (guven: KISMI; n1=346, n2=17) |
| OB | 1 | 32.9 | 81647 | 0.1 | 5919 | +32.7 | YAZILIR (fark=+32.7pp, artis, n=81647/5919, sansur<=20%) |
| OB | 2 | 35.1 | 29283 | 0.2 | 1965 | +34.9 | YAZILIR (fark=+34.9pp, artis, n=29283/1965, sansur<=20%) |
| OB | 3+ | 40.3 | 19915 | 0.0 | 1251 | +40.3 | YAZILIR (fark=+40.3pp, artis, n=19915/1251, sansur<=20%) |

- **ANA SAYI**: dönüş gecikmesi medyanı (bayraklı CALISTI): 5.0 bar
- **KARAR**: FVG/no1: RED (fark=+1.2pp, |fark|<5); FVG/no2: KARAR YOK (guven: KISMI; n1=346, n2=17); OB/no1: YAZILIR (fark=+32.7pp, artis, n=81647/5919, sansur<=20%); OB/no2: YAZILIR (fark=+34.9pp, artis, n=29283/1965, sansur<=20%); OB/no3+: YAZILIR (fark=+40.3pp, artis, n=19915/1251, sansur<=20%)
- **Notlar**: Bayrak repoh12_next_same_zone_touch_in_window; pencere tam değilse False (kod sözleşmesi).

## §2 MS SWING

### S16 · Rol süresi → koruma (PH/PL)

- **VERİ**: PH/PL + engelledi_025 dolu: 86004 rol aralığı

| scope | side | rol süresi | n | engelledi_025=True% | sansür(None)% | güven |
| --- | --- | --- | --- | --- | --- | --- |
| EXTERNAL | HIGH | 1-5 | 1023 | 66.4 | 0.0 | YETERLI |
| EXTERNAL | HIGH | 11-20 | 3205 | 58.5 | 0.0 | YETERLI |
| EXTERNAL | HIGH | 6-10 | 1116 | 32.3 | 0.0 | YETERLI |
| EXTERNAL | HIGH | >=21 | 9321 | 81.1 | 0.0 | YETERLI |
| EXTERNAL | LOW | 1-5 | 1418 | 74.1 | 0.0 | YETERLI |
| EXTERNAL | LOW | 11-20 | 3154 | 63.0 | 0.0 | YETERLI |
| EXTERNAL | LOW | 6-10 | 1004 | 44.4 | 0.0 | YETERLI |
| EXTERNAL | LOW | >=21 | 9554 | 82.2 | 0.0 | YETERLI |
| INTERNAL | HIGH | 1-5 | 4084 | 45.4 | 0.0 | YETERLI |
| INTERNAL | HIGH | 11-20 | 8601 | 57.9 | 0.0 | YETERLI |
| INTERNAL | HIGH | 6-10 | 6229 | 53.1 | 0.0 | YETERLI |
| INTERNAL | HIGH | >=21 | 9178 | 72.9 | 0.0 | YETERLI |
| INTERNAL | LOW | 1-5 | 3817 | 54.4 | 0.0 | YETERLI |
| INTERNAL | LOW | 11-20 | 8372 | 62.5 | 0.0 | YETERLI |
| INTERNAL | LOW | 6-10 | 6046 | 59.2 | 0.0 | YETERLI |
| INTERNAL | LOW | >=21 | 9882 | 74.0 | 0.0 | YETERLI |

- **ANA SAYI**: EXTERNAL/HIGH: fark +14.7pp (n=9321/1023) → YAZILIR (fark=+14.7pp, artis, n=9321/1023, sansur<=20%); EXTERNAL/LOW: fark +8.1pp (n=9554/1418) → YALNIZ KART METNI (fark=+8.1pp, n=9554/1418); INTERNAL/HIGH: fark +27.5pp (n=9178/4084) → YAZILIR (fark=+27.5pp, artis, n=9178/4084, sansur<=20%); INTERNAL/LOW: fark +19.6pp (n=9882/3817) → YAZILIR (fark=+19.6pp, artis, n=9882/3817, sansur<=20%)
- **KARAR**: EXTERNAL/HIGH:YAZILIR; EXTERNAL/LOW:YALNIZ KART METNI; INTERNAL/HIGH:YAZILIR; INTERNAL/LOW:YAZILIR
- **Notlar**: scope/side büyük harf gerçek değerler (§8-E7).

### S17 · Belirginlik → koruma

- **VERİ**: prominence + engelledi dolu: 410229

| scope | side | prominence | n | engelledi=True% | güven |
| --- | --- | --- | --- | --- | --- |
| EXTERNAL | HIGH | 0.5-1 | 32 | 43.8 | YETERLI |
| EXTERNAL | HIGH | 1-2 | 4970 | 43.0 | YETERLI |
| EXTERNAL | HIGH | >=2 | 60790 | 55.1 | YETERLI |
| EXTERNAL | LOW | 0.5-1 | 19 | 47.4 | KISMI |
| EXTERNAL | LOW | 1-2 | 4290 | 38.7 | YETERLI |
| EXTERNAL | LOW | >=2 | 63046 | 57.0 | YETERLI |
| INTERNAL | HIGH | 0-0.5 | 64 | 35.9 | YETERLI |
| INTERNAL | HIGH | 0.5-1 | 2547 | 36.4 | YETERLI |
| INTERNAL | HIGH | 1-2 | 54080 | 40.0 | YETERLI |
| INTERNAL | HIGH | >=2 | 80878 | 49.6 | YETERLI |
| INTERNAL | LOW | 0-0.5 | 36 | 38.9 | YETERLI |
| INTERNAL | LOW | 0.5-1 | 2155 | 29.9 | YETERLI |
| INTERNAL | LOW | 1-2 | 54450 | 38.6 | YETERLI |
| INTERNAL | LOW | >=2 | 82872 | 53.3 | YETERLI |

- **ANA SAYI**: INTERNAL/HIGH: >=2 vs <0.5 fark +13.7pp; INTERNAL/LOW: >=2 vs <0.5 fark +14.4pp
- **KARAR**: INTERNAL/HIGH:YAZILIR; INTERNAL/LOW:YAZILIR
- **Notlar**: Kovalar yükseklik kovası sınırlarıyla aynı.

### S18 · Geç rol ataması

- **VERİ**: capa+confirm+engelledi dolu: 410229 (ROL_ATANMADI hariç; havuzda %28.4 )

| scope | atama gecikmesi | n | engelledi=True% | güven |
| --- | --- | --- | --- | --- |
| EXTERNAL | 0-1 | 108297 | 48.3 | YETERLI |
| EXTERNAL | 2-4 | 3225 | 74.7 | YETERLI |
| EXTERNAL | >=5 | 21625 | 85.5 | YETERLI |
| INTERNAL | 0-1 | 232110 | 40.7 | YETERLI |
| INTERNAL | 2-4 | 7876 | 67.0 | YETERLI |
| INTERNAL | >=5 | 37096 | 77.4 | YETERLI |

- **ANA SAYI**: EXTERNAL: 0-1 vs >=5 fark -37.2pp; INTERNAL: 0-1 vs >=5 fark -36.7pp
- **KARAR**: EXTERNAL:YAZILIR; INTERNAL:YAZILIR
- **Notlar**: gecikme = capa_bar − confirm_bar (rol atama anı − onay).

### S19 · Rol kapanış türü (DEVREDILDI / TEMIZLENDI / …)

- **VERİ**: tüm rol aralıkları: 416685

| scope | side | kapanış | n | pay% | broken% | medyan süre |
| --- | --- | --- | --- | --- | --- | --- |
| EXTERNAL | HIGH | DEVREDILDI | 28518 | 42.2 | 0.1 | 19.0 |
| EXTERNAL | HIGH | TEMIZLENDI | 20439 | 30.2 | 63.9 | 10.0 |
| EXTERNAL | HIGH | VERI_SONU_SANSURLU | 1140 | 1.7 | 0.0 | 13.0 |
| EXTERNAL | HIGH | ROL_ATANMADI | 17537 | 25.9 | 13.3 | - |
| EXTERNAL | LOW | DEVREDILDI | 28055 | 41.5 | 0.1 | 19.0 |
| EXTERNAL | LOW | TEMIZLENDI | 20558 | 30.4 | 65.3 | 11.0 |
| EXTERNAL | LOW | VERI_SONU_SANSURLU | 341 | 0.5 | 0.0 | 23.0 |
| EXTERNAL | LOW | ROL_ATANMADI | 18722 | 27.7 | 11.4 | - |
| INTERNAL | HIGH | DEVREDILDI | 62047 | 44.0 | 0.1 | 9.0 |
| INTERNAL | HIGH | TEMIZLENDI | 38510 | 27.3 | 60.5 | 6.0 |
| INTERNAL | HIGH | VERI_SONU_SANSURLU | 1158 | 0.8 | 0.0 | 7.0 |
| INTERNAL | HIGH | ROL_ATANMADI | 39369 | 27.9 | 13.4 | - |
| INTERNAL | LOW | DEVREDILDI | 58098 | 41.4 | 0.2 | 9.0 |
| INTERNAL | LOW | TEMIZLENDI | 39172 | 27.9 | 63.3 | 6.0 |
| INTERNAL | LOW | VERI_SONU_SANSURLU | 378 | 0.3 | 0.0 | 11.0 |
| INTERNAL | LOW | ROL_ATANMADI | 42643 | 30.4 | 11.4 | - |

rol × DEVREDILDI payı:
| scope | rol | n | DEVREDILDI% | güven |
| --- | --- | --- | --- | --- |
| EXTERNAL | PH | 15353 | 64.2 | YETERLI |
| EXTERNAL | PL | 15174 | 65.4 | YETERLI |
| EXTERNAL | SH | 9864 | 60.3 | YETERLI |
| EXTERNAL | SL | 9928 | 62.9 | YETERLI |
| EXTERNAL | WH | 24880 | 51.1 | YETERLI |
| EXTERNAL | WL | 23852 | 49.8 | YETERLI |
| INTERNAL | PH | 29260 | 66.8 | YETERLI |
| INTERNAL | PL | 28234 | 66.1 | YETERLI |
| INTERNAL | SH | 19553 | 64.1 | YETERLI |
| INTERNAL | SL | 18671 | 64.1 | YETERLI |
| INTERNAL | WH | 52902 | 56.6 | YETERLI |
| INTERNAL | WL | 50743 | 54.1 | YETERLI |

- **ANA SAYI**: havuz DEVREDILDI payı 42.4% (eşik: >=25 kart cümlesi, <10 koru)
- **KARAR**: DEVREDILDI kart cümlesi yazılır
- **Notlar**: 'KIRILDI' kapanış türü YOK; kırılım ayrı alandır (broken). §8-E6.

### S20 · İç yapı kırılımı sığ mı (kirilim_atr < 0.25)

- **VERİ**: broken=True: 89408

| scope | side | n | olçülen | sansür% | medyan aşım ATR | medyan bars_to_break | sığ% (<0.25) | güven |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EXTERNAL | HIGH | 15414 | 14041 | 8.9 | 1.198 | 6.0 | 4.6 | YETERLI |
| EXTERNAL | LOW | 15581 | 13930 | 10.6 | 0.810 | 7.0 | 9.7 | YETERLI |
| INTERNAL | HIGH | 28648 | 27701 | 3.3 | 1.129 | 3.0 | 4.7 | YETERLI |
| INTERNAL | LOW | 29765 | 28662 | 3.7 | 0.768 | 4.0 | 10.2 | YETERLI |

bars_to_break kovası dağılımı:
| scope    |    1 |   2-3 |   4-6 |   >=7 |   yok |
|:---------|-----:|------:|------:|------:|------:|
| EXTERNAL | 3841 |  3353 |  4001 | 15915 |  3885 |
| INTERNAL | 8960 | 10313 |  9032 | 20503 |  9605 |

- **ANA SAYI**: HIGH: INTERNAL sığ kırılım 4.7% → kural-red | LOW: INTERNAL sığ kırılım 10.2% → kural-red
- **KARAR**: HIGH: INTERNAL sığ kırılım 4.7% → kural-red | LOW: INTERNAL sığ kırılım 10.2% → kural-red
- **Notlar**: kirilim_bar pencere-içi 1-tabanlı konum; mutlak bar broken_bar (§8-E15).

### S21 · Rol atama hacmi → koruma (verimlilik çeyrekleri)

- **VERİ**: vp_ready + engelledi dolu: 370861

| scope | çeyrek | n | engelledi=True% | güven |
| --- | --- | --- | --- | --- |
| EXTERNAL | Q1 | 30285 | 50.4 | YETERLI |
| EXTERNAL | Q2 | 30285 | 52.4 | YETERLI |
| EXTERNAL | Q3 | 30284 | 55.9 | YETERLI |
| EXTERNAL | Q4 | 30285 | 61.0 | YETERLI |
| INTERNAL | Q1 | 62431 | 41.9 | YETERLI |
| INTERNAL | Q2 | 62430 | 42.3 | YETERLI |
| INTERNAL | Q3 | 62430 | 46.8 | YETERLI |
| INTERNAL | Q4 | 62431 | 54.1 | YETERLI |

- **ANA SAYI**: EXTERNAL: Q4−Q1 +10.6pp; INTERNAL: Q4−Q1 +12.1pp
- **KARAR**: EXTERNAL:YALNIZ KART METNI; INTERNAL:YAZILIR
- **Notlar**: Çeyrekler scope içi içsel sıralama (run içi).

## §3 MS OLAY

### S22 · Olgunluk → devamlılık (BOS/CHOCH)

- **VERİ**: olgunluk+devamlılık dolu olay: 81527 (toplam 202938)

| scope | tip | n INITIAL | CALISTI% INITIAL | n CONT | CALISTI% CONT | fark pp | karar |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EXTERNAL | EVENT_BOS | 703 | 70.0 | 14179 | 67.8 | +2.2 | RED (fark=+2.2pp, |fark|<5) |
| INTERNAL | EVENT_BOS | 540 | 71.1 | 27950 | 67.6 | +3.5 | RED (fark=+3.5pp, |fark|<5) |

BOS dağılımı:
|                                         |   AZ_DEVAM |   CALISTI |   DEVAM_YOK |   TERS |
|:----------------------------------------|-----------:|----------:|------------:|-------:|
| ('EXTERNAL', 'CONTINUATION')            |       3211 |      9611 |        1197 |    160 |
| ('EXTERNAL', 'INITIAL_STRUCTURE')       |        153 |       492 |          53 |      5 |
| ('EXTERNAL', 'TRANSITION_CONFIRMATION') |       1261 |      3821 |         462 |     43 |
| ('INTERNAL', 'CONTINUATION')            |       6318 |     18896 |        2433 |    303 |
| ('INTERNAL', 'INITIAL_STRUCTURE')       |        107 |       384 |          38 |     11 |
| ('INTERNAL', 'TRANSITION_CONFIRMATION') |       2276 |      6967 |         872 |    120 |

- **ANA SAYI**: EXTERNAL/EVENT_BOS: +2.2pp; INTERNAL/EVENT_BOS: +3.5pp
- **KARAR**: EXTERNAL/EVENT_BOS:RED; INTERNAL/EVENT_BOS:RED
- **Notlar**: bos_maturity: NOT_APPLICABLE/INITIAL_STRUCTURE/TRANSITION_CONFIRMATION/CONTINUATION.

### S23 · Onay gecikmesi → devamlılık

- **VERİ**: onay_gecikmesi dolu: 202938

| scope | tip | n 0-1 | medyan devam_h12 | n >=4 | medyan devam_h12 | Δ medyan | CALISTI% fark | pp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EXTERNAL | EVENT_FALSE_BREAK | 1003 | 1.55 | 207 | 1.76 | 0.21 | 2.8 | +2.8 |
| INTERNAL | EVENT_FALSE_BREAK | 1959 | 1.48 | 247 | 1.82 | 0.34 | 2.8 | +2.8 |

- **ANA SAYI**: EXTERNAL/EVENT_FALSE_BREAK: Δmedyan=0.21 ATR, ΔCALISTI=+2.8pp → kart dipnotu | INTERNAL/EVENT_FALSE_BREAK: Δmedyan=0.34 ATR, ΔCALISTI=+2.8pp → RED: hipotez ters (geç onaylılar daha iyi; gecikme cezası kurulmaz)
- **KARAR**: EXTERNAL/EVENT_FALSE_BREAK: Δmedyan=0.21 ATR, ΔCALISTI=+2.8pp → kart dipnotu | INTERNAL/EVENT_FALSE_BREAK: Δmedyan=0.34 ATR, ΔCALISTI=+2.8pp → RED: hipotez ters (geç onaylılar daha iyi; gecikme cezası kurulmaz)
- **Notlar**: event_bar yoksa gecikme None → kapsam dışı (§8-E13b).

### S24 · Sahte kırılım/süpürme kontra sinyali

- **VERİ**: ters_h12 dolu: 202550

| scope | tip | n | medyan ters_h12 | ters>=1.0% | güven |
| --- | --- | --- | --- | --- | --- |
| EXTERNAL | EVENT_BOS | 20469 | 1.52 | 64.5 | YETERLI |
| EXTERNAL | EVENT_CHOCH | 7878 | 1.51 | 64.4 | YETERLI |
| EXTERNAL | EVENT_FALSE_BREAK | 1565 | 1.47 | 63.9 | YETERLI |
| EXTERNAL | EVENT_SWEEP | 42892 | 1.56 | 65.3 | YETERLI |
| EXTERNAL | EVENT_TRANSITION_FAIL | 2150 | 1.56 | 64.9 | YETERLI |
| INTERNAL | EVENT_BOS | 38725 | 1.51 | 64.4 | YETERLI |
| INTERNAL | EVENT_CHOCH | 14455 | 1.47 | 63.3 | YETERLI |
| INTERNAL | EVENT_FALSE_BREAK | 2780 | 1.50 | 63.3 | YETERLI |
| INTERNAL | EVENT_SWEEP | 67536 | 1.58 | 65.8 | YETERLI |
| INTERNAL | EVENT_TRANSITION_FAIL | 4100 | 1.54 | 64.4 | YETERLI |

- **ANA SAYI**: EXTERNAL EVENT_SWEEP vs BOS: +0.8pp → kontra reddedilir | EXTERNAL EVENT_FALSE_BREAK vs BOS: -0.6pp → kontra reddedilir | EXTERNAL EVENT_CHOCH vs BOS: -0.1pp → kontra reddedilir | INTERNAL EVENT_SWEEP vs BOS: +1.4pp → kontra reddedilir | INTERNAL EVENT_FALSE_BREAK vs BOS: -1.1pp → kontra reddedilir | INTERNAL EVENT_CHOCH vs BOS: -1.1pp → kontra reddedilir
- **KARAR**: EXTERNAL EVENT_SWEEP vs BOS: +0.8pp → kontra reddedilir | EXTERNAL EVENT_FALSE_BREAK vs BOS: -0.6pp → kontra reddedilir | EXTERNAL EVENT_CHOCH vs BOS: -0.1pp → kontra reddedilir | INTERNAL EVENT_SWEEP vs BOS: +1.4pp → kontra reddedilir | INTERNAL EVENT_FALSE_BREAK vs BOS: -1.1pp → kontra reddedilir | INTERNAL EVENT_CHOCH vs BOS: -1.1pp → kontra reddedilir
- **Notlar**: ters_h12: olay yönünün TERSİNE 12 bar maksimum (negatif korunur).

### S25 · Olay ezilmesi (relevance)

- **VERİ**: tüm olaylar: 202938; SUPERSEDED: 171023

| scope | tip | relevance | pay% | not |
| --- | --- | --- | --- | --- |
| EXTERNAL | EVENT_BOS | CURRENT | 6.8 | 20495 |
| EXTERNAL | EVENT_BOS | SUPERSEDED | 93.2 |  |
| EXTERNAL | EVENT_BOS | HISTORICAL | 0.0 |  |
| EXTERNAL | EVENT_CHOCH | CURRENT | 1.7 | 7881 |
| EXTERNAL | EVENT_CHOCH | SUPERSEDED | 0.0 |  |
| EXTERNAL | EVENT_CHOCH | HISTORICAL | 98.3 |  |
| EXTERNAL | EVENT_FALSE_BREAK | CURRENT | 51.4 | 1565 |
| EXTERNAL | EVENT_FALSE_BREAK | SUPERSEDED | 48.6 |  |
| EXTERNAL | EVENT_FALSE_BREAK | HISTORICAL | 0.0 |  |
| EXTERNAL | EVENT_SWEEP | CURRENT | 3.3 | 42896 |
| EXTERNAL | EVENT_SWEEP | SUPERSEDED | 96.7 |  |
| EXTERNAL | EVENT_SWEEP | HISTORICAL | 0.0 |  |
| EXTERNAL | EVENT_TRANSITION_FAIL | CURRENT | 44.3 | 2151 |
| EXTERNAL | EVENT_TRANSITION_FAIL | SUPERSEDED | 55.7 |  |
| EXTERNAL | EVENT_TRANSITION_FAIL | HISTORICAL | 0.0 |  |
| INTERNAL | EVENT_BOS | CURRENT | 3.6 | 38927 |
| INTERNAL | EVENT_BOS | SUPERSEDED | 96.4 |  |
| INTERNAL | EVENT_BOS | HISTORICAL | 0.0 |  |
| INTERNAL | EVENT_CHOCH | CURRENT | 0.8 | 14463 |
| INTERNAL | EVENT_CHOCH | SUPERSEDED | 0.0 |  |
| INTERNAL | EVENT_CHOCH | HISTORICAL | 99.2 |  |
| INTERNAL | EVENT_FALSE_BREAK | CURRENT | 37.8 | 2790 |
| INTERNAL | EVENT_FALSE_BREAK | SUPERSEDED | 62.2 |  |
| INTERNAL | EVENT_FALSE_BREAK | HISTORICAL | 0.0 |  |
| INTERNAL | EVENT_SWEEP | CURRENT | 2.1 | 67666 |
| INTERNAL | EVENT_SWEEP | SUPERSEDED | 97.9 |  |
| INTERNAL | EVENT_SWEEP | HISTORICAL | 0.0 |  |
| INTERNAL | EVENT_TRANSITION_FAIL | CURRENT | 28.6 | 4104 |
| INTERNAL | EVENT_TRANSITION_FAIL | SUPERSEDED | 71.4 |  |
| INTERNAL | EVENT_TRANSITION_FAIL | HISTORICAL | 0.0 |  |

- **ANA SAYI**: SUPERSEDED olayların seri-sonu yaşı medyan=976.0 bar (tüm olaylar havuz medyanı 926)
- **KARAR**: EXTERNAL BOS: SUPERSEDED 93.2% → bastırma kuralı | INTERNAL BOS: SUPERSEDED 96.4% → bastırma kuralı
- **Notlar**: age_bars = event_bar'dan serinin sonuna süre (ledger'da EZİLME ANINDA donmaz); 'ezilme süresi' olarak okunmamalı — ezilme hızını relevance payları verir (BOS %93–96).

### S26 · Kırılım hızı (ani kırılım, BOS)

- **VERİ**: pay_1 dolu BOS: 57647

| scope | pay_1 kovası | n | CALISTI% | n_olçülen | güven |
| --- | --- | --- | --- | --- | --- |
| EXTERNAL | 0.3-0.8 | 5040 | 71.6 | 5040 | YETERLI |
| EXTERNAL | <0.3 | 10581 | 86.9 | 10581 | YETERLI |
| EXTERNAL | >=0.8 | 4324 | 25.9 | 4324 | YETERLI |
| INTERNAL | 0.3-0.8 | 9553 | 70.3 | 9553 | YETERLI |
| INTERNAL | <0.3 | 20048 | 87.0 | 20048 | YETERLI |
| INTERNAL | >=0.8 | 8101 | 25.9 | 8101 | YETERLI |

- **ANA SAYI**: pay_1>=0.8 payı=21.6%; medyan tepe bar=6; hareketin ort. %60'i ilk 3 barda (medyan pay_3)
- **KARAR**: EXTERNAL: fark -61.0pp → YAZILIR; INTERNAL: fark -61.1pp → YAZILIR
- **Notlar**: Mekanizma (kayit.py): h12 = bar+1'den itibaren 12 bar; devam_pay_1 ≥0.8 ise tepe zaten 1. bara kilitlenmiş → CALISTI yalnızca o ilk barın ≥1.0 ATR olmasıyla gelir. Fark büyük ölçüde TANIMSAL; kart metninde yön 'ilk barda tükenmiş/uzanım sınırlı' dilinde yazılır, 'devam etmez' genellemesi kurulmaz.

## §4 FORMASYON

### S27 · Faz çırpınması → sonuç

- **VERİ**: frm: 34455 (kova dışı: 0); bu bölüm 34455; kapalı (sansürsüz) 34282

| tf | geçiş | n | TAMAMLANDI% | açık% | güven |
| --- | --- | --- | --- | --- | --- |
| 1d | 3-5 | 1057 | 75.1 | 1.3 | YETERLI |
| 1d | <=2 | 240 | 0.0 | 15.0 | YETERLI |
| 1d | >=6 | 711 | 69.1 | 1.0 | YETERLI |
| 1h | 3-5 | 10623 | 82.3 | 0.1 | YETERLI |
| 1h | <=2 | 1571 | 0.0 | 1.3 | YETERLI |
| 1h | >=6 | 6593 | 77.9 | 0.1 | YETERLI |
| 2h | 3-5 | 4989 | 81.1 | 0.1 | YETERLI |
| 2h | <=2 | 822 | 0.0 | 1.9 | YETERLI |
| 2h | >=6 | 3349 | 77.5 | 0.4 | YETERLI |
| 4h | 3-5 | 2350 | 79.5 | 0.8 | YETERLI |
| 4h | <=2 | 447 | 0.0 | 4.7 | YETERLI |
| 4h | >=6 | 1703 | 76.9 | 0.4 | YETERLI |

kova × terminal_state:
| gecis_kova   |   BASARISIZ_KIRILIM |   FORMASYON_GECERSIZ |   FORMASYON_TAMAMLANDI |   FORMASYON_TANIMLANDI |   FORMASYON_ZAYIFLADI |   KIRILIM_ADAYI |   KIRILIM_DENEMESI |   KIRILIM_HAZIRLIGI |   KIRILIM_TEYITLI |   KIRILIM_TEYIT_ALAMADI |   OLGUNLASIYOR |   RETEST_BASARILI |   RETEST_BEKLENIYOR |   RETEST_EDILIYOR |   SIKISMA_GUCLENIYOR |
|:-------------|--------------------:|---------------------:|-----------------------:|-----------------------:|----------------------:|----------------:|-------------------:|--------------------:|------------------:|------------------------:|---------------:|------------------:|--------------------:|------------------:|---------------------:|
| 3-5          |                2703 |                  575 |                  15448 |                     99 |                    52 |               3 |                  1 |                  28 |                 3 |                       1 |             21 |                 8 |                  19 |                 4 |                   54 |
| <=2          |                1290 |                  541 |                      0 |                    104 |                   262 |              16 |                  3 |                  67 |                11 |                       1 |            236 |                 1 |                   2 |                 0 |                  546 |
| >=6          |                2302 |                  403 |                   9534 |                     55 |                    10 |               1 |                  0 |                   9 |                 0 |                       1 |              2 |                 1 |                  18 |                 9 |                   11 |

(n>=30 tip hücreleri)
| pattern_type | geçiş | n | TAMAMLANDI% |
| --- | --- | --- | --- |
| Alçalan Kama | 3-5 | 3526 | 84.7 |
| Alçalan Kama | <=2 | 605 | 0.0 |
| Alçalan Kama | >=6 | 2487 | 83.1 |
| Alçalan Üçgen | 3-5 | 5223 | 78.9 |
| Alçalan Üçgen | <=2 | 937 | 0.0 |
| Alçalan Üçgen | >=6 | 3787 | 75.2 |
| Simetrik Üçgen | 3-5 | 1813 | 74.7 |
| Simetrik Üçgen | <=2 | 350 | 0.0 |
| Simetrik Üçgen | >=6 | 837 | 71.7 |
| Yükselen Kama | 3-5 | 4205 | 84.8 |
| Yükselen Kama | <=2 | 515 | 0.0 |
| Yükselen Kama | >=6 | 2251 | 76.5 |
| Yükselen Üçgen | 3-5 | 4227 | 80.6 |
| Yükselen Üçgen | <=2 | 667 | 0.0 |
| Yükselen Üçgen | >=6 | 2979 | 76.9 |

- **ANA SAYI**: İSTENEN (≤2 vs ≥6, tüm satır): 1d: -69.1pp (n=240/711); 1h: -77.9pp (n=1571/6593); 2h: -77.5pp (n=822/3349); 4h: -76.9pp (n=447/1703) | GERÇEK çırpınma (3-5 vs ≥6, kapalı): havuz +4.1pp; 1d +6.4pp; 1h +4.4pp; 2h +3.3pp; 4h +3.0pp | ≤2 kovası: TAMAMLANDI %0.0 (n=3080), BASARISIZ_KIRILIM %41.9
- **KARAR**: RED (yapısal): '6+ yayınlanmaz' kuralı KURULMAZ — çırpınma kontrastı 3-5 vs ≥6 = +4.1pp (<5); ≤2 tabanı TAMAMLANDI üretemez (TAMAMLANDI %0.0, BASARISIZ_KIRILIM %41.9)
- **Notlar**: YAPISAL: TAMAMLANDI yoluna ulaşmak için faz geçişi zorunludur — ≤2 kovası erken-kapanış kovasıdır (BASARISIZ_KIRILIM/GEÇERSIZ ağırlıklı), çırpınma ölçmez. Soru setindeki ≤2 TABANI bu yüzden yanıltıcı; eksen 3-5 vs ≥6 olmalıdır.; C4: tip×TF hücreleri n<30 ise yalnız birleşik n raporlanır.

### S28 · Açık örneklem payı (acik + yarım segment)

- **VERİ**: frm=34455, frm_olay=232792, stable_id (son olay satırı)=34455

| pattern_type | tf | n | açık% | medyan ömür (açık) | medyan ömür (kapalı) | güven |
| --- | --- | --- | --- | --- | --- | --- |
| Alçalan Kama | 1d | 429 | 6.8 | 6 | 12 | YETERLI |
| Alçalan Kama | 1h | 3492 | 0.4 | 3 | 10 | YETERLI |
| Alçalan Kama | 2h | 1759 | 0.4 | 14 | 11 | YETERLI |
| Alçalan Kama | 4h | 938 | 2.0 | 14 | 12 | YETERLI |
| Alçalan Üçgen | 1d | 662 | 3.0 | 10 | 13 | YETERLI |
| Alçalan Üçgen | 1h | 5368 | 0.2 | 4 | 11 | YETERLI |
| Alçalan Üçgen | 2h | 2633 | 0.6 | 11 | 12 | YETERLI |
| Alçalan Üçgen | 4h | 1284 | 0.9 | 7 | 13 | YETERLI |
| Ayı Bayrağı | 1d | 3 | 0.0 | - | 17 | ZAYIF |
| Ayı Bayrağı | 1h | 5 | 0.0 | - | 15 | ZAYIF |
| Ayı Bayrağı | 2h | 2 | 0.0 | - | 8 | ZAYIF |
| Ayı Bayrağı | 4h | 6 | 0.0 | - | 14 | ZAYIF |
| Ayı Flaması | 1d | 4 | 0.0 | - | 14 | ZAYIF |
| Ayı Flaması | 1h | 3 | 0.0 | - | 11 | ZAYIF |
| Ayı Flaması | 2h | 4 | 0.0 | - | 8 | ZAYIF |
| Ayı Flaması | 4h | 5 | 0.0 | - | 10 | ZAYIF |
| Boğa Bayrağı | 1d | 3 | 33.3 | 8 | 11 | ZAYIF |
| Boğa Bayrağı | 1h | 3 | 0.0 | - | 8 | ZAYIF |
| Boğa Bayrağı | 2h | 2 | 0.0 | - | 9 | ZAYIF |
| Boğa Bayrağı | 4h | 2 | 0.0 | - | 10 | ZAYIF |
| Boğa Flaması | 1h | 1 | 0.0 | - | 14 | ZAYIF |
| Boğa Flaması | 2h | 1 | 100.0 | 10 | - | ZAYIF |
| Boğa Flaması | 4h | 2 | 0.0 | - | 8 | ZAYIF |
| Simetrik Üçgen | 1d | 285 | 1.1 | 8 | 11 | YETERLI |
| Simetrik Üçgen | 1h | 1190 | 0.3 | 9 | 10 | YETERLI |
| Simetrik Üçgen | 2h | 850 | 0.4 | 9 | 10 | YETERLI |
| Simetrik Üçgen | 4h | 675 | 1.0 | 6 | 11 | YETERLI |
| Yükselen Kama | 1d | 288 | 0.3 | 8 | 11 | YETERLI |
| Yükselen Kama | 1h | 4100 | 0.0 | 2 | 9 | YETERLI |
| Yükselen Kama | 2h | 1825 | 0.1 | 4 | 10 | YETERLI |
| Yükselen Kama | 4h | 758 | 0.1 | 12 | 12 | YETERLI |
| Yükselen Üçgen | 1d | 334 | 0.9 | 8 | 12 | YETERLI |
| Yükselen Üçgen | 1h | 4625 | 0.1 | 16 | 10 | YETERLI |
| Yükselen Üçgen | 2h | 2084 | 0.3 | 9 | 11 | YETERLI |
| Yükselen Üçgen | 4h | 830 | 1.0 | 9 | 12 | YETERLI |

- **ANA SAYI**: havuz açık %0.5; son olayı terminal olmayan stable_id %4.8; meta.formasyon_sayisi=34455 ↔ frm=34455 tutarlı=EVET
- **KARAR**: en yüksek hücre açık %6.8 → payda düzeltmesi yeterli
- **Notlar**: Terminal set (§8-E11): FORMASYON_TAMAMLANDI, BASARISIZ_KIRILIM, FORMASYON_GECERSIZ, KIRILIM_TEYIT_ALAMADI

### S29 · Pivot ezilmesi → teyit sonrası getiri

- **VERİ**: mfe+mae dolu (teyitli): 29039; ezilen: 337

| ezildi | deneme_var | n | medyan MFE | medyan MAE | MAE/MFE% | güven |
| --- | --- | --- | --- | --- | --- | --- |
| False | True | 28702 | 1.06 | 0.99 | 92.6 | YETERLI |
| True | True | 337 | 1.10 | 0.93 | 84.2 | YETERLI |

tip×ezilme (MFE):
| pattern_type | n ezilen | MFE | n ezilmeyen | MFE |
| --- | --- | --- | --- | --- |
| Alçalan Kama | 37 | 1.65 | 5580 | 1.10 |
| Alçalan Üçgen | 145 | 1.23 | 8028 | 1.10 |
| Yükselen Kama | 53 | 0.76 | 6080 | 1.00 |
| Yükselen Üçgen | 90 | 0.97 | 6652 | 1.04 |

- **ANA SAYI**: ezilen MFE=1.10 vs değil=1.06 (Δ=0.04 ATR); MAE/MFE 84.2% vs 92.6% (Δ=-8.3pp)
- **KARAR**: yalnız gözlem

### S30 · 12 bar yeterli mi (MFE_uzun / MFE)

- **VERİ**: mfe + mfe_uzun dolu, mfe>0: 27827

| pattern_type | n | medyan oran | p90 | medyan MFE(12) | medyan MFE(40) | tepe sonra% (mfe_uzun>mfe) | güven |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Alçalan Kama | 5385 | 1.00 | 1.00 | 1.17 | 1.17 | 0.2 | YETERLI |
| Alçalan Üçgen | 7807 | 1.00 | 1.00 | 1.17 | 1.18 | 0.3 | YETERLI |
| Ayı Bayrağı | 11 | 1.00 | 1.00 | 1.28 | 1.28 | 0.0 | ZAYIF |
| Ayı Flaması | 13 | 1.00 | 1.00 | 1.17 | 1.17 | 0.0 | ZAYIF |
| Boğa Bayrağı | 7 | 1.00 | 1.00 | 2.12 | 2.12 | 0.0 | ZAYIF |
| Boğa Flaması | 4 | 1.00 | 1.00 | 1.20 | 1.20 | 0.0 | ZAYIF |
| Simetrik Üçgen | 2244 | 1.00 | 1.00 | 1.15 | 1.15 | 0.2 | YETERLI |
| Yükselen Kama | 5886 | 1.00 | 1.00 | 1.05 | 1.05 | 0.2 | YETERLI |
| Yükselen Üçgen | 6470 | 1.00 | 1.00 | 1.09 | 1.09 | 0.2 | YETERLI |

- **ANA SAYI**: havuz medyan oran=1.00; tepe sonrada oluşan pay %0.2
- **KARAR**: 12 bar yeterli (eşik: >=1.5 uzun, <1.2 kısa)
- **Notlar**: break_confirmation_strength destek medyanıdır (§8-E12); gruplama değişkeni değil.; Eşitliğin kaynağı: formasyon.py'de `sonra` etkin ömürle (anti-dairesellik kesiği, _TERMINAL) sınırlıdır; teyitten sonra terminal barına kadar yalnızca birkaç bar kalır, 40-bar pencere ancak uzun açık dönemlerde açılır — bu yüzden oran ~1.0.

## §5 KESİT / VERİ KAPISI

### S31 · Semboller arası yayılım (p10–p90)

- **VERİ**: zone ölçülebilir sembol-grupları (n>=30 semboller); MS: 2 scope

| tf | family | n sembol | p10 | medyan | p90 | p90−p10 |
| --- | --- | --- | --- | --- | --- | --- |
| 1d | FVG | 145 | 57.7 | 65.1 | 73.8 | +16.1 |
| 1d | OB | 177 | 57.6 | 65.2 | 73.3 | +15.7 |
| 1h | OB | 175 | 62.1 | 66.2 | 70.3 | +8.2 |
| 2h | FVG | 175 | 61.5 | 66.5 | 71.9 | +10.4 |
| 2h | OB | 175 | 61.1 | 65.8 | 70.5 | +9.3 |
| 4h | FVG | 177 | 61.7 | 66.2 | 72.6 | +10.9 |
| 4h | OB | 175 | 60.0 | 65.4 | 70.8 | +10.8 |

MS:
| scope | n sembol | p10 | medyan | p90 | p90−p10 |
| --- | --- | --- | --- | --- | --- |
| EXTERNAL | 177 | 61.5 | 65.7 | 70.2 | +8.7 |
| INTERNAL | 177 | 62.1 | 65.6 | 69.4 | +7.3 |

- **ANA SAYI**: en geniş p90−p10=16.1pp; en düşük 5: GSRAY(49%), ASELS(59%), SISE(59%), SASA(59%), XU100(59%) · en yüksek 5: ANSGR(72%), OFSYM(72%), AVPGY(73%), AKFGY(73%), IHEVA(73%)
- **KARAR**: global oran + aralık notu
- **Notlar**: n<30 semboller dışlanmadı, yalnızca güven etiketi alır (C4).

### S32 · Kirli bar penceresi (K5, 12 bar sonrası)

- **VERİ**: penceresi hesaplanan epizod: 243256; bayraklı epizod: 90063 (37.02%)

| timeframe   | family   |     n |   split_pct |   sifir_pct |   nan_pct |   kirli_pct |
|:------------|:---------|------:|------------:|------------:|----------:|------------:|
| 1d          | FVG      |  6313 |       0.76  |       0.665 |         0 |       1.41  |
| 1d          | OB       | 18689 |       0.567 |       0.54  |         0 |       1.108 |
| 1h          | OB       | 91725 |       0.148 |      94.529 |         0 |      94.566 |
| 2h          | FVG      | 21986 |       0.305 |       2.074 |         0 |       2.379 |
| 2h          | OB       | 55180 |       0.294 |       2.329 |         0 |       2.622 |
| 4h          | FVG      | 15043 |       0.578 |       1.595 |         0 |       2.167 |
| 4h          | OB       | 34320 |       0.487 |       1.643 |         0 |       2.127 |

bar-seviyesi split_adayi: 1d: 0.051%, 1h: 0.016%, 2h: 0.036%, 4h: 0.059%

sıfır-hacimli bar saatleri: 1d: 00:00=172, 07:00=6, 08:00=1; 1h: 09:00=59362, 17:00=850, 16:00=769; 2h: 09:00=1763, 17:00=848, 11:00=730; 4h: 17:00=848, 09:00=730, 13:00=729

- **ANA SAYI**: en kötü hücre kirli pencere %94.57
- **KARAR**: kural + karne ayrımı
- **Notlar**: K5 bayrakları JSONL'de yok → arşiv çerçevelerinden üretildi (§8-E13).; 1h sıfır-hacim yığını 09:30 açılış öncesi bar kaynaklıdır (yapısal, fiyat boşluğu değil); split payları çok düşük. FAYDA kuralı split için geçerli, sıfır-hacim ayrı hücrede raporlanır.

## §6 KARAR ÖZETİ (canlı bileşen eşlemesiyle)

### CANLIYA YAZILIR (kart/rozet/kuyruk/filtre) — 19 madde

- **S02**: FVG: YAZILIR (fark=-13.9pp, azalis, n=278/40349, sansur<=20%); OB: RED (fark=-3.8pp, |fark|<5)
- **S03**: 0-0.5 ATR'de OLCULEMEDI=49.6% → kural; >=2 ATR'de 5.1% (karşılaştırma)
- **S04**: FVG: YAZILIR (fark=+21.0pp, artis, n=30995/844, sansur<=20%); OB: YAZILIR (fark=+15.3pp, artis, n=107978/7511, sansur<=20%)
- **S05**: STOP KURALI (havuz) — hücreler tabloda
- **S06**: TAVSİYE: 10 bar (eşik: Δmedyan>=0.15 ATR ve Δpp>=3)
- **S07**: kural zorunlu (havuz 65.3% vs eşik 10/5/5)
- **S08**: FVG: HIT_ONLY_AFTER=61.7% → kural+karne; OB: HIT_ONLY_AFTER=30.9% → kural+karne
- **S09**: güven etiketi düşürmesi zorunlu (>=5 pp)
- **S10**: FVG: RED (fark=+3.6pp, |fark|<5); OB: YAZILIR (fark=+34.3pp, artis, n=6383/15737, sansur<=20%)
- **S11**: FVG/FROM_ABOVE: YAZILIR (fark=+15.6pp, artis, n=8994/7972, sansur<=20%); FVG/FROM_BELOW: YAZILIR (fark=+18.5pp, artis, n=14791/6154, sansur<=20%); FVG/ON_ZONE_BOUNDARY: YAZILIR (fark=+25.3pp, artis, n=1367/645, sansur<=20%); OB/FROM_ABOVE: YAZILIR (fark=+18.8p
- **S15**: FVG/no1: RED (fark=+1.2pp, |fark|<5); FVG/no2: KARAR YOK (guven: KISMI; n1=346, n2=17); OB/no1: YAZILIR (fark=+32.7pp, artis, n=81647/5919, sansur<=20%); OB/no2: YAZILIR (fark=+34.9pp, artis, n=29283/1965, sansur<=20%); OB/no3+: YAZILIR (fark=+40.3pp, artis, n
- **S16**: EXTERNAL/HIGH:YAZILIR; EXTERNAL/LOW:YALNIZ KART METNI; INTERNAL/HIGH:YAZILIR; INTERNAL/LOW:YAZILIR
- **S17**: INTERNAL/HIGH:YAZILIR; INTERNAL/LOW:YAZILIR
- **S18**: EXTERNAL:YAZILIR; INTERNAL:YAZILIR
- **S19**: DEVREDILDI kart cümlesi yazılır
- **S21**: EXTERNAL:YALNIZ KART METNI; INTERNAL:YAZILIR
- **S25**: EXTERNAL BOS: SUPERSEDED 93.2% → bastırma kuralı | INTERNAL BOS: SUPERSEDED 96.4% → bastırma kuralı
- **S26**: EXTERNAL: fark -61.0pp → YAZILIR; INTERNAL: fark -61.1pp → YAZILIR
- **S32**: kural + karne ayrımı

### YALNIZ KART METNİ (5–12 pp / dipnot) — 1 madde

- **S13**: OB: en_iyi−en_kötü +5.5pp → kart metni

### RED / hipotez çöktü (yeni kural açılmaz) — 7 madde

- **S01**: FVG: RED (fark=-3.9pp, |fark|<5); OB: RED (fark=-2.7pp, |fark|<5)
- **S12**: RED / kart standardı: rvol tek ölçüt (çelişki yapısal olarak yok)
- **S20**: HIGH: INTERNAL sığ kırılım 4.7% → kural-red | LOW: INTERNAL sığ kırılım 10.2% → kural-red
- **S22**: EXTERNAL/EVENT_BOS:RED; INTERNAL/EVENT_BOS:RED
- **S23**: EXTERNAL/EVENT_FALSE_BREAK: Δmedyan=0.21 ATR, ΔCALISTI=+2.8pp → kart dipnotu | INTERNAL/EVENT_FALSE_BREAK: Δmedyan=0.34 ATR, ΔCALISTI=+2.8pp → RED: hipotez ters (geç onaylılar daha iyi; gecikme cezası kurulmaz)
- **S24**: EXTERNAL EVENT_SWEEP vs BOS: +0.8pp → kontra reddedilir | EXTERNAL EVENT_FALSE_BREAK vs BOS: -0.6pp → kontra reddedilir | EXTERNAL EVENT_CHOCH vs BOS: -0.1pp → kontra reddedilir | INTERNAL EVENT_SWEEP vs BOS: +1.4pp → kontra reddedilir | INTERNAL EVENT_FALSE_B
- **S27**: RED (yapısal): '6+ yayınlanmaz' kuralı KURULMAZ — çırpınma kontrastı 3-5 vs ≥6 = +4.1pp (<5); ≤2 tabanı TAMAMLANDI üretemez (TAMAMLANDI %0.0, BASARISIZ_KIRILIM %41.9)

### KARAR YOK / HATA (n<30, sansür>20%, o hücrede karar yok) — 1 madde

- **S14**: S10–S12 için kapalı hücreler var (max 25.3%) → o hücrelerde karar yok

### Gözlem / yapısal bulgu (kurala dönüşmez) — 4 madde

- **S28**: en yüksek hücre açık %6.8 → payda düzeltmesi yeterli
- **S29**: yalnız gözlem
- **S30**: 12 bar yeterli (eşik: >=1.5 uzun, <1.2 kısa)
- **S31**: global oran + aralık notu

> Kart/rozet/filtre yalnız 'CANLIYA YAZILIR' maddelerine yazılır (§0 eşik sözleşmesi).
> RED maddeleri mevcut kararlardan da çıkarılmaz; yalnız yeni kural AÇILMAZ.
