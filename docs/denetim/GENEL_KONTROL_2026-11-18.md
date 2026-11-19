# Genel kontrol — TV/datafeed ekleri ve depo geneli (2026-11-18)

**Dal:** `arena/79b4d2e1-formation-bot` · **HEAD:** `9cb439b0c13375f6fadaa8f4b4faaf97d03befb4`
(grafted tek commit; geçmiş diff yoktur, bu yüzden kod/doküman/testler tek tek okundu).
**Durum:** İlk tur `87cb6ed` ile `origin/arena/79b4d2e1-formation-bot` dalına
push edildi; GitHub Actions `CI (Render parity)` koşusu **success** (Python 3.12,
9 dk 46 sn / run `44326773886`). Operatörün Windows makinesindeki ilk canlı ölçüm
ardından §8'deki ikinci düzeltme turu yapıldı. Canlı Render/Telegram doğrulaması
yok; PR açılmadı.

## 1. Özet

Kullanıcı isteği: son eklenen TV/datafeed olayını incelemek, sorunlarını düzeltmek
ve ayrıca genel kontrol yapmak. Son ekler iki yüzeyde bulundu:

1. **Ölçüm/karar aracı:** `scripts/saglayici_karsilastirma.py`,
   `test_saglayici_karsilastirma.py`, `docs/tasarim/VERI_KAYNAGI_VE_TF_PLANI_2026-11-16.md`.
2. **Araştırma arşivi yedeği + yerel teşhis:** `scripts/backfill/capraz_piyasa_cek.py`,
   `test_capraz_piyasa_cek.py`, `scripts/yerel_onar.ps1`, Termux kurulum belgeleri.

