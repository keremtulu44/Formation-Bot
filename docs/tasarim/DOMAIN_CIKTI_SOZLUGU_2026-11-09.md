# Domain Çıktı Sözlüğü — motorların verebildiği TÜM çıktılar

**Tarih:** 2026-11-09 · **Durum:** Referans (kod okunarak üretildi; kod değiştirilmez)
**Amaç:** [Senaryo Motoru Brifing Sözleşmesi](SENARYO_MOTORU_BRIFING_SOZLESMESI_2026-11-09.md) §3
(bildiri şeması) için **kaynak envanteri**: her domain'in native olarak
verebildiği çıktıların tam listesi. Kural: **çıktı kırpılmaz** — brifing bu
sözlükten beslenir, "yukarı/aşağı" bitine indirgenmez.
**Kaynak:** `domain_engines/` altındaki export/dataclass/enum tanımları
(2026-11-09 itibarıyla bu checkout).

---

## 0. Ortak kabuk — `EngineResult` (tüm domainler)

`domain_engines/market_structure/models.py` (base engine sözleşmesi):

| Alan | Tip | Anlamı |
|---|---|---|
| `engine` | str | Motor adı |
| `state` | str | Motorun kendi durum metni |
| `timestamp` | Any | Bar zamanı |
| `direction` | `Direction` (UP/DOWN/NEUTRAL) | **Tek bit — tek başına asla yeterli değildir; yanındaki alanlarla okunur** |
| `score` / `quality` | float\|None | Motorun kendi skoru |
| `levels` | dict[str, float] | Seviyeler (seviye adı → fiyat) |
| `events` | tuple[str, ...] | Bu barda tetiklenen olay adları |
| `reasons` | tuple[str, ...] | Redd/sebep metinleri (açıklanabilirlik) |
| `is_confirmed` | bool | Teyitli mi |

Base contract: `replay(frame)` / `update(bar)` / `snapshot()` — üçü de aynı
sözleşmeyi uygular.

---

## 1. Market Structure (MS)

**Export:** `MarketStructureExport` (`market_structure_evidence.py`, contract v3)

| Alan | İçerik |
|---|---|
| `external_state` / `internal_state` | Kod: **2.0 BOĞA · 1.0 geçiş-yukarı · 0.0 nötr · −1.0 geçiş-aşağı · −2.0 AYI** (`export_state_code`) |
| `evidence_score` | Kanıt skoru |
| `external_protected_low/high` · `external_weak_low/high` | **PL / PH / WL / WH** (dış kapsam) |
| `internal_protected_low/high` · `internal_weak_low/high` | Aynıları iç kapsam |
| `events` | `tuple[MarketStructureEventRecord, ...]` — **silinmez olay defteri** |
| `latest_external_event` / `latest_internal_event` | En taze olay |
| `external_scope` / `internal_scope` | `MarketStructureScopeSnapshot` (kapsam özeti) |

**Olay kaydı** `MarketStructureEventRecord`:

| Alan | İçerik |
|---|---|
| `event_type` | **`BOS` · `CHOCH` · `FALSE_BREAK` · `TRANSITION_FAIL`** |
| `scope` | `EXTERNAL` / `INTERNAL` |
| `direction` | UP / DOWN |
| `event_bar`, `candidate_bar`, `candidate_at`, `confirmed_at` | Zaman ekseni (aday vs teyit ayrımı) |
| `broken_level`, `broken_source_bar/at`, `broken_swing_identity` | Kırılan seviye + köken |
| `origin_price`, `origin_source_bar/at`, `origin_swing_identity` | Olayın köken swing'i |
| `quality`, `event_uid`, `identity` | Kalite + kimlik |

**Brifing'e katkısı (G3):** taze BOS/CHoCH (yaş/süpürme süzgeciyle), yanlış
kırılım (`FALSE_BREAK`), geçiş çöküşü (`TRANSITION_FAIL`), PH/PL/WH/WL
seviyeleri, dış/iç ayrımı, kanıt skoru.

---

## 2. Order Block (OB)

**Export:** `OrderBlockExport` (ARGENT Export Contract v1) — **yön başına en
yakın aktif OB anlık görüntüsü:**

| Alan | İçerik |
|---|---|
| `bull.state / top / bottom / fill / source_bar` | Boğa bloğu: durum, üst/alt sınır, doluluk, kaynak bar |
| `bear.state / top / bottom / fill / source_bar` | Ayı bloğu aynı |

**Replay/tarihçe tarafı:** `OrderBlockEngine._records` (geçmiş kayıtları;
dikkat: dolan zone'lar export'ta görünmez — ölçüm tuzağı, bkz.
ARASTIRMA_SONUCLARI §yapısal tuzaklar). **Brifing'e katkısı (G5/G6):** bant
(`top–bottom`), genişlik ATR, doluluk `fill`, kaynak bar yaşı, yön.

---

## 3. FVG + Engulfing (tek motor)

**Export:** `FvgEngulfingExport` — dört yan:

| Yan | Alanlar |
|---|---|
| `bull_fvg` / `bear_fvg` (`FvgSideExport`) | `state, top, bottom, quality, fill, event` |
| `bull_engulf` / `bear_engulf` (`EngulfingSideExport`) | `state, top, bottom, quality, retrace, event` |

