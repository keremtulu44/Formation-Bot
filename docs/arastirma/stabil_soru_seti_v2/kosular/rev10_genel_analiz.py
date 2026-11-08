"""GENEL ANALIZ (rev10): havuzlanmis katman etkisi + senaryo-stratifiye MH testi + aile tablolari."""
import numpy as np, pandas as pd, math, json

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
ev["side_a"] = ev.gecis.str.split(" -> ").str[0].str.split("+").str[0]
ev["beh_a"]  = ev.gecis.str.split(" -> ").str[0].str.split("+").str[1]
ev["side_b"] = ev.gecis.str.split(" -> ").str[1].str.split("+").str[0]
ev["beh_b"]  = ev.gecis.str.split(" -> ").str[1].str.split("+").str[1]

BASE = {}
for sp in ["kesif", "dogrulama"]:
    b = bd[bd.split == sp]
    BASE[sp] = dict(n=len(b), up=(b["first"] == "UP").mean(), down=(b["first"] == "DOWN").mean())

def pnorm(z):  # ust kuyruk
    return 0.5 * math.erfc(z / math.sqrt(2))

def lift_stats(sub, sp, key="UP"):
    n = len(sub); k = int((sub["first"] == key).sum())
    if n == 0: return n, None, None, None
    p = k / n
    base = BASE[sp][key.lower()]
    se = math.sqrt(base * (1 - base) / n)
    z = (p - base) / se if se > 0 else 0.0
    return n, p, (p - base) * 100, pnorm(z)

def mh(strata):
    """strata: list of (a_up,a_dn,b_up,b_dn); A = maruz (kosul var), B = referans."""
    R = S = 0.0; VR = 0.0
    for a, b, c, d in strata:
        n = a + b + c + d
        if n < 2: continue
        r1 = a + b; r2 = c + d; c1 = a + c; c2 = b + d
        R += a * d / n; S += b * c / n
        VR += r1 * r2 * c1 * c2 / (n * n * (n - 1))
    if VR <= 0: return None
    chi = (R - S) ** 2 / VR
    return dict(OR=(R / S) if S > 0 else float("inf"), chi2=chi,
                p=math.erfc(math.sqrt(chi / 2)), R=R, S=S)

out = []
log = []

# ---------- G1: havuzlanmis katman etkisi (tum senaryolar tek havuz) ----------
log.append("### G1 — Havuzlanmis katman etkisi (tum olaylar, senaryo ayrimi yok)")
log.append(f"{'katman':16s} {'bolme':10s} {'n':>5s} {'UP%':>6s} {'UP lift':>8s} {'p_up':>7s} {'DN%':>6s} {'DN lift':>8s} {'p_dn':>7s}")
for attr, bands in [("rb", ["dusuk", "normal", "yuksek"]),
                    ("gb", ["yonsuz", "orta", "buyuk"]),
                    ("kb", ["alt", "orta", "ust"])]:
    for bn in bands:
        for sp in ["kesif", "dogrulama"]:
            sub = ev[(ev[attr] == bn) & (ev.split == sp)]
            nu, pu, lu, zu = lift_stats(sub, sp, "UP")
            nd, pd_, ld, zd = lift_stats(sub, sp, "DOWN")
            if nu < 30:
                log.append(f"{attr+'='+bn:16s} {sp:10s} {nu:5d}   (n<30, yuzde yok)")
                continue
            log.append(f"{attr+'='+bn:16s} {sp:10s} {nu:5d} {pu*100:6.1f} {lu:+8.1f} {zu:7.4f} {pd_*100:6.1f} {ld:+8.1f} {zd:7.4f}")
            out.append(dict(analiz="G1", katman=f"{attr}={bn}", bolme=sp, n=nu,
                            up_yuzde=round(pu*100, 1), up_lift=round(lu, 1), p_up=round(zu, 4),
                            dn_yuzde=round(pd_*100, 1), dn_lift=round(ld, 1), p_dn=round(zd, 4)))

# ---------- G2: senaryo-stratifiye MH (genel, tek test) ----------
log.append("")
log.append("### G2 — Senaryo-stratifiye Mantel-Haenszel (tek genel test, coklu karsilastirma yok)")
comparisons = [
    ("rvol yuksek vs dusuk (UP/DOWN)", "rb", "yuksek", "dusuk"),
    ("govde buyuk vs yonsuz (UP/DOWN)", "gb", "buyuk", "yonsuz"),
    ("kapanis ust vs alt (UP/DOWN)", "kb", "ust", "alt"),
    ("onayli mum (govde>=.50 & kpoz>=.65) vs zayif (govde<.20 & rvol<.8)", "combo", "onay", "zayif"),
]
ev["combo"] = None
ev.loc[(ev.govde >= 0.50) & (ev.kpoz >= 0.65), "combo"] = "onay"
ev.loc[(ev.govde < 0.20) & (ev.rvol < 0.8), "combo"] = "zayif"
for sp in ["kesif", "dogrulama"]:
    log.append(f"-- {sp}")
    for label, attr, A, B in comparisons:
        strata = []
        for g, grp in ev[ev.split == sp].groupby("gecis"):
            ga = grp[grp[attr] == A]; gb_ = grp[grp[attr] == B]
            a_up = int((ga["first"] == "UP").sum()); a_dn = int((ga["first"] == "DOWN").sum())
            b_up = int((gb_["first"] == "UP").sum()); b_dn = int((gb_["first"] == "DOWN").sum())
            if a_up + a_dn + b_up + b_dn >= 10:
                strata.append((a_up, a_dn, b_up, b_dn))
        r = mh(strata)
        if r is None:
            log.append(f"   {label:62s} yetersiz"); continue
        nA = sum(s[0] + s[1] for s in strata); nB = sum(s[2] + s[3] for s in strata)
        log.append(f"   {label:62s} nA={nA:4d} nB={nB:4d} OR={r['OR']:6.2f} chi2={r['chi2']:6.2f} p={r['p']:.5f} katman={len(strata)}")
        out.append(dict(analiz="G2", katman=label, bolme=sp, n=nA + nB, oran=round(r["OR"], 3),
                        chi2=round(r["chi2"], 2), p=round(r["p"], 5), katman_sayisi=len(strata)))

