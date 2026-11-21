# Beş alarm fikri: kapanıştan sonra gerçekten ne oldu?

Formasyonlarda 24 sabit BIST hissesi × 4 native periyot; Stabil ve hacimde aynı tanımlar ile genişletilmiş **174 BIST hissesi**. Geniş koşunun 24 hisselik ortak bölümünün olay zamanları, grupları, fiyatları ve bariyerleri pilotla aynı (7.976 ölçüm satırı). 19 Kasım 2026 arşiv gününün tamamı kısmi olabilme ihtimaline karşı dışarıda. Bu, geçmiş gözlem; ileri test veya işlem getirisi değil.

## 1. Dikey → yatay Stabil desteğe dönüş

Günlük native Stabil çizgisi, yalnız kapanmış günlük bilgiyle 4s grafiğe taşındı. Dikey/görsel eşlemesi **aday rejim**, gerçek bir grafikte kullanıcı tarafından onaylanmış etiket değil. Ölçülen çıkış: `STEPPING_UP/DOWN` durumunda, en düşük fiyatın çizginin üzerine ayrıldığı veya bu rejime çizginin üzerinde girildiği mum = 0. Seviye değişmeden yatay proxy’ye geçtikten sonraki ilk geometrik temas: fitil dahil `low ≤ destek ≤ high`. Süre yataylaşmadan değil çıkıştan başlıyor: günlük ≤7, 4s ≤12 mum. Çizginin altında kapanan bir temas da temas sayılır; “üstünde kapandı” şartı konmadı. Alarm çapası geri ziyaret mumunun **kapanışı**; bu, çıkış anında geri dönüş olasılığı ölçümü değildir.

Günlük: **304/646 (%47,1)** önce yukarı 1 ATR; genel yatay temaslarda %48,9. 4s: **358/771 (%46,4)**; genel yatay temaslarda %45,2. İkisi beraber 662/1.417 (%46,7); sıradan yatay ziyaret örneklemi 1.890/4.065 (%46,5). Gruplar örtüşebilir. Görsel örnekle çıkış tanımı doğrulanmadan bu yakın oranları alarm kanıtı saymıyoruz.

## 2. Sabit desteğin altındaki dipten yeşil mumlarla geri alış

Aynı destek seviyesinin altında kapanıştan ilk **üst** kapanışa kadar izlenir. Seviye değişirse sayaç iptal. Bu bölümün en düşük fitilli mumu (eşitse sonuncu) ile geri alış mumu **dahil** arası payda: sabit son 10 mum değil. Olay anında bu dip bilinir. En az 3 mumluk yol; ayrıca en az 5 ve 10 mum kesitleri. Yeşil = `close > open`; “temiz yeşil” pilot tanımı = yeşil ve gövde / yüksek–düşük ≥%50. Tam 10 mumluk yolda en az 8’i, 5 mumda en az 4’ü şartı karşılamalı.

| Geniş evren | Olay | +1 ATR önce | −1 ATR önce |
|---|---:|---:|---:|
| Bütün sabit seviye geri alışları | 4.112 | 2.050 (%49,9) | 1.940 |
| Yolun ≥%80’i yeşil | 270 | 136 (%50,4) | 127 |
| Yolun ≥%80’i **temiz yeşil** | 19 | **13** | 6 |
| ≥10 mum ve ≥%80 yeşil | 13 | 5 | 7 (1 belirsiz) |
| ≥10 mum ve ≥%80 **temiz** yeşil | 0 | — | — |

19 temiz yolun hepsi **3–5 mumluk**. En az 5 mum koşulunda 7 olayın 6’sında önce yukarı görüldü; dört başarılı hisse aynı **16 Eylül 2025** mumunda oluştu. Bağımsız yedi deneme veya 10 mumluk modeli doğrulama değil. THYAO 4s, **9 Mart 2026 18:00**: dip 263,50, sabit destek 279,50, geri alış kapanışı 282,00; üç mumun üçü temiz, ilk ileri mumda +1 ATR. TTRAK 4s, **2 Aralık 2025 13:00**: dip 510, destek 520; beş mumun dördü temiz, önce ters bariyer. Son fiyatın iyi olması yolun risksiz olduğu anlamına gelmiyor.

