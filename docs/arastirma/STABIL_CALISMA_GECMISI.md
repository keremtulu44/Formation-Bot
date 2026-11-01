# Stabil çalışma geçmişi — konuşma kaydı ve kanıt sınırı

**Belgeleme:** 2026-11-01. [Ana rehber](STABIL_REHBERI.md) · [dosya envanteri](STABIL_DOSYA_ENVANTERI.md).

> Aşağıdaki tamamlanma/test/süre/sayılar **önceki konuşmada raporlanan kayıtlardır**.
> Bu checkout'ta eski kod, tam sonuç tabloları ve paket yoktur. Sayılar yeniden
> hesaplanmadı; tarihsel anlatım bağımsız kanıt veya şu an çalışan özellik değildir.

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
motor çağrısı olmadan birebir geri kurulması raporlandı. O paket **bugün yok**.

77 test, 700 çalışma dosyası kontrolü ve paket doğrulamaları bugünkü bu belge
kontrolüyle aynı şey değildir. Yeni dokümanların kontrol sonucu, eski native
çalışmanın yeniden doğrulanması diye sunulmayacak.

## 6. Bu güncellemede gerçekten yapılan

- Gerçek checkout, Git geçmişi/nesneleri, dosya yolları ve yükleme alanı denetlendi.
- Özgün TXT bulundu, depoya aynen alındı ve SHA256 eşitliği doğrulandı.
- Model, soru sicili, yöntem/geçmiş ve dosya durumları konuşmadan kaydedildi.
- Mevcut README/belge/araştırma/devir haritalarına gerçek bağlantılar eklendi.
- Eksik runtime/raporların yerini uydurma Python, JSON veya sahte paketle
  doldurmak yerine kurtarma ihtiyacı açık bırakıldı.
- Yeni replay, provider veri çekimi, Telegram veya Supabase işlemi yapılmadı.
