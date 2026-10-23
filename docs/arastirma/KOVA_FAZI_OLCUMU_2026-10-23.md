# Kova fazı ölçümü — 2s/4s serisi neden her saat yeniden yazılıyor?

> **Durum:** Ölçüldü ve düzeltme UYGULANDI (aynı gün, §9) · **Tarih:** 23 Ekim 2026
> **Köken:** 23 Ekim public akışında aynı gün 26 mesaj: ALARK 4 kez, AKBNK/AYDEM/KCHOL'da aynı mumun kopyaları.
> **Üretim:** `scripts/kova_fazi_olcumu.py` (ağsız; `backfill_data/*_1h.csv.gz`) + Supabase canlı agregaları (salt okuma).

---

## 0) Kısa cevap

Telegram iki görseli/mesajı birleştirmediği için değil; tekrarların ana kaynağı
**2s/4s mum kovalarının fazının saatten saate dönmesi**. `data.resample_ohlcv`,
kova başlangıç saatini (offset) sabit seans çapasından değil, elindeki veri
penceresinin **ilk barının saatinden** alıyor (`data.py:1513-1514`). Canlı
pencere 360 barlık kayan bir deque olduğu için (`config.py:470`) her yeni 1s
barda pencerenin başı 1 bar ileri kayar; ilk barın gün-içi saati değiştiğinde
bütün 2s/4s serisi farklı kovalara yeniden bölünür.

Sonuç sayıları (ayrıntı §2-§4):

| Ölçüm | 2s | 4s |
|---|---:|---:|
| Pencere başı doğru (09:30) fazda olma oranı | %55,6 | **%33,3** |
| Canlıda kayda geçmiş formasyon doğumlarının TV fazı dışı payı | %53,0 (192/362) | **%71,5 (228/319)** |
| Motorun nihai durumu sabit çapadan farklı | %19,2 | **%33,3** |
| Ardışık iki saatlik taramada motor karar imzası değişimi | %64,4 | **%67,8** |

Yani 4s'de taramaların kabaca üçte ikisi, TradingView/Pine'da **var olmayan**
mum bileşimleri üstünden karar veriyor. Formasyon bu yüzden beliriyor,
kayboluyor, yeni kimlikle yeniden "teyitleniyor" — 23 Ekim'deki tekrarların
mekanizması bu.

