# Formation-Bot Arşiv Araştırma Raporu
> Bu dosya tablo ekidir: ham aggregatlar soru başına bölümlenir.
> Okunabilir özet ve yorum: `docs/arastirma/ARASTIRMA_SONUCLARI.md`.
> Yalnız karar için okuyan, aşağıdaki tablolara inmeden özetle yetinebilir.
Kaynak: `backfill_data/` (365 gün derin çekim) · Sembol: 176 · Havuz dışı: BRENT

## Kapsam
| timeframe | sembol | ort_bar | toplam_zone | toplam_epizot | toplam_swing | toplam_event | toplam_rol_araligi | ms_hatali_seri |
|-----------|--------|---------|-------------|---------------|--------------|--------------|--------------------|----------------|
| 1d        | 176    | 501     | 22331       | 24863         | 32466        | 17409        | 23481              | 0              |
| 1h        | 176    | 3212    | 59377       | 90495         | 200899       | 94119        | 142858             | 0              |
| 2h        | 176    | 1499    | 53658       | 62958         | 93805        | 45728        | 67335              | 0              |
| 4h        | 176    | 1496    | 59173       | 69590         | 96096        | 47905        | 69722              | 0              |

## Yöntem notları
- Ölçüm birimi **çapa sonrası** barlardır; çapa barının kendisi hiçbir uzanıma katılmaz (anti-lookahead).
- Tüm uzanımlar **ATR cinsindendir**; TL/% kullanılmaz çünkü BIST 5-500 TL aralığında hisse barındırır.
- `sansur` alanı pencerenin veri sonuna takıldığını gösterir; sansürlü gözlem başarı sayılmaz.
- OB popülasyonu `replay_ob_zones` ile yeniden kurulur: motor dolan zone'ları listesinden sildiği için final snapshot yalnız hayatta kalanları verir.
- PH/PL/WH/WL rolleri bar bar izlenir: `structural_role` zamanla mutate olur ve final değer tarihsel atamaları kaybetmiştir.
- `TUM_ZONE`/`ZONE_ICI` temaslarında kenar-ancored yön belirlenemez; bunlar `OLCULEMEDI` kovasında ayrı raporlanır, düşürülmez.
- Güven etiketi: n>=30 YETERLI, n>=15 KISMI, altı ZAYIF (`analytics/backtest.py` ile aynı eşikler).
- Native arşiv: 2h/4h 1h'den resample EDİLMEZ; eksik native dosya ölçüm hatası olarak yazılır.
- Kaynak/TF: 1h=yahoo, 2h=tvdatafeed, 4h=tvdatafeed, 1d=yahoo (arsiv_modu=native).

## Soru 1 — OB/FVG tek denemede mi çok denemede mi?
| timeframe | family | n     | guven   | tek_deneme | 2_deneme | 3plus_deneme | hic_deneme | ort_epizot |
|-----------|--------|-------|---------|------------|----------|--------------|------------|------------|
| 1d        | FVG    | 8694  | YETERLI | %71.1      | %0.7     | %0.0         | %28.2      | 0.725      |
| 1d        | OB     | 13637 | YETERLI | %59.6      | %19.1    | %10.5        | %10.7      | 1.361      |
| 1h        | OB     | 59377 | YETERLI | %59.9      | %21.1    | %13.3        | %5.6       | 1.524      |
| 2h        | FVG    | 22580 | YETERLI | %75.2      | %0.7     | %0.0         | %24.1      | 0.766      |
| 2h        | OB     | 31078 | YETERLI | %59.6      | %20.8    | %12.3        | %7.4       | 1.469      |
| 4h        | FVG    | 25735 | YETERLI | %76.1      | %0.8     | %0.0         | %23.0      | 0.778      |
| 4h        | OB     | 33438 | YETERLI | %59.9      | %20.4    | %12.7        | %7.0       | 1.482      |

## Soru 2 — %kaçı geçildi, %kaçı tepki aldı?
### Zone seviyesi: temas / geçilme / dolum

| timeframe | family | n     | guven   | temas_var | gecildi_violation | full_fill | sansur_payi | ort_omur_bar | ort_yukseklik_atr |
|-----------|--------|-------|---------|-----------|-------------------|-----------|-------------|--------------|-------------------|
| 1d        | FVG    | 8694  | YETERLI | %71.8     | %0.0              | %40.4     | %1.7        | 5.452        | 0.630             |
| 1d        | OB     | 13637 | YETERLI | %89.3     | %85.2             | %0.0      | %14.8       | 33.761       | 0.959             |
| 1h        | OB     | 59377 | YETERLI | %94.4     | %93.3             | %0.0      | %6.7        | 94.656       | 0.948             |
| 2h        | FVG    | 22580 | YETERLI | %75.9     | %0.0              | %40.2     | %0.4        | 5.738        | 0.677             |
| 2h        | OB     | 31078 | YETERLI | %92.6     | %90.4             | %0.0      | %9.6        | 57.538       | 0.949             |
| 4h        | FVG    | 25735 | YETERLI | %77.0     | %0.0              | %40.9     | %0.4        | 5.245        | 0.724             |
| 4h        | OB     | 33438 | YETERLI | %93.0     | %91.4             | %0.0      | %8.6        | 60.128       | 0.962             |

### Dokunuş seviyesi: beklenen yönde tepki (zone yönü)

| timeframe | family | n     | guven   | yon_tepki_CALISTI | yon_tepki_AZ | yon_tepki_YOK | yon_tepki_TERS | ort_yon_h12_atr | ort_yon_uzun_tepe_h40 |
|-----------|--------|-------|---------|-------------------|--------------|---------------|----------------|-----------------|-----------------------|
| 1d        | FVG    | 6299  | YETERLI | %64.8             | %17.5        | %4.8          | %12.6          | 1.954           | 3.929                 |
| 1d        | OB     | 18564 | YETERLI | %64.8             | %15.1        | %4.4          | %14.7          | 1.978           | 3.758                 |
| 1h        | OB     | 90495 | YETERLI | %66.1             | %15.1        | %4.8          | %13.9          | 2.000           | 3.834                 |
| 2h        | FVG    | 17298 | YETERLI | %65.9             | %18.7        | %4.6          | %10.8          | 2.084           | 4.021                 |
| 2h        | OB     | 45660 | YETERLI | %65.2             | %15.2        | %4.7          | %14.6          | 1.949           | 3.767                 |
| 4h        | FVG    | 20019 | YETERLI | %66.4             | %17.4        | %4.4          | %11.7          | 2.083           | 3.990                 |
| 4h        | OB     | 49571 | YETERLI | %64.9             | %15.2        | %4.5          | %15.1          | 1.965           | 3.883                 |

