# TERMUX NATIVE 1h/2h/4h/1d ÇEKİMİ — Mevcut yerel klondan, replay OLMADAN

**Amaç:** 170+ sembol için dört zaman dilimini de **kendi sağlayıcısının gerçek
mumlarıyla** çekmek, `backfill_data/` altındaki CSV'leri + manifest/probe/raporu
`git push` ile ajana ulaştırmak. Bu turda **replay koşulmaz**; önce veriler
gelecek, replay komutu veriler geldikten sonra ayrı verilecek.

**Kaynak kararı (2026-11-18):**

| TF | Sağlayıcı | Native istek | Not |
|---|---|---|---|
| `1h` | Yahoo/yfinance | `interval="1h"`, `auto_adjust=False` | Ham OHLCV, 365d |
| `2h` | TradingView/tvDatafeed | `Interval.in_2_hour` | **1h'den resample DEĞİL** |
| `4h` | TradingView/tvDatafeed | `Interval.in_4_hour` | **1h'den resample DEĞİL** |
| `1d` | Yahoo/yfinance | `interval="1d"`, `auto_adjust=False` | Native günlük, 2y |

Yahoo `2h`/`4h` intervalini desteklemediği için bu iki TF tvDatafeed'in anonim
WebSocket kanalından çekilir. 1h'den türetim hacim/fiyat kayması ürettiği için
yeni replay girdisinden **tamamen çıkarılmıştır**: `research/arsiv.py` yeni
native manifestte `_2h.csv.gz` / `_4h.csv.gz` dosyalarını okur, eksikse hata
verir. `BRENT` BIST exchange'inde native 2h/4h karşılığı olmadığı için probe'da
doğrulanmış listeye alınmaz.

**Bu araç ne YAPMAZ:** Supabase'e bağlanmaz, Telegram'a dokunmaz, `.env`
okumaz, canlı botu/Supabase/Telegram'ı etkilemez, formasyon/zone üretmez,
bildirim göndermez. Yalnız iki sağlayıcıdan OHLCV çeker ve diske yazar.
**Ajan tarafında canlı Yahoo/TradingView çağrısı yoktur**; ağ çekimi senin
Termux'undaki yerel klonda olur. Klon **canlı servis değildir**.

**Kod:** `scripts/backfill/yahoo_backfill.py` · `scripts/backfill/native_kaynak.py`
**Kurulum:** `setup-termux.sh` · `requirements-termux.txt`
**Testler:** `test_native_kaynak.py`, `test_yahoo_backfill.py`,
`test_arastirma_olcum.py`, `test_dz_yukleme.py` (ağsız)

---

> **TERMUX OTURUMU KAPANMASIN (2026-11-19):** Hata kontrollerindeki çıkış
> komutu interaktif kabukta **oturumun kendisini** kapatır. Bu belgedeki
> kontroller bu yüzden `bash -s <<'SH' ... SH` alt kabuğu içindedir; çıkış
> yalnızca o alt kabuğu bitirir, Termux penceresi açık kalır. Blokları
> **başından `SH` satırına kadar** kopyala; tek satırı ayırıp çalıştırma.

---

## 0) Beklenen çıktı ve maliyet

| Kalem | Değer |
|---|---|
| Probe isteği | Sembol başına 2 (Yahoo 1d + TV 4h, 5 bar) |
| Tam çekim isteği | Sembol başına 4 (2 Yahoo + 2 TV WS) |
| Süre | 170+ sembol için molalar/WS ile **bir saati aşabilir** |
| Disk | 4 TF × sembol; birkaç on MB (eski 2 TF arşivinin ~2 katı) |
| Git'e giren | `backfill_data/` — `.gitignore`'da DEĞİL |
| Replay | **Bu turda YOK** |

`--tv-bar-sayisi 1500` varsayılandır: 2h için ~1,3 yıl, 4h için ~2,5 yıl BIST
seansı ister. TV daha az bar döndürürse manifest gerçek satır sayısını yazar;
uydurma/türetme bar eklenmez.

---

## 1) Termux'ta mevcut klonu güncelle ve bağımlılıkları kur

