"""Yeni domain tetiklemeli bildirim kanalı (kullanıcı kararı, 2026-11-03).

Mevcut formasyon push'u, 4S Stabil geri alım alarmı, replay sonuçları ve kart
metinleri **değiştirilmez**. Bu modül yalnızca ek bir aday üretir: BOS/CHoCH,
formasyon, OB/FVG tepkisi veya grafikteki RVOL mantığıyla olağandışı hacim
olduğunda, o anki **native basamaklı** Stabil desteğine bakılır.

Kural:
* `dist_atr >= YENI_DOMAIN_ALARM_DIST_ATR_ALT` (varsayılan -3.0) HARD alt sınır.
* Üst sınır YOK: fiyat desteğin 5 ATR üstünde de tetikleyebilir.
* Hacim hard `AND` kapısı DEĞİLDİR; kendi başına ayrı tetikleyicidir.
* Bildirim ana DM + public hedefe gider ve kart `🆕 YENİ` ile işaretlenir.
* Aynı sembol/TF/bar tekrar basılmaz; bar bazlı cooldown korunur.
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

import pandas as pd

import config
from data import bar_kapandi_mi, mum_kapanis_ani
from domain_engines.stabil import format_stabil_card_lines
from notification_context import (
    _alarm_tf_rvol,
    _domain,
    _event_rows,
    _field,
    _number,
    _token,
    _usable_export,
)
from state.paths import yeni_domain_alarm_state_yolu
from telegram_measure import metni_sigdir

logger = logging.getLogger(__name__)

YENI_KART_ISARETI = "🆕 YENİ"
_TF_ETIKET = {"1h": "1s", "2h": "2s", "4h": "4s", "1d": "1g"}
_GECERSIZ_FORMASYON = {"FORMASYON_GECERSIZ", "YOK", "ST_NONE", "NONE", ""}


@dataclass(frozen=True, slots=True)
class DomainAlarmCandidate:
    symbol: str
    timeframe: str
    bar_open: str
    bar_close: str
    bar_label: str
    bar_index: int
    close_price: float
    support_level: float | None
    dist_atr: float
    relation: str
    reasons: tuple[str, ...]
    volume_rvol: float | None
    volume_tier: str | None
    volume_source: str
    data_quality: str
    card_lines: tuple[str, ...]
    rank_score: float

    @property
    def dedup_key(self) -> str:
        return f"{self.symbol}|{self.timeframe}|{self.bar_open}"

    @property
    def reason_signature(self) -> str:
        return "|".join(sorted(self.reasons))


def _tr_sayi(deger: float | None, ondalik: int = 2) -> str:
    if deger is None:
        return "—"
    try:
        v = float(deger)
    except (TypeError, ValueError, OverflowError):
        return "—"
    if not math.isfinite(v):
        return "—"
    kalip = f"{v:,.{ondalik}f}"
    return kalip.replace(",", "_").replace(".", ",").replace("_", ".")


def _tf_etiket(tf: str) -> str:
    return _TF_ETIKET.get(str(tf).lower(), str(tf))


def _cfg_sayi(ad: str, varsayilan: float) -> float:
    try:
        return float(getattr(config, ad, varsayilan))
    except (TypeError, ValueError, OverflowError):
        return varsayilan


def _cfg_int(ad: str, varsayilan: int) -> int:
    try:
        return max(1, int(getattr(config, ad, varsayilan)))
    except (TypeError, ValueError, OverflowError):
        return varsayilan


def _token_temiz(deger: Any) -> str:
    return str(_token(deger) or "").strip()


def _stabil_bilgisi(results: Mapping[str, Any], tf: str,
                    frame: pd.DataFrame) -> dict[str, Any] | None:
    """O anki native basamaklı destek + `dist_atr` + ilişki + 2 satırlık kart."""
    entry = _domain(results, tf, "stabil")
    if entry is None or _field(entry, "error") or bool(_field(entry, "skipped", False)):
        return None

    details = _field(entry, "details", {}) or {}
    out = _field(entry, "result")
    bhv = _field(details, "latest_behavior") or _field(out, "latest_behavior")
    if bhv is None:
        return None

    dist = _number(_field(bhv, "dist_atr"))
    if dist is None or not math.isfinite(dist):
        # Hard alt sınır doğrulanamıyorsa UNKNOWN; sessiz "geçti" denmez.
        return None

    alt_sinir = _cfg_sayi("YENI_DOMAIN_ALARM_DIST_ATR_ALT", -3.0)
    if dist < alt_sinir:
        return None

    sup = _number(_field(bhv, "support_level"))
    if sup is None:
        projeksiyon = _field(details, "bar_projection") or _field(out, "bar_projection") or ()
        if projeksiyon:
            sup = _number(_field(projeksiyon[-1], "support_level"))

    try:
        close = float(frame["close"].iloc[-1])
    except (KeyError, IndexError, TypeError, ValueError, OverflowError):
        close = _number(_field(bhv, "close_price"))
    if close is None or not math.isfinite(close):
        return None

    relation = str(
        _field(details, "latest_support_relation")
        or _field(out, "latest_support_relation")
        or ""
    ).strip()
    if not relation:
        if dist > 0.25:
            relation = "destek üstünde"
        elif dist < -0.15:
            relation = "destek altında"
        else:
            relation = "destekte"

    try:
        kart = tuple(
            format_stabil_card_lines(
                price=close, support_level=sup, behavior=bhv,
            )[:2]
        )
    except Exception as exc:  # noqa: BLE001 - kart satırı alarmı düşürmesin
        logger.debug("Yeni domain Stabil kart satırı atlandı: %s", exc)
        kart = ()

    kalite = _token_temiz(_field(entry, "data_quality")) or "OK"
    if kalite == "READY":
        kalite = "OK"

    return {
        "dist_atr": float(dist),
        "support_level": sup,
        "close_price": close,
        "relation": relation,
        "card_lines": kart,
        "data_quality": kalite,
        "behavior": bhv,
    }


def _bos_ve_choch_sebepleri(results: Mapping[str, Any], tf: str,
                            frame_len: int) -> list[str]:
    """Yalnız son 2 bardaki teyitli/aktif BOS-CHoCH olaylarını al."""
    export = _usable_export(_domain(results, tf, "market_structure"))
    if export is None:
        return []
    esik_bar = max(0, frame_len - 2)
    bulunan: list[str] = []
    for event in _event_rows(export):
        tip = _token_temiz(_field(event, "event_type"))
        if tip not in {"EVENT_BOS", "BOS", "EVENT_CHOCH", "CHOCH"}:
            continue
        if _token_temiz(_field(event, "confirmation_status")) != "CONFIRMED":
            continue
        if _token_temiz(_field(event, "validity")) == "FAILED":
            continue
        if _token_temiz(_field(event, "relevance")) in {"SUPERSEDED", "HISTORICAL"}:
            continue
        if not bool(_field(event, "is_active", True)):
            continue
        bar = _number(_field(event, "event_bar"))
        if bar is None or bar < esik_bar:
            continue
        yon = _number(_field(event, "direction")) or 0.0
        ok = "↑" if yon > 0 else ("↓" if yon < 0 else "")
        kisa = "CHoCH" if "CHOCH" in tip else "BOS"
        bulunan.append(f"{kisa} {ok}".strip())
    return sorted(set(bulunan))


def _bolge_sebepleri(results: Mapping[str, Any], tf: str,
                     close: float) -> list[str]:
    """OB/FVG: fiyat aktif bölgenin içindeyse veya FVG `reaksiyon` state'indeyse."""
    bulunan: list[str] = []
    for alan, tip, yanlar in (
        ("order_block", "OB", ("bull", "bear")),
        ("fvg", "FVG", ("bull_fvg", "bear_fvg")),
    ):
        export = _usable_export(_domain(results, tf, alan))
        if export is None:
            continue
        for anahtar in yanlar:
            yan = _field(export, anahtar)
            top = _number(_field(yan, "top"))
            bottom = _number(_field(yan, "bottom"))
            if top is None or bottom is None or top < bottom:
                continue
            icinde = bottom <= close <= top
            state = _number(_field(yan, "state"))
            reaksiyon = bool(
                tip == "FVG" and state is not None and abs(int(state)) == 8
            )
            if not (icinde or reaksiyon):
                continue
            yon = "boğa" if "bull" in anahtar else "ayı"
            if reaksiyon:
                bulunan.append(f"{tip} {yon} reaksiyon")
            else:
                bulunan.append(f"{tip} {yon} bölge tepkisi")
    return sorted(set(bulunan))


