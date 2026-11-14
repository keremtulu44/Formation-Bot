"""D7 işlem-içi iptal araştırması; yalnız gölge, yeniden üretilebilir eşleşmiş replay.

python -m research.golge_v2_iptal_olcum --workers 2
Duvar: önceki kapanışta bilinen karşı bandın aynı bantta iki ardışık temas ve
kapanışla aşılamaması. VP: kullanılabilir iki ardışık kapanışta ters 0.13.
Kapanış sinyali işlem maliyeti dışında aynı kapanıştan gerçekleşir (iyimser).
"""
import argparse
import concurrent.futures
from pathlib import Path
import json
import hashlib
import pandas as pd
from senaryo_v2.adaptor import seriyi_hazirla, hazirla_gunluk_baglam
from senaryo_v2.yaris import _tek_yarisi_simule_et

ROOT = Path('docs/arastirma/sonuclar/golge_v2')
OUT = ROOT / 'iptal_olcum'
CACHE_KEY = hashlib.sha256(b''.join(Path(p).read_bytes() for p in (
    __file__, 'senaryo_v2/yaris.py', 'senaryo_v2/adaptor.py',
    'senaryo_v2/modeller.py', str(ROOT/'mod0_baz.csv.gz')))).hexdigest()[:16]
PARTS = OUT / 'parca' / CACHE_KEY
CASES = {'baz10': (10,False,False), 'duvar10': (10,True,False),
         'baski10': (10,False,True), 'birlesik10': (10,True,True),
         'baz20': (20,False,False), 'duvar20': (20,True,False),
         'baski20': (20,False,True), 'birlesik20': (20,True,True)}

def worker(args):
    symbol, rows = args
    path = PARTS / (symbol + '.csv')
    if path.exists():
        return symbol
    bag = hazirla_gunluk_baglam(symbol)
    results = []
    for tf, group in pd.DataFrame(rows).groupby('tf'):
        seri = seriyi_hazirla(symbol, tf, gunluk_baglam=bag)
        if any((seri.r_hatali, seri.frm_hatali, seri.ms_hatali, seri.blok_hatali, seri.vp_hatali)):
            raise RuntimeError(f'{symbol} {tf}: domain engine error')
        for r in group.to_dict('records'):
            i = int(r['bar_index']); bars = seri.barlar
            if bars[i].bar_close_time != r['bar_close_time'] or abs(bars[i].close-float(r['giris_gercek'])) > 1e-7:
                raise ValueError(f"series alignment mismatch {r['olay_id']}")
            entry=float(r['giris_gercek']); stop=float(r['stop']); atr=float(r['atr_tf'])
            target=entry+(1 if r['yon']=='long' else -1)*2*atr
            cost=.003*entry/abs(entry-stop)
            common=dict(olay_bar_idx=i,dolum_idx=i,start_scan_idx=i+1,yon=r['yon'],giris=entry,stop=stop,hedef=target,atr_baz=atr,intrabar=True,tez_iptal=True)
            base = dict(olay_id=r['olay_id'],sembol=symbol,tf=tf,donem=r['donem'],yon=r['yon'],bar_close_time=r['bar_close_time'], csv_net=float(r['net15_20_r']),full20=i+20<len(bars))
            for name,(h,wall,pressure) in CASES.items():
                _, gross, reason, offset = _tek_yarisi_simule_et(bars, **common,ufuk_bar=h,duvar_iptal=wall,baski_iptal=pressure)
                base[name+'_net'] = None if gross is None else gross-cost
                base[name+'_neden'] = reason
                base[name+'_bar'] = offset
            results.append(base)
    pd.DataFrame(results).to_csv(path,index=False)
    return symbol

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--workers',type=int,default=2); args=parser.parse_args()
    PARTS.mkdir(parents=True,exist_ok=True)
    data=pd.read_csv(ROOT/'mod0_baz.csv.gz')
    data=data[data.tf.isin(['4h','1d']) & data.kalite_katmani.eq('A_ARTI') & ~data.sansurlu].copy()
    jobs=[(str(symbol),g.to_dict('records')) for symbol,g in data.groupby('sembol')]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(worker,j) for j in jobs]
        for i,f in enumerate(concurrent.futures.as_completed(futures),1):
            print(f'{i}/{len(jobs)} {f.result()}',flush=True)
    df=pd.concat([pd.read_csv(PARTS/f'{symbol}.csv') for symbol,_ in jobs],ignore_index=True)
    if len(df)!=len(data) or df.olay_id.nunique()!=len(data): raise ValueError('eksik/tekrarlı olay')
    delta=(df.baz10_net-df.csv_net).abs()
    if delta.max()>0.00011: raise ValueError(f'Baz replay raporla eşleşmiyor: max {delta.max()}')
    df.to_csv(OUT/'olaylar.csv.gz', index=False)
    summaries=[]
    for sample,sub in [('tum_10',df),('ortak_20',df[df.full20])]:
        for period,part in [('tum',sub),('kesif',sub[sub.donem=='kesif']),('dogrulama',sub[sub.donem=='dogrulama'])]:
            for name in CASES:
                if sample=='tum_10' and name.endswith('20'): continue
                baseline='baz10' if name.endswith('10') else 'baz20'
                diff=part[name+'_net']-part[baseline+'_net']
                hit=part[name+'_neden'].isin(['DUVAR_IPTAL','BASKI_IPTAL'])
                summaries.append(dict(ornek=sample,donem=period,variant=name,n=len(part),net_ort=part[name+'_net'].mean(),toplam=part[name+'_net'].sum(),kazanc_orani=(part[name+'_net']>0).mean(),degisim_ort=diff.mean(),iptal=int(hit.sum()),iptalde_baz_kazanc=int((hit & (part[baseline+'_net']>0)).sum()),iptalde_baz_zarar=int((hit & (part[baseline+'_net']<=0)).sum()),nedenler=part[name+'_neden'].value_counts().to_dict()))
    (OUT/'ozet.json').write_text(json.dumps({'baz_max_fark':float(delta.max()),'ozet':summaries},ensure_ascii=False,indent=2),encoding='utf8')
    print('TAMAMLANDI',len(df),'baseline max diff',delta.max(),flush=True)
if __name__=='__main__': main()
