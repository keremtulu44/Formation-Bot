"""End-to-end chart paths; the resistance layer never creates alarm candidates."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import config
import grafik
import grafik_uret
from data import mum_kapanis_anlari, resample_all_timeframes, seans_sonu_saati, tamamlanmis_mumlar
from domain_engines.runner import run_stabil_symbol_bundle
from test_stabil_resistance_chart_bridge import _frames


class _Manager:
    def __init__(self, daily, hourly, root):
        self.daily, self.hourly = daily, hourly
        self.data_dir = str(root)
        self.deques = {"AKBNK": object()}
        self.gunluk_deques = {"AKBNK": object()} if daily is not None else {}
        self.sureklilik_sorunlari = {}

    def to_dataframe(self, _symbol):
        return self.hourly.copy(deep=True)

    def to_gunluk_dataframe(self, _symbol):
        return self.daily.copy(deep=True) if self.daily is not None else None

    def _okuma_yolu(self, name):
        return str(Path(self.data_dir) / name)

    def gunluk_veri_eksik_mi(self, *_args):
        return False

    def save_to_disk(self, _symbol):
        return None


def _larger_frames():
    daily, _ = _frames()
    labels = []
    for day in daily.index[-15:]:
        label = day + pd.Timedelta(hours=9, minutes=30)
        end_time = seans_sonu_saati(day.date())
        end = day + pd.Timedelta(hours=end_time.hour, minutes=end_time.minute)
        while label < end:
            labels.append(label)
            label += pd.Timedelta(hours=1)
    prices = 102.0 + np.arange(len(labels)) * 0.007
    hourly = pd.DataFrame({"open": prices, "high": prices + 0.7, "low": prices - 0.7,
                           "close": prices + 0.1, "volume": 1000.0}, index=pd.DatetimeIndex(labels))
    now = pd.Timestamp(daily.index[-1].date(), tz="Europe/Istanbul") + pd.Timedelta(hours=18, minutes=35)
    return daily, hourly, now


def _support_results(daily, hourly, now):
    frames = {tf: tamamlanmis_mumlar(frame, tf, now=now)
              for tf, frame in resample_all_timeframes(hourly).items() if tf != "1d"}
    frames["1d"] = tamamlanmis_mumlar(daily, "1d", now=now)
    bundle = run_stabil_symbol_bundle("AKBNK", frames, daily_frame=daily, h4_frame=frames["4h"],
                                      as_of_close=now, isolated=True)
    return frames, {tf: {"stabil": result} for tf, result in bundle.items()}


@pytest.mark.parametrize("tf,switch", [("1h", "yok"), ("2h", "yok"), ("4h", "yok"),
                                        ("1d", "yok"), ("4h", "false")])
def test_grafik_uret_builds_real_resistance_overlay_without_alarm_kill_switch(tf, switch, tmp_path, monkeypatch):
    daily, hourly, now = _larger_frames()
    manager = _Manager(daily, hourly, tmp_path)
    monkeypatch.setenv("TELEGRAM_GRAFIK", switch)  # manual /grafik is independent of automatic graphics
    observed = []
    draw = grafik.ciz

    def capture(snapshot, *args, **kwargs):
        observed.append(snapshot)
        return draw(snapshot, *args, **kwargs)

    monkeypatch.setattr(grafik, "ciz", capture)
    answer = grafik_uret.kare_uret("AKBNK", tf, zone=True, yonetici=manager, simdi=now,
                                    cikti=str(tmp_path / f"manual_{tf}.png"))
    assert answer["hata"] is None and Path(answer["yol"]).stat().st_size > 10000
    layer = observed[0]["stabil_direnc"]
    assert layer["hazir"] and layer["durum"] == "READY" and layer["son_seviye"] > 0
    assert observed[0]["stabil"] is not None
    drawn = answer["meta"]["cizgiler"]["stabil_direnc"]
    if tf in {"1h", "2h"}:
        assert answer["meta"]["stabil_cizimde_gizli"] and not drawn["cizildi"]
    else:
        assert drawn["son_seviye"] == layer["son_seviye"]
    assert not any("Stabil direnç gösterilemedi" in msg for msg in answer["meta"]["uyarilar"])


def test_grafik_without_native_daily_still_draws_old_chart_and_explains_absence(tmp_path, monkeypatch):
    _, hourly, now = _larger_frames()
    manager = _Manager(None, hourly, tmp_path)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    answer = grafik_uret.kare_uret("AKBNK", "4h", zone=True, yonetici=manager, simdi=now,
                                    cikti=str(tmp_path / "missing.png"))
    assert answer["yol"] and Path(answer["yol"]).stat().st_size > 10000
    assert not answer["meta"]["cizgiler"]["stabil_direnc"]["hazir"]
    assert answer["meta"]["cizgiler"]["stabil_direnc"]["neden"] == "missing_source"
    assert any("gerekli günlük veya saatlik kaynak yok" in x for x in answer["meta"]["uyarilar"])


def test_real_manual_command_worker_includes_layer_without_sending_telegram(tmp_path, monkeypatch):
    import bot.commands as commands
    import main

    daily, hourly, _now = _larger_frames()
    manager = _Manager(daily, hourly, tmp_path)
    observed = []
    draw = grafik.ciz

    def capture(snapshot, *args, **kwargs):
        observed.append(snapshot)
        return draw(snapshot, *args, **kwargs)

    sent_pngs = []

    def collect(packets):
        for path, caption in packets:
            sent_pngs.append((Path(path).read_bytes(), caption))
            Path(path).unlink(missing_ok=True)
        return [True] * len(packets)

    notifier = SimpleNamespace(token="", enabled=True, grafik_toplu_gonder=collect,
                               send_text=lambda _msg: (True, ""))
    monkeypatch.setattr(grafik, "ciz", capture)
    monkeypatch.setattr(commands, "_grafik_cache_tazelik_durumu", lambda *_a, **_k: {"taze": True})
    # Existing command worker, with network/Telegram replaced by in-memory fakes.
    main._grafik_isi_yurut({"hisse": "AKBNK", "tfler": ("4h",), "sade": False}, notifier, manager)
    assert len(sent_pngs) == 1 and sent_pngs[0][0].startswith(b"\x89PNG")
    assert observed and observed[0]["stabil_direnc"]["hazir"]


def test_stabil_support_alarm_4h_and_1d_graphs_add_layer_without_mutating_results(monkeypatch):
    from bot.stabil_service import _stabil_public_grafik_verisi_uret

    daily, hourly, now = _larger_frames()
    frames, results = _support_results(daily, hourly, now)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    before = {tf: dict(entry) for tf, entry in results.items()}
    answer = _stabil_public_grafik_verisi_uret(
        "AKBNK", frames["4h"], frames["1d"], now, {"AKBNK": results}, results["4h"]["stabil"],
        direnc_gunluk_ham=daily, direnc_saatlik_ham=hourly,
    )
    assert [row["tf"] for row in answer["goruntular"]] == ["4h", "1d"]
    assert answer["goruntular"][1]["rol"] == "ust"
    for row in answer["goruntular"]:
        assert row["goruntu"]["stabil_direnc"]["hazir"], row["goruntu"]["stabil_direnc"]
        old = grafik.anlik_goruntu(None, row["tf"], frames[row["tf"]],
                                    sonuclar=results[row["tf"]], simdi=now)
        assert row["goruntu"]["stabil"] == old["stabil"] is not None
    assert results == before
    assert all("stabil_direnc" not in entry for entry in results.values())


def test_domain_alarm_dm_and_public_share_resistance_without_changing_support(monkeypatch, tmp_path):
    from bot.domain_alarm_service import _grafik_verisi_uret

    daily, hourly, now = _larger_frames()
    frames, results = _support_results(daily, hourly, now)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "1")
    before = {tf: dict(entry) for tf, entry in results.items()}
    cache = {}
    dm, public = _grafik_verisi_uret("AKBNK", "4h", frames["4h"], frames, results, now, None,
                                    direnc_gunluk_ham=daily, direnc_saatlik_ham=hourly,
                                    direnc_cache=cache)
    assert [k["tf"] for k in dm["goruntular"]] == ["4h"]
    assert [k["tf"] for k in public["goruntular"]] == ["4h", "1d"]
    assert set(cache) == {"4h", "1d"}  # only emitted TFs, reused for both audiences
    assert dm["goruntular"][0]["goruntu"]["stabil_direnc"] == public["goruntular"][0]["goruntu"]["stabil_direnc"]
    assert all(k["goruntu"]["stabil_direnc"]["hazir"] for k in public["goruntular"])
    path, meta = grafik.ciz(public["goruntular"][0]["goruntu"], "4h",
                             secenekler={"cikti": str(tmp_path / "domain.png")})
    assert path and meta["cizgiler"]["stabil_direnc"]["cizildi"]
    assert results == before and all("stabil_direnc" not in e for e in results.values())


def test_domain_candidate_and_text_are_identical_with_graphics_on_or_off(monkeypatch):
    from bot.domain_alarm_service import evaluate_domain_alarm_candidates, format_domain_alarm_card
    import domain_engines.stabil.chart_bridge as bridge

    daily, hourly, now = _larger_frames()
    frames, results = _support_results(daily, hourly, now)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_TAZE_DK", 10000)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_IMMEDIATE_TEKRAR", True)
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "2")
    pattern = [{"timeframe": tf, "state": "KIRILIM_TEYITLI", "quality": 90,
                "min_quality": 50, "pattern_name": "Üçgen"} for tf in ("1h", "2h", "4h")]
    args = ("AKBNK", {**frames, "1h": hourly}, frames, results, now)
    calls = []
    original = bridge.resistance_for_chart

    def counted(*a, **kw):
        assert a[0] == "AKBNK" and kw["daily_frame"] is daily and kw["hourly_frame"] is hourly
        assert pd.Timestamp(kw["as_of_close"]) == now
        calls.append(a[1])
        return original(*a, **kw)

    monkeypatch.setattr(bridge, "resistance_for_chart", counted)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    old = evaluate_domain_alarm_candidates(*args, formasyon_kayitlari=pattern, direnc_gunluk_ham=daily)
    assert not calls
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    new = evaluate_domain_alarm_candidates(*args, formasyon_kayitlari=pattern, direnc_gunluk_ham=daily)
    assert len(old) == len(new) == 3
    assert set(calls) == {"1h", "2h", "4h", "1d"} and len(calls) == 4
    for a, b in zip(old, new):
        assert replace(a, grafik_verisi=None, grafik_verisi_public=None) == replace(
            b, grafik_verisi=None, grafik_verisi_public=None)
        assert format_domain_alarm_card(a) == format_domain_alarm_card(b)
        assert b.grafik_verisi is not None and b.grafik_verisi_public is not None


def test_graphics_kill_switch_skips_all_resistance_calculations(monkeypatch):
    from bot.domain_alarm_service import _grafik_verisi_uret
    from bot.stabil_service import _stabil_public_grafik_verisi_uret
    import domain_engines.stabil.chart_bridge as bridge

    daily, hourly, now = _larger_frames()
    frames, results = _support_results(daily, hourly, now)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    monkeypatch.setattr(bridge, "resistance_for_chart", lambda *_a, **_k: pytest.fail("kill-switch"))
    assert _stabil_public_grafik_verisi_uret(
        "AKBNK", frames["4h"], frames["1d"], now, {"AKBNK": results}, results["4h"]["stabil"],
        direnc_gunluk_ham=daily, direnc_saatlik_ham=hourly,
    ) is None
    assert _grafik_verisi_uret("AKBNK", "4h", frames["4h"], frames, results, now, None,
                               direnc_gunluk_ham=daily, direnc_saatlik_ham=hourly) == (None, None)


@pytest.mark.parametrize("invalidation", [False, True])
def test_full_formation_scan_preserves_alert_and_adds_dm_public_charts(
    monkeypatch, tmp_path, invalidation,
):
    """The real scan's nested bridge is exercised; no network/Telegram calls."""
    import copy
    import main
    import domain_engines.stabil.chart_bridge as bridge

    daily, hourly, now = _larger_frames()
    manager = _Manager(daily, hourly, tmp_path)
    frames, results = _support_results(daily, hourly, now)
    expected_bar = len(frames["4h"]) - 1
    last_price = float(frames["4h"]["close"].iloc[-1])
    active = SimpleNamespace(
        raw_quality=92.0, pattern_type="Simetrik Üçgen", upper_now=last_price - 0.5,
        lower_now=last_price - 5, frozen_upper_boundary_at_break=(last_price + 1 if invalidation else last_price - 0.5),
        frozen_lower_boundary_at_break=last_price - 5, stable_id="resistance-chart-audit",
        start_bar=4, break_strength=91.0, contraction=0.6, upper_touches=3, lower_touches=2,
    )
    events = []
    if invalidation:
        events = [
            {"type": "BREAK_CONFIRMED", "state": "KIRILIM_TEYITLI", "bar": expected_bar - 1,
             "time": (now - pd.Timedelta(minutes=5)).isoformat(), "stable_id": active.stable_id,
             "direction": 1, "quality": 92.0, "price": last_price + 1.5},
            {"type": "BREAK_FAILED", "state": "BASARISIZ_KIRILIM", "bar": expected_bar,
             "time": now.isoformat(), "stable_id": active.stable_id, "direction": 1,
             "quality": 92.0, "price": last_price},
        ]

    class Lifecycle:
        def scan(self, key, frame, *, tam_yeniden):
            if not key.endswith("_4h"):
                return SimpleNamespace(state="Yok", break_dir=0, log="", active=None)
            return SimpleNamespace(state="BASARISIZ_KIRILIM" if invalidation else "KIRILIM_TEYITLI",
                                   invalid_reason="Kırılım sonrası formasyon alanına dönüldü" if invalidation else "Yok",
                                   events=events, break_dir=1, log="test", active=active,
                                   effective_quality=92.0, bar_index=len(frame) - 1, retest_seen=False)

        def get_snapshot(self, _key):
            return None

    class State:
        def begin_scan(self, *_a, **_k): pass
        def record_formation(self, *_a, **_k): pass
        def mark_alert_sent(self, *_a, **_k): pass
        def finish_scan(self, *_a, **_k): pass
        def fail_scan(self, *_a, **_k): pass

    class Notifier:
        def __init__(self):
            self.sent = []
        def send(self, payload):
            self.sent.append(dict(payload))
            return True
        def public_kuyruk(self, _payload): pass
        def teyit_teslim_edildi_mi(self, _fid): return True
        def grafik_kopru_hatasi(self, message):
            raise AssertionError(f"formation chart bridge failed: {message}")

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            value = now.to_pydatetime()
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)

    monkeypatch.setattr(main, "datetime", Frozen)
    monkeypatch.setattr(main, "ACTIVE_STOCKS", ["AKBNK"])
    monkeypatch.setattr(main, "_live_state", State())
    monkeypatch.setattr(main, "_deferred_alert_buffer", SimpleNamespace(observe=lambda *_a, **_k: None))
    monkeypatch.setattr(main, "fetch_1h_stocks_paced", lambda *_a, **_k: ({}, {}, 0, 0))
    monkeypatch.setattr(main, "create_yahoo_pacer", lambda: object())
    monkeypatch.setattr(main, "select_yfinance_1h_period", lambda *_a: "5d")
    monkeypatch.setattr(main, "tarama_penceresi_acik_mi", lambda *_a: False)
    monkeypatch.setattr(main, "_cache_verisi_kullanilabilir", lambda *_a, **_k: True)
    monkeypatch.setattr(main, "_domain_results_for_notification", lambda *_a, **_k: results)
    monkeypatch.setattr(main, "reset_daily_if_needed", lambda: None)
    monkeypatch.setattr(main, "write_heartbeat", lambda **_k: None)
    monkeypatch.setattr(main, "son_tarama_kaydet", lambda: None)
    monkeypatch.setattr(main, "_shutdown_requested", False)
    monkeypatch.setattr(main, "_public_turu_kapat", lambda *_a: None)
    monkeypatch.setattr(main, "_grafikleri_tur_sonunda", lambda *_a: None)
    monkeypatch.setattr(main, "_karne_olay_kaydet", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "_ileri_test_kaydet", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "_gun_sayacini_gonderimle_hizala", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "_record_daily_lifecycle_events", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "_note_pattern_found", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "_note_basarisiz_kirilim", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "_note_unannounced_invalidation", lambda *_a, **_k: None)
    monkeypatch.setattr(config, "STABIL_GERI_ALIM_ALARM", False)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", False)
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "1")

    original_resistance = bridge.resistance_for_chart
    calls = []
    def counted(*args, **kwargs):
        assert args[0] == "AKBNK" and args[1] in {"4h", "1d"}
        pd.testing.assert_frame_equal(kwargs["daily_frame"], daily)
        pd.testing.assert_frame_equal(kwargs["hourly_frame"], hourly)
        assert pd.Timestamp(kwargs["as_of_close"]) == now
        calls.append(args[1])
        return original_resistance(*args, **kwargs)
    monkeypatch.setattr(bridge, "resistance_for_chart", counted)

    def scan(switch):
        monkeypatch.setenv("TELEGRAM_GRAFIK", switch)
        stats = copy.deepcopy(main.daily_stats)
        stats["max_bar_age_min"] = None
        monkeypatch.setattr(main, "daily_stats", stats)
        notifier = Notifier()
        report = main.scan_all_stocks(manager, Lifecycle(), notifier, stocks=["AKBNK"], send_alerts=True)
        assert report["status"] == "tamamlandi", report
        assert len(notifier.sent) == 1
        return notifier.sent[0]

    old = scan("yok")
    assert calls == []  # disabled graphs do not calculate resistance
    new = scan("alarm")
    remove = {"grafik_verisi", "grafik_verisi_public"}
    assert {k: v for k, v in old.items() if k not in remove} == {
        k: v for k, v in new.items() if k not in remove
    }
    assert len(new["grafik_verisi"]["goruntular"]) == 1
    public = new["grafik_verisi_public"]["goruntular"]
    assert [x["tf"] for x in public] == (["4h"] if invalidation else ["4h", "1d"])
    assert all(x["goruntu"]["stabil_direnc"]["hazir"] for x in public)
    assert all(x["goruntu"]["stabil"] is not None for x in public)
    assert calls == (["4h"] if invalidation else ["4h", "1d"])
    assert all("stabil_direnc" not in per_tf for per_tf in results.values())
    path, meta = grafik.ciz(public[0]["goruntu"], "4h", secenekler={"cikti": str(tmp_path / "formation.png")})
    assert path and meta["cizgiler"]["stabil_direnc"]["cizildi"]

    def broken(*_args, **_kwargs):
        raise RuntimeError("isolated test failure")

    monkeypatch.setattr(bridge, "resistance_for_chart", broken)
    failed = scan("alarm")
    assert {k: v for k, v in old.items() if k not in remove} == {
        k: v for k, v in failed.items() if k not in remove
    }
    failed_img = failed["grafik_verisi"]["goruntular"][0]["goruntu"]
    assert failed_img["stabil"] == new["grafik_verisi"]["goruntular"][0]["goruntu"]["stabil"]
    assert failed_img["stabil_direnc"]["neden"] == "chart_bridge_error:RuntimeError"
    assert not failed_img["stabil_direnc"]["hazir"]
    assert any("Stabil direnç gösterilemedi" in w for w in failed_img["uyarilar"])


