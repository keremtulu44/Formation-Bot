# FAZ9 — Tecrübe Entegrasyonu (uzun görev ön-kayıdı)

**Tarih:** 2026-11-11 · **Durum:** AKTİF · **Kullanıcı görevi:**
*"bunları olabildiğince mantıklı ve anlamlı şekilde ekle, sistemimizin amacını
koruyarak çalış; replay'i çalıştır,50 sembolde sonuçların nasıl etkilediğini,
nerelerin düzeldiğini, nerelerin problem yaşadığını tespit et; amaca uygun
şekilde sistemi düzenle, felsefeye uygun test et."*

**Girdi:** `docs/arastirma/faz9_tecrube/TECRUBE_ENVANTERI.md` (69 genel ders) +
`SENARYO_MOTORU_BRIFING_SOZLESMESI` (felsefe) + `ZARAR_TESHISI` (FAZ8 teşhisi).

## 0. Felsefe kilidi (değişmez — hepsi sözleşme maddesi)

1. Plan ≠ sinyal; çıktı gölge defter + rapor; ana sistem **değişmez**.
2. Katman çıktısı kırpılmaz; **yön girdi değil çıktıdır**.
3. Kapılar az ve sığ; n≥30 (nadir<300); sıfat yok sayı var; uydurma yasağı.
4. Her karar-değişikliği **ölçülür** (FAZ8 protokolü: aynı evren, kapılar K1–K6);
   sonuçlar bozulursa geri alınır/sınırlandırılır.

## 1. Tur A — Bilgi katmanı (KARAR DEĞİŞMEZ, kanıt zorunlu)

| Ek | Ne | Neden felsefeye uygun |
|---|---|---|
| A1 | `PlanKaydi.aktif_bildirimler` — tetik anındaki aktif bildirilerin **tamamı** (kim, iddia, **kosul**, kaynak, kalan geçerlilik, **seviyeler**, görev) JSON olarak plana işlenir | Brifing §3: zenginlik kaybolmasın; şimdiye kadar yalnız `kim:iddia` taşıyorduk |
| A2 | `PlanKaydi.sahneler` — tetik anında **as-of** (≥ bakışı yok) ön-kayıtlı sahne etiketleri: `zemin_onayli · zemin_yakin(≤0,5A) · zemin_kademe_yukari/asagi · formasyon_aktif · formasyon_olgun · ms_destek(lehte5) · zone_genis(≥2A) · zone_dar(<0,5A) · zone_dolu` | Tecrübe Envanteri §H1: sahne-bileşimi ölçümünün tohumu; etiket = kayıt, filtre değil |
| A3 | Replay50 (ana50) yeniden + **değişmezlik kanıtı**:412 plan, plan_id kümesi ve **plan başına sonuç** FAZ8 ile birebir | Kapı bozulmadı kanıtı |
| A4 | İki rapor: **Cümle Sicili** (iddia × sonuç, n≥30) ve **Sahne Ölçümü** (etiket × sonuç, n≥30) | Brifing B4; "nereler düzeltebilir/neler bozar" aday listesi |

## 2. Tur B — İlk karar adayları (A'dan SONRA, ayrı kapı ile)

Sıra (A raporlarının çıktılarıyla kesinleşecek):
1. **Hedef zenginliği:** formasyon üst sınırı hedefe dahil (sözleşme §5'te yazılı,
   kodda eksik — GZ "bilinmeyen" satırı). A/B: FAZ8 (412) vs yeni hedef.
2. **Cümle-sicilinden tek sığ kapı:** örn. stop oranlı bir iddia (envanter C6 usulü).
3. **Karakterli stop** (yatay zemin vs dikey basamak — sözleşme §5) — en son.

## 3. Ölçüm protokolü

- Baseline: **FAZ8** (n412 · PF2,12 · net+175,5A · kâr%55,8 · K2+5,03 ·7/7).
- Her tur: replay50 → olcum → kapi → inceleme → sahne/kova kırılımı raporu
  (*neresi düzeldi / neresi bozuldu*) → geri-al/sınır kararı.
