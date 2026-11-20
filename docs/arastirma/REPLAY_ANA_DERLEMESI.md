# REPLAY ANA DERLEMESİ — bütün geçmiş ölçümler tek dosyada

> **Durum:** Derleme (yeni ölçüm değil) · **Tarih:** 2026-11-19 · **Sürüm:** `derleme-v1`
> **Ne yapar:** Depoda dağınık duran **bütün** replay/ölçüm çalışmalarını tek yerde
> toplar; her biri için kapsam, ana sayı ve **kısa yorum** verir. Pozitif, negatif ve
> "yazı tura kadar" sonuçlar aynı dürüstlükle yazılır.
> **Ne yapmaz:** Yeni sayı üretmez, eski sayıyı düzeltmez, canlı kural önermez.

---

## 0 · Nasıl okunur

**Nereden başlamalı:** acelesi olan → **§7.5 Karar tablosu** (hangi kurala
güvenilebilir). Bir iddiayı kontrol edecek olan → **§2 Envanter** (ID ile ara),
sonra ilgili kart. Yeni bir ölçüm planlayan → **§6 sıra** + **§8 Sınırlar**.

| Bölüm | Ne var |
|---|---|
| §1 | Veri rejimi değişikliği (2h/4h native, 1h'de FVG yok) |
| §2 | 37 çalışmanın envanter tablosu (ID · evren · sonuç yönü · durum) |
| §3 | Kartlar: §3.1 zone/OB/FVG/MS · §3.2 formasyon · §3.3 kırılım/teyit · §3.4 gölge · §3.5 stabil · §3.6 pilot · §3.7 altyapı |
| §4 | Onlarca çalışmanın kesiştiği **9 tekrar eden ders** |
| §5 | "Yazı tura kadar" olanlar (ölçülmüş belirsizlikler) |
| §5.5 | Native verinin kendi gürültü tabanı (2h/4h ↔ 1h) |
| §5.7 | **Native sonuçlar (tam evren)** — eski vs yeni yan yana, hangi bulgu ayakta kaldı |
| §5.8 | **Üç aile (Stabil/OB/FVG)** 8 soruda karşılaştırma — hangisi ne işe yarıyor |
| §5.9 | **Alarm yönü önerisi** — 4 katman + 5 grafik kuralı ([ayrı dosya](ALARM_YONU_2026-11-19.md)) |
| §6 | Yeniden koşu sırası ve komutlar |
| §7 | Dosya haritası · §7.5 Karar tablosu · §8 Sınırlar |

Her replay bir **kart** olarak durur:

```
### Rxx · Başlık
KAPSAM · VERİ · DÖNEM
ANA SAYI — ölçülmüş, uydurulmamış
YORUM — bu sayı ne demek, ne demek değil
DURUM — bu sonuç bugün hâlâ geçerli mi?
KAYNAK — dosya
```

**DURUM etiketleri:**

| Etiket | Anlamı |
|---|---|
| `GEÇERLİ` | Veri ve yöntem bugünkü arşivle uyumlu; sayı kullanılabilir |
| `VERİ DEĞİŞTİ` | Sonuç eski **türetilmiş** 2h/4h ile üretildi (1h'den resample). Sayı tarihsel kayıt; yeni native replay'in sonucu **değil** (bkz. §1) |
| `GEÇERSİZ` | Yöntemde sonradan sızıntı/hata bulundu; sayı **karar tabanı olamaz** |
| `PLAN` | Yalnız plan/kural belgesi; ölçüm yok |
| `SİCİL` | Ölçüm değil, soru/kolon sözlüğü/sözleşme |

**Kritik okuma kuralı:** Bu dosyadaki oranlar **birbirine eklenemez.** Her replay
farklı bir evren, dönem veya satır birimi kullanır (176 sembol / 174 / 100 / 50;
zone / temas epizodu / swing / olay / plan). İki kartın yüzdesini toplamak veya
ortalamak yanlış sonuç verir.

---

## 1 · Önce şunu bil: 2h/4h artık native

Bütün eski replay'ler `2h` ve `4h` barlarını **1 saatlik barlardan türetiyordu**
(`data.resample_ohlcv`). 2026-11-18'de bu kaldırıldı:

| TF | Eski | Yeni (native) |
|---|---|---|
| 1h | Yahoo 1h | Yahoo 1h (aynı) |
| **2h** | 1h → resample | **TradingView `in_2_hour`** |
| **4h** | 1h → resample | **TradingView `in_4_hour`** |
| 1d | Yahoo 1d | Yahoo 1d (aynı) |

**Neden önemli:** 1h açılış müzayede barlarının hacmi ve 2h/4h kova ızgarası
sağlayıcıda farklıydı; türetim **hacim ve fiyat kayması** üretiyordu. Dahası,
kayan pencerede kova fazı saatten saate döndüğü için aynı gün **26 tekrar mesaj**
üretilmişti (R29).

**Bugünkü durum:** `backfill_data/` içinde **176 sembol × 4 TF = 704 native
CSV.gz**, `resample_kullanildi=false`. Eski 2h/4h'ye dayanan **her** sayı artık
"tarihsel kayıt"tır. Yeniden koşu bu turda başlatıldı (§6).

Ayrıca, doğrulama sırasında görülen ve **bütün** replay'leri etkileyen bir kapsam
gerçeği:

> **`1h` zaman diliminde FVG hiç üretilmiyor.** Native koşuda `fvg_durum =
> ATLANDI_TIMEFRAME`, `fvg_zone_sayisi = 0`. Yani "FVG" başlıklı her bulgu aslında
> **2h/4h/1d** bulgusudur; 1h için FVG iddiası kurulamaz.

---

## 2 · Envanter — tek bakışta bütün replay'ler

| ID | Çalışma | Evren | Satır birimi | Sonuç yönü | Durum |
|---|---|---|---|---|---|
| R01 | Arşiv araştırması (OB/FVG/MS/swing) | 176×4 | zone / epizod / swing / olay | **Karışık** — güçlü yapısal bulgu, zayıf yön | VERİ DEĞİŞTİ |
| R02 | Replay özeti 2026-10-21 | 176×4 | 11 hücre | **Yazı tura** — MFE≈MAE, NET≈0 | VERİ DEĞİŞTİ |
| R03 | DZ replay 2026-10-28 | 177×4 | 708 seri | **Yeniden üretim kanıtı** | VERİ DEĞİŞTİ |
| R04 | S01–S32 soru seti cevapları | 176×4 | soru başına tablo | **19 canlı / 7 RED** | VERİ DEĞİŞTİ |
| R05 | Formasyon FRM-01…20 | 176×4 | 33.964 formasyon | **Negatif** — kalite ayırt etmiyor | VERİ DEĞİŞTİ |
| R06 | Fazla analizi (formasyon katkısı) | 177×4 | 15.756 kırılım | **Zayıf pozitif** (+1,5 pp) | VERİ DEĞİŞTİ |
| R07 | Koşul taraması (59 özellik) | 177×4 | 16.417 kırılım | **Negatif** — neredeyse hiçbiri geçmedi | VERİ DEĞİŞTİ |
| R08 | Puan doğrulama | 177×4 | 16.818 olay | **Negatif** — puan kurulamaz | VERİ DEĞİŞTİ |
| R09 | Kırılım + teyit replay | 174×4 | 25.457 aday | **Karışık** | VERİ DEĞİŞTİ |
| R10 | Teyit sonrası hareket | 174×4 | 18.131 teyit | **Yön asimetrisi** | VERİ DEĞİŞTİ |
| R11 | Stop & sermaye koruma | 174×4 | 18.352 yol | **Maliyetin altında** | VERİ DEĞİŞTİ |
| R12 | Kırılım replay planı | — | — | PLAN | PLAN |
| R13 | Gölge zincir Faz 0–5 | 176×4 | 704 seri | **Kapı GEÇMEDİ** | VERİ DEĞİŞTİ |
| R14 | Gölge zincir giriş/çıkış | 704 seri | 2.771 plan | **Negatif** — %90 stop erken giriş | VERİ DEĞİŞTİ |
| R15 | Giriş teyidi Faz 6 (holdout) | 120×4 | 480 seri / 990 plan | **Kapı GEÇMEDİ** (K2 −2,24) | VERİ DEĞİŞTİ |
| R16 | Faz 9 tecrübe entegrasyonu | 50 sembol | 412 plan | **Zayıf pozitif, kırılgan** | VERİ DEĞİŞTİ |
| R17 | Gölge v2 inceleme | 176 sembol | 46.773 olay | **Negatif** — 20 kuralın hiçbiri geçmedi | VERİ DEĞİŞTİ |
| R18 | Zarar teşhisi A50 / Tepeden klasik | 120 sembol | 412 / 990 plan | **GEÇERSİZ** (G5 sızıntısı) | GEÇERSİZ |
| R19 | Stabil 100 hisse / 48 soru | 100 sembol | 107.441 H4 checkpoint | **Karışık, güçlü** | GEÇERLİ* |
| R20 | Stabil ok replay 2026-11-05 | seçili hisseler | oklar | **Negatif** — okların çoğu uyarı | GEÇERLİ* |
| R21 | OK sistemi katalog + denetim | 50 sembol | 1.315 ok | **Negatif** — %79 şüpheli | GEÇERLİ* |
| R22 | Stabil direnç replay + 50 model | 174 / 50 sembol | TEST olayları | **Yazı tura** — ayna simetrik | GEÇERLİ* |
| R23 | Destek ↔ direnç karşılaştırma | 174 sembol | 178 eşleşmiş çift | **Yazı tura** (+1,1 pp, GA 0'ı içerir) | GEÇERLİ* |
| R24 | Ek yol analizi (kırılma sonrası) | 174 sembol | 1.467 / 1.233 olay | **Pozitif** — %63,3 geri dönüş | GEÇERLİ* |
| R25 | Kırılım/teyit ayrıntılı dosya | 174×4 | 696 seri | **Sicilli ölçüm** | VERİ DEĞİŞTİ |
| R26 | Kaçırılan hareket pilotu | 5 sembol | 10-bar pencereleri | **Pilot** — temsil edici değil | GEÇERLİ |
| R27 | Çapraz piyasa keşfi | 2 sembol | 21 altküme | **Doğrulanmamış keşif** | GEÇERLİ |
| R28 | Deploy piyasa pilotu | 48 hisse × 12 endeks | 12+66 koşul | **Keşif** | GEÇERLİ |
| R29 | Kova fazı ölçümü | 176 sembol | 1h→2h/4h | **Hata bulundu + düzeltildi** | GEÇERLİ |
| R30 | Aday-teyit karşılaştırma & teyit nedenleri | 174×4 | olay | **Betimsel** | VERİ DEĞİŞTİ |
| R31 | Stabil soru seti V2 | 100 sembol | senaryo | **Sicil** | SİCİL |
| R32 | Yaşam tablosu + kolon sözlüğü | — | — | SİCİL | SİCİL |
| R33 | Telegram DM replay eğitimi | — | — | Ayrı ürün | GEÇERLİ |
| R34 | Alarm context prototipi | 10 sembol | JSON paket | Prototip | GEÇERLİ |
| R35 | Ampirik referans katmanı | 176×4 | kart satırı | **Ölçüm→metin köprüsü** | VERİ DEĞİŞTİ |
| R36 | **Native tutarlılık denetimi** (bu tur) | 174×2 | kapanış farkı | **Veri kalitesi** — %0,2–0,3 medyan, 13 uyumsuz sembol | GEÇERLİ |
| R37 | **Domain alarm replay** (bu tur) | **176×4 (tam)** | 334.191 tetik + 162.810 taban | **Karışık** — HACIM +7,3 pp, BOS −2,0 pp; hiçbiri yön vermiyor | GEÇERLİ |

\* `GEÇERLİ*`: Stabil çalışmaları **1d + 1h→4h** kullanır. 4h tarafı hâlâ türetim
olduğu için native 4h ile birebir aynı olmayabilir; ancak bu çalışmaların ana
sonuçları **günlük** çizgi davranışına dayanır ve o taraf native'dir.

---

## 3 · Kartlar — replay replay

### §3.1 Zone / OB / FVG / Market Structure

---

### R01 · Arşiv araştırması — "zone ne yapar?"
**KAPSAM** 176 sembol × 4 TF = 704 seri · **VERİ** 994.142 gözlem satırı · 365 gün
**ANA SAYI**
- Zone **bariyer değil, zamanlama aracı**: dokunuşta **%65,0–66,5** beklenen yönde
  ≥1 ATR tepki, ama zone'ların **%85–94'ü** eninde sonunda geçiliyor.
- **FVG tek kullanımlık**: 3+ temas %0,0 (55.145 zone'da yalnız 4 adet); %23'ü hiç
  temas almıyor. **OB tekrar denenir**: 3+ temas %12,9, %24'ü iki+ epizot.
- **Tek gerçek ayrıştırıcı: zone yüksekliği** — 1d FVG %64,3 → **%71,0** (≥2 ATR).
- **Hacim ters çalışır**: dokunuşta Q1 %70,1 → Q4 **%61,0** (4h). Yani "hacimli
  dokunuş" teyit değil, **tükenme** işareti.
- **MS en güvenilir yön teyidi**: BOS/CHoCH yön uyumu **%97–98**, devam ~%70.
- Destek tarafı tepkiyi daha büyük üretir (1d'de +0,53 ATR).

**YORUM** Bu, depodaki en sağlam yapısal bulgu kümesi: **"nereden döner" değil
"ne kadar oynar"** ölçülmüş. Ama dikkat — "%65 çalıştı" **kârlılık değil**,
"yönlü uzanım sıklığı". Aynı veride MFE≈MAE olduğu için (R02) bu tepki kâra
çevrilemez.

**DURUM** `VERİ DEĞİŞTİ` — 2h/4h türetimliydi. Yapısal sıralamaların (yükseklik
ayırt eder, hacim ters çalışır) native veride de kalması **beklenir ama
kanıtlanmadı**; doğrulama koşusu bu turda başlatıldı.

**KAYNAK** [`ARASTIRMA_SONUCLARI.md`](ARASTIRMA_SONUCLARI.md) · [`ARASTIRMA_BULGULARI.md`](ARASTIRMA_BULGULARI.md) · [`ARASTIRMA_HATTI.md`](ARASTIRMA_HATTI.md)

---

### R02 · Replay özeti — "yön avantajı var mı?"
**KAPSAM** 11 hücre (TF × aile) · MFE/MAE/NET
**ANA SAYI** **MFE ≈ MAE ≈ 2,0 ATR, NET ≈ 0.** 11 hücrenin GA'larının çoğu sıfırı içerir.
**YORUM** Depodaki **en önemli negatif sonuç**: zone dokunuşundan sonra fiyat
**her iki yöne de** benzer büyüklükte gidiyor. Yani "zone'a değdi → şu yöne
gider" cümlesi ölçümle desteklenmiyor. Bu, R01'in "%65 çalıştı" sayısıyla
çelişmiyor: %65 **yön** değil, **oynaklık** ölçüsü.

**DURUM** `VERİ DEĞİŞTİ` — ama native veride NET'in sıfıra yakın kalması
muhtemel; asıl test edilecek şey yön asimetrisi.

**KAYNAK** [`REPLAY_OZET_2026-10-21.md`](REPLAY_OZET_2026-10-21.md)

---

### R03 · DZ replay — "yeniden üretilebiliyor mu?"
**KAPSAM** 177 sembol × 4 TF = 708 seri, **0 hata**, 6.920 sn
**ANA SAYI** 2026-10-21 doğrulamasının zone/dokunuş n'leri **birebir** aynı çıktı
(zone 189.171 / dokunuş 243.256). Yani hat **deterministik**.
**YORUM** Bu kartın değeri sonuç değil **güvenilirlik**: aynı kod + aynı veri →
aynı sayı. Depodaki ölçümlerin tekrar üretilebilirliği kanıtlanmış durumda.
**DURUM** `VERİ DEĞİŞTİ` (belge başında uyarı şerhi var).
**KAYNAK** [`DZ_REPLAY_SONUCLARI_2026-10-28.md`](DZ_REPLAY_SONUCLARI_2026-10-28.md)

---

### R04 · S01–S32 soru seti — "hangi hipotez geçti?"
**KAPSAM** 32 ön-kayıtlı soru, 708 seri, karar eşiği: **≥12 pp yazılır / 5–12 pp
yalnız kart metni / <5 pp RED**
**ANA SAYI** **19 canlıya yazılır · 1 kart metni · 7 RED · 1 karar yok · 4 gözlem.**
Öne çıkanlar:

| Soru | Bulgu | Karar |
|---|---|---|
| S01 taze zone | ≤10 bar %65,7 vs ≥40 bar %69,6 (FVG) — **yaş etkisi yok** | RED |
| S02 rejim kayması | FVG: rejim ≥1,5 → %52,9 vs 0,8–1,2 → %66,8 (**−13,9 pp**) | YAZILIR |
| S02 rejim | OB: −3,8 pp | RED |
| S03 kenar ölçülemezliği | epizotların **%24,4**'ünde kenar yönü belirlenemiyor; yükseklik 0–0,5'te **%49,6** | gözlem |

**YORUM** En çarpıcı sonuç: **"taze zone daha iyi" hipotezi REDDEDİLDİ** — sezgiye
ters. Buna karşılık "zone doğduğundan beri volatilite rejimi değiştiyse FVG
zayıflar" **13,9 puanla** geçti. Ayrıca epizodların dörtte birinde **kenar yönü
ölçülemiyor**; yani "üst kenara değdi → aşağı" kuralı her durumda uygulanamaz.

**DURUM** `VERİ DEĞİŞTİ`. Bu 32 sorunun **native veride tekrarı** en yüksek
öncelikli iş (bkz. §6).
**KAYNAK** [`REPLAY_SORU_SETI_2026-10-29.md`](REPLAY_SORU_SETI_2026-10-29.md) · [`REPLAY_SORU_YANITLARI_2026-10-29.md`](REPLAY_SORU_YANITLARI_2026-10-29.md)

---

### R29 · Kova fazı — "neden aynı gün 26 mesaj?"
**KAPSAM** 176 sembol, 1h→2h/4h dönüşümü
**ANA SAYI** Kayan pencerede kova fazı doğru olma oranı **2h %55,6 · 4h %33,3**.
Kayda geçmiş formasyon doğumlarının TV fazı dışı payı **2h %53,0 · 4h %71,5**.
Ardışık iki taramada motor karar imzası **%64,4 / %67,8** değişiyordu.
**YORUM** Bu bir **hata bulma** çalışması: tekrarların kaynağı Telegram değil,
kova fazının saatten saate dönmesiydi. Düzeltme uygulandı (sabit 09:30 çapası) ve
native 2h/4h'ye geçiş bunu kökten çözdü.
**DURUM** `GEÇERLİ` — düzeltildi; native arşivle konu kapandı.
**KAYNAK** [`KOVA_FAZI_OLCUMU_2026-10-23.md`](KOVA_FAZI_OLCUMU_2026-10-23.md)

---

### §3.2 Formasyon

---

### R05 · Formasyon yaşam döngüsü — FRM-01…20 (native ile YENİLENDİ)
**KAPSAM** 704 seri · **33.964 formasyon** · **229.785 formasyon olayı**
**ANA SAYI**
- Tip dağılımı: Alçalan Üçgen %28,8 · Yükselen Üçgen %22,8 · Yükselen Kama %20,2 ·
  Alçalan Kama %19,3 · Simetrik Üçgen %8,7. Bayrak/flama **%0,0** (16'şar adet).
- Median kalite **her tipte 80–86/100** → **kalite puanı tipleri ayırt etmiyor.**
- Ölüm dağılımı: **%76,2 FORMASYON_TAMAMLANDI** (24.618), gerisi başarısız/zayıf.
- Retest: **%34,9**, medyan gecikme **1 bar**.
**YORUM** Formasyon **çok sık** doğuyor ve **dörtte üçü "tamamlanıyor"** — ama
"tamamlandı" motorun kendi tanımı, kâr değil. Kalite puanının 80–86 bandında
sıkışması, onu ayırt edici olmaktan çıkarıyor (R06 ve R08 bunu ayrıca doğruluyor).
**DURUM** `VERİ DEĞİŞTİ`
**KAYNAK** [`FORMASYON_SONUCLARI.md`](FORMASYON_SONUCLARI.md)

---

### R06 · Fazla analizi — "formasyon ne katıyor?"
**KAPSAM** 177×4 · 15.756 etiketli kırılım · 7 etiket varyantı · sembol düzeyinde bootstrap
**ANA SAYI** Ölçüm birimi **fazla** = sonuç − aynı hücrede rastgele giriş tabanı.
- **Aile en büyük belirleyici**: kama **+4,1** · üçgen **−1,9** (fark 6,1 pp)
- Kama & MTF=4 → **+10,3** (tek başına en iyi hücre)
- Giriş mesafesi: aile içinde Q5−Q1 **−7,0 pp**
- **Kalite puanı belirleyici değil** — bileşenleri birbirini götürüyor
- **Retest −19,9 pp** ama **gelecek bilgisi içeriyor → kullanılamaz**
**YORUM** Formasyon katkısı **gerçek ama küçük** ve tek bir eksende değil.
"Kalite 84 aldı" bilgisi işe yaramıyor; **aile** (kama vs üçgen) ve **giriş mesafesi**
işe yarıyor. Retest satırı ise klasik bir tuzak: en büyük sayı, en kullanılamaz
bilgi.
**DURUM** `VERİ DEĞİŞTİ`
**KAYNAK** [`FAZLA_ANALIZI_2026-10-25.md`](FAZLA_ANALIZI_2026-10-25.md)

---

### R07 · Koşul taraması — 59 özellik
**KAPSAM** 177×4 · 16.417 kırılım · 7 Mayıs 2025 – 19 Ekim 2026
**ANA SAYI** 59 özellik, ~110 eşik kombinasyonu tarandı; çoklu test protokolü
(keşifte |AUC−0,5| ≥ 0,02 ve |z| ≥ 3,0, iki doğrulamada aynı işaret, 7 varyantta
≥6/7) — **geçen özellik sayısı bir elin parmaklarıyla sınırlı**, ayrıntı kaynakta.
**YORUM** "Formasyon dışında şu koşullar kırılımı ayırıyor" hipotezi **büyük ölçüde
RED**. En güçlü aday **piyasa koşulu** (endeks eğimi), formasyonun şekli değil.
**DURUM** `VERİ DEĞİŞTİ`
**KAYNAK** [`KOSUL_TARAMASI_2026-10-24.md`](KOSUL_TARAMASI_2026-10-24.md)

---

### R08 · Puan doğrulama — "puan kurulabilir mi?"
**KAPSAM** 177×4 · 16.818 kırılım olayı · **ön-kayıt SHA-256 alınmış**
**ANA SAYI** **HÜKÜM: öngörücü puan kurulamaz.** Sebep ağırlık değil: kırılım
olayının kendisi aynı yönde **rastgele girişten yalnız +1,5 puan** iyi (ön kayıtta
bar +3,0 idi). Endeks yönü uyumu %38,1 vs %33,0 — ama hiç analiz edilmemiş
77 sembolde uyumlu kırılım %37,5, aynı yönde rastgele giriş %36,4 → formasyon
naif trend takibine **+1,0 pp** ekliyor (kısa tarafta **−0,9**).
**YORUM** Bu, depodaki **en kesin negatif sonuç**. "Olay rastgelelikten zar zor
ayrılıyorsa, o olayı sıralayacak hiçbir puan öngörücü olamaz." Ön-kayıt disiplini
de burada: sonuç görülmeden eşik yazılmış.
**DURUM** `VERİ DEĞİŞTİ`
**KAYNAK** [`PUAN_DOGRULAMA_RAPORU_2026-10-24.md`](PUAN_DOGRULAMA_RAPORU_2026-10-24.md) · [`PUANLAMA_MIMARISI_2026-10-25.md`](PUANLAMA_MIMARISI_2026-10-25.md)

---

### §3.3 Kırılım / teyit

---

### R12 · Kırılım/teyit replay — plan ve kabul kapıları (`PLAN`)
**KAPSAM** Ölçüm yok; bu turun **sözleşmesi**: 174 hisse × 4 TF = 696 seri,
veri sonu 19 Ekim 2026, çevrimdışı gözlemsel araştırma.
**ANA SAYI** — (plan; R09/R10/R11/R25 bu planın ürünü)
**YORUM** Planın en değerli kısmı **kabul kapılarının önceden yazılmış olması**:
ölçüm bittikten sonra eşik seçilmedi. R09/R10/R11'in "geçti/kaldı" hükmü bu
yüzden sonradan rasyonalize edilmiş değil. Ayrıca üç bağımsız payda tanımlıyor
(25.457 ham aday / 21.244 çakışmasız olay / 18.131 teyit penceresi filtreli) —
bu derlemede oranların neden birbirine eklenemediğinin kaynağı budur.
**DURUM** `PLAN` (kabul edildi ve uygulandı; R09/R10/R11/R25 onun çıktısı)
**KAYNAK** [`REPLAY_UYGULAMA_VE_KOR_NOKTA_PLANI.md`](REPLAY_UYGULAMA_VE_KOR_NOKTA_PLANI.md)

---

### R09 · Kırılım + teyit replay
**KAPSAM** 174 hisse × 4 TF = 696 seri · **25.457 ham aday** · son kayıt 19 Ekim 2026
**ANA SAYI**
- Teyitli / teyit alamadı / başarısız: **18.752 / 4.776 / 1.907**
- Filtrelenmiş 15.947 teyidin **12.163'ü ilk**, 3.784'ü ikinci mumda; **medyan 1 bar**
- Adaydan teyide yönlü hareketin medyanı **~0,21 ATR**
- Teyit alamayan 3.577 olayın **%20,0**'inde sonraki 10 kapanıştan biri +2 ATR'ye ulaştı
- İleri dönem: 4h aşağı adaylarda +2 ATR **%49,3**; 4h yukarı **%25,8**
  (keşifte aynı oran %43,2 → **rejim farkı**)
**YORUM** Teyit mekanizması **çalışıyor ama gecikmeli**: teyit gelene kadar
hareketin çoğu (medyan 0,21 ATR) zaten olmuş. İleri dönemde **aşağı yön** belirgin
şekilde daha iyi — bu bir rejim özelliği, kalıcı üstünlük değil.
**DURUM** `VERİ DEĞİŞTİ` (2h/4h resample)
**KAYNAK** [`KIRILIM_TEYIT_REPLAY_SONUCLARI_2026-10-30.md`](KIRILIM_TEYIT_REPLAY_SONUCLARI_2026-10-30.md) · [`KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md`](KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md)

---

### R10 · Teyitten sonra ne oldu?
**KAPSAM** 18.131 teyit (örtüşmesiz), 10 bar ufuk, teyit kapanışından ölçüm
**ANA SAYI** 10. kapanışın medyanı, yönlü:

| TF | Yukarı | Aşağı |
|---|---|---|
| 1h | −0,19 ATR | +0,53 ATR |
| 2h | −0,37 ATR | +0,66 ATR |
| **4h** | **−0,67 ATR** | **+0,81 ATR** |
| 1d | −0,58 ATR | +0,34 ATR |

**YORUM** Üç TF'de de **aşağı teyitler yukarı teyitlerden daha iyi çalıştı**.
Buradaki tehlike: bu tek bir 365 günlük rejimin özelliği olabilir; yukarı
teyitlerin negatif medyanı **kural olarak "yukarı teyitte sat"** demek değil.
**DURUM** `VERİ DEĞİŞTİ`
**KAYNAK** [`TEYIT_SONRASI_HAREKET_2026-10-30.md`](TEYIT_SONRASI_HAREKET_2026-10-30.md)

---

### R11 · Stop & sermaye koruma
**KAPSAM** 18.495 olay → 18.352 geçerli yol · stop 1,0 / hedef 1,5 / 10 bar
**ANA SAYI**
- Baz hücre beklentisi **+0,090 ATR/işlem**; tur başına **0,10 ATR** maliyetle
  **−0,010** → **ham teyitli kırılım maliyeti karşılamıyor**
- "Günde 2 stop → dur" kuralı **hiç tetiklenmedi**; risk **üst üste serilerde**
  (serilerin %60,7'si ≥3, %16,2'si ≥5 stop)
- Dar stop pişmanlığı düşük: S=1,0 ile stop olanların yalnız **%4,05**'i S=1,5 ile
  hedefe varabiliyor
- TF farkı büyük: **4h +0,125** · 1d **+0,025**
**YORUM** Bu kart, R02'nin (NET≈0) işlem diline çevrilmiş hâli. Önemli olan
**stop kuralının yanlış olmaması**: stopu genişletmek kurtarmıyor, çünkü düşen
işlemler düşmeye devam ediyor. Değer **seçicilikte**, stop ayarında değil.
**DURUM** `VERİ DEĞİŞTİ`
**KAYNAK** [`STOP_SERMAYE_REPLAY_2026-11-09.md`](STOP_SERMAYE_REPLAY_2026-11-09.md)

---

### R25 · Kırılım/teyit ayrıntılı dosya — "sayılar birbirini tutuyor mu?"
**KAPSAM** 174×4 = 696 seri · 45.255 takip kontrolü · bağımsız skor yeniden hesabı
**ANA SAYI**
- 45.255 kontrolde bağımsız skor hesabıyla en büyük fark **1,82 × 10⁻¹²**
  (kayan nokta gürültüsü düzeyi) — aritmetik uyuşmazlık yok
- **Üç farklı payda** açıkça ayrıştırıldı: 25.457 ham aday → 21.244 çakışmasız
  olay (15.947 teyitli / 3.577 teyitsiz / 1.720 başarısız) → 18.131 teyit
  penceresi filtreli olay
**YORUM** Bu kart bir "bulgu" değil, **denetim**: aynı olayların farklı
raporlarda farklı paydalarla görünmesinin nedeni belgelendi. Derlemede oranları
toplamayı yasaklayan kural (§0) doğrudan buradan geliyor. Sınırı da yazılı:
aritmetik doğrulama, **Pine/canlı motor/Telegram teslimatı doğrulaması değildir**.
**DURUM** `VERİ DEĞİŞTİ` (yeniden koşulursa payda tablosu native veriyle tekrar üretilmeli)
**KAYNAK** [`KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md`](KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md)

---

### R30 · Aday–teyit karşılaştırma & teyit nedenleri
**KAPSAM** 696 seri · aynı olaylarda aday ve teyit kapanışı
**ANA SAYI** Özet tablolar `sonuclar/aday_teyit_karsilastirma/` ve
`sonuclar/teyit_nedenleri/` altında; teyit nedenleri "güçlü aynı-yön koşulu" ve
"retest" olarak sınıflandırıldı.
**YORUM** Karar üretmeyen **betimsel** çalışma: hangi nedenin teyit ürettiğini
sayar, nedenin işe yarayıp yaramadığını ölçmez. R09/R10 ile birlikte okunur.
**DURUM** `VERİ DEĞİŞTİ`
**KAYNAK** `sonuclar/aday_teyit_karsilastirma/` · `sonuclar/teyit_nedenleri/`

---

### §3.4 Senaryo / gölge (plan) hattı — hepsi kapıdan döndü

---

### R13 · Gölge zincir Faz 0–5
**KAPSAM** 704 seri × 0 hata · ön-kayıtlı 7 kapı
**ANA SAYI** **6/7 kapı geçti, K2 düştü → KAPI GEÇMEDİ.**
- K1 doğrulama n **566** ✓ · K3 doğrulama beklentisi **+0,1107 ATR** ✓
- **K2 UYGUN − kör koşullu hedef = −0,67 puan** (eşik +5,0) ✗
- K6a keşif **+0,3595 ATR** ✓ · K6b doğrulama **+0,1107 ATR** ✓
**YORUM** K2'nin yakaladığı şey tam olarak şu: **geometri + zamanlama değer
üretiyor; "BEKLE/UYGUN" hüküm katmanı hiçbir şey katmıyor.** Yani plan üretmek
işe yarıyor, planı **etiketlemek** yaramıyor. Bu, R08'in (puan kurulamaz) plan
dilindeki tekrarı.
**DURUM** `VERİ DEĞİŞTİ`
**KAYNAK** [`GOLGE_ZINCIR_REPLAY_2026-11-09.md`](GOLGE_ZINCIR_REPLAY_2026-11-09.md)

---

### R14 · Gölge zincir giriş/çıkış incelemesi
**KAPSAM** 704 seri · **2.771 sonuçlu plan** (951 stop)
**ANA SAYI**

| Giriş yeri | n | % | stop oranı |
|---|---:|---:|---:|
| İyi zamanlama | 1.384 | %50,1 | **%5,6** |
| **Erken girdi, düştü** | 843 | %30,5 | **%82,7** |
| Geç girdi, dibi kaçırdı | 338 | %12,2 | %5,3 |
| **Yüksekten girdi, düştü** | 200 | %7,2 | **%79,0** |

**951 stopun 855'i (%90)** erken/yüksekten giriş kesiminden.
**YORUM** Sorun **stop değil, giriş yeri**. Sistem rastgele veya geç girmiyor;
**düşen bıçağa** giriyor: girişten sonraki 10 barda ortalama **1,08 ATR** aleyhte
hareket var. Bu, tek bir kartla çözülebilecek bir problem değil — tetik
zamanlamasının kendisi.
**DURUM** `VERİ DEĞİŞTİ`
**KAYNAK** [`GOLGE_ZINCIR_GIRIS_CIKIS_INCELEMESI_2026-11-10.md`](GOLGE_ZINCIR_GIRIS_CIKIS_INCELEMESI_2026-11-10.md)

---

### R15 · Giriş teyidi Faz 6 (holdout)
**KAPSAM** **holdout120** sembol (ilk30 kalibrasyon dışı) × 4 TF = 480 seri · 990 plan
**ANA SAYI** **KAPI GEÇMEDİ** — K2 **−2,24** (Faz5'te +0,67'ydi, **kötüleşti**).
K3 +0,1204 (yükseldi), K1 224 ✓, K4/K5/K6 ✓.
**YORUM** En kritik metodolojik sonuç: **holdout'ta iyileşme kayboluyor.** Faz5'te
"kağıt üzerinde +0,67" olan katkı, görülmemiş sembollerde **eksiye** dönüyor. Bu,
depodaki tüm "+ puan" iddiaları için okunması gereken ders: **kalibrasyon evreninde
çalışan şey doğrulama evreninde çalışmıyor.**
**DURUM** `VERİ DEĞİŞTİ`
**KAYNAK** [`GIRIS_TEYIDI_FAZ6_RAPOR_2026-11-10.md`](GIRIS_TEYIDI_FAZ6_RAPOR_2026-11-10.md)

---

### R16 · Faz 9 tecrübe entegrasyonu
**KAPSAM** 50 sembol (ana50) · 412 plan · baseline PF 2,12 · net +175,5 A
**ANA SAYI** D7 katmanı **637 işlem · +0,1147 R · %50,7 pozitif**; değişmezlik
kanıtı 412/412 plan-id birebir. Aday dersler: `zemin EXPANDING` **+0,560 A** vs
`CONTRACTING` **+0,330 A**; `zemin_kademe_asagi` **%60 kârlı** vs yukarı **%53**.
**YORUM** En olumlu senaryo sonucu — **ama kırılgan**: net kârın **+67,4 R'si
(92%) en iyi 5 haftadan** geliyor ve en kötü GA sıfırı içeriyor. Kontrol
grubunun (kör baz) altında kalma sorunu (K2) burada da sürüyor.
**DURUM** `VERİ DEĞİŞTİ`
**KAYNAK** [`docs/tasarim/faz9_tecrube/FAZ9_PLAN_VE_SONUCLAR.md`](../tasarim/faz9_tecrube/FAZ9_PLAN_VE_SONUCLAR.md)

---

### R17 · Gölge v2 inceleme ve süreç ölçümü
**KAPSAM** 176 sembol · 46.773 ham olay · 697 karantina
**ANA SAYI**
- **20 ön-kayıtlı yönetim kuralının hiçbiri** kabul çıtasını geçmedi.
- En tutarlı aday: **kapanış tez seviyesinin ters tarafında → çık**; D7'de
  +0,018 R, ama GA sıfırı içeriyor ve doğrulamada yalnız 29 işlemi etkiliyor.
- **28 endeks rejimi filtresinin hiçbiri** stopları anlamlı elemiyor
  (151 erken stopun yalnız 10–20'sini eliyor, 24–46 kârlı işlemi götürüyor).
- Kâr görüp dönenleri önceden ayıran **hiçbir domain gözlemi yok**.
- **48 tepki varyantından hiçbiri** geçmedi.
**YORUM** Bu, depodaki **en kapsamlı "hayır" cevabı**. Özellikle önemli olan:
sistem **aleyhte gözleme tepki verse de** kazanmıyor — yani "erken çık" refleksi
veriyle desteklenmiyor. Tekrar eden tek sinyal: işlem sürerken **endeksin tersine
dönmesi** (%61,2 eşlik).
**DURUM** `VERİ DEĞİŞTİ`
**KAYNAK** [`GOLGE_V2_INCELEME_VE_SUREC_2026-11-14.md`](GOLGE_V2_INCELEME_VE_SUREC_2026-11-14.md) · `sonuclar/golge_v2/`

---

### R18 · Zarar teşhisi A50 / Tepeden klasik — **GEÇERSİZ**
**KAPSAM** 120 sembol · 412 / 990 plan
**ANA SAYI** (yalnız tarihsel kayıt) zarar kovaları, giriş kvadrantı, +2.215 ATR
"bırakılan" hareket.
**YORUM** **Bu sayılar KULLANILAMAZ.** Her iki belge de kendi başında şerh taşıyor:
G5 tepki-onayı **gelecek barı okuyordu** (FAZ9-C'de kapatıldı). Sızıntılı tetikle
üretilen her sayı geçersizdir. Depoda **geçersiz olduğu işaretlenmiş** tek grup
burasıdır ve bu iyi bir uygulamadır.
**DURUM** `GEÇERSİZ`
**KAYNAK** [`ZARAR_TESHISI_A50_2026-11-11.md`](ZARAR_TESHISI_A50_2026-11-11.md) · [`TEPEDEN_KLASIK_2026-11-11.md`](TEPEDEN_KLASIK_2026-11-11.md)

---

### §3.5 Stabil (günlük çizgi) hattı

---

### R19 · Stabil 100 hisse / 48 davranış sorusu
**KAPSAM** 100 BIST hissesi · **107.441 kapanmış 4h noktası** · **10.417 destek olayı** · 642 tablo satırı
**ANA SAYI**
- Çizgiye **sadece değmek** sıradan 20 günlük dipten farksız (`H01`, `H02`) → **yazı tura**
- **Sindire sindire yükseliş** vs dik fırlama: çizgi takibi **%42,7** vs **%19,0**;
  aşağı kayma **%1,5** vs **%16,8**
- **2. temas en iyi**: 8×4H medyan **+0,16 ATR**, 16×4H **+0,32 ATR**
- **3.–4. temas yoruluyor**: 16×4H **−0,67 ATR**, aşağı kırılma **%48,5**
- Fiyat çizgiden **1–2 ATR** uzaktayken iki ihtimal başa baş (%33,5 / %31,7);
  **>2 ATR** olunca eski desteğe dönüş **%12,8**'e düşüyor
- Altına az sarkan (**0–0,5 ATR**) **%65+** geri alıyor; **1,2+ ATR** göçerse
  yalnız **%16** geri alıyor, **%55** çizgi de pes ediyor
- **Yataylaşma kritik**: iniş evresinde tekrar çökme %29,7 → yatayda **%9,1**;
  yukarı yeni basamak **%2,7 → %32,7**
**YORUM** Depodaki **en değerli davranışsal bulgu kümesi**: "çizgi nerede" değil
"çizgi ne yapıyor" ayırt ediyor. Ama dikkat — bu sayılar **betimsel**; işlem
maliyeti, pozisyon ve çıkış kuralı yok. Ve **2. temas iyi / 3.+ temas kötü**
bulgusu, R14'ün "erken giriş" teşhisiyle aynı ailede: tekrar eden temas = tükenme.
**DURUM** `GEÇERLİ*` (günlük native; 4h türetim)
**KAYNAK** [`STABIL_100_HISSE_ANALIZ_SENTEZI.md`](STABIL_100_HISSE_ANALIZ_SENTEZI.md) · [`stabil_100_sonuclar/`](stabil_100_sonuclar/) · [`STABIL_DAVRANIS_MODELI.md`](STABIL_DAVRANIS_MODELI.md)

---

### R20 · Stabil ok replay (2026-11-05)
**KAPSAM** seçili hisseler · ▲/▼ ok adayları · 4s
**ANA SAYI** Sinyal kapanışından sonraki **8 barda MFE < 0,5 ATR** olan "zayıf
tepki" oranı ölçüldü; hacim, önündeki bearish OB/FVG ve MS bağlamına göre kırılım
verildi. Sonuç: hacim grubu ve blok bağlamı **tek başına** zayıf tepkiyi
açıklamıyor.
**YORUM** "Ok var ama tepki yok" şikâyetinin arşiv karşılığı. Buradaki asıl değer
**yöntem**: ok sonrası ölçüm sinyal kapanışından başlar, ATR donar, sansür açık.
**DURUM** `GEÇERLİ*`
**KAYNAK** [`stabil_ok_replay_2026_11_05/RAPOR.md`](stabil_ok_replay_2026_11_05/RAPOR.md)

---

### R21 · OK sistemi katalog + denetim
**KAPSAM** 50 sembol · 4s · 1.079 bar/sembol · **1.315 ok**
**ANA SAYI**
- Ok dağılımı: **U1 ▼ 1.176 (%89)** · K1 ▲ 74 · K2 ▲ 44 · M2 ▲ 12 · M1 ▲ 9
- **Gerçek sinyal (▲) yalnız 139 (%11)**
- Denetim kararı: **ŞÜPHELİ 1.041 (%79)** · SAĞLAM 168 · ZAYIF 106
- Düzeltme sonrası (4s): 1.315 → **932 ok (−%29)**; ▲ 139 → 132
- Günlükte: 1.243 → 968; "**3+ gün üst üste uyarı: 46 → 0**"
**YORUM** Çok net bir **negatif** sonuç: grafikte görünen okların **onda dokuzu
sinyal değil, aynı ▼ yapı uyarısının tekrarı**. Düzeltme eşikleri gevşetmeden
yalnız mesafe + soğuma + görsel ayrım ekledi ve ▲ tarafına **dokunmadı**.
**DURUM** `GEÇERLİ*`
**KAYNAK** [`OK_SISTEMI_2026-11-08.md`](OK_SISTEMI_2026-11-08.md)

---

### R22 · Stabil direnç replay + 50 hisse model testi
**KAPSAM** 174 / 50 sembol · ters direnç çizgisi · 8×4s bar
**ANA SAYI**
- Ters direnç TEST olayı: **aşağı önce %42,1 · yukarı önce %51,6** (1.241 geçerli olay)
- Normal destek: **yukarı önce %41,3 · aşağı önce %51,6**
- **Eşleştirilmiş 178 çift: destek %47,2 · direnç %46,1 → fark +1,1 pp;
  GA −9,2 … +11,6** (sıfırı içerir)
- 50 hisselik bağımsız kesit: 53 çift, ikisi de **%45,3**, fark **+0,0 pp**
**YORUM** Direnç ile destek **simetrik**. Bu iki taraflı bir "yazı tura" sonucudur:
tepki yönü önce gelme yarışı ~%41–42, ters yön ~%51. Yani çizgi temasından
sonra **ters tarafa gitme olasılığı daha yüksek** — bu, "destek tutar" sezgisinin
tersi.
**DURUM** `GEÇERLİ*`
**KAYNAK** [`stabil_direnc_replay_2026_11_06/RAPOR.md`](stabil_direnc_replay_2026_11_06/RAPOR.md) · [`stabil_direnc_50_model_testi_2026_11_06/RAPOR_50.md`](stabil_direnc_50_model_testi_2026_11_06/RAPOR_50.md)

---

### R23 · Destek ↔ direnç karşılaştırma
**KAPSAM** 174 hisse · 2026 kesiti · 1.616 / 1.241 geçerli olay
**ANA SAYI**
- Gerçek temas: tepki yönü önce destek **%40,1** / direnç **%43,8**
- Temas mumunda güvenli tarafta kapanma: destek **%53,5** / direnç **%56,2**
- Uzaklaşma yarışı (24×4s): destek **%35,4 takip / %32,6 dönüş**;
  direnç **%29,2 / %36,8** → **sıralama tersine dönüyor**
**YORUM** Simetri **yakın ama birebir değil**: kısa vadede destek daha çok takip
ediyor, uzun vadede dirençte fiyat dönüşü öne geçiyor. Fark küçük ve GA geniş;
**"direnç desteğin aynasıdır"** demek için yeterli değil, "benziyor" demek için yeterli.
**DURUM** `GEÇERLİ*`
**KAYNAK** [`stabil_destek_direnc_karsilastirma_2026_11_06/SONUC.md`](stabil_destek_direnc_karsilastirma_2026_11_06/SONUC.md)

---

### R24 · Kırılma sonrası ek yol analizi
**KAPSAM** 2026 · destek 1.467 / direnç 1.233 geçerli kırılma · tam 24×4s bar
**ANA SAYI** Kırılma sonrası fiyat eski çizginin **güvenli tarafına döndü**:
destek **%63,3** · direnç **%69,4**. Çizgi ters yönde taşındı: **%16,1 / %12,5**.
**YORUM** Çizgi kırıldıktan sonra **geri dönüş** baskın (%63–69). Yani kırılma
**tek başına** yön değişimi değil; "kırıldı, devam eder" varsayımı bu veride
**azınlık** senaryo.
**DURUM** `GEÇERLİ*` — not: bu analiz ana sonuçlar görüldükten **sonra** planlandı
(belgede açıkça yazılı), keşifseldir.
**KAYNAK** [`stabil_destek_direnc_karsilastirma_2026_11_06/SONUC.md`](stabil_destek_direnc_karsilastirma_2026_11_06/SONUC.md)

---

### R31 · Stabil soru seti V2
**KAPSAM** 100 sembol · senaryo doğrulama/geçiş/teşhis tabloları
**ANA SAYI** `stabil_soru_seti_v2/` altında `genel_okuma`, `senaryo_dogrulama`,
`senaryo_gecis`, `senaryo_teshis` CSV'leri + manifest.
**YORUM** R19'un soru setini senaryo biçimine çeviren **sicil** çalışması; ayrı
bir bulgu iddiası yok. Sayı gerektiğinde R19'a, yöntem için buraya bakılır.
**DURUM** `SİCİL`
**KAYNAK** [`stabil_soru_seti_v2/`](stabil_soru_seti_v2/) · [`STABIL_SORU_SETI_V2_2026-11-08.md`](STABIL_SORU_SETI_V2_2026-11-08.md)

---

### §3.6 Pilot / keşif hattı

---

### R26 · Kaçırılan hareketler pilotu
**KAPSAM** **5 hisse** (ASTOR, THYAO, AKBNK, GARAN, TUPRS) · 1d son 400 / 1h son 800 mum
**ANA SAYI** 10 mumda bir karar penceresi; ±2 ATR korunmuş hareket tanımı;
%70 keşif / %30 ileri dönem. Ayrıntılı yüzdeler `sonuclar/kacirilan_pilot/`.
**YORUM** Bu bir **pilot**, bulgu değil: 5 hisse BIST'i temsil etmez ve örneklem
elle seçildi. Belgenin kendi ifadesiyle "tek bir sonuç bile doğrulanmış bulgu
sayılamaz". Değeri: **sistem şeması önerisi** (kaçırılan vs yanlış alarm ayrımı).
**DURUM** `GEÇERLİ` (pilot olarak)
**KAYNAK** [`KACIRILAN_HAREKETLER_PILOTU.md`](KACIRILAN_HAREKETLER_PILOTU.md)

---

### R27 · Çapraz piyasa keşfi
**KAPSAM** ASTOR + THYAO · 6 bağlam × 2 araçlıya kadar = 21 altküme
**ANA SAYI** STRICT_UNKNOWN: 2.268 gözlenen hücre, **0 tamamen bilinen koşul**.
İki günlük gecikme varsayımıyla 11.454 hücre / 8.394 bilinen satır. Keşifte seçilen
90 adayın 74'ü ileri dönemde **n<30**'a düştü; 16'sı kıyaslanabilir, hiçbiri
doğrulanmış bulgu değil. USDTRY'de **31 bozuk mum**.
**YORUM** Dürüst bir **"yapılamadı"** kaydı: veri kalitesi ve örneklem nedeniyle
çapraz piyasa etkisi **ölçülemedi**. Buradan "endeks hisseyi sürüklüyor" sonucu
çıkarılamaz.
**DURUM** `GEÇERLİ` (keşif; `UNADJUSTED_EXPLORATORY`)
**KAYNAK** [`CAPRAZ_PIYASA_UYGULAMA.md`](CAPRAZ_PIYASA_UYGULAMA.md) · [`CAPRAZ_PIYASA_REPLAY_TASLAGI.md`](CAPRAZ_PIYASA_REPLAY_TASLAGI.md)

---

### R28 · Deploy piyasa pilotu
**KAPSAM** 48 deploy hissesi × 12 endeks/makro · 1/5/10 işlem günü · **12 tekli + 66 ikili koşul**
**ANA SAYI** Keşif/ileri dönem ayrı; her hücre için n ve dönem yazılı.
Ayrıntı [`DEPLOY_PIYASA_PILOTU.md`](DEPLOY_PIYASA_PILOTU.md).
**YORUM** Kapsam **geniş**, iddia **dar**: tekli/ikili hücreler arasında seçim
yapılmış ve çoklu test düzeltmesi yapılmamış. "Şu endeks şu hisseyi şu kadar
sürükler" cümlesi buradan **kurulamaz**; yalnız hücre taraması olarak okunur.
**DURUM** `GEÇERLİ` (keşif)
**KAYNAK** [`DEPLOY_PIYASA_PILOTU.md`](DEPLOY_PIYASA_PILOTU.md) · [`DEPLOY_TEKLI_PIYASA_HUCRELERI.csv`](DEPLOY_TEKLI_PIYASA_HUCRELERI.csv)

---

### §3.7 Altyapı / sözleşme katmanları (replay değil, replay'i mümkün kılan şeyler)

---

### R32 · Yaşam tablosu + kolon sözlüğü
**KAPSAM** — · **ANA SAYI** — · **YORUM** Ölçümden **önce** okunması gereken iki
belge: her kolonun anlamı/birimi (KOLON_SOZLUGU) ve soru sicili (YASAM_TABLOSU).
Yeni bir soru yazmadan buraya bakılmazsa aynı soru ikinci kez ölçülür.
**DURUM** `SİCİL` · **KAYNAK** [`KOLON_SOZLUGU.md`](KOLON_SOZLUGU.md) · [`YASAM_TABLOSU.md`](YASAM_TABLOSU.md)

---

### R35 · Ampirik referans katmanı
**KAPSAM** 176×4 tabloları → kart satırı · **ANA SAYI** Kartta basılan her
`◇` satırı bir rapor tablosundan elle alınmıştır; kaynağı `KAYNAK_TABLOLARI`
sözlüğünde yazılı. Varsayılan **kapalı**.
**YORUM** Ölçümü **metne** bağlayan tek köprü. Ama kart metni artık **eski
veriyle** üretilmiş sayılara dayanıyor; native koşu bitince bu sözlüğün
güncellenmesi gerekir — yoksa kart doğru sayıyı **yanlış tabandan** basar.
**DURUM** `VERİ DEĞİŞTİ` (kaynak tablolar yenilenmeli)
**KAYNAK** [`AMPIRIK_REFERANS.md`](AMPIRIK_REFERANS.md) · [`ampirik_referans.py`](../../ampirik_referans.py)

---

### R36 · Native tutarlılık denetimi — "2h/4h gerçekten aynı barı mı anlatıyor?" (bu tur)
**KAPSAM** 174 sembol × 2 TF · native 2h/4h ↔ 1h kapanış karşılaştırması
**ANA SAYI** Kapanış medyan |fark| **2h %0,249 / 4h %0,212**; birebir aynı
kapanış yalnız **%3,5 / %4,0**; barların **%23 / %20**'si %0,5'ten fazla farklı.
Uyumsuz sembol **6 (2h) / 7 (4h)**: `KRTEK` %71, `CVKMD` %61, `SKBNK` %22,
`MARTI`, `CANTE`, `BJKAS` (+4h'de `GSRAY`, `SELVA`).
**YORUM** `resample_kullanildi=False` **doğru** ama yeterli değil: iki sağlayıcı
arasında %0,25'lik sistematik bir fiyat farkı var. Bu, ATR tabanlı bir eşiğin tam
sınırındaki sinyalleri düzenli olarak çevirir → **5 pp altı farklar gürültünün
altında kalabilir.** Ayrıca 1h dosyasında her gün 09:30'da hacmi 0 olan bir bar
var (%10,6); fiyatı gerçek, hacmi yok → RVOL/kuruma bağlamı orada bozuluyor.
**DURUM** `GEÇERLİ` (ölçüm bu veri seti için geçerli; veri yenilenirse tekrar koş)
**KAYNAK** [`NATIVE_TUTARLILIK.md`](../denetim/NATIVE_TUTARLILIK.md) · [`native_tutarlilik.py`](../../research/native_tutarlilik.py)

---

### R37 · Domain alarm replay — "hangi alarm türü gerçekten değerli?"
**KAPSAM** **176 sembol × 4 TF = 704 seri (TAM ARŞİV)** · 510.820 satır =
**334.191 tetik + 162.810 taban** · tetik başına 3/12/40 bar ATR yolu ·
canlı 6 bar cooldown · tetik anındaki 6 bağlam özelliği
**ANA SAYI**
- Tetik vs **taban** (12 bar, lehte ≥1 ATR): **%66,5 vs %64,1 → fazla +2,4 pp**
- Yön farkı (lehte − aleyhte): tetik **+4,1 pp**, taban **+0,0 pp**
- **Belirsizlik:** tetiklerin **%30,5**'i 12 barda *her iki yöne de* ≥1 ATR görüyor;
  tabanda %30,4 → **alarm belirsizliği azaltmıyor**
- Kanal (taban farkı): **HACIM +7,3** (n=8.213) · **FORMASYON +2,9** (142.458) ·
  **FVG +2,8** (29.578) · **OB +1,7** (186.541) · **CHoCH +0,9** (269) ·
  **BOS −2,0** (3.730; aleyhte %73,5, iki yöne de %36,2)
- **Cooldown:** 116.047 kart gönderildi, **218.144 tekrar susturuldu (%65,3)**.
  Gönderilen %67,4 vs susturulan %66,1 → **−1,3 pp**
- **En değerli segment:** HACIM × yukarı koşu **%74,7** (n=4.075, z=+13,9) ·
  HACIM × 09:00 **%75,4** · FORMASYON × yukarı koşu %69,6 (n=34.898, z=+19,5)
- 102 segmentin **74'ü anlamlı iyi, 7'si anlamlı kötü**, 21'i anlamsız.
  Anlamlı kötülerin **tamamı BOS kanalında** (yukarı koşu −4,8 pp, hacim canlı −5,1 pp)
**YORUM** Dört hüküm:
1. **Kanal seçimi değer yaratıyor ve sıralama net:** HACIM (+7,3 pp) → FORMASYON
   (+2,9) ≈ FVG (+2,8) → OB (+1,7) → CHoCH (+0,9) → **BOS (−2,0)**. BOS tek
   başına alarm olarak **zararlı**: tetiklediğinde 12 barda aleyhte ≥1 ATR görme
   oranı %73,5 ve "iki yöne de" %36,2 (taban %30,4) — yani yön vermiyor, gürültü
   ekliyor. Susturulacak ilk kanal bu.
2. **HACIM istisnası gerçek ve büyük.** 8.213 tetikte +7,3 pp; alt segmentlerinde
   %71–77. Hacim "yön teyidi" değil (R01/R07/R20 ile uyumlu) ama **"burada bir
   hareket olacak"** sinyali olarak ölçülebilir biçimde en güçlü kanal.
3. **Alarm oynaklık işaret ediyor, yön değil.** Tetiklerin %30,5'i iki yöne de
   ≥1 ATR görüyor (taban %30,4 — fark yok). Yön farkı +4,1 pp gerçek ama küçük.
   Kullanıcının "belirsizlik değil, yön hissi" talebi **mevcut kanallarla
   karşılanamıyor**; bu ölçüm bunu sayıyla söylüyor.
4. **Cooldown doğru:** 2 tekrardan 1'inden fazlası (%65,3) susturuluyor ve
   susturulanlar gönderilenlerden farksız. Yani alarm yorgunluğunun üçte ikisi
   bilgi taşımayan tekrar.
**DURUM** `GEÇERLİ` — tam arşiv (704/704 seri), hata 0. 44 sembollük ara koşuyla
aynı yönde (HACIM +8,4 → +7,3; BOS −1,6 → −2,0): örneklem büyüdükçe farklar
**küçüldü ama sıralama değişmedi**.
**KAYNAK** [`DOMAIN_ALARM_REPLAY.md`](DOMAIN_ALARM_REPLAY.md) · [`domain_alarm_replay.py`](../../research/domain_alarm_replay.py) · [`test_domain_alarm_replay.py`](../../test_domain_alarm_replay.py) (38 test)
---

### R33 · Telegram DM replay eğitimi · R34 · Alarm context prototipi
**R33** kullanıcıya soru-cevap soran **ürün**; ölçüm koşusu değil.
[`TELEGRAM_DM_REPLAY_EGITIM_MODU.md`](../tasarim/TELEGRAM_DM_REPLAY_EGITIM_MODU.md)
**R34** 10 sembol için no-lookahead JSON bağlam paketi prototipi; canlı davranışı
değiştirmez. [`ALARM_CONTEXT_API_PLANI.md`](ALARM_CONTEXT_API_PLANI.md)
**DURUM** `GEÇERLİ`

---

## 4 · Replay'lerin kesişiminde tekrar eden 9 şey

Bu liste, onlarca ayrı çalışmanın **aynı yöne** işaret ettiği maddelerdir. Tek tek
sayılar değişse de yön aynı kaldığı için en güvenilir bilgi bunlar.

1. **Seviye "nereden döner"i söylemiyor, "ne kadar oynar"ı söylüyor.**
   R01 (%65 tepki ama %90 geçilme) + R02 (MFE≈MAE, NET≈0) + R22 (tepki %41 vs ters %51)
   aynı şeyi üç ayrı yoldan söylüyor.

2. **Tekrarlanan temas = tükenme, ilk temaslar dağınık.**
   R01 (FVG tek kullanımlık, OB tekrar denenir) + R19 (2. temas en iyi, 3.–4. temas
   −0,67 ATR ve %48,5 kırılma) + R21 (ok tekrarı %89).

3. **Kalite puanı ayırt etmiyor.**
   R05 (her tip 80–86) + R06 (bileşenler birbirini götürüyor) + R08 (puan kurulamaz) —
   üç bağımsız çalışma, aynı hüküm.

4. **Hacim yön teyidi değil.**
   R01 (Q4 dokunuşta en zayıf tepki) + R07 (hacim özellikleri geçmedi) + R20
   (hacim grubu zayıf tepkiyi açıklamıyor).

5. **Kırılım olayının kendisi rastgele girişten zar zor ayrılıyor (+1–2 pp).**
   R06 (+1,5 pp) + R08 (+1,5 pp, ön-kayıtlı) + R11 (maliyetle −0,01 ATR).

6. **Kazanç seçicilikten gelmeli, ayar/katmandan değil.**
   R13 (geometri çalışıyor, hüküm katmanı katmıyor) + R17 (20 kuralın hiçbiri geçmedi)
   + R15 (holdout'ta katkı kayboldu) + R08.

7. **Aşağı yön bu dönemde sistematik olarak daha iyi.**
   R09 (%49,3 vs %25,8) + R10 (4h −0,67 vs +0,81). **Uyarı:** tek rejim;
   kalıcı üstünlük değil.

8. **En büyük risk erken/yüksekten giriş, stop ayarı değil.**
   R14 (stopların %90'ı) + R11 (dar stop pişmanlığı %4) + R17 (erken çık refleksi
   kazandırmıyor).

9. **Alarm oynaklık işaret ediyor, yön değil.** (bu tur eklendi — R37)
   Tetiklerin %30,5'i 12 barda *iki yöne de* ≥1 ATR görüyor; taban örneklemde bu
   oran %30,4. Yani alarm "burada bir şey olacak" diyor, "şu yöne gidecek"
   demiyor. Bu, 1–8. maddelerin **alarm tarafındaki karşılığı**: yön üstünlüğü
   kurulamıyorsa kartın işi **dikkat yönetimi** olmalı, tahmin değil.

---

## 5 · "Yazı tura kadar" olanlar — pozitifler kadar açık

Bunlar **kaybedilmiş** bulgular değil; ölçülmüş **belirsizlikler**. Depo bunları
saklamıyor, yazıyor.

| Bulgu | Sayı | Neden yazı tura |
|---|---|---|
| Zone dokunuşu → yön | MFE≈MAE≈2,0 ATR, NET≈0 | İki yöne de aynı büyüklükte gidiyor |
| Stabil çizgiye değmek | sıradan 20 günlük dipten farksız (`H01/H02`) | Çizginin kendisi bilgi taşımıyor |
| Destek vs direnç simetrisi | +1,1 pp, GA −9,2…+11,6 | Güven aralığı sıfırı içeriyor |
| Eşleştirilmiş direnç testi | +0,0 pp (53 çift) | Tam eşit |
| Taze zone avantajı | ≤10 bar %65,7 vs ≥40 bar %69,6 | Beklenenin **tersi**, etki yok |
| Zone yaşı (OB) | −2,7 pp | <5 pp eşiği |
| Kalite puanı × sonuç | aile içinde eriyor | Bileşenler birbirini götürüyor |
| Endeks rejimi filtresi | 28 varyantın hiçbiri geçmedi | Stopları elemek ≈ kârlı işlemleri elemek |
| Kâr görüp dönenleri önceden ayırma | 24 gözlemin hiçbiri geçmedi | Engel/takılma iki grupta aynı sıklıkta |

**Bu tablo neden değerli:** "yazı tura" bilgisi, yanlış bir kuralın canlıya
girmesini engeller. R21'in düzeltmesi (513 ok silindi, ▲'lere dokunulmadı) bu
ilkenin çalışan örneği.

---

## 5.5 · Native verinin kendi kontrolü — "aynı barı mı anlatıyor?"

Bu tur eklenen **veri kalitesi** bulgusu; bütün 2h/4h sayılarının tavanını
belirlediği için ayrı bölüm.

`manifest.json` `resample_kullanildi=False` diyor ve bu doğru: 2h/4h dosyaları
1h'den **türetilmedi**, TradingView'den native geldi. Ama "native" olmak "1h ile
tutarlı" olmak demek değil — farklı sağlayıcı ve farklı kova çapası (09:00 vs
09:30) kullanıldı. Ölçtüm (`python -m research.native_tutarlilik`, 174 sembol):

| TF | kapanış medyan \|fark\| | p95 | birebir aynı kapanış | >%0,5 fark eden bar | uyumsuz sembol |
|---|---|---|---|---|
| 2h | **%0,249** | %1,15 | %3,5 | %23 | **6 / 174** |
| 4h | **%0,212** | %1,03 | %4,0 | %20 | **7 / 174** |

- **%0,2–0,3 medyan fark beklenen düzey** (çapa + sağlayıcı farkı). Bu düzeyde
  2h/4h sayıları kullanılabilir; ama bir sinyal tam eşik sınırında tetikleniyorsa
  iki seride farklı sonuç verir.
- **Kapanışların yalnız %3,5'i birebir aynı.** "Resample yok" doğru olsa da
  "aynı veri" değil. İki sağlayıcı arasında ortalama %0,25'lik bir fiyat farkı
  var; ATR tabanlı bir eşiğin (ör. 1 ATR) tam sınırında bu düzenli olarak
  sinyal çevirir.
- **Uyumsuz semboller** (medyan fark > %0,5): 2h'de `KRTEK` (%71), `CVKMD` (%61),
  `SKBNK` (%22), `MARTI`, `CANTE`, `BJKAS`; 4h'de aynı küme + `GSRAY`, `SELVA`.
  Bunlarda 2h/4h ile 1h **çelişiyor**; o sembollerin 2h/4h sayıları ayrıca
  işaretlenmeli. `MARTI`/`CANTE`/`SELVA` p95'te %16–41'e çıkıyor → serinin bir
  bölümünde ciddi ayrışma var (bedelsiz/split veya sağlayıcı boşluğu).
- Ayrıca **1h dosyasında her gün 09:30'da hacmi 0 olan bir bar var** (%10,6'sı).
  OHLC'si düz değil, yani gerçek bir fiyat taşıyor; canlı sistemde RVOL hesabı bu
  barlarda 0 hacim görür. Alarmın HACIM kanalı bu yüzden günde bir kez yanlış
  "hacim yok" bağlamı görebilir — 5×/10× eşiği tetiklenmez ama "kuruma" tipi
  bağlam ölçümleri bu barda bozulur (bknz. `bagl_hacim_kuruma`).

**Sonuç:** 2h/4h'ye dayanan her yeni sayı bu %0,2–0,3 gürültü tabanıyla
okunmalı; 5 pp'den küçük farklar bu gürültünün altında kalabilir.

---

## 5.7 · NATIVE SONUÇLAR — eski sayılarla yan yana (TAM EVREN)

**176 sembol × 4 TF = 704 seri, hata 0.** Aşağıdaki her satır iki bağımsız koşunun
karşılaştırması: sol taraf eski (2h/4h **türetilmiş**), sağ taraf bu tur (**native**).

| Ne | Eski (türetilmiş) | **Yeni (native, 176 sembol)** | Hüküm |
|---|---|---|---|
| Zone temas (OB, 1h) | %94 civarı | **%94,4** (1h) / %92,6 (2h) / %93,0 (4h) | **Aynı** |
| OB geçilme (violation) | %90+ | **%85,2–%93,3** | **Aynı** — seviye yön söylemiyor |
| FVG tek deneme | %71,9 (1d) | **%71,1 (1d) / %76,1 (4h)** | **Aynı** — FVG tek kullanımlık |
| OB tek deneme | %61,0 | **%59,6–%59,9** | **Aynı** — OB tekrar denenir |
| Dokunuş tepkisi "çalıştı" (OB) | ~%65 | **%64,8 (1d) – %66,7 (1h)** | **Aynı** — %4'lük yön avantajı |
| Ters tepki (OB) | ~%15 | **%13,7–%15,6** | **Aynı** |
| Zone ömrü × yükseklik | — | OB **0,95–0,96 ATR**, FVG 0,63–0,72 ATR | Yeni |
| `ORT_İz` tepe h40 | ≈3,8 ATR | **3,74–3,93 ATR** | **Aynı** |
| Formasyon sayısı | 33.964 | **24.615** (704 seri) | **DEĞİŞTİ** (−%28) |
| Formasyon tamamlanma | %76,2 | **%74,4** (n=23.012) | **Aynı** (−1,8 pp) |
| Formasyon tipi/kalite | 80–86 | **78–85**, tip ayrımı yok | **Aynı** |
| **Retest oranı** | %34,9 | **%40,8** (GA %40,2–%41,5) | **DEĞİŞTİ** (+5,9 pp) |
| **Retest derinliği** | — | **<0,25 ATR %61,7 vs ≥0,5 ATR %35,5** | Yeni, güçlü (26 pp) |
| **Retest hacmi (rvol)** | — | düşük %39,4 vs yüksek %45,6 · **+6,2 pp** (GA +4,0…+8,2) | Yeni, güçlü |
| **Formasyon ↔ MS yön uyumu** | — | uyumlu **%79,3** vs uyumsuz **%69,6** · **+9,6 pp** (GA +8,4…+10,7) | Yeni, güçlü |
| MS BOS "CALISTI" | — | **%66,6–%70,3** (4h en yüksek) | Yeni |
| MS yön asimetrisi | "aşağı daha iyi" (R09/R10) | 1d **UP %75,9 vs DOWN %60,9**; 44 sembolde aynı | **TERS DÖNDÜ** |

### Bu tablodan çıkan dört hüküm

1. **Yapısal bulgular native veride de ayakta.** "OB tekrar denenir, FVG tek
   kullanımlıktır", "seviye oynaklık ölçer, yön ölçmez", "formasyon kalitesi
   tipi ayırt etmez" — üçü de neredeyse birebir aynı çıktı. **R01/R02/R05'in
   ana hükmü veri değişikliğinden etkilenmedi.** Derlemenin en sağlam haberi bu.
2. **Yön asimetrisi ters döndü ve bu iki koşuda da aynı.** Eski kırılım/teyit
   çalışması (R09/R10) "aşağı yön daha iyi" diyordu; native veride 1d'de
   **yukarı BOS %75,9, aşağı %60,9**. R09/R10'un kendi uyarısı ("tek rejim,
   kalıcı değil") böylece **iki bağımsız gözlemle** doğrulandı. Yön asimetrisi
   kural değil, dönemin özelliği.
3. **En kullanışlı yeni bulgu retest tarafında ve tam evrende de duruyor.**
   Retest oranı %40,8 (eskiden %34,9) — yani formasyonların **beşte ikisi**
   kırılımdan sonra geri dönüyor. Ve retestin **niteliği** sonucu belirliyor:
   sığ retest (<0,25 ATR) %61,7, derin retest (≥0,5 ATR) %35,5 → **26 pp**,
   derlemedeki en büyük tek etki. Retest hacmi (+6,2 pp) ve formasyon–MS yön
   uyumu (+9,6 pp) GA'ları sıfırı içermiyor.
   **Kart metninde kullanılabilir; ama önce ayrı pencerede tekrar test
   edilmeli** (raporun kendi kuralı: tanımlayıcı bulgu ≠ kural).
4. **Formasyon sayısı %28 düştü (33.964 → 24.615).** Oranlar aynı kaldığı için
   bu bir "bulgu kaybı" değil, **türetilmiş 2h/4h'nin daha fazla sahte formasyon
   ürettiğinin** göstergesi. Aynı şey BOS/CHoCH sayılarında da görülüyor:
   1h'de üretilen, 2h/4h'de üretilmeyen yapılar vardı.

### Uyarılar

- Bu artık **tam evren** (704/704 seri, 176 sembol). 44 sembollük ara koşuyla
  aynı yönde: farklar küçüldü, **sıralama değişmedi** (ör. retest derinliği
  26 pp → 26 pp; formasyon–MS uyumu +10,1 → +9,6 pp).
- `1h`'de FVG yok (bilinen kısıt): FVG satırları 2h/4h/1d'ye aittir.
- Native 2h/4h ile 1h arasında medyan %0,2–0,3 fiyat farkı var (§5.5); 5 pp
  altındaki iyileşmeler bu gürültüyle ayrıştırılamaz. Buradaki farklar (26 pp,
  +9,6 pp, +6,2 pp) gürültünün **çok üstünde**.

**KAYNAK** [`ARASTIRMA_BULGULARI.md`](ARASTIRMA_BULGULARI.md) (ham tablolar) ·
[`FORMASYON_SONUCLARI.md`](FORMASYON_SONUCLARI.md) (FRM-01…20)

---

## 5.8 · ÜÇ AİLE, TEK SORU — Stabil / OB / FVG gerçekten ne biliyor?

Bu bölüm üç aileyi **aynı soruyla** karşılaştırıyor: *"Bu yapı bana ne söylüyor,
ne söylemiyor?"* Sayılar §5.7 (OB/FVG, native 176 sembol) ve R19/R21/R22/R24
(Stabil) kartlarından.

### Karşılaştırma — 8 soruda üç aile

| Soru | **STABİL** (günlük çizgi) | **OB** (order block) | **FVG** (boşluk) |
|---|---|---|---|
| **1. Temas tepkisi** | çizgiye değmek sıradan 20 günlük dipten **farksız** (H01/H02) | **%64,8** beklenen yönde ≥1 ATR | %64,8 |
| **2. Geçilme oranı** | çizgi pes ediyor: %55 (1,2+ ATR göçte) | **%85–93** geçiliyor | %77 temas, geçilme ölçülmüyor |
| **3. Tekrar davranışı** | **2. temas en iyi** (+0,32 ATR/16×4H), **3.–4. temas −0,67 ATR** | **tekrar denenir** (3+ temas %12,7) | **tek kullanımlık** (3+ temas %0,0) |
| **4. Yükseklik/genişlik** | çizgi uzunluğu değil, **eğim** belirleyici | yükseklik kovası: ≥2 ATR'de tepki %68,9 (1d) | ≥2 ATR'de **%70,4** (1d), %73,7 (4h) — **en yüksek tepki** |
| **5. Hacim etkisi** | hacim grubu zayıf tepkiyi **açıklamıyor** (R20) | Q1 %66,9 → **Q4 %61,4** (1h, ters) | aynı ters ilişki |
| **6. En güçlü ayrıştırıcı** | **bağlam/rejim**: sindire sindire yükseliş %42,7 vs dik fırlama %19,0 | **tekrar sayısı** + MS yönü | **tek kullanımlık olması** |
| **7. Sinyal olarak değeri** | ok üretimi: 1.315 okun **%89'u ▼ aynı uyarının tekrarı**, %79 şüpheli | +1,7 pp (alarm ölçümü) | +2,8 pp |
| **8. Ne ZAMAN değerli** | fiyat çizgiden **1–2 ATR** uzaktayken (başabaş), >2 ATR'de dönüş %12,8'e düşer | MS yönüyle **uyumlu** kırılımda (%79,3 vs %69,6) | **taze** ve **geniş** olduğunda; ikinci temasta değil |

### Üç ayrı hüküm

**1. Stabil ≠ OB ≠ FVG; üçü farklı iş yapıyor.**
- **Stabil** bir **rejim/bağlam** aracı: "çizgi ne kadar süredir, hangi eğimle
  tutuluyor" sorusuna cevap veriyor. Tek başına temas bilgisi değersiz (H01/H02),
  ama **eğim + temas sayısı** birleşince depodaki en güçlü davranışsal bulgu
  kümesini üretiyor (R19).
- **OB** bir **tekrar/bölge** aracı: sürekli yeniden test edilen, bu yüzden tek
  başına "giriş noktası" olmayan bir alan. Değeri **MS yönüyle uyumda**.
- **FVG** bir **tek atımlık** araç: doldurulduğunda işi bitiyor, ikinci temas
  yok. Değeri **tazelik + genişlik**te.

**2. Üçünde de ortak olan tek şey: hacim yön söylemiyor.** OB'de Q4 %61,4
(Q1 %66,9), Stabil'de hacim grubu zayıf tepkiyi açıklamıyor, FVG'de aynı ters
ilişki. Ama §5.8'in alarm tarafında (R37) hacim **+7,3 pp** ile en güçlü kanal.
Çelişki değil: **hacim yönü değil, "hareket olacak"ı** söylüyor. Bu ayrım
kart metninde kritik — "hacim teyit etti" yazmak ölçümle **çelişir**;
"hacim dikkat çekiyor" yazmak ölçümle **uyumlu**.

**3. Üçü de "buradan döner" demiyor.** Temas sonrası ters yön olasılığı
(~%15–20) beklenen yönle (~%65) birlikte yaşıyor ve geçilme oranı %77–93.
Yani hiçbiri **seviye tahmini** aracı değil; **oynaklık/zamanlama** aracı.
R22'nin "destek ↔ direnç simetrik, ters tarafa gitme daha olası" bulgusu bunun
en net ifadesi.

### Pratik sonuç: üçünü nasıl birlikte kullanmalı

| Durum | Kullan | Kullanma |
|---|---|---|
| Fiyat OB'ye **ilk kez** değdi + MS yönü uyumlu | OB'yi **bölge** olarak işaretle, teyit bekle | "destek tuttu" diye kart basma |
| FVG **taze** ve **≥1 ATR geniş** | FVG'yi tek seferlik hedef/tepki alanı | ikinci teması bekleme (yok) |
| Stabil çizgi **2. temasta** ve **yataylaşmış** | en güçlü kombinasyon (R19: %42,7 takip) | 3.+ temasta aynı şeyi söyleme (−0,67 ATR) |
| Hacim yüksek | "hareket olabilir" bağlamı | "yön teyit edildi" |

## 5.9 · Alarm yönü — ölçüm ne diyorsa o

Ölçüm bir **yön** veriyor; ayrıntı [`ALARM_YONU_2026-11-19.md`](ALARM_YONU_2026-11-19.md).
Tek cümle:

> **Alarm "olay bildiricisi" olarak çalışıyor; ölçüm "nadirlik dedektörü" olmasını
> söylüyor.** Taban oranı %64,1; alarmlı barlarda %66,5. Fark +2,4 pp.

En sert kanıt **kapsam ↔ değer ters oranı**: tetiklerin **%56'sı OB** (+1,7 pp),
**%2,5'i HACIM** (+7,3 pp). Ve **kombinasyon seyreltıyor**: HACIM tek başına
%71,6 → HACIM+OB %67,9 → FORMASYON+HACIM+OB %65,9. Mevcut sistem tam tersini
varsayıyor ("çok kanal = güçlü").

Önerilen 4 katman: **0 sessiz** (yalnız OB/FVG/BOS) · **1 günlük özet satırı**
(formasyon state) · **2 kart** (HACIM ≥5× veya HACIM+FORMASYON) · **3 grafik**
(katman 2 + 09–10 / 17 seansı). Grafik kuralı: **yön oku değil, aralık konisi** —
çünkü tetiklerin %30,5'i iki yöne de ≥1 ATR görüyor.

---

**KAYNAK** §5.7 (R01/R02/R05 native) · R19/R20/R21/R22/R24 · R37

---

## 6 · Bundan sonra: ne yeniden koşulacak, hangi sırayla

Native veri geldiği için **2h/4h'ye dayanan her sayı** yeniden üretilmeli. Ama
hepsini birden koşmak gerekmez; bağımlılık sırası var:

| Sıra | İş | Neden bu sırada | Komut |
|---|---|---|---|
| **1** | Ana arşiv ölçümü (R01/R02/R05) | **BİTTİ — 704/704 seri, hata 0** (§5.7) | `python scripts/backfill/arastirma_kosu.py` + `--agrega` |
| **2** | S01–S32 cevapları (R04) | 1'in çıktısını okur | `python -m research.soru_cevaplama` |
| **3** | Formasyon kartları (R05) | 1'in çıktısını okur | aynı koşunun `--agrega` adımı |
| **4** | Kırılım/teyit (R09/R10/R11) | Kendi replay'i, 696 seri | `python scripts/kirilim_replay.py` |
| **5** | Stabil hattı (R19/R21) | 1d native ama 4h türetim → native 4h ile tekrar | `python -m research.stabil_replay` |
| **6** | Ampirik referans tabloları (R35) | Kart metnini yeni sayılara bağlar | elle: yeni tablolardan satır güncelleme |

Bu turda **1. sıra BİTTİ** (704 iş, native, `resample_kullanildi=false`, hata 0) ve
**7. sıra** olarak aşağıdaki uçtan uca hat eklendi (canlı alarm tetikleyicilerinin
arşivde ölçümü — derlemedeki R21/R24/R29 derslerinin doğal devamı):

| Sıra | İş | Neden | Komut |
|---|---|---|---|
| **7** | Domain alarm ölçümü | Hangi alarm kanalı gerçekten değerli? Canlı eşiklerin birebir kopyası + kontrol örneklemi | `python -m research.domain_alarm_replay --havuz-disi-dahil` |
| **0** | Veri tutarlılığı (ön koşul) | 2h/4h'nin 1h ile aynı barı anlatıp anlatmadığı; bütün 2h/4h sayılarının gürültü tabanı | `python -m research.native_tutarlilik` |

Diğer sıralar onun çıktısına bağlı olduğu için bekliyor.

**Yeniden koşulmayacaklar:** R18 (`GEÇERSİZ`, sızıntı), R26/R27/R28 (pilot/keşif;
yeni veriyle anlam kazanmaz), R29 (düzeltildi, konu kapandı), R32/R31 (sicil).

---

## 7 · Dosya haritası

| Ne arıyorsun | Nereye bak |
|---|---|
| Ham ölçüm çıktıları (JSONL) | `arastirma_cikti/` (git dışı) |
| Üretilen rapor | [`ARASTIRMA_BULGULARI.md`](ARASTIRMA_BULGULARI.md) |
| Soruların cevapları | [`ARASTIRMA_SONUCLARI.md`](ARASTIRMA_SONUCLARI.md) |
| Yöntem ve anti-lookahead | [`ARASTIRMA_HATTI.md`](ARASTIRMA_HATTI.md) |
| S01–S32 sözleşmesi / cevapları | [`REPLAY_SORU_SETI_2026-10-29.md`](REPLAY_SORU_SETI_2026-10-29.md) · [`REPLAY_SORU_YANITLARI_2026-10-29.md`](REPLAY_SORU_YANITLARI_2026-10-29.md) |
| Formasyon kartları | [`FORMASYON_SONUCLARI.md`](FORMASYON_SONUCLARI.md) |
| Senaryo/gölge sonuçları | [`sonuclar/golge_zincir/`](sonuclar/golge_zincir/) · [`sonuclar/golge_v2/`](sonuclar/golge_v2/) · `golge_zincir_*` belgeleri |
| Kırılım/teyit | [`KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md`](KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md) · [`sonuclar/kirilim_replay/`](sonuclar/kirilim_replay/) |
| Stabil | [`STABIL_REHBERI.md`](STABIL_REHBERI.md) · [`STABIL_REPLAY_HATLARI.md`](STABIL_REPLAY_HATLARI.md) · `stabil_*/` dizinleri |
| Kolon/terminoloji | [`KOLON_SOZLUGU.md`](KOLON_SOZLUGU.md) · [`YASAM_TABLOSU.md`](YASAM_TABLOSU.md) |
| Veri güvenilirliği | [`VERI_KULLANIM_VE_GUVENILIRLIK_2026-10-30.md`](VERI_KULLANIM_VE_GUVENILIRLIK_2026-10-30.md) |
| Bu derlemenin alarm tarafı | [`DOMAIN_ALARM_REPLAY.md`](DOMAIN_ALARM_REPLAY.md) · üretici: `research/domain_alarm_replay.py` |

---

## 7.5 · Karar tablosu — bugün **hangi kurala güvenilebilir, hangisine güvenilemez**

Bu dosya bir başvuru kaynağı olarak kullanılacaksa tek ekran bu. "Bugün canlıda
ne yapabilirim?" sorusunun derlemeden çıkan cevabı:

| Karar | Dayanak | Neden |
|---|---|---|
| **Yapılabilir:** Sabit seviyeyi "şuradan döner" diye **kart metninde** kullanmak | R01, R02, R22 | Seviye oynaklığı ölçüyor (%65 temas), yönü değil |
| **Yapılabilir:** Tekrarlanan temasları "tükenme" olarak işaretlemek | R19, R21 | 3.–4. temas −0,67 ATR ve %48,5 kırılma; en güçlü ve tutarlı bulgu |
| **Yapılabilir:** Hacmi *yön teyidi* değil, *dikkat* sinyali saymak | R01, R07, R20, R37 | Hacim yön ayırt etmiyor ama ≥1 ATR oranını **+7,3 pp** yükseltiyor (en güçlü kanal, n=8.213) |
| **Yapılabilir:** Alarm sıklığını cooldown ile sınırlamak | R37 | Tetiklerin **%65,3**'ü tekrar; susturulanlar gönderilenlerden farksız (%66,1 vs %67,4), yani sıklık değer eklemiyor |
| **Yapılabilir:** FVG'ye *tek kullanımlık* muamele | R01, §5.7 | Tekrar denendiğinde tepki düşüyor — native veride de aynı (%76,2 tek deneme) |
| **Aday (önce ayrı pencerede test):** Retest niteliğini karta yazmak | §5.7 | Sığ retest (<0,25 ATR) **%61,7** vs derin retest (≥0,5 ATR) **%35,5** — **26 pp**, derlemedeki en büyük tek etki. 704 seride de duruyor ama tek dönemde ölçüldü |
| **Yapılabilir:** Alarmı **katmanlamak** (sessiz / günlük özet / kart / grafik) | R37, §5.9 | HACIM +7,3 · OB +1,7 · BOS −2,0 → tek tek kart basmak değer üretmiyor |
| **Güvenilemez:** "Çok kanal ateşledi = güçlü sinyal" | R37 §2 | HACIM tek başına %71,6; HACIM+OB %67,9; üçü birlikte %65,9 → **kombinasyon seyreltıyor** |
| **Güvenilemez:** Grafikte **yön oku** | R21, R37 | Okların %89'u aynı uyarının tekrarı; tetiklerin %30,5'i iki yöne de ≥1 ATR |
| **Güvenilemez:** Alarmı "burada şu olacak" diye sunmak | R37 | Tetiklerin **%30,5**'i 12 barda iki yöne de ≥1 ATR görüyor (taban %30,4) — alarm oynaklık işaret ediyor, yön değil |
| **Aday (önce ayrı pencerede test):** Formasyon yönü ile MS yönü uyumunu karta yazmak | §5.7 (FRM-20) | Uyumlu **%79,3** vs uyumsuz **%69,6** = **+9,6 pp** (GA +8,4…+10,7), n=22.738 |
| **Güvenilemez:** Kalite/puan ile eleme | R05, R06, R08 | Üç bağımsız çalışma aynı hükmü verdi |
| **Güvenilemez:** Kırılımı tek başına sinyal saymak | R06, R08, R11 | Rastgele girişten +1,5 pp; maliyetle −0,01 ATR |
| **Güvenilemez:** "Yukarı teyit al" / "aşağı teyit al" kuralı | R09, R10 | Aşağı lehine asimetri **tek rejim**; kalıcı değil |
| **Güvenilemez:** 5 pp altındaki her iyileşme | R36 | Native 2h/4h ↔ 1h gürültü tabanı %0,2–0,3 kapanış = eşik sınırında sinyal çevirir |
| **Güvenilemez:** Stop/hedef ayarını değiştirerek kurtarmak | R11, R14 | Dar stop pişmanlığı yalnız %4; sorun giriş zamanı |
| **Yasak:** R18'in herhangi bir sayısı | R18 | G5 gelecek barı okuyordu |

**Bu tabloyu kullanma kuralı:** Sağ sütunda bir kart ID'si yoksa, o karar bu
derlemeden **desteklenmiyor** demektir — desteklenmediği de yazılıdır.

---

## 8 · Sınırlar (dürüstlük notu)

- **Tek 365 günlük rejim.** Bütün sayılar aynı piyasa döneminden; rejim değişince
  özellikle **yön asimetrisi** (madde 7) dönebilir.
- **Evren BIST likit 176 hisse**; küçük hisseler temsil edilmiyor. `BRENT` havuz dışı.
  Derlemedeki yeni ölçümler (R36/R37/§5.7) **tam 176 sembol** ile üretildi; eski
  kartların bir kısmı 174/100/50/48 sembolle üretilmişti — karşılaştırırken evren
  farkı akılda tutulmalı.
- **Bunlar backtest değil.** Maliyet, kayma, pozisyon boyutu ve çıkış kuralı çoğu
  çalışmada yok. "%65 çalıştı" kârlılık değil, yönlü uzanım sıklığı.
- **Bu derleme ikinci el.** Sayılar kaynak belgelerden alındı, yeniden hesaplanmadı;
  bir sayı ile kaynağı çelişirse **kaynak doğrudur**.
- **Eski türetilmiş 2h/4h'ye dayanan her sayı** yeni replay'in sonucu olarak
  kullanılamaz. Bu, listedeki kartların çoğunluğu için geçerli.
- **Native veri de tek başına "temiz veri" değil.** 2h/4h ile 1h arasında medyan
  %0,2–0,3 kapanış farkı var (§5.5). Bu fark, özellikle eşik sınırında tetiklenen
  sinyalleri çevirebilir; **5 pp altındaki iyileşmeler bu gürültüyle ayrılamaz.**
- **`1h`'de FVG yok.** FVG'ye dair her cümle 2h/4h/1d için geçerlidir.
- **Hacmi 0 olan 09:30 barı.** 1h arşivinde her gün bir tane var (%10,6); fiyatı
  gerçek, hacmi yok. Hacim/RVOL tabanlı ölçümlerde bu barlar özel işlenmezse
  "kuruma" gibi yanlış bağlam okumaları üretir.
- **Envanterdeki 37 kartın 37'si bulgu değil.** 5'i `PLAN`/`SİCİL`, 1'i `GEÇERSİZ`;
  gerçek karar tabanı olabilecek kart sayısı ~20 ve çoğu `VERİ DEĞİŞTİ`.
