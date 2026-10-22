# Son Doğrulanmış Replay — okunur özet

> **Durum:** Kayıt (tarihli ölçüm) · **Tarih:** 2026-10-21 · **Sürüm:** replay-2026-10-21
> **Kaynak:** iki düz metin dökümü (veri + temel ölçüm dökümü ve arşiv araştırma raporu)
> **Okuma süresi:** 2 dk özet · 8 dk tam
> **Sayı biçimi:** adetlerde binlik ayırıcı yok, ondalık nokta (`90199`, `2.0054`).
> Kaynak dökümle birebir aynı tutuldu; yeniden biçimlendirme sırasında sayı
> dönüştürülmedi.

Bu belge, iki dökümün **aynı bilgiyi tek yerde** verecek biçimde yeniden
düzenlenmesidir. Dört ayrı MFE/MAE/NET tablosu tek tabloya indirildi, her
bölümün sonuna "ne demek / canlıda ne yaparız" satırı eklendi, ölçülemeyen
hücreler gizlenmek yerine tabloya yazıldı.

---

## 0 · Tek ekran

| # | Bulgu | Sayı | Güven |
|---|---|---|---|
| 1 | Zone **bariyer değil, zamanlama aracı** | dokunuşta %65.0–66.5 tepki, ama zone'ların %85.4–93.6'sı geçilir | n 240484 / 187046 |
| 2 | **FVG tek kullanımlık, OB tekrar denenir** | FVG 3+ temas: 55145 zone'da 4 adet · OB 3+ temas: %12.9 | n 55145 / 131901 |
| 3 | **Tek gerçek ayrıştırıcı: zone yüksekliği** | CALISTI %64.3 → %71.0 (alçak → yüksek) | n 6285 (1d FVG) |
| 4 | **Hacim ters çalışır** | Q1 %70.1 → Q4 %61.0 (4h) | n 6740 / 11928 |
| 5 | **MS en güvenilir yön teyidi** | uyum %97–98, devam ~%70 | n 3387 (4h dış BOS) |
| 6 | **MFE ≈ MAE ≈ 2.0 ATR, NET ≈ 0** | yön avantajı ölçülmedi | 11 hücre, GA'ların çoğu sıfırı içerir |

Tek cümle: **bu ölçüm "nereden döner"i değil "ne kadar oynar"ı ölçüyor** —
zone/MS fiyatın oynayacağı yeri ve büyüklüğünü gösteriyor, yön kazancı
göstermiyor.

---

## 1 · Ölçüm künyesi

