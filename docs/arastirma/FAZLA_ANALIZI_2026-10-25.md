# Fazla analizi — formasyonun kendi katkısı nereden geliyor?

**Tarih:** 2026-10-25
**Soru:** Kırılımın "iyi" olması formasyonun kendisinden mi, yoksa içinde bulunduğu
piyasa koşulundan mı? Hangi maddeler belirleyici ve puanlamada kullanılabilir?
**Veri:** 177 sembol × {1h,2h,4h,1d}, 15.756 etiketli kırılım, 7 etiket varyantı.
**Hüküm:** 59 özellik → 67 boyut testi → 21 aile içi testi sonunda **aile içinde
ayakta kalan tek özellik giriş mesafesi**; en büyük belirleyici ise ölçtüğümüz
hiçbir "puan" değil, **formasyonun kendi ailesi (kama / üçgen)**.

---

## 1. Yöntem ve bu turda düzeltilen üç hata

### 1.1 Hedef: fazla, mutlak başarı değil

Her kırılım aynı **sembol × zaman dilimi × ay × yön** hücresindeki rastgele giriş
tabanıyla eşleştirilir:

```
fazla = sonuç (0/1) − taban (aynı hücrede rastgele giriş)
```

Mutlak başarıya göre model kurmak yanıltıcı: tabanı düşük hücrelerdeki formasyonlar
"kötü" görünüyor. Ölçüm: mutlak başarı ile taban arasındaki korelasyon **+0,245**;
mutlak hedefle fit edilen model kama katsayısını **−0,027** veriyor, fazla ile fit
edilen **+0,046** (yani +4,6 puan). Bu yüzden bütün sonuçlar fazla üzerinden.

### 1.2 Ölçüm birimi sembol

Bir sembolün 40+ kırılımı bağımsız değil. Tüm güven aralıkları **sembol düzeyinde**
bootstrap ile (aynı sembolün kırılımları ortalanır, semboller yeniden örneklenir).
Gözlem düzeyinde bootstrap GA'yı yapay olarak 3–5 kat daraltıyordu.

### 1.3 Taban, etiketle aynı tanımı kullanmalı

`rastgele_aylik.csv` tek bir etiket tanımıyla (2 ATR / 1 ATR / 24 bar) üretilmişti.
Farklı etiketlerle karşılaştırma yapınca taban elma-armut oluyor. Bu turda
`scripts/taban_uret.py` **7 varyantın hepsi için ayrı taban** üretti
(`var/replay/taban_<leh>_<ters>_<ufuk>.csv`, ~24 bin hücre/varyant):

| varyant | taban başarı |
|---|---|
| 1/1/12 | %50,0 |
| 1/1/24 | %50,0 |
| 1,5/1/24 | %40,8 |
| 2/1/24 | %34,5 |
| 2/1,5/24 | %43,2 |
| 2/1/48 | %34,7 |
| 3/1/48 | %26,7 |

### 1.4 Arama merdiveni (çokluk kontrolü)

| aşama | test sayısı | geçen | ne yapıldı |
|---|---|---|---|
| kova taraması | 201 hücre | 24 | hücre − dışarısı; orta kovanın parlaması şans |
| boyut testi | 67 boyut | 16 | Q5−Q1 uçlar arası + tekdüzelik + 4 kısıt |
| **aile içi test** | **21 boyut** | **1** | kama ve üçgen ayrı ayrı; ikisinde de aynı işaret |

Geçme koşulu (dördü birlikte): |etki| ≥ 1,0 puan · sembol GA sıfırı dışlıyor ·
S (ayrık sembol) ve Z (uzak dönem) doğrulamada aynı işaret · 7 varyantın ≥6'sında
aynı işaret.

---

## 2. Belirleyici beş madde

### 2.1 Aile: kama +4,1 · üçgen −1,9 (fark 6,1 puan)

