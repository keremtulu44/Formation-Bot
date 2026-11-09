"""Offline archive-to-Telegram-boundary checks for Stabil resistance charts.

Candles and production scan/render/delivery paths are real; tokens, network and
Telegram transports are fake.  Saved PNGs inside tmp_path are for inspection.
"""
from __future__ import annotations

import copy
import json
import shutil
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import requests

import config
import grafik
import notifier
import transport.telegram as telegram
from data import resample_all_timeframes, tamamlanmis_mumlar
from domain_engines.runner import run_domain_engines, run_stabil_symbol_bundle
from research.arsiv import ham_frame


DM, GROUP = "12345", "-10012345"  # fake targets, never real Telegram


class ArchiveManager:
    def __init__(self, symbol, hourly, daily, directory):
        self.symbol = symbol
        self.hourly = hourly
        self.daily = daily
        self.data_dir = str(directory)
        self.deques = {symbol: object()}
        self.gunluk_deques = {symbol: object()} if daily is not None else {}
        self.sureklilik_sorunlari = {}

    def to_dataframe(self, symbol):
        return self.hourly.copy(deep=True) if symbol == self.symbol else None

    def to_gunluk_dataframe(self, symbol):
        if symbol != self.symbol or self.daily is None:
            return None
        return self.daily.copy(deep=True)

    def _okuma_yolu(self, name):
        return str(Path(self.data_dir) / name)

    def gunluk_veri_eksik_mi(self, *_args):
        return False

    def save_to_disk(self, _symbol):
        return None


def archived(symbol, when):
    now = pd.Timestamp(when, tz="Europe/Istanbul")
    hourly = tamamlanmis_mumlar(ham_frame(symbol, "1h"), "1h", now=now).iloc[-360:].copy()
    daily = tamamlanmis_mumlar(ham_frame(symbol, "1d"), "1d", now=now).copy()
    # The repository archive reads UTC; the production deque normalizes aware
    # incoming timestamps to Istanbul. Preserve instants while matching that path.
    hourly.index = hourly.index.tz_convert("Europe/Istanbul")
    daily.index = daily.index.tz_convert("Europe/Istanbul")
    frames = {**resample_all_timeframes(hourly), "1d": daily}
    closed = {tf: tamamlanmis_mumlar(frame, tf, now=now) for tf, frame in frames.items()}
    return now, hourly, daily, frames, closed


def _frozen_clock(now):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            dt = now.to_pydatetime()
            return dt.astimezone(tz) if tz else dt.replace(tzinfo=None)

    return Frozen


class OfflineTelegram:
    """Transport double that copies the actual PNG before normal cleanup."""

    def __init__(self, directory):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.messages = []
        self.albums = []
        self.renders = []

    def post(self, _url, json=None, timeout=None, **_kwargs):
        del timeout
        self.messages.append({"chat_id": str((json or {}).get("chat_id", "")),
                              "text": (json or {}).get("text", "")})
        return SimpleNamespace(status_code=200, text='{"ok":true}', json=lambda: {"ok": True})

    def _save(self, paths, captions, target):
        images = []
        sequence = len(self.albums)
        for index, path in enumerate(paths):
            out = self.directory / f"album_{sequence:02d}_{index:02d}.png"
            shutil.copyfile(path, out)
            assert out.read_bytes().startswith(b"\x89PNG")
            images.append(out.name)
        self.albums.append({"chat_id": str(target), "images": images, "captions": list(captions)})
        return True, "ok"

    def album(self, paths, *, captions, notifier, chat_id=None, **_kwargs):
        return self._save(paths, captions, chat_id or notifier.chat_id)

    def photo(self, path, *, notifier, caption="", chat_id=None, **_kwargs):
        return self._save([path], [caption], chat_id or notifier.chat_id)

    def report(self):
        result = {"messages": self.messages, "albums": self.albums, "renders": self.renders}
        (self.directory / "kayit.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


@pytest.fixture
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", DM)
    monkeypatch.setenv("TELEGRAM_GROUP_ID", GROUP)
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "4")
    monkeypatch.setattr(config, "PUBLIC_STATES", ["KIRILIM_TEYITLI", "RETEST_BASARILI", "KIRILIM_GECERSIZLESTI"])
    capture = OfflineTelegram(tmp_path / "media")
    monkeypatch.setattr(requests, "post", capture.post)
    monkeypatch.setattr(telegram, "medya_grubu_gonder", capture.album)
    monkeypatch.setattr(telegram, "foto_gonder", capture.photo)
    actual = grafik.kareyi_yaz

    def render(snapshot, tf, **kwargs):
        path, meta = actual(snapshot, tf, **kwargs)
        layer = snapshot.get("stabil_direnc") or {}
        capture.renders.append({"tf": tf, "symbol": snapshot.get("sembol"),
                                "resistance": meta.get("cizgiler", {}).get("stabil_direnc"),
                                "support": meta.get("cizgiler", {}).get("stabil"),
                                "signal_bars": {name: layer.get(name) for name in
                                                ("donus_barlar", "momentum_barlar", "dikey_deneme_barlar")},
                                "warnings": meta.get("uyarilar", [])})
        return path, meta

    monkeypatch.setattr(grafik, "kareyi_yaz", render)
    yield capture
    capture.report()


