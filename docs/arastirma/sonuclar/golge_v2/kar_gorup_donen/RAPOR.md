# Gölge v2 — Kâr Görüp Dönenler: 0.5 / 1 ATR Gördükten Sonra Stop Olan İşlemlerin Domain Dökümü

> Üretici: `python -m research.golge_v2_kar_gorup_donen`. Bu dosya elle düzenlenmez.

- Kapsam: `4h + 1d` birincil işlemler (sansürsüz, veri karantinası dışı). İşlem: `4233`. Sonuçlar ana CSV'den okunur; yalnız domain serileri yeniden kurulur.
- Ölçü birimi ATR'dir (giriş anındaki ATR; hedef 2 ATR). "0.5 ATR gördü": çıkış mumundan ÖNCEKİ bir mumun lehte ucu girişten en az 0.5 ATR uzaklaştı. Stop mumunun içinde önce yükselip sonra düşen işlemler görünmez; sayılar alt sınırdır.

**Üç okuma, üç ayrı güç.** (1) *Eşik anı*: eşiğin ilk görüldüğü mumun kapanışında bilinenler ve sonrasında olanlar; aynı eşiği görüp hedefe gidenler kontrol grubudur ve tek adil karşılaştırma budur. (2) *Eşikten sonra*: eşik mumundan çıkışa kadar görülen olaylar; uzun yaşayan işlem hem daha çok olay görür hem daha sık stop olur, bu yüzden olayları olduğundan kötü gösterir. (3) *Tepeden stopa*: yalnız stop olanlara geriye dönük bakış; ne görüldüğünü anlatır, neden olduğunu kanıtlamaz.

**Çıkış karşı-olgusu.** Bir gözlem stop oranını ayırsa bile ona göre çıkmak kazandırmayabilir: aynı gözlemi görüp hedefe giden işlemlerin kârı da kesilir. Bu yüzden her gözlem için "o kapanışta karar verip sonraki açılışta çıkılsaydı" ayrıca ölçülür; ölçüt budur.

**Terimler.** *Karşı engel*: işlemin gideceği yönde, mumdan ÖNCEKİ kapanışta bilinen seviye — Stabil karşı seviyesi, Market Structure tepe/dip seviyeleri (korunan, zayıf, kırılmamış ve ters yönde kırılmış), yüksekliği en az `0.5 ATR` olan karşı OB/FVG bandı. *Değdi, aşamadı*: mumun lehte ucu engele ulaştı, kapanış ötesine geçemedi. *Dibinde kaldı*: değmedi ama `0.25 ATR` kadar yaklaştı. *Tez seviyesi*: işlemin dayandığı kırılım seviyesi. *Formasyon bozulması*: süreç izinde sistemin aleyhte saydığı formasyon etiketleri (retest ediliyor, teyit alamadı, başarısız, karşı kırılım). *Birincil gözlem*: bir işlemde birden çok şey görüldüyse tabloda yukarıdan aşağı ilk sıradaki sayılır; sıra ölçümden önce sabitlenmiştir. Bu sıra bir önem sırası DEĞİLDİR; hangi gözlemin gerçekten ayırdığını "Kontrol" sütunu ve eşik anı tablosu gösterir.

**Karar etiketleri (eşik anı tablosu).** `AYIRIYOR`: gözlem varken ve yokken stop oranı farkı keşif ve doğrulamada aynı yönde ve sembol / gün / hafta / ay kümeli %95 aralıkların en genişi sıfırı dışlıyor. `ZAYIF`: iki dönemde aynı yönde ama aralık sıfırı içeriyor. `AYIRMIYOR`: iki dönemde yön değiştiriyor. `SAYILMAZ_N<30`: gözlemin olduğu ya da olmadığı grup `30` işlemden az. Çoklu karşılaştırma düzeltmesi yoktur.

