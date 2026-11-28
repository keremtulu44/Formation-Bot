# Nedensel alarm replay'i: seçilenler, bastırılanlar ve gecikme

> **Sonraki uygulama:** [OB alarmının olay seçimi](ALARM_OLAY_SECIMI_OB_2026-11-27.md). Bu rapor ve v2 aday akışı, OB için eski fiyat-içi koşulunu tarihî karşılaştırma tabanı olarak korur; yeni OB kuralıyla güncel canlı-parite iddiası değildir.

**27 Kasım 2026 · Kayıt / araştırma.** Önceki [sistem ve filtre denetiminin](ALARM_DENGESI_VE_REPLAY_DENETIMI_2026-11-27.md) devamıdır.
**Amaç:** alarm sayısını azaltmak değil; anlamlı olayları zamanında, anlaşılır ve gereksiz yere bastırmadan göstermek.
**Bu aşamada:** araştırma replay'i ve testleri düzeltildi; canlı politika/eşik/teslim davranışı değiştirilmedi. Commit/push/deploy, Telegram gönderimi veya Supabase yazımı yapılmadı. Önceki mum/AI/teslim çalışmaları korunmuştur.

## 1. Sonuç ve karar

- **Nedensel aday üretimi onarıldı:** 50 sembol × 4 native TF = **200 seri**, **200/200 önek eşitliği**, **0 domain hatası**. Her mumda o anda mevcut domain dışa aktarımları ve canlı kanal koşulları kullanılıyor. Son durumdan geçmişe olay uydurulmuyor.
- **P6'nın kaliteyi artırdığı bu örneklemde gösterilemedi.** Seçilen ve ölçülebilen olaylarda ilk lehte ±1 ATR bariyeri oranı P0'da **669/1.222 = %54,75**, P6'da **257/521 = %49,33**. P6'nın politika nedeniyle bastırdığı ölçülebilen satırlarda **1.738/3.148 = %55,21**. Bunlar bağımsız işlem başarıları veya istatistiksel üstünlük testi değildir.
- **Bastırılanları gözden kaçırmamak gerekiyor.** P0'ın gösterdiği fakat P6'nın aynı mumda göstermediği 1.408 olayın 933'ü ölçülebiliyor; **520'sinde ilk bariyer lehte**. Buna karşılık P6'nın kendi cooldown takvimiyle eklediği 353 olayda 232 ölçülebilir, 108 ilk-lehte var. Net sayı farkını “gürültü temizliği” diye açıklayamıyoruz.
- **Yön dengesi sorunlu:** P0 seçimi 733 aşağı / 670 yukarı / 377 yönü belirsiz-çelişkili; P6 seçimi **94 aşağı / 472 yukarı / 159 belirsiz-çelişkili**. Önceki denetimde saptanan pozitif fiyat koşusu kapısı ile uyumlu. Yön karışımı farkı kalite karşılaştırmasının da bir parçası; tüm farkı filtre etkisine nedensel olarak atfetmiyoruz.
- **Cooldown yalnızca kopya olayları susturmuyor.** P6'nın cooldown ile bastırdığı 1.275 satırın 816'sında son seçime göre kategorik bağlam değişmiş; 459'unda aynı kategorik imza var. Ancak aynı imza bile yeni bir fiyat seviyesini saklayabilir. Bu yüzden 459'u “kesin tekrar”, 816'yı “kesin yeni fırsat” saymıyoruz.

**Karar:** P4'e geçişi veya yeni sert kapı eklemeyi destekleyen kanıt yok. P6'yı körlemesine kaldırma ya da cooldown'u tamamen açma önerisi de yok. Öncelik, yön asimetrisini ve gerçek yeni-olay kimliklerini gölge karşılaştırmada sınamak; ardından üç canlı alarm yolunun teslim defteriyle kapsamı doğrulamak. Daha az alarm kendi başına başarı değildir.

## 2. Tam olarak ne onarıldı?

Yeni kod:

- `research/causal_alarm_replay.py`: MS/OB/FVG/hacim motorları tek ileri geçişle ilerler. Her bardaki dışa aktarım canlı `bot/domain_alarm_service.py` kanal yardımcılarına verilir; 1h'de FVG eklenmez. Formasyon, yalnız kendi özel motor örneği üzerinde gözlenir; sınıf çapında monkeypatch yoktur.
- Formasyon motorunun kimlik deposu anahtarı bilerek **None** tutulur: canlı kimlik depolarına okuma/yazma yapılmaz. Rastgele UUID yerine deterministik, seriyle ayrıştırılmış araştırma kimliği kullanılır.
- `BOS ↓` artık ölçümde aşağıdır. Yönsüz hacim veya çelişen yönler kendiliğinden yukarı yapılmaz. Gelecekte doğacak bölge yön kaynağı olamaz.
- Karar snapshot'ları ile 12 bar sonraki sonuç etiketleri ayrı katmandadır; politika/cooldown gelecek sonuçları okumaz.
- `research/alarm_recall_study.py`: P0/P6/P4/P7 için ayrı cooldown; politika önce, altı bar cooldown sonra. Değerlendirme penceresinden önceki olaylar cooldown durumunu kurar.
- `research/alarm_recall_breakdown.py`: yön/TF/kanal kırılımı, son seçime göre kategorik değişim, aynı formasyondaki gecikmeli seçimler ve deterministik örnekler.

**Nedensellik kontrolü:** her 480 barlık seri yeniden ilk %75'lik önekiyle çalıştırıldı; bu kesitten önceki tüm karar snapshot'ları birebir aynı: **200/200**. Ayrıca testte dört TF'de gelecekteki OHLC değiştirilse de geçmiş kararları değişmiyor. Bu, test edilen karar akışının nedenselliği için kanıttır; bütün canlı tarama/teslim hattının birebir simülasyonu değildir.

### Açık kapsam sınırları

1. Adaylar **canlı Stabil destek/mesafe kapısından önceki domain kanal adaylarıdır**. Ana formasyon, Stabil geri-alım ve domain yolunun birleşik canlı simülatörü değildir.
2. Üretimin kayan geçmiş penceresi yerine sabit başlangıçlı son 480 native bar kullanılır. Öncesindeki formasyon yaşam geçmişi bilinmez. Tarama düzeyindeki geçersizleşme bildirim alias'ı gözlemciye dahil değildir.
3. Canlı tarama saatleri, tazelik, hedef/MTF birleştirmesi, hız limitleri, Telegram paketleme ve teslim/receipt yoktur. Buradaki olay/seans, DM veya grup mesajı/gün değildir.
4. Olaylar çakışır, koreledir ve aynı hareketi birden fazla satır ölçebilir. İşlem maliyeti/PnL veya piyasa üzerinde nedensel etki ölçülmedi. “İlk lehte bariyer” operasyonel bir gösterge; kârlı işlem tanımı değildir.
5. Arşiv daha önce araştırıldı. Kronolojik iki parça **kör holdout değildir**; yeni eşik seçmek için ileri test sayılamaz.

## 3. Veri ve ölçüm sözleşmesi

- **50 sembol, 1h/2h/4h/1d native 200 seri**, her seride en fazla 480 mum; 2h/4h yeniden örneklenmedi.
- Ortak pencere **19 Ekim–18 Kasım 2026, 22 İstanbul seansı**. Sıfır olaylı seanslar ortalama paydasında. Kaynak çekiminin başlangıcından önce kapandığı doğrulanamayan mumlar dışarıda.
- Tam geçmişte **35.071 aday**, pencerede **6.907 aday**. Birim sembol × TF × bar; aynı olay iki ayrı yön satırına çoğaltılmaz.
- Pencere aday yönü: 5.280 açık, 1.391 bilinmiyor, 236 çelişkili. Bilinmiyor/çelişkili olaylar sayımda kalır, yönlü kalite paydasına alınmaz.
- Arşiv dışında kalan aktif semboller: BRENT, USDTRY, XAGUSD, XAUUSD, XBANK, XU50, XUSIN. Çalışma anındaki üretim env/evreninin kanıtı değildir.
- Koşu **428,54 sn**, 0 domain hatası. Hata veya önek farkında tamamlanmış evren raporu yayımlanmaz.

**Sonuç tanımı:** olay mumunun kapanışı referans; o anda hesaplanan Wilder ATR dondurulur. Sonraki 12 mumda +1 ATR lehte ve −1 ATR aleyhte bariyerlerinden hangisine önce ulaşıldığı ölçülür. Aynı mumda ikisi de varsa **belirsiz**; hiçbirine ulaşılmazsa **hiçbiri**. Olay mumunun kendi aralığı sonuca sayılmaz. Sonuçta ayrıca 12. mumdaki yönlü kapanış ve pencere boyunca maksimum ters hareket (MAE) tutulur.

12 mum tamamlanmamışsa **sağdan sansürlü**; yanlış/eksik OHLC ve ATR ayrı durumdur, otomatik başarısızlık değildir. Önce sansür kontrolü yapıldığı için `UNKNOWN_DIRECTION` durum sayısı ile bütün yönü sıfır satırların sayısı aynı olmayabilir. Tablodaki “yön yok” bütün yönü sıfır olayları, “sansür” bütün eksik ufukları sayar; bu iki sütun örtüşebilir.

