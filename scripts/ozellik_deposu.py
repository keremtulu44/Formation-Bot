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


def _oku(sembol: str, tf: str) -> Optional[pd.DataFrame]:
    p = REPO / "backfill_data" / f"{sembol}_{tf}.csv.gz"
    if not p.exists():
        return None
    d = pd.read_csv(p, compression="gzip", parse_dates=["bar_time"]).set_index("bar_time")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    if tf not in ("1h", "1d"):
        d = resample_ohlcv(d, tf)
    return d


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
        kapanislar[sembol] = d["close"]
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
        })
        # kırılım öncesi koşu: son 10 barın toplam hareketi / ATR
        saat_oz["h_kosu_atr"] = (k - k.shift(10)) / atr_h.replace(0, np.nan)
        oz["1h"] = saat_oz
        # 2h/4h trendleri saatlikten türetilir
        for tf in ("2h", "4h"):
            dd = resample_ohlcv(d1h, tf)
            kk = dd["close"]
            oz[tf] = pd.DataFrame({f"{tf}_ust_ma20": kk / _ma(kk, 20) - 1.0,
                                   f"{tf}_ret20": kk.pct_change(20)})
    return oz


# --------------------------------------------------------------------------- #
# endeks ve kesitsel
# --------------------------------------------------------------------------- #

def endeks_ozellikleri() -> pd.DataFrame:
    d = _oku("XU100", "1d")
    k = d["close"]
    atr = calculate_atr(d, 14)
    return pd.DataFrame({
        "x_ust_ma50": k / _ma(k, 50) - 1.0,
        "x_ust_ma200": k / _ma(k, 200) - 1.0,
        "x_ret20": k.pct_change(20),
        "x_ret60": k.pct_change(60),
        "x_atr_yuzdelik": atr.rolling(120, min_periods=40).rank(pct=True),
    })


def beta_korelasyon(sembol: str, pencere: int = 60) -> Optional[pd.DataFrame]:
    s = _oku(sembol, "1d")
    x = _oku("XU100", "1d")
    if s is None or x is None:
        return None
    ortak = pd.concat([s["close"].pct_change(), x["close"].pct_change()], axis=1,
                      join="inner").dropna()
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
