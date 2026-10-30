# Telegram DM Replay Eğitim Modu — Tartışma Taslağı

**Durum:** Fikir ve tasarım taslağı; uygulanmış özellik değildir. Açık tercihler
kullanıcıyla netleştirilecek. Canlı botun karar, alarm ve kart davranışı bu
çalışmanın kapsamında değiştirilmez.

## 1. Amaç

Kullanıcı, geçmişte rastgele seçilen bir piyasa anında sadece o ana kadar
bilinebilen grafiğe bakarak kısa vadeli yön tahmini yapar. Tahmininden sonra
geçmişin gerçek devamını görür. Amaç yatırım tavsiyesi vermek veya modelin
getirisini kanıtlamak değil; grafik okuma pratiği ve geri bildirim sağlamaktır.

Bu mod, araştırma/replay ölçümlerindeki geçmiş veri ve nedensellik ilkelerinden
yararlanır. Soru üretimi için `dz_*` tablolarının veya mevcut araştırma
çıktılarının dolu olduğu varsayılmaz. Canlı Supabase'te `dz_*` tablolarının
boş olduğu 2026-10-29 denetiminde gözlemlenmiştir. Gerçek uygulamada veri
kaynağı ve geçmiş arşivinin dağıtımı ayrıca doğrulanmalıdır.

## 2. Kullanıcının tarif ettiği deneyim

### Görüşmede netleşen tercihler

- Dört zaman diliminin grafiği **tek Telegram albümünde** gösterilecek;
  **tahmin edilecek tek TF'yi kullanıcı seçecek.** Sonuçta da dört grafik
  albüm olarak gönderilecek. Amaç, zamanla hangi zaman ölçeğinde daha tutarlı
  olduğunu görebilmesine yardımcı olmak; ilk sürümde skor/geçmiş tutulmaz.
  Bu ölçüm işlem başarısı veya kişiye uygun işlem süresinin kanıtı değildir.
- Grafikler **botun mevcut grafiklerine benzer** olacak ve analizlerini içerecek.
  Yalnız kesit anında mevcut veriyle nedensel olarak hesaplanabilen analizler
  gösterilebilir; birebir çizimlerin kapsamı, yükü ve uyumluluğu değerlendirilecek.
- Gerçek tarih hem soru hem sonuç grafiklerinde **hiç gösterilmeyecek**. Tarihin
  grafik ekseni, başlık, açıklama, dosya adı veya mesajlardan sızmamasına dikkat
  edilmeli; tarih yerine göreli mum numaraları ve kesit çizgisi kullanılabilir.
- `/test ASTOR` ile belirli sembol, `/test` ile GitHub'daki geçmiş arşiv
  evreninden yeterli verisi olan bir sembol rastgele seçilecek. Sıra: önce
  sembol, sonra bu sembolün geçerli geçmişinden rastgele zaman. Önceki Replay
  raporundaki 177 sembol 176'lık havuz ile ayrı koşulan BRENT'i içerir; evrende
  endeks/emtia da bulunabildiğinden `/test` için hisse dışı sembollerin dahil
  edilip edilmeyeceği ayrıca belirlenmeli. Uygun veri yoksa açık hata verilir.
- **Canlı veri gerekmez:** Soru ve cevabın grafik/mum verisi GitHub'da bulunan
  `backfill_data/` geçmiş arşivinden gelir; seçim sırasında Yahoo veya başka
  canlı fiyat kaynağına başvurulmaz. Telegram mesajlaşması elbette ağ gerektirir.
  Arşivin dağıtılan ortamda gerçekten mevcut olduğu ve her TF için yeterli
  veri bulunduğu doğrulanmalı; veri yoksa başka bir kaynağa sessiz geçilmez.
- Seçilen geçmiş ana kadar olan veriyle botun analizleri normal grafiklere
  benzer biçimde yeniden çalıştırılır; seçilen andan sonraki mumlar yalnız
  cevabı ve sonuç grafiğini üretirken kullanılır. Gelecek bilgisi kullanan
  analizler gösterilmez; canlı tarama, alarm ve kayıt durumları değiştirilmez.
- Sistem **8, 10 veya 20 mumu eşit olasılıkla rastgele** seçecek ve tahminden
  önce açıklayacak.