def test_real_archived_stabil_reclaim_candidate_and_notifications_are_unchanged(tmp_path, monkeypatch):
    """AKBNK 23 Mar 2026 17:30: an actual native 4H support reclaim, not a fake behavior."""
    from bot.stabil_service import (dispatch_stabil_scan_candidates, evaluate_stabil_4h_candidate,
                                    format_stabil_reclaim_alert_card)
    from research.arsiv import ham_frame

    now = pd.Timestamp("2026-03-23 17:30", tz="Europe/Istanbul")
    daily = ham_frame("AKBNK", "1d")
    hourly = tamamlanmis_mumlar(ham_frame("AKBNK", "1h"), "1h", now=now).iloc[-360:]
    frames = resample_all_timeframes(hourly)
    frames["1d"] = daily
    completed = {tf: tamamlanmis_mumlar(frame, tf, now=now) for tf, frame in frames.items()}
    bundle = run_stabil_symbol_bundle("AKBNK", completed, daily_frame=daily, h4_frame=completed["4h"],
                                      as_of_close=now, isolated=True)
    results = {"AKBNK": {tf: {"stabil": value} for tf, value in bundle.items()}}
    before = results["AKBNK"]["4h"]["stabil"].result.latest_behavior
    assert before.reclaim_kind is None
    assert before.support_level == pytest.approx(69.30, abs=.01)
    assert before.close_price == pytest.approx(72.50, abs=.01)
    monkeypatch.setattr(config, "STABIL_GERI_ALIM_ALARM", True)
    assert evaluate_stabil_4h_candidate(
        "AKBNK", frames, now, domain_results_by_stock=results,
        direnc_gunluk_ham=daily, state_path=str(tmp_path / "state.json"),
    ) is None


