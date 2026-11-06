Başarılı/istenen hisse: **174/174**; hatalı: **0**. Tüm olaylar: **4775**; sınıflar: `UP_ARROW` 584, `VERTICAL_OTHER_WARNING` 3353, `VERTICAL_SUPPRESSED_PREVIOUS_UP_CANDIDATE` 838.
Arşiv yakalama sınırıyla kapanmamış **174 adet 4s** ve **174 adet günlük** bar dışlandı. Bu, eksik seansları bağımsız denetlemez.
`▲` 8-bar durumları: `BAD_HISTORY` 15, `RIGHT_CENSORED` 14, `VALID` 555.
Geçerli 8 barlı **555 ▲** içinde zayıf MFE (<0,5 ATR) **138 (%24.9)**; en az 8 bar ayrılmış geçerli ok **486**.
8 bar ±1 ATR ilk temas sayıları: `AMBIGUOUS_SAME_BAR` 9, `DOWN_FIRST` 245, `NEITHER` 25, `UP_FIRST` 276.

Aşağıdaki yüzde paydası, her satırdaki **geçerli 8-barlık olay n**'dir. İlk-temas yüzdeleri aynı-bar belirsiz ve hiç temas etmeyenleri de paydada tutar. Az n/hisse sayılı gruplar kararsızdır; olaylar ve tarihler bağımsız değildir.

### Ok/uyarı sınıfları (farklı popülasyonlar)
| Grup | Olay n | Hisse n | Zayıf n | Zayıf % | Medyan kapanış (ATR) | +1 ATR önce % | −1 ATR önce % |
|---|---:|---:|---:|---:|---:|---:|---:|
| UP_ARROW | 555 | 160 | 138 | 24.9 | -0.10 | 49.7 | 44.1 |
| VERTICAL_OTHER_WARNING | 3262 | 174 | 745 | 22.8 | -0.03 | 49.7 | 42.9 |
| VERTICAL_SUPPRESSED_PREVIOUS_UP_CANDIDATE | 803 | 170 | 165 | 20.5 | +0.00 | 53.4 | 39.4 |

Bastırılmış önceki ▲ adayları ile kalan ▲ okları aynı olaylar değildir; bu tablo politikanın nedensel etkisi veya ▼ sonrası düşüş garantisi değildir.

### Hacim karşılaştırması
| Grup | Olay n | Hisse n | Zayıf n | Zayıf % | Medyan kapanış (ATR) | +1 ATR önce % | −1 ATR önce % |
|---|---:|---:|---:|---:|---:|---:|---:|
| HIGH_GE_1.2 | 337 | 137 | 83 | 24.6 | -0.03 | 49.9 | 43.6 |
| LOW_LT_0.8 | 99 | 76 | 25 | 25.3 | -0.30 | 50.5 | 46.5 |
| MID_0.8_TO_1.2 | 119 | 83 | 30 | 25.2 | -0.31 | 48.7 | 43.7 |

### Kapanış saati × hacim
| Grup | Olay n | Hisse n | Zayıf n | Zayıf % | Medyan kapanış (ATR) | +1 ATR önce % | −1 ATR önce % |
|---|---:|---:|---:|---:|---:|---:|---:|
| 13:00 / MID_0.8_TO_1.2 | 1 | 1 | 0 | 0.0 | +1.28 | 100.0 | 0.0 |
| 13:30 / HIGH_GE_1.2 | 144 | 95 | 28 | 19.4 | +0.30 | 60.4 | 35.4 |
| 13:30 / LOW_LT_0.8 | 44 | 43 | 10 | 22.7 | +0.29 | 56.8 | 40.9 |
| 13:30 / MID_0.8_TO_1.2 | 67 | 53 | 19 | 28.4 | -0.18 | 41.8 | 49.3 |
| 17:30 / HIGH_GE_1.2 | 188 | 111 | 53 | 28.2 | -0.22 | 42.6 | 48.9 |
| 17:30 / LOW_LT_0.8 | 11 | 11 | 2 | 18.2 | +0.00 | 54.5 | 36.4 |
| 17:30 / MID_0.8_TO_1.2 | 48 | 41 | 11 | 22.9 | -0.43 | 56.2 | 37.5 |
| 18:00 / HIGH_GE_1.2 | 5 | 5 | 2 | 40.0 | -0.74 | 20.0 | 80.0 |
| 18:00 / LOW_LT_0.8 | 44 | 38 | 13 | 29.5 | -0.72 | 43.2 | 54.5 |
| 18:00 / MID_0.8_TO_1.2 | 3 | 3 | 0 | 0.0 | +0.48 | 66.7 | 33.3 |