- Sonuç için ilk aday bant **±1,5 ATR** olacak: kullanıcı önceki sınırları dar buluyor.
  ATR ve referans kapanış seçilen TF'de soru anında hesaplanacak. Eşik ve sınıf
  dağılımı geçmiş arşivde kontrol edilmeli; iyi sonuç garantisi değildir.
- İlk sürüm **skorsuz**: kalıcı performans/geçmiş özelliği sonraya bırakılacak.
- Sonuç mesajı **kısa** olacak: tahmin, gerçek sınıf, fiyat değişimi ve dört
  sonuç grafiği. Yatay bandın sınırları tahmin öncesi gizli, sonuçta açık olacak;
  soru grafiği ve açıklamasındaki ATR değerleri veya çizgilerinden bu sınırlar
  doğrudan çıkarılabiliyorsa onlar da tahminden önce gizlenmeli.
- Sonraki soru otomatik veya butonla başlamaz; kullanıcı yeniden `/test` yazar.
  Açık soru varken yeni `/test` eski soruyu iptal edip yenisini başlatır; eski
  yanıtlar geçersizdir. Bot yeniden başlarsa cevaplanmamış soru da iptal olur;
  kullanıcıya sonraki etkileşiminde yeni `/test` başlatması söylenir.
- Seçimler yazıyla yapılabilmeli. Düğmeler düzgün ve güvenli uygulanabiliyorsa
  yazılı girişe eklenebilir; düğme desteği şart değildir.
- Grafiklerdeki mum sayısı mevcut bot grafiklerinin kadraj mantığını takip eder;
  sabit 50/100 mum dayatılmaz.
- Ana yön sonucu, son görünen kapanış ile seçilen N. mumun kapanışı arasındaki
  farkın ±1,5 ATR bandıyla karşılaştırılmasıdır; aradaki fiyat hareketleri
  sonuç grafiğinde görünür, ilk dokunuş puanlamayı değiştirmez.
- Tahmin sonrasında **dört TF'nin devamı aynı bitiş anına kadar** gösterilecek;
  yalnız seçilen TF tahminin doğru/yanlış değerlendirmesinde kullanılacak.
  Seçilen TF'de hedeflenen mumun kapanışında diğer TF'lerin yalnız kapanmış
  mumları gösterilecek; yeni kapanmış mum yoksa bu durum belirtilecek. Tahmin
  anı her sonuç grafiğinde belirgin bir **dikey çizgi** ile işaretlenecek.

### Tartışmaya açılan öneriler

- **Ufuk (seçildi):** Sistem 8, 10 veya 20 mumu soru başında eşit olasılıkla
  rastgele seçer ve kullanıcının cevabından önce açıklar. Tüm seçenekler ilgili TF'de
  tamamlanmış mum sayısıdır. Günlük mumlar takvim günü değil işlem günüdür;
  seans, tatil ve yarım günler nedeniyle kesin bitiş saati varsayılmaz. Her
  İstatistikler daha sonra eklenirse TF/ufuk için ayrı örnek sayısı ve sonuç
  tutulabilir. Bu basit başlangıç, mevcut
  veriden otomatik olarak kısa/uzun ufuk seçen bir kurala göre açıklanabilir ve
  yanlılığı daha kolay ölçülebilir. Eşit rastgele seçim kullanıcının gerçek
  işlem süresini otomatik ölçmez; dilerse ileride ufuk seçimi de eklenebilir.
- **Yön (±1,5 ATR seçildi, doğrulama gerekli):** N. tamamlanmış mumun kapanışını,
  son gösterilen tamamlanmış mumun kapanışıyla karşılaştır. Başlangıç yatay
  bandı ±1,5 ATR'dir; ATR yalnız soru anına kadarki seçilen TF verisinden
  hesaplanır. Değişim bandın
  üstündeyse yukarı, altındaysa aşağı, sınırların kendisi de dahil bandın
  içindeyse yataydır. Sonuçta fiyat, yüzde, ATR ve eşik gösterilir. Bu **nihai
  veya kanıtlanmış ideal eşik değildir**: TF/ufuk başına sınıf dağılımı,
  yetersiz ATR, ham/ayarlanmış fiyat uyumu ve dengesiz sınıflar uygulamadan
  önce arşiv üzerinde kontrol edilmeli; dağılım dengesizse kullanıcıyla
  birlikte yeniden değerlendirilmelidir.

## 2.1 Deneyim

