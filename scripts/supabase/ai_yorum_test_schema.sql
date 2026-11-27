-- Telegram yayını öncesi gölge (shadow) AI yorum + gizli 5-filtre sonuç
-- değerlendirme ve ileri fiyat performans ölçüm tablosu.
-- Sunucu tarafında yalnızca service_role erişebilir; anon/authenticated kapalıdır.

create table if not exists public.ai_yorum_test (
    anahtar          text primary key,
    sembol           text not null,
    tf               text not null,
    kesit_zamani     timestamptz not null,
    referans_fiyat   double precision,
    kaynak_turu      text not null default 'manuel',
    tetikleyici_tur  text,
    egilim           text check (egilim is null or egilim in ('yukari', 'asagi', 'kararsiz')),
    guc              text check (guc is null or guc in ('dusuk', 'orta', 'yuksek')),
    mtf_uyum         text check (mtf_uyum is null or mtf_uyum in ('uyumlu', 'karma', 'celiskili')),
    risk             text check (risk is null or risk in ('dusuk', 'orta', 'yuksek')),
    yayin_degeri     text check (yayin_degeri is null or yayin_degeri in ('gonder', 'izle', 'pas')),
    filtreler        jsonb not null default '{}'::jsonb,
    temiz_yorum      text not null,
    ham_sonuc_blogu  text,
    dogrulama        jsonb not null default '{}'::jsonb,
    model_adi        text,
    prompt_surumu    text not null default 'api-v1',
    system_sha256    text,
    telegrama_gitti  boolean not null default false,
    baglam_ozet      jsonb not null default '{}'::jsonb,
    sonuc            jsonb,
    olcum_zamani     timestamptz,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

alter table public.ai_yorum_test enable row level security;
revoke all privileges on table public.ai_yorum_test from public, anon, authenticated;
grant select, insert, update on table public.ai_yorum_test to service_role;

create index if not exists ai_yorum_test_sembol_tf_kesit_idx
    on public.ai_yorum_test (sembol, tf, kesit_zamani desc);

create index if not exists ai_yorum_test_filtreler_idx
    on public.ai_yorum_test (yayin_degeri, egilim, guc);

create index if not exists ai_yorum_test_bekleyen_olcum_idx
    on public.ai_yorum_test (kesit_zamani)
    where sonuc is null;

comment on table public.ai_yorum_test is
    'Telegram yayini oncesi golge (shadow) AI yorum, gizli 5-filtre sonucu ve ileri fiyat performans olcum tablosu.';

create or replace view public.v_ai_yorum_test_ozet
with (security_invoker = true) as
select
    egilim,
    guc,
    mtf_uyum,
    risk,
    yayin_degeri,
    coalesce(model_adi, 'bilinmiyor') as model_adi,
    prompt_surumu,
    count(*) as toplam_kayit,
    count(*) filter (where sonuc is not null and sonuc ? 'yuzde') as olculen_kayit,
    round(avg((sonuc ->> 'yuzde')::double precision)::numeric, 3) as ortalama_yuzde,
    round(avg((sonuc ->> 'yon_uyumlu_yuzde')::double precision)::numeric, 3) as ortalama_yon_uyumlu_yuzde,
    round(
        avg(
            case
                when (sonuc ->> 'yon_isabet') = 'true' then 1.0
                when (sonuc ->> 'yon_isabet') = 'false' then 0.0
                else null
            end
        )::numeric,
        3
    ) as yon_isabet_orani,
    min(kesit_zamani) as ilk_kesit,
    max(kesit_zamani) as son_kesit
from public.ai_yorum_test
group by
    egilim,
    guc,
    mtf_uyum,
    risk,
    yayin_degeri,
    coalesce(model_adi, 'bilinmiyor'),
    prompt_surumu;

revoke all privileges on table public.v_ai_yorum_test_ozet from public, anon, authenticated;
grant select on table public.v_ai_yorum_test_ozet to service_role;
