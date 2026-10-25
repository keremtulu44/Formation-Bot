# Puanlama mimarisi — geometri kapı, devamlılık puanı belirleyici

**Tarih:** 2026-10-25
**Karar veren ölçüm:** `FAZLA_ANALIZI_2026-10-25.md` (kama +4,1 · üçgen −1,9 ·
kama & MTF4 +10,3 · mesafe aile içi −7,0 · kalite bilgi taşımıyor · retest
gelecek bilgisi)
**Durum:** öneri. Bu doküman hiçbir kod, eşik, kart veya Telegram davranışı
değiştirmez. Kart/sıralama değişikliği `/evet` ile ayrı adımda yapılır.

---

## 0. Karar, tek paragraf

Geometri **belirleyici olmaktan çıkıyor**. Uyarıların öne çıkma sırasını ve
kullanıcıya verilen "devamlılık kalitesi" bilgisini yeni üç maddeli puan
belirleyecek: **aile + aile × trend uyumu + giriş mesafesi**. Geometri
silinmiyor, ama işi değişiyor: **kaba taban**. Yani "bu şekil hiç formasyon
sayılmaz" çizgisini korumaya devam eder, ama o çizgiyi geçen hiçbir şekli
puanla, sıralamayla veya etiketle **elemez** ve kullanıcıya **hiç görünmez**.
Kullanıcı yalnız tek satır görür: `Devamlılık: iyi · 75/100`. Bu satır bir
filtre değil, bir bilgi cümlesidir; hiçbir mesajı susturmaz.

Ek olarak **hacmi artık geometri değil puan yönetir**: ölçüm, kalite eşiğinin
altında kalan kırılımların daha kötü olmadığını gösterdi (3.3), yani yüksek eşik
bir performans filtresi değil, bir hacim musluğuydu. Taban tek seviyeye (~70)
iner, musluğu puan tutar.

---

## 1. Üç katman, tek kapı

Sistemde üç ayrı iş var ve bugüne kadar ikisi aynı sayıya sıkıştırılmıştı.
Ayrım şu:

| katman | sorduğu soru | ne yapar | kullanıcı görür mü | bugün | sonra |
|---|---|---|---|---|---|
| **1. Dedektör + geometri tabanı** | "Bu bir formasyon mu, hiç var mı?" | Uyarının oluşup oluşmayacağını belirler | Hayır | Geometri eşiği | Aynı, eşik seviyesi test edilir |
| **2. Devamlılık puanı** | "Bu uyarı, aynı yerde rastgele girmekten ne kadar iyi?" | Sıralama, öncelik, hangi uyarı öne çıkacak | Dolaylı (sıralama) | Geometri (yanlış araç) | **Yeni puan** |
| **3. Kart cümlesi** | "Kullanıcı ne okusun?" | Tek satır bilgi | Evet | Kalite yüzdesi (%76) | `Devamlılık: iyi · 75/100` |

**İki kelimeyi ayıralım, karışmasın:**

* **Kapı** = mesajın var olup olmaması. Sistemde **tek kapı** var: dedektör +
  geometri tabanı. İkinci bir kapı **yok** ve olmayacak.
* **Belirleyici** = var olan mesajlar arasında hangisinin öne çıktığı.
  Belirleyici **yeni puan**.

Neden tek kapı: geçen turda "koşul kötüyse hiç konuşma" kuralı ölçüldü, **−0,7
puan** çıktı; yani elemek sonucu iyileştirmedi, kötüleştirdi. İkinci kapı
mesaj sayısını düşürür (senin endişen haklı) ve karşılığında hiçbir şey
kazandırmaz.

---

## 2. Yeni puan

### 2.1 Ham etkiler ve güvenilirlik küçültmesi

Her maddenin ölçülen etkisi, **doğrulanma gücüne göre sıfıra doğru**
küçültülür. Çok test edilmiş ve her bölmede aynı çıkmış madde tam ağırlık alır;
dar kapsamlı, geçmişte yanıltmış madde kısılır.

