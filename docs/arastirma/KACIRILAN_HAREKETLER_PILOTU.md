# Kaçırılan hareketlerin haritası: gerçek Replay pilotu ve sistem önerisi

**Durum:** Araştırma, canlı özellik değil. Bu rapor tarihsel hareketleri
başlangıç noktası yapar. Fiyat yükselişi ve düşüşü ayrı tutulur; bir grafik
üzerindeki geçmiş hareketin yakalanabilir kâr veya gönderilmiş Telegram mesajı
olduğunu iddia etmez.

## 1. Gerçek pilot: ne çalıştırıldı?

Yerel arşivden ASTOR, THYAO, AKBNK, GARAN ve TUPRS; her biri için 1d son 400
ve 1h son 800 ham mum. 1d ve 1h sonuçları karıştırılmadı. Bu beş hisse örneklem
olarak elle seçildi; 177 serilik arşiv tüm BIST değildir ve bu pilot evreni
istatistiksel olarak temsil etmez. Veri ve hash kayıtları çalışma çıktısındaki
`metadata.json` içindedir.

```bash
python scripts/kacirilan_hareket_pilotu.py
# var/kacirilan_pilot/windows.csv, summary.csv, metadata.json
```

Her seri ayrı taranır; en az 80 mum ısınmadan sonra **10 mumda bir** karar
penceresi açılır. Bir pencerenin sonuç mumları bir sonrakinin sonuç mumlarıyla
örtüşmez; farklı hisseler ise aynı piyasa döneminden ötürü bağımlıdır. Bu yöntem
örtüşen olayları çift saymamak için bir başlangıçtır, tüm büyük hareketleri
bulmaz: pencere hizasını 10 mum değiştirmek sonucu değiştirebilir.

Karar anı t'de bilinen son kapanış ve temiz veriyle yeniden tohumlanmış Wilder
ATR sabittir. Sonraki 10 tamamlanmış mumun kapanışlarından:

* **Korunmuş:** 10. kapanış − t kapanışı ≥ +2 ATR ise yukarı; ≤ −2 ATR ise aşağı.
* **Yol içi:** 10 kapanıştan herhangi biri aynı eşiği aşarsa ilgili yönde olay.
  Yol içi eşik geçilip 10. kapanışta korunmamışsa geri verilmiş olarak ayrılır.
  Bir pencere iki yönde de yol içi eşik görebilir. Mum içi high/low değil,
  kapanışlar kullanılır; 2 ATR/10 mum önerisel, nihai ve optimize edilmiş
  bir eşik değildir.

Her seri kronolojik %70 keşif / %30 ileri dönem olarak bölünür. Keşif kararından
ileri dönem sınırına taşan hedefler dışlanır; sonu eksik pencereler hiç pozitif
veya negatif sayılmaz. Bu sabit aralıklı deney bağımsız ileri test değildir.
Zaman etiketleri sağlayıcı bar etiketleridir: özellikle günlük `00:00` piyasanın
kapanış saati değildir. Geçmiş seans takvimi, boş mumların eksiksizliği,
kurumsal işlemler ve fiyatların düzeltilmişlik politikası bağımsız
kanıtlanmadığından sonuçlar doğrulanmış canlı performans değildir.

**Karar anındaki gözlemsel üç yapı:**

1. `pattern_active`: yalnız o kapanışta izole Argent Replay'de aktif formasyon
   var mı? Bu yönden bağımsız bir yapı, yönlü alarm değildir.
2. `pattern_recent10`: t dahil son 10 mumda en az bir aktif formasyon var mı?
   Bu daha gevşek alternatif çok sayıda kontrol penceresinde de görülür.
3. `ob_up` / `ob_down`: o anda zaten oluşmuş ve bitmemiş, ilgili yöndeki OB'nin
   **orijinal** fiyat bölgesine kapanış en çok 1 ATR uzaklıkta mı? Bütün OB/FVG
   veya canlı motor kararları bununla temsil edilmez. `break_up/down` da aktif
   yapı içindeki ilgili yönlü kırılım durumunu ayrı ölçer.

Bunlar salt Replay durumlarıdır; canlı sistemin bir hareketi değerlendirip
filtrelediğine, mesaj ürettiğine veya Telegram'ın teslim ettiğine kanıt değildir.
Aynı koşul büyük hareket olmayan **kontrol pencerelerinde** de sayılır; bu
kontrol eşleştirmesi henüz volatilite/rejim/sektörle dengelenmiş değildir.

## 2. Pilot sayıları — keşif ve ileri dönem ayrı

