"""G1–G5 adaptörleri — mevcut motor çıktılarını **okur**, motor değiştirmez.

Her adaptör as-of prensibiyle çalışır: ``t`` (veya bar indeksi ``i``) anından
önceki olaylar/durumlar dışında hiçbir şey okunmaz. Çıktılar:
``G1Durum``/``G2Durum``/``MSUyari``/``G5Durum`` — bunlardan ``bildirim_uret``
§3 şemasında bildirilere dönüşür (uydurma yasağı: her kaynak ``n=`` taşır).

Kaynak sabitleri (gerçek ölçüm tabloları):
* ``OK_SISTEMI_2026-11-08 §12`` — onaylı tutunma R3: keşif %63,5 vs %49,6
  (lift +14,0), doğrulama %58,9 vs %50,1; 716 ok (176 sembol, 1g).
* ``STABIL_OK sentezi §12`` — koşulsuz destek TEST: tepki %41,3 / kırılma
  %51,6 (n = 1.616; 8×4s, 174 hisse).
* ``ARASTIRMA_SONUCLARI`` — MS olay defteri n = 202.938; formasyon n = 34.455;
  zone n = 187.046; dokunuş n = 240.484 (altın toplamlar, 2026-10-29 kapısı).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from .modeller import Bildirim

# --- sabit kaynaklar (uydurma yasağı) --------------------------------------
KAY_STABIL_ONAY = "OK_SISTEMI_2026-11-08 §12 onaylı tutunma R3 · n=716"
KAY_STABIL_TEST = "STABIL_OK sentezi §12 koşulsuz TEST · n=1616"
KAY_MS = "ARASTIRMA_SONUCLARI MS olay defteri · n=202938"
KAY_FRM = "ARASTIRMA_SONUCLARI formasyon · n=34455"
KAY_ZONE = "ARASTIRMA_SONUCLARI zone · n=187046"
KAY_DOKUNUS = "ARASTIRMA_SONUCLARI dokunuş · n=240484"

TAZE_MS_BAR = 5            # plan §3: yaş ≤ 5 bar → taze uyarı
GECTERSIZ_ZEMIN = {"BREACHED", "BELOW_FLOOR"}


# --- G1: Stabil (1g) -------------------------------------------------------
@dataclass(frozen=True, slots=True)
class G1Durum:
    t: str
    zemin: str = "NO_SUPPORT"       # SupportValidity
    destek: float | None = None
    onayli: bool = False
    dinamik: str = "UNAVAILABLE"
    ilerleme: str = "NONE"
    mesafe_atr: float | None = None
    trend_gunluk: str = "PENDING"
    trend_hazir: bool = False
    kapali: bool = False            # zemin BREACHED/BELOW_FLOOR → G1 kapandı
    olaylar: tuple[str, ...] = ()

    @property
    def kapi_acik(self) -> bool:
        """Yön kapısı: geçerli zemin var (onay şart değil — onay ayrı sinyal)."""
        return self.zemin == "ACTIVE" and not self.kapali


def g1_durumu(history: Any, t: Any) -> G1Durum:
    """Stabil tek-geçiş önbelleğinden ``t`` anının as-of durumu (sorgu ≤ t)."""
    _idx, snap = history.support_at(t)
    ctx = history.trend_at(t)
    daily = getattr(ctx, "daily", None)
    zemin = str(getattr(snap, "validity", "NO_SUPPORT"))
    olaylar = tuple(
        str(getattr(e, "event_type", e)) for e in (getattr(snap, "events", ()) or ())[-3:]
    )
    return G1Durum(
        t=pd.Timestamp(t).isoformat(),
        zemin=zemin,
        destek=(float(snap.support_level) if getattr(snap, "support_level", None) is not None else None),
        onayli=getattr(snap, "support_confirmed_at", None) is not None,
        dinamik=str(getattr(snap, "dynamics", "UNAVAILABLE")),
        ilerleme=str(getattr(snap, "progression", "NONE")),
        mesafe_atr=(float(snap.distance_atr) if getattr(snap, "distance_atr", None) is not None else None),
        trend_gunluk=str(getattr(daily, "state", "PENDING")) if daily is not None else "PENDING",
        trend_hazir=bool(getattr(daily, "data_ready", False)) if daily is not None else False,
        kapali=zemin in GECTERSIZ_ZEMIN,
        olaylar=olaylar,
    )


# --- G2: Formasyon (2s/4s) — bağlam/yol haritası ---------------------------
@dataclass(frozen=True, slots=True)
class G2Durum:
    aktif: bool = False
    stable_id: str = ""
    tip: str = ""
    aile: str = ""
    daralma: float | None = None      # son gözlenen daralma oranı
    ilerleme: float | None = None
    mesafe_alt_atr: float | None = None  # alt sınıra kapanış mesafesi (ATR)
    mesafe_ust_atr: float | None = None
    dogum_bar: int | None = None
    olgun: bool = False               # daralma ≥ %50 veya sınıra ≤ 1 ATR


def g2_durumu(frm_satirlari: Sequence[Mapping[str, Any]], i: int) -> G2Durum:
    """Bar ``i`` anında yaşayan formasyon (doğum ≤ i ≤ ölçüm sonu)."""
    aday = [
        r for r in frm_satirlari
        if r.get("dogum_bar") is not None and r.get("olcum_son_bar") is not None
        and int(r["dogum_bar"]) <= i <= int(r["olcum_son_bar"])
    ]
    if not aday:
        return G2Durum()
    # en taze doğumlu yaşayan aday
    r = max(aday, key=lambda x: int(x["dogum_bar"]))
    daralma = r.get("daralma_orani")
    mesafe_alt = r.get("frm_yakinlik_alt_kapanis_atr")
    mesafe_ust = r.get("frm_yakinlik_ust_kapanis_atr")
    olgun = bool(
        (daralma is not None and float(daralma) >= 0.5)
        or (mesafe_alt is not None and float(mesafe_alt) <= 1.0)
    )
    return G2Durum(
        aktif=True,
        stable_id=str(r.get("stable_id", "")),
        tip=str(r.get("pattern_type") or ""),
        aile=str(r.get("family") or ""),
        daralma=(float(daralma) if daralma is not None else None),
        ilerleme=(float(r["progress_son"]) if r.get("progress_son") is not None else None),
        mesafe_alt_atr=(float(mesafe_alt) if mesafe_alt is not None else None),
        mesafe_ust_atr=(float(mesafe_ust) if mesafe_ust is not None else None),
        dogum_bar=int(r["dogum_bar"]),
        olgun=olgun,
    )


# --- G3: Market Structure — uyarı/erteleme ---------------------------------
@dataclass(frozen=True, slots=True)
class MSUyari:
    tip: str = ""            # BOS | CHOCH | TRANSITION_FAIL | FALSE_BREAK
    yon: str = ""            # up | down
    yas_bar: int = 0         # olaydan beri geçen bar (≤0 = bu bar)
    seviye: float | None = None
    taze: bool = False


def ms_uyarilari(
    event_history: Iterable[Any],
    i: int,
    *,
    yas_esik: int = TAZE_MS_BAR,
) -> list[MSUyari]:
    """``i`` barına kadar onaylanmış MS olayları; tazelik ``i - event_bar`` ile."""
    cikti: list[MSUyari] = []
    for e in event_history or ():
        bar = getattr(e, "event_bar", None)
        if bar is None or int(bar) > i:
            continue  # gelecek olay okunmaz
        ham = str(getattr(e, "event_type", ""))
        tip = ham.replace("EVENT_", "")
        if tip not in {"BOS", "CHOCH", "TRANSITION_FAIL", "FALSE_BREAK"}:
            continue
        yon_val = int(getattr(e, "direction", 0))
        yas = i - int(bar)
        cikti.append(MSUyari(
            tip=tip,
            yon="up" if yon_val > 0 else ("down" if yon_val < 0 else "neutral"),
            yas_bar=yas,
            seviye=(float(e.broken_level) if getattr(e, "broken_level", None) is not None else None),
            taze=yas <= yas_esik,
        ))
    return cikti


# --- G5: Bloklar (1s/2s/4s) — giriş hassasiyeti -----------------------------
@dataclass(frozen=True, slots=True)
class G5Durum:
    bant: tuple[float, float] | None = None
    zone_id: str = ""
    aile: str = ""             # OB | FVG
    dolu: bool = False         # terminal/dolum kaydı var mı (as-of)
    temas_bar: int | None = None   # bant son teması (as-of, ≤ i)
    tepki_onayi: bool = False      # temas sonrası 3 bar içinde bandın üstüne kapanış


def _zone_asof_aktif(z: Mapping[str, Any], i: int) -> bool:
    if int(z.get("available_index", 10**9)) > i:
        return False
    termin = z.get("native_terminal_index")
    if termin is not None and int(termin) <= i:
        return False
    return True


def g5_durumu(
    ob_zonlari: Sequence[Mapping[str, Any]],
    fvg_zonlari: Sequence[Mapping[str, Any]],
    frame: pd.DataFrame,
    i: int,
    *,
    yon: str = "long",
) -> G5Durum:
    """``i`` anında fiyata en yakın yaşayan giriş bandı + tepki onayı.

    ``frame``: ``_normalize_frame`` çıktısı (RangeIndex + timestamp kolonu).
    Tepki onayı: band temasından sonraki 3 bar içinde bandın beklenen yönde
    dışına kapanış (uzun: ``close ≥ band_hi``). Blok işlemi **engellemez**:
    banda yoksa ``bant=None`` kalır, zincir devam eder.
    """
    if len(frame) == 0 or i < 0 or i >= len(frame):
        return G5Durum()
    kapanis = float(frame.at[i, "close"])
    beklenen = "bullish" if yon == "long" else "bearish"
    adaylar: list[tuple[float, Mapping[str, Any]]] = []
    for z in list(ob_zonlari) + list(fvg_zonlari):
        if str(z.get("direction", "")) != beklenen:
            continue
        if not _zone_asof_aktif(z, i):
            continue
        lo, hi = float(z["zone_lower"]), float(z["zone_upper"])
        uzaklik = 0.0 if lo <= kapanis <= hi else min(abs(kapanis - lo), abs(kapanis - hi))
        adaylar.append((uzaklik, z))
    if not adaylar:
        return G5Durum()
    _, z = min(adaylar, key=lambda x: x[0])
    lo, hi = float(z["zone_lower"]), float(z["zone_upper"])

    temaslar = [c for c in (z.get("contact_bars") or []) if int(c.get("index", 10**9)) <= i]
    temas_bar = int(temaslar[-1]["index"]) if temaslar else None

    tepki = False
    if temas_bar is not None:
        uc_bar = range(temas_bar + 1, min(temas_bar + 4, len(frame)))
        for j in uc_bar:
            c = float(frame.at[j, "close"])
            tepki = (c >= hi) if yon == "long" else (c <= lo)
            if tepki:
                break

    aile = str(z.get("family", ""))
    dolu = (z.get("native_terminal_index") is not None) or (
        (z.get("native_fill_ratio_at_terminal_or_asof") or 0) >= 0.5
    )
    return G5Durum(
        bant=(lo, hi),
        zone_id=str(z.get("zone_id", "")),
        aile=aile,
        dolu=bool(dolu),
        temas_bar=temas_bar,
        tepki_onayi=tepki,
    )


# --- Bildiri üretimi (§3 şeması) -------------------------------------------
def bildirim_uret(
    *,
    sembol: str,
    tf: str,
    t: str,
    g1: G1Durum,
    g2: G2Durum,
    ms_olaylari: Sequence[MSUyari],
    g5: G5Durum,
) -> list[Bildirim]:
    """As-of durumlardan katman bildirileri (karar vermez, görev+seviye verir)."""
    out: list[Bildirim] = []

    # G1 — stabil
    if g1.kapali:
        out.append(Bildirim(
            sembol=sembol, tf=tf, t=t, kim="stabil", iddia="bozulma",
            kosul=f"zemin {g1.zemin} (destek öldü/onay bekliyor)",
            kaynak=KAY_STABIL_TEST, gecerlilik_bar=10,
            seviyeler=(g1.destek,) if g1.destek is not None else (),
            dogrudan="bekle",
        ))
    elif g1.kapi_acik:
        out.append(Bildirim(
            sembol=sembol, tf=tf, t=t, kim="stabil", iddia="izle",
            kosul=f"zemin ACTIVE, dinamik {g1.dinamik}, trend {g1.trend_gunluk}",
            kaynak=(KAY_STABIL_ONAY if g1.onayli else KAY_STABIL_TEST),
            gecerlilik_bar=20,
            seviyeler=(g1.destek,) if g1.destek is not None else (),
            uyari_metni="" if g1.onayli else "onay yok — koşulsuz testte kırılma %51,6",
            dogrudan="takip_et",
        ))
    else:
        # sessizlik: durum belirsiz — kayıt yine yazılır (kırmızı çizgi 7)
        out.append(Bildirim(
            sembol=sembol, tf=tf, t=t, kim="stabil", iddia="bekle",
            kosul=f"zemin {g1.zemin} — kapı belirsiz, G2-G5'e sıra gelmedi sayılır",
            kaynak=KAY_STABIL_TEST, gecerlilik_bar=10,
            dogrudan="bekle",
        ))

    # G2 — formasyon (yoksa bağlam satırı boş kalır; zincir devam eder)
    if g2.aktif:
        out.append(Bildirim(
            sembol=sembol, tf=tf, t=t, kim="formasyon", iddia="izle",
            kosul=(f"{g2.tip} aktif, daralma "
                   f"{f'%{g2.daralma * 100:.0f}' if g2.daralma is not None else 'bilinmiyor'}"
                   + (", sınıra yakın" if g2.olgun else ", olgunlaşmadı")),
            kaynak=KAY_FRM, gecerlilik_bar=20,
            uyari_metni="daralma olgunlaşabilir; kırılım denemesi riski var",
            dogrudan="haber_ver",
        ))

    # G3 — MS (taze olaylar yazılır; taze-olmayan yazılmaz)
    for u in ms_olaylari:
        if not u.taze:
            continue
        out.append(Bildirim(
            sembol=sembol, tf=tf, t=t, kim="ms",
            iddia="uyari" if u.yon == "down" else "olasi_tepki",
            # İmza sabittir (yaş sayılmaz): aynı koşul her bar yeniden yazılmaz.
            kosul=f"{u.tip} {u.yon} taze",
            kaynak=KAY_MS, gecerlilik_bar=max(1, TAZE_MS_BAR - u.yas_bar),
            seviyeler=(u.seviye,) if u.seviye is not None else (),
            uyari_metni="taze karşıt yapı — erken girişin panzehridi, bekleyelim"
                        if u.yon == "down" else "taze boş yön uyumlu",
            dogrudan="bekle" if u.yon == "down" else "takip_et",
        ))

    # G5 — blok (yalnız UYGUN sonrası devrede; izleme seviyesi olarak durur)
    if g5.bant is not None:
        out.append(Bildirim(
            sembol=sembol, tf=tf, t=t, kim="blok",
            iddia="onay_bekliyor" if not g5.tepki_onayi else "konfluans",
            kosul=(f"{g5.aile} bandı {'temaslı' if g5.temas_bar is not None else 'temassız'}"
                   + (", tepki onayı var" if g5.tepki_onayi else ", onay yok")),
            kaynak=KAY_DOKUNUS if g5.aile == "OB" else KAY_ZONE,
            gecerlilik_bar=10,
            seviyeler=(g5.bant[0], g5.bant[1]),
            dogrudan="takip_et",
        ))

    return out
