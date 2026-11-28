# Formation-Bot — genel durum ve yön

**Tarih:** 27 Kasım 2026 · **Durum:** tarihli inceleme kaydı; dağıtım onayı değildir.
**İncelenen taban:** `dddf38abb30bf4af76dfa1e2e010b3d83d283c1b` ve bu oturumdaki yerel AI/alarm düzenlemeleri.

**Aynı gün sonraki uygulama:** [Mum akışı, AI bütçesi ve bildirim teşhisi](MUM_AKISI_AI_VE_BILDIRIM_2026-11-27.md). Aşağıdaki tespitler inceleme anının kaydıdır; yeni yerel korumalar, testler ve devam eden sınırlar bu takip belgesinde ayrılır. Canlı dağıtım yapıldığı anlamına gelmez.

## 1. Kısa karar

Proje, basit bir formasyon betiğinin oldukça ötesinde: kapanmış mum doğrulaması, formasyon yaşam döngüsü, bağımsız domain motorları, üç alarm yolu, grafikler, Telegram komutları, araştırma ve sonuç defterleri var. **Güçlü tarafı analitik kapsamı ve sözleşme testleri; öncelikli açığı operasyonel süreklilik ve uçtan uca teslim kanıtının parçalı oluşu.**

Önerilen yön: **yeni motor/filtre eklemek değil, mevcut sinyali güvenilir ve ölçülebilir bir ürüne dönüştürmek.** Önce kalıcılık ve teslim, sonra gecikme/izleme, sonra bakım sınırları; yeni strateji en son. Tam yeniden yazım önermiyorum.

- Kontrollü kişisel kullanım/pilot ile büyümeye hazır, kesintisiz hizmet aynı seviye değildir.
- Kod testinin geçmesi, canlı servisin son sürümü çalıştırdığını veya Telegram teslimini kanıtlamaz.
- Araştırmada olumlu tepki oranı, maliyet ve risk sonrası işlem kârlılığı değildir.

## 2. Kapsam ve yöntem

Depo envanteri ve mimari belgelerden başlayıp gerçek çağrı zincirleri üzerinden giriş/zamanlama, veri alma ve kapanış, formasyon ve domain runner, alarm kararları, DM/public teslim kuyrukları, grafik/komut yolları, durum kurtarma, KAP/AI bağlamı, araştırma, güvenlik ve CI/dağıtım incelendi. İnceleme, her araştırma dosyasının her satırına dair biçimsel doğruluk ispatı değildir; kritik üretim yolları ve sınırları önceliklendirildi.

İzlenen Python dosyası sayısı 515; bunların 208'i test adlandırmalı. Bu sayı test vaka sayısı veya kapsam yüzdesi değildir. Büyük veri/replay çıktıları yeniden üretilmedi. Canlıya mesaj atılmadı, Supabase'e yazılmadı, üretim ayarı değiştirilmedi, commit/push/deploy yapılmadı. Önceki AI/alarm çalışması korundu; bu genel incelemede çalışma davranışı değiştirilmedi.

## 3. Sistemin gerçek akışı

```text
main.py → bot/app.py: başlangıç, kurtarma, zamanlama
  → data/: Yahoo → gerektiğinde TV yedeği → temizleme/kapanmış mumlar
  → patterns/: formasyon tespiti, kimlik, yaşam döngüsü
  → domain_engines/: MS / OB / FVG / hacim; ayrıca Stabil bundle
  → üç ayrı aday/teslim yolu:
      1. ana formasyon → DeliveryOutbox + ayrı public bülten yolu
      2. birleşik domain → özel DM/public outbox
      3. Stabil 4h geri alım → özel DM/public outbox
  → bağlam/grafik/uygunsa AI → Telegram
  → yerel durum, history, karne, sağlık ve araştırma raporları
```

**Hesaplanan bilgi ≠ alarm tetiği ≠ kuyruğa kabul ≠ metin teslimi ≠ grafik teslimi.** Projeyi değerlendirirken bu beş aşamayı ayrı tutmak gerekiyor.

## 4. Katman katman değerlendirme

