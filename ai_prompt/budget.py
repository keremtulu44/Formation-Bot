"""Prompt karakter, UTF-16 ve tahminî token bütçesi tek-kaynak sistematiği.

Tüm prompt aileleri (`compact_paste`, `api_standard`, `api_extended`) için:
  - Ölçüm birimi: UTF-16 kod birimi (Telegram/JS/kopyala-yapıştır ile birebir)
    + Python Unicode karakter sayısı + Türkçe teknik metin kalibrasyonlu
    tahminî token sayısı (`ceil(chars / 3.4)` — sağlayıcı tokenizer'ı değildir).
  - Bölüm bazlı yumuşak hedefler (tanılama/telemetri için; sessiz kesme YOK).
  - Sistem, kullanıcı ve toplam için katı üst sınırlar (fail-closed).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Mapping

EST_CHARS_PER_TOKEN = 3.4


@dataclass(frozen=True, slots=True)
class PromptBudget:
    """Değişmez prompt bütçe profili (UTF-16 kod birimi cinsinden)."""

    name: str
    system_target: int
    system_hard_max: int
    user_target: int
    user_hard_max: int
    total_hard_max: int
    section_targets: Mapping[str, int]


COMPACT_PASTE_BUDGET = PromptBudget(
    name="compact_paste",
    system_target=0,
    system_hard_max=0,
    user_target=4000,
    user_hard_max=4500,
    total_hard_max=4500,
    section_targets={
        "talimat_kisa": 950,
        "grafik_ve_replay": 3550,
    },
)

API_STANDARD_BUDGET = PromptBudget(
    name="standard",
    system_target=3200,
    system_hard_max=4000,
    user_target=5200,
    user_hard_max=6000,
    total_hard_max=10000,
    section_targets={
        "meta": 420,
        "tetikleyici": 350,
        "grafikler": 2250,
        "replay": 1350,
        "genel_arastirma": 700,
        "kap_baglam": 1050,
        "kap_durum": 200,
        "ek_baglam_diger": 1000,
    },
)

API_EXTENDED_BUDGET = PromptBudget(
    name="extended",
    system_target=3800,
    system_hard_max=4500,
    user_target=7500,
    user_hard_max=9000,
    total_hard_max=13500,
    section_targets={
        "meta": 450,
        "tetikleyici": 450,
        "grafikler": 2600,
        "replay": 1600,
        "genel_arastirma": 800,
        "kap_baglam": 1100,
        "kap_durum": 250,
        "ek_baglam_diger": 2500,
    },
)

PROMPT_BUDGETS: dict[str, PromptBudget] = {
    "standard": API_STANDARD_BUDGET,
    "extended": API_EXTENDED_BUDGET,
}

_SINGLE_TAGS = ("meta", "tetikleyici", "grafikler", "replay", "genel_arastirma")
_TAG_PATTERNS: dict[str, re.Pattern[str]] = {
    tag: re.compile(rf"<{tag}\b[^>]*>.*?</{tag}>", re.DOTALL) for tag in _SINGLE_TAGS
}
_EK_BAGLAM_RE = re.compile(r'<ek_baglam\s+ad="([^"]+)"\s*>.*?</ek_baglam>', re.DOTALL)


def resolve_budget(budget: str | PromptBudget) -> PromptBudget:
    if isinstance(budget, PromptBudget):
        return budget
    key = str(budget or "standard").strip().lower()
    if key not in PROMPT_BUDGETS:
        raise ValueError(
            f"Bilinmeyen prompt bütçe profili: {budget!r} "
            f"(desteklenen: {', '.join(sorted(PROMPT_BUDGETS))})"
        )
    return PROMPT_BUDGETS[key]


def utf16_len(text: str) -> int:
    """UTF-16 kod birimi uzunluğu (Telegram/JS sayaçlarıyla birebir; emoji=2 birim)."""
    return len(str(text).encode("utf-16-le")) // 2


def estimate_tokens(text: str) -> int:
    """Türkçe teknik metin için kaba tahminî token sayısı (sağlayıcı tokenizer'ı değildir)."""
    n = len(str(text))
    return 0 if n == 0 else math.ceil(n / EST_CHARS_PER_TOKEN)


def measure_text(text: str) -> dict[str, int]:
    s = str(text)
    return {
        "chars": len(s),
        "utf16": utf16_len(s),
        "est_tokens": estimate_tokens(s),
    }


def measure_user_sections(user_text: str) -> dict[str, int]:
    """`<veri_paketi>` içindeki her XML bölümünün UTF-16 uzunluğunu ölçer."""
    text = str(user_text)
    counts: dict[str, int] = {tag: 0 for tag in _SINGLE_TAGS}
    counts["kap_baglam"] = 0
    counts["kap_durum"] = 0
    counts["ek_baglam_diger"] = 0

    accounted = 0
    for tag, pattern in _TAG_PATTERNS.items():
        match = pattern.search(text)
        if match:
            size = utf16_len(match.group(0))
            counts[tag] = size
            accounted += size

    for match in _EK_BAGLAM_RE.finditer(text):
        ad = match.group(1).strip().lower()
        size = utf16_len(match.group(0))
        accounted += size
        if ad == "kap_baglam":
            counts["kap_baglam"] += size
        elif ad == "kap_durum":
            counts["kap_durum"] += size
        else:
            counts["ek_baglam_diger"] += size

    total = utf16_len(text)
    counts["xml_overhead"] = max(0, total - accounted)
    return counts


def evaluate_api_budget(
    system_text: str,
    user_text: str,
    *,
    budget: PromptBudget = API_STANDARD_BUDGET,
    effective_user_max: int | None = None,
    compaction_stage: int = 0,
) -> dict[str, Any]:
    """API prompt paketi için eksiksiz bütçe, doluluk ve bölüm telemetrisi üretir."""
    sys_m = measure_text(system_text)
    usr_m = measure_text(user_text)
    user_cap = int(effective_user_max) if effective_user_max is not None else budget.user_hard_max
    extra_user = max(0, user_cap - budget.user_hard_max)
    total_cap = budget.total_hard_max + extra_user
    total_chars = sys_m["chars"] + usr_m["chars"]
    total_u16 = sys_m["utf16"] + usr_m["utf16"]
    total_tok = sys_m["est_tokens"] + usr_m["est_tokens"]

    sections = measure_user_sections(user_text)
    over_target = [
        sec for sec, limit in budget.section_targets.items()
        if sections.get(sec, 0) > limit
    ]

    sys_ok = budget.system_hard_max <= 0 or sys_m["utf16"] <= budget.system_hard_max
    usr_ok = usr_m["utf16"] <= user_cap
    tot_ok = total_u16 <= total_cap
    sys_target_ok = budget.system_target <= 0 or sys_m["utf16"] <= budget.system_target
    usr_target_ok = usr_m["utf16"] <= min(budget.user_target, user_cap)

    return {
        "profile": budget.name,
        "unit": "utf16",
        "compaction_stage": int(compaction_stage),
        "system": {
            **sys_m,
            "target": budget.system_target,
            "hard_max": budget.system_hard_max,
            "utilization_pct": round(sys_m["utf16"] / budget.system_hard_max * 100, 1)
            if budget.system_hard_max > 0 else 0.0,
        },
        "user": {
            **usr_m,
            "target": min(budget.user_target, user_cap),
            "hard_max": user_cap,
            "utilization_pct": round(usr_m["utf16"] / user_cap * 100, 1) if user_cap > 0 else 0.0,
        },
        "total": {
            "chars": total_chars,
            "utf16": total_u16,
            "est_tokens": total_tok,
            "hard_max": total_cap,
            "utilization_pct": round(total_u16 / total_cap * 100, 1) if total_cap > 0 else 0.0,
        },
        "sections": sections,
        "over_target_sections": over_target,
        "within_target": bool(sys_target_ok and usr_target_ok),
        "within_hard_cap": bool(sys_ok and usr_ok and tot_ok),
    }