Beş hissede geçerli 1d: keşif 100, ileri 55; 1h: keşif 240, ileri 115 pencere.
Aşağıda olay sayısı iki sütunda, yapı örneği olarak `pattern_active` için
`olayda aktif / tüm olaylar` ve `kontrolde aktif / tüm kontroller` verilmiştir.
Bunlar kazanç, teslim veya güvenilirlik yüzdesi değildir.

| Dönem | TF | Tanım | Yön | Olayda aktif | Kontrolde aktif |
|---|---|---|---|---:|---:|
| Keşif | 1d | 10. kapanış | Yukarı | 15 / 27 | 29 / 73 |
| Keşif | 1d | 10. kapanış | Aşağı | 9 / 16 | 35 / 84 |
| Keşif | 1h | 10. kapanış | Yukarı | 16 / 43 | 62 / 197 |
| Keşif | 1h | 10. kapanış | Aşağı | 9 / 33 | 69 / 207 |
| İleri | 1d | 10. kapanış | Yukarı | 3 / 9 | 23 / 46 |
| İleri | 1d | 10. kapanış | Aşağı | 7 / 11 | 19 / 44 |
| İleri | 1h | 10. kapanış | Yukarı | 2 / 12 | 46 / 103 |
| İleri | 1h | 10. kapanış | Aşağı | 18 / 32 | 30 / 83 |
| İleri | 1d | Yol içi kapanış | Yukarı | 4 / 12 | 22 / 43 |
| İleri | 1d | Yol içi kapanış | Aşağı | 11 / 19 | 15 / 36 |
| İleri | 1h | Yol içi kapanış | Yukarı | 6 / 18 | 42 / 97 |
| İleri | 1h | Yol içi kapanış | Aşağı | 23 / 45 | 25 / 70 |

İleri dönemde yol içi eşiği geçip 10. kapanışta korumayan pencere sayıları:
1d yukarı 3, aşağı 8; 1h yukarı 6, aşağı 13. Her iki yönde yol içi eşik gören
1d 1, 1h 2 pencere var; yukarı ve aşağı toplamları dolayısıyla birbirini
dışlamaz. Örneğin gerçek arşivde ASTOR 1d `2026-05-26` etiketli başlangıçta
yukarı yol içi eşik geçilmiş fakat 10. kapanışta korunmamış; o ankarda aktif
formasyon ve yakın yönlü OB yok. Bu, kaçırılmış gerçek bildirim veya işlem
ispatı değildir; fiyat penceresi ve as-of yapı yokluğu gözlemidir.

Aynı ileri dönem 1h aşağı, korunmuş 32 pencerenin 2'sinde yakın aşağı OB vardı;
83 kontrolün 21'inde de yakın aşağı OB vardı. Alternatif olarak son 10 mumda
herhangi bir aktif formasyon 32 olayın 24'ünde, 83 kontrolün 41'inde vardı. Bu
küçük ve bağımlı örnekte daha geniş zaman penceresi kapsama ile birlikte kontrol
sıklığını da artırıyor. Eşik seçimi ve çoklu karşılaştırmaların etkileri
hesaplanmadığı için hangisinin "daha iyi" olduğunu söylemek erken. Diğer tüm
yön/tanım/yapı hücreleri ve örnek pencereler yeniden üretilebilir CSV'dedir.

## 3. Gerçekten neyin kaçırıldığını ayıracak sistem şeması

```text
Ham arşiv + kaynak/zaman/kalite manifesti
  → bar kapanış/işlem takvimi + düzeltme + corporate-action kontrolü
  → hareket adayı [TF × yön × ölçü × ATR] + sağ sansür
  → aynı hareket için epizot birleştirme ve embargo
  → t öncesi verilerle Replay (bar ve ara durum, sürüm sabit)
  → tespit → değerlendirme → filtre kararı → bildirim isteği → teslim kanıtı
  → olay ve eşleştirilmiş controls / dönem / yön bazlı karşılaştırma
  → ayrı holdout, çoklu-test ve bağımlılık düzeltmesi, ileri paper gözlem
  → araştırma raporu; başarılı olursa ayrıca onaylı ürün tasarımı
```

Önerilen kanıt sınıfları (her biri zaman damgası ve sürümle):

* **Saptanmadı:** Güvenilir girdi ve tam Replay varken ilgili yapı motorunda aday
  üretilmedi. Yalnız tanımlı aday sınıfı için geçerlidir.
