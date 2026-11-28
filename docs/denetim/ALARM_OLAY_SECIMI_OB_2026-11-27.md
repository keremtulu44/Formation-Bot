# Alarmı geliştirme: OB temasını gerçek kapanış tepkisinden ayırmak

**27 Kasım 2026 · Uygulama ve tarihli araştırma kaydı.**

Amaç: alarm geldiği mumda grafikte anlamlı bir olayın karşılığı olsun. Daha çok olumlu yorum, yeni görsel veya daha düşük alarm sayısı hedeflenmedi. İnceleme, mevcut domain alarmının **OB olay seçimine** odaklandı; bütün alarm yollarının tamamlandığı iddiası yok.

## 1. Arşivde saptanan tekrar eden sorun

Mevcut koşul: **kapanış, motorun son dışa aktardığı OB bandının içindeyse “bölge tepkisi”**.

Fakat OB motoru temas sırasında kullanılan kısmı çıkarıyor: boğa bölgesinin üst sınırı görülen en düşük fiyata, ayı bölgesinin alt sınırı görülen en yüksek fiyata daralıyor. Temastan **sonraki** bu kalan bantla kapanışı kıyaslamak, tepkiyi değil çoğunlukla tam tersini yakalıyor:

- Boğa OB'de kapanışın kalan banda girebilmesi çoğunlukla mum dibinde kapanması demek.
- Ayı OB'de aynı durum mum tepesindeki kapanışta oluşuyor.
- Bölgeye değip dışarı geri kapanan mum ise artık kalan bandın dışında olduğu için kaçıyor.

50 sembol × dört native TF, 19 Ekim–18 Kasım, 22 ortak seans içinde **196 eski OB tetik mumunun 196'sında da** kapanış ilgili uçtaydı: boğa için mum dibi, ayı için mum tepesi. Bu gelecekte fiyatın ne yaptığını değil, **alarm anında “tepki” diye hangi olayın seçildiğini** gösteriyor.

## 2. Dar kapsamlı mantık değişikliği

Yeni OB alarm sebebi için:

1. Bölge olay mumundan **önce** aktif ve biliniyor olmalı.
2. Kapanmış mumun yüksek/düşük aralığı, bu önceki kalan banda gerçekten temas etmeli.
3. Kapanış boğa bölgesinin üstüne, ayı bölgesinin altına **geri çıkmış** olmalı. Sınırda/henüz bölge içinde kapanış tepki sayılmıyor.
4. Aynı OB, yerel motorun kendi dolum/iptal mantığından sonra hâlâ geçerli olmalı. Tam kullanılmış/iptal edilmiş bölgeden tepki üretilmiyor.

Bu, yeni yön tahmini veya gelecekte kazandırma koşulu değil; o mumda gözlenen **temas + dışarı geri kapanış** olayı. Önceki en yakın aktif OB, her taraf için ayrı değerlendirilir; bütün uzak bölgeler taranarak alarm çoğaltılmaz. Önceki bölge/olay zamanı bilinmiyorsa OB tepkisi uydurulmaz; diğer alarm sebepleri bağımsız kalır.

OB motorunun aday, üç-kanıt, dolum, iptal ve dışa aktarım matematiği değiştirilmedi. Yalnız olayın öncesindeki bandı saklayan bir kanıt snapshot'ı eklendi. P6/P4, kalite, destek/mesafe, hacim, ana formasyon ve Stabil eşikleri değiştirilmedi. FVG'nin mevcut koşulları korunuyor.

### Cooldown yan etkisini de kontrol ettim

Yalnız OB koşulu değiştirilseydi bazı yeni OB bildirimleri, ardından oluşan farklı kanalı altı bar susturabiliyordu. Bu yüzden dar bir öncelik kuralı eklendi:

> Son gönderilen domain bildirimi **yalnız OB** sebebi taşıyorsa, daha sonraki mumdaki yeni bir **OB dışı** sebep bu OB-only bildirimin cooldown'una takılmaz.

Bu genel bir cooldown kaldırma değil: aynı mum/eskimiş mum, OB→OB tekrarı, bilinmeyen eski state veya zaten farklı kanal içeren önceki bildirim normal korumalarda kalır. Yeni kanal gönderildikten sonra normal cooldown tekrar uygulanır. Yeni BOS, CHoCH, formasyon, hacim veya FVG bilgisinin sadece daha önce bir OB teması bildirildi diye yutulmaması amaçlandı. Kullanıcıya yeni başlık/ok/görsel eklenmedi.

