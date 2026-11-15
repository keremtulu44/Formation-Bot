# Gölge v2 — İşlem-İçi Süreç Ölçümü

> Üretici: `python -m research.golge_v2_surec_olcum`. Bu dosya elle düzenlenmez.

- Evren: `176` sembol, `4h + 1d`, Mod 0, `2.0 ATR` hedef, 10 bar ufuk, `30 bps` masraf.
- İşlem (sansürsüz, veri karantinası dışı): `4233`; kod özeti `bf13afabe251`.
- Baz eşitliği (bu koşucunun bazı ile ana rapordaki `net15_20_r`): `4233` ortak işlemde en büyük mutlak fark `0.0` R, farklı işlem `0`; ana CSV'de bulunmayan işlem `0`.

**Okuma kılavuzu.** `İleri R`, etiketin ilk görüldüğü kapanıştan sonra işlemde kalmanın brüt getirisidir (pozitifse kalmak kazandırır). `Aynı yaşta koşulsuz`, aynı kapanış sayısında açık olan bütün işlemlerin ileri getirisidir; `Fark` ikisinin farkıdır ve etiketin taşıdığı bilgiyi ölçer. `Bilgi`: bu farkın en kötü aralığı sıfırı dışlıyorsa `KOTU` / `IYI`. `Çıkış adayı`: `İleri R`'nin kendisi iki dönemde de negatif ve en kötü üst sınırı sıfırın altında. Replay tablolarında `Fark`, varyantın aynı işlemlerde baza göre net R farkıdır. Aralıklar dört küme tanımının (sembol / gün / hafta / ay) **en kötüsüdür**. `n<30` sayılmaz; bu, dönem hücreleri için de geçerlidir. Çıkış politikalarında kabul için `sonraki açılış` uygulaması esas alınır; `kapanış` uygulaması iyimser üst sınırdır.

**Kabul kuralı.** `GECTI`: fark hem keşif hem doğrulama döneminde pozitif, iki dönemde de etkilenen işlem ≥ 30 ve en kötü alt sınır sıfırın üstünde. `UMUT_VAR`: aynı koşullar, ama alt sınır yalnız havuzda sıfırın üstünde. `ZAYIF_ARTI`: iki dönemde de pozitif ama aralık sıfırı içeriyor ya da bir dönemde etkilenen işlem < 30. `ZARARLI`: havuzda en kötü üst sınır bile negatif. `GECMEDI`: en az bir dönemde fark pozitif değil.

## D7_A_Arti

İşlem: `637` (keşif `414`, doğrulama `223`); baz net `+0.1147 R`.

### İleri beklenti (etiket ilk görüldükten sonra işlemde kalmanın brüt R'si)

| Etiket | N | İlk bar | O andaki açık R | İleri R | En kötü GA | Keşif (n) | Doğrulama (n) | Aynı yaşta koşulsuz | Fark | Fark en kötü GA | Bilgi | Çıkış adayı |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|---|---|
| SEVIYE_GERI_ALINDI | 30 | 3.5 | -0.057 | -0.285 | [-0.691, +0.123] | -0.393 (21) | -0.033 (9) | +0.066 | -0.351 | [-0.753, +0.056] | — | hayır |
| FRM_RETEST | 57 | 4 | -0.592 | -0.172 | [-0.412, +0.150] | -0.244 (43) | +0.052 (14) | +0.060 | -0.231 | [-0.473, +0.088] | — | hayır |
| TEZ=SINANIYOR | 112 | 3 | -0.625 | -0.142 | [-0.314, +0.038] | -0.209 (80) | +0.024 (32) | +0.084 | -0.226 | [-0.394, -0.046] | **KOTU** | hayır |
| SEVIYE_ICI | 102 | 3 | -0.668 | -0.126 | [-0.293, +0.044] | -0.162 (73) | -0.034 (29) | +0.086 | -0.212 | [-0.377, -0.041] | **KOTU** | hayır |
| MS_EXT_BOS_LEHTE | 41 | 2 | +0.324 | -0.068 | [-0.535, +0.303] | -0.033 (30) | -0.166 (11) | +0.066 | -0.135 | [-0.604, +0.235] | — | hayır |
| MS_INT_BOS_LEHTE | 74 | 3 | +0.573 | +0.013 | [-0.262, +0.256] | -0.074 (48) | +0.174 (26) | +0.087 | -0.074 | [-0.352, +0.170] | — | hayır |
| MS_INT_SWEEP_TERS | 78 | 3 | -0.277 | +0.016 | [-0.159, +0.191] | -0.045 (54) | +0.153 (24) | +0.093 | -0.077 | [-0.253, +0.102] | — | hayır |
| ADAY_KARSI | 45 | 3 | -0.438 | +0.035 | [-0.354, +0.366] | -0.035 (29) | +0.162 (16) | +0.074 | -0.039 | [-0.433, +0.293] | — | hayır |
| FRM_RETEST_BEKLE | 287 | 2 | +0.370 | +0.044 | [-0.089, +0.181] | +0.006 (193) | +0.122 (94) | +0.054 | -0.010 | [-0.142, +0.126] | — | hayır |
| ADAY_LEHTE | 130 | 2.5 | +0.155 | +0.046 | [-0.215, +0.301] | +0.099 (83) | -0.047 (47) | +0.055 | -0.009 | [-0.269, +0.245] | — | hayır |
| FRM_RETEST_OK | 130 | 2.5 | +0.155 | +0.046 | [-0.215, +0.301] | +0.099 (83) | -0.047 (47) | +0.055 | -0.009 | [-0.269, +0.245] | — | hayır |
| SR_KARSI_RED | 104 | 2 | -0.200 | +0.047 | [-0.218, +0.280] | +0.053 (67) | +0.036 (37) | +0.086 | -0.039 | [-0.308, +0.193] | — | hayır |
| SR_KARSI_ASILDI | 135 | 2 | +0.125 | +0.052 | [-0.177, +0.291] | +0.067 (90) | +0.021 (45) | +0.098 | -0.047 | [-0.277, +0.194] | — | hayır |
| FIYAT_TERS_KAPANIS | 432 | 1 | -0.023 | +0.066 | [-0.082, +0.197] | +0.043 (285) | +0.110 (147) | +0.103 | -0.037 | [-0.178, +0.090] | — | hayır |
| FIYAT_ZARARDA | 341 | 1 | -0.263 | +0.074 | [-0.072, +0.220] | +0.051 (225) | +0.119 (116) | +0.121 | -0.046 | [-0.191, +0.100] | — | hayır |
| VP_TERS_BASKI | 123 | 5 | -0.152 | +0.076 | [-0.078, +0.217] | +0.048 (77) | +0.122 (46) | +0.080 | -0.004 | [-0.160, +0.141] | — | hayır |
| FIYAT_BIR_R | 178 | 2 | +0.933 | +0.095 | [-0.117, +0.300] | +0.014 (117) | +0.251 (61) | +0.079 | +0.016 | [-0.196, +0.219] | — | hayır |
| FIYAT_YARIM_R | 358 | 2 | +0.527 | +0.096 | [-0.047, +0.238] | +0.060 (221) | +0.153 (137) | +0.095 | +0.001 | [-0.142, +0.143] | — | hayır |
| BLOK_DUVAR | 182 | 1 | +0.263 | +0.109 | [-0.066, +0.283] | +0.065 (123) | +0.199 (59) | +0.120 | -0.012 | [-0.186, +0.162] | — | hayır |
| FRM_TAMAM | 119 | 7 | +0.414 | +0.114 | [-0.033, +0.275] | +0.177 (75) | +0.006 (44) | +0.108 | +0.006 | [-0.140, +0.164] | — | hayır |
| FRM_TEYIT | 455 | 1 | +0.223 | +0.119 | [-0.012, +0.254] | +0.081 (294) | +0.187 (161) | +0.130 | -0.011 | [-0.140, +0.123] | — | hayır |
| TEZ=TEYITLI | 461 | 1 | +0.226 | +0.123 | [-0.008, +0.257] | +0.080 (295) | +0.201 (166) | +0.128 | -0.005 | [-0.138, +0.128] | — | hayır |
| VP_DUSUK_KATILIM | 371 | 2 | +0.102 | +0.130 | [-0.008, +0.271] | +0.087 (220) | +0.193 (151) | +0.092 | +0.038 | [-0.097, +0.178] | — | hayır |
| VP_LEHTE_BASKI | 426 | 1 | +0.169 | +0.160 | [+0.035, +0.291] | +0.140 (248) | +0.189 (178) | +0.137 | +0.023 | [-0.101, +0.157] | — | hayır |
| MS_EXT_SWEEP_TERS | 75 | 2 | -0.287 | +0.167 | [-0.083, +0.404] | +0.120 (48) | +0.251 (27) | +0.097 | +0.070 | [-0.177, +0.309] | — | hayır |
| FRM_TEYITSIZ | 51 | 3 | -0.069 | +0.324 | [+0.029, +0.593] | +0.439 (33) | +0.113 (18) | +0.031 | +0.293 | [-0.002, +0.562] | — | hayır |

