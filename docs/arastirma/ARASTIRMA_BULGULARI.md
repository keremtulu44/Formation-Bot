# Formation-Bot Arşiv Araştırma Raporu
> Bu dosya tablo ekidir: ham aggregatlar soru başına bölümlenir.
> Okunabilir özet ve yorum: `docs/arastirma/ARASTIRMA_SONUCLARI.md`.
> Yalnız karar için okuyan, aşağıdaki tablolara inmeden özetle yetinebilir.
Kaynak: `backfill_data/` (365 gün derin çekim) · Sembol: 44 · Havuz dışı: BRENT

## Kapsam
| timeframe | sembol | ort_bar | toplam_zone | toplam_epizot | toplam_swing | toplam_event | toplam_rol_araligi | ms_hatali_seri |
|-----------|--------|---------|-------------|---------------|--------------|--------------|--------------------|----------------|
| 1d        | 44     | 503     | 5564        | 6239          | 8204         | 4605         | 5992               | 0              |
| 1h        | 44     | 3253    | 16182       | 24723         | 50082        | 25743        | 36226              | 0              |
| 2h        | 44     | 1500    | 14158       | 16776         | 23305        | 11993        | 16929              | 0              |
| 4h        | 44     | 1500    | 15205       | 18056         | 24377        | 12924        | 17815              | 0              |

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
| 1d        | FVG    | 2144  | YETERLI | %71.9      | %0.7     | %0.0         | %27.4      | 0.733      |
| 1d        | OB     | 3420  | YETERLI | %61.0      | %18.8    | %10.5        | %9.8       | 1.365      |
| 1h        | OB     | 16182 | YETERLI | %59.3      | %21.7    | %13.2        | %5.8       | 1.528      |
| 2h        | FVG    | 5809  | YETERLI | %75.1      | %0.8     | %0.0         | %24.1      | 0.767      |
| 2h        | OB     | 8349  | YETERLI | %59.8      | %21.0    | %12.1        | %7.1       | 1.476      |
| 4h        | FVG    | 6431  | YETERLI | %76.2      | %1.0     | %0.0         | %22.8      | 0.781      |
| 4h        | OB     | 8774  | YETERLI | %59.8      | %20.2    | %13.0        | %7.0       | 1.485      |

## Soru 2 — %kaçı geçildi, %kaçı tepki aldı?
### Zone seviyesi: temas / geçilme / dolum

| timeframe | family | n     | guven   | temas_var | gecildi_violation | full_fill | sansur_payi | ort_omur_bar | ort_yukseklik_atr |
|-----------|--------|-------|---------|-----------|-------------------|-----------|-------------|--------------|-------------------|
| 1d        | FVG    | 2144  | YETERLI | %72.6     | %0.0              | %40.0     | %1.9        | 5.584        | 0.628             |
| 1d        | OB     | 3420  | YETERLI | %90.2     | %85.6             | %0.0      | %14.4       | 35.217       | 0.957             |
| 1h        | OB     | 16182 | YETERLI | %94.2     | %93.2             | %0.0      | %6.8        | 97.121       | 0.953             |
| 2h        | FVG    | 5809  | YETERLI | %75.9     | %0.0              | %40.4     | %0.4        | 5.735        | 0.659             |
| 2h        | OB     | 8349  | YETERLI | %92.9     | %91.0             | %0.0      | %9.0        | 54.840       | 0.952             |
| 4h        | FVG    | 6431  | YETERLI | %77.2     | %0.0              | %40.9     | %0.3        | 5.354        | 0.684             |
| 4h        | OB     | 8774  | YETERLI | %93.0     | %91.7             | %0.0      | %8.3        | 63.377       | 0.958             |

### Dokunuş seviyesi: beklenen yönde tepki (zone yönü)

| timeframe | family | n     | guven   | yon_tepki_CALISTI | yon_tepki_AZ | yon_tepki_YOK | yon_tepki_TERS | ort_yon_h12_atr | ort_yon_uzun_tepe_h40 |
|-----------|--------|-------|---------|-------------------|--------------|---------------|----------------|-----------------|-----------------------|
| 1d        | FVG    | 1572  | YETERLI | %64.8             | %17.6        | %4.8          | %12.5          | 1.952           | 3.980                 |
| 1d        | OB     | 4667  | YETERLI | %63.7             | %14.7        | %4.8          | %15.6          | 1.927           | 3.739                 |
| 1h        | OB     | 24723 | YETERLI | %66.7             | %14.7        | %4.8          | %13.7          | 2.029           | 3.842                 |
| 2h        | FVG    | 4453  | YETERLI | %66.3             | %18.5        | %4.6          | %10.6          | 2.046           | 3.920                 |
| 2h        | OB     | 12323 | YETERLI | %65.7             | %15.1        | %4.5          | %14.4          | 1.932           | 3.762                 |
| 4h        | FVG    | 5024  | YETERLI | %66.3             | %18.1        | %4.9          | %10.7          | 2.042           | 3.848                 |
| 4h        | OB     | 13032 | YETERLI | %64.7             | %15.0        | %4.4          | %15.4          | 1.942           | 3.878                 |

## Soru 3 — Kenar-ancored tepki (ATR)
| timeframe | family | dokunulan_kenar | n     | guven   | tepki_CALISTI | tepki_AZ | tepki_YOK | tepki_TERS | OLCULEMEDI | ort_kenar_h12 | ort_kenar_tepe | ort_kenar_uzun_tepe |
|-----------|--------|-----------------|-------|---------|---------------|----------|-----------|------------|------------|---------------|----------------|---------------------|
| 1d        | FVG    | ALT_KENAR       | 527   | YETERLI | %56.5         | %15.2    | %7.0      | %21.3      | %0.0       | 1.783         | 1.783          | 3.964               |
| 1d        | FVG    | TUM_ZONE        | 514   | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1d        | FVG    | UST_KENAR       | 526   | YETERLI | %60.6         | %19.2    | %5.7      | %13.9      | %0.6       | 1.856         | 1.856          | 3.327               |
| 1d        | FVG    | ZONE_ICI        | 5     | ZAYIF   | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1d        | OB     | ALT_KENAR       | 1911  | YETERLI | %63.0         | %13.3    | %4.3      | %18.6      | %0.7       | 2.226         | 2.226          | 4.761               |
| 1d        | OB     | TUM_ZONE        | 646   | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1d        | OB     | UST_KENAR       | 2053  | YETERLI | %58.8         | %18.2    | %4.5      | %16.7      | %1.8       | 1.706         | 1.706          | 3.088               |
| 1d        | OB     | ZONE_ICI        | 57    | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1h        | OB     | ALT_KENAR       | 9342  | YETERLI | %57.8         | %15.3    | %6.1      | %20.7      | %0.1       | 1.974         | 1.974          | 4.082               |
| 1h        | OB     | TUM_ZONE        | 5235  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 1h        | OB     | UST_KENAR       | 10069 | YETERLI | %59.0         | %16.1    | %6.1      | %18.7      | %0.1       | 1.773         | 1.773          | 3.571               |
| 1h        | OB     | ZONE_ICI        | 77    | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 2h        | FVG    | ALT_KENAR       | 1403  | YETERLI | %55.2         | %19.5    | %8.1      | %17.0      | %0.1       | 1.774         | 1.774          | 3.710               |
| 2h        | FVG    | TUM_ZONE        | 1551  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 2h        | FVG    | UST_KENAR       | 1488  | YETERLI | %55.5         | %20.8    | %6.6      | %17.1      | %0.0       | 1.531         | 1.531          | 3.226               |
| 2h        | FVG    | ZONE_ICI        | 11    | ZAYIF   | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 2h        | OB     | ALT_KENAR       | 4809  | YETERLI | %58.5         | %15.8    | %5.5      | %19.9      | %0.3       | 1.973         | 1.973          | 4.107               |
| 2h        | OB     | TUM_ZONE        | 2390  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 2h        | OB     | UST_KENAR       | 5080  | YETERLI | %60.5         | %16.6    | %5.6      | %17.0      | %0.3       | 1.871         | 1.871          | 3.616               |
| 2h        | OB     | ZONE_ICI        | 44    | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 4h        | FVG    | ALT_KENAR       | 1709  | YETERLI | %56.0         | %17.3    | %8.5      | %18.1      | %0.1       | 1.740         | 1.740          | 3.966               |
| 4h        | FVG    | TUM_ZONE        | 1724  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 4h        | FVG    | UST_KENAR       | 1585  | YETERLI | %58.4         | %18.4    | %6.2      | %16.9      | %0.1       | 1.648         | 1.648          | 3.355               |
| 4h        | FVG    | ZONE_ICI        | 6     | ZAYIF   | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 4h        | OB     | ALT_KENAR       | 5135  | YETERLI | %61.1         | %14.2    | %5.3      | %19.1      | %0.3       | 2.101         | 2.101          | 4.307               |
| 4h        | OB     | TUM_ZONE        | 2643  | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |
| 4h        | OB     | UST_KENAR       | 5183  | YETERLI | %59.7         | %15.5    | %5.4      | %18.8      | %0.6       | 1.821         | 1.821          | 3.409               |
| 4h        | OB     | ZONE_ICI        | 71    | YETERLI | %0.0          | %0.0     | %0.0      | %0.0       | %100.0     | -             | -              | -                   |