## 3. Gerçek örnekler — sonraki fiyatı görmeden

Zamanlar aşağıda İstanbul işlem tarihidir; kaynak CSV'de UTC mum açılış etiketi saklanır. Alarm uygunluğu mum kapanışından sonradır.

| Örnek | O anda bilinen bölge ve mum | Eski / yeni |
|---|---|---|
| **TUPRS 1d, 19 Ekim** | Önceki boğa kalan bandı 343,25–357,00; düşük **356,75**, kapanış **356,75**. Kapanış dışarı geri çıkmamış. | Eski “boğa tepkisi” veriyor; yeni OB sebebi vermiyor. Aynı mumdaki başka sebepler silinmiyor. |
| **ASTOR 1d, 19 Ekim** | Önceki boğa bandı 149,00–156,40; düşük **151,80**, kapanış **160,60**. Temas + bandın üzerine geri kapanış var, OB hâlâ geçerli. | Eski OB sebebi yok; yeni kapanışta tepkiyi yakalıyor. |
| **GARAN 1d, 19 Ekim** | Önceki ayı bandı 133,90–135,90; yüksek **134,00**, kapanış **132,50**. Temas + bandın altına geri kapanış var. | Eski OB sebebi yok; yeni aşağı taraftaki tepkiyi yakalıyor. |
| **DOCO 4h, 19 Ekim arşivli tam hat testi** | Aynı kapanışta CHoCH yanında gerçek OB geri kapanışı var. | Mevcut CHoCH korunuyor, daha önce kaçan OB olayı da aynı adayda yer alıyor; ayrı ikinci OB kartı yapılmıyor. |

ASTOR ve TUPRS için gerçek native domain + native Stabil destek kapısı + aday üretimi ayrıca test edildi. Bu iki testte politika P0'a alınarak OB olayının kendisi izole edildi; P6'nın o örneği mutlaka geçireceği iddia edilmiyor. DOCO testi üretimdeki gibi saatlikten türetilmiş 4h ve sahte taşıma kullanır; native sayım tablosuna eklenmez.

## 4. Önce–sonra: ne seçiliyor, ne korunuyor?

200 native serinin girdileri, önceki nedensel v2 koşusundaki **200 arşiv hash'iyle** eşleştirildi. Her mumda eski OB sonucu kayıtlı v2 satırıyla karşılaştırıldı. Yeni üretim yardımcı fonksiyonunun sonucu, motor güncellenmeden saklanan bant üzerinden ayrı yazılmış tanımla da karşılaştırıldı; tetiksiz mumlar dahil uyuşmazlıkta koşu durur. **200/200 geçmiş önek kontrolü geçti.**

Penceredeki OB olayları:

- **195 mum:** eski fiyat-içi koşulu var, kapanışta dışarı geri tepki yok.
- **1.531 mum:** önceden bilinen bölgeye temas ve geri kapanış var, eski koşul kaçırıyor.
- **1 mum:** iki yöntem de OB sebebi veriyor ama **farklı bölgeler/yönler** için. Bu ortak doğru olay sayılmadı; SNGYO 2h'de boğa kalan bandına kapanış ile ayı bölgesinden tepki aynı şey değil.
- Eski ve yeninin aynı yönde OB sebebi seçtiği mum yok. Bu yüksek fark, eski koşulun ne kadar farklı bir olayı ölçtüğünü gösteriyor; bir gelecek başarı yüzdesi değil.

195 kaldırılan OB-sebepli mumun 78'inde başka kanal da bulunduğundan ham aday tümüyle kaybolmuyor. 1.531 ek OB-sebepli mumun 557'sinde de başka kanal zaten var; bunlar yeni bağımsız kartlar gibi toplanmıyor.

### Mevcut politikalar ve altı bar cooldown ile hacim etkisi

**Aşağıdaki birim domain kanal adayı / ortak seans; Stabil destek kapısı, tarama programı, hedef/MTF birleştirmesi ve gerçek teslimden önce. Beklenen DM/gün değildir.** Tam geçmişteki adaylar cooldown'u kurar; pencere başında sıfırlanmaz.