`n<30` olduğu için tabloya alınmayan etiketler: `FRM_BASARISIZ`, `BLOK_DESTEK_KAYBI`, `MS_INT_CHOCH_LEHTE`, `BLOK_ASILDI`, `MS_INT_TRANSITION_FAIL_LEHTE`, `TEZ=BOZULDU`, `MS_EXT_FALSE_BREAK_TERS`, `FRM_KAYIP`, `MS_INT_FALSE_BREAK_TERS`.

### Eşleşmiş replay — Aleyhte gözlemde çıkış

| Varyant | Etkilenen | Etkilenenlerde baz kazanan / kaybeden | Fark R (tümü) | En kötü GA | Keşif (etkilenen) | Doğrulama (etkilenen) | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---:|---|
| `seviye_ici_acilis` — Kapanış tez seviyesinin ters tarafında → sonraki açılışta çık | 101 | 9 / 92 | +0.0181 | [-0.0117, +0.0409] | +0.0222 (72) | +0.0104 (29) | +11.5 | **ZAYIF_ARTI** |
| `seviye_ici_kapanis` — Kapanış tez seviyesinin ters tarafında → aynı kapanışta çık (iyimser) | 102 | 9 / 93 | +0.0201 | [-0.0103, +0.0456] | +0.0286 (73) | +0.0044 (29) | +12.8 | **ZAYIF_ARTI** |
| `tez_bozuldu_acilis` — Tez BOZULDU → sonraki açılışta çık | 26 | 2 / 24 | +0.0055 | [-0.0048, +0.0146] | +0.0071 (18) | +0.0025 (8) | +3.5 | **SAYILMAZ_N<30** |
| `tez_bozuldu_kapanis` — Tez BOZULDU → aynı kapanışta çık (iyimser) | 26 | 2 / 24 | +0.0067 | [-0.0039, +0.0163] | +0.0091 (18) | +0.0025 (8) | +4.3 | **SAYILMAZ_N<30** |
| `frm_retest_acilis` — Formasyon RETEST_EDILIYOR → sonraki açılışta çık | 57 | 5 / 52 | +0.0130 | [-0.0124, +0.0372] | +0.0187 (43) | +0.0023 (14) | +8.2 | **ZAYIF_ARTI** |
| `frm_retest_kapanis` — Formasyon RETEST_EDILIYOR → aynı kapanışta çık (iyimser) | 57 | 5 / 52 | +0.0153 | [-0.0112, +0.0437] | +0.0254 (43) | -0.0033 (14) | +9.8 | **GECMEDI** |
| `ters_kapanis_acilis` — İlk ters kapanış → sonraki açılışta çık | 432 | 190 / 242 | -0.0389 | [-0.1180, +0.0421] | -0.0247 (285) | -0.0653 (147) | -24.8 | **GECMEDI** |
| `blok_duvar_acilis` — Karşı OB/FVG bandında ret → sonraki açılışta çık | 180 | 108 / 72 | -0.0295 | [-0.0757, +0.0154] | -0.0217 (121) | -0.0438 (59) | -18.8 | **GECMEDI** |
| `sr_red_acilis` — Karşı Stabil çizgisinde ret → sonraki açılışta çık | 101 | 38 / 63 | -0.0074 | [-0.0473, +0.0259] | -0.0086 (66) | -0.0051 (35) | -4.7 | **GECMEDI** |
| `vp_ters_acilis` — Ters hacim baskısı → sonraki açılışta çık | 114 | 45 / 69 | -0.0128 | [-0.0413, +0.0131] | -0.0099 (72) | -0.0182 (42) | -8.2 | **GECMEDI** |
| `ms_ters_acilis` — Ters yapı kırılımı (iç/dış BOS-CHoCH) → sonraki açılışta çık | 0 | 0 / 0 | +0.0000 | [+0.0000, +0.0000] | +0.0000 (0) | +0.0000 (0) | +0.0 | **SAYILMAZ_N<30** |
| `aday_karsi_acilis` — Sistemin kendi karşı yön adayı → sonraki açılışta çık | 44 | 12 / 32 | -0.0007 | [-0.0294, +0.0235] | +0.0044 (28) | -0.0103 (16) | -0.5 | **GECMEDI** |

