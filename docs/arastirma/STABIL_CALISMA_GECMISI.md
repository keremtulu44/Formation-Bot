# Stabil çalışma geçmişi — konuşma kaydı ve kanıt sınırı

**Belgeleme:** tarihsel kayıt 2026-11-01; checkout yeniden denetimi 2026-11-04.
[Ana rehber](STABIL_REHBERI.md) · [dosya envanteri](STABIL_DOSYA_ENVANTERI.md).

> Aşağıdaki tamamlanma/test/süre/sayılar **önceki konuşma ve eski çalışma
> sürümlerinin kaydıdır**; bunları bugünkü manifestle birleştirmeyin. 2026-11-04
> checkout'ta Stabil runtime, `research/stabil_replay.py`, `research/stabil_bhv48.py`
> ve 48-soru aggregate JSON/CSV/Markdown mevcuttur. 80 MB native checkpoint paketi,
> özgün 27-soru çıktıları, manifest kaynak hashleri ve kesin veri sonu mevcut
> aggregate dosyalarda yoktur. Güncel dosya durumu aşağıdaki §7'de karşılaştırılır.

## 1. Domain ve kullanıcı kabul edilen kapsam

Özgün Python TXT matematik kaynağı alındı; Pine yalnız görsel görünüm içindi.
Trend ve günlük destek yaşam döngüsü bağımsız ve tam çıktı olarak tutulduğunun
raporu verildi. Domain-first sonrası grafik, sonra kart bilgilendirmesi yapıldığı
anlatıldı. Kaynağın hash eşitliği bugün gerçek dosyadan doğrulandı; entegrasyon
kodlarının çalışması bugün doğrulanamadı.

Grafik kapsamı: ana günlük destek; stepline, geçmiş native renkler, etiket ve
helper olmaması; dört TF, alarm/normal/eğitim. Eğitim kesitinde gelecek veri
kullanmama ve sonuç görselinde soru katmanını dondurma. Önizleme ASTOR arşivinin
son günlük mumu 2026-10-19 olan örneğiydi; canlı fiyat testi değildi.

Kart kapsamı: YAPI bölümünde destek üstünde/altında (eşitlikte destekte);
veri yoksa susma; o anki alarm kapanışı ve bilinen günlük destek. Skor ve alarm
filtresi değişmediği bildirildi. Gerçek Telegram/deploy doğrulaması yapılmış
olduğu söylenmedi.

## 2. Performans yöntemi düzeltmesi

| Aşama | Önceki rapor | Doğru yorum |
|---|---|---|
| Prefix'i her kapanışta baştan çalıştırma | ASTOR 803,052 sn; 100 çarpımı 22 sa 18 dk | Terk edilen verimsiz uygulama; doğal Stabil maliyeti değil |
| Tek geçişli geçmiş, ortak ölçüm | ASTOR 17,050 sn; 100 çarpımı 28 dk 25 sn | Tek örnekten seri hesap tahmini; tüm yazma/host farklarını kapsamaz |
| ASTOR benchmark kapsamı | 501 kaynak günlük, 1079 4H checkpoint; 2025-05-07 → 2026-10-19 | Arşiv ölçümü; 100 sembol ortalaması veya canlı SLA değil |

Yöntem: [replay hatları](STABIL_REPLAY_HATLARI.md). Tek-sembol benchmark,
toplu araştırma ve Telegram eğitimi farklı işlerdir.

## 3. İlk 100 sembol — genel 27 soru/referans grubu

Önceki kayıtta 100/100 ve sıfır hata/eksik; **107.446 checkpoint**, olay
çıkarımı düzeltildikten sonra **386.017 soru gözlemi**, **2.034 grup×ufuk
satırı** bildirildi. Worker hesap+kayıt süreleri toplamı 45 dk 15 sn idi;
kurulum, son toplama ve kalite kontrolüyle tüm duvar saati değildi.

### Kritik olay eşleme düzeltmesi

Native lifecycle olayındaki `available_at` alanının mum etiketi olması,
günlük olayları sonraki 4H checkpoint'inde zaman aralığı filtresinin dışında
bırakmıştı. Native tam olay geçmişi saklandığı için yeni `sequence`'nin ilk
bilindiği checkpoint kullanılarak **motor tekrar çalıştırılmadan** düzeltildiği
raporlandı: S04/M01 eski olay satırı 64 → 12.768. İlk checkpoint'in geçmiş
olayları yeni sayılmadı; orijinal dosyalar saklandığı söylendi.

