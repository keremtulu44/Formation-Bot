# Formation-Bot Arşiv Araştırma Raporu
> Bu dosya tablo ekidir: ham aggregatlar soru başına bölümlenir.
> Okunabilir özet ve yorum: `docs/arastirma/ARASTIRMA_SONUCLARI.md`.
> Yalnız karar için okuyan, aşağıdaki tablolara inmeden özetle yetinebilir.

## ÖZET — ilk bakışta (176 sembol × 4 TF, 994.142 gözlem)
- **OB yeniden test edilir** (%12,9'u 3+ kez, en çok 20 epizot); **FVG tek kullanımlık** (3+ deneme 55.145'te 4; %23'ü hiç dokunulmamış).
- **OB %85–94 sonunda geçilir**, ama dokunuşların %65–67'si ≥1 ATR tepki verir → zone bir *zamanlama* aracı, bariyer değil. FVG tam dolum %40–43.
- **Destek tepkisi dirençten büyük** (1d: 2,187'ye 1,660 ATR). Eşik eğrisi düz: ≥0,25 ATR %74–77, ≥1 ATR %58–61, ≥2 ATR %38–40.
- **Zone boyu ayırt edici ve monoton**: uzun zone erken tepki verip tutuyor (CALISTI %64,3→%71,0), kısa zone geç tepki verip geri veriyor.
- **MS yön uyumu %97–98**; BOS sonrası devam ~%70; UP BOS, DOWN BOS'tan ~8 puan iyi; INTERNAL biraz zayıf ama daha sık.
- **PH teste dayanmaz** (%36,0 → 4+ testte %8,0); **PL tutar** (%37,5 → %33,3).
- **WH/WL medyan 3 native bar**'da süpürülür; WL ~3–5 puan daha çok; INTERNAL > EXTERNAL.
- **Hacim sezgiye ters**: dokunuşta yüksek RVOL → daha ZAYIF tepki (4h Q1 %70,1 → Q4 %61,0). Hacim burada teyit değil ihlal sinyali.
- **MS %5,0 seride çöküyor** (35/704) — canlı bot bu serilerde MS alanını sessizce boş bırakıyor (liste: `docs/arastirma/arastirma_ms_hatali_seriler.txt`).

Kaynak: `backfill_data/` (365 gün derin çekim) · Sembol: 176 · Havuz dışı: BRENT

## Kapsam
| timeframe | sembol | ort_bar | toplam_zone | toplam_epizot | toplam_swing | toplam_event | toplam_rol_araligi | ms_hatali_seri |
|-----------|--------|---------|-------------|---------------|--------------|--------------|--------------------|----------------|
| 1d        | 176    | 499     | 22190       | 24846         | 31875        | 17074        | 23058              | 5              |
| 1h        | 176    | 3211    | 59130       | 90485         | 177472       | 81853        | 125955             | 20             |
| 2h        | 176    | 1790    | 64216       | 76267         | 106108       | 52027        | 75822              | 6              |
| 4h        | 176    | 1073    | 41510       | 48886         | 66940        | 33263        | 48748              | 4              |

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
| 1d        | EXTERNAL | EVENT_BOS             | 1777  | YETERLI | %96.7  | %68.9   | %21.2    | %7.1      | %2.0 | %2.8   | 2.284         | 2.083        |
| 1d        | EXTERNAL | EVENT_CHOCH           | 694   | YETERLI | %95.2  | %66.3   | %22.2    | %8.1      | %3.2 | %0.9   | 2.093         | 2.029        |
| 1d        | EXTERNAL | EVENT_FALSE_BREAK     | 148   | YETERLI | %96.6  | %69.6   | %20.9    | %6.8      | %2.7 | %2.0   | 2.125         | 2.049        |
| 1d        | EXTERNAL | EVENT_SWEEP           | 3460  | YETERLI | %95.8  | %66.3   | %23.0    | %7.3      | %3.3 | %0.8   | 1.994         | 2.132        |
| 1d        | EXTERNAL | EVENT_TRANSITION_FAIL | 201   | YETERLI | %99.5  | %67.7   | %26.4    | %5.5      | %0.5 | %1.0   | 2.258         | 2.199        |
| 1d        | INTERNAL | EVENT_BOS             | 3236  | YETERLI | %94.7  | %68.0   | %22.0    | %5.5      | %2.5 | %3.5   | 2.300         | 1.942        |
| 1d        | INTERNAL | EVENT_CHOCH           | 1253  | YETERLI | %95.3  | %64.8   | %23.1    | %8.9      | %2.9 | %0.7   | 2.026         | 2.160        |
| 1d        | INTERNAL | EVENT_FALSE_BREAK     | 229   | YETERLI | %95.2  | %65.1   | %25.3    | %6.1      | %2.2 | %3.1   | 1.973         | 2.172        |
| 1d        | INTERNAL | EVENT_SWEEP           | 5686  | YETERLI | %95.8  | %65.0   | %24.8    | %6.9      | %2.7 | %1.3   | 2.015         | 2.058        |
| 1d        | INTERNAL | EVENT_TRANSITION_FAIL | 390   | YETERLI | %97.2  | %66.4   | %25.6    | %5.6      | %2.1 | %1.3   | 2.145         | 2.183        |
| 1h        | EXTERNAL | EVENT_BOS             | 8430  | YETERLI | %97.0  | %67.3   | %23.0    | %8.8      | %0.9 | %0.3   | 2.284         | 1.965        |
| 1h        | EXTERNAL | EVENT_CHOCH           | 3185  | YETERLI | %97.2  | %68.4   | %22.7    | %7.8      | %1.1 | %0.2   | 2.294         | 1.835        |
| 1h        | EXTERNAL | EVENT_FALSE_BREAK     | 598   | YETERLI | %96.0  | %60.4   | %27.1    | %10.0     | %2.5 | %0.0   | 1.901         | 2.264        |
| 1h        | EXTERNAL | EVENT_SWEEP           | 17076 | YETERLI | %96.8  | %62.4   | %26.3    | %10.1     | %1.2 | %0.2   | 1.873         | 2.122        |
| 1h        | EXTERNAL | EVENT_TRANSITION_FAIL | 830   | YETERLI | %97.6  | %69.2   | %21.8    | %8.1      | %1.0 | %0.1   | 2.442         | 1.878        |
| 1h        | INTERNAL | EVENT_BOS             | 15837 | YETERLI | %97.0  | %67.2   | %23.0    | %8.6      | %1.0 | %0.4   | 2.273         | 1.943        |
| 1h        | INTERNAL | EVENT_CHOCH           | 5812  | YETERLI | %97.2  | %66.5   | %23.6    | %8.9      | %1.0 | %0.1   | 2.177         | 1.935        |
| 1h        | INTERNAL | EVENT_FALSE_BREAK     | 1078  | YETERLI | %96.4  | %63.1   | %25.0    | %10.9     | %0.7 | %0.1   | 1.952         | 2.054        |
| 1h        | INTERNAL | EVENT_SWEEP           | 27374 | YETERLI | %96.9  | %62.8   | %26.2    | %9.7      | %1.1 | %0.3   | 1.919         | 2.108        |
| 1h        | INTERNAL | EVENT_TRANSITION_FAIL | 1633  | YETERLI | %97.7  | %68.4   | %22.5    | %8.2      | %0.9 | %0.2   | 2.282         | 1.931        |
| 2h        | EXTERNAL | EVENT_BOS             | 5225  | YETERLI | %97.6  | %67.0   | %23.8    | %8.2      | %1.0 | %1.2   | 2.318         | 2.005        |
| 2h        | EXTERNAL | EVENT_CHOCH           | 2071  | YETERLI | %97.9  | %68.5   | %22.7    | %8.0      | %0.8 | %0.2   | 2.373         | 1.966        |
| 2h        | EXTERNAL | EVENT_FALSE_BREAK     | 408   | YETERLI | %94.9  | %68.9   | %20.1    | %8.6      | %2.5 | %0.7   | 2.215         | 2.100        |
| 2h        | EXTERNAL | EVENT_SWEEP           | 11258 | YETERLI | %97.1  | %63.9   | %25.4    | %9.4      | %1.2 | %0.9   | 1.958         | 2.113        |
| 2h        | EXTERNAL | EVENT_TRANSITION_FAIL | 585   | YETERLI | %98.6  | %69.9   | %24.8    | %4.8      | %0.5 | %1.7   | 2.451         | 1.976        |
| 2h        | INTERNAL | EVENT_BOS             | 9983  | YETERLI | %97.2  | %67.2   | %22.8    | %8.8      | %0.7 | %0.9   | 2.271         | 1.991        |
| 2h        | INTERNAL | EVENT_CHOCH           | 3714  | YETERLI | %97.7  | %69.2   | %22.1    | %7.7      | %0.9 | %0.4   | 2.283         | 1.887        |
| 2h        | INTERNAL | EVENT_FALSE_BREAK     | 671   | YETERLI | %95.1  | %64.8   | %22.8    | %10.4     | %1.8 | %0.6   | 2.093         | 2.061        |
| 2h        | INTERNAL | EVENT_SWEEP           | 17091 | YETERLI | %97.3  | %63.5   | %25.6    | %9.6      | %1.1 | %0.7   | 1.903         | 2.153        |
| 2h        | INTERNAL | EVENT_TRANSITION_FAIL | 1021  | YETERLI | %97.7  | %69.6   | %23.5    | %5.9      | %0.8 | %1.8   | 2.437         | 1.995        |
| 4h        | EXTERNAL | EVENT_BOS             | 3387  | YETERLI | %98.0  | %71.0   | %20.5    | %7.5      | %0.9 | %2.9   | 2.500         | 1.992        |
| 4h        | EXTERNAL | EVENT_CHOCH           | 1300  | YETERLI | %97.9  | %70.8   | %20.0    | %8.2      | %0.8 | %0.4   | 2.403         | 2.100        |
| 4h        | EXTERNAL | EVENT_FALSE_BREAK     | 262   | YETERLI | %97.7  | %66.0   | %24.8    | %8.0      | %1.1 | %0.8   | 2.077         | 2.274        |
| 4h        | EXTERNAL | EVENT_SWEEP           | 6931  | YETERLI | %97.2  | %66.0   | %23.1    | %9.2      | %1.7 | %1.8   | 2.075         | 2.225        |
| 4h        | EXTERNAL | EVENT_TRANSITION_FAIL | 359   | YETERLI | %98.1  | %71.3   | %19.2    | %8.6      | %0.6 | %1.1   | 2.714         | 2.016        |
| 4h        | INTERNAL | EVENT_BOS             | 6505  | YETERLI | %97.0  | %68.2   | %20.9    | %9.2      | %1.0 | %1.7   | 2.408         | 2.084        |
| 4h        | INTERNAL | EVENT_CHOCH           | 2455  | YETERLI | %97.9  | %70.0   | %21.7    | %7.5      | %0.8 | %0.6   | 2.407         | 2.028        |
| 4h        | INTERNAL | EVENT_FALSE_BREAK     | 541   | YETERLI | %97.8  | %67.5   | %22.6    | %8.7      | %1.1 | %0.4   | 2.171         | 2.170        |
| 4h        | INTERNAL | EVENT_SWEEP           | 10827 | YETERLI | %97.4  | %64.3   | %24.3    | %9.9      | %1.3 | %1.4   | 1.977         | 2.280        |
| 4h        | INTERNAL | EVENT_TRANSITION_FAIL | 696   | YETERLI | %97.6  | %71.8   | %20.3    | %7.2      | %0.6 | %3.2   | 2.547         | 1.926        |

### Scope x yön (BOS/CHOCH ayrımıyla)

| timeframe | scope    | event_type  | direction | n    | guven   | uyumlu | CALISTI | AZ_DEVAM | DEVAM_YOK | TERS | sansur | ort_devam_h12 | ort_ters_h12 |
|-----------|----------|-------------|-----------|------|---------|--------|---------|----------|-----------|------|--------|---------------|--------------|
| 1d        | EXTERNAL | EVENT_BOS   | DOWN      | 904  | YETERLI | %95.2  | %60.6   | %26.8    | %8.3      | %2.8 | %5.4   | 1.759         | 2.077        |
| 1d        | EXTERNAL | EVENT_BOS   | UP        | 873  | YETERLI | %98.2  | %77.5   | %15.3    | %5.8      | %1.3 | %0.1   | 2.820         | 2.089        |
| 1d        | EXTERNAL | EVENT_CHOCH | DOWN      | 386  | YETERLI | %93.8  | %61.1   | %24.6    | %9.8      | %3.9 | %1.0   | 1.629         | 1.841        |
| 1d        | EXTERNAL | EVENT_CHOCH | UP        | 308  | YETERLI | %97.1  | %72.7   | %19.2    | %5.8      | %2.3 | %0.6   | 2.672         | 2.263        |
| 1d        | INTERNAL | EVENT_BOS   | DOWN      | 1667 | YETERLI | %93.3  | %60.4   | %27.3    | %6.5      | %3.0 | %6.4   | 1.756         | 1.985        |
| 1d        | INTERNAL | EVENT_BOS   | UP        | 1569 | YETERLI | %96.3  | %76.1   | %16.3    | %4.3      | %1.9 | %0.3   | 2.871         | 1.898        |
| 1d        | INTERNAL | EVENT_CHOCH | DOWN      | 638  | YETERLI | %93.6  | %57.5   | %25.9    | %12.9     | %3.3 | %1.1   | 1.503         | 2.038        |
| 1d        | INTERNAL | EVENT_CHOCH | UP        | 615  | YETERLI | %97.1  | %72.4   | %20.3    | %4.9      | %2.4 | %0.3   | 2.566         | 2.286        |
| 1h        | EXTERNAL | EVENT_BOS   | DOWN      | 4176 | YETERLI | %97.0  | %67.0   | %23.3    | %8.4      | %1.1 | %0.6   | 2.128         | 2.078        |
| 1h        | EXTERNAL | EVENT_BOS   | UP        | 4254 | YETERLI | %97.0  | %67.6   | %22.6    | %9.1      | %0.7 | %0.0   | 2.436         | 1.854        |
| 1h        | EXTERNAL | EVENT_CHOCH | DOWN      | 1648 | YETERLI | %97.7  | %67.2   | %24.6    | %7.0      | %1.1 | %0.3   | 2.123         | 1.836        |
| 1h        | EXTERNAL | EVENT_CHOCH | UP        | 1537 | YETERLI | %96.7  | %69.7   | %20.6    | %8.7      | %1.0 | %0.0   | 2.477         | 1.834        |
| 1h        | INTERNAL | EVENT_BOS   | DOWN      | 8061 | YETERLI | %97.2  | %67.1   | %23.8    | %7.7      | %1.2 | %0.8   | 2.124         | 1.997        |
| 1h        | INTERNAL | EVENT_BOS   | UP        | 7776 | YETERLI | %96.7  | %67.2   | %22.1    | %9.5      | %0.9 | %0.0   | 2.428         | 1.887        |
| 1h        | INTERNAL | EVENT_CHOCH | DOWN      | 2922 | YETERLI | %97.8  | %64.6   | %26.1    | %8.0      | %1.2 | %0.0   | 1.965         | 2.032        |
| 1h        | INTERNAL | EVENT_CHOCH | UP        | 2890 | YETERLI | %96.6  | %68.4   | %21.0    | %9.8      | %0.8 | %0.1   | 2.391         | 1.836        |
| 2h        | EXTERNAL | EVENT_BOS   | DOWN      | 2610 | YETERLI | %97.7  | %64.4   | %25.9    | %8.8      | %0.9 | %2.4   | 2.054         | 2.108        |
| 2h        | EXTERNAL | EVENT_BOS   | UP        | 2615 | YETERLI | %97.5  | %69.6   | %21.8    | %7.5      | %1.0 | %0.1   | 2.582         | 1.902        |
| 2h        | EXTERNAL | EVENT_CHOCH | DOWN      | 1062 | YETERLI | %97.8  | %64.7   | %25.2    | %9.3      | %0.8 | %0.4   | 2.001         | 2.014        |
| 2h        | EXTERNAL | EVENT_CHOCH | UP        | 1009 | YETERLI | %98.0  | %72.5   | %20.1    | %6.5      | %0.8 | %0.0   | 2.764         | 1.917        |
| 2h        | INTERNAL | EVENT_BOS   | DOWN      | 5073 | YETERLI | %97.6  | %65.1   | %24.8    | %9.2      | %0.6 | %1.7   | 2.024         | 2.105        |
| 2h        | INTERNAL | EVENT_BOS   | UP        | 4910 | YETERLI | %96.9  | %69.4   | %20.8    | %8.3      | %0.9 | %0.1   | 2.527         | 1.872        |
| 2h        | INTERNAL | EVENT_CHOCH | DOWN      | 1889 | YETERLI | %97.6  | %66.5   | %23.7    | %8.6      | %1.1 | %0.7   | 1.958         | 1.921        |
| 2h        | INTERNAL | EVENT_CHOCH | UP        | 1825 | YETERLI | %97.9  | %72.1   | %20.5    | %6.7      | %0.7 | %0.1   | 2.620         | 1.853        |
| 4h        | EXTERNAL | EVENT_BOS   | DOWN      | 1736 | YETERLI | %97.8  | %67.3   | %23.2    | %8.4      | %1.1 | %5.6   | 2.189         | 2.067        |
| 4h        | EXTERNAL | EVENT_BOS   | UP        | 1651 | YETERLI | %98.2  | %75.0   | %17.7    | %6.6      | %0.7 | %0.0   | 2.827         | 1.914        |
| 4h        | EXTERNAL | EVENT_CHOCH | DOWN      | 650  | YETERLI | %97.7  | %70.9   | %19.2    | %9.2      | %0.5 | %0.6   | 2.126         | 1.957        |
| 4h        | EXTERNAL | EVENT_CHOCH | UP        | 650  | YETERLI | %98.2  | %70.8   | %20.8    | %7.2      | %1.2 | %0.2   | 2.680         | 2.242        |
| 4h        | INTERNAL | EVENT_BOS   | DOWN      | 3393 | YETERLI | %97.0  | %64.6   | %23.2    | %10.6     | %1.2 | %3.1   | 2.069         | 2.148        |
| 4h        | INTERNAL | EVENT_BOS   | UP        | 3112 | YETERLI | %97.0  | %72.2   | %18.3    | %7.6      | %0.9 | %0.1   | 2.779         | 2.015        |
| 4h        | INTERNAL | EVENT_CHOCH | DOWN      | 1235 | YETERLI | %97.8  | %67.9   | %22.8    | %8.6      | %0.8 | %1.0   | 2.077         | 2.019        |
| 4h        | INTERNAL | EVENT_CHOCH | UP        | 1220 | YETERLI | %98.0  | %72.2   | %20.6    | %6.5      | %0.7 | %0.2   | 2.741         | 2.037        |

### Motorun kendi outcome kararı (çapraz kontrol)

| timeframe | scope    | outcome                  | n     | guven   | adet   |
|-----------|----------|--------------------------|-------|---------|--------|
| 1d        | EXTERNAL | FAILED                   | 349   | YETERLI | %100.0 |
| 1d        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 455   | YETERLI | %100.0 |
| 1d        | EXTERNAL | OBSERVED                 | 5438  | YETERLI | %100.0 |
| 1d        | EXTERNAL | PENDING                  | 38    | YETERLI | %100.0 |
| 1d        | INTERNAL | FAILED                   | 619   | YETERLI | %100.0 |
| 1d        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 833   | YETERLI | %100.0 |
| 1d        | INTERNAL | OBSERVED                 | 9312  | YETERLI | %100.0 |
| 1d        | INTERNAL | PENDING                  | 30    | YETERLI | %100.0 |
| 1h        | EXTERNAL | FAILED                   | 1428  | YETERLI | %100.0 |
| 1h        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 2317  | YETERLI | %100.0 |
| 1h        | EXTERNAL | OBSERVED                 | 26336 | YETERLI | %100.0 |
| 1h        | EXTERNAL | PENDING                  | 38    | YETERLI | %100.0 |
| 1h        | INTERNAL | FAILED                   | 2711  | YETERLI | %100.0 |
| 1h        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 4155  | YETERLI | %100.0 |
| 1h        | INTERNAL | OBSERVED                 | 44844 | YETERLI | %100.0 |
| 1h        | INTERNAL | PENDING                  | 24    | KISMI   | %100.0 |
| 2h        | EXTERNAL | FAILED                   | 993   | YETERLI | %100.0 |
| 2h        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 1463  | YETERLI | %100.0 |
| 2h        | EXTERNAL | OBSERVED                 | 17068 | YETERLI | %100.0 |
| 2h        | EXTERNAL | PENDING                  | 23    | KISMI   | %100.0 |
| 2h        | INTERNAL | FAILED                   | 1692  | YETERLI | %100.0 |
| 2h        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 2664  | YETERLI | %100.0 |
| 2h        | INTERNAL | OBSERVED                 | 28095 | YETERLI | %100.0 |
| 2h        | INTERNAL | PENDING                  | 29    | KISMI   | %100.0 |
| 4h        | EXTERNAL | FAILED                   | 621   | YETERLI | %100.0 |
| 4h        | EXTERNAL | FOLLOW_THROUGH_CONFIRMED | 912   | YETERLI | %100.0 |
| 4h        | EXTERNAL | OBSERVED                 | 10677 | YETERLI | %100.0 |
| 4h        | EXTERNAL | PENDING                  | 29    | KISMI   | %100.0 |
| 4h        | INTERNAL | FAILED                   | 1237  | YETERLI | %100.0 |
| 4h        | INTERNAL | FOLLOW_THROUGH_CONFIRMED | 1726  | YETERLI | %100.0 |
| 4h        | INTERNAL | OBSERVED                 | 18028 | YETERLI | %100.0 |
| 4h        | INTERNAL | PENDING                  | 33    | YETERLI | %100.0 |

## Soru 6 — PH/PL direnç/destek mi, çok denenen mi az denenen mi?
### Kararı verilebilir satırlar (sansürsüz)

| timeframe | scope    | rol | deneme_kovasi | n    | guven   | engelledi | engellemedi | ort_deneme_epizot | ort_deneme_bar | ort_rol_sure_bar | ort_bars_to_break |
|-----------|----------|-----|---------------|------|---------|-----------|-------------|-------------------|----------------|------------------|-------------------|
| 1d        | EXTERNAL | PH  | 0_deneme      | 664  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 35.706           | 67.030            |
| 1d        | EXTERNAL | PH  | 1_deneme      | 292  | YETERLI | %36.0     | %64.0       | 1.000             | 11.743         | 24.637           | 22.168            |
| 1d        | EXTERNAL | PH  | 2-3_deneme    | 195  | YETERLI | %22.6     | %77.4       | 2.328             | 16.015         | 19.385           | 18.896            |
| 1d        | EXTERNAL | PH  | 4plus_deneme  | 25   | KISMI   | %8.0      | %92.0       | 4.240             | 16.800         | 20.120           | 19.913            |
| 1d        | EXTERNAL | PL  | 0_deneme      | 704  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 39.670           | 70.090            |
| 1d        | EXTERNAL | PL  | 1_deneme      | 309  | YETERLI | %37.5     | %62.5       | 1.000             | 14.906         | 22.618           | 21.182            |
| 1d        | EXTERNAL | PL  | 2-3_deneme    | 225  | YETERLI | %28.9     | %71.1       | 2.324             | 15.227         | 22.009           | 22.163            |
| 1d        | EXTERNAL | PL  | 4plus_deneme  | 30   | YETERLI | %33.3     | %66.7       | 4.300             | 15.833         | 21.733           | 22.167            |
| 1d        | INTERNAL | PH  | 0_deneme      | 882  | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 20.217           | 58.345            |
| 1d        | INTERNAL | PH  | 1_deneme      | 643  | YETERLI | %34.1     | %65.9       | 1.000             | 13.726         | 14.773           | 13.396            |
| 1d        | INTERNAL | PH  | 2-3_deneme    | 533  | YETERLI | %21.0     | %79.0       | 2.310             | 16.964         | 14.782           | 14.591            |
| 1d        | INTERNAL | PH  | 4plus_deneme  | 96   | YETERLI | %19.8     | %80.2       | 4.292             | 18.135         | 14.354           | 13.956            |
| 1d        | INTERNAL | PL  | 0_deneme      | 1000 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 20.556           | 59.741            |
| 1d        | INTERNAL | PL  | 1_deneme      | 637  | YETERLI | %37.7     | %62.3       | 1.000             | 15.777         | 15.771           | 14.556            |
| 1d        | INTERNAL | PL  | 2-3_deneme    | 587  | YETERLI | %30.0     | %70.0       | 2.344             | 16.242         | 15.828           | 16.347            |
| 1d        | INTERNAL | PL  | 4plus_deneme  | 98   | YETERLI | %26.5     | %73.5       | 4.378             | 16.694         | 16.051           | 16.676            |
| 1h        | EXTERNAL | PH  | 0_deneme      | 3724 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 46.807           | 79.363            |
| 1h        | EXTERNAL | PH  | 1_deneme      | 1292 | YETERLI | %34.2     | %65.8       | 1.000             | 13.403         | 30.562           | 24.848            |
| 1h        | EXTERNAL | PH  | 2-3_deneme    | 889  | YETERLI | %22.9     | %77.1       | 2.342             | 14.721         | 25.543           | 24.240            |
| 1h        | EXTERNAL | PH  | 4plus_deneme  | 172  | YETERLI | %22.7     | %77.3       | 4.430             | 16.006         | 25.948           | 25.522            |
| 1h        | EXTERNAL | PL  | 0_deneme      | 3937 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 46.432           | 89.234            |
| 1h        | EXTERNAL | PL  | 1_deneme      | 1366 | YETERLI | %35.1     | %64.9       | 1.000             | 13.417         | 29.850           | 24.707            |
| 1h        | EXTERNAL | PL  | 2-3_deneme    | 801  | YETERLI | %30.5     | %69.5       | 2.293             | 14.251         | 25.471           | 25.437            |
| 1h        | EXTERNAL | PL  | 4plus_deneme  | 115  | YETERLI | %28.7     | %71.3       | 4.400             | 16.583         | 25.226           | 24.793            |
| 1h        | INTERNAL | PH  | 0_deneme      | 5344 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 24.927           | 72.796            |
| 1h        | INTERNAL | PH  | 1_deneme      | 3030 | YETERLI | %34.3     | %65.7       | 1.000             | 15.257         | 16.582           | 14.709            |
| 1h        | INTERNAL | PH  | 2-3_deneme    | 2595 | YETERLI | %24.1     | %75.9       | 2.334             | 16.104         | 17.227           | 16.929            |
| 1h        | INTERNAL | PH  | 4plus_deneme  | 570  | YETERLI | %15.3     | %84.7       | 4.442             | 17.604         | 17.030           | 16.962            |
| 1h        | INTERNAL | PL  | 0_deneme      | 5623 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 24.405           | 97.729            |
| 1h        | INTERNAL | PL  | 1_deneme      | 3112 | YETERLI | %33.4     | %66.6       | 1.000             | 15.254         | 21.372           | 18.110            |
| 1h        | INTERNAL | PL  | 2-3_deneme    | 2305 | YETERLI | %27.2     | %72.8       | 2.309             | 16.703         | 18.214           | 17.945            |
| 1h        | INTERNAL | PL  | 4plus_deneme  | 396  | YETERLI | %29.0     | %71.0       | 4.402             | 17.366         | 18.157           | 17.893            |
| 2h        | EXTERNAL | PH  | 0_deneme      | 2290 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 43.072           | 72.655            |
| 2h        | EXTERNAL | PH  | 1_deneme      | 758  | YETERLI | %32.1     | %67.9       | 1.000             | 13.991         | 26.047           | 22.800            |
| 2h        | EXTERNAL | PH  | 2-3_deneme    | 618  | YETERLI | %23.8     | %76.2       | 2.346             | 14.476         | 25.359           | 24.109            |
| 2h        | EXTERNAL | PH  | 4plus_deneme  | 141  | YETERLI | %14.2     | %85.8       | 4.426             | 16.121         | 23.844           | 19.762            |
| 2h        | EXTERNAL | PL  | 0_deneme      | 2502 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 44.203           | 79.673            |
| 2h        | EXTERNAL | PL  | 1_deneme      | 799  | YETERLI | %35.4     | %64.6       | 1.000             | 13.343         | 31.708           | 25.201            |
| 2h        | EXTERNAL | PL  | 2-3_deneme    | 537  | YETERLI | %30.2     | %69.8       | 2.287             | 14.480         | 26.892           | 24.951            |
| 2h        | EXTERNAL | PL  | 4plus_deneme  | 76   | YETERLI | %35.5     | %64.5       | 4.263             | 15.632         | 25.250           | 24.419            |
| 2h        | INTERNAL | PH  | 0_deneme      | 3265 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 23.916           | 63.482            |
| 2h        | INTERNAL | PH  | 1_deneme      | 1874 | YETERLI | %34.0     | %66.0       | 1.000             | 15.710         | 18.048           | 15.648            |
| 2h        | INTERNAL | PH  | 2-3_deneme    | 1738 | YETERLI | %23.1     | %76.9       | 2.356             | 16.533         | 16.203           | 16.231            |
| 2h        | INTERNAL | PH  | 4plus_deneme  | 398  | YETERLI | %17.8     | %82.2       | 4.503             | 17.704         | 17.470           | 16.743            |
| 2h        | INTERNAL | PL  | 0_deneme      | 3519 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 21.962           | 64.790            |
| 2h        | INTERNAL | PL  | 1_deneme      | 1942 | YETERLI | %35.4     | %64.6       | 1.000             | 15.654         | 19.795           | 16.996            |
| 2h        | INTERNAL | PL  | 2-3_deneme    | 1500 | YETERLI | %26.7     | %73.3       | 2.298             | 16.878         | 18.379           | 18.419            |
| 2h        | INTERNAL | PL  | 4plus_deneme  | 247  | YETERLI | %25.9     | %74.1       | 4.372             | 17.789         | 19.911           | 19.393            |
| 4h        | EXTERNAL | PH  | 0_deneme      | 1471 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 42.923           | 76.870            |
| 4h        | EXTERNAL | PH  | 1_deneme      | 479  | YETERLI | %31.3     | %68.7       | 1.000             | 12.622         | 30.284           | 25.487            |
| 4h        | EXTERNAL | PH  | 2-3_deneme    | 395  | YETERLI | %23.0     | %77.0       | 2.306             | 14.053         | 23.076           | 22.682            |
| 4h        | EXTERNAL | PH  | 4plus_deneme  | 93   | YETERLI | %17.2     | %82.8       | 4.624             | 16.731         | 20.613           | 20.093            |
| 4h        | EXTERNAL | PL  | 0_deneme      | 1551 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 40.729           | 69.262            |
| 4h        | EXTERNAL | PL  | 1_deneme      | 497  | YETERLI | %34.0     | %66.0       | 1.000             | 13.740         | 26.938           | 23.926            |
| 4h        | EXTERNAL | PL  | 2-3_deneme    | 355  | YETERLI | %21.1     | %78.9       | 2.276             | 15.986         | 25.459           | 22.610            |
| 4h        | EXTERNAL | PL  | 4plus_deneme  | 52   | YETERLI | %17.3     | %82.7       | 4.365             | 16.846         | 23.077           | 22.000            |
| 4h        | INTERNAL | PH  | 0_deneme      | 2080 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 20.720           | 60.490            |
| 4h        | INTERNAL | PH  | 1_deneme      | 1182 | YETERLI | %29.8     | %70.2       | 1.000             | 15.365         | 16.637           | 14.394            |
| 4h        | INTERNAL | PH  | 2-3_deneme    | 1180 | YETERLI | %21.8     | %78.2       | 2.331             | 16.426         | 15.840           | 15.883            |
| 4h        | INTERNAL | PH  | 4plus_deneme  | 328  | YETERLI | %19.2     | %80.8       | 4.595             | 17.640         | 15.747           | 15.408            |
| 4h        | INTERNAL | PL  | 0_deneme      | 2219 | YETERLI | %100.0    | %0.0        | 0.000             | 0.000          | 21.700           | 57.476            |
| 4h        | INTERNAL | PL  | 1_deneme      | 1234 | YETERLI | %37.0     | %63.0       | 1.000             | 15.391         | 17.989           | 17.489            |
| 4h        | INTERNAL | PL  | 2-3_deneme    | 985  | YETERLI | %27.1     | %72.9       | 2.322             | 16.902         | 17.502           | 18.121            |
| 4h        | INTERNAL | PL  | 4plus_deneme  | 181  | YETERLI | %22.7     | %77.3       | 4.376             | 17.702         | 16.110           | 16.092            |

### Karar verilemeyen satırlar (sağdan sansürlü — payda dışı)

| timeframe | scope    | rol | deneme_kovasi | n   | guven   | ort_deneme_epizot | ort_rol_sure_bar |
|-----------|----------|-----|---------------|-----|---------|-------------------|------------------|
| 1d        | EXTERNAL | PH  | 0_deneme      | 211 | YETERLI | 0.000             | 15.209           |
| 1d        | EXTERNAL | PH  | 1_deneme      | 3   | ZAYIF   | 1.000             | 20.333           |
| 1d        | EXTERNAL | PH  | 2-3_deneme    | 3   | ZAYIF   | 2.333             | 24.667           |
| 1d        | EXTERNAL | PL  | 0_deneme      | 10  | ZAYIF   | 0.000             | 18.900           |
| 1d        | EXTERNAL | PL  | 2-3_deneme    | 1   | ZAYIF   | 2.000             | 27.000           |
| 1d        | INTERNAL | PH  | 0_deneme      | 329 | YETERLI | 0.000             | 10.818           |
| 1d        | INTERNAL | PH  | 1_deneme      | 30  | YETERLI | 1.000             | 11.833           |
| 1d        | INTERNAL | PH  | 2-3_deneme    | 19  | KISMI   | 2.158             | 10.947           |
| 1d        | INTERNAL | PL  | 0_deneme      | 15  | KISMI   | 0.000             | 13.400           |
| 1d        | INTERNAL | PL  | 1_deneme      | 5   | ZAYIF   | 1.000             | 11.600           |
| 1d        | INTERNAL | PL  | 2-3_deneme    | 4   | ZAYIF   | 2.000             | 17.750           |
| 1d        | INTERNAL | PL  | 4plus_deneme  | 1   | ZAYIF   | 5.000             | 7.000            |
| 1h        | EXTERNAL | PH  | 0_deneme      | 138 | YETERLI | 0.000             | 16.732           |
| 1h        | EXTERNAL | PH  | 1_deneme      | 4   | ZAYIF   | 1.000             | 23.500           |
| 1h        | EXTERNAL | PH  | 2-3_deneme    | 1   | ZAYIF   | 2.000             | 19.000           |
| 1h        | EXTERNAL | PL  | 0_deneme      | 5   | ZAYIF   | 0.000             | 20.200           |
| 1h        | EXTERNAL | PL  | 1_deneme      | 1   | ZAYIF   | 1.000             | 25.000           |
| 1h        | INTERNAL | PH  | 0_deneme      | 229 | YETERLI | 0.000             | 9.013            |
| 1h        | INTERNAL | PH  | 1_deneme      | 51  | YETERLI | 1.000             | 10.784           |
| 1h        | INTERNAL | PH  | 2-3_deneme    | 11  | ZAYIF   | 2.000             | 13.182           |
| 1h        | INTERNAL | PL  | 0_deneme      | 10  | ZAYIF   | 0.000             | 11.800           |
| 1h        | INTERNAL | PL  | 1_deneme      | 4   | ZAYIF   | 1.000             | 11.500           |
| 1h        | INTERNAL | PL  | 2-3_deneme    | 2   | ZAYIF   | 2.500             | 20.500           |
| 2h        | EXTERNAL | PH  | 0_deneme      | 142 | YETERLI | 0.000             | 12.887           |
| 2h        | EXTERNAL | PH  | 1_deneme      | 3   | ZAYIF   | 1.000             | 22.667           |
| 2h        | EXTERNAL | PH  | 2-3_deneme    | 3   | ZAYIF   | 2.000             | 17.667           |
| 2h        | EXTERNAL | PL  | 0_deneme      | 11  | ZAYIF   | 0.000             | 21.000           |
| 2h        | EXTERNAL | PL  | 1_deneme      | 1   | ZAYIF   | 1.000             | 31.000           |
| 2h        | INTERNAL | PH  | 0_deneme      | 198 | YETERLI | 0.000             | 9.333            |
| 2h        | INTERNAL | PH  | 1_deneme      | 9   | ZAYIF   | 1.000             | 12.000           |
| 2h        | INTERNAL | PH  | 2-3_deneme    | 3   | ZAYIF   | 2.333             | 21.000           |
| 2h        | INTERNAL | PL  | 0_deneme      | 14  | ZAYIF   | 0.000             | 15.571           |
| 2h        | INTERNAL | PL  | 1_deneme      | 9   | ZAYIF   | 1.000             | 10.556           |
| 2h        | INTERNAL | PL  | 2-3_deneme    | 2   | ZAYIF   | 2.500             | 30.000           |
| 4h        | EXTERNAL | PH  | 0_deneme      | 141 | YETERLI | 0.000             | 8.908            |
| 4h        | EXTERNAL | PH  | 1_deneme      | 2   | ZAYIF   | 1.000             | 19.500           |
| 4h        | EXTERNAL | PH  | 2-3_deneme    | 1   | ZAYIF   | 3.000             | 29.000           |
| 4h        | EXTERNAL | PL  | 0_deneme      | 9   | ZAYIF   | 0.000             | 23.111           |
| 4h        | INTERNAL | PH  | 0_deneme      | 202 | YETERLI | 0.000             | 8.381            |
| 4h        | INTERNAL | PH  | 1_deneme      | 10  | ZAYIF   | 1.000             | 13.000           |
| 4h        | INTERNAL | PH  | 2-3_deneme    | 10  | ZAYIF   | 2.200             | 19.000           |
| 4h        | INTERNAL | PH  | 4plus_deneme  | 1   | ZAYIF   | 4.000             | 17.000           |
| 4h        | INTERNAL | PL  | 0_deneme      | 27  | KISMI   | 0.000             | 16.556           |
| 4h        | INTERNAL | PL  | 1_deneme      | 10  | ZAYIF   | 1.000             | 17.800           |
| 4h        | INTERNAL | PL  | 2-3_deneme    | 7   | ZAYIF   | 2.286             | 19.571           |

### Yaklaşma eşiği duyarlılığı (0.25 ana; 0.15 / 0.50 kontrol)

| esik     | timeframe | n_satir | guven   | engelledi_orani | kararsiz_adet |
|----------|-----------|---------|---------|-----------------|---------------|
| 0.25 ATR | 1d        | 7551    | YETERLI | %63.4           | 631           |
| 0.25 ATR | 1h        | 35727   | YETERLI | %66.9           | 456           |
| 0.25 ATR | 2h        | 22599   | YETERLI | %66.3           | 395           |
| 0.25 ATR | 4h        | 14702   | YETERLI | %64.9           | 420           |
| 0.15 ATR | 1d        | 7551    | YETERLI | %59.9           | 631           |
| 0.15 ATR | 1h        | 35727   | YETERLI | %64.7           | 456           |
| 0.15 ATR | 2h        | 22599   | YETERLI | %63.7           | 395           |
| 0.15 ATR | 4h        | 14702   | YETERLI | %62.4           | 420           |
| 0.5 ATR  | 1d        | 7551    | YETERLI | %72.4           | 631           |
| 0.5 ATR  | 1h        | 35727   | YETERLI | %74.1           | 456           |
| 0.5 ATR  | 2h        | 22599   | YETERLI | %73.8           | 395           |
| 0.5 ATR  | 4h        | 14702   | YETERLI | %72.5           | 420           |

## Soru 7 — WH/WL %kaçı ziyaret/süpürüldü, ne kadar sürede?
| timeframe | scope    | rol | n     | guven   | ziyaret_epizot | supuruldu | hic_ulasilmadi | sansur | ort_deneme_epizot |
|-----------|----------|-----|-------|---------|----------------|-----------|----------------|--------|-------------------|
| 1d        | EXTERNAL | WH  | 1727  | YETERLI | %65.2          | %56.2     | %43.8          | %5.4   | 1.208             |
| 1d        | EXTERNAL | WL  | 1601  | YETERLI | %74.0          | %64.1     | %35.9          | %12.1  | 1.427             |
| 1d        | INTERNAL | WH  | 3757  | YETERLI | %77.5          | %66.8     | %33.2          | %4.3   | 1.531             |
| 1d        | INTERNAL | WL  | 3751  | YETERLI | %81.7          | %71.0     | %29.0          | %11.8  | 1.558             |
| 1h        | EXTERNAL | WH  | 10669 | YETERLI | %68.2          | %56.3     | %43.7          | %0.7   | 1.340             |
| 1h        | EXTERNAL | WL  | 10453 | YETERLI | %71.3          | %60.7     | %39.3          | %1.4   | 1.291             |
| 1h        | INTERNAL | WH  | 22995 | YETERLI | %76.7          | %63.0     | %37.0          | %0.6   | 1.544             |
| 1h        | INTERNAL | WL  | 22152 | YETERLI | %80.6          | %68.9     | %31.1          | %1.7   | 1.502             |
| 2h        | EXTERNAL | WH  | 6548  | YETERLI | %67.8          | %56.9     | %43.1          | %1.0   | 1.373             |
| 2h        | EXTERNAL | WL  | 5896  | YETERLI | %71.5          | %60.3     | %39.7          | %2.8   | 1.301             |
| 2h        | INTERNAL | WH  | 13074 | YETERLI | %76.7          | %63.8     | %36.2          | %1.5   | 1.616             |
| 2h        | INTERNAL | WL  | 12832 | YETERLI | %80.4          | %69.8     | %30.2          | %2.2   | 1.509             |
| 4h        | EXTERNAL | WH  | 3854  | YETERLI | %70.5          | %59.3     | %40.7          | %1.1   | 1.444             |
| 4h        | EXTERNAL | WL  | 4126  | YETERLI | %71.2          | %60.4     | %39.6          | %6.6   | 1.325             |
| 4h        | INTERNAL | WH  | 8327  | YETERLI | %77.2          | %65.3     | %34.7          | %1.8   | 1.690             |
| 4h        | INTERNAL | WL  | 8190  | YETERLI | %80.9          | %69.9     | %30.1          | %5.0   | 1.562             |

### Seviyeye ulaşma süresi (native bar; rol atamasından itibaren)

| timeframe | rol | n    | guven   | q25   | ortanca | q75   | ortalama |
|-----------|-----|------|---------|-------|---------|-------|----------|
| 1d        | WH  | 1735 | YETERLI | 1.000 | 3.000   | 5.000 | 4.900    |
| 1d        | WL  | 1827 | YETERLI | 1.000 | 3.000   | 6.000 | 4.700    |
| 1h        | WH  | 9222 | YETERLI | 1.000 | 3.000   | 6.000 | 5.600    |
| 1h        | WL  | 9856 | YETERLI | 2.000 | 3.000   | 7.000 | 6.000    |
| 2h        | WH  | 5696 | YETERLI | 1.000 | 3.000   | 6.000 | 5.400    |
| 2h        | WL  | 5983 | YETERLI | 2.000 | 3.000   | 7.000 | 5.600    |
| 4h        | WH  | 3754 | YETERLI | 1.000 | 3.000   | 6.000 | 5.100    |
| 4h        | WL  | 4207 | YETERLI | 1.000 | 3.000   | 6.000 | 5.400    |

### EVENT_SWEEP çapraz kontrolü
| timeframe | scope    | direction | n     | guven   | uyumlu | CALISTI | ort_devam_h12 |
|-----------|----------|-----------|-------|---------|--------|---------|---------------|
| 1d        | EXTERNAL | DOWN      | 2040  | YETERLI | %95.8  | %65.2   | 1.939         |
| 1d        | EXTERNAL | UP        | 1420  | YETERLI | %95.9  | %68.0   | 2.073         |
| 1d        | INTERNAL | DOWN      | 3463  | YETERLI | %96.0  | %65.3   | 1.932         |
| 1d        | INTERNAL | UP        | 2223  | YETERLI | %95.7  | %64.6   | 2.145         |
| 1h        | EXTERNAL | DOWN      | 9378  | YETERLI | %97.3  | %62.9   | 1.759         |
| 1h        | EXTERNAL | UP        | 7698  | YETERLI | %96.1  | %61.8   | 2.012         |
| 1h        | INTERNAL | DOWN      | 14888 | YETERLI | %97.4  | %63.1   | 1.812         |
| 1h        | INTERNAL | UP        | 12486 | YETERLI | %96.3  | %62.5   | 2.047         |
| 2h        | EXTERNAL | DOWN      | 6506  | YETERLI | %97.9  | %64.6   | 1.878         |
| 2h        | EXTERNAL | UP        | 4752  | YETERLI | %96.1  | %63.1   | 2.068         |
| 2h        | INTERNAL | DOWN      | 9742  | YETERLI | %98.2  | %64.2   | 1.799         |
| 2h        | INTERNAL | UP        | 7349  | YETERLI | %96.3  | %62.7   | 2.041         |
| 4h        | EXTERNAL | DOWN      | 4012  | YETERLI | %98.4  | %66.7   | 2.016         |
| 4h        | EXTERNAL | UP        | 2919  | YETERLI | %95.6  | %64.9   | 2.157         |
| 4h        | INTERNAL | DOWN      | 6375  | YETERLI | %98.2  | %64.1   | 1.878         |
| 4h        | INTERNAL | UP        | 4452  | YETERLI | %96.3  | %64.6   | 2.118         |

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
| 1d        | KULLANILAMAZ | 4885  | YETERLI | %65.9   | %94.8  | 2.127         |
| 1d        | Q1_dusuk     | 2378  | YETERLI | %63.2   | %95.2  | 1.807         |
| 1d        | Q2           | 4521  | YETERLI | %66.4   | %96.4  | 2.019         |
| 1d        | Q3           | 3234  | YETERLI | %65.6   | %96.3  | 2.185         |
| 1d        | Q4_yuksek    | 2056  | YETERLI | %72.9   | %96.4  | 2.439         |
| 1h        | KULLANILAMAZ | 4787  | YETERLI | %63.9   | %96.3  | 2.057         |
| 1h        | Q1_dusuk     | 23588 | YETERLI | %64.0   | %97.2  | 1.985         |
| 1h        | Q2           | 16133 | YETERLI | %64.3   | %96.5  | 2.001         |
| 1h        | Q3           | 17497 | YETERLI | %64.7   | %96.9  | 2.068         |
| 1h        | Q4_yuksek    | 19848 | YETERLI | %66.1   | %97.1  | 2.197         |
| 2h        | KULLANILAMAZ | 4479  | YETERLI | %64.8   | %96.2  | 2.166         |
| 2h        | Q1_dusuk     | 10236 | YETERLI | %64.1   | %96.7  | 1.978         |
| 2h        | Q2           | 13808 | YETERLI | %64.2   | %97.3  | 1.985         |
| 2h        | Q3           | 12061 | YETERLI | %65.9   | %97.9  | 2.075         |
| 2h        | Q4_yuksek    | 11443 | YETERLI | %68.3   | %97.8  | 2.324         |
| 4h        | KULLANILAMAZ | 4412  | YETERLI | %65.3   | %96.4  | 2.177         |
| 4h        | Q1_dusuk     | 5214  | YETERLI | %66.3   | %96.1  | 2.126         |
| 4h        | Q2           | 6950  | YETERLI | %66.1   | %97.5  | 2.123         |
| 4h        | Q3           | 8620  | YETERLI | %67.0   | %98.2  | 2.148         |
| 4h        | Q4_yuksek    | 8067  | YETERLI | %69.5   | %98.0  | 2.410         |
