# MS kilitli-referans düzeltmesi — 2026-10-28

**Durum:** Kayıt · **Kapsam:** `domain_engines/market_structure/*` (yalnız recovery/saklama katmanı) ·
**Yöntem:** arşiv üzerinden kök-neden izleme (bar bar), üç katmanlı düzeltme, 35 serilik hedef regresyon + tam suite.

Bu belge **o günün** düzeltme kaydıdır; bugünün durumunu koddan okuyun.

## 1. Özet

| # | Madde | Önem | Durum |
|---|---|---|---|
| M1 | MS motoru 704 serinin 35'inde (%5,0) `ValueError: confirmed break references must still be active` ile düşüyor, domain sessiz boş kalıyor (arşiv bulgusu) | **Kritik** (canlıda yapısal kör nokta) | ✅ kök neden düzeltildi |
| M2 | Kök neden: bekleyen kırılımın **geçici referansı**, aday slotu "prior identity locked by break" ile fork edilince hiçbir yerde saklanmıyor | Kritik (M1'in sebebi) | ✅ fork anında snapshot saklanır |
| M3 | Görünür degrade (`/durum` MS arıza satırı) araştırma belgesinde "öneri" olarak duruyordu | Düşük (belge tazeliği) | ✅ kodda zaten var; belge notu güncellendi |

**Doğrulama (2026-10-28):**

```
eski 35 hatalı seri (hedef regresyon)  → 0/35 MS hatası
pytest -q                              → 2725 passed, 0 failed (+6 yeni test)
ruff check .                           → All checks passed (F/E9/S110 kapısı)
test_tarama_zamani.py                  → 102/102
test_breakout/flag/pennant/triangle.py → yeşil
```

Yeni kilit testi: `test_ms_kilitli_referans.py` (6 test — 4 sentetik unit + 2 arşiv regresyonu;
arşiv yoksa ikisi atlanır, sentetik katman `backfill_data/` olmadan da koşar).

## 2. Kök neden (bar bar iz, AEFES/1h)

Hata zinciri üç katmanın karşılaşmasıyla oluşur:

1. **Bekleyen kırılım geçici referans alır.** Bar 2367'de CHOCH adayı açılır
   (`candidate_bar=2367`); origin, henüz `swings` listesine **girilmemiş** geçici bir
   low swing'dir (`identity=745`, `source_bar=2357`) — yani yalnız aday slotunda yaşar.
   `finalize_confirmed_break` onay anında iki referansın da `swings` içinde *aktif*
   olmasını ister (`market_structure_state.py`).

2. **Sonraki bar slotu fork eder.** Bar 2368'de daha güçlü bir low pivot kabul edilir.
   Aday kilitlidir (`locks_candidate` — bekleyen kırılım `origin=745`'i referans alır),
   bu yüzden `_candidate_update` "prior identity locked by break" dalıyla slotu **taze
   kimliğe** (747) taşır: `replace(incoming, evidence_text="candidate fork: …")` eski
   snapshot'ı slottan çıkarır ve hiçbir yere yazmaz.

3. **Onay hiçbir referansı bulamaz.** Bar 2368'de kanıt tamamlanır →
   `finalize_confirmed_break` → `active_by_id(745)` → listede yok → `ValueError`.
   Köprü (`market_structure_runtime_bridge`) devreye girer ama kurtarma yolu yalnızca
   (a) `swings` listesi ve (b) **o anki** aday slotu üzerinden arar; fork edilmiş
   snapshot gittiği için kurtarma başarısız ve hata yukarı fırlar.
   `runner._execute_domain` bu hatayı yutar → o sembolün **MS domaini sessizce boş**:
   BOS/CHOCH hiç üretilmez (1h'de 20 sembol = botun her gün kör kaldığı yapısal kırılımlar).

Ölçüm: `docs/arastirma/arastirma_ms_hatali_seriler.txt` (35 seri) — hepsinde aynı imza.
Bu düzeltilmeden önce 33/33 hedef seri canlı yolda (`run_domain_engines`) birebir
yeniden üretildi.

## 3. Düzeltme (üç katman, matematik DEĞİŞMEDİ)

Kırılım/onay kalitesi, break buffer'ları, state geçişleri **dokunulmadı**; yalnızca
"kaybolan snapshot'ın saklanması + kurtarmada kullanılması" eklendi:

1. **Saklama** — `market_structure_engine.py::_candidate_update`:
   kilit aktiken slot fork edilirse (`action == CANDIDATE_NEW` ve geçerli eski aday),
   eski snapshot `_RuntimeScope.retained_locked` haritasına kimlikle yazılır
   (`retain_locked_snapshot`).

2. **Kurtarma** — `market_structure_runtime_bridge.py::process_scope`:
   recovery, slotta eş bulamazsa artık `pop_retained_snapshot(scope, identity, source_bar)`
   ile fork anındaki snapshot'ı dener (kimlik + `source_bar` eşleşmesi zorunlu, tek
   kullanımlık). Eşleşen snapshot `_commit_missing_reference` ile geçici → onaylı
   promosyonu yapar, sonra aynı bar için finalize yeniden denenir (mevcut akış aynen).

3. **Temizlik** — `market_structure_runtime.py`: aday çözüldüğünde (onay **veya**
   false break) `retained_locked.clear()`; bayat entry hiçbir sonraki adaya sızamaz.

Saklama yalnız kilitli fork anında tetiklenir; kilitsiz normal REPLACE/REJECT/MERGE
akışı davranış olarak **birebir aynıdır** (test: `test_kilitsiz_slot_guncellemesi_saklama_yapmaz`).

## 4. İlgili belge tazeliği

* `docs/arastirma/README.md` ⚠️ bölümü — bulgu artık **düzeltilmiştir**; notu güncellendi.
* Görünür degrade önerisi (`_execute_domain` hata versin) bu düzeltmeden ÖNCE kodda
  mevcuttu: `notification_context.market_yapisi_hatali` → `bot/commands._ms_hata_kaydet`
  → `/durum`da `⚠️ MS (piyasa yapısı) motoru: N hissede hata` satırı. Kök neden
  düzeldikten sonra bu satır yalnız **gelecek** MS hataları için teşhis görevi görür.
* `docs/arastirma/arastirma_ms_hatali_seriler.txt` tarihli kayıt olarak durur (silinmez).
