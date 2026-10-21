# Kolon Sözlüğü — ölçüm hattının ortak dili (v1)

> **Durum:** Yürürlükte · **Sürüm:** v1 · **Tarih:** 21 Ekim 2026
> **Kaynak:** `research/kayit.py`, `research/olcum.py`, `state/formation_schema.py`,
> `state/formation_history.py`, `patterns/lifecycle.py`, `domain_engines/market_structure/`
> **Kapsam:** `research/` ölçüm hattının ürettiği tüm tablolar + **formasyon tablosu (yeni, henüz kodlanmadı)**
> **Kapsam dışı:** canlı bot Telegram çıktısı, veritabanı şeması, Pine uyumu

Bu belge **kod değil sözleşmedir**. Amacı tek şey: bir kolon adı duyulduğunda
herkesin aynı şeyi anlaması. Bugüne kadar aynı büyüklük farklı tablolarda farklı
adlarla, aynı ad farklı anlamlarla yaşadı; bu belge o borcu kapatır.

**Yeniden adlandırma yapılmaz.** Aşağıdaki mevcut kolon adları **donmuştur** —
eski raporlarla karşılaştırılabilirlik buna bağlıdır. Ekleme serbesttir.

---

## 1. Yedi kural

| # | Kural | Neden |
|---|---|---|
| **K1** | Bir isim → bir anlam → bir birim | `max_yaklasma_atr` ile `deneme_bar_025` aynı cümlede kullanılabilsin diye |
| **K2** | Defter alanı = kolon adı | Tanığa (history JSON) geri iz sürülebilmesi için; `frozen_*` asla yeniden adlandırılmaz |
| **K3** | Eşik ölçümden **önce** sabit | Sonradan eşik seçmek sonucu üretmek demektir. Eşikler `ESIK_IZGARA`, `DENEME_ESIKLERI`, `YUKSEKLIK_KOVALARI` sabitlerinde |
| **K4** | `null` ≠ `0` ≠ `False` | Üç ayrı olgu: ölçülmedi / ölçüldü-sıfır / ölçüldü-hayır |
| **K5** | Sansür görünür | Pencere yetmediyse değer `null`, sebep `sansur*` kolonunda |
| **K6** | Türetilmiş kolon hamın yerine geçmez | İkisi de yazılır; türetilmiş kolon formülü docstring'de taşır |
| **K7** | Ekleme serbest, yeniden adlandırma yasak | v1 kolonları donduruldu |

**K3'ün pratik sonucu:** yeni bir eşik ızgarası eklenirse `config_hash` değişmeli.
`_ANAHTARLAR` (`research/kayit.py:83`) listesine eklenmezse eski ve yeni satırlar
sessizce aynı havuzda karışır — bu, hattın en tehlikeli sessiz hatasıdır.

---

## 2. `n` nedir — satır birimi sözlüğü

Her cevap kartı `n` yazar. **`n` tablolar arasında toplanmaz**; her tablo kendi
birimini sayar. Bu, hattaki en sık yapılan istatistik hatasının önündeki tek engeldir.

| Tablo | Satır birimi | `n` ne sayar | Tipik satır |
|---|---|---|---|
| `zone` | zone | OB + FVG zone sayısı | 176 × 4 × ~? |
| `dokunus` | temas **epizodu** | zone'un kaçıncı kez temas aldığı | 994k (tam koşu) |
| `swing` | swing **× rol aralığı** | aynı swing PH rolünü 2 kez alırsa 2 satır | ~? |
| `event` | MS olayı (BOS/CHOCH/sweep) | onaylanmış olay sayısı | ~? |
| `meta` | **seri** (sembol × TF) | 704 | 704 |
| `frm` *(yeni)* | formasyon | doğumdan ölüme bir formasyon | ~? |
| `frm_olay` *(yeni)* | formasyon olayı | merdiven basamağı | ~? |

**Tuzak:** `dokunus` satırı "temaş başına"dır, "bar başına" değil. Bir epizot 9 bar
sürse bile **1** satırdır. Bu yüzden "temas süresi" sorusu `dokunus_bar_sayisi`
kolonundan okunur, satır sayılarak değil.

---

## 3. Adlandırma sözleşmesi

### 3.1 Önekler (hangi aileye ait)

| Önek | Anlam | Örnek |
|---|---|---|
| `yon_` | zone **yönünden** ölçüm (bullish → yukarı) | `yon_tepe_atr` |
| `kenar_` | **dokunulan kenardan** ölçüm (kullanıcı kuralı) | `kenar_tepe_atr` |
| `devam_` | MS olayı sonrası ölçüm | `devam_h12` |
| `repoh{10,12}_` | repo'nun eski pencere çıktısı (regresyon kanıtı) | `repoh12_next_same_zone_touch_in_window` |
| `vp_` | hacim katılımı (yan sütun) | `vp_rvol` |
| `native_` | **motorun kendi** terminal kararı (OB/FVG) | `native_terminal_category` |
| `frozen_` | kırılım anında dondurulmuş değer | `frozen_atr_at_break` |
| `frm_` | formasyon ölçümü (yeni tablo) | `frm_yakinlik_ust_fitil_atr` |
| `ms_` | market structure **motor durumu** (yalnız `meta`) | `ms_data_quality` |

### 3.2 Sonekler (hangi birim / hangi an)