### Kenar-ancored: ATR eşik ızgarası aşım oranı (h12)

| timeframe | n     | guven   | >=0.25 ATR | >=0.5 ATR | >=1 ATR | >=1.5 ATR | >=2 ATR |
|-----------|-------|---------|------------|-----------|---------|-----------|---------|
| 1d        | 6239  | YETERLI | %77.3      | %72.5     | %61.0   | %49.7     | %39.3   |
| 1h        | 24723 | YETERLI | %74.2      | %69.3     | %58.5   | %48.1     | %38.6   |
| 2h        | 16776 | YETERLI | %75.8      | %70.2     | %58.7   | %48.1     | %38.5   |
| 4h        | 18056 | YETERLI | %75.4      | %70.3     | %59.8   | %48.8     | %39.2   |

## Soru 4 — Yüksek zone ayırt edici mi, tepki anlık mı kalıcı mı?
| timeframe | family | yukseklik_kovasi | n     | guven   | ort_pay_5 | ort_pay_3 | ort_h12_decay | ort_tepe_h12 | ort_uzun_tepe_h40 | uzun/ana_tepe_orani | tepki_CALISTI |
|-----------|--------|------------------|-------|---------|-----------|-----------|---------------|--------------|-------------------|---------------------|---------------|
| 1d        | FVG    | 0-0.5            | 806   | YETERLI | 0.670     | 0.532     | 2.351         | 1.903        | 3.990             | 3.903               | %64.3         |
| 1d        | FVG    | 0.5-1            | 507   | YETERLI | 0.594     | 0.428     | 1.611         | 1.958        | 3.888             | 2.308               | %63.7         |
| 1d        | FVG    | 1-2              | 229   | YETERLI | 0.645     | 0.440     | 1.722         | 2.019        | 4.140             | 2.334               | %66.8         |
| 1d        | FVG    | >=2              | 30    | YETERLI | 0.817     | 0.710     | 0.637         | 2.634        | 4.042             | 1.683               | %80.0         |
| 1d        | OB     | 0-0.5            | 331   | YETERLI | 0.631     | 0.498     | 2.612         | 1.780        | 3.992             | 4.070               | %59.8         |
| 1d        | OB     | 0.5-1            | 2348  | YETERLI | 0.548     | 0.395     | 2.409         | 1.977        | 3.858             | 3.096               | %65.0         |
| 1d        | OB     | 1-2              | 1643  | YETERLI | 0.577     | 0.381     | 2.283         | 1.922        | 3.683             | 2.868               | %63.9         |
| 1d        | OB     | >=2              | 204   | YETERLI | 0.555     | 0.388     | 2.249         | 1.794        | 3.056             | 2.558               | %66.2         |
| 1d        | OB     | BILINMEYEN       | 141   | YETERLI | 0.278     | 0.088     | 1.213         | 1.599        | 2.477             | 2.057               | %45.4         |
| 1h        | OB     | 0-0.5            | 2701  | YETERLI | 0.632     | 0.493     | 2.177         | 2.101        | 3.949             | 2.718               | %65.9         |
| 1h        | OB     | 0.5-1            | 11808 | YETERLI | 0.612     | 0.474     | 1.826         | 2.023        | 3.872             | 2.887               | %66.4         |
| 1h        | OB     | 1-2              | 8465  | YETERLI | 0.605     | 0.444     | 1.517         | 2.025        | 3.773             | 2.425               | %67.0         |
| 1h        | OB     | >=2              | 1662  | YETERLI | 0.586     | 0.375     | 1.295         | 1.979        | 3.834             | 2.388               | %69.4         |
| 1h        | OB     | BILINMEYEN       | 87    | YETERLI | 0.782     | 0.709     | 2.005         | 2.064        | 3.198             | 1.756               | %48.3         |
| 2h        | FVG    | 0-0.5            | 2256  | YETERLI | 0.659     | 0.496     | 2.038         | 2.023        | 3.819             | 2.946               | %66.2         |
| 2h        | FVG    | 0.5-1            | 1384  | YETERLI | 0.630     | 0.479     | 1.657         | 1.940        | 3.865             | 2.771               | %65.2         |
| 2h        | FVG    | 1-2              | 648   | YETERLI | 0.718     | 0.565     | 1.497         | 2.043        | 3.946             | 2.495               | %66.0         |
| 2h        | FVG    | >=2              | 165   | YETERLI | 0.755     | 0.680     | 0.733         | 3.268        | 5.667             | 1.986               | %77.0         |
| 2h        | OB     | 0-0.5            | 1183  | YETERLI | 0.654     | 0.463     | 2.561         | 1.958        | 3.866             | 3.312               | %66.3         |
| 2h        | OB     | 0.5-1            | 6108  | YETERLI | 0.643     | 0.459     | 1.857         | 1.958        | 3.827             | 2.757               | %65.4         |
| 2h        | OB     | 1-2              | 4192  | YETERLI | 0.606     | 0.393     | 1.598         | 1.878        | 3.632             | 2.572               | %64.9         |
| 2h        | OB     | >=2              | 717   | YETERLI | 0.478     | 0.296     | 0.918         | 1.971        | 3.827             | 2.850               | %72.8         |
| 2h        | OB     | BILINMEYEN       | 123   | YETERLI | 0.406     | 0.279     | 2.280         | 2.065        | 3.599             | 4.183               | %57.7         |
| 4h        | FVG    | 0-0.5            | 2416  | YETERLI | 0.657     | 0.517     | 2.289         | 1.958        | 3.725             | 3.460               | %65.7         |
| 4h        | FVG    | 0.5-1            | 1605  | YETERLI | 0.649     | 0.512     | 2.093         | 1.971        | 3.735             | 2.711               | %64.3         |
| 4h        | FVG    | 1-2              | 822   | YETERLI | 0.639     | 0.490     | 1.744         | 2.216        | 4.066             | 2.358               | %70.0         |
| 4h        | FVG    | >=2              | 181   | YETERLI | 0.626     | 0.529     | 0.826         | 3.009        | 5.505             | 2.460               | %75.7         |
| 4h        | OB     | 0-0.5            | 1638  | YETERLI | 0.625     | 0.502     | 33.903        | 2.003        | 4.015             | 74.419              | %64.8         |
| 4h        | OB     | 0.5-1            | 5510  | YETERLI | 0.621     | 0.483     | 2.213         | 1.947        | 3.876             | 3.209               | %65.0         |
| 4h        | OB     | 1-2              | 4981  | YETERLI | 0.545     | 0.383     | 1.532         | 1.897        | 3.783             | 2.846               | %64.4         |
| 4h        | OB     | >=2              | 752   | YETERLI | 0.492     | 0.330     | 1.068         | 2.055        | 4.245             | 2.799               | %67.3         |
| 4h        | OB     | BILINMEYEN       | 151   | YETERLI | 0.445     | 0.159     | 1.067         | 2.085        | 3.697             | 3.620               | %48.3         |

_Okuma: `ort_pay_5` yüksek + `uzun/ana_tepe_orani` ~1 -> **anlık**; `ort_pay_5` düşük + oran >>1 -> **yavaş ama kalıcı**._

