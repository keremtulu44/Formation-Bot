# Deploy hazırlık kontrolü — 2026-11-18

**Dal:** `arena/79b4d2e1-formation-bot` (aktif) · **Hedef:** Render Web Service,
Python 3.12 · **Kapsam:** *mevcut* üretim veri hattının deploy'a hazırlanması.
TV/datafeed geçişi ayrı bir ölçüm kapısıdır ve bu deploy'un parçası **değildir**.

## Kısa cevap

| Soru | Cevap |
|---|---|
| **Veri çekme sistemi hazır mı?** | **EVET.** Üretim `data/fetch.py` hattı bu çalışma boyunca **hiç değişmedi**: yfinance birincil + Yahoo sembol yedeği. `python -m data` çevrimdışı duman testi geçti. |
| **Testler hazır mı?** | **EVET.** `ruff`, `compileall`, `pip check`, `git diff --check`, tam pytest, zamanlama, 4 bağımsız formasyon scripti, grafik doktoru ve gerçek HTTP `/health` smoke yeşil. |
| **CI hazır mı?** | **EVET.** `.github/workflows/ci.yml` `arena/**` push'unda koşar; ilk push'un Python 3.12 koşusu `success` (run `44326773886`, 9 dk 46 sn). |
| **TV/datafeed yedeği deploy'a dahil mi?** | **HAYIR.** Ölçüm kapısı henüz yeşil değil; `config.py` / `.env.example` / `requirements-deploy.txt` içinde TV bayrağı veya pin yok. Bu, mevcut sistemi **bloklamaz**. |
| **Şimdi deploy edilebilir mi?** | **EVET — mevcut yfinance sistemi için.** Aşağıdaki §6 adımlarıyla. |

## 1. Üretim veri hattı (değişmedi)

- `data/fetch.py::saglayici_adaylari` / `_fetch_yfinance_adaylari`: **yalnızca yfinance**.
- `config.py`: BIST endeksleri, makro ve `XAUUSD`/`XAGUSD` için Yahoo yedek sembolleri.
- `data/replay.py`, `data/seed_cache.py`, `data/__main__.py`: modüler `data/` paketi;
  kök `data.py` yok, doğru giriş `python -m data`.
- `data/fetch.py`, `bot/scan.py`, `bot/app.py`, `main.py`, `config.py` içinde
  **tvDatafeed / tradingview / tvdatafeed_client importu yok** (grep ile doğrulandı).
- TV kodu yalnızca şu ölçüm/araştırma yüzeylerinde:
  `scripts/tvdatafeed_client.py`, `scripts/saglayici_karsilastirma.py`,
  `scripts/backfill/capraz_piyasa_cek.py`. Bunlar `main.py` tarafından import edilmez.

## 2. Deploy yapılandırması

| Öğe | Durum |
|---|---|
| `.python-version` | `3.12` — Render'ın 3.14 varsayılanına karşı pandas/numpy tekerlek koruması |
| `render.yaml` | `buildCommand: bash scripts/install_deploy_dependencies.sh` · `startCommand: python main.py` · `healthCheckPath: /health` · `autoDeployTrigger: checksPass` |
| Build script | `pip==26.2` + `setuptools==84.1.0` → `-r requirements-deploy.txt` → `pip check` |
| Pinler | `yfinance==1.7.0`, `pandas==2.2.2`, `numpy==1.26.4`, `requests==2.34.2`, `matplotlib==3.11.2`, `pytest==9.0.3`, `python-dotenv==1.2.4` |
| TV bağımlılığı | **Yok.** Yalnız yorum satırında ölçüm için opsiyonel kurulum ipucu var |
| Sırlar | `render.yaml` içinde `sync: false` (Telegram token/chat/group, Supabase, webhook secret); depoda değer yok |
| `TZ` | `Europe/Istanbul` (BIST seansı + günlük sayaç sıfırlaması) |

