"""▲ "avantajı yok" sonucu doğru mu? — TABANLI (control'lü) replay.

ÖNCEKİ ÖLÇÜMÜN HATASI (kabul)
-----------------------------
`stabil_ok_bayrak_replay.py` ▲'nın yön isabetini **taban olmadan** yorumladı:
%50,9'u "yazı tura" saydı. Oysa aynı sembollerde, aynı dönemde, aynı ufukta
*ok olmayan* barların isabeti de %50 olabilir — ya da %44. Tabanı ölçmeden
"avantaj yok" denemez. Ayrıca ±1 ATR **simetrik** yarış, okun iddiasını
("seviye geri alındı") yansıtmıyor.

SORU (ölçümden ÖNCE kilitlendi)
------------------------------
Dolu ▲ (K1/K2) okları, aynı sembol/dönemdeki **kontrol barlarına** kıyasla
anlamlı avantaj sağlıyor mu? Üç ayrı "yansıtma" ile sorulur.

KÜTLE / BÖLÜNME
---------------
Günlük (1d), `backfill_data` tüm semboller (≥300 bar). Bölünme:
`sha256(sembol)%10 < 6` → keşif (K), kalanı doğrulama (D).

KONTROLLER (aynı sembol, aynı dönem, aynı ufuk)
----------------------------------------------
A) **Tüm barlar** (ok olmayan her bar; geçerli ATR ve 16 ileri bar şartı)
B) **Destekteki barlar**: |dist_atr| ≤ 0,50 ve o barda ok yok — "ok" ile
   "desteğe yakın olmak" ayrışsın diye (eşleştirilmiş kontrol)

ÜÇ YANSITMA
-----------
R1 simetrik:  ilk +1 ATR (UP) mi −1 ATR (DOWN) mü  → "yön yarışı"
R2 asimetrik: +2 ATR önce mi −1 ATR önce mi (2:1)  → "koşu var mı"
R3 seviye:    t+10'da kapanış, okun seviyesinin üstünde mi → "seviye tuttu mu"
   (kontrol için aynı tanım: o barın kendi seviyesi)

EŞİKLER (kilitli)
-----------------
Hücre kullanılabilir: nK ≥ 50 ve nD ≥ 20. "Avantaj var" iddiası için:
liftK ≥ +6 puan **ve** liftD ≥ +1 puan **ve** iki kümede tek taraflı Fisher
p < 0,01. Aksi hâlde "avantaj ölçülmedi" (yok değil — ölçülmedi).

REPLAY
------
    PYTHONPATH=. .venv/bin/python research/stabil_ok_taban_replay.py
    → /tmp/ok_taban_oklar.csv · /tmp/ok_taban_ozet.csv
"""
from __future__ import annotations

import glob
import hashlib
import math
import os

import numpy as np
import pandas as pd

from domain_engines.stabil.signals import _causal_atr14
from domain_engines.stabil.runtime import evaluate_stabil_symbol
from research.stabil_ok_denetimi import denetle

UFUK = 16
SEVIYE_BAR = 10
YAKIN_ATR = 0.50
ALFA = 0.01
LIMIT = int(os.environ.get("LIMIT", "0")) or None


def kesif(sembol: str) -> bool:
    return int(hashlib.sha256(sembol.encode()).hexdigest(), 16) % 10 < 6


def yaris(kapanis: np.ndarray, atr: np.ndarray, i: int, yukari: float, asagi: float) -> str:
    """i barından sonra ilk hangi eşik: +yukari ATR (UP) / -asagi ATR (DOWN)."""
    n = len(kapanis)
    giris, birim = kapanis[i], float(atr[i])
    for j in range(1, min(UFUK, n - i - 1) + 1):
        if kapanis[i + j] >= giris + yukari * birim:
            return "UP"
        if kapanis[i + j] <= giris - asagi * birim:
            return "DOWN"
    return "NEITHER"


