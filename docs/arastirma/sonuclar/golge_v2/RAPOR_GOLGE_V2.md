# Gölge v2 Domain-Denetimli Plan & Kalite Merdiveni Raporu

- **Evren:** 176 sembol (`BRENT` hariç tüm BIST arşivi)
- **Toplam Ham Olay:** `46773` (sansürsüz `46500`; karantina sonrası ölçüme giren `45803`; bunların birincil `KIRILIM_ADAYI`: `16729`, çekirdek/A+: `4116`)
- **Domain Hatası Nedeniyle Ölçüme Alınmayan Seri (fail-closed):** `0`
- **Veri Karantinasına Alınan Olay:** `697` (fiyat kopukluğu; tablolar temiz kümeden, bkz. §7)
- **Kabul Kapısı Kararı:** **`GECTI_4H_1D_CEKIRDEK`** — zaman kümelerinde: **`KIRILGAN`**, keşif dönemi teyidi: **`YOK`** (bkz. §8)
- **Kod Özeti:** `df187d7e9732`

## 1. Domain Merdiveni (`4h + 1d`, `2.0 ATR` Hedef, `Net15` = `30 bps` Gidiş-Dönüş Masraf Düşülmüş R)

| Dönem | Katman | N | Pay | Net15 Ort R | Pozitif % | Küme %95 GA |
|---|---|---:|---:|---:|---:|---|
| tumu | D0_Tum_Olaylar | 13477 | 100.0% | -0.0605 | 41.7% | [-0.0865, -0.0331] |
| tumu | D1_Birincil_KirilimAdayi | 4233 | 31.4% | 0.01 | 43.0% | [-0.0333, 0.0535] |
| tumu | D2_TersBOS_Yok | 4179 | 31.0% | 0.0081 | 42.9% | [-0.0343, 0.0514] |
| tumu | D3_Blok_Temiz | 3927 | 29.1% | 0.0117 | 43.0% | [-0.0325, 0.0539] |
| tumu | D4_VP_Kalite | 2773 | 20.6% | 0.0208 | 44.5% | [-0.028, 0.0731] |
| tumu | D5_MS_Yapi_Uyumlu | 1390 | 10.3% | 0.033 | 45.5% | [-0.0406, 0.0975] |
| tumu | D6_A_Cekirdek_Veya_Arti | 1124 | 8.3% | 0.0611 | 48.5% | [-0.0202, 0.1297] |
| tumu | D7_A_Arti_UyumluBOS | 637 | 4.7% | 0.1147 | 50.7% | [0.0102, 0.2161] |
| tumu | Ikincil_Retest | 1818 | 13.5% | -0.1421 | 35.1% | [-0.2063, -0.0801] |
| tumu | Ikincil_GecTeyitli | 1007 | 7.5% | -0.1019 | 39.8% | [-0.1927, -0.0083] |
| tumu | Ikincil_Stabil_Tumu | 5403 | 40.1% | -0.0782 | 42.9% | [-0.1171, -0.0394] |
| tumu | Ikincil_Stabil_Emilim | 404 | 3.0% | -0.0192 | 44.1% | [-0.1582, 0.1034] |
| kesif | D0_Tum_Olaylar | 8780 | 100.0% | -0.0561 | 42.0% | [-0.0892, -0.0231] |
| kesif | D1_Birincil_KirilimAdayi | 2723 | 31.0% | -0.0096 | 42.2% | [-0.0649, 0.0441] |
| kesif | D2_TersBOS_Yok | 2686 | 30.6% | -0.0135 | 42.1% | [-0.0695, 0.0414] |
| kesif | D3_Blok_Temiz | 2529 | 28.8% | -0.0154 | 42.0% | [-0.0702, 0.0386] |
| kesif | D4_VP_Kalite | 1846 | 21.0% | 0.0042 | 43.6% | [-0.0521, 0.0634] |
| kesif | D5_MS_Yapi_Uyumlu | 920 | 10.5% | 0.0096 | 44.2% | [-0.0694, 0.0843] |
| kesif | D6_A_Cekirdek_Veya_Arti | 738 | 8.4% | 0.021 | 47.0% | [-0.0726, 0.1078] |
| kesif | D7_A_Arti_UyumluBOS | 414 | 4.7% | 0.0543 | 47.8% | [-0.0605, 0.1685] |
| kesif | Ikincil_Retest | 1170 | 13.3% | -0.1338 | 35.6% | [-0.2113, -0.0556] |
| kesif | Ikincil_GecTeyitli | 636 | 7.2% | -0.0284 | 42.8% | [-0.1299, 0.0803] |
| kesif | Ikincil_Stabil_Tumu | 3627 | 41.3% | -0.0767 | 43.1% | [-0.123, -0.0299] |
| kesif | Ikincil_Stabil_Emilim | 247 | 2.8% | -0.0681 | 42.5% | [-0.2356, 0.0982] |
| dogrulama | D0_Tum_Olaylar | 4697 | 100.0% | -0.0687 | 41.2% | [-0.1105, -0.0225] |
| dogrulama | D1_Birincil_KirilimAdayi | 1510 | 32.1% | 0.0454 | 44.2% | [-0.0293, 0.1236] |
| dogrulama | D2_TersBOS_Yok | 1493 | 31.8% | 0.047 | 44.3% | [-0.029, 0.1257] |
| dogrulama | D3_Blok_Temiz | 1398 | 29.8% | 0.0607 | 44.7% | [-0.0179, 0.1438] |
| dogrulama | D4_VP_Kalite | 927 | 19.7% | 0.0537 | 46.4% | [-0.0405, 0.1487] |
| dogrulama | D5_MS_Yapi_Uyumlu | 470 | 10.0% | 0.0788 | 47.9% | [-0.055, 0.2143] |
| dogrulama | D6_A_Cekirdek_Veya_Arti | 386 | 8.2% | 0.1378 | 51.3% | [0.0126, 0.2745] |
| dogrulama | D7_A_Arti_UyumluBOS | 223 | 4.8% | 0.2269 | 56.0% | [0.0547, 0.3943] |
| dogrulama | Ikincil_Retest | 648 | 13.8% | -0.1572 | 34.1% | [-0.2713, -0.0559] |
| dogrulama | Ikincil_GecTeyitli | 371 | 7.9% | -0.2279 | 34.8% | [-0.3521, -0.0867] |
| dogrulama | Ikincil_Stabil_Tumu | 1776 | 37.8% | -0.0814 | 42.5% | [-0.1479, -0.021] |
| dogrulama | Ikincil_Stabil_Emilim | 157 | 3.3% | 0.0577 | 46.5% | [-0.1458, 0.2543] |

