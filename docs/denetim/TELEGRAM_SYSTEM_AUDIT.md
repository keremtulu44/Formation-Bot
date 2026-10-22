# Telegram ve sistem bildirim yaşam döngüsü denetimi

**Tarih:** 8 Ekim 2026 (Europe/Istanbul)  
**Kapsam:** Telegram bildirim politikası ve teslimatı, Formation lifecycle, digest/watch buffer, domain context, restart/persistence, sembol hata izolasyonu ve 100 sembole ölçek tahmini.  
**Önemli sınır:** Hiçbir gerçek Telegram mesajı gönderilmedi. Yerel replay yalnızca cache ve mock/policy hesabıdır; Telegram teslimatı değildir.

## 1. Yönetici özeti

Denetimde üç kanıtlı kullanıcı etkisi düzeltildi:

1. **Aynı Formation olayının dört saat sonra tekrar DM olması:** Cooldown anahtarı `(sembol, formasyon, timeframe, state)` idi. Aynı lifecycle olayı state’te kaldıkça dört saat sonunda yeniden gönderilebiliyordu. Anahtara lifecycle’ın kendi event type’ı ve native event timestamp’i (yoksa bar index’i) eklendi. Aynı olay artık cooldown geçse de tekrar açılmıyor; yeni bir lifecycle olayı ayrı kimlik alıyor.
2. **DM’ye özel watch context’in public kanala çıkabilmesi:** Eski public formatter `watch_context` alanını da yazıyordu ve `send()` public metni aynı ham payload’dan üretiyordu. Public payload’dan `watch_context`, `dm_context` ve dahili event ID açıkça çıkarılıyor.
3. **DM hatasının public post’u bastırması:** Public gönderim yalnızca DM HTTP isteği başarılı olunca deneniyordu. DM ve kanal artık ayrı cooldown/delivery outcome kullanıyor; DM reddedilse veya cooldown’da olsa bile uygun public post denenebilir. Kanal başarısızlığı da başarılı DM’yi geri almaz.

Ayrıca cooldown ve Telegram günlük/saatlik cap JSON dosyaları geçici dosyaya yazılıp `os.replace` ile atomik değiştiriliyor. Domain zone’larının **mesajdaki gösterimi** iki ondalık haneye sabitlendi; domain nesnesindeki ham sayılar değiştirilmedi.

28 cache’li sembol × 360 scan zamanı replay’inde eski politika **477 olası DM** üretti; event kimlikli politika **310** üretti. Fark **167 tekrar gönderimin** önlenmesi; eski politikada 118 olay anahtarı birden çok kez gönderilmiş, en çok 4 kez. Yeni politikada aynı event ID için tekrar yoktu; 1.293 immediate-state gözleminde event ID eksikliği görülmedi. Bu, başarılı Telegram teslimatı sayısı değil, yerel policy replay’idir.

**Kalan en önemli riskler:** başarısız immediate DM için kalıcı outbox/retry yok; close digest/scheduled reports gönderim işaretleri süreç belleğinde; scan içinde mesajlar gönderildikten sonra başka sembolde hata gelirse snapshot tüm scan için başarısız sayılır ama önceki DM’ler geri alınamaz. Bunları otomatik olarak “bug” diye değiştirmedim; retry/digest idempotency tasarımı ve duplicate-vs-loss tercihi ayrıca kararlaştırılmalı.

## 2. Gerçek bildirim akışı

`scan_all_stocks` akışı:

1. 1H veriyi pacer ile çeker veya cache’i tazelik kurallarına göre kullanır; split/stale filtreleri uygulanır.
2. 1H/2H/4H/1D frame’lerini üretir ve tamamlanmamış barları çıkarır.
3. Her timeframe’de Formation lifecycle’ını tarar. Kalite kapısı timeframe’e göre 1H 80, 2H 78, 4H 75, 1D 70’tir.
4. Altı düşük öncelikli state `DeferredAlertBuffer`’da slot başına son durum olarak tutulur. Dört immediate state için alert payload hazırlanır.
5. Her sembolün tamamlanmış frame’leri domain runner’a verilir. Context yalnızca bu sembolün **aynı scan’de dönen** domain sonuçlarından seçilir; stale runner cache fallback’i kullanılmaz. Domain/context hatası Formation alert’ini düşürmemeli, context boş kalmalıdır.
6. DM formatter; Formation state, kalite/yaş/temas bilgisi, bilinen retest/kırılım ayrıntısı, en çok üç watch adayı ve varsa domain context üretir.
7. Notifier cooldown/cap’i uygular, DM’yi gönderir, ardından uygun public kanalı ayrı ele alır. DM başarısında watch adayları “raporlandı” olarak işaretlenir.
8. Sembol biter; bir sembol istisnası loglanıp sonraki sembole geçilir. Tüm evren tamamlanırsa LiveState atomik olarak yayımlanır; eksik/hatalı scan’de son başarılı snapshot korunur.

