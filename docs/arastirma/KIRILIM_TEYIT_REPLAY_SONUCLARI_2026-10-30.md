# Kırılım ve teyit Replay araştırması — 30 Ekim 2026

**Birleştirilmiş kapsamlı kayıt:** [Aday ve teyit sonrası karşılaştırmalar, tüm tablolar, veriler ve yöntem](KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md).

## Sonuç ve kapsam

174 arşiv hissesi × 1s/2s/4s/1g = **696 serinin tamamı** işlendi; seri hatası yok. Burada **s = saat, g = gün**. Veri tüm BIST'i temsil etmez; kayıtların son günü 19 Ekim 2026. Bu, **gerçek bildirim veya teslimat kaydı değil**, geçmiş OHLCV üzerinde kuralların araştırma amaçlı yürütülmesidir. Canlı kural, eşik, bildirim ve ham veri değiştirilmedi.

**Ana bulgular:**

1. Ölçülen teyit kontrollerinde bağımsız skor hesabı ve seçili karar değişmezleriyle bariz bir aritmetik uyuşmazlık bulunmadı. Bu, tüm motorun, Pine'ın veya gerçek canlı teslimatın doğrulandığı anlamına gelmez.
2. Filtrelenmiş 15.947 teyidin **12.163'ü ilk**, 3.784'ü ikinci sonraki mumda geldi; medyan bir mum. Aday başlangıcından teyit kapanışına yönlü hareketin medyanı yaklaşık **0,21 ATR**. Bu bir işlem getirisi, kalan hareket veya anlık bildirim gecikmesi değildir.
3. 3.577 filtrelenmiş teyit alamama olayının 16'sında (%0,4) ilk iki kapanıştan biri, 716'sında (%20,0) sonraki on kapanışın en az biri yönlü +2 ATR'ye ulaştı; 526'sında (%14,7) onuncu kapanış hâlâ en az +2 ATR idi. Teyit alamamak her zaman fiyatın ilerlemediği anlamına gelmiyor; fakat bu olayların tümüne erken sinyal verilmesi gerektiği de kanıtlanmış değil.
4. İleri dönemde yön ve zaman dilimi farklılaştı. Örneğin 4s aşağı teyitli adaylarda yol içi +2 ATR **186/377 (%49,3)**, 4s yukarıda **110/426 (%25,8)**. Aynı 4s yukarı oranı keşifte **415/960 (%43,2)** idi. Rejim farkı ve çoklu seçim riski nedeniyle bu yüzdeler sabit başarı olasılığı değildir.
5. Veri kalitesi önemli bir sınır: 1s kaynakta **59.604/558.724 sıfır hacim** var; 59.342'si 09:30 etiketli. Bunun gerçekten işlemsizlik mi yoksa kaynak eksikliği mi olduğu bilinmiyor. Motor sıfır hacimde ilgili skora nötr değer kullanıyor, ayrıca sıfırlar hacim ortalamasını etkileyebilir. Bundan dolayı hacim temelli kararların doğruluğu yalnız bu Replay ile kesinleştirilemez.

## Tasarım

