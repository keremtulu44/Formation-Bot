# Mum çekme düzeni, AI kullanımı ve bildirim azalması

**Tarih:** 27 Kasım 2026 · **Durum:** yerel uygulama ve doğrulama kaydı; canlıya dağıtım kanıtı değil.

## 1. Amaç ve değişmeyen kurallar

İstenen iş: mumların ne zaman ve hangi sırayla çekildiğini; aksama, eksik veri, kurtarma ve eski önbellek durumlarında ne olduğunu netleştirmek; AI'ı daha kontrollü kullanmak; günlük bildirim sayısındaki yaklaşık 15 → 3–5 düşüşünü araştırılabilir hale getirmek.

**Sayı artsın diye kalite eşikleri, formasyon matematiği, P6 politikası, cooldown, haber filtresi veya teslim kapıları gevşetilmedi.** AI görüşü yeni bir alarm bastırma filtresine dönüştürülmedi. Genel Supabase yazımı açılmadı, kalıcılık modeli değiştirilmedi. Önceki kısa alarm / ayrıntılı manuel AI ayrımı korundu.

## 2. Mum çekmenin uçtan uca düzeni

```text
Seans/takvim ve tarama zamanı
  → her sembolde cache incelemesi
  → sağlıklı cache: rutin 5d pencere
    boş/eski cache: tam 60d pencere
    onarılabilir boşluk: soğumalı tam pencere denemesi
  → ortak, seri Yahoo pacer'ı
  → Yahoo OHLCV temizliği + canlı çağrıda kapanmış mum tazelik kontrolü
      uygun yanıt → kabul
      boş/geçersiz/bayat/ağ hatası → TV reaktif yedeği
  → TV de aynı canlı tazelik kontrolünden geçer
  → geçici hata kalırsa tur sonunda tek retry
  → cache'e yazma doğrulaması
  → yeterlilik/split/tazelik kapıları
  → kapanmış TF'ler → motorlar → kalite/politika/tekrar/bütçe kapıları
  → uygunsa AI; başarısızsa düz teknik kart
  → mevcut DM/public teslim yolları
  → tarama akış sicili + health özeti
```

### Senaryolar

| Durum | Yeni/korunan davranış | Ne yapılmaz? |
|---|---|---|
| Yahoo geçerli ve beklenen kapanmış mumu içeriyor | Veri kullanılır, TV açılmaz. | Gereksiz çift sağlayıcı çağrısı yok. |
| Yahoo dolu ama son kapanmış mum eksik | Canlı validator reddeder; TV aynı gereklilikle denenir. | HTTP başarısını/veri uzunluğunu tazelik saymaz. |
| Yahoo boş, bozuk veya ağ hatalı | Mevcut TV yedek yolu çalışır. | Sentetik mum üretilmez. |
| TV güncel veriyle kurtarıyor | Aynı turda kullanılır; kaynak etiketi TV, zincir Yahoo→TV olur. | Başarılı kurtarmadan sonra gereksiz Yahoo retry yok. |
| İki sağlayıcı da gecikmiş | Geçerli yeni veri sayılmaz; geçici hata tek retry'a uygun olur. | İki eski yanıt birleştirilip “taze” ilan edilmez. |
| Geçici hata retry'da düzeliyor | Aynı turda motorlara girer; kurtarma ayrıca sayılır. | Sonsuz retry yok. |
| Desteklenmeyen sembol / kalıcı 404 | Mevcut sınırlı hata yolu korunur. | Her kalıcı hataya kör tekrar eklenmez. |
| Cache'e append reddediliyor | Yeni yanıt analizde taze sayılmaz; ret kaydedilir. | Reddedilmiş veri yazılmış gibi gösterilmez. |
| Cache yeterli ve mevcut tazelik kapısı izin veriyor | Cache kullanımı açıkça sayılır. | “Yeni sağlayıcı verisi” denmez. |
| Cache yetersiz, fazla eski veya split sorunu var | İlgili analiz kapısı atlar; sebep sicile girer. | Eski/bozuk veriye dayanıp alarm sayısı artırılmaz. |
| Eski seans içi delik | Önceden var olan soğumalı 60d tamir yolu korunur. | Bu sürüm delikli tüm serileri topluca yasaklamaz; mevcut uyarılı analiz davranışı değişmedi. |
| Hafta sonu / açılıştan önce | Beklenen son işlem günü kapanışı kullanılır. | Cuma kapanışı Pazartesi sabahı salt saat yaşı nedeniyle yeni validator'da reddedilmez. Mevcut üst katman cache kapıları ayrıca geçerlidir. |
| Yayın gecikmesi payı | Mevcut `SCAN_DELAY_AFTER_CLOSE_MIN` kadar pay bırakılır. | Tam kapanış saniyesinde sağlayıcıya henüz yayımlanmamış mumu dayatmaz. |
| TV çağrısı timeout oluyor | Çağıran beklemeyi bırakır; worker bitene kadar kotasını tutar. | Timeout olmuş thread iptal edilmiş gibi yeni işler sınırsız açılmaz. |

