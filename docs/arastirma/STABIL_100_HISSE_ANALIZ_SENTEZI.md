# Stabil — 100 BIST Hissesi × 48 Davranış Sorusu (`STB-BHV-A01..H06`) Analitik Sentez

- **Tarih:** 2026-11-01
- **Kaynak matematik:** `domain_engines/05_stabil.txt` (`StabilTrendEngine` + `StabilSupportLifecycleEngine`, eşikler ve formüller değiştirilmeden)
- **Evren:** 100 BIST pay senedi (`AEFES` .. `KONTR`; endeks/spot metal/yabancı varlıklar hariç)
- **Veri hacmi:** `107.441` kapanmış `4H` nedensel checkpoint · `10.417` first-seen `SupportLifecycleEvent`
- **Çalışma süresi:** `188,84 sn` (tek geçişli `O(N)` tarihçe; tam önek paritesi testle doğrulanmış)
- **Ham çıktılar:**
  - `docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_YANITLARI.md`
  - `docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_TABLO.csv` (`642` kova×ufuk satırı)
  - `docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_SONUCLAR.json`
  - `docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_MANIFEST.json`

---

## 1. Karar Dağılımı Özeti (48 Soru)

| Sonuç Sınıfı | Soru Sayısı | Açıklama |
|---|---:|---|
| **Betimsel ayrım** | **19** | Kovalar arasında anlamlı getiri, MAE veya 24×4H yarış olasılığı farkı var |
| **Belirgin ayrım yok** | **17** | Sezgisel olarak farklı sanılan kovalar ampirik veride benzer dağılım üretiyor |
| **Ayrı doğrulama gerekli** | **10** | Dikey/yatay aday rejim eşlemesine (`B01–B06`, `F01`, `F03`, `F05`, `F06`) dayalı ölçümler (debug şerhiyle raporlandı) |
| **Örnek yetersiz** | **2** | Çoklu ardışık tamamlanmış tepki şartı nedeniyle daralan uç alt kümeler (`C05`, `C06`) |

> **Yönetişim notu:** Eski `S01–S32` otomatik karar kapısı uygulanmamıştır; bu bulgular canlı alarm filtresi veya al/sat skoru üretmez, kartta yalnız tek olgusal yapı satırı (`Stabil: destek üstünde / altında / destekte`) ve grafikte 2 renkli günlük destek stepline'ı kullanılır.

---

## 2. Sekiz Davranış Boyutundan Çıkan Ana Bulgular

### A. Fiyat Uzaklaşması ve Takip Mekaniği (`A01–A06`)
1. **2.0 ATR Eşiğinde Rejim Değişimi (`A01`, `n=65.955`):**
   - Fiyat destek üstünde **`1,0–2,0 ATR`** bandındayken 24×4H yarışında iki yol başa baştır: **`%33,5`** önce destek yukarı güncellenir (`SUPPORT_UP_FIRST`), **`%31,7`** önce fiyat eski desteğe döner (`PRICE_RETURN_FIRST`).
   - Mesafe **`2,0–3,5 ATR`** bandına çıktığında desteğin yukarı basamak yapma oranı **`%39,7`'ye yükselirken**, fiyatın eski desteğe geri dönme oranı **`%12,8`'e düşer** (`3,5+ ATR` üzerinde ise yalnız **`%3,1`**).
2. **Sindirilerek Çıkış vs Hızlı Sıçrama (`A02`, `n=27.136` — Kritik Bulgu):**
   - Aynı `1,5–3,0 ATR` destek mesafesine **yavaş/sindire sindire çıkanlarda** (`past12_ret < 1,2 ATR`) destek **`%42,7`** olasılıkla yukarı taşınır, aşağı basamak riski yalnız **`%1,5`** kalır (`16×4H eqSym: +0,064 ATR`).
   - Aynı mesafeye **hızlı sıçramayla çıkanlarda** (`past12_ret >= 1,2 ATR`) günlük 4-bar pivot dibi oluşmadığı için destek takibi **`%19,0`'a düşer**, desteğin aşağı kayma riski **`%16,8`'e (11 kat) çıkar** ve `16×4H` medyan korunan getiri **`-0,149 ATR`** olur.
3. **Destek Yaşı Uzadıkça Çökme Riski Artmıyor (`A04`, `n=65.955`):**
   - Taze destek (`0–5g`) evresinde fiyatın desteğe dönüş oranı `%23,1` (`8×4H med: -0,084 ATR`) iken, `16g+` korunmuş destek üstünde eski desteğe dönüş `%7,2`'ye iner ve ileri getiri pozitif ayrışır (`8×4H med: +0,055 ATR`, `16×4H eqSym: +0,205 ATR`).

---

