# Deploy ve Stabil entegrasyonu kontrolü

## Kanıt ve sınır

Bu inceleme checkout ve izole yerel testlere dayanır. Render Dashboard, canlı servis ayarları/logları, Telegram ve veri sağlayıcılarına erişimle doğrulama yapılmadı; deploy veya GitHub değişikliği tetiklenmedi. Yerel Python 3.11 ile çalışıldı; Render/CI `.python-version` 3.12 kullanır. GitHub'daki mevcut main commit `f03b155...` için CI başarılıdır, ancak bu çalışma alanındaki henüz commit edilmemiş değişikliklerin GitHub CI'dan geçtiğini göstermez.

## Deploy zinciri

1. `render.yaml` isteğe bağlı Blueprint'tir; mevcut Dashboard servisini otomatik olarak değiştirdiği varsayılamaz. Build `pip install -r requirements.txt`, başlangıç `python main.py`, sağlık yolu `/health`. Mevcut Dashboard'da branch, build/start komutları, Python sürümü ve otomatik deploy ayarı ayrıca kontrol edilmelidir. Blueprint'i var olan servis üzerine ayrıca uygulamak ikinci bot oluşturabilir.
2. `.python-version` 3.12; `requirements.txt` sabit sürümlü. Yerel bağımlılık kurulumu, `ruff check .`, `deploy_check.py --skip-network` başarılı. Doktorun yerelde bildirdiği Telegram/Supabase eksikleri yalnız bu test ortamını gösterir, Render ortamını değil.
3. Script giriş noktası ayrı `main` modülü oluşmasını önler, sağlık sunucusunu yükleme öncesinde açar. Ağsız smoke ile gerçek giriş noktasında `/health` ve sorgulu biçimi 200, `/ready` 503, kapalı HTTP `/test` ve webhook 404 görüldü. `/health` liveness'tır: 200, ilk veri yüklemesi ve komut sisteminin hazır olduğunu kanıtlamaz. `/ready` yalnız başlangıç/kapanış durumunu bildirir; her sembolün güncel olduğunu kanıtlamaz.
4. CI lint, tam pytest, bağımsız regresyon betikleri ve health smoke içerir. Son yerel tam test: 3292 geçti, 43 atlandı. Sonraki deploy/Stabil odaklı testlerde 183 geçti; bağımsız CI regresyon betikleri ve Ruff başarılı. GitHub CI'nın bu değişiklikler için çalışması commit/push sonrası ayrıca gerekir.
5. `deploy.yml` yalnız elle, main üzerinden ve gizli hook ile istek gönderir; 200/201/202 yalnız isteğin kabulüdür. Otomatik deploy, yalnız gerçek Dashboard/Blueprint ayarları ve bağlı branch ile doğrulanabilir. Canlı sürümü Render Deploys ve `/health` commit bilgisiyle karşılaştırın; ayrıntılı hazır olma ve veri sağlığını ayrı kontrol edin.
6. Keep-alive varsayılan olarak 08:00–23:00 ve 02:00–02:20 TSİ penceresinde en iyi çabayla ping atar; Actions cron gecikebilir/devre dışı kalabilir, hedef değişkeninin gerçekten ayarlı olduğu bu ortamda doğrulanmadı. Gece tüm evrenin 1s/1g yenilenmesinin o pencerede biteceği garanti değildir; işlem daha uzun sürerse uykuya geçebilir. Özel saat pencereleri/gece ayarları gerçek serviste de kontrol edilmelidir.
7. Varsayılan Render geçici disk ve Supabase salt-okunur modu, yeniden başlatmada yeni mum/state kaybına açıktır. `bot_data` seed evrenin tamamı değildir. Bu yüzden fetch/yeniden yükleme ve gerçek kalıcı disk ayarlarını kontrol etmeden süreklilik garanti edilemez; ikinci örnek açılmamalıdır.
8. Startup'ta `_startup_ready`, ilk yükleme denemeleri ve hazırlık tamamlandıktan sonra açılır; başarısız sembollerin bulunmaması şart değildir. Başlangıçta saatlik ve günlük çekimlerin yaklaşık %80'i başarılı olduğunda gece yenileme gün damgası da yazılabilir: kalan sembollerin güncel olduğu anlamına gelmez. Sembol bazlı son başarılı veri, hata ve son kapanış ayrıca izlenmelidir.

## Stabil: hangi yolda, hangi kısıtla?

- `/stabil [HISSE]`: kayıtlı komut; canlı saatlik/günlük cache üzerinden bağımsız hesap. Makro semboller desteklenmez; yetersiz günlük veri uyarılır. Güncel veri bulunması otomatik garanti değildir.
- `/grafik`: seçilen TF için izole Stabil; günlük ve 4s bağlamı aynı canlı cache'den hazırlanır. Yetersiz veri/hesaplama hatasında uyarı vardır. Destek oluşmadıysa çizgi uydurulmaz; sade görünüm Stabil'i gizler. Makro semboller Stabil'in BIST takvim sözleşmesi dışında kalır.
- `/test`: derin geçmiş OHLCV arşivi kullanır; soru anındaki kapanmış 1g/4s geçmişinden izole Stabil hesaplanır. Canlı cache'e veya canlı motor durumuna yazılmaz; gelecek mumlar soru analizi girdisine dahil edilmez.
- Canlı tarama bildirim sonuçları, uygun 1g/4s veri olduğunda TF başına Stabil sonucunu taşır; 4s geri alım sinyali için ayrıca hesaplama yolu, tazelik ve mükerrer/cooldown koruması vardır. `STABIL_GERI_ALIM_ALARM`, DM/public hedef ayarları, veri yeterliliği ve alarm koşulları sonucu etkiler. Oluşan sinyal veya Telegram teslimi gerçek ortam testi olmadan garanti edilemez.
- Alarm grafikleri `TELEGRAM_GRAFIK=alarm` ile açıksa hesaplanmış TF sonuçları katmana taşınır; `yok` ayarı alarm grafiğini kapatır. `/grafik` bu ayardan bağımsızdır. Varsayılan Blueprint alarm grafiği `yok`tur; Dashboard ayarı farklı olabilir.
- `/stabil` cache'e bağlıdır; her piyasa/seans için bağımsız güncellik doğrulaması veya sorunsuz 24 saat çalışma garantisi yoktur. Özellikle makro grafik veri yenilemesi ve kapanış semantiği raporda ayrı açık risk olarak kalır.
