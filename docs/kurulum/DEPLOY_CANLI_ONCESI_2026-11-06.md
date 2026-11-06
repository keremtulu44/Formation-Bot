# Render deploy denetimi ve kontrollü operasyon — 6 Kasım 2026

## Karar özeti

Kod, test ve erişilebilen GitHub/Supabase **salt-okunur metadata** incelendi; bu
denetim canlı Render deploy logları, Dashboard ayarları veya gerçek Telegram/Yahoo
teslimi değildir. `main`e merge, mevcut Render Dashboard auto-deploy ayarına
bağlı olarak canlı deploy başlatabilir. Blueprint yalnızca Blueprint ile yönetilen
servise uygulanır; **mevcut botun yanına ikinci servis oluşturmayın**.

Üç açık operasyonel risk kapatılmadan **kesintisiz tarama, tek sender veya
restart boyunca tam veri koruması garanti edilemez**:

1. GitHub keep-alive'ın gerçek sıklığı `*/5` hedefinden çok uzaktır. Bağımsız,
   gerçekten ölçülen izleme/uyandırma veya uygun sürekli çalışan plan gerekir.
2. Supabase bot tarafından salt okunur; Render varsayılan diski geçicidir. Yeni
   kuyruk, gönderim mühürleri, sayaçlar ve mumlar disk kaybolunca kaybolabilir.
3. Tek ölçekli web servis bile rolling deploy sırasında eski/yeni süreçleri kısa
   süre birlikte çalıştırabilir. Dağıtık liderlik/fencing yoktur; iki sender ve
   aynı token için webhook/state yarışı mümkündür. Otomatik secret'ın sabit
   türetilmesi yalnız yeni örneklerin aynı header'ı doğrulamasını sağlar, lider
   seçmez. Eski rastgele secret kullanan sürümden **ilk geçiş** ayrıca 403/yeniden
   deneme yaratabilir. Tekilleştirme süreçler arasında garanti değildir.

## Doğrudan gözlenen kanıtlar

### GitHub Actions — 6 Kasım 2026, yaklaşık 06:00 UTC

- Varsayılan branch'teki keep-alive workflow'u `active`; ilgili YAML'de cron
  `*/5 * * * *`. Son **100 schedule başlangıcı** 17 Ekim 23:24:15 UTC ile
  6 Kasım 01:45:14 UTC arasındaydı. Ardışık **99/99 aralık 15 dakikadan uzundu**;
  medyan **290,6 dk**, maksimum **519,2 dk**. Bu ölçüm GitHub tetiklenme
  aralığıdır; Render'ın hangi saatlerde gerçekten uyuduğunu tek başına ölçmez.
- Aynı 100 işin genel sonucu `success`; son 12 işin `GET /health` adımları
  incelendiğinde **6 success / 6 skipped** görüldü. Yeşil iş = HTTP isteği
  değildir. Success adımı HTTP 200 + `status=ok` kontrolünden geçtiğini gösterir;
  hangi Render servisi olduğu veya botun güncel/veri açısından hazır olduğu
  bu metadata ile doğrulanamaz.
- Başlangıç aralığının tamamen kapsadığı **19** İstanbul 02:00–02:20 penceresinin
  **16'sında** hiç schedule başlangıcı yok. Gece penceresi desteği workflow'a
  2 Kasım'da eklendi; onu izleyen örneklemde tamamen kapsanan **4/4** gece
  penceresinde başlangıç yoktu. Önceki sürümlerde üç gece başlangıcının GET
  adımı `skipped`; bu eski sürümlerde gece desteği bulunmadığından onlar için
  güncel konfigürasyon hatası sonucu çıkarılamaz.
