# Büyük FVG ilk teması: tarih, fiyat ve sonraki 12 mum

**Doğrudan arşiv taraması.** 176 sembol × motorun desteklediği 3 native periyot (2s, 4s, günlük) = **528 seri**. Dengeli profilde aday aşamasını geçmiş 57.009 FVG bulundu. Önceki [replay derlemesindeki](../../REPLAY_ANA_DERLEMESI.md) tanımı koruduk: büyük = başlangıçtaki bant genişliği / oluşum mumundaki Wilder ATR(14) **≥1**, çok büyük **≥2**. Tarihler İstanbul saatinde **sağlayıcının mum etiketi**; fitilin saat/dakikası bilinmez. Günlükte 00:00 tarih etiketidir, işlem saati değildir.

- **[Bütün büyük FVG’ler: tarih ve fiyat envanteri (CSV.gz)](BUYUK_FVG_TARIHLERI.csv.gz)** — 11.084 ayrı bölge. `temas_no=0` motor ömründe hiç temas yok (2.559 bölge); `1` ilk motor teması (8.525); `2` ikinci motor teması (137 ek satır). Dosyayı açıp sembol, tarih ve `genislik_atr` ile filtreleyebilirsiniz. Büyüklerin ilk motor temaslarından 90 mum bandı geometrik olarak kesmemiştir (tek taraflı motor koşulu/gap); fiyat karşılaştırmasının paydasına katılmadılar.
- **[Dört örneğin mum mum OHLCV’si](DORT_ORNEK_MUMLAR.csv)** — bar 0 ilk temas; sonraki 12 mumun tarihleri, en yüksek, en düşük ve kapanışları.
- **[Boyut × zaman dilimi sayımları](ILK_TEMAS_OZET.csv)** — küçük bölgeler de kontrol olarak dahil.

## Tarihli dört örnek (2026)

| Hisse ve yön | Oluşum → ilk temas | Bant / boyut | Sonraki hareket |
|---|---|---|---|
| **TUPRS · 2s ↑** | 20 Tem 11:00 → **20 Tem 13:00** | 289,50–302,25 / **2,57 ATR** | Temas mumunun dibi 301,25, kapanışı 304,50. Sonraki iki kapanış 306,75 → 307,50. **21 Tem 11:00**, +4. mumda tepe 311,25: 309,48 hedefi geçildi. +12 kapanış 313,75; bu 12 mumun hiçbiri banda dönmedi. |
| **THYAO · 4s ↓** | 18 Şub 17:00 → **19 Şub 09:00** | 331,00–345,25 / **2,20 ATR** | Temas mumunun tepesi tam 331,00, kapanışı 319,50. Bu mumdaki düşüşü sonuç saymadık. **19 Şub 17:00**, +2. mumun dibi 310,25: kapanıştan hesaplanan 312,65 hedefi de görüldü. +12 kapanış 308,50; arada banda dönüş yok. |
| **TUPRS · 4s ↑** | 20 Tem 13:00 → **27 Tem 09:00** | 289,50–301,25 / **2,04 ATR** | İlk kapanış 295,00. **28 Tem 13:00**, +4. mumda dip 289,00: bant tamamen doldu. 301,04 hedefi **29 Tem 13:00** mumunda görüldü ama artık “ilk temastan temiz tepki” değildi. Aynı hissede benzer bant, başka periyot ve başka temas. |
| **GARAN · 2s ↑** | 5 Eki 11:00 → **5 Eki 17:00** | 126,30–130,10 / **2,07 ATR** | İlk kapanış 130,40. Fiyat banttan ayrıldı; **7 Eki 11:00** mumunda dip 128,00 ile geri döndü. 132,06 hedefi 12 mumda hiç görülmedi; +12 kapanış 128,10. |

## Örneklerin ötesinde

Her **geometrik ilk temasın kapanışından** hareketi ölçtük. Hedef = o kapanıştan FVG yönünde **1 temas ATR’si**. Hedefin **ilk** gelmesi için sonraki 12 mum içinde hem banda dönüşten hem de uzak kenarın fitille tamamen dolmasından önce görülmesi gerekir. Bitişik kesişen mumlar tek ziyarettir. Açıkça ilk gelen hedefleri saydık; aynı mumda iki olay varsa sırasını tahmin etmedik.

