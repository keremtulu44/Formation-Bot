# Hareket haritası 1 — Hacim hangi doğru uyarıyı sildi?

**Karar:** Bu hacim formülünü genel alarm filtresi yapma. Aynı kart bütçesinde kart başına hedef isabeti bir miktar yükseldi, fakat farklı hareketleri erken yakalama artmadı. Sonuç hacmin her kullanımını değil, burada sınanan sıralamayı ilgilendiriyor.

## Aynı bütçe, iki farklı soru

24 sabit BIST hissesi, native 1 saat / 4 saat / günlük. Son tarih kesiti 1 Temmuz–18 Kasım 2026, 99 arşiv seansı. Formasyon sütunu Dengeli Argent’in o kapanışta ilk kez teyit ettiği yönlü kırılımdır. Bu **botun tamamı veya gönderilmiş Telegram kartları değildir**: OB, FVG, BOS, Stabil, birleşik yön kararı ve teslimat bu ilk referansta yok. Fiyat ve fiyat+hacim de canlı politikalar değil, izole araştırma sıralamalarıdır.

| Son kesit | Formasyon teyidi (referans, kotasız) | Fiyat sırası | Fiyat + hacim sırası |
|---|---:|---:|---:|
| Kart | 594 | 985 | 985 |
| Kart kapanışından +2 yön ATR önce / ölçülen | 206/575 | 283/940 (%30,1) | 295/940 (%31,4) |
| Ters 1 ATR önce / süre sonu / henüz ölçülemez | 323 / 46 / 19 | 569 / 88 / 45 | 558 / 87 / 45 |
| 3.475 ayrı seri-hareketinde erken | 107 | **116** | **114** |
| Geç / hiç yönlü işaret yok | 148 / 3.220 | 240 / 3.119 | 231 / 3.130 |

Kart isabeti **kartın kendi fiyatından**, kapsam **hareketin ilk çapasından** hesaplanır. Bir kart kendi fiyatından çalışabilir ama hareketin önemli kısmı çoktan gerçekleşmiş olabilir. Formasyon referansının bütçesi farklıdır; onu aynı bütçeye sahip üçüncü rakip sayma. Yönlü hedef iki kat uzaklıktadır, %50 tarafsız başarı eşiği değildir.

## Filtrenin ödediği bedel

- Fiyatla erken bulunan 116 hareketin **81’i** yine erken, **3’ü** geç, **32’si** tamamen kaçtı. Buna karşılık hacim, önceden geç olan **2** ve tamamen kaçan **31** hareketi erkene aldı. Net: **33 kazanılan, 35 kaybedilen erken uyarı**.
- Değişen **161’er** kartın ikisinde de 9’ar eksik ufuk var. Dışarı atılan 152 ölçülebilir kartın **44’ü hedef**, 97’si ters, 11’i süre. İçeri alınan 152’nin **56’sı hedef**, **86’sı ters**, 10’u süre. Yalnız 56 doğru örneği göstermek yanıltır.
- **Aynı anda, aynı yönde, aynı yapıda karşı örnek:** 7 Temmuz 2026, 13:00. İki 4s mum da önceki 20 mumun tepesinin üstünde kapandı. TUPRS 254,00; hacim aynı saat normalinin **1,07×**’i, gövde/aralık %81. ASTOR 328,75; hacim **1,55×**, gövde/aralık %84. Fiyat sırası TUPRS’ı, hacimli sıra ASTOR’u seçti. **TUPRS önce +2 ATR, ASTOR önce −1 ATR** gördü. Yani iki temiz kırılımdan daha yüksek hacimlisini seçmek bu kez yanlış oldu.
- Eşik duyarlılığı: 1,5 ATR hedefte erken **127 → 131** (4.750 hareket); 2 ATR’de **116 → 114**; 2,5 ATR’de **119 → 122** (2.632 hareket). Önceki kesitte 2 ATR’de **419 → 396**. Üstünlük hedef ve döneme dayanıklı değil. Aynı arşivle daha önce çalışıldı; son kesit bağımsız canlı test değildir.

## Nerede sessiz kalıyor?

Son kesitte hacimli sıranın doğru yönlü kart vermediği 3.130 hareketin:

| Hedefe ulaşılmadan önce | Hareket |
|---|---:|
| Ayrılan seans diliminde doğru renkli en az bir aday mum vardı, sıralamada seçilmedi | **2.634** |
| Ayrılan seans dilimi vardı, o hissede doğru renkli aday yoktu | 306 |
| Ayrılan hiçbir seans dilimi yoktu | 190 |

Bu **2.634'ü hacim tek başına eledi** demek değil: sıralama rekabeti ve zaman bütçesi birlikte işliyor. Başlangıç ailesine göre toplam/erken: önceki sınır kırılımı **205/15**, fitille geri alım **244/9**, trend içinde mola **245/5**, diğer **2.781/85**. Başlangıç etiketi hareketin gelecekte oluşturacağı formasyon değil. “Diğer” çok büyük; bu hâliyle belirli bir yapının en çok kaçtığını söylemek erken. Dönüşlerin veya sessiz başlangıçların bir kısmı basit bir mum rengine hiç uymaz. Sıradaki çalışma: pozitif ve negatif örnekleri birlikte kullanarak bu grubu ayırmak; tüm bot kanallarını gerçek kapanış yönüyle eklemek. Mevcut sıralamaya yeni yasak koymak değil.

## Nasıl sayıldı?

- Çapa kapanışındaki Wilder ATR(14) sabit. Gelecek 12 mumda yönlü hedefe ters 1 ATR’den önce varılmalı. Aynı mumda iki sınır görülürse sıra bilinmiyor, pozitif sayılmaz. Yukarı ve aşağı ayrı. İlk uygun çapadan ilk hedef mumuna kadar aynı hisse/periyotta ikinci hareket yazılmaz; hedef geçildikten sonraki devam yeni bir bölüm olabilir. Farklı periyotlar/piyasa günleri bağımsız değildir. 12 ileri mumu olmayan kartlar kart adedinde kalır, isabette yoktur. Son arşiv günü ve ilk 50 mum ölçümden ayrı.
- Erken/geç: çapa dahil hedef mumundan **önceki** ilk aynı yönlü kart; o kapanışa kadar yönlü hedef mesafesinin yarısına fitille dahi gelinmemişse erken. Hedef mumunun kapanışındaki alarm geriye dönük yakalama sayılmaz. Çapa öncesindeki eski kartları bu harekete bağlamıyoruz. Bazı hedefler sonraki açılışta geçilir; kârlı bir uygulanabilir giriş varsayılmıyor.
- Fiyat sırası = mutlak gövde / ATR + gövde / mum aralığı. Aday yönü mum rengi; doji yok. Hacimli sırada ek terim = `clip(log2(RVOL), −2, 2) × (gövde/aralık − 0,5)`. Hacim kendi hissesinin aynı TF ve aynı açılış-kapanış saatli önceki 20 mumunun medyanına göre; günlükte önceki 20 gün. Geçmiş yetersizse ek terim sıfır. Fiyatı ileri taşıyamayan yüksek hacmi otomatik artı saymıyoruz. İki sıra aynı anda, aynı adaylardan seçer; eşitlikte sembol adı. Eşikler fit edilmedi.
- Günde toplam **en fazla 10**: 1s 10:30/12:30/14:30/16:30’da birer; 4s 13:00/17:00’de birer, 18:00’de iki; günlük kapanışta iki. Kullanılmayan kota ileriye taşınmaz. 99 günde iki sırada da 985 kart, en yoğun gün 10. O akşamın tüm kartlarını sabah bilerek geriye dönük seçim yok. Saat kotaları ürün kararı değil, iki sıralamaya eşit maliyet yükleyen deney düzeni. Ücret, kayma, endeks düzeltmesi, stokastik anlamlılık veya bot teslimatı ölçülmedi.

[Değişen kartların tek tek sonuçları](DEGISEN_KARTLAR.csv) · [kapsam kayıpları](KAPSAM_KAYBI.csv) · [kart sayımı](KART_SAYIMI.csv) · [tarihli hareketler](HAREKETLER.csv.gz) · [tüm karar kapanışları](KARARLAR.csv.gz).

Yeniden üret: `python -m research.hareket_kapsam && python -m research.hareket_kapsam_ozet`.