| Alan | İyi çalışan tasarım | Sınır / sonraki iş |
|---|---|---|
| Giriş ve zamanlama | Sağlık sunucusu ana döngüden önce açılıyor; kapanış sonrası tarama, seans/tatil ve manuel iş yolları var. | Uyuyan ücretsiz servis ve en iyi çaba cron'u zamanında çalışmayı garanti etmez. Uzun tarama/AI beklemesi ayrıca ölçülmeli. |
| Veri | Yahoo birincil, TV reaktif; bozuk OHLCV temizliği, veri yok/bayat veri ve kapanmış mum kapıları var. | TV native 4h ile 1h'den türetilmiş 4h aynı veri değildir. Kalite ve kaynak karşılaştırması kaynak/TF bazında yapılmalı. |
| Formasyon | Yaşam döngüsü, dondurulmuş kırılım verileri, kalıcı kimlik/history, tekrar kapıları mevcut. | History/kimlik diski kaybolduğunda güncel süreklilik de kaybolabilir; ham mumdan yeniden hesaplamak teslim geçmişini geri getirmez. |
| Domain motorları | Sonuçlar ayrı tutuluyor, bir motorun hatası diğerlerini kesmiyor; OB/FVG incremental durumları ve reset nesilleri düşünülmüş. | İzolasyon iyi, fakat istisnayı loglayıp devam etmek motorun haftalarca sağlıklı kaldığı anlamına gelmez: motor başına hata/atlama oranı izlenmeli. |
| Alarm politikası | Birleşik domain P6, cooldown, ana formasyon kalite/durum kapıları birbirinden ayrılmış. | Tek bir genel “kalite puanı” bütün yolları açıklamaz. P6'nın amacı isabeti büyütmekten çok kart hacmini azaltmak; eski örneklem geleceğe garanti değil. |
| Teslim | Ana FIFO'da atomik checkpoint, yeniden deneme ve grafik bozukluğunda metinle devam var. Özel outbox'larda belirsiz HTTP sonucu ayrı durum. | Ana formasyon ile özel alarmın belirsiz sonuç politikası aynı değil. DM/public/grafik tek bir “gönderildi” sayacına indirgenmemeli. |
| Grafik ve komutlar | Snapshot temelli çizim, güvenli medya okuma, sınırlı manuel grafik işi ve grup hedefine dönüş var. | Tek smoke örneği tüm sembol/TF görsellerini ispatlamaz; grafik üretiminin gecikme/memory payı ölçülmeli. |
| KAP ve AI | KAP arka plan toplayıcısı ve tetik anına göre bağlam; AI'da doğrulama ve düz karta dönüş var. | Bağlam toplamak, haberin fiyat etkisini doğrulamaz. AI senkron yolun üzerinde ve varsayılan toplam süre bütçesi yok. |
| Kalıcılık | Yerel atomik dosyalar, en yeni snapshot seçimi, dar teslim yedeği seçeneği ve eski uzak veriyi okuma var. | Varsayılan genel uzak store read-only; geçici diskte tüm yeni durum için kalıcı kurtarma garantisi yok. |
| Güvenlik | Yetkide hata halinde ret, webhook secret kontrolü, gövde/rate sınırları, sır maskeleme, pickle opt-in ve SQL'de RLS/revoke var. | Bu inceleme bağımlılık CVE taraması veya canlı RLS/erişim testi değildir. SQL dosyası gerçek sunucudaki izinleri tek başına ispatlamaz. |
| Test/dağıtım | Python 3.12 CI, ortak deploy kurulumu, full pytest, bağımsız motor betikleri ve health/grafik smoke kapıları var. | Yerel Python 3.11.2. Mevcut kirli çalışma ağacı için uzaktaki CI sonucu yok; taban commit'in yeşil olması yeterli değil. |
| Araştırma | Çapa sonrası ölçüm, dondurulmuş ATR, sansür ve örneklem uyarıları gibi önemli korumalar var. | `/backtest` kayıtlı sonuç raporudur, tam strateji replay'i değildir. Karne maliyet katmanı ayrıca vardır; iki raporu aynı finansal ölçüm sanmamak gerekir. |
| Bakım/doküman | Mimari merkez, test korumaları, tarihli karar ve ölçüm kayıtları zengin. | Dosyalara ayırma, `_pkg` üzerinden ortak global namespace bağımlılığını kaldırmamış. Bazı mimari açıklamalar kodun gerisinde kalmış. |

