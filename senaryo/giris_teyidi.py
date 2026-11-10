# -*- coding: utf-8 -*-
"""Faz6 giriş teyidi (devamlılık) — Revize1 kuralı T1505.

Saf modül: veri okumaz, sadece sayılarla çalışır (test edilebilirlik).

Kural (FAZ6_GIRIS_TEYIDI_KURALLARI Revize1 — kalibrasyon sonrası seçildi,
30 sembol holdout'lu ana koşudan önce kaydedildi):

1. **test:** son15 barda zemin test edilmiş —
   `min(low[i-14..i]) ≤ zemin + 0,5·ATR`
2. **hold:** son15 barda kapanışlar zemin üstü —
   `close[j] ≥ zemin ∀j ∈ [i-14..i]` (intraday delik serbest)
3. **dönüş:** giriş kapanışı pencere dibinden yukarı dönmüş —
   `close[i] > min(close[i-14..i])`

Zemin hattı koşucuda hesaplanır: `max(destek, band_lo)` (FAZ6 §2 —
destek çizgisi desteklemezse kâğıt tutmaz).

Kullanım: `ok, neden = giris_teyidi(low=..., close=..., i=..., zemin=..., atr=...)`

Neden sırası (ilk ihlal): `zemin_alti_kapanis` → `test_yok` → `donus_yok` →
`tamam` (ok=True).

Revize1 tarihi ve gerekçesi (V1'in yıkanmayı kesmesi) belgede §Revize1.
"""

from __future__ import annotations

from typing import Sequence

PENCERE = 15          # test/hold penceresi (bar)
TEST_TAVANI_ATR = 0.50  # zemin + 0,5 ATR'e kadar test sayılır


def giris_teyidi(*, low: Sequence[float], close: Sequence[float], i: int,
                 zemin: float, atr: float) -> tuple[bool, str | None]:
    """Faz6 giriş teyidi (Revize1 · T1505).

    Args:
        low: serinin tüm bar LOW değerleri.
        close: serinin tüm bar CLOSE değerleri.
        i: tetik/giriş barı indeksi (kapanış üzerinden).
        zemin: giriş tezi zemin hattı — `max(destek, band_lo)`.
        atr: tetik barındaki ATR (TOL ölçeği).

    Returns:
        (True, None) teyit verildi; (False, neden) teyit reddedildi.
    """
    if i < PENCERE - 1:
        return False, "yetersiz_gecmis"
    bas = i - (PENCERE - 1)
    pencere_close = close[bas:i + 1]
    pencere_low = low[bas:i + 1]

    # 1) hold: zemin altına kapanış olmamış (intraday delik serbest)
    for j in range(bas, i + 1):
        if close[j] < zemin:
            return False, "zemin_alti_kapanis"

    # 2) test: zemin son15 barda test edilmiş olmalı (0,5 ATR tampon)
    if min(pencere_low) > zemin + TEST_TAVANI_ATR * atr:
        return False, "test_yok"

    # 3) dönüş: giriş kapanışı pencere dibinin üstünde olmalı
    if close[i] <= min(pencere_close):
        return False, "donus_yok"

    return True, None


def kural_metni() -> str:
    """Tek satırlık kural özeti (rapor/belge tekrar kullanımı için)."""
    return (f"Faz6 T1505: son{PENCERE} barda test (low≤zemin+{TEST_TAVANI_ATR} ATR) "
            f"∧ hold (close≥zemin) ∧ dönüş (close[i]>min(close))")