Başlangıçta CI eşdeğeri kapılar yeşildi (4405 test geçti), fakat yeşil testler yeni
eklenen ölçüm aracındaki **karar kapısı ve zaman damgası** hatalarını yakalamıyordu.
Bu kontrol sırasında 6 ana kusur düzeltildi, 28 yeni regresyon testi eklendi ve aktif
belgelerdeki eski dal / sağlayıcı / `data.py` bilgileri gerçek kodla hizalandı.
Push sonrası operatörün gerçek TradingView verisiyle yaptığı ilk ölçüm üç yeni
kusuru daha ortaya çıkardı (§8): 1g damga hizası, yfinance MultiIndex kolonları ve
pandas `freq`'li `intersection` sahte eşleşmesi. Bunlar da düzeltildi; `4442 passed /
43 skipped` ile yeniden doğrulandı.

## 2. Yöntem ve yeniden üretilebilir komutlar

Yerel ortam: Python **3.11.2**, izlenmeyen `.venv` içinde
`requirements-deploy.txt` + `requirements-dev.txt` pinleri, `pip check` temiz.
CI/Render `.python-version` gereği Python **3.12** kullanır; bu rapor yerel
doğrulamadır, CI sonucu değildir.

```bash
bash scripts/install_deploy_dependencies.sh  # CI/Render ile aynı canlı pinler
python -m pip install -r requirements-dev.txt
ruff check .
python -m pytest -q
python test_tarama_zamani.py
python test_triangle.py && python test_breakout.py && python test_flag.py && python test_pennant.py
python deploy_check.py --skip-network --grafik-test
PORT=10000 BOT_HEALTH_SMOKE_ONLY=1 python main.py  # /health duman testi
```

Ağsız TV teşhisi ve arşiv ölçümü de ayrıca koşuldu:

```bash
python -m scripts.saglayici_karsilastirma --mod tanis --tanis-dene 0
python -m scripts.saglayici_karsilastirma --mod arsiv --veri-dizini bot_data
```

## 3. Kontrol sonuçları

| Kapı | Önce | Sonra |
|---|---|---|
| `ruff check .` | temiz | **temiz** |
| `python -m pip check` | bağımlılık kurulumu yoktu | **No broken requirements found** |
| `python -m compileall -q .` | temiz | **temiz** |
| `python -m pytest -q` | 4405 passed / 43 skipped | **4442 passed / 43 skipped** (696 sn; §8 sonrası son koşu) |
| Hedefli TV/veri testleri | 169 passed / 14 skipped | **121 passed** (6 dosya; ikinci tur dâhil) |
| `test_tarama_zamani.py` | — | **102/102** |
| `test_triangle/breakout/flag/pennant` | — | **4/4** bağımsız script geçti |
| `deploy_check.py --skip-network --grafik-test` | — | **Kare üretildi: AKBNK 4h**, stabil direnç ve gönderilmeme kapıları geçti |
| `/health` smoke | — | **/health 200**, `/ready 503`, `/test` 404, webhook 404, smoke guard temiz |
| `python -m data` | — | çevrimdışı duman testi geçti |
| `--mod tanis --tanis-dene 0` | varsayılan ağa çıkıyordu | **ağ denemesi yok**, iki kurulum ipucu yazıldı |
| `--mod arsiv` | — | yerel arşiv kalite raporu üretildi |
| `git diff --check` | — | **temiz** |

## 4. Bulgular ve yapılan düzeltmeler

### 4.1 Geçiş kapısı hacim/kısa-bar koşullarını uygulamıyordu (yanlış `geç`)

`karar_ver` yalnızca ortak bar oranı ve kapanış farkına bakıyordu. Üst bilgi ve
planda yazan **"adayda sıfır hacim referanstan kötü olmasın"** ile **"adayda kısa
bar referanstan kötü olmasın"** koşulları ölçülüp rapora yazılmasına rağmen kararda
kullanılmıyordu. Fiyat uyumu yeşilken hacim/kurgu bozulan aday `geç` alabilirdi.

**Düzeltme:** kalite metrikleri `karar_ver` içinde tolerate edilmiş yüzde puanıyla
denetleniyor; kötüleşme varsa gerekçeli `red (...)` dönüyor. Hem damga bazlı hem
gün ızgarası karşılaştırması aynı kapıdan geçiyor. Yeni testler sıfır hacim, kısa
bar ve eksik/None metrik durumlarını kilitliyor.

### 4.2 tvDatafeed zaman damgası iki scriptte farklı ve kırılgan işleniyordu

`tvDatafeed` 2.1.x `datetime.fromtimestamp` ile POSIX zamanını **çalışan makinenin
yerel naive saati** olarak verir. Ölçüm aracı bu damgayı doğrudan İstanbul sanıyor,
çapraz piyasa arşivi ise süreç genelinde `TZ=UTC` + `time.tzset()` ile düzeltiyordu.
İkinci yol Windows'ta çalışmaz (`time.tzset` yok), süreç TZ'sini bozar ve yalnız
`tradingview-datafeed==2.1.1` dağıtımını kabul ediyordu. Ölçüm aracı ayrıca
WebSocket'i kapatmıyordu ve `tvdatafeed` dağıtım adını ararken PyPI çatalını
görmüyordu.

**Düzeltme:** yeni `scripts/tvdatafeed_client.py` tek kaynak oldu.

* İki doğrulanmış dağıtım kabul edilir: PyPI `tradingview-datafeed==2.1.1` ve
  sabit GitHub commit'inin `tvdatafeed==2.1.0` dağıtımı.
* Naive yerel damga `dateutil.tz.tzlocal()` ile gerçek UTC'ye çevrilir; süreç TZ'si
  **değiştirilmez** (POSIX/Windows aynı davranır). tz-aware yeni sürümler de UTC'ye
  çevrilir.
* Boş/geçersiz yanıt, bilinmeyen aralık ve doğrulanmamış sürüm sessizce kabul edilmez.
* Her çağrıda açık WebSocket kapatılır; hata durumunda da kapanır.
* `scripts/saglayici_karsilastirma.py` ve `scripts/backfill/capraz_piyasa_cek.py`
  bu istemciye bağlandı; `normalize` artık doğru UTC → İstanbul dönüşümü yapıyor.

Ağsız testler İstanbul/UTC-ofset, tz-aware girdi, boş yanıt, çekme hatası, WS
kapanışı, iki dağıtım ve bilinmeyen sürümü kapsıyor. Gerçek TradingView WS çağrısı
yapılmadı.

### 4.3 `--mod tanis` dokümanın aksine varsayılan ağ denemesi yapıyordu

`tani()` varsayılanı `dene=False` iken CLI `--tanis-dene` varsayılanı `1` idi.
`scripts/yerel_onar.ps1` bu yüzden üç sağlayıcıya ağ denemesi yapabiliyordu.

**Düzeltme:** CLI varsayılanı `0`; gerçek çekme yalnızca `--tanis-dene 1`. Onarım
betiği açıkça `--tanis-dene 0` çağırıyor. Yeni CLI testi her iki yolu kilitliyor.

### 4.4 `yerel_onar.ps1` eski dala geçip yerel commitleri silebilirdi

Betik varsayılan olarak eski `arena/52b49b26-formation-bot` dalına geçiyor ve
`git reset --hard origin/$Dal` uyguluyordu. Aktif oturum dalında çalıştırılırsa
farklı bir dala geçer; uzaktan ileride yerel commit varsa bunları reflog'a düşürür.
"Hiçbir şey silinmez" notu bu durum için doğru değildi.

**Düzeltme:** varsayılan dal artık `git rev-parse --abbrev-ref HEAD` ile bulunur;
detached HEAD reddedilir; `origin/$Dal` doğrulanır; `git rev-list --count` ile
uzaktan ileride yerel commit varsa reset yapılmadan durulur. README ve statik test
bu sözleşmeyi koruyor.

### 4.5 Aktif kurulum belgelerinde sabit eski Arena dalı vardı

`docs/kurulum/TERMUX_BACKFILL.md`, `TERMUX_CAPRAZ_PIYASA.md` ve
`scripts/operational/save_real_data.py` eski oturum dallarını yazıyordu. Kullanıcı
bu komutları kopyalarsa çalışması gereken daldan çıkardı.

**Düzeltme:** aktif dal `$DAL` / `git branch --show-current` ile alınıyor; script
push ipucunu çalışma anındaki dala göre basıyor. Tarihsel denetim belgelerindeki
dal adları kayıt olduğu için bilinçli değiştirilmedi; statik test yalnızca aktif
kurulum yüzeylerini denetliyor.

### 4.6 Plan/belge ile kod birbirini yanlış anlatıyordu

* Plan "Karar: tvDataFeed reaktif yedek / 4s gerçek bar" diyordu; üretim
  `data/fetch.py` yalnızca `yfinance` kullanıyor, `veri_kaynagi` etiketleme ve
  gerçek 4s entegrasyonu yok.
* "tvDataFeed PyPI'de yok" ifadesi `tradingview-datafeed==2.1.1` için yanlıştı.
* Yerel kurulum rehberi "borsapy fallback" ve kök `data.py` diyordu; modülerleştirme
  sonrası üretimde borsapy importu yok ve paket `data/` altında.
* README ve Termux belgesi `data.py` / `python data.py` referansı taşıyordu.

**Düzeltme:** plan açıkça **geçiş taslağı / ölçüm kapısı** olarak işaretlendi,
uygulama durumu ve üretimde henüz olmayan maddeler yazıldı; kurulum/plan/
requirements yorumları iki dağıtımı doğru adlandırıyor; aktif belgeler `data/`
paketini ve `python -m data` komutunu kullanıyor. `docs/README.md` ve README'nin
"son genel kontrol" bağlantıları bu rapora güncellendi.

## 5. Değişen dosyalar

| Alan | Dosyalar |
|---|---|
| Yeni ortak TV katmanı | `scripts/tvdatafeed_client.py` |
| Ölçüm/karar | `scripts/saglayici_karsilastirma.py`, `test_saglayici_karsilastirma.py`, `test_tv_datafeed_docs.py` |
| Araştırma arşivi | `scripts/backfill/capraz_piyasa_cek.py`, `test_capraz_piyasa_cek.py` |
| İstemci sözleşmeleri | `test_tvdatafeed_client.py`, `conftest.py` (`istanbul_tz` fixture) |
| Yerel onarım / dal güvenliği | `scripts/yerel_onar.ps1`, `scripts/operational/save_real_data.py`, `test_yerel_onar_script.py` |
| Belgeler / pin yorumları | `README.md`, `docs/README.md`, `docs/tasarim/VERI_KAYNAGI_VE_TF_PLANI_2026-11-16.md`, `docs/kurulum/LOCAL_SETUP.md`, `docs/kurulum/TERMUX_BACKFILL.md`, `docs/kurulum/TERMUX_CAPRAZ_PIYASA.md`, `requirements*.txt` |

## 6. Açık kalan riskler (bilinçli olarak değiştirilmedi)

1. **Canlı reaktif yedek henüz yok.** tvDataFeed üretim `data/fetch.py` /
   `bot/scan.py` hattına bağlanmadı; 4s gerçek bar, `veri_kaynagi` etiketi ve
   türetilmiş bar düzeltmesi planda kaldı. Geçiş için canlı ölçüm kapısının yeşil
   olması, kaynak etiketleme ve deque/append senaryo testleri gerekir. Bu kontrol
   ölçüm aracını güvenli hale getirdi; üretim davranışını değiştirmedi.
2. **Gerçek TradingView fiyat karşılaştırması henüz yeşil değil.** Anonim WS
   erişimi operatör makinesinde **kısmen doğrulandı**: `nologin` uyarısıyla birlikte
   1g için 360 bar geldi (§8). Ancak ilk ölçüm referans/hizalama hataları nedeniyle
   `red` üretti; düzeltilmiş araçla yeniden koşulmadı. Sembol izinleri, IP kısıtı,
   gerçek 4h ızgarası ve fiyat uyumu açık kalmaya devam ediyor.
3. **Yerel Python 3.11.2 / CI 3.12 farkı.** Pinler `pip check` ile doğrulandı; ilk
   push'un CI koşusu 3.12 üzerinde **success**. İkinci turun CI koşusu ayrı tetiklenir.
4. **borsapy hâlâ opsiyonel ölçüm bağımlılığı.** Deploy zincirinde ve otomatik
   yedekte değil; planın "borsapy'yi fiyat kaynağı yapmama" kararı korundu.
5. **Tarihsel denetim belgeleri** kendi dallarını kayıt olarak taşır; aktif komut
   kaynağı `docs/README.md` ve güncel kurulum belgeleridir.

## 7. Sonuç

Yerel statik kapı, 4442 birim test, bağımsız regresyon scriptleri, grafik doktoru,
HTTP smoke ve ilk push'un Python 3.12 CI koşusu dahil **tüm kontrol edilen kapılar
yeşil**. TV/datafeed ekindeki yanlış `geç` kararı, platforma bağımlı zaman dönüşümü,
dağıtım/sürüm çelişkisi, WS sızıntısı, eski dal güvenliği ve §8'deki üç ölçüm
hatası düzeltildi. Kalan en önemli iş, planlanan reaktif yedeği canlı fetch hattına
taşımadan önce düzeltilmiş araçla gerçek TradingView ölçümünü yeşil geçirmektir.

## 8. Operatörün ilk canlı ölçümü ve ikinci düzeltme turu (aynı gün)

`PS C:\Projeler\Formation-Bot>` üzerinde `tradingview-datafeed==2.1.1` kurulduktan
sonra çalıştırıldı:

```powershell
python -m scripts.saglayici_karsilastirma --mod tanis --tanis-dene 1 --tanis-sembol THYAO
python -m scripts.saglayici_karsilastirma --mod canli --tf 4s 1g --sembol "THYAO,GARAN,AKBNK,ASELS,EREGL" --aday tvdatafeed --adet 360
```

**Gözlem:** `you are using nologin method...` uyarısıyla TradingView WS bağlantısı
kuruldu ve 1g için **360 bar geldi** → anonim erişim çalışıyor. Buna karşın raporun
tamamı `red` çıktı:

* `Deneme yahoo: 0 bar geldi ✅` → yanıltıcı başarı işareti; Yahoo veri vermedi.
* `THYAO`: `$THYAO.IS: possibly delisted; no price data found (60d/2y)` → Yahoo
  boş döndü. Harici sağlayıcı/kota sorunu, koddan düzeltilemez.
* `GARAN/AKBNK/ASELS/EREGL 4h`: `KeyError: "Column(s) ['close','high','low','open',
  'volume'] do not exist"` → yfinance'in MultiIndex kolonları `turet()` öncesinde
  düzleştirilmiyordu; 4s referansı hiç üretilemedi.
