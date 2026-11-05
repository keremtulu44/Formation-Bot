# Formation-Bot için API senaryoları ve ürün fikirleri

> **Öneri / fikir notu.** Bu dosya yeni bir değerlendirme belgesidir; mevcut araştırma ekleri, CSV/JSON sonuç dosyaları ve örnek PNG'ler değiştirilmemiştir. Bu turda **public/production REST API eklenmedi**. Yalnız `scripts/diagnostics/stabil_api_poc.py` altında, gerçek Stabil runner'ını yerel ASTOR arşiviyle çağıran, `127.0.0.1` dışına bağlanmayan bir HTTP PoC ve kontrat testleri eklendi. Bu PoC deploy edilebilir API değildir; kapsam/sınırlar §10'da.

---

## 0. Kısa cevap

Bugün proje tek kullanıcılı, Telegram merkezli, uzun süre çalışan bir bot. Dışarıya açılmış bir analiz API'si yok; yalnızca operasyonel HTTP uçları var. API eklenirse sistem üç farklı ürüne dönüşebilir:

1. **Okuma API'si / analiz servisi:** formasyon, Stabil destek, sinyal, grafik ve replay sonuçlarını `as_of` kesitiyle sorgulayan web/mobil/partner yüzeyi.
2. **Olay API'si / otomasyon:** yeni sinyal, kırılım, geri alım ve güçlü yukarı momentum olaylarını webhook/SSE ile alan alarm, dashboard ve araştırma otomasyonu.
3. **Platform çekirdeği:** aynı motoru çoklu kullanıcı, çoklu sembol evreni, lisanslı veri, kalıcı state ve denetim kaydıyla sunan B2B/B2C servis.

Ayrıca "API eklemek" şu anlama da gelebilir: **dış servisleri içeri bağlamak** (lisanslı piyasa verisi, haber/fundamental, LLM, broker/OMS, Slack/e-posta, gözlemlenebilirlik). Bu ikisi ayrı katmanlarda ele alınmalı; önce dışa okuma API'si, sonra kontrollü entegrasyonlar önerilir.

---

## 1. Bugünkü durum — kodda ne var, ne yok?

| Yüzey | Dosya | Bugünkü rol | API ürünü için sınır |
|---|---|---|---|
| `GET /health` | `health_server.py` | Render liveness; her koşulda 200 | Veri/sinyal doğruluğunu kanıtlamaz |
| `GET /ready` | `health_server.py` | Yalnız başlangıç/kapanış durumu | Telegram, veri veya Supabase hazırlığını garanti etmez |
| `GET /test` | `health_server.py` | `TELEGRAM_TEST_KEY` ile korunan tek Telegram denemesi | Analiz uçu değil |
| `POST /webhook` | `health_server.py` | Telegram komutlarını taşır | Dış istemci API'si değil |
| `/grafik`, `/stabil`, `/panel`, `/tara` | `telegram_commands.py`, `bot/commands.py`, `bot/stabil_service.py` | Telegram komutları | Komut katmanı HTTP sözleşmesine sahip değil |
| `notifier/api.py` | `notifier/api.py` | Telegram'a giden istemci/yardımcılar | İsim yanıltıcı; public API değil |
| `supabase_store.py` | `supabase_store.py` | Opsiyonel, büyük ölçüde salt-okunur uzak state | Yeni state yazmıyor; kalıcı disk değil |
| `domain_engines/` | `runner.py`, `stabil/*` | Nedensel motorlar | Şu an bot süreciyle aynı yaşam döngüsünde |
| `research/` | `replay_egitim.py`, `stabil_replay.py` | Arşiv ölçümü ve eğitim | Script/DM akışı; job/artifact API'si yok |

Önemli mimari gerçekler:

- `requirements.txt` içinde FastAPI/Flask yok; HTTP katmanı standart `http.server` ile küçük tutulmuş.
- `DATA_DIR` Render'da varsayılan geçici `/tmp` olabilir; restart'ta yerel state kaybı riski var.
- Replay sonuçları **betimsel araştırmadır**, canlı getiri veya yatırım tavsiyesi değildir.
- Motorlar `as_of`/kapanmış mum sözleşmesine bağlıdır; API bunu bozmamalı.
- Aynı token/Supabase ile iki örnek açılması çift bildirim ve state yarışı riski taşır.

