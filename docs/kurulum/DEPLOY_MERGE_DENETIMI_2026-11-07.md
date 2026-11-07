# Deploy ve merge öncesi kontrol — 7 Kasım 2026

## Kapsam ve karar sınırı

Bu kayıt repo, çevrimdışı testler ve erişilebilen GitHub Actions **metadata**
incelemesidir. Render Dashboard, gerçek servis ortamı, Telegram teslimi, Yahoo ve
canlı deploy bu oturumda doğrulanmamıştır. `main`e merge, mevcut Dashboard'ın
ayarına bağlı olarak **gerçek deploy'u otomatik başlatabilir**. `render.yaml`
sadece Blueprint ile yönetilen serviste ayar ister; başka bir yoldan oluşturulmuş
mevcut servisin Dashboard ayarını değiştirdiği varsayılmamalıdır. İkinci bot
servisi oluşturulmadı; manuel deploy hook'u çalıştırılmadı.

## Repo tarafında yapılan düzeltmeler

- Python 3.12 CI job zaman aşımı 20'den 45 dakikaya çıkarıldı. En son yerel tam
  Python 3.11 koşusu 24 dakika 46 saniye raporladı; tam regresyon ve duman testleri
  atlanmadan yavaş koşucuya da pay bırakıldı. Gerçek 3.12 sonucunu PR'ın **son
  head SHA'sına ait** GitHub Actions kontrolünden ayrıca doğrulayın.
- Otomatik grafik şalteri tutarsızdı: doktor `false`/`kapalı` değerlerini kapalı
  yorumlarken çalışan bildirim ve grafik yolu açık sayıyordu. Artık boş, `yok`,
  `0`, `false`, `off`, `no`, `none`, `hayir/hayır`, `kapali/kapalı` her iki
  yolda da kapalıdır; `/render` ve kurulum doktoru aynı kararı gösterir. `alarm`
  ve eski açık eş anlamları çalışır. Bilinmeyen değerler geriye uyumluluk için
  açık sayılır ve doktor uyarır; operasyonda `yok` veya `alarm` kullanın.
  `/grafik` komutu otomatik alarm şalterinden bağımsız kalır.
- Kurulum doktoru PNG'nin varlığını Stabil direnç hazır/çizilmiş durumuyla artık
  karıştırmaz. Eksik kaynak ve çizilmeyen katman uyarı olarak gösterilir; tek
  örnekte çizilmesi tüm semboller veya canlı teslim için garanti sayılmaz. CI,
  gerçek seed ve çevrimdışı doktorla PNG ve katman durumu üretimini de sınar.
- `.env.example`, `render.yaml` yorumları ve Render kılavuzunda DM/public kare
  kuralları, özetler, şalter ve belirsiz medya teslimi düzeltildi. `ADET` DM
  üst sınırıdır; public normal olayın ikinci karesi bu sınırdan bağımsızdır.
- Tarihsel araştırma manifestleri, kaynak hash'leri ve destek motoru korunmuştur.
  Raporların bağlantı verdiği ve doğrulayıcıların hash ile kontrol ettiği
  sıkıştırılmış araştırma çıktıları, mevcut depo geleneğine uygun olarak kanıt
  bütünlüğü için tutulur; `.arena_work/` geçici test/log dosyaları Git'e
  konulmaz.

## Bağımlılık ve güvenlik kontrolü

7 Kasım PyPI sürüm duyurularına göre araştırma replay'inin eski `requirements.txt`
pinlerinde `requests==2.32.3` (CVE-2024-47081 ve CVE-2026-25645),
`python-dotenv==1.0.1` (CVE-2026-28684) ve test aracı `pytest==8.3.2`
(CVE-2025-71176) için düzeltmeler yayınlanmıştı. Sömürü koşulları farklıdır:
requests `.netrc` duyurusu özel hazırlanmış URL ve kimlik bilgisi koşullarına
bağlıdır; diğer requests duyurusu `extract_zipped_paths`, dotenv duyurusu
`set_key`/`unset_key` çağrılarıyla ilgilidir ve repo kaynaklarında bu özel API
çağrıları bulunmamıştır. Pytest duyurusu ortak Unix geçici dizininde yerel
saldırgan riskidir; bunlar canlı sömürünün kanıtı değildir.