### Izgara ve zaman farkı

Yahoo'nun `:30` etiketli 1H serisiyle native TV'nin tam saatli serisi aynı ızgara değil. Validator, tutarlı tam-saat serisine olmayan `:30` mumu şart koşmaz. Mumun **açılış etiketi** ile hesaplanan **gerçek kapanışını** ayrı tutar; yarım gün sonu ve normal 18:00 intraday kapanışı korunur. Makro enstrümanlar BIST seansına zorlanmaz. Takvim bilinmiyorsa tazelik iddia edilmez.

Bu kontrol açıkça canlı çağrıda etkin: `fetch_yfinance_1h(..., as_of=...)`. Tarihsel/araştırma çağrılarında `as_of` verilmezse eski davranış korunur. Ana tarama `validate_freshness=True` gönderir. Bu sürüm bütün başlangıç/gece/araştırma indirmelerini yeniden tanımlamaz; 1D çekimin mevcut kısa hata soğuması ve başarılı çekim soğuması korunur.

## 3. Sağlayıcı ve worker güvenliği

- En fazla **iki yaşayan TV worker**. Çağıran timeout olsa bile worker slotu, gerçek işin `finally` bloğu bitene kadar boşalmaz.
- Dolu kotada yeni thread açılmaz; Yahoo akışı ve sonraki taramalar devam eder.
- Ortak TV istemcisindeki WebSocket `finally` kapanışı korunur.
- `health.veri_saglayicilari` içinde aktif TV worker ve sınır görünür.
- Bu bir zorla thread sonlandırma mekanizması değildir. Kütüphane gerçekten hiç dönmezse slot tutulmaya devam eder; sınırsız kaynak tüketmek yerine yedek kapasitesi sınırlanır.
- Sağlayıcı geçmişi **sembol + TF** için de tutulur. Günlük Yahoo başarısı saatlik TV kaynağını ezmez. Ana tarama, aldığı 1H yanıtının kaynak etiketini analiz çerçevesine taşır; native 4H seçimi başka TF'nin son çağrısıyla karışmaz.

Kaynak etiketi birleştirilmiş cache'in bütün eski barlarının aynı sağlayıcıdan geldiği iddiası değildir; bu turdaki yanıtın kaynağıdır.

## 4. AI tarafındaki düzenleme

### Veri güveni

Canlı alarmın ana TF'si eksik, beklenen kapanışa göre gecikmiş veya gecikmesi bilinmiyorsa AI API çağrısı yapılmaz. **Teknik alarm iptal edilmez; mevcut düz kart yolu devam eder.** Manuel `/ai` tarihsel/isteğe bağlı inceleme olarak ayrı kalır.

AI paketinin kaynak satırı artık canlı tarama/manuel önbellek ayrımını ve varsa 1H kaynak etiketini taşır. Daha önceki kapanmış mum, eksik katman, karşı delil, araştırma kesim zamanı ve KAP sınırları korunur. AI'dan eksik mumu tahmin etmesi istenmez.

### API zinciri bütçesi

| Ayar | Varsayılan | Anlamı |
|---|---:|---|
| `AI_ALARM_TOPLAM_BUTCE_SN` | 45 | Canlı alarm API zincirinin ortak süre bütçesi |
| `AI_ALARM_SAGLAYICI_BUTCE_SN` | 20 | Tek sağlayıcıya ayrılan üst bütçe; kalan toplam daha azsa kalan kullanılır |
| `AI_YORUM_MAX_BEKLEME_SN` | Mevcut ayar | Pozitifse alarm sağlayıcı bütçesini daha da daraltabilir; manuel yolun mevcut davranışı korunur |

- Toplam bütçe her yedek sağlayıcıda sıfırlanmaz.
- Connect/read/write/pool timeout'ları sağlayıcıya verilen bütçeyi aşmayacak şekilde daraltılır.
- Bütçe bitmişse sonraki sağlayıcı başlatılmaz; bütçeden sonra gelen başarı zamanında başarı diye kabul edilmez.
- Wrapper wait akışı süre kontrolünden geçer; Gemini'nin geç kalan tamamlanmış yanıtı reddedilir.
- AI sağlık özetinde etkin bütçeler ve oturum içi alarm sonucu sayaçları görünür. Bunlar teslim sayaçları değil, AI hazırlama sonuçlarıdır.

