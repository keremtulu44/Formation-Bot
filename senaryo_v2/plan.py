"""Gölge v2 simetrik plan kartı üretimi (Mod 0 bloksuz, Mod 1 stop/band, Mod 2 1-3 bar limit)."""

from __future__ import annotations

import math

from .modeller import (
    BLOK_MIN_HEIGHT_ATR,
    MOD2_MIN_RISK_ATR,
    TAMPON_VARSAYILAN_ATR,
    AdayOlay,
    BarDurum,
    BlokBand,
    PlanKartV2,
)


def karsit_yapisal_hedef(
    olay: AdayOlay,
    b: BarDurum,
    giris: float,
) -> tuple[float | None, str, int]:
    """Bar i itibarıyla bilinen en yakın karşıt yapısal hedefi döndürür (min 0.35 ATR uzaklık)."""
    min_uzak = 0.35 * b.atr_tf
    adaylar: list[tuple[float, str]] = []

    if olay.yon == "long":
        esik = giris + min_uzak
        if b.r_level is not None and b.r_validity in ("ACTIVE", "BREACHED") and b.r_level > esik:
            adaylar.append((float(b.r_level), "stabil_r"))
        if b.ms_weak_high is not None and b.ms_weak_high > esik:
            adaylar.append((float(b.ms_weak_high), "ms_weak_high"))
        if b.ms_protected_high is not None and b.ms_protected_high > esik:
            adaylar.append((float(b.ms_protected_high), "ms_prot_high"))
        for lvl in b.ms_unbroken_highs:
            if lvl > esik:
                adaylar.append((float(lvl), "ms_high"))
        for lvl in b.ms_down_broken_levels:
            if lvl > esik:
                adaylar.append((float(lvl), "ms_down_bos"))
        if olay.alt_kol == "B_sinir" and b.frm_upper_now is not None and b.frm_upper_now > esik:
            adaylar.append((float(b.frm_upper_now), "frm_ust"))
        adaylar.sort(key=lambda x: x[0])
    else:
        esik = giris - min_uzak
        if b.s_level is not None and b.s_validity in ("ACTIVE", "BREACHED") and b.s_level < esik:
            adaylar.append((float(b.s_level), "stabil_s"))
        if b.ms_weak_low is not None and b.ms_weak_low < esik:
            adaylar.append((float(b.ms_weak_low), "ms_weak_low"))
        if b.ms_protected_low is not None and b.ms_protected_low < esik:
            adaylar.append((float(b.ms_protected_low), "ms_prot_low"))
        for lvl in b.ms_unbroken_lows:
            if lvl < esik:
                adaylar.append((float(lvl), "ms_low"))
        for lvl in b.ms_up_broken_levels:
            if lvl < esik:
                adaylar.append((float(lvl), "ms_up_bos"))
        if olay.alt_kol == "B_sinir" and b.frm_lower_now is not None and b.frm_lower_now < esik:
            adaylar.append((float(b.frm_lower_now), "frm_alt"))
        adaylar.sort(key=lambda x: -x[0])

    if not adaylar:
        return None, "", 0
    return adaylar[0][0], adaylar[0][1], len(adaylar)


def _gecerli_blok_mu(z: BlokBand, b: BarDurum) -> bool:
    """S03/S07: <0.5 ATR mikro-gürültü ve 3+ dokunulmuş FVG'yi dışlar."""
    h_atr = z.height_atr if z.height_atr > 0 else ((z.upper - z.lower) / b.atr_tf if b.atr_tf > 0 else 0.0)
    if h_atr < BLOK_MIN_HEIGHT_ATR:
        return False
    if z.family == "FVG" and z.touch_count_asof >= 2:
        return False
    return True


def _mod1_blok_sec(olay: AdayOlay, b: BarDurum, stop_mod0: float) -> BlokBand | None:
    """TYR-sonrası stop/zemin hizalaması için uygun aynı yönlü OB/FVG bandını seçer."""
    if b.atr_tf <= 0:
        return None
    if olay.yon == "long":
        uygun = [
            z for z in b.blok_bull
            if _gecerli_blok_mu(z, b)
            and z.lower <= b.close + 0.25 * b.atr_tf
            and z.upper >= stop_mod0 - 0.75 * b.atr_tf
        ]
        if not uygun:
            return None
        return min(uygun, key=lambda z: abs(z.lower - olay.zemin_tavan))
    uygun = [
        z for z in b.blok_bear
        if _gecerli_blok_mu(z, b)
        and z.upper >= b.close - 0.25 * b.atr_tf
        and z.lower <= stop_mod0 + 0.75 * b.atr_tf
    ]
    if not uygun:
        return None
    return min(uygun, key=lambda z: abs(z.upper - olay.zemin_tavan))


