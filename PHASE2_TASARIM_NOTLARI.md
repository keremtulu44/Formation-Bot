# Phase 2 — Tasarım Notları

Bu dosya Phase 1 kapanışını ve Phase 2'ye devredilen bulguları taşır.
**Implementation notu değildir.** Phase 1 kapanış şartları altında aşağıdaki alanlar
değiştirilmemiştir: geometry, quality, threshold, `continuity_score`,
`identity_compatible`, lifecycle transitions, anchor persistence logic.

---

## 1. Phase 1 Durumu: TAMAMLANDI

Phase 1 (Persistent Formation Identity) correctness açısından tamamlanmıştır.

Doğrulanan davranışlar:

| Alan | Durum |
|---|---|
| Tek formasyonlu sliding-window senaryosu | stabil |
| Restart sonrası re-attach | stabil (ölçülen skor 100.0) |
| Terminal → yeni formation `stable_id` ayrımı | doğru (X ≠ Y) |
| Gerçek `tam_yeniden=True` production path | doğru |
| Yanlış / çapraz ID taşıma | **0 olay** |
| Anchor disk güncelliği | tüm senaryolarda güncel |

Phase 1 kapsamındaki son düzeltme: `ArgentEngine.reset()` içinde `_key`'in
korunması (`af3e51b`). `_key`, motorun formation/lifecycle state'i değil,
manager'ın motoru hangi `(stock, timeframe)` kaydına bağladığını tutan
metadata'dır; reset sırasında silinmesi `tam_yeniden=True` taramasında
`_match_persisted_anchor` / `_save_formation_anchor`'u erken çıkışa zorluyor,
böylece her taramada yeni UUID üretiliyor ve restart re-attach devre dışı kalıyordu.

---

## 2. Phase 2 Finding — Multi-Formation / Sliding-Window Identity History

Mevcut Phase 1 mimarisi tek `(stock, timeframe)` için **tek** persisted formation
anchor tutuyor.

Bu yapı:

- tek formasyonlu sliding-window senaryosunda stabil,
- restart sonrası re-attach'te stabil,
- terminal → yeni formation `stable_id` ayrımında doğru,
- gerçek `tam_yeniden=True` production path'te doğru,

ancak aynı `(stock, timeframe)` penceresinde birden fazla fiziksel formasyon
bulunduğunda **identity churn** oluşabiliyor.

### Audit kanıtı

- çoklu formation + sliding window senaryosunda canlı formation `stable_id`
  churn görüldü,
- yanlış ID taşıma görülmedi,
- restart re-attach başarılı,
- guard kaldırma simülasyonu problemi çözmedi,
- anchor yenileme de tek-slot mimarisi nedeniyle problemi çözmüyor.

### Ölçülen değerler (audit, `tam_yeniden=True` production yolu)

| Senaryo | Tarama | Formasyon | `stable_id` değişim | Gereksiz yeni ID | Canlı churn | Yanlış taşıma | Restart | Anchor |
|---|---|---|---|---|---|---|---|---|
| Aynı formasyon + kaymalı pencere W=45 | 15 | 1 | 1 | 1 | 1 | YOK | – | GÜNCEL |
| Aynı formasyon + kaymalı pencere W=90 | 21 | 1 | 1 | 1 | 0 | YOK | – | GÜNCEL |
| Çoklu formasyon + kaymalı pencere W=90 | 21 | 2 | 19 | 18 | 18 | YOK | – | GÜNCEL |
| Çoklu formasyon + büyüyen pencere | 53 | 2 | 5 | 4 | 4 | YOK | – | GÜNCEL |
| Restart (güncel pencere) + kaymalı devam | 15+4 | 1 | 1 | 1 | 1 | YOK | BAŞARILI | GÜNCEL |
| Gerçek bot yolu (4× aynı df) | 4 | 1 | 0 | 0 | 0 | YOK | – | GÜNCEL |
| Sıklık: 4 formasyon + kaymalı W=90 | 132 | 3 | 34 | 32 | 22 | YOK | – | GÜNCEL |
| Artımlı yol (`tam_yeniden=False`) | 111 | 1 | 0 | 0 | 0 | YOK | – | – |

### Kök neden (ölçüldü)

`tam_yeniden=True` her taramada tüm pencereyi baştan oynattığı için pencere içindeki
her formasyon yeniden "doğuyor". İki etken birlikte çalışıyor:

1. **`if not self.active.valid` guard'ı** — pencere içindeki ikinci formasyon doğduğunda
   `self.active.valid == True` olduğundan `_match_persisted_anchor` hiç çağrılmıyor,
   koşulsuz yeni UUID üretiliyor.
2. **Tek yuvalı anchor salınımı** — ilk formasyon doğumunda anchor'u çalıyor. Anchor her
   taramada iki formasyon arasında salınıyor ve hiç stabilize olmuyor
   (`anchor→aday`: `68>20, 20>19, 19>66, 66>65, 65>64, …`).

Guard'ın kaldırılması durumunda doğum anında ölçülen `continuity_score`
değerleri: **25.0, 25.0, 0.0, 0.0** — hepsi eşiğin (60) altında. Yani guard'ı
kaldırmak tek başına problemi çözmüyor; anchor zaten bir önceki formasyonun
yapısını tutuyor. Anchor'u her güncellemede yenilemek de tek yuva mimarisi
nedeniyle salınımı engellemiyor.

### Phase 2'de tasarım yönü

Bu nedenle Phase 2'de çözümün:

- tek anchor yerine **çoklu formation identity/history registry**,
- **`stable_id` → formation history** bağlantısı,
- **sliding-window yeniden keşfinde doğru historical formation eşleştirme**,
- **aynı anda birden fazla formation'ın bağımsız kimliklerini koruma**

üzerinden tasarlanması gerektiğini not et.

> Bu madde Phase 1 kapsamında düzeltilmemiştir ve production kodunda bir
> değişikliğe neden olmamıştır.

---

## 3. Ayrı Bulgu — Flama → Simetrik Üçgen Sınıflandırma Geçişi

Kaymalı pencerede aynı fiyat yapısının farklı taramalarda farklı sınıflandırıldığı
gözlemlendi:

```
t=47: family=Flama  classic_dir=1  pattern_type=Boğa Flaması
t=48: family=Üçgen  classic_dir=0  pattern_type=Simetrik Üçgen
```

Sonuç: `identity_compatible` = False, `continuity_score` = 0.0, yeni UUID.

Bu bir `stable_id` correctness problemi olarak sınıflandırılmayacak. Pattern
classification / formation-family sınır durumu olarak **ayrı Phase 2+ araştırma
maddesi** olacak.

---

## 4. Phase 1 Kapanışında Değiştirilmeyenler

- geometry
- quality
- threshold
- `continuity_score`
- `identity_compatible`
- lifecycle transitions
- anchor persistence logic

Mevcut test sonuçları korunmuştur: `pytest -q` → 512 passed,
`python3 test_tarama_zamani.py` → 102/102.

---

## 5. Faz 2.0 / 2.1 / 2.2 Uygulaması (bu commit)

Hedef: **"Formasyonun tüm yaşam döngüsünü hatırlayan motor."** Uygulanan
sıra, değerlendirmede önerilen yol haritasıdır: P2.0 → P2.1 → (P2.5 sonra) →
P2.2 → P2.3 → P2.4. Bu commit P2.0, P2.1 ve P2.2'yi kapsar.

### 5.1 Faz 2.0 — Field & Event Contract (`state/formation_schema.py`)

Model icat edilmedi; motora gömülü 85 alan sınıflandırıldı:

| Sınıf | Alan | Anlam |
|---|---|---|
| `IDENTITY` | 32 | Doğumda sabit: kimlik, doğum geometrisi, direk (pole) |
| `STATE` | 18 | Zaman içinde değişir: sınır, genişlik, dokunuş, kalite bileşenleri |
| `BREAKOUT` | 20 | `freeze_pattern_quality` anında dondurulanlar (Faz 2.4'te serileştirilir) |
| `TRANSIENT` | 16 | Türetilmiş/önbellek: **asla** history'ye yazılmaz |

Doğrulanan: 85/85 alan sınıflandırıldı, eksik/fazla yok. Tek bilinçli
çakışma `raw_quality` (doğum değeri IDENTITY, anlık değer STATE).

`PERSISTED_TODAY` (21 alan) disk üzerinde ölçüldü (anchor 14 + `formasyon_kaydi`
7 ek alan). `INCELENMELI` = sınıflandırılmış ama bugün yazılmayan **48 alan** —
tahmin değil, ölçüm.

### 5.2 Faz 2.1 — Formation History Registry (`state/formation_history.py`)

`(stock, timeframe) → birden fazla kayıt → stable_id → history`.
Dosya düzeni: `bot_data/formation_history/{STOCK}_{TF}.json`
(`bot_data/{STOCK}.json` yazım kuralı taklit edilir).

**Bar-time alignment — en kritik tasarım kararı.** Tüm bar indeksleri
pencere-relatiftir ve her taramada ~1 birim kayar. Ham indeks karşılaştırması
kaymaya açıktır. Bu yüzden defter doğum anının **mutlak zamanını** saklar ve
eşleştirmede:

```
delta = bugünkü_konum(doğum_bar_zamanı) - kayıtlı_doğum_indeksi
```

hesaplayıp kaydın bar indekslerini `delta` ile taşır; **fiyatlara dokunmaz**.
Böylece `identity_compatible` ve `continuity_score` (60 eşiği dahil)
**DEĞİŞTİRİLMEDEN** aynı pencere koordinat sisteminde çalışır.

Güvenlik kuralları (öncelik sırası):
1. **Yanlış birleşme asla olmamalı.** Doğum barı pencerede değilse kayıt
   atlanır; eşleşme olmaması tercih edilir.
2. Gereksiz yeni ID en aza indirilir.
3. Bir scan'de aynı `stable_id` iki farklı candidate'a atanamaz
   (`_p2_kullanilan` kümesi, deterministik "ilk gelen alır").
4. Terminal kayıt asla eşleşmez (kayıt durumuna göre — motor belleğine göre
   eleme KATI olarak güvenlidir, çoklu formasyonda motor belleği yanıltıcıdır).

### 5.3 Faz 2.2 — Olaylar `stable_id` taşır (`patterns/lifecycle.py`)

`_emit` tek bir additif anahtar kazandı: `stable_id`. Mevcut anahtar adları
(`type`, `name`, `bar`, `time`, `state`) **değişmedi**.

Yazma yalnızca anlamlı olaylarda tetiklenir (per-bar dump YOK): doğum, olay,
terminal. Tek taramada tek save: defter bir kez yüklenir, tüm mutasyonlar
uygulanır, en fazla bir kez yazılır.

### 5.4 Ölçüm — gerçek BIST verisi (28 hisse × 4 TF)

| Senaryo | Faz 1 (önce) | Faz 2.1 (sonra) |
|---|---|---|
| Kayan pencere, tek formation | `ortak=1, yeni=6, kayip=6` | `ortak=7, yeni=0, kayip=0` |
| Kayan pencere, 3 formation | kayıt sayısı `2 → 4 → 6` | kayıt sayısı `2 → 3 → 3` |
| Gerçek bot yolu (collective_test) | — | 9 defter, 36 kayıt, 257 olay |

Bar-time alignment'ın doğrulaması: pencere kaydığında translate edilmiş kaydın
pivotları adayla **birebir** örtüşüyor (`pivot_overlap_count = 4`,
`start_distance = 0`, fiyatlar aynı). Kimlik değişimi yalnızca
Flama→Üçgen **yeniden sınıflandırmasında** oluyor — bu §3'te dokümante edilmiş
ve kabul edilmiş davranıştır (`identity_compatible` matematiktir, değiştirilmez).

### 5.5 Değiştirilmeyenler (doğrulandı)

- formasyon matematiği, geometri, kalite, threshold'lar
- `identity_compatible`, `continuity_score` (60 eşiği dahil)
- lifecycle state makinesi ve geçişleri
- Faz 1 `formation_identity.py` — geriye dönük uyumluluk korunur; registry
  boşken davranış birebir aynıdır
- karne yazımı ve `sinyal_sonucu`
- olay sözlüğü anahtar adları

### 5.6 Testler

`test_formation_history.py` — 37 test (sözleşme, registry, kimlik, çoklu
formasyon, yanlış eşleşme güvenliği, terminal, olay, retention, **mutasyon**).

Mutasyon kanıtı: `_match_registry` çağrısı devre dışı bırakıldığında 3 test
başarısız olur (`test_coklu_formasyon_kayan_pencerede_kimlik_korunur`,
`test_kayan_pencerede_kayit_sayisi_kontrolsuz_artmaz`,
`test_aktif_formation_sid_kayan_pencerede_sabit`) — düzeltme gerçekten
gereklidir.

### 5.7 Doğrulama

- `pytest -q` → **549 passed** (512 + 37 yeni)
- `python3 test_tarama_zamani.py` → **102/102**
- `python3 collective_test.py` (gerçek BIST verisi) → 9 pattern, 9 defter üretildi
- Bozuk defter senaryosu: startup raporu bozuk dosyayı tespit eder, bot çalışmaya devam eder
