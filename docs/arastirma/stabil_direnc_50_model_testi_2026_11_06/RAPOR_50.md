# Direnç, anlattığın destek yolunun tersi gibi çalışıyor mu? — 50 hisse

50 hisse, eski 100 hisselik destek örnekleminden sabit SHA256 sırasıyla ve tek tek sonuçlara bakılmadan seçildi. Aynı hisselerin aynı arşivinde normal native destek ve ters native direnç ölçüldü. Kullanıcının onayladığı karşıt yol esas alındı; sabit direnç ve yukarı takip eden direnç ayrı incelendi. Bu çalışma daha önce sonuçları görülmüş veriye dayandığından kör doğrulama değildir.

## 1. Temas ve sonraki tepki

TEST çizgiye yakınlık bandına girme olayıdır; gerçek temastan ayrı tutulur. Tepki yönü destekte yukarı, dirençte aşağıdır. Olaydan sonraki ilk ±1 **4s ATR**, 8 × 4s bar:

| Dönem / taraf | Geçerli | Hisse | Tepki önce | Ters yön önce | Aynı-bar | Hiçbiri |
|---|---:|---:|---:|---:|---:|---:|
| 2025 / Destek | 288 | 45 | %41.3 | %51.7 | %1.4 | %5.6 |
| 2025 / Direnç | 331 | 47 | %42.9 | %49.5 | %1.5 | %6.0 |
| 2026 / Destek | 492 | 46 | %40.2 | %52.2 | %2.6 | %4.9 |
| 2026 / Direnç | 350 | 45 | %41.7 | %51.4 | %4.0 | %2.9 |

2026'da gerçek temas, aynı mumun güvenli kapanışı ve temas sonrası 8-bar yarışı:

| Taraf | Tüm TEST | Geçerli | Gerçek temas | Temas & güvenli kapanış | % / gerçek temas | Sonraki tepki önce |
|---|---:|---:|---:|---:|---:|---:|
| Destek | 573 | 492 | 322 | 174 | %54.0 | %37.3 |
| Direnç | 395 | 350 | 250 | 133 | %53.2 | %42.4 |

İlk sütundaki tüm olaylar ile geçerli olaylar farklıdır; yakınlık ve gap gerçek temas sayılmaz. Mum içindeki temas ve kapanışın sırası bilinmez. Yukarıdaki son sütunun paydası güvenli kapanışlar değil **tüm gerçek temaslar**dır.

Gerçek temasları aynı mum kapanışına göre ayırıp sonraki 8 × 4s ilk ±1 olay-4s-ATR yarışını ayrıca izleyince:

| Taraf | Temas mumunun kapanışı | n | Hisse | Tepki önce | Ters yön önce | Aynı-bar | Hiçbiri |
|---|---|---:|---:|---:|---:|---:|---:|
| Destek | Güvenli | 174 | 44 | 73 (%42.0) | 88 (%50.6) | 2 (%1.1) | 11 (%6.3) |
| Destek | İhlal | 148 | 43 | 47 (%31.8) | 91 (%61.5) | 5 (%3.4) | 5 (%3.4) |
| Direnç | Güvenli | 133 | 42 | 57 (%42.9) | 67 (%50.4) | 1 (%0.8) | 8 (%6.0) |
| Direnç | İhlal | 117 | 45 | 49 (%41.9) | 60 (%51.3) | 8 (%6.8) | 0 (%0.0) |

Güvenli kapanış, destekte çizgiye eşit/üst, dirençte eşit/alt; ihlal kapanışı kesin ters taraftır. Tepki önce demek, garantili işlem başarısı veya sürekli düşüş/yükseliş demek değildir. Bu alt gruplama keşifseldir; eşleştirme yapılmamıştır.

53 geçerli çift / 32 hisse: destek %45.3, direnç %45.3; fark +0.0 puan, hisse-kümeli %95 bootstrap -17.5…+16.7 puan. Bu aralık denklik veya nedensellik kanıtı değildir.

