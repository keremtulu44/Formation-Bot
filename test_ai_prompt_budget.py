"""Tests for the unified AI prompt budget system (`ai_prompt.budget` + `api_messages`)."""
from __future__ import annotations

import copy

import pytest

from ai_prompt import (
    API_EXTENDED_BUDGET,
    API_STANDARD_BUDGET,
    COMPACT_PASTE_BUDGET,
    PromptBudget,
    build_api_prompt,
    build_from_local_cache,
    estimate_tokens,
    evaluate_api_budget,
    measure_text,
    measure_user_sections,
    render_compact_prompt,
    resolve_budget,
    utf16_len,
)
from ai_prompt.api_messages import _build_system_prompt
from ai_prompt.compact import MAXIMUM as COMPACT_MAX, TARGET as COMPACT_TARGET
from ai_prompt.verdict import HIDDEN_VERDICT_INSTRUCTION


def _sample_packet() -> dict:
    return build_from_local_cache("BIMAS", as_of="2026-09-25 18:05+03:00", main_tf="4h")


def _worst_kap_payload() -> dict:
    return {
        "durum": "var",
        "baglam": {
            "konu": "satis_sozlesmesi",
            "yayin_zamani": "2026-09-25T05:15:00Z",
            "seans_durumu": "seans_oncesi",
            "olay": (
                "Yüksek tutarlı uzun vadeli havalimanı işletme ve yeni iş sözleşmesi imzalandı "
                "(tutar 185 mn EUR); teslimatlar 2026-2028 dönemine yayılacak ve döviz bazlı "
                "gelir katkısı beklenmektedir."
            ),
            "onemi": "Sözleşme tutarı / son 12 ay konsolide satış geliri oranı %18,4; kur tahmini yapılmadı.",
            "mali_tablo": {
                "donem_sonu": "2026-06-30",
                "yayin_zamani": "2026-08-14T16:30:00Z",
                "kaynak": "KAP resmi konsolide finansal rapor",
            },
            "revizyon": {"onceki_id": 123456},
            "kaynak": "kap_resmi",
        },
        "sirket_profili": {
            "aliskanlik": "seyrek",
            "son_30_gun_bildirim_sayisi": 1,
        },
        "bekleyen_bildirim": {
            "yayin_zamani": "2026-09-25T14:40:00Z",
        },
    }


def _worst_trigger() -> dict:
    return {
        "kind": "FORMASYON_KIRILIM",
        "channel": "telegram_main",
        "timeframe": "4h",
        "state": "KIRILIM_TEYITLI",
        "pattern_name": "Simetrik Üçgen",
        "direction": "yukarı",
        "bar_open": "2026-09-25T13:00:00+03:00",
        "bar_close": "2026-09-25T17:00:00+03:00",
        "summary": "4H üst bant üzerinde hacimli kapanış ile kırılım teyidi alındı.",
        "reasons": ["Üst bant üstü kapanış", "RVOL > 1,5x", "Dış yapı uyumlu"],
    }


def test_budget_primitives_and_single_source_constants():
    assert COMPACT_TARGET == COMPACT_PASTE_BUDGET.user_target == 4000
    assert COMPACT_MAX == COMPACT_PASTE_BUDGET.user_hard_max == 4500

    # Emoji counts as 2 UTF-16 code units; Turkish BMP chars count as 1.
    assert utf16_len("🧭") == 2
    assert len("🧭") == 1
    assert utf16_len("ŞĞÜÖÇİşığüöç") == 12
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 34) == 10

    m = measure_text("🧭 Mevcut durum")
    assert m["chars"] == 14
    assert m["utf16"] == 15
    assert m["est_tokens"] == estimate_tokens("🧭 Mevcut durum")

    assert resolve_budget("standard") is API_STANDARD_BUDGET
    assert resolve_budget("extended") is API_EXTENDED_BUDGET
    with pytest.raises(ValueError, match="Bilinmeyen prompt bütçe profili"):
        resolve_budget("nonexistent")