> Aşağıdaki blok **mevcut yerel klon** içindir; `git clone` YOK. Aktif dal
> Arena oturum notundaki **aktif dal** olmalı; aşağıdaki komutlar dal adını
> `git branch --show-current` ile dinamik okur, belgeye sabit dal yazılmaz. Klon
> canlı değil, sadece veri çekim çalışma alanıdır.

```bash
bash -s <<'SH'
cd ~/Formation-Bot
DAL="$(git branch --show-current)"
test -n "$DAL" -a "$DAL" != "HEAD" || { echo "HATA: önce Arena oturumunun aktif dalına geç"; exit 1; }
test -z "$(git status --porcelain)" || { echo "HATA: önce yerel değişiklikleri commit/stash et"; exit 1; }

git fetch origin "$DAL"
git pull --rebase origin "$DAL"
git rev-parse --short HEAD

# Tek seferlik sistem paketleri (pandas/numpy pip ile KURULMAZ)
pkg update -y
pkg install python python-numpy python-pandas git -y
pkg install termux-api -y || echo "termux-api yok; wake-lock'suz devam"

# Varsa venv'i kullan; yoksa sistem Python ile devam
if [ -d venv ]; then . venv/bin/activate; fi
python -m pip install --upgrade pip
python -m pip install -r requirements-termux.txt

# Doğrulanmış TV dağıtımı + temel importlar
python - <<'PY'
import numpy, pandas, yfinance, pytz, websocket
from scripts.tvdatafeed_client import dogrulanmis_surum
print("pandas", pandas.__version__, "numpy", numpy.__version__)
print("yfinance", yfinance.__version__, "websocket", websocket.__version__)
print("tv", *dogrulanmis_surum())
from scripts.backfill import native_kaynak
print("kaynak plani", native_kaynak.KAYNAK_PLANI)
PY
SH
```

Beklenen son satır:
`{'1h': 'yahoo', '2h': 'tvdatafeed', '4h': 'tvdatafeed', '1d': 'yahoo'}`.
`tv tradingview-datafeed 2.1.1` görmüyorsan `pip install -r requirements-termux.txt`
adımını tekrar koş; betik doğrulanmamış kurulumda fail-closed durur.

> Eski `backfill_data/manifest.json` kaynak etiketsizse 1h/1d kayıtları da
> **yeniden çekilir**. Bu bilinçlidir: eski türetimli arşivin native arşivle
> karışmaması için `atlanmali_mi` kaynak + `native=True` + dosya varlığını
> birlikte ister.

---

## 2) ADIM 1 — Probe: iki sağlayıcıyı da doğrula

```bash
cd ~/Formation-Bot
if [ -d venv ]; then . venv/bin/activate; fi
python scripts/backfill/yahoo_backfill.py --probe --tv-bar-sayisi 5
```

Üretilenler:

- `backfill_data/probe_sonucu.json` — sembol başına `yahoo`/`tvdatafeed`
  sonucu, `kaynak_plani`, `tv_dagitim`, `kaynak_plani_ozeti`
- `backfill_data/dogrulanmis_semboller.txt` — **yalnız iki kaynakta da veri
  dönen** semboller; tam çekim bunu otomatik kullanır

Özeti gör:

```bash
python - <<'PY'
import json
d = json.load(open("backfill_data/probe_sonucu.json"))
print("mod:", d["mod"])
print("kaynak:", d["kaynak_plani"])
print("tv:", d["tv_dagitim"])
print("geçerli:", d["gecerli_sayisi"], "geçersiz:", d["gecersiz_sayisi"])
print("ilk geçersizler:", list(d["gecersiz"].items())[:10])
PY
printf 'doğrulanmış sembol: '; grep -c . backfill_data/dogrulanmis_semboller.txt
```

**Bana söyle:** geçerli/geçersiz sayıları, TV dağıtım satırı ve ilk birkaç
geçersiz sembol. `gecerli_sayisi` 170+ çıkmıyorsa tam çekime geçmeden haber ver.

---

## 3) ADIM 2 — Pilot: ilk 10 sembol, dört native TF

```bash
cd ~/Formation-Bot
if [ -d venv ]; then . venv/bin/activate; fi
python scripts/backfill/yahoo_backfill.py --limit 10 --tv-bar-sayisi 1500
```

