# Telegram alarm kartı — biçim sözleşmesi (13 Eki 2026)

Bu dosya `KARTE` biçimleyicisinin kalıcı sözleşmesidir: nedenleri, sınırları ve
yeniden üretilebilir ölçüm sonuçlarıyla. Amaç formatı beğenmek/beğenmemek değil;
**hangi kuralın hangi hatayı kapattığını** tek yerden okunabilir kılmak.

İlgili kod: `notifier.py` (`_format_lifecycle_alert_kart`),
`notification_context.py` (`domain_bolumleri`, `karsi_deliller`),
`telegram_measure.py` (satır ölçeri), `main.py` (`_attach_domain_context`).

## 1. Kurallar (değiştirirken bozulmaması gerekenler)

1. **Düz metin.** `parse_mode`, HTML, `<b>`, ```` ``` ```` yok. Vurgu yalnız
   sembol ve büyük/küçük harfle: `▲ ▼ × ▪ ▸ ◈ ▤ ◆ ‹ •`.
2. **1 olay = 1 mesaj.** Kart sıkıştırması mesaj sayısını değiştirmez; yalnız
   değişmemiş bağlam bloğunu tek satıra indirir.
3. **Satır bütçesi: ≤ 283 px.** Telegram 360 px'lik telefonda satırı kendi
   kırar; kırılan satır kartın tüm düzenini bozar. Üretici taraf `bol()` ile
   böler, gönderim `_gonder()` içinde `satirlar_asiyor_mu()` ile denetlenir ve
   aşım WARNING olarak loglanır. Karakter limiti (70 kr) tek başına yetmiyor:
   `ı` ile `m` aynı değil.
   Kart dışı yüzeyler (özet, komut yanıtları, karne) için aynı bütçe
   **üç merkezi gönderim noktasında** uygulanır: `notifier.send_text`,
   `notifier.send_to_public`, `telegram_commands._cevapla` →
   `metni_sigdir(metin, guvenlik=1.0)`. `guvenlik=1.0` liste/özet yüzeyleri
   için: ölçüm tablosu ±%3 hata taşıyor, alarm kartı `%5` payla (`_GUVENLIK`)
   çalışıyor; liste satırı 1 px taşarsa tek kelime iner, kartta ise taşma kartın
   dengesini bozduğu için pay bırakılıyor.
4. **Sarmayan satır ≠ düzeltilmiş satır.** Bölünme kelime/ibare ortasına
   düşüyorsa (başlık ikiye yarılmış, son kelimeler havada kalmış) sorun
   çözülmemiştir: satır **kelime düzeyinde kısaltılarak** tek başına okunan bir
   birime dönüştürülür (`q88`, `%72`, `1s`, `⚡ Kırılım: 3 · …`). Bilgi
   düşürülmez — alan adını kısaltır, veriyi silmeyiz.
5. **Mesaj bütçesi: ≤ 1100 karakter.** 4096'lık Telegram tavanı değil, tek
   ekran sözümüzdür. 1100'ün altındaki boşluk "daha çok yazı" anlamına gelmez.
6. **Kaynakta olmayan veri yazılmaz.** `olay kalitesi`, `deneme sayısı`, OB
   yaşam döngüsü etiketi gibi motorun üretmediği alanlar kartta yok (motor OB
   için yalnız `state = ±1` veriyor — `domain_engines/order_block/order_block.py`).
7. **Bilgi kaybı yok.** Kartta çıkarılan her satır `/tara SEMBOL` çıktısında
   duruyor; `ters işaret` satırı bu yüzden kartta. **İstisna (2026-10-22):**
   `/tara` komut satırı karttan çıktı (kullanıcı kararı); komut çalışmaya devam
   eder, her alarmın altında tekrar etmez. Boşalan yer ölçüm dipnotuna gitti.
8. **Klasik yol byte-byte duruyor.** `TELEGRAM_ALERT_STYLE=klasik` → 25 Eyl
   öncesi biçim. A/B karşılaştırma ve geri alma hakkı için korundu; kartta
   yapılan düzeltme klasik biçime uygulanmaz.
9. **`◇` satırı ölçümdür, tahmin değil.** Kart, aynı kurulumun arşivdeki
   sonucunu en çok **3** satırda basar — grup mesajı da aynı 3 satırı basar (koşul + n görünür, kaynak
   [arastirma/AMPIRIK_REFERANS.md](../arastirma/AMPIRIK_REFERANS.md)). Sayı
   biçimleyicide hesaplanmaz; `ampirik_referans` tablolarından gelir. Koşul
   sağlanmıyorsa satır basılmaz. Yatırım tavsiyesi dili testle yasak
   (`test_ampirik_referans.py`).

## 2. Kart iskeleti

```
▲ BIMAS 4s · YUKARI TEYİTLİ          ← olay: yön + hisse + TF + durum (tek satır)
◆ Simetrik Üçgen · kapanışla         ← desen + teyidin türü
🕒 25.09 09:30→13:30 mumu             ← hangi mumun kapandığı

