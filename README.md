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

## Render ve Supabase dağıtımı

> Adım adım kurulum (Python sürümü sabitleme, Supabase `sb_secret_` anahtarı,
> telefondan Telegram token alma, keep-alive) için: **[RENDER_DEPLOY.md](RENDER_DEPLOY.md)**

Build Command `pip install -r requirements.txt`, Start Command `python main.py`.
Python sürümü repodaki `.python-version` ile **3.12**'ye sabitlidir; Render'ın
varsayılanı 3.14'tür ve pandas 2.2.2 / numpy 1.26.4'ün cp314 tekerleği
olmadığı için build kaynak koddan derlemeye düşüp patlıyor.
Render `PORT` değişkenini verdiğinde bot `0.0.0.0:$PORT` üzerinde `/health` endpoint'i açar;
monitör yalnızca liveness JSON'u görür, token/anahtar veya portföy verisi döndürülmez.

İki çalışma seçeneği:

- **Background Worker (önerilen, ücretli):** Sürekli çalışan Python döngüsüne uygun servis türü;
  dışarıdan ping gerekmez. Bot piyasa dışında/hafta sonu tarama yapmadan bekler, fakat servis açık
  kaldığından worker çalışma süresi devam eder.
- **Free Web Service (deneysel/garantisiz):** Bir dış uptime monitörü
  `https://<render-adresi>/health` adresine hafta içi İstanbul saatiyle 08:00–19:00 arasında
  10 dakikada bir istek gönderebilir. Render Free, 15 dakika inbound trafik olmazsa servisi
  uyutur; 10 dk aralık 5 dk pay bırakır. 5 dakikalık kontrol daha güvenlidir. Monitör durursa,
  Render servisi yeniden başlatırsa veya isteği kaçırırsa bot uyuyabilir; bu yöntem uptime
  garantisi değildir. Son kontrol 19:00'da yapılırsa servis yaklaşık 19:15'te uykuya geçer.
  Süreç pingler arasında çalışır, yalnızca CPU'yu sürekli meşgul etmez.

Supabase SQL scriptini çalıştırdıktan sonra Render servisinin **Environment** bölümüne şu
secret'ları girin (değerleri Git'e veya sohbete koymayın):

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- İsteğe bağlı `BOT_PROFILE`

Supabase değişkenleri yoksa bot mevcut yerel cache/dosya davranışıyla çalışır; ancak Render'ın
ephemeral diski nedeniyle restart/deploy sonrası bu yerel veriler korunmaz. Değişkenler varsa
bot açılışta 1H/1D cache ve Telegram state'ini tek istekle yükler, değişiklikleri `bot_store`
tablosuna yazar; yerel JSON/pickle dosyalarını da fallback olarak tutar.

## Dosya haritası

| Dosya | İçerik |
|---|---|
| `main.py` | Bot döngüsü: fetch → resample → motor → Telegram + heartbeat; veri-yok/split kapıları |
| `canli_tarama.py` | Aktif evren (48 sembol) × 4 TF (1h/2h/4h/1d) canlı tarama raporu — **Pine karşılaştırması için** |
| `config.py` | Profiller (eşikler), hisse listesi, tatil/yarım gün takvimi, timing sabitleri |
| `data.py` | yfinance fetch (`auto_adjust=False`), StockDequeManager (1H + ayrı 1D deque), tatil/veri-yok/split yardımcıları |
| `scan_pacer.py` | Seri Yahoo istekleri için rastgele aralık, 10'lu istek grubu ve grup molası |
| `supabase_store.py` | Supabase REST API adaptörü; servis anahtarı yalnızca environment'tan okunur |
| `health_server.py` | Render `PORT` varsa `/health` liveness endpoint'i; uptime monitörleri için |
| `supabase_schema.sql` | Cache ve çalışma durumları için tek JSONB store tablosu; Supabase SQL Editor'da çalıştırılır |
| `RENDER_DEPLOY.md` | Render Free + Supabase + Telegram kurulum rehberi; build hatası ve keep-alive dahil |
| `.python-version` | Render build'ı için Python 3.12 sabitlemesi (3.14'te pandas derlenemiyor) |
| `.github/workflows/keepalive.yml` | 10 dakikada bir `/health` isteği; Render Free'ın 15 dk uyku kuralını engeller |
| `requirements-optional.txt` | Deploy zincirinde olmayan isteğe bağlı paketler (borsapy) |
| `patterns/` | Motor: `candidate.py` (geometri + bayrak/flama), `pivots.py`, `pole.py` (direk), `lifecycle.py` (state makinesi), `violation.py`, `selection.py`, `mathutil.py` |
| `notifier.py` | Telegram: 4 saat cooldown + global günlük/saatlik kapanı |
| `bot_data/` | Hisse cache'leri — **bilerek git-tracked** (kullanıcı isteği) |
| `PINE_FARK_ANALIZI.md` | **Çalışma defteri:** Pine ile fark analizi, doğrulama listesi, fikir defteri |
| `FORMASYON_MANTIGI.md` | Pine v0.4.6 Türkçe dökümanı (formasyon koşulları, kalite formülleri) |
| `TESHIS_RAPORU.md` | Dış teşhis raporunun bağımsız doğrulaması (TRUE/FALSE/PARTIAL) |