Kontrol et:

```bash
ls -lh backfill_data/*_1h.csv.gz backfill_data/*_2h.csv.gz \
       backfill_data/*_4h.csv.gz backfill_data/*_1d.csv.gz | head -20
python - <<'PY'
import gzip, glob
for tf in ("1h", "2h", "4h", "1d"):
    yol = sorted(glob.glob(f"backfill_data/*_{tf}.csv.gz"))[0]
    with gzip.open(yol, "rt", encoding="utf-8") as f:
        baslik = f.readline().strip()
        ilk = f.readline().strip()
    print(tf, yol.split("/")[-1], "|", baslik, "|", ilk.split(",")[0])
PY
```

Beklenen:

- başlık `bar_time,open,high,low,close,volume`
- `bar_time` `YYYY-MM-DD HH:MM:SS+03:00` (ISO `T` YOK)
- dört TF için ayrı dosya; `2h`/`4h` satırları 1h satırlarının yarısı/dörte
  biri kadar DEĞİL, sağlayıcının kendi bar sayısıdır

`ModuleNotFoundError: tvDatafeed` veya `doğrulanmamış tvDatafeed dağıtımı`
görürsen §1'deki kurulumu tekrar koş.

---

## 4) ADIM 3 — Tam çekim

Android Termux'u arka planda öldürebilir; wake-lock + pil optimizasyonunu kapat.

```bash
cd ~/Formation-Bot
if [ -d venv ]; then . venv/bin/activate; fi
termux-wake-lock
python scripts/backfill/yahoo_backfill.py --tv-bar-sayisi 1500 --wake-lock
```

Ekranı kilitleme, Termux'u kaydırmadan bırak. Süreç ölürse **aynı komutu**
tekrar koş: başarılı `(sembol, interval, kaynak)` çiftleri atlanır, manifest
her adımda diske yazılır. Ban koruması `⚠️ KOŞU BAN KORUMASIYLA DURDURULDU`
derse birkaç saat bekle, sonra:

```bash
python scripts/backfill/yahoo_backfill.py --retry-failed --tv-bar-sayisi 1500
```

Üretilen yeni rapor: `backfill_data/kaynak_raporu.json` — TF × kaynak × durum
özeti, beklenen/eksik native dosya listeleri ve `resample_kullanildi=false`.

---

## 5) ADIM 4 — Push öncesi doğrulama (zorunlu)

```bash
cd ~/Formation-Bot
python - <<'PY'
import gzip, json, re, sys
from pathlib import Path

kok = Path("backfill_data")
m = json.load(open(kok / "manifest.json", encoding="utf-8"))
r = json.load(open(kok / "kaynak_raporu.json", encoding="utf-8"))
plan = {"1h": "yahoo", "2h": "tvdatafeed", "4h": "tvdatafeed", "1d": "yahoo"}
hatalar = []

if m.get("native_zorunlu") is not True or m.get("arsiv_modu") != "native":
    hatalar.append("manifest native modda değil")
if m.get("kaynak_plani") != plan:
    hatalar.append(f"kaynak planı yanlış: {m.get('kaynak_plani')}")
if r.get("resample_kullanildi") is not False:
    hatalar.append("kaynak raporu resample kullanımını false demiyor")

semboller = [s.strip() for s in
             (kok / "dogrulanmis_semboller.txt").read_text(encoding="utf-8").splitlines()
             if s.strip()]
kayitlar = m["kayitlar"]
tf_sayisi = {tf: 0 for tf in plan}
for sembol in semboller:
    for tf, beklenen in plan.items():
        dosya = kok / f"{sembol}_{tf}.csv.gz"
        kayit = kayitlar.get(f"{sembol}:{tf}")
        if not dosya.exists():
            hatalar.append(f"eksik dosya: {dosya.name}")
            continue
        if not kayit or kayit.get("durum") != "ok":
            hatalar.append(f"manifest ok değil: {sembol}:{tf}")
            continue
        if kayit.get("kaynak") != beklenen or kayit.get("native") is not True:
            hatalar.append(f"kaynak/native etiketi yanlış: {sembol}:{tf}")
        if tf in ("2h", "4h") and kayit.get("provider_interval") not in ("in_2_hour", "in_4_hour"):
            hatalar.append(f"TV provider_interval yanlış: {sembol}:{tf}")
        tf_sayisi[tf] += 1
        with gzip.open(dosya, "rt", encoding="utf-8") as f:
            baslik = f.readline().strip()
            ilk = f.readline().strip()
        if baslik != "bar_time,open,high,low,close,volume":
            hatalar.append(f"başlık bozuk: {dosya.name}")
        elif not re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\+03:00$", ilk.split(",")[0]):
            hatalar.append(f"bar_time biçimi bozuk: {dosya.name}")

print("sembol:", len(semboller), "TF başarı:", tf_sayisi)
print("beklenen dosya:", r["beklenen_dosya_sayisi"],
      "diskte:", r["diskteki_dosya_sayisi"],
      "eksik:", r["eksik_dosya_sayisi"])
print("durum özeti:", r["kayit_durum_ozeti"])
print("tv dağıtım:", r["tv_dagitim"])
if hatalar:
    print("\nDOĞRULAMA BAŞARISIZ:")
    for h in hatalar[:30]:
        print(" -", h)
    sys.exit(1)
print("DOĞRULAMA OK: dört TF native, kaynak etiketleri tam, resample yok")
PY

git status --short | head -30
du -sh backfill_data
```

