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
