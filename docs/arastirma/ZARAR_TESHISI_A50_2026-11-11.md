# FAZ8 A50 — Zarar Teşhisi (kova × domain × kvadrant)

*Veri: plan_sonuc.csv + FAZ8 defteri (yeniden koşu) + arşiv kapanışı · n=412 plan, 132 stop, 143 zaman, 137 hedef*

## 1) Kova profilleri (ana_kova bazında)

| kova | n | kv erken/iyi/geç/yüksekten | stop hızı (bar) | MAE ort | düşüş ort | dipKaçış ort | R ort | dönem baskın | onaysız n |
|---|---|---|---|---|---|---|---|---|---|
| kâr | 237 | 13/200/24/0 | 6.9 | -0.2 | 0.31 | 0.49 | 3.96 | kesif | 0 |
| zarar 0–0,5 | 20 | 1/14/3/2 | 10.0 | -0.55 | 0.55 | 0.69 | 5.98 | kesif | 0 |
| zarar 0,5–1 | 90 | 69/19/1/1 | 5.7 | -1.34 | 2.03 | 0.32 | 6.34 | kesif | 0 |
| zarar 1–1,5 | 50 | 43/0/0/7 | 5.9 | -1.74 | 2.41 | 0.6 | 4.16 | kesif | 0 |
| zarar 1,5+ | 15 | 7/0/0/8 | 6.0 | -2.39 | 3.37 | 0.96 | 2.81 | kesif | 0 |

## 2) Giriş kvadrantı × kova (‘çok erken dalıyor’ testi)

| kvadrant | n | stop | stop % | hedef | zaman | zarar.5–1 | zarar1–1.5 | zarar1.5+ | net pnl |
|---|---|---|---|---|---|---|---|---|---|
| iyi_zamanlama | 233 | 9 | %4 | 117 | 107 | 19 | 0 | 0 | 256.9 |
| erken_girdi_dustu | 133 | 112 | %84 | 12 | 9 | 69 | 43 | 7 | -99.2 |
| gec_girdi_dibi_kacirdi | 28 | 0 | %0 | 8 | 20 | 1 | 0 | 0 | 41.9 |
| yuksekten_girdi_ve_dustu | 18 | 11 | %61 | 0 | 7 | 1 | 7 | 8 | -24.1 |

## 3) Domain pay testi — ‘zararların %60’ında tek domain’ hipotezi

Aynı domain hem çok yaygın olabilir hem de ayırt edici olmayabilir; **fazla_pay** (stop payı − hedef payı) ayırt gücüdür.


### domain varlığı

| değer | stop n | stop pay | hedef n | hedef pay | fazla pay | stop/hedef oran |
|---|---|---|---|---|---|---|
| ms | 5 | %4 | 1 | %1 | +3 puan | 5.19 |
| formasyon | 114 | %86 | 115 | %84 | +2 puan | 1.03 |
| stabil | 132 | %100 | 137 | %100 | +0 puan | 1.0 |
| blok | 128 | %97 | 136 | %99 | -2 puan | 0.98 |

### domain:iddia kombinasyonu

| değer | stop n | stop pay | hedef n | hedef pay | fazla pay | stop/hedef oran |
|---|---|---|---|---|---|---|
| ms:olasi_tepki | 5 | %4 | 1 | %1 | +3 puan | 5.19 |
| formasyon:izle | 114 | %86 | 115 | %84 | +2 puan | 1.03 |
| stabil:izle | 132 | %100 | 137 | %100 | +0 puan | 1.0 |
| blok:konfluans | 128 | %97 | 136 | %99 | -2 puan | 0.98 |

### tam kaynak seti (format)

| değer | stop n | stop pay | hedef n | hedef pay | fazla pay | stop/hedef oran |
|---|---|---|---|---|---|---|
| ms:olasi_tepki | 5 | %4 | 1 | %1 | +3 puan | 5.19 |
| formasyon:izle | 114 | %86 | 115 | %84 | +2 puan | 1.03 |
| stabil:izle | 132 | %100 | 137 | %100 | +0 puan | 1.0 |
| blok:konfluans | 128 | %97 | 136 | %99 | -2 puan | 0.98 |

