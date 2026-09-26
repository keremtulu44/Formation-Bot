# Formation-Bot - BIST Formasyon Radarı

> ARGENT v0.4.6 Pine Script'in Python'a dönüşümü - adım adım, explainable

## 🎯 Proje Durumu

**Şu an: Adım 1 - İskelet Tamamlandı**

- [x] `config.py` - Profil, BIST listesi, sabitler
- [x] `patterns.py` - Matematik yardımcıları, pivot motoru, direk bulma (iskelet)
- [x] `data.py` - Deque yönetimi, resampling (2H/4H/1D), BIST saat kontrolü
- [x] `main.py` - Ana döngü iskeleti
- [x] `notifier.py` - Telegram iskeleti (henüz pasif)
- [ ] `patterns.py` - `f_build_candidate` tam implementasyon (üçgen/kama/bayrak/flama)
- [ ] `patterns.py` - Violation taraması, lifecycle, breakout
- [ ] Deployment dosyaları (setup.sh, bist-bot.service)

## 🧠 Pine'dan Python'a - Neden Karmaşık?

Pine'daki her filtre neden var?

1. **Pivot Motoru** (`ta.pivothigh/low`): Formasyonun köşe taşları
2. **Direk Motoru** (`f_find_pole`): Bayrak/flama öncesi impuls olmalı
3. **Aday Motoru** (`f_build_candidate`): 6 son pivotun tüm kombinasyonları (1296 aday)
4. **Kalite Skorlama** (`geometryScore`, `touchScore`, `contractionScore`): Smoothstep ile yumuşak geçiş
5. **İhlal Taraması** (`f_boundary_violation_stats`): Geçmişte sınır delinmiş mi?
6. **Lifecycle** (`ST_BREAK_CANDIDATE` -> `CONFIRMED` -> `RETEST_OK`): Kırılımın teyidi

## 🔍 Kontrol Yöntemi (Explainable)

Her aday neden reddedildi / kabul edildi loglanacak:

```
[THYAO] Aday: hb1=10, hb2=20, lb1=12, lb2=22
  -> chronological: OK
  -> topAbove: OK
  -> touch: 2 üst / 2 alt = OK
  -> contraction %18 < min %25 = RED (daralma yetersiz)
  -> historical violation: 0 kapanış / 1 fitil = OK
  -> rawQuality 42 < min 46 = RED
```

Böylece TradingView ile karşılaştırma yapılabilir.

## 🚀 Kurulum (Local Test)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt --break-system-packages

# Test
python3 patterns.py
python3 data.py
python3 main.py  # Mock data ile çalışır, gerçek API yoksa
```

## 📊 Veri Kaynağı

- **Primary**: `yfinance` (THYAO.IS) - 60 gün 1H için yeterli
- **Alternatif**: `borsapy` (İş Yatırım) - TradingView ile fark yok dedin
- **Eski**: `tvdatafeed` - SSL ban riski, PyPI'de yok

Mock data ile test edilebilir, gerçek API sonra bağlanır.

## 📝 Sonraki Adım

**Adım 2: `f_build_candidate` tam implementasyon**

- Üçgen türleri: Yükselen, Alçalan, Simetrik
- Kama: Yükselen, Alçalan
- Bayrak/Flama: Boğa/Ayı (direk + paralel kanal / daralan)

Her biri için:
- Geometri kontrolü (eğimler, paralellik, daralma)
- Touch istatistiği
- Quality hesaplama
- Neden reddedildi logu

## 💬 İletişim

Adım adım gidiyoruz, aniden zıplamıyoruz. Her adımda ne yaptığını bilen, neden yapmadığını açıklayan kod.

- Telegram formatı: Şimdilik ham, sonra insanlaştırma
- Hisse listesi: BIST30 ile test, sonra 50
- AL/SAT: Üretmeyecek, state bazlı (KIRILIM_ADAYI, TEYITLI, RETEST)
