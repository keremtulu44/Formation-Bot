# Stabil — V2 soru seti: ana sorular (onay taslağı)

**Tarih:** 2026-11-08 · **Durum:** ÖNERİ — kullanıcı onayı bekliyor · **Kod:** henüz yok
[Ana rehber](STABIL_REHBERI.md) · [Eski 48 soru sicili (A–H, legacy)](STABIL_DAVRANIS_SORULARI.md) ·
[Sistem incelemesi](STABIL_SISTEM_INCELEMESI_2026-11-08.md) · [Replay hattı sözleşmesi](STABIL_REPLAY_HATLARI.md) ·
Makine okunur: [`stabil_soru_seti_v2/manifest.json`](stabil_soru_seti_v2/manifest.json)

Bu dosya **48 soruluk yeni bir sicil değildir**. Amaç, önce üzerinde anlaşacağımız **8 ana soruyu**
seçmek; her ana sorunun alt hücrelerini ve domain sütunlarını ölçümden **önce** sabitlemek. Alt
sorular (V2-01a, V2-01b…) ancak ana soru onaylandıktan sonra açılır.

Eski A–H sicili **legacy** olarak donar: kimlikleri, cevapları ve ölçüm eşlemesi değişmez; V2
kimlikleri onunla karışmaz. Bir V2 sorusu eski bir soruyla aynı şeyi ölçüyorsa bu, o satırda
"miras" alanında yazılır (kopyalamak yok).

---

## 0. Kararlar (bu turda kilitlenen)

| Konu | Karar | Kaynak |
|---|---|---|
| Başarı ölçüsü | **İkisi birden**: (a) ±1 ATR ilk dokunma, (b) sabit ufukta kapanış işareti. Çelişen olaylar ayrı hücre. | Kullanıcı |
| Örneklem bölmesi | **Sembol bölmeli**: %60 keşif / %40 doğrulama, sembol hash'i ile deterministik. | Kullanıcı |
| Gruplama ekseni | **İki ayrı eksen**: native yaşam döngüsü (durum/yaş/rejim) × geometrik mesafe (ATR bandı). | Kullanıcı |
| Mum birimi | **Günlük ATR** (girişte dondurulmuş ATR14). 4s ATR yalnız ek sütun. | Kullanıcı |
| Sicil yapısı | **Yeni V2 ID uzayı** + JSON manifest; A–H legacy. | Ajan kararı |
| Dallanma | **3 seviye**: sonuç → mum anatomisi → domain → **kalan artık hücresi** (artık zorunlu). | Ajan kararı |
| Minimum hücre | Ana kütle **n≥100**; alt hücre **n≥30**. Altında yüzde yazılmaz, "yetersiz örneklem (n=..)" yazılır. | Ajan kararı |

---

## 1. Yöntem: sonucu parçalayıp nedenini soyma

Her ana soru aynı iskeleti kullanır. Sıra **sabittir**; katman atlanmaz.

1. **Kütle** — olay tanımı ve sayısı (nedensel: yalnız o an bilinen bilgi).
2. **Sonuç bölünmesi** — ör. %70 yukarı / %30 aşağı. Bu bölünme tek başına bulgu değildir.
3. **Azınlık hücresi** — bölünmenin küçük tarafı ayrı kütle olarak alınır.
4. **Mum anatomisi katmanı** — azınlığın ortak noktası ne? (gövde, kapanış pozisyonu, aralık, fitiller)
5. **Domain katmanı** — mum katmanı açıklamıyorsa yan domainler: BOS aşağı, hacim, FVG, order block.
6. **Artık hücresi** — hiçbir katmana girmeyen kalan. **Zorunlu**: "geri kalan ne yapmış" sorusu
   cevaplanmadan ana soru kapanmaz. Genelde en bilgilendirici hücre budur.
7. **Kontrol** — aynı hücre, karşı örnekle (rastgele bar / destek yok) karşılaştırılır. Fark yoksa
   bulgu "bilgi taşımıyor" diye kapatılır.

Bir katman anlamlı çıktığında **sonraki ana soruya geçilir**; aynı katmanı zorlamak veri madenciliğidir.

---

## 2. Ölçüm sözleşmesi (ölçümden önce sabit — değişmez)

**Fiyat ve birim**
- Seviye: native günlük destek projeksiyonunun o 4s bar kapanışındaki değeri (`support_level`).
  Direnç için aynası (`resistance_level`); V2 ilk turda **yalnız destek** tarafında koşar.
- Tüm mesafeler **ATR1d** = giriş barında dondurulmuş günlük ATR14. Geriye dönük ATR kullanılmaz.
- `d = (kapanış − seviye) / ATR1d` (işaretli).

