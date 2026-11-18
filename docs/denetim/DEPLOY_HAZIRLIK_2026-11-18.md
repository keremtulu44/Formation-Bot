# TV + Yahoo tam üretim / deploy yolu — 2026-11-18

**Dal:** `arena/79b4d2e1-formation-bot` (aktif) · **Hedef:** Render Web Service,
Python 3.12 · **Kapsam:** Yahoo birincil + TradingView (`tvDatafeed`) reaktif
yedeğinin **tüm üretim hattına ve deploy zincirine** oturtulması.

> **Bu belge aynı günün ilk "deploy hazırlığı" kararını geçersiz kılar.** İlk
> turda TV ölçüm kapısı yeşil sayılmadığı için bilinçli olarak deploy dışında
> tutulmuştu. Kullanıcının `Yeşil` beyanıyla kapı operatör tarafından açıldı;
> bu turda `config.py`, `data/fetch.py`, `data/replay.py`, `bot/scan.py`,
> `bot/commands.py`, `requirements*.txt`, `render.yaml` ve `.env.example`
> birlikte değiştirildi. TV artık **opsiyonel ölçüm scripti değil**, Yahoo
> veri döndürmediğinde devreye giren üretim yedeğidir.

## Kısa cevap

| Soru | Cevap |
|---|---|
| **Veri sistemi hazır mı?** | **EVET.** `yfinance` birincil; BIST hisse/endeks için `tvDatafeed` reaktif yedek. İkisi de veri vermezse uydurma yok, `None` + mevcut "veri yok" kapıları. |
| **TV deploy'a tam oturdu mu?** | **EVET.** `tradingview-datafeed==2.1.1` + `websocket-client==1.9.2` hem `requirements.txt` hem `requirements-deploy.txt` içinde sabit; aynı installer CI ve Render'da koşuyor. |
| **Yahoo hâlâ birincil mi?** | **EVET.** Yahoo başarılıyken **hiçbir TV/WS çağrısı yapılmaz**; ek ağ maliyeti yalnızca Yahoo boş/geçersiz döndüğünde oluşur. |
| **Gerçek 4s barları kullanılıyor mu?** | **EVET, TV yedeği devredeyse.** `TV_GERCEK_4S_AKTIF=1` ile TradingView native 4s, 1s'den türetilmiş 4s'in yerine geçer; alınamazsa türetim korunur. |
| **Testler hazır mı?** | **EVET.** `ruff`, `pip check`, `compileall`, `git diff --check`, tam pytest **4525 passed / 43 skipped** (668 sn), 39 yeni entegrasyon senaryosu, grafik doktoru, `/health` smoke, çevrimdışı replay. |
| **CI / Render parity hazır mı?** | **EVET.** `.python-version=3.12`; `scripts/install_deploy_dependencies.sh` CI ve `render.yaml` tarafından birebir kullanılıyor; `pip==26.2` → `setuptools==84.1.0` → `-r requirements-deploy.txt` → `pip check`. Entegrasyon commit'i `8707efa` CI run **`44346289337` success** (15 dk 8 sn, Python 3.12, 10/10 job ✓); önceki `4292ecf` run `44337872706` de **success**. |
| **Fiilen Render'a deploy edildi mi?** | **HAYIR.** Bu çalışma kod/push ile sınırlı; `autoDeployTrigger: checksPass` yalnızca Blueprint yönetilen servis için tetiklenir. Operatör adımları §8'de. |

## 1. Üretim veri akışı