| Politika | Önce seçilen | Sonra seçilen | Önce / seans | Sonra / seans |
|---|---:|---:|---:|---:|
| P0 | 1.780 | 2.198 | 80,91 | 99,91 |
| P6 | 725 | 841 | 32,95 | 38,23 |
| P4 | 426 | 426 | 19,36 | 19,36 |
| P7 araştırma alternatifi | 752 | 870 | 34,18 | 39,55 |

**Sayı artışı da azalışı da başarı ölçütü değil.** Bu tablo bildirim yükü bedelini görünür kılıyor; daha çok alarmın daha iyi olduğunu söylemiyor. P4'ün aynı kalması da OB kuralının değişmediği anlamına gelmiyor: P4'ün katman kapısı OB'yi tek başına seçmiyor.

P6 ayrıntısı:

- Önceden seçilen 725 mumun **707'si aynı mumda korunuyor**.
- Diğer **18'i yalnız eski OB fiyat-içi sebebiyle** seçilmişti; yeni tepki tanımını karşılamıyor.
- **134 başka mum** seçiliyor. Bunlar 134 bağımsız fırsat veya kârlı işlem değildir; cooldown takvimleri de değişebilir.
- Yeni OB kuralı tek başına bırakılsaydı 37 eski seçilmiş mum farklı kanallar taşıdığı hâlde cooldown'a takılacaktı. OB-only öncelik korumasıyla bu örneklemde P6'nın önce seçtiği **OB dışı bilgi taşıyan mumların hiçbiri kaybolmuyor**. Bu, başka veri/env için evrensel garanti değil.
- P0'da ise **32 eski seçilmiş mum** yeni takvimde hâlâ cooldown nedeniyle aynı mumda seçilmiyor; ayrıca 72 eski OB-only aday kalkıyor. Bu maliyeti saklamadım ve bütün cooldown sorunları çözüldü demiyorum. Yeni filtreyle sayıları hedefe uydurmadım.

## 5. Sınırlar ve doğrulama

Bu çalışma **OB olay seçimini** değiştirir; ana formasyon, Stabil, FVG ve domain birleşiminin bütün tasarım sorunlarını bitirmez. Önceki formasyon-çizgi/seviye düzeltmesi korunur. Yeni sert piyasa-yönü kapısı eklenmedi; fiyatın o an yaptığı tepki ile genel trend/tahmin aynı şey değildir.

- Gelecek getiri/ilk bariyer/başarı etiketi karar veya eşik seçiminde kullanılmadı. Bu kurala göre gelen olayın sonradan tersine dönmesi mümkündür.
- Aynı arşiv daha önce araştırıldı; kör holdout veya ileri canlı doğrulama değildir. Sabit başlangıçlı son480 native bar, üretimin kayan penceresinin tam kopyası değildir.
- Bölge motor tarafından tamamen kullanılmış/iptal edilmişse, güçlü bir geri kapanış olsa bile bu kural OB alarmı üretmez. Bu kapsam kaybı bilerek açık tutulur; ayrı bir sweep kuralı eklenmedi.
- Önceki en yakın bölgeyle sınırlı; bütün OB kayıtlarındaki her temasın kapsamını iddia etmez.
- FVG'de bölge-içi durum ile gerçek reaksiyon ayrımı ayrı inceleme konusu olarak kalıyor; OB değişikliği FVG'ye otomatik yayılmadı.
- Odaklı olay/öncelik testleri **35 geçti**. 13 dosyalık son regresyon **297 geçti, 1 atlandı** (192,13 sn). Gerçek arşivli üretim tarama → PNG → sahte Telegram teslimi, native motor/parite, cooldown ve önceki formasyon geometrisi testleri dahildir. Ruff ve `git diff --check` temiz. Bu, tam repo suite'inin yeniden çalıştırıldığı iddiası değildir.

**Canlıya dağıtım, commit/push, gerçek Telegram gönderimi ve Supabase yazımı yapılmadı.** Bu, çalışma dalında test edilen alarm mantığı değişikliğidir. Son yön/AI talimatı ekleri geri alınmış durumda kalır.

[Kanıt paketi ve yeniden üretim](../arastirma/sonuclar/ob_alarm_events_2026_11_27/README.md)
