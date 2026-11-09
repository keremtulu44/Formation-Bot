"""CI grafiği için arşivden saatlik seed ile tarih uyumlu günlük girdi kur.

Yalnız açıkça verilen geçici DATA_DIR'e yazar; canlı veri dizininde çalıştırılmaz.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main(target: str) -> None:
    target_path = Path(target).resolve()
    if target_path == (ROOT / 'bot_data').resolve() or (ROOT / 'bot_data').resolve() in target_path.parents:
        raise ValueError('Canlı seed dizinine yazılamaz')
    target_path.mkdir(parents=True, exist_ok=True)
    hourly = json.loads((ROOT / 'bot_data' / 'AKBNK.json').read_text(encoding='utf-8'))
    latest = max(datetime.fromisoformat(row['timestamp']).date() for row in hourly)
    daily = pd.read_csv(ROOT / 'backfill_data' / 'AKBNK_1d.csv.gz')
    dates = pd.to_datetime(daily['bar_time'], utc=True).dt.tz_convert('Europe/Istanbul').dt.date
    daily = daily.loc[dates <= latest].rename(columns={'bar_time': 'timestamp'})
    if daily.empty:
        raise ValueError('Saatlik veriyle uyumlu günlük kaynak bulunamadı')
    (target_path / 'AKBNK_gunluk.json').write_text(daily.to_json(orient='records', indent=2), encoding='utf-8')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Kullanım: python scripts/ci_seed_graphics.py <geçici-data-dizini>')
    main(sys.argv[1])
