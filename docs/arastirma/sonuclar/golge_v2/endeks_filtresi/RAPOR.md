# Gölge v2 — Endeks Rejimi Filtresi: "Endeks Uzun Süredir Düşüyorsa İşlem Yok"

> Üretici: `python -m research.golge_v2_endeks_filtresi`. Bu dosya elle düzenlenmez.

- Kapsam: `4h + 1d` birincil işlemler (sansürsüz, veri karantinası dışı). İşlem: `4233`. Sonuçlar ana CSV'den okunur; yarış yeniden koşulmaz.
- Endeks: `XU100` günlük, `2024-10-21` – `2026-10-19` (`499` gün). Rejim yalnız girişten ÖNCE kapanmış günlerden hesaplanır; aynı günün kapanışı kullanılmaz.

**Okuma kılavuzu.** `Doğrudan stop`: stop olan ve stop mumundan önce `0.5 ATR` kârı hiç görmemiş işlem (doğrudan düşen ya da çok az yükselip düşen). `0.5 ATR görüp stop`: stoptan önce en az `0.5 ATR` kâr görmüş olan. İkisinin toplamı stop oranıdır; mum çözünürlüğünde ölçülür (stop mumunun içi görülmez). `Fayda`: elenen işlemin net R'sinin ters işaretlisi; elenen işlemler zarar ediyorsa pozitiftir. `Toplam fayda R`: filtre uygulansaydı toplam net R'nin değişimi. `Fayda en kötü GA`: işlem başına faydanın (elenmeyenlerde 0) sembol / gün / hafta / ay kümeli %95 aralıklarının en düşük alt ve en yüksek üst sınırı. `Ayrı dönem`: elenen işlemlerin düştüğü ayrı rejim dönemi sayısı; parantez içi, elenen işlemlerin toplamda zarar ettiği dönem sayısı.

**Kabul kuralı.** `GECTI`: fayda keşif ve doğrulamada pozitif, iki dönemde de elenen işlem ≥ 30 ve iki dönemde de en kötü alt sınır sıfırın üstünde. `UMUT_VAR`: aynı, ama alt sınır yalnız havuzda sıfırın üstünde. `ZAYIF_ARTI`: iki dönemde de pozitif ama aralık sıfırı içeriyor ya da bir dönemde elenen işlem < 30. `GECMEDI`: en az bir dönemde fayda pozitif değil (elenen işlemler o dönemde kâr etmiş). `ZARARLI`: havuzda en kötü üst sınır bile negatif. `SAYILMAZ_N<30`: elenen işlem 30'dan az.

**Sınırlar.** Rejim bir zaman değişkenidir; aynı gün açılan işlemler aynı rejimi taşır ve bir dönem haftalarca sürer. İki yıllık arşivde ayrı dönem sayısı azdır, bu yüzden hafta ve ay kümeli aralıklar bile belirsizliği olduğundan dar gösterebilir. `7` tanım × `4` filtre × 3 küme sınandı; çoklu karşılaştırma düzeltmesi yok. Short sonuçları açığa satışın mümkün olduğunu varsayar.

## Kısa özet

- **Soru:** girişte bilinen uzun vadeli endeks rejimi, doğrudan stop olanları ayırıyor mu? Ana tanım `getiri_20` (endeks son 20 günde ekside).
- **D7, endeks işleme karşıyken:** `222` işlem; stop `41.4%`, doğrudan stop `23.0%`, net `+0.164 R` [-0.057, +0.414].
- **D7, endeks işlemle aynı yöndeyken:** `415` işlem; stop `45.3%`, doğrudan stop `24.1%`, net `+0.088 R` [-0.093, +0.233].
- **Filtre kararları** (`7` rejim tanımı × `4` filtre = `28` varyant; `GECTI` ya da `UMUT_VAR` alan): D7 `0`; D6 `0`; D1 `0`. Dağılım: D7 GECMEDI 24, SAYILMAZ_N<30 2, ZARARLI 2; D6 GECMEDI 26, SAYILMAZ_N<30 1, ZAYIF_ARTI 1; D1 GECMEDI 21, ZAYIF_ARTI 7.
- **Bağımsız gözlem azlığı:** arşiv `499` endeks günü. `getiri_20` tanımıyla yalnız `25` ayrı düşüş dönemi ve `25` ayrı yükseliş dönemi var.
- **Kademeli tabloda öne çıkan hücre (ön-kayıtlı filtre değil, betimleyici):** endeks son 60 günde işlemin tersine %5'ten fazla gitmişse → D7 `125` işlem, net `-0.116 R` [-0.395, +0.153], keşif `-0.115` / doğrulama `-0.116` (long `22` işlem `+0.154`; short `103` işlem `-0.173` [-0.455, +0.109]); D6 `233` işlem, net `-0.132 R` [-0.348, +0.074], keşif `-0.090` / doğrulama `-0.207` (long `46` işlem `+0.043`; short `187` işlem `-0.175` [-0.393, +0.035]); D1 `1375` işlem, net `-0.112 R` [-0.275, +0.029], keşif `-0.079` / doğrulama `-0.178` (long `296` işlem `-0.116`; short `1079` işlem `-0.110` [-0.270, +0.037]). "Long" satırı endeksin 60 günde %5'ten fazla DÜŞTÜĞÜ, "short" satırı %5'ten fazla YÜKSELDİĞİ durumdur. Aralık sıfırı içeriyorsa kural değil, gölge deftere adaydır.
- **Duyarlılık:** girişle aynı anda kapanan endeks günü de sayılırsa `10` karar etiketi değişiyor; `GECTI` ya da `UMUT_VAR` alan varyant sayısı `0`.

## Rejim tanımları ve arşivde kapladıkları yer

| Tanım | Düşüş koşulu | Düşüş günü | Yükseliş günü | Kararsız | Geçmiş yetersiz | Ayrı düşüş dönemi | Ayrı yükseliş dönemi |
|---|---|---:|---:|---:|---:|---:|---:|
| `getiri_10` | Endeks son 10 günde ekside | 220 | 269 | 0 | 10 | 27 | 26 |
| `getiri_20` | Endeks son 20 günde ekside | 187 | 292 | 0 | 20 | 25 | 25 |
| `getiri_60` | Endeks son 60 günde ekside | 155 | 284 | 0 | 60 | 14 | 14 |
| `sma_20` | Endeks 20 günlük ortalamasının altında | 211 | 269 | 0 | 19 | 24 | 24 |
| `sma_50` | Endeks 50 günlük ortalamasının altında | 190 | 260 | 0 | 49 | 23 | 23 |
| `trend_20` | Endeks 20 günlük ortalamanın altında VE ortalama düşüyor (aksi: kararsız) | 154 | 224 | 97 | 24 | 17 | 17 |
| `ms_dis` | Endeksin günlük dış piyasa yapısı ayı (Market Structure motoru) | 24 | 257 | 218 | 0 | 1 | 3 |

## D7_A_Arti — 637 işlem

Baz: stop `44.0%`, doğrudan stop `23.7%`, 0.5 ATR görüp stop `20.3%`, net `+0.115 R`, toplam `+73.1 R`.

### 1. Rejim işlemin yönüne göre

Long işlem için düşüş rejimi "karşı", short işlem için yükseliş rejimi "karşı"dır.

**`getiri_10`** — Endeks son 10 günde ekside:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 203 | 45.3% | 21.7% | 23.6% | 49.8% | +0.031 | [-0.189, +0.258] | +0.042 (127) | +0.013 (76) |
| Endeks işlemle aynı yönde | 434 | 43.3% | 24.7% | 18.7% | 51.2% | +0.154 | [-0.019, +0.301] | +0.060 (287) | +0.337 (147) |

**`getiri_20`** — Endeks son 20 günde ekside:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 222 | 41.4% | 23.0% | 18.5% | 53.6% | +0.164 | [-0.057, +0.414] | +0.163 (133) | +0.165 (89) |
| Endeks işlemle aynı yönde | 415 | 45.3% | 24.1% | 21.2% | 49.2% | +0.088 | [-0.093, +0.233] | +0.003 (281) | +0.268 (134) |