* `1g`: `ref_bar 360`, `aday_bar 360`, **`ortak_bar 0`** → Yahoo `00:00 İstanbul`
  tarih etiketi ile TV `00:00 UTC` (= `03:00 İstanbul`) anı damga damga
  kesişmiyordu. 2s/4s için var olan gün ızgarası 1g'de uygulanmıyordu.

**Kök neden kazısı sırasında üçüncü hata:** `DatetimeIndex.intersection`, `freq`
taşıyan düzenli ızgaralarda hızlı yola girip **hiç var olmayan damgaları ortak**
döndürebiliyor (pandas 2.2.2'de yeniden üretildi: `09:30` ızgarası ↔ `10:00`
ızgarası 5 sahte eşleşme verdi). Bu, ileride sahte `geç` üretebilecek sessiz bir
riskti; eşleşme değer bazlı `isin`'e çevrildi.

**Yapılan düzeltmeler:**

| Kusur | Düzeltme |
|---|---|
| 1g `ortak_bar 0` | `canli_karsilastir` artık `1d` için de `karsilastir_gunluk` (İstanbul takvim günü) kullanıyor |
| yfinance MultiIndex | `_kolon_adlari` + `normalize` kolonları düzleştiriyor; `_yahoo` türetimden **önce** normalize ediyor |
| `intersection` sahte eşleşmesi | `karsilastir` / `karsilastir_gunluk` değer bazlı `isin` kullanıyor |
| `0 bar geldi ✅` | teşhis artık `⚠️ 0 bar … Bu başarı değil` yazıyor |
| Hata teşhisi zor | `ortak_bar 0` olan kayıtlarda ilk ref/aday damgaları rapora ve `Ham:` JSON'una yazılıyor |
| Yahoo tek nokta | `--referans` seçeneği eklendi (Yahoo boşsa `1g` için `borsapy` çapraz kontrolü; borsapy 2s/4s desteklemez) |

