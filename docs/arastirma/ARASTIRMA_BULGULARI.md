# Formation-Bot Arşiv Araştırma Raporu
> Bu dosya tablo ekidir: ham aggregatlar soru başına bölümlenir.
> Okunabilir özet ve yorum: `docs/arastirma/ARASTIRMA_SONUCLARI.md`.
> Yalnız karar için okuyan, aşağıdaki tablolara inmeden özetle yetinebilir.
Kaynak: `backfill_data/` (365 gün derin çekim) · Sembol: 176 · Havuz dışı: BRENT

## Kapsam
| timeframe | sembol | ort_bar | toplam_zone | toplam_epizot | toplam_swing | toplam_event | toplam_rol_araligi | ms_hatali_seri |
|-----------|--------|---------|-------------|---------------|--------------|--------------|--------------------|----------------|
| 1d        | 176    | 499     | 22190       | 24846         | 32801        | 17590        | 23733              | 0              |
| 1h        | 176    | 3211    | 59130       | 90485         | 201024       | 94455        | 143055             | 0              |
| 2h        | 176    | 1790    | 64216       | 76267         | 109756       | 53911        | 78467              | 0              |
| 4h        | 176    | 1073    | 41510       | 48886         | 68464        | 34072        | 49848              | 0              |

## Yöntem notları
- Ölçüm birimi **çapa sonrası** barlardır; çapa barının kendisi hiçbir uzanıma katılmaz (anti-lookahead).
- Tüm uzanımlar **ATR cinsindendir**; TL/% kullanılmaz çünkü BIST 5-500 TL aralığında hisse barındırır.
- `sansur` alanı pencerenin veri sonuna takıldığını gösterir; sansürlü gözlem başarı sayılmaz.
- OB popülasyonu `replay_ob_zones` ile yeniden kurulur: motor dolan zone'ları listesinden sildiği için final snapshot yalnız hayatta kalanları verir.
- PH/PL/WH/WL rolleri bar bar izlenir: `structural_role` zamanla mutate olur ve final değer tarihsel atamaları kaybetmiştir.
- `TUM_ZONE`/`ZONE_ICI` temaslarında kenar-ancored yön belirlenemez; bunlar `OLCULEMEDI` kovasında ayrı raporlanır, düşürülmez.
- Güven etiketi: n>=30 YETERLI, n>=15 KISMI, altı ZAYIF (`analytics/backtest.py` ile aynı eşikler).

## Soru 1 — OB/FVG tek denemede mi çok denemede mi?
| timeframe | family | n     | guven   | tek_deneme | 2_deneme | 3plus_deneme | hic_deneme | ort_epizot |
|-----------|--------|-------|---------|------------|----------|--------------|------------|------------|
| 1d        | FVG    | 8641  | YETERLI | %71.4      | %0.6     | %0.0         | %27.9      | 0.727      |
| 1d        | OB     | 13549 | YETERLI | %59.8      | %19.1    | %10.7        | %10.3      | 1.370      |
| 1h        | OB     | 59130 | YETERLI | %59.9      | %21.3    | %13.3        | %5.4       | 1.530      |
| 2h        | FVG    | 27910 | YETERLI | %76.4      | %0.8     | %0.0         | %22.8      | 0.780      |
| 2h        | OB     | 36306 | YETERLI | %59.7      | %20.7    | %13.0        | %6.6       | 1.501      |
| 4h        | FVG    | 18594 | YETERLI | %77.9      | %1.1     | %0.0         | %20.9      | 0.802      |
| 4h        | OB     | 22916 | YETERLI | %59.4      | %19.7    | %13.0        | %7.8       | 1.482      |

## Soru 2 — %kaçı geçildi, %kaçı tepki aldı?
### Zone seviyesi: temas / geçilme / dolum

| timeframe | family | n     | guven   | temas_var | gecildi_violation | full_fill | sansur_payi | ort_omur_bar | ort_yukseklik_atr |
|-----------|--------|-------|---------|-----------|-------------------|-----------|-------------|--------------|-------------------|
| 1d        | FVG    | 8641  | YETERLI | %72.1     | %0.0              | %40.8     | %1.7        | 5.398        | 0.628             |
| 1d        | OB     | 13549 | YETERLI | %89.7     | %85.4             | %0.0      | %14.6       | 32.495       | 0.959             |
| 1h        | OB     | 59130 | YETERLI | %94.6     | %93.6             | %0.0      | %6.4        | 89.806       | 0.948             |
| 2h        | FVG    | 27910 | YETERLI | %77.2     | %0.0              | %40.3     | %0.3        | 5.650        | 0.720             |
| 2h        | OB     | 36306 | YETERLI | %93.4     | %92.0             | %0.0      | %8.0        | 63.555       | 0.932             |
| 4h        | FVG    | 18594 | YETERLI | %79.1     | %0.0              | %42.6     | %0.6        | 5.160        | 0.775             |
| 4h        | OB     | 22916 | YETERLI | %92.2     | %90.0             | %0.0      | %10.0       | 47.107       | 0.986             |

### Dokunuş seviyesi: beklenen yönde tepki (zone yönü)

| timeframe | family | n     | guven   | yon_tepki_CALISTI | yon_tepki_AZ | yon_tepki_YOK | yon_tepki_TERS | ort_yon_h12_atr | ort_yon_uzun_tepe_h40 |
|-----------|--------|-------|---------|-------------------|--------------|---------------|----------------|-----------------|-----------------------|
| 1d        | FVG    | 6285  | YETERLI | %65.0             | %17.8        | %4.8          | %12.3          | 1.956           | 3.914                 |
| 1d        | OB     | 18561 | YETERLI | %65.0             | %14.9        | %4.4          | %14.7          | 1.990           | 3.777                 |
| 1h        | OB     | 90485 | YETERLI | %66.1             | %15.0        | %4.8          | %14.0          | 2.004           | 3.838                 |
| 2h        | FVG    | 21757 | YETERLI | %66.5             | %18.1        | %4.2          | %11.2          | 2.111           | 4.051                 |
| 2h        | OB     | 54510 | YETERLI | %65.6             | %15.3        | %4.5          | %14.3          | 1.997           | 3.917                 |
| 4h        | FVG    | 14921 | YETERLI | %66.4             | %17.3        | %4.1          | %12.2          | 2.125           | 4.089                 |
| 4h        | OB     | 33965 | YETERLI | %65.2             | %15.2        | %4.4          | %14.8          | 2.027           | 3.957                 |

