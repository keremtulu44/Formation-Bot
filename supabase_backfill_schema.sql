-- ============================================================================
-- FAZ 1: DERİN GEÇMİŞ ARAŞTIRMA ARŞİVİ (dz_* — "domain zone")
-- ============================================================================
-- AMAÇ: OB / FVG / Engulfing / Market Structure / Hacim gözlemlerini, ilerde
-- backtest ile test edilebilecek biçimde kalıcılaştırmak. Canlı botun
-- `f2_*` aynası YALNIZ klasik formasyon (üçgen/kama/bayrak) yaşam döngüsünü
-- taşır; dört domain motorunun çıktısı bugün yalnız süreç belleğinde kalır
-- (domain_engines/runner.py:54 `_latest_by_series`). Bu şema o boşluğu kapatır.
--
-- CANLI YOLA DOKUNMAZ: bu tablolar canlı tarama tarafından okunmaz/yazılmaz.
-- Yalnız `scripts/backfill/*` ve ileride eklenecek ölçüm/rapor katmanı kullanır.
--
-- Bu dosyanın tamamını Supabase Dashboard -> SQL Editor'da BİR KEZ çalıştırın.
-- supabase_schema.sql'den BAĞIMSIZDIR; sıralama önemli değil.
--
-- ============================================================================
-- ÜÇ KRİTİK ŞEMA KURALI (ihlal edilirse veri seti sessizce bozulur)
-- ============================================================================
-- K1) bar_time / *_at KOLONLARI TEXT OLMAK ZORUNDADIR (timestamptz DEĞİL).
--     Gerekçe supabase_schema.sql'de de yazılı: yerel kayıt
--     'YYYY-MM-DD HH:MM:SS+03:00' formatında string tutar; PostgREST
--     timestamptz'i ISO 'T' ayraçlı döndürür ve string eşitliği arayan konum
--     bulma eşleşmeyi SESSİZCE kaçırır. Arşivde aynı disiplin korunur.
--
-- K2) DOĞAL ANAHTARLAR BAR_TIME İLE KURULUR, İNDEKSLE DEĞİL.
--     `source_index` (OB), `formation_index` (FVG), `identity` (MS swing/event)
--     ve tüm bar indeksleri PENCERE-RELATİFTİR: 360 barlık canlı deque ile 365
--     günlük arşiv aynı zone'a FARKLI indeks verir. İndeksi kimlik yaparsan her
--     koşu hayalet satır üretir. İndeks kolonları yalnız TANI amaçlıdır ve
--     yanlarında pencere bağlamı (pencere_ilk_bar / pencere_bar_sayisi) taşır.
--     Repo aynı tuzağı f2_formations için de belgelemiştir.
--
-- K3) HER TÜRETİLMİŞ SATIRDA engine_version + config_hash + kaynak + run_id.
--     OB'de fill_cancel_threshold=0.70, VP'de ~30 eşik, FVG'de duyarlılık
--     profili var. Bir eşiği değiştirirsen eski satırlar BAŞKA bir üretici
--     süreçten gelir; parmak izi yoksa veri seti analiz edilemez olur.
--     `kaynak` = backfill | weekend_batch | live_scan (popülasyon ayrımı:
--     canlı yol incremental cursor, batch soğuk tam replay kullanır).
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1) dz_bars — HAM OHLCV ARŞİVİ (kaynak doğrulanabilirlik katmanı)
-- ----------------------------------------------------------------------------
-- Neden zorunlu: (a) 1H penceresi 60 günde kayar ve arşivlenmeyen bar KALICI
-- kaybolur (DEQUE_MAXLEN=360 Pine uyumu için bilerek büyütülmez, config.py:225);
-- (b) türetilmiş gözlemler motor mantığı değişince YENİDEN hesaplanabilmelidir —
-- ham barlar olmadan bu imkânsız; (c) PH/PL "fiyata engel olabildi mi" ve WL/WH
-- "süpürme derinliği" soruları zone/swing satırlarından DEĞİL, ham barlardan
-- cevaplanır.
--
-- auto_adjust=False ile HAM fiyat yazılır (Pine/TV paritesi; data.py:1757).
create table if not exists public.dz_bars (
    symbol         text        not null,
    timeframe      text        not null,             -- 1h | 1d (2h/4h türetilir)
    bar_time       text        not null,             -- K1: TEXT
    open           double precision,
    high           double precision,
    low            double precision,
    close          double precision,
    volume         double precision,
    -- veri kalitesi: kirli bar SESSİZCE düşürülmez, bayrakla yazılır (K5 aşağıda)
    nan_ohlc       boolean     not null default false,
    sifir_hacim    boolean     not null default false,
    split_adayi    boolean     not null default false,   -- |open-prev_close|/prev_close > %10
    kaynak         text        not null default 'backfill',
    run_id         text,
    ingested_at    timestamptz not null default now(),
    constraint dz_bars_pk primary key (symbol, timeframe, bar_time)
);

