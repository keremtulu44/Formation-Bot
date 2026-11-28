# Alarm nerede tetikleniyor? Geometri ve zamanlama kontrolü

**27 Kasım 2026 — araştırma + dar kapsamlı hata düzeltmesi.**

## İstenen ve geri alınanlar

Amaç grafiğe ek görsel/yön etiketi koymak veya alarmları olumlu göstermek değil: **alarmın mevcut yapının anlamlı olduğu mumda tetiklenmesi**.

Yanlış anlaşılarak son eklenen `_yon_isareti` değişikliği ve üç AI talimatına eklenen yön/olumluluk kuralları geri alındı; yalnız bunları sınayan `test_direction_readability.py` kaldırıldı. Önceki mum/AI güvenilirliği, kısa alarm ve nedensel replay çalışmaları korunuyor. Yeni görsel, yön tahmin kuralı veya başarı oranına göre seçilmiş filtre eklenmedi.

## Somut hata: eğimli çizgiye yatay fiyat muamelesi

Formasyon motoru aynı sabit çapalardan geçen eğimli sınırı **her olay mumunda** değerlendiriyor. Bildirim katmanı ise kırılım gününde bu çizginin sahip olduğu tek fiyatı kullanıyordu. Eğimli çizginin güncel değeri ile geçmişteki değeri aynı değil.

Bu yüzden motorun o mumda teyit/retest koşulunu sağladığı bazı olaylar bildirim kapısında tekrar engelleniyordu. Bu, modelin yükseliş/düşüş tahmini veya grafik okunabilirliği sorunu değil; iki katmanın farklı seviyeyi kontrol etmesi.

**Örnek — AKBNK, native 2h, 21 Ekim 2026 17:00 TSİ açılış etiketli mum:**

| Ölçü | Değer |
|---|---:|
| Motor durumu | Alçalan Üçgen · retest başarılı |
| Kalite / mevcut eşik | 86,49 / 78 |
| Mum kapanış fiyatı | 67,20 |
| Kırılım anındaki eski çizgi fiyatı | 67,2273 |
| Aynı çapaların olay mumundaki değeri | **66,8750** |

Kapanış güncel çizgiyi koruyor; eski sabit fiyat kontrolü reddediyor. Sabit başlangıçlı replay'de aynı durum için eski kapı ancak **iki mum sonra** geçiliyor. Aynı örnek olay anında kesilmiş **360 ve 480 bar** geçmişle de ayrı ayrı yeniden üretildi. Tablodaki saat açılış etiketidir; alarm uygunluğu o mum **kapandıktan** sonradır.

İşlem yalnız yukarı olayları açmak değil: örneğin YKBNK native 1d, 19 Ekim İstanbul tarihli aşağı teyitte kapanış 36,10; eski referans 35,98, olay çizgisi 36,1964. Güncel alt çizginin altında olmasına rağmen eski kapı bunu da reddediyordu.

## Yapılan düzeltme

- `patterns/mathutil.py`: mevcut adayın **kendi iki çapasından** olay mumundaki çizgi değeri okunur; yeni çizgi, seviye veya yön türetilmez.
- `bot/security.py::_alert_break_level`: teyit/retest için bar indeksi ve sağlam çapalar varsa bu değer kullanılır. Çapa/bar yoksa eski davranış korunur. Geçersizleşme bildiriminin eski referansı değiştirilmez.
- `bot/scan.py`: zaten hesaplanan `snap.bar_index` seviye seçimine aktarılır. Kapanış kapısı, karttaki seviye ve ilgili mesafe hesabı aynı referansı kullanır.
- `tutarlilik.py`: bar indeksi mevcut olduğunda aynı geometri hesabını kullanır.

**Değişmeyenler:** motorun kırılım gücü, teyit penceresi, retest koşulları, kalite eşikleri, mum-kapanış güvenliği, cooldown, tekilleştirme, P6/P4 politikaları, Stabil ve domain alarm koşulları. Çizginin içinde kalan kapanış yine geçmez; eğim tersineyse yeni kontrol eski sabit fiyattan daha kısıtlayıcı da olabilir. Yeni bir tetik türü eklenmedi.

## 200 seri üzerinde önce / sonra

`research/formation_trigger_audit.py`, 50 sembol × 4 native TF'de sabit başlangıçlı son480 barı ileri yürütür. Özel motorun kimlik deposu anahtarı None; canlı durum/Telegram/Supabase kullanılmaz. Her seri ilk %75 öneğiyle ayrıca karşılaştırılır: **200/200 eşit**. Düzeltilmiş seviye, gözlenen bütün teyit/retest satırlarında motorun kendi kırılım çizgisinin olay mumundaki değeriyle ayrıca karşılaştırılıp eşitliği doğrulanır.

Ortak araştırma tarihi **19 Ekim–18 Kasım 2026**. Durum tekrarlarını alarm saymamak için aynı formasyon × durum × duruma giriş mumu tek bir **durum dönemi** olarak ele alındı. Aynı formasyonda daha sonraki yeniden retest ayrı dönem olabilir; bağımsız işlem/fırsat sayısı değildir.

| Kalite + kapanış kapısından ilk geçiş | Eski sabit fiyat | Aynı geometrinin olay-mumu değeri |
|---|---:|---:|
| Pencerede ilk kez uygun olan durum dönemi | 315 | 360 |
| Duruma girildiği mumda uygun | 297 | 360 |
| Bir mum bekleyerek uygun | 14 | 0 |
| İki mum bekleyerek uygun | 4 | 0 |
| İlk uygun kapanışın çizgiye medyan yönlü uzaklığı | 0,819 ATR | 0,654 ATR |

