# Faz 6 — Giriş Teyidi Kuralları (Önceden Kayıtlı)

**Tarih:** 2026-11-10 · **Durum:** koşudan ÖNCE yazıldı (anti-lookahead)
**Bağlantı:** [5 Fazlı Plan](5_FAZLI_KODLAMA_PLANI_2026-11-09.md) · [Giriş-Çıkış İncelemesi](../arastirma/GOLGE_ZINCIR_GIRIS_CIKIS_INCELEMESI_2026-11-10.md)

## 0. Sorun (neden Faz 6)

Tam koşu + inceleme (2.771 plan) gösterdi:

- **Erken giriş %30,5** (düşüş bitmeden dalmak) → bu kesimin **%83'ü stop**;
  **951 stopun %90'ı** erken+yüksek kesimden.
- **Yüksekten kovalama %7,2** (zirveye yakın + momentumlu giriş) → **%79 stop**.
- Kök neden: sistem **"desteğe yaklaştık mı"** sorusunu soruyor,
  **"destek tuttu mu / düşüş bitti mi"** sorusunu sormuyor (buna "boşluk" deniyor).

## 1. Reddedilen tasarım — BOS/CHOCH giriş şartı (ders)

**Karar: BOS/CHOCH (yapı bozulması) giriş şartı YAPILMAYACAK.**

Gerekçe: BOS/CHOCH erken gelmez — gerçek kanıt ancak dönüş olduktan sonra
oluşur. Girişe şart yapılsaydı işlem sayısı **yılda30-40'a** düşerdi
(100+ hissede bile), sistem fiilen dururdu. Mevcut sistem "iyi bir konumda";
aşırı filtre = ölüm.

Kanıt: tek "taze karşıt MS" uyarısı bile şimdiden868 geometrik tetiği
BEKLE'ye alıyor; UYGUN zaten "taze karşıt yok" şartını taşıyor (veto olarak
doğru yerde — RET/BEKLE). **BOS/CHOCH veto olarak kalır, giriş onayı olmaz.**

## 2. Kural seti (orta sertlik — pre-registration)

Yeni modül: `senaryo/giris_teyidi.py` → `giris_teyidi(...)` (saf fonksiyon).
Mevcut kapılar (G5 bant ∩ tepki onayı, TYR UYGUN, geometri,20 bar boşluk)
**aynen kalır**; üzerine **devamlılık teyidi** eklenir.

Sabitler (koştan önce yazıldı):

| Sabit | Değer | Anlamı |
|---|---|---|
| `PENCERE` | **3 bar** | devamlılık penceresi |
| `ZEMIN_ALTIN_KAPANIS_YASAK` | evet | son3 barda zemin altına **kapanış** olmayacak |
| `YUKSEK_DIP_GEREKLİ` | evet | giriş barının low'u, son2 bardaki dibin **altında yeni dip yapmayacak** |
| `MOM3_TAVANI_ATR` | **0,50** | girişten önceki3 barda koşu >0,5 ATR ise kovalamadır, giriş yok |

- **Zemin hattı:** `max(destek, band_lo)` — stop ile aynı tez çizgisi
  (destek yoksa band_lo).
- Plan = mevcut koşullar ∧ **giriş teyidi**. Teyit yalnız **planı** etkiler;
  **tetik/kör baz değişmez** (K2 karşılaştırmasının temeli korunur).
- **K1–K6 kapı eşikleri DEĞİŞMEZ** (Faz 5 belgesi §4). K0 (min. plan
  sayısı) **eklenmeyecek** (karar: gerek yok).

## 3. Başarı ölçütleri (koşudan önce)

1. **Tutunma (retention):** teyitli plan / (teyitli plan + teyit reddi)
   ≥ **%40** (orta sertlik zemini). altında ise koşu "çok kapalı" raporlanır;
   **eşik değişmez**, yeni belge gerekir.
