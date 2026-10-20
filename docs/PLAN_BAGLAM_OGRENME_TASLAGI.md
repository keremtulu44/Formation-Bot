# Bağlam Öğrenme Sistemi — Plan Taslağı (v0.1, tartışma aşaması)

> Durum: **Taslak. Kod yazılmadı, dosya değiştirilmedi.** Bu belge kararları ve açık soruları
> kaydetmek için. Onaylanmayan maddeler uygulanmaz.
> Tarih: 2026-10-20 · Dal: `arena/d13dc3c7-formation-bot`

---

## 1. Amaç

Sistem bir grafiğe baktığında, kendi bilgi tabanında karşılığı olmayan bağlamları (zone, seviye,
yapı, formasyon konumu) **tespit edip kaydetmeli**. Kayıtlar daha sonra sayısal olarak ölçülür ve
"bu bağlamda ne oldu" sorusu istatistiksel olarak yanıtlanır. Anlatım (metinsel yol analizi) yalnızca
ölçülüp doğrulanmış sonuçları aktarır.

Amaç ilk aşamada **yorum yapmak değil, neyi bilmediğini bilmektir.**

---

## 2. Temel ilkeler

| # | İlke | Gerekçe |
|---|---|---|
| P1 | **Domainler ayrı öğrenilir.** Her domain (OB, FVG, MS, formasyon, hacim) kendi durum uzayını ve kendi istatistiklerini tutar. | Birleşik senaryolar önceden ayarlanmış reçete üretir; domain bazlı öğrenme bunu engeller. |
| P2 | **Zaman dilimleri ayrı tutulur** (1h, 2h, 4h, 1d). | Her TF'in davranışı farklı; araştırma raporu da 4 TF × 176 sembol olarak ölçüldü. |
| P3 | **Alarm kapsamı = birincil TF.** Alarmda 4 kare gider; uzman yalnızca formasyonun oluştuğu (birincil) TF'nin durumunu girdi alır. Diğer kareler bağlam olarak kalır, uzmanın girdisine karışmaz. | Domain ayrımını korur. *(Birincil TF'nin kodda nasıl seçildiği henüz doğrulanmadı — bkz. Açık Soru A1.)* |
| P4 | **Kayıtlar değişmez ve bar bar üretilir.** Final snapshot'tan öğrenilmez. | Araştırmada OB'nin dolan zone'ları silmesi (138'e karşı 18) ve `structural_role` mutasyonu bulundu. |
| P5 | **Üç durum ayrı etiketlenir:** `BILINEN` / `BILINMEYEN` (veri var, tanıdık değil) / `OLCULEMEDI` (motor veya veri hatası). | Canlı botta 35 MS serisi sessizce boş kaldı; bu "bilmiyorum" değil "ölçemedim". Karışırsa sahte bilinmeyen üretilir. |
| P6 | **Kabul kriterleri veriye bakılmadan önce yazılır.** Minimum n, minimum fark (lift), dönemler arası tutarlılık, çoklu test düzeltmesi. | Çok sayıda hücre test edilirse bazıları şans eseri anlamlı görünür. |
| P7 | **Ölçüt olarak olasılık tek başına kullanılmaz.** Taban oranına göre fark (lift), güven aralığı ve beklenen değer (olasılık × hareket büyüklüğü) birlikte raporlanır. | "%2 ama milyonda biri" gibi durumlarda nadirlik tek başına karar vermez. |
| P8 | **n < 30 hücreler "YETERSİZ"** olarak işaretlenir; tahmin yapılmaz. | Üçüncü ve sonraki temaslar çok küçük örneklem. |
| P9 | **Sansür.** Sonucu henüz oluşmamış kayıtlar "başarısız" sayılmaz; ayrı bir sansür bayrağı taşır. | Son günlerde açılan kayıtların sonucu henüz bilinmez. |
| P10 | **Hacim koşullandırıcıdır, uzman değildir.** | Araştırmada yüksek göreli hacimde tepki zayıfladı; tek başına bir karar kaynağı değil. |
| P11 | **Anlatım katmanı yalnızca doğrulanmış sonuçları anlatır.** Her cümle n, pencere ve taban oranı ile birlikte gelir. Sayı üretmez. | Metin katmanının uydurma riskini kapatır. |
| P12 | **Motorlar değiştirilmez** (ilk aşamada). Ölçüm mevcut çıktılar üzerinden yapılır. | Canlı bot davranışı ayrı bir karardır. |