## 2. Kalite Katmanı × Zaman Dilimi (Tüm TF'ler, `Net15` R)

| Dönem | Katman | TF | N | Net15 Ort R | Pozitif % | Küme %95 GA |
|---|---|---|---:|---:|---:|---|
| dogrulama | A_ARTI | 1d | 60 | 0.27 | 55.0% | [-0.0878, 0.6145] |
| dogrulama | A_ARTI | 1h | 369 | -0.3777 | 36.6% | [-0.5501, -0.1954] |
| dogrulama | A_ARTI | 2h | 218 | -0.0172 | 45.9% | [-0.144, 0.1425] |
| dogrulama | A_ARTI | 4h | 163 | 0.2111 | 56.4% | [0.0257, 0.4025] |
| dogrulama | A_CEKIRDEK | 1d | 39 | -0.0042 | 43.6% | [-0.3511, 0.3143] |
| dogrulama | A_CEKIRDEK | 1h | 292 | -0.2889 | 38.7% | [-0.4221, -0.1487] |
| dogrulama | A_CEKIRDEK | 2h | 202 | -0.1516 | 43.6% | [-0.3295, 0.0087] |
| dogrulama | A_CEKIRDEK | 4h | 124 | 0.0222 | 45.2% | [-0.1892, 0.2244] |
| dogrulama | B_ADAY | 1d | 332 | 0.0121 | 40.4% | [-0.1339, 0.1589] |
| dogrulama | B_ADAY | 1h | 2388 | -0.2166 | 38.6% | [-0.2751, -0.1521] |
| dogrulama | B_ADAY | 2h | 1308 | -0.039 | 42.0% | [-0.1134, 0.0347] |
| dogrulama | B_ADAY | 4h | 792 | 0.0143 | 42.4% | [-0.0817, 0.0986] |
| dogrulama | C_IKINCIL | 1d | 1216 | -0.0773 | 40.6% | [-0.1439, -0.0113] |
| dogrulama | C_IKINCIL | 1h | 4507 | -0.2325 | 38.7% | [-0.2718, -0.1864] |
| dogrulama | C_IKINCIL | 2h | 2771 | -0.1681 | 39.3% | [-0.2174, -0.1093] |
| dogrulama | C_IKINCIL | 4h | 1971 | -0.1507 | 39.2% | [-0.2079, -0.0929] |
| kesif | A_ARTI | 1d | 143 | 0.028 | 47.5% | [-0.1855, 0.2516] |
| kesif | A_ARTI | 1h | 691 | -0.2488 | 40.5% | [-0.351, -0.1519] |
| kesif | A_ARTI | 2h | 490 | -0.1161 | 42.4% | [-0.2241, -0.0124] |
| kesif | A_ARTI | 4h | 271 | 0.0682 | 48.0% | [-0.0706, 0.2254] |
| kesif | A_CEKIRDEK | 1d | 106 | 0.0377 | 47.2% | [-0.1825, 0.2588] |
| kesif | A_CEKIRDEK | 1h | 443 | -0.085 | 46.1% | [-0.2075, 0.0421] |
| kesif | A_CEKIRDEK | 2h | 287 | -0.0173 | 48.1% | [-0.1544, 0.1178] |
| kesif | A_CEKIRDEK | 4h | 218 | -0.0504 | 45.4% | [-0.1966, 0.0918] |
| kesif | B_ADAY | 1d | 728 | 0.056 | 40.5% | [-0.0532, 0.1676] |
| kesif | B_ADAY | 1h | 3844 | -0.2112 | 39.5% | [-0.256, -0.1646] |
| kesif | B_ADAY | 2h | 1964 | -0.1042 | 40.4% | [-0.1647, -0.0317] |
| kesif | B_ADAY | 4h | 1257 | -0.0657 | 40.4% | [-0.1401, 0.0041] |
| kesif | C_IKINCIL | 1d | 2958 | -0.0634 | 41.9% | [-0.1032, -0.0195] |
| kesif | C_IKINCIL | 1h | 7799 | -0.2882 | 37.4% | [-0.3227, -0.2554] |
| kesif | C_IKINCIL | 2h | 4753 | -0.169 | 39.4% | [-0.2059, -0.1252] |
| kesif | C_IKINCIL | 4h | 3099 | -0.09 | 41.8% | [-0.1447, -0.0378] |

