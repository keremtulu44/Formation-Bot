# Yaşam Tablosu — Domain bazında soru sicili

> **Durum:** Yürürlükte (v1 taslak) · **Kod yok:** bu bir soru/ölçüm spesifikasyonudur.
> **Amaç:** OB, FVG ve formasyonu **doğumdan ölüme** izleyip, her aşamada okunabilir ve
> önceden kilitlenmiş sorular sormak. Cevaplar aynı formatta yazılır; böylece "öyle oldu
> böyle oldu" anlatısı yerine ölçülmüş hücreler konuşur.
> **Yöntem:** [ARASTIRMA_HATTI.md](ARASTIRMA_HATTI.md) · **Sonuçlar:** [ARASTIRMA_SONUCLARI.md](ARASTIRMA_SONUCLARI.md) · **Kolon adları:** [KOLON_SOZLUGU.md](KOLON_SOZLUGU.md)

---

## 0. Üç tasarım kuralı (bunlar bozulursa tablo çöp olur)

**Kural 1 — Ana çizgi domainin kendisidir.** Her domain kendi yaşam çizgisinde ilerler;
market ve hacim **yan sütundur**, soru değil. Yan sütun yalnızca "ana sonucu değiştiriyor mu?"
diye bakılır.

> Neden: hacim ve endeks aynı anda ikinci bir eksen olursa her hücre 4'e bölünür, n düşer,
> "n=6 ile karar" hatası başlar. Ayrıca endeks yönü **tüm sembollerde ortaktır** — onu koşul
> yaptığın an bağımsız gözlem sayısı çöker (bugün 176 sembol, etkin olarak birkaç rejim).

**Kural 2 — Sonuç penceresi epizot bittikten sonra başlar.** Dolum derinliği, temas süresi
gibi ölçüler **epizot içinde**; tepki (ATR) **epizot kapandıktan sonra** ölçülür. Aksi halde
"derin dolum kötü" sonucu bir bulgu değil, tanımın kendisi olur (döngüsellik).

**Kural 3 — "Hiç olmadı" bir satırdır, ortalamaya katılmaz.** Temas almayan / kırılmayan /
sansürlü gözlemler her tabloda **ayrı satır** olarak yazılır. Ortalamalar daima
**medyan + q25 + q75**; asla tek başına ortalama. 1h ile 1d asla havuzlanmaz.

---

## 1. Cevap formatı — her soru tek kart üretir

```
SORU      : OB-13 · İlk temasta dolum derinliği tepkiyi değiştiriyor mu?
AŞAMA     : S3 (ilk temas)
ANA ÇİZGİ : dolum kovası  (<%25 · %25–50 · %50–75 · >%75)
ÇIKTI     : ≥1 ATR tepki oranı + medyan tepki (ATR), her kovada
TABAN     : aynı TF'te tüm temaslar (karşılaştırma çizgisi)
YAN SÜTUN : rvol çeyreği (ana sonucu değiştiriyor mu?)
KARAR     : GA sıfırı içermiyorsa "fark var", aksi halde "fark yok"
```

**Yazım kuralları**
- `n < 50` → sayı yazılmaz, **"ölçüm yok (n=X)"** yazılır.
- GA (küme bootstrap, sembol×gün) sıfırı içeriyorsa → **"fark yok"**, yorum yapılmaz.
- Delta daima **puan** cinsinden ve taban oranla birlikte yazılır (`+16,8 puan`).
- Keşifte bulunan her şey, ayrı pencerede tekrar test edilmeden **"bulgu"** sayılmaz.
- Durum işaretleri: `✅` bugün ölçülebilir · `◐` mevcut alanlardan türetilebilir · `○` yeni alan/tanık gerekir.

---

## 2. OB — yaşam tablosu

### S0 · Doğum
Ne biliyoruz: OB motoru zone'u doğurur, sınırları **doğum anında dondurulur**; `origin` ile
`available` arasında kullanıma açılma gecikmesi vardır. Doğum anı özellikleri sonradan
değişmez — bu yüzden en güvenilir ölçüm noktası burasıdır.