## Soru 3 — Kenar-ancored tepki (ATR)
| timeframe | family | dokunulan_kenar | n     | guven   | tepki_CALISTI | tepki_AZ | tepki_YOK | tepki_TERS | OLCULEMEDI | ort_kenar_h12 | ort_kenar_tepe | ort_kenar_uzun_tepe |
|-----------|--------|-----------------|-------|---------|---------------|----------|-----------|------------|------------|---------------|----------------|---------------------|
| 1d        | FVG    | ALT_KENAR       | 2089  | YETERLI | %55.7         | %18.4    | %6.9      | %18.9      | %0.1       | 1.833         | 1.833          | 4.039               |
| 1d        | FVG    | TUM_ZONE        | 2071  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1d        | FVG    | UST_KENAR       | 2091  | YETERLI | %62.4         | %17.7    | %5.5      | %13.8      | %0.6       | 1.843         | 1.843          | 3.253               |
| 1d        | FVG    | ZONE_ICI        | 48    | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1d        | OB     | ALT_KENAR       | 7444  | YETERLI | %62.0         | %13.3    | %4.2      | %19.9      | %0.5       | 2.147         | 2.147          | 4.456               |
| 1d        | OB     | TUM_ZONE        | 2669  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1d        | OB     | UST_KENAR       | 8238  | YETERLI | %59.5         | %17.7    | %5.1      | %16.3      | %1.4       | 1.726         | 1.726          | 3.232               |
| 1d        | OB     | ZONE_ICI        | 213   | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1h        | OB     | ALT_KENAR       | 34330 | YETERLI | %57.9         | %15.3    | %6.0      | %20.7      | %0.1       | 1.973         | 1.973          | 4.092               |
| 1h        | OB     | TUM_ZONE        | 19471 | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1h        | OB     | UST_KENAR       | 36449 | YETERLI | %59.1         | %16.4    | %6.0      | %18.4      | %0.1       | 1.782         | 1.782          | 3.581               |
| 1h        | OB     | ZONE_ICI        | 245   | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 2h        | FVG    | ALT_KENAR       | 5565  | YETERLI | %53.0         | %18.6    | %8.4      | %19.8      | %0.1       | 1.680         | 1.680          | 3.627               |
| 2h        | FVG    | TUM_ZONE        | 5877  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 2h        | FVG    | UST_KENAR       | 5764  | YETERLI | %55.0         | %20.1    | %7.9      | %16.9      | %0.0       | 1.565         | 1.565          | 3.377               |
| 2h        | FVG    | ZONE_ICI        | 92    | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 2h        | OB     | ALT_KENAR       | 17635 | YETERLI | %57.7         | %15.8    | %5.6      | %20.5      | %0.4       | 1.929         | 1.929          | 3.945               |
| 2h        | OB     | TUM_ZONE        | 8974  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 2h        | OB     | UST_KENAR       | 18889 | YETERLI | %60.7         | %15.9    | %5.4      | %17.7      | %0.4       | 1.847         | 1.847          | 3.638               |
| 2h        | OB     | ZONE_ICI        | 162   | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 4h        | FVG    | ALT_KENAR       | 6642  | YETERLI | %54.1         | %17.9    | %8.5      | %19.4      | %0.1       | 1.770         | 1.770          | 4.029               |
| 4h        | FVG    | TUM_ZONE        | 6823  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 4h        | FVG    | UST_KENAR       | 6424  | YETERLI | %57.7         | %18.5    | %6.8      | %16.9      | %0.1       | 1.685         | 1.685          | 3.477               |
| 4h        | FVG    | ZONE_ICI        | 130   | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 4h        | OB     | ALT_KENAR       | 19077 | YETERLI | %59.9         | %15.2    | %5.3      | %19.2      | %0.4       | 2.086         | 2.086          | 4.264               |
| 4h        | OB     | TUM_ZONE        | 10289 | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 4h        | OB     | UST_KENAR       | 19940 | YETERLI | %60.5         | %15.6    | %5.3      | %18.1      | %0.4       | 1.833         | 1.833          | 3.446               |
| 4h        | OB     | ZONE_ICI        | 265   | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |

### Kenar-ancored: ATR eşik ızgarası aşım oranı (h12)

| timeframe | n     | guven   | >=0.25 ATR | >=0.5 ATR | >=1 ATR | >=1.5 ATR | >=2 ATR |
|-----------|-------|---------|------------|-----------|---------|-----------|---------|
| 1d        | 24863 | YETERLI | %77.1      | %72.1     | %60.9   | %49.8     | %39.7   |
| 1h        | 90495 | YETERLI | %74.5      | %69.5     | %58.6   | %48.1     | %38.6   |
| 2h        | 62958 | YETERLI | %74.9      | %69.4     | %58.2   | %47.6     | %37.9   |
| 4h        | 69590 | YETERLI | %75.5      | %70.1     | %59.3   | %48.5     | %39.0   |

## Soru 4 — Yüksek zone ayırt edici mi, tepki anlık mı kalıcı mı?
| timeframe | family | yukseklik_kovasi | n     | guven   | ort_pay_5 | ort_pay_3 | ort_h12_decay | ort_tepe_h12 | ort_uzun_tepe_h40 | uzun/ana_tepe_orani | tepki_CALISTI |
|-----------|--------|------------------|-------|---------|-----------|-----------|---------------|--------------|-------------------|---------------------|---------------|
| 1d        | FVG    | 0-0.5            | 3239  | YETERLI | 0.615     | 0.479     | 2.459         | 1.914        | 3.850             | 3.207               | %64.0         |
| 1d        | FVG    | 0.5-1            | 2023  | YETERLI | 0.616     | 0.436     | 1.833         | 1.977        | 4.060             | 3.317               | %64.4         |
| 1d        | FVG    | 1-2              | 878   | YETERLI | 0.659     | 0.461     | 1.708         | 1.986        | 3.876             | 2.347               | %67.7         |
| 1d        | FVG    | >=2              | 159   | YETERLI | 0.395     | 0.171     | 1.239         | 2.320        | 4.144             | 1.715               | %70.4         |
| 1d        | OB     | 0-0.5            | 1517  | YETERLI | 0.550     | 0.397     | 1.958         | 1.963        | 3.988             | 3.566               | %61.8         |
| 1d        | OB     | 0.5-1            | 9137  | YETERLI | 0.571     | 0.398     | 2.102         | 2.002        | 3.827             | 3.037               | %65.0         |
| 1d        | OB     | 1-2              | 6503  | YETERLI | 0.293     | 0.101     | 2.527         | 1.981        | 3.678             | 2.848               | %65.7         |
| 1d        | OB     | >=2              | 866   | YETERLI | 0.607     | 0.438     | 1.551         | 1.844        | 3.548             | 2.375               | %68.9         |
| 1d        | OB     | BILINMEYEN       | 541   | YETERLI | 0.438     | 0.291     | 1.233         | 1.759        | 3.116             | 2.319               | %52.5         |
| 1h        | OB     | 0-0.5            | 9731  | YETERLI | 0.655     | 0.520     | 2.124         | 2.037        | 3.950             | 2.821               | %65.9         |
| 1h        | OB     | 0.5-1            | 43456 | YETERLI | 0.620     | 0.476     | 1.860         | 2.015        | 3.872             | 2.836               | %65.8         |
| 1h        | OB     | 1-2              | 31473 | YETERLI | 0.589     | 0.425     | 1.552         | 1.984        | 3.776             | 2.580               | %66.3         |
| 1h        | OB     | >=2              | 5508  | YETERLI | 0.586     | 0.388     | 1.225         | 1.910        | 3.683             | 2.346               | %67.9         |
| 1h        | OB     | BILINMEYEN       | 327   | YETERLI | 0.649     | 0.523     | 1.953         | 2.091        | 3.343             | 1.830               | %54.7         |
| 2h        | FVG    | 0-0.5            | 8679  | YETERLI | 0.668     | 0.518     | 1.963         | 2.008        | 3.877             | 2.939               | %65.3         |
| 2h        | FVG    | 0.5-1            | 5325  | YETERLI | 0.662     | 0.516     | 1.766         | 2.084        | 3.989             | 2.791               | %66.6         |
| 2h        | FVG    | 1-2              | 2546  | YETERLI | 0.639     | 0.493     | 1.513         | 2.078        | 4.137             | 2.570               | %65.3         |
| 2h        | FVG    | >=2              | 748   | YETERLI | 0.610     | 0.477     | 1.112         | 2.998        | 5.534             | 1.968               | %68.6         |
| 2h        | OB     | 0-0.5            | 4263  | YETERLI | 0.658     | 0.482     | 2.203         | 2.001        | 3.836             | 3.003               | %64.7         |
| 2h        | OB     | 0.5-1            | 22791 | YETERLI | 0.640     | 0.427     | 2.322         | 1.977        | 3.822             | 2.724               | %65.0         |
| 2h        | OB     | 1-2              | 15697 | YETERLI | 0.593     | 0.375     | 1.563         | 1.904        | 3.690             | 2.587               | %65.5         |
| 2h        | OB     | >=2              | 2482  | YETERLI | 0.557     | 0.299     | 1.262         | 1.870        | 3.606             | 2.518               | %68.5         |
| 2h        | OB     | BILINMEYEN       | 427   | YETERLI | 0.420     | 0.246     | 2.260         | 2.152        | 3.895             | 3.110               | %50.1         |
| 4h        | FVG    | 0-0.5            | 9248  | YETERLI | 0.648     | 0.513     | 2.076         | 1.986        | 3.832             | 2.990               | %65.6         |
| 4h        | FVG    | 0.5-1            | 6437  | YETERLI | 0.620     | 0.477     | 1.955         | 2.035        | 3.947             | 2.722               | %65.6         |
| 4h        | FVG    | 1-2              | 3356  | YETERLI | 0.636     | 0.486     | 1.652         | 2.152        | 4.030             | 2.430               | %68.0         |
| 4h        | FVG    | >=2              | 978   | YETERLI | 0.641     | 0.500     | 1.036         | 3.082        | 5.633             | 2.217               | %73.7         |
| 4h        | OB     | 0-0.5            | 6427  | YETERLI | 0.636     | 0.499     | 10.335        | 2.055        | 3.994             | 21.271              | %64.3         |
| 4h        | OB     | 0.5-1            | 20913 | YETERLI | 0.599     | 0.454     | 2.181         | 1.959        | 3.917             | 3.056               | %64.8         |
| 4h        | OB     | 1-2              | 18486 | YETERLI | 0.553     | 0.388     | 1.672         | 1.937        | 3.810             | 2.882               | %65.2         |
| 4h        | OB     | >=2              | 3229  | YETERLI | 0.453     | 0.226     | 1.244         | 1.963        | 3.855             | 2.635               | %66.9         |
| 4h        | OB     | BILINMEYEN       | 516   | YETERLI | 0.305     | -0.032    | 1.435         | 2.072        | 3.872             | 2.966               | %47.3         |