alter table public.dz_bars enable row level security;
revoke all privileges on table public.dz_bars from public, anon, authenticated;
grant select, insert, update on table public.dz_bars to service_role;

-- Sorgu desenleri: sembol serisi çekme + watermark (max bar_time) + run denetimi
create index if not exists dz_bars_seri_idx
    on public.dz_bars (symbol, timeframe, bar_time);
create index if not exists dz_bars_run_idx
    on public.dz_bars (run_id) where run_id is not null;

comment on table public.dz_bars is
    'Ham OHLCV arşivi. auto_adjust=False (ham fiyat). 2h/4h TÜRETİLİR, saklanmaz: '
    'resample_ohlcv seans başına hizalı kova kullanır (data.py:1470) ve aynı girdiden '
    'deterministik yeniden üretilebilir.';
comment on column public.dz_bars.bar_time is
    'K1: TEXT zorunlu. Biçim: YYYY-MM-DD HH:MM:SS+03:00 (Europe/Istanbul).';
comment on column public.dz_bars.split_adayi is
    'SPLIT_SUREKLILIK_ESIK_PCT=10.0 (config.py:208) ile aynı eşik. Satır DÜŞÜRÜLMEZ: '
    'eleme kararı ingest/analiz katmanınındır, aksi halde survivorship bias oluşur.';


-- ----------------------------------------------------------------------------
-- 2) dz_zones — OB / FVG / ENGULFING DOĞUŞ + TERMİNAL
-- ----------------------------------------------------------------------------
-- family: OB | FVG | ENGULFING
-- Doğal anahtar: (symbol, timeframe, family, direction, dogum_bar_time) — K2.
-- Sütunlar motorların NATIVE alan adlarıyla birebir eşlenir:
--   OB  -> OrderBlockRecord (domain_engines/order_block/order_block_engine.py:28)
--   FVG -> FvgLifecycleRecord (domain_engines/fvg/fvg_engulfing_final.py:55)
create table if not exists public.dz_zones (
    zone_id            text primary key,             -- '<symbol>:<tf>:<family>:<dir>:<dogum_bar_time>'
    symbol             text not null,
    timeframe          text not null,                -- 1h | 2h | 4h | 1d
    family             text not null,                -- OB | FVG | ENGULFING
    direction          text not null,                -- bullish | bearish
    -- DOĞUŞ (K2: bar_time kimliktir, indeks tanıdır)
    dogum_bar_time     text not null,
    dogum_bar_index    integer,                      -- TANIM: pencere-relatif
    pencere_ilk_bar    text,                         -- indeksin hangi pencereye ait olduğu
    pencere_bar_sayisi integer,
    -- ORTAK GEOMETRİ
    zone_lower         double precision not null,    -- OB: bottom   / FVG: lower_boundary
    zone_upper         double precision not null,    -- OB: top      / FVG: upper_boundary
    yukseklik          double precision,             -- zone_upper - zone_lower (ham)
    yukseklik_atr      double precision,             -- ATR-normalize: KARŞILAŞTIRILABİLİR tek ölçü
    atr_at_dogum       double precision,             -- normalizasyonun girdisi (denetlenebilirlik)
    quality            double precision,
    -- OB'ye özgü (OrderBlockRecord)
    base_score         integer,
    has_imbalance      boolean,
    score              integer,                      -- base_score + (1 if has_imbalance)
    ob_active          boolean,                      -- has_imbalance and score == 3
    anchor_high        double precision,
    anchor_low         double precision,
    fill_boundary      double precision,
    maximum_fill_ratio double precision,
    -- FVG/Engulfing'e özgü (FvgLifecycleRecord / EngulfingLifecycleRecord)
    gap_size           double precision,
    gap_atr            double precision,             -- FVG'de yükseklik zaten ATR-normalize gelir
    body_size          double precision,             -- ENGULFING
    body_atr           double precision,             -- ENGULFING
    formation_atr      double precision,
    invalidation_buffer double precision,
    evidence_count     integer,
    embedded_candle_contribution double precision,
    -- TERMİNAL (zone nasıl öldü)
    terminal_bar_time  text,
    terminal_state     text,                         -- FvgState / OB kaldırma durumu
    terminal_reason    text,                         -- invalid_reason | gap_through | fill_cancel ...
    terminal_category  text,
    price_violation    boolean,
    full_fill          boolean,
    sansur             text not null default 'YOK',  -- YOK | SAGDAN_SANSURLU (veri sonunda hâlâ açık)
    -- motor parmak izi (K3)
    engine_version     text,
    config_hash        text,
    kaynak             text not null default 'backfill',
    run_id             text,
    created_at         timestamptz not null default now(),
    constraint dz_zones_dogal_tek unique (symbol, timeframe, family, direction, dogum_bar_time)
);

