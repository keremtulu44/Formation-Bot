"""Regression checks at the actual Telegram text/caption boundary."""
import pytest

import main as M
from notifier.format_kart import _kart_mum_damgasi
from telegram_commands import TelegramCommandListener, kirp, metni_sigdir


def test_help_is_not_truncated_after_real_mobile_wrapping():
    wrapped = metni_sigdir(M.KOMUT_YARDIM, guvenlik=1.0)
    assert len(wrapped) <= 4096 and kirp(wrapped) == wrapped
    assert "48 hisse" not in wrapped  # Universe size changes over time.
    for name in M.TELEGRAM_KOMUTLARI:
        assert f"/{name}" in wrapped.lower()
    assert "sıra silinir" in wrapped
    sent = []
    listener = TelegramCommandListener("token", "123", M.TELEGRAM_KOMUTLARI,
                                       help_text=M.KOMUT_YARDIM,
                                       response_sender=lambda uid, text: sent.append(text) or True)
    update = {"update_id": 1, "message": {"message_id": 1, "text": "/yardim",
              "chat": {"id": 123, "type": "private"}, "from": {"id": 123}}}
    listener.handle_update(update)
    assert sent and sent[0] == wrapped
    assert "mesaj sınırı nedeniyle kesildi" not in sent[0]


@pytest.mark.parametrize(("tf", "bar_label", "expected"), [
    ("1h", "2026-09-25T12:30:00Z", "25.09.2026 16:30 TSİ"),
    ("1h", "2026-09-25T17:30:00+03:00", "25.09.2026 18:00 TSİ"),
    ("4h", "2026-10-28T11:30:00+03:00", "28.10.2026 13:00 TSİ"),
    ("1d", "2026-10-28T00:00:00+03:00", "28.10.2026 13:00 TSİ"),
])
def test_chart_caption_uses_actual_candle_close_in_istanbul(tf, bar_label, expected):
    caption = M._kare_altyazisi("ASTOR", tf, {"son_bar_ts": bar_label})
    assert "son mum kapanışı " + expected in caption


def test_alert_candle_range_normalizes_mixed_timezones():
    card = _kart_mum_damgasi({"bar_time": "2026-09-25T09:30:00+00:00",
                               "bar_kapanis": "2026-09-25T13:30:00+03:00"})
    assert card == "🕒 25 Eylül 12:30→13:30 mumu"


@pytest.mark.parametrize("seen", [None, False, True])
@pytest.mark.parametrize("sade", ["1", "0"])
def test_successful_retest_never_contradicts_its_own_state(monkeypatch, seen, sade):
    import notifier

    monkeypatch.setenv("TELEGRAM_KART_SUZGEC", sade)
    monkeypatch.setattr(notifier, "TELEGRAM_ALERT_STYLE", "kart")
    message = notifier.TelegramNotifier().format_message({
        "stock_name": "AKBNK", "timeframe": "4h", "pattern_name": "Üçgen",
        "state": "RETEST_BASARILI", "break_dir": 1, "break_price": 70,
        "candle_close_price": 71, "retest_seen": seen,
    })
    assert "SEVİYE KORUNDU" in message
    assert "dönüş yok" not in message and "retest yok" not in message
    assert "dönüş var" in message or "retest var" in message


@pytest.mark.parametrize("seen, expected", [
    (True, "dönüş var"), (False, "dönüş yok"),
    (None, "dönüşü bilinmiyor"), ("not-a-boolean", "dönüşü bilinmiyor"),
])
def test_alert_distinguishes_absent_retest_data_from_negative(monkeypatch, seen, expected):
    import notifier

    monkeypatch.setenv("TELEGRAM_KART_SUZGEC", "1")
    monkeypatch.setattr(notifier, "TELEGRAM_ALERT_STYLE", "kart")
    message = notifier.TelegramNotifier().format_message({
        "stock_name": "AKBNK", "timeframe": "4h", "state": "KIRILIM_TEYITLI",
        "break_price": 70, "candle_close_price": 71, "retest_seen": seen,
    })
    assert expected in message
    assert "1g onayı bilinmiyor" in message


@pytest.mark.parametrize("timeframe, fields, expected", [
    ("2h", {"mtf_destek": False, "mtf_uyum": 0, "mtf_kontrol_edildi": False},
     "4s onayı bilinmiyor"),
    ("1h", {"mtf_destek": False, "mtf_uyum": 0, "mtf_kontrol_edildi": True},
     "4s onayı yok"),
    ("4h", {"mtf_destek": True, "mtf_uyum": 4, "mtf_kontrol_edildi": True},
     "1g onayı var ✓ — uyumlu"),
    ("4h", {"mtf_destek": None, "mtf_uyum": None}, "1g onayı bilinmiyor"),
    ("4h", {"mtf_destek": True, "mtf_uyum": 0, "mtf_kontrol_edildi": True,
            "mtf_yon_biliniyor": False}, "1g formasyonu · yön belirsiz"),
])
def test_alert_never_reports_unchecked_mtf_as_no_confirmation(monkeypatch, timeframe, fields, expected):
    import notifier

    monkeypatch.setenv("TELEGRAM_KART_SUZGEC", "1")
    monkeypatch.setattr(notifier, "TELEGRAM_ALERT_STYLE", "kart")
    message = notifier.TelegramNotifier().format_message({
        "stock_name": "AKBNK", "timeframe": timeframe, "state": "KIRILIM_TEYITLI",
        "break_price": 70, "candle_close_price": 71, **fields,
    })
    assert expected in message


def test_long_month_candle_range_wraps_as_two_meaningful_lines(monkeypatch):
    import notifier
    from telegram_measure import genislik

    monkeypatch.setenv("TELEGRAM_KART_SUZGEC", "1")
    monkeypatch.setattr(notifier, "TELEGRAM_ALERT_STYLE", "kart")
    message = notifier.TelegramNotifier().format_message({
        "stock_name": "AKBNK", "timeframe": "4h", "state": "KIRILIM_TEYITLI",
        "bar_time": "2026-08-24T10:30:00+00:00",
        "bar_kapanis": "2026-08-24T17:30:00+03:00",
    })
    assert "🕒 24 Ağustos mumu\n   13:30→17:30" in message
    assert not any(line.strip() == "mumu" for line in message.splitlines())
    assert all(genislik(line) <= notifier._kart_esik_px() for line in message.splitlines())


def test_karma_evren_panel_ve_sayaclari_sembol_olarak_adlandirilir(monkeypatch):
    import copy

    import main as M
    from live_state import LiveState

    stocks = ["THYAO", "XU100", "BRENT"]
    monkeypatch.setattr(M, "ACTIVE_STOCKS", stocks)
    monkeypatch.setattr(M, "_daily_pattern_keys", set())
    monkeypatch.setattr(M, "daily_stats", copy.deepcopy(M.daily_stats))
    state = LiveState()
    state.begin_scan(beklenen_hisse=3)
    state.finish_scan(son_tarama_hissesi=3, son_tarama_beklenen_hisse=3)
    monkeypatch.setattr(M, "_live_state", state)
    M._note_pattern_found("XU100", "1h")
    panel = M._panel_raporu("")
    assert "3 sembol x 4 TF" in panel
    assert "hesaplanan 3/3 sembol" in panel
    assert "3 hisse x 4 TF" not in panel
    durum = M._komut_durum("")
    assert "1 formasyonlu sembol" in durum
    assert "Semboller tekil" in durum