## 3. Birincil vs İkincil Alt Kol Karşılaştırması (`2.0 ATR` Brüt R)

| Dönem | Sınıf | Alt Kol | Yön | N | Brüt Ort R | Pozitif % | Küme %95 GA |
|---|---|---|---|---:|---:|---:|---|
| dogrulama | BIRINCIL | B_kirilim | long | 3128 | -0.0282 | 38.1% | [-0.0859, 0.0243] |
| dogrulama | BIRINCIL | B_kirilim | short | 3159 | 0.2158 | 46.2% | [0.1481, 0.2838] |
| dogrulama | IKINCIL | A_momentum | long | 722 | -0.0969 | 40.7% | [-0.1802, -0.0199] |
| dogrulama | IKINCIL | A_momentum | short | 811 | -0.0869 | 46.1% | [-0.1848, 0.0197] |
| dogrulama | IKINCIL | A_multi_bar | long | 154 | -0.139 | 36.4% | [-0.3507, 0.0534] |
| dogrulama | IKINCIL | A_return | short | 1343 | 0.0449 | 39.7% | [-0.0453, 0.147] |
| dogrulama | IKINCIL | A_sweep | long | 584 | -0.0564 | 37.8% | [-0.167, 0.0779] |
| dogrulama | IKINCIL | A_sweep | short | 693 | 0.0492 | 44.4% | [-0.0464, 0.1473] |
| dogrulama | IKINCIL | B_kirilim | long | 908 | -0.0438 | 37.7% | [-0.1373, 0.0414] |
| dogrulama | IKINCIL | B_kirilim | short | 633 | 0.1307 | 46.8% | [0.0122, 0.2491] |
| dogrulama | IKINCIL | B_retest | long | 1348 | 0.0677 | 35.3% | [-0.0092, 0.1444] |
| dogrulama | IKINCIL | B_retest | short | 1488 | 0.0557 | 40.4% | [-0.0311, 0.1439] |
| dogrulama | IKINCIL | B_sinir | long | 768 | 0.0319 | 41.8% | [-0.0674, 0.1221] |
| dogrulama | IKINCIL | B_sinir | short | 1013 | -0.0132 | 42.1% | [-0.1027, 0.0784] |
| kesif | BIRINCIL | B_kirilim | long | 5213 | 0.169 | 45.2% | [0.1259, 0.2072] |
| kesif | BIRINCIL | B_kirilim | short | 5229 | 0.0241 | 39.2% | [-0.0239, 0.0676] |
| kesif | IKINCIL | A_momentum | long | 1159 | 0.119 | 53.1% | [0.047, 0.1911] |
| kesif | IKINCIL | A_momentum | short | 1608 | -0.0467 | 46.8% | [-0.1118, 0.0247] |
| kesif | IKINCIL | A_multi_bar | long | 299 | -0.0127 | 41.8% | [-0.1501, 0.1205] |
| kesif | IKINCIL | A_return | short | 2927 | -0.0438 | 35.2% | [-0.118, 0.0362] |
| kesif | IKINCIL | A_sweep | long | 869 | -0.0193 | 40.3% | [-0.1246, 0.0755] |
| kesif | IKINCIL | A_sweep | short | 1367 | -0.0194 | 41.8% | [-0.0995, 0.0608] |
| kesif | IKINCIL | B_kirilim | long | 1399 | 0.086 | 42.7% | [0.0173, 0.1644] |
| kesif | IKINCIL | B_kirilim | short | 1285 | 0.0132 | 41.9% | [-0.0558, 0.0801] |
| kesif | IKINCIL | B_retest | long | 2159 | 0.111 | 39.0% | [0.046, 0.1785] |
| kesif | IKINCIL | B_retest | short | 2642 | -0.0757 | 34.5% | [-0.1365, -0.0133] |
| kesif | IKINCIL | B_sinir | long | 1399 | 0.106 | 44.5% | [0.0258, 0.201] |
| kesif | IKINCIL | B_sinir | short | 1496 | 0.0294 | 42.8% | [-0.0415, 0.099] |

