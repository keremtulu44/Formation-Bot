from datetime import datetime, timedelta, time as dt_time

import pytz

import main as main_mod
from notifier import TelegramNotifier
from telegram_alert_flow import DeferredAlertBuffer

TZ = pytz.timezone("Europe/Istanbul")


def _record(stock="THYAO", tf="1h", state="SIKISMA_GUCLENIYOR", quality=84):
    return {
        "stock": stock,
        "timeframe": tf,
        "pattern_name": "Simetrik Üçgen",
        "state": state,
        "quality": quality,
        "contraction": 0.72,
    }


def test_immediate_event_identity_is_stable_and_state_specific():
    event = {
        "type": "RETEST_OK",
        "state": "RETEST_BASARILI",
        "time": datetime(2026, 9, 25, 18, 30),
        "bar": 217,
    }
    first = main_mod._formation_alert_event_id(type("Snap", (), {"events": [event]})(), "RETEST_BASARILI")
    replayed = main_mod._formation_alert_event_id(type("Snap", (), {"events": [dict(event)]})(), "RETEST_BASARILI")

    assert first == replayed == "RETEST_OK:2026-09-25T18:30:00"
    assert main_mod._formation_alert_event_id(
        type("Snap", (), {"events": [event]})(), "RETEST_BEKLENIYOR"
    ) is None
    assert main_mod._formation_alert_event_id(
        type("Snap", (), {"events": [{**event, "time": None}]})(), "RETEST_BASARILI"
    ) == "RETEST_OK:bar:217"


def test_watchlist_guncel_durumu_slot_basina_tutar():
    buf = DeferredAlertBuffer()
    now = TZ.localize(datetime(2026, 9, 30, 17, 0))
    buf.observe("THYAO", "1h", _record(quality=80), now)
    buf.observe("THYAO", "1h", _record(quality=87), now + timedelta(hours=1))
    buf.observe("GARAN", "4h", _record("GARAN", "4h", quality=90), now)

    items = buf.items(now + timedelta(hours=1))
    assert len(items) == 2
    assert items[0]["stock"] == "GARAN"
    assert next(x for x in items if x["stock"] == "THYAO")["quality"] == 87


def test_watch_snapshot_same_day_restart_and_day_change_restore():
    now = TZ.localize(datetime(2026, 9, 30, 17, 0))
    source = DeferredAlertBuffer()
    source.observe("THYAO", "1h", _record(), now)
    source.mark_reported([_record("GARAN", "4h")], now)
    snapshot = source.snapshot(now)

    restarted = DeferredAlertBuffer()
    assert restarted.restore(snapshot, now) == 1
    assert [(item["stock"], item["timeframe"]) for item in restarted.items(now)] == [("THYAO", "1h")]
    same_day = restarted.snapshot(now)
    assert same_day["reported"] == [["GARAN", "4h", "Simetrik Üçgen", "SIKISMA_GUCLENIYOR"]]

    assert restarted.restore(snapshot, now + timedelta(days=1)) == 0
    assert restarted.items(now + timedelta(days=1)) == []


def test_watch_restore_ignores_malformed_collections_and_candidates():
    buffer_ = DeferredAlertBuffer()
    now = TZ.localize(datetime(2026, 9, 30, 17, 0))
    assert buffer_.restore({"date": now.date().isoformat(), "pending": None, "reported": "bad"}, now) == 0
    assert buffer_.items(now) == []


def test_acil_duruma_gecis_veya_slotun_sonlanmasi_bekleyeni_siler():
    buf = DeferredAlertBuffer()
    now = TZ.localize(datetime(2026, 9, 30, 17, 0))
    buf.observe("THYAO", "1h", _record(), now)
    buf.observe("THYAO", "1h", _record(state="KIRILIM_TEYITLI"), now + timedelta(minutes=30))
    assert len(buf) == 0

    buf.observe("THYAO", "1h", _record(), now + timedelta(hours=1))
    buf.observe("THYAO", "1h", None, now + timedelta(hours=2))
    assert len(buf) == 0


def test_bildirilen_ayni_watch_ayni_gun_tekrarlanmaz_yeni_gunde_sifirlanir():
    buf = DeferredAlertBuffer()
    now = TZ.localize(datetime(2026, 9, 30, 17, 0))
    record = _record()
    buf.observe("THYAO", "1h", record, now)
    buf.mark_reported([record], now + timedelta(minutes=30))
    buf.observe("THYAO", "1h", record, now + timedelta(hours=1))
    assert len(buf) == 0

    tomorrow = now + timedelta(days=1)
    buf.observe("THYAO", "1h", record, tomorrow)
    assert len(buf.items(tomorrow)) == 1


def test_digest_icin_en_yuksek_kalite_oniki_aday_doner():
    buf = DeferredAlertBuffer()
    now = TZ.localize(datetime(2026, 9, 30, 17, 0))
    for i in range(15):
        buf.observe(f"H{i:02d}", "1h", _record(f"H{i:02d}", quality=60 + i), now)

    items = buf.items(now, limit=12)
    assert len(items) == 12
    assert items[0]["quality"] == 74
    assert "H00" not in {x["stock"] for x in items}


def test_acil_mesaj_baglaminda_en_fazla_uc_ertelenmis_aday_gosterilir():
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    watch_context = [
        _record(f"H{i:02d}", quality=90 - i)
        for i in range(4)
    ]
    message = notifier.format_message({
        "stock_name": "THYAO",
        "timeframe": "1h",
        "pattern_name": "Simetrik Üçgen",
        "state": "KIRILIM_TEYITLI",
        "confidence_score": 88,
        "upper_now": 300,
        "lower_now": 290,
        "critical_price_level": 300,
        "break_dir": 1,
        "watch_context": watch_context,
    })

    assert "Diğer izleme adayları" in message
    assert "H00" in message and "H02" in message
    assert "H03" not in message


def test_eski_aksam_ozeti_kapanis_saatine_tasinir(monkeypatch):
    monkeypatch.setattr(main_mod, "SUMMARY_HOURS", "09:55,18:15")
    monkeypatch.setattr(main_mod, "DEFERRED_ALERT_DIGEST_TIME", "18:45")

    assert main_mod._effective_summary_hours() == [dt_time(9, 55), dt_time(18, 45)]


def test_digest_saati_son_otomatik_tarama_oncesine_cekilemez(monkeypatch):
    monkeypatch.setattr(main_mod, "DEFERRED_ALERT_DIGEST_TIME", "18:15")

    assert main_mod._parse_deferred_alert_digest_time() == dt_time(18, 45)
