# Ek yol testi — kırılmadan aynı epizodun devamına

Bu ek plan **ana iki-taraflı sonuçlar görüldükten sonra**, bu ek koşudan önce
hazırlandı; keşifseldir ve ön-kayıt/kör doğrulama değildir. Amaç yalnız ayrı
kırılma ve üst/alt kesişimlerini saymak yerine kullanıcının şu dizisini **aynı
epizotta** izlemektir: kırılma → eski çizgiyi fiyat geri alır **veya** çizgi
ters yönde yeniden yerleşir → aday yataylaşma / yeniden kırılma.

## Başlangıç ve sansür

- Ana karşılaştırmada tanımlanan gerçek, kapanmış 4s kırılma: destekte aşağı,
  dirençte yukarı kapanış; günlük seviye 4s mumunun başında biliniyor. Önceki
  bar güvenli taraftadır. Başlangıç seviyesini ve kimliğini dondur.
- 2026 ve 2025 ayrı; eski 100 hissenin aynı arşivdeki kesişimi ayrıca.
- Kapanıştan sonraki **24 adet 4s bar**, eski A01/E02 ile aynı gözlem ufku.
  Bu işlem kuralına eklenen bekleme/teyit değildir. Başlangıç ve tüm 24 barın
  kalite/sansür, geçmiş ve dönem-sınırı kontrolleri ana ölçümle aynı; yetersiz
  gözlem ilk aşamada sansürlü ve hiçbir yarış sonucunda sayılmaz.
- Koşullar ilk görüldükleri kapanmış checkpoint'te kaydedilir. Aynı checkpoint'te
  birden fazla olası yol varsa `AMBIGUOUS_SAME_BAR`; intrabar sırası uydurulmaz.
  Üst üste gelen kırılmalar bağımsız işlem değildir.

## İlk yarış, aynı kırılma epizodu

Dondurulan eski çizgiye fiyatın ilk güvenli-taraf kapanışı; çizginin >0,01 fiyat
birimi **ters yönde** (destekte aşağı, dirençte yukarı) yer değiştirmesi; çizginin
ters olmayan yönde yer değiştirmesi; değeri aynı kalan yeni çizgi kimliği ve
hiçbirinin görülmemesi ayrı sonuçlardır. Bir çizgi değişimi ile fiyat dönüşü
aynı checkpoint'te ise belirsizdir. İlk aşamada **fiyatı bekleyip sonradan
çizgiyi seçmek** gibi geleceğe dayalı koşul yoktur.

## Çizgi ters hareketi ilkse, sonra ne oldu?

O an fiyatın **yeni** çizginin güvenli tarafında olup olmadığı kaydedilir;
bu, fiyatın eski çizgiyi geçtiğini iddia etmez. Ardından ilk ters basamağın
**aynı native kimliği** korunurken `HORIZONTAL_AFTER_DROP` aday sınıfına geçiş,
fiyatın eski çizgiye dönüşü ve yeni bir çizgi kimliği yarıştırılır. Aynı-bar
çakışma ve 24 bar içinde görülmeyenler ayrı. `HORIZONTAL_AFTER_DROP` yalnız
aday, native tabanlı proxy'dir; kullanıcının grafikteki yatayıyla eşitliği
**doğrulanmış değildir** ve tek stepline dik bağını kalıcı rejim saymaz.

Aday yatay proxy görülürse o anda fiyatın yeni çizgiye göre güvenli/ihlal
konumundan başlanarak, kalan pencere içinde çizgi kimliği değişmeden fiyatın
karşı tarafa kapanması veya önce çizgi kimliğinin değişmesi ayrı kaydedilir.
Altına/üstüne 'tutundu' ilan edilmez; kalan takip süresi bütün olaylarda eşit
değildir ve tüm bulgular önceki dallara **koşulludur**.

## Eski çizgiye fiyat ilk dönerse, sonra ne oldu?

Eski çizgi kimliği sabitken fiyatın yeniden kırması ile çizginin yer değiştirmesi
ayrı; çizgi değişimi ve kırılma aynı 4s checkpoint'te ise belirsiz. Diğer
çizgi yönü ve aynı-fiyat-yeni-kimlik ayrıca kaydedilir. Fiyatın bir kez geri
dönmesi devamlı başarı ya da getiri sayılmaz.

Sayılarda her aşamanın paydası, önceki aşamaya ulaşan gözlem sayısıdır. Ortak
piyasa günleri, dönem, kova ve hisse dağılımı farklılığını bu ham yol dağılımları
kontrol etmez; destek/direnç oran farkı nedensel veya kesin simetri ölçüsü değildir.
