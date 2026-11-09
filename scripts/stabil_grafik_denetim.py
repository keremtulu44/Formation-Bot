#!/usr/bin/env python3
"""Arşivden tek bir tarihsel kesitte grafik denetimi; performans replay'i değildir.

Canlı duruma yazmaz; kaynak mumlar backfill_data, domain motorları izole çalışır.
2s ve 4s mumları projenin BIST seansına hizalı resampler'ından gelir.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
import grafik
from data import mum_kapanis_anlari
from research.arsiv import tf_frame
from domain_engines.runner import run_domain_engines, run_stabil_domain
from domain_engines.stabil.chart_bridge import resistance_for_chart

SYMBOLS = ('AKBNK','ASELS','ASTOR','BIMAS','EREGL','FROTO','GARAN','ISCTR','KCHOL',
           'DOCO','PETKM','SAHOL','SISE','SNGYO','THYAO','TUPRS','YKBNK')
CUTOFF = pd.Timestamp('2026-10-16 18:30:00', tz='Europe/Istanbul')


def closed(df, tf):
    return df.loc[mum_kapanis_anlari(df.index, tf) <= CUTOFF].copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True)
    ap.add_argument('--symbols', nargs='+', default=SYMBOLS)
    ap.add_argument('--tfs', nargs='+', default=['1h','2h','4h','1d'])
    ap.add_argument('--kisa-karsilastirma', action='store_true')
    args=ap.parse_args()
    base=Path(args.output).resolve()
    if base == (ROOT/'bot_data').resolve() or (ROOT/'bot_data').resolve() in base.parents:
        raise ValueError('Canlı bot verisine yazılamaz')
    base.mkdir(parents=True, exist_ok=True)
    results=[]
    for symbol in args.symbols:
        daily=closed(tf_frame(symbol,'1d'), '1d')
        hourly=closed(tf_frame(symbol,'1h'), '1h')
        h4=closed(tf_frame(symbol,'4h'), '4h')
        for tf in args.tfs:
            try:
                frame=closed(tf_frame(symbol,tf),tf).tail(500)
                cutoff=mum_kapanis_anlari(frame.index,tf)[-1]
                domains=run_domain_engines(symbol,tf,frame,isolated=True)
                domains['stabil']=run_stabil_domain(symbol,tf,frame,daily_frame=daily,h4_frame=h4,
                                                    as_of_close=cutoff,isolated=True)
                domains['stabil_direnc']=resistance_for_chart(symbol,tf,frame,daily_frame=daily,
                                                               hourly_frame=hourly,as_of_close=cutoff)
                snap=grafik.anlik_goruntu(None,tf,frame,sonuclar=domains,sembol=symbol,
                                          simdi=CUTOFF+timedelta(seconds=90),tarihsel=True)
                path=base/f'{symbol}_{tf}.png'
                img,meta=grafik.ciz(snap,tf,{'cikti':str(path)})
                if not img: raise RuntimeError('Çizim çıktı üretmedi')
                if args.kisa_karsilastirma and tf in ('1h', '2h'):
                    before=base/f'{symbol}_{tf}_once.png'
                    old_img, old_meta = grafik.ciz(snap,tf,{'cikti':str(before), 'stabil_goster':True})
                    if not old_img: raise RuntimeError('Karşılaştırma çizimi çıktı üretmedi')
                row={'symbol':symbol,'tf':tf,'last_bar':str(frame.index[-1]),'close_time':str(cutoff),
                     'image':path.name,'cizgiler':meta.get('cizgiler'), 'zone':meta.get('zone'),
                     'uyarilar':meta.get('uyarilar'), 'eksik':meta.get('eksik_katmanlar'),
                     'resistance_status':str(domains['stabil_direnc'].status),
                     'resistance_reason':domains['stabil_direnc'].reason}
                results.append(row)
                print(symbol,tf,'ok',row['resistance_status'],row['resistance_reason'],flush=True)
            except Exception as exc:
                results.append({'symbol':symbol,'tf':tf,'error':f'{type(exc).__name__}: {exc}'})
                print(symbol,tf,'ERROR',repr(exc),flush=True)
            (base/'sonuclar.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,default=str))
    if any('error' in row for row in results): return 1
    return 0

if __name__=='__main__': raise SystemExit(main())
