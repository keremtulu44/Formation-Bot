from datetime import datetime, timedelta, timezone
import pytest
from senaryo_v2.mtf_yonetim import Snapshot, mtf_signal, protected_stop
T=datetime(2026,1,5,12,tzinfo=timezone.utc)
def test_signal_closed_fresh_and_reverse():
    two=Snapshot(T,99,100,1,-1,-1); one=Snapshot(T,99,100,1,-1,-1)
    assert mtf_signal(T,1,two,one,None,two_mode='price',four_mode='state').signal
    assert not mtf_signal(T-timedelta(minutes=1),1,two,one,None,two_mode='price',four_mode='state').signal
    assert not mtf_signal(T+timedelta(hours=3),1,two,one,None,two_mode='price',four_mode='state').signal
    assert not mtf_signal(T,-1,two,one,None,two_mode='event',four_mode='state').signal

def test_four_hour_alternative():
    two=Snapshot(T,99,100,1,-1,-1); four=Snapshot(T,99,100,1,0,-1)
    assert mtf_signal(T,1,two,None,four,two_mode='event',four_mode='state').signal
    assert mtf_signal(T,1,two,None,four,two_mode='event',four_mode='price').signal
    assert not mtf_signal(T,1,two,None,None,two_mode='event',four_mode='price').signal

def test_stop_only_improves():
    assert protected_stop(100,10,1,90,.25)==102.5
    assert protected_stop(100,10,1,105,.25)==105
    assert protected_stop(100,10,-1,110,.25)==97.5
    with pytest.raises(ValueError): protected_stop(100,0,1,90,0)

from senaryo_v2.mtf_yonetim import ManagementBar, ManagementConfig, simulate_management

def test_protection_applies_next_bar_and_stop_precedes_target():
    bars=[ManagementBar(T,100,112,99,105),ManagementBar(T+timedelta(hours=1),105,110,99,101)]
    cfg=ManagementConfig(protect_trigger_r=1,protect_lock_r=.25)
    r=simulate_management(bars,entry=100,stop=90,target=120,direction=1,cfg=cfg)
    assert r.reason=='STOP' and r.gross_r==.25 and r.bar_index==1
    bars[0]=ManagementBar(T,100,121,89,100)
    r=simulate_management(bars,entry=100,stop=90,target=120,direction=1,cfg=cfg)
    assert r.reason=='STOP' and r.gross_r==-1

def test_signal_executes_next_open_not_signal_close():
    two=Snapshot(T,99,100,1,-1,-1); one=Snapshot(T,99,100,1,-1,-1)
    bars=[ManagementBar(T,100,101,99,100,one,two),ManagementBar(T+timedelta(hours=1),94,101,93,99)]
    r=simulate_management(bars,entry=100,stop=90,target=120,direction=1,cfg=ManagementConfig(mtf_action='exit'))
    assert r.reason=='MTF_EXIT_OPEN' and r.gross_r==-.6

def test_profit_stop_gap_can_lose():
    bars=[ManagementBar(T,100,111,99,105),ManagementBar(T+timedelta(hours=1),95,100,94,99)]
    cfg=ManagementConfig(protect_trigger_r=1,protect_lock_r=.25)
    r=simulate_management(bars,entry=100,stop=90,target=120,direction=1,cfg=cfg)
    assert r.reason=='STOP_GAP' and r.gross_r==-.5
