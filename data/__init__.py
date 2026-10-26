"""data paketi (Faz 8) — data.py bölündü; dış API aynı.

Yama yüzeyi (test_patch_yuzeyi.py): DATA_DIR, SEED_DATA_DIR,
ALLOW_TRUSTED_PICKLE_CACHE, StockDequeManager, fetch_yfinance_1h/1d,
_atomic_pickle_write — aşağıdaki bağlamalarda kalır; alt modüller
`_pkg.X` ile çağrı anında okur. `import data` sonrası data.X aynı.
Duman testi: `python -m data`.
"""

import pandas as pd
import numpy as np
from collections import deque
from datetime import date, datetime, timedelta, time as dt_time
import logging
import math
import os
import pickle
import tempfile
from typing import Dict, List, Optional, Tuple

from config import (
    ISTANBUL_TZ, BIST_OPEN, BIST_CLOSE, DEQUE_MAXLEN,
    DATA_DIR, SEED_DATA_DIR, MARKET_SUFFIX, yahoo_ticker_for_symbol,
    PROVIDER_SYMBOL_FALLBACK,
    CANDLE_CLOSE_MINUTE, SCAN_DELAY_AFTER_CLOSE_MIN, TARAMA_PENCERE_SONU,
    BIST_TATILLER, BIST_YARIM_GUNLER,
    VERI_YOK_MODU_ESIK_DK, SPLIT_SUREKLILIK_ESIK_PCT, BAR_BOSLUK_ESIK_SAAT,
    GUNLUK_FETCH_PERIOD, GUNLUK_DEQUE_MAXLEN,
    FULL_1H_FETCH_PERIOD, ROUTINE_1H_FETCH_PERIOD, FULL_1H_FETCH_STALE_DAYS,
    ALLOW_TRUSTED_PICKLE_CACHE,
)

log = logging.getLogger(__name__)

# Günlük (1d) mum: 00:00 etiketli, seans kapanışında tamamlanır (normal 18:30, yarım gün 13:00).
GUNLUK_MUM_KAPANIS_SAATI = dt_time(18, 30)  # BIST seans kapanışı + takas payı (1H ölçümünden)


# Seansın GERÇEK bitiş saati (intraday barların kesme sınırı): normal gün 18:00, yarım gün 13:00.
# Ölçüm: Yahoo regular period 09:30–18:00; kapanış müzayedesi fiyatı ~18:09'da oluşur.
INTRADAY_SEANS_SONU_SAATI = dt_time(18, 0)


# --- MUM KAPANIŞ KURALI (P0 düzeltmesi, 2 Eki 2026) -------------------------
# ÖLÇÜM (Yahoo chart API, THYAO.IS; meta.currentTradingPeriod.regular):
#   * Seans 09:30–18:00, barlar SOL etiketli (etiket = bar BAŞI): 09:30, 10:30, ... 17:30.
#   * Bir barın ömrü = etiket + TF süresi. GÜNÜN SON barı/kovası seans sonunda KESİLİR
#     (17:30 etiketli kova 18:00'de kapanır; 4 saatlikte bu 30 dakikalık kovadır —
#     TradingView'in BIST 4h grafiğinde de aynı).
#
# ESKİ HATA 1: 1h için "+30 dk" kullanılıyordu -> 10:30 barı 11:00'de "kapandı"
#   sayılıyordu. Normal :35 taramaları doğru barı görüyordu ama :00–:29 arasında
#   tetiklenen bir tarama (restart / kaçırılan tarama telafisi / çok uzun tur)
#   HENÜZ KAPANMAMIŞ 1h mumunu kapanmış sayıp bildirim üretebiliyordu.
# ESKİ HATA 2: 2h/4h için kesme yoktu -> günün son kovası (17:30) "+2sa/+4sa" kuralıyla
#   19:30/21:30'a kadar "yarım" kalıyor, 18:35 taramasında hiç analiz edilmiyordu
#   (ölçüm: 2h son kova 15:30, 4h son kova 13:30). Günün kapanış saati kayıptı.
# ESKİ HATA 3: 1d mumu sabit 18:30'da tamamlanıyordu; yarım günde (arefe, 13:00 kapanış)
#   mum 18:30'a kadar "yarım" kalıyor ve o gün günlük bildirim hiç gitmiyordu.
TF_BAR_SURELERI = {
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
    "4h": timedelta(hours=4),
}


# Timeframe -> pandas süre etiketi (tamamlanmis_mumlar filtresi için)
TF_SURELERI = {"1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D"}


logger = logging.getLogger(__name__)


from data.fetch import (  # noqa: F401
    fetch_last_bar,
    fetch_yfinance_1d,
    fetch_yfinance_1h,
    mock_fetch_60d_1h,
    saglayici_adaylari,
    select_yfinance_1h_period,
    yfinance_error_is_retryable,
)
from data.replay import (  # noqa: F401
    _SEANS_CAPASI,
    _bist_seans_serisi,
    _gun_kapanis_damgalari,
    _istanbul_dizin,
    _istanbul_zaman,
    _resample_sabit_capali,
    bar_kapandi_mi,
    bist_tatil_adi,
    is_bist_open,
    islem_gunu_mu,
    mum_kapanis_ani,
    mum_kapanis_anlari,
    resample_all_timeframes,
    resample_ohlcv,
    seans_kapanis_saati,
    seans_sonu_saati,
    son_kapanan_mum_ani,
    sonraki_islem_gunu,
    tamamlanmis_mumlar,
    tarama_animi_mi,
    tarama_penceresi_acik_mi,
    time_until_next_candle_close,
    time_until_next_open,
    veri_yok_modu_acik_mi,
    yarim_gun_kapanisi,
)
from data.backfill import (  # noqa: F401
    _cache_barlari_birlestir,
    _karisik_timestamp_zaman_dilimi,
    _ohlcv_kayit_sorunlari,
    _temiz_1d_cache_kayitlari,
    _temiz_1h_cache_kayitlari,
    ohlcv_girdi_sorunlari,
    sureklilik_sorunlari_bul,
    yuvarlak_orana_yakin_mi,
)
from data.seed_cache import (  # noqa: F401
    StockDequeManager,
    _atomic_json_write,
    _atomic_pickle_write,
    _atomic_write,
)