- Rejim/ay filtresi, exit-side, H20, ön-gözlem giriş filtreleri **kapalı kalır**.
- Tecrübe satırları yalnız envanterdaki n+kaynakla yazılır (uydurma yasağı).

## 4. Tur A kayıtları (2026-11-11 tamamlandı)

- **Kod:** `bcf534d` (modeller + plan_karti + golge_zincir; test paketi
  4349passed/6failed — 6 hata **önceden var**, `git stash` ile teyitli,
  stabil_direnç modülüyle ilgili, FAZ9'a bağımsız).
- **Replay A:** `sonuclar/golge_zincir_faz9a/` (998,7 sn, 0 hata).
- **Değişmezlik kanıtı ✓✓:**412/412 plan-id birebir · plan-başı sonuç farkı
  **0** · pnl maks fark **0,000000 ATR** · sonuç137/132/143 = FAZ8.
- **Rapor:** `docs/arastirma/faz9_tecrube/CUMLE_SICILI_SAHNE.md`
  (cümle sicili + koşul öbekleri + sahne ölçümü + çift-kesişimler).
- **İlk adaylar (öLÇÜLDÜ, KARAR YOK):**
  1. `stabil:zemin ACTIVE, dinamik **EXPANDING**` n141 → **+0,560A/işlem**
     vs `**CONTRACTING**` n188 → **+0,330A** (fark +0,23A; büyük-eksik adayı).
  2. `zemin_kademe_asagi` n183 **%60 kârlı** vs `zemin_kademe_yukari` n222
     **%53** (C3 "dikey tırmanışta altı boş" dersi işlem sonuçlarına yansıdı).
  3. Evrensel iddialar (stabil:izle vb.) ayırt etmiyor — A12 dersi tekrar.
- **Sıradaki tur (B)** — kullanıcı seçimi bekliyor: hedef-zenginliği A/B,
  CONTRACTING cümlesinden sığ kapı, veya karakterli stop.

---

## 5. B-1 ÖN-KAYIT — CONTRACTING kapısı (2026-11-11, sonuç okunmadan yazıldı)

**Aday kural (sığ, tek değişken):** Tetik anında stabil zemin dinamiği
`CONTRACTING` olan planlar **açılmaz** (golge defterindeki stabil:izle
cümlesinin koşulundan okunur; n=188, işlem başı +0,330A vs genel +0,426A —
FAZ9-A cümle sicili, rapor §2).

**Kapı (değişmez, plan belgesi §4):** K1–K6 **aynı eşiklerle**, `golge_kapi.py`
ile değerlendirilir. Ek ölçütler (önceden sabit):

| Ölçüt | Eşik | Gerekçe |
|---|---|---|
| Kapı K1–K6 | **GEÇTİ** (7/7) | Ana şart — sistem bütünlüğü |
| Net kârlı oranı | **≥ %58** (baseline %55,8) | Kullanıcının seçtiği metrik |
| Doğrulama beklentisi (K3) | ≥ baseline 0,4073 | Zayıf grubun elenince artmalı |
| Toplam net | Düşüş **raporlanır** (gizlenmez) | CONTRACTING subset'i +62,1A taşıyordu — maliyet görünür olacak |

**Red koşulu:** Kapı geçmezse veya kârlı oran %58'i tutturamazsa → sistem
**değişmez**; sonuç Tecrübe Envanteri §I'ye "B-1 RED" olarak yazılır.
**Geçerse** bile canlıya bağlantı yok (kırmızı çizgi8); yalnız gölge kanıt.

**Yöntem:** FAZ9-A defterinden CONTRACTING planları çıkarılır → alt-defter →
`golge_olcum` → `golge_kapi` (gerçek araç zinciri). Kör baz (kor_baz)
plan-bağımsız olduğundan aynı kalır; beklenen değişiklik yalnız plan tarafı.

---

## 6. B-1 SONUÇ — CONTRACTING kapısı (ölçüm tamam, karar: **RED**)

**Araç zinciri:** alt-defter (188 plan/sonuc çıkarıldı,376 satır) →
`golge_olcum` (plan224 · kör baz1452, **kör 39,80 puan ile FAZ8 ile birebir**)
→ `golge_kapi` → `kapi_karari_faz9b1.json`.

| Ölçüt (§5'te sabit) | Eşik | Sonuç | Durum |
|---|---|---|---|
| **Kapı K1–K6** | 7/7 | **6/7 — K1 = 47 < 50** | ✗ **GEÇMEDİ** |
| K2 (UYGUN−kör) | ≥ +5,0 | **+8,59** (baseline +5,03) | ✓✓ |
| K3 / K6b doğrulama beklentisi | ≥0,4073 | **0,5795** | ✓✓ (+%42) |
| K6a keşif beklentisi | >0 | 0,4866 (0,4311'den) | ✓ |
| K4/K5 | 0/0 | 0/0 | ✓ |
| Net kârlı oranı (kullanıcı metriği) | ≥ %58 | **%58,5** (131/224) | ✓ |
| PF | rapor | 2,12 → **2,46** | ✓ |
| Toplam net | görünür | **+175,5A → +113,4A (−62,1A)** | raporlandı |

**KARAR (önceden yazılmış kırmızı çizgi):** Kapı geçmedi → **sistem DEĞİŞMEDİ.**
Sonuç Envanter §I'ye işlendi.

**Ne öğrendik (dürüst okuma):**
1. Yön doğru: zayıf grubu çıkınca **kalite tüm kapılarda yükseldi** (K2 neredeyse
   ikiye katlandı, kazanç% %58,5'e çıktı, PF2,46).
2. Tek kırmızı **nüfus sorunu**: CONTRACTING doğrulamanın43/90'ını taşıyordu —
   K1 (anti-overfit n≥50) tam da bu yüzden var; eşik değiştirilemez.
3. Maliyet net: elenen grup188 işlemde **+62,1A** kazandırıyordu — filtre toplam
   kârı %35 düşürüyor (kalite artıyor, miktar düşüyor).
4. **B-1b alternatifi (sıradaki aday, ayrı ön-kayıt ister):** CONTRACTING'te
   filtre değil **uyarı/teyit-sıkılaştırma** — n'yi kesmeden kalite aramak
   (B-2 kademe-uyarısı ile aynı mekanizma). Kapı K1 riski olmadan test edilebilir.

---

## 7. FAZ9-C DÜZELTMELİ BAZ + B TURU ÖN-KAYDI (2026-11-11, B varyantları okunmadan yazıldı)

### 7.1 Bağlam: G5 gelecek-sızıntısı (dış denetim bulgusu) ve FAZ9-C baz

Dış danışman oturumu `senaryo/zincir.py` G5 tepki-onay penceresinde gelecek
bar okuması buldu (`temas_bar+1..+3`, `i`'ye kırpılmamış): **276/412 plan
gelecek kapanışlarla tetiklenmişti.** Düzeltme (tek satır, `min(..., i+1)`) +
kalıcı kesme/gelecek testleri `3d4838e` ile commit edildi (testler: gelecek
okuma, temas-barı-bos-pencere, çerçeve-kesme). Dış danışmanın bağımsız koşusuyla
**bizim koşumuz birebir uyuştu** (aşağıdaki tablo = iki bağımsız koşunun teyidi).

**FAZ9-C düzeltilmiş baz (ana50, H=10, aynı protokol):**

| Ölçüt | Eski (sızıntılı) baz | **FAZ9-C düzeltmeli baz** | Danışman koşusu |
|---|---|---|---|
| Plan n | 412 (137/132/143) | **200 (49 hedef/74 stop/77 zaman)** | 200 (49/74/77) ✓ |
| Net / işlem | +175,5A / +0,426 | **+57,9A / +0,290** | +57,9 / +0,290 ✓ |
| Kârlı % / PF | %55,8 / 2,12 | **%47,5 (95/200) / 1,57** | %47,5 / 1,57 ✓ |
| Kör baz beklenti | +0,362 | **+0,130** | +0,130 ✓ |
| Kapı | 7/7 (K2+5,03) | **6/7 GEÇMEDİ (K1=43<50; K2=+18,12)** | 6/7, K1=43, K2=+18,12 ✓ |
| Keşif / doğrulama n | 322/90 | **157/43** | — |
| Hedefe ulaşılan planların girişe göre ort. getirisi | — | **%4,75 (n49)** | — |
| Plan dönemi | — | **2024-12-31 → 2026-10-13 (~22 ay)** | — |

Ana50 sembol listesi `docs/arastirma/sonuclar/golge_zincir/ana50_semboller.txt`
(FAZ9-A defterinden çıkarıldı — tekrarlanabilirlik açığı kapatıldı).

### 7.2 B-turu ölçüm protokolü (ön-kayıt)

**K1 yapısal durumu:** düzeltmeli baz K1=43 <50 → kapı **7/7 yapısal olarak
kapanmıştır** (nüfus kararı ayrı ön-kayıt ister: evren/genişletme kullanıcıyla
ele alınacak — dış danışman3. adım). Bu tur **bağıl protokol** ile ölçülür:

- **Kazanan varyant şartları (hepsi, eşzamanlı):** K1 ≥ **43** (baz korunur) ·
  kârlı% ≥ **%47,5** · net ≥ **+57,9A** · PF ≥ **1,57**.
- Her varyant aynı düzeltmeli bazla **ayrı ayrı** koşulur (üst üste binmez);
  bayraklar opt-in (varsayılan kapalı = baz birebir).
- Sonuç ne olursa olsun sistem ancak **kazanan** varyantta değişir; beraberlik
  veya belirsizlikte RED ve sistem değişmez. Tüm sonuçlar Envanter'e yazılır.

### 7.3 B2 — kademe-yukarı TYR uyarısı (`--b2-uyari`)

**Kural:** tetik anında `g1.ilerleme == REBASED_HIGHER` ise TYR'ye
`ek_celiski=+2` → çelişki tavanı(1) aşılır → **BEKLE** → plan o bar'da
açılmaz. Tetik koşulu (bant+tepki) dayanıklıysa kademe sonunda **gecikmeli**
açılarak n korunur; dayanmıyorsa **kayıp** olur — ikisi de raporlanır
(gecikme/kayıp ayrımı: plan barı kademe-sonrası mı, hiç plan yok mu).
**Bilinen risk (dış danışman):** kademe etiketi geniş (eski bazda222/412),
beklenti farkı zayıf (p≈0,87), bu grup az ama büyük kazanıyor — nüfus K1
tehlikesi. **Ön-kayıt beklentisi:** dürüst test; kazanma olasılığı düşük,
sonuç ne olursa olsus kaydedilir.

### 7.4 B3 — formasyon üst sınırı hedef adayı (`--b3-hedef`)

**Kural:** `g2.aktif && mesafe_ust_atr` varsa üst-sınır adayı hedef yarışına
girer (en yakın aday seçilir, R≥1,2 süzgeci aynen). Bilinmeyenler satırında
**statik G2 mesafesi** uyarısı taşır (tazelik sınırlı — dış danışman uyarısı:
G2 satırları tam-seriyle hesaplanır). **Bilinen risk:** en yakın aday
yakınlaşınca R<1,2'e takılan planlar düşer (dış danışman tahmini düzeltilmiş
bazda ~32 plan, K1 43→~36) + kör baz da kayabilir (tetik geometrisi değişmez;
plan geometrisi değişir → kör baz plan-bağımsız, **sabit kalır** — düzeltme:
kör baz yalnız tetikte oluşur, tetik değişmez → sabit). **Hüküm:** gizli-filtre
etkisi + K1 kaybı görülürse RED.

### 7.5 B4 — karakterli stop (`--b4-karakterli`)

**Kural (sözleşme §5):** stop = tez ölümü, sabit ATR değil. Mevcut tampon
0,10 ATR; **dikey-yükselen karakterde (`REBASED_HIGHER`) tampon 0,30 ATR**
(dikey basamak gürültüsü/genişlik), diğer karakterlerde 0,10 aynı. **Bilinen
etki:** stop mesafesi büyür → [0,5;2,5]A süzgeci bazı planları düşürebilir
(n/K1 riski), R düşer (hedef aynı) → hedef-sonucu oranı artabilir. **Hüküm:**
K1/kârlı%/net/PF dörtlüsünden herhangi biri baz altına düşerse RED.

### 7.6 Kayıt sırası

Her varyant: bayraklı replay → `golge_olcum` → `golge_kapi` → bu belgeye sonuç
tablosu → kazanan varsa Envanter + sistem değişikliği; yoksa sistem değişmez.
**Kırmızı çizgi8:** hepsi gölge kanıt; canlıya bağlantı yok.

---

## 9. B-5 ÖN-KAYIT — TYR olgunluk-zenginliği (`--b5-olgunluk`) (2026-11-11, sonuç okunmadan yazıldı)

**Kaynak (uydurma değil):** Envanter §H7 "TYR'ye zenginlik girişi — akmıyor →
lehte sayacı" boşluğu + TYR'nin kendi lehte mimarisi (`onaylı +1` ve
`taze_destekleyen +1` ayrı ayrı sayılıyor ama ikisi birlikte UYGUN'un
olgunluk kapısını açmıyor) + B1/B2/B3 üçünün de K1'i kıstığı (nüfus büyüten
kol son6 adayın tek yönü).

**Kural (tek değişken):** `olgunluk = (mesafe ≤ 1 ATR) VEYA (G2 olgun) VEYA
(--b5-olgunluk açıkken: g1.onaylı AND taze_destekleyen MS desteği)`. Yalnızca
UYGUN hücresine dokunur; RET, çelişki-bekle, tetik, geometri, teyit DEĞİŞMEZ.
Yani: destek onayı + taze MS desteği birlikte varsa, mesafe >1 ATR olsa bile
olgunluk tamamlanmış sayılır.

**Kapı (aynı dörtlü, §7.2):** K1 ≥ 43 · kârlı% ≥ 47,5 · net ≥ +57,9A ·
PF ≥ 1,57. **Dürüst beklenti:** n yönü ↑ olası (genişleme); kalite belirsiz
(desteğe uzak giriş riski — doz-yanıt D5 tersi işlem görebilir). Kazanan
dörtlü tutmazsa RED.

---

## 11. KÖK PLAN ÖN-KAYDI — audit + evren genişletme + yeniden koşu (2026-11-11, sonuçlar okunmadan yazıldı)

**Bağlam:** G5 sızıntısı + dış denetimin açık maddeleri (G2/G4 kesim
tutarsızlığı, zone_dolu etiketi) **kökten kapatıldı** (`2f956ba`): violation
penceresi çerçeve sonu yerine tarama bitişine çakıldı (kök neden — canlıda
tesadüfen aynı, uzun replay'de erken barlar yanlıştı), G2 as-of dizileri,
zone_dolu terminal kaldırıldı; **kalıcı boru-hattı kesme testi GEÇTİ**
(`test_golge_kesme.py`). Önceki tüm koşular (FAZ9-C baz, B1–B5) **audit-öncesi
döneme** aittir: göreli yön bilgisi olarak okunur, kapı iddiası yeniden
kurulmaz.

### 11.1 Evren kararı (kilit)

- **Evren = tüm arşiv** (`arsiv_sembolleri` − `HAVUZ_DISI` = **176 sembol**).
  Gerekçe: (a) ana50'de K1=43 yapısal yetmezlik; (b) ciro-sıralaması
  belirsizliği (dış denetim:48/50 vs37/50 örtüşme) tamamen ortadan kalkar;
  (c) likidite kalitesini kapı K1/kârlı% zaten ölçer.
- Protokol AYNEN: H=10, TF=1h/2h/4h/1d, %70/%30 keşif/doğrulama, K1–K6
  **eşikleri değişmez** (K1≥50 dahil — anti-overfit kalkanı sökülmez).
- Beklenti (yön): plan n ≈700 → doğrulama ≈150–190 → kapı anlamlı çalışır.

### 11.2 Koşu sırası ve adaylar

1. **Büyük-evre baz** (bayrak yok, audit-öncesi kod değil — yeni kod).
2. **B4** (karakterli stop — audit-öncesi en yakın aday: kârlı% eşit, K2↑).
3. **B5** (olgunluk-zenginliği — tek n-büyüten kol).
- B1/B2/B3 **tekrarlanmaz**: üçü de kesme-tuzağında RED (mekanizma sınıfı
  kapandı).

### 11.3 Kazanma şartı (her varyant için, eşzamanlı)

**K1 ≥ 50** (mutlak kapı) · kârlı% ≥ büyük-evre baz · net ≥ baz · PF ≥ baz.
Beraberlik/belirsizlik → RED, sistem değişmez. Tüm sonuçlar bu belgeye + Envanter'e yazılır.

---

## 8. AUDIT-ÖNCESİ DÖNEM SONUÇ TABLOSU (2026-11-11 — §11 uyarınca kapı iddiası değil, yön bilgisi)

> **Uyarı:** Bu tablo G5 sızıntısı kapatıldıktan ama G2/violation/zone_dolu
> audit'i (`2f956ba`) ÖNCESİ koşulmuştur. Dış denetim kurallarıyla (§7.2 dörtlü)
> değerlendirilmiş, hepsi RED'tir; mekanizma yönleri korunur, kapı iddiası
> büyük-evre bazda yeniden kurulur (§11).

| Koşu | n | K1 | K2 | Kârlı% | PF | Net | Dörtlü karar |
|---|---|---|---|---|---|---|---|
| FAZ9-C baz (50 sembol) |200 |43 ✗ |+18,12 |%47,5 |1,57 |+57,9A | referans |
| **B2** kademe-uyarısı |97 |23 ✗ |+24,12 |**%52,6** |1,65 |+30,2A | **RED** (K1+net) |
| **B3** formasyon-üstü hedef |152 |33 ✗ |+15,96 |%42,1 |1,20 |+16,4A | **RED** (4/4 kötü) |
| **B4** karakterli stop |179 |39 ✗ |**+22,15** |%47,5 |1,54 |+51,6A | **RED** (K1,PF,net) |
| **B5** olgunluk-zenginliği |207 |44 ✗ |+16,43 |%46,9 |1,57 |**+60,7A** | **RED** (kârlı% −0,6pp) |

**Dönem ortak:** 2024-12-31 → 2026-10-13 (651 gün), ana50, H=10.

**Kârlı-işlem raporu (kullanıcı sorusu — bu dönem, ana50):**

| | Baz | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|
| Karlı işlem / toplam |95/200 |51/97 |64/152 |85/179 |96/207 |
| Kârlı % |%47,5 |%52,6 |%42,1 |%47,5 |%46,9 |
| Hedefe ulaşanların ort. getirisi |%4,75 |%4,17 |%4,11 |%4,88 |— |
| Net |+57,9A |+30,2A |+16,4A |+51,6A |+60,7A |

**Çıkarılan dersler (audit-öncesi döneme ait, mekanizma sınıfı):**
1. **B2/B1 sınıfı (kesme/uyarı):** kalite artıyor, nüfus ve net kırılıyor →
   bu sınıf kapandı (B1, B2).
2. **B3 sınıfı (hedefe aday ekleme):** en yakın-aday R süzgeci gizli filtre
   oluyor, hedef sayısı bile düşüyor → sınıf RED.
3. **B4 (karakterli stop):** mekanizma çalıştı (stop74→62, K2+22,15, kârlı%
   eşit) ama dörtlü tutmadı → büyük-evrede tekrar (§11).
4. **B5 (olgunluk-zenginliği):** tek n-büyüten kol (207, K1 44, net en yüksek)
   ve kârlı% eşiğine0,6 puan kaldı → büyük-evrede tekrar (§11).

---

## 10. DOMAIN ANALİZİ — eski domain replay'lerinden eklenebilir sistemler (2026-11-11)

**Kaynak:** Envanter §A–H (domain hatları: OB–FVG, MARKET STRUCTURE, STABIL,
FORMASYON, hacim, veri-tuzakları) + dış denetim notları. Kural: her aday
**as-of kanıt tazelemesi** (audit dersi: A–D bölümleri sızıntılı hatlardan
geldi, denetlenmedi) + ön-kayıt + kapı ister.

| # | Aday sistem | Kaynak ders | Durum | Sıradaki adım |
|---|---|---|---|---|
| 1 | **Olgunluk-zenginliği** (yapı-koşullu UYGUN genişlemesi) | H7 + TYR lehte mimarisi | **Test edildi (B5, audit-öncesi: en yakın RED)** | §11 büyük-evre tekrarı |
| 2 | **Formasyon üst sınırı → hedef** | H5 + sözleşme §5 gerilimi | **Test edildi (B3: RED — sınıf kapandı)** | Kapatıldı |
| 3 | **Karakterli stop** (dikey basamakta geniş tampon) | H6 + sözleşme §5 + FRM-39 | **Test edildi (B4: RED, en yakın2)** | §11 büyük-evre tekrarı |
| 4 | **Kademe/CONTRACTING uyarı-sınıfı** | B-1 dersi + I1 | **Test edildi (B1, B2: RED — kesme tuzağı)** | Kapatıldı (uyarı≠kesme doğrulandı ama TYR bekleme de kesiyor) |
| 5 | **Sahne-bileşimi** (çok-etiketli sahne × sonuç) | H1 + Tur A sahne etiketleri | Açık | Az sayıda ön-kayıtlı sahne, tek tek ölç (n≥30) |
| 6 | **Doğrulanmış domain iddialarını TYR'ye akıtmak** (OK R3-B %63,5; KIRILIM ilk-barda %76,3; TAHMIN MS-dış-BOS +9,5) | §C/§A dersleri | Açık (H7 v2) | Önce as-of tazeleme (A–D denetimi) → sonra B5-v2 gibi tek değişken |
| 7 | **Hacim izin katmanı (VP)** | H4 + F1 (hacim %100 dolu ama kirli) | Açık | Önce hacim audit'i; izin katmanı sonra |
| 8 | **Rejim/genişlik** (evren-genişlik; ay-filtresi kapandı) | H8 | Açık | Ayrı faz — kombinasyon-kaos riski nedeniyle tek başına |
| 9 | **Cümle sicili bildiri-başına** (H2) + diyalog döngüsü (H3) | Sözleşme §4/§3 | Altyapı | Tur A verisi hazır; rapor katmanı en sonda |

**Dış denetimle gelen ek uyarılar (ekleme öncesi):** `zone_dolu` (audit'de
kapatıldı —407/412 sabit etiket), K2'nin tek-işleme bağlılığı (std hata7,4
puan — bu nüfusta K2 ayırt edemiyor), "erken giriş" teşhisi hâlâ baskın
(giriş zamanlaması = ana kâr kaynağı; hedef/stop kolları ikincil).

---

## 12. §11 EVREN PROGRAMI SONUÇLARI + KÖK HÜKÜM (2026-11-12)

### 12.1 Büyük-evre koşuları (audit'li kod, H=10, tüm arşiv — ön-kayıt `389d259`)

| Koşu | N | plan | K1 | K2 | K3 | K4/K5/K6 | Kapı | Net | Kârlı% |
|---|---|---|---|---|---|---|---|---|---|
| **FAZ9-D baz176** |176 |633 |**141 ✓** |**2,88 ✗** |**−0,120 ✗** | ✓✓✗ | **4/7 GEÇMEDİ** | +81,7A | %44,2 |
| **FAZ9-D B4-176** |176 |554 |131 ✓ |3,32 ✗ |−0,107 ✗ | ✓✓✗ | **4/7 GEÇMEDİ** | +79,9A | %44,8 |
| B5-176 | — | — | — | — | — | — | **koşulmadı** (baz176 RED → §11.3 program durdu) | — | — |

- **Doğrulama:** baz176 = n141 ama **−16,9A, kârlı%36,9** — kenar yok.
- Keşif tarafı pozitif (+98,6A) — **tüm kayıp doğrulamada**.

### 12.2 Evren-kırılımı (baz176 alt kümeleri, koşusuz teşhis)

| Alt küme | plan n | doğrulama n | doğrulama net | K2 (plan−kör) |
|---|---|---|---|---|
| ana50 (orijinal) |200 |43 | **+19,1A** | **+18,12 ✓** |
| ciro-top100 (benim sıralamam) |318 |80 | −0,5A | ~+3 ✗ |
| ciro-300M tabanı (N75) |230 |57 | +7,8A | **−1,07 ✗** |
| ana50 ∪ likidite-top50 (N70) |223 |53 | +13,7A | **−0,89 ✗** |
| tüm176 |633 |141 | −16,9A | **2,88 ✗** |

### 12.3 Kök hüküm (sayılar)

1. **Nüfus sorunu çözüldü:** K1 her geniş evrede131–141 (≥50 ✓).
2. **Kapılar zıt çekiyor:** K1 (n≥50) yalnız geniş evrede; **K2≥5 yalnız
   orijinal ana50'de**. Genişletmenin her yolu K2'yi −1…+3 aralığına düşürüyor.
3. **Kenar likidite-çekirdeğinde yaşıyor ama orada n kıt:** ana50 doğrulama
   +19,1A (n43) — ekleme gelen her grup doğrulamada ~0/negatif katkı veriyor.
4. **Ölçüm sağlıklı artık:** kesme testi kalıcı; tüm sayılar as-of boru
   hattından; dış danışmanla çapraz teyit (G5 düzeltmesi) var.
5. **Seçim-sızıntısı notu:** FAZ8 evreni tam-arşiv cirosuyla seçilmiş
   (üretim kuralı "ilk30 gün" ile48/50 uyuşmuyor — dış denetim bulgusu);
   tam-arşiv ciro = sonuç dönemini içeren seçim (hafif selection-leak riski).

### 12.4 Kapı-protokolü kararı — SADECE KULLANICININ (bu noktadan sonra koşu yok)

Mevcut veri/evrenlerle **7/7 geçilemez**; seçenekler (önce-ölç-sonra-karar):

| Seçenek | Anlamı | Risk |
|---|---|---|
| **A) K1 tazelemesi** (≥50 → ≥40 gibi, gerekçeli) | ana50'de43 ≥ yeni eşik → kapı anlamlı ölçülebilir | Eşik revizyonu = kalkan değişikliği; açık beyan + danışman denetimi ister |
| **B) Taze veriyi bekle** | Aylık yeni plan ~doğrulama50'yi birkaç ayda aşar | Zaman; sistem gölgede kalır |
| **C) Hold-out taze26 ile doğrula** |24 hisse K1'i tek başına açmaz; ana50+taze birleşimi K2 riski | Örnek yetersiz |
| **D) Sistemi olduğu gibi bırak** | Gölge devam, canlıya bağlantı yok (kırmızı çizgi8), B4/B5 adayları kayıtlı | İlerleme durmaz, kanıt birikir |

