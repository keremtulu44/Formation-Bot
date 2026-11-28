"""AI akışı temizliği: veri koruma, aynı doğrulama kapıları ve güvenli kayıt (ağ yok)."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
import json
from types import SimpleNamespace

import pandas as pd
import pytest

import config
from ai_prompt import build_api_prompt, build_from_local_cache, build_shadow_record, parse_ai_response
from ai_prompt import service, shadow_store
from ai_prompt.api_messages import _build_system_prompt
from ai_prompt.budget import utf16_len
from ai_prompt.verdict import parse_verdict_block, strip_hidden_verdict
from test_ai_live_integration import (
    VALID_AI_REPLY,
    _FakeWritableStore,
    _mock_router_wrapper_ok,
    _sample_alert_data,
)
from test_ai_prompt_budget import _worst_kap_payload, _worst_trigger

CUT = config.ISTANBUL_TZ.localize(datetime(2026, 9, 25, 18, 5))
VERDICT = "[AI_SONUC egilim=yukari | guc=orta | mtf_uyum=karma | risk=orta | yayin_degeri=izle]"


@pytest.fixture(scope="module")
def packet():
    return build_from_local_cache("BIMAS", as_of=CUT, main_tf="4h")


def _frames_and_packet(monkeypatch, packet, memory):
    monkeypatch.setattr(service, "build_from_local_cache", lambda *a, **k: packet)
    monkeypatch.setattr(service, "build_from_frames", lambda *a, **k: packet)
    frame = pd.DataFrame({"close": [100.0] * 5})
    if not memory:
        return None
    return SimpleNamespace(to_dataframe=lambda _: frame, to_gunluk_dataframe=lambda _: None)


@pytest.mark.parametrize("memory", [False, True])
def test_manual_cache_and_memory_reject_unsafe_output_equally(monkeypatch, tmp_path, packet, memory):
    import test_ai_live_integration as integration

    manager = _frames_and_packet(monkeypatch, packet, memory)
    bad = VALID_AI_REPLY.replace("Dış yapı aşağı geçişte", "al sinyali; dış yapı aşağı geçişte")
    monkeypatch.setattr(integration, "VALID_AI_REPLY", bad)
    reply = service.run_manual_ai_analysis(
        "BIMAS", deque_manager=manager, now=CUT, router=_mock_router_wrapper_ok(),
        shadow_local_path=tmp_path / "shadow.json",
    )
    assert "AI analizi alınamadı (validation_failed)" in reply
    assert "al sinyali" not in reply and "🧭 Mevcut durum" not in reply
    row = shadow_store.load_local_shadow_records(tmp_path / "shadow.json")[0]
    assert not row["telegrama_gitti"]
    assert not row["dogrulama"]["ok_for_telegram"]


@pytest.mark.parametrize("memory", [False, True])
@pytest.mark.parametrize("failure", ["prompt_error", "client_error"])
def test_manual_paths_handle_prompt_and_client_exceptions(monkeypatch, packet, memory, failure):
    manager = _frames_and_packet(monkeypatch, packet, memory)
    router = _mock_router_wrapper_ok()

    def fail(*a, **kw):
        raise RuntimeError("synthetic failure")

    if failure == "prompt_error":
        monkeypatch.setattr(service, "build_api_prompt", fail)
    else:
        monkeypatch.setattr(router, "ask_bundle", fail)
    reply = service.run_manual_ai_analysis("BIMAS", deque_manager=manager, now=CUT, router=router)
    assert f"AI analizi alınamadı ({failure})" in reply


@pytest.mark.parametrize("tail", [
    "[AI_SONUC egilim=yukari | guc=orta",
    "```text\n[AI_SONUC egilim=yukari | guc=orta",
    "[SONUÇ egilim=yukari",
    "```[AI-SONUC egilim=yukari",
])
def test_unfinished_hidden_blocks_never_leak(tail):
    body, _ = strip_hidden_verdict(VALID_AI_REPLY)
    parsed = parse_ai_response(body + "\n\n" + tail, output_profile="alarm")
    assert parsed["ok_for_telegram"]  # güvenli görünür yorum kaybolmaz
    assert not parsed["verdict_valid"]
    assert parsed["visible_text"] == body
    assert "```" not in parsed["visible_text"]


@pytest.mark.parametrize("fenced_first", [True, False])
def test_last_verdict_source_order_not_regex_pass_order(fenced_first):
    first = VERDICT.replace("egilim=yukari", "egilim=asagi")
    last = VERDICT
    if fenced_first:
        text = f"```text\n{first}\n```\n{last}"
    else:
        text = f"{first}\n```text\n{last}\n```"
    cleaned, raw = strip_hidden_verdict(text)
    assert cleaned == "" and raw == last


@pytest.mark.parametrize("field", ["egilim=asagi", "yon=asagi"])
def test_conflicting_or_alias_duplicate_verdict_fields_invalid(field):
    raw = VERDICT.replace("egilim=yukari", f"egilim=yukari | {field}")
    _, valid, errors = parse_verdict_block(raw)
    assert not valid and "yinelenen_alan:egilim" in errors
    parsed = parse_ai_response(VALID_AI_REPLY.replace(VERDICT, raw))
    assert not parsed["ok_for_shadow_log"]
    assert "AI_SONUC" not in parsed["visible_text"]


def test_shadow_version_and_delivery_are_not_inferred_from_preparation(monkeypatch, tmp_path, packet):
    _frames_and_packet(monkeypatch, packet, False)
    real_builder = service.build_api_prompt

    def versioned(*a, **kw):
        bundle = real_builder(*a, **kw)
        bundle["prompt_version"] = "audit-version"
        return bundle

    monkeypatch.setattr(service, "build_api_prompt", versioned)
    outcome = service.generate_ai_commentary_for_frames(
        "BIMAS", pd.DataFrame({"close": [100.0] * 5}), as_of=CUT,
        router=_mock_router_wrapper_ok(), telegram_delivered_hint=True,
        shadow_local_path=tmp_path / "shadow.json",
    )
    assert outcome["ok"]
    row = shadow_store.load_local_shadow_records(tmp_path / "shadow.json")[0]
    assert row["prompt_surumu"] == "audit-version"
    assert not row["telegrama_gitti"]
    assert row["baglam_ozet"]["teslim_durumu"] == "dogrulanmadi"


def test_alarm_and_manual_shadow_rows_do_not_overwrite_each_other(packet, tmp_path):
    manual, _ = build_shadow_record(packet, VALID_AI_REPLY, output_profile="standard")
    alarm, _ = build_shadow_record(packet, VALID_AI_REPLY, output_profile="alarm")
    assert manual["anahtar"] != alarm["anahtar"]
    path = tmp_path / "book.json"
    shadow_store.save_local_shadow_records([manual, alarm], path)
    assert len(shadow_store.load_local_shadow_records(path)) == 2
    with pytest.raises(ValueError, match="çıktı profili"):
        shadow_store.make_shadow_key("BIMAS", "4h", CUT, output_profile="typo")


def test_concurrent_shadow_writes_preserve_every_record(tmp_path):
    path = tmp_path / "book.json"

    def write(i):
        return shadow_store.save_local_shadow_records([{"anahtar": str(i), "value": i}], path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(write, range(32))) == [1] * 32
    rows = shadow_store.load_local_shadow_records(path)
    assert {r["value"] for r in rows} == set(range(32))
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("old", ["{broken", '{"kayitlar": null}', '[{"anahtar": "old"}, 42]'])
def test_corrupt_local_book_preserved_and_remote_write_still_attempted(tmp_path, old):
    path = tmp_path / "book.json"
    path.write_text(old)
    store = _FakeWritableStore()
    result = shadow_store.save_shadow_record(
        {"anahtar": "new", "kesit_zamani": CUT.isoformat()}, local_path=path, store=store, allow_supabase_write=True,
    )
    assert not result["local_saved"] and result["supabase_saved"]
    assert path.read_text() == old and len(store.calls) == 1


def test_atomic_write_failure_keeps_old_book_and_cleans_temp(monkeypatch, tmp_path):
    path = tmp_path / "book.json"
    shadow_store.save_local_shadow_records([{"anahtar": "old"}], path)
    before = path.read_bytes()

    def fail(*a):
        raise OSError("disk error")

    monkeypatch.setattr(shadow_store.os, "replace", fail)
    with pytest.raises(OSError):
        shadow_store.save_local_shadow_records([{"anahtar": "new"}], path)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_alarm_prompt_compacts_labels_without_dropping_evidence(packet):
    before = deepcopy(packet)
    kwargs = dict(trigger=_worst_trigger(), kap_context=_worst_kap_payload(), include_hidden_verdict=True)
    normal = build_api_prompt(packet, **kwargs)
    alarm = build_api_prompt(packet, output_profile="alarm", **kwargs)
    # Yalnız Durum/Dış yapı/Hacim cümle etiketleri kısalır. Başka satırlar aynı.
    stable = lambda text: [line for line in text.splitlines() if not line.startswith(
        ("Durum: dış yapı=", "Durum: hacim=", "Dış yapı durumu:", "Hacim motoru:")
    )]
    assert stable(normal["user"]) == stable(alarm["user"])
    assert utf16_len(alarm["user"]) < utf16_len(normal["user"])
    assert packet == before
    assert "alt bölge emilim işareti geçersizleşti" in alarm["user"]
    assert "hazır değil" in alarm["user"]
    assert alarm["metadata"]["kap_rules_included"]
    assert "rapor 2026-10-21" in alarm["user"]  # zaman sınırı kaybolmaz


def test_alarm_output_rules_independent_from_standard_wording(monkeypatch, tmp_path):
    import ai_prompt.api_messages as messages

    original = (messages.ROOT / "talimat_api.txt").read_text()
    (tmp_path / "talimat_api.txt").write_text(original.replace("120–180 kelime", "140–200 kelime"))
    (tmp_path / "talimat_api_alarm.txt").write_text((messages.ROOT / "talimat_api_alarm.txt").read_text())
    monkeypatch.setattr(messages, "ROOT", tmp_path)
    alarm = _build_system_prompt("text_only", output_profile="alarm")
    assert "50–80 kelime" in alarm and "140–200" not in alarm
    assert "140–200 kelime" in _build_system_prompt("text_only")


def test_telegram_utf16_limit_rejects_without_cutting_conditions(monkeypatch, tmp_path, packet):
    _frames_and_packet(monkeypatch, packet, False)
    payload = _sample_alert_data()
    payload["bar_metni"] = "🕯" * 1800
    # Karakter sayısı 4000 altındayken UTF-16 sınırı aşılabilir.
    with pytest.raises(ValueError, match="uzunluk"):
        service.format_ai_alarm_message(payload, parse_ai_response(VALID_AI_REPLY)["visible_text"])
    assert not service.enrich_alarm_with_ai(
        payload, df_1h=pd.DataFrame({"close": [100.0] * 5}), as_of=CUT,
        router=_mock_router_wrapper_ok(), shadow_local_path=tmp_path / "shadow.json",
    )
    assert "ai_yorum_mesaji" not in payload
    json.dumps(payload, default=str)


@pytest.mark.parametrize("value", [float("inf"), -float("inf"), float("nan"), True, -1, 0])
def test_invalid_close_prices_are_not_rendered_as_financial_levels(value):
    assert service._tr_price(value) == ""