1. Kullanıcı botla özel mesajda örneğin `/test ASTOR` yazar.
2. Sistem geçmişten rastgele bir zaman seçer ve 1h, 2h, 4h, 1d grafiklerini
   kullanıcının değerlendirmesine sunar.
3. Kullanıcı tahminde bulunacağı tek zaman dilimini seçer. Sistem rastgele
   **8, 10 veya 20 mum** sonrasını seçip önceden bildirir.
4. Kullanıcı seçili TF için **yukarı / yatay / aşağı** tahmininde bulunur.
5. Sistem seçilen TF'deki sonucu ve dört TF için devam grafiklerini gösterir.
   Her sonuç grafiğinin ortak bitişi, seçilen TF'deki N. mumun kapanış anıdır;
   diğer TF'lerde o ana kadar tamamlanan mumlar gösterilir. Başka TF'de bu
   aralıkta yeni tamamlanmış mum yoksa açıkça belirtilir; değerlendirme
   penceresinin ötesindeki mumlar gösterilmez.
6. Kullanıcı başka bir örnek için tekrar `/test` komutunu yazar. İlk sürümde
   skor/geçmiş tutulmaz; açık sorunun iptali ve restart davranışı ayrıca
   kararlaştırılacak.

Buradaki `/test`, **Telegram komutu önerisidir**. `health_server.py` içinde
var olan, erişimi korunan HTTP `/test` tanılama uç noktasıyla aynı şey değildir.
İsim karışıklığı yaratıp yaratmadığına uygulama öncesi karar verilmeli.

### Örnek akış — yalnızca gösterim, nihai kurallar değil

```text
Kullanıcı: /test ASTOR
Bot: ASTOR için geçmişten bir kesit seçtim.
     [1h / 2h / 4h / 1d analizli grafikler: tek albüm — gelecek gizli]
     Hangi zaman diliminde tahmin yapmak istersin?
Kullanıcı: 4h
Bot: 4 saatlik grafikte 10 tamamlanmış mum sonra fiyat nasıl olacak?
     [⬆️ Yukarı] [↔️ Yatay] [⬇️ Aşağı]
Kullanıcı: ↔️ Yatay
Bot: Seçimin: Yatay. Gerçek sonuç: …
     Başlangıç kapanışı: … | Sonraki 10. mum kapanışı: …
     Değişim: … | Kullanılan yatay eşik: …
     [Seçili 4h grafikte önceki kesit ve sonraki 10 mum]
     [1h / 2h / 1d devamı: aynı bitiş anına kadar kapanan mumlar]
     Başka bir soru için /test veya /test ASTOR yaz.
```

Grafikler albüm olarak sunulur; restart açık soruyu iptal eder. Süre aşımı
henüz kararlaştırılmadı. Yazıyla yanıt zorunlu; düğmeler ise düzgün ve güvenli
uygulanabiliyorsa ek seçenektir.

## 3. Doğruluk ve oyun adaleti

- **Geleceği gizle:** Soru grafiklerinde seçilen kesitten sonraki mumlar,
  geleceğe dayalı çizimler, göstergeler, etiketler, hacim/olay özetleri,
  dosya adları veya görünür tarihler üzerinden cevabın açığa çıkması önlenmeli.
  Kullanıcı seçimine göre gerçek tarih soru ve sonuçta gizli kalır. Ancak sembol
  ve görünen fiyatlar bilindiği için gerçek dönemin tahmin edilmesi tümüyle
  engellenmiş sayılmaz; bu sınır açıkça kabul edilmeli.
- **Ortak zaman sınırı:** Dört zaman dilimi birlikte kullanılıyorsa her grafik
  aynı geçmiş anı esas almalı ve yalnız o anda gerçekten tamamlanmış mumları
  göstermeli. Özellikle günlük ve 2h/4h mumların kapanışı, seans ve saat dilimi
  dikkate alınmalı; tamamlanmamış büyük zaman dilimi mumu geleceğe sızmamalı.
- **Nedensel analiz:** Grafiğe zone, formasyon veya gösterge çizilecekse, bunlar
  kesit anındaki veriyle tekrar hesaplanmalı. Sonradan doğrulanmış pivot, olay,
  terminal durum veya geçmişe geriye dönük çizilen formasyon kullanılmamalı.
  Bunun maliyeti yüksekse ilk sürümde çıplak OHLCV grafiği daha güvenli olabilir.
