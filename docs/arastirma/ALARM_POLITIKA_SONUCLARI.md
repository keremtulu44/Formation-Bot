# ALARM POLİTİKASI — "hangi kural daha iyi?" sorusunun sayıyla cevabı

> **Durum:** Ölçüm + çalışan prototipler · **Tarih:** 2026-11-19
> **Canlıya etkisi:** **YOK.** Canlı kural, eşik, kart biçimi, Telegram, Supabase
> değişmedi. Bu dosya yalnız **ölçüm** ve **araç** içerir.
> **Dayanak:** [`DOMAIN_ALARM_REPLAY.md`](DOMAIN_ALARM_REPLAY.md) · [`ALARM_YONU_2026-11-19.md`](ALARM_YONU_2026-11-19.md)
> **Veri:** 88 sembol × 4 TF = **352 seri**, 177.723 tetik + 86.496 taban satırı
> (yarı evren; tam evren 704 seri — kapsam uyarısı §7'de)

Bu dosya önceki turda önerdiğim **4 katmanlı yönü** "bence daha iyi olur"dan
çıkarıp **ölçülmüş** karşılaştırmaya çevirir. Araç:
[`research/alarm_politika.py`](../../research/alarm_politika.py) — 8 politikayı
aynı tetik satırları üzerinde çalıştırır.

---

## 1 · Neden ayrı bir ölçüm gerekti

`DOMAIN_ALARM_REPLAY.md` **bugünkü kuralı** ölçüyor: "gönderilen kart ne yapıyor".
Alternatif bir kuralı hiç çalıştırmıyor. Dolayısıyla "katmanlasak daha iyi olur
mu" sorusuna cevap veremez — o soru **karşılaştırma** ister.

`alarm_politika.py` üç şeyi yan yana koyar:

| Sütun | Ne ölçer | Neden gerekli |
|---|---|---|
| **kart/gün** | sıklık | alarm yorgunluğu |
| **≥1 ATR** | isabet | "kart çıktı, hareket oldu mu" |
| **iyi yakalama** | hatırlama | **politikanın ne kaybettiği** |

Üçüncü sütun olmadan tartışma eksik: her politika isabeti yükseltir, çünkü az
kart basar. Asıl soru **neyi kaybettiğidir**.

---

## 2 · Sonuç — 8 politika, aynı veri

Taban (alarmsız bar): **%63,7** · tetik satırı **177.723** · taban satırı **86.496**.
Kart sayıları canlı **6 bar cooldown** uygulandıktan sonra.

| politika | ne yapar | kart | kart/gün | ≥1 ATR | Wilson alt | taban farkı | iyi yakalama |
|---|---|---:|---:|---:|---:|---:|---:|
| **P0** | canlı kural (her kanal) | 61.221 | 1,17 | %66,6 | %66,3 | +3,0 pp | %35,1 |
| **P1** | P0 − tek başına BOS | 60.944 | 1,17 | %66,7 | %66,3 | +3,1 pp | %35,0 |
| **P2** | yalnız hacim ≥5× | 3.338 | 0,06 | %70,6 | %69,0 | **+6,9 pp** | **%2,1** ❌ |
| **P3** | katman: yalnız OB/FVG/BOS/CHoCH → sessiz | 37.734 | 0,72 | %66,5 | %66,1 | +2,9 pp | %21,2 |
| **P4** | P3 + bağlam (sıkışma/koşu) | 14.257 | 0,27 | **%68,2** | %67,5 | +4,6 pp | %8,2 |
| **P5** | P3 + seans (09–10, 17) | 19.710 | 0,38 | %67,0 | %66,4 | +3,4 pp | %11,2 |
| **P6** | yalnız bağlam (sıkışma/koşu) | 21.913 | 0,42 | **%68,3** | **%67,7** | **+4,7 pp** | %12,8 |
| **P7** | P6 + hacim ≥5× | 22.749 | 0,44 | %68,2 | %67,6 | +4,5 pp | %13,3 |

---

## 3 · Sonucun okunması — **P4/P6, önceki turdaki önerimin düzeltmesi**

Önceki turda "yalnız bağlam değil, kanal katmanı da gerekli" demiştim. Yarı
evren koşusu bunu **kısmen çürüttü ve düzeltti**:

### ✅ Doğrulanan
* **Kanal katmanı işe yaramıyor.** P3 (%66,5) ile P0 (%66,6) **istatistiksel olarak
  aynı** (Wilson alt sınırları %66,1 vs %66,3). OB/FVG tek tek basmayı kesmek
  isabeti artırmıyor — **kart sayısını** %38 düşürüyor, o kadar.
* **Bağlam katmanı isabeti GERÇEKTEN artırıyor.** P4 (%68,2) ve P6 (%68,3) —
  taban farkı **+4,6 / +4,7 pp**, Wilson alt sınırları P0'ın üstünde.
  Bu, önceki turdaki "bağlam işe yaramaz" sonucunu **düzeltir**; o sonuç
  20 sembollük gürültülü örnekten geliyordu.
* **Bağlamı kanal katmanıyla birleştirmek zarar veriyor:** P4 %68,2 —
  P6'nın (%68,3) altında. Yani **kanal eleme + bağlam ≠ daha iyi.** İkisi
  birlikte, sadece bağlamdan daha az kart ve aynı isabet üretiyor.
* **En verimli tek politika P6:** 21.913 kart (%35,8'ini basıyor),
  isabet %68,3 (+4,7 pp), iyi yakalama %12,8. P0'a göre kart **%64 az**,
  isabet **+1,7 pp yukarı**.

### ❌ Hâlâ çürüyen
* **"Az kart = yüksek isabet" tuzağı:** P2 (+6,9 pp) en yüksek fark ama
  **iyi yakalamanın %97,9'unu** kaybediyor. İsabet sütunu tek başına
  okunursa yanlış karar verilir; bu yüzden raporun 3. sütunu var.
* **Hacim eklemek marjinal:** P7 (%68,2) ≈ P6 (%68,3). Hacim kanalını
  "her zaman bas" kuralı, bağlam filtresinin üstüne **hiçbir şey eklemiyor.**

### 🔴 Tek cümlelik hüküm

> **Alarmı iyileştiren şey "hangi kanal" değil, "hangi bağlam".**
> Kanal seçimi (OB mı FVG mi hacim mi) 12 bar ölçüsünde en fazla **9 pp**
> ayrışıyor ve tek tek elemek isabet kazandırmıyor. Bağlam filtresi
> (6 bar koşu yukarı **veya** sıkışma genişliyor) ise kart sayısını **%64**
> azaltırken isabeti **+1,7 pp** yükseltiyor.

---

## 4 · Ufuk bulgusu — kanal ayrışması nerede büyüyor?

`DOMAIN_ALARM_REPLAY.md` yalnız **12 bar / 1 ATR** ölçüsünü raporluyor. Aynı
JSONL'de 3 ve 40 bar ufukları da var (ek koşu gerekmedi). Kanal × (ufuk, eşik):

| kanal | n | 3b 0,5 | 3b 1,0 | 3b 1,5 | **12b 1,0** | 12b 1,5 | 12b 2,0 | 40b 2,0 | 40b 3,0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **HACIM** | 3.332 | **66,3** | **46,3** | **30,4** | **71,5** | **60,4** | **50,1** | **69,5** | **55,4** |
| FORMASYON | 75.425 | 62,8 | 36,4 | 20,4 | 66,8 | 52,9 | 41,2 | 66,5 | 52,5 |
| FVG | 14.016 | 62,4 | 36,8 | 21,2 | 66,5 | 53,6 | 42,2 | 68,0 | 53,4 |
| OB | 81.933 | 61,4 | 40,1 | 24,4 | 66,0 | 53,6 | 42,4 | 66,5 | 52,3 |
| BOS | 2.644 | 57,1 | 34,9 | 21,2 | 58,0 | 46,2 | 37,6 | 56,7 | 46,8 |
| CHoCH | 373 | 60,8 | 37,8 | 21,4 | 61,9 | 42,8 | 33,9 | 54,2 | 38,3 |
| **TABAN** | 86.496 | 59,7 | 32,6 | 17,5 | 64,0 | 49,7 | 38,1 | 63,5 | 49,5 |

**Üç okuma:**

1. **Ayrışma ufukla büyümüyor** — HACIM ile OB arasındaki fark 12b'de 5,5 pp,
   40b'de 3,0 pp. **Kısa ufukta** daha büyük (3b 1,0: HACIM 46,3 vs OB 40,1 = 6,2 pp).
   Yani "trend devamı iddiası" (40 bar) kanalları **daha da eşitliyor.**
2. **BOS ve CHoCH tabana yakın veya altında** her ölçüde. BOS 12b'de %58,0
   (taban %64,0) — **tabandan 6 pp kötü.** Bu, `DOMAIN_ALARM_REPLAY.md`'deki
   −2,0 pp'den daha sert bir bulgu; 6 bar cooldown sonrası fark büyüyor.
3. **En büyük tek ayrıştırıcı hacim** ve fark her ufukta korunuyor (+4 ila +13 pp).
   Ama hacim tetiklerin yalnız **%1,9'u** — pratikte "nadir ama iyi".

**Hüküm:** Kanal seçimi 40 bar/3 ATR'de **20 pp**'yi aşmıyor (aşan tek durum
3b 1,0'de HACIM 46,3 vs CHoCH 37,8 = 8,5 pp). Önceki turda "aşarsa katmanlama
savunulabilir olur" demiştim — **aşmıyor**, dolayısıyla kanal katmanı
savunulamaz; **bağlam katmanı** savunulabilir.

---

## 5 · Pratik öneri — üç seçenek, sayılarıyla

Canlıya alınacaksa üç savunulabilir seçenek var; üçü de **kural değişikliği**
demektir ve **kullanıcı kararıdır**:

| seçenek | kart/gün | isabet | iyi yakalama | ne kaybedersin |
|---|---:|---:|---:|---|
| **A · Dokunma (P0)** | 1,17 | %66,6 | %35,1 | — (bugünkü hâl) |
| **B · Yalnız bağlam (P6)** | 0,42 | %68,3 | %12,8 | iyi tetiklerin %87'si |
| **C · Katman + bağlam (P4)** | 0,27 | %68,2 | %8,2 | iyi tetiklerin %92'si |

**B ile C arasındaki fark yok** (isabet aynı) — C sadece daha az konuşuyor.
Dolayısıyla seçim "ne kadar konuşsun" sorusuna indirgeniyor, "ne kadar isabetli
olsun" sorusuna değil.

**Ölçümün söylemediği:** hangi seçeneğin kullanıcı için **daha değerli**
olduğu. %35 hatırlama ile %13 hatırlama arasındaki tercih bir **ürün kararı**;
veri bu kararı vermiyor. Rapor bunu açıkça yazıyor.

---

## 6 · Prototipler (araç, kural değil)

| Dosya | Ne yapar | Ne değiştirmez |
|---|---|---|
| [`research/alarm_politika.py`](../../research/alarm_politika.py) | 8 politikayı aynı veride karşılaştırır + ufuk ızgarası | canlı kodu import etmez |
| [`research/alarm_karti.py`](../../research/alarm_karti.py) | katmanlı kart + günlük özet metni üretir | `bot/domain_alarm_service.py` değişmedi |
| [`research/koni_grafik.py`](../../research/koni_grafik.py) | ok yerine aralık konisi PNG üretir | `grafik/render.py` değişmedi |
| [`test_alarm_politika.py`](../../test_alarm_politika.py) | 8 test: cooldown, katman, Wilson, bayrak | — |

Koni örneği: `python -m research.koni_grafik --sembol ASELS --tf 4h --bar -90`

Grafikte **ok yok**; tetikten sonra 12 bar için medyan yukarı/aşağı ve %80
aralık var. Kart metninde "teyit/onay/güçlü sinyal" kelimeleri **yok**.

---

## 7 · Sınırlar — bu raporun söylemedikleri

1. **Kapsam:** 352 seri (yarı evren), 704 değil. Süre sınırı nedeniyle bölündü.
   Sıralama ve büyüklükler tam evrende değişebilir; yön değişmez sanılıyor ama
   **kanıtlanmadı**.
2. **Tek ölçü:** 12 bar / ≥1 ATR yönlü. "İyi" = ≥1,5 ATR. Başka bir tanım
   (ör. kapanışa göre) sıralamayı değiştirebilir.
3. **Politikalar kaba:** bağlam eşiği (koşu ≥1 ATR, sıkışma ≥1) ölçümden
   alındı, optimize edilmedi. Eşik taraması yapılmadı — yapılırsa P6'nın
   %68,3'ü yükselir **veya** aşırı-uydurma riski doğar.
4. **Cooldown 6 bar sabit.** Farklı cooldown (3/12/24) kart sayısını ve
   dolayısıyla isabeti değiştirir; denenmedi.
5. **Kullanıcı algısı ölçülmedi.** "Az ama iyi kart" mı "çok kart" mı tercih
   edilir — veri yok.
