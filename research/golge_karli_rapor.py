# -*- coding: utf-8 -*-
"""FAZ9 kârlı-işlem raporu: kaç karlı işlem, hangi dönemde, ortalama yüzde kaç.

Kullanım:
    python research/golge_karli_rapor.py --olcum sonuclar/<ad>/olcum/plan_sonuc.csv

Çıktı: düz sayı tablosu (kural: sıfat yok, sayı var).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path


def raporla(csv_yol: str) -> dict:
    rows = list(csv.DictReader(open(csv_yol, encoding="utf-8")))
    if not rows:
        raise SystemExit("plan_sonuc.csv boş")
    pnl = [float(r["pnl_atr"]) for r in rows]
    kazanclar = [x for x in pnl if x > 0]
    kayiplar = [x for x in pnl if x < 0]
    ts = sorted(r["t"] for r in rows)

    # Hedefe ulaşan planların girişe göre yüzdesi (fiyat bazlı)
    yuzde_hedef = []
    for r in rows:
        if r["sonuc"] == "hedef":
            g, h = float(r["giris"]), float(r["hedef"])
            if g > 0:
                yuzde_hedef.append(100.0 * (h - g) / g)

    # Plan başına ortalama getiri (%) — hedef/stop/zaman sonucuna göre
    yuzde_sonuc = {"hedef": [], "stop": [], "zaman": []}
    for r in rows:
        g, s, h = float(r["giris"]), float(r["stop"]), float(r["hedef"])
        if g <= 0:
            continue
        if r["sonuc"] == "hedef":
            yuzde_sonuc["hedef"].append(100.0 * (h - g) / g)
        elif r["sonuc"] == "stop":
            yuzde_sonuc["stop"].append(100.0 * (s - g) / g)
        # zaman: çözülme barındaki pnl yok — atlanır (pnl_atr ATR birimi)

    gun_sayisi = None
    try:
        from datetime import datetime
        a, b = datetime.fromisoformat(ts[0]), datetime.fromisoformat(ts[-1])
        gun_sayisi = (b - a).days
    except Exception:
        pass

    return {
        "plan_n": len(rows),
        "donem_ilk": ts[0][:10],
        "donem_son": ts[-1][:10],
        "donem_gun": gun_sayisi,
        "karli_n": len(kazanclar),
        "karli_yuzde": round(100.0 * len(kazanclar) / len(pnl), 1),
        "kar_zarar_orani_pf": round(sum(kazanclar) / abs(sum(kayiplar)), 2) if kayiplar else None,
        "net_atr": round(sum(pnl), 1),
        "ort_pnl_atr": round(sum(pnl) / len(pnl), 3),
        "hedefe_ulasan_n": len(yuzde_hedef),
        "hedefe_ulasan_ort_yuzde": round(sum(yuzde_hedef) / len(yuzde_hedef), 2) if yuzde_hedef else None,
        "sonuc_dagilimi": dict(Counter(r["sonuc"] for r in rows)),
        "daga_kucuk_karli_getiri_ort_yuzde": round(sum(kazanclar) / len(kazanclar), 3) if kazanclar else None,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Kârlı işlem raporu")
    p.add_argument("--olcum", required=True, help="plan_sonuc.csv yolu")
    p.add_argument("--json", default="", help="opsiyonel json çıktı yolu")
    args = p.parse_args(argv)
    sonuc = raporla(args.olcum)
    print(json.dumps(sonuc, ensure_ascii=False, indent=2))
    if args.json:
        Path(args.json).write_text(
            json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