def test_automatic_graphs_report_exception_but_keep_existing_layers(monkeypatch, tmp_path):
    from bot.domain_alarm_service import _grafik_verisi_uret
    from bot.stabil_service import _stabil_public_grafik_verisi_uret
    import domain_engines.stabil.chart_bridge as bridge

    daily, hourly, now = _larger_frames()
    frames, results = _support_results(daily, hourly, now)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "1")
    before = {tf: grafik.anlik_goruntu(None, tf, frames[tf], sonuclar=results[tf], simdi=now)["stabil"]
              for tf in ("4h", "1d")}

    def broken(*_a, **_k):
        raise RuntimeError("isolation")

    monkeypatch.setattr(bridge, "resistance_for_chart", broken)
    st = _stabil_public_grafik_verisi_uret("AKBNK", frames["4h"], frames["1d"], now,
                                            {"AKBNK": results}, results["4h"]["stabil"],
                                            direnc_gunluk_ham=daily, direnc_saatlik_ham=hourly)
    dm, pub = _grafik_verisi_uret("AKBNK", "4h", frames["4h"], frames, results, now, None,
                                   direnc_gunluk_ham=daily, direnc_saatlik_ham=hourly)
    assert len(dm["goruntular"]) == 1
    for package in (st, pub):
        assert [k["tf"] for k in package["goruntular"]] == ["4h", "1d"]
        for row in package["goruntular"]:
            snap = row["goruntu"]
            assert snap["stabil"] == before[row["tf"]]
            assert snap["stabil_direnc"]["neden"] == "chart_bridge_error:RuntimeError"
            assert not snap["stabil_direnc"]["hazir"]
            assert any("Stabil direnç gösterilemedi" in warning for warning in snap["uyarilar"])
    answer = grafik_uret.kare_uret("AKBNK", "4h", zone=True, yonetici=_Manager(daily, hourly, tmp_path),
                                    simdi=now, cikti=str(tmp_path / "broken.png"))
    assert answer["yol"] and answer["meta"]["cizgiler"]["stabil"]["hazir"]
    assert answer["meta"]["cizgiler"]["stabil_direnc"]["neden"] == "chart_bridge_error:RuntimeError"