_`ort_h12_decay` 1'den büyükse pencere, tepenin altına kapanmıştır (kapanış referansın ters tarafında); bu "tepki verdi sonra tamamen geri verdi" demektir, ölçüm hatası değildir._

## Soru 5 — MS BOS/CHOCH: yön ile tepki uyuşuyor mu?
### Scope x event tipi

| timeframe | scope    | event_type            | n    | guven   | uyumlu | CALISTI | AZ_DEVAM | DEVAM_YOK | TERS | sansur | ort_devam_h12 | ort_ters_h12 |
|-----------|----------|-----------------------|------|---------|--------|---------|----------|-----------|------|--------|---------------|--------------|
| 1d        | EXTERNAL | EVENT_BOS             | 470  | YETERLI | %97.7  | %68.3   | %23.2    | %6.4      | %2.1 | %0.4   | 2.253         | 2.128        |
| 1d        | EXTERNAL | EVENT_CHOCH           | 173  | YETERLI | %95.4  | %63.6   | %23.7    | %9.2      | %2.9 | %1.2   | 2.283         | 2.042        |
| 1d        | EXTERNAL | EVENT_FALSE_BREAK     | 29   | KISMI   | %96.6  | %62.1   | %20.7    | %13.8     | %3.4 | %0.0   | 1.907         | 2.492        |
| 1d        | EXTERNAL | EVENT_SWEEP           | 886  | YETERLI | %96.4  | %66.0   | %23.5    | %7.6      | %2.9 | %1.1   | 1.974         | 2.232        |
| 1d        | EXTERNAL | EVENT_TRANSITION_FAIL | 61   | YETERLI | %100.0 | %77.0   | %21.3    | %1.6      | %0.0 | %1.6   | 2.363         | 1.669        |
| 1d        | INTERNAL | EVENT_BOS             | 844  | YETERLI | %94.7  | %67.3   | %21.9    | %5.9      | %2.7 | %1.1   | 2.285         | 1.953        |
| 1d        | INTERNAL | EVENT_CHOCH           | 328  | YETERLI | %97.6  | %63.4   | %25.6    | %9.1      | %1.8 | %3.0   | 1.924         | 2.211        |
| 1d        | INTERNAL | EVENT_FALSE_BREAK     | 63   | YETERLI | %92.1  | %69.8   | %20.6    | %3.2      | %3.2 | %4.8   | 1.974         | 1.849        |
| 1d        | INTERNAL | EVENT_SWEEP           | 1637 | YETERLI | %96.7  | %66.3   | %24.7    | %6.5      | %2.3 | %1.3   | 2.022         | 2.000        |
| 1d        | INTERNAL | EVENT_TRANSITION_FAIL | 114  | YETERLI | %95.6  | %63.2   | %24.6    | %8.8      | %3.5 | %0.0   | 2.210         | 2.166        |
| 1h        | EXTERNAL | EVENT_BOS             | 2528 | YETERLI | %97.2  | %67.1   | %23.3    | %8.7      | %0.9 | %0.3   | 2.273         | 1.993        |
| 1h        | EXTERNAL | EVENT_CHOCH           | 977  | YETERLI | %97.0  | %70.5   | %19.3    | %8.4      | %1.7 | %0.4   | 2.345         | 1.931        |
| 1h        | EXTERNAL | EVENT_FALSE_BREAK     | 180  | YETERLI | %98.9  | %65.0   | %23.3    | %11.1     | %0.6 | %0.0   | 1.856         | 1.879        |
| 1h        | EXTERNAL | EVENT_SWEEP           | 5575 | YETERLI | %97.0  | %62.9   | %25.9    | %9.9      | %1.3 | %0.1   | 1.913         | 2.112        |
| 1h        | EXTERNAL | EVENT_TRANSITION_FAIL | 270  | YETERLI | %97.0  | %67.8   | %21.1    | %9.3      | %1.9 | %0.4   | 2.253         | 2.076        |
| 1h        | INTERNAL | EVENT_BOS             | 4706 | YETERLI | %96.7  | %67.5   | %22.0    | %9.1      | %1.0 | %0.3   | 2.242         | 1.971        |
| 1h        | INTERNAL | EVENT_CHOCH           | 1748 | YETERLI | %96.9  | %66.0   | %23.3    | %9.4      | %1.2 | %0.2   | 2.134         | 2.030        |
| 1h        | INTERNAL | EVENT_FALSE_BREAK     | 327  | YETERLI | %95.7  | %60.9   | %25.7    | %11.9     | %1.2 | %0.3   | 1.890         | 2.087        |
| 1h        | INTERNAL | EVENT_SWEEP           | 8913 | YETERLI | %97.0  | %63.6   | %25.8    | %9.1      | %1.3 | %0.3   | 1.930         | 2.107        |
| 1h        | INTERNAL | EVENT_TRANSITION_FAIL | 519  | YETERLI | %96.7  | %68.8   | %21.2    | %8.3      | %1.7 | %0.4   | 2.269         | 1.904        |
| 2h        | EXTERNAL | EVENT_BOS             | 1221 | YETERLI | %97.3  | %67.9   | %21.9    | %8.8      | %1.4 | %0.9   | 2.218         | 2.010        |
| 2h        | EXTERNAL | EVENT_CHOCH           | 500  | YETERLI | %97.2  | %68.6   | %21.6    | %8.2      | %1.6 | %0.6   | 2.292         | 1.829        |
| 2h        | EXTERNAL | EVENT_FALSE_BREAK     | 83   | YETERLI | %96.4  | %63.9   | %24.1    | %9.6      | %2.4 | %1.2   | 1.926         | 2.195        |
| 2h        | EXTERNAL | EVENT_SWEEP           | 2619 | YETERLI | %96.8  | %63.3   | %24.7    | %10.4     | %1.6 | %0.6   | 1.853         | 2.092        |
| 2h        | EXTERNAL | EVENT_TRANSITION_FAIL | 134  | YETERLI | %95.5  | %64.2   | %24.6    | %9.7      | %1.5 | %0.7   | 2.195         | 2.114        |
| 2h        | INTERNAL | EVENT_BOS             | 2213 | YETERLI | %97.0  | %67.9   | %22.0    | %8.3      | %1.3 | %0.4   | 2.232         | 1.958        |
| 2h        | INTERNAL | EVENT_CHOCH           | 844  | YETERLI | %96.6  | %67.8   | %22.3    | %7.8      | %2.1 | %0.8   | 2.174         | 1.988        |
| 2h        | INTERNAL | EVENT_FALSE_BREAK     | 166  | YETERLI | %97.6  | %71.7   | %21.1    | %5.4      | %1.2 | %0.0   | 2.089         | 1.560        |
| 2h        | INTERNAL | EVENT_SWEEP           | 3969 | YETERLI | %97.1  | %65.7   | %24.5    | %8.1      | %1.5 | %0.4   | 1.939         | 2.078        |
| 2h        | INTERNAL | EVENT_TRANSITION_FAIL | 244  | YETERLI | %98.4  | %69.3   | %24.2    | %5.7      | %0.8 | %1.2   | 2.202         | 1.867        |
| 4h        | EXTERNAL | EVENT_BOS             | 1207 | YETERLI | %97.4  | %70.3   | %21.0    | %7.5      | %1.3 | %1.1   | 2.318         | 2.006        |
| 4h        | EXTERNAL | EVENT_CHOCH           | 487  | YETERLI | %99.0  | %72.1   | %18.1    | %9.2      | %0.6 | %0.2   | 2.403         | 1.992        |
| 4h        | EXTERNAL | EVENT_FALSE_BREAK     | 97   | YETERLI | %93.8  | %58.8   | %25.8    | %11.3     | %3.1 | %1.0   | 2.058         | 1.963        |
| 4h        | EXTERNAL | EVENT_SWEEP           | 2833 | YETERLI | %97.8  | %65.6   | %24.1    | %9.1      | %1.2 | %0.6   | 2.021         | 2.101        |
| 4h        | EXTERNAL | EVENT_TRANSITION_FAIL | 161  | YETERLI | %95.7  | %70.8   | %19.3    | %7.5      | %2.5 | %1.2   | 2.432         | 2.095        |
| 4h        | INTERNAL | EVENT_BOS             | 2444 | YETERLI | %97.0  | %66.6   | %22.8    | %8.6      | %1.3 | %0.5   | 2.231         | 2.072        |
| 4h        | INTERNAL | EVENT_CHOCH           | 941  | YETERLI | %98.5  | %71.6   | %21.5    | %6.1      | %0.9 | %0.6   | 2.367         | 1.915        |
| 4h        | INTERNAL | EVENT_FALSE_BREAK     | 199  | YETERLI | %95.0  | %62.3   | %27.6    | %5.5      | %3.5 | %0.5   | 1.884         | 2.142        |
| 4h        | INTERNAL | EVENT_SWEEP           | 4290 | YETERLI | %97.4  | %64.1   | %25.1    | %9.1      | %1.4 | %0.5   | 1.950         | 2.124        |
| 4h        | INTERNAL | EVENT_TRANSITION_FAIL | 265  | YETERLI | %96.6  | %69.4   | %21.5    | %7.5      | %1.5 | %1.5   | 2.565         | 1.888        |

