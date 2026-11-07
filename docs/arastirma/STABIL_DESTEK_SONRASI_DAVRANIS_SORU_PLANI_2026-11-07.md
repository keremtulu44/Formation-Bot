# Stabil desteği çevresindeki davranış — konuşarak netleştirilecek çalışma planı

**Tarih:** 2026-11-07 · **Durum:** Kaynak mantığı incelendi; hipotez ve soru tanımlama sürüyor. **Replay başlatılmadı; kod, eşik, alarm ve destek kuralı değiştirilmedi.**

Kaynaklar: [`domain_engines/05_stabil.txt`](../../domain_engines/05_stabil.txt), gerçek uygulama [`stabil_support_lifecycle.py`](../../domain_engines/stabil/stabil_support_lifecycle.py), [kullanıcının fiyat/çizgi davranış modeli](STABIL_DAVRANIS_MODELI.md), [Stabil ana rehberi](STABIL_REHBERI.md).

## Stabil'in native destek mantığı — çalışma planının temeli

- Stabil, destek çizgisini günlük mumlardan üretilen **teyitli pivot dipleri** üzerinden kurar. Ayar `daily_pivot_len=4`; pivotun meydana geldiği bar (`origin`) ile iki taraflı yapıda teyit edilip bilinir olduğu bar (`confirmed`) farklıdır. Yeni seviye ancak Stabil'in o pivotu kullanabildiği tarihten itibaren geçerlidir; geriye dönük çizilmez.
- Günlük destek gözlemi için son iki teyitli tepe ve son iki teyitli dip yapısının kullanılabilir/uygun sıralı olması gerekir; güncel son teyitli dip destek seviyesi olur. Destek tabanı (`support_floor`) pivot kökenindeki ATR'den `destek − 0,35 × ATR_köken` olarak çıkarılır.
- Günlük kapanış çizginin üstünde/eşitse destek `ACTIVE`; kapanış çizginin altında ama floor üstünde/eşitse `BREACHED`; kapanış floor altındaysa `BELOW_FLOOR`. Fitilin çizgi altına sarkması, tek başına kapanışla kırılma değildir.
- Lifecycle olayları günlük mumda gerçek aralık çizgiyi kapsadığında temas/test; temas sonrası kapanış çizgi üstündeyse test/tutunma olayı; önceki kapanış çizgi altındayken sonraki kapanış çizgi üstüne/eşit dönerse geri-alım (`RECLAIMED`) üretir. Çizgi altı kapanış `BREACHED`; ATR tabanının altı ayrı `FLOOR_BROKEN` olayıdır. Desteğin yeni seviyeye taşınması, yeni teyitli pivotun bilinir olduğu zamanda `REBASED_HIGHER/LOWER` olur.
- Destek kimliği (pivot kökeni, teyit zamanı, fiyat) değişince eski çizgiyle yeni çizgi tek bir sürekli hareket gibi karşılaştırılmaz. Fiyatın destekten açılması/daralması aynı destek kimliği altında fiyat-destek mesafesinin değişimidir; çizginin yeni pivota taşınması ayrı olaydır.
- **Native lifecycle sabit destek için bir temas adedi/“3. temasta kırılır” kuralı üretmez.** Grafik sinyallerindeki `touch_count` ise ATR yakınlığı ve bar aralığı kullanan ayrı davranış katmanıdır. Araştırmada “gerçek temas” ve “yaklaşma” ayrı etiketlenmeli; bunlar birbirinin yerine kullanılmamalı.
- Haftalık trend, günlük trend ve 4s toparlanma Stabil'in ayrı bağlam çıktılarıdır; günlük destek yaşam döngüsü bunları tek bir yön sinyaline indirgemez. BOS/CHoCH, Volume Participation, OB ve FVG de bu native destek çekirdeğinin içinde hesaplanmaz; olay anında bilinen ayrı domain bağlamlarıdır.
- `STEPPING_UP/DOWN` gibi dikey/yatay aday rejimler native çizginin kullanıcı tarifindeki görsel rejim olduğunun kanıtı değildir. Çalışmanın ana sınıfları önce native çizgi kimliği ve rebase olaylarından kurulmalı; görsel yorum ayrıca doğrulanmalıdır.