### B. Yükseliş Sonrası Yataylaşma vs Uzun Yatay (`B01–B06` — Debug/Aday Eşleme Şerhiyle)
1. **Uzun Yatay Seviyelerin Sağlamlığı (`B01`, `n=43.682`):**
   - Aday eşleme altında **`LONG_HORIZONTAL` (`24g+` yatay tutunma)** en dengeli pozitif kovadır: `8×4H med: +0,100 ATR` (`ort: +0,179`, `eqSym: +0,243 ATR`), `+1 ATR` ilk vuruş **`%40,0`** vs `-1 ATR` ilk vuruş **`%26,5`**, üstelik hem erken (`+0,167`) hem geç (`+0,031`) arşiv yarısında pozitiftir.
   - **`NEWLY_FLATTENED_AFTER_RISE` (`9–23g`)** ise nötr/sürtünmeli bölgedir (`8×4H med: 0,000 ATR`, aşağı basamak riski `%6,2`).
2. **Önceki Yükselişin Süresinden Çok Şiddeti Bozulma Yaratıyor (`B02`, `B03`):**
   - Önceki yükselişin uzun sürmesi (`>=20g`, `B02`) MAE'yi ılımlı artırırken (`0,585 → 0,638 ATR`), **önceki yükselişin aşırı şiddetli olması (`>=3,0 ATR`, `B03`)** eşit-sembol ortalamasını sert biçimde negatife çeker (`8×4H eqSym: +0,044 → -0,159 ATR`, `16×4H eqSym: +0,091 → -0,363 ATR`). Birkaç uç hisse ham ortalamayı (`+0,077`) pozitif gösterse de tipik hissede sert ralli sonrası ilk yataylaşma zayıftır.
3. **Pivot Onay Gecikmesi vs Gerçek Sakinleşme (`B06`):**
   - İlk `1–4g` doğal pivot onay penceresi negatif beklentilidir (`8×4H med: -0,117 ATR`); `5–12g` arasında fiyat gerçekten sakinleşmişse (`|past12_ret| <= 0,8 ATR`) MAE `0,574 ATR`'ye düşer ve `16×4H eqSym +0,154 ATR` üretir.

---

### C. Temas ve Tepki Dizileri (`C01–C06`)
1. **İkinci Bağımsız Temas Güçlü, Üçüncü ve Sonrası Kırılgan (`C02`, `n=1.976`):**
   - **1. temas (`n=1.773`):** Sürtünmeli ve hafif negatif (`8×4H med: -0,066 ATR`, `pos: %44,7`).
   - **2. bağımsız temas (`n=137`, en az `0,35 ATR` tepki sonrası ikinci test):** Belirgin pozitif ayrım üretir (`8×4H med: +0,155 ATR`, `ort: +0,256`, `eqSym: +0,166`; `16×4H med: +0,316 ATR`, `pos: %56,6`).
   - **3+ temas (`n=33`):** Belirgin bozulma (`8×4H med: -0,376 ATR`, `16×4H med: -0,674 ATR`, `-1 ATR` kırılma `%48,5`). Çok kez test edilen destek güçlenmez, aşınır.
2. **Başarısız/Cılız Tepki Birikimi (`C04`):**
   - Önceki temastan `<0,75 ATR` cılız tepki verip geri dönenlerde `8×4H medyan -0,342 ATR` ve `16×4H` `-1 ATR` kırılma oranı **`%60,0`** olur (`temiz temaslarda %40,7`).

---

### D & E. Kırılma Derinliği ve Sabit Desteğin Geri Alınması (`D01–D06`, `E01–E06`)
Açık bırakılan *"küçük kırılma geri alımı ile derin kırılma geri alımı farklı mı?"* sorusu iki katmanda netleşmiştir:
1. **Kırılma Altındayken Geri Alma Olasılığı Çok Keskin Ayrışıyor (`D01` & `D04`, `n=21.892`):**
   - **Küçük kırılma (`0–0,5 ATR`):** 24×4H içinde sabit desteği geri alma oranı **`%65,6`** (`destek aşağı inme: %12,8`).
   - **Orta kırılma (`0,5–1,2 ATR`):** Geri alma oranı **`%51,0`** (`destek aşağı inme: %20,8`).
   - **Derin kırılma (`1,2+ ATR`):** Geri alma oranı **`%16,0`'a düşer**; `%55,3` olasılıkla destek aşağı taşınır.
   - **Native `0,35 ATR` Floor Sınırı (`D04`):** Yalnız ana destek altında kalıp `support_floor` üstünde tutunanlarda geri alım **`%65,2`** iken, `floor` altına kapananlarda geri alım **`%24,1`'e düşer**.