- Her seri için ilk %70 bar keşif, son %30 ileri dönem. Sınır hisse ve TF'ye göre belirlenir; tek bir ortak takvim tarihi değildir. Keşif adayının 10 mumluk hedefi ileri döneme taşıyorsa sonuç `BOUNDARY_PURGED`. Geçmiş formasyon durumu ileri döneme taşınır, çünkü karar anında bilinen geçmiş buna dahildir.
- Kapanış anındaki aday/deneme başlangıcı kaydedilir. **Başlangıç kapanışı ve o andaki ATR sabit**: sonraki on tamamlanmış varsayılan barın kapanışlarından yönlü +2 ATR'ye ulaşma, −2 ATR'ye ulaşma ve onuncu kapanış ölçülür. Yol içi iki yön de görülebilir; sıraları veya mum içi yüksek/düşük, işlem maliyeti ve gerçekleşebilir fiyat burada ölçülmez.
- Aynı hisse/TF içinde seçilen adayın on mumluk hedef penceresi bitmeden gelen aday ikinci kez seçilmez. Ham dosyada bütün adaylar saklanır; özetler `VALID` ve `nonoverlap=true` üzerinden hazırlanır. Farklı hisseler ve piyasa günleri yine bağımsız değildir.
- Kontrol: temiz segmentlerde 80 mum ısınma sonrası ilk ızgara noktası da atlanarak her 10 mumda, kaydedilmiş kırılım adayının o anda sürmediği anlar. **Eşleştirilmiş veya rastgele kontrol değildir**; aktif formasyonun tamamen yokluğunu, piyasa rejimi veya hisse eşleşmesini garanti etmez. Seçim kuralları farklı olduğundan adaylarla nedensel karşılaştırma yapılamaz.
- Bozuk OHLC ve önceki kapanışa göre %30'u aşan sıçrama karantinaya alınır; sonraki temiz parçada ATR/motor baştan başlar. Bu yaklaşım şirket işlemlerini teşhis etmez ve doğru veriyi de dışlayabilir. Her temiz parçanın başında 80 bar ısınma uygulanır. 2s/4s, repodaki 09:30 seans çapalı 1s dönüşümünden üretilir ve son türetilen kova ihtiyatla atılır. 1s/1g son yerel mumun hedefe denk geldiği dört aday ayrıca sansürlendi; son mumun tamamlandığı ispatlanmış değildir.

## Kapsam ve sansür

| Ölçü | Sayı |
|---|---:|
| Ham aday/deneme | 25.457 |
| Teyitli / teyit alamadı / başarısız kırılım | 18.752 / 4.776 / 1.907 |
| Sonu veya veri kesintisinde yaşam döngüsü sansürlü | 22 |
| 10 mum sonucu geçerli | 25.133 |
| Dönem sınırı / seri sonu / veri kırılması / son mum belirsizliği | 156 / 152 / 12 / 4 |
| Geçerli ve aynı seri içinde örtüşmeyen aday | 21.244 |
| Eşleşmemiş kontrol penceresi | 99.944 |
| Kalite nedeniyle işaretlenen barlar, TF toplamı | 48 |

48 sayısı aynı kaynak kusurunun farklı TF'lerde sayılmasını içerir; 48 bağımsız şirket işlemi veya olay demek değildir. Kontrollerde ayrıca 650 dönem sınırı, 700 segment sonu ve 3 son yerel mum hedefi sansürlendi; 6.834 ızgara noktası o anda kaydedilmiş aday sürdüğü için çıkarıldı.

## İleri dönem: yön ve zaman dilimi ayrı

Tablodaki **yol**: adaydan sonraki 10 kapanıştan herhangi birinde yönlü ≥2 ATR; **son**: 10. kapanışta yönlü ≥2 ATR. Paydalar örtüşme filtresi sonrası geçerli adaylardır. `Teyitsiz` yalnız süresi dolan `KIRILIM_TEYIT_ALAMADI` grubudur; `BASARISIZ_KIRILIM` ayrı tutulur ve ayrıntılı CSV'dedir.

| TF | Yön | Teyitli n | Teyitli yol | Teyitli son | Teyit alamadı n | Teyit alamadı yol | Teyit alamadı son |
|---|---|---:|---:|---:|---:|---:|---:|
| 1s | Yukarı | 1.062 | %27,4 | %17,7 | 298 | %16,8 | %13,4 |
| 1s | Aşağı | 1.237 | %32,7 | %22,9 | 234 | %22,6 | %18,8 |
| 2s | Yukarı | 631 | %27,7 | %17,4 | 197 | %15,7 | %12,7 |
| 2s | Aşağı | 672 | %38,8 | %29,0 | 100 | %30,0 | %28,0 |
| 4s | Yukarı | 426 | %25,8 | %13,1 | 149 | %15,4 | %8,7 |
| 4s | Aşağı | 377 | %49,3 | %37,4 | 65 | %30,8 | %21,5 |
| 1g | Yukarı | 215 | %30,7 | %15,3 | 64 | %23,4 | %18,8 |
| 1g | Aşağı | 219 | %31,5 | %23,7 | 17 | %29,4 | %23,5 |

Bunlar teyidin **sonradan gözlenmesine koşullu** gruplar; teyit anında girilen bir strateji, ileri dönemde sabitlenmiş sinyal başarısı veya canlı yatırım sonucu değildir. Günlük aşağı teyit alamadı grubunda yalnız 17 olay var.

