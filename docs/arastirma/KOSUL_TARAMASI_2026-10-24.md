# Koşul taraması — formasyon dışı domainler (2026-10-24)

Soru: **formasyon kalitesi dışında** hangi ölçülebilir koşullar kırılımın devamını
ayırıyor ve bunlarla bir puanlama kurulabilir mi?

Veri: 177 sembol × 4 zaman dilimi, 7 Mayıs 2025 – 19 Ekim 2026.
Gözlem: 16.417 kırılım (etiket penceresi tamamlanmış).
Etiket: lehte 2,0 ATR / ters 1,0 ATR / 24 bar (ana); 7 varyantla duyarlılık.
Bölmeler: ayrık sembol (S) + uzak dönem/35 gün boşluk (Z). Yan yana blok (Y)
yalnızca tuzak göstergesi.

---

## 1. Taranan domainler ve ölçülen özellik sayısı

| Domain | Ne ölçüldü | Özellik |
|---|---|---|
| Trend / yapı | çoklu TF hizası, MA mesafeleri, Donchian kırılımı, HH/HL yapısı, BOS | 12 |
| Hacim | kırılım hacmi/20 ort., saat-düzeltilmiş hacim, hacim trendi, kuruma | 5 |
| Volatilite | ATR yüzdelik dilimi, ATR sıkışması (10/60) | 4 |
| Piyasa | endeks trendi, endeks gün içi, piyasa genişliği (breadth), enine dağılım | 6 |
| Konum | 52h zirve/dip mesafesi, üstteki direnç (headroom), zirveye yakınlık | 4 |
| Momentum | kırılım öncesi koşu, 20/60 bar getiri | 5 |
| Mikroyapı | gap, gövde içi kapanış konumu, bar aralığı, seans saati | 4 |
| Kesitsel | beta, endeks korelasyonu, göreli güç, akran (sektör) momentumu | 4 |
| Olay | retest, kırılım gecikmesi | 2 |
| Formasyon | kalite, güç, geometri, temas, olgunluk, daralma, bant | 11 |
| Takvim | ay, haftanın günü | 2 |

Toplam **59 özellik**, 16.417 gözlemde tarandı. Ayrıca ~110 eşik kombinasyonu.

---

## 2. Sonuç: kaç özellik geçti

Çoklu test düzeltmeli protokol (keşifte |AUC−0,5| ≥ 0,02 ve |z| ≥ 3,0,
iki doğrulamada aynı işaret, 7 etiket varyantında ≥ 6/7):

| özellik | AUC | z | S doğr. | Z doğr. | 7 varyant | hüküm |
|---|---|---|---|---|---|---|
| **retest görüldü** | 0,393 | −14,5 | +6,8 | +8,5 | 7/7 | geçti — ama **sızıntı** |
| **çoklu TF uyumu** | 0,530 | +4,1 | +4,4 | +3,1 | 7/7 | geçti — **trend filtresi** |
| kırılım hacmi/20 ort. | 0,525 | +3,3 | +1,4 | −0,1 | — | kaldı |
| kapanışın bar içi konumu | 0,521 | +2,8 | +1,7 | −1,3 | — | kaldı |
| endeks uyumu | 0,521 | +2,9 | +2,4 | +1,4 | — | kaldı (zayıf) |
| market structure (HH/HL) | 0,503 | +0,4 | +1,7 | +2,2 | — | **kaldı** |
| aynı TF yapı kırılımı (BOS) | 0,503 | +0,4 | +0,0 | +0,0 | — | **kaldı** |
| piyasa genişliği | 0,496 | −0,5 | −1,4 | +0,5 | — | kaldı |
| ATR sıkışması | 0,514 | +1,8 | −0,3 | +0,3 | — | kaldı |
| akran momentumu | ≈0,50 | ≈0 | — | — | — | kaldı |
| kalite (mevcut puan) | 0,492 | −1,2 | — | — | — | kaldı |

