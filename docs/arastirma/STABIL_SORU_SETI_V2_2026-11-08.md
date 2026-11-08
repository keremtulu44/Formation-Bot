# Stabil — V2 soru seti: **ok yönü çıkar mı?** (onay taslağı)

**Tarih:** 2026-11-08 · **Durum:** ÖNERİ (rev. 3) · **Kod:** henüz yok
[Ana rehber](STABIL_REHBERI.md) · [Eski 48 soru sicili (A–H, legacy)](STABIL_DAVRANIS_SORULARI.md) ·
[Sistem incelemesi](STABIL_SISTEM_INCELEMESI_2026-11-08.md) · [Davranış modeli](STABIL_DAVRANIS_MODELI.md) ·
Makine okunur: [`stabil_soru_seti_v2/manifest.json`](stabil_soru_seti_v2/manifest.json)

Amacı davranış betimlemek değil. Her soru tek cümleye bağlanır: **"Bu koşulda ok yönü çıkar mı, hangi
yönde?"** Cevabın "yön çıkmıyor" olması da geçerli sonuçtur. Bu yüzden her soru bir **yön hükmü** ile
kapanır (§2.4).

---

## 0. Kullanıcının modeli — ölçülecek asıl iddia

> "Dikey derken **step-step desteğin dikleşmesini** kastediyorum. Fiyat dikey destekten çıkmaya çalışır:
> düşüş devam ederse destek dikliğini bozmaz, **yeni step yapmaz**; ama o çıkışında **hafif bir yukarı
> tepki** gösterirse matematiksel Stabil desteği **yataya döner**. Dikeyken sağlam düşüş var demek,
> yatayken fiyat toparlandı demek."

Üç parçaya ayrılıyor — ve **"altı dolması" bir fiyat rafı değil, çizginin yataya dönmesidir**:

| Parça | Ne | Native karşılığı |
|---|---|---|
| **P1 Dikeylik** | Yükselen kademelerin (step) dikleşmesi | `STEPPING_UP` + seviyenin ATR cinsinden yükseliş hızı |
| **P2 Altı dolması** | Dik çizginin **yataya dönmesi** (hafif yukarı tepki sonrası) | `STEPPING_UP → NEWLY_FLATTENED_AFTER_RISE` geçişi |
| **P3 Sonuç** | Diken sonra yön: düşüş sürüyor mu, toparlanma mı | 16 × 4s bar `first_1atr` + getiri (ATR1d) |

### 0.1 Ölçülen yapı (20 sembol)

`STEPPING_UP` barlarının **10 bar içinde** vardığı durum (n=6.117):

| Sonraki durum | Pay |
|---|---|
| Hâlâ `STEPPING_UP` (dik kaldı) | %61,9 |
| `NEWLY_FLATTENED_AFTER_RISE` (**yataya döndü**) | %23,1 |
| `BREACHED_FIXED_SUPPORT` | %11,8 |
| `STEPPING_DOWN` | %3,0 |

Yani "dik çizgi ya dik kalır ya yataya döner" ikilemi gerçekten **en sık iki yol** (%62 / %23).

### 0.2 Ölçülen yön — iki zaman dilimi

**Günlük (esas, 39 sembol, 4.205 `STEPPING_UP` günü, ufuk 16 gün, ATR1d):**

| Dik destek ne yaptı (10 gün) | n | UP_first | DOWN_first | ort. getiri | medyan |
|---|---|---|---|---|---|
| **Dik kaldı** | 1.415 | %45,6 | **%53,5** | −0,14 ATR | **−0,29 ATR** |
| **Yataya döndü** | 2.790 | **%58,2** | %40,4 | **+0,46 ATR** | **+0,11 ATR** |

**4s (ikincil, 20 sembol, 6.117 bar, ufuk 16 × 4s bar):**

| Dik destek ne yaptı (10 bar) | n | UP_first | DOWN_first | ort. getiri | medyan |
|---|---|---|---|---|---|
| Dik kaldı | 4.525 | %51,1 | %47,6 | +0,05 ATR | −0,04 ATR |
| Yataya döndü | 1.479 | %54,8 | %43,3 | +0,83 ATR | +0,47 ATR |

