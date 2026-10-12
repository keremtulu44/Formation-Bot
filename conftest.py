"""Pytest genel kurulumu.

C4 (Batch 7) ile `DATA_DIR` repo dışına taşındı (`~/.formation-bot/data` gibi).
Testler o dizine kalıcı durum yazarsa bir sonraki koşu kirlenir (örn. Telegram kap
sayaçları dolu gelir ve `can_send` beklemedik yerde False döner). Bu yüzden her
test, veri dizinini kendi geçici klasörüne alır.

Not: `data.StockDequeManager(data_dir=DATA_DIR)` varsayılanı import anında
bağlandığı için modül özniteliğini değiştirmek onu etkilemez; testler zaten
açıkça `data_dir=` verir veya `SEED_DATA_DIR` yedeğini kullanır.
"""

import pytest

import config as config_mod
import notifier as notifier_mod

# Repo seed'i (bot_data/*.json + *.pkl) testlere sızmamalı: `_okuma_yolu` DATA_DIR'de
# dosya bulamazsa SEED_DATA_DIR'e bakar ve geçici dizinli testler 360 satırlık örnek
# seriyle kirlenir. Seed'i de aynı geçici dizine bağlıyoruz; seed'i BİLEN test
# (test_kaynak_ve_guvenlik) zaten kendi monkeypatch'ini kuruyor.
try:
    import data as data_mod
except Exception:  # pragma: no cover - data import edilemezse izolasyon yine çalışır
    data_mod = None


@pytest.fixture(autouse=True)
def _izole_veri_dizini(tmp_path, monkeypatch):
    veri = tmp_path / "test-data"
    veri.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config_mod, "DATA_DIR", str(veri), raising=False)
    monkeypatch.setattr(notifier_mod, "DATA_DIR", str(veri), raising=False)
    monkeypatch.setattr(config_mod, "SEED_DATA_DIR", str(veri), raising=False)
    if data_mod is not None:
        monkeypatch.setattr(data_mod, "SEED_DATA_DIR", str(veri), raising=False)
    yield veri


# === scan_all_stocks testleri için deterministik veri kaynağı ==============
# Neden? main'in P0 testleri (test_mum_kapanis_penceresi, test_karne) taramanın
# VERİ TAZELİĞİ kapılarından geçmek zorunda; o kapılar commit'lenmiş `bot_data`
# seed'inin yaşına bakıyordu. Seed 9 Eki'nde OFFSESSION_CACHE_MAX_AGE_DAYS (14 gün)
# sınırını aştığı için bu testler saatten/bağlamsız olarak KIRILDI (origin/main
# de aynı 3 testle kırmızı). Testin konusu tazelik değil, bar-kapanış kapısı;
# burada sentetik (her zaman "taze" görünen) bir çerçeve kullanıyoruz ki CI
# günün herhangi bir saatinde ve seed bayatlasa da deterministik koşsun.
_SEANS_SAATLERI = tuple(range(10, 18))   # 1H barları: 10:00 .. 17:00 (17:00 → 18:00 kapanır)


def sentetik_1h_mumlar(gun_sayisi: int = 45):
    """Seans saatlerinde, en yeni mumu en yakın iş gününde olan düzgün OHLCV serisi."""
    from collections import deque  # noqa: F401  (çağıran taraf kullanır)
    from datetime import datetime, time as dt_time, timedelta

    import data as data_mod

    tz = data_mod.ISTANBUL_TZ
    gun = datetime.now(tz).date()
    gunler = []
    while len(gunler) < gun_sayisi:
        if gun.weekday() < 5:
            gunler.append(gun)
        gun -= timedelta(days=1)
    gunler.reverse()

    def _kapanis(i):
        return round(100.0 + (i % 7) * 1.5 - (i % 3) * 0.7, 2)

    mumlar = []
    i = 0
    for gun in gunler:
        for saat in _SEANS_SAATLERI:
            acilis, kapanis = _kapanis(i), _kapanis(i + 1)
            mumlar.append({
                "timestamp": tz.localize(datetime.combine(gun, dt_time(saat, 0))),
                "open": acilis,
                "high": round(max(acilis, kapanis) + 0.4, 2),
                "low": round(min(acilis, kapanis) - 0.4, 2),
                "close": kapanis,
                "volume": 1_000_000 + i * 137,
            })
            i += 1
    return mumlar


@pytest.fixture
def tarama_deque_manager(tmp_path, monkeypatch):
    """`scan_all_stocks`'ı veri-yokluğundan kırılmadan koşturan deque yöneticisi.

    Kalıcılık bu testin kendi geçici dizinine yazılır: tarama sonu `save_to_disk`
    DATA_DIR'e yazar; paylaşılan dizine yazarsa sentetik seri sonradan `bot_data`
    okuyan testlerin (test_mum_kapanis_penceresi df_1h) fixture'ına sızar.
    """
    from collections import deque

    import config as config_mod
    import data as data_mod
    import main as main_mod

    cache_yolu = tmp_path / "tarama-cache"
    cache_yolu.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(data_mod, "DATA_DIR", str(cache_yolu), raising=False)
    manager = data_mod.StockDequeManager(data_dir=str(cache_yolu))
    mumlar = sentetik_1h_mumlar()
    for stock in sorted(set(list(getattr(config_mod, "ACTIVE_STOCKS", []) or [])) | {"THYAO"}):
        manager.deques[stock] = deque(mumlar, maxlen=manager.maxlen)

    # Tazelik eşikleri bu testlerin konusu değil (testte fetch sahte, veri sentetik):
    # kapılar günün herhangi bir saatinde geçilmezse test yanlış nedenle kırılır.
    for ad in ("STALE_BAR_UYARI_DK", "VERI_YOK_MODU_ESIK_DK"):
        monkeypatch.setattr(main_mod, ad, 365 * 24 * 60, raising=False)
    monkeypatch.setattr(main_mod, "OFFSESSION_CACHE_MAX_AGE_DAYS", 365, raising=False)
    return manager