alter table public.dz_zones enable row level security;
revoke all privileges on table public.dz_zones from public, anon, authenticated;
grant select, insert, update on table public.dz_zones to service_role;

create index if not exists dz_zones_soru_idx
    on public.dz_zones (family, timeframe, direction);
create index if not exists dz_zones_sembol_idx
    on public.dz_zones (symbol, timeframe);
create index if not exists dz_zones_yukseklik_idx
    on public.dz_zones (family, timeframe, yukseklik_atr);
create index if not exists dz_zones_config_idx
    on public.dz_zones (config_hash);

comment on table public.dz_zones is
    'Zone doğuş + terminal. "Yükseklik -> tepki şekli" sorusunun girdisi: yukseklik_atr '
    'kuvaları ile dz_zone_touches şekil metrikleri çaprazlanır.';
comment on column public.dz_zones.sansur is
    'Veri sonunda hâlâ açık zone "başarısız" DEĞİLDİR, sağdan sansürlüdür. Ayrı sayılmazsa '
    'yüzdeler veri penceresinin uzunluğuna göre değişen bir artefakt olur.';
comment on column public.dz_zones.dogum_bar_index is
    'K2: TANIM amaçlı, pencere-relatif. Kimlik dogum_bar_time''dır.';


-- ----------------------------------------------------------------------------
-- 3) dz_zone_touches — TEMAS EPISODELARI + ŞEKİL METRİKLERİ + HACİM ÖRNEĞİ
-- ----------------------------------------------------------------------------
-- Kaynak: directional_zone_replay.build_touch_episodes / build_window_rows.
-- Bu tablo üç soruyu birden cevaplar:
--   (a) tek denemede mi çok denemede mi -> touch_number + touch_bar_count
--   (b) tepki nereden/hangi yönde -> boundary_anchored + ust/alt yönlü excursion
--   (c) ani mi ağır-uzun mu -> bars_to_peak, peak_share_at_*, decay_ratio
-- Hacim burada BAR BAŞINA değil ÇAPA ANINDA örneklenir: VP metrics_history[i]
-- indexlenebilir, dolayısıyla 118.000 satırlık bar-başı tabloya gerek yok.
create table if not exists public.dz_zone_touches (
    touch_id           text primary key,             -- '<zone_id>|touch<N>|<touch_start>'
    zone_id            text not null references public.dz_zones(zone_id) on delete cascade,
    symbol             text not null,
    timeframe          text not null,
    family             text not null,
    direction          text not null,
    touch_number       integer not null,             -- zone içindeki kaçıncı deneme
    touch_bar_count    integer,                      -- bu deneme kaç bar sürdü
    touch_start        text not null,                -- K1: TEXT
    touch_end          text not null,
    touch_start_index  integer,                      -- TANIM: pencere-relatif
    touch_end_index    integer,
    -- GELİŞ YÖNÜ / HANGİ KENAR
    arrival_side           text,                     -- FROM_ABOVE|FROM_BELOW|INSIDE_ZONE|ON_ZONE_BOUNDARY|NO_PREVIOUS_BAR
    approach_direction     text,                     -- DOWN_TOWARD_ZONE|UP_TOWARD_ZONE|AMBIGUOUS|UNKNOWN
    arrival_previous_close double precision,
    boundary_anchored      text not null default 'BELIRSIZ',  -- UST|ALT|BELIRSIZ
    -- zone'un temas sonundaki kalan durumu (doluluk ölçümü)
    remaining_lower_at_touch_end double precision,
    remaining_upper_at_touch_end double precision,
    fill_ratio_before_touch_end_bar double precision,
    wick_fill_ratio      double precision,           -- FVG: fitille mi doldu
    close_fill_ratio     double precision,           -- FVG: gövdeyle mi doldu
    atr_at_touch         double precision,           -- tüm ATR normalizasyonlarının paydası
    -- YÖNE-ÇAPALI excursion (mevcut directional_excursions semantiği)
    favorable_atr_h10    double precision,
    adverse_atr_h10      double precision,
    favorable_atr_h12    double precision,
    adverse_atr_h12      double precision,
    -- KENARA-ÇAPALI excursion (YENİ): üst kenara temas -> AŞAĞI, alt kenara -> YUKARI
    -- Neden ayrı: mevcut fonksiyon zone YÖNÜNE (bullish/bearish) bakıyor, dokunulan
    -- kenara bakmıyor. "OB yukarıdayken direnç gibi çalışır" sorusu kenara-çapalıdır.
    kenar_yonlu_tepki_atr_h10 double precision,
    kenar_yonlu_tepki_atr_h12 double precision,
    kenar_yonlu_ters_atr_h10  double precision,
    -- ŞEKİL: ani mi, ağır ama uzun mu
    peak_excursion_atr   double precision,           -- pencere içi tepe (yön lehine)
    bars_to_peak         integer,                    -- tepeye kaç barda ulaştı
    peak_share_at_1      double precision,           -- 1. bardaki / tepe  (1.0 = ani)
    peak_share_at_3      double precision,
    peak_share_at_5      double precision,
    bars_in_profit       integer,                    -- kaç bar excursion > 0 kaldı
    decay_ratio          double precision,           -- (tepe - h10 sonu) / tepe: ne kadarı geri verildi
    horizon_10_12_farki  double precision,           -- hâlâ büyüyor mu, doygun mu
    -- SONUÇ / SANSÜR
    observed_post_touch_bars integer,
    window_complete      boolean,
    status               text not null,              -- COMPLETE|RIGHT_CENSORED_DATA_END|ATR14_UNAVAILABLE_AT_TOUCH|NATIVE_TERMINAL_ON_TOUCH
    native_terminal_at_touch boolean,
    -- HACİM ÖRNEĞİ (çapa anında; bar başına DEĞİL)
    vp_data_ready        boolean,
    vp_volume_usable     boolean,
    vp_capital_usable    boolean,
    vp_rvol              double precision,
    vp_volume_z_score    double precision,
    vp_volume_percent_rank double precision,
    vp_capital_z_score   double precision,
    vp_directional_value_pressure_10 double precision,
    vp_net_progress_atr  double precision,
    vp_directional_efficiency double precision,
    vp_effort_result_class text,                     -- çaba(hacim) <-> sonuç(fiyat) sınıfı
    vp_participation_stage text,
    vp_up_confirmed      boolean,
    vp_down_confirmed    boolean,
    -- motor parmak izi (K3)
    engine_version       text,
    config_hash          text,
    kaynak               text not null default 'backfill',
    run_id               text,
    created_at           timestamptz not null default now()
);