def _hacim_bilgisi(results: Mapping[str, Any], tf: str,
                   frame: pd.DataFrame) -> dict[str, Any]:
    """Grafikteki RVOL mantığı: motor `rvol`, yoksa `hacim / SMA20` yerel."""
    rvol = _number(_alarm_tf_rvol(results, tf))
    kaynak = "motor"
    if rvol is None or rvol <= 0 or not math.isfinite(rvol):
        rvol = None
        kaynak = "yerel"
        try:
            hacimler = pd.to_numeric(frame["volume"], errors="coerce").astype(float)
            if len(hacimler) >= 20:
                ortalama = float(hacimler.iloc[-20:].mean())
                son = float(hacimler.iloc[-1])
                if ortalama > 0 and math.isfinite(son) and math.isfinite(ortalama):
                    rvol = son / ortalama
        except Exception as exc:  # noqa: BLE001 - hacim alanı alarmı düşürmesin
            logger.debug("Yerel RVOL hesaplanamadı: %s", exc)

    vp = _domain(results, tf, "volume_participation")
    details = _field(vp, "details", {}) or {} if vp is not None else {}
    metrics = _field(details, "latest_metrics")
    volume_usable = _field(metrics, "volume_usable", True) if metrics is not None else True
    if volume_usable is None:
        volume_usable = True

    esik5 = _cfg_sayi("YENI_DOMAIN_ALARM_HACIM_5X", 5.0)
    esik10 = _cfg_sayi("YENI_DOMAIN_ALARM_HACIM_10X", 10.0)
    suphe = _cfg_sayi("YENI_DOMAIN_ALARM_HACIM_SUPHE", 50.0)

    tier: str | None = None
    if rvol is not None and math.isfinite(rvol):
        if rvol >= esik10:
            tier = "10×"
        elif rvol >= esik5:
            tier = "5×"

    veri_suphe = bool(
        rvol is not None and (rvol >= suphe or not bool(volume_usable))
    )
    return {
        "rvol": rvol,
        "source": kaynak,
        "tier": tier,
        "veri_suphe": veri_suphe,
        "sebep": (
            f"hacim {tier} ({_tr_sayi(rvol, 1)}×)"
            if tier and rvol is not None else None
        ),
    }


