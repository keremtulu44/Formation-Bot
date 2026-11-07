# Stabil direnç ve oklar — uygulama öncesi kontrol

**Durum — 3. adım, yerel bağlantı:** Bağımsız direnç çizgisi, ters oklar ve
aday yapı uyarısı `/grafik` ile mevcut formasyon, Stabil destek ve domain alarm
karelerine bağlandı. Kaynak güvenliği ve regresyon sınırları aşağıdadır. Bu
çalışma **canlıya dağıtılmadı; gerçek Telegram teslimi doğrulanmadı**. Dirence
özel tetikleyici/alarm, BOS filtresi veya ilk sinyal için ek bekleme eklenmedi;
ertelenen BOS/tekrar-kısıtı replay'i yapılmadı.

## İlk iki adımın uygulama notu

- Yeni giriş noktası `domain_engines.stabil.resistance.evaluate_stabil_resistance`;
  ilk iki adımda mevcut `signals.py`, destek motoru, grafik ve alarm akışları
  değiştirilmedi. Grafiklere bağlantı daha sonra aşağıdaki 3. adımda yapıldı.
  Günlük OHLC yalnız native yaşam döngüsünü kullanmak için işaretçe yansıtılır
  (`yüksek = −gerçek düşük`, `düşük = −gerçek yüksek`). Dışarıya gerçek pozitif
  direnç ve ATR tolerans üst sınırı (borsanın günlük tavan fiyatı değil), pivotun
  oluşum/teyit/hazır olma zamanı, yaşam döngüsü ve hedef mumun kapanışına
  nedensel projeksiyon verilir. Araştırmadaki
  büyük sabit fiyat dönüşümü sinyal hesabında kullanılmaz.
- Renk rolleri desteğin tersidir: native günlük geçerlilik **ACTIVE** ise kırmızı,
  kırılmış/ATR üst sınırını aşmışsa yeşil; eşitlik normal taraftadır. Mevcut destekle
  simetrik olarak renk, hedef 4s mumun tek başına kapanışından değil, o ana kadar
  bilinen **günlük** geçerlilikten taşınır. Bu nedenle 4s fiyat çizgiyi aşsa da
  günlük durum güncellenene kadar renk hemen değişmeyebilir.
- Güçlü çizgi altına dönüş ve fitilli red ayrı aşağı ok sınıfıdır; güçlü aşağı
  momentum ikinci, ayrı sınıftır. Momentum tekrar aralığı destekteki gibi üç
  hedef mumdur; pivot sonrasına ilave teyit beklemesi eklenmemiştir. Dikey aday
  proxy'sinde normal aşağı sinyal bastırılır ve ayrı yukarı **yapı uyarısı**
  üretilir; fiyat yönü garantisi veya doğrulanmış görsel dikeylik değildir.
  Toleranslı yaklaşım uyarısı gerçek temas iddiası taşımaz; çizgi altına kapanış
  dönüşü de gap ile oluşabilir. Ayrı temas işareti oluşturulmadı.
- Kapanmamış sondaki mum dışlanır; bilinen bozuk OHLC, bozuk zaman/bayrak veya
  aradaki eksik olduğu işaretli mum hesaplamayı hata durumuyla durdurur. Kesim
  sonrasındaki veri önceki kararı değiştirmez; hedefteki son mumdan sonraki günlük
  veri de kullanılmaz. Hacim yokluğu mevcut destekte olduğu gibi sıfır-hacim
  yolundan değerlendirilir. **Hiç gönderilmemiş ve bayraklanmamış mum boşluğu**
  bu katmanda kendiliğinden saptanamaz; kurumsal aksiyonlar da ayrıca doğrulanmaz.
  Grafik bağlantısından önce kaynak/kalite kontrolü gerekir. Bayraksız ham veride
  çağıran gerçek kapanış kesimini sağlamalıdır; varsayılan kesim en son kabul
  edilen hedef mumdur.
- Ok kuralları desteğin üretim işleyişiyle ayrı kodda karşılaştırılır; destek
  eşikleri/politikası ileride değişirse direnç aynası ve eşlik testleri birlikte
  gözden geçirilmelidir. Testler sentetik ayna, nedensellik, renk, eşitlik/gap,
  sabit/değişen seviye, eksik veri, üç bar kısıtı ve yapı uyarısını kapsar.
  Daha önce incelenen EFOR ve AKBNK 4s örneklerinde de seviye/zaman ve o kesite
  kadarki oklar destek aynasıyla karşılaştırılmıştır; bu bir performans veya BOS
  replay'i değildir.