2. **Yön:** erken giriş kvadrantı düşmeli, yüksekten kvadrantı düşmeli;
   iyi zamanlama payı artmalı (aynı inceleme betiği ile).
3. Kapı K1–K6 aynı eşiklerle tekrar değerlendirilir.

## 4. Koşu kapsamı

- **~40 dakika** (tam6 saat değil): `python3 research/golge_zincir.py --limit 120`
  → ilk120 sembol ×4 TF ≈480 seri (tam koşunun %68'i).
- Ardından: `golge_olcum.py` → `golge_kapi.py` → geniş inceleme
  (önceki giriş/çıkış kalitesi + **kaçan tetiklerin dipte/tepeden konumu**).

## 5. Bilinen riskler / notlar

- `YUKSEK_DIP_GEREKLİ` bazı iyi çekiç (hammer) girişlerini de kesebilir —
  tutunma ölçütü %40 ile dengelenir.
- Zemin altı kapanış kuralı, kırılıp geri dönen (bull-trap) girişleri de keser
  — bilinçli muhafazakârlık.
- Teyit penceresi3 bar: uzun TF'te (1d)3 bar =3 gün — kabul edildi (basitlik).

---

## Revize 1 — kalibrasyon sonrası (2026-11-10, ana koşudan ÖNCE)

30 sembol kalibrasyon koşusu + çevrimdışı varyant süpürmesi (939 aday,
`research/faz6_kalibrasyon.py`) **V1'in (ilk3 kural) işe yaramadığını** gösterdi:

| varyant | ret% | stop% | bek | iyi | erken | yüksekten |
|---|---|---|---|---|---|---|
| kapı yok | 100 | 36,7 | +0,326 | 48,6 | 33,2 | 7,6 |
| **V1 (ilk hâli)** | 39,1 | 35,4 | +0,293 | 52,6 | 32,2 | 8,7 |
| T10 (test10) | 36,3 | **34,9** | +0,381 | 52,8 | **29,6** | 7,3 |
| T1005 | 39,9 | 34,9 | +0,334 | 52,3 | 30,7 | 7,5 |
| **T1505 (SEÇİLDİ)** | **41,9** | 35,9 | **+0,365** | **55,5** | 33,8 | **4,6** |
| T1075 | 44,1 | 35,3 | +0,301 | 51,2 | 31,9 | 7,2 |

**Püf noktası (V1 neden geri tepti):** "yeni dip yok" kuralı asıl **yıkanma
dipini** (desteğin test edilip tutulduğu an — çekiç/kırılış) kesiyor, henüz
test edilmemiş düşüşleri bırakıyordu → kapı, iyi girişleri (bek +0,35)
elemiş, zayıfları tutmuştu (retro-korelatif). Kullanıcı sorusu olan
"destek tuttu mu" **test+hold** ile ölçülür: son15 barda zemin test
edilmiş (low ≤ zemin+0,5 ATR), kapanışlar zemin üstü kalmış, giriş
pencerenin dibinden geri dönmüş.

**Revize kural (tek,3 koşul):**
1. `min(low[i-14..i]) ≤ zemin + 0,5·ATR` — test edilmiş
2. `close[j] ≥ zemin ∀j ∈ [i-14..i]` — zemin altına kapanış yok (intraday
   delik serbest)
3. `close[i] > min(close[i-14..i])` — pencere dibinden geri dönüldü

Mom3/zirve kapakları **elendi** (sweep'te bek'i düşürdü: T1005M +0,298 <
T1005 +0,334). Yeni-dip kuralı **elendi** (yukarıda). Zemin hattı aynen:
`max(destek, band_lo)`.

**Kalibrasyon sızıntısını önleme:** ilk30 sembol kalibrasyonda kullanıldı —
**ana koşu `--semboller` ile ilk30 DIŞINDA120 sembol** (holdout). K1–K6,
boşluk20, tetik/kör baz değişmedi. Zemin40% korundu (T1505 = %41,9;
mutlak hacim ≈2000+ plan/yıl — aç bırakma riski yok).
