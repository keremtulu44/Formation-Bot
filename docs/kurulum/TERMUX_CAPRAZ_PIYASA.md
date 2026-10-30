# Termux: Çapraz piyasa araştırması için günlük veri çekimi

Bu araç seçtiğimiz günlük Replay araştırması için Yahoo Finance'tan geçmiş veri
indirir. **Canlı botu, mevcut `backfill_data/` arşivini, Supabase'i veya Telegram'ı
değiştirmez.** Sonuçlar ayrı `capraz_piyasa_data/` klasörüne yazılır. Replay
araştırmasının kendisi ve gram fiyatı hesaplaması henüz uygulanmamıştır.

## Hangi seriler?

| Dosya adı | Yahoo sembolü | Ne olduğu |
|---|---|---|
| XU100 | `XU100.IS` | BIST 100 |
| XU30 | `XU030.IS` | BIST 30 |
| XU50 | `XU050.IS` | BIST 50 |
| XBANK | `XBANK.IS` | Bankacılık endeksi |
| XUSIN | `XUSIN.IS` | Sanayi endeksi |
| XUTUM | `XUTUM.IS` | BIST Tüm |
| BRENT | `BZ=F` | Brent vadeli (USD) |
| USDTRY | `USDTRY=X` | ABD doları / Türk lirası |
| XAUUSD / XAGUSD | `XAUUSD=X` / `XAGUSD=X` | Ons altın / gümüş spot (USD) |
| XAU_FUT / XAG_FUT | `GC=F` / `SI=F` | Ons altın / gümüş vadeli (USD) |

Spot ve vadeli **ayrı dosyalar**dır. Yahoo spot metal verisini sunmazsa araç
Stooq üzerindeki `xauusd` / `xagusd` günlük CSV'sini deneyecek; kaynak ve
sembol manifestte açıkça yazılır. Stooq erişimi/CAPTCHA veya kota nedeniyle
başarısız olabilir. Stooq da başarısızsa TradingView üzerindeki ICE
`FX_IDC:XAUUSD` / `FX_IDC:XAGUSD` kotasyonları denenir. Bunlar kaynağa özgü
USD/ons kotasyonlarıdır, fiziksel alım-satım fiyatı veya merkezi bir spot
kapanış garantisi değildir. Kaynak ve sembol manifestte belirtilir; vadeli
spot adıyla kaydedilmez. Alternatiflere anonim erişim garanti değildir.
Stooq yalnız tarih etiketi verdiği için saat ve kapanış zamanı uydurulmaz.
Gram TL serisi burada üretilmez:
ilgili metal ve kurdan sonra hesaplanabilir, ancak uyumlu zamanlar ve ürün
seçimi ayrıca doğrulanmalı. Vadeliyle hesaplanana spot/gerçek fiziki gram fiyatı
denemez. Spot ve kur dosyası yoksa ilgili gram serisi hazır sayılmaz.

5 yıllık **günlük** ham veri istenir; Yahoo'nun gerçekten verdiği aralık ve
mevcut hisse arşiviyle örtüşme daha kısa olabilir. Saatlik veri bu günlük
araştırma için istenmez. `bar_time`, Yahoo'nun mum etiketidir, **kapanış veya
verinin erişilebilir olduğu an değildir**. Son mum tamamlanmamış olabilir.
Replay'de BIST/makro kapanış saatleri, kaynak ve zaman uyumu ayrıca doğrulanmadan
bu dosyalar doğrudan karar anı verisi sayılmamalıdır. Yahoo fiyatları
`auto_adjust=False` ile alınır; diğer sağlayıcıların düzeltme bilgisi manifestte
ayrıca belirtilir. Split/sıçrama ve sıfır hacim raporlanır.

## 1. Kodu ve ortamı hazırla

Bu dalın GitHub'a yayınlanmış olması gerekir; Arena'daki kaydedilmiş dosyalar
kendiliğinden uzak GitHub dalına gitmez. Kendi Termux klonunda önce:

```bash
cd ~/Formation-Bot
git status --short
```

Yerel değişiklik varsa önce koru/incele; başkasının değişikliklerini silen
komutları çalıştırma. Dal GitHub'da varsa ve çalışma ağacın uygunsa:

```bash
git fetch origin
git switch arena/cd404914-formation-bot
git pull --ff-only origin arena/cd404914-formation-bot
ls scripts/backfill/capraz_piyasa_cek.py
```

