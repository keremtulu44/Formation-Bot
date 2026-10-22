# Alarm kartı — sade dil sürümü (2026-10-21 · v2)

> **Durum:** Önizleme — **kod değişmedi**, onay bekliyor
> **Bu turda:** teknik kısaltmalar kaldırıldı (`n1651`, `ATR`, `RVOL`, `MTF`, `BOS`, `OB/FVG`, `bar`)
> **Ölçüm:** her satır `telegram_measure.genislik()` ile ölçüldü · bütçe **262 px**
> **Onaylanan 4 karar uygulandı:** 3 boş satır · 3 ölçü satırı · public 1 kare + üst TF · MS uyarısı yalnız `/durum`

---

## 1 · Kart böyle gelecek

```
▲ SISE 4s YUKARI TEYİTLİ
Yükselen Üçgen — kapanışla
🕒 21 Ekim 13:30→17:30 mumu
· kapanış 39,60 · sınır 39,26
▲ yukarıda boşluk 41,90 — %5,8
· kalite 81/100 — güç 100
· 30 Eylül'den beri 94 mum

◈ yön yukarı · kısa vade uyumlu
test edilmedi · 1g de yukarı

◇ bölge normalin 1,4 katı
◇ kırılım sürdü %75 · 1651 kayıt
◇ direnç→destek %80 · 15724

hacim normalin 0,45 katı
ters işaret: kısa vade aşağı
· bozulur: 39,26 üstü kapanış
› /tara SISE
• yatırım tavsiyesi değildir
```

**20 satır · 478 karakter · en geniş satır 259 px** (bütçe 262 → sarmaz)

Okunuşu, sırayla: **ne oldu → önünde ne var → yön uyuyor mu → geçmişte nasıl bitti → hacim → nerede bozulur.**
Hiçbir satırda kısaltma yok; hepsi bir cümle gibi okunur.

---

## 2 · İkinci örnek — farklı aile (boşluk/FVG)

```
▲ THYAO 4s AŞAĞI TEYİTLİ
Simetrik Üçgen — kapanışla
🕒 21 Ekim 13:30→17:30 mumu
· kapanış 288,50 · sınır 289,75
▼ aşağıda blok 284,00 — %1,6
· kalite 74/100 — güç 88
· 9 Ekim'den beri 38 mum

◈ yön aşağı · kısa vade uyumlu
test edilmedi · 1g de aşağı

◇ bölge normal genişlikte
◇ boşluk kapandı %41 · 18594
◇ hacim yüksekken %61 sürdü

hacim normalin 2,8 katı
ters işaret: kısa vade yukarı
· bozulur: 289,75 üstü kapanış
› /tara THYAO
• yatırım tavsiyesi değildir
```

**20 satır · 471 karakter · en geniş 251 px**

Üç fark, üçü de sade yazılmış: `boşluk` = FVG (tek kullanımlık), `blok` = OB,
`hacim yüksekken %61 sürdü` = eski "Q4 RVOL %61 · 4/4 TF n11928".

---

## 3 · Diğer üç durum

### Geçersizleşme · 16 satır · 348 kr · 251 px

```
▼ AKBNK 1s GEÇERSİZLEŞTİ
Alçalan Üçgen - bandına dönüş
🕒 21 Ekim 16:30→17:30 mumu
· dönüş sınırı 38,79 üstü
· kapanış 39,05 · %0,7 içeri
· 12 Ekim'den beri 61 mum

◈ yön aşağı · kısa vade uyumlu
test var · 4s onayı yok

◇ seviye tutmadı %73 · 13573

hacim normalin 1,6 katı
ters işaret: hacim desteği yok
› /tara AKBNK
• yatırım tavsiyesi değildir
```

`▲ yukarıda …` ve `· bozulur` satırları **basılmaz** — olay zaten bozuldu.

### Veri eksik · 11 satır · 207 kr · 251 px

```
◆ GARAN 2s GEÇERSİZLEŞTİ
· kapanış 122,40
🕒 21 Ekim 15:30→17:30 mumu
· 14 Ekim'den beri 27 mum

◇ yapı verisi yok · atlandı
hacim verisi yok

ters işaret: veri yok
› /tara GARAN
• yatırım tavsiyesi değildir
```

Boş bırakmak yerine **"veri yok" yazıyor**. Altyapı arızası (`MS domain devre dışı`)
karta değil `/durum`'a gider (karar D); kartta yalnız bu hisseye ait eksik kalır.

### Güncelleme · 6 satır · 154 kr · 251 px

```
▲ SISE 4s YUKARI TEYİTLİ
Yükselen Üçgen — kapanışla
🕒 21 Ekim 13:30→17:30 mumu
değişiklik yok · yapı/bölge aynı
› /tara SISE
• yatırım tavsiyesi değildir
```

---

## 4 · Ne değişti: teknik sözcük → sade sözcük