**Sınır:** Bu değerler senkron HTTP istemcisine verilen süre bütçeleridir; süreç izolasyonuyla zorla iptal sağlayan katı gerçek-zaman garantisi değildir. HTTP aşamaları/okuma kontrol noktaları nedeniyle hedef aşılabilir. Prompt/motor/çizim paketinin hazırlanma süresi ve shadow yazımı bu API zinciri bütçesine dahil değildir. Toplam tarama gecikmesini yalnız “AI 45 saniye” diye okumayın. Daha kısa sınırın AI başarı oranına etkisi canlıda ölçülmeli; gerekirse bu iki ayar gözleme göre değiştirilir.

## 5. `/akis`: sayılar neden azaldı sorusu için yeni kanıt

Yeni salt-okunur `/akis` (`/akış`) komutu mevcut komut yetkilendirmesini kullanır; tarama veya harici API başlatmaz. Public tarafta diğer okuma komutları gibi yalnız mevcut izin/yönetici kontrolüyle çalışır.

Son koşuda gösterir:

- İstenen/işlenen sembol ve tarama modu;
- Gelen yanıt, fetch hatası, retry kurtarması;
- Yahoo/TV/bilinmeyen kaynak dağılımı;
- Sağlayıcı/cache ile analiz ve atlanan semboller;
- Yetersiz veri, bayatlık, split ve cache reddi;
- Ana formasyonda eşik altı, özete erteleme ve durum kapsamı dışı;
- Ana DM gönderim denemesi ve başarılı/başarısız dönüş;
- Birleşik domain'de destek kapısı sonrası tetik, P6/P4 elemesi, üretilen aday;
- Domain sevkinde filtre ve başarılı kart/özet dönüşleri;
- En fazla 12 kısa sorun örneği.

Son 7 **kayıtlı** gün için yalnız otomatik tam-evren koşuları karşılaştırılır. Manuel, alt-evren ve `send_alerts=False` koşuları günlük karşılaştırmayı şişirmez.

### Sayaçları doğru okuma

Bunlar çoğunlukla **tarama gözlemleri**: aynı formasyon iki taramada görülebilir. Ham tetik/politika elemesi, benzersiz alarm veya Telegram mesaj sayısı değildir. Domain `dispatch_ok` DM/public hedeflerinden başarılı dönüş/kabulü veya özet kartını temsil edebilir; hedef başına teslim adedi değildir. Ana DM başarılı dönüşü de tur sonu bekleyen kuyruk flush'ında gerçekleşen bütün teslimleri kapsamaz. Stabil'in ayrı yolu mevcut sağlık/teslim kayıtlarıyla izlenmeye devam eder; bu komut bütün Telegram trafiğinin eksiksiz muhasebesi değildir.

### Saklama sınırı

`DATA_DIR/scan_evidence.json`: atomik, süreç içi kilitli, en fazla 512 koşu; okuma boyut sınırı 4 MB. Bozuk dosya sessizce sıfırlanmaz. Ham sağlayıcı hataları, sırlar, mesaj metni veya DataFrame yazılmaz. `health.son_tarama_akisi` en son tamamlanan koşunun özetini gösterir.

Bu **yerel** kayıt; Supabase'e yazım eklenmedi. Geçici disk kaybolursa sicil de kaybolabilir. Sınırlı saklama, başlangıç tarihi ve süreç kesintileri nedeniyle günlük toplamlar tam gün garantisi vermez. Eski 15/gün dönemini geriye dönük yaratmaz.

## 6. Bildirim azalması hakkında eldeki kanıt

Kullanıcının gözlemi: eskiden yaklaşık 15/gün, son dönemde yaklaşık 3–5/gün; geçmiş haber/gündem koşulları sıra dışı olabilir. Hedef ve kesin başlangıç aralığı belirli değil. **Azalmanın anormal olduğu varsayılmadı.**

27 Kasım salt-okunur Supabase kontrolü:

- Kasım için `ai_yorum_test` içinde 27 Kasım tarihli **iki alarm hazırlama kaydı** (teyit + retest) ve **bir manuel yorum** bulundu.
- Bu tablo bütün Telegram alarmlarını veya teslimlerini saymıyor. Hazırlama sırasında tutulan eski `telegrama_gitti` alanı da kesin teslim makbuzu değil.
- `bot_store` heartbeat/son tarama kayıtları 30 Ekim; teslim yedeği de 30 Ekim. Genel uzak yazımın read-only olması nedeniyle bunlar mevcut sürecin durduğunu kanıtlamıyor.

Dolayısıyla **“piyasa sakinleşti” de “sistem alarm kaçırıyor” da mevcut veriyle doğrulanmış sonuç değil.** Haber etkisi, volatilite ve gerçek tetik sayısı farklı dönemler karşılaştırılarak incelenmeli.