def _notifier(monkeypatch):
    instance = notifier.TelegramNotifier()
    instance.public_max_saatlik = instance.public_max_gunluk = 50
    instance.public_min_aralik_sn = 0
    monkeypatch.setattr(instance, "_grafik_pace", lambda: None)
    monkeypatch.setattr(instance, "_public_pace", lambda: None)
    return instance


def _run_command(monkeypatch, symbol, manager, now, argument, channel=""):
    import bot.commands as commands
    import main

    instance = _notifier(monkeypatch)
    monkeypatch.setattr(main, "datetime", _frozen_clock(now))
    monkeypatch.setattr(main, "_notifier_ref", instance)
    monkeypatch.setattr(main, "_deque_manager_ref", manager)
    monkeypatch.setattr(main, "komut_sohbeti", lambda: channel)
    # This is a historical, explicitly selected archive cutoff. No refresh is
    # attempted and its former availability is not represented as live freshness.
    monkeypatch.setattr(commands, "_grafik_cache_tazelik_durumu", lambda *_a, **_k: {"taze": True})
    monkeypatch.setattr(commands, "_grafik_tazele", lambda *_a, **_k: pytest.fail("network refresh"))
    main._grafik_aktif_is.clear()
    done = threading.Event()
    worker = main._grafik_isi_calistir

    def run(*args):
        try:
            worker(*args)
        finally:
            done.set()

    monkeypatch.setattr(main, "_grafik_isi_calistir", run)
    result = main._komut_grafik(argument)
    assert hasattr(result, "baslat"), result
    result.baslat()
    assert done.wait(120), "manual chart worker did not finish"
    assert not main._grafik_aktif_is
    return result


def test_command_real_worker_all_four_archived_frames_with_alarm_switch_off(monkeypatch, tmp_path, offline):
    now, hourly, daily, _, _ = archived("DOCO", "2026-10-19 13:30")
    manager = ArchiveManager("DOCO", hourly, daily, tmp_path)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    observed = []
    draw = grafik.ciz

    def capture(snapshot, tf, *args, **kwargs):
        path, meta = draw(snapshot, tf, *args, **kwargs)
        observed.append((tf, meta, snapshot))
        return path, meta

    monkeypatch.setattr(grafik, "ciz", capture)
    result = _run_command(monkeypatch, "DOCO", manager, now, "DOCO")
    assert "DM'e" in str(result)
    assert len(offline.albums) == 1 and offline.albums[0]["chat_id"] == DM
    assert len(offline.albums[0]["images"]) == 4
    assert [tf for tf, _, _ in observed] == ["1h", "2h", "4h", "1d"]
    assert all(meta["cizgiler"]["stabil_direnc"]["hazir"] == (tf in {"4h", "1d"})
               for tf, meta, _ in observed)
    assert all((snap.get("stabil_direnc") or {}).get("hazir") for _, _, snap in observed)
    h4 = next((meta, snap) for tf, meta, snap in observed if tf == "4h")
    assert h4[0]["cizgiler"]["stabil_direnc"]["cizildi"]
    assert h4[1]["stabil_direnc"]["donus_barlar"]  # the selected archived return is actually shown
    assert h4[1]["stabil_direnc"]["momentum_barlar"]
    offline.renders.extend({"tf": tf, "resistance": meta["cizgiler"]["stabil_direnc"],
                            "support": meta["cizgiler"]["stabil"], "warnings": meta["uyarilar"]}
                           for tf, meta, _ in observed)
    assert any(message["chat_id"] == DM and "4 kare" in message["text"] for message in offline.messages)


