# Faz 8 — "Ana50" Evreni (güçlü likit çekirdek) — Koşudan Önce Tescil

**Tarih:** 2026-11-10 · **Durum:** tescilli (holdout120 üzerinde çevrimdışı
ölçüm sonuçlandıktan sonra, doğrulama replay'inden ÖNCE).

## 1. Gerekçe (çevrimdışı ölçüm —990 holdout plan)

| Evren | n | pnl/plan | kayıp% | doğrulama bek |
|---|---|---|---|---|
| Tüm120 (Faz6/7 evreni) |990 | +0,2950 |48 | +0,1204 |
| **ANA50 (ciro top50)** | **412** | **+0,4259** | **42** | **+0,4073** |
| Diğer70 |578 | +0,2016 |52 | **−0,0722** |

- Kaybedenlerin kümesi:34 net-zararlı sembolün ilk10'u zararın %57'sini
  üretiyor;10'un7'si ciro sırası55+ (düşük likidite). **Oynaklık
  ilişkisi reddedildi** (Spearman ρ=−0,09; "kripto gibi" hipotezi
  veriyle çürütüldü — en oynakların çoğu kazanıyor).
- **Kural basit:** evren = ciro top50 (likidite = "güçlü ana hisse").
  Tek parametre değişikliği; filtre/kural değişikliği YOK (K1–K6 aynen).

## 2. Üretim dürüstlüğü (arşiv-sızıntısı notu)

Çevrimdışı ölçümde ciro sıralaması **arşiv ortalaması** ile hesaplandı
(inceleme-amaçlı). Üretim/doğrulama kuralı: **sıralama ilk30 günün ciro
verisiyle belirlenip sezon boyunca sabitlenir** (gelecek veri yok).
Büyük-likidite sıralaması stabil olduğu için (KCHOL/THYAO vb. hep üstte)
beklenen sapma minimal; replay bunu test eder.

## 3. Doğrulama replay'i

- `--semboller <ciro-top50>` · H=10 (Faz6/7 aynen) · teyit T1505 aynen.
- **Beklenen (çevrimdışıdan):** n≈412 plan · pnl/plan≈+0,426 ·
  doğrulama bek≈+0,41 · K1 (doğrulama UYGUN n) ≈412×0,226 ≈93 ≥50 ✓.
- Kapı eşikleri DEĞİŞMEZ. K2 beklentisi: diğer70 çıkınca UYGUN−kör
  farkı değişebilir — ölçülüp raporlanır (K2 hâlâ ana kırmızı aday).
- Sonuç FAZ6 raporu ile karşılaştırılıp karar verilir (kabul/redd).

## 4. Riskler

- **N düşer:**412 plan (K1 için yeterli, ama alt gruplar incelir).
- Ciro sıralaması ilk30 günde belirlenmezse (arşiv-ortalamasıyla
  ölçülürse) hafif gelecek-sızıntısı — üretimde kural §2'de.
- Kötü10'un3'ü (KCHOL/CCOLA/HEKTS) ana50'de KALIR — evren filtresi
  kronik-10'u tam temizlemez; ana etki likidite-ekstrem olan
  düşük ciro70'in çıkarılması.
- Rejim sinyali (genişlik ρ=+0,64) BİLEREK bu faza alınmadı —
  karmaşıklık maliyeti; ayrı faz adayı.
