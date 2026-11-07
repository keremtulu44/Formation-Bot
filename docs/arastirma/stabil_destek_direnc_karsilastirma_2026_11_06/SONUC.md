# Normal Stabil desteği ile ters direnç: benziyor mu?

**Kısa cevap: Evet, bazı temel davranışlar ve kırılma sonrası yol benziyor; ama bütün ayrıntılar ve oranlar birebir aynı değil.** Aynı veride ve tanımla bakınca temel TEST tepkileri yakın. Çizgi–fiyat sırasındaki bazı dallar da benzer, fakat uzaklaşma yarışı ve basamak/yataylaşma alt gruplarında farklar var. Bunlar betimsel sonuçlar; eşitliği, işlem avantajını veya nedenselliği kanıtlamıyor.

Karşılaştırma 174 hissenin aynı arşivinde yapıldı. Normal destek gerçek günlük OHLC üzerinden native Stabil desteği; direnç aynı günlük yapının matematiksel tersi. Eski 100 hissenin tamamı bu evrene dahil. Aşağıdaki ana tabloda dönem **2026**, ufuk olaydan sonraki **8 kapanmış 4 saatlik bar**.

## 1. İlk tepki: yakın, fakat aynı davranış garantisi değil

TEST, çizgiye yaklaşma bandına ilk giriştir; bütün TEST'ler gerçek temas değildir. Olay kapanışından sonra hangisinin önce görüldüğüne bakılır: tepki yönünde 1 olay-4s-ATR (destekte yukarı, dirençte aşağı) veya ters yönde 1 ATR.

| | Geçerli olay / hisse | Tepki yönü önce | Ters yön önce | Aynı mum belirsiz | Hiçbiri |
|---|---:|---:|---:|---:|---:|
| Normal destek | 1.616 / 162 | **%41,3 yukarı** | %51,6 aşağı | %1,9 | %5,2 |
| Ters direnç | 1.241 / 161 | **%42,1 aşağı** | %51,6 yukarı | %3,1 | %3,2 |

Gerçek çizgi temasıyla sınırlayınca 8 barda tepki yönü önce: destekte **%40,1** (1.028 olay), dirençte **%43,8** (889 olay). Gerçek temasın **aynı mumda** güvenli tarafta kapanması destek için 550/1.028 (**%53,5**), direnç için 500/889 (**%56,2**). Mum içindeki temas–kapanış sırası bilinmez.

Farklı olay kümelerini biraz daha yaklaştırmak için aynı hisse, çeyrek, seans, çizgi mesafesi ve önceki hareket kovalarında; aralarında en az 8 bar olan ve tekrar kullanılmayan olaylar eşleştirildi. **178 geçerli çiftte** destek tepkisi %47,2, direnç tepkisi %46,1; fark **+1,1 yüzde puan**, hisse-kümeli %95 bootstrap aralığı **−9,2 ile +11,6 puan**. Aralık geniştir: bu, farkın sıfır olduğunu ya da eşdeğerliği ispatlamaz.

## 2. Eski destek sonucuyla aynı tip uzaklaşma yarışı

Eski A01 tarifine yakın ölçüm: fiyat çizginin güvenli tarafında **1–2 günlük ATR** uzakta; takip eden **24 × 4s bar** içinde çizginin fiyat yönünde takip etmesi veya fiyatın eski çizgiye 0,15 günlük ATR'ye kadar yaklaşması yarıştırılır. Bu, yukarıdaki 8 bar / 4s ATR TEST'inden farklıdır.

| 2026 | Geçerli checkpoint | Çizgi takip önce | Fiyat eski çizgiye yaklaşma önce | Ters basamak önce | Aynı-bar | Hiçbiri |
|---|---:|---:|---:|---:|---:|---:|
| Destek | 16.597 | **%35,4** | %32,6 | %8,9 | %0,4 | %22,6 |
| Direnç | 13.947 | **%29,2** | %36,8 | %12,5 | %1,4 | %20,0 |

Burada sıralama tersine dönüyor: destekte takip, dirençte fiyat dönüşü az farkla daha sık. Bunlar farklı anlarda oluşmuş ve sıkça üst üste binen checkpoint'lerdir; farkın nedenini veya kesin üstünlüğü göstermez.

Eski 100 hisse kaydındaki aynı A01 kovası yaklaşık **%33,49 takip / %31,74 fiyat dönüşü** idi. Yeni, daha sıkı kalite ve tam-24-bar koşullarında eski 100 hisselik evrenin geçerli **95 hissesinde**, iki dönem birlikte destek **%34,7 / %31,7** (n=16.931), ters direnç **%28,6 / %39,0** (n=14.883). Eski kayıt ve yeni filtrelerin paydaları aynı değildir; bu yakınlık tam yeniden üretim veya bağımsız doğrulama sayılmaz.

## 3. Kırılmadan sonra aynı epizotta hangi yol izlendi?