Tarihsel dosyayı/hash zincirini değiştirmeden canlı `requirements-deploy.txt`
dosyası eklendi: sırasıyla `requests==2.34.2`, `python-dotenv==1.2.4`,
`pytest==9.0.3`; diğer doğrudan paket pinleri aynı kaldı. Ortak kurucu
`bash scripts/install_deploy_dependencies.sh`, `pip==26.2` ve
`setuptools==84.1.0` kurup canlı pinleri yükler ve `pip check` çalıştırır.
Blueprint ve CI aynı kurucuyu kullanır; Termux dosyasına da requests ve dotenv
asgari düzeltilmiş sürümleri eklendi. Doktor eski paketleri uyarır ve ölçtüğü
ortamın yalnız yerel Python olduğunu belirtir.

Ayrı ve temiz yerel Python 3.11 ortamında kurulum ve `pip check` başarılı; o
ortamdaki 45 kurulu paket için PyPI sürüm JSON sorgusunda **0 duyuru / 0 sorgu
hatası** görüldü. Bu anlık, yalnız PyPI ve o ortama ait bir sonuçtur; tüm açıklar,
serbest transitif sürümlerin geleceği veya Python 3.12 Render ortamı için güvenlik
garantisi değildir. Render Dashboard eski build komutunu koruyorsa canlı servise
yeni pinler uygulanmaz. Kurucu dağıtılan commit'te olmadan build komutunu
çalıştırmak da build'i bozar; deploy geçişi bakım planıyla koordine edilmelidir.

## Yerel kanıt

- Önceki tam paket: Python 3.11.2, **4057 passed, 43 skipped**, exit 0; bu koşu
  son deploy düzeltmelerinden öncedir ve Python 3.12 CI'nın yerine geçmez.
- Önceki deploy/şalter, workflow, grafik, doktor, `/render` ve gerçek arşivli
  teslim entegrasyon testleri: **231 passed**. Bunlar bağımlılık güvenlik
  güncellemesinden önceydi; güncel pinlerle CI sonucunu ayrıca izleyin.
- Yeni temiz ortamda deploy, başlangıç/kapanış, grafik, Telegram, bildirim ve
  Supabase odaklı paket: **612 passed, 1 skipped**. Son doktor/kurucu değişikliği
  sonrasında odaklı dosyalar yeniden **95 passed**; kurucu başarısız adımda
  duruyor, yorum satırı paket sayılmıyor. Ruff ve `git diff --check` temiz.
- Yeni pinlerle çevrimdışı grafik doktoru **0 hata**, health dumanı ve dört
  tarihsel araştırma doğrulayıcısı da başarılı; canlı erişim sınırı değişmedi.
- Aynı CI kabuğuyla gerçek entrypoint dumanı: `/health` 200 ve beklenen sahte
  commit, `/ready` 503 ve `startup_complete=false`, kapalı `/test` ve webhook
  404. Smoke modunda tarama/sağlayıcı/Telegram döngüleri özellikle başlamaz;
  bu, botun canlı başlangıcını veya teslimini doğrulamaz.
- Çevrimdışı doktor, yalnız kopyalanmış AKBNK seed verisi ve `TELEGRAM_GRAFIK=false`
  ile kare üretti; native günlük seed eksik olduğu için direnç katmanını açıkça
  `UNAVAILABLE / missing_source` olarak uyardı. Fotoğraf veya ağ isteği yapılmadı.
- `test_tarama_zamani.py`: 102/102; üçgen, kırılım, bayrak ve flama bağımsız
  regresyon scriptleri geçti. Dört tarihsel araştırma doğrulayıcısı, kaynak,
  arşiv ve çıktı hash denetimleriyle yeniden başarılı oldu.