| Kalem | Değer |
|---|---|
| Sembol | 176 |
| Zaman dilimi | 1h, 2h, 4h, 1d |
| Sembol × TF (seri) | 704 (tamamlanan 704, başarısız 0) |
| Intraday arşiv | 2025-05-07 → 2026-10-19 |
| Günlük arşiv | 2024-10-21 → 2026-10-19 |
| Gözlem satırı | 994142 |
| MS onarım serisi | 35 (yeni örneklem değil; 704'ün onarılmış çıktısı) |
| Motor profili | Dengeli (parametre değiştirilmedi) |
| Örneklem eşiği | sayısal ortalama/oran için n ≥ 50 |
| GA yöntemi | sembol × ay kümeli, 200 tekrarlı bootstrap; en az 5 sembol ve 3 ay |
| Pencere (MFE/MAE/NET) | 12 bar, birim ATR |

**Dönem uyarısı:** intraday ve günlük arşiv takvim uzunlukları eşit değil.
Bu çalışma sırasında veri çekilmedi, model eğitilmedi, canlı işlem çalıştırılmadı.

**Çalıştırma ayrımı (karıştırılmamalı):** bu dökümün formasyon sayıları
(23806 formasyon, FRM geçerli n 5670/3178/1964/940) `FORMASYON_SONUCLARI.md`
koşusuyla (33964 formasyon, teyitli n 28624) **aynı koşu değildir**; iki
belgenin yüzdeleri yan yana konmaz.

---

## 2 · Nihai kayıt sayıları

| Kayıt | Adet | Not |
|---|---|---|
| OB + FVG zone | 187046 | ölçümün ana birimi |
| Temas epizodu | 240484 | bir epizot 9 bar sürse de 1 satırdır |
| Formasyon | 23806 | motorun bu arşivde tanıdığı |
| Ham formasyon olayı | 215960 | merdiven basamağı |
| Formasyon sınır epizodu | 47785 | |
| Dolum eşik geçiş kaydı | 543411 | **zone sayısı değil**: %25/%50/%75/%100 geçişleri |
| MS olay tanığı | 200028 | |

**TF dağılımı**

| TF | Zone | Temas | Formasyon | Formasyon olayı |
|---|---|---|---|---|
| 1h | 59130 | 90485 | 11369 | 102167 |
| 2h | 64216 | 76267 | 6400 | 58022 |
| 4h | 41510 | 48886 | 4045 | 37688 |
| 1d | 22190 | 24846 | 1992 | 18083 |

**Aile dağılımı**

| Aile | Zone | Temas | TF kapsamı |
|---|---|---|---|
| OB | 131901 | 197521 | 1h, 2h, 4h, 1d |
| FVG | 55145 | 42963 | 2h, 4h, 1d (**1h yok**) |

1h FVG "piyasada yok" değil — bu hat 1h FVG üretmiyor.

---

## 3 · Zone: bariyer mi, zamanlama aracı mı?

**Zone seviyesi**

| Aile | Temas aldı | Geçildi | Tam dolum | Not |
|---|---|---|---|---|
| OB | %89.7–94.6 | **%85.4–93.6** | %0.0 | dolum göstergesi `native_price_violation` |
| FVG | %72.1–79.1 | — | %40.3–42.6 | |

OB'de `native_full_fill` yapısal olarak her zaman `False`; bu ölçüm hatası değil,
motorun kayıt sözleşmesi.

**Dokunuş seviyesi (n 240484)**

| Beklenen yönde tepki | Oran |
|---|---|
| ≥1 ATR | %65.0–66.5 |
| 0.25–1 ATR | %14.9–18.1 |
| tepki yok | %4.1–4.8 |
| ters yönde | %11.2–14.8 |
| ortalama uzanım (h12) | ~2.0 ATR |

**Ne demek:** "buradan döner mi?" → %65 evet. "burada kalıcı mı durur?" → %90
hayır. TF'ler arasında fark şaşırtıcı küçük (%65.0–66.5 bandı); tepki oranı
timeframe'den çok zone'un varlığına bağlı.

**Canlıda ne yaparız:** zone teması giriş **zamanlaması** için kullanılır;
kalıcı destek/direnç varsayımıyla pozisyon taşınmaz.

---

## 4 · OB tekrar denenir, FVG tek kullanımlık

| Aile | Tek temas | 2 temas | 3+ temas | Hiç temas | Ort. epizot |
|---|---|---|---|---|---|
| OB (4 TF) | %59.4–59.9 | %19.1–21.3 | %10.7–13.3 | %5.4–10.3 | 1.37–1.53 |
| FVG (3 TF) | %71.4–77.9 | %0.6–1.1 | %0.0 | %20.9–27.9 | 0.73–0.80 |

Yuvarlama uyarısı: FVG'de 3+ temas %0.0 görünür ama ham sayı **4 adettir**
(%0.007, en fazla 5 epizot). OB'de aynı oran %12.9 (17048 zone, en fazla 20
epizot). FVG zone'larının %23.0'ı (12680) hiç temas almaz; OB'de %6.7 (8797).

**Temas sırasına göre MFE (12 bar, ATR)** — ayrı, betimsel gruplar:

| TF | 1. temas | 2. temas | 3. temas | 4+ temas |
|---|---|---|---|---|
| 1h | 2.0214 (n 55738) | 2.0077 (20441) | 1.9387 (7865) | 1.9380 (6155) |
| 2h | 2.0249 (33682) | 1.9743 (12144) | 1.9005 (4676) | 1.9850 (3611) |
| 4h | 2.0555 (20843) | 2.0276 (7408) | 1.9534 (2951) | 2.0468 (2314) |
| 1d | 1.9963 (11731) | 2.0541 (3965) | 2.0201 (1427) | 1.9194 (897) |

