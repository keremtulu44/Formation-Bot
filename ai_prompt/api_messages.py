"""AI API sağlayıcıları için önbelleklenebilir system/user prompt derleyicisi.

Bu modül tamamen yerel ve ağsızdır: HTTP isteği atmaz, API anahtarı okumaz,
SDK bağımlılığı eklemez ve canlı motor/alarm state'ini değiştirmez.
Üretilen `system` metni aynı modalite için semboller arası bayt-birebir
sabittir (OpenAI / Anthropic / Gemini prompt caching uyumlu); dinamik grafik,
replay ve araştırma verisi XML sınırlarıyla ayrılmış `user` mesajına konur.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

import pandas as pd

from notification_context import _VOLUME_STATE_LABELS
from .builder import ROOT, STABIL_LABELS, TF_ORDER, _label, _num, _same_level
from .compact import _drawn_context, _replay, _research, _size, _stabil, _time
from .verdict import HIDDEN_VERDICT_INSTRUCTION

API_PROMPT_VERSION = "api-v1"
DEFAULT_MAX_USER_CHARS = 6000
HARD_MAX_USER_CHARS = 12000

_MODALITY_NOTES = {
    "text_only": (
        "MODALİTE: Grafik görseli ekli değil; yalnızca `<veri_paketi>` içindeki "
        "kapalı-bar verilerine dayan, verilmeyen görsel detayı varsayma."
    ),
    "multimodal": (
        "MODALİTE: Grafik görselleri ekli; görsel çizgileri `<veri_paketi>` içindeki "
        "sayısal bağlamla birlikte oku, çelişkide kapalı-bar verisini esas al, "
        "görselde etiketlenmeyen sayıyı tahmin etme."
    ),
}

_SAFE_TAG_RE = re.compile(r"^[a-z0-9_]{1,32}$")
_CLOSING_TAG_RE = re.compile(r"</\s*(ek_baglam|veri_paketi|tetikleyici|grafikler|replay|genel_arastirma)\s*>", re.IGNORECASE)


def _escape_data_text(text: str) -> str:
    """Harici metinlerdeki kapatma etiketlerini etkisizleştir (veri sınırı koruması)."""
    return _CLOSING_TAG_RE.sub(lambda m: f"&lt;/{m.group(1)}&gt;", str(text))


def _pct_vs(close: Any, level: Any) -> str:
    c, lv = _num(close), _num(level)
    if c is None or lv is None or lv <= 0:
        return ""
    pct = (c - lv) / lv * 100.0
    sign = "+" if pct >= 0 else "−"
    return f" ({sign}%{abs(pct):.1f})".replace(".", ",")


def _rich_tf_lines(tf: str, row: Mapping[str, Any]) -> list[str]:
    """Packet içinde zaten bulunan ama çıplak grafik özetinde saklı kalan motor durumları."""
    if row.get("status") != "available":
        return []
    out: list[str] = []

    ms = row.get("market_structure") or {}
    if ms.get("status") == "available":
        ext = (ms.get("scopes") or {}).get("dış")
        if isinstance(ext, Mapping) and ext.get("state"):
            out.append(f"Dış yapı durumu: {ext['state']}.")

    vol = row.get("volume") or {}
    if vol.get("status") == "available":
        state = str(vol.get("state") or "")
        if state == "PARTICIPATION_PENDING":
            out.append("Hacim motoru: hazır değil (sonuç çıkarılmaz).")
        elif state:
            label = _VOLUME_STATE_LABELS.get(state, state)
            out.append(f"Hacim motoru: {label}.")
    elif vol.get("status"):
        out.append(f"Hacim motoru: {vol['status']}.")

    if tf in {"4h", "1d"}:
        close = row.get("last_close")
        for key, title in (("chart_stabil_support", "Stabil destek uzaklığı"),
                           ("chart_stabil_resistance", "Stabil direnç uzaklığı")):
            if row.get(key) is not None:
                pct = _pct_vs(close, row[key])
                if pct:
                    out.append(f"{title}:{pct}.")
        stabil = row.get("stabil") or {}
        if stabil.get("status") == "available":
            roles = stabil.get("roles") or {}
            role_parts = []
            for rkey, rlabel in (("weekly", "haftalık"), ("daily", "günlük"), ("h4", "4s")):
                info = roles.get(rkey)
                if isinstance(info, Mapping) and info.get("state"):
                    state_tr = _label(STABIL_LABELS, str(info["state"]))
                    role_parts.append(f"{rlabel}={state_tr}")
            if role_parts:
                out.append("Stabil roller: " + ", ".join(role_parts) + ".")
    return out


def _render_trigger(trigger: Mapping[str, Any], year: int) -> list[str]:
    lines = ["<tetikleyici>"]
    for key in ("kind", "channel", "timeframe", "state", "pattern_name", "direction", "bar_open", "bar_close", "summary"):
        value = trigger.get(key)
        if value is None or value == "":
            continue
        if key in {"bar_open", "bar_close"}:
            rendered = _time(value, year)
            if rendered == "bilinmiyor":
                rendered = _escape_data_text(str(value))
            lines.append(f"{key}: {rendered}")
        else:
            lines.append(f"{key}: {_escape_data_text(str(value))}")
    reasons = trigger.get("reasons")
    if isinstance(reasons, Sequence) and not isinstance(reasons, (str, bytes)) and reasons:
        clean = "; ".join(_escape_data_text(str(r)) for r in reasons if str(r).strip())
        if clean:
            lines.append(f"reasons: {clean}")
    lines.append("</tetikleyici>")
    return lines


def _normalize_extra_sections(
    extra_sections: Mapping[str, str] | Sequence[tuple[str, str]] | None,
) -> list[tuple[str, str]]:
    if not extra_sections:
        return []
    items = list(extra_sections.items()) if isinstance(extra_sections, Mapping) else list(extra_sections)
    out: list[tuple[str, str]] = []
    for raw_name, raw_body in items:
        name = str(raw_name).strip().lower()
        if not _SAFE_TAG_RE.fullmatch(name):
            raise ValueError(f"Geçersiz ek bölüm adı: {raw_name!r} (yalnız [a-z0-9_], en fazla 32 karakter)")
        body = str(raw_body or "").strip()
        if body:
            out.append((name, _escape_data_text(body)))
    return out


def _build_system_prompt(modality: str, *, include_hidden_verdict: bool = False) -> str:
    if modality not in _MODALITY_NOTES:
        raise ValueError(f"Desteklenmeyen modalite: {modality!r} ('text_only' veya 'multimodal' olmalı)")
    base = (ROOT / "talimat_api.txt").read_text(encoding="utf-8").strip()
    parts = [base, _MODALITY_NOTES[modality]]
    if include_hidden_verdict:
        parts.append(HIDDEN_VERDICT_INSTRUCTION)
    return "\n\n".join(parts)


def _compose_user_payload(
    packet: Mapping[str, Any],
    *,
    stage: int,
    history_bars: int | None,
    trigger: Mapping[str, Any] | None,
    include_rich_context: bool,
    extra_sections: Sequence[tuple[str, str]],
) -> str:
    year = pd.Timestamp(packet["as_of"]).tz_convert("Europe/Istanbul").year
    symbol = str(packet["symbol"])
    main_tf = str(packet["main_tf"])
    mode = str(packet.get("research_mode") or "strict")
    kind = (
        "gerçek alarm tetikleyicisi eklendi"
        if trigger is not None
        else "tarihsel/isteğe bağlı kesit; gerçek alarm doğrulanmadı"
    )

    lines: list[str] = [
        f'<veri_paketi sembol="{symbol}" ana_tf="{main_tf}" kesit="{_time(packet["as_of"], year)}" yil="{year}" arastirma_modu="{mode}">',
        "<meta>",
        f"Durum: {kind}.",
        f"Kaynak: {packet['source']}; günlük: {packet['daily_source']}.",
        "İlk kova eksik, son seans mumu kısa olabilir; görünüm tüm geçmiş değil, süreklilik tam doğrulanmadı.",
    ]
    if history_bars is not None:
        lines.append(f"TF başına son {history_bars} kapanmış mum öncelikli; [E]=daha eski.")
    if packet.get("quality_notes"):
        lines.append("Veri uyarısı: " + "; ".join(_escape_data_text(str(x)) for x in packet["quality_notes"]) + ".")
    warnings: dict[str, list[str]] = {}
    for tf in TF_ORDER:
        for warning in packet["timeframes"][tf].get("chart_warnings", []):
            warnings.setdefault(str(warning), []).append(tf)
    for warning, timeframes in warnings.items():
        if warning == "Stabil direnç gösterilemedi: gerekli günlük veya saatlik kaynak yok":
            warning = "Stabil direnç: günlük/saatlik kaynak eksik; gösterilemedi"
        lines.append(f"Grafik uyarısı ({'/'.join(timeframes)}): {_escape_data_text(warning)}.")
    lines.append("</meta>")

    if trigger is not None:
        lines.extend(_render_trigger(trigger, year))

    lines.append("<grafikler>")
    for tf in TF_ORDER:
        row = packet["timeframes"][tf]
        tf_lines = _drawn_context(
            tf,
            row,
            year,
            compact_volume=(2 if stage >= 5 else 1 if stage >= 4 else 0),
            baseline=packet["timeframes"]["1h"],
            history_bars=history_bars,
        )
        if include_rich_context:
            rich = _rich_tf_lines(tf, row)
            if rich:
                # Insert right after closing price line (index 2) so the model
                # reads current state before raw historical events.
                insert_at = min(2, len(tf_lines))
                tf_lines[insert_at:insert_at] = rich
        lines.extend(tf_lines)
    lines.append("</grafikler>")

    row_main = packet["timeframes"][main_tf]
    lines.append(f'<replay tf="{main_tf}">')
    lines.extend(_replay(
        main_tf,
        row_main,
        year,
        focus_only=stage >= 1,
        last_only=stage >= 3,
        history_bars=history_bars,
    ))
    if (
        row_main.get("status") == "available"
        and row_main.get("chart_stabil_support") is not None
        and _same_level(row_main.get("stabil_daily_replay", {}).get("support_level"), row_main["chart_stabil_support"])
    ):
        lines.extend(_stabil(row_main["stabil_daily_replay"], year))
    lines.append("</replay>")

    research_lines = _research(packet, row_main, main_tf, abbreviated=stage >= 2)
    if research_lines:
        lines.append("<genel_arastirma>")
        lines.extend(research_lines)
        lines.append("</genel_arastirma>")

    for sec_name, sec_body in extra_sections:
        lines.append(f'<ek_baglam ad="{sec_name}">')
        lines.append(sec_body)
        lines.append("</ek_baglam>")

    lines.append("</veri_paketi>")
    return "\n".join(line for line in lines if line is not None).strip() + "\n"


def build_api_prompt(
    packet: Mapping[str, Any],
    *,
    modality: str = "text_only",
    trigger: Mapping[str, Any] | None = None,
    history_bars: int | None = 60,
    include_rich_context: bool = True,
    include_hidden_verdict: bool = False,
    extra_sections: Mapping[str, str] | Sequence[tuple[str, str]] | None = None,
    max_user_chars: int = DEFAULT_MAX_USER_CHARS,
) -> dict[str, Any]:
    """Sağlayıcıdan bağımsız, önbelleklenebilir `system` + `user` prompt paketi üret."""
    if not 500 <= max_user_chars <= HARD_MAX_USER_CHARS:
        raise ValueError(f"max_user_chars 500..{HARD_MAX_USER_CHARS} aralığında olmalı")
    if history_bars is not None and (not isinstance(history_bars, int) or isinstance(history_bars, bool) or history_bars < 1):
        raise ValueError("Geçmiş penceresi pozitif tamamlanmış mum sayısı olmalı")
    if trigger is not None and not isinstance(trigger, Mapping):
        raise ValueError("trigger bir eşleme (dict) veya None olmalı")

    system_text = _build_system_prompt(modality, include_hidden_verdict=include_hidden_verdict)
    extras = _normalize_extra_sections(extra_sections)

    user_text = _compose_user_payload(
        packet,
        stage=0,
        history_bars=history_bars,
        trigger=trigger,
        include_rich_context=include_rich_context,
        extra_sections=extras,
    )
    if _size(user_text) > max_user_chars:
        for stage in range(1, 6):
            candidate = _compose_user_payload(
                packet,
                stage=stage,
                history_bars=history_bars,
                trigger=trigger,
                include_rich_context=include_rich_context,
                extra_sections=extras,
            )
            if _size(candidate) < _size(user_text):
                user_text = candidate
            if _size(user_text) <= max_user_chars:
                break
    if _size(user_text) > max_user_chars:
        raise ValueError(
            f"API user prompt {_size(user_text)} karakter/birim; üst sınır {max_user_chars}. "
            "Veriler sessizce kesilmedi."
        )

    return {
        "prompt_version": API_PROMPT_VERSION,
        "modality": modality,
        "system": system_text,
        "system_sha256": hashlib.sha256(system_text.encode("utf-8")).hexdigest(),
        "user": user_text,
        "user_size": _size(user_text),
        "expected_sections": ("🧭 Mevcut durum", "🔎 Bağlam", "🕯️ Replay notu"),
        "metadata": {
            "symbol": packet.get("symbol"),
            "as_of": packet.get("as_of"),
            "main_tf": packet.get("main_tf"),
            "research_mode": packet.get("research_mode"),
            "has_trigger": trigger is not None,
            "include_rich_context": bool(include_rich_context),
            "include_hidden_verdict": bool(include_hidden_verdict),
            "extra_section_tags": [name for name, _ in extras],
        },
    }


def to_openai_messages(bundle: Mapping[str, Any]) -> list[dict[str, str]]:
    """OpenAI Chat Completions / Responses uyumlu mesaj dizisi."""
    return [
        {"role": "system", "content": str(bundle["system"])},
        {"role": "user", "content": str(bundle["user"])},
    ]


def to_anthropic_payload(
    bundle: Mapping[str, Any],
    *,
    cache_system: bool = True,
) -> dict[str, Any]:
    """Anthropic Messages API uyumlu gövde (isteğe bağlı prompt cache bloğuyla)."""
    system_block: dict[str, Any] = {"type": "text", "text": str(bundle["system"])}
    if cache_system:
        system_block["cache_control"] = {"type": "ephemeral"}
    return {
        "system": [system_block],
        "messages": [{"role": "user", "content": str(bundle["user"])}],
    }


def to_gemini_payload(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Google Gemini generateContent API uyumlu gövde."""
    return {
        "system_instruction": {"parts": [{"text": str(bundle["system"])}]},
        "contents": [{"role": "user", "parts": [{"text": str(bundle["user"])}]}],
    }