## 4. Seçilenler: sıklık ve yönlü sonuç birlikte

**Lehte oranının paydası yalnız geçerli yönlü, tamamlanmış 12 bar sonuçlarıdır; belirsiz/hiçbiri de bu paydada kalır.**

| Politika + bağımsız 6 bar cooldown | Olay | Olay/seans | Ölçülebilir | İlk lehte | İlk aleyhte | Aynı bar / hiçbiri | Lehte oranı | Medyan 12. bar kapanış / ATR | Medyan MAE / ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 | 1.780 | 80,91 | 1.222 | 669 | 523 | 21 / 9 | %54,75 | +0,167 | 1,400 |
| P6 | 725 | 32,95 | 521 | 257 | 253 | 8 / 3 | %49,33 | +0,114 | 1,526 |
| P4 | 426 | 19,36 | 220 | 95 | 117 | 7 / 1 | %43,18 | +0,110 | 1,602 |
| P7 | 752 | 34,18 | 526 | 258 | 255 | 10 / 3 | %49,05 | +0,121 | 1,521 |

P0/P6/P4/P7'de sırasıyla yönü yok: **377 / 159 / 179 / 178**; sansür: **216 / 56 / 38 / 59**. P4, seçilmiş 426 olayın yalnız 220'sinde yönlü tam sonuç taşıyor; bu payda kaybını gizlemiyoruz.

12. mumda en az +0,5 ATR koruyanlar P0'da **538/1.222**, P6'da **222/521**, P4'te **94/220**, P7'de **224/526**. İlk bariyer ile kapanışta korunma aynı şey değildir. Medyan MAE tüm 12 barı kapsar; ilk bariyere kadar risk veya stoplu işlem kaybı diye okunmaz.

**Sıklık farkı:** P6, P0'dan 47,95 potansiyel olay/seans daha az seçiyor. Bu fark başlı başına iyileşme değil; aşağıda neyin kaybolduğuyla birlikte değerlendirilmelidir. Önceki denetimin 97,09 / 35,68 değerleri eski terminal-rekonstrüksiyon proxy'sidir; bunlarla yeni 80,91 / 32,95 sayıları birleştirilmez veya değişim canlıya atfedilmez.

## 5. P6 neleri bastırıyor?

| P6 kohortu | Olay | Ölçülebilir | İlk lehte | İlk aleyhte | Belirsiz / hiçbiri | Lehte oranı | Medyan kapanış / ATR | Medyan MAE / ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Seçilen | 725 | 521 | 257 | 253 | 8 / 3 | %49,33 | +0,114 | 1,526 |
| Politika engeli | 4.907 | 3.148 | 1.738 | 1.340 | 44 / 26 | %55,21 | +0,141 | 1,435 |
| Politikayı geçti, cooldown engeli | 1.275 | 926 | 466 | 430 | 21 / 9 | %50,32 | +0,156 | 1,349 |

Toplam 725 + 4.907 + 1.275 = **6.907**. Politika engelindeki 1.738 ilk-lehte satır **1.738 bağımsız kaçırılmış fırsat** değildir: aynı formasyon/hareketin tekrarları olabilir. Buna rağmen reddedilenleri “kötü olay” diye varsaymak açıkça yanlış olur.

### P0 gösterir miydi? Aynı mumda kesişim

| P0 ↔ P6, her birinin kendi cooldown'u | Olay | Ölçülebilir | İlk lehte | İlk aleyhte | Medyan kapanış / ATR |
|---|---:|---:|---:|---:|---:|
| İkisi de seçti | 372 | 289 | 149 | 136 | +0,109 |
| Yalnız P0 seçti | 1.408 | 933 | 520 | 387 | +0,199 |
| Yalnız P6 seçti | 353 | 232 | 108 | 117 | +0,121 |

P0'ın 669 ilk-lehte seçiminin yalnız **149'u aynı mumda P6 ile ortak**; 520'si ortak değil. Bu, hareket/episod bazında recall değildir: aynı hareketin sonraki P6 alarmı ayrı olabilir. P6 ham politika olarak P0'ın altkümesi olsa da seçilmiş olaylar altküme değildir; önceki engeller cooldown saatini değiştirir. Bu nedenle “P0 − P6 = doğrudan filtre kaybı” hesabını tek başına kullanmadım.

P4'te yalnız-P0 ilk-lehte 647, yalnız-politika 73; P7'de 519 ve 108. Ayrıntılı tüm kohortlar JSON'dadır.

## 6. Yön ve TF: asimetriyi gizlememek

