# Formation-Bot — BIST Formasyon Radarı

> ARGENT v0.4.6 Pine Script'in Python portu. BIST hisselerinde üçgen/kema/bayrak/flama
> formasyonlarını tespit eder, state makinesiyle takip eder ve Telegram'dan bildirir.
> Pine ile **birebir** uyum hedefi; her reddedilme sebebi Türkçe loglanır (explainable).

## Hızlı başlangıç

```bash
python3 -m pip install -r requirements.txt   # pandas, numpy, pytz, yfinance
cp .env.example .env                         # TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
python3 main.py                              # canlı bot (heartbeat + SIGTERM destekli)
python3 canli_tarama.py                      # Aktif evren (48 sembol) x 4 TF canlı tarama raporu
python3 canli_tarama.py --cache              # internet yok: bot_data cache ile tarar
python3 test_tarama_zamani.py                # Faz 1+2 regresyon (90 kontrol)
python3 test_pennant.py                      # flama regresyon (6 test)
```

Profil seçimi: `.env` içinde `BOT_PROFILE=Dengeli` (Hassas / Dengeli / Seçici).

## Tarama temposu

Canlı bot `BIST_50` listesindeki **48 sembolü** tarar; Yahoo'da sorunlu KOZAL ve KOZAA
şimdilik çıkarılmıştır. Eksik iki bileşen için veri sağlayıcısı doğrulaması sonrası
sembol eklenmelidir. Boş/kısa veya 5 günden eski cache için 60 günlük 1H geçmişi;
sağlıklı cache'in rutin güncellemesinde yalnızca son 5 gün indirilir ve timestamp'e
göre tekilleştirilerek eklenir. Yahoo istekleri paralel değil, seri yürütülür: en çok
10 HTTP isteğinden sonra 10–15 sn mola; istekler arasında 0,9–1,5 sn rastgele aralık.
Yalnızca geçici ağ/rate-limit hataları için tüm ilk tur bittikten sonra 30–60 sn
beklenip tek bir retry yapılır. Boş/404 veya desteklenmeyen semboller retry edilmez.
Aynı pacing ilk 1H/1D cache yüklemesinde de uygulanır.
Günlük seri, intraday güncelleme gelmediyse 6 saat dolmadan tekrar istenmez; kapanıştan
sonra aynı gün içi kısmi barı tamamlamak için bir kez daha yenilenir.

Ayarlar `.env` üzerinden değiştirilebilir: `SCAN_REQUEST_BATCH_SIZE`,
`SCAN_REQUEST_DELAY_MIN_SEC`, `SCAN_REQUEST_DELAY_MAX_SEC`,
`SCAN_BATCH_PAUSE_MIN_SEC`, `SCAN_BATCH_PAUSE_MAX_SEC`,
`SCAN_RETRY_BACKOFF_MIN_SEC`, `SCAN_RETRY_BACKOFF_MAX_SEC`.
BIST 50 bileşenleri endeks değişikliklerinde `config.py` içindeki listeyle birlikte
elle güncellenmelidir.

### Mum kapanış kuralı (bildirim ancak mum KAPANDIKTAN sonra)

`tamamlanmis_mumlar()` (data.py) motoru yalnız kapanmış mumlarla besler; kural tek
kaynaktan (`mum_kapanis_anlari`) yönetilir:

| TF | Kapanış anı |
|---|---|
| 1h | etiket + 1 saat (17:30 etiketli günün son barı 18:00'de) |
| 2h | etiket + 2 saat; günün son kovası (17:30) seans sonunda, 18:00'de |
| 4h | etiket + 4 saat; günün son kovası (17:30) seans sonunda, 18:00'de |
| 1d | o günün seans kapanışı (normal 18:30, yarım günde 13:00) |

Kapanmamış bar hiçbir koşulda bildirime kaynak olmaz: tarama anı kayarsa (:00–:29
arası restart/telafi taraması) `bar_kapandi_mi()` güvenlik kapısı anlık push'u
sonraki tura bırakır ve durum `/durum` aday hunisinde "kapanmamış bar (ertelendi)"
olarak görünür. Anlık mesajlar hangi mumun kapandığını da yazar
(`🕒 4 saatlik mum 25.09 13:30 → 17:30 kapandı`).
Regresyon: `test_mum_kapanis_penceresi.py` (23 test) + `test_tarama_zamani.py`.

### Haftalık doğruluk karnesi (Supabase GEREKTİRMEZ)

Bot, sinyal defterini **tamamen yerel** tutar: `DATA_DIR/karne_defteri.json`
(atomik yazım, tek dosya). Uzak store yoksa da karne tam çalışır.

* Tarama sırasında iki olay deftere düşer: **formasyon** (hisse/TF/formasyon
  48 saat TTL ile tekilleştirilir) ve **kırılım** (giriş = teyit barının kapanışı,
  yön, kalite, ATR). Retest/tamamlanma/başarısız kırılım **huni** sayılarına girer.
* **Her Cuma** gün sonu mesajının (18:45 `📋 Günlük Özet`; gönderilemezse 20:00
  `🌙 GÜN SONU ANALİZİ`) **altına** karne otomatik eklenir; haftada bir kez
  gönderilir (kalıcı işaret). Karne uzun ve mesaja sığmıyorsa kesilmez, ayrı
  mesaj olarak gider.
* `/karne` (veya `/karnem`) ile istenildiği an alınır: `/karne 30` son 30 gün.
* Karne içeriği: formasyon sayısı + TF kırılımı, hisse listesi (adet ile),
  kırılım sayısı (yukarı/aşağı), `N bar içinde: hedef / nötr / stop`,
  "kırılım yönünde kapatan" oranı, ortalama lehte/aleyhte hareket, TF ve kalite
  performansı, en iyi/en kötü sinyaller, huni ve `n<30` uyarısı.
* Performans ölçütü ATR bazlıdır (`KARNE_HEDEF_ATR=1.5`, `KARNE_STOP_ATR=1.0`,
  `KARNE_HORIZON_BAR=10`); ilk dokunuş yarışı kullanılır, aynı barda ikisi de
  olursa muhafazakâr sayılır (stop).

Regresyon: `test_karne.py` (30 test).

**Canlı notu (Render):** `DATA_DIR` orada `/tmp` olduğu için defter redeploy'da
silinir; `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` tanımlıysa defter
`state:karne_defteri` anahtarına **yalnız yedek** olarak yazılır ve açılışta
yerelle birleştirilir. Supabase **zorunlu değildir**; yoksa karne yerel dosyayla
tam çalışır.

## Render ve Supabase dağıtımı

> Adım adım kurulum (Python sürümü sabitleme, Supabase `sb_secret_` anahtarı,
> telefondan Telegram token alma, keep-alive) için: **[RENDER_DEPLOY.md](RENDER_DEPLOY.md)**

Build Command `pip install -r requirements.txt`, Start Command `python main.py`.
Python sürümü repodaki `.python-version` ile **3.12**'ye sabitlidir; Render'ın
varsayılanı 3.14'tür ve pandas 2.2.2 / numpy 1.26.4'ün cp314 tekerleği
olmadığı için build kaynak koddan derlemeye düşüp patlıyor.
Render `PORT` değişkenini verdiğinde bot `0.0.0.0:$PORT` üzerinde `/health` endpoint'i açar;
monitör yalnızca liveness JSON'u görür, token/anahtar veya portföy verisi döndürülmez.
Yanıt canlılık alanları da taşır (`heartbeat_age_s`, `heartbeat_stale`,
`tarama_suruyor`, `seans_acik`) ve komut katmanını raporlar:

```json
"komut": {"mod": "webhook|yoklama|kapali", "dinleyici_canli": true,
          "islenen": 3, "yetkisiz_sohbet": 0, "bayat_atlanan": 12, "mesgul_atlanan": 4,
          "son_komut_sn_once": 240, "son_yetkisiz_sohbet": "…1234"}
```

Yani "bot ayakta görünüyor ama DM komutları cevap vermiyor" durumunun sebebi
(yanlış `chat_id` → `yetkisiz_sohbet`, uyku → `bayat_atlanan`, kapalı katman →
`mod: kapali`, ölü dinleyici → `dinleyici_canli: false`) tek bakışta görülür.
Render'ın kendi health check'i sorgusuz çağırdığı için `/health` **her zaman
200** alır, ama `GET /health?strict=1` heartbeat bayatken **503** döner —
UptimeRobot/cron-job.org gibi bir monitörü bu adrese bağlarsan "bot dondu"
durumu sessizce geçmez.

`TELEGRAM_TEST_KEY` tanımlıysa `GET /test?k=<anahtar>` gerçek bir Telegram test
mesajı gönderir (gönderim tarafını telefondan doğrulamak için). Anahtar
tanımlı değilse bu yol 404 döner ve Telegram'a hiçbir istek gitmez.

`TELEGRAM_WEBHOOK_SECRET` tanımlıysa aynı sunucu `POST /webhook` (sırsız yol;
doğrulama `X-Telegram-Bot-Api-Secret-Token` başlığıyla)
ucunu açar ve Telegram komutları webhook ile gelir (adres `RENDER_EXTERNAL_URL`
üzerinden otomatik üretilir); tanımlı değilse uç 404 döner ve bot `getUpdates`
yoklamasını kullanır. Detay: `RENDER_DEPLOY.md` §4.6.

Bot artık **iki yönlüdür**: Telegram'dan gelen komutları yanıtlar. Komutlar
yalnızca `TELEGRAM_CHAT_ID`'den (DM) kabul edilir; public grup/kanal hedefi
(`TELEGRAM_GROUP_ID`) yalnız yayın alır. Kanal mesajları Telegram'da
`channel_post` türünde gelir ve bot yalnız `message` güncellemelerini dinlediği
için **kanalda komut yolu yoktur**:

| Komut | Ne yapar |
|---|---|
| `/formasyonlar` | Günün canlı formasyonları (`/formasyonlar 1h`, `/formasyonlar THYAO` filtreleri) |
| `/canli`, `/c` | Canlı formasyonlar tek kompakt mesajda |
| `/panel`, `/p` | 48 hisse × 4 TF slot tablosu + sayılar + kompozit kalite/durum puanına göre en anlamlı 12 aday (`/genel`, `/tablo` diğer adları; `/panel 1h THYAO` gibi filtreler). Çağrıldığında güncel veriyle analiz başlatır. |
| Son tarama durumu | Başarısız/eksik analiz başarılı boş sonuçtan ayrılır; önceki başarılı adaylar hata durumunda korunur. Yeniden başlatılmış snapshot güncel kabul edilmez. Supabase yalnızca opsiyonel OHLCV cache/geçmiş kaydıdır. |
| `/ozet`, `/o` | Günlük özet (tamamlanan/retest/sıkışan) |
| `/durum` | Piyasa, son tarama yaşı, canlı sayı, veri sağlığı, günlük alarm/hata |
| `/tara [HISSE]` | Şimdi analiz et (seans dışı da; mum kapanışını beklemez). Son tamamlanmış mumun zamanı/veri yaşı raporlanır. |
| `/yardim` | Komut listesi |

`/panel` ve `/tara [HISSE]` yeni analiz işini kuyruğa alır ve bitince raporlar. Analiz sırasında gelen slash komutları kuyruğa eklenmez ama sessiz de bırakılmaz: kısa bir "⏳ Analiz sürüyor" mesajıyla yanıtlanır. İstanbul saatiyle `POST_CLOSE_ANALYSIS_TIME` (varsayılan 20:00) anında ayrı bir tam evren analizi yapılır.

Komutlar varsayılan olarak `getUpdates` uzun yoklamasıyla ayrı bir thread'de
toplanır; aynı token'la ikinci bir kopya (Termux/PC) çalışıyorsa `409 Conflict`
alır — o kopyayı kapatın, yoksa komutlar çalışmaz. Webhook modunda (`§4.6`)
yoklama kapanır, çakışma olmaz. Detay: `RENDER_DEPLOY.md` §4.5.

Bot uykudayken yazılan komutlar sessizce kaybolmaz: 15 dakikadan eski komutlar
çalıştırılmaz ama atlandıkları tek bir mesajla bildirilir; gecikmeli teslim
edilen `/yardim`, `/durum` gibi okuma komutları "bot uykudaydı" notuyla
yanıtlanır. Komut katmanının canlı durumu `/health` içindeki `komut` alanındadır
(`mod`, `dinleyici_canli`, `yetkisiz_sohbet`, `bayat_atlanan`, `son_komut_sn_once`).

Kurulumun neresinde takıldığını tek komutla görmek için:

```bash
python deploy_check.py --url https://<servis-adin>.onrender.com
python deploy_check.py --url https://<servis-adin>.onrender.com --test-key <TELEGRAM_TEST_KEY>
```

Her satır ✅/⚠️/❌ ile biter, ❌ satırının altında ne yapılacağı yazar; token ve
anahtar değerleri hiçbir zaman ekrana basılmaz. Özet satırı üç durumu ayrı söyler:
`ÖZET: Telegram HAZIR · Kanal HAZIR|YOK|HEDEF VAR, IZIN YOK · Supabase HAZIR|YOK`
— kanal adımı (bot yönetici mi, mesaj izni açık mı) aynı komutla doğrulanır. Deploy öncesi kontrol ise GitHub
tarafındadır: `.github/workflows/ci.yml` her push'ta aynı Python 3.12 sürümüyle
kurulumu, testleri ve `PORT` verilip `/health`'in 200 döndüğünü doğrular.

Keep-alive iş akışı (`.github/workflows/keepalive.yml`) **5 dakikada bir** olacak
şekilde tanımlıdır ve her gün İstanbul saatiyle 08:00–23:00 arasında `/health`'e
istek atar. Pencere, BIST seansını ve akşam komut kullanımını kapsar; gece servis
uyur (Render Free'nin 750 instance saat/ay kotası korunur: 15 sa/gün ≈ 450–465
sa/ay, 7/24 ≈ 730 sa/ay). 7/24 ayakta tutmak için Actions → Variables →
`KEEPALIVE_ALWAYS=true` (bkz. `RENDER_DEPLOY.md` §5).

> ⚠️ **Ölçüldü (Ekim 2026):** GitHub bu repoda cron koşularını seyrek tetikledi —
> `*/5` tanımına rağmen günde 4–6 koşu (beklenen 288), çoğu pencere dışı olduğu
> için **günde 0–3 gerçek ping**. Yani servis saatlerce uyuyabiliyor ve o sırada
> yazılan DM komutları yanıtsız kalıyor. Tek kontrol:
> `gh run list --workflow keepalive.yml --limit 20`. Bu yüzden **dış monitör
> (cron-job.org / UptimeRobot) birincil yol olmalı**; DM komutlarının uyku
> sırasında da çalışması için **webhook modu** en etkilisidir
> (`TELEGRAM_WEBHOOK_SECRET`, §4.6 — Telegram POST'u servisi uyandırır).

İki çalışma seçeneği:

- **Background Worker (önerilen, ücretli):** Sürekli çalışan Python döngüsüne uygun servis türü;
  dışarıdan ping gerekmez. Bot piyasa dışında/hafta sonu tarama yapmadan bekler, fakat servis açık
  kaldığından worker çalışma süresi devam eder.
- **Free Web Service (repo içindeki iş akışıyla):** `.github/workflows/keepalive.yml`
  `https://<render-adresi>/health` adresine **5 dakikada bir**, her gün İstanbul
  saatiyle 08:00–23:00 arasında istek atar (gece servis uyur, tarama da yapmaz).
  Render Free, 15 dakika inbound trafik olmazsa servisi uyutur; 5 dk aralık
  GitHub cron gecikmelerine karşı pay bırakır. Dış monitör (cron-job.org /
  UptimeRobot) alternatiftir ve repo aktivitesinden bağımsızdır. Monitör durursa,
  Render servisi yeniden başlatırsa veya istek kaçarsa bot uyuyabilir; bu yöntem
  uptime garantisi değildir. Süreç pingler arasında çalışır, CPU'yu sürekli meşgul
  etmez; ancak uyuyan servis Telegram komutlarına cevap veremez (Telegram mesajı
  Render'a gelen bir HTTP isteği değildir) — gece komut yanıtı için
  `KEEPALIVE_ALWAYS=true`.

Telegram komutları için Render **Environment** bölümüne `TELEGRAM_BOT_TOKEN` ve
`TELEGRAM_CHAT_ID` ekleyin (secret değerleri Git'e veya sohbete koymayın).
`BOT_PROFILE` isteğe bağlıdır. Supabase entegrasyonu da isteğe bağlıdır:
`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` ve `supabase_schema.sql`, OHLCV
cache/history ile Telegram rate-limit/cooldown durumunun restart sonrası
korunmasını sağlar. Bunlar olmadan da bot Yahoo Finance ve yerel cache ile analiz
üretir; Render'ın ephemeral diski restart/deploy'da yerel geçmişi ve Telegram
cooldown state'ini sıfırlayabilir. Yeniden başlatılan analiz snapshot'ı güncel
sonuç diye kullanılmaz; `/panel` yeni veriyle tarama başlatır.

## Dosya haritası

| Dosya | İçerik |
|---|---|
| `main.py` | Bot döngüsü: fetch → resample → motor → Telegram + heartbeat; veri-yok/split kapıları |
| `canli_tarama.py` | Aktif evren (48 sembol) × 4 TF (1h/2h/4h/1d) canlı tarama raporu — **Pine karşılaştırması için** |
| `config.py` | Profiller (eşikler), hisse listesi, tatil/yarım gün takvimi, timing sabitleri |
| `data.py` | yfinance fetch (`auto_adjust=False`), StockDequeManager (1H + ayrı 1D deque), tatil/veri-yok/split yardımcıları |
| `scan_pacer.py` | Seri Yahoo istekleri için rastgele aralık, 10'lu istek grubu ve grup molası |
| `supabase_store.py` | Supabase REST API adaptörü; servis anahtarı yalnızca environment'tan okunur |
| `telegram_commands.py` | İki yönlü Telegram: `getUpdates` uzun yoklaması, yetki kontrolü, komut dağıtımı, 401/409 yönetimi (webhook modunda da aynı komut dağıtımı kullanılır) |
| `live_state.py` | Tarama thread'i ile komut thread'i arasında thread-safe canlı formasyon/durum paylaşımı |
| `health_server.py` | Render `PORT` varsa `/health` liveness (+ canlılık alanları, `?strict=1`), korumalı `/test` (X-Test-Key) ve `POST /webhook` (secret_token başlığı) uçları + IP başına rate limit |
| `supabase_schema.sql` | Cache ve çalışma durumları için tek JSONB store tablosu; Supabase SQL Editor'da çalıştırılır |
| `deploy_check.py` | Kurulum doktoru: repo dosyaları + env + Supabase tablosu + **heartbeat canlılığı** + Telegram + Render `/health` ve `/test` uçlarını tek komutla doğrular (sır yazdırmaz) |
| `.github/workflows/deploy.yml` | Render Deploy Hook ile `main` push'unda otomatik deploy (hook secret yoksa uyarı verip atlar) |
| `.github/workflows/ci.yml` | Render eşdeğeri CI: Python 3.12 kurulumu, pytest, zamanlama regresyonu ve `PORT` verilip `/health` duman testi |
| `.github/workflows/keepalive.yml` | Render Free uyumasın diye `/health` pingi (5 dk, her gün 08:00–23:00 İstanbul; `KEEPALIVE_*` değişkenleriyle ayarlanır) |
| `RENDER_DEPLOY.md` | Render Free + Supabase + Telegram kurulum rehberi; build hatası ve keep-alive dahil |
| `.python-version` | Render build'ı için Python 3.12 sabitlemesi (3.14'te pandas derlenemiyor) |
| `requirements-optional.txt` | Deploy zincirinde olmayan isteğe bağlı paketler (borsapy) |
| `patterns/` | Motor: `candidate.py` (geometri + bayrak/flama), `pivots.py`, `pole.py` (direk), `lifecycle.py` (state makinesi), `violation.py`, `selection.py`, `mathutil.py` |
| `notifier.py` | Telegram: 4 saat cooldown + global günlük/saatlik kapanı |
| `bot_data/` | Hisse cache'leri — **bilerek git-tracked** (kullanıcı isteği) |
| `PINE_FARK_ANALIZI.md` | **Çalışma defteri:** Pine ile fark analizi, doğrulama listesi, fikir defteri |
| `FORMASYON_MANTIGI.md` | Pine v0.4.6 Türkçe dökümanı (formasyon koşulları, kalite formülleri) |
| `docs/archive/TESHIS_RAPORU.md` | Dış teşhis raporunun bağımsız doğrulaması (TRUE/FALSE/PARTIAL) — arşiv |
| `SORUN_RAPORU.md` | Ölçümlü teşhis: üretim→Telegram hunisi, bastırılan adaylar, S1-S11 + ek bulgular |
| `YAPILACAKLAR.md` | A (düzeltme) / B (iyileştirme) / C (şablon) tam iş listesi, öncelik ve efor |
| `KODLAMA_PLANI.md` | Batch'li uygulama planı; her batch için kapsam/dosya/test/kabul kriteri |

## Canlı tarama raporu nasıl okunur (Pine karşılaştırması)

`canli_tarama.py` çıktısı TradingView'daki Pine overlay'iyle karşılaştırmak için tasarlandı:

- Başlıkta **"Veri son bar: <tarih> (<N> saat once)"** — TradingView'da tam olarak hangi ana bakılacağını söyler.
- Her formasyon: tip, kalite, state, üst/alt çizgi seviyeleri, daralma %, başlangıç tarihi.
- **Bayrak/flamada ek detay:** `Pine varyanti` (standart/eğik), `Direk` (yön/süre/büyüklük/kalite), `Flama olculeri` (derinlik, yükseklik/süre oranı — Pine eşikleri parantezde).
- Rapor sonunda **PINE KARSILASTIRMA REHBERI**: kaç bayrak/flama bulundu + tüm eşikler.
- Not: Pine ekranında eski TAMAMLANDI/BASARISIZ formasyonlar da çizili kalabilir — rapor yalnız **canlı** olanları listeler.

## Durum (2026-09-30, dal `arena/01a0f318-formation-bot`)

| Faz | İçerik | Commit |
|---|---|---|
| Faz 1 | Son mum/35-dk gecikme düzeltmesi, `auto_adjust=False`, ölü formasyon alarm kapısı, fetch hata loglama + `data_stale` heartbeat | `7485ab6` |
| Faz 2 | 1D gecikme, BIST tatil/yarım gün takvimi + veri-yok modu, split/süreklilik kontrolü, Telegram global kapanı, tarama drift uyarısı, 1D derin deque (500 bar) | `c3000b6` |
| Faz 3 | Flama motoru doğrulama: `test_pennant.py` (6/6), `specialized_variant` (standart/eğik ayrımı), standart flama geometri şartı, canlı rapora direk/ölçüm detayı + veri tazeliği | `da3840b`, `0fd1f46`, `28a1e7a` |
| Faz 4 | Son tarama kalıcılığı + `LiveState.snapshot/hydrate`, Telegram webhook modu, `telegram_alert_flow` ile erteleme (18:45 digest) ve panel rapor katmanı | `b85f6bb` (PR #9), `0bca8e5` |
| Faz 5 (batch-1) | Açılışta `son_tarama_yukle()` çağrısı geri kondu; tatil/yarım gün günlerinde ana döngünün 0 sn uykulu boş dönmesi düzeltildi | `e9a736f` |
| Faz 5 (batch-2) | Ölü kod temizliği (kanal dalı, `[:10]`, `get_formations`), özet ile panel aynı kaynaktan, digest şeffaflığı (`12/21 gösteriliyor` + `… N aday daha`), `DEFERRED_ALERT_DIGEST_LIMIT`, benzersiz günlük formasyon sayacı | `6dca717` |
| Faz 5 (batch-3) | Aday hunisi sayaçları (`/durum` "🔎 Aday hunisi"), engel sayaçları (cooldown/günlük kap/saatlik kap/hata), `/panel` eşik altı satırı | `401a788` |
| Faz 5 (batch-4) | Sunucu saat dilimi (İstanbul) sayaç/log uyumu + `TZ` değişkeni, uzun mesaj kırpma + sınırlı retry, gönderim sağlığı alanları (heartbeat + `/durum` "Telegram PASİF" uyarısı) | `7626e7d` |
| Faz 5 (batch-5) | 18:45 digest tamponu kalıcı (`state:digest_pending` + açılışta geri yükleme + kaçırılan özet telafisi), engellenen acil olay kuyruğu (`state:telegram_acil_kuyruk`, engel kalkınca gönderim, kuyruk derinliği heartbeat'te) | `0ba343e` |
| Faz 5 (batch-6) | Yazma amplikasyonu (içerik parmak izi + heartbeat throttle → tarama başına 144 istek/3,3 MB yerine ~50 istek/2 MB, değişmeyen turda ~0), sır URL'den çıktı (webhook `/webhook` + secret_token başlığı, `/test` X-Test-Key, IP rate limit), `.pkl` Git'ten çıkarıldı (JSON birincil), çoklu örnek tespiti (`state:instances` + heartbeat/`/durum` uyarısı) | `a65b053` |
| Faz 5 (batch-7) | Şablon hazırlığı: `MARKET_SUFFIX`/`STOCK_UNIVERSE`/`LOG_DIR` env + `SESSION_OPEN/CLOSE` adları + 2027 tatil takvimi (C1), Supabase anahtar ön eki `SUPABASE_STORE_PREFIX=formation-bot:` + eski anahtarları iki turlu okuma (C3), `DATA_DIR` repo dışı varsayılan + `SEED_DATA_DIR` salt-okuma seed (C4), ölü araç temizliği (`fetch_with_rate_limit`, mock demo, `repo_teshis.py`, `logrotate.conf`, `.ps1`) (C7) | `a738ec4` |

| Faz 5 (batch-8) | `main.py` katmanlara ayrıldı (yapısal, davranış değişmedi): `reporting/format.py` (saf metin/sayı üretimi, 8.1), `import main` yan etkisi kaldırıldı (8.2), `reporting/panel.py` (panel raporu bağlam ile, 8.3), `state/paths.py` + `state/persistence.py` (son tarama + digest tamponu, 8.4), `transport/telegram.py` (webhook/komut katmanı, 8.5). `main.py` 3047 → 2380 satır | `77a2756` |

Regresyon: `pytest` **305 passed**, `test_tarama_zamani.py` **100/100**, `test_pennant.py` **6/6**.

Ölçüm (B5, 48 hisse × 360 bar 1H + 250 bar 1D, tek tarama turu):
`96 istek / 3,26 MB` → seans içi `48 istek / 1,98 MB`, veri değişmeyen turda `0 istek / 0 MB`;
heartbeat `48 istek / 42 KB` → `2 istek / 1,8 KB`. Telemetri: heartbeat `uzak_yazma` alanı.
Açık iş listesi ve batch planı: `YAPILACAKLAR.md`, `KODLAMA_PLANI.md`; ölçümlü teşhis: `SORUN_RAPORU.md`.

## Bilinmesi gerekenler (yeni oturum için)

1. **Pine dosyası bekleniyor** (`Yeni Metin Belgesi.txt`, ARGENT v0.4.6 export). Diske
   ulaşmadı; geldiğinde `PINE_FARK_ANALIZI.md` §5'teki 12 maddelik doğrulama listesi açılacak.
2. **Bildirim durumu artık kalıcı (Faz 5):** 18:45 digest tamponu `state:digest_pending`,
   engellenen acil olaylar `state:telegram_acil_kuyruk` anahtarıyla Supabase'e +
   `DATA_DIR` içindeki dosyalara yazılır (batch-7/C4: repo dışı; `state/persistence.py`);
   açılışta geri yüklenir. Bot akşam 18:45'te kapalıysa kaçırılan
   kapanış özeti açılışta "⏰ Kaçırılan kapanış özeti" olarak telafi edilir. Engellenen acil
   olay `ACIL_KUYRUK_TTL_DK` (varsayılan 180 dk) içinde engel kalkınca gönderilir; süre aşılırsa
   bayat sinyal atılır (kuyruk sayaçları `/durum` ve heartbeat'te görünür).
3. **Kalite katsayı sapması:** döküman 0.28/0.20/0.12/0.16/0.12/0.07/0.05 diyor, kod
   0.26/0.18/0.12/0.20/0.10/0.07/0.07 kullanıyor — **Pine gelmeden kod değiştirilmeyecek**.
4. **Standart flama geometri şartı** (Faz 3'te eklendi): standart flama yalnız Simetrik Üçgen
   geometrisinde kurulur; eğik geometri eğik flama tablosundan (direk kalitesi +10, süre ×0.85,
   kalite +8) geçer. Pine'da birebir var mı — doğrulama madde 11.
5. **Açık A5 maddeleri:** `filter_same_bar_double_pivot` stub, `local_break` TODO,
   `ST_WEAK`/`ST_GEOMETRY` kod yolu yok.
6. **Eşikleri ölçüm olmadan gevşetme yasağı** — A4'ün kök nedeni buydu (sentetik bayrak
   reddediliyor, gerçek veride sahte bayrak bulunuyordu).
7. **Sandbox kısıtı:** bu ortamdan Yahoo Finance ve Telegram'a erişilemiyor (SSL). Gerçek
   zamanlı tarama ve canlı bot testi kullanıcının kendi makinesinde yapılmalı; burada
   `--cache` modu ve commit'li `bot_data` kullanılır.
8. **Alarm ve kanal politikası TEK KAYNAK (`config.py`):** karar bekleyen B7/B9
   maddeleri davranışı değiştirmeden tek yerde toplandı —
   `ALERT_STATES` (anında push edilen 4 kritik olay), `WATCH_STATES` (18:45 kapanış
   özetine ertelenen 6 izleme state'i; `telegram_alert_flow.WATCH_STATES` bu listeye
   bağlıdır) ve `PUBLIC_STATES` + `PUBLIC_MIN_QUALITY_TF` + `PUBLIC_SIKISMA_MIN_CONTRACTION`
   (public grup/kanal akışı; B9). Kesişim/çift bildirim `config._politika_hatalari` ile
   import anında yakalanır, testler bunu doğrular. Politikayı değiştirmek için sadece
   bu üç yeri düzenle; kodda başka yerde kopya liste yok.

   **Public grup (Faz 1, 02.10.2026):** `TELEGRAM_GROUP_ID` tanımlıysa bot, DM'den
   **bağımsız** olarak gruba yayın yapar (DM kapalıyken de çalışır). Olaylar tarama turu
   boyunca kuyrukta toplanır ve tur sonunda **tek bültende** gider; bütçe DM'den ayrıdır
   (`PUBLIC_MAX_MESAJ_SAAT=6`, `PUBLIC_MAX_MESAJ_GUN=25`, `PUBLIC_MIN_ARALIK_SN=1.2`) ve
   429 `retry_after` desteklenir. Grup metni sadedir: iç izleme notu, `/panel`, `/durum`,
   dosya yolu, ❌ tek tek olaylar gruba **gitmez**; başarısız kırılımlar 18:45 özetinde
   sayı olarak ve Cuma karnesinin kısa sürümünde görünür. Gruba yönetici bot, komut
   olmayan grup mesajlarına **cevap vermez** (yalnız DM'de yardım metni döner).

   **Kanal/grup açılışı:** hedef bir **kanal** da olabilir (önerilen); açıklama ve
   sabitlenmiş karşılama metinleri `KANAL_ACILIS_PAKETI.md`'de, uygulama aracı
   `python kanal_acilis.py --durum|--uygula` (varsayılan kuru çalışma, yazmaz). Evren 48'in üzerine çıkarsa
   `EVREN_BUYUME_UYARI_ESIGI` ile açılışta tek satır uyarı loglanır (pacing/digest/panel
   limitleri yeniden ölçülmeli).
9. **Veri dizini artık repo dışında (batch-7 / C4):** yazımlar `DATA_DIR`'e gider; sırayla
   `RENDER` → `/tmp/formation-bot-data` → `/var/lib/formation-bot/data` → `~/.formation-bot/data` →
   `./bot_data` denenir. Repodaki `bot_data/*.json` yalnız **okuma** yedeğidir (`SEED_DATA_DIR`);
   canlı veri diske yazılmaz. Supabase anahtarları `SUPABASE_STORE_PREFIX` (varsayılan
   `formation-bot:`) ile öneklenir; öneksiz eski kayıtlar okunur ve sonraki yazımda taşınır.
10. **Bot kuralları:** `bot_data/*.json` git-tracked; **`*.pkl` artık dışarıda** (A8: public repoda pickle yürütme yüzeyi olmasın; okuma JSON birincil, eski `.pkl` yalnız yedek). Runtime dosyaları
   (heartbeat, telegram_kap, telegram_acil_kuyruk, telegram_digest_pending, *_gunluk.json) gitignore'da. Tüm iş `arena/01a0f318-formation-bot`
   dalında; başka dala push yok. Merge YALNIZCA kullanıcı onayıyla yapılır.