**`getiri_60`** — Endeks son 60 günde ekside:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 202 | 47.0% | 25.2% | 21.8% | 48.5% | +0.055 | [-0.166, +0.294] | +0.152 (126) | -0.106 (76) |
| Endeks işlemle aynı yönde | 431 | 42.2% | 23.0% | 19.3% | 52.0% | +0.148 | [-0.024, +0.293] | +0.018 (284) | +0.399 (147) |
| Geçmiş yetersiz | 4 | 75.0% | 25.0% | 50.0% | 25.0% | -0.472 | [-1.163, +0.817] | -0.472 (4) | — (0) |

**`sma_20`** — Endeks 20 günlük ortalamasının altında:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 206 | 41.3% | 19.9% | 21.4% | 53.4% | +0.100 | [-0.102, +0.303] | +0.059 (120) | +0.158 (86) |
| Endeks işlemle aynı yönde | 431 | 45.2% | 25.5% | 19.7% | 49.4% | +0.122 | [-0.050, +0.280] | +0.052 (294) | +0.270 (137) |

**`sma_50`** — Endeks 50 günlük ortalamasının altında:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 207 | 37.7% | 18.4% | 19.3% | 57.5% | +0.217 | [-0.009, +0.443] | +0.096 (116) | +0.371 (91) |
| Endeks işlemle aynı yönde | 428 | 46.7% | 26.2% | 20.6% | 47.7% | +0.071 | [-0.090, +0.228] | +0.046 (296) | +0.128 (132) |
| Geçmiş yetersiz | 2 | 100.0% | 50.0% | 50.0% | 0.0% | -1.069 | [-1.071, -1.067] | -1.069 (2) | — (0) |

**`trend_20`** — Endeks 20 günlük ortalamanın altında VE ortalama düşüyor (aksi: kararsız):

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 161 | 36.0% | 16.8% | 19.3% | 57.8% | +0.244 | [+0.034, +0.491] | +0.211 (94) | +0.291 (67) |
| Endeks işlemle aynı yönde | 338 | 43.5% | 24.9% | 18.6% | 50.3% | +0.130 | [-0.086, +0.305] | +0.077 (244) | +0.267 (94) |
| Kararsız | 138 | 54.3% | 29.0% | 25.4% | 43.5% | -0.073 | [-0.374, +0.192] | -0.211 (76) | +0.097 (62) |

**`ms_dis`** — Endeksin günlük dış piyasa yapısı ayı (Market Structure motoru):

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 127 | 51.2% | 27.6% | 23.6% | 48.0% | +0.062 | [-0.243, +0.362] | -0.090 (65) | +0.221 (62) |
| Endeks işlemle aynı yönde | 216 | 38.9% | 22.7% | 16.2% | 54.6% | +0.219 | [+0.009, +0.439] | +0.213 (123) | +0.227 (93) |
| Kararsız | 294 | 44.6% | 22.8% | 21.8% | 49.0% | +0.061 | [-0.122, +0.246] | +0.010 (226) | +0.233 (68) |

### 2. Yön × rejim (ana tanım)

`getiri_20`:

| Yön / rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| long / DUSUS | 76 | 42.1% | 25.0% | 17.1% | 51.3% | +0.029 | [-0.275, +0.415] | +0.068 (39) | -0.013 (37) |
| long / YUKSELIS | 271 | 39.5% | 21.8% | 17.7% | 52.0% | +0.174 | [-0.011, +0.365] | +0.156 (209) | +0.237 (62) |
| short / DUSUS | 144 | 56.2% | 28.5% | 27.8% | 43.8% | -0.073 | [-0.442, +0.220] | -0.441 (72) | +0.295 (72) |
| short / YUKSELIS | 146 | 41.1% | 21.9% | 19.2% | 54.8% | +0.234 | [-0.022, +0.529] | +0.203 (94) | +0.292 (52) |

### 3. Filtreler

**Endeks düşüşteyken long yok** (`LONG_DUSUSTE`):

| Rejim tanımı | Elenen | Elenenin net R | Keşif (n) | Doğrulama (n) | Toplam fayda R | Fayda en kötü GA (R/işlem) | Kalan: N / net R | Elenen doğrudan stop | Elenen kazanan | Ayrı dönem (zararda) | Karar |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| `getiri_10` | 92 | -0.007 | +0.055 (39) | -0.052 (53) | +0.6 | [-0.052, +0.043] | 545 / +0.135 | 19 / 151 | 46 / 323 | 17 (9) | **GECMEDI** |
| `getiri_20` | 76 | +0.029 | +0.068 (39) | -0.013 (37) | -2.2 | [-0.044, +0.032] | 561 / +0.126 | 19 / 151 | 39 / 323 | 15 (7) | **GECMEDI** |
| `getiri_60` | 51 | +0.016 | +0.321 (26) | -0.301 (25) | -0.8 | [-0.047, +0.037] | 586 / +0.123 | 10 / 151 | 24 / 323 | 11 (7) | **GECMEDI** |
| `sma_20` | 85 | +0.003 | +0.027 (39) | -0.016 (46) | -0.3 | [-0.045, +0.038] | 552 / +0.132 | 20 / 151 | 44 / 323 | 17 (7) | **GECMEDI** |
| `sma_50` | 80 | +0.152 | +0.177 (40) | +0.128 (40) | -12.2 | [-0.068, +0.025] | 557 / +0.109 | 17 / 151 | 45 / 323 | 17 (6) | **GECMEDI** |
| `trend_20` | 57 | +0.233 | +0.475 (24) | +0.057 (33) | -13.3 | [-0.059, +0.013] | 580 / +0.103 | 12 / 151 | 33 / 323 | 12 (3) | **GECMEDI** |
| `ms_dis` | 1 | -1.047 | — (0) | -1.047 (1) | +1.1 | [+0.000, +0.006] | 636 / +0.117 | 0 / 151 | 0 / 323 | 1 (1) | **SAYILMAZ_N<30** |

**Endeks yükselişteyken short yok** (`SHORT_YUKSELISTE`):

| Rejim tanımı | Elenen | Elenenin net R | Keşif (n) | Doğrulama (n) | Toplam fayda R | Fayda en kötü GA (R/işlem) | Kalan: N / net R | Elenen doğrudan stop | Elenen kazanan | Ayrı dönem (zararda) | Karar |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| `getiri_10` | 111 | +0.063 | +0.037 (88) | +0.163 (23) | -7.0 | [-0.067, +0.051] | 526 / +0.126 | 25 / 151 | 55 / 323 | 19 (8) | **GECMEDI** |
| `getiri_20` | 146 | +0.234 | +0.203 (94) | +0.292 (52) | -34.2 | [-0.118, +0.006] | 491 / +0.079 | 32 / 151 | 80 / 323 | 17 (7) | **GECMEDI** |
| `getiri_60` | 151 | +0.068 | +0.108 (100) | -0.011 (51) | -10.2 | [-0.074, +0.048] | 486 / +0.129 | 41 / 151 | 74 / 323 | 12 (4) | **GECMEDI** |
| `sma_20` | 121 | +0.169 | +0.075 (81) | +0.358 (40) | -20.4 | [-0.084, +0.022] | 516 / +0.102 | 21 / 151 | 66 / 323 | 15 (5) | **GECMEDI** |
| `sma_50` | 127 | +0.257 | +0.053 (76) | +0.562 (51) | -32.7 | [-0.112, +0.005] | 510 / +0.079 | 21 / 151 | 74 / 323 | 15 (6) | **GECMEDI** |
| `trend_20` | 104 | +0.250 | +0.120 (70) | +0.518 (34) | -26.0 | [-0.089, +0.007] | 533 / +0.088 | 15 / 151 | 60 / 323 | 14 (4) | **GECMEDI** |
| `ms_dis` | 126 | +0.071 | -0.090 (65) | +0.242 (61) | -8.9 | [-0.077, +0.044] | 511 / +0.126 | 35 / 151 | 61 / 323 | 3 (1) | **GECMEDI** |