### Scope x yön (BOS/CHOCH ayrımıyla)

| timeframe | scope    | event_type  | direction | n    | guven   | uyumlu | CALISTI | AZ_DEVAM | DEVAM_YOK | TERS | sansur | ort_devam_h12 | ort_ters_h12 |
|-----------|----------|-------------|-----------|------|---------|--------|---------|----------|-----------|------|--------|---------------|--------------|
| 1d        | EXTERNAL | EVENT_BOS   | DOWN      | 238  | YETERLI | %97.1  | %60.9   | %30.7    | %5.5      | %2.9 | %0.8   | 1.751         | 2.022        |
| 1d        | EXTERNAL | EVENT_BOS   | UP        | 232  | YETERLI | %98.3  | %75.9   | %15.5    | %7.3      | %1.3 | %0.0   | 2.768         | 2.236        |
| 1d        | EXTERNAL | EVENT_CHOCH | DOWN      | 93   | YETERLI | %92.5  | %55.9   | %24.7    | %12.9     | %5.4 | %2.2   | 1.677         | 1.885        |
| 1d        | EXTERNAL | EVENT_CHOCH | UP        | 80   | YETERLI | %98.8  | %72.5   | %22.5    | %5.0      | %0.0 | %0.0   | 2.980         | 2.221        |
| 1d        | INTERNAL | EVENT_BOS   | DOWN      | 421  | YETERLI | %94.8  | %61.0   | %29.0    | %5.2      | %3.8 | %1.9   | 1.780         | 2.047        |
| 1d        | INTERNAL | EVENT_BOS   | UP        | 423  | YETERLI | %94.6  | %73.5   | %14.9    | %6.6      | %1.7 | %0.2   | 2.800         | 1.858        |
| 1d        | INTERNAL | EVENT_CHOCH | DOWN      | 163  | YETERLI | %97.5  | %61.3   | %24.5    | %11.7     | %2.5 | %0.6   | 1.635         | 1.939        |
| 1d        | INTERNAL | EVENT_CHOCH | UP        | 165  | YETERLI | %97.6  | %65.5   | %26.7    | %6.7      | %1.2 | %5.5   | 2.210         | 2.480        |
| 1h        | EXTERNAL | EVENT_BOS   | DOWN      | 1206 | YETERLI | %97.4  | %67.7   | %22.1    | %9.0      | %1.1 | %0.6   | 2.172         | 2.110        |
| 1h        | EXTERNAL | EVENT_BOS   | UP        | 1322 | YETERLI | %97.0  | %66.5   | %24.4    | %8.4      | %0.8 | %0.1   | 2.365         | 1.888        |
| 1h        | EXTERNAL | EVENT_CHOCH | DOWN      | 505  | YETERLI | %96.4  | %68.1   | %22.0    | %7.7      | %2.2 | %0.8   | 2.171         | 1.971        |
| 1h        | EXTERNAL | EVENT_CHOCH | UP        | 472  | YETERLI | %97.7  | %73.1   | %16.5    | %9.1      | %1.3 | %0.0   | 2.532         | 1.889        |
| 1h        | INTERNAL | EVENT_BOS   | DOWN      | 2392 | YETERLI | %96.4  | %66.6   | %23.2    | %8.1      | %1.2 | %0.6   | 2.134         | 2.063        |
| 1h        | INTERNAL | EVENT_BOS   | UP        | 2314 | YETERLI | %97.1  | %68.4   | %20.7    | %10.0     | %0.8 | %0.0   | 2.352         | 1.877        |
| 1h        | INTERNAL | EVENT_CHOCH | DOWN      | 878  | YETERLI | %96.9  | %62.6   | %26.5    | %9.2      | %1.5 | %0.5   | 1.893         | 2.184        |
| 1h        | INTERNAL | EVENT_CHOCH | UP        | 870  | YETERLI | %96.9  | %69.3   | %20.1    | %9.7      | %0.9 | %0.0   | 2.377         | 1.875        |
| 2h        | EXTERNAL | EVENT_BOS   | DOWN      | 632  | YETERLI | %97.6  | %64.9   | %23.3    | %10.6     | %1.3 | %1.6   | 2.045         | 2.120        |
| 2h        | EXTERNAL | EVENT_BOS   | UP        | 589  | YETERLI | %96.9  | %71.1   | %20.5    | %6.8      | %1.5 | %0.2   | 2.404         | 1.892        |
| 2h        | EXTERNAL | EVENT_CHOCH | DOWN      | 250  | YETERLI | %96.8  | %65.6   | %22.0    | %10.4     | %2.0 | %1.2   | 2.056         | 1.835        |
| 2h        | EXTERNAL | EVENT_CHOCH | UP        | 250  | YETERLI | %97.6  | %71.6   | %21.2    | %6.0      | %1.2 | %0.0   | 2.528         | 1.823        |
| 2h        | INTERNAL | EVENT_BOS   | DOWN      | 1177 | YETERLI | %96.9  | %66.2   | %23.4    | %8.8      | %1.1 | %0.6   | 2.099         | 2.046        |
| 2h        | INTERNAL | EVENT_BOS   | UP        | 1036 | YETERLI | %97.1  | %69.8   | %20.4    | %7.7      | %1.4 | %0.2   | 2.383         | 1.857        |
| 2h        | INTERNAL | EVENT_CHOCH | DOWN      | 411  | YETERLI | %96.4  | %67.2   | %21.4    | %9.2      | %2.2 | %1.7   | 1.931         | 2.042        |
| 2h        | INTERNAL | EVENT_CHOCH | UP        | 433  | YETERLI | %96.8  | %68.4   | %23.1    | %6.5      | %2.1 | %0.0   | 2.404         | 1.937        |
| 4h        | EXTERNAL | EVENT_BOS   | DOWN      | 615  | YETERLI | %96.9  | %68.9   | %21.5    | %8.0      | %1.6 | %1.8   | 2.020         | 2.090        |
| 4h        | EXTERNAL | EVENT_BOS   | UP        | 592  | YETERLI | %98.0  | %71.6   | %20.4    | %6.9      | %1.0 | %0.3   | 2.628         | 1.919        |
| 4h        | EXTERNAL | EVENT_CHOCH | DOWN      | 248  | YETERLI | %99.6  | %69.0   | %17.3    | %13.3     | %0.4 | %0.4   | 2.186         | 1.844        |
| 4h        | EXTERNAL | EVENT_CHOCH | UP        | 239  | YETERLI | %98.3  | %75.3   | %18.8    | %5.0      | %0.8 | %0.0   | 2.629         | 2.146        |
| 4h        | INTERNAL | EVENT_BOS   | DOWN      | 1257 | YETERLI | %97.1  | %63.0   | %25.3    | %9.9      | %1.2 | %0.6   | 1.971         | 2.143        |
| 4h        | INTERNAL | EVENT_BOS   | UP        | 1187 | YETERLI | %97.0  | %70.4   | %20.2    | %7.2      | %1.3 | %0.3   | 2.507         | 1.996        |
| 4h        | INTERNAL | EVENT_CHOCH | DOWN      | 461  | YETERLI | %98.5  | %69.2   | %21.9    | %7.8      | %1.1 | %1.1   | 2.113         | 1.960        |
| 4h        | INTERNAL | EVENT_CHOCH | UP        | 480  | YETERLI | %98.5  | %74.0   | %21.0    | %4.4      | %0.6 | %0.2   | 2.611         | 1.871        |