---

## 2. İki ayrı "API" yorumunun ayrımı

### A. Sistemi dışarıya açmak — önerilen ilk anlam

İstemciler motorun sonucunu okur; motoru değiştirmez. Örnekler: web dashboard, mobil uygulama, partner sinyal feed'i, araştırma paneli, eğitim/replay aracı.

**Öncelik:** salt-okunur, versiyonlu, `as_of` zorunlu, cache'li, denetim kayıtlı.

### B. Dış API'leri sisteme bağlamak — ikinci anlam

| Dış servis | Amaç | Dikkat |
|---|---|---|
| Lisanslı BIST / piyasa verisi | Yahoo/yfinance bağımlılığını azaltmak, kapanış semantiğini sertifikalandırmak | Veri lisansı, sembol eşlemesi, split/bedelsiz, makro 24s kapanış |
| Haber / temel veri / takvim | Sinyale bağlam eklemek | Motor çıktısını değiştirmeden ayrı `context` alanı |
| LLM / açıklama servisi | Kartı düz Türkçe özetlemek | Deterministik şablonu bozmamak; ölçüm uydurmamak; gizli veri göndermemek |
| Broker / OMS | Emir göndermek | En yüksek risk; ayrı yetki, risk limiti, regülasyon, audit; MVP'de **yok** |
| Telegram / Slack / e-posta | Bildirim dağıtımı | Mevcut Telegram yolunu API'den ayırmak |
| S3 / Supabase / Postgres | PNG ve sinyal geçmişi | Kalıcı disk, tek yazan örnek, migration |
| Auth / billing / observability | API anahtarı, kota, fatura, hata izleme | Sırlar header'da; URL'de değil |

---

## 3. Ne amaçla kullanılabilir? Somut ürün senaryoları

1. **Analist terminali:** sembol × TF matrisi, Stabil destek/uzaklık, formasyon durumu, OB/FVG/zone çakışması, veri kalitesi.
2. **Mobil/web grafik:** aynı `grafik.ciz` çıktısını PNG veya etkileşimli JSON katmanlarıyla sunmak. Bu turda eklenen güçlü yukarı momentum `▲` işareti de API'den dönebilir.
3. **Sinyal aboneliği:** `reclaim`, `momentum`, `breakout`, `retest` olaylarını webhook/SSE ile iletmek; idempotency key ve tekrar deneme.
4. **Replay eğitim modu:** `/replay/questions` ile soru üret, tahmin al, `/replay/results` ile sonuç karesini döndür. Tarihleri gizleyen mevcut DM eğitim akışı API'ye taşınabilir.
5. **Araştırma/backtest servisi:** asenkron job → CSV/JSON artifact; aynı nedensellik ve sansür kuralları; ham veri lisansı kontrolü.
6. **Operasyon dashboard'ı:** `/health` + `/ready` + tarama yaşı + veri kaynağı + gönderim sağlığı + kaçırılan aday sayaçları.
7. **Kurumsal alarm otomasyonu:** fon/yatırım masası için watchlist, kota, kullanıcı/rol, denetim kaydı.
8. **Eğitim / içerik ürünü:** formasyon ve Stabil davranışını örnek grafiklerle anlatan interaktif dersler; canlı emir içermez.
9. **Veri ürünü / B2B feed:** normalize edilmiş olay geçmişi, destek seviyesi, rejim, kalite bayrağı; lisans ve kullanım koşullarıyla.
10. **Model izleme:** motor sürümü, sinyal dağılımı, drift, yanlış/eksik veri oranı, replay ile canlı sonuç farkı.

**Şimdilik kaçınılması gereken:** doğrudan otomatik emir, "kesin getiri" pazarlaması, doğrulanmamış makro kapanışlarla sinyal, lisanssız veri dağıtımı.

---

## 4. Önerilen MVP sözleşmesi

### 4.1 Temel ilkeler

