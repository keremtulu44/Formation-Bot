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

### 0.7 Süreç haritası: 9 durum (kullanıcının senaryo ağacı)

Kullanıcının anlattığı süreç iki eksene indi: **fiyatın yeri** (desteğin altı / yapışık / üstü) ×
**desteğin davranışı** (sabit / yukarı hareket / aşağı hareket; son 10 günde seviye değişti mi).
Her gün bir duruma düşüyor, sonra ne olduğu ölçülüyor. (39 sembol, 16.745 gün, ufuk 16 gün.)

| Durum | n | 16 günde kırılma | UP_first | DOWN_first | medyan | **3 gün sonra** alt/yapışık/üst |
|---|---|---|---|---|---|---|
| alt + sabit | 1.881 | %91,3 | **%54,7** | %43,9 | −0,37 ATR | **60 / 9 / 31** |
| alt + yukarı | 712 | %92,1 | %49,2 | %50,4 | +0,06 | 65 / 10 / 25 |
| alt + aşağı | 580 | %95,3 | %50,9 | %47,1 | −0,14 | 72 / 8 / 20 |
| yapışık + sabit | 462 | %73,6 | %53,7 | %45,2 | −0,12 | 29 / 18 / 53 |
| yapışık + yukarı | 520 | %70,8 | %51,0 | %48,7 | +0,24 | 38 / 18 / 44 |
| yapışık + aşağı | 442 | %76,7 | %49,3 | %49,1 | −0,42 | 41 / 19 / 40 |
| üst + sabit | 4.153 | **%39,5** | %53,2 | %45,6 | −0,17 | 5 / 7 / 89 |
| üst + yukarı | 4.032 | %42,6 | %54,1 | %44,5 | −0,02 | 6 / 7 / 86 |
| üst + aşağı | 3.963 | %42,2 | %49,5 | %49,0 | −0,14 | 6 / 8 / 86 |

*(Kırılma = sonraki 16 günde o gün bilinen seviyenin altına kapanış. "Alt" durumlarında bu tanım
neredeyse hep doğru olduğu için o satırların okunması gereken sütunu "3 gün sonra" dağılımıdır.)*

**Bu haritanın söyledikleri — üç net sonuç:**

1. **Kırılma riskini destek hareketi değil, mesafe belirliyor.** Üstteyken kırılma %39–43; çizgiye
   yapışıkken %71–77. Destek sabit mi hareketli mi: fark yalnız 2–4 puan. Yani "destek hareketlenince
   kırılır" iddiası bu kütlede **zayıf**.
2. **"Sabit destek tepki verir" iddiası zayıf ama aynı yönde.** Altta kalan fiyat 3 gün içinde üste
   dönme: sabit destekte %31, yukarı hareketli destekte %25, aşağı hareketli destekte %20.
   Ayrıca alt+sabit, alt durumların en yüksek UP_first'ine sahip (%54,7 vs %49–51).
3. **Hiçbir statik durum ok eşiğini geçmiyor.** En yüksek UP_first %54,7; ön kayıtlı eşik %60.
   Sonuç: **ok statik durumdan değil, geçişten (olaydan) çıkmalı** — yani K1/K2'nin "yataya döndü /
   dik kaldı" olayı ve R1–R4 tepki tetikleyicileri doğru yol; statik durum tabloları ok kaynağı değil.


### 0.8 Senaryo kataloğu — "şuradan şuraya geçersek ne oluyor"

**Tanım:** senaryo = bir gün **A durumundan B durumuna geçiş** (durum = fiyatın yeri × desteğin davranışı,
§0.7). Geçiş günü gözlenebilir olduğu için ölçüm o günden ileri yapılır → **nedensel**. ID: `A -> B`.

**İki ayrı ölçüm, karıştırılmamalı:** *teşhis* (durumun kendisinden ileri — harita) ve *nedensel*
(geçiş gününden ileri — ok adayı). Dosyalar: `senaryo_teshis_sonuclari_2026_11_08.csv` (73 hücre) ve
`senaryo_gecis_sonuclari_2026_11_08.csv` (58 hücre). 39 sembol, günlük, ufuk 16 gün, 3.496 geçiş olayı.

**Sonucu olan 30 senaryo** (kenar = UP% − DN%):