### Eşleşmiş replay — Kâr koruma (stop taşıma)

| Varyant | Etkilenen | Etkilenenlerde baz kazanan / kaybeden | Fark R (tümü) | En kötü GA | Keşif (etkilenen) | Doğrulama (etkilenen) | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---:|---|
| `kar_1_0` — +1R görülünce stop başa baş | 82 | 34 / 48 | -0.0115 | [-0.0551, +0.0343] | -0.0049 (58) | -0.0237 (24) | -7.3 | **GECMEDI** |
| `kar_1_025` — +1R görülünce stop +0.25R | 96 | 48 / 48 | -0.0140 | [-0.0704, +0.0443] | -0.0007 (65) | -0.0386 (31) | -8.9 | **GECMEDI** |
| `kar_15_05` — +1.5R görülünce stop +0.5R | 38 | 19 / 19 | +0.0001 | [-0.0330, +0.0320] | -0.0007 (26) | +0.0014 (12) | +0.0 | **GECMEDI** |

### Eşleşmiş replay — Hedefte çıkmayıp iz sürme

| Varyant | Etkilenen | Etkilenenlerde baz kazanan / kaybeden | Fark R (tümü) | En kötü GA | Keşif (etkilenen) | Doğrulama (etkilenen) | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---:|---|
| `hedef_kilit_10` — Hedefte çıkma; +1.0 ATR kilitle, ufka taşı | 262 | 262 / 0 | +0.0029 | [-0.1094, +0.1424] | -0.0639 (162) | +0.1269 (100) | +1.9 | **GECMEDI** |
| `hedef_kilit_15` — Hedefte çıkma; +1.5 ATR kilitle, ufka taşı | 262 | 262 / 0 | +0.0084 | [-0.0778, +0.1133] | -0.0420 (162) | +0.1021 (100) | +5.4 | **GECMEDI** |
| `hedef_iz_15` — Hedefte çıkma; +1.0 ATR kilit + 1.5 ATR kapanış izi | 262 | 262 / 0 | +0.0219 | [-0.0722, +0.1304] | -0.0245 (162) | +0.1082 (100) | +14.0 | **GECMEDI** |
| `hedef_iz_10` — Hedefte çıkma; +1.5 ATR kilit + 1.0 ATR kapanış izi | 262 | 262 / 0 | +0.0238 | [-0.0413, +0.0955] | +0.0039 (162) | +0.0607 (100) | +15.1 | **ZAYIF_ARTI** |
| `hedef_yapi` — Hedefte çıkma; +1.0 ATR kilit + iç yapı korunan seviye izi | 262 | 262 / 0 | +0.0029 | [-0.1094, +0.1424] | -0.0639 (162) | +0.1269 (100) | +1.9 | **GECMEDI** |

## D6_A_Cekirdek_Veya_Arti

İşlem: `1124` (keşif `738`, doğrulama `386`); baz net `+0.0611 R`.

### İleri beklenti (etiket ilk görüldükten sonra işlemde kalmanın brüt R'si)