**MS/BOS hipotezi desteklenmedi.** Market structure yönü AUC 0,503 (z=0,4),
aynı-TF yapı kırılımı 0,503 (lift 0,0). Önceki araştırmadaki "MS %97-98 uyum,
devam %70" bulgusu bizim verimizde **kırılım sonucunu ayırmıyor**; o ölçüm
zone/MS tabanlı farklı bir veri setinden geliyordu.

---

## 3. Belirleyici olan tek şey var, o da formasyon değil

Çoklu TF uyumu kademeleri tekdüze:

| kademe | n | devam |
|---|---|---|
| 0 | 1.713 | %30,8 |
| 1 | 1.693 | %32,8 |
| 2 | 2.079 | %33,4 |
| 3 | 4.673 | %35,5 |
| 4 | 5.598 | %39,9 |

S doğrulamasında kademe 4: %40,5 · Z doğrulamasında %40,2. Sağlam.

**Ama aynı ölçü rastgele girişlerde birebir aynı sonucu veriyor:**

| kademe | kırılım | rastgele giriş | fark |
|---|---|---|---|
| 0 | %30,8 | %30,3 | +0,4 |
| 1 | %32,8 | %34,5 | −1,6 |
| 2 | %33,4 | %35,7 | −2,4 |
| 3 | %35,5 | %36,6 | −1,1 |
| 4 | %39,9 | %40,1 | **−0,2** |

Yani MTF uyumu **piyasa zamanlama filtresi**; formasyonun kalitesi değil.
Herhangi bir bardan trend yönünde girmek aynı oranı veriyor.

---

## 4. Formasyonun kendi katkısı ne kadar?

Eşleştirilmiş kontrol (her kırılım, aynı sembol + TF + ay + yön için hesaplanan
rastgele tabanla kıyaslanır; trend/mevsim/yön etkisi çıkarılır):

**Ortalama fazla: +1,6 puan** [%95 GA +0,8 … +2,4] (sembol kümesi bootstrap).

En iyi koşul alt kümesinde bile (MTF≥4 + breadth≥0,65):
kırılım %43,0 · aynı koşullarda rastgele %41,0 → **formasyonun fazlası +2,0 puan**.

Bu, "formasyon hiçbir şey katmıyor" demek değil; ama katkının büyüklüğü
±2 puan mertebesinde ve hiçbir formasyon-içi özellik bunun *hangisinde* daha
büyük olduğunu öngörmüyor (59 özellik, hepsi ≤ 0,53 AUC).

---

## 5. Kırılım sonrası okunabilen tek güçlü sinyal

| durum | n | devam |
|---|---|---|
| Bir sonraki bar bandın dışında kaldı (tutunma) | 13.792 | %39,1 |
| Bir sonraki bar bandın içine döndü (snap-back) | 1.964 | %13,9 |
| Retest olayı hiç görülmedi | 10.625 | %43,0 |
| Retest görüldü (medyan +2 bar) | 5.131 | %21,5 |

Bunlar **tahmin edici değil, kırılım sonrası teşhis**. Kart için değerli:
"seviyeye geri döndü, olasılık %39 → %14'e düştü" gibi bir uyarı gerçek.

Dikkat: bir bar gecikmeli girişte kazanç kayboluyor (gecikmeli %36,9,
anında %36,0). Yani snap-back filtresi bildirim kalitesini artırır ama işlem
kazancı sağlamaz.

---

## 6. Oynaklık hipotezi de kapandı

Kırılım sonrası 24 barlık oynaklık (max−min)/ATR = **5,33**;
rastgele girişlerde **5,32**. Oran 1,01x, 700 hücrenin %53'ünde kırılım yüksek.
Yani kırılımlar oynaklık patlaması da öngörmüyor.

---

## 7. Puanlama kurulabilir mi? Evet — ama "koşul puanı" olarak

Eşit ağırlıklı üç koşulla (çoklu TF uyumu + piyasa genişliği + endeks uyumu),
her gözlem yalnızca geçmiş veriyle puanlanarak (walk-forward):