`/tara` isteği ve 20:00 gün sonu analizi `send_alerts=False` ile çalışır. Bunların kullanıcıya dönüşü scan içi Formation alarmı değil, komut cevabı/ayrı özet mesajıdır.

## 3. State politikası

| Lifecycle state | Kod politikası | Kullanıcı kanalı / katkısı |
|---|---|---|
| `KIRILIM_TEYITLI` | Immediate | DM; teyitli kırılım ve bilinen yön/seviye. `PUBLIC_STATES` içine eklenmedikçe public değil. |
| `RETEST_BASARILI` | Immediate | DM; başarılı retest. Varsayılan public state ve kalite ≥80 ise ayrıca public post. |
| `FORMASYON_TAMAMLANDI` | Immediate | DM; tamamlanma/retest bilgisi. Varsayılan public state ve kalite ≥80 ise ayrıca public post. |
| `BASARISIZ_KIRILIM` | Immediate | DM; state’in başarısız kırılım anlamı. Varsayılan public listede değil. |
| `SIKISMA_GUCLENIYOR` | Watch/deferred | Gün içi buffer; doğrudan alarm değil. Kalite kapısı sonrası digest’e veya en fazla üç kayıt olarak bir immediate DM’nin DM-only bağlamına girebilir. |
| `KIRILIM_HAZIRLIGI` | Watch/deferred | Kapanış digest’i; her scan’de tekrarlı immediate mesaj değil. |
| `KIRILIM_ADAYI` | Watch/deferred | Kapanış digest’i. Notifier’ın “kritik” listesindeki adı, ana alert-state listesinde immediate olduğu anlamına gelmiyor. |
| `KIRILIM_DENEMESI` | Watch/deferred | Kapanış digest’i. |
| `RETEST_BEKLENIYOR` | Watch/deferred | Kapanış digest’i; yeni bilgi varsa state değişimiyle güncellenir. |
| `RETEST_EDILIYOR` | Watch/deferred | Kapanış digest’i. |
| Diğer state’ler | Immediate/deferred listesinde değil | Canlı liste/özet görünürlüğü olabilir; Telegram alert’i olduğu varsayılmamalı. |

Digest buffer aynı sembol/timeframe slotunda eski pending adayı yeniler veya kaldırır; en yüksek kaliteye göre en fazla 12 kayıt döndürür. Başarılı immediate DM’de mesajın içine alınan watch kayıtları aynı gün digest’te tekrar edilmemek üzere işaretlenir. Günlük özet formasyonu en fazla 10, watch digest’i en fazla 12 kayıtla sınırlar; bu, her gerçek state’i ayrı Telegram mesajı yapmaz.

## 4. Spam ve dedup ölçümü

**Replay kapsamı:** `bot_data/*.pkl` içindeki 28 sembol, sembol başına 360 adet 1H bar; scan zamanları 3 Ağustos–25 Eylül 2026. Günlük frame ayrı günlük cache olmadığı için 1H veriden resample edildi. Aynı dört immediate state, kalite eşikleri ve dört saatlik cooldown politikası kullanıldı. Yerel, ağsız simülasyondur.

| Metrik | Önce | Event ID sonrası | Not |
|---|---:|---:|---|
| DM policy kabulü | 477 | 310 | Olası/gönderilebilir mesaj; gerçek teslimat değil |
| Aynı lifecycle event için tekrar | 118 event anahtarı | 0 | Önce 167 fazla tekrar; tek event en çok 4 kez |
| Eksik stable event ID | — | 0 / 1.293 immediate-state gözlemi | Bu cache replay’inde |
| En yüksek saatlik burst | 9 | 9 | Default hourly cap 20; bu replay’de cap’e ulaşmadı |
| En yüksek günlük sayı | 28 | 22 | Default daily cap 120; bu replay’de cap’e ulaşmadı |
| Public-eligible policy post’u | 199 | 111 | Yalnızca `FORMASYON_TAMAMLANDI`/`RETEST_BASARILI`, kalite ≥80; teslimat değil |
| Public’te tekrarlanan event | 67 event, 88 fazla post | 0 | Başarılı DM varsayımıyla eski/yeni policy karşılaştırması |

