"""Canlı alarm ve DM `/ai` komutu için uçtan uca AI yorum orkestrasyon katmanı.

Sorumluluklar:
  - Sıralı sağlayıcı zincirini çalıştırır:
      ApiWrapper (/v1/ask) -> Ücretsiz Gemini #1 -> Ücretsiz Gemini #2 -> düz kart yedeği.
  - Hiçbir AI anahtarı tanımlı değilse 0 ms içinde çıkıp düz karta düşer.
  - Başarılı ve Telegram doğrulamasından geçen AI yorumunu ana alarm mesajı olarak
    biçimlendirir; gizli `[AI_SONUC ...]` bloğu Telegram alarmına ASLA sızmaz.
  - `AI_SHADOW_LOG` açıksa gizli `[AI_SONUC ...]` 5-filtre kaydını yerel JSON'a ve
    Supabase tanımlıysa `public.ai_yorum_test` tablosuna kaydeder.
  - Herhangi bir hata, zaman aşımı veya yapısal doğrulama başarısızlığında istisna
    yükseltmez; arayan katman kesintisiz olarak düz teknik kartı gönderir.
"""
from __future__ import annotations

import logging
import math
import os
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

import config
from secrets_redaction import redact_sensitive_text

from .api_messages import API_PROMPT_VERSION, build_api_prompt
from .builder import build_from_frames, build_from_local_cache
from .budget import utf16_len
from .client import AIClientRouter
from .commentary import format_short_alarm_commentary
from .shadow_store import (
    DEFAULT_LOCAL_SHADOW_FILE,
    build_shadow_record,
    save_shadow_record,
)

logger = logging.getLogger(__name__)
_AI_ALARM_LOCK = threading.Lock()
_AI_ALARM_COUNTS = Counter()


def _note_alarm_outcome(outcome):
    reason = "ok" if outcome.get("ok") else outcome.get("reason", "other")
    if reason not in {"ok", "stale_or_unknown_data", "all_providers_failed",
                       "validation_failed", "packet_error", "client_error"}:
        reason = "other"
    with _AI_ALARM_LOCK:
        _AI_ALARM_COUNTS[reason] += 1


_TF_TR = {"1h": "1s", "2h": "2s", "4h": "4s", "1d": "1g"}
_STATE_TR = {
    "KIRILIM_TEYITLI": "Kırılım Teyitli",
    "RETEST_BASARILI": "Retest Başarılı",
    "KIRILIM_GECERSIZLESTI": "Kırılım Geçersizleşti",
    "STABIL_GERI_ALIM": "Stabil Geri Alım",
    "YENI_DOMAIN": "Teknik Tetikleme",
}
_PROVIDER_LABEL = {
    "api_wrapper": "ApiWrapper",
    "gemini_free_1": "Gemini #1",
    "gemini_free_2": "Gemini #2",
}
_TELEGRAM_SAFE_MAX = 4000


