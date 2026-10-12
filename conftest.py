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


@pytest.fixture(autouse=True)
def _izole_veri_dizini(tmp_path, monkeypatch):
    veri = tmp_path / "test-data"
    veri.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config_mod, "DATA_DIR", str(veri), raising=False)
    monkeypatch.setattr(notifier_mod, "DATA_DIR", str(veri), raising=False)
    yield veri
