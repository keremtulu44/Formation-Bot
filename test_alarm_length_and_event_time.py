"""Alarm denetimi: kısa AI çıktısı, eksiksiz koruma ve TF kapanış sırası (ağ yok)."""
import json

import pytest

from ai_prompt import build_api_prompt, load_local_shadow_records, parse_ai_response
from ai_prompt.api_messages import _build_system_prompt
from ai_prompt.budget import API_STANDARD_BUDGET, utf16_len
from ai_prompt.commentary import validate_ai_commentary
from ai_prompt.service import enrich_alarm_with_ai
from notification_delivery import DeliveryOutbox, _olay_zamani
from test_ai_live_integration import (
    LONG_AI_REPLY,
    VALID_AI_REPLY,
    _load_bimas_1h_frame,
    _mock_router_wrapper_ok,
    _sample_alert_data,
)
from test_notification_delivery import _bar, alert, owner


def test_alarm_profile_has_short_instruction_in_every_system_variant():
    for modality in ("text_only", "multimodal"):
        system = _build_system_prompt(
            modality, include_hidden_verdict=True, include_kap_rules=True,
            output_profile="alarm",
        )
        assert "50–80 kelime" in system and "en fazla 100 kelime" in system
        assert "120–180 kelime" not in system
        assert "CHoCH" in system and "BOS" in system
        assert utf16_len(system) <= API_STANDARD_BUDGET.system_hard_max
    assert "120–180 kelime" in _build_system_prompt("text_only")


def test_unknown_output_profile_is_rejected():
    with pytest.raises(ValueError):
        _build_system_prompt("text_only", output_profile="typo")
    with pytest.raises(ValueError):
        parse_ai_response(VALID_AI_REPLY, output_profile="typo")


def test_alarm_word_limit_does_not_truncate_or_reject_manual_analysis():
    assert parse_ai_response(VALID_AI_REPLY, output_profile="alarm")["ok_for_telegram"]
    assert parse_ai_response(LONG_AI_REPLY)["ok_for_telegram"]
    parsed = parse_ai_response(LONG_AI_REPLY, output_profile="alarm")
    assert not parsed["ok_for_telegram"]
    assert "cok_uzun" in parsed["validation"]["warnings"]
    assert "AI_SONUC" not in parsed["visible_text"]
    assert parsed["visible_text"].endswith("olarak duruyor.")  # no sentence slicing


def test_alarm_word_limit_boundary_and_hidden_verdict_exclusion():
    for words, allowed in ((100, True), (101, False)):
        text = ("Mevcut durum\n" + "görüş " * (words - 2)
                + "\nBağlam\nkanıt\nReplay notu\ntemas\n"
                + "[AI_SONUC egilim=yukari | guc=orta | mtf_uyum=karma | risk=orta | yayin_degeri=izle]")
        parsed = parse_ai_response(text, output_profile="alarm")
        assert parsed["validation"]["word_count"] == words
        assert parsed["ok_for_telegram"] is allowed


def test_blank_paragraphs_cannot_hide_words_or_unsafe_late_sections():
    text = ("Mevcut durum\nilk paragraf\n\n" + "görüş " * 110
            + "\n\nBağlam\nkarşı kanıt\n\nReplay notu\nal sinyali")
    checked = validate_ai_commentary(text, min_words=1, max_words=100)
    assert checked["word_count"] == 116
    assert checked["section_word_counts"] == {"Mevcut durum": 112, "Bağlam": 2, "Replay notu": 2}
    assert "cok_uzun" in checked["warnings"]
    assert "yasak_tavsiye_veya_kesin_tahmin" in checked["warnings"]
    assert not parse_ai_response(text, output_profile="alarm")["ok_for_telegram"]


def test_enrichment_sends_actual_trigger_and_short_profile(monkeypatch, tmp_path):
    import ai_prompt.service as service

    bundles = []

    def capture(*args, **kwargs):
        bundle = build_api_prompt(*args, **kwargs)
        bundles.append(bundle)
        return bundle

    monkeypatch.setattr(service, "build_api_prompt", capture)
    payload = _sample_alert_data()
    assert enrich_alarm_with_ai(
        payload, df_1h=_load_bimas_1h_frame(), as_of="2026-09-25 18:05+03:00",
        router=_mock_router_wrapper_ok(), shadow_local_path=tmp_path / "shadow.json",
    )
    assert bundles[0]["metadata"]["output_profile"] == "alarm"
    assert bundles[0]["metadata"]["has_trigger"]
    assert "state: KIRILIM_TEYITLI" in bundles[0]["user"]
    assert "direction: 1" in bundles[0]["user"]
    rows = load_local_shadow_records(tmp_path / "shadow.json")
    assert "cok_kisa" not in rows[0]["dogrulama"]["warnings"]


def test_overlong_ai_reply_falls_back_without_losing_alarm(monkeypatch, tmp_path):
    import test_ai_live_integration as integration

    monkeypatch.setattr(integration, "VALID_AI_REPLY", LONG_AI_REPLY)
    payload = _sample_alert_data()
    assert not enrich_alarm_with_ai(
        payload, df_1h=_load_bimas_1h_frame(), as_of="2026-09-25 18:05+03:00",
        router=_mock_router_wrapper_ok(), shadow_local_path=tmp_path / "shadow.json",
    )
    assert "ai_yorum_mesaji" not in payload  # notifier still has the original card
    rows = load_local_shadow_records(tmp_path / "shadow.json")
    assert rows[0]["dogrulama"]["ok_for_telegram"] is False
    assert "cok_uzun" in rows[0]["dogrulama"]["warnings"]
    assert rows[0]["telegrama_gitti"] is False
    json.dumps(payload, default=str)  # no unserializable context added


