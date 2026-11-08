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
| **K1** | ▲ | Destek altına sarktıktan sonra **gövdeyle desteğin üstüne kapanış** | önceki ihlal ≤ 1,50 ATR · gövde ≥ 0,32 · kapanış poz. ≥ 0,65 · çizgiye uzaklık ≥ +0,05 ATR · **hacim şartı yok** (§9) | `close_reclaim` |
| **K2** | ▲ | Yukarıdayken **fitille altı süpürüp** aynı mumda üstüne dönüş | fitil −1,20…−0,08 ATR · gövde ≥ 0,35 · kapanış poz. ≥ 0,68 · **hacim şartı yok** (§9) | `intrabar_sweep_reclaim` |
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

---

## 7. UYGULANAN DÜZELTME (2026-11-08)

Üç kapı eklendi; **eşikler gevşetilmedi, ok üretim mantığı değişmedi**.

| # | Kapı | Yer | Ne yapıyor |
|---|---|---|---|
| 1 | **Mesafe** `\|d\| ≤ 1,80 ATR` | `signals.py` / `resistance.py` (ayna) | Çizgiden 1,8 ATR'den uzakta ok basılmaz ("destekle ilişkisi yok" şikâyeti) |
| 2 | **Soğuma** 3 bar | aynı | Yalnız **zayıf** denemelerde (`weak_reclaim`, `touch_from_below`, `weak_return`, `approach_from_above`). Bastırılmış **güçlü** aday (close_reclaim / sweep / momentum) her zaman yazılır — "dikey bastırma" bilgisi kaybolmaz |
| 3 | **Görsel** | `render.py` + `panels.py` | Direnç yapı uyarısı artık **▲ değil ◇** ve mumun **üstünde**; lejant: "◇ direnç yapı uyarısı" |

### Ölçüm — düzeltme öncesi / sonrası

**Günlük grafik (49 sembol, ~500 bar/sembol):**

| Ölçüm | Önce | Sonra |
|---|---|---|
| Toplam ok | 1.243 | **968 (−%22)** |
| **3+ gün üst üste uyarı** | **46 vaka** | **0** |
| **Çizgiden uzak ok** | 102 | **0** |
| Tekrar bayrağı | 467 | 257 |
| ▲ sinyalleri | 237 | 231 (yalnız uzakta olanlar düştü) |

**4 saatlik (50 sembol, 1.079 bar/sembol):** 1.315 → **932 ok (−%29)**; dikey uyarı 1.176 → 800;
▲ 139 → 132; şüpheli 1.041 → 663; tekrar 498 → 256.

### Test
`test_stabil_vertical_policy`, `test_stabil_resistance_engine` (parite dahil), `test_stabil_arrow_context_replay`
(AEFES 17:30 gerçek vakası), `test_stabil_momentum_arrow`, `test_stabil_resistance_chart_render`,
`test_stabil_resistance_delivery_e2e` → **tamamı geçiyor**.

### Görseller (`docs/gorseller/ok_duzeltme_2026_11_08/`)
- `karsilastirma_AGHOL.png` — 4 gün üst üste uyarı (önce 7 → sonra 4)
- `karsilastirma_AGROT.png` — 3 ATR uzakta uyarı (önce 8 → sonra 6, uzaktaki tamamen silindi)
- `karsilastirma_AKSEN.png` — tekrar (önce 4 → sonra 2)
- `*_before.png` / `*_after.png` — tam kareler

### Kalan (bilinçli)
- `KADEME_ASAGI` bayrağı hâlâ en büyük grup (462): bu bir **hata değil**, destek aşağı kademedeyken
  üretilen yapı uyarısıdır ve ▲ zaten bastırılıyor. Sinyal değeri ayrı ölçülüyor (§0.10).
- Direnç tarafı görselleri bu arşivde üretilemedi (o rol aktif değil); ayna kod ve testler kapsıyor.

---

## 8. İKİ KATMAN BİRLİKTE + AYRIŞAN RENK + EŞİTLENMİŞ OK SÖZLÜĞÜ (2026-11-08)

### 8.1 Direnç neden hiç görünmüyordu
Canlı `/grafik` yolu iki katmanı da hesaplıyor (`grafik_uret`: `stabil` + `stabil_direnc`), ama
**replay/örnek görsel yolu** (`research/replay_egitim._soru_goruntusu`) yalnız destek motorunu
çalıştırıyordu → ürettiğim örnek görsellerde direnç katmanı **hiç yoktu**. Hata görselde değil,
görseli üreten yoldaydı.
→ Yeni üretici `research/stabil_ok_ornek_gorseller.py` her karede **ikisini birlikte** hesaplıyor;
10 görselin 10'unda da `destek=True, direnç=True` doğrulandı.