### Uygulama doğrulaması — 2026-11-07

- Yeni katman için **54** odak test; son kodla çalıştırılan Stabil + grafik
  regresyonlarında **586 başarılı**. Paralel genel test koşusunda **3.862 başarılı,
  43 atlandı**; onun çalışması sırasında son veri-kalitesi düzeltmesi ayrıca
  yapıldığı için bu son düzeltme 586'lık ilgili regresyon paketinde tekrar test
  edildi. `ruff check .` başarılı.
- EFOR 28.07.2026 13:30 için direnç **19,53**, kapanış **19,80**; AKBNK
  06.01.2026 17:30 için direnç **73,65**, kapanış **74,15**. Bu iki geçmiş
  örneğin sırasıyla **539 ve 495 adet** 4s mumundaki ters davranışlar destek
  aynasıyla eşleşti; bunlar kalite/getiri ölçümü değildir.
- 50-hisse çalışmasının üç mevcut doğrulayıcısı tekrar başarılı; önceki sonuçlar
  veya manifestler yeniden yazılmadı. Destek `signals.py` kaynak hash'i aynı kaldı.
- Yerel test ortamı **Python 3.11** idi; deponun hedefi **Python 3.12**. Bu turda
  GitHub CI, canlı servis, Telegram teslimi veya dağıtım doğrulanmadı.

## Kullanıcının açık istekleri

- Destek modeliyle yönce ters bir Stabil direnç ve ters yönlü ok mantığı.
- Renkler mevcut desteğin tersidir: destek çizgisinde yeşil olan rol dirençte
  kırmızı, destekte kırmızı olan rol dirençte yeşil. Kullanıcı ayrı yeşil temas
  işareti istemedi; bu renk kararını ayrıca temas işareti diye yorumlama.
- Önceden kaydedilmiş güçlü görünen/görünmeyen destek okları ve BOS bağlantısı
  hakkında: [bekleyen notlar](../arastirma/STABIL_BEKLEYEN_ARASTIRMA_NOTLARI_2026_11_06.md).
  Kullanıcı BOS ölçümünü direnç canlı grafik işinden **sonraya** bıraktı; şimdilik
  bunun için ek replay/filtre yapılmayacak.
- Native Stabil teyidi yeterli; onun üzerine keyfî 2/3/5 mum **ek teyit
  beklemesi** ekleme. Görsel dikey/yatay eşlemesini doğrulanmış varsayma.
- Yeni direnci `/grafik`te ve başka bir formasyon veya Stabil destek alarmı için
  mevcut akışta üretilen grafiklerde görmek istiyor. **Dirence özel yeni bir
  tetikleyici veya otomatik alarm yok.** Mevcut destek mesajları sessizce
  kapatılmayacak/değiştirilmeyecek; alarm grafik ayarının gerçek durumu ayrıca
  doğrulanacak.
- Kullanıcı mevcut güçlü momentum okunun üç barlık tekrar sınırlamasını da
  dirence tersleyerek uygulamamızı, bu sınırlamanın etkisini daha sonra replay
  konusu olarak kaydetmemizi istedi.

## Destek okları şu anda nasıl çalışıyor?

Kaynak: `domain_engines/stabil/signals.py`, `grafik/tarama.py`,
`grafik/render.py` ve güncel [dikey uyarı sözleşmesi](STABIL_DIKEY_UYARI_2026-11-05.md).

1. Yukarı `▲` tek tür değil: dolu yeşil güçlü destek geri alımı ve içi boş
   güçlü yukarı momentum ayrı sınıflardır. Yalnızca “mum yeşil” olmak ikisine de
   yeterli değil: gövdenin ATR'ye göre büyüklüğü, mum kapanışının konumu, hacim
   veya daha büyük gövde alternatifi ve destek durumu gibi koşullar var. Örneğin
   momentumda en az 0,35 ATR gövde, mum aralığında en az %65 kapanış konumu ve
   1,10× hacim **veya** en az 0,50 ATR gövde şartı var. Geri alım koşulları
   bunlarla birebir aynı değil.
2. Dikey/kademeli destek **aday proxy'sinde** normal `▲` bastırılır ve yukarı
   deneme ayrı `▼` yapı uyarısı olarak çizilir. Uyarı fiyatın mutlaka düşeceğini
   iddia etmez. Aday proxy kullanıcı tarafından görsel olarak doğrulanmış değil;
   yatay görünen bazı parçaları da kapsayabilir.