def test_domain_invalidation_selects_only_its_public_frame_and_calculates_once(monkeypatch):
    from bot.domain_alarm_service import _grafik_verisi_uret
    import domain_engines.stabil.chart_bridge as bridge

    daily, hourly, now = _larger_frames()
    frames, results = _support_results(daily, hourly, now)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "4")
    original = bridge.resistance_for_chart
    calls = []
    def counted(*args, **kwargs):
        calls.append(args[1])
        return original(*args, **kwargs)
    monkeypatch.setattr(bridge, "resistance_for_chart", counted)
    dm, public = _grafik_verisi_uret(
        "AKBNK", "4h", frames["4h"], frames, results, now,
        {"cift": SimpleNamespace(start_bar=5, upper_now=104.0, lower_now=100.0),
         "state": "KIRILIM_GECERSIZLESTI", "alarm_bar": len(frames["4h"]) - 1},
        direnc_gunluk_ham=daily, direnc_saatlik_ham=hourly,
    )
    assert [k["tf"] for k in dm["goruntular"]] == ["4h"]
    assert [k["tf"] for k in public["goruntular"]] == ["4h"]
    assert calls == ["4h"]
    assert public["goruntular"][0]["goruntu"]["stabil_direnc"]["hazir"]


def test_split_or_missing_raw_daily_disables_only_resistance_in_all_automatic_charts(monkeypatch):
    from bot.domain_alarm_service import _grafik_verisi_uret
    from bot.stabil_service import _stabil_public_grafik_verisi_uret

    daily, hourly, now = _larger_frames()
    frames, results = _support_results(daily, hourly, now)
    split_daily = daily.copy(deep=True)
    split_daily.loc[split_daily.index[-5:], ["open", "high", "low", "close"]] *= .5
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    for raw, expected in [(split_daily, "daily_split_scale_unverified"), (None, "missing_source")]:
        st = _stabil_public_grafik_verisi_uret(
            "AKBNK", frames["4h"], frames["1d"], now, {"AKBNK": results}, results["4h"]["stabil"],
            direnc_gunluk_ham=raw, direnc_saatlik_ham=hourly,
        )
        dm, pub = _grafik_verisi_uret("AKBNK", "4h", frames["4h"], frames, results, now, None,
                                       direnc_gunluk_ham=raw, direnc_saatlik_ham=hourly)
        for package in (st, dm, pub):
            assert package and package["goruntular"]
            for row in package["goruntular"]:
                snap = row["goruntu"]
                assert snap["stabil"] is not None
                assert snap["stabil_direnc"]["neden"] == expected
                assert not snap["stabil_direnc"]["hazir"]


