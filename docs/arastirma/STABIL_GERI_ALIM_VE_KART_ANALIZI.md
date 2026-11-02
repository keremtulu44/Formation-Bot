# Stabil — "Desteğin Altına İnip Güçlü Mumla Üstüne Çıkma" ve Kart/Grafik Analizi

- **Kapsam:** 100 BIST hissesi (`AEFES` – `KONTR`), 107.441 kapanmış 4 saatlik mum, **1.150 gerçek sabit-destek geri alım olayı**.
- **Amaç:** Senin deneyiminden gelen *"desteğin altına bir miktar inip sonra güçlü mumla üstüne çıkınca güçlü artış oluyor"* gözlemini bütün ince detaylarıyla ölçmek ve kart/grafik kurallarını veriye dayandırmak.
- **Ham sonuç dosyası:** `docs/arastirma/stabil_100_sonuclar/STABIL_GERI_ALIM_16_SONUCLAR.json` (`research/stabil_reclaim_deep.py`).

---

## 1. Büyük Bulgu: Deneyimin Neden Tam İsabet Çıktı? (`RCL-01`)

Önceki genel taramada bütün geri alımlar tek torbaya girdiği için cılız mumlarla güçlü mumlar birbirini sıfırlıyordu. Sarkma boyu ile çıkış mumunun gücünü ayırdığımız anda tablo bıçak gibi ikiye bölündü:

| Sarkma Derinliği | Çıkış Mumu | Olay Sayısı | Ertesi Mum Üstte Kalma | 8×4H Medyan / Eşit-Hisse Ort. | 16×4H Medyan / Eşit-Hisse Ort. | +1 ATR / -1 ATR İlk Vuruş |
|---|---|---:|---:|---:|---:|---:|
| **Bir miktar sarkma (`0,5–1,2 ATR`)** | **Güçlü mum** | **198** | **%85,9** | **`+0,145` / `+0,380 ATR`** | **`+0,153` / `+0,413 ATR`** | **%40,6 / %22,3** |
| Bir miktar sarkma (`0,5–1,2 ATR`) | Cılız mum | 180 | %75,6 | `-0,216` / `-0,182 ATR` | `-0,339` / `-0,274 ATR` | %25,3 / %29,8 |
| Çok az sarkma (`0–0,5 ATR`) | Güçlü mum | 155 | **%91,6** | `0,000` / `+0,115 ATR` | `0,000` / `+0,231 ATR` | %39,0 / %26,0 |
| Çok derin çöküş (`1,2+ ATR`) | Güçlü mum | 149 | %82,6 | `-0,066` / `+0,184 ATR` | `+0,035` / `+0,220 ATR` | %42,3 / %28,2 |

**Buradan çıkan net gerçek:**
- Hisse çizginin altına **bir miktar sarkıp (`0,5–1,2 ATR`, yani klasik stopları patlatacak kadar silkeleyip)** ardından **güçlü gövdeli mumla** tekrar üstüne çıktığında, bütün tablodaki **en yüksek ve en istikrarlı kazancı (`+0,38 / +0,41 ATR`)** üretiyor. Üstelik hem iyi piyasada (`+0,10`) hem 2026'nın sert testere piyasasında (`+0,18`) artıda kalan **tek** kurulum bu.
- Aynı yerden **cılız mumla** çıkanlar ise tam bir tuzak (`-0,34 ATR`).
- **Çok derin çökenler (`1,2+ ATR`)** güçlü mumla dönse bile enerjisini aşağıdan yukarı gelene kadar harcadığı için ilk iki günde zorlanıyor (`medyan -0,07 ATR`).

---

## 2. Üstüne Çıkış Sürecinin 6 İnce Püf Noktası

1. **Mumun Üst Fitili Olmamalı (`RCL-04`):**
   - Çizginin üstüne atan mum **en tepesine yakın (`>= %70` bar boyu)** kapattığında ertesi mum üstte tutunma **%82,5**, beklenti net pozitif (`+0,19 ATR`).
   - Üstte uzun fitil bırakan (satış yiyip zar zor çizgi üstünde kapatan) geri alımlar **`-0,17 ATR`** ile başarısız oluyor.