- Her analiz yanıtında `as_of`, `timeframe`, `symbol`, `engine_version`, `data_quality`, `source`, `warnings` zorunlu.
- Snapshot endpoint'lerinde `as_of` timezone taşıyan ISO-8601 olmalı; timestamp etiketinden ziyade gerçek mum kapanışıyla kesim yapılmalı. Yalnız **kapanmış mumlar** kullanılır; gelecek mum sonuca giremez.
- `replay` ve `live` ayrı etiketlenir; replay sonucu canlı performans gibi sunulmaz.
- Yanıtlar `not_investment_advice: true` taşır.
- GET sorguları doğal olarak idempotent olabilir. Aynı cache anahtarı `symbol + tf + as_of + source/version` bileşenlerini içermeli; canlı/freshness uçları için `no-store` tercih edilebilir. Yazma/iş başlatma uçları idempotent sayılmaz; idempotency key, tekrar deneme ve replay koruması ayrıca tanımlanır.
- Bütün ürün uçları versiyonlu (`/v1/...`) olmalı; test PoC'sindeki `X-API-Key` production auth/kota tasarımının yerine geçmez.

### 4.2 İlk endpoint seti

| Endpoint | Amaç |
|---|---|
| `GET /v1/health` | Operasyonel özet; `/health` liveness ile karıştırılmaz |
| `GET /v1/symbols` | Desteklenen evren, TF'ler, veri kaynağı, son kapanış |
| `GET /v1/symbols/{symbol}/stabil?tf=4h&as_of=...` | Destek seviyesi, renk rolü, rejim, mesafe, `reclaim_kind`, `momentum_kind` |
| `GET /v1/symbols/{symbol}/domains?tf=4h` | OB/FVG/MS/hacim/Stabil özetleri |
| `GET /v1/signals?from=...&to=...&kind=...` | Olay geçmişi; sayfalama + imza |
| `GET /v1/charts/{symbol}?tf=4h&as_of=...` | PNG veya katman JSON; cache anahtarı motor sürümünü içerir |
| `POST /v1/replay/jobs` | Arşiv kesiti + soru/ölçüm job'ı; `job_id` döner |
| `GET /v1/replay/jobs/{job_id}` | Durum + artifact URL'leri |
| `POST /v1/webhooks` | Olay aboneliği; HMAC imzalı teslim, retry, idempotency |
| `GET /v1/audit/events` | Kim, ne zaman, hangi motor sürümüyle hangi sonucu aldı |

### 4.3 Örnek Stabil yanıtı

```json
{
  "api_version": "v1",
  "request_id": "<her istekte yeni 32 karakterlik kimlik>",
  "symbol": "ASTOR",
  "timeframe": "4h",
  "as_of": "2026-10-16T18:30:00+03:00",
  "engine_version": "stabil-local-poc",
  "data_quality": "OK",
  "source": "archive",
  "latest_bar_close": "2026-10-16T18:00:00+03:00",
  "latest_bar_age_seconds_at_as_of": 1800,
  "close_price": 164.89999389648438,
  "support_level": 172.10000610351562,
  "price_vs_support": "destek altında",
  "regime": "HORIZONTAL_AFTER_DROP",
  "signals": {
    "reclaim_kind": null,
    "momentum_kind": null,
    "weak_reclaim": false
  },
  "chart_markers": {
    "reclaim_arrow": false,
    "momentum_arrow": false
  },
  "readiness": {
    "daily_support": "READY",
    "weekly_trend": "READY",
    "daily_trend": "READY",
    "h4_trend": "READY"
  },
  "warnings": ["OFFLINE_ARCHIVE_NOT_LIVE"],
  "not_investment_advice": true
}
```

Bu, aşağıdaki §10'da anlatılan yerel PoC'nin **gerçek HTTP yanıtındaki** değişken `request_id` çıkarılmış örnektir; fiyatların son basamakları kaynak/arşiv kayan nokta gösterimini yansıtır, canlı fiyat değildir. `source` tek bir enum değeridir (`archive` gibi); `archive|live-cache` ifadesi iki seçenek anlamına gelir, JSON'a aynen yazılmaz. Üretimde `engine_version` build/git kimliğine bağlanmalı; PoC etiketi gerçek sürümleme değildir.

