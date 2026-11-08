"""Ok denetimi — her okun "neden orada" olduğunu sembol sembol çıkarır.

Üretim kodunu DEĞİŞTİRMEZ; yalnız okun üretildiği davranışı (StabilBarBehavior)
okur, hangi kuralın ateşlediğini söyler ve ölçülmüş koşullara göre bayrak takar.

Kurallar (üretim koduyla birebir):
  K1 close_reclaim          → ▲  destek altına sarktıktan sonra gövdeyle üstüne kapanış
  K2 intrabar_sweep_reclaim → ▲  fitille altı süpürülüp aynı mumda üstüne dönüş
  M1 long_base_breakout     → ▲  ≥20 gün sabit destek üstünde güçlü gövdeyle kopuş
  M2 upward_rebase_momentum → ▲  destek yukarı basamak yaparken güçlü yukarı mum
  U1 vertical_attempt_kind  → ▼  dikey destek + yukarı deneme (yapı uyarısı, ▲ bastırılır)

Bayraklar (rev10 ölçümüne dayanır):
  GOVDESIZ    gövde < 0,20 ATR      → rev10: gövdesiz mumda sinyal yok
  SESSIZ      rvol < 0,8            → rev10: sessiz günde sinyal yok
  KADEME_ASAGI destek aşağı kademede → rev10: bu durumda yukarı ok ters risk taşır
  REJIM_YOK   destek rejimi bilinmiyor (ısınma/veri boşluğu) → ok yine de basılmış
  ALTI_BOS    fiyat çizginin >1 ATR üstünde ve çizgi dikey → aşağıda destek yok
  UZAK        |mesafe| > 1,8 ATR    → artık çizgi olayı değil
  YORGUN      temas ≥ 3             → çizgi yıpranmış
  TEKRAR      aynı yönde ok son 5 barda da var → gereksiz tekrar
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from domain_engines.stabil.candidate_regime import CandidateLineRegime
from domain_engines.stabil.stabil_support_lifecycle import SupportValidity

#: kural kimliği → (ok, kısa ad, gerekçe şablonu)
KURALLAR: dict[str, tuple[str, str, str]] = {
    "close_reclaim": ("▲", "K1", "Destek altına sarktıktan sonra gövdeyle destek üstüne kapanış"),
    "intrabar_sweep_reclaim": ("▲", "K2", "Fitille destek altı süpürüldü, aynı mumda üstüne dönüş"),
    "long_base_breakout": ("▲", "M1", "Uzun süre sabit desteğin üstünde güçlü gövdeyle kopuş"),
    "upward_rebase_momentum": ("▲", "M2", "Destek yukarı basamak yaparken güçlü yukarı mum"),
}

_GOVDE_ESIK = 0.20      # rev10 kilidi
_RVOL_ESIK = 0.8        # rev10 kilidi
_UZAK_ATR = 1.80
_TEKRAR_BAR = 5


@dataclass(frozen=True, slots=True)
class OkDenetim:
    bar_index: int
    bar_close_time: Any
    ok: str
    kural_kimlik: str
    kural_adi: str
    gerekce: str
    destek: float | None
    kapanis: float | None
    mesafe_atr: float | None
    govde_atr: float | None
    rvol: float | None
    kapanis_poz: float | None
    rejim: str
    temas: int
    dikey: bool
    bayraklar: tuple[str, ...]

    @property
    def karar(self) -> str:
        if any(b in {"KADEME_ASAGI", "REJIM_YOK", "ALTI_BOS", "TEKRAR"} for b in self.bayraklar):
            return "ŞÜPHELİ"
        if any(b in {"GOVDESIZ", "SESSIZ", "UZAK", "YORGUN"} for b in self.bayraklar):
            return "ZAYIF"
        return "SAĞLAM"


def _sayi(x: Any) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    return f"{v:.2f}".replace(".", ",") if abs(v) < 100 else f"{v:.1f}"


def ok_kurali(behavior: Any) -> tuple[str, str] | None:
    """Bir barda ok üretilmişse (ok, kural_kimlik) döndürür."""
    attempt = getattr(behavior, "vertical_attempt_kind", None)
    if attempt:
        return "▼", f"U1:{attempt}"
    kind = getattr(behavior, "reclaim_kind", None)
    if kind in KURALLAR:
        return KURALLAR[kind][0], kind
    kind = getattr(behavior, "momentum_kind", None)
    if kind in KURALLAR:
        return KURALLAR[kind][0], kind
    return None


def _bayraklar(b: Any, onceki_okler: Sequence[tuple[int, str]]) -> tuple[str, ...]:
    out: list[str] = []
    govde = getattr(b, "body_atr", None)
    rvol = getattr(b, "vol_ratio", None)
    mesafe = getattr(b, "dist_atr", None)
    rejim = str(getattr(b, "regime", "") or "")

    if govde is not None and abs(float(govde)) < _GOVDE_ESIK:
        out.append("GOVDESIZ")
    if rvol is not None and float(rvol) < _RVOL_ESIK:
        out.append("SESSIZ")
    if rejim in {"", CandidateLineRegime.UNAVAILABLE.value}:
        out.append("REJIM_YOK")
    if rejim == CandidateLineRegime.STEPPING_DOWN.value:
        out.append("KADEME_ASAGI")
    if mesafe is not None and abs(float(mesafe)) > _UZAK_ATR:
        out.append("UZAK")
    if int(getattr(b, "touch_count", 0) or 0) >= 3:
        out.append("YORGUN")
    dikey = bool(getattr(b, "vertical_support", False))
    if dikey and mesafe is not None and float(mesafe) > 1.0:
        out.append("ALTI_BOS")
    if any(abs(b.bar_index - idx) <= _TEKRAR_BAR for idx, _ in onceki_okler):
        out.append("TEKRAR")
    return tuple(out)


def denetle(behaviors: Sequence[Any]) -> list[OkDenetim]:
    kayitlar: list[OkDenetim] = []
    onceki: list[tuple[int, str]] = []
    for b in behaviors:
        bulunan = ok_kurali(b)
        if bulunan is None:
            continue
        ok, kid = bulunan
        if kid.startswith("U1:"):
            ad = "U1"
            gerekce = "Dikey destek üzerinde yukarı deneme — ▲ bastırıldı, ▼ yapı uyarısı"
        else:
            _, ad, gerekce = KURALLAR[kid]
        kayitlar.append(
            OkDenetim(
                bar_index=int(b.bar_index),
                bar_close_time=b.bar_close_time,
                ok=ok,
                kural_kimlik=kid,
                kural_adi=ad,
                gerekce=gerekce,
                destek=getattr(b, "support_level", None),
                kapanis=getattr(b, "close_price", None),
                mesafe_atr=getattr(b, "dist_atr", None),
                govde_atr=getattr(b, "body_atr", None),
                rvol=getattr(b, "vol_ratio", None),
                kapanis_poz=getattr(b, "close_pos", None),
                rejim=str(getattr(b, "regime", "") or ""),
                temas=int(getattr(b, "touch_count", 0) or 0),
                dikey=bool(getattr(b, "vertical_support", False)),
                bayraklar=_bayraklar(b, onceki),
            )
        )
        onceki.append((int(b.bar_index), ok))
    return kayitlar


def aciklama(k: OkDenetim) -> str:
    """Tek satır: hangi orandan dolayı bu ok konmuş."""
    parca = [
        f"{k.kural_adi}: {k.gerekce}",
        f"kapanış çizginin {_sayi(k.mesafe_atr)} ATR üstünde",
        f"gövde {_sayi(k.govde_atr)} ATR",
        f"hacim {_sayi(k.rvol)}x",
        f"kapanış pozisyonu {_sayi(k.kapanis_poz)}",
        f"temas {k.temas}",
        f"rejim {k.rejim or '—'}",
    ]
    return " · ".join(parca)