| kapsam | gözlem | koşul puanı | mevcut kalite | fark |
|---|---|---|---|---|
| %10 | 1.546 | **%42,6** | %34,1 | **+8,5** |
| %20 | 3.092 | **%40,2** | %34,7 | +5,4 |
| %30 | 4.637 | %38,3 | %35,0 | +3,3 |
| %50 | 7.728 | %38,4 | %35,8 | +2,7 |

Puan dilimleri tekdüze: %31,6 · %34,7 · %37,0 · %36,8 · %40,2.

Zaman dilimi kırılımı (kapsam %20): 1s %38,5 · 2s %41,3 · 4s %44,0 · 1g %40,5.

Çeyrek bazında kararlılık (kapsam %20): 2025Q2 +12,8 · 2025Q3 +2,9 · 2025Q4 +3,6 ·
2026Q1 +10,5 · 2026Q2 +1,1 · **2026Q3 −3,6**. Son çeyrek negatif: istikrar tam değil.

**Okunuşu:** mevcut kalite puanı aynı kapsamda tabanın *altında* (%34,7 < %36,0),
koşul puanı tabanın belirgin üstünde (%40,2). Yani sıralama işi
"formasyon kalitesi" ile değil, "piyasa koşulu" ile yapılabiliyor.

**Formasyonun payı bu tabloda yok.** %40,2'nin tahminen %38'i zaten trend
filtresinden geliyor; formasyon +2 puan ekliyor.

---

## 8. Breadth etkileşimi hakkında uyarı

MTF≥4 içinde breadth kovaları tekdüze görünüyordu (%37,4 → %42,4), ancak
bölme testinde tutarsız: S doğrulamasında yüksek breadth %42,2 > düşük %38,7,
Z doğrulamasında tersi (%39,3 < %40,7). Ayrıca MTF<4 grubunda etki ters
(breadth Q1 %33,7 > Q4 %30,4). **Doğrulanmamış etkileşim** olarak işaretlendi,
puanlamaya katılmadı.

---

## 9. Sınırlar (dürüstçe)

- 18 ay, tek piyasa rejimi (güçlü yukarı eğilim), tek ülke, 177 sembol.
- 59 özellik × 2 bölme = çok sayıda test; çoklu test düzeltmesi uygulandı ama
  tamamen ortadan kaldırmaz.
- **Tüm veri artık kullanıldı.** Kalan tek temiz sınav canlı veridir: aşağıdaki
  puan ön kayıtla dondurulup 3 ay sonra ölçülmelidir.
- Haber/gündem verisi yok; takvim hipotezleri ölçülemedi.

---

## 10. Öneri (uygulamak için onay gerekiyor)

1. Kartta "formasyon kalitesi" sayısı **sıralama amacıyla kullanılmasın**;
   açıklayıcı etiket olarak kalabilir.
2. Sıralama/filtre gerekiyorsa **koşul puanı** kullanılsın: çoklu TF uyumu (0-4)
   + endeks uyumu. Ölçülen sonuç: kapsam %20'de %40,2 (taban %36,0).
3. Kırılım sonrası tek uyarı satırı eklenebilir: "seviyeye döndü" (oran
   %39 → %14). Yeni özellik sayılır; onay istiyor.
4. Kartta "%76'sı devam etti" iddiası kaldırılmalı (ölçülen %36).

---

## 11. Tekrar üretim

```
python scripts/puan_replay.py --sembol-sayisi 177 --cikti var/replay/gozlemler177.csv
python scripts/ozellik_deposu.py
python scripts/ozellik_avi.py
python scripts/kombinasyon_taramasi.py
python scripts/kontrol_mtf.py
python scripts/kontrol_eslesmis.py
python scripts/puan_kompozit.py --ozellikler "mtf_uyum:1,p_breadth:1,endeks_uyum:1" --kapsam 0.2
```

Hiçbiri üretim koduna, `bot_data/` dizinine veya Telegram'a dokunmaz.