## 2. Fiyat uzaklaşırsa önce çizgi mi takip eder, fiyat mı eski çizgiye döner?

2026, fiyat başlangıç çizgisinden 1,5 **önceki 4s ATR** uzaklaşma eşiğini geçtikten sonraki 8 × 4s bar; dönüş eski çizgiye kapanış:

| Taraf | Geçerli | Hisse | Çizgi takip önce | Fiyat eski çizgiye önce | Aynı-bar | Hiçbiri |
|---|---:|---:|---:|---:|---:|---:|
| Destek | 506 | 46 | %2.4 | %19.6 | %0.2 | %77.9 |
| Direnç | 345 | 46 | %1.2 | %22.0 | %0.0 | %76.8 |

Farklı eski A01 tarifinde fiyat 1–2 **günlük ATR** uzaktayken 24 × 4s yarışılır; burada fiyat dönüşü eski çizgiye 0,15 günlük ATR yakınlık demektir:

| Taraf | Geçerli | Hisse | Takip önce | Fiyat yaklaşma önce | Ters basamak önce | Aynı-bar | Hiçbiri |
|---|---:|---:|---:|---:|---:|---:|---:|
| Destek | 4850 | 46 | %33.8 | %32.8 | %9.4 | %0.3 | %23.6 |
| Direnç | 4109 | 46 | %31.2 | %34.1 | %11.0 | %2.6 | %21.1 |

Bunlar farklı ATR ve ufuk tanımlarıdır; yüzdeler birbirine çıkarılmaz. 24-bar checkpoint'ler birbirleriyle sıklıkla örtüşür. Kısa ufukta native 4 günlük pivot teyidi, çizgi takip olayını doğal olarak geciktirebilir.

## 3. Kırılma → sabit çizgiye dönüş veya çizginin takip etmesi

2026'da aynı kırılma epizodunu 24 × 4s izleyince ilk yol:

| Taraf | Geçerli | Hisse | Fiyat eski çizgiye önce | Ters çizgi basamağı önce | Aynı-bar | Hiçbiri |
|---|---:|---:|---:|---:|---:|---:|
| Destek | 441 | 46 | %63.0 | %16.1 | %1.6 | %19.3 |
| Direnç | 371 | 46 | %71.2 | %14.0 | %3.2 | %11.6 |

*Çizgi ters yönde önce taşınmışsa*, aynı çizgi kimliği altında hangi olay önce geldi? Payda yalnız bu dala giren olaylardır:

| Taraf | Dal n | Hisse | Düz proxy önce | Eski çizgiye dönüş önce | Aynı-bar | Hiçbiri |
|---|---:|---:|---:|---:|---:|---:|
| Destek | 71 | 36 | %60.6 | %7.0 | %7.0 | %23.9 |
| Direnç | 52 | 35 | %67.3 | %3.8 | %7.7 | %21.2 |

*Fiyat eski çizginin güvenli tarafına önce döndüyse*, kalan pencerede hangi olay önce geldi? Payda yalnız önce fiyatın döndüğü daldır:

| Taraf | Dal n | Hisse | Yeniden kırılma önce | Çizgi ters basamak önce | Aynı-bar | Hiçbiri |
|---|---:|---:|---:|---:|---:|---:|
| Destek | 278 | 46 | %57.9 | %34.2 | %2.9 | %5.0 |
| Direnç | 264 | 45 | %61.4 | %34.5 | %2.3 | %1.9 |

Dalların kalan izleme süreleri eşit değildir. Tablo bazı nadir çizgi-kimliği/değişim sınıflarını sütunlara sığdırmaz; tam dağılım [yol tablolarında](yol_bulgulari.md). Fiyatın bir kez eski çizgiye dönmesi kalıcı tutunma veya işlem başarısı demek değildir.