**Ne demek:** eğilim "temas arttıkça tepki azalır" yönünde ama **GA'lar üst
üste biniyor** (ör. 1h 1. temas [1.9900–2.0662] ile 3. temas [1.8433–2.0283]).
Bu tablo tek başına "çok temas = zayıf bölge" iddiasını kanıtlamaz. Aynı zone
içindeki temaslar bağımsız gözlem değildir; eşleşik (2.−1.) fark ayrı ölçümdür.

**Canlıda ne yaparız:** kart, FVG'de "kaçıncı temas" sorusunu hiç sormaz
(cevabı yok); OB'de temas sırası bilgisi varsa yazılır, yoksa yazılmaz.

---

## 5 · Zone yüksekliği: tek gerçek ayrıştırıcı

1d FVG (n 6285) — dört gösterge de **monoton** aynı yönde:

| Yükseklik | n | h12_decay | uzun/ana tepe | tepe_h12 | CALISTI |
|---|---|---|---|---|---|
| 0–0.5 ATR | 3276 | 2.418 | 3.307 | 1.912 | %64.3 |
| 0.5–1 ATR | 1989 | 1.956 | 3.338 | 1.989 | %64.7 |
| 1–2 ATR | 858 | 1.747 | 2.426 | 1.985 | %67.8 |
| ≥2 ATR | 162 | **1.248** | **1.656** | **2.304** | **%71.0** |

| Gösterge | Alçak zone | Yüksek zone | Okuma |
|---|---|---|---|
| `h12_decay` | 2.418 | 1.248 | yüksek zone'da tepkinin azı geri veriliyor |
| uzun/ana tepe | 3.307 | 1.656 | alçak zone'da hareket **sonradan** geliyor |
| CALISTI | %64.3 | %71.0 | |

Aynı desen OB'de de var (1h decay 2.130 → 1.213); en belirgin hâli 2h FVG
(≥2 ATR: tepe_h12 2.839, uzun tepe 4.926, CALISTI %71.7).

**Canlıda ne yaparız:** yüksek zone (≥2 ATR) → kısa ufuk yeterli, tepki hızlı ve
tutulur. Alçak zone (<0.5 ATR) → ya sabırlı ufuk ya hiç giriş.

**Okuma uyarısı:** `h12_decay` 1'den büyükse pencere tepenin altına kapanmıştır
(tepki verildi, tamamı geri verildi) — ölçüm hatası değil.

---

## 6 · Kenar asimetrisi: destek daha sert, fark sıklıkta değil

| Aile | TF | Alt kenar (→yukarı) | Üst kenar (→aşağı) | Fark |
|---|---|---|---|---|
| OB | 1h | 1.983 ATR | 1.779 ATR | +0.20 |
| OB | 4h | 2.117 ATR | 1.869 ATR | +0.25 |
| OB | 1d | 2.187 ATR | 1.660 ATR | **+0.53** |
| FVG | 1d | 1.842 ATR | 1.812 ATR | −0.03 (ters döner) |

CALISTI oranları iki kenarda yakın (%54–63): asimetri **sıklıkta değil
büyüklükte**.

**Eşik ızgarası (h12 içinde aşım)**

| TF | ≥0.25 | ≥0.5 | ≥1 | ≥1.5 | ≥2 ATR |
|---|---|---|---|---|---|
| 1h | %74.5 | %69.4 | %58.6 | %48.0 | %38.5 |
| 2h | %74.7 | %69.2 | %58.0 | %47.3 | %37.7 |
| 4h | %75.2 | %69.9 | %59.3 | %49.3 | %39.8 |
| 1d | %77.1 | %72.0 | %60.7 | %49.5 | %39.2 |

Dört TF neredeyse üst üste. Pratik eşik 1 ATR: temasların ~%59'u ≥1 ATR,
~%39'u ≥2 ATR tepki veriyor.

