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
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

import config
from secrets_redaction import redact_sensitive_text

from .api_messages import API_PROMPT_VERSION, build_api_prompt
from .builder import build_from_frames, build_from_local_cache
from .client import AIClientRouter
from .shadow_store import (
    DEFAULT_LOCAL_SHADOW_FILE,
    build_shadow_record,
    save_shadow_record,
)

logger = logging.getLogger(__name__)

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
    aktif = bool(config.ai_yorum_enabled())
    return {
        "aktif": aktif,
        "dm_aktif": bool(config.ai_yorum_dm_enabled()),
        "public_aktif": bool(config.ai_yorum_public_enabled()),
        "shadow_log_aktif": bool(config.ai_shadow_log_enabled()),
        "saglayicilar": providers,
        "hazir": bool(aktif and providers),
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
        if pd.isna(num):
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
            prompt_surumu=str(bundle.get("version") or API_PROMPT_VERSION),
            system_sha256=str(bundle.get("system_sha256") or ""),
            kaynak_turu=source_kind,
            tetikleyici_tur=trigger_kind,
            kap_context=kap_context,
            telegrama_gitti=telegram_delivered,
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
    tf_tr = _TF_TR.get(tf, tf or "4s")
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
    lines.append(visible_text.strip())
    lines.append("")
    lines.append("📌 Yapay zekâ teknik özeti · yatırım tavsiyesi değildir")

    text = "\n".join(lines).strip()
    if len(text) > _TELEGRAM_SAFE_MAX:
        text = text[: _TELEGRAM_SAFE_MAX - 1].rstrip() + "…"
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
    router: AIClientRouter | None = None,
    kap_arsiv_yolu: str | None = None,
    shadow_local_path: str | os.PathLike[str] | None = None,
    shadow_store: Any = None,
    telegram_delivered_hint: bool = False,
) -> dict[str, Any]:
    """OHLCV çerçevelerinden prompt + KAP bağlamı kurup AI zincirini çalıştırır."""
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
            source="canlı tarama verisi",
        )
    except Exception as exc:  # noqa: BLE001 - prompt kurulum hatası düz karta düşer
        logger.warning("AI veri paketi kurulamadı (%s %s): %s", sym, tf, exc)
        return {"ok": False, "reason": "packet_error", "fallback_to_plain_card": True}

    kap_ctx = _read_live_kap_context(sym, packet["as_of"], kap_arsiv_yolu=kap_arsiv_yolu)
    try:
        bundle = build_api_prompt(
            packet,
            modality="text_only",
            include_hidden_verdict=True,
            kap_context=kap_ctx,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI prompt derlenemedi (%s %s): %s", sym, tf, exc)
        return {"ok": False, "reason": "prompt_error", "fallback_to_plain_card": True}

    max_wall = config.ai_yorum_max_bekleme_sn()
    try:
        asked = active_router.ask_bundle(
            bundle,
            parse_response=True,
            require_verdict=False,
            max_wall_seconds_per_provider=max_wall,
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
        telegram_delivered=bool(telegram_delivered_hint and ok_tg),
        shadow_local_path=shadow_local_path,
        shadow_store=shadow_store,
    )

    if not ok_tg:
        err = ((parsed.get("validation") or {}).get("error")) or "yapısal doğrulama geçemedi"
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
        router=router,
        kap_arsiv_yolu=kap_arsiv_yolu,
        shadow_local_path=shadow_local_path,
        shadow_store=shadow_store,
        telegram_delivered_hint=bool(config.ai_yorum_dm_enabled() or config.ai_yorum_public_enabled()),
    )
    if not outcome.get("ok"):
        return False

    alert_data["ai_yorum_mesaji"] = format_ai_alarm_message(alert_data, outcome["visible_text"])
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
            telegram_delivered_hint=True,
        )
    else:
        # Bellek önbelleğinde yoksa yerel bot_data seed dosyasını dene.
        try:
            packet = build_from_local_cache(sym, as_of=simdi, main_tf=tf_norm)
        except Exception as exc:  # noqa: BLE001
            return f"⚠️ {sym} ({tf_tr}) için önbellekte yeterli veri bulunamadı ({type(exc).__name__})."
        kap_ctx = _read_live_kap_context(sym, packet["as_of"], kap_arsiv_yolu=kap_arsiv_yolu)
        bundle = build_api_prompt(
            packet,
            modality="text_only",
            include_hidden_verdict=True,
            kap_context=kap_ctx,
        )
        asked = active_router.ask_bundle(
            bundle,
            parse_response=True,
            require_verdict=False,
            max_wall_seconds_per_provider=config.ai_yorum_max_bekleme_sn(),
        )
        res = asked["result"]
        parsed = asked["parsed"]
        if not res.ok or not res.text or not isinstance(parsed, Mapping):
            outcome = {"ok": False, "reason": "all_providers_failed", "result": res, "parsed": parsed}
        else:
            _persist_shadow_safe(
                packet,
                bundle,
                res.text,
                provider=res.provider,
                model=res.model,
                source_kind="manuel",
                trigger_kind="komut_ai",
                kap_context=kap_ctx,
                telegram_delivered=bool(parsed.get("ok_for_telegram")),
                shadow_local_path=shadow_local_path,
                shadow_store=shadow_store,
            )
            outcome = {
                "ok": bool(parsed.get("visible_text")),
                "visible_text": str(parsed.get("visible_text") or "").strip(),
                "verdict": parsed.get("verdict"),
                "result": res,
                "parsed": parsed,
            }

    res = outcome.get("result")
    if not outcome.get("ok") and not outcome.get("visible_text"):
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
    if len(text) > _TELEGRAM_SAFE_MAX:
        text = text[: _TELEGRAM_SAFE_MAX - 1].rstrip() + "…"
    return text