**Endeks rejimine karşı işlem yok (ikisi birden)** (`KARSI`):

| Rejim tanımı | Elenen | Elenenin net R | Keşif (n) | Doğrulama (n) | Toplam fayda R | Fayda en kötü GA (R/işlem) | Kalan: N / net R | Elenen doğrudan stop | Elenen kazanan | Ayrı dönem (zararda) | Karar |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| `getiri_10` | 203 | +0.031 | +0.042 (127) | +0.013 (76) | -6.4 | [-0.078, +0.056] | 434 / +0.154 | 44 / 151 | 101 / 323 | 36 (17) | **GECMEDI** |
| `getiri_20` | 222 | +0.164 | +0.163 (133) | +0.165 (89) | -36.4 | [-0.132, +0.015] | 415 / +0.088 | 51 / 151 | 119 / 323 | 32 (14) | **GECMEDI** |
| `getiri_60` | 202 | +0.055 | +0.152 (126) | -0.106 (76) | -11.1 | [-0.098, +0.051] | 435 / +0.143 | 51 / 151 | 98 / 323 | 23 (11) | **GECMEDI** |
| `sma_20` | 206 | +0.100 | +0.059 (120) | +0.158 (86) | -20.7 | [-0.098, +0.032] | 431 / +0.122 | 41 / 151 | 110 / 323 | 32 (12) | **GECMEDI** |
| `sma_50` | 207 | +0.217 | +0.096 (116) | +0.371 (91) | -44.9 | [-0.146, -0.002] | 430 / +0.066 | 38 / 151 | 119 / 323 | 32 (12) | **ZARARLI** |
| `trend_20` | 161 | +0.244 | +0.211 (94) | +0.291 (67) | -39.3 | [-0.121, -0.004] | 476 / +0.071 | 27 / 151 | 93 / 323 | 26 (7) | **ZARARLI** |
| `ms_dis` | 127 | +0.062 | -0.090 (65) | +0.221 (62) | -7.8 | [-0.074, +0.046] | 510 / +0.128 | 35 / 151 | 61 / 323 | 4 (2) | **GECMEDI** |

**Endeks düşüşteyken hiç işlem yok (long + short)** (`DUSUSTE_HIC`):

| Rejim tanımı | Elenen | Elenenin net R | Keşif (n) | Doğrulama (n) | Toplam fayda R | Fayda en kötü GA (R/işlem) | Kalan: N / net R | Elenen doğrudan stop | Elenen kazanan | Ayrı dönem (zararda) | Karar |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| `getiri_10` | 271 | +0.059 | -0.118 (117) | +0.194 (154) | -16.1 | [-0.099, +0.054] | 366 / +0.156 | 67 / 151 | 134 / 323 | 22 (12) | **GECMEDI** |
| `getiri_20` | 220 | -0.038 | -0.262 (111) | +0.190 (109) | +8.3 | [-0.049, +0.080] | 417 / +0.195 | 60 / 151 | 102 / 323 | 20 (9) | **GECMEDI** |
| `getiri_60` | 187 | +0.081 | -0.161 (89) | +0.300 (98) | -15.1 | [-0.108, +0.050] | 450 / +0.129 | 42 / 151 | 92 / 323 | 11 (6) | **GECMEDI** |
| `sma_20` | 254 | +0.014 | -0.143 (124) | +0.164 (130) | -3.6 | [-0.078, +0.070] | 383 / +0.181 | 72 / 151 | 121 / 323 | 20 (8) | **GECMEDI** |
| `sma_50` | 242 | +0.018 | -0.066 (129) | +0.114 (113) | -4.3 | [-0.078, +0.073] | 395 / +0.174 | 69 / 151 | 114 / 323 | 21 (10) | **GECMEDI** |
| `trend_20` | 161 | +0.019 | -0.163 (81) | +0.203 (80) | -3.0 | [-0.063, +0.056] | 476 / +0.147 | 48 / 151 | 76 / 323 | 15 (5) | **GECMEDI** |
| `ms_dis` | 18 | +0.187 | — (0) | +0.187 (18) | -3.4 | [-0.025, +0.011] | 619 / +0.113 | 1 / 151 | 11 / 323 | 1 (0) | **SAYILMAZ_N<30** |

### 4. Kademeli bakış: girişten önceki endeks getirisi, işlemin yönüne göre

Betimleyicidir; kademeler ön-kayıtlı filtre değildir ve kabul merdiveninden geçmez. "Ters": long için endeks düşmüş, short için yükselmiş.

Son `20` gün:

| Son 20 günde endeks | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| %5'ten fazla ters | 65 | 35.4% | 12.3% | 23.1% | 55.4% | +0.175 | [-0.152, +0.455] | +0.189 (32) | +0.163 (33) |
| %5'ten fazla ters — yalnız long | 24 | 37.5% | 16.7% | 20.8% | 45.8% | -0.020 | [-0.434, +0.441] | +0.082 (12) | -0.121 (12) |
| %5'ten fazla ters — yalnız short | 41 | 34.1% | 9.8% | 24.4% | 61.0% | +0.290 | [-0.101, +0.648] | +0.252 (20) | +0.325 (21) |
| %0–5 ters | 157 | 43.9% | 27.4% | 16.6% | 52.9% | +0.159 | [-0.114, +0.492] | +0.155 (101) | +0.166 (56) |
| %0–5 ters — yalnız long | 52 | 44.2% | 28.8% | 15.4% | 53.8% | +0.051 | [-0.329, +0.532] | +0.062 (27) | +0.039 (25) |
| %0–5 ters — yalnız short | 105 | 43.8% | 26.7% | 17.1% | 52.4% | +0.213 | [-0.166, +0.572] | +0.189 (74) | +0.269 (31) |
| %0–5 lehte | 187 | 51.3% | 23.5% | 27.8% | 47.1% | -0.012 | [-0.262, +0.245] | -0.236 (113) | +0.331 (74) |
| %0–5 lehte — yalnız long | 82 | 48.8% | 22.0% | 26.8% | 47.6% | -0.060 | [-0.358, +0.231] | -0.116 (58) | +0.076 (24) |
| %0–5 lehte — yalnız short | 105 | 53.3% | 24.8% | 28.6% | 46.7% | +0.026 | [-0.417, +0.441] | -0.363 (55) | +0.453 (50) |
| %5'ten fazla lehte | 228 | 40.4% | 24.6% | 15.8% | 50.9% | +0.170 | [-0.057, +0.380] | +0.163 (168) | +0.190 (60) |
| %5'ten fazla lehte — yalnız long | 189 | 35.4% | 21.7% | 13.8% | 54.0% | +0.276 | [+0.034, +0.494] | +0.260 (151) | +0.339 (38) |
| %5'ten fazla lehte — yalnız short | 39 | 64.1% | 38.5% | 25.6% | 35.9% | -0.340 | [-0.918, +0.108] | -0.694 (17) | -0.066 (22) |

Son `60` gün:

| Son 60 günde endeks | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| %5'ten fazla ters | 125 | 52.0% | 27.2% | 24.8% | 44.8% | -0.116 | [-0.395, +0.153] | -0.115 (78) | -0.116 (47) |
| %5'ten fazla ters — yalnız long | 22 | 36.4% | 13.6% | 22.7% | 54.5% | +0.154 | [-0.745, +0.813] | +0.165 (12) | +0.140 (10) |
| %5'ten fazla ters — yalnız short | 103 | 55.3% | 30.1% | 25.2% | 42.7% | -0.173 | [-0.455, +0.109] | -0.166 (66) | -0.186 (37) |
| %0–5 ters | 77 | 39.0% | 22.1% | 16.9% | 54.5% | +0.331 | [-0.032, +0.730] | +0.586 (48) | -0.090 (29) |
| %0–5 ters — yalnız long | 29 | 44.8% | 24.1% | 20.7% | 41.4% | -0.088 | [-0.529, +0.490] | +0.454 (14) | -0.595 (15) |
| %0–5 ters — yalnız short | 48 | 35.4% | 20.8% | 14.6% | 62.5% | +0.585 | [+0.095, +1.081] | +0.640 (34) | +0.450 (14) |
| %0–5 lehte | 124 | 45.2% | 21.0% | 24.2% | 50.0% | +0.159 | [-0.165, +0.478] | -0.230 (67) | +0.615 (57) |
| %0–5 lehte — yalnız long | 52 | 50.0% | 19.2% | 30.8% | 44.2% | -0.097 | [-0.408, +0.224] | -0.302 (26) | +0.108 (26) |
| %0–5 lehte — yalnız short | 72 | 41.7% | 22.2% | 19.4% | 54.2% | +0.343 | [-0.207, +0.814] | -0.184 (41) | +1.041 (31) |
| %5'ten fazla lehte | 307 | 41.0% | 23.8% | 17.3% | 52.8% | +0.144 | [-0.059, +0.322] | +0.095 (217) | +0.262 (90) |
| %5'ten fazla lehte — yalnız long | 243 | 37.4% | 23.5% | 14.0% | 54.7% | +0.225 | [+0.026, +0.420] | +0.183 (195) | +0.394 (48) |
| %5'ten fazla lehte — yalnız short | 64 | 54.7% | 25.0% | 29.7% | 45.3% | -0.163 | [-0.736, +0.194] | -0.689 (22) | +0.112 (42) |
| BILINMIYOR | 4 | 75.0% | 25.0% | 50.0% | 25.0% | -0.472 | [-1.163, +0.817] | -0.472 (4) | — (0) |

## D6_A_Cekirdek_Veya_Arti — 1124 işlem

Baz: stop `44.8%`, doğrudan stop `24.4%`, 0.5 ATR görüp stop `20.5%`, net `+0.061 R`, toplam `+68.7 R`.

### 1. Rejim işlemin yönüne göre

Long işlem için düşüş rejimi "karşı", short işlem için yükseliş rejimi "karşı"dır.

**`getiri_10`** — Endeks son 10 günde ekside:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 411 | 46.5% | 22.6% | 23.8% | 47.7% | -0.007 | [-0.153, +0.129] | +0.032 (265) | -0.078 (146) |
| Endeks işlemle aynı yönde | 713 | 43.9% | 25.4% | 18.5% | 48.9% | +0.101 | [-0.072, +0.239] | +0.015 (473) | +0.269 (240) |

**`getiri_20`** — Endeks son 20 günde ekside:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 419 | 44.4% | 25.1% | 19.3% | 48.2% | +0.053 | [-0.141, +0.261] | +0.050 (257) | +0.058 (162) |
| Endeks işlemle aynı yönde | 705 | 45.1% | 24.0% | 21.1% | 48.7% | +0.066 | [-0.107, +0.193] | +0.006 (481) | +0.195 (224) |

**`getiri_60`** — Endeks son 60 günde ekside:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 384 | 48.7% | 26.0% | 22.7% | 45.6% | -0.030 | [-0.229, +0.176] | +0.062 (246) | -0.195 (138) |
| Endeks işlemle aynı yönde | 735 | 42.7% | 23.5% | 19.2% | 50.1% | +0.111 | [-0.061, +0.267] | +0.003 (487) | +0.323 (248) |
| Geçmiş yetersiz | 5 | 60.0% | 20.0% | 40.0% | 40.0% | -0.234 | [-1.163, +0.774] | -0.234 (5) | — (0) |

**`sma_20`** — Endeks 20 günlük ortalamasının altında:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 393 | 43.3% | 21.9% | 21.4% | 49.9% | +0.057 | [-0.124, +0.229] | +0.046 (245) | +0.076 (148) |
| Endeks işlemle aynı yönde | 731 | 45.7% | 25.7% | 20.0% | 47.7% | +0.063 | [-0.119, +0.201] | +0.009 (493) | +0.177 (238) |

**`sma_50`** — Endeks 50 günlük ortalamasının altında:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 394 | 40.1% | 19.5% | 20.6% | 53.3% | +0.134 | [-0.068, +0.323] | +0.039 (237) | +0.276 (157) |
| Endeks işlemle aynı yönde | 728 | 47.3% | 26.9% | 20.3% | 46.0% | +0.025 | [-0.128, +0.162] | +0.017 (499) | +0.043 (229) |
| Geçmiş yetersiz | 2 | 100.0% | 50.0% | 50.0% | 0.0% | -1.069 | [-1.071, -1.067] | -1.069 (2) | — (0) |

**`trend_20`** — Endeks 20 günlük ortalamanın altında VE ortalama düşüyor (aksi: kararsız):

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 323 | 42.1% | 21.7% | 20.4% | 50.2% | +0.100 | [-0.088, +0.298] | +0.102 (206) | +0.097 (117) |
| Endeks işlemle aynı yönde | 579 | 43.7% | 25.0% | 18.7% | 48.9% | +0.087 | [-0.122, +0.241] | +0.045 (412) | +0.193 (167) |
| Kararsız | 222 | 51.8% | 26.6% | 25.2% | 45.0% | -0.064 | [-0.310, +0.163] | -0.199 (120) | +0.095 (102) |

**`ms_dis`** — Endeksin günlük dış piyasa yapısı ayı (Market Structure motoru):

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 208 | 51.4% | 28.8% | 22.6% | 44.7% | -0.019 | [-0.275, +0.203] | -0.069 (104) | +0.031 (104) |
| Endeks işlemle aynı yönde | 391 | 41.7% | 22.8% | 18.9% | 50.6% | +0.128 | [-0.046, +0.285] | +0.131 (219) | +0.126 (172) |
| Kararsız | 525 | 44.6% | 23.8% | 20.8% | 48.4% | +0.043 | [-0.127, +0.204] | -0.014 (415) | +0.258 (110) |

### 2. Yön × rejim (ana tanım)

`getiri_20`:

| Yön / rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| long / DUSUS | 159 | 42.8% | 23.9% | 18.9% | 49.1% | +0.048 | [-0.219, +0.303] | +0.118 (88) | -0.038 (71) |
| long / YUKSELIS | 482 | 42.5% | 22.8% | 19.7% | 49.4% | +0.090 | [-0.119, +0.226] | +0.098 (363) | +0.063 (119) |
| short / DUSUS | 223 | 50.7% | 26.5% | 24.2% | 47.1% | +0.015 | [-0.294, +0.277] | -0.279 (118) | +0.345 (105) |
| short / YUKSELIS | 260 | 45.4% | 25.8% | 19.6% | 47.7% | +0.056 | [-0.178, +0.317] | +0.014 (169) | +0.133 (91) |

### 3. Filtreler

**Endeks düşüşteyken long yok** (`LONG_DUSUSTE`):