| madde | ham etki (puan) | doğrulanma | küçültme | puana giren |
|---|---|---|---|---|
| kama | +4,1 | 7/7 varyant · 6/6 bölme · 176 sembol · aynı hücrede +6,4 | 1,00 | **+4,1** |
| üçgen | −1,9 | aynı | 1,00 | **−1,9** |
| kama & MTF 4 (ek) | +6,2 | 7/7 varyant, ama kapsam %6,8 ve MTF geçen turda hayaletti | 0,60 | **+3,7** |
| mesafe ≤0,3 ATR | +2,0 | 2/2 aile, S/Z aynı yön, 7/7 varyant; **ama 50 sembollük taze dilimde −7,0 → −2,8'e zayıfladı, GA sıfırı içerdi** | 0,50 | **+1,0** |
| mesafe 0,3–1 ATR | +1,0 | aynı | 0,50 | **+0,5** |
| mesafe 1–2 ATR | 0 | referans | — | **0** |
| mesafe >2 ATR | −1,5 | aynı | 0,50 | **−0,75** |

Küçültme katsayıları **veriye bakmadan** yazıldı; tek dayanak yukarıdaki
doğrulama sütunu. `mesafe` 2026-10-25'te 0,85'ten 0,50'ye indirildi: taze
dilimde etki yarıdan fazla eridi. Ölçüldü ki bu indirim puanın gücünü
değiştirmiyor (en iyi %10 dilimde 0,85 ile 0,00 arası fark <1 puan) — yani
puanın getirisi mesafeden değil, aile ve aile×trend maddesinden geliyor.

Küçültme katsayıları **veriye bakmadan** yazıldı; tek dayanak yukarıdaki
doğrulama sütunu. (MTF'nin 0,60 alması, geçen turda MTF uyumunun rastgele
girişte birebir aynı çıkmasından geliyor — kapsamı dar, geçmişi lekeli.)

### 2.2 Formül

```
toplam = aile + etkileşim + mesafe            (puan, yukarıdaki tablo)
puan   = 50 + 5 × toplam                       (5 … 95 arası kırpılır)
```

* **50 = "rastgele girmekle aynı."** Puanın tanımı fazla olduğu için sıfır
  noktası 50'dir; 100 değil. Kimse 100 alamaz — ölçülmüş en iyi hücre +9,5,
  yani 95.
* **5 çarpanı** ölçeği 34–95 aralığına yayar. Daha büyük çarpan (10) farkları
  abartır, 60/95 arasını "uçurum" gibi gösterir.
* **Ondalık yok.** 72 ile 75 arasındaki fark gürültü; kartta tam sayı.

### 2.3 Bantlar

| puan | bant | kart cümlesi | arşivdeki pay | gerçekleşen fazla (arşiv) |
|---|---|---|---|---|
| 85–94 | yüksek | `Devamlılık: yüksek` | %7 | **+10,3** [+6,2, +13,1] |
| 65–84 | iyi | `Devamlılık: iyi` | %50 | **+3,3** [+1,9, +4,5] |
| 45–64 | normal | `Devamlılık: normal` | %9 | **−0,7** [−4,1, +1,6] |
| 5–44 | zayıf | `Devamlılık: zayıf` | %34 | **−2,2** [−4,1, −1,2] |

Son iki sütun **arşivde ölçülen** değerler (15.736 gözlem, `var/replay/devamlilik.md`).
Fazla, eşleştirilmiş rastgele tabana göre; taban rejime göre %30–41 arasında
oynadığı için sabit değil.

Tekdüzelik sağlanıyor: yüksek > iyi > normal > zayıf. "yüksek" bandı küçük
(%2, n=333) çünkü kama + MTF4 birlikte gerekiyor — bu bilinçli: en yüksek etiket
nadir olsun.

### 2.4 Örnekler (senin tablon, puana çevrilmiş)

| durum | toplam | puan | bant |
|---|---|---|---|
| kama + MTF4 + yakın giriş (≤0,3 ATR) | +8,8 | **94** | yüksek |
| kama + MTF4 + 0,3–1 ATR | +8,3 | **92** | yüksek |
| kama + MTF4 + uzak (>2 ATR) | +7,1 | **85** | yüksek |
| kama, MTF düşük, 0,3–1 | +4,6 | **73** | iyi |
| kama, MTF düşük, 1–2 | +4,1 | **71** | iyi |
| üçgen, 0,3–1 | −1,4 | **43** | zayıf |
| üçgen, 2 ATR ötesi | −2,7 | **37** | zayıf |