def test_all_system_variants_fit_standard_target_and_preserve_core_rules():
    variants = [
        ("text_only", False, False),
        ("text_only", True, False),
        ("text_only", True, True),
        ("multimodal", True, True),
    ]
    for modality, verdict, kap_rules in variants:
        sys_text = _build_system_prompt(
            modality,
            include_hidden_verdict=verdict,
            include_kap_rules=kap_rules,
        )
        u16 = utf16_len(sys_text)
        assert u16 <= API_STANDARD_BUDGET.system_target, (
            f"System variant {(modality, verdict, kap_rules)} is {u16} > target {API_STANDARD_BUDGET.system_target}"
        )
        assert u16 <= API_STANDARD_BUDGET.system_hard_max

        # Essential epistemic & formatting rules must never be lost in tightening.
        assert "🧭 Mevcut durum" in sys_text
        assert "🔎 Bağlam" in sys_text
        assert "🕯️ Replay notu" in sys_text
        assert "120–180 kelime" in sys_text
        assert "CHoCH" in sys_text and "BOS" in sys_text
        assert "kırılım yönü" in sys_text.lower()
        assert "<veri_paketi>" in sys_text
        if kap_rules:
            assert "seyrek" in sys_text and "normal" in sys_text and "sık" in sys_text
            assert "seans öncesi" in sys_text
            assert "ciro" in sys_text.lower()
        if verdict:
            assert "[AI_SONUC" in sys_text
            assert "yayin_degeri=gonder" in sys_text
            assert HIDDEN_VERDICT_INSTRUCTION in sys_text


def test_api_budget_telemetry_and_exact_section_accounting():
    packet = _sample_packet()
    bundle = build_api_prompt(
        packet,
        include_hidden_verdict=True,
        kap_context=_worst_kap_payload(),
        trigger=_worst_trigger(),
    )
    b = bundle["budget"]
    assert b["profile"] == "standard"
    assert b["unit"] == "utf16"
    assert b["within_hard_cap"] is True
    assert b["system"]["utf16"] <= API_STANDARD_BUDGET.system_target
    assert b["user"]["utf16"] == bundle["user_size"]
    assert b["total"]["utf16"] == b["system"]["utf16"] + b["user"]["utf16"]
    assert b["total"]["utf16"] <= API_STANDARD_BUDGET.total_hard_max

    # Exact XML section sum accounting matches user UTF-16 length.
    sections = b["sections"]
    assert sum(sections.values()) == bundle["user_size"]
    assert sections["meta"] > 0
    assert sections["tetikleyici"] > 0
    assert sections["grafikler"] > 0
    assert sections["replay"] > 0
    assert sections["kap_baglam"] > 0
    assert sections["kap_durum"] == 0
    assert sections["ek_baglam_diger"] == 0
    assert measure_user_sections(bundle["user"]) == sections


def test_stabil_deduplication_and_inline_distance():
    packet = _sample_packet()
    bundle = build_api_prompt(packet, include_rich_context=True)
    user = bundle["user"]

    # Inline distance must be merged into Stabil line (no standalone distance line).
    assert "Stabil destek uzaklığı:" not in user
    assert "Stabil direnç uzaklığı:" not in user

    # Check whether 4h and 1d have identical Stabil roles in packet; if so, emitted once.
    r4 = (packet["timeframes"]["4h"].get("stabil") or {}).get("roles")
    r1 = (packet["timeframes"]["1d"].get("stabil") or {}).get("roles")
    if r4 and r4 == r1:
        assert user.count("Stabil roller:") == 1


def test_stage_6_compaction_preserves_kap_and_trigger_under_tight_cap():
    from ai_prompt.api_messages import _compose_user_payload
    from ai_prompt.kap_bridge import format_kap_for_prompt

    packet = _sample_packet()
    kap = _worst_kap_payload()
    trig = _worst_trigger()
    kap_info = format_kap_for_prompt(kap, as_of=packet["as_of"])
    extras = [(kap_info["section_name"], kap_info["section_text"])]

    stage5_len = utf16_len(
        _compose_user_payload(
            packet,
            stage=5,
            history_bars=60,
            trigger=trig,
            include_rich_context=True,
            extra_sections=extras,
        )
    )
    stage6_len = utf16_len(
        _compose_user_payload(
            packet,
            stage=6,
            history_bars=60,
            trigger=trig,
            include_rich_context=True,
            extra_sections=extras,
        )
    )
    assert stage6_len < stage5_len

    # Set cap right between stage 6 and stage 5 so stage 6 is explicitly exercised.
    compacted = build_api_prompt(
        packet,
        include_hidden_verdict=True,
        kap_context=kap,
        trigger=trig,
        max_user_chars=stage6_len,
    )
    assert compacted["user_size"] == stage6_len
    assert compacted["metadata"]["compaction_stage"] == 6
    assert compacted["budget"]["compaction_stage"] == 6
    assert "Durum: dış yapı=" in compacted["user"]
    # Trigger & KAP news must NEVER be silently truncated.
    assert "<tetikleyici>" in compacted["user"]
    assert "FORMASYON_KIRILIM" in compacted["user"]
    assert '<ek_baglam ad="kap_baglam">' in compacted["user"]
    assert "185 mn EUR" in compacted["user"]


