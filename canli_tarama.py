"""
CANLI FORMASYON TARAMASI — TradingView çapraz doğrulama
Ne yapar:
  30 hisse x 4 TF (1h/2h/4h/1d) taranır; ŞU AN canlı formasyonu olanlar listelenir.
  Her formasyon için: tip, state, kalite, üst/alt çizgi seviyeleri, pivot zamanları.
Kullanım:
  python canli_tarama.py            -> yfinance'den TAZE veri çeker (başarısızsa cache)
  python canli_tarama.py --cache    -> internet yok; bot_data cache'i ile tarar
Karşılaştırma:
  TradingView'de kendi argent Pine'ınızı (v0.4.6, ayarlar VARSAYILAN) ilgili hisse +
  periyotta açın. Çizgi seviyelerini ve state etiketini bu çıktıyla karşılaştırın.
  DİKKAT: Pine ekranında TAMAMLANDI/BASARISIZ eski formasyonlar da ÇİZİLİ kalabilir —
  bunlar "canlı" DEĞİLDİR. Bu listedekiler canlı olanlardır (SIKISMA, OLGUNLASIYOR vb.).
"""

import sys
import time
import pandas as pd

from config import ACTIVE_STOCKS, ISTANBUL_TZ
from data import StockDequeManager, resample_all_timeframes, fetch_yfinance_1h
from patterns import PatternLifecycleManager
from patterns.detect import _usable_active, LIVE_STATES, TRIANGLE_FAMILIES, SPECIALIZED_FAMILIES

TUM_AILELER = TRIANGLE_FAMILIES + SPECIALIZED_FAMILIES
TFLER = ["1h", "2h", "4h", "1d"]


def taze_veri_cek(stock: str) -> pd.DataFrame:
    """yfinance'den 60d 1h çeker, OHLCV lowercase döner.
    yfinance'in gürültülü hata baskıları (HTTP 404 vb.) yakalanıp susturulur —
    başarısızlık tek satır özetle raporlanır (cache'e düşer)."""
    import io
    import contextlib
    import yfinance as yf
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        df = yf.Ticker(stock + ".IS").history(period="60d", interval="1h")
    if df is None or df.empty:
        raise ValueError("bos veri")
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    return df


def cache_veri_al(manager: StockDequeManager, stock: str) -> pd.DataFrame:
    df = manager.to_dataframe(stock)
    if df is None or df.empty:
        raise ValueError("cache bos")
    return df


def main():
    force_cache = "--cache" in sys.argv
    deque_manager = StockDequeManager()
    lifecycle = PatternLifecycleManager()

    rapor_satirlari = []
    bulgular = []  # (stock, tf, cand, snap, df_tf)
    kaynak_notlari = []

    for i, stock in enumerate(ACTIVE_STOCKS):
        kaynak = "-"
        try:
            if not force_cache:
                try:
                    df_1h = taze_veri_cek(stock)
                    kaynak = "yfinance(taze)"
                    deque_manager.append_dataframe(stock, df_1h)
                except Exception as e:
                    df_1h = cache_veri_al(deque_manager, stock)
                    kaynak = f"cache (fetch basarisiz: {type(e).__name__})"
            else:
                df_1h = cache_veri_al(deque_manager, stock)
                kaynak = "cache"
        except Exception as e:
            kaynak_notlari.append(f"{stock}: VERI YOK ({e})")
            continue

        son_bar = df_1h.index[-1]
        kaynak_notlari.append(f"{stock}: {kaynak}, son bar {son_bar}")

        tfs = resample_all_timeframes(df_1h)
        for tf in TFLER:
            df_tf = tfs.get(tf)
            if df_tf is None or len(df_tf) < 30:
                continue
            snap = lifecycle.scan(f"{stock}_{tf}", df_tf)
            cand = _usable_active(snap, TUM_AILELER)
            if cand is not None:
                bulgular.append((stock, tf, cand, snap, df_tf))
        if not force_cache:
            time.sleep(0.7)  # rate limit nazik olsun

    # ---- Rapor ----
    baslik = ("=" * 60 + "\nCANLI FORMASYON TARAMASI — "
              + pd.Timestamp.now(tz=ISTANBUL_TZ).strftime("%d.%m.%Y %H:%M")
              + "\n" + "=" * 60)
    print(baslik)
    rapor_satirlari.append(baslik)

    print("\n--- Veri kaynaklari ---")
    for n in kaynak_notlari:
        print(" ", n)

    if not bulgular:
        mesaj = "\n>>> SU AN CANLI FORMASYON YOK. <<<"
        print(mesaj)
        rapor_satirlari.append(mesaj)
    else:
        print(f"\n>>> {len(set(b[0] for b in bulgular))} hissede "
              f"{len(bulgular)} CANLI formasyon var <<<\n")
        rapor_satirlari.append(f"\n>>> {len(bulgular)} canli formasyon <<<\n")

        sira = 0
        for stock, tf, a, snap, df_tf in bulgular:
            sira += 1
            bas_zaman = df_tf.index[max(0, a.start_bar)] if 0 <= a.start_bar < len(df_tf) else "?"
            satir = [
                f"[{sira}] {stock} | {tf} | {a.pattern_type} | q{snap.effective_quality:.0f} | {snap.state}",
                f"    Ust cizgi: {a.upper_now:.2f}   Alt cizgi: {a.lower_now:.2f}",
                f"    Daralma: %{(a.contraction or 0) * 100:.0f}   Formasyon baslangici: {bas_zaman}",
                f"    TV KONTROL: {stock} grafigini {tf} periyotta ac; Pine overlay'inde "
                f"'{a.pattern_type}' ve state '{snap.state}' etiketi gorunmeli; cizgiler "
                f"ust~{a.upper_now:.2f} / alt~{a.lower_now:.2f} seviyesinde olmali.",
            ]
            for s in satir:
                print(s)
                rapor_satirlari.append(s)
            print()

    ozet = f"\nToplam: {len(bulgular)} canli formasyon / {len(ACTIVE_STOCKS)} hisse x {len(TFLER)} TF"
    print(ozet)
    rapor_satirlari.append(ozet)
    print("\nRapor dosyasi: CANLI_FORMASYONLAR.txt")

    with open("CANLI_FORMASYONLAR.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(rapor_satirlari) + "\n")


if __name__ == "__main__":
    main()