| Seçim | Aşağı olay / ölçülebilir / ilk-lehte | Yukarı olay / ölçülebilir / ilk-lehte | Yönü yok |
|---|---|---|---:|
| P0 | 733 / 632 / 372 (%58,86) | 670 / 590 / 297 (%50,34) | 377 |
| P6 | 94 / 81 / 40 (%49,38) | 472 / 440 / 217 (%49,32) | 159 |

P6'nın politika nedeniyle reddettiği aşağı olaylar **2.589**, ölçülebilir 2.219; ilk-lehte **1.306 (%58,86)**. Reddedilen yukarı olaylarda **432/929 (%46,50)**. Pozitif fiyat koşusu kapısı aşağı yönlü bilgiye sistematik olarak daha zor geçit veriyor. Bu dönemin aşağı/yukarı piyasa karışımı ile politika seçimi iç içedir; P0'ın gelecekte üstün olacağını kanıtlamaz.

TF bazında seçilen olay / yönlü payda / ilk-lehte:

| TF | P0 | P6 |
|---|---|---|
| 1h | 762 / 569 / 309 | 321 / 241 / 115 |
| 2h | 544 / 371 / 205 | 216 / 166 / 87 |
| 4h | 347 / 236 / 129 | 144 / 110 / 55 |
| 1d | 127 / 46 / 26 | 44 / **4** / 0 |

**1d P6 için payda dört:** 0/4'ü “%0 kalite” diye genellemek doğru değil. TF'lerin 12 barlık ufku farklı sürelerdir. Kanal birleşimi kırılımları da `breakdown.json` içinde; küçük/korele altgruplarla yeni eşik ayarlanmadı.

## 7. Cooldown: tekrar mı, yeni bilgi mi?

Son seçilmiş olayla şu kategoriler karşılaştırılır: yön, sebep kümesi, formasyon kimliği ve bildirim durumu/kırılım yönü, hacim tier'i ve şüpheli hacim etiketi. Sonuç etiketleri bu sınıflandırmada kullanılmaz.

| Cooldown engeli | Kategorik değişim var | Aynı kategorik imza |
|---|---:|---:|
| P0 olay | 3.370 | 1.757 |
| P0 ölçülebilir / ilk-lehte | 2.421 / 1.262 | 952 / 530 |
| P6 olay | 816 | 459 |
| P6 ölçülebilir / ilk-lehte | 637 / 324 | 289 / 142 |

Bu bir **yeni bilgi proxy'si**: kayıt şemasında MS olay kimliği, OB/FVG bölge kimliği ve sınırları bulunmadığından aynı “BOS ↑” veya “OB tepkisi” etiketi farklı seviyede yeni olay olabilir. Kategorik değişim de her zaman kullanıcı için değerli güncelleme değildir. O yüzden “816 gereksiz yere kaçırılmış yeni sinyal” veya “459 güvenle silinebilir tekrar” sonucu çıkarılmadı. Kesin tekilleştirme için bu domain kimlikleri ve son teslim edilmiş olayla bağ şarttır.

## 8. Gecikme: sonradan alarm gelene kadar hareket olmuş mu?

Aynı sembol/TF, deterministik formasyon kimliği ve yön korunarak sonraki **en fazla altı barda** P6 seçimi arandı. Bu formasyonlu altküme dışına genellenmez; eşleşmeyenler kesin kayıp sayılmaz.

- **794 engellenmiş satır**, **197 farklı sonraki seçimle** eşleşiyor. Medyan gecikme **3 bar**; TF'ler farklı olduğundan bunu üç saat diye okumuyoruz.
- 498 satır politika, 296 satır cooldown nedeniyle engellenmiş.
- **300 satırda**, sonraki seçimin kapanışına gelindiğinde ilk-lehte +1 ATR zaten görülmüş: politika 163, cooldown 137.
- Bu 300 satır **114 farklı sonraki seçime** bağlanıyor; 300 bağımsız geç alarm/işlem değil. Örtüşme düzeltmesi yalnız sonraki seçim düzeyindedir, bağımsız piyasa hareketi düzeyinde değildir.
- Gelecekteki fiyat burada sadece gecikmeyi etiketler; karar üretiminde kullanılmaz. İleri eşleşme veri setindeki sonraki satırlara bakabilir; yeni alarm kuralı değildir.

## 9. Kayıptan örnekler: kazananları seçip anlatmamak

`examples.csv`, P0 seçimi olup P6 seçimi olmayan ölçülebilir satırlardan **her ilk-bariyer sınıfının kronolojik ilk üçünü** alır. Elle güzel grafik seçilmedi; toplam 12 örnek. Zamanlar UTC mum açılış etiketidir; seans seçimi İstanbul tarihine göre yapılır.

