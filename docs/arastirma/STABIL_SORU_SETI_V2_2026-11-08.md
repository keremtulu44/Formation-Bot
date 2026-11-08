# Stabil — V2 soru seti: **ok yönü çıkar mı?** (onay taslağı)

**Tarih:** 2026-11-08 · **Durum:** ÖNERİ (rev. 2) · **Kod:** henüz yok
[Ana rehber](STABIL_REHBERI.md) · [Eski 48 soru sicili (A–H, legacy)](STABIL_DAVRANIS_SORULARI.md) ·
[Sistem incelemesi](STABIL_SISTEM_INCELEMESI_2026-11-08.md) · [Davranış modeli](STABIL_DAVRANIS_MODELI.md) ·
Makine okunur: [`stabil_soru_seti_v2/manifest.json`](stabil_soru_seti_v2/manifest.json)

**Bu setin amacı davranış betimlemek değil.** Her soru şu tek cümleye bağlanmak zorunda:
**"Bu koşulda ok yönü çıkar mı, çıkarsa hangi yönde?"** Cevap "yön çıkmıyor" ise bu da geçerli bir
sonuçtur ve o koşul ok üretmez. Bu yüzden her soru **yön hükmü** ile kapanır (§2.4), yoksa açık kalmaz.

---

## 0. Kullanıcının modeli — ölçülecek asıl iddia

> "Destek **dikeyken** fiyat desteğin altına düşerse ve tekrar üstüne çıkmaya çalışırsa, **tekrar altına
> iniyor**. Mantığı: destek dikeyken fiyatın **altı boş**. Ama fiyatın **altı dolduğunda**, altında
> sağlam bir destek olduğu için oradan destek alması daha muhtemel."

Bu iddia üç ayrı ölçülebilir parçaya ayrılıyor:

| Parça | Ölçüm |
|---|---|
| (P1) **Dikeylik** | Çizginin son N barda ATR cinsinden yükseliş hızı (eğim) |
| (P2) **Altı boş / dolu** | Fiyatın altında yatay bir "raf" (kümelenmiş kapanışlar) var mı, yoksa sadece dik çizgi mi |
| (P3) **Sonuç** | Altından üstüne çıkma denemesi 3 barda geri düşüyor mu; 16 barda ilk dokunma yönü |

**Tek bir uyarı:** "dikey" tanımı ölçümün kaderini belirliyor. Bugün kodda `vertical_support` diye bir
proxy var ama **eğim ölçmüyor**: `rejim ∈ {STEPPING_UP, STEPPING_DOWN}` veya "son 8 günde yukarı rebase"
veya "seviye önceki bardan farklı ve sabit değil". Yani pratikte **"yatay olmayan her destek dikey"**
sayılıyor. Ön ölçüm (15 sembol, 16.185 4s bar):

| Tanım | "Dikey" sayılan bar payı |
|---|---|
| Kod proxy'si (mevcut) | **%41,1** |
| Rejim = `STEPPING_UP` | %28,8 |
| Çizgi 20 barda ≥1 ATR yükseldi (eğim) | %0,1 |

Aynı olgu üç tanımda %0,1 ile %41 arasında. **Tanım seçilmeden hiçbir sonuç okunamaz** — bu yüzden §3'te
üç tanım yan yana koşulacak ve hangisinin ayrıştırdığı raporlanacak.

**Ön ipucu (karar DEĞİL):** "fiyat destek altında → 1–3 bar içinde üstüne çıkma denemesi" olaylarında
3 barda tekrar altına inme oranı: kod-proxy dikey **%21,8 (n=170)** · eğim≥1 ATR/20 bar **%32,0 (n=25)** ·
`STEPPING_UP` **%42,9 (n=14)** · yatay rejimler **%28,6 (n=14)**. Yön, iddiandaki gibi (dikey → daha çok
geri düşüş) ama **n çok küçük**; 15 sembol ve tek pencere ile hüküm verilemez. Ayrıca yatay rejimde de
%28,6 çıkması "dikey olmayan her şey iyi" demek olmadığını gösteriyor.

---

## 1. Kilitlenen kararlar