def test_domain_candidate_nonmapping_hourly_source_degrades_without_dropping_alarm(monkeypatch):
    from bot.domain_alarm_service import evaluate_domain_alarm_candidates

    daily, hourly, now = _larger_frames()
    frames, results = _support_results(daily, hourly, now)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_TAZE_DK", 10000)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_IMMEDIATE_TEKRAR", True)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    pattern = [{"timeframe": "4h", "state": "KIRILIM_TEYITLI", "quality": 90,
                "min_quality": 50, "pattern_name": "Üçgen"}]
    candidates = evaluate_domain_alarm_candidates("AKBNK", None, frames, results, now,
                                                   formasyon_kayitlari=pattern, direnc_gunluk_ham=daily)
    assert candidates
    row = next(c for c in candidates if c.timeframe == "4h")
    snap = row.grafik_verisi["goruntular"][0]["goruntu"]
    assert snap["stabil"] is not None
    assert snap["stabil_direnc"]["neden"] == "missing_source"


@pytest.mark.parametrize("simple", [False, True])
def test_manual_command_caption_reports_missing_resistance_unless_simple(simple, tmp_path, monkeypatch):
    import bot.commands as commands
    import main

    _, hourly, _ = _larger_frames()
    manager = _Manager(None, hourly, tmp_path)
    captions = []
    def collect(packets):
        for path, caption in packets:
            assert Path(path).read_bytes().startswith(b"\x89PNG")
            Path(path).unlink(missing_ok=True)
            captions.append(caption)
        return [True] * len(packets)
    notifier = SimpleNamespace(token="", enabled=True, grafik_toplu_gonder=collect,
                               send_text=lambda _msg: (True, ""))
    monkeypatch.setattr(commands, "_grafik_cache_tazelik_durumu", lambda *_a, **_k: {"taze": True})
    main._grafik_isi_yurut({"hisse": "AKBNK", "tfler": ("4h",), "sade": simple}, notifier, manager)
    assert len(captions) == 1
    assert ("Stabil direnç gösterilemedi: gerekli günlük veya saatlik kaynak yok" in captions[0]) is not simple