def fisher(a: int, n1: int, b: int, n2: int) -> float:
    """Tek taraflı: P(X ≥ a) — bayrak/ok lehine (üstünlük testi)."""
    toplam, n = a + b, n1 + n2
    if n == 0 or n1 == 0:
        return 1.0
    payda = math.comb(n, n1)
    p = 0.0
    for x in range(a, min(n1, toplam) + 1):
        p += math.comb(toplam, x) * math.comb(n - toplam, n1 - x) / payda
    return min(1.0, p)


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
            out = evaluate_stabil_symbol(sembol, "1d", d, daily_frame=d)
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

        ok_barlar = set()
        for k in denetle(out.bar_behaviors):
            if k.ok == "▲" and k.kural_adi in {"K1", "K2"}:
                ok_barlar.add(k.bar_index)

        for b in out.bar_behaviors:
            i = int(b.bar_index)
            if i + UFUK + 1 >= n or not np.isfinite(atr[i]) or atr[i] <= 0:
                continue
            seviye = b.support_level
            satir = dict(
                sembol=sembol, bolum=bolum, bar=i,
                r1=yaris(kapanis, atr, i, 1.0, 1.0),
                r2=yaris(kapanis, atr, i, 2.0, 1.0),
                r3=(bool(kapanis[i + SEVIYE_BAR] >= float(seviye))
                    if seviye else None),
                yakin=bool(b.dist_atr is not None and abs(float(b.dist_atr)) <= YAKIN_ATR),
            )
            (ok_satir if i in ok_barlar else ctl_satir).append(satir)

    ok = pd.DataFrame(ok_satir)
    ctl = pd.DataFrame(ctl_satir)
    ok.to_csv("/tmp/ok_taban_oklar.csv", index=False)
    ctl.to_csv("/tmp/ok_taban_kontrol.csv", index=False)
    print(f"sembol {len(dosyalar) - atlanan}/{len(dosyalar)} · ▲ {len(ok)} · kontrol barı {len(ctl)}")

    ozet = []
    for r in ("r1", "r2", "r3"):
        for ad, alt in (("A tüm barlar", ctl), ("B destekteki barlar", ctl[ctl.yakin])):
            for bolum in ("K", "D"):
                o = ok[(ok.bolum == bolum) & ok[r].notna()]
                c = alt[(alt.bolum == bolum) & alt[r].notna()]
                if o.empty or c.empty:
                    continue
                if r == "r3":
                    o_oran = 100 * o[r].astype(bool).mean()
                    c_oran = 100 * c[r].astype(bool).mean()
                    a, b = int(o[r].astype(bool).sum()), int(c[r].astype(bool).sum())
                else:
                    oo = o[o[r] != "NEITHER"]
                    cc = c[c[r] != "NEITHER"]
                    o_oran = 100 * (oo[r] == "UP").mean()
                    c_oran = 100 * (cc[r] == "UP").mean()
                    a, b = int((oo[r] == "UP").sum()), int((cc[r] == "UP").sum())
                    o, c = oo, cc
                ozet.append(dict(yansitma=r, kontrol=ad, bolum=bolum, n_ok=len(o), n_ctl=len(c),
                                 ok_oran=o_oran, ctl_oran=c_oran, lift=o_oran - c_oran,
                                 p=fisher(a, len(o), b, len(c))))
    oz = pd.DataFrame(ozet)
    oz.to_csv("/tmp/ok_taban_ozet.csv", index=False)

    etiket = {"r1": "R1 ±1 ATR yarışı", "r2": "R2 +2/−1 ATR", "r3": "R3 seviye 10 bar sonra"}
    for r in ("r1", "r2", "r3"):
        print(f"\n=== {etiket[r]} ===")
        for ad in ("A tüm barlar", "B destekteki barlar"):
            k = oz[(oz.yansitma == r) & (oz.kontrol == ad) & (oz.bolum == "K")]
            dd = oz[(oz.yansitma == r) & (oz.kontrol == ad) & (oz.bolum == "D")]
            if k.empty:
                continue
            kk = k.iloc[0]
            if dd.empty:
                print(f"  {ad:20s} nK={int(kk.n_ok):4d} ok %{kk.ok_oran:.1f} ctl %{kk.ctl_oran:.1f} "
                      f"lift {kk.lift:+.1f} | doğrulamada yok")
                continue
            ddd = dd.iloc[0]
            print(f"  {ad:20s} | K: n={int(kk.n_ok):4d} ok %{kk.ok_oran:.1f} ctl %{kk.ctl_oran:.1f} "
                  f"lift {kk.lift:+.1f} p={kk.p:.4f} | D: n={int(ddd.n_ok):4d} "
                  f"lift {ddd.lift:+.1f} p={ddd.p:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
