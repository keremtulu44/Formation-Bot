"""Direnç (▼) tarafının TABANLI ölçümü — destek aynası, işaret yönü düzeltilmiş.

NEDEN AYRI BETİK
----------------
Destek tarafında (§12) "başarı" = fiyatın **yukarı** gitmesiydi. Direnç tarafında
▼ oku "fiyat aşağı döner" der; yani **başarı = aşağı**. Aynı sayıyı doğru yönde
yorumlamak bu betiğin tek işi: sembol çevirme yok, yalnız işaret yönü tanımı.

SORU (ölçümden ÖNCE kilitlendi)
------------------------------
Dolu ▼ (close_return_below / intrabar_sweep_rejection) okları, aynı sembol ve
dönemdeki kontrol barlarına kıyasla anlamlı avantaj sağlıyor mu?

KÜTLE / BÖLÜNME
---------------
Günlük (1d), `backfill_data` tüm semboller (≥300 bar); yalnız dolu ▼.
`sha256(sembol)%10 < 6` → keşif (K), kalanı doğrulama (D).

KONTROLLER
----------
A) Ok olmayan tüm barlar
B) Dirençteki ok olmayan barlar: |dist_atr| ≤ 0,50

ÜÇ YANSITMA (▼ için başarı yönü AŞAĞI)
--------------------------------------
R1  −1 ATR (başarı) vs +1 ATR, ilk dokunan          → "yön yarışı"
R2  −2 ATR önce mi +1 ATR önce mi (2:1)             → "koşu var mı"
R3  t+10 kapanış ≤ o barın direnç seviyesi           → "seviye tuttu mu"

EŞİKLER (kilitli)
-----------------
Hücre: nK ≥ 50 ve nD ≥ 20. "Avantaj var": liftK ≥ +6 **ve** liftD ≥ +1 **ve**
iki kümede tek taraflı Fisher p < 0,0083 (6 test → Bonferroni).

REPLAY
------
    PYTHONPATH=. .venv/bin/python research/stabil_direnc_taban_replay.py
    → /tmp/ok_direnc_taban_{oklar,kontrol,ozet}.csv
"""
from __future__ import annotations

import glob
import hashlib
import os

import numpy as np
import pandas as pd

from domain_engines.stabil.resistance import evaluate_stabil_resistance
from domain_engines.stabil.signals import _causal_atr14
from research.stabil_ok_taban_replay import UFUK, YAKIN_ATR, fisher, kesif

SEVIYE_BAR = 10
LIMIT = int(os.environ.get("LIMIT", "0")) or None


def yaris_asagi(kapanis: np.ndarray, atr: np.ndarray, i: int, asagi: float, yukari: float) -> str:
    """i sonrası ilk eşik: −asagi ATR (DOWN = başarı) mı +yukari ATR (UP) mi."""
    n = len(kapanis)
    giris, birim = kapanis[i], float(atr[i])
    for j in range(1, min(UFUK, n - i - 1) + 1):
        if kapanis[i + j] <= giris - asagi * birim:
            return "DOWN"
        if kapanis[i + j] >= giris + yukari * birim:
            return "UP"
    return "NEITHER"