def _formasyon_sebepleri(kayitlar: Sequence[Mapping[str, Any]] | None,
                         tf: str) -> list[str]:
    if not kayitlar:
        return []
    tekrar = bool(getattr(config, "YENI_DOMAIN_ALARM_IMMEDIATE_TEKRAR", False))
    anlik = {str(s).upper() for s in getattr(config, "ALERT_STATES", ())}
    bulunan: list[str] = []
    for kayit in kayitlar:
        if not isinstance(kayit, Mapping):
            continue
        if str(kayit.get("timeframe", "")).lower() != str(tf).lower():
            continue
        state = str(kayit.get("state") or "").strip().upper()
        bildirim = str(kayit.get("notification_state") or state).strip().upper()
        if state in _GECERSIZ_FORMASYON or bildirim in _GECERSIZ_FORMASYON:
            continue
        if not tekrar and bildirim in anlik:
            # Aynı olay zaten mevcut ana alarma gitti; ikinci kart üretme.
            continue
        try:
            q = float(kayit.get("quality") or 0.0)
            min_q = float(kayit.get("min_quality") or 0.0)
        except (TypeError, ValueError, OverflowError):
            continue
        if q < min_q:
            continue
        tip = str(kayit.get("pattern_name") or "formasyon").strip()
        bulunan.append(f"formasyon: {tip} · {state or bildirim}")
    return sorted(set(bulunan))