**Gözlem listesi.** Eşik anı tablosundaki gözlemlerin `20` tanesi ölçümden önce sabitlendi. † işaretli `4` gözlem ilk koşudan sonra domain kapsamını tamamlamak için eklendi (Market Structure süpürme olayı, OB / FVG'de dışarıdan / içeriden ayrımı, formasyon durumu); "çıkılsaydı" karşı-olgusu da ilk koşudan sonra eklendi. Hepsi sonucundan bağımsız raporlanır; † işaretli bir satırın tek başına ayırması, ön-kayıtlı bir satırınkinden daha zayıf kanıttır.

## Kısa özet

- **D7: 637 işlemden 280 tanesi stop oldu.** Bunların `151` tanesi stoptan önce 0.5 ATR'yi hiç görmedi; `129` tanesi en az 0.5 ATR, `58` tanesi en az 1 ATR gördükten sonra döndü.
- **0.5 ATR görüp o mumun kapanışında hâlâ açık olan 411 işlemin akıbeti:** stop `129 (31.4%)`, hedef `194 (47.2%)`, süre sonunda kârda `60 (14.6%)`, zararda `28 (6.8%)`; bu grubun ortalaması `+0.402 R`.
- **0.5 ATR görüp stop olan 129 işlemde tepeden stopa ne görüldü (bir işlemde birden çoğu olabilir):** bilinen engele takıldı `51` (39.5%); engelin dibinde kaldı `6` (4.7%); endeks tersine döndü `79` (61.2%); hissenin yapısı bozuldu `51` (39.5%); ters hacim `36` (27.9%); boşlukla stop `13` (10.1%); hiçbiri `12` (9.3%).
- **Kontrol — aynı tür olay 0.5 ATR gören bütün işlemlerde görülünce stop oranı / görülmeyince:** bilinen engele takıldı `30.1% / 32.8%`; endeks tersine döndü `54.0% / 19.6%`; hissenin yapısı bozuldu `61.6% / 23.4%`; ters hacim `34.4% / 30.5%`. İki oran yakınsa o gözlem dönüşü açıklamaz; uzak olanlar da işlem sürerken ortaya çıkar, önceden bilinmez.
- **0.5 ATR görüldüğü kapanışta bilinen engele takılmış olmak sonradan stop olmayı ayırıyor mu:** herhangi bir engel `30.9%` / yokken `31.7%` → AYIRMIYOR; Stabil `38.5%` / yokken `31.2%` → SAYILMAZ_N<30; Market Structure `40.0%` / yokken `29.0%` → ZAYIF; OB / FVG `25.2%` / yokken `33.6%` → ZAYIF.
- **0.5 ATR görüldüğü kapanışta, sonradan stop olacakları ayıran gözlem** (`24` gözlemden): `ESIK_ALTI_KAPANIS` (stop `42.3%` / yokken `19.4%`); `FITIL` (stop `46.1%` / yokken `24.7%`); `DAR_STOP` (stop `42.5%` / yokken `27.5%`).
- **0.5 ATR: o gözlem görülünce sonraki açılışta çıkmak kabul merdiveninden geçiyor mu:** hiçbiri geçmiyor.
- **1 ATR görüp o mumun kapanışında hâlâ açık olan 293 işlemin akıbeti:** stop `58 (19.8%)`, hedef `163 (55.6%)`, süre sonunda kârda `53 (18.1%)`, zararda `19 (6.5%)`; bu grubun ortalaması `+0.706 R`.
- **1 ATR görüp stop olan 58 işlemde tepeden stopa ne görüldü (bir işlemde birden çoğu olabilir):** bilinen engele takıldı `25` (43.1%); engelin dibinde kaldı `2` (3.4%); endeks tersine döndü `40` (69.0%); hissenin yapısı bozuldu `19` (32.8%); ters hacim `16` (27.6%); boşlukla stop `7` (12.1%); hiçbiri `5` (8.6%).
- **Kontrol — aynı tür olay 1 ATR gören bütün işlemlerde görülünce stop oranı / görülmeyince:** bilinen engele takıldı `20.0% / 19.6%`; endeks tersine döndü `40.2% / 9.5%`; hissenin yapısı bozuldu `61.3% / 14.9%`; ters hacim `23.7% / 18.8%`. İki oran yakınsa o gözlem dönüşü açıklamaz; uzak olanlar da işlem sürerken ortaya çıkar, önceden bilinmez.
- **1 ATR görüldüğü kapanışta bilinen engele takılmış olmak sonradan stop olmayı ayırıyor mu:** herhangi bir engel `20.7%` / yokken `19.2%` → AYIRMIYOR; Stabil `10.0%` / yokken `20.1%` → SAYILMAZ_N<30; Market Structure `25.4%` / yokken `18.1%` → ZAYIF; OB / FVG `16.7%` / yokken `20.8%` → ZAYIF.
- **1 ATR görüldüğü kapanışta, sonradan stop olacakları ayıran gözlem** (`24` gözlemden): `FITIL` (stop `33.0%` / yokken `14.1%`).
- **1 ATR: o gözlem görülünce sonraki açılışta çıkmak kabul merdiveninden geçiyor mu:** hiçbiri geçmiyor.

**Kümeler yan yana.** Yüzdeler "görüldüğü işlem" paylarıdır (örtüşür); son iki sütun eşik anı tablosundandır.

| Küme | Eşik | Görüp stop olan | Engele takıldı | Endeks döndü | Yapı bozuldu | Ters hacim | Hiçbiri | Eşik anında ayıran gözlem | Geçen çıkış kuralı |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D7 | 0.5 ATR | 129 | 39.5% | 61.2% | 39.5% | 27.9% | 9.3% | 3 / 24 | 0 |
| D7 | 1 ATR | 58 | 43.1% | 69.0% | 32.8% | 27.6% | 8.6% | 1 / 24 | 0 |
| D6 | 0.5 ATR | 230 | 47.4% | 59.1% | 43.0% | 30.0% | 8.7% | 6 / 24 | 0 |
| D6 | 1 ATR | 104 | 51.0% | 64.4% | 36.5% | 33.7% | 7.7% | 3 / 24 | 0 |
| D1 | 0.5 ATR | 851 | 60.9% | 59.1% | 43.6% | 32.3% | 6.3% | 13 / 24 | 0 |
| D1 | 1 ATR | 393 | 65.6% | 60.6% | 36.9% | 36.4% | 5.9% | 10 / 24 | 0 |

## D7_A_Arti — 637 işlem, 280 stop

Stopların `151` tanesi stoptan önce 0.5 ATR'yi hiç görmedi (doğrudan / çok az yükselip düşen); `129` tanesi en az 0.5 ATR gördü; bunların `58` tanesi en az 1 ATR gördü.

### 1. Eşiği gören işlemlerin akıbeti

"Gören işlem": eşiği çıkış mumundan ÖNCE gören, yani o mumun kapanışında hâlâ açık olan işlem. Eşiği ilk kez çıkış mumunda gören işlemler (örneğin tek mumda hedefe giden) burada yoktur; o an verilecek bir karar olmadığı için.

| Eşik | Gören işlem | Stop oldu | Hedefe gitti | Süre doldu, kârda | Süre doldu, zararda | Grubun net R'si |
|---|---:|---:|---:|---:|---:|---:|
| 0.5 ATR | 411 (64.5%) | 129 (31.4%) | 194 (47.2%) | 60 (14.6%) | 28 (6.8%) | +0.402 |
| 1 ATR | 293 (46.0%) | 58 (19.8%) | 163 (55.6%) | 53 (18.1%) | 19 (6.5%) | +0.706 |

### 2. Tepeden stopa: 0.5 ATR görüp stop olanlarda ne görüldü

`129` işlem (keşif `84`, doğrulama `45`; long `61`, short `68`). "Kontrol" sütunu aynı tür olayın eşiği gören BÜTÜN işlemlerdeki karşılığıdır: olay eşikten sonra görülünce stop oranı / görülmeyince stop oranı. İki oran yakınsa o gözlem dönüşü açıklamaz.

| Gözlem | Görüldüğü işlem | Yalnız bu görüldü | Birincil gözlem (toplam %100) | Kontrol: görülünce stop / görülmeyince stop |
|---|---:|---:|---:|---:|
| Tepe mumu bilinen bir karşı seviyeye / banda değdi, kapanışla aşamadı | 51 (39.5%) | 9 | **51 (39.5%)** | 30.1% / 32.8% |
| Tepe, bilinen bir karşı seviyenin 0.25 ATR dibinde kaldı (değmedi) | 6 (4.7%) | 2 | **6 (4.7%)** | — |
| Tepe kapanışından stop mumuna endeks işlemin tersine en az %0.5 gitti | 79 (61.2%) | 23 | **46 (35.7%)** | 54.0% / 19.6% |
| Hissenin kendi yapısı bozuldu (ters BOS/CHoCH, tez seviyesinin içine kapanış ya da formasyon bozulması) | 51 (39.5%) | 1 | **7 (5.4%)** | 61.6% / 23.4% |
| Ters hacim baskısı ya da tepede yüksek çaba – zayıf sonuç | 36 (27.9%) | 4 | **5 (3.9%)** | 34.4% / 30.5% |
| Stop bir açılış boşluğuyla geldi | 13 (10.1%) | 2 | **2 (1.6%)** | — |
| Yukarıdakilerin hiçbiri görülmedi | 12 (9.3%) | 12 | **12 (9.3%)** | — |

- İki ya da daha çok gözlemin birlikte görüldüğü işlem: `76 (58.9%)`.
- Tepe mumunun takıldığı engel, alan alan (bir işlem birden çok alanda sayılabilir): Stabil `6 (4.7%)`; Market Structure `37 (28.7%)`; OB / FVG `27 (20.9%)`.
- OB / FVG ayrımı: banda dışarıdan gelip takılan `13 (10.1%)`; önceki kapanışta zaten bandın içinde olup çıkamayan `14 (10.9%)`. Engel gözlemi YALNIZ "zaten içinde olunan bant"tan gelen işlem: `6 (4.7%)`.
- Market Structure motorunun kendi olayı — ters süpürme / sahte kırılım: tepe mumunda `10 (7.8%)`; tepe mumundan stop öncesi son kapanışa `35 (27.1%)`.
- Yapı ayrıntısı (tepe mumundan stop öncesi son kapanışa): ters dış kırılım `0 (0.0%)`; ters iç kırılım `0 (0.0%)`; tez seviyesinin içine kapanış `47 (36.4%)`; formasyon bozulması `40 (31.0%)` (tepe mumunun kapanışında formasyon zaten aleyhte durumda olan `8 (6.2%)`).
- Hacim ayrıntısı: tepe ile stop arasında ters baskı `33 (25.6%)`; tepede yüksek çaba – zayıf sonuç `3 (2.3%)`; tepe mumunda düşük göreli hacim `14 (13.0%)` (hacmi bilinenler içinde).
- Tepe mumu aralığının en az yarısını geri verip kapattı (fitil): `86 (66.7%)`. Stop mumunun kendisinde ters yapı kırılımı: `3 (2.3%)` (düşüşün sonucu, habercisi değil).
- Stoptan önceki son kapanışta işlem hâlâ kârdaydı: `45 (34.9%)`.
- Tepeden stopa kaç mum: 1 mum `35 (27.1%)`; 2 mum `33 (25.6%)`; 3 mum `25 (19.4%)`; 4+ mum `36 (27.9%)`; medyan `2`.
- Tepeden stopa gereken geri çekilme: medyan `2.32 ATR`; en çok 1.5 ATR olan `14 (10.9%)`; 2 ATR'den büyük olan `87 (67.4%)`.

### 3. Tepeden stopa: 1 ATR görüp stop olanlarda ne görüldü

`58` işlem (keşif `35`, doğrulama `23`; long `27`, short `31`). "Kontrol" sütunu aynı tür olayın eşiği gören BÜTÜN işlemlerdeki karşılığıdır: olay eşikten sonra görülünce stop oranı / görülmeyince stop oranı. İki oran yakınsa o gözlem dönüşü açıklamaz.

| Gözlem | Görüldüğü işlem | Yalnız bu görüldü | Birincil gözlem (toplam %100) | Kontrol: görülünce stop / görülmeyince stop |
|---|---:|---:|---:|---:|
| Tepe mumu bilinen bir karşı seviyeye / banda değdi, kapanışla aşamadı | 25 (43.1%) | 5 | **25 (43.1%)** | 20.0% / 19.6% |
| Tepe, bilinen bir karşı seviyenin 0.25 ATR dibinde kaldı (değmedi) | 2 (3.4%) | 0 | **2 (3.4%)** | — |
| Tepe kapanışından stop mumuna endeks işlemin tersine en az %0.5 gitti | 40 (69.0%) | 15 | **24 (41.4%)** | 40.2% / 9.5% |
| Hissenin kendi yapısı bozuldu (ters BOS/CHoCH, tez seviyesinin içine kapanış ya da formasyon bozulması) | 19 (32.8%) | 0 | **1 (1.7%)** | 61.3% / 14.9% |
| Ters hacim baskısı ya da tepede yüksek çaba – zayıf sonuç | 16 (27.6%) | 0 | **1 (1.7%)** | 23.7% / 18.8% |
| Stop bir açılış boşluğuyla geldi | 7 (12.1%) | 0 | **0 (0.0%)** | — |
| Yukarıdakilerin hiçbiri görülmedi | 5 (8.6%) | 5 | **5 (8.6%)** | — |

- İki ya da daha çok gözlemin birlikte görüldüğü işlem: `33 (56.9%)`.
- Tepe mumunun takıldığı engel, alan alan (bir işlem birden çok alanda sayılabilir): Stabil `1 (1.7%)`; Market Structure `20 (34.5%)`; OB / FVG `11 (19.0%)`.
- OB / FVG ayrımı: banda dışarıdan gelip takılan `4 (6.9%)`; önceki kapanışta zaten bandın içinde olup çıkamayan `7 (12.1%)`. Engel gözlemi YALNIZ "zaten içinde olunan bant"tan gelen işlem: `3 (5.2%)`.
- Market Structure motorunun kendi olayı — ters süpürme / sahte kırılım: tepe mumunda `3 (5.2%)`; tepe mumundan stop öncesi son kapanışa `15 (25.9%)`.
- Yapı ayrıntısı (tepe mumundan stop öncesi son kapanışa): ters dış kırılım `0 (0.0%)`; ters iç kırılım `0 (0.0%)`; tez seviyesinin içine kapanış `19 (32.8%)`; formasyon bozulması `14 (24.1%)` (tepe mumunun kapanışında formasyon zaten aleyhte durumda olan `0 (0.0%)`).
- Hacim ayrıntısı: tepe ile stop arasında ters baskı `14 (24.1%)`; tepede yüksek çaba – zayıf sonuç `2 (3.4%)`; tepe mumunda düşük göreli hacim `5 (10.4%)` (hacmi bilinenler içinde).
- Tepe mumu aralığının en az yarısını geri verip kapattı (fitil): `44 (75.9%)`. Stop mumunun kendisinde ters yapı kırılımı: `1 (1.7%)` (düşüşün sonucu, habercisi değil).
- Stoptan önceki son kapanışta işlem hâlâ kârdaydı: `21 (36.2%)`.
- Tepeden stopa kaç mum: 1 mum `14 (24.1%)`; 2 mum `14 (24.1%)`; 3 mum `12 (20.7%)`; 4+ mum `18 (31.0%)`; medyan `3`.
- Tepeden stopa gereken geri çekilme: medyan `2.68 ATR`; en çok 1.5 ATR olan `0 (0.0%)`; 2 ATR'den büyük olan `54 (93.1%)`.

### 4. Eşik anı: 0.5 ATR ilk görüldüğü mumun kapanışında domainler

`411` işlem. "Varken stop": gözlem o kapanışta varsa işlemin sonradan stop olma oranı.

| Gözlem | Var (n) | Varken stop | Yokken stop | Fark (puan) | Fark en kötü GA | Keşif / doğrulama farkı | Stoplarda | Hedefe gidenlerde | Net R: var / yok | Karar |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| Eşik mumu bilinen bir karşı engele değdi, kapanışla aşamadı | 162 / 411 | 30.9% | 31.7% | -0.9 | [-11.4, +8.9] | -8.7 / +12.2 | 38.8% | 36.1% | +0.283 / +0.481 | **AYIRMIYOR** |
| … karşı Stabil seviyesine değip aşamadı | 13 / 411 | 38.5% | 31.2% | +7.3 | [—, —] | +0.8 / +21.1 | 3.9% | 2.6% | +0.294 / +0.406 | **SAYILMAZ_N<30** |
| … karşı Market Structure seviyesine değip aşamadı | 90 / 411 | 40.0% | 29.0% | +11.0 | [-2.2, +23.9] | +3.5 / +21.8 | 27.9% | 17.5% | +0.054 / +0.500 | **ZAYIF** |
| … karşı OB / FVG bandına değip aşamadı | 107 / 411 | 25.2% | 33.6% | -8.3 | [-19.2, +3.0] | -12.8 / -0.6 | 20.9% | 26.8% | +0.425 / +0.395 | **ZAYIF** |
| … … banda dışarıdan gelip takıldı † | 67 / 411 | 22.4% | 33.1% | -10.8 | [-22.2, +1.6] | -16.7 / -0.3 | 11.6% | 19.1% | +0.504 / +0.383 | **ZAYIF** |
| … … önceki kapanışta zaten bandın içindeydi, çıkamadı † | 40 / 411 | 30.0% | 31.5% | -1.5 | [-16.5, +13.5] | -2.0 / -0.9 | 9.3% | 7.7% | +0.292 / +0.414 | **ZAYIF** |
| Eşik mumu bir karşı engeli kapanışla aştı (takıldığı engel yok) | 60 / 411 | 21.7% | 33.0% | -11.4 | [-24.1, +4.9] | -5.1 / -18.5 | 10.1% | 18.0% | +0.800 / +0.334 | **ZAYIF** |
| Kapanışın önünde en çok 0.5 ATR'de karşı engel var | 158 / 411 | 33.5% | 30.0% | +3.5 | [-6.0, +13.4] | -1.1 / +11.6 | 41.1% | 35.6% | +0.337 / +0.443 | **AYIRMIYOR** |
| Kapanış ile hedef arasında karşı engel var | 238 / 411 | 33.2% | 28.9% | +4.3 | [-5.8, +14.9] | +2.2 / +9.0 | 61.2% | 51.5% | +0.322 / +0.513 | **ZAYIF** |
| Eşiği mum içinde gördü ama altında kapattı | 215 / 411 | 42.3% | 19.4% | +22.9 | [+13.0, +32.0] | +18.7 / +30.5 | 70.5% | 39.7% | +0.078 / +0.759 | **AYIRIYOR** |
| Mum, aralığının en az yarısını geri verip kapattı | 128 / 411 | 46.1% | 24.7% | +21.4 | [+7.4, +34.0] | +21.3 / +21.7 | 45.7% | 21.1% | -0.110 / +0.634 | **AYIRIYOR** |
| Göreli hacim 0.75'in altında | 44 / 344 | 36.4% | 30.7% | +5.7 | [-11.9, +23.3] | +12.1 / -1.1 | 14.8% | 11.9% | +0.412 / +0.375 | **AYIRMIYOR** |
| Göreli hacim en az 2 | 64 / 344 | 31.2% | 31.4% | -0.2 | [-18.2, +17.5] | -10.5 / +13.7 | 18.5% | 19.4% | +0.211 / +0.418 | **AYIRMIYOR** |
| Hacim baskısı işlemin tersine (< −0.13) | 11 / 344 | 27.3% | 31.5% | -4.3 | [—, —] | -13.2 / +4.0 | 2.8% | 1.9% | -0.047 / +0.394 | **SAYILMAZ_N<30** |
| Hacim sınıfı: yüksek çaba – zayıf sonuç | 9 / 411 | 33.3% | 31.3% | +2.0 | [—, —] | -12.8 / +21.1 | 2.3% | 1.5% | -0.075 / +0.413 | **SAYILMAZ_N<30** |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi † | 24 / 411 | 29.2% | 31.5% | -2.4 | [—, —] | -4.2 / +0.6 | 5.4% | 2.6% | -0.157 / +0.437 | **SAYILMAZ_N<30** |
| Dış piyasa yapısı işlemin tersinde | 0 / 411 | — | 31.4% | — | [—, —] | — / — | 0.0% | 0.0% | — / +0.402 | **SAYILMAZ_N<30** |
| İç piyasa yapısı işlemin tersinde | 7 / 411 | 28.6% | 31.4% | -2.9 | [—, —] | -12.8 / +20.9 | 1.6% | 1.5% | +0.198 / +0.406 | **SAYILMAZ_N<30** |
| Kapanış tez seviyesinin ters tarafında | 8 / 411 | 87.5% | 30.3% | +57.2 | [—, —] | +68.2 / +52.3 | 5.4% | 0.0% | -0.880 / +0.428 | **SAYILMAZ_N<30** |
| Formasyon girişten sonra aleyhte duruma geçti ve hâlâ orada (retest ediliyor / teyitsiz / başarısız / karşı kırılım) † | 22 / 411 | 22.7% | 31.9% | -9.1 | [—, —] | -16.7 / +0.6 | 3.9% | 4.6% | +0.238 / +0.412 | **SAYILMAZ_N<30** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 67 / 404 | 35.8% | 30.6% | +5.3 | [-8.3, +19.4] | +2.9 / +9.2 | 18.9% | 16.3% | +0.265 / +0.425 | **ZAYIF** |
| Eşik, girişten sonraki ilk mumda görüldü | 226 / 411 | 30.1% | 33.0% | -2.9 | [-13.2, +6.2] | -4.1 / -0.2 | 52.7% | 58.8% | +0.447 / +0.348 | **ZAYIF** |
| Stop uzaklığı en çok 1 ATR | 106 / 411 | 42.5% | 27.5% | +14.9 | [+3.1, +26.4] | +16.1 / +13.1 | 34.9% | 26.3% | +0.686 / +0.304 | **AYIRIYOR** |
| Girişte 20 günlük endeks rejimi işleme karşı | 144 / 411 | 28.5% | 33.0% | -4.5 | [-17.5, +8.7] | -4.6 / -4.1 | 31.8% | 32.5% | +0.450 / +0.377 | **ZAYIF** |

**0.5 ATR — o gözlem görülünce çıkılsaydı.** Karar eşik mumunun kapanışında verilir, çıkış bir sonraki mumun açılışındadır; masraf aynıdır. "Kümenin işlem başına R'si": gözlemin olmadığı işlemler değişmeden kalır. Kabul merdiveni endeks filtresi raporundakiyle aynıdır.

| Gözlem | Görüldüğü işlem | Çıkılsaydı, etkilenen işlem başına R | Kümenin işlem başına R'si | En kötü GA | Keşif / doğrulama | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---|
| Eşiği gören her işlem (karşılaştırma tabanı) | 411 | -0.099 | -0.0637 | [-0.1399, +0.0216] | -0.0258 / -0.1341 | -40.6 | **GECMEDI** |
| Eşik mumu bilinen bir karşı engele değdi, kapanışla aşamadı | 162 | -0.078 | -0.0199 | [-0.0651, +0.0252] | -0.0224 / -0.0154 | -12.7 | **GECMEDI** |
| … karşı Stabil seviyesine değip aşamadı | 13 | -0.054 | -0.0011 | [-0.0154, +0.0114] | +0.0001 / -0.0033 | -0.7 | **SAYILMAZ_N<30** |
| … karşı Market Structure seviyesine değip aşamadı | 90 | +0.085 | +0.0119 | [-0.0280, +0.0480] | +0.0056 / +0.0237 | +7.6 | **ZAYIF_ARTI** |
| … karşı OB / FVG bandına değip aşamadı | 107 | -0.167 | -0.0281 | [-0.0634, +0.0077] | -0.0263 / -0.0316 | -17.9 | **GECMEDI** |
| … … banda dışarıdan gelip takıldı † | 67 | -0.194 | -0.0204 | [-0.0464, +0.0104] | -0.0265 / -0.0091 | -13.0 | **GECMEDI** |
| … … önceki kapanışta zaten bandın içindeydi, çıkamadı † | 40 | -0.123 | -0.0077 | [-0.0294, +0.0151] | +0.0002 / -0.0225 | -4.9 | **GECMEDI** |
| Eşik mumu bir karşı engeli kapanışla aştı (takıldığı engel yok) | 60 | -0.134 | -0.0126 | [-0.0594, +0.0267] | +0.0070 / -0.0490 | -8.0 | **GECMEDI** |
| Kapanışın önünde en çok 0.5 ATR'de karşı engel var | 158 | -0.024 | -0.0061 | [-0.0523, +0.0441] | -0.0043 / -0.0094 | -3.9 | **GECMEDI** |
| Kapanış ile hedef arasında karşı engel var | 238 | -0.084 | -0.0315 | [-0.0931, +0.0284] | -0.0209 / -0.0513 | -20.1 | **GECMEDI** |
| Eşiği mum içinde gördü ama altında kapattı | 215 | -0.111 | -0.0375 | [-0.0943, +0.0195] | -0.0408 / -0.0312 | -23.9 | **GECMEDI** |
| Mum, aralığının en az yarısını geri verip kapattı | 128 | -0.038 | -0.0077 | [-0.0489, +0.0314] | -0.0075 / -0.0082 | -4.9 | **GECMEDI** |
| Göreli hacim 0.75'in altında | 44 | -0.162 | -0.0112 | [-0.0400, +0.0198] | +0.0009 / -0.0338 | -7.2 | **GECMEDI** |
| Göreli hacim en az 2 | 64 | +0.045 | +0.0045 | [-0.0257, +0.0298] | +0.0008 / +0.0115 | +2.9 | **ZAYIF_ARTI** |
| Hacim baskısı işlemin tersine (< −0.13) | 11 | -0.076 | -0.0013 | [-0.0115, +0.0085] | +0.0023 / -0.0081 | -0.8 | **SAYILMAZ_N<30** |
| Hacim sınıfı: yüksek çaba – zayıf sonuç | 9 | -0.328 | -0.0046 | [-0.0136, +0.0038] | -0.0037 / -0.0063 | -3.0 | **SAYILMAZ_N<30** |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi † | 24 | +0.021 | +0.0008 | [-0.0127, +0.0143] | +0.0054 / -0.0078 | +0.5 | **SAYILMAZ_N<30** |
| Dış piyasa yapısı işlemin tersinde | 0 | — | +0.0000 | [+0.0000, +0.0000] | +0.0000 / +0.0000 | +0.0 | **SAYILMAZ_N<30** |
| İç piyasa yapısı işlemin tersinde | 7 | -0.202 | -0.0022 | [-0.0087, +0.0033] | -0.0022 / -0.0022 | -1.4 | **SAYILMAZ_N<30** |
| Kapanış tez seviyesinin ters tarafında | 8 | +0.133 | +0.0017 | [-0.0048, +0.0069] | +0.0031 / -0.0010 | +1.1 | **SAYILMAZ_N<30** |
| Formasyon girişten sonra aleyhte duruma geçti ve hâlâ orada (retest ediliyor / teyitsiz / başarısız / karşı kırılım) † | 22 | -0.152 | -0.0053 | [-0.0193, +0.0084] | -0.0095 / +0.0027 | -3.4 | **SAYILMAZ_N<30** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 67 | -0.083 | -0.0088 | [-0.0379, +0.0207] | -0.0094 / -0.0075 | -5.6 | **GECMEDI** |
| Eşik, girişten sonraki ilk mumda görüldü | 226 | -0.132 | -0.0467 | [-0.1034, +0.0087] | -0.0219 / -0.0926 | -29.7 | **GECMEDI** |
| Stop uzaklığı en çok 1 ATR | 106 | -0.135 | -0.0224 | [-0.0783, +0.0356] | -0.0026 / -0.0594 | -14.3 | **GECMEDI** |
| Girişte 20 günlük endeks rejimi işleme karşı | 144 | -0.102 | -0.0231 | [-0.0701, +0.0234] | -0.0145 / -0.0390 | -14.7 | **GECMEDI** |

### 5. Eşik anı: 1 ATR ilk görüldüğü mumun kapanışında domainler

`293` işlem. "Varken stop": gözlem o kapanışta varsa işlemin sonradan stop olma oranı.

| Gözlem | Var (n) | Varken stop | Yokken stop | Fark (puan) | Fark en kötü GA | Keşif / doğrulama farkı | Stoplarda | Hedefe gidenlerde | Net R: var / yok | Karar |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| Eşik mumu bilinen bir karşı engele değdi, kapanışla aşamadı | 111 / 293 | 20.7% | 19.2% | +1.5 | [-10.7, +10.8] | -4.5 / +10.4 | 39.7% | 33.7% | +0.606 / +0.768 | **AYIRMIYOR** |
| … karşı Stabil seviyesine değip aşamadı | 10 / 293 | 10.0% | 20.1% | -10.1 | [—, —] | -5.7 / -20.4 | 1.7% | 3.1% | +0.837 / +0.702 | **SAYILMAZ_N<30** |
| … karşı Market Structure seviyesine değip aşamadı | 67 / 293 | 25.4% | 18.1% | +7.2 | [-8.7, +19.9] | +3.8 / +11.5 | 29.3% | 19.6% | +0.496 / +0.769 | **ZAYIF** |
| … karşı OB / FVG bandına değip aşamadı | 72 / 293 | 16.7% | 20.8% | -4.1 | [-15.1, +7.2] | -5.7 / -1.7 | 20.7% | 23.3% | +0.683 / +0.714 | **ZAYIF** |
| … … banda dışarıdan gelip takıldı † | 47 / 293 | 10.6% | 21.5% | -10.9 | [-20.6, +0.0] | -15.4 / -3.7 | 8.6% | 14.7% | +0.704 / +0.707 | **ZAYIF** |
| … … önceki kapanışta zaten bandın içindeydi, çıkamadı † | 25 / 293 | 28.0% | 19.0% | +9.0 | [—, —] | +12.6 / +2.6 | 12.1% | 8.6% | +0.642 / +0.712 | **SAYILMAZ_N<30** |
| Eşik mumu bir karşı engeli kapanışla aştı (takıldığı engel yok) | 48 / 293 | 18.8% | 20.0% | -1.2 | [-13.6, +12.7] | +1.1 / -4.8 | 15.5% | 17.2% | +0.731 / +0.701 | **AYIRMIYOR** |
| Kapanışın önünde en çok 0.5 ATR'de karşı engel var | 108 / 293 | 18.5% | 20.5% | -2.0 | [-12.5, +9.0] | -2.1 / -1.9 | 34.5% | 34.4% | +0.753 / +0.679 | **ZAYIF** |
| Kapanış ile hedef arasında karşı engel var | 150 / 293 | 20.0% | 19.6% | +0.4 | [-10.7, +10.8] | -2.3 / +4.6 | 51.7% | 45.4% | +0.656 / +0.759 | **AYIRMIYOR** |
| Eşiği mum içinde gördü ama altında kapattı | 165 / 293 | 23.0% | 15.6% | +7.4 | [-2.3, +17.4] | +6.0 / +9.6 | 65.5% | 47.9% | +0.495 / +0.979 | **ZAYIF** |
| Mum, aralığının en az yarısını geri verip kapattı | 88 / 293 | 33.0% | 14.1% | +18.8 | [+7.0, +30.5] | +20.3 / +16.6 | 50.0% | 19.6% | +0.156 / +0.942 | **AYIRIYOR** |
| Göreli hacim 0.75'in altında | 23 / 245 | 17.4% | 19.8% | -2.4 | [—, —] | -8.4 / +1.2 | 8.3% | 10.3% | +1.028 / +0.667 | **SAYILMAZ_N<30** |
| Göreli hacim en az 2 | 39 / 245 | 23.1% | 18.9% | +4.1 | [-10.7, +18.7] | -0.9 / +10.7 | 18.8% | 16.9% | +0.501 / +0.739 | **AYIRMIYOR** |
| Hacim baskısı işlemin tersine (< −0.13) | 11 / 245 | 36.4% | 18.8% | +17.6 | [—, —] | -19.7 / +48.9 | 8.3% | 2.9% | -0.026 / +0.735 | **SAYILMAZ_N<30** |
| Hacim sınıfı: yüksek çaba – zayıf sonuç | 2 / 293 | 50.0% | 19.6% | +30.4 | [—, —] | -19.9 / +80.9 | 1.7% | 0.0% | -0.524 / +0.715 | **SAYILMAZ_N<30** |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi † | 20 / 293 | 10.0% | 20.5% | -10.5 | [—, —] | -3.3 / -21.3 | 3.4% | 4.3% | +0.289 / +0.737 | **SAYILMAZ_N<30** |
| Dış piyasa yapısı işlemin tersinde | 0 / 293 | — | 19.8% | — | [—, —] | — / — | 0.0% | 0.0% | — / +0.706 | **SAYILMAZ_N<30** |
| İç piyasa yapısı işlemin tersinde | 4 / 293 | 25.0% | 19.7% | +5.3 | [—, —] | -20.0 / +30.7 | 1.7% | 1.8% | +0.639 / +0.707 | **SAYILMAZ_N<30** |
| Kapanış tez seviyesinin ters tarafında | 1 / 293 | 100.0% | 19.5% | +80.5 | [—, —] | — / +80.9 | 1.7% | 0.0% | -1.062 / +0.712 | **SAYILMAZ_N<30** |
| Formasyon girişten sonra aleyhte duruma geçti ve hâlâ orada (retest ediliyor / teyitsiz / başarısız / karşı kırılım) † | 18 / 293 | 0.0% | 21.1% | -21.1 | [—, —] | -21.0 / -21.3 | 0.0% | 5.5% | +0.579 / +0.715 | **SAYILMAZ_N<30** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 42 / 287 | 21.4% | 19.6% | +1.8 | [-13.4, +20.3] | -10.9 / +14.4 | 15.8% | 14.5% | +0.596 / +0.719 | **AYIRMIYOR** |
| Eşik, girişten sonraki ilk mumda görüldü | 84 / 293 | 25.0% | 17.7% | +7.3 | [-3.9, +18.6] | +1.5 / +15.6 | 36.2% | 32.5% | +0.650 / +0.729 | **ZAYIF** |
| Stop uzaklığı en çok 1 ATR | 67 / 293 | 23.9% | 18.6% | +5.3 | [-7.6, +17.4] | +6.0 / +4.2 | 27.6% | 26.4% | +1.339 / +0.519 | **ZAYIF** |
| Girişte 20 günlük endeks rejimi işleme karşı | 104 / 293 | 16.3% | 21.7% | -5.3 | [-15.7, +5.0] | -4.7 / -6.3 | 29.3% | 34.4% | +0.771 / +0.670 | **ZAYIF** |

**1 ATR — o gözlem görülünce çıkılsaydı.** Karar eşik mumunun kapanışında verilir, çıkış bir sonraki mumun açılışındadır; masraf aynıdır. "Kümenin işlem başına R'si": gözlemin olmadığı işlemler değişmeden kalır. Kabul merdiveni endeks filtresi raporundakiyle aynıdır.

| Gözlem | Görüldüğü işlem | Çıkılsaydı, etkilenen işlem başına R | Kümenin işlem başına R'si | En kötü GA | Keşif / doğrulama | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---|
| Eşiği gören her işlem (karşılaştırma tabanı) | 293 | -0.066 | -0.0304 | [-0.0886, +0.0290] | -0.0221 / -0.0459 | -19.4 | **GECMEDI** |
| Eşik mumu bilinen bir karşı engele değdi, kapanışla aşamadı | 111 | -0.072 | -0.0125 | [-0.0483, +0.0247] | -0.0170 / -0.0042 | -8.0 | **GECMEDI** |
| … karşı Stabil seviyesine değip aşamadı | 10 | -0.348 | -0.0055 | [-0.0190, +0.0044] | -0.0033 / -0.0096 | -3.5 | **SAYILMAZ_N<30** |
| … karşı Market Structure seviyesine değip aşamadı | 67 | -0.077 | -0.0081 | [-0.0406, +0.0227] | -0.0098 / -0.0049 | -5.1 | **GECMEDI** |
| … karşı OB / FVG bandına değip aşamadı | 72 | -0.102 | -0.0115 | [-0.0388, +0.0147] | -0.0110 / -0.0124 | -7.3 | **GECMEDI** |
| … … banda dışarıdan gelip takıldı † | 47 | -0.137 | -0.0101 | [-0.0308, +0.0140] | -0.0154 / -0.0004 | -6.5 | **GECMEDI** |
| … … önceki kapanışta zaten bandın içindeydi, çıkamadı † | 25 | -0.035 | -0.0014 | [-0.0174, +0.0144] | +0.0043 / -0.0120 | -0.9 | **SAYILMAZ_N<30** |
| Eşik mumu bir karşı engeli kapanışla aştı (takıldığı engel yok) | 48 | +0.177 | +0.0133 | [-0.0112, +0.0392] | +0.0145 / +0.0112 | +8.5 | **ZAYIF_ARTI** |
| Kapanışın önünde en çok 0.5 ATR'de karşı engel var | 108 | -0.083 | -0.0140 | [-0.0537, +0.0271] | -0.0168 / -0.0088 | -8.9 | **GECMEDI** |
| Kapanış ile hedef arasında karşı engel var | 150 | -0.078 | -0.0183 | [-0.0607, +0.0256] | -0.0170 / -0.0205 | -11.6 | **GECMEDI** |
| Eşiği mum içinde gördü ama altında kapattı | 165 | -0.159 | -0.0411 | [-0.0848, +0.0016] | -0.0342 / -0.0538 | -26.2 | **GECMEDI** |
| Mum, aralığının en az yarısını geri verip kapattı | 88 | +0.025 | +0.0035 | [-0.0283, +0.0341] | +0.0100 / -0.0085 | +2.2 | **GECMEDI** |
| Göreli hacim 0.75'in altında | 23 | -0.101 | -0.0037 | [-0.0216, +0.0159] | -0.0071 / +0.0027 | -2.3 | **SAYILMAZ_N<30** |
| Göreli hacim en az 2 | 39 | +0.077 | +0.0047 | [-0.0196, +0.0281] | +0.0023 / +0.0092 | +3.0 | **ZAYIF_ARTI** |
| Hacim baskısı işlemin tersine (< −0.13) | 11 | +0.091 | +0.0016 | [-0.0100, +0.0126] | -0.0038 / +0.0115 | +1.0 | **SAYILMAZ_N<30** |
| Hacim sınıfı: yüksek çaba – zayıf sonuç | 2 | +0.132 | +0.0004 | [+0.0000, +0.0013] | +0.0001 / +0.0010 | +0.3 | **SAYILMAZ_N<30** |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi † | 20 | -0.185 | -0.0058 | [-0.0196, +0.0076] | +0.0023 / -0.0208 | -3.7 | **SAYILMAZ_N<30** |
| Dış piyasa yapısı işlemin tersinde | 0 | — | +0.0000 | [+0.0000, +0.0000] | +0.0000 / +0.0000 | +0.0 | **SAYILMAZ_N<30** |
| İç piyasa yapısı işlemin tersinde | 4 | -0.468 | -0.0029 | [-0.0075, +0.0003] | -0.0033 / -0.0022 | -1.9 | **SAYILMAZ_N<30** |
| Kapanış tez seviyesinin ters tarafında | 1 | +0.224 | +0.0004 | [+0.0000, +0.0012] | +0.0000 / +0.0010 | +0.2 | **SAYILMAZ_N<30** |
| Formasyon girişten sonra aleyhte duruma geçti ve hâlâ orada (retest ediliyor / teyitsiz / başarısız / karşı kırılım) † | 18 | -0.256 | -0.0072 | [-0.0172, +0.0021] | -0.0096 / -0.0029 | -4.6 | **SAYILMAZ_N<30** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 42 | -0.084 | -0.0056 | [-0.0281, +0.0182] | -0.0140 / +0.0101 | -3.5 | **GECMEDI** |
| Eşik, girişten sonraki ilk mumda görüldü | 84 | +0.003 | +0.0004 | [-0.0291, +0.0308] | -0.0110 / +0.0216 | +0.3 | **GECMEDI** |
| Stop uzaklığı en çok 1 ATR | 67 | -0.146 | -0.0154 | [-0.0589, +0.0297] | -0.0089 / -0.0275 | -9.8 | **GECMEDI** |
| Girişte 20 günlük endeks rejimi işleme karşı | 104 | -0.089 | -0.0145 | [-0.0459, +0.0220] | -0.0072 / -0.0282 | -9.2 | **GECMEDI** |

### 6. Eşikten sonra: 0.5 ATR gördükten sonra çıkışa kadar görülen olaylar

Uzun yaşayan işlem daha çok olay görür; bu tablo olayları olduğundan kötü gösterir. "Stoplarda" ve "Hedefe gidenlerde" sütunlarını birlikte okuyun.

| Gözlem | Var (n) | Varken stop | Yokken stop | Fark (puan) | Fark en kötü GA | Keşif / doğrulama farkı | Stoplarda | Hedefe gidenlerde | Net R: var / yok |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Bir mum karşı engele değdi, kapanışla aşamadı | 216 / 411 | 30.1% | 32.8% | -2.7 | [-14.4, +7.4] | -8.7 / +7.6 | 50.4% | 44.3% | +0.291 / +0.527 |
| Eşik kapanışından çıkış mumuna endeks işlemin tersine en az %0.5 | 139 / 404 | 54.0% | 19.6% | +34.3 | [+18.4, +49.4] | +30.9 / +40.6 | 59.1% | 16.8% | -0.178 / +0.701 |
| Yapı bozulması (aşağıdaki dördünden en az biri) | 86 / 411 | 61.6% | 23.4% | +38.2 | [+23.1, +53.8] | +40.3 / +33.9 | 41.1% | 8.2% | -0.421 / +0.620 |
| … ters dış yapı kırılımı (BOS / CHoCH) | 0 / 411 | — | 31.4% | — | [—, —] | — / — | 0.0% | 0.0% | — / +0.402 |
| … ters iç yapı kırılımı (BOS / CHoCH) | 0 / 411 | — | 31.4% | — | [—, —] | — / — | 0.0% | 0.0% | — / +0.402 |
| … tez seviyesinin ters tarafında kapanış | 53 / 411 | 88.7% | 22.9% | +65.8 | [+54.4, +75.3] | +66.7 / +63.5 | 36.4% | 1.0% | -0.931 / +0.600 |
| … formasyon bozulması (retest / teyitsiz / başarısız / karşı kırılım) | 75 / 411 | 57.3% | 25.6% | +31.7 | [+15.1, +49.7] | +35.0 / +24.0 | 33.3% | 8.2% | -0.327 / +0.565 |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi | 79 / 411 | 45.6% | 28.0% | +17.6 | [+2.3, +33.0] | +19.2 / +14.8 | 27.9% | 8.2% | -0.219 / +0.550 |
| Ters hacim baskısı | 96 / 411 | 34.4% | 30.5% | +3.9 | [-5.9, +15.7] | +3.2 / +5.1 | 25.6% | 10.3% | -0.051 / +0.541 |

### 7. Eşikten sonra: 1 ATR gördükten sonra çıkışa kadar görülen olaylar

Uzun yaşayan işlem daha çok olay görür; bu tablo olayları olduğundan kötü gösterir. "Stoplarda" ve "Hedefe gidenlerde" sütunlarını birlikte okuyun.

| Gözlem | Var (n) | Varken stop | Yokken stop | Fark (puan) | Fark en kötü GA | Keşif / doğrulama farkı | Stoplarda | Hedefe gidenlerde | Net R: var / yok |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Bir mum karşı engele değdi, kapanışla aşamadı | 140 / 293 | 20.0% | 19.6% | +0.4 | [-10.8, +10.7] | -4.1 / +7.2 | 48.3% | 39.3% | +0.577 / +0.824 |
| Eşik kapanışından çıkış mumuna endeks işlemin tersine en az %0.5 | 97 / 287 | 40.2% | 9.5% | +30.7 | [+17.6, +43.7] | +28.6 / +34.2 | 68.4% | 18.9% | +0.155 / +0.980 |
| Yapı bozulması (aşağıdaki dördünden en az biri) | 31 / 293 | 61.3% | 14.9% | +46.4 | [+25.6, +72.1] | +44.9 / +50.8 | 32.8% | 3.1% | -0.504 / +0.849 |
| … ters dış yapı kırılımı (BOS / CHoCH) | 0 / 293 | — | 19.8% | — | [—, —] | — / — | 0.0% | 0.0% | — / +0.706 |
| … ters iç yapı kırılımı (BOS / CHoCH) | 0 / 293 | — | 19.8% | — | [—, —] | — / — | 0.0% | 0.0% | — / +0.706 |
| … tez seviyesinin ters tarafında kapanış | 20 / 293 | 95.0% | 14.3% | +80.7 | [—, —] | +79.4 / +84.5 | 32.8% | 0.6% | -1.032 / +0.834 |
| … formasyon bozulması (retest / teyitsiz / başarısız / karşı kırılım) | 26 / 293 | 53.8% | 16.5% | +37.4 | [—, —] | +36.8 / +39.7 | 24.1% | 3.1% | -0.332 / +0.807 |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi | 45 / 293 | 33.3% | 17.3% | +16.0 | [-0.7, +36.9] | +23.0 / +1.8 | 25.9% | 6.1% | -0.156 / +0.863 |
| Ters hacim baskısı | 59 / 293 | 23.7% | 18.8% | +4.9 | [-7.0, +17.9] | +0.3 / +11.8 | 24.1% | 9.2% | +0.137 / +0.850 |

### 8. Girişte hedef yolundaki engel (bütün küme)

Girişte bilinen en yakın karşı engelin uzaklığı; hedef 2 ATR'dedir.

| Girişte en yakın karşı engel | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Engel 1 ATR'den yakın | 371 | 42.3% | 24.3% | 18.1% | 52.8% | +0.125 | [-0.035, +0.291] | +0.074 (212) | +0.192 (159) |
| Engel 1–2 ATR arasında (hedeften önce) | 47 | 51.1% | 12.8% | 38.3% | 40.4% | -0.059 | [-0.454, +0.434] | -0.030 (38) | -0.181 (9) |
| Hedefe kadar engel yok | 219 | 45.2% | 25.1% | 20.1% | 49.3% | +0.135 | [-0.050, +0.329] | +0.049 (164) | +0.394 (55) |

## D6_A_Cekirdek_Veya_Arti — 1124 işlem, 504 stop

Stopların `274` tanesi stoptan önce 0.5 ATR'yi hiç görmedi (doğrudan / çok az yükselip düşen); `230` tanesi en az 0.5 ATR gördü; bunların `104` tanesi en az 1 ATR gördü.

### 1. Eşiği gören işlemlerin akıbeti

"Gören işlem": eşiği çıkış mumundan ÖNCE gören, yani o mumun kapanışında hâlâ açık olan işlem. Eşiği ilk kez çıkış mumunda gören işlemler (örneğin tek mumda hedefe giden) burada yoktur; o an verilecek bir karar olmadığı için.

| Eşik | Gören işlem | Stop oldu | Hedefe gitti | Süre doldu, kârda | Süre doldu, zararda | Grubun net R'si |
|---|---:|---:|---:|---:|---:|---:|
| 0.5 ATR | 718 (63.9%) | 230 (32.0%) | 328 (45.7%) | 96 (13.4%) | 64 (8.9%) | +0.328 |
| 1 ATR | 502 (44.7%) | 104 (20.7%) | 269 (53.6%) | 84 (16.7%) | 45 (9.0%) | +0.609 |

### 2. Tepeden stopa: 0.5 ATR görüp stop olanlarda ne görüldü

`230` işlem (keşif `154`, doğrulama `76`; long `125`, short `105`). "Kontrol" sütunu aynı tür olayın eşiği gören BÜTÜN işlemlerdeki karşılığıdır: olay eşikten sonra görülünce stop oranı / görülmeyince stop oranı. İki oran yakınsa o gözlem dönüşü açıklamaz.

| Gözlem | Görüldüğü işlem | Yalnız bu görüldü | Birincil gözlem (toplam %100) | Kontrol: görülünce stop / görülmeyince stop |
|---|---:|---:|---:|---:|
| Tepe mumu bilinen bir karşı seviyeye / banda değdi, kapanışla aşamadı | 109 (47.4%) | 17 | **109 (47.4%)** | 30.5% / 34.4% |
| Tepe, bilinen bir karşı seviyenin 0.25 ATR dibinde kaldı (değmedi) | 15 (6.5%) | 3 | **15 (6.5%)** | — |
| Tepe kapanışından stop mumuna endeks işlemin tersine en az %0.5 gitti | 136 (59.1%) | 28 | **60 (26.1%)** | 52.8% / 20.6% |
| Hissenin kendi yapısı bozuldu (ters BOS/CHoCH, tez seviyesinin içine kapanış ya da formasyon bozulması) | 99 (43.0%) | 6 | **17 (7.4%)** | 59.8% / 23.2% |
| Ters hacim baskısı ya da tepede yüksek çaba – zayıf sonuç | 69 (30.0%) | 5 | **6 (2.6%)** | 35.2% / 31.0% |
| Stop bir açılış boşluğuyla geldi | 19 (8.3%) | 3 | **3 (1.3%)** | — |
| Yukarıdakilerin hiçbiri görülmedi | 20 (8.7%) | 20 | **20 (8.7%)** | — |

- İki ya da daha çok gözlemin birlikte görüldüğü işlem: `148 (64.3%)`.
- Tepe mumunun takıldığı engel, alan alan (bir işlem birden çok alanda sayılabilir): Stabil `21 (9.1%)`; Market Structure `73 (31.7%)`; OB / FVG `63 (27.4%)`.
- OB / FVG ayrımı: banda dışarıdan gelip takılan `33 (14.3%)`; önceki kapanışta zaten bandın içinde olup çıkamayan `30 (13.0%)`. Engel gözlemi YALNIZ "zaten içinde olunan bant"tan gelen işlem: `15 (6.5%)`.
- Market Structure motorunun kendi olayı — ters süpürme / sahte kırılım: tepe mumunda `31 (13.5%)`; tepe mumundan stop öncesi son kapanışa `74 (32.2%)`.
- Yapı ayrıntısı (tepe mumundan stop öncesi son kapanışa): ters dış kırılım `0 (0.0%)`; ters iç kırılım `1 (0.4%)`; tez seviyesinin içine kapanış `82 (35.7%)`; formasyon bozulması `68 (29.6%)` (tepe mumunun kapanışında formasyon zaten aleyhte durumda olan `16 (7.0%)`).
- Hacim ayrıntısı: tepe ile stop arasında ters baskı `63 (27.4%)`; tepede yüksek çaba – zayıf sonuç `10 (4.3%)`; tepe mumunda düşük göreli hacim `22 (11.3%)` (hacmi bilinenler içinde).
- Tepe mumu aralığının en az yarısını geri verip kapattı (fitil): `144 (62.6%)`. Stop mumunun kendisinde ters yapı kırılımı: `13 (5.7%)` (düşüşün sonucu, habercisi değil).
- Stoptan önceki son kapanışta işlem hâlâ kârdaydı: `72 (31.3%)`.
- Tepeden stopa kaç mum: 1 mum `55 (23.9%)`; 2 mum `51 (22.2%)`; 3 mum `46 (20.0%)`; 4+ mum `78 (33.9%)`; medyan `3`.
- Tepeden stopa gereken geri çekilme: medyan `2.34 ATR`; en çok 1.5 ATR olan `15 (6.5%)`; 2 ATR'den büyük olan `159 (69.1%)`.

### 3. Tepeden stopa: 1 ATR görüp stop olanlarda ne görüldü

`104` işlem (keşif `65`, doğrulama `39`; long `56`, short `48`). "Kontrol" sütunu aynı tür olayın eşiği gören BÜTÜN işlemlerdeki karşılığıdır: olay eşikten sonra görülünce stop oranı / görülmeyince stop oranı. İki oran yakınsa o gözlem dönüşü açıklamaz.

| Gözlem | Görüldüğü işlem | Yalnız bu görüldü | Birincil gözlem (toplam %100) | Kontrol: görülünce stop / görülmeyince stop |
|---|---:|---:|---:|---:|
| Tepe mumu bilinen bir karşı seviyeye / banda değdi, kapanışla aşamadı | 53 (51.0%) | 9 | **53 (51.0%)** | 20.9% / 20.5% |
| Tepe, bilinen bir karşı seviyenin 0.25 ATR dibinde kaldı (değmedi) | 5 (4.8%) | 1 | **5 (4.8%)** | — |
| Tepe kapanışından stop mumuna endeks işlemin tersine en az %0.5 gitti | 67 (64.4%) | 19 | **32 (30.8%)** | 38.9% / 11.3% |
| Hissenin kendi yapısı bozuldu (ters BOS/CHoCH, tez seviyesinin içine kapanış ya da formasyon bozulması) | 38 (36.5%) | 1 | **4 (3.8%)** | 55.1% / 15.2% |
| Ters hacim baskısı ya da tepede yüksek çaba – zayıf sonuç | 35 (33.7%) | 0 | **1 (1.0%)** | 26.1% / 19.1% |
| Stop bir açılış boşluğuyla geldi | 11 (10.6%) | 1 | **1 (1.0%)** | — |
| Yukarıdakilerin hiçbiri görülmedi | 8 (7.7%) | 8 | **8 (7.7%)** | — |

- İki ya da daha çok gözlemin birlikte görüldüğü işlem: `65 (62.5%)`.
- Tepe mumunun takıldığı engel, alan alan (bir işlem birden çok alanda sayılabilir): Stabil `7 (6.7%)`; Market Structure `38 (36.5%)`; OB / FVG `29 (27.9%)`.
- OB / FVG ayrımı: banda dışarıdan gelip takılan `16 (15.4%)`; önceki kapanışta zaten bandın içinde olup çıkamayan `13 (12.5%)`. Engel gözlemi YALNIZ "zaten içinde olunan bant"tan gelen işlem: `8 (7.7%)`.
- Market Structure motorunun kendi olayı — ters süpürme / sahte kırılım: tepe mumunda `14 (13.5%)`; tepe mumundan stop öncesi son kapanışa `35 (33.7%)`.
- Yapı ayrıntısı (tepe mumundan stop öncesi son kapanışa): ters dış kırılım `0 (0.0%)`; ters iç kırılım `0 (0.0%)`; tez seviyesinin içine kapanış `33 (31.7%)`; formasyon bozulması `25 (24.0%)` (tepe mumunun kapanışında formasyon zaten aleyhte durumda olan `2 (1.9%)`).
- Hacim ayrıntısı: tepe ile stop arasında ters baskı `31 (29.8%)`; tepede yüksek çaba – zayıf sonuç `7 (6.7%)`; tepe mumunda düşük göreli hacim `9 (10.1%)` (hacmi bilinenler içinde).
- Tepe mumu aralığının en az yarısını geri verip kapattı (fitil): `70 (67.3%)`. Stop mumunun kendisinde ters yapı kırılımı: `8 (7.7%)` (düşüşün sonucu, habercisi değil).
- Stoptan önceki son kapanışta işlem hâlâ kârdaydı: `36 (34.6%)`.
- Tepeden stopa kaç mum: 1 mum `21 (20.2%)`; 2 mum `22 (21.2%)`; 3 mum `22 (21.2%)`; 4+ mum `39 (37.5%)`; medyan `3`.
- Tepeden stopa gereken geri çekilme: medyan `2.66 ATR`; en çok 1.5 ATR olan `0 (0.0%)`; 2 ATR'den büyük olan `100 (96.2%)`.

### 4. Eşik anı: 0.5 ATR ilk görüldüğü mumun kapanışında domainler

`718` işlem. "Varken stop": gözlem o kapanışta varsa işlemin sonradan stop olma oranı.

| Gözlem | Var (n) | Varken stop | Yokken stop | Fark (puan) | Fark en kötü GA | Keşif / doğrulama farkı | Stoplarda | Hedefe gidenlerde | Net R: var / yok | Karar |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| Eşik mumu bilinen bir karşı engele değdi, kapanışla aşamadı | 335 / 718 | 32.5% | 31.6% | +0.9 | [-7.1, +9.7] | -4.3 / +11.0 | 47.4% | 44.5% | +0.240 / +0.406 | **AYIRMIYOR** |
| … karşı Stabil seviyesine değip aşamadı | 44 / 718 | 47.7% | 31.0% | +16.7 | [+0.0, +32.7] | +14.5 / +21.1 | 9.1% | 4.0% | -0.121 / +0.358 | **AYIRIYOR** |
| … karşı Market Structure seviyesine değip aşamadı | 192 / 718 | 37.0% | 30.2% | +6.8 | [-4.2, +17.7] | +3.9 / +12.1 | 30.9% | 23.2% | +0.091 / +0.415 | **ZAYIF** |
| … karşı OB / FVG bandına değip aşamadı | 225 / 718 | 29.3% | 33.3% | -3.9 | [-12.4, +5.1] | -7.7 / +3.0 | 28.7% | 32.6% | +0.339 / +0.323 | **AYIRMIYOR** |
| … … banda dışarıdan gelip takıldı † | 137 / 718 | 28.5% | 32.9% | -4.4 | [-13.6, +4.6] | -5.4 / -2.5 | 17.0% | 21.6% | +0.393 / +0.313 | **ZAYIF** |
| … … önceki kapanışta zaten bandın içindeydi, çıkamadı † | 88 / 718 | 30.7% | 32.2% | -1.5 | [-12.8, +10.6] | -7.8 / +9.9 | 11.7% | 11.0% | +0.255 / +0.339 | **AYIRMIYOR** |
| Eşik mumu bir karşı engeli kapanışla aştı (takıldığı engel yok) | 99 / 718 | 22.2% | 33.6% | -11.4 | [-21.2, -0.4] | -4.9 / -20.8 | 9.6% | 16.5% | +0.648 / +0.277 | **AYIRIYOR** |
| Kapanışın önünde en çok 0.5 ATR'de karşı engel var | 328 / 718 | 31.4% | 32.6% | -1.2 | [-7.6, +5.7] | -3.2 / +3.2 | 44.8% | 44.5% | +0.316 / +0.339 | **AYIRMIYOR** |
| Kapanış ile hedef arasında karşı engel var | 473 / 718 | 33.0% | 30.2% | +2.8 | [-4.6, +10.2] | +1.5 / +6.5 | 67.8% | 62.8% | +0.288 / +0.407 | **ZAYIF** |
| Eşiği mum içinde gördü ama altında kapattı | 383 / 718 | 41.0% | 21.8% | +19.2 | [+11.9, +26.0] | +17.1 / +23.2 | 68.3% | 41.5% | +0.046 / +0.651 | **AYIRIYOR** |
| Mum, aralığının en az yarısını geri verip kapattı | 241 / 718 | 44.4% | 25.8% | +18.6 | [+9.8, +27.5] | +18.3 / +19.2 | 46.5% | 22.9% | -0.110 / +0.550 | **AYIRIYOR** |
| Göreli hacim 0.75'in altında | 85 / 604 | 30.6% | 32.6% | -2.0 | [-12.4, +9.3] | +1.7 / -6.5 | 13.3% | 15.8% | +0.453 / +0.275 | **AYIRMIYOR** |
| Göreli hacim en az 2 | 114 / 604 | 33.3% | 32.0% | +1.3 | [-10.6, +14.7] | -3.3 / +7.7 | 19.5% | 20.2% | +0.200 / +0.324 | **AYIRMIYOR** |
| Hacim baskısı işlemin tersine (< −0.13) | 24 / 604 | 37.5% | 32.1% | +5.4 | [—, —] | +6.3 / +3.6 | 4.6% | 1.5% | -0.250 / +0.323 | **SAYILMAZ_N<30** |
| Hacim sınıfı: yüksek çaba – zayıf sonuç | 17 / 718 | 52.9% | 31.5% | +21.4 | [—, —] | +21.9 / +20.4 | 3.9% | 0.9% | -0.493 / +0.348 | **SAYILMAZ_N<30** |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi † | 63 / 718 | 42.9% | 31.0% | +11.9 | [-3.5, +25.5] | +16.9 / +5.1 | 11.7% | 4.0% | -0.281 / +0.387 | **ZAYIF** |
| Dış piyasa yapısı işlemin tersinde | 0 / 718 | — | 32.0% | — | [—, —] | — / — | 0.0% | 0.0% | — / +0.328 | **SAYILMAZ_N<30** |
| İç piyasa yapısı işlemin tersinde | 31 / 718 | 35.5% | 31.9% | +3.6 | [-15.3, +23.7] | +1.8 / +7.7 | 4.8% | 4.3% | +0.211 / +0.334 | **ZAYIF** |
| Kapanış tez seviyesinin ters tarafında | 16 / 718 | 87.5% | 30.8% | +56.7 | [—, —] | +56.9 / +57.3 | 6.1% | 0.3% | -0.837 / +0.355 | **SAYILMAZ_N<30** |
| Formasyon girişten sonra aleyhte duruma geçti ve hâlâ orada (retest ediliyor / teyitsiz / başarısız / karşı kırılım) † | 53 / 718 | 18.9% | 33.1% | -14.2 | [-25.2, -1.3] | -18.2 / -8.0 | 4.3% | 7.0% | +0.267 / +0.333 | **AYIRIYOR** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 116 / 707 | 37.1% | 30.8% | +6.3 | [-5.3, +16.4] | +4.6 / +9.6 | 19.1% | 16.4% | +0.208 / +0.354 | **ZAYIF** |
| Eşik, girişten sonraki ilk mumda görüldü | 372 / 718 | 32.0% | 32.1% | -0.1 | [-7.9, +6.9] | +2.2 / -3.9 | 51.7% | 56.4% | +0.380 / +0.273 | **AYIRMIYOR** |
| Stop uzaklığı en çok 1 ATR | 144 / 718 | 42.4% | 29.4% | +12.9 | [+3.4, +22.7] | +14.0 / +11.3 | 26.5% | 20.1% | +0.594 / +0.262 | **AYIRIYOR** |
| Girişte 20 günlük endeks rejimi işleme karşı | 267 / 718 | 30.3% | 33.0% | -2.7 | [-11.9, +8.1] | -2.1 / -3.8 | 35.2% | 34.8% | +0.334 / +0.325 | **ZAYIF** |

**0.5 ATR — o gözlem görülünce çıkılsaydı.** Karar eşik mumunun kapanışında verilir, çıkış bir sonraki mumun açılışındadır; masraf aynıdır. "Kümenin işlem başına R'si": gözlemin olmadığı işlemler değişmeden kalır. Kabul merdiveni endeks filtresi raporundakiyle aynıdır.

| Gözlem | Görüldüğü işlem | Çıkılsaydı, etkilenen işlem başına R | Kümenin işlem başına R'si | En kötü GA | Keşif / doğrulama | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---|
| Eşiği gören her işlem (karşılaştırma tabanı) | 718 | -0.050 | -0.0322 | [-0.1075, +0.0501] | -0.0094 / -0.0760 | -36.2 | **GECMEDI** |
| Eşik mumu bilinen bir karşı engele değdi, kapanışla aşamadı | 335 | -0.037 | -0.0109 | [-0.0540, +0.0297] | -0.0131 / -0.0066 | -12.2 | **GECMEDI** |
| … karşı Stabil seviyesine değip aşamadı | 44 | +0.204 | +0.0080 | [-0.0083, +0.0221] | +0.0123 / -0.0003 | +9.0 | **GECMEDI** |
| … karşı Market Structure seviyesine değip aşamadı | 192 | +0.049 | +0.0083 | [-0.0250, +0.0377] | +0.0111 / +0.0030 | +9.3 | **ZAYIF_ARTI** |
| … karşı OB / FVG bandına değip aşamadı | 225 | -0.097 | -0.0194 | [-0.0502, +0.0128] | -0.0206 / -0.0173 | -21.8 | **GECMEDI** |
| … … banda dışarıdan gelip takıldı † | 137 | -0.121 | -0.0148 | [-0.0368, +0.0091] | -0.0122 / -0.0198 | -16.6 | **GECMEDI** |
| … … önceki kapanışta zaten bandın içindeydi, çıkamadı † | 88 | -0.059 | -0.0047 | [-0.0235, +0.0130] | -0.0084 / +0.0025 | -5.2 | **GECMEDI** |
| Eşik mumu bir karşı engeli kapanışla aştı (takıldığı engel yok) | 99 | -0.046 | -0.0040 | [-0.0323, +0.0178] | +0.0109 / -0.0325 | -4.5 | **GECMEDI** |
| Kapanışın önünde en çok 0.5 ATR'de karşı engel var | 328 | -0.025 | -0.0074 | [-0.0503, +0.0368] | -0.0036 / -0.0147 | -8.4 | **GECMEDI** |
| Kapanış ile hedef arasında karşı engel var | 473 | -0.060 | -0.0253 | [-0.0889, +0.0404] | -0.0190 / -0.0374 | -28.5 | **GECMEDI** |
| Eşiği mum içinde gördü ama altında kapattı | 383 | -0.074 | -0.0251 | [-0.0730, +0.0190] | -0.0245 / -0.0263 | -28.2 | **GECMEDI** |
| Mum, aralığının en az yarısını geri verip kapattı | 241 | -0.003 | -0.0007 | [-0.0314, +0.0278] | -0.0002 / -0.0018 | -0.8 | **GECMEDI** |
| Göreli hacim 0.75'in altında | 85 | -0.200 | -0.0151 | [-0.0352, +0.0088] | -0.0046 / -0.0351 | -17.0 | **GECMEDI** |
| Göreli hacim en az 2 | 114 | +0.033 | +0.0033 | [-0.0211, +0.0248] | -0.0013 / +0.0123 | +3.8 | **GECMEDI** |
| Hacim baskısı işlemin tersine (< −0.13) | 24 | +0.035 | +0.0007 | [-0.0060, +0.0076] | +0.0034 / -0.0044 | +0.8 | **SAYILMAZ_N<30** |
| Hacim sınıfı: yüksek çaba – zayıf sonuç | 17 | -0.010 | -0.0001 | [-0.0059, +0.0054] | +0.0012 / -0.0028 | -0.2 | **SAYILMAZ_N<30** |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi † | 63 | +0.152 | +0.0085 | [-0.0038, +0.0211] | +0.0146 / -0.0031 | +9.6 | **GECMEDI** |
| Dış piyasa yapısı işlemin tersinde | 0 | — | +0.0000 | [+0.0000, +0.0000] | +0.0000 / +0.0000 | +0.0 | **SAYILMAZ_N<30** |
| İç piyasa yapısı işlemin tersinde | 31 | -0.189 | -0.0052 | [-0.0164, +0.0043] | -0.0050 / -0.0056 | -5.9 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 16 | +0.064 | +0.0009 | [-0.0060, +0.0062] | +0.0001 / +0.0025 | +1.0 | **SAYILMAZ_N<30** |
| Formasyon girişten sonra aleyhte duruma geçti ve hâlâ orada (retest ediliyor / teyitsiz / başarısız / karşı kırılım) † | 53 | -0.112 | -0.0053 | [-0.0177, +0.0084] | -0.0053 / -0.0053 | -6.0 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 116 | -0.041 | -0.0042 | [-0.0241, +0.0166] | -0.0044 / -0.0038 | -4.7 | **GECMEDI** |
| Eşik, girişten sonraki ilk mumda görüldü | 372 | -0.089 | -0.0296 | [-0.0857, +0.0256] | -0.0091 / -0.0688 | -33.2 | **GECMEDI** |
| Stop uzaklığı en çok 1 ATR | 144 | -0.087 | -0.0111 | [-0.0484, +0.0281] | +0.0043 / -0.0406 | -12.5 | **GECMEDI** |
| Girişte 20 günlük endeks rejimi işleme karşı | 267 | -0.022 | -0.0052 | [-0.0472, +0.0394] | +0.0013 / -0.0176 | -5.8 | **GECMEDI** |

### 5. Eşik anı: 1 ATR ilk görüldüğü mumun kapanışında domainler

`502` işlem. "Varken stop": gözlem o kapanışta varsa işlemin sonradan stop olma oranı.

| Gözlem | Var (n) | Varken stop | Yokken stop | Fark (puan) | Fark en kötü GA | Keşif / doğrulama farkı | Stoplarda | Hedefe gidenlerde | Net R: var / yok | Karar |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| Eşik mumu bilinen bir karşı engele değdi, kapanışla aşamadı | 228 / 502 | 22.4% | 19.3% | +3.0 | [-5.8, +11.0] | -0.5 / +8.9 | 49.0% | 43.5% | +0.556 / +0.653 | **AYIRMIYOR** |
| … karşı Stabil seviyesine değip aşamadı | 31 / 502 | 25.8% | 20.4% | +5.4 | [-9.8, +21.4] | +8.1 / -4.4 | 7.7% | 5.2% | +0.445 / +0.620 | **AYIRMIYOR** |
| … karşı Market Structure seviyesine değip aşamadı | 139 / 502 | 25.2% | 19.0% | +6.2 | [-4.8, +15.0] | +3.9 / +9.6 | 33.7% | 25.7% | +0.459 / +0.666 | **ZAYIF** |
| … karşı OB / FVG bandına değip aşamadı | 147 / 502 | 20.4% | 20.8% | -0.4 | [-8.9, +7.3] | -0.2 / -0.9 | 28.8% | 28.3% | +0.595 / +0.615 | **ZAYIF** |
| … … banda dışarıdan gelip takıldı † | 91 / 502 | 19.8% | 20.9% | -1.1 | [-12.0, +9.3] | -2.0 / +0.1 | 17.3% | 16.0% | +0.536 / +0.625 | **AYIRMIYOR** |
| … … önceki kapanışta zaten bandın içindeydi, çıkamadı † | 56 / 502 | 21.4% | 20.6% | +0.8 | [-11.9, +15.5] | +2.6 / -2.2 | 11.5% | 12.3% | +0.691 / +0.599 | **AYIRMIYOR** |
| Eşik mumu bir karşı engeli kapanışla aştı (takıldığı engel yok) | 82 / 502 | 17.1% | 21.4% | -4.4 | [-14.0, +5.6] | -0.7 / -11.5 | 13.5% | 16.4% | +0.600 / +0.611 | **ZAYIF** |
| Kapanışın önünde en çok 0.5 ATR'de karşı engel var | 218 / 502 | 18.8% | 22.2% | -3.4 | [-11.0, +4.1] | -1.8 / -6.1 | 39.4% | 43.1% | +0.669 / +0.563 | **ZAYIF** |
| Kapanış ile hedef arasında karşı engel var | 298 / 502 | 20.8% | 20.6% | +0.2 | [-9.4, +9.7] | -2.1 / +4.3 | 59.6% | 56.1% | +0.582 / +0.648 | **AYIRMIYOR** |
| Eşiği mum içinde gördü ama altında kapattı | 292 / 502 | 26.7% | 12.4% | +14.3 | [+6.9, +21.0] | +16.2 / +11.1 | 75.0% | 46.8% | +0.360 / +0.955 | **AYIRIYOR** |
| Mum, aralığının en az yarısını geri verip kapattı | 163 / 502 | 33.1% | 14.7% | +18.4 | [+9.0, +27.7] | +20.9 / +14.0 | 51.9% | 21.2% | +0.114 / +0.847 | **AYIRIYOR** |
| Göreli hacim 0.75'in altında | 54 / 424 | 14.8% | 21.9% | -7.1 | [-18.5, +5.4] | -7.9 / -6.2 | 9.0% | 14.7% | +0.849 / +0.539 | **ZAYIF** |
| Göreli hacim en az 2 | 76 / 424 | 23.7% | 20.4% | +3.3 | [-6.3, +14.6] | +5.2 / +0.7 | 20.2% | 19.6% | +0.477 / +0.601 | **ZAYIF** |
| Hacim baskısı işlemin tersine (< −0.13) | 18 / 424 | 44.4% | 20.0% | +24.5 | [—, —] | +20.1 / +30.0 | 9.0% | 1.8% | -0.304 / +0.618 | **SAYILMAZ_N<30** |
| Hacim sınıfı: yüksek çaba – zayıf sonuç | 10 / 502 | 50.0% | 20.1% | +29.9 | [—, —] | +30.2 / +29.3 | 4.8% | 0.7% | -0.524 / +0.632 | **SAYILMAZ_N<30** |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi † | 51 / 502 | 25.5% | 20.2% | +5.3 | [-9.6, +21.5] | +12.2 / -9.3 | 12.5% | 6.3% | +0.198 / +0.655 | **AYIRMIYOR** |
| Dış piyasa yapısı işlemin tersinde | 0 / 502 | — | 20.7% | — | [—, —] | — / — | 0.0% | 0.0% | — / +0.609 | **SAYILMAZ_N<30** |
| İç piyasa yapısı işlemin tersinde | 19 / 502 | 26.3% | 20.5% | +5.8 | [—, —] | -0.6 / +29.7 | 4.8% | 4.5% | +0.619 / +0.608 | **SAYILMAZ_N<30** |
| Kapanış tez seviyesinin ters tarafında | 4 / 502 | 100.0% | 20.1% | +79.9 | [—, —] | +80.2 / +79.5 | 3.8% | 0.0% | -1.048 / +0.622 | **SAYILMAZ_N<30** |
| Formasyon girişten sonra aleyhte duruma geçti ve hâlâ orada (retest ediliyor / teyitsiz / başarısız / karşı kırılım) † | 45 / 502 | 4.4% | 22.3% | -17.9 | [-24.6, -8.2] | -18.0 / -17.9 | 1.9% | 9.3% | +0.610 / +0.609 | **AYIRIYOR** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 72 / 494 | 22.2% | 20.4% | +1.8 | [-10.2, +13.9] | -5.9 / +11.6 | 15.7% | 14.8% | +0.612 / +0.605 | **AYIRMIYOR** |
| Eşik, girişten sonraki ilk mumda görüldü | 125 / 502 | 27.2% | 18.6% | +8.6 | [-0.8, +17.5] | +8.9 / +8.2 | 32.7% | 27.5% | +0.535 / +0.633 | **ZAYIF** |
| Stop uzaklığı en çok 1 ATR | 91 / 502 | 23.1% | 20.2% | +2.9 | [-8.4, +15.1] | +1.0 / +5.8 | 20.2% | 20.8% | +1.214 / +0.475 | **ZAYIF** |
| Girişte 20 günlük endeks rejimi işleme karşı | 187 / 502 | 17.1% | 22.9% | -5.7 | [-14.2, +4.4] | -5.8 / -5.7 | 30.8% | 37.2% | +0.667 / +0.575 | **ZAYIF** |

**1 ATR — o gözlem görülünce çıkılsaydı.** Karar eşik mumunun kapanışında verilir, çıkış bir sonraki mumun açılışındadır; masraf aynıdır. "Kümenin işlem başına R'si": gözlemin olmadığı işlemler değişmeden kalır. Kabul merdiveni endeks filtresi raporundakiyle aynıdır.

| Gözlem | Görüldüğü işlem | Çıkılsaydı, etkilenen işlem başına R | Kümenin işlem başına R'si | En kötü GA | Keşif / doğrulama | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---|
| Eşiği gören her işlem (karşılaştırma tabanı) | 502 | -0.006 | -0.0028 | [-0.0555, +0.0454] | -0.0049 / +0.0014 | -3.1 | **GECMEDI** |
| Eşik mumu bilinen bir karşı engele değdi, kapanışla aşamadı | 228 | -0.017 | -0.0034 | [-0.0423, +0.0332] | -0.0081 / +0.0056 | -3.8 | **GECMEDI** |
| … karşı Stabil seviyesine değip aşamadı | 31 | -0.066 | -0.0018 | [-0.0191, +0.0117] | -0.0005 / -0.0042 | -2.0 | **GECMEDI** |
| … karşı Market Structure seviyesine değip aşamadı | 139 | -0.050 | -0.0062 | [-0.0372, +0.0245] | -0.0053 / -0.0079 | -7.0 | **GECMEDI** |
| … karşı OB / FVG bandına değip aşamadı | 147 | -0.019 | -0.0025 | [-0.0241, +0.0194] | -0.0035 / -0.0006 | -2.9 | **GECMEDI** |
| … … banda dışarıdan gelip takıldı † | 91 | +0.005 | +0.0004 | [-0.0184, +0.0183] | -0.0035 / +0.0079 | +0.5 | **GECMEDI** |
| … … önceki kapanışta zaten bandın içindeydi, çıkamadı † | 56 | -0.059 | -0.0030 | [-0.0179, +0.0102] | -0.0001 / -0.0085 | -3.3 | **GECMEDI** |
| Eşik mumu bir karşı engeli kapanışla aştı (takıldığı engel yok) | 82 | +0.188 | +0.0137 | [-0.0032, +0.0313] | +0.0146 / +0.0121 | +15.4 | **ZAYIF_ARTI** |
| Kapanışın önünde en çok 0.5 ATR'de karşı engel var | 218 | -0.026 | -0.0051 | [-0.0415, +0.0284] | -0.0045 / -0.0062 | -5.7 | **GECMEDI** |
| Kapanış ile hedef arasında karşı engel var | 298 | -0.023 | -0.0061 | [-0.0497, +0.0347] | -0.0118 / +0.0049 | -6.8 | **GECMEDI** |
| Eşiği mum içinde gördü ama altında kapattı | 292 | -0.050 | -0.0130 | [-0.0539, +0.0239] | -0.0088 / -0.0209 | -14.6 | **GECMEDI** |
| Mum, aralığının en az yarısını geri verip kapattı | 163 | +0.041 | +0.0060 | [-0.0203, +0.0307] | +0.0104 / -0.0025 | +6.8 | **GECMEDI** |
| Göreli hacim 0.75'in altında | 54 | +0.007 | +0.0003 | [-0.0156, +0.0162] | +0.0053 / -0.0092 | +0.4 | **GECMEDI** |
| Göreli hacim en az 2 | 76 | -0.009 | -0.0006 | [-0.0174, +0.0155] | -0.0021 / +0.0022 | -0.7 | **GECMEDI** |
| Hacim baskısı işlemin tersine (< −0.13) | 18 | +0.215 | +0.0034 | [-0.0027, +0.0108] | +0.0018 / +0.0066 | +3.9 | **SAYILMAZ_N<30** |
| Hacim sınıfı: yüksek çaba – zayıf sonuç | 10 | +0.112 | +0.0010 | [-0.0019, +0.0037] | +0.0009 / +0.0012 | +1.1 | **SAYILMAZ_N<30** |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi † | 51 | -0.132 | -0.0060 | [-0.0192, +0.0082] | -0.0025 / -0.0126 | -6.7 | **GECMEDI** |
| Dış piyasa yapısı işlemin tersinde | 0 | — | +0.0000 | [+0.0000, +0.0000] | +0.0000 / +0.0000 | +0.0 | **SAYILMAZ_N<30** |
| İç piyasa yapısı işlemin tersinde | 19 | -0.338 | -0.0057 | [-0.0125, +0.0006] | -0.0069 / -0.0035 | -6.4 | **SAYILMAZ_N<30** |
| Kapanış tez seviyesinin ters tarafında | 4 | +0.192 | +0.0007 | [+0.0000, +0.0016] | +0.0007 / +0.0006 | +0.8 | **SAYILMAZ_N<30** |
| Formasyon girişten sonra aleyhte duruma geçti ve hâlâ orada (retest ediliyor / teyitsiz / başarısız / karşı kırılım) † | 45 | -0.194 | -0.0078 | [-0.0183, +0.0036] | -0.0078 / -0.0077 | -8.7 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 72 | -0.133 | -0.0085 | [-0.0246, +0.0084] | -0.0151 / +0.0041 | -9.6 | **GECMEDI** |
| Eşik, girişten sonraki ilk mumda görüldü | 125 | +0.071 | +0.0079 | [-0.0164, +0.0310] | +0.0010 / +0.0212 | +8.9 | **ZAYIF_ARTI** |
| Stop uzaklığı en çok 1 ATR | 91 | -0.113 | -0.0092 | [-0.0390, +0.0210] | -0.0052 / -0.0167 | -10.3 | **GECMEDI** |
| Girişte 20 günlük endeks rejimi işleme karşı | 187 | -0.008 | -0.0012 | [-0.0265, +0.0255] | +0.0042 / -0.0116 | -1.4 | **GECMEDI** |

### 6. Eşikten sonra: 0.5 ATR gördükten sonra çıkışa kadar görülen olaylar

Uzun yaşayan işlem daha çok olay görür; bu tablo olayları olduğundan kötü gösterir. "Stoplarda" ve "Hedefe gidenlerde" sütunlarını birlikte okuyun.

| Gözlem | Var (n) | Varken stop | Yokken stop | Fark (puan) | Fark en kötü GA | Keşif / doğrulama farkı | Stoplarda | Hedefe gidenlerde | Net R: var / yok |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Bir mum karşı engele değdi, kapanışla aşamadı | 433 / 718 | 30.5% | 34.4% | -3.9 | [-12.5, +3.9] | -8.9 / +6.2 | 57.4% | 54.0% | +0.257 / +0.437 |
| Eşik kapanışından çıkış mumuna endeks işlemin tersine en az %0.5 | 246 / 707 | 52.8% | 20.6% | +32.2 | [+23.7, +40.8] | +30.5 / +35.6 | 57.8% | 17.3% | -0.235 / +0.631 |
| Yapı bozulması (aşağıdaki dördünden en az biri) | 174 / 718 | 59.8% | 23.2% | +36.6 | [+24.5, +48.0] | +40.3 / +29.2 | 45.2% | 11.0% | -0.400 / +0.561 |
| … ters dış yapı kırılımı (BOS / CHoCH) | 0 / 718 | — | 32.0% | — | [—, —] | — / — | 0.0% | 0.0% | — / +0.328 |
| … ters iç yapı kırılımı (BOS / CHoCH) | 1 / 718 | 100.0% | 31.9% | +68.1 | [—, —] | +67.0 / — | 0.4% | 0.0% | -1.141 / +0.330 |
| … tez seviyesinin ters tarafında kapanış | 97 / 718 | 85.6% | 23.7% | +61.9 | [+52.7, +70.2] | +63.4 / +58.6 | 36.1% | 0.9% | -0.907 / +0.521 |
| … formasyon bozulması (retest / teyitsiz / başarısız / karşı kırılım) | 141 / 718 | 51.8% | 27.2% | +24.6 | [+11.4, +36.7] | +28.5 / +15.9 | 31.7% | 11.0% | -0.240 / +0.467 |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi | 178 / 718 | 43.3% | 28.3% | +14.9 | [+5.2, +24.7] | +14.5 / +15.8 | 33.5% | 13.4% | -0.149 / +0.486 |
| Ters hacim baskısı | 179 / 718 | 35.2% | 31.0% | +4.2 | [-4.3, +13.1] | +3.5 / +5.9 | 27.4% | 9.5% | -0.150 / +0.487 |

### 7. Eşikten sonra: 1 ATR gördükten sonra çıkışa kadar görülen olaylar

Uzun yaşayan işlem daha çok olay görür; bu tablo olayları olduğundan kötü gösterir. "Stoplarda" ve "Hedefe gidenlerde" sütunlarını birlikte okuyun.

| Gözlem | Var (n) | Varken stop | Yokken stop | Fark (puan) | Fark en kötü GA | Keşif / doğrulama farkı | Stoplarda | Hedefe gidenlerde | Net R: var / yok |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Bir mum karşı engele değdi, kapanışla aşamadı | 278 / 502 | 20.9% | 20.5% | +0.3 | [-7.6, +8.9] | -1.5 / +3.4 | 55.8% | 49.1% | +0.517 / +0.722 |
| Eşik kapanışından çıkış mumuna endeks işlemin tersine en az %0.5 | 167 / 494 | 38.9% | 11.3% | +27.6 | [+19.4, +37.8] | +26.8 / +29.3 | 63.7% | 18.2% | +0.052 / +0.889 |
| Yapı bozulması (aşağıdaki dördünden en az biri) | 69 / 502 | 55.1% | 15.2% | +39.8 | [+25.9, +55.1] | +46.2 / +29.3 | 36.5% | 4.8% | -0.416 / +0.772 |
| … ters dış yapı kırılımı (BOS / CHoCH) | 0 / 502 | — | 20.7% | — | [—, —] | — / — | 0.0% | 0.0% | — / +0.609 |
| … ters iç yapı kırılımı (BOS / CHoCH) | 0 / 502 | — | 20.7% | — | [—, —] | — / — | 0.0% | 0.0% | — / +0.609 |
| … tez seviyesinin ters tarafında kapanış | 37 / 502 | 89.2% | 15.3% | +73.9 | [+61.8, +83.4] | +81.0 / +62.3 | 31.7% | 0.4% | -1.008 / +0.738 |
| … formasyon bozulması (retest / teyitsiz / başarısız / karşı kırılım) | 55 / 502 | 45.5% | 17.7% | +27.8 | [+8.4, +46.0] | +33.0 / +19.3 | 24.0% | 4.8% | -0.227 / +0.712 |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi | 108 / 502 | 33.3% | 17.3% | +16.1 | [+5.1, +26.9] | +20.9 / +5.8 | 34.6% | 10.4% | -0.035 / +0.786 |
| Ters hacim baskısı | 119 / 502 | 26.1% | 19.1% | +7.0 | [-2.2, +17.1] | +4.8 / +10.3 | 29.8% | 8.9% | -0.005 / +0.800 |

### 8. Girişte hedef yolundaki engel (bütün küme)

Girişte bilinen en yakın karşı engelin uzaklığı; hedef 2 ATR'dedir.

| Girişte en yakın karşı engel | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Engel 1 ATR'den yakın | 713 | 44.0% | 24.7% | 19.4% | 48.9% | +0.065 | [-0.055, +0.180] | +0.052 (427) | +0.083 (286) |
| Engel 1–2 ATR arasında (hedeften önce) | 96 | 49.0% | 18.8% | 30.2% | 43.8% | -0.037 | [-0.324, +0.288] | -0.073 (73) | +0.078 (23) |
| Hedefe kadar engel yok | 315 | 45.4% | 25.4% | 20.0% | 48.9% | +0.083 | [-0.095, +0.263] | -0.006 (238) | +0.361 (77) |

## D1_Birincil — 4233 işlem, 2158 stop

Stopların `1307` tanesi stoptan önce 0.5 ATR'yi hiç görmedi (doğrudan / çok az yükselip düşen); `851` tanesi en az 0.5 ATR gördü; bunların `393` tanesi en az 1 ATR gördü.

### 1. Eşiği gören işlemlerin akıbeti

"Gören işlem": eşiği çıkış mumundan ÖNCE gören, yani o mumun kapanışında hâlâ açık olan işlem. Eşiği ilk kez çıkış mumunda gören işlemler (örneğin tek mumda hedefe giden) burada yoktur; o an verilecek bir karar olmadığı için.

| Eşik | Gören işlem | Stop oldu | Hedefe gitti | Süre doldu, kârda | Süre doldu, zararda | Grubun net R'si |
|---|---:|---:|---:|---:|---:|---:|
| 0.5 ATR | 2539 (60.0%) | 851 (33.5%) | 1096 (43.2%) | 378 (14.9%) | 214 (8.4%) | +0.427 |
| 1 ATR | 1749 (41.3%) | 393 (22.5%) | 891 (50.9%) | 316 (18.1%) | 149 (8.5%) | +0.732 |

### 2. Tepeden stopa: 0.5 ATR görüp stop olanlarda ne görüldü

`851` işlem (keşif `549`, doğrulama `302`; long `431`, short `420`). "Kontrol" sütunu aynı tür olayın eşiği gören BÜTÜN işlemlerdeki karşılığıdır: olay eşikten sonra görülünce stop oranı / görülmeyince stop oranı. İki oran yakınsa o gözlem dönüşü açıklamaz.

| Gözlem | Görüldüğü işlem | Yalnız bu görüldü | Birincil gözlem (toplam %100) | Kontrol: görülünce stop / görülmeyince stop |
|---|---:|---:|---:|---:|
| Tepe mumu bilinen bir karşı seviyeye / banda değdi, kapanışla aşamadı | 518 (60.9%) | 78 | **518 (60.9%)** | 31.9% / 37.9% |
| Tepe, bilinen bir karşı seviyenin 0.25 ATR dibinde kaldı (değmedi) | 70 (8.2%) | 13 | **70 (8.2%)** | — |
| Tepe kapanışından stop mumuna endeks işlemin tersine en az %0.5 gitti | 503 (59.1%) | 71 | **147 (17.3%)** | 55.0% / 21.4% |
| Hissenin kendi yapısı bozuldu (ters BOS/CHoCH, tez seviyesinin içine kapanış ya da formasyon bozulması) | 371 (43.6%) | 19 | **44 (5.2%)** | 61.9% / 24.3% |
| Ters hacim baskısı ya da tepede yüksek çaba – zayıf sonuç | 275 (32.3%) | 13 | **14 (1.6%)** | 41.0% / 30.9% |
| Stop bir açılış boşluğuyla geldi | 66 (7.8%) | 4 | **4 (0.5%)** | — |
| Yukarıdakilerin hiçbiri görülmedi | 54 (6.3%) | 54 | **54 (6.3%)** | — |

- İki ya da daha çok gözlemin birlikte görüldüğü işlem: `599 (70.4%)`.
- Tepe mumunun takıldığı engel, alan alan (bir işlem birden çok alanda sayılabilir): Stabil `93 (10.9%)`; Market Structure `330 (38.8%)`; OB / FVG `335 (39.4%)`.
- OB / FVG ayrımı: banda dışarıdan gelip takılan `205 (24.1%)`; önceki kapanışta zaten bandın içinde olup çıkamayan `130 (15.3%)`. Engel gözlemi YALNIZ "zaten içinde olunan bant"tan gelen işlem: `61 (7.2%)`.
- Market Structure motorunun kendi olayı — ters süpürme / sahte kırılım: tepe mumunda `145 (17.0%)`; tepe mumundan stop öncesi son kapanışa `250 (29.4%)`.
- Yapı ayrıntısı (tepe mumundan stop öncesi son kapanışa): ters dış kırılım `2 (0.2%)`; ters iç kırılım `4 (0.5%)`; tez seviyesinin içine kapanış `314 (36.9%)`; formasyon bozulması `174 (20.4%)` (tepe mumunun kapanışında formasyon zaten aleyhte durumda olan `60 (7.1%)`).
- Hacim ayrıntısı: tepe ile stop arasında ters baskı `265 (31.1%)`; tepede yüksek çaba – zayıf sonuç `25 (2.9%)`; tepe mumunda düşük göreli hacim `138 (18.4%)` (hacmi bilinenler içinde).
- Tepe mumu aralığının en az yarısını geri verip kapattı (fitil): `544 (63.9%)`. Stop mumunun kendisinde ters yapı kırılımı: `71 (8.3%)` (düşüşün sonucu, habercisi değil).
- Stoptan önceki son kapanışta işlem hâlâ kârdaydı: `290 (34.1%)`.
- Tepeden stopa kaç mum: 1 mum `211 (24.8%)`; 2 mum `185 (21.7%)`; 3 mum `201 (23.6%)`; 4+ mum `254 (29.8%)`; medyan `3`.
- Tepeden stopa gereken geri çekilme: medyan `2.05 ATR`; en çok 1.5 ATR olan `107 (12.6%)`; 2 ATR'den büyük olan `454 (53.3%)`.

### 3. Tepeden stopa: 1 ATR görüp stop olanlarda ne görüldü

`393` işlem (keşif `245`, doğrulama `148`; long `201`, short `192`). "Kontrol" sütunu aynı tür olayın eşiği gören BÜTÜN işlemlerdeki karşılığıdır: olay eşikten sonra görülünce stop oranı / görülmeyince stop oranı. İki oran yakınsa o gözlem dönüşü açıklamaz.

| Gözlem | Görüldüğü işlem | Yalnız bu görüldü | Birincil gözlem (toplam %100) | Kontrol: görülünce stop / görülmeyince stop |
|---|---:|---:|---:|---:|
| Tepe mumu bilinen bir karşı seviyeye / banda değdi, kapanışla aşamadı | 258 (65.6%) | 40 | **258 (65.6%)** | 22.9% / 21.5% |
| Tepe, bilinen bir karşı seviyenin 0.25 ATR dibinde kaldı (değmedi) | 23 (5.9%) | 5 | **23 (5.9%)** | — |
| Tepe kapanışından stop mumuna endeks işlemin tersine en az %0.5 gitti | 238 (60.6%) | 42 | **72 (18.3%)** | 40.1% / 13.0% |
| Hissenin kendi yapısı bozuldu (ters BOS/CHoCH, tez seviyesinin içine kapanış ya da formasyon bozulması) | 145 (36.9%) | 3 | **9 (2.3%)** | 57.2% / 16.5% |
| Ters hacim baskısı ya da tepede yüksek çaba – zayıf sonuç | 143 (36.4%) | 6 | **7 (1.8%)** | 32.7% / 19.2% |
| Stop bir açılış boşluğuyla geldi | 36 (9.2%) | 1 | **1 (0.3%)** | — |
| Yukarıdakilerin hiçbiri görülmedi | 23 (5.9%) | 23 | **23 (5.9%)** | — |

- İki ya da daha çok gözlemin birlikte görüldüğü işlem: `273 (69.5%)`.
- Tepe mumunun takıldığı engel, alan alan (bir işlem birden çok alanda sayılabilir): Stabil `54 (13.7%)`; Market Structure `162 (41.2%)`; OB / FVG `173 (44.0%)`.
- OB / FVG ayrımı: banda dışarıdan gelip takılan `114 (29.0%)`; önceki kapanışta zaten bandın içinde olup çıkamayan `59 (15.0%)`. Engel gözlemi YALNIZ "zaten içinde olunan bant"tan gelen işlem: `29 (7.4%)`.
- Market Structure motorunun kendi olayı — ters süpürme / sahte kırılım: tepe mumunda `74 (18.8%)`; tepe mumundan stop öncesi son kapanışa `136 (34.6%)`.
- Yapı ayrıntısı (tepe mumundan stop öncesi son kapanışa): ters dış kırılım `1 (0.3%)`; ters iç kırılım `2 (0.5%)`; tez seviyesinin içine kapanış `134 (34.1%)`; formasyon bozulması `49 (12.5%)` (tepe mumunun kapanışında formasyon zaten aleyhte durumda olan `15 (3.8%)`).
- Hacim ayrıntısı: tepe ile stop arasında ters baskı `136 (34.6%)`; tepede yüksek çaba – zayıf sonuç `15 (3.8%)`; tepe mumunda düşük göreli hacim `45 (13.0%)` (hacmi bilinenler içinde).
- Tepe mumu aralığının en az yarısını geri verip kapattı (fitil): `248 (63.1%)`. Stop mumunun kendisinde ters yapı kırılımı: `31 (7.9%)` (düşüşün sonucu, habercisi değil).
- Stoptan önceki son kapanışta işlem hâlâ kârdaydı: `149 (37.9%)`.
- Tepeden stopa kaç mum: 1 mum `75 (19.1%)`; 2 mum `73 (18.6%)`; 3 mum `103 (26.2%)`; 4+ mum `142 (36.1%)`; medyan `3`.
- Tepeden stopa gereken geri çekilme: medyan `2.46 ATR`; en çok 1.5 ATR olan `0 (0.0%)`; 2 ATR'den büyük olan `328 (83.5%)`.

### 4. Eşik anı: 0.5 ATR ilk görüldüğü mumun kapanışında domainler

`2539` işlem. "Varken stop": gözlem o kapanışta varsa işlemin sonradan stop olma oranı.

| Gözlem | Var (n) | Varken stop | Yokken stop | Fark (puan) | Fark en kötü GA | Keşif / doğrulama farkı | Stoplarda | Hedefe gidenlerde | Net R: var / yok | Karar |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| Eşik mumu bilinen bir karşı engele değdi, kapanışla aşamadı | 1533 / 2539 | 34.4% | 32.2% | +2.2 | [-1.6, +6.3] | +0.7 / +5.5 | 61.9% | 58.8% | +0.389 / +0.486 | **ZAYIF** |
| … karşı Stabil seviyesine değip aşamadı | 199 / 2539 | 42.7% | 32.7% | +10.0 | [+1.9, +17.5] | +7.5 / +14.4 | 10.0% | 5.9% | +0.144 / +0.451 | **AYIRIYOR** |
| … karşı Market Structure seviyesine değip aşamadı | 831 / 2539 | 38.1% | 31.3% | +6.9 | [+1.3, +12.2] | +7.5 / +7.1 | 37.3% | 29.5% | +0.244 / +0.516 | **AYIRIYOR** |
| … karşı OB / FVG bandına değip aşamadı | 1075 / 2539 | 33.0% | 33.9% | -0.9 | [-4.5, +2.7] | -2.3 / +1.7 | 41.7% | 42.9% | +0.448 / +0.412 | **AYIRMIYOR** |
| … … banda dışarıdan gelip takıldı † | 727 / 2539 | 31.5% | 34.3% | -2.8 | [-6.8, +1.2] | -2.4 / -3.5 | 26.9% | 30.8% | +0.499 / +0.399 | **ZAYIF** |
| … … önceki kapanışta zaten bandın içindeydi, çıkamadı † | 348 / 2539 | 36.2% | 33.1% | +3.1 | [-2.9, +9.2] | -0.8 / +9.8 | 14.8% | 12.0% | +0.341 / +0.441 | **AYIRMIYOR** |
| Eşik mumu bir karşı engeli kapanışla aştı (takıldığı engel yok) | 350 / 2539 | 21.4% | 35.4% | -14.0 | [-18.6, -8.7] | -11.8 / -17.4 | 8.8% | 18.1% | +0.872 / +0.356 | **AYIRIYOR** |
| Kapanışın önünde en çok 0.5 ATR'de karşı engel var | 1479 / 2539 | 31.7% | 36.0% | -4.3 | [-8.6, -0.5] | -4.1 / -4.2 | 55.1% | 59.0% | +0.480 / +0.354 | **AYIRIYOR** |
| Kapanış ile hedef arasında karşı engel var | 2092 / 2539 | 33.9% | 31.5% | +2.4 | [-2.8, +7.4] | +1.6 / +4.6 | 83.4% | 79.6% | +0.408 / +0.519 | **ZAYIF** |
| Eşiği mum içinde gördü ama altında kapattı | 1337 / 2539 | 42.7% | 23.3% | +19.4 | [+14.8, +23.3] | +17.5 / +22.9 | 67.1% | 40.0% | +0.109 / +0.782 | **AYIRIYOR** |
| Mum, aralığının en az yarısını geri verip kapattı | 849 / 2539 | 46.8% | 26.9% | +19.9 | [+14.7, +25.2] | +19.4 / +21.1 | 46.7% | 22.1% | -0.021 / +0.653 | **AYIRIYOR** |
| Göreli hacim 0.75'in altında | 428 / 2199 | 34.1% | 34.1% | +0.0 | [-6.4, +6.6] | +1.7 / -2.7 | 19.5% | 17.7% | +0.463 / +0.383 | **AYIRMIYOR** |
| Göreli hacim en az 2 | 326 / 2199 | 31.6% | 34.5% | -2.9 | [-9.6, +4.7] | -8.8 / +4.2 | 13.7% | 17.1% | +0.358 / +0.405 | **AYIRMIYOR** |
| Hacim baskısı işlemin tersine (< −0.13) | 145 / 2199 | 52.4% | 32.8% | +19.6 | [+11.7, +28.2] | +17.6 / +22.3 | 10.1% | 3.1% | -0.218 / +0.442 | **AYIRIYOR** |
| Hacim sınıfı: yüksek çaba – zayıf sonuç | 39 / 2539 | 53.8% | 33.2% | +20.6 | [+2.0, +36.8] | +15.9 / +28.3 | 2.5% | 1.0% | -0.238 / +0.438 | **AYIRIYOR** |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi † | 266 / 2539 | 44.0% | 32.3% | +11.7 | [+5.8, +18.3] | +15.0 / +6.6 | 13.7% | 7.8% | +0.088 / +0.467 | **AYIRIYOR** |
| Dış piyasa yapısı işlemin tersinde | 895 / 2539 | 34.7% | 32.8% | +1.9 | [-2.4, +6.0] | -1.7 / +8.1 | 36.5% | 33.6% | +0.388 / +0.449 | **AYIRMIYOR** |
| İç piyasa yapısı işlemin tersinde | 800 / 2539 | 37.4% | 31.7% | +5.6 | [+1.0, +9.8] | +3.1 / +9.9 | 35.1% | 28.4% | +0.326 / +0.474 | **AYIRIYOR** |
| Kapanış tez seviyesinin ters tarafında | 68 / 2539 | 85.3% | 32.1% | +53.2 | [+41.0, +62.0] | +55.3 / +50.0 | 6.8% | 0.5% | -0.743 / +0.460 | **AYIRIYOR** |
| Formasyon girişten sonra aleyhte duruma geçti ve hâlâ orada (retest ediliyor / teyitsiz / başarısız / karşı kırılım) † | 150 / 2539 | 24.7% | 34.1% | -9.4 | [-17.1, -1.4] | -10.4 / -7.7 | 4.3% | 5.4% | +0.236 / +0.439 | **AYIRIYOR** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 390 / 2502 | 38.7% | 32.6% | +6.1 | [-0.2, +12.7] | +7.4 / +4.5 | 18.0% | 13.9% | +0.225 / +0.462 | **ZAYIF** |
| Eşik, girişten sonraki ilk mumda görüldü | 1361 / 2539 | 33.9% | 33.1% | +0.8 | [-3.5, +4.8] | +0.9 / +0.6 | 54.2% | 59.4% | +0.481 / +0.366 | **ZAYIF** |
| Stop uzaklığı en çok 1 ATR | 1028 / 2539 | 41.1% | 28.3% | +12.8 | [+9.0, +16.7] | +13.0 / +12.3 | 49.7% | 38.5% | +0.631 / +0.289 | **AYIRIYOR** |
| Girişte 20 günlük endeks rejimi işleme karşı | 1304 / 2539 | 33.4% | 33.6% | -0.2 | [-7.2, +7.4] | +1.1 / -2.4 | 51.2% | 49.5% | +0.432 / +0.422 | **AYIRMIYOR** |

**0.5 ATR — o gözlem görülünce çıkılsaydı.** Karar eşik mumunun kapanışında verilir, çıkış bir sonraki mumun açılışındadır; masraf aynıdır. "Kümenin işlem başına R'si": gözlemin olmadığı işlemler değişmeden kalır. Kabul merdiveni endeks filtresi raporundakiyle aynıdır.

| Gözlem | Görüldüğü işlem | Çıkılsaydı, etkilenen işlem başına R | Kümenin işlem başına R'si | En kötü GA | Keşif / doğrulama | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---|
| Eşiği gören her işlem (karşılaştırma tabanı) | 2539 | -0.079 | -0.0474 | [-0.0903, -0.0017] | -0.0321 / -0.0749 | -200.4 | **ZARARLI** |
| Eşik mumu bilinen bir karşı engele değdi, kapanışla aşamadı | 1533 | -0.076 | -0.0276 | [-0.0584, +0.0045] | -0.0194 / -0.0423 | -116.7 | **GECMEDI** |
| … karşı Stabil seviyesine değip aşamadı | 199 | +0.007 | +0.0003 | [-0.0099, +0.0104] | +0.0003 / +0.0003 | +1.4 | **ZAYIF_ARTI** |
| … karşı Market Structure seviyesine değip aşamadı | 831 | -0.056 | -0.0110 | [-0.0363, +0.0127] | -0.0001 / -0.0305 | -46.4 | **GECMEDI** |
| … karşı OB / FVG bandına değip aşamadı | 1075 | -0.063 | -0.0160 | [-0.0406, +0.0099] | -0.0155 / -0.0167 | -67.6 | **GECMEDI** |
| … … banda dışarıdan gelip takıldı † | 727 | -0.061 | -0.0104 | [-0.0298, +0.0099] | -0.0092 / -0.0126 | -44.0 | **GECMEDI** |
| … … önceki kapanışta zaten bandın içindeydi, çıkamadı † | 348 | -0.068 | -0.0056 | [-0.0182, +0.0070] | -0.0063 / -0.0042 | -23.5 | **GECMEDI** |
| Eşik mumu bir karşı engeli kapanışla aştı (takıldığı engel yok) | 350 | -0.136 | -0.0112 | [-0.0226, +0.0010] | -0.0078 / -0.0174 | -47.5 | **GECMEDI** |
| Kapanışın önünde en çok 0.5 ATR'de karşı engel var | 1479 | -0.089 | -0.0312 | [-0.0606, +0.0012] | -0.0181 / -0.0548 | -132.0 | **GECMEDI** |
| Kapanış ile hedef arasında karşı engel var | 2092 | -0.099 | -0.0490 | [-0.0861, -0.0080] | -0.0394 / -0.0663 | -207.4 | **ZARARLI** |
| Eşiği mum içinde gördü ama altında kapattı | 1337 | -0.108 | -0.0340 | [-0.0604, -0.0096] | -0.0294 / -0.0424 | -144.0 | **ZARARLI** |
| Mum, aralığının en az yarısını geri verip kapattı | 849 | -0.064 | -0.0129 | [-0.0302, +0.0046] | -0.0111 / -0.0161 | -54.6 | **GECMEDI** |
| Göreli hacim 0.75'in altında | 428 | -0.086 | -0.0086 | [-0.0240, +0.0075] | -0.0006 / -0.0232 | -36.6 | **GECMEDI** |
| Göreli hacim en az 2 | 326 | -0.007 | -0.0005 | [-0.0126, +0.0116] | -0.0038 / +0.0053 | -2.2 | **GECMEDI** |
| Hacim baskısı işlemin tersine (< −0.13) | 145 | +0.007 | +0.0003 | [-0.0067, +0.0068] | +0.0002 / +0.0004 | +1.1 | **ZAYIF_ARTI** |
| Hacim sınıfı: yüksek çaba – zayıf sonuç | 39 | -0.191 | -0.0018 | [-0.0052, +0.0015] | -0.0016 / -0.0021 | -7.5 | **GECMEDI** |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi † | 266 | -0.128 | -0.0080 | [-0.0171, +0.0012] | +0.0001 / -0.0227 | -34.0 | **GECMEDI** |
| Dış piyasa yapısı işlemin tersinde | 895 | -0.060 | -0.0126 | [-0.0347, +0.0105] | -0.0234 / +0.0068 | -53.4 | **GECMEDI** |
| İç piyasa yapısı işlemin tersinde | 800 | -0.040 | -0.0075 | [-0.0267, +0.0128] | -0.0133 / +0.0029 | -31.8 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 68 | +0.003 | +0.0000 | [-0.0043, +0.0041] | +0.0025 / -0.0044 | +0.2 | **GECMEDI** |
| Formasyon girişten sonra aleyhte duruma geçti ve hâlâ orada (retest ediliyor / teyitsiz / başarısız / karşı kırılım) † | 150 | -0.117 | -0.0041 | [-0.0101, +0.0011] | -0.0026 / -0.0069 | -17.5 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 390 | -0.063 | -0.0058 | [-0.0194, +0.0067] | +0.0008 / -0.0177 | -24.7 | **GECMEDI** |
| Eşik, girişten sonraki ilk mumda görüldü | 1361 | -0.115 | -0.0368 | [-0.0689, -0.0048] | -0.0294 / -0.0502 | -155.9 | **ZARARLI** |
| Stop uzaklığı en çok 1 ATR | 1028 | -0.111 | -0.0269 | [-0.0564, +0.0050] | -0.0153 / -0.0477 | -113.8 | **GECMEDI** |
| Girişte 20 günlük endeks rejimi işleme karşı | 1304 | -0.043 | -0.0131 | [-0.0473, +0.0194] | -0.0046 / -0.0284 | -55.4 | **GECMEDI** |

### 5. Eşik anı: 1 ATR ilk görüldüğü mumun kapanışında domainler

`1749` işlem. "Varken stop": gözlem o kapanışta varsa işlemin sonradan stop olma oranı.

| Gözlem | Var (n) | Varken stop | Yokken stop | Fark (puan) | Fark en kötü GA | Keşif / doğrulama farkı | Stoplarda | Hedefe gidenlerde | Net R: var / yok | Karar |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| Eşik mumu bilinen bir karşı engele değdi, kapanışla aşamadı | 1074 / 1749 | 23.7% | 20.4% | +3.3 | [-0.8, +7.5] | +1.1 / +7.0 | 64.9% | 58.4% | +0.675 / +0.825 | **ZAYIF** |
| … karşı Stabil seviyesine değip aşamadı | 136 / 1749 | 39.0% | 21.1% | +17.9 | [+10.0, +26.5] | +16.0 / +21.6 | 13.5% | 5.6% | +0.208 / +0.777 | **AYIRIYOR** |
| … karşı Market Structure seviyesine değip aşamadı | 587 / 1749 | 25.2% | 21.1% | +4.1 | [-0.3, +8.7] | +3.8 / +4.8 | 37.7% | 30.8% | +0.567 / +0.816 | **ZAYIF** |
| … karşı OB / FVG bandına değip aşamadı | 768 / 1749 | 23.3% | 21.8% | +1.5 | [-2.9, +5.5] | +1.1 / +2.2 | 45.5% | 42.0% | +0.707 / +0.753 | **ZAYIF** |
| … … banda dışarıdan gelip takıldı † | 532 / 1749 | 24.1% | 21.8% | +2.3 | [-2.0, +6.8] | +3.2 / +0.8 | 32.6% | 27.6% | +0.640 / +0.773 | **ZAYIF** |
| … … önceki kapanışta zaten bandın içindeydi, çıkamadı † | 236 / 1749 | 21.6% | 22.6% | -1.0 | [-8.0, +7.0] | -3.7 / +2.9 | 13.0% | 14.4% | +0.856 / +0.713 | **AYIRMIYOR** |
| Eşik mumu bir karşı engeli kapanışla aştı (takıldığı engel yok) | 294 / 1749 | 16.7% | 23.6% | -7.0 | [-12.4, -1.3] | -2.5 / -14.0 | 12.5% | 20.1% | +0.993 / +0.680 | **AYIRIYOR** |
| Kapanışın önünde en çok 0.5 ATR'de karşı engel var | 1000 / 1749 | 22.1% | 23.0% | -0.9 | [-4.9, +3.2] | +0.3 / -2.7 | 56.2% | 57.0% | +0.773 / +0.679 | **AYIRMIYOR** |
| Kapanış ile hedef arasında karşı engel var | 1312 / 1749 | 23.3% | 19.9% | +3.4 | [-1.0, +8.2] | +2.7 / +5.1 | 77.9% | 71.4% | +0.694 / +0.849 | **ZAYIF** |
| Eşiği mum içinde gördü ama altında kapattı | 995 / 1749 | 28.8% | 14.1% | +14.8 | [+9.2, +20.1] | +12.2 / +19.0 | 73.0% | 46.8% | +0.476 / +1.071 | **AYIRIYOR** |
| Mum, aralığının en az yarısını geri verip kapattı | 547 / 1749 | 34.4% | 17.1% | +17.3 | [+12.3, +22.0] | +15.4 / +20.3 | 47.8% | 20.8% | +0.241 / +0.956 | **AYIRIYOR** |
| Göreli hacim 0.75'in altında | 255 / 1511 | 17.6% | 24.0% | -6.4 | [-12.2, -0.2] | -6.7 / -6.0 | 13.0% | 17.0% | +0.950 / +0.656 | **AYIRIYOR** |
| Göreli hacim en az 2 | 285 / 1511 | 24.6% | 22.6% | +2.0 | [-4.6, +8.8] | -1.6 / +6.2 | 20.2% | 20.4% | +0.614 / +0.727 | **AYIRMIYOR** |
| Hacim baskısı işlemin tersine (< −0.13) | 91 / 1511 | 39.6% | 21.9% | +17.7 | [+7.9, +27.8] | +12.7 / +22.4 | 10.4% | 3.0% | +0.028 / +0.749 | **AYIRIYOR** |
| Hacim sınıfı: yüksek çaba – zayıf sonuç | 22 / 1749 | 45.5% | 22.2% | +23.3 | [—, —] | +23.7 / +22.7 | 2.5% | 0.4% | -0.323 / +0.746 | **SAYILMAZ_N<30** |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi † | 177 / 1749 | 33.3% | 21.2% | +12.1 | [+4.3, +19.5] | +13.1 / +10.4 | 15.0% | 7.1% | +0.217 / +0.790 | **AYIRIYOR** |
| Dış piyasa yapısı işlemin tersinde | 590 / 1749 | 24.4% | 21.5% | +2.9 | [-1.6, +7.5] | +0.2 / +7.3 | 36.6% | 32.4% | +0.686 / +0.756 | **ZAYIF** |
| İç piyasa yapısı işlemin tersinde | 477 / 1749 | 25.2% | 21.5% | +3.7 | [-0.9, +8.3] | +2.1 / +6.3 | 30.5% | 25.0% | +0.648 / +0.764 | **ZAYIF** |
| Kapanış tez seviyesinin ters tarafında | 12 / 1749 | 83.3% | 22.0% | +61.3 | [—, —] | +65.2 / +53.3 | 2.5% | 0.1% | -0.723 / +0.742 | **SAYILMAZ_N<30** |
| Formasyon girişten sonra aleyhte duruma geçti ve hâlâ orada (retest ediliyor / teyitsiz / başarısız / karşı kırılım) † | 119 / 1749 | 10.1% | 23.4% | -13.3 | [-19.0, -6.4] | -14.2 / -12.1 | 3.1% | 7.5% | +0.707 / +0.734 | **AYIRIYOR** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 238 / 1719 | 24.4% | 22.1% | +2.3 | [-4.7, +8.9] | +0.1 / +5.2 | 15.1% | 12.6% | +0.650 / +0.746 | **ZAYIF** |
| Eşik, girişten sonraki ilk mumda görüldü | 473 / 1749 | 26.4% | 21.0% | +5.4 | [+0.5, +10.4] | +5.3 / +5.6 | 31.8% | 30.9% | +0.722 / +0.736 | **AYIRIYOR** |
| Stop uzaklığı en çok 1 ATR | 696 / 1749 | 28.0% | 18.8% | +9.2 | [+4.6, +13.8] | +10.0 / +7.9 | 49.6% | 39.2% | +1.057 / +0.518 | **AYIRIYOR** |
| Girişte 20 günlük endeks rejimi işleme karşı | 893 / 1749 | 21.6% | 23.4% | -1.8 | [-8.1, +5.0] | -1.8 / -1.6 | 49.1% | 49.9% | +0.759 / +0.705 | **ZAYIF** |

**1 ATR — o gözlem görülünce çıkılsaydı.** Karar eşik mumunun kapanışında verilir, çıkış bir sonraki mumun açılışındadır; masraf aynıdır. "Kümenin işlem başına R'si": gözlemin olmadığı işlemler değişmeden kalır. Kabul merdiveni endeks filtresi raporundakiyle aynıdır.

| Gözlem | Görüldüğü işlem | Çıkılsaydı, etkilenen işlem başına R | Kümenin işlem başına R'si | En kötü GA | Keşif / doğrulama | Toplam R | Karar |
|---|---:|---:|---:|---|---:|---:|---|
| Eşiği gören her işlem (karşılaştırma tabanı) | 1749 | -0.009 | -0.0039 | [-0.0325, +0.0268] | -0.0032 / -0.0050 | -16.3 | **GECMEDI** |
| Eşik mumu bilinen bir karşı engele değdi, kapanışla aşamadı | 1074 | -0.012 | -0.0030 | [-0.0267, +0.0198] | -0.0077 / +0.0054 | -12.8 | **GECMEDI** |
| … karşı Stabil seviyesine değip aşamadı | 136 | +0.191 | +0.0061 | [-0.0009, +0.0137] | +0.0079 / +0.0030 | +26.0 | **ZAYIF_ARTI** |
| … karşı Market Structure seviyesine değip aşamadı | 587 | -0.053 | -0.0074 | [-0.0240, +0.0086] | -0.0007 / -0.0195 | -31.3 | **GECMEDI** |
| … karşı OB / FVG bandına değip aşamadı | 768 | +0.016 | +0.0029 | [-0.0166, +0.0238] | -0.0045 / +0.0162 | +12.1 | **GECMEDI** |
| … … banda dışarıdan gelip takıldı † | 532 | +0.091 | +0.0114 | [-0.0030, +0.0252] | +0.0062 / +0.0209 | +48.4 | **ZAYIF_ARTI** |
| … … önceki kapanışta zaten bandın içindeydi, çıkamadı † | 236 | -0.154 | -0.0086 | [-0.0177, +0.0010] | -0.0107 / -0.0047 | -36.3 | **GECMEDI** |
| Eşik mumu bir karşı engeli kapanışla aştı (takıldığı engel yok) | 294 | +0.039 | +0.0027 | [-0.0066, +0.0124] | +0.0068 / -0.0048 | +11.4 | **GECMEDI** |
| Kapanışın önünde en çok 0.5 ATR'de karşı engel var | 1000 | -0.014 | -0.0032 | [-0.0240, +0.0185] | -0.0022 / -0.0051 | -13.8 | **GECMEDI** |
| Kapanış ile hedef arasında karşı engel var | 1312 | -0.013 | -0.0040 | [-0.0282, +0.0202] | -0.0067 / +0.0008 | -16.9 | **GECMEDI** |
| Eşiği mum içinde gördü ama altında kapattı | 995 | -0.070 | -0.0164 | [-0.0416, +0.0066] | -0.0212 / -0.0077 | -69.5 | **GECMEDI** |
| Mum, aralığının en az yarısını geri verip kapattı | 547 | -0.003 | -0.0004 | [-0.0155, +0.0133] | -0.0039 / +0.0059 | -1.7 | **GECMEDI** |
| Göreli hacim 0.75'in altında | 255 | -0.006 | -0.0003 | [-0.0106, +0.0110] | +0.0041 / -0.0084 | -1.4 | **GECMEDI** |
| Göreli hacim en az 2 | 285 | -0.033 | -0.0022 | [-0.0137, +0.0093] | -0.0050 / +0.0028 | -9.3 | **GECMEDI** |
| Hacim baskısı işlemin tersine (< −0.13) | 91 | -0.034 | -0.0007 | [-0.0061, +0.0044] | -0.0025 / +0.0025 | -3.1 | **GECMEDI** |
| Hacim sınıfı: yüksek çaba – zayıf sonuç | 22 | +0.038 | +0.0002 | [-0.0016, +0.0020] | +0.0010 / -0.0013 | +0.8 | **SAYILMAZ_N<30** |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi † | 177 | +0.033 | +0.0014 | [-0.0059, +0.0081] | +0.0052 / -0.0055 | +5.9 | **GECMEDI** |
| Dış piyasa yapısı işlemin tersinde | 590 | -0.002 | -0.0003 | [-0.0153, +0.0156] | -0.0071 / +0.0121 | -1.1 | **GECMEDI** |
| İç piyasa yapısı işlemin tersinde | 477 | +0.024 | +0.0027 | [-0.0103, +0.0155] | -0.0001 / +0.0077 | +11.5 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 12 | +0.002 | +0.0000 | [-0.0018, +0.0013] | +0.0010 / -0.0017 | +0.0 | **SAYILMAZ_N<30** |
| Formasyon girişten sonra aleyhte duruma geçti ve hâlâ orada (retest ediliyor / teyitsiz / başarısız / karşı kırılım) † | 119 | -0.210 | -0.0059 | [-0.0109, -0.0004] | -0.0063 / -0.0053 | -25.0 | **ZARARLI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 238 | -0.052 | -0.0029 | [-0.0120, +0.0059] | -0.0015 / -0.0054 | -12.4 | **GECMEDI** |
| Eşik, girişten sonraki ilk mumda görüldü | 473 | -0.007 | -0.0008 | [-0.0141, +0.0137] | -0.0027 / +0.0027 | -3.4 | **GECMEDI** |
| Stop uzaklığı en çok 1 ATR | 696 | -0.012 | -0.0020 | [-0.0216, +0.0206] | -0.0009 / -0.0041 | -8.7 | **GECMEDI** |
| Girişte 20 günlük endeks rejimi işleme karşı | 893 | +0.023 | +0.0049 | [-0.0160, +0.0255] | +0.0064 / +0.0022 | +20.9 | **ZAYIF_ARTI** |

### 6. Eşikten sonra: 0.5 ATR gördükten sonra çıkışa kadar görülen olaylar

Uzun yaşayan işlem daha çok olay görür; bu tablo olayları olduğundan kötü gösterir. "Stoplarda" ve "Hedefe gidenlerde" sütunlarını birlikte okuyun.

| Gözlem | Var (n) | Varken stop | Yokken stop | Fark (puan) | Fark en kötü GA | Keşif / doğrulama farkı | Stoplarda | Hedefe gidenlerde | Net R: var / yok |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Bir mum karşı engele değdi, kapanışla aşamadı | 1855 / 2539 | 31.9% | 37.9% | -6.0 | [-10.0, -1.5] | -7.6 / -2.5 | 69.6% | 69.2% | +0.419 / +0.450 |
| Eşik kapanışından çıkış mumuna endeks işlemin tersine en az %0.5 | 906 / 2502 | 55.0% | 21.4% | +33.6 | [+28.0, +39.4] | +33.1 / +34.4 | 59.4% | 16.2% | -0.248 / +0.807 |
| Yapı bozulması (aşağıdaki dördünden en az biri) | 620 / 2539 | 61.9% | 24.3% | +37.6 | [+32.3, +42.9] | +40.4 / +33.1 | 45.1% | 9.1% | -0.439 / +0.707 |
| … ters dış yapı kırılımı (BOS / CHoCH) | 3 / 2539 | 66.7% | 33.5% | +33.2 | [—, —] | +15.7 / +67.9 | 0.2% | 0.0% | -0.871 / +0.429 |
| … ters iç yapı kırılımı (BOS / CHoCH) | 11 / 2539 | 36.4% | 33.5% | +2.9 | [—, —] | -9.3 / +34.6 | 0.5% | 0.0% | -0.582 / +0.432 |
| … tez seviyesinin ters tarafında kapanış | 392 / 2539 | 81.1% | 24.8% | +56.3 | [+51.3, +61.4] | +57.5 / +54.3 | 37.4% | 1.5% | -0.846 / +0.660 |
| … formasyon bozulması (retest / teyitsiz / başarısız / karşı kırılım) | 374 / 2539 | 50.3% | 30.6% | +19.6 | [+13.5, +26.1] | +24.9 / +11.0 | 22.1% | 8.4% | -0.172 / +0.531 |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi | 650 / 2539 | 40.6% | 31.1% | +9.5 | [+4.1, +14.4] | +11.8 / +5.5 | 31.0% | 17.2% | +0.101 / +0.540 |
| Ters hacim baskısı | 656 / 2539 | 41.0% | 30.9% | +10.1 | [+5.0, +15.1] | +11.3 / +9.0 | 31.6% | 9.9% | -0.172 / +0.636 |

### 7. Eşikten sonra: 1 ATR gördükten sonra çıkışa kadar görülen olaylar

Uzun yaşayan işlem daha çok olay görür; bu tablo olayları olduğundan kötü gösterir. "Stoplarda" ve "Hedefe gidenlerde" sütunlarını birlikte okuyun.

| Gözlem | Var (n) | Varken stop | Yokken stop | Fark (puan) | Fark en kötü GA | Keşif / doğrulama farkı | Stoplarda | Hedefe gidenlerde | Net R: var / yok |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Bir mum karşı engele değdi, kapanışla aşamadı | 1233 / 1749 | 22.9% | 21.5% | +1.4 | [-2.8, +6.0] | +0.1 / +3.5 | 71.8% | 65.1% | +0.668 / +0.886 |
| Eşik kapanışından çıkış mumuna endeks işlemin tersine en az %0.5 | 596 / 1719 | 40.1% | 13.0% | +27.1 | [+20.3, +34.2] | +27.6 / +26.2 | 62.1% | 17.4% | +0.092 / +1.072 |
| Yapı bozulması (aşağıdaki dördünden en az biri) | 257 / 1749 | 57.2% | 16.5% | +40.7 | [+32.6, +47.8] | +45.2 / +34.3 | 37.4% | 4.8% | -0.372 / +0.923 |
| … ters dış yapı kırılımı (BOS / CHoCH) | 1 / 1749 | 100.0% | 22.4% | +77.6 | [—, —] | +77.3 / — | 0.3% | 0.0% | -1.028 / +0.733 |
| … ters iç yapı kırılımı (BOS / CHoCH) | 6 / 1749 | 33.3% | 22.4% | +10.9 | [—, —] | +2.3 / +28.1 | 0.5% | 0.0% | -0.608 / +0.737 |
| … tez seviyesinin ters tarafında kapanış | 164 / 1749 | 82.3% | 16.3% | +66.0 | [+57.9, +72.0] | +68.6 / +62.0 | 34.4% | 0.4% | -0.917 / +0.903 |
| … formasyon bozulması (retest / teyitsiz / başarısız / karşı kırılım) | 139 / 1749 | 36.7% | 21.2% | +15.4 | [+4.7, +25.9] | +20.3 / +9.5 | 13.0% | 4.6% | +0.091 / +0.788 |
| Market Structure motoru ters süpürme / sahte kırılım bildirdi | 406 / 1749 | 34.0% | 19.0% | +15.0 | [+9.5, +20.5] | +17.2 / +11.2 | 35.1% | 13.9% | +0.191 / +0.896 |
| Ters hacim baskısı | 419 / 1749 | 32.7% | 19.2% | +13.4 | [+8.5, +18.8] | +13.2 / +14.3 | 34.9% | 8.9% | -0.038 / +0.975 |

### 8. Girişte hedef yolundaki engel (bütün küme)

Girişte bilinen en yakın karşı engelin uzaklığı; hedef 2 ATR'dedir.

| Girişte en yakın karşı engel | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Engel 1 ATR'den yakın | 3305 | 51.0% | 31.6% | 19.5% | 43.0% | +0.016 | [-0.056, +0.092] | -0.001 (2045) | +0.042 (1260) |
| Engel 1–2 ATR arasında (hedeften önce) | 433 | 50.3% | 26.8% | 23.6% | 41.1% | -0.043 | [-0.171, +0.095] | -0.024 (313) | -0.093 (120) |
| Hedefe kadar engel yok | 495 | 51.1% | 29.7% | 21.4% | 44.0% | +0.020 | [-0.117, +0.186] | -0.047 (365) | +0.206 (130) |