3. Momentumda mevcut 3 barlık tekrar sınırlaması, ayrı 4s geri-alım alarmında
   mevcut 6 barlık gönderim cooldown'ı vardır. Bunlar native pivot sonrası yeni
   teyit beklemesi değildir; fakat tekrar eden okları/bildirimleri azaltırlar.
   Kullanıcının “ilave mum bekleme” istememesiyle karıştırılmadan neyin
   korunacağı görünür biçimde ele alınmalı.
4. “BOS aşağıyken yukarı oklar zayıf olabilir” kullanıcı gözlemidir. Ok
   fonksiyonunda BOS filtresi yoktur. Önceki ok replay'indeki dış yapı yönü,
   ayrıca incelenmesi gereken **son teyitli BOS olayıyla aynı şey değildir**;
   önceki sayılar bu filtreyi otomatik doğrulamaz.

## Planlanan yön aynası

- Günlük teyitli destek hesabının yüksek pivot üzerinden karşıtını ayrı bir
  direnç çıktısı olarak üret; fiyatı, pivotun oluşum ve **bilinirlik** zamanını
  koru. Araştırma koordinat dönüşümünü canlı sinyal koduna doğrulamasız
  kopyalama: `evaluate_bar_behaviors` pozitif destek ister, normalize edilmiş
  fiyatlar/mesafeler ayrıca terslenmelidir.
- Destekteki güçlü yukarı geri-alımın karşıtı, direnç üstünden çizginin altına
  güçlü dönüşte **aşağı ok**; güçlü yukarı momentumun karşıtı güçlü aşağı mumda
  **aşağı ok** olacaktır. Bunlar genel aynalama taslağıdır; gerçek 4s direnç
  oklarının koşulları/kalitesi, yalnız çizgi davranışını ölçen 50-hisse
  replay'iyle kanıtlanmış sayılmaz.
- Destekte dikey denemeye karşı uyarının dirençteki karşılığı, koşullar aynı
  şekilde terslenirse **yukarı uyarı** olur; bu da fiyat yönü garantisi değildir.
  Güçlü düşüş, yatay/aday dikey, temas, kırılma ve geri dönüş ayrılmalı.
- Aynı `/grafik` hattında ve mevcut alarm grafiği üretilen formasyon/Stabil
  destek akışlarında mevcut desteği bozmadan ayrı `Direnç` çizgisi, fiyat etiketi
  ve direnç okları göster. Direncin normal rengi kırmızı; destek tarafında
  kırmızıya karşılık gelen ters rol dirençte yeşil. Gerekli yerde şekil/doluluk
  ve etiketle destek/direnç, uyarı/sinyal birbirinden ayrılsın. Ayrı direnç
  alarmı veya yeni bir alarm tetiklemesi yapılmasın.
- Destek/direnç katmanları yalnız kapanmış veri ve bilinen pivot zamanıyla,
  çizilen mumlara doğru zaman damgasıyla eşleşsin. Eksik/güvenilmez veride
  seviye uydurma veya gelecekteki pivotu geçmişe taşımak yok.

## Kodda bağlanacak yerler ve testler

- `domain_engines/stabil/`: bağımsız veya yön-parametreli direnç pivotu, aday
  yaşam döngüsü, zamansal projeksiyon ve ters davranış/oklar.
- `domain_engines/runner.py`, `grafik_uret.py`, `grafik/tarama.py`,
  `grafik/render.py`, `grafik/core.py`: ayrı katmanın mevcut destekle birlikte
  taşınması, zaman eşlemesi, renk, ok, lejant ve fiyat çipi. `/grafik` 1s, 2s,
  4s ve 1g kareleri destekler; `/grafik` komutu `TELEGRAM_GRAFIK=alarm`
  ayarından bağımsızdır. Grubun komut yetkisi dağıtım ayarına bağlıdır.
- Pozitif gerçek fiyatlar, high/low ayna simetrisi, pivot hazır olma, kapalı
  mum, veri boşluğu, eşitlik/gap, sabit/taşınan çizgi ve uyarı-sinyal
  ayrımına birim testleri; mevcut destek çıktıları ve alarmları için regresyon.