_Okuma: `ort_pay_5` yüksek + `uzun/ana_tepe_orani` ~1 -> **anlık**; `ort_pay_5` düşük + oran >>1 -> **yavaş ama kalıcı**._

_`ort_h12_decay` 1'den büyükse pencere, tepenin altına kapanmıştır (kapanış referansın ters tarafında); bu "tepki verdi sonra tamamen geri verdi" demektir, ölçüm hatası değildir._

## Soru 5 — MS BOS/CHOCH: yön ile tepki uyuşuyor mu?
### Scope x event tipi

| timeframe | scope    | event_type            | n     | guven   | uyumlu | CALISTI | AZ_DEVAM | DEVAM_YOK | TERS | sansur | ort_devam_h12 | ort_ters_h12 |
|-----------|----------|-----------------------|-------|---------|--------|---------|----------|-----------|------|--------|---------------|--------------|
| 1d        | EXTERNAL | EVENT_BOS             | 1796  | YETERLI | %97.4  | %69.5   | %21.5    | %6.9      | %2.0 | %0.4   | 2.280         | 2.110        |
| 1d        | EXTERNAL | EVENT_CHOCH           | 700   | YETERLI | %95.4  | %65.7   | %22.6    | %8.4      | %3.1 | %1.1   | 2.156         | 2.128        |
| 1d        | EXTERNAL | EVENT_FALSE_BREAK     | 152   | YETERLI | %97.4  | %72.4   | %19.7    | %5.9      | %2.0 | %0.7   | 2.185         | 1.953        |
| 1d        | EXTERNAL | EVENT_SWEEP           | 3527  | YETERLI | %96.0  | %66.8   | %22.7    | %7.3      | %3.1 | %1.2   | 2.019         | 2.097        |
| 1d        | EXTERNAL | EVENT_TRANSITION_FAIL | 219   | YETERLI | %99.5  | %69.4   | %25.1    | %5.0      | %0.5 | %2.3   | 2.096         | 2.052        |
| 1d        | INTERNAL | EVENT_BOS             | 3265  | YETERLI | %95.3  | %68.4   | %21.7    | %5.8      | %2.3 | %1.1   | 2.306         | 1.965        |
| 1d        | INTERNAL | EVENT_CHOCH           | 1285  | YETERLI | %95.6  | %64.4   | %24.0    | %8.8      | %2.8 | %2.3   | 2.004         | 2.163        |
| 1d        | INTERNAL | EVENT_FALSE_BREAK     | 237   | YETERLI | %95.8  | %65.0   | %25.3    | %6.8      | %1.7 | %2.5   | 1.967         | 2.114        |
| 1d        | INTERNAL | EVENT_SWEEP           | 5829  | YETERLI | %95.8  | %65.5   | %24.2    | %6.9      | %2.6 | %1.8   | 2.033         | 2.045        |
| 1d        | INTERNAL | EVENT_TRANSITION_FAIL | 399   | YETERLI | %97.7  | %66.2   | %25.8    | %6.0      | %2.0 | %0.3   | 2.144         | 2.211        |
| 1h        | EXTERNAL | EVENT_BOS             | 9503  | YETERLI | %97.0  | %67.4   | %22.7    | %8.9      | %0.9 | %0.3   | 2.282         | 1.977        |
| 1h        | EXTERNAL | EVENT_CHOCH           | 3603  | YETERLI | %97.1  | %68.6   | %22.0    | %8.3      | %1.1 | %0.6   | 2.283         | 1.842        |
| 1h        | EXTERNAL | EVENT_FALSE_BREAK     | 720   | YETERLI | %96.1  | %61.4   | %26.1    | %10.0     | %2.5 | %0.3   | 1.876         | 2.173        |
| 1h        | EXTERNAL | EVENT_SWEEP           | 19661 | YETERLI | %96.8  | %62.6   | %26.2    | %10.0     | %1.2 | %0.2   | 1.880         | 2.137        |
| 1h        | EXTERNAL | EVENT_TRANSITION_FAIL | 920   | YETERLI | %97.2  | %68.8   | %21.7    | %8.3      | %1.2 | %0.7   | 2.424         | 1.927        |
| 1h        | INTERNAL | EVENT_BOS             | 18171 | YETERLI | %96.8  | %67.4   | %22.2    | %8.9      | %1.1 | %0.4   | 2.268         | 1.949        |
| 1h        | INTERNAL | EVENT_CHOCH           | 6627  | YETERLI | %97.2  | %66.2   | %23.6    | %9.1      | %1.1 | %0.5   | 2.150         | 1.949        |
| 1h        | INTERNAL | EVENT_FALSE_BREAK     | 1252  | YETERLI | %96.5  | %63.0   | %25.2    | %10.4     | %1.3 | %0.2   | 1.968         | 2.046        |
| 1h        | INTERNAL | EVENT_SWEEP           | 31804 | YETERLI | %96.8  | %62.6   | %26.4    | %9.7      | %1.2 | %0.2   | 1.908         | 2.126        |
| 1h        | INTERNAL | EVENT_TRANSITION_FAIL | 1858  | YETERLI | %97.1  | %68.9   | %21.5    | %8.2      | %1.3 | %0.2   | 2.295         | 1.929        |
| 2h        | EXTERNAL | EVENT_BOS             | 4648  | YETERLI | %97.2  | %67.5   | %23.0    | %8.1      | %1.4 | %0.9   | 2.296         | 2.035        |
| 2h        | EXTERNAL | EVENT_CHOCH           | 1909  | YETERLI | %97.0  | %68.0   | %22.3    | %8.3      | %1.4 | %0.5   | 2.307         | 1.842        |
| 2h        | EXTERNAL | EVENT_FALSE_BREAK     | 353   | YETERLI | %92.9  | %64.6   | %21.0    | %10.2     | %4.2 | %1.1   | 1.920         | 2.150        |
| 2h        | EXTERNAL | EVENT_SWEEP           | 9753  | YETERLI | %96.7  | %63.1   | %25.4    | %9.9      | %1.5 | %0.7   | 1.927         | 2.072        |
| 2h        | EXTERNAL | EVENT_TRANSITION_FAIL | 536   | YETERLI | %96.6  | %67.0   | %24.3    | %7.8      | %0.9 | %1.3   | 2.279         | 1.936        |
| 2h        | INTERNAL | EVENT_BOS             | 8711  | YETERLI | %96.8  | %67.2   | %22.4    | %8.6      | %1.3 | %0.6   | 2.226         | 2.017        |
| 2h        | INTERNAL | EVENT_CHOCH           | 3371  | YETERLI | %96.9  | %68.3   | %22.0    | %8.1      | %1.6 | %1.2   | 2.231         | 1.866        |
| 2h        | INTERNAL | EVENT_FALSE_BREAK     | 701   | YETERLI | %95.1  | %66.2   | %20.8    | %10.1     | %2.6 | %0.4   | 2.047         | 1.972        |
| 2h        | INTERNAL | EVENT_SWEEP           | 14805 | YETERLI | %97.0  | %63.2   | %26.1    | %9.3      | %1.3 | %0.6   | 1.902         | 2.055        |
| 2h        | INTERNAL | EVENT_TRANSITION_FAIL | 941   | YETERLI | %97.6  | %69.5   | %23.3    | %6.4      | %0.9 | %1.5   | 2.302         | 1.920        |
| 4h        | EXTERNAL | EVENT_BOS             | 4790  | YETERLI | %97.8  | %71.8   | %19.9    | %7.3      | %1.0 | %0.8   | 2.419         | 1.959        |
| 4h        | EXTERNAL | EVENT_CHOCH           | 1893  | YETERLI | %98.0  | %71.0   | %19.9    | %8.0      | %1.1 | %0.2   | 2.393         | 1.982        |
| 4h        | EXTERNAL | EVENT_FALSE_BREAK     | 397   | YETERLI | %95.0  | %59.4   | %26.4    | %10.8     | %3.0 | %0.8   | 1.972         | 2.073        |
| 4h        | EXTERNAL | EVENT_SWEEP           | 10175 | YETERLI | %97.6  | %65.0   | %24.2    | %9.6      | %1.2 | %0.6   | 2.051         | 2.110        |
| 4h        | EXTERNAL | EVENT_TRANSITION_FAIL | 565   | YETERLI | %97.0  | %72.4   | %19.8    | %6.0      | %1.8 | %0.5   | 2.543         | 2.011        |
| 4h        | INTERNAL | EVENT_BOS             | 9316  | YETERLI | %96.6  | %67.0   | %22.0    | %8.7      | %1.4 | %0.6   | 2.308         | 2.108        |
| 4h        | INTERNAL | EVENT_CHOCH           | 3641  | YETERLI | %97.3  | %71.0   | %20.4    | %7.0      | %1.3 | %0.5   | 2.417         | 1.874        |
| 4h        | INTERNAL | EVENT_FALSE_BREAK     | 692   | YETERLI | %94.4  | %64.7   | %22.5    | %8.7      | %3.6 | %1.2   | 2.004         | 2.257        |
| 4h        | INTERNAL | EVENT_SWEEP           | 15392 | YETERLI | %97.1  | %64.2   | %24.6    | %9.4      | %1.3 | %0.7   | 1.978         | 2.142        |
| 4h        | INTERNAL | EVENT_TRANSITION_FAIL | 1044  | YETERLI | %97.4  | %70.3   | %22.0    | %6.2      | %1.4 | %0.9   | 2.423         | 1.941        |