### 8.2 Renk: artık renk KATMANI söylüyor

| Katman | Tutuyor | Kırıldı / ters taraf |
|---|---|---|
| **Destek** | yeşil `#2cc98d` | koyu yeşil `#1f9e73` |
| **Direnç** | turuncu `#f5a05a` | koyu turuncu `#c2410c` |

Önce ikisi de aynı yeşil/kırmızı paleti kullanıyordu → "direnç mi destek mi" ayırt edilemiyordu.
Artık **yeşil = destek, turuncu = direnç**; "tutuyor mu, kırıldı mı" bilgisi aynı rengin iki tonunda.
Renk körü modunda mavi/turuncu ikilisi korunuyor.

### 8.3 Eşitlenmiş ok sözlüğü (iki taraf aynı dil)

| Olay | Destek tarafı | Direnç tarafı |
|---|---|---|
| Geri alım / dönüş | **▲** dolu (yeşil) | **▼** dolu (turuncu) |
| Momentum | **▲** içi boş (yeşil) | **▼** içi boş (turuncu) |
| Yapı uyarısı | **◇** içi boş (yeşil) | **◇** içi boş (turuncu) |

Destek tarafındaki yapı uyarısı eskiden **▼** (dolu kırmızı) çiziliyordu — direnç dönüşüyle birebir
aynı görünüyordu. Artık iki tarafta da **◇**; ayırt eden şey renk ve konum.

### 8.4 Görseller — `docs/gorseller/ok_duzeltme_2026_11_08/` (10 adet, hepsinde iki katman)

Sayılar §9 (hacim) ve §10 (◇ seyreltme) değişikliklerinden **sonraki** kodla üretilmiştir.
Biçim: **dolu** (olay) · *içi boş* (momentum) · ◇ (yapı uyarısı).

| Dosya | Sembol / gün | Destek: dolu ▲ · içi boş ▲ · ◇ | Direnç: dolu ▼ · içi boş ▼ · ◇ |
|---|---|---|---|
| `ikikatman_aefes_uzak_uyari.png` | AEFES 19.09.2025 | 0 · 0 · 2 | 0 · 0 · 3 |
| `ikikatman_aghol_ust_uste.png` | AGHOL 01.04.2025 | **3** · 0 · 2 | 1 · 1 · 0 |
| `ikikatman_agrot_uc_atr.png` | AGROT 28.03.2025 | 0 · 0 · 2 | 1 · 1 · 0 |
| `ikikatman_aksen_tekrar.png` | AKSEN 06.03.2026 | 0 · 0 · 1 | 0 · 1 · 0 |
| `ikikatman_sise_kademe.png` | SISE 02.10.2026 | 2 · 0 · 2 | 0 · 0 · 1 |
| `ikikatman_thyao_gun_ici.png` | THYAO 21.09.2026 | 2 · 0 · 1 | 0 · 0 · 0 |
| `ikikatman_cemas_yogun.png` | CEMAS 06.08.2026 | 1 · 0 · 1 | 1 · 0 · 1 |
| `ikikatman_alark_bes_bar.png` | ALARK 22.05.2025 | 0 · 0 · 3 | 0 · 1 · 2 |
| `ikikatman_garan_dikey.png` | GARAN 21.09.2026 | 0 · **2** · 1 | 4 · 0 · 2 |
| `ikikatman_akbnk_geri_alim.png` | AKBNK 23.03.2026 | 0 · 0 · 1 | 2 · 0 · 2 |

Ayrıca önce/sonra karşılaştırmaları: `karsilastirma_AGHOL.png`, `karsilastirma_AGROT.png`,
`karsilastirma_AKSEN.png` (§7).

### 8.5 Test
`test_stabil_resistance_chart_render` (7), `test_stabil_resistance_chart_bridge`,
`test_stabil_resistance_chart_snapshot`, `test_stabil_support_resistance_compare`, `test_grafik_gorsel4`,
`test_grafik_gorsel_kalite` → **73 test geçiyor**.

---

## 9. HACİM ŞARTI KALDIRILDI — yalnız DOLU oklarda (2026-11-08, kullanıcı kararı)

### 9.1 Karar
- **Dolu ▲ (destek geri alımı) ve dolu ▼ (direnç dönüşü)** artık hacim şartı aramıyor.
- **Momentum (içi boş ▲/▼) AYNEN kaldı** — orada hâlâ `hacim ≥1,10×` **veya** `gövde ≥0,50 ATR`.
- ◇ yapı uyarısı değişmedi.