## 4. Kalite Katmanı × Yön (`4h + 1d`, `Net15` R)

| Dönem | Katman | Yön | N | Net15 Ort R | Pozitif % | Küme %95 GA |
|---|---|---|---:|---:|---:|---|
| dogrulama | A_ARTI | long | 99 | 0.1436 | 52.5% | [-0.1206, 0.3877] |
| dogrulama | A_ARTI | short | 124 | 0.2935 | 58.9% | [0.0503, 0.5388] |
| dogrulama | A_CEKIRDEK | long | 91 | -0.103 | 41.8% | [-0.3214, 0.1022] |
| dogrulama | A_CEKIRDEK | short | 72 | 0.1662 | 48.6% | [-0.1177, 0.4511] |
| dogrulama | B_ADAY | long | 617 | -0.1998 | 34.5% | [-0.3091, -0.0802] |
| dogrulama | B_ADAY | short | 507 | 0.2733 | 50.7% | [0.1567, 0.4056] |
| dogrulama | C_IKINCIL | long | 1299 | -0.1708 | 36.5% | [-0.2418, -0.1012] |
| dogrulama | C_IKINCIL | short | 1888 | -0.0896 | 41.9% | [-0.1641, -0.0218] |
| kesif | A_ARTI | long | 248 | 0.1418 | 51.6% | [-0.015, 0.3086] |
| kesif | A_ARTI | short | 166 | -0.0764 | 42.2% | [-0.2653, 0.121] |
| kesif | A_CEKIRDEK | long | 203 | 0.0534 | 48.3% | [-0.0949, 0.2272] |
| kesif | A_CEKIRDEK | short | 121 | -0.1474 | 42.1% | [-0.3342, 0.0555] |
| kesif | B_ADAY | long | 920 | 0.1033 | 45.4% | [0.0021, 0.1924] |
| kesif | B_ADAY | short | 1065 | -0.1284 | 36.1% | [-0.2149, -0.0459] |
| kesif | C_IKINCIL | long | 2248 | 0.0486 | 46.0% | [-0.0068, 0.1041] |
| kesif | C_IKINCIL | short | 3809 | -0.1511 | 39.4% | [-0.2068, -0.0967] |

