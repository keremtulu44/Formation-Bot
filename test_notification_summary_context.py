from datetime import datetime

from notifier import TelegramNotifier


def _formatter():
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    notifier.public_sikisma_min = 0.8
    return notifier


def _stale_summary():
    return {
        "tarama_sayisi": 4,
        "alerts_sent": 2,
        "kirilim_teyitli_olay_sayisi": 3,
        "retest_basarili_olay_sayisi": 2,
        "kirilim_gecersizlesti_olay_sayisi": 1,
        "son_basarili_tam_tarama": "2026-10-11T18:00:00+03:00",
        "tam_tarama_guncel": False,
    }


def _old_formations():
    return [
        {
            "stock_name": "THYAO",
            "timeframe": "1h",
            "pattern_name": "Yükselen Üçgen",
            "state": "KIRILIM_TEYITLI",
            "confidence_score": 86,
            "break_dir": 1,
        },
        {
            "stock_name": "GARAN",
            "timeframe": "2h",
            "pattern_name": "Alçalan Üçgen",
            "state": "RETEST_BASARILI",
            "confidence_score": 81,
            "break_dir": -1,
        },
    ]


def test_daily_summary_counts_transitions_and_does_not_present_stale_formations():
    notifier = _formatter()
    message = notifier.format_daily_summary(_old_formations(), _stale_summary())

    assert "THYAO" not in message and "GARAN" not in message
    assert "önceki formasyon listesi gösterilmedi" in message
    assert "3 teyitli kırılım · 2 başarılı retest · 1 teyit sonrası geçersizleşme" in message
    assert "Son başarılı tam tarama: 11 Eki 18:00" in message
    assert "güncel tam tarama yok" in message
    assert "yatırım tavsiyesi değildir" in message


def test_public_daily_summary_reports_counts_and_hides_stale_snapshot():
    notifier = _formatter()
    message = notifier.format_public_summary(
        _old_formations(), _stale_summary(), izleme=_old_formations(), kapanis=True
    )

    assert "THYAO" not in message and "GARAN" not in message
    assert "eski formasyon listesi gösterilmedi" in message
    assert "3 teyitli kırılım · 2 başarılı retest · 1 teyit sonrası geçersizleşme" in message
    assert "Son başarılı tam tarama: 11 Eki 18:00" in message


def test_current_daily_summary_labels_fresh_full_scan_and_keeps_current_results():
    notifier = _formatter()
    now = datetime.now().astimezone().isoformat()
    payload = {
        "kirilim_teyitli_olay_sayisi": 0,
        "retest_basarili_olay_sayisi": 0,
        "kirilim_gecersizlesti_olay_sayisi": 0,
        "son_basarili_tam_tarama": now,
        "tam_tarama_guncel": True,
        "tarama_sayisi": 1,
        "alerts_sent": 1,
    }
    message = notifier.format_daily_summary(_old_formations(), payload)

    assert "THYAO" in message
    assert "· güncel" in message
    assert "0 teyitli kırılım · 0 başarılı retest · 0 teyit sonrası geçersizleşme" in message