## 3. Yukarı kırılım teyidi + açık alan + Stabil üstü

Dengeli Argent motorunun yukarı `KIRILIM_TEYITLI` geçişi; kapanış günlük Stabil desteğinin üstünde. Aynı anda fiyatı kapsayan veya yukarıda duran aktif **karşıt** OB/FVG’nin kalan alt kenarına mesafe en az bir sinyal ATR’si; hiç karşıt bölge yoksa açık alan. Sadece yakın tek OB değil, aktif karşıt OB’ler tarandı. FVG 1s desteklemediği için 1s’te son **kapanmış 2s FVG** + 1s OB kullanıldı; bu açıkça vekil ölçümdür. Diğer periyotlarda ikisi de native aynı TF. Bilgi eksikse açık sayılmadı.

24 hissede **348/694 (%50,1)**; aynı veri kapsamındaki şartı sağlamayan teyitler **294/572 (%51,4)**. Adayın periyotları 1s %45,8 (271), 2s %54,9 (164), 4s %52,8 (197), günlük %48,4 (62). 1s vekilini çıkarınca 224/423 (%53,0); 1 Temmuz 2026 sonrası tüm periyotlar %45,9. Aynı teyit **ve destek üstü kapanış** korunup yalnız mesafe değiştirildiğinde, önünde 1 ATR’den yakın karşıt bölge olanlarda **221/434 (%50.9)** önce yukarı. Açık alan grubunu izole eden asıl karşılaştırma budur. Genel üstünlük gözlenmedi.

## 4. Yukarı eğimli formasyon + yakın pozitif BOS + üst periyot hacmi

Canlı oluşum durumunda üst ve alt çizgi eğimlerinin ortalaması >0; **yukarı kırılım şart değil**. Yukarı BOS iç/dış yapı motorunun o mumda teyit ettiği olay. Yakınlık penceresi pilot tercihi: sinyal mumu dahil 1s/2s/4s/günlükte son **10/5/3/2** mum. Üst periyot 1s→2s→4s→günlük→tamamlanmış hafta; son kapanmış üst mum RVOL >0,5×. Bir formasyon kimliği için ilk uygun kapanış sayıldı. Çizgi eğimi ekranın piksel açısı değil, fiyat/zaman eğimidir.

**159/321 (%49,5)** önce yukarı; 157 önce aşağı, 4 belirsiz, 1 süre doldu. Karşılaştırma: ilk pozitif eğim gözlemlerinde **574/1.166 (%49,2)**. Bu kontrol aynı formasyonun farklı bir mumuna denk gelebilir. 4s adaylar 33/60 (%55); günlük yalnız 11 örnek. `MS_EKSIK.csv` bu pilotta boş: yapı motoru hatasıyla dışlanan seri olmadı. Tek başına canlıya almak için yeterli ayrım yok.

## 5. Bir saat hacim söndü; üst periyotlar normal. Fiyatı ne kadar etkiliyor?

**Her periyodun paydası kendi önceki 20 mumunun hacim ortalaması**; güncel mum ortalamaya girmiyor. Alt mum kapanana kadar kapanmamış üst mum yok. 1s `0 < RVOL ≤ 0,30×`, 2s `≥0,80×`, 4s `≥1×` = `dusuk_guclu`. Bu “üst fiyat trendi güçlü” değil, **üst hacim korunuyor** demek. İki kontrol: aynı düşük 1s hacmi fakat hem 2s <0,8 hem 4s <1; aynı güçlü üst koşul fakat normal 1s hacmi (0,8–1,2×). Aynı 1s grubu için bir sinyalden sonraki dört mum tekrarlanmadı. Ufuk **gün değil, 3 ve 4 saatlik mum** (3–4 adet 1s mum).