Bu ek yol analizi ana sonuçlar görüldükten sonra planlandı. Başlangıç, fiyatın önceden bilinen çizgiyi kapanışla kırdığı 4s mumdur. Ondan sonraki **tam ve temiz 24 × 4s bar** izlenir; bu ufuk yeni bir alarm beklemesi veya ek teyit kuralı değildir.

| 2026 kırılma sonrası ilk yol | Destek: 1.467 geçerli | Direnç: 1.233 geçerli |
|---|---:|---:|
| Fiyat eski çizginin güvenli tarafına önce döndü | **%63,3** | **%69,4** |
| Önce çizgi ters yönde taşındı: destek aşağı / direnç yukarı | **%16,1** | **%12,5** |
| İkisi aynı 4s checkpoint'te; sıra belirsiz | %1,9 | %2,8 |
| 24 barda ikisi de görülmedi | %18,7 | %15,2 |

İlk olarak **çizginin taşındığı** dalın devamında, eski çizgiye fiyat dönmeden veya çizgi kimliği yeniden değişmeden aday yataylaşmaya ulaşanlar destek için **141/236 (%59,7)**, direnç için **102/154 (%66,2)**. Bu yüzdelerin paydası bütün kırılmalar değil, yalnız çizginin ilk taşındığı daldır. Aday yataylaşmaya ulaşma, fiyatın kalıcı tutunduğunu göstermez.

İlk olarak **fiyatın eski çizgiye döndüğü** dalda, kalan pencere içinde eski çizgiyi yeniden kıranlar destek için **531/928 (%57,2)**, direnç için **488/856 (%57,0)**. Kalan takip süresi her olayda aynı değildir; aynı-bar çakışmalar ve çizginin önce değiştiği durumlar ayrıca sayılmıştır. Yani bir kez geri almak, kalıcı başarı demek değildir.

Aynı hisseden seçilmiş, sonuçları temsil ettiği iddia edilmeyen iki somut tarihli yol [örneklerdedir](ORNEK_YOLLAR.md). Tüm dallar, sayılar ve 2025/2026 ayrımı [yol tablolarındadır](yol_bulgulari.md).

## 4. Kullanıcının basamak / yataylaşma gözlemi

Eski F01'e yakın ortak tarifte son 4 × 4s fiyat hareketi tepki yönünde >0,3 günlük ATR olmalı; ardından ilk ±1 günlük ATR'ye bakılır. **2026'da:**

| Aday durum | Geçerli checkpoint | Tepki yönü önce | Ters yön önce |
|---|---:|---:|---:|
| Destek aşağı basamak | 2.823 | %33,2 | %25,6 |
| Destek iniş sonrası düz | 9.376 | %37,7 | %28,2 |
| Direnç yukarı basamak | 3.311 | %37,3 | %37,5 |
| Direnç çıkış sonrası düz | 11.235 | %33,6 | %28,5 |

Bu alt gruplarda sıralama her iki tarafta aynı değil. Ayrıca 2025 destek kesitinde tepki-yönü-önce, basamak/düz için %40,4/%33,6 iken 2026'da %33,2/%37,7; bu dönem değişimi karar vermek için yeterince kararlı olmadığını gösterir. Aynı-bar ve hiçbiri de paydada kalır.

**Önemli:** Bunlar mevcut native aday sınıflandırıcının basamak/yataylaşma **proxy**'leridir. Kullanıcının grafikteki “dikey/yatay” tanımıyla birebir eşleştiği henüz doğrulanmadı; stepline'ın dikey bağ çizgisi kalıcı dikey rejim sayılmadı. Native teyide keyfî 2/3/5 bar bekleme eklenmedi.

## Sınırlar ve dosyalar

- Kırılma ve tepki grupları eşlenmiş tek olaylar değil; hisse/gün etkileri, dönem, trend, eksik gözlem, kurumsal işlemler ve çoklu karşılaştırmalar oranları etkileyebilir. Aynı bar için iki eşik görülürse sırası belirsiz bırakıldı.
- Arşiv ve önceki direnç sonuçları zaten incelenmişti: 2026 **kör ya da bağımsız doğrulama değil**. Eski 48 sorunun yalnız A01, B04, C02 ve F01 tariflerine yakın simetrik değerlendirmeler yapıldı; 48 sorunun tamamı yeniden üretilmedi. C02 eski kodda günlük temas sırasını 4s checkpoint'e taşır.
- Günlük native tersleme yapıldı; yeni 4s olayları araştırma ölçütleridir, canlı 4s ok/alarm motorunun birebir tersi oldukları iddia edilmez. Üretim veya Telegram kuralları değiştirilmedi.

[Detaylı ana rapor](RAPOR.md) · [Bütün karşılaştırma tabloları](toplu_bulgular.md) · [Aynı epizotta yol tabloları](yol_bulgulari.md) · [Somut örnekler](ORNEK_YOLLAR.md) · [Doğrulama](DOGRULAMA.md) · [Ana plan](PLAN.md) · [Ek yol planı](YOL_PLANI.md)