def test_stabil_actual_reclaim_sends_public_4h_daily_but_dm_text_only(monkeypatch, tmp_path, offline):
    from bot.stabil_service import dispatch_stabil_scan_candidates, evaluate_stabil_4h_candidate

    now, hourly, daily, frames, closed = archived("AKBNK", "2026-03-23 17:30")
    bundle = run_stabil_symbol_bundle("AKBNK", closed, daily_frame=daily, h4_frame=closed["4h"],
                                      as_of_close=now, isolated=True)
    results = {"AKBNK": {tf: {"stabil": value} for tf, value in bundle.items()}}
    monkeypatch.setattr(config, "STABIL_GERI_ALIM_ALARM", True)
    monkeypatch.setattr(config, "STABIL_ALARM_DM", True)
    monkeypatch.setattr(config, "STABIL_ALARM_PUBLIC", True)
    path = str(tmp_path / "stabil-state.json")
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    without_charts = evaluate_stabil_4h_candidate("AKBNK", {**frames, "1h": hourly}, now,
                                                  domain_results_by_stock=results, state_path=path,
                                                  direnc_gunluk_ham=daily)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    candidate = evaluate_stabil_4h_candidate("AKBNK", {**frames, "1h": hourly}, now,
                                               domain_results_by_stock=results, state_path=path,
                                               direnc_gunluk_ham=daily)
    assert candidate is None and without_charts is None
    assert not offline.messages and not offline.albums


def test_domain_real_choch_candidate_sends_private_and_public_albums(monkeypatch, tmp_path, offline):
    from bot.domain_alarm_service import dispatch_domain_alarm_candidates, evaluate_domain_alarm_candidates

    now, hourly, daily, frames, closed = archived("DOCO", "2026-10-19 13:30")
    bundle = run_stabil_symbol_bundle("DOCO", closed, daily_frame=daily, h4_frame=closed["4h"],
                                      as_of_close=now, isolated=True)
    outputs = {tf: {**run_domain_engines("DOCO", tf, frame, isolated=True), "stabil": bundle[tf]}
               for tf, frame in closed.items()}
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_DM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_PUBLIC", True)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    without_charts = evaluate_domain_alarm_candidates("DOCO", {**frames, "1h": hourly}, closed,
                                                       outputs, now, direnc_gunluk_ham=daily)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    candidates = evaluate_domain_alarm_candidates("DOCO", {**frames, "1h": hourly}, closed,
                                                   outputs, now, direnc_gunluk_ham=daily)
    assert [replace(c, grafik_verisi=None, grafik_verisi_public=None) for c in candidates] == without_charts
    assert len(candidates) == 1 and candidates[0].timeframe == "4h"
    assert "CHoCH ↑" in candidates[0].reasons  # actual structure-engine event, no injected pattern
    path = str(tmp_path / "domain-state.json")
    result = dispatch_domain_alarm_candidates(candidates, _notifier(monkeypatch), state_path=path)
    assert result == {"aday": 1, "tekil_gonderilen": 1, "toplu_ozet": 0, "filtrelendi": 0}
    assert [row["chat_id"] for row in offline.messages] == [DM, GROUP]
    assert offline.messages[0]["text"] == offline.messages[1]["text"]
    assert [(x["chat_id"], len(x["images"])) for x in offline.albums] == [(DM, 4), (GROUP, 2)]
    assert [x["tf"] for x in offline.renders] == ["4h", "1h", "2h", "1d", "4h", "1d"]
    assert all(x["resistance"]["hazir"] == (x["tf"] in {"4h", "1d"}) for x in offline.renders)
    assert offline.renders[0]["resistance"]["cizildi"]
    assert offline.renders[0]["resistance"]["donus_isaret"] >= 1


