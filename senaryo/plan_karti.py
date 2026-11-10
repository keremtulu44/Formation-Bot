"""Plan kartı üretimi — UYGUN + G5 bandında onaylı tepki → ölçülmüş plan.

Kurallar (plan belgesi §5, önceden kayıtlı):
* giriş = tetik barının kapanışı;
* **stop = tez ölümü**: girişin altındaki **ilk** kırılma hattı — destek ile
  band alt sınırının **büyüğü** (destek bandın içindeyse destek, bandın
  altındaysa bandın kendisi) − tampon (0,10 ATR); mesafe 0,5–2,5 ATR
  **dışındaysa plan yok**;
* **hedef = en yakın karşıt yapı** (MS tepe swing'leri; formasyon üst sınırı
  G2 bağlamdır, hedefe girmez — kırmızı çizgi); ``R ≥ 1,2`` değilse plan yok;
* zaman-stopu 10 bar; ``bilinmeyenler`` satırı zorunlu.

Safdır: çerçeve okumaz, girdi değişmezse çıktı değişmez.
"""

from __future__ import annotations

import math
from typing import Sequence

from .modeller import PlanKaydi

STOP_TAMPON_ATR = 0.10
STOP_MIN_ATR = 0.5
STOP_MAX_ATR = 2.5
R_MIN = 1.2
VARSAYILAN_ZAMAN_STOPU = 10


def plan_karti_uret(
    *,
    plan_id: str,
    sembol: str,
    tf: str,
    t: str,
    bar_index: int,
    donem: str,
    giris: float,
    atr: float,
    destek: float | None,
    band: tuple[float, float] | None,
    karsit_yapilar: Sequence[float],
    hukum_satiri: str,
    kaynak_bildirimler: Sequence[str] = (),
    ek_bilinmeyenler: Sequence[str] = (),
    yon: str = "long",
    zaman_stopu: int = VARSAYILAN_ZAMAN_STOPU,
) -> PlanKaydi | None:
    """Plan kartı; koşullar sağlanmazsa ``None`` (kartsızlık da kayıttır)."""
    if atr is None or not math.isfinite(atr) or atr <= 0:
        return None
    if giris is None or not math.isfinite(giris) or giris <= 0:
        return None
    if destek is None or band is None:
        return None

    # --- stop: tez ölümü (girişin altındaki ilk kırılma hattı) --------------
    # destek bandın içindeyse destek, bandın altındaysa bandın alt sınırı
    # yakındır: max() ile yakın hat seçilir; uzak destek stopu şişirmez.
    zemin = max(float(destek), float(band[0]))
    stop = zemin - STOP_TAMPON_ATR * atr
    stop_mesafe = giris - stop
    if not (STOP_MIN_ATR * atr <= stop_mesafe <= STOP_MAX_ATR * atr):
        return None

    # --- hedef: en yakın karşıt yapı (R eşiği ile) --------------------------
    adaylar = sorted(
        float(x) for x in karsit_yapilar
        if x is not None and math.isfinite(float(x)) and float(x) > giris
    )
    if not adaylar:
        return None
    hedef = adaylar[0]
    R = (hedef - giris) / stop_mesafe
    if R < R_MIN:
        return None

    # --- bilinmeyenler (zorunlu dürüstlük satırı) ---------------------------
    bilinmeyenler = list(ek_bilinmeyenler)
    bilinmeyenler.append("direnç tepkisi ölçülmüş değil (yapısal hedef)")
    return PlanKaydi(
        plan_id=plan_id,
        sembol=sembol,
        tf=tf,
        t=t,
        yon=yon,
        giris=float(giris),
        band_lo=float(band[0]),
        band_hi=float(band[1]),
        stop=float(stop),
        hedef=float(hedef),
        R=round(float(R), 4),
        zaman_stopu=int(zaman_stopu),
        bilinmeyenler=tuple(dict.fromkeys(bilinmeyenler)),  # tekrarsız, sıra korunur
        hukum_satiri=hukum_satiri,
        kaynak_bildirimler=tuple(kaynak_bildirimler),
        donem=donem,
        bar_index=int(bar_index),
    )
