# Normal Stabil desteği ile ters direnç — eş-kural karşılaştırma planı

Bu plan, daha önce direnç sonuçlarına bakıldıktan sonra ve **bu iki taraflı
koşudan önce** yazıldı; dolayısıyla bağımsız, kör bir ön kayıt değildir.
Kullanıcının [davranış modeli](../STABIL_DAVRANIS_MODELI.md) ile daha önceki
[48 soruluk destek kayıtları](../stabil_100_sonuclar/STABIL_DAVRANIS_48_YANITLARI.md)
incelendi. Kullanıcının “dikey” düzeltmesi ve **native teyit yeterlidir** ilkesi
korunur; ek 2/3/5 bar onayı eklenmez.

## Önceki destek rakamları neden doğrudan çıkarılamıyor?

48 soru sicilinde 100 hisse, 107.441 4s checkpoint ve 10.417 ilk görülen destek
olayı yazılıdır. Örneğin C02'deki temas sınıfları ve F01'deki aday rejim
etkinlikleri, son direnç araştırmasının TEST sınıfı ve 4s ATR'siyle aynı
olaylar değildir. Eski dosyalarda tam kaynak/veri hash'leri, kesin yakalama
kesitleri ve event-level doğal ara durum paketi yok; `USER_CONFIRMED` benzeri
bazı satır etiketleri görsel dikey/yatay eşlemesinin doğruluğunu kanıtlamaz.
Önceki sayılar silinmez fakat yeni direnç yüzdeleriyle doğrudan farkı alınmaz.
Kısmen uyum kontrolü için eski 100 hissenin alt örneği de **yeni, aynı** tanımla
raporlanır; bu eski 48-soru sonucunun yeniden üretildiği anlamına gelmez.

## Aynı evren ve yönü çevrilmiş ölçüm

- Son direnç koşusunun 174 uygun BIST hissesi, günlük ve 1s veri kaynakları,
  yakalama kesimleri ve `events_4h` ile `native_daily_events` dosyaları kaynak
  hash'leriyle doğrulanır. Her hissenin 4s/günlük bar sayısı ve eksik veri
  bayrakları eski direnç manifestiyle karşılaştırılır. Uyuşmazlık fail-closed.
- Normal destek **gerçek native** `build_daily_support_observations` ve
  `build_support_lifecycle_timeline` ile, gerçek günlük OHLC üzerinden
  çıkarılır; orijinal günlük destek/alt ATR sınırı, köken, teyit, geçerlilik ve
  aday rejimler aynen korunur. Yalnız ortak ölçüm algoritmasına girdi için tüm
  fiyatlar sabit `K=100.000` ile yansıtılır: `O'=K−O, H'=K−L, L'=K−H, C'=K−C`.
  Bu araştırma koordinatıdır, grafiğe veya gerçek fiyatına yazılmaz. `K` arşiv
  fiyatından küçükse sembol hata verir; seviye ve ATR, bağımsız native çalışmayla
  her günlük prefix için kontrol edilir. Destek sonuçları gerçek TL fiyatlarına
  çevrilip açık yön etiketleriyle kaydedilir.
- Hem destek hem direnç için önceki direnç çalışmasının aynı `TEST`, `BREAK`,
  `RETURN`, `DEPART` ve native günlük olay işleyicileri; aynı 4/8/16 kapalı 4s
  bar, 4s olay-ATR, 0,25 önceki 4s ATR test bandı, ≤1,5 ATR mesafe, eksik
  bileşen/kova, 20 geçmiş bar, şüpheli günlük fiyat, yakalama, sansür ve bölünme
  sınırı uygulanır. Günlük native olaylarda ise ayrı 4/8/16 **günlük** ufuk ve
  günlük ATR kullanılır; 4s ile birleştirilmez.
- Yönler anlamca eşlenir: destek tepkisi **yukarı**, direnç tepkisi **aşağı**;
  destek kırılımı **aşağı**, direnç kırılımı **yukarı**. Örn. ilk ±1 ATR
  yarışında `REACTION_FIRST` destek için +1, direnç için −1 ATR'dir.
  `BREACH_SIDE_FIRST` bunun karşıtıdır. Aynı mumdaki ikisi `AMBIGUOUS`, ikisine
  ulaşmama `NEITHER`; hepsi paydada ayrı tutulur.
- Gerçek temas `low ≤ çizgi ≤ high`; yalnız yaklaşılan zone ve çizgiye değmeden
  gap ayrı. Olay mumu içinde kapanışın güvenli tarafta olması ile takip eden
  barların sonucu ayrı. Kırılım sonrası 8 barda **başlangıçta dondurulmuş**
  çizginin güvenli tarafına en az bir kapanış; ilk retest ve gap ayrı. Bir kere
  dönmek nihai başarılı/başarısız işlem demek değildir.

## Modelin yolunu karşılaştırma

1. Uzaklaşma (1,5 önceki 4s ATR geçişi) → çizginin eski seviyeden takip
   yönünde >0,01 basamak yapması / fiyatın eski çizgiye kapanarak dönmesi /
   aynı-bar / hiçbiri yarışı, 4/8/16 bar. Günlük dört-bar pivot gecikmesi
   özellikle kısa ufukta mekanik olarak sonucu etkiler.