| Etiket | N | İlk bar | O andaki açık R | İleri R | En kötü GA | Keşif (n) | Doğrulama (n) | Aynı yaşta koşulsuz | Fark | Fark en kötü GA | Bilgi | Çıkış adayı |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|---|---|
| SEVIYE_GERI_ALINDI | 62 | 4 | -0.119 | -0.207 | [-0.470, +0.054] | -0.244 (41) | -0.137 (21) | +0.019 | -0.227 | [-0.484, +0.035] | — | hayır |
| FRM_RETEST | 96 | 4 | -0.583 | -0.089 | [-0.281, +0.122] | -0.177 (71) | +0.163 (25) | +0.014 | -0.103 | [-0.294, +0.105] | — | hayır |
| SEVIYE_ICI | 193 | 3 | -0.693 | -0.086 | [-0.199, +0.040] | -0.096 (132) | -0.063 (61) | +0.038 | -0.123 | [-0.237, +0.004] | — | hayır |
| TEZ=SINANIYOR | 220 | 3 | -0.644 | -0.080 | [-0.194, +0.034] | -0.129 (151) | +0.026 (69) | +0.036 | -0.116 | [-0.228, +0.000] | — | hayır |
| BLOK_ASILDI | 39 | 3 | +0.882 | -0.061 | [-0.457, +0.282] | +0.254 (24) | -0.565 (15) | +0.050 | -0.111 | [-0.506, +0.241] | — | hayır |
| FRM_RETEST_OK | 207 | 3 | +0.014 | -0.059 | [-0.241, +0.120] | -0.006 (133) | -0.154 (74) | +0.016 | -0.075 | [-0.259, +0.105] | — | hayır |
| ADAY_LEHTE | 208 | 3 | +0.017 | -0.059 | [-0.240, +0.120] | -0.006 (134) | -0.154 (74) | +0.016 | -0.075 | [-0.258, +0.104] | — | hayır |
| MS_EXT_BOS_LEHTE | 166 | 2 | +0.454 | -0.030 | [-0.207, +0.158] | -0.060 (110) | +0.028 (56) | +0.030 | -0.060 | [-0.242, +0.131] | — | hayır |
| MS_INT_BOS_LEHTE | 158 | 2 | +0.558 | -0.018 | [-0.268, +0.195] | -0.081 (106) | +0.111 (52) | +0.046 | -0.064 | [-0.322, +0.152] | — | hayır |
| TEZ=BOZULDU | 50 | 5 | -0.665 | -0.014 | [-0.227, +0.233] | -0.032 (32) | +0.018 (18) | +0.018 | -0.032 | [-0.244, +0.217] | — | hayır |
| SR_KARSI_RED | 214 | 2 | -0.127 | -0.008 | [-0.200, +0.211] | -0.002 (148) | -0.021 (66) | +0.043 | -0.051 | [-0.243, +0.174] | — | hayır |
| ADAY_KARSI | 91 | 3 | -0.412 | +0.003 | [-0.245, +0.250] | +0.005 (63) | -0.003 (28) | +0.038 | -0.035 | [-0.285, +0.215] | — | hayır |
| MS_INT_SWEEP_TERS | 174 | 3 | -0.178 | +0.004 | [-0.129, +0.132] | -0.056 (115) | +0.121 (59) | +0.046 | -0.042 | [-0.175, +0.086] | — | hayır |
| FRM_KAYIP | 37 | 8 | -0.081 | +0.010 | [-0.153, +0.193] | +0.019 (22) | -0.003 (15) | +0.044 | -0.035 | [-0.194, +0.148] | — | hayır |
| FRM_RETEST_BEKLE | 515 | 2 | +0.342 | +0.013 | [-0.108, +0.139] | +0.018 (340) | +0.003 (175) | +0.020 | -0.007 | [-0.128, +0.120] | — | hayır |
| FIYAT_BIR_R | 294 | 3 | +0.903 | +0.021 | [-0.156, +0.185] | -0.002 (189) | +0.061 (105) | +0.030 | -0.010 | [-0.190, +0.156] | — | hayır |
| FIYAT_YARIM_R | 620 | 2 | +0.488 | +0.031 | [-0.098, +0.154] | +0.007 (393) | +0.072 (227) | +0.048 | -0.017 | [-0.148, +0.106] | — | hayır |
| FIYAT_TERS_KAPANIS | 805 | 1 | -0.058 | +0.045 | [-0.072, +0.167] | +0.040 (533) | +0.055 (272) | +0.059 | -0.014 | [-0.130, +0.105] | — | hayır |
| SR_KARSI_ASILDI | 233 | 2 | +0.250 | +0.045 | [-0.130, +0.229] | +0.043 (164) | +0.051 (69) | +0.047 | -0.001 | [-0.178, +0.182] | — | hayır |
| VP_TERS_BASKI | 235 | 5 | -0.204 | +0.048 | [-0.069, +0.174] | +0.051 (143) | +0.044 (92) | +0.030 | +0.018 | [-0.102, +0.147] | — | hayır |
| FRM_TAMAM | 213 | 7 | +0.351 | +0.053 | [-0.059, +0.192] | +0.081 (142) | -0.003 (71) | +0.043 | +0.011 | [-0.101, +0.148] | — | hayır |
| FIYAT_ZARARDA | 664 | 1 | -0.269 | +0.058 | [-0.053, +0.178] | +0.048 (439) | +0.077 (225) | +0.071 | -0.013 | [-0.122, +0.107] | — | hayır |
| FRM_TEYIT | 776 | 1 | +0.199 | +0.060 | [-0.045, +0.164] | +0.040 (507) | +0.099 (269) | +0.081 | -0.021 | [-0.126, +0.083] | — | hayır |
| TEZ=TEYITLI | 796 | 1 | +0.211 | +0.066 | [-0.044, +0.169] | +0.042 (518) | +0.111 (278) | +0.078 | -0.012 | [-0.123, +0.091] | — | hayır |
| MS_EXT_SWEEP_TERS | 155 | 2 | -0.145 | +0.085 | [-0.103, +0.260] | +0.025 (104) | +0.208 (51) | +0.042 | +0.043 | [-0.146, +0.217] | — | hayır |
| VP_DUSUK_KATILIM | 688 | 2 | +0.063 | +0.090 | [-0.032, +0.204] | +0.073 (412) | +0.115 (276) | +0.053 | +0.036 | [-0.088, +0.151] | — | hayır |
| VP_LEHTE_BASKI | 738 | 1 | +0.156 | +0.090 | [-0.025, +0.199] | +0.079 (436) | +0.105 (302) | +0.088 | +0.001 | [-0.112, +0.112] | — | hayır |
| BLOK_DUVAR | 361 | 1 | +0.225 | +0.130 | [-0.011, +0.269] | +0.120 (236) | +0.150 (125) | +0.074 | +0.056 | [-0.084, +0.193] | — | hayır |
| FRM_TEYITSIZ | 118 | 3 | -0.025 | +0.139 | [-0.055, +0.326] | +0.134 (82) | +0.149 (36) | -0.007 | +0.146 | [-0.047, +0.334] | — | hayır |

`n<30` olduğu için tabloya alınmayan etiketler: `MS_EXT_SWEEP_LEHTE`, `MS_INT_CHOCH_LEHTE`, `MS_INT_BOS_TERS`, `MS_INT_TRANSITION_FAIL_LEHTE`, `FRM_BASARISIZ`, `MS_INT_SWEEP_LEHTE`, `MS_INT_FALSE_BREAK_TERS`, `BLOK_DESTEK_KAYBI`, `MS_EXT_FALSE_BREAK_TERS`, `FRM_KARSI_KIRILIM`.

### Eşleşmiş replay — Aleyhte gözlemde çıkış