```
fetch_yfinance_1h / 1d / chart_data(stock, ...)
        │
        ▼
_veri_zinciri()  ──►  _fetch_yfinance_adaylari()   [Yahoo: auto_adjust=False]
        │                     │
        │                başarılı ► frame.attrs = {
        │                     │        "veri_kaynagi": "yahoo",
        │                     │        "saglayici_zinciri": ["yahoo"],
        │                     │        "gercek_bar": False }
        │                     │        → TV çağrılMAZ
        │
        └── boş / kalıcı hata / geçici hata
                        ▼
              _tv_yedek_dene()  [yalnız BIST hisse + endeks]
                        │  • TV_YEDEK_AKTIF=1
                        │  • TV_ZAMAN_ASIMI_SN=25 (daemon thread + join)
                        │  • scripts/tvdatafeed_client.get_hist()
                        │      – doğrulanmış dağıtım/sürüm
                        │      – en fazla 2 WS denemesi, her denemede ws.close()
                        │      – naive yerel saati tzlocal() ile GERÇEK UTC'ye
                        │      – tz-aware UTC DatetimeIndex döner
                        │  • üretim hattı naive indeksi REDDEDER (fail-closed)
                        │  • UTC → Europe/Istanbul, OHLCV temizliği
                        ▼
              frame.attrs = { "veri_kaynagi": "tvdatafeed",
                              "saglayici_zinciri": ["yahoo","tvdatafeed"],
                              "gercek_bar": True, "provider_fallback": True }
                        │
                        ▼
        bot/scan.py::_zaman_dilimlerini_hazirla()
              ├─ Yahoo → resample_all_timeframes(df_1h)
              └─ TV    → fetch_tv_4h(stock)
                         → resample_all_timeframes(df_1h,
                                                   df_4h_native=gercek_4s)
                           2s ve 1g yine 1s'den türetilir
                        │
           ikisi de başarısız ► None + retryable/gerekçe
                              ► veri_yok_modu / cache tazeliği / UNKNOWN kapıları
```

**Değişmeyen sözleşmeler:** Yahoo kendi içindeki sembol yedeği
(`PROVIDER_SYMBOL_FALLBACK`) önce denenir; geçici Yahoo hatasında `retryable`
korunur ama TV kurtarırsa yeniden deneme gerekmez; hiçbir katman sentetik bar
üretmez. `data/seed_cache.py::append_dataframe` farklı kaynaklardan gelen aynı
zaman damgasını tekilleştirir, `to_dataframe` tek TZ kovasına indirger.

## 2. Kaynak etiketi ve gözlemlenebilirlik

* `frame.attrs["veri_kaynagi"]` → `"yahoo"` veya `"tvdatafeed"`.
* `frame.attrs["saglayici_zinciri"]` → `["yahoo"]` / `["yahoo","tvdatafeed"]`.
* `frame.attrs["gercek_bar"]`, `["gercek_4h"]`, `["tv_exchange"]`,
  `["provider_fallback"]` TV tarafında doldurulur.
* `data.fetch.saglayici_durumu()` süreç içi sayaçları döndürür:
  `yahoo_basari`, `yahoo_hata`, `tv_basari`, `tv_hata`, `yok`,
  `son_kaynak`, `son_kaynak_by_symbol`, son başarı/hata zamanları,
  `tv_aktif`, `tv_kurulu`, `tv_dagitim` (metadata ile doğrulanır).
* `bot/commands.py::_saglik_ozeti` bunu `/health` → `veri_saglayicilari`
  alanına ekler; `/ready` 503 davranışı ve `?strict=1` heartbeat-bayatlık 503
  kapısı **değişmedi** (yeni regresyon testiyle doğrulandı).

## 3. Kalite / tazelik / UNKNOWN kapıları