def test_real_alarm_snapshot_survives_durable_dm_and_public_json_render(monkeypatch, tmp_path):
    import base64
    from bot.domain_alarm_service import _grafik_verisi_uret
    from notification_delivery import DeliveryOutbox, freeze

    daily, hourly, now = _larger_frames()
    frames, results = _support_results(daily, hourly, now)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "1")
    dm, pub = _grafik_verisi_uret("AKBNK", "4h", frames["4h"], frames, results, now, None,
                                   direnc_gunluk_ham=daily, direnc_saatlik_ham=hourly)
    restored_public = freeze(pub)
    assert [k["tf"] for k in restored_public["goruntular"]] == ["4h", "1d"]
    for original, restored in zip(pub["goruntular"], restored_public["goruntular"]):
        assert restored["goruntu"]["stabil_direnc"] == original["goruntu"]["stabil_direnc"]
        path, meta = grafik.ciz(restored["goruntu"], restored["tf"],
                                 secenekler={"cikti": str(tmp_path / f"public_{restored['tf']}.png")})
        assert path and meta["cizgiler"]["stabil_direnc"]["hazir"]

    # The existing durable DM outbox freezes the snapshot, then prepares an
    # actual PNG. Mock only its remote owner; no Telegram request is made.
    owner = SimpleNamespace(initial_store_data={}, persistent_store=None)
    box = DeliveryOutbox(owner, tmp_path / "state")
    row = {"data": {"stock_name": "AKBNK", "state": "KIRILIM_TEYITLI", "grafik_verisi": freeze(dm)}}
    box.state["rows"].append(row)
    actual_write = grafik.kareyi_yaz
    metas = []
    def capture(snapshot, tf):
        path, meta = actual_write(snapshot, tf)
        metas.append(meta)
        return path, meta
    monkeypatch.setattr(grafik, "kareyi_yaz", capture)
    box.prepare(row)
    assert row["prepared"] and len(row["images"]) == 1
    assert base64.b64decode(row["images"][0]["png"]).startswith(b"\x89PNG")
    assert metas[0]["cizgiler"]["stabil_direnc"]["cizildi"]
    restarted = DeliveryOutbox(owner, tmp_path / "state")
    saved = restarted.state["rows"][0]
    assert saved["images"][0]["caption"] == row["images"][0]["caption"]
    assert saved["data"]["grafik_verisi"]["goruntular"][0]["goruntu"]["stabil_direnc"] == (
        dm["goruntular"][0]["goruntu"]["stabil_direnc"])


