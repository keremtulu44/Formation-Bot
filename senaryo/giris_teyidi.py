# -*- coding: utf-8 -*-
"""Faz 6 — giriş teyidi: "destek tuttu mu / düşüş bitti mi?" (devamlılık).

Belge: ``docs/tasarim/FAZ6_GIRIS_TEYIDI_KURALLARI_2026-11-10.md`` (koşudan
önce yazıldı; eşikler değişmez).

Üç şart (hepsi **devamlılık** — ucuz, yerel, BOS/CHOCH değil):

1. **Zemin altı kapanış yok** (son ``PENCERE`` bar): tez çizgisi
   ``zemin = max(destek, band_lo)`` altına **kapanılmamış** olacak —
   destek kırılıp geri dönmüş girişler elenir.
2. **Yeni dip yok:** giriş barının ``low``'u, son2 bardaki dibin altında
   **yeni dip yapmayacak** (dip zaten oluşmuş olmalı; düşüşe alım kesilir).
3. **Kovalama sınırı:** girişten önceki3 barda koşu ``MOM3_TAVANI_ATR``
   ATR'yi aşarsa giriş yok (zirveye yakın/omentumlu kovalama kesilir).

Safdır: çerçeve okumaz; girdi değişmezse çıktı değişmez. Yalnız **planı**
etkiler — tetik/kör baz (K2 temeli) değişmez.
"""

from __future__ import annotations

PENCERE = 3              # devamlılık penceresi (bar) — FAZ6 §2
MOM3_TAVANI_ATR = 0.50   # kovalama sınırı — FAZ6 §2


def giris_teyidi(
    *,
    low: list[float],
    close: list[float],
    i: int,
    zemin: float,
    atr: float,
    pencere: int = PENCERE,
    mom3_tavani: float = MOM3_TAVANI_ATR,
) -> tuple[bool, str]:
    """``i`` anında giriş teyidi. ``(geçti mi, gerekçe)`` — saf.

    ``i >= pencere + 1`` varsayılır (koşucu ``ILK_BAR=40`` ile garanti eder);
    yine de küçük ``i`` için pencere kırpılır, ``dip_teyidi_yok`` için
    en az1 bar geçmiş gerekir.
    """
    if i < 1:
        return False, "yetersiz_gecmis"

    # 1) zemin altına kapanış yok (son pencere bar, giriş barı dahil)
    bas = max(0, i - pencere + 1)
    for j in range(bas, i + 1):
        if close[j] < zemin:
            return False, "zemin_alti_kapanis"

    # 2) yeni dip yok: giriş low'u son (pencere-1) bardaki dibin altında olmasın
    onceki = low[max(0, i - (pencere - 1)):i]
    if onceki and low[i] < min(onceki):
        return False, "dip_teyidi_yok"

    # 3) kovalama: son3 barda koşu > tavan (i>=3; ILK_BAR sayesinde her zaman)
    if i >= 3 and (close[i] - close[i - 3]) / atr > mom3_tavani:
        return False, "kovalama"

    return True, "tamam"
