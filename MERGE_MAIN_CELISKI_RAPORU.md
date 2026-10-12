# main ↔ arena dalı merge çelişki raporu (12 Eki 2026)

Bu dosya `arena/22bb6a24-formation-bot` dalının `main`'e taşınma denemesinin tam
kaydıdır. Merge **main'e alınmadı**; bu commit dalda çözümü ve ölçümü taşır, PR
draft olarak açıktır. Amaç: 81 çelişki hunks'ını yeniden çözmek zorunda kalmadan
devam edilebilmesi.

## 1. Neden otomatik merge yok

İki hat 29 Eyl `0bca8e5d`'de ayrıldı ve o zamandan beri **aynı alt sistemleri ayrı
şekillerde** yeniden yazdı:

| Hat | Tarih aralığı | Kapsam |
|---|---|---|
| `main` (31 commit, squash) | 30 Eyl – 4 Eki | batch 1–8 (açılış kalıcılığı, aday hunisi, TZ, kayıp bildirim digest'i, kaynak/güvenlik, `transport/`+`reporting/`+`state/` katman ayrımı, `analytics/backtest.py`), #11 tz hydrate, #12 tek-seferlik mühür, #13 Türkçe mesaj, #14 **P0 mum kapanış ölçümü**, #16 Faz 1–3 (kalıcı formasyon kimliği, durable mirror, public kanal), #17 komut yolu teşhisi |
| bu dal (16 commit) | 6 – 11 Eki | `domain_engines/`, `zone_scoring.py`, `bist_calendar.py` (exchange-calendars), `secrets_redaction.py`, `notification_outbox.py` + `telegram_alert_flow.py` + `formation_dm_context.py`, OHLCV girdi doğrulaması, fail-closed seans, cache/persistence sertleştirme, PR #18 |

`main` dalın 30 Eyl–4 Eki düzeltmelerini **içermiyor**, dal da `main`'in P0 ölçümünü
ve katman ayrımını **içermiyor**. Kimse kimsenin atası değil.

## 2. Çatallanma (mimari karar, mekanik çelişki değil)

`notifier.py` ve `main.py` içinde aynı sınıfın/akışın iki rakip tasarımı var:

| | dal (11 Eki) | main (4 Eki, canlıda) |
|---|---|---|
| gönderim hattı | `NotificationOutbox`: her olay için `make_id(identity, "dm"/"channel")` + claim/ACK; update ACK'i cevap dayanıklı yazılana kadar bekletilir | `DeferredAlertBuffer` + acil kuyruk + `_gonder()`; 18:45 digest, `uzak_yazma_*` telemetrisi |
| mesaj üretimi | `format_dm_message()` (DM bağlamı `formation_dm_context.py`) | `format_message()` + `reporting/format.py`, `karne.py` |
| public kanal | `send_to_channel(text, idempotency_key=...)` | `_public_pace()`, `PUBLIC_MAX_MESAJ_SAAT/GUN`, bütçe + tempo |
| mükerrer alarm | outbox kimliği (`update_id`/event hash) | tek-seferlik mühür (TTL, TZ ölçekli) |
| seans/takvim | `bist_calendar.py` + `is_bist_open`, yarım gün 13:00, fail-closed | `bist_tatil_adi` statik liste + `tarama_penceresi_acik_mi`, P0 `mum_kapanis_anlari` |

Bunlardan birini seçip diğerinin özelliklerini taşımak gerekiyor; hunk bazlı
birleştirme çalışır görünüp sessizce bozuk bir hibrit üretirdi (alarm yitimi veya
çift alarm).

## 3. Bu commit'te çözülen dosyalar (karar tablosu)

| Dosya | Çözüm |
|---|---|
| `.env.example` | main'in public-kapı bloğu (`PUBLIC_MIN_QUALITY=0`, `PUBLIC_MIN_QUALITY_TF`, `PUBLIC_STATES=KIRILIM_TEYITLI,...`) + dalın `ALLOW_TRUSTED_PICKLE_CACHE=0` satırı |
| `.github/workflows/ci.yml` | dalın pytest adımına eklediği env izolasyonu; main'in "(100 kontrol)" etiketi yerine sayısız başlık (sayı zaten bayatlıyordu) |
| `config.py` | main'in **ölçülmüş** mum-kapanış bloğu + `SESSION_OPEN/SESSION_CLOSE` + `WATCH_STATES`/public/B8 politika yorumları + `_varsayilan_data_dir()`/`SEED_DATA_DIR`; dalın `_resolve_app_path()` ile `LOG_DIR`/`LOCAL_LOG_DIR`/`SEED_DATA_DIR`/`DATA_DIR` sabitlemesi, `LOG_LEVEL` doğrulaması, `ALLOW_TRUSTED_PICKLE_CACHE` |
| `data.py` | kural kaynağı main: P0 `mum_kapanis_anlari`, `tamamlanmis_mumlar`, yarım gün; dalın güvenlik katmanı: `_atomic_write`, `ohlcv_girdi_sorunlari`, `_temiz_1h_cache_kayitlari`, JSON-birincil yükleme, `save_to_disk/save_all` bool+durum raporu. **Birleştirilen** davranış: main'in `_veri_ozeti` içerik-hash UPSERT-atlama + dalın Supabase yazma-hata raporlaması (1H ve 1D); main'in `_okuma_yolu`/SEED yedeği korundu; dalın `mock_fetch_60d_1h`'i kaldığı için `test_ohlcv_guvenligi.py` bunu kullanıyor |
| `deploy_check.py` | main: `/test` anahtarı `X-Test-Key` başlığında (`health_server` query'yi `TELEGRAM_TEST_KEY_QUERY=1` olmadan okumuyor) |
| `telegram_commands.py` | **gerçek union**: main'in teşhis sayaçları (`_sayac`, `durum()`, `_maskele`), bayat-komut kapısı, grup politikası, meşguliyet bilgi mesajı + dalın fail-closed backlog döngüsü, outbox `response_sender`/`response_exists` kancaları, `_pending_reply` ACK kapısı, log redaksiyonu. `update_waiting_for_delivery()` eklendi; `main.py`'den gelen eski çağrılar parametre vermeyince main davranışıyla birebir aynı kalır |
| `test_deploy_check.py`, `test_son_tarama_kaliciligi.py` | iki tarafın EOF'a eklediği testlerin birleşimi (hiçbir test atılmadı) |
| `test_telegram_webhook.py` | main'ın sırsız `/webhook` adresi + dalın `delete_cagrilari == []` güvencesi |
| `test_tarama_zamani.py` | main'ın P0 beklentileri (2h/4h 17:30, yarım gün 13:00, kısmi bar kapısı) + dalın import/test-izolasyonu |
| `notifier.py`, `main.py` | **main'in canlı mimarisi** (bkz. §2; bilinçli erteleme, §5) |

## 4. Ölçüm (pytest, Python 3.11 + requirements.txt, CI ile aynı env)

| Ağaç | Sonuç |
|---|---|
| `main` @ `11648bc` | 704 passed, **3 failed** (`test_mum_kapanis_penceresi` ×2, `test_karne` ×1 — tarihe bağlı, main'de de kırmızı) |
| dal @ `c8862cf` | 457 passed, **1 failed** (`test_son_tarama_kaliciligi::test_restart_panel_...`), 2 skipped |
| bu merge | 841 passed, **111 failed** (yerel saatli 3 + 1 önceden var olan hariç) |

Kırmızılar dökümü:

- **93** → dalın YALNIZCA-dalda-olan test dosyaları, reddedilen mimariyi assert ediyor:
  `test_telegram_notification_delivery.py` 23, `test_bist_calendar_regressions.py` 18,
  `test_dm_mesaj_kalitesi.py` 15, `test_live_data_flow.py` 13,
  `test_formation_dm_context.py` 8, `test_takvim_politikasi.py` 4,
  `test_domain_integration_regressions.py` 4, `test_secrets_redaction.py` 3,
  `test_persistence_safety.py` 2, `test_ohlcv_guvenligi.py` 2, `test_domain_engines.py` 1
- **14** → her iki tarafta da olan dosyalar; **gerçek merge işi**:
  `test_telegram_webhook.py` 6, `test_son_tarama_kaliciligi.py` 4,
  `test_telegram_alert_flow.py` 2, `test_telegram_commands.py` 1, `test_supabase_integration.py` 1
- **4** → yalnız-main dosyası `test_kaynak_ve_guvenlik.py`; `data.py` kararlarımın
  main davranışına dokunduğu yerler — **PR-A'da mutlaka sıfırlanmalı**

## 5. Önerilen aşamalı plan

**PR-A (güvenli dilim, main'e alınabilir):** `main`'in `notifier.py`/`main.py`'si
olduğu gibi kalır; buna ek olarak dalın çatallanmasız parçaları girer —
`domain_engines/`, `zone_scoring.py`, `run_directional_zone_replay.py`,
`directional_zone_replay.py`, `bist_calendar.py`, `secrets_redaction.py`, §3'teki
`config.py`/`data.py`/`deploy_check.py`/CI çözümleri ve bunların testleri.
Kabul kapısı: `test_kaynak_ve_guvenlik.py` + §4'ün "her iki taraf" grubu sıfır
olmalı; dalın outbox-kuyruk modülleri (`notification_outbox.py`,
`telegram_alert_flow.py`, `formation_dm_context.py`) ve 93 kırmızı testi bu PR'a
girmez (PR-B'nin konusu).

**PR-B (alarm hattı kararı):** §2'den tek tasarım seçilir ve diğerinin özellikleri
taşınır. Öneri: **outbox'ı teslim defteri olarak alta, main'in digest/public-pace
politikalarını üste koymak** (hem "kayıp bildirim yok" hem "aynı alarm iki kez yok"
amacını karşılar); daha küçük iş istenirse main'in hattı sabit kalır, outbox yalnız
komut cevaplarına (`response_sender`) bağlanır.

**PR-C (takvim sözleşmesi):** `bist_calendar` (exchange-calendars, fail-closed) ile
main'in `bist_tatil_adi` statik listesi tek kaynağa indirilir; `is_bist_open` /
`tarama_penceresi_acik_mi` / `time_until_next_open` ve P0 `mum_kapanis_anlari`
üzerindeki `test_takvim_politikasi.py`, `test_bist_calendar_regressions.py`,
`test_tarama_zamani.py`, `test_mum_kapanis_penceresi.py` beklentileri uzlaştırılır.

## 6. Bu çözümü yeniden üretmek

```bash
git checkout arena/22bb6a24-formation-bot
git config merge.conflictStyle zdiff3
git merge --no-commit --no-ff origin/main     # 12 dosyada conflict
# §3 tablosundaki kararları uygula, sonra:
python -m pytest -q                            # hedef: yalnız 3 önceden-kırmızı
python test_tarama_zamani.py                   # CI parity
```