| Rejim tanımı | Elenen | Elenenin net R | Keşif (n) | Doğrulama (n) | Toplam fayda R | Fayda en kötü GA (R/işlem) | Kalan: N / net R | Elenen doğrudan stop | Elenen kazanan | Ayrı dönem (zararda) | Karar |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| `getiri_10` | 195 | -0.009 | +0.086 (97) | -0.103 (98) | +1.8 | [-0.041, +0.039] | 929 / +0.076 | 40 / 274 | 93 / 545 | 21 (11) | **GECMEDI** |
| `getiri_20` | 159 | +0.048 | +0.118 (88) | -0.038 (71) | -7.7 | [-0.045, +0.028] | 965 / +0.063 | 38 / 274 | 78 / 545 | 20 (9) | **GECMEDI** |
| `getiri_60` | 119 | +0.043 | +0.222 (70) | -0.213 (49) | -5.1 | [-0.038, +0.026] | 1005 / +0.063 | 23 / 274 | 57 / 545 | 13 (8) | **GECMEDI** |
| `sma_20` | 171 | +0.073 | +0.147 (90) | -0.008 (81) | -12.5 | [-0.051, +0.024] | 953 / +0.059 | 36 / 274 | 88 / 545 | 19 (8) | **GECMEDI** |
| `sma_50` | 163 | +0.164 | +0.192 (92) | +0.127 (71) | -26.7 | [-0.064, +0.013] | 961 / +0.044 | 30 / 274 | 89 / 545 | 20 (7) | **GECMEDI** |
| `trend_20` | 125 | +0.186 | +0.365 (67) | -0.020 (58) | -23.3 | [-0.058, +0.010] | 999 / +0.045 | 26 / 274 | 67 / 545 | 15 (5) | **GECMEDI** |
| `ms_dis` | 4 | -1.101 | — (0) | -1.101 (4) | +4.4 | [+0.000, +0.011] | 1120 / +0.065 | 2 / 274 | 0 / 545 | 1 (1) | **SAYILMAZ_N<30** |

**Endeks yükselişteyken short yok** (`SHORT_YUKSELISTE`):

| Rejim tanımı | Elenen | Elenenin net R | Keşif (n) | Doğrulama (n) | Toplam fayda R | Fayda en kötü GA (R/işlem) | Kalan: N / net R | Elenen doğrudan stop | Elenen kazanan | Ayrı dönem (zararda) | Karar |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| `getiri_10` | 216 | -0.006 | +0.001 (168) | -0.027 (48) | +1.2 | [-0.044, +0.049] | 908 / +0.077 | 53 / 274 | 103 / 545 | 21 (12) | **GECMEDI** |
| `getiri_20` | 260 | +0.056 | +0.014 (169) | +0.133 (91) | -14.6 | [-0.072, +0.043] | 864 / +0.063 | 67 / 274 | 124 / 545 | 19 (11) | **GECMEDI** |
| `getiri_60` | 265 | -0.063 | -0.001 (176) | -0.185 (89) | +16.6 | [-0.031, +0.060] | 859 / +0.099 | 77 / 274 | 118 / 545 | 12 (4) | **ZAYIF_ARTI** |
| `sma_20` | 222 | +0.044 | -0.013 (155) | +0.177 (67) | -9.8 | [-0.052, +0.035] | 902 / +0.065 | 50 / 274 | 108 / 545 | 16 (8) | **GECMEDI** |
| `sma_50` | 231 | +0.112 | -0.058 (145) | +0.399 (86) | -26.0 | [-0.077, +0.030] | 893 / +0.048 | 47 / 274 | 121 / 545 | 18 (9) | **GECMEDI** |
| `trend_20` | 198 | +0.046 | -0.025 (139) | +0.212 (59) | -9.0 | [-0.051, +0.031] | 926 / +0.064 | 44 / 274 | 95 / 545 | 15 (6) | **GECMEDI** |
| `ms_dis` | 204 | +0.002 | -0.069 (104) | +0.076 (100) | -0.4 | [-0.046, +0.041] | 920 / +0.074 | 58 / 274 | 93 / 545 | 3 (1) | **GECMEDI** |

**Endeks rejimine karşı işlem yok (ikisi birden)** (`KARSI`):

| Rejim tanımı | Elenen | Elenenin net R | Keşif (n) | Doğrulama (n) | Toplam fayda R | Fayda en kötü GA (R/işlem) | Kalan: N / net R | Elenen doğrudan stop | Elenen kazanan | Ayrı dönem (zararda) | Karar |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| `getiri_10` | 411 | -0.007 | +0.032 (265) | -0.078 (146) | +3.0 | [-0.050, +0.054] | 713 / +0.101 | 93 / 274 | 196 / 545 | 42 (23) | **GECMEDI** |
| `getiri_20` | 419 | +0.053 | +0.050 (257) | +0.058 (162) | -22.2 | [-0.095, +0.053] | 705 / +0.066 | 105 / 274 | 202 / 545 | 39 (20) | **GECMEDI** |
| `getiri_60` | 384 | -0.030 | +0.062 (246) | -0.195 (138) | +11.6 | [-0.056, +0.072] | 740 / +0.108 | 100 / 274 | 175 / 545 | 25 (12) | **GECMEDI** |
| `sma_20` | 393 | +0.057 | +0.046 (245) | +0.076 (148) | -22.4 | [-0.084, +0.040] | 731 / +0.063 | 86 / 274 | 196 / 545 | 35 (16) | **GECMEDI** |
| `sma_50` | 394 | +0.134 | +0.039 (237) | +0.276 (157) | -52.7 | [-0.108, +0.020] | 730 / +0.022 | 77 / 274 | 210 / 545 | 38 (16) | **GECMEDI** |
| `trend_20` | 323 | +0.100 | +0.102 (206) | +0.097 (117) | -32.3 | [-0.089, +0.026] | 801 / +0.045 | 70 / 274 | 162 / 545 | 30 (11) | **GECMEDI** |
| `ms_dis` | 208 | -0.019 | -0.069 (104) | +0.031 (104) | +4.0 | [-0.043, +0.046] | 916 / +0.079 | 60 / 274 | 93 / 545 | 4 (2) | **GECMEDI** |

**Endeks düşüşteyken hiç işlem yok (long + short)** (`DUSUSTE_HIC`):

| Rejim tanımı | Elenen | Elenenin net R | Keşif (n) | Doğrulama (n) | Toplam fayda R | Fayda en kötü GA (R/işlem) | Kalan: N / net R | Elenen doğrudan stop | Elenen kazanan | Ayrı dönem (zararda) | Karar |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| `getiri_10` | 462 | +0.037 | -0.103 (216) | +0.161 (246) | -17.2 | [-0.094, +0.056] | 662 / +0.078 | 113 / 274 | 219 / 545 | 23 (11) | **GECMEDI** |
| `getiri_20` | 382 | +0.029 | -0.110 (206) | +0.190 (176) | -10.9 | [-0.065, +0.044] | 742 / +0.078 | 97 / 274 | 183 / 545 | 21 (10) | **GECMEDI** |
| `getiri_60` | 333 | +0.119 | -0.083 (177) | +0.348 (156) | -39.6 | [-0.116, +0.035] | 791 / +0.037 | 72 / 274 | 166 / 545 | 13 (7) | **GECMEDI** |
| `sma_20` | 432 | +0.048 | -0.069 (222) | +0.171 (210) | -20.6 | [-0.083, +0.044] | 692 / +0.070 | 112 / 274 | 209 / 545 | 20 (9) | **GECMEDI** |
| `sma_50` | 414 | +0.047 | -0.015 (233) | +0.127 (181) | -19.7 | [-0.073, +0.040] | 710 / +0.069 | 109 / 274 | 197 / 545 | 21 (12) | **GECMEDI** |
| `trend_20` | 292 | +0.061 | -0.029 (158) | +0.166 (134) | -17.8 | [-0.064, +0.035] | 832 / +0.061 | 78 / 274 | 140 / 545 | 15 (5) | **GECMEDI** |
| `ms_dis` | 34 | +0.179 | — (0) | +0.179 (34) | -6.1 | [-0.026, +0.011] | 1090 / +0.057 | 4 / 274 | 18 / 545 | 1 (0) | **GECMEDI** |

### 4. Kademeli bakış: girişten önceki endeks getirisi, işlemin yönüne göre

Betimleyicidir; kademeler ön-kayıtlı filtre değildir ve kabul merdiveninden geçmez. "Ters": long için endeks düşmüş, short için yükselmiş.

Son `20` gün:

| Son 20 günde endeks | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| %5'ten fazla ters | 143 | 46.9% | 24.5% | 22.4% | 44.1% | -0.032 | [-0.302, +0.191] | -0.003 (82) | -0.071 (61) |
| %5'ten fazla ters — yalnız long | 59 | 47.5% | 22.0% | 25.4% | 42.4% | -0.016 | [-0.471, +0.400] | +0.201 (36) | -0.356 (23) |
| %5'ten fazla ters — yalnız short | 84 | 46.4% | 26.2% | 20.2% | 45.2% | -0.044 | [-0.419, +0.278] | -0.163 (46) | +0.101 (38) |
| %0–5 ters | 276 | 43.1% | 25.4% | 17.8% | 50.4% | +0.097 | [-0.170, +0.392] | +0.075 (175) | +0.137 (101) |
| %0–5 ters — yalnız long | 100 | 40.0% | 25.0% | 15.0% | 53.0% | +0.086 | [-0.262, +0.365] | +0.061 (52) | +0.114 (48) |
| %0–5 ters — yalnız short | 176 | 44.9% | 25.6% | 19.3% | 48.9% | +0.103 | [-0.242, +0.458] | +0.081 (123) | +0.157 (53) |
| %0–5 lehte | 311 | 49.8% | 22.8% | 27.0% | 46.9% | -0.028 | [-0.231, +0.190] | -0.193 (196) | +0.252 (115) |
| %0–5 lehte — yalnız long | 161 | 50.9% | 23.0% | 28.0% | 44.1% | -0.131 | [-0.344, +0.068] | -0.162 (114) | -0.057 (47) |
| %0–5 lehte — yalnız short | 150 | 48.7% | 22.7% | 26.0% | 50.0% | +0.082 | [-0.295, +0.419] | -0.236 (82) | +0.466 (68) |
| %5'ten fazla lehte | 394 | 41.4% | 24.9% | 16.5% | 50.0% | +0.140 | [-0.087, +0.305] | +0.142 (285) | +0.135 (109) |
| %5'ten fazla lehte — yalnız long | 321 | 38.3% | 22.7% | 15.6% | 52.0% | +0.200 | [-0.025, +0.391] | +0.217 (249) | +0.142 (72) |
| %5'ten fazla lehte — yalnız short | 73 | 54.8% | 34.2% | 20.5% | 41.1% | -0.124 | [-0.608, +0.335] | -0.379 (36) | +0.123 (37) |

Son `60` gün:

| Son 60 günde endeks | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| %5'ten fazla ters | 233 | 51.1% | 29.2% | 21.9% | 42.9% | -0.132 | [-0.348, +0.074] | -0.090 (150) | -0.207 (83) |
| %5'ten fazla ters — yalnız long | 46 | 43.5% | 19.6% | 23.9% | 50.0% | +0.043 | [-0.622, +0.467] | +0.008 (26) | +0.088 (20) |
| %5'ten fazla ters — yalnız short | 187 | 52.9% | 31.6% | 21.4% | 41.2% | -0.175 | [-0.393, +0.035] | -0.110 (124) | -0.301 (63) |
| %0–5 ters | 151 | 45.0% | 21.2% | 23.8% | 49.7% | +0.126 | [-0.176, +0.449] | +0.299 (96) | -0.176 (55) |
| %0–5 ters — yalnız long | 73 | 45.2% | 19.2% | 26.0% | 46.6% | +0.042 | [-0.481, +0.401] | +0.347 (44) | -0.421 (29) |
| %0–5 ters — yalnız short | 78 | 44.9% | 23.1% | 21.8% | 52.6% | +0.205 | [-0.252, +0.623] | +0.259 (52) | +0.098 (26) |
| %0–5 lehte | 206 | 45.1% | 24.3% | 20.9% | 48.1% | +0.124 | [-0.262, +0.469] | -0.253 (111) | +0.565 (95) |
| %0–5 lehte — yalnız long | 94 | 48.9% | 24.5% | 24.5% | 42.6% | -0.107 | [-0.400, +0.137] | -0.326 (44) | +0.086 (50) |
| %0–5 lehte — yalnız short | 112 | 42.0% | 24.1% | 17.9% | 52.7% | +0.318 | [-0.266, +0.835] | -0.205 (67) | +1.098 (45) |
| %5'ten fazla lehte | 529 | 41.8% | 23.3% | 18.5% | 50.9% | +0.106 | [-0.072, +0.248] | +0.078 (376) | +0.172 (153) |
| %5'ten fazla lehte — yalnız long | 427 | 40.5% | 23.7% | 16.9% | 51.3% | +0.133 | [-0.064, +0.283] | +0.137 (336) | +0.120 (91) |
| %5'ten fazla lehte — yalnız short | 102 | 47.1% | 21.6% | 25.5% | 49.0% | -0.010 | [-0.408, +0.332] | -0.411 (40) | +0.248 (62) |
| BILINMIYOR | 5 | 60.0% | 20.0% | 40.0% | 40.0% | -0.234 | [-1.163, +0.774] | -0.234 (5) | — (0) |

## D1_Birincil — 4233 işlem

Baz: stop `51.0%`, doğrudan stop `30.9%`, 0.5 ATR görüp stop `20.1%`, net `+0.010 R`, toplam `+42.3 R`.

### 1. Rejim işlemin yönüne göre

Long işlem için düşüş rejimi "karşı", short işlem için yükseliş rejimi "karşı"dır.

**`getiri_10`** — Endeks son 10 günde ekside:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 2113 | 52.8% | 31.0% | 21.8% | 41.0% | -0.043 | [-0.152, +0.064] | -0.001 (1378) | -0.122 (735) |
| Endeks işlemle aynı yönde | 2120 | 49.2% | 30.8% | 18.4% | 44.9% | +0.063 | [-0.091, +0.218] | -0.018 (1345) | +0.204 (775) |

**`getiri_20`** — Endeks son 20 günde ekside:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 2170 | 52.1% | 32.0% | 20.1% | 41.6% | -0.016 | [-0.148, +0.117] | -0.026 (1377) | +0.002 (793) |
| Endeks işlemle aynı yönde | 2063 | 49.8% | 29.7% | 20.1% | 44.4% | +0.037 | [-0.088, +0.154] | +0.007 (1346) | +0.094 (717) |

**`getiri_60`** — Endeks son 60 günde ekside:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 2002 | 53.8% | 32.0% | 21.8% | 40.6% | -0.052 | [-0.192, +0.073] | -0.007 (1310) | -0.138 (692) |
| Endeks işlemle aynı yönde | 2179 | 48.2% | 29.6% | 18.6% | 45.2% | +0.068 | [-0.074, +0.214] | -0.012 (1361) | +0.201 (818) |
| Geçmiş yetersiz | 52 | 57.7% | 40.4% | 17.3% | 40.4% | -0.035 | [-1.098, +0.401] | -0.035 (52) | — (0) |

**`sma_20`** — Endeks 20 günlük ortalamasının altında:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 2108 | 52.4% | 31.5% | 20.8% | 41.5% | -0.029 | [-0.153, +0.083] | -0.003 (1325) | -0.073 (783) |
| Endeks işlemle aynı yönde | 2125 | 49.6% | 30.2% | 19.4% | 44.4% | +0.049 | [-0.089, +0.168] | -0.016 (1398) | +0.173 (727) |

**`sma_50`** — Endeks 50 günlük ortalamasının altında:

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 2126 | 50.5% | 30.4% | 20.1% | 43.4% | +0.026 | [-0.109, +0.151] | -0.016 (1324) | +0.097 (802) |
| Endeks işlemle aynı yönde | 2090 | 51.5% | 31.3% | 20.2% | 42.4% | -0.007 | [-0.122, +0.122] | -0.005 (1382) | -0.013 (708) |
| Geçmiş yetersiz | 17 | 52.9% | 41.2% | 11.8% | 47.1% | +0.108 | [-1.098, +1.131] | +0.108 (17) | — (0) |

**`trend_20`** — Endeks 20 günlük ortalamanın altında VE ortalama düşüyor (aksi: kararsız):

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 1759 | 51.9% | 30.8% | 21.1% | 41.5% | -0.010 | [-0.144, +0.118] | -0.010 (1138) | -0.009 (621) |
| Endeks işlemle aynı yönde | 1625 | 48.7% | 29.5% | 19.1% | 45.5% | +0.068 | [-0.076, +0.194] | +0.027 (1099) | +0.155 (526) |
| Kararsız | 849 | 53.5% | 33.7% | 19.8% | 41.1% | -0.060 | [-0.235, +0.124] | -0.091 (486) | -0.019 (363) |

