# Native 2h/4h ↔ 1h tutarlılığı

> Üreten: `python -m research.native_tutarlilik`
> Amaç: native dosyaların **1h ile aynı barı** anlatıp anlatmadığını ölçmek.

Bu bir resample karşılaştırması **değildir**: hiçbir sayı 1h'den türetilmedi,
yalnız iki bağımsız serinin aynı mumu ne kadar farklı kapattığı ölçüldü.

## 2h — 174 sembol

- Kapanış |fark| **medyanı**: 0.249% (sembol p95 medyanı 1.153%)
- Birebir aynı kapanış: sembollerin medyanı **%3.5**
- Barların >%0,5 fark ettiği oran (sembol medyanı): **%23.2**
- Uyumsuz sembol (medyan fark > %0.5): **6** (%3.4)

| sembol | ortak bar | medyan fark | p95 | birebir |
|---|---:|---:|---:|---:|
| KRTEK | 1483 | 71.03% | 71.29% | %0.9 |
| CVKMD | 1483 | 61.27% | 61.73% | %0.4 |
| SKBNK | 1484 | 22.19% | 22.84% | %0.2 |
| MARTI | 1484 | 1.00% | 36.05% | %6.3 |
| CANTE | 1483 | 0.78% | 16.32% | %5.6 |
| BJKAS | 1483 | 0.52% | 1.38% | %12.2 |

## 4h — 174 sembol

- Kapanış |fark| **medyanı**: 0.212% (sembol p95 medyanı 1.031%)
- Birebir aynı kapanış: sembollerin medyanı **%4.0**
- Barların >%0,5 fark ettiği oran (sembol medyanı): **%19.5**
- Uyumsuz sembol (medyan fark > %0.5): **7** (%4.0)

| sembol | ortak bar | medyan fark | p95 | birebir |
|---|---:|---:|---:|---:|
| KRTEK | 1074 | 71.05% | 71.25% | %1.0 |
| CVKMD | 1069 | 61.30% | 61.64% | %0.4 |
| MARTI | 1075 | 34.67% | 36.05% | %5.7 |
| SKBNK | 1063 | 22.19% | 22.75% | %0.2 |
| CANTE | 1075 | 1.03% | 16.36% | %4.8 |
| GSRAY | 1075 | 0.60% | 10.50% | %11.3 |
| SELVA | 1074 | 0.56% | 41.15% | %7.0 |

## Nasıl okunur

- %0,3 civarı medyan fark **beklenen** düzeydir: kova çapası (09:00 vs 09:30) ve
  sağlayıcı fiyat kaynağı farkı. Bu düzeyde 2h/4h sayıları kullanılabilir;
  ancak tam eşik sınırında tetiklenen sinyaller iki seride farklı sonuç verir.
- **%1 üstü** fark, o sembolde 2h/4h analizinin 1h ile çeliştiğini gösterir;
  o sembolün 2h/4h sayıları raporda ayrıca işaretlenmeli.
- Bu araç karar vermez; hangi sembolde hangi zaman dilimine güvenilebileceğini
  gösteren bir **veri kalitesi** ölçümüdür.

