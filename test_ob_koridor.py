from types import SimpleNamespace
import pandas as pd

from research.ob_koridor import koridor, kapanis_yolu, esik_yolu
from research.ob_koridor_kiyas import ozellikler


def test_iki_zit_bant_ve_dar_aralik():
    b=SimpleNamespace(top=10); s=SimpleNamespace(bottom=12)
    assert koridor(b,s,11,1)
    assert not koridor(b,s,10,1) and not koridor(b,s,11,.99)
    assert not koridor(b,SimpleNamespace(bottom=None),11,1)


def test_buyuk_destek_itmesi_ile_yakin_bant_ayni_sey_degil():
    df=pd.DataFrame([dict(alt_kalan=2,ust_kalan=1,alt_dis=8,ust_dis=13,ref=10.4,alt_ilk=2,ust_ilk=3,konum=.2,son3_atr=0,
                          ust_temas=1,alt_temas=1,alt_kaynak='2026-01-06',ust_kaynak='2026-01-05',
                          ust_dolum=.5,alt_dolum=0,tarih='2026-01-09')])
    r=ozellikler(df).iloc[0]; assert r.buyuk_iter=='YUKARI' and r.yakin_kenar=='ASAGI'
    assert r.az_test_iter=='PAS' and r.ilk_boy_iter=='ASAGI'


def test_ara_ve_dis_sinir_farkli_yonde_gecilebilir():
    assert kapanis_yolu([12,12.3,9.4],10,12)==('YUKARI',2)
    assert kapanis_yolu([12,12.3,9.4],9.5,14)==('ASAGI',3)
    assert esik_yolu([(12,10,11)],11,1)==('BELIRSIZ',1)


def test_cift_ikinci_kapanistan_once_olay_olmaz_ve_tekrarlanmaz(monkeypatch):
    from research import ob_koridor as ob

    idx=pd.date_range('2026-03-01',periods=48,freq='h',tz='Europe/Istanbul',name='timestamp')
    f=pd.DataFrame(dict(open=11.,high=11.2,low=10.8,close=11.,volume=100),index=idx)
    f.iloc[18,f.columns.get_loc('close')]=12.5
    f.iloc[18,f.columns.get_loc('high')]=12.6
    class Engine:
        active_records=()
        def update(self,row):
            b=SimpleNamespace(bottom=8.,top=10.,source_bar=7,fill=0.)
            s=SimpleNamespace(bottom=12.,top=13.,source_bar=8,fill=0.)
            if row['timestamp']<idx[15]:
                s.bottom=None
            self.export=SimpleNamespace(bull=b,bear=s)
    monkeypatch.setattr(ob,'OrderBlockEngine',Engine)
    monkeypatch.setattr(ob.arsiv,'tf_frame',lambda *args,**kw:f)
    rows=ob.seri(('X','1h'))
    assert not rows  # Dar koridor koşulu sağlanmıyor (ATR küçük).
    monkeypatch.setattr(ob,'compute_wilder_atr',lambda f:[1.]*len(f))
    r,=ob.seri(('X','1h'))
    assert r['tarih']==idx[16].isoformat() and r['ic']=='YUKARI' and r['ic_n']==2
    assert r['dis']=='YOK' and r['simetrik']=='YUKARI'