## 5. Öncelikli bulgular

### P1 — güncel durumun kalıcılığı ve yeniden başlatma güvenliği

**Kanıt:** `bot/app.py::main_loop` içinde `SupabaseStore.from_env(read_only=True)`, mirror yazımı kapalı. `SUPABASE_DELIVERY_WRITES` varsayılan 0; açılırsa `DeliveryOnlyStore` yalnız `state:notification_delivery` yazar. `render.yaml` ücretsiz/geçici disk riskini açıkça belgeliyor. Özel outbox'lar yerel dosyalarda.

**Etki:** geçici dosya sistemi kaybolursa güncel cooldown, kimlik/history, karne, bekleyen digest ve özel teslim durumlarının tamamı uzak kopyadan kurtarılamaz. Eski Supabase kaydı veya repo seed'i yeni operasyonel geçmiş değildir. Her süreç restart'ının kesin disk silmesi iddiası yok; risk disk kaybı/redeploy/yeniden yaratılmadadır.

**Karar:** en kısa bütünsel yol, tek aktif örnek + kalıcı `DATA_DIR` + yedek/restore provasıdır. Ücretsiz barındırma zorunluysa, hangi state'in nasıl kurtarılacağı yazılı bir allowlist ile ayrı tasarlanmalı. Genel Supabase yazımını düşünmeden açmak çözüm değildir. Yalnız teslim yedeği açılması **tüm** cooldown/history/KAP/karneyi korumaz.

**Kabul testi:** bir bekleyen ana/özel alarm, kimlik, cooldown ve karne kaydı oluştur; kontrollü yeniden başlatma ve disk-kaybı senaryosunu ayrı dene. Bekleyen işin akıbeti, mükerrerler ve geri gelen kayıtlar listelenmeden “kalıcı” deme. İki örneğin aynı hedefe eşzamanlı çalışmasını ayrıca önle; mevcut read-only mod çoklu örnek bildirimini kapatıyor ve bu bir dağıtık lider kilidi değil.

### P1 — teslim semantiği yollar arasında tutarlı değil

**Kanıt:** `notification_delivery.py::DeliveryOutbox.flush`, `_gonder_metin` başarısızlığında 30 saniye sonra yeniden deniyor; başarılı HTTP'den sonra `text_sent` checkpoint'i var. `notifier/api.py::_gonder_metin` Telegram'a tek istek yapıp başarı/hata döndürüyor. Buna karşılık `public_aux_outbox.py` / `private_aux_outbox.py` timeout/5xx ve yarıda kalan gönderimi `uncertain`/operatör incelemesi olarak ele alıyor.

**Etki:** Telegram isteği kabul edip yanıt kaybolursa ana kuyruk aynı metni tekrar deneyebilir. Başarı ile checkpoint arasındaki süreç ölümü de belirsizlik penceresi. Bu, gerçekleşmiş canlı mükerrer kanıtı değil, koddan görülen hata senaryosu. Telegram idempotency key sağlamadığı için mutlak “tam bir kez” sözü verilmemeli.

**Karar:** ortak teslim sözlüğü belirle: `pending`, `sending`, `sent`, `uncertain`, `failed`, `suppressed`; metin/grafik ve DM/public ayrı. Otomatik tekrar mı, kayıp riskinden kaçınma mı, operatör incelemesi mi tercih edildiği görünür olsun. Başarılı yanıttaki message ID ve olay kimliği tutulmalı. Şüpheli sonucu kör tekrar etmeden önce ürün kararı gerekli.

**Kabul testi:** “sunucu kabul etti, istemci timeout aldı” ve “başarıdan hemen sonra süreç öldü” hata enjeksiyonları her üç alarm yolunda aynı açıklanabilir sonucu vermeli. AI hazırlık kaydındaki `telegrama_gitti=False/dogrulanmadi`, gerçek teslimle ayrıca eşlenmedikçe teslim kanıtı değildir.

### P1 — canlılığın, veri ve teslim sağlığından ayrılması

**Kanıt:** `/health` normalde 200; `/ready` yalnız başlangıç/kapanış kapısı. `?strict=1` heartbeat bayatlığına bakıyor. `bot/commands.py::_saglik_ozeti` scan ve bildirim ayrıntıları üretiyor; `.github/workflows/keepalive.yml` zamanlamanın garanti olmadığını zaten söylüyor.

