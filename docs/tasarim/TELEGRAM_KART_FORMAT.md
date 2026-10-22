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
   Kart dışı yüzeyler (bülten, özet, komut yanıtları, karne) için aynı bütçe
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
   sonucunu en çok **3** satırda (public bültende **2**) basar (koşul + n görünür, kaynak
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
◇ rol uyumlu %80 n15724               ← arşiv ölçümü (en çok 2 satır)
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

### 7.4 Public = DM

Grup bülteni aynı biçimleyiciyi `public=True` ile kullanır: aynı 7 blok, ölçü
2 satır, yasal uyarı bültede **tek kez**, her olayın ardından **1 kare + üst
zaman dilimi** görseli (DM 4 kare). `PUBLIC_MIN_ARALIK_SN` 1,2 → 2,0.

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