**FvgState (11):** `NONE · CANDIDATE · ACTIVE · FIRST_TEST · PARTIAL_FILL ·
DEEP_TEST · FULL_FILL · REACTION · FAILED_REACTION · INVALID · SUPERSEDED`

**EngulfingState (7):** `NONE · ACTIVE · FIRST_TEST · PARTIAL_RETRACE ·
CONTINUATION_CONFIRMED · WEAKENED · INVALID · EXPIRED`

**Hassasiyet profili:** `Hassas / Dengeli / Seçici` (SensitivityProfile).
**Brifing'e katkısı:** boşluk dolum evresi (FVG pratikte tek-denemelik),
kalite, genişlik, yaş; ENG için geri-izleme oranı.

---

## 4. Volume Participation (VP)

| Enum | Üyeler |
|---|---|
| `ParticipationState` | `PENDING · VOLUME_UNAVAILABLE · NEUTRAL · UP_CANDIDATE · DOWN_CANDIDATE · UP_CONFIRMED · DOWN_CONFIRMED · CONFLICT` |
| `FinalParticipationState` | PEND/VOL_UNAV/NEUTRAL ek olarak `LOW · RISING · ABNORMAL_VOLUME · ABNORMAL_CAPITAL · ONE_BAR_SHOCK · UP/DOWN_CANDIDATE · UP/DOWN_CONFIRMED · UP/DOWN_PROTECTED` |
| `EffortResultClass` | `NEUTRAL · RISING_EFFORT_STRONG_RESULT · HIGH_EFFORT_STRONG_RESULT · HIGH_EFFORT_WEAK_RESULT · VERY_HIGH_EFFORT_WEAK_RESULT` |
| `LifecycleStage` | `NONE · CONFIRMED · PROTECTED · WEAKENING · CLOSED` |
| `AbsorptionSide/Stage` | emilim tarafı/aşaması |

**Brifing'e katkısı:** **uyarı katmanı** — yüksek çaba/zayıf sonuç (tükenme),
anormal hacim. Ölçüm notu: zone dokunuşunda yüksek hacim **zayıflatır**, MS
devamlılığında **güçlendirir** — tek hükümlü kullanılmaz.

---

## 5. Stabil (destek/direnç + trend)

### 5.1 Trend motoru (`stabil_trend_engine.py`)

| Enum | Üyeler |
|---|---|
| `WeeklyTrendState` | `PENDING · UP_STABLE · UP_WEAKENING · TRANSITION · NOT_UP · UP_PARABOLIC` |
| `DailyRawState` | `PENDING · ADVANCE · PULLBACK · BALANCE · NEUTRAL · TOO_DEEP · DISTRIBUTION · STRUCTURE_BROKEN · GAP_WATCH · PARABOLIC` |
| `DailyTrendState` | `PENDING · HEALTHY_ADVANCE · CONTROLLED_PULLBACK · BASE_BUILDING · PULLBACK_TOO_DEEP · DISTRIBUTION_RISK · STRUCTURE_BROKEN · NEUTRAL · BEARISH_BALANCE · GAP_WATCH · PARABOLIC · LOCAL_RECOVERY · LOCAL_OVERHEAT` |
| `GapState` | `NONE · RECLAIMED · WATCH · CONFIRMED` |
| `H4TrendState` | `PENDING · NO_RECOVERY · SELLING_WEAKENING · BUYERS_EMERGING · RECOVERY_CONFIRMED · RECOVERY_FAILED` |
| `H4Lifecycle` | `NO_EVENT · DISPLACEMENT_ACTIVE · BUYERS_EMERGING · RECOVERY_CONFIRMED · RECOVERY_FAILED` |
| `H4EvidenceStatus` | `NONE · FRESH · OLD · FAILED · ATTEMPT_FAILED` |

### 5.2 Destek yaşam döngüsü (`stabil_support_lifecycle.py`)

`SupportLifecycleEventType` (9): `SUPPORT_CONFIRMED · SUPPORT_TESTED ·
SUPPORT_HELD · SUPPORT_BREACHED · SUPPORT_FLOOR_BROKEN · SUPPORT_RECLAIMED ·
SUPPORT_LOST · SUPPORT_REBASED_HIGHER · SUPPORT_REBASED_LOWER`

**Direnç aynası** (`resistance.py`): `RESISTANCE_CONFIRMED · TESTED · HELD ·
BREACHED · CEILING_BROKEN · RETURNED_BELOW · LOST · REBASED_HIGHER ·
REBASED_LOWER` (aynı matematik, aynalanmış eksen).

### 5.3 Karakter rejimi (`candidate_regime.py`) — **"destek karakteri"**

`CandidateLineRegime`: `UNAVAILABLE · STEPPING_UP (dikey-yükselen) ·
STEPPING_DOWN (dikey-düşen) · BREACHED_FIXED_SUPPORT (yatay zemin kırıldı) ·
NEWLY_FLATTENED_AFTER_RISE (dikten yataya dönüş) · LONG_HORIZONTAL ·
HORIZONTAL_AFTER_DROP · HORIZONTAL_BASE`