### Scope x yön (BOS/CHOCH ayrımıyla)

| timeframe | scope    | event_type  | direction | n    | guven   | uyumlu | CALISTI | AZ_DEVAM | DEVAM_YOK | TERS | sansur | ort_devam_h12 | ort_ters_h12 |
|-----------|----------|-------------|-----------|------|---------|--------|---------|----------|-----------|------|--------|---------------|--------------|
| 1d        | EXTERNAL | EVENT_BOS   | DOWN      | 1015 | YETERLI | %97.1  | %63.9   | %26.1    | %7.6      | %2.4 | %0.5   | 1.874         | 2.097        |
| 1d        | EXTERNAL | EVENT_BOS   | UP        | 781  | YETERLI | %97.8  | %76.8   | %15.6    | %6.0      | %1.5 | %0.3   | 2.808         | 2.128        |
| 1d        | EXTERNAL | EVENT_CHOCH | DOWN      | 358  | YETERLI | %93.6  | %59.5   | %24.9    | %11.2     | %4.2 | %0.6   | 1.570         | 1.926        |
| 1d        | EXTERNAL | EVENT_CHOCH | UP        | 342  | YETERLI | %97.4  | %72.2   | %20.2    | %5.6      | %2.0 | %1.8   | 2.767         | 2.340        |
| 1d        | INTERNAL | EVENT_BOS   | DOWN      | 1780 | YETERLI | %95.8  | %64.2   | %25.7    | %6.8      | %2.8 | %1.7   | 1.914         | 1.956        |
| 1d        | INTERNAL | EVENT_BOS   | UP        | 1485 | YETERLI | %94.7  | %73.5   | %17.0    | %4.7      | %1.8 | %0.5   | 2.787         | 1.976        |
| 1d        | INTERNAL | EVENT_CHOCH | DOWN      | 643  | YETERLI | %94.2  | %58.6   | %26.1    | %12.1     | %3.1 | %0.2   | 1.541         | 2.026        |
| 1d        | INTERNAL | EVENT_CHOCH | UP        | 642  | YETERLI | %97.0  | %70.2   | %21.8    | %5.5      | %2.5 | %4.5   | 2.467         | 2.300        |
| 1h        | EXTERNAL | EVENT_BOS   | DOWN      | 4704 | YETERLI | %97.2  | %67.6   | %23.0    | %8.3      | %1.1 | %0.5   | 2.162         | 2.092        |
| 1h        | EXTERNAL | EVENT_BOS   | UP        | 4799 | YETERLI | %96.8  | %67.2   | %22.5    | %9.5      | %0.8 | %0.2   | 2.401         | 1.864        |
| 1h        | EXTERNAL | EVENT_CHOCH | DOWN      | 1818 | YETERLI | %97.4  | %67.4   | %23.5    | %7.8      | %1.2 | %1.3   | 2.096         | 1.858        |
| 1h        | EXTERNAL | EVENT_CHOCH | UP        | 1785 | YETERLI | %96.7  | %69.7   | %20.3    | %8.9      | %1.1 | %0.0   | 2.473         | 1.826        |
| 1h        | INTERNAL | EVENT_BOS   | DOWN      | 9379 | YETERLI | %96.8  | %67.6   | %22.8    | %7.8      | %1.2 | %0.6   | 2.166         | 2.010        |
| 1h        | INTERNAL | EVENT_BOS   | UP        | 8792 | YETERLI | %96.7  | %67.2   | %21.6    | %10.1     | %0.9 | %0.1   | 2.377         | 1.885        |
| 1h        | INTERNAL | EVENT_CHOCH | DOWN      | 3288 | YETERLI | %97.6  | %64.5   | %25.7    | %8.5      | %1.2 | %1.0   | 1.900         | 2.059        |
| 1h        | INTERNAL | EVENT_CHOCH | UP        | 3339 | YETERLI | %96.9  | %67.9   | %21.5    | %9.6      | %0.9 | %0.0   | 2.397         | 1.842        |
| 2h        | EXTERNAL | EVENT_BOS   | DOWN      | 2531 | YETERLI | %97.4  | %65.7   | %24.5    | %8.5      | %1.3 | %1.5   | 2.148         | 2.133        |
| 2h        | EXTERNAL | EVENT_BOS   | UP        | 2117 | YETERLI | %96.9  | %69.7   | %21.2    | %7.6      | %1.5 | %0.3   | 2.473         | 1.917        |
| 2h        | EXTERNAL | EVENT_CHOCH | DOWN      | 942  | YETERLI | %97.7  | %65.1   | %24.7    | %9.2      | %1.0 | %0.8   | 2.025         | 1.852        |
| 2h        | EXTERNAL | EVENT_CHOCH | UP        | 967  | YETERLI | %96.3  | %70.9   | %20.0    | %7.3      | %1.8 | %0.1   | 2.582         | 1.832        |
| 2h        | INTERNAL | EVENT_BOS   | DOWN      | 4766 | YETERLI | %96.7  | %66.6   | %23.3    | %8.4      | %1.3 | %0.8   | 2.121         | 2.088        |
| 2h        | INTERNAL | EVENT_BOS   | UP        | 3945 | YETERLI | %96.8  | %67.9   | %21.4    | %9.0      | %1.4 | %0.3   | 2.351         | 1.930        |
| 2h        | INTERNAL | EVENT_CHOCH | DOWN      | 1634 | YETERLI | %97.4  | %66.0   | %24.1    | %8.4      | %1.5 | %2.4   | 1.940         | 1.894        |
| 2h        | INTERNAL | EVENT_CHOCH | UP        | 1737 | YETERLI | %96.4  | %70.5   | %20.0    | %7.7      | %1.8 | %0.2   | 2.504         | 1.840        |
| 4h        | EXTERNAL | EVENT_BOS   | DOWN      | 2470 | YETERLI | %97.4  | %68.9   | %22.2    | %7.7      | %1.2 | %1.5   | 2.147         | 2.037        |
| 4h        | EXTERNAL | EVENT_BOS   | UP        | 2320 | YETERLI | %98.2  | %74.8   | %17.4    | %6.9      | %0.9 | %0.1   | 2.709         | 1.877        |
| 4h        | EXTERNAL | EVENT_CHOCH | DOWN      | 953  | YETERLI | %98.2  | %68.3   | %21.6    | %9.0      | %1.0 | %0.1   | 2.081         | 1.937        |
| 4h        | EXTERNAL | EVENT_CHOCH | UP        | 940  | YETERLI | %97.8  | %73.7   | %18.1    | %7.0      | %1.2 | %0.2   | 2.710         | 2.028        |
| 4h        | INTERNAL | EVENT_BOS   | DOWN      | 4845 | YETERLI | %96.1  | %63.6   | %24.2    | %9.7      | %1.7 | %0.7   | 2.015         | 2.193        |
| 4h        | INTERNAL | EVENT_BOS   | UP        | 4471 | YETERLI | %97.0  | %70.8   | %19.7    | %7.6      | %1.1 | %0.4   | 2.625         | 2.016        |
| 4h        | INTERNAL | EVENT_CHOCH | DOWN      | 1771 | YETERLI | %97.8  | %69.7   | %22.4    | %6.7      | %1.2 | %0.7   | 2.150         | 1.880        |
| 4h        | INTERNAL | EVENT_CHOCH | UP        | 1870 | YETERLI | %96.8  | %72.3   | %18.5    | %7.3      | %1.3 | %0.4   | 2.671         | 1.869        |

