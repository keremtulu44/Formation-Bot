# FAZ 2 FİNAL AUDİT RAPORU — "Formation history tamamlandı mı?"

**Commit:** `96cc78e` (branch `arena/01a1020f-formation-bot`, PR #15)
**Audit öncesi HEAD:** `0460350` — bu rapordaki tüm ürün davranışı ölçümleri `0460350` üzerinde yapıldı
**Kural:** yalnızca audit; matematik, eşik, outcome motoru, Telegram biçimleri değiştirilmedi

---

## 1) Test

| Ölçüm | Sonuç |
|---|---|
| Baseline `pytest -q` (audit öncesi, `0460350`) | **632 passed** in 61.32s |
| Final `pytest -q` (audit sonrası, `96cc78e`) | **638 passed** in 61.40s |
| Yeni audit testi | **6** (`test_p2_audit_lifecycle.py`) |
| `test_tarama_zamani.py` (script) | **102/102** |
| `collective_test.py` (script) | **9 pattern** bulundu — canlı test için hazır |
| Audit betikleri | AUDIT-A **6** + AUDIT-B **42** + AUDIT-C **33** = **81 kontrol, 0 hata** |

> Baseline **korundu** (632 → 638, +6 yeni test). Mevcut hiçbir test değiştirilmedi; yanlış
> varsayım içeren mevcut test **bulunmadı**. AUDIT-C'de çıkan 5 "hata" ve AUDIT-B'deki 1 "hata"
> tamamen kendi betik hatamdı (aşağıda kanıtlandı); üründe kusur yoktu.

---

## 2) Full lifecycle — zincir tamamı

İzlenen zincir ve her halkadaki sahiplik:

`Formation detection → stable_id → Formation Registry → Birth → Geometry snapshots → Lifecycle events → Breakout → Retest → Terminal → Outcome Link → Karne`

| Halka | Mekan | Sahiplik nasıl korunuyor |
|---|---|---|
| Formation detection | `patterns/detect.py` (DEĞİŞMEDİ) | `PatternCandidate` üretir |
| stable_id | `lifecycle._new_stable_id()` (`uuid4`) | motor-içi `identity`'den ayrı, kalıcı kimlik |
| Formation Registry | `lifecycle._match_registry` → `fh.eslestir(...)` | bar-time alignment ile eşleşme |
| Birth | `lifecycle._history_kaydet` → `fh.dogum_ekle` | idempotent; sadece `son_gorulme` tazelenir |
| Geometry snapshots | `fh.snapshot_ekle(..., ek={"stable_id", "state"})` | 4 `tur`'un hepsi kendi SID'sini taşır |
| Lifecycle events | `fh.olay_ekle` (dedup: `stable_id\|type\|name\|bar\|time`) | bilinmeyen SID sessizce atlanır |
| Breakout | `kirilim` snapshot'ı (20 BREAKOUT alan dondurulur) | freeze + teyit ayrı snapshot |
| Retest | `retest` snapshot'ı (18 STATE alan) | retest barına geometri yazılmaz |
| Terminal | `fh.terminal_ekle` (`ek={"stable_id","state"}`) | tek terminal snapshot |
| Outcome Link | `outcome_link.bagla` → `fh.sonuc_bagla` | yalnızca outcome gerçekten değiştiğinde yazar |
| Karne | `karne.kirilim_kaydet(stable_id=...)` | `main._karne_olay_kaydet` yönlendirir |

Gerçek motorla (`_kanalli_pennant(seed=8, n_bars=60)` + birikimli bar) tek formation
`FORMASYON_TAMAMLANDI`'ya ulaştı: **1 kayıt**, `durum='terminal'`.

---

## 3) SID continuity

| Aşama | Bulunan SID | unique |
|---|---|---|
| `birth:` | `bbbafd68-cd47-415a-825b-2ce16754fe14` | 1 |
| `geometry:` | `bbbafd68-…` (7 snapshot) | 1 |
| `event:` | `bbbafd68-…` (9 olay) | 1 |
| `breakout:` | `bbbafd68-…` (2 kirilim) | 1 |
| `retest:` | `bbbafd68-…` (2 retest) | 1 |
| `terminal:` | `bbbafd68-…` (1 terminal) | 1 |
| `outcome:` | `bbbafd68-…` (kaydın kendi SID'si üzerinden bağlandı) | 1 |
| **`unique SID:`** | — | **1** |

**SID kaybı / değişimi: YOK.** Yeni regression testi `test_yasam_dongusu_yedi_asama_tek_sid`
her aşamanın SID'sini ayrı ayrı toplayıp `v == {sid}` ve `len(tum) == 1` olmadıkça geçmez.

Sayımlar: `{geometri:7, kirilim:2, retest:2, terminal:1, olaylar:9}` — per-bar dump değil,
yalnızca anlamlı geçişler.

---

## 4) Multi-formation

Tek `(stock,tf)` içinde iki formation, ikisi de birth → geometri → kırılım → retest → terminal:

| | A (`b4b460d2`) | B (`a25600c1`) |
|---|---|---|
| geometri snapshot | 7 | 5 |
| olay | 11 | 7 |
| kirilim | 2 | 2 |
| retest | 2 | 1 |
| terminal | 1 | 1 |

- **Cross-contamination: 0.** A'nın geometri/olay/kırılım/retest/terminal verisi B'ye geçmedi; tersi de.
- Kendi SID'sini taşımayan snapshot/olay: **0**.
- A `FORMASYON_TAMAMLANDI`, B `BASARISIZ_KIRILIM` ile bitti — **iki farklı terminal anlamı korundu**.
- Outcome'lar kaynaşmadı: A `stop` (kaynak `2026-01-07T16:30:00+03:00`), B `stop` (kaynak `2026-01-10T08:30:00+03:00`).

---

## 5) Terminal → new formation

- `old_sid != new_sid` ✅
- Yeni formation'ın devraldığı eski geometri / kırılım / retest / terminal / outcome: **0**
- Eski kayıt history'de `durum='terminal'` ve outcome'ı korunmuş durumda kaldı.
- Terminal SID asla yeni formation'a taşınmaz.

---

## 6) Restart (6 nokta)

**(A) birth sonrası / (B) geometri sırasında / (C) breakout sonrası / (D) retest sırasında / (E) terminal sonrası / (F) outcome varken** → **18/18 PASS**

- `stable_id` korundu (Faz 1 anchor `state/formation_identity.py` üzerinden re-attach)
- history korundu, dondurulmuş breakout verisi korundu
- retest ve terminal history'si korundu, outcome bağlantısı korundu
- **Yalnızca RAM referansında yaşayan durum: YOK.** Tüm kalıcı durum diskte
  (`formation_history`, `formation_identity`, Karne). Motor içi teşhis alanları
  (`invalid_reason` gibi) zaten kontrat dışı ve bilerek persist edilmiyor (bkz. madde 10).

---

## 7) Replay / sliding window

| Ölçüm | Sonuç |
|---|---|
| `tam_yeniden=True` replay | mevcut kaydı değiştirmedi; **0 yeni kayıt**, 0 yeni snapshot |
| Kayan pencerede kayıt sayısı | **1 → 1** (kontrolsüz büyüme yok) |
| Snapshot sayısı | 12 ≤ `MAX_SNAPSHOT`=40 |
| Olay sayısı | 9 ≤ `MAX_OLAY`=200 |
| Aynı barlar 5× okunduğunda history | **değişmedi** |
| Duplicate (per `(sid, bar_time)` / `tur`) | geometri 0, kirilim 0, retest 0, terminal 0 |

**Gerçek kimlik sınırı vs persistence duplicate — ayırım:**
- Persistence duplicate'ı **yok** — yukarıdaki tüm sayaçlar 0.
- Gerçek kimlik sınırı olarak bilinen tek davranış: pencere farklı uzunlukta yeniden
  sınıflandırma tetiklenirse **yeni SID hak kazanır** (`test_yeniden_siniflandirma_yeni_sid_hakeder`).
  Bu **P2.2 identity matching'in tasarım özelliğidir**, `9b74afc`'ten beri böyledir ve
  P2.4/P2.5'ten kaynaklanmaz. Dokunulmadı.

---

## 8) Legacy / corruption

**Legacy (10/10):**
- Faz 1 `formation_identity.json` okunuyor. Gerçek imza `load_anchor(stock, tf)` / `save_anchor(...)`
  — `load_anchor` **2 zorunlu positional argüman** ister (audit betiğim argümansız çağırıp
  `TypeError` almıştı; API gerçek imzaydı, betik yanlıştı).
- `stable_id: None` ile yazılmış eski Karne kaydı çalışıyor; `stable_id_ozetleri` bunu
  **bilinçli atlıyor** (özet sayısı 0); `bagla(...)` eski kayda **bağlanmıyor** (None).
- Eski düz history biçimi, eksik field'li kayıt, bilinmeyen SID → crash yok.

**Corruption (10/10):** boş dosya, bozuk JSON, `kayitlar` eksik/yanlış tip, `stable_id`'siz,
snapshot'sız, bilinmeyen `tur`, üst-seviye liste, `null`, sayı → **tarama durmuyor**,
0–1 kayıtla devam ediyor. Mevcut self-repair davranışı bozulmadı.

---

## 9) Persistence

| Ölçüm | Sonuç |
|---|---|
| Tarama sayısı | 5 |
| Disk yazımı (`kaydet`) | **3** |
| Oran | **60%** |
| **Per-bar persistence** | **NO** |

Mevcut mimarinin doğal davranışı ölçüldü — **yeni bir eşik icat edilmedi**. `_history_kaydet`
defteri tek kez yükleyip tüm mutasyonları uygulayıp tarama başına **en fazla bir kez** kaydeder.

---

## 10) Information loss — açık cevap

> *"Formation'ın yaşamındaki önemli bir bilgi mevcut motor tarafından hesaplandığı halde
> history'de tamamen kayboluyor mu?"*

### Kontrat içinde: **HAYIR.**

| Sınıf | Alan | Persist edilen |
|---|---|---|
| IDENTITY | 32 | **32/32** |
| STATE | 18 | **18/18** |
| BREAKOUT | 20 | **20/20** |
| TRANSIENT | 16 | bilerek 0 (sızıntı **0**) |
| **INCELENMELI** | 48 | **48/48** (P2.0'da "henüz persist edilmeyen" listesi) |

- Şema dışı alan: **0**. TRANSIENT sızıntısı: **0**.
- `break_confirmation_strength` **kaybolmamıştır**: kırılım dondurma (`KIRILIM_DENEMESI`)
  anında `None` olması **doğrudur** (teyit henüz olmamıştır); teyit (`KIRILIM_TEYITLI`)
  anında `22.698` olarak history'ye ulaşıyor. Bunu regression testine aldım.

### Kontrat dışında tek öğe: `ArgentEngine.invalid_reason`

| | |
|---|---|
| **1. Hangi bilgi** | Mevcut/terminal durumun nedeni (örn. *"Kırılım denemesi formasyon içine döndü"*, *"Retest korunumu bekleniyor"*) |
| **2. Hangi aşamada** | Terminal |
| **3. Neden kayboluyor** | Alan **motor üzerinde** yaşar, `PatternCandidate` üzerinde değil. P2.0 kontratı persistence kapsamını açıkça `PatternCandidate`'ın 85 alanıyla sınırlamıştır |
| **4. Gerçekten tarihsel mi** | **KISMEN.** Başarısız terminallerde (`BASARISIZ_KIRILIM`, `FORMASYON_GECERSIZ`) neden gerçekten tarihseldir ve persist edilen snapshot'lardan **türetilemez**. Başarılı terminalde ise canlı durum tanımıdır, sonuç nedeni değil |

**Karar: bu turda düzeltmedim — raporladım.** Gerekçe: (a) P2.0 kontratı bunu hiç vaat etmemişti,
yani regresyon değil kapsam sınırıdır; (b) bu tur "audit only / yeni özellik ekleme" kuralına
tabi; (c) `terminal_state` **ne** olduğunu zaten saklıyor, yalnızca başarısızlık terminallerinde
**nedeni** eksik. Davranış bilinçli sınır olarak testle sabitlendi
(`test_motor_seviyesi_invalid_reason_bilincli_olarak_historyde_degil`).

**Transient olarak doğru şekilde persist edilmeyenler (bug İLAN ETMİYORUM):**
16 TRANSIENT alan (ihlal önbellekleri, `selection_score`, `valid`, `identity`), RAM'deki
ham `Timestamp`'li olay listesi (JSON güvenliği yazma anında sağlanır), motor konfigürasyon
parametreleri (`min_quality`, `retest_window`, `horizon`, …) — bunların hiçbiri tarihsel
bilgi değildir.

---

## 11) Math

| Soru | Cevap | Kanıt |
|---|---|---|
| Formation math değişti mi? | **HAYIR** | `patterns/pivots.py`, `mathutil.py`, `pole.py`, `indicators.py`, `detect.py`, `selection.py`, `violation.py`, `constants.py` → **0 satır değişiklik** |
| Breakout kriterleri değişti mi? | **HAYIR** | |
| Retest kriterleri değişti mi? | **HAYIR** | |
| Outcome math değişti mi? | **HAYIR** | `karne.sinyal_sonucu` ve `karne.karne_hesapla` **BYTE-IDENTICAL** (`ast.get_source_segment` karşılaştırması) |
| `sinyyal_sonucu`, MFE, MAE, ATR, target, stop, horizon değişti mi? | **HAYIR** | yukarıdaki byte-identical kanıtı |
| Karne doğruluğu değişti mi? | **HAYIR** | `karne.py` farkı yalnızca `stable_id` **parametresi** + kayda yazılması; outcome hesabı bu alanı kullanmaz |

`patterns/candidate.py` farkı tek bir alan: `stable_id: Optional[str] = None` (+3 satır yorum).
`patterns/lifecycle.py` modül yapısı bozulmamış (modül-seviyesi `def`/`class` sırası doğrulandı).

Outcome motoru bağımsız olarak **üç sonuç** için doğrulandı (yalnızca bağlantı ölçümü, matematik
yeniden hesaplanmadı): yükselen seri → `hedef`, düşen seri → `stop`, düz seri → `nötr`.

`birincil_outcome` kuralı teyit edildi: **çözümlenmiş (hedef/stop/nötr) > bekliyor**; aynı
grupta **en yeni bar_time** kazanır. (Üç deneme de çözümlenmiş olduğunda en yenisi — `nötr` —
hak kazanır; bu tasarım gereğidir, hata değil.)

---

## 12) Kod değişikliği

### Bu audit turu (`96cc78e`)

| Dosya | Neden | Minimal değişiklik | Yeni test |
|---|---|---|---|
| `test_p2_audit_lifecycle.py` (yeni, 6 test) | Audit ölçümlerini regression'a dökmek | yalnızca yeni dosya; mevcut koda dokunulmadı | 6 |

**Ürün kodu değişikliği: YOK.**

### P2.4/P2.5'ten kalan (audit edilen, bu turda dokunulmayan)

| Dosya | Neden | Minimal değişiklik |
|---|---|---|
| `patterns/lifecycle.py` | snapshot'ların kendi SID'sini taşıması; terminal snapshot'ına `ek` | `ek={"stable_id","state"}` — saf additive metadata |
| `state/formation_history.py` | `terminal_ekle`'in `stable_id`/`state` geçirmesi | mevcut `ek` mekanizması kullanıldı |
| `karne.py` | Karne kayıtlarının SID taşıması | `stable_id` parametresi (default `None` = geriye dönük uyum) |
| `main.py` | Karne olay yönlendirmesi + outcome bağlama | yalnızca `stable_id` aktarımı + yeni `_karne_outcome_bagla`; **Telegram biçimi değişmedi** |
| `patterns/candidate.py` | kalıcı kimlik alanı | 1 alan + yorum |

Hiçbir dosyada `formasyon_kaydet` dedup/TTL, `stock|tf|patern` kayıt mantığı, yeni outcome
datastore'u veya yeni soyutlama **oluşturulmadı**.

---

## 13) Final verdict

### ✅ READY FOR P2.6

**Ölçülmüş kanıtlara dayalı gerekçe:**

1. **Zincir eksiksiz.** 7 aşamanın hepsinde tek SID; `len(unique(sid)) == 1` — artık regression testi var.
2. **Kontrat tam kapsandı.** INCELENMELI 48/48, IDENTITY 32/32, STATE 18/18, BREAKOUT 20/20,
   TRANSIENT sızıntısı 0, şema dışı alan 0.
3. **Sahiplik izolasyonu kanıtlandı.** Çoklu formasyonda cross-contamination 0; terminal sonrası
   yeni formation eski veriyi devralmıyor.
4. **Dedup / replay sağlam.** 7 mekanizmanın hepsinde duplicate 0; aynı barlar 5× okunduğunda
   history değişmiyor; kayan pencerede kontrolsüz büyüme yok.
5. **Geriye dönük uyumluluk ve bozulma dayanıklılığı.** 10/10 legacy + 10/10 corruption.
6. **Matematik ve outcome motoru dokunulmamış.** Outcome fonksiyonları byte-identical.
7. **Baseline korundu.** 632 → 638.

**Minor follow-up (P2.6'yı engellemez):**
- `ArgentEngine.invalid_reason` kontrat dışıdır ve bilinçli olarak persist edilmiyor.
  Başarısız terminal nedenleri (`BASARISIZ_KIRILIM` / `FORMASYON_GECERSIZ`) tarihsel değer
  taşır ve snapshot'lardan türetilemez. Kapsam sınırı olarak raporlandı, bu turda
  "audit only" kuralı gereği düzeltilmedi. P2.6'da veya küçük bir P2.5.x'te değerlendirilebilir.
- P2.2'den beri bilinen: pencere farklı uzunlukta yeniden sınıflandırma tetiklenirse yeni SID
  hak kazanır. Tasarlanmış davranış, kusur değil; dokunulmadı.

---

## Ek: bu turda çözülen audit betiği hataları (ürün hatası DEĞİL)

| # | Betik hatası | Gerçek davranış |
|---|---|---|
| 1 | Üç Karne kırılım kaydı **aynı `bar_time`** ile yazıldı → dedup anahtarı `{stock}\|{tf}\|K\|{bar_iso}` çakıştı | İlk kayıt yazılır, diğerleri atlanır (doğru). Farklı bar aralığına kayınca 3/3 yazıldı |
| 2 | Sinyal barından **önce** seri kuruldu | `sinyal_sonucu` ileri penceresi boş kalır → `bekliyor` |
| 3 | `dir=0` NÖTR senaryosu | `kirilim_kaydet` `dir not in (1,-1)` reddeder; düz seri + `dir=1` → `nötr` |
| 4 | Long için STOP senaryosu yükselen seriyle kuruldu | Düşen short hedefine ulaşır; STOP için seri **aşağı** gitmeli |
| 5 | `fid.load_anchor()` argümansız | Gerçek imza `load_anchor(stock, tf)` |
| 6 | `karne_legacy.kayitlar()` paylaşımlı disk dosyasını saydı | `KarneDefteri` stock'lara göre global; `stable_id is None` ile filtrelendi |
| 7 | Doğumsuz kayda snapshot'ın **reddedilmesi** beklendi | `snapshot_ekle` yalnızca kaydın varlığını ister — tasarım gereği kabul |
| 8 | Sabit ofsetli `pd.Timestamp("…+03:00")` `date_range(tz="Europe/Istanbul")` içinde | pandas `AssertionError` → sağlayıcı hata verir → `ölçülemedi`. `localize` ile çözüldü |
| 9 | AUDIT-B [F]: 1. tarama (30 bar, henüz formation yok, 0 kayıt) son taramayla karşılaştırıldı | "Büyüme" yanılgısı; ilk kayıttan sonra ölçüldü ve 5× aynı-bar kontrolü eklendi |
