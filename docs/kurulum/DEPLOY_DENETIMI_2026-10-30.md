# Deploy denetimi — 30 Ekim 2026

## Durum ve kapsam

Repo/Actions, Render Blueprint ve çalışma akışı, sağlık uçları, Telegram,
Supabase ve kapanış/restart yolları incelendi. Canlı Render Dashboard'a veya
servis URL'ine erişim olmadığından gerçek ayarlar, canlı commit, gerçek Telegram
mesajı ve sıfır kesintili geçiş doğrulanamadı. Deploy tetiklenmedi. Önceki
Supabase incelemesinde proje REST/DB erişilebilir, Realtime sağlıksız görülmüştü;
Realtime'ın bu bot için gerekli olduğu doğrulanmadı. Bu durum bugünkü Render
servis ayarlarını kanıtlamaz.

## Bulgular ve düzeltmeler

1. 29 Ekim main deploy koşusu `40899846264` başarılı görünse de **Deploy
   tetikle adımı atlanmış**. Bu, Render Auto-Deploy üzerinden dağıtım yapılıp
   yapılmadığını söylemez. Eskiden hook push ile CI'a paralel tetikleniyordu;
   Blueprint de push'ta auto-deploy istiyordu. CI kırıkken dağıtım ve çift
   tetiklenme mümkündü. Blueprint, `checksPass` ister; workflow hook'u yalnız
   manuel kurtarmaya çevrildi. Manual hook CI'ı atlayabilir. Render'ın CI
   seçeneği tüm algılanan kontrolleri bekler; sıfır kontrol veya başarısız
   kontrol dağıtımı engeller [1](https://render.com/docs/deploys).
2. `/health` daha veri yüklenmeden HTTP 200 dönüyordu ve hala liveness amacıyla
   böyle kalır. Yeni `/ready` başlangıç bayrağı tamamlanıncaya ve kapanış bitene
   kadar 503 döner; 200, Telegram/Supabase/veri kalitesini veya tek örnek
   çalışmasını garanti etmez. `?strict=1` yalnız bayat heartbeat'i 503 yapar,
   eksik heartbeat'i değil. Deploy doktoru bu bilinmezlikleri raporlar. Sağlık
   sağlayıcısı hata iletisindeki olası sırlar artık HTTP/loga yazılmaz.
3. Keep-alive doğrulaması yalnız `"status"` anahtarının varlığını arıyordu;
   hatalı durumlar başarı sayılabilirdi ve timeout yeniden deneme süresinden
   kısaydı. JSON'da `status == "ok"` aranır, ağ hatası doğru gösterilir,
   geçersiz/ertesi güne taşan saat pencereleri işlenir; eksik adres hata verir.
4. `/test` rehberi sırları URL'ye koyuyor ve varsayılan ayarla çelişiyordu.
   Rehber ve örnek ortam başlıkla kullanımı gösterir; `?k=` varsayılan kapalı.
   Test gerçek Telegram mesajı gönderir. Yanlış `/test kapalı` logu düzeltildi.
5. Ana döngü hata geri beklemesindeki 30 saniyelik kesintisiz uyku, SIGTERM
   sonrası kapanış kaydını geciktirebiliyordu. Shutdown duyarlı bekleme kullanılır;
   ağ çağrılarının zaman aşımı ve yük altında bütün kayıtların platformun
   kapanış süresine sığması yine canlıda ölçülmelidir.

## Açık yüksek risk: deploy sırasında iki çalışan süreç

Render'ın sıfır kesintili geçişinde yeni örnek başlarken eski örnek bir süre
çalışmaya devam eder [1](https://render.com/docs/deploys). `/health` erken 200
verir ve yeni botun başlangıç işlemleri arka planda yürür. Mevcut Supabase
`_tekil_ornek_kontrolu` yalnız uyarır; atomik tek-yazıcı kilidi değildir. İki
örnek aynı Telegram'a bildirim gönderebilir, Telegram webhook kaydını değiştirebilir
ve aynı durum anahtarlarını yazabilir. `/ready` eklemek bu yarışı **çözmez**;
hatta Render health path'ini değiştirerek tek başına düzeltilmez. Bunu güvenli
biçimde gidermek için süreli, atomik Supabase liderlik kirası + fencing,
ödeme/teslim idempotency ve eski/yeni örneğin kontrollü devri gerekir; canlı
veritabanına şema/migrasyon uygulamadan burada otomatik etkinleştirilmedi.
Bu çözümün ağ bölünmesi, kira süresi dolması, SIGKILL ve iki örnekle test edilmesi
gerekir. O zamana kadar geçişleri düşük etkinlik saatinde operatör izlesin,
çift örnek uyarılarını kontrol etsin; bu önlemler yarış olasılığını sıfırlamaz.

Supabase kullanılamıyorsa bot devam eder: geçici disk/cache, cooldown ve kuyruk
kalıcılığı garanti edilmez. Shutdown'da `save_all`, digest ve mirror flush
best-effort çalışır; platformun SIGKILL sınırı veya başarısız uzak yazım kayba
neden olabilir. Çoklu tablo hydration snapshot/pagination ve mirror hatalı batch
riskleri önceki Supabase denetiminde de açık kalmıştır; yeniden başlatma testinde
bunlar ayrıca değerlendirilmelidir.

## Canlıya geçirmeden kontrol listesi

1. Bu değişiklikler henüz canlı değildir. Eski otomatik hook'a bağlı kurulumlarda
   öncelikle mevcut Render servisi, bağlı `main` branch'i, Git provider
   bağlantısı ve **Auto-Deploy → After CI Checks Pass** ayarını doğrulayın.
   Mevcut servis Blueprint ile yönetilmiyorsa `render.yaml` onu değiştirmez;
   mevcut servisin yanına ikinci Blueprint servisi kurmayın. Manuel hook'u
   sürekli otomasyonla eş zamanlı kullanmayın. Varsayılan olarak hook latest
   commit'i deploy eder; SHA'lı hook auto-deploy'u kapatabilir
   [2](https://render.com/docs/deploy-hooks).
2. `RENDER_HEALTH_URL` gerçek `/health` adresi olarak tanımlı ve keep-alive
   koşusunun ilgili adımı gerçekten başarılı mı kontrol edin. Zamanlama
   varsayılanı her gün 08:00–23:00 İstanbul; GitHub cron ve Free uyku 7/24
   çalışma garantisi değildir. Yeşil workflow dış pencere nedeniyle atlanmış
   olabilir. Hatalı keep-alive koşuları da ilgili commit üzerindeki CI kontrol
   durumunu etkileyebilir; Render'ın beklediği tüm kontrolleri inceleyin.
   Secret/variable listeleme yetkisi bu incelemede yoktu.
3. Render Environment'ta Python sürümü, token/sohbet kimlikleri, webhook
   secret, Supabase URL/service role key ve tablo/izinler kontrol edilsin;
   değerleri kayıt veya sohbetlere yapıştırmayın. DB şema değişikliği yapmadan
   önce ayrı yedek ve erişim denetimi uygulayın.
4. GitHub CI'ın dağıtılacak SHA için yeşil olduğunu, sonra Render Deploys'ta
   başarıyı ve `/health` commit alanını görün. `/ready`, heartbeat/scan,
   `komut` alanları ve loglar ayrı kontrol edilsin. İsteğe bağlı `/test`
   başlıkla bir gerçek mesaj gönderir; gelen Telegram komutları da gerçek
   cihazda ayrıca doğrulanmalıdır. Sinyal/restart sırasında kuyruk ve uzak
   kayıt sürekliliği kontrollü test edilmelidir.
5. GitHub Actions branch koşusu `40932967720` pytest aşamasında başarısızdı;
   log indirme EOF verdiği için gerçek hata saptanamadı. Yerel başarı bu koşunun
   sebebini veya bir sonraki Python 3.12 CI sonucunu kanıtlamaz.

## Doğrulama

- İzole, sır içermeyen Python 3.11 ortamında tam paket: **2931 başarılı, 43
  atlandı** (değişikliklerin son küçük kapanış iyileştirmesinden önce); ilgili
  testler ayrıca tekrar koşulur. `ruff check .` ve `git diff --check` temiz.
- CI'ın beş bağımsız scripti başarılı; zamanlama 102/102. Gerçek `python main.py`
  ile CI HTTP smoke çalıştı: `/health` 200, `/ready` 503 (smoke modunda başlangıç
  özellikle yapılmaz), kapalı `/test` ve webhook 404. Son kapanış değişikliği
  sonrası hedefli testler: 92 başarılı, 14 atlandı.
- Python 3.12 için tüm bağımlılık ağacı Linux cp312/universal wheel olarak
  çözümlendi ve indirildi; gerçek Python 3.12 ortamı indirilemedi, bu yüzden sürüm paritesi
  ve Render build'i henüz uçtan uca kanıtlanmış değildir.
- Webhook/health/doctor/workflow davranışları sahtelenmiş ağ veya yerel HTTP ile
  test edildi; bunlar gerçek Render/Telegram/Supabase teslimi değildir.
