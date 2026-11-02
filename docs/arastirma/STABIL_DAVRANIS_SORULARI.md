# Stabil — 48 davranış sorusu sicili

**Yeniden kayıt:** 2026-11-01. Önceki dosya bulunamadığından konuşmadan yeniden oluşturuldu.
A01–H06 kimlik dizisi ve araştırma ayrımları kaydedildi; soru ifadeleri özetlenerek yeniden yazıldı. **Soru metinlerinin ve kimlik→ölçüm eşlemesinin eski dosyayla birebirliği doğrulanamadı.** Aşağıdaki sicil kurtarılacak orijinalle karşılaştırılması gereken araştırma taslağıdır; eski dosyanın bayt-kopyası veya çalıştırılmış cevap kodu değildir.
[Ana rehber](STABIL_REHBERI.md) · [Davranış modeli](STABIL_DAVRANIS_MODELI.md) · [Çalışma geçmişi](STABIL_CALISMA_GECMISI.md).

## Ortak sözleşme

Başlangıç o anda bilinen gerçek kapanıştır; pivot kökenine geri taşınmaz. Yataylık,
gelecekte ne kadar süreceğine göre tanımlanmaz. Kullanıcının teyidine yeni 2/3/5 mum
bekleme koşulu eklenmez. Süre ve mesafe eşikleri ölçümden önce sabitlenir.

Her cevapta n, tam ufuk, ATR geçerli n, sansür, sembol yoğunlaşması; ortalama/medyan,
MFE/MAE, iki yönlü eşik ve ilk temas sırası; dönem ve karşı örnekler bulunmalı.
İlk bilinmeyen yaş/temas/epizot UNKNOWN; örtüşen olaylar bağımsız işlem değildir.
Aynı mumdaki çift eşik belirsiz. 1/4/8/10/12/16 adet 4H mum farklı ufuklardır.
Eski S01–S32 karar kapısı bu yeni soru ad alanına otomatik uygulanmaz.

## A — Uzaklaşma ve takip

| Kimlik | Soru | Ölçüm/yanılgı kontrolü |
|---|---|---|
| STB-BHV-A01 | Fiyat uzaklaşınca önce destek mi yukarı güncelleniyor, fiyat mı eski desteğe dönüyor? | İlk olay yarışması; aynı checkpoint, henüz hiçbiri ve sansür ayrı. |
| STB-BHV-A02 | Aynı uzaklığa hızlı veya yavaş çıkmak bu iki yolun oranını değiştiriyor mu? | Mesafeyi benzer tut, hız ve süreyi ayrı ölç. |
| STB-BHV-A03 | Destek takibe başladığında yükselişin ne kadarı geride, ne kadarı ileride? | Gerçekleşmiş tepkiyi giriş sonrası getiriyle birleştirme. |
| STB-BHV-A04 | Destek takip etmeden bekleme uzadıkça fiyatın geri dönüş riski artıyor mu? | Sadece o ana kadar bilinen bekleme; gelecekte takip etmeyecekleri baştan seçme. |
| STB-BHV-A05 | Mesafe küçülürken fiyat mı geri geliyor, destek mi fiyatı yakalıyor? | Mesafe değişimini iki katkıya ayır; aynı yaklaşma etiketi iki farklı yol olabilir. |
| STB-BHV-A06 | Destek fiyatı yakalayınca devam mı geliyor, hareket tükenmiş mi oluyor? | Yol içi tepe ile kapanışta korunan kazanç ayrı. |

## B — Yükseliş sonrası yataylaşma

| Kimlik | Soru | Ölçüm/yanılgı kontrolü |
|---|---|---|
| STB-BHV-B01 | Yukarı takip sonrası yataylaşmanın ardından devam, bekleme ve kırılma nasıl dağılıyor? | Kesin yataylaşma eşlemesi olmadan native güncelleme yalnız proxy. |
| STB-BHV-B02 | Yeni yataydan önce yükseliş uzun sürmüşse kırılma daha sık veya sert mi? | Önceki yükseliş süresi ile yatay yaşını karıştırma. |
| STB-BHV-B03 | Önceki yükselişin şiddeti ve hızı, süreden bağımsız ek bilgi taşıyor mu? | Benzer yaş/sürede ATR kazanç ve hız karşılaştırması. |
| STB-BHV-B04 | Uzun yatay seviyelerde bir sonraki ani aşağı kırılma gerçekten daha az mı? | O ana kadar geçen yaş; sağ kalım ve mesafe farkını kontrol et. |
| STB-BHV-B05 | Yeni yatayda kırılma sıklığı mı, kırılınca şiddet mi artıyor? | İki oranı ayrı ve koşulsuz zararla birlikte raporla. |
| STB-BHV-B06 | Yataylaşma fiyat sakinleşmesini mi, pivot teyit gecikmesini mi yansıtıyor? | Bağımsız görsel/native eşleme ve köken–teyit gecikmesi gerekli. |

