# Deploy + bildirim uçtan uca denetimi — 2026-11-18

> **Durum:** Kayıt / güncel denetim. Bu dosya, önceki
> [tam TV + Yahoo deploy yolu](DEPLOY_HAZIRLIK_2026-11-18.md) üzerine gelen
> *"deploy sürecini her türlü baştan sona incele, sorunları düzelt, bildirim
> gönderme sürecini de incele"* isteğinin kod, test ve doküman karşılığıdır.
> **Fiili Render deploy / PR yapılmadı; gerçek Telegram, TradingView, Yahoo veya
> Supabase çağrısı yapılmadı.**

## 0. Kapsam ve yöntem

| Katman | İncelenen yüzey |
|---|---|
| Build / start / pinler | `.python-version` (3.12), `scripts/install_deploy_dependencies.sh`, `requirements-deploy.txt`, `setup.sh`, `render.yaml`, CI kurulum adımı, `pip check` |
| Runtime env | Telegram token/DM/public hedefleri, webhook auto secret, `PORT`, `TZ`, `DATA_DIR`, `LOG_DIR`, `LOCAL_LOG_DIR`, TV/Yahoo bayrakları, Supabase read-only ve teslim yedeği |
| HTTP | `/health`, `/ready`, `?strict=1`, `?ka=...`, `/test`, kapalı `/webhook`, IP limiti, commit/branch alanları |
| Komut yolu | polling ↔ webhook seçimi, `setWebhook` başarısızlığında eski webhook'u silip polling'e düşme, webhook işleyicisinin 503/500/200 sözleşmesi, public grup yönetici kapısı |
| Veri / tarama | Yahoo birincil → TV reaktif yedek → fail-closed `None`, gerçek 4s, kaynak sayaçları, 20s/25s kapıları, veri-yok/cache/STRICT_UNKNOWN, `/health.veri_saglayicilari` |
| Supabase | `SupabaseStore.from_env(read_only=True)`, mirror writes kapalı, uzak cache/state okuması, bekleyen teslim/mühür/acil kuyrukların restart davranışı |
| Bildirim | DM kalıcı FIFO, public ana bülten kuyruğu, public/DM özel kuyruklar, public hedef inceleme arşivi, alarm/grafik/bülten, kapanış özeti ve flush pencereleri |
| Gözlemlenebilirlik | `/health.bildirim`, `/durum` sayaçları, doktor çıktısı, CI smoke doğrulaması |

Yöntem: depo içi statik okuma, ağsız pytest/regresyon, gerçek entrypoint ile yerel HTTP
smoke, çevrimdışı doktor/grafik seed. Bağlı uygulamalar (`google_docs`, `google_drive`,
`notion`, `supabase`) kapalı olduğu için hiçbir connector kullanılmadı; gerçek Render
kontrol paneli veya canlı servis sorgulanmadı.

## 1. Bulunan somut sorunlar ve uygulanan düzeltmeler

