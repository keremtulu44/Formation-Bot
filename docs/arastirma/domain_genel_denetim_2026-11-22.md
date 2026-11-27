# Domain, veri, alarm ve grafik denetimi — 22 Kasım 2026

## 1. Kapsam ve kanıt kuralları

Bu rapor Market Structure (MS), Volume Participation, FVG/Engulfing, Order Block (OB), Stabil destek/direnç ve formasyonun yanı sıra ortak giriş, durum, zamanlama, grafik ve bildirim akışını inceler. Bulgular kaynak kodu, hedefli testler ve gerektiğinde yapay, tekrarlanabilir verilerle sınırlıdır. Üretim verisi, OANDA barları, kullanıcıdaki 20 Kasım grafiğinin ham OHLCV'si ve sağlayıcının gerçek seans takvimi mevcut değildir. **Test geçmesi matematiksel doğruluk veya Pine ile her durumda eşitlik kanıtı değildir.** Bu çalışma her satırın ve tüm piyasa durumlarının eksiksiz doğrulandığı anlamına gelmez.

Kanıt düzeyleri: **tekrarlandı** = kod yolu/deney ile davranış gösterildi; **tasarım/kaynak farkı** = kaynaklardan görülüyor, kullanıcıdaki olaya etkisi gösterilmedi; **risk** = etkisi mantıksal, canlıda gerçekleşmesi/sıklığı kanıtlanmadı. Öncelikler olası etkiye göre değerlendirmedir, olay sıklığı ölçümü değildir.

## 2. Tekrarlanan ve bu çalışma alanında düzeltilen sorunlar

### P1 — Yeni domain alarmı kayan pencerede kalıcı olarak susabiliyordu

- `bot/domain_alarm_service.py`: adayın `bar_index` değeri `len(frame)-1`; cooldown daha önce sadece son gönderilen indeksin farkına bakıyordu. `data/seed_cache.py` sınırlı uzunlukta FIFO deque kullanıyor (1s 360, günlük 500). Pencere doluyken yeni mumlar gelse de son indeks sabit kalabilir. Örneğin hem eski hem yeni adayın indeksi 39 olduğunda fark 0 kalır; altı yeni mum geçse de cooldown açılmaz.
- Düzeltme: aday, yakın geçmişteki tamamlanmış mum etiketlerini de taşır; önceki gönderimden sonraki **farklı gözlemlenmiş mumlar** sayılır. Yetersiz/bozuk/tutarsız geçmişte yeni yolda güvenli biçimde susar. Tarihçesiz eski çağırıcılar için indeks yedeği korunmuştur.
- Testler: `test_cooldown_rolling_pencerede_gercek_kapanmis_mumlari_sayar` ve `test_rolling_cooldown_kalici_state_ile_tekrar_gonderir`: 40 mumluk kayan pencerede indeks daima 39; 1–5 yeni mumda susar, 6. mumda açılır; bozuk ve yetersiz tarihçe ve kalıcı state üzerinden teslim kontrol edilir. Bu yeni domain kanalıdır; ayrı Stabil alarmı farklı cooldown kodu kullanır.
- Sınır: mevcut frame'in gerçekten tamamlanmış ve eksiksiz mumlar içerdiği veri katmanının sorumluluğundadır. Bilinmeyen oturumları saat farkından üretmiyoruz.

### P1 — Bilinmeyen/açık mum bayrakları teyitli mum gibi işlenebiliyordu

- MS, OB ve FVG'de `bool(float('nan'))` doğru kabul edildi; `pd.NA` belirsizliği bazı yollarda hata üretir. Volume'da `is False` kimlik karşılaştırması `numpy.bool_(False)`, `None`, `NaN`, `pd.NA` ve `"False"` değerlerini reddetmiyordu. Doğrudan `update` deneyinde `numpy.bool_(False)` olan hacim mumu satıra eklendi ve `is_confirmed=True` sonuç üretti. Standart pandas `to_dict` normal boolean sütununu çoğu zaman Python `False` yaptığından, bu gözlem her normal üretim mumu için meydana geliyor demek değildir.
- Düzeltme: `domain_engines/bar_quality.py` ortak yorumlayıcısı; sütun yoksa mevcut varsayılan korunur, açıkça bilinmeyen/geçersiz/false değerler onay sayılmaz. MS ve OB durum ilerletmez; FVG açık mumda durur, eksik mumda kendi kaynak boşluğu işaretini korur; Volume üç katmanda aynı kontrolü yapar. `"true"` kabul edilir, `"False"` reddedilir.
- Test: `test_unknown_or_false_completion_flags_do_not_advance_confirmed_domains` ve `test_volume_explicit_unclosed_or_unknown_flags_never_advance`, her iki bayrak ve çeşitli temsil türleri için. Bu düzeltme Stabil'in ayrı DataFrame temizleme yolunu kapsamaz.