| Kapı | Uygulama |
|---|---|
| Fiyat ölçeği | Yahoo `history(..., auto_adjust=False)`; tvDatafeed WS `adjustment:"splits"`. İkisi de ham kapanış → elma/elma. |
| OHLCV | `_saglayici_ohlcv_temizle`: NaN/sonsuz, ≤0 fiyat, zarf ihlali, 0-hacimli hayalet günlük bar ayıklanır; ayıklanan satır `attrs` ile loglanır. |
| Zaman | Ortak istemci tz-aware UTC döner; üretim İstanbul'a çevirir. Naive indeks **reddedilir** (DST/ortam TZ'sine göre uydurma yok). Süreç `TZ` değiştirilmez. |
| WS | `scripts/tvdatafeed_client.py`: `DENEME_SINIRI=2`, her denemede yeni istemci, `finally: ws.close()`, boş/geçersiz frame → `ValueError`. |
| Süre | `TV_ZAMAN_ASIMI_SN=25`; takılan WS taramayı bloke etmez, daemon thread + `join`. |
| Tazelik | `VERI_YOK_MODU_ESIK_DK=20s`, `STALE_BAR_UYARI_DK`, seans açık/kapalı ayrımı, split süreklilik kontrolü, gece mum temizliği aynen korunur. |
| STRICT_UNKNOWN | `docs/arastirma/CAPRAZ_PIYASA_UYGULAMA.md` kuralları geçerli: doğrulanmamış bağlam `unknown` kalır, `--availability` dışında varsayım yok. |
| Kapsam | TV yalnızca `sembol_turu ∈ {hisse, endeks}` için; makro (`XAUUSD`, `BRENT`, `USDTRY`...) Yahoo'nun kendi vadeli yedeğiyle kalır. |

## 4. Deploy parity (CI = Render = yerel)

| Öğe | Değer |
|---|---|
| `.python-version` | `3.12` — pandas 2.2.2 / numpy 1.26.4 cp314 derleme düşmesini engeller |
| Installer | `scripts/install_deploy_dependencies.sh`: `pip==26.2` + `setuptools==84.1.0` → `-r requirements-deploy.txt` → `pip check` |
| CI | `.github/workflows/ci.yml` aynı installer'ı `run:` ile çağırır; `arena/**` push'unda koşar. `8707efa` → run `44346289337` **success** (15 dk 8 sn): ruff, tam pytest, kurulum doktoru + grafik, zamanlama, 4 formasyon scripti ve `/health` duman testi dahil tüm job'lar yeşil |
| Render | `buildCommand: bash scripts/install_deploy_dependencies.sh` · `startCommand: python main.py` · `healthCheckPath: /health` · `autoDeployTrigger: checksPass` |
| Pinler | `requirements.txt` **ve** `requirements-deploy.txt`: `tradingview-datafeed==2.1.1`, `websocket-client==1.9.2` (set eşitliği `test_deploy_workflows.py` ile korunur) |
| Diğer canlı pinler | `yfinance==1.7.0`, `pandas==2.2.2`, `numpy==1.26.4`, `requests==2.34.2`, `matplotlib==3.11.2`, `pytest==9.0.3`, `python-dotenv==1.2.4` |
| Env | `TV_YEDEK_AKTIF=1`, `TV_GERCEK_4S_AKTIF=1`, `TV_EXCHANGE=BIST`, `TV_ZAMAN_ASIMI_SN=25`, `TZ=Europe/Istanbul` |
| Sırlar | `render.yaml` içinde `sync: false`; depoda token/chat/Supabase değeri yok |

> `tvdatafeed` **adıyla** PyPI paketi yoktur; aynı `tvDatafeed` import modülünü
> sağlayan PyPI çatallı dağıtım sabitlendi. Sabit GitHub commit alternatifi
> (`tvdatafeed==2.1.0`) ortak istemci tarafından da kabul edilir ama deploy
> manifestinde kullanılmaz. `render.yaml` **opsiyonel Blueprint**'tir:
> Dashboard'da servis varsa uygulamak ikinci servis / çift fatura üretir.

## 5. Ortam anahtarları

| Anahtar | Varsayılan | Anlamı |
|---|---|---|
| `TV_YEDEK_AKTIF` | `1` | `0` → eski Yahoo-only davranış; TV hiç çağrılmaz |
| `TV_GERCEK_4S_AKTIF` | `1` | `0` → 4s her zaman 1s'den türetilir |
| `TV_EXCHANGE` | `BIST` | TradingView borsa kodu |
| `TV_BAR_SAYISI` | `500` | `5d`/`1d` kısa çekimde 60/30'a iner |
| `TV_ZAMAN_ASIMI_SN` | `25` | Tek TV çağrısının üst sınırı |