def _current_secret_values(env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    src = env if env is not None else os.environ
    vals = []
    for key in (
        "AI_WRAPPER_API_KEY",
        "GEMINI_API_KEY_1",
        "GEMINI_API_KEY",
        "GEMINI_API_KEY_2",
        "SUPABASE_SERVICE_ROLE_KEY",
        "TELEGRAM_BOT_TOKEN",
    ):
        v = str(src.get(key) or "").strip()
        if v:
            vals.append(v)
    return tuple(vals)


def is_ai_configured(env: Mapping[str, str] | None = None) -> bool:
    """En az bir AI sağlayıcısı (ApiWrapper veya Gemini #1/#2) yapılandırılmış mı?"""
    try:
        router = AIClientRouter.from_env(env)
        return len(router.providers) > 0
    except Exception:  # noqa: BLE001
        return False


def ai_health_summary(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """`/health` için sıfır ağ / sıfır sır AI istemci durumu özeti."""
    try:
        providers = list(AIClientRouter.from_env(env).provider_names())
    except Exception:  # noqa: BLE001
        providers = []
    with _AI_ALARM_LOCK:
        alarm_counts = dict(_AI_ALARM_COUNTS)
    aktif = bool(config.ai_yorum_enabled())
    return {
        "aktif": aktif,
        "dm_aktif": bool(config.ai_yorum_dm_enabled()),
        "public_aktif": bool(config.ai_yorum_public_enabled()),
        "shadow_log_aktif": bool(config.ai_shadow_log_enabled()),
        "saglayicilar": providers,
        "hazir": bool(aktif and providers),
        "alarm_sonuclari_oturum": alarm_counts,
        "alarm_toplam_butce_sn": config.AI_ALARM_TOPLAM_BUTCE_SN,
        "alarm_saglayici_butce_sn": config.AI_ALARM_SAGLAYICI_BUTCE_SN,
    }


def _ensure_tz_frame(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    out = frame.copy()
    if isinstance(out.index, pd.DatetimeIndex):
        if out.index.tz is None:
            out.index = out.index.tz_localize("Europe/Istanbul")
    return out


def _tr_price(value: Any) -> str:
    try:
        num = float(value)
        if isinstance(value, bool) or not math.isfinite(num) or num <= 0:
            return ""
        return f"{num:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    except (TypeError, ValueError):
        return ""


def _resolve_kap_archive_path(explicit_path: str | None = None) -> Path | None:
    if explicit_path and str(explicit_path).strip():
        return Path(str(explicit_path).strip())
    try:
        from kap.runtime import kap_arsiv_yolu

        return Path(kap_arsiv_yolu())
    except Exception:  # noqa: BLE001
        raw = str(getattr(config, "KAP_ARSIV_YOLU", "") or "").strip()
        if raw:
            return Path(raw)
        return None


def _read_live_kap_context(
    symbol: str,
    as_of: Any,
    *,
    kap_arsiv_yolu: str | None = None,
    origin: str = "kap_arsiv",
) -> dict[str, Any] | None:
    if not config.kap_baglam_enabled() and not kap_arsiv_yolu:
        return None
    archive = _resolve_kap_archive_path(kap_arsiv_yolu)
    if archive is None or not archive.is_file():
        return None
    try:
        from kap import alarm_kap_baglami_oku

        stamp = pd.Timestamp(as_of)
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize("Europe/Istanbul")
        return alarm_kap_baglami_oku(
            symbol,
            stamp.to_pydatetime(),
            arsiv_yolu=str(archive),
            max_age_gun=int(getattr(config, "KAP_MAX_YAS_GUN", 7) or 7),
            origin=origin,  # type: ignore[arg-type]
            force=True,
        )
    except Exception as exc:  # noqa: BLE001 - KAP okuma hatası AI'yi durdurmaz
        logger.debug("KAP bağlamı okunamadı (%s): %s", symbol, type(exc).__name__)
        return None


def _resolve_shadow_local_path(explicit_path: str | os.PathLike[str] | None = None) -> Path | None:
    if explicit_path is not None:
        return Path(explicit_path)
    data_dir = str(getattr(config, "DATA_DIR", "") or os.getenv("DATA_DIR") or "").strip()
    if data_dir:
        return Path(data_dir) / DEFAULT_LOCAL_SHADOW_FILE
    try:
        from state import paths as _state_paths

        resolved = _state_paths.son_tarama_data_dir()
        return Path(resolved) / DEFAULT_LOCAL_SHADOW_FILE
    except Exception:  # noqa: BLE001
        return Path(DEFAULT_LOCAL_SHADOW_FILE)


def _make_shadow_supabase_store(explicit_store: Any = None) -> tuple[Any, bool]:
    if explicit_store is not None:
        return explicit_store, bool(getattr(explicit_store, "writable", False))
    try:
        from supabase_store import SupabaseStore

        store = SupabaseStore.from_env(read_only=False)
        if store is not None and getattr(store, "writable", False):
            return store, True
    except Exception as exc:  # noqa: BLE001
        logger.debug("AI gölge Supabase istemcisi açılamadı: %s", type(exc).__name__)
    return None, False


def _persist_shadow_safe(
    packet: Mapping[str, Any],
    bundle: Mapping[str, Any],
    raw_ai_text: str,
    *,
    provider: str | None,
    model: str | None,
    source_kind: str,
    trigger_kind: str | None,
    kap_context: Mapping[str, Any] | None,
    telegram_delivered: bool,
    shadow_local_path: str | os.PathLike[str] | None = None,
    shadow_store: Any = None,
) -> dict[str, Any] | None:
    if not config.ai_shadow_log_enabled():
        return None
    try:
        model_label = f"{provider or 'ai'}:{model or 'default'}"
        record, _parsed = build_shadow_record(
            packet,
            raw_ai_text,
            model_adi=model_label,
            prompt_surumu=str(bundle.get("prompt_version") or API_PROMPT_VERSION),
            system_sha256=str(bundle.get("system_sha256") or ""),
            kaynak_turu=source_kind,
            tetikleyici_tur=trigger_kind,
            kap_context=kap_context,
            telegrama_gitti=telegram_delivered,
            output_profile=(bundle.get("metadata") or {}).get("output_profile", "standard"),
        )
        local_path = _resolve_shadow_local_path(shadow_local_path)
        store, allow_supa = _make_shadow_supabase_store(shadow_store)
        return save_shadow_record(
            record,
            store=store,
            local_path=local_path,
            allow_supabase_write=allow_supa,
        )
    except Exception as exc:  # noqa: BLE001 - gölge kaydı alarmı asla durdurmaz
        logger.warning(
            "AI gölge kaydı atlandı: %s",
            redact_sensitive_text(str(exc), *_current_secret_values())[:160],
        )
        return None


def format_ai_alarm_message(
    alert_data: Mapping[str, Any],
    visible_text: str,
) -> str:
    """Ana alarm kartının YERİNE gidecek temiz Telegram AI yorum mesajını biçimlendirir.

    Gizli `[AI_SONUC ...]` bloğu bu fonksiyona gelmeden önce ayıklanmıştır ve
    Telegram mesajına ASLA dahil edilmez.
    """
    stock = str(alert_data.get("stock_name") or "").strip().upper()
    tf = str(alert_data.get("timeframe") or "").strip().lower()
    tf_tr = {"1h": "1 saat", "2h": "2 saat", "4h": "4 saat", "1d": "Günlük"}.get(tf, tf or "4 saat")
    pattern = str(alert_data.get("pattern_name") or "").strip()
    state = str(alert_data.get("state") or "").strip().upper()
    state_tr = _STATE_TR.get(state, state.replace("_", " ").title() if state else "")

    title_parts = [p for p in (stock, tf_tr, pattern) if p]
    header = "🤖 " + " · ".join(title_parts)
    if state_tr:
        header += f" ({state_tr})"

    close_val = alert_data.get("candle_close_price")
    if close_val is None:
        close_val = alert_data.get("close_price")
    price_str = _tr_price(close_val)
    bar_metni = str(alert_data.get("bar_metni") or "").strip()

    meta_parts = []
    if price_str:
        meta_parts.append(f"Kapanış: {price_str} TL")
    if bar_metni:
        meta_parts.append(bar_metni)

    lines = [header]
    if meta_parts:
        lines.append(" · ".join(meta_parts))
    lines.append("")
    lines.append(format_short_alarm_commentary(visible_text))
    lines.append("")
    lines.append("📌 Yapay zekâ teknik özeti · yatırım tavsiyesi değildir")

    text = "\n".join(lines).strip()
    if utf16_len(text) > _TELEGRAM_SAFE_MAX:
        raise ValueError("AI alarm mesajı Telegram güvenli uzunluk sınırını aştı")
    return text


def generate_ai_commentary_for_frames(
    symbol: str,
    df_1h: pd.DataFrame,
    *,
    as_of: Any,
    main_tf: str = "4h",
    df_1d: pd.DataFrame | None = None,
    source_kind: str = "alarm",
    trigger_kind: str | None = None,
    trigger: Mapping[str, Any] | None = None,
    router: AIClientRouter | None = None,
    kap_arsiv_yolu: str | None = None,
    shadow_local_path: str | os.PathLike[str] | None = None,
    shadow_store: Any = None,
    telegram_delivered_hint: bool = False,
) -> dict[str, Any]:
    """OHLCV çerçevelerinden prompt + KAP bağlamı kurup AI zincirini çalıştırır.

    `telegram_delivered_hint` eski çağrılarla uyum için kabul edilir; hazırlık
    gerçek teslim olmadığı için artık gölge kaydını teslim edildi işaretlemez.
    """
    sym = str(symbol or "").strip().upper()
    tf = str(main_tf or "4h").strip().lower()
    if config.sembol_turu(sym) != "hisse":
        return {"ok": False, "reason": "non_equity", "fallback_to_plain_card": True}

    active_router = router if router is not None else AIClientRouter.from_env()
    if not active_router.providers:
        return {"ok": False, "reason": "no_providers", "fallback_to_plain_card": True}

    hourly = _ensure_tz_frame(df_1h)
    if hourly is None or len(hourly) < 5:
        return {"ok": False, "reason": "insufficient_1h", "fallback_to_plain_card": True}
    daily = _ensure_tz_frame(df_1d)

    try:
        packet = build_from_frames(
            sym,
            hourly,
            as_of=as_of,
            main_tf=tf,
            daily=daily,
            research_mode="strict",
            source=(f"{'canlı tarama' if source_kind == 'alarm' else 'manuel önbellek'}; "
                    f"1H kaynak={hourly.attrs.get('veri_kaynagi', 'bilinmiyor')}"),
        )
        if source_kind == "alarm" and tf == "1h":
            # The generic packet builder uses the :30 chart grid. A validated
            # native :00 close is not 30 minutes late on its own provider grid.
            from data.quality import hourly_fetch_validator
            validate = hourly_fetch_validator(sym, as_of)
            if validate is not None and validate(hourly)[0]:
                packet["timeframes"]["1h"]["expected_delay_minutes"] = 0
    except Exception as exc:  # noqa: BLE001 - prompt kurulum hatası düz karta düşer
        logger.warning("AI veri paketi kurulamadı (%s %s): %s", sym, tf, exc)
        return {"ok": False, "reason": "packet_error", "fallback_to_plain_card": True}

    return _generate_ai_commentary_for_packet(
        packet, router=active_router, source_kind=source_kind,
        trigger_kind=trigger_kind, trigger=trigger, kap_arsiv_yolu=kap_arsiv_yolu,
        shadow_local_path=shadow_local_path, shadow_store=shadow_store,
    )


def _generate_ai_commentary_for_packet(
    packet: Mapping[str, Any],
    *,
    router: AIClientRouter,
    source_kind: str,
    trigger_kind: str | None = None,
    trigger: Mapping[str, Any] | None = None,
    kap_arsiv_yolu: str | None = None,
    shadow_local_path: str | os.PathLike[str] | None = None,
    shadow_store: Any = None,
) -> dict[str, Any]:
    """Canlı ve yerel veri aynı hata/koruma kapılarından geçer."""
    sym, tf = str(packet["symbol"]), str(packet["main_tf"])
    active_router = router
    # Eksik/bayat ana TF için AI harcaması yapma; teknik alarm engellenmez.
    main_data = (packet.get("timeframes") or {}).get(tf, {})
    delay = main_data.get("expected_delay_minutes")
    try:
        fresh_main = main_data.get("status") == "available" and math.isfinite(float(delay)) and float(delay) == 0
    except (TypeError, ValueError):
        fresh_main = False
    if source_kind == "alarm" and not fresh_main:
        return {"ok": False, "reason": "stale_or_unknown_data", "fallback_to_plain_card": True}
    kap_ctx = _read_live_kap_context(sym, packet["as_of"], kap_arsiv_yolu=kap_arsiv_yolu)
    try:
        bundle = build_api_prompt(
            packet,
            modality="text_only",
            include_hidden_verdict=True,
            kap_context=kap_ctx,
            trigger=trigger,
            output_profile="alarm" if source_kind == "alarm" else "standard",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI prompt derlenemedi (%s %s): %s", sym, tf, exc)
        return {"ok": False, "reason": "prompt_error", "fallback_to_plain_card": True}

    max_wall = config.ai_yorum_max_bekleme_sn()
    budget_args = {}
    if source_kind == "alarm":
        max_wall = min(max_wall or config.AI_ALARM_SAGLAYICI_BUTCE_SN,
                       config.AI_ALARM_SAGLAYICI_BUTCE_SN)
        budget_args["max_total_seconds"] = config.AI_ALARM_TOPLAM_BUTCE_SN
    try:
        asked = active_router.ask_bundle(
            bundle,
            parse_response=True,
            require_verdict=False,
            max_wall_seconds_per_provider=max_wall,
            **budget_args,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "AI istemci zinciri hatası (%s %s): %s",
            sym,
            tf,
            redact_sensitive_text(str(exc), *_current_secret_values())[:160],
        )
        return {"ok": False, "reason": "client_error", "fallback_to_plain_card": True}

    result = asked["result"]
    parsed = asked["parsed"]
    if not result.ok or not result.text or not isinstance(parsed, Mapping):
        ozet = ", ".join(f"{a.provider}:{a.outcome}" for a in result.attempts)
        logger.warning("AI sağlayıcı zinciri başarısız (%s %s) [%s] -> düz kart yedeği", sym, tf, ozet)
        return {
            "ok": False,
            "reason": "all_providers_failed",
            "result": result,
            "parsed": parsed,
            "fallback_to_plain_card": True,
        }

    ok_tg = bool(parsed.get("ok_for_telegram")) and bool(str(parsed.get("visible_text") or "").strip())
    shadow_res = _persist_shadow_safe(
        packet,
        bundle,
        result.text,
        provider=result.provider,
        model=result.model,
        source_kind=source_kind,
        trigger_kind=trigger_kind,
        kap_context=kap_ctx,
        # Hazırlama/gönderim niyeti teslim makbuzu değildir.
        telegram_delivered=False,
        shadow_local_path=shadow_local_path,
        shadow_store=shadow_store,
    )

    if not ok_tg:
        validation = parsed.get("validation") or {}
        err = validation.get("error") or ", ".join(validation.get("warnings") or []) or "doğrulama geçemedi"
        logger.warning(
            "AI yanıtı Telegram doğrulamasından geçemedi (%s %s, %s: %s) -> düz kart yedeği",
            sym,
            tf,
            result.provider,
            err,
        )
        return {
            "ok": False,
            "reason": "validation_failed",
            "result": result,
            "parsed": parsed,
            "shadow": shadow_res,
            "fallback_to_plain_card": True,
        }

    return {
        "ok": True,
        "visible_text": str(parsed["visible_text"]).strip(),
        "verdict": parsed.get("verdict"),
        "result": result,
        "parsed": parsed,
        "shadow": shadow_res,
        "fallback_to_plain_card": False,
    }


def enrich_alarm_with_ai(
    alert_data: dict[str, Any],
    *,
    df_1h: pd.DataFrame | None,
    df_1d: pd.DataFrame | None = None,
    as_of: Any = None,
    router: AIClientRouter | None = None,
    kap_arsiv_yolu: str | None = None,
    shadow_local_path: str | os.PathLike[str] | None = None,
    shadow_store: Any = None,
) -> bool:
    """Klasik formasyon alarm sözlüğüne AI yorum mesajını ekler; hata hâlinde dokunmaz.

    Başarılı olursa `alert_data["ai_yorum_mesaji"]` alanını doldurup True döner.
    Herhangi bir sorunda False döner ve notifier kesintisiz olarak düz kartı gönderir.
    """
    if not isinstance(alert_data, dict):
        return False
    if not config.ai_yorum_enabled():
        return False
    if not (
        config.ai_yorum_dm_enabled()
        or config.ai_yorum_public_enabled()
        or config.ai_shadow_log_enabled()
    ):
        return False
    if router is None and not is_ai_configured():
        return False
    if df_1h is None or not isinstance(df_1h, pd.DataFrame) or df_1h.empty:
        return False

    stock = str(alert_data.get("stock_name") or "").strip().upper()
    tf = str(alert_data.get("timeframe") or "4h").strip().lower()
    state = str(alert_data.get("state") or "").strip().upper()
    cutoff = as_of or alert_data.get("bar_kapanis") or alert_data.get("timestamp") or datetime.now(config.ISTANBUL_TZ)

    outcome = generate_ai_commentary_for_frames(
        stock,
        df_1h,
        as_of=cutoff,
        main_tf=tf,
        df_1d=df_1d,
        source_kind="alarm",
        trigger_kind=state or None,
        trigger={
            "kind": "alarm",
            "timeframe": tf,
            "state": state,
            "pattern_name": alert_data.get("pattern_name"),
            "direction": alert_data.get("break_dir"),
            "bar_open": alert_data.get("bar_time"),
            "bar_close": alert_data.get("bar_kapanis"),
        },
        router=router,
        kap_arsiv_yolu=kap_arsiv_yolu,
        shadow_local_path=shadow_local_path,
        shadow_store=shadow_store,
    )
    _note_alarm_outcome(outcome)
    alert_data["ai_yorum_durum"] = "ok" if outcome.get("ok") else outcome.get("reason", "hata")
    if not outcome.get("ok"):
        return False

    try:
        message = format_ai_alarm_message(alert_data, outcome["visible_text"])
    except ValueError as exc:
        logger.warning("AI alarm biçimlenemedi (%s %s): %s -> düz kart", stock, tf, exc)
        return False
    alert_data["ai_yorum_mesaji"] = message
    res = outcome.get("result")
    if res is not None:
        alert_data["ai_yorum_saglayici"] = res.provider
    logger.info(
        "🤖 AI alarm yorumu hazır: %s %s %s (%s, %.1fs)",
        stock,
        tf,
        state,
        getattr(res, "provider", "?"),
        float(getattr(res, "total_elapsed_s", 0.0)),
    )
    return True


def build_ai_replacement_text_for_signal(
    *,
    symbol: str,
    timeframe: str,
    pattern_name: str,
    state: str,
    close_price: float | None,
    bar_metni: str = "",
    df_1h: pd.DataFrame | None,
    df_1d: pd.DataFrame | None = None,
    as_of: Any = None,
    router: AIClientRouter | None = None,
    kap_arsiv_yolu: str | None = None,
    shadow_local_path: str | os.PathLike[str] | None = None,
    shadow_store: Any = None,
) -> str | None:
    """Stabil 4s ve Yeni Domain tekil kartları için AI yorum metni üretir (hata -> None)."""
    payload: dict[str, Any] = {
        "stock_name": symbol,
        "timeframe": timeframe,
        "pattern_name": pattern_name,
        "state": state,
        "candle_close_price": close_price,
        "close_price": close_price,
        "bar_metni": bar_metni,
    }
    if not enrich_alarm_with_ai(
        payload,
        df_1h=df_1h,
        df_1d=df_1d,
        as_of=as_of,
        router=router,
        kap_arsiv_yolu=kap_arsiv_yolu,
        shadow_local_path=shadow_local_path,
        shadow_store=shadow_store,
    ):
        return None
    return payload.get("ai_yorum_mesaji")


def run_manual_ai_analysis(
    symbol: str,
    tf: str = "4h",
    *,
    deque_manager: Any = None,
    now: datetime | None = None,
    router: AIClientRouter | None = None,
    kap_arsiv_yolu: str | None = None,
    shadow_local_path: str | os.PathLike[str] | None = None,
    shadow_store: Any = None,
) -> str:
    """DM `/ai <SEMBOL> [TF]` komutu için tam canlı analiz metni döndürür."""
    sym = str(symbol or "").strip().upper()
    tf_norm = str(tf or "4h").strip().lower()
    tf_tr = _TF_TR.get(tf_norm, tf_norm)
    if config.sembol_turu(sym) != "hisse":
        return f"ℹ️ {sym} BIST hissesi değil; `/ai` yalnızca BIST hisselerinde çalışır."

    active_router = router if router is not None else AIClientRouter.from_env()
    if not active_router.providers:
        return (
            "⚠️ Hiçbir AI sağlayıcısı yapılandırılmamış.\n"
            "Render Environment (veya .env) içine AI_WRAPPER_BASE_URL + AI_WRAPPER_API_KEY "
            "ve/veya GEMINI_API_KEY_1 / GEMINI_API_KEY_2 ekleyin."
        )

    simdi = now or datetime.now(config.ISTANBUL_TZ)
    df_1h = None
    df_1d = None
    if deque_manager is not None:
        try:
            df_1h = deque_manager.to_dataframe(sym)
        except Exception:  # noqa: BLE001
            df_1h = None
        try:
            df_1d = deque_manager.to_gunluk_dataframe(sym)
        except Exception:  # noqa: BLE001
            df_1d = None

    if df_1h is not None and len(df_1h) >= 5:
        outcome = generate_ai_commentary_for_frames(
            sym,
            df_1h,
            as_of=simdi,
            main_tf=tf_norm,
            df_1d=df_1d,
            source_kind="manuel",
            trigger_kind="komut_ai",
            router=active_router,
            kap_arsiv_yolu=kap_arsiv_yolu,
            shadow_local_path=shadow_local_path,
            shadow_store=shadow_store,
        )
    else:
        # Bellek önbelleğinde yoksa yerel bot_data seed dosyasını dene.
        try:
            packet = build_from_local_cache(sym, as_of=simdi, main_tf=tf_norm)
        except Exception as exc:  # noqa: BLE001
            return f"⚠️ {sym} ({tf_tr}) için önbellekte yeterli veri bulunamadı ({type(exc).__name__})."
        outcome = _generate_ai_commentary_for_packet(
            packet, router=active_router, source_kind="manuel",
            trigger_kind="komut_ai", kap_arsiv_yolu=kap_arsiv_yolu,
            shadow_local_path=shadow_local_path, shadow_store=shadow_store,
        )

    res = outcome.get("result")
    if not outcome.get("ok"):
        denemeler = ""
        if res is not None and getattr(res, "attempts", None):
            denemeler = "\nDenemeler: " + ", ".join(
                f"{_PROVIDER_LABEL.get(a.provider, a.provider)}={a.outcome}"
                for a in res.attempts
            )
        return (
            f"❌ {sym} · {tf_tr} AI analizi alınamadı ({outcome.get('reason', 'hata')})."
            f"{denemeler}\nCanlı alarmlarda bu durumda otomatik olarak düz teknik kart gönderilir."
        )

    provider_tr = _PROVIDER_LABEL.get(getattr(res, "provider", "") or "", getattr(res, "provider", "AI"))
    elapsed = float(getattr(res, "total_elapsed_s", 0.0))
    lines = [
        f"🤖 {sym} · {tf_tr} · AI Analiz ({provider_tr} · {elapsed:.1f}s)",
        "",
        str(outcome.get("visible_text") or "").strip(),
    ]
    verdict = outcome.get("verdict")
    if isinstance(verdict, Mapping) and verdict:
        lines.append("")
        lines.append(
            f"🧪 Özet: eğilim={verdict.get('egilim', '-')} · "
            f"güç={verdict.get('guc', '-')} · MTF={verdict.get('mtf_uyum', '-')} · "
            f"risk={verdict.get('risk', '-')} · yayın={verdict.get('yayin_degeri', '-')}"
        )
    lines.append("📌 Yapay zekâ teknik özeti · yatırım tavsiyesi değildir")
    text = "\n".join(lines).strip()
    if utf16_len(text) > _TELEGRAM_SAFE_MAX:
        return f"⚠️ {sym} · {tf_tr} AI yanıtı güvenli mesaj sınırını aştı; yorum kesilerek gösterilmedi."
    return text
