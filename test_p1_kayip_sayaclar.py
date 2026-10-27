# -*- coding: utf-8 -*-
"""P1 — kayıp sayaçlar panel/özet/heartbeat'e görünür olmalı"""

def test_panel_hunisi_daily_stats_ile():
    from reporting.panel import panel_raporu
    from config import ACTIVE_STOCKS
    daily = {
        "patterns_found": 18,
        "alerts_sent": 5,
        "alerts_deferred": 7,
        "alerts_state_disabled": 3,
        "alerts_below_threshold": 3,
        "alerts_kuyruk": 2,
        "alerts_bar_kapanmadi": 1,
        "alerts_break_close_invalid": 1,
    }
    # boş formation listesi ama hunisi gösterilmeli
    metin = panel_raporu(
        arguman="",
        durum={"son_tarama_durumu": "tamamlandi", "son_tarama_bitis": "2026-10-27T10:00:00+03:00"},
        formations=[],
        aktif_hisseler=list(ACTIVE_STOCKS)[:4],
        daily_stats=daily,
        bos_analiz_mesaji="henüz yok",
    )
    assert "Huni" in metin, metin[:500]
    assert "18 üretildi" in metin
    assert "eşik altı" in metin
    # bar kapanmadı ve kapanış teyidi de görünmeli
    assert "kapanmamış bar" in metin or "kapanış teyidi" in metin


def test_summary_hunisi():
    # 2026-10-27: Huni artık akşam özetinden kalktı (panel/durum/heartbeat'te duruyor)
    from notifier.api import TelegramNotifier
    n = TelegramNotifier.__new__(TelegramNotifier)
    n.public_sikisma_min = 0.5
    gun_ozeti = {
        "tarama_sayisi": 9,
        "alerts_sent": 5,
        "patterns_found": 18,
        "alerts_below_threshold": 3,
        "alerts_state_disabled": 2,
        "alerts_deferred": 7,
        "alerts_kuyruk": 1,
        "alerts_bar_kapanmadi": 1,
        "alerts_break_close_invalid": 1,
        "tam_tarama_guncel": True,
        "son_basarili_tam_tarama": "2026-10-27T10:00:00+03:00",
    }
    metin = n.format_daily_summary([], gun_ozeti=gun_ozeti)
    assert "Huni" not in metin and "huni" not in metin.lower()
    assert "yatırım tavsiyesi değildir" in metin


def test_heartbeat_aday_hunisi_var():
    import pathlib
    hb = pathlib.Path("bot/heartbeat.py").read_text(encoding="utf-8")
    assert "aday_hunisi" in hb
    assert "alerts_below_threshold" in hb or "esik_alti" in hb


def test_durum_hunisi_var():
    import pathlib
    cm = pathlib.Path("bot/commands.py").read_text(encoding="utf-8")
    assert "Aday hunisi" in cm or "aday hunisi" in cm.lower()
    assert "alerts_below_threshold" in cm