- Uygulama doğruluğu için sentetik ayna testleri ve önceden seçilmiş birkaç
  somut fiyat/grafik örneği; büyük yeni BOS/tekrar-kısıtı replay'ini kullanıcının
  istediği gibi sonraya bırak. Kullanıcı zayıf görünen bir ok için sembol/tarih/TF
  verirse sonradan incelenebilir. Güçlü **görünmeyen sinyal mumu** ile sinyalden
  sonraki **zayıf fiyat tepkisi** aynı ölçüm değildir.
- Performans, grafik okunabilirliği, sembol/TF hata durumları, testler ve CI
  kontrolü sonrası olası kontrollü dağıtım **ayrı aşama ve kullanıcı onayı**
  gerektirir. Render Dashboard ayarları, yayınlanan commit ve Telegram teslimi
  bu kontrolde görülmedi; ikinci bot servisi veya yinelenen gönderici açılmaz.

## En sona bırakılan replay soruları

Direnç ve ters oklar canlı grafikte kullanıcı testine hazırlandıktan sonra; bu
ön kontrol sırasında ayrıca replay koşulmayacak:

1. Aşağı BOS + destek yukarı oku ve yukarı BOS + direnç aşağı oku / destek-direncin
   kırılması ilişkisi. Olay anında bilinen teyitli BOS ve zaman dilimi açıkça
   ayrılmalı; BOS bilinmiyorsa yok sayılmamalı. Filtre/uyarı, ölçümden sonra
   ayrıca kararlaştırılmalı.
2. Mevcut momentumun üç barlık tekrar kısıtının hangi okları sakladığı ve
   çıktıya etkisi; bekleme/teyitle karıştırılmadan karşılaştırılmalı.
3. Kullanıcının gözlemlediği zayıf görünen mumlar: güçlü **görünmeyen sinyal
   mumu** ile sinyalden sonraki **zayıf fiyat tepkisi** ayrı araştırılmalı.
   Gelişigüzel yeni gövde/hacim eşiği veya BOS filtresi seçilmemeli.

## 3. adım: grafik bağlantısı uygulama planı (2026-11-07)

Amaç: bağımsız Stabil direnç çıktısını yalnız mevcut grafiklere bağlamak; destek
motorunun, destek mesajlarının ve formasyon/Stabil alarm kararlarının sözleşmesini
değiştirmemek. Yeni dirence özel otomatik alarm, BOS filtresi, ilk sinyale ek
bekleme, canlı dağıtım veya Telegram teslim iddiası bu aşamada yoktur.

1. **Kaynak ve hesap köprüsü:** `/grafik`, formasyon alarmı ve Stabil destek
   alarmı için mevcut kapanmış hedef/günlük çerçeveleri kullan. Direnci yalnız
   gerçekten grafik hazırlanırken, mevcut kill-switch'e uyarak, ayrı sonuç
   alanında hesapla. Var olan domain/mesaj çıktısını değiştirme. Saptanabilen
   eksik veya bozuk kaynakta yalnız direnç katmanını durdur ve nedeni kaydet;
   açık/gelecek mumları veya eksik bileşenli türetilmiş kovaları tamam sayma.
   Kaynağın işaretlemediği ve takvim/kaynaklarla saptanamayan bir eksikliği
   eksiksizlik kanıtı olarak sunma.
2. **Nedensel hizalama:** Motorun günlük `available_at` ve hedef mum kapanış
   kurallarını koru. Projeksiyon ve davranışı görünür mumun tam kapanış zamanına
   eşleştir; zaman belirsizse indeks veya önceki okla tahmin etme.
3. **Çizim:** Destekten bağımsız stepline, etiket ve metadata; güvenli taraf
   kırmızı, üst taraf yeşil. Aşağı dönüş/momentum ve yukarı yapı uyarıları yalnız
   motorun sınıflandırmasından çizilir; basamak konektöründen yeni dikey rejim
   veya keyfî ek kural üretilmez. Var olan destek, sade görünüm ve kadraj
   sözleşmelerini koru; ayrıca temas işareti veya yeni alarm ekleme.
4. **Bağlantı sırası:** `/grafik` yolunu; sonra formasyonun özel/genel alarm
   karesini ve Stabil destek alarm karesini bağla. Katman hatası eski grafik
   ve bildirimi engellemez; yanlış/eksik veriyle sahte direnç göstermez.
