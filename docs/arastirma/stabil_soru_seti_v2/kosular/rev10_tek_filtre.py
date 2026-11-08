"""G6 — tek genel filtre: ▼ ailesi icinde rvol>=0.8 & govde>=0.20
Karar: kilitli kural v2.0 (§2.7) aynen uygulanir. Sembol yogunlasmasi da raporlanir."""
import numpy as np, pandas as pd, math

ev = pd.read_csv("/tmp/gen_ev.csv")
bd = pd.read_csv("/tmp/gen_base.csv")
BASE = {}
for sp in ["kesif", "dogrulama"]:
    b = bd[bd.split == sp]
    BASE[sp] = dict(up=(b["first"] == "UP").mean(), down=(b["first"] == "DOWN").mean())

def pnorm(z): return 0.5 * math.erfc(z / math.sqrt(2))
def stats(sub, sp, yon):
    n = len(sub); k = int((sub["first"] == yon).sum())
    if n == 0: return n, None, None, None
    p = k / n; base = BASE[sp][yon.lower()]
    se = math.sqrt(base * (1 - base) / n)
    return n, p * 100, (p - base) * 100, pnorm((p - base) / se) if se > 0 else None

OKV = ["ust+asagi -> ust+sabit", "ust+asagi -> yapisik+asagi", "ust+asagi -> alt+asagi",
       "ust+sabit -> yapisik+sabit", "ust+yukari -> alt+yukari"]
ev["ai̇le_v"] = ev.gecis.isin(OKV)
filt = (ev.rvol >= 0.8) & (ev.govde >= 0.20)
ev["filtre"] = filt

print("### G6a — ▼ ailesi: filtre oncesi / sonrasi (tek govde)")
print(f"{'durum':34s} {'bolme':10s} {'n':>5s} {'DOWN%':>6s} {'lift':>6s} {'p':>8s} {'sembol':>6s} {'en buyuk sembol pay':>18s}")
for label, sel in [("▼ ailesi (filtresiz)", ev.gecis.isin(OKV)),
                   ("▼ ailesi + rvol>=0.8", ev.gecis.isin(OKV) & (ev.rvol >= 0.8)),
                   ("▼ ailesi + govde>=0.20", ev.gecis.isin(OKV) & (ev.govde >= 0.20)),
                   ("▼ ailesi + rvol>=0.8 & govde>=0.20", ev.gecis.isin(OKV) & filt),
                   ("▼ ailesi + rvol<0.8 (DISLANAN)", ev.gecis.isin(OKV) & (ev.rvol < 0.8)),
                   ("▼ ailesi + govde<0.20 (DISLANAN)", ev.gecis.isin(OKV) & (ev.govde < 0.20))]:
    for sp in ["kesif", "dogrulama"]:
        s = ev[sel & (ev.split == sp)]
        n, pc, l, p = stats(s, sp, "DOWN")
        if n == 0:
            print(f"{label:34s} {sp:10s} {0:5d}"); continue
        share = s.sym.value_counts().iloc[0] / n * 100
        print(f"{label:34s} {sp:10s} {n:5d} {pc:6.1f} {l:+6.1f} {p:8.4f} {s.sym.nunique():6d} {share:17.0f}%")

print("\n### G6b — filtrenin senaryo bazinda dagilimi (▼ ailesi, kesif)")
for g in OKV:
    s = ev[(ev.gecis == g) & (ev.split == "kesif")]
    a = s[filt[s.index]]
    print(f"{g:32s} filtresiz n={len(s):4d} DOWN %{(s['first']=='DOWN').mean()*100:5.1f} | "
          f"filtreli n={len(a):4d} DOWN %{(a['first']=='DOWN').mean()*100 if len(a) else float('nan'):5.1f}")

print("\n### G6c — ayni filtre tum havuza uygulanirsa (yanlis kullanim testi)")
for sp in ["kesif", "dogrulama"]:
    for label, sel in [("tum olaylar", ev.split == sp), ("filtreli tum olaylar", (ev.split == sp) & filt)]:
        s = ev[sel]
        n, pc, l, p = stats(s, sp, "DOWN")
        print(f"{label:28s} {sp:10s} n={n:5d} DOWN %{pc:5.1f} lift {l:+5.1f} p={p:.4f}")

print("\n### G6d — yukari tarafi ayni filtreyle (sabit->yukari ailesi, bilgi)")
A = ev[(ev.gecis.str.startswith("sabit")) | (ev.gecis.str.contains("-> "))].copy()
uy = ev[ev.gecis.str.contains("-> ") & ev.gecis.str.split(" -> ").str[1].str.endswith("yukari")]
for sp in ["kesif", "dogrulama"]:
    s = uy[uy.split == sp]; f = uy[(uy.split == sp) & filt]
    n1, p1, l1, q1 = stats(s, sp, "UP"); n2, p2, l2, q2 = stats(f, sp, "UP")
    print(f"{sp:10s} filtre yok n={n1:4d} UP %{p1:5.1f} lift {l1:+5.1f} | filtreli n={n2:4d} UP %{p2:5.1f} lift {l2:+5.1f} p={q2:.4f}")