| Varyant | Etkilenen | Etkilenenlerde baz kazanan / kaybeden | Fark R (tümü) | En kötü GA | Keşif (etkilenen) | Doğrulama (etkilenen) | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---:|---|
| `seviye_ici_acilis` — Kapanış tez seviyesinin ters tarafında → sonraki açılışta çık | 191 | 18 / 173 | +0.0144 | [-0.0064, +0.0326] | +0.0150 (130) | +0.0133 (61) | +16.2 | **ZAYIF_ARTI** |
| `seviye_ici_kapanis` — Kapanış tez seviyesinin ters tarafında → aynı kapanışta çık (iyimser) | 193 | 18 / 175 | +0.0147 | [-0.0074, +0.0363] | +0.0172 (132) | +0.0099 (61) | +16.6 | **ZAYIF_ARTI** |
| `tez_bozuldu_acilis` — Tez BOZULDU → sonraki açılışta çık | 47 | 5 / 42 | +0.0009 | [-0.0095, +0.0104] | +0.0009 (31) | +0.0008 (16) | +1.0 | **ZAYIF_ARTI** |
| `tez_bozuldu_kapanis` — Tez BOZULDU → aynı kapanışta çık (iyimser) | 50 | 5 / 45 | +0.0006 | [-0.0100, +0.0106] | +0.0014 (32) | -0.0009 (18) | +0.7 | **GECMEDI** |
| `frm_retest_acilis` — Formasyon RETEST_EDILIYOR → sonraki açılışta çık | 96 | 10 / 86 | +0.0065 | [-0.0097, +0.0231] | +0.0134 (71) | -0.0066 (25) | +7.3 | **GECMEDI** |
| `frm_retest_kapanis` — Formasyon RETEST_EDILIYOR → aynı kapanışta çık (iyimser) | 96 | 10 / 86 | +0.0076 | [-0.0112, +0.0268] | +0.0171 (71) | -0.0105 (25) | +8.5 | **GECMEDI** |
| `ters_kapanis_acilis` — İlk ters kapanış → sonraki açılışta çık | 805 | 336 / 469 | -0.0239 | [-0.1013, +0.0569] | -0.0235 (533) | -0.0249 (272) | -26.9 | **GECMEDI** |
| `blok_duvar_acilis` — Karşı OB/FVG bandında ret → sonraki açılışta çık | 357 | 206 / 151 | -0.0364 | [-0.0774, +0.0080] | -0.0358 (232) | -0.0378 (125) | -41.0 | **GECMEDI** |
| `sr_red_acilis` — Karşı Stabil çizgisinde ret → sonraki açılışta çık | 209 | 79 / 130 | +0.0015 | [-0.0403, +0.0341] | -0.0000 (146) | +0.0045 (63) | +1.7 | **GECMEDI** |
| `vp_ters_acilis` — Ters hacim baskısı → sonraki açılışta çık | 221 | 79 / 142 | -0.0072 | [-0.0339, +0.0176] | -0.0087 (136) | -0.0043 (85) | -8.1 | **GECMEDI** |
| `ms_ters_acilis` — Ters yapı kırılımı (iç/dış BOS-CHoCH) → sonraki açılışta çık | 1 | 0 / 1 | +0.0003 | [+0.0000, +0.0013] | +0.0005 (1) | +0.0000 (0) | +0.4 | **SAYILMAZ_N<30** |
| `aday_karsi_acilis` — Sistemin kendi karşı yön adayı → sonraki açılışta çık | 89 | 22 / 67 | +0.0017 | [-0.0208, +0.0195] | +0.0011 (62) | +0.0028 (27) | +1.9 | **ZAYIF_ARTI** |

### Eşleşmiş replay — Kâr koruma (stop taşıma)

| Varyant | Etkilenen | Etkilenenlerde baz kazanan / kaybeden | Fark R (tümü) | En kötü GA | Keşif (etkilenen) | Doğrulama (etkilenen) | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---:|---|
| `kar_1_0` — +1R görülünce stop başa baş | 138 | 53 / 85 | -0.0039 | [-0.0343, +0.0293] | -0.0039 (90) | -0.0039 (48) | -4.3 | **GECMEDI** |
| `kar_1_025` — +1R görülünce stop +0.25R | 156 | 71 / 85 | +0.0005 | [-0.0367, +0.0397] | +0.0031 (100) | -0.0044 (56) | +0.6 | **GECMEDI** |
| `kar_15_05` — +1.5R görülünce stop +0.5R | 56 | 31 / 25 | -0.0022 | [-0.0230, +0.0183] | -0.0021 (37) | -0.0024 (19) | -2.5 | **GECMEDI** |

### Eşleşmiş replay — Hedefte çıkmayıp iz sürme

| Varyant | Etkilenen | Etkilenenlerde baz kazanan / kaybeden | Fark R (tümü) | En kötü GA | Keşif (etkilenen) | Doğrulama (etkilenen) | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---:|---|
| `hedef_kilit_10` — Hedefte çıkma; +1.0 ATR kilitle, ufka taşı | 447 | 447 / 0 | +0.0492 | [-0.0336, +0.1467] | +0.0074 (281) | +0.1292 (166) | +55.3 | **ZAYIF_ARTI** |
| `hedef_kilit_15` — Hedefte çıkma; +1.5 ATR kilitle, ufka taşı | 447 | 447 / 0 | +0.0351 | [-0.0292, +0.1127] | +0.0151 (281) | +0.0733 (166) | +39.5 | **ZAYIF_ARTI** |
| `hedef_iz_15` — Hedefte çıkma; +1.0 ATR kilit + 1.5 ATR kapanış izi | 447 | 447 / 0 | +0.0625 | [-0.0093, +0.1450] | +0.0378 (281) | +0.1097 (166) | +70.3 | **ZAYIF_ARTI** |
| `hedef_iz_10` — Hedefte çıkma; +1.5 ATR kilit + 1.0 ATR kapanış izi | 447 | 447 / 0 | +0.0482 | [-0.0071, +0.1073] | +0.0459 (281) | +0.0526 (166) | +54.2 | **ZAYIF_ARTI** |
| `hedef_yapi` — Hedefte çıkma; +1.0 ATR kilit + iç yapı korunan seviye izi | 447 | 447 / 0 | +0.0492 | [-0.0336, +0.1467] | +0.0074 (281) | +0.1292 (166) | +55.3 | **ZAYIF_ARTI** |

## D1_Birincil

İşlem: `4233` (keşif `2723`, doğrulama `1510`); baz net `+0.0100 R`.

### İleri beklenti (etiket ilk görüldükten sonra işlemde kalmanın brüt R'si)