> Bu enum, sözleşmedeki **karakter ayrımının** (yatay zemin kırılımı ≠ dikey
> basamak ≠ yataya dönme) native karşılığıdır.

### 5.4 Bar davranışı / ok sistemi (`signals.py` → `StabilBarBehavior`)

| Alan | İçerik |
|---|---|
| `support_level`, `close_price`, `pct_vs_support` | Seviye ve konum |
| `dist_atr`, `low_dist_atr`, `body_atr`, `close_pos` | Mesafe/gövde anatomisi (ATR) |
| `vol_ratio` | Hacim oranı |
| `fixed_support`, `regime`, `unchanged_days`, `touch_count` | Karakter + sabitlik + temas |
| `prev_breach_bars`, `prev_breach_depth_atr` | Önceki ihlal derinliği/yaşı |
| `reclaim_kind` | **`multi_bar_recovery` · `intrabar_sweep_reclaim` · None** (tek-mumlu `close_reclaim` sinyal değildir — yalnız `weak_reclaim` bayrağı olarak yaşar) |
| `weak_reclaim` | Zayıf geri-alım bayrağı (◇; soğuma 50 bar) |
| `momentum_kind` | Güçlü yukarı mum (boş ▲) |
| `vertical_support` / `vertical_attempt_kind` | Dikey rejim uyarısı (▼ yapı) |
| `rank_score` | Sıralama |

---

## 6. Formasyon (patterns/ — ayrı motor, domain gibi okunur)

**State makinesi (18)** (`patterns/constants.py`, Pine ile birebir):

```
FORMASYON_YOK · ADAY_OLUSUYOR · GEOMETRI_ADAYI · FORMASYON_TANIMLANDI ·
OLGUNLASIYOR · SIKISMA_GUCLENIYOR · KIRILIM_HAZIRLIGI · KIRILIM_DENEMESI ·
KIRILIM_ADAYI · KIRILIM_TEYITLI · RETEST_BEKLENIYOR · RETEST_EDILIYOR ·
RETEST_BASARILI · KIRILIM_TEYIT_ALAMADI · BASARISIZ_KIRILIM ·
FORMASYON_ZAYIFLADI · FORMASYON_GECERSIZ · FORMASYON_TAMAMLANDI
```

**Tipler (10):** `Yok · Yükselen Üçgen · Alçalan Üçgen · Simetrik Üçgen ·
Yükselen Kama · Alçalan Kama · Boğa Bayrağı · Ayı Bayrağı · Boğa Flaması ·
Ayı Flaması`

**Kimlik alanları** (32, `formation_schema.py` — FAZ3 envanteri): tip, aile,
yön, apex/pivot koordinatları, üst/alt eğim, doğum genişliği, `geometry_atr`,
`raw_quality`, pole bloğu; + olaylar (NEW_PATTERN … BREAK_CONFIRMED/OK/
TIMEOUT/FAILED/WEAK/INVALID) + `sonuc` (outcome_link: hedef/stop/nötr + MFE/MAE).

---

## 7. Yan katmanlar (brifingin beslendiği diğer kaynaklar)

| Kaynak | Çıktı |
|---|---|
| **Karne** (`karne.py`) | `hedef · stop · nötr · bekliyor · ölçülemedi` (ilk-dokunuş yarışı; 1,5/1,0 ATR, 10 bar) |
| **Ampirik referans** (`ampirik_referans.py`) | Koşullu beklenti satırları (kaynak tablo + n ile) |
| **Beklenti hükmü** (TAHMIN_KATMANI) | `devam · tek kanıt · kararsız · yön kanıtı yok` + lehte/aleyhte sayacı |
| **Blok/ölçüm CSV'leri** (arşiv) | `dz_*`, kırılım aday/teyit/yol CSV'leri (gölge defterin ham maddesi) |

---

## 8. Brifing eşleme (hangi çıktı hangi kapıya)

| Kapı | Bu sözlükten zorunlu alanlar |
|---|---|
| **G1 Stabil 1g** | `DailyTrendState` + `CandidateLineRegime` + `SupportLifecycleEventType` + `support_level/floor` + mesafe |
| **G2 Formasyon** | state makinesi + tip + `geometry_atr`/genişlik/daralma + üst/alt mesafe |
| **G3 MS** | taze `event_type×scope×direction` + `age` + PH/PL/WH/WL + `FALSE_BREAK/TRANSITION_FAIL` |
| **G4 TYR** | G1–G3'ün canlı tümü + zaman ölçümleri (daralma, yaş, mesafe) → hüküm |
| **G5 Bloklar** | OB `top/bottom/fill/source_bar` + FVG state/top/bottom/quality + genişlik ATR + konfluans |
| **Uyarı (opsiyonel)** | VP `EffortResultClass`/`ABNORMAL_*` + `StabilBarBehavior` dikey/◇ |

**Kırmızız çizgi:** Bu sözlükte olmayan hiçbir alan brifinge yazılmaz;
sözlükte olan hiçbir alan "kullanışsız" diye kırpılmaz.