| Konu | Karar |
|---|---|
| Başarı ölçüsü | **İkisi birden**: ±1 ATR ilk dokunma (16 × 4s bar) **+** 16. barda kapanış işareti. Çelişen olay ayrı hücre. |
| Örneklem bölmesi | **Sembol hash'i**: `sha256(sembol) % 10 < 6` → keşif (~106), kalan doğrulama (~71). |
| Gruplama | **İki eksen**: native yaşam döngüsü × geometrik mesafe (ATR bandı). |
| Mum birimi | **Günlük ATR14** (girişte dondurulmuş). 4s ATR yalnız ek sütun. |
| Sicil | **Yeni V2 ID uzayı** (Y = yön sorusu, X = açıklayıcı katman, K = kontrol); A–H legacy dondu. |
| Dallanma | **3 seviye**: yön sonucu → mum anatomisi → domain → **artık hücresi** (zorunlu). |
| Min hücre | Ana kütle **n≥100**, alt hücre **n≥30**; altında yüzde yazılmaz: "yetersiz örneklem (n=..)". |

---

## 2. Ölçüm sözleşmesi (ölçümden önce sabit)

**2.1 Birim ve bantlar**
- Seviye: native günlük destek projeksiyonunun o bardaki değeri. `d = (kapanış − seviye) / ATR1d`.
- Mesafe: **temas** `|low−seviye| ≤ 0.35 ATR1d` (veya bar seviyeyi kesiyor) · **yakın** `0.35<|d|≤1.00` ·
  **uzak** `1.00<|d|≤2.00` · **çok uzak** `|d|>2.00`.
- Temas epizodu: ardışık temas barları tek temas; yeni temas için ≥2 bar ayrılma. (native `touch_count` kullanılmaz.)
- Mum (günlük ATR): gövde **yönsüz <0.20** / orta 0.20–0.50 / **büyük ≥0.50**; kapanış pozisyonu
  alt <0.35 / orta / üst >0.65; aralık dar <0.35 / normal / geniş >1.00.
- Hacim rvol: düşük <0.8 / normal 0.8–1.2 / yüksek ≥1.2.

**2.2 "Dikeylik" üç tanım (yan yana koşulur)**
| Kod | Tanım |
|---|---|
| **D1** | Mevcut kod proxy'si: `regime ∈ {STEPPING_UP, STEPPING_DOWN}` veya son 8 günde yukarı rebase veya seviye değişti ve sabit değil |
| **D2** | **Eğim**: `(seviye_t − seviye_{t−20}) / ATR1d ≥ 1.0` (20 × 4s bar ≈ 6–7 işlem günü) |
| **D3** | `regime == STEPPING_UP` (native etiket) |

Her yön sorusu D1/D2/D3 için **ayrı satırda** raporlanır. Hangi tanım ayrıştırıyorsa ok kuralı onun
üzerine kurulur; ayrıştırmıyorsa o tanım "yön bilgisi taşımıyor" diye kapatılır.

**2.3 "Altı boş / altı dolu" (raf) tanımı**
- **Raf var (altı dolu):** son 20 barda **en az 5 barın** kapanışı tek bir bantta (`±0.35 ATR1d`) kümelenmiş
  **ve** bu bant fiyatın altında (bantın üstü ≤ güncel kapanış).
- **Altı boş:** son 20 barda böyle bir küme yok; fiyatın altında yalnız dik çizgi var.
- Ön ölçüm: bu raf koşulu barların %0,6'sında sağlanıyor (102/16.185) — çok dar. Varyant olarak
  `en az 3 bar` ve `±0.50 ATR1d` de ölçülecek, hangisinin n≥100 hücre ürettiği raporda yazılacak.

**2.4 Yön hükmü (karar kuralı — ön kayıtlı)**
Bir koşul **ok adayı** sayılır ancak ve ancak:
1. **Keşif** kümesinde `UP_FIRST` oranı **≥ %60** (veya `DOWN_FIRST` ≥ %60) **ve** `n ≥ 100`,
2. **Doğrulama** kümesinde aynı yön **≥ %55**,
3. **Kontrol** (K1) aynı hücrede **≥10 puan** daha düşük sonuç veriyor.

Üçü sağlanmazsa hüküm: **"ok üretme"**. (Yön çıkmayan koşul, yanlış yönde ok üretmekten iyidir.)

**2.5 Diğer**
- Aynı barda iki eşik → `AMBIGUOUS` ayrı hücre. Sağ-sansür tabanda, yüzdeler geçerli n üzerinden.
- Ana ufuk **16 × 4s bar**; 1/4/8/10/12 kısa ufuk yalnız ek sütun.
- Sembol yoğunlaşması: bir hücrenin %20'sinden fazlası tek sembolden gelirse not düşülür.

---

## 3. YÖN SORULARI (ana set)

