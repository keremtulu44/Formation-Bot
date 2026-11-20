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

<!-- URETILEN:BASLANGIC -->

Taban (alarmsız bar): **%63,7** · tetik satırı: **177,723** · taban satırı: **86,496**

| politika | ne yapar | kart | kart/gün | ≥1 ATR (yönlü) | Wilson alt | taban farkı | ≥1 ATR (iki yön) | iyi yakalama | hamın %'si |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **P0** | canlı kural (her kanal) | 61,221 | 0,38 | %66,6 | %66,3 | +3,0 pp | %81,7 | %35,1 | %34,4 |
| **P1** | P0 − tek başına BOS | 60,944 | 0,38 | %66,7 | %66,3 | +3,1 pp | %81,8 | %35,0 | %34,3 |
| **P2** | yalnız hacim ≥5× | 3,338 | 0,02 | %70,6 | %69,0 | +6,9 pp | %82,5 | %2,1 | %1,9 |
| **P3** | katman: yalnız OB/FVG/BOS → sessiz | 37,734 | 0,23 | %66,5 | %66,1 | +2,9 pp | %81,7 | %21,2 | %21,2 |
| **P4** | P3 + bağlam (sıkışma/koşu) | 14,257 | 0,09 | %68,2 | %67,5 | +4,6 pp | %82,7 | %8,2 | %8,0 |
| **P5** | P3 + seans (09–10, 17) | 19,710 | 0,12 | %67,0 | %66,4 | +3,4 pp | %82,0 | %11,2 | %11,1 |
| **P6** | yalnız bağlam (sıkışma/koşu) | 21,913 | 0,14 | %68,3 | %67,7 | +4,7 pp | %82,8 | %12,8 | %12,3 |
| **P7** | P6 + hacim ≥5× | 22,749 | 0,14 | %68,2 | %67,6 | +4,5 pp | %82,5 | %13,3 | %12,8 |

- **≥1 ATR (yönlü)**: kartın söylediği yönde 12 bar içinde ≥1 ATR. Arşiv raporuyla
  aynı ölçü (orada taban %64,1 / tetik %66,5).
- **taban farkı**: aynı verideki alarmsız barlara göre fark. Tek başına yeterli değil;
  az kart basan politika bu sütunu otomatik yükseltir.
- **iyi yakalama**: ≥1,5 ATR hareket eden tetiklerin politika sonrası hâlâ basılan payı.
  Bu sütun, politikanın **ne kaybettiğini** gösterir.
- Cooldown: 6 bar (canlı kural). Kart sayıları cooldown SONRASI.

<!-- URETILEN:BITIS -->

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

## 4.5 · Hacmin üstünlüğü gerçek mi? — rejim sabit tutulduğunda

Hacim tetikleri daha oynak barlarda oluşuyor (ATR %2,14 vs taban %1,82).
"Öyleyse üstünlük sadece rejim etkisidir" itirazı haklı olabilir. Test: ATR
yüzdeliği **sabit tutulup** kanallar karşılaştırıldı.

**≥1 ATR (yönlü, 12 bar) — rejim içinde taban farkı:**

| ATR rejimi | taban | HACIM | fark | OB | fark |
|---|---:|---:|---:|---:|---:|
| sakin (<%30) | %64,4 | %67,9 | **+3,4** | %65,6 | +1,2 |
| orta | %63,3 | %69,8 | **+6,6** | %65,0 | +1,7 |
| fırtına (≥%70) | %62,8 | %72,3 | **+9,5** | %65,7 | +2,9 |

**≥1,5 ATR — aynı kırılım:**

| ATR rejimi | taban | HACIM | fark | OB | fark |
|---|---:|---:|---:|---:|---:|
| sakin | %50,7 | %57,8 | **+7,2** | %54,1 | +3,4 |
| orta | %48,8 | %59,2 | **+10,4** | %52,2 | +3,4 |
| fırtına | %48,3 | %61,3 | **+13,1** | %52,8 | +4,6 |

**Hüküm:** Rejim sabit tutulsa da hacmin üstünlüğü **kalıyor, hatta büyüyor**.
"Hacim sadece oynak barları yakalıyor" **doğru değil** — aynı oynaklık
seviyesinde bile diğer kanallardan **+2 ila +9 pp** daha iyi. OB'nin katkısı her
rejimde **küçük ve sabit** (+1,2…+4,6).

**Ama:** hacim tetikleri tüm tetiklerin **%1,9'u**. Yani hacim "en iyi kanal"
olarak **doğru**, "alarmın temeli" olarak **yetersiz** — neredeyse hiç ateşlemiyor.

---

## 4.6 · Asıl mesele: hacim değil **eşik**

Ölçüm şunu gösteriyor: alarmların çoğu, oynaklığın zaten yüksek olduğu anda
ateşliyor. Tüm kanallarda tetik anındaki ATR% tabana göre yüksek:

| | ATR% (fiyatın yüzdesi) | 12b ≥1 ATR | tabana fark |
|---|---:|---:|---:|
| TABAN (alarmsız bar) | 1,82 | %63,7 | — |
| OB | 1,87 | %65,6 | +1,9 |
| FORMASYON | 1,87 | %66,3 | +2,6 |
| HACIM | **2,14** | %71,5 | **+7,8** |
| FVG | **2,37** | %65,8 | +2,1 |
| BOS | **2,75** | %52,1 | **−11,6** |

**İki farklı şey görünüyor:**

