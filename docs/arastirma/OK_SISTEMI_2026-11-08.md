# OK SİSTEMİ — kural kataloğu ve sembol sembol denetim

**Tarih:** 2026-11-08 · **Kapsam:** 50 sembol, 4s barlar (1.079 bar/sembol), **1.315 ok**
**Amaç:** "Bu ok buraya hangi sistematikten dolayı konmuş?" sorusunu her ok için cevaplamak;
gereksiz tekrarı ve anlamsız oku ayırmak. **Ok çeşitlendirmesi yapılmadı**, yeni ok türü eklenmedi.

---

## 1. Şu an ok koyan 5 kural (kodla birebir)

Kaynak: `domain_engines/stabil/signals.py` (`evaluate_bar_behaviors`).
Direnç tarafı (`resistance.py`) bunun **birebir aynası**dır (aynı eşikler, aynı soğuma).

| ID | Ok | Ne zaman konuyor | Eşikler | Kod |
|---|---|---|---|---|
| **K1** | ▲ | Destek altına sarktıktan sonra **gövdeyle desteğin üstüne kapanış** | önceki ihlal ≤ 1,50 ATR · gövde ≥ 0,32 · kapanış poz. ≥ 0,65 · çizgiye uzaklık ≥ +0,05 ATR · hacim onayı | `close_reclaim` |
| **K2** | ▲ | Yukarıdayken **fitille altı süpürüp** aynı mumda üstüne dönüş | fitil −1,20…−0,08 ATR · gövde ≥ 0,35 · kapanış poz. ≥ 0,68 · hacim onayı | `intrabar_sweep_reclaim` |
| **M1** | ▲ | **Oturmuş yatay zeminden** güçlü gövdeyle kopuş | çizgi ≥ 20 gün sabit · uzaklık 0,15–1,80 ATR · gövde ≥ 0,35 · kapanış poz. ≥ 0,65 · (hacim ≥ 1,10 **veya** gövde ≥ 0,50) · temas < 3 · 3 bar soğuma | `long_base_breakout` |
| **M2** | ▲ | **Destek yukarı basamak yaparken** gelen güçlü yukarı mum | kademe yukarı · uzaklık 0,10–1,60 ATR · diğer eşikler M1 ile aynı | `upward_rebase_momentum` |
| **U1** | ▼ | **Dikey/kademeli destek üzerinde yukarı deneme** → ▲ bastırılır, yerine yapı uyarısı | dikey rejim (kademe yukarı/aşağı, ya da çizgi o bar yer değiştirdi) **ve** (geri alım / zayıf geri alım / momentum / alttan temas) | `vertical_attempt_kind` |

### Bozulmayacak kural (senin "bozma" dediğin)

> **Destek dikeyken fiyat yukarı çıktıysa ve aşağıda başka destek yoksa ▲ konmaz.**
> Kodda `vertical_support` bunu fail-closed yapıyor: dikey rejimde K1/K2/M1/M2 hepsi bastırılır,
> yerine **yalnız yapı uyarısı** (▼) kalır. Denetimde bu durumda üretilmiş **tek bir ▲ bile yok (0 vaka)** →
> kural bugün **çalışıyor**. Bu turda **değiştirilmedi**.

---

## 2. Sembol sembol denetim — 50 sembol

| Ölçüm | Sonuç |
|---|---|
| Toplam ok | **1.315** (sembol başına ortalama 26,3) |
| Bar başına ok oranı | **%2,49** |
| Ok dağılımı | **U1 ▼ 1.176 (%89)** · K1 ▲ 74 · K2 ▲ 44 · M2 ▲ 12 · M1 ▲ 9 |
| Gerçek sinyal (▲) toplamı | **139 (%11)** |
| Denetim kararı | **ŞÜPHELİ 1.041 (%79)** · SAĞLAM 168 · ZAYIF 106 |
| Bayraklar | kademe aşağı 741 · **tekrar 498** · sessiz hacim 366 · altı boş 331 · gövdesiz 256 · uzak 189 · yorgun 50 |

**Tek cümle:** grafikte görünen okların **onda dokuzu ▲ sinyal değil, aynı ▼ yapı uyarısının tekrarı**.

---

## 3. "Neden bu ok var?" — gerçek örnekler

**a) Temiz ▲ (savunulabilir):** `AKBNK 2026-03-23 17:30` → **K1**
kapanış çizginin +1,41 ATR üstünde, gövde 1,83 ATR, hacim 5,24× → "destek altına sarktı, gövdeyle üstüne
döndü" tarifine tam uyuyor. Denetim: **SAĞLAM**.