### P2 — Aynı timestamp/OHLCV, farklı kalite bayrağı olan satırlar sessizce tekleştiriliyordu

- `domain_engines/incremental.py`: OB/FVG tekrar tespitinde eskiden yalnız OHLCV karşılaştırılıyordu. Aynı mumun önce `is_closed=True`, sonra `False` gelen iki kopyası öncesinde `cold_full_replay`, tek işlenmiş bar ve OB `OK` üretirken, yerel motorun iki satırlı tam replay'i `INCOMPLETE_BAR` üretir. Dolayısıyla kapanış/kalite bilgisi kaybolabiliyordu.
- Düzeltme: aynı zaman damgalı kayıtların tüm giriş sütunları karşılaştırılır; çelişkide mevcut `full_replay_conflicting_timestamp` yolu çalışır ve incremental güveni kapatılır. Çelişkili kayıtlar değiştirilmeden replay edilir; bu, çelişkinin kaynağını çözmek veya tüm domainlere ortak tekilleştirme yapmak değildir.
- Test: `test_duplicate_ohlcv_with_conflicting_quality_flags_is_replayed`: OB/FVG ve her iki bayrak, native tam replay çıktısı ve sonraki güvenli toparlanma.

### P1/P2 — Eski donmuş OB/FVG çıktısı yeni alarm sebebi olabiliyordu

- OB ve FVG eksik/açık mumda önceki export'u bilerek dondurur. Yeni domain kanalındaki `_bolge_sebepleri` eskiden kaliteyi kontrol etmeden bu bölgeyi veya FVG reaksiyonunu tetikleyici sayıyordu.
- Düzeltme: bu alarm yolunda açık kalite mevcutsa yalnız `OK` kabul edilir; `SOURCE_GAP`, `INCOMPLETE_BAR`, `WARMUP` vb. durumlar yeni OB/FVG tetikleyicisi olmaz. Kalite alanı bulunmayan eski/harici sonuçlarla mevcut uyumluluk korunur. Diğer bağımsız tetikleyiciler etkilenmez.
- Test: `test_kalitesi_dusuk_donmus_bolge_alarm_tetiklemez`. Kart ve grafiklerde donmuş verinin sunumu ayrıca aşağıdaki açık bulgudur; bu düzeltme tüm gösterim yollarını değiştirmez.

## 3. Açık, tekrarlanmış veya doğrudan kodla doğrulanmış bulgular

### P1 — Ortak kapanış/fiyat kaynağı farklılığı: makro

`data/replay.py::tamamlanmis_mumlar` sembol parametresi almıyor ve BIST kapanış kurallarını kullanıyor; `bot/scan.py::_completed_domain_frames` aynı yolu domain girişinde kullanıyor. Sentetik XAUUSD günlük örneğinde Cuma 18:31 İstanbul anında günlük mum kapalı sayıldı. Bunun OANDA'nın o tarihteki gerçek kapanışına uyup uymadığı **ölçülmedi**. Kod, makro günlük grafikte gerçek kapanışın doğrulanmadığını artık uyarıyor; hesaplama düzeltildi demek değildir.

`config.py` XAUUSD için Yahoo spot `XAUUSD=X`, spot yoksa COMEX vadeli `GC=F` fallback'i tanımlar; TV sağlayıcısı OANDA'dır. `data/seed_cache.py` mumları timestamp ile birleştirir, JSON cache seri başına sağlayıcı/spot-vadeli provenansını korumaz. Kod kaynaklarının farklılığı ve metadata eksikliği doğrulandı; belirli bir kayıtta gerçekten fallback kullanıldığı veya iki kaynağın karıştığı gösterilmedi. Bu durum tüm domainlerin fiyat, hacim, ATR, zamanlama ve formasyon girdisine yansıyabilir. `MAKRO_ALARM` varsayılan olarak kapalıdır; `/grafik` için bu farklıdır.

**Öneri:** sağlayıcı/sembol/tür/seans/timezone/fetch zamanı bar provenansı; spot-vadeli karışımını engelleyen versiyonlu cache; sağlayıcıya özgü kapanış ve DST/hafta sonu/yarım gün testleri. Bunlar gerçek sağlayıcı sözleşmesi doğrulanmadan varsayımla değiştirilmemeli.