**Karar: ölçüm günlükten yapılır.** Gerekçe hem native (matematik günlük pivotlarla, ATR günlük), hem
ölçüm (DOWN_first farkı günlükte 13 puan, 4s'te 4,3 puan). 4s yalnız **uygulama/çizim** katmanı: okun
tetiklendiği gün günlük kapanışta bilinen durum, sonraki günlük kapanışa kadar 4s grafikte devralınır.

### 0.2b Ölçümün en önemli kısıtı: senaryo seyrek

Günlükte fiyatın çizgiye mesafesine göre dağılım (aynı 4.205 gün):

| d = (kapanış − seviye)/ATR1d | n | 10 günde yataya dönme | UP_first |
|---|---|---|---|
| **d < 0 (fiyat dik desteğin altında)** | **16** | %43,8 | %43,8 |
| 0 … 0,5 (çizgiye yapışık) | 440 | %31,6 | %50,5 |
| 0,5 … 1,5 | 1.246 | %51,4 | %57,8 |
| > 1,5 (uzak) | 2.503 | %80,1 | %52,8 |

Yani "dik destek + fiyat altında + üstüne çıkma denemesi" **günlükte yalnız 16 gözlem** (39 sembolde).
Onunla ok kuralı kurulamaz. İki sonuç:

1. Okun hedefi "altına düşen fiyatın geri alımı" değil, **çizginin yataya dönüş anı** olmalı — bu %66
   sıklıkta ve yeterli n üretiyor.
2. Senaryoyu korumak istiyorsak kütle `d ≤ +0,5 ATR1d` ("fiyat çizgiye yapışık veya altında") olarak
   genişletilmeli (n≈456). Bu bir **kapsam kararı**; §8'de onay isteniyor.

### 0.3 KRİTİK UYARI — bu bir teşhis, sinyal değil

Yukarıdaki tablo **geleceğe bakarak** gruplanmıştır: bir barın "yataya dönecek" olduğu ölçüm anında
bilinmiyordu. Tradable hâle gelmesi için **nedensel** sürüm gerekir: yataya dönüşün **ilk işaretini**
(o "hafif yukarı tepki") gördüğümüz barda pozisyon almak. Y1'in işi tam olarak budur. Bu yüzden:

- **Y1-a (teşhis)**: yataya dönüş öncesi ortak nokta ne? (mum, hacim, tepki büyüklüğü)
- **Y1-b (nedensel)**: o işaret görüldüğü anda ölçülen ileri sonuç, dik kalanlarınkinden ayrışıyor mu?

### 0.4 "Dikey" tanımı: üç varyant (yan yana koşulur)

| Kod | Tanım | Bar payı (20 sembol) |
|---|---|---|
| **D1** | Mevcut kod proxy'si: rejim `STEPPING_UP/STEPPING_DOWN` veya son 8 günde yukarı rebase veya seviye değişti ve sabit değil | %41,1 |
| **D2** | **Eğim**: `(seviye_t − seviye_{t−20}) / ATR1d ≥ 1.0` | %0,1 |
| **D3** | `regime == STEPPING_UP` (kullanıcının "step dikleşmesi"nin native etiketi) | %28,8 (4s) |

**D1 bugün "yatay olmayan her destek dikey" demek** ve `HORIZONTAL_AFTER_DROP` /
`NEWLY_FLATTENED_AFTER_RISE` rejimlerinde hiç ateşlemiyor. Kullanıcının kastettiği dikeylik **D3 +
diklik derecesi**; bu yüzden D3 esas, D2 diklik derecesi olarak sütun olacak.

Diklik derecesi ölçümü: `step_dikligi = (seviye_t − seviye_{t−20}) / ATR1d` bantları
`≤0` / `0–1` / `1–2` / `>2`. (İlk denemede `>2` hücresinde yalnız 23 geri alım denemesi vardı; asıl
ölçüm 177 sembolde yapılacak.)

### 0.5 Örnek doldurulmuş şablon (gerçek ölçüm — biçim örneği)

Kütle: **günlük `STEPPING_UP` günleri**, 40 sembol, ufuk 16 gün → n=4.205.

**1) Ana bölünme:** `UP_first` %54,0 · `DOWN_first` %44,8 · `AMBIG` %0,9 · `NEITHER` %0,4.
(%70/%30 değil — gerçek sayı bu; %70 gibi bir eşik yalnız daraltılmış hücrelerde çıkar.)