## GitHub keep-alive: sorun sürüyor

7 Kasım'daki salt-okunur örneklemde son 20 schedule başlangıcı 2–7 Kasım arasına
sayıldı. **19/19** aralık 15 dakikadan uzun; medyan **391,7 dk**, maksimum
**519,2 dk**. Tam kapsanan 5 gecenin 5'inde 02:00–02:20 İstanbul penceresinde
başlangıç yoktu. Son 5 job'da GET adımı **3 success / 2 skipped**; yeşil job,
ping hedefini veya botun hazır olduğunu kanıtlamaz. Örnek eski workflow sürümü
ve özel değişkenleri içerebilir. GitHub planlayıcı davranışı repo değişikliğiyle
garantilenemez: ayrı ve gerçekten gözlemlenen izleme/uyandırma veya uygun sürekli
çalışan plan gerekir. `python scripts/keepalive_audit.py --repo keremtulu44/Formation-Bot`
metadata'yı yeniden ölçer, Render'a ping atmaz.

## Canlıda henüz çözülmemiş operasyonel riskler

1. **Çift sender / rolling deploy:** Dağıtık liderlik veya fencing yoktur. Tek
   ölçekli web servis bile deploy sırasında eski/yeni süreçleri örtüştürebilir;
   mesajlar, webhook ve yerel state yarışabilir. Gerçek tek sender gerekiyorsa
   yetkili operatörün bakım penceresi ve eski sender'ın durdurulması veya ayrıca
   uygulanmış güvenilir bir liderlik mekanizması gerekir.
2. **Geçici disk:** Render Free'deki varsayılan `DATA_DIR` yeniden başlatmada
   kaybolabilir; Supabase yeni durumları yedeklemez. Kuyruk, gönderim mühürleri,
   sayaçlar ve mumlar için uygun izinli yedek ve gerekiyorsa desteklenen kalıcı
   disk ayrıca hazırlanmalıdır. Ücret/plan değişikliği yapılmadı.
3. **Gerçek ayarlar bilinmiyor:** Dashboard branch, Auto-Deploy/check kapısı,
   env adları, hedef izinleri, bağımsız monitör ve başka bir bot örneği yetkili
   panelden doğrulanmalı. GitHub main protection API erişimi de 403 döndü; branch
   protection kuralları bu denetimde görülemedi.

## Yetkili operatör için kontrol sırası

Ayrıntılı prosedür ve rollback: [önceki operasyon denetimi](DEPLOY_CANLI_ONCESI_2026-11-06.md)
ve [Render kılavuzu](RENDER_DEPLOY.md).

1. Son PR head SHA'sında Python 3.12 CI'nın tamamını ve `main`e göre güncelliği
   doğrulayın. Dashboard'da mevcut servisin build/start/branch/auto-deploy
   ayarını, tek sender geçişini ve gizli değerleri paylaşmadan env adlarını
   kontrol edin. `DATA_DIR` state'inin uygun izinli yedeğini alın.
2. Merge/deploy sonrasında Render Deploys ve loglardan sonucun tamamlandığını
   kontrol edin; `/health` commit alanını **merge commit'i** ile karşılaştırın.
   `/health` 200 yalnız canlılıktır, `/ready` 200 de veri ve Telegram teslimi
   garantisi değildir. Hook'un kabul yanıtı deploy tamamlandı demek değildir.
3. Gerçek hedefte yalnız yetkiyle `deploy_check.py --url ...` ve gerekirse
   `--grafik-test` çalıştırın; `--send-test-message` gerçekten mesaj/fotoğraf
   yollar. İlk tarama, kaynak tazeliği, hedef fotoğraf izni, kuyruk, belirsiz
   teslim ve çift sender belirtilerini izleyin; timeout'u körlemesine tekrarlamayın.
4. Bağımsız keep-alive/uyandırma aralığını gözlemleyin; yalnız `*/5` cron veya
   başarılı job sonucu yeterli kanıt değildir.