5. **Doğrulama:** birim ve uçtan uca grafik testleriyle 1s/2s/4s/1g,
   kapanış/cutoff, günlük bilinirlik, eksik mum/kovalar, okların tam yerleri,
   ters renkler, iki katmanın çakışmadan yerleşmesi, grafik kill-switch'i,
   alarm kararlarının ve destek sonuçlarının değişmemesi, arşiv/manifest
   bütünlüğü ve genel regresyon doğrulanır. Ortam ve canlı teslim sınırları
   sonuçta açıkça belirtilir.

## 3. adım: uygulanan yerel bağlantı ve sınırları (2026-11-07)

### Kaynak, nedensellik ve hata yalıtımı

- `domain_engines/stabil/chart_bridge.py` yalnız grafik için çalışır: ham native
  günlük kaynağı ve intraday hedeflerde asıl 1s bileşenleri kontrol eder. Günlük
  yerine 1s'den türetilmiş seri native diye kullanılmaz. İşaretlenmiş kısmi
  mum, bilinen iç eksik kova/seans, uyuşmayan OHLCV, belirsiz tatil/yarım gün
  kapanışı ve tespit edilmiş ölçek değişimi gibi durumlar katmanı kapatır.
  Grafik ve mevcut alarm kararı yaşamaya devam eder; gerekçe snapshot/meta'da
  saklanır. Sağlayıcının hiç bildirmediği veya yanlış etiketlediği tüm eksik
  verilerin ve kurumsal aksiyonların bulunabildiği iddia edilemez.
- Günlük bölünme normalizasyonu geçmişi daha sonraki verilerle yeniden
  ölçekleyebildiğinden, bilinen split tespitinde direnç
  `daily_split_scale_unverified` ile kapatılır. Başka kaynak değişimlerinin
  saptanacağı garanti edilmez. `1g` hedefindeki OHLCV de ham native kaynakla
  karşılaştırılır; intraday hedef, kapanmış 1s bileşenlerinden doğrulanır.
- Kesim hedef karenin **son kapanmış mumundan daha ileri gitmez**. Her günlük
  snapshot yalnız kendi kapanışından, her direnç noktası yalnız hedef mumunun
  tam kapanışından itibaren eşleşir. Yanlış/hatalı durum taşıyan sonuç eski
  nokta veya oklar içerse bile çizilmez; seviyesi olan bir noktanın günlük
  bilinirlik zamanı da zorunludur. İlk eksik rolling kova atılır; hedef aralığı
  içindeki ve son hedef kovasının bilinen eksik bileşenleri doldurulmaz. Ancak
  tamamen bulunmayan bir son seans, kesimi geriye çekilmiş bayat grafikten her
  durumda ayırt edilemez; mevcut komut/tarama tazelik kapıları ayrıca önemlidir.
- `/grafik`te native günlük kaynak yok veya bayatsa sistem bu bağlantı için
  ayrıca günlük ağ isteği yapmaz. Güvenli kaynak bulunamazsa direnç çizilmez;
  sade olmayan manuel kare altyazısında kısa neden belirtilir. Otomatik
  grafiklerde neden snapshot/meta'dadır; mevcut public altyazı yolu her nedeni
  kullanıcıya göstermeyebilir. `BRENT` gibi BIST seansı doğrulanamayan makro
  sembollerde direnç gösterilmez.

### Görünüm ve kapsam

- Destek düz, bağımsız direnç kesiklidir; ayrı `Destek` / `Direnç` fiyat
  etiketleri ve metadata'ları vardır. Dirençte güvenli günlük durum kırmızı,
  üstüne geçilmiş günlük durum yeşildir. Fiyatın her intraday geçişi rengi
  anında değiştirmez. Geometrik dikey basamak, kendi başına yeni rejim veya
  ok sayılmaz.
- Dolu kırmızı `▼` güçlü dönüşü, boş kırmızı `▽` aşağı momentumu; boş yeşil
  `△` aday dikey yapıda yukarı **yapı uyarısını** gösterir. Uyarı fiyat yönü
  tahmini veya temas kanıtı değildir. Ayrı temas işareti eklenmedi; mevcut
  momentumun üç barlık **tekrar** kısıtı ilk sinyale bekleme eklenmeden korundu.
- Eski kadraj politikası korunur: fiyattan çok uzak seviye mumları sıkıştırmak
  için zorla kadraja alınmaz; bu durumda hazır bir direnç grafikte görünmeyebilir.
  `sade` görünüm mevcut sözleşmeye göre her iki Stabil katmanını gizler.