`DOĞRULAMA OK` görmeden push atma. `eksik > 0` ise aynı tam çekim komutunu
veya `--retry-failed` koşunu tekrarla. `kalici_basarisiz` olan semboller probe
listesinden çıkmalı; `gecici_basarisiz` varsa retry gerekir.

---

## 6) ADIM 5 — Commit & push

```bash
bash -s <<'SH'
cd ~/Formation-Bot
DAL="$(git branch --show-current)"
test -n "$DAL" -a "$DAL" != "HEAD" || { echo "HATA: önce Arena oturumunun aktif dalına geç"; exit 1; }

git add backfill_data/
git status --short | head -30
git commit -m "backfill: 1h/2h/4h/1d native OHLCV (Yahoo + TradingView) — Termux"
git push origin "$DAL"
SH
```

Push reddedilirse (ajandan yeni commit gelmişse):

```bash
git pull --rebase origin "$DAL"
git push origin "$DAL"
```

Push sonrası ajana şunu yapıştır:

```bash
printf 'Ajana haber: native veri push edildi. commit=%s sembol=%s csv=%s kaynak_raporu=OK replay=YOK (önce veriler).\n' \
  "$(git rev-parse --short HEAD)" \
  "$(grep -c . backfill_data/dogrulanmis_semboller.txt)" \
  "$(ls backfill_data/*_*.csv.gz | wc -l)"
```

> **Boyut notu:** 4 TF arşivi eski 2 TF arşivinin yaklaşık iki katıdır.
> 100 MB'ı aşarsan bana söyle; sembol gruplarına bölüp ayrı commit yaparız.
> Bu turda `arastirma_kosu.py` / `dz_yukleme.py` replay komutu **verilmedi**;
> veriler geldikten sonra ayrı adımda koşulacak.

---

## 7) Komut özeti (kopyala-yapıştır)

```bash
bash -s <<'SH'
cd ~/Formation-Bot
DAL="$(git branch --show-current)"
test -n "$DAL" -a "$DAL" != "HEAD" || { echo "HATA: önce Arena oturumunun aktif dalına geç"; exit 1; }
test -z "$(git status --porcelain)" || { echo "HATA: önce temizle"; exit 1; }
git fetch origin "$DAL" && git pull --rebase origin "$DAL"

pkg update -y && pkg install python python-numpy python-pandas git -y
pkg install termux-api -y || true
if [ -d venv ]; then . venv/bin/activate; fi
python -m pip install --upgrade pip
python -m pip install -r requirements-termux.txt
python -c "from scripts.tvdatafeed_client import dogrulanmis_surum; print('tv', *dogrulanmis_surum())"

python scripts/backfill/yahoo_backfill.py --probe --tv-bar-sayisi 5
python scripts/backfill/yahoo_backfill.py --limit 10 --tv-bar-sayisi 1500
termux-wake-lock
python scripts/backfill/yahoo_backfill.py --tv-bar-sayisi 1500 --wake-lock

# §5 doğrulama bloğunu çalıştır, DOĞRULAMA OK görmeden devam etme
git add backfill_data/
git commit -m "backfill: 1h/2h/4h/1d native OHLCV (Yahoo + TradingView) — Termux"
git push origin "$DAL"
printf 'Ajana haber: commit=%s sembol=%s csv=%s replay=YOK.\n' \
  "$(git rev-parse --short HEAD)" \
  "$(grep -c . backfill_data/dogrulanmis_semboller.txt)" \
  "$(ls backfill_data/*_*.csv.gz | wc -l)"
SH
```