### Motorun kendi outcome kararı (çapraz kontrol)

| timeframe | scope    | outcome                  | n     | guven   | adet   |
|-----------|----------|--------------------------|-------|---------|--------|
| 1d        | EXTERNAL | FAILED                   | 371   | YETERLI | %100.0 |
| 1d        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 454   | YETERLI | %100.0 |
| 1d        | EXTERNAL | OBSERVED                 | 5542  | YETERLI | %100.0 |
| 1d        | EXTERNAL | PENDING                  | 27    | KISMI   | %100.0 |
| 1d        | INTERNAL | FAILED                   | 636   | YETERLI | %100.0 |
| 1d        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 851   | YETERLI | %100.0 |
| 1d        | INTERNAL | OBSERVED                 | 9493  | YETERLI | %100.0 |
| 1d        | INTERNAL | PENDING                  | 35    | YETERLI | %100.0 |
| 1h        | EXTERNAL | FAILED                   | 1640  | YETERLI | %100.0 |
| 1h        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 2611  | YETERLI | %100.0 |
| 1h        | EXTERNAL | OBSERVED                 | 30084 | YETERLI | %100.0 |
| 1h        | EXTERNAL | PENDING                  | 72    | YETERLI | %100.0 |
| 1h        | INTERNAL | FAILED                   | 3110  | YETERLI | %100.0 |
| 1h        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 4710  | YETERLI | %100.0 |
| 1h        | INTERNAL | OBSERVED                 | 51833 | YETERLI | %100.0 |
| 1h        | INTERNAL | PENDING                  | 59    | YETERLI | %100.0 |
| 2h        | EXTERNAL | FAILED                   | 889   | YETERLI | %100.0 |
| 2h        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 1314  | YETERLI | %100.0 |
| 2h        | EXTERNAL | OBSERVED                 | 14937 | YETERLI | %100.0 |
| 2h        | EXTERNAL | PENDING                  | 59    | YETERLI | %100.0 |
| 2h        | INTERNAL | FAILED                   | 1642  | YETERLI | %100.0 |
| 2h        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 2369  | YETERLI | %100.0 |
| 2h        | INTERNAL | OBSERVED                 | 24457 | YETERLI | %100.0 |
| 2h        | INTERNAL | PENDING                  | 61    | YETERLI | %100.0 |
| 4h        | EXTERNAL | FAILED                   | 962   | YETERLI | %100.0 |
| 4h        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 1277  | YETERLI | %100.0 |
| 4h        | EXTERNAL | OBSERVED                 | 15530 | YETERLI | %100.0 |
| 4h        | EXTERNAL | PENDING                  | 51    | YETERLI | %100.0 |
| 4h        | INTERNAL | FAILED                   | 1736  | YETERLI | %100.0 |
| 4h        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 2531  | YETERLI | %100.0 |
| 4h        | INTERNAL | OBSERVED                 | 25752 | YETERLI | %100.0 |
| 4h        | INTERNAL | PENDING                  | 66    | YETERLI | %100.0 |

## Soru 6 — PH/PL direnç/destek mi, çok denenen mi az denenen mi?
### Kararı verilebilir satırlar (sansürsüz)