## 5. Mod 0 vs Mod 1 vs Mod 2 (Birincil + Tüm Domain Kapıları Açık, `2.0 ATR` Brüt R)

- **Mod 0 (Bloksuz baz):** N=9416, Ort R=0.0918 `[0.0604, 0.1198]`
- **Mod 1 (Blok kenarına stop):** N=9416, Ort R=0.074 `[0.0458, 0.0979]` (değişen N=3269)
- **Mod 2 (Min risk >=0.35 ATR & >=0.50 ATR blok):** Uygun=371, Dolan=148 (`39.9%`), Ort R=-0.2516 vs Mod 0 eş küme=-0.0324
  - Emir beklerken ters yapı kırılımıyla iptal edilen limit: 0. Mod 2'de R paydası planlanan risktir (`limit - stop`); boşlukla daha iyi fiyattan dolum R'yi şişirmez.

## 6. Duyarlılık (`tampon` & `H`, Birincil + Tüm Domain Kapıları, `2.0 ATR` Brüt R)

| Tampon | H | Dönem | N | Ort R | Küme %95 GA |
|---:|---:|---|---:|---:|---|
| 0.5 | 10 | kesif | 6079 | 0.1058 | [0.0681, 0.1375] |
| 0.5 | 10 | dogrulama | 3337 | 0.0662 | [0.0182, 0.111] |
| 0.25 | 10 | kesif | 6079 | 0.1159 | [0.0748, 0.1572] |
| 0.25 | 10 | dogrulama | 3337 | 0.0908 | [0.0314, 0.152] |
| 0.5 | 16 | kesif | 6075 | 0.1104 | [0.0706, 0.1438] |
| 0.5 | 16 | dogrulama | 3307 | 0.0491 | [-0.0029, 0.0973] |
| 1.0 | 10 | kesif | 6079 | 0.077 | [0.0534, 0.1022] |
| 1.0 | 10 | dogrulama | 3337 | 0.0644 | [0.0258, 0.0978] |

## 7. Veri Karantinası (Düzeltilmemiş Kurumsal İşlem / Durdurma Kopuklukları)

Arşiv fiyatları düzeltilmemiştir. Açılışı önceki kapanıştan `%11.5`'ten fazla kopan barlar (BIST günlük fiyat marjının üstü) gerçek bir fiyat hareketi değil bölünme / bedelli / uzun durdurma izidir. Böyle bir barı işlem penceresinde ya da son `60` barlık bağlamında taşıyan olaylar sonuca bakılmadan karantinaya alınır; yukarıdaki bütün tablolar temiz kümeden üretilmiştir.

