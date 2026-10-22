# Örnek mesajlar — DM ve public (22 Ekim 2026)

Bu dosyadaki metinler **elle yazılmadı**: aynı kodla (`notifier` biçimleyicileri)
üretildi, sonra markdown'a alındı. Yani aşağıdaki satırlar, satır bütçesi ve
sayılar gerçek çıktıdır. Sayılar örnektir (THYAO/XBANK/ISMEN/ASELS kurgu veri),
biçim gerçektir.

- Kart sözleşmesi: [`TELEGRAM_KART_FORMAT.md`](TELEGRAM_KART_FORMAT.md)
- Evren ve endeks/makro kararı: [`EVREN_GENISLETME.md`](EVREN_GENISLETME.md)

---

## 1. DM · teyitli kırılım (hisse, hacim var)

**THYAO 4s · Yükselen Üçgen**

```
▲ THYAO 4s YUKARI TEYİTLİ
Yükselen Üçgen — kapanışla
🕒 22 Ekim 14:30 mumu
· kapanış 312,50 · sınır 309,00

· kalite 84/100 — güç 100
· bant 12 mum (30 Eylül'den)

◈ 4s yapı dış ↑, iç ↑
· 20 mum endekse +4,6 puan
geri çekilme var · 1g de onaylı

◇ 32321 formasyon · %76 tuttu
◇ 1651 kırılımın %75'i sürdü
◇ hacim yüksekken %79 sürdü
· geçmiş davranış, kazanç değil

katılım 4s destekliyor

· bozulur: 318,00 altı kapanış

• yatırım tavsiyesi değildir
```

*22 satır · 16 dolu · 449 kr · en geniş 253,5 px (eşik 262,85)*

**Nasıl okunur**

| Blok | Satır | Ne söylüyor |
|---|---|---|
| OLAY | `▲ THYAO 4s YUKARI TEYİTLİ` | ne oldu, hangi yönde, hangi zaman diliminde |
| | `Yükselen Üçgen — kapanışla` | hangi formasyon, nasıl tamamlandı |
| | `🕒 22 Ekim 14:30 mumu` | hangi mumun kapanışıyla |
| | `· kapanış 312,50 · sınır 309,00` | kapanış ve aşılan sınır |
| ÖNÜNDE | `· kalite 84/100 — güç 100` | kurulum kalitesi, kırılım gücü |
| | `· bant 12 mum (30 Eylül'den)` | formasyon kaç mumdür, ne zamandan beri |
| YAPI | `◈ 4s yapı dış ↑, iç ↑` | piyasa yapısı kırılımla aynı yönde mi |
| | `· 20 mum endekse +4,6 puan` | XU100'e göre 20 mumluk fark |
| | `geri çekilme var · 1g de onaylı` | geri çekilme oldu mu, üst TF onayı |
| ÖLÇÜ | `◇ …` 3 satır | geçmişte benzer kurulumlar ne yaptı |
| | `· geçmiş davranış, kazanç değil` | oran "kazanç" diye okunmasın |
| KATILIM | `katılım 4s destekliyor` | hacim kırılımı destekliyor mu |
| SINIR | `· bozulur: 318,00 altı kapanış` | hangi kapanış bu teyidi bozar |

---

## 2. DM · teyitli kırılım (endeks, hacim yok)

**XBANK 4s · direnç kırılımı**

```
▲ XBANK 4s YUKARI TEYİTLİ
Direnç Kırılımı — kapanışla
🕒 22 Ekim 14:30 mumu
· kapanış 13482,50
· sınır 13380,00

· kalite 81/100 — güç 100
· bant 7 mum (30 Eylül'den)

◈ 4s yapı dış ↑, iç ↑
· 20 mum endekse +1,2 puan
geri çekilme var · 1g de onaylı

◇ 32321 formasyon · %76 tuttu
◇ 1651 kırılımın %75'i sürdü
· geçmiş davranış, kazanç değil

katılım 4s hacim yok (endeks)
yön fiyattan okunur

· bozulur: 13510,00 altı kapanış

• yatırım tavsiyesi değildir
```

*23 satır · 17 dolu · 454 kr · en geniş 253,5 px*

Endeks kartının hisse kartından **tek farkı** KATILIM bloğu ve fiyat ölçeği:

1. `hacim yok (endeks)` — "veri yok" değil: veri var, hacim alanı boş.
   İkinci satır `yön fiyattan okunur` ne demek istediğimizi söyler.
2. Fiyat 5 haneli olunca `· kapanış · sınır` birleşik satırı 279,5 px'e çıkıyor
   ve bölünüyordu; artık bölme **iki tam satır** olarak yapılıyor (girintili
   devam satırı yasak).

---

## 3. DM · geçersizleşti

**THYAO 4s · geri dönüş**

```
▲ THYAO 4s GEÇERSİZLEŞTİ
Yükselen Üçgen - bandına dönüş
🕒 22 Ekim 14:30 mumu
· dönüş sınırı 318,00 altı

· kalite 84/100 — güç 100
· bant 12 mum (30 Eylül'den)

geri çekilme yok · 1g onayı yok

katılım 4s destek yok

• yatırım tavsiyesi değildir
```

*13 satır · 9 dolu · 245 kr · en geniş 260,5 px*

Geri alma kartı kısadır: ölçüm satırları ve göreli güç **basılmaz** — teyit
zaten geçmişte kaldı, geçmiş istatistiği tekrar okumak yanıltıcı olur.

---

## 4. PUBLIC · bülten (3 olay tek mesaj)

