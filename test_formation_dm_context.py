from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from domain_engines.fvg.fvg_engulfing_final import (
    FvgEngulfingExport,
    FvgSideExport,
)
from domain_engines.fvg.fvg_engulfing_models import FvgEngulfingDataQuality, FvgState
from domain_engines.order_block.order_block import OrderBlockDataQuality
from domain_engines.runner import DomainRunResult
from formation_dm_context import build_formation_dm_context
from notifier import TelegramNotifier


AS_OF = pd.Timestamp("2026-10-08 13:00", tz="Europe/Istanbul")


def _event(event_type="EVENT_BOS", direction=1, *, confirmed_at=AS_OF, active=True):
    return SimpleNamespace(
        event_type=event_type,
        direction=direction,
        confirmed_at=confirmed_at,
        confirmation_status=SimpleNamespace(value="CONFIRMED"),
        is_active=active,
        timeframe=None,
        symbol=None,
    )


def _output(domain, timeframe, *, export=None, details=None, quality=None, result_time=AS_OF, error=None):
    return DomainRunResult(
        domain=domain,
        symbol="THYAO",
        timeframe=timeframe,
        result=SimpleNamespace(timestamp=result_time),
        export=export,
        details=details or {},
        data_quality=quality,
        error=error,
    )


def _market_output(timeframe, event=None, *, result_time=AS_OF):
    events = (event,) if event is not None else ()
    return _output(
        "market_structure",
        timeframe,
        export=SimpleNamespace(events=events),
        result_time=result_time,
    )


def _volume_output(timeframe="2h", level="HIGH", *, data_ready=True, result_time=AS_OF, error=None):
    return _output(
        "volume_participation",
        timeframe,
        export=SimpleNamespace(volume_level=level),
        details={"latest_metrics": SimpleNamespace(data_ready=data_ready)},
        result_time=result_time,
        error=error,
    )


def _ob_output(timeframe, records, *, result_time=AS_OF, error=None):
    return _output(
        "order_block",
        timeframe,
        export=SimpleNamespace(),
        details={"active_records": tuple(records)},
        quality=OrderBlockDataQuality.OK,
        result_time=result_time,
        error=error,
    )


def _ob(top, bottom, *, source_time=AS_OF, active=True):
    return SimpleNamespace(top=top, bottom=bottom, source_time=source_time, active=active)


def _fvg_output(
    timeframe, *, top=None, bottom=None, state=FvgState.ACTIVE,
    formation_time=AS_OF, result_time=AS_OF,
):
    active_record = None
    bull = FvgSideExport()
    bear = FvgSideExport()
    if top is not None and bottom is not None:
        active_record = SimpleNamespace(
            state=state,
            invalid=False,
            full_fill=False,
            formation_time=formation_time,
        )
        bull = FvgSideExport(state=int(state), top=top, bottom=bottom, quality=80, fill=0, event=None)
    return _output(
        "fvg",
        timeframe,
        export=FvgEngulfingExport(bull_fvg=bull, bear_fvg=bear),
        details={"active_bullish_fvg": active_record, "active_bearish_fvg": None},
        quality=FvgEngulfingDataQuality.OK,
        result_time=result_time,
    )


def _dm_sample(**overrides):
    data = {
        "stock_name": "THYAO",
        "timeframe": "2h",
        "pattern_name": "Boğa Bayrağı",
        "state": "KIRILIM_TEYITLI",
        "confidence_score": 81,
        "critical_price_level": 101.0,
        "upper_now": 101.0,
        "lower_now": 95.0,
        "contraction": 0.67,
        "timestamp": AS_OF,
        "break_dir": 1,
        "break_strength": 85,
        "break_price": 101.0,
        "retest_seen": False,
        "upper_touches": 2,
        "lower_touches": 2,
        "age_bars": 145,
        "mtf_destek": False,
        "watch_context": [],
    }
    data.update(overrides)
    return data