def test_public_notifier_renders_resistance_album_with_transport_mocked(monkeypatch, tmp_path):
    from bot.domain_alarm_service import _grafik_verisi_uret
    import notifier
    import transport.telegram as telegram

    daily, hourly, now = _larger_frames()
    frames, results = _support_results(daily, hourly, now)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "1")
    _, public = _grafik_verisi_uret("AKBNK", "4h", frames["4h"], frames, results, now, None,
                                     direnc_gunluk_ham=daily, direnc_saatlik_ham=hourly)
    # Existing public sender is run through rendering/album assembly; the
    # transport itself is replaced so nothing is sent to Telegram.
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-1001234567890")
    monkeypatch.setattr(notifier, "DATA_DIR", str(tmp_path / "state"))
    instance = notifier.TelegramNotifier()
    monkeypatch.setattr(instance, "_public_pace", lambda: None)
    rendered = []
    actual_write = grafik.kareyi_yaz
    def capture(snapshot, tf):
        path, meta = actual_write(snapshot, tf)
        rendered.append((tf, meta["cizgiler"]["stabil_direnc"]))
        return path, meta
    monkeypatch.setattr(grafik, "kareyi_yaz", capture)
    albums = []
    def album(paths, *, captions, chat_id, notifier):
        albums.append(([Path(p).read_bytes() for p in paths], captions, chat_id))
        return True, "ok"
    monkeypatch.setattr(telegram, "medya_grubu_gonder", album)
    identity = {"stock_name": "AKBNK", "timeframe": "4h", "state": "KIRILIM_TEYITLI",
                "pattern_name": "Üçgen"}
    assert instance.public_grafik_bagla(identity, public) == 2
    assert [tf for tf, _ in rendered] == ["4h", "1d"]
    assert all(meta["hazir"] for _, meta in rendered)
    assert len(albums) == 1 and len(albums[0][0]) == 2
    assert all(png.startswith(b"\x89PNG") for png in albums[0][0])
    assert "üst zaman dilimi" in albums[0][1][1]