| Senaryo (geçiş günü) | n | UP_first | DOWN_first | medyan | 16g kırılma | Karar |
|---|---|---|---|---|---|---|
| `alt+asagi -> alt+sabit` | 81 | %69.1 | %29.6 | +0.20 | %95.1 | **ADAY ▲** |
| `alt+sabit -> ust+sabit` | 44 | %65.9 | %34.1 | -0.49 | %40.9 | **ADAY ▲** |
| `alt+sabit -> yapisik+sabit` | 100 | %64.0 | %36.0 | -0.11 | %65.0 | **ADAY ▲** |
| `yapisik+yukari -> ust+yukari` | 148 | %59.5 | %39.2 | +0.73 | %48.0 | — |
| `alt+sabit -> yapisik+asagi` | 33 | %57.6 | %39.4 | -0.56 | %81.8 | — |
| `alt+yukari -> ust+yukari` | 33 | %57.6 | %39.4 | +0.70 | %39.4 | — |
| `yapisik+asagi -> ust+asagi` | 135 | %57.8 | %41.5 | -0.42 | %60.0 | — |
| `ust+sabit -> ust+yukari` | 333 | %56.2 | %41.7 | -0.40 | %47.4 | — |
| `yapisik+sabit -> ust+sabit` | 112 | %56.2 | %42.0 | -0.17 | %51.8 | — |
| `ust+sabit -> yapisik+yukari` | 44 | %56.8 | %43.2 | +0.29 | %72.7 | — |
| `alt+asagi -> ust+asagi` | 31 | %54.8 | %41.9 | -0.41 | %61.3 | — |
| `yapisik+sabit -> alt+sabit` | 130 | %54.6 | %43.8 | +0.15 | %90.8 | — |
| `ust+sabit -> alt+sabit` | 47 | %53.2 | %46.8 | -0.26 | %89.4 | — |
| `ust+yukari -> ust+sabit` | 248 | %52.4 | %46.8 | -0.34 | %41.1 | — |
| `ust+sabit -> yapisik+sabit` | 137 | %50.4 | %47.4 | -0.08 | %75.2 | — |
| `alt+sabit -> ust+asagi` | 169 | %50.3 | %49.1 | -0.29 | %42.6 | — |
| `alt+yukari -> yapisik+yukari` | 56 | %50.0 | %50.0 | -0.13 | %69.6 | — |
| `ust+asagi -> yapisik+asagi` | 187 | %48.7 | %50.8 | -0.35 | %77.5 | — |
| `ust+yukari -> ust+asagi` | 59 | %47.5 | %50.8 | +0.38 | %32.2 | — |
| `alt+asagi -> yapisik+asagi` | 49 | %46.9 | %51.0 | -0.92 | %73.5 | — |
| `yapisik+asagi -> alt+asagi` | 122 | %46.7 | %50.8 | -0.38 | %95.1 | — |
| `ust+yukari -> yapisik+yukari` | 215 | %47.4 | %51.6 | +0.37 | %74.0 | — |
| `yapisik+yukari -> alt+yukari` | 141 | %46.8 | %52.5 | +0.08 | %92.2 | — |
| `ust+asagi -> ust+sabit` | 234 | %45.3 | %53.4 | +0.03 | %40.2 | — |
| `ust+asagi -> ust+yukari` | 82 | %43.9 | %52.4 | -0.33 | %48.8 | — |
| `alt+yukari -> alt+sabit` | 86 | %44.2 | %54.7 | -0.27 | %90.7 | — |
| `ust+sabit -> ust+asagi` | 107 | %43.0 | %55.1 | -0.44 | %38.3 | — |
| `yapisik+sabit -> ust+asagi` | 50 | %42.0 | %58.0 | -0.69 | %46.0 | — |
| `ust+yukari -> alt+yukari` | 65 | %38.5 | %60.0 | +0.33 | %83.1 | **ADAY ▼** |
| `ust+asagi -> alt+asagi` | 49 | %36.7 | %61.2 | +0.02 | %93.9 | **ADAY ▼** |