- Karantinaya alınan olay: `697` / `46500` (`27` sembol); TF dağılımı: `{'1d': 97, '1h': 261, '2h': 205, '4h': 134}`; neden: `{'KOPUKLUK_GERI': 626, 'KOPUKLUK_GERI+ILERI': 18, 'KOPUKLUK_ILERI': 53}`
- Karantinadaki olayların toplam brüt sonucu (2.0 ATR): `-70.23 R`

| Dönem | Katman | Ham N | Ham Net15 R | Temiz N | Temiz Net15 R |
|---|---|---:|---:|---:|---:|
| tumu | D0_Tum_Olaylar | 13708 | -0.0596 | 13477 | -0.0605 |
| tumu | D1_Birincil_KirilimAdayi | 4289 | 0.009 | 4233 | 0.01 |
| tumu | D6_A_Cekirdek_Veya_Arti | 1140 | 0.0693 | 1124 | 0.0611 |
| tumu | D7_A_Arti_UyumluBOS | 648 | 0.1234 | 637 | 0.1147 |
| kesif | D0_Tum_Olaylar | 8981 | -0.0546 | 8780 | -0.0561 |
| kesif | D1_Birincil_KirilimAdayi | 2771 | -0.0104 | 2723 | -0.0096 |
| kesif | D6_A_Cekirdek_Veya_Arti | 750 | 0.0295 | 738 | 0.021 |
| kesif | D7_A_Arti_UyumluBOS | 422 | 0.0632 | 414 | 0.0543 |
| dogrulama | D0_Tum_Olaylar | 4727 | -0.0692 | 4697 | -0.0687 |
| dogrulama | D1_Birincil_KirilimAdayi | 1518 | 0.0446 | 1510 | 0.0454 |
| dogrulama | D6_A_Cekirdek_Veya_Arti | 390 | 0.146 | 386 | 0.1378 |
| dogrulama | D7_A_Arti_UyumluBOS | 226 | 0.2358 | 223 | 0.2269 |

En uç karantina örnekleri (ölçüme alınsaydı):

| Olay | Kapanış | Katman | Karantina | Çıkış | Brüt R |
|---|---|---|---|---|---:|
| `FENER:1h:1484:B_retest:long` | 2026-01-02 | C_IKINCIL | KOPUKLUK_GERI+ILERI | STOP_GAP | -72.0687 |
| `FENER:1h:308:B_kirilim:long` | 2025-06-27 | B_ADAY | KOPUKLUK_GERI+ILERI | STOP_GAP | -37.8573 |
| `CVKMD:2h:1533:B_kirilim:long` | 2026-08-04 | B_ADAY | KOPUKLUK_GERI+ILERI | STOP_GAP | -16.1114 |
| `FENER:1h:539:B_kirilim:long` | 2025-08-05 | B_ADAY | KOPUKLUK_GERI | STOP_GAP | -11.3193 |
| `GSRAY:1d:170:B_kirilim:long` | 2025-06-27 | B_ADAY | KOPUKLUK_ILERI | STOP_GAP | -5.3749 |
| `FENER:2h:350:B_kirilim:short` | 2025-08-19 | B_ADAY | KOPUKLUK_GERI | STOP_GAP | -5.0777 |
| `KONTR:1d:275:B_kirilim:long` | 2025-11-25 | C_IKINCIL | KOPUKLUK_ILERI | STOP_GAP | -3.9903 |
| `BRKVY:1h:488:B_retest:long` | 2025-07-28 | C_IKINCIL | KOPUKLUK_GERI | HEDEF | 3.7554 |

### 7b. Market Structure Bayatlığı (etiket; ölçümden çıkarmaz)

Market Structure motoru bir korunan seviyeyi geçerli sayarken fiyat o seviyenin `1` ATR'den fazla ötesinde kapanmışsa motorun dış yapı durumu fiyatla çelişir; ardışık taban/tavan barlarında ya da kopukluk sonrasında swing oluşmayınca görülür ve yüzlerce bar sürebilir. O barda `ms_yapi_uyumlu` güvenilmezdir. Temiz kümede böyle `780` olay var (`46` sembol). Aşağıdaki tablo kalite katmanlarının bu olaylar çıkarıldığında değişip değişmediğini gösterir.

