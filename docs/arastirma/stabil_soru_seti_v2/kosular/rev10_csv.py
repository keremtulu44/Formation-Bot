"""Konsolide CSV: genel okuma (rev10). Tek kaynak: /tmp/gen_ev.csv + /tmp/gen_base.csv."""
import numpy as np, pandas as pd, math

ev = pd.read_csv("/tmp/gen_ev.csv"); bd = pd.read_csv("/tmp/gen_base.csv")
BASE = {}
for sp in ["kesif", "dogrulama"]:
    b = bd[bd.split == sp]
    BASE[sp] = dict(up=(b["first"] == "UP").mean(), down=(b["first"] == "DOWN").mean())
def rb(x):
    return "dusuk" if x < 0.8 else ("normal" if x < 1.2 else "yuksek")
def gb(x):
    return "yonsuz" if x < 0.20 else ("orta" if x < 0.50 else "buyuk")
def kb(x):
    return "alt" if x < 0.35 else ("orta" if x <= 0.65 else "ust")
ev["rb"] = ev.rvol.map(rb); ev["gb"] = ev.govde.map(gb); ev["kb"] = ev.kpoz.map(kb)
def pnorm(z): return 0.5 * math.erfc(z / math.sqrt(2))
def st(sub, sp, yon):
    n = len(sub); k = int((sub["first"] == yon).sum())
    if n == 0: return n, None, None, None
    p = k / n; base = BASE[sp][yon.lower()]
    se = math.sqrt(base * (1 - base) / n)
    return n, round(p * 100, 1), round((p - base) * 100, 1), round(pnorm((p - base) / se), 4) if se else None
def mh(strata):
    R = S = 0.0; VR = 0.0
    for a, b, c, d in strata:
        n = a + b + c + d
        if n < 4: continue
        r1 = a + b; r2 = c + d; c1 = a + c; c2 = b + d
        R += a * d / n; S += b * c / n
        VR += r1 * r2 * c1 * c2 / (n * n * (n - 1))
    if VR <= 0 or S == 0: return None
    chi = (R - S) ** 2 / VR
    return round(R / S, 2), round(math.erfc(math.sqrt(chi / 2)), 4)

rows = []
def add(analiz, kalem, bolme, n, yuzde, lift, p, yorum=""):
    rows.append(dict(analiz=analiz, kalem=kalem, bolme=bolme, n=n, yuzde=yuzde,
                     lift_puan=lift, p=p, yorum=yorum))

# A1 havuzlanmis katman
for attr, bands, ad in [("rb", ["dusuk", "normal", "yuksek"], "rvol"),
                        ("gb", ["yonsuz", "orta", "buyuk"], "govde"),
                        ("kb", ["alt", "orta", "ust"], "kapanis_poz")]:
    for bn in bands:
        for sp in ["kesif", "dogrulama"]:
            s = ev[(ev[attr] == bn) & (ev.split == sp)]
            n, pu, lu, zu = st(s, sp, "UP"); _, pd_, ld, zd = st(s, sp, "DOWN")
            if n < 30: continue
            add("A1 havuz", f"{ad}={bn}", sp, n, pu, lu, zu, "UP tarafi (DOWN lift: %+.1f, p=%.4f)" % (ld, zd))
# A2 MH
ev["combo"] = None
ev.loc[(ev.govde >= 0.50) & (ev.kpoz >= 0.65), "combo"] = "onay"
ev.loc[(ev.govde < 0.20) & (ev.rvol < 0.8), "combo"] = "zayif"
comps = [("rvol yuksek vs dusuk", "rb", "yuksek", "dusuk"),
         ("govde buyuk vs yonsuz", "gb", "buyuk", "yonsuz"),
         ("kapanis ust vs alt", "kb", "ust", "alt"),
         ("onayli mum vs zayif mum", "combo", "onay", "zayif")]