| timeframe | scope    | rol | deneme_kovasi | n    | guven   | engelledi | engellemedi | ort_deneme_epizot | ort_deneme_bar | ort_rol_sure_bar | ort_bars_to_break |
|-----------|----------|-----|---------------|------|---------|-----------|-------------|-------------------|----------------|------------------|-------------------|
| 1d        | EXTERNAL | PH  | 0_deneme      | 813  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 34.692           | 67.559            |
| 1d        | EXTERNAL | PH  | 1_deneme      | 319  | YETERLI | %36.1     | %63.9       | 1.000             | 11.674         | 24.219           | 22.094            |
| 1d        | EXTERNAL | PH  | 2-3_deneme    | 213  | YETERLI | %22.1     | %77.9       | 2.333             | 15.582         | 19.554           | 18.847            |
| 1d        | EXTERNAL | PH  | 4plus_deneme  | 26   | KISMI   | %15.4     | %84.6       | 4.269             | 16.308         | 21.885           | 22.217            |
| 1d        | EXTERNAL | PL  | 0_deneme      | 649  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 40.018           | 71.759            |
| 1d        | EXTERNAL | PL  | 1_deneme      | 303  | YETERLI | %38.0     | %62.0       | 1.000             | 15.172         | 22.683           | 21.137            |
| 1d        | EXTERNAL | PL  | 2-3_deneme    | 221  | YETERLI | %29.0     | %71.0       | 2.326             | 15.783         | 22.009           | 21.756            |
| 1d        | EXTERNAL | PL  | 4plus_deneme  | 29   | KISMI   | %31.0     | %69.0       | 4.241             | 16.207         | 19.966           | 20.708            |
| 1d        | INTERNAL | PH  | 0_deneme      | 1078 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 19.522           | 58.679            |
| 1d        | INTERNAL | PH  | 1_deneme      | 689  | YETERLI | %34.1     | %65.9       | 1.000             | 13.071         | 14.810           | 13.331            |
| 1d        | INTERNAL | PH  | 2-3_deneme    | 562  | YETERLI | %20.6     | %79.4       | 2.302             | 16.692         | 14.560           | 14.461            |
| 1d        | INTERNAL | PH  | 4plus_deneme  | 97   | YETERLI | %19.6     | %80.4       | 4.289             | 18.402         | 14.340           | 14.043            |
| 1d        | INTERNAL | PL  | 0_deneme      | 915  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 20.828           | 66.714            |
| 1d        | INTERNAL | PL  | 1_deneme      | 637  | YETERLI | %37.4     | %62.6       | 1.000             | 16.339         | 15.951           | 14.497            |
| 1d        | INTERNAL | PL  | 2-3_deneme    | 581  | YETERLI | %29.8     | %70.2       | 2.344             | 16.592         | 15.861           | 16.322            |
| 1d        | INTERNAL | PL  | 4plus_deneme  | 97   | YETERLI | %28.9     | %71.1       | 4.351             | 16.639         | 16.124           | 16.761            |
| 1h        | EXTERNAL | PH  | 0_deneme      | 4163 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 46.173           | 75.746            |
| 1h        | EXTERNAL | PH  | 1_deneme      | 1472 | YETERLI | %34.1     | %65.9       | 1.000             | 13.410         | 30.809           | 25.933            |
| 1h        | EXTERNAL | PH  | 2-3_deneme    | 1030 | YETERLI | %21.8     | %78.2       | 2.336             | 15.004         | 24.837           | 23.523            |
| 1h        | EXTERNAL | PH  | 4plus_deneme  | 203  | YETERLI | %19.2     | %80.8       | 4.443             | 16.365         | 25.286           | 24.425            |
| 1h        | EXTERNAL | PL  | 0_deneme      | 4519 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 46.186           | 88.524            |
| 1h        | EXTERNAL | PL  | 1_deneme      | 1501 | YETERLI | %36.1     | %63.9       | 1.000             | 13.536         | 32.731           | 24.195            |
| 1h        | EXTERNAL | PL  | 2-3_deneme    | 893  | YETERLI | %30.2     | %69.8       | 2.283             | 14.326         | 25.368           | 25.255            |
| 1h        | EXTERNAL | PL  | 4plus_deneme  | 130  | YETERLI | %29.2     | %70.8       | 4.454             | 16.623         | 25.008           | 24.208            |
| 1h        | INTERNAL | PH  | 0_deneme      | 6180 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 24.304           | 72.755            |
| 1h        | INTERNAL | PH  | 1_deneme      | 3510 | YETERLI | %35.1     | %64.9       | 1.000             | 15.192         | 17.294           | 16.050            |
| 1h        | INTERNAL | PH  | 2-3_deneme    | 3057 | YETERLI | %23.5     | %76.5       | 2.342             | 16.298         | 16.966           | 16.649            |
| 1h        | INTERNAL | PH  | 4plus_deneme  | 676  | YETERLI | %16.0     | %84.0       | 4.444             | 17.454         | 17.083           | 16.921            |
| 1h        | INTERNAL | PL  | 0_deneme      | 6449 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 23.280           | 76.662            |
| 1h        | INTERNAL | PL  | 1_deneme      | 3451 | YETERLI | %34.8     | %65.2       | 1.000             | 15.080         | 21.881           | 18.957            |
| 1h        | INTERNAL | PL  | 2-3_deneme    | 2639 | YETERLI | %27.8     | %72.2       | 2.312             | 16.735         | 18.341           | 17.992            |
| 1h        | INTERNAL | PL  | 4plus_deneme  | 454  | YETERLI | %28.2     | %71.8       | 4.403             | 17.608         | 17.672           | 17.292            |
| 2h        | EXTERNAL | PH  | 0_deneme      | 2239 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 42.978           | 73.917            |
| 2h        | EXTERNAL | PH  | 1_deneme      | 744  | YETERLI | %31.6     | %68.4       | 1.000             | 14.481         | 25.750           | 22.486            |
| 2h        | EXTERNAL | PH  | 2-3_deneme    | 597  | YETERLI | %23.5     | %76.5       | 2.343             | 14.966         | 24.831           | 22.900            |
| 2h        | EXTERNAL | PH  | 4plus_deneme  | 104  | YETERLI | %15.4     | %84.6       | 4.442             | 16.721         | 25.192           | 22.341            |
| 2h        | EXTERNAL | PL  | 0_deneme      | 2044 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 43.041           | 76.027            |
| 2h        | EXTERNAL | PL  | 1_deneme      | 733  | YETERLI | %33.0     | %67.0       | 1.000             | 14.086         | 28.285           | 24.482            |
| 2h        | EXTERNAL | PL  | 2-3_deneme    | 464  | YETERLI | %34.1     | %65.9       | 2.287             | 15.144         | 25.067           | 24.813            |
| 2h        | EXTERNAL | PL  | 4plus_deneme  | 58   | YETERLI | %22.4     | %77.6       | 4.310             | 16.672         | 22.966           | 21.960            |
| 2h        | INTERNAL | PH  | 0_deneme      | 3118 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 22.801           | 74.392            |
| 2h        | INTERNAL | PH  | 1_deneme      | 1757 | YETERLI | %33.9     | %66.1       | 1.000             | 15.407         | 17.203           | 15.798            |
| 2h        | INTERNAL | PH  | 2-3_deneme    | 1569 | YETERLI | %22.4     | %77.6       | 2.344             | 16.604         | 17.058           | 17.371            |
| 2h        | INTERNAL | PH  | 4plus_deneme  | 329  | YETERLI | %21.3     | %78.7       | 4.550             | 16.620         | 18.271           | 17.643            |
| 2h        | INTERNAL | PL  | 0_deneme      | 2807 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 23.274           | 90.331            |
| 2h        | INTERNAL | PL  | 1_deneme      | 1763 | YETERLI | %34.4     | %65.6       | 1.000             | 16.115         | 18.711           | 16.794            |
| 2h        | INTERNAL | PL  | 2-3_deneme    | 1283 | YETERLI | %28.8     | %71.2       | 2.297             | 17.182         | 16.867           | 17.626            |
| 2h        | INTERNAL | PL  | 4plus_deneme  | 198  | YETERLI | %24.7     | %75.3       | 4.338             | 18.808         | 17.429           | 18.674            |
| 4h        | EXTERNAL | PH  | 0_deneme      | 2248 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 42.657           | 72.550            |
| 4h        | EXTERNAL | PH  | 1_deneme      | 760  | YETERLI | %30.5     | %69.5       | 1.000             | 12.539         | 27.141           | 24.364            |
| 4h        | EXTERNAL | PH  | 2-3_deneme    | 559  | YETERLI | %23.1     | %76.9       | 2.288             | 14.626         | 23.349           | 22.505            |
| 4h        | EXTERNAL | PH  | 4plus_deneme  | 120  | YETERLI | %15.0     | %85.0       | 4.458             | 16.708         | 20.725           | 20.149            |
| 4h        | EXTERNAL | PL  | 0_deneme      | 2082 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 41.429           | 71.969            |
| 4h        | EXTERNAL | PL  | 1_deneme      | 813  | YETERLI | %34.8     | %65.2       | 1.000             | 13.524         | 28.038           | 24.761            |
| 4h        | EXTERNAL | PL  | 2-3_deneme    | 484  | YETERLI | %27.3     | %72.7       | 2.300             | 15.320         | 24.636           | 22.650            |
| 4h        | EXTERNAL | PL  | 4plus_deneme  | 68   | YETERLI | %26.5     | %73.5       | 4.265             | 17.265         | 22.603           | 22.404            |
| 4h        | INTERNAL | PH  | 0_deneme      | 3063 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 20.950           | 65.819            |
| 4h        | INTERNAL | PH  | 1_deneme      | 1868 | YETERLI | %29.1     | %70.9       | 1.000             | 15.568         | 15.711           | 14.333            |
| 4h        | INTERNAL | PH  | 2-3_deneme    | 1733 | YETERLI | %22.2     | %77.8       | 2.319             | 16.699         | 15.565           | 15.910            |
| 4h        | INTERNAL | PH  | 4plus_deneme  | 417  | YETERLI | %18.0     | %82.0       | 4.568             | 17.971         | 15.175           | 14.829            |
| 4h        | INTERNAL | PL  | 0_deneme      | 3065 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 22.520           | 68.394            |
| 4h        | INTERNAL | PL  | 1_deneme      | 1953 | YETERLI | %34.7     | %65.3       | 1.000             | 15.661         | 16.788           | 16.421            |
| 4h        | INTERNAL | PL  | 2-3_deneme    | 1443 | YETERLI | %29.2     | %70.8       | 2.314             | 17.480         | 17.154           | 17.572            |
| 4h        | INTERNAL | PL  | 4plus_deneme  | 201  | YETERLI | %23.9     | %76.1       | 4.348             | 18.378         | 16.284           | 17.153            |

### Karar verilemeyen satırlar (sağdan sansürlü — payda dışı)