| Etiket | N | İlk bar | O andaki açık R | İleri R | En kötü GA | Keşif (n) | Doğrulama (n) | Aynı yaşta koşulsuz | Fark | Fark en kötü GA | Bilgi | Çıkış adayı |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|---|---|
| MS_INT_FALSE_BREAK_TERS | 45 | 3 | -0.182 | -0.252 | [-0.568, +0.100] | -0.172 (33) | -0.470 (12) | +0.039 | -0.291 | [-0.601, +0.056] | — | hayır |
| MS_EXT_SWEEP_LEHTE | 34 | 1 | +0.237 | -0.163 | [-0.562, +0.256] | -0.117 (21) | -0.238 (13) | +0.067 | -0.231 | [-0.636, +0.186] | — | hayır |
| TEZ=BOZULDU | 222 | 4 | -0.655 | -0.101 | [-0.198, +0.007] | -0.097 (132) | -0.108 (90) | +0.028 | -0.130 | [-0.226, -0.022] | **KOTU** | hayır |
| MS_EXT_TRANSITION_FAIL_LEHTE | 38 | 3 | +0.992 | -0.087 | [-0.487, +0.304] | -0.130 (24) | -0.014 (14) | +0.047 | -0.134 | [-0.533, +0.251] | — | hayır |
| MS_INT_CHOCH_LEHTE | 240 | 2 | +1.006 | -0.048 | [-0.238, +0.141] | -0.004 (151) | -0.122 (89) | +0.053 | -0.102 | [-0.294, +0.087] | — | hayır |
| SEVIYE_ICI | 884 | 3 | -0.639 | -0.005 | [-0.070, +0.064] | -0.008 (573) | -0.001 (311) | +0.051 | -0.056 | [-0.122, +0.013] | — | hayır |
| TEZ=SINANIYOR | 925 | 3 | -0.620 | -0.004 | [-0.070, +0.060] | -0.014 (604) | +0.016 (321) | +0.050 | -0.054 | [-0.118, +0.011] | — | hayır |
| FRM_RETEST | 215 | 3 | -0.595 | -0.001 | [-0.142, +0.154] | -0.071 (152) | +0.168 (63) | +0.030 | -0.032 | [-0.173, +0.123] | — | hayır |
| VP_TERS_BASKI | 921 | 5 | -0.186 | +0.032 | [-0.050, +0.120] | +0.023 (529) | +0.044 (392) | +0.046 | -0.014 | [-0.095, +0.075] | — | hayır |
| FRM_RETEST_BEKLE | 1930 | 2 | +0.434 | +0.032 | [-0.049, +0.110] | +0.022 (1225) | +0.049 (705) | +0.043 | -0.011 | [-0.092, +0.067] | — | hayır |
| FRM_TAMAM | 832 | 7 | +0.465 | +0.037 | [-0.028, +0.101] | +0.055 (537) | +0.005 (295) | +0.029 | +0.008 | [-0.058, +0.071] | — | hayır |
| FIYAT_BIR_R | 1397 | 2 | +0.926 | +0.039 | [-0.057, +0.129] | +0.020 (889) | +0.071 (508) | +0.051 | -0.012 | [-0.106, +0.077] | — | hayır |
| MS_EXT_BOS_LEHTE | 328 | 2 | +0.747 | +0.039 | [-0.096, +0.183] | -0.009 (220) | +0.138 (108) | +0.048 | -0.009 | [-0.146, +0.136] | — | hayır |
| FRM_KAYIP | 119 | 8 | +0.053 | +0.045 | [-0.062, +0.169] | +0.054 (74) | +0.030 (45) | +0.023 | +0.022 | [-0.085, +0.143] | — | hayır |
| SEVIYE_GERI_ALINDI | 286 | 3 | -0.013 | +0.051 | [-0.108, +0.204] | +0.039 (192) | +0.073 (94) | +0.031 | +0.020 | [-0.140, +0.174] | — | hayır |
| MS_INT_SWEEP_TERS | 643 | 2 | +0.059 | +0.051 | [-0.059, +0.146] | -0.022 (420) | +0.188 (223) | +0.052 | -0.001 | [-0.110, +0.094] | — | hayır |
| SR_KARSI_RED | 744 | 2 | +0.089 | +0.054 | [-0.050, +0.173] | +0.059 (502) | +0.045 (242) | +0.055 | -0.001 | [-0.105, +0.117] | — | hayır |
| FIYAT_TERS_KAPANIS | 2969 | 1 | -0.027 | +0.057 | [-0.003, +0.125] | +0.043 (1919) | +0.082 (1050) | +0.067 | -0.010 | [-0.070, +0.057] | — | hayır |
| ADAY_KARSI | 354 | 3 | -0.301 | +0.058 | [-0.093, +0.230] | +0.137 (226) | -0.081 (128) | +0.050 | +0.009 | [-0.144, +0.179] | — | hayır |
| FIYAT_ZARARDA | 2361 | 1 | -0.286 | +0.059 | [-0.004, +0.123] | +0.045 (1520) | +0.084 (841) | +0.075 | -0.016 | [-0.079, +0.048] | — | hayır |
| MS_INT_TRANSITION_FAIL_LEHTE | 61 | 3 | +0.920 | +0.060 | [-0.261, +0.396] | +0.024 (42) | +0.142 (19) | +0.051 | +0.009 | [-0.313, +0.343] | — | hayır |
| FRM_TEYITSIZ | 416 | 3 | -0.046 | +0.060 | [-0.035, +0.157] | +0.023 (252) | +0.118 (164) | +0.025 | +0.036 | [-0.060, +0.132] | — | hayır |
| BLOK_DESTEK_KAYBI | 54 | 4 | -0.414 | +0.065 | [-0.192, +0.339] | -0.048 (30) | +0.206 (24) | +0.027 | +0.038 | [-0.220, +0.312] | — | hayır |
| VP_LEHTE_BASKI | 2588 | 1 | +0.233 | +0.068 | [-0.005, +0.143] | +0.032 (1532) | +0.120 (1056) | +0.087 | -0.019 | [-0.092, +0.055] | — | hayır |
| MS_INT_SWEEP_LEHTE | 47 | 4 | +0.042 | +0.077 | [-0.224, +0.379] | +0.075 (30) | +0.079 (17) | +0.044 | +0.033 | [-0.269, +0.336] | — | hayır |
| VP_DUSUK_KATILIM | 2653 | 2 | +0.108 | +0.079 | [+0.009, +0.151] | +0.045 (1557) | +0.129 (1096) | +0.069 | +0.011 | [-0.060, +0.083] | — | hayır |
| FRM_RETEST_OK | 635 | 2 | -0.015 | +0.080 | [-0.053, +0.209] | +0.093 (409) | +0.056 (226) | +0.036 | +0.043 | [-0.089, +0.173] | — | hayır |
| ADAY_LEHTE | 673 | 2 | +0.015 | +0.081 | [-0.048, +0.212] | +0.087 (435) | +0.071 (238) | +0.037 | +0.044 | [-0.086, +0.176] | — | hayır |
| FIYAT_YARIM_R | 2349 | 1 | +0.507 | +0.082 | [+0.007, +0.158] | +0.059 (1487) | +0.121 (862) | +0.067 | +0.015 | [-0.060, +0.091] | — | hayır |
| MS_EXT_CHOCH_LEHTE | 107 | 3 | +0.996 | +0.082 | [-0.133, +0.283] | +0.034 (70) | +0.172 (37) | +0.046 | +0.036 | [-0.179, +0.241] | — | hayır |
| FRM_TEYIT | 2871 | 1 | +0.257 | +0.089 | [+0.015, +0.161] | +0.070 (1849) | +0.122 (1022) | +0.086 | +0.002 | [-0.071, +0.074] | — | hayır |
| BLOK_DUVAR | 1657 | 1 | +0.310 | +0.089 | [+0.006, +0.169] | +0.081 (1061) | +0.104 (596) | +0.080 | +0.010 | [-0.073, +0.088] | — | hayır |
| TEZ=TEYITLI | 2856 | 1 | +0.290 | +0.092 | [+0.017, +0.167] | +0.075 (1832) | +0.123 (1024) | +0.085 | +0.007 | [-0.067, +0.082] | — | hayır |
| MS_EXT_SWEEP_TERS | 411 | 2 | +0.044 | +0.111 | [-0.003, +0.240] | -0.003 (274) | +0.338 (137) | +0.054 | +0.057 | [-0.058, +0.188] | — | hayır |
| SR_KARSI_ASILDI | 800 | 2 | +0.592 | +0.116 | [+0.004, +0.230] | +0.108 (546) | +0.135 (254) | +0.061 | +0.056 | [-0.058, +0.169] | — | hayır |
| MS_INT_BOS_LEHTE | 440 | 2 | +0.764 | +0.127 | [+0.006, +0.243] | +0.079 (277) | +0.209 (163) | +0.053 | +0.075 | [-0.045, +0.190] | — | hayır |
| BLOK_ASILDI | 193 | 2 | +1.109 | +0.193 | [+0.011, +0.368] | +0.261 (114) | +0.095 (79) | +0.063 | +0.130 | [-0.051, +0.304] | — | hayır |