alter table public.dz_zone_touches enable row level security;
revoke all privileges on table public.dz_zone_touches from public, anon, authenticated;
grant select, insert, update on table public.dz_zone_touches to service_role;

create index if not exists dz_touches_zone_idx
    on public.dz_zone_touches (zone_id);
create index if not exists dz_touches_soru_idx
    on public.dz_zone_touches (family, timeframe, direction, boundary_anchored);
create index if not exists dz_touches_status_idx
    on public.dz_zone_touches (status);
create index if not exists dz_touches_hacim_idx
    on public.dz_zone_touches (vp_volume_usable, vp_effort_result_class);

comment on table public.dz_zone_touches is
    'Temas episode + yönlü/kenara-çapalı ATR excursion + tepki şekli + çapa anı hacim örneği. '
    'Her hücre sorguda n ile raporlanmalı (analytics/backtest.py: n<15 betimleyici, 15-30 kısmi, >=30 yeterli).';
comment on column public.dz_zone_touches.boundary_anchored is
    'UST/ALT yalnız arrival_side FROM_ABOVE/FROM_BELOW iken atanır; INSIDE_ZONE ve '
    'ON_ZONE_BOUNDARY BELIRSIZ kalır. Belirsizler NE düşürülür NE diğerlerine katılır '
    '(classify_arrival zaten AMBIGUOUS döndürür) — düşürmek seçim yanlılığı üretir.';