## Kullanıcının çalışma fikri — soru kümelerine ayrılmış taslak

### 1. Yukarı/aşağı sonuç ayrımı ve mum incelemesi

Örnek düşünce: seçilmiş bir destek olayından sonra anlamlı bir izleme penceresinde olayların yaklaşık %70'i yukarı, %30'u aşağı sonuçlanıyorsa, iki grubun mum özellikleri nasıl ayrışıyor? Bu oran örnektir, ölçülmüş sonuç değildir.

Önce olay anında bilinen fiyat davranışları karşılaştırılır:

- Olay mumunun gövdesi ve toplam aralığı ATR'ye göre ne kadar büyük/küçük?
- Kapanış aralığın neresinde; üst/alt fitil, destek altına sarkma veya güçlü kapanış var mı?
- Mum yönlü güçlü mü, küçük/yönsüz mü, yoksa fitilli kararsız mı?
- Hacim o sembolün önceki günlük hacmine göre normal, düşük veya yüksek mi?
- Bir önceki birkaç günlük mum dizisi alıcı/satıcı baskısı, küçük gövde veya genişleyen aralık gösteriyor mu?

Sonuç gruplarının her biri kendi içindeki yüzdelerle değil yalnızca ortak paydada ve karşılaştırma grubuyla yorumlanmalı. “Aşağı giden %30'un %90'ı küçük mumdu” gibi ifade ancak olay etiketi, mum sınıfı ve paydalar önceden tanımlanıp gerçekten sayıldıktan sonra kullanılabilir.

### 2. Mumlardan sonra diğer domain'lerle bağlam

Mum tarafı tek başına ayırmıyorsa, **aynı olay kapanışında bilinen** ek bağlamlar sırayla katılır:

1. Son teyitli BOS/CHoCH yönü ve olay anında bilinirlik zamanı.
2. Volume Participation / günlük hacim rejimi.
3. Stabil'in ayrı günlük ve haftalık trend bağlamı; 4s toparlanma kanıtı.
4. Olay anında geçerli FVG/Order Block konumu, mesafesi ve temas bilgisi.

Her domain için yukarı ve aşağı sonuç gruplarında adet/oran, taban oran ve eksik/bilinmeyen durumu ayrı gösterilir. Bunlar “neden oldu” kanıtı değil, öncelikle **birlikte görülme/ayrışma** ölçümüdür. Çok küçük hücrelerden kural çıkarılmaz; BOS filtresi veya yeni Stabil eşiği bu plandan otomatik türetilmez.

### 3. Fiyat destekten uzaklaşınca çizgi ne zaman hareketleniyor?

Kullanıcının tarif ettiği sıralama ayrı bir yol analizi olarak kurulabilir:

`destekten uzaklaşma → yeni teyitli pivotla destek rebase'i → yeni basamakta fiyat davranışı → eski/yeni çizgiye dönüş veya kırılma`

Burada “fiyat uzaklaştı” bir fiyat/ATR olayı; “destek hareketlendi” ise native destek kimliğinin yeni teyitli pivotla değişmesidir. Bunlar aynı olay sayılmaz. Sonrasında yeni desteğe göre yukarı/aşağı tepki, fiyatın eski çizgiye dönüşü, destek rebase'inin fiyat dönüşünden önce/sonra gelmesi ve aynı-bar belirsizliği incelenebilir. Görsel olarak dik/yatay denmesi ayrıca kullanıcı örneğiyle eşleştirilmelidir.

### 4. Sabit destek, temas sayısı, altına sarkma ve geri alma

Native seviyenin aynı destek kimliğiyle değişmeden kaldığı dönem ayrı tutulur. Her olay için:

- Gerçek temas: günlük mumun `low ≤ support ≤ high` aralığı çizgiyi kapsar. Yakınlık bandına girip çizgiye değmeyen olaylar ayrı `yaklaşma` grubudur.
- Temas sırası: aynı seviyeye art arda değen mumlar bir temas dizisi mi, ayrı testler mi? Ayrı test saymak için önce çizgiden ne kadar uzaklaşma ve kaç günlük bar gerektiği konuşulmalıdır.
- Altına sarkma derinliği: fitilin desteğin altına ne kadar indiği; ATR ile normalize edilmiş en derin mesafe. Mumun kapanışı (çizgi üstü, support-floor ile çizgi arası, floor altı) ayrı kategori.
- Geri alma: aynı mumda mı, sonraki kaç günlük barda mı kapanış çizginin üstüne döndü; sonrasında çizgi üzerinde kalabildi mi?
- 1./2./3./4. **gerçek test** gruplarında ihlal, floor kırılımı ve geri alma oranları. “Üçüncü temas düşüş şartı olabilir” henüz yalnız bir hipotezdir; canlı kural değildir.

“Temizlik oranı” için iki farklı payda karıştırılmamalı: (a) çizgi altına fitil atan gerçek temasların ne kadarı çizgi üstü kapandı; (b) çizgi altı **kapanış** yapanların ne kadarı kaç gün içinde çizgiyi geri aldı. İlk ölçüm destek delinmesi değil, temas mumunun kapanış konumudur.

## Ölçümden önce konuşulacak kararlar

Buradaki amaç hazır seçeneklerden birini körlemesine seçmek değil; cevap, her tablonun anlamını belirleyecek:

1. Kullanıcının “destek üstüne çıkarken” dediği ilk ana örnek hangi grafikteki hangi olay: destek altı kapanıştan sonra geri alma mı, yukarıdan gerçek temas edip üstte kapanma mı, yoksa başka bir yol mu? İki yol da ilginçse ayrı kohortlar yapılır.
2. Günlük incelemede “%70 yukarı / %30 aşağı” derken yukarı/aşağı **hangi fiyat sonucunu** kastediyoruz: sonraki günlük kapanışın olay kapanışından yüksek/düşük olması mı; destekten uzaklaşmanın sürmesi mi; yoksa önce anlamlı bir ATR eşiğine ulaşma mı? Ufuk bu tanımdan sonra sabitlenir; aynı-bar çift eşik, eşik yok ve sansür ayrı kalır.
3. Kullanıcı tüm destek rejimlerinin **ayrı tabakalar** olarak görülmesini istedi: sabit aynı-identity segmentleri, yukarı rebase, aşağı rebase ve ihlal altındaki eski sabit çizgi birbirine karışmadan raporlanır. Birleşik genel oran ancak bu tabakalar ayrı gösterildikten sonra anlamlıysa eklenir.
4. Kullanıcı gerçek temasla ATR yakınlığının **ayrı** tutulmasını istedi. Çoklu temas için arka arkaya gelen temas barlarını ayrı test sayma kuralını ve testler arası ayrışma ölçüsünü ayrıca belirlemeliyiz.
5. Ana çalışma günlük destek ve günlük sonuçlarla başlayabilir. 1s/4s yardımcı verisi mum içi sıralama ve domain bağlamı için kullanılacaksa, günlük seviye bilinirliği, 1h→4h toplama/kova kalitesi ve günlük kapanışla eşleşme ayrıca doğrulanır; günlük native sonucu 4s proxy ile karıştırılmaz.

## Henüz yapılmayanlar

Bu çalışma planıdır, sonuç raporu değildir. Replay, yüzde hesabı, eşik seçimi, örnek seçimi, yeni alarm/filtre veya kod değişikliği yapılmadı. Önce yukarıdaki terimler ve ilk incelemenin sırası kullanıcıyla konuşulacak; sonra soru/plan önceden kaydedilip veriye bakılacaktır.