## C — Temas ve tepki dizileri

| Kimlik | Soru | Ölçüm/yanılgı kontrolü |
|---|---|---|
| STB-BHV-C01 | Yukarı takip sonrası ilk temas, temas olmadan devamdan nasıl farklı? | Temas ancak bilindiği anda çapa; gelecekte temas edecekleri baştan seçme. |
| STB-BHV-C02 | İlk ve sonraki bağımsız temaslar aynı tutunmayı mı üretiyor? | Aradan ayrılmadan duran mumlar yeni test değil; başlangıç bilinmiyorsa sıra UNKNOWN. |
| STB-BHV-C03 | Yavaş yaklaşmakla sert düşerek desteğe gelmek farklı mı? | Aynı yaş/mesafede yaklaşma hızı ve olay mumu büyüklüğü. |
| STB-BHV-C04 | Temaslardan sonra uzaklaşamamak kırılma riskini biriktiriyor mu? | Yalnız geçmişte tamamlanmış başarısız tepkiler. |
| STB-BHV-C05 | Tepkilerin giderek küçülmesi, temas sayısından daha açıklayıcı mı? | Tamamlanmış ardışık tepki boyları, her tepkiye sabit ATR. |
| STB-BHV-C06 | Güçlü ilk tepkiye rağmen hızlı yeniden test kazancı geri verdiriyor mu? | Benzer tepki boyunda yeniden teste geçen süre. |

## D — Kırılma boyutu ve biçimi

| Kimlik | Soru | Ölçüm/yanılgı kontrolü |
|---|---|---|
| STB-BHV-D01 | Küçük ve derin aşağı kırılmalarda geri alım ihtimali farklı mı? | O ana kadar bilinen derinlik; geri almayan/sansürlü olaylar tabanda. |
| STB-BHV-D02 | Geri alımdan sonra küçük ve derin kırılmaların kalan tepkisi farklı mı? | Derinlik ve altta kalma süresini ayrı tut; önceki destek yolu da önemli. |
| STB-BHV-D03 | Aynı derinliğe tek mumda ve yavaş düşerek gelmek farklı mı? | Derinliği benzer tut, hız/süreyi karşılaştır. |
| STB-BHV-D04 | Ana seviye ile native tolerans sınırının kaybı geri dönüşü ayırıyor mu? | Level ve floor ayrı; epizot başlangıcı bilinmiyorsa geçmiş ihlal UNKNOWN. |
| STB-BHV-D05 | Gap ve seans içi kırılma benzer derinlikte farklı mı? | Gerçek açılış/kapanış; günlük gap ile intraday gap aynı etiket değil. |
| STB-BHV-D06 | Geri alıma kadar hareketin çoğu zaten tüketiliyor mu? | Önceden bilinen dipten geri alıma ve sonrasında kalan harekete ayrı bak. |

## E — Sabit desteğin geri alınması

| Kimlik | Soru | Ölçüm/yanılgı kontrolü |
|---|---|---|
| STB-BHV-E01 | Destek sabitken ilk deneme ne sıklıkla üstte kapanışa dönüşüyor? | Fitil, başarısız deneme, kapanış ve hiç denemeyenler ayrı. |
| STB-BHV-E02 | Başarısız denemeden sonra önce destek mi aşağı iner, fiyat mı yeniden dener? | İlk sonraki olay, bekleme, aynı checkpoint ve sansür. |
| STB-BHV-E03 | İlk ve birkaçıncı denemede geri alım aynı tepkiyi mi veriyor? | Bağımsız deneme sayısı; derinlik/süre kontrolü. |
| STB-BHV-E04 | Altta kalma uzarsa sabit seviyenin geri alım tepkisi güçleniyor mu? | Süre ile derinliği karıştırma; baştan başarılı geri alımları seçme. |
| STB-BHV-E05 | Güçlü geri alım mumu bilgi mi taşıyor, kalan tepkiyi mi tüketiyor? | Olay mumunu geleceğe katmadan kalan hareketi ölç. |
| STB-BHV-E06 | Geri alım sonrası yeniden testte tutunmayı beklemek faydalı mı? | Aynı olaylarda eleme yararı, gecikme ve kaçan hareket birlikte. |

## F — Aşağı takip ve yeniden yerleşme

