# D7: Kâr gördükten sonra dönen işlemlerin domain anatomisi

## Soru ve yöntem

D7'nin 648 işlemini, giriş/stop/hedef ve 10 bar ufku değişmeden inceledik. “Kâr gördü”: girişten sonra, **çıkış barından önce**, bir mumun yüksek/düşüğü en az +0,5 başlangıç riski (R) gördü. Ardından o mumdan sonraki ilk ters yönlü kapanış barını seçtik (long: önceki kapanışa göre düşüş; short: yükseliş). Bu nokta gerçekleştiğinde bilinebilir; sonradan bakılarak bulunmuş mutlak tepe değildir. Fiyat bu barda hâlâ kârda olabilir. Çıkış barı, stop/hedef ve diğer hareketlerin mum içi sırası bilinmediği için dışarıda bırakıldı.

Önceki “zararlı işlemlerin %63'ü +0,5 R gördü” ifadesi güvenilir işlem-içi oran değildi: kullanılmış MFE stop/hedefe göre kesilmeyen 10 barlık saf yol metriğiydi ve çıkıştan sonraki hareketleri içerebilir. Aynı mumda kâr ve stop ihtimali de burada sıralanamadığından dışarıda; yeni oran da gerçek stop öncesi bar içi olayların kesin toplamı değil, ihtiyatlı alt ölçümdür.

## Evren

| Grup | İşlem | Çıkış barından önce +0,5R | Sonrasında çıkıştan önce ters kapanış |
|---|---:|---:|---:|
| Net zararlı tüm işlemler | 318 | 129 (%40,6) | 95 |
| Stop/gap ile net zararlı | 283 | 112 (%39,6) | **79** |
| Net kârlı karşılaştırma | 330 | 233 (%70,6) | **128** |

Aşağıdaki tablo, kullanıcının istediği stop grubundaki 79 işleme ve aynı koşulları sağlayan 128 kârlı işleme aittir. Bu iki grup aynı piyasalar ve dönemler bakımından eşleştirilmemiştir; çıkış barı hariç kuralı ve farklı işlem süreleri seçilim yanlılığı yaratabilir. Sinyal yüzdeleri üst üste binebilir.

## İlk ters kapanışta domainler

| Gözlem | Sonunda stop olanlar | Sonunda kârlı olanlar |
|---|---:|---:|
| RVOL < 0,75 | 19/64 **%29,7** | 53/106 **%50,0** |
| RVOL, giriştekinin yarısından az | 21/63 **%33,3** | 62/102 **%60,8** |
| Ters VP baskısı: yönlü pressure_5 < −0,13 | 7/64 **%10,9** | 5/106 **%4,7** |
| Karşı OB/FVG bandına temas | 9/79 **%11,4** | 25/128 **%19,5** |
| Karşı OB/FVG bandı kapanıştan itibaren ≤0,75 ATR ötede | 6/79 **%7,6** | 17/128 **%13,3** |
| Karşı Stabil seviyesine mum aralığında temas | 13/79 **%16,5** | 10/128 **%7,8** |
| Formasyon durumu RETEST_EDILIYOR | 15/79 **%19,0** | 1/128 **%0,8** |
| Ters external BOS/CHoCH, o barda | 0/79 | 0/128 |
| Kırılmış formasyon sınırının ≥0,5 giriş ATR ötesine ters kapanış | 0/79 | 0/128 |

VP için veri hazır/kullanılabilir ve ölçüm mevcut olanların paydası kullanıldı; stop grubunda 15/79 işlemde RVOL bilinmiyor. RVOL göreli hacimdir, ham hacim değil; girişle yarı kıyası her iki anda bilinen RVOL'ü gerektirir. OB/FVG için önceki kapanışta bilinen, yüksekliği ≥0,5 ATR olan karşı bandın ters kapanış mumundaki aralıkla kesişmesi sayıldı. Stabil teması fiyatın ilgili seviyeyi mum aralığında görmesidir; çizginin kendisi mevcut bar kapanışında bilinir, mum içi sıralama kanıtlanmaz. Formasyon durumu motorun bar sonu etiketidir; durumun aynı formasyona ait olduğu ayrıca bu tabloda garanti edilmez. Sıfır sonuç genel olarak olayın hiç oluşmadığını değil, bu tek ölçüm anında bulunmadığını gösterir.

## Yorum

* Bu örneklemde tek başına düşük RVOL veya karşı blok teması, stopa gidenleri ayırt etmiyor; hatta kârlı karşılaştırma grubunda daha sık. Bunları otomatik çıkış saymak kazananları kesebilir.
* `RETEST_EDILIYOR`, karşı Stabil teması ve ters VP baskısı araştırmaya değer **aday gözlemler**; gözlemsel, küçük ve seçilmiş örneklemdeki farklar tek başına çıkış kuralını doğrulamaz. Özellikle 15 ve 1 olaylık retest farkına göre eşik uydurmadan, farklı dönemlerde ve eşleştirilmiş kontrollerle doğrulama gerekir.
* Bu analiz kâr/stop sonrası durumları önceden biliyormuş gibi giriş veya çıkış kararı üretmez. İptal performansı, portföy getirisi ve faiz karşılaştırması ölçülmedi.

Kod: `python -m research.golge_v2_donus_anatomisi --workers 2`; tam olaylar `olaylar.csv.gz`, tüm net zararlıların ek özeti `ozet.json`. Ana ürün motoru değiştirilmedi.