### 9.2 Gerekçe (rev10 replay, ölçülmüş)
- Havuzda "hacim yüksek" anlamlı **göründü** (DOWN lift +4,9, p=0,0007) ama senaryo-stratifiye
  Mantel–Haenszel testinde **kayboldu**: OR 0,82 (p=0,020) → **0,93 (p=0,55)**; işaret testi doğrulamada
  **3/6** (p=0,66). Havuzdaki fark kompozisyondan geliyordu (Cramér's V 0,383).
- **Yukarı tarafta hacim hiç fark yaratmadı:** UP %52,0 → %50,5. Yani hacim, ▲'yı doğru yapan şey değildi.
- Hacmin işe yaradığı tek yer `▼` ailesiydi (`rvol ≥0,8` → DOWN %52,9 → %56,9) ve o hâlâ **aday**, canlı ok değil.

### 9.3 Kod
| Dosya | Ne değişti |
|---|---|
| `domain_engines/stabil/signals.py` | `vol_ok_close` / `vol_ok_sweep` → `True` (K1/K2). Momentumun `hacim veya gövde` şartı dokunulmadı |
| `domain_engines/stabil/resistance.py` | `volume_ok_return` / `volume_ok_sweep` → `True` (ayna, dolu ▼) |

**Yan etki (bilinçli):** `is_index` gövde istisnası (endekslerde 0,38/0,40) bu blokla birlikte kalktı;
artık herkes için aynı anatomik kapılar geçerli (gövde ≥0,32/0,35 · kapanış poz. ≥0,65/0,68).
Endeks istisnası zaten **gevşetiyordu**; kalkması endeksi dezavantajlı bırakmıyor.

### 9.4 Ölçüm — önce / sonra (günlük, 50 sembol, 24.549 bar)

| Ölçüm | Önce | Sonra |
|---|---|---|
| **Dolu ▲** (K1+K2) | 180 | **195 (+15, %8,3)** |
| Momentum ▲ (M1+M2) | 51 | **51 (değişmedi)** |
| ◇ yapı uyarısı | 737 | **737 (değişmedi)** |
| Toplam ok | 968 | **983 (+%1,5)** |
| Sembol başına dolu ▲ | 3,6 | 3,9 |
| Hiç değişmeyen sembol | — | **36 / 50** |

**Direnç tarafı (30 sembol, ~14.600 bar):** dolu ▼ 159 → **174 (+15)** · momentum ▼ 38 → **38 (aynı)** · ◇ 377 → 378.

**Yeni gelen 15 ok nereden geldi?** Hepsi hacmi 1,0×'in **altında** olan günler (0,23–0,94×):
10'u `close_reclaim`, 5'i `intrabar_sweep_reclaim`; gövde 0,33–0,45 ATR, kapanış pozisyonu 0,70–1,00,
çizgiye mesafe 0,08–0,81 ATR. Mesafe (`≤1,80 ATR`) ve soğuma kapıları aynen geçerli → **uzaktan ok gelmedi,
art arda ok oluşmadı**. "Hacim kalkarsa spam olur" korkusu bu kütlede **doğrulanmadı**.

### 9.5 Görseller — `docs/gorseller/ok_hacim_kapisi_2026_11_08/`
5 sembolde **aynı kare, iki kod hâli**:

| Sembol / gün | Ne görünüyor | Dosya |
|---|---|---|
| AGHOL 16.01.2025 | dolu ▲ 1 → **2** | `karsilastirma_aghol_geri_alim.png` |
| ALARK 14.07.2026 | dolu ▲ 1 → **2** | `karsilastirma_alark_geri_alim.png` |
| CEMTS 25.03.2025 | dolu ▲ 2 → **3** | `karsilastirma_cemts_geri_alim.png` |
| AEFES 30.12.2025 | dolu ▲ 1 → **2** (süpürme) | `karsilastirma_aefes_supurme.png` |
| DOCO 17.03.2026 | dolu ▲ 2 → **3**, dolu ▼ 0 → **1** | `karsilastirma_doco_geri_alim.png` |

Tam kareler: `hacim_once_*.png` (eski kod, `HEAD` sürümü süreç içinde taklit edilir) ve
`hacim_sonra_*.png` (yeni kod). Üretici: `research/stabil_hacim_kapisi_gorseller.py`
(`once` · `sonra` · `karsilastir`).

### 9.6 Test
`test_stabil_resistance_engine` içindeki eski "endeks hacim istisnası" testi yeni davranışa çevrildi:
`test_zero_volume_no_longer_blocks_return_on_index_or_stock` (hacim 0 iken endeks de hisse de dönüş alır).
`test_stabil_resistance_engine` · `test_stabil_momentum_arrow` · `test_stabil_vertical_policy` ·
`test_stabil_arrow_context_replay` · `test_stabil_support_resistance_compare` ·
`test_stabil_resistance_chart_render` · `test_stabil_resistance_chart_bridge` · `test_stabil_resistance_replay`
→ **131 test geçiyor**.

---

## 10. ◇ YAPI UYARISI SEYRELTILDI (2026-11-08, kullanıcı kararı: 20 bar)

### 10.1 Sorun
Oklar temizlendikten sonra grafikte kalan kalabalığın kaynağı ok değildi: günlük 50 sembolde
**983 işaretin 737'si (%75) ◇** idi. Sembol başına 14,7 ◇, en yoğun sembolde 22.

### 10.2 Ayrım (ölçümden önce konuldu)
722 ◇'in **189'u güçlü** (bastırılmış gerçek aday: `close_reclaim` 60 · `intrabar_sweep_reclaim` 18 ·
`upward_rebase_momentum` 111), **548'i zayıf** (`touch_from_below` 516 · `weak_reclaim` 32).
Güçlü olanlar kullanıcının koruduğu kuralın taşıyıcısı — **onlara dokunulmadı**.

### 10.3 Uygulanan kural
`_DIKEY_UYARI_SOGUMA_BAR`: **3 → 20**. Soğuma yalnız **zayıf** denemelere uygulanır (mevcut mantık);
güçlü bastırılmış aday her zaman yazılır. ▲ / momentum / mesafe kapısı **hiç değişmedi**.

Ölçülen seçenekler (süzgeç, günlük 50 sembol, 737 ◇):

| Zayıf ◇ soğuma | Kalan ◇ | Silinen | Sembol başına | En yüksek |
|---|---|---|---|---|
| 3 bar (eski) | 737 | — | 14,7 | 22 |
| 10 bar | 591 | −%20 | 11,8 | 18 |
| **20 bar (seçilen)** | **484** | **−%34** | **9,7** | 15 |
| 30 bar | 432 | −%41 | 8,6 | 15 |
| 60 bar | 333 | −%55 | 6,7 | 11 |

Ayrıca "her ◇'e ara vermek" (güçlü dahil) −%42…−%59 veriyordu; **reddedildi** (korunan kuralın bilgisi kaybolur).

### 10.4 Ölçüm — önce / sonra (günlük, 50 sembol, 24.549 bar)

| Ölçüm | Önce | Sonra |
|---|---|---|
| ◇ yapı uyarısı | 737 | **486 (−%34)** |
| ◇ sembol başına (medyan) | 14,7 (15) | **9,7 (10)** |
| ◇ en yoğun sembol | 22 | **15** |
| **Dolu ▲** | 195 | **195 (değişmedi)** |
| Momentum ▲ | 51 | **51 (değişmedi)** |
| Toplam işaret | 983 | **732** |

**Direnç tarafı (30 sembol):** ◇ 378 → **294 (−%22)**, dolu ▼ 174 → **174**, momentum 38 → **38**.
(Simülasyon 484, üretim 486 — aradaki 2 fark, üretimde soğumanın döngü içinde uygulanmasından.)

### 10.5 Görseller — `docs/gorseller/ok_cizgi_seyreltme_2026_11_08/`
Aynı kare, iki kod hâli (▲ okları birebir aynı):

| Sembol / gün | ◇ önce → sonra | Dosya |
|---|---|---|
| ALARK 22.05.2025 | **7 → 3** | `karsilastirma_cizgi_alark_yogun.png` |
| AGROT 28.03.2025 | **6 → 2** | `karsilastirma_cizgi_agrot_uc_atr.png` |
| AGHOL 01.04.2025 | **4 → 2** | `karsilastirma_cizgi_aghol_ust_uste.png` |
| CEMAS 06.08.2026 | **3 → 1** | `karsilastirma_cizgi_cemas_yogun.png` |
| AEFES 19.09.2025 | 2 → 2 | `karsilastirma_cizgi_aefes_uzak_uyari.png` |

Tam kareler: `cizgi_once_*.png` / `cizgi_sonra_*.png`. Üretici:
`research/stabil_cizgi_seyreltme_gorseller.py` (`once` · `sonra` · `karsilastir`).

**Not:** `docs/gorseller/ok_hacim_kapisi_2026_11_08/` kareleri §9'un kendi kanıtıdır ve ◇ değişikliğinden
**önce** üretildi; orada yalnız ▲ farkı önemlidir, ◇ sayıları bugünkü koddan fazladır.

### 10.6 Test
`test_stabil_vertical_policy` · `test_stabil_momentum_arrow` · `test_stabil_resistance_engine` ·
`test_stabil_arrow_context_replay` · `test_stabil_support_resistance_compare` ·
`test_stabil_resistance_chart_render` · `test_stabil_resistance_chart_bridge` ·
`test_stabil_resistance_replay` → **131 test geçiyor**. §8'in 10 görseli yeni kodla yeniden üretildi,
§8.4 tablosu güncellendi.
