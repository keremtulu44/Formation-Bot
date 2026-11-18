# Genel kontrol — TV/datafeed ekleri ve depo geneli (2026-11-18)

**Dal:** `arena/79b4d2e1-formation-bot` · **HEAD:** `9cb439b0c13375f6fadaa8f4b4faaf97d03befb4`
(grafted tek commit; geçmiş diff yoktur, bu yüzden kod/doküman/testler tek tek okundu).
**Durum:** Yerel doğrulama + düzeltmeler tamam. Canlı Render/Telegram/TradingView verisi
bu checkout'ta doğrulanmadı; commit/push/PR yapılmadı.

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
| `python -m pytest -q` | 4405 passed / 43 skipped | **4433 passed / 43 skipped** (694 sn; +28 test) |
| Hedefli TV/veri testleri | 169 passed / 14 skipped | **76 passed** yeni sözleşme seti dâhil |
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
2. **Gerçek TradingView ağ doğrulaması yok.** Tüm TV testleri sahte modül/frame ile
   çevrimdışı koştu. Anonim WS erişimi, sembol izinleri, IP kısıtı ve gerçek bar
   ızgarası operatör makinesinde `--mod canli` ile ölçülmeli.
3. **Yerel Python 3.11.2 / CI 3.12 farkı.** Pinler `pip check` ile doğrulandı; CI
   push sonrası 3.12 üzerinde aynı kapıları koşmalı.
4. **borsapy hâlâ opsiyonel ölçüm bağımlılığı.** Deploy zincirinde ve otomatik
   yedekte değil; planın "borsapy'yi fiyat kaynağı yapmama" kararı korundu.
5. **Tarihsel denetim belgeleri** kendi dallarını kayıt olarak taşır; aktif komut
   kaynağı `docs/README.md` ve güncel kurulum belgeleridir.

## 7. Sonuç

Yerel statik kapı, 4433 birim test, bağımsız regresyon scriptleri, grafik doktoru ve
HTTP smoke dahil **tüm kontrol edilen kapılar yeşil**. TV/datafeed ekindeki yanlış
`geç` kararı, platforma bağımlı zaman dönüşümü, dağıtım/sürüm çelişkisi, WS sızıntısı
ve eski dal güvenliği düzeltildi. Kalan en önemli iş, planlanan reaktif yedeği canlı
fetch hattına taşımadan önce gerçek TradingView ölçümünü yeşil geçirmektir.