Aynı dönemde eşleşmemiş kontrol yol oranları sırasıyla: 1s yukarı/aşağı %20,6/%28,7; 2s %22,4/%30,2; 4s %20,9/%32,2; 1g %23,1/%29,0. Bu kontrollerin zamanları ve adayların zamanları eşleşmediğinden farkları teyidin katkısı olarak yorumlanamaz.

## Matematik ve zamanlama denetimi

- **45.255** takip kontrolünde, motorun kullandığı sınır, OHLC, tolerans ve hacim girdilerinden skor ve bileşenler bağımsız yeniden hesaplandı. Maksimum sayısal fark **1,82 × 10⁻¹²**; 10⁻⁹ üstü fark yok. Seçili teyit penceresi/tetikleme değişmezleri bu kontrollerin tamamında sağlandı. Kontrollere ısınmadaki bazı takipler de dahildir; bunlar olay tablosuna aday olarak alınmamıştır.
- Aday dosyasındaki 18.752 teyidin 9.930'unda yalnız güçlü aynı-yön koşulu, 4.755'inde yalnız retest, 4.067'sinde ikisi birlikte sağlandı. Güçlü koşul için yalnız puanın eşiği aşması yetmez; kapanışın tampon dışındaki aynı tarafta olması da gerekir. Bu ayrım düzeltilmiştir: önceki 4.713/4.109 sayımı 42 eşiği geçen fakat kapanışı tampon dışına çıkmayan retesti yanlışlıkla iki koşulun da sağlandığı gruba koyuyordu. Bunlar motorun gözlenen girdileriyle yapılan mekanizma sayımıdır.
- Denetim, tüm formasyon seçimini, başlangıç skorunun her bileşenini, tüm durum geçişlerini, sağlayıcının gerçek hacmini, Pine ile uyumu veya canlı Telegram teslimini bağımsız ispatlamaz. Teyit eşiği ve tamponları araştırmada değiştirilmedi.
- **THYAO 12 Haziran 1g**: 307,75 aday, ATR 8,4564. 15/16 Haziran takip skorları 33,01/35,55; eşik 44, retest yok. 17 Haziran pencere dolarak teyit alamadı. Onuncu kapanış +2,72 ATR. Bu tek örnekte mekanizma açıklanıyor, hata veya işlem fırsatı olduğu ispatlanmıyor.

## Kritik Replay sızıntısı ve kalan eşdeğerlik sınırı

İlk prototipte tüm uzun seri tek seferde motora verilince, bazı tarihçe sınırları `len(close)` üzerinden **sonradan gelen seri uzunluğundan** etkilendi. Örneğin THYAO 1s'de 17 Aralık 2025'e kadar aday sayısı, korumasız uzun seri yürütmesinde 66 iken gerçek önek yürütmesinde 38 idi. Bu, geçmişi uzun frame üzerinde doğrudan olay sayarak Replay yapmanın güvenli olmadığını gösterir; tek başına canlı botun gelecekteki fiyatı gördüğünü kanıtlamaz.

Araştırma sarmalayıcısı her bar işlenirken OHLCV/ATR dizilerini yalnız o ana kadar görünür kılar; canlı motor değiştirilmedi. **1.453 örnek önek karşılaştırmasında** aday zamanı/türü/yönü/formasyonu farklı çıkmadı. Ayrıca uzun seride gelecek verisini değiştirme testi ve üç örnekte gerçek tek tek artımlı yürütme karşılaştırması geçti. THYAO/ASTOR/AKBNK/GARAN'da bazı 360 bar yeniden kurulum örnekleri de incelendi. Bunlar örneklerdir; tüm olayların canlıdaki her taramada `tam_yeniden=True` ve kayan pencereyle birebir aynı olduğunun kanıtı değildir. Gerçek canlı kayıtlar ve tam rolling karşılaştırması ayrı çalışma gerektirir.

## Veri kalitesi: özellikle hacim ve seans kovaları