**Sabit eski çizgi örneği — AKBNK:** 6 Ocak 2026 17:30 kapanışı 74,15 ile 73,65 direncinin üstündeydi. 7 Ocak 13:30 kapanışı aynı çizginin altında 73,40'a döndü; çizgi hâlâ 73,65 iken 9 Ocak 18:00 kapanışı 73,75 ile tekrar üzerine çıktı. Bu tek bir seçilmiş epizottur, genellenemez.

## 4. Fiyat çizginin hangi tarafındayken basamak / düz proxy?

Aynı tarihte bilinen, eski F01'e yakın örnek: son 4 × 4s hareket tepki yönünde >0,3 günlük ATR. Gelecek 8 × 4s ilk ±1 **günlük** ATR; 2026. Güvenli taraf = destekte çizgiye eşit/üstü, dirençte çizgiye eşit/altı; ihlal kapanışı kesin ters taraftadır:

| Taraf | Aday rejim | Fiyat/çizgi | Geçerli | Hisse | Tepki önce | Ters yön önce | Aynı-bar | Hiçbiri |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Destek | Ters basamak | Güvenli | 470 | 46 | %44.9 | %23.0 | %0.4 | %31.7 |
| Destek | Ters basamak | İhlal | 420 | 36 | %29.8 | %19.5 | %0.7 | %50.0 |
| Destek | Sonrası düz | Güvenli | 2698 | 46 | %33.7 | %31.8 | %1.1 | %33.4 |
| Destek | Sonrası düz | İhlal | 10 | 8 | %30.0 | %20.0 | %0.0 | %50.0 |
| Direnç | Ters basamak | Güvenli | 490 | 46 | %35.9 | %39.4 | %0.2 | %24.5 |
| Direnç | Ters basamak | İhlal | 450 | 37 | %34.2 | %38.2 | %0.0 | %27.6 |
| Direnç | Sonrası düz | Güvenli | 3015 | 46 | %32.5 | %29.5 | %0.2 | %37.9 |
| Direnç | Sonrası düz | İhlal | 6 | 5 | %50.0 | %50.0 | %0.0 | %0.0 |

Bu karşılaştırmada aynı-bar ve hiçbiri paydada. "Ters basamak" destek aşağı / direnç yukarıdır. Rejimler grafikteki dikey/yatayın doğrulanmış karşılığı **değil**. Özellikle düz proxy, ilgili native günlük kapanışın güvenli tarafta olmasını içerir; bu ilişkiyi bağımsız kanıt diye okumamak gerekir. 2026'da aday düzken fiyatın ihlal tarafında olduğu direnç grubu yalnız **6 checkpoint / 5 hisse**, destek grubu 10 checkpoint / 8 hisse; kullanıcının tarifindeki durumu bunlarla kesinleştiremeyiz. Alt gruplar ve checkpoint'ler bağımsız değildir.

## 5. Fiyat koşuluna bağlamadan yeni sabit çizgiyi izleme

Kırılmadan sonra çizgi ters yönde **önce** taşındığında, aday yatay rejimi filtrelemeden aynı native çizgi kimliği ve fiyatın konumu izlendi. İlk taşınmadan sonraki kalan 24-bar pencerede fiyatın yeni çizgiye göre güvenli/ihlal durumunun değişmesi / çizgi kimliğinin önce değişmesi (güvenli tarafa dönüş çizgiye eşit kapanışı da içerir):

| Taraf | İlk taşınmada fiyat | n | Hisse | Fiyat geçişi önce | Çizgi değişimi önce | Aynı-bar | Hiçbiri | Kalan bar yok |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Destek | İhlal tarafında | 6 | 6 | 5 | 0 | 0 | 1 | 0 |
| Destek | Güvenli tarafta | 65 | 35 | 16 | 3 | 0 | 40 | 6 |
| Direnç | İhlal tarafında | 6 | 6 | 6 | 0 | 0 | 0 | 0 |
| Direnç | Güvenli tarafta | 46 | 32 | 11 | 3 | 0 | 24 | 8 |