def evaluate_domain_alarm_candidates(
    stock: str,
    all_tfs: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame],
    results: Mapping[str, Any],
    simdiki_zaman: datetime,
    *,
    formasyon_kayitlari: Sequence[Mapping[str, Any]] | None = None,
    bar_metni_fn: Any = None,
) -> list[DomainAlarmCandidate]:
    """Bir sembol için yeni kanal adaylarını üret; canlı state'e yazmaz."""
    if not bool(getattr(config, "YENI_DOMAIN_ALARM", True)):
        return []
    if (
        str(getattr(config, "sembol_turu", lambda _s: "")(stock)).lower() == "makro"
        and not bool(getattr(config, "MAKRO_ALARM", False))
    ):
        return []
    if not isinstance(results, Mapping) or not isinstance(frames, Mapping):
        return []

    taze_sinir = _cfg_int("YENI_DOMAIN_ALARM_TAZE_DK", 390)
    adaylar: list[DomainAlarmCandidate] = []

    for tf, frame in frames.items():
        tf = str(tf).lower()
        if tf not in results or not isinstance(frame, pd.DataFrame) or len(frame) < 30:
            continue
        per_tf = results.get(tf)
        if not isinstance(per_tf, Mapping):
            continue

        try:
            son_acilis = frame.index[-1]
            if not bar_kapandi_mi(son_acilis, tf, now=simdiki_zaman):
                continue
            kapanis = mum_kapanis_ani(son_acilis, tf)
            if kapanis is None:
                continue
            simdi_ts = pd.Timestamp(simdiki_zaman)
            kapanis_ts = pd.Timestamp(kapanis)
            if simdi_ts.tzinfo is None:
                simdi_ts = simdi_ts.tz_localize("Europe/Istanbul")
            if kapanis_ts.tzinfo is None:
                kapanis_ts = kapanis_ts.tz_localize("Europe/Istanbul")
            yas_dk = (simdi_ts - kapanis_ts).total_seconds() / 60.0
            if yas_dk < -1.0 or yas_dk > taze_sinir:
                continue
        except Exception as exc:  # noqa: BLE001 - bozuk TF diğerlerini engellemesin
            logger.debug("Yeni domain bar kontrolü atlandı %s/%s: %s", stock, tf, exc)
            continue

        stabil = _stabil_bilgisi(results, tf, frame)
        if stabil is None:
            continue

        close = float(stabil["close_price"])
        sebepler: list[str] = []
        sebepler.extend(_bos_ve_choch_sebepleri(results, tf, len(frame)))
        sebepler.extend(_bolge_sebepleri(results, tf, close))
        sebepler.extend(_formasyon_sebepleri(formasyon_kayitlari, tf))

        hacim = _hacim_bilgisi(results, tf, frame)
        if hacim["sebep"]:
            sebepler.append(hacim["sebep"])
        sebepler = sorted(set(s for s in sebepler if s))
        if not sebepler:
            continue

        kalite = str(stabil["data_quality"] or "OK")
        if hacim["veri_suphe"]:
            kalite = "VERI_SUPHE"

        try:
            bar_label = (
                str(bar_metni_fn(tf, son_acilis, kapanis) or "")
                if callable(bar_metni_fn)
                else kapanis_ts.strftime("%d.%m %H:%M")
            )
        except Exception:  # noqa: BLE001 - etiket alarmı düşürmesin
            bar_label = kapanis_ts.strftime("%d.%m %H:%M")

        puan = float(len(sebepler))
        if hacim["tier"] == "10×":
            puan += 4.0
        elif hacim["tier"] == "5×":
            puan += 2.0
        if stabil["dist_atr"] < 0:
            puan += 1.5  # çöküş / risk tarafı
        if any("BOS" in s or "CHoCH" in s for s in sebepler):
            puan += 1.0

        adaylar.append(
            DomainAlarmCandidate(
                symbol=str(stock).upper(),
                timeframe=tf,
                bar_open=pd.Timestamp(son_acilis).isoformat(),
                bar_close=pd.Timestamp(kapanis).isoformat(),
                bar_label=bar_label,
                bar_index=int(len(frame) - 1),
                close_price=close,
                support_level=stabil["support_level"],
                dist_atr=float(stabil["dist_atr"]),
                relation=str(stabil["relation"]),
                reasons=tuple(sebepler),
                volume_rvol=hacim["rvol"],
                volume_tier=hacim["tier"],
                volume_source=str(hacim["source"]),
                data_quality=kalite,
                card_lines=tuple(stabil["card_lines"]),
                rank_score=puan,
            )
        )

    return adaylar