**Etki:** HTTP 200, taze veri tarandığını ve alarm gittiğini göstermiyor. İlk heartbeat henüz yoksa `heartbeat_stale=None` olabilir; strict sorgu tek başına bütün arızaları yakalamaz. Seans dışında uzun bayatlık eşiği kasıtlıdır.

**Karar:** mevcut liveness kontrolünü acele değiştirip restart döngüsü yaratma. Bağımsız monitörle başlangıç süresi, seans-farkında son başarılı tarama/veri zamanı, işlenen/beklenen sembol, başarısız motorlar, kuyruk yaşı ve `uncertain` adetlerini izle. Aktif sinyal yokken mesaj yokluğunu tek başına hata sayma.

**Kabul testi:** HTTP sunucusu açıkken tarama dursun; veri kaynağı bozulsun; Telegram reddetsin. Üçü farklı teşhis üretmeli. Monitör botla aynı uyku/cron arızasına bağlı olmamalı.

### P2 — dış servis gecikmeleri ana taramaya taşınıyor

**Kanıt:** `bot/scan.py` AI zenginleştirmeyi senkron çağırıyor. `config.py` içinde `AI_YORUM_MAX_BEKLEME_SN=0`; `ai_prompt/client.py` wrapper stream'inde `wait` satırları okunabiliyor, 45 saniye sessizlik timeout'u toplam süre sınırı değil. Zincir sağlayıcıları sırayla dener. TV tarafında `_tv_yedek_dene` yeni daemon thread başlatıp `join(25)` sonrasında dönebilir; çalışan iş o anda iptal edilmiyor. Ortak TV istemcisi iki denemeli ve dönüşte `finally` ile socket kapatıyor; bu koruma yok sayılmamalı.

**Etki:** sürekli wait üreten AI yanıtı alarmı/taramayı uzatabilir. TV worker çağıran döndükten sonra yaşamaya devam edebilir; ardışık takılmalarda kaynak baskısı mümkün. Burada ölçülmüş bir üretim thread sızıntısı veya kilitlenme iddiası yok.

**Karar:** önce toplam tarama, veri, motor, grafik, AI ve teslim sürelerini p50/p95 olarak ölç. Sonra alarm için uçtan uca bir gecikme bütçesi seç; sağlayıcı başına ayarı zincirin toplam bütçesi sanma. TV'ye sınırlı eşzamanlılık ve soket/iş ömrü garantisi tasarla. Sırf thread'e taşımak, iptal ve state güvenliğini çözmez.

**Kabul testi:** bitmeyen AI wait akışı, sürekli TV timeout'u ve aynı anda grafik isteğinde; iş parçacığı/bellek sınırları korunsun, komut sağlığı cevap versin, alarm belirlenen sürede düz karta dönebilsin.

### P2 — politika ve kaynak seçiminin operasyonel görünürlüğü

**Kanıt:** P6/P4/P0 seçimi ve `_politika_gecer` `bot/domain_alarm_service.py` içinde. Tanınmayan politika P0'a dönüyor; elenme nedenleri çoğunlukla DEBUG log. TV gerçek 4h yolu kaynak TV olduğunda deneniyor, olmazsa türetilmiş 4h kullanılabiliyor (`data/fetch.py::fetch_tv_4h`).

**Etki:** yazım hatalı ayar daha fazla kart üreten P0'a dönebilir; yalnız normal seviye logla filtrenin ne kadar elediği bilinmez. Kaynak dağılımı değişirse araştırma ile canlı sonuçların karşılaştırılması da etkilenir.

**Karar:** etkin ayarları sır içermeyen startup/health özetiyle görünür yap; politika/tazelik/kalite/dedup/bütçe/teslim için ayrı sayaç ekle. Politika hata davranışı, mevcut fail-open tercihi değiştirilmeden önce onaylanmalı. Sonuçları kaynak+native/resample+TF+motor/politika sürümüyle ayır.

### P2 — modüler görünümün altında global bağımlılık