- `/grafik` bağımsız manuel istektir; otomatik grafik kill-switch'inden ayrı
  çalışır. Alarm grafikleri yalnız mevcut grafik anahtarı açıkken hazırlanır;
  kapalıyken direnç hesabı sıfırdır. Formasyon ve domain yollarında özel/genel
  kare aynı TF sonucunu paylaşır; domain adayları içinde yerel cache tekrarı
  önler. Geçersizleşme mevcut tek-kare kuralını korur. Destek motoru, aday
  seçimi ve destek/formasyon/domain metin alarmı dirence bağlanmadı.

### Arşiv duman testleri ve uygulama kapsamı

- Gerçek EFOR arşivinden yerel `/grafik` üreticisiyle 28.07.2026 **17:30 4s
  kapanışına** kadar çizilen örnekte son kapanış **20,66**, direnç **19,53**,
  destek **13,95**; iki katman ve işaretleri ayrı incelendi. Bu, daha önce
  ölçülen **13:30 kapanışlı** 19,80 mumuyla aynı bar değildir.
- Gerçek AKBNK arşivinden 06.01.2026 **17:30 4s kapanışına** kadar çizilen
  örnekte son kapanış **74,15**, direnç **73,65**, destek **68,60**; iki katman
  ve ayrı etiketleri incelendi. PNG başlığındaki 13:30, bu 4s mumunun **açılış
  etiketi**, 17:30 ise kapanışıdır. Son barda direnç oku yok; görselin daha
  önceki bir barında aday yapı uyarısı bulunur.
- Bu iki dosya yerel arşiv/üretici duman testidir; güncel piyasa, kârlılık,
  canlı Telegram teslimi veya ileriye dönük performans kanıtı değildir. Testte
  Telegram taşıması taklit edildi; canlı mesaj veya dağıtım yapılmadı.
- Yalnız kaynak kapısını görmek için daha önce seçilmiş 50 hissenin arşiv
  yakalama anında, son **360 kapanmış 1s** bardan türetilen 4s hedef ve native
  günlük veriyle kontrol yapıldı: **46 READY**, 3 tespit edilmiş split ölçeği
  (`ARZUM`, `DENGE`, `GSRAY`) ve 1 eksik/hatalı hedef kova (`DIRIT`). Bu bir
  canlı kapsama oranı, ok/getiri replay'i veya tüm veri hatalarının tespiti
  değildir. Tek yerel örneklemede 50 hesap toplamı yaklaşık 19,5 sn, en yavaşı
  0,90 sn idi; bu da üretim yük testi değildir.

### Son doğrulama — 2026-11-07

- Son kod ve kalıcılık testleriyle tek ve çakışmasız tam test koşusu:
  **3.979 başarılı, 43 atlandı** (`.venv/bin/python -m pytest -q`, Python
  **3.11.2**, 486,69 sn). Daha önce durdurulmuş/çakışmış koşular bu sonucun
  parçası değildir.
- Gerçek PNG üretimi, özel bildirim outbox hazırlama ve diskten yükleme, public
  snapshot JSON ile formasyon public kuyruğu ve public yardımcı outbox'ın diske
  yazılıp yeniden yüklenmesi ağsız sınandı. Her iki public kuyruktan yeniden
  yüklenen direnç katmanıyla iki PNG üretildi; taşıma sahtedir, gerçek Telegram
  yoktur.
- Dört tarihsel araştırma doğrulayıcısı başarılı; önceki rapor, manifest ve
  kaynak sözleşmeleri yeniden yazılmadı. `signals.py` destek hash'i korundu.
- Python **3.12 CI**, canlı sistem ve gerçek teslim bu yerel koşuda doğrulanmadı.
  `ruff check .` ve `git diff --check` son kontrolde çalıştırıldı.

### Sonraki ayrıntılı denetim

Manuel komut, gerçek formasyon, Stabil geri alımı, domain alarmı, toplu özet,
kadraj ve hata durumlarını gerçek arşivden üreten 15 ağsız uçtan uca senaryo,
12 seçilmiş PNG ve teslim sınırları ayrı raporlandı:
[Stabil direnç görsel ve teslim denetimi](STABIL_DIRENC_GORSEL_TESLIM_DENETIMI_2026-11-07.md).
Bu çalışma da canlı dağıtım veya gerçek Telegram teslimi değildir.
Ayrıntılı denetim sonrasındaki en güncel tam regresyon: **4.057 başarılı,
43 atlandı** (Python 3.11.2, çıkış kodu 0).
