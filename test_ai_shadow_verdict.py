"""Tests for hidden `[AI_SONUC ...]` verdict stripping, parsing, shadow store, and forward outcome."""
from __future__ import annotations

import pandas as pd
import pytest

import config
from ai_prompt import (
    AI_YORUM_TEST_TABLE,
    AI_YORUM_TEST_VIEW,
    append_hidden_verdict_instruction,
    build_api_prompt,
    build_from_local_cache,
    build_shadow_record,
    evaluate_shadow_outcome,
    fetch_shadow_summary,
    load_local_shadow_records,
    parse_ai_response,
    save_shadow_record,
    strip_hidden_verdict,
)
from supabase_store import SupabaseStore
from test_supabase_store import FakeResponse, FakeSession

CUT = "2026-09-25T18:30:00+03:00"


@pytest.fixture(scope="module")
def bimas():
    return build_from_local_cache("BIMAS", as_of=CUT, research_mode="strict")


def _sample_body(extra_tail: str = "") -> str:
    p1 = " ".join(["görüş"] * 40)
    p2 = " ".join(["karşı"] * 40)
    p3 = " ".join(["temas"] * 40)
    return (
        f"🧭 Mevcut durum\n{p1}\n\n"
        f"🔎 Bağlam\n{p2}\n\n"
        f"🕯️ Replay notu\n{p3}"
        + (f"\n\n{extra_tail}" if extra_tail else "")
    )


def test_hidden_verdict_stripped_normalized_and_never_leaks():
    raw = _sample_body(
        "[AI_SONUC egilim=yukarı | guc=orta | mtf_uyum=çelişkili | risk=yüksek | yayin_degeri=gönder]"
    )
    parsed = parse_ai_response(raw, require_verdict=True)
    assert parsed["verdict_valid"] is True
    assert parsed["verdict"] == {
        "egilim": "yukari",
        "guc": "orta",
        "mtf_uyum": "celiskili",
        "risk": "yuksek",
        "yayin_degeri": "gonder",
    }
    assert parsed["ok_for_telegram"] is True
    assert parsed["ok_for_shadow_log"] is True
    assert "AI_SONUC" not in parsed["visible_text"]
    assert "yayin_degeri" not in parsed["visible_text"]
    assert parsed["visible_text"].startswith("🧭 Mevcut durum\n")


def test_malformed_or_fenced_hidden_verdict_is_still_stripped_from_visible_text():
    raw = _sample_body("```text\n[SONUÇ egilim=uydurma | guc=orta]\n```")
    cleaned, raw_block = strip_hidden_verdict(raw)
    assert "SONUÇ" not in cleaned and "```" not in cleaned
    assert raw_block == "[SONUÇ egilim=uydurma | guc=orta]"

    parsed = parse_ai_response(raw)
    assert parsed["verdict_valid"] is False
    assert "gecersiz:egilim=uydurma" in parsed["verdict_errors"]
    assert "eksik:mtf_uyum" in parsed["verdict_errors"]
    assert parsed["ok_for_shadow_log"] is False
    assert parsed["ok_for_telegram"] is True  # visible text is still clean & safe
    assert "SONUÇ" not in parsed["visible_text"]

    with pytest.raises(ValueError, match="Gizli AI_SONUC bloğu geçersiz"):
        parse_ai_response(raw, require_verdict=True)


def test_api_prompt_hidden_verdict_flag_stays_cache_invariant_across_symbols(bimas):
    alark = build_from_local_cache("ALARK", as_of=CUT, research_mode="strict")
    b1 = build_api_prompt(bimas, include_hidden_verdict=True)
    b2 = build_api_prompt(alark, include_hidden_verdict=True)
    b_plain = build_api_prompt(bimas, include_hidden_verdict=False)

    assert b1["system"] == b2["system"]
    assert b1["system_sha256"] == b2["system_sha256"]
    assert b1["system"] != b_plain["system"]
    assert "[AI_SONUC egilim=" in b1["system"]
    assert "[AI_SONUC" not in b_plain["system"]
    assert b1["metadata"]["include_hidden_verdict"] is True

    appended = append_hidden_verdict_instruction("örnek prompt")
    assert "[AI_SONUC egilim=" in appended
    assert append_hidden_verdict_instruction(appended) == appended


