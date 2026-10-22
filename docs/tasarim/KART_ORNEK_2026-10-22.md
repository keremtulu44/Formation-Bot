# Alarm kartı — uygulanmış sürüm (2026-10-22 · v3)

> **Durum:** Uygulandı (kod + test) · önceki öneri: [KART_ORNEK_2026-10-21.md](KART_ORNEK_2026-10-21.md)
> **Kod:** `notifier._format_lifecycle_alert_kart_sade` (7 blok)
> **Bütçe:** satır ≤ 262,8 px (`_kart_esik_px()`), tavan 20 dolu satır
> **Ölçüm bloğu:** `ampirik_referans.olcum_satirlari` — DM 3 satır, public 2 satır
> **Aile ayrımı:** formasyon alarmı yalnız `FRM` ölçümünü basar (MS/zone satırı girmez)

---

## 1 · DM kartı — teyitli kırılım

```
▲ SISE 4s YUKARI TEYİTLİ
Yükselen Üçgen — kapanışla
🕒 21 Ekim 13:30→17:30 mumu
· kapanış 39,60 · sınır 39,26

▲ direnç · boşluk 4s 41,90 +%5,8
· kalite 81/100 — güç 100
· bant 94 mum (30 Eylül'den)

◈ 4s yapı dış ve iç yukarı
geri çekilme yok · 1g de onaylı

◇ 32321 formasyon · %76 tuttu
◇ tutunca ~1,05 TL · %2,6
◇ rol uyumlu %80 · 15724
· geçmiş davranış, kazanç değil

katılım 4s hacim 0,45 kat

ters işaret: iç yapı aşağı döndü
· bozulur: 39,96 altı kapanış

• yatırım tavsiyesi değildir
```
**23 satır (17 dolu) · 493 karakter · en geniş 262 px**

### Geçersizleşme kartı
```
▼ AKBNK 1s GEÇERSİZLEŞTİ
Alçalan Üçgen — bandına dönüş
🕒 21 Ekim 16:30 mumu
· dönüş sınırı 38,79 üstü

· kalite 76/100 — güç 70
· bant 61 mum (12 Ekim'den)

geri çekilme var · 4s onayı yok

◇ 32321 formasyon · %76 tuttu
◇ rol uyumsuz %73 · 13573
· geçmiş davranış, kazanç değil

katılım 1s hacim düşük (0,42)

• yatırım tavsiyesi değildir
```
**17 satır (12 dolu) · 339 karakter · en geniş 257 px**

### Bağlam değişmedi (kısa güncelleme)
```
▲ SISE 4s YUKARI TEYİTLİ
Yükselen Üçgen — kapanışla
🕒 21 Ekim 13:30 mumu
· kapanış 39,60 · sınır 39,26

▲ direnç · boşluk 4s 41,90 +%5,8
· kalite 81/100 — güç 100
· bant 94 mum (30 Eylül'den)

◈ 4s yapı dış ve iç yukarı
geri çekilme yok · 1g de onaylı

◇ 32321 formasyon · %76 tuttu
◇ tutunca ~1,05 TL · %2,6
◇ rol uyumlu %80 · 15724
· geçmiş davranış, kazanç değil

katılım 4s hacim 0,45 kat

ters işaret: iç yapı aşağı döndü
· bozulur: 39,96 altı kapanış

• yatırım tavsiyesi değildir
```
**23 satır (17 dolu) · 487 karakter · en geniş 262 px**