Dikkat: **iki tepe var, arası seyrek**. Puan dağılımı düzgün bir çan eğrisi
değil, kama/üçgen ayrımından doğuyor. "Her uyarı 0–100 arası güzel bir
spektrumda" beklentisi kurma.

---

## 3. Geometri: ne olacak, ne olmayacak

### 3.1 Bugün ne yapıyor

Geometri (kalite) şu anda iki işi birden yapıyor: dedektörün içinde **eşik**
(bu şekil formasyon sayılır mı) ve kartta **yüzde** (kalite %76). İkincisi
ölçümle çöktü: kartta %76 görünen sayı, ölçülen devam %36,1; kalite kovaları
arasında sonuç farkı 2 puandan az ve tekdüze değil.

### 3.2 Yeni rol: kaba taban

Üç kural:

1. **Tabanın altındaki şekil uyarıya dönüşmez.** Taban tek seviye (~70);
   bugünkü 80/78/75/70 merdiveni yerine geçer (gerekçe 3.3).
2. **Tabanı geçen şekil "geçersiz" sayılmaz.** Puan bir formasyonu
   geçersiz kılmaz; yalnız **öncelik** verir. Hacim sınırı konacaksa, bu sınır
   günlük bir **bütçedir** (en yüksek puanlı N olay gönderilir), formasyonun
   geçerliliği değil. Kuyrukta kalan olay silinmez, sonraki bütçeye taşınır.
3. **Geometri değeri kullanıcıya gösterilmez** ve sıralamaya girmez.

Böylece "çok kötü şekiller içeri girmesin" isteğin karşılanır, ama geometri
"hangi uyarı daha değerli" sorusunun cevabı olmaktan çıkar.

### 3.3 Tabanın seviyesi: ölçüldü, sonuç net

Kritik teknik ayrım: `ALERT_MIN_QUALITY` (1h 80 · 2h 78 · 4h 75 · 1d 70)
**motorun değil bildirim katmanının** eşiği (`main.py:2951`). Motor bütün
kırılımları üretiyor, replay de hepsini görüyor. Yani "eşiği düşürürsek ne
gelir" sorusu **yeniden oynatmadan**, arşivdeki 15.756 kırılımın üzerinden
cevaplanabiliyor (`scripts/esik_analizi.py`).

**Kalite kovası ve fazla (eşiğin altı dahil):**

| kalite | n | ham devam | fazla | %95 GA (sembol) |
|---|---|---|---|---|
| ≤65 | 144 | %32,0 | **−4,9** | [−12,7, +3,9] |
| 65–70 | 451 | %35,0 | −0,5 | [−6,6, +1,7] |
| 70–75 | 1.450 | %37,7 | +1,7 | [−1,8, +3,8] |
| 75–80 | 3.464 | %36,7 | +1,6 | [+0,5, +4,6] |
| 80–85 | 5.174 | %35,9 | +1,4 | [−1,5, +2,6] |
| 85+ | 5.073 | %35,2 | +2,0 | [−0,1, +3,7] |

**Eşik düşürme senaryoları:**

| senaryo | uyarı | artış | eklenen grubun fazlası | %95 GA |
|---|---|---|---|---|
| mevcut | 11.384 | — | — | — |
| −5 | 14.281 | +%25 | **+3,2** | [+1,6, +5,4] |
| −10 | 15.348 | +%35 | **+2,2** | [+0,9, +4,2] |
| −15 | 15.665 | +%38 | +1,9 | [+0,6, +3,8] |

**Hüküm:** eşiğin altında kalan kırılımlar **daha kötü değil, eşit ya da daha
iyi**. Bugünkü 80/78/75/70 merdiveni performansı korumuyor — **hacmi kısıyor**.
Kalite ancak iki uçta konuşuyor: 65 altı gerçekten kötü (−4,9), 90 üstü gerçekten
iyi (+4,9, n=563). Ortada 70–90 arası düz (+1,4…+1,7).