**`ms_dis`** — Endeksin günlük dış piyasa yapısı ayı (Market Structure motoru):

| Rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Endeks işleme karşı | 1040 | 55.2% | 33.8% | 21.3% | 39.3% | -0.060 | [-0.254, +0.119] | -0.068 (536) | -0.051 (504) |
| Endeks işlemle aynı yönde | 1123 | 48.3% | 29.8% | 18.4% | 44.4% | +0.058 | [-0.065, +0.196] | +0.039 (547) | +0.075 (576) |
| Kararsız | 2070 | 50.3% | 30.0% | 20.4% | 44.0% | +0.019 | [-0.083, +0.142] | -0.007 (1640) | +0.118 (430) |

### 2. Yön × rejim (ana tanım)

`getiri_20`:

| Yön / rejim | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| long / DUSUS | 814 | 50.9% | 31.1% | 19.8% | 39.8% | -0.068 | [-0.253, +0.114] | +0.082 (427) | -0.235 (387) |
| long / YUKSELIS | 1364 | 47.7% | 27.9% | 19.8% | 45.7% | +0.057 | [-0.097, +0.186] | +0.112 (944) | -0.066 (420) |
| short / DUSUS | 699 | 53.9% | 33.2% | 20.7% | 41.8% | -0.003 | [-0.262, +0.228] | -0.240 (402) | +0.319 (297) |
| short / YUKSELIS | 1356 | 52.8% | 32.5% | 20.3% | 42.7% | +0.016 | [-0.157, +0.243] | -0.074 (950) | +0.227 (406) |

### 3. Filtreler

**Endeks düşüşteyken long yok** (`LONG_DUSUSTE`):

| Rejim tanımı | Elenen | Elenenin net R | Keşif (n) | Doğrulama (n) | Toplam fayda R | Fayda en kötü GA (R/işlem) | Kalan: N / net R | Elenen doğrudan stop | Elenen kazanan | Ayrı dönem (zararda) | Karar |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| `getiri_10` | 941 | -0.079 | +0.124 (476) | -0.287 (465) | +74.7 | [-0.019, +0.056] | 3292 / +0.036 | 273 / 1307 | 377 / 1818 | 25 (12) | **GECMEDI** |
| `getiri_20` | 814 | -0.068 | +0.082 (427) | -0.235 (387) | +55.6 | [-0.021, +0.047] | 3419 / +0.029 | 253 / 1307 | 324 / 1818 | 23 (11) | **GECMEDI** |
| `getiri_60` | 595 | +0.010 | +0.284 (336) | -0.347 (259) | -5.7 | [-0.039, +0.033] | 3638 / +0.010 | 158 / 1307 | 259 / 1818 | 13 (7) | **GECMEDI** |
| `sma_20` | 868 | -0.077 | +0.077 (435) | -0.232 (433) | +67.1 | [-0.018, +0.051] | 3365 / +0.033 | 264 / 1307 | 345 / 1818 | 22 (10) | **GECMEDI** |
| `sma_50` | 834 | -0.009 | +0.118 (433) | -0.146 (401) | +7.3 | [-0.030, +0.035] | 3399 / +0.015 | 238 / 1307 | 356 / 1818 | 23 (10) | **GECMEDI** |
| `trend_20` | 674 | -0.051 | +0.157 (349) | -0.273 (325) | +34.1 | [-0.025, +0.042] | 3559 / +0.021 | 204 / 1307 | 269 / 1818 | 17 (7) | **GECMEDI** |
| `ms_dis` | 84 | -0.685 | — (0) | -0.685 (84) | +57.5 | [+0.000, +0.036] | 4149 / +0.024 | 28 / 1307 | 14 / 1818 | 1 (1) | **GECMEDI** |

**Endeks yükselişteyken short yok** (`SHORT_YUKSELISTE`):

| Rejim tanımı | Elenen | Elenenin net R | Keşif (n) | Doğrulama (n) | Toplam fayda R | Fayda en kötü GA (R/işlem) | Kalan: N / net R | Elenen doğrudan stop | Elenen kazanan | Ayrı dönem (zararda) | Karar |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| `getiri_10` | 1172 | -0.015 | -0.068 (902) | +0.162 (270) | +17.2 | [-0.041, +0.045] | 3061 / +0.019 | 382 / 1307 | 490 / 1818 | 24 (9) | **GECMEDI** |
| `getiri_20` | 1356 | +0.016 | -0.074 (950) | +0.227 (406) | -21.5 | [-0.067, +0.054] | 2877 / +0.007 | 441 / 1307 | 579 / 1818 | 25 (12) | **GECMEDI** |
| `getiri_60` | 1407 | -0.078 | -0.107 (974) | -0.013 (433) | +109.9 | [-0.022, +0.072] | 2826 / +0.054 | 483 / 1307 | 554 / 1818 | 13 (8) | **ZAYIF_ARTI** |
| `sma_20` | 1240 | +0.005 | -0.042 (890) | +0.125 (350) | -5.8 | [-0.054, +0.050] | 2993 / +0.012 | 401 / 1307 | 529 / 1818 | 22 (9) | **GECMEDI** |
| `sma_50` | 1292 | +0.049 | -0.082 (891) | +0.339 (401) | -63.3 | [-0.076, +0.042] | 2941 / -0.007 | 408 / 1307 | 567 / 1818 | 21 (10) | **GECMEDI** |
| `trend_20` | 1085 | +0.015 | -0.084 (789) | +0.281 (296) | -16.5 | [-0.050, +0.039] | 3148 / +0.008 | 337 / 1307 | 461 / 1818 | 17 (4) | **GECMEDI** |
| `ms_dis` | 956 | -0.005 | -0.068 (536) | +0.076 (420) | +4.7 | [-0.045, +0.040] | 3277 / +0.014 | 324 / 1307 | 395 / 1818 | 3 (2) | **GECMEDI** |

**Endeks rejimine karşı işlem yok (ikisi birden)** (`KARSI`):

| Rejim tanımı | Elenen | Elenenin net R | Keşif (n) | Doğrulama (n) | Toplam fayda R | Fayda en kötü GA (R/işlem) | Kalan: N / net R | Elenen doğrudan stop | Elenen kazanan | Ayrı dönem (zararda) | Karar |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| `getiri_10` | 2113 | -0.043 | -0.001 (1378) | -0.122 (735) | +91.9 | [-0.031, +0.071] | 2120 / +0.063 | 655 / 1307 | 867 / 1818 | 49 (21) | **ZAYIF_ARTI** |
| `getiri_20` | 2170 | -0.016 | -0.026 (1377) | +0.002 (793) | +34.2 | [-0.067, +0.078] | 2063 / +0.037 | 694 / 1307 | 903 / 1818 | 48 (23) | **GECMEDI** |
| `getiri_60` | 2002 | -0.052 | -0.007 (1310) | -0.138 (692) | +104.3 | [-0.037, +0.082] | 2231 / +0.066 | 641 / 1307 | 813 / 1818 | 26 (15) | **ZAYIF_ARTI** |
| `sma_20` | 2108 | -0.029 | -0.003 (1325) | -0.073 (783) | +61.3 | [-0.047, +0.073] | 2125 / +0.049 | 665 / 1307 | 874 / 1818 | 44 (19) | **ZAYIF_ARTI** |
| `sma_50` | 2126 | +0.026 | -0.016 (1324) | +0.097 (802) | -56.0 | [-0.079, +0.046] | 2107 / -0.007 | 646 / 1307 | 923 / 1818 | 44 (20) | **GECMEDI** |
| `trend_20` | 1759 | -0.010 | -0.010 (1138) | -0.009 (621) | +17.7 | [-0.059, +0.057] | 2474 / +0.024 | 541 / 1307 | 730 / 1818 | 34 (11) | **ZAYIF_ARTI** |
| `ms_dis` | 1040 | -0.060 | -0.068 (536) | -0.051 (504) | +62.2 | [-0.030, +0.059] | 3193 / +0.033 | 352 / 1307 | 409 / 1818 | 4 (3) | **ZAYIF_ARTI** |