**Mesafe bantları (geometrik eksen)**
| Bant | Tanım |
|---|---|
| Temas | `|low − seviye| ≤ 0.35 ATR1d` veya bar seviyeyi kesiyor (`low ≤ seviye ≤ high`) |
| Yakın | `0.35 < |d| ≤ 1.00` |
| Uzak | `1.00 < |d| ≤ 2.00` |
| Çok uzak | `|d| > 2.00` |

**Temas epizodu (türetilmiş sayaç, native `touch_count` kullanılmaz)**
Ardışık temas barları **tek** temastır. Yeni temas için aradaki en az **2 bar** temas bandının dışında
kalmalıdır. Temaş sayısı 1 / 2 / 3 / 4+ olarak raporlanır.

**Mum anatomisi (günlük ATR)**
| Alan | Bantlar |
|---|---|
| Gövde `|C−O|/ATR1d` | yönsüz `<0.20` · orta `0.20–0.50` · büyük `≥0.50` |
| Kapanış pozisyonu `(C−L)/(H−L)` | alt `<0.35` · orta `0.35–0.65` · üst `>0.65` |
| Aralık `(H−L)/ATR1d` | dar `<0.35` · normal `0.35–1.00` · geniş `>1.00` |
| Üst/alt fitil payı | fitil `>0.5 × aralık` ise "fitilli" |

**Sonuç metrikleri (ikisi birden)**
- (a) `first_1atr_h`: `UP_FIRST` / `DOWN_FIRST` / `AMBIGUOUS_SAME_BAR` / `NEITHER` / `CENSORED` / `NO_ATR`
- (b) `ret_atr_h` (kapanış getirisi) + `mfe_atr_h` / `mae_atr_h`
- Ufuklar: 4s bar cinsinden **1, 4, 8, 10, 12, 16** (mevcut sözleşme). **Ana ufuk = 16 bar**; kısa
  ufuklar yalnız ek sütun, ana hüküm 16 bardan verilir.
- Aynı barda iki eşik → `AMBIGUOUS` **ayrı hücre**, yukarı/aşağı sayılmaz.
- Sağ-sansürlü olaylar tabanda; tüm yüzdeler **geçerli n** üzerinden.

