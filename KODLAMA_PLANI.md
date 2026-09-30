# Formation-Bot — Toplu Kodlama Planı

> Bu dosya **çalışma planıdır** ve repo içinde yaşar. Teşhis: `SORUN_RAPORU.md`,
> yapılacaklar listesi: `YAPILACAKLAR.md`.
> Kural: her batch = **tek commit + push** (`arena/01a0f318-formation-bot`),
> testler yeşil olmadan push yok, **main'e merge yalnız kullanıcı onayıyla**.

## Çalışma kuralları (her batch için)
1. Batch başında `git status` temiz + `python -m pytest -q` ve `python test_tarama_zamani.py` yeşil.
2. Kod + test aynı commit'te. Yeni davranış için en az bir **regresyon testi**.
3. Batch sonunda: `pytest` + `test_tarama_zamani.py` yeniden koşar, `git status` temiz, `bot_data/` değişmemiş.
4. Commit mesajı: `fix(batch-N): ...` / `feat(batch-N): ...` + gövdede ölçüm.
5. Merge yok. Push var.

---

## DURUM

| Batch | Kapsam | Durum |
|---|---|---|
| **B1** | A1 (kalıcılık çağrısı) + A2 (tatil/yarım gün döngüsü) + 11 test | ✅ tamamlandı `e9a736f` (`fix(batch-1)`) — pytest 200, test_tarama_zamani 100/100 |
| **B2** | A3 ölü kod + A9 metrik + C6 doküman + B2 digest şeffaflığı | ✅ tamamlandı `6dca717` (`fix(batch-2)`) — pytest 213, test_tarama_zamani 100/100 |
| **B3** | B1 bastırılan aday sayacı + B6 eşik altı + A10 kap sayacı | ✅ tamamlandı `401a788` (`feat(batch-3)`) — pytest 224, test_tarama_zamani 100/100 |
| **B4** | A4 TZ + A5 kirp/retry + A6 gönderim sağlığı | ✅ tamamlandı `fix(batch-4)` — pytest 235, test_tarama_zamani 100/100 |
| **B5** | B3 kalıcı digest + B4 engellenen acil kuyruğu | ✅ tamamlandı `0ba343e` (`feat(batch-5)`) — pytest 250, test_tarama_zamani 100/100 |
| **B6** | B5 yazma amplikasyonu + A7 sır/rate limit + A8 pickle + B10 çoklu örnek | ✅ tamamlandı `fix(batch-6)` — pytest 267, test_tarama_zamani 100/100 |
| **B7** | C1 sabitler + C3 namespace + C4 DATA_DIR + C7 ölü araçlar | ✅ tamamlandı `a738ec4` (`fix(batch-7)`) — pytest 271, test_tarama_zamani 100/100 |
| **B8** | C2 `main.py` katmanlara ayırma (yapısal, dallanmış iş) | ⏳ sırada |

---

## BATCH 1 — ✅ Tamamlandı (bu commit)

**A1 — Kalıcılık çağrısı geri kondu**
- `main.py` `main_loop`: `supabase_store.ping()`'ten sonra `son_tarama_yukle(supabase_store)`.
- Neden: fonksiyon + `LiveState.hydrate` + testleri vardı, çağrı düşmüştü → yazılıyor, okunmuyordu.
- Test: `test_son_tarama_kaliciligi.py::test_acilista_son_tarama_yukle_cagriliyor` (AST ile `main_loop`
  gövdesinde çağrı arar; mutasyonla doğrulandı: çağrı silinince test **kırmızı**).