## Canlı tarama raporu nasıl okunur (Pine karşılaştırması)

`canli_tarama.py` çıktısı TradingView'daki Pine overlay'iyle karşılaştırmak için tasarlandı:

- Başlıkta **"Veri son bar: <tarih> (<N> saat once)"** — TradingView'da tam olarak hangi ana bakılacağını söyler.
- Her formasyon: tip, kalite, state, üst/alt çizgi seviyeleri, daralma %, başlangıç tarihi.
- **Bayrak/flamada ek detay:** `Pine varyanti` (standart/eğik), `Direk` (yön/süre/büyüklük/kalite), `Flama olculeri` (derinlik, yükseklik/süre oranı — Pine eşikleri parantezde).
- Rapor sonunda **PINE KARSILASTIRMA REHBERI**: kaç bayrak/flama bulundu + tüm eşikler.
- Not: Pine ekranında eski TAMAMLANDI/BASARISIZ formasyonlar da çizili kalabilir — rapor yalnız **canlı** olanları listeler.

## Durum (2026-09-27, dal `arena/01a0e2d0-formation-bot`)

| Faz | İçerik | Commit |
|---|---|---|
| Faz 1 | Son mum/35-dk gecikme düzeltmesi, `auto_adjust=False`, ölü formasyon alarm kapısı, fetch hata loglama + `data_stale` heartbeat | `7485ab6` |
| Faz 2 | 1D gecikme, BIST tatil/yarım gün takvimi + veri-yok modu, split/süreklilik kontrolü, Telegram global kapanı, tarama drift uyarısı, 1D derin deque (500 bar) | `c3000b6` |
| Faz 3 | Flama motoru doğrulama: `test_pennant.py` (6/6), `specialized_variant` (standart/eğik ayrımı), standart flama geometri şartı, canlı rapora direk/ölçüm detayı + veri tazeliği | `da3840b`, `0fd1f46`, `28a1e7a` |

Regresyon: `test_tarama_zamani.py` **90/90**, `test_pennant.py` **6/6**.

## Bilinmesi gerekenler (yeni oturum için)

1. **Pine dosyası bekleniyor** (`Yeni Metin Belgesi.txt`, ARGENT v0.4.6 export). Diske
   ulaşmadı; geldiğinde `PINE_FARK_ANALIZI.md` §5'teki 12 maddelik doğrulama listesi açılacak.
2. **Kalite katsayı sapması:** döküman 0.28/0.20/0.12/0.16/0.12/0.07/0.05 diyor, kod
   0.26/0.18/0.12/0.20/0.10/0.07/0.07 kullanıyor — **Pine gelmeden kod değiştirilmeyecek**.
3. **Standart flama geometri şartı** (Faz 3'te eklendi): standart flama yalnız Simetrik Üçgen
   geometrisinde kurulur; eğik geometri eğik flama tablosundan (direk kalitesi +10, süre ×0.85,
   kalite +8) geçer. Pine'da birebir var mı — doğrulama madde 11.
4. **Açık A5 maddeleri:** `filter_same_bar_double_pivot` stub, `local_break` TODO,
   `ST_WEAK`/`ST_GEOMETRY` kod yolu yok.
5. **Eşikleri ölçüm olmadan gevşetme yasağı** — A4'ün kök nedeni buydu (sentetik bayrak
   reddediliyor, gerçek veride sahte bayrak bulunuyordu).
6. **Sandbox kısıtı:** bu ortamdan Yahoo Finance ve Telegram'a erişilemiyor (SSL). Gerçek
   zamanlı tarama ve canlı bot testi kullanıcının kendi makinesinde yapılmalı; burada
   `--cache` modu ve commit'li `bot_data` kullanılır.
7. **Bot kuralları:** `bot_data/*.json` + `*.pkl` git-tracked kalacak; runtime dosyaları
   (heartbeat, telegram_kap, *_gunluk.json) gitignore'da. Tüm iş `arena/01a0e2d0-formation-bot`
   dalında; başka dala push yok.