## Soru 3 — Kenar-ancored tepki (ATR)
| timeframe | family | dokunulan_kenar | n     | guven   | tepki_CALISTI | tepki_AZ | tepki_YOK | tepki_TERS | OLCULEMEDI | ort_kenar_h12 | ort_kenar_tepe | ort_kenar_uzun_tepe |
|-----------|--------|-----------------|-------|---------|---------------|----------|-----------|------------|------------|---------------|----------------|---------------------|
| 1d        | FVG    | ALT_KENAR       | 2054  | YETERLI | %55.6         | %18.6    | %6.7      | %19.0      | %0.0       | 1.842         | 1.842          | 4.093               |
| 1d        | FVG    | TUM_ZONE        | 2089  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1d        | FVG    | UST_KENAR       | 2099  | YETERLI | %62.6         | %18.4    | %5.2      | %13.6      | %0.1       | 1.812         | 1.812          | 3.228               |
| 1d        | FVG    | ZONE_ICI        | 43    | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1d        | OB     | ALT_KENAR       | 7381  | YETERLI | %62.6         | %13.2    | %4.1      | %19.6      | %0.5       | 2.187         | 2.187          | 4.578               |
| 1d        | OB     | TUM_ZONE        | 2664  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1d        | OB     | UST_KENAR       | 8302  | YETERLI | %58.6         | %17.9    | %5.1      | %16.9      | %1.5       | 1.660         | 1.660          | 3.066               |
| 1d        | OB     | ZONE_ICI        | 214   | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1h        | OB     | ALT_KENAR       | 34517 | YETERLI | %58.0         | %15.2    | %5.9      | %20.8      | %0.1       | 1.983         | 1.983          | 4.088               |
| 1h        | OB     | TUM_ZONE        | 19440 | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1h        | OB     | UST_KENAR       | 36285 | YETERLI | %58.9         | %16.5    | %6.0      | %18.4      | %0.2       | 1.779         | 1.779          | 3.586               |
| 1h        | OB     | ZONE_ICI        | 243   | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 2h        | FVG    | ALT_KENAR       | 6860  | YETERLI | %54.2         | %18.7    | %7.7      | %19.3      | %0.1       | 1.719         | 1.719          | 3.832               |
| 2h        | FVG    | TUM_ZONE        | 7445  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 2h        | FVG    | UST_KENAR       | 7435  | YETERLI | %54.8         | %19.9    | %7.7      | %17.5      | %0.0       | 1.544         | 1.544          | 3.311               |
| 2h        | FVG    | ZONE_ICI        | 17    | KISMI   | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 2h        | OB     | ALT_KENAR       | 20699 | YETERLI | %58.1         | %15.6    | %5.6      | %20.5      | %0.2       | 1.985         | 1.985          | 4.165               |
| 2h        | OB     | TUM_ZONE        | 12516 | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 2h        | OB     | UST_KENAR       | 21107 | YETERLI | %60.0         | %15.9    | %5.5      | %18.4      | %0.3       | 1.800         | 1.800          | 3.518               |
| 2h        | OB     | ZONE_ICI        | 188   | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 4h        | FVG    | ALT_KENAR       | 4853  | YETERLI | %55.8         | %17.4    | %7.5      | %19.2      | %0.0       | 1.831         | 1.831          | 4.026               |
| 4h        | FVG    | TUM_ZONE        | 5235  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 4h        | FVG    | UST_KENAR       | 4754  | YETERLI | %57.1         | %18.6    | %6.9      | %17.4      | %0.0       | 1.677         | 1.677          | 3.494               |
| 4h        | FVG    | ZONE_ICI        | 79    | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 4h        | OB     | ALT_KENAR       | 12953 | YETERLI | %59.9         | %14.6    | %5.4      | %19.9      | %0.2       | 2.117         | 2.117          | 4.397               |
| 4h        | OB     | TUM_ZONE        | 7763  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 4h        | OB     | UST_KENAR       | 13053 | YETERLI | %60.4         | %15.6    | %5.2      | %18.3      | %0.6       | 1.869         | 1.869          | 3.461               |
| 4h        | OB     | ZONE_ICI        | 196   | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |

### Kenar-ancored: ATR eşik ızgarası aşım oranı (h12)

| timeframe | n     | guven   | >=0.25 ATR | >=0.5 ATR | >=1 ATR | >=1.5 ATR | >=2 ATR |
|-----------|-------|---------|------------|-----------|---------|-----------|---------|
| 1d        | 24846 | YETERLI | %77.1      | %72.0     | %60.7   | %49.5     | %39.2   |
| 1h        | 90485 | YETERLI | %74.5      | %69.4     | %58.6   | %48.0     | %38.5   |
| 2h        | 76267 | YETERLI | %74.7      | %69.2     | %58.0   | %47.3     | %37.7   |
| 4h        | 48886 | YETERLI | %75.2      | %69.9     | %59.3   | %49.3     | %39.8   |

## Soru 4 — Yüksek zone ayırt edici mi, tepki anlık mı kalıcı mı?
| timeframe | family | yukseklik_kovasi | n     | guven   | ort_pay_5 | ort_pay_3 | ort_h12_decay | ort_tepe_h12 | ort_uzun_tepe_h40 | uzun/ana_tepe_orani | tepki_CALISTI |
|-----------|--------|------------------|-------|---------|-----------|-----------|---------------|--------------|-------------------|---------------------|---------------|
| 1d        | FVG    | 0-0.5            | 3276  | YETERLI | 0.617     | 0.481     | 2.418         | 1.912        | 3.815             | 3.307               | %64.3         |
| 1d        | FVG    | 0.5-1            | 1989  | YETERLI | 0.613     | 0.438     | 1.956         | 1.989        | 4.080             | 3.338               | %64.7         |
| 1d        | FVG    | 1-2              | 858   | YETERLI | 0.652     | 0.452     | 1.747         | 1.985        | 3.880             | 2.426               | %67.8         |
| 1d        | FVG    | >=2              | 162   | YETERLI | 0.414     | 0.192     | 1.248         | 2.304        | 4.046             | 1.656               | %71.0         |
| 1d        | OB     | 0-0.5            | 1493  | YETERLI | 0.552     | 0.379     | 2.042         | 1.981        | 4.035             | 3.571               | %62.7         |
| 1d        | OB     | 0.5-1            | 9112  | YETERLI | 0.571     | 0.396     | 2.094         | 1.997        | 3.811             | 3.053               | %65.0         |
| 1d        | OB     | 1-2              | 6534  | YETERLI | 0.294     | 0.099     | 2.523         | 1.992        | 3.700             | 2.890               | %66.1         |
| 1d        | OB     | >=2              | 873   | YETERLI | 0.587     | 0.426     | 1.531         | 1.828        | 3.469             | 2.322               | %68.4         |
| 1d        | OB     | BILINMEYEN       | 549   | YETERLI | 0.566     | 0.442     | 1.426         | 2.184        | 3.932             | 2.759               | %52.1         |
| 1h        | OB     | 0-0.5            | 9650  | YETERLI | 0.657     | 0.522     | 2.130         | 2.033        | 3.928             | 2.811               | %66.1         |
| 1h        | OB     | 0.5-1            | 43454 | YETERLI | 0.621     | 0.476     | 1.853         | 2.019        | 3.874             | 2.817               | %65.9         |
| 1h        | OB     | 1-2              | 31590 | YETERLI | 0.590     | 0.427     | 1.572         | 1.988        | 3.793             | 2.604               | %66.3         |
| 1h        | OB     | >=2              | 5475  | YETERLI | 0.599     | 0.419     | 1.213         | 1.925        | 3.662             | 2.180               | %68.1         |
| 1h        | OB     | BILINMEYEN       | 316   | YETERLI | 0.393     | 0.250     | 2.150         | 1.887        | 3.489             | 2.550               | %44.9         |
| 2h        | FVG    | 0-0.5            | 10132 | YETERLI | 0.684     | 0.530     | 2.008         | 2.033        | 3.972             | 2.941               | %65.6         |
| 2h        | FVG    | 0.5-1            | 6756  | YETERLI | 0.658     | 0.498     | 1.976         | 2.074        | 3.984             | 2.735               | %66.1         |
| 2h        | FVG    | 1-2              | 3842  | YETERLI | 0.637     | 0.443     | 1.463         | 2.190        | 4.145             | 2.472               | %68.1         |
| 2h        | FVG    | >=2              | 1027  | YETERLI | 0.647     | 0.517     | 1.063         | 2.839        | 4.926             | 1.935               | %71.7         |
| 2h        | OB     | 0-0.5            | 7600  | YETERLI | 0.662     | 0.498     | 2.136         | 2.076        | 4.069             | 2.873               | %64.7         |
| 2h        | OB     | 0.5-1            | 24221 | YETERLI | 0.643     | 0.454     | 2.015         | 2.027        | 3.977             | 2.936               | %65.5         |
| 2h        | OB     | 1-2              | 18783 | YETERLI | 0.600     | 0.402     | 1.579         | 1.948        | 3.831             | 2.714               | %65.9         |
| 2h        | OB     | >=2              | 3507  | YETERLI | 0.588     | 0.344     | 1.350         | 1.928        | 3.711             | 2.413               | %68.9         |
| 2h        | OB     | BILINMEYEN       | 399   | YETERLI | 0.580     | 0.352     | 2.179         | 1.392        | 3.041             | 3.985               | %43.4         |
| 4h        | FVG    | 0-0.5            | 6211  | YETERLI | 0.619     | 0.487     | 2.120         | 2.011        | 3.873             | 3.200               | %65.1         |
| 4h        | FVG    | 0.5-1            | 5067  | YETERLI | 0.598     | 0.465     | 1.768         | 2.074        | 4.023             | 2.807               | %66.0         |
| 4h        | FVG    | 1-2              | 2812  | YETERLI | 0.576     | 0.407     | 1.339         | 2.192        | 4.215             | 2.635               | %68.3         |
| 4h        | FVG    | >=2              | 831   | YETERLI | 0.622     | 0.450     | 1.065         | 3.061        | 5.680             | 2.182               | %72.6         |
| 4h        | OB     | 0-0.5            | 5711  | YETERLI | 0.623     | 0.496     | 2.167         | 2.135        | 4.221             | 3.039               | %65.3         |
| 4h        | OB     | 0.5-1            | 11107 | YETERLI | 0.610     | 0.464     | 1.886         | 2.031        | 3.992             | 3.079               | %64.8         |
| 4h        | OB     | 1-2              | 13803 | YETERLI | 0.559     | 0.399     | 1.677         | 1.996        | 3.858             | 2.871               | %65.6         |
| 4h        | OB     | >=2              | 2929  | YETERLI | 0.529     | 0.359     | 1.255         | 1.970        | 3.806             | 2.364               | %67.2         |
| 4h        | OB     | BILINMEYEN       | 415   | YETERLI | 0.553     | 0.436     | 2.202         | 1.817        | 3.662             | 2.649               | %48.4         |

