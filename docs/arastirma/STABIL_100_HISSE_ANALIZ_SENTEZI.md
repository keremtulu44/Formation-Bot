# Stabil Çizgisi — 100 Hisselik Geçmiş Taramasından Çıkan Düz Türkçe Bulgular

- **Kapsam:** 100 BIST hissesi (`AEFES` – `KONTR`), 107.441 adet kapanmış 4 saatlik mum noktası, 10.417 adet destek olayı.
- **Yöntem:** Geleceği görmeyen (nedensel) tek geçişli tarama; motorun orijinal matematiğine (`domain_engines/05_stabil.txt`) hiç dokunulmadı.
- **Detaylı ham tablolar:** `docs/arastirma/stabil_100_sonuclar/` klasöründe (`STABIL_DAVRANIS_48_YANITLARI.md` ve `.csv/.json`).

---

## 1. En Temel Gerçek: Çizgi Tek Başına "Değdi Al" Çizgisi Değil

Hiçbir şeye bakmadan, sadece "fiyat Stabil desteğine değdi" diye işlem yapıldığında sıradan bir 20 günlük dip çizgisinden anlamlı bir üstünlüğü **çıkmıyor** (`H01`, `H02`).

Stabil'i değerli yapan şey tek başına çizginin kendisi değil; **çizginin o anki davranışı (düz mü, iniyor mu, sabit mi kaldı) + kaçıncı kez test edildiği + fiyatın çizgiyle buluştuğu mumun gücü.**

---

## 2. Yükseliş Tarafında Doğrulananlar

1. **Sindire sindire yükseliş vs dik fırlama (`A02`):**
   - Hisse sindire sindire yükseldiğinde çizgi arkadan merdiven gibi yukarı taşınıyor (**%42,7** oranında yeni yukarı basamak kuruyor; aşağı kırılma sadece **%1,5**).
   - Hisse tek bacakta dik fırladığında arada günlük dip bırakmadığı için çizgi aşağıda uzakta kalıyor; yukarı takip **%19,0**'a düşerken desteğin aşağı kayma riski **%16,8**'e (11 katına) çıkıyor.
2. **Ne zaman çizgi takip eder, ne zaman fiyat geri döner? (`A01`):**
   - Fiyat çizgiden **1–2 ATR** uzaktayken iki ihtimal başa baş (%33,5 çizgi yukarı çıkar, %31,7 fiyat çizgiye döner).
   - Mesafe **2 ATR'yi geçtiğinde** hissenin eski desteğe dönme ihtimali sert biçimde azalıyor (%12,8 ve altına iniyor), çizginin arkadan yukarı basamak yapması ağır basıyor (%39+).
3. **Uzun düz kalış sağlam, sert çıkış sonrası ilk düzleşme riskli (`A04`, `B01`, `B03`):**
   - Çizgi **uzun süredir (3–4 hafta ve üzeri) düz** gidiyorsa kolay kırılmıyor; bütün kovalar içinde en istikrarlı artı beklenti burada (`B01`: +1 ATR vurma oranı %40, -1 ATR vurma oranı %26,5).
   - Buna karşılık **çok sert/dik bir yükselişin hemen ardından ilk kez düzleşen** seviyelerde tipik hisse yoruluyor ve geri verme riski belirginleşiyor (`B03`: eşit-sembol ortalaması 16×4H'te `-0,36 ATR`'ye düşüyor).

---

## 3. Temas Sayısı: İkinci Geliş En İyisi, Üç ve Sonrası Tehlikeli (`C01`, `C02`, `C04`)

- **Hiç değmeden üstte giden trend (`C01`)**, çizgiye ilk kez geri çekilenden daha güçlü.
- **1. temas:** Kararsız ve sürtünmeli (hafif eksi/nötr).
- **2. bağımsız temas (ikili dip gibi ikinci yoklama):** Açık ara en temiz tepkiyi veren yer (`8×4H` medyan `+0,16 ATR`, `16×4H` medyan `+0,32 ATR`).
- **3. ve 4. temas:** Destek güçlenmiyor, tam tersine **yorulup kırılıyor** (`16×4H` medyan `-0,67 ATR`, aşağı kırılma %48,5).
- Hele bir önceki temasta cılız bir tepki verip hemen geri döndüyse (`C04`), bir sonraki gelişte aşağı kırılma oranı **%60**'a çıkıyor.

---

## 4. Düşüş ve Kırılma Tarafında Doğrulananlar

Senin düşüş için tarif ettiğin dört kuralın dördü de veride karşılık buldu:

1. **Kırılınca çizgi sabit kalırsa geri alım izlenir (`D01`, `D04`, `E01`):**
   - Sabit çizgiye alttan yapılan denemelerin **%77,2'si üstte kapatamıyor**, fitil/red olarak kalıyor (`E01`).
   - Fiyat çizginin az altına sarktıysa (`0–0,5 ATR` veya motorun `0,35 ATR` tolerans sınırı üstü) **%65+** ihtimalle çizgiyi geri alabiliyor. Çok altına göçtüyse (`1,2+ ATR`) sadece **%16** geri alabiliyor, **%55** ihtimalle çizgi de pes edip aşağı iniyor.
2. **İniş (dikey/merdiven) bölümünün "altı boştur", yataylaşınca zemin tutar (`F01`):**
   - Aşağı iniş evresindeki sıçrama denemelerinde anlık tepkiler gelse bile **altı boş olduğu için %29,7 oranında destek tekrar aşağı çöküyor** ve sadece **%2,7** oranında yukarı yeni basamak kurabiliyor.
   - Çizgi **yataylaştığında** tekrar aşağı çökme oranı **%29,7'den %9,1'e düşüyor**, yukarı yeni destek basamağı kurma oranı **%2,7'den %32,7'ye (12 katına)** çıkıyor.
3. **Yataylaşma kendi başına teyittir; ekstra 3–6 gün beklemek faydasız (`F05`):**
   - Çizgi düzleştikten sonra "birkaç gün daha yeni dip yapmasın, öyle bakayım" demek hiçbir koruma sağlamadığı gibi getiriyi düşürüyor.
4. **Sırf çizgi aşağı kaydı diye "fiyat destek üstünde" görünmesi aldatıcıdır (`F02`, `G01`):**
   - Fiyat yükselmediği halde çizginin aşağı inmesiyle pasif şekilde "destek üstünde" kalan hisseler ilk 1–2 mum nefes alsa da birkaç gün içinde tekrar eksiye dönüyor. Kalıcı olanlar eski çizgiyi fiyat gücüyle yukarı aşanlar.

---

## 5. En Önemli Püf Nokta: "Desteğin Altına İnip Güçlü Mumla Geri Çıkma" (`D02`, `E05`, `E06`, `G06`)

Veride en parlak çalışan sinyallerden biri tam olarak senin dikkat çektiğin **geri alım (üstüne çıkış) kalitesi**:

- **Sadece "üste attı" demek yetmiyor (`D02`):** Mum cılızsa, öncesinde az mı sarkmış çok mu sarkmış tek başına medyan sonucu değiştirmiyor (`0,00 ATR`).
- **Asıl farkı üstüne çıkan mumun gücü ve hacmi yaratıyor (`E05`, `G06`):**
  - Üste atan 4 saatlik mum **güçlü gövdeli (`>= 0,5 günlük ATR`)** ise devamında +1 ATR'ye ulaşma oranı **%30,0'dan %43,8'e** fırlıyor, eşit-sembol ortalaması **`+0,015`'ten `+0,249 ATR`'ye** çıkıyor (`E05`).
  - Destekte tutunma veya geri alım anında **4 saatlik hacimli alıcı mumu (`G06`)** varsa +1 ATR vurma oranı **%42,1**'e çıkarken -1 ATR riski **%24,0**'ta kalıyor (kanıt yoksa %28,9'a karşı %27,8 — yani yazı-tura).
- **Üste attıktan sonra "bir daha geri gelip test etsin (retest)" diye beklemek gerekmiyor (`E06`):** En güçlü gidenler geri dönüp test vermeden gidiyor; retest beklemek ortalama kazancı yarıya düşürüyor.

---

## 6. Bir Sonraki Adımda Derinleştirilecek Nokta: "Üstüne Çıkış Süreci"

Mevcut 48 soruda sarkma derinliği (`D01/D02`) ile çıkış mumunun gücü (`E05/G06`) ayrı ayrı ölçüldü. Senin işaret ettiğin asıl kurulum için şu birleşik sorular ayrıca mercek altına alınmaya çok uygun:

1. **"Sığ sarkma + güçlü mumla geri çıkış"** ile **"derin sarkma + güçlü mumla geri çıkış"** bir arada ayrıştırıldığında hangisi daha temiz ve kalıcı gidiyor? (Derin sarkmada arkada derin dip kaldığı için 3–4 gün sonra günlük çizginin aşağı kayma yan etkisi var; sığ sarkmada bu bozulma olmuyor.)
2. Altta **kaç mum kalıp** çıktığı (1–3 mumluk hızlı "ayı tuzağı / silkeleme" mi, yoksa 1–2 gün altta yatıp topladıktan sonra çıkış mı)?
3. Çizginin üstüne **tek mumda sert geçiş** mi daha verimli, yoksa çizgi altında sıkışıp ikinci denemede hacimli kopuş mu?
4. Kırılan çizginin öncesinde **uzun yatay bir destek** olması geri alım tepkisini katlıyor mu?