`n<30` olduğu için tabloya alınmayan etiketler: `MS_INT_FALSE_BREAK_LEHTE`, `MS_EXT_BOS_TERS`, `MS_INT_TRANSITION_FAIL_TERS`, `MS_EXT_FALSE_BREAK_TERS`, `ADAY_LEHTE_BIRINCIL`, `FRM_BASARISIZ`, `MS_INT_BOS_TERS`, `ADAY_KARSI_BIRINCIL`, `FRM_KARSI_KIRILIM`.

### Eşleşmiş replay — Aleyhte gözlemde çıkış

| Varyant | Etkilenen | Etkilenenlerde baz kazanan / kaybeden | Fark R (tümü) | En kötü GA | Keşif (etkilenen) | Doğrulama (etkilenen) | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---:|---|
| `seviye_ici_acilis` — Kapanış tez seviyesinin ters tarafında → sonraki açılışta çık | 862 | 110 / 752 | +0.0033 | [-0.0109, +0.0165] | +0.0005 (561) | +0.0085 (301) | +14.2 | **ZAYIF_ARTI** |
| `seviye_ici_kapanis` — Kapanış tez seviyesinin ters tarafında → aynı kapanışta çık (iyimser) | 884 | 110 / 774 | +0.0011 | [-0.0130, +0.0149] | +0.0016 (573) | +0.0002 (311) | +4.8 | **ZAYIF_ARTI** |
| `tez_bozuldu_acilis` — Tez BOZULDU → sonraki açılışta çık | 212 | 21 / 191 | +0.0049 | [-0.0003, +0.0096] | +0.0025 (129) | +0.0090 (83) | +20.6 | **ZAYIF_ARTI** |
| `tez_bozuldu_kapanis` — Tez BOZULDU → aynı kapanışta çık (iyimser) | 222 | 21 / 201 | +0.0053 | [-0.0001, +0.0103] | +0.0047 (132) | +0.0065 (90) | +22.5 | **ZAYIF_ARTI** |
| `frm_retest_acilis` — Formasyon RETEST_EDILIYOR → sonraki açılışta çık | 215 | 31 / 184 | -0.0004 | [-0.0079, +0.0070] | +0.0025 (152) | -0.0056 (63) | -1.7 | **GECMEDI** |
| `frm_retest_kapanis` — Formasyon RETEST_EDILIYOR → aynı kapanışta çık (iyimser) | 215 | 31 / 184 | +0.0001 | [-0.0076, +0.0073] | +0.0040 (152) | -0.0070 (63) | +0.3 | **GECMEDI** |
| `ters_kapanis_acilis` — İlk ters kapanış → sonraki açılışta çık | 2969 | 1177 / 1792 | -0.0286 | [-0.0688, +0.0148] | -0.0202 (1919) | -0.0437 (1050) | -120.9 | **GECMEDI** |
| `blok_duvar_acilis` — Karşı OB/FVG bandında ret → sonraki açılışta çık | 1649 | 867 / 782 | -0.0305 | [-0.0603, -0.0004] | -0.0295 (1055) | -0.0321 (594) | -128.9 | **ZARARLI** |
| `sr_red_acilis` — Karşı Stabil çizgisinde ret → sonraki açılışta çık | 731 | 324 / 407 | -0.0103 | [-0.0291, +0.0071] | -0.0112 (496) | -0.0087 (235) | -43.7 | **GECMEDI** |
| `vp_ters_acilis` — Ters hacim baskısı → sonraki açılışta çık | 891 | 295 / 596 | -0.0021 | [-0.0192, +0.0152] | -0.0027 (511) | -0.0012 (380) | -9.1 | **GECMEDI** |
| `ms_ters_acilis` — Ters yapı kırılımı (iç/dış BOS-CHoCH) → sonraki açılışta çık | 20 | 1 / 19 | +0.0003 | [-0.0004, +0.0010] | -0.0000 (13) | +0.0009 (7) | +1.3 | **SAYILMAZ_N<30** |
| `aday_karsi_acilis` — Sistemin kendi karşı yön adayı → sonraki açılışta çık | 349 | 107 / 242 | -0.0030 | [-0.0178, +0.0109] | -0.0100 (223) | +0.0097 (126) | -12.5 | **GECMEDI** |

