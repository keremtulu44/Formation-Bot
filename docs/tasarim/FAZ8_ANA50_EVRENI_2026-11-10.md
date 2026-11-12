# Faz 8 — "Ana50" Evreni (güçlü likit çekirdek) — Koşudan Önce Tescil

> ⚠️ **GEÇERSİZ KAYNAK ŞERİDİ (2026-11-12, FAZ9-C denetimi):** Bu belgedeki
> tüm sayılar **sızıntılı tetikle** (G5 tepki-onayı gelecek bar okuyordu;
> FAZ9-C'de kapatıldı) ölçülmüştür. **Sayılar karar tabanı olarak
> GEÇERSİZDİR; yalnız tarihsel kayıt olarak durur.** Tek geçerli ölçümler:
> `docs/tasarim/faz9_tecrube/FAZ9_PLAN_VE_SONUCLAR.md` (audit-öncesi §8 +
> audit'li §11/§12).


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

---

## Replay Sonucu (2026-11-11,200 seri,0 hata,1.842 sn) → **KAPI: GEÇTİ (7/7)**

| Kapı | Eşik | Faz6 (tüm120) | Faz7 (H20) | **FAZ8 ana50** | |
|---|---|---|---|---|---|
| K1 | ≥50 |224 |223 | **90** | ✓ |
| **K2** | **≥+5,0** | −2,24 | −4,46 | **+5,03** | **✓ (ilk kez)** |
| K3 | >0 | +0,1204 | +0,0383 | **+0,4073** | ✓ |
| K4 | ≤5 |0 |0 | **0** | ✓ |
| K5 | =0 |0 |0 | **0** | ✓ |
| K6a | >0 | +0,346 | +0,4088 | **+0,4311** | ✓ |
| K6b | >0 | +0,1204 | +0,0383 | **+0,4073** | ✓ |
| **karar** | | GEÇMEDİ | GEÇMEDİ | **GEÇTİ** | **7/7** |

- **Offline↔replay birebir:** plan412 · sonuç137/132/143 — çevrimdışı
  öngörüyle **tam eşleşme** (determinizm korunuyor).
- **K2'nin dönüşü:** UYGUN koşullu44,83 − kör39,80 = +5,03 — paket
  (verdict+teyit) **çekirdek evrende ham akışı ilk kez geçiyor**;
  sürükleyici olan düşük-likidite70 idi (−0,07 doğrulama).
- Giriş kv233/133/28/18 · stop kalitesi127/132 = **%96,2 doğrulanmış** ·
  tutunma %31,7 (889 teyit_red) · n412/yıl.

**Dürüstlük notları:** (1) K2 marjı **ince:5,03 ≥5,0 (0,03 pay)** —
sınırda; (2) ölçüm aynı holdout120 üzerinde (evren seçimi ex-ante ciro
ama numune taze değil); (3) kesin onay adayı: **taze26 sembol** (hiç
kullanılmadı) veya yeni sezon verisi. Bu notlar kapı disiplininin parçası
olarak kayda geçti.
