# P0-P2 Uygulama Planı — Adım Adım (27 Ekim 2026)

Bu dosya ilk üç önerinin adım adım uygulanmasını takip eder.
Her adım: Kod + Test + Commit + Doğrulama.

## P0 — Tatil/yarım günde sonsuz döngü yok + restart körlüğü yok
- **Durum:** Zaten büyük ölçüde düzelmiş
  - `data/replay.py:time_until_next_open` tatili atlıyor (aday loop weekday>=5 or bist_tatil_adi)
  - `bot/app.py:726-734` taban uyku `max(sleep_time,60)` var → 0 sn döngü yok
  - `bot/app.py:146` `son_tarama_yukle(supabase_store)` çağrısı var (main_loop başında, ping sonrası)
- **Eksik:** 
  - `sonraki_islem_gunu()` 60 günlük limit, ama `time_until_next_open` 2027 tatillerini doğru atlıyor — test yok
  - BIST KAPALI dalında `formation_mirror` flush yok (P2'ye sarkıyor)
- **Yapılacak:** 
  1. `test_p0_tatil_uyku.py` — tatil ve yarım gün için `time_until_next_open > 0` ve `is_bist_open==False` testi
  2. `bot/app.py` BIST KAPALI dalına `time_until_next_open` logunu daha net yaz (açılışa kaç saat)

## P1 — Kayıp sayaçları görünür
- **Durum:** Zaten var
  - `bot/counters.py:reset_daily_if_needed` 14 sayaç sıfırlıyor (alerts_below_threshold, alerts_engel_cooldown/kap/tekrar, alerts_kuyruk, alerts_digest_overflow, alerts_bar_kapanmadi vb.)
  - `bot/scan.py:811,815,829,837,1157` her biri artırılıyor
  - `bot/commands.py:336-348` hunisi: `🔎 Aday hunisi: 21 üretildi · 3 push · 11 digest · 6 state dışı · 8 eşik altı · 2 digest taşması`
  - `bot/heartbeat.py:161-173` heartbeat JSON'da `bar_kapanmadi`, `digest_tasmasi` vb.
- **Eksik:**
  - Panelde (`reporting/panel.py`) huninin detayı yok — sadece `/durum`da var
  - Günlük özet (`notifier/api.py:format_daily_summary`) huniyi göstermiyor
- **Yapılacak:**
  1. `reporting/panel.py` huniyi `panel_raporu` çıktısına ekle (mevcut değilse)
  2. `notifier/api.py:format_daily_summary` kapanış özetine 1 satır ekle: `Filtre: X eşik altı · Y cooldown`

## P2 — Arşiv tabloları doluyor
- **Durum:** Kısmen var
  - `state/formation_mirror.py` 4 tabloyu (f2_formations/snapshots/events/outcome_links) kuyruğa alıp Supabase'e flush ediyor
  - `olcum_tazele.py:arsiv_sagligi()` her gece 4 tabloyu sayıp uyarıyor
  - `supabase_schema.sql` 4 tablo + view var
- **Eksik:**
  - `f2_events`/`f2_outcome_links`/`f2_snapshots` üretimde **0** (denetim 2026-10-25: 1.126 formasyon ama olay 0) — poison batch yüzünden baş batch 3 kez reddedilince düşürülüyor, ama **yeniden deneme yok**
  - `bot/app.py` BIST KAPALI dalında mirror flush yok — gece 02:00 idle'da `olcum_tazele` çalışıyor ama mirror flush yok
  - `olcum_tazele` çıktısı sadece loga gidiyor, `/durum`da görünmüyor
- **Yapılacak:**
  1. `bot/app.py` BIST KAPALI dalına `formation_mirror.flush` ekle (her 5dk uyanışta bir dene, backoff'lu)
  2. `bot/heartbeat.py` heartbeat'e `arsiv_sagligi` sayıları ekle (4 tablo sayısı)
  3. `bot/commands.py` `/durum`da `f2_*` sayıları göster (varsa)

Her adım ayrı commit + `pytest -q` + `test_tarama_zamani.py` ile doğrulanır.
