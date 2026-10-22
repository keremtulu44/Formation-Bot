# Grafik deneyimi ve bildirim zamanlaması denetimi

**Tarih:** 15 Ekim 2026  
**Kapsam:** Grafiklerin yerleşimi, görsel hiyerarşisi ve okunurluğu; 18:10 sonrası tarama, kapanış özeti ve ertelenmiş hisse bildirimleri.  
**Dış servisler:** Canlı Telegram, Yahoo/market verisi veya Render çağrısı yapılmadı. Yerel testler/örnekler kullanıldı. Renk paletine dokunulmadı.

## Kısa sonuç

- **18:10 tarama kapanışı değil.** Bu saat, günlük bakım işinin başlayabildiği aralık. Normal işlem gününde son planlı tarama 18:35’te; tarama penceresi 18:40’a kadar açık. Kapanış özeti hedefi 18:45.
- Özetten sonra hisse mesajı gelmesine yol açabilecek gerçek bir yol bulundu: günlük özetin önünde çalışan acil bildirim kuyruğu, ayrıca başlangıçta koşulsuz boşaltılıyordu. Kuyruk kaydı 180 dakika geçerli kaldığı için geçerli bir sinyal özetten sonra ayrı mesaj olarak gidebiliyordu.
- Grafiklerde renk değil **bilgi yoğunluğu ve lejant şeffaflığı** öne çıktı. Ayrıntılı görünümde örnek bir kare yedi lejant girdisini sığdıramadı; bu sayı daha önce yalnız metadata’da kalıyordu. Telegram altyazısına artık kısa bir uyarı ekleniyor ve `/grafik` için kullanıcı seçebilir `sade` görünüm açıldı.

## 1. Grafik akışı ve görsel bulgular

### Akış

Telegram’daki manuel `/grafik` isteği `_komut_grafik` üzerinden arka plan işine alınır; aynı `grafik_uret.kare_uret` ve `grafik.ciz` hattını kullanır. Var olan cache/bellek okunur, komut kendi başına canlı veri çekmez. Tek TF seçilirse tek kare, TF yazılmazsa o hisse için dört TF’lik albüm üretilir. Otomatik alarm görselleri bu manuel komuttan ayrı çalışır.

### Örneklerde görülenler

- Ayrıntılı kare; başlık/formasyon durumu, yapı işaretleri, OB/FVG bölgeleri, sağ fiyat etiketi rayı, hacim şeridi, alt lejant ve veri uyarılarını aynı görüntüde taşıyor. Bilgi miktarı yüksek; 180 mumluk mobil görünümde metin ve işaretlerin hepsini ilk bakışta okumak güç.
- Sağdaki fiyat rayı seviyelerin mumların üzerine yığılmasını azaltıyor; karşılığında ana çizim alanını daraltıyor. Bu, mevcut düzenin bilinçli bir takası. Renk veya ray ölçüsü gelişigüzel değiştirilmedi.
- Lejant en fazla iki satıra sığdırılıyor; gerektiğinde yazı 7 pt’ye kadar küçülüyor ve düşük öncelikli maddeler düşürülüyor. Kodda düşürülen adet `meta["lejant_atlanan"]` olarak tutuluyordu, fakat okuyucuya görünmüyordu.
- Yerel render doğrulamasında AKBNK 1s, 180 mum örneği ayrıntılı modda `lejant_atlanan=7`; sade modda `lejant_atlanan=0` verdi. Kullanılan cache’in son mumu 25 Eylül 2026 tarihli olduğundan bu yalnızca **yerleşim/render denemesidir**, güncel piyasa görünümü değildir.

### Uygulanan grafik değişikliği

`/grafik` artık görünüm seçimini kabul ediyor:

- `/grafik THYAO 4s sade` — tek TF’de mumlar, formasyon bandı ve kritik/son fiyatı öne çıkarır.
- `/grafik THYAO sade` — dört TF’yi sade görünümde dener.
- `/grafik THYAO 4s detay` — ayrıntılı görünümü açıkça seçer.

Mod yazılmazsa mevcut davranış korunur; varsa `GRAFIK_SADE` ortam ayarı varsayılanı belirler. Açıkça `sade` veya `detay` yazılması ortam ayarını geçersiz kılar. Sade modu altyazıda belirtilir. Lejant maddesi atlandıysa hem manuel kare altyazısı hem otomatik alarm karesi altyazısı `lejant kısaltıldı (+N)` uyarısını taşır. Böylece grafiğin içi yeni bir dipnotla daha da kalabalıklaştırılmadan bilgi kaybı görünür olur. **Palet değiştirilmedi.**

## 2. 18:10 sonrası çalışma ve bildirim zaman çizelgesi

| Saat/davranış | Koddan doğrulanan anlam |
|---|---|
| 18:10 | `evening_maintenance()` günlük bakım/status kontrolü için çalışabilir. Telegram günlük özeti oluşturmaz veya göndermez. |
| 18:35 | Normal günün son kapanış taraması: ilgili mum kapanışı + 5 dakika. Ana döngü tarama kapısı açıksa tüm evreni `send_alerts=True` ile tarar. |
| 18:40 | Normal gün tarama penceresinin sonu. 18:40’a kadar açık; 18:41 ve sonrasında kapalı. Dolayısıyla “18:10’dan sonra hiç tarama yok” yorumu doğru değil. |
| 18:45 | Günlük kapanış özeti ve izleme adayları hedefi. Aynı gün başarılı tam-evren tarama şartı sağlanmadıysa özet bekler ve şart sağlanınca aynı gün daha geç gönderilebilir. 18:45 kesin bir çalışma sonu değil, hedef saattir. |
| 20:00 (varsayılan) | Ayrı gün-sonu analiz taraması `send_alerts=False` ile çalışır; “GÜN SONU ANALİZİ” paneli gönderebilir, normal hisse alarmı üretmez. |