Okunuş sırası: **ne oldu → önünde ne var → yapı uyuyor mu → arşivde nasıl bitti → hacim → nerede bozulur.**
Ölçüm satırlarının hepsi cümle gibi okunur: kısaltma yok, `n` yerine düz sayı,
`tamamlandı` yerine **tuttu** (motorun `FORMASYON_TAMAMLANDI` hâli "hedefe
ulaştı" değil, "kırılım teyit aldı ve bandın içine dönmedi" demek).

---

## 2 · Public bülten (grup) — aynı 7 blok

```
📊 Bülten · 2 gelişme
   22 Eki 09:35

▲ SISE 4s YUKARI TEYİTLİ
Yükselen Üçgen — kapanışla
🕒 21 Ekim 13:30→17:30 mumu
· kapanış 39,60 · sınır 39,26

▲ direnç · boşluk 4s 41,90 +%5,8
· kalite 81/100 — güç 100
· bant 94 mum (30 Eylül'den)

◈ 4s yapı dış ve iç yukarı
geri çekilme yok · 1g de onaylı

◇ 32321 formasyon · %76 tuttu
◇ tutunca ~1,05 TL · %2,6
· geçmiş davranış, kazanç değil

katılım 4s hacim 0,45 kat

ters işaret: iç yapı aşağı döndü
· bozulur: 39,96 altı kapanış

▼ GARAN 1s GEÇERSİZLEŞTİ
Alçalan Üçgen — bandına dönüş
🕒 21 Ekim 16:30 mumu
· dönüş sınırı 38,79 üstü

· kalite 76/100 — güç 70
· bant 61 mum (12 Ekim'den)

geri çekilme var · 4s onayı yok

◇ 32321 formasyon · %76 tuttu
◇ rol uyumsuz %73 · 13573
· geçmiş davranış, kazanç değil

katılım 1s hacim düşük (0,42)

📌 yatırım tavsiyesi değildir
```

**Public kuralı: ◇ en fazla 2 satır · görsel 1 kare + üst TF · tek yasal uyarı**

**Değişen tek şey:** ölçü bloğu bülten kalabalığında **2 satır** (DM 3),
yasal uyarı bültede **tek kez** yazılır ve her olayın ardından **1 kare + üst
zaman dilimi** görseli gider (DM 4 kare alır). Bülten ile kare aynı veriden
çizilir; motor yeniden koşmaz.

---

## 2b · Beklenti hükmü (`TELEGRAM_KART_TAHMIN=1`, varsayılan KAPALI)

Ölçü bloğunun başına tek kelimelik hüküm eklenir; slot sayısı değişmez
(hüküm + sayaç + 1 ölçüm = 3):

```
◇ beklenti: devam
◇ 2 ölçüm lehte
◇ 32321 formasyon · %76 tuttu
· geçmiş davranış, kazanç değil
```

Çelişki varsa hüküm `kararsız` olur ve aleyhte olanın **adı** yazılır:

```
◇ beklenti: kararsız
◇ 1 ölçüm lehte · 1 aleyhte
◇ aleyhte: hacim yüksek
```

Yön kanıtı yoksa (ölçüm eşiği geçmedi) **hiçbir satır basılmaz** — kart bugünkü
hâline döner. Bu bir yön tahmini değil: NET %95 GA 11 hücrenin 10'unda sıfırı
içeriyor, "yukarı gider" cümlesinin kanıtı yok. Ayrıntı ve eşik tablosu:
`docs/arastirma/AMPIRIK_REFERANS.md` → "Beklenti hükmü".

---

## 3 · Sade dil sözlüğü (uygulanan)

| Kartta yok | Yerine gelen | Neden |
|---|---|---|
| `n1651` | `1651` | taban düz sayı; `n` etiketi okunmuyordu |
| `BOS` / `CHoCH` | `kırılım` / `dönüş` | kesit adı düz Türkçe |
| `ATR` | `normalin x katı`, `~1,05 TL · %2,6` | okumak için ATR bilmek gerekmiyor |
| `RVOL` | `hacim 0,45 kat` | kısaltma kartta yaşamaz |
| `OB` / `FVG` | `blok` / `boşluk` | aynı şey, herkesin sözcüğü |
| `bar` | `mum` | aynı şey |
| `retest` | `geri çekilme` | jargon |
| `↑` / `↓geçiş` | `yukarı` / `aşağı döndü` | ok tek başına yön söylemiyordu |
| `tipik` | yok | yasak (kullanıcı kararı) |
| `zayıf`, `güçlü`, `muhtemel` | yok | ölçü satırında sıfat taşınmaz |

---

## 4 · Sınırlar (kartın söylemediği)

- `◇` satırları **kazanç değil, geçmiş davranış**; karta dipnot olarak da yazılır
  (`· geçmiş davranış, kazanç değil`).
- MFE ≠ NET: `◇ tutunca ~1,05 TL` 12 mum içindeki **lehte tepe** hareketin
  medyanıdır; kapanış kazancı değildir, maliyet/kayma/çıkış kuralı yoktur.
- Farklı tabanlı yüzdeler yan yana konmaz: formasyon kartında MS `%75 devam
  etti` satırı **basılmaz** (aile süzgeci).
- `n < 300` kesitlerde `◇ nadir (n) · yorum yok` yazılır.
- "giderse tamamlanır" koşullu cümlesi **yazılmadı**: `asim_*` ×
  `sonuc_durum=tamamlandı` çaprazı ölçülmeden basılmaz (açık iş).