def _offline_scan_environment(monkeypatch, symbol, now):
    import main
    from notification_delivery import DeliveryOutbox

    class State:
        def begin_scan(self, *_a, **_k): pass
        def record_formation(self, *_a, **_k): pass
        def mark_alert_sent(self, *_a, **_k): pass
        def finish_scan(self, *_a, **_k): pass
        def fail_scan(self, *_a, **_k): pass

    monkeypatch.setattr(main, "datetime", _frozen_clock(now))
    monkeypatch.setattr(DeliveryOutbox, "now", lambda _self: now.to_pydatetime())
    monkeypatch.setattr(main, "ACTIVE_STOCKS", [symbol])
    monkeypatch.setattr(main, "_live_state", State())
    monkeypatch.setattr(main, "_deferred_alert_buffer", SimpleNamespace(observe=lambda *_a, **_k: None))
    monkeypatch.setattr(main, "fetch_1h_stocks_paced", lambda *_a, **_k: ({}, {}, 0, 0))
    monkeypatch.setattr(main, "create_yahoo_pacer", lambda: object())
    monkeypatch.setattr(main, "select_yfinance_1h_period", lambda *_a: "5d")
    monkeypatch.setattr(main, "tarama_penceresi_acik_mi", lambda *_a: False)
    monkeypatch.setattr(main, "_cache_verisi_kullanilabilir", lambda *_a, **_k: True)
    monkeypatch.setattr(main, "reset_daily_if_needed", lambda: None)
    monkeypatch.setattr(main, "write_heartbeat", lambda **_k: None)
    monkeypatch.setattr(main, "son_tarama_kaydet", lambda: None)
    monkeypatch.setattr(main, "_shutdown_requested", False)
    monkeypatch.setattr(main, "_gunluk_sayac_kaydet", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "_karne_olay_kaydet", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "_ileri_test_kaydet", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "_gun_sayacini_gonderimle_hizala", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "_record_daily_lifecycle_events", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "_note_pattern_found", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "_note_basarisiz_kirilim", lambda *_a, **_k: None)
    monkeypatch.setattr(main, "_note_unannounced_invalidation", lambda *_a, **_k: None)
    # Production engines still run, but without retaining incremental process state.
    monkeypatch.setattr(main, "_load_domain_runner", lambda: (
        lambda sym, tf, frame, profile: run_domain_engines(sym, tf, frame, profile=profile, isolated=True)))
    stats = copy.deepcopy(main.daily_stats)
    stats["max_bar_age_min"] = None
    monkeypatch.setattr(main, "daily_stats", stats)
    return main


def test_real_formation_breakout_from_archive_through_scan_and_both_delivery_paths(
        monkeypatch, tmp_path, offline):
    from patterns import PatternLifecycleManager

    now, hourly, daily, _, _ = archived("AKBNK", "2026-03-18 13:30")
    manager = ArchiveManager("AKBNK", hourly, daily, tmp_path)
    main = _offline_scan_environment(monkeypatch, "AKBNK", now)
    monkeypatch.setattr(config, "STABIL_GERI_ALIM_ALARM", False)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", False)
    lifecycle = PatternLifecycleManager()
    n = _notifier(monkeypatch)
    report = main.scan_all_stocks(manager, lifecycle, n, stocks=["AKBNK"], send_alerts=True)
    assert report["status"] == "tamamlandi", report
    snap = lifecycle.get_snapshot("AKBNK_4h")
    assert snap and snap.state == "KIRILIM_TEYITLI" and snap.active.pattern_type == "Alçalan Kama"
    assert snap.effective_quality == pytest.approx(85.488, abs=.01)
    assert any(row["chat_id"] == DM and "AKBNK" in row["text"] for row in offline.messages)
    assert any(row["chat_id"] == GROUP and "AKBNK" in row["text"] for row in offline.messages)
    assert offline.messages[0]["text"] == offline.messages[1]["text"]
    assert [(x["chat_id"], len(x["images"])) for x in offline.albums] == [(DM, 4), (GROUP, 2)]
    assert [x["tf"] for x in offline.renders] == ["4h", "1h", "2h", "1d", "4h", "1d"]
    assert all(x["resistance"]["hazir"] == (x["tf"] in {"4h", "1d"}) for x in offline.renders)
    assert offline.renders[0]["resistance"]["cizildi"]
    # On 1H the resistance layer is intentionally hidden for display.
    assert not offline.renders[1]["resistance"]["cizildi"]
    assert not offline.renders[1]["resistance"]["kadrajda"]


