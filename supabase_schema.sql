-- Formation-Bot için Supabase kalıcı store şeması.
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
    'Kullanılan anahtarlar: cache:1h:<SYMBOL>, cache:1d:<SYMBOL>, state:daily_fetch_attempts, state:telegram_cooldowns, state:telegram_caps, state:heartbeat, state:son_tarama.';
comment on column public.bot_store.payload is
    'OHLCV cache: timestamp/open/high/low/close/volume alanlı JSON array. Telegram cooldowns, caps, heartbeat ve son tarama (state:son_tarama): mevcut JSON dosya yapılarıyla uyumlu JSON object.';
comment on column public.bot_store.updated_at is
    'Son yazma zamanı; uygulama UPSERT sırasında güncel UTC zaman damgası yazar.';

-- Lifecycle state ayrıca saklanmaz: repo her taramada OHLCV cache'inden yeniden oynatır.
-- data.py'deki günlük fetch deneme zamanları state:daily_fetch_attempts JSON nesnesinde tutulur.