- **45 durum dönemi** eski kapıda gözlenen durum boyunca hiç geçmezken geometrisiyle uyumlu kapıdan geçebiliyor: 21 teyit, 24 retest. Bunların çizgiye medyan uzaklığı 0,160 ATR.
- **18 durum dönemindeki 1–2 mum ek bildirim-kapısı gecikmesi** gideriliyor. Bu, motorun teyit bekleme süresinin kaldırılması değildir.
- Bu örneklemde eski kapının geçirdiği fakat yeni kapının bütün durum boyunca engellediği dönem yok. Bunun evrensel garantisi yok; yükselen üst çizgi karşı örneği testte eski fiyatın yanlış geçireceği kapanışı reddediyor.
- 699 teyit/retest **durum satırının** 136'sında eski fiyat ile motor çizgisinin kapanış kararı farklı; 110'unda kalite eşiği de geçilmiş. Bunları 110 bağımsız kaçırılmış alarm saymıyoruz.

**Bu rakamlar teslim edilmiş mesaj sayısı değildir.** Burada kalite + kapanış katmanı ölçülüyor; bildirim/teslim tekilleştirmesi, MTF birleştirmesi, hız limitleri, makro izinleri ve canlı tarama saati ayrıca uygulanır. Native sabit başlangıçlı replay, üretimin kayan pencere/kimlik depolu replay'inin birebir kopyası değildir. Bu nedenle +45'i beklenen DM artışı diye kullanmamak gerekir. Gelecek getirisi veya kazanma oranı ölçülmedi, eşik optimize edilmedi.

## Erkenlik, geçlik, tekrar ve diğer alarm yolları

- **Erkenlik:** teyit/retest durumuna girmeden bildirim açılmadı; kapanmış mum ve kapanışın çizgi dışında olması koşulları korunuyor. Fitil/temas tek başına teyide çevrilmedi.
- **Geçlik:** ispatlanan sorun, motor durumundan sonra ikinci kapının yanlış seviyeyi bekletmesiydi. Bu düzeltildi. Motorun kendi teyit gecikmesi ayrı bir tasarım tercihidir ve değiştirilmedi.
- **Hareketi kovalamak:** düzeltmeden sonra bile ilk uygun 360 dönemin 120'si çizgiden >1 ATR uzakta. **Bu tek başına yanlış alarm demek değildir.** Güçlü kırılım ile geç kalmış giriş ayrımı çözülmüş sayılmadı; buna bakıp yeni mesafe filtresi eklenmedi.
- **Tekrar / yollar arası çakışma:** gerçek arşivli tam tarama testi aynı mumda formasyon retesti ve ayrı domain olaylarının birlikte bildirilebildiğini doğruluyor. Domain politikası P0'a ayarlı bu tesisat testinde AKBNK için bir formasyon ve iki domain kartı var; aynı şeyi üç defa ölçen bağımsız fırsatlar gibi sayılmamalı. Bunu gizlemek için diğer alarm yollarını kapatmadım.
- **Stabil:** güçlü geri-alım seçimi, ters yapı ve yakın engel kontrolleri bu yamayla değişmedi; ilgili arşiv/teslim regresyonları çalıştırıldı. Stabil ve domain için bütün kapılardan geçen kapsamlı canlı zamanlama replay'i bu çalışma kapsamında tamamlanmış değildir.
- **Domain:** fiyatın OB/FVG bölgesinde bulunması ile doğrulanmış dönüş aynı şey değil; mevcut bazı kanal koşulları ilkiyle çalışıyor. Bu çalışmada kanıtsız bir dönüş/mesafe filtresi eklenmedi. Önceki domain aday akışı ölçümleri korunuyor, ana formasyonla karıştırılmıyor.

## Doğrulama ve sınır

- Geometri/olay-yeri testleri: **21 geçti**. İki yönde eğimli sınır, içeri kapanışın reddi, geçersiz/eksik çapa, tarihî iptal referansı, dört TF'de önek/değiştirilmiş gelecek bağımsızlığı ve 360/480 bar gerçek örnek dahil.
- Gerçek arşivli tarama → kart → PNG → sahte Telegram taşıması testi, daha önce yanlış sabit fiyat yüzünden hiç gönderilmeyen AKBNK 4h retestini artık motor çizgisiyle aynı seviyede geçiriyor. PNG üretimi gerçek, hedefler ve taşıma sahte; canlı mesaj yok.
- İlgili **12 dosyalık regresyonda 187 test geçti (189,03 sn)**; yukarıdaki 21 test bu gruba dahildir, toplanmaz. Kapanış/teslim, tekrar koruması, domain, Stabil ve arşivli uçtan uca senaryolar dahil. Değişen yedi Python dosyasında Ruff, compile ve diff kontrolü temiz. Bütün repo testlerinin yeşil olduğu iddiası değildir.

**Commit/push/deploy yapılmadı.** Kullanıcıya çalışan botun değiştiği veya günlük 15 → 3–5 gözleminin nedeni bulunduğu söylenemez.

[Kanıt ve yeniden üretim](../arastirma/sonuclar/formation_trigger_2026_11_27/README.md)
