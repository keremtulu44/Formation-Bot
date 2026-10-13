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
4. **Mesaj bütçesi: ≤ 1100 karakter.** 4096'lık Telegram tavanı değil, tek
   ekran sözümüzdür. 1100'ün altındaki boşluk "daha çok yazı" anlamına gelmez.
5. **Kaynakta olmayan veri yazılmaz.** `olay kalitesi`, `deneme sayısı`, OB
   yaşam döngüsü etiketi gibi motorun üretmediği alanlar kartta yok (motor OB
   için yalnız `state = ±1` veriyor — `domain_engines/order_block/order_block.py`).
6. **Bilgi kaybı yok.** Kartta çıkarılan her satır `/tara SEMBOL` çıktısında
   duruyor; `! karşı delil` satırı bu yüzden kartta.
7. **Klasik yol byte-byte duruyor.** `TELEGRAM_ALERT_STYLE=klasik` → 25 Eyl
   öncesi biçim. A/B karşılaştırma ve geri alma hakkı için korundu; kartta
   yapılan düzeltme klasik biçime uygulanmaz.

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
- **Grup bülteni satırları** klasik biçimde kaldı (en uzun satır 1 089 px); px
  kuralı yaşam döngüsü alarmlarına uygulanıyor. Group bülteni ayrı iş.