**Doğrulama:** `ruff check .` temiz, `compileall` temiz, `git diff --check` temiz,
hedefli 6 dosya **121 passed**, tüm pytest **4442 passed / 43 skipped** (696 sn).
Son sağlamlaştırmada `('THYAO.IS','Close')` sıralı (ticker-ilk) MultiIndex de
desteklendi (+1 test); ruff/compileall/diff check ve hedefli 6 dosya **122 passed**
olarak yeniden yeşil. Tam pytest'in 4442'lik koşusu bu izole kolon eşleme
değişikliğinden önceydi; push'un CI koşusu 3.12 üzerinde tam seti tekrarlar.
Dokümanlar (plan §4/§5, `docs/README.md`) yeni ızgara/`--referans` davranışıyla
hizalandı. **Operatörün düzeltilmiş araçla ölçümü tekrarlaması gerekir**; üretim
`data/fetch.py` hattı hâlâ değiştirilmedi.

## 9. İkinci canlı ölçüm ve deploy hazırlığı (aynı gün)

Düzeltilmiş araçla aynı komut yeniden koşuldu. Hizalama düzeltmesi **çalıştı**:
1g için `ortak_bar 0 → 360` (`ortak_oran 1.0`), 4s için `60` ortak gün. Fakat
yeni, gerçek veriden gelen üç bulgu daha çıktı:

| Bulgular | Kök neden | Düzeltme |
|---|---|---|
| `GARAN 1d 4,041 / AKBNK 1d 3,205 / EREGL 1d 1,360` ve `medyan == max`, `fark_esik_asimi 206/360` | tvDatafeed `adjustment:"splits"`; yfinance varsayılan `auto_adjust=True` temettüyü de düzeltiyor → sabit oranlı elma/armut kıyası | `_yahoo` artık `auto_adjust=False, actions=False` |
| `4s: %33,15 → %33,33` → `red (adayda kısa bar fazla)` | 0,18 puan ≈ **tek bar**; sabit 0,01 puan tolerans | tolerans `100/n_ref + 100/n_aday` ile dinamik; gerçek kötüleşme hâlâ `red` |
| `EREGL 4h: Connection to remote host was lost / no data` | anonim WS geçici kopması | ortak istemci yeni istemciyle en fazla **2 deneme**, her denemede WS kapatılır |

`ASELS 1d geç (0,000 / 0,127)`, `THYAO 1d koşullu (0,000 / 1,030)`;
`--referans borsapy` ile THYAO/GARAN `geç (0,000/0,000)` geldi ama borsapy de
TradingView WS kullandığı için bu bağımsız referans **değildir**. THYAO 4h hâlâ
`red (yahoo boş döndü)` — harici Yahoo kota/sembol sorunu.

