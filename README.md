# Formation-Bot — BIST Formasyon Radarı

> ARGENT v0.4.6 Pine Script'in Python portu. BIST hisselerinde üçgen/kema/bayrak/flama
> formasyonlarını tespit eder, state makinesiyle takip eder ve Telegram'dan bildirir.
> Pine ile **birebir** uyum hedefi; her reddedilme sebebi Türkçe loglanır (explainable).

## Hızlı başlangıç

```bash
python3 -m pip install -r requirements.txt   # pandas, numpy, pytz, yfinance
cp .env.example .env                         # TELEGRAM_TOKEN / TELEGRAM_CHAT_ID
python3 main.py                              # canlı bot (heartbeat + SIGTERM destekli)
python3 canli_tarama.py                      # 30 hisse x 4 TF canlı formasyon taraması (rapor: CANLI_FORMASYONLAR.txt)
python3 canli_tarama.py --cache              # internet yok: bot_data cache ile tarar
python3 test_tarama_zamani.py                # Faz 1+2 regresyon (90 kontrol)
python3 test_pennant.py                      # flama regresyon (6 test)
```

Profil seçimi: `.env` içinde `BOT_PROFILE=Dengeli` (Hassas / Dengeli / Seçici).

## Dosya haritası

| Dosya | İçerik |
|---|---|
| `main.py` | Bot döngüsü: fetch → resample → motor → Telegram + heartbeat; veri-yok/split kapıları |
| `canli_tarama.py` | 30 hisse × 4 TF (1h/2h/4h/1d) canlı tarama raporu — **Pine karşılaştırması için** |
| `config.py` | Profiller (eşikler), hisse listesi, tatil/yarım gün takvimi, timing sabitleri |
| `data.py` | yfinance fetch (`auto_adjust=False`), StockDequeManager (1H + ayrı 1D deque), tatil/veri-yok/split yardımcıları |
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
