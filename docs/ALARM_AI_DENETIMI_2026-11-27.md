# Alarm ve AI denetimi — 27 Kasım 2026

## Kapsam ve kanıt sınırı

Klasik formasyon taraması → kalite/kapanış kapıları → DM/public tekilleştirme → AI → teslim akışı incelendi. Stabil ve yeni domain tekil kartlarının ortak AI yolu da kontrol edildi. Supabase'de yalnız SELECT sorguları çalıştırıldı; canlı ayar veya veri değiştirilmedi. Değişiklikler çalışma dalındadır, canlıya dağıtım yapılmadı.

- `ai_yorum_test` tablosunda 27 Kasım için iki alarm örneği var: 132 ve 137 kelime (yaklaşık 1.050 karakter). Tek manuel örnek de 137 kelime. Örnek sayısı toplam alarm hacmini veya teslim başarısını ölçmeye yetmez.
- `bot_store` içindeki heartbeat/tarama/cache kayıtları 30 Ekim'de kalmış. Bu veriler bugünkü sürecin güncel durumunu göstermez; tek başına botun durduğunu da kanıtlamaz. AI kayıtlarının daha güncel olması ayrı yazım yollarının incelenmesini gerektirir.
- İlk incelemede AI gölge kaydındaki `telegrama_gitti`, hazırlık anındaki gönderim niyetinden besleniyordu. Sonraki temizlikte bu yanlış pozitif kaldırıldı: hazırlık kaydı `false` ve `baglam_ozet.teslim_durumu=dogrulanmadi` taşır. Bu alan artık hazırlık aşamasında gerçek teslim iddiasında bulunmaz; gerçek teslim defteri ve gönderim sayaçları esas alınır. Eski kayıtlar değiştirilmedi; teslim sonrasında gölge kaydını güncelleyen yeni bir entegrasyon bu çalışmaya dahil değildir.

## Düzeltilenler

### 1. Alarm için ayrı kısa AI profili

**Kök neden:** Manuel analiz ile canlı alarm aynı 120–180 kelimelik talimatı kullanıyordu. Uzunluk uyarısı Telegram yayınına engel değildi.

**Yeni davranış:**

- Klasik, Stabil ve domain tekil AI alarmları: 50–80 kelime hedefi, görünür yorum gövdesinde 100 kelime katı üst sınırı. Tekrar eden TF/bölge listeleri istenmez.
- Kullanıcı onayıyla Telegram sunumu iki bölüme indirildi: **Görünüm** (yön + ana gerekçe + karşı kanıt) ve **İzlenecek bölgeler** (görüşü değiştirecek kapanış koşulu + en fazla iki bölgenin durumu). İç model/denetim/gölge sözleşmesi üç başlıklı kalır; sunum dönüşümü hiçbir cümleyi kesmez veya yeni finansal yorum eklemez.
- Alarm başlığındaki `1s/2s/4s/1g` yerine `1 saat/2 saat/4 saat/Günlük` gösterilir. Kapanış fiyatı ve mevcut mum zaman bilgisi korunur. DM ve public mesajları yeni iki bölümlü metni tablo gibi sarmalamadan gösterir.
- Manuel `/ai` ve varsayılan API promptu: mevcut uzun analiz biçimi korunur.
- Gizli `AI_SONUC` bloğu kelime sınırına dahil değildir, kullanıcıya sızmaz.
- Sınır aşılırsa finansal koşullar cümle ortasında kesilmez. AI metni kullanılmaz, mevcut normal teknik kart gönderilir; alarm iptal edilmez. Ek AI yeniden denemesi eklenmedi.
- Prompt profili metadata'ya, gölge doğrulamaya ve istemci ayrıştırmasına aynı şekilde taşınır.
- Gerçek alarmın türü, state'i, yönü, deseni ve varsa açılış/kapanış zamanı `<tetikleyici>` bölümüne aktarılır. Önceden alarm çağrısı bu bölümü doldurmuyordu.

### 2. TF'ler arası yanlış olay sıralaması

**Kök neden:** Hikâye tekilleştirme kapısı önce `bar_time` (açılış) alanını okuyordu. Örneğin 13:30–17:30 4H retesti, 15:30–16:30 1H teyidinden önce açıldığı için eski olay kabul edilebiliyordu. Oysa retest daha sonra bilinir.

**Yeni davranış:**