@pytest.mark.parametrize("queue_kind", ["formation", "auxiliary"])
def test_public_resistance_snapshot_persists_restart_and_renders_real_album(
        queue_kind, monkeypatch, tmp_path):
    """Both public queues restore the new layer from disk before rendering.

    The notifier, JSON persistence and PNG renderer are real; only HTTP and
    Telegram media transport are replaced so no messages leave the test.
    """
    import json
    import requests
    import notifier
    import state.persistence as persistence
    import transport.telegram as telegram
    from bot.domain_alarm_service import _grafik_verisi_uret
    from notification_delivery import snapshot_from_json, snapshot_to_json
    from state.paths import gonderim_durumu_yolu

    daily, hourly, now = _larger_frames()
    frames, results = _support_results(daily, hourly, now)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-10012345")
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)
    monkeypatch.setattr(config, "PUBLIC_STATES", ["KIRILIM_TEYITLI"])
    _, public = _grafik_verisi_uret("AKBNK", "4h", frames["4h"], frames, results, now, None,
                                     direnc_gunluk_ham=daily, direnc_saatlik_ham=hourly)
    assert [image["tf"] for image in public["goruntular"]] == ["4h", "1d"]
    expected = {image["tf"]: image["goruntu"]["stabil_direnc"]
                for image in public["goruntular"]}
    assert all(layer["hazir"] for layer in expected.values())
    # Explicitly verify the public JSON codec independently of the outboxes.
    decoded = snapshot_from_json(snapshot_to_json(public))
    assert {image["tf"]: image["goruntu"]["stabil_direnc"]
            for image in decoded["goruntular"]} == expected

    http = []
    monkeypatch.setattr(requests, "post", lambda url, json, timeout: (
        http.append((url, json)) or SimpleNamespace(status_code=200, text="{}")))
    original = notifier.TelegramNotifier()
    identity = {"stock_name": "AKBNK", "timeframe": "4h", "state": "KIRILIM_TEYITLI",
                "pattern_name": "Üçgen", "confidence_score": 95,
                "break_dir": 1, "formation_id": "resistance-persistence"}
    if queue_kind == "formation":
        assert original.public_kuyruk({**identity, "grafik_verisi_public": public})
        assert Path(gonderim_durumu_yolu()).is_file()
        encoded = persistence.gunluk_durum_yukle()["public"]["kuyruk"][0]["_public_grafik_snapshot"]
    else:
        original.public_max_saatlik = 0  # keep a definite, retryable budget block
        assert original.public_ozel_gonder("stabil-resistance", "alarm", identity=identity,
                                          graphics=public) == (True, False)
        row = json.loads((Path(notifier.DATA_DIR) / "telegram_public_aux.json").read_text())["rows"][0]
        assert row["status"] == "pending" and row["graphics"] and not row["volatile_graphics"]
        encoded = row["graphics"]
    assert not http  # enqueue/persist never reached a network transport
    decoded_disk = snapshot_from_json(encoded)
    assert {image["tf"]: image["goruntu"]["stabil_direnc"]
            for image in decoded_disk["goruntular"]} == expected

    restarted = notifier.TelegramNotifier()
    restarted.public_max_saatlik = restarted.public_max_gunluk = 20
    restarted.public_min_aralik_sn = 0
    monkeypatch.setattr(restarted, "_public_pace", lambda: None)
    rendered, albums = [], []
    actual_write = grafik.kareyi_yaz
    def capture(snapshot, tf):
        assert snapshot["stabil_direnc"] == expected[tf]
        path, meta = actual_write(snapshot, tf)
        rendered.append((tf, meta["cizgiler"]["stabil_direnc"]))
        return path, meta
    def album(paths, *, captions, chat_id, notifier):
        albums.append(([Path(p).read_bytes() for p in paths], chat_id))
        return True, "ok"
    monkeypatch.setattr(grafik, "kareyi_yaz", capture)
    monkeypatch.setattr(telegram, "medya_grubu_gonder", album)
    if queue_kind == "formation":
        assert restarted._public_grafik == {} and len(restarted._public_kuyruk) == 1
        assert restarted.public_bosalt() == 1 and restarted.public_bosalt() == 0
        assert persistence.gunluk_durum_yukle()["public"]["kuyruk"] == []
    else:
        assert restarted.public_ozel_bosalt() == 1 and restarted.public_ozel_bosalt() == 0
        assert restarted._public_aux.status()["completed"] == 1
    assert [tf for tf, _ in rendered] == ["4h", "1d"]
    assert all(meta["hazir"] and meta["cizildi"] for _, meta in rendered)
    assert len(http) == len(albums) == 1 and albums[0][1] == restarted.public_chat_id
    assert len(albums[0][0]) == 2 and all(png.startswith(b"\x89PNG") for png in albums[0][0])