Bu turun genel geri alım ortalamaları, kullanıcının sonradan anlattığı
**çizginin hareket/yataylaşma yolu** ayrımının doğrudan testi değildi.

## 4. Model açıklaması sonrası ikinci 100 sembol — 48 davranış başlığı

Kullanıcı dikey/yatay düzeltmesini ve yükseliş/düşüş yollarını anlattı.
[Model](STABIL_DAVRANIS_MODELI.md) ve [48 soru](STABIL_DAVRANIS_SORULARI.md)
üzerine yeni çalışma raporlandı. Önceki tam native dizin o ortamda da
bulunmadığından aynı çekirdekle yeniden üretim gerektiği belirtildi.

| Ölçü | Önceki konuşmada raporlanan |
|---|---:|
| Tamamlanan sembol | 100/100, hata/eksik yok |
| 4H checkpoint | 107.446 |
| Soru gözlemi | 390.905 |
| Grup × ufuk satırı | 4.074 |
| Operasyonel alt soru ölçümü | 33 |
| Yaklaşık gösterge (proxy) | 8 |
| Açık tanım/veri/ayrı doğrulama ihtiyacı | 7 |
| Worker süreleri toplamı | 35 dk 2 sn; tüm duvar saati değil |
| Son ilgili test sayısı | 77 geçti; tam repo regresyonu değil |

### Tarihsel olarak vurgulanan betimsel sonuçlar

Bunlar **rapor dosyası kurtarılana kadar tekrar doğrulanamayan konuşma sayılarıdır**:

- B04: 8 mumda başlangıçtaki sabit seviyenin altında kapanış, yeni seviyede
  %11,3 (2340 gözlem), 33–64 günlük mum yaşında %3,0 (432 gözlem). Her an
  güncellenen aktif çizginin kırılma oranı değildi. Mesafe, önceki yol ve
  sağ kalım seçimi kontrol edilmedi; kullanıcı modelinin kanıtı ilan edilmedi.
- D02: sabit segmentte geri alım sonrası 8 mum ortalama ATR hareketi, 1–2 ATR
  derinlikte +0,279 (231 olay); 2–4 ATR derinlikte -0,105 (76 olay). Önceki
  destek yolları ve süre eşleştirilmedi; bantlar işlem ayarı sayılmadı.
- F02: fiyatın çıkışı ile desteğin altına taşınması ayrı aritmetik geçişler
  olarak değerlendirildi. Konum değişimi tek başına fiyat tepkisi değildir.
- A01: kısa ufukta ne destek takibi ne geri dönüş gerçekleşmiş olabilir;
  “henüz olmadı” ile “hiç olmayacak” ayrıldı.

**Kesin cevaplanmadığı bildirilenler:** B06, F01, F03, H01, H02, H05, H06.
Özellikle görsel dikey→yatay rejim eşlemesi, eşleştirilmiş olaysız/basit referans
kontrolleri, erken saatlik native kanıt ve bağımsız kör doğrulama eksikti.

## 5. Paketleme kaydı ve bugünkü kayıp

Önceki konuşmada 80.735.612 baytlık (yaklaşık 80,7 MB) taşınabilir native/fiyat
paketi; 719 içerik üyesinin SHA256 kontrolü ve THYAO'nun 4107 soru kaydının
motor çağrısı olmadan birebir geri kurulması raporlandı. O **tam native paket**
2026-11-04 checkout'ta hâlâ yoktur. Bununla birlikte §7'deki 48-soru aggregate
JSON/CSV/Markdown dosyaları artık mevcuttur; bunlar native checkpoint/fiyat
paketinin veya eski 27-soru çıktılarının yerine geçmez.

Önceki 77 test, 700 çalışma dosyası kontrolü ve paket doğrulamaları bugünkü bu
dosya envanteri/tek-sembol spot-check'iyle aynı şey değildir. Yeni doküman veya
spot-check sonucu, eski 100-sembollük tam koşunun yeniden doğrulanması diye
sunulmayacak.

