# FAZ9 — Tecrübe Entegrasyonu (uzun görev ön-kayıdı)

**Tarih:** 2026-11-11 · **Durum:** AKTİF · **Kullanıcı görevi:**
*"bunları olabildiğince mantıklı ve anlamlı şekilde ekle, sistemimizin amacını
koruyarak çalış; replay'i çalıştır,50 sembolde sonuçların nasıl etkilediğini,
nerelerin düzeldiğini, nerelerin problem yaşadığını tespit et; amaca uygun
şekilde sistemi düzenle, felsefeye uygun test et."*

**Girdi:** `docs/arastirma/TECRUBE_ENVANTERI_2026-11-11.md` (69 genel ders) +
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

## 4. Tur A kayıtları

- (doldurulacak: commit, replay doğrulama, rapor yolları)