▪ kırılan 407,17                      ← olay künyesi (önce bunlar okunur)
▪ kapanış 428,25 · %5,2 aştı
▪ kalite 76/100 (formasyon)
   kırılma gücü 25
▪ temas üst 2 / alt 2 · retest yok
▪ MTF: 1g onayı yok
▪ bant 96 bar
   izlenme 12.08 09:30
▪ daralma %90
× geçersiz: 406,08 altı kapanış       ← teyit hangi seviyede düşer

◈ 4s yapı: dış ↓geçiş · iç ↓          ← piyasa yapısı: alarm TF olaylarıyla
   dış · CHoCH ↓ 411,75 · geçerli
   iç · BOS ↓ 429,00 · geçerli
▸ 1s ↓/↑ · PH 437,50                  ← diğer TF'ler tek satır

▲ FVG 4s ayı · 429,00–433,50          ← OB + FVG TEK liste, mesafeye göre
   ilk temas · %22 dolu · +%0,2
▲ OB 1s ayı · 432,25–435,75
▼ OB 2s boğa · 423,00–425,50

▤ 1s alt bölge emilim işareti         ← hacim: yargı / sayılar / katkı
   RVOL 0,53× ≈DV
▤ 4s: hacim verisi bekleniyor
◇ rol uyumlu %80 n15724               ← arşiv ölçümü (en çok 3 satır)
! karşı delil: iç yapı ↓
› /tara BIMAS
• yatırım tavsiyesi değildir
```

Okuma sırası önem sırasıdır: olay → künye → teyit kuralı → yapı → bölge →
hacim → karşı delil → CTA.

## 3. 25 Eyl 2026 ölçüm sonuçları (aynı cache, `gun_simulasyonu.py`)

| Ölçüm | Eski biçim | Kart |
|---|---:|---:|
| DM alarm sayısı | 6 | 6 |
| Toplam karakter | 8 774 | **5 273** (−%40) |
| Görsel satır (sararak uzayanlar dahil) | 308 | **218** |
| Saran satır | 120 | **0** |
| En uzun satır | 1 338 px | **268 px** |
| Tek mesaj tavanı | 1 559 kr | 966 kr (≤ 1 100 ✓) |
| DM özet | 2 842 kr | 2 016 kr |
| Kanal mesajı | 5 | 4 (1 geçersizleşme, kural gereği) |

Kart, tahmin edilen 850–900 kr bandının tamamında (816–966 kr).

## 4. Bu biçimin kapattığı içerik hataları

- **Kırılım marjı hiç yazılmıyordu** → `▪ kapanış … · %5,2 aştı`.
- **`Kalite` iki farklı sayıyı gösteriyordu** (mesajda `snap.effective_quality`,
  kapıdan geçiren `break_quality`) → etiket `(formasyon)` ile net; kırılma gücü
  ayrı satırda.
- **OB ve FVG aynı bölgeyi iki başlıkta tekrarlıyordu** → tek liste, taraf +
  mesafe sıralı; fiyat bandın içindeyse `◉` ile önce basılır.
- **Alarm olmayan TF'nin olay listesi her karta basılıyordu** → alarm TF
  olaylarıyla, diğerleri tek satırda.
- **Hacim yargısı yoksa satır kayboluyordu** → `▤ {tf}: hacim verisi bekleniyor`
  ("veri yok" ile "yargı yok" ayrımı kullanıcı için karar vericidir).
- **Desen adı `str.upper()` ile bozuluyordu** (`Simetrik → SIMETRIK`) → ad
  olduğu gibi yazılır.
- **KARNE bloğu DM özetine iki kez ekleniyordu** (2 842 kr'lik özetin 1 651 kr'i)
  → tek geçiş; sayaçlar gönderilen mesajla hizalandı (`5 bildirim` → `6`).

## 5. Ayarlar

| Anahtar | Varsayılan | İş |
|---|---|---|
| `TELEGRAM_ALERT_STYLE` | `kart` | `klasik` = eski biçim |
| `TELEGRAM_SATIR_PX` | `283` | satır bütçesi (px) |
| `TELEGRAM_ALERT_MAX_KARAKTER` | `1100` | mesaj bütçesi (kr) |
| `TELEGRAM_DM_DEGISIM_KAPISI` | `1` | değişmeyen bağlam bloğunu tek satıra indirir |
| `TELEGRAM_KANAL_GECERSIZ_KAPISI` | `1` | geçersizleşme yalnız teyidi kanala gitmişse kanala gider |

## 6. Bilinçli olarak yapılmayanlar (Faz 2)

- **OB + FVG konfluence puanı**: motor tarafı işi, biçim değil (`order_block.py`
  yalnız `state = ±1` veriyor; lifecycle `break_strength`'i bölgesel dolulukla
  karıştırmıyor). Kart ham veriyi gösterir; birleşik yargı üretilmez.
- **Olay/deneme sayacı**: payload'da yok → kartta da yok (uydurulmadı).
- **Kısmi bağlam diff'i**: `değişmedi` kapısı tam eşleşme ister; 5 satırdan 1'i
  değişince blok tamamı basılır (25 Eyl TOASO çifti böyle çalıştı: kısaltma
  devreye girmedi, yanılma payı bırakılmadı).
- **Klasik (`kart=0`) şablon** kelime kısaltmalarından faydalanmaz; satır
  bütçesi güvenlik ağı olarak yine uygulanır (A/B referansı bozulmasın diye
  `_gonder()` yolu kendi biçimleyicisini kullanır).
- **On-demand listeler 1100 kr'ı aşabilir** (`/yardim` 2 641, `/formasyonlar`
  2 140 kr): 1100 kr alarm başlığıdır; liste tek mesajda tam kalmalıdır. Koruma
  `kirp()` + Telegram'ın 4096 tavanı.
- **Ölü `format_message` şablonu** (329–361 px satırlar) silinmedi; hiçbir akış
  oradan geçmiyor, temizliği ayrı commit.

---

## 7. 22 Ekim 2026 revizyonu — 7 blok, sade dil, aile, public

Bu bölüm yukarıdaki 1-9 kuralların **üzerine** eklenir; çelişki varsa bu bölüm
geçerlidir (kod: `notifier._format_lifecycle_alert_kart_sade`).

### 7.1 Blok düzeni

Kart 7 bloğa ayrıldı, blok arası **tek boş satır**, girinti yok. Sıra karar
sırasını izler:

| Blok | İçerik |
|---|---|
| 1 OLAY | kimlik, formasyon, `🕒 … mumu`, `· kapanış … · sınır …` |
| 2 ÖNÜNDE | kırılımın önündeki canlı bölge, kalite, bant yaşı |
| 3 YAPI | kısa vadeli yön, geri çekilme/onay |
| 4 ÖLÇÜ | `◇` arşiv ölçümü (DM 3, public 2) + `· geçmiş davranış, kazanç değil` |
| 5 KATILIM | hacim yargısı |
| 6 SINIR | `ters işaret:` ve `· bozulur:` |
| 7 CTA | `• yatırım tavsiyesi değildir` |

Tavan `_KART_MAKS_SATIR = 20` **dolu** satır (boş satırlar sayılmaz).

### 7.2 Sade dil

Ölçü ve kart satırlarında kısaltma yaşamaz: `ATR` → `normalin x katı` /
`~1,05 TL`, `RVOL` → `hacim`, `BOS`/`CHoCH` → `kırılım`/`dönüş`, `OB`/`FVG` →
`blok`/`boşluk`, `bar` → `mum`, `retest` → `geri çekilme`, `tamamlandı` →
`tuttu`. Sıfat yasak (`tipik`, `zayıf`, `güçlü`, `muhtemel`). Testler:
`test_kart_metin.py::test_kart_jargon_tasimaz`,
`test_ampirik_referans.py::test_sade_dilde_*`.

### 7.3 Aile ayrımı

Aynı kartta iki farklı yüzde basılmaz. Formasyon alarmı `FRM` ailesini
(`kırılım tuttu`, `rol uyumu`, `geri çekilme`), MS olayı `ms`, zone teması
`ZONE` ailesini basar (`ampirik_referans.AILE_OLCU`). `aile=""` eski davranışı
korur (kısıtsız).

### 7.4 Public = DM (birebir)

Grup mesajı DM kartının **aynısıdır** — ayrı kip yok, ayrı başlık yok
(2026-10-22 akşamı; kullanıcı: *"Gelişme olmamalı, DM ile aynı olmalı"*).
Aynı biçimleyici, aynı 7 blok, aynı 3 `◇`, aynı `• yatırım tavsiyesi değildir`
satırı. Toplu bülten (`📊 Bülten · N gelişme` + tarih) **kaldırıldı**: olay
başına bir mesaj gider. Tek fark görseldedir: grup **1 kare + üst zaman dilimi**
alır (DM 4 kare); `PUBLIC_MIN_ARALIK_SN` 1,2 → 2,0.

Test: `test_public_grup.py::test_public_her_olay_kendi_mesajinda_dm_ile_ayni`
mesaj metnini DM kartıyla **byte byte** karşılaştırır.

### 7.5 DM kapısı

Görseller yalnız **pozitif tamsayı** `TELEGRAM_CHAT_ID`'ye gider
(`notifier.grafik_dosya_gonder`). `deploy_check` bunu üç satırla denetler:
pozitif tamsayı · `@kullanici` biçimi (görsel gitmez) · DM ile public hedefin
aynı olması (hata).

### 7.6 Beklenti hükmü (varsayılan kapalı)

`TELEGRAM_KART_TAHMIN=1` iken ölçü bloğunun başına `◇ beklenti: devam` +
`◇ 2 ölçüm lehte` girer; slot sayısı 3'te kalır. Hüküm kelimeleri
`devam · tek kanıt · kararsız · yön kanıtı yok` — sıfat yok. Yön kanıtı yoksa
satır basılmaz. Aile tabanları: ms/rvol/yükseklik/zone %65,5 · uyum %75,0.

### 7.7 Ölçülen ama yazılmayan

Koşullu "giderse tamamlanır" cümlesi ölçüldü ve **karta yazılmadı**; gerekçe ve
sayılar `docs/arastirma/KOSULLU_CUMLE_OLCUMU.md`. Kural: ölçüm cümleyi
desteklemiyorsa cümle yazılmaz.

### 7.8 Public bağımsızlığı ve üst TF yedeği (22 Ekim 2026, akşam)

Public kuyruğu DM kartıyla aynı 7 bloğu basar; bu bölüm **public'in DM
kapılarına takılmamasını** ve eksik kalan iki bloğun nasıl doldurulduğunu
tanımlar (kod: `notifier.public_kuyruk`, `notification_context._kart_yapi_ozet`).

| Durum | Eskiden | Şimdi |
|---|---|---|
| Alarm TF'sinde MS satırı yok (motor o TF'de olay üretmedi) | `◈ … yapı` satırı hiç basılmıyordu → bültende yapı bloğu boş | Sıra: alarm TF → **public görselindeki üst TF** (1h/2h→4h, 4h→1g) → kalan üst TF'ler. Satır **kendi etiketiyle** yazılır (`◈ 4s yapı …`); alarm TF'si gibi gösterilmez |
| DM mührü `tekrar` dedi (olay bugün DM'e gitti) | `before_send` çalışmadığı için public kuyruğu da dolmuyordu | Yalnız **public'te kaydı olmayan** olay için bağlam hazırlanır; DM'e ikinci kez gitmez |
| DM geçersizleşme kapısı kapalı (teyit DM'e teslim edilmemiş) | Ayrı `elif` bloğu tüm bağlamı atlıyordu → grupta teyit "geçerli" kalıyordu | Kapı yalnız DM push'unu atlar; bağlam + public kuyruğu çalışır, kararı public kendi kapısı verir |
| Teyit sonradan kalitesi düştü (eşik altı) | Geçersizleşme kalite kapısına takılıp düşüyordu | `KIRILIM_GECERSIZLESTI` kalite kapısından **muaf** (DM ve public). Kapı yalnız yeni iddialar içindir |
| Teyit kuyrukta bekliyor (henüz gruba gitmedi) + geçersizleşme | Teyit sonradan gidiyor, geri alma kalıcı olarak kayboluyordu | İkisi **birlikte düşer** (`Public: teyit henüz gönderilmemişti …`) |

MS motoru arızası karta **basılmaz** (karar D); `/durum`a `⚠️ MS (piyasa yapısı)
motoru: N hissede hata · son: … · alarm kartı etkilenmez` satırı düşer (hisse
bazlı sayaç; aynı hissenin iki TF alarmı sayacı şişirmez).

Ölçüm (22 Ekim, örnek kayıtlarla): teyit kartı 25 satır / 524 kr / en geniş
253,5 px; geçersizleşme 24 satır / 439 kr; en geniş satır 253,5 px
(`_kart_esik_px` 283). Grup mesajı aynı kart olduğu için ölçüm de aynıdır.

### 7.9 Endeks + makro: iki kart satırı (22 Ekim 2026, gece)

Evren 57 sembol oldu (48 hisse + 5 endeks + 4 makro). Kart tarafında **iki yeni
satır** var; ikisi de aynı 283 px bütçesine uyar (kod: `main._goreli_guc_satiri`,
`notification_context._hacim_yok_nedeni` / `_hacim_yok_notu`).

**1. Endekse göre göreli güç** — YAPI bloğunda, yapı özetinin hemen altında:

```
· 20 mum endekse +2,1 puan
```

| Kural | Değer |
|---|---|
| Taban | XU100, **aynı TF**, **aynı bitiş mumu**, aynı 20 mum |
| Ölçü | `hisse_getiri − XU100_getiri`; birim **puan** (iki yüzdenin farkı yüzde değil) |
| Yazılmaz | XU100'ün kendisinde · veri kısıtsa · geçersizleşme kartında |
| Not (23 Eki) | Satır, `resample_ohlcv` import edilmediği için 22–23 Ekim boyunca **hiç basılmadı**; bkz. §7.10 |
| Ölçüm | 243,5 px. Adaylar: `· 20 mumda endeksten +2,1 puan` 270,5 px ve `· 20 mumda endekse +17,9 puan` 263,5 px — ikisi de eşiği (262,85) aşıyordu |

**2. Hacim yok açıklaması** — KATILIM bloğunda, iki kısa satır:

| Tür | Satırlar | Ölçüm |
|---|---|---|
| Endeks | `katılım 4s hacim yok (endeks)` + `yön fiyattan okunur` | 237 + 159 px |
| Makro | `katılım 4s hacim yok (makro)` + `yön fiyattan okunur` | 231 + 159 px |
| Hisse, veri yok | `katılım 4s veri yok` (tek satır) | — |
| Analiz yapılamadı | `analiz yapılamadı` (not **eklenmez**) | — |

Tek satır hâli (`… endeks hacmi yok · yön fiyattan`) 466 px ölçüldü ve `_satir`
bölüyordu; bu yüzden iki satıra ayrıldı. "veri yok" denmez — veri var, hacim
alanı boş. Gerekçe ve evren kararı: `docs/tasarim/EVREN_GENISLETME.md`.

**3. Fiyat ölçeği (aynı gün bulundu).** Endeks fiyatı 5 haneli olunca olay
satırı `· kapanış 13482,50 · sınır 13380,00` **279,5 px** ölçüldü; `_satir`
bölüyor ve **girintili devam satırı** (`   · sınır 13380,00`) üretiyordu — kart
sözleşmesi bunu yasaklıyor. Bölme artık biçimleyicide: satır eşiği aşıyorsa
`· kapanış …` ve `· sınır …` **iki tam satır** olur (hisse fiyatında birleşik
satır 219,5 px, tek satır kalır). Test:
`test_kart_metin.py::test_endeks_olceginde_kapanis_sinir_satiri_girintili_bolunmez`.

### 7.10 23 Ekim 2026 — kart neden "sade" geliyordu (NameError)

Kullanıcı canlı mesajı yapıştırıp *"gelen metin basit, planlanan biçim farklıydı"*
dedi. Örnek, **7.1'deki blokların 2–6'sı boş** bir karttı: `◈` yapı, `◇` ölçü,
`▤` katılım, `▼` engel ve `ters işaret` satırlarının hiçbiri yoktu.

Biçimleyici suçlu değildi; **bağlam hiç üretilmemişti**. `main._attach_domain_context`
içinde:

| Hata | Sonuç |
|---|---|
| `atr=atr_alarm` — `atr_alarm` hiçbir yerde tanımlı değil | `NameError`, `except kart_hata` yutuyor → `domain_bolumleri` **her alarmda** boş kalıyor |
| `_goreli_guc_satiri` içinde `resample_ohlcv(...)` — `main.py`'ye import edilmemiş | `NameError`, `except` yutuyor → `· 20 mum endekse … puan` satırı hiç basılmıyor |

İki hata da geniş `except` bloklarının içinde olduğu için **hiçbir davranış testi
kırılmadı**; yalnızca Render logunda `Kart bağlamı hazırlanamadı …: name
'atr_alarm' is not defined` satırı vardı. Kart bu yüzden yalnız payload'dan
türeyen satırları (olay, kalite, bant, daralma, temas, geri çekilme, `· bozulur`,
CTA) basıyordu — yani kullanıcının gördüğü "basit" mesaj.

Düzeltme (23 Ekim):

1. `atr_alarm = atr_hesapla(df_tf)` — karne ile aynı fonksiyon; ölçüm kesitleri
   `normalin x katı` / `~1,05 TL` eşiklerini artık gerçek ATR'den okur. Bu, karta
   `◇ tutunca ~1,19 TL · %1,7` gibi ATR koşullu satırları geri getirdi.
2. `resample_ohlcv` `from data import ...` listesine eklendi.
3. Bağlam parçaları **ayrı try/except**'lere ayrıldı: `domain_context` (klasik
   metin), `domain_bolumleri` (kart bölümleri), `goreli`, `karsi_deliller`.
   Tek bir bölümün hatası artık diğerlerini düşürmüyor (25 Eyl dersinin devamı).
4. Yeni koruma testi: `test_tanimsiz_ad_korumasi.py` — modülleri çalıştırmadan
   AST ile tarar, Load edilen ama hiçbir yerde atanmayan ad varsa kırılır
   (`main.py`, `notifier.py`, `notification_context.py`, `notification_delivery.py`,
   `grafik.py`, `grafik_uret.py`, `telegram_alert_flow.py`, `ampirik_referans.py`).

Düzeltmeden sonra aynı olay (AKBNK 4s, gerçek `bot_data`) kartı:

```
▼ AKBNK 4s AŞAĞI TEYİTLİ
Alçalan Üçgen — kapanışla
🕒 23 Ekim 06:30→10:30 mumu
· kapanış 70,95 · sınır 65,97