**Dürüst sınır:** 1h OB'de temasların %21.5'inde (4h'te ~%23) yön belirlenemiyor
(`TUM_ZONE`); bu satırlar `OLCULEMEDI` olarak ayrı duruyor. Kenar-ancored
sonuçlar temasların ~%77'sine dayanıyor.

---

## 7 · Hacim: sezgiye ters

| rvol çeyreği | 1h CALISTI | 2h CALISTI | 4h CALISTI | 4h ort. h12 |
|---|---|---|---|---|
| Q1 (düşük) | %66.6 | %69.6 | **%70.1** | 2.272 ATR |
| Q2 | %71.9 | %67.8 | %67.7 | 2.115 ATR |
| Q3 | %67.3 | %65.9 | %66.1 | 2.081 ATR |
| Q4 (yüksek) | **%61.3** | **%60.4** | **%61.0** | 1.868 ATR |

Q4 her intraday TF'de en kötü; Q1–Q4 farkı ~9 puan; ortalama uzanım da aynı
yönde düşüyor (4h: 2.272 → 1.868).

**Ne demek:** dokunuşta yüksek göreli hacim, zone'un **tüketilmekte** olduğunu
gösterir; teyit değil, ihlal işaretidir. Desen tam monotonik değil (1h'de
Q2 > Q1); sağlam kısım Q4'ün her zaman en kötü olması. `KULLANILAMAZ`
satırları `volume_usable=False` gözlemlerdir (XU100/XU30), düşürülmedi.

**Canlıda ne yaparız:** "hacim teyit eder" filtresi ters çalışır; zone
bağlamında hacim ya tersine kullanılır ya hiç kullanılmaz.

---

## 8 · MS: en güvenilir yön teyidi, ama asimetrik

4h özet:

| Kapsam | Tip | n | Uyumlu | CALISTI | Devam yok | Ters | Ort. devam |
|---|---|---|---|---|---|---|---|
| Dış | BOS | 3387 | %98.0 | %71.0 | %7.5 | %0.9 | 2.500 ATR |
| Dış | CHoCH | 1300 | %97.9 | %70.8 | %8.2 | %0.8 | 2.403 ATR |
| İç | BOS | 6505 | %97.0 | %68.2 | %9.2 | %1.0 | 2.408 ATR |
| İç | CHoCH | 2455 | %97.9 | %70.0 | %7.5 | %0.8 | 2.407 ATR |

İki asimetri:

| Eksen | Bulgu | Örnek |
|---|---|---|
| Yön | yukarı kırılım daha güvenilir | 4h dış BOS ↑ %75.0 / 2.827 ATR · ↓ %67.3 / 2.189 ATR |
| Kapsam | iç yapı biraz zayıf ama daha sık | 4h BOS: iç %68.2 (6505) vs dış %71.0 (3387) |

**Ne demek:** sinyallerin ~%70'i çalışıyor; zone'lardaki %65'ten belirgin yüksek.
365 günlük pencerede yukarı kırılımlar ~8 puan daha güvenilir — bu bir rejim
gözlemi, kural değil.

---

## 9 · PH / PL / WH / WL: tepe çöker, dip tutar

**Engelleme oranı, test sayısına göre** (0.25 ATR yaklaşma bandı):

| Test | PH 1d dış | PH 1d iç | PH 4h dış | PL 1d dış | PL 1d iç |
|---|---|---|---|---|---|
| 1 | %36.0 | %34.1 | %31.3 | %37.5 | %37.7 |
| 2–3 | %22.6 | %21.0 | %23.0 | %28.9 | %30.0 |
| 4+ | **%8.0** | %19.8 | %17.2 | **%33.3** | %26.5 |

PH: %36.0 → %8.0 (test arttıkça çöker) · PL: %37.5 → %33.3 (neredeyse hiç bozulmaz).

**WH/WL süpürülme (4h)**

| Seviye | n | Ziyaret | Süpürüldü | Hiç ulaşılmadı |
|---|---|---|---|---|
| Dış WH | 3854 | %70.5 | %59.3 | %40.7 |
| Dış WL | 4126 | %71.2 | %60.4 | %39.6 |
| İç WH | 8327 | %77.2 | %65.3 | %34.7 |
| İç WL | 8190 | %80.9 | %69.9 | %30.1 |

**Süre:** ortanca **3 native bar** (dört TF'de aynı); q25 1–2, q75 5–7,
ortalama 4.7–6.0. Yani zayıf seviyeler "er ya da geç" değil neredeyse hemen
test ediliyor. İç seviyeler dıştan daha sık süpürülüyor (%77–81 vs %65–71);
WL, WH'den her TF'de ~3–5 puan daha sık.

**Canlıda ne yaparız:** WH/WL hedef olarak kullanılacaksa ufak ufuk **3–6 bar**,
20 değil. 4+ test edilmiş PH direnç sayılmaz (kırılım beklentisi); tekrar test
edilen PL güvenilir kalır.

**Okuma uyarısı:** 0-deneme kovasının %100 "engelledi" görünmesi tanımsal
boşluktur (seviyeye hiç yaklaşılmamış) — yorum dışı. Bu soru yalnız bar bar rol
izlemesiyle cevaplanabildi: final snapshot'ta roller mutate olduğu için 2 PH /
0 PL görünüyordu; izleme 382395 swing satırı ve 273583 rol aralığı üretti.

---

## 10 · Sonuç ölçümleri: tek tablo

MFE = yapı yönünde en büyük uzam · MAE = ters yönde en büyük uzam (pozitif
gösterilir) · NET = pencere sonu kapanışının yönlü farkı. Birim ATR, pencere
12 bar. Çapa: OB/FVG **temas epizodu sonu**, FRM **teyit**. Aynı çapa değil.

| Aile | TF | n | MFE | MAE | NET | NET %95 GA | Yön var mı |
|---|---|---|---|---|---|---|---|
| OB | 1h | 90199 | 2.0054 | 2.0846 | −0.0065 | [−0.0835, 0.0561] | hayır |
| OB | 2h | 54113 | 2.0001 | 2.1184 | −0.0345 | [−0.1359, 0.0557] | hayır |
| OB | 4h | 33516 | 2.0397 | 2.2219 | −0.0679 | [−0.1718, 0.0521] | hayır |
| OB | 1d | 18020 | 2.0071 | 2.1046 | 0.0031 | [−0.1600, 0.1409] | hayır |
| FVG | 2h | 21679 | 2.1112 | 1.9693 | 0.0979 | [−0.0276, 0.1992] | hayır |
| FVG | 4h | 14830 | 2.1264 | 2.1316 | 0.0032 | [−0.0900, 0.0903] | hayır |
| FVG | 1d | 6139 | 1.9725 | 2.1383 | −0.0139 | [−0.1453, 0.1391] | hayır |
| FRM | 1h | 5670 | 2.1939 | 1.9688 | 0.1173 | [−0.0293, 0.2774] | hayır |
| FRM | 2h | 3178 | 2.2690 | 1.9409 | **0.1835** | **[0.0262, 0.3475]** | sınırda |
| FRM | 4h | 1964 | 2.3756 | 1.9896 | 0.1608 | [−0.1106, 0.3770] | hayır |
| FRM | 1d | 940 | 2.0178 | 2.2277 | −0.2183 | [−0.6393, 0.1251] | hayır |

**Bu tablonun tek okuması:** her satırda `MFE ≈ MAE ≈ 2.0 ATR` ve `NET ≈ 0`.
Yani ölçüm, zone/formasyon sonrası **oynaklığı** gösteriyor (her iki yöne de
~2 ATR), **yön kazancını** göstermiyor. Yalnız FRM 2h hafif pozitif ve GA
sıfırı dışlıyor; tek hücre, 258 soru içinde seçilmiş kesit → çoklu test
düzeltmesi yapılmadan kural sayılmaz.

**Okuma kuralları**

| Durum | Doğru okuma | Yanlış okuma |
|---|---|---|
| Pozitif MFE | pencere içinde bu kadar yol vardı | pencere sonunda o kadar kâr kaldı |
| GA sıfırı içeriyor | fark kanıtlanmadı | "ilişki yok" kanıtlandı |
| GA sıfırı içermiyor | bu örnekte fark var | işlem avantajı/nedensellik var |
| 12 bar | 12 bar, ATR cinsinden | 12 bar = aynı takvim süresi (1h ≠ 1d) |

---

## 11 · Örneklem: hangi hücreye güvenilir

**Aday kayıt → geçerli sonuç** (tam 12 bar penceresi şartı):

| Aile | TF | Aday | Geçerli n | Geçersiz | Geçerli pay |
|---|---|---|---|---|---|
| OB | 1h | 90485 | 90199 | 286 | %99.7 |
| OB | 2h | 54510 | 54113 | 397 | %99.3 |
| OB | 4h | 33965 | 33516 | 449 | %98.7 |
| OB | 1d | 18561 | 18020 | 541 | %97.1 |
| FVG | 2h | 21757 | 21679 | 78 | %99.6 |
| FVG | 4h | 14921 | 14830 | 91 | %99.4 |
| FVG | 1d | 6285 | 6139 | 146 | %97.7 |
| FRM | 1h | 11369 | 5670 | 5699 | **%49.9** |
| FRM | 2h | 6400 | 3178 | 3222 | **%49.7** |
| FRM | 4h | 4045 | 1964 | 2081 | **%48.6** |
| FRM | 1d | 1992 | 940 | 1052 | **%47.2** |

**Kritik:** OB/FVG ölçümleri neredeyse tam popülasyonu görüyor (%97–99.7);
**formasyon ölçümleri yarısını görüyor**. Dışarıda kalan yarı rastgele değil —
tam 12 bar penceresi dolmayan kayıtlar. Yani FRM satırları "tüm formasyonlar"
diye okunamaz.

Geçerli sonuca girmeyen kayıtlar **başarısız sayılmadı**, eksik sonuçlar
**sıfırla doldurulmadı**.

**Ölçülemeyen sorular (258 soru içinde)**

| Durum | Adet | Ne demek |
|---|---|---|
| Betimsel hesap üretildi | 171 | "kapandı" demek değil |
| Kısmi kapsam | 84 | veri az + model eksik (sansür, competing-risk, çoklu test, bağımsız dönem) |
| Örneklem yetersizliği | 3 | aşağıdaki üç soru |
| Tamamen ölçümsüz | 0 | |
| Teknik hata | 0 | |

| Soru | Neden yok |
|---|---|
| 87 · ilişkilerin sembol × dönem tekrarı | 131901 zone içinde ortak hücrelerde n ≥ 50 yok |
| 115 · FVG temasları arası hacim/MS ilişkisi | 42963 adaydan 42950'si eksik; tam özellikli satır 13 |
| 141 · FVG etkileşimlerinin TF/koşul tekrarı | ortak hücreler n ≥ 50 vermiyor |

İlk temaslar, tekrar-temas ölçümü yerine kullanılmadı; genel havuz ortalamasıyla
"doğrulanmış tekrar" iddiası kurulmadı.

---

## 12 · Formasyon kayıtları

| Tür | 1h | 2h | 4h | 1d | Toplam |
|---|---|---|---|---|---|
| Alçalan Kama | 1998 | 1192 | 810 | 421 | 4421 |
| Alçalan Üçgen | 3202 | 1790 | 1164 | 660 | 6816 |
| Ayı Bayrağı | 19 | 8 | 6 | 3 | 36 |
| Ayı Flaması | 19 | 4 | 7 | 4 | 34 |
| Boğa Bayrağı | 15 | 7 | 3 | 2 | 27 |
| Boğa Flaması | 4 | 2 | 3 | 0 | 9 |
| Simetrik Üçgen | 1941 | 1091 | 691 | 282 | 4005 |
| Yükselen Kama | 1770 | 985 | 635 | 286 | 3676 |
| Yükselen Üçgen | 2401 | 1321 | 726 | 334 | 4782 |

Bayrak/flama türlerinde toplam örneklem 50'nin altında → bu türler için
karşılaştırma/genelleme yapılmaz. Diğer sayılar "motorun bu arşiv ve ayarlarda
tanıdığı" kayıtlardır; piyasadaki tüm formasyonların sayımı değildir.

**Gözlem sonu nedeni**

| TF | Native terminal | Yerine başka yapı geçen | Veri sonunda kalan |
|---|---|---|---|
| 1h | 10687 | 650 | 32 |
| 2h | 5964 | 401 | 35 |
| 4h | 3754 | 247 | 44 |
| 1d | 1822 | 117 | 53 |

"Native terminal" otomatik **başarı** demek değil, motorun sonlanma tanımıdır.
Yerine başka yapı geçen veya veri sonunda açık kalan formasyonlar başarısızlık
için negatif örnek yapılmadı.

---

## 13 · Native sonlanma dağılımı (zone motorunun kendi kararı)

**OB**

| TF | Zone | Dolum eşiği (iptal) | Gap ile geçiş | Gözlem sonunda aktif |
|---|---|---|---|---|
| 1h | 59130 | 53679 (%90.8) | 1694 (%2.9) | 3757 (%6.4) |
| 2h | 36306 | 32356 (%89.1) | 1043 (%2.9) | 2907 (%8.0) |
| 4h | 22916 | 20011 (%87.3) | 602 (%2.6) | 2303 (%10.1) |
| 1d | 13549 | 11214 (%82.8) | 363 (%2.7) | 1972 (%14.6) |

**FVG**

| TF | Toplam | Tam dolum | Native tepki | Superseded | Yaş sınırı | Aktif |
|---|---|---|---|---|---|---|
| 2h | 27910 | 11260 (%40.3) | 11291 (%40.5) | 4643 (%16.6) | 622 (%2.2) | 94 (%0.3) |
| 4h | 18594 | 7914 (%42.6) | 7241 (%38.9) | 3045 (%16.4) | 288 (%1.5) | 106 (%0.6) |
| 1d | 8641 | 3523 (%40.8) | 2929 (%33.9) | 1913 (%22.1) | 130 (%1.5) | 146 (%1.7) |

Native dolum eşiği ile geometrik %100 dolum veya distal fiyat ihlali **aynı olay
değil**. Aktif zone başarılı/başarısız diye sınıflandırılmadı. Bu kategoriler
işlem kazancı/kaybı değildir.

---

## 14 · Zaman korumaları ve sansür

| Kalem | Adet |
|---|---|
| Bitişi bilinmiyor olarak korunan açık temas epizodu | 156 |
| Başarısızlık için negatif örnek yapılmayan açık/değiştirilmiş formasyon | 1579 |
| Üst-TF eşlemesi yeniden kurulan günlük-altı formasyon | 21814 |
| Zone ömrü ölçümlerinde sağdan sansürlü | %0.3–14.6 |

Korunan ayrımlar: oluşum zamanı · kullanılabilir olma zamanı · olay zamanı ·
olayın bilinebildiği zaman · terminal zamanı · gözlenen süre · tamamlanmış süre ·
eksik takip. Üst bar, sonraki üst-bar zamanında bilinebilir kabul edildi
(günlük için daha yüksek TF bu çalışmada yok).

---

## 15 · Denetim ve tekrar üretilebilirlik

| Kontrol | Sonuç |
|---|---|
| Denetlenen seri | 704 |
| Üretilen soru kartı | 258 |
| Tam kanıt hücresi | 210791 |
| Tekrar hücre | 0 |
| Payda hatası | 0 |
| Seçilmiş birleşimde MS teknik hatası | 0 |
| Bağımsız tekrar hesabında byte-byte aynı rapor | 263 |
| Onarım serilerinde geometri/olay verisi aynı | 35 / 35 |
| Test sonucu | 218 geçti, 1 atlandı |

Atlanan test: önceden işaretlenmiş canlı durable-outbox/scanner entegrasyon
testi (offline araştırma kapsamı dışında).

---

## 16 · Ölçüm sırasında bulunan iki yapısal tuzak

| Tuzak | Ne oldu | Etki |
|---|---|---|
| OB motoru dolan zone'ları listeden siliyor | THYAO 4h: replay 138 zone, final snapshot 18 zone (7.7× eksik) | snapshot'tan ölçüm yapılsaydı örneklem yalnız geçilmemiş zone'lardan oluşurdu |
| `structural_role` zamanla mutate oluyor | final snapshot: 2 PH / 0 PL / 0 WH-WL | bar bar rol izleme zorunlu hâle geldi |

İkisi de canlı botu etkilemez (canlı yol snapshot'ı ölçüm için kullanmıyor);
snapshot'tan backtest yapmaya kalkışan herkesi etkiler.

---

## 17 · Açık bulgu: canlı botta sessiz MS çökmesi

704 serinin **35'inde (%5.0)** MS motoru
`ValueError: confirmed break references must still be active` ile düşüyor:
1h 20, 2h 6, 4h 4, 1d 5 seri (liste: `arastirma_ms_hatali_seriler.txt`).

Canlı botta `_execute_domain` hatayı yuttuğu için bot çökmüyor; o sembolün MS
domaini **sessizce boş** kalıyor — BOS/CHoCH sinyali üretilmiyor, kullanıcıya
uyarı gitmiyor. Bu araştırma tarafının değil **canlı botun** kusuru.

**İlk adım (kök neden ayrı iş):** hata yakalandığında "MS domain devre dışı"
uyarısı düşürmek — sessiz boşluk yerine görünür degrade.

---

## 18 · Terimler

| Kısa | Açılım | Not |
|---|---|---|
| OB / FVG | order block / fair value gap | iki ayrı aile, ayrı çapa |
| TF | zaman dilimi | 1h, 2h, 4h, 1d |
| FRM | formasyon | çapası teyit, OB/FVG'den farklı |
| n | geçerli gözlem sayısı | tablolar arasında **toplanmaz** |
| GA | %95 güven aralığı | grup ortalamasına ait; gruplar arası farkın GA'sı değil |
| MFE / MAE | en büyük olumlu / ters uzam | ATR, 12 bar, pozitif büyüklük |
| NET | pencere sonu yönlü fark | MFE ile aynı şey değil |
| CALISTI | beklenen yönde ≥1 ATR uzanım | kârlılık değil, sıklık |
| TUM_ZONE | kenar seçilemeyen temas | `OLCULEMEDI`, sonuca karışmaz |
| Decay | h12 sonunda verilen pay | >1 ise tepki tamamen geri verilmiş |
| PH / PL / WH / WL | korunan tepe/dip, zayıf tepe/dip | rol zamanla mutate olur |

---

## 19 · Bu verinin izin verdiği / vermediği yorum

| Yapılabilir | Yapılamaz |
|---|---|
| "Bu tanım, bu TF, bu dönem, bu örneklemde hangi davranış gözlendi?" | nedensellik |
| "Bu davranış 4 TF'de tutarlı mı?" | garantili yön tahmini |
| "Hangi kesitte veri var, hangisinde yok?" | işlem kârlılığı, maliyet sonrası avantaj |
| "GA bu örnekte sıfırı dışlıyor mu?" | bütün sembollerde ve gelecek dönemlerde geçerlilik |
| — | native terminal etiketinden otomatik başarı/başarısızlık |

Özellikle: yüksek MFE ile yüksek NET aynı şey değil; olumlu ve ters uzam aynı
pencere içinde birlikte görülebilir; bar içindeki kesin olay sırası OHLC'den her
durumda bilinemez.

---

## 20 · Bu belge nasıl güncellenir

1. Yeni replay koşusu bitince **yeni dosya** açılır (`replay-YYYY-MM-DD`); bu
   dosya olduğu gibi kalır — tarihli kayıt üzerine yazılmaz.
2. Sayılar kaynak dökümden **elle** taşınır; hesaplama burada yapılmaz.
3. Yeni bir satır eklenecekse tabloya değil, ilgili bölümün "ne demek" satırına
   gerekçe yazılır (K3: eşik ölçümden önce sabit).
4. Kart/metin tarafına taşınacak sayı varsa `AMPIRIK_REFERANS.md` üzerinden
   gider; bu belge doğrudan üretim koduna bağlanmaz.