2. Doğrulanmış aday rejim eşlemesi değil, aynı native aday sınıflandırıcıyla
   basamak-takip / ters basamak / ikisinden sonraki düz parça / uzun düz proxy;
   yalnızca olay anına kadar bilinen yaş kovaları. Kullanıcı görseli ile birebir
   eşitlik veya ek teyit ilan edilmez.
3. İlk, ikinci, üçüncü+ gözlenen ayrık zone yaklaşımı; geçmişi bilinmeyen
   UNKNOWN. Bu sayı eski C02 tanımıyla özdeş sayılmaz.
4. Yukarı/aşağı simetrik kırılma → başlangıçta dondurulan seviye → dönüş;
   bilinen son kırılım derinliği ve üstte/altta kalma süresi. Başlangıç, eksik
   ara bar veya çizgi kimliği değiştiğinde bilinmiyorsa UNKNOWN.
5. Native günlük TESTED, HELD, BREACHED, sınır kırımı, geri dönüş ve yukarı/aşağı
   yeniden seviyeleme sonuçları aynı olay ve günlük ufukla ayrı.
6. Çizgi/fiyat taraf değişimi ayrıştırılır: fiyat tek başına, çizgi tek başına,
   ikisi birlikte gerekli veya ikisi ayrı ayrı yeterli. Bu piyasa nedenselliği
   değil, iki karşı olgusal aritmetik kıyaslamadır.

## Karşılaştırma ve belirsizlik

2026 kesiti ve daha eski 2025 kesiti ayrı. Ham gruplar aynı olayı seçmediği için
fark doğrudan etki sayılmaz. 2026 TEST olayları ayrıca aynı hisse, çeyrek,
seans, başlangıç çizgi mesafesi `[0,.5), [.5,1), [1,1.5]` ve yönü normalize
edilmiş son dört bar hareketi (`<−1`, `−1..0`, `0..1`, `≥1` ATR) kovalarında,
en az 8 bar ayrı, en yakın zamanlı ve tekrarsız eşleştirilir. Eşler ileri
sonuçlara bakılmadan seçilir, **sonra** geçersiz/eksik ufuk dışlanır. Tepki
önce oranı farkına 2.000 tekrar ve sabit tohumla hisse-kümeli bootstrap aralığı
hesaplanır. Bu eşleme gün şokları, trend, tüm bağlam ve çoklu hipotezleri
kontrol etmez; nedensel değildir. Gruplarda n, hisse sayısı, sansür ve aynı-bar
belirsizlik gösterilir. Hiçbir bulgu canlı filtreye uygulanmaz.

## Eski soru tariflerine yakın ayrıca ölçülen dört başlık

Kullanıcının eski kayıtlarla doğrudan ilgisi nedeniyle, yukarıdaki yeni TEST
olaylarından **ayrı** olarak eski `research/stabil_bhv48.py` soru tanımları
iki yöne aynalanır; sonuçlar 4s ATR değil, olayda bilinen **günlük ATR** kullanır:

- `A01`: Güvenli tarafta günlük ATR ile ≥1 uzaklıkta her 4s kapanış; 1–2,
  2–3,5 ve 3,5+ mesafe kovaları; takip / fiyatın eski çizgiye dönmesi / ters
  çizgi basamağı / aynı-bar / 24 bar hiçbiri yarışı.
- `B04`: Güvenli tarafta 0–2,5 günlük ATR mesafe ve bilinen epizot; mevcut
  aday `NEWLY_FLATTENED_AFTER_RISE` ile `LONG_HORIZONTAL`.
- `C02`: Native günlük kimlik altındaki temas sayısı, 0,35 günlük ATR ayrılma
  kuralıyla; seçilen 4s mum çizgiye 0,05 günlük ATR yakınında ve güvenli
  tarafta kapanmış olmalı. Bu eski kodda günlük temas sayısının 4s checkpoint'e
  taşınmasıdır; her 4s bar bağımsız yeni temas değildir. O mumun başlangıcında
  günlük seviye **ve günlük ATR biliniyor** koşulu ayrıca uygulanır.
- `F01`: Son dört 4s kapanış hareketi tepki yönünde >0,3 günlük ATR iken,
  aday `STEPPING_DOWN` ile `HORIZONTAL_AFTER_DROP`; dirençte tam karşıt yönde
  karşılıkları. Bu sınıflar görsel dikey/yatayın doğrulanmış karşılığı değildir.

Bu yeni koşu, önceki 100 hisse raporuna kaynak olan teyitsiz son bar/eksik
checkpoint paketini aynen kurtardığını iddia etmez: aynı kuralı iki yönde,
kapanış/yakalama ve kalite kısıtları uygulanmış yeni 174 hisse evreninde ve
ayrıca eski 100 hisse alt evreninde uygular. 24 bar yarışı için **tam ve temiz
24 bar** şartı kullanılır; önceki kodun kısmi izleme sırasında gerçekleşen olayı
sayabildiği durumlar bu yüzden farklıdır. Gelecekte bilinen etiketler girişte
kullanılmaz; örtüşen checkpoint'ler bağımsız işlem değildir.
