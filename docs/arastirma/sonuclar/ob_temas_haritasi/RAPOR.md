# Order block: büyüklük, kaçıncı temas ve kalan bant

**Temel bulgu:** Geniş OB orijinal bandına daha sık geri dönülüyor. Bu, fiyatın temas kapanışından sonra OB yönünde önce hareket etme ihtimalinin aynı ölçüde arttığı anlamına gelmiyor. İkinci gelişte fiyatın *önceden test edilmiş bölümde mi kaldığı, yoksa kalan banda mı girdiği* ise bölgenin neden hâlâ aktif olduğunu anlatan faydalı bir ayrım.

176 sembol × native 1s/2s/4s/günlük = **704 seri**; **137.530 OB, 204.290 temas epizodu**. Saatlikleri içeren bu evren FVG çalışmasının birebir aynı evreni değildir. 9.445 bölgeye hiç temas yok; 82.246 bölgeye yalnız bir, 28.447’ye iki, 10.308’e üç, 7.084’e dört veya daha fazla ziyaret var. En yüksek gözlenen sayı 18. “Hiç” ve “yalnız” arşiv sonuna veya motorun bölgeyi kaldırmasına kadardır; ilk gün bilinen özellikler değildir.

## 1. Boyut bir bölgenin tekrar izlenmeye değer olup olmadığını anlatıyor

Genişlik = *orijinal* üst−alt / kaynak mumunun Wilder ATR(14)’ü. İlk temas ancak motor bölgeyi tanıdıktan sonraki mumlarda sayılır. Art arda üç mum bantta = bir ziyaret; çıkıp tekrar girmek = ikinci ziyaret.

| Başlangıç genişliği | Bölge | En az 2 ziyaret | En az 4 ziyaret | İlk temasta temiz tepki | İlk temasta yön önce |
|---|---:|---:|---:|---:|---:|
| <0,5 ATR | 18.117 | %21,6 | %1,3 | %32,3 | %47,3 |
| 0,5–<1 ATR | 69.608 | %30,3 | %3,2 | %35,4 | %47,1 |
| 1–<2 ATR | 43.112 | %40,6 | %8,2 | %40,6 | %46,9 |
| ≥2 ATR | 5.519 | **%53,1** | **%18,2** | **%48,7** | **%47,8** |

İlk iki yüzde **tüm bölgeler** üzerinden; son iki yüzde aşağıdaki koşulları sağlayan **ilk temas kapanışları** üzerinden. 1.174 OB’de kaynak ATR’si ölçülemediği için boyut bilinmiyor; genel temas sayımında var. Geniş bandın %70’ini doldurmak mekanik olarak daha zordur. Daha çok ziyaret ve temiz tepki, kendiliğinden fiyat yönü avantajı değildir.

## 2. Temas sırası × genişlik: yönü gerçekten ne kadar ayırıyor?

**Yön önce:** temas mumunun kapanışından 12 sonraki mumda, OB yönüne +1 temas ATR’si ters yönde −1 ATR’den önce mi geldi? Temas mumunun kendi fitilini kullanmadık. Aynı mumda iki eşik görülürse belirsiz; süre dolarsa çözülmedi; her ikisi de paydada. **Temiz tepki:** orijinal banda *yeni* ziyaret başlamadan veya motor bölgeyi kaldırmadan +1 ATR; hedef ve engel aynı bardaysa başarı değil. Bu ikinci ölçü önce ters 1 ATR görülmesine izin verir. Bunlar getiriyi değil fiyat yolunu ölçer.

| Yön önce | 1. temas | 2. temas | 3. temas | 4. ve sonrası |
|---|---:|---:|---:|---:|
| <0,5 ATR | %47,3 | %46,3 | %45,0 | %46,7 |
| 0,5–<1 ATR | %47,1 | %45,8 | %46,7 | %44,1 |
| 1–<2 ATR | %46,9 | %47,0 | %46,2 | %45,3 |
| ≥2 ATR | %47,8 | %44,7 | %47,0 | %44,7 |
| **Tüm genişlikler** | **%47,1** | **%46,2** | **%46,4** | **%45,0** |
| Ölçülen temas | 85.782 | 32.388 | 12.941 | 10.378 |

Toplam **141.489** ölçülebilir kapanış. Paydadan yalnız kapanışta artık aktif olmayan OB’ler, temas ATR’si geçersiz veya 12 ileri mumu eksik olaylar çıkarıldı. Yönlü ölçü fiyatı, motor daha sonra bölgeyi silse bile takip eder. ≥2 ATR’de 2. temasın ilkinden üstün olduğu bir sıralama yok. Temasın **erken** gelmesi de FVG’deki kadar ayırmıyor: ≥2 ATR’de bilinebilirlikten itibaren ilk 3 mum / daha sonra, yön önce %49,4 / %46,7; temiz tepki %48,4 / %48,9.

## 3. İkinci temas neye değdi?