Bu sözleşme, grafikteki iki ayrı `▲` anlamını da korur: **dolu yeşil** güçlü geri alım, **içi boş altın** güçlü yukarı momentum. İkisini tek bir "sinyal" alanında ezmek replay karşılaştırmasını bozar.

---

## 5. Önerilen mimari

```text
İstemci (web / mobil / partner)
        │  HTTPS + API key / OAuth + kota
        ▼
API katmanı (FastAPI + OpenAPI, ayrı process)
        │  salt-okunur sorgu + job kuyruğu
        ▼
Çekirdek servis: domain_engines + grafik + research
        │  as_of / isolated / causal
        ▼
Kalıcı katman: Postgres/Supabase + object storage (PNG/CSV)
        ▲
Bot worker: veri çekme, tarama, Telegram bildirimi
```

Neden ayrı process: bugün `main.py` uzun süreli döngü, import yan etkileri ve global state taşıyor. API'nin motoru doğrudan bot sürecine bağlaması restart, çift örnek ve kota sorunlarını büyütür.

Gerekenler:

- Motor çağrıları `isolated=True` ve `as_of_close` ile; canlı latest registry API'ye sızmasın.
- PNG/CSV artifact'ları object storage; cache anahtarı `(symbol, tf, as_of, options, engine_version)`.
- Uzun replay/backtest job'ları kuyruk + `job_id`; HTTP isteği dakikalarca açık kalmasın.
- Tek yazan worker; API salt-okunur. İkinci bot örneği için instance kilidi.
- `DATA_DIR` kalıcı diske taşınmadan API state garanti edilmesin.
- CI'a OpenAPI schema, contract test ve auth/rate-limit testi eklensin.

---

## 6. Güvenlik, hukuk ve veri kalitesi kapıları

1. **Kimlik/kota:** API key veya OAuth; scope (`read:signals`, `read:charts`, `write:webhooks`), dakikalık/günlük kota, per-IP limit.
2. **Sır yönetimi:** anahtar header'da; URL query'de değil. Mevcut `/test?k=` yolunun varsayılan kapalı olması örnek alınmalı.
3. **Webhook güvenliği:** HMAC imza, timestamp, replay koruması, exponential retry, ölü kuyruk.
4. **Denetim:** her sinyal/yanıt için `request_id`, motor sürümü, veri kesiti, kaynak, uyarılar.
5. **Veri lisansı:** yfinance/BIST verisinin dağıtım koşulları ayrı doğrulanmalı; ham OHLCV paylaşımı en riskli ürün.
6. **Yatırım tavsiyesi:** sinyal, hedef, "başarı oranı" ve replay ATR sonuçları yatırım tavsiyesi gibi paketlenmemeli.
7. **Regülasyon:** otomatik emir, portföy yönetimi veya ücretli sinyal pazarlaması ayrı hukuki değerlendirme ister.
8. **Model riski:** replay sonuçları betimsel; eşleşmiş kontrol, dönem stabilitesi, çoklu hipotez ve `n<30` uyarıları korunmalı.
9. **Gözlemlenebilirlik:** `/health` 200 iken veri bayat olabilir; API ayrı `data_freshness`, `last_scan`, `domain_errors` alanları döndürmeli.
10. **Makro semboller:** sertifikalı kapanış zamanı olmadan Stabil/API sonucu `DATA_ERROR` veya `UNAVAILABLE` dönmeli; BIST takvimi varsayılmamalı.

---

## 7. Yol haritası

### Faz 0 — Bu turda yapılan teknik hazırlık

- Stabil grafiğinde yalnız yatay destek/geri alımda çıkan `▲`, replay eşikli **güçlü yukarı mum** için de üretiliyor; destek yukarı basamak yaparken kaybolmuyor.
- `reclaim_kind` ile `momentum_kind` ayrıldı; mevcut 4S geri alım alarmı ve kart metni değiştirilmedi.
- Normal grafik ile replay aynı nedensel 1d/4h arşiv kesitini kullanabiliyor; böylece API ileride `as_of` ile aynı sonucu döndürebilir.
- Domain projeksiyonu grafikten kısaldığında oklar kapanış zamanıyla hizalanıyor; kesim sonrası destek uydurulmuyor.
- `prepare_causal_ohlcv` içinde NaN satırdan sonra `is_closed/is_complete` maskelerinin kayması düzeltildi.

