"""G5 — kosullandirma gercekten ise yariyor mu? (genel testler)
(a) 59 senaryo icinde isaret testi: kosul lift'i kac senaryoda artiriyor?
(b) 5 OK-V ailesi icinde katman kirilimi + stratifiye test
(c) kompozisyon kaniti: kosul ile senaryo iliskisi (Cramer's V / beklenti)
"""
import numpy as np, pandas as pd, math

ev = pd.read_csv("/tmp/gen_ev.csv")
bd = pd.read_csv("/tmp/gen_base.csv")
def rband(x):
    if not np.isfinite(x): return None
    return "dusuk" if x < 0.8 else ("normal" if x < 1.2 else "yuksek")
def gband(x):
    if not np.isfinite(x): return None
    return "yonsuz" if x < 0.20 else ("orta" if x < 0.50 else "buyuk")
def kband(x):
    if not np.isfinite(x): return None
    return "alt" if x < 0.35 else ("orta" if x <= 0.65 else "ust")
ev["rb"] = ev.rvol.map(rband); ev["gb"] = ev.govde.map(gband); ev["kb"] = ev.kpoz.map(kband)

BASE = {}
for sp in ["kesif", "dogrulama"]:
    b = bd[bd.split == sp]
    BASE[sp] = dict(up=(b["first"] == "UP").mean(), down=(b["first"] == "DOWN").mean())

def mh(strata):
    R = S = 0.0; VR = 0.0
    for a, b, c, d in strata:
        n = a + b + c + d
        if n < 4: continue
        r1 = a + b; r2 = c + d; c1 = a + c; c2 = b + d
        R += a * d / n; S += b * c / n
        VR += r1 * r2 * c1 * c2 / (n * n * (n - 1))
    if VR <= 0 or S == 0: return None
    chi = (R / S - 1) ** 2 * S * S / VR if False else (R - S) ** 2 / VR
    return dict(OR=R / S, chi2=chi, p=math.erfc(math.sqrt(chi / 2)))

print("### G5a — isaret testi: kosul (A) lift'i B'ye gore kac senaryoda BUYUTUYOR?")
comps = [("rb", "yuksek", "dusuk", "DOWN"), ("gb", "buyuk", "yonsuz", "DOWN"),
         ("kb", "alt", "ust", "DOWN"), ("kb", "ust", "alt", "UP")]
for sp in ["kesif", "dogrulama"]:
    print(f"-- {sp}")
    for attr, A, B, yon in comps:
        won = lost = 0
        for g, grp in ev[ev.split == sp].groupby("gecis"):
            ga = grp[grp[attr] == A]; gb_ = grp[grp[attr] == B]
            if len(ga) < 20 or len(gb_) < 20: continue
            ra = (ga["first"] == yon).mean(); rb_ = (gb_["first"] == yon).mean()
            if ra > rb_: won += 1
            elif ra < rb_: lost += 1
        n = won + lost
        if n == 0:
            print(f"   {attr} {A}>{B} ({yon}): karsilastirilabilir senaryo yok"); continue
        # iki terimli isaret testi (tek yonlu, A lehine)
        p = sum(math.comb(n, k) for k in range(won, n + 1)) / 2 ** n
        print(f"   {attr} {A}>{B} ({yon}): A lehine {won}, B lehine {lost} (n={n}) isaret-p={p:.4f}")

print("\n### G5b — 5 OK-V ailesi (tek govde, senaryo ayrimi yok): katman kirilimi")
OKV = ["ust+asagi -> ust+sabit", "ust+asagi -> yapisik+asagi", "ust+asagi -> alt+asagi",
       "ust+sabit -> yapisik+sabit", "ust+yukari -> alt+yukari"]
fam = ev[ev.gecis.isin(OKV)]
for sp in ["kesif", "dogrulama"]:
    s = fam[fam.split == sp]
    print(f"-- {sp}  n={len(s)}  DOWN %{(s['first']=='DOWN').mean()*100:.1f} (taban {BASE[sp]['down']*100:.1f})")
    for attr, bands in [("rb", ["dusuk", "normal", "yuksek"]), ("gb", ["yonsuz", "orta", "buyuk"]),
                        ("kb", ["alt", "orta", "ust"])]:
        for bn in bands:
            q = s[s[attr] == bn]
            if len(q) < 25: continue
            print(f"     {attr}={bn:7s} n={len(q):4d} DOWN %{(q['first']=='DOWN').mean()*100:5.1f} "
                  f"lift {(q['first']=='DOWN').mean()*100 - BASE[sp]['down']*100:+5.1f}")
    strata = []
    for g, grp in s.groupby("gecis"):
        ga = grp[grp.rb == "yuksek"]; gb_ = grp[grp.rb == "dusuk"]
        strata.append((int((ga["first"]=="UP").sum()), int((ga["first"]=="DOWN").sum()),
                       int((gb_["first"]=="UP").sum()), int((gb_["first"]=="DOWN").sum())))
    r = mh(strata)
    if r: print(f"     [MH] rvol yuksek vs dusuk (▼ ailesi icinde): OR={r['OR']:.2f} chi2={r['chi2']:.2f} p={r['p']:.4f}")

print("\n### G5c — kompozisyon kaniti: kosul senaryoya bagli mi?")
for attr, bands in [("rb", ["dusuk", "normal", "yuksek"]), ("kb", ["alt", "orta", "ust"])]:
    ct = pd.crosstab(ev.gecis, ev[attr])
    ct = ct.loc[ct.sum(axis=1) >= 30]
    exp = np.outer(ct.sum(axis=1), ct.sum(axis=0)) / ct.values.sum()
    chi2 = ((ct.values - exp) ** 2 / exp).sum()
    dof = (ct.shape[0] - 1) * (ct.shape[1] - 1)
    # Cramer's V
    V = math.sqrt(chi2 / (ct.values.sum() * (min(ct.shape) - 1)))
    print(f"{attr}: senaryo x katman Cramer's V = {V:.3f} (chi2={chi2:.0f}, dof={dof}, hucre={ct.shape})")
    share = (ct.div(ct.sum(axis=1), axis=0)).round(2)
    up_share = ct.sum(axis=0) / ct.values.sum()
    top = share[[c for c in ct.columns if c in bands]]
    print("   katman payi (tum olaylar):", {k: round(v, 2) for k, v in up_share.items()})
    dev = (top - up_share).abs().max(axis=1).sort_values(ascending=False).head(4)
    print("   payi en cok sapan senaryolar:", {k: round(v, 2) for k, v in dev.items()})