DM düşüşü 167/477, yaklaşık **%35**. Public sayıları aynı replay’de kod filtresine göre uygun olan postlardır; kanal konfigürasyonu ve Telegram cevabı ölçülmedi.

Bu replay, “günlük sayı fazla” gibi keyfî eşik koymuyor. Gözlenen eski maksimum 9/saat ve 28/gündü; sabit kod cap’leri bu aralıkta tetiklenmedi. Immediate state’lerin tümü `KRITIK_STATELER` içinde olduğundan saatlik cap’i aşınca da geçebiliyor; geniş evrende gerçek burst ayrıca ölçülmeli. `send_text` ile giden scheduled özetler ve public post’lar mevcut DM cap sayacına dahil değil.

## 5. Public/DM ayrımı ve teslimat

### Düzeltilen

- Public payload’dan `watch_context`, `dm_context` ve `lifecycle_event_id` çıkarılır. Public mesaj yalnızca public Formation formatter’ının kendi alanlarını görür.
- DM ve kanal cooldown anahtarı ayrı tutulur; event ID her iki destination’da da kullanılır.
- DM başarısızlığında uygun public post denenir. Public başarısızsa kanal cooldown’u yazılmaz; sonraki scan aynı event için public retry fırsatını korur. DM başarılıysa kanal hatası DM sonucunu bozmaz.
- `send()` dönüşü hâlâ **DM sonucudur**. Yalnız public teslim olduysa `send()` false döner; dolayısıyla `alerts_sent` ve watch `mark_reported` DM başarısına göre davranır. Public-only başarı metriği ayrı değil.

### Kalan teslimat semantiği

- DM için tek HTTP denemesi ve 10 saniye timeout var; `429`/`5xx` için notifier düzeyinde retry/backoff veya kalıcı outbox yok.
- Başarısız bir `KIRILIM_TEYITLI` olayı sonraki barda başka state’e geçerse DM’de kaçabilir; sonraki watch digest aynı olayı değil, güncel watch durumunu gösterebilir.
- Başarılı HTTP 200’den sonra cooldown yazılır. Telegram mesajı kabul ettikten sonra süreç, cooldown kaydından önce çökerse restart duplicate’i mümkündür. Timeout’ta Telegram’ın mesajı kabul edip etmediği belirsiz olabilir; Telegram `sendMessage` için burada kullanılan idempotency anahtarı yoktur. Exactly-once teslimat garanti edilemez.
- Yerel cooldown/cap JSON yazımları artık atomiktir. Supabase ve yerel kopya yedekli kullanılır; notifier Supabase `upsert` dönüş değerini ayrıca bir delivery metriğine dönüştürmez.
- Notifier pasif/mock modda `send()` policy kabulünü başarılı sayabilir; böyle bir sayaç “Telegram gerçekten teslim etti” anlamına gelmez. Bu denetimin hiçbir replay sayısı teslimat olarak sunulmamıştır.

## 6. Digest, restart ve özet yoğunluğu

Varsayılan kod saatleri 09:55 sabah özeti, 18:45 kapanış özeti/digest, 18:10–19:00 aralığında bir akşam bakım mesajı ve 20:00 gün sonu tam evren raporudur. Bu koşullar sağlanırsa owner DM’de günde **dört ayrı scheduled mesaj yolu** oluşabilir; 09:55 ve 18:45’te public summary de ayrıca denenir. Akşam bakım ve 18:45 mesajı aktif formasyon/daily stats bakımından örtüşür, fakat 20:00 panel daha geniş rapordur. Bunların gerçek gün içi gönderim sayısı log boş olduğu için ölçülemedi.

Restart davranışı:

- `LiveState` son başarılı formation snapshot’ını yerel dosya/Supabase’e kaydediyor; yerel snapshot geçici dosya + atomic replace kullanıyor. Başarısız scan son geçerli görünümü koruyor.
- Formation lifecycle engine state’i ayrıca serialize edilmiyor; sonraki scan cache OHLC’den yeniden kuruluyor. Restart’ta `son_taranan_kapanis=None`, bu yüzden aynı kapanış tekrar hesaplanabilir. Yeni event dedup aynı immediate event’in tekrarını azaltır.
- Cooldown ve cap state’i disk/Supabase’e yazılıyor; bu turda bu JSON yazımları atomikleştirildi.
- `DeferredAlertBuffer`, `last_summary_sent`, `last_summary_channel_sent`, `last_post_close_analysis_date` ve maintenance tarihi süreç belleğinde. Restart kapanış digest’ini/özetini tekrar ettirebilir; buffer yeniden kurulmadıysa bekleyen gün içi watch adayları da digest’te kaybolabilir. Post-close scan sonradan buffer’ı yeniden doldursa bile 18:45 digest’i geçmiş olabilir.
- `send_text` scheduled raporları notifier DM alert cooldown/cap akışından geçmiyor. Bu nedenle event dedup fix’i scheduled-summary restart tekrarlarını çözmüyor.

Bu risk için güvenli sonraki adım, scheduled job/date/destination bazlı kalıcı idempotency ledger ve aynı gün watch digest’in güvenli şekilde yeniden kurulmasıdır. Bunu bu değişiklikte eklemedim; boş buffer’dan stale aday üretmek ve başarılı/başarısız gönderim sınırını yanlış işaretlemek yeni kayıp/tekrar yaratabilir.

## 7. Sembol hatası, scan tutarlılığı ve genel state audit’i

- Bir sembolün çevresindeki hata sınırı exception’ı sayıyor ve `continue` ile diğer sembollere geçiyor. Tek sembol arızası döngüyü bütünüyle durdurmuyor.
- Bir sembolde oluşan hata/atlama tam evreni eksik bırakırsa scan `basarisiz` işaretleniyor ve son başarılı LiveState snapshot’ı korunuyor.
- Alert’ler tarama bitmeden, sembol başına gönderilir. Daha sonraki sembol hata verirse önceki DM’ler geri alınamaz; kullanıcı kısmi fakat kendi sembolü için taze bir olayı görmüş olabilirken panel eski başarılı snapshot’ta kalabilir. Bu bir transaction değildir; mesajları scan sonunda toplamak gecikme ve kayıp politikasını değiştirir.
- Webhook/poll komut işleme ve LiveState okuma-yazması serileştirme/lock kullanıyor. Telegram komutları scan’i doğrudan paralel çalıştırmak yerine isteği ana döngüye kuyruğa alıyor. Cooldown ve cache writes aynı scan thread’inde seri; command `send_text` yanıtları ayrı HTTP isteği olabilir.
- Incomplete candle filtresi timeframe kapanışına göre; 1D özel olarak seans kapanışında tamamlanıyor. `tam_yeniden=True` Formation snapshot’larının cache geçmişinden yeniden kurulması restart parity’si için iyi; aynı barın yeniden taranması domain hesaplarını tekrar çalıştırabilir.
- OHLC cache’lerinin pkl/json dosyaları notifier state’i gibi atomik yazılmıyor. Loader bozuk pickle’da JSON fallback’i deniyor; her iki kopyanın aynı anda yarıda yazılması hâlâ risk. Bu audit’te cache formatı değiştirilmedi.
- `logs/bot.log` denetim başında 0 bayttı; gerçek canlı gönderim başarısı, Telegram 429 oranı ve restart zaman çizelgesi logdan doğrulanamadı.

## 8. Domain context / dashboard gürültüsü

Context seçimi aynı scan’in aynı timeframe frame’ine bağlıdır; domain `error`/`skipped`, sembol/timeframe uyuşmazlığı, timestamp eşleşmemesi, stale/future event, Volume warm-up ve OB/FVG kalite kapıları context’in ilgili parçasını düşürür. Domain hatasının kendisi Formation DM’ini engellemez. Public mesaj domain context’i ve watch list’i almaz.

Ölçüm notları:

- 28 sembol × 4 timeframe = **112 frame**. Önceki tam pipeline ölçümü (resampling/lifecycle/domain/context dahil) yaklaşık **15.764 s**; son ayrı domain-runner ölçümü 112 frame için **9.237 s**. Ölçüm kapsamları farklıdır ve cache tarihi 25 Eylül 2026’dır.
- Domain runner exception/error görülmedi. Order Block 112/112 `OK`; Volume Participation 112 native state; FVG 1H’de 28 destek dışı/skip, diğer 84 frame’de 56 `OK`, 28 `WARMUP`. Market Structure çıktısında ayrı `data_quality` alanı yok.
- Önceki not iki alert örneği yazmıştı. Bu rapor için son cache barı (`2026-09-25 18:35 +03`) bağımsız yeniden kurulduğunda **3** kalite/state-uygun immediate Formation snapshot’ı bulundu: GUBRF 4H `KIRILIM_TEYITLI`, HALKB 1H `RETEST_BASARILI`, HALKB 4H `FORMASYON_TAMAMLANDI`. Önceki “2” örnek ile bu “3” uygun snapshot arasındaki sayım farkı çözülemedi; önceki replay artifact’i ve tam payload saklanmamış. İki sayıyı sessizce birleştirmiyorum.
- Bu son bar örneklerinde GUBRF yapısı 1H/2H/4H CHoCH yukarı ve 1D BOS aşağı; HALKB’de 1H/2H/1D BOS yukarı, 4H BOS aşağı gösterildi. Bu çok-timeframe context **toplam yön/sinyal olarak birleştirilmiyor**; kullanıcıya ham timeframe karşılaştırmasıdır. HALKB 1H/4H örneğinde volume `Yükselen`; yakın bölgeler OB idi, seçilen zone örneklerinde FVG yoktu.
- Yeni son-bar örnek DM’leri watch list olmadan 246–284 karakterdi. Önceki nottaki 298–306 karakterlik iki örnek aynı payload/sampling olmadığı için doğrudan önce/sonra kıyaslanamaz.
- Zone mesaj yazımı artık iki ondalık hane (`45.060001373…` yerine `45.06`). Ham OB/FVG nesnesi ve uzaklık seçimi değişmiyor; yalnızca metin temsili yuvarlanıyor. Domain’in sub-cent hassasiyeti anlamlı bir değer ürettiği ürün ihtiyacı varsa tick-aware gösterim ayrıca tanımlanmalı.

Bunlar 25 Eylül’de biten cache’e aittir; **güncel piyasa durumu değildir**. Gerçek public post, dashboard kullanıcı trafiği veya canlı performans kanıtı sayılmaz.

## 9. 100 sembol ölçeği

100 sembol × 4 timeframe için canlı/yeni tarihli veriyle gerçek ölçüm yapılmadı. İki sınırlı tahmin:

- 28 × 4 (112 frame) tam pipeline’ın 15.764 saniyelik eski yerel ölçümünü doğrusal ölçeklemek, 100 × 4 için yaklaşık **56 saniye CPU** verir. Bu yalnızca kaba tahmindir; domain engine cold/warm durumu, farklı bar sayısı, piyasa saatleri ve 100 gerçek sembol ölçülmedi.
- Default Yahoo pacer 10 istek/grup, istek arası 0.9–1.5 s ve grup arası 10–15 s. 100 seri istekte yalnız pacing beklemesi yaklaşık **2.7–4.3 dakika**; hem 100 adet 1H hem de 100 adet günlük fetch gerekirse yaklaşık **5.4–8.6 dakika** pacing beklemesi, Yahoo request süresi ve retry’ler hariç. Rutin günlük cache tazeyse ikinci 100 istek gerekmeyebilir.

Bu varsayımlarda 100 sembol CPU + pacing açısından saatlik tarama aralığına sığabilir; **kanıtlanmış değil**. Config’te 45 dakika tarama uyarısı var (hard timeout değil); retry/API yavaşlığı, kısmi evren ve Telegram burst’leri ayrıca test edilmeli. 28 sembol replay’indeki 9/saat ve 28/gün maksimumu 100 sembole doğrusal ölçeklenemez. Özellikle tüm immediate state’ler saatlik cap’ten muaf ve günlük cap 120; 100 sembolde gerçek dağılım izlenmeli.

## 10. Yapılan/yapılmayan değişiklikler ve testler

### Bu denetimde yapılanlar

- `main.py`: four immediate lifecycle states için native transition event ID üretip alert payload’una ekleme.
- `notifier.py`: event-aware DM/public dedup; destination-bağımsız delivery/cooldown; public payload sanitization; atomik cooldown/cap JSON writes.
- `formation_dm_context.py`: zone labels için iki ondalık presentation formatting; native values mutation yok.
- Regression testleri: stable event ID/fallback; 4 saat sonra aynı event’in dedup edilmesi; restart’ta cooldown’un korunması; serialization failure’da son iyi JSON’un korunması; DM-only watch/domain context’in public’ten çıkarılması; DM/channel hata bağımsızlığı; ham zone sınırlarının değişmeden kalması.

### Test sonuçları