---

## 3. Mimari aşamalar

| Aşama | İçerik | Çıktı | Durum |
|---|---|---|---|
| **0** | Bağlam kaydı şeması: sembol, TF, bar zamanı, ATR, domain durumları, imza, etiket (BILINEN/BILINMEYEN/OLCULEMEDI), motor sürümü, birincil TF işareti | Şema belgesi | Taslak |
| **1** | Bar bar durum üretimi; imza arşivde yeterince görülmemişse BILINMEYEN kaydı. Append-only, deterministik (aynı veri → aynı kayıt). | Kayıt tablosu | Bekliyor |
| **2** | Her kayıt için ileriye dönük etiket: H bar içinde ATR hareketi, seviye vuruldu mu, BOS/CHOCH oldu mu, kabul oldu mu, sansür bayrağı | Etiketli tablo | Bekliyor |
| **3** | Önceden kayıtlı hipotez testi: keşif dönemi / doğrulama dönemi, taban oranı karşılaştırması, çoklu test düzeltmesi, n ve güven aralığı | Kabul / red raporu | Bekliyor |
| **4** | Domain uzmanlarının bilgi tabanı (kabul edilen istatistikler) | Uzman tabloları | Bekliyor |
| **5** | Birleştirme katmanı (domainler arası). Ayrıca test edilir; önceden tanımlı kural değil. | Birleşik çıktı | En son |
| **6** | Anlatım katmanı (metinsel yol analizi) | Metin | En son |

---

## 4. OB uzmanı — ilk spesifikasyon (pilot)

Pilot olarak OB seçildi (karar bekliyor, bkz. Soru B1). Bu, kullanıcının örneğini (1. temas tepki, 2.
temas tepki, 3. temas bozulma beklentisi, kabul olasılığı, hedef) karşılar.

### 4.1 Tanımlar (önerilen, onaylanacak)

- **Temas (epizot):** Fiyatın zone'a girmesiyle başlayıp zone'dan çıkmasıyla biten ayrı dönem.
  İki temas arasında zone dışında geçen en az X bar (X: Soru B4).