### Motorun kendi outcome kararı (çapraz kontrol)

| timeframe | scope    | outcome                  | n     | guven   | adet   |
|-----------|----------|--------------------------|-------|---------|--------|
| 1d        | EXTERNAL | FAILED                   | 90    | YETERLI | %100.0 |
| 1d        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 108   | YETERLI | %100.0 |
| 1d        | EXTERNAL | OBSERVED                 | 1417  | YETERLI | %100.0 |
| 1d        | EXTERNAL | PENDING                  | 4     | ZAYIF   | %100.0 |
| 1d        | INTERNAL | FAILED                   | 177   | YETERLI | %100.0 |
| 1d        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 201   | YETERLI | %100.0 |
| 1d        | INTERNAL | OBSERVED                 | 2595  | YETERLI | %100.0 |
| 1d        | INTERNAL | PENDING                  | 13    | ZAYIF   | %100.0 |
| 1h        | EXTERNAL | FAILED                   | 450   | YETERLI | %100.0 |
| 1h        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 688   | YETERLI | %100.0 |
| 1h        | EXTERNAL | OBSERVED                 | 8373  | YETERLI | %100.0 |
| 1h        | EXTERNAL | PENDING                  | 19    | KISMI   | %100.0 |
| 1h        | INTERNAL | FAILED                   | 846   | YETERLI | %100.0 |
| 1h        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 1217  | YETERLI | %100.0 |
| 1h        | INTERNAL | OBSERVED                 | 14138 | YETERLI | %100.0 |
| 1h        | INTERNAL | PENDING                  | 12    | ZAYIF   | %100.0 |
| 2h        | EXTERNAL | FAILED                   | 217   | YETERLI | %100.0 |
| 2h        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 347   | YETERLI | %100.0 |
| 2h        | EXTERNAL | OBSERVED                 | 3974  | YETERLI | %100.0 |
| 2h        | EXTERNAL | PENDING                  | 19    | KISMI   | %100.0 |
| 2h        | INTERNAL | FAILED                   | 410   | YETERLI | %100.0 |
| 2h        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 584   | YETERLI | %100.0 |
| 2h        | INTERNAL | OBSERVED                 | 6426  | YETERLI | %100.0 |
| 2h        | INTERNAL | PENDING                  | 16    | KISMI   | %100.0 |
| 4h        | EXTERNAL | FAILED                   | 258   | YETERLI | %100.0 |
| 4h        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 315   | YETERLI | %100.0 |
| 4h        | EXTERNAL | OBSERVED                 | 4201  | YETERLI | %100.0 |
| 4h        | EXTERNAL | PENDING                  | 11    | ZAYIF   | %100.0 |
| 4h        | INTERNAL | FAILED                   | 464   | YETERLI | %100.0 |
| 4h        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 659   | YETERLI | %100.0 |
| 4h        | INTERNAL | OBSERVED                 | 6999  | YETERLI | %100.0 |
| 4h        | INTERNAL | PENDING                  | 17    | KISMI   | %100.0 |

## Soru 6 — PH/PL direnç/destek mi, çok denenen mi az denenen mi?
### Kararı verilebilir satırlar (sansürsüz)