Bayrak yorumlayıcısı `config._env_bayrak`: `0/false/off/no/none/hayir/kapalı`
değerleri kapalı, diğerleri açık. `conftest.py` testler sırasında ağa çıkışı
önlemek için `TV_YEDEK_AKTIF`'i config importundan **önce** zorla `0` yapar;
yeni entegrasyon testleri `data.fetch.TV_YEDEK_AKTIF`'i sahte istemciyle açar.

## 6. Çok yönlü testler

`test_tv_yahoo_uretim_zinciri.py` **39 ağsız senaryo**:

1. **Yahoo birincil:** 1h/1d başarı, TV hiç çağrılmaz, `auto_adjust=False`, kaynak etiketi.
2. **Geçiş:** boş / kalıcı hata / geçici hata → TV; `retryable` korunur veya TV kurtarınca sıfırlanır; 1d + grafik yolları da TV'ye düşer; `frame_validator` TV'yi de reddedebilir.
3. **Fail-closed:** ikisi de yok → `None` + gerekçe, sayaçlar, `son_kaynak=None`; 5 geçersiz TV yanıtı; makro atlandı; şalter kapalı; WS zaman aşımı; naive damga reddi; UTC→İstanbul dönüşümü.
4. **WS / 4s:** ortak istemcinin gerçek koduyla `ws.close()` her denemede; native 4s türetilmişin yerine geçer; geçersiz native → türetime geri düşer; kapalı şalterde ek çağrı yok.
5. **Tarama katmanı:** `_zaman_dilimlerini_hazirla` Yahoo'da TV çağırmaz, TV'de native 4s verir, TV 4s hatasında türetimi korur.
6. **Cache / health / strict:** karma kaynaklı append tekilleşir ve sıralanır; `/health` yeni alanı + `?strict=1` bayatlık kapısı; `veri_yok_modu` 21s'de açık / 30dk'da kapalı; `STRICT_UNKNOWN` kılavuzu.
7. **Deploy parity:** iki manifestte aynı TV pinleri, `.env.example`, `render.yaml`, installer/CI, ortak istemci belgesi, doğrulanmış sürüm metadata'sı.

Mevcut regresyonlar da yeniden koştu: `test_scan_pacing`,
`test_grafik_veri_guvenilirligi`, `test_deploy_workflows`,
`test_health_server`, `test_kaynak_ve_guvenlik`, `test_live_data_flow`,
`test_capraz_piyasa_replay`, `test_tvdatafeed_client`,
`test_saglayici_karsilastirma`, `test_bist_calendar_regressions`.

### Sonuçlar

| Kapı | Sonuç |
|---|---|
| `.venv/bin/ruff check .` | `All checks passed!` |
| `python -m pip check` | `No broken requirements found.` (TV pinleri kurulu) |
| `python -m compileall -q .` | temiz |
| `git diff --check` | temiz |
| Tam `pytest -q` | **4525 passed / 43 skipped** (668,14 sn) |
| Yeni entegrasyon dosyası | **39 passed** |
| `test_tv_datafeed_docs.py` + deploy/render/docs | **88 passed** (4 dosya) |
| `scripts/tvdatafeed_client.dogrulanmis_surum()` | `('tradingview-datafeed', '2.1.1')` |
| `tvDatafeed.Interval` | `in_1_hour / in_2_hour / in_4_hour / in_daily` mevcut |
| `python -m data` | çevrimdışı duman testi geçti |
| `--mod tanis --tanis-dene 0` | `tvdatafeed: ok`, dağıtım `tradingview-datafeed 2.1.1 (doğrulandı)`; `borsapy` opsiyonel yok (beklenen iz) |
| `--mod arsiv` | 28 sembol / 10080 bar, ağsız rapor |
| `test_tarama_zamani.py` | **102/102** |
| 4 bağımsız formasyon scripti | **4/4** `TÜM KONTROLLER GEÇTİ` |
| `deploy_check.py --skip-network --grafik-test` | `✅ 39 tamam · ⚠️ 7 uyarı · ❌ 0 hata`; kare `AKBNK 4h · 68 mum`, `Fotoğraf gönderilmedi`. Stabil direnç uyarısı `UNAVAILABLE/missing_source` bu çevrimdışı tohumda beklenen uyarıdır, hata değildir |
| `BOT_HEALTH_SMOKE_ONLY=1 PORT=10011 python main.py` | `/health 200`, `/ready 503`, `/test 404`, `/health?strict=1 200` (henüz heartbeat yok). Yanıtta `veri_saglayicilari.tv_kurulu=true`, `tv_dagitim="tradingview-datafeed==2.1.1"`, `tv_aktif=true`, `yahoo_birincil=true` |
| GitHub Actions (Python 3.12) | `8707efa` → run `44346289337` **success** (15 dk 8 sn); installer/ruff/pytest/doktor/zamanlama/4 script/`/health` job'larının tamamı ✓ |