Motor her temas öncesi OB’nin kalan fiyat aralığını tutuyor. Orijinal banda geri dönmek ile daha önce taranmamış banda kadar ilerlemek aynı şey değil. Burada **temas başındaki** kalan sınırları kullandık; kapanıştan sonraki dolumu geriye taşımadık. Sınıra eşitlik kesişim sayılır.

| İkinci ziyaret | Tüm temas | Temas kapanışında hâlâ aktif | Aktif ve ölçülebilenlerde temiz tepki | Aktif ve ölçülebilenlerde yön önce |
|---|---:|---:|---:|---:|
| Yalnız önceden taranmış kısım | 19.590 | 19.590 (%100) | %40,5 (n=19.435) | %46,6 |
| Kalan banda da değdi | 26.249 | 13.076 (%49,8) | %35,7 (n=12.953) | %45,7 |

**Yorum:** %100 bir yön tahmini değil; motorun dolum kuralının beklenen sonucu. Yeni alana ilerlemeyen fiyat bu yolla dolum sınırını aşmaz. Öte yandan kalan banda değen 13.173 OB **o temas mumunda** listeden çıktı. Böyle bir olayı kapanıştan sonra “destek hâlâ tutuyor” diye sunmamak gerekir. Kamuya dönük kart için öneri: temas sayısıyla birlikte orijinal bant, kalan bant ve kapanışta aktiflik verilsin; sayı tek başına güç rozeti olmasın.

**Geriye bakış tuzağı:** Yalnız ileride ikinci kez test edileceğini bildiğimiz ve iki kapanışı da ölçülebilen 32.286 bölgeyi seçince, ilk temasta “yön önce” %69,0 görünür; tüm ölçülebilir ilk temaslarda ise %47,1’dir. İlk kapanışta ikinci ziyaretin gerçekleşeceği bilinmez. İlk ziyarette bir kez işe yaramış olması da tekrar garantisi değil: ilk +1 ATR üstünlüğünün ikinci temastan *önce* kesinleştiği örneklerde ikinci temas yön önce oranı 1 Temmuz 2026 öncesi %47,0, sonrasında %43,2.

## 4. Aynı bölgede saat saat ne oldu?

**AKBNK · 4 saat · düşüş OB’si 65,05–67,50 (2,31 ATR).** Kaynak 22 Ekim 2026 13:00; bölge motorca ancak **23 Ekim 13:00** etiketli mumda bilinebilir.

| İstanbul mum etiketi | Ziyaret | Kapanış | Gözlenen hareket |
|---|---:|---:|---|
| 26 Ekim 17:00 | 1 | 65,00 | 27 Ekim 09:00 mumunda aşağı 1 ATR önce görüldü. |
| 27 Ekim 13:00 | 2 | 64,50 | Kalan bant **65,65–67,50**; bu mum yalnız eski kısmı test etti. 28 Ekim 09:30 mumunda aşağı 1 ATR önce geldi. |
| 4 Kasım 09:00 | 3 | 66,55 | Bu kez kalan banda girdi. Motor sonraki hedefe varmadan bölgeyi kaldırdı; 6 Kasım 09:00 mumunda **ters** 1 ATR önce görüldü. |

**Karşı örnek — GARAN · 4 saat · düşüş OB’si 135,50–139,90 (2,24 ATR).** 3 Temmuz 2026 17:00 etiketli mumda bilinebilir. **7 Temmuz 09:00** ikinci ziyarette kapanış 134,40; aynı gün 13:00 mumunda önce **ters** 1 ATR. Buna karşılık **27 Ağustos 09:00** dördüncü ziyarette kapanış yine 134,40 ve aynı gün 17:00 mumunda önce **aşağı** 1 ATR. Dokuzuncu ziyarette (4 Kasım) ters taraf önce geldi. “İki temas gördüyse bir daha çalışmaz” da doğru bir tanım değil.

**Sınırlar:** Bunlar sağlayıcının İstanbul mum etiketleri, kesin işlem/fitil dakikası değil. Aynı hisse ve zaman dilimindeki birden fazla OB, hatta aynı bölgenin yakın ziyaretleri aynı fiyat hareketini paylaşabilir. Olaylar bağımsız işlem değildir. Alarmsız eşlenmiş piyasa tabanı veya yeni tarihlerde ileri test yapılmadı; %50 ile farkı getiri/kayıp olarak okumayın.

[Boyut, periyot ve ziyaret sayısı](BOLGELER.csv) · [Bütün kıyaslar ve paydalar](KIYAS.csv) · [Kalan bant ve aktiflik](KALAN_BANT_OMRU.csv) · [≥2 ATR OB’lerde 12.085 tarihli ziyaret](BUYUK_OB_TEMASLARI.csv.gz).

```bash
python -m research.ob_temas_haritasi --cikti var/ob_temas
python -m research.ob_temas_ozeti --girdi var/ob_temas --cikti var/ob_rapor
```

İlk komut `OB.csv.gz` (hiç temas almamış olanlar dahil) ve `TEMAS.csv.gz` (tüm genişliklerde her ziyaret) üretir. Canlı sağlayıcı ve Telegram kullanılmaz.