Bunun mimari sonucu şu: eşiği yüksek tutmanın tek nedeni **hacim kontrolüydü**,
çünkü sıralayıcı yoktu. Sıralayıcı artık puan olduğuna göre:

* **Geometri tek ve kaba bir tabana iner: ~70 (TF'den bağımsız).** Altı çöp.
* **Hacmi puan belirler.** Mesaj sayısı sabit tutulmak isteniyorsa taban
  düşürülürken puan eşiği yükseltilir; ikisi birbirinin yerine geçebilir.

Ölçülen hacim/getiri sınırı (taban + puan birlikte, bugünün hacmi = 100):

| taban | puan eşiği | hacim | fazla | %95 GA |
|---|---|---|---|---|
| bugün (80/78/75/70) | — | 100 | +1,5 | [+0,5, +2,7] |
| 70 | 75 | 40 | +6,2 | [+4,9, +8,6] |
| 70 | 55 | 76 | +4,2 | [+3,1, +6,0] |
| 70 | — | 133 | +1,7 | [+0,6, +2,8] |

Yani aynı hacimde bugünden belirgin şekilde daha iyi bir nokta var. **Uyarı:**
puan bu veride keşfedildiği için bu satırlar iyimser; asıl güvenilir olan
yukarıdaki iki tablo (puan kullanmadan, yalnız eşiği oynatarak elde edilen).
Onlar da aynı şeyi söylüyor: alt grup kayıp değil.

Bu yüzden taban 70'e indirilmesi **önerilir**, hacim kararı ayrı verilir:
*Hacim aynı kalsın* isteniyorsa taban 70 + puan ≥55; *daha çok uyarı* isteniyorsa
taban 70 + puan ≥45.

---

## 4. Kullanıcı ne görecek

### 4.1 Önerilen satır

```
Devamlılık: iyi · 75/100
```

Dört sözcük + sayı. Tek satır, 283 px sınırının çok altında, `parse_mode`
gerektirmiyor, düz metin.

### 4.2 Gerekçe satırı (isteğe bağlı, ikinci satır)

```
kama · trend uyumlu
üçgen · seviyeden uzak
```

En fazla **iki** parça: aile + puanı en çok oynatan tek neden. Üç parça 283 px
satır bütçesini aşıyor ve kart satırı bölünüyordu (2026-10-25 örnek görselde
görüldü, ikiye indirildi). Ölçülen genişlikler: 176–197 px / 283 px.

### 4.3 Yazmayacaklarımız

| yazım | neden değil |
|---|---|
| `Devam olasılığı: %89` | kalibre değil; 89 puanlı hücrenin ölçülen devamı %47 |
| `Kalite: 89` | eski kelime; geometriyle karışır |
| `Başarı oranı %89` | aynı hata, üstelik yanlış güven verir |
| `Kazanç potansiyeli` | yasaklı dil (onaylı sözlük: `hacim`, `olumsuz:`, `geçmiş davranıştır, kazanç değil`) |
| Puanı hiç göstermemek | kullanıcı neden bu uyarının öne çıktığını bilmez |

Puan satırı **bilgi**dir, garanti değil. Bu yüzden "olasılık" değil
"devamlılık" kelimesi: sonuç değil, eğilim anlatıyor.

---

## 5. Eski puan: kenara, silmeye

| | eski | yeni |
|---|---|---|
| adı | **şekil kalitesi** (iç metrik) | **devamlılık puanı** (dış bilgi) |
| ne ölçer | geometri temizliği | rastgele girişe göre fazla |
| nerede kullanılır | yalnız dedektör eşiği | sıralama + kart cümlesi |
| kullanıcı görür mü | hayır | evet |
| sonuçla ilişkisi | ölçülmedi (seçim etkisi) | +6,1 / +10,3 / −7,0 puan |

Şekil kalitesi hesaplanmaya devam eder, **kapıyı** besler, başka hiçbir yerde
okunmaz. İki ayrı isim, iki ayrı iş; aynı 0–100 ölçeğinde iki sayı olmadığı
için karışma ihtimali yok.

Kod tarafında geri dönüş tek bayrak: kart satırı ve sıralama eski davranışa
döner, `TELEGRAM_ALERT_STYLE=klasik` çıktısı byte-identical kalır.

---

## 6. Geçiş planı

### Adım 1 — gölge mod (kart değişmez)

Puan her olay için hesaplanır, **kartta görünmez**, yalnız loga yazılır:
olay kimliği, sembol, TF, yön, aile, MTF, mesafe, puan, bant. 24 bar sonra
sonuç otomatik etiketlenir (mevcut `etiketle` tanımı).

Çıktı: olay başına puan + gerçekleşen sonek. Hiçbir kullanıcı etkisi yok.

### Adım 2 — doğrulama (6 hafta)

Üç ölçüt, üçü de geçmeli:

1. **Tekdüzelik:** bant sırası ile gerçek devam oranı sırası aynı mı
   (yüksek > iyi > normal > zayıf).
2. **Getiri:** en iyi %20 dilimin fazlası **+2,0 puanın üstünde** mi.
3. **Kararlılık:** iki haftalık blokların **en az 2/3'ünde** aynı işaret.

Bir ölçüt düşerse puan ağırlıkları düşürülür (küçültme katsayıları yarıya),
kart satırı eklenmez. İki ölçüt düşerse yeni puan rafa kalkar, eski davranış
sürer.

### Adım 3 — kart ve sıralama (`/evet` gerekir)

Sıralama puanla, kart satırı 4.1'deki gibi. Geri alma: tek bayrak.

---

## 7. Sınırlar, açıkça

1. **Ağırlıklar aynı veride keşfedilip aynı veride sınandı.** Canlıda beklenen
   getiri, tabloda görünenin yarısı ile üçte ikisi arası. Sıralama güvenilir,
   aralıkların genişliği iyimser.
2. **Kapsam %7'lik etkileşim ilk bozulacak yer.** MTF geçen turda rastgele
   girişte birebir aynı çıkmıştı; bu yüzden 0,60 küçültme aldı. Canlıda ilk
   izlenecek madde bu.
3. **Kama üstünlüğü ortalamada, isabette değil.** Aynı hücrede kama üçgenden
   yalnız %35 oranında daha iyi; fark toplamdan geliyor. "Kama geldi, tutar"
   diye okunmamalı.
4. **Puan tabanı değiştirmiyor.** Taban rejime göre %30–41 arasında oynuyor
   (çeyrekler: %30,1–%41,0). Puan fazla üzerinden kurulu olduğu için mutlak
   devam oranı vaat etmiyor; sabit bir yüzde gösterilirse o günkü taban da
   eklenmeli — puan göstererek bu tuzaktan çıkıyoruz.
5. **2026Q4 verisi 10 gözlem.** Bu çeyrek hiçbir kararın dayanağı yapılmadı.
6. **Eşik ölçümünün sınırı:** "eşiği düşürünce gelenler daha iyi" sonucu
   *fazla* ölçüsüne dayanıyor; ham devam oranları neredeyse aynı (%37–38).
   Yani düşürülen eşik daha çok uyarı üretir, uyarı başına beklenti aynı kalır —
   "daha iyi sinyal" değil, "daha çok aynı kalitede sinyal". Hacim artışı kabul
   edilecekse doğru hamle; edilmeyecekse puan eşiği ile dengelenmeli.
7. **Ölçülmeyenler:** kama/üçgen farkının **nedeni** (dedektör geometrisi mi,
   gerçek piyasa davranışı mı), haber/gündem etkisi, kartta etiketin kullanıcı
   davranışına etkisi.

---

## 8. Sıradaki ölçümler (öncelik sırası)

1. ~~**Eşik seviyesi taraması**~~ — **yapıldı** (`var/replay/esik.md`,
   `scripts/esik_analizi.py`). Sonuç 3.3'te: taban ~70'e inebilir; bugünkü
   merdiven hacim musluğu.
2. **Gölge mod doğrulaması** (6.2) — puan canlıda da çalışıyor mu. Sıradaki
   tek zorunlu adım bu.
3. **Üçgenlerin negatifliği** — üç ailenin (simetrik/yükselen/alçalan) hepsi
   negatif. Üçgen tanımı çok gevşek mi, yoksa üçgen kırılımı gerçekten zayıf
   mı? Ayrıştırılırsa üçgen cezası yerine "hangi üçgen" cezası yazılabilir.
4. **TF bazlı ağırlık** — kama & MTF4 etkisi 2h +13,0 · 1h +11,0 · 4h +5,7 ·
   1d +2,4. 1d örnek az (n=70); yeterli örnek gelince ayrı ağırlık gerekebilir.

---

## 8a. Kod durumu (2026-10-25)

**Uygulandı (2026-10-25, ikinci adım).**

| dosya | ne | durum |
|---|---|---|
| `devamlilik.py` | saf hesap: `devamlilik_puani`, `bant`, `kart_satiri`, `gerekce` | **uygulandı** |
| `test_devamlilik.py` | 21 test: ölçek, kapsam dışı, monotonluk, piksel bütçesi, kart entegrasyonu, rollback | **21/21 geçti** |
| `scripts/devamlilik_dogrulama.py` | arşiv doğrulaması | `var/replay/devamlilik.md` |
| `scripts/devamlilik_ornek.py` | gerçek koddan örnek metin + görsel | `docs/gorseller/devamlilik_ornek_kartlar.png`, `var/replay/devamlilik_ornek.md` |
| `notifier.py` | kart + klasik + sıralama + kanal kapısı | **uygulandı** |
| `main.py` | `mtf_uyum` + `bant_mesafe_atr` üretimi, DM kapısı | **uygulandı** |
| `config.py` | `DEVLAMLILIK_AKTIF`, `PUBLIC_MIN_DEVLAMLILIK`, `DM_MIN_DEVLAMLILIK` | **uygulandı** |

Değişen noktalar:

* `notifier.py` sade kart — `· formasyon kalitesi 87/100` → `· Devamlılık: iyi · 75/100` + gerekçe satırı
* `notifier.py` künye — `▪ kalite 87/100 (formasyon)` → `▪ Devamlılık: …`
* `notifier.py` klasik stil — `Kalite: 87/100 · Çok güçlü` → `Devamlılık: …`
  (iki stil arasında sayı farkı kalmasın; eski metin bayrakla geri gelir)
* `notifier.py` Top-12 sıralaması — `confidence_score` → devamlılık puanı
* `notifier.py` public kapı — `PUBLIC_MIN_DEVLAMLILIK > 0` ise ek eleme
* `main.py` — `mtf_uyum` artık **yön** karşılaştırmalı; `bant_mesafe_atr` eklendi

**Üç bayrak, üçü de varsayılan olarak davranışı korur:**

| bayrak | varsayılan | etki |
|---|---|---|
| `DEVLAMLILIK_AKTIF` | `1` | `0` → eski kalite metni birebir geri gelir (kart + klasik) |
| `PUBLIC_MIN_DEVLAMLILIK` | `0` | `>0` → kanalda ek puan elemesi (55 → hacim %76) |
| `DM_MIN_DEVLAMLILIK` | `0` | `>0` → DM'de ek puan elemesi |

Hacim kararı bilinçli olarak **verilmedi**: varsayılan 0, yani mesaj sayısı
bugünküyle aynı. Ölçülen noktalar hazır (55 → hacim %76, fazla +4,2), tek
env değişikliğiyle açılır.

## 8b. Tekrar üretim

```bash
python scripts/puan_replay.py --sembol-sayisi 177   # arşiv (13 dk)
mv var/replay/gozlemler.csv var/replay/gozlemler177.csv
python scripts/ozellik_deposu.py                    # özellikler (16.417×147)
python scripts/taban_uret.py                        # 7 varyant tabanı
python scripts/esik_analizi.py                      # taban/hacim sınırı
```

Çıktı: `var/replay/esik.md` (tablo 3.3'ün kaynağı), `var/replay/fazla*.md`,
`var/replay/puan_besli.md`.

## 9. Tek sayfa özet

```
KAPI        dedektör + tek kaba taban (~70) → mesaj var mı?        (sadeleşiyor)
BELİRLEYİCİ aile + aile×MTF + mesafe       → hangi mesaj öne?     (yeni)
HACİM       puan eşiği                     → kaç mesaj?           (yeni)
BİLGİ       Devamlılık: iyi · 75/100       → kullanıcı ne okur?   (yeni)
GİZLİ       şekil kalitesi (0–100)         → yalnız tabanı besler (gösterilmez)
YASAK       retest değişkeni               → gelecek bilgisi
```

Puan = 50 + 5 × (aile + etkileşim + mesafe), 5–95 kırpık.
Geometri iki işten birine indi: çöpü kesen taban. Hacmi puan tutuyor.
Eşikler ve ağırlıklar bu dokümanla değişmiyor; değişiklik `/evet` ile.

---

## 10. 50 sembollük taze replay — puan gerçekten çalışıyor mu?

**Soru:** ağırlıklar 177 sembollük arşivde seçildi. Aynı veride ölçmek kendini
doğrulamak olur. Bu yüzden 50 sembollük **yeni bir replay** koşuldu ve puan o
dilimde sınandı.

**Kurulum:** `puan_replay.py --sembol-sayisi 50` (3,8 dk, 5.236 gözlem, hata 0)
→ `ozellik_deposu` → o 50 sembol için ayrı taban. Puan, kartın gerçekten
kullanacağı alanlarla hesaplandı; araştırma kolonlarıyla değil.

### 10.1 Sonuç: bantlar tekdüze, en iyi dilim belirgin

| sıralayıcı | dilim | fazla | **aşırı** (dilim − küme ort.) | %95 GA |
|---|---|---|---|---|
| devamlılık puanı · üretim alanlarıyla | %10 | +8,4 | **+6,4** | [+4,2, +12,2] |
| devamlılık puanı · üretim alanlarıyla | %20 | +6,4 | **+4,4** | [+3,6, +9,0] |
| devamlılık puanı · araştırma kolonlarıyla | %10 | +8,2 | **+6,2** | [+4,3, +12,1] |
| eski kalite | %10 | +5,4 | **+3,5** | [+1,3, +10,0] |
| eski kalite | %20 | +3,3 | +1,3 | [+0,0, +6,6] |
| rastgele | %10 | +2,0 | **0,0** | — |

Kümenin ortalama fazlası +2,0 puan. Rastgele bir dilim de bunu verir; bu yüzden
"aşırı" sütunu asıl ölçü. **Puan, rastgele seçime göre %10 dilimde +6,4, eski
kaliteye göre +2,9 puan daha iyi.**

| bant | n | ham devam | fazla |
|---|---|---|---|
| yüksek | 190 | %47,9 | **+14,1** |
| iyi | 2.186 | %35,9 | **+4,8** |
| normal | 1.711 | %34,7 | −0,7 |
| zayıf | 1.000 | %36,6 | **−2,1** |

Tekdüze ✅. Üretim alanlarıyla hesaplanan puan, araştırma kolonlarıyla
hesaplanandan **daha iyi** çıktı (aşırı +6,4 vs +6,2) — yani karta bağlarken
yapılan uyarlama puanı bozmamış.

### 10.2 Ama: puan bir olasılık değil, kuyruk aracı

| sıralayıcı | AUC (başarı) | ρ (fazla) |
|---|---|---|
| devamlılık puanı | **0,507** | +0,141 |
| eski kalite | 0,494 | +0,041 |
| MTF tek başına | 0,544 | −0,100 |
| mesafe tek başına | 0,486 | +0,045 |

AUC 0,507 demek: **tek tek olaylarda puan neredeyse yazı-tura**. Kazanç, olayların
%7'lik kuyruğunda toplanıyor (kama & MTF4), ortada sinyal yok. Bu yüzden puan
kartta "olasılık" gibi değil, **öncelik** olarak sunulmalı — nitekim öyle
sunuluyor ("Devamlılık: iyi · 73/100", "%73 devam" değil).

### 10.3 Kazanç nereden geliyor: iki madde, üçüncüsü zayıf

| kural | kapsam | fazla | aşırı |
|---|---|---|---|
| kama & MTF4 | 335 | **+11,7** | **+9,7** |
| kama | 2.950 | +4,4 | +2,4 |
| üçgen | 2.137 | −1,3 | −3,3 |
| MTF4 (her aile) | 1.722 | +1,5 | **−0,4** |
| ≤0,3 ATR | 990 | +2,5 | +0,6 |
| >2 ATR | 1.610 | +1,3 | −0,6 |

Üç bulgu:

1. **MTF tek başına sıfır** (aşırı −0,4), kama ile birleşince +9,7. Etkileşim
   gerçek; 177'lik arşivde ölçülen +6,2'lik ek katkı burada da doğrulandı.
2. **Aile maddesi ayakta**: kama +2,4, üçgen −3,3 (aşırı).
3. **Mesafe zayıfladı.** 177'de aile içi Q5−Q1 −7,0 iken burada −2,8 (kama) ve
   −4,4 (üçgen), ikisinin de GA'sı sıfırı içeriyor. Ayrıca kama & MTF4 içinde
   ≤1 ATR (+10,0, n=55) ile >2 ATR (+10,0, n=231) **aynı** çıktı — yani o
   kuyrukta mesafe hiçbir şey ayırmıyor.

Bu yüzden mesafe küçültmesi **0,85 → 0,50** indirildi. Duyarlılık ölçümü: en iyi
%10 dilimde 0,85 ile 0,00 arasındaki fark **1 puandan az** — yani puanın getirisi
mesafeden gelmiyor; katsayıyı düşürmek riski azaltıyor, getiriyi değiştirmiyor.

### 10.4 Aile içinde ne yapıyor

| küme | n | puan aralığı | en iyi %20 | en kötü %20 |
|---|---|---|---|---|
| kama | 2.950 | 64–95 | **+7,9** | +1,3 |
| üçgen | 2.137 | 34–49 | **+0,5** | **−3,2** |

Kama içinde puan 6,6 puanlık yayılma yaratıyor (asıl faydalı kısım bu). Üçgen
içinde yayılma 3,7 puan ve tamamı negatif: üçgenlerde puan "hangisi daha az
kötü"yü söylüyor, "hangisi iyi"yi değil.

### 10.5 Çeyrek ve zaman dilimi

| çeyrek | n | araştırma (%20) | üretim (%20) |
|---|---|---|---|
| 2025Q2 | 397 | +4,0 | +9,4 |
| 2025Q3 | 1.161 | +7,0 | +10,2 |
| 2025Q4 | 1.106 | +0,7 | +4,7 |
| 2026Q1 | 955 | +8,5 | +12,0 |
| 2026Q2 | 783 | +9,5 | +9,3 |
| 2026Q3 | 643 | +8,2 | +5,2 |

Altı çeyreğin altısı pozitif; en zayıfı 2025Q4 (+0,7), o çeyrekte taban da
yüksekti.

Zaman dilimi: 1h +2,4 · 2h +2,4 · **4h −0,4 · 1d −0,4**. 4h ve 1g'de puan
getirisi yok. Üretim `mtf_uyum`'u 2h ve 1g için hiç hesaplamıyor; 4h'te
hesaplayıp sonuç alamıyor. Yani puan 4h/1g'de yalnız aile ve mesafeyle çalışıyor
ve oradaki ağırlıklar doğrulanmadı.

### 10.6 Hüküm

**Çalışıyor, ama dar bir yerde.**

* bant sırasını doğru kuruyor (yüksek > iyi > normal > zayıf) — arşivde de taze
  dilimde de;
* en iyi %10'da rastgeleye göre +6,4, eski kaliteye göre +2,9 puan önde;
* altı çeyreğin altısında pozitif;
* tek tek olaylarda zayıf (AUC 0,51) — bu yüzden "olasılık" değil "öncelik".

Kazanç iki maddeden geliyor (aile, aile × trend uyumu); giriş mesafesi taze
dilimde eridi ve ağırlığı yarıya indirildi. 4h ve 1g'de getiri ölçülmedi.

**Tekrar üretim:**

```bash
python scripts/puan_replay.py --sembol-sayisi 50 --cikti var/replay/gozlemler50.csv
python scripts/ozellik_deposu.py --girdi var/replay/gozlemler50.csv --cikti var/replay/ozellikler50.csv
python scripts/taban_uret.py --semboller <50 sembol> --cikti var/replay/taban50
python scripts/puan_sinama.py     # var/replay/puan_sinama.md
```