* **Saptandı/değerlendirildi:** Aday kimliği, özellikleri, oluşum zamanı, yönü,
  veri kesiti ve hesaplanan kriterler mevcut; gönderi anlamına gelmez.
* **Filtrelendi:** Filtre ismi, sürümü, eşik ve açık gerekçesi biliniyor.
* **Bildirim istendi:** Kalıcı outbox/olay kimliği ve karar zamanı mevcut.
* **Fiilen teslim edildi:** Telegram/transport sonucu güvenilir kayıtla eşleşmiş.
* **UNKNOWN:** Kayıt, veri, seans, sürüm, filtre veya teslim kanıtı eksik;
  geçmişteki yokluk `gönderilmedi` diye doldurulmaz.

Bu pilot yalnız ilk iki katmanın yaklaşık yapı durumunu inceler; geçmiş gerçek
filtre/ileti/teslim kayıtlarıyla birleştirme yapılmadı. Yönlü OB ve formasyonlar
botun tüm analizleri değildir. Bir kararın sonuç penceresinden sonraki durumunu
tespit gibi yazmak geleceğe bakmadır. Üretim kodunda gözlemlenebilirlik
artırmak için şimdilik değişiklik yapılmadı.

## 4. Alternatif deneyler ve karar ölçütleri

1. **Epizot-öncelikli tarama:** Her mumda ±1.5/2/3 ATR eşiği ve 5/10/20 ufuk;
   eşikleri önceden dondur, kesişen ilk-geçiş pencerelerini yön ve TF bazında
   kümelendir. Tek büyük trendi onlarca olay sayma. Sabit-10 pilotunu başlangıç
   ofsetleri 0–9 ile tekrarla ve oynaklığı raporla.
2. **Kapanış / yol içi / geri verme:** kapanış bazlı etiket yanında, OHLC
   high-low dokunuşunu ayrı tut. Aynı mumda hem yukarı hem aşağı eşik olursa
   sıralama bilinmez; lower-TF gerçek veri yoksa UNKNOWN. İlk dokunuşun anı ve
   geri verme ayrı olay özellikleri; hiçbirini fiili kâr sayma.
3. **Olay öncesi katmanlı iz:** ör. −20…−1 mumda yönlü OB/FVG yakınlığı,
   olgunluk ve kırılım, hacim, oynaklık ve piyasa bağlamını bar-kapanışında
   çek. Sonraki bilgilerden boyut seçme veya geçmişe düzeltilmiş sınır yazma.
   İlk görünme ile olay başlangıcı arasında kaç mum olduğu, çok erken/geç ve
   hangi katmanda kaybolduğu ölçülebilir.
4. **Gerçek kontrol grubu:** aynı hisse/TF, geçmiş volatilite, zaman ve sektör
   bakımından benzer, tanımlı ufukta büyük hareket olmayan pencereler. Aynı
   epizottan veya holdout'tan keşif kontrolü seçme. Olay kapsaması yanında
   kontrol sıklığı, hassasiyet, alarm/hisse/gün, gecikme ve sansür oranını ver.
5. **Bağımlılık ve seçim:** tarihsel rejimlere göre blok bootstrap/güven aralığı,
   hisse/sektör kümelenmesi ve çoklu test düzeltmesi uygula. Keşifte seçilen
   eşikler ve kuralları değişmeden ileri dönemde ölç; yeterli örnek yoksa UNKNOWN.
   Kapanış kanıtı olmayan makro değişkenleri özellikle dışarıda bırak.
6. **Yöntem karşılaştırmaları:** mevcut formasyon-only, sadece OB/FVG, birlikte
   VE/VEYA, volatilite sıkışması/genişlemesi, göreli hacim ve piyasa göreli güç
   özelliklerini ayrı ayrı; her biri için aynı negatif kontrollerle karşılaştır.
   Tahmini açıklama ile ileriye dönük tahmin başarısını karıştırma. İlk pilot
   yalnız aktif yapı/yakın OB ve kırılım proxy'lerini karşılaştırdı.
7. **Sonraki aşama:** tarihsel günlük kayıtların imkânı araştırılır; kayıtlar
   yoksa başlayacak bir gölge koşuda sürüm, veri kesiti, tüm filtre nedenleri,
   outbox ve teslim sonucu toplanır. Canlı alarm kuralı değiştirilmeden önce
   maliyet/slippage ve kullanıcıya sunulacak uyarı yükü ayrıca değerlendirilir.

Veri düzeltmesi, şirket işlemi ve seans takvimleri doğrulanmadan "kaçırılanların
x% kadarı kurtarılır" veya otomatik yeni alarm sözü verilemez.
