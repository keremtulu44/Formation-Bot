# TERMUX DERİN GEÇMİŞ ÇEKİMİ — Adım Adım

**Amaç:** BIST havuzundan 365 günlük 1H + 2 yıllık 1D ham OHLCV'yi telefonundan
(Termux) çekmek, repoya commit/push etmek. Böylece araştırma arşivi gerçek veriyle
dolar — sandbox'tan Yahoo'ya çıkılamadığı için bu adımı senin cihazın yapıyor.

**Bu araç ne YAPMAZ:** Supabase'e bağlanmaz, Telegram'a dokunmaz, `.env` okumaz,
domain motorlarını çalıştırmaz, formasyon/zone üretmez, bildirim göndermez.
Yalnız Yahoo'dan OHLCV çeker ve diske `CSV.gz` yazar.

**Kod:** `scripts/backfill/yahoo_backfill.py`
**Testler:** `test_yahoo_backfill.py` (40 test, ağsız)
**Şema (henüz uygulanmayacak):** `supabase_backfill_schema.sql`

---

## 0) Beklenen maliyet

| Kalem | Değer |
|---|---|
| İstek sayısı | ~200 (100 sembol × 2 aralık) |
| Süre | **~13–20 dk** (molalar dahil; ban koruması devreye girerse uzar) |
| Disk | **~4–8 MB** (gzip'li CSV) |
| Git'e giren | `backfill_data/` — `.gitignore`'da DEĞİL, düz `git add` çalışır |

365 gün seçilme gerekçesi: 60 günde 4h FVG'nin kullanılabilir penceresi **21 bar**,
4h'de hacim motoru **hiç** hazır olmuyor (150 bar kapısı). 365 günde 4h FVG **657 bar**,
hacim çalışır hale geliyor. Ayrıntı: ölçüm tablosu proje sohbetinde.

---

## 1) Termux kurulumu (tek seferlik)

> **Kritik:** pandas/numpy'ı `pip` ile KURMA. aarch64 + Python 3.14'te rust
> derleme hatası verir (`requirements-termux.txt`'te belgeli). `pkg`'den gelir.

```bash
pkg update -y
pkg install python python-pandas python-numpy git -y
pip install --upgrade pip
pip install yfinance pytz
```

Doğrula:

```bash
python -c "import pandas, numpy, yfinance, pytz; print('ok', pandas.__version__)"
```

`ok` görüyorsan hazırsın. `yfinance` sürümü önemli değil; `.history()` API'si sabit.

---

## 2) Repoyu ve branch'i al

```bash
cd ~
git clone https://github.com/keremtulu44/Formation-Bot.git
cd Formation-Bot
git fetch origin
git checkout arena/88cda271-formation-bot
```

Zaten klonun varsa:

```bash
cd ~/Formation-Bot
git fetch origin
git checkout arena/88cda271-formation-bot
git pull --rebase origin arena/88cda271-formation-bot
```

Doğrula — bu iki dosya olmalı:

```bash
ls -l scripts/backfill/yahoo_backfill.py test_yahoo_backfill.py
```

---

## 3) ADIM 1 — Probe: hangi semboller Yahoo'da gerçekten var

> Havuz **doğrulanmamıştır** (BIST100 bileşimi çeyreklik değişir). Yahoo bazı BIST
> sembollerini taşımıyor — bilinen örnek: `KOZAL.IS` / `KOZAA.IS` → HTTP 404.
> Probe bunu önceden eler, asıl çekimde boşa istek atılmaz.

```bash
python scripts/backfill/yahoo_backfill.py --probe
```

Üretilenler:

- `backfill_data/probe_sonucu.json` — sembol başına geçerli/geçersiz + hata metni
- `backfill_data/dogrulanmis_semboller.txt` — **asıl çekim bunu otomatik kullanır**

Sonucu gör:

```bash
grep -c . backfill_data/dogrulanmis_semboller.txt
python -c "import json;d=json.load(open('backfill_data/probe_sonucu.json'));print('geçerli',d['gecerli_sayisi'],'geçersiz',d['gecersiz_sayisi']);print(list(d['gecersiz'].items())[:10])"
```

**Bana söyle:** geçerli sayısı kaç, ve geçersiz listede hangi semboller var.

---

## 4) ADIM 2 — Pilot: 10 sembol (her şeyden önce bunu koş)

```bash
python scripts/backfill/yahoo_backfill.py --limit 10
```

Kontrol et (`zcat` Termux'ta her zaman yoktur; Python karşılığı güvenli):

```bash
ls -lh backfill_data/*.csv.gz | head
python -c "
import gzip
with gzip.open('backfill_data/THYAO_1h.csv.gz','rt') as f:
    for i, satir in enumerate(f):
        if i < 3: print(satir.rstrip())
        n = i + 1
print('toplam satır (başlık dahil):', n)
"
```

Beklenen:
- başlık satırı `bar_time,open,high,low,close,volume`
- `bar_time` biçimi `2026-10-16 09:30:00+03:00` — **ISO `T` YOK** (şema kuralı K1)
- satır sayısı ~2200–2400 (365 gün × ~9 bar/seans)

`~90` satır görüyorsan period 60d kalmış demektir; `--period-1h 365d` açıkça ver.

---

## 5) ADIM 3 — Tam çekim

Android Termux'u arka planda öldürür. Önce wake-lock:

```bash
termux-wake-lock
python scripts/backfill/yahoo_backfill.py
```

Ekranı kilitleme, Termux'u kaydırmadan bırak. Pil optimizasyonunu Termux için
kapatmak da önerilir (Ayarlar → Uygulamalar → Termux → Pil → Kısıtlama yok).

**Süreç ölürse / yarıda kesilirse:** aynı komutu tekrar koş. Başarılı sembol-atılım
çiftleri **atlanır**, kaldığı yerden devam eder. Manifest her adımda diske yazılır.

Ban koruması koşuyu durdurursa (`⚠️ KOŞU BAN KORUMASIYLA DURDURULDU`):
**birkaç saat bekle**, sonra:

```bash
python scripts/backfill/yahoo_backfill.py --retry-failed
```

---

## 6) ADIM 4 — Sonuçları denetle

```bash
python - <<'PY'
import json
m = json.load(open("backfill_data/manifest.json"))
k = m["kayitlar"]
durumlar = {}
for v in k.values():
    durumlar[v["durum"]] = durumlar.get(v["durum"], 0) + 1
print("durumlar:", durumlar)
h1 = [v for v in k.values() if v["interval"] == "1h" and v["durum"] == "ok"]
print("1h başarılı:", len(h1), "toplam bar:", sum(v.get("satir", 0) for v in h1))
if h1:
    en_az = min(h1, key=lambda v: v.get("satir", 0))
    en_cok = max(h1, key=lambda v: v.get("satir", 0))
    print("en az bar:", en_az["sembol"], en_az["satir"])
    print("en çok bar:", en_cok["sembol"], en_cok["satir"])
kirli = [(kk, v["kalite"]) for kk, v in k.items() if v.get("kalite", {}).get("split_sicramasi_adayi", 0)]
print("split adayı olan kayıt:", len(kirli))
for kk, kal in kirli[:10]:
    print("   ", kk, kal)
PY
```

Dikkat edilecekler:
- `gecici_basarisiz` > 0 ise `--retry-failed` koş
- `kalici_basarisiz` olanlar 404/sembol yok — **tekrar denenmez**, listeden çıkar
- `split_sicramasi_adayi` olan kayıtlar düşürülmez, yalnız işaretlenir (eleme kararı
  ingest katmanınındır; düşürmek survivorship bias üretir)

---

## 7) ADIM 5 — Commit & push

```bash
cd ~/Formation-Bot
git add backfill_data/
git status --short | head
git commit -m "backfill: BIST derin geçmiş (365d 1h + 2y 1d) — Termux çekimi"
git push origin arena/88cda271-formation-bot
```

Push'tan önce benim yeni commit'lerim geldiyse:

```bash
git pull --rebase origin arena/88cda271-formation-bot
git push origin arena/88cda271-formation-bot
```

Push sonrası bana haber ver — gerçek veriyle Faz 2'yi (ölçüm çekirdeği) doğrularım.

> **Boyut notu:** `backfill_data/` ~4–8 MB. Git için sorun değil. 100 MB'ı aşarsan
> bana söyle, sembol gruplarına bölüp ayrı commit'ler yapalım.

---

## 8) Komut özeti (kopyala-yapıştır)

```bash
# kurulum
pkg update -y && pkg install python python-pandas python-numpy git -y
pip install --upgrade pip && pip install yfinance pytz

# repo
cd ~ && git clone https://github.com/keremtulu44/Formation-Bot.git
cd Formation-Bot && git checkout arena/88cda271-formation-bot

# koşu
python scripts/backfill/yahoo_backfill.py --probe
python scripts/backfill/yahoo_backfill.py --limit 10
termux-wake-lock && python scripts/backfill/yahoo_backfill.py

# push
git add backfill_data/ && git commit -m "backfill: BIST derin geçmiş" \
  && git push origin arena/88cda271-formation-bot
```

---

## 9) Sorun giderme

| Belirti | Sebep / Çözüm |
|---|---|
| `ModuleNotFoundError: pandas` | `pkg install python-pandas` — pip ile KURMA (rust hatası) |
| `ModuleNotFoundError: yfinance` | `pip install yfinance` |
| Sürekli `429` / `Too Many Requests` | Ban koruması zaten yavaşlatır. Koşu durduysa birkaç saat bekle, `--retry-failed` |
| `KOZAL: HTTP Error 404` | Normal — Yahoo taşımıyor. `kalici_basarisiz` olarak işaretlenir, tekrar denenmez |
| Süreç kendi kendine kapandı | Android öldürdü. `termux-wake-lock` + aynı komutu tekrar koş (kaldığı yerden devam) |
| `~90 satır` geldi | period 60d kalmış. `--period-1h 365d` açıkça ver |
| Depolama doldu | `df -h ~`; 4–8 MB yeterli, `backfill_data/` dışında büyük dosya olmamalı |
| `bar_time` içinde `T` görünüyor | Hata — bana söyle. Sözleşme `YYYY-MM-DD HH:MM:SS+03:00` |
| Testleri koşmak istersen | `pip install pytest && python -m pytest test_yahoo_backfill.py -q` (40 test, ağsız) |

---

## 10) Çıktı biçimi sözleşmesi

```
backfill_data/
├── <SEMBOL>_1h.csv.gz     bar_time,open,high,low,close,volume
├── <SEMBOL>_1d.csv.gz     aynı biçim
├── manifest.json          sembol başına durum/satır/aralık/kalite/hata/süre + koşu geçmişi
├── probe_sonucu.json      (--probe) geçerlilik raporu
└── dogrulanmis_semboller.txt   (--probe) sonraki çekimin girdisi
```

Kurallar:
- `bar_time` **TEXT**, `YYYY-MM-DD HH:MM:SS+03:00`, Europe/Istanbul
- Sayılar `repr()` ile **tam round-trip**; yuvarlama yok. NaN/inf → **boş hücre**
  (`nan` yazılmaz: okuyucuda sayı diye patlar)
- Sıfır hacim **korunur** (düşürülmez), yalnız işaretlenir
- Yazım **atomik** (`.tmp` → `os.replace`): yarım dosya arşive girmez
- `auto_adjust=False`: ham fiyat (Pine/TradingView paritesi)
- 2h/4h **saklanmaz**: `resample_ohlcv` (data.py:1470) seans başına hizalı
  kovalarla 1H'den deterministik türetir