_Okuma: `ort_pay_5` yüksek + `uzun/ana_tepe_orani` ~1 -> **anlık**; `ort_pay_5` düşük + oran >>1 -> **yavaş ama kalıcı**._

_`ort_h12_decay` 1'den büyükse pencere, tepenin altına kapanmıştır (kapanış referansın ters tarafında); bu "tepki verdi sonra tamamen geri verdi" demektir, ölçüm hatası değildir._

## Soru 5 — MS BOS/CHOCH: yön ile tepki uyuşuyor mu?
### Scope x event tipi

| timeframe | scope    | event_type            | n     | guven   | uyumlu | CALISTI | AZ_DEVAM | DEVAM_YOK | TERS | sansur | ort_devam_h12 | ort_ters_h12 |
|-----------|----------|-----------------------|-------|---------|--------|---------|----------|-----------|------|--------|---------------|--------------|
| 1d        | EXTERNAL | EVENT_BOS             | 1826  | YETERLI | %96.7  | %68.5   | %21.5    | %7.2      | %2.0 | %2.8   | 2.284         | 2.081        |
| 1d        | EXTERNAL | EVENT_CHOCH           | 714   | YETERLI | %95.2  | %65.8   | %22.7    | %8.0      | %3.2 | %0.8   | 2.100         | 2.038        |
| 1d        | EXTERNAL | EVENT_FALSE_BREAK     | 153   | YETERLI | %96.7  | %69.9   | %20.9    | %6.5      | %2.6 | %2.0   | 2.137         | 2.026        |
| 1d        | EXTERNAL | EVENT_SWEEP           | 3566  | YETERLI | %95.8  | %66.1   | %23.2    | %7.3      | %3.3 | %0.8   | 1.987         | 2.129        |
| 1d        | EXTERNAL | EVENT_TRANSITION_FAIL | 208   | YETERLI | %99.5  | %68.8   | %25.5    | %5.3      | %0.5 | %1.0   | 2.288         | 2.145        |
| 1d        | INTERNAL | EVENT_BOS             | 3332  | YETERLI | %94.7  | %67.9   | %21.9    | %5.6      | %2.5 | %3.5   | 2.301         | 1.941        |
| 1d        | INTERNAL | EVENT_CHOCH           | 1291  | YETERLI | %95.2  | %64.0   | %23.9    | %8.9      | %3.0 | %0.7   | 2.016         | 2.174        |
| 1d        | INTERNAL | EVENT_FALSE_BREAK     | 236   | YETERLI | %95.3  | %64.8   | %25.4    | %6.4      | %2.1 | %3.0   | 1.972         | 2.165        |
| 1d        | INTERNAL | EVENT_SWEEP           | 5859  | YETERLI | %95.9  | %64.9   | %24.9    | %7.0      | %2.6 | %1.3   | 2.008         | 2.059        |
| 1d        | INTERNAL | EVENT_TRANSITION_FAIL | 405   | YETERLI | %97.3  | %66.4   | %25.7    | %5.7      | %2.0 | %1.2   | 2.141         | 2.159        |
| 1h        | EXTERNAL | EVENT_BOS             | 9564  | YETERLI | %97.0  | %67.5   | %22.7    | %8.9      | %0.9 | %0.3   | 2.278         | 1.979        |
| 1h        | EXTERNAL | EVENT_CHOCH           | 3606  | YETERLI | %97.0  | %68.4   | %22.3    | %8.2      | %1.2 | %0.1   | 2.286         | 1.857        |
| 1h        | EXTERNAL | EVENT_FALSE_BREAK     | 697   | YETERLI | %96.3  | %61.0   | %26.7    | %10.0     | %2.3 | %0.0   | 1.908         | 2.214        |
| 1h        | EXTERNAL | EVENT_SWEEP           | 19748 | YETERLI | %96.9  | %62.6   | %26.2    | %10.0     | %1.2 | %0.2   | 1.882         | 2.130        |
| 1h        | EXTERNAL | EVENT_TRANSITION_FAIL | 947   | YETERLI | %97.4  | %69.0   | %22.1    | %7.7      | %1.3 | %0.1   | 2.406         | 1.924        |
| 1h        | INTERNAL | EVENT_BOS             | 18210 | YETERLI | %96.9  | %67.3   | %22.6    | %8.8      | %1.1 | %0.4   | 2.266         | 1.958        |
| 1h        | INTERNAL | EVENT_CHOCH           | 6656  | YETERLI | %97.3  | %66.5   | %23.6    | %8.9      | %1.0 | %0.1   | 2.174         | 1.942        |
| 1h        | INTERNAL | EVENT_FALSE_BREAK     | 1250  | YETERLI | %96.4  | %63.2   | %24.5    | %11.2     | %0.7 | %0.1   | 1.988         | 2.016        |
| 1h        | INTERNAL | EVENT_SWEEP           | 31886 | YETERLI | %96.9  | %62.9   | %26.2    | %9.6      | %1.1 | %0.2   | 1.923         | 2.114        |
| 1h        | INTERNAL | EVENT_TRANSITION_FAIL | 1891  | YETERLI | %97.4  | %68.5   | %22.1    | %8.2      | %1.2 | %0.2   | 2.267         | 1.943        |
| 2h        | EXTERNAL | EVENT_BOS             | 5408  | YETERLI | %97.6  | %67.1   | %23.8    | %8.1      | %0.9 | %1.2   | 2.326         | 2.001        |
| 2h        | EXTERNAL | EVENT_CHOCH           | 2141  | YETERLI | %97.9  | %68.6   | %22.6    | %8.1      | %0.7 | %0.2   | 2.362         | 1.962        |
| 2h        | EXTERNAL | EVENT_FALSE_BREAK     | 421   | YETERLI | %94.8  | %68.9   | %20.0    | %8.6      | %2.6 | %0.7   | 2.195         | 2.114        |
| 2h        | EXTERNAL | EVENT_SWEEP           | 11705 | YETERLI | %97.2  | %63.9   | %25.4    | %9.4      | %1.2 | %0.8   | 1.955         | 2.113        |
| 2h        | EXTERNAL | EVENT_TRANSITION_FAIL | 604   | YETERLI | %98.7  | %70.4   | %24.2    | %5.0      | %0.5 | %1.8   | 2.448         | 1.986        |
| 2h        | INTERNAL | EVENT_BOS             | 10330 | YETERLI | %97.3  | %67.3   | %22.8    | %8.8      | %0.7 | %0.9   | 2.276         | 1.989        |
| 2h        | INTERNAL | EVENT_CHOCH           | 3845  | YETERLI | %97.7  | %69.3   | %22.0    | %7.6      | %0.9 | %0.4   | 2.286         | 1.885        |
| 2h        | INTERNAL | EVENT_FALSE_BREAK     | 694   | YETERLI | %95.2  | %64.8   | %22.9    | %10.4     | %1.7 | %0.6   | 2.095         | 2.057        |
| 2h        | INTERNAL | EVENT_SWEEP           | 17708 | YETERLI | %97.4  | %63.5   | %25.6    | %9.6      | %1.1 | %0.7   | 1.900         | 2.151        |
| 2h        | INTERNAL | EVENT_TRANSITION_FAIL | 1055  | YETERLI | %97.7  | %69.6   | %23.4    | %6.1      | %0.8 | %1.8   | 2.429         | 1.999        |
| 4h        | EXTERNAL | EVENT_BOS             | 3466  | YETERLI | %98.0  | %70.9   | %20.5    | %7.6      | %0.9 | %2.9   | 2.503         | 1.999        |
| 4h        | EXTERNAL | EVENT_CHOCH           | 1325  | YETERLI | %98.0  | %71.0   | %19.8    | %8.2      | %0.8 | %0.4   | 2.414         | 2.097        |
| 4h        | EXTERNAL | EVENT_FALSE_BREAK     | 279   | YETERLI | %95.0  | %64.5   | %24.0    | %7.9      | %3.6 | %0.7   | 1.991         | 2.438        |
| 4h        | EXTERNAL | EVENT_SWEEP           | 7085  | YETERLI | %97.2  | %65.8   | %23.2    | %9.2      | %1.8 | %1.7   | 2.068         | 2.229        |
| 4h        | EXTERNAL | EVENT_TRANSITION_FAIL | 363   | YETERLI | %98.1  | %70.8   | %19.3    | %9.1      | %0.6 | %1.1   | 2.691         | 2.024        |
| 4h        | INTERNAL | EVENT_BOS             | 6645  | YETERLI | %97.0  | %68.3   | %20.9    | %9.1      | %1.0 | %1.6   | 2.413         | 2.082        |
| 4h        | INTERNAL | EVENT_CHOCH           | 2507  | YETERLI | %97.8  | %70.0   | %21.8    | %7.4      | %0.8 | %0.6   | 2.407         | 2.024        |
| 4h        | INTERNAL | EVENT_FALSE_BREAK     | 579   | YETERLI | %95.5  | %66.1   | %21.8    | %8.8      | %3.1 | %0.3   | 2.104         | 2.320        |
| 4h        | INTERNAL | EVENT_SWEEP           | 11109 | YETERLI | %97.4  | %64.2   | %24.3    | %9.9      | %1.3 | %1.4   | 1.970         | 2.282        |
| 4h        | INTERNAL | EVENT_TRANSITION_FAIL | 714   | YETERLI | %97.3  | %71.3   | %20.4    | %7.6      | %0.6 | %3.1   | 2.529         | 1.950        |

