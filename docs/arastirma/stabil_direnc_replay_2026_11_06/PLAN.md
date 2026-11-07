# Stabil direnç replay planı — sonuçlar okunmadan sabitlenen sözleşme

Bu çalışma canlı kodu, filtreleri, alarmları veya çizimleri değiştirmez.
[Geri kazanılarak yeniden yazılmış kullanıcı davranışı modeli](../STABIL_DAVRANIS_MODELI.md)
ve [48 soruluk sicil](../STABIL_DAVRANIS_SORULARI.md) kaynak alınır; bunlar
bulunamayan özgün dosyanın birebir kopyası değildir. Dikey/yatayın görsel–native
birebir eşlemesi henüz doğrulanmamıştır. Bir stepline dik bağını sürekli dikey
rejim saymayacağız. Native teyidin üzerine 2/3/5 mum bekleme eklemeyeceğiz.

## Evren, zaman ve olay sözleşmesi

- Yerel arşivde 1s ve native 1g olan bütün uygun BIST hisseleri; arşiv manifesti
  ve günlük/saatlik her kaynak dosyası hash'lenir. 4s, repo 09:30 seans kuralı
  ile saatlikten üretilir. Her kaynağın yakalama anından önce kapanmamış son bar
  atılır; günlük kapanış 18:30/yarım gün kuralına bağlıdır.
- Ana seviyeyi gerçekten **birebir** çevirmek için günlük OHLC işaret çevrilir
  (`O'=-O, H'=-L, L'=-H, C'=-C`), değiştirilmemiş native
  `build_daily_support_observations` ve `build_support_lifecycle_timeline`
  çalıştırılır ve çıktı işareti geri çevrilir. Böylece span=4, iki teyitli dip +
  iki teyitli tepe, tekil ekstremum, sıralama, köken/teyit/ilk kullanılabilirlik,
  köken ATR'si ve `tavan=tepe+0,35*köken ATR` birebirdir. Native durum/olaylar
  da ters yönde okunur; bunlar 4s ok/uyarı kodunun birebir terslendiği iddiası
  değildir. Bağımsız yüksek-pivot hesabı ve prefix testleri ile kontrol edilir.
- 4s OHLC teması için günlük seviye mum **başlamadan** bilinmelidir, yalnızca
  mum kapanışında öğrenilen seviye o mumun yüksek/düşüğüyle sınanmaz. Olayın
  kendi kapanışından sonraki 4/8/16 **mevcut** 4s barı; ayrıca native günlük
  olaylarından sonraki 4/8/16 günlük bar değerlendirilir. Eşzamanlı ±1 ATR ilk
  temasları belirsizdir; aynı mumda sıralama uydurulmaz.
- Başlangıç/son ve veri kalitesi: manifest yakalama sınırı, geçersiz OHLC/negatif
  hacim/>%30 kapanış sıçraması, eksik saatlik bileşenler ve günlük oturumlara
  göre aradaki eksik 4s kovalar işaretlenir; 20 bar geçmiş ve tüm ileri ufuk
  temiz değilse metrikler geçersiz/sansürlüdür. Günlük kaydın da eksik olduğu
  seans ve kurumsal işlem düzeltmesi bağımsız doğrulanamaz. Üçüncü taraf XIST
  takviminin yarım günleri kontrol edilir; günlük kaynaktaki bir >%30 sıçrama
  ATR/pivot geçmişini bozabileceğinden o sembolün o noktadan sonraki tüm
  ufukları ihtiyatla geçersizdir. Sıfır hacim tek
  başına fiyat verisi hatası sayılmaz. 2026-01-01 öncesi ve sonrası sabit
  takvim dilimleridir; önceki araştırmalarda arşiv görülmüş olduğundan 2026
  tamamıyla kör veya bağımsız bir test değildir. Ufuk bölünme sınırını geçerse
  önceki dilimdeki gözlem o ufuk için dışlanır.