```
📊 Bülten · 3 gelişme
   22 Eki 18:12

▲ THYAO 4s YUKARI TEYİTLİ
Yükselen Üçgen — kapanışla
🕒 22 Ekim 14:30 mumu
· kapanış 312,50 · sınır 309,00

· kalite 84/100 — güç 100
· bant 12 mum (30 Eylül'den)

◈ 4s yapı dış ↑, iç ↑
· 20 mum endekse +4,6 puan
geri çekilme var · 1g de onaylı

◇ 32321 formasyon · %76 tuttu
◇ 1651 kırılımın %75'i sürdü
· geçmiş davranış, kazanç değil

katılım 4s destekliyor

· bozulur: 318,00 altı kapanış

▲ ISMEN 2s RETEST BAŞARILI
Yükselen Üçgen
🕒 22 Ekim 14:30 mumu
· kapanış 41,02 · sınır 40,80

· kalite 86/100 — güç 100
· bant 5 mum (30 Eylül'den)

◈ 2s yapı dış ↑, iç ↑
· 20 mum endekse +0,8 puan
geri çekilme var · 4s de onaylı

◇ 32321 formasyon · %76 tuttu
◇ rol 41,00 %71 · 486
· geçmiş davranış, kazanç değil

katılım 2s destekliyor

· bozulur: 41,60 altı kapanış

▲ ASELS 1s YUKARI TEYİTLİ
Bayrak — kapanışla
🕒 22 Ekim 14:30 mumu
· kapanış 88,15 · sınır 87,60

· kalite 81/100 — güç 100
· bant 2 mum (30 Eylül'den)

◈ 1s yapı dış ↑, iç ↑
· 20 mum endekse +1,4 puan
geri çekilme yok · 4s de onaylı

◇ 32321 formasyon · %76 tuttu
· geçmiş davranış, kazanç değil

katılım 1s destekliyor

· bozulur: 89,40 altı kapanış

📌 yatırım tavsiyesi değildir
```

*63 satır · 44 dolu · 1182 kr · en geniş 253,5 px · bütçe 3300 kr*

**Public ile DM arasındaki fark metinde üç noktada:**

| | DM | Public |
|---|---|---|
| Mesaj sayısı | olay başına 1 kart | olaylar **tek bültende** |
| Ölçü satırı | 3 `◇` | 2 `◇` |
| Yasal uyarı | her kartta | bültede **bir kez**, sonda |

Geri kalan her şey birebir aynıdır — aynı biçimleyici, aynı 283 px satır bütçesi,
aynı sade dil. Bülten 3300 kr'yi aşarsa olay **kesilmez**, sonraki bültene kalır
(12 olay → 2 mesaj: 6+6).

---

## 5. Görsel: iki tarafta da nasıl geliyor

### DM — olay başına 4 kare, tek albüm

Sıra: alarmın kendi zaman dilimi **ilk** kare, sonra kalan zaman dilimleri
(`TELEGRAM_GRAFIK_ADET`, varsayılan 4). Hepsi **tek albüm** olarak gider, aralara
metin girmez. Albüm reddedilirse kareler tek tek yeniden denenir.

Alt yazılar (`caption`) — kısa, kartın satırlarını tekrarlamaz:

```
THYAO · 4s · 105 mum
THYAO · 1s · 220 mum
THYAO · 2s · 160 mum
THYAO · 1g · 60 mum
```

Geçersizleşmede tek kare ve alt yazıda mum sayısı yok: `THYAO · 4s`

### Public — olay başına 2 kare, metnin hemen ardından

1. **ana kare** (alarmın zaman dilimi), alt yazı `THYAO 4s · Yükselen Üçgen`
2. **üst zaman dilimi** karesi, alt yazı `THYAO 4s · 1g üst zaman dilimi`

Alt yazıda sıra: `SEMBOL <alarm TF> · …`. İkinci kare "üst zaman dilimi"
olduğunu kendi etiketiyle söyler (1h/2h → 4s, 4h → 1g).

### Örnek kareler

Sentetik veriyle, aynı çizim koduyla üretildi (`grafik_uret.py --demo --zone`);
gerçek alarmda motor çıktısı (OB/FVG/yapı) bu kutuların yerine geçer.

**Ana kare — 4s:**

![Örnek ana kare: THYAO 4s, OB kutuları ve yapı etiketleri](ornekler/ornek_ana_thyao_4h.png)

**Üst zaman dilimi — 1g (public'te ikinci kare):**

![Örnek üst TF karesi: THYAO 1g](ornekler/ornek_ust_thyao_1d.png)

Karenin taşıdığı bilgi kartta **tekrarlanmaz**: bölge kutuları, kırılan seviye,
temas işaretleri görselde; kart yalnız kararı ve sınırı yazar.

---

## 6. Görsel ne zaman gelmez

Görsel hiçbir koşulda **metni düşürmez**. Metin gider, görsel gider veya gider
ama sessiz kalmaz:

| Durum | Sonuç |
|---|---|
| `TELEGRAM_GRAFIK=yok` (varsayılan kapalı) | yalnız metin; sayaç "şalter kapalı" der |
| Kare üretilemedi (veri/kadraj) | metin gider, `/durum`da hata sayacı |
| Public kare gönderimi başarısız | metin kalır, log + sayaç |
| Diskte yer az (`DISK_MIN_BOS_MB` altı) | kareler üretilmez, sayaç artar |
| Restart kuyruk ile görsel arasında | metin gider, kare gitmez (açık madde) |

Görsel gönderildikten sonra dosya **her durumda silinir** — diskte çöp kalmaz.
