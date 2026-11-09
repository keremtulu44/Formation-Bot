# Eğitim karesi + lejant dili + ◇ ikinci tur — 8 Kasım 2026

Bu set, `docs/arastirma/OK_SISTEMI_2026-11-08.md` **§14**'ün kanıtıdır.

| Dosya | Neyi kanıtlar |
|---|---|
| `00_pano.png` | Tek sayfa özet: lejant **önce → sonra** (GARAN yoğun kare + AGHOL), replay/eğitim karesinde **direnç katmanı** (▼) ve ◇ ikinci tur ölçüm eğrisi + tablo |
| `01_egitim_karesi_garan.png` | Replay karesinin tam hâli: ▼ dönüş işaretleri ve ┄ direnç seviyesi kadrajda |

## Neyi değiştirdi
1. **Eğitim karesi:** `research/replay_egitim.py` artık canlı `/grafik` ile aynı direnç köprüsünü
   kullanıyor (`resistance_for_chart`, aynı nedensel kesim). Soru karelerinde ▼ dönüş oku görünür.
2. **Lejant dili:** iki katman başlığı (`┄ Stabil destek (yeşil)` / `┄ Stabil direnç (turuncu)`) +
   tek ok sözlüğü (`▼ dönüş = sinyal · ▲ geri alım = yapı · boş = momentum · ◇ = uyarı`).
   Kırpıcı bu maddeleri **korumaz**; yoğun karede ok sözlüğü düşüyordu — düzeltildi (§14.2).
3. **◇ ikinci tur:** ölçüldü, **uygulanmadı**. 50 bar seçeneği 486 → 364 (−%25) ve kilitli eşikleri
   geçen tek aday; karar kullanıcıda (§14.3).

## Yeniden üretmek için
```bash
PYTHONPATH=. .venv/bin/python research/stabil_cizgi_seyreltme_olcum.py   # ◇ ölçümü (≈100 sn)
PYTHONPATH=. .venv/bin/python research/ok_egitim_ozet_pano.py             # kare + pano
```