@pytest.mark.parametrize("destination", ["dm", "public"])
@pytest.mark.parametrize("confirmation_open,confirmation_close", [("15:30", "16:30"), ("16:30", "17:30")])
def test_later_or_same_close_retest_not_blocked_by_earlier_open(
    tmp_path, destination, confirmation_open, confirmation_close,
):
    box = DeliveryOutbox(owner([]), tmp_path)
    confirmation = alert(tf="1h", identity="first", bar=_bar(box, saat=confirmation_open))
    confirmation["bar_kapanis"] = _bar(box, saat=confirmation_close)
    retest = alert(tf="4h", identity="second", state="RETEST_BASARILI",
                   bar=_bar(box, saat="13:30"))
    retest["bar_kapanis"] = _bar(box, saat="17:30")
    if destination == "dm":
        box.state["rows"].append({"data": confirmation, "created": box.now().isoformat()})
        duplicate = box.is_story_duplicate
    else:
        box.remember_public(confirmation)
        # Kapanış geçmişi restart'ta da korunmalı.
        box = DeliveryOutbox(owner([]), tmp_path)
        assert box.state["public"][0]["data"]["bar_kapanis"] == confirmation["bar_kapanis"]
        duplicate = box.public_duplicate
    assert not duplicate(retest)
    retest["bar_time"] = _bar(box, saat="09:30")
    retest["bar_kapanis"] = _bar(box, saat="13:30")
    assert duplicate(retest)  # truly older event is still a replay
    retest["bar_kapanis"] = _bar(box, saat=confirmation_close)
    retest["state"] = "KIRILIM_TEYITLI"
    assert duplicate(retest)  # same-close same-stage duplicate still blocked


def test_event_time_uses_istanbul_day_and_legacy_fallback():
    assert _olay_zamani({"bar_kapanis": "2026-11-26T22:00:00Z"}).isoformat() == "2026-11-27T01:00:00+03:00"
    legacy = {"bar_time": "2026-11-27T13:30:00+03:00", "bar_kapanis": "bad"}
    assert _olay_zamani(legacy).hour == 13
    assert _olay_zamani({"timestamp": legacy["bar_time"]}).hour == 13


def test_short_alarm_display_preserves_all_bodies_without_reinterpreting():
    from ai_prompt.commentary import format_short_alarm_commentary

    text = ("**Mevcut durum**\nKırılım aşağı.\n\nDevam koşullu.\n\n"
            "## Bağlam:\nÜst TF yukarı geçişte.\n\n"
            "Replay notu\n288,25 üzeri kapanış görüşü zayıflatır.\n\n267,75 henüz temas almamış.")
    assert format_short_alarm_commentary(text) == (
        "🧭 Görünüm\nKırılım aşağı. Devam koşullu. Üst TF yukarı geçişte.\n\n"
        "📍 İzlenecek bölgeler\n288,25 üzeri kapanış görüşü zayıflatır. 267,75 henüz temas almamış."
    )
    # Eksik bölümler sessizce kaybolmaz; biçim bozuksa mevcut fallback kullanılır.
    with pytest.raises(ValueError):
        format_short_alarm_commentary("Mevcut durum\nEksik yanıt")


@pytest.mark.parametrize("tf,label", [("1h", "1 saat"), ("2h", "2 saat"), ("4h", "4 saat"), ("1d", "Günlük")])
def test_compact_alarm_is_readable_prose_for_dm_and_public(tf, label):
    from ai_prompt.service import format_ai_alarm_message
    from notifier.api import _ai_duzyazi_mesaji_mi, _metin_govdesi

    payload = _sample_alert_data()
    payload["timeframe"] = tf
    parsed = parse_ai_response(VALID_AI_REPLY, output_profile="alarm")
    message = format_ai_alarm_message(payload, parsed["visible_text"])
    assert f"🤖 BIMAS · {label} ·" in message
    assert "Kapanış: 421,50 TL" in message
    assert payload["bar_metni"] in message  # kapanış zamanı bilgisi kaybolmaz
    assert message.count("🧭 Görünüm") == message.count("📍 İzlenecek bölgeler") == 1
    assert "Replay notu" not in message and "🔎 Bağlam" not in message
    assert "410,75 altı kapanış" in message
    assert "henüz yukarı BOS teyidi yok" in message
    assert "AI_SONUC" not in message
    assert message.endswith("yatırım tavsiyesi değildir")
    assert _ai_duzyazi_mesaji_mi(message)
    assert _metin_govdesi(message) == message  # notifier tablo gibi girinti eklemez
    # İç denetim/gölge görünümü değişmez; manuel analiz bu dönüşümü kullanmaz.
    assert "🧭 Mevcut durum" in parsed["visible_text"]
    assert "🕯️ Replay notu" in parsed["visible_text"]
