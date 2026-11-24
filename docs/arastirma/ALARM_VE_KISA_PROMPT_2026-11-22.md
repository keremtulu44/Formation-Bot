# Klasik formasyon + Stabil ve kısa grafik promptu

## Alarm geçmişi ve seçilen dönüş

- Klasik formasyon bildirimleri `bot/scan.py` yolundadır; ayrı Stabil alarmı
  1 Kasım'da (`5e1ff435168a`) eklenmiştir. Yeni domain kartı 3 Kasım'da
  (`90c1a6915cef`) ayrı bir kanal olarak eklenmiş, formasyon tetikleri de
  aynı gün (`ad85fff1661e`) bu kanala alınmıştır.
- GitHub Actions keep-alive koşularında 9 Kasım'daki `284548c54774` commit'i
  22 Kasım'a kadar görünür; o commit'in config varsayılanları hem Stabil hem
  yeni domain kartını açık tutar. Workflow commit'i Render'ın çalıştırdığı
  sürümün kanıtı değildir. Bu yüzden kesin bir canlı çalışma süresi iddia
  edilmez. Kullanıcı bu ayrım sonrasında **klasik formasyon + Stabil** seçti.
- Değişiklik eski commit'i bütünüyle geri yüklemez: klasik anlık/digest
  state listeleri ve Stabil korunur, yeni domain kartı varsayılanı kapatılır.
  P6 ve cooldown/kalite düzeltmeleri kodda kalır; `P0` domain filtresiz
  politikasıdır, klasik alarm düzeni değildir.
- Yeni kartlar `YENI_DOMAIN_ALARM=1` ile yeniden açılabilir. Dağıtımda veya
  `.env` içinde bu değişken zaten `1` ise yeni varsayılan onu **ezmez**;
  istenen düzen için operatörün ortamda `YENI_DOMAIN_ALARM=0` ayarlayıp ilgili
  dağıtımı güncellemesi gerekir. Stabil'i ayrıca etkileyen ortam/kanal
  ayarları değiştirilmedi.
- DM ve public yardımcı outbox'larda, kesin gönderilmemiş eski domain kartları
  ve gönderilmiş metnin bekleyen görselleri kanal kapalıyken gönderilmez;
  saklanır, Stabil işini engellemez. Kanal açılırsa normal TTL/hedef kontrolleri
  devam eder. Belirsiz teslimler otomatik tekrarlanmaz. Ortam ayarı/deploy ve
  geçmiş bekleyen kayıtların durumu bu yerel değişiklikle doğrulanmış değildir.

## Prompt

`ai_prompt` hâlâ ağsız, bağımsız bir deneme aracıdır; Telegram veya bir AI
servisine bağlanmadı. Grafik ile ortak seçilen dış, teyitli, geçerli ve kadraj
içindeki BOS/CHoCH olayları kullanılır; sweep, iç yapı ve çizilmeyen geçiş
başarısızlığı promptta yer almaz. Aynı dört TF ve tüm görünür seçili OB/FVG
bölgeleri, ana TF temas replay'i, geçerli destek replay'i, ilgili ve tarih
etiketli genel araştırma, veri/hesap belirsizlikleri korunur. Grafik şeridinin
RVOL kaynağı yazılır; yerel yedek motor sonucu olarak sunulmaz.

Bu grafik görünümü **planlanan normal render** esasındadır: çizim hatası,
piksel yerleşiminde kesilen etiket veya başka çağrı seçenekleri otomatik
kanıtlanmaz. Kullanıcıya özel gösterilen bir gerçek alarmla eşleştiği iddia
edilmez. Geriye dönük örneklerin araştırma sonuçları, kesit zamanında biliniyor
sayılmaması için ayrıca etiketlidir.

| 25 Eylül yerel kesiti, 4s | Eski v5 | Yeni v7 |
|---|---:|---:|
| BIMAS | 10.997 | 6.160 |
| ALARK | 11.539 | 6.772 |
| PETKM | 10.228 | 5.724 |

2–6 bin karakter hedefi, önemli görünür kanıtları sessizce kesen zorunlu
limit değildir. 28 sembolün v7 taramasında aralık 3.979–7.132 karakterdir.

## Doğrulama

- Tüm testler, son outbox kapasite ve direnç köprüsü ekinden önce: **4.924
  geçti, 43 atlandı**. Sonrasında alarm/outbox/grafik seçkisi **150**, prompt
  seçkisi **43** geçti. İki görünüm modunda BIMAS'ın dört gerçek renderer sonucu
  olay, dış seviye ve bölge sayılarıyla karşılaştırıldı; sentetik uzak olay
  ve sade görünüm de sınandı. Native günlük veriyle görünür 4s Stabil direnç
  ayrıca gerçek renderer sonucu ile karşılaştırıldı.
- 28 sembol, 112 TF: 241 seçili bölge, 241 eşleşen replay, 0 atlanan bölge,
  hata 0. Bu tarama tek başına her PNG'nin piksel karşılaştırması değildir.
- Uzun günlük arşivde Stabil referansı: 13.020 kesit, 11.543 bilinen sıra,
  507 temas günü, hata 0. Gerçek model yanıtı veya canlı gönderim test edilmedi.

Yerel çalışmadır; commit, push veya deploy yapılmadı.