| Sonek | Birim / anlam |
|---|---|
| `_atr` | ATR cinsinden (o barın ATR'si) |
| `_atr_dogum` | ATR cinsinden, **doğum barının** ATR'si (sabit cetvel) |
| `_fiyat` | ham fiyat |
| `_bar` | **bar sayısı** (int) |
| `_bar_time` | ISO 8601 zaman damgası (Europe/Istanbul) |
| `_index` | pencere içi sıra numarası — **kalıcı kimlik değil** |
| `_sayisi` | sayı (int) |
| `_no` | kaçıncı (1'den başlar) |
| `_var` | bool |
| `_sansur` | bool: pencere yetmedi |
| `_ratio` | oran (0–1), yüzde değil |
| `_sinifi` | ön-tanımlı metin sınıfı |
| `_kovasi` | ön-tanımlı sayısal kova |
| `_min` / `_max` | yaşam boyu en küçük / en büyük |
| `_ilk` / `_son` | ilk / son görülme |
| `_gecikme_bar` | bir olaydan kaç bar **sonra** (çapa = doğum) |

### 3.3 Dil ve biçim

- **Kolon adları ASCII Türkçe**: `ı→i`, `ş→s`, `ğ→g`, `ü→u`, `ö→o`, `ç→c`. Kod
  içinde ve CSV başlığında aksan yok (Excel/araç uyumu).
- **Değerler aksanlı olabilir**: `nötr`, `ölçülemedi`. Ama **motor sabitleri** stopludur ve
  aksansız yazılır (`KIRILIM_TEYITLI`, `UST_KENAR`). Bir değerin kaynağı motor mu, rapor mu —
  bu ayrım korunur.
- **Birim adları İngilizce kısaltma**: `ATR`, `TF`. Çevrilmez.
- Kolon adı uzunluğu ≤ **45** karakter (okunabilirlik; pandas sınırı değil).
- `bar_time` her zaman **string**; `Timestamp` nesnesi asla tabloya yazılmaz.

---

## 4. Birim sözlüğü

| Birim | Tanım | Üretim yeri |
|---|---|---|
| **ATR** | 14 periyot Wilder ATR, **o barın** değeri | `calculate_atr(df, 14)` |
| **ATR (doğum)** | Formasyon/zone doğum barındaki ATR; ATR oynasa da **sabit kalır** | `_atr_at(atr, dogum)` |
| **bar** | Gözlem çerçevesinin bir mumu; 1h'de 1 saat | ham veri |
| **oran** | 0–1 arası kayan nokta; yüzde **değil** | `_ratio` |
| **yüzde** | Yalnız **rapor** katmanında (`research/rapor.py`); tabloda yok | `%…` |
| **zaman** | ISO 8601 string, Europe/Istanbul, saat dilimi eki ile | `_bar_time` |
| **fiyat** | Ham fiyat, 6 basamağa yuvarlı | `_yuvarla` |

**Yuvarlama:** tüm sayısal değerler `_yuvarla` ile **6 basamağa** yuvarlanır; `bool`,
`str` ve `None` olduğu gibi geçer. NaN/Inf → `None` (sessizce `0` yapılmaz).

**Neden iki ATR?** Trader "1 ATR yaklaştı" derken **bugünkü** ATR'yi kasteder (ana
kolon). Ama ATR oynadıkça sabit fiyat farklı ATR'ye denk gelir. `_atr_dogum` sürümü
sabit cetveldir ve sonucun ATR oynaklığına duyarlılığını test eder. İkisi çelişirse
bu bir **bulgudur**, hata değil.

---

## 5. Değer sözleşmesi — `null`, `0`, `False`

### 5.1 `null` üç farklı şey olabilir

| Durum | Nasıl anlaşılır | Örnek |
|---|---|---|
| Yapısal olarak yok | İlgili `*_var` kolonu `False` | `pole_quality=null` + `has_pole=False` |
| Ölçülmedi (veri yok) | `olculmedi` kolonu dolu | `olculmedi="referans_yok"` |
| Sansürlendi (pencere bitti) | `sansur=True` / `*_sansur=True` | `h12=null` + `h12_sansur=True` |

**K4 gereği** hiçbir eksik `0` ile doldurulmaz. Bir kolonun `null` oranı %5'i
geçiyorsa cevap kartı bunu **yazar**; sessiz ortalama alınmaz.

### 5.2 `False` ≠ `null` — üç değerli alanlar

`engelledi_{025,015,050}` **üç değerlidir**:

- `True` → pencere içinde seviye kırılmadı (direnç tuttu)
- `False` → kırıldı
- `null` → pencere veri sonuna takıldı; **karar verilemez**

"Henüz kırılmadı" ile "başarılı direnç" ayrımı budur. Bu alanı `astype(bool)` ile
sadeleştirmek veriyi bozar.

### 5.3 Ön-tanımlı sınıf değerleri (kapalı liste)

| Kolon | Olası değerler |
|---|---|
| `tepki_sinifi` / `yon_tepki_sinifi` / `kenar_tepki_sinifi` | `CALISTI`, `AZ`, `YOK`, `TERS`, `OLCULEMEDI` |
| `devamlilik_sinifi` | `CALISTI`, `AZ_DEVAM`, `DEVAM_YOK`, `TERS`, `OLCULEMEDI` |
| `yukseklik_kovasi` | `0-0.5`, `0.5-1`, `1-2`, `>=2`, `BILINMEYEN` |
| `dokunulan_kenar` | `UST_KENAR`, `ALT_KENAR`, `TUM_ZONE`, `ZONE_ICI`, `GECERSIZ` |
| `uyum` | `UYUMLU`, `UYUMSUZ` |
| `rol` | `PH`, `PL`, `SH`, `SL`, `WH`, `WL` |
| `rol_kapanis` | `DEVREDILDI`, `TEMIZLENDI`, `ROL_ATANMADI`, `VERI_SONU_SANSURLU` |
| `sonuc_durum` | `hedef`, `stop`, `nötr`, `bekliyor`, `ölçülemedi`, `kirilim_yok` |
| `fvg_durum` | motor durumu / `ATLANDI_TIMEFRAME` |
| `vp_data_quality` | `PARTICIPATION_*` (motor state'i) |

`TERS` önemli: fiyatın ölçüm yönünün **tersine** gitmesi "tepki yok" değildir.
Bu yüzden `YOK`'tan ayrı sınıftır ve raporda ayrı kovada durur.

---

## 6. Ortak kimlik kolonları

| Kolon | Birim | Tanım |
|---|---|---|
| `symbol` | metin | BIST kodu (`THYAO`) |
| `timeframe` | metin | `1h`, `2h`, `4h`, `1d` |
| `engine_version` | metin | `arastirma-olcum-v1` — hat sürümü |
| `config_hash` | 12 hex | Ölçüm sabitlerinin özeti; eşik değişirse değişir |

`config_hash` **filtre değil, damgadır**: iki farklı hash'li satır aynı tabloda
bulunursa analiz bölünür. Kart yazarken hash ve `engine_version` **yazılır**.

---

## 7. `zone` tablosu — OB ve FVG zone'ları

Satır birimi: **zone**. Sınırlar **doğum anında dondurulur**; sonradan değişen
ATR kullanılmaz.

| Kolon | Birim | Tanım | Not |
|---|---|---|---|
| `zone_id` | metin | Zone kimliği | `family` + üretim indeksi türevi |
| `family` | metin | `OB` / `FVG` | ⚠️ formasyon tablosunda **başka anlam** — bkz. §14 |
| `direction` | metin | `bullish` / `bearish` | |
| `beklenen_yon` | metin | Beklenen tepki yönü | `direction`'dan türetilmiş |
| `dogum_bar_time` | zaman | Zone'un oluştuğu bar | |
| `kullanilabilir_bar_time` | zaman | Karar için hazır olduğu bar | OB'de gecikme vardır |
| `dogum_index` | index | Pencere içi sıra | kalıcı değil |
| `zone_lower` / `zone_upper` | fiyat | Dondurulmuş sınırlar | |
| `yukseklik_fiyat` | fiyat | `zone_upper - zone_lower` | |
| `atr_at_birth` | fiyat | Doğum barındaki ATR | |
| `yukseklik_atr` | ATR | `yukseklik_fiyat / atr_at_birth` | Zone boyutu sorusunun ekseni |
| `yukseklik_kovasi` | sınıf | Ön-tanımlı kova | |
| `native_terminal_category` | metin | Motorun terminal sınıfı | |
| `native_terminal_reason` | metin | Motorun gerekçesi | |
| `native_terminal_state` | metin | Motorun terminal state'i | |
| `terminal_bar_time` / `terminal_index` | zaman / index | Zone'un öldüğü an | |
| `native_price_violation` | bool | Fiyat zone'u ihlal etti mi | OB'de `native_full_fill` yerine **bunu** kullan |
| `native_full_fill` | bool | Tam dolum | OB'de yapısal olarak `False`; yanıltıcı |
| `native_fill_ratio` | oran | Terminalde dolum oranı | Zone düzeyinde; temas başına değil |
| `temas_bar_sayisi` | **epizot** | Temas **epizodu** sayısı | ⚠️ adı "bar" diyor, epizot sayıyor — donmuş hata |
| `temas_var` | bool | En az bir temas | |
| `omur_bar` | bar | `terminal_index - kullanilabilir` | |
| `sansur` | bool | Terminal yok = hâlâ açık | |
| `engine_version`, `config_hash` | metin | Damga | |

**Kritik:** `temas_var=False` **"temas yok"** demektir, "ölçülmedi" değil. Zone
gözlenen pencerede hiç temas almamışsa bu bir **bulgudur** (FVG'nin %21–28'i).

---

## 8. `dokunus` tablosu — temas epizotları

Satır birimi: **epizod**. Çapa = epizodun **ilk** barı (`dokunus_baslangic_bar_time`).
Ölçüm çapadan **sonraki** barlarda yapılır — bu, anti-lookahead sözleşmesidir.

### 8.1 Taban kolonlar

| Kolon | Birim | Tanım |
|---|---|---|
| `episode_id` | metin | Epizot kimliği |
| `zone_id`, `symbol`, `timeframe`, `family`, `direction`, `beklenen_yon` | — | Kimlik |
| `dokunus_no` | sayı | Bu zone'daki **kaçıncı** temas (1, 2, 3…) |
| `dokunus_baslangic_bar_time` / `dokunus_bitis_bar_time` | zaman | Epizodun ilk/son barı |
| `dokunus_bar_sayisi` | bar | Epizodun sürdüğü bar sayısı |
| `sonraki_epizot_index` | index | Sonraki temasın başlangıcı |
| `arrival_side` | metin | Fiyatın hangi taraftan geldiği |
| `approach_direction` | metin | Yaklaşma yönü |
| `dokunulan_kenar` | sınıf | İlk temasta değen kenar (sonradan değişmez) |
| `kenar_olcum_yonu` | metin | `UP` / `DOWN` |
| `zone_lower` / `zone_upper` | fiyat | Zone sınırları |
| `atr_at_touch` | fiyat | Temas barındaki ATR |
| `yukseklik_atr`, `yukseklik_kovasi` | ATR / sınıf | Zone boyutu |
| `gozlenen_bar` | bar | Çapadan sonra gözlenen bar sayısı |
| `sansur_pencere` | bool | Gözlem penceresi yetmedi |
| `sansur_terminal` | bool | Zone terminali yok |
| `native_terminal_category` | metin | Motor terminal sınıfı |
| `native_price_violation`, `native_full_fill`, `terminal_dokunusta` | bool | Terminal olguları |
| `yon_tepki_sinifi` / `kenar_tepki_sinifi` | sınıf | Ön-tanımlı tepki sınıfı |

**İki ayrı sansür:** `sansur_pencere` (zaman yetmedi) ile `sansur_terminal` (zone
hâlâ açık, ölüm görülmedi) farklı şeylerdir. Bir kart ikisini ayrı raporlar.

### 8.2 Üretilen aileler

| Aile | Kolon sayısı | İçerik |
|---|---|---|
| `yon_*` | 30 | Zone yönünden ölçüm |
| `kenar_*` | 30–31 | Dokunulan kenardan ölçüm (+ gerekiyorsa `kenar_olculmedi`) |
| `vp_*` | 17 | Hacim (yan sütun — §12) |
| `repoh10_*` / `repoh12_*` | 8 + 8 | Eski pencere çıktısı (regresyon) |

**`yon_*` ve `kenar_*` aynı 30 anahtarı taşır:**

| Anahtar | Birim | Tanım |
|---|---|---|
| `tepe_atr` | ATR | 12 bar içindeki en büyük yönlü uzanım (**ana tepki ölçüsü**) |
| `tepe_bar` | bar | Tepeye kaç barda ulaşıldı |
| `dip_atr` | ATR | Aynı penceredeki en olumsuz uzanım |
| `h10`, `h12` | ATR | O ufuktaki tepe |
| `h10_kapanis_atr`, `h12_kapanis_atr` | ATR | Ufuk sonundaki kapanış uzanımı |
| `h10_decay`, `h12_decay` | oran | Tepenin ne kadarı geri verildi |
| `h10_sansur`, `h12_sansur` | bool | Ufuk tamamlanmadı |
| `uzun_tepe_atr`, `uzun_tepe_bar` | ATR / bar | 40 barlık uzun penceredeki tepe |
| `uzun_kapanis_atr`, `uzun_decay`, `uzun_sansur` | ATR / oran / bool | Kalıcılık |
| `pay_1`, `pay_3`, `pay_5` | oran | Tepenin ne kadarı ilk 1/3/5 barda geldi |
| `asim_{025,050,100,150,200}` | bool | Eşik aşıldı mı |
| `asim_{…}_bar` | bar | Eşiğe kaç barda ulaşıldı |
| `gozlenen_bar` | bar | Ölçülen bar sayısı |
| `olcum_yonu` (yalnız `kenar_`) | metin | `UP` / `DOWN` |
| `olculmedi` (yalnız `kenar_`) | metin | Yön belirlenemediyse gerekçe |

**`pay_5 ≈ 1` → tepki anlık; `pay_5` düşük + `uzun_tepe_atr` yüksek → yavaş ama kalıcı.**
Bu ayrım sadece bu kolon çiftinden çıkar.

**`asim_*` yön-ancored'dır**: `kenar_asim_100` "değdiği kenardan 1 ATR uzaklaştı" demek,
"1 ATR kâr" demek değil.

---

## 9. `swing` tablosu — PH/PL/SH/SL/WH/WL denemeleri

Satır birimi: **swing × rol aralığı**. Bir swing aynı rolü iki kez alırsa **iki satır**
olur; `structural_role_final` yanlıttır, `rol_*` kolonları gerçeği taşır.

### 9.1 Taban

| Kolon | Birim | Tanım |
|---|---|---|
| `scope` | metin | `EXTERNAL` / `INTERNAL` |
| `identity` | sayı | Swing kimliği (motor içi sayaç) |
| `side` | metin | `HIGH` / `LOW` |
| `rol_uci` | metin | `HIGH` / `LOW` — seviyenin direnç mi destek mi olduğu |
| `swing_class` | metin | Swing sınıfı |
| `structural_role_final` | metin | **Yanlı** final rol — yalnız şeffaflık için |
| `state`, `valid`, `finalized`, `locked` | metin/bool | Motor durumu |
| `source_bar` / `source_bar_time` | index / zaman | Pivotun kaynak barı |
| `confirm_bar` / `confirm_bar_time` | index / zaman | Pivotun **onaylandığı** bar (pivot_len bar sonra) |
| `price` | fiyat | Seviye fiyatı |
| `atr_at_source` | fiyat | Kaynak barın ATR'si |
| `prominence_atr` | ATR | Pivotun belirginliği |
| `distance_atr` | ATR | Komşu pivota uzaklık |
| `quality` | 0–100 | Swing kalitesi |
| `broken` / `broken_bar` / `broken_bar_time` | bool / index / zaman | Kırıldı mı, ne zaman |
| `bars_to_break` | bar | `broken_bar - confirm_bar` |
| `bars_to_break_sansur` | bool | Kırılım görülmedi |

### 9.2 Rol aralığı ve deneme

| Kolon | Birim | Tanım |
|---|---|---|
| `rol` | sınıf | PH/PL/SH/SL/WH/WL |
| `rol_ilk_bar` / `rol_son_bar` / `rol_sure_bar` | bar | Rolün ömrü |
| `rol_kapanis` | sınıf | Neden bitti |
| `capa_bar` / `capa_bar_time` | bar / zaman | **Rolün atandığı** an = ölçüm çapası |
| `atr_at_capa` | fiyat | Çapa barının ATR'si |
| `gozlenen_bar` | bar | `SWING_PENCERESI` içinde gözlenen bar |
| `max_yaklasma_atr` | ATR | ⚠️ **işaretli**: negatif = yaklaştı ama geçmedi, pozitif = geçti |
| `max_yaklasma_bar` | bar | O anın çapadan kaç bar sonrası olduğu |
| `gecildi` | bool | Seviye geçildi mi |
| `kirilim_bar` / `kirilim_atr` | bar / ATR | Kırılım anı ve büyüklüğü |
| `red_magnitude_atr` | ATR | Kırılımdan sonra geri dönüş büyüklüğü |
| `deneme_bar_{025,015,050}` | **bar** | Eşik içinde geçen bar sayısı |
| `deneme_epizot_{025,015,050}` | **epizot** | Ardışık yaklaşma bloklarının sayısı |
| `engelledi_{025,015,050}` | bool/`null` | Üç değerli — bkz. §5.2 |
| `bars_to_break_from_rol` | bar | Rol atamasından kırılıma |

**`deneme_bar_*` ile `deneme_epizot_*` aynı şey değildir.** 20 bar boyunca seviyeye
yapışan fiyat: `deneme_bar_025=20`, `deneme_epizot_025=1`. Karıştırmak "20 kez denedi"
gibi yanlış bir cümle üretir.

`{025,015,050}` etiketleri **0.25 / 0.15 / 0.50 ATR** demektir (yüzdelik tam sayı etiketi).

---

## 10. `event` tablosu — BOS / CHOCH / sweep

Satır birimi: **MS olayı**. Çapa = `event_bar` (onay anı); referans fiyat onay barının
**kapanışı** — yani olayı gören kişinin o anki fiyatı.

| Kolon | Birim | Tanım |
|---|---|---|
| `event_uid` | metin | Olay kimliği |
| `identity`, `scope` | sayı / metin | Ait olduğu swing |
| `event_type` | metin | `EVENT_BOS`, `EVENT_CHOCH`, `EVENT_SWEEP`, `EVENT_FALSE_BREAK`, … |
| `direction` | metin | `UP` / `DOWN` |
| `candidate_bar` / `event_bar` | index | Aday ve onay barı |
| `onay_gecikmesi_bar` | bar | `event_bar - candidate_bar` |
| `broken_level` | fiyat | Kırılan seviye |
| `broken_swing_identity` | sayı | Kırılan swing |
| `origin_price` | fiyat | Olayın referans fiyatı |
| `quality` | 0–100 | Motor kalitesi |
| `confirmation_status`, `validity`, `relevance` | metin | Motor sınıflandırması |
| `outcome` | metin | **Motorun kendi takip kararı** — bağımsız değil |
| `bos_maturity` | metin | BOS olgunluğu |
| `age_bars` | bar | Yaş |
| `confirmed_by` / `failed_by` | metin | İlişkili olay kimliği |
| `referans_kapanis` / `atr_at_event` | fiyat | Ölçüm referansı |
| `devam_*` | 30 | `devam_` önekiyle `yol_ozeti` (bkz. §8.2) |
| `ters_h12` | ATR | **Ters** yöndeki uzanım — tepkinin diğer yarısı |
| `devamlilik_sinifi` | sınıf | Ön-tanımlı sınıf |
| `uyum` | sınıf | `UYUMLU` / `UYUMSUZ` |

**`outcome` motorun kendi görüşüdür.** Bağımsız ölçüm `devam_h12` ve `uyum`'dur;
ikisi çelişirse bu bir bulgudur ve kartta **ikisi birlikte** yazılır.

---

## 11. `meta` tablosu — seri özeti

| Kolon | Birim | Tanım |
|---|---|---|
| `symbol`, `timeframe` | metin | Seri kimliği |
| `bar_sayisi` | bar | Çerçeve uzunluğu |
| `atr_son` | fiyat | Son barın ATR'si |
| `zone_sayisi`, `ob_zone_sayisi`, `fvg_zone_sayisi` | sayı | Zone sayıları |
| `epizot_sayisi`, `swing_sayisi`, `event_sayisi`, `rol_araligi_sayisi` | sayı | Satır sayıları |
| `ms_data_quality`, `ms_hata` | metin | MS motor durumu / hata metni |
| `vp_data_quality` | metin | VP motor state'i |
| `fvg_durum`, `fvg_isinanma` | metin / sayı | FVG alt motoru |
| `engine_version`, `config_hash` | metin | Damga |

`ms_hata` dolu bir seri **eksik veridir**, `n`'e katılmaz; kart bunu yazar.

---

## 12. Yan sütun sözleşmesi — `vp_*` ve `ms_*`

**Kural:** Market yapısı ve hacim **ana çıktı değildir**. Ölçüm yönünü (ana oranı)
belirlemezler; **koşul** olarak kesit alırlar ("şu koşulda ne değişiyor").

| Aile | Nerede | Rolü |
|---|---|---|
| `vp_*` (17) | `dokunus`, `swing`, `event` | Temas/olay **anındaki** hacim durumu |
| `ms_*` (2) | yalnız `meta` | Motor sağlığı |

`vp_*` alanları: `rvol`, `volume_z_score`, `volume_percent_rank`, `volume_slope`, `rtv`,
`capital_z_score`, `directional_value_pressure_5/10`, `net_progress_atr`,
`directional_efficiency`, `volume_result_efficiency`, `capital_result_efficiency`,
`effort_result_class`, `data_ready`, `volume_usable`, `capital_usable`.

**Bayrak kuralı:** `vp_volume_usable=False` ise o satırın hacim kolonları
**yorumlanmaz** (satır düşürülmez, sadece kesit alınmaz). `vp_data_ready` olmadan
`vp_rvol` üzerinden oran hesaplamak yasaktır.

---

## 13. `frm` — formasyon tablosu (yeni, henüz kodlanmadı)

### 13.1 Neden ayrı tablo

`research/kayit.py` içinde bugün **formasyon hattı yok**; oradaki `lifecycle_export`
hacim motorunun alanıdır, formasyonla ilgisi yoktur. Formasyonun tanığı
`state/formation_history.py` defteridir ve o defter **canlı bot** tarafından yazılır.
Bu tablo, aynı motoru (`ArgentEngine.process(df, tam_yeniden=True)`) replay ederek
defterin **offline** karşılığını üretir.

**Yeni matematik yok.** Motor zaten "geri test = canlı birebir" diyor; yapılan iş
sarmalayıcıdır.

### 13.2 Satır birimleri

| Tablo | Birim | Ne taşır |
|---|---|---|
| `frm` | formasyon | Doğumdan ölüme **tek satır** özet |
| `frm_olay` | olay | Merdivenin her basamağı (uzun format) |

Kullanıcı kararı: **bar-bazlı seri yok** (soru 2 = B). Bar-bazlı sorular özet
kolonlardan cevaplanır; yeni bir bar-bazlı soru doğarsa koşu tekrarlanır (50 dk).

### 13.3 Senin cümlelerin → motor durumu

| Cümle | Motor durumu (`patterns/constants.py`) | Bugün olay olarak var mı |
|---|---|---|
| "kırılım denemesi yapıyor" | `KIRILIM_DENEMESI` | ❌ yalnız snapshot |
| "kırılım adayı" | `KIRILIM_ADAYI` | ✅ `BREAK_CANDIDATE` |
| "kırılım teyitli" | `KIRILIM_TEYITLI` | ✅ `BREAK_CONFIRMED` |
| "retest bekliyor / işliyor" | `RETEST_BEKLENIYOR`, `RETEST_EDILIYOR` | ❌ yalnız snapshot |
| "retest aldı" | `RETEST_BASARILI` | ✅ `RETEST_OK` |
| "tamamlandı" | `FORMASYON_TAMAMLANDI` | ✅ `COMPLETED` |
| "teyit alamadı" | `KIRILIM_TEYIT_ALAMADI` | ✅ `TIMEOUT` |
| "başarısız kırılım" | `BASARISIZ_KIRILIM` | ✅ `BREAK_FAILED` |
| "zayıfladı" | `FORMASYON_ZAYIFLADI` | ✅ `WEAK` |
| "geçersiz" | `FORMASYON_GECERSIZ` | ✅ `INVALID` |
| **"desteğe/dirençe yakınlaştı"** | — | ❌ **hiç yok** (bu tablonun varlık sebebi) |

### 13.4 Kimlik bloğu (defterden **birebir**, K2)

`stable_id`, `pattern_type`, `family`, `classic_dir`, `specialized_variant`,
`dogum_bar_time`, `known_bar_time`, `end_bar_time`, `apex_bar_time`,
`geometry_atr`, `start_width`, `raw_quality`, `has_pole`, `pole_*`.

`family` burada **formasyon ailesi** demektir (üçgen, kama, bayrak…), OB/FVG değil.
Birleştirme yapılırsa `frm_family` / `zone_family` olarak ön eklenir (§14).

### 13.5 Mesafe bloğu — "1 ATR yaklaştı" ★

Yaşam boyunca her bar için `U_b` = üst sınır, `L_b` = alt sınır, `A_b` = o barın ATR'si.

**İşaretsiz iki ayrı ölçü** (karışmasın diye ayrı kolon):

```
yakinlik = max(0, U_b - H_b) / A_b     → 0 ise fitil çizgiye değdi
asim     = max(0, H_b - U_b) / A_b     → ne kadar aştı
```

| Kolon | Birim | Tanım |
|---|---|---|
| `frm_yakinlik_ust_fitil_atr` ★ | ATR | Üst sınıra **en çok** yaklaştığı an (fitil). 0 = değdi |
| `frm_yakinlik_ust_kapanis_atr` ★ | ATR | Aynı ölçü, **kapanış** ile |
| `frm_yakinlik_alt_fitil_atr` ★ | ATR | Alt sınıra en çok yaklaşma (fitil) |
| `frm_yakinlik_alt_kapanis_atr` ★ | ATR | Aynı ölçü, kapanış |
| `frm_yakinlik_ust_bar_time` ★ | zaman | O anın barı (çapa; kart bunu yazar) |
| `frm_yakinlik_alt_bar_time` ★ | zaman | Aynı |
| `…_atr_dogum` (4 varyant) ○ | ATR | Aynı ölçüler, **doğum ATR'si** ile — sabit cetvel |
| `frm_asim_ust_fitil_atr` ★ | ATR | Üst sınırı en fazla ne kadar aştı |
| `frm_asim_alt_fitil_atr` ★ | ATR | Alt sınırı en fazla ne kadar aştı |

**Eşik ızgarası.** `ESIK_IZGARA` (`(0.25, 0.50, 1.00, 1.50, 2.00)`) yeniden
kullanılmaz: 0.25 zaten swing tarafında **temas/deneme** eşiğidir, yakınlık için fazla
geniştir. Yeni sabit — **`YAKINLIK_IZGARA = (0.50, 1.00, 1.50, 2.00)`** — tanımlanır ve
`_ANAHTARLAR`'a eklenir (K3: aksi halde `config_hash` değişmez ve satırlar karışır).
`E ∈ {050, 100, 150, 200}`.

| Kolon deseni | Birim | Tanım |
|---|---|---|
| `frm_yakin_ust_{E}_bar` ★ | bar | `0 ≤ yakinlik ≤ E` olan bar sayısı |
| `frm_yakin_ust_{E}_epizot` ★ | epizot | Bu bandın **ardışık blok** sayısı (= "kaç kez yaklaştı") |
| `frm_yakin_ust_{E}_ilk_gecikme_bar` ○ | bar | İlk yaklaşmanın doğumdan kaç bar sonra olduğu |
| `frm_yakin_alt_{E}_…` (aynı 3) | — | Alt sınır için simetrik |

`epizot` sayımı **swing tablosundaki `_yaklasma_epizotlari` ile birebir aynı**
mantığı kullanır; iki tablo arasında "deneme" tanımı farklı olamaz.

**Anti-dairesellik:** `yakinlik_*_min` metrikleri **çapanın kendisine kadar** olan
barlarda hesaplanır. Tepki büyüklüğü (kâr, MFE) çapadan **sonra** başlar. İkisini aynı
pencerede hesaplamak "yaklaşan formasyon tepki verdi" cümlesini totoloji yapar.

### 13.6 Deneme bloğu — kırılım kaç kez denendi ★

| Kolon | Birim | Tanım |
|---|---|---|
| `frm_kirilim_deneme` ★ | sayı | Kırılım denemesi sayısı (buffer'a giriş + geri dönüş epizodu) |
| `frm_kirilim_ilk_deneme_gecikme_bar` ★ | bar | İlk denemenin doğumdan uzaklığı |
| `frm_kirilim_son_deneme_gecikme_bar` ○ | bar | Son deneme |
| `frm_teyit_deneme_no` ★ | sayı | **Kaçıncı denemede** teyit alındı (`null` = almadı) |
| `frm_kirilim_deneme_var` ★ | bool | En az bir deneme |

**Deneme tanımı (öneri — kodlanmadan önce onaylanacak):** fiyat etkin kırılım buffer'ı
kadar sınırı aşar, sonra `retest_window` bar içinde geri döner. **Tam sayım replay'den
gelir**; defterdeki snapshot sayısı yalnız **alt sınır** verir (faz içi gidip-gelmeler
kaybolur). Bu yüzden `KIRILIM_DENEMESI` olayının defterde olmaması bu tabloyu engellemez.

### 13.7 Temas bloğu

| Kolon | Birim | Tanım |
|---|---|---|
| `upper_touches` / `lower_touches` ★ | sayı | Defterdeki **pivot** temas sayısı (son değer) |
| `frm_pivot_temas_max` ★ | sayı | Yaşam boyunca görülen **en yüksek** değer |
| `frm_pivot_ezilme_var` ★ | bool | Sayaç hiç **düştü** mü (pivot ezilmesi kanıtı) |
| `frm_temas_epizot` ★ | epizot | Fiyatın sınıra **fiilen** değdiği blok sayısı (fitil) |
| `frm_temas_ilk_gecikme_bar` / `_son_gecikme_bar` ○ | bar | İlk/son temas |

`frm_pivot_temas_max` neden gerekli: pivot listesi sonradan ezilebilir
(`patterns/pivots.py:43`), yani `upper_touches` **donmuş gerçek değil**. İki kolonun
farkı, ölçüm belirsizliğinin kendisidir ve kartta yazılır.

### 13.8 Faz ve süre bloğu

| Kolon | Birim | Tanım |
|---|---|---|
| `frm_faz_geometri_bar` ★ | bar | `GEOMETRI_ADAYI` evresinde geçen bar |
| `frm_faz_kirilim_bar` ★ | bar | `KIRILIM_*` evresinde geçen bar (deneme dahil) |
| `frm_faz_retest_bar` ★ | bar | `RETEST_*` evresinde geçen bar |
| `frm_faz_gecis_sayisi` ○ | sayı | Toplam state geçişi (osilasyon ölçüsü) |
| `frm_olgunlasma_bar_time` ★ | zaman | `OLGUNLASIYOR`'a ilk giriş |
| `frm_hazirlik_bar_time` ★ | zaman | `KIRILIM_HAZIRLIGI`'ne ilk giriş |

### 13.9 Kırılım bloğu (defterden birebir)

`quality_frozen`, `frozen_raw_quality`, `frozen_upper_boundary_at_break`,
`frozen_lower_boundary_at_break`, `frozen_break_buffer`, `frozen_retest_tolerance`,
`frozen_atr_at_break`, `frozen_classic_dir`, `frozen_pattern_type`,
`break_snapshot_bar`, `break_snapshot_price`, `break_snapshot_direction`,
`break_snapshot_quality`, `break_strength`, `break_body_score`, `break_close_score`,
`break_penetration_score`, `break_expansion_score`, `break_volume_score`,
`break_confirmation_strength`.

**Birim tuzağı:** `frozen_break_buffer` ve `frozen_retest_tolerance` **fiyat**
birimindedir, ATR değil. Bu yüzden türetilmiş üç kolon eklenir:

| Kolon | Formül |
|---|---|
| `break_buffer_atr` ★ | `frozen_break_buffer / frozen_atr_at_break` |
| `retest_tolerans_atr` ★ | `frozen_retest_tolerance / frozen_atr_at_break` |
| `break_marj_atr` ★ | `(break_snapshot_price - sınır) / frozen_atr_at_break` |
| `break_gecikme_bar` ★ | `break_snapshot_bar - end_bar` (formasyon bitişinden kaç bar sonra) |

### 13.10 Retest bloğu

| Kolon | Birim | Tanım |
|---|---|---|
| `retest_var` ★ | bool | `RETEST_BASARILI` görüldü mü |
| `retest_gecikme_bar` ★ | bar | Teyitten kaç bar sonra |
| `retest_derinlik_atr` ★ | ATR | Sınıra geri dönüşün derinliği |
| `retest_sure_bar` ○ | bar | Retest evresinin süresi |

### 13.11 Sonuç bloğu

| Kolon | Birim | Tanım |
|---|---|---|
| `terminal_state` ★ | sınıf | `FORMASYON_TAMAMLANDI`, `KIRILIM_TEYIT_ALAMADI`, `BASARISIZ_KIRILIM`, `FORMASYON_ZAYIFLADI`, `FORMASYON_GECERSIZ`, `AÇIK` |
| `terminal_bar_time` ★ | zaman | Ölüm anı |
| `omur_bar` ★ | bar | `terminal_index - known_bar` |
| `olay_sayisi` ★ | sayı | Defterdeki olay sayısı |
| `sonuc_durum` ★ | sınıf | `hedef` / `stop` / `nötr` / `bekliyor` / `ölçülemedi` / `kirilim_yok` |
| `sonuc_kaynak_bar_time` ○ | zaman | Sonucun bağlandığı bar |
| `sansur` ★ | bool | Koşu sonunda hâlâ açık |

**Ölüm ayrımı korunur.** `BASARISIZ_KIRILIM` tek tür değildir: teyit almadan
başarısız olan ile teyitten sonra geçersizleşen ayrı hikâyelerdir
(`main.py:375`'teki sınıflandırma bunu zaten ayırıyor). `frm_olay` tablosunda
`olay_type` + `teyit_oncesi` (bool) bu ayrımı taşır.

### 13.12 `frm_olay` tablosu

`stable_id`, `olay_type` (`NEW_PATTERN`, `DEFINED`, `MATURE`, `PREP`,
`BREAK_CANDIDATE`, `COUNTER_BREAK`, `BREAK_CONFIRMED`, `RETEST_OK`, `COMPLETED`,
`TIMEOUT`, `BREAK_FAILED`, `WEAK`, `INVALID`), `olay_name`, `direction`, `quality`,
`bar_time`, `gecikme_bar`, `faz`, `fiyat`, `teyit_oncesi`.

Defterdeki olay sözlüğü **birebir** taşınır (K2) — yeni alan icat edilmez.

### 13.13 Maliyet ve hacim beklentisi

| Kalem | Değer |
|---|---|
| Replay ek maliyeti | seri başına +0.1–0.3 s |
| Tam havuz (704 seri) | ~50 dk → **~54 dk** |
| Kolon sayısı | ~92 (★ çekirdek: ~45) |
| Satır sayısı | 704 × (formasyon/seri) — `dokunus`tan **çok** küçük |

### 13.14 Yasaklar

1. Mesafe kolonlarını "tepki" sanmak — biri yaklaşma, diğeri sonuç.
2. `upper_touches`'ı donmuş gerçek saymak.
3. Defterdeki `snapshot` sayısını deneme sayısı saymak (alt sınırdır).
4. `frozen_*` fiyat alanlarını ATR sanmak.

---

## 14. Çakışma kayıtları (aynı isim, farklı anlam)

Bunlar **dondurulmuş** durumlardır; düzeltmek eski raporları bozar. Kural: çakışma
yalnızca **birleştirmede** çözülür, tablo adı ön ek olarak eklenir.

| İsim | Nerede | Anlam(lar) | Karar |
|---|---|---|---|
| `family` | `zone` / `frm` | zone'da `OB`/`FVG`; formasyonda formasyon ailesi | Birleştirmede `zone_family` / `frm_family` |
| `quality` | 5 yerde | `raw_quality`, `geometry_score`, `quality_frozen`, swing `quality`, event `quality` | **Çıplak `quality` kullanma**; tablo adıyla an |
| `sansur` | `zone`, `swing`, `event` | Anlam aynı ("pencere yetmedi"), **eşik farklı**: terminal yok / `SWING_PENCERESI` / `h12` | Kart eşiği yazar |
| `olculmedi` | `swing`, `event`, `kenar_` | `capa_yok`·`fiyat_yok`·`rol_uci_belirsiz` / `referans_yok`·`yon_belirsiz` / kenar metni | Önek zorunlu: `swing_olculmedi` vb. |
| `temas_bar_sayisi` | `zone` | **epizot** sayısı (adı "bar" diyor) | Donmuş hata; asla bar sayısı olarak okunmaz |
| `deneme` | `outcome_link` | kırılım denemesi sayısı | `frm_kirilim_deneme` ile aynı kavram; birleşince tek kolon |
| `gozlenen_bar` | 3 tablo | Aynı anlam: çapa sonrası gözlenen bar | Çakışma değil — **eşik** farkını kart yazar |
| `dogum_bar_time` | `zone`, `frm` | Aynı anlam: oluşum barı | Farklı tablo, çakışma yok |
| `native_full_fill` | `zone` | OB'de yapısal olarak `False` | OB'de `native_price_violation` kullan |

---

## 15. Yeni kolon ekleme kontrol listesi

Yeni bir kolon eklemeden önce **sekizi de** cevaplanır:

1. **Ad benzersiz mi?** §14 listesinde çakışma var mı?
2. **Birim belli mi?** ATR / fiyat / bar / oran / sınıf / zaman — biri seçildi mi?
3. **`null` ne demek?** Hangi durumda boş kalır, hangi kolon sebebi taşır?
4. **Sansür nasıl görünür?** Pencere yetmezse hangi `*_sansur` işaretlenir?
5. **`n` hangi satır birimi?** Hangi tabloda, hangi satır sayılır?
6. **Ölçümden önce mi tanımlandı?** Eşik sabit mi, `config_hash`'e girdi mi?
7. **Canlı davranışı etkiliyor mu?** Cevap **hayır** olmalı. Etkiliyorsa bu bir
   ölçüm işi değil, ürün kararıdır — ayrı konuşulur.
8. **Hangi soruyu cevaplıyor?** `YASAM_TABLOSU.md`'de bir soru kimliği yoksa kolon
   eklenmez (soru sicili kolondan önce gelir).

---

## 16. Açık uçlar (v2 adayları)

- `violation` (STATE alanı) tek sayı: ihlal **şiddeti** mi, ihlal **sayısı** mı?
  Şu an snapshot'ta tek değer; tanımı netleşmeden kolona dönüşmemeli.
- `native_*` ailesi OB/FVG'ye özgü; FVG'de `native_terminal_category` ile OB'deki
  aynı mı, ayrı mı — kart bazında doğrulanmalı.
- `ms_data_quality` şu an boş string (`research/kayit.py:763`); doldurulmalı.
- Per-bar seri: kullanıcı kararı gereği **v1'de yok**. İhtiyaç doğarsa ayrı dosya
  (`frmbar_*.jsonl`), `frm` tablosu değişmez.
- `frm_asim_{E}_bar` (sığ aşım bandında geçen bar sayısı) — şimdilik gereksiz;
  "kırılım tuttu mu" sorusu `frm_kirilim_deneme` + `break_marj_atr` ile cevaplanıyor.

---

## 17. Doğrulama

Kolon listesinin tek doğruluk kaynağı **koddur**. Kontrol:

```bash
python scripts/backfill/arastirma_kosu.py --limit 1 --csv-yaz   # başlık satırı
python -c "from research import kayit; print(kayit.config_hash())"
```

**Uyarı:** kolon kümesi koşuya göre değişir. `repoh*` yalnız pencere satırı varsa,
`olculmedi` yalnız ölçüm başarısızsa, `fvg_*` yalnız FVG destekli TF'lerde (2h/4h/1d)
bulunur. Tüketici kod **eksik kolona dayanıklı** olmalı; kolon yokluğu "0" değildir.

**Pilot ölçümü (12 seri, Ekim 2026)** — kolon sayıları ampirik çıpadır:

| Tablo | Kolon | Satır başına |
|---|---|---|
| `dokunus` | 124 | ~4.1 KB |
| `event` | 79 | ~2.3 KB |
| `swing` | 71 | ~2.0 KB |
| `zone` | 29 | ~0.9 KB |
| `meta` | 18 | ~0.45 KB |

`frm` tablosu için hedef ~92 kolon (§13); pilot ile doğrulanmadan **donmaz**.

`config_hash` değiştiyse eski ve yeni satırlar aynı tabloda birleştirilmez.