| timeframe | scope    | rol | deneme_kovasi | n    | guven   | engelledi | engellemedi | ort_deneme_epizot | ort_deneme_bar | ort_rol_sure_bar | ort_bars_to_break |
|-----------|----------|-----|---------------|------|---------|-----------|-------------|-------------------|----------------|------------------|-------------------|
| 1d        | EXTERNAL | PH  | 0_deneme      | 201  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 34.493           | 76.316            |
| 1d        | EXTERNAL | PH  | 1_deneme      | 71   | YETERLI | %33.8     | %66.2       | 1.000             | 11.662         | 24.803           | 24.340            |
| 1d        | EXTERNAL | PH  | 2-3_deneme    | 50   | YETERLI | %22.0     | %78.0       | 2.380             | 15.660         | 20.000           | 18.649            |
| 1d        | EXTERNAL | PH  | 4plus_deneme  | 6    | ZAYIF   | %16.7     | %83.3       | 4.000             | 13.833         | 23.167           | 23.167            |
| 1d        | EXTERNAL | PL  | 0_deneme      | 172  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 36.471           | 72.929            |
| 1d        | EXTERNAL | PL  | 1_deneme      | 96   | YETERLI | %40.6     | %59.4       | 1.000             | 15.479         | 22.635           | 19.267            |
| 1d        | EXTERNAL | PL  | 2-3_deneme    | 63   | YETERLI | %31.7     | %68.3       | 2.286             | 13.587         | 22.873           | 24.909            |
| 1d        | EXTERNAL | PL  | 4plus_deneme  | 8    | ZAYIF   | %37.5     | %62.5       | 4.250             | 14.125         | 18.625           | 19.429            |
| 1d        | INTERNAL | PH  | 0_deneme      | 251  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 19.797           | 57.818            |
| 1d        | INTERNAL | PH  | 1_deneme      | 164  | YETERLI | %34.1     | %65.9       | 1.000             | 12.122         | 14.695           | 12.840            |
| 1d        | INTERNAL | PH  | 2-3_deneme    | 149  | YETERLI | %16.1     | %83.9       | 2.322             | 17.470         | 13.658           | 13.120            |
| 1d        | INTERNAL | PH  | 4plus_deneme  | 30   | YETERLI | %13.3     | %86.7       | 4.300             | 19.100         | 14.733           | 16.211            |
| 1d        | INTERNAL | PL  | 0_deneme      | 259  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 19.139           | 62.800            |
| 1d        | INTERNAL | PL  | 1_deneme      | 187  | YETERLI | %35.3     | %64.7       | 1.000             | 17.626         | 15.011           | 13.664            |
| 1d        | INTERNAL | PL  | 2-3_deneme    | 146  | YETERLI | %28.8     | %71.2       | 2.425             | 15.514         | 16.644           | 16.347            |
| 1d        | INTERNAL | PL  | 4plus_deneme  | 29   | KISMI   | %20.7     | %79.3       | 4.552             | 17.448         | 14.931           | 15.632            |
| 1h        | EXTERNAL | PH  | 0_deneme      | 1070 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 44.917           | 72.811            |
| 1h        | EXTERNAL | PH  | 1_deneme      | 392  | YETERLI | %32.7     | %67.3       | 1.000             | 13.112         | 28.500           | 26.866            |
| 1h        | EXTERNAL | PH  | 2-3_deneme    | 285  | YETERLI | %20.7     | %79.3       | 2.358             | 15.312         | 23.098           | 21.770            |
| 1h        | EXTERNAL | PH  | 4plus_deneme  | 58   | YETERLI | %20.7     | %79.3       | 4.448             | 16.397         | 24.586           | 23.200            |
| 1h        | EXTERNAL | PL  | 0_deneme      | 1233 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 44.766           | 78.985            |
| 1h        | EXTERNAL | PL  | 1_deneme      | 436  | YETERLI | %36.2     | %63.8       | 1.000             | 13.713         | 26.312           | 23.884            |
| 1h        | EXTERNAL | PL  | 2-3_deneme    | 235  | YETERLI | %27.2     | %72.8       | 2.302             | 13.991         | 24.438           | 24.193            |
| 1h        | EXTERNAL | PL  | 4plus_deneme  | 39   | YETERLI | %23.1     | %76.9       | 4.590             | 15.564         | 24.744           | 23.273            |
| 1h        | INTERNAL | PH  | 0_deneme      | 1557 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 25.507           | 58.559            |
| 1h        | INTERNAL | PH  | 1_deneme      | 878  | YETERLI | %32.6     | %67.4       | 1.000             | 15.428         | 14.581           | 13.869            |
| 1h        | INTERNAL | PH  | 2-3_deneme    | 843  | YETERLI | %23.8     | %76.2       | 2.370             | 16.435         | 15.887           | 15.761            |
| 1h        | INTERNAL | PH  | 4plus_deneme  | 194  | YETERLI | %17.5     | %82.5       | 4.428             | 17.531         | 15.418           | 15.551            |
| 1h        | INTERNAL | PL  | 0_deneme      | 1686 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 24.495           | 75.655            |
| 1h        | INTERNAL | PL  | 1_deneme      | 906  | YETERLI | %35.3     | %64.7       | 1.000             | 14.291         | 19.185           | 18.929            |
| 1h        | INTERNAL | PL  | 2-3_deneme    | 711  | YETERLI | %28.3     | %71.7       | 2.325             | 16.997         | 16.539           | 16.663            |
| 1h        | INTERNAL | PL  | 4plus_deneme  | 138  | YETERLI | %30.4     | %69.6       | 4.493             | 17.326         | 17.580           | 17.284            |
| 2h        | EXTERNAL | PH  | 0_deneme      | 558  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 41.934           | 68.585            |
| 2h        | EXTERNAL | PH  | 1_deneme      | 184  | YETERLI | %33.2     | %66.8       | 1.000             | 14.022         | 26.005           | 22.561            |
| 2h        | EXTERNAL | PH  | 2-3_deneme    | 158  | YETERLI | %26.6     | %73.4       | 2.323             | 15.418         | 23.171           | 21.296            |
| 2h        | EXTERNAL | PH  | 4plus_deneme  | 30   | YETERLI | %3.3      | %96.7       | 4.500             | 17.533         | 20.667           | 18.240            |
| 2h        | EXTERNAL | PL  | 0_deneme      | 544  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 41.669           | 76.352            |
| 2h        | EXTERNAL | PL  | 1_deneme      | 203  | YETERLI | %33.5     | %66.5       | 1.000             | 14.039         | 26.305           | 24.284            |
| 2h        | EXTERNAL | PL  | 2-3_deneme    | 131  | YETERLI | %32.1     | %67.9       | 2.267             | 14.099         | 24.496           | 24.579            |
| 2h        | EXTERNAL | PL  | 4plus_deneme  | 20   | KISMI   | %25.0     | %75.0       | 4.350             | 16.400         | 22.100           | 21.176            |
| 2h        | INTERNAL | PH  | 0_deneme      | 766  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 23.866           | 62.550            |
| 2h        | INTERNAL | PH  | 1_deneme      | 405  | YETERLI | %35.3     | %64.7       | 1.000             | 15.788         | 16.556           | 14.797            |
| 2h        | INTERNAL | PH  | 2-3_deneme    | 423  | YETERLI | %24.1     | %75.9       | 2.355             | 16.596         | 16.440           | 15.969            |
| 2h        | INTERNAL | PH  | 4plus_deneme  | 95   | YETERLI | %17.9     | %82.1       | 4.642             | 17.558         | 16.095           | 15.315            |
| 2h        | INTERNAL | PL  | 0_deneme      | 743  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 23.732           | 89.036            |
| 2h        | INTERNAL | PL  | 1_deneme      | 443  | YETERLI | %37.0     | %63.0       | 1.000             | 15.018         | 16.632           | 17.263            |
| 2h        | INTERNAL | PL  | 2-3_deneme    | 317  | YETERLI | %26.2     | %73.8       | 2.303             | 16.940         | 16.470           | 17.249            |
| 2h        | INTERNAL | PL  | 4plus_deneme  | 62   | YETERLI | %21.0     | %79.0       | 4.355             | 18.984         | 16.532           | 16.667            |
| 4h        | EXTERNAL | PH  | 0_deneme      | 554  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 42.690           | 68.625            |
| 4h        | EXTERNAL | PH  | 1_deneme      | 187  | YETERLI | %31.6     | %68.4       | 1.000             | 12.513         | 28.754           | 24.695            |
| 4h        | EXTERNAL | PH  | 2-3_deneme    | 156  | YETERLI | %19.9     | %80.1       | 2.282             | 14.404         | 22.308           | 22.500            |
| 4h        | EXTERNAL | PH  | 4plus_deneme  | 36   | YETERLI | %13.9     | %86.1       | 4.444             | 17.500         | 16.722           | 15.889            |
| 4h        | EXTERNAL | PL  | 0_deneme      | 528  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 42.714           | 69.931            |
| 4h        | EXTERNAL | PL  | 1_deneme      | 225  | YETERLI | %33.8     | %66.2       | 1.000             | 14.418         | 23.813           | 24.013            |
| 4h        | EXTERNAL | PL  | 2-3_deneme    | 117  | YETERLI | %24.8     | %75.2       | 2.342             | 15.513         | 20.940           | 20.688            |
| 4h        | EXTERNAL | PL  | 4plus_deneme  | 17   | KISMI   | %41.2     | %58.8       | 4.471             | 18.176         | 20.294           | 18.455            |
| 4h        | INTERNAL | PH  | 0_deneme      | 793  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 19.673           | 57.444            |
| 4h        | INTERNAL | PH  | 1_deneme      | 480  | YETERLI | %30.6     | %69.4       | 1.000             | 16.092         | 15.527           | 14.042            |
| 4h        | INTERNAL | PH  | 2-3_deneme    | 460  | YETERLI | %23.5     | %76.5       | 2.272             | 16.257         | 15.787           | 16.100            |
| 4h        | INTERNAL | PH  | 4plus_deneme  | 106  | YETERLI | %16.0     | %84.0       | 4.755             | 18.208         | 15.274           | 15.179            |
| 4h        | INTERNAL | PL  | 0_deneme      | 801  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 21.451           | 55.417            |
| 4h        | INTERNAL | PL  | 1_deneme      | 508  | YETERLI | %36.0     | %64.0       | 1.000             | 15.281         | 16.817           | 16.507            |
| 4h        | INTERNAL | PL  | 2-3_deneme    | 382  | YETERLI | %30.1     | %69.9       | 2.314             | 16.948         | 15.223           | 15.950            |
| 4h        | INTERNAL | PL  | 4plus_deneme  | 57   | YETERLI | %33.3     | %66.7       | 4.456             | 18.947         | 15.316           | 15.000            |

### Karar verilemeyen satırlar (sağdan sansürlü — payda dışı)