- Yerel 1s veride 59.604 sıfır hacmin 59.342'si 09:30 etiketlidir; bütün 174 hisse en az bir 1s sıfır hacim içerir. 1g'de 86.945 mumun 170'i sıfır hacimli ve 8 hisseye yayılmıştır. Bu, eksik veri veya gerçek sıfır işlem ayrımını yapmaz; ham değerler değiştirilmemiştir.
- Kullanılan 311.277 adet 2s kovasının 64.051'inde yalnız **bir** kaynak 1s etiketi var. 186.625 adet 4s kovasının 63.191'inde dörtten az kaynak etiketi var. Seans sonu kısa kovaları meşru olabilir; bu sayılar tek başına hata değildir. Tarihsel yarım günler, iç eksikler, tatiller ve kaynak mumlarının kapanış anları bağımsız takvimle doğrulanmadı. 2s/4s karşılaştırması bu nedenle ihtiyatlıdır.
- Kaynakta negatif/eksik hacim 348 yerel hisse serisinde görülmedi; **sıfırın doğru olduğu doğrulanmadı**. %30 filtresi şirket işlemleri veya bütün veri hatalarının tespiti değildir.

## Ne yapılmalı?

1. Hacim sıfırlarının kaynağını ve 09:30 mum semantiğini bağımsız sağlayıcı/ham kayıtla doğrula; sonuç belli olmadan hacim eşiğini veya canlı davranışı değiştirme.
2. Tatil/yarım gün takvimi ve 1s iç boşluklarını denetle; seans sonu kısa 2s/4s kovalarını sınıflandır. Kaynak kapanışını kanıtlamadan tamamlanmış sayma.
3. Kaydedilmiş canlı bar, rolling rebuild, motor durumu, alarm kararı ve Telegram teslimini aynı olay kimliğiyle karşılaştır; artımlı araştırmayı canlıya eşitleme.
4. Erken teyit için yeni bir hipotez ancak sabitlenmiş keşif, zaman ve hisse dışı doğrulama, negatif kontroller, yanlış/kaçan alarm ve bildirim sayısı incelendikten sonra **gölge modda** sınansın. Bu çalışmanın tabloları tek başına eşik değiştirme gerekçesi değildir.

## Dosyalar ve tekrar üretim

- [Adaylar](sonuclar/kirilim_replay/adaylar.csv.gz), [teyit kontrolleri](sonuclar/kirilim_replay/teyit_kontrolleri.csv.gz), [aday özeti](sonuclar/kirilim_replay/ozet.csv).
- [İlk iki mumun aday bazlı sonuçları](sonuclar/kirilim_replay/iki_mum.csv.gz), [iki mum özeti](sonuclar/kirilim_replay/iki_mum_ozet.csv).
- [Kontrol pencereleri](sonuclar/kirilim_replay/kontroller.csv.gz), [kontrol özeti](sonuclar/kirilim_replay/kontrol_ozet.csv), [kontrol kapsamı](sonuclar/kirilim_replay/kontrol_manifest.json).
- [Kaynak hacim profili](sonuclar/kirilim_replay/kaynak_veri_profili.csv), [türetilmiş kova profili](sonuclar/kirilim_replay/kova_veri_profili.csv), [kaynak/kod hashleri ve seri kapsamı](sonuclar/kirilim_replay/manifest.json).
- [Araştırma planı](KIRILIM_REPLAY_PLANI_2026-10-30.md). Çalıştırılan bağımlılıkların SHA-256 özeti manifesttedir; checkpoint yazılma aralığı gerçek başlangıç saati değildir.

```bash
mkdir -p var
WORKDIR=$(mktemp -d var/kirilim-replay-XXXXXX)
python scripts/kirilim_replay.py --workers 2 --workdir "$WORKDIR"
python scripts/kirilim_sonuc_sansuru.py --workdir "$WORKDIR/checkpoints"
python scripts/kirilim_kontrolleri.py
python scripts/kirilim_iki_mum.py
python scripts/kirilim_veri_profili.py
python -m pytest -q test_kirilim_denetim.py
```

Checkpoint'ler yeniden başlatmayı hızlandırmak içindir. Otomatik geçersizleştirme yerel 1s/1g verisini ve iki ana araştırma dosyasını kontrol eder; motor/config gibi diğer bağımlılıklar değişirse eski checkpoint'ler otomatik geçersizleşmez. Bu yüzden tam tekrar için yukarıdaki gibi yeni bir çalışma dizini kullanılır. Araştırma dosyaları canlı bota bağlanmaz.
