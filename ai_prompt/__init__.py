"""Yerel, izole grafik-prompt derleme aracı; ağ/Telegram entegrasyonu içermez."""
from .api_messages import (
    API_PROMPT_VERSION,
    build_api_prompt,
    to_anthropic_payload,
    to_gemini_payload,
    to_openai_messages,
)
from .builder import build_from_frames, build_from_local_cache, render_prompt
from .commentary import format_ai_commentary, validate_ai_commentary
from .compact import render_compact_prompt
from .shadow_store import (
    AI_YORUM_TEST_TABLE,
    AI_YORUM_TEST_VIEW,
    DEFAULT_LOCAL_SHADOW_FILE,
    build_shadow_record,
    evaluate_shadow_outcome,
    fetch_shadow_summary,
    load_local_shadow_records,
    make_shadow_key,
    save_local_shadow_records,
    save_shadow_record,
    write_shadow_records_to_supabase,
)
from .verdict import (
    HIDDEN_VERDICT_INSTRUCTION,
    HIDDEN_VERDICT_TAG,
    VERDICT_FIELDS,
    VERDICT_SCHEMA,
    append_hidden_verdict_instruction,
    parse_ai_response,
    parse_verdict_block,
    strip_hidden_verdict,
)

__all__ = [
    "AI_YORUM_TEST_TABLE",
    "AI_YORUM_TEST_VIEW",
    "API_PROMPT_VERSION",
    "DEFAULT_LOCAL_SHADOW_FILE",
    "HIDDEN_VERDICT_INSTRUCTION",
    "HIDDEN_VERDICT_TAG",
    "VERDICT_FIELDS",
    "VERDICT_SCHEMA",
    "append_hidden_verdict_instruction",
    "build_api_prompt",
    "build_from_frames",
    "build_from_local_cache",
    "build_shadow_record",
    "evaluate_shadow_outcome",
    "fetch_shadow_summary",
    "format_ai_commentary",
    "load_local_shadow_records",
    "make_shadow_key",
    "parse_ai_response",
    "parse_verdict_block",
    "render_compact_prompt",
    "render_prompt",
    "save_local_shadow_records",
    "save_shadow_record",
    "strip_hidden_verdict",
    "to_anthropic_payload",
    "to_gemini_payload",
    "to_openai_messages",
    "validate_ai_commentary",
    "write_shadow_records_to_supabase",
]