### P1/P2 — Aynı timestamp domainler arasında farklı sayıda işleniyor

Tekrarlı iki aynı OHLCV satırı ile deney: MS `2`, Volume `2`, incremental OB `1`, FVG `1` bar işledi. OB/FVG aynı girdiyi tekleştirirken `to_domain_frame` MS ve Volume için satırları koruyor. Bu, pencere uzunluğu, pivot, ATR, RVOL ve bar indekslerini ayrıştırabilir. Çelişkili satırlarda OB/FVG halen iki satırı tam replay ediyor; çelişkili verinin anlamını çözmüyor. Gerçek cache'lerde bu durumun sıklığı ölçülmedi.

**Öneri:** runner girişinde tek, açık ve domainler arası tutarlı politika: birebir aynı kayıtları tekleştirme; çelişkide veriyi uyarıyla reddetme/karantinaya alma; bütün ham veri ve kalite bayrakları korunarak replay/indeks beklentilerinin test edilmesi. Bu davranış değişikliği bu turda bütün domainlere zorlanmadı.

### P1/P2 — Stabil destek hazırlığında bozuk mum sessizce atlanabiliyor

`domain_engines/stabil/runtime.py::prepare_causal_ohlcv` eksik OHLC olan satırları `dropna` ile çıkarır, kalan satırları komşu yapar ve yine `None` hata döndürebilir. Üç günlük örnekte ortadaki günün `high=NaN` olması 3→2 satır üretti ve hata `None` idi. Bu, kaynak boşluğunun destek/trend hesabına iletilmeden geçmişteki komşuluğun değişmesine yol açabilir; belirli alarm veya yanlış destek seviyesi bu deneyde gösterilmedi. Direnç köprüsünde daha katı fail-closed hazırlık bulunduğu için destek ve direnç davranışları aynı değildir. Stabil'in `.astype(bool)` bayrak dönüşümü de `"False"` gibi stringlerde şaşırtıcı olabilir; ortak flag düzeltmesi bu yolu kapsamıyor.

**Öneri:** cutoff öncesi, gerçekten kullanılması gereken bozuk/çelişkili mumlarda günlük ve hedef TF için ayrı açık kalite durumu; eksik işlem günü ile piyasa tatilinin ayırt edilmesi; gelecekteki/henüz kapanmamış bozuk satırların tarihi sonuçları etkilememesi. Geçmiş veri politikası ve alarm etkisi geniş olduğundan otomatik değiştirilmedi.

### P2 — Reset ile devam eden tarama arasında yarış

`domain_engines/runner.py::reset_incremental_domain_states` state registry ve latest cache'ini temizliyor, ama aynı seri üzerinde süren `run_domain_engines` işleminin tamamını beklemiyor. `threading.Event` ile MS yürütmesi durdurulup reset uygulandı, reset sonrası latest boştu; eski tarama devam ettiğinde hem latest hem state yeniden doldu. Bu, eşzamanlılık senaryosunda gerçekleşebilir; canlı zamanlayıcıda çakışma sıklığı veya kullanıcıya etkisi kanıtlanmadı. `bot/summary.py` gece veri yenilemesinden sonra reset çağırır.

Yalnız kilit eklemek, resetten önce okunmuş eski frame'in reset sonrasında tekrar işlenmesini tek başına çözmeyebilir. **Öneri:** veri nesli/generation kimliği ile fetch-snapshot, state ve publish işlemini bağlama; atomik değiştirme ve eşzamanlılık testleri. Bu turda kör kilit düzeltmesi yapılmadı.

### P2 — Donmuş domain sonuçları kart/grafik bağlamında hâlâ görünebilir

Alarm tetikleyicisi düzeltildi; fakat `notification_context.py::_usable_export` hata/skip kontrolü yapar, OB/FVG kalite durumunu genel olarak kontrol etmez. `grafik/geometry.py` kayıtları kaliteye göre genel bir kapı uygulamadan çizer. Motorlar açık/eksik mumda önceki export veya kayıtları korudukları için, bu yollar eski bölgeyi gösterme potansiyeli taşır. Belirli bir üretim kartında yanlış gösterim yakalanmadı. Eski bölgeyi gizleme ile açıkça 'son teyitli ama güncel değil' etiketleme arasındaki ürün politikası belirlenmeli; tüm kart/grafik yollarına sessiz bir filtre uygulanmadı.

## 4. Domain bazında inceleme notları

### Market Structure