## 6. Bu güncellemede gerçekten yapılan

- Gerçek checkout, Git geçmişi/nesneleri, dosya yolları ve yükleme alanı denetlendi.
- Özgün TXT bulundu, depoya aynen alındı ve SHA256 eşitliği doğrulandı.
- Model, soru sicili, yöntem/geçmiş ve dosya durumları konuşmadan kaydedildi.
- Mevcut README/belge/araştırma/devir haritalarına gerçek bağlantılar eklendi.
- Eksik runtime/raporların yerini uydurma Python, JSON veya sahte paketle
  doldurmak yerine kurtarma ihtiyacı açık bırakıldı.
- Bu 2026-11-01 belgeleme turunda yeni replay, provider veri çekimi, Telegram veya Supabase işlemi yapılmadı.

## 7. 2026-11-04 checkout yeniden denetimi — current artifacts

| Kalem | Mevcut artifact'ten doğrulanan |
|---|---|
| Runtime / builder / evaluator | `domain_engines/stabil/`, `research/stabil_replay.py`, `research/stabil_bhv48.py` mevcuttur |
| 48-soru manifesti | 100 sembol; 107.441 H4 checkpoint; 10.417 first-seen support event; 48 soru; 642 sonuç satırı; 188.841 s; `user_confirmed_regime=false` |
| 48-soru verdict summary | 10 separate-validation; 17 no-clear-difference; 19 descriptive; 2 insufficient-sample |
| Aggregate çıktılar | `docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_SONUCLAR.json`, `_TABLO.csv`, `_YANITLARI.md` ve `_MANIFEST.json` |
| Tam native checkpoint/fiyat arşivi | Yok; manifestte source/data SHA256 ve kesin data cutoff da yok |
| Ayrı live-systematic çalışma | `stabil_live_systematic_results.json`: 50/53 non-macro canlı sembol arşivde; 284 sinyal; 75,9 hafta; next-bar hold %91,5; 8×4H medyan +0,262 ATR |

**Sayım farkı korunmalıdır:** §§3–4'teki eski konuşma kayıtları 107.446 checkpoint,
390.905/386.017 observation ve 4.074/2.034 satır gibi farklı sayı sürümleri
aktarır. Mevcut 2026-11-01 manifest 107.441/10.417/642 kaydeder. Bunları tek
koşu gibi toplamak veya eski yüzdeleri yeni manifestle teyit edilmiş saymak doğru
değildir. İlk 27-soru koşusunun özgün sonuçları da bu checkout'ta yoktur.

**Sınırlı ASTOR spot-check:** `research.stabil_replay.replay_single_symbol("ASTOR")`
manifestteki per-symbol 501 günlük / 104 haftalık / 1.079 H4 bar ve 91 first-seen
event adetleriyle eşleşti. Aynı 4h veri üzerinde cevaplayıcı 48 soru ve 552 satır
üretti (32 insufficient, 8 descriptive, 7 separate-validation, 1 period-varying).
Bu bir sembolün yeniden üretim kontrolüdür; 100 sembollük tam koşu değildir ve
manifestte eksik olan kaynak hashleri/veri kesimini geriye dönük ispatlamaz.

**Ayrı alarm-context denemesi:** ASTOR 2026-10-16 13:30 +03 kapanışına göre
1075 tamamlanmış H4 bar ve 183,20 referans kapanışıyla salt-okunur domain packet
örneği üretildi. Replay aday CSV'sindeki 13:30 etiketi H4 barının açılış etiketidir;
o bar ancak 17:30'da kapanır. Bu nedenle aday tetikleyici/kalite/kuvvet ve sonraki
onay/sonuç alanları 13:30 paketine dahil edilmedi. Sonraki replay çalışmaları da
pakette `SONRAKİ ARAŞTIRMA` olarak işaretlenir. Plan/çıktı: [context API planı](ALARM_CONTEXT_API_PLANI.md)
ve [ASTOR örneği](samples/ALARM_CONTEXT_ASTOR_2026-10-16.md). Sonraki denemede aynı kesit
ASTOR, THYAO, GARAN, ASELS, SISE, TUPRS, BIMAS, EREGL, FROTO ve SNGYO için on ayrı
JSON packet olarak üretildi; sembole özgü 4h breakout replay'i `replay_evidence.symbol_specific`
altına ayrı ve `available_at_snapshot=false` olarak eklendi. [10 sembol yorum raporu](samples/ALARM_CONTEXT_10_SEMBOL_INCELEME_2026-10-16.md)
ve [10 JSON çıktısı](samples/ALARM_CONTEXT_10_SEMBOL_2026-10-16.zip). Bu deneme live alarm,
depolama, Telegram veya Supabase davranışını değiştirmez.