| Katman | Dönem | N | Bayat N | Net15 Ort R | GA alt | Bayatsız Ort R | Bayatsız GA alt |
|---|---|---:|---:|---:|---:|---:|---:|
| D1_Birincil_KirilimAdayi | tumu | 4233 | 58 | 0.01 | -0.0333 | 0.0073 | -0.0366 |
| D1_Birincil_KirilimAdayi | kesif | 2723 | 32 | -0.0096 | -0.0649 | -0.0129 | -0.0691 |
| D1_Birincil_KirilimAdayi | dogrulama | 1510 | 26 | 0.0454 | -0.0293 | 0.044 | -0.0255 |
| D6_A_Cekirdek_Veya_Arti | tumu | 1124 | 13 | 0.0611 | -0.0202 | 0.0618 | -0.0192 |
| D6_A_Cekirdek_Veya_Arti | kesif | 738 | 6 | 0.021 | -0.0726 | 0.0206 | -0.0722 |
| D6_A_Cekirdek_Veya_Arti | dogrulama | 386 | 7 | 0.1378 | 0.0126 | 0.1413 | 0.0116 |
| D7_A_Arti_UyumluBOS | tumu | 637 | 0 | 0.1147 | 0.0102 | 0.1147 | 0.0102 |
| D7_A_Arti_UyumluBOS | kesif | 414 | 0 | 0.0543 | -0.0605 | 0.0543 | -0.0605 |
| D7_A_Arti_UyumluBOS | dogrulama | 223 | 0 | 0.2269 | 0.0547 | 0.2269 | 0.0547 |

## 8. Kabul Kararının Küme Tanımına Dayanıklılığı (`4h + 1d`, `Net15` R)

Kabul kapısı yalnız doğrulama döneminin **sembol kümeli** alt sınırına bakar. Aynı gün birlikte hareket eden hisseler bağımsız değildir; bu yüzden aynı ortalama gün, hafta ve ay kümeleriyle de sınanır. Ay kümesinde küme sayısı azdır, aralık gösterge niteliğindedir.

| Katman | Dönem | N | Ort R | Sembol GA | Gün GA | Hafta GA | Ay GA | Hepsinde > 0 |
|---|---|---:|---:|---|---|---|---|---|
| D6_A_Cekirdek_Veya_Arti | tumu | 1124 | 0.0611 | [-0.0202, 0.1327] (k=176) | [-0.0305, 0.1591] (k=353) | [-0.0352, 0.1535] (k=92) | [-0.0463, 0.1563] (k=23) | HAYIR |
| D6_A_Cekirdek_Veya_Arti | kesif | 738 | 0.021 | [-0.0688, 0.1054] (k=171) | [-0.0896, 0.1415] (k=239) | [-0.0923, 0.1363] (k=64) | [-0.1109, 0.1409] (k=16) | HAYIR |
| D6_A_Cekirdek_Veya_Arti | dogrulama | 386 | 0.1378 | [0.0126, 0.2709] (k=155) | [-0.0211, 0.2836] (k=114) | [-0.0507, 0.3131] (k=29) | [-0.0257, 0.2446] (k=7) | HAYIR |
| D7_A_Arti_UyumluBOS | tumu | 637 | 0.1147 | [0.0102, 0.2183] (k=163) | [-0.0023, 0.2306] (k=287) | [-0.0011, 0.2308] (k=90) | [0.0121, 0.2013] (k=23) | HAYIR |
| D7_A_Arti_UyumluBOS | kesif | 414 | 0.0543 | [-0.0616, 0.169] (k=149) | [-0.0937, 0.2045] (k=191) | [-0.0884, 0.2065] (k=62) | [-0.104, 0.1892] (k=16) | HAYIR |
| D7_A_Arti_UyumluBOS | dogrulama | 223 | 0.2269 | [0.056, 0.3943] (k=124) | [0.0427, 0.4111] (k=96) | [0.0652, 0.3724] (k=29) | [0.1378, 0.3192] (k=7) | evet |