**Deploy kararı:** üretim `data/fetch.py` / `bot/scan.py` / `config.py` /
`requirements-deploy.txt` bu turda da değişmedi; TV yedeği eklenmedi. Mevcut
yfinance sistemi için deploy hazırlığı tamamlandı. Ayrıntılı kontrol listesi,
Render build/start/env ayarları ve operatör adımları
[`docs/denetim/DEPLOY_HAZIRLIK_2026-11-18.md`](DEPLOY_HAZIRLIK_2026-11-18.md)'de.
**Geçiş kapısı hâlâ yeşil değil:** `auto_adjust` düzeltmesi sonrası canlı ölçümün
operatör makinesinde tekrarlanması gerekir.

**Deploy hazırlığı doğrulaması:** `ruff` / `compileall` / `pip check` /
`git diff --check` temiz; tam pytest **4448 passed / 43 skipped** (694,5 sn);
`tanis`/`arsiv` ağsız, `python -m data`, timing **102/102**, 4 bağımsız script
**4/4**, grafik doktoru ve `/health` smoke yeşil. `6452a82` CI koşusu Python 3.12'de
**success** (run `44332184670`, 15 dk 44 sn). Üretim `data/fetch.py` hattı hiçbir
committe değişmedi.

## 10. TV + Yahoo tam üretim / deploy entegrasyonu (aynı gün, üçüncü tur)

Kullanıcı ölçüm kapısını `Yeşil` ilan etti ve TV'nin yalnızca ölçümde değil
**tam süreçte** olmasını istedi. §9'daki "TV deploy dışında" kararı bu turda
kapatıldı; önceki kök neden düzeltmeleri korundu.

| Katman | Değişiklik |
|---|---|
| `config.py` | `TV_YEDEK_AKTIF`, `TV_GERCEK_4S_AKTIF`, `TV_EXCHANGE`, `TV_BAR_SAYISI`, `TV_ZAMAN_ASIMI_SN`, `TV_ARALIK`, `TV_SEMBOL_TURLERI`, ortak `_env_bayrak` |
| `data/fetch.py` | `_veri_zinciri` (Yahoo → TV → fail-closed), `_tv_yedek_dene` (25 sn sınırlı, UTC-aware zorunlu, OHLCV temizliği), `saglayici_durumu`, `son_veri_kaynagi`, `fetch_tv_4h`; `1h/1d/chart_data` aynı zincirden geçer |
| `data/replay.py` | `resample_all_timeframes(..., df_4h_native=...)`; geçersiz native 4s türetime geri düşer |
| `bot/scan.py` | `_zaman_dilimlerini_hazirla`: yalnızca TV yedeği devredeyken gerçek 4s çekilir |
| `bot/commands.py` | `/health` → `veri_saglayicilari`; `/ready` ve `?strict=1` kapıları değişmedi |
| Deploy | İki `requirements*.txt` dosyasına `tradingview-datafeed==2.1.1` + `websocket-client==1.9.2`; `render.yaml` env bayrakları; `.env.example`; aynı installer CI/Render |
| Doküman | `docs/denetim/DEPLOY_HAZIRLIK_2026-11-18.md` tam yol olarak yeniden yazıldı; plan/kurulum/README index güncellendi |

**Yeni regresyonlar:** `test_tv_yahoo_uretim_zinciri.py` 39 ağsız senaryo
(Yahoo birincil, boş/kalıcı/geçici hata, TV kurtarma, ikisi de yok, 5 geçersiz
frame, makro kısıtı, şalter, zaman aşımı, naive reddi, UTC→İstanbul, WS
kapanışı, gerçek 4s, cache tekilleştirme, strict health, `veri_yok_modu`,
`STRICT_UNKNOWN`, pin/CI/Render parity). `conftest.py` testlerde ağa çıkışı
önlemek için `TV_YEDEK_AKTIF`'i config'ten önce zorla kapatır.