| timeframe | scope    | rol | deneme_kovasi | n   | guven   | ort_deneme_epizot | ort_rol_sure_bar |
|-----------|----------|-----|---------------|-----|---------|-------------------|------------------|
| 1d        | EXTERNAL | PH  | 0_deneme      | 115 | YETERLI | 0.000             | 21.600           |
| 1d        | EXTERNAL | PH  | 1_deneme      | 3   | ZAYIF   | 1.000             | 21.000           |
| 1d        | EXTERNAL | PH  | 2-3_deneme    | 6   | ZAYIF   | 2.333             | 21.000           |
| 1d        | EXTERNAL | PL  | 0_deneme      | 18  | KISMI   | 0.000             | 12.333           |
| 1d        | INTERNAL | PH  | 0_deneme      | 202 | YETERLI | 0.000             | 15.609           |
| 1d        | INTERNAL | PH  | 1_deneme      | 19  | KISMI   | 1.000             | 14.895           |
| 1d        | INTERNAL | PH  | 2-3_deneme    | 10  | ZAYIF   | 2.200             | 18.600           |
| 1d        | INTERNAL | PL  | 0_deneme      | 43  | YETERLI | 0.000             | 10.163           |
| 1d        | INTERNAL | PL  | 1_deneme      | 4   | ZAYIF   | 1.000             | 17.250           |
| 1d        | INTERNAL | PL  | 2-3_deneme    | 11  | ZAYIF   | 2.364             | 13.182           |
| 1d        | INTERNAL | PL  | 4plus_deneme  | 4   | ZAYIF   | 4.500             | 16.750           |
| 1h        | EXTERNAL | PH  | 0_deneme      | 86  | YETERLI | 0.000             | 11.907           |
| 1h        | EXTERNAL | PH  | 1_deneme      | 3   | ZAYIF   | 1.000             | 15.333           |
| 1h        | EXTERNAL | PL  | 0_deneme      | 18  | KISMI   | 0.000             | 15.000           |
| 1h        | EXTERNAL | PL  | 1_deneme      | 5   | ZAYIF   | 1.000             | 28.400           |
| 1h        | EXTERNAL | PL  | 2-3_deneme    | 3   | ZAYIF   | 2.000             | 13.667           |
| 1h        | INTERNAL | PH  | 0_deneme      | 171 | YETERLI | 0.000             | 10.222           |
| 1h        | INTERNAL | PH  | 1_deneme      | 11  | ZAYIF   | 1.000             | 9.455            |
| 1h        | INTERNAL | PH  | 2-3_deneme    | 9   | ZAYIF   | 2.444             | 10.667           |
| 1h        | INTERNAL | PH  | 4plus_deneme  | 1   | ZAYIF   | 4.000             | 6.000            |
| 1h        | INTERNAL | PL  | 0_deneme      | 31  | YETERLI | 0.000             | 11.935           |
| 1h        | INTERNAL | PL  | 1_deneme      | 10  | ZAYIF   | 1.000             | 9.100            |
| 1h        | INTERNAL | PL  | 2-3_deneme    | 7   | ZAYIF   | 2.571             | 12.143           |
| 2h        | EXTERNAL | PH  | 0_deneme      | 71  | YETERLI | 0.000             | 11.718           |
| 2h        | EXTERNAL | PH  | 1_deneme      | 1   | ZAYIF   | 1.000             | 7.000            |
| 2h        | EXTERNAL | PL  | 0_deneme      | 32  | YETERLI | 0.000             | 21.688           |
| 2h        | EXTERNAL | PL  | 1_deneme      | 5   | ZAYIF   | 1.000             | 19.000           |
| 2h        | EXTERNAL | PL  | 2-3_deneme    | 1   | ZAYIF   | 2.000             | 13.000           |
| 2h        | INTERNAL | PH  | 0_deneme      | 118 | YETERLI | 0.000             | 9.263            |
| 2h        | INTERNAL | PH  | 1_deneme      | 15  | KISMI   | 1.000             | 9.067            |
| 2h        | INTERNAL | PH  | 2-3_deneme    | 11  | ZAYIF   | 2.182             | 21.727           |
| 2h        | INTERNAL | PH  | 4plus_deneme  | 1   | ZAYIF   | 5.000             | 22.000           |
| 2h        | INTERNAL | PL  | 0_deneme      | 34  | YETERLI | 0.000             | 14.176           |
| 2h        | INTERNAL | PL  | 1_deneme      | 16  | KISMI   | 1.000             | 11.125           |
| 2h        | INTERNAL | PL  | 2-3_deneme    | 3   | ZAYIF   | 2.333             | 16.000           |
| 2h        | INTERNAL | PL  | 4plus_deneme  | 1   | ZAYIF   | 4.000             | 13.000           |
| 4h        | EXTERNAL | PH  | 0_deneme      | 44  | YETERLI | 0.000             | 5.750            |
| 4h        | EXTERNAL | PH  | 1_deneme      | 2   | ZAYIF   | 1.000             | 12.000           |
| 4h        | EXTERNAL | PL  | 0_deneme      | 66  | YETERLI | 0.000             | 22.061           |
| 4h        | EXTERNAL | PL  | 1_deneme      | 2   | ZAYIF   | 1.000             | 13.000           |
| 4h        | INTERNAL | PH  | 0_deneme      | 70  | YETERLI | 0.000             | 6.700            |
| 4h        | INTERNAL | PH  | 1_deneme      | 24  | KISMI   | 1.000             | 10.542           |
| 4h        | INTERNAL | PH  | 2-3_deneme    | 12  | ZAYIF   | 2.167             | 12.917           |
| 4h        | INTERNAL | PH  | 4plus_deneme  | 5   | ZAYIF   | 4.600             | 8.600            |
| 4h        | INTERNAL | PL  | 0_deneme      | 123 | YETERLI | 0.000             | 17.943           |
| 4h        | INTERNAL | PL  | 1_deneme      | 22  | KISMI   | 1.000             | 16.227           |
| 4h        | INTERNAL | PL  | 2-3_deneme    | 1   | ZAYIF   | 3.000             | 12.000           |
| 4h        | INTERNAL | PL  | 4plus_deneme  | 1   | ZAYIF   | 4.000             | 12.000           |

### Yaklaşma eşiği duyarlılığı (0.25 ana; 0.15 / 0.50 kontrol)

| esik     | timeframe | n_satir | guven   | engelledi_orani | kararsiz_adet |
|----------|-----------|---------|---------|-----------------|---------------|
| 0.25 ATR | 1d        | 7664    | YETERLI | %63.9           | 435           |
| 0.25 ATR | 1h        | 40682   | YETERLI | %67.1           | 355           |
| 0.25 ATR | 2h        | 20116   | YETERLI | %65.9           | 309           |
| 0.25 ATR | 4h        | 21249   | YETERLI | %64.3           | 372           |
| 0.15 ATR | 1d        | 7664    | YETERLI | %60.4           | 435           |
| 0.15 ATR | 1h        | 40682   | YETERLI | %64.8           | 355           |
| 0.15 ATR | 2h        | 20116   | YETERLI | %63.1           | 309           |
| 0.15 ATR | 4h        | 21249   | YETERLI | %61.5           | 372           |
| 0.5 ATR  | 1d        | 7664    | YETERLI | %72.8           | 435           |
| 0.5 ATR  | 1h        | 40682   | YETERLI | %74.4           | 355           |
| 0.5 ATR  | 2h        | 20116   | YETERLI | %74.2           | 309           |
| 0.5 ATR  | 4h        | 21249   | YETERLI | %72.4           | 372           |

## Soru 7 — WH/WL %kaçı ziyaret/süpürüldü, ne kadar sürede?
| timeframe | scope    | rol | n     | guven   | ziyaret_epizot | supuruldu | hic_ulasilmadi | sansur | ort_deneme_epizot |
|-----------|----------|-----|-------|---------|----------------|-----------|----------------|--------|-------------------|
| 1d        | EXTERNAL | WH  | 1625  | YETERLI | %65.0          | %56.1     | %43.9          | %2.9   | 1.196             |
| 1d        | EXTERNAL | WL  | 1780  | YETERLI | %71.5          | %62.0     | %38.0          | %12.4  | 1.386             |
| 1d        | INTERNAL | WH  | 3624  | YETERLI | %77.3          | %66.3     | %33.7          | %2.3   | 1.512             |
| 1d        | INTERNAL | WL  | 4079  | YETERLI | %80.3          | %69.4     | %30.6          | %13.9  | 1.537             |
| 1h        | EXTERNAL | WH  | 12208 | YETERLI | %68.4          | %56.6     | %43.4          | %1.6   | 1.351             |
| 1h        | EXTERNAL | WL  | 11564 | YETERLI | %71.2          | %60.5     | %39.5          | %0.7   | 1.300             |
| 1h        | INTERNAL | WH  | 25997 | YETERLI | %77.0          | %63.5     | %36.5          | %1.3   | 1.565             |
| 1h        | INTERNAL | WL  | 25081 | YETERLI | %80.3          | %68.8     | %31.2          | %1.0   | 1.503             |
| 2h        | EXTERNAL | WH  | 5300  | YETERLI | %65.6          | %54.2     | %45.8          | %2.9   | 1.267             |
| 2h        | EXTERNAL | WL  | 5816  | YETERLI | %72.3          | %61.5     | %38.5          | %2.8   | 1.282             |
| 2h        | INTERNAL | WH  | 11016 | YETERLI | %74.1          | %61.2     | %38.8          | %3.9   | 1.517             |
| 2h        | INTERNAL | WL  | 12080 | YETERLI | %80.3          | %69.5     | %30.5          | %1.5   | 1.503             |
| 4h        | EXTERNAL | WH  | 5326  | YETERLI | %68.9          | %57.5     | %42.5          | %1.3   | 1.349             |
| 4h        | EXTERNAL | WL  | 5893  | YETERLI | %70.8          | %60.6     | %39.4          | %4.5   | 1.293             |
| 4h        | INTERNAL | WH  | 11863 | YETERLI | %76.6          | %64.5     | %35.5          | %2.3   | 1.593             |
| 4h        | INTERNAL | WL  | 11637 | YETERLI | %80.0          | %69.5     | %30.5          | %2.2   | 1.525             |

### Seviyeye ulaşma süresi (native bar; rol atamasından itibaren)