## 9. İşlem-İçi Süreç Görünürlüğü (`D7`, `4h + 1d`, Birincil Yarış)

Yarış artık dolumdan çıkışa kadar her kapanışta domainleri yeniden okur ve kaydeder (`surec_*` kolonları). Bu bölüm **betimleyicidir**: işlem açıkken ne görüldüğünü söyler, bir çıkış kuralının değerini ölçmez. Etiket ile nihai sonuç arasındaki ilişki sonuç-koşulludur; kural değeri `surec_olcum/RAPOR.md` içindeki eşleşmiş replay ile ölçülür.

- İşlem: `637`; işlem başına ortalama gözlenen kapanış: `4.04`; hiç kapanış görmeden (ilk barda bar içi) kapanan: `87` (`13.7%`)
- Stop olan `280` işlemin stoptan önce `+0.5R` gören payı: `39.3%`, `+1R` gören payı: `16.1%`

| Çıkış | N | Net15 Ort R | Ort Gözlem | Çıkışa Kadar MFE (R) | Çıkışa Kadar MAE (R) |
|---|---:|---:|---:|---:|---:|
| HEDEF | 262 | 1.4311 | 3.12 | 1.5427 | 0.2702 |
| STOP | 255 | -1.1306 | 2.82 | 0.5 | 1.0 |
| STOP_GAP | 25 | -1.4361 | 3.36 | 0.5901 | 1.3274 |
| ZAMAN_STOPU | 95 | 0.2352 | 10.0 | 0.9035 | 0.5566 |

| Çıkıştan Önceki Son Tez Durumu | N | Pay | Net15 Ort R | Stop Oranı |
|---|---:|---:|---:|---:|
| BEKLIYOR | 56 | 8.8% | -0.0335 | 44.6% |
| BOZULDU | 26 | 4.1% | -0.9649 | 84.6% |
| GOZLEM_YOK | 87 | 13.7% | -0.0092 | 55.2% |
| SINANIYOR | 62 | 9.7% | -1.0572 | 93.5% |
| TEYITLI | 406 | 63.7% | 0.4098 | 31.3% |

| Süreç Etiketi | Görüldüğü İşlem | Pay | İlk Görülme (medyan bar) |
|---|---:|---:|---:|
| FRM_TEYIT | 455 | 71.4% | 1 |
| FIYAT_TERS_KAPANIS | 432 | 67.8% | 1 |
| VP_LEHTE_BASKI | 426 | 66.9% | 1 |
| VP_DUSUK_KATILIM | 371 | 58.2% | 2 |
| FIYAT_YARIM_R | 358 | 56.2% | 2 |
| FIYAT_ZARARDA | 341 | 53.5% | 1 |
| FRM_RETEST_BEKLE | 287 | 45.1% | 2 |
| BLOK_DUVAR | 182 | 28.6% | 1 |
| FIYAT_BIR_R | 178 | 27.9% | 2 |
| SR_KARSI_ASILDI | 135 | 21.2% | 2 |
| ADAY_LEHTE | 130 | 20.4% | 2.5 |
| FRM_RETEST_OK | 130 | 20.4% | 2.5 |
| VP_TERS_BASKI | 123 | 19.3% | 5 |
| FRM_TAMAM | 119 | 18.7% | 7 |
| SR_KARSI_RED | 104 | 16.3% | 2 |
| SEVIYE_ICI | 102 | 16.0% | 3 |
| MS_INT_SWEEP_TERS | 78 | 12.2% | 3 |
| MS_EXT_SWEEP_TERS | 75 | 11.8% | 2 |
| MS_INT_BOS_LEHTE | 74 | 11.6% | 3 |
| FRM_RETEST | 57 | 8.9% | 4 |
| FRM_TEYITSIZ | 51 | 8.0% | 3 |
| ADAY_KARSI | 45 | 7.1% | 3 |
| MS_EXT_BOS_LEHTE | 41 | 6.4% | 2 |
| SEVIYE_GERI_ALINDI | 30 | 4.7% | 3.5 |
