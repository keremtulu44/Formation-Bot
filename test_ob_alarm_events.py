"""Alarm a closed rejection, not a low/high close inside the remaining OB."""
from dataclasses import replace
from types import SimpleNamespace

import pandas as pd
import pytest

from bot.domain_alarm_events import ob_reaction_reasons
from bot.domain_alarm_service import _bolge_sebepleri, evaluate_domain_alarm_candidates
from domain_engines.adapter import to_domain_frame
from domain_engines.order_block import OrderBlockEngine
from domain_engines.order_block.order_block import (
    OrderBlockExport, OrderBlockSideExport, OrderBlockReactionContext,
)
from research.alarm_recall_study import closed_archive
from research.ob_alarm_event_study import compare_policies


def frame():
    index = pd.date_range("2026-10-01T10:00+03:00", periods=30, freq="D")
    return pd.DataFrame({"open": 101., "high": 103., "low": 99., "close": 102., "volume": 1000.}, index=index)


def context(f, side="bull"):
    zone = OrderBlockSideExport(state=1 if side == "bull" else -1,
        top=100. if side == "bull" else 105., bottom=95. if side == "bull" else 100., source_bar=3.)
    return OrderBlockReactionContext(f.index[-1], f.index[-2], OrderBlockExport(**{side: zone}),
                                    ((3, 1 if side == "bull" else -1),))


def wrapped(ctx, quality="OK", side=None):
    # Post-fill remaining bounds are deliberately different from pre-touch.
    return {"1h": {"order_block": {"data_quality": quality,
        "export": OrderBlockExport(bull=side or OrderBlockSideExport(top=99., bottom=95., source_bar=3.)),
        "details": {"reaction_context": ctx}}}}


@pytest.mark.parametrize("side", ["bull", "bear"])
def test_closed_rejection_uses_existing_zone_and_is_symmetric(side):
    f = frame()
    if side == "bear":
        f.loc[f.index[-1], ["open", "high", "low", "close"]] = [99., 101., 97., 98.]
    reasons = ob_reaction_reasons(context(f, side), f)
    assert reasons == [f"OB {'boğa' if side == 'bull' else 'ayı'} bölge tepkisi"]


@pytest.mark.parametrize("ohlc", [(100.,101.,99.,99.), (100.,101.,99.,100.),
    (102.,104.,101.,103.), (96.,98.,94.,97.)])
def test_occupancy_boundary_close_and_no_touch_are_not_rejection(ohlc):
    f = frame()
    f.loc[f.index[-1], ["open", "high", "low", "close"]] = ohlc
    assert ob_reaction_reasons(context(f), f) == []


def test_stale_future_missing_or_invalidated_context_cannot_create_reaction():
    f = frame()
    ctx = context(f)
    for bad in (None, replace(ctx, surviving_sources=()), replace(ctx, previous_bar_time=f.index[-3]),
                replace(ctx, bar_time=f.index[-1] + pd.Timedelta(days=1))):
        assert ob_reaction_reasons(bad, f) == []
    f.loc[f.index[-1], "low"] = float("nan")
    assert ob_reaction_reasons(ctx, f) == []


@pytest.mark.parametrize("quality", ["SOURCE_GAP", "INCOMPLETE_BAR"])
def test_frozen_export_is_not_fresh_trigger(quality):
    f = frame()
    assert _bolge_sebepleri(wrapped(context(f), quality), "1h", 102., frame=f) == []


def test_live_missing_context_does_not_fall_back_to_old_occupancy():
    f = frame()
    side = OrderBlockSideExport(top=103., bottom=99., source_bar=3.)
    results = wrapped(None, side=side)
    assert _bolge_sebepleri(results, "1h", 102.) == ["OB boğa bölge tepkisi"]  # frozen v2 baseline
    assert _bolge_sebepleri(results, "1h", 102., frame=f) == []


@pytest.mark.parametrize("event,label", [(8,"boğa"),(-8,"ayı")])
def test_native_fvg_reaction_is_preserved(event, label):
    f = frame()
    results = {"1h": {"fvg": {"data_quality": "OK", "export": {
        "bull_fvg" if event > 0 else "bear_fvg": {"event": event}}}}}
    assert _bolge_sebepleri(results,"1h",102.,frame=f) == [f"FVG {label} reaksiyon"]


