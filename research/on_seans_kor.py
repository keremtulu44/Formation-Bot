"""Son 10 ortak arşiv seansını, geleceği ve tetik durumunu göstermeden incele."""
from hashlib import sha256
from pathlib import Path

import pandas as pd

from data import mum_kapanis_anlari
from research.arsiv import tf_frame

ROOT = Path(__file__).resolve().parents[1] / 'docs/arastirma/sonuclar'
OUT = ROOT / 'on_seans_kor'


def pick(frame, salt):
    return min(frame.itertuples(), key=lambda r: sha256(f'{salt}|{r.t}|{r.hisse}|{r.tf}'.encode()).digest())


def pairs(b):
    dates=b.t.str[:10];days=sorted(set.intersection(*(set(dates[g.index]) for _,g in b.groupby(['hisse','tf']))))[-10:]
    for k,day in enumerate(days):
        g=b[dates.eq(day)];yes=g[g.frm.ne(0)]
        preferred=('1h','4h','1d')[k%3];pool=yes[yes.tf.eq(preferred)]
        a=pick(pool if len(pool) else yes,'teyit');controls=g[g.tf.eq(a.tf)&g.t.eq(a.t)&g.frm.eq(0)]
        same=controls[controls.yon.eq(a.yon)&controls.aile.eq(a.aile)]
        if same.empty:same=controls[controls.yon.eq(a.yon)]
        other=pick(same if len(same) else controls,'kontrol')
        yield sorted([a,other],key=lambda r:sha256(f'sira|{r.hisse}|{r.t}'.encode()).digest()),a.frm


def prefix(r):
    f=tf_frame(r.hisse,r.tf,legacy_resample=False);times=mum_kapanis_anlari(f.index,r.tf)
    loc=times.get_loc(pd.Timestamp(r.t));g=f.iloc[loc-39:loc+1].copy();g.index=times[loc-39:loc+1]
    assert len(g)==40 and g.index.max()==pd.Timestamp(r.t) and abs(g.close.iloc[-1]-r.ref)<.001
    return g


def make():
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.colors import HexColor
    for name,file in [('D','DejaVuSans'),('B','DejaVuSans-Bold')]:
        pdfmetrics.registerFont(TTFont(name,'/usr/share/fonts/truetype/dejavu/'+file+'.ttf'))
    OUT.mkdir(exist_ok=True);c=Canvas(str(OUT/'KOR_INCELEME.pdf'),pagesize=(590,820),invariant=True);c.setTitle('Son 10 seans | Kör grafik incelemesi');key=[]
    def text(x,y,s,size=10,bold=False,color='#172b36'):
        c.setFillColor(HexColor(color));c.setFont('B' if bold else 'D',size);c.drawString(x,y,s)
    b=pd.read_csv(ROOT/'hareket_kapsam/KARARLAR.csv.gz');num=0
    for day,(pair,direction) in enumerate(pairs(b),1):
        c.setFillColor(HexColor('#f5f6f2'));c.rect(0,0,590,820,fill=1,stroke=0)
        text(34,781,'KÖR GRAFİK İNCELEMESİ      /      %02d · 10'%day,10,True,'#0e706a');text(34,749,'Bu kapanışta bildirim ister miydin?',22,True)
        text(34,727,'İkisini de, yalnız birini veya hiçbirini seçebilirsin. Gelecek mumlar gösterilmiyor.')
        text(34,710,'Her grafik için: Açardım / Açmazdım / Kararsızım. Açardım ise: yukarı, aşağı veya yönsüz?')
        for offset,r in enumerate(pair):
            num+=1;code=f'K{num:02}';g=prefix(r);y0=648-offset*301
            c.setFillColor(HexColor('#ffffff'));c.roundRect(26,y0-235,538,270,9,fill=1,stroke=0)
            tf={'1h':'1 saat','4h':'4 saat','1d':'Günlük'}[r.tf];text(39,y0+10,f'{code}    {r.hisse}  ·  {tf}',15,True);text(302,y0+11,f'{g.index[-1]:%d.%m.%Y  %H:%M} TSİ   |   Son: {r.ref:.2f}',10)
            low=g.low.min();high=g.high.max();span=max(high-low,.01);py=lambda v:y0-140+122*(v-low)/span
            vmax=max(1,g.volume.max());dx=11.55
            for frac in [0,.5,1]:
                price=low+frac*span;level=py(price);c.setStrokeColor(HexColor('#d8e0df'));c.line(40,level,504,level);text(507,level-2,f'{price:.2f}',8)
            for i,bar in enumerate(g.itertuples()):
                x=45+dx*i;color=HexColor('#158074' if bar.close>=bar.open else '#bb5148');c.setStrokeColor(color);c.setFillColor(color);c.line(x,py(bar.low),x,py(bar.high));c.rect(x-3,min(py(bar.open),py(bar.close)),6,max(1,abs(py(bar.close)-py(bar.open))),stroke=0,fill=1);c.rect(x-3,y0-184,6,30*max(0,bar.volume)/vmax,stroke=0,fill=1)
            text(506,y0-178,'Hacim',8);text(40,y0-199,f'{g.index[0]:%d.%m  %H:%M}',8);text(438,y0-199,'Karar mumu ↑',8);text(40,y0-220,'Kararım: ____________________     Gerekçem: __________________________________',9)
            outcome=r.arti if direction==1 else r.eksi
            key.append(dict(kod=code,sembol=r.hisse,tf=r.tf,kapanis=r.t,teyit=int(r.frm),cift_referans_yonu=direction,sonuc_12=outcome,yukari_12=r.arti,asagi_12=r.eksi))
        text(34,68,'Her kutu: aynı periyotta son 40 tamamlanmış mum. Saatler mum kapanışıdır.',9)
        text(34,50,'Arşiv çalışmasıdır. Grafik seçimi Telegram’da bir kartın gönderildiği / gönderilmediği anlamına gelmez.',9)
        c.showPage()
    c.save();pd.DataFrame(key).to_csv(OUT/'OYDAN_SONRA.csv',index=False)


if __name__=='__main__':make()