> `render.yaml` **opsiyonel Blueprint**'tir. Dashboard'da servis zaten varsa
> Blueprint uygulamak ikinci servis / çift fatura / aynı Telegram'a iki bot
> üretir. Mevcut servis Dashboard > Settings'ten yönetilir.

## 3. Doğrulanan kapılar

| Kapı | Sonuç |
|---|---|
| `.venv/bin/ruff check .` | temiz |
| `python -m compileall -q .` | temiz |
| `python -m pip check` | `No broken requirements found.` |
| `git diff --check` | temiz |
| Tam `pytest -q` | **4448 passed / 43 skipped** (694,5 sn) |
| `test_tarama_zamani.py` | `102/102` |
| `test_triangle.py` / `breakout` / `flag` / `pennant` | 4/4 |
| `deploy_check.py --skip-network --grafik-test` | kare üretildi, stabil direnç + gönderilmeme kapıları geçti |
| `python -m data` | çevrimdışı duman testi geçti |
| `--mod tanis --tanis-dene 0`, `--mod arsiv` | ağa çıkmadan rapor üretti |
| `PORT=10000 BOT_HEALTH_SMOKE_ONLY=1 python main.py` | `/health 200`, `/ready 503`, `/test` 404, webhook 404 |
| GitHub Actions (Python 3.12) | ilk push `success`; son push'un koşusu §7'de |

Bağımsız regresyon scriptleri ve smoke, CI job'undaki aynı komutlarla yerelde
koşuldu; CI ile Render build komutu birebir aynı install scriptini kullanıyor.

## 4. TV ölçümü neden bu deploy'un parçası değil

Operatörün `PS C:\Projeler\Formation-Bot>` üzerindeki canlı ölçümü TV tarafının
çalıştığını gösterdi: `nologin` uyarısıyla WS bağlandı, 1g için **360 bar** geldi.
Ancak geçiş kapısı yeşil değil ve aşağıdaki bulgular bu turda düzeltildi:

1. **1g damga hizası** — Yahoo `00:00 İstanbul` etiketi ↔ TV `00:00 UTC` anı;
   `1d` de gün ızgarasına indirildi (`ortak_bar 0 → 360`).
2. **yfinance MultiIndex kolonları** — 4s referansı `KeyError` veriyordu;
   türetimden önce normalize edildi.
3. **`intersection` sahte eşleşmesi** — `freq`'li hızlı yol değer bazlı `isin`'e çevrildi.
4. **Fiyat düzeltmesi farkı (yeni)** — tvDatafeed WS `adjustment:"splits"` gönderir;
   yfinance varsayılan `auto_adjust=True` **temettüyü de** düzeltir. Canlı sonuçta
   `GARAN 4,041 / AKBNK 3,205 / EREGL 1,360` ve `medyan == max`, `fark_esik_asimi
   206/360` görüldü: sabit oranlı kayma = elma/armut kıyası. `_yahoo` artık
   `auto_adjust=False, actions=False` istiyor.
5. **Tek barlık kalite gürültüsü (yeni)** — `%33,15 → %33,33` farkı 0,01 puanlık
   sabit toleransla `red (adayda kısa bar fazla)` üretiyordu. Tolerans artık iki
   serinin bar sayısından (`100/n_ref + 100/n_aday`) hesaplanıyor; gerçek
   kötüleşme hâlâ `red`.
6. **Geçici WS hatası (yeni)** — `EREGL 4h` için `Connection to remote host was
   lost / no data` geldi. Ortak istemci artık yeni istemciyle **en fazla 2 deneme**
   yapıyor, her denemede WS'yi kapatıyor.
7. `0 bar geldi ✅` → `⚠️ 0 bar … Bu başarı değil`; `--referans` eklendi.