**Doğrulama:** `ruff`, `pip check` (TV pinleri kurulu), `compileall`,
`git diff --check` temiz; tam pytest **4525 passed / 43 skipped** (668,14 sn);
yeni dosya **39 passed**; doküman/deploy/render hedefli 4 dosya **88 passed**;
`dogrulanmis_surum() == ('tradingview-datafeed','2.1.1')`; grafik doktoru,
`/health` smoke, çevrimdışı `tanis`/`arsiv`, timing **102/102** ve 4 bağımsız
script **4/4**. Push `8707efa` CI run **`44346289337` success** (Python 3.12,
15 dk 8 sn, 10/10 job). Ajan tarafında canlı Yahoo/TradingView çağrısı yok;
entegrasyon kanıtı kod + testlerdir, operatörün `var\tv_olcum4.md` canlı teyidi
ayrıdır. Fiili Render deploy / PR yapılmadı.

## 11. Deploy + bildirim uçtan uca ikinci denetim (2026-11-18)

Aynı gün gelen *"deploy sürecini her türlü baştan sona incele, sorunları düzelt,
bildirim gönderme sürecini de incele"* isteği ayrı bir denetim raporuna taşındı:
[`DEPLOY_BILDIRIM_DENETIMI_2026-11-18.md`](DEPLOY_BILDIRIM_DENETIMI_2026-11-18.md).
Build/start/env pinleri, Python 3.12 CI↔Render parity, `/health`/`/ready`,
webhook/polling, Telegram komutları, Supabase read-only, veri/cache/tarama,
DM/public alarm-bülten-grafik ve kalıcı teslim kuyrukları birlikte okundu.

Düzeltmeler: doktor public-only ve TV/runtime env körlükleri, public-only test
mesajı/fotoğrafı, koşullu Supabase uyarısı, `/health.bildirim` public/inceleme
sayaçları, tarama dışı periyodik public bülten flush'ı, opt-in ve tek anahtarla
sınırlı `state:notification_delivery` uzak yedeği, Blueprint'te 120 sn graceful
shutdown, CI smoke JSON assert'i ve sıra bağımlı `daily_stats` kirliliği. Varsayılan
Supabase modu hâlâ tam salt okunur; genel cache/state/mirror yazımları açılmadı.
Yeni 16 ağsız regresyon; tam pytest **4557 passed / 43 skipped**; doktor/grafik
**53 tamam / 0 hata**; gerçek entrypoint HTTP smoke. Push `bef9008` CI run
**`44366863050` success** (9 dk 50 sn, 10/10 adım). Gerçek Render deploy/PR ve
canlı Telegram/Yahoo/TV/Supabase çağrısı yoktur.

## 12. NATIVE 1h/2h/4h/1d replay veri zinciri (2026-11-19)

Kullanıcı 170+ sembolde 2h/4h'nin 1h'den `resample_ohlcv` ile türetilmesinin
hacim/fiyat kayması ürettiğini bildirdi; dört TF'nin de **native** çekilmesini,
mevcut mum çekme/kurulum betiğinin düzenlenmesini ve Termux'taki yerel klondan
`pull → bağımlılık → probe/pilot → tam çekim → doğrulama → commit/push → ajana
haber` komutlarını istedi. Üç kapsam kararı kullanıcıdan alındı: **karma kaynak**
(1h/1d Yahoo + 2h/4h TradingView), **CSV'ler + manifest push**, **replay şimdi
yok — önce veriler gelecek**.

| Katman | Değişiklik |
|---|---|
| Yeni `scripts/backfill/native_kaynak.py` | Kaynak planı, TV sembol eşlemesi, lazy ortak istemci, UTC→İstanbul, OHLCV normalizasyonu, WS hata sınıflandırması |
| `scripts/backfill/yahoo_backfill.py` | Varsayılan `1h,2h,4h,1d`, `--tv-bar-sayisi/--tv-exchange`, iki sağlayıcılı probe, native etiketli manifest, `kaynak_raporu.json`, kaynak/native resume kapısı, gerçek `--retry-failed` |
| `research/arsiv.py` | `KAYNAK_INTERVAL` identity, `arsiv_modu`, `arsiv_kaynak_plani`, dört dosya şartı, `tf_frame(..., legacy_resample=False)` strict native okuma |
| Replay/rapor | `arastirma_kosu.py` strict native + kaynak/TF rapor notları; `dz_yukleme.py` 4 TF `dz_bars` etiketi + `kapsam_raporu.json` native alanları |
| Termux | `requirements-termux.txt` + `setup-termux.sh` içine `tradingview-datafeed==2.1.1`, `websocket-client==1.9.2` ve dağıtım doğrulaması; `TERMUX_BACKFILL.md` baştan yazıldı |
| Doküman | `NATIVE_TF_REPLAY_PLANI_2026-11-18.md` eklendi; eski `DZ_REPLAY_SONUCLARI_2026-10-28.md` legacy türetim uyarısıyla işaretlendi; plan/README index güncellendi |

