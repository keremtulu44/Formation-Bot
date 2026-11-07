# Stabil ve Stabil direnç — genel sorun/bug kontrolü

**Tarih:** 2026-11-07 · **Branch:** `arena/31e6116e-formation-bot` · **Durum:** Yerel statik inceleme + test; canlıya gönderim/deploy yapılmadı.

## Kısa sonuç

Stabil, bu branch'te yalnızca eski bir not veya deneysel TXT değil: günlük destek yaşam döngüsü ile haftalık/günlük/4s trend bağlamı için native Python runtime mevcut. Yeni direnç ise günlük Stabil desteğinin yönce yansıtılmış ayrı bir çizgi/yaşam döngüsü hesabı; mevcut `/grafik` ve mevcut alarm grafiklerine bağlanmış. Tasarım gereği **direnç kendi başına otomatik alarm üretmiyor**. Bu nedenle “kod ve yerel grafik yolu çalışıyor” sonucu, “canlıda her kullanıcıya görünecek / direnç sinyali gelecek” anlamına gelmiyor.

Bu kontrolde direnç odaklı **135 test**, tam depoda **4.131 test geçti, 43 test atlandı**; Ruff ve `git diff --check` geçti. Çalışma Python 3.11.2 yerel ortamında ve sahte/yerel taşıma ile yapıldı. Kod tarafında bu incelemede yeniden üretilebilen bir başarısızlık bulamadım. Bununla birlikte gerçek Render ayarları, güncel sağlayıcı verisi, gerçek Telegram teslimi/izinleri ve Python 3.12 CI bu kontrolde doğrulanmadı.

## Stabil nasıl çalışıyor?

### Destek ve trend: ayrı anlamlar

- `domain_engines/05_stabil.txt` özgün matematik kaynağı; uygulama `domain_engines/stabil/` altında. `domain_engines/runner.py` ve `bot/scan.py` sonuçları normal domain hattına taşır.
- Destek, günlük pivot ve yaşam döngüsü üzerinden oluşur: teyit/erişilebilirlik zamanı, seviye ve ATR tavanı, test/tutunma/ihlal/geri alım/yeniden seviyelenme gibi durumlar üretilir. Haftalık trend, günlük trend, 4s toparlanma ile günlük destek aynı şey değildir; destek üstünde olmak tek başına yükseliş/alım sinyali değildir.
- Grafik katmanı, günlük seviye bilgisini yalnız o mumun kapanışında bilinebilen haliyle 1s/2s/4s/günlük kareye taşır. Native pivotun oluştuğu tarih ile teyit edilip kullanılabilir olduğu tarih farklıdır. Gelecek pivotu geçmişe çizmemek ve kapanmamış mumdan karar almamak ana güvenlik şartlarıdır.

### Direnç: destek çekirdeğinin bağımsız ters yönlü eşi

- `domain_engines/stabil/resistance.py` fiyat OHLC'sini işaretçe yansıtarak native destek yaşam döngüsünü kullanır; dışarıya pozitif gerçek fiyatla direnç, tavan, oluşma/teyit/bilinirlik zamanları ve terslenmiş yaşam döngüsü çıkarır.
- 4s/2s/1s grafik hedef barları, yalnız tamamlanmış hedef mumlar ve doğrulanmış native günlük + saatlik kaynaklar üzerinden değerlendirilir. `chart_bridge.py` kaynak uyuşmazlığında veya veri eksiğinde çizgiyi uydurmak yerine direnç katmanını kapatır.
- Tepki oku ve momentum oku farklıdır. Dolu kırmızı `▼` aşağı dönüş; boş kırmızı `▽` aşağı momentum; boş yeşil `△` aday yapısal/yukarı deneme uyarısıdır. Sonuncusu düşüş tahmini değildir. Üç barlık momentum tekrarı bir tekrar kısıtıdır; pivot teyidinden sonra ek 2/3/5 mum beklemesi değildir.
- Grafiklerde direnç kesikli, destek düz çizgidir. Direnç rengi günlük snapshot rolünden gelir; 4s kapanışın çizgiyi aşması rengi hemen değiştirmeyebilir.
- Araştırma replay'i yatırım sonucu veya canlı alarm başarı oranı ölçmüyor. 50 hisselik direnç/destek karşılaştırması daha önce incelenmiş, eski örneklemden türemiş ve kör holdout değil. “Görsel dikey/yatay” eşleşmesi de doğrulanmış native rejim değildir.