Son tarama zamanlaması `data.py`’deki mevcut yardımcılar üzerinden doğrulandı; bu yardımcıları değiştirmedim. `test_takvim_politikasi.py` ve `test_son_tarama_kaliciligi.py` bu turda da geçti.

## 3. Özetten sonra hisse bildiriminin kök nedeni ve düzeltme

### Kök neden

- Kota/cooldown nedeniyle gönderilemeyen teyitli alarmlar `notifier.py` içindeki kalıcı acil kuyruğa alınıyor; varsayılan TTL 180 dakika.
- Ana döngü kuyruk boşaltmasını kapanış özeti kontrolünden **önce** yapıyordu. Özet gönderildikten sonraki döngü de kuyruğu yeniden boşaltabildi.
- Başlangıçta da bekleyen kuyruk koşulsuz boşaltılıyordu. Bot özeti gönderdikten sonra yeniden başlatılırsa TTL içindeki eski alarm tek başına gelebiliyordu.

Bu, tarama saatinin 18:10’da kesilmesi değil; kuyruk teslim zamanlaması problemiydi.

### Uygulanan bildirim politikası

1. Acil kuyruk kapanış özeti saatinden **iki dakika önce** bireysel gönderim için kapanır; böylece yavaş Telegram/ağ kuyruğu özeti geç başlatmaz.
2. Kapanış özeti henüz gönderilmemişse taze ve geçerli bekleyen teyitli alarmlar DM özetine tarih/saatli bir bölüm olarak eklenir. Mum saati ile kuyruğa alınma saati ayrı gösterilir.
3. Özet Telegram tarafından başarıyla kabul edilirse bu kayıtlar kuyruktan tüketilir ve aynı formasyon/state’in tekrar ayrı acil mesaj olarak çıkmaması için tekrar mührü yazılır. Özet gönderimi başarısızsa kayıt tüketilmez; özet sonraki döngüde yeniden denenebilir.
4. Özet aynı gün daha önce gönderilmişse açılışta kalan kuyruk kayıtları ayrı geç mesaj olarak gönderilmez, temizlenir. Önceki İstanbul gününden kalan kayıtlar da TTL kullanıcı tarafından uzatılmış olsa bile bireysel push edilmez.
5. DM kuyruğu DM kapanış özetine eklenir; public kanalın ayrı olay/bülten yolu değiştirilmedi.
6. Telegram gönderimi ile yerel kuyruk/özet işaretlerinin yazılması tek atomik işlem değil. Süreç Telegram’ın kabulünden hemen sonra, yerel işaret yazılmadan kapanırsa restartta tekrar deneme ve dolayısıyla tekrar mesaj olasılığı tamamen kaldırılamaz. Normal döngüdeki tekrar yolu kapatıldı; Telegram API’si için burada **tam “exactly once” garantisi yoktur**.

Bu politika, kapanış özetinden sonra tek tek gecikmiş hisse mesajı gelmesini engeller. Özet tam-evren taraması tamamlanana kadar bekliyorsa kuyruk aynı gün özet için tutulur; Telegram gönderimi başarısızsa aynı gün yeniden denenir. Gün sonuna kadar başarılı tarama/özet oluşmazsa veya özet sonrası restartta önceki güne ait kayıt kalmışsa olay **geç bireysel push olarak gönderilmez** (önceki gün kuyruğu temizlenir). Böylece bayat alarm ertesi güne sarkmaz; bunun bedeli, tam günlük özet hiç üretilemeyen günde kuyruktaki olayın kullanıcıya teslim edilmeyebilmesidir.

## 4. Doğrulama

- Yerel görsel denemesi: aynı AKBNK 1s/180 mum cache’iyle detay ve sade PNG üretildi. Detay: 7 lejant girdisi gizli; sade: 0. Görseller `/tmp` altında tutuldu, repoya eklenmedi. Cache eskidir; finansal doğruluk iddiası değildir.
- Grafik, kuyruk, komut, kapanış özeti ve zamanlama odaklı pytest grubu: **221 geçti, 4 atlandı**.
- Tam test paketi: **1201 geçti, 55 atlandı** (`pytest.ini`’nin bilerek toplama dışında bıraktığı bağımsız scriptler dâhil değildir).
- Testler izole `DATA_DIR` ile çalıştı; canlı Telegram/Yahoo/Render çağrısı yapılmadı.

## Son değerlendirme

18:10 sonrası planlı tarama devam eder ve 18:35 son taraması korunur. Hisse bildirimlerinin özetten sonra tek tek görünmesine neden olan kalıcı kuyruk boşaltma yolu kapatıldı; geçerli, henüz raporlanmamış olaylar kapanış özetine alınır. Grafik tarafında ayrıntılı görünüm korunurken sade okuma modu erişilebilir hale geldi ve lejant budaması altyazıda artık gizli değil.