**Sonucu OLMAYANLAR (replay'e kalacaklar):**
- **28 hücre** n<30 → CSV'de `durum=yetersiz-n`. Tam koşuda çoğu n≥30'a çıkar.
- **~400 koşullu senaryo** (`A -> B` + tepki tipi R1–R4 / hacim / BOS aşağı / mum anatomisi / gap)
  hiç ölçülmedi; G0–G2 sütunları gerekiyor.

---

### 0.9 DOĞRULAMA KOŞUSU — adaylar keşif/doğrulama ayrımında test edildi

**Kurulum:** 119 sembol, günlük, olaylar arası **en az 5 gün** ayrım, ufuk 16 gün, **5.530 geçiş olayı**.
Sembol hash'i ile bölme: **keşif %60** / **doğrulama %40**. Taban oran (durumdan bağımsız, her 5. gün):
**keşif UP %54,1 / DOWN %44,0**, **doğrulama UP %54,8 / DOWN %43,5**.

**En önemli bulgu: taban oran %54.** Yani "%60 yukarı" tek başına beceri değil; her senaryo **tabana göre**
okunmalı. Ölçüm sözleşmesi buna göre kilitlendi (§2).

**Sonuç — 59 senaryo hücresi:**

| Karar | Sayı | Anlamı |
|---|---|---|
| **OK-▼** | **5** | Aşağı yön, tabana göre anlamlı, doğrulamada tutuyor |
| **OK-▲** | **0** | **Hiçbir yukarı senaryo kalmadı** |
| ELENDİ | 15 | Keşifte görünen kenar doğrulamada kayboldu |
| yetersiz-n | 39 | n<50 (keşif) veya n<20 (doğrulama) |

**Doğrulanan 5 senaryo (hepsi aşağı):**

| Senaryo | nK | UP_keşif | nD | UP_doğr | UP lift K/D | p (tek yön) |
|---|---|---|---|---|---|---|
| `ust+aşağı → ust+sabit` | 465 | %47,7 | 187 | %48,7 | −6,4 / −6,1 | 0,0004 |
| `ust+aşağı → yapışık+aşağı` | 226 | %42,9 | 108 | %51,9 | −11,2 / −2,9 | 0,0005 |
| `ust+sabit → yapışık+sabit` | 103 | %48,5 | 50 | %38,0 | −5,6 / −16,8 | 0,0087 |
| `ust+yukarı → alt+yukarı` | 82 | %42,7 | 30 | %43,3 | −11,5 / −11,5 | 0,0132 |

(`ust+aşağı → alt+aşağı` = %39,7 / %39,1, n=63/23, p=0,0022 — tabloda da var.)

**Ortak nokta:** fiyat **desteğe doğru inerken** destek ya **aşağı step** yapıyor ya da **sabit**; her iki
hâlde de **yukarı ilk dokunma tabanın altında**. Kullanıcının "dikey destek altına düşen fiyat tekrar altına
iner" iddiası `ust+yukarı → alt+yukarı` satırıyla **doğrulandı** (−11,5 puan, iki kümede de aynı).

**En öğretici iki eleme:**
- `alt+sabit → yapışık+sabit`: keşif %61,1 (aday) → doğrulama **%44,4** → sahte.
- `alt+aşağı → alt+sabit`: küçük örneklemde %69,1 idi; geniş örneklemde %57,6 / %61,2 (lift +3,5/+6,4) →
  eşiği geçemedi. **%69 gürültüymüş.**

**Bonferroni (59 test → p<0,00085):** yalnız **2** senaryo geçiyor (`ust+aşağı → ust+sabit`,
`ust+aşağı → yapışık+aşağı`) → "destek aşağı step yaparken fiyat yaklaşırsa düşüş sürer" **en sağlam** bulgu.

**Gözlem listesi (ok değil):** `ust+sabit → ust+yukarı` — n=695, UP %58,5→%59,3, lift +4,3/+4,5, p=0,008.
Tek tutarlı pozitif; 6 puan eşiğini geçmediği için aday değil.

**İlk 21 hücre** (nK≥30 ve nD≥20):

| Senaryo | nK | UP_keşif | nD | UP_doğr | UP lift K/D | p | Karar |
|---|---|---|---|---|---|---|---|
| `ust+asagi -> ust+sabit` | 465 | %47.7 | 187 | %48.7 | -6.4 / -6.1 | 0.9992 | OK-▼ |
| `ust+asagi -> yapisik+asagi` | 226 | %42.9 | 108 | %51.9 | -11.2 / -2.9 | 0.9989 | OK-▼ |
| `ust+asagi -> alt+asagi` | 63 | %39.7 | 23 | %39.1 | -14.5 / -15.7 | 0.9967 | OK-▼ |
| `ust+sabit -> yapisik+sabit` | 103 | %48.5 | 50 | %38.0 | -5.6 / -16.8 | 0.9876 | OK-▼ |
| `ust+yukari -> yapisik+yukari` | 215 | %46.0 | 99 | %53.5 | -8.1 / -1.3 | 0.9792 | ELENDI |
| `ust+yukari -> alt+yukari` | 82 | %42.7 | 30 | %43.3 | -11.5 / -11.5 | 0.9917 | OK-▼ |
| `alt+sabit -> ust+asagi` | 260 | %51.5 | 112 | %40.2 | -2.6 / -14.6 | 0.9901 | ELENDI |
| `yapisik+asagi -> alt+asagi` | 57 | %43.9 | 23 | %56.5 | -10.3 / +1.7 | 0.8833 | ELENDI |
| `ust+yukari -> ust+sabit` | 480 | %50.6 | 216 | %54.6 | -3.5 / -0.2 | 0.8855 | ELENDI |
| `ust+sabit -> ust+asagi` | 73 | %42.5 | 30 | %53.3 | -11.7 / -1.5 | 0.9585 | ELENDI |
| `ust+yukari -> ust+asagi` | 83 | %47.0 | 38 | %60.5 | -7.2 / +5.7 | 0.7390 | ELENDI |
| `ust+asagi -> ust+yukari` | 136 | %49.3 | 69 | %52.2 | -4.9 / -2.6 | 0.8685 | ELENDI |
| `alt+yukari -> alt+sabit` | 116 | %44.8 | 61 | %55.7 | -9.3 / +0.9 | 0.9309 | ELENDI |
| `yapisik+sabit -> alt+sabit` | 62 | %56.5 | 28 | %50.0 | +2.3 / -4.8 | 0.4769 | ELENDI |
| `yapisik+yukari -> ust+yukari` | 54 | %53.7 | 24 | %54.2 | -0.4 / -0.6 | 0.5207 | ELENDI |
| `yapisik+yukari -> alt+yukari` | 67 | %47.8 | 32 | %71.9 | -6.4 / +17.1 | 0.3887 | ELENDI |
| `alt+sabit -> yapisik+sabit` | 90 | %61.1 | 36 | %44.4 | +7.0 / -10.4 | 0.3093 | ELENDI |
| `alt+sabit -> yapisik+asagi` | 46 | %60.9 | 20 | %45.0 | +6.7 / -9.8 | 0.3771 | yetersiz-n |
| `yapisik+asagi -> ust+asagi` | 54 | %63.0 | 24 | %54.2 | +8.8 / -0.6 | 0.1391 | ELENDI |
| `alt+asagi -> alt+sabit` | 118 | %57.6 | 49 | %61.2 | +3.5 / +6.4 | 0.1194 | ELENDI |
| `ust+sabit -> ust+yukari` | 496 | %58.5 | 199 | %59.3 | +4.3 / +4.5 | 0.0079 | ELENDI |

### 0.10 GENEL OKUMA — senaryolar tek tek değil, aile olarak ölçüldü (rev10)

**Ne değişti:** rev9'dan sonra plan, 5 `▼` adayını **teker teker** hacim/mum koşuluyla keskinleştirmekti
(~30 küçük örneklem hücresi). Bunun yerine **tek koşullandırma katmanı bütün senaryolara aynı anda**
uygulandı; karar hücre hücre değil **aile düzeyinde** ve **senaryo-stratifiye tek test**le verildi.

**Aynı olay kümesi:** 119 sembol, **5.530 geçiş olayı**, 59 geçiş, olaylar arası ≥5 gün, ufuk 16 gün,
taban **keşif UP %54,1 / DOWN %44,0** · **doğrulama UP %54,8 / DOWN %43,5**. rev9 ile **birebir
karşılaştırılabilir**: §2.1–§2.8 aynen korundu, giriş gününe yalnız üç nitelik eklendi
(`rvol`, `gövde`, `kapanış konumu`; §2.8'deki kilitli bantlarla). **Olay kümesi hiç değişmedi.**

#### 1) Havuzda görünen koşul etkisi GERÇEK DEĞİL — kompozisyon

Tüm olaylar tek havuzda, tek değişkenli bakıldığında koşullar güçlü görünüyor (keşif):

| Katman | n keşif | UP % | UP lift | DOWN lift | p (DOWN) |
|---|---|---|---|---|---|
| `rvol < 0,8` | 1.616 | %52,5 | −1,7 | +2,0 | 0,054 |
| `rvol 0,8–1,2` | 1.218 | %50,4 | −3,7 | +4,3 | 0,0012 |
| `rvol ≥ 1,2` | 1.037 | %48,2 | −5,9 | +4,9 | 0,0007 |
| `gövde ≥ 0,50` | 1.757 | %49,9 | −4,3 | +4,3 | 0,0002 |
| `kapanış gün dibinde (<0,35)` | 1.955 | %48,0 | −6,2 | +6,2 | <0,0001 |

Üç test bu tabloyu **çürütüyor**:

1. **Senaryo-stratifiye Mantel–Haenszel** (her senaryo kendi içinde; tek test):
   `rvol yüksek vs düşük` **OR 0,82 (p=0,020) → 0,93 (p=0,55)**;
   `gövde büyük vs yönsüz` **0,95 → 0,93** (p=0,58 / 0,61);
   `kapanış üst vs alt` **1,07 → 0,85** (p=0,44 / 0,28).
   **Doğrulamada hiçbiri kalmıyor.**
2. **İşaret testi:** `rvol yüksek > düşük` kaç senaryoda DOWN lift'ini büyütüyor → keşif **9/14** (p=0,21),
   doğrulama **3/6** (p=0,66). Yön bile tutarlı değil.
3. **Kompozisyon kanıtı:** `kapanış konumu` ile senaryo arasında **Cramér's V = 0,383**. "Gün dibinde
   kapanış" zaten `üst+aşağı` geçişinin tarifidir; havuzdaki +6,2 puan **senaryodan** geliyor, koşuldan değil.

> **Ders:** havuzlanmış tek değişkenli tablo, 59 senaryoyu tek torbaya attığı için yanıltıcı.
> Sözleşmeye bu yüzden **§2.9** eklendi: koşullandırma yalnız senaryo-stratifiye veya aile-içi testle kanıtlanır.

#### 2) Doğru okuma: aile düzeyi (59 hücre yerine 11 aile)

DOWN lift = tabana göre puan (taban DOWN: keşif %44,0 · doğrulama %43,5).

| Aile ekseni | Aile | nK | DN % K | lift K | p K | nD | DN % D | lift D | p D | İki kümede |
|---|---|---|---|---|---|---|---|---|---|---|
| fiyat yeri | **`üst → alt`** | 197 | %53,3 | **+9,3** | 0,0045 | 75 | %58,7 | **+15,2** | 0,0039 | **EVET** |
| fiyat yeri | **`üst → yapışık`** | 632 | %54,1 | **+10,1** | <0,0001 | 298 | %47,7 | +4,2 | 0,072 | kısmî (D zayıf) |
| fiyat yeri | `yapışık → üst` | 211 | %40,8 | −3,3 | 0,83 | 92 | %47,8 | +4,4 | 0,20 | hayır |
| fiyat yeri | `alt → üst` | 411 | %45,7 | +1,7 | 0,24 | 164 | %53,7 | +10,2 | 0,0042 | hayır (yalnız D) |
| destek | **`aşağı → aşağı`** | 492 | %52,4 | **+8,4** | 0,0001 | 204 | %48,0 | +4,6 | 0,093 | kısmî |
| destek | **`aşağı → sabit`** | 618 | %48,9 | **+4,8** | 0,0079 | 259 | %46,7 | +3,3 | 0,14 | kısmî |
| destek | `sabit → aşağı` | 416 | %45,9 | +1,9 | 0,22 | 181 | %55,2 | +11,8 | 0,0007 | hayır (yalnız D) |
| destek | `yukarı → aşağı` | 136 | %52,2 | +8,2 | 0,028 | 58 | %39,7 | −3,8 | 0,72 | hayır (D'de ters) |
| destek | `sabit → sabit` | 386 | %43,3 | −0,8 | 0,62 | 164 | %51,2 | +7,8 | 0,022 | hayır |
| kaynak konum | `üst` (tüm) | 2.562 | %49,1 | +5,1 | <0,0001 | 1.112 | %46,0 | +2,5 | 0,046 | **EVET** |
| kaynak konum | `alt` (tüm) | 884 | %44,6 | +0,5 | 0,38 | 364 | %48,6 | +5,2 | 0,023 | hayır |

**Okuma:**
- **İki kümede de tutan tek aile `üst → alt`.** Fiyat desteğin altına indiği gün, 16 günde ilk ±1 ATR
  dokunması belirgin şekilde aşağı: **+9,3 / +15,2 puan**. 11 aile testi → Bonferroni eşiği **0,0045**;
  `üst → alt` her iki kümede **tam sınırda** geçiyor (0,0045 / 0,0039) → "sağlam ama sınırda".
- **`üst → yapışık` ve `aşağı → aşağı`** keşifte çok güçlü, doğrulamada yön aynı ama anlamsız → **kısmî**.
  rev9'un "destek aşağı step yaparken düşüş sürer" bulgusu aile olarak **doğrulanıyor ama zayıflıyor**.
- **Asimetri uyarısı:** `sabit → aşağı`, `alt → üst` gibi aileler **yalnız doğrulamada** anlamlı; keşifte
  yoklar → kural gereği (§2.7) aday olamazlar. Bunlar "ters sırada bulunmuş" tesadüfler.
- **Yukarı taraf:** tek tutarlı aile **`sabit → yukarı`** (destek yukarı adım atmaya başlıyor):
  UP %57,4 (+3,2, n=542, p=0,065) / %58,7 (+3,9, n=218, p=0,12) → **6 puan eşiğinin altında**.
  ⇒ rev9'un "**0 ▲**" sonucu aile düzeyinde de aynı: **yukarı ok yok**.

#### 3) Tek genel filtre — 5 ayrı kural değil, 1 kapı

`▼` ailesi (rev9'un 5 hücresi) **tek gövde** olarak havuzlandı; iki koşul ayrı ayrı ve birlikte sınandı:

| Durum | nK | DN % K | lift K | p K | nD | DN % D | lift D | p D |
|---|---|---|---|---|---|---|---|---|
| aile, filtre yok | 939 | %52,9 | +8,9 | <0,0001 | 398 | %51,3 | +7,8 | 0,0008 |
| + `rvol ≥ 0,8` | 561 | %56,9 | **+12,8** | <0,0001 | 226 | %55,3 | **+11,9** | 0,0002 |
| + `gövde ≥ 0,20` | 778 | %53,6 | +9,5 | <0,0001 | 323 | %52,9 | +9,5 | 0,0003 |
| **+ ikisi birden** | **466** | **%56,9** | **+12,8** | **<0,0001** | **188** | **%57,4** | **+14,0** | **0,0001** |
| aile, `rvol < 0,8` (**elenen**) | 378 | %47,1 | +3,0 | 0,12 | 172 | %45,9 | +2,5 | 0,26 |
| aile, `gövde < 0,20` (**elenen**) | 161 | %49,7 | +5,6 | 0,075 | 75 | %44,0 | +0,5 | 0,46 |

- **Kapı mı, süs mü?** Elenen iki taraf da taban gürültüsüne düşüyor (+3,0/+2,5 ve +5,6/+0,5) → bu iki
  koşul sinyali **üretmiyor, ayıklıyor**. Kilitli kural (§2.7) filtrelenmiş ailede rahat geçiyor.
- **Sembol yoğunlaşması yok:** en büyük tek sembol payı %3 (keşif) / %5 (doğrulama).
- **Kontrol — yanlış kullanım testi:** aynı filtre **tüm** olaylara uygulanınca hiçbir şey eklemiyor
  (DOWN lift +3,5 → +4,4 keşif; +2,8 → +2,9 doğrulama). ⇒ filtre **kendi başına sinyal değil**, yalnız
  `▼` ailesinin içinde anlamlı. Yukarı tarafta da işe yaramıyor: UP %52,0 → %50,5 (keşif).
- **Senaryo bazında (keşif, önce → sonra):** `üst+aşağı → üst+sabit` %51,0 → **%55,4** (n=224) ·
  `üst+aşağı → yapışık+aşağı` %55,8 → **%60,0** (n=100) · `üst+aşağı → alt+aşağı` %58,7 → **%60,0** (n=45) ·
  `üst+yukarı → alt+yukarı` %53,7 → **%61,4** (n=57). **İstisna:** `üst+sabit → yapışık+sabit`
  %51,5 → %47,5 (n=40) — ailenin zaten en zayıf hücresi, filtre onu kurtarmıyor.

#### 4) Pratik anlamı (ok kuralı **değişmedi**)

1. **Tek aday kural** (5 ayrı senaryo yerine): *kaynak `üst` + geçiş günü destek aşağı step ya da fiyat
   desteğe iniyor + `rvol ≥ 0,8` + `gövde ≥ 0,20` → 16 günde ilk ±1 ATR dokunması aşağı.*
   Ölçülmüş hâli: n 466/188, DOWN %56,9/%57,4, lift +12,8/+14,0. **Bu bir aday**; ok kuralına dönüşmesi
   onay bekliyor (rev9 kararı: ok değişmiyor).
2. **Yukarı ok yok**; `sabit → yukarı` gözlem listesinde kalıyor (+3,2/+3,9).
3. **Teker teker keskinleştirme iptal:** genel okuma, ~30 küçük hücre yerine **11 aile + 4 MH + 2 filtre
   testi** ile aynı bilgiyi verdi — ve çoklu karşılaştırma riskini ortadan kaldırdı.

**Tekrar üretim (replay):** `docs/arastirma/stabil_soru_seti_v2/kosular/rev10_*.py` sırasıyla
`rev10_olay_uretimi.py` (olay + taban, ~325 s) → `rev10_genel_analiz.py` → `rev10_kosul_gercek_mi.py` →
`rev10_tek_filtre.py` → `rev10_csv.py`. Çalıştırma: `PYTHONPATH=. .venv/bin/python <dosya>`.

**Açık kalan (onay bekleyen):** (a) tek aday kuralın ok olarak kilitlenmesi, (b) `üst → alt` ailesinin
hangi alt hücrelerden beslendiğinin sembol bazında dökümü, (c) 177 sembollük tam koşu.

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
| Genel okuma | Karar **aile düzeyinde** verilir (59 hücre değil); koşullandırma yalnız senaryo-stratifiye MH veya aile-içi testle kanıtlanır (§2.9). |
| Hacim/mum filtresi | Tek genel kapı: **`rvol ≥ 0,8` + `gövde ≥ 0,20`**, yalnız `▼` ailesi içinde geçerli; tek başına sinyal değil. |

---

## 2. ÖLÇÜM SÖZLEŞMESİ v2.1 — KİLİTLİ (2026-11-08)

*(v2.1 = v2.0 + madde 2.9. §2.1–§2.8 **değişmedi**; rev9 sonuçları geçerli.)*

Aşağıdaki tanımlar **donduruldu**. Değiştirmek için yeni sürüm numarası gerekir; aksi hâlde sonuçlar
karşılaştırılamaz.

**2.1 Zaman dilimi ve birim**
- Ölçüm **günlük (1d)**; 4s yalnız uygulama/çizim. Tüm pencereler **gün** cinsinden.
- `ATR1d` = giriş gününde dondurulmuş, nedensel Wilder ATR14 (günlük).
- `d = (kapanış − destek seviyesi) / ATR1d`.

**2.2 Durum tanımı (9 durum)**
- Fiyat yeri: **alt** `d < −0.05` · **yapışık** `−0.05 ≤ d ≤ +0.50` · **üst** `d > +0.50`.
- Destek davranışı: seviyenin **10 gün önceki** değerine göre `Δ = (seviye_t − seviye_{t−10}) / ATR1d`;
  **sabit** `|Δ| < 0.02` · **yukarı** `Δ ≥ 0.02` · **aşağı** `Δ ≤ −0.02`.
- Durum = `fiyat_yeri + destek_davranışı` (ör. `ust+yukari`).

**2.3 Senaryo (geçiş) tanımı**
- Senaryo = **durumun değiştiği gün**: `durum(t−1) = A`, `durum(t) = B`, `A ≠ B`.
- Aynı sembolde iki olay arasında **en az 5 gün** (örtüşme azaltma). Bu kural uygulanmadan elde edilen
  sayılar yalnız teşhis amaçlıdır, karar veremez.

**2.4 Sonuç metrikleri**
- **Birincil:** `first_1atr_16` = geçiş günü kapanışından itibaren 16 gün içinde **+1 ATR** (UP) mi
  **−1 ATR** (DOWN) mı önce vuruldu. Aynı gün ikisi → `AMBIG` (ayrı hücre, yukarı/aşağı sayılmaz).
  16 gün dolmadan veri biterse `NEITHER`/sansür → tabanda.
- **İkincil:** `ret_atr_16` (16. gün kapanış getirisi, ATR1d) medyanı; `kirilma` = 16 gün içinde o gün
  bilinen seviyenin altına kapanış oranı.

**2.5 Taban oranı (baseline) — ZORUNLU**
- Her sembolde **her 5. gün** durumdan bağımsız örneklenir; aynı `first_1atr_16` metriği hesaplanır.
- Taban **ayrı ayrı keşif ve doğrulama kümelerinde** raporlanır ve her senaryo **tabana göre** okunur.
- Ölçülen taban (2026-11-08): keşif UP %54,1 / DOWN %44,0 · doğrulama UP %54,8 / DOWN %43,5.
- **Kural:** mutlak yüzde karar için kullanılmaz; **lift** (senaryo − taban) kullanılır.

**2.6 Örneklem bölmesi**
- `sha256(sembol) % 10 < 6` → **keşif**; kalan → **doğrulama**. Bölme ölçümden önce sabit.

**2.7 Karar kuralı (ok adayı)**
Bir senaryo ok adayı olur ancak ve ancak:
1. **n ≥ 50** (keşif) ve **n ≥ 20** (doğrulama),
2. keşifte **lift ≥ +6 puan** (yukarı için UP, aşağı için DOWN),
3. doğrulamada **aynı yönde lift ≥ +1 puan**,
4. havuzlanmış tek yönlü binom **p < 0,05**,
5. ve §5'teki kontrol (K1) ile çelişmiyor.

Ek not: 59 hücre test edildiği için **Bonferroni eşiği p < 0,00085** ayrıca raporlanır; bu eşiği geçen
senaryolar "sağlam", yalnız p<0,05'i geçenler "yön doğru, kanıt orta" sayılır.

**2.8 Diğer sabitler**
- Mum anatomisi (günlük ATR): gövde `<0.20` yönsüz / `0.20–0.50` / `≥0.50` büyük; kapanış pozisyonu
  `<0.35` / `0.35–0.65` / `>0.65`; aralık `<0.35` / `0.35–1.00` / `>1.00`.
- Hacim `rvol` = hacim / 20 günlük ortalama: `<0.8` / `0.8–1.2` / `≥1.2`.
- Temas: `|low − seviye| ≤ 0.35 ATR1d` veya bar seviyeyi kesiyor; ardışık temaslar tek temas; yeni temas
  için ≥2 gün ayrılma.
- Kırpma/sansür: hücrelerde n yazılır, n<30 olan hücrede yüzde verilmez ("yetersiz örneklem").
- Sembol yoğunlaşması: bir hücrenin %20'sinden fazlası tek sembolden gelirse not düşülür.

**2.9 Koşullandırma ve aile (genel) testleri — v2.1 eki**
- Bir koşulun (hacim, mum anatomisi, kapanış konumu…) yön verdiği iddia **yalnız** iki yolla test edilir:
  **(a)** senaryo-stratifiye Mantel–Haenszel (her senaryo kendi içinde), **(b)** senaryoların **aile** olarak
  havuzlanması. **Havuzlanmış tek değişkenli tablo karar veremez** (senaryo karışımı = kompozisyon etkisi).
- Her ölçümde **kompozisyon kontrolü** zorunlu: koşul ile senaryo arasındaki ilişki (Cramér's V) raporlanır;
  V ≥ 0,30 ise havuz etkisi şüpheli sayılır ve karar için kullanılamaz.
- Aile havuzu **tek test** sayılır; Bonferroni **aile sayısına** göre uygulanır.
- Bir filtrenin değeri **elenen tarafla birlikte** raporlanır: elenen taraf taban gürültüsünde kalıyorsa
  filtre "kapı", sinyali koruyorsa "süs"tür.
- Aynı filtre **tüm** olaylara da uygulanıp gösterilir; genel havuzda etki eklemiyorsa filtre yalnız kendi
  ailesi içinde geçerlidir, tek başına sinyal sayılamaz.

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
