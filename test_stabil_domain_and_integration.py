from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from domain_engines.runner import run_stabil_domain, run_stabil_symbol_bundle
from domain_engines.stabil import (
    CandidateLineRegime,
    StabilRoleStatus,
    StabilSupportLifecycleEngine,
    StabilTrendEngine,
    SupportProgression,
    SupportValidity,
    build_completed_weekly_from_daily,
    build_single_pass_history,
    classify_candidate_support_regimes,
    prepare_causal_ohlcv,
)
import grafik
from notification_context import domain_bolumleri
from notifier.format_kart import _format_lifecycle_alert_kart_sade
from research import replay_egitim as eg
from research.arsiv import tf_frame
from research.stabil_bhv48 import evaluate_all_48_questions
from research.stabil_replay import replay_single_symbol, select_bist_equity_universe

_IST = ZoneInfo("Europe/Istanbul")


def _load_verbatim_reference_modules() -> tuple[ModuleType, ModuleType]:
    """Execute `domain_engines/05_stabil.txt` verbatim in isolated modules for parity proof."""
    raw = Path("domain_engines/05_stabil.txt").read_text(encoding="utf-8")
    mod1_start = raw.index("from __future__ import annotations")
    mod2_marker = "CORE DOMAIN: STABIL SUPPORT LIFECYCLE"
    mod2_hdr = raw.index(mod2_marker)
    mod1_code = raw[mod1_start:mod2_hdr]
    mod1_code = mod1_code[: mod1_code.rfind("####")]

    doc_marker = "DOMAIN CONTRACT: STABIL TREND"
    doc_hdr = raw.index(doc_marker)
    mod2_part = raw[mod2_hdr:doc_hdr]
    mod2_code = mod2_part[mod2_part.index("from __future__ import annotations") :]
    mod2_code = mod2_code[: mod2_code.rfind("####")]

    m1 = ModuleType("_ref_stabil_trend")
    sys.modules["_ref_stabil_trend"] = m1
    exec(compile(mod1_code, "05_stabil_mod1", "exec"), m1.__dict__)

    mod2_patched = mod2_code.replace("from .stabil_trend_engine import", "from _ref_stabil_trend import")
    m2 = ModuleType("_ref_stabil_support")
    sys.modules["_ref_stabil_support"] = m2
    exec(compile(mod2_patched, "05_stabil_mod2", "exec"), m2.__dict__)
    return m1, m2


def test_verbatim_parity_with_05_stabil_txt_on_real_astor_archive():
    m1, m2 = _load_verbatim_reference_modules()
    d_raw = tf_frame("ASTOR", "1d").tail(320)
    h4_raw = tf_frame("ASTOR", "4h").tail(900)

    daily, d_err = prepare_causal_ohlcv(d_raw, symbol="ASTOR", timeframe="1d")
    assert d_err is None
    weekly = build_completed_weekly_from_daily(
        daily,
        symbol="ASTOR",
        cutoff_close=daily["timestamp"].iloc[-1],
    )
    h4, h_err = prepare_causal_ohlcv(h4_raw, symbol="ASTOR", timeframe="4h")
    assert h_err is None

    ref_trend = m1.StabilTrendEngine().analyze(weekly, daily, h4)
    our_trend = StabilTrendEngine().analyze(weekly, daily, h4)
    assert repr(our_trend) == repr(ref_trend).replace("_ref_stabil_trend.", "")

    ref_sup = m2.StabilSupportLifecycleEngine().analyze(daily)
    our_sup = StabilSupportLifecycleEngine().analyze(daily)
    assert our_sup.support_level == ref_sup.support_level
    assert our_sup.support_floor == ref_sup.support_floor
    assert our_sup.validity.value == ref_sup.validity.value
    assert our_sup.dynamics.value == ref_sup.dynamics.value
    assert our_sup.progression.value == ref_sup.progression.value
    assert len(our_sup.events) == len(ref_sup.events)
    assert [
        (e.sequence, e.event_type.value, e.support_level, e.previous_support, e.new_support)
        for e in our_sup.events
    ] == [
        (e.sequence, e.event_type.value, e.support_level, e.previous_support, e.new_support)
        for e in ref_sup.events
    ]


def test_single_pass_history_matches_prefix_reruns_exactly():
    d_raw = tf_frame("ASTOR", "1d").iloc[:260]
    h4_raw = tf_frame("ASTOR", "4h").iloc[:750]

    hist = build_single_pass_history("ASTOR", d_raw, h4_raw, include_support_prefix_events=True)
    trend_engine = StabilTrendEngine()

    for cp_idx in [25, 120, 280, 480, len(hist.h4_close_times) - 1]:
        if cp_idx >= len(hist.h4_close_times):
            continue
        cutoff = hist.h4_close_times[cp_idx]
        d_idx, sp_sup = hist.support_at(cutoff)
        sp_trend = hist.trend_at(cutoff)

        d_pref = hist.daily_frame[hist.daily_frame["timestamp"] <= cutoff].reset_index(drop=True)
        w_pref = build_completed_weekly_from_daily(d_pref, symbol="ASTOR", cutoff_close=cutoff)
        h4_pref = hist.h4_frame[hist.h4_frame["timestamp"] <= cutoff].reset_index(drop=True)

        assert d_idx == len(d_pref) - 1
        ref_sup = StabilSupportLifecycleEngine().analyze(d_pref)
        assert sp_sup == ref_sup

        ref_trend = trend_engine.analyze(w_pref, d_pref, h4_pref, as_of=cutoff)
        assert sp_trend == ref_trend