def _mod2_blok_sec(olay: AdayOlay, b: BarDurum, stop_mod0: float) -> BlokBand | None:
    """TYR-sonrası 1-3 bar limit girişi için minimum risk tabanını koruyan bandı seçer."""
    if b.atr_tf <= 0:
        return None
    min_risk_fiyat = MOD2_MIN_RISK_ATR * b.atr_tf
    if olay.yon == "long":
        uygun = [
            z for z in b.blok_bull
            if _gecerli_blok_mu(z, b)
            and (stop_mod0 + min_risk_fiyat) <= z.upper < (b.close - 0.05 * b.atr_tf)
        ]
        if not uygun:
            return None
        return max(uygun, key=lambda z: z.upper)
    uygun = [
        z for z in b.blok_bear
        if _gecerli_blok_mu(z, b)
        and (b.close + 0.05 * b.atr_tf) < z.lower <= (stop_mod0 - min_risk_fiyat)
    ]
    if not uygun:
        return None
    return min(uygun, key=lambda z: z.lower)


def plan_karti_olustur(
    olay: AdayOlay,
    b: BarDurum,
    *,
    mod: str = "mod0",
    tampon_atr: float = TAMPON_VARSAYILAN_ATR,
) -> PlanKartV2:
    """Aday olay için belirtilen modda (mod0/mod1/mod2) plan kartı üretir."""
    atr = b.atr_tf
    giris_baz = b.close
    stop_mod0 = (
        olay.zemin_tavan - tampon_atr * atr
        if olay.yon == "long"
        else olay.zemin_tavan + tampon_atr * atr
    )

    if mod == "mod0":
        giris = giris_baz
        stop = stop_mod0
        blok_kul = False
        blok_bilgi = ""
        limit_fiyat = None
    elif mod == "mod1":
        giris = giris_baz
        band = _mod1_blok_sec(olay, b, stop_mod0)
        if band is not None:
            if olay.yon == "long":
                aday_stop = band.lower - tampon_atr * atr
                stop = aday_stop if aday_stop < giris - 0.25 * atr else min(stop_mod0, aday_stop)
            else:
                aday_stop = band.upper + tampon_atr * atr
                stop = aday_stop if aday_stop > giris + 0.25 * atr else max(stop_mod0, aday_stop)
            blok_kul = True
            blok_bilgi = f"{band.family}:{band.lower:.4f}-{band.upper:.4f}"
        else:
            stop = stop_mod0
            blok_kul = False
            blok_bilgi = ""
        limit_fiyat = None
    elif mod == "mod2":
        band = _mod2_blok_sec(olay, b, stop_mod0)
        if band is not None:
            limit_fiyat = float(band.upper if olay.yon == "long" else band.lower)
            giris = limit_fiyat
            stop = stop_mod0
            blok_kul = True
            blok_bilgi = f"{band.family}:{band.lower:.4f}-{band.upper:.4f}"
        else:
            giris = giris_baz
            stop = stop_mod0
            limit_fiyat = None
            blok_kul = False
            blok_bilgi = ""
    else:
        raise ValueError(f"Bilinmeyen mod: {mod}")

    risk = abs(giris - stop)
    risk_atr = (risk / atr) if atr > 0 else 0.0
    hedef_yap, kaynak, karsi_n = karsit_yapisal_hedef(olay, b, giris)
    r_yap = (
        round(abs(hedef_yap - giris) / risk, 4)
        if (hedef_yap is not None and math.isfinite(hedef_yap) and risk > 1e-9)
        else None
    )
    return PlanKartV2(
        olay_id=olay.olay_id,
        mod=mod,
        tampon_atr=float(tampon_atr),
        yon=olay.yon,
        giris=float(giris),
        stop=float(stop),
        risk_atr=round(float(risk_atr), 4),
        hedef_yapisal=float(hedef_yap) if hedef_yap is not None else None,
        r_yapisal=r_yap,
        hedef_kaynagi=kaynak,
        blok_kullanildi=blok_kul,
        blok_bilgisi=blok_bilgi,
        limit_fiyat=limit_fiyat,
        karsi_aday_sayisi=karsi_n,
    )