### Eşleşmiş replay — Kâr koruma (stop taşıma)

| Varyant | Etkilenen | Etkilenenlerde baz kazanan / kaybeden | Fark R (tümü) | En kötü GA | Keşif (etkilenen) | Doğrulama (etkilenen) | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---:|---|
| `kar_1_0` — +1R görülünce stop başa baş | 700 | 249 / 451 | -0.0051 | [-0.0226, +0.0125] | -0.0059 (457) | -0.0037 (243) | -21.6 | **GECMEDI** |
| `kar_1_025` — +1R görülünce stop +0.25R | 794 | 341 / 453 | -0.0006 | [-0.0210, +0.0197] | +0.0044 (505) | -0.0097 (289) | -2.6 | **GECMEDI** |
| `kar_15_05` — +1.5R görülünce stop +0.5R | 400 | 198 / 202 | -0.0032 | [-0.0178, +0.0109] | -0.0008 (265) | -0.0076 (135) | -13.7 | **GECMEDI** |

### Eşleşmiş replay — Hedefte çıkmayıp iz sürme

| Varyant | Etkilenen | Etkilenenlerde baz kazanan / kaybeden | Fark R (tümü) | En kötü GA | Keşif (etkilenen) | Doğrulama (etkilenen) | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---:|---|
| `hedef_kilit_10` — Hedefte çıkma; +1.0 ATR kilitle, ufka taşı | 1435 | 1435 / 0 | +0.0138 | [-0.0345, +0.0676] | -0.0014 (900) | +0.0414 (535) | +58.6 | **GECMEDI** |
| `hedef_kilit_15` — Hedefte çıkma; +1.5 ATR kilitle, ufka taşı | 1435 | 1435 / 0 | +0.0023 | [-0.0370, +0.0412] | -0.0075 (900) | +0.0199 (535) | +9.6 | **GECMEDI** |
| `hedef_iz_15` — Hedefte çıkma; +1.0 ATR kilit + 1.5 ATR kapanış izi | 1435 | 1435 / 0 | +0.0201 | [-0.0250, +0.0714] | +0.0074 (900) | +0.0430 (535) | +84.9 | **ZAYIF_ARTI** |
| `hedef_iz_10` — Hedefte çıkma; +1.5 ATR kilit + 1.0 ATR kapanış izi | 1435 | 1435 / 0 | +0.0148 | [-0.0195, +0.0489] | +0.0052 (900) | +0.0319 (535) | +62.5 | **ZAYIF_ARTI** |
| `hedef_yapi` — Hedefte çıkma; +1.0 ATR kilit + iç yapı korunan seviye izi | 1435 | 1435 / 0 | +0.0138 | [-0.0345, +0.0676] | -0.0014 (900) | +0.0414 (535) | +58.6 | **GECMEDI** |

## Özet karar

- **D7_A_Arti**
  - Replay: GECTI = yok; UMUT_VAR = yok; ZARARLI = yok; ZAYIF_ARTI = `seviye_ici_acilis`, `seviye_ici_kapanis`, `frm_retest_acilis`, `hedef_iz_10`.
  - Etiketler: çıkış adayı = yok; bilgi `KOTU` = `TEZ=SINANIYOR`, `SEVIYE_ICI`; bilgi `IYI` = yok; ileri R iki dönemde de negatif (aralığa bakılmadan) = yok.
- **D6_A_Cekirdek_Veya_Arti**
  - Replay: GECTI = yok; UMUT_VAR = yok; ZARARLI = yok; ZAYIF_ARTI = `seviye_ici_acilis`, `seviye_ici_kapanis`, `tez_bozuldu_acilis`, `aday_karsi_acilis`, `hedef_kilit_10`, `hedef_kilit_15`, `hedef_iz_15`, `hedef_iz_10`, `hedef_yapi`.
  - Etiketler: çıkış adayı = yok; bilgi `KOTU` = yok; bilgi `IYI` = yok; ileri R iki dönemde de negatif (aralığa bakılmadan) = `SEVIYE_ICI`, `FRM_RETEST_OK`, `ADAY_LEHTE`, `SR_KARSI_RED`.
- **D1_Birincil**
  - Replay: GECTI = yok; UMUT_VAR = yok; ZARARLI = `blok_duvar_acilis`; ZAYIF_ARTI = `seviye_ici_acilis`, `seviye_ici_kapanis`, `tez_bozuldu_acilis`, `tez_bozuldu_kapanis`, `hedef_iz_15`, `hedef_iz_10`.
  - Etiketler: çıkış adayı = yok; bilgi `KOTU` = `TEZ=BOZULDU`; bilgi `IYI` = yok; ileri R iki dönemde de negatif (aralığa bakılmadan) = `TEZ=BOZULDU`, `MS_INT_CHOCH_LEHTE`, `SEVIYE_ICI`.

## Sınırlar

- 20 varyant × 3 küme sınandı; çoklu karşılaştırma düzeltmesi yapılmadı. `GECTI` bile yalnız ileriye dönük gölge defterde izlenecek aday demektir.
- Keşif ve doğrulama dönemleri aynı arşivin iki dilimidir; baz beklenti iki dönem arasında belirgin oynar (özellikle short tarafı), bu yüzden tek dönemde görünen iyileşme rejim etkisi olabilir.
- Bar içi sıra bilinmez: stop ile hedef aynı barda ise stop sayılır; taşınan stop ve politika çıkışı bir sonraki bardan itibaren işler. Hedefe değilen barda kilit o bar için geçerli değildir.
- İzleme işlemin kendi zaman dilimindedir (4h / 1d barları). Alt zaman dilimiyle yönetim ayrı ölçümdür (`mtf_olcum`).
- Üç küme iç içedir (`D7 ⊂ D6 ⊂ D1`); bir kuralın üç kümede de aynı yönde çıkması üç bağımsız doğrulama değildir.
- `Bilgi` bayrakları da çoklu karşılaştırmaya göre düzeltilmemiştir (küme başına onlarca etiket sınanır).
- Bütün işlemlerde birebir aynı sonucu veren varyantlar: `hedef_kilit_10` = `hedef_yapi`. Aralarındaki fark bu örneklemde hiç devreye girmedi; ayrı kanıt sayılmaz.