Kısa seans-sonu kovaları önceki 20 karma uzunluktaki bara karşı düşük hacimli görünebilir; saat içi karşılaştırmalar da nedensel ayarlama değildir.

### Öndeki bearish OB ve seçili bearish FVG
| Grup | Olay n | Hisse n | Zayıf n | Zayıf % | Medyan kapanış (ATR) | +1 ATR önce % | −1 ATR önce % |
|---|---:|---:|---:|---:|---:|---:|---:|
| FAR_OVER_1ATR | 321 | 137 | 83 | 25.9 | -0.18 | 50.2 | 42.4 |
| NEAR_1ATR | 167 | 103 | 42 | 25.1 | -0.06 | 47.9 | 46.7 |
| NONE_AHEAD | 11 | 10 | 2 | 18.2 | +0.60 | 36.4 | 63.6 |
| UNKNOWN | 56 | 42 | 11 | 19.6 | -0.17 | 55.4 | 42.9 |

| Grup | Olay n | Hisse n | Zayıf n | Zayıf % | Medyan kapanış (ATR) | +1 ATR önce % | −1 ATR önce % |
|---|---:|---:|---:|---:|---:|---:|---:|
| FAR_OVER_1ATR | 73 | 56 | 19 | 26.0 | -0.60 | 46.6 | 49.3 |
| NEAR_1ATR | 83 | 62 | 25 | 30.1 | -0.18 | 47.0 | 45.8 |
| NONE_AHEAD | 343 | 139 | 83 | 24.2 | +0.00 | 50.1 | 42.9 |
| UNKNOWN | 56 | 42 | 11 | 19.6 | -0.17 | 55.4 | 42.9 |

### Yakın OB/FVG birlikte
| Grup | Olay n | Hisse n | Zayıf n | Zayıf % | Medyan kapanış (ATR) | +1 ATR önce % | −1 ATR önce % |
|---|---:|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 56 | 42 | 11 | 19.6 | -0.17 | 55.4 | 42.9 |
| ikisi de yakın değil | 276 | 129 | 67 | 24.3 | -0.09 | 50.4 | 42.4 |
| ikisi yakın | 27 | 24 | 7 | 25.9 | +0.08 | 48.1 | 44.4 |
| yalnız FVG yakın | 56 | 48 | 18 | 32.1 | -0.55 | 46.4 | 46.4 |
| yalnız OB yakın | 140 | 96 | 35 | 25.0 | -0.09 | 47.9 | 47.1 |

### Dış piyasa yapısı
| Grup | Olay n | Hisse n | Zayıf n | Zayıf % | Medyan kapanış (ATR) | +1 ATR önce % | −1 ATR önce % |
|---|---:|---:|---:|---:|---:|---:|---:|
| STATE_BEARISH | 265 | 123 | 70 | 26.4 | -0.07 | 49.1 | 46.4 |
| STATE_BULLISH | 74 | 48 | 18 | 24.3 | -0.22 | 51.4 | 43.2 |
| STATE_TRANSITION_DOWN | 123 | 76 | 31 | 25.2 | -0.11 | 48.8 | 43.1 |
| STATE_TRANSITION_UP | 37 | 31 | 8 | 21.6 | +0.00 | 45.9 | 35.1 |
| UNKNOWN | 56 | 42 | 11 | 19.6 | -0.17 | 55.4 | 42.9 |

### Stabil 4s ve günlük bağlam
| Grup | Olay n | Hisse n | Zayıf n | Zayıf % | Medyan kapanış (ATR) | +1 ATR önce % | −1 ATR önce % |
|---|---:|---:|---:|---:|---:|---:|---:|
| H4_BUYERS_EMERGING | 314 | 135 | 83 | 26.4 | +0.00 | 49.7 | 44.3 |
| H4_NO_RECOVERY | 19 | 18 | 3 | 15.8 | +0.09 | 52.6 | 42.1 |
| H4_RECOVERY_CONFIRMED | 17 | 16 | 6 | 35.3 | -0.07 | 52.9 | 47.1 |
| H4_RECOVERY_FAILED | 46 | 35 | 5 | 10.9 | +0.12 | 63.0 | 28.3 |
| H4_SELLING_WEAKENING | 149 | 94 | 40 | 26.8 | -0.39 | 44.3 | 49.0 |
| UNKNOWN | 10 | 7 | 1 | 10.0 | +0.67 | 60.0 | 40.0 |