### Scope x yön (BOS/CHOCH ayrımıyla)

| timeframe | scope    | event_type  | direction | n    | guven   | uyumlu | CALISTI | AZ_DEVAM | DEVAM_YOK | TERS | sansur | ort_devam_h12 | ort_ters_h12 |
|-----------|----------|-------------|-----------|------|---------|--------|---------|----------|-----------|------|--------|---------------|--------------|
| 1d        | EXTERNAL | EVENT_BOS   | DOWN      | 928  | YETERLI | %95.4  | %60.1   | %27.3    | %8.4      | %2.7 | %5.5   | 1.747         | 2.075        |
| 1d        | EXTERNAL | EVENT_BOS   | UP        | 898  | YETERLI | %98.1  | %77.2   | %15.6    | %5.9      | %1.3 | %0.1   | 2.830         | 2.087        |
| 1d        | EXTERNAL | EVENT_CHOCH | DOWN      | 398  | YETERLI | %93.7  | %60.3   | %25.4    | %9.8      | %4.0 | %1.0   | 1.611         | 1.850        |
| 1d        | EXTERNAL | EVENT_CHOCH | UP        | 316  | YETERLI | %97.2  | %72.8   | %19.3    | %5.7      | %2.2 | %0.6   | 2.712         | 2.273        |
| 1d        | INTERNAL | EVENT_BOS   | DOWN      | 1710 | YETERLI | %93.2  | %60.3   | %27.1    | %6.8      | %3.1 | %6.5   | 1.754         | 1.987        |
| 1d        | INTERNAL | EVENT_BOS   | UP        | 1622 | YETERLI | %96.4  | %76.0   | %16.5    | %4.4      | %1.9 | %0.3   | 2.869         | 1.893        |
| 1d        | INTERNAL | EVENT_CHOCH | DOWN      | 658  | YETERLI | %93.6  | %56.5   | %27.1    | %12.6     | %3.3 | %1.1   | 1.488         | 2.049        |
| 1d        | INTERNAL | EVENT_CHOCH | UP        | 633  | YETERLI | %96.8  | %71.7   | %20.5    | %5.1      | %2.7 | %0.3   | 2.563         | 2.304        |
| 1h        | EXTERNAL | EVENT_BOS   | DOWN      | 4725 | YETERLI | %97.1  | %67.2   | %23.1    | %8.5      | %1.1 | %0.7   | 2.129         | 2.099        |
| 1h        | EXTERNAL | EVENT_BOS   | UP        | 4839 | YETERLI | %97.0  | %67.8   | %22.3    | %9.2      | %0.7 | %0.0   | 2.422         | 1.862        |
| 1h        | EXTERNAL | EVENT_CHOCH | DOWN      | 1869 | YETERLI | %97.4  | %67.0   | %24.1    | %7.6      | %1.2 | %0.3   | 2.111         | 1.877        |
| 1h        | EXTERNAL | EVENT_CHOCH | UP        | 1737 | YETERLI | %96.7  | %69.8   | %20.3    | %8.8      | %1.1 | %0.0   | 2.474         | 1.835        |
| 1h        | INTERNAL | EVENT_BOS   | DOWN      | 9232 | YETERLI | %97.2  | %67.3   | %23.3    | %7.9      | %1.2 | %0.8   | 2.120         | 2.030        |
| 1h        | INTERNAL | EVENT_BOS   | UP        | 8978 | YETERLI | %96.7  | %67.3   | %21.8    | %9.6      | %0.9 | %0.0   | 2.417         | 1.885        |
| 1h        | INTERNAL | EVENT_CHOCH | DOWN      | 3361 | YETERLI | %97.7  | %64.7   | %25.9    | %8.2      | %1.2 | %0.0   | 1.965         | 2.047        |
| 1h        | INTERNAL | EVENT_CHOCH | UP        | 3295 | YETERLI | %96.8  | %68.3   | %21.2    | %9.6      | %0.8 | %0.1   | 2.387         | 1.836        |
| 2h        | EXTERNAL | EVENT_BOS   | DOWN      | 2696 | YETERLI | %97.7  | %64.3   | %25.9    | %8.8      | %0.9 | %2.4   | 2.064         | 2.104        |
| 2h        | EXTERNAL | EVENT_BOS   | UP        | 2712 | YETERLI | %97.5  | %69.8   | %21.7    | %7.4      | %1.0 | %0.1   | 2.587         | 1.899        |
| 2h        | EXTERNAL | EVENT_CHOCH | DOWN      | 1098 | YETERLI | %97.8  | %64.7   | %25.0    | %9.6      | %0.7 | %0.4   | 2.000         | 2.010        |
| 2h        | EXTERNAL | EVENT_CHOCH | UP        | 1043 | YETERLI | %98.0  | %72.7   | %20.0    | %6.5      | %0.8 | %0.0   | 2.743         | 1.911        |
| 2h        | INTERNAL | EVENT_BOS   | DOWN      | 5241 | YETERLI | %97.6  | %65.1   | %24.7    | %9.3      | %0.6 | %1.7   | 2.025         | 2.102        |
| 2h        | INTERNAL | EVENT_BOS   | UP        | 5089 | YETERLI | %97.0  | %69.5   | %20.7    | %8.4      | %0.9 | %0.1   | 2.535         | 1.872        |
| 2h        | INTERNAL | EVENT_CHOCH | DOWN      | 1955 | YETERLI | %97.6  | %66.6   | %23.6    | %8.5      | %1.1 | %0.7   | 1.961         | 1.924        |
| 2h        | INTERNAL | EVENT_CHOCH | UP        | 1890 | YETERLI | %97.8  | %72.1   | %20.4    | %6.7      | %0.7 | %0.1   | 2.621         | 1.845        |
| 4h        | EXTERNAL | EVENT_BOS   | DOWN      | 1777 | YETERLI | %97.8  | %67.0   | %23.2    | %8.7      | %1.1 | %5.6   | 2.180         | 2.072        |
| 4h        | EXTERNAL | EVENT_BOS   | UP        | 1689 | YETERLI | %98.2  | %75.0   | %17.8    | %6.6      | %0.7 | %0.0   | 2.843         | 1.921        |
| 4h        | EXTERNAL | EVENT_CHOCH | DOWN      | 661  | YETERLI | %97.7  | %71.1   | %19.2    | %9.1      | %0.5 | %0.6   | 2.130         | 1.957        |
| 4h        | EXTERNAL | EVENT_CHOCH | UP        | 664  | YETERLI | %98.2  | %70.9   | %20.5    | %7.4      | %1.2 | %0.2   | 2.697         | 2.237        |
| 4h        | INTERNAL | EVENT_BOS   | DOWN      | 3454 | YETERLI | %97.0  | %64.6   | %23.2    | %10.6     | %1.2 | %3.1   | 2.065         | 2.147        |
| 4h        | INTERNAL | EVENT_BOS   | UP        | 3191 | YETERLI | %97.0  | %72.2   | %18.3    | %7.5      | %0.9 | %0.1   | 2.792         | 2.011        |
| 4h        | INTERNAL | EVENT_CHOCH | DOWN      | 1263 | YETERLI | %97.8  | %67.8   | %22.9    | %8.5      | %0.9 | %1.0   | 2.077         | 2.015        |
| 4h        | INTERNAL | EVENT_CHOCH | UP        | 1244 | YETERLI | %97.9  | %72.2   | %20.7    | %6.4      | %0.8 | %0.2   | 2.743         | 2.033        |