### Faz 1 — Salt-okunur MVP

`/v1/health`, `/v1/symbols`, `/v1/symbols/{symbol}/stabil`, `/v1/signals`, `/v1/charts`. API key, kota, OpenAPI, contract testleri, artifact cache. **Emir yok, write endpoint yok.**

### Faz 2 — Olay ve araştırma

Webhook abonelikleri, SSE/WebSocket, replay job'ları, CSV/PNG artifact URL'leri, denetim kaydı, çoklu TF paketleri.

### Faz 3 — Platform

Çoklu kullanıcı/rol, watchlist, faturalama, lisanslı veri sağlayıcısı, kalıcı state, model sürümleme, drift raporları. Broker/OMS entegrasyonu ancak ayrı hukuki/risk kapısından sonra.

---

## 8. En yüksek getirili ilk üç fikir

1. **Stabil + grafik okuma API'si:** motor zaten hazır; en düşük risk, en hızlı demo. `as_of` ile replay/normal grafik birebir doğrulanabilir.
2. **İmzalı sinyal webhook'u:** mevcut Telegram alarm mantığını çoklu istemciye taşır; önce dolu yeşil geri alım + içi boş altın momentum ayrımıyla.
3. **Replay eğitim API'si:** mevcut DM oyununu web/mobil ürüne çevirir; canlı emir ve yatırım tavsiyesi riski olmadan değerli bir eğitim/araştırma yüzeyi olur.

---

## 9. Karar verilmesi gereken sorular

- API "dışa açık ürün" mü, yoksa önce sadece iç dashboard mu?
- Ham OHLCV dağıtılacak mı, yoksa yalnız türetilmiş olay/çizgi mi?
- Ücretli sinyal ürünü hedefleniyor mu? (Regülasyon kapısı.)
- Replay job'ları hangi arşiv/ lisans kapsamında çalışacak?
- Kalıcı veri için Supabase yazımı mı, ayrı Postgres/object storage mı?
- Broker entegrasyonu hiç düşünülüyor mu, yoksa bilinçli olarak kapsam dışı mı?

Bu sorular yanıtlanmadan public API'yi açmak, mevcut tek örnekli botun state/veri sözleşmesini bozma riski taşır. Öneri: **Faz 1'i salt-okunur ve ayrı process olarak açmak**, ürün kararını gerçek kullanım verisiyle sonra vermek.

---

## 10. Bu turdaki doğrulama ve PoC sınırları

Kod taraması `health_server.py`, `notifier/api.py`, `bot/commands.py`, `telegram_commands.py`, `supabase_store.py`, `main.py`, `grafik_uret.py` ve `research/` üzerinde yapıldı. `notifier/api.py` dosya adına rağmen `TelegramNotifier` sınıfını taşır; HTTP route veya OpenAPI şeması içermez. Mevcut uygulamanın public erişilebilir HTTP yüzü yalnızca `health_server.py` içindeki operasyonel/webhook uçlarıdır. Aşağıdaki PoC, bu yüzün genişletilmesi değil, ondan bağımsız yerel bir kontrat denemesidir.

### Okuma API'si PoC — doğrulanmış senaryo

`domain_engines/runner.py::run_stabil_domain` gerçek motoru çağrılıyor; `as_of_close` ile kesiliyor ve `isolated=True` kullanılıyor. Veri `research.arsiv.tf_frame` üzerinden repo içindeki ASTOR arşivinden gelir. `scripts/diagnostics/stabil_api_poc.py` ana bot tarafından import edilmez, yalnız `127.0.0.1`'e bind eder, `GET` dışında yöntem kabul etmez ve analiz uçlarında `X-API-Key` ister.

Yerelde başlatma (Terminal 1):

```bash
export FORMATION_API_POC_KEY='local-only-demo'  # yalnız bu yerel PoC için uydurma anahtar
.venv/bin/python -m scripts.diagnostics.stabil_api_poc --port 8765
```

İkinci terminalden gönderilen istek (zaman damgasındaki `+` URL-encode edilir):