**2–3) Azınlık profili (`DOWN_first`, n=1.883) ve LIFT (çoğunluk `UP_first`, n=2.270):**

| Özellik | Azınlıkta | Çoğunlukta | Lift | Yorum |
|---|---|---|---|---|
| Gövde `<0,20 ATR` (yönsüz) | %26,3 | %24,3 | **1,08** | **ayırt etmiyor** |
| Gövde `≥0,50 ATR` (büyük) | %38,7 | %39,6 | 0,98 | ayırt etmiyor |
| Kapanış altta `<0,35` | %38,7 | %34,7 | 1,12 | zayıf |
| Kapanış üstte `>0,65` | %27,0 | %33,5 | 0,81 | ters yönde zayıf |
| Aralık `>1,0 ATR` | %42,6 | %37,5 | 1,13 | zayıf |
| Hacim `rvol ≥1,2` | %27,6 | %27,7 | **1,00** | **ayırt etmiyor** |
| Hacim `rvol <0,8` | %40,7 | %39,7 | 1,02 | ayırt etmiyor |
| Fiyat çizginin **altında** | %0,5 | %0,3 | 1,55 | nadir ama en yüksek lift |
| Mesafe `0–0,5 ATR` | %11,5 | %9,8 | 1,17 | zayıf |

**Öğretici sonuç:** "kalan %30'un çoğu küçük/yönsüz mum" iddiası **bu kütlede doğrulanmıyor**
(lift 1,08; hacimde hiç fark yok). Ama bu, iddianın yanlış olduğu anlamına gelmez — iddia **dar
senaryo** için (fiyat çizgiye yapışık/altında, kapsam **b**) kurulmuş olabilir; orada yeniden test edilir.
Şablonun işi tam olarak bunu ayırmak: geniş kütlede kaybolan özellik, dar hücrede güçlenebilir.

### 0.6 Konu adayları — hepsi "ok çıkar mı?" sorusu (SEÇİM BEKLİYOR)

Her satır: **koşul → ok adayı → iddia**. Sadeleştirilmiş liste; her biri aynı şablonla (§2.3b) ölçülür.
"n durumu" yalnız ölçülmüş olanlarda yazılı, diğerleri ilk koşuda belli olacak.

| # | Koşul (kütle) | Ok adayı | İddia | n durumu |
|---|---|---|---|---|
| **K1** | Dik step-step destek + 1–3 günlük tepki → **10 günde yataya döndü** | **▲** | Toparlanma başladı | ölçüldü: ~12.000 (40 sembolde 2.790) |
| **K2** | Dik destek **dik kaldı** (tepki yok, yeni step yok) | **▼** | Düşüş sürüyor | ölçüldü: ~6.000 (40 sembolde 1.415) |
| **K3** | Sabit destek sarktı, **kapanış geri döndü** (temizlik oranı yüksek) | **▲** | Sarkma fitildi, kırılma değil | ölçülecek |
| **K4** | Sabit destek **derin kırıldı**, dönüş yok | **▼** | Kırılma gerçek | ölçülecek |
| **K5** | Uzun yatay destek (**≥24 gün**) + **ilk temas** | **▲** | Yatay taban tutar | ölçülecek |
| **K6** | **3. ve sonraki temas** | **▼** | Yapı yoruldu (kırılma riski) | ölçülecek |
| **K7** | Uzun yatay + **hacim patlaması** (rvol ≥1,2) | patlama yönü | Sıkışma çözülüyor | ölçülecek |
| **K8** | **Yeni yukarı step** (rebase) + güçlü gövde | **▲** | Momentum devam — *bugün canlıda olan ok* | doğrulama |
| **K9** | **≥20 gün yatay** + güçlü gövde | **▲** | Taban kırılımı — *bugün canlıda olan ok* | doğrulama |
| **K10** | Desteğin **altına gapla** açılış | ▼ veya ▲ | Panik mi, tuzak mı | ölçülecek |

**Notlar**
- **K8 ve K9 doğrulama**: bu iki ok bugün canlıda üretiliyor; ilk iş "gerçekten kazandırıyor mu" — ölçüm
  hazır olduğu için en ucuz ve en öğretici satırlar. Sonuç kötüyse ok rework'ünde ilk kesilecekler.