def test_manual_group_simple_mode_is_routed_to_group_but_hides_stabil(monkeypatch, tmp_path, offline):
    now, hourly, daily, _, _ = archived("DOCO", "2026-10-19 13:30")
    manager = ArchiveManager("DOCO", hourly, daily, tmp_path)
    observed, inputs = [], []
    draw = grafik.ciz

    def capture(snapshot, tf, *args, **kwargs):
        inputs.append(snapshot)
        path, meta = draw(snapshot, tf, *args, **kwargs)
        observed.append(meta)
        return path, meta

    monkeypatch.setattr(grafik, "ciz", capture)
    response = _run_command(monkeypatch, "DOCO", manager, now, "DOCO 4s sade", channel=GROUP)
    assert "bu gruba" in str(response)
    assert [(a["chat_id"], len(a["images"])) for a in offline.albums] == [(GROUP, 1)]
    assert observed[0]["mod"]["sade"]
    assert inputs[0]["stabil_direnc"]["hazir"]  # source was valid before the intentional omission
    assert not observed[0]["cizgiler"]["stabil_direnc"]["hazir"]
    assert not observed[0]["cizgiler"]["stabil_direnc"]["cizildi"]
    assert not observed[0]["cizgiler"]["stabil"]["cizildi"]
    assert [message["chat_id"] for message in offline.messages] == [GROUP]
    offline.renders.append({"tf": "4h", "mode": "sade",
                            "resistance": observed[0]["cizgiler"]["stabil_direnc"],
                            "support": observed[0]["cizgiler"]["stabil"]})


def test_manual_missing_daily_emits_chart_and_clear_caption_without_resistance(monkeypatch, tmp_path, offline):
    now, hourly, _daily, _, _ = archived("DOCO", "2026-10-19 13:30")
    manager = ArchiveManager("DOCO", hourly, None, tmp_path)
    observed = []
    draw = grafik.ciz

    def capture(snapshot, tf, *args, **kwargs):
        path, meta = draw(snapshot, tf, *args, **kwargs)
        observed.append(meta)
        return path, meta

    monkeypatch.setattr(grafik, "ciz", capture)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    _run_command(monkeypatch, "DOCO", manager, now, "DOCO 4s detay")
    assert [(a["chat_id"], len(a["images"])) for a in offline.albums] == [(DM, 1)]
    layer = observed[0]["cizgiler"]["stabil_direnc"]
    assert not layer["hazir"] and not layer["cizildi"] and layer["neden"] == "missing_source"
    assert "Stabil direnç gösterilemedi" in offline.albums[0]["captions"][0]
    offline.renders.append({"tf": "4h", "resistance": layer,
                            "support": observed[0]["cizgiler"]["stabil"],
                            "warnings": observed[0]["uyarilar"]})


@pytest.mark.parametrize("tf,other,role", [
    ("1h", "4h", "ust"), ("2h", "4h", "ust"),
    ("4h", "1d", "ust"), ("1d", "4h", "alt"),
])
def test_domain_public_graph_timeframe_pair_and_resistance_per_timeframe(monkeypatch, tf, other, role):
    from bot.domain_alarm_service import _grafik_verisi_uret

    now, hourly, daily, _, closed = archived("DOCO", "2026-10-19 13:30")
    bundle = run_stabil_symbol_bundle("DOCO", closed, daily_frame=daily, h4_frame=closed["4h"],
                                      as_of_close=now, isolated=True)
    results = {timeframe: {"stabil": value} for timeframe, value in bundle.items()}
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "1")
    dm, public = _grafik_verisi_uret("DOCO", tf, closed[tf], closed, results, now, None,
                                      direnc_gunluk_ham=daily, direnc_saatlik_ham=hourly)
    assert [k["tf"] for k in dm["goruntular"]] == [tf]
    assert [k["tf"] for k in public["goruntular"]] == [tf, other]
    assert public["goruntular"][1]["rol"] == role
    assert all(k["goruntu"]["stabil_direnc"]["hazir"] for k in public["goruntular"])