Kullandığın mevcut Python ortamında bağımlılıkları kontrol et:

```bash
python -c "import pandas, numpy, yfinance, pytz; print('bağımlılıklar hazır')"
```

Eksikse Termux'un kendi paketlerinden pandas/numpy kullan; pip ile bunları
kaynak koddan derlemeye zorlama. Mevcut `venv` varsa önce onu etkinleştir:

```bash
pkg install python python-pandas python-numpy git -y
# Yalnız venv yoksa:
python -m venv venv --system-site-packages
source venv/bin/activate
pip install yfinance pytz requests
python -c "import pandas, numpy, yfinance, pytz; print('bağımlılıklar hazır')"
```

XU050/XUTUM için Yahoo çok kısa geçmiş döndürürse TradingView'in aynı
endekslerini, spot metaller için de FX_IDC kotasyonlarını anonim olarak
denemek üzere ek bağımlılığı kur:

```bash
pip install tradingview-datafeed==2.1.1
```

Bu paket opsiyoneldir, giriş bilgisi gerektirmez; TradingView anonim veriyi
sınırlayabilir. Kaynak, sembol ve ayrı düzeltme/hacim notları manifestte
belirtilir. Termux sürümüne göre kurulum hata verebilir; çıktıyı paylaş.
Komutlar `.env`, TradingView hesabı veya Supabase anahtarı gerektirmez.

## 2. Çekim ve doğrulama

```bash
cd ~/Formation-Bot
# venv kullanıyorsan: source venv/bin/activate
python scripts/backfill/capraz_piyasa_cek.py
python scripts/backfill/capraz_piyasa_cek.py --durum
```

Seriler sırayla indirilir. Dosyalar `<SEMBOL>_1d.csv.gz` ve kaynak, zaman dilimi,
dönem, veri kalitesi ve SHA-256 içeren `manifest.json` olarak yazılır. Temposu
vardır; Yahoo geçici hata/rate-limit verirse yavaşlar. İşlem kesilirse **aynı
komutu** tekrar çalıştır: sağlam indirilmiş dosyalar atlanır, eksikler denenir.
XU50 veya XUTUM için Yahoo yalnız bir bar verirse aynı endeks `max` ve uygun
kısa dönemlerle, ardından TradingView'de denenir; başka endeksle değiştirilmez.
İstenen dönemden kısa veri gelirse kapsam eksik işaretlenir. USDTRY'de OHLC
bileşenleri tutarsızsa ham değerler değiştirilmeden kaydedilir; hatalı mumların
zamanları `quality.invalid_ohlc_labels` listesinde, sayısı
`quality.invalid_ohlc_count` alanındadır. `quality.atr_ready=false` varsa bu
seri filtreleme/doğrulama yapılmadan ATR hesabına sokulmamalıdır. Kapanışın
tek başına güvenilirliği de ayrıca araştırılmalıdır.

Bir seri sağlayıcıda yoksa bekleyip tekrar denemek her zaman çözmez; çıktıdaki
sembol/hata bilgisini paylaş. Sonuç `12/12` değilse kod sıfır dışı çıkar;
başarılı dosyalar silinmez. `--durum` ağ kullanmadan manifest ve hash doğrular;
bu, verinin Replay'e doğrudan hazır olduğu anlamına gelmez.

Varsayılan `5y` yerine farklı geçmiş istenirse, örneğin ilk çekimde:

```bash
python scripts/backfill/capraz_piyasa_cek.py --period 2y
```

Mevcut veriler farklı dönemle veya bozuk hash ile yeniden çekilecekse açıkça
`--yenile` gerekir. Bu seçenek **tüm** serileri yeniden ister; başarısız
indirmede eski dosya korunur ve işlem başarısız raporlanır.

## 3. Git'e gönder

Verileri gözden geçirdikten sonra yalnız yeni arşivi ekle:

```bash
git status --short
git add capraz_piyasa_data/
git diff --cached --stat
git commit -m "Add cross-market daily research data"
git push origin arena/cd404914-formation-bot
```

Başka önceden stage edilmiş dosyalar varsa `git diff --cached --stat` içinde
onlar da görünür; istemediklerini commit etmeden önce ayır. Serilerden bazıları
başarısız olsa da mevcut başarılı dosyaları göndermek mümkündür, fakat raporu
**eksiksiz** sayma. Push sonrası durum/eksik sembol listesini paylaş.