| # | Sorun | Etki | Düzeltme |
|---|---|---|---|
| 1 | `deploy_check.kontrol_env` TV bayraklarını, `PORT`, `TZ`, `DATA_DIR`, `LOG_DIR`, `LOCAL_LOG_DIR` ve `SUPABASE_DELIVERY_WRITES`'i listelemiyordu | Operatör doğru kurulumu doktorda göremiyor, TV/Yahoo parity el ile kontrol ediliyordu | Tüm runtime/TV/depolama env'leri opsiyonel satırlara eklendi; `TV_BAR_SAYISI` ve `TV_ZAMAN_ASIMI_SN` dahil |
| 2 | Doktor `TELEGRAM_CHAT_ID`'yi koşulsuz zorunlu sayıyor, özette eski `TELEGRAM_CHANNEL_ID`'yi yok sayıyordu | Geçerli **public-only** deploy yanlış HATA veriyor; yalnız kanal hedefi olan kurulum "hedef yok" sanılıyordu | Token + (DM **veya** public hedef) kuralı; `TELEGRAM_CHANNEL_ID` yedek hedef olarak `degerler` ve özete eklendi; public-only satırı `OK` |
| 3 | `kontrol_telegram` / `kontrol_grafik` `--send-test-message` için yalnızca DM `chat_id` istiyordu | Public-only kurulumda gerçek test mesajı/fotoğrafı hiç sınanmıyor, "chat_id/token yok" FAIL basılıyordu | Public hedefe fallback; test `sendMessage`/`sendPhoto` doğru hedefe gider, sır redaksiyonu public hedefi de kapsar |
| 4 | "Yeni durum Supabase'e yedeklenmez" uyarısı Supabase hiç yokken de koşulsuz basılıyordu | Gürültülü/yanıltıcı doktor çıktısı | Uyarı yalnızca Supabase tanımlıysa; `SUPABASE_DELIVERY_WRITES=1` ise "yalnız teslim kuyruğu yedeklenir" ayrımı; özet satırı da ayrıştırıldı |
| 5 | `bot/app.py` read-only store + `TelegramNotifier(persistent_store=None)` nedeniyle `DeliveryOutbox.save()` uzak yedek yazmıyordu | Render ephemeral diski silinirse bekleyen DM metni + albüm kuyruğu kaybolabiliyordu | **Opt-in** `SUPABASE_DELIVERY_WRITES=1`: ayrı `SupabaseStore(read_only=False)` + `DeliveryOnlyStore` dar fasadı; **yalnız** `state:notification_delivery` okunur/yazılır. Varsayılan `0` = hiçbir uzak yazı yok; genel store read_only kalır, mirror/coklu-ornek yazımları açılmaz |
| 6 | Public ana bülten kuyruğu yalnızca `scan_all_stocks()` sonunda `_public_turu_kapat()` ile boşaltılıyordu | Tarama çökmesi, Telegram ağ hatası veya restart sonrası onaylı public olaylar bir sonraki taramaya kadar bekliyordu | `_public_bulten_bosalt()` ana döngüde periyodik (60 sn) çağrılıyor; `public_enabled` kapısı, iş günü + seans başlangıcı + 18:43 kesimi, shutdown ve tek-işçi `public_bosalt` kilidi korunur. DM kapalı olsa da public-only çalışır |
| 7 | `/health.bildirim` yalnızca `enabled`, `teslim_kuyrugu`, `acil_kuyruk`, son başarı/hata taşıyordu | "HTTP 200 ama gruba hiç mesaj gitmiyor" durumu dışarıdan görünmüyordu; public sayaçları ve inceleme kuyrukları gizliydi | `_bildirim_sagligi()`: `mod`, `durum`, `nedenler`, `public_enabled`, public ana/özel/DM özel kuyrukları, hedef inceleme arşivi, grafik kuyruğu, `son_public_gonderim`, `uzak_yedek`. Token/chat_id **yok**. `/health` yine her koşulda 200; `?strict=1` heartbeat sözleşmesi değişmedi |
| 8 | Render varsayılan 30 sn shutdown, cache/heartbeat/kuyruk kayıtlarını kesebilirdi | SIGTERM'de son `save_all`, digest tamponu ve heartbeat yazımı yarım kalabilirdi | Blueprint'e `maxShutdownDelaySeconds: 120`; mevcut Dashboard servisi için rehbere "elle doğrula" satırı |
| 9 | CI HTTP smoke'u yeni bildirim JSON alanını doğrulamıyordu | `/health` alanı sessizce düşerse CI yeşil kalırdı | Smoke `bildirim.durum` + `nedenler` alanlarını `python -c` ile assert eder; test fake curl gövdesi de güncellendi |
| 10 | `test_gonderim_sagligi.py` global `daily_stats`'i geri almadan değiştiriyordu | Dosya sırasına bağlı olarak `test_kaynak_ve_guvenlik.py::test_main_panel_adaptoru_ayni_metni_uretir` yanlış "Huni" satırıyla kırılıyordu | Test `monkeypatch.setattr(..., copy.deepcopy(daily_stats))` ile izole edildi |