- `domain_engines/market_structure/` pivot, iç/dış yapı ve BOS/CHoCH olaylarını tam replay ile üretir. Runner bağımsız kopya verir; hata diğer domainlere ayrı sonuç olarak yansır.
- Bayrak belirsizliği giderildi; timestamp tekilleştirme ayrışması ve makro kapanış riski devam ediyor. Alarmlarda `_bos_ve_choch_sebepleri` teyit/aktiflik ve son iki bar filtrelerini kullanır. Frame'den atlanan/tekrarlanan barlar bu indeks filtresini etkileyebilir.
- `test_ms_kilitli_referans.py` ve domain entegrasyon testleri yararlı referanslardır; her profil, gerçek OANDA feed'i veya tüm pivot senaryoları için Pine paritesi değildir.

### Volume Participation

- Core → lifecycle → final katmanları ve RVOL/hacim kullanılabilirliği incelendi. Eksik hacim, az sayıda dolu hacim, düşük geçmiş ve sıfır hacim 'sinyal yok' ile aynı şey değildir; XAUUSD yerel örnek hacmi sıfırdı.
- Boolean/NA sorunu düzeltildi. Yeni domain alarmında motor RVOL yoksa yerel 20 bar ortalaması fallback'i vardır; uygun olmayan hacim oranı için `VERI_SUPHE` işareti üretilebilir. Bu yerel fallback, motor metriğinin veya OANDA tick volume'unun birebir eşdeğeri olduğu anlamına gelmez.
- Tam replay, sınırlı tarihçe ve yinelenen barlar EMA/RVOL ile yaşam döngüsüne etki edebilir; çeşitli veri kaynakları ve gerçek hacim türleriyle parite ayrıca ölçülmeli.

### FVG / Engulfing

- Kaynak FVG 2s/4s/1g destekler; runner 1s'de atlar ve 2s'yi varsayılan kapalı tutup yalnız açık opt-in ile çalıştırır. Dolayısıyla 2s'de bölge olmaması tek başına hata değildir.
- Artımlı FVG sol kenar ATR/RMA başlangıcı nedeniyle kayan pencerelerde ara pencereleri tam replay eder. Gap durumunda detector zincirini işaretler, export önceki değerde kalabilir. Eksik bayrak ve yanlış duplicate sorunu düzeltildi; alarm tetikleyicisi kaliteyle kapatıldı.
- `test_domain_incremental_parity.py` cached/uncached referansı, catch-up, revizyon, kapanış ve restart senaryolarını karşılaştırır. Sağlayıcının hiç göndermediği gerçek barların tespiti ve farklı oturumların FVG üzerindeki etkisi ayrıca gereklidir.

### Order Block

- Aktif kalan bölgeye mesafe, dolum ve kaynak bar yaşam döngüsü ile incremental pencere kaydırma incelendi. 250 rastgele OHLC serisinde tek bar kayan 100 barlık pencerenin native kayıt/export/snapshot karşılaştırmasında fark gözlenmedi; bu bir ispat veya tüm durumların taranması değildir.
- `_is_better` açıklamasında minimum tick içindeki eşitlikte yeninin kazanacağı yazıyor; kod ise mesafe daha küçükse önce doğrudan kazanıyor. Kaynak sözleşmesi `domain_engines/04_order_block.txt` aynı kodu içeriyor: dolayısıyla **yorum/kod sözleşmesi belirsizliği**, doğrudan Pine'dan sapma kanıtı değil. Bu turda matematik değiştirilmedi. Minimum tick varsayılanı 0.01, enstrümana göre doğrulanmalı.
- Bayraklar ve duplicate düzeltmeleri ile kalite kapısı yukarıdadır.

### Stabil destek ve direnç

- Destek/trend MTF girdileri kapanış zamanına göre hizalanır; haftalık tamamlama ve tek geçişli geçmiş için prefix testleri mevcuttur. Yabancı/makro enstrümanlarda sertifikalı kapanış zamanı yoksa Stabil varsayılan olarak güvenli şekilde hesap yapmaz (`foreign_market_requires_certified_close_times`); bu da çizim/sinyal yokluğunun açıklaması olabilir, ancak XAUUSD formasyon uyuşmazlığının kanıtlanmış nedeni değildir.
- Bozuk satır düşürme riski §3'tedir. Direnç `chart_bridge` daha katı politika uygular, bu iki yolun farklılığını tasarım testleriyle açıklığa kavuşturmak gerekir.
- Önceki düzeltme: Stabil alarm çizimine tam formasyon çapaları taşındı; ALARK 4s deneyinde sade sözlük yatay, tam aday eğimli çizgiler üretmişti. İlgili grafik/entegrasyon testleri eklendi. Bu XAUUSD olayının doğrudan kanıtı değildir.