Kodda sayıyı azaltabilen bilinen meşru kapılar: formasyon kalite/durum koşulları, P6 bağlam filtresi, altı bar domain cooldown'u, hikâye/tekrar kapıları, public ayrı kuralları/bütçeleri ve veri tazeliği. Bunların varlığı son düşüşün sebebinin kesin bu kapılar olduğu anlamına gelmez. Bu sürüm bu kapıları gevşetmedi.

## 7. Canlı gözlem planı

1. Seans dışında mevcut servise bu sürümü dağıt; ikinci Blueprint servisi açma.
2. Çalışan commit, evren, DM/public hedef modu ve P6 ayarını `/durum`, `/render` ve health ile doğrula.
3. En az üç karşılaştırılabilir tam işlem gününde `/akis` kaydını sakla. Servis kesintilerini ve kısmi günleri ayrıca işaretle.
4. **Veri kapsamı düşükse:** sağlayıcı/yeniden deneme/kurtarma ve atlanan semboller öncelik.
5. **Kapsam normal, tetik azsa:** piyasa koşulları/gerçek motor tetikleri incelenir; haber etkisi varsayılmaz.
6. **Tetik var, politika elemesi fazlaysa:** P6'nın etkisi ölçülür; alarm sayısı hedefiyle eşik değiştirilmez.
7. **Aday var, sevk/teslim azsa:** cooldown, bütçe, DM/public ayrı kuyruklar ve belirsiz gönderimler incelenir.
8. AI sağlık sayaçlarında düz karta dönüş artarsa veri kalite nedenleriyle sağlayıcı timeout/doğrulama nedenlerini ayır. Önce ölç; sonra süre bütçesini ayarla.

## 8. Doğrulama

Ağsız yeni senaryolar: Yahoo/TV gecikmesi ve kurtarma, aynı gün açık mumun eski kapanışı gizleyememesi, yayın payı, hafta sonu/açılış/yarım gün, `:00`/`:30` ızgaraları, bilinmeyen takvim, tarihsel API uyumu, TF başına kaynak, timeout sonrası worker kotası, atomik/eşzamanlı/bozuk sicil, manuel karşılaştırma izolasyonu, komut yetkisi, AI ortak bütçesi ve eksik/bayat veri kapısı. Domain teşhis sayaçlarının aday seçimini değiştirmediği ayrıca test edilir.

- Hedefli veri/yeni regresyon seçimi: **111 geçti**.
- Domain + AI istemci seçimi: **49 geçti**.
- Geniş tam-paket koşusu: **5.222 geçti, 43 atlandı, 2 başarısız** — 1.343,41 sn (22 dk 23 sn). İki hata da yeni `/akış` alias'ının yardım metninde listelenmemesiydi; yardım metni düzeltildi. Testler gevşetilmedi.
- Son native 1H AI ızgara düzeltmesi ve yardım metni düzeltmesinden sonra, etkilenen veri/AI/domain/Telegram mesajı/komut/patch yüzeyini kapsayan son regresyon: **1.634 geçti, 14 atlandı — 45,54 sn**, exit 0. Son küçük düzeltmelerden sonra bütün paket yeniden baştan çalıştırılmadı; tam-paket koşusunu tamamen yeşil diye sunmuyoruz.
- Statik/diff/compile: temiz. `pip check`: bozuk bağımlılık yok.
- Zamanlama betiği: **102/102**. Bağımsız triangle/breakout/flag/pennant betikleri: tüm kontroller geçti.
- P6 formül paritesi: **300 seride 0 fark**; eşikler/filtre kararı değiştirilmedi.
- Çevrimdışı grafik doktoru: **67 tamam, 8 uyarı, 0 hata**; AKBNK 4h PNG üretildi, Stabil direnç çizildi, fotoğraf gönderilmedi. Uyarılar yerel pip/setuptools eskiliği, eksik test anahtar/hedefleri ve ağ kontrolünün atlanması; canlı hazırlık kanıtı değil.

Yerel Python 3.11.2; hedef CI/deploy 3.12. Canlı sağlayıcı/Telegram çağrısı, Supabase yazımı, commit/push/deploy yapılmadı. Buradaki test sayıları aynı vakaları içerebilir; toplanıp farklı test sayısı diye sunulmaz.

### Kod girişleri

- [Canlı veri validator'ı](../../data/quality.py)
- [Sağlayıcı zinciri ve TV kotası](../../data/fetch.py)
- [Tarama ve veri/aday hunisi](../../bot/scan.py)
- [Yerel sicil ve raporu](../../bot/scan_evidence.py)
- [Domain teşhis sayaçları](../../bot/domain_alarm_service.py)
- [AI istemcisi](../../ai_prompt/client.py) · [AI orkestrasyonu](../../ai_prompt/service.py)
- [Yeni hata enjeksiyon testleri](../../test_candle_flow_reliability.py)
