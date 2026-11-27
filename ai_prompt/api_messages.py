"""AI API sağlayıcıları için önbelleklenebilir system/user prompt derleyicisi.

Bu modül tamamen yerel ve ağsızdır: HTTP isteği atmaz, API anahtarı okumaz,
SDK bağımlılığı eklemez ve canlı motor/alarm state'ini değiştirmez.
Üretilen `system` metni aynı modalite ve kural kombinasyonu için semboller
arası bayt-birebir sabittir (OpenAI / Anthropic / Gemini prompt caching uyumlu);
dinamik grafik, replay, araştırma ve harici bağlam verisi XML sınırlarıyla
ayrılmış `user` mesajına konur ve tek-kaynak `PromptBudget` sistematiğiyle
ölçülüp denetlenir.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

import pandas as pd

from notification_context import _VOLUME_STATE_LABELS

from .budget import (
    API_STANDARD_BUDGET,
    PromptBudget,
    evaluate_api_budget,
    resolve_budget,
    utf16_len,
)
from .builder import ROOT, STABIL_LABELS, TF_ORDER, _label, _num, _same_level
from .compact import _drawn_context, _replay, _research, _stabil, _time
from .kap_bridge import KAP_SYNTHESIS_INSTRUCTION, format_kap_for_prompt
from .verdict import HIDDEN_VERDICT_INSTRUCTION

API_PROMPT_VERSION = "api-v1"
DEFAULT_MAX_USER_CHARS = API_STANDARD_BUDGET.user_hard_max
HARD_MAX_USER_CHARS = 12000

_MODALITY_NOTES = {
    "text_only": (
        "MODALİTE: Grafik görseli ekli değil; yalnız `<veri_paketi>` kapalı-bar verisine dayan."
    ),
    "multimodal": (
        "MODALİTE: Grafik görselleri ekli; çizgileri `<veri_paketi>` ile birlikte oku, "
        "çelişkide kapalı-bar verisini esas al, etiketsiz sayı tahmin etme."
    ),
}

_SAFE_TAG_RE = re.compile(r"^[a-z0-9_]{1,32}$")
_RESERVED_TAG_RE = re.compile(
    r"<\s*(/?)\s*(ek_baglam|veri_paketi|tetikleyici|grafikler|replay|genel_arastirma|meta)\b([^>]*)>",
    re.IGNORECASE,
)


def _escape_data_text(text: str) -> str:
    """Harici metinlerdeki açılış ve kapanış XML etiketlerini etkisizleştir (veri sınırı koruması)."""
    return _RESERVED_TAG_RE.sub(lambda m: f"&lt;{m.group(1)}{m.group(2)}{m.group(3)}&gt;", str(text))


def _pct_vs(close: Any, level: Any) -> str:
    c, lv = _num(close), _num(level)
    if c is None or lv is None or lv <= 0:
        return ""
    pct = (c - lv) / lv * 100.0
    sign = "+" if pct >= 0 else "−"
    return f" ({sign}%{abs(pct):.1f})".replace(".", ",")


def _stabil_roles_text(row: Mapping[str, Any], *, include_h4: bool = True) -> str | None:
    stabil = row.get("stabil") or {}
    if stabil.get("status") != "available":
        return None
    roles = stabil.get("roles") or {}
    role_parts: list[str] = []
    keys = (("weekly", "haftalık"), ("daily", "günlük"), ("h4", "4s")) if include_h4 else (
        ("weekly", "haftalık"),
        ("daily", "günlük"),
    )
    for rkey, rlabel in keys:
        info = roles.get(rkey)
        if isinstance(info, Mapping) and info.get("state"):
            state_tr = _label(STABIL_LABELS, str(info["state"]))
            role_parts.append(f"{rlabel}={state_tr}")
    return ", ".join(role_parts) if role_parts else None


def _attach_stabil_distances(tf_lines: list[str], row: Mapping[str, Any]) -> None:
    """Mevcut `Stabil destek:` / `Stabil direnç:` satırlarına yüzde uzaklığı satır içi ekler."""
    close = row.get("last_close")
    sup_pct = _pct_vs(close, row.get("chart_stabil_support"))
    res_pct = _pct_vs(close, row.get("chart_stabil_resistance"))
    if not sup_pct and not res_pct:
        return
    for idx, line in enumerate(tf_lines):
        if sup_pct and line.startswith("Stabil destek: ") and line.endswith("."):
            tf_lines[idx] = f"{line[:-1]}{sup_pct}."
        elif res_pct and line.startswith("Stabil direnç: ") and line.endswith("."):
            tf_lines[idx] = f"{line[:-1]}{res_pct}."


def _rich_tf_lines(
    tf: str,
    row: Mapping[str, Any],
    *,
    compact: bool = False,
    seen_stabil_roles: set[str] | None = None,
) -> list[str]:
    """Packet içinde zaten bulunan ama çıplak grafik özetinde saklı kalan motor durumları."""
    if row.get("status") != "available":
        return []
    out: list[str] = []

    ext_state: str | None = None
    ms = row.get("market_structure") or {}
    if ms.get("status") == "available":
        ext = (ms.get("scopes") or {}).get("dış")
        if isinstance(ext, Mapping) and ext.get("state"):
            ext_state = str(ext["state"])

    vol_text: str | None = None
    vol = row.get("volume") or {}
    if vol.get("status") == "available":
        state = str(vol.get("state") or "")
        if state == "PARTICIPATION_PENDING":
            vol_text = "hazır değil" if compact else "hazır değil (sonuç çıkarılmaz)"
        elif state == "PARTICIPATION_VOLUME_UNAVAILABLE":
            vol_text = "veri yok" if compact else "hacim verisi yok (sonuç çıkarılmaz)"
        elif state == "PARTICIPATION_NEUTRAL":
            vol_text = "nötr"
        elif state:
            vol_text = _VOLUME_STATE_LABELS.get(state, state)
    elif vol.get("status"):
        vol_text = str(vol["status"])

    if compact:
        parts = []
        if ext_state:
            parts.append(f"dış yapı={ext_state}")
        if vol_text:
            parts.append(f"hacim={vol_text}")
        if parts:
            out.append("Durum: " + "; ".join(parts) + ".")
    else:
        if ext_state:
            out.append(f"Dış yapı durumu: {ext_state}.")
        if vol_text:
            out.append(f"Hacim motoru: {vol_text}.")

    if tf == "4h":
        roles_str = _stabil_roles_text(row, include_h4=True)
        if roles_str:
            out.append(f"Stabil roller: {roles_str}.")
            if seen_stabil_roles is not None:
                seen_stabil_roles.add(roles_str)
                wd_str = _stabil_roles_text(row, include_h4=False)
                if wd_str:
                    seen_stabil_roles.add(wd_str)
    elif tf == "1d":
        # 4H zaten güncel 4s rolünü içerir; 1D bir önceki günlük kapanıştan
        # hesaplandığı için eski 4s rolünü tekrarlayıp çelişki üretme.
        has_4h_roles = bool(seen_stabil_roles)
        roles_str = _stabil_roles_text(row, include_h4=not has_4h_roles)
        if roles_str and (seen_stabil_roles is None or roles_str not in seen_stabil_roles):
            out.append(f"Stabil roller: {roles_str}.")
            if seen_stabil_roles is not None:
                seen_stabil_roles.add(roles_str)
    return out


def _render_trigger(trigger: Mapping[str, Any], year: int) -> list[str]:
    lines = ["<tetikleyici>"]
    for key in (
        "kind",
        "channel",
        "timeframe",
        "state",
        "pattern_name",
        "direction",
        "bar_open",
        "bar_close",
        "summary",
    ):
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
            raise ValueError(
                f"Geçersiz ek bölüm adı: {raw_name!r} (yalnız [a-z0-9_], en fazla 32 karakter)"
            )
        body = str(raw_body or "").strip()
        if body:
            out.append((name, _escape_data_text(body)))
    return out


def _build_system_prompt(
    modality: str,
    *,
    include_hidden_verdict: bool = False,
    include_kap_rules: bool = False,
) -> str:
    if modality not in _MODALITY_NOTES:
        raise ValueError(f"Desteklenmeyen modalite: {modality!r} ('text_only' veya 'multimodal' olmalı)")
    base = (ROOT / "talimat_api.txt").read_text(encoding="utf-8").strip()
    parts = [base, _MODALITY_NOTES[modality]]
    if include_kap_rules:
        parts.append(KAP_SYNTHESIS_INSTRUCTION)
    if include_hidden_verdict:
        parts.append(HIDDEN_VERDICT_INSTRUCTION)
    return "\n\n".join(parts)


def _strip_leading_blank(lines: list[str]) -> list[str]:
    if lines and isinstance(lines[0], str) and lines[0].startswith("\n"):
        lines = [lines[0].lstrip("\n"), *lines[1:]]
    return lines


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
        "İlk kova eksik, son mum kısa olabilir; tüm geçmiş değil, süreklilik tam doğrulanmadı.",
    ]
    if history_bars is not None:
        lines.append(f"TF başına son {history_bars} kapanmış mum öncelikli; [E]=daha eski.")
    if packet.get("quality_notes"):
        lines.append(
            "Veri uyarısı: " + "; ".join(_escape_data_text(str(x)) for x in packet["quality_notes"]) + "."
        )
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
    seen_stabil_roles: set[str] = set()
    for tf_idx, tf in enumerate(TF_ORDER):
        row = packet["timeframes"][tf]
        tf_lines = _drawn_context(
            tf,
            row,
            year,
            compact_volume=(2 if stage >= 5 else 1 if stage >= 4 else 0),
            baseline=packet["timeframes"]["1h"],
            history_bars=history_bars,
        )
        if tf_idx == 0:
            tf_lines = _strip_leading_blank(tf_lines)
        if include_rich_context:
            if tf in {"4h", "1d"} and row.get("status") == "available":
                _attach_stabil_distances(tf_lines, row)
            rich = _rich_tf_lines(
                tf,
                row,
                compact=stage >= 6,
                seen_stabil_roles=seen_stabil_roles,
            )
            if rich:
                insert_at = min(2, len(tf_lines))
                tf_lines[insert_at:insert_at] = rich
        lines.extend(tf_lines)
    lines.append("</grafikler>")

    row_main = packet["timeframes"][main_tf]
    lines.append(f'<replay tf="{main_tf}">')
    replay_lines = _strip_leading_blank(
        _replay(
            main_tf,
            row_main,
            year,
            focus_only=stage >= 1,
            last_only=stage >= 3,
            history_bars=history_bars,
            compact_header=stage >= 6,
        )
    )
    lines.extend(replay_lines)
    if (
        row_main.get("status") == "available"
        and row_main.get("chart_stabil_support") is not None
        and _same_level(
            row_main.get("stabil_daily_replay", {}).get("support_level"),
            row_main["chart_stabil_support"],
        )
    ):
        lines.extend(_stabil(row_main["stabil_daily_replay"], year, compact_note=stage >= 6))
    lines.append("</replay>")

    research_lines = _strip_leading_blank(_research(packet, row_main, main_tf, abbreviated=stage >= 2))
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
    kap_context: Mapping[str, Any] | None = None,
    kap_max_age_gun: int = 7,
    extra_sections: Mapping[str, str] | Sequence[tuple[str, str]] | None = None,
    budget: str | PromptBudget = "standard",
    max_user_chars: int | None = None,
) -> dict[str, Any]:
    """Sağlayıcıdan bağımsız, önbelleklenebilir ve bütçe-denetimli `system` + `user` paketi üret."""
    budget_profile = resolve_budget(budget)
    effective_user_max = (
        int(max_user_chars) if max_user_chars is not None else budget_profile.user_hard_max
    )
    if not 500 <= effective_user_max <= HARD_MAX_USER_CHARS:
        raise ValueError(f"max_user_chars 500..{HARD_MAX_USER_CHARS} aralığında olmalı")
    if history_bars is not None and (
        not isinstance(history_bars, int) or isinstance(history_bars, bool) or history_bars < 1
    ):
        raise ValueError("Geçmiş penceresi pozitif tamamlanmış mum sayısı olmalı")
    if trigger is not None and not isinstance(trigger, Mapping):
        raise ValueError("trigger bir eşleme (dict) veya None olmalı")

    kap_info = format_kap_for_prompt(
        kap_context,
        as_of=packet.get("as_of"),
        max_age_gun=kap_max_age_gun,
    )
    system_text = _build_system_prompt(
        modality,
        include_hidden_verdict=include_hidden_verdict,
        include_kap_rules=bool(kap_info["include_kap_rules"]),
    )
    if budget_profile.system_hard_max > 0 and utf16_len(system_text) > budget_profile.system_hard_max:
        raise ValueError(
            f"API system prompt {utf16_len(system_text)} UTF-16 birim; "
            f"üst sınır {budget_profile.system_hard_max} ({budget_profile.name})."
        )

    extras = _normalize_extra_sections(extra_sections)
    if kap_info["section_name"] and kap_info["section_text"]:
        kap_pair = (kap_info["section_name"], _escape_data_text(kap_info["section_text"]))
        extras = [kap_pair, *[item for item in extras if item[0] != kap_pair[0]]]

    used_stage = 0
    user_text = _compose_user_payload(
        packet,
        stage=0,
        history_bars=history_bars,
        trigger=trigger,
        include_rich_context=include_rich_context,
        extra_sections=extras,
    )
    if utf16_len(user_text) > effective_user_max:
        for stage in range(1, 7):
            candidate = _compose_user_payload(
                packet,
                stage=stage,
                history_bars=history_bars,
                trigger=trigger,
                include_rich_context=include_rich_context,
                extra_sections=extras,
            )
            if utf16_len(candidate) < utf16_len(user_text):
                user_text = candidate
                used_stage = stage
            if utf16_len(user_text) <= effective_user_max:
                break
    if utf16_len(user_text) > effective_user_max:
        raise ValueError(
            f"API user prompt {utf16_len(user_text)} karakter/birim; üst sınır {effective_user_max}. "
            "Veriler sessizce kesilmedi."
        )

    budget_report = evaluate_api_budget(
        system_text,
        user_text,
        budget=budget_profile,
        effective_user_max=effective_user_max,
        compaction_stage=used_stage,
    )
    if not budget_report["within_hard_cap"]:
        raise ValueError(
            f"API toplam prompt bütçesi aşıldı ({budget_report['total']['utf16']} > "
            f"{budget_report['total']['hard_max']})."
        )

    return {
        "prompt_version": API_PROMPT_VERSION,
        "modality": modality,
        "system": system_text,
        "system_sha256": hashlib.sha256(system_text.encode("utf-8")).hexdigest(),
        "user": user_text,
        "user_size": utf16_len(user_text),
        "budget": budget_report,
        "expected_sections": ("🧭 Mevcut durum", "🔎 Bağlam", "🕯️ Replay notu"),
        "metadata": {
            "symbol": packet.get("symbol"),
            "as_of": packet.get("as_of"),
            "main_tf": packet.get("main_tf"),
            "research_mode": packet.get("research_mode"),
            "has_trigger": trigger is not None,
            "include_rich_context": bool(include_rich_context),
            "include_hidden_verdict": bool(include_hidden_verdict),
            "budget_profile": budget_profile.name,
            "compaction_stage": used_stage,
            "kap_status": kap_info["status"],
            "kap_rules_included": bool(kap_info["include_kap_rules"]),
            "kap_summary": kap_info["meta_summary"],
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
