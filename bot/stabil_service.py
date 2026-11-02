"""Stabil canlı 4S güçlü geri alım alarm yöneticisi ve `/stabil` komutu servisi."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import math
import os
from typing import Any, Mapping, Sequence

import pandas as pd

import config
from data import (
    bar_kapandi_mi,
    gunluk_bolunme_normalize_et,
    mum_kapanis_ani,
    resample_all_timeframes,
    tamamlanmis_mumlar,
)
from domain_engines.runner import run_stabil_domain, run_stabil_symbol_bundle
from domain_engines.stabil import (
    LiveStabilSummary,
    StabilBarBehavior,
    format_stabil_card_lines,
    summarize_symbol_for_command,
)
from telegram_measure import metni_sigdir

logger = logging.getLogger(__name__)


def _tr_sayi(deger: float | None, ondalik: int = 2) -> str:
    if deger is None or not math.isfinite(float(deger)):
        return "—"
    v = float(deger)
    if abs(v) >= 1000 and ondalik == 2:
        ondalik = 1
    kalip = f"{v:,.{ondalik}f}"
    return kalip.replace(",", "_").replace(".", ",").replace("_", ".")


@dataclass(frozen=True, slots=True)
class StabilAlarmCandidate:
    symbol: str
    bar_open_ts: str
    bar_close_ts: str
    bar_label: str
    close_price: float
    support_level: float
    behavior: StabilBarBehavior
    card_lines: tuple[str, ...]


def _state_file_path() -> str:
    from state.paths import stabil_alarm_state_yolu

    data_dir = str(getattr(config, "DATA_DIR", "") or "").strip() or None
    return stabil_alarm_state_yolu(data_dir)


def _load_alarm_state(path: str | None = None) -> dict[str, Any]:
    hedef = path or _state_file_path()
    try:
        if os.path.exists(hedef):
            with open(hedef, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict) and isinstance(raw.get("symbols"), dict):
                return raw
    except Exception as exc:
        logger.warning("Stabil alarm durumu okunamadı (%s): %s", hedef, exc)
    return {"version": 1, "symbols": {}}


def _save_alarm_state(state: Mapping[str, Any], path: str | None = None) -> None:
    hedef = path or _state_file_path()
    try:
        os.makedirs(os.path.dirname(hedef) or ".", exist_ok=True)
        tmp = f"{hedef}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dict(state), f, ensure_ascii=False, indent=2)
        os.replace(tmp, hedef)
    except Exception as exc:
        logger.warning("Stabil alarm durumu yazılamadı (%s): %s", hedef, exc)


def _bars_since_last_sent(df_4h_closed: pd.DataFrame, last_bar_open_iso: str | None) -> int | None:
    if not last_bar_open_iso or df_4h_closed is None or df_4h_closed.empty:
        return None
    try:
        target = pd.Timestamp(last_bar_open_iso)
        idx_ts = pd.DatetimeIndex(df_4h_closed.index)
        if target.tzinfo is not None and idx_ts.tz is None:
            target = target.tz_localize(None)
        elif target.tzinfo is None and idx_ts.tz is not None:
            target = target.tz_localize(idx_ts.tz)
        elif target.tzinfo is not None and idx_ts.tz is not None:
            target = target.tz_convert(idx_ts.tz)
        pos = int(idx_ts.searchsorted(target, side="left"))
        if pos < len(idx_ts) and idx_ts[pos] == target:
            return (len(idx_ts) - 1) - pos
        if target < idx_ts[0]:
            return len(idx_ts)
        if target >= idx_ts[-1]:
            return 0
        return (len(idx_ts) - 1) - max(0, pos - 1)
    except Exception:
        return None


def evaluate_stabil_4h_candidate(
    stock: str,
    all_tfs: Mapping[str, pd.DataFrame],
    simdiki_zaman: datetime,
    *,
    domain_results_by_stock: Mapping[str, Any] | None = None,
    bar_metni_fn: Any = None,
    state_path: str | None = None,
) -> StabilAlarmCandidate | None:
    """Evaluate closed 4H bar for strong Stabil reclaim signal with causal dedup & cooldown."""
    if not bool(getattr(config, "STABIL_GERI_ALIM_ALARM", True)):
        return None
    if config.sembol_turu(stock) == "makro":
        return None

    raw_4h = all_tfs.get("4h")
    raw_1d = all_tfs.get("1d")
    if raw_4h is None or raw_1d is None or len(raw_4h) < 20 or len(raw_1d) < 25:
        return None

    df_4h = tamamlanmis_mumlar(raw_4h, "4h", now=simdiki_zaman)
    df_1d = tamamlanmis_mumlar(raw_1d, "1d", now=simdiki_zaman)
    if df_4h is None or df_1d is None or len(df_4h) < 15 or len(df_1d) < 20:
        return None

    last_open_ts = df_4h.index[-1]
    if not bar_kapandi_mi(last_open_ts, "4h", now=simdiki_zaman):
        return None

    son_kapanis = mum_kapanis_ani(last_open_ts, "4h")
    if son_kapanis is None:
        return None
    yas_dk = (simdiki_zaman - son_kapanis).total_seconds() / 60.0
    taze_sinir = float(getattr(config, "STABIL_ALARM_TAZE_DK", 390))
    if yas_dk < -1.0 or yas_dk > taze_sinir:
        # Eski cache veya ertesi gün yeniden başlatmalarda geçmiş 4S mumu tekrar bildirilmez
        return None

    bar_open_iso = pd.Timestamp(last_open_ts).isoformat()
    state = _load_alarm_state(state_path)
    sym_state = (state.get("symbols") or {}).get(stock) or {}
    last_sent_open = sym_state.get("last_bar_open")
    if last_sent_open == bar_open_iso:
        return None

    cooldown_bars = int(getattr(config, "STABIL_ALARM_COOLDOWN_BAR", 6))
    bars_elapsed = _bars_since_last_sent(df_4h, last_sent_open)
    if bars_elapsed is not None and bars_elapsed < cooldown_bars:
        return None

    # Reuse domain result if already computed in this scan turn; otherwise run isolated Stabil 4H
    stabil_res = None
    if domain_results_by_stock and stock in domain_results_by_stock:
        tf_map = domain_results_by_stock.get(stock) or {}
        if isinstance(tf_map, Mapping) and isinstance(tf_map.get("4h"), Mapping):
            stabil_res = tf_map["4h"].get("stabil")

    if stabil_res is None:
        stabil_res = run_stabil_domain(
            stock,
            "4h",
            df_4h,
            daily_frame=df_1d,
            h4_frame=df_4h,
            as_of_close=simdiki_zaman,
            isolated=True,
        )

    if stabil_res is None or getattr(stabil_res, "error", None):
        return None

    out = getattr(stabil_res, "result", None)
    bhv: StabilBarBehavior | None = getattr(out, "latest_behavior", None) if out is not None else None
    if bhv is None and isinstance(getattr(stabil_res, "details", None), Mapping):
        bhv = stabil_res.details.get("latest_behavior")

    if bhv is None or bhv.reclaim_kind not in {"close_reclaim", "intrabar_sweep_reclaim"}:
        return None
    if bhv.support_level is None or bhv.close_price is None:
        return None

    card_lines = tuple(
        format_stabil_card_lines(
            price=bhv.close_price,
            support_level=bhv.support_level,
            behavior=bhv,
        )
    )
    bar_label = (
        bar_metni_fn("4h", last_open_ts, son_kapanis)
        if callable(bar_metni_fn)
        else son_kapanis.strftime("%d.%m %H:%M")
    )
    return StabilAlarmCandidate(
        symbol=stock,
        bar_open_ts=bar_open_iso,
        bar_close_ts=son_kapanis.isoformat(),
        bar_label=str(bar_label or ""),
        close_price=float(bhv.close_price),
        support_level=float(bhv.support_level),
        behavior=bhv,
        card_lines=card_lines,
    )


def format_stabil_reclaim_alert_card(cand: StabilAlarmCandidate) -> str:
    """283px mobile-safe standalone 4H Stabil strong reclaim alert card."""
    bhv = cand.behavior
    baslik_tur = (
        "STABİL GÜÇLÜ GERİ ALIM"
        if bhv.reclaim_kind == "close_reclaim"
        else "STABİL SİLKELEME DÖNÜŞÜ"
    )
    satirlar = [
        f"🟢 {cand.symbol} · 4s — {baslik_tur}",
        f"Kapanış {_tr_sayi(cand.close_price)} · {cand.bar_label}".strip(" ·"),
        "",
    ]
    for cl in cand.card_lines[:2]:
        satirlar.append(cl)

    zemin_parcalar: list[str] = []
    if bhv.unchanged_days >= 20:
        zemin_parcalar.append(f"{bhv.unchanged_days}g yatay baz")
    elif bhv.unchanged_days >= 5:
        zemin_parcalar.append(f"{bhv.unchanged_days}g sabit çizgi")
    if bhv.touch_count >= 1:
        zemin_parcalar.append(f"{bhv.touch_count}. test")
    if bhv.vol_ratio is not None and bhv.vol_ratio >= 1.0:
        zemin_parcalar.append(f"hacim x{_tr_sayi(bhv.vol_ratio, 1)}")
    if zemin_parcalar:
        satirlar.append("Zemin: " + " · ".join(zemin_parcalar))

    satirlar.extend(
        [
            "",
            "📊 Arşiv karşılığı (canlı evren 4s):",
            "• Sonraki mum destek üstü: %91,5",
            "• 2 günde ortanca fark: +0,26 ATR",
        ]
    )
    return metni_sigdir("\n".join(satirlar), guvenlik=1.0)


def format_stabil_burst_summary_card(extra_candidates: Sequence[StabilAlarmCandidate]) -> str:
    """Consolidated summary card when >3 symbols reclaim on the same 4H scan."""
    adet = len(extra_candidates)
    zaman = extra_candidates[0].bar_label if extra_candidates else ""
    satirlar = [
        f"🟢 STABİL TOPLU DÖNÜŞ ÖZETİ (+{adet} sembol)",
    ]
    if zaman:
        satirlar.append(f"Kapanan mum: {zaman}")
    satirlar.append("Aynı 4s kapanışında destek üstüne güçlü dönen diğer semboller:")
    satirlar.append("")
    for c in extra_candidates[:10]:
        pct = c.behavior.pct_vs_support or 0.0
        pct_s = f"+%{_tr_sayi(abs(pct), 1)}"
        tur = "geri alım" if c.behavior.reclaim_kind == "close_reclaim" else "silkeleme dönüşü"
        satirlar.append(
            f"• {c.symbol}: {_tr_sayi(c.close_price)} (destek {_tr_sayi(c.support_level)}, {pct_s}) · {tur}"
        )
    if adet > 10:
        satirlar.append(f"• … ve {adet - 10} sembol daha (/stabil ile inceleyin)")
    satirlar.append("")
    satirlar.append("Detaylı liste için: /stabil")
    return metni_sigdir("\n".join(satirlar), guvenlik=1.0)


def _deliver_stabil_message(notifier: Any, text: str) -> bool:
    dm_on = bool(getattr(config, "STABIL_ALARM_DM", True))
    pub_on = bool(getattr(config, "STABIL_ALARM_PUBLIC", True))
    any_ok = False

    if dm_on and notifier is not None:
        send_text = getattr(notifier, "send_text", None)
        if callable(send_text):
            try:
                res = send_text(text)
                ok = res[0] if isinstance(res, tuple) else bool(res)
                any_ok = any_ok or bool(ok)
            except Exception as exc:
                logger.warning("Stabil DM gönderim hatası: %s", exc)

    if pub_on and notifier is not None:
        dm_aktif_ama_public_kapali = (
            bool(getattr(notifier, "enabled", False))
            and not bool(getattr(notifier, "public_enabled", True))
        )
        send_pub = getattr(notifier, "send_to_public", None)
        if callable(send_pub) and not dm_aktif_ama_public_kapali:
            try:
                ok_pub = bool(send_pub(text))
                any_ok = any_ok or ok_pub
            except Exception as exc:
                logger.warning("Stabil public gönderim hatası: %s", exc)

    return any_ok


def dispatch_stabil_scan_candidates(
    candidates: Sequence[StabilAlarmCandidate],
    notifier: Any,
    *,
    state_path: str | None = None,
) -> dict[str, int]:
    """Send standalone 4H Stabil alerts applying burst rule (>3 -> top 2 cards + 1 summary)."""
    ozet = {"aday": len(candidates), "tekil_gonderilen": 0, "toplu_ozet": 0}
    if not candidates:
        return ozet

    sirali = sorted(
        candidates,
        key=lambda c: (-float(c.behavior.rank_score), c.symbol),
    )
    tekil_ust_sinir = int(getattr(config, "STABIL_ALARM_TEKIL_UST_SINIR", 3))
    if len(sirali) <= tekil_ust_sinir:
        tekil_liste = list(sirali)
        toplu_liste: list[StabilAlarmCandidate] = []
    else:
        tekil_liste = list(sirali[:2])
        toplu_liste = list(sirali[2:])

    state = _load_alarm_state(state_path)
    symbols_map = state.setdefault("symbols", {})
    degisti = False

    for cand in tekil_liste:
        metin = format_stabil_reclaim_alert_card(cand)
        if _deliver_stabil_message(notifier, metin):
            ozet["tekil_gonderilen"] += 1
            symbols_map[cand.symbol] = {
                "last_bar_open": cand.bar_open_ts,
                "last_bar_close": cand.bar_close_ts,
                "kind": cand.behavior.reclaim_kind,
            }
            degisti = True

    if toplu_liste:
        ozet_metin = format_stabil_burst_summary_card(toplu_liste)
        if _deliver_stabil_message(notifier, ozet_metin):
            ozet["toplu_ozet"] = 1
            for cand in toplu_liste:
                symbols_map[cand.symbol] = {
                    "last_bar_open": cand.bar_open_ts,
                    "last_bar_close": cand.bar_close_ts,
                    "kind": cand.behavior.reclaim_kind,
                }
            degisti = True

    if degisti:
        _save_alarm_state(state, state_path)

    return ozet


def _symbol_frames_from_cache(
    stock: str,
    deque_manager: Any,
    now: datetime,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    if deque_manager is None:
        return None, None
    df_1h = deque_manager.to_dataframe(stock)
    df_gunluk = deque_manager.to_gunluk_dataframe(stock)
    df_4h = None
    if df_1h is not None and len(df_1h) >= 20:
        tfs = resample_all_timeframes(df_1h)
        df_4h = tamamlanmis_mumlar(tfs.get("4h"), "4h", now=now) if tfs.get("4h") is not None else None
        if df_gunluk is None or len(df_gunluk) < 20:
            df_gunluk = tfs.get("1d")
    df_1d = (
        tamamlanmis_mumlar(df_gunluk, "1d", now=now)
        if df_gunluk is not None and len(df_gunluk) >= 20
        else None
    )
    if df_1d is not None and len(df_1d) > 1:
        df_1d, _ = gunluk_bolunme_normalize_et(df_1d)
    return df_4h, df_1d


def format_single_symbol_stabil_report(
    stock: str,
    deque_manager: Any,
    now: datetime,
) -> str:
    if config.sembol_turu(stock) == "makro":
        return metni_sigdir(
            f"ℹ️ {stock} makro semboldür; BIST seans kapanış saatlerine dayalı "
            "günlük Stabil destek çizgisi bu enstrümanda çalıştırılmaz.",
            guvenlik=1.0,
        )

    df_4h, df_1d = _symbol_frames_from_cache(stock, deque_manager, now)
    if df_1d is None or len(df_1d) < 20:
        return metni_sigdir(
            f"⚠️ {stock} için önbellekte yeterli günlük veri henüz yok.\n"
            "Tam tarama tamamlandıktan sonra /stabil komutunu tekrar deneyin.",
            guvenlik=1.0,
        )

    frames: dict[str, pd.DataFrame] = {"1d": df_1d}
    if df_4h is not None and len(df_4h) >= 15:
        frames["4h"] = df_4h

    bundle = run_stabil_symbol_bundle(
        stock,
        frames,
        daily_frame=df_1d,
        h4_frame=df_4h,
        as_of_close=now,
        isolated=True,
    )
    out_4h = getattr(bundle.get("4h"), "result", None) if "4h" in bundle else None
    out_1d = getattr(bundle.get("1d"), "result", None) if "1d" in bundle else None
    aktif_out = out_4h if out_4h is not None else out_1d
    if aktif_out is None:
        return f"⚠️ {stock} için Stabil özeti üretilemedi."

    bhv: StabilBarBehavior | None = getattr(aktif_out, "latest_behavior", None)
    if bhv is None or bhv.support_level is None or bhv.close_price is None:
        return metni_sigdir(
            f"🧭 {stock} — STABİL DURUMU\n"
            "Günlük yapısal destek henüz ısınma aşamasında (onaylı destek oluşmadı).",
            guvenlik=1.0,
        )

    card_lines = format_stabil_card_lines(
        price=bhv.close_price,
        support_level=bhv.support_level,
        behavior=bhv,
    )
    summary = summarize_symbol_for_command(stock, out_4h or out_1d, out_1d)

    grup_etiket = {
        "guclu_cikis": "🟢 Güçlü çıkış / geri alım",
        "saglam_zemin": "🛡️ Sağlam yatay zemin",
        "sig_sarkma": "👀 Sığ sarkma (geri alım izlenir)",
        "zayif_dusus": "⚠️ Yorulan destek / düşüş baskısı",
        "notr": "➖ Destek üstü olağan seyir",
    }.get(summary.bucket if summary else "notr", "➖ Olağan seyir")

    tf_notu = "4s + 1g" if out_4h is not None else "1g"
    satirlar = [
        f"🧭 {stock} — STABİL ANALİZİ ({tf_notu})",
        f"Son kapanış: {_tr_sayi(bhv.close_price)}",
        "",
    ]
    for cl in card_lines:
        satirlar.append(f"• {cl}")
    satirlar.append(f"• Sınıf: {grup_etiket}")

    detaylar: list[str] = []
    if bhv.unchanged_days > 0:
        detaylar.append(f"zemin yaşı {bhv.unchanged_days} iş günü")
    if bhv.touch_count > 0:
        detaylar.append(f"{bhv.touch_count} bağımsız test")
    if bhv.dist_atr is not None:
        isaret = "+" if bhv.dist_atr >= 0 else ""
        detaylar.append(f"mesafe {isaret}{_tr_sayi(bhv.dist_atr, 2)} ATR")
    if detaylar:
        satirlar.append("• Ölçü: " + " · ".join(detaylar))

    if summary is not None and summary.detail_tr:
        satirlar.append("")
        satirlar.append(f"📌 Yorum: {summary.detail_tr}")

    return metni_sigdir("\n".join(satirlar), guvenlik=1.0)


def format_stabil_universe_command(
    arguman: str,
    *,
    deque_manager: Any,
    active_stocks: Sequence[str],
    now: datetime,
) -> str:
    """`/stabil` and `/stabil <SEMBOL>` handler implementation."""
    temiz = (arguman or "").strip().upper().replace(".IS", "")
    if temiz:
        parca = temiz.split()[0]
        known = {str(s).upper() for s in active_stocks}
        if parca not in known:
            return metni_sigdir(
                f"❓ '{parca}' izlenen sembol listesinde bulunamadı.\n"
                "Genel görünüm için /stabil · örnek tek sembol: /stabil THYAO",
                guvenlik=1.0,
            )
        return format_single_symbol_stabil_report(parca, deque_manager, now)

    if deque_manager is None:
        return "⏳ Önbellek henüz hazır değil; ilk taramadan sonra /stabil kullanılabilir."

    summaries: list[LiveStabilSummary] = []
    hazir_sembol = 0
    for sym in active_stocks:
        if config.sembol_turu(sym) == "makro":
            continue
        df_4h, df_1d = _symbol_frames_from_cache(sym, deque_manager, now)
        if df_1d is None or len(df_1d) < 20:
            continue
        hazir_sembol += 1
        frames: dict[str, pd.DataFrame] = {"1d": df_1d}
        if df_4h is not None and len(df_4h) >= 15:
            frames["4h"] = df_4h
        try:
            bundle = run_stabil_symbol_bundle(
                sym,
                frames,
                daily_frame=df_1d,
                h4_frame=df_4h,
                as_of_close=now,
                isolated=True,
            )
            out_4h = getattr(bundle.get("4h"), "result", None) if "4h" in bundle else None
            out_1d = getattr(bundle.get("1d"), "result", None) if "1d" in bundle else None
            ozet = summarize_symbol_for_command(sym, out_4h or out_1d, out_1d)
            if ozet is not None:
                summaries.append(ozet)
        except Exception as exc:
            logger.debug("/stabil %s hesaplanamadı: %s", sym, exc)

    if not summaries:
        return metni_sigdir(
            "🧭 STABİL PİYASA ÖZETİ\n\n"
            "Önbellekte henüz yeterli günlük/4s veri bulunamadı. "
            "İlk tarama tamamlandıktan sonra /stabil çalıştırılabilir.",
            guvenlik=1.0,
        )

    gruplar: dict[str, list[LiveStabilSummary]] = {
        "guclu_cikis": [],
        "saglam_zemin": [],
        "sig_sarkma": [],
        "zayif_dusus": [],
    }
    for s in summaries:
        if s.bucket in gruplar:
            gruplar[s.bucket].append(s)

    for k in gruplar:
        gruplar[k].sort(key=lambda item: (-item.priority, item.symbol))

    ust_sayisi = sum(1 for s in summaries if (s.pct_vs_support or 0.0) >= 0.0)
    alt_sayisi = len(summaries) - ust_sayisi

    satirlar = [
        f"🧭 STABİL ÖZETİ — {now.strftime('%d.%m.%Y %H:%M')}",
        f"İncelenen {len(summaries)} sembol: {ust_sayisi} destek üstü · {alt_sayisi} destek altı",
    ]

    bolum_tanimlari = (
        ("guclu_cikis", "🟢 GÜÇLÜ ÇIKIŞ / TAZE GERİ ALIM", 5),
        ("saglam_zemin", "🛡️ SAĞLAM YATAY ZEMİN (20g+ / 2. TEST)", 5),
        ("sig_sarkma", "👀 SIĞ SARKMA (GERİ ALIM İZLENENLER)", 4),
        ("zayif_dusus", "⚠️ YORULAN DESTEK / SAĞLAM DÜŞÜŞ", 5),
    )

    herhangi_bolum = False
    for anahtar, baslik, limit in bolum_tanimlari:
        liste = gruplar[anahtar]
        if not liste:
            continue
        herhangi_bolum = True
        satirlar.append("")
        satirlar.append(f"{baslik} ({len(liste)})")
        for item in liste[:limit]:
            satirlar.append(f"• {item.headline_tr}")
        if len(liste) > limit:
            kalan = ", ".join(x.symbol for x in liste[limit : limit + 5])
            ek = f" (+{len(liste) - limit - 5})" if len(liste) > limit + 5 else ""
            satirlar.append(f"  Diğer: {kalan}{ek}")

    if not herhangi_bolum:
        satirlar.append("")
        satirlar.append("Şu an uç bir geri alım veya kırılım kümesi yok; semboller olağan seyirde.")

    satirlar.append("")
    satirlar.append("Tek hisse detayı: /stabil THYAO")
    return metni_sigdir("\n".join(satirlar), guvenlik=1.0)