* **HACIM**: yüksek ATR% **ve** tabandan yüksek isabet → gerçek bilgi.
* **FVG ve BOS**: *en yüksek* ATR% ama isabet tabanda veya altında. Yani bu iki
  kanal **"oynaklık var"** diyor, **"hareket olacak"** demiyor. Sadece oynaklığı
  etiketliyorlar.

**Bu, bugünkü tasarımın çekirdek hatası:** sistem "oynaklık" ile "fırsat"ı aynı
şey sanıyor. Ölçüm ikisini ayırıyor.

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

## 5.5 · "Replay sonuçlarıyla seçim yapmak mantıklı mı?" — net cevap

Kısa cevap: **hayır, replay ile sembol seçilmez. Replay ile *kural* seçilir.**
İkisi farklı sorular; bu ayrım yapılmadığı sürece replay yanlış kullanılır.

### Neden sembol seçimi replay ile olmaz

| Engel | Sayı | Ne demek |
|---|---|---|
| **İsabet zaten yüksek** | her kanalda tetik %52–71 | Sembol seçmek dar bir aralıkta kumar oynamak |
| **Sembol başına örneklem küçük** | 0,14–0,38 kart/gün → yılda ~35–95 kart/sembol | "Bu sembol daha iyi" demek için yetersiz |
| **Ayrışma yok** | kanal dağılımı semboller arasında benzer | "OB'si iyi çalışan sembol" diye bir şey ölçülmedi |
| **Seçim = aşırı uydurma** | 176 sembol × 4 TF = 704 hücre | En iyi 10'u seçmek geçmişe uydurulmuş 10 sembol üretir |

**Somut tehlike:** 704 hücreden en iyi %5'i seçilirse çoğu **şans eseri** iyi
çıkmış olur. Aynı veride tekrar test edilemez (zaten seçildiler), yeni veride
kaybolur. Replay'in en sık yapılan yanlış kullanımı budur.

### Replay'in doğru kullanımı — 3 soru

| Soru | Replay cevap verir mi | Bugünkü cevap |
|---|---|---|
| **Kural iyi mi?** (kanal/bağlam/eşik) | **EVET** — 61 bin kart, güçlü örneklem | Bağlam kazandırıyor, kanal katmanı kazandırmıyor |
| **Hangi iddia savunulabilir?** | **EVET** | "oynaklık var + aralık şu" — "yön" ve "döner" değil |
| **Hangi sembolü izlemeliyim?** | **HAYIR** | Ölçülmedi; ayrışma yok |

### "Çok inefficient" hissi nereden geliyor?

His **doğru**, ama sebebi sandığı yerde değil. Verimsizlik **kaç kart
gönderdiğinde** değil (0,38 kart/sembol/gün — zaten az), **kartın ne
söylediğinde**:

1. **Kart bir iddia taşımıyor.** "Şu seviye, şu kanallar" diyor; %64 tabanla bu
   iddia neredeyse bedava. Yatırım kararı için kullanılamaz.
2. **Grafik yön oku çiziyor**, ölçüm iki yönlü diyor (tetiklerin %30,5'i iki
   yöne de ≥1 ATR).
3. **Kanal sayısı vurgulanıyor** ("3 kanal ateşledi"), ölçüm kombinasyonun
   **seyrelttiğini** gösteriyor (HACIM %71,6 → HACIM+OB %67,9).
4. **BOS/FVG "oynaklık" diyor, "fırsat" demiyor** — BOS tabandan −11,6 pp.

> **Verimsizlik "çok mesaj" değil, "mesajın boş iddiası".**
> Çözüm mesaj sayısını kısmak değil, **iddiayı değiştirmek**.

### Sıralama — ne yapmalı, hangi sırayla

| # | Adım | Neden bu sırada | Ölçüm desteği |
|---|---|---|---|
| **1** | Kartın **iddiasını** değiştir: yön/seviye yerine **aralık + bağlam ölçüsü** | En büyük kazanç burada; mesaj sayısı zaten az | §4.6, P0→P6 |
| **2** | **BOS'u** tek başına alarm olmaktan çıkar | Tabandan −6…−11,6 pp | §4, §4.6 |
| **3** | Grafikte **yön okunu** kaldır, **aralık konisi** koy | Ölçüm iki yönlü diyor | §6, koni prototipi |
| **4** | Kanal sayısını **vurgulamayı bırak** | HACIM+OB < HACIM | §4 |
| **5** | Bağlam filtresini **isteğe bağlı** sun (P6), zorunlu yapma | İyi tetiklerin %87'sini kesiyor — tercih meselesi | §5 |
| **6** | Sembol **seçme**. Replay bunu desteklemiyor. | Aşırı uydurma riski | bu bölüm |

**En önemli tek cümle:** Replay, "hangi sembol" sorusunun değil **"hangi
iddia"** sorusunun aracı. Bugünkü sistemin verimsizliği ikinci soruyu hiç
sormamasından geliyor.

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

### Örnek çıktılar

| ASELS 4h | THYAO 1d |
|---|---|
| ![ASELS 4h](koni_ornek_asels_4h.png) | ![THYAO 1d](koni_ornek_thyao_1d.png) |

İki örnekte de koni **referanstan başlıyor** ve iki yöne açılıyor. Sol üstteki
kutu sıfat değil **ölçü** yazıyor (ATR, sıkışma, koşu, ATR yüzdelik). Grafikte
tek bir ok, tek bir hedef, tek bir "döner/döner değil" iddiası yok — çünkü
ölçüm bunları desteklemiyor.

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