| timeframe | scope    | rol | deneme_kovasi | n  | guven   | ort_deneme_epizot | ort_rol_sure_bar |
|-----------|----------|-----|---------------|----|---------|-------------------|------------------|
| 1d        | EXTERNAL | PH  | 0_deneme      | 33 | YETERLI | 0.000             | 18.909           |
| 1d        | EXTERNAL | PH  | 1_deneme      | 1  | ZAYIF   | 1.000             | 23.000           |
| 1d        | EXTERNAL | PH  | 2-3_deneme    | 1  | ZAYIF   | 3.000             | 38.000           |
| 1d        | EXTERNAL | PL  | 0_deneme      | 2  | ZAYIF   | 0.000             | 10.000           |
| 1d        | INTERNAL | PH  | 0_deneme      | 46 | YETERLI | 0.000             | 13.239           |
| 1d        | INTERNAL | PH  | 1_deneme      | 6  | ZAYIF   | 1.000             | 14.667           |
| 1d        | INTERNAL | PH  | 2-3_deneme    | 5  | ZAYIF   | 2.200             | 18.000           |
| 1d        | INTERNAL | PL  | 0_deneme      | 10 | ZAYIF   | 0.000             | 8.700            |
| 1d        | INTERNAL | PL  | 1_deneme      | 1  | ZAYIF   | 1.000             | 15.000           |
| 1d        | INTERNAL | PL  | 2-3_deneme    | 3  | ZAYIF   | 2.333             | 14.333           |
| 1h        | EXTERNAL | PH  | 0_deneme      | 21 | KISMI   | 0.000             | 12.381           |
| 1h        | EXTERNAL | PH  | 1_deneme      | 1  | ZAYIF   | 1.000             | 10.000           |
| 1h        | EXTERNAL | PL  | 0_deneme      | 3  | ZAYIF   | 0.000             | 18.333           |
| 1h        | EXTERNAL | PL  | 1_deneme      | 1  | ZAYIF   | 1.000             | 37.000           |
| 1h        | EXTERNAL | PL  | 2-3_deneme    | 1  | ZAYIF   | 2.000             | 24.000           |
| 1h        | INTERNAL | PH  | 0_deneme      | 45 | YETERLI | 0.000             | 11.289           |
| 1h        | INTERNAL | PH  | 1_deneme      | 3  | ZAYIF   | 1.000             | 13.000           |
| 1h        | INTERNAL | PH  | 2-3_deneme    | 4  | ZAYIF   | 2.500             | 15.750           |
| 1h        | INTERNAL | PH  | 4plus_deneme  | 1  | ZAYIF   | 4.000             | 6.000            |
| 1h        | INTERNAL | PL  | 0_deneme      | 4  | ZAYIF   | 0.000             | 15.000           |
| 1h        | INTERNAL | PL  | 1_deneme      | 1  | ZAYIF   | 1.000             | 3.000            |
| 1h        | INTERNAL | PL  | 2-3_deneme    | 2  | ZAYIF   | 2.500             | 16.500           |
| 2h        | EXTERNAL | PH  | 0_deneme      | 18 | KISMI   | 0.000             | 11.278           |
| 2h        | EXTERNAL | PH  | 1_deneme      | 1  | ZAYIF   | 1.000             | 7.000            |
| 2h        | EXTERNAL | PL  | 0_deneme      | 6  | ZAYIF   | 0.000             | 26.167           |
| 2h        | EXTERNAL | PL  | 1_deneme      | 1  | ZAYIF   | 1.000             | 3.000            |
| 2h        | EXTERNAL | PL  | 2-3_deneme    | 1  | ZAYIF   | 2.000             | 13.000           |
| 2h        | INTERNAL | PH  | 0_deneme      | 22 | KISMI   | 0.000             | 9.909            |
| 2h        | INTERNAL | PH  | 1_deneme      | 6  | ZAYIF   | 1.000             | 8.500            |
| 2h        | INTERNAL | PH  | 2-3_deneme    | 2  | ZAYIF   | 2.000             | 15.000           |
| 2h        | INTERNAL | PH  | 4plus_deneme  | 1  | ZAYIF   | 5.000             | 22.000           |
| 2h        | INTERNAL | PL  | 0_deneme      | 7  | ZAYIF   | 0.000             | 16.429           |
| 2h        | INTERNAL | PL  | 1_deneme      | 5  | ZAYIF   | 1.000             | 8.400            |
| 2h        | INTERNAL | PL  | 2-3_deneme    | 3  | ZAYIF   | 2.333             | 16.000           |
| 2h        | INTERNAL | PL  | 4plus_deneme  | 1  | ZAYIF   | 4.000             | 13.000           |
| 4h        | EXTERNAL | PH  | 0_deneme      | 14 | ZAYIF   | 0.000             | 6.786            |
| 4h        | EXTERNAL | PH  | 1_deneme      | 1  | ZAYIF   | 1.000             | 4.000            |
| 4h        | EXTERNAL | PL  | 0_deneme      | 19 | KISMI   | 0.000             | 21.474           |
| 4h        | EXTERNAL | PL  | 1_deneme      | 1  | ZAYIF   | 1.000             | 3.000            |
| 4h        | INTERNAL | PH  | 0_deneme      | 20 | KISMI   | 0.000             | 6.850            |
| 4h        | INTERNAL | PH  | 1_deneme      | 3  | ZAYIF   | 1.000             | 14.667           |
| 4h        | INTERNAL | PH  | 2-3_deneme    | 2  | ZAYIF   | 2.000             | 22.000           |
| 4h        | INTERNAL | PL  | 0_deneme      | 35 | YETERLI | 0.000             | 19.029           |
| 4h        | INTERNAL | PL  | 1_deneme      | 3  | ZAYIF   | 1.000             | 11.333           |

### Yaklaşma eşiği duyarlılığı (0.25 ana; 0.15 / 0.50 kontrol)

| esik     | timeframe | n_satir | guven   | engelledi_orani | kararsiz_adet |
|----------|-----------|---------|---------|-----------------|---------------|
| 0.25 ATR | 1d        | 1990    | YETERLI | %62.6           | 108           |
| 0.25 ATR | 1h        | 10748   | YETERLI | %66.2           | 87            |
| 0.25 ATR | 2h        | 5156    | YETERLI | %66.0           | 74            |
| 0.25 ATR | 4h        | 5505    | YETERLI | %64.2           | 98            |
| 0.15 ATR | 1d        | 1990    | YETERLI | %59.7           | 108           |
| 0.15 ATR | 1h        | 10748   | YETERLI | %63.9           | 87            |
| 0.15 ATR | 2h        | 5156    | YETERLI | %63.2           | 74            |
| 0.15 ATR | 4h        | 5505    | YETERLI | %61.2           | 98            |
| 0.5 ATR  | 1d        | 1990    | YETERLI | %71.1           | 108           |
| 0.5 ATR  | 1h        | 10748   | YETERLI | %74.0           | 87            |
| 0.5 ATR  | 2h        | 5156    | YETERLI | %74.4           | 74            |
| 0.5 ATR  | 4h        | 5505    | YETERLI | %72.0           | 98            |

## Soru 7 — WH/WL %kaçı ziyaret/süpürüldü, ne kadar sürede?
| timeframe | scope    | rol | n    | guven   | ziyaret_epizot | supuruldu | hic_ulasilmadi | sansur | ort_deneme_epizot |
|-----------|----------|-----|------|---------|----------------|-----------|----------------|--------|-------------------|
| 1d        | EXTERNAL | WH  | 425  | YETERLI | %66.6          | %59.3     | %40.7          | %4.5   | 1.233             |
| 1d        | EXTERNAL | WL  | 428  | YETERLI | %69.2          | %61.9     | %38.1          | %10.7  | 1.383             |
| 1d        | INTERNAL | WH  | 960  | YETERLI | %79.3          | %69.4     | %30.6          | %3.8   | 1.540             |
| 1d        | INTERNAL | WL  | 963  | YETERLI | %80.2          | %69.1     | %30.9          | %13.5  | 1.597             |
| 1h        | EXTERNAL | WH  | 3124 | YETERLI | %69.2          | %58.0     | %42.0          | %1.5   | 1.376             |
| 1h        | EXTERNAL | WL  | 2818 | YETERLI | %70.7          | %60.1     | %39.9          | %0.3   | 1.320             |
| 1h        | INTERNAL | WH  | 6537 | YETERLI | %76.5          | %63.4     | %36.6          | %1.0   | 1.588             |
| 1h        | INTERNAL | WL  | 5853 | YETERLI | %79.9          | %68.4     | %31.6          | %0.9   | 1.530             |
| 2h        | EXTERNAL | WH  | 1405 | YETERLI | %67.2          | %56.3     | %43.7          | %3.0   | 1.322             |
| 2h        | EXTERNAL | WL  | 1399 | YETERLI | %71.7          | %61.5     | %38.5          | %2.4   | 1.303             |
| 2h        | INTERNAL | WH  | 2806 | YETERLI | %75.2          | %62.5     | %37.5          | %3.3   | 1.574             |
| 2h        | INTERNAL | WL  | 2817 | YETERLI | %80.5          | %69.6     | %30.4          | %0.8   | 1.581             |
| 4h        | EXTERNAL | WH  | 1327 | YETERLI | %70.7          | %59.1     | %40.9          | %1.5   | 1.406             |
| 4h        | EXTERNAL | WL  | 1481 | YETERLI | %70.3          | %60.0     | %40.0          | %4.3   | 1.280             |
| 4h        | INTERNAL | WH  | 2965 | YETERLI | %77.7          | %66.5     | %33.5          | %2.6   | 1.654             |
| 4h        | INTERNAL | WL  | 2974 | YETERLI | %80.3          | %69.3     | %30.7          | %1.5   | 1.541             |

### Seviyeye ulaşma süresi (native bar; rol atamasından itibaren)