# --- Kalıcı dedup / cooldown -------------------------------------------------

def _state_yolu(state_path: str | None = None) -> str:
    return state_path or yeni_domain_alarm_state_yolu()


def _load_state(state_path: str | None = None) -> dict[str, Any]:
    yol = _state_yolu(state_path)
    try:
        if os.path.exists(yol):
            with open(yol, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict) and isinstance(raw.get("slots"), dict):
                return raw
    except Exception as exc:  # noqa: BLE001 - bozuk state taramayı durdurmasın
        logger.warning("Yeni domain alarm state okunamadı (%s): %s", yol, exc)
    return {"version": 1, "slots": {}}


def _save_state(state: Mapping[str, Any], state_path: str | None = None) -> None:
    yol = _state_yolu(state_path)
    try:
        os.makedirs(os.path.dirname(yol) or ".", exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(dict(state), f, ensure_ascii=False, indent=2)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Yeni domain alarm state yazılamadı (%s): %s", yol, exc)


def _zaten_gonderildi(slot: Mapping[str, Any] | None, cand: DomainAlarmCandidate) -> bool:
    if not slot:
        return False
    if str(slot.get("last_bar_open") or "") == cand.bar_open:
        return True
    try:
        son_index = int(slot["last_bar_index"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    cooldown = _cfg_int("YENI_DOMAIN_ALARM_COOLDOWN_BAR", 6)
    return (cand.bar_index - son_index) < cooldown


def _isaretle(slots: dict[str, Any], cand: DomainAlarmCandidate) -> None:
    slots[cand.dedup_key] = {
        "last_bar_open": cand.bar_open,
        "last_bar_close": cand.bar_close,
        "last_bar_index": cand.bar_index,
        "reason_signature": cand.reason_signature,
        "volume_tier": cand.volume_tier,
        "data_quality": cand.data_quality,
    }


# --- Kart metinleri ----------------------------------------------------------

def format_domain_alarm_card(cand: DomainAlarmCandidate) -> str:
    satirlar = [
        f"{YENI_KART_ISARETI} · DOMAİN TETİKLEME",
        f"{cand.symbol} · {_tf_etiket(cand.timeframe)} · {cand.bar_label}",
        "Sebep: " + " · ".join(cand.reasons[:4]),
        f"Stabil: {cand.relation} · {_tr_sayi(cand.dist_atr, 2)} ATR",
    ]
    if len(cand.reasons) > 4:
        satirlar.append(f"… +{len(cand.reasons) - 4} sebep daha")
    for satir in cand.card_lines[:2]:
        satirlar.append(satir)
    satirlar.append("Koşul: −3 ATR alt sınırı geçti · üst sınır yok")
    if cand.volume_tier:
        satirlar.append(
            f"Hacim: {cand.volume_tier} · RVOL {_tr_sayi(cand.volume_rvol, 1)}× "
            f"({cand.volume_source})"
        )
    if cand.data_quality == "VERI_SUPHE":
        satirlar.append("⚠️ Hacim uç değeri: veri kalitesi kontrolü gerekli")
    elif cand.data_quality not in {"OK", ""}:
        satirlar.append(f"Veri kalitesi: {cand.data_quality}")
    satirlar.append("Yatırım tavsiyesi değildir.")
    return metni_sigdir("\n".join(satirlar), guvenlik=1.0)


def format_domain_alarm_summary_card(cands: Sequence[DomainAlarmCandidate]) -> str:
    adet = len(cands)
    satirlar = [
        f"{YENI_KART_ISARETI} · DOMAİN TOPLU ÖZET (+{adet})",
        "Aynı taramada −3 ATR alt sınırını geçen diğer adaylar:",
        "",
    ]
    for c in cands[:10]:
        satirlar.append(
            f"• {c.symbol} {_tf_etiket(c.timeframe)}: {c.relation} "
            f"({_tr_sayi(c.dist_atr, 1)} ATR) · {' · '.join(c.reasons[:2])}"
        )
    if adet > 10:
        satirlar.append(f"• … ve {adet - 10} aday daha")
    satirlar.extend(["", "Detay: /grafik <SEMBOL> · /stabil"])
    return metni_sigdir("\n".join(satirlar), guvenlik=1.0)


def _deliver_message(notifier: Any, text: str) -> bool:
    """Ana DM + public hedefe aynı yeni kartı gönder."""
    dm_on = bool(getattr(config, "YENI_DOMAIN_ALARM_DM", True))
    pub_on = bool(getattr(config, "YENI_DOMAIN_ALARM_PUBLIC", True))
    any_ok = False

    if dm_on and notifier is not None:
        send_text = getattr(notifier, "send_text", None)
        if callable(send_text):
            try:
                res = send_text(text)
                ok = res[0] if isinstance(res, tuple) else bool(res)
                any_ok = any_ok or bool(ok)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Yeni domain DM gönderim hatası: %s", exc)

    if pub_on and notifier is not None:
        public_acik = getattr(notifier, "public_enabled", None)
        send_pub = getattr(notifier, "send_to_public", None)
        if public_acik is not False and callable(send_pub):
            try:
                ok_pub = bool(send_pub(text))
            except Exception as exc:  # noqa: BLE001
                ok_pub = False
                logger.warning("Yeni domain public gönderim hatası: %s", exc)
            any_ok = any_ok or ok_pub

    return any_ok


def dispatch_domain_alarm_candidates(
    candidates: Sequence[DomainAlarmCandidate],
    notifier: Any,
    *,
    state_path: str | None = None,
) -> dict[str, int]:
    """Adayları tekilleştir, burst kuralıyla gönder, state'e işaretle."""
    ozet = {"aday": len(candidates), "tekil_gonderilen": 0,
            "toplu_ozet": 0, "filtrelendi": 0}
    if not candidates or not bool(getattr(config, "YENI_DOMAIN_ALARM", True)):
        return ozet

    # Aynı sembol/TF/bar için en yüksek puanlı tek aday.
    en_iyi: dict[str, DomainAlarmCandidate] = {}
    for cand in candidates:
        onceki = en_iyi.get(cand.dedup_key)
        if onceki is None or cand.rank_score > onceki.rank_score:
            en_iyi[cand.dedup_key] = cand
    sirali = sorted(en_iyi.values(), key=lambda c: (-c.rank_score, c.symbol, c.timeframe))

    state = _load_state(state_path)
    slots = state.setdefault("slots", {})
    degisti = False

    ust_sinir = _cfg_int("YENI_DOMAIN_ALARM_TEKIL_UST_SINIR", 3)
    if len(sirali) <= ust_sinir:
        tekil_liste = list(sirali)
        toplu_liste: list[DomainAlarmCandidate] = []
    else:
        tekil_liste = list(sirali[:2])
        toplu_liste = list(sirali[2:])

    gonderilen: list[DomainAlarmCandidate] = []
    for cand in tekil_liste:
        if _zaten_gonderildi(slots.get(cand.dedup_key), cand):
            ozet["filtrelendi"] += 1
            continue
        if _deliver_message(notifier, format_domain_alarm_card(cand)):
            ozet["tekil_gonderilen"] += 1
            gonderilen.append(cand)

    if toplu_liste:
        yeni_toplu = [
            c for c in toplu_liste
            if not _zaten_gonderildi(slots.get(c.dedup_key), c)
        ]
        ozet["filtrelendi"] += len(toplu_liste) - len(yeni_toplu)
        if yeni_toplu and _deliver_message(
            notifier, format_domain_alarm_summary_card(yeni_toplu)
        ):
            ozet["toplu_ozet"] = 1
            gonderilen.extend(yeni_toplu)

    for cand in gonderilen:
        _isaretle(slots, cand)
        degisti = True
    if degisti:
        _save_state(state, state_path)
    return ozet


__all__ = [
    "DomainAlarmCandidate",
    "YENI_KART_ISARETI",
    "dispatch_domain_alarm_candidates",
    "evaluate_domain_alarm_candidates",
    "format_domain_alarm_card",
    "format_domain_alarm_summary_card",
]