def main() -> int:
    dosyalar = sorted(glob.glob("backfill_data/*_1d.csv.gz"))
    if LIMIT:
        dosyalar = dosyalar[:LIMIT]

    ok_satir, ctl_satir = [], []
    atlanan = 0
    for yol in dosyalar:
        sembol = os.path.basename(yol).split("_")[0]
        try:
            d = (pd.read_csv(yol, compression="gzip", parse_dates=["bar_time"])
                 .set_index("bar_time").reset_index().rename(columns={"bar_time": "timestamp"}))
            if len(d) < 300:
                continue
            out = evaluate_stabil_resistance(sembol, "1d", d, daily_frame=d)
        except Exception:
            atlanan += 1
            continue
        if len(out.bar_behaviors) != len(d):
            atlanan += 1
            continue
        atr = _causal_atr14(d["high"].to_numpy(float), d["low"].to_numpy(float),
                            d["close"].to_numpy(float), period=14)
        kapanis = d["close"].to_numpy(float)
        n = len(d)
        bolum = "K" if kesif(sembol) else "D"

        ok_barlar = {int(b.bar_index) for b in out.bar_behaviors if b.return_kind}

        for b in out.bar_behaviors:
            i = int(b.bar_index)
            if i + UFUK + 1 >= n or not np.isfinite(atr[i]) or atr[i] <= 0:
                continue
            seviye = b.resistance_level
            satir = dict(
                sembol=sembol, bolum=bolum, bar=i,
                r1=yaris_asagi(kapanis, atr, i, 1.0, 1.0),
                r2=yaris_asagi(kapanis, atr, i, 2.0, 1.0),
                r3=(bool(kapanis[i + SEVIYE_BAR] <= float(seviye)) if seviye else None),
                yakin=bool(b.dist_atr is not None and abs(float(b.dist_atr)) <= YAKIN_ATR),
            )
            (ok_satir if i in ok_barlar else ctl_satir).append(satir)

    ok = pd.DataFrame(ok_satir)
    ctl = pd.DataFrame(ctl_satir)
    ok.to_csv("/tmp/ok_direnc_taban_oklar.csv", index=False)
    ctl.to_csv("/tmp/ok_direnc_taban_kontrol.csv", index=False)
    print(f"sembol {len(dosyalar) - atlanan}/{len(dosyalar)} · ▼ {len(ok)} · kontrol barı {len(ctl)}")

    ozet = []
    for r in ("r1", "r2", "r3"):
        for ad, alt in (("A tüm barlar", ctl), ("B dirençteki barlar", ctl[ctl.yakin])):
            for bolum in ("K", "D"):
                o = ok[(ok.bolum == bolum) & ok[r].notna()]
                c = alt[(alt.bolum == bolum) & alt[r].notna()]
                if o.empty or c.empty:
                    continue
                if r == "r3":
                    o_oran = 100 * o[r].astype(bool).mean()
                    c_oran = 100 * c[r].astype(bool).mean()
                    a, b_ = int(o[r].astype(bool).sum()), int(c[r].astype(bool).sum())
                else:
                    oo = o[o[r] != "NEITHER"]
                    cc = c[c[r] != "NEITHER"]
                    o_oran = 100 * (oo[r] == "DOWN").mean()
                    c_oran = 100 * (cc[r] == "DOWN").mean()
                    a, b_ = int((oo[r] == "DOWN").sum()), int((cc[r] == "DOWN").sum())
                    o, c = oo, cc
                ozet.append(dict(yansitma=r, kontrol=ad, bolum=bolum, n_ok=len(o), n_ctl=len(c),
                                 ok_oran=o_oran, ctl_oran=c_oran, lift=o_oran - c_oran,
                                 p=fisher(a, len(o), b_, len(c))))
    oz = pd.DataFrame(ozet)
    oz.to_csv("/tmp/ok_direnc_taban_ozet.csv", index=False)

    etiket = {"r1": "R1 -1/+1 ATR (aşağı = başarı)", "r2": "R2 -2/+1 ATR",
              "r3": "R3 seviye 10 bar sonra (aşağıda kaldı)"}
    for r in ("r1", "r2", "r3"):
        print(f"\n=== {etiket[r]} ===")
        for ad in ("A tüm barlar", "B dirençteki barlar"):
            k = oz[(oz.yansitma == r) & (oz.kontrol == ad) & (oz.bolum == "K")]
            dd = oz[(oz.yansitma == r) & (oz.kontrol == ad) & (oz.bolum == "D")]
            if k.empty:
                continue
            kk = k.iloc[0]
            if dd.empty:
                print(f"  {ad:20s} nK={int(kk.n_ok):4d} lift {kk.lift:+.1f} | doğrulamada yok")
                continue
            ddd = dd.iloc[0]
            print(f"  {ad:20s} | K: n={int(kk.n_ok):4d} ok %{kk.ok_oran:.1f} ctl %{kk.ctl_oran:.1f} "
                  f"lift {kk.lift:+.1f} p={kk.p:.4g} | D: n={int(ddd.n_ok):4d} "
                  f"ok %{ddd.ok_oran:.1f} ctl %{ddd.ctl_oran:.1f} lift {ddd.lift:+.1f} p={ddd.p:.4g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