### Motorun kendi outcome kararı (çapraz kontrol)

| timeframe | scope    | outcome                  | n     | guven   | adet   |
|-----------|----------|--------------------------|-------|---------|--------|
| 1d        | EXTERNAL | FAILED                   | 361   | YETERLI | %100.0 |
| 1d        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 468   | YETERLI | %100.0 |
| 1d        | EXTERNAL | OBSERVED                 | 5600  | YETERLI | %100.0 |
| 1d        | EXTERNAL | PENDING                  | 38    | YETERLI | %100.0 |
| 1d        | INTERNAL | FAILED                   | 641   | YETERLI | %100.0 |
| 1d        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 856   | YETERLI | %100.0 |
| 1d        | INTERNAL | OBSERVED                 | 9596  | YETERLI | %100.0 |
| 1d        | INTERNAL | PENDING                  | 30    | YETERLI | %100.0 |
| 1h        | EXTERNAL | FAILED                   | 1644  | YETERLI | %100.0 |
| 1h        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 2615  | YETERLI | %100.0 |
| 1h        | EXTERNAL | OBSERVED                 | 30259 | YETERLI | %100.0 |
| 1h        | EXTERNAL | PENDING                  | 44    | YETERLI | %100.0 |
| 1h        | INTERNAL | FAILED                   | 3141  | YETERLI | %100.0 |
| 1h        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 4739  | YETERLI | %100.0 |
| 1h        | INTERNAL | OBSERVED                 | 51987 | YETERLI | %100.0 |
| 1h        | INTERNAL | PENDING                  | 26    | KISMI   | %100.0 |
| 2h        | EXTERNAL | FAILED                   | 1025  | YETERLI | %100.0 |
| 2h        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 1513  | YETERLI | %100.0 |
| 2h        | EXTERNAL | OBSERVED                 | 17717 | YETERLI | %100.0 |
| 2h        | EXTERNAL | PENDING                  | 24    | KISMI   | %100.0 |
| 2h        | INTERNAL | FAILED                   | 1749  | YETERLI | %100.0 |
| 2h        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 2761  | YETERLI | %100.0 |
| 2h        | INTERNAL | OBSERVED                 | 29093 | YETERLI | %100.0 |
| 2h        | INTERNAL | PENDING                  | 29    | KISMI   | %100.0 |
| 4h        | EXTERNAL | FAILED                   | 642   | YETERLI | %100.0 |
| 4h        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 933   | YETERLI | %100.0 |
| 4h        | EXTERNAL | OBSERVED                 | 10914 | YETERLI | %100.0 |
| 4h        | EXTERNAL | PENDING                  | 29    | KISMI   | %100.0 |
| 4h        | INTERNAL | FAILED                   | 1293  | YETERLI | %100.0 |
| 4h        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 1759  | YETERLI | %100.0 |
| 4h        | INTERNAL | OBSERVED                 | 18468 | YETERLI | %100.0 |
| 4h        | INTERNAL | PENDING                  | 34    | YETERLI | %100.0 |

## Soru 6 — PH/PL direnç/destek mi, çok denenen mi az denenen mi?
### Kararı verilebilir satırlar (sansürsüz)