# ---------- G3: aile tablolari (59 hucre yerine yapisal aile) ----------
def aile_table(key, ad):
    log.append("")
    log.append(f"### G3 — {ad} (senaryolar aile olarak havuzlandi)")
    log.append(f"{'aile':22s} {'nK':>5s} {'UPk%':>6s} {'liftK':>6s} {'nD':>5s} {'UPd%':>6s} {'liftD':>6s} {'pK_up':>7s} {'pK_dn':>7s}")
    rows = []
    for fam, grp in ev.groupby(key):
        nk = len(grp[grp.split == "kesif"]); nd = len(grp[grp.split == "dogrulama"])
        if nk < 30: continue
        subk = grp[grp.split == "kesif"]
        n1, pk, lk, zk = lift_stats(subk, "kesif", "UP")
        _, pkd, lkd, zkd = lift_stats(subk, "kesif", "DOWN")
        if nd >= 30:
            subd = grp[grp.split == "dogrulama"]
            _, pv, lv, zv = lift_stats(subd, "dogrulama", "UP")
            _, pvd, lvd, zvd = lift_stats(subd, "dogrulama", "DOWN")
            sD = f"{pv*100:6.1f} {lv:+6.1f}"
        else:
            sD = "     -      -"
        log.append(f"{str(fam):22s} {nk:5d} {pk*100:6.1f} {lk:+6.1f} {nd:5d} {sD} {zk:7.4f} {zkd:7.4f}")
        rows.append(dict(analiz="G3", aile_ekseni=ad, aile=str(fam), nK=nk,
                         UPk=round(pk*100, 1), liftK_up=round(lk, 1), DNk=round(pkd*100, 1),
                         liftK_dn=round(lkd, 1), pK_up=round(zk, 4), pK_dn=round(zkd, 4),
                         nD=nd, UPd=(round(pv*100, 1) if nd >= 30 else None),
                         liftD_up=(round(lv, 1) if nd >= 30 else None)))
    return rows

rows = []
rows += aile_table("side_a", "kaynak fiyat yeri")
rows += aile_table("beh_a", "kaynak destek davranisi")
rows += aile_table("beh_b", "hedef destek davranisi")
# birlesik aile: (kaynak yer + hedef yer)
ev["yer_gecisi"] = ev.side_a + "->" + ev.side_b
ev["beh_gecisi"] = ev.beh_a + "->" + ev.beh_b
rows += aile_table("yer_gecisi", "fiyat yeri gecisi")
rows += aile_table("beh_gecisi", "destek davranisi gecisi")

# ---------- G4: 5 OK-V hucresinin katman detayi (bilgi amacli) ----------
OKV = ["ust+asagi -> ust+sabit", "ust+asagi -> yapisik+asagi", "ust+asagi -> alt+asagi",
       "ust+sabit -> yapisik+sabit", "ust+yukari -> alt+yukari", "ust+sabit -> ust+yukari"]
log.append("")
log.append("### G4 — rev9'un 5 OK-V hucresi + watchlist: katman kirilimi (bilgi amacli)")
log.append(f"{'senaryo':32s} {'katman':16s} {'nK':>4s} {'DNk%':>6s} {'nD':>4s} {'DNd%':>6s}")
for g in OKV:
    g_ = ev[ev.gecis == g]
    for attr, bands in [("rb", ["dusuk", "normal", "yuksek"]), ("gb", ["yonsuz", "orta", "buyuk"])]:
        for bn in bands:
            sk = g_[(g_[attr] == bn) & (g_.split == "kesif")]
            sd = g_[(g_[attr] == bn) & (g_.split == "dogrulama")]
            if len(sk) < 15: continue
            dk = (sk["first"] == "DOWN").mean() * 100; dd = (sd["first"] == "DOWN").mean() * 100 if len(sd) else np.nan
            log.append(f"{g:32s} {attr+'='+bn:16s} {len(sk):4d} {dk:6.1f} {len(sd):4d} "
                       f"{(dd if len(sd) >= 10 else float('nan')):6.1f}")

print("\n".join(log))
out.extend(rows)
pd.DataFrame(out).to_csv("/tmp/gen_out.csv", index=False)
open("/tmp/gen_log.txt", "w", encoding="utf-8").write("\n".join(log))
print("\n--- yazildi: /tmp/gen_out.csv , /tmp/gen_log.txt")
