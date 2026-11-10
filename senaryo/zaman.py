"""Zaman disiplini — her karar yalnız ``≤ t`` verisiyle üretilir (kırmızı çizgi 7).

Tek kural: ``as_of`` gelecek satırları keser ve **kopya** döner; asıl çerçeve
değişmez. MTF katı kuralı: üst TF'nin karar anına kadar kapanmış barları
kullanılır (``son_kapanis``).
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def as_of(frame: pd.DataFrame, t: Any) -> pd.DataFrame:
    """``t`` anına kadar kapanmış barlar (kopya; asıl frame'e dokunulmaz)."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame pd.DataFrame olmali")
    ts = pd.Timestamp(t)
    mask = frame.index <= ts
    return frame.loc[mask].copy()


def kapatilmis_barlar(frame: pd.DataFrame, t: Any) -> pd.DataFrame:
    """``as_of`` ile aynı anlam — okunur ad."""
    return as_of(frame, t)


def son_kapanis(ust_frame: pd.DataFrame, t: Any) -> pd.Timestamp | None:
    """``t`` anına kadar kapanmış üst-TF barının zamanı (yoksa None)."""
    if ust_frame is None or len(ust_frame) == 0:
        return None
    ts = pd.Timestamp(t)
    kapali = ust_frame.index[ust_frame.index <= ts]
    if len(kapali) == 0:
        return None
    return pd.Timestamp(kapali[-1])


def ust_tf_kapandi_mi(ust_frame: pd.DataFrame, t: Any) -> bool:
    """Karar anında üst TF'de en az bir kapanmış bar var mı?"""
    return son_kapanis(ust_frame, t) is not None


def gelecek_sizintisi_var_mi(frame: pd.DataFrame, t: Any) -> bool:
    """Test/denetim yardımcısı: ``t``'den sonra satır kaldı mı?"""
    ts = pd.Timestamp(t)
    return bool((frame.index > ts).any())


def bar_zamani(index: pd.Index, i: int) -> str:
    """Bar indeksini ISO zaman damgasına çevirir (kayıt alanı için)."""
    if i < 0 or i >= len(index):
        raise IndexError(f"bar disinda: {i} (len={len(index)})")
    return pd.Timestamp(index[i]).isoformat()
