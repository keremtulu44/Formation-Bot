# P2.6 — AUDIT + MİMARİ ÖNERİ (implementasyon YOK)

**Tarih:** 2026-10-04 · **HEAD:** `623592f` (branch `arena/01a1020f-formation-bot`, PR #15)
**Kapsam:** yalnızca audit + architecture proposal. **Hiçbir dosya değiştirilmedi, commit üretilmedi.**
**Doğrulama:** `pytest -q` → **638 passed** (bu rapor yazılırken çalıştırıldı).

---

## 0) Önce çevre notu (dürüstlük)

Bu tur başında sandbox yeniden klonlandı: `.git` `a34a353`'te, çalışma ağacı ise
`623592f` içeriğindeydi. `git fetch origin` sonrası `origin/arena/01a1020f-formation-bot`
= `623592f` olduğu **doğrulandı** (tüm P2.0–P2.5 commit'leri uzakta duruyor), ardından
`git reset --hard 623592f` ile hizalandı. Diskdeki her dosyanın blob hash'i commit'teki
ile birebir karşılaştırıldı — **içerik kaybı yok.** Python paketleri de sıfırlanmıştı
(`pandas`/`pytest`/`requests` yoktu); `requirements.txt` pin'leriyle geri kuruldu
(`pandas 2.2.2 / numpy 1.26.4 / pytz 2024.1 / pytest 8.3.2`) ve suite 638 passed ile
doğrulandı. Aşağıdaki tüm ölçümler bu doğrulanmış ortamda yapıldı.

---

## 1) Mevcut Supabase durumu

### 1.1 Aktif olanlar

**Tek entegrasyon noktası: `supabase_store.py` (`SupabaseStore`).**
Ek bağımlılık **yok** — `supabase-py`/`postgrest` kullanılmıyor, saf `requests` ile
PostgREST REST API'ye gidiliyor. Bu iyi bir haber: P2.6 için yeni bir client bağımlılığı
gerekmez.

**Tablo: `public.bot_store`** (`supabase_schema.sql`, tek dosya, tek tablo):

```sql
create table if not exists public.bot_store (
    store_key  text primary key,
    payload    jsonb not null,
    updated_at timestamptz not null default now()
);
alter table public.bot_store enable row level security;
revoke all privileges on table public.bot_store from public, anon, authenticated;
grant select, insert, update on table public.bot_store to service_role;
```

Yani **key → JSONB** mağazası. İlişkisel hiçbir şey yok; RLS kapalı, yalnızca
`service_role` yazıyor.

**Gerçekten kullanılan anahtarlar (kodda ölçüldü):**

| Anahtar | Yazıcı | Amaç |
|---|---|---|
| `cache:1h:<SYM>`, `cache:1d:<SYM>` | `data.py:662,890` | OHLCV deque yedeği (48×2 ≈ 96 anahtar) |
| `state:son_tarama` | `state/persistence.py:son_tarama_kaydet` | son tarama listesi |
| `state:digest_pending` | `state/persistence.py:digest_tamponu_kaydet` | 18:45 digest tamponu |
| `state:karne_defteri` | `state/persistence.py:karne_defteri_kaydet` | **Karne yedeği** (yerel dosya birincil) |
| `state:telegram_caps` / `state:telegram_cooldowns` | `notifier.py:957,1016` | kota/soğuma |
| `state:telegram_son_alerts` | `notifier.py:1146` | tekrar-alarm mührü |
| `state:telegram_acil_kuyruk` | `notifier.py:1229` | engellenen acil kuyruk |
| `state:daily_fetch_attempts` | `data.py:873` | günlük fetch denemeleri |
| `state:heartbeat` | `main.py:719` | canlılık |
| `state:instances` | `main.py:588` | çoklu örnek tespiti (TTL 180 sn) |

Tümü `SUPABASE_STORE_PREFIX` (varsayılan `formation-bot:`) ile önekli; öneksiz eski
kayıtlar okunup bir sonraki yazımda taşınıyor (`get_many` içinde ikinci tur).

### 1.2 Altyapı var ama formation history için kullanılmayan

- **`formation_history` Supabase'te YOK.** `state/paths.py:FORMATION_HISTORY_ALT_DOSYA =
  "formation_history"` — yalnızca yerel dosya yolu üretiyor, Supabase anahtarı tanımlı değil.
  Yani botun en değerli verisi şu an **yalnızca Render'ın ephemeral diskinde**.
- `deploy_check.py` — bağımsız bir ortam doğrulama aracı (kendi kopyası `supabase_basliklari`,
  `store_onek`); production yolunda değil, deploy teşhisinde kullanılıyor. **Ayrı kod kopyası
  riski** var ama P2.6 kapsamı değil.
- `telegram_alert_flow.py`, `gun_simulasyonu.py` — Supabase'ten bağımsız/simülasyon araçları.

### 1.3 Mevcut davranışın ölçülmüş özellikleri (P2.6 için doğrudan bağlı)

| Özellik | Değer | Kaynak |
|---|---|---|
| HTTP timeout | 8 sn | `SupabaseStore.REQUEST_TIMEOUT_SEC` |
| Deneme sayısı | 2 (0.5 sn ara) | `_request` |
| Ağ/5xx backoff | 30 sn | `_request` |
| 429 backoff | 60 sn | `_request` |
| **4xx (429 hariç)** | **süreç boyunca kalıcı devre dışı** | `_disabled_reason` |
| Erişilemezlik sinyali | `get_many` → `None` (boş değil) | çağıran ayırt edebiliyor |
| **Yerel kuyruk** | **YOK** | tüm `upsert` doğrudan, fire-and-forget |
| Yazma amplifikasyonu koruması | **VAR (sadece OHLCV cache'de)** | `data.py:_veri_ozeti`/`_uzak_ozet` |

`data.py:657` içindeki yorum bu korumanın nedenini açıkça yazıyor: *"İçerik değişmediyse
UPSERT atlanır (tarama başına ~48 gereksiz istek + ~2 MB gidiyordu)."* — yani ekip bu sorunu
OHLCV cache'te çözmüş, **formation history'de henüz kararlığı yok.**

### 1.4 Kullanılmayan / ölü Supabase kodu

- `upsert_many` — **hiçbir production çağrısı yok** (yalnızca `upsert` kullanılıyor).
  Toplu yazma altyapısı hazır duruyor, kullanılmıyor. **P2.6 için doğrudan yeniden kullanılabilir.**
- `anahtar_turu` / `supabase_basliklari` dışa açık ama yalnızca `deploy_check.py` kendi
  kopyasını kullanıyor.
- `ornek_bildir` — sadece `main.py` heartbeat'ta.

**Sonuç:** Supabase altyapısı gerçekten aktif ve sağlıklı; formation history'yi taşıyacak
yer **hazır değil**. En verimli yol, `bot_store`'u genişletmek değil, **yeni tablolar** eklemek.

---

## 2) Mevcut Formation History persistence mimarisi

### 2.1 Dosya modeli

```
bot_data/formation_history/{STOCK}_{TF}.json      # 48 × 4 = 192 dosya
{
  "surum": ..., "stock": ..., "timeframe": ...,
  "kayitlar": {                                     # stable_id -> kayıt
    "<uuid4>": {
      "stable_id", "durum", "ilk_gorulme", "son_gorulme",
      "terminal_state", "terminal_zamani",
      "dogum":  { "bar_time", "bar_index", "alanlar": {32 IDENTITY alanı} },
      "olaylar":[ {stable_id,type,name,bar,time} ], # MAX_OLAY = 200
      "snapshotlar":[ {tur,bar_time,alanlar,stable_id,state,bar} ], # MAX_SNAPSHOT = 40
      "sonuc":  {durum,outcome,deneme,kaynak}       # P2.5 outcome linki
    }
  }
}
```

- Yazma **atomik**: `tmp + os.replace + fsync`, thread-lock korumalı (`fh.kaydet`).
- Okuma **bozulmaya dayanıklı**: bozuk JSON / yanlış tip / eksik alan → boş defter,
  bot durmaz (10/10 corruption varyantı audit edildi).
- **Tek yazım yolu:** `patterns/lifecycle.py:_history_kaydet` — defteri bir kez yükler,
  tüm mutasyonları uygular, **tarama başına en fazla bir kez** kaydeder.

### 2.2 Mevcut idempotency anahtarları (P2.6'nın en değerli mirası)

| Koleksiyon | Mevcut dedup anahtarı | Karşılık |
|---|---|---|
| Kayıt | `stable_id` | PK |
| Doğum | `stable_id` (var olanı ezmaz, sadece `son_gorulme`) | PK |
| Olay | `stable_id \| type \| name \| bar \| time` | UNIQUE |
| Snapshot | `(tur, bar_time)` | UNIQUE |
| Terminal | `tur == "terminal"` bir kez | UNIQUE (kısmi) |
| Outcome | tek `sonuc` alanı (tek sözlük) | 1:1 |

**Bu anahtarlar birebir DB unique constraint'ine map edilebilir.** Bu, P2.6'nın
en kritik bulgusudur: idempotency zaten tasarlanmış, sadece uygulanmadı.

### 2.3 Ölçülen veri hacmi (gerçek)

| Ölçüm | Değer |
|---|---|
| Tek tam-yaşam-döngüsü kaydı | **13.3 KB** (indent'siz JSON) |
| Doğum alanı | 32 |
| Snapshot dağılımı | geometri 7×18, kirilim 2×20, retest 2×18, terminal 1×20 = 12 |
| Olay | 9 |
| Dolu defter (`MAX_KAYIT=30`) | **≈ 390 KB** |
| 192 defter toplamı | **≈ 73 MB** |
| Tahmin (365 gün, retention yok) | **≈ 445 MB** |

### 2.4 Ölçülen yazım amplifikasyonu (P2.6 için KRİTİK)

Production `main.py:1897` her taramada **`tam_yeniden=True`** kullanıyor (pencere sıfırdan
deterministik oynatma). Ölçüm:

| Senaryo | 5 tekrar tarama → disk yazımı |
|---|---|
| Terminal'e ulaşmış formation | **5** |
| Hâlâ açık formation | **0** |

**Neden:** `terminal_ekle` koşulsuz olarak `terminal_zamani`/`son_gorulme`'yi `_simdi()` ile
tazeliyor ve `True` dönüyor → `_history_kaydet` `degisti=True` görüp `fh.kaydet` çağırıyor.
Yani **terminal her kapanan formasyon, her tarama döngüsünde defteri diske yeniden yazıyor.**

Bugün bu sadece yerel disk maliyeti (ucuz). Ama P2.6'da bu davranış 1:1 Supabase'e
yansırsa: **her terminal formation için her döngüde tüm defter JSON'ının yeniden gönderilmesi**
demek. Bu, P2.6'yı şekillendiren tek en önemli ölçümdür.

### 2.5 Retention devrede DEĞİL (ölçülen)

`MAX_KAYIT = 30` tanımlı ve birim testli, ama `_retention_temizle` **yalnızca `temizle()`'den
çağrılıyor ve `temizle()`'nin production çağrısı yok.** `_history_kaydet` ve `kaydet`
retention uygulamıyor. → **Yerel history (stock,tf) başına sınırsız büyüyor.**

Bu, "retention değerini kodlama" kararını doğrudan etkiliyor: değer seçmek yetmez,
**uygulama noktası da seçilmeli.**

### 2.6 Kim okuyor? (P2.6'nın kırılma riski)

| Okuyucu | Ne yapıyor |
|---|---|
| `patterns/lifecycle.py:_match_registry` → `fh.eslestir` | **restart sonrası stable_id re-attach.** Tüm AÇIK kayıtları + doğum bar_time/bar_index + 32 IDENTITY alanını ister |
| `state/outcome_link.py:formasyon_sonucu` | `fh.yukle` + `kayit_getir` — outcome için history kaydını okur |
| `state/outcome_link.py:bagla` | `fh.sonuc_bagla` + `fh.kaydet` — **yazıyor** |
| `main.py:_formation_history_baslangic_kontrolu` | `fh.saglik_raporu()` — sadece startup logu |

**En kritik bağımlılık `eslestir`.** Eğer history Supabase'e taşınırsa ve yerel defter
boş kalırsa, restart sonrası `eslestir` hiçbir kayıt bulamaz → **yeni stable_id üretilir**
→ P2.0–P2.5'in tüm sahiplik garantileri (7 aşama tek SID) sessizce bozulur. Bu, P2.6'nın
bir numaralı regresyon riskidir.

---

## 3) Önerilen Supabase schema

### 3.1 Neden `bot_store`'a JSONB olarak koymak yanlış

| Sorun | Sonuç |
|---|---|
| 192 satır × 390 KB | ~73 MB, satır başına tek JSONB |
| Her terminal formation her döngüde | tüm defter yeniden gönderilir |
| "Tüm `outcome=stop` formation'lar" | **sorgulanamaz** — blob içinde |
| "Quality ≥ 80 olanları sırala" | **sorgulanamaz** |
| Validation/backtest analizi | **imkânsız** — SQL yerine tüm blob'u indirip parse etmek gerekir |

Kullanıcının 8 analiz hedefinin (detector doğruluğu, lifecycle güvenilirliği, quality
anlamlılığı, sıralama-sonuç ilişkisi, bileşen etkisi, ağırlık doğrulaması,
özellik-sonuç ilişkisi, kontrollü backtest) **hiçbiri** JSONB blob üzerinden verimli
yapılamaz.

### 3.2 Öneri: normalize edilmiş, `stable_id` merkezli 4 tablo

```sql
-- ============ 1) FORMATIONS (kimlik + yaşam döngüsü durumu) ============
create table if not exists public.f2_formations (
    stable_id      text primary key,               -- P2.0–P2.5'in kalıcı kimliği
    stock          text        not null,
    timeframe      text        not null,
    durum          text        not null default 'acik',   -- acik | kirilim | retest | terminal
    terminal_state text,                           -- FORMASYON_TAMAMLANDI | BASARISIZ_KIRILIM | ...
    ilk_gorulme    timestamptz not null default now(),
    son_gorulme    timestamptz not null default now(),
    dogum_bar_time timestamptz,                    -- MUTLAK bar zamanı (alignment kaynağı)
    dogum_bar_index integer,
    terminal_zamani timestamptz,
    dogum_alanlar  jsonb       not null default '{}',  -- 32 IDENTITY alanı (değişmez)
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);
create index if not exists f2_formations_kimlik_idx
    on public.f2_formations (stock, timeframe, durum);
create index if not exists f2_formations_terminal_idx
    on public.f2_formations (terminal_state) where terminal_state is not null;
-- dogum_alanlar üzerinde bileşen araması (GIN) — analiz için, P2.6'da ZORUNLU DEĞİL
-- create index ... using gin (dogum_alanlar);

-- ============ 2) SNAPSHOTS (geometri / kirilim / retest / terminal) ============
create table if not exists public.f2_snapshots (
    id           bigserial primary key,
    stable_id    text        not null references public.f2_formations(stable_id) on delete cascade,
    tur          text        not null,             -- geometri | kirilim | retest | terminal
    bar_time     timestamptz not null,
    bar_index    integer,
    state        text,                             -- KIRILIM_DENEMESI | KIRILIM_TEYITLI | ...
    alanlar      jsonb       not null default '{}',
    created_at   timestamptz not null default now(),
    constraint f2_snapshots_tek unique (stable_id, tur, bar_time)   -- snapshot_ekle dedup'ı
);
create index if not exists f2_snapshots_tur_idx on public.f2_snapshots (tur, bar_time);