## Bulgular ve riskler

### 1. [Orta] README'de Stabil'in mevcut durumu yanlış/eski anlatılıyor

`README.md` 37–42. satırlar runtime entegrasyonunun ve replay raporlarının checkout'ta bulunmadığını söylüyordu. Aynı branch'te runtime, direnç motoru, grafik köprüsü, replay ve ilgili testler mevcut; `STABIL_REHBERI.md` de 2026-11-04 checkout'ta runtime bulunduğunu açıklıyor. `docs/README.md` 37. satırda rehberi “Yürürlükte” sayarken entegrasyonun “şu an eksik” olduğunu yazıyor. Bu, araştırma durumu ile canlıya alma kanıtını birbirine karıştırıyor ve yeni inceleyeni yanlış yönlendiriyor.

**Öneri:** README'lerde runtime/yerel bağlantı durumunu ve canlı teslimin doğrulanmadığını ayrı cümlelerde tutmak; tarihsel eksik listesini yalnız 2026-11-01 snapshot'ı olarak etiketlemek. Bu turda üst seviye README ve belge haritası güncellendi; tarihsel kayıtlar silinmedi.

### 2. [Yüksek – canlı görünürlük] Otomatik alarm grafiği varsayılan olarak kapalı

`config.py` ve `.env.example`'da `TELEGRAM_GRAFIK` varsayılanı `yok`; `render.yaml` da örnek ayarda kapalı. Direnç otomatikte yalnız mevcut bir alarmın grafik hazırlanması halinde görülebilir. `/grafik` komutu bu şalterden bağımsızdır. Gerçek Render Dashboard değeri bu depodan bilinemez.

**Etkisi:** Kullanıcı canlıda Stabil direnç grafiğini bekleyebilir ama otomatik alarmlarda hiç grafik gelmeyebilir. Bu kod hatası değil, aktivasyon/konfigürasyon kapısıdır. Gerçek Dashboard doğrulanmadan canlı için “açık” denmemeli.

**Kullanıcının son `/grafik` gözlemiyle ilgili ek inceleme:** Manuel grafik üretimi direnç için native günlük kaynak ve özgün 1s kaynağı ister (`grafik_uret.py::_direnc_kaynaklari`). Tek bir intraday TF istendiğinde `/grafik` yenileme yolu yalnız o grafiğin baz kaynağını (1s) tazeler; ayrı günlük kaynak yoksa köprü `missing_source` ile kapatır. Varsayılan dört-TF isteğinde 1g yenilemesi TF sırasının sonunda yapılır; dolayısıyla önceki intraday kareler o istek içinde günlük veri henüz yokken hazırlanabilir. Bu, “Stabil direnç gösterilemedi” uyarısını açıklayabilecek somut bir akış riski. Kullanıcının hisse sembolü ve uyarıdaki iki nokta sonrasındaki tam neden olmadan, iki denemenin kesin kök nedeni olduğu söylenemez. Eğer tüm dört karede aynı uyarı varsa günlük kaynak ya hiç yüklenmemiş/yenilenememiş ya da köprü tarafından kalite/kapanış kontrolünde reddedilmiş olabilir.

### 3. [Orta – kanal farkı] Stabil geri-alım alarmında DM metin alıyor, public grafik de alıyor

`bot/stabil_service.py` Stabil geri-alımında public grafik çifti hazırlıyor; 7 Kasım gerçek arşivli ama sahte taşımalı E2E denetiminde DM yalnız metin, public ise 4s + varsa günlük grafik aldı. Normal formasyon/domain yollarında DM grafiği ayrı hazırlanabiliyor.