▼ destek · blok 1s 70,40 −%0,8
· kalite 80/100 — güç 99
· bant 49 mum (30 Eylül'den)
· daralma %100
· temas üst 2 / alt 2

◈ 4s yapı dış ve iç aşağı döndü
geri çekilme yok · 1g de onaylı

◇ 32321 formasyon · %76 tuttu
◇ tutunca ~1,19 TL · %1,7
◇ geri çekilme %35 · 28624
· geçmiş davranış, kazanç değil

katılım 4s veri yok
katılım 1s hacim bitti (0,86)

ters işaret: hacim teyitsiz
· bozulur: 65,97 üstü kapanış

• yatırım tavsiyesi değildir
```

20 dolu satır (tavan 20), 551 kr (tavan 1100). `§2` iskeletinden bilinçli
sapmalar: `› /tara` satırı 2026-10-22 kararıyla yok; `× geçersiz:` yerine
`· bozulur:` yazılıyor (aynı bilgi, kullanıcı dili); bölge listesi yerine tek
`▼/▲ engel` satırı (en yakın bölge) — kullanıcı kararı 2026-10-22, kart 20
satırı aşmasın.

**Teşhis notu:** aynı belirti (bölümsüz kart) bağlamın gerçekten boş olduğu
durumda da görülür; ayırt etmek için logda
`Kart bağlamı hazırlanamadı` / `Domain runner yüklenemedi` satırına bakılır.

### 7.11 23 Ekim 2026 — sade dil revizyonu (kullanıcı onaylı metin)

Kullanıcı §7.10 sonrası kartı okudu ve *"metni biraz konuşmalıyız, anlam olarak
pek olmamış, karışık yani bilmeyen biri için"* dedi. Ölçüt tek: **hiç bilmeyen
biri kartı tek başına okuyup ne olduğunu anlatabilmeli.** Her sayı neyin ölçüsü
olduğunu kendi satırında taşır; jargon yok, kısaltma yok.

Onaylanan kart (AKBNK 4s, gerçek `bot_data`) — **20 dolu satır / 573 kr**,
her satır ≤ 262,8 px (bütçe 283 px × 0,95 − 6):

```
▼ AKBNK 4s AŞAĞI KIRILIM
Alçalan Üçgen — kapanış onaylı
🕒 23 Ekim 06:30→10:30 mumu
· kapanış 63,95 · kırılan 65,97

▼ destek bölgesi 4s 70,40 (%0,8 uzak)
· formasyon kalitesi 80/100
· kırılım gücü 99/100
· bant 49 mum, %55 daralma
· üste 2, alta 2 kez değdi

◈ 4s yön aşağı (iç ve dış yapı)
· kırılan seviyeye dönüş yok
· günlük de aynı yönde

◇ benzer 32.321 kurulum
   %76'sı devam etti · %35 geri
◇ tutarsa tepe ~1,19 TL (+%1,7)
geçmiş davranıştır, kazanç değil

hacim: 1s tükendi (0,86×)

olumsuz: hacim teyidi yok
· teyit düşer: 65,97 üstü kapanış

• yatırım tavsiyesi değildir
```

#### Sözcük tablosu (eski → onaylanan)

| Eski | Yeni | Neden |
|---|---|---|
| `TEYİTLİ` / `RETEST BAŞARILI` / `GEÇERSİZLEŞTİ` | `KIRILIM` / `SEVİYE KORUNDU` / `KIRILIM İPTAL` | olayın adı; teyidin türü ikinci satırda (`kapanış onaylı`) |
| `· kalite 80/100 — güç 99` | `· formasyon kalitesi 80/100` + `· kırılım gücü 99/100` | iki 100'lük sayı etiketsizdi |
| `· sınır 65,97` | `· kırılan 65,97` | hangi sınır? kırılan bant sınırı |
| `· bozulur: … kapanış` | `· teyit düşer: … kapanış` | "ne bozulur" belirsizdi |
| `· bant 49 mum (30 Eylül'den)` + `· daralma %100` | `· bant 49 mum, %55 daralma` | tarih iki satırı şişiriyordu; daralma bandın ölçüsü |
| `· temas üst 2 / alt 2` | `· üste 2, alta 2 kez değdi` | "temas" jargon |
| `◈ 4s yapı dış ve iç aşağı döndü` | `◈ 4s yön aşağı (iç ve dış yapı)` | hangi yön, neye göre |
| `geri çekilme yok · 1g de onaylı` | `· kırılan seviyeye dönüş yok` + `· günlük de aynı yönde` | iki jargon tek satırdaydı |
| `◇ 32321 formasyon · %76 tuttu` | `◇ benzer 32.321 kurulum` + `   %76'sı devam etti · %35 geri` | "%76 kazanç" diye okunuyordu |
| `◇ tutunca ~1,19 TL · %1,7` | `◇ tutarsa tepe ~1,19 TL (+%1,7)` | "tutunca" koşulsuz hedef gibi okunuyordu |
| `· geçmiş davranış, kazanç değil` | `geçmiş davranıştır, kazanç değil` (TEK satır) | "geçmişte önerilmiş" gibi okunuyordu; tam hâli 330 px, bütçeye sığan sözcük ekonomisi |
| `katılım 4s veri yok` | `hacim: 4s yok (endeks)` / hissede **satır yok** | hissede bilgi yokluğu kart yeri hak etmiyor |
| `katılım 1s hacim bitti (0,86)` | `hacim: 1s tükendi (0,86×)` | ölçü etiketli, × çarpan olarak yazılır |
| `ters işaret: …` | `olumsuz: …` | neyin tersi? |
| `▼ destek · blok 1s 70,40 −%0,8` | `▼ destek bölgesi 4s 70,40 (%0,8 uzak)` | `blok` jargon; `−%` işareti yön sanılıyordu |

#### Aynı turda kapatılan iki kusur

1. **Kopya alarmlar** (ALARK 4s ×3, KCHOL 2s ×3): mühür `formation_id` ile
   tekilleşiyordu; motor aynı kurulumu her taramada yeni kimlikle üretince mühür
   tutmuyordu. `notifier._kart_kopyasi_mi` artık **kartın kendisine** bakar:
   aynı hisse+TF+state için birebir aynı metin, mühür TTL'i içinde ikinci kez
   gönderilmez. Fiyat/kapanış/kalite değişirse metin değişir → gerçekten yeni
   olay geçer. `TELEGRAM_ALERT_STYLE=klasik` de aynı kapıdan geçer (metin
   değişmez, yalnız kopya gönderilmez).
2. **`· bozulur` ↔ `· sınır` çelişkisi** (DOHOL: kırılan 16,87, eşik 16,83):
   eşik motorun kuralıdır (kapanış bandın içine dönerse teyit düşer) ve bant
   daraldıkça kırılan seviyenin öbür tarafına düşebilir. Eşik kırılana **eşit
   değilse** satır artık `· teyit düşer: bant 16,83 üstü` biçiminde yazılır;
   iki sayı farklı nesnelere (kırılan seviye / bant) ait olduğu görülür.

#### Ölçü bloğu ve sığmayan satırlar

Ölçü bloğu iki seviyeli yazılır: başlık **kaç benzer kurulum** olduğunu söyler
(`◇ benzer 32.321 kurulum`), alt satır yüzdeyi taşır (`   %76'sı devam etti ·
%35 geri`). İkinci satır girintilidir çünkü başlığın DEVAMI olduğunu böyle
gösterir; kart sözleşmesi girintili devam satırını yalnız bu blokta kabul eder.

Satır bütçesi (262,8 px) aşılırsa kırpma yapılmaz, sırayla kısalır: `· bant 49
mum, %55 daralma` → `· bant %55 daralma`; `· teyit düşer: 65,97 üstü kapanış`
→ `· teyit düşer: 65,97 üstü`. Eşik kırılan seviyeye EŞİT DEĞİLSE (bant
daraldığı için olabilir) satır `· teyit düşer: bant 16,83 üstü` biçimini alır —
iki sayının farklı nesnelere (kırılan seviye / bant) ait olduğu görülür.

#### `/grafik` metni

Albüm tek başına yanıttı; hangi hisseye ait olduğunu söyleyen metin yoktu.
2026-10-23'ten beri karelerden **sonra** tek özet mesajı gider (hisse en başta):

```
📈 THYAO · grafik hazır
1s · 2s · 4s · 1g · 4 kare · 3,2 sn
```

İkinci satır bütçeye göre kısalır (süre → görünüm seçimleri → kare sayısı);
hisse ve TF listesi her zaman kalır.