| timeframe | scope    | rol | deneme_kovasi | n    | guven   | engelledi | engellemedi | ort_deneme_epizot | ort_deneme_bar | ort_rol_sure_bar | ort_bars_to_break |
|-----------|----------|-----|---------------|------|---------|-----------|-------------|-------------------|----------------|------------------|-------------------|
| 1d        | EXTERNAL | PH  | 0_deneme      | 683  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 35.801           | 66.776            |
| 1d        | EXTERNAL | PH  | 1_deneme      | 298  | YETERLI | %36.2     | %63.8       | 1.000             | 11.762         | 24.628           | 22.181            |
| 1d        | EXTERNAL | PH  | 2-3_deneme    | 200  | YETERLI | %22.0     | %78.0       | 2.325             | 15.990         | 19.410           | 18.946            |
| 1d        | EXTERNAL | PH  | 4plus_deneme  | 27   | KISMI   | %11.1     | %88.9       | 4.222             | 17.185         | 20.519           | 20.360            |
| 1d        | EXTERNAL | PL  | 0_deneme      | 725  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 39.611           | 69.481            |
| 1d        | EXTERNAL | PL  | 1_deneme      | 315  | YETERLI | %37.8     | %62.2       | 1.000             | 14.914         | 22.648           | 21.227            |
| 1d        | EXTERNAL | PL  | 2-3_deneme    | 234  | YETERLI | %28.6     | %71.4       | 2.321             | 15.158         | 22.064           | 22.298            |
| 1d        | EXTERNAL | PL  | 4plus_deneme  | 31   | YETERLI | %32.3     | %67.7       | 4.290             | 15.581         | 21.516           | 21.880            |
| 1d        | INTERNAL | PH  | 0_deneme      | 906  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 20.209           | 58.345            |
| 1d        | INTERNAL | PH  | 1_deneme      | 657  | YETERLI | %33.8     | %66.2       | 1.000             | 13.755         | 14.668           | 13.222            |
| 1d        | INTERNAL | PH  | 2-3_deneme    | 548  | YETERLI | %20.6     | %79.4       | 2.305             | 16.878         | 14.715           | 14.537            |
| 1d        | INTERNAL | PH  | 4plus_deneme  | 100  | YETERLI | %20.0     | %80.0       | 4.280             | 18.350         | 14.260           | 13.847            |
| 1d        | INTERNAL | PL  | 0_deneme      | 1036 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 20.572           | 58.862            |
| 1d        | INTERNAL | PL  | 1_deneme      | 658  | YETERLI | %38.3     | %61.7       | 1.000             | 15.679         | 15.807           | 14.554            |
| 1d        | INTERNAL | PL  | 2-3_deneme    | 605  | YETERLI | %29.9     | %70.1       | 2.344             | 16.301         | 15.752           | 16.234            |
| 1d        | INTERNAL | PL  | 4plus_deneme  | 101  | YETERLI | %26.7     | %73.3       | 4.376             | 16.762         | 16.020           | 16.608            |
| 1h        | EXTERNAL | PH  | 0_deneme      | 4186 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 46.643           | 79.274            |
| 1h        | EXTERNAL | PH  | 1_deneme      | 1468 | YETERLI | %34.9     | %65.1       | 1.000             | 13.246         | 30.858           | 24.711            |
| 1h        | EXTERNAL | PH  | 2-3_deneme    | 1024 | YETERLI | %22.4     | %77.6       | 2.339             | 14.879         | 24.869           | 23.431            |
| 1h        | EXTERNAL | PH  | 4plus_deneme  | 204  | YETERLI | %21.6     | %78.4       | 4.422             | 16.294         | 25.235           | 24.519            |
| 1h        | EXTERNAL | PL  | 0_deneme      | 4471 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 46.276           | 87.132            |
| 1h        | EXTERNAL | PL  | 1_deneme      | 1550 | YETERLI | %35.9     | %64.1       | 1.000             | 13.412         | 30.185           | 24.766            |
| 1h        | EXTERNAL | PL  | 2-3_deneme    | 915  | YETERLI | %30.3     | %69.7       | 2.293             | 14.231         | 25.603           | 25.701            |
| 1h        | EXTERNAL | PL  | 4plus_deneme  | 133  | YETERLI | %28.6     | %71.4       | 4.429             | 16.383         | 25.609           | 25.398            |
| 1h        | INTERNAL | PH  | 0_deneme      | 6063 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 24.326           | 71.958            |
| 1h        | INTERNAL | PH  | 1_deneme      | 3454 | YETERLI | %34.7     | %65.3       | 1.000             | 15.246         | 16.319           | 14.570            |
| 1h        | INTERNAL | PH  | 2-3_deneme    | 3031 | YETERLI | %23.7     | %76.3       | 2.340             | 16.149         | 17.022           | 16.757            |
| 1h        | INTERNAL | PH  | 4plus_deneme  | 681  | YETERLI | %16.2     | %83.8       | 4.441             | 17.460         | 17.019           | 16.849            |
| 1h        | INTERNAL | PL  | 0_deneme      | 6489 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 23.927           | 93.482            |
| 1h        | INTERNAL | PL  | 1_deneme      | 3577 | YETERLI | %34.1     | %65.9       | 1.000             | 15.156         | 21.174           | 18.707            |
| 1h        | INTERNAL | PL  | 2-3_deneme    | 2661 | YETERLI | %27.4     | %72.6       | 2.309             | 16.775         | 18.189           | 18.014            |
| 1h        | INTERNAL | PL  | 4plus_deneme  | 453  | YETERLI | %28.7     | %71.3       | 4.395             | 17.422         | 17.876           | 17.576            |
| 2h        | EXTERNAL | PH  | 0_deneme      | 2369 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 43.171           | 72.938            |
| 2h        | EXTERNAL | PH  | 1_deneme      | 786  | YETERLI | %31.8     | %68.2       | 1.000             | 13.977         | 26.145           | 23.071            |
| 2h        | EXTERNAL | PH  | 2-3_deneme    | 633  | YETERLI | %24.0     | %76.0       | 2.344             | 14.491         | 25.425           | 24.031            |
| 2h        | EXTERNAL | PH  | 4plus_deneme  | 145  | YETERLI | %14.5     | %85.5       | 4.414             | 16.041         | 23.903           | 19.667            |
| 2h        | EXTERNAL | PL  | 0_deneme      | 2596 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 44.242           | 79.294            |
| 2h        | EXTERNAL | PL  | 1_deneme      | 824  | YETERLI | %35.2     | %64.8       | 1.000             | 13.414         | 31.405           | 25.028            |
| 2h        | EXTERNAL | PL  | 2-3_deneme    | 556  | YETERLI | %30.6     | %69.4       | 2.281             | 14.408         | 27.061           | 25.069            |
| 2h        | EXTERNAL | PL  | 4plus_deneme  | 78   | YETERLI | %34.6     | %65.4       | 4.256             | 15.679         | 25.141           | 24.312            |
| 2h        | INTERNAL | PH  | 0_deneme      | 3376 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 23.934           | 63.070            |
| 2h        | INTERNAL | PH  | 1_deneme      | 1931 | YETERLI | %33.8     | %66.2       | 1.000             | 15.705         | 18.020           | 15.679            |
| 2h        | INTERNAL | PH  | 2-3_deneme    | 1803 | YETERLI | %23.2     | %76.8       | 2.354             | 16.515         | 16.223           | 16.253            |
| 2h        | INTERNAL | PH  | 4plus_deneme  | 411  | YETERLI | %17.5     | %82.5       | 4.523             | 17.745         | 17.433           | 16.658            |
| 2h        | INTERNAL | PL  | 0_deneme      | 3644 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 22.075           | 64.686            |
| 2h        | INTERNAL | PL  | 1_deneme      | 2009 | YETERLI | %35.5     | %64.5       | 1.000             | 15.649         | 19.781           | 17.026            |
| 2h        | INTERNAL | PL  | 2-3_deneme    | 1557 | YETERLI | %26.9     | %73.1       | 2.292             | 16.852         | 18.306           | 18.396            |
| 2h        | INTERNAL | PL  | 4plus_deneme  | 257  | YETERLI | %26.5     | %73.5       | 4.362             | 17.739         | 20.074           | 19.416            |
| 4h        | EXTERNAL | PH  | 0_deneme      | 1498 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 42.900           | 77.034            |
| 4h        | EXTERNAL | PH  | 1_deneme      | 493  | YETERLI | %31.6     | %68.4       | 1.000             | 12.521         | 30.469           | 25.797            |
| 4h        | EXTERNAL | PH  | 2-3_deneme    | 402  | YETERLI | %22.9     | %77.1       | 2.306             | 14.055         | 23.062           | 22.648            |
| 4h        | EXTERNAL | PH  | 4plus_deneme  | 95   | YETERLI | %16.8     | %83.2       | 4.621             | 16.884         | 20.526           | 20.000            |
| 4h        | EXTERNAL | PL  | 0_deneme      | 1587 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 40.951           | 68.957            |
| 4h        | EXTERNAL | PL  | 1_deneme      | 502  | YETERLI | %33.9     | %66.1       | 1.000             | 13.691         | 27.010           | 24.024            |
| 4h        | EXTERNAL | PL  | 2-3_deneme    | 366  | YETERLI | %21.6     | %78.4       | 2.284             | 15.899         | 25.544           | 22.654            |
| 4h        | EXTERNAL | PL  | 4plus_deneme  | 52   | YETERLI | %17.3     | %82.7       | 4.365             | 16.846         | 23.077           | 22.000            |
| 4h        | INTERNAL | PH  | 0_deneme      | 2117 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 20.696           | 60.490            |
| 4h        | INTERNAL | PH  | 1_deneme      | 1204 | YETERLI | %29.9     | %70.1       | 1.000             | 15.317         | 16.650           | 14.447            |
| 4h        | INTERNAL | PH  | 2-3_deneme    | 1210 | YETERLI | %21.9     | %78.1       | 2.327             | 16.412         | 15.971           | 16.027            |
| 4h        | INTERNAL | PH  | 4plus_deneme  | 332  | YETERLI | %19.0     | %81.0       | 4.599             | 17.687         | 15.699           | 15.389            |
| 4h        | INTERNAL | PL  | 0_deneme      | 2277 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 21.746           | 57.524            |
| 4h        | INTERNAL | PL  | 1_deneme      | 1253 | YETERLI | %37.2     | %62.8       | 1.000             | 15.330         | 17.970           | 17.484            |
| 4h        | INTERNAL | PL  | 2-3_deneme    | 1016 | YETERLI | %27.7     | %72.3       | 2.325             | 16.793         | 17.580           | 18.061            |
| 4h        | INTERNAL | PL  | 4plus_deneme  | 184  | YETERLI | %22.3     | %77.7       | 4.380             | 17.777         | 16.277           | 16.323            |

### Karar verilemeyen satırlar (sağdan sansürlü — payda dışı)