def test_actual_formation_retest_outside_frozen_boundary_is_not_a_sent_alert(monkeypatch, tmp_path, offline):
    from patterns import PatternLifecycleManager

    now, hourly, daily, _, _ = archived("AKBNK", "2026-03-23 17:30")
    main = _offline_scan_environment(monkeypatch, "AKBNK", now)
    monkeypatch.setattr(config, "STABIL_GERI_ALIM_ALARM", False)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", False)
    monkeypatch.setattr(main, "_domain_results_for_notification", lambda *_a, **_k: {})
    manager = ArchiveManager("AKBNK", hourly, daily, tmp_path)
    lifecycle = PatternLifecycleManager()
    report = main.scan_all_stocks(manager, lifecycle, _notifier(monkeypatch), stocks=["AKBNK"])
    snap = lifecycle.get_snapshot("AKBNK_4h")
    assert report["status"] == "tamamlandi"
    assert snap.state == "RETEST_BASARILI" and snap.active.pattern_type == "Alçalan Kama"
    assert float(hourly["close"].iloc[-1]) == pytest.approx(72.50)
    assert snap.active.frozen_upper_boundary_at_break == pytest.approx(73.942853, abs=.001)
    assert not offline.messages and not offline.albums  # existing close-confirmation gate vetoed it


def test_domain_real_event_media_uncertainty_keeps_text_and_requests_manual_review(monkeypatch, tmp_path, offline):
    from bot.domain_alarm_service import dispatch_domain_alarm_candidates, evaluate_domain_alarm_candidates

    now, hourly, daily, frames, closed = archived("DOCO", "2026-10-19 13:30")
    bundle = run_stabil_symbol_bundle("DOCO", closed, daily_frame=daily, h4_frame=closed["4h"],
                                      as_of_close=now, isolated=True)
    outputs = {"4h": {**run_domain_engines("DOCO", "4h", closed["4h"], isolated=True),
                       "stabil": bundle["4h"]}}
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_DM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_PUBLIC", True)
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "1")
    candidates = evaluate_domain_alarm_candidates("DOCO", {**frames, "1h": hourly},
                                                   closed, outputs, now, direnc_gunluk_ham=daily)
    assert len(candidates) == 1 and "CHoCH ↑" in candidates[0].reasons

    # The real PNGs are prepared; only the final transport reports uncertainty.
    # Copy the attempted files to show what was attempted, not proof of delivery.
    def ambiguous_album(paths, *, captions, notifier, chat_id=None, **kwargs):
        offline.album(paths, captions=captions, notifier=notifier, chat_id=chat_id, **kwargs)
        return False, "timeout: outcome unknown"

    def ambiguous_photo(path, *, notifier, caption="", chat_id=None, **kwargs):
        offline.photo(path, notifier=notifier, caption=caption, chat_id=chat_id, **kwargs)
        return False, "timeout: outcome unknown"

    monkeypatch.setattr(telegram, "medya_grubu_gonder", ambiguous_album)
    monkeypatch.setattr(telegram, "foto_gonder", ambiguous_photo)
    n = _notifier(monkeypatch)
    result = dispatch_domain_alarm_candidates(candidates, n, state_path=str(tmp_path / "domain-failure.json"))
    assert result["tekil_gonderilen"] == 1  # texts succeeded; image transport did not
    assert [m["chat_id"] for m in offline.messages] == [DM, GROUP]
    assert [(a["chat_id"], len(a["images"])) for a in offline.albums] == [(DM, 1), (GROUP, 2)]
    assert n._dm_aux.status()["review"] == n._public_aux.status()["review"] == 1
    assert n._dm_aux.rows[0]["status"] == n._public_aux.rows[0]["status"] == "graphics_uncertain"
    assert n._dm_aux.flush() == n._public_aux.flush() == 0
    assert len(offline.messages) == len(offline.albums) == 2  # no unsafe automatic retry