def test_same_scan_context_selects_native_structure_volume_and_nearest_zones():
    tf_asofs = {tf: AS_OF for tf in ("1h", "2h", "4h", "1d")}
    domain_results = {
        "1h": {
            "market_structure": _market_output("1h", _event("EVENT_BOS", 1)),
            "order_block": _ob_output("1h", [_ob(103.0, 101.5)]),
            # Runner does not support 1H FVG; a supplied fake result must not leak in.
            "fvg": _fvg_output("1h", top=99.0, bottom=98.0),
        },
        "2h": {
            "market_structure": _market_output("2h", _event("EVENT_CHOCH", -1)),
            "volume_participation": _volume_output("2h", "HIGH"),
            "fvg": _fvg_output("2h", top=99.0, bottom=98.0),
            "order_block": _ob_output("2h", [_ob(107.0, 106.0)]),
        },
        "4h": {"market_structure": _market_output("4h")},
        "1d": {
            "market_structure": _market_output("1d"),
            "order_block": _ob_output("1d", [_ob(116.0, 115.0)]),
        },
    }

    context = build_formation_dm_context(
        domain_results,
        tf_asofs,
        symbol="THYAO",
        formation_timeframe="2h",
        reference_price=100.0,
        scan_as_of=AS_OF,
    )

    assert context["structure"] == "1H BOS ↑ · 2H CHoCH ↓ · 4H — · 1D —"
    assert context["volume"] == "Yüksek"
    assert context["nearby_zones"] == [
        "↑ 1H OB · 101.50–103.00",
        "↓ 2H FVG · 98.00–99.00",
    ]

    message = TelegramNotifier.__new__(TelegramNotifier).format_dm_message(
        _dm_sample(dm_context=context)
    )
    for expected in (
        "THYAO · 2H Boğa Bayrağı",
        "KIRILIM TEYİTLİ",
        "Kalite 81",
        "Daralma %67",
        "4 temas",
        "145 bar",
        "Yukarı kırılım 101.00 teyitli",
        "Yapı: 1H BOS ↑ · 2H CHoCH ↓",
        "Hacim: Yüksek",
        "Yakın bölgeler",
        "↑ 1H OB · 101.50–103.00",
        "↓ 2H FVG · 98.00–99.00",
    ):
        assert expected in message
    assert "98.00–99.00" in message
    assert "1H FVG" not in message


def test_zone_labels_hide_binary_float_noise_without_mutating_native_bounds():
    native_zone = _ob(103.000001, 101.500001)
    context = build_formation_dm_context(
        {"1h": {"order_block": _ob_output("1h", [native_zone])}},
        {"1h": AS_OF},
        symbol="THYAO",
        formation_timeframe="1h",
        reference_price=100.0,
        scan_as_of=AS_OF,
    )
    assert context["nearby_zones"] == ["↑ 1H OB · 101.50–103.00"]
    assert native_zone.bottom == 101.500001
    assert native_zone.top == 103.000001


def test_zone_side_uses_bounds_and_skips_zone_containing_reference():
    tf_asofs = {"1h": AS_OF}
    domain_results = {
        "1h": {
            "order_block": _ob_output(
                "1h",
                [
                    _ob(106.0, 104.0),  # truly above
                    _ob(96.0, 94.0),  # truly below
                    _ob(102.0, 99.0),  # contains reference; not an upper/lower zone
                ],
            )
        }
    }
    context = build_formation_dm_context(
        domain_results,
        tf_asofs,
        symbol="THYAO",
        formation_timeframe="1h",
        reference_price=100.0,
        scan_as_of=AS_OF,
    )
    assert context["nearby_zones"] == [
        "↑ 1H OB · 104.00–106.00",
        "↓ 1H OB · 94.00–96.00",
    ]


def test_stale_or_future_domain_results_are_not_used():
    old = AS_OF - pd.Timedelta(hours=2)
    future = AS_OF + pd.Timedelta(hours=1)
    current_asofs = {"1h": AS_OF, "2h": AS_OF}
    domain_results = {
        "1h": {
            "market_structure": _market_output("1h", _event(confirmed_at=old), result_time=old),
            "order_block": _ob_output("1h", [_ob(102.0, 101.0, source_time=old)], result_time=old),
        },
        "2h": {
            "volume_participation": _volume_output("2h", result_time=old),
            "fvg": _fvg_output(
                "2h", top=99.0, bottom=98.0, formation_time=old, result_time=old
            ),
            "order_block": _ob_output("2h", [_ob(120.0, 119.0)], result_time=future),
        },
    }
    context = build_formation_dm_context(
        domain_results,
        current_asofs,
        symbol="THYAO",
        formation_timeframe="2h",
        reference_price=100.0,
        scan_as_of=AS_OF,
    )
    assert context == {}


def test_future_native_event_and_zone_timestamps_are_not_in_context():
    future = AS_OF + pd.Timedelta(minutes=1)
    domain_results = {
        "2h": {
            "market_structure": _market_output(
                "2h", _event("EVENT_BOS", 1, confirmed_at=future)
            ),
            "volume_participation": _volume_output("2h", "HIGH"),
            "fvg": _fvg_output(
                "2h", top=99.0, bottom=98.0, formation_time=future
            ),
            "order_block": _ob_output(
                "2h", [_ob(103.0, 101.0, source_time=future)]
            ),
        }
    }
    context = build_formation_dm_context(
        domain_results,
        {"2h": AS_OF},
        symbol="THYAO",
        formation_timeframe="2h",
        reference_price=100.0,
        scan_as_of=AS_OF,
    )
    assert "structure" not in context
    assert context["volume"] == "Yüksek"
    assert "nearby_zones" not in context


