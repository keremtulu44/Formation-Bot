# -*- coding: utf-8 -*-
"""Geliştirici önizlemesi: sentetik veriyle TEK kare üretir (FAZ 1-4 görsel kontrol).

Neden ayrı script: kareyi botu/metni çalıştırmadan, canlı motoru ilerletmeden
görmek gerek (motor durumunu tests/parite bozmasın, §14.2). Deterministik veri
kullanır; önbelleğe (`bot_data/`) YAZMAZ, motor ÇALIŞTIRMAZ.

Kullanım:
    python scripts/grafik_onizleme.py --tf 4h --cikti /tmp/onizleme.png
    python scripts/grafik_onizleme.py --tf 1d --ob-doluluk 0.41
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

import grafik  # noqa: E402
from test_grafik_iskelet import _cerceve, _cift  # noqa: E402

IST = timezone(timedelta(hours=3))
ZAMAN = datetime(2026, 12, 1, 9, 0, tzinfo=IST)


def _ob(index, alt, ust, bullish=True, skor=2, dolan=0.0):
    """Sentetik `OrderBlockRecord`: `fill_boundary` doluluk oranını verir."""
    yuk = float(ust) - float(alt)
    sinir = (float(ust) - yuk * float(dolan)) if bullish else (float(alt) + yuk * float(dolan))
    return SimpleNamespace(source_index=index, source_time=None, top=ust, bottom=alt,
                           bullish=bullish, base_score=skor, anchor_high=ust,
                           anchor_low=alt, imbalance_end_index=None, fill_boundary=sinir)


def _fvg(index, alt, ust, direction=1, durum="ACTIVE", kalite=88.0, gap=1.5,
         doluluk=0.0):
    return SimpleNamespace(formation_index=index, formation_time=None,
                           lower_boundary=alt, upper_boundary=ust,
                           direction=SimpleNamespace(value=direction),
                           state=SimpleNamespace(name=durum), gap_size=gap,
                           gap_atr=gap / 1.5, formation_atr=1.5, quality=kalite,
                           maximum_fill_ratio=doluluk, close_fill_ratio=doluluk)


def _sonuclar(ob=(), fvg=()):
    return {"order_block": SimpleNamespace(details={"records": list(ob),
                                                    "active_records": list(ob)}),
            "fvg": SimpleNamespace(details={"fvg_formations": list(fvg),
                                            "engulfing_formations": []})}


def main(argv=None) -> int:
    ay = argparse.ArgumentParser(description="Sentetik kare önizlemesi (geliştirici).")
    ay.add_argument("--tf", default="4h", choices=["1h", "2h", "4h", "1d"])
    ay.add_argument("--cikti", default="/tmp/onizleme.png")
    ay.add_argument("--ob-doluluk", type=float, default=0.41,
                    help="kısmen dolmuş OB'nin tazeden sonra dolan oranı (0-1)")
    ay.add_argument("--sade", action="store_true")
    sec = ay.parse_args(argv)

    cerceve = _cerceve(240, sec.tf)
    son = float(cerceve["kapanis"][-1])
    ob = [_ob(150, son - 1.6, son - 0.4, bullish=True),
          _ob(170, son - 1.2, son - 0.2, bullish=True, dolan=sec.ob_doluluk),
          _ob(190, son + 0.4, son + 1.6, bullish=False, dolan=sec.ob_doluluk),
          _ob(120, son + 2.4, son + 3.4, bullish=False, dolan=1.0, skor=1)]
    fvg = [_fvg(160, son - 2.6, son - 1.9, direction=1, gap=0.7),
           _fvg(180, son + 2.0, son + 2.8, direction=-1, gap=0.8)]
    cift = _cift(start_bar=200, upper_now=son + 0.8, lower_now=son - 1.4,
                 break_price=son + 0.8, candle_close_price=son + 0.9,
                 current_width=2.2, break_dir=1, state="KIRILIM_TEYITLI")
    goruntu = grafik.anlik_goruntu(cift, sec.tf, cerceve,
                                   sonuclar=_sonuclar(ob, fvg), simdi=ZAMAN,
                                   alarm_bar=len(cerceve["kapanis"]) - 1, sembol="DEMO")
    goruntu["olay"] = {"swinglar": [{"bar": 12, "fiyat": son - 1.1, "yon": "alt",
                                     "sinif": "HL", "durum": "teyitli"},
                                    {"bar": 24, "fiyat": son + 1.3, "yon": "ust",
                                     "sinif": "HH", "durum": "teyitli"}],
                       "seviyeler": [], "olaylar": [
                           {"bar": 20, "kaynak_bar": 200, "aday_bar": 19, "pivot_bar": 6,
                            "tur": "BOS", "yon": "ust", "seviye": son + 0.5,
                            "kimlik": 1, "nitelik": 80, "yas": 3, "kanit": ""},
                           {"bar": 30, "kaynak_bar": 210, "aday_bar": 29, "pivot_bar": 26,
                            "tur": "CHoCH", "yon": "alt", "seviye": son - 0.3,
                            "kimlik": 2, "nitelik": 70, "yas": 1, "kanit": ""}],
                       "kritik": {"seviye": son - 0.3, "bar": 30, "kaynak_bar": 210,
                                  "tur": "CHoCH", "yon": "alt", "pivot_bar": 26},
                       "cizilen": 4, "elenen": 0, "kapak": {"swing": 10, "olay": 6},
                       "hata": []}
    yol, meta = grafik.ciz(goruntu, sec.tf, {"cikti": sec.cikti, "sade": sec.sade})
    print("kare:", yol)
    print("kadraj:", meta["mum_sayisi"], "mum · sağ boşluk",
          meta["kare"]["sag_bosluk"], "mum")
    print("zone:", {k: v for k, v in (meta.get("zone") or {}).items()
                    if k in ("cizilen", "dolgu", "ceza")})
    print("pill:", [p["metin"] for p in (meta["metin"].get("pill_listesi") or [])])
    print("dipnot:", meta["metin"]["dipnotlar"], meta["metin"]["notlar"])
    print("serit:", meta["serit"].get("panel"), "panel · rozet",
          meta["serit"].get("rozet"),
          "(↑%s ↓%s)" % (meta["serit"].get("rozet_artis"), meta["serit"].get("rozet_dusus")))
    print("sag:", {k: meta["sag"].get(k) for k in ("yerlesen", "kaydirilan", "lider")})
    return 0 if yol else 1


if __name__ == "__main__":
    raise SystemExit(main())