| timeframe | rol | n    | guven   | q25   | ortanca | q75   | ortalama |
|-----------|-----|------|---------|-------|---------|-------|----------|
| 1d        | WH  | 474  | YETERLI | 1.000 | 3.000   | 6.000 | 5.200    |
| 1d        | WL  | 462  | YETERLI | 1.000 | 3.000   | 5.000 | 4.400    |
| 1h        | WH  | 2828 | YETERLI | 1.000 | 3.000   | 6.000 | 6.600    |
| 1h        | WL  | 2824 | YETERLI | 2.000 | 3.000   | 7.000 | 5.800    |
| 2h        | WH  | 1258 | YETERLI | 1.000 | 3.000   | 6.000 | 5.200    |
| 2h        | WL  | 1383 | YETERLI | 2.000 | 3.000   | 7.000 | 5.600    |
| 4h        | WH  | 1360 | YETERLI | 1.000 | 3.000   | 6.000 | 4.900    |
| 4h        | WL  | 1483 | YETERLI | 1.000 | 3.000   | 6.000 | 5.400    |

### EVENT_SWEEP çapraz kontrolü
| timeframe | scope    | direction | n    | guven   | uyumlu | CALISTI | ort_devam_h12 |
|-----------|----------|-----------|------|---------|--------|---------|---------------|
| 1d        | EXTERNAL | DOWN      | 469  | YETERLI | %95.5  | %64.6   | 1.848         |
| 1d        | EXTERNAL | UP        | 417  | YETERLI | %97.4  | %67.6   | 2.115         |
| 1d        | INTERNAL | DOWN      | 978  | YETERLI | %96.6  | %66.8   | 1.973         |
| 1d        | INTERNAL | UP        | 659  | YETERLI | %96.8  | %65.6   | 2.095         |
| 1h        | EXTERNAL | DOWN      | 3092 | YETERLI | %97.6  | %62.8   | 1.730         |
| 1h        | EXTERNAL | UP        | 2483 | YETERLI | %96.2  | %63.0   | 2.141         |
| 1h        | INTERNAL | DOWN      | 4875 | YETERLI | %97.1  | %64.1   | 1.812         |
| 1h        | INTERNAL | UP        | 4038 | YETERLI | %96.8  | %63.1   | 2.073         |
| 2h        | EXTERNAL | DOWN      | 1499 | YETERLI | %97.4  | %64.0   | 1.813         |
| 2h        | EXTERNAL | UP        | 1120 | YETERLI | %96.0  | %62.3   | 1.906         |
| 2h        | INTERNAL | DOWN      | 2281 | YETERLI | %97.4  | %65.8   | 1.874         |
| 2h        | INTERNAL | UP        | 1688 | YETERLI | %96.7  | %65.5   | 2.027         |
| 4h        | EXTERNAL | DOWN      | 1613 | YETERLI | %97.8  | %66.0   | 1.928         |
| 4h        | EXTERNAL | UP        | 1220 | YETERLI | %97.9  | %65.0   | 2.145         |
| 4h        | INTERNAL | DOWN      | 2472 | YETERLI | %97.3  | %63.8   | 1.878         |
| 4h        | INTERNAL | UP        | 1818 | YETERLI | %97.5  | %64.5   | 2.047         |

## Hacim — koşullandırma değişkeni
### Dokunuş tepkisi x hacim çeyreği (rvol)

| timeframe | hacim_kovasi | n    | guven   | tepki_CALISTI | ort_yon_h12 | ort_pay_5 | ort_h12_decay | ort_rvol |
|-----------|--------------|------|---------|---------------|-------------|-----------|---------------|----------|
| 1d        | KULLANILAMAZ | 1640 | YETERLI | %65.1         | 2.002       | 0.514     | 2.239         | -        |
| 1d        | Q1_dusuk     | 938  | YETERLI | %61.3         | 1.886       | 0.623     | 1.987         | 0.519    |
| 1d        | Q2           | 1648 | YETERLI | %68.3         | 2.097       | 0.639     | 1.852         | 0.909    |
| 1d        | Q3           | 1203 | YETERLI | %64.6         | 1.923       | 0.596     | 2.831         | 1.414    |
| 1d        | Q4_yuksek    | 810  | YETERLI | %55.3         | 1.533       | 0.519     | 2.634         | 2.975    |
| 1h        | KULLANILAMAZ | 885  | YETERLI | %65.1         | 2.056       | 0.610     | 2.238         | -        |
| 1h        | Q1_dusuk     | 8425 | YETERLI | %67.6         | 2.001       | 0.570     | 1.722         | 0.143    |
| 1h        | Q2           | 4082 | YETERLI | %71.7         | 2.227       | 0.695     | 1.526         | 0.918    |
| 1h        | Q3           | 4882 | YETERLI | %68.2         | 2.146       | 0.647     | 1.769         | 1.452    |
| 1h        | Q4_yuksek    | 6449 | YETERLI | %61.5         | 1.849       | 0.579     | 1.778         | 3.468    |
| 2h        | KULLANILAMAZ | 1232 | YETERLI | %67.4         | 1.983       | 0.566     | 1.796         | -        |
| 2h        | Q1_dusuk     | 2979 | YETERLI | %68.8         | 2.104       | 0.718     | 1.907         | 0.508    |
| 2h        | Q2           | 4870 | YETERLI | %68.7         | 2.084       | 0.658     | 1.667         | 0.909    |
| 2h        | Q3           | 4090 | YETERLI | %65.0         | 1.923       | 0.613     | 1.775         | 1.430    |
| 2h        | Q4_yuksek    | 3605 | YETERLI | %59.8         | 1.721       | 0.556     | 1.907         | 3.203    |
| 4h        | KULLANILAMAZ | 1167 | YETERLI | %63.9         | 1.856       | 0.559     | 1.612         | -        |
| 4h        | Q1_dusuk     | 2876 | YETERLI | %68.0         | 2.112       | 0.662     | 2.177         | 0.491    |
| 4h        | Q2           | 4617 | YETERLI | %68.6         | 2.102       | 0.625     | 12.882        | 0.921    |
| 4h        | Q3           | 5042 | YETERLI | %66.2         | 1.994       | 0.625     | 1.943         | 1.437    |
| 4h        | Q4_yuksek    | 4354 | YETERLI | %58.7         | 1.739       | 0.518     | 2.058         | 3.043    |

### MS event devamlılığı x hacim çeyreği

| timeframe | hacim_kovasi | n    | guven   | CALISTI | uyumlu | ort_devam_h12 |
|-----------|--------------|------|---------|---------|--------|---------------|
| 1d        | KULLANILAMAZ | 1317 | YETERLI | %66.8   | %96.1  | 2.034         |
| 1d        | Q1_dusuk     | 599  | YETERLI | %62.9   | %96.3  | 1.863         |
| 1d        | Q2           | 1191 | YETERLI | %69.5   | %97.4  | 2.111         |
| 1d        | Q3           | 888  | YETERLI | %61.3   | %95.8  | 2.037         |
| 1d        | Q4_yuksek    | 610  | YETERLI | %70.3   | %95.6  | 2.499         |
| 1h        | KULLANILAMAZ | 1030 | YETERLI | %63.2   | %93.2  | 2.137         |
| 1h        | Q1_dusuk     | 7742 | YETERLI | %63.8   | %97.4  | 1.966         |
| 1h        | Q2           | 4975 | YETERLI | %66.1   | %96.9  | 2.056         |
| 1h        | Q3           | 5451 | YETERLI | %64.1   | %96.3  | 2.018         |
| 1h        | Q4_yuksek    | 6545 | YETERLI | %66.8   | %97.6  | 2.180         |
| 2h        | KULLANILAMAZ | 1223 | YETERLI | %66.1   | %95.7  | 1.985         |
| 2h        | Q1_dusuk     | 2019 | YETERLI | %64.9   | %96.7  | 1.971         |
| 2h        | Q2           | 3311 | YETERLI | %65.8   | %97.3  | 1.990         |
| 2h        | Q3           | 2916 | YETERLI | %66.2   | %97.7  | 2.032         |
| 2h        | Q4_yuksek    | 2524 | YETERLI | %67.7   | %96.8  | 2.215         |
| 4h        | KULLANILAMAZ | 1192 | YETERLI | %62.7   | %95.6  | 1.962         |
| 4h        | Q1_dusuk     | 2266 | YETERLI | %64.2   | %95.5  | 2.009         |
| 4h        | Q2           | 3150 | YETERLI | %66.0   | %97.5  | 2.059         |
| 4h        | Q3           | 3370 | YETERLI | %65.8   | %98.6  | 2.073         |
| 4h        | Q4_yuksek    | 2946 | YETERLI | %71.0   | %98.5  | 2.382         |