**A2 — Tatil/yarım gün sonsuz döngüsü**
- `data.py`: yeni `sonraki_islem_gunu()`; `time_until_next_open()` tatil/hafta sonu atlar ve
  pencere kapalıyken **her zaman > 0** döner (sözleşme docstring'de).
- `main.py`: kapalı dalda `sleep_time = max(sleep_time, 60.0)` (ikinci güvenlik ağı).
- Ölçüm: 29.10.2026 12:00 → bekleme **0.0 → 20.8 saat**, döngü uykusu **0 → 5 dk** (önce ~21.500 log satırı/sn).
- Test: `test_tarama_zamani.py` §11 — 10 yeni kontrol (tatil, yarım gün, hafta sonu, sözleşme invaryantı),
  toplam **100/100**.

## BATCH 2 — Görünürlük ve ölü kod (davranış değişikliği yok, düşük risk)

| İş | Dosya | Detay | Test |
|---|---|---|---|
| A3b | `main.py:~2147` | `_live_state.get_formations()` → `formations()` (metot yok, sessizce yanlış kaynak) | özet ile `/panel` aynı kaynaktan mı? |
| A3c | `main.py:~2166` | `'contraction': None` → gerçek değer (A3b düzelince sıkışanlar bölümü boşalmasın) | `format_daily_summary` sıkışan sayısı > 0 senaryosu |
| A3a | `notifier.py:211-221` | Kanala sıkışma dalı: `False` dönen ölü dal → karar: kuralı yaz ya da sil | `should_send_to_public` tablo testi |
| A3d | `notifier.py:255` | Kullanılmayan `[:10]` → ya kullan ya kaldır | — |
| A3e | `notifier.py:582` | `FORMASYON_GECERSIZ` şablonunu bağla (kritik değil, özet/ihtiyaç halinde) | mesaj biçimi testi |
| **B2** | `main.py:2104,1937,2397`, `config.py` | Digest başlığı `(12/21 gösteriliyor)` + `… N aday daha (tam liste: /formasyonlar)`; `limit=12` → `DEFERRED_DIGEST_LIMIT` env | 20 kayıt → 12 gösterim + 8 "daha" satırı |
| A9 | `main.py:1848` | `patterns_found` → benzersiz `(hisse|TF)` sayacı (ya da metni "slot kaydı") | aynı slot 2 kez taranınca sayaç 1 |
| C6 | `README.md`, `supabase_schema.sql` | Test sayıları (100/100, 199+), dal adı, `state:son_tarama` anahtarı | — |

**Kabul:** davranış değişikliği yok (mesaj içerikleri hariç), tüm testler yeşil, `/panel` çıktısı aynı kaynaktan.

## BATCH 3 — "Kaç tanesini kullanmadım" sayacı (ana istek)

| İş | Dosya | Detay |
|---|---|---|
| B1 | `main.py` (`daily_stats`, `_komut_durum`) | `alerts_below_threshold / alerts_cooldown / alerts_cap_blocked / alerts_digest_overflow / alerts_state_disabled` sayaçları; `/durum`'a `Bugün: 21 aday · 4 push · 11 digest · 6 kapsam dışı · 0 cooldown · 3 eşik altı` |
| B6 | `main.py:1892` | Eşik altı kayıt: `debug` → sayılır + `/panel`'de `eşik altı N aday` satırı |
| A10 | `notifier.py:294-301` | Kap sayacı tüm gönderim yollarından geçsin (komut/özet/digest dahil) |

**Kabul:** aynı taramada üretilen 21 kaydın akıbeti tek satırda görünür; hiçbir kayıt "iz bırakmadan" düşmez.

## BATCH 4 — Operasyonel sağlık

| İş | Dosya | Detay |
|---|---|---|
| A4 | `notifier.py:144,294-330,370-393` + `render.yaml` | Cooldown/kap sayaçları `ISTANBUL_TZ`; Render'a `TZ=Europe/Istanbul` |
| A5 | `notifier.py:176-191` | `send_text` → `kirp()` + sınırlı retry + log |
| A6 | `main.py:311-354` | Heartbeat: `notifier_enabled`, `son_basarili_gonderim`, `son_gonderme_hatasi`, `bekleyen_bildirim`; `alerts_attempted/failed` |

**Kabul:** token yanlışken heartbeat "gönderim yok" der; 03:00 sıfırlaması biter; uzun mesaj sessiz düşmez.

## BATCH 5 — Kayıp bildirimleri sıfıra indirme

| İş | Dosya | Detay |
|---|---|---|
| B3 | `telegram_alert_flow.py`, `supabase_store` | Digest tamponu kalıcı (`state:digest_pending`), kaçırılan 18:45 telafisi |
| B4 | `notifier.py:370-393` | Cooldown/kap engeline takılan **acil** olaylar kuyruğa girer, kap açılınca gider; kuyruk derinliği heartbeat'te |

**Kabul:** restart/uçuşta bekleyen aday kaybolmaz; engellenen acil olay 1 saat içinde gider.

## BATCH 6 — Kaynak ve güvenlik

| İş | Dosya | Detay |
|---|---|---|
| B5 | `data.py:499-538,727-737`, `main.py:311-354` | Tur sonunda batch yazım / ayrı thread; heartbeat dedupe (~4 MB/tarama → ~0,5 MB) |
| A7 | `health_server.py:33,88` | Sır URL yolundan kalksın (başlık doğrulaması zaten var) + basit rate limit |
| A8 | `bot_data/*.pkl`, `data.py:549` | `.pkl` git'ten çıkar veya okuma JSON'a sabitlenir |
| B10 | `supabase_store.py:107` | Anahtarlara örnek namespace'i; webhook modunda tekil örnek kontrolü |

## BATCH 7 — ✅ Tamamlandı (şablon hazırlığı)

| İş | Dosya | Detay |
|---|---|---|
| C1 | `data.py`, `config.py` | `.IS` eki, seans/tatil/evren/`LOG_DIR` → config; `MARKET_SUFFIX`, `SESSION_*` isimleri |
| C3 | `data.py:534`, `supabase_store.py:107` | `STORE_PREFIX` (örn. `formation-bot:`) |
| C4 | `config.py`, `.gitignore` | `DATA_DIR` repo dışı varsayılan |
| C7 | — | `fetch_with_rate_limit`, `mock_fetch_60d_1h`, `repo_teshis.py`, `logrotate.conf`, `.ps1` temizliği |

**Ne yapıldı:**

- **C1 — sabitler config'e:** `MARKET_SUFFIX` (env, `.IS`; `data.py` iki `yf.Ticker` çağrısı bu eki kullanır),
  `STOCK_UNIVERSE` (env, boşsa BIST 50), `SESSION_OPEN`/`SESSION_CLOSE` adları (`BIST_OPEN`/`BIST_CLOSE`
  alias'ı; yeni kod okur), `LOG_DIR` env; 2027 resmi tatil takvimi eklendi (11 tam gün; 8 Mart ve
  28 Ekim yarım gün — 3 kaynakla doğrulandı).
- **C3 — Supabase ön eki:** `SupabaseStore.VARSAYILAN_PREFIX = "formation-bot:"`; env
  `SUPABASE_STORE_PREFIX` (boş/`off` = öneksiz eski davranış). Okuma iki turlu: önce ön ekli,
  bulunamayanlar için eski (öneksiz) anahtarlar → mevcut veri kaybolmaz, sonraki yazımda taşınır.
  Çağıranlar öneksiz ad kullanmaya devam eder.
- **C4 — veri dizini repo dışı:** `DATA_DIR` env → yoksa `RENDER` ortamı `/tmp/formation-bot-data`,
  `/var/lib/formation-bot/data`, `~/.formation-bot/data` (makedirs + W_OK denemesi), son çare `./bot_data`.
  `SEED_DATA_DIR` (varsayılan `./bot_data`) **yalnız okuma** yedeği: `StockDequeManager._okuma_yolu()`
  DATA_DIR'de dosya yoksa seed'e bakar, yazım her zaman DATA_DIR'e gider. `notifier` cooldown/kap
  dosyaları da DATA_DIR köküne taşındı; testler artık `~/.formation-bot` altına kalıcı durum yazmaz
  (`conftest.py` autouse fixture).
- **C7 — ölü araç temizliği:** `fetch_with_rate_limit` + `RATE_LIMIT_MIN/MAX` silindi;
  `mock_fetch_60d_1h` ve `python data.py` mock demosu kaldırıldı (yerine çevrimdışı duman testi);
  `repo_teshis.py`, `logrotate.conf`, `setup.ps1`, `local_test.ps1` git'ten çıkarıldı;
  `LOCAL_SETUP.md` güncellendi (ölü referanslar, eski dal adı, `patterns/` paket yapısı).
- Dokümanlar: `.env.example`, `render.yaml`, `RENDER_DEPLOY.md` env tablosu ve `README.md`
  Batch 7 satırı; `TESHIS_RAPORU.md`'ye aracın kaldırıldığına dair not.

## BATCH 8 — `main.py` katmanlara ayırma (yapısal)

Hedef mimari: `patterns/` (motor, **zaten bağımsız**) · `orchestration/` (tarama+zamanlama) ·
`reporting/` (panel/digest/özet metinleri) · `transport/` (telegram, supabase, health) · `state/`.
Yöntem: dosya taşıma değil **kademeli**: önce `reporting/` (saf fonksiyonlar) çıkarılır, `main.py` ince
orchestrator'a iner; `import main` yan etkileri (logger ele geçirme, `/var/log` yazma) kaldırılır.
Her adım ayrı commit; davranış değişmez, yalnız taşıma.

**İlerleme (kademeli, her adım ayrı commit):**

| Adım | Kapsam | Durum |
|---|---|---|
| 8.1 | `reporting/format.py`: saf metin/sayı üretimi (panel, digest özeti, yaş metni, filtreleme) main'den ayrıldı; main'de alias'larla geriye dönük uyum | ✅ `bd6214f` |
| 8.2 | `import main` yan etkileri (logger ele geçirme, `/var/log`-`./logs` yazımı) kaldırıldı; kurulum `main_loop()`/girişe taşındı | ✅ `8fd8028` |
| 8.3 | `reporting/panel.py`: `panel_raporu` artık durumu parametre alır; `main._panel_raporu` ince adaptör (bu commit) | ✅ |
| 8.4 | `state/`: kalıcılık yardımcıları (son tarama, digest tamponu) main'den ayrılır | ⏳ |
| 8.5 | `transport/`: telegram/webhook kurulumu main'den ayrılır; main ince orkestratör | ⏳ |

---

## Riskli/karar bekleyen işler
- **B7 (WATCH state politikası):** bu dal 3 state'i topluya çevirdi, `main` anlık atıyor. Karar + tek
  yerde tanım + README notu + test gerekir. Karar senin.
- **B9 (kanal akışı):** hangi state'ler public kanala gitsin.
- **B8 (evren büyütme):** pacing/panel/digest limitleri — evren 48'den büyükse önce bu batch.

## Bağımlılık sırası
`B1 ✅ → B2 → B3 → B4 → B5 → B6 → B7 → B8`
(B3'ün B1'e bağımlılığı yok; B5, B4'ten sonra anlamlı — kuyruk, sağlıklı gönderim varsayar.)