def test_weak_ob_does_not_silence_independent_bos(monkeypatch):
    import config
    import bot.domain_alarm_service as service
    from test_domain_alarm_service import _stabil, _bos_event
    f = frame()
    monkeypatch.setattr(config,"YENI_DOMAIN_ALARM",True)
    monkeypatch.setattr(config,"YENI_DOMAIN_ALARM_POLITIKA","P0")
    monkeypatch.setattr(service,"_grafik_verisi_uret",lambda *a,**kw: (None,None))
    results = wrapped(None, side=OrderBlockSideExport(top=103.,bottom=99.,source_bar=3.))
    results["1h"].update(stabil=_stabil(dist_atr=1.,support=95.,close=102.),
        market_structure=SimpleNamespace(error=None,skipped=False,
            export=SimpleNamespace(events=[_bos_event(len(f)-1)])))
    candidates = evaluate_domain_alarm_candidates("THYAO",{"1h":f},{"1h":f},results,
                                                (f.index[-1]+pd.Timedelta(hours=1,minutes=1)).to_pydatetime())
    assert len(candidates) == 1
    assert "BOS ↑" in candidates[0].reasons
    assert not any(r.startswith("OB ") for r in candidates[0].reasons)


def real_engine_frame():
    from test_domain_engines import _ob_fill_frame
    f = _ob_fill_frame()
    f.loc[f.index[-1],["open","high","low","close"]] = [10.5,10.6,9.8,10.5]
    return f


def test_native_engine_keeps_pre_touch_bounds_and_rejects_open_bar():
    f = real_engine_frame()
    engine = OrderBlockEngine()
    engine.replay(to_domain_frame(f))
    ctx = engine.reaction_context
    assert ctx.previous_export.bull.top == pytest.approx(10.2)
    assert engine.export.bull.top == pytest.approx(9.8)
    assert ob_reaction_reasons(ctx,f) == ["OB boğa bölge tepkisi"]
    engine.update({**to_domain_frame(f).iloc[-1].to_dict(),"is_closed":False})
    assert engine.reaction_context is ctx
    assert str(engine.last_data_quality) == "INCOMPLETE_BAR"


def test_slide_invalidates_context_until_next_update():
    engine = OrderBlockEngine()
    engine.replay(to_domain_frame(real_engine_frame()))
    assert engine.reaction_context is not None
    engine.slide_window(1)
    assert engine.reaction_context is None


@pytest.mark.parametrize("symbol,expected", [("ASTOR",True),("TUPRS",False)])
def test_archive_closed_wick_response_vs_low_close(symbol,expected):
    f = closed_archive(symbol,"1d",480)
    f = f.loc[f.index <= pd.Timestamp("2026-10-18T21:00Z")]
    engine = OrderBlockEngine()
    engine.replay(to_domain_frame(f))
    results = {"1d":{"order_block":{"export":engine.export,"data_quality":engine.last_data_quality,
        "details":{"reaction_context":engine.reaction_context}}}}
    old = _bolge_sebepleri(results,"1d",f.close.iloc[-1])
    new = _bolge_sebepleri(results,"1d",f.close.iloc[-1],frame=f)
    assert ("OB boğa bölge tepkisi" in new) is expected
    assert ("OB boğa bölge tepkisi" in old) is not expected


def test_policy_counterfactual_preserves_other_channels_and_never_reads_returns():
    before = {("T","1h",30): {"symbol":"T","timeframe":"1h","bar_index":30,
        "bar_time":"2026-11-02T10:00+03:00","reasons":["BOS ↑","OB boğa bölge tepkisi"],
        "kanallar":["BOS","OB"],"bagl_gunici_kosu":2.,"bagl_sikisma":.5,"hacim_tier":None}}
    evidence = [{**next(iter(before.values())),"old_ob":["OB boğa bölge tepkisi"],"event_ob":[]}]
    result = compare_policies(before,evidence,["2026-11-02"])
    assert result["candidate_bars_after"] == 1
    assert result["policies_independent_6bar_cooldowns"]["P0"]["same_bar_shared"] == 1


@pytest.mark.parametrize("reason", ["BOS ↑", "CHoCH ↓", "FVG boğa reaksiyon",
                                     "formasyon: Üçgen · RETEST_BASARILI", "hacim 5×"])
@pytest.mark.parametrize("with_history", [False, True])
def test_ob_only_alert_cannot_swallow_new_independent_channel(reason,with_history):
    from bot.domain_alarm_service import _zaten_gonderildi
    from test_domain_alarm_service import _aday
    times = tuple(t.isoformat() for t in pd.date_range("2026-11-01T10:00+03:00",periods=3,freq="D"))
    slot = {"last_bar_open":times[-2],"last_bar_index":39,
            "reason_signature":"OB boğa bölge tepkisi"}
    cand = _aday(bar_index=40,bar_open=times[-1],reasons=(reason,),
                 recent_bar_opens=times if with_history else ())
    assert not _zaten_gonderildi(slot,cand)
    # Once the independent channel is sent, the ordinary cooldown applies.
    next_slot = {"last_bar_open":times[-1],"last_bar_index":40,"reason_signature":reason}
    later = replace(cand,bar_index=41,bar_open="2026-11-04T10:00+03:00",recent_bar_opens=())
    assert _zaten_gonderildi(next_slot,later)