def test_domain_errors_remove_only_their_own_context():
    domain_results = {
        "2h": {
            "market_structure": _market_output("2h", _event("EVENT_BOS", 1)),
            "volume_participation": _volume_output("2h", error="volume failure"),
            "fvg": _output("fvg", "2h", error="fvg failure"),
            "order_block": _ob_output("2h", [_ob(103.0, 101.0)], error="ob failure"),
        }
    }
    context = build_formation_dm_context(
        domain_results,
        {"2h": AS_OF},
        symbol="THYAO",
        formation_timeframe="2h",
        reference_price=100.0,
        scan_as_of=AS_OF,
    )
    assert context == {"structure": "1H — · 2H BOS ↑ · 4H — · 1D —"}
    assert "volume" not in context
    assert "nearby_zones" not in context


def test_only_native_volume_levels_are_translated_and_not_guessed():
    for native, expected in (("NORMAL", "Normal"), ("RISING", "Yükselen"), ("ABNORMAL", "Anormal")):
        context = build_formation_dm_context(
            {"2h": {"volume_participation": _volume_output("2h", native)}},
            {"2h": AS_OF},
            symbol="THYAO",
            formation_timeframe="2h",
            reference_price=100,
            scan_as_of=AS_OF,
        )
        assert context["volume"] == expected
    not_ready = build_formation_dm_context(
        {"2h": {"volume_participation": _volume_output("2h", "HIGH", data_ready=False)}},
        {"2h": AS_OF},
        symbol="THYAO",
        formation_timeframe="2h",
        reference_price=100,
        scan_as_of=AS_OF,
    )
    unavailable = build_formation_dm_context(
        {"2h": {"volume_participation": _volume_output("2h", "UNAVAILABLE")}},
        {"2h": AS_OF},
        symbol="THYAO",
        formation_timeframe="2h",
        reference_price=100,
        scan_as_of=AS_OF,
    )
    assert not_ready == {}
    assert unavailable == {}


def test_compact_dm_preserves_formation_details_and_uses_turkish_labels():
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    message = notifier.format_dm_message(
        _dm_sample(dm_context={"structure": "2H BOS ↑", "volume": "Yüksek"})
    )
    assert "Kalite 81" in message
    assert "Daralma %67" in message
    assert "4 temas" in message
    assert "145 bar" in message
    assert "KIRILIM TEYİTLİ" in message
    assert "Yukarı kırılım 101.00 teyitli · retest bekleniyor" in message
    assert "Q:" not in message and "Age:" not in message
    assert "Yapı:" in message and "Hacim: Yüksek" in message


def test_failed_break_dm_uses_native_state_meaning_without_inventing_cause_or_followup():
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    data = _dm_sample(state="BASARISIZ_KIRILIM")
    message = notifier.format_dm_message(data)

    assert "BAŞARISIZ KIRILIM" in message
    assert "Fiyat kırılım sonrası formasyon alanına döndü" in message
    # No explicit native field says this is a "fake break" or predicts a new squeeze.
    assert "sahte kırılım ihtimali" not in message.lower()
    assert "yeniden sıkışma bekleniyor" not in message.lower()


def test_confirmed_break_keeps_native_directional_support_resistance_meaning():
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    upward = notifier.format_dm_message(
        _dm_sample(state="KIRILIM_TEYITLI", break_dir=1, break_price=101.0)
    )
    downward = notifier.format_dm_message(
        _dm_sample(state="KIRILIM_TEYITLI", break_dir=-1, break_price=95.0)
    )
    no_direction = notifier.format_dm_message(
        _dm_sample(state="KIRILIM_TEYITLI", break_dir=0, break_price=None)
    )

    assert "Seviye destek olabilir" in upward
    assert "Seviye direnç olabilir" in downward
    assert "Seviye destek olabilir" not in no_direction
    assert "Seviye direnç olabilir" not in no_direction


def test_mtf_label_preserves_existing_supporting_timeframe():
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    one_hour = notifier.format_dm_message(
        _dm_sample(timeframe="1h", mtf_destek=True)
    )
    four_hour = notifier.format_dm_message(
        _dm_sample(timeframe="4h", mtf_destek=True)
    )
    explicit = notifier.format_dm_message(
        _dm_sample(timeframe="2h", mtf_destek=True, mtf_timeframe="1d")
    )
    no_mtf = notifier.format_dm_message(_dm_sample(mtf_destek=False))

    assert "MTF: 4H destekliyor" in one_hour
    assert "MTF: 1D destekliyor" in four_hour
    assert "MTF: 1D destekliyor" in explicit
    assert "Çoklu zaman desteği mevcut" not in one_hour + four_hour + explicit
    assert "MTF:" not in no_mtf