### Y1 — Dikey destek altından gelen geri alım tutmuyor mu? *(çekirdek)*
- **Kütle:** `d_{t−1} < 0` (fiyat destek altında) **ve** `d_t ≥ 0` (kapanış üstüne çıktı) = **geri alım denemesi**.
- **Bölünme:** (a) 3 barda kapanış tekrar `seviye` altında mı (tutmadı / tuttu); (b) 16 barda `first_1atr`.
- **Alt hücreler:** D1/D2/D3 dikeylik · raf var/yok · temas sayısı · geri alım barının gövdesi · hacim · artık.
- **Yön kuralı adayı:** dikey + raf yok → `▼`; dikey değil + raf var → `▲`. Ön kayıtlı eşik §2.4.
- **Cevaplanırsa:** ok yönü ilk kez *yapı* bilgisinden türetilir; bugünkü "dikeyde ▲ basma" kuralının
  (kör bastırma) yerine **karşıt yön** kuralı gelebilir.
- **Miras:** A01/A03/C01, model §dikey.

### Y2 — "Altı dolu" gerçekten destek veriyor mu?
- **Kütle:** fiyat desteğin **üstünde** (`0 < d ≤ 1.0`) **ve** raf var (2.3). Kontrol: raf yok, aynı mesafe.
- **Bölünme:** 16 barda `first_1atr` + `ret_atr_16` + "destekten sekme" (temas sonrası 8 barda `≥ +0.5 ATR`).
- **Alt hücreler:** raf yaşı (kaç bar) · temas sayısı · rejim · hacim · BOS · artık.
- **Yön kuralı adayı:** raf var + temas → `▲`; raf yok (altı boş) + temas → `▼` veya "ok yok".
- **Cevaplanırsa:** "raf" kavramı ok filtresi olarak kullanılabilir hale gelir.

### Y3 — Tutmayan geri alım sonrası düşüş sürüyor mu? (`▼` devam kuralı)
- **Kütle:** Y1'in **"tutmadı"** hücresi (geri alım denemesi 3 barda geri düştü).
- **Bölünme:** sonraki 16 barda `first_1atr` (aşağı ilk dokunma) + `mae_atr_16`.
- **Alt hücreler:** raf yok · dikeylik tanımı · düşüş barının gövdesi · hacim · BOS aşağı · artık.
- **Yön kuralı adayı:** "başarısız geri alım" → `▼` (bugün böyle bir ok **yok**; yalnız uyarı işareti var).
- **Cevaplanırsa:** mevcut mercan `▼`nin (dikey deneme uyarısı) bir *giriş* sinyaline dönüşüp dönmeyeceği belli olur.

### Y4 — Sabit desteğin altına inişte temizlik oranı yön veriyor mu?
- **Kütle:** kapanış `d < 0` (kırılma), ilk kırılma barı.
- **Bölünme:** 8 bar içinde kapanışla seviye üstüne dönüş (temizlik oranı) + 16 barda `first_1atr`.
- **Alt hücreler:** sarkma derinliği (`≤0.35` fitil / `0.35–1.0` / `1.0–2.0` / `>2.0` ATR1d) · sarkma süresi ·
  kırılma gövdesi · hacim · BOS aşağı · artık.
- **Yön kuralı adayı:** sığ sarkma + hızlı dönüş → `▲`; derin sarkma + dönüş yok → `▼`.
- **Cevaplanırsa:** `▲` reclaim eşiklerinin (ihlal ≤1,5 ATR) dayanağı sayıya bağlanır.

### Y5 — Hareketsiz fiyat + hacim patlaması yön veriyor mu?
- **Kütle:** `|d| > 1.00` üst üste ≥6 bar (hareketsiz) **ve** sonraki barda rvol ≥1.2.
- **Bölünme:** 16 barda `first_1atr` (patlama yönünde mi, tersine mi).
- **Alt hücreler:** bekleme süresi · rejim (`NEWLY_FLATTENED_AFTER_RISE` / `LONG_HORIZONTAL`) · gövde · BOS · artık.
- **Yön kuralı adayı:** hareketsizlik + hacim → patlama yönünde `▲`/`▼`.
- **Cevaplanırsa:** "sıkışma sonrası kırılma" tipi ok için ilk sayısal dayanak.

---

## 4. Açıklayıcı katmanlar (tek başına soru değil, Y1–Y5 hücrelerine uygulanır)