def test_controlled_post_confirmation_invalidation_sends_only_its_4h_frame(monkeypatch, tmp_path, offline):
    """Real prior confirmation; invalidation transition deliberately injected, not historical fact."""
    from patterns import PatternLifecycleManager

    first_time, first_h, first_d, _, _ = archived("AKBNK", "2026-03-18 13:30")
    main = _offline_scan_environment(monkeypatch, "AKBNK", first_time)
    monkeypatch.setattr(config, "STABIL_GERI_ALIM_ALARM", False)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", False)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    manager = ArchiveManager("AKBNK", first_h, first_d, tmp_path)
    lifecycle = PatternLifecycleManager()
    n = _notifier(monkeypatch)
    assert main.scan_all_stocks(manager, lifecycle, n, stocks=["AKBNK"])["status"] == "tamamlandi"
    confirmed = lifecycle.get_snapshot("AKBNK_4h")
    active = confirmed.active
    assert confirmed.state == "KIRILIM_TEYITLI" and n.teyit_teslim_edildi_mi(active.stable_id)
    assert [m["chat_id"] for m in offline.messages] == [DM, GROUP]
    assert not offline.albums
    offline.messages.clear()

    now, hourly, daily, _, closed = archived("AKBNK", "2026-03-23 17:30")
    manager.hourly, manager.daily = hourly, daily
    _offline_scan_environment(monkeypatch, "AKBNK", now)
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    bundle = run_stabil_symbol_bundle("AKBNK", closed, daily_frame=daily, h4_frame=closed["4h"],
                                      as_of_close=now, isolated=True)
    results = {tf: {"stabil": value} for tf, value in bundle.items()}
    monkeypatch.setattr(main, "_domain_results_for_notification", lambda *_a, **_k: results)
    bar = len(closed["4h"]) - 1
    close = float(closed["4h"]["close"].iloc[-1])
    events = [
        {"type": "BREAK_CONFIRMED", "state": "KIRILIM_TEYITLI", "bar": bar - 1,
         "time": (now - pd.Timedelta(hours=4)).isoformat(), "stable_id": active.stable_id,
         "direction": 1, "quality": 85.488, "price": 76.95},
        {"type": "BREAK_FAILED", "state": "BASARISIZ_KIRILIM", "bar": bar,
         "time": now.isoformat(), "stable_id": active.stable_id,
         "direction": 1, "quality": 85.488, "price": close},
    ]

    class InjectedFailure:
        def scan(self, key, frame, *, tam_yeniden):
            if not key.endswith("_4h"):
                return SimpleNamespace(state="Yok", break_dir=0, log="", active=None)
            return SimpleNamespace(state="BASARISIZ_KIRILIM", break_dir=1, log="kontrollü test",
                                   invalid_reason="Kırılım sonrası formasyon alanına dönüldü",
                                   events=events, active=active, effective_quality=85.488,
                                   bar_index=len(frame) - 1, retest_seen=False)

        def get_snapshot(self, _key):
            return None

    report = main.scan_all_stocks(manager, InjectedFailure(), n, stocks=["AKBNK"])
    assert report["status"] == "tamamlandi"
    assert [m["chat_id"] for m in offline.messages] == [DM, GROUP]
    assert offline.messages[0]["text"] == offline.messages[1]["text"]
    assert [(a["chat_id"], len(a["images"])) for a in offline.albums] == [(DM, 1), (GROUP, 1)]
    assert [r["tf"] for r in offline.renders] == ["4h", "4h"]
    assert all(r["resistance"]["hazir"] and r["resistance"]["cizildi"] for r in offline.renders)