- Birincil 4s `TEST`: önceki kapanış seviye altında/eşit, 0–1,5 önceki 4s
  ATR uzakta; önceki yüksek zone altında, şimdiki yüksek `R−0,25*önceki 4s ATR`
  veya üstünde. Böylece bitişik temaslar ayrılmadan tek test olur. Gerçek tepeye
  değmeyen **zone yaklaşımı**, fitil reddi ve üstte kapanış ayrı tutulur. Bu
  mekanik ölçüm native günlük TESTED'in yerine geçmez. Fiyat mumunun tamamı
  gap ile çizginin üstünde kalmışsa gerçek temas sayılmaz. Aradaki çizgi güncellemesi
  sonucu fiyatın geçtiği sabit referansla gösterilir; ayrıca önceki seviyeden
  güncel seviyeye üst/alt durum değişimi fiyat/çizgi/ikisinin etkisi olarak ayrılır.
- İlk gözlenen seviyenin daha eski test/break geçmişi `UNKNOWN`; yeni bir seviye
  kimliği arşiv içinde gözlenirse temas ve üstte kalma geçmişi yeniden başlar.
  Aynı çizgi kimliğinin yukarı kırılıp aşağı dönmesinde bilinen süre ve en büyük
  yukarı taşma, kırılma anında sabitlenmiş ATR ile ayrı tutulur. Kırılmadan sonra
  donmuş seviyeye ilk dönüş, bar açılışına göre test/kapanış veya gap/geri alım
  diye sınıflanır; mum içi kesin sıralama iddiası yoktur.
- Kullanıcıdaki uzaklaşma/takip yolunu da ölç: önceden bilinen direncin altında
  fiyat, 1,5 önceki 4s ATR uzaklık eşiğini ilk kez aşağı geçince giriş. İzleyen
  4/8/16 barda ilk olay `direnç eski seviyeden >0,01 aşağı basamak` mı, `fiyatın
  eski seviyede/üstünde kapanışı` mı; ikisi aynı 4s checkpoint'te ise belirsiz,
  hiçbiri ve sansür ayrı. Bu eşik, tek sembollü teknik pilot sonrasında ve tüm
  evren replay'inden önce yazıldı; AEFES için tamamen kör ön kayıt değildir.
- Ana ölçü, TEST kapanışı sonrasında 8 barda −1 ATR'ye önce ulaşma oranı,
  +1 ATR önce, aynı-bar belirsiz ve hiçbiri ile birlikte; medyan 8-bar kapanış,
  yukarı/aşağı hareket, tavanın kapanışla aşılması, n ve sansür sayılarıdır.
  Ayrıca 4/16 bar, en az 8 bar aralıklı alt örnek, hisse-eşit ortalama, dönem,
  seans saati, son bilinen yaş/rejim, temas sırası, geçmiş yaklaşma hızı, hacim,
  break ve aşağı dönüş/taşma derinliği ayrı incelenir. Sonucun işlem getirisi
  olduğu, komisyon/kayma/işlem fiyatı hesaba katılmadığından iddia edilmez.

## İlk tam koşu sonrası veri-kalite düzeltmesi

İlk tam koşunun OHLC denetiminde, çizgi üzerinden gap açıp tüm mum boyunca
çizginin üzerinde kalan olayların yanlışlıkla “gerçek temas” paydasına girdiği
bulundu. 2026 ana geçerli TEST kümesinde bu tür 28 olay vardı. Bunlar artık
ayrı sınıftır; gerçek temas için `low ≤ çizgi ≤ high` gerekir. Bu, ilk koşu
sonrası açıklanan bir veri sınıflama düzeltmesidir; adaylar, TEST seçimi ve
ileri ±1 ATR yarışı değiştirilmedi, tüm arşiv düzeltilmiş kodla tekrar çalıştırıldı.
Günlük >%30 şüpheli barın gününe denk gelen 4s barlar ve bu duruma uzanan
ufuklar da daha ihtiyatlı sansürlenir. Bu değişiklik ana ölçümün geçerli
paydasını etkileyebilir ve bağımsız bir ön-kayıt gibi sunulmaz.

## Önceden tanımlanan seviye ve seçim adayları

Aynı test/ufuk kullanılır; koşullu modellerin kapsaması ayrı raporlanır.