## 8. 2026-11-06 — sonraki araştırma için yalnızca kullanıcı notu

Kullanıcının güçlü mum beklenen normal destek yukarı oklarıyla ilgili gözlemi,
BOS aşağı yönü ile okun ve destek kırılmasının ilişkisi hakkındaki hipotezi ve
dikey/yatay mantığıyla daha sonra denemek istediği küçük direnç görselleştirmesi
[bekleyen araştırma notlarına](STABIL_BEKLEYEN_ARASTIRMA_NOTLARI_2026_11_06.md)
kaydedildi. Kullanıcı bu aşamada yalnız kayıt istedi: yeni replay, BOS filtresi,
dirence ilişkin görsel deneme veya canlı kural değişikliği yapılmadı.

## 9. 2026-11-06 — kullanıcının tanımına göre 50 hisselik direnç replay'i

Kullanıcı destek modelinin ters yönlü direnç tarifini onayladı; kırılmadan sonra
eski çizgi sabitken fiyatın dönüşü ile çizginin yukarı takibi, ayrıca temas,
kapanış ve sonraki hareketin ayrı ölçülmesini istedi. Aynı veri ve aynı simetrik
araştırma kurallarıyla 50 hisse replay edildi: [odak raporu](stabil_direnc_50_model_testi_2026_11_06/RAPOR_50.md),
[plan](stabil_direnc_50_model_testi_2026_11_06/PLAN.md) ve
[doğrulama](stabil_direnc_50_model_testi_2026_11_06/DOGRULAMA.md).

Sonuçlar bazı benzerlikler gösterse de kullanıcının grafikteki dikey/yatay
sırasını ispatlamıyor; özellikle fiyat yeni direncin üstündeyken görülen yolun
örneklemi küçük. Bu, sonradan istenirse görsel olarak da doğrulanacak bir açık
noktadır. Bekleyen güçlü mum, BOS ve görsel notları §8'deki yerinde duruyor;
bu turda BOS filtresi, yeni görsel, canlı aktivasyon, alarm veya dağıtım yok.

## 10. 2026-11-07 — bağımsız direnç ve ters ok katmanı, ilk iki adım

Kullanıcının yalnız ilk iki adım için verdiği onayla, mevcut desteği değiştirmeden
`domain_engines/stabil/resistance.py` içinde native teyitli günlük direnç,
renk rolleri, kapanışa projeksiyon ve ters ok/yapı uyarısı hazırlandı. Üç barlık
momentum tekrar kısıtı korundu; pivot sonrası keyfî bekleme, dirence özel alarm
veya BOS filtresi eklenmedi. Ayrıntılar ve veri-kalitesi sınırları:
[uygulama ön kontrolü](../tasarim/STABIL_DIRENC_CANLI_TEST_ON_KONTROL_2026-11-06.md).

Sentetik ayna/nedensellik testleri ve daha önce incelenen EFOR/AKBNK örnekleri
başarılı; destek ve grafik regresyonları da tekrar kontrol edildi. Bu ilk iki
adımın sonunda katman **grafiklere bağlı veya canlıda değildi**. Sonraki yerel
bağlantı için §11'e bakın; canlı test ve BOS/tekrar-kısıtı araştırması ayrıdır.

## 11. 2026-11-07 — direnç katmanını mevcut grafiklere yerel bağlama

Üçüncü adım kullanıcı isteğiyle planlandı ve bağımsız direnç, kaynak/kalite
köprüsünden geçirilerek `/grafik`, formasyon, Stabil destek ve domain alarm
karelerine eklendi. Kesikli direnç desteğin yerini almaz; ters renkler, aşağı
oklar ve yukarı aday yapı uyarısı yalnız motorun kendi sınıflandırmasını izler.
Günlük kaynak veya saatlik bileşenler doğrulanamazsa yalnız direnç gizlenir;
mevcut alarm kararı ve destek kartı değiştirilmez. Otomatik grafik anahtarı
kapalıyken direnç hesabı yapılmaz; manuel `/grafik` bundan bağımsızdır.