-- ============ 3) EVENTS (yaşam döngüsü olayları) ============
create table if not exists public.f2_events (
    id           bigserial primary key,
    stable_id    text        not null references public.f2_formations(stable_id) on delete cascade,
    type         text        not null,
    name         text        not null,
    bar          integer,
    bar_time     timestamptz,
    payload      jsonb       not null default '{}',
    created_at   timestamptz not null default now(),
    constraint f2_events_tek unique (stable_id, type, name, bar, bar_time)  -- _olay_anahtar dedup'ı
);
create index if not exists f2_events_sid_idx on public.f2_events (stable_id, bar);

-- ============ 4) OUTCOME LINKAGE (P2.5 — Karne'den BAĞIMSIZ) ============
create table if not exists public.f2_outcome_links (
    stable_id    text primary key references public.f2_formations(stable_id) on delete cascade,
    durum        text        not null,             -- hedef | stop | nötr | bekliyor | ölçülemedi
    deneme       integer     not null default 0,
    kaynak       timestamptz,                      -- birincil kırılımın bar_time'ı
    outcome      jsonb       not null default '{}',-- sinyal_sonucu çıktısı (MFE/MAE/atr/horizon)
    baglandi     timestamptz not null default now()
);
```

**RLS politikası mevcut `bot_store` ile aynı tutulmalı** (istemci rolleri yok, yalnız
`service_role`).

### 3.3 Neden bu model (ve alternatifler)

| Seçenek | Artı | Eksi | Karar |
|---|---|---|---|
| **A. `bot_store`'a `state:formation_history:<stock>_<tf>`** | mevcut kodu hiç değiştirmez, en az iş | sorgulanamaz, 390 KB satır, terminal her döngüde yeniden yazar, analiz imkânsız | ❌ **Reddedildi** |
| **B. 4 normalize tablo (öneri)** | `stable_id` gerçek PK, her alan sorgulanabilir, dedup DB seviyesinde garanti, satır bazlı yazım (blob değil), bileşen analizi mümkün | yeni migration + repository katmanı gerekir | ✅ **Önerilen** |
| **C. Tek `f2_formations` + tüm snapshot'ları JSONB dizide** | tablo sayısı az | snapshot sorgulanamaz, "en son geometri" gibi basit sorgu bile zor | ❌ Reddedildi |
| **D. Karne'yi de aynı şemaya katmak** | tek DB | kullanıcı bunu açıkça istemedi; outcome motoru taşınmamalı | ❌ Reddedildi |

**B seçilme nedeni, tek cümle:** kullanıcının 8 analiz hedefinin hepsi `stable_id` üzerinden
*ilişkisel sorgu* gerektiriyor; JSONB blob bu sorguları imkânsız kılıyor.

### 3.4 Primary key / identity

- **`stable_id` formation'ın kalıcı identity'si olarak uygun mu? EVET.** Zaten
  `uuid4`, tüm 7 aşamada tek değer (audit: `len(unique(sid)) == 1`), terminal sonrası
  yeni formation'a asla taşınmıyor, restart'ta `eslestir` ile re-attach ediliyor.
  Ek olarak `(stock, timeframe, stable_id)` üzerinden doğal bir kapsam sınırı var.
- **Snapshot identity:** `(stable_id, tur, bar_time)` — mevcut `snapshot_ekle` dedup'ı
  birebir aynı. Ek olarak `bar_index` taşınmalı çünkü `eslestir` pencere kaymasını
  bar indeksinden hesaplıyor.
- **Event identity:** `(stable_id, type, name, bar, bar_time)` — mevcut `_olay_anahtar`
  birebir aynı. **Dikkat:** mevcut anahtar ham `pandas.Timestamp`'i `json_guvenli` ile
  indirgiyor; DB'de `timestamptz` kolonu kullanılmalı ki string/timestamp karışmasın.
- **Outcome:** `(stable_id)` 1:1 — mevcut `sonuc` tek sözlük zaten 1:1.

### 3.5 Idempotency — mevcut davranıştan birebir garanti

| Koleksiyon | DB mekanizması | Mevcut karşılığı |
|---|---|---|
| Formation | `stable_id` PK + `ON CONFLICT (stable_id) DO NOTHING` | `dogum_ekle` idempotentliği |
| Snapshot | `UNIQUE (stable_id, tur, bar_time)` + `ON CONFLICT DO NOTHING` | `snapshot_ekle` dedup |
| Event | `UNIQUE (stable_id, type, name, bar, bar_time)` + `ON CONFLICT DO NOTHING` | `olay_ekle` dedup |
| Terminal | `UNIQUE (stable_id, tur, bar_time)`'nin `tur='terminal'` hâli | terminal bir kez yazılır |
| Outcome | `stable_id` PK + `DO UPDATE ... WHERE değiştiyse` | `bagla` yalnızca değiştiğinde yazar |

**`ON CONFLICT DO NOTHING` seçilme nedeni:** mevcut sistem "son yazan kazanır" değil,
"**ilk yazan kazanır**" semantiği kullanıyor (doğum snapshot'ı üzerine yazılmıyor,
`son_gorulme` hariç). `DO UPDATE` kullanmak bu semantiği sessizce değiştirir.

**Önemli ayrıntı:** `dogum_ekle` var olan kayıtta `son_gorulme`'yi tazeliyor. Bu DB'de
ayrı bir `UPDATE ... SET son_gorulme = now()` olmalı; `ON CONFLICT DO NOTHING` bunu yapmaz.
Yani **iki ayrı ifade** gerekir: (1) snapshot/event için `DO NOTHING`, (2) `son_gorulme`
için ayrı, koşullu `UPDATE`.

---

## 4) Önerilen write / retry / idempotency modeli

### 4.1 Temel karar: "local-first, remote-mirror, diff-gated"

Mevcut mimariyi bozmadan, mevcut deseni genişlet:

```
_history_kaydet (TEK yazım yolu — DEĞİŞMEZ)
   ├─ fh.yukle → mutasyonlar → fh.kaydet      # BİRİNCİL, değişmez
   └─ mirror_kuyruga_ekle(defter)              # YENİ: sadece fark varsa
```

**Kritik kural: Supabase yazımı `fh.kaydet`'in başarısına ASLA bağlı olmamalı.**
Mevcut `_history_kaydet` zaten her hatta sessizce dönüyor (bot durmuyor) — bu korunmalı.

### 4.2 Yazım tetikleyicisi: içerik parmak izi (mevcut deseni yeniden kullan)

`data.py`'deki kanıtlanmış desen (`_veri_ozeti` / `_uzak_ozet`) formation history'ye
uyarlanmalı:

```python
def _defter_ozeti(defter):
    """Değeri değişmeyen alanları HARİÇ tutan parmak izi.

    son_gorulme / terminal_zamani / guncellendi HER taramada değişir; bunları
    dahil etmek her döngüde gereksiz UPSERT üretir (ölçüldü: terminal
    formation 5 taramada 5 yazım).
    """
    return (
        len(defter.get("kayitlar", {})),
        # her kayıt için: stable_id, durum, snapshot sayısı, olay sayısı,
        # son snapshot'in (tur,bar_time), sonuc durumu
    )
```

**Bu tek başına, ölçülen 5/5 yazım amplifikasyonunu 5/0'a düşürür.** Terminal kaydın
içeriği zaten sabitken yalnızca zaman damgaları değişiyorsa neden yeniden gönderilsin?

> **Not:** bu bir *optimizasyondur*, mevcut davranışı değiştirir (zamandan bağımsız olarak
> aynı içerik artık yeniden yazılmaz). Kullanıcı "gereksiz refactor yapma" dediği için
> bunu **ayrı, isteğe bağlıı bir adım** olarak öneriyorum; zorunlu değil. Ama yapılmazsa
> Supabase'e gereksiz yazım gider.

### 4.3 Per-event mi, batch mi?

| Seçenek | Değerlendirme |
|---|---|
| Her event'te anında network isteği | ❌ 192 (stock,tf) × her anlamlı geçiş = tarama başına yüzlerce istek. `data.py` yorumu zaten "~48 gereksiz istek" için uyarıyor |
| **Tarama sonu kuyruk + akıllı flush** | ✅ Önerilen |
| Sabit aralık (cron) flush | ⚠️ basit ama restart penceresinde veri kaybı |

**Öneri (üç katman):**

1. **Bellek kuyruğu** (`collections.deque` + lock): `_history_kaydet` yalnızca *farkı*
   kuyruğa atar. Tam defter değil — **satır bazlı fark** (yeni kayıt, yeni snapshot,
   yeni event, durum değişikliği). Böylece 390 KB defter yerine ~1–13 KB gider.
2. **Flush tetikleyicileri (ilk eşleşmede):**
   - kuyruk boyutu ≥ `F2_FLUSH_MAX_KAYIT` (örn. 50 satır)
   - son flush'tan beri ≥ `F2_FLUSH_MAX_SN` (örn. 60 sn) geçti VE kuyruk boş değil
   - tarama döngüsü bitti (48×4 tamamlandı)
   - **graceful shutdown** (SIGTERM handler)
3. **Retry + kalıcı yedek kuyruk:**
   - Yazım başarısızsa satırları **bellekte** tut, üstel backoff (30 sn → 60 sn → 120 sn, üst sınır 10 dk)
   - Aynı anda diske `f2_kuyruk.json` olarak da yaz (Render'da kaybolur ama **10 dakikalık**
     bir kesintiyi aşmak için yeterli; ayrıca restartları karşılar)
   - `get_many` `None` döndüğünde (erişilemez) satırları **atma**, biriktir

**Mevcut `SupabaseStore._request` backoff'ü yeterli mi?** Kısmen. 8 sn timeout + 2 deneme
+ 30/60 sn backoff makul, ama **kuyruk yok.** `upsert_many` hazır — kullanılmalı.

### 4.4 "Supabase 10 dakika erişilemezse ne olur?"

**Dürüst cevap — üç ayrı soru:**

**(a) Bot çalışmaya devam eder mi? EVET, kesin.** Yazım yolu `_history_kaydet` ve zaten
her hatta sessizce dönüyor; `SupabaseStore._request` de 4xx'te süreci devre dışı bırakıp
yerel moda düşüyor. Hiçbir koşulda tarama/detection/lifecycle durmaz.

**(b) O 10 dakikadaki history kaybolur mu? HAYIR — yerel JSON yazılmaya devam eder.**
`fh.kaydet` Supabase'den bağımsız. Veri `bot_data/formation_history/` altında.

**(c) O 10 dakika Supabase'e yazılmaz. Sonra ne olur?**
- Bellek kuyruğu + disk kuyruğu varsa: **recovery sonrası flush edilir, kayıp yok.**
- Yoksa (bugünkü durum): **o 10 dakikanın formation history'si kalıcı olarak kaybolur.**

**Sınırları açıkça belirliyorum:**
- Render Free'da `DATA_DIR=/tmp/formation-bot-data` **ephemeral**. Restart/redeploy'da
  **silinir.** Yani disk kuyruğu yalnızca *aynı süreç ömrü* boyunca ve *restartı değil,
  yeniden dağıtımı* karşılamaz.
- **"Supabase yokken sonsuza kadar history garanti edilir" — BU GARANTİYİ VEREMEM.**
  Supabase kapalıyken üretilen ve flush edilemeyen veri, süreç ölürse kaybolur.
- En iyi durum: kuyruk + backoff ile **dakikalarca/saatlerce** (bellek + disk) tolere edilir;
  kalıcı garanti yalnızca **flush edildikten sonra** başlar.

---

## 5) Restart / redeploy / fallback davranışı

### 5.1 Senaryo A: local yok, Supabase var (redeploy sonrası — ANA senaryo)

**Bugünkü davranış:** `eslestir` boş defter görür → yeni `stable_id` üretir → sahiplik zinciri kırılır.

**Öneri (mevcut recovery mekanizmasını BOZMADAN):**

```
_formation_history_baslangic_kontrolu()          # mevcut, sağlık raporu — KALIR
   └─ YENİ: f2_hydrate()  ── sadece yerel defter BOŞSA ve Supabase erişilebilirse
         1. f2_formations'dan (stock,tf) için AÇIK (durum != terminal) kayıtları çek
         2. dogum_alanlar + dogum_bar_time + dogum_bar_index ile yerel defteri KUR
         3. Terminal kayıtları da çek (sonuc bağlı olanlar öncelikli)
         4. Hydrate başarısızsa SESSİZCE geç — Faz 1 anchor yolu devralır
```

**Kritik güvenlik kuralı:** hydrate **yalnızca yerel defter boşken** çalışmalı.
Yerel veri varken Supabase'den gelen veri üzerine yazılmamalı — mevcut
`son_tarama_yukle`'ün "en yenisi kazanır" kuralı burada **yanlış** olurdu, çünkü
`eslestir` için *eksiksiz açık kayıt kümesi* gerekir, yarım veri yanlış eşleşme üretir.

**Ek güvenlik:** hydrate sonrası `eslestir`'ın eşikleri (`identity_compatible`,
`continuity_score >= 60`) **aynen devrede** — yani Supabase'den gelen bir kayıt bile
doğum barı pencerede değilse eşleşmez. Bu, yanlış birleşme riskini zaten minimize ediyor.

### 5.2 Senaryo B: local var, Supabase yok

**Öneri: hiçbir şey yapma.** Yerel defter zaten doğru ve birincil. Supabase yazımı
kuyrukta birikir, erişilebilir olunca flush edilir. `eslestir` yerel defterden okumaya
devam eder — **davranış bugünküyle birebir aynı.**

Bu, "local-first" modelinin en büyük avantajı: Supabase tamamen kapalıyken bot
*bugünkü davranışının aynısını" sergiler.

### 5.3 Senaryo C: ikisi de var ama farklı (çatışma)

| Durum | Öneri |
|---|---|
| Yerel daha yeni | yerel kazanır, fark kuyruğa atılır → Supabase güncellenir |
| Supabase daha yeni | **yerel korunur**, Supabase'deki ek kayıtlar hydrate edilir (birleşim) |
| Aynı `stable_id`, farklı içerik | yerel kazanır (doğum snapshot'ı üzerine yazılmaz kuralı) |

**Birleşim (merge) yerine "yerel kazanır + eksikleri ekle" seçilme nedeni:** mevcut
`KarneDefteri.birlestir` de aynı semantiği kullanıyor (`+N kayıt` ekliyor, üzerine yazmıyor).
Tutarlılık için aynı desen.

### 5.4 Mevcut recovery mekanizmasına dokunulmayacaklar

- `fh.yukle` bozulma dayanıklılığı (10/10 varyant) — **değişmez**
- `fh.kaydet` atomik yazım — **değişmez**
- Faz 1 anchor (`state/formation_identity.py`) — **değişmez**, yalnızca *fallback* olarak kalır
- `eslestir` eşikleri ve kuralları — **değişmez**
- `_history_kaydet` tek yazım yolu — **değişmez** (sadece yanına mirror çağrısı eklenir)

---

## 6) Retention seçenekleri

### 6.1 Önce ölçüm (kullanıcının istediği gibi — değer kodlanmıyor)

| Metrik | Ölçülen/Tahmini değer |
|---|---|
| Tek kayıt | 13.3 KB |
| (stock,tf) defteri | 192 |
| `MAX_KAYIT=30` dolu hâlde | 73 MB |
| Retention **uygulanmıyor** | sınırsız büyüme |
| 365 gün (retention yok) | ≈ 445 MB |

**Supabase Free:** 500 MB veritabanı. 445 MB **neredeyse limit.** Yani retention
*isteğe bağlı değil, zorunlu* — ama değerini ölçmeden kodlamak yanlış olur.

### 6.2 Seçenekler

| Seçenek | Artı | Eksi | Değerlendirme |
|---|---|---|---|
| **DB'den sil** | basit, alan kazanılır | gelecekteki validation verisi **kalıcı olarak kaybolur** | ⚠️ yalnızca arşivden emin olduktan sonra |
| **Arşiv tablosu** (`f2_formations_archive`) | veri korunur, ana tablo hızlı, sorgu ayrılabilir | 2× alan (ama Free 500 MB'ye sığar) | ✅ **Önerilen** |
| **Cold storage** (S3/R2) | en ucuz, sınırsız | ek entegrasyon, erişim karmaşık | 🔜 P2.7+ |
| **Son N formation** (mevcut `MAX_KAYIT`) | kod hazır, testli | (stock,tf) başına — analiz için *global* kesme daha işe yarar | ⚠️ yanlış kapsam |
| **Son N gün** | analiz açısından anlamlı (zaman penceresi) | `sonuc` bağlı olmayan kayıtları kaybedebilir | ⚠️ dikkatli |

### 6.3 Önerilen model (hibrit, üç katman)

```
1) ANA TABLO   : son 90 gün (ya da son N formation) — hızlı sorgu
2) ARŞİV TABLO : 90 günden eski + sonucu bağlı olanlar — ASLA silinmez
3) COLD (P2.7+): 1 yıldan eski — S3/R2
```

**Güvenlik kuralları (mevcut `_silme_onceligi` ile uyumlu):**

| Öncelik | Kural |
|---|---|
| 0 | `sonuc` bağlı kayıt → **ASLA silinmez, ASLA arşivden çıkarılmaz** (P2.5'in tek değerli çıktısı) |
| 1 | Terminal + sonuçsuz → arşivlenebilir |
| 2 | Açık (yaşayan) → **asla silinmez**; yalnızca zorunluysa |

**"Aktif formation'ı silmek" ile "eski formation'ı silmek" ayrımı:**
- **Aktif (açık) kayıt asla silinmemeli.** `eslestir` bunlara bakar; silinirse restart
  sonrası yeni SID üretilir. Bu bir *doğruluk* sorunu, depolama sorunu değil.
- **Eski terminal kayıt** analiz değeri taşıyorsa arşivlenmeli, silinmemeli.
- Silme yalnızca: *sonucusuz + terminal + çok eski + zaten arşivlenmiş* kayıtlar için.

**Kritik uyarı:** retention değeri henüz netleşmedi (500 belirtilmedi). Bu yüzden
**P2.6'da retention'ı KODLAMAYI önermiyorum** — yalnızca arşiv tablosunu ve
güvenlik kurallarını eklemeyi öneriyorum. Böylece değer kararı verildiğinde tek bir
`WHERE` ifadesiyle uygulanır.

### 6.4 Mevcut `MAX_KAYIT=30`'ün kaderi

Şu anda devrede değil. İki seçenek:
- **(a) P2.6'da devreye sok** — `_history_kaydet` sonunda `_retention_temizle` çağrılır.
  Artı: yerel disk kontrollü. Eksi: *davranış değişikliği* (kayıt silinmeye başlar) →
  mevcut testlere ve kullanıcı beklentisine etkisi var.
- **(b) Olduğu gibi bırak** — P2.6 yalnızca uzak taşımayı yapar.

**Öneri: (b), ama raporla.** Retention'ı devreye sokmak *ürün davranışını değiştirir*
(kayıt silinir) ve bu "gereksiz refactor/değişiklik" sınırına giriyor. P2.6'yı
**taşıma** ile sınırlamak daha güvenli. (a) ayrı bir karar olarak ele alınmalı.

---

## 7) Read repository önerisi

### 7.1 Soyutlama

```
state/formation_repository.py        # arayüz + yerel/Supabase uygulaması
```

**Tek arayüz, iki uygulama:**

| Metod | Yerel kaynak | Supabase karşılığı |
|---|---|---|
| `get_formation(stable_id)` | `kayit_getir` | `f2_formations` + ilgili satırlar |
| `get_formations(stock, timeframe, durum=None)` | defter + filtre | `WHERE stock=$1 AND timeframe=$2` |
| `get_timeline(stable_id)` | snapshot'lar + olaylar | `f2_snapshots` ⋈ `f2_events ORDER BY bar_time` |
| `get_recent_formations(stock=None, tf=None, gun=None, limit=)` | defterler | `ORDER BY ilk_gorulme DESC` |
| `get_terminal_formations(terminal_state=None)` | defterler | `WHERE terminal_state IS NOT NULL` |
| `get_open_formations(stock, tf)` | `eslestir`'ın okuduğu küme | `WHERE durum != 'terminal'` |
| `get_outcome(stable_id)` | `rec["sonuc"]` | `f2_outcome_links` |

### 7.2 Neden soyutlama şart

`eslestir` bugün `fh.yukle`'ye doğrudan bağımlı. P2.6'da Supabase eklenince bu bağımlılık
ikiye ayrılmalı. Ama **`eslestir`'ın matematik/semantiği değişmemeli** — yalnızca
*veri kaynağı* değişmeli.

**Öneri:** repository arayüzünü **P2.6'da ekle ama P2.7'de doldur.** P2.6 yalnızca
*yazımı* taşısın; okuma P2.7 (Telegram/UI) ile gelsin. Böylece P2.6 minimal kalır.

### 7.3 Telegram UI bu aşamada YAPILMAYACAK

Kullanıcı bunu açıkça istedi. `get_*` metodları P2.6'da **tanımlanabilir ama çağrılmaz**;
Telegram komutları (`/formasyonlar`, `/panel`, `/canli`, `/karne`) olduğu gibi çalışır.

---

## 8) Karne ayrımının değerlendirmesi

### 8.1 Teknik açıdan sakınca var mı? **HAYIR — aksine doğru.**

| Konu | Değerlendirme |
|---|---|
| Outcome motoru taşınmamalı | ✅ Karne `sinyal_sonucu` / `karne_hesapla` **byte-identical** (audit kanıtlı). Taşımak = matematik riski |
| Karne ayrı hesaplanabilir | ✅ `KarneDefteri` disk-backed, `kayitlar()` dict form; istendiğinde yeniden hesaplanabiliyor |
| Yeni outcome datastore yasak | ✅ `f2_outcome_links` **yeni datastore değil** — P2.5'in `rec["sonuc"]` alanının taşınması. Karne defteri değişmiyor |
| Tek bağımsızlık noktası | `stable_id` |

### 8.2 Linkage nasıl korunur

```
Karne defteri (yerel + opsiyonel uzak yedek)     f2_outcome_links
  kirilim kaydı {stable_id, ...}  ────────┐       stable_id (PK)
  olay kaydı    {stable_id, ...}  ────────┼──────  durum, deneme, kaynak, outcome
  formasyon     {stable_id, ...}  ────────┘