def test_four_actual_4h_domain_candidates_use_two_individual_albums_and_text_summary(
        monkeypatch, tmp_path, offline):
    """A focused 4H-only burst made from four real same-close archive candidates."""
    from bot.domain_alarm_service import dispatch_domain_alarm_candidates, evaluate_domain_alarm_candidates

    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_DM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_PUBLIC", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_TEKIL_UST_SINIR", 3)
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "1")
    candidates = []
    for symbol in ("EREGL", "KCHOL", "DOCO", "EFOR"):
        now, hourly, daily, frames, closed = archived(symbol, "2026-10-19 13:30")
        bundle = run_stabil_symbol_bundle(symbol, closed, daily_frame=daily, h4_frame=closed["4h"],
                                          as_of_close=now, isolated=True)
        outputs = {"4h": {**run_domain_engines(symbol, "4h", closed["4h"], isolated=True),
                           "stabil": bundle["4h"]}}
        found = evaluate_domain_alarm_candidates(symbol, {**frames, "1h": hourly}, closed,
                                                  outputs, now, direnc_gunluk_ham=daily)
        assert len(found) == 1 and found[0].timeframe == "4h"
        candidates.extend(found)

    assert candidates[0].reasons == ("BOS ↓",) and candidates[1].reasons == ("BOS ↓",)
    assert candidates[2].reasons == ("CHoCH ↑",) and candidates[3].reasons == ("BOS ↓",)
    assert sorted(candidates, key=lambda c: (-c.rank_score, c.symbol))[:2] == candidates[:2]
    n = _notifier(monkeypatch)
    path = str(tmp_path / "burst.json")
    result = dispatch_domain_alarm_candidates(candidates, n, state_path=path)
    assert result == {"aday": 4, "tekil_gonderilen": 2, "toplu_ozet": 1, "filtrelendi": 0}
    dm = [m["text"] for m in offline.messages if m["chat_id"] == DM]
    group = [m["text"] for m in offline.messages if m["chat_id"] == GROUP]
    assert len(dm) == len(group) == 3 and dm == group
    assert "EREGL" in dm[0] and "KCHOL" in dm[1]
    assert "DOMAİN TOPLU ÖZET" in dm[2] and "DOCO" in dm[2] and "EFOR" in dm[2]
    assert [(a["chat_id"], len(a["images"])) for a in offline.albums] == [
        (DM, 1), (GROUP, 2), (DM, 1), (GROUP, 2),
    ]  # summary is text only
    assert [r["tf"] for r in offline.renders] == ["4h", "4h", "1d", "4h", "4h", "1d"]
    assert all(r["resistance"]["hazir"] for r in offline.renders)
    again = dispatch_domain_alarm_candidates(candidates, n, state_path=path)
    assert again == {"aday": 4, "tekil_gonderilen": 0, "toplu_ozet": 0, "filtrelendi": 4}
    assert len(offline.messages) == 6 and len(offline.albums) == 4


def test_same_real_scan_can_emit_stabil_reclaim_and_existing_domain_event(monkeypatch, tmp_path, offline):
    """One archived scan, real pattern lifecycle + both existing automatic alert paths."""
    from patterns import PatternLifecycleManager

    now, hourly, daily, _, _ = archived("AKBNK", "2026-03-23 17:30")
    main = _offline_scan_environment(monkeypatch, "AKBNK", now)
    for key in ("STABIL_GERI_ALIM_ALARM", "STABIL_ALARM_DM", "STABIL_ALARM_PUBLIC",
                "YENI_DOMAIN_ALARM", "YENI_DOMAIN_ALARM_DM", "YENI_DOMAIN_ALARM_PUBLIC"):
        monkeypatch.setattr(config, key, True)
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "1")
    manager = ArchiveManager("AKBNK", hourly, daily, tmp_path)
    lifecycle = PatternLifecycleManager()
    report = main.scan_all_stocks(manager, lifecycle, _notifier(monkeypatch), stocks=["AKBNK"])
    assert report["status"] == "tamamlandi", report
    assert lifecycle.get_snapshot("AKBNK_4h").state == "RETEST_BASARILI"  # vetoed by existing close gate
    dm = [m["text"] for m in offline.messages if m["chat_id"] == DM]
    group = [m["text"] for m in offline.messages if m["chat_id"] == GROUP]
    assert len(dm) == len(group) == 2 and dm == group
    assert all("STABİL GÜÇLÜ GERİ ALIM" not in text for text in dm)
    assert "🆕 YENİ" in dm[0] and "BOS ↓" in dm[0]
    assert "🆕 YENİ" in dm[1] and "2s" in dm[1]
    assert [(a["chat_id"], len(a["images"])) for a in offline.albums] == [
        (DM, 1), (GROUP, 2), (DM, 1), (GROUP, 2),
    ]