## 4) Tetik anı zemin (G1) & mesafe & lehte & onay

| zemin | n | stop | stop % | net pnl |
|---|---|---|---|---|
| ACTIVE | 412 | 132 | %32 | 175.5 |
| hükm gücü | n | stop | stop % | net pnl |
|---|---|---|---|---|
| lehte=4 | 393 | 126 | %32 | 159.9 |
| lehte=5 | 19 | 6 | %32 | 15.6 |
- **onaylı (g1)**: n=412 · stop 132 (%32) · net 175.5 ATR

## 5) Zarar kovalarında yoğunlaşma (sembol / tf / dönem)


**zarar 0,5–1** (n=90): sembol üst6 → HEDEF:6, CCOLA:4, ISMEN:4, CIMSA:3, CVKMD:3, CWENE:3 · tf: {'4h': 12, '1d': 27, '1h': 25, '2h': 26} · dönem: {'kesif': 71, 'dogrulama': 19}

**zarar 1–1,5** (n=50): sembol üst6 → BTCIM:3, ESEN:3, FENER:3, ISMEN:3, KCHOL:3, ODAS:3 · tf: {'2h': 15, '1d': 12, '1h': 16, '4h': 7} · dönem: {'kesif': 37, 'dogrulama': 13}

**zarar 1,5+** (n=15): sembol üst6 → CCOLA:3, EFOR:2, DAPGM:1, ESEN:1, FENER:1, FROTO:1 · tf: {'1h': 6, '2h': 5, '4h': 4} · dönem: {'kesif': 13, 'dogrulama': 2}

## 6) Stop içindeki en yaygın tam kaynak formatı

| format (kaynak seti) | stop n | stop pay |
|---|---|---|
| blok:konfluans+formasyon:izle+stabil:izle | 109 | %83 |
| blok:konfluans+stabil:izle | 14 | %11 |
| blok:konfluans+formasyon:izle+ms:olasi_tepki+stabil:izle | 3 | %2 |
| formasyon:izle+stabil:izle | 2 | %2 |
| stabil:izle | 2 | %2 |
| blok:konfluans+ms:olasi_tepki+stabil:izle | 2 | %2 |

Hedefteki en yaygın formatlar:
| format | hedef n | hedef pay |
|---|---|---|
| blok:konfluans+formasyon:izle+stabil:izle | 113 | %82 |
| blok:konfluans+stabil:izle | 22 | %16 |
| formasyon:izle+stabil:izle | 1 | %1 |
| blok:konfluans+formasyon:izle+ms:olasi_tepki+stabil:izle | 1 | %1 |

## 7) Erken giriş kümesi derinlemesine (erken_girdi_dustu)

- n=133 · stop 112 · stop hızı ort 4.9 bar · düşüş ort 2.44 ATR · net -99.2 ATR
- kv×domain: stabil:133, blok:128, formasyon:113, ms:4
- erken-stop sembolleri üst8: [('HEDEF', 7), ('CCOLA', 5), ('FENER', 5), ('KCHOL', 5), ('ESEN', 4), ('ISMEN', 4), ('MIATK', 4), ('ODAS', 4)]

## 8) Karşılaştırma özeti (ayırt edici sinyaller)

| alan | stop fazlası (ilk3) |  |  |
|---|---|---|---|
| giriş kvadrantı | erken_girdi_dustu: +76 puan | yuksekten_girdi_ve_dustu: +8 puan | gec_girdi_dibi_kacirdi: -6 puan |
| domain | ms: +3 puan | formasyon: +2 puan | stabil: +0 puan |
| onaysız test | False: +0 puan |
| dönem | dogrulama: +5 puan | kesif: -5 puan |

## 9) Önceden gözlenebilir ölçütler — ‘canlıda ayrım mümkün mü?’