def test_weekly_close_causality_blocks_incomplete_friday_holiday_week():
    # Week of 2024-08-26..29 (Friday 2024-08-30 is Zafer Bayrami official holiday, so Thu Aug 29 is last trading day)
    rows = [
        {"timestamp": pd.Timestamp("2024-08-26 00:00", tz=_IST), "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 1000.0},
        {"timestamp": pd.Timestamp("2024-08-27 00:00", tz=_IST), "open": 101.0, "high": 103.0, "low": 100.0, "close": 102.0, "volume": 1000.0},
        {"timestamp": pd.Timestamp("2024-08-28 00:00", tz=_IST), "open": 102.0, "high": 104.0, "low": 101.0, "close": 103.0, "volume": 1000.0},
        {"timestamp": pd.Timestamp("2024-08-29 00:00", tz=_IST), "open": 103.0, "high": 105.0, "low": 102.0, "close": 104.0, "volume": 1000.0},
    ]
    d_prep, err = prepare_causal_ohlcv(pd.DataFrame(rows), symbol="ASTOR", timeframe="1d")
    assert err is None
    wed_close = pd.Timestamp("2024-08-28 18:30", tz=_IST)
    d_wed = d_prep[d_prep["timestamp"] <= wed_close].reset_index(drop=True)
    w_mid = build_completed_weekly_from_daily(d_wed, symbol="ASTOR", cutoff_close=wed_close)
    assert w_mid.empty, "Tamamlanmamış hafta Çarşamba kapanışında haftalık bar olarak sızmamalı."

    thu_close = pd.Timestamp("2024-08-29 18:30", tz=_IST)
    w_after = build_completed_weekly_from_daily(d_prep, symbol="ASTOR", cutoff_close=thu_close)
    assert len(w_after) == 1
    assert pd.Timestamp(w_after["timestamp"].iloc[0]) == thu_close


def test_support_ready_is_never_hidden_when_trend_warming_up():
    d_raw = tf_frame("ASTOR", "1d").iloc[:95]
    res = run_stabil_domain("ASTOR", "1d", d_raw, isolated=True)
    roles = res.details["role_readiness"]
    assert roles["daily_support"].status is StabilRoleStatus.READY
    assert roles["weekly_trend"].status is StabilRoleStatus.WARMUP
    assert res.details["support_snapshot"].support_level is not None
    assert res.data_quality == "OK"


def test_foreign_and_spot_metal_fail_closed_in_stabil_and_universe():
    d_raw = tf_frame("ASTOR", "1d").iloc[:100]
    res = run_stabil_domain("XAUUSD", "1d", d_raw, isolated=True)
    assert res.data_quality == StabilRoleStatus.DATA_ERROR.value
    assert res.details["role_readiness"]["daily_support"].status is StabilRoleStatus.DATA_ERROR

    universe = select_bist_equity_universe(100)
    assert len(universe) == 100
    assert "XAUUSD" not in universe
    assert "XAGUSD" not in universe
    assert "XU100" not in universe


def test_chart_stepline_two_colors_sade_freeze_and_balanced_yaxis(tmp_path):
    d_raw = tf_frame("ASTOR", "1d").tail(220)
    h4_raw = tf_frame("ASTOR", "4h").tail(200)

    res = run_stabil_domain("ASTOR", "4h", h4_raw, daily_frame=d_raw, h4_frame=h4_raw, isolated=True)
    assert res.data_quality == "OK"

    goruntu = grafik.anlik_goruntu(
        tf="4h",
        cerceve=h4_raw,
        sembol="ASTOR",
        sonuclar={"stabil": res},
        tarihsel=True,
    )
    assert goruntu["stabil"] is not None
    assert goruntu["stabil"]["hazir"] is True

    png_norm, meta_norm = grafik.ciz(goruntu, "4h")
    assert png_norm is not None and Path(png_norm).stat().st_size > 10_000
    assert meta_norm["cizgiler"]["stabil"]["cizildi"] is True
    assert meta_norm["cizgiler"]["stabil"]["son_renk"] in ("ust", "alt")

    png_sade, meta_sade = grafik.ciz(goruntu, "4h", secenekler={"sade": True})
    assert png_sade is not None
    assert meta_sade["cizgiler"]["stabil"]["cizildi"] is False

    gor_far = dict(goruntu)
    n_vis = goruntu["sag"] - goruntu["sol"]
    gor_far["stabil"] = {
        "hazir": True,
        "seviyeler": [1.0] * n_vis,
        "renkler": ["ust"] * n_vis,
        "son_seviye": 1.0,
        "son_renk": "ust",
    }
    png_far, meta_far = grafik.ciz(gor_far, "4h")
    assert png_far is not None
    assert meta_far["cizgiler"]["stabil"]["kadrajda"] is False

    gor_kesit = {**goruntu, "kesit": 55, "replay": {"asama": "sonuc", "hazir_gorunum": True}}
    png_kesit, meta_kesit = grafik.ciz(gor_kesit, "4h")
    assert png_kesit is not None
    assert meta_kesit["cizgiler"]["stabil"]["gorunur_bar"] <= 56


def test_telegram_card_blok3_yapi_stabil_single_line():
    d_raw = tf_frame("ASTOR", "1d").tail(180)
    h4_raw = tf_frame("ASTOR", "4h").tail(200)
    price = float(h4_raw["close"].iloc[-1])
    bundle = run_stabil_symbol_bundle(
        "ASTOR",
        {"1d": d_raw, "4h": h4_raw},
        as_of_close=datetime.now(_IST),
        isolated=True,
    )
    bolumler = domain_bolumleri(
        {"4h": {"stabil": bundle["4h"]}},
        price,
        stil="kart",
        alarm_tf="4h",
    )
    assert bolumler.get("stabil"), "BLOK 3 · YAPI için Stabil satırı üretilmeli"
    kart = _format_lifecycle_alert_kart_sade(
        {
            "stock_name": "ASTOR",
            "timeframe": "4h",
            "state": "KIRILIM_TEYITLI",
            "pattern_name": "TOBO",
            "break_dir": 1,
            "close_price": price,
            "break_price": price * 0.99,
            "domain_bolumleri": bolumler,
        }
    )
    assert any(
        tag in kart
        for tag in ("Stabil: destek üstünde", "Stabil: destek altında", "Stabil: destekte")
    )


def test_training_mode_upfront_horizon_code_free_combined_and_causal_stabil(monkeypatch):
    import transport.telegram as tg

    with pytest.raises(ValueError):
        eg.soru_sec("XAUUSD")

    session = eg.Session()
    messages: list[str] = []
    sent_albums: list[tuple] = []
    monkeypatch.setattr(session, "_schedule", lambda job, generation: job())
    monkeypatch.setattr(
        tg,
        "medya_grubu_gonder",
        lambda paths, captions=None, **k: sent_albums.append((paths, captions)) or (True, ""),
    )
    monkeypatch.setattr(eg, "album_hazirla", lambda *a, **k: (["a", "b", "c", "d"], ["1s", "2s", "4s", "1g"]))
    notifier = SimpleNamespace(chat_id="777", send_to_chat=lambda text, _: messages.append(text) or True)

    session.yeni("ASTOR", notifier).baslat()
    assert session.current is not None
    q = session.current
    assert q.horizon in eg.HORIZONS
    assert f"{q.horizon} kapanmış mum" in messages[-1]

    snap_4h = eg._soru_goruntusu(q, "4h")
    assert snap_4h.get("stabil") is not None

    reply = session.cevap("1s aşağı", notifier)
    assert "Sonuç hazırlanıyor" in reply
    reply.baslat()
    assert session.current is None
    assert "Tahmin: aşağı" in messages[-1] and f"1s · {q.horizon} kapanmış mum" in messages[-1]


def test_candidate_regime_has_no_artificial_post_confirmation_delay_and_provisional_flag():
    d_raw = tf_frame("ASTOR", "1d").tail(220)
    hist = build_single_pass_history("ASTOR", d_raw, pd.DataFrame())
    anns = classify_candidate_support_regimes(hist.support_timeline, user_confirmed=False)
    assert len(anns) == len(hist.support_timeline)
    assert all(a.provisional is True for a in anns)
    for snap, ann in zip(hist.support_timeline, anns):
        if (
            snap.progression is SupportProgression.REBASED_LOWER
            and snap.validity is SupportValidity.ACTIVE
            and snap.bars_since_support == 1
        ):
            assert ann.regime is CandidateLineRegime.HORIZONTAL_AFTER_DROP


def test_replay_first_seen_censoring_and_bhv48_contract():
    res = replay_single_symbol("ASTOR", user_confirmed_regime=False)
    cp = res.checkpoint_df
    assert len(cp) > 500
    for h in (1, 4, 8, 10, 12, 16):
        assert bool(cp[f"censored_{h}"].iloc[-1]) is True
        assert np.isnan(cp[f"ret_atr_{h}"].iloc[-1])

    if not res.first_seen_events_df.empty:
        seqs = res.first_seen_events_df["sequence"].tolist()
        assert len(seqs) == len(set(seqs))

    q_results, q_table = evaluate_all_48_questions(cp, user_confirmed_regime=False)
    assert len(q_results) == 48
    by_id = {q["question_id"]: q for q in q_results}
    assert by_id["STB-BHV-F01"]["regime_mapping_status"] == "PROVISIONAL_CANDIDATE_PENDING_USER_CONFIRMATION"
    assert by_id["STB-BHV-B01"]["regime_mapping_status"] == "PROVISIONAL_CANDIDATE_PENDING_USER_CONFIRMATION"
    assert by_id["STB-BHV-D02"]["regime_mapping_status"] == "USER_CONFIRMED"
