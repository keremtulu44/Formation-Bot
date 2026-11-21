"""Orijinal OB ziyareti, kalan bant, terminal çapa ve payda sözleşmeleri."""
import pandas as pd

from research import ob_temas_haritasi as ob
from research.ob_temas_ozeti import olculebilir, eslesen_ilk_ikinci


def test_kalan_sinir_dahil_sadece_taranmis_kisim_haric():
    once={'remaining_lower': 11., 'remaining_upper': 12.}
    assert not ob.kalan_kesisim(10.99,10.,once)
    assert ob.kalan_kesisim(11.,10.,once)


def test_uygunluk_ve_esleme_kimlige_gore():
    rows=[dict(id=k,temas_no=n,yas=n*5,bariyer='LEHTE',karar_bar=2,temiz='HEDEF',
               kapanista_aktif=aktif,ileri=ileri,atr=1.) for k,n,aktif,ileri in [
                 ('A',2,True,12),('B',1,True,12),('A',1,True,12),('B',2,False,12),('C',1,True,11)]]
    g=olculebilir(pd.DataFrame(rows)); assert len(g)==3
    p=eslesen_ilk_ikinci(g); assert p.id.tolist()==['A'] and p.yas_ilk.tolist()==[5]


def test_tek_seride_bitisik_temaslar_kapanis_ve_ileri_yol(monkeypatch):
    idx=pd.date_range('2026-02-02',periods=20,freq='h',tz='Europe/Istanbul')
    f=pd.DataFrame(dict(open=11.,high=11.3,low=10.8,close=11.,volume=100),index=idx)
    f.index.name='timestamp'
    # Temas mumunun kendi tepesi sayılmaz; ikinci gelişin mumunda hedef ve dönüş bir arada.
    f.loc[idx[[2,5]],'high']=13.
    bars=[dict(index=i,remaining_lower=10.,remaining_upper=hi,fill_ratio_before_bar=0.) for i,hi in [(2,12.),(3,11.2),(5,10.5)]]
    z=dict(zone_id='Z',symbol='X',family='OB',timeframe='1h',direction='bullish',
           expected_reaction_direction='UP',origin_index=0,available_index=1,available_at=idx[1],
           zone_lower=10.,zone_upper=12.,touch_bars=bars,native_terminal_index=5,native_terminal_at=idx[5],
           native_terminal_state='REMOVED',native_terminal_reason='fill_cancel_threshold',
           native_terminal_category='FILL_CANCEL_THRESHOLD',native_price_violation=True,native_full_fill=False)
    monkeypatch.setattr(ob.arsiv,'tf_frame',lambda *a,**kw:f)
    monkeypatch.setattr(ob,'replay_ob_zones',lambda *a:[z])
    monkeypatch.setattr(ob,'compute_wilder_atr',lambda frame:[1.]*len(frame))
    zones,events=ob.seri(('X','1h'))
    assert zones[0]['toplam_temas']==2 and zones[0]['genislik']==2
    a,b=events
    assert a['yas']==1 and a['karar_bar']==3 and a['temiz']=='BELIRSIZ'
    assert b['ara_bar']==1 and b['temas_no']==2 and not b['kalana_degen']
    assert not b['kapanista_aktif'] and b['temiz']=='MOTOR_BITTI'