- Örnekler: [son koşu](https://github.com/keremtulu44/Formation-Bot/actions/runs/42145902949),
  [gündüz GET başarılı örnek](https://github.com/keremtulu44/Formation-Bot/actions/runs/42049711929).
  Ham Actions logları ortamın izin vermediği bir log-indirme hostuna yönlendiğinden
  okunamadı; yukarıdakiler job/step metadata'sıdır. Secret/variable listesi için
  GitHub entegrasyonu 403 verdi; URL'nin, gece değişkenlerinin ve deploy hook'unun
  canlı değerleri **doğrulanmadı**. Seyrek tetiklenmenin kök nedeni kanıtlanmadı.
- Tekrar ölçüm: `python scripts/keepalive_audit.py --repo keremtulu44/Formation-Bot`.
  Betik yalnız metadata okur, Render'a ping atmaz; 0 yalnız örneklenen schedule
  aralıklarının eşikte olduğunu, 1 bulunan sorunu, 2 yetersiz kanıtı bildirir.
  Sağlık adımları örneği ile tüm gerçek ping geçmişi aynı şey değildir.

### Bağlı Supabase projesi — yalnız SELECT/health

- Bağlı projede DB ve REST `ACTIVE_HEALTHY`; `public.bot_store` mevcut. Repo
  rehberinde aynı proje referansı geçiyor, ancak Render'ın şu anda bu projeye
  bağlı olduğu Dashboard/env doğrulanamadığından kesin söylenemez.
- `bot_store`: `formation-bot:` önekli **61** 1H, **60** 1D ve **14** state
  kaydı. Bu kategorilerde en yeni değişiklikler 30 Ekim 2026'da; bu, bugünkü
  canlı durumun yedeği olduklarını kanıtlamaz. RLS açık, `bot_store` için policy
  sayısı 0; `anon` ve `authenticated` SELECT yetkisi yok, `service_role` SELECT
  yetkili. Bağlantının kullandığı gerçek anahtar/Render env'i görülmedi.
- Salt okunur `state:digest_pending` 30 Ekim'den **7 bekleyen aday** içeriyordu;
  son digest günü 28 Ekim. Bunların daha sonra Telegram'a gidip gitmediği
  bilinmiyor. Eski kod boş geçici diskle açılırsa eski özeti tekrar gönderebilirdi.
  Yeni kod bu doğrulanmamış uzak özeti otomatik yüklemez; uzak kayıt **silinmedi**.
  Aynı şekilde doğrulanmamış uzak acil/outbox bekleyenleri otomatik oynatılmaz;
  mevcut yerel durum önceliklidir. Bu, kayıp olmayan otomatik teslim garantisi
  değil, belirsiz uzak durumu otomatik tekrarlamama tercihidir.
- Aynı tarihli uzak bildirim outbox'ında 39 satır ve 0 bekleyen satır; eski acil
  kuyruk kaydında 0 satır görüldü. Bunlar tarihsel kayıtlar, güncel canlı teslim
  kanıtı değildir. Hiçbir SQL yazma/silme, şema veya secret değişikliği yapılmadı.

### Güncel hedef ve bildirim incelemesi — 6 Kasım

- Kullanıcı eski `@bisthisseveri` **kanalından** `https://t.me/FormationBot1`
  **grubuna** geçtiğini bildirdi. Public önizleme `Formation` adlı, 2 üyeli bir
  gruba katılma ekranını gösterdi; bu sayfa grup gönderi geçmişi, bot üyeliği veya
  bugünkü teslim hakkında kanıt sağlamıyor. Eski kanalın son gönderileri artık
  güncel grubun çalıştığı/çalışmadığına delil değildir.
- Gerçek Render değerleri erişilemedi. `TELEGRAM_GROUP_ID` önceliklidir;
  `TELEGRAM_CHANNEL_ID` yalnız grup değeri boşsa kullanılır. Bu yüzden Render'da
  yeni grup hedefini ve varsa `PUBLIC_COMMAND_CHATS` eski listesini doğrulayın.
  Botun grupta metin **ve fotoğraf** izni ayrı ayrı önemlidir. Grup kullanıcı adı,
  `@FormationBot1` veya sayısal kimlik kullanılabilir; Telegram davet bağlantısı
  sohbet kimliği değildir. Yeni kod public `t.me` kullanıcı adı URL'sini de normalize
  eder; örnek env dosyasını değiştirmek Render ayarını değiştirmez.
- Kod varsayılanları ile canlı env aynı olmak zorunda değildir: teyitli kırılım,
  başarılı retest ve teyit sonrası geçersizleşme yayınlanabilir; deneme/bekleme
  state'leri doğrudan push değildir. Varsayılan kalite tabanları 1s=80, 2s=78,
  4s=75, 1g=70. `PUBLIC_STATES` veya ek public kalite eşiği bunları daraltabilir.
  Eski rehberdeki `FORMASYON_TAMAMLANDI,RETEST_BASARILI` listesi efektif olarak
  yalnız retest bırakır; kullanıldığını bilmiyoruz. Eski örnek 6/saat, 25/gün
  limitliydi; mevcut varsayılan 20/saat, 120/gün metindir. Görsellerin ana şalteri
  `TELEGRAM_GRAFIK` varsayılan/örnek değerle `yok` olduğunda grafik üretilmez;
  `alarm` olarak açılması gerekir. Gerçek Render değerleri bilinmiyor.
- Aynı turda üçten fazla yeni domain adayı varsa normal politika en yüksek ikiyi
  tekil kart+görsel, kalanları metin özeti şeklindedir; özet üyeleri tek tek
  görsel almaz. Önceden gönderilmiş adaylar artık burst sayısına katılmıyor;
  uzun toplu özetler aday isimlerini kaybetmemek için sayfalara ayrılıyor.
- `YENI_DOMAIN_ALARM_COOLDOWN_BAR=6` ayarının kodda farklı barları kapsamadığı
  tespit edildi: anahtarın kendisi bar zamanını içeriyor, dolayısıyla pratikte
  aynı-bar tekilleştirme var. Bu davranışı altı barlık yasak hâline getirmek yeni
  alarmları azaltacağından bu incelemede değiştirilmedi. Stabil'in altı 4s barlık
  cooldown'ı ayrı çalışır.
- Dikey destek üzerindeki yukarı denemede aşağı uyarı politikası korunur: bu
  olay güçlü yeşil Stabil geri-alım alarmı sayılmaz. Test edildi; bu dalda bazı
  eski pozitif Stabil alarmları azalabilir. Bunun bugünkü canlı örneklerin nedeni
  olduğu veya dalın Render'da çalıştığı kanıtlanmadı.

## Kodda düzeltilen deploy sınıfı sorunlar

- Salt okunur uzak eski digest ve pending outbox tekrarını engelleme; yerel
  cooldown, sayaç, mühür ve kuyrukları eski uzak kopyaya karşı önceliklendirme.
- Gece temizliğinde artık her hedef için **1H ve 1D doğrulanıp yerel kaydedilmeden**
  tamamlandı damgası basılmaz. Kısmi başarıda yalnız tamamlanmamış semboller aynı
  işlem içinde en erken 10 dk sonra yeniden denenir. İlk cache preload'u temizlik
  sayılmaz; eski kuralla yazılmış sürümsüz damgalar geçersiz sayılır. İlerleme
  bellektedir: restart'ta tam evren yeniden denenebilir. Başarılı yazım, ayrıca
  veri bütünlüğü/kapanış tazeliği veya kalıcı disk garantisi değildir.
- Yerel, geçmiş günün kaçırılmış digest telafisi başarısız/belirsizse tam tampon
  `DATA_DIR/telegram_missed_digest_*.json` altında **yerel inceleme arşivine**
  alınır; otomatik tekrar gönderilmez, çünkü timeout sonucu belirsiz olabilir.
  Dosya yazılamazsa mevcut tampon hemen temizlenmez ve hata loglanır; sonraki gün
  veya disk kaybında yine kayıp riski vardır. Arşiv de Render geçici diskinden
  daha dayanıklı değildir.
- Otomatik webhook secret yüksek entropili bot token'ından HMAC ile türetilir;
  açıkça yapılandırılmış secret önceliklidir. Rotasyon için bağımsız güçlü
  `TELEGRAM_WEBHOOK_SECRET` kullanılabilir; hiçbir secret'ı loglamayın.
- SIGTERM sonrası yeni webhook işleri 503 alır; kapanış açılış sırasında gelirse
  yeni Telegram bağlantısı/kuyruk boşaltma/listener ve ilk fetch başlatılmaz.
  Hâlihazırda başlayan ağ çağrısı anında iptal edilemez.
- Keep-alive job özeti pencere dışı `GET` atlamasını açık yazar. Cron değiştirmek
  veya başka bir Actions işi eklemek GitHub'ın dış zamanlayıcısını garanti edemez.
- Standalone domain/Stabil kartının public kopyası artık DM'den bağımsız yerel
  `DATA_DIR/telegram_public_aux.json` kuyruğuna alınır; kota veya kesin 4xx
  reddinde pencere içinde tekrar denenir. `ACIL_KUYRUK_TTL_DK` (varsayılan 180 dk)
  aşılırsa veya gün değişirse otomatik gönderilmez. Timeout/5xx, gönderim sırasında
  kapanma, kısmi görsel ve hedef değişikliği elle incelemeye gider; otomatik kör
  tekrar çift gönderime yol açabilir. `/durum` pending/review ve açılıştaki
  metin/fotoğraf izin durumunu gösterir; izin bilgisi canlı sürekli test değildir.
  100 tamamlanmamış/inceleme kaydı sınırı, yerel diskin kaybı, eşzamanlı süreçler
  ve belirsiz ağ sonucu nedeniyle bu bir teslim veya exactly-once garantisi
  değildir. Kuyruk eski hedefe yazılmış mesajı yeni gruba otomatik taşımaz.
- **Bilinen asimetri:** public başarılıyken DM başarısız olursa bu özel kuyruk
  DM'yi telafi etmez. Görsel üretilemez/gönderilemezse metin yine gidebilir;
  ilgili sayaç/log ve inceleme kaydı kontrol edilmelidir.

## Birleştirme/deploy öncesi kontrol

1. Çalışma ağacının temiz, PR'ın doğru session branch'inden ve güncel `main`e
   karşı olduğunu doğrulayın. PR/head SHA üzerinde **Python 3.12 CI** başarıyla
   tamamlanmadan merge etmeyin; `gh pr checks <PR>` ve Actions job adımlarına
   bakın. Green check başka SHA'ya aitse geçerli kanıt değildir.
2. Render Dashboard → ilgili **mevcut** servis: branch, build
   `pip install -r requirements.txt`, start `python main.py`, Python 3.12,
   health `/health`, auto-deploy/check kapısı ve env değişkenlerinin **adlarını**
   kontrol edin. `render.yaml` mevcut Dashboard ayarlarını otomatik kanıtlamaz.
3. İkinci servis/worker/polling istemcisinin aynı token'la çalışmadığını ve
   deploy sırasındaki olası iki-process penceresini değerlendirin. Gerçek tek
   sender gerekiyorsa bakım penceresinde eski sender'ı durdurarak geçiş veya
   ayrıca uygulanmış güvenilir dağıtık liderlik/fencing gerekir. Platformun
   özelliklerini/kesintisini ve devralma prosedürünü önceden doğrulayın.
4. `DATA_DIR` ve ilgili local state dosyalarının uygun izinli yedeğini alın;
   kişisel/sır içerebileceği için repoya, Actions loguna veya sohbete koymayın.
   Kalıcı disk gerekiyorsa seçilen Render planında destek/maliyet ve tek-yazar
   kullanımını doğrulayın. Salt okunur Supabase'in yedek yazdığını varsaymayın.
5. GitHub `RENDER_HEALTH_URL`, `KEEPALIVE_*` ve gerçek hedefi yetkili panelden
   doğrulayın; değerleri paylaşmayın. Bağımsız monitörün gerçekten 15 dakikadan
   kısa aralıklarla geldiğini ve alarm ürettiğini gözlemleyin; yalnızca ayar yapmak
   garanti değildir. Uyandırma saatlerini/Render kota ve ücretlerini kontrol edin.

## Merge/deploy sonrası doğrulama

1. Render → Deploys/Logs: beklenen deploy'un gerçekten tamamlandığını, eski/yeni
   örnek sayısını ve hata/yeniden başlatmaları görün. Manuel deploy hook'unun HTTP
   200/201/202 yanıtı yalnız **isteğin kabulüdür**, deploy tamamlandı demek değildir.
2. `/health` içindeki `commit` değerini (varsa ilk 7 karakter) deploy edilen
   **merge commit'i** ile karşılaştırın; alan yoksa Dashboard/log üzerinden doğrulayın.
   HTTP 200 yalnız liveness'tır. `/ready` startup sırasında/kapanışta
   503, tamamlanınca 200 olabilir; bu da tüm sembol, Telegram veya Supabase sağlığı
   demek değildir. `/health?strict=1` bayat heartbeat'i 503 yapabilir, ancak
   `heartbeat_stale=null` sağlıklı veri kanıtı değildir.
3. Yetkili ortamda `python deploy_check.py --url https://<servis>.onrender.com`
   ile yapılandırma/erişim bulgularını inceleyin. `--send-test-message` gerçek
   mesaj gönderir; test hedefi ve izin olmadan kullanmayın. Webhook `mod`, dinleyici,
   Telegram `getWebhookInfo`, 401/403/409/429 ve bekleyen güncellemeler izlenmeli.
4. İlk gerçek taramada log ve yetkili `/durum` üzerinden toplam/başarılı sembol,
   kapanmış son bar zamanı, veri tazeliği ve hataları kontrol edin. `startup_complete`
   tüm sembollerin güncel olduğunu söylemez. 02:00 işi için `GECE ... BAŞLIYOR`,
   `1H yenilenen`, `1D yenilenen`, `kalan sorunlu` ve tamamlanmadı uyarılarını
   izleyin; servis 09:30'dan sonra uyanırsa o günün gece penceresini kaçırabilir.
5. Çift alarm, kuyruk birikimi, güncel olmayan veri, webhook hata yağmuru veya
   iki sender görülürse yeni gönderimleri güvenli biçimde durdurun ve inceleyin;
   timeout sonrası mesajı körlemesine tekrar göndermeyin. Alarm outbox'ı
   **at-least-once** çalışır, belirsiz ağ hatasında tekrar mümkündür.

## Rollback / kurtarma

- Önce etkili sender'ı ve deploy otomasyonunu kontrol altına alın; eski ve yeni
  örneklerin örtüşmesi rollback sırasında da olabilir. Render planında desteklenen
  yöntemle son bilinen iyi commit'i deploy edin; Dashboard son durumunu doğrulayın.
- Eski sürüm, bu değişikliklerle oluşturulmuş güncel yerel state'i veya webhook
  secret'ı farklı yorumlayabilir. İzinli yedeği koruyun; state/DB'yi körlemesine
  silmeyin, geçmiş Supabase kuyruklarını yeniden oynatmayın.
- `telegram_missed_digest_*.json` ve `telegram_public_aux.json` için önce
  güvenli yedek alın ve gerçek Telegram geçmişini kontrol edin; "belirsiz" kayıt
  mesajın gitmediğini ispatlamaz. Özel kuyruğun `uncertain`, `graphics_uncertain`,
  `expired` ve `target_changed` satırlarını otomatik göndermeyin. 100 tamamlanmamış
  kayıt sınırı dolduysa yetkili operatör her kaydı hedef/geçmiş/tazelik açısından
  incelemeli; dosyayı veya kayıtları körlemesine silmemelidir. Elle telafi/temizlik
  yalnız çift mesaj ve yanlış gruba gönderim riski değerlendirilerek yapılmalıdır.
- Son başarılı deploy'a döndükten sonra `/health` commit, `/ready`, gerçek tarama
  ve Telegram yolunu tekrar kontrol edin. Bu kontroller yapılmadıkça rollback
  başarıyla tamamlandı denmez.