**Etkisi:** Kullanıcı alarmı DM'de izlerken direnç çizgisini görmüyorsa, bu direncin hesaplanmadığı anlamına gelmeyebilir. Bu davranış mevcut teslim sözleşmesiyle tutarlı, fakat test beklentisini şaşırtabilir. DM'ye Stabil grafiği eklemek ayrı ürün/teslim kararıdır; bu denetimde değiştirilmedi.

### 4. [Orta – anlaşılabilirlik] `READY` olmak grafikte görünür olmayı garanti etmiyor

Gerçek arşivli AKBNK örneğinde direnç `READY` olmasına rağmen 1s grafiğin fiyat aralığının dışında kaldığı için çizgi ve fiyat çipi görünmüyor. Otomatik altyazı her zaman “kadraj dışında” demiyor. `sade` görünüm her iki Stabil çizgisini kasıtlı gizliyor; günlük kaynak/kova doğrulanmazsa güvenli şekilde çizgi bastırılıyor. Otomatik mesajda kaynak hata nedeni her zaman kullanıcıya açık metin olarak aktarılmıyor.

**Etkisi:** “Direnç yok” ile “hesaplandı ama kadraj dışında / görünümde gizli / güvenlikte bastırıldı” kullanıcı açısından aynı boşluk gibi görünebilir.

**Öneri:** Gelecekte görsel metadata/altyazıda `READY + kadraj dışı`, `sade görünüm`, `kaynak eksik/kalitesiz` durumlarını birbirinden ayıran kısa açıklama sunmak. Mevcut çizgi ve alarm davranışına dokunulmadı.

### 5. [Orta – mevcut destek tutarlılığı] Stabil geri-alımında günlük destek karesi önbelleğe bağlı

7 Kasım teslim denetiminde, Stabil adayları önceden hesaplanmış domain sonuçları yokken izole 4s destek hesabından geldiğinde, public günlük grafikte günlük **direnç** hazır/çizili olduğu halde günlük **destek** çizgisi yoktu. Günlük destek sonucu önceden cache'e konmuş başka senaryoda çizildi.

**Etkisi:** Aynı alarmın public 4s ve günlük kareleri destek katmanı bakımından tutarsız görünebilir. Rapora göre bu direnç değişikliğinden önceki mevcut cache/akış tercihidir; destek motoru veya mesajı değiştirilmedi. Bunu kesin hata diye değil, ayrıca ele alınması gereken akış tutarlılığı olarak sınıflandırıyorum.

**Öneri:** Stabil public karelerinin destek ve direnci aynı sembol/zaman kesiti için aynı birleştirilmiş domain sonuçlarından üretmesini garanti eden hedefli test/bağlantı düzenlemesi.

### 6. [Yüksek – doğrulama sınırı] Yerel test geçişi canlı hizmeti doğrulamaz

15 senaryolu teslim E2E, gerçek arşiv, motor, PNG ve notifier/kuyruk kodunu kullanmış; Telegram taşıması/hedefleri sahte. Test geçmiş kapanış saatini, cache tazeliğini kontrollü biçimde sabitlemiş. Gerçek bot izni, grup yöneticiliği, Render `TELEGRAM_GRAFIK`, güncel veri, rate-limit, medya taşıması ve deploy edilen commit doğrulanmış değil.

**Etkisi:** Yerel grafik/test başarısından Telegram'da teslim garantisi çıkmaz. Özellikle belirsiz medya sonucunda çift görseli önlemek için otomatik tekrar yapılmaması mümkündür; gerçek operatör teslim/health kontrolü gerekir.

### Kullanıcının paylaştığı 7 Kasım canlı `/grafik` çıktısı