| ID | Soru | Cevap formatı | Durum |
|---|---|---|---|
| OB-01 | Kaç OB doğuyor, TF ve yön (boğa/ayı) kırılımıyla? | n / ay / sembol; TF×yön tablosu | ✅ |
| OB-02 | Aynı sembolde aynı gün kaç OB doğuyor (kümelenme)? | dağılım: 1 · 2 · 3–5 · 6+ | ✅ |
| OB-03 | Doğumdan kullanıma açılmaya gecikme ne kadar? | medyan / q25 / q75 (bar) | ✅ |
| OB-04 | Doğum büyüklüğü (ATR) dağılımı ne? | kovalar: <0,5 · 0,5–1 · 1–2 · ≥2 | ✅ |
| OB-05 | Doğum barı hacmi dağılımı ne? | rvol çeyreği | ✅ |
| OB-06 | Doğum anında yapı (MS) ne diyordu? | son olay tipi/yön/yaşı dağılımı | ○ |

**Yan sütun (S0):** doğum hacmi (OB-05) — burada "koşul" değil, **sonraki aşamaların yan sütunu**
için etiket. Tek başına yorumlanmaz.

### S1 · Bekleme — ilk temasa kadar

Bu, senin "ortalama kaç mumda ulaştı" sorusunun doğru yeri. **Üç satır birden** yazılmazsa
sonuç yanıltıcı olur.

| ID | Soru | Cevap formatı | Durum |
|---|---|---|---|
| OB-07 | OB'lerin kaçı hiç temas almıyor? | **ayrı satır**: % + n (taban: %5,4–10,3) | ✅ |
| OB-08 | İlk temasa süre? | **medyan / q25 / q75** (bar), TF ayrı | ✅ |
| OB-09 | Bekleme süresi sonucu değiştiriyor mu? | süre kovası (0–5 · 6–15 · 16–40 · 40+) → temas aldı mı / tepki | ✅ |
| OB-10 | Bekleme sırasında fiyat kaç kez yaklaşıp döndü? | yaklaşma epizodu sayısı dağılımı | ◐ |
| OB-11 | Bekleme sırasında hacim kurudu mu? | doğum→temas arası rvol ortalaması (yan sütun) | ✅ |

**Yan sütun (S1):** OB-11 yalnız OB-09'un içinde okunur: "süre etkisi hacim kurumasından bağımsız mı?"

### S2 · Kullanıma açılma
Kısa aşama; ölçüm değeri düşük. Yalnız bir kontrol sorusu:

| ID | Soru | Cevap formatı | Durum |
|---|---|---|---|
| OB-12 | `available` anında geçmişe göre ne değişti (fiyat zone'dan ne kadar uzakta)? | ATR mesafe dağılımı | ✅ |

### S3 · İlk temas — en yoğun aşama

Senin sorduğun her şey burada: hangi kenar, ne kadar doldu, ne kadar kaldı, hacim/market nasıldı,
tepki ne oldu. **Tepki eşiği asla tek sayı değil, eğri olarak** yazılır.

| ID | Soru | Cevap formatı | Durum |
|---|---|---|---|
| OB-13 | Hangi kenar dokunuluyor, OB yönüyle ilişkisi ne? | % üst / alt / iki kenar; yön kırılımı | ✅ |
| OB-14 | Dolum derinliği ne, tepkiyi değiştiriyor mu? | kova (%25/50/75) → ≥1 ATR oranı + medyan ATR | ✅ |
| OB-15 | Temas kaç bar sürüyor? | medyan / q25 / q75 | ✅ |
| OB-16 | **Tepki eşik eğrisi:** temasların kaçı ≥0,25 / 0,5 / 1 / 1,5 / 2 ATR? | beş satır, her biri % + n *(taban: ≥1 ATR %65, ≥2 ATR ~%39)* | ✅ |
| OB-17 | Tepki büyüklüğü ne (koşulsuz)? | medyan + q25/q75 ATR (h=12) | ✅ |
| OB-18 | Tepki ne kadar hızlı ve ne kadarı geri veriliyor? | tepeye süre (bar) + decay (ATR) | ✅ |
| OB-19 | Yol şekli düz mü testere mi? | yol verimliliği (net/brüt hareket) | ◐ |
| OB-20 | **İlk temas sonrası kırılmazsa ne olur?** | hayatta kalan % → sonraki kırılma süresi medyanı | ✅ |

**Yan sütun (S3):** `rvol çeyreği` + `endeks yönü (aynı bar / son 5 bar)`.
Yalnızca OB-14 ve OB-16'nın **içinde** raporlanır: "koşul eklendiğinde delta değişiyor mu?"
Hacim burada **ana eksen değildir** (mevcut bulgu Q4 için ayrı bir not olarak durur).

### S4 · Tekrar temaslar — 2. ve 3.

Senin "2. temas nasıl yapılıyor, 1.'yi nasıl etkiliyor, üst/alt farkı var mı" soruları burada.
En değerli **yeni** satır `OB-23`: aynı kenar mı, karşı kenar mı.

| ID | Soru | Cevap formatı | Durum |
|---|---|---|---|
| OB-21 | Hayatta kalanların kaçı 2. / 3. kez dokunuyor? | % (taban: 2. temas %19–21, 3+ %11–13) | ✅ |
| OB-22 | 2. temasın tepkisi 1.'ye göre ne kadar az? | delta ATR + ≥1 ATR oranı farkı | ✅ |
| OB-23 | **İkinci temas aynı kenara mı, karşı kenara mı?** (tekrar red mi, sıkışma mı) | 2×2 dağılım + her hücrenin sonucu | ◐ |
| OB-24 | Tekrar temaslar arası süre kısalıyor mu (sıkışma)? | 1→2 ve 2→3 süre medyanı | ✅ |
| OB-25 | Büyüklük (ATR) tekrar temas etkisini değiştiriyor mu? | `yukseklik_kovasi × temas_no` çapraz | ✅ |
| OB-26 | Üst kenar ve alt kenar tekrar davranışı farklı mı? | kenar × temas_no | ✅ |

**Yan sütun (S4):** aynı — rvol ve endeks yalnız OB-22/OB-25'in içinde.

### S5 · Ölüm ve kırılma mekaniği

| ID | Soru | Cevap formatı | Durum |
|---|---|---|---|
| OB-27 | Ölüm nedeni dağılımı ne? | fiyat ihlali / tam dolum / sansür % | ✅ |
| OB-28 | Ömür ne kadar? | medyan / q25 / q75 (bar) + TF ayrı | ✅ |
| OB-29 | **Nasıl kırıldı?** | tek bar / 2–3 bar / sürünme; gap'li mi; ihlal barı rvol'ü | ✅ |
| OB-30 | Kırılma ne kadar derin (zone'u ne kadar aştı)? | ATR dağılımı | ✅ |
| OB-31 | Kırılma anında MS ne yazdı, aynı barda mı? | eşleşme oranı + onay gecikmesi | ○ |

### S6 · Ölüm sonrası (bugün hiç bakılmayan aşama)

| ID | Soru | Cevap formatı | Durum |
|---|---|---|---|
| OB-32 | İhlalden sonra fiyat devam mı etti, döndü mü? | h=5/12'de yön dağılımı | ✅ |
| OB-33 | Kırılan OB'ye geri dönüş (retest) oldu mu, kaç barda? | retest % + süre medyanı | ✅ |
| OB-34 | Retest sonrası yön ne oldu? | % devam / dönüş | ✅ |

---

## 3. FVG — yaşam tablosu (iki aşamalı)

**Tasarım farkı:** FVG'de "kaç denemede doldu" sorusu **anlamsızdır** — 55.145 zone'da 3+ deneme
4 adettir. Bu yüzden FVG tablosu tek bir çatala indirilir:

```
S1 doğum → S2 çatal:  (a) hiç temas almadı (%21–28)   → bu bir SONUÇ, ayrı satır
                       (b) temas aldı (tek temas)     → nasıl çözüldü?
```

| ID | Soru | Cevap formatı | Durum |
|---|---|---|---|
| FVG-01 | Kaç FVG doğuyor, TF dağılımı ne? | n / ay / TF | ✅ |
| FVG-02 | Ne kadarı hiç temas almıyor? | **ayrı satır**: % + n *(taban %20,9–27,9)* | ✅ |
| FVG-03 | Temas alanların kaçı tek temasta çözülüyor? | % *(taban %71,4–77,9)* | ✅ |
| FVG-04 | 2. temas gerçekten nadir mi, hangi koşulda oluyor? | % + koşul kırılımı | ✅ |
| FVG-05 | Temas alanların kaçı tam doluyor / kaçı ihlal ediliyor? | % *(taban tam dolum %40–42)* | ✅ |
| FVG-06 | Yükseklik (ATR) "hiç temas almama"yı değiştiriyor mu? | kova → hiç temas % + tam dolum % | ✅ |
| FVG-07 | Tepki eşik eğrisi ne? | ≥0,25 / 0,5 / 1 / 1,5 / 2 ATR → % | ✅ |
| FVG-08 | Tepki büyüklüğü ve hızı ne? | medyan ATR + tepeye süre + decay | ✅ |
| FVG-09 | Doğum barı (displacement) hacmi tepkiyi değiştiriyor mu? | rvol kovası → tepki | ✅ |
| FVG-10 | Temas anı yüksek hacmi burada da mı zayıflatıyor? | rvol Q4 vs Q1 delta (yan sütun testi) | ✅ |
| FVG-11 | OB ile örtüşen FVG daha mı iyi? | örtüşme var/yok → hiç temas % + tam dolum % | ◐ |

**Yan sütun (FVG):** FVG-09/10 yalnız "ana sonucu değiştiriyor mu" olarak okunur; ayrı soru açılmaz.
**Not:** FVG'de sol taraf senin gözleminle birebir uyuşuyor — tek temas ya da hiç temas. Tablo bunu
**varsaymıyor**, ölçüp satır olarak yazıyor.

---

## 4. Formasyon — yaşam tablosu (8 aşama)

18 state'in tamamı izlenmez; **karar omurgası** izlenir. Her aşamada "solda kalan kaç tane?"
mantığı (yaşam tablosu) korunur.

| Aşama | State eşlemesi | Ana soru (ID) | Cevap formatı | Durum |
|---|---|---|---|---|
| S0 Öncül | ADAY_OLUSUYOR, GEOMETRI_ADAYI | FRM-01 · Öncül hareket neydi (impulse var mı, yön)? | % + tip dağılımı | ✅ |
| S1 Doğum | FORMASYON_TANIMLANDI | FRM-02 · Tip/kalite/bant genişliği dağılımı | tablo | ✅ |
| S1 | — | FRM-03 · **Doğduğu anda en yakın aktif destek/direnç (PH/PL) ne kadar uzakta?** | ATR mesafe kovaları | ◐ |
| S2 Olgunlaşma | OLGUNLASIYOR, SIKISMA_GUCLENIYOR | FRM-04 · Daralma ne kadar, kaç barda? | medyan % + süre | ✅ |
| S2 | — | FRM-05 · Sıkışmada hacim kurudu mu? | rvol eğimi (yan sütun) | ✅ |
| S3 Hazırlık | KIRILIM_HAZIRLIGI | FRM-06 · **Direnç yakınlığı kırılım oranını artırıyor mu?** (doz-yanıt) | mesafe kovası → kırılım % | ◐ |
| S4 Deneme | KIRILIM_DENEMESI, KIRILIM_ADAYI | FRM-07 · Kaç deneme yapılıyor, kaçı başarısız? | dağılım + % | ✅ |
| S4 | — | FRM-08 · **Kırılım yönü, en yakın rol seviyesinin tarafıyla uyumlu mu?** | % uyum | ◐ |
| S5 Teyit | KIRILIM_TEYITLI | FRM-09 · Teyit ne kadar gecikiyor, hangi bar kapanışıyla? | medyan bar | ✅ |
| S5 | — | FRM-10 · **Teyit barı hacmi: teyit mi, tuzak mı?** (zone'da tersi bulunmuştu) | rvol kovası → hedefe ulaşma | ✅ |
| S5 | — | FRM-11 · Teyit ile MS BOS aynı barda mı? | % eşleşme + gecikme | ○ |
| S6 Retest | RETEST_BEKLENIYOR/EDILIYOR/BASARILI | FRM-12 · Retest oranı ne, kaç barda geliyor? | % + süre medyanı | ✅ |
| S6 | — | FRM-13 · Retest derinliği başarıyı değiştiriyor mu? | kova → başarı % | ✅ |
| S6 | — | FRM-14 · Retest sırasında hacim düşükse başarı artıyor mu? | rvol (yan sütun) | ✅ |
| S7 Sonuç | TAMAMLANDI / BASARISIZ / TEYIT_ALAMADI / GECERSIZ | FRM-15 · Sonuç dağılımı ne? (yaşam tablosu son satırı) | % + n | ✅ |
| S7 | — | FRM-16 · Tamamlanma süresi ve hedefe ulaşan ATR hareketi? | medyan bar + ATR | ✅ |
| S7 | — | FRM-17 · Başarısız kırılım ne kadar geri dönüyor? | ATR dağılımı | ✅ |
| S7 | — | FRM-18 · Geçersizleşme en sık hangi state'te oluyor? | state matrisi | ✅ |
| Çapraz | — | FRM-19 · Kırılım noktasında OB/FVG var mı; retest başarısını değiştiriyor mu? | var/yok → % | ◐ |
| Çapraz | — | FRM-20 · Formasyon yönü ile MS yönü uyumu sonucu değiştiriyor mu? | 2×2 → sonuç % | ○ |

**Yan sütun (formasyon):** FRM-05, FRM-10, FRM-14. Hepsi tek bir soruda, tek bir delta olarak.

---

## 5. Yan sütun sözleşmesi — market ve hacim nasıl kullanılır

Sen bunları "destekleyici" istedin; bunun **tek** doğru kullanımı şudur:

| Kullanım | Doğru | Yanlış |
|---|---|---|
| Ana hücrenin içinde delta | "Dolum >%75 → ≥1 ATR %48 (rvol Q4'te %44, Q1'de %52)" | Ayrı "hacim × dolum × TF" tablosu |
| Etiket | "Endeks aynı yönde / ters" | Endeksi kova yapıp hücreleri bölmek |
| Sağlamlık kontrolü | "Endeks yönü sabitken delta korunuyor mu?" | Endeks yönü başına ayrı sonuç ilan etmek |
| Karar kuralı | Yan sütun deltayı **değiştirmiyorsa** ana bulgu sağlam | Yan sütun "anlamlı" diye ana sonucu değiştirmek |

**Üç uyarı**
1. **Endeks ortaktır.** 176 sembolün aynı günü bağımsız gözlem değildir; endeks koşulu etkin n'yi
   çökerür. Yalnız "aynı gün" etiketi olarak ve GA hesabında küme olarak kullanılır.
2. **Hacim ikiye ayrılır:** `temas öncesi` (yaklaşma, kuruma) ve `temas anı` (rvol). İkisini
   birleştirmek, mevcut Q4 bulgusunu gizler.
3. **`volume_usable=False`** (XU100/XU30/BRENT) satırları düşürülmez; "KULLANILAMAZ" olarak ayrı
   gösterilir — payda kaybı görünür kalmalı.

---

## 6. v1 kilidi — önce cevaplanacak 12 soru

Bunlar bugün ölçülebilir (`○` gerektirmeyen) ve en yüksek değerli olanlar:

| # | ID | Neden ilk |
|---|---|---|
| 1 | OB-07 | "hiç temas almadı" satırı olmadan süre ortalaması yanıltıcı |
| 2 | OB-08 | senin ana sorusu: ilk temasa kaç mumda |
| 3 | OB-09 | süre gerçekten sonucu değiştiriyor mu |
| 4 | OB-13 | kenar asimetrisi (destek/direnç) |
| 5 | OB-14 | dolum derinliği (döngüsellik kuralıyla) |
| 6 | OB-16 | tepki eşik eğrisi — tek sayı yerine eğri |
| 7 | OB-20 | "ilk temasta kırılmazsa ne olur" |
| 8 | OB-22/23 | 2. temas: aynı kenar mı karşı kenar mı |
| 9 | OB-29 | kırılma mekaniği (nasıl kırıldı) |
| 10 | FVG-02/03/06 | FVG'nin çatalı: hiç temas / tek temas / ATR etkisi |
| 11 | FRM-06/08 | senin örneğin: direnç yakınlığı kırılımı etkiliyor mu |
| 12 | FRM-10 | kırılım hacmi teyit mi tuzak mı |

**Rafta (v2):** `○` işaretli tüm sorular — MS tanık kartı geldikten sonra.

---

## 7. Kontrol soruları — cevaplanmadan hiçbir sonuç yayınlanmaz

| ID | Soru | Neden |
|---|---|---|
| K1 | Aynı gün aynı yönde kaç sinyal var, etkin n kaç? | kümelenme |
| K2 | MS'i bozuk semboller dışlanınca sonuç kayıyor mu? | **%5 seri sessizce düşüyor** — seçilim yanlılığı |
| K3 | Aynı soru 4 TF'te aynı yönde mi cevaplanıyor? | tutarlılık |
| K4 | Sansürlü oran ne, sonucu çarpıtıyor mu? | sağdan sansür %0,3–14,6 |
| K5 | Profil (Hassas/Dengeli/Seçici) değişince cevap değişiyor mu? | eşik bağımlılığı |

---

## 8. Cevap kartı örnekleri (mevcut rapordan, format göstergesi)

Aşağıdakiler **yeni ölçüm değil**; bugünkü bulguların bu formatta nasıl yazılacağını gösterir.

**Örnek A — OB-16 (tepki eşik eğrisi)**
```
Taban: tüm OB temasları (n=240.484, 704 seri)
≥0,25 ATR → %74–77     ≥1 ATR → %59–61 (rapor: ≥1 ATR %65,0–66,5 kenar-ancored)
0,5 ATR  → %69–72      ≥2 ATR → %37–40
Okuma: eşik yükseldikçe düşüş dik; "tepki var" ile "yeterli tepki" farklı şeyler.
```

**Örnek B — FVG-02 + FVG-03 (çatal)**
```
Hiç temas almadı  : %20,9–27,9  (n=12.680 / 55.145 zone)
Tek temasta çözüldü: %71,4–77,9
2. temas           : %0,6–1,1
3+                 : %0,0 (4 adet)
Okuma: FVG'de çoklu temas varsayımı geçersiz; soru "temas aldı mı".
```

**Örnek C — OB-22/23 (2. temas)**
```
1. temas tepkisi : taban
2. temas tepkisi : %19–21 oranında gerçekleşiyor → tepki deltası ölçülecek
Kenar ayrımı     : ◐ (aynı kenar = tekrar red, karşı kenar = sıkışma)
Okuma: PH'deki %36→%8 deseninin OB karşılığı ancak bu ayrımla görülebilir.
```

---

## 9. Açık uçlar

- **Formasyon defteri bugün yok.** `research/` hattı OB/FVG/rol/MS ölçüyor; `lifecycle_export`
  motorda var ama satıra çevrilmiyor. FRM-01…20 bu yüzden "yeni hat" gerektirir.
- **MS durum serisi yok.** Olaylar var (`event_satirlari`), ama "her bar için son durum" serisi yok;
  `○` soruların tamamı buna bağlı.
- **VP ince.** POC/VA/absorption ölçüm satırında yok; hacim şimdilik yalnız rvol düzeyinde.
- **Breadth yok.** 48 hissenin kaçı ortalamanın üstünde sorusu ikinci turda.