| timeframe | rol | n     | guven   | q25   | ortanca | q75   | ortalama |
|-----------|-----|-------|---------|-------|---------|-------|----------|
| 1d        | WH  | 1645  | YETERLI | 1.000 | 3.000   | 6.000 | 5.000    |
| 1d        | WL  | 1963  | YETERLI | 1.000 | 3.000   | 6.000 | 4.700    |
| 1h        | WH  | 10541 | YETERLI | 1.000 | 3.000   | 6.000 | 5.600    |
| 1h        | WL  | 11144 | YETERLI | 2.000 | 3.000   | 7.000 | 6.200    |
| 2h        | WH  | 4608  | YETERLI | 1.000 | 3.000   | 6.000 | 5.400    |
| 2h        | WL  | 5703  | YETERLI | 2.000 | 3.000   | 7.000 | 5.700    |
| 4h        | WH  | 5196  | YETERLI | 1.000 | 3.000   | 6.000 | 5.000    |
| 4h        | WL  | 5749  | YETERLI | 1.000 | 3.000   | 6.000 | 5.500    |

### EVENT_SWEEP çapraz kontrolü
| timeframe | scope    | direction | n     | guven   | uyumlu | CALISTI | ort_devam_h12 |
|-----------|----------|-----------|-------|---------|--------|---------|---------------|
| 1d        | EXTERNAL | DOWN      | 1988  | YETERLI | %96.0  | %65.6   | 1.963         |
| 1d        | EXTERNAL | UP        | 1539  | YETERLI | %95.9  | %68.4   | 2.093         |
| 1d        | INTERNAL | DOWN      | 3424  | YETERLI | %95.6  | %65.9   | 1.967         |
| 1d        | INTERNAL | UP        | 2405  | YETERLI | %96.0  | %65.0   | 2.126         |
| 1h        | EXTERNAL | DOWN      | 10965 | YETERLI | %97.5  | %63.2   | 1.751         |
| 1h        | EXTERNAL | UP        | 8696  | YETERLI | %96.0  | %61.7   | 2.042         |
| 1h        | INTERNAL | DOWN      | 17317 | YETERLI | %97.4  | %63.1   | 1.789         |
| 1h        | INTERNAL | UP        | 14487 | YETERLI | %96.1  | %62.2   | 2.049         |
| 2h        | EXTERNAL | DOWN      | 5586  | YETERLI | %97.4  | %64.0   | 1.855         |
| 2h        | EXTERNAL | UP        | 4167  | YETERLI | %95.8  | %61.9   | 2.025         |
| 2h        | INTERNAL | DOWN      | 8393  | YETERLI | %97.6  | %64.6   | 1.824         |
| 2h        | INTERNAL | UP        | 6412  | YETERLI | %96.2  | %61.3   | 2.002         |
| 4h        | EXTERNAL | DOWN      | 5772  | YETERLI | %98.0  | %66.3   | 2.001         |
| 4h        | EXTERNAL | UP        | 4403  | YETERLI | %97.0  | %63.3   | 2.116         |
| 4h        | INTERNAL | DOWN      | 9125  | YETERLI | %97.5  | %64.7   | 1.904         |
| 4h        | INTERNAL | UP        | 6267  | YETERLI | %96.6  | %63.5   | 2.084         |

## Hacim — koşullandırma değişkeni
### Dokunuş tepkisi x hacim çeyreği (rvol)

| timeframe | hacim_kovasi | n     | guven   | tepki_CALISTI | ort_yon_h12 | ort_pay_5 | ort_h12_decay | ort_rvol |
|-----------|--------------|-------|---------|---------------|-------------|-----------|---------------|----------|
| 1d        | KULLANILAMAZ | 6373  | YETERLI | %65.9         | 2.060       | 0.523     | 2.189         | -        |
| 1d        | Q1_dusuk     | 4028  | YETERLI | %63.3         | 1.911       | 0.646     | 1.870         | 0.530    |
| 1d        | Q2           | 6526  | YETERLI | %66.9         | 2.046       | 0.367     | 2.425         | 0.910    |
| 1d        | Q3           | 4743  | YETERLI | %63.7         | 1.919       | 0.576     | 2.341         | 1.417    |
| 1d        | Q4_yuksek    | 3193  | YETERLI | %61.7         | 1.803       | 0.508     | 1.750         | 2.934    |
| 1h        | KULLANILAMAZ | 4538  | YETERLI | %63.0         | 1.957       | 0.526     | 2.773         | -        |
| 1h        | Q1_dusuk     | 30467 | YETERLI | %66.9         | 2.000       | 0.581     | 1.658         | 0.144    |
| 1h        | Q2           | 14804 | YETERLI | %71.2         | 2.221       | 0.691     | 1.525         | 0.924    |
| 1h        | Q3           | 17339 | YETERLI | %67.5         | 2.080       | 0.643     | 1.761         | 1.449    |
| 1h        | Q4_yuksek    | 23347 | YETERLI | %61.4         | 1.811       | 0.589     | 1.820         | 3.454    |
| 2h        | KULLANILAMAZ | 4239  | YETERLI | %65.7         | 1.999       | 0.597     | 1.763         | -        |
| 2h        | Q1_dusuk     | 11380 | YETERLI | %68.8         | 2.145       | 0.690     | 1.626         | 0.525    |
| 2h        | Q2           | 18264 | YETERLI | %67.5         | 2.076       | 0.662     | 1.771         | 0.915    |
| 2h        | Q3           | 15664 | YETERLI | %64.9         | 1.967       | 0.625     | 2.540         | 1.424    |
| 2h        | Q4_yuksek    | 13411 | YETERLI | %60.1         | 1.749       | 0.548     | 1.826         | 3.207    |
| 4h        | KULLANILAMAZ | 4544  | YETERLI | %64.4         | 1.940       | 0.570     | 1.568         | -        |
| 4h        | Q1_dusuk     | 11180 | YETERLI | %69.4         | 2.209       | 0.691     | 1.968         | 0.494    |
| 4h        | Q2           | 17457 | YETERLI | %68.3         | 2.102       | 0.629     | 5.004         | 0.927    |
| 4h        | Q3           | 19307 | YETERLI | %65.9         | 2.012       | 0.587     | 1.849         | 1.433    |
| 4h        | Q4_yuksek    | 17102 | YETERLI | %59.2         | 1.757       | 0.497     | 1.981         | 3.087    |

### MS event devamlılığı x hacim çeyreği

| timeframe | hacim_kovasi | n     | guven   | CALISTI | uyumlu | ort_devam_h12 |
|-----------|--------------|-------|---------|---------|--------|---------------|
| 1d        | KULLANILAMAZ | 5005  | YETERLI | %67.0   | %95.3  | 2.109         |
| 1d        | Q1_dusuk     | 2468  | YETERLI | %63.0   | %95.8  | 1.879         |
| 1d        | Q2           | 4375  | YETERLI | %67.3   | %96.5  | 2.061         |
| 1d        | Q3           | 3349  | YETERLI | %65.0   | %96.2  | 2.159         |
| 1d        | Q4_yuksek    | 2212  | YETERLI | %72.1   | %96.2  | 2.416         |
| 1h        | KULLANILAMAZ | 5166  | YETERLI | %62.9   | %95.1  | 2.099         |
| 1h        | Q1_dusuk     | 27884 | YETERLI | %64.0   | %97.2  | 1.979         |
| 1h        | Q2           | 17809 | YETERLI | %64.6   | %96.7  | 2.005         |
| 1h        | Q3           | 19655 | YETERLI | %64.6   | %96.7  | 2.044         |
| 1h        | Q4_yuksek    | 23605 | YETERLI | %66.1   | %97.1  | 2.178         |
| 2h        | KULLANILAMAZ | 4598  | YETERLI | %64.7   | %96.2  | 1.970         |
| 2h        | Q1_dusuk     | 7682  | YETERLI | %63.5   | %96.7  | 1.963         |
| 2h        | Q2           | 12901 | YETERLI | %64.0   | %96.8  | 1.993         |
| 2h        | Q3           | 11113 | YETERLI | %65.3   | %97.4  | 2.067         |
| 2h        | Q4_yuksek    | 9434  | YETERLI | %68.2   | %96.7  | 2.291         |
| 4h        | KULLANILAMAZ | 4571  | YETERLI | %64.7   | %94.9  | 2.022         |
| 4h        | Q1_dusuk     | 8422  | YETERLI | %64.7   | %95.3  | 2.028         |
| 4h        | Q2           | 11370 | YETERLI | %65.4   | %97.3  | 2.129         |
| 4h        | Q3           | 12338 | YETERLI | %66.1   | %98.2  | 2.096         |
| 4h        | Q4_yuksek    | 11204 | YETERLI | %70.8   | %98.4  | 2.449         |