- `XAGUSD`: `unsupported_session` sonucu bu yapılandırmada beklenen davranış. `config.py` XAGUSD'yi makro sembol olarak sınıflandırıyor; direnç köprüsü XIST/BIST seans takvimi olmayan sembolü bilerek reddediyor. Gümüşte direnç istenirse ayrı piyasa takvimi/kapanış sözleşmesi gerekir.
- `GARAN`: 2026-11-06, yerel XIST takviminde **işlem günü**. `daily_on_closed_session` son 6 Kasım mumunun kapalı gün sayıldığını değil, 108 günlük kaynakta başka bir kapalı/hafta sonu tarihine etiketlenmiş mumu gösteriyordu. Aynı uyarının THYAO'da da çıkması ortak veri sağlayıcı/cache artifaktını kuvvetlendirdi. Direnç köprüsü şimdi takvimce kesin kapalı olan BIST tarihli günlük sentetik satırları yalnız direnç hesabı için dışarıda bırakıp tarihleri logluyor; takvim bilinmiyorsa veya gerçek işlem seansı eksik kalıyorsa fail-closed sürüyor. Böylece tek bir tatil satırı çizgiyi gereksiz yere tamamen kapatmamalı; fakat canlı cache'te başka kalite sorunu varsa direnç yine bastırılabilir.
- `/grafik hazır · 4 kare` mesajı PNG'lerin üretildiğini bildirir; her overlay'in hazır veya çizilmiş olduğunu garanti etmez. Bu iki komutun çıktısında da direnç alarmı tetiklenmedi; bunlar manuel grafik istekleridir.

**Canlı sınırı:** Düzeltme bu branch'te; Render/Telegram'daki sürüme dağıtılmadı. Canlı cache'e erişim olmadığı için hangi tarih satırının bu çıktıyı ürettiği ayrı doğrulanamadı. Bilinen kapalı gün satırlarını atlamak izole tatil artifaktını ele alır; eksik gerçek işlem günleri, saatlik kaynak uyuşmazlığı veya başka kalite kapıları hâlâ direnç çizgisini durdurabilir.

## Yapılan testler

- Önceki tam test paketi: **4.131 passed, 43 skipped**, Python 3.11.2 (bu dar tanı iyileştirmesinden önce).
- Bu takipte direnç motoru + chart bridge/integration/render/snapshot + teslim E2E + dikey politika: **137 passed**; Ruff ve `git diff --check` geçti.
- `.venv/bin/ruff check .`: **All checks passed**.
- `git diff --check`: geçti.
- Bu denetimde gerçek Telegram ağına, Render'a veya Supabase yazımına istek yapılmadı; canlıya deploy edilmedi.

## Öncelikli takip önerisi

1. Canlı ortamın `TELEGRAM_GRAFIK`, Stabil alarm anahtarı, DM/public hedefleri ve izinlerini operatörle doğrula; önce tek test sembolüyle kontrollü grafik denemesi yap.
2. Stabil DM geri-alım alarmında grafik istenip istenmediğine karar ver; DM/public farkını davranış sözleşmesinde açık tut.
3. Günlük Stabil destek cache akışını günlük dirençle aynı karede tutarlı hale getirecek küçük entegrasyon testi ekle.
4. “Hazır fakat kadraj dışında” ve “veri güvenliğinde bastırıldı” durumlarını otomatik grafik teslim metaverisinde görünür yap.
5. Güçlü/zayıf oklar ve BOS ilişkisi için bekleyen replay'leri ayrı araştırma olarak tut; sonuç görmeden BOS filtresi veya yeni sinyal eşiği ekleme.

## Bağlantılar

- [Direnç görsel ve teslim E2E denetimi](../tasarim/STABIL_DIRENC_GORSEL_TESLIM_DENETIMI_2026-11-07.md)
- [Direnç uygulama ve güvenlik notları](../tasarim/STABIL_DIRENC_CANLI_TEST_ON_KONTROL_2026-11-06.md)
- [Direnç/destek 50-hisse araştırması](../arastirma/stabil_direnc_50_model_testi_2026_11_06/RAPOR_50.md)
- [Günlük native direnç replay'i](../arastirma/stabil_direnc_replay_2026_11_06/RAPOR.md)
- [Stabil ana rehberi](../arastirma/STABIL_REHBERI.md)