```bash
curl --get 'http://127.0.0.1:8765/v1/symbols/ASTOR/stabil' \
  --data-urlencode 'tf=4h' \
  --data-urlencode 'as_of=2026-10-16T18:30:00+03:00' \
  -H 'X-API-Key: local-only-demo'
```

`test_api_readonly_contract_poc.py` aynı endpoint'e gerçek loopback HTTP istekleri gönderip ASTOR arşivi ve gerçek motorla sınar. 2026-11-03 tarihinde `.venv/bin/python -m pytest -q test_api_readonly_contract_poc.py` sonucu **7 passed**. Ayrıca belgelenen CLI komutu `127.0.0.1:8765` üzerinde başlatıldı; örnek `curl` isteği gerçek runner'dan HTTP 200 ve aşağıdaki arşiv sonucunu döndürdü. Kapsam:

- 4h ve 1d başarılı cevap; 4h mum kapanışı/as-of yaşı ve günlük kapanışı ayrı doğrulanır.
- `2026-10-16T15:30:00Z` ile `2026-10-16T18:30:00+03:00` aynı an kabul edilip aynı 4h sonucu üretir; cevabın `as_of` alanı İstanbul saatine normalize edilir.
- Eksik/yanlış anahtar `401`, desteklenmeyen sembol `404`, desteklenmeyen `tf`, eksik/naive/hatalı/tekrarlı sorgu parametresi `422`, gelecekteki `as_of` `422`, arşiv yokluğu `503`, `POST` `405` verir.
- `as_of` sonrasındaki hem günlük hem 4h OHLCV satırları aşırı değerlere (`10.000` fiyat ve `10^9` hacim) değiştirilince, `request_id` haricindeki analiz yanıtı değişmez; sonuçta gelecekteki kapanış bulunmadığı da ayrıca kontrol edilir. Bu, bu kontrat için look-ahead regresyonudur.
- Ham OHLCV alanları cevapta yok; offline kaynağı açıkça `source: archive` ve `OFFLINE_ARCHIVE_NOT_LIVE` ile işaretlenir.

Testte gözlenen örnek özet: ASTOR/4h için `as_of=2026-10-16T18:30:00+03:00`, son kapanış `18:00`, yaş `1800` saniye; kapanış yaklaşık `164.90`, destek yaklaşık `172.10`, ilişki `destek altında`, kalite `OK`. Bunlar **arşiv kesiti** değerleridir; canlı fiyat veya sinyal önerisi değildir. `/v1/health` yalnız PoC liveness bilgisidir; veri tazeliğini kanıtlamaz.

### Dış API ile dış servis entegrasyonu aynı iş değil

- **Dışarıya salt-okunur analiz API'si:** bu turda yalnız local PoC test edildi; auth/kapanış/look-ahead sözleşmesi için ilk kanıt var, fakat public ürün yok.
- **Dış servisleri içeri bağlamak:** piyasa verisi sağlayıcısı, haber/LLM, broker, Slack veya başka servis çağrısı bu PoC'de yapılmadı. API key, lisans, kapanış semantiği ve veri kalitesi ayrı bir değişiklik/karar olarak ele alınmalı. Broker/OMS ve emir gönderimi kapsam dışı.

Bu PoC'de TLS, rate-limit/kota, production kimlik ve anahtar rotasyonu, scope/tenant, OpenAPI, kalıcı audit, cache, canlı veri sağlayıcısı, hata bütçesi ve dışa açma yoktur. Standart kütüphanenin HTTP sunucusu ve yalnız tek ASTOR arşivi kullanılır; sonuç başına motor çalıştırılır. Dolayısıyla **Render'a deploy edilmemeli ve internet arayüzüne bind edilmemelidir**. Public API kararı öncesi ayrı process, veri lisansı, auth/kota, izleme, API schema ve contract/security testleri gerekir.

2026-11-03 son doğrulaması: tüm depo testleri **3367 passed, 43 skipped**; `.venv/bin/ruff check .` ve `git diff --check` temiz. Genel kontrol sonuçları ayrıca `docs/tasarim/GENEL_KONTROL_VE_STABIL_OK_DUZELTMESI_2026-11-03.md` dosyasında özetlenmiştir. Public API, yeni bağımlılık veya emir/yazma yüzeyi bu turda eklenmedi.

