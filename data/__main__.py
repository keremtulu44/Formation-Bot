# python -m data — eski `python data.py` duman testi (Faz 8).
# Test, kendi geçici cache'ini kullanır; kalıcı iz bırakmaz.
import os
import tempfile

from data import (
    StockDequeManager,
    is_bist_open,
    mock_fetch_60d_1h,
    resample_all_timeframes,
    time_until_next_candle_close,
    time_until_next_open,
)

print("=== Data.py duman testi (çevrimdışı) ===")
print(f"BIST açık mı? {is_bist_open()}")
print(f"Sonraki açılışa: {time_until_next_open()/3600:.2f} saat")
print(f"Sonraki mum kapanışına: {time_until_next_candle_close()/60:.1f} dk")

with tempfile.TemporaryDirectory(prefix="formation-bot-data-test-") as test_root:
    test_data_dir = os.path.join(test_root, "cache")
    manager = StockDequeManager(maxlen=10, data_dir=test_data_dir)
    df_mock = mock_fetch_60d_1h("THYAO", 20)
    print(f"\nMock THYAO: {len(df_mock)} bar")
    print(df_mock.tail(3))

    manager.append_dataframe("THYAO", df_mock)
    df_from_deque = manager.to_dataframe("THYAO")
    print(f"\nDeque'den DataFrame: {len(df_from_deque)} bar")

    resampled = resample_all_timeframes(df_from_deque)
    for tf, df in resampled.items():
        print(f"{tf}: {len(df)} bar")

print("\nTest bitti (test-owned geçici cache temizlendi)")