| grup | n | kapsam | fazla | %95 GA | önce (S) | sonra (Z) | ham başarı |
|---|---|---|---|---|---|---|---|
| Kama | 8.968 | %56,9 | **+4,1** | [+2,8, +5,4] | +3,8 | +4,9 | %35,8 |
| Üçgen | 6.768 | %43,0 | **−1,9** | [−3,5, −0,9] | −1,5 | −2,6 | %36,2 |

* Fark **+6,1 puan [GA +4,5, +7,8]**, 7 varyantın 7'sinde aynı yönde (+4,8…+6,1).
* S/Z/Y × keşif/doğrulama altı bölmenin altısında aynı yönde (kama +3,6…+6,1).
* 176 sembolde eşleşen çift: kama − üçgen **+6,2 [GA +4,5, +7,8]**; sembollerin
  %73'ünde kama pozitif, üçgende %40.
* **Aynı hücre içinde** (aynı sembol + TF + ay + yön, 1.477 hücre): **+6,4
  [GA +3,3, +9,6]**. Ancak hücrelerin yalnız %35'inde kama üstün → ortalama
  pozitif, medyan negatif: **beklenen değer artıyor, isabet oranı artmıyor.**
* Desen düzeyinde: Yükselen Kama +3,9, Alçalan Kama +3,1, Yükselen Üçgen −4,4,
  Alçalan Üçgen −5,6, Simetrik Üçgen −1,5.

Kama/üçgen ayrımı, motorun "kalite" puanının ölçmediği şeyi ölçüyor: iki aile
arasındaki fark, kalite puanının bütün kova farkından büyük.

### 2.2 Aile × trend uyumu: kama & MTF=4 → +10,3 (tek başına en iyi hücre)

| grup | n | kapsam | fazla | %95 GA | önce | sonra | ham başarı |
|---|---|---|---|---|---|---|---|
| kama & MTF 4 | 1.074 | %6,8 | **+10,3** | [+6,0, +13,0] | +9,2 | +13,3 | **%47,1** |
| kama & MTF 0–3 | 7.894 | %50,1 | +3,3 | [+1,9, +4,4] | +3,1 | +3,7 | %34,3 |
| üçgen & MTF 4 | 4.507 | %28,6 | **−1,4** | [−3,7, −0,4] | −1,0 | −2,2 | %38,1 |

* **Etkileşim**, toplam değil: MTF uyumu üçgende hiçbir şey eklemiyor (−1,4),
  kamada +7,0 puan ekliyor. 7 varyantın 7'sinde etkileşim +5,2…+7,0.