| Eski kart | Yeni kart | Neden |
|---|---|---|
| `n1651` | `1651 kayıt` | `n` istatistik kısaltması, kimse bilmiyor |
| `ATR` | `normalin 1,4 katı` | ATR bir formül adı; "normal" aynı şeyi anlatıyor |
| `RVOL 0,45` | `hacim normalin 0,45 katı` | oranın neye göre olduğu yazılı |
| `MTF 1g onaylı` | `1g de yukarı` | "MTF" piyasa terimi değil, kod terimi |
| `BOS ↑ dış devam` | `kırılım sürdü` | BOS = break of structure, İngilizce kısaltma |
| `MS` / `iç yapı` | `yön` / `kısa vade` | MS kod adı; "yön" herkesin anladığı |
| `FVG` | `boşluk` | FVG = fair value gap |
| `OB` | `blok` | OB = order block |
| `tam dolum` | `boşluk kapandı` | dolum borsacı dili, "kapanma" net |
| `rol uyumlu` | `direnç→destek` | rol ne demek belirsiz; ok ne yaptığını gösteriyor |
| `bar` | `mum` | mum Türkçe trading dilinde standart |
| `seviye` | `sınır` | eşik mi direnç mi belirsizdi |
| `karşı delil` | `ters işaret` | delil hukuk dili; işaret daha kısa |
| `◇ Q4 RVOL %61 · 4/4 TF` | `◇ hacim yüksekken %61 sürdü` | çeyrek/dilim hesabı kullanıcıya gerekmiyor |

**Kartta hiç görünmeyecek olanlar:** `n` sembolü, TF kısaltması (yerine `4s`/`1g` yazılıyor),
`sessiz MS çökmesi` uyarısı, GA aralıkları, ölçülemeyen soru numaraları.

---

## 5 · Semboller — 8 tane, hepsi tek anlamlı

| Simge | Anlam | Örnek |
|---|---|---|
| `▲ ▼ ◆` | olayın yönü (◆ = yönsüz/geçersiz) | `▼ AKBNK 1s GEÇERSİZLEŞTİ` |
| `🕒` | hangi mum kapandı | `🕒 21 Ekim 13:30→17:30 mumu` |
| `◈` | grafikteki yapı | `◈ yön yukarı · kısa vade uyumlu` |
| `◇` | arşivden ölçüm (hepsinde kayıt sayısı var) | `◇ kırılım sürdü %75 · 1651 kayıt` |
| `·` | ölçünün künyesi | `· 30 Eylül'den beri 94 mum` |
| `→` | seviyenin rol değiştirmesi | `◇ direnç→destek %80` |
| `›` | komut | `› /tara SISE` |
| `•` | uyarı | `• yatırım tavsiyesi değildir` |

Bloklar arası boş satır (onaylanan karar A): göz 3 saniyede 4 blok bulur.

---

## 6 · Bugünkü kart → yeni kart

> Soldaki **eski** metin, sağdaki yeni. Bu blok karşılaştırma içindir; gönderilmez.

```
BUGÜN                          YENİ
▲ SISE 4s YUKARI TEYİTLİ       ▲ SISE 4s YUKARI TEYİTLİ
Yükselen Üçgen — kapanışla     Yükselen Üçgen — kapanışla
· kapanış 39,60 (seviye 39,26) 🕒 21 Ekim 13:30→17:30 mumu
· kalite 81/100 — güç 100      · kapanış 39,60 · sınır 39,26
· bant 94 bar                   ▲ yukarıda boşluk 41,90 — %5,8
· 30 Eylül'den beri            · kalite 81/100 — güç 100
retest yok — MTF 1g onaylı     · 30 Eylül'den beri 94 mum
katılım 4s destekliyor         ─────
· bozulur 39,26 üstü kapanış   ◈ yön yukarı · kısa vade uyumlu
› /tara SISE                   test edilmedi · 1g de yukarı
• yatırım tavsiyesi değildir   ─────
                               ◇ bölge normalin 1,4 katı
                               ◇ kırılım sürdü %75 · 1651 kayıt
                               ◇ direnç→destek %80 · 15724
                               ─────
                               hacim normalin 0,45 katı
                               ters işaret: kısa vade aşağı
                               · bozulur: 39,26 üstü kapanış
                               › /tara SISE
                               • yatırım tavsiyesi değildir
```

| | Bugün | Yeni |
|---|---|---|
| satır | 10 | 20 |
| karakter | ~250 | 478 (tavan 1100) |
| ölçüm satırı | 0 | 3 |
| kısaltma | 3 (`MTF`, `bar`, `retest`) | 0 |
| "ne kadar" bilgisi | yok | `%5,8` (önündeki mesafe) |
| "kaç kez tuttu" | yok | `%75 · 1651 kayıt` |

---

## 7 · Uygulama (onay sonrası)

| Adım | Dosya | İş |
|---|---|---|
| 1 | `notifier.py` | 4 blok + 3 boş satır, 20 satır sınırı |
| 2 | `notification_context.py` | `engel` → `boşluk/blok`, `yapi_ozet` → sade cümle |
| 3 | `ampirik_referans.py` | `normalin x katı`, `kırılım sürdü % · kayıt`, `direnç→destek` |
| 4 | metin testleri | 13–20 satır, ≤262 px, yasak sözcük listesi (`n1…`, `ATR`, `RVOL`, `MTF`, `BOS`, `FVG`, `OB`, `bar`) |
| 5 | `config.py` | public görsel = 1 kare + üst TF (kart metnini etkilemez) |
| 6 | geri dönüş | `TELEGRAM_KART_SURUM=sade` / `eski` |

**Yasak sözcük testi** en önemlisi: bir gün koda yeni bir kısaltma eklenirse test kırmızı
olur, kart sessizce teknikleşmez.

---

## 8 · Kartın söylemediği şeyler

- Hedef, stop, pozisyon, kâr garantisi: yok.
- `%75`, "bu alarm %75 kazanır" demek değil — "arşivde böyle 1651 olayın %75'i devam etti".
- Kayıt sayısı 50'nin altındaysa satır basılmaz.
- Ölçümü olmayan hiçbir satır uydurulmaz; veri yoksa `veri yok` yazar.