| timeframe | scope    | rol | deneme_kovasi | n   | guven   | ort_deneme_epizot | ort_rol_sure_bar |
|-----------|----------|-----|---------------|-----|---------|-------------------|------------------|
| 1d        | EXTERNAL | PH  | 0_deneme      | 218 | YETERLI | 0.000             | 15.252           |
| 1d        | EXTERNAL | PH  | 1_deneme      | 3   | ZAYIF   | 1.000             | 20.333           |
| 1d        | EXTERNAL | PH  | 2-3_deneme    | 3   | ZAYIF   | 2.333             | 24.667           |
| 1d        | EXTERNAL | PL  | 0_deneme      | 10  | ZAYIF   | 0.000             | 18.900           |
| 1d        | EXTERNAL | PL  | 2-3_deneme    | 1   | ZAYIF   | 2.000             | 27.000           |
| 1d        | INTERNAL | PH  | 0_deneme      | 341 | YETERLI | 0.000             | 10.777           |
| 1d        | INTERNAL | PH  | 1_deneme      | 32  | YETERLI | 1.000             | 12.125           |
| 1d        | INTERNAL | PH  | 2-3_deneme    | 19  | KISMI   | 2.158             | 10.947           |
| 1d        | INTERNAL | PL  | 0_deneme      | 15  | KISMI   | 0.000             | 13.400           |
| 1d        | INTERNAL | PL  | 1_deneme      | 5   | ZAYIF   | 1.000             | 11.600           |
| 1d        | INTERNAL | PL  | 2-3_deneme    | 4   | ZAYIF   | 2.000             | 17.750           |
| 1d        | INTERNAL | PL  | 4plus_deneme  | 1   | ZAYIF   | 5.000             | 7.000            |
| 1h        | EXTERNAL | PH  | 0_deneme      | 155 | YETERLI | 0.000             | 16.632           |
| 1h        | EXTERNAL | PH  | 1_deneme      | 4   | ZAYIF   | 1.000             | 23.500           |
| 1h        | EXTERNAL | PH  | 2-3_deneme    | 1   | ZAYIF   | 2.000             | 19.000           |
| 1h        | EXTERNAL | PL  | 0_deneme      | 5   | ZAYIF   | 0.000             | 20.200           |
| 1h        | EXTERNAL | PL  | 1_deneme      | 1   | ZAYIF   | 1.000             | 25.000           |
| 1h        | INTERNAL | PH  | 0_deneme      | 262 | YETERLI | 0.000             | 9.118            |
| 1h        | INTERNAL | PH  | 1_deneme      | 56  | YETERLI | 1.000             | 10.946           |
| 1h        | INTERNAL | PH  | 2-3_deneme    | 13  | ZAYIF   | 2.077             | 13.308           |
| 1h        | INTERNAL | PL  | 0_deneme      | 10  | ZAYIF   | 0.000             | 11.800           |
| 1h        | INTERNAL | PL  | 1_deneme      | 5   | ZAYIF   | 1.000             | 10.400           |
| 1h        | INTERNAL | PL  | 2-3_deneme    | 2   | ZAYIF   | 2.500             | 20.500           |
| 2h        | EXTERNAL | PH  | 0_deneme      | 148 | YETERLI | 0.000             | 13.088           |
| 2h        | EXTERNAL | PH  | 1_deneme      | 3   | ZAYIF   | 1.000             | 22.667           |
| 2h        | EXTERNAL | PH  | 2-3_deneme    | 3   | ZAYIF   | 2.000             | 17.667           |
| 2h        | EXTERNAL | PL  | 0_deneme      | 11  | ZAYIF   | 0.000             | 21.000           |
| 2h        | EXTERNAL | PL  | 1_deneme      | 1   | ZAYIF   | 1.000             | 31.000           |
| 2h        | INTERNAL | PH  | 0_deneme      | 204 | YETERLI | 0.000             | 9.333            |
| 2h        | INTERNAL | PH  | 1_deneme      | 10  | ZAYIF   | 1.000             | 13.000           |
| 2h        | INTERNAL | PH  | 2-3_deneme    | 3   | ZAYIF   | 2.333             | 21.000           |
| 2h        | INTERNAL | PL  | 0_deneme      | 14  | ZAYIF   | 0.000             | 15.571           |
| 2h        | INTERNAL | PL  | 1_deneme      | 9   | ZAYIF   | 1.000             | 10.556           |
| 2h        | INTERNAL | PL  | 2-3_deneme    | 2   | ZAYIF   | 2.500             | 30.000           |
| 4h        | EXTERNAL | PH  | 0_deneme      | 147 | YETERLI | 0.000             | 8.959            |
| 4h        | EXTERNAL | PH  | 1_deneme      | 2   | ZAYIF   | 1.000             | 19.500           |
| 4h        | EXTERNAL | PH  | 2-3_deneme    | 1   | ZAYIF   | 3.000             | 29.000           |
| 4h        | EXTERNAL | PL  | 0_deneme      | 9   | ZAYIF   | 0.000             | 23.111           |
| 4h        | INTERNAL | PH  | 0_deneme      | 207 | YETERLI | 0.000             | 8.469            |
| 4h        | INTERNAL | PH  | 1_deneme      | 10  | ZAYIF   | 1.000             | 13.000           |
| 4h        | INTERNAL | PH  | 2-3_deneme    | 10  | ZAYIF   | 2.200             | 19.000           |
| 4h        | INTERNAL | PH  | 4plus_deneme  | 1   | ZAYIF   | 4.000             | 17.000           |
| 4h        | INTERNAL | PL  | 0_deneme      | 27  | KISMI   | 0.000             | 16.556           |
| 4h        | INTERNAL | PL  | 1_deneme      | 11  | ZAYIF   | 1.000             | 18.091           |
| 4h        | INTERNAL | PL  | 2-3_deneme    | 7   | ZAYIF   | 2.286             | 19.571           |

### Yaklaşma eşiği duyarlılığı (0.25 ana; 0.15 / 0.50 kontrol)

| esik     | timeframe | n_satir | guven   | engelledi_orani | kararsiz_adet |
|----------|-----------|---------|---------|-----------------|---------------|
| 0.25 ATR | 1d        | 7776    | YETERLI | %63.4           | 652           |
| 0.25 ATR | 1h        | 40874   | YETERLI | %66.8           | 514           |
| 0.25 ATR | 2h        | 23383   | YETERLI | %66.3           | 408           |
| 0.25 ATR | 4h        | 15020   | YETERLI | %65.0           | 432           |
| 0.15 ATR | 1d        | 7776    | YETERLI | %59.9           | 652           |
| 0.15 ATR | 1h        | 40874   | YETERLI | %64.6           | 514           |
| 0.15 ATR | 2h        | 23383   | YETERLI | %63.7           | 408           |
| 0.15 ATR | 4h        | 15020   | YETERLI | %62.4           | 432           |
| 0.5 ATR  | 1d        | 7776    | YETERLI | %72.5           | 652           |
| 0.5 ATR  | 1h        | 40874   | YETERLI | %74.1           | 514           |
| 0.5 ATR  | 2h        | 23383   | YETERLI | %73.8           | 408           |
| 0.5 ATR  | 4h        | 15020   | YETERLI | %72.6           | 432           |

## Soru 7 — WH/WL %kaçı ziyaret/süpürüldü, ne kadar sürede?
| timeframe | scope    | rol | n     | guven   | ziyaret_epizot | supuruldu | hic_ulasilmadi | sansur | ort_deneme_epizot |
|-----------|----------|-----|-------|---------|----------------|-----------|----------------|--------|-------------------|
| 1d        | EXTERNAL | WH  | 1777  | YETERLI | %65.4          | %56.4     | %43.6          | %5.5   | 1.214             |
| 1d        | EXTERNAL | WL  | 1647  | YETERLI | %73.8          | %63.8     | %36.2          | %12.1  | 1.424             |
| 1d        | INTERNAL | WH  | 3882  | YETERLI | %77.6          | %66.9     | %33.1          | %4.2   | 1.530             |
| 1d        | INTERNAL | WL  | 3845  | YETERLI | %81.7          | %71.0     | %29.0          | %11.9  | 1.559             |
| 1h        | EXTERNAL | WH  | 12058 | YETERLI | %68.2          | %56.4     | %43.6          | %0.8   | 1.345             |
| 1h        | EXTERNAL | WL  | 11653 | YETERLI | %71.3          | %60.8     | %39.2          | %1.3   | 1.289             |
| 1h        | INTERNAL | WH  | 26207 | YETERLI | %76.8          | %63.0     | %37.0          | %0.6   | 1.552             |
| 1h        | INTERNAL | WL  | 24837 | YETERLI | %80.5          | %68.9     | %31.1          | %1.7   | 1.500             |
| 2h        | EXTERNAL | WH  | 6784  | YETERLI | %67.8          | %57.0     | %43.0          | %1.0   | 1.376             |
| 2h        | EXTERNAL | WL  | 6101  | YETERLI | %71.4          | %60.4     | %39.6          | %2.8   | 1.297             |
| 2h        | INTERNAL | WH  | 13571 | YETERLI | %76.8          | %63.9     | %36.1          | %1.5   | 1.623             |
| 2h        | INTERNAL | WL  | 13237 | YETERLI | %80.2          | %69.8     | %30.2          | %2.2   | 1.505             |
| 4h        | EXTERNAL | WH  | 3957  | YETERLI | %70.4          | %59.3     | %40.7          | %1.1   | 1.443             |
| 4h        | EXTERNAL | WL  | 4211  | YETERLI | %71.1          | %60.6     | %39.4          | %6.7   | 1.327             |
| 4h        | INTERNAL | WH  | 8538  | YETERLI | %77.2          | %65.4     | %34.6          | %1.8   | 1.687             |
| 4h        | INTERNAL | WL  | 8362  | YETERLI | %80.8          | %69.9     | %30.1          | %5.0   | 1.565             |

### Seviyeye ulaşma süresi (native bar; rol atamasından itibaren)