---

## 8) Sorun giderme

| Belirti | Sebep / Çözüm |
|---|---|
| `ModuleNotFoundError: pandas` | `pkg install python-pandas` — pip ile KURMA (rust hatası) |
| `ModuleNotFoundError: tvDatafeed` | `pip install -r requirements-termux.txt` |
| `doğrulanmamış tvDatafeed dağıtımı` | `tradingview-datafeed==2.1.1` + `websocket-client==1.9.2` pinlerini kur |
| `TV boş veri döndürdü` | WS bazen ilk çağrıda kopar; ortak istemci 2 deneme yapar, yine olursa `--retry-failed` |
| `BRENT` probe'da geçersiz | Beklenen: BIST exchange'inde native 2h/4h yok; doğrulanmış listeden çıkar |
| Sürekli `429` / `Too Many Requests` | Ban koruması yavaşlatır; durduysa birkaç saat bekle, `--retry-failed` |
| `KOZAL: HTTP Error 404` | Normal — Yahoo taşımıyor; `kalici_basarisiz`, tekrar denenmez |
| Süreç kendi kendine kapandı | Android öldürdü. `termux-wake-lock` + aynı komutu tekrar koş |
| Enter'a basınca Termux anında kapanıyor | Hata kontrolündeki çıkış komutu interaktif kabukta oturumu kapatır; `bash -s <<'SH' ... SH` bloğunu baştan sona kopyala, tek satırı çalıştırma |
| `~90 satır` 1h | `--period-1h 365d` açıkça ver (varsayılan zaten 365d) |
| `bar_time` içinde `T` | Hata — bana söyle. Sözleşme `YYYY-MM-DD HH:MM:SS+03:00` |
| `native 4h arşiv dosyası yok` | Replay'e geçilmemeli; önce 4h çekimini tamamla |
| Testleri koşmak istersen | `python -m pytest -q test_native_kaynak.py test_yahoo_backfill.py` (ağsız) |

---

## 9) Çıktı biçimi sözleşmesi

```
backfill_data/
├── <SEMBOL>_1h.csv.gz     Yahoo native, 365d
├── <SEMBOL>_2h.csv.gz     TradingView native, in_2_hour
├── <SEMBOL>_4h.csv.gz     TradingView native, in_4_hour
├── <SEMBOL>_1d.csv.gz     Yahoo native, 2y
├── manifest.json          durum/satır/kaynak/TF/native/kalite/hata/süre + koşu geçmişi
├── probe_sonucu.json      iki sağlayıcının geçerlilik + dağıtım raporu
├── dogrulanmis_semboller.txt   yalnız dört kaynakta da doğrulanan semboller
└── kaynak_raporu.json     TF × kaynak × durum + eksik native dosyalar
```

Kurallar:

- `bar_time` **TEXT**, `YYYY-MM-DD HH:MM:SS+03:00`, Europe/Istanbul
- Sayılar `repr()` ile tam round-trip; yuvarlama yok, NaN/inf → boş hücre
- Sıfır hacim korunur, yalnız `kalite.sifir_hacim` ile işaretlenir
- Yazım atomiktir (`.tmp` → `os.replace`)
- Yahoo `auto_adjust=False`; TV `adjustment:"splits"` ham/split-ayarlı barları
- **2h/4h 1h'den resample EDİLMEZ**; manifest `native_zorunlu=true`,
  `arsiv_modu=native`, `kaynak_plani` etiketleri bunu kilitler
- Dört native dosyası tamamlanmayan sembol `arsiv_sembolleri(native_only=True)`
  ile replay planına alınmaz