### Formasyon motoru ve grafik

- Önceki çalışma: çizim yolunda mevcut adayın kaliteyi ikinci kez geçme koşulu kaldırıldı; terminal adayların grafik yaşamı için tamamlanmış aday ve dört bar ghost davranışı düzeltildi. Alarm kalite filtresi korunur. Sentetik `RETEST_BEKLENIYOR` grafiği test edildi.
- `_inside_confirmed` TF bazlı çoklu kapanış/derinlik ve başarısızlık sonrası bekleme kullanır; paylaşılan Pine ile davranış ayrımı olabilir. Paylaşılan ekran görüntüsünün tek başına kök nedeni olarak gösterilmedi.
- Yerel XAUUSD arşivi 2026-10-28'de bitiyor; Kasım ekran görüntüsünün girdisi değildir. Geçmiş arşivde görülen tamamlanmış yükselen üçgen, kullanıcının alçalan üçgeniyle eşleştirilemez. Aynı sağlayıcı, seans, mum, ayar ve barlar olmadan birebir skor/tespit garantisi verilemez.

## 5. Diğer entegrasyon sınırları

- Runner MS/Volume tam replay, OB/FVG seri+TF için state kullanır; `isolated=True` grafik/replay yolunu canlı state'ten ayırır. Farklı konfigürasyonlar state değişimine neden olabilir. Çıktıların bağımsız olması ortak veri sorunlarından bağımsız oldukları anlamına gelmez.
- `bot/scan.py` domain sonuçlarını tarama turunda cache'ler ve Stabil bundle ekler. Domain exception'ları diğerlerini durdurmamak için yakalanır. Bu operasyonel dayanıklılık sağlarken kısmi sonuçların log/ölçüm üzerinden izlenmesini gerektirir.
- Yeni domain kanalı Stabil mesafesi ve ayrı BOS/formasyon/OB/FVG/hacim sebeplerini kullanır; ürün politikası ve teslim/cooldown önceki alarm kanallarından ayrıdır. Zamanlama tazelik kapıları yanlış seans modelini tek başına düzeltmez.
- İlgili testler yapay ve yerel veriyle yürütüldü; Telegram'a gerçek gönderim, canlı sağlayıcı çağrısı, deploy ve üretim doğrulaması yapılmadı.

## 6. Öncelikli devam planı

1. Girdi sözleşmesini standardize et: sağlayıcı+enstrüman+oturum kimliği, kapanış sertifikası, OHLCV tutarlılığı, açık/eksik flag türleri, tekrar/çatışma, eksik gerçek seanslar.
2. Ortak kaliteyi domain sonucu, alarm, grafik ve kartlara uçtan uca taşı; 'eski teyitli', 'hesaplanamıyor' ve 'gerçekten yok' durumlarını ayır.
3. Cache yenileme/tarama yarışını generation kimliği ile çöz; farklı TF'lerin aynı gözlem anı ve veri nesliyle ilişkisini test et.
4. Her domain için çok sayıda gerçek veriyle prefix-causality, her barda replay/incremental, eksik/revize/tekrarlı bar ve restart testleri; Pine referansı ile aynı OHLCV ve aynı parametrelerde karşılaştırma.
5. Özellikle XAUUSD için OANDA'nın tarihsel günlük bar ve oturum kuralları elde edildiğinde Yahoo spot/vadeli ile ayrı ayrı karşılaştır; bar ve aday bazında farkları belgeleyip ondan sonra düzeltme tasarla.

## 7. Test notu

- Son domain/entegrasyon seçkisi: **531 geçti, 1 atlandı** (28 test dosyası; 274,92 sn).
- İlk tam paket: **4777 geçti, 43 atlandı, 2 başarısız**. İki başarısızlık, önceki grafik testlerindeki monkeypatch hedefinin statik kontrolünün `patterns.lifecycle.lifecycle.ArgentEngine` olarak yanlış çözülmesiydi. Test import takma adı düzeltildi; `test_patch_yuzeyi.py` ile ilgili grafik testlerinin yeniden çalıştırılması **1283 geçti** sonucu verdi.
- Son kod ve test ağacıyla tam paket yeniden çalıştırıldı: **4851 geçti, 43 atlandı** (744,21 sn). İlk tam paketin sonucu son ağacın kanıtı değildir; yukarıdaki ikinci sonuç geçerlidir.
- Daha önceki 456 test, sonraki değişikliklerin tamamının doğrulaması sayılmamalıdır. Çalışma alanı değişiklikleri commit edilmedi ve canlı ortama dağıtılmadı.