- Önce `bar_kapanis` karşılaştırılır; yok/geçersizse eski kayıtlarla uyum için açılış/zaman alanları yedektir.
- Eşit kapanış zamanındaki teyit → retest ilerlemesine izin verilir. Gerçekten eski olaylar, aynı aşamanın tekrarı ve geri aşama engellenmeye devam eder.
- Public geçmişine kapanış zamanı da kaydedilir; restart sonrası korunur.
- Zamanlar gün karşılaştırmasından önce İstanbul saatine çevrilir.
- Mevcut kalite, kapanmış mum, geçersizleşme, aynı-gün hikâye ve kota politikaları gevşetilmedi. Eski public kayıtlara bilinmeyen kapanış zamanı uydurulmadı.

### 3. Boş paragrafla denetimden kaçış

**Kök neden:** Yorum doğrulayıcı metni çift satır sonundan bölüp ilk üç parçayı bölüm sanıyordu. Bölüm içi boş paragraflar, sonraki kelimelerin ve yasak içeriklerin taranmamasına neden olabiliyordu.

**Düzeltme:** Doğrulama gerçek başlıkları izleyerek bütün gövdeyi sayar ve tarar. Bu düzeltme hem manuel hem alarm yorumlarını kapsar.

## Alarm sayısını bilinçli azaltan mevcut kurallar

Bu kurallar hata diye kaldırılmadı:

| Kapı | Mevcut politika |
| --- | --- |
| Anlık state'ler | `KIRILIM_TEYITLI`, `RETEST_BASARILI`, `KIRILIM_GECERSIZLESTI` |
| İzleme | `SIKISMA_GUCLENIYOR` kapanış özetine ertelenir |
| Diğer hazırlık/adayı state'ler | Anlık alarm değildir |
| Kalite | 1H ≥80, 2H ≥78, 4H ≥75, 1D ≥70; geçersizleşme istisnası korunur |
| Mum | Kapanmış mum ve kırılım seviyesi teyidi gerekir |
| Hikâye | Aynı hisse/yön/aşama aynı gün TF ve desen farklı olsa bile tekrar sayılır |
| Tekrar ve soğuma | Formasyon mühürleri, TF birleştirme ve 4 saatlik DM soğuması ayrıca uygulanır |
| Yeni motorlar | Stabil/domain alarm şalterleri ve kendi aday/soğuma kuralları ayrıdır |

Dolayısıyla panelde çok formasyon görünmesi, aynı sayıda anlık alarm beklemek anlamına gelmez. Kalite eşiklerini düşürmenin etkisi ölçülmeden eşik değişikliği yapılmadı.

## Canlıda izlenecekler

1. Dağıtım sonrasında güncel `/durum` ve `/health` çıktısından aday hunisi, eşik altı, state dışı, tekrar/soğuma/kota, veri tazeliği ve teslim kuyruğu sayaçlarını karşılaştır.
2. Supabase heartbeat'in neden eski kaldığını güncel süreç ayarları ve yazım modu üzerinden doğrula. Eski heartbeat'i bugünkü alarm hacmiyle eşleştirme.
3. AI senkron çalışıyor; `AI_YORUM_MAX_BEKLEME_SN=0` varsayılanı sağlayıcı başına toplam süre sınırı koymuyor. SSE beklemeleri taramayı uzatabilir. Bu bir kod riski, bugünkü hacim kaybının ölçülmüş nedeni değil. Sözleşme/varsayılan değiştirilmedi; ihtiyaçta pozitif süre sınırı operasyon ayarıyla değerlendirilmeli.
4. Kısa profilin `cok_uzun` nedeniyle normal karta düşme sıklığını izle. AI bozulduğunda alarmın normal kartla devam ettiğini kontrol et.

## Doğrulama

- Alarm/AI, DM/public teslim, tekrar, kalite/kapanış, Stabil/domain entegrasyonu: **393 passed**.
- Ek veri akışı, takvim, tarama, prompt ve regresyon grubu: **238 passed, 32 skipped**. Bazı ortak regresyonlar iki koşuda da çalıştırıldı; sayılar benzersiz test toplamı değildir.
- Depo genelinde `ruff check .` ve `git diff --check`: temiz.
- Yeni regresyonlar: `test_alarm_length_and_event_time.py`. Uzun AI entegrasyon örneği limit/manuel testi için korunup alarm başarı örneği kısa profile uyarlandı.
- Toplam 5.170 test toplanabildi; bütün depo testlerinin tamamı çalıştırılmış değildir. Testlerde gerçek AI/Telegram ağı kullanılmadı.