- İlgili alt küme + integration + Supabase persistence: **51 passed**.
- `test_tarama_zamani.py` (Telegram env değişkenleri boşaltılarak, gerçek ağa çıkmadan): **90/90 kontroller geçti**; önceden bulunmayan `telegram_kap.json`/`telegram_soguma.json` test artıkları temizlendi.
- Tam pytest: **246 passed, 4 failed**. Dört hata `test_domain_incremental_parity.py` içinde test helper’ın bulunmayan `FvgEngulfingEngine._calculate_atr_series` metodunu çağırması (`AttributeError`). Bu parity baseline’ı önceki denetim notunda da vardı; domain engine dosyaları bu değişiklikte düzenlenmedi.
- Parity modülü hariç: **239 passed**.
- `py_compile` ve `git diff --check` başarılı.
- Test/replay sırasında gerçek Telegram mesajı gönderilmedi; commit/push yapılmadı.

## 11. Kullanıcı için 10 ürün sorusuna açık cevap

1. **Hangi state’ler hemen bildirim?** Dört state: teyitli kırılım, başarılı retest, formasyon tamamlandı, başarısız kırılım; kalite timeframe kapısı geçilirse DM.
2. **Hangi state’ler günlük digest?** Sıkışma güçleniyor, kırılım hazırlığı/adayı/denemesi, retest bekleniyor/ediliyor. Slot başına son durum; kapanışta en çok 12.
3. **Aynı state sürerken neden tekrar geliyordu?** Cooldown anahtarı state bazlıydı; 4 saat sonra aynı episode tekrar açılıyordu. Artık stable lifecycle event ID aynı olayı kapalı tutuyor.
4. **Yeni state ayrı olay mı?** Evet. Teyit → retest → tamamlanma gibi yeni lifecycle transition ayrı state/event olduğunda ayrıca değerlendiriliyor; dedup state hikâyesini bastırmıyor.
5. **Public ile DM aynı mı?** Hayır. Varsayılan public yalnızca `FORMASYON_TAMAMLANDI`/`RETEST_BASARILI`, kalite ≥80. DM watch/context public’e aktarılmıyor. Public post artık DM’nin başarılı olmasına bağlı değil.
6. **Domain bozulursa Formation alarmı duruyor mu?** Hayır. Kısmi veya başarısız domain sonuçlarında yalnız geçerli parçalar kullanılır; context selection hatası Formation-only DM’e düşer.
7. **Telegram DM başarısızsa tekrar deneniyor mu?** Durable outbox yok; başarılı response alınmazsa cooldown yazılmaz. Sonraki scan aynı state’i görürse yeniden dener, fakat state geçmişse DM kaçabilir. Bu önemli kalan risk.
8. **Bir sembol bozulursa tüm tarama ne olur?** Döngü sonraki sembole devam eder. Herhangi bir sembol eksik/hatalıysa evren scan’i başarısız işaretlenir ve son başarılı snapshot korunur; daha önce gönderilmiş DM’ler geri alınamaz.
9. **Restart digest’i koruyor mu?** LiveState ve cooldown/cap kalıcı; deferred buffer ve scheduled sent-date kayıtları değil. Restart sonrası digest/özet tekrarı veya watch kaybı olası; çözüm için kalıcı job ledger ve buffer yeniden kurma tasarımı gerekiyor.
10. **100 sembol hazır mı?** Tahminler saatlik pencereye sığabileceğini düşündürüyor; 100 sembol gerçek taraması ölçülmedi. 100 veri çekimi başına yalnız pacing 2.7–4.3 dakika, 1H+1D ikisi gerekirse 5.4–8.6 dakika; bu sayılar provider latency/retry hariçtir.

## 12. Sonraki adımlar

1. 100 sembollük kontrollü, ağsız/fixture replay ve ayrıca gerçek veri fetch latency ölçümü (Telegram kapalı/mock).
2. Telegram send failure için kalıcı outbox mı, state transition digest fallback’i mi istendiğini kararlaştır; accepted-but-timeout duplicate riskini de kapsa.
3. Scheduled summary/post-close/maintenance için kalıcı destination+date idempotency ledger tasarla; digest buffer’ının stale aday üretmeden restart sonrası nasıl geri kurulacağını test et.
4. 2026-09-25 cache üstünde önceki “2” ve yeni “3” alert sayımı farkını çözmek için replay input/snapshot artifact’ini sabitle.
5. FVG parity test helper’ını mevcut engine API’siyle eşleştir; bunu ayrı baseline/test düzeltmesi olarak tut.