**X1 — Mum anatomisi katmanı.** Azınlık hücresinin ortak noktası: gövde bandı, kapanış pozisyonu, aralık,
fitil. Kullanıcı gözlemi: "kalamayanların çoğu küçük/yönsüz mum". Bu katman Y1 ve Y4'ün azınlığına uygulanır.
**Neden/eşlikçi ayrımı:** aynı `ATR1d` diliminde ve aynı mesafe bandında eşleştirilmiş karşılaştırma zorunlu.

**X2 — Yan domain katmanı.** BOS aşağı (son 3 bar) · rvol bandı · ayı FVG mesafesi · ayı OB mesafesi ·
weekly bağlam. Her domain "var / yok / **bilinmiyor**" üçlüsü; "bilinmiyor" asla 0 sayılmaz.
**Artık hücresi zorunlu**: dört domainin hiçbiri yok → ayrı satır; "geri kalan ne yapmış" cevaplanmadan
soru kapanmaz.

---

## 5. K1 — Kontrol (atlanamaz)

Aynı sembol, aynı `ATR1d` dilimi, aynı mesafe bandı; seviyeden bağımsız **rastgele barlar** (sabit tohum)
ve "seviye yok" karşı örneği. Aynı sonuç metrikleri.

K1 olmadan Y1–Y5'in yüzdeleri yorumlanamaz: destek seviyesine hiç bakmadan seçilen rastgele barlar da
benzer %60/%40 üretebilir. Yön hükmü kuralının 3. şartı (§2.4) budur.

---

## 6. Öncelik ve kod işleri

| Sıra | Soru | Neden |
|---|---|---|
| 1 | **Y1** | Kullanıcının modeli; ok yönünün ilk gerçek testi |
| 2 | **K1** | Y1'in yüzdesini anlamlandırır |
| 3 | **Y4** | Temizlik oranı hiç ölçülmedi, `▲` eşiklerinin dayanağı |
| 4 | Y2 → Y3 | Raf kavramı ve `▼` devam kuralı |
| 5 | Y5 → X1 → X2 | Sıkışma + açıklayıcı katmanlar |

| # | İş | Neden gerekli |
|---|---|---|
| **G0** | Dikeylik tanımları D1/D2/D3 + raf (shelf) metriği, replay checkpoint tablosuna | Y1/Y2 kütlesi; bugün yalnız kod proxy'si (D1) var |
| **G1** | "Son 3 barda BOS aşağı/yukarı" bayrağı | Bugün yalnız `ms_external_state` var, olay bayrağı yok |
| **G2** | Mum anatomisi sütunları (gövde, kp, aralık, fitil — günlük ATR) | `stabil_replay` checkpoint'inde yok |
| **G3** | Geri alım denemesi + "3 barda tuttu/tutmadı" + temas epizodu sayaçları | Y1/Y3/Y4 kütlesi |
| **G4** | Sembol hash bölmesi + keşif/doğrulama sütunları | Sözleşme |
| **G5** | Manifest tabanlı yön tablosu üreticisi (JSON/CSV) | Tekrarlanabilirlik (§8.8) |

---

## 7. Kapsam sınırı

- **Ok kuralları bu turda değişmez.** V2 yalnız ölçer ve "yön kuralı adayı" önerir; `▲`/`▼` eşiklerine
  dokunmak ayrı ve birlikte verilecek bir karardır.
- **Direnç tarafı** ilk turda koşmaz (aynı sorular sonra aynalanır).
- **Yeni domain yazılmaz**; yalnız mevcut 4 domain kullanılır.
- Checkpoint paketi (~80 MB) depoya eklenmez.

---

## 8. Onay istenen noktalar

1. **Dikeylik için hangi tanım esas alınsın?** D1 (kod proxy, %41) / D2 (eğim, %0,1) / D3 (`STEPPING_UP`, %29)
   — bence üçü de koşulmalı ve **ok kuralı en iyi ayrıştıran** tanımın üzerine kurulmalı; sen gözle
   baktığında "dikey" dediğin çizgi hangisi?
2. **"Altı dolu" raf tanımı** (son 20 barda ≥5 bar, ±0.35 ATR1d) senin gördüğünle uyuşuyor mu? Daha gevşek
   (≥3 bar / ±0.50 ATR1d) ölçülsün mü?
3. **Y3 çıktısı:** "başarısız geri alım → `▼`" fikri ok rework'ünün parçası mı olacak, yoksa ayrı bir
   uyarı işareti olarak mı kalmalı?