- **Geçerli pencere:** Soru için yeterli geçmiş ve istenen sayıda sonraki
  tamamlanmış mum bulunmalı. Veri boşluğu, bozuk OHLC, kullanılmayan hacim,
  bölünme/düzeltme ve seans dışı barlar önceden ele alınmalı; eksik veya
  karşılaştırılamayan pencere soru diye sunulmamalı.
- **Yön tanımı açık olmalı:** Tercih edilen ±1,5 ATR yatay bandı ile önerilen
  son görünen kapanış–N. mum kapanışı karşılaştırması uygulanacaksa, sonuç
  mesajı kullanılan formülü, ATR'yi ve gerçek değişimi açıkça göstermelidir.
- **Rastgeleliğin sınırları:** Geçerli veri arasından seçim yapılmalı. Sembol,
  TF, tarih ve yön dağılımı otomatik olarak dengeli sayılmamalı; yeniden aynı
  soruların çıkması, yanlı örnekleme ve rastgele seçimin doğrulanması için
  politika belirlenmeli.
- **Eğitim sınırı:** Doğruluk puanı varsa, işlem getirisi veya gelecekteki
  performans olarak sunulmaz. Sınıf dağılımı ve basit tahmin kıyasları olmadan
  isabet oranı tek başına yanıltıcı olabilir.

## 4. Önerilen teknik sınırlar — henüz tasarım kararı değil

- **Yalnız DM:** Mevcut komut katmanı sahibin `TELEGRAM_CHAT_ID` DM'ini kabul
  ediyor; diğer özel sohbetler yok sayılıyor. Bu tasarım mevcut yetki modelini
  değiştirmez. Grup/kanala otomatik yayın yapılmamalı.
- **Durum ve güvenlik:** Soruya özgü kimlik, sohbet, sembol, veri sürümü,
  kesit zamanı, TF, ufuk, kullanılan eşik, doğru yanıt ve durum saklanabilir.
  Düğme yanıtı aynı sohbet ve hâlâ açık soru ile doğrulanmalı; eski/tekrarlı
  buton veya eşzamanlı yanıt ikinci sonuç üretmemeli. Kullanıcıya gelecek veri
  ve doğru yanıt callback içeriğinde gönderilmemeli.
- **Restart davranışı:** Yeniden başlatma cevaplanmamış soruyu iptal eder;
  kullanıcı sonraki etkileşimde yeni `/test` başlatmaya yönlendirilir. Eski
  düğmeler soru kimliğiyle reddedilmeli. Serbest yazı tek başına eski/yeni
  soruyu ayırt edemez: mesaj yanıtlama veya benzer bir bağlama mekanizması ve
  gecikmiş mesajların politikası tasarlanmalı. Oturumun süre aşımı ve
  kullanıcıya açıklaması ayrıca belirlenmeli.
- **Veri kaynağı:** Repo geçmiş arşivi `backfill_data/` 1h/1d verilerini
  içeriyor; 2h/4h serileri mevcut resampling mantığıyla türetilebiliyor. Ancak
  dağıtım ortamındaki erişim, gerçek kapsama tarihleri, veri ayarlamaları ve
  sembol varlığı test edilmeli. Yeni veri indirmeye bağımlılık veya Supabase'e
  yükleme yapılacağı varsayılmamalı.
- **Performans ve izolasyon:** Geçmiş analizi/grafik üretimi pahalı olabilir;
  tarama, alarm ve Telegram komut işleme döngüsünü bloke etmemeli. Eşzamanlı
  iş ve hız limitleri, hata ve iptal davranışı tasarlanmalı.
- **Grafik uyumu:** Mevcut grafik üretim altyapısı incelenip yeniden kullanım
  değerlendirilir; gelecekteki barları veya sonradan hesaplanan yapıları
  sızdırmadığı test edilmeden doğrudan eğitim moduna bağlanmaz.
- **Gizlilik:** Kullanıcının tahmin geçmişi veya sohbet kimliği gerekli
  olandan fazla saklanmamalı. Skor geçmişi istenirse saklama süresi, silme ve
  veri konumu açıkça belirlenmeli.

## 5. Tasarımda açık sorular

1. Mevcut grafiklere benzer analizlerde hangi çizimler as-of hesaplanabilecek;
   yoğunluk ve okunabilirlik nasıl yönetilecek?
2. Opsiyonel düğmeler, metin yanıtı, iptal, süre aşımı ve yeniden başlatma nasıl
   uygulanacak? Komut dinleyicisine gerekli uyarlamalar ve güvenlik doğrulanmalı.