**Öneri (ajan):** D + B birlikte — sistem gölgede kalmaya devam eder, veri
akar, K1 doğal yoldan açılır; A yalnız danışman/insan onayıyla ve beyanlı.

**Kilit cümleleri (2026-11-12 dış denetçi onayıyla, bağlayıcı):**

1. **"Taze doğrulama bitmeden HİÇBİR eşik revizyonu koşulmaz/koşılmaz."**
   (D oturumu nazikçe A'ya kaymasın diye bu madde plan belgesine işlenmiştir.)
2. **K1 yalnız şu zincirle değişebilir:** (i) gerekçe "43 vs50 fark etmez"
   değil, **ölçüm cihazının değişmesidir** (sızıntı audit'i = cihaz temelden
   değişti → kapı re-basing'i meşrudur); (ii) yeni eşik **taze/okunmamış**
   veride, sonuç OKUNMADAN ön-kayıtla yazılır; (iii) eski eşik (K1=50,
   FAZ9-A 6/7 kaydı) tarihsel olarak korunur, yenisi yalnız ileriye uygulanır;
   (iv) **güç analiziyle** motive edilir (ör. K2≥5'i %80 güçle ayırt eden n
   kaçtır). **Mevcut veri üzerinde "K1:50→40" savunulamaz.**
3. **Evren süzgeci (ön-kayıt):** yeni evrenler yalnız **hisselerden**
   seçilir; endeksler (XU100/XU30) hariç.176'daki iki endeks bu süzgecin
   gerisindedir; sonraki evren sayımlarında dikkate alınmaz.
4. **Rapor katmanı:** K2/K3 sayılarının yanına **sembol-gruplu bootstrap
   GA** eşlik eder (artık `olcum_ozet.json["ga95"]` ve kapı JSON'unda —
   yalnız görünürlük, kapı eşiği değişmez).