| timeframe | rol | n     | guven   | q25   | ortanca | q75   | ortalama |
|-----------|-----|-------|---------|-------|---------|-------|----------|
| 1d        | WH  | 1792  | YETERLI | 1.000 | 3.000   | 5.000 | 4.900    |
| 1d        | WL  | 1879  | YETERLI | 1.000 | 3.000   | 6.000 | 4.700    |
| 1h        | WH  | 10610 | YETERLI | 1.000 | 3.000   | 6.000 | 5.600    |
| 1h        | WL  | 11199 | YETERLI | 2.000 | 3.000   | 7.000 | 6.100    |
| 2h        | WH  | 5912  | YETERLI | 1.000 | 3.000   | 6.000 | 5.400    |
| 2h        | WL  | 6183  | YETERLI | 2.000 | 3.000   | 7.000 | 5.600    |
| 4h        | WH  | 3854  | YETERLI | 1.000 | 3.000   | 6.000 | 5.100    |
| 4h        | WL  | 4287  | YETERLI | 1.000 | 3.000   | 6.000 | 5.400    |

### EVENT_SWEEP çapraz kontrolü
| timeframe | scope    | direction | n     | guven   | uyumlu | CALISTI | ort_devam_h12 |
|-----------|----------|-----------|-------|---------|--------|---------|---------------|
| 1d        | EXTERNAL | DOWN      | 2090  | YETERLI | %95.8  | %65.0   | 1.929         |
| 1d        | EXTERNAL | UP        | 1476  | YETERLI | %95.9  | %67.7   | 2.069         |
| 1d        | INTERNAL | DOWN      | 3575  | YETERLI | %96.0  | %65.0   | 1.923         |
| 1d        | INTERNAL | UP        | 2284  | YETERLI | %95.8  | %64.8   | 2.141         |
| 1h        | EXTERNAL | DOWN      | 10935 | YETERLI | %97.4  | %63.1   | 1.761         |
| 1h        | EXTERNAL | UP        | 8813  | YETERLI | %96.1  | %62.0   | 2.033         |
| 1h        | INTERNAL | DOWN      | 17471 | YETERLI | %97.4  | %63.1   | 1.808         |
| 1h        | INTERNAL | UP        | 14415 | YETERLI | %96.3  | %62.6   | 2.063         |
| 2h        | EXTERNAL | DOWN      | 6782  | YETERLI | %97.9  | %64.3   | 1.871         |
| 2h        | EXTERNAL | UP        | 4923  | YETERLI | %96.2  | %63.3   | 2.072         |
| 2h        | INTERNAL | DOWN      | 10138 | YETERLI | %98.1  | %64.1   | 1.797         |
| 2h        | INTERNAL | UP        | 7570  | YETERLI | %96.3  | %62.9   | 2.038         |
| 4h        | EXTERNAL | DOWN      | 4106  | YETERLI | %98.4  | %66.7   | 2.011         |
| 4h        | EXTERNAL | UP        | 2979  | YETERLI | %95.5  | %64.7   | 2.145         |
| 4h        | INTERNAL | DOWN      | 6533  | YETERLI | %98.2  | %64.1   | 1.873         |
| 4h        | INTERNAL | UP        | 4576  | YETERLI | %96.3  | %64.4   | 2.108         |

## Hacim — koşullandırma değişkeni
### Dokunuş tepkisi x hacim çeyreği (rvol)

| timeframe | hacim_kovasi | n     | guven   | tepki_CALISTI | ort_yon_h12 | ort_pay_5 | ort_h12_decay | ort_rvol |
|-----------|--------------|-------|---------|---------------|-------------|-----------|---------------|----------|
| 1d        | KULLANILAMAZ | 6269  | YETERLI | %65.1         | 2.059       | 0.539     | 2.138         | -        |
| 1d        | Q1_dusuk     | 3489  | YETERLI | %63.9         | 1.884       | 0.657     | 1.738         | 0.503    |
| 1d        | Q2           | 7079  | YETERLI | %67.7         | 2.060       | 0.391     | 2.409         | 0.882    |
| 1d        | Q3           | 4923  | YETERLI | %63.6         | 1.940       | 0.557     | 2.462         | 1.411    |
| 1d        | Q4_yuksek    | 3086  | YETERLI | %62.0         | 1.821       | 0.495     | 1.828         | 2.972    |
| 1h        | KULLANILAMAZ | 4328  | YETERLI | %63.6         | 1.870       | 0.568     | 2.591         | -        |
| 1h        | Q1_dusuk     | 28912 | YETERLI | %66.6         | 1.988       | 0.567     | 1.674         | 0.124    |
| 1h        | Q2           | 15425 | YETERLI | %71.9         | 2.255       | 0.695     | 1.508         | 0.897    |
| 1h        | Q3           | 18341 | YETERLI | %67.3         | 2.095       | 0.650     | 1.796         | 1.448    |
| 1h        | Q4_yuksek    | 23479 | YETERLI | %61.3         | 1.811       | 0.587     | 1.837         | 3.501    |
| 2h        | KULLANILAMAZ | 5184  | YETERLI | %63.5         | 1.971       | 0.626     | 2.694         | -        |
| 2h        | Q1_dusuk     | 15803 | YETERLI | %69.6         | 2.169       | 0.669     | 1.633         | 0.470    |
| 2h        | Q2           | 20880 | YETERLI | %67.8         | 2.094       | 0.666     | 1.719         | 0.882    |
| 2h        | Q3           | 17949 | YETERLI | %65.9         | 2.051       | 0.634     | 1.907         | 1.431    |
| 2h        | Q4_yuksek    | 16451 | YETERLI | %60.4         | 1.808       | 0.577     | 1.932         | 3.295    |
| 4h        | KULLANILAMAZ | 4927  | YETERLI | %64.2         | 2.018       | 0.588     | 1.968         | -        |
| 4h        | Q1_dusuk     | 6740  | YETERLI | %70.1         | 2.272       | 0.682     | 1.899         | 0.427    |
| 4h        | Q2           | 11561 | YETERLI | %67.7         | 2.115       | 0.620     | 1.710         | 0.901    |
| 4h        | Q3           | 13730 | YETERLI | %66.1         | 2.081       | 0.582     | 1.803         | 1.437    |
| 4h        | Q4_yuksek    | 11928 | YETERLI | %61.0         | 1.868       | 0.513     | 1.774         | 3.173    |

### MS event devamlılığı x hacim çeyreği

| timeframe | hacim_kovasi | n     | guven   | CALISTI | uyumlu | ort_devam_h12 |
|-----------|--------------|-------|---------|---------|--------|---------------|
| 1d        | KULLANILAMAZ | 5028  | YETERLI | %65.7   | %94.8  | 2.132         |
| 1d        | Q1_dusuk     | 2368  | YETERLI | %63.0   | %95.4  | 1.811         |
| 1d        | Q2           | 4710  | YETERLI | %66.2   | %96.3  | 2.006         |
| 1d        | Q3           | 3377  | YETERLI | %65.1   | %96.2  | 2.161         |
| 1d        | Q4_yuksek    | 2107  | YETERLI | %72.7   | %96.3  | 2.447         |
| 1h        | KULLANILAMAZ | 5374  | YETERLI | %64.4   | %96.3  | 2.042         |
| 1h        | Q1_dusuk     | 27108 | YETERLI | %64.0   | %97.3  | 1.980         |
| 1h        | Q2           | 18815 | YETERLI | %64.4   | %96.6  | 2.008         |
| 1h        | Q3           | 20237 | YETERLI | %64.7   | %96.9  | 2.065         |
| 1h        | Q4_yuksek    | 22921 | YETERLI | %66.1   | %97.1  | 2.199         |
| 2h        | KULLANILAMAZ | 4634  | YETERLI | %65.0   | %96.3  | 2.164         |
| 2h        | Q1_dusuk     | 10413 | YETERLI | %64.1   | %96.7  | 1.979         |
| 2h        | Q2           | 14409 | YETERLI | %64.3   | %97.3  | 1.984         |
| 2h        | Q3           | 12609 | YETERLI | %65.9   | %97.9  | 2.074         |
| 2h        | Q4_yuksek    | 11846 | YETERLI | %68.2   | %97.8  | 2.322         |
| 4h        | KULLANILAMAZ | 4504  | YETERLI | %65.1   | %96.3  | 2.178         |
| 4h        | Q1_dusuk     | 5233  | YETERLI | %66.1   | %95.9  | 2.122         |
| 4h        | Q2           | 7189  | YETERLI | %66.1   | %97.5  | 2.117         |
| 4h        | Q3           | 8898  | YETERLI | %66.7   | %98.1  | 2.137         |
| 4h        | Q4_yuksek    | 8248  | YETERLI | %69.5   | %97.9  | 2.410         |