| Kod | Tanım | Rol |
|---|---|---|
| MIRROR_P4 | Native desteğin birebir aritmetik/yaşam döngüsü karşıtı | Ana aday |
| P2, P3, P6, P8 | Aynı iki-tepe/iki-dip koşulu, teyit span 2/3/6/8 | Duyarlılık |
| BODY_P4 | Fitil yerine gövde üst/alt pivotu; orijinal OHLC köken ATR'si | Alternatif |
| P4_MAX3, P4_MEDIAN3 | Son üç teyitli tepenin maksimumu veya medyanı | Alternatif; üç tepe gerekir |
| P4_DOUBLE | Son iki tepe farkı en fazla son tepenin 0,5 köken ATR'si; son tepe | Seçici alternatif |
| P4_ACTIVE | Günlük kapanış seviyesi üzerindeyken kapalı; alta dönünce açık | Native ACTIVE karşıtı koşul; ek gecikme değil |
| P4_CEILING | Ana tepe yerine native +0,35 köken ATR tavanı | Seviye alternatifi |
| ROLL10, ROLL20, ROLL55 | Son 10/20/55 tamamlanmış günün en yüksek fitili | Basit referanslar |
| ROLL20_CLOSE | Son 20 tamamlanmış günün en yüksek kapanışı | Basit referans |
| EMA20 | Son tamamlanmış günlük kapanışların EMA20'si | Dinamik, yapısal olmayan referans |
| SHIFT_UP, SHIFT_DOWN | Ana teyitli tepeye ±0,5 **köken günlük ATR** sabit ofset | Yakındaki sentetik sahte seviyeler, öneri değil |
| P4_ZONE0, P4_ZONE50 | Ana çizgi değişmez; test bandı 0 veya 0,50 önceki 4s ATR | Temas eşiği duyarlılığı |

Bütün bu adaylar ve aşağıdaki karşılaştırmalar sonuçlar görülmeden seçildi;
çoklu denemelerden en yüksek yüzdeyi seçmek doğrulama sayılmaz.

## Kontroller ve nedensel sınırlar

1. Ana adayın aynı dönem/ufuk ve aynı olay sözleşmesinde ROLL20/55 ve iki
   ofsetle ham sonucu: farklı olay popülasyonlarıdır, doğrudan neden kanıtı değildir.
2. `MIRROR_P4 TEST` ile her ofset TEST'i arasında: aynı hisse, takvim çeyreği,
   kapanış saat grubu, önceki kapanış–çizgi mesafesi `[0,.5), [.5,1), [1,1.5]`
   ve önceki dört bar fiyat hareketi `<−1, −1..0, 0..1, ≥1` ATR kovalarında,
   farklı en az 8 bar uzaklıkta en yakın zamanlı birer eş, tekrarsız eşleştirilir.
   Sadece geçmiş/olay anında bilinen kovalar kullanılır; eşleşmeyenler ve ±1 ATR
   ilk-temas belirsizleri saklanır. 2026 kesitinde olay ağırlıklı −1 ATR önce
   oran farkı için sabit tohumla 2.000 hisse-kümeli bootstrap %95 aralığı verilir;
   bu ortak gün şokunu, seçim yanlılığını veya çoklu denemeleri düzeltmez.
3. Ana adayın bilinen geçmişe dayalı yaş, dikey/basamak **proxy**'si, ilk/tekrar
   test, yaklaşma, break/geri dönüş büyüklüğü ve retest grupları betimseldir;
   aralarındaki eşitsizlik nedensellik değildir. Birinci gözlenen epizod geçmişi
   bilinmiyorsa ilk diye yazılmaz. İstenilen görsel teyitli yatay/dikey tanımı
   bu çalışma tarafından çözüldü ilan edilmez.
4. Arşiv sonundaki sansür, kapsama, veri hatası, aynı-bar belirsizliği, olayların
   örtüşmesi ve varyant sayısı her iddia yanında görünür; sıralamaya göre canlı
   kural değiştirilmez. İleri dönem ve zaman damgalı kullanıcı grafik etiketleri
   ayrı doğrulama gerektirir.
