# Gölge v2 — Veri Karantinası Penceresine Duyarlılık

> Üretici: `python -m research.golge_v2_karantina_duyarlilik`. Bu dosya elle düzenlenmez.

- Kopukluk eşiği: açılış / önceki kapanış farkı `%11.5` üstü; ileri pencere `13` bar (sabit).
- Sansürsüz olay: `46500`; seçeneğe göre karantinaya giren olay: `geri_0` → `78`, `geri_14` → `165`, `geri_30` → `325`, `geri_60` → `697`, `geri_120` → `1414`, `geri_sinirsiz` → `4286`, `sembol_disi` → `5735`.
- Varsayılan pencere (`60` bar) ana CSV'deki `veri_karantina` kolonunu birebir yeniden üretti: `evet`.

`geri_L`: kopukluktan sonraki `L` bar (günlük kopuklukta `L` günlük bar) kirli bağlam sayılır. `geri_0` yalnız kopukluk barının kendisini ve işlem penceresine düşen kopuklukları çıkarır. `geri_sinirsiz`: bir seride ilk kopukluktan sonraki bütün olaylar çıkar. `sembol_disi`: herhangi bir serisinde kopukluk olan sembol tümüyle çıkar (`29` sembol). `4h + 1d`, `Net15` R, sembol kümeli %95 GA.

## D7_A_Arti

| Karantina | Tümü N | Tümü Ort R | Tümü GA | Keşif N | Keşif Ort R | Doğrulama N | Doğrulama Ort R | Doğrulama GA |
|---|---:|---:|---|---:|---:|---:|---:|---|
| karantinasiz | 648 | 0.1234 | [0.0214, 0.2215] | 422 | 0.0632 | 226 | 0.2358 | [0.0673, 0.4042] |
| geri_0 | 645 | 0.1195 | [0.0167, 0.2171] | 421 | 0.0589 | 224 | 0.2334 | [0.0635, 0.401] |
| geri_14 | 645 | 0.1195 | [0.0167, 0.2171] | 421 | 0.0589 | 224 | 0.2334 | [0.0635, 0.401] |
| geri_30 | 644 | 0.1171 | [0.016, 0.2151] | 421 | 0.0589 | 223 | 0.2269 | [0.056, 0.3943] |
| geri_60 | 637 | 0.1147 | [0.0102, 0.2183] | 414 | 0.0543 | 223 | 0.2269 | [0.056, 0.3943] |
| geri_120 | 633 | 0.1143 | [0.0105, 0.2216] | 411 | 0.0569 | 222 | 0.2206 | [0.0451, 0.3908] |
| geri_sinirsiz | 601 | 0.1127 | [0.0008, 0.2136] | 394 | 0.0534 | 207 | 0.2255 | [0.0259, 0.4158] |
| sembol_disi | 578 | 0.1145 | [0.0118, 0.2202] | 376 | 0.0518 | 202 | 0.2312 | [0.046, 0.4179] |

## D6_A_Cekirdek_Veya_Arti

| Karantina | Tümü N | Tümü Ort R | Tümü GA | Keşif N | Keşif Ort R | Doğrulama N | Doğrulama Ort R | Doğrulama GA |
|---|---:|---:|---|---:|---:|---:|---:|---|
| karantinasiz | 1140 | 0.0693 | [-0.0095, 0.141] | 750 | 0.0295 | 390 | 0.146 | [0.0205, 0.2757] |
| geri_0 | 1133 | 0.0653 | [-0.0128, 0.1379] | 746 | 0.0257 | 387 | 0.1418 | [0.0171, 0.2722] |
| geri_14 | 1133 | 0.0653 | [-0.0128, 0.1379] | 746 | 0.0257 | 387 | 0.1418 | [0.0171, 0.2722] |
| geri_30 | 1132 | 0.0639 | [-0.0144, 0.1366] | 746 | 0.0257 | 386 | 0.1378 | [0.0126, 0.2709] |
| geri_60 | 1124 | 0.0611 | [-0.0202, 0.1327] | 738 | 0.021 | 386 | 0.1378 | [0.0126, 0.2709] |
| geri_120 | 1111 | 0.0602 | [-0.0187, 0.1282] | 727 | 0.023 | 384 | 0.1306 | [0.0072, 0.2602] |
| geri_sinirsiz | 1043 | 0.0678 | [-0.0047, 0.1417] | 691 | 0.0292 | 352 | 0.1436 | [0.0015, 0.2949] |
| sembol_disi | 993 | 0.0684 | [-0.0086, 0.1477] | 650 | 0.0238 | 343 | 0.153 | [0.0089, 0.3071] |

## D1_Birincil

| Karantina | Tümü N | Tümü Ort R | Tümü GA | Keşif N | Keşif Ort R | Doğrulama N | Doğrulama Ort R | Doğrulama GA |
|---|---:|---:|---|---:|---:|---:|---:|---|
| karantinasiz | 4289 | 0.009 | [-0.0368, 0.0541] | 2771 | -0.0104 | 1518 | 0.0446 | [-0.0329, 0.1203] |
| geri_0 | 4273 | 0.0104 | [-0.0345, 0.0549] | 2758 | -0.0076 | 1515 | 0.0433 | [-0.0335, 0.119] |
| geri_14 | 4273 | 0.0104 | [-0.0345, 0.0549] | 2758 | -0.0076 | 1515 | 0.0433 | [-0.0335, 0.119] |
| geri_30 | 4266 | 0.01 | [-0.035, 0.0545] | 2753 | -0.0082 | 1513 | 0.043 | [-0.0339, 0.1189] |
| geri_60 | 4233 | 0.01 | [-0.0343, 0.0546] | 2723 | -0.0096 | 1510 | 0.0454 | [-0.0317, 0.1226] |
| geri_120 | 4174 | 0.0082 | [-0.0372, 0.049] | 2672 | -0.0119 | 1502 | 0.0438 | [-0.0277, 0.1163] |
| geri_sinirsiz | 3922 | 0.0134 | [-0.0338, 0.0604] | 2551 | -0.0104 | 1371 | 0.0577 | [-0.0201, 0.1398] |
| sembol_disi | 3742 | 0.0194 | [-0.0271, 0.0669] | 2401 | -0.0076 | 1341 | 0.0678 | [-0.0129, 0.1477] |

## Okuma

- Karantina sonuca bakmaz; yalnız kopukluğun takvim konumuna bakar. Pencere büyüdükçe çıkan olay artar.
- Kabul kapısı `D6` ve `D7` doğrulama dönemi alt sınırına bakar; bu iki alt sınırın pencereyle nasıl değiştiği kapı kararının veri temizliği yargısına ne kadar bağlı olduğunu gösterir.
- `geri_sinirsiz` ve `sembol_disi` örneklemi küçültür; aralığın genişlemesi yalnız kirlenmeden değil, azalan gözlem sayısından da gelir.