**Kanıt:** `ruff`, `pip check`, `compileall`, `bash -n`, `git diff --check` temiz;
hedefli 8 dosya **256 passed**; tam pytest **4585 passed / 43 skipped**
(513,07 sn). İlk tam koşuda `test_yerel_onar_script.py` sabit Arena dalı
bulduğu için 1 doküman testi kırmızıydı; `TERMUX_BACKFILL.md` dinamik
`DAL="$(git branch --show-current)"` ile düzeltildi ve tam suite yeşil döndü.
Push `96bd20b` (17 dosya, 1617+/423-); CI run **`44508629441` success**
(Python 3.12, 10 dk 9 sn, 10/10 adım, head `96bd20b8b4c7002e503726f4f9bac135447acb27`).

**Sınır (§13 ile güncellendi):** Ajan canlı Yahoo/TradingView/Supabase/Telegram/Render çağrısı,
fiili Render deploy veya PR yapmadı. 170+ sembolün gerçek çekimi ve `backfill_data/`
commit/push'u kullanıcının Termux'unda 2026-11-19'da tamamlandı; ayrıntı §13'tedir.
Bu turda replay komutu verilmedi; `docs/kurulum/TERMUX_BACKFILL.md` akışı
bilerek replay içermez. Bağlı uygulamalar kapalı ve kullanılmadı.


## 13. NATIVE veri arşivinin gelişi ve doğrulanması (2026-11-19)

§12'de "Termux'ta/sonraki turda" denilen çekim gerçekleşti. Kullanıcının yerel
klonundan iki commit geldi: **`8a18fbd`** (176 sembol × 4 native TF + manifest,
probe ve kaynak raporu) ve **`6cb80eb`** (ikinci kayıt; dokuz alakasız debug
dosyası da içeriyor). Ayrıntılı rapor:
[`NATIVE_VERI_GELISI_2026-11-19.md`](NATIVE_VERI_GELISI_2026-11-19.md).

| Kapı | Sonuç |
|---|---|
| Probe / liste | **176 geçerli / 10 geçersiz**, 176 benzersiz satır |
| Kaynak planı | `1h`/`1d` Yahoo · `2h`/`4h` tvDatafeed `2.1.1` |
| `kaynak_raporu.json` | `native`, `native_zorunlu=True`, **704/704**, `eksik=0`, `resample_kullanildi=False` |
| Kayıt özeti | 176 × 4 `ok`; `1h\|yahoo`, `1d\|yahoo`, `2h\|tvdatafeed`, `4h\|tvdatafeed` |
| `manifest.son_kosu` | **704 `ok`**, `gecici=0`, `kalici=0`, ban durdurmadı, 3579.6 sn |
| Strict kesişim | Dört dosyası olan **176** sembol = doğrulanmış liste; `BRENT` yok |
| Örnek CSV | `TCELL_2h` 1500 bar / 120 dk, `TCELL_4h` 1500 bar / 240 dk, tüm `bar_time` `+03:00` |
| Boyut | `backfill_data/` **20M** |

İlk probe'da TV WS boş yanıtıyla düşen 12 sembol (`TCELL`, `TOASO`, `DOAS`,
`SNGYO`, `CANTE` dahil) kısa yeniden probe ile **12/0** kurtarıldı; 164/22
sonucu 176/10'a yükseldi. Kalıcı 10 sembol `BRENT` + 9 Yahoo-boş semboldür;
bunlar için 2h/4h dosyası üretilmedi ve strict replay'e girmezler.

**Sınır:** Ajan verileri üretmedi, yalnızca gelen dosyaları okudu; canlı
Yahoo/TradingView/Supabase/Telegram/Render çağrısı, fiili Render deploy, PR,
tam pytest veya CI watch yoktur. `6cb80eb` ile giren 9 debug/backup dosyası
veri doğrulamasını etkilemez; ayrı temizlik onayı bekliyor. **Replay koşulmadı**;
native seriler hazır, replay ayrı turda.