- **K1 + K2 tek soru**: aynı kütlenin iki tarafı (yataya döndü / dik kaldı). Birlikte ölçülmeli.
- **K5 ve K6** aynı ailenin iki ucu: ilk temas iyi, 3.+ temas kötü mü? İkisi tek tabloda.
- **K10** yalnız gap tanımı netleşirse (kaç ATR'lik açılış boşluğu) ölçülür.

**Önerilen ilk 3 (basit başlangıç):** **K1+K2** (senin modelin, en çok veri) → **K3+K4** (temizlik oranı,
hiç ölçülmedi) → **K8+K9** (canlıdaki okların doğrulanması, ucuz).

---

## 1. Kilitlenen kararlar

| Konu | Karar |
|---|---|
| Başarı ölçüsü | ±1 ATR ilk dokunma (16 × 4s bar) **+** 16. barda kapanış getirisi. Çelişen olay ayrı hücre. |
| Örneklem bölmesi | Sembol hash'i: `sha256(sembol) % 10 < 6` → keşif (~106), kalan doğrulama (~71). |
| Gruplama | İki eksen: native rejim/yaşam döngüsü × geometrik mesafe (ATR bandı). |
| Mum birimi | **Günlük ATR14** (girişte dondurulmuş). |
| Sicil | Yeni V2 ID uzayı (Y = yön, X = katman, K = kontrol); A–H legacy dondu. |
| Dallanma | 3 seviye: yön sonucu → mum anatomisi → domain → **artık hücresi** (zorunlu). |
| Min hücre | Ana kütle **n≥100**, alt hücre **n≥30**; altında yüzde yazılmaz: "yetersiz örneklem (n=..)". |
| Ölçüm TF | **Günlük (1d) esas**; 4s yalnız uygulama/çizim. |
| Tetik onayı | **Günlük kapanış onayı yeterli** (intraday erken tetik yok). |
| Kapsam | **(c)**: hem "dik kalma / yataya dönme" (geniş, n≈19.000) hem "fiyat çizgiye yapışık/altında" (dar, n≈2.000) ayrı satırlarda. |
| Şablon | Ana bölünme → azınlık profili → **LIFT** → mum → domain → artık → kontrol. |

---

## 2. Ölçüm sözleşmesi (ölçümden önce sabit)

**2.1 Birim ve bantlar**
- `d = (kapanış − seviye) / ATR1d`. Mesafe: **temas** `|low−seviye| ≤ 0.35 ATR1d` · **yakın**
  `0.35<|d|≤1.00` · **uzak** `1.00<|d|≤2.00` · **çok uzak** `|d|>2.00`.
- Temas epizodu: ardışık temas barları tek temas; yeni temas için ≥2 bar ayrılma (native `touch_count` kullanılmaz).
- Mum (günlük ATR): gövde **yönsüz <0.20** / 0.20–0.50 / **büyük ≥0.50**; kapanış pozisyonu
  <0.35 / 0.35–0.65 / >0.65; aralık dar <0.35 / 0.35–1.00 / >1.00.
- Hacim rvol: düşük <0.8 / normal 0.8–1.2 / yüksek ≥1.2.

**2.2 Yataylaşma geçişi ("altı dolması") — olay tanımı (günlük, gün cinsinden)**
- **Geçiş olayı:** `regime == STEPPING_UP` iken **10 gün** içinde `NEWLY_FLATTENED_AFTER_RISE` etiketinin
  ilk göründüğü gün. (10 gün = native pivot aralığı 2 × `daily_pivot_len` = 8 gün + 2 gün pay.)
- **Dik kalma:** aynı pencerede rejim `STEPPING_UP` kalıyor (yeni step yok).
- **Bozulma:** pencerede `BREACHED_FIXED_SUPPORT` veya `STEPPING_DOWN` (ayrı hücre, karıştırılmaz).
- **"Hafif yukarı tepki" — tek mum değil, değişken uzunlukta (kullanıcı kararı):**
  tepki **1–3 gün** sürebilir; **tek fitilli mum çizgiyi matematiksel olarak yataylaştırmaz**, bu yüzden
  yalnız fitil tepki sayılmaz. Varyantlar yan yana ölçülür:
  - **R1** (gövde katılımı): pencere içinde **en az bir gün** gövde `≥0.20 ATR1d` ve kapanış > açılış
  - **R2** (kapanış yeri): pencerenin son günü kapanış pozisyonu `>0.65`
  - **R3** (toparlanma): pencerenin en düşük dibinden son kapanışa `≥0.35 ATR1d`
  - **R4** = R1 **veya** R2, **ve** pencere hacmi `rvol ≥ 1.0`
  - **Geçersiz:** yalnız fitil (gövde `<0.20 ATR1d`) ve kapanış < açılış → tepki sayılmaz.

**2.2b R1–R4 ne demek (sade dil)**

Hepsi aynı şeyi ölçmenin dört farklı yolu: **"o hafif yukarı tepki gerçekten oldu mu?"** Tepki 1–3 gün
sürebilir; her varyant farklı bir "kanıt" arıyor:

| Varyant | Aradığı şey | Neden |
|---|---|---|
| **R1** | Pencerede **en az bir gün gerçek gövde** (gövde ≥0,20 ATR1d) ve kapanış > açılış | Tek fitilli mum yataylaştırmıyor; gövde şart |
| **R2** | Pencerenin **son günü üst tarafta kapanış** (kapanış pozisyonu >0,65) | Alıcı gün sonunda hâlâ güçlü |
| **R3** | Pencerenin **en dibinden son kapanışa** toplam toparlanma ≥0,35 ATR1d | Tepkinin büyüklüğü (fitil dahil) |
| **R4** | R1 **veya** R2, **ve** pencere hacmi `rvol ≥ 1,0` | Tepki hacimle destekleniyor mu |

Dördü **alternatif**, biri diğerinin yerine geçmez: ölçümde hangisinin "yataya dönüş"ü en iyi ayırdığı
görülecek. Hiçbiri ayırmıyorsa hüküm: **"tepki ölçütü çalışmıyor"** — o zaman bu yoldan ok çıkmaz.

**2.3 Yön hükmü (karar kuralı — ön kayıtlı)**
Bir koşul **ok adayı** olur ancak ve ancak:
1. keşifte `UP_FIRST` (veya `DOWN_FIRST`) **≥ %60** ve `n ≥ 100`,
2. doğrulamada aynı yön **≥ %55**,
3. kontrol (K1) aynı hücrede **≥10 puan** düşük.

Tutmazsa hüküm: **"ok üretme"**. Ayrıca **teşhis tabloları** (§0.2 gibi, geleceğe bakarak gruplanmış)
hiçbir zaman ok kuralına dönüşmez; yalnız nedensel tablolar dönüşür.

**2.3b Standart şablon — her soru bu sırayla doldurulur**

Kullanıcının istediği "%70 şöyle olunca yukarı olmuş, kalan %30'un ortak noktası ne" işi **budur** ve
her soru için aynı sırayla koşar:

1. **Ana bölünme:** kütlede sonuç oranları (ör. %54 yukarı / %45 aşağı / %1 belirsiz).
2. **Azınlık profili:** azınlık hücresinde her özelliğin payı.
3. **LIFT (zorunlu):** aynı özelliğin **çoğunluk** hücresindeki payı ve oranı `lift = azınlık / çoğunluk`.
   **Lift 1,0'a yakınsa o özellik "ortak nokta" değildir.** Lift yazılmadan hiçbir ortak nokta iddiası
   kabul edilmez. (Ör. "azınlığın %90'ı küçük mum" — çoğunlukta da %85 ise bulgu yoktur.)
4. **Katman sırası:** mum anatomisi → yan domain → **artık hücresi** (zorunlu).
5. **Kontrol (K1):** aynı hücrede rastgele bar / seviye yok.
6. **Yön hükmü:** §2.3.

*Örnek doldurulmuş şablon (gerçek ölçüm, §0.5) bu sıranın nasıl göründüğünü gösterir.*

**2.4 Diğer**
- Aynı barda iki eşik → `AMBIGUOUS` ayrı hücre. Sağ-sansür tabanda; yüzdeler geçerli n üzerinden.
- Ana ufuk **16 × 4s bar**; 1/4/8/10/12 yalnız ek sütun.
- Sembol yoğunlaşması: bir hücrenin %20'sinden fazlası tek sembolden gelirse not düşülür.

---

## 3. YÖN SORULARI (ana set)

### Y1 — Dik destekte yataya dönüş öngörülebilir mi? *(çekirdek, iki parçalı)*

**Y1-a (teşhis):** Dik kalma ile yataya dönme ayrımını ne yapıyor?
- **Kütle:** **günlük** `regime == STEPPING_UP` günleri (n≈4.200 / 39 sembol; 177 sembolde ~19.000 bekleniyor).
- **Bölünme:** 10 bar içinde yataya döndü / dik kaldı / bozuldu.
- **Alt hücreler:** geçişten önceki 1–3 barın mumu (gövde, kp, fitil) · `step_dikligi` bandı ·
  hacim · `touch_count` · son step'ten bu yana geçen gün · artık.
- **Cevaplanırsa:** "hafif yukarı tepki"nin hangi ölçülebilir tanımı ayrıştırıyor (R1–R4'ten hangisi).

**Y1-b (nedensel):** O işaret görüldüğü anda yön çıkıyor mu?
- **Kütle:** `regime == STEPPING_UP` **ve** R1–R4'ten biri sağlanan gün (işaret günü = tepki penceresinin
  son günü, karar o günün kapanışında verilir).
- **Kontrol:** aynı gün/rejimde işaret sağlamayan günler.
- **Bölünme:** 16 **gün**de `first_1atr` + getiri.
- **Yön kuralı adayı:** işaret var → `▲` (yataya dönüş lehine); işaret yok + fiyat çizgi altı → `▼` veya "ok yok".
- **Cevaplanırsa:** ok yönü ilk kez *yapı geçişinden* türetilir — bugün böyle bir ok **yok**.

### Y2 — "Dik kaldı" durumu düşüşün devamı mı? (`▼` kuralı)
- **Kütle:** Y1-a'nın **"dik kaldı"** hücresi (10 bar boyunca yeni step yok).
- **Bölünme:** sonraki 16 barda `first_1atr` (aşağı) + `mae_atr_16`.
- **Alt hücreler:** `step_dikligi` · fiyatın çizgiye mesafesi · düşüş barı gövdesi · hacim · BOS aşağı · artık.
- **Yön kuralı adayı:** dik + dik kaldı → `▼`. (Bugün dikeyde `▲` bastırılıp mercan `▼` uyarısı basılıyor;
  bu soru o uyarının *giriş* sinyaline dönüşüp dönmeyeceğini ölçer.)
- **Cevaplanırsa:** mevcut "dikeyde ok bastırma" politikası yön kuralına dönüşür.

### Y3 — Sabit desteğin altına inişte temizlik oranı yön veriyor mu?
- **Kütle:** kapanış `d < 0` (kırılma), ilk kırılma barı.
- **Bölünme:** 8 bar içinde kapanışla seviye üstüne dönüş (temizlik oranı) + 16 barda `first_1atr`.
- **Alt hücreler:** sarkma derinliği (`≤0.35` fitil / `0.35–1.0` / `1.0–2.0` / `>2.0`) · sarkma süresi ·
  kırılma gövdesi · hacim · BOS aşağı · artık.
- **Yön kuralı adayı:** sığ sarkma + hızlı dönüş → `▲`; derin sarkma + dönüş yok → `▼`.
- **Cevaplanırsa:** `▲` reclaim eşiklerinin (ihlal ≤1,5 ATR) dayanağı sayıya bağlanır.

### Y4 — Yatay desteğin üstünde tutunma neye bağlı?
- **Kütle:** `NEWLY_FLATTENED_AFTER_RISE` veya `LONG_HORIZONTAL` rejiminde, `0 < d ≤ 1.0`.
- **Bölünme:** 16 barda `first_1atr` + "sekme" (temas sonrası 8 barda `≥ +0,5 ATR`).
- **Alt hücreler:** yataylaşma yaşı (bar) · temas sayısı · hacim · BOS · artık.
- **Yön kuralı adayı:** yatay + temas → `▲`; dikey + temas → `▼` veya "ok yok".
- **Cevaplanırsa:** "dikey/yatay" ikilemi okun temel filtresi olur — bugünkü `long_base_breakout`
  (≥20 gün yatay) kuralının sayısal karşılığı netleşir.

### Y5 — Hareketsiz fiyat + hacim patlaması yön veriyor mu?
- **Kütle:** `|d| > 1.00` üst üste ≥6 bar **ve** sonraki barda rvol ≥1.2.
- **Bölünme:** 16 barda `first_1atr`.
- **Alt hücreler:** bekleme süresi · rejim · gövde · BOS · artık.
- **Yön kuralı adayı:** hareketsizlik + hacim → patlama yönünde `▲`/`▼`.

---

## 4. Açıklayıcı katmanlar (tek başına soru değil)

**X1 — Mum anatomisi.** Y1-a/Y2/Y3'ün azınlık hücrelerine uygulanır: gövde, kapanış pozisyonu, aralık,
fitil. **Neden/eşlikçi ayrımı** için aynı `ATR1d` diliminde ve aynı mesafe bandında eşleştirme zorunlu.

**X2 — Yan domain.** BOS aşağı (son 3 bar) · rvol · ayı FVG mesafesi · ayı OB mesafesi · weekly bağlam.
Her domain "var / yok / **bilinmiyor**"; "bilinmiyor" asla 0 sayılmaz. **Artık hücresi zorunlu**:
"geri kalan ne yapmış" cevaplanmadan soru kapanmaz.

---

## 5. K1 — Kontrol (atlanamaz)

Aynı sembol, aynı `ATR1d` dilimi, aynı mesafe bandı; seviyeden bağımsız rastgele barlar (sabit tohum) ve
"seviye yok" karşı örneği. Aynı sonuç metrikleri. Yön hükmünün 3. şartı budur (§2.3).

---

## 6. Öncelik ve kod işleri

| Sıra | Soru | Neden |
|---|---|---|
| 1 | **Y1-a** | "Hafif yukarı tepki" hangi tanımla ayrışıyor — her şeyin başlangıcı |
| 2 | **Y1-b** | Nedensel sürüm; ok kuralının doğduğu yer |
| 3 | **K1** | Y1-b'nin yüzdesini anlamlandırır |
| 4 | Y2 → Y3 → Y4 | `▼` kuralı, temizlik oranı, yatay filtresi |
| 5 | Y5 → X1 → X2 | Sıkışma + katmanlar |

| # | İş | Neden gerekli |
|---|---|---|
| **G0** | `step_dikligi` (20 bar ATR yükselişi) + yataylaşma geçiş etiketi + R1–R4 işaret bayrakları | Y1'in kütlesi |
| **G1** | "Son 3 barda BOS aşağı/yukarı" bayrağı | Bugün yalnız `ms_external_state` var |
| **G2** | Mum anatomisi sütunları (gövde, kp, aralık, fitil — günlük ATR) | `stabil_replay` checkpoint'inde yok |
| **G3** | Kırılma/temas/geri alım sayaçları + 3 bar "tuttu/tutmadı" | Y2/Y3 kütlesi |
| **G4** | Sembol hash bölmesi + keşif/doğrulama sütunları | Sözleşme |
| **G5** | Manifest tabanlı yön tablosu üreticisi | Tekrarlanabilirlik (§8.8) |
| **G6** | 177 sembollük tam koşu (paralel, ~10 dk) | Hücrelerin n≥100 olması için |

---

## 7. Kapsam sınırı

- **Ok kuralları bu turda değişmez.** V2 yalnız ölçer ve yön kuralı adayı önerir.
- **Direnç tarafı** ilk turda koşmaz.
- **Yeni domain yazılmaz**; mevcut 4 domain kullanılır.
- Checkpoint paketi (~80 MB) depoya eklenmez.

---

## 8. Onay istenen noktalar

1. **KAPSAM (en önemli):** "dik destek + fiyat altında" senaryosu günlükte yalnız 16 gözlem. Hangi kütle?
   - **(a)** Yalnız çizginin yataya dönüşü (n≈19.000, en güçlü istatistik) — senaryoyu dolaylı ölçer
   - **(b)** `d ≤ +0,5 ATR1d` ("fiyat çizgiye yapışık veya altında", n≈2.000) — senaryoyu doğrudan ölçer
   - **(c)** İkisi ayrı satırda
2. **Tepki penceresi 1–3 gün** ve **R1 (en az bir gövde ≥0,20 ATR1d)** senin gördüğün "hafif yukarı tepki"yi
   yakalıyor mu? (Tek fitil hariç tutuldu — dediğin gibi yataylaştırmıyor.)
3. **Yataylaşma penceresi 10 gün** (native 8 gün + 2 pay) doğru mu?
4. **Y2 çıktısı `▼`** (dik kaldı → düşüş devam): ok rework'ünün parçası mı, ayrı uyarı mı? — "bakarız" notu duruyor.