**Örneklem bölmesi**
- Evren: arşivdeki 177 sembolden `sembol_turu == "hisse"` ve havuz dışı olmayanlar.
- Keşif: `sha256(sembol) % 10 < 6` (≈106 sembol). Doğrulama: kalan (≈71 sembol).
- Her tabloda **iki sütun**: keşif ve doğrulama. Doğrulamada işaret değişen bulgu "kararsız" sayılır.
- Sembol yoğunlaşması raporlanır (tek sembol bir hücrenin %20'sinden fazlasını taşıyamaz; taşırsa not düşülür).

---

## 3. ANA SORULAR (onay istenen set)

### K1 — Destek üstüne çıkış ne kadar tutuyor? (çekirdek soru)

**V2-01**
- **Soru:** Fiyat desteğin üstüne kapandığında sonuç dağılımı nedir ve azınlık neyle ayrışıyor?
- **Kütle:** `d_prev < 0` **ve** `d_now ≥ +0.05` (kapanışla üstüne çıkış). Aynı epizotta tek olay.
- **Bölünme:** (a) 16 barda ±1 ATR ilk dokunma; (b) 16 bar kapanış işareti.
- **Alt hücreler:** çıkış öncesi sarkma derinliği · temas sayısı · native durum (ACTIVE/REBASED) ·
  çıkış barının gövde bandı · hacim bandı · BOS aşağı var/yok · artık.
- **Domain sütunları:** BOS yönü (son 3 bar), rvol bandı, ayı FVG mesafesi, ayı OB mesafesi.
- **Miras:** A01/A03/C01 ile aynı aileyi ölçer, ama ayrıştırmayı mum+domain katmanıyla yapar.
- **Cevaplanırsa:** "destek üstüne çıkış" sinyalinin güvenilirliği ilk kez katmanlı olarak bilinir;
  ok eşiklerinin kalibrasyonu (§8.5) bu tablodan beslenir.

**V2-02**
- **Soru:** Üstüne çıktıktan sonra fiyat kaç bar üstünde kalıyor ve kalamama sonucu değiştiriyor mu?
- **Kütle:** V2-01 olayları.
- **Bölünme:** `kalma` = çıkıştan sonraki 3 barda kapanış `≥ seviye − 0.05`; `kalamadı` = aynı pencerede
  kapanış yeniden `seviye − 0.05` altına indi. Sonra 16 bar sonucu.
- **Alt hücreler:** kalma/kalamama × mum anatomisi (günlük ATR) × hacim × temas sayısı.
- **Not:** Kullanıcının "küçük ve yönsüz mumlar yüzünden desteğin üstünde kalamamış" gözleminin
  birinci elden testi budur. İkinci gözlem ("kalamayanların %90'ı küçük mum") bu tabloda yüzdeye döner.
- **Cevaplanırsa:** "kalamama" ayrı bir sinyal sınıfı olarak (uyarı/ok bastırma) değerlendirilebilir.

**V2-03**
- **Soru:** Küçük/yönsüz mum **neden** mi, sadece eşlikçi mi?
- **Kütle:** V2-02'nin `kalamadı` hücresi ile mesafe bandı ve rejim eşleştirilmiş kontrol hücresi.
- **Bölünme:** aynı mesafe bandı + aynı rejimde, büyük gövdeli ve yönsüz mumların 16 bar sonucu.
- **Yanılgı kontrolü:** mum boyu ile sarkma derinliği/volatilite iç içe; ayrıştırmak için **ATR1d sabit**
  tutulur ve hücreler `ATR1d` dilimlerine bölünür.
- **Cevaplanırsa:** ok eşiklerinde "gövde" filtresinin gerçekten nedensel olup olmadığı anlaşılır.

### K2 — Hareketsizlik ve hareketlenme

**V2-04**
- **Soru:** Fiyat destekten uzakta hareketsizken ne olur; destek ne zaman "hareketlenir" ve sonrası nasıl gider?
- **Kütle:** `|d| > 1.00` üst üste ≥6 bar (hareketsiz) → ilk hareketlenme barı (seviye güncellenmesi veya
  `|d|` 1 ATR'den fazla değişim).
- **Bölünme:** hareketlenme yönü (destek fiyatı mı yakaladı, fiyat mı desteğe döndü) × 16 bar sonucu.
- **Alt hücreler:** bekleme süresi (6–9 / 10–19 / 20+ bar) · rejim (NEWLY_FLATTENED / LONG_HORIZONTAL) ·
  hacim bandı · artık.
- **Miras:** A01/A04/A05.
- **Cevaplanırsa:** "destek takip etmiyorsa risk artıyor" hipotezi sayıya döner.

### K3 — Sabit desteğin altına iniş ("temizlik oranı")

**V2-05**
- **Soru:** Destek altına inildiğinde ne kadarı geri dönüyor; sarkma derinliği ve süresi kararı değiştiriyor mu?
- **Kütle:** kapanış `d < 0` (kırılma olayı), ilk kırılma barı.
- **Bölünme:** **temizlik oranı** = 8 bar içinde kapanışla seviye üstüne dönenler / tüm kırılmalar.
- **Alt hücreler:** sarkma derinliği `(seviye − min(low, 8 bar))/ATR1d` bantları: `≤0.35` (fitil) ·
  `0.35–1.0` · `1.0–2.0` · `>2.0`; sarkma süresi (bar sayısı: 1 / 2–3 / 4–8); kırılma barının gövdesi;
  hacim; BOS aşağı; artık.
- **Cevaplanırsa:** "ne kadar sarkarsa döner" eşiği (fitil mi kırılma mı) sayısallaşır; `▲` reclaim
  eşiklerinin (ihlal ≤1.5 ATR) dayanağı test edilir.

**V2-06**
- **Soru:** Temas sayısı kırılma riskini gerçekten artırıyor mu? ("3. temas = düşüş" şartı)
- **Kütle:** her temas epizodu (tanım §2) ve onu izleyen 16 bar.
- **Bölünme:** temas sayısı 1 / 2 / 3 / 4+ → kırılma oranı ve derinliği.
- **Alt hücreler:** tepki boyu (her temas sonrası MFE) · temas aralığı (bar) · rejim · hacim · artık.
- **Yanılgı kontrolü:** temas sayısı yaşla iç içe; aynı yaş ve aynı mesafe bandında karşılaştırma zorunlu.
- **Cevaplanırsa:** kullanıcının "%20'si 2 temasta, %7'si 1 temasta, %13'ü 4 temasta kırılmış" tablosu
  doğrulanır veya çürütülür; ok tarafında `touch_count < 3` filtresinin dayanağı netleşir.

### K4 — Açıklayıcı katmanlar ve kontrol

**V2-07**
- **Soru:** Azınlık hücrelerini hangi yan domain açıklıyor, hangisi açıklamıyor?
- **Kütle:** V2-01/02/05/06'nın azınlık hücreleri (her biri ayrı satır).
- **Bölünme:** her domain için "var / yok / bilinmiyor" üçlüsü; yüzde yalnız "bilinen" üzerinden,
  "bilinmiyor" ayrı sütun (asla 0 sayılmaz).
- **Domain sütunları:** BOS aşağı (yön −1, son 3 bar) · rvol bandı · ayı FVG mesafesi · ayı OB mesafesi ·
  weekly bağlam (varsa).
- **Artık:** dört domainin hiçbiri yok/etkisiz → ayrı ve **zorunlu** hücre.
- **Cevaplanırsa:** "kalan %40 ne yapmış" sorusu cevaplanır; hangi domainin araştırmaya değer olduğu belli olur.

**V2-08**
- **Soru:** Bu ayrışmalar destek bilgisinden mi geliyor, yoksa piyasanın genel eğiliminden mi?
- **Kütle:** V2-01 ve V2-05 hücrelerinin **eşleştirilmiş karşı örneği**: aynı sembol, aynı ATR dilimi,
  seviyeden bağımsız rastgele barlar (tohum sabit) ve `d` bandı aynı tutulmuş "seviye yok" kontrolü.
- **Bölünme:** aynı sonuç metrikleri.
- **Cevaplanırsa:** %70/%30'un ne kadarının desteğe ait olduğu ayrılır. Bu soru **atlanamaz**;
  atlanırsa diğer yedi sorunun sonucu yorumlanamaz.

---

## 4. Öncelik (ilk turda koşulacak üç soru)

| Sıra | Soru | Neden ilk |
|---|---|---|
| 1 | **V2-01** | Kullanıcının çekirdek sorusu; diğer soruların kütlesini üretir. |
| 2 | **V2-05** | "Temizlik oranı" bugün hiç ölçülmedi ve ok eşiklerinin dayanağı. |
| 3 | **V2-08** | Kontrol olmadan ilk ikisinin yüzdesi yorumlanamaz. |

İkinci tur: V2-02 → V2-03 → V2-06. Üçüncü tur: V2-04 → V2-07 (domain katmanı, önceki hücrelere bağlı).

---

## 5. Bu turda yapılmayacaklar (kapsam sınırı)

- **Ok kuralları değişmez.** V2 yalnız ölçer; `▲`/`▼` eşiklerine dokunulmaz (kullanıcı kararı).
- **Direnç tarafı ilk turda koşmaz.** Aynasal direnç ayrı tur; aynı sorular orada tekrarlanır.
- **Yeni domain yazılmaz.** Yalnız mevcut 4 domain (`market_structure`, `fvg`, `order_block`,
  `volume_participation`) kullanılır.
- **Checkpoint paketi depoya eklenmez** (≈80 MB); yalnız özet tablolar ve manifest.

## 6. Koşu için eksik parçalar (kod işi)

| # | İş | Neden gerekli | Boyut |
|---|---|---|---|
| G1 | Replay checkpoint tablosuna "son 3 barda BOS aşağı/yukarı" bayrağı | Bugün yalnız `ms_external_state` var, olay bayrağı yok; V2-07 için şart | küçük |
| G2 | Mum anatomisi sütunları (gövde, kp, aralık, fitil — **günlük ATR**) | `stabil_replay` checkpoint'inde yok; ok replay'inde var | küçük |
| G3 | "Kalma" (3 bar) ve temas epizodu sayaçları | V2-02/V2-06 kütlesi | orta |
| G4 | Sembol hash bölmesi + keşif/doğrulama sütunları | V2 sözleşmesi | küçük |
| G5 | Sonuç tablosu üreticisi (manifest'e göre JSON/CSV) | Tekrarlanabilirlik (§8.8) | orta |

---

## 7. Onay istenen noktalar

1. **8 ana soru doğru set mi?** Çıkarılacak/eklenecek var mı? (Bence çekirdek: V2-01, V2-05, V2-08.)
2. **Eşikler makul mü?** Özellikle: üstüne çıkış toleransı `+0.05 ATR1d`, temas bandı `0.35 ATR1d`,
   kalma penceresi `3 bar`, ana ufuk `16 × 4s bar`, temizlik penceresi `8 bar`.
3. **Mum bantları** (yönsüz <0.20 / büyük ≥0.50 ATR1d) senin gözle gördüğünle uyuşuyor mu?
4. **Sembol bölmesi** hash ile mi olsun, yoksa likidite/hacim sıralamasıyla mı (hash seçildi: seçim
   yanlılığı yok).