## 7. Komutlar (PowerShell, `PS C:\Projeler\Formation-Bot>`)

```powershell
# 1) Dalı tazele (cd YOK; zaten doğru klasördesin)
git fetch origin
git switch arena/79b4d2e1-formation-bot
git pull --ff-only origin arena/79b4d2e1-formation-bot

# 2) Yerel ortamı deploy pinleriyle eşitle
$py = ".\.venv\Scripts\python.exe"; if (-not (Test-Path $py)) { $py = "python" }
& $py -m pip install -r .\requirements-deploy.txt
& $py -m pip check

# 3) Hızlı doğrulama (ağsız)
& $py -m pytest -q test_tv_yahoo_uretim_zinciri.py test_tv_datafeed_docs.py test_deploy_workflows.py
& $py -m ruff check .
& $py -m compileall -q .

# 4) Çevrimdışı tanı / arşiv ve modüler data paketi
& $py scripts\saglayici_karsilastirma.py --mod tanis --tanis-dene 0
& $py -m data

# 5) Operatör canlı ölçümü (istersen; ölçüm kapısını tekrar görmek için)
New-Item -ItemType Directory -Force .\var | Out-Null
& $py scripts\saglayici_karsilastirma.py --mod canli --tf 4s 1g --sembol "GARAN,AKBNK,ASELS,EREGL" --aday tvdatafeed --adet 360 --cikti "var\tv_olcum4.md"
Get-Content .\var\tv_olcum4.md -Encoding UTF8

# 6) Grafik doktoru + /health smoke
& $py deploy_check.py --skip-network --grafik-test
$env:PORT = "10000"; $env:BOT_HEALTH_SMOKE_ONLY = "1"; & $py main.py
```

> `main.py` smoke'unu ayrı terminalde başlatıp `Invoke-RestMethod
> http://127.0.0.1:10000/health` ile kontrol et; `/ready` başlangıçta 503
> döner (beklenen), `?strict=1` heartbeat bayatsa 503 döner.

Linux / CI tarafı için aynı kapılar:

```bash
bash scripts/install_deploy_dependencies.sh
python -m pytest -q
python deploy_check.py --skip-network --grafik-test
PORT=10000 BOT_HEALTH_SMOKE_ONLY=1 python main.py
```

## 8. Operatör deploy adımları

1. Bu commit `origin/arena/79b4d2e1-formation-bot` üzerine push edildi; CI
   (`arena/**`) Python 3.12 ile tam seti koştu ve **success** oldu
   (run `44346289337`, 15 dk 8 sn). `autoDeployTrigger: checksPass` yalnızca
   **Blueprint ile yönetilen** Render servisinde otomatik tetiklenir.
2. Dashboard'da mevcut servis varsa Blueprint'i **yeniden uygulamayın**;
   Settings > Environment içinde `TV_YEDEK_AKTIF=1`,
   `TV_GERCEK_4S_AKTIF=1`, `TV_EXCHANGE=BIST`, `TV_ZAMAN_ASIMI_SN=25`,
   `TZ=Europe/Istanbul` olduğunu doğrulayın. Build komutu installer'a işaret
   etmeli.