comment on column public.dz_zone_touches.vp_volume_usable is
    'Bayrak SATIRDA taşınır, satır düşürülmez. BIST hacim verisi bazı sembollerde sorunlu; '
    'bayraksız kurulan korelasyon çöp olur ve sonradan fark edilemez.';


-- ----------------------------------------------------------------------------
-- 4) dz_ms_swings — MARKET STRUCTURE SWING'LERİ (WL/WH/PL/PH/SL/SH)
-- ----------------------------------------------------------------------------
-- Kaynak: SwingPoint (domain_engines/market_structure/market_structure.py:84),
-- runner'da details["external_swings"] / details["internal_swings"] içinde.
-- structural_role sabitleri: WEAK_HIGH/WEAK_LOW/STRONG_HIGH/STRONG_LOW/
-- PROTECTED_HIGH/PROTECTED_LOW (market_structure_state.py:17-22).
--
-- K2 TUZAĞI BURADA DA VAR: `identity` replay sırasında sırayla atanır, yani
-- pencere başlangıcı değişirse NUMARALAMA KAYAR. Kimlik bu yüzden
-- (symbol, timeframe, scope, side, confirm_bar_time, price) bileşimidir.
create table if not exists public.dz_ms_swings (
    swing_id          text primary key,              -- '<symbol>:<tf>:<scope>:<side>:<confirm_bar_time>:<price>'
    symbol            text not null,
    timeframe         text not null,
    scope             text not null,                 -- external | internal (AYRI analiz edilir)
    side              text not null,                 -- high | low
    identity          integer,                       -- TANIM: pencere-relatif (K2)
    pencere_ilk_bar   text,
    pencere_bar_sayisi integer,
    structural_role   text,                          -- WEAK_* | STRONG_* | PROTECTED_* | neutral
    swing_class       text,
    state             text,
    source_bar        integer,
    confirm_bar       integer,
    confirm_bar_time  text,                          -- K1: TEXT — lookahead çapası
    source_bar_time   text,
    price             double precision not null,
    atr_at_source     double precision,
    prominence_atr    double precision,
    distance_atr      double precision,
    distance_pct      double precision,
    finalized         boolean,
    locked            boolean,
    quality           double precision,
    -- KIRILMA / UĞRANMA
    broken            boolean,
    broken_bar        integer,
    broken_bar_time   text,
    bars_to_break     integer,                       -- confirm_bar -> broken_bar: "ne kadar sürede gelindi"
    sansur            text not null default 'YOK',   -- YOK | SAGDAN_SANSURLU (veri sonunda kırılmamış)
    -- DENEME SAYISI (PH/PL "kaç kez denendi") — eşikler ÖNCEDEN deklare edildi
    deneme_025_atr    integer,                       -- birincil eşik: 0.25 ATR yaklaşma
    deneme_015_atr    integer,                       -- duyarlılık kontrolü
    deneme_050_atr    integer,                       -- duyarlılık kontrolü
    ilk_deneme_bar_time text,
    son_deneme_bar_time text,
    -- ENGELLEME / TEPKİ (PH/PL "fiyata engel olabildi mi")
    engelledi         boolean,                       -- yaklaşma sonrası fiyat geri döndü mü
    red_magnitude_atr double precision,              -- yaklaşıp dönmede ATR cinsinden red
    max_yaklasma_atr  double precision,              -- seviyeye en yakın yaklaşma (ATR)
    -- motor parmak izi (K3)
    engine_version    text,
    config_hash       text,
    kaynak            text not null default 'backfill',
    run_id            text,
    created_at        timestamptz not null default now(),
    constraint dz_ms_swings_dogal_tek unique
        (symbol, timeframe, scope, side, confirm_bar_time, price)
);