> Bu işte yapılan değişiklik, **tekrarları kullanıcı tarafında kesen hikâye
> kapısıdır** (§6). Fazın kendisini düzeltmek (offset'i sabitlemek) ayrı ve
> büyük etkili bir karardır; bu rapor onun ölçümüdür, uygulaması değildir.

---

## 1) Olay tam olarak ne?

### 1.1 Kova nedir, faz nedir?

Bot 1s barlardan 2s/4s barlar üretir ("resample"): art arda 1s barlar
gruplara (kovalara) bölünür, her kova tek OHLCV barı olur. **Faz**, ilk kovanın
günün hangi saatinde başladığıdır. BIST'te ilk 1s barın etiketi 09:30 olduğu
için TradingView/Pine hizası şudur:

- 2s kovaları: 09:30, 11:30, 13:30, 15:30, 17:30 (günün son kovası yarım)
- 4s kovaları: 09:30, 13:30, 17:30 (son kova yarım)

Faz kayarsa — örneğin 4s kovaları 06:30/10:30/14:30 olursa — aynı fiyat
hareketi bambaşka mumlara bölünür: pivotlar, bant sınırları, temas sayıları ve
dolayısıyla formasyon tespiti değişir. 23 Ekim kartlarındaki
`06:30→10:30`, `07:30→11:30`, `08:30→12:30` aralıkları seans dışı saatler
değil, bu kayık fazların etiketleridir.

### 1.2 Faz neden kayıyor?

`data.py:1511-1515` (B1 düzeltmesi) kovaları seans başına hizalamak istiyor
ama "seans başı"nı **verinin ilk barı** sanıyor:

```python
ilk = df.index[0]
offset = f"{ilk.hour}h{ilk.minute:02d}min"
```

Canlı akışta `df`, 360 barlık kayan deque'nin o anki içeriğidir. Bir seans
gününde 9 adet 1s barı (09:30…17:30) olduğu için pencerenin ilk barı gün
içinde bu 9 etiketten herhangi biri olabilir:

- 2s için ilk bar {09:30, 11:30, 13:30, 15:30, 17:30}'dan biriyse faz doğru
  (9 konumun 5'i → %55,6), değilse kovalar 08:30 fazına oturur.
- 4s için ilk bar {09:30, 13:30, 17:30}'dan biriyse faz doğru (9 konumun
  3'ü → %33,3); diğer konumlarda faz 06:30, 07:30 veya 08:30 olur.

Tarama her turda motoru `tam_yeniden=True` ile tüm pencereye baştan koşturduğu
için (`main.py:2863`) faz değişimi yalnız son barı değil, **geçmişteki bütün
2s/4s mumlarını** yeniden yazar. İki saat arayla yapılan iki tarama aynı 1s
verisine bakıp farklı 4s tarihi görebilir.

Bu, arşivdeki doğrulama raporunda **P2-2** olarak kayıtlı bilinen bir bulgunun
(`docs/arsiv/DOGRULAMA_RAPORU.md`) canlı tekrar sorunuyla birleşmiş hâlidir.

### 1.3 Neden tekrar bildirime dönüşüyor?

1. Faz değişince seri değişir → motor aynı bölgede yeni/different bir
   formasyon bulur veya aynı formasyonu yeniden teyit aşamasına getirir.
2. Yeni tespit yeni `formation_id` alır (`patterns/lifecycle.py:50`, uuid4);
   restart sonrası re-attach tutmazsa aynı geometri bile yeni kimlik taşır.
3. DM mührü ve public mührü kimlik temellidir; kimlik değişince delinir.
4. DM'i asıl koruyan 4 saatlik cooldown public yolunda yoktur; public tekilleştirmesi
   kimlik + TF-arası `related()` (farklı TF + aynı aile + 4 saat) ile sınırlıdır.

Aynı gün içinde: ALARK 4s dört kez (her saat farklı faz), KCHOL 4s üçgen + 2s
kama (aile farklı → `related()` kaçırdı), TTKOM'da RETEST sonrası tekrar TEYİT
(yeni aday, geriye gidiş), restart turlarında AKBNK/KCHOL/AYDEM'in aynı mumu
yeniden basıldı.

---

## 2) Seviye 1 — Kova ölçümü (motorsuz, deterministik)

Yöntem: 20 sembol × 3 pencere sonu × 9 başlangıç kayması = TF başına 540
senaryo. Her senaryoda üretim fonksiyonu `data.resample_ohlcv` ile sabit
09:30 çapalı seri karşılaştırıldı.

| TF | Farklı faz | Doğru faz oranı | Sabit seri ile ortalama etiket kesişimi |
|---|---:|---:|---:|
| 2s | 2 | %55,6 | %54,9 |
| 4s | 4 | **%33,3** | **%32,9** |

- Etiket kesişimi doğru faz oranına neredeyse eşittir: yanlış fazdaki serinin
  bar zamanları TV serisiyle neredeyse hiç çakışmaz. Çakışan barlarda OHLC
  farkı 0'dır — sorun değer hesabı değil, **hangi 1s barların aynı kovaya
  girdiği**dir.
- 4s fazları birebir canlıda görülen dörtlüdür: 06:30 / 07:30 / 08:30 /
  09:30 başlangıçlı kovalar.

## 3) Seviye 2 — Motor kararı ölçümü

Yöntem: 6 sembol (ALARK, AKBNK, KCHOL, TTKOM, EREGL, DOHOL) × 5 pencere
sonu × 4 başlangıç kayması = TF başına 120 karşılaştırma. Her senaryoda taze
`ArgentEngine(profile="Dengeli")`, `process(tam_yeniden=True)`; imza =
(durum, desen, kırılım yönü, ham kalite). Kimlik (uuid) imzaya dâhil değildir.

| TF | İmza farklı (eski vs sabit) | Durum farklı | Desen farklı | Ardışık saatte karar değişimi |
|---|---:|---:|---:|---:|
| 2s | %37,5 | %19,2 | %21,7 | %64,4 |
| 4s | **%50,0** | **%33,3** | %19,2 | **%67,8** |

Örnek (ALARK 4s, aynı pencere sonu 2026-10-19 15:30): bir kaymada motor
`FORMASYON_TAMAMLANDI` (aktif desen yok) derken sabit çapada
`RETEST_BEKLENIYOR` + Yükselen Üçgen (kalite 91,4) diyor. ALARK 2s'de bir
başka pencerede sabit çapa `SIKISMA_GUCLENIYOR` + Alçalan Üçgen bulurken
kayık fazlar formasyonu çoktan tamamlanmış sayıyor.

**Okuma sınırı:** "İmza farklı" oranı ham kaliteyi (0,1 duyarlılık) de içerdiği
için üst sınırdır; karar değişimini en temiz gösteren satırlar durum/desen
oranlarıdır. Örneklem 6 sembol × 5 bitiştir; oranlar mertebe göstergesi olarak
okunmalıdır (±%9 civarı örnekleme belirsizliği). Canlıda PatternLifecycleManager'ın
re-attach/continuity katmanı bazı kararsızlıkları yutabilir; fakat aynı
mekanizmanın canlı izi §4'tedir ve yön aynıdır.

## 4) Canlı kanıt (Supabase, salt okuma)

`f2_formations.dogum_bar_time` gün-içi saat dağılımı — bir formasyon hangi fazın
kovasında doğmuş:

| TF | Toplam doğum | TV fazı | Faz dışı |
|---|---:|---:|---:|
| 2s | 362 | 170 (%47,0) | 192 (%53,0) |
| 4s | 319 | 91 (%28,5) | **228 (%71,5)** |

Canlı doğumların faz dağılımı, laboratuvar ölçümünün öngördüğü oranlara
(2s %55,6 / 4s %33,3 doğru) yakındır; sapma, doğumların gün içi saatlere
eşit dağılmamasındandır.

Bildirim defteri (`bot_store: formation-bot:state:notification_delivery`,
17 Ekim sonrası):

| Kanal | Kayıt | Aynı gün+slot+state tekrarı | Hikâye kuralıyla düşecek olan |
|---|---:|---:|---:|
| DM satırları | 83 | 2 | 6 (%7) |
| Public kabul edilenler | 96 | 15 | **19 (%20)** |

23 Ekim'in yapıştırılan 26 public mesajına hikâye kuralı elle uygulandığında
17 mesaj kalıyor (**−%35**): düşenler ALARK'ın 3 tekrarı, AKBNK/KCHOL/AYDEM
kopyaları, XU30'un ikincisi, KCHOL'un ikinci TEYİT'i ve TTKOM'un RETEST
sonrası TEYİT'i. KCHOL 2s RETEST, TEYİT sonrası ilerleme olduğu için kalır.

## 5) Etkilenmeyenler / sınırlar

- **1s ve 1g etkilenmez:** 1s doğrudan kaynak seridir; 1g gün kovası faza
  duyarlı değildir. Sorun yalnız 2s/4s türetimindedir.
- Ölçüm, sabit 09:30 çapasını "doğru" referans alır; gerekçe Pine/TV
  uyumu hedefidir (B1 düzeltmesinin kendi gerekçesi). BRENT/USDTRY/ALTIN gibi
  kesintisiz piyasalarda doğru çapa ayrıca tartışılmalıdır; faz düzeltmesi
  yapılırsa onlar için politika ayrıca seçilmelidir.
- Faz düzeltmesi yapılırsa geçmiş 2s/4s tespit/karne kayıtları yeni seriyle
  birebir karşılaştırılamaz (zaten karışık fazda üretildiler); geçiş gününde
  formasyon envanteri bir kez sıçrar.

## 6) Bu işte uygulanan çözüm: hikâye kapısı

Faz düzeltilene kadar (ve düzeltildikten sonra da restart/replay'e karşı)
tekrarlar teslim katmanında kesilir — `notification_delivery.py`
`_story_duplicate`, DM'de `submit()` + `notifier.send_with_prepare` erken
kapısı, public'te `public_duplicate()` üzerinden:

- Anahtar kimlik değil: **hisse + yön + aşama** (TEYİT=1, RETEST=2).
- Aynı aşama, aynı kimlik veya aynı olay-gününde ikinci kez basılmaz;
  TF ve desen ailesi farkı gözetilmez.
- Aşama yalnız ileri gider; RETEST sonrası TEYİT geri gelemez.
- Adayın barı kabul edilmiş hikâye olayından yeni değilse replay sayılır.
- Mutlak bayatlık: gün-içi TF yalnız kendi İstanbul gününde, 1g 7 gün içinde
  anlık push olur.
- `KIRILIM_GECERSIZLESTI` bu kapıda asla engellenmez; hikâyeyi kapatır,
  kapanıştan eski tekrarlar düşer, yenisi serbesttir.
- Bar zamanı taşımayan (eski/test) kayıtlarda kapı çalışmaz; eski
  related/alias davranışı korunur.
- DM'de kapının kararı nihai "tekrar" reddidir: acil kuyruğa girmez,
  sonradan dirilmez.

Public kürasyonunda ek filtre konmadı: üst-TF onayı bugünkü hâliyle gevşek
bir "üst TF'de aktif yapı var" bilgisidir ve kendisi de faz hatasından
etkilenir; güç eşiği için tek günlük gözlem yetersizdir. İki eşik de faz
düzeltmesi sonrası karne verisiyle yeniden değerlendirilmelidir.

## 7) Önerilen sıradaki adım (faz düzeltmesi)

1. `resample_ohlcv` offset'ini BIST sembollerinde sabit seans çapasına bağla
   (etiket dünyada 09:30); kesintisiz semboller için politikayı ayrıca seç.
2. Faz kararlılığı regresyonu: pencere başı kaydıkça seri değişmemeli
   (bu betiğin seviye-1 kontrolü teste çevrilebilir).
3. Geçişte geometry snapshot / mum kapanış testlerindeki faz varsayımlarını
   güncelle; karneye "faz geçişi" notu düş (önce/sonra ayrımı).
4. Bir hafta gözlem: 2s/4s tespit ve bildirim sayısındaki değişimi bu
   raporun tabanıyla karşılaştır; güç/üst-TF eşiklerini ondan sonra konuş.

## 8) Yeniden üretim

```bash
.venv/bin/python scripts/kova_fazi_olcumu.py                 # tam ölçüm (~20 sn)
.venv/bin/python scripts/kova_fazi_olcumu.py --motorsuz      # yalnız seviye 1
.venv/bin/python scripts/kova_fazi_olcumu.py --semboller ALARK,AKBNK --json sonuc.json
```


## 9) Uygulama (23 Ekim 2026, onay sonrası)

§7'deki adımlar uygulandı:

1. **Sabit çapa:** `data._resample_sabit_capali` — BIST seans serisinde çapa
   sabit 09:30 (İstanbul); kesintisiz seride (gece barı taşıyan: BRENT,
   USDTRY, ALTIN...) İstanbul gece yarısı. Karar sembol listesinden değil
   serinin kendi saatlerinden verilir (`_bist_seans_serisi`): yeni sembol
   sınıfı eklenirse davranış kendiliğinden doğru kalır. Girdi tz'si (canlı
   İstanbul / araştırma UTC) çıktıya aynen geri çevrilir; kova anları her
   yolda aynıdır. 1g yolu bilinçli olarak değiştirilmedi.
2. **Regresyon:** `test_kova_fazi.py` — 9 pencere başının hepsinde etiketlerin
   doğru fazda olması, pencere başı sonrası kovaların tam seriyle birebir
   eşitliği, UTC/tz'siz/kesintisiz varyantlar.
3. **Doğrulama ölçümü** (aynı betik, düzeltme sonrası):

   | Ölçüm | Önce (2s/4s) | Sonra (2s/4s) |
   |---|---|---|
   | Doğru faz oranı | %55,6 / %33,3 | **%100 / %100** |
   | Motor nihai durum farkı | %19,2 / %33,3 | **%0 / %0** |
   | Desen farkı | %21,7 / %19,2 | **%0 / %0** |
   | Ardışık saatte karar imzası değişimi | %64,4 / %67,8 | %2,2 / %5,6 |

   Kalan %2-6 imza farkı fazdan değil, pencere başındaki **kısmi ilk
   kovadan** geliyor (kalite ±0,1); durum/desen hiç değişmiyor.
4. **Ek sertleştirme (aynı işte):**
   - Hikâye kapısında bar zamanı taşımayan eski kaydın `created` yedeği
     artık yalnız gün seviyesinde konuşuyor; "aday barı gönderim anından
     eski = replay" hükmü kesin olmayan zamanla verilmiyor.
   - Supabase mirror flush'ında zehirli batch kilidi açıldı: deterministik
     4xx alan tablo diğer tabloları kilitlemiyor, red sebebi loglanıyor,
     baş batch 5 denemede düşürülüyor. (Canlıda `f2_snapshots`/`f2_events`'in
     0 satırda kalmasının mekanizması buydu.)
5. **Kalan — sıradaki hafta:** §7/4 gözlemi: 2s/4s tespit ve bildirim
   sayısını bu raporun tabanıyla karşılaştır; güç/üst-TF eşiklerini ancak
   ondan sonra konuş. Karne kayıtları tarih taşıdığı için önce/sonra ayrımı
   deploy tarihinden yapılabilir; ayrı sürüm etiketi eklenmedi.

Geçiş notu: deploy günü canlı 2s/4s serileri bir kez sıçrar (doğru faza
oturur); o gün formasyon envanterinde tek seferlik dalgalanma normaldir.