EFOR ve AKBNK gerçek arşiv görüntüleri yerel olarak incelendi; komut, alarm
karesi, JSON/kuyruk ve sahte taşıma entegrasyonları test edildi. Bunlar canlı
Telegram teslimi veya kârlılık kanıtı değildir. Eksik native günlük kaynakta
manuel `/grafik` yeni bir günlük ağ isteği yapmaz; ayrıca kaynakta görülmeyen
her veri hatası saptanamaz. Sade görünüm iki Stabil katmanını da gizler; uzak
seviyeler mevcut kadraj politikasında görünmeyebilir.

Kaynak kontrolleri, örneklerin kesin kapanışları, test sınırları ve dağıtım
öncesi kalanlar [3. adım notunda](../tasarim/STABIL_DIRENC_CANLI_TEST_ON_KONTROL_2026-11-06.md#3-adım-uygulanan-yerel-bağlantı-ve-sınırları-2026-11-07).
Bu adımda yeni direnç alarmı, BOS filtresi, ek bekleme, Telegram gönderimi veya
canlı dağıtım yoktur.

Son kodun ve public kuyruk kalıcılığı testlerinin Python 3.11.2 ile tek, temiz
tam regresyonu **3.979 başarılı, 43 atlandı**. Dört tarihsel araştırma
doğrulayıcısı da başarılı; Python 3.12 CI, gerçek Telegram teslimi ve canlı
dağıtım bu yerel çalışmanın dışındadır.

## 12. 2026-11-07 — gerçek arşivle görsel ve teslim denetimi

Kullanıcının ayrıntılı kontrol isteği üzerine gerçek tarihsel arşivle `/grafik`
komut işçisi, normal formasyon taraması, Stabil destek ve domain adayları,
notifier/outbox ve gerçek PNG üretimi birlikte sınandı. **15 uçtan uca senaryo
başarılı**; ağ ve Telegram taşıması sahte, tarih ve cache tazeliği tarihsel
simülasyona göre kontrollü. Seçilmiş 12 görsel, mesaj/metadata kanıtları ve
hangi durumda neyin gönderilip gönderilmediği:
[ayrıntılı görsel ve teslim denetimi](../tasarim/STABIL_DIRENC_GORSEL_TESLIM_DENETIMI_2026-11-07.md).

Gerçek AKBNK formasyon kırılımında DM dört/public iki kare; 23 Mart gerçek
Stabil geri alımında DM yalnız metin, public 4s+1g; gerçek DOCO CHoCH'ta DM
dört/public iki kare denetlendi. Gerçek AKBNK retest adayı mevcut kapanış
sınırı kapısında reddedildi. Aynı taramada bağımsız Stabil ve domain olayları
ayrıca ortaya çıkabildi. Dört gerçek 4s domain adayıyla yapılan seçili burst
denemesinde iki tekil kart ve grafik, kalan adaylar için grafik içermeyen özet
üretildi. Geçersizleşme olayı ise açıkça kontrollü olarak enjekte edildi.

Önemli sınırlar: `sade` her iki Stabil katmanını gizler; hazır ama kadraj dışı
direncin otomatik altyazıda her zaman açıklaması yoktur. Tam taramadaki izole
Stabil geri alımında, önceden domain cache olmadığı için public günlük karede
eski destek katmanı yokken bağımsız direnç çizildi; bu eski destek akışı
sessizce değiştirilmedi. Medya sonucu belirsizliği, teslim kanıtı olmaksızın
incelemeye işaretlendi. Render Dashboard, gerçek Telegram ve deploy hâlâ
kontrol edilmedi; BOS/ok etkisi replay araştırması ertelenmiş durumdadır.

Bu ayrıntılı denetimden sonraki tek tam regresyon **4.057 başarılı, 43 atlandı**
(Python 3.11.2, çıkış kodu 0); `ruff check .` ve `git diff --check` başarılı.
