# -*- coding: utf-8 -*-
"""giris_teyidi (Faz6 Revize1 · T1505) testleri — saf modül, veri yok."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from senaryo.giris_teyidi import PENCERE, giris_teyidi, kural_metni

N = 30


def seri(yap: dict[int, tuple[float, float]], varsayilan_close=10.0,
         varsayilan_low=9.5):
    """{bar: (low, close)} — belirtilmeyen barlar varsayılanla dolar."""
    low, close = [], []
    for j in range(N):
        l, c = yap.get(j, (varsayilan_low, varsayilan_close))
        low.append(l)
        close.append(c)
    return low, close


ZEMIN = 9.0
ATR = 1.0


def test_tamam_holdsuz_kalmaz():
    #15 bar boyunca close ≥ zemin, low zemine inmiş (test), giriş dibin üstünde
    yap = {j: (9.1, 9.6) for j in range(15)}
    yap[10] = (8.9, 9.4)          # test: low zemin+0,5 ATR'in altında
    low, close = seri(yap, varsayilan_close=9.6, varsayilan_low=9.3)
    ok, neden = giris_teyidi(low=low, close=close, i=15, zemin=ZEMIN, atr=ATR)
    assert ok and neden is None


def test_zemin_alti_kapanis_eliyor():
    #15 bar içinde bir kapanış zeminin altında → hold ihlali
    yap = {j: (9.3, 9.6) for j in range(15)}
    yap[5] = (9.0, 8.95)          # zemin altına kapanış
    yap[10] = (8.9, 9.5)          # test var ama kırılmış
    low, close = seri(yap, varsayilan_close=9.6, varsayilan_low=9.3)
    ok, neden = giris_teyidi(low=low, close=close, i=15, zemin=ZEMIN, atr=ATR)
    assert not ok and neden == "zemin_alti_kapanis"


def test_test_yok_eliyor():
    # zemine hiç inilmemiş (low hep zemin+0,5 ATR üstü) → henüz test yok
    yap = {j: (9.6, 9.8) for j in range(15)}
    low, close = seri(yap, varsayilan_close=9.8, varsayilan_low=9.6)
    ok, neden = giris_teyidi(low=low, close=close, i=15, zemin=ZEMIN, atr=ATR)
    assert not ok and neden == "test_yok"


def test_test_pencere_disi_sayilmaz():
    # test15 bar ÖNCESİNE düştü → pencere içinde yok → test_yok
    yap = {j: (9.6, 9.8) for j in range(15)}
    yap[0] = (8.5, 9.8)           # ama bar0 pencerede (i=15, bas=1)… değil
    # i=15 → bas = 15-14 = 1 → bar0 dışarıda
    low, close = seri(yap, varsayilan_close=9.8, varsayilan_low=9.6)
    ok, neden = giris_teyidi(low=low, close=close, i=15, zemin=ZEMIN, atr=ATR)
    assert not ok and neden == "test_yok"


def test_donus_yok_eliyor():
    # test var, hold var ama giriş kapanışı pencerenin EN DİBİNDE → dönüş yok
    yap = {j: (9.3, 9.6) for j in range(15)}
    yap[10] = (8.9, 9.4)          # test
    yap[15] = (9.2, 9.35)         # kapanış = min(kapanış) (hepsi ≥9,35 değil…
    # min close'u giriş yapalım: bar15 kapanışını en dip yap
    low, close = seri(yap, varsayilan_close=9.6, varsayilan_low=9.3)
    close[15] = min(close[1:16])  # giriş = pencere dibi
    low, close = list(low), list(close)
    ok, neden = giris_teyidi(low=low, close=close, i=15, zemin=ZEMIN, atr=ATR)
    assert not ok and neden == "donus_yok"


def test_yetersiz_gecmis():
    low, close = seri({})
    ok, neden = giris_teyidi(low=low, close=close, i=PENCERE - 2,
                             zemin=ZEMIN, atr=ATR)
    assert not ok and neden == "yetersiz_gecmis"


def test_test_tamponu_hassas():
    # min low = zemin + 0,5 ATR tam sınırda → test sayılır (≤);
    # zemin + 0,51 ATR → test_yok (dönüş/hold için dip kapanış şartı da var)
    yap = {j: (9.5, 9.7) for j in range(16)}
    yap[5] = (9.5, 9.65)          # girişin dibin üstünde olması için
    low, close = seri(yap, varsayilan_close=9.7, varsayilan_low=9.5)
    ok1, neden1 = giris_teyidi(low=low, close=close, i=15,
                               zemin=ZEMIN, atr=ATR)
    yap2 = {j: (9.51, 9.7) for j in range(16)}
    yap2[5] = (9.51, 9.65)
    low2, close2 = seri(yap2, varsayilan_close=9.7, varsayilan_low=9.51)
    ok2, neden2 = giris_teyidi(low=low2, close=close2, i=15,
                               zemin=ZEMIN, atr=ATR)
    assert ok1 and neden1 is None
    assert not ok2 and neden2 == "test_yok"


def test_kural_metni():
    metin = kural_metni()
    assert "T1505" in metin and "test" in metin and "hold" in metin
