-- Formation-Bot için Supabase kalıcı store şeması.
--
-- NOT (Batch 7 / C3): Uygulama anahtarları varsayılan olarak `formation-bot:` ön
-- ekiyle yazar (`SUPABASE_STORE_PREFIX`). Aynı tabloyu paylaşan ikinci bir örnek
-- varsa bu ön ek çakışmayı önler. Aşağıdaki "kullanılan anahtarlar" açıklaması
-- ÖNEKSİZ (mantıksal) adları listeler; tabloda `formation-bot:cache:1h:THYAO`
-- gibi görünürler. Ön ek devreye girerken yazılmış eski (öneksiz) kayıtlar
-- okunur ve bir sonraki yazımda ön ekli hâle taşınır.
-- Bu dosyanın tamamını Supabase Dashboard -> SQL Editor'da bir kez çalıştırın.
-- Bot bağlantısı sunucu tarafında service_role ile yapılmalı; anahtarı koda/Git'e koymayın.

create table if not exists public.bot_store (
    store_key text primary key,
    payload jsonb not null,
    updated_at timestamptz not null default now()
);

-- İstemci rolleri tabloya erişemez. RLS policy bilerek eklenmiyor:
-- Render'daki sunucu service_role kullanır ve Supabase'de RLS'i bypass eder.
alter table public.bot_store enable row level security;
revoke all privileges on table public.bot_store from public, anon, authenticated;
grant select, insert, update on table public.bot_store to service_role;

comment on table public.bot_store is
    'Formation-Bot OHLCV cache ve runtime JSON verileri için tek satır/anahtar store.';
comment on column public.bot_store.store_key is
    'Kullanılan anahtarlar: cache:1h:<SYMBOL>, cache:1d:<SYMBOL>, state:daily_fetch_attempts, state:telegram_cooldowns, state:telegram_caps, state:heartbeat, state:son_tarama, state:digest_pending, state:telegram_acil_kuyruk, state:karne_defteri.';
comment on column public.bot_store.payload is
    'OHLCV cache: timestamp/open/high/low/close/volume alanlı JSON array. Telegram cooldowns, caps, heartbeat, son tarama (state:son_tarama), bekleyen 18:45 digest tamponu (state:digest_pending) ve engellenen acil alarm kuyruğu (state:telegram_acil_kuyruk) ve haftalık doğruluk karnesi sinyal defteri (state:karne_defteri; yalnız yedek/taşıma amaçlı, yerel dosya birincildir): mevcut JSON dosya yapılarıyla uyumlu JSON object.';
comment on column public.bot_store.updated_at is
    'Son yazma zamanı; uygulama UPSERT sırasında güncel UTC zaman damgası yazar.';

-- ============================================================================
-- FAZ 2.6: FORMATION HISTORY DURABLE MIRROR & RECOVERY ŞEMASI
-- ============================================================================
-- KRİTİK: bar_time kolonları TEXT olmak ZORUNDADIR (kesinlikle timestamptz DEĞİL).
-- Yerel history 'YYYY-MM-DD HH:MM:SS+03:00' formatında string saklar;
-- _konum_bul string eşitliği arar. PostgREST timestamptz döndürürse ISO 'T'
-- ayraçlı döner ve hydration sonrası _konum_bul eşleşmeyi kaçırarak yanlış SID üretir.

-- 1) FORMATIONS (ana identity ve lifecycle durumu)
create table if not exists public.f2_formations (
    stable_id          text primary key,
    stock              text not null,
    timeframe          text not null,
    family             text,
    pattern_type       text,
    classic_dir        integer default 0,
    durum              text not null default 'acik',
    terminal_state     text,
    dogum_bar_time     text,                     -- TEXT: str(Timestamp) birebir format
    dogum_bar_index    integer,
    raw_quality        double precision,
    geometry_atr       double precision,
    pole_quality       double precision,
    start_bar          integer,
    ilk_gorulme        text,
    son_gorulme        text,
    terminal_zamani    text,
    dogum_alanlar      jsonb not null default '{}'::jsonb,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);

alter table public.f2_formations enable row level security;
revoke all privileges on table public.f2_formations from public, anon, authenticated;
grant select, insert, update on table public.f2_formations to service_role;

create index if not exists f2_formations_kimlik_idx
    on public.f2_formations (stock, timeframe, durum);
create index if not exists f2_formations_terminal_idx
    on public.f2_formations (terminal_state) where terminal_state is not null;
create index if not exists f2_formations_quality_idx
    on public.f2_formations (raw_quality);

-- 2) SNAPSHOTS (geometri, kırılım, retest, terminal snapshot evrimi)
create table if not exists public.f2_snapshots (
    id                         bigserial primary key,
    stable_id                  text not null references public.f2_formations(stable_id) on delete cascade,
    tur                        text not null,           -- geometri | kirilim | retest | terminal
    bar_time                   text not null,           -- TEXT: str(Timestamp) birebir format
    bar_index                  integer,
    state                      text,
    raw_quality                double precision,
    geometry_score             double precision,
    contraction_score          double precision,
    maturity_score             double precision,
    touch_score                double precision,
    slope_shape_score          double precision,
    break_strength             double precision,
    break_confirmation_strength double precision,
    frozen_raw_quality         double precision,
    alanlar                    jsonb not null default '{}'::jsonb,
    created_at                 timestamptz not null default now(),
    constraint f2_snapshots_dedup_tek unique (stable_id, tur, bar_time)
);

alter table public.f2_snapshots enable row level security;
revoke all privileges on table public.f2_snapshots from public, anon, authenticated;
grant select, insert, update on table public.f2_snapshots to service_role;

create index if not exists f2_snapshots_sid_tur_idx
    on public.f2_snapshots (stable_id, tur);
create index if not exists f2_snapshots_bar_time_idx
    on public.f2_snapshots (bar_time);

-- 3) EVENTS (yaşam döngüsü olayları / state geçişleri)
create table if not exists public.f2_events (
    id         bigserial primary key,
    stable_id  text not null references public.f2_formations(stable_id) on delete cascade,
    type       text not null,
    name       text not null,
    bar        integer,
    bar_time   text,                                    -- TEXT: str(Timestamp) birebir format
    state      text,
    quality    double precision,
    direction  integer,
    price      double precision,
    payload    jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint f2_events_dedup_tek unique (stable_id, type, name, bar, bar_time)
);

alter table public.f2_events enable row level security;
revoke all privileges on table public.f2_events from public, anon, authenticated;
grant select, insert, update on table public.f2_events to service_role;

create index if not exists f2_events_sid_bar_idx
    on public.f2_events (stable_id, bar);

-- 4) OUTCOME LINKS (P2.5 Formation -> Karne bağlantı durumu)
create table if not exists public.f2_outcome_links (
    stable_id  text primary key references public.f2_formations(stable_id) on delete cascade,
    durum      text not null,                           -- hedef | stop | nötr | bekliyor | ölçülemedi
    deneme     integer not null default 0,
    kaynak     text,                                    -- birincil kırılımın bar_time'ı (TEXT)
    outcome    jsonb not null default '{}'::jsonb,      -- sinyal_sonucu temel özeti
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.f2_outcome_links enable row level security;
revoke all privileges on table public.f2_outcome_links from public, anon, authenticated;
grant select, insert, update on table public.f2_outcome_links to service_role;

create index if not exists f2_outcome_links_durum_idx
    on public.f2_outcome_links (durum);