2. **Kıl Payı Üstte Kapanışlara Dikkat (`RCL-06`):**
   - Çizginin kıl payı üstünde (`0–0,12 ATR`) kapatanların **üçte biri (%34,4)** hemen bir sonraki 4 saatlik mumda tekrar çizgi altına düşüyor.
   - Çizginin biraz üstüne net koparak (`>= 0,12 ATR`) kapatanlarda üstte kalma oranı **%88–96**'ya çıkıyor.
3. **Altta Ne Kadar Kaldığı (`RCL-03`):**
   - Altta **1–2 mum (aynı gün hızlı silkeleme)** veya **3–6 mum (1–1,5 gün silkeleme)** kalıp güçlü mumla dönenler en verimlisi (`16×4H medyan +0,22 ATR`, üstte kalma %85–93).
   - Altta 2–3 gün (`7–14 mum`) sürünenler yoruluyor (`-0,25 ATR`).
4. **Kırılan Çizgi Öncesinde Uzun Düzdüyse Etki Katlanıyor (`RCL-07`):**
   - Geri alınan çizgi öncesinde **16+ gündür düz giden oturmuş bir destekse** ve güçlü mumla geri alınırsa ortalama getiri **`+0,33 ATR`'ye** çıkıyor (+1 ATR vurma oranı %42,9'a karşı -1 ATR %21,4 — tam iki katı).
5. **Panik Şelalesinden Çok Yumuşak Süzülme Sonrası Patlama Daha Temiz (`RCL-09`):**
   - Tek mumda şelale gibi yıkılanlardan ziyade, çizgi altına sakin süzülüp sonra tek güçlü alıcı mumuyla yukarı patlayanlar çok daha istikrarlı (`16×4H medyan +0,15 vs -0,09 ATR`).
6. **Sahte Çıkış Filtresi (`RCL-10`):**
   - Bütün geri alımların %20'si hemen ertesi mumda tekrar çizgi altına düşüyor ve düşenler ağır satış yiyor (`-0,40 ATR`). Ancak **"makul sarkma + güçlü gövde + tepeye yakın kapanış + hacim"** filtresi uygulandığında ertesi mumda üstte kalma oranı **%90**'a ulaşıyor (`RCL-13`).

---

## 3. Grafikteki "Minik Geri Alım İşareti" İçin En Doğru Kural (`RCL-13`)

Grafiği kirletmemek için 5 adayı yarıştırdık:
- **Tüm geri alımlar:** Hisse başına 11,5 kez çıkıyor — çok sık ve yarısı cılız.
- **Seçilen Temiz Kural (`Makul sarkma <= 1,2 ATR` + `Güçlü gövdeli yeşil mum` + `Üst yarıda/tepeye yakın kapanış`):**
  - 1,5 yılda hisse başına sadece **2,7 – 4,0 kez** çıkıyor (yani 65–80 mumluk bir grafikte **en fazla 0 veya 1 kez** görünür, grafiği asla kalabalıklaştırmaz).
  - Ertesi mum üstte tutunma oranı **%88 – %90**.
  - `16×4H` eşit-hisse ortalaması **`+0,22` ile `+0,32 ATR`** arası (+1 ATR ilk vuruş ~%40–42, -1 ATR ~%23–24).

---

## 4. Telegram Kartı Etiketlerinin Gerçek Karne Tablosu (`RCL-14`, `RCL-15`)

Özellikle yukarı kırılım / atak mumlarında (`RCL-15`) tek satırlık kart ifadeleri resmi çok net ayırıyor:

- `Stabil: destek geri alındı (güçlü mum)` → **Güçlü silkeleme dönüşü** (`8×4H eqSym +0,24`, `16×4H +0,35 ATR`, +1A/-1A = %42 / %23)
- `Stabil: destek üstünde (uzun yatay)` → **En sağlam zemin** (`8×4H med +0,26`, `ort +0,35 ATR`, +1A/-1A = %49 / %25)
- `Stabil: destekte (2. temas)` → **En temiz destek tepkisi** (`8×4H med +0,16`, `16×4H med +0,30 ATR`)
- `Stabil: destekte (3+ temas · yorulma)` → **Kırılma tehlikesi** (`8×4H med -0,38`, `16×4H eqSym -0,47 ATR`)
- `Stabil: destek aşağı kaydı` → Fiyat çıkmadan çizgi aşağı indi (uzun vadede zayıf)
- `Stabil: destek altında (geri alım izleniyor)` → Sığ sarkma (`<= 0,5 ATR`, %65 geri alma potansiyeli var)
- `Stabil: destek altında` → Derin kırık bölge