### Değişmeden doğrulanan sözleşmeler

* `config.telegram_webhook_runtime_secret()` explicit secret yoksa `PORT` + public URL +
  token + auto açıkken HMAC ile stabil secret üretir; `transport/telegram.py` setWebhook
  başarısız olursa eski webhook'u silip polling'e düşer.
* `bot/commands._telegram_webhook_isle`: processor yoksa/shutdown 503, cevap bekliyorsa
  503, işleyici hatasında 500, başarıda 200.
* `health_server`: sorgusuz `/health` 200; `/ready` startup tamamlanmadan 503;
  `?strict=1` yalnızca `heartbeat_stale=true` iken 503; `/test` ve secret'sız
  `/webhook` 404.
* Yahoo birincil, TV reaktif yedek, native 4s, `STRICT_UNKNOWN`, veri-yok/cache/stale
  kapıları ve `/health.veri_saglayicilari` önceki turdaki gibi korunur.
* `DeliveryOutbox.flush()` FIFO, metin öncesi görsel hazırlığı, `retry_at +30s`,
  3 hazırlık hatasında karesiz devam, duplicate/story/public marker kapıları korunur.

## 2. Yeni dosya / env sözleşmesi

| Yol / anahtar | Anlamı |
|---|---|
| `notification_delivery.DeliveryOnlyStore` | Yalnız `KEY = state:notification_delivery` için `get()` / `upsert()`; başka anahtarı reddeder, read-only store'u yazma iznine zorlamaz |
| `config.supabase_delivery_writes_enabled()` | `_env_bayrak("SUPABASE_DELIVERY_WRITES", "0")`; varsayılan kapalı |
| `TelegramNotifier(remote_delivery_store=...)` | Opsiyonel dar yazıcı; verilmezse eski `persistent_store`/yalnız yerel davranış |
| `bot.summary._public_bulten_bosalt()` | Tarama dışı public ana kuyruk flush; `(adet, yeni_son_deneme)` döner |
| `bot.commands._bildirim_sagligi()` | `/health` için sır içermeyen bildirim özeti |
| `test_deploy_bildirim_denetimi.py` | 16 yeni ağsız regresyon |
| `render.yaml` / `.env.example` | `SUPABASE_DELIVERY_WRITES=0`, `maxShutdownDelaySeconds: 120` |
| `.github/workflows/ci.yml` | `/health` smoke içinde `bildirim` JSON assert |

**Kalıcılık sınırı:** `SUPABASE_DELIVERY_WRITES=1` yalnız bekleyen **DM teslim FIFO**'nu
uzak yedekler. Public ana bülten, public/DM özel kuyruklar, public hedef inceleme
arşivi, yeni OHLCV cache, karne ve Telegram limit sayaçları hâlâ yerel `DATA_DIR`'dedir.
Render Free'de bu disk geçicidir; tam kalıcılık için ayrı disk + `DATA_DIR` gerekir.
Telegram'da idempotency key olmadığı için uzak yedek "en az bir kez" teslim
sözleşmesini değiştirmez; belirsiz timeout/5xx yine operatör incelemesine düşer.

## 3. Koşulan kapılar (yerel, 2026-11-18)

| Kapı | Sonuç |
|---|---|
| `.venv/bin/ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pip check` | `No broken requirements found.` |
| `compileall -q .`, `git diff --check` | temiz |
| Hedefli 12 dosya | **327 passed** |
| Tam pytest | **4557 passed, 43 skipped in 703.26s (0:11:43)** |
| `python -m data` + offline `tanis` + `arsiv` | geçti, canlı sağlayıcı çağrısı yok |
| `test_tarama_zamani.py` | `SONUÇ: TÜM KONTROLLER GEÇTİ (102/102)` |
| 4 bağımsız formasyon scripti | `test_triangle`, `test_breakout`, `test_flag`, `test_pennant` geçti |
| `deploy_check.py --skip-network --grafik-test` | **53 tamam · 5 uyarı · 0 hata**; `Kare üretildi: AKBNK 4h · 68 mum · 74.9 KB · 517.8 ms`, `Stabil direnç bu karede çizildi`, `Fotoğraf gönderilmedi` |
| Gerçek entrypoint HTTP smoke (`BOT_HEALTH_SMOKE_ONLY=1`, `PORT=10013`) | `/health 200` + `bildirim.durum=bilinmiyor` + `nedenler` listesi, `/ready 503`, `/health?ka=1 200`, `/test 404`, kapalı webhook, "Health smoke mode" logu |
| CI | push sonrası `gh run watch` ile bu tabloya eklenecek |