3. Deploy sonrası `/health` → `veri_saglayicilari.tv_kurulu=true`,
   `tv_dagitim="tradingview-datafeed==2.1.1"`, `tv_aktif=true` beklenir.
   `son_kaynak_by_symbol` hangi sembolün TV'ye düştüğünü gösterir.
4. Yahoo normale döndüğünde sayaçlar yeniden `yahoo` yazmalı; TV yalnızca
   gerektiğinde `tv_basari` artmalı. `yok` sayacı artıyorsa iki sağlayıcı da
   veri vermiyor demektir → `?strict=1` ve `veri_yok_modu` kapılarına bakın.
5. **Fiili Render deploy / PR bu çalışmada yapılmadı.** Bu belge kod, test ve
   yapılandırma hazırlığını kanıtlar; dağıtım operatör onayıyla gerçekleşir.

## 9. Dürüst kanıt sınırı

* Ajan tarafında bu turda **canlı Yahoo/TradingView çağrısı yapılmadı**; tüm
  entegrasyon testleri sahte `yfinance` + sahte `tvDatafeed` ile ağsız koştu.
* Kullanıcının `Yeşil` beyanı, operatör makinesindeki ölçüm kapısının açıldığı
  olarak alındı. Daha önceki iki canlı çıktıda bulunan `auto_adjust`, dinamik
  tolerans ve geçici WS kopması kök nedenleri `4292ecf` ile düzeltilmişti;
  düzeltilmiş aracın `var\tv_olcum4.md` çıktısı bu oturuma yapıştırılmadı.
* Bu nedenle "TV üretimde" ifadesi **kod + pin + 39 senaryo + tam pytest**
  kanıtına dayanır; "canlı TradingView'den bugün bar geldi" iddiası **değildir**.
  Canlı teyit §7.5 komutuyla operatör tarafından yapılır.

## 10. Tarihçe (aynı gün, ilk tur)

İlk deploy hazırlığında üretim `data/fetch.py` yfinance-only idi; TV yalnız
`scripts/saglayici_karsilastirma.py`, `scripts/backfill/capraz_piyasa_cek.py`
ve `scripts/tvdatafeed_client.py` içinde ölçüm/araştırma amaçlıydı. Operatörün
iki canlı ölçüm turunda şu kök nedenler bulunup düzeltildi: 1g gün ızgarası
(`ortak_bar 0 → 360`), yfinance MultiIndex kolonları, pandas `intersection`
sahte eşleşmesi (`isin`), `auto_adjust=True` temettü düzeltmesi
(`auto_adjust=False, actions=False`), tek barlık kalite gürültüsü (dinamik
tolerans) ve EREGL 4h geçici WS kopması (`DENEME_SINIRI=2`). O turun kararı
"mevcut yfinance sistemi hazır, TV deploy dışında" idi; **bu belge o kararı
kapatır**, düzeltmeleri korur ve TV'yi tüm sürece ekler.

İlgili belgeler:
[`GENEL_KONTROL_2026-11-18.md`](GENEL_KONTROL_2026-11-18.md) ·
[`DEPLOY_BILDIRIM_DENETIMI_2026-11-18.md`](DEPLOY_BILDIRIM_DENETIMI_2026-11-18.md) ·
[`VERI_KAYNAGI_VE_TF_PLANI_2026-11-16.md`](../tasarim/VERI_KAYNAGI_VE_TF_PLANI_2026-11-16.md) ·
[`LOCAL_SETUP.md`](../kurulum/LOCAL_SETUP.md) ·
[`CAPRAZ_PIYASA_UYGULAMA.md`](../arastirma/CAPRAZ_PIYASA_UYGULAMA.md)

> **Aynı gün ikinci tur:** Bildirim gönderme ve deploy sürecinin tamamı ayrıca
> [`DEPLOY_BILDIRIM_DENETIMI_2026-11-18.md`](DEPLOY_BILDIRIM_DENETIMI_2026-11-18.md)
> içinde denetlendi; doktor public-only kuralı, `/health.bildirim`, tarama dışı
> public flush, opt-in dar teslim yedeği ve 120 sn shutdown düzeltmeleri oradadır.
