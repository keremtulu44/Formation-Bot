# Çapraz Piyasa Replay Araştırması — Tartışma Taslağı

**Durum:** Kullanıcıyla şekillendirilen araştırma tasarımıdır; uygulanmış bir
sistem veya kanıtlanmış istatistik değildir. İlk aşamada sonuçlar sadece
araştırma raporunda incelenecek; canlı bildirim/kart, puan veya işlem kararı
bu tasarımla değiştirilmez.

## Amaç

GitHub arşivindeki hisse geçmişleri ile endeks, petrol, altın ve gümüş gibi
araçların geçmiş hareketleri birlikte incelenir. Farklı piyasa koşullarında
her hissenin sonraki davranışı Replay ile ölçülür. İlk fikir bir kullanıcı
sorgu aracı değil, **arka planda çalışan toplu araştırma hattıdır**.

Örnek soru: Petrol yükselmiş ve XU100 düşmüşken ASTOR, sonraki 5 işlem günü
sonunda nasıl davranmış? Örnek kart metni ancak ileride onaylanırsa:

> “Geçmişte petrol yükselirken XU100'ün düştüğü N örneğin %70'inde ASTOR,
> takip eden 5 işlem günü sonunda yükselmiş.”

Bu sayılar **tamamen örnektir**; gerçek sonuç veya fiyat tahmini değildir.
Çalışma yalnız ASTOR'la sınırlı olmayacak; uygun geçmiş verisi bulunan tüm
hisseler için ölçüm amaçlanır. Bulgular otomatik olarak karta konulmayacak.

## Kullanıcıyla netleşen kararlar

- **Bağlam günlük:** Anlık hareket yerine günlük piyasalar üzerinden araştırma;
  her karar anında ancak kapanmış ve o anda gerçekten bilinebilen veri kullanılır.
  Kullanıcı seçimi asistana bıraktı: ilk tasarımda bağlam her BIST işlem günü
  **seans başında** bir kez oluşturulup o seans boyunca sabit tutulur. Her araç
  için o anda gerçekten erişilebilir son tamamlanmış günlük mum kullanılır;
  bayatlık ve kapanış zamanı bilinmiyorsa `bilinmiyor` sayılır. Bu, seans içi
  makro değişimleri bilerek içermez; ayrı bir çalışma olarak değerlendirilebilir.
  Replay ve ileride olası canlı uygulama aynı saat ve kuralları kullanmalıdır.
- **Tekli ve birleşik koşullar:** Örneğin sadece Brent veya sadece XU100 ve
  Brent + XU100 kombinasyonları ayrı ayrı incelenecek. Diğer endeksler,
  altın ve gümüş için de yeterli veri varsa aynı yaklaşım izlenecek.
- **Sonuç ufukları:** Hissenin sonraki **1, 5 ve 10 işlem günü** sonunda nasıl
  davrandığı ayrı ölçülecek. Önerilen seans-başı araştırmasında referans, o
  anda bilinen önceki hisse kapanışıdır; birinci sonuç, başlayan seansın kapanışı
  ve sonrakiler ilgili sonraki hisse kapanışlarıdır. Bunlar takvim günü değil,
  hisse için tamamlanmış işlem günleridir. Önceki kapanıştan hesaplanan fark,
  seans açılışında o fiyattan işlem yapılabildiği anlamına gelmez. İleride
  intraday bildirim kartında kullanılacaksa sinyal anındaki fiyat ve o anki
  ufuklarla ayrıca test edilmeli; bu araştırmanın oranı doğrudan taşınmamalı.
- **Piyasa koşulu eşiği:** Petrol, endeks ve değerli metaller için değişim,
  aracın karar anına kadar bilinen günlük **ATR'sine** göre yukarı/yatay/aşağı
  sınıflandırılacak. 0,5 ve 1 ATR gibi adaylar önce keşif döneminde karşılaştırılacak;
  seçilen katsayı ayrı doğrulama döneminde sınanacak. Eksik ATR veya yetersiz
  veri bilinmiyor sayılacak.
- **Hisse sonucu:** Hissede de küçük değişimler yatay sayılacak; yukarı, yatay
  ve aşağı sonuçları ayrı gösterilecek. Kullanıcı sistem önerisini istedi:
  öneri, hisse için de karar anında bilinen günlük ATR'yi kullanmak ve 1/5/10
  günlük sonuçları ayrı raporlamak. Eşik adayları ve kesin katsayı henüz
  seçilmedi. Kullanıcı 0,5 / 1 / 1,5 ATR gibi adayların keşif döneminde
  karşılaştırılmasını ve seçilen kuralın ayrı dönemde doğrulanmasını seçti. Aynı
  eşikle uzun ve kısa ufukların dağılımı farklı olabileceğinden her ufuk ayrı
  değerlendirilecek; sonuç yüzdesi ve örnek sayısı da gösterilecek.
- **Tüm kombinasyonlar:** Kullanıcı tekli koşullarla birlikte mevcut araçların
  tüm kombinasyonlarının araştırılmasını istiyor. Örneklem yetersiz veya veri
  eksikse bu hücreler ayrıca raporlanacak; anlamlı/karta uygun sayılmayacak.
  Çalışma kapsamı, kaynak maliyeti ve test sayısı önceden raporlanmalı.
- **Altın ve gümüş:** Hem ons/USD hem gram/TL ayrı ayrı incelenecek. Bunlar
  aynı veri olarak birleştirilmeyecek. Gram için ayrı kaynak veya ons ile kur
  kullanılarak türetme yöntemi ve eşzamanlılık ayrıca doğrulanacak.