* kama & MTF 4 fazlası 7 varyantta +8,6…+10,3 — hiçbir varyantta sıfıra yaklaşmıyor.
* 170 sembolde %65 pozitif, **medyan +6,2** (yani kuyruk etkisi değil).
* TF kırılımı: 2h +13,0 · 1h +11,0 · 4h +5,7 · 1d +2,4 (1d n=70, zayıf).
* Çeyrek: +3,6 / +10,5 / +7,0 / +13,9 / +12,5 / +15,5 (2026Q4'te n=2).
* Alt hücre: kama & MTF 4 & mesafe ≤1 ATR → n=160, **+17,4 [GA +6,5, +22,5]**,
  ham başarı %53,1 (küçük örnek, temkinli).

### 2.3 Giriş mesafesi: aile içinde Q5−Q1 −7,0 puan

Seviyeye uzaklık (`bant_mesafe_atr` = giriş kapanışının banda ATR cinsinden
uzaklığı) **aile içinde** test edildiğinde ayakta kalan tek özellik:

| aile | Q1 (yakın) | Q5 (uzak) | Q5−Q1 | %95 GA |
|---|---|---|---|---|
| Kama | +5,8 | +0,8 | **−6,0** | [−9,7, −2,5] |
| Üçgen | −0,9 | −3,1 | **−8,0** | [−13,0, −3,2] |

* S doğrulama −4,7 · Z doğrulama −8,7 · 7/7 varyant aynı yönde.
* Eşik hücreleri: kama & ≤0,3 ATR **+6,1** [GA +4,2, +9,4] (n=1.689);
  kama & >2 ATR **+2,5** [−0,6, +3,5] (n=3.371); üçgen & >2 ATR −3,1.
* Yorum: kırılımın 2 ATR ötesinden girmek, formasyonun katkısının yarısını yiyor.
  Bu bir "kovalama cezası", formasyon kalitesiyle ilgisi yok.

### 2.4 Kalite puanı: belirleyici değil — bileşenleri birbirini götürüyor

| kalite kovası | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|
| fazla | +0,8 | +2,2 | +0,5 | +2,4 | +1,9 |

Tekdüze değil, kova farkı < 2 puan; boyut testini geçmiyor. Nedeni bileşenlerinde:

| bileşen | Q5−Q1 | %95 GA | kama içinde | üçgen içinde |
|---|---|---|---|---|
| olgunluk | +4,1 | [+1,0, +7,3] | +0,3 | +2,3 |
| daralma | −4,0 | [−6,6, −1,1] | −0,5 | +1,0 |

İki bileşen birbiriyle **−0,76** korelasyonlu ve zıt yönde katkı veriyor; ağırlıklı
bileşkede birbirini götürüyor. Üstelik ikisi de aile içinde eriyor: **aile
farkının vekili** (kamalar daha az daralmış, daha "olgun" görünüyor).

Sonuç: kalite puanına puanlama ağırlığı vermek, ölçülebilir hiçbir şey eklemiyor.

### 2.5 Retest: −19,9 puan ama gelecek bilgisi — kullanılamaz

| retest | n | fazla | %95 GA |
|---|---|---|---|
| yok | 10.625 | **+19,9** | [+18,4, +21,5] |
| var | 5.131 | **−19,9** | [−21,5, −18,4] |

7 varyantta 7/7, S/Z'de ±19…±21 — ölçtüğüm en güçlü tek değişken. Ama `retest_bar`
değerleri **1–13 bar, medyan +2**: olay girişten *sonra* oluşuyor. Yani bu değişken
geleceği görüyor; canlı puanlamada kullanılamaz.

İki sonucu var: (a) "retest bekle" kuralı canlıda kendini kandırma olur; (b) bu
değişkeni bir modele koymak diğer katsayıları bozuyor — mesafeyi ±14 puana
şişiriyor, çünkü ≤0,3 ATR grubunun %67'sinde retest zaten var.

---

## 3. Beş maddeden kurulan puanlama (yalnız öneri)

Ölçüt: doğrulanmış maddelerle basit kural, ağırlıklar **keşif kümesinde (ayrık
semboller)** fit, **uzak dönemde (Z, son %30)** test.

| kural | kapsam | Z başarı | Z taban | fazla |
|---|---|---|---|---|
| kama & MTF4 | %5 | %51,8 | %36,7 | **+15,0** |
| kama & MTF4 | %10 | %45,3 | %35,8 | +9,5 |
| kama & MTF4 | %20 | %40,4 | %34,9 | +5,5 |
| kama & MTF4 + mesafe | %10 | %42,6 | %34,5 | +8,1 |
| toplamsal (kama + mesafe + mtf + breadth) | %10 | %43,2 | %33,9 | +9,3 |
| yalnız koşul (mtf + breadth) | %10 | %40,8 | %39,6 | +1,2 |

Çeyrek kararlılığı (kama & MTF4 + mesafe, en iyi %10): +8,6 · +4,1 · +9,5 · +3,8 ·
+6,7 · +5,5 · −20,1 (2026Q4, n=10). **Altı çeyreğin altısı pozitif.**

Önerilen ağırlıklar (puanlama için, kod değişikliği değil):

```
aile       kama +4   ·  üçgen −2
etkileşim  kama & MTF4  ek +6
mesafe     ≤0,3 ATR +2 · 0,3–1 +1 · 1–2 0 · >2 −1,5
kalite     ağırlık 0 (bilgi yok)
retest     asla (gelecek bilgisi)
```

---

## 4. Aile içinde eriyenler (kötü haber listesi)

Kama/üçgen farkı çıkarıldıktan sonra **hiçbiri** ayakta kalmıyor:

| boyut | aile içi birleşik etki | neden elendi |
|---|---|---|
| olgunluk | +0,3 / +2,3 | aile vekili |
| daralma | −0,5 / +1,0 | aile vekili |
| yapı uyumu (−1) | +4,2 (ham) | kamaların %70'i zaten −1 |
| p_dispersion | +3,3 (ham) | iki ailede zıt işaret |
| gün (Pzt–Cum) | −3,0 | Z doğrulamada +0,2 |
| kore60 | −7,8 | S +1,2 / Z −2,7 (tutarsız) |
| d_ret60 | +3,9 | S −1,5 / Z +2,3 (tutarsız) |
| akran momentumu | +4,3 kama / +0,4 üçgen | sadece kamada |
| hacim (formasyon içi artış) | −2,2 kama / −1,9 üçgen | **artıyor = daha kötü**, S/Z oynak |
| MTF tek başına | — | rastgele girişte de aynı (geçen tur) |

---

## 5. Bu turda bulunan dört veri hatası

1. **`likidite_tl` yer tutucu.** `ozellik_deposu.py` içinde
   `out["likidite_tl"] = out.hacim_orani` — yani likidite kolonu hacim oranının
   kopyası. Bu dosyadan çıkarılan hiçbir likidite sonucu geçerli değil.
2. **Taban/etiket uyuşmazlığı.** Tek tabanla 7 varyant karşılaştırmak geçersizdi;
   `taban_uret.py` ile düzeltildi (varyant başına ~24 bin hücre).
3. **Mutlak başarıya göre model.** Tabanı düşük hücreleri cezalandırıyor
   (kama katsayısı −0,027 ↔ +0,046). Hedef fazla olmalı.
4. **Eşit puanlı sıralama.** İkili/az seviyeli puanlarda `argsort` kararlı
   sıralaması ilk satırları seçiyordu (en erken aylar); rastgele eşitlik kırma +
   20 çekim ortalaması eklendi.

---

## 6. Tekrar üretim

```bash
python scripts/taban_uret.py            # 7 varyant tabanı (~1 dk)
python scripts/fazla_analizi.py         # aile/TF/kalite/mesafe kırılımı
python scripts/fazla_tarama.py          # 201 hücre taraması
python scripts/fazla_egilim.py          # 67 boyut testi
python scripts/fazla_ic_egilim.py       # 21 aile içi testi
python scripts/fazla_model.py           # çok değişkenli ayrıştırma
python scripts/puan_besli.py            # kural + kapsam/başarı eğrisi
```

Çıktılar: `var/replay/fazla.md`, `fazla_tarama.md`, `fazla_egilim.md`,
`fazla_ic_egilim.md`, `fazla_model.md`, `puan_besli.md`, `taban_*.csv`.

---

## 7. Sınırlar

* Fazla, **aynı ay içindeki** rastgele girişlere göre; aylar arası rejim farkı
  tabana gömülüyor, ayrıca modellenmiyor.
* Aynı hücrede kama−üçgen farkı ortalamada +6,4 ama hücrelerin sadece %35'inde
  kama üstün → dağılım çarpık, işlem başına isabet değil, toplam beklenti artıyor.
* 2026Q4 yalnız 10 gözlem; çeyrek tablosunun son satırı anlamlı değil.
* Kama/üçgen farkının **nedeni** ölçülmedi (dedektör geometrisi mi, gerçek piyasa
  davranışı mı). Ayrımın canlıda bozulup bozulmadığı ayrı bir izleme konusu.
* Y blok karar için kullanılmadı; hiçbir üretim kodu, eşik, kart veya Telegram
  değişmedi.