@pytest.mark.parametrize("signature", ["", "BOS ↑", "OB boğa bölge tepkisi|BOS ↑"])
def test_priority_does_not_bypass_unknown_or_non_ob_only_cooldowns(signature):
    from bot.domain_alarm_service import _zaten_gonderildi
    from test_domain_alarm_service import _aday
    slot = {"last_bar_open":"2026-11-02T10:00+03:00","last_bar_index":39,"reason_signature":signature}
    assert _zaten_gonderildi(slot,_aday(bar_index=40,reasons=("CHoCH ↓",)))


def test_priority_never_bypasses_same_bar_older_bar_or_ob_repeat():
    from bot.domain_alarm_service import _zaten_gonderildi
    from test_domain_alarm_service import _aday
    slot = {"last_bar_open":"2026-11-03T10:00:00+03:00","last_bar_index":39,
            "reason_signature":"OB boğa bölge tepkisi"}
    assert _zaten_gonderildi(slot,_aday(bar_index=40,reasons=("BOS ↑",)))  # same bar
    assert _zaten_gonderildi(slot,_aday(bar_index=40,bar_open="2026-11-02T10:00+03:00",reasons=("BOS ↑",)))
    assert _zaten_gonderildi(slot,_aday(bar_index=40,bar_open="2026-11-04T10:00+03:00",reasons=("OB boğa bölge tepkisi",)))


@pytest.mark.parametrize("symbol,expected", [("ASTOR",True),("TUPRS",False)])
def test_real_archive_candidate_uses_ob_event_with_native_stabil_gate(monkeypatch,symbol,expected):
    import config
    import bot.domain_alarm_service as service
    from domain_engines.runner import run_domain_engines, run_stabil_domain
    from data import mum_kapanis_ani
    f = closed_archive(symbol,"1d",480)
    f = f.loc[f.index <= pd.Timestamp("2026-10-18T21:00Z")]
    now = mum_kapanis_ani(f.index[-1],"1d") + pd.Timedelta(minutes=1)
    result = run_domain_engines(symbol,"1d",f,isolated=True)
    result["stabil"] = run_stabil_domain(symbol,"1d",f,daily_frame=f,as_of_close=now,isolated=True)
    assert service._stabil_bilgisi({"1d":result},"1d",f) is not None
    monkeypatch.setattr(config,"YENI_DOMAIN_ALARM",True)
    monkeypatch.setattr(config,"YENI_DOMAIN_ALARM_POLITIKA","P0")  # isolate event semantics; not production env proof
    monkeypatch.setattr(service,"_grafik_verisi_uret",lambda *a,**kw:(None,None))
    candidates = evaluate_domain_alarm_candidates(symbol,{"1d":f},{"1d":f},{"1d":result},now)
    assert any("OB boğa bölge tepkisi" in c.reasons for c in candidates) is expected


def test_dispatch_keeps_new_channel_after_ob_but_seals_exact_retries(tmp_path,monkeypatch):
    import config
    from bot.domain_alarm_service import dispatch_domain_alarm_candidates
    from test_domain_alarm_service import _aday, _Notifier
    monkeypatch.setattr(config,"YENI_DOMAIN_ALARM",True)
    monkeypatch.setattr(config,"YENI_DOMAIN_ALARM_DM",True)
    monkeypatch.setattr(config,"YENI_DOMAIN_ALARM_PUBLIC",True)
    monkeypatch.setattr(config,"YENI_DOMAIN_ALARM_COOLDOWN_BAR",6)
    n = _Notifier()
    path = str(tmp_path / "private-ob-test-state.json")
    ob = _aday(bar_index=39,bar_open="2026-11-02T10:00+03:00",reasons=("OB boğa bölge tepkisi",))
    bos = _aday(bar_index=40,bar_open="2026-11-03T10:00+03:00",reasons=("BOS ↓",))
    assert dispatch_domain_alarm_candidates([ob],n,state_path=path)["tekil_gonderilen"] == 1
    assert dispatch_domain_alarm_candidates([bos],n,state_path=path)["tekil_gonderilen"] == 1
    assert dispatch_domain_alarm_candidates([bos],n,state_path=path)["tekil_gonderilen"] == 0
    assert len(n.dm) == len(n.public) == 2