| Kimlik | Soru | Ölçüm/yanılgı kontrolü |
|---|---|---|
| STB-BHV-F01 | Hareketli/dikey bölümde yukarı deneme, yataylaşma sonrasından daha mı çok geri dönüyor? | Kullanıcının altı boş hipotezi; kesin native eşleme şart. |
| STB-BHV-F02 | Üstte görünmeyi fiyat mı, desteğin aşağı taşınması mı oluşturuyor? | Fiyat tek başına / destek tek başına / ikisi de yeterli / birlikte gerekli ayrımı. |
| STB-BHV-F03 | Kesin yataylaşma anında üstte veya altta olmak sonucu değiştiriyor mu? | Eşleme yoksa proxy doğrudan cevap diye sunulmaz. |
| STB-BHV-F04 | Tek büyük aşağı basamak ile birçok küçük basamaktan sonra toparlanma farklı mı? | Toplam aşağı mesafe benzer; güncelleme ritmi ayrı. |
| STB-BHV-F05 | Yataylaşma sonrası yeni dip yapmamak ek bilgi katıyor mu? | Zorunlu yeni teyit değil, ayrı aday soru; beklemenin maliyeti de ölçülür. |
| STB-BHV-F06 | Yerleşip tekrar aşağı hareketlenmek tek yerleşmeden farklı mı? | İkinci hareket öğrenildiği andan sonrası; gelecekte sabit kalanı ideal seçme. |

## G — Yol bağımlılığı ve karşı örnekler

| Kimlik | Soru | Ölçüm/yanılgı kontrolü |
|---|---|---|
| STB-BHV-G01 | Aynı güncel konuma farklı yollardan gelmek fiyatı ayırıyor mu? | Yukarıdan yerleşme / aşağıdan yerleşme / eski seviyeyi geri alma. |
| STB-BHV-G02 | Aynı fiyat civarındaki eski ve yeni teyit edilen destek farklı mı? | Seviye yakın olsa da kimlik/köken/teyit geçmişlerini birleştirme. |
| STB-BHV-G03 | Eski ve yeni destek arasında gidip gelince hangi seviye açıklayıcı? | İkisi de önceden bilinen seviyeler; sonradan işe yarayanı seçme. |
| STB-BHV-G04 | Önceki başarısız destekler yeni desteğin sonucunu etkiliyor mu? | Olay öncesi gözlenen geçmiş; arşiv öncesini sıfır sayma. |
| STB-BHV-G05 | İki yönlü savrulma artınca yön avantajı kayboluyor mu? | Yukarı MFE ile yetinme; aşağı yol ve kapanışta korunma da gerekli. |
| STB-BHV-G06 | Hacim/4H alıcı kanıtı hangi yolda ek bilgi veya gecikme getiriyor? | Yol benzer; eksik hacim olumlu teyit sayılmaz. |

## H — Kontrol ve sağlamlık

| Kimlik | Soru | Ölçüm/yanılgı kontrolü |
|---|---|---|
| STB-BHV-H01 | Benzer fiyat düşüşlerinden sonra Stabil olayı olmadan da aynı tepki var mı? | Aynı sembol/dönem, ön hareket, oynaklık ve saatle eşleştirilmiş kontrol. |
| STB-BHV-H02 | Basit/gecikmeli referans seviyeleri aynı ayrımı yapıyor mu? | Önceden sabitlenmiş basit kontrol; sonuçtan en iyi çizgi seçilmez. |
| STB-BHV-H03 | Aynı yol farklı piyasa rejimlerinde korunuyor mu? | Olay anında bilinen piyasa rejimi; haftalık hisse durumu yalnız proxy olabilir. |
| STB-BHV-H04 | Sonucu birkaç hisse/gün/aşırı hareket mi sürüklüyor? | Medyan, eşit-sembol, yoğunlaşma, leave-one-out ve dönem kırılımları. |
| STB-BHV-H05 | İlk izleyen 4H kapanışını beklemek farkı yok ediyor mu? | Saatlik fiyat var diye saatlik native teyit var sayılamaz. |
| STB-BHV-H06 | Ayrımlar yeni dönem/sembol ve komşu eşiklerde korunuyor mu? | Görülmüş 100 sembol gerçek kör test değil; çoklu hipotez ve bağımsız doğrulama. |

## Öncelik ve durum

1. Önce görsel/native eşleme, yaş, epizot ve fiyat/çizgi kaynaklı geçiş tanımları.
2. Model omurgası: A01, B01/B02/B04, D02, E02, F01/F02.
3. Kaçan mekanizmalar: A05, B05, D06, E05, G01/G05.
4. Bağımsız katkı ve sağlamlık: H01–H06.

Önceki konuşmada **33 operasyonel ölçüm / 8 proxy / 7 açık** durum raporlandı.
Proxy başlıklar: B01/B02/B03/B05/C01/F05/F06/H03. Açık başlıklar:
B06/F01/F03/H01/H02/H05/H06. Sonuç dosyaları şu anda bulunmadığı için bu
dağılım yeniden hesaplanmış değil; [kanıt durumu](STABIL_DOSYA_ENVANTERI.md).

Cevap şablonu: **TANIM → VERİ → KARŞILAŞTIRMA → TABLO → KARŞI ÖRNEK → SINIR → SONUÇ**.
İzinli sonuçlar: betimsel ayrım / belirgin ayrım yok / dönemlere göre değişiyor /
örnek yetersiz / tanım-veri yetersiz / ayrı doğrulama gerekli. Hepsi canlı kuraldan ayrıdır.