- **Önce rapor:** İlk bulgular kartlara aktarılmadan önce incelenecek; sonuç
  yetersiz veya yanıltıcıysa yayınlanmayacak. Ana rapor, yeterli ve doğrulanmış
  bulguları özetleyecek; tüm hücreler ve yetersiz örnekler ayrı ayrıntıda
  tutulacak. Tüm kombinasyonlar istenmesi, tümünün güvenilir olduğu anlamına
  gelmez.

## Ölçüm tasarımı — öneriler, henüz nihai değil

1. Her hisse ve karar zamanı için yalnız o anda bilinen bağlamı oluştur.
   Araçların o anda tamamlanmış son günlük değerleri, kaynakları ve asıl
   kapanış zamanları kaydedilir. Bayat/eksik makro veri normal gözlem gibi
   gösterilmez; azami veri yaşı kuralı ayrıca belirlenir.
2. Tekli koşulları ve önceden tanımlanan birleşimleri ayrı ölç. Örneğin Brent
   ↑ / XU100 ↓ gibi koşulun hissenin 1/5/10 günlük sonraki kapanış değişimiyle
   ilişkisini ölç. Gözlem dönemi bittiği için geleceği eksik olan satırlar
   “düşüş” veya “yatay” sayılmaz; sansürlü olarak raporlanır.
3. Her hücrede koşul tanımı, sembol, ufuk, örnek sayısı, tarih aralığı,
   yükseliş/yatay/düşüş sayıları, yüzde ve mümkünse güven aralığı göster.
   Karşılaştırma olarak aynı hisse, dönem ve ufuktaki genel davranışı ve farkı
   ver. Bir sonuç yalnızca %70 olduğu için anlamlı sayılmamalıdır.
4. Aynı olayı birbirini izleyen günlerde tekrar tekrar sayma ve 1/5/10 günlük
   sonuç pencerelerinin örtüşmesi bağımsız örnek izlenimi oluşturabilir. Olay
   kümelemesi/örnekleme ve sembol-zaman bloklu belirsizlik ayrıca tasarlanmalı.
5. Günlük oturumlar arasında zaman uyumu kritik: XU100 ve petrol/altın/gümüş
   farklı saatlerde işlem görür. Günlük mum tarih etiketi tek başına o mumun
   BIST karar anında bilindiğini kanıtlamaz. Sağlayıcının mum kapanış zamanı
   belirsizse durum bilinmiyor sayılır; gelecekteki kapanış kullanılamaz.
6. Çok sayıda hisse × araç × koşul × ufuk tarandığında tesadüfi güçlü sonuçlar
   ortaya çıkar. Hipotezler/eleme kuralları önceden tanımlanmalı; zaman ayrımlı
   keşif ve sonradan gelen bağımsız doğrulama dönemi, çoklu karşılaştırma
   kontrolü ve dönemler arası istikrar değerlendirilmelidir.
7. Veri temin edilirken sembol, para birimi ve seri türü açık olmalı: örneğin
   ons XAU/USD ile gram TL altın aynı seri değildir; spot ve vadeli fiyatlar da
   birbirinin sessiz yerine kullanılamaz. Fiyat düzeltmeleri, bölünme, boş bar,
   tatil ve seans farkları raporlanmalı. Sonuçlar nedensellik kanıtlamaz.

## Mevcut veri ve sınırlar

- Repo `backfill_data/` içinde `XU100`, `XU30`, `BRENT` için 1h ve 1d dosyaları
  mevcut. İncelenen arşivde altın/gümüş dosyası görülmedi; bu iki araç için
  uyumlu geçmiş verisi temin edilmeden araştırma tamam sayılmaz.
- `config.py` içindeki `XAUUSD`, `XAGUSD`, BRENT ve bazı diğer endekslerin
  canlı sağlayıcı sembol tanımları, arşivde yeterli tarihsel dosya olduğu
  anlamına gelmez. Kaynak, doğru kapsam ve geçmiş tarihler doğrulanmalı.
- 177 sembollük eski Replay koşusu 176'lık havuz ve ayrı koşulan BRENT'ten
  oluşur; bu evreni tüm BIST veya tüm endeks/emtia geçmişi diye sunma.
- `dz_*` tabloları 2026-10-29 Supabase incelemesinde boştu. Bu araştırmanın
  verilerinin nerede tutulacağı, yükleme kotası ve sürümlenmesi henüz karara
  bağlanmadı; Supabase'e veya canlı bot verisine otomatik yazma yapılmaz.

## Açık sorular

1. Piyasa koşulları için günlük ATR katsayısı ne olacak ve tek bir katsayı
   farklı araçlar için geçerli mi? Seçim veriyle doğrulanmalı.
2. Hisse sonucu için önerilen ATR eşiğinin katsayısı ne olacak? 1/5/10 işlem
   günü için dağılım ve sansür ayrı incelenmeli.
3. Tüm kombinasyonların hesaplama maliyeti, araştırma kapsamı ve istatistiksel
   çoklu test kontrolü nasıl yönetilecek? Çok parçalı koşullarda örnek sayısı
   ve güven hızla azalabilir.
4. Başlangıçta hangi endeksler ve altın/gümüşte spot/vadeli, gram verisi için
   hangi kaynak/türetme yöntemi kullanılacak?
5. Asgari örnek sayısı, sansür, veri bayatlığı ve karşılaştırma farkı için
   yayın koşulları önceden nasıl belirlenecek?
6. İlk raporun ayrıntısı, veri yenileme sıklığı ve ileride karta aktarım
   koşulları ayrı karar gerektirir.
