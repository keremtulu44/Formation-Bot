"""D7: stop öncesi bar içi +0.5R ve ardından ilk ters kapanışta domain durumu.

python -m research.golge_v2_donus_anatomisi --workers 2
Her işlemin çıkış barından ÖNCEKİ kapalı barlar kullanılır; tepe geleceği bilerek
seçilmez. Karşılaştırma: aynı koşulları sağlayan net kârlı ve zararlı işlemler.
"""
import argparse, concurrent.futures, json
from pathlib import Path
import numpy as np
import pandas as pd
from senaryo_v2.adaptor import seriyi_hazirla, hazirla_gunluk_baglam

ROOT=Path('docs/arastirma/sonuclar/golge_v2'); OUT=ROOT/'donus_anatomisi'

def work(job):
    sym, rows=job; result=[]; bag=hazirla_gunluk_baglam(sym)
    for tf,g in pd.DataFrame(rows).groupby('tf'):
        seri=seriyi_hazirla(sym,tf,gunluk_baglam=bag)
        if any((seri.r_hatali,seri.frm_hatali,seri.ms_hatali,seri.blok_hatali,seri.vp_hatali)): raise RuntimeError(f'domain failure {sym}/{tf}')
        bars=seri.barlar
        for r in g.to_dict('records'):
            i=int(r['bar_index']); entry=float(r['giris_gercek']); risk=abs(entry-float(r['stop'])); direction=1 if r['yon']=='long' else -1
            if bars[i].bar_close_time != r['bar_close_time'] or abs(bars[i].close-entry)>1e-7: raise ValueError(r['olay_id'])
            exit_offset=int(r['baz10_bar']); end=i+exit_offset
            # Stop/hedef barının sırası bilinmediğinden tümü hariç; kapanış zamanı stop öncesi değil.
            p=None; q=None
            for j in range(i+1,end):
                if p is None and ((bars[j].high-entry if direction==1 else entry-bars[j].low)>=0.5*risk): p=j
                if p is not None and j>p and direction*(bars[j].close-bars[j-1].close)<0:
                    q=j; break
            row={'olay_id':r['olay_id'],'sembol':sym,'tf':tf,'donem':r['donem'],'yon':r['yon'],'net':r['baz10_net'], 'neden':r['baz10_neden'], 'exit_bar':exit_offset,'kar_kapanis':p is not None,'donus_var':q is not None}
            if q is not None:
                b=bars[q]; prev=bars[q-1]; ent=bars[i]; atr=float(r['atr_tf'])
                zones=prev.blok_bear if direction==1 else prev.blok_bull
                # Önceki kapanışta canlı bölgeler: bu barda terminal olsa da gözlenebilir.
                touch=any(z.height_atr>=.5 and b.low<=z.upper and b.high>=z.lower for z in zones)
                dist=lambda z: (z.lower-b.close if direction==1 else b.close-z.upper)/atr
                near=any(z.height_atr>=.5 and 0<=dist(z)<=.75 for z in zones)
                usable=bool(b.vp_data_ready and b.vp_volume_usable)
                rvol=b.vp_rvol if usable else None; p5=b.vp_pressure_5 if usable else None
                e_rvol=ent.vp_rvol if ent.vp_data_ready and ent.vp_volume_usable else None
                level=b.r_level if direction==1 else b.s_level
                sr_touch=level is not None and b.low<=level<=b.high
                same=bool(ent.frm_stable_id and ent.frm_stable_id==b.frm_stable_id)
                bound=b.frm_broken_boundary if same else None
                depth=direction*(bound-b.close)/atr if bound is not None else None
                row.update(kar_bar=p-i,donus_bar=q-i,donus_net_r=direction*(b.close-entry)/risk,
                    vp_usable=usable,vp_rvol=rvol,vp_rvol_giris=e_rvol,
                    vp_dusuk=(rvol<.75 if rvol is not None else None),
                    vp_yari=(rvol<.5*e_rvol if rvol is not None and e_rvol is not None else None),
                    vp_ters=(direction*p5<-.13 if p5 is not None else None),vp_pressure=p5,
                    vp_sinif=b.vp_effort_result_class,blok_temas=touch,blok_yakin=near,
                    stabil_temas=sr_touch,ms_ters_olay=bool(b.ms_bos_down_now if direction==1 else b.ms_bos_up_now),
                    ms_ters_durum=b.ms_ext_dir == -direction,frm_ayni=same,frm_state=b.frm_state,
                    frm_sinir_biliniyor=bound is not None,frm_derin=(depth>=.5 if depth is not None else None),frm_derin_atr=depth)
            result.append(row)
    return result

def main():
    p=argparse.ArgumentParser(); p.add_argument('--workers',type=int,default=2); args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(ROOT/'mod0_baz.csv.gz'); e=pd.read_csv(ROOT/'iptal_olcum/olaylar.csv.gz')
    d=d.merge(e[['olay_id','baz10_net','baz10_neden','baz10_bar']],on='olay_id',validate='one_to_one')
    jobs=[(s,g.to_dict('records')) for s,g in d.groupby('sembol')]; allrows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        fs=[pool.submit(work,j) for j in jobs]
        for i,f in enumerate(concurrent.futures.as_completed(fs),1):
            allrows.extend(f.result()); print(f'{i}/{len(jobs)}',flush=True)
    df=pd.DataFrame(allrows); assert len(df)==len(d) and df.olay_id.nunique()==len(d)
    df.to_csv(OUT/'olaylar.csv.gz',index=False)
    signals=['vp_dusuk','vp_yari','vp_ters','blok_temas','blok_yakin','stabil_temas','ms_ters_olay','ms_ters_durum','frm_derin']
    summary={}
    for cohort, x in [('zarar',df[df.net<=0]),('stop_zarar',df[(df.net<=0)&df.neden.isin(['STOP','STOP_GAP'])]),('kar',df[df.net>0])]:
        y=x[x.donus_var]; out={'n':len(x),'kar_kapanis':int(x.kar_kapanis.sum()),'donus':len(y),'signals':{}}
        for s in signals:
            known=y[s].dropna(); out['signals'][s]={'known':len(known),'true':int(known.astype(bool).sum()),'pct_known':float(known.astype(bool).mean()*100) if len(known) else None,'pct_all':float(known.astype(bool).sum()/len(y)*100) if len(y) else None}
        out['vp_sinif']=y.vp_sinif.value_counts().to_dict(); out['frm_state']=y.frm_state.value_counts().to_dict()
        summary[cohort]=out
    (OUT/'ozet.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__': main()