def test_other_break_and_retest_states_keep_native_event_details():
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    candidate = notifier.format_dm_message(_dm_sample(state="KIRILIM_ADAYI"))
    attempt = notifier.format_dm_message(_dm_sample(state="KIRILIM_DENEMESI"))
    retesting = notifier.format_dm_message(_dm_sample(state="RETEST_EDILIYOR"))
    completed_without_retest = notifier.format_dm_message(
        _dm_sample(state="FORMASYON_TAMAMLANDI", retest_seen=False)
    )

    assert "kırılım gücü 85 · teyit bekleniyor" in candidate
    assert "kırılım gücü 85 · teyit bekleniyor" in attempt
    assert "kırılan seviye yeniden test ediliyor" in retesting
    assert "fiyat kırılan seviyeye dönmedi" in completed_without_retest


def test_public_formatter_and_channel_payload_ignore_dm_context(tmp_path, monkeypatch):
    import notifier as notifier_module
    from notification_outbox import NotificationOutbox

    monkeypatch.setattr(notifier_module.random, "choice", lambda values: values[0])
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    notifier.enabled = True
    notifier.token = "123456:fake-token"
    notifier.chat_id = "private-chat"
    notifier.channel_id = "public-channel"
    notifier.last_sent = {}
    notifier.cooldown_hours = 4
    notifier.persistent_store = None
    notifier.can_send = lambda *args, **kwargs: True
    notifier._cooldown_kaydet = lambda: None
    notifier._gonderim_kaydet = lambda: None
    notifier.max_saatlik = 20
    notifier.max_gunluk = 120
    notifier._saatlik_zamanlar = []
    notifier._gunluk_sayac = 0
    notifier._gunluk_tarih = datetime.now().date()
    notifier._kap_uyarildi = False
    notifier.public_min_quality = 80
    notifier.public_states = {"KIRILIM_TEYITLI"}
    notifier.public_sikisma_min = 0.80
    notifier._delivery_interval_seconds = 0
    notifier._outbox = NotificationOutbox(str(tmp_path / "outbox.json"))
    channel_messages = []
    requests_seen = []

    def fake_transport(text, chat_id):
        requests_seen.append(("fake://telegram/sendMessage", {"chat_id": chat_id, "text": text}, 10))
        if chat_id == "public-channel":
            channel_messages.append(text)
        return True, 200, "ok", None, False

    notifier._send_text_direct = fake_transport

    base_data = _dm_sample()
    enriched_data = _dm_sample(
        dm_context={
            "structure": "2H BOS ↑",
            "volume": "Yüksek",
            "nearby_zones": ["↑ 2H OB · 101–102"],
        }
    )
    old_public_message = notifier.format_message(base_data)
    assert notifier.format_message(enriched_data) == old_public_message
    assert notifier.should_send_to_public(base_data) == notifier.should_send_to_public(enriched_data)

    assert notifier.send(enriched_data) is True
    assert len(requests_seen) == 2
    dm_text = next(payload["text"] for _, payload, _ in requests_seen if payload["chat_id"] == "private-chat")
    assert "Yapı: 2H BOS ↑" in dm_text
    assert "Yakın bölgeler" in dm_text
    assert channel_messages == [old_public_message]
    assert "Yapı:" not in channel_messages[0]
    assert "Hacim:" not in channel_messages[0]
    assert "Yakın bölgeler" not in channel_messages[0]


def test_dm_length_is_compact_relative_to_legacy_formation_message():
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    data = _dm_sample(
        dm_context={
            "structure": "1H BOS ↑ · 2H BOS ↑ · 4H — · 1D CHoCH ↓",
            "volume": "Yüksek",
            "nearby_zones": ["↑ 1D OB · 101.50–103.00", "↓ 2H FVG · 98.00–99.00"],
        }
    )
    old_message = notifier.format_message({key: value for key, value in data.items() if key != "dm_context"})
    new_message = notifier.format_dm_message(data)
    context_chars = sum(
        len(line)
        for line in (
            f"Yapı: {data['dm_context']['structure']}",
            f"Hacim: {data['dm_context']['volume']}",
            "Yakın bölgeler",
            *data["dm_context"]["nearby_zones"],
        )
    )
    # The compact Formation core plus actual context may not exceed the old
    # Formation-only wording plus the literal new context content.
    assert len(new_message) <= len(old_message) + context_chars + 6
    assert len(new_message) < 4096  # Telegram's hard message ceiling, not a bespoke cap.