**Kanıt:** `bot/__init__.py` facade ve `bot/{app,scan,commands,security,statestore}.py` içinde `import main as _pkg`; önemli davranışlar ortak namespace üzerinden geç bağlanıyor. Komutlar yaklaşık 2.857, tarama 1.990, app 1.166 satır; bunlar tek başına hata değil, etki alanının genişliğinin işareti.

**Karar:** yeniden yazma yerine tek akış seç: tarama sonucu → alarm olayı → teslim kaydı. Açık veri tipleri ve küçük bağımlılık arayüzleri çıkar; eski facade'ı uyumluluk adaptörü olarak koru. Dosyayı bölüp aynı global bağları taşımak tek başına kazanım değil.

**Kabul testi:** seçilen politika/değerlendirici `main` import etmeden çalışabilsin; sabit mum girdisiyle eski/yeni çıktı aynı olsun. Sayısal eşik ve motor davranışı refaktörle aynı değişiklikte değiştirilmesin.

### P3 — dokümanların güncellik sınırı

Mimari merkezdeki “domain dedup anahtarı bar içeriyor, cooldown için test gerekir” uyarısı artık güncel değil: kod `symbol|timeframe`, ayrı `bar_key` ve rolling-window regresyonları içeriyor. Belge dizinindeki açık MS sorunu ifadesi de 28 Ekim düzeltmesini yansıtmıyor. Bu iki navigasyon/açıklama hatası bu incelemede düzeltildi; tarihli eski raporlar yeniden yazılmadı.

## 6. Araştırma tarafına yön

- `analytics/backtest.py` bilinçli olarak kayıtlı history sonuçlarını okuyor; yeniden veri indirip strateji yürütmüyor. Raporunda komisyon/slippage yokluğu belirtilmiş. Buna karşılık `karne.py::sinyal_sonucu` masraf/net katmanı taşıyor. “Projede maliyet hesabı hiç yok” demek yanlış.
- `research/domain_alarm_replay.py` çapa sonrası ölçüm, dondurulmuş ATR ve sağdan sansür tanımlıyor. Bunlar değerli; fakat kendiliğinden dönem dışı performans doğrulaması değil.
- P6 karar belgesinin 22 seanslık geçmiş örneklemi ve parity ölçümü, ürünün kart yoğunluğunu ayarlamak için kanıt; gelecek kârlılık garantisi değil. 300 seride formül paritesi, aynı formülün doğru aktarıldığını test eder, stratejinin üstünlüğünü değil.
- Sonraki deney: politika ve eşiği sabitle, farklı bir ileri dönem topla; sembol/sektör/rejim/TF/kaynak bazında kapsam, örneklem, yanlış alarm, kaçırılan güçlü hareket, maksimum ters hareket ve net sonuçları ayrı raporla. Aynı veriyle sürekli filtre seçip aynı veriyle başarı ilan etme.
- Tek “isabet” yerine ürün amacı seç: anlamlı izleme noktası mı, işlem girişi mi, erken haber verme mi? Bu hedefler farklı ölçüm gerektiriyor.

## 7. Uygulanabilir yol haritası

| Sıra | Paket | Somut çıktı | Bitiş kapısı |
|---|---|---|---|
| 1 — hemen | Kalıcılık ve tek örnek kararı | Korunacak state envanteri; kalıcı DATA_DIR veya açık kayıp/kurtarma planı; yedek ve geri yükleme prosedürü | Kontrollü restart + disk kaybı provası ve kayıtlı sonuç |
| 2 — hemen | Teslim kanıtı ve hata politikası | Üç yolda ortak durum sözlüğü, olay/Telegram message ID eşlemesi, belirsiz gönderim inceleme yolu | Kabul-sonrası-timeout ve checkpoint-arası-ölüm testleri |
| 3 — hemen | Canlı doğrulama ve bağımsız izleme | Çalışan commit/ayar özeti; seans-farkında tarama/veri/kuyruk paneli | En az üç seans gözlem, kopukluk senaryolarında uyarı |
| 4 — sonraki | Gecikme ve kaynak bütçesi | Aşama süreleri; AI toplam bütçesi kararı; TV worker sınırı | p95 ve timeout yük testleri; komut yanıtları bozulmasın |
| 5 — sonraki | Sınırlı bakım refaktörü | Alarm olayı/teslim arayüzü; global bağların tek akışta azaltılması | Eski/yeni eşdeğerlik ve full CI |
| 6 — sonra | İleri dönem ölçüm | Sabit politika sürümüyle yeni dönem raporu ve maliyet/risk ayrımı | Yeterli ve raporlanmış örneklem; gelecek sızıntısı kontrolü |

