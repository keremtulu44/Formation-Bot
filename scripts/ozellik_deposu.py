# -*- coding: utf-8 -*-
"""Özellik deposu: replay gözlemlerine bağlam özellikleri ekler.

Motor ÇALIŞTIRILMAZ (gözlemler `var/replay/gozlemler177.csv`'den gelir).
Özellikler `backfill_data/` OHLCV'sinden, gözlem anına hizalanarak hesaplanır.

Domainler:
  1. Trend / yapı      — çoklu zaman dilimi hizası, MA mesafesi, Donchian kırılımı,
                         market structure (HH/HL) yönü
  2. Hacim             — kırılım hacmi / 20 bar ortalama, formasyon içi hacim kuruması,
                         hacim trendi (önceki çalışmada "hacim ters çalışır" notu var)
  3. Volatilite        — ATR yüzdelik dilimi (sembolün kendi geçmişinde), sıkışma
  4. Piyasa / genişlik — endeks trendi, endeks volatilitesi, piyasa genişliği (breadth),
                         enine dağılım (dispersion)
  5. Konum / çapa      — 52 haftalık zirveye uzaklık, aralık içi konum
  6. Momentum / dönüş  — kırılım öncesi koşu (ATR cinsinden), aşırılık
  7. Mikroyapı vekili  — gap, gövde içi kapanış konumu, gün içi aralık
  8. Kesitsel          — endekse beta, korelasyon, göreli güç
  9. Olay bağlamı      — retest, kırılımdan bu yana geçen süre, son başarısızlıklar
 10. Takvim            — ay, haftanın günü, tatil yakınlığı

Kullanım:
    python scripts/ozellik_deposu.py --girdi var/replay/gozlemler177.csv \
        --cikti var/replay/ozellikler177.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from data import resample_ohlcv  # noqa: E402
from patterns.indicators import calculate_atr  # noqa: E402

TFLER = ("1h", "2h", "4h", "1d")


# --------------------------------------------------------------------------- #
# yardımcılar
# --------------------------------------------------------------------------- #

def _ns(idx) -> np.ndarray:
    return pd.to_datetime(idx, utc=True).astype("int64").to_numpy()


def _gunluk(s: pd.Series) -> pd.Series:
    """Günlük seriyi gün başına normalize et (00:00 / 07:00 damga farkını sil)."""
    kopya = s.copy()
    kopya.index = pd.to_datetime(kopya.index, utc=True).tz_convert("Europe/Istanbul").normalize()
    kopya = kopya[~kopya.index.duplicated(keep="last")].sort_index()
    return kopya


def _oku(sembol: str, tf: str) -> Optional[pd.DataFrame]:
    p = REPO / "backfill_data" / f"{sembol}_{tf}.csv.gz"
    if not p.exists():
        return None
    d = pd.read_csv(p, compression="gzip", parse_dates=["bar_time"]).set_index("bar_time")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    if tf not in ("1h", "1d"):
        d = resample_ohlcv(d, tf)
    return d


def engel_mesafe(d: pd.DataFrame, atr: pd.Series, pencere: int = 5) -> pd.Series:
    """Fiyatın üstündeki en yakın pivot dirence uzaklık (ATR). Yoksa 30 (tavan)."""
    h = d["high"].to_numpy(float)
    c = d["close"].to_numpy(float)
    a = atr.to_numpy(float)
    n = len(h)
    cikti = np.full(n, np.nan)
    pivotlar: List[Tuple[int, float]] = []
    for i in range(n):
        j = i - pencere
        if j - pencere >= 0:
            sol = h[j - pencere:j]
            sag = h[j + 1:i] if i > j + 1 else np.array([])
            if len(sol) and len(sag) and h[j] >= sol.max() and h[j] >= sag.max():
                pivotlar.append((j, h[j]))
        if not np.isfinite(a[i]) or a[i] <= 0:
            continue
        ust = [f for (_k, f) in pivotlar if f > c[i]]
        cikti[i] = ((min(ust) - c[i]) / a[i]) if ust else 30.0
    return pd.Series(cikti, index=d.index)


def yapi_netligi(d: pd.DataFrame, pencere: int = 10) -> pd.Series:
    """Son 3 salınımın yönü: +1 yükselen dipler, -1 alçalan tepeler."""
    h = d["high"]
    l = d["low"]
    tepe_yon = np.sign(h.rolling(pencere, min_periods=3).max()
                       - h.rolling(pencere, min_periods=3).max().shift(pencere))
    dip_yon = np.sign(l.rolling(pencere, min_periods=3).min()
                      - l.rolling(pencere, min_periods=3).min().shift(pencere))
    return (tepe_yon + dip_yon) / 2.0


def _saat_medyan(hacim: pd.Series, pencere: int = 20) -> pd.Series:
    """Aynı saatteki (seans saati) son `pencere` gözlemin medyan hacmi."""
    idx = hacim.index
    saat = pd.Series(idx.hour, index=idx)
    med = hacim.groupby(saat).transform(
        lambda x: x.rolling(pencere, min_periods=5).median())
    return med.replace(0, np.nan)


def _ma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=max(3, n // 3)).mean()


# --------------------------------------------------------------------------- #
# piyasa genişliği (breadth) — tüm sembollerin günlük kapanışlarından
# --------------------------------------------------------------------------- #

def piyasa_serileri() -> pd.DataFrame:
    """Günlük breadth ve dispersion serisi (tüm semboller)."""
    kapanislar: Dict[str, pd.Series] = {}
    for p in sorted((REPO / "backfill_data").glob("*_1d.csv.gz")):
        sembol = p.name.rsplit("_", 1)[0]
        if sembol.startswith("XU"):
            continue
        d = pd.read_csv(p, compression="gzip", usecols=["bar_time", "close"],
                        parse_dates=["bar_time"]).set_index("bar_time")
        d = d[~d.index.duplicated(keep="last")].sort_index()
        if len(d) < 60:
            continue
        kapanislar[sembol] = _gunluk(d["close"])
    if not kapanislar:
        return pd.DataFrame()
    mat = pd.DataFrame(kapanislar).sort_index()
    ma20 = mat.rolling(20, min_periods=10).mean()
    ustunde = (mat > ma20).where(ma20.notna())
    breadth = ustunde.mean(axis=1)
    getiri = mat.pct_change()
    dispersion = getiri.std(axis=1)
    return pd.DataFrame({"breadth": breadth, "dispersion": dispersion}).dropna(how="all")


# --------------------------------------------------------------------------- #
# sembol özellikleri
# --------------------------------------------------------------------------- #

def sembol_ozellikleri(sembol: str) -> Optional[Dict[str, pd.DataFrame]]:
    """Sembol için TF bazında özellik tabloları."""
    d1d = _oku(sembol, "1d")
    if d1d is None or len(d1d) < 60:
        return None
    kapanis = d1d["close"]
    atr_d = calculate_atr(d1d, 14)
    oz: Dict[str, pd.DataFrame] = {}

    # --- günlük: trend, yapı, konum
    ma20d = _ma(kapanis, 20)
    ma50d = _ma(kapanis, 50)
    ma200d = _ma(kapanis, 200)
    zirve252 = kapanis.rolling(252, min_periods=60).max()
    dip252 = kapanis.rolling(252, min_periods=60).min()
    hh = d1d["high"].rolling(10, min_periods=3).max()
    ll = d1d["low"].rolling(10, min_periods=3).min()
    yapi = np.sign(hh - hh.shift(10)) + np.sign(ll - ll.shift(10))  # +2: yukarı yapı
    gun_oz = pd.DataFrame({
        "d_ust_ma20": (kapanis / ma20d - 1.0),
        "d_ust_ma50": (kapanis / ma50d - 1.0),
        "d_ust_ma200": (kapanis / ma200d - 1.0),
        "d_zirve_mesafe": (zirve252 - kapanis) / atr_d.replace(0, np.nan),
        "d_dip_mesafe": (kapanis - dip252) / atr_d.replace(0, np.nan),
        "d_ret20": kapanis.pct_change(20),
        "d_ret60": kapanis.pct_change(60),
        "d_yapi": yapi,
        "d_atr_yuzde": atr_d / kapanis * 100.0,
        "d_atr_yuzdelik": atr_d.rolling(120, min_periods=40).rank(pct=True),
        "d_donchian20": (kapanis >= d1d["high"].rolling(20, min_periods=10).max().shift(1)).astype(float),
        "d_donchian55": (kapanis >= d1d["high"].rolling(55, min_periods=20).max().shift(1)).astype(float),
        "d_engel_atr": engel_mesafe(d1d, atr_d),
        "d_sikisma": _ma(atr_d, 10) / _ma(atr_d, 60).replace(0, np.nan),
        "d_yapi_net": yapi_netligi(d1d),
    })
    oz["1d"] = gun_oz

    # --- saatlik türevler
    d1h = _oku(sembol, "1h")
    if d1h is not None and len(d1h) > 100:
        k = d1h["close"]
        atr_h = calculate_atr(d1h, 14)
        ma20h = _ma(k, 20)
        ma50h = _ma(k, 50)
        hacim = d1h["volume"].astype(float)
        hacim_ma = hacim.rolling(20, min_periods=5).mean()
        konum = (k - d1h["low"]) / (d1h["high"] - d1h["low"]).replace(0, np.nan)
        saat_oz = pd.DataFrame({
            "h_ust_ma20": k / ma20h - 1.0,
            "h_ust_ma50": k / ma50h - 1.0,
            "h_ret20": k.pct_change(20),
            "h_ret60": k.pct_change(60),
            "h_hacim_20": hacim / hacim_ma.replace(0, np.nan),
            "h_hacim_trend": hacim.rolling(10, min_periods=4).mean()
                              / hacim.rolling(40, min_periods=10).mean().replace(0, np.nan),
            "h_hacim_kuruma": hacim.rolling(20, min_periods=5).mean()
                              / hacim.rolling(60, min_periods=10).mean().replace(0, np.nan),
            "h_gap_atr": (d1h["open"] - k.shift(1)) / atr_h.replace(0, np.nan),
            "h_govde_konum": konum,
            "h_aralik_atr": (d1h["high"] - d1h["low"]) / atr_h.replace(0, np.nan),
            "h_atr_yuzdelik": atr_h.rolling(240, min_periods=60).rank(pct=True),
            "h_donchian20": (k >= d1h["high"].rolling(20, min_periods=10).max().shift(1)).astype(float),
            "h_donchian55": (k >= d1h["high"].rolling(55, min_periods=20).max().shift(1)).astype(float),
            "h_atr": atr_h,
            "h_atr_sikisma": _ma(atr_h, 10) / _ma(atr_h, 60).replace(0, np.nan),
            "h_hacim_saat": hacim / _saat_medyan(hacim),
        })
        # kırılım öncesi koşu: son 10 barın toplam hareketi / ATR
        saat_oz["h_kosu_atr"] = (k - k.shift(10)) / atr_h.replace(0, np.nan)
        oz["1h"] = saat_oz
        # 2h/4h trendleri saatlikten türetilir
        for tf in ("2h", "4h"):
            dd = resample_ohlcv(d1h, tf)
            kk = dd["close"]
            at = calculate_atr(dd, 14)
            oz[tf] = pd.DataFrame({f"{tf}_ust_ma20": kk / _ma(kk, 20) - 1.0,
                                   f"{tf}_ret20": kk.pct_change(20),
                                   f"{tf}_bos20": (kk >= dd["high"].rolling(20, min_periods=10)
                                                   .max().shift(1)).astype(float),
                                   f"{tf}_sikisma": _ma(at, 10) / _ma(at, 60).replace(0, np.nan)})
        # gözlem TF'sine göre "aynı TF yapı kırılımı" (aşağıda satır bazında seçilir)
    return oz


# --------------------------------------------------------------------------- #
# endeks ve kesitsel
# --------------------------------------------------------------------------- #

def endeks_ozellikleri() -> pd.DataFrame:
    d = _oku("XU100", "1d").copy()
    d.index = pd.to_datetime(d.index, utc=True).tz_convert("Europe/Istanbul").normalize()
    d = d[~d.index.duplicated(keep="last")].sort_index()
    k = d["close"]
    atr = calculate_atr(d, 14)
    return pd.DataFrame({
        "x_ust_ma50": k / _ma(k, 50) - 1.0,
        "x_ust_ma200": k / _ma(k, 200) - 1.0,
        "x_ret20": k.pct_change(20),
        "x_ret60": k.pct_change(60),
        "x_atr_yuzdelik": atr.rolling(120, min_periods=40).rank(pct=True),
    })


def endeks_gun_ici() -> pd.DataFrame:
    """XU100 için gün içi getiri (kapanış / günün açılışı - 1)."""
    d = _oku("XU100", "1h")
    k = d["close"]
    gun = pd.Series(d.index.date, index=d.index)
    acilis = d["open"].groupby(gun).transform("first")
    return pd.DataFrame({"x_gun_ici": (k / acilis - 1.0)})


def akran_momentumu(semboller: List[str], kume: int = 10) -> pd.DataFrame:
    """Korelasyonla akran grubu kurar (farthest-point medoid, tüm semboller kapsanır).

    scipy yok: k medoid en uzak nokta seçimiyle belirlenir, her sembol en yüksek
    korelasyonlu medoide atanır. Akran momentumu = grubun (kendisi hariç)
    son 5 günlük ortalama getirisi.
    """
    kapanis: Dict[str, pd.Series] = {}
    for s in semboller:
        d = _oku(s, "1d")
        if d is not None and len(d) > 120:
            kapanis[s] = _gunluk(d["close"])
    if len(kapanis) < 20:
        return pd.DataFrame()
    mat = pd.DataFrame(kapanis).sort_index()
    getiri = mat.pct_change(fill_method=None)
    kor = getiri.tail(120).corr().fillna(0.0)
    adlar = list(kor.columns)

    # --- farthest-point medoid seçimi
    ort = kor.mean(axis=1)
    medoidler = [ort.idxmax()]
    while len(medoidler) < min(kume, len(adlar)):
        mesafe = kor.loc[adlar, medoidler].max(axis=1)
        aday = mesafe.idxmin()
        if aday in medoidler:
            break
        medoidler.append(aday)

    # --- atama
    atama = {}
    for a in adlar:
        en_iyi = max(medoidler, key=lambda m_: kor.loc[a, m_])
        atama[a] = en_iyi
    gruplar: Dict[str, List[str]] = {}
    for a, m_ in atama.items():
        gruplar.setdefault(m_, []).append(a)

    peer = {}
    for m_, uyeler in gruplar.items():
        if len(uyeler) < 3:
            continue
        toplam = getiri[uyeler].sum(axis=1)
        n = len(uyeler)
        for u in uyeler:
            peer[u] = (toplam - getiri[u]) / (n - 1)
    if not peer:
        return pd.DataFrame()
    mom5 = pd.DataFrame(peer).rolling(5, min_periods=3).sum()
    return mom5


def beta_korelasyon(sembol: str, pencere: int = 60) -> Optional[pd.DataFrame]:
    s = _oku(sembol, "1d")
    x = _oku("XU100", "1d")
    if s is None or x is None:
        return None
    ortak = pd.concat([_gunluk(s["close"]).pct_change(),
                       _gunluk(x["close"]).pct_change()], axis=1, join="inner").dropna()
    if len(ortak) < pencere:
        return None
    ortak.columns = ["s", "x"]
    beta = ortak["s"].rolling(pencere).cov(ortak["x"]) / ortak["x"].rolling(pencere).var()
    kore = ortak["s"].rolling(pencere).corr(ortak["x"])
    return pd.DataFrame({"beta60": beta, "kore60": kore})


# --------------------------------------------------------------------------- #
# ana akış
# --------------------------------------------------------------------------- #

def hizala(df: pd.DataFrame, zaman: pd.Series, onek: str = "") -> pd.DataFrame:
    """Seriyi gözlem zamanlarına (geriye dönük) hizalar."""
    if df is None or len(df) == 0:
        return pd.DataFrame(index=zaman.index)
    idx = _ns(df.index)
    obs = pd.to_datetime(zaman, utc=True, errors="coerce").astype("int64").to_numpy()
    konum = np.searchsorted(idx, obs, side="right") - 1
    gecerli = (konum >= 0) & (konum < len(df))
    cikti = pd.DataFrame(index=zaman.index)
    deger = df.to_numpy(dtype=float)
    for j, kolon in enumerate(df.columns):
        s = np.full(len(zaman), np.nan)
        s[gecerli] = deger[konum[gecerli], j]
        cikti[f"{onek}{kolon}"] = s
    return cikti


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Bağlam özellikleri")
    ap.add_argument("--girdi", default="var/replay/gozlemler177.csv")
    ap.add_argument("--cikti", default="var/replay/ozellikler177.csv")
    args = ap.parse_args(argv)

    d = pd.read_csv(REPO / args.girdi, low_memory=False)
    d = d[d.pencere_tam == 1].copy()
    d["tarih"] = pd.to_datetime(d["zaman"], utc=True, errors="coerce")
    d = d[d.tarih.notna()].copy()

    print(f"gözlem {len(d)} · sembol {d.sembol.nunique()}")

    # --- piyasa genişliği
    print("piyasa serisi (breadth/dispersion) hesaplanıyor...")
    piyasa = piyasa_serileri()
    print(f"  {len(piyasa)} gün · breadth ortanca %{piyasa.breadth.median()*100:.0f}")
    endeks = endeks_ozellikleri()

    endeks_gi = endeks_gun_ici()
    akran = akran_momentumu(sorted(d.sembol.unique()))
    print(f"akran gruplaması: {akran.shape[1] if len(akran) else 0} sembol")

    parcalar = []
    semboller = sorted(d.sembol.unique())
    for i, sembol in enumerate(semboller, 1):
        alt = d[d.sembol == sembol]
        oz = sembol_ozellikleri(sembol)
        if oz is None:
            parcalar.append(alt)
            continue
        ek = [alt.reset_index(drop=True)]
        zaman = alt.reset_index(drop=True)["tarih"]
        # günlük her TF için
        gun = hizala(oz["1d"], zaman)
        # saatlik (1h) her TF için; 2h/4h'in kendi serisi varsa o
        saat = hizala(oz.get("1h"), zaman)
        satir = pd.concat([alt.reset_index(drop=True), gun, saat], axis=1)
        for tf in ("2h", "4h"):
            if tf in oz:
                satir = pd.concat([satir, hizala(oz[tf], zaman)], axis=1)
        satir = pd.concat([satir, hizala(endeks, zaman, "e_")], axis=1)
        satir = pd.concat([satir, hizala(piyasa, zaman, "p_")], axis=1)
        satir = pd.concat([satir, hizala(beta_korelasyon(sembol), zaman)], axis=1)
        satir = pd.concat([satir, hizala(endeks_gi, zaman, "e_")], axis=1)
        if len(akran) and sembol in akran.columns:
            satir = pd.concat([satir, hizala(akran[[sembol]].rename(
                columns={sembol: "akran_mom5"}), zaman)], axis=1)
        parcalar.append(satir)
        if i % 20 == 0 or i == len(semboller):
            print(f"  {i}/{len(semboller)} sembol", flush=True)

    out = pd.concat(parcalar, ignore_index=True).sort_values(["sembol", "tf", "bar"])

    # --- türetilmiş bileşikler
    yon = np.sign(out.yon)
    for ad, kolon in (("mtf", None),):
        pass
    out["mtf_uyum"] = (
        (np.sign(out.h_ust_ma20) == yon).astype(float)
        + (np.sign(out.get("2h_ust_ma20", np.nan)) == yon).astype(float)
        + (np.sign(out.get("4h_ust_ma20", np.nan)) == yon).astype(float)
        + (np.sign(out.d_ust_ma50) == yon).astype(float)
    )
    out["yapi_uyum"] = np.where(np.sign(out.d_yapi) == yon, 1.0,
                                np.where(out.d_yapi == 0, 0.0, -1.0))
    out["zirve_uyum"] = (out.d_zirve_mesafe <= 3).astype(float)   # zirveye 3 ATR'den yakın
    out["endeks_uyum"] = (np.sign(out.endeks_egim) == yon).astype(float)
    out["likidite_tl"] = out.hacim_orani  # yer tutucu (gerçek likidite ayrıca eklenir)
    # gözlem TF'sinin kendi yapı kırılımı ve sıkışması
    out["tf_bos20"] = np.where(out.tf == "1h", out.get("h_donchian20"),
                        np.where(out.tf == "2h", out.get("2h_bos20"),
                         np.where(out.tf == "4h", out.get("4h_bos20"),
                                  out.get("d_donchian20"))))
    out["tf_sikisma"] = np.where(out.tf == "1h", out.h_atr_sikisma,
                         np.where(out.tf == "2h", out.get("2h_sikisma"),
                          np.where(out.tf == "4h", out.get("4h_sikisma"),
                                   out.get("d_sikisma"))))

    # formasyon içi hacim kuruması: gözlem anına kadar olan blok hacmi / öncesi
    out["hacim_formasyon"] = np.nan
    try:
        h1 = {}
        for sembol in out.sembol.unique():
            dd = _oku(sembol, "1h")
            if dd is None or len(dd) < 120:
                continue
            h1[sembol] = dd["volume"].astype(float).to_numpy()
        for i, r in enumerate(out.itertuples()):
            v = h1.get(r.sembol)
            if v is None or not np.isfinite(r.dogum_bar):
                continue
            b, dg = int(r.bar), int(r.dogum_bar)
            if b - dg < 10 or b >= len(v):
                continue
            blok = np.nanmean(v[max(0, dg):b])
            once = np.nanmean(v[max(0, dg - 60):max(1, dg)])
            if once and np.isfinite(once) and once > 0:
                out.iloc[i, out.columns.get_loc("hacim_formasyon")] = blok / once
    except Exception as e:
        print("  hacim_formasyon atlandı:", e)

    # takvim
    out["ay"] = out.tarih.dt.month.astype(float)
    out["gun_no"] = out.tarih.dt.dayofweek.astype(float)

    hedef = REPO / args.cikti
    out.to_csv(hedef, index=False)
    print(f"\nYazıldı: {hedef} · {out.shape[0]} satır × {out.shape[1]} kolon")
    print("dolu oranı düşük kolonlar:",
          {c: round(out[c].isna().mean() * 100) for c in out.columns
           if out[c].isna().mean() > 0.3})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