def test_fail_closed_guards_for_system_user_and_total_caps():
    packet = _sample_packet()

    # 1) System hard max breach -> fail closed.
    tiny_sys_budget = PromptBudget(
        name="tiny_sys",
        system_target=1000,
        system_hard_max=1500,
        user_target=5000,
        user_hard_max=6000,
        total_hard_max=7500,
        section_targets={},
    )
    with pytest.raises(ValueError, match="API system prompt"):
        build_api_prompt(packet, budget=tiny_sys_budget)

    # 2) Combined total hard max breach -> fail closed even if system & user each pass.
    tight_total_budget = PromptBudget(
        name="tight_total",
        system_target=3500,
        system_hard_max=4000,
        user_target=5000,
        user_hard_max=6000,
        total_hard_max=4000,
        section_targets={},
    )
    with pytest.raises(ValueError, match="API toplam prompt bütçesi aşıldı"):
        build_api_prompt(packet, budget=tight_total_budget)

    # 3) User hard max impossible cap -> fail closed without silent truncation.
    with pytest.raises(ValueError, match="sessizce kesilmedi"):
        build_api_prompt(packet, max_user_chars=600)


def test_extended_budget_allows_large_extra_context():
    packet = _sample_packet()
    big_extra = "Ek teknik/makro not satırı. " * 120  # ~3,360 chars
    # Exceeds standard 6,000 user cap -> fails under standard.
    with pytest.raises(ValueError, match="sessizce kesilmedi"):
        build_api_prompt(
            packet,
            kap_context=_worst_kap_payload(),
            extra_sections={"makro": big_extra},
            budget="standard",
        )
    # Succeeds cleanly under extended 9,000 user cap.
    ext = build_api_prompt(
        packet,
        kap_context=_worst_kap_payload(),
        extra_sections={"makro": big_extra},
        budget="extended",
    )
    assert ext["budget"]["profile"] == "extended"
    assert ext["budget"]["within_hard_cap"] is True
    assert ext["budget"]["sections"]["ek_baglam_diger"] > 3000
    assert ext["user_size"] <= API_EXTENDED_BUDGET.user_hard_max


def test_evaluate_api_budget_explicit_max_user_chars_respects_extra_allowance():
    rep = evaluate_api_budget(
        "s" * 3000,
        "<veri_paketi><meta>ok</meta></veri_paketi>" + "u" * 6500,
        budget=API_STANDARD_BUDGET,
        effective_user_max=7000,
    )
    assert rep["user"]["hard_max"] == 7000
    assert rep["total"]["hard_max"] == 11000
    assert rep["within_hard_cap"] is True


def test_compact_prompt_contract_preserved():
    packet = copy.deepcopy(_sample_packet())
    text = render_compact_prompt(packet)
    size = utf16_len(text)
    assert COMPACT_PASTE_BUDGET.user_target < size <= COMPACT_PASTE_BUDGET.user_hard_max


def test_compact_stage_6_handles_heaviest_retrospective_tavhl_without_data_loss():
    tavhl = build_from_local_cache(
        "TAVHL",
        as_of="2026-09-25 18:05+03:00",
        main_tf="4h",
        research_mode="retrospective",
    )
    text = render_compact_prompt(tavhl)
    assert utf16_len(text) <= COMPACT_PASTE_BUDGET.user_hard_max
    # Breakout directions, Stabil support level, and replay zones stay intact.
    assert "kırılım ↑" in text
    assert "243,20" in text
    assert "4H REPLAY" in text