2. **Geri Alım Gerçekleştikten SONRA Kalan Medyan Tepki Eşit, Kuyruk Oynaklığı Farklı (`D02`, `D06`, `E05`, `n=1.150`):**
   - Sabit destek geri alındıktan sonraki **8×4H medyan korunan getiri üç derinlik grubunda da `0,000 ATR`'dir** (`pos: %48,7 / %48,0 / %49,8`). Derin kırılmadan dönmek tek başına medyan kazancı büyütmez (`belirgin ayrım yok`).
   - Ancak derin kırılmadan geri dönebilen `%16`'lık azınlık daha yüksek volatilite taşır (`12×4H MFE: 1,047 vs 0,819 ATR`, `MAE: 0,828 vs 0,655 ATR`, `eqSym: +0,194 vs +0,100 ATR`).
   - **Güçlü Geri Alım Mumu Hareketi Tüketmiyor (`E05` & `D06`):** Gövdesi `>=0,5 günlük ATR` olan güçlü geri alım mumları (`n=395`), cılız geri alımlara (`n=746`) kıyasla sonraki `8×4H` pencerede hem daha yüksek MFE (`0,840 vs 0,643 ATR`) hem daha yüksek eşit-sembol getirisi (`+0,249 vs +0,015 ATR`) hem de daha yüksek `+1 ATR` ilk vuruş oranı (`%43,8 vs %30,0`) üretir.
   - **İlk Deneme Başarı Oranı ve Retest (`E01`, `E06`):** Alttan sabit desteğe uzanan denemelerin yalnız **`%22,8`'i** üstte 4H kapanışa dönüşür (`%77,2` fitil/red). Üstte kapanış geldikten sonra ayrıca yeniden test (`retest`) beklemek (`E06`) ek getiri sağlamaz (`8×4H eqSym +0,098 → +0,054 ATR`).

---

### F & G. Aşağı Takip, Yol Bağımlılığı ve 4H Alıcı/Hacim Kanıtı (`F01–G06`)
1. **"Destek Üstünde" Görünmenin Yol Bağımlılığı (`F02` & `G01`, `n=19.594`):**
   - Aynı `0–1,0 ATR` destek üstü konumda; **fiyat yükselerek eski desteği geri alanlar** (`8×4H eqSym: +0,106 ATR`, `16×4H eqSym: +0,119 ATR`) ile **yukarıdan düşerek desteğe yaklaşanlar** (`8×4H eqSym: -0,017 ATR`) ve **destek aşağı taşındığı için pasif olarak üstte kalanlar** (`F02`, `16×4H eqSym: -0,035 ATR`) birbirinden ayrışır. Statik konum tek başına yolu temsil etmez.
2. **Aday Dikey/Yatay Eşleme Uyarısının Doğrulanması (`F01`):**
   - Saf yaş tabanlı aday eşlemede `STEPPING_DOWN` yalnızca yeni alt basamak teyit/ihlal anındaki aşırı satım sıçramalarını yakaladığı için kısa vadede tepki (`8×4H med +0,024`) gösterir ama `%29,7` oranında destek tekrar aşağı kırılır. Bu durum, dikey/yatay ayrımının debug şerhiyle tutulup otomatik kurala bağlanmamasının doğruluğunu teyit eder.
3. **4H Alıcı + Hacim Kanıtı En Temiz Tamamlayıcıdır (`G06`, `n=4.037`):**
   - Destek teması ve geri alım anlarında native **`H4 bull_displacement + volume_pass` var ise (`n=542`)**, kanıt olmayanlara (`n=3.399`) kıyasla `8×4H` medyan **`-0,077 → +0,058 ATR`**, eşit-sembol ortalaması **`-0,018 → +0,238 ATR`**, `+1 ATR / -1 ATR` ilk vuruş oranı ise **`%28,9 / %27,8` → `%42,1 / %24,0`** düzeyine taşınır.

---

### H. Kontrol Grupları, Endeks Rejimi ve Sağlamlık (`H01–H06`)
1. **Koşulsuz Destek Teması Basit 20g Dipten Üstün Değildir (`H01`, `H02`):**
   - Yalın Stabil destek teması (`8×4H med: -0,046`, `eqSym: +0,014 ATR`) ile basit `20` günlük dip kontrol grubu (`med: -0,059`, `eqSym: +0,021 ATR`) arasında koşulsuz kullanımda anlamlı fark yoktur. Stabil'in analitik değeri tekil çizgiye körlemesine emir bağlamakta değil; **24g+ yatay tutunma (`B01`), 2. bağımsız temas (`C02`), `0,35 ATR` floor toleransı (`D04`), güçlü geri alım mumu (`E05`) ve 4H hacimli alıcı kanıtı (`G06`)** ayrımındadır.
2. **Endeks Rejimi Etkisi (`H03`):**
   - `XU100 < EMA34` (endeks düzeltme/iskonto rejimindeyken) kendi günlük desteğini tutan/geri alan hisseler (`8×4H eqSym: +0,113 ATR`, `16×4H: +0,198 ATR`), `XU100 > EMA34` uzamış endeks rejimindeki temaslardan (`8×4H eqSym: -0,092 ATR`) çok daha güçlü performans göstermiştir (göreli güç + endeks ortalamaya dönüş etkisi).
3. **Yoğunlaşma ve Dönem Kararlılığı (`H04`, `H06`):**
   - Hiçbir ana kovada tekil hisse sürüklemesi yoktur (`top1` payı `%1,2 – %3,9`).
   - BIST'te yukarı uç hareketler ortalamayı medyandan yukarı çektiği için (`H04` destek üstü tüm evren `8×4H ort: +0,041` vs `med: -0,037 ATR`), değerlendirmelerde medyan + eşit-sembol ortalaması + erken/geç yarı tutarlılığı esas alınmıştır.