| Geniş evren, medyan | Olay | O 1s mumun mutlak gövdesi | Sonraki 3 mumda dip | Sonraki 4 mumda dip | 4. kapanışın net değişimi |
|---|---:|---:|---:|---:|---:|
| 1s düşük, üstler normal/güçlü | 3.162 | **0,09** | 0,57 | **0,69** | 0,00 |
| 1s düşük, üstler zayıf | 8.245 | 0,12 | 0,62 | 0,74 | −0,06 |
| 1s normal, üstler normal/güçlü | 17.942 | **0,32** | 0,63 | 0,74 | 0,00 |

Birim sinyal anında dondurulan **1s ATR**; “dip” = sinyal kapanışından en düşük sonraki fiyata aleyhte mesafe (hiç altına inmediyse 0). İlk satırda mum gövdesi %60,2 oranında ≤0,15 ATR. Aynı mumun fitiller dahil aralığı medyan **0,40 ATR**. İleri 4 mumda dip yalnız **%19,4** olayda ≤0,15 ATR; medyan 4 mumluk dip son kapanmış **4s ATR** ile de **0,41**. Net değişimin medyanı sıfır, ama mutlak net değişim 0,65 ATR: “fiyat hiç oynamadı” anlamına gelmez.

Düşük hacim öğle saatlerine yığılabildiğinden ayrıca **aynı hisse + aynı 1s mum saati** için 7–90 gün önceki en yakın kullanılmamış kontrolle eşledik. 1.757 düşük/düşük çiftinde üst hacimler korunurken 4 mumluk dip medyan 0,67, zayıfken 0,73; çift içi fark medyanı **−0,05 ATR**, çift içi net kapanış farkı medyanı sıfır. 2.456 düşük/normal çiftinde üst hacimler korunurken gövde **0,10 / 0,32 ATR**, ileri dip **0,68 / 0,73 ATR**. Bu eşleşme zaman/isim yanlılığını azaltır, volatilite ve haberleri sabitlemez; hacmin nedensel etkisini kanıtlamaz.

Örnek: AKBNK **19 Ekim 2026 13:30** kapanışında 1s/2s/4s hacim **0,30× / 1,02× / 1,23×**; buna rağmen sonraki dört mumda dip **0,78 ATR**. Üst hacimler normal diye geri çekilmenin çok küçük kalacağı garanti değil.

## Karar ve doğrulama sınırları

**Gölge takip için ayır:** nadir temiz geri alış. **Kart bağlamı için ayır:** “düşük hacim yalnız 1s’te mi, üst periyotlarda da mı?” Diğer üç yön kuralını mevcut sayılarla bağımsız alarm yapma. Özellikle dikey/yatay görselini birkaç kullanıcı örneğiyle doğrulamak gerekli. Buradaki ortak bariyer ölçüsü kullanıcının fikrini tanımlayan tek olası başarı ölçüsü değildir.

Yön sorularında aynı sinyal kapanışından sonraki 12 barın ilk ±1 ATR’si (Wilder 14). Çift isabet ve süre sonu paydada, tamamlanmamış ufuk sayılmadı. Birçok hisse aynı piyasa hareketini paylaşır, grupların bazıları örtüşür. Tarih bölmesi 1 Temmuz 2026, kör ileri test değil. Kurumsal aksiyon, kayma, işlem maliyeti ve gerçek Telegram teslimi modellenmedi. Canlı karar kodu veya eşik değiştirilmedi.

[174 hisse kural sayımları](genis/KURALLAR.csv) · [hacim ölçüleri](genis/HACIM.csv) · [eşlenmiş kontroller](genis/HACIM_ESLER.csv) · [geniş evren tarihli adaylar](genis/ADAYLAR.csv.gz) · [24 hisselik pilotun tüm olayları](OLAYLAR.csv.gz) · [pilot kural sayımları](KURALLAR.csv).

```bash
python -m research.bes_alarm_pilotu --cikti var/bes_pilot
python -m research.bes_alarm_ozet --dizin var/bes_pilot
python -m research.bes_alarm_pilotu --genis-stabil-hacim --cikti var/bes_genis
python -m research.bes_alarm_ozet --dizin var/bes_genis
```