**Endeks düşüşteyken hiç işlem yok (long + short)** (`DUSUSTE_HIC`):

| Rejim tanımı | Elenen | Elenenin net R | Keşif (n) | Doğrulama (n) | Toplam fayda R | Fayda en kötü GA (R/işlem) | Kalan: N / net R | Elenen doğrudan stop | Elenen kazanan | Ayrı dönem (zararda) | Karar |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| `getiri_10` | 1824 | -0.021 | -0.051 (926) | +0.011 (898) | +37.9 | [-0.053, +0.062] | 2409 / +0.033 | 564 / 1307 | 758 / 1818 | 25 (14) | **GECMEDI** |
| `getiri_20` | 1513 | -0.038 | -0.074 (829) | +0.006 (684) | +57.4 | [-0.028, +0.058] | 2720 / +0.037 | 485 / 1307 | 616 / 1818 | 24 (12) | **GECMEDI** |
| `getiri_60` | 1206 | +0.113 | +0.050 (677) | +0.194 (529) | -136.5 | [-0.091, +0.020] | 3027 / -0.031 | 334 / 1307 | 560 / 1818 | 13 (6) | **GECMEDI** |
| `sma_20` | 1683 | -0.032 | -0.107 (897) | +0.054 (786) | +53.3 | [-0.036, +0.062] | 2550 / +0.037 | 536 / 1307 | 687 / 1818 | 22 (14) | **GECMEDI** |
| `sma_50` | 1585 | -0.035 | -0.055 (882) | -0.011 (703) | +56.2 | [-0.031, +0.059] | 2648 / +0.037 | 500 / 1307 | 653 / 1818 | 23 (13) | **ZAYIF_ARTI** |
| `trend_20` | 1185 | -0.036 | -0.081 (641) | +0.016 (544) | +43.0 | [-0.028, +0.049] | 3048 / +0.028 | 380 / 1307 | 476 / 1818 | 17 (8) | **GECMEDI** |
| `ms_dis` | 155 | +0.005 | — (0) | +0.005 (155) | -0.8 | [-0.016, +0.016] | 4078 / +0.010 | 34 / 1307 | 61 / 1818 | 1 (0) | **GECMEDI** |

### 4. Kademeli bakış: girişten önceki endeks getirisi, işlemin yönüne göre

Betimleyicidir; kademeler ön-kayıtlı filtre değildir ve kabul merdiveninden geçmez. "Ters": long için endeks düşmüş, short için yükselmiş.

Son `20` gün:

| Son 20 günde endeks | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| %5'ten fazla ters | 1020 | 52.9% | 31.8% | 21.2% | 39.4% | -0.055 | [-0.208, +0.105] | -0.064 (645) | -0.037 (375) |
| %5'ten fazla ters — yalnız long | 366 | 51.9% | 30.1% | 21.9% | 36.1% | -0.145 | [-0.424, +0.094] | +0.050 (185) | -0.344 (181) |
| %5'ten fazla ters — yalnız short | 654 | 53.5% | 32.7% | 20.8% | 41.3% | -0.004 | [-0.227, +0.221] | -0.111 (460) | +0.249 (194) |
| %0–5 ters | 1150 | 51.3% | 32.2% | 19.1% | 43.6% | +0.019 | [-0.188, +0.222] | +0.008 (732) | +0.037 (418) |
| %0–5 ters — yalnız long | 448 | 50.0% | 31.9% | 18.1% | 42.9% | -0.006 | [-0.248, +0.207] | +0.107 (242) | -0.139 (206) |
| %0–5 ters — yalnız short | 702 | 52.1% | 32.3% | 19.8% | 44.0% | +0.034 | [-0.230, +0.352] | -0.040 (490) | +0.207 (212) |
| %0–5 lehte | 1118 | 52.8% | 31.0% | 21.7% | 41.8% | -0.038 | [-0.191, +0.127] | -0.085 (704) | +0.041 (414) |
| %0–5 lehte — yalnız long | 638 | 51.1% | 29.5% | 21.6% | 42.3% | -0.041 | [-0.228, +0.171] | +0.018 (417) | -0.152 (221) |
| %0–5 lehte — yalnız short | 480 | 55.0% | 33.1% | 21.9% | 41.0% | -0.034 | [-0.315, +0.231] | -0.233 (287) | +0.263 (193) |
| %5'ten fazla lehte | 945 | 46.3% | 28.1% | 18.2% | 47.4% | +0.126 | [-0.061, +0.271] | +0.107 (642) | +0.165 (303) |
| %5'ten fazla lehte — yalnız long | 726 | 44.8% | 26.6% | 18.2% | 48.6% | +0.144 | [+0.003, +0.263] | +0.187 (527) | +0.030 (199) |
| %5'ten fazla lehte — yalnız short | 219 | 51.6% | 33.3% | 18.3% | 43.4% | +0.066 | [-0.372, +0.616] | -0.257 (115) | +0.424 (104) |

Son `60` gün:

| Son 60 günde endeks | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| %5'ten fazla ters | 1375 | 56.1% | 33.5% | 22.6% | 38.5% | -0.112 | [-0.275, +0.029] | -0.079 (921) | -0.178 (454) |
| %5'ten fazla ters — yalnız long | 296 | 52.4% | 28.4% | 24.0% | 38.9% | -0.116 | [-0.479, +0.230] | +0.109 (132) | -0.298 (164) |
| %5'ten fazla ters — yalnız short | 1079 | 57.1% | 34.8% | 22.2% | 38.4% | -0.110 | [-0.270, +0.037] | -0.110 (789) | -0.111 (290) |
| %0–5 ters | 627 | 48.8% | 28.9% | 19.9% | 45.3% | +0.078 | [-0.109, +0.278] | +0.164 (389) | -0.061 (238) |
| %0–5 ters — yalnız long | 299 | 43.8% | 24.7% | 19.1% | 48.2% | +0.134 | [-0.263, +0.483] | +0.398 (204) | -0.432 (95) |
| %0–5 ters — yalnız short | 328 | 53.4% | 32.6% | 20.7% | 42.7% | +0.027 | [-0.241, +0.307] | -0.095 (185) | +0.185 (143) |
| %0–5 lehte | 751 | 49.9% | 30.0% | 20.0% | 44.5% | +0.075 | [-0.196, +0.348] | -0.087 (447) | +0.313 (304) |
| %0–5 lehte — yalnız long | 387 | 54.8% | 30.7% | 24.0% | 38.8% | -0.127 | [-0.363, +0.111] | -0.079 (209) | -0.184 (178) |
| %0–5 lehte — yalnız short | 364 | 44.8% | 29.1% | 15.7% | 50.5% | +0.290 | [-0.167, +0.777] | -0.093 (238) | +1.015 (126) |
| %5'ten fazla lehte | 1428 | 47.3% | 29.4% | 17.9% | 45.5% | +0.064 | [-0.071, +0.190] | +0.025 (914) | +0.134 (514) |
| %5'ten fazla lehte — yalnız long | 1181 | 47.2% | 29.6% | 17.5% | 45.1% | +0.057 | [-0.081, +0.173] | +0.077 (811) | +0.011 (370) |
| %5'ten fazla lehte — yalnız short | 247 | 48.2% | 28.3% | 19.8% | 47.4% | +0.102 | [-0.321, +0.484] | -0.384 (103) | +0.450 (144) |
| BILINMIYOR | 52 | 57.7% | 40.4% | 17.3% | 40.4% | -0.035 | [-1.098, +0.401] | -0.035 (52) | — (0) |