| Oluşum genişliği | Geometrik ilk temas | Engel öncesi 1 ATR | Tüm ilk temaslara oranı | Dönüş/dolumu dikkate almadan 12 mumda 1 ATR¹ |
|---|---:|---:|---:|---:|
| <0,5 ATR | 20.730 | 3.115 | %15,0 | %64,5 |
| 0,5–<1 ATR | 13.494 | 4.036 | %29,9 | %64,1 |
| 1–<2 ATR | 6.610 | 2.942 | %44,5 | %65,7 |
| **≥2 ATR** | **1.825** | **1.134** | **%62,1** | **%72,1** |

¹ Son sütunun paydası **12 ileri mumu tamamlanmış** ilk temastır (sırasıyla 20.491, 13.301, 6.530, 1.811). Diğer oranda payda tüm ilk temaslar; belirsiz veya tamamlanmamış olanlar “kesin hedef” değildir. ≥2 ATR grubunda 1.134 kesin hedef dışında 376 tam dolum, 173 dönüş, 34 aynı-mum belirsizliği, 106 ufuk sonu, 2 eksik ufuk vardır. Kesin hedeflerin medyan süresi **2 mum**. Hedef yönlü fiyat uzanımıdır; kapanış teyidi veya işlem getirisi değildir. Hedef seviyesi her zaman bandın dışında olmak zorunda değildir.

**“Tek temas”ı gerçekten tek mum diye okursak:** ≥2 ATR grubunda tam 12 ileri mumu bulunan 1.811 olayın **215’inde** yalnız temas mumu bandı kesti. Bunların **199’unda** hedef engelden önce görüldü. Ama bu 215 olayı *ilk kapanışta* ayırmak mümkün değildir: seçim gelecek 12 mumda tekrar değmemeyi şart koşuyor. **199/215 bir canlı alarm isabeti değildir.** İlk temasta bilinen genişliğe göre karşılaştırma yukarıdaki %62,1’lik satırdır.

**Yorum:** Genişlik bu arşivde ayrıştırıyor; tek başına dönüş garantisi değil. Farkın bir kısmı mekanik: geniş bandın uzak kenarını tamamen doldurmak daha zor. Bu yüzden son sütun önemlidir: dolumu önemsemesek bile ≥2 ATR grubunda yönlü hareket daha sık, fakat fark çok daha küçük. Aynı hareket farklı zaman dilimlerinde yeniden sayılabilir; bu çalışma bağımsız işlemler testi veya ileri dönem doğrulaması değildir.

## Veri sözlüğü ve tekrar koşusu

`dogum` / `bilinebilir` oluşum ve motorun bölgeyi ilk bildiği mum; `alt`/`ust` orijinal bandın kenarlarıdır. `sonraki_motor_temasi` motor bölgeyi takip ederken gördüğü sonraki ziyaret; `banda_donus` ise **motor takibi bitse bile** ham mumlarda ilk ayrılma sonrası ilk geometrik geri dönüştür. `motor_sonuc` motor kapanışlarını da içerir (yeni bölgenin devralması fiyat bozuluşu değildir). Ana tablo **`fiyat_sonuc`** kullanır. `fiyat_karar_bar/zamani` ilk olayın sırasını; `ilk_hedef_bar/zamani` ise dolumdan sonra bile olsa fiyatın hedefi ilk gördüğü mumu verir. `kesisen_mum` başlangıç dahil gözlenen pencerede bandı kesen toplam mum sayısı; `kapanis_1/3/6/12` olay sonrası gerçek kapanışlar. Tarihlerin hepsi borsa takvim günü değil mevcut bar sırasıyla okunmalıdır. Bulunmayan zamanlar boştur.

```bash
python -m research.fvg_temas_izleri --cikti var/fvg_izleri
python -m research.fvg_fiyat_raporu --girdi var/fvg_izleri/tum_izler.csv.gz --cikti var/fvg_rapor
```

Veri kaynağı yerel `backfill_data/`; 2s/4s türetilmedi. Bunlar arşivdeki sağlayıcı fiyatlarıdır; kurumsal aksiyonlar ve sağlayıcı farkları ayrıca doğrulanmadı. Canlı kurala veya Telegram gönderimine değişiklik yapılmadı.
