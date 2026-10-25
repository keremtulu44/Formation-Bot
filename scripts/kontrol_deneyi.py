# -*- coding: utf-8 -*-
"""Aşama 0 · Kontrol deneyi: formasyon kırılımı, rastgele girişten iyi mi?

SALT OKUNUR. Motor çalıştırılmaz, üretim koduna dokunulmaz.

Fikir: elimizde "kırılım + endeks uyumu" var. Bilmediğimiz şey, formasyonun
kendisinin bir katkısı olup olmadığı. Aynı sembollerde, aynı dönemde, her barda
"endeksin yönünde gir" kuralıyla sanal girişler üretilir ve kırılım gözlemleriyle
birebir aynı baraj/ufuk/ATR normalizasyonuyla kıyaslanır.

  uyumlu rastgele giriş   : yön = endeks eğiminin işareti
  uyumsuz rastgele giriş  : yön = tersi

Kırılım tarafı `var/replay/gozlemler.csv`'den okunur, etiketler ızgaradan
(tl_*/tt_*) türetilir — böylece iki taraf tam aynı tanımla ölçülür.

Ön kayıt: docs/arastirma/PUAN_DOGRULAMA_ON_KAYIT.md
Kabul barı (H0): kırılım(uyumlu) − rastgele(uyumlu) ≥ +3,0 puan ve
sembol kümesi bootstrap GA alt sınırı > 0.

Kullanım:
    python scripts/kontrol_deneyi.py --rapor var/replay/kontrol.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402
from data import resample_ohlcv  # noqa: E402
from patterns.indicators import calculate_atr  # noqa: E402
from puan_analiz import etiketle  # noqa: E402
from puan_tarama import ozellikler  # noqa: E402

UFUK_MAX = 48
GIRIS = "close"          # "close" | "next_open"  (--giris ile değişir)
KADEMELER = (1.0, 1.5, 2.0, 3.0)
# Ön kayıtta sabitlenen 7 etiket varyantı
VARYANTLAR = [(1.0, 1.0, 12), (1.0, 1.0, 24), (1.5, 1.0, 24), (2.0, 1.0, 24),
              (2.0, 1.5, 24), (2.0, 1.0, 48), (3.0, 1.0, 48)]
ANA = (2.0, 1.0, 24)


def ilk_vurus(off: np.ndarray, esik: np.ndarray) -> np.ndarray:
    """off[i, j] = i+j+1 barındaki offset; esik[i] eşiği ilk kez kaçıncı barda
    geçildi (1..48, hiç geçilmediyse 0)."""
    m = off >= esik[:, None]
    t = m.argmax(axis=1) + 1
    return np.where(m.any(axis=1), t, 0)


def etiketle_np(t_fav: np.ndarray, t_adv: np.ndarray, ufuk: int) -> np.ndarray:
    f_ok = (t_fav > 0) & (t_fav <= ufuk)
    a_ok = (t_adv > 0) & (t_adv <= ufuk)
    y = np.full(len(t_fav), np.nan)
    y[f_ok & (~a_ok | (t_fav < t_adv))] = 1.0
    y[a_ok & (~f_ok | (t_adv < t_fav))] = 0.0
    return y


def endeks(tf: str) -> pd.Series:
    d = pd.read_csv(REPO / "backfill_data" / "XU100_1h.csv.gz", compression="gzip",
                    parse_dates=["bar_time"]).set_index("bar_time")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    if tf != "1h":
        d = resample_ohlcv(d, tf)
    c = d["close"]
    return (c / c.shift(20) - 1.0).dropna()


def rastgele_ornek(sembol: str, tf: str, egim: pd.Series) -> List[Dict]:
    """Sembol/TF için her bara sanal giriş; uyumlu ve uyumsuz sonuç sayıları."""
    p = REPO / "backfill_data" / f"{sembol}_1h.csv.gz"
    d = pd.read_csv(p, compression="gzip", parse_dates=["bar_time"]).set_index("bar_time")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    if tf != "1h":
        d = resample_ohlcv(d, tf)
    n = len(d)
    if n < 120:
        return []
    atr = calculate_atr(d, 14).to_numpy(dtype=float)
    high = d["high"].to_numpy(dtype=float)
    low = d["low"].to_numpy(dtype=float)
    close = d["close"].to_numpy(dtype=float)

    son = n - UFUK_MAX - 2
    if son <= 30:
        return []
    idx = np.arange(0, son)
    idx = idx[(atr[idx] > 0) & np.isfinite(atr[idx])]
    if len(idx) == 0:
        return []

    if GIRIS == "next_open":
        giris = d["open"].to_numpy(dtype=float)[idx + 1]
        baslangic = idx + 1
    else:
        giris = close[idx]
        baslangic = idx
    pencere = np.arange(1, UFUK_MAX + 1)
    kollar = np.clip(baslangic[:, None] + pencere[None, :], 0, n - 1)
    yukari = high[kollar] - giris[:, None]           # long lehte
    asagi = giris[:, None] - low[kollar]             # short lehte

    # endeks eğimi (aynı zaman damgasına eşle)
    idx_ns = pd.to_datetime(egim.index, utc=True).asi8
    obs_ns = pd.to_datetime(d.index[idx], utc=True).asi8
    konum = np.searchsorted(idx_ns, obs_ns, side="right") - 1
    gecerli = (konum >= 0) & (konum < len(egim))
    eg = np.full(len(idx), np.nan)
    eg[gecerli] = egim.to_numpy()[konum[gecerli]]
    isaret = np.sign(eg)
    gecerli &= np.isfinite(eg) & (isaret != 0)
    if gecerli.sum() < 50:
        return []

    satirlar = []
    a = atr[idx]
    for leh, ters, ufuk in VARYANTLAR:
        # dört ayrı ilk-vuruş: yukarı/asagi × lehte/ters barajı
        up_leh = ilk_vurus(yukari, (leh * a).astype(float))
        up_ters = ilk_vurus(yukari, (ters * a).astype(float))
        dn_leh = ilk_vurus(asagi, (leh * a).astype(float))
        dn_ters = ilk_vurus(asagi, (ters * a).astype(float))
        y_long = etiketle_np(up_leh, dn_ters, ufuk)    # long: lehte yukarı, ters aşağı
        y_short = etiketle_np(dn_leh, up_ters, ufuk)   # short: lehte aşağı, ters yukarı

        # uyumlu: endeks yukarıysa long, aşağıysa short
        for ad, v, yon in (("uyumlu", np.where(isaret > 0, y_long, y_short), isaret),
                           ("uyumsuz", np.where(isaret > 0, y_short, y_long), -isaret)):
            for y in (1, -1):
                m = gecerli & np.isfinite(v) & (yon == y)
                if m.sum() == 0:
                    continue
                satirlar.append({"sembol": sembol, "tf": tf, "varyant": f"{leh:g}/{ters:g}/{ufuk}",
                                 "grup": ad, "yon": y, "n": int(m.sum()),
                                 "basari": int(np.nansum(v[m]))})
    return satirlar


_SERI: Dict[tuple, tuple] = {}


def _seri(sembol: str, tf: str):
    """(high, low, open, close, atr) — sembol/TF başına bir kez yüklenir."""
    anahtar = (sembol, tf)
    if anahtar in _SERI:
        return _SERI[anahtar]
    d = pd.read_csv(REPO / "backfill_data" / f"{sembol}_1h.csv.gz", compression="gzip",
                    parse_dates=["bar_time"]).set_index("bar_time")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    if tf != "1h":
        d = resample_ohlcv(d, tf)
    veri = (d["high"].to_numpy(float), d["low"].to_numpy(float),
            d["open"].to_numpy(float), d["close"].to_numpy(float),
            calculate_atr(d, 14).to_numpy(float))
    _SERI[anahtar] = veri
    return veri


def _ilk_vurus_tek(yuksek: np.ndarray, alcak: np.ndarray, bas: int, giris: float,
                   esik: float) -> int:
    """bas+1..bas+48 arasında eşiğin ilk vurulduğu bar (0 = vurulmadı)."""
    n = len(yuksek)
    for j in range(1, UFUK_MAX + 1):
        i = bas + j
        if i >= n:
            break
        if yuksek[i] - giris >= esik:
            return j
    return 0


def _ilk_vurus_asagi(yuksek: np.ndarray, alcak: np.ndarray, bas: int, giris: float,
                     esik: float) -> int:
    n = len(alcak)
    for j in range(1, UFUK_MAX + 1):
        i = bas + j
        if i >= n:
            break
        if giris - alcak[i] >= esik:
            return j
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Aşama 0 kontrol deneyi")
    ap.add_argument("--gozlem", default="var/replay/gozlemler.csv")
    ap.add_argument("--rapor", default="var/replay/kontrol.md")
    ap.add_argument("--giris", default="close", choices=["close", "next_open"])
    args = ap.parse_args(argv)
    global GIRIS
    GIRIS = args.giris

    goz = pd.read_csv(REPO / args.gozlem)
    goz = goz[goz.pencere_tam == 1]
    semboller = sorted(goz.sembol.unique())
    print(f"Kırılım gözlemi: {len(goz)} · sembol: {len(semboller)}")

    satirlar: List[Dict] = []
    for i, s in enumerate(semboller, 1):
        for tf in ("1h", "2h", "4h", "1d"):
            egim = endeks(tf)
            satirlar.extend(rastgele_ornek(s, tf, egim))
        if i % 10 == 0 or i == len(semboller):
            print(f"  {i}/{len(semboller)} sembol", flush=True)
    rnd = pd.DataFrame(satirlar)
    rnd.to_csv(REPO / "var/replay/rastgele.csv", index=False)

    # --- kırılım tarafını aynı varyantlarla etiketle
    g = ozellikler(goz.copy())
    g["tarih"] = pd.to_datetime(g["zaman"], utc=True, errors="coerce")
    kir = []
    for leh, ters, ufuk in VARYANTLAR:
        gg = g.copy()
        if GIRIS == "next_open":
            yeni_y = []
            for r in gg.itertuples():
                try:
                    high_, low_, open_, close_, atr_ = _seri(r.sembol, r.tf)
                except Exception:
                    yeni_y.append(np.nan)
                    continue
                b = int(r.bar)
                a = float(atr_[b]) if 0 <= b < len(atr_) else 0.0
                if b + 1 >= len(open_) or not np.isfinite(a) or a <= 0:
                    yeni_y.append(np.nan)
                    continue
                giris_f = float(open_[b + 1])
                if r.yon == 1:
                    tf_ = _ilk_vurus_tek(high_, low_, b + 1, giris_f, leh * a)
                    ta_ = _ilk_vurus_asagi(high_, low_, b + 1, giris_f, ters * a)
                else:
                    tf_ = _ilk_vurus_asagi(high_, low_, b + 1, giris_f, leh * a)
                    ta_ = _ilk_vurus_tek(high_, low_, b + 1, giris_f, ters * a)
                yeni_y.append(etiketle_np(np.array([tf_]), np.array([ta_]), ufuk)[0])
            gg["y"] = yeni_y
        else:
            gg["y"] = etiketle(gg, leh, ters, ufuk)
        gg = gg[gg.y.notna()]
        _eg = endeks("1h")
        idx_ns = pd.to_datetime(_eg.index, utc=True).astype("int64").to_numpy()
        obs = pd.to_datetime(gg["tarih"], utc=True).astype("int64").to_numpy()
        k = np.searchsorted(idx_ns, obs, side="right") - 1
        ok = (k >= 0) & (k < len(idx_ns))
        eg = np.full(len(gg), np.nan)
        eg[ok] = _eg.to_numpy()[k[ok]]
        gg["uyum"] = np.sign(gg.yon.to_numpy()) == np.sign(eg)
        for ad, m in (("uyumlu", gg.uyum), ("uyumsuz", ~gg.uyum)):
            sub = gg[m]
            for (sembol, tf, yon), ss in sub.groupby(["sembol", "tf", "yon"]):
                kir.append({"sembol": sembol, "tf": tf, "yon": int(yon),
                            "varyant": f"{leh:g}/{ters:g}/{ufuk}", "grup": ad,
                            "n": len(ss), "basari": int(np.nansum(ss.y))})
    kir_df = pd.DataFrame(kir)

    # --- karşılaştırma (yön eşleştirmeli) ---
    def oranlar(df_, grup):
        d_ = df_[df_.grup == grup]
        return d_.groupby(["varyant", "yon"]).agg(n=("n", "sum"), b=("basari", "sum"))

    k_or = oranlar(kir_df, "uyumlu")
    r_or = oranlar(rnd, "uyumlu")
    k_te = oranlar(kir_df, "uyumsuz")
    r_te = oranlar(rnd, "uyumsuz")

    def fark_hesap(a, b, varyant):
        """Yön ağırlıklı fark (puan) — kırılım tarafının yön ağırlıklarıyla."""
        try:
            ka = a.loc[varyant]
            kb = b.loc[varyant]
        except KeyError:
            return float("nan")
        toplam_n = 0.0
        toplam = 0.0
        for y in ka.index:
            if y not in kb.index:
                continue
            na, pa = float(ka.loc[y, "n"]), float(ka.loc[y, "b"]) / max(1.0, float(ka.loc[y, "n"]))
            nb, pb = float(kb.loc[y, "n"]), float(kb.loc[y, "b"]) / max(1.0, float(kb.loc[y, "n"]))
            if na <= 0 or nb <= 0:
                continue
            toplam += na * (pa - pb)
            toplam_n += na
        return 100.0 * toplam / toplam_n if toplam_n else float("nan")

    out = ["# Aşama 0 · Kontrol deneyi\n",
           f"Kırılım gözlemi {len(goz)} · rastgele giriş {int(rnd.n.sum()):,}\n",
           "Yön eşleştirmeli: aynı yöndeki kırılım ile rastgele giriş kıyaslanır; "
           "piyasanın sürüklenmesi farkı şişirmez.\n",
           "| etiket | kırılım uyumlu | rastgele uyumlu | fark | kırılım uyumsuz | rastgele uyumsuz | fark |",
           "|---|---|---|---|---|---|---|"]
    ana_fark = None
    for leh, ters, ufuk in VARYANTLAR:
        v = f"{leh:g}/{ters:g}/{ufuk}"
        fu = fark_hesap(k_or, r_or, v)
        ft = fark_hesap(k_te, r_te, v)
        pu = (k_or.loc[v].b.sum() / max(1.0, k_or.loc[v].n.sum()))
        ru = (r_or.loc[v].b.sum() / max(1.0, r_or.loc[v].n.sum()))
        pt = (k_te.loc[v].b.sum() / max(1.0, k_te.loc[v].n.sum()))
        rt = (r_te.loc[v].b.sum() / max(1.0, r_te.loc[v].n.sum()))
        out.append(f"| {v} | %{pu*100:.1f} | %{ru*100:.1f} | **{fu:+.1f}** | "
                   f"%{pt*100:.1f} | %{rt*100:.1f} | {ft:+.1f} |")
        if (leh, ters, ufuk) == ANA:
            ana_fark = fu

    # --- ana etiket: yön ve TF kırılımı
    v_ana = f"{ANA[0]:g}/{ANA[1]:g}/{ANA[2]}"
    out.append("\n## Ana etiket (2/1/24) · yön kırılımı\n")
    out.append("| yön | kırılım uyumlu | rastgele uyumlu | fark |")
    out.append("|---|---|---|---|")
    for y, ad in ((1, "long"), (-1, "short")):
        ka, kb = k_or.loc[(v_ana, y)], r_or.loc[(v_ana, y)]
        pa = ka.b / ka.n
        pb = kb.b / kb.n
        out.append(f"| {ad} | %{pa*100:.1f} (n={int(ka.n)}) | %{pb*100:.1f} "
                   f"(n={int(kb.n):,}) | **{(pa-pb)*100:+.1f}** |")

    out.append("\n## Ana etiket · TF kırılımı (yön eşleştirmeli)\n")
    out.append("| TF | kırılım uyumlu | rastgele uyumlu | fark |")
    out.append("|---|---|---|---|")
    for tf in ("1h", "2h", "4h", "1d"):
        kk = kir_df[(kir_df.varyant == v_ana) & (kir_df.grup == "uyumlu") & (kir_df.tf == tf)]
        rr = rnd[(rnd.varyant == v_ana) & (rnd.grup == "uyumlu") & (rnd.tf == tf)]
        if kk.n.sum() == 0 or rr.n.sum() == 0:
            continue
        toplam_n = toplam = 0.0
        for y in (1, -1):
            a = kk[kk.yon == y]
            b_ = rr[rr.yon == y]
            if a.n.sum() == 0 or b_.n.sum() == 0:
                continue
            pa = a.basari.sum() / a.n.sum()
            pb = b_.basari.sum() / b_.n.sum()
            toplam += a.n.sum() * (pa - pb)
            toplam_n += a.n.sum()
        pa_all = kk.basari.sum() / kk.n.sum()
        pb_all = rr.basari.sum() / rr.n.sum()
        out.append(f"| {tf} | %{pa_all*100:.1f} (n={int(kk.n.sum())}) | %{pb_all*100:.1f} "
                   f"(n={int(rr.n.sum()):,}) | {(toplam/toplam_n)*100:+.1f} |")

    # --- ana etiket: sembol bazlı eşleştirilmiş bootstrap
    out.append("\n## Ana etiket · sembol bazlı bootstrap (yön eşleştirmeli)\n")
    ozet = []
    for sembol in sorted(set(kir_df.sembol) & set(rnd.sembol)):
        kk = kir_df[(kir_df.sembol == sembol) & (kir_df.varyant == v_ana) & (kir_df.grup == "uyumlu")]
        rr = rnd[(rnd.sembol == sembol) & (rnd.varyant == v_ana) & (rnd.grup == "uyumlu")]
        toplam_n = toplam = 0.0
        for y in (1, -1):
            a = kk[kk.yon == y]
            b_ = rr[rr.yon == y]
            if a.n.sum() == 0 or b_.n.sum() == 0:
                continue
            toplam += a.n.sum() * (a.basari.sum()/a.n.sum() - b_.basari.sum()/b_.n.sum())
            toplam_n += a.n.sum()
        if toplam_n:
            ozet.append((sembol, toplam / toplam_n * 100, toplam_n))
    if ozet:
        sz = np.array([o[1] for o in ozet])
        ag = np.array([o[2] for o in ozet], dtype=float)
        rng = np.random.default_rng(7)
        bs = []
        for _ in range(1000):
            sec = rng.integers(0, len(sz), len(sz))
            bs.append(float(np.average(sz[sec], weights=ag[sec])))
        lo, hi = np.percentile(bs, [2.5, 97.5])
        ort = float(np.average(sz, weights=ag))
        out.append(f"- Sembol sayısı: {len(ozet)} · ağırlıklı fark: **{ort:+.1f} puan** · "
                   f"%95 GA [{lo:+.1f}, {hi:+.1f}]")
        karar = "GEÇTİ" if (ort >= 3.0 and lo > 0) else "KALDI"
        out.append(f"- Ön kayıt barı (≥ +3,0 puan ve GA alt sınırı > 0): **{karar}**")

    metin = "\n".join(out)
    print(metin)
    (REPO / args.rapor).write_text(metin, encoding="utf-8")
    print(f"\nRapor: {REPO / args.rapor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