`--referans borsapy` ile THYAO/GARAN 1g `geç (0,000 / 0,000)` geldi; ancak borsapy
de TradingView WS tabanlı olduğu için bu **bağımsız referans değil**, yalnızca
çapraz kontroldür. Geçiş kapısının referansı yahoo olarak kalmalı.

**Karar:** kapı yeniden ölçülüp yeşil olmadan `data/fetch.py` / `bot/scan.py`
değiştirilmeyecek. Bu yüzden TV yedeği deploy'a **dahil edilmedi**; mevcut
sistemin deploy'u bundan etkilenmez.

## 5. Açık riskler (deploy'u bloklamaz)

1. **Yahoo `THYAO.IS: possibly delisted; no price data found (60d/2y)`** — harici
   sağlayıcı/kota sorunu. Üretimde sembol yedeği + `UNKNOWN` kapısı korunuyor;
   `docs/arastirma/CAPRAZ_PIYASA_UYGULAMA.md` fail-closed davranışı değişmedi.
2. **Anonim TradingView WS** tek sembolde geçici veri vermeyebilir; sınırlı yeniden
   deneme eklendi ama canlı tekrar doğrulanmadı.
3. **1g/4h geçiş kapısı yeşil değil** — `auto_adjust` düzeltmesi sonrası ölçümün
   operatör makinesinde tekrarlanması gerekir.
4. **Yerel Python 3.11.2 / CI-Render 3.12** farkı: pinler `pip check` ile temiz,
   CI 3.12'de yeşil; Render build'i aynı scripti kullanır.
5. **PowerShell `yerel_onar.ps1`** statik/BOM testleri geçti, PowerShell çalıştırılmadı.

## 6. Operatör için deploy adımları

```powershell
# 1) Son kodu al ve temiz olduğunu gör
git status --short --branch
git pull --ff-only origin arena/79b4d2e1-formation-bot

# 2) Kapıları yerelde son kez doğrula (opsiyonel; CI zaten koşuyor)
ruff check .
python -m pytest -q
python deploy_check.py --skip-network --grafik-test
```

Render Dashboard > ilgili Web Service:

- **Build Command:** `bash scripts/install_deploy_dependencies.sh`
- **Start Command:** `python main.py`
- **Health Check Path:** `/health`
- **Python:** repo `.python-version` = `3.12`
- **Env (Secret):** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
  `TELEGRAM_GROUP_ID`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- **`autoDeployTrigger: checksPass`** — CI yeşil olmadan deploy tetiklenmez.

Deploy sonrası:

```bash
curl -fsS https://<servis>/health      # 200 + JSON durum
curl -sS -o /dev/null -w '%{http_code}\n' https://<servis>/ready
```

`/ready` veri/Telegram hazır değilse `503` dönebilir; `/health` liveness içindir.

## 7. Son doğrulama kaydı

Son doğrulama (2026-11-18, Python 3.11.2 venv): `ruff` temiz · `pip check`
`No broken requirements found.` · `compileall` temiz · `git diff --check` temiz ·
tam pytest **4448 passed / 43 skipped** (694,5 sn) · ağsız `tanis`/`arsiv` rapor
üretti · `python -m data` geçti · `test_tarama_zamani.py` **102/102** · 4 bağımsız
formasyon scripti **4/4** · grafik doktoru `Kare üretildi: AKBNK 4h`, stabil
direnç çizildi, `Fotoğraf gönderilmedi` · HTTP smoke `/health 200`, `/ready 503`,
`/test 404`.

GitHub Actions: `6452a82` için Python 3.12 koşusu **success** (run
`44332184670`, 15 dk 44 sn); ilk push `87cb6ed` de **success** (`44326773886`,
9 dk 46 sn). Bu belgenin commit/push'u yeni bir CI koşusu tetikler.

**Özet: üretim veri sistemi ve testler deploy'a hazır; TV geçişi ayrı, ölçüm
bekleyen iştir.** Kesin kayıt `docs/denetim/GENEL_KONTROL_2026-11-18.md` §9'da.