Bu, mevcut native seviyenin sabit kalmasıdır; çizginin grafikte kullanıcının kastettiği "yatay" duruma geçtiğini ispatlamaz. Fiyat yeni direncin üstündeyken taşınan **6** olayın 6 tanesinde fiyat kalan pencerede eşit/alt, 5 tanesinde kesin alt kapandı; ilk eşit/alt kapanışın ardından 4 tanesinde çizgi kimliği değişmeden önce tekrar üstte kapandı. Bu küçük gruptan genel oran çıkarılmamalıdır. Aşamalardaki süreler farklı, aynı-bar ve kalan süre olmaması ayrı. Ayrıntı [sabit çizgi yollarında](sabit_cizgi_yollari.md).

**Somut örnek — EFOR:** 23 Temmuz 2026 17:30'da kapanış 17,76 iken eski direnç 17,70'ti. 28 Temmuz 13:30'da yeni teyitli çizgi 19,53, kapanış 19,80 idi. Çizgi kimliği korunurken 3 Ağustos 13:30 kapanışı 19,05 ile kesin altına geçti; özgün 24-bar pencere bitene kadar yeni çizginin üstünde kapanış görülmedi. Bu bir fiyat/çizgi yolu örneğidir; görsel "yatay" teyidi veya işlem önerisi değildir.

## 6. Yeni/uzun düz aday çizginin kırılması

2026, güvenli tarafta ve aynı 0–2,5 günlük ATR mesafe bandındaki eski B04'e yakın checkpoint'ler: başlangıçta dondurulan çizginin sonraki 8 × 4s barın **herhangi birinde kapanışla** ihlali:

| Taraf | Aday rejim | Geçerli | Hisse | İhlal | İhlal % |
|---|---|---:|---:|---:|---:|
| Direnç | Uzun düz proxy | 78 | 13 | 11 | %14.1 |
| Direnç | Yeni düz proxy | 1132 | 45 | 273 | %24.1 |
| Destek | Uzun düz proxy | 361 | 22 | 75 | %20.8 |
| Destek | Yeni düz proxy | 1131 | 45 | 262 | %23.2 |

Yeni-düz ve uzun-düz mevcut araştırma sınıflandırıcısının yaşa dayalı proxy'leridir; bu sınıfları yeni canlı bekleme/teyit kuralı yapmak istenmiyor. Özellikle küçük hisse sayılı gruplardan kesin sonuç çıkarılmaz; fiyat mesafesi ve geçmiş yolu tamamen eşleştirilmiş değildir.

## Sonuç nasıl kullanılmalı?

- Sayısal karşılaştırma, hangi ters davranışın **görüldüğünü ve nerede ayrıştığını** gösterir; tek başına tüm dönemlerde simetri veya işlem avantajı kanıtı değildir.
- Bu 50 hisse önceki sonuçları da görülmüş eski 100 hisselik kolayda örneklemden seçildi; kör/bağımsız dış doğrulama yok. Tekrarlanan olaylar ve ortak piyasa günleri bağımsız değildir.
- Ters günlük çekirdek ile kullanıcı görselindeki dikey/yatay eşleşmesi henüz doğrulanmadı; küçük görsel deney kullanıcı daha sonra istediğinde ayrıca yapılabilir. Native teyide keyfî 2/3/5 bar bekleme eklenmedi.
- **Direnç canlıda aktifleştirilmedi.** Yeni grafik, alarm veya Telegram değişikliği yok; sonuç ve sınırlamalar kullanıcıyla değerlendirildikten sonra ayrıca karar gerekir.

[Plan](PLAN.md) · [50 hisse seçimi](selection.json) · [Tüm eş-kural tabloları](toplu_bulgular.md) · [Aynı epizot yol tabloları](yol_bulgulari.md) · [Sabit çizgi yolları](sabit_cizgi_yollari.md) · [Seçilmiş DOCO örnekleri](../stabil_destek_direnc_karsilastirma_2026_11_06/ORNEK_YOLLAR.md) · [Makine özeti](focused_summary.json) · [Doğrulama](DOGRULAMA.md)