for label, attr, A, B in comps:
    for sp in ["kesif", "dogrulama"]:
        strata = []
        for g, grp in ev[ev.split == sp].groupby("gecis"):
            ga = grp[grp[attr] == A]; gbb = grp[grp[attr] == B]
            strata.append((int((ga["first"] == "UP").sum()), int((ga["first"] == "DOWN").sum()),
                           int((gbb["first"] == "UP").sum()), int((gbb["first"] == "DOWN").sum())))
        r = mh(strata)
        n = sum(s[0] + s[1] + s[2] + s[3] for s in strata)
        if r: add("A2 MH (senaryo-stratifiye)", label, sp, n, r[0], None, r[1],
                  "OR<1 = kosul DOWN olasiligini artiriyor; n = karsilastirilabilir olay")
# A3 aileler
ev["side_a"] = ev.gecis.str.split(" -> ").str[0].str.split("+").str[0]
ev["beh_a"] = ev.gecis.str.split(" -> ").str[0].str.split("+").str[1]
ev["beh_b"] = ev.gecis.str.split(" -> ").str[1].str.split("+").str[1]
ev["side_b"] = ev.gecis.str.split(" -> ").str[1].str.split("+").str[0]
ev["yer"] = ev.side_a + "->" + ev.side_b
ev["beh"] = ev.beh_a + "->" + ev.beh_b
for key, ad in [("side_a", "A3a kaynak fiyat yeri"), ("beh_a", "A3b kaynak destek davranisi"),
                ("beh_b", "A3c hedef destek davranisi"), ("yer", "A3d fiyat yeri gecisi"),
                ("beh", "A3e destek davranisi gecisi")]:
    for fam, grp in ev.groupby(key):
        sk = grp[grp.split == "kesif"]; sd = grp[grp.split == "dogrulama"]
        if len(sk) < 30: continue
        nK, pK, lK, zK = st(sk, "kesif", "DOWN")
        if len(sd) >= 30:
            nD, pD, lD, zD = st(sd, "dogrulama", "DOWN")
            add(ad, fam, "kesif->dogrulama", nK, pK, lK, zK, f"DOWN; dogrulama n={nD} %{pD} lift {lD:+} p={zD}")
        else:
            add(ad, fam, "kesif", nK, pK, lK, zK, f"DOWN; dogrulama n={len(sd)} (yetersiz)")
# A4 ▼ ailesi + filtre
OKV = ["ust+asagi -> ust+sabit", "ust+asagi -> yapisik+asagi", "ust+asagi -> alt+asagi",
       "ust+sabit -> yapisik+sabit", "ust+yukari -> alt+yukari"]
filt = (ev.rvol >= 0.8) & (ev.govde >= 0.20)
for label, sel in [("ailesi filtresiz", ev.gecis.isin(OKV)),
                   ("ailesi rvol>=0.8", ev.gecis.isin(OKV) & (ev.rvol >= 0.8)),
                   ("ailesi govde>=0.20", ev.gecis.isin(OKV) & (ev.govde >= 0.20)),
                   ("ailesi rvol>=0.8 & govde>=0.20", ev.gecis.isin(OKV) & filt),
                   ("ailesi rvol<0.8 (elenen)", ev.gecis.isin(OKV) & (ev.rvol < 0.8)),
                   ("ailesi govde<0.20 (elenen)", ev.gecis.isin(OKV) & (ev.govde < 0.20))]:
    for sp in ["kesif", "dogrulama"]:
        s = ev[sel & (ev.split == sp)]
        if len(s) < 20: continue
        n, p, l, z = st(s, sp, "DOWN")
        add("A4 OK-V ailesi", label, sp, n, p, l, z, f"{s.sym.nunique()} sembol, en buyuk sembol pay %{s.sym.value_counts().iloc[0]/n*100:.0f}")
# A5 filtre tum havuza
for sp in ["kesif", "dogrulama"]:
    for label, sel in [("tum olaylar", ev.split == sp), ("filtreli tum olaylar", (ev.split == sp) & filt)]:
        s = ev[sel]; n, p, l, z = st(s, sp, "DOWN")
        add("A5 kontrol (yanlis kullanim)", label, sp, n, p, l, z, "filtre tek basina sinyal uretmiyor")

out = pd.DataFrame(rows)
path = "docs/arastirma/stabil_soru_seti_v2/genel_okuma_2026_11_08.csv"
out.to_csv(path, index=False)
print(out.to_string(index=False))
print("\nyazildi:", path, len(out), "satir")