**b) Zayıf ▲ (eşiği geçiyor ama kanıt zayıf):** `AGROT 2026-02-20 13:30` → **M2**, hacim 0,57× → **sessiz gün**.
rev10 ölçümü "sessiz günde sinyal yok" diyor. Denetim: **ZAYIF**.

**c) Anlamsız ▼ (asıl problem):** `AEFES 2025-09-02 17:30` → **U1**
kapanış çizginin **−2,20 ATR altında**, gövde −1,29 ATR (sert düşüş mumu), hacim 5,9×.
Bu barda "dikey destek, **yukarı deneme**" uyarısı konmuş. Yukarı deneme yok — fiyat çizginin çok altında.
**Sebep:** `vertical_attempt_kind`, "zayıf geri alım / alttan temas" bayraklarından biri varsa, fiyatın
nerede kapandığına bakmadan uyarı basıyor.

**d) Tekrar:** `ALARK 2025-05-22` günü **3 ayrı ▼**, `DENGE 2026-08-14` **3 ayrı ▼**; 50 sembolde
**498 ok** kendinden önceki okla 5 bar içinde. K1/K2/M1/M2'de soğuma var; **U1'de hiç yok**.

---

## 4. Üç problem ve ölçülmüş düzeltme seçenekleri

Kaydedilmiş davranışlar üzerinde simülasyon (üretim kodu değiştirilmeden):

| Düzeltme | Silinen ok | Kalan | Azalma |
|---|---|---|---|
| Sadece "fiyat çizginin altındaysa uyarı yok" | 401 | 914 | %30 |
| Sadece 6 bar (≈1 gün) soğuma | 459 | 856 | %35 |
| Sadece 12 bar (≈2 gün) soğuma | 593 | 722 | %45 |
| Sadece "günde en fazla 1 uyarı" | 194 | 1.121 | %15 |
| **Fiyat-altı + günde 1 uyarı (öneri)** | **513** | **802** | **%39** |
| Fiyat-altı + 12 bar soğuma | 752 | 563 | %57 |

**Kritik kontrol:** bu düzeltmelerin hiçbiri **▲ sinyallerine dokunmuyor** — 139 sinyal okunun tamamı
korunuyor (U1 dışındaki oklardan "fiyat altında" olan: **0**).

**Öneri (kontrollü seçenek):** iki küçük kapı —
1. **U1 yalnızca gerçek yukarı denemede:** kapanış çizginin **−0,10 ATR** altındaysa ▼ konmaz ("yukarı deneme" değil).
2. **U1 günde en fazla 1 kez:** aynı gün ikinci uyarı basılmaz (K1/K2/M1/M2'nin 3 barlık soğuması gibi).

Etkisi: **513 ok (%39) azalır**, ▲ tarafı hiç etkilenmez, "dikey bastırma" kuralı aynen kalır.

---

## 5. Neyi DEĞİŞTİRMİYORUZ

- **Dikey destekte ▲ bastırma** kuralı (senin "bozma" dediğin) aynen duruyor.
- **K1/K2/M1/M2 eşikleri** aynı; ok üretim mantığı değişmiyor.
- **Ok çeşitlendirmesi yok** — yeni ok türü eklenmiyor, mevcutlar kaldırılmıyor.
- **Direnç tarafı** (ayna) bu turda ayrıca ölçülmedi; eşikler birebir aynı olduğu için aynı problemin
  orada da olması beklenir → sıradaki adım.

---

## 6. Senden onay bekleyen

1. Öneriyi uygulayalım mı? (**fiyat-altı kapısı + günde 1 uyarı**) — uygulandığında `signals.py` içinde
   2 küçük değişiklik olur, ardından `test_stabil_vertical_policy`, `test_stabil_momentum_arrow`,
   `test_stabil_resistance_engine` çalıştırılır ve denetim aynı 50 sembolde tekrarlanır.
2. Soğuma süresi 12 bar (%57 azalma) daha mı doğru, yoksa %39'luk kontrollü sürüm mü?
3. Direnç tarafı (▼ aynası) için aynı denetimi çalıştırayım mı?

**Dosyalar:** `ok_denetimi_2026_11_08.csv` (1.315 ok, kural + gerekçe + bayrak),
`ok_ozet_sembol_2026_11_08.csv` (50 sembol), kod: `research/stabil_ok_denetimi.py`.
