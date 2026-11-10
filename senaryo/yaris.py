"""İleri yarış — pencere (ölçüm) sürümü. Koşucunun bar-bar mantığıyla aynı.

Kurallar (plan §3 / stop replay sözleşmesi):
* yalnız kapanışlar; ``bas`` = giriş barının indeksi (yarış ``bas+1``'den);
* ilk dokunuş: stop ≤ giriş−S vs hedef ≥ giriş+T; **aynı barda çift
  dokunuş → stop** (muhafazakâr);
* ``H`` barda çözüm yoksa → ``zaman`` (bar H kapanışı, mark-to-market);
* veri ``H`` barı tamamlamıyorsa → ``yok`` (sağdan sansür, sonuç sayılmaz).
"""

from __future__ import annotations

from typing import Sequence


def yaris_penceresi(
    kapanislar: Sequence[float],
    bas: int,
    H: int,
    giris: float,
    stop: float,
    hedef: float,
    atr: float,
) -> tuple[str, int | None, float, float]:
    """→ (sonuc, cozunme_bar, pnl_atr, mae_atr)."""
    if H <= 0 or atr <= 0:
        raise ValueError("H ve atr pozitif olmalı")
    if bas < 0:
        raise ValueError("bas negatif olamaz")
    son = bas + H
    if son > len(kapanislar):
        return "yok", None, 0.0, 0.0           # sağdan sansürlü
    yol = kapanislar[bas:son]
    mae = 0.0
    for k, c in enumerate(yol, start=1):
        mae = min(mae, (c - giris) / atr)
        hit_stop = c <= stop
        hit_hedef = c >= hedef
        if hit_stop:                           # eşitlik → stop
            return "stop", k, -(giris - stop) / atr, mae
        if hit_hedef:
            return "hedef", k, (hedef - giris) / atr, mae
    return "zaman", H, (yol[-1] - giris) / atr, mae