alter table public.dz_ms_swings enable row level security;
revoke all privileges on table public.dz_ms_swings from public, anon, authenticated;
grant select, insert, update on table public.dz_ms_swings to service_role;

create index if not exists dz_swings_rol_idx
    on public.dz_ms_swings (scope, structural_role, timeframe);
create index if not exists dz_swings_sembol_idx
    on public.dz_ms_swings (symbol, timeframe, scope);
create index if not exists dz_swings_kirilma_idx
    on public.dz_ms_swings (structural_role, broken, sansur);

comment on table public.dz_ms_swings is
    'WL/WH uğranma + PH/PL destek-direnç dayanıklılığı. scope=external/internal AYRI '
    'raporlanmalı: config farklı (external_pivot_len=5 / internal_pivot_len=2, mesafe '
    'eşiği 0.45 / 0.20 ATR), internal çok daha sık ve gürültülü üretir.';
comment on column public.dz_ms_swings.sansur is
    'Pencere sonunda kırılmamış PL "başarılı destek" DEĞİLDİR, sağdan sansürlüdür. '
    '"Bugüne kadar kırılmadı" ile "fiyatı gerçekten geri çevirdi" ayrı sayılmalı.';


-- ----------------------------------------------------------------------------
-- 5) dz_ms_events — BOS / CHOCH OLAYLARI + DEVAMLILIK
-- ----------------------------------------------------------------------------
-- Kaynak: MarketStructureEventRecord (market_structure_events.py:51).
-- "yüzde kaçı işe yaradı / az devamlılık" sorusunun cevabı motorun KENDİ
-- enum'larında hazır: outcome = FOLLOW_THROUGH_CONFIRMED | FAILED | OBSERVED | PENDING.
--
-- LOOKAHEAD KORUMASI: candidate_at != confirmed_at. Tüm ileri yönlü ölçümler
-- confirmed_at'tan başlar; candidate_at'tan başlatmak henüz bilinmeyen bilgiyi
-- kullanmak olur ve devamlılık yüzdelerini şişirir.
create table if not exists public.dz_ms_events (
    event_id           text primary key,             -- '<symbol>:<tf>:<scope>:<event_type>:<confirmed_at>:<broken_level>'
    symbol             text not null,
    timeframe          text not null,
    scope              text not null,                -- external | internal
    event_type         text not null,                -- BOS | CHOCH | ...
    direction          integer not null,             -- +1 / -1 / 0
    identity           integer,                      -- TANIM: pencere-relatif (K2)
    event_uid          text,                          -- TANIM: scope-local, pencere-relatif
    pencere_ilk_bar    text,
    pencere_bar_sayisi integer,
    -- LOOKAHEAD ÇİFTİ (ikisi de saklanır)
    candidate_bar      integer,
    candidate_at       text,                         -- K1
    event_bar          integer,
    confirmed_at       text not null,                -- K1 — ÖLÇÜM ÇAPASI
    broken_swing_identity integer,
    broken_source_bar  integer,
    broken_source_at   text,
    broken_level       double precision,             -- kırılan seviye
    origin_swing_identity integer,
    origin_source_bar  integer,
    origin_source_at   text,
    origin_price       double precision,
    quality            double precision,
    -- GÜVENİLİRLİK (4 enum + olgunluk)
    confirmation_status text,                        -- CONFIRMED | CANDIDATE_FAILED
    validity            text,                        -- VALID | FAILED
    relevance           text,                        -- CURRENT | SUPERSEDED | HISTORICAL
    outcome             text,                        -- PENDING | FOLLOW_THROUGH_CONFIRMED | FAILED | OBSERVED
    bos_maturity        text,                        -- NOT_APPLICABLE | INITIAL_STRUCTURE | TRANSITION_CONFIRMATION | CONTINUATION
    age_bars            integer,
    confirmed_by_event_uid text,
    failed_by_event_uid text,
    confirmation_high  double precision,
    confirmation_low   double precision,
    confirmation_close double precision,
    -- DEVAMLILIK ÖLÇÜMÜ (confirmed_at çapalı, ATR cinsinden — ortak çekirdek)
    atr_at_confirm     double precision,
    follow_atr_h10     double precision,             -- söylenen yönde alınan yol
    follow_atr_h12     double precision,
    ters_yon_atr_h10   double precision,             -- söylenen yönün tersine giden yol
    bars_to_peak       integer,
    peak_share_at_5    double precision,
    decay_ratio        double precision,
    devamlilik_sinifi  text,                         -- YUKSEK | ORTA | DUSUK | YOK | SANSURLU
    status             text not null default 'COMPLETE',
    -- hacim örneği (çapa anında)
    vp_data_ready      boolean,
    vp_volume_usable   boolean,
    vp_rvol            double precision,
    vp_volume_percent_rank double precision,
    vp_effort_result_class text,
    -- motor parmak izi (K3)
    engine_version     text,
    config_hash        text,
    kaynak             text not null default 'backfill',
    run_id             text,
    created_at         timestamptz not null default now(),
    constraint dz_ms_events_dogal_tek unique
        (symbol, timeframe, scope, event_type, confirmed_at, broken_level)
);

