"""GENEL kosullandirma kosusu (rev10).

Amac: rev9'da bulunan 5 OK-V adayini TEKER TEKER hacim/govde ile keskinlestirmek yerine,
tek bir kosullandirma katmanini (rvol + govde) AYNI ANDA tum senaryolara uygulamak.

Olcum sozlesmesi v2.0 AYNEN korunur: ayni 1d TF, ayni nedensel ATR14, ayni 9 durum,
ayni gecis tanimi, ayni 5 gun dedup, ayni first_1atr_16, ayni taban ornekleme.
Sadece giris gunune 3 NITELIK eklenir: rvol, govde, kapanis_poz.
"""
import numpy as np, pandas as pd, glob, os, hashlib, time
from domain_engines.stabil import build_single_pass_history, classify_candidate_support_regimes
from domain_engines.stabil.signals import _causal_atr14
from data import resample_ohlcv

LIMIT = 120; FWD = 16; DEDUP = 5

def split_of(sym):
    h = int(hashlib.sha256(sym.encode()).hexdigest(), 16) % 10
    return "kesif" if h < 6 else "dogrulama"

syms = sorted(os.path.basename(p).split("_")[0] for p in glob.glob("backfill_data/*_1d.csv.gz"))[:LIMIT]
ev = []; base = []
t0 = time.time()

for k, s in enumerate(syms):
    if k % 20 == 0:
        print(f"...{k}/{len(syms)} ({time.time()-t0:.0f}s)", flush=True)
    try:
        d = pd.read_csv(f"backfill_data/{s}_1d.csv.gz", compression="gzip",
                        parse_dates=["bar_time"]).set_index("bar_time")
        h = pd.read_csv(f"backfill_data/{s}_1h.csv.gz", compression="gzip",
                        parse_dates=["bar_time"]).set_index("bar_time")
        h4 = resample_ohlcv(h, "4h"); hist = build_single_pass_history(s, d, h4)
    except Exception:
        continue
    regs = classify_candidate_support_regimes(hist.support_timeline)
    H = d["high"].to_numpy(float); L = d["low"].to_numpy(float)
    C = d["close"].to_numpy(float); O = d["open"].to_numpy(float)
    V = d["volume"].to_numpy(float)
    atr = _causal_atr14(H, L, C, 14); n = len(C)
    pts = [(int(rp.daily_index), float(rp.support_level)) for rp in regs if rp.support_level]
    if len(pts) < 30:
        continue
    lvl = np.full(n, np.nan); pidx = dict(pts); last = np.nan
    for t in range(n):
        if t in pidx: last = pidx[t]
        lvl[t] = last

    def state(t):
        if t < 12 or not np.isfinite(atr[t]) or atr[t] <= 0 or not np.isfinite(lvl[t]): return None
        j = None
        for i2, l2 in reversed(pts):
            if i2 <= t - 10: j = (i2, l2); break
        if j is None: return None
        dl = (lvl[t] - j[1]) / atr[t]
        beh = "sabit" if abs(dl) < 0.02 else ("yukari" if dl > 0 else "asagi")
        dd = (C[t] - lvl[t]) / atr[t]
        side = "alt" if dd < -0.05 else ("yapisik" if dd <= 0.5 else "ust")
        return f"{side}+{beh}"

    def outcome(t):
        a = atr[t]; up = C[t] + a; dn = C[t] - a
        for k2 in range(t + 1, min(n, t + FWD + 1)):
            hu = H[k2] >= up; hd = L[k2] <= dn
            if hu and hd: return "AMBIG"
            if hu: return "UP"
            if hd: return "DOWN"
        return "NEITHER"

    st = [state(t) for t in range(n)]
    sp = split_of(s); last_ev = -999
    for t in range(13, n - FWD - 1):
        a, b = st[t-1], st[t]
        if a is None or b is None or a == b: continue
        if t - last_ev < DEDUP: continue
        last_ev = t
        # --- nedensel nitelikler (giris gunu) ---
        rvol = V[t] / V[max(0, t-20):t].mean() if t >= 20 and V[max(0, t-20):t].mean() > 0 else np.nan
        govde = abs(C[t] - O[t]) / atr[t]
        rng = H[t] - L[t]
        kpoz = (C[t] - L[t]) / rng if rng > 0 else np.nan
        dd = (C[t] - lvl[t]) / atr[t]
        ev.append(dict(sym=s, split=sp, date=str(d.index[t])[:10], gecis=f"{a} -> {b}",
                       first=outcome(t), ret=(C[t+FWD]-C[t])/atr[t],
                       rvol=rvol, govde=govde, kpoz=kpoz, d=dd))
    for t in range(13, n - FWD - 1, 5):
        if not np.isfinite(atr[t]) or atr[t] <= 0: continue
        base.append(dict(sym=s, split=sp, first=outcome(t)))

df = pd.DataFrame(ev); bd = pd.DataFrame(base)
df.to_csv("/tmp/gen_ev.csv", index=False); bd.to_csv("/tmp/gen_base.csv", index=False)
print(f"\nolay: {len(df)} | sembol: {df.sym.nunique()} | taban: {len(bd)}")
print("gecis sayisi:", df.gecis.nunique())
for sp in ["kesif", "dogrulama"]:
    b = bd[bd.split == sp]
    print(f"TABAN {sp:10s} n={len(b):5d} UP %{(b['first']=='UP').mean()*100:5.1f} DOWN %{(b['first']=='DOWN').mean()*100:5.1f}")
print(df[["rvol", "govde", "kpoz"]].describe().to_string())