| Grup | Olay n | Hisse n | Zayıf n | Zayıf % | Medyan kapanış (ATR) | +1 ATR önce % | −1 ATR önce % |
|---|---:|---:|---:|---:|---:|---:|---:|
| DAILY_RAW_ADVANCE | 4 | 3 | 0 | 0.0 | +2.05 | 100.0 | 0.0 |
| DAILY_RAW_BALANCE | 8 | 8 | 4 | 50.0 | -0.83 | 25.0 | 75.0 |
| DAILY_RAW_DISTRIBUTION | 15 | 13 | 1 | 6.7 | +0.27 | 73.3 | 6.7 |
| DAILY_RAW_GAP_WATCH | 6 | 6 | 2 | 33.3 | -0.18 | 33.3 | 66.7 |
| DAILY_RAW_NEUTRAL | 257 | 119 | 65 | 25.3 | -0.16 | 48.6 | 45.1 |
| DAILY_RAW_PULLBACK | 43 | 32 | 9 | 20.9 | +0.16 | 41.9 | 48.8 |
| DAILY_RAW_STRUCTURE_BROKEN | 45 | 34 | 8 | 17.8 | +0.41 | 62.2 | 35.6 |
| DAILY_RAW_TOO_DEEP | 176 | 110 | 48 | 27.3 | -0.31 | 48.9 | 45.5 |
| UNKNOWN | 1 | 1 | 1 | 100.0 | -1.67 | 0.0 | 100.0 |

### Ok türü ve destek rejimi proxy'si
| Grup | Olay n | Hisse n | Zayıf n | Zayıf % | Medyan kapanış (ATR) | +1 ATR önce % | −1 ATR önce % |
|---|---:|---:|---:|---:|---:|---:|---:|
| close_reclaim | 255 | 131 | 59 | 23.1 | -0.21 | 46.3 | 47.5 |
| intrabar_sweep_reclaim | 162 | 107 | 48 | 29.6 | -0.16 | 51.2 | 43.8 |
| long_base_breakout | 63 | 49 | 18 | 28.6 | -0.04 | 49.2 | 42.9 |
| upward_rebase_momentum | 75 | 54 | 13 | 17.3 | +0.20 | 58.7 | 34.7 |

| Grup | Olay n | Hisse n | Zayıf n | Zayıf % | Medyan kapanış (ATR) | +1 ATR önce % | −1 ATR önce % |
|---|---:|---:|---:|---:|---:|---:|---:|
| BREACHED_FIXED_SUPPORT | 130 | 86 | 23 | 17.7 | +0.00 | 52.3 | 43.1 |
| HORIZONTAL_AFTER_DROP | 213 | 117 | 63 | 29.6 | -0.30 | 45.5 | 51.2 |
| HORIZONTAL_BASE | 10 | 9 | 4 | 40.0 | +0.12 | 60.0 | 40.0 |
| LONG_HORIZONTAL | 49 | 29 | 12 | 24.5 | +0.10 | 55.1 | 32.7 |
| NEWLY_FLATTENED_AFTER_RISE | 153 | 86 | 36 | 23.5 | -0.27 | 51.0 | 39.2 |

### Hisse başına en az 8 bar ayrılmış alt kümede hacim
| Grup | Olay n | Hisse n | Zayıf n | Zayıf % | Medyan kapanış (ATR) | +1 ATR önce % | −1 ATR önce % |
|---|---:|---:|---:|---:|---:|---:|---:|
| HIGH_GE_1.2 | 295 | 137 | 72 | 24.4 | +0.00 | 49.8 | 44.1 |
| LOW_LT_0.8 | 89 | 72 | 21 | 23.6 | -0.44 | 50.6 | 46.1 |
| MID_0.8_TO_1.2 | 102 | 74 | 23 | 22.5 | -0.08 | 52.0 | 41.2 |

Düşük eksi yüksek hacim için zayıf tepki oranı farkı **+0.6 yüzde puan**; 5.000 hisse-kümeli bootstrap ile betimsel %95 aralık **[-8.8, +10.3] puan**. Hisseler ortak tarih şoklarını paylaşır, seçim/çoklu deneme ve gün korelasyonu bu aralıkla düzeltilmemiştir; nedensel kanıt veya canlı tahmin değildir.

### Farklı pencerelerde zayıf MFE
Her ufuk için yalnız o ufkun tam/geçerli olayları; farklı paydalar aynı olayı izleme garantisi vermez.

| Sonraki bar | Geçerli ▲ | Zayıf MFE n | Zayıf % |
|---:|---:|---:|---:|
| 4 | 557 | 193 | 34.6 |
| 8 | 555 | 138 | 24.9 |
| 16 | 554 | 103 | 18.6 |