**Şimdilik dokunma:** formasyon matematiği, kalite eşikleri, P6/P4 seçimi, Stabil ok/direnç kuralları ve deneysel stratejiler; yeni karşılaştırmalı kanıt olmadan değiştirme. Domain'leri tek bir skora zorla birleştirme. Repo seed'ini canlı state deposuna dönüştürme. Tarihsel araştırma manifestini deploy bağımlılıklarıyla rastgele eşitleme.

Takvim tahmini vermekten daha önemli sıra: **ilk üç paket kapanmadan yeni özellik dalgasına geçmemek.** Her paketi ayrı, geri alınabilir değişiklik olarak ilerlet.

## 8. Doğrulama sicili

Yerel interpreter **Python 3.11.2**, CI/deploy hedefi **3.12**. Yerel sonuçlar Render parity diye etiketlenmedi.

| Kontrol | Bu incelemedeki sonuç |
|---|---|
| `ruff check .` | Temiz; yapılandırılmış F/E9/S110 kapıları, kapsamlı güvenlik taraması değil |
| `git diff --check` | Temiz |
| `pip check` | Bozuk bağımlılık yok |
| `deploy_check.py --skip-network` | 62 tamam, 8 uyarı, 0 hata; anahtarlar boşaltılmış, ağ doğrulaması yok |
| `deploy_check.py --skip-network --grafik-test` | 67 tamam, 8 uyarı, 0 hata; AKBNK 4h PNG üretildi, Stabil direnç çizildi; fotoğraf gönderilmedi |
| `python -m scripts.politika_parite_kontrol --seri 300` | 300 karşılaştırma, 0 fark |
| `test_tarama_zamani.py` | 102/102 kontrol geçti |
| Bağımsız triangle/breakout/flag/pennant betikleri | Dördü de exit 0, tüm kontroller geçti |
| Tam `pytest -q` | **5.170 passed, 43 skipped — 831,89 saniye (13 dk 51 sn), exit 0.** Yerel çalışma ağacı; atlanan 43 vaka başarılı sayılmadı. |
| GitHub Actions | Taban `dddf38a` CI success, 27 Kasım 05:54 UTC başlangıçlı koşu; bu yerel değişiklikleri kapsamaz |
| Canlı Supabase | Salt-okunur metadata sorgusu: heartbeat/son tarama 30 Ekim, teslim kaydı da 30 Ekim. Read-only tasarım nedeniyle bu tek başına “bot durdu” kanıtı değil |
| Canlı Render / Telegram | Mevcut sürecin commit/env/sağlığı ve gerçek mesaj teslimi bu incelemede doğrulanmadı |

8 doktor uyarısı yok sayılmadı: yerel venv'deki **pip 23.0.1 ve setuptools 66.1.1** için eski sürüm uyarıları; Telegram token eksikliği için iki ayrı kontrol; AI sağlayıcı anahtarının yokluğu; Telegram hedefinin yokluğu; Supabase'in kapalı oluşu ve ağ kontrollerinin atlanması. Yerel build araçları güncel deploy kurulumuyla aynı değil; `scripts/install_deploy_dependencies.sh` pip 26.2 / setuptools 84.1.0 sabitliyor. Bu nedenle bu venv için “tam deploy ortamı” iddiası yok. Doktorun exit 0 dönmesi canlı hazırlık anlamına gelmez.

## 9. Sonuç

Bir sonraki çalışma başlığı **“güvenilir işletim paketi”** olmalı: kalıcı durum + açıklanabilir teslim + canlı sağlık kanıtı. Bu üçlü kapandığında, mevcut motor ve araştırma birikiminden daha sağlıklı sonuç almak mümkün. Şu anda en yüksek getirili iş yeni bir gösterge değil, **“bu veri ne kadar taze, bu olay neden seçildi ve hangi hedefe gerçekten ulaştı?” sorularına tek zincirde cevap verebilmek.**