## Sonraki genel temizlik — kullanıcı onayıyla

Bu turda AI–alarm–manuel komut–gölge kayıt zincirindeki küçük/orta sorunlara odaklanıldı; formasyon motoru veya alarm eşikleri yeniden tasarlanmadı.

1. **Tek yorum üretim/doğrulama yolu:** Canlı çerçeve ve yerel JSON önbellek artık aynı packet → prompt → sağlayıcı → doğrulama yolunu kullanır. Yerel `/ai` artık güvenlik uyarısı almış bir yanıtı yalnız metni var diye göstermez; iki yol da reddeder. Prompt veya istemci hataları manuel komutu kontrolsüz istisnayla düşürmez.
2. **Ayrı, açık alarm talimatı:** Uzun analizdeki belirli bir cümleyi `replace` ile değiştiren kırılgan bağlantı kaldırıldı. Alarmın çıktı kuralları `ai_prompt/talimat_api_alarm.txt` içindedir; ortak doğruluk/veri sınırı kuralları değişmedi.
3. **Veri silmeden kısa etiketler:** Alarm promptunda dış yapı/hacim durum etiketleri kompakt yazılır. Bölge sınırları, karşı yönlü kanıtlar, temas geçmişi, TF'ler, veri hazır-değil notları, KAP içeriği ve araştırma tarih sınırları korunur. Manuel paket ayrıntısı değişmez. Normal ve alarm veri metni arasındaki farkın yalnız bu etiketler olduğunu doğrulayan regresyon vardır.
4. **Gizli blok temizliği:** Kapanış parantezi eksik `AI_SONUC` ve kod çiti içindeki yarım bloklar kullanıcı metninden temizlenir. Birden fazla düz/çitli blokta kaynak metindeki son blok kullanılır. Yinelenen/çelişen alanlar, alias ile yazılsa bile geçerli ölçüm kararı sayılmaz. Güvenli görünür yorum, yalnız gizli ölçüm hatalı diye kaybedilmez.
5. **Kesilmeyen finansal koşullar:** Alarm ve manuel mesaj sınırları UTF-16 ile ölçülür. Fazla uzun metin cümle/koşul ortasında kesilmez; alarm normal karta döner, manuel analiz açık hata mesajı verir. Sonsuz, NaN, negatif veya boolean kapanış değerleri fiyat gibi basılmaz.
6. **Gölge defterinin veri bütünlüğü:** Thread kilidi + eşsiz geçici dosya + fsync/atomik replace kullanılır. Eşzamanlı komutlar birbirinin kayıtlarını ezmez. Okunamayan/bozuk geçmiş sıfırlanmaz; dosya korunur. Yerel hata, açıkça yapılandırılmış uzak kaydın ayrıca denenmesini engellemez. Kilit tek süreç içindir; çok süreçli paylaşımlı dosya kullanımı için süreçler arası kilit sağlamaz.
7. **Doğru ölçüm kimliği:** Prompt sürümü doğru `prompt_version` alanından alınır. Aynı sembol/TF/kesit/modelde kısa alarm kaydı ile uzun manuel kayıt farklı anahtar kullanır; birbirini ezmez. Standart/eski anahtarlar korunur.

### Ölçüm ve kapsam sınırı

- Önceki dört tarihsel örnek aynı koşullarla tekrar ölçüldü (BIMAS/ALARK/THYAO/TAVHL, 25 Eylül kesiti, KAP eklenmeden, 1H alarm profili). Ortalama talimat **2.786**, veri **3.071**, toplam **5.858 karakter**. Önceki toplam 5.892 idi. Bu, büyük bir token tasarrufu iddiası değildir; önemli verileri silmeden bakım ve güvenilirlik iyileştirmesidir.
- Yeni regresyon dosyası: `test_ai_cleanup_regressions.py` (**30 vaka**).
- Geniş seçilmiş koşu: tüm AI testleri; alarm uzunluğu; DM/public teslim ve politika; Stabil/domain alarm; komutlar; kalıcılık; tekrar/kayıp bildirim; deploy kontrolleri: **763 passed, 1 skipped**.
- `ruff check .` ve `git diff --check`: temiz. Tüm depo testleri çalıştırıldığı iddia edilmiyor; canlı sağlayıcı/Telegram veya üretim veritabanında değişiklik yapılmadı. Dağıtım yapılmadı.