def test_shadow_record_and_supabase_write_protection(bimas, tmp_path):
    raw = _sample_body(
        "[AI_SONUC egilim=kararsiz | guc=dusuk | mtf_uyum=karma | risk=orta | yayin_degeri=izle]"
    )
    bundle = build_api_prompt(bimas, include_hidden_verdict=True)
    record, parsed = build_shadow_record(
        bimas,
        raw,
        model_adi="claude-sonnet",
        prompt_surumu=bundle["prompt_version"],
        system_sha256=bundle["system_sha256"],
        kaynak_turu="offline_test",
        telegrama_gitti=False,
    )
    assert parsed["ok_for_shadow_log"] is True
    assert record["sembol"] == "BIMAS"
    assert record["tf"] == bimas["main_tf"]
    assert record["egilim"] == "kararsiz"
    assert record["yayin_degeri"] == "izle"
    assert record["telegrama_gitti"] is False
    assert "AI_SONUC" not in record["temiz_yorum"]

    local_file = tmp_path / "ai_yorum_test.json"
    ro_session = FakeSession([])
    ro_store = SupabaseStore("https://demo.supabase.co", "sb_secret_test", session=ro_session, read_only=True)

    # 1) Default allow_supabase_write=False AND read_only store -> zero remote calls!
    res1 = save_shadow_record(record, store=ro_store, local_path=local_file, allow_supabase_write=True)
    assert res1["local_saved"] is True and res1["supabase_saved"] is False
    assert ro_session.calls == []
    assert len(load_local_shadow_records(local_file)) == 1

    # 2) Writable store but allow_supabase_write=False -> still zero remote calls!
    rw_session = FakeSession([FakeResponse(status_code=201, payload=[])])
    rw_store = SupabaseStore("https://demo.supabase.co", "sb_secret_test", session=rw_session, read_only=False)
    res2 = save_shadow_record(record, store=rw_store, local_path=local_file, allow_supabase_write=False)
    assert res2["supabase_saved"] is False and rw_session.calls == []

    # 3) Explicit opt-in + writable store -> UPSERT to public.ai_yorum_test
    res3 = save_shadow_record(record, store=rw_store, local_path=local_file, allow_supabase_write=True)
    assert res3["supabase_saved"] is True
    assert len(rw_session.calls) == 1
    method, url, kwargs = rw_session.calls[0]
    assert method == "POST"
    assert url.endswith(f"/rest/v1/{AI_YORUM_TEST_TABLE}")
    assert kwargs["params"]["on_conflict"] == "anahtar"
    assert kwargs["json"][0]["anahtar"] == record["anahtar"]

    # 4) Summary view read uses GET on v_ai_yorum_test_ozet
    sum_session = FakeSession([FakeResponse(payload=[{"egilim": "kararsiz", "toplam_kayit": 1}])])
    sum_store = SupabaseStore("https://demo.supabase.co", "sb_secret_test", session=sum_session, read_only=True)
    summary = fetch_shadow_summary(sum_store)
    assert summary == [{"egilim": "kararsiz", "toplam_kayit": 1}]
    assert sum_session.calls[0][1].endswith(f"/rest/v1/{AI_YORUM_TEST_VIEW}")


def test_evaluate_shadow_outcome_uses_only_future_bars_and_scores_direction():
    idx = pd.date_range("2026-09-25 10:00", periods=6, freq="4h", tz="Europe/Istanbul")
    frame = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0, 101.0, 103.0, 104.0],
            "High": [101.0, 102.0, 102.0, 104.0, 106.0, 105.0],
            "Low": [99.0, 99.0, 98.0, 100.0, 102.0, 103.0],
            "Close": [100.0, 100.0, 101.0, 103.0, 105.0, 104.0],
            "Volume": [1000] * 6,
        },
        index=idx,
    )
    cut = idx[2].isoformat()  # strictly after index 2 -> bars 3, 4, 5 (3 bars)

    rec_up = {"kesit_zamani": cut, "referans_fiyat": 100.0, "tf": "4h", "egilim": "yukari"}
    rec_dn = {"kesit_zamani": cut, "referans_fiyat": 100.0, "tf": "4h", "egilim": "asagi"}
    rec_flat = {"kesit_zamani": cut, "referans_fiyat": 100.0, "tf": "4h", "egilim": "kararsiz"}

    # Horizon > available future bars -> None (not mature yet)
    assert evaluate_shadow_outcome(rec_up, frame, horizon_bars=4) is None

    out_up = evaluate_shadow_outcome(rec_up, frame, horizon_bars=3)
    assert out_up is not None
    assert out_up["bar_sayisi"] == 3
    assert out_up["yuzde"] == 4.0
    assert out_up["yon_uyumlu_yuzde"] == 4.0
    assert out_up["max_yukari_yuzde"] == 6.0
    assert out_up["max_asagi_yuzde"] == 0.0
    assert out_up["yon_isabet"] is True

    out_dn = evaluate_shadow_outcome(rec_dn, frame, horizon_bars=3)
    assert out_dn["yon_uyumlu_yuzde"] == -4.0
    assert out_dn["yon_isabet"] is False

    out_flat = evaluate_shadow_outcome(rec_flat, frame, horizon_bars=3)
    assert out_flat["yon_uyumlu_yuzde"] is None
    assert out_flat["yon_isabet"] is None


def test_ai_shadow_log_defaults_on_and_can_be_toggled(monkeypatch):
    assert config.AI_SHADOW_LOG is True
    assert config.ai_shadow_log_enabled() is True
    monkeypatch.setattr(config, "AI_SHADOW_LOG", False)
    assert config.ai_shadow_log_enabled() is False
