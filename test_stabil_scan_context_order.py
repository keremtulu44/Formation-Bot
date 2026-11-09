"""The ordinary scan supplies closed structure data even with no formation alert."""
import copy
from types import SimpleNamespace

import pandas as pd


def test_scan_builds_domain_context_before_stabil_without_formation(monkeypatch):
    import main
    import bot.stabil_service as service
    from test_domain_integration_regressions import _valid_frame

    frame = _valid_frame(50)
    calls = []
    class Manager:
        sureklilik_sorunlari = {}
        def to_dataframe(self, _): return frame.copy()
        def to_gunluk_dataframe(self, _): return None
        def gunluk_veri_eksik_mi(self, *_): return False
        def save_to_disk(self, _): pass
    class Lifecycle:
        def scan(self, *_a, **_k):
            return SimpleNamespace(state="Yok", break_dir=0, log="", active=None, events=[])
        def get_snapshot(self, *_): return None
    class State:
        def begin_scan(self, *_a, **_k): pass
        def record_formation(self, *_a, **_k): pass
        def finish_scan(self, *_a, **_k): pass
        def fail_scan(self, *_a, **_k): pass
    class Notifier:
        def public_bosalt(self): return 0
    def domain(stock, tf, data, *, profile):
        calls.append("domain")
        return {"market_structure": SimpleNamespace(details={"event_history": []})}
    def stabil(stock, all_tfs, now, *, domain_results_by_stock, **kwargs):
        calls.append("stabil")
        assert "market_structure" in domain_results_by_stock[stock]["4h"]
        return None
    monkeypatch.setattr(main, "ACTIVE_STOCKS", ["AUDIT"])
    monkeypatch.setattr(main, "daily_stats", copy.deepcopy(main.daily_stats))
    monkeypatch.setattr(main, "_live_state", State())
    monkeypatch.setattr(main, "_deferred_alert_buffer", SimpleNamespace(observe=lambda *_a, **_k: None))
    monkeypatch.setattr(main, "_load_domain_runner", lambda: domain)
    monkeypatch.setattr(main, "fetch_1h_stocks_paced", lambda *_a, **_k: ({}, {}, 0, 0))
    monkeypatch.setattr(main, "create_yahoo_pacer", lambda: object())
    monkeypatch.setattr(main, "select_yfinance_1h_period", lambda *_: "5d")
    monkeypatch.setattr(main, "resample_all_timeframes", lambda _: {"4h": frame})
    monkeypatch.setattr(main, "tarama_penceresi_acik_mi", lambda *_: False)
    monkeypatch.setattr(main, "_cache_verisi_kullanilabilir", lambda *_a, **_k: True)
    monkeypatch.setattr(main, "_alarm_izni_var", lambda *_: True)
    monkeypatch.setattr(main, "reset_daily_if_needed", lambda: None)
    monkeypatch.setattr(main, "write_heartbeat", lambda **_k: None)
    monkeypatch.setattr(main, "son_tarama_kaydet", lambda: None)
    monkeypatch.setattr(main, "_shutdown_requested", False)
    monkeypatch.setattr(service, "evaluate_stabil_4h_candidate", stabil)
    result = main.scan_all_stocks(Manager(), Lifecycle(), Notifier(), stocks=["AUDIT"], send_alerts=True)
    assert result["status"] == "tamamlandi"
    assert calls == ["domain", "stabil"]
