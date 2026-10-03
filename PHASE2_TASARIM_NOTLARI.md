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
