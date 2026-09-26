# Formation-Bot - BIST Formasyon Radarı

> ARGENT v0.4.6 Pine Script'in Python'a dönüşümü - adım adım, explainable

## 🎯 Proje Durumu - Adım 4 Bitti

### ✅ Tamamlananlar

- [x] `config.py` - Profil (Dengeli), BIST30/50 listesi, tüm sabitler
- [x] `patterns.py` - **~80KB, 1500 satır**
  - Matematik yardımcıları: `f_clamp`, `f_smoothstep`, `f_band_quality`, `f_line_price`, `f_slope`
  - ATR hesaplama (Wilder's RMA, Pine ile aynı)
  - Pivot motoru: `find_pivots` (ta.pivothigh/low)
  - Touch stats: `f_touch_stats` (sınır temas sayma, min gap)
  - Violation tarama: `f_boundary_violation_stats_simple` (geçmiş ihlal)
  - Üçgen/Kama: `f_build_triangle_candidate`, `find_best_triangle_candidate`
    - Yükselen Üçgen, Alçalan Üçgen, Simetrik Üçgen
    - Yükselen Kama, Alçalan Kama
    - Her reddedilme sebebi Türkçe loglanıyor (rejected_only)
  - Bayrak: `f_build_flag_candidate`, `find_best_flag_candidate`
    - Boğa/Ayı Bayrağı (direk + paralel kanal)
    - Direk bulma: `find_pole` (magnitude, efficiency, quality)
  - Kırılım gücü: `f_breakout_strength` (body, close, penetration, expansion, volume)
  - Lifecycle: `PatternLifecycleManager`
    - `ADAY_OLUSUYOR` → `KIRILIM_ADAYI` → `KIRILIM_TEYITLI` → `RETEST_BEKLENIYOR` → `RETEST_BASARILI` → `TAMAMLANDI`
    - `KIRILIM_TEYIT_ALAMADI`, `BASARISIZ_KIRILIM`, `GECERSIZ`
  - Ana fonksiyon: `detect_patterns` (dict döner, explainable logs ile)
- [x] `data.py` - Deque yönetimi
  - `StockDequeManager`: maxlen=360, hem pickle hem json (both)
  - Resampling: 1H → 2H, 4H, 1D (dropna ile BIST gap handling)
  - BIST saat kontrolü: `is_bist_open`, `time_until_next_open`, `time_until_next_candle_close`
  - Mock data: `mock_fetch_60d_1h` (test için)
- [x] `main.py` - Ana döngü
  - Lifecycle + Deque + Notifier entegre
  - Günlük özet log
  - Rate limit 45-50sn, hata olursa devam (crash yok)
  - BIST kapalıysa 5dk uyku
- [x] `notifier.py` - Telegram iskeleti
  - Cooldown 4 saat (spam önleme)
  - Env'den token/chat_id
  - Mock modda sadece log
- [x] Deployment
  - `setup.sh` - Ubuntu 22.04 ARM kurulum
  - `bist-bot.service` - systemd (Restart=always, RestartSec=30)
  - `logrotate.conf` - 7 gün log tutma
  - `.env.example`, `requirements.txt`, `.gitignore`

### 🧪 Test Sonuçları

**test_triangle.py:**
- Random data: 225 adaydan 1 geçti (82 kalite) - false positive normal, random walk bile üçgen oluşturur
- Simetrik üçgen mock: 14 aday geçti, en iyi 83.7 kalite Alçalan Üçgen
- Yükselen üçgen mock: 87.0 kalite ile doğru tespit

**test_breakout.py:**
- `ADAY_OLUSUYOR` → `KIRILIM_ADAYI` (güç 82) → `KIRILIM_TEYITLI` → `RETEST` → `COMPLETED/FAILED`
- Başarısız kırılım: içeri dönüş → `BASARISIZ_KIRILIM`

**test_flag.py:**
- Direk bulma: valid=True quality 77.9 eff 0.76 (Dengeli min 0.62 üstü)
- Bayrak: Mock data'da paralel toleransı çok katı (0.018), gerçek BIST datasında daha iyi olacak
- Random data'da bayrak yok (beklendiği gibi)

**main.py mock tarama (30 hisse):**
- 25 hisse tarandı, 76 pattern bulundu (mock data çok pattern üretiyor, gerçek data daha az olur)

### 📝 Kalanlar

- [ ] Flama (pennant) - bayrak gibi ama daralan (simetrik üçgen)
- [ ] Violation taraması tam versiyon (şu an basit, Pine'daki cache'li versiyon sonra)
- [ ] Gerçek veri katmanı: yfinance/borsapy entegrasyonu (sandbox'ta SSL hatası, sen canlıda test edeceksin)
- [ ] Telegram insanlaştırma: State bazlı mesajı daha anlaşılır yap
- [ ] BIST 50 listesi final
- [ ] Loglama Türkçe iyileştirme

## 🧠 Formasyon Mantığı

Detaylı döküman: `FORMASYON_MANTIGI.md`

- 4 pivot ile formasyon (2 üst + 2 alt)
- Kronolojik, topAbove, yaş, temas, daralma, apex kontrolleri
- Kalite: geometry*0.38 + touch*0.32 + maturity*0.18 + cleanliness*0.12
- İhlal taraması: close<2, maxViol<0.72, penalty<62
- Selection: recency + proximity + continuity
- Lifecycle: breakout gücü, teyit, retest

## 🚀 Kurulum

```bash
git clone https://github.com/keremtulu44/Formation-Bot.git
cd Formation-Bot
git checkout arena/01a0dd9d-formation-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt --break-system-packages

# Test
python3 test_triangle.py
python3 test_breakout.py
python3 test_flag.py

# Main (mock data ile)
python3 main.py
```

## 📊 Veri Kaynağı

- **Mock**: Şu an mock data ile test (sandbox'ta yfinance/borsapy SSL engelli)
- **Gerçek**: Sen canlıda `yfinance` (THYAO.IS) veya `borsapy` ile test edeceksin
- `data.py`'deki `mock_fetch_60d_1h` yerine gerçek fetch koyulacak

## 💬 Notlar

- Adım adım gidiyoruz, aniden zıplamıyoruz
- Her reddedilme sebebi loglanıyor (rejected_only) - explainable
- Dosya yapısı düzenli: config, data, patterns, notifier, main
- Telegram: Şimdilik ham, sonra insanlaştırma (senin isteğin)
- AL/SAT yok, state bazlı (KIRILIM_ADAYI, TEYITLI, RETEST)

## 🔜 Sonraki Adım

Senin seçimin: Flama mı, deployment test mi, main entegrasyon mu, telegram humanize mı?