```

**Kural: Karne kaydındaki `stable_id` ile `f2_outcome_links.stable_id` aynı olmalı.**
Bu, P2.5'te zaten çalışan tek bağ. P2.6 bu bağı **taşır, değiştirmez.**

### 8.3 Tek risk ve çözümü

**Risk:** `f2_outcome_links.outcome` alanı `sinyal_sonucu` çıktısını (MFE/MAE/atr/horizon)
kopyalarsa, iki yerde aynı veri olur ve senkron bozulursa hangisi doğru?

**Çözüm:** `f2_outcome_links` **yalnızca linkage + son durumu** tutsun:
`{stable_id, durum, deneme, kaynak, baglandi}`. Ham `outcome` (MFE/MAE/atr) Karne'de
kalsın; gerektiğinde `saglayici` ile yeniden hesaplansın. Böylece:
- Tek doğruluk kaynağı Korunur (Karne)
- `f2_outcome_links` yalnızca "bu formation'a hangi sonuç bağlandı" der
- Validation analizi için yine de yeterli: `durum` + `kaynak` bar_time + Karne'den
  yeniden hesaplanabilir MFE/MAE

**Alternatif (daha az tercih edilir):** `outcome` jsonb'sini de tutmak. Artı: analiz
tek sorgu. Eksi: senkron riski, "Karne matematiği taşındı" izlenimi. **Öneri: tutma.**

---

## 9) Gelecekteki validation/backtest için kritik alanlar

### 9.1 "Quality=80 tek başına yeterli değil" varsayımı — DEĞERLENDİRME

**Varsayım DOĞRU ve halihazırda karşılanmış durumda.** P2.0 kontratı zaten
`raw_quality`'yi *bileşenlerine* ayırmış:

| Sınıf | Alan | Ne sağlar |
|---|---|---|
| IDENTITY (32) | doğumdaki sabit geometri + pole + family + pattern_type + `raw_quality` | "hangi formation" |
| STATE (18) | zaman içinde değişen kalite bileşenleri (`geometry_score`, `upper_slope`, `pole_quality`, `contraction`, `upper_touches` …) | "nasıl evrimleşti" |
| BREAKOUT (20) | `freeze_pattern_quality` anında dondurulan kırılım gücü + teyit | "kırılım ne kadar güçlüydü" |
| TRANSIENT (16) | ihlal önbellekleri, `selection_score` — bilerek persist edilmez | gereksiz |

**Audit ölçümü:** IDENTITY 32/32, STATE 18/18, BREAKOUT 20/20 persist ediliyor;
TRANSIENT sızıntısı 0; şema dışı alan 0. Yani iki farklı `quality=80` formation'ın
bileşenleri **zaten ayrıştırılmış olarak history'de.**

**Kritik nokta:** bu ayrım `bot_store`'a JSONB olarak konursa **kaybolur** (blob içinde
sorgulanamaz), normalize tablolara konursa **korunur**. Bu, şema önerisinin (B) en güçlü
gerekçesi.

### 9.2 Her analiz hedefi için gereken alanlar

| Analiz hedefi | Gereken alanlar | Nerede |
|---|---|---|
| **1. Detector doğruluğu** | `dogum_alanlar` (32 IDENTITY) + `dogum_bar_time` + `bar_index` + `terminal_state` | `f2_formations.dogum_alanlar` |
| **2. Lifecycle güvenilirliği** | `durum`, `terminal_state`, olay dizisi (`type`,`name`,`bar`) | `f2_events` |
| **3. Quality anlamlı mı** | `raw_quality` (doğum) + `geometry_score` (geometri snapshot) | `dogum_alanlar` + `f2_snapshots` |
| **4. Sıralama–sonuç ilişkisi** | `raw_quality` ⋈ `f2_outcome_links.durum` | JOIN |
| **5. Bileşen etkisi** | STATE 18 alan (slope, contraction, touches, pole_quality) ⋈ outcome | `f2_snapshots.alanlar` ⋈ `f2_outcome_links` |
| **6. Ağırlık doğrulama** | aynı + `break_*_score` (BREAKOUT 20) | `f2_snapshots.alanlar` |
| **7. Özellik–sonuç ilişkisi** | `family`, `classic_dir`, `pattern_type`, `geometry_atr` | `dogum_alanlar` |
| **8. Kontrollü backtest** | `dogum_bar_time` + `kaynak` (outcome bar) + `stable_id` | `f2_formations` ⋈ `f2_outcome_links` |

### 9.3 Mutlaka korunması gereken alanlar (kaybetme listesi)

**Zorunlu (bunlar olmanal analiz imkânsız):**
1. `dogum_alanlar` içindeki **32 IDENTITY alanı** — özellikle `family`, `classic_dir`,
   `pattern_type`, `raw_quality`, `start_bar`, `apex_bar`, pivot koordinatları
2. `dogum_bar_time` (MUTLAK) — pencere kaymasından bağımsız hizalama
3. `terminal_state` — hangi terminal anlamıyla bitti
4. `f2_outcome_links.durum` + `kaynak` — sonuç ve onun barı
5. Snapshot'lardaki **STATE 18 + BREAKOUT 20** alanlar — quality'nin bileşen evrimi

**Bilerek korunmayacak (transient, analiz değeri yok):**
- 16 TRANSIENT alan (ihlal önbellekleri, `selection_score`, `valid`, `identity`)
- `ArgentEngine.invalid_reason` (kontrat dışı; audit raporunda MINOR FOLLOW-UP olarak notlu)
- Motor konfigürasyon parametreleri (`min_quality`, `retest_window`, `horizon` …)

**Ek öneri (P2.6'da ZORUNLU DEĞİL, P2.7 için not):** `alanlar` jsonb'si üzerinde GIN
indeks eklenebilir; böylece `"raw_quality >= 80"` gibi sorgular hızlanır. Ama 192×30 =
5760 satır için gerekmez — önce ölç, sonra indeksle.

---

## 10) P2.6 için önerilen minimum implementation scope

### 10.1 İçeride (minimum)

| # | Adım | Neden minimum |
|---|---|---|
| 1 | `supabase_schema.sql`'e 4 tablo ekle (`f2_formations`, `f2_snapshots`, `f2_events`, `f2_outcome_links`) + RLS | veri modeli |
| 2 | `state/formation_mirror.py`: satır bazlı fark çıkarımı + kuyruk + `SupabaseStore.upsert_many` ile toplu yazım | tek yeni modül |
| 3 | `patterns/lifecycle.py:_history_kaydet` sonuna **tek satır** mirror çağrısı (try/except, sessiz) | mevcut tek yazım yoluna dokunmadan |
| 4 | `main.py` startup: yerel defter boşsa hydrate (yalnızca AÇIK + sonuçlu kayıtlar) | restart sürekliliği |
| 5 | Graceful shutdown'ta kuyruğu flush et | veri kaybını azaltır |
| 6 | `state/paths.py`'ye `F2_FLUSH_MAX_KAYIT` / `F2_FLUSH_MAX_SN` env'leri | ayarlanabilirlik |
| 7 | Yeni test dosyası `test_p2_6_mirror.py` (mevcut testlere dokunmadan) | regression |
| 8 | Migration aracı `tools/f2_migration.py` (tekrar çalıştırılabilir, upsert) | mevcut veri taşıma |

### 10.2 Dışarıda (bilinçli olarak)

| Hariç tutulan | Gerekçe |
|---|---|
| Retention değeri kodlama | kullanıcı istemedi; değer henüz netleşmedi |
| `MAX_KAYIT=30`'ü devreye sokmak | **ürün davranışını değiştirir** (kayıt silinir) |
| Telegram UI / read repository implementasyonu | kullanıcı istemedi (P2.7) |
| Karne taşıma | kullanıcı istemedi |
| Outcome matematiği | dokunulmaz (byte-identical kanıtı) |
| Formation/lifecycle math | dokunmaz |
| `_veri_ozeti` optimizasyonu | davranış değişikliği; isteğe bağlı ayrı adım |
| Cold storage | P2.7+ |
| Kullanıcı/abonelik sistemi | kapsam dışı |

### 10.3 Tahmini dokunulan dosya sayısı

**2 mevcut dosyada toplam ~4 satır** (`lifecycle.py` 1 satır, `main.py` ~3 satır) +
**2 yeni dosya** (`formation_mirror.py`, `test_p2_6_mirror.py`) + **1 SQL eklemesi**.
Bu, "gereksiz refactor yapma" kuralına uygun minimum.

---

## 11) Riskler ve trade-off'lar

| # | Risk | Olasılık | Etki | Azaltma |
|---|---|---|---|---|
| R1 | **Hydrate sonrası `eslestir` yanlış eşleşme** → yeni SID | Orta | **Yüksek** — tüm sahiplik zinciri kırılır | Hydrate yalnızca yerel boşken; eşikler aynen devrede; `kullanilan` kümesi korunur; hydrate sonrası SID sürekliliğini ölçen test |
| R2 | Terminal kayıt her döngüde yeniden yazılır (ölçüldü 5/5) | **Kesin (mevcut)** | Orta — gereksiz Supabase trafiği | `_defter_ozeti` ile diff-gate; ya da sadece `durum` değişiminde yaz |
| R3 | Supabase 4xx → süreç boyunca devre dışı (`_disabled_reason`) | Orta | Düşük–Orta | Kuyruk birikmeye devam eder; `_disabled_reason`'ı periyodik sıfırlayan bir "re-enable probe" eklenebilir |
| R4 | Render Free `/tmp` silinir → disk kuyruğu kaybolur | **Kesin (redeploy)** | Orta | Kuyruk **bellekte** de tutulur; flush sıklığını düşük tut; "garanti verme" |
| R5 | 445 MB/365 gün → Free limit | Yüksek | Orta | Arşiv tablosu + retention kararı P2.6 sonrası |
| R6 | İki yazıcı (yerel + uzak) senkron bozulması | Orta | Orta | Yerel her zaman birincil; uzak yalnızca "en iyi çaba"; hydrate yalnızca boşken |
| R7 | `bot_store` önek (`formation-bot:`) ile yeni tablolar karışır | Düşük | Düşük | Yeni tablolar ayrı; önek sadece `bot_store` için |
| R8 | `upsert_many` hiç kullanılmamış → gizik hata | Orta | Düşük | P2.6'da ilk kez kullanılacak; ayrı test |
| R9 | Migration tekrar çalışınca duplicate | Orta | Düşük | `ON CONFLICT DO NOTHING` + `stable_id` PK |
| R10 | Yeni modül botu yavaşlatır | Düşük | Düşük | Yazım async değil, kuyruk + flush; tarama döngüsünde tek flush |

### Trade-off özeti

| Karar | Artı | Eksi |
|---|---|---|
| Local-first, Supabase mirror | bot Supabase'siz %100 çalışır | iki yazım yolu, senkron karmaşası |
| Normalize tablo (JSONB değil) | sorgulanabilir, analiz mümkün | migration + repository gerekir |
| `DO NOTHING` (değil `DO UPDATE`) | mevcut "ilk yazan kazanır" semantiği korunur | `son_gorulme` için ayrı UPDATE gerekir |
| P2.6'da retention kodlamama | kullanıcı isteğine uygun, risk az | DB büyümeye devam eder |
| Hydrate yalnızca yerel boşken | yanlış birleşme riski minimal | "iki veri kaynağını birleştirme" yok |

---

## 12) P2.6'ya başlamadan önce çözülmesi gereken kararlar

### 12.1 Kullanıcının vermesi gereken kararlar

| # | Karar | Neden kritik | Önerim |
|---|---|---|---|
| D1 | **Retention değeri** (500 mi, 90 gün mü?) | DB büyümesi doğrudan buna bağlı; Free limit 500 MB | P2.6'da kodlama; **arşiv tablosunu şimdi ekle** |
| D2 | **Hydrate kapsamı**: yalnız AÇIK kayıtlar mı, terminal + sonuçlu da mı? | Analiz için terminal verisi değerli ama hydrate'ı büyütür | AÇIK + `sonuc` bağlı terminal; diğerleri lazy |
| D3 | **Disk kuyruğu** yazılsın mı? | Render'da restart/redeploy'ta kaybolur; "garanti" vermek yanlış olur | **Evet, yazılsın** ama "en iyi çaba" olarak; garanti olarak sunulmasın |
| D4 | **`_defter_ozeti` optimizasyonu** yapılsın mı? | Davranış değişikliği (aynı içerik yeniden yazılmaz) | **Evet** — ölçülen 5/5 amplifikasyonu ortadan kaldırır, riski düşük |
| D5 | **`f2_outcome_links.outcome`** jsonb tutulsun mu? | Senkron riski vs tek-sorgu analizi | **Tutma** — Karne tek doğruluk kaynağı kalsın |
| D6 | **`MAX_KAYIT=30` devreye sokulsun mu?** | Ürün davranışı değişir (kayıt silinir) | **Hayır** — ayrı karar, P2.6 dışı |
| D7 | **Migration ne zaman çalışsın?** | İlk açılışta mı, ayrı komut mu? | Ayrı komut (`python tools/f2_migration.py`) — otomatik değil |
| D8 | **Eski `bot_store` verisi** (`state:karne_defteri`) korunsun mu? | Karne zaten ayrı; karıştırılmamalı | Olduğu gibi kalsın |

### 12.2 Teknik olarak P2.6 öncesi çözülmesi gerekenler

| # | Madde | Durum |
|---|---|---|
| T1 | `_history_kaydet`'in terminal her döngüde yazması — bilinçli mi? | **Ölçüldü, açık.** D4 kararıyla çözülür |
| T2 | `eslestir`'ın Supabase'den okuması gerekecek mi? | **Evet** (hydrate sonrası). Ama matematik değişmemeli |
| T3 | `upsert_many`'ın ilk production kullanımı | Test edilmeli |
| T4 | `SupabaseStore._request`'in 4xx'te kalıcı devre dışı bırakması | Re-enable probe eklenmeli (R3) |
| T5 | Snapshot/event için `ON CONFLICT DO NOTHING` + `son_gorulme` için ayrı UPDATE | Tasarım netleştirilmeli |
| T6 | Yeni tabloların RLS politikası | `bot_store` ile aynı tutulmalı |
| T7 | `test_p2_6_mirror.py` için deterministic test altyapısı | Mevcut `ortam` fixture deseni kullanılabilir |

---

## 13) Sonuç ve net öneri

### Öneri: **B seçeneği — normalize 4 tablo + local-first mirror + diff-gated kuyruk**

```
┌─────────────────────────────────────────────────────────────┐
│  BOT (değişmeyen çekirdek)                                   │
│  formation detection → lifecycle → _history_kaydet           │
│         │                                                    │
│         ├──► fh.kaydet (YEREL, BİRİNCİL, atomik)  ── DEĞİŞMEZ│
│         │                                                    │
│         └──► mirror_kuyruga_ekle(fark)  ── YENİ (1 satır)     │
│                    │                                         │
│                    ▼                                         │
│         bellekk+disk kuyruğu → upsert_many → Supabase        │
│                                            (en iyi çaba)     │
└─────────────────────────────────────────────────────────────┘
```

**Neden bu:**
1. Bot **her durumda** çalışır — Supabase yoksa bugünkü davranışın aynısı.
2. `stable_id` gerçek PK olur; 8 analiz hedefinin hepsi sorgu ile yanıtlanabilir.
3. Mevcut idempotency anahtarları **birebir** DB constraint'ine map edilir —
   sıfırdan tasarım gerekmez.
4. Dokunulan mevcut kod: **~4 satır.** Matematik, outcome, Karne, Telegram: **sıfır.**
5. Mevcut `upsert_many` ve `data.py`'deki diff-gate deseni **yeniden kullanılır.**

**Garanti etmediğim şey:** Supabase kapalıyken üretilen ve flush edilemeyen history'nin
süreç ölürse korunması. Render Free'ın `/tmp`'si ephemeral; disk kuyruğu restart'ı
karşılar, redeploy'u karşılamaz. Kalıcı garanti yalnızca flush sonrası başlar.

**P2.6'nın başarı kriteri (ölçülebilir):**
- Supabase tamamen kapalıyken `pytest -q` ve canlı tarama **kesintisiz** çalışır
- Restart sonrası `eslestir` aynı `stable_id`'yi re-attach eder (`len(unique(sid)) == 1`)
- Aynı event/snapshot 3× tekrar yazıldığında DB'de **1 satır** olur
- Terminal formation'ın içeriği değişmediği sürece **0 gereksiz yazım** gider
- Baseline **638 passed** korunur; yeni testler ayrı dosyada

---

**Bu raporda hiçbir kod değiştirilmedi, hiçbir commit üretilmedi.**
HEAD: `623592f` · `pytest -q`: 638 passed · Çalışma ağacı: temiz.