Doktor uyarıları bilinçlidir: smoke env'inde token/Supabase boş, ağ kontrolleri
`--skip-network` ile atlandı. `0 hata` canlı erişim kanıtı değildir.

## 4. Operatör adımları (PowerShell, `PS C:\Projeler\Formation-Bot>`)

```powershell
git fetch origin
git switch arena/79b4d2e1-formation-bot
git pull --ff-only origin arena/79b4d2e1-formation-bot
$py = ".\.venv\Scripts\python.exe"; if (-not (Test-Path $py)) { $py = "python" }
& $py -m pip install -r .\requirements-deploy.txt
& $py -m pip check
& $py -m pytest -q test_deploy_bildirim_denetimi.py test_deploy_check.py test_supabase_read_only_mode.py test_notification_delivery.py test_public_grup.py test_health_server.py
& $py -m ruff check .
& $py -m compileall -q .
New-Item -ItemType Directory -Force .\var | Out-Null
& $py deploy_check.py --skip-network --grafik-test
```

Public-only canlı kontrol (DM `chat_id` boş; **gerçek bir mesaj gönderir**):

```powershell
$env:TELEGRAM_BOT_TOKEN="<token>"
$env:TELEGRAM_CHAT_ID=""
$env:TELEGRAM_GROUP_ID="<@kanal_adi veya -100...>"
& $py deploy_check.py --url https://<servis>.onrender.com --send-test-message
```

Ayrı terminalde yerel liveness:

```powershell
$env:PORT="10000"; $env:BOT_HEALTH_SMOKE_ONLY="1"; & $py main.py
```

Render Dashboard'da (Blueprint zaten yönetilen bir servise uygulanmıyorsa):
`Max Shutdown Delay = 120 s`, `Health Check Path = /health`, `Auto-Deploy =
After CI Checks Pass`. `SUPABASE_DELIVERY_WRITES=1` **yalnızca** service_role yazma
izni ve tek bot örneği doğrulandıktan sonra açılmalıdır; varsayılan `0` tam salt
okunur moddur.

## 5. Dürüst kanıt sınırı

* Bu çalışma kod/doküman/test/commit-push ile sınırlıdır; **Render'a fiilen deploy
  edilmedi**, PR açılmadı. `autoDeployTrigger: checksPass` yalnızca Blueprint ile
  yönetilen servis için tetiklenir.
* Ajan tarafında canlı Yahoo / TradingView WebSocket / Telegram / Supabase çağrısı yok.
  `SUPABASE_DELIVERY_WRITES=1` yolu sahte store ve ağsız testlerle doğrulandı; gerçek
  tabloya yazım operatör tarafından sınanmalıdır.
* Supabase uygulaması bu oturumda kapalı; connector üzerinden doğrulama yapılmadı.
  Gerçek tablo/izin kontrolü istenirse ilgili uygulamanın açılması gerekir.
* `/health.bildirim.durum=inceleme` kuyruk/manuel inceleme işaretidir; Telegram
  tesliminin başarılı olduğunu kanıtlamaz. Sorgusuz `/health` her zaman 200'dür.
* `Yeşil` önceki turda operatör ölçüm kapısı beyanıdır; bu dosyadaki `4557 passed`
  sonucu ajanın yerel test kanıtıdır, canlı veri/teslim kanıtı değildir.
