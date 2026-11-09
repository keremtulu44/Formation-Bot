"""Stabil canlı 4S güçlü geri alım alarm yöneticisi ve `/stabil` komutu servisi."""

from __future__ import annotations

from dataclasses import dataclass, replace
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
    grafik_verisi_public: dict[str, Any] | None = None


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


def _stabil_public_grafik_verisi_uret(
    stock: str,
    df_4h: pd.DataFrame,
    df_1d: pd.DataFrame,
    simdiki_zaman: datetime,
    domain_results_by_stock: Mapping[str, Any] | None,
    stabil_res: Any,
    *,
    direnc_gunluk_ham: pd.DataFrame | None = None,
    direnc_saatlik_ham: pd.DataFrame | None = None,
    pattern_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Public Stabil kartı için mevcut ana-TF + üst-TF kare sözleşmesini üret.

    Grafik kill-switch'i mevcut global `TELEGRAM_GRAFIK` ayarına tabidir. Destek
    ve diğer domain sonuçları yeniden kullanılır; bağımsız direnç yalnız grafik
    için, ham kaynaklar doğrulanarak hesaplanır. Görsel hatası alarmı engellemez.
    """
    try:
        import grafik

        if not grafik.grafik_aktif_mi():
            return None

        per_tf = (domain_results_by_stock or {}).get(stock, {})
        sonuclar = dict(per_tf) if isinstance(per_tf, Mapping) else {}
        ana_sonuclar = sonuclar.get("4h")
        ana_sonuclar = dict(ana_sonuclar) if isinstance(ana_sonuclar, Mapping) else {}
        # `stabil_res` aday değerlendirmesinde zaten kullanılmış aynı 4s çıktıdır.
        # İzole hesap yolunda da ana kare Stabil katmanını çizebilsin.
        ana_sonuclar["stabil"] = stabil_res
        sonuclar["4h"] = ana_sonuclar
        try:
            from domain_engines.stabil.chart_bridge import add_chart_resistance

            sonuclar = add_chart_resistance(
                stock, {"4h": df_4h, "1d": df_1d}, sonuclar,
                daily_frame=direnc_gunluk_ham, hourly_frame=direnc_saatlik_ham,
                as_of_close=simdiki_zaman,
            )
        except Exception as exc:  # noqa: BLE001 - eski destek alarm karesi korunur
            logger.warning("Stabil direnç grafiği atlandı (%s): %s", stock, type(exc).__name__)

        chart_pattern = None
        if isinstance(pattern_snapshot, Mapping):
            try:
                matches = pd.Timestamp(pattern_snapshot.get("bar_time")) == pd.Timestamp(df_4h.index[-1])
            except (TypeError, ValueError):
                matches = False
            if matches:
                chart_pattern = {
                    "state": pattern_snapshot.get("state"),
                    "pattern_name": pattern_snapshot.get("pattern_name"),
                    "upper_now": pattern_snapshot.get("upper"),
                    "lower_now": pattern_snapshot.get("lower"),
                }
        veri = grafik.kare_listesi(
            chart_pattern,
            "4h",
            df_4h,
            sonuclar=sonuclar,
            ek_cerceveler={"1d": df_1d},
            sembol=str(stock).upper(),
            zaman_damgasi=df_4h.index[-1],
            adet=2,
            simdi=simdiki_zaman,
        )
        if not isinstance(veri, dict):
            return None
        uretilenler = list(veri.get("goruntular") or [])
        ana_kare = next(
            (k for k in uretilenler
             if isinstance(k, Mapping) and str(k.get("tf") or "").lower() == "4h"),
            None,
        )
        if ana_kare is None:
            logger.warning("Stabil ana 4s grafiği üretilemedi (%s); görsel eklenmedi", stock)
            return None
        ust_kare = next(
            (k for k in uretilenler
             if isinstance(k, Mapping) and str(k.get("tf") or "").lower() == "1d"),
            None,
        )
        goruntular = [dict(ana_kare)]
        if ust_kare is not None:
            ust_kare = dict(ust_kare)
            # Public albüm caption'ı ikinci kareyi doğru biçimde "üst TF" yazar.
            ust_kare["rol"] = "ust"
            goruntular.append(ust_kare)
        else:
            logger.warning("Stabil public grafik çifti eksik (%s 4s + 1g): 1/2 kare", stock)
        veri["goruntular"] = goruntular
        return veri
    except Exception as exc:  # noqa: BLE001 - grafik metin alarmını engellemesin
        logger.warning("Stabil public grafikleri hazırlanamadı (%s): %s", stock, exc)
        return None


def _update_sent_stabil_status(state, symbol, frame, market_result):
    """Record later opposite BOS without changing the original delivered alert."""
    from domain_engines.stabil.structure_context import events_for_bars, marker_state
    item = (state.get("symbols") or {}).get(symbol) or {}
    if not item.get("last_bar_open") or item.get("signal_status") == "invalidated_by_opposite_bos":
        return False
    try:
        origin = pd.Timestamp(item["last_bar_open"])
        matches = [i for i, time in enumerate(frame.index) if pd.Timestamp(time) == origin]
    except (TypeError, ValueError):
        return False
    if len(matches) != 1:
        return False
    bar = matches[0]
    events = events_for_bars(market_result, frame.index)
    # Invalidation is a separate post-delivery fact even if another event
    # would classify the original marker as opposed in hindsight.
    post = [e for e in events if bar < e[0] <= min(bar + 3, len(frame) - 1)]
    if marker_state(bar, "UP", "4h", post, len(frame) - 1) != "invalidated_by_opposite_bos":
        return False
    invalidation_bar = next(i for i, kind, direction in post
                            if kind == "BOS" and direction == "DOWN"
                            and {e[2] for e in post if e[0] == i and e[1] == "BOS"} == {"DOWN"})
    item["signal_status"] = "invalidated_by_opposite_bos"
    item["invalidated_bar_open"] = pd.Timestamp(frame.index[invalidation_bar]).isoformat()
    return True


def evaluate_stabil_4h_candidate(
    stock: str,
    all_tfs: Mapping[str, pd.DataFrame],
    simdiki_zaman: datetime,
    *,
    domain_results_by_stock: Mapping[str, Any] | None = None,
    bar_metni_fn: Any = None,
    state_path: str | None = None,
    direnc_gunluk_ham: pd.DataFrame | None = None,
    pattern_snapshot: Any = None,
    notifier: Any = None,
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
    cached_tf = (domain_results_by_stock or {}).get(stock, {})
    cached_tf = cached_tf.get("4h", {}) if isinstance(cached_tf, Mapping) else {}
    cached_market = cached_tf.get("market_structure") if isinstance(cached_tf, Mapping) else None
    if _update_sent_stabil_status(state, stock, df_4h, cached_market):
        sym_state["queue_cancel_pending"] = True
        _save_alarm_state(state, state_path)
    cancel = getattr(notifier, "stabil_bekleyen_iptal", None)
    if sym_state.get("queue_cancel_pending") and callable(cancel):
        from public_aux_outbox import auxiliary_event_id
        event_id = auxiliary_event_id("stabil", [(stock, sym_state.get("last_bar_open"))])
        try:
            cancel(event_id)
            sym_state.pop("queue_cancel_pending", None)
            _save_alarm_state(state, state_path)
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("Stabil bekleyen alarm iptali kaydedilemedi (%s): %s", stock, exc)
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

    if bhv is None or bhv.reclaim_kind not in {"multi_bar_recovery", "intrabar_sweep_reclaim"}:
        return None
    # Apply the same optional causal structure gate as the chart. Missing or
    # unaligned Market Structure data are not evidence of a contrary event.
    from domain_engines.stabil.structure_context import barrier_reason, events_for_bars, marker_state
    tf_map = (domain_results_by_stock or {}).get(stock, {})
    per_tf = tf_map.get("4h", {}) if isinstance(tf_map, Mapping) else {}
    ms = per_tf.get("market_structure") if isinstance(per_tf, Mapping) else None
    events = events_for_bars(ms, df_4h.index)
    if marker_state(len(df_4h) - 1, "UP", "4h", events, len(df_4h) - 1) == "opposite_structure":
        return None
    if bhv.support_level is None or bhv.close_price is None:
        return None

    # Same-bar opposing boundaries, only when their source is available.
    # A missing pattern/resistance is unknown, not an invented obstacle.
    from domain_engines.stabil.signals import _causal_atr14
    import numpy as np
    atr = _causal_atr14(df_4h["high"].to_numpy(dtype=float),
                        df_4h["low"].to_numpy(dtype=float),
                        df_4h["close"].to_numpy(dtype=float), period=14)[-1]
    barriers = []
    if isinstance(pattern_snapshot, Mapping):
        try:
            pattern_time = pd.Timestamp(pattern_snapshot.get("bar_time"))
            same_bar = not pd.isna(pattern_time) and pattern_time == pd.Timestamp(last_open_ts)
        except (TypeError, ValueError):
            same_bar = False
        if same_bar and pattern_snapshot.get("state") not in {"FORMASYON_GECERSIZ", "Yok", "ST_NONE"}:
            barriers.append(("formasyon_siniri", pattern_snapshot.get("upper")))
    resistance = per_tf.get("stabil_direnc") if isinstance(per_tf, Mapping) else None
    if resistance is None and all_tfs.get("1h") is not None and direnc_gunluk_ham is not None:
        from domain_engines.stabil.chart_bridge import resistance_for_chart
        resistance = resistance_for_chart(stock, "4h", df_4h, daily_frame=direnc_gunluk_ham,
                                          hourly_frame=all_tfs.get("1h"), as_of_close=simdiki_zaman)
    if resistance is not None:
        from grafik.tarama import _stabil_direnc_verisi
        layer = _stabil_direnc_verisi({"stabil_direnc": resistance}, "4h", 0, len(df_4h), list(df_4h.index))
        if layer and layer.get("hazir") and layer.get("renkler") and layer["renkler"][-1] == "alt":
            barriers.insert(0, ("stabil_koridoru", layer["seviyeler"][-1]))
    if barrier_reason(bhv.close_price, atr, "UP", barriers):
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
    grafik_verisi_public = None
    if bool(getattr(config, "STABIL_ALARM_PUBLIC", True)):
        grafik_verisi_public = _stabil_public_grafik_verisi_uret(
            stock,
            df_4h,
            df_1d,
            simdiki_zaman,
            domain_results_by_stock,
            stabil_res,
            direnc_gunluk_ham=direnc_gunluk_ham,
            direnc_saatlik_ham=all_tfs.get("1h"),
            pattern_snapshot=pattern_snapshot,
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
        grafik_verisi_public=grafik_verisi_public,
    )


def format_stabil_reclaim_alert_card(cand: StabilAlarmCandidate) -> str:
    """283px mobile-safe standalone 4H Stabil strong reclaim alert card."""
    bhv = cand.behavior
    baslik_tur = (
        "STABİL ÇOK MUMLU TOPARLANMA"
        if bhv.reclaim_kind == "multi_bar_recovery"
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

    # Historical combined close-reclaim/sweep statistics do not describe the
    # new multi-bar rule or the sweep-only subset; do not present them here.
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
    satirlar.append("Aynı 4s kapanışındaki diğer Stabil dönüşleri:")
    satirlar.append("")
    for c in extra_candidates[:10]:
        pct = c.behavior.pct_vs_support or 0.0
        pct_s = f"{'+' if pct >= 0 else '-'}%{_tr_sayi(abs(pct), 1)}"
        tur = "geri alım" if c.behavior.reclaim_kind == "multi_bar_recovery" else "silkeleme dönüşü"
        satirlar.append(
            f"• {c.symbol}: {_tr_sayi(c.close_price)} (destek {_tr_sayi(c.support_level)}, {pct_s}) · {tur}"
        )
    if adet > 10:
        satirlar.append(f"• … ve {adet - 10} sembol daha (/stabil ile inceleyin)")
    satirlar.append("")
    satirlar.append("Detaylı liste için: /stabil")
    return metni_sigdir("\n".join(satirlar), guvenlik=1.0)


def _deliver_stabil_message_result(notifier: Any, text: str, *, public_event_id=None,
                                   public_identity=None, public_graphics=None) -> dict[str, bool]:
    """DM sonucu ile public'in teslim/kuyruk sonucunu ayrı tut."""
    dm_on = bool(getattr(config, "STABIL_ALARM_DM", True))
    pub_on = bool(getattr(config, "STABIL_ALARM_PUBLIC", True))
    dm_ok = dm_accepted = pub_ok = pub_accepted = False
    public_managed = False
    dm_required = dm_on and notifier is not None and getattr(notifier, "enabled", True) is not False
    pub_required = pub_on and notifier is not None and getattr(notifier, "public_enabled", True) is not False

    if dm_required:
        send_text = getattr(notifier, "send_text", None)
        queue_dm = getattr(notifier, "dm_ozel_gonder", None)
        if public_event_id and callable(queue_dm):
            try:
                dm_accepted, dm_ok = queue_dm(public_event_id, text, identity=public_identity)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Stabil DM kuyruğu başarısız: %s", type(exc).__name__)
        elif callable(send_text):
            try:
                res = send_text(text)
                dm_ok = bool(res[0] if isinstance(res, tuple) else res)
                dm_accepted = dm_ok
            except Exception as exc:  # noqa: BLE001
                logger.warning("Stabil DM gönderim hatası: %s", type(exc).__name__)

    if pub_on and notifier is not None:
        dm_aktif_ama_public_kapali = (
            bool(getattr(notifier, "enabled", False))
            and not bool(getattr(notifier, "public_enabled", True))
        )
        send_pub = getattr(notifier, "send_to_public", None)
        queue_pub = getattr(notifier, "public_ozel_gonder", None)
        if not dm_aktif_ama_public_kapali and public_event_id and callable(queue_pub):
            public_managed = True
            try:
                pub_accepted, pub_ok = queue_pub(
                    public_event_id, text, identity=public_identity, graphics=public_graphics)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Stabil public kuyruğu başarısız: %s", type(exc).__name__)
        elif callable(send_pub) and not dm_aktif_ama_public_kapali:
            try:
                pub_ok = bool(send_pub(text))
                pub_accepted = pub_ok
            except Exception as exc:  # noqa: BLE001
                logger.warning("Stabil public gönderim hatası: %s", type(exc).__name__)
        if dm_ok and dm_aktif_ama_public_kapali:
            logger.warning("Stabil DM gitti, public hedef kapalı; kanal kopyası gönderilmedi")
        elif dm_ok and not (pub_ok or pub_accepted):
            logger.warning("Stabil DM gitti ancak public kopyası saklanamadı/gönderilmedi")

    recorded = ((not dm_required or dm_ok or dm_accepted)
                and (not pub_required or pub_ok or pub_accepted)
                and (dm_ok or dm_accepted or pub_ok or pub_accepted))
    return {"dm": bool(dm_ok), "public": bool(pub_ok), "any": bool(dm_ok or pub_ok),
            "recorded": bool(recorded), "public_managed": public_managed}


def _deliver_stabil_message_channels(notifier: Any, text: str) -> tuple[bool, bool]:
    sonuc = _deliver_stabil_message_result(notifier, text)
    return sonuc["dm"], sonuc["public"]


def _deliver_stabil_message(notifier: Any, text: str) -> bool:
    """Geriye uyumlu kolaylık: DM veya public metninden biri gittiyse True."""
    dm_ok, pub_ok = _deliver_stabil_message_channels(notifier, text)
    return dm_ok or pub_ok


def _stabil_public_identity(cand: StabilAlarmCandidate) -> dict[str, str]:
    tur = ("STABİL ÇOK MUMLU TOPARLANMA" if cand.behavior.reclaim_kind == "multi_bar_recovery"
           else "STABİL SİLKELEME DÖNÜŞÜ")
    return {"stock_name": cand.symbol, "timeframe": "4h", "state": "STABIL_GERI_ALIM",
            "pattern_name": tur, "formation_id": cand.bar_open_ts}


def _deliver_stabil_public_graphic(
    notifier: Any,
    cand: StabilAlarmCandidate,
    *,
    public_text_sent: bool,
) -> int:
    """Metni başarılı public tesliminden sonra kareleri mevcut albüm yoluna bağla."""
    veri = cand.grafik_verisi_public
    if notifier is None or not public_text_sent or not isinstance(veri, dict):
        return 0
    if not (veri.get("goruntular") or []):
        return 0
    bagla = getattr(notifier, "public_grafik_bagla", None)
    if not callable(bagla):
        return 0

    try:
        return int(bagla(_stabil_public_identity(cand), veri) or 0)
    except Exception as exc:  # noqa: BLE001 - grafik metin alarmını engellemesin
        logger.warning("Stabil public grafiği gönderilemedi (%s): %s", cand.symbol, exc)
        return 0


def dispatch_stabil_scan_candidates(
    candidates: Sequence[StabilAlarmCandidate],
    notifier: Any,
    *,
    state_path: str | None = None,
) -> dict[str, int]:
    """Send standalone 4H Stabil alerts applying burst rule (>3 -> top 2 cards + 1 summary)."""
    # Legacy candidates may be deserialized or passed directly, bypassing
    # evaluation. Never dispatch the retired support close_reclaim path.
    candidates = [c for c in candidates if c.behavior.reclaim_kind in
                  {"intrabar_sweep_reclaim", "multi_bar_recovery"}]
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
    from public_aux_outbox import auxiliary_event_id

    for cand in tekil_liste:
        metin = format_stabil_reclaim_alert_card(cand)
        sonuc = _deliver_stabil_message_result(
            notifier, metin,
            public_event_id=auxiliary_event_id("stabil", [(cand.symbol, cand.bar_open_ts)]),
            public_identity=_stabil_public_identity(cand),
            public_graphics=cand.grafik_verisi_public,
        )
        if sonuc["public"] and not sonuc["public_managed"]:
            _deliver_stabil_public_graphic(notifier, cand, public_text_sent=True)
        if sonuc["any"]:
            ozet["tekil_gonderilen"] += 1
        if sonuc["recorded"]:
            symbols_map[cand.symbol] = {
                "last_bar_open": cand.bar_open_ts,
                "last_bar_close": cand.bar_close_ts,
                "kind": cand.behavior.reclaim_kind,
                "signal_status": "active",
            }
            degisti = True

    if toplu_liste:
        ozet_metin = format_stabil_burst_summary_card(toplu_liste)
        sonuc = _deliver_stabil_message_result(
            notifier, ozet_metin,
            public_event_id=auxiliary_event_id(
                "stabil-summary", [(c.symbol, c.bar_open_ts) for c in toplu_liste]),
            public_identity={"state": "STABIL_OZET", "stabil_event_ids": [
                auxiliary_event_id("stabil", [(c.symbol, c.bar_open_ts)]) for c in toplu_liste
            ]},
        )
        if sonuc["any"]:
            ozet["toplu_ozet"] = 1
        if sonuc["recorded"]:
            for cand in toplu_liste:
                symbols_map[cand.symbol] = {
                    "last_bar_open": cand.bar_open_ts,
                    "last_bar_close": cand.bar_close_ts,
                    "kind": cand.behavior.reclaim_kind,
                    "signal_status": "active",
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


def _command_structure_context(symbol: str, timeframe: str, frame: pd.DataFrame,
                               bhv: Any, summary: LiveStabilSummary | None):
    """Use only a same-snapshot cached structure result, never a stale cache."""
    if summary is None or summary.bucket != "guclu_cikis" or frame is None or frame.empty:
        return bhv, summary
    from domain_engines.runner import get_latest_domain_results
    from domain_engines.stabil.structure_context import events_for_bars, marker_state
    record = (get_latest_domain_results(symbol, timeframe) or {}).get("market_structure")
    snapshot = getattr(record, "result", None)
    try:
        timestamp = pd.Timestamp(getattr(snapshot, "timestamp", None))
        if pd.isna(timestamp) or timestamp != pd.Timestamp(frame.index[-1]):
            return bhv, summary
    except (ValueError, TypeError):
        return bhv, summary
    events = events_for_bars(record, frame.index)
    current = len(frame) - 1
    marker_bar = current - (summary.reclaim_bars_ago or 0)
    status = marker_state(marker_bar, "UP", timeframe, events, current)
    if status not in {"opposite_structure", "invalidated_by_opposite_bos"}:
        return bhv, summary
    if bhv is not None:
        bhv = replace(bhv, reclaim_kind=None, momentum_kind=None)
    return bhv, replace(summary, bucket="notr", priority=0.0, reclaim_kind=None,
                        reclaim_bars_ago=None,
                        headline_tr=f"{symbol} · ters piyasa yapısı bağlamı",
                        detail_tr="Ters yapı veya sonradan ters BOS: önceki yukarı ok bastırıldı.")


def _command_barrier_context(symbol, timeframe, frame, bhv, summary, manager, now, formations):
    """Use only current-bar geometry; never back-project today's formation."""
    if (summary is None or summary.bucket != "guclu_cikis" or frame is None or frame.empty
            or (summary.reclaim_bars_ago or 0) != 0):
        return bhv, summary
    from domain_engines.stabil.structure_context import barrier_reason
    from domain_engines.stabil.signals import _causal_atr14
    barriers = []
    for pattern in formations or ():
        if pattern.get("stock") != symbol or pattern.get("timeframe") != timeframe:
            continue
        try:
            same_bar = pd.Timestamp(pattern.get("bar_time")) == pd.Timestamp(frame.index[-1])
        except (ValueError, TypeError):
            same_bar = False
        if same_bar and pattern.get("state") not in {"FORMASYON_GECERSIZ", "Yok", "ST_NONE"}:
            barriers.append(("formasyon_siniri", pattern.get("upper")))
            break
    try:
        from domain_engines.stabil.chart_bridge import resistance_for_chart
        from grafik.tarama import _stabil_direnc_verisi
        raw_daily = manager.to_gunluk_dataframe(symbol)
        raw_hourly = manager.to_dataframe(symbol)
        if raw_daily is not None and (timeframe == "1d" or raw_hourly is not None):
            resistance = resistance_for_chart(symbol, timeframe, frame, daily_frame=raw_daily,
                                               hourly_frame=raw_hourly, as_of_close=now)
            layer = _stabil_direnc_verisi({"stabil_direnc": resistance}, timeframe, 0,
                                           len(frame), list(frame.index))
            if layer and layer.get("hazir") and layer.get("renkler") and layer["renkler"][-1] == "alt":
                barriers.insert(0, ("stabil_koridoru", layer["seviyeler"][-1]))
    except Exception as exc:
        logger.debug("/stabil direnç bağlamı kullanılamadı (%s): %s", symbol, exc)
    try:
        atr = _causal_atr14(frame["high"].to_numpy(dtype=float), frame["low"].to_numpy(dtype=float),
                            frame["close"].to_numpy(dtype=float), period=14)[-1]
        reason = barrier_reason(summary.close_price, atr, "UP", barriers)
    except (KeyError, ValueError, TypeError, IndexError):
        reason = None
    if reason is None:
        return bhv, summary
    if bhv is not None:
        bhv = replace(bhv, reclaim_kind=None, momentum_kind=None)
    return bhv, replace(summary, bucket="notr", priority=0.0, reclaim_kind=None,
                        reclaim_bars_ago=None, headline_tr=f"{symbol} · yakın karşı sınır",
                        detail_tr="Karşı sınır yakın; yukarı ok bağlamda bastırıldı.")


def format_single_symbol_stabil_report(
    stock: str,
    deque_manager: Any,
    now: datetime,
    formations: Sequence[Mapping[str, Any]] = (),
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

    summary = summarize_symbol_for_command(stock, out_4h or out_1d, out_1d)
    bhv, summary = _command_structure_context(
        stock, "4h" if out_4h is not None else "1d",
        df_4h if out_4h is not None else df_1d, bhv, summary)
    bhv, summary = _command_barrier_context(
        stock, "4h" if out_4h is not None else "1d",
        df_4h if out_4h is not None else df_1d, bhv, summary, deque_manager, now, formations)
    card_lines = format_stabil_card_lines(
        price=bhv.close_price, support_level=bhv.support_level, behavior=bhv)

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
    formations: Sequence[Mapping[str, Any]] = (),
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
        return format_single_symbol_stabil_report(parca, deque_manager, now, formations)

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
            _, ozet = _command_structure_context(
                sym, "4h" if out_4h is not None else "1d",
                df_4h if out_4h is not None else df_1d, None, ozet)
            _, ozet = _command_barrier_context(
                sym, "4h" if out_4h is not None else "1d",
                df_4h if out_4h is not None else df_1d, None, ozet, deque_manager, now, formations)
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