3. Dört sonuç grafiğinin ölçekleri ve görünümü nasıl olacak?
4. ±1,5 ATR bandının sınıf dağılımı ve farklı TF/ufuklarda etkisi
   uygulamadan önce doğrulanmalı.
5. 177 sembollük arşiv evreninde hisse dışı sembollerin rastgele test
   seçimine dahil edilip edilmeyeceği ve yetersiz arşivli sembollerin ele
   alınması netleştirilmeli.

## 6. Uygulama öncesi kabul testleri

- İzinli DM dışında komut ve yanıt işlenmez; kanala/gruba gönderilmez.
- Soru seçimi yeterli geçmiş/gelecek ve geçerli bar gerektirir; veri yoksa
  anlaşılır mesaj döner ve uydurma veri kullanılmaz.
- Her TF, ortak kesit anında kapanmış verilerle sınırlandırılır; gelecekteki
  veriyi değiştirmek soru grafiğini ve soru anındaki analizleri değiştirmez.
- Kullanıcının yanıtı gelmeden sonraki mumlar/doğru sonuç paylaşılmaz; eski,
  tekrar edilmiş veya farklı sohbete ait düğme güvenli biçimde reddedilir.
- Seçilen eşiklerde sınır değerler (tam eşik, sıfır değişim, eksik/bozuk bar)
  tutarlı sınıflandırılır; sonuç grafiği ve metni aynı mumları kullanır.
- 1h/2h/4h/1d kapanış ve tatil/yarım gün senaryoları test edilir.
- Grafik veya veri hatası canlı taramayı, alarmı ve diğer komutları bozmaz.

## 7. Önerilen geliştirme sırası

1. Kullanıcı tercihlerini ve başarı ölçütlerini netleştir; belgeyi güncelle.
2. Erişilebilir arşivi ve ortak zaman kesitini, sızıntı testleriyle doğrula.
3. Tek soruluk, DM'ye özel en küçük akışı grafiklerle ağsız test et.
4. Telegram düğmeleri, durum yönetimi, süre aşımı ve hata yönetimini ekle.
5. Gerekirse kişisel skor/geçmişi ayrıca tasarla; canlı alım-satım önerisine
   veya otomatik alarm kararına bağlama.

## 8. İlk uygulama ve bilinen sınırlar

`/test [HISSE]` yalnız izinli DM'de yerel `backfill_data/` kullanır. Sembol
seçiminde bilinen endeks/makro semboller hariçtir. TF ve yön metin cevaplarına
sorunun ürettiği kısa kod eklenir; bu, yeni soru açıldığında eski gecikmiş
metnin başka soruyu cevaplamasını önler. Yeni `/test` önceki soruyu iptal eder;
arka plan işi varsa yalnız en son istek bekler. Ağ işlemi boyunca oturum kilidi
tutulmaz; ancak iptal anında Telegram'a zaten gönderilmiş bir albüm isteği
geri alınamaz. Böyle bir albüm ulaşsa bile eski sorunun kodu geçerli olmaz.
Restart oturumu siler. Düğme ve skor geçmişi yoktur.

Dört görsel tek albümdür; zaman ekseni ve tarih yazılmaz. TF'nin bot kadraj
kuralı, izole Argent formasyon motoru ve as-of OB/FVG replay bölge katmanları
kullanılır; tüm canlı grafik analizlerinin birebir uygulandığı iddia edilmez.
Yalnız kesit öncesi hesap yapılır; sonuçtaki dikey çizgi başlangıç sınırıdır.
As-of sınırı mevcut `data.mum_kapanis_anlari` kuralına dayanır; geçmiş takvim
ve sağlayıcı zaman etiketlerinin doğruluğu ayrıca kontrol edilmelidir. Pencere
OHLC/geçmiş/gelecek ve %30 sıçramaya karşı kontrol edilir; arşivde tüm olası
seans boşlukları veya kurumsal işlemler henüz eksiksiz doğrulanmış değildir.
Bu nedenle gerçek dağıtımdan önce veri kapsamı ile kaynak/yarım gün örnekleri
ve Telegram'a teslimat elle doğrulanmalıdır. Render/üretimde arşiv yoksa hata
verilir; otomatik veri indirilmez. Testler Telegram'ı taklit eder; gerçek DM
mesajı veya canlı deploy yapılmamıştır.