Kvadrant `dusus` alanı geleceğe bakar (yalnız teşhis için). Bu tablo giriş anında **zaten bilinebilen** alanlarla kazanan/kaybeden ayrımını ölçer (R13: önce ölç, karar sonra).

| ölçüt (ort) | kâr | zarar 0–0,5 | zarar 0,5–1 | zarar 1–1,5 | zarar 1,5+ |
|---|---|---|---|---|---|
| stop mesafesi (A) | 1.08 | 1.1 | 0.86 | 1.27 | 1.76 |
| hedef mesafesi (A) | 4.63 | 5.38 | 6.35 | 5.72 | 4.93 |
| R | 3.96 | 5.98 | 6.34 | 4.16 | 2.81 |
| band konumu (0=alt,1=üst) | 1.51 | 1.47 | 1.5 | 1.8 | 2.52 |
| zemin mesafesi (A) | 0.98 | 1.0 | 0.76 | 1.17 | 1.66 |
| dip kaçış (A) | 0.49 | 0.69 | 0.32 | 0.6 | 0.96 |
| dip yaşı (bar) | 5.7 | 4.7 | 5.69 | 5.52 | 6.53 |
| momentum10 (A) | -0.65 | -0.87 | -1.21 | -0.5 | -0.52 |
| momentum5 (A) | -0.46 | -0.03 | -0.58 | -0.34 | 0.02 |

Paylar:
| kova | n | dip taze (≤3 bar) | düşüş ortası (mom10<−1A) | üst bant (pos≥0,5) |
|---|---|---|---|---|
| kâr | 237 | %27 | %36 | %98 |
| zarar 0–0,5 | 20 | %30 | %50 | %100 |
| zarar 0,5–1 | 90 | %27 | %53 | %100 |
| zarar 1–1,5 | 50 | %32 | %28 | %100 |
| zarar 1,5+ | 15 | %13 | %53 | %100 |

## 10) Aday kural taraması — ‘bunu filtreleseydik’ (salt offline)

Kural uygulansaydı o işlem **açılmazdı**; ‘kalan net’ = filtreli sistem net’i. Baseline: n=412, net +175,5A, kazanç %55,8. **Uyarı:** bu tarama post-hoc çoklu-testtir — seçilecek tek kural yeni (kör) fazda kapı ile doğrulanmalı.

| kural (açılmaz) | n elenir | elenen net | elenen stop | kalan n | kalan net | kalan kazanç% |
|---|---|---|---|---|---|---|
| momentum10 < −1A | 165 | +46.4 | 62 | 247 | +129.1 | %59.5 |
| dip kaçış < 0,5A | 235 | +95.1 | 84 | 177 | +80.4 | %56.5 |
| R > 5,5 (uzak hedef) | 29 | +17.4 | 10 | 383 | +158.1 | %56.1 |
| stop mesafesi < 0,9A | 169 | +69.0 | 61 | 243 | +106.4 | %56.8 |
| zemin mesafesi < 0,8A | 169 | +69.0 | 61 | 243 | +106.4 | %56.8 |
| R>5,5 ∧ dip<0,5 | 17 | +14.3 | 6 | 395 | +161.2 | %56.2 |
| R>5,5 ∧ mom<−1 | 12 | +0.1 | 6 | 400 | +175.4 | %56.2 |
| R>5,5 ∧ stop<0,9 | 5 | -0.4 | 2 | 407 | +175.9 | %56.3 |
| dip<0,5 ∧ mom<−1 | 119 | +37.8 | 49 | 293 | +137.7 | %57.3 |
| R>5,5 ∧ dip<0,5 ∧ mom<−1 | 11 | +1.8 | 5 | 401 | +173.7 | %56.1 |

---
*Doğrulama: n=412 · kova toplamı {'kâr': 237, 'zarar 1–1,5': 50, 'zarar 0,5–1': 90, 'zarar 0–0,5': 20, 'zarar 1,5+': 15}*