alter table public.dz_ms_events enable row level security;
revoke all privileges on table public.dz_ms_events from public, anon, authenticated;
grant select, insert, update on table public.dz_ms_events to service_role;

create index if not exists dz_events_soru_idx
    on public.dz_ms_events (scope, event_type, direction, timeframe);
create index if not exists dz_events_outcome_idx
    on public.dz_ms_events (outcome, validity, relevance);
create index if not exists dz_events_sembol_idx
    on public.dz_ms_events (symbol, timeframe, scope);

comment on table public.dz_ms_events is
    'BOS/CHOCH yön -> tepki yönü ve devamlılığı. Ölçüm çapası HER ZAMAN confirmed_at; '
    'candidate_at yalnız lookahead denetimi için saklanır.';
comment on column public.dz_ms_events.devamlilik_sinifi is
    'Motorun native outcome hükmünden BAĞIMSIZ, ATR eşik ızgarasından türetilir. İkisi '
    'birlikte raporlanır: native hüküm motorun tanımı, sınıf bizim tanımlı eşiklerimizdir.';


-- ----------------------------------------------------------------------------
-- 6) dz_batch_runs — KOŞU GÖZLEMLENEBİLİRLİĞİ + BEKÇİ
-- ----------------------------------------------------------------------------
-- Neden kritik: bir koşu kaçarsa, o hafta pencereden düşen 1H barlar KALICI
-- kaybolur ve sağdan sansürlü gözlemler çözümsüz kalır. "son N günde başarılı
-- koşu var mı" sorgusu bu tablodan yapılır.
create table if not exists public.dz_batch_runs (
    run_id            text primary key,
    basladi           timestamptz not null,
    bitti             timestamptz,
    mod               text not null,                 -- probe | backfill | retry_failed
    durum             text not null default 'suruyor', -- suruyor | ok | kismi | basarisiz | ban_korumasi
    evren             text,                          -- havuz | dogrulanmis | ozel
    sembol_sayisi     integer,
    basarili          integer,
    atlanan           integer,
    kalici_basarisiz  integer,
    gecici_basarisiz  integer,
    period_1h         text,
    period_1d         text,
    derinlik_gun       integer,
    toplam_istek      integer,
    soguma_sayisi     integer,
    sure_sn           double precision,
    satir_bars        integer,
    satir_zones       integer,
    satir_touches     integer,
    satir_swings      integer,
    satir_events      integer,
    baslayan_yarbay   double precision,              -- ölçülen en yaşlı AKTİF zone (replay penceresi sınırı için)
    engine_version    text,
    detay             jsonb not null default '{}'::jsonb,
    created_at        timestamptz not null default now()
);

alter table public.dz_batch_runs enable row level security;
revoke all privileges on table public.dz_batch_runs from public, anon, authenticated;
grant select, insert, update on table public.dz_batch_runs to service_role;

create index if not exists dz_runs_bekci_idx
    on public.dz_batch_runs (basladi desc);
create index if not exists dz_runs_durum_idx
    on public.dz_batch_runs (durum);

comment on table public.dz_batch_runs is
    'Koşu günlüğü ve bekçi kaynağı. Kaçan koşu = kalıcı veri kaybı (1H penceresi kayar), '
    'bu yüzden son başarılı koşu yaşı izlenmelidir.';
comment on column public.dz_batch_runs.baslayan_yarbay is
    'Pilot ölçümü: "hâlâ aktif olan en yaşlı zone kaç seanslık?" — replay penceresi '
    'sınırını (arşiv derin, replay sınırlı) belirleyen sayı.';