- **Temas sırası k:** Bu zone'daki k. epizot (k = 1, 2, 3, …).
- **Yön:** Zone'un kendi yönü (yön-ancored). Kenar-ancored ölçüm ayrıca tutulur.
- **Tepki:** Temas sonrası H bar içinde, beklenen yönde ≥ 1 ATR hareket — ve bu hareket
  bozulmadan (zone'un karşı kenarı kapanışla geçilmeden) gerçekleşmiş olmalı.
- **Bozulma:** Zone'un karşı kenarının kapanışla geçilmesi.
- **Kabul:** Bozulmanın ardından, zone'un öte tarafında **N ardışık bar kapanışı** (N: Soru B3).
- **Hareket birimi:** ATR; ortalama ve medyan birlikte raporlanır.
- **Sansür:** H bar dolmadan veri biterse sansürlü işaretlenir.

### 4.2 Durum uzayı (uzmanın gördükleri)

| Değişken | Açıklama | Not |
|---|---|---|
| k | Temas sırası | Ana değişken |
| TF | Birincil TF | Ayrı tablolar |
| yükseklik_ATR | Zone yüksekliği / ATR | Araştırmada yüksek zone'lar daha hızlı ve kalıcı tepki verdi |
| önceki_tepki | Önceki temaslarda tepki var mıydı | k ile birlikte |
| son_temas_gecikmesi | Son temastan bu yana bar sayısı | Yaşlanma etkisi |
| rvol_temas | Temas anındaki göreli hacim | Koşullandırıcı (P10) |
| yön | Zone'un yönü | Ayrı tablo |

Değişken sayısı arttıkça n küçülür. İlk sürümde durum uzayı **en fazla 3–4 değişken** ile sınırlı
tutulmalı (Soru B5).

### 4.3 Uzmanın çıktıları (her durum için)

1. P(tepki ≥ 1 ATR, bozulmadan)
2. P(bozulma)
3. P(kabul | bozulma)
4. P(ters yön) — araştırmada ~%11–15
5. Hedef adayları: zone'un karşı tarafındaki en yakın salınım ucu ve/veya bir sonraki yapısal seviye —
   vuruş olasılığı ve ortanca süre (bar) ile
6. Her çıktı için n, güven aralığı ve YETERLI/YETERSİZ etiketi

### 4.4 Bilinen veri ve boşluklar

- Mevcut araştırma raporu (`docs/ARASTIRMA_RAPORU_DUZMETIN.txt`) **bölge düzeyinde** tekrar sayısı verir
  (tek %59–60, iki %19–21, üç+ %11–13) ve **temas düzeyinde** genel tepki oranlarını (≥1 ATR %65–66,5;
  ters %11–15) verir.
- **Temas sırasına göre tepki/bozulma/kabul kırılımı yoktur.** Bu, yeni bir ölçümle üretilecek.
- Hedef adayları ve kabul tanımına göre hesaplanan olasılıklar da yoktur.

---

## 5. Diğer uzmanlar (taslak, sonra detaylandırılacak)

- **FVG:** Araştırmada FVG zone'larının neredeyse tamamı tek temasta çözülüyor veya hiç temas almıyor.
  Sorulacak soru "kaçıncı temas" değil, **"temas alır mı, almaz mı"**. Hedef: temas olasılığı ve sonrası.
- **Market yapısı (MS):** BOS/CHOCH sonrası devam olasılıkları raporda var (4h EXT BOS: %98 uyum,
  %71 çalıştı). Uzmanın sorusu "kırılım ne kadar güvenilir ve nereye kadar devam eder".
  Ayrıca yukarı/aşağı asimetrisi var; tek rejimli 1 yıllık veri bunu kesin kılmaz.
- **Formasyon:** `patterns/` modülü. Kapsamı ve durum tanımı henüz incelenmedi.
- **PH/PL ve WH/WL:** Korunan tepe/dip denemeleri ve süpürülme süreleri raporda var (WH/WL medyan 3 bar).
  Hedef/seviye bilgisi olarak kullanılabilir.
- **Hacim:** Yalnızca koşullandırıcı (P10).

---

## 6. Veri kaynakları

- `backfill_data/` — 365 günlük gerçek arşiv (Mayıs 2025 – Ekim 2026), 176 sembol × 4 TF.
- `docs/ARASTIRMA_BULGULARI.md` — mevcut ölçüm tabloları.
- `docs/arastirma_ms_hatali_seriler.txt` — 35 MS hatalı serinin listesi (OLCULEMEDI olarak işaretlenecek).
- `research/` (`arsiv.py`, `olcum.py`, `kayit.py`, `rapor.py`) — mevcut ölçüm altyapısı. Yeniden
  kullanılabilirliği henüz incelenmedi.
- `domain_engines/` — OB, FVG, MS, hacim motorları. Kayıt üretiminde girdi.
- `state/outcome_link.py`, `state/formation_history.py` — mevcut sonuç bağlama altyapısı. İncelenecek.

---

## 7. Riskler

| Risk | Etki | Önlem |
|---|---|---|
| Domainler arası örtüşme (OB çoğu zaman BOS'tan sonra oluşur) | Bağımsız sanılan kanıtlar aslında aynı bilgi | Birleştirmeden önce örtüşme ölçümü (Aşama 5) |
| Üçüncü+ temas örneklemi küçük | Yanlış kesinlik | n < 30 → YETERSİZ; havuzlama kararı (B2) |
| Tek 1 yıllık rejim | Yön asimetrisi rejim değişiminde tersine dönebilir | Dönemler arası ayrı kontrol; sonuçlar "bu rejimde" diye etiketlenir |
| Motor hataları (35 MS serisi) | Sahte BILINMEYEN kayıtları | P5: OLCULEMEDI ayrı etiket |
| Snapshot mutasyonu | Yanlış durum, yanlış etiket | P4: bar bar üretim |
| Çoklu test | Şans eseri anlamlı hücreler | P6: önceden kayıtlı kriterler, düzeltme |
| Canlı botla karışma | Ölçüm kodu canlı davranışı değiştirebilir | P12: motorlara dokunulmaz; ayrı modül |

---

## 8. Açık sorular (tartışma için)

### A. Kapsam ve birincil TF
- **A1.** Alarmda birincil TF nasıl belirleniyor? (Kodda `birincil` ifadesi yalnızca config yorumunda
  geçiyor; `main.py` ve `telegram_alert_flow.py` içinde açık bir seçim mantığı bulunamadı. Doğrulanmalı.)
- **A2.** Dört TF'nin tümü için ayrı uzman mı, yoksa önce tek TF ile pilot mu? Pilot TF hangisi?

### B. OB uzmanı
- **B1.** OB pilot olarak başlasın mı?
- **B2.** Havuzlama: TF bazında ayrı mı, tüm semboller birlikte mi? Ayrı öğrenme temiz ama üçüncü
  temas örneklemi küçülür. Sembol havuzlaması (sektör/likidite grubu) bir seçenek mi?
- **B3.** "Kabul" tanımı: N kaç bar? (Öneri: 2 ardışık kapanış, zone'un öte tarafında.)
- **B4.** İki temas arasında "zone dışında geçen minimum bar" kaç olsun? Bu, aynı hareketin iki kez
  temas sayılmasını engeller.
- **B5.** Durum uzayında ilk sürümde hangi değişkenler olsun? (Öneri: k, yükseklik_ATR, TF, rvol_temas.)
- **B6.** Hedef tanımı: "zone'un karşı tarafındaki en yakın salınım ucu" mu, yoksa "bir sonraki OB/FVG
  bölgesi" mi? Hangisi daha anlamlı görülüyor?
- **B7.** H (ileriye bakış ufku) kaç bar ve ATR cinsinden kaç olsun? Araştırmada ortalama uzanım h12
  (12 bar) üzerinden ölçüldü.

### C. Kayıt ve sistem
- **C1.** Kayıtlar nerede tutulsun? Yerel dosya (parquet/CSV), Supabase (`supabase_store.py` mevcut),
  yoksa her ikisi?
- **C2.** Kayıt üretimi canlı bota eklenecek mi, yoksa yalnızca arşiv üzerinde replay ile mi? (Öneri:
  ilk aşamada yalnızca replay; canlı entegrasyon en sonda.)
- **C3.** BILINMEYEN tanımı için imza eşiği: bir imza arşivde kaç kez görülmüşse "bilinen" sayılsın?
  (Öneri: n ≥ 30.)

### D. Kabul ve sunum
- **D1.** Kabul kriterleri sayısal olarak ne olsun? (Öneri taslağı: n ≥ 30, lift ≥ 0,5 ATR veya belirlenen
  eşik, güven aralığı taban oranını dışlamalı, iki ayrı dönemde yön tutarlı, en az iki TF'de tekrar.)
- **D2.** Sonuçların sunumu: yalnız tablo mu, yoksa metin özeti de ilk aşamada istenir mi?

---

## 9. Sonraki adımlar (onay sonrası)

1. Açık soruların yanıtlanması (öncelik: A1, A2, B1, B3, B4, B6, D1).
2. Aşama 0 şemasının yazılması ve onaylanması.
3. A1 doğrulaması: birincil TF seçim mantığının kod incelemesi.
4. OB pilotu için ölçüm planının yazılması (temas sırası tablosu, kabul ve hedef tanımları).
5. Pilot ölçümün çalıştırılması ve sonuçların bu belgeye eklenmesi.