- **DOAS 1d, 18 Ekim 21:00 UTC (=19 Ekim 00:00 İstanbul):** aşağı BOS, P6 politika engeli; ilk lehte 3 bar, 12. bar kapanışı +0,936 ATR. Engellenen ama takip yönünde hareketi koruyan örnek.
- **ARCLK 2h, 19 Ekim 06:00 UTC:** aşağı formasyon/retest, politika engeli; ilk lehte 4 bar, ama 12. bar kapanışı **−0,825 ATR** ve MAE 4,290 ATR. İlk lehte bariyer, iyi taşınmış hareket demek değil.
- **CIMSA 1d, 18 Ekim 21:00 UTC:** aşağı BOS, politika engeli; ilk bariyer aleyhte, 12. bar kapanışı −3,477 ATR. Filtrenin bastırdığı her şeyin iyi olmadığını gösterir.
- **SKBNK 1d, 20 Ekim 21:00 UTC:** aynı ileri mum iki bariyeri de gördü. “Önce lehteydi” diye varsayılmadı.

## 10. Dönem duyarlılığı ve doğrulama

İlk/son 11 ortak seans; holdout değil:

| Seçilenler | İlk 11 seans ilk-lehte / payda | Son 11 seans ilk-lehte / payda |
|---|---|---|
| P0 | 364/633 (%57,50) | 305/589 (%51,78) |
| P6 | 91/190 (%47,89) | 166/331 (%50,15) |
| P4 | 25/66 (%37,88) | 70/154 (%45,45) |
| P7 | 91/194 (%46,91) | 167/332 (%50,30) |

P6'nın bu iki parçanın hiçbirinde açık bir betimsel kalite üstünlüğü görünmüyor; güven aralığı/bağımsız deney iddiası yok. Piyasa gündemi ve örneklem etkisini dışlamaz.

**Testler:** yeni replay ve kırılım testleri **25 geçti (3,21 sn)**. İlgili 13 dosyalık geniş regresyon **1.547 geçti (192,20 sn)**; bunlar örtüşür, toplanmaz. Sonradan eklenen beş kırılım testi odaklı 25 testin içindedir. Yeni beş Python dosyasında Ruff temiz. Bu bütün repo testlerinin tamamen yeşil olduğu iddiası değildir.

## 11. Bundan sonraki değişiklik için kabul ölçütü

1. Üç alarm yolu için aday → kapı nedeni → gerçek olay kimliği → son teslim kimliği → teslim sonucu aynı defterde ilişkilendirilmeli. Kullanıcının **15 → 3–5** gözlemi hâlâ nedensel olarak açıklanmış değil; bu arşiv Kasım sonundaki günleri kapsamıyor.
2. Tam canlı yol eşlemesi: Stabil destek/mesafe kapısı, kayan pencere formasyon yaşamı, tarama programı ve MTF/hedef teslim kuralları. Bu çalışmanın sayılarını beklenen DM/gün diye kullanmamak şart.
3. P6 için olay yönüyle uyumlu koşu ve gerçek genişleme tanımı **önceden dondurulmuş gölge hipotezleri** olarak kıyaslanabilir. Yönü bilinmeyen/çelişkili olayları gelişigüzel yönlendirmemek gerekir. Mevcut +1 koşu eşiğini körlemesine iki tarafa açmak da henüz doğrulanmış çözüm değildir.
4. Cooldown'da gerçek yeni BOS/zone/formasyon-durum kimliğini tekrar etiketiyle ayırmak; yeni bilgiyi kaçırmadan tekrar yükünü yönetmek. Önce kayıt, sonra istisna kapısı.
5. Kabul tablosu: anlamlı **olay/episod kapsaması**, ilk bariyer, korunmuş kapanış, MAE, gecikme, bilinmeyen payı ve kullanıcıya düşen tekrar yükü birlikte. Dondurulmuş kuralları yeni tarih/sembol verisinde doğrulamak; yalnız daha düşük adet yeterli değildir.

## Kanıtlar

[Kalıcı küçük sonuç paketi](../arastirma/sonuclar/alarm_recall_v2_2026_11_27/README.md): `summary.json`, `breakdown.json`, `daily.csv`, `examples.csv`, `evidence_manifest.json`.
Ham 35.071 snapshot ve karar defteri Git dışında `var/alarm_recall_v2_20261127/` altında; yeniden üretim komutları ve dosya hash'leri pakette. Eski denetim ve sonuçlar silinmedi; yöntem farkı açıkça korunuyor.
