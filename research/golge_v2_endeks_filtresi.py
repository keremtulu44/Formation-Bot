"""Gölge v2 endeks rejimi filtresi — "endeks uzun süredir düşüyorsa işlem yok" fikrinin ölçümü.

Sonuç anatomisi şunu gösterdi: işlem AÇIKKEN endeksin gittiği yön sonuçla güçlü biçimde
birlikte hareket ediyor, ama bu giriş anında bilinmiyor; girişten önceki 5 mumun endeks yönü
ise stop oranını ayırt etmiyor. Bu betik aynı soruyu "uzun süredir" için sorar: girişte
BİLİNEN daha uzun vadeli bir endeks rejimi, doğrudan stop olan işlemleri eleyebilir mi?

Yöntem
------
* Rejim yalnız `XU100` GÜNLÜK kapanışlarından ve yalnız işlemin giriş anından ÖNCE kapanmış
  günlerden hesaplanır (aynı günün kapanışı kullanılmaz). Yani giriş anında bilinir.
* Rejim tanımları ÖN-KAYITLIDIR (`REJIMLER`); sonuç görüldükten sonra tanım eklemek ölçümü
  geçersiz kılar. Hepsi raporlanır, yalnız en iyisi değil.
* Bir filtrenin değeri, elediği işlemlerin net R'sidir: elenen işlemler ortalamada zarar
  ediyorsa filtre kazandırır. `fayda = −(elenen işlemin net R'si)`, elenmeyenlerde 0.
* Kabul merdiveni `research/golge_v2_surec_olcum.py` ile aynıdır: iki dönemde de pozitif,
  iki dönemde de en az 30 elenen işlem ve dört küme tanımının en kötü alt sınırı sıfırın üstünde.
* Rejim bir ZAMAN değişkenidir: aynı gün açılan bütün işlemler aynı rejimi taşır ve bir
  "düşüş dönemi" haftalarca sürer. Bağımsız gözlem sayısı işlem sayısı değil, ayrı dönem
  sayısıdır; rapor bunu da verir.

İşlemler `research/golge_v2_sonuc_anatomisi.py` ile aynıdır (ana CSV, sansürsüz, karantina dışı,
`4h + 1d`, birincil); yarış yeniden koşulmaz.

Kullanım::

    python -m research.golge_v2_endeks_filtresi [--girdi D] [--cikti D] [--workers 2]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from domain_engines.market_structure import MarketStructureConfig, MarketStructureEngine
from domain_engines.stabil import prepare_causal_ohlcv
from research import golge_v2_sonuc_anatomisi as sa
from research.arsiv import tf_frame
from senaryo_v2.rapor import zaman_kumesi_saglamligi

ENDEKS: str = sa.ENDEKS
DUSUS, KARARSIZ, YUKSELIS = -1, 0, 1
MIN_N: int = 30
B_ARALIK: int = 600
NET = sa.NET

# Ön-kayıtlı rejim tanımları: ad -> açıklama (düşüş tarafı; yükseliş tarafı aynasıdır).
REJIMLER: dict[str, str] = {
    "getiri_10": "Endeks son 10 günde ekside",
    "getiri_20": "Endeks son 20 günde ekside",
    "getiri_60": "Endeks son 60 günde ekside",
    "sma_20": "Endeks 20 günlük ortalamasının altında",
    "sma_50": "Endeks 50 günlük ortalamasının altında",
    "trend_20": "Endeks 20 günlük ortalamanın altında VE ortalama düşüyor (aksi: kararsız)",
    "ms_dis": "Endeksin günlük dış piyasa yapısı ayı (Market Structure motoru)",
}
ANA_REJIM: str = "getiri_20"      # kısa özet ve kademeli tablo bu tanımı kullanır

# Ön-kayıtlı filtreler: ad -> (açıklama, eleme kuralı(yön dizisi, rejim dizisi)).
FILTRELER: dict[str, tuple[str, Any]] = {
    "LONG_DUSUSTE": ("Endeks düşüşteyken long yok", lambda yon, rj: (yon == "long") & (rj == DUSUS)),
    "SHORT_YUKSELISTE": ("Endeks yükselişteyken short yok", lambda yon, rj: (yon == "short") & (rj == YUKSELIS)),
    "KARSI": (
        "Endeks rejimine karşı işlem yok (ikisi birden)",
        lambda yon, rj: ((yon == "long") & (rj == DUSUS)) | ((yon == "short") & (rj == YUKSELIS)),
    ),
    "DUSUSTE_HIC": ("Endeks düşüşteyken hiç işlem yok (long + short)", lambda yon, rj: rj == DUSUS),
}
# Stop grupları ATR cinsindendir (hedef 2 ATR'dir; ATR, stop uzaklığından bağımsız bir fiyat ölçüsüdür).
ESIK_YARIM_ATR: float = 0.5       # stoptan önce bundan azını gördüyse "doğrudan / minnak artıp düşen"
ESIK_BIR_ATR: float = 1.0
KADEME_SINIR = (-np.inf, -5.0, 0.0, 5.0, np.inf)
KADEME_AD = ("%5'ten fazla ters", "%0–5 ters", "%0–5 lehte", "%5'ten fazla lehte")


# ---------------------------------------------------------------------------
# Rejim (saf)
# ---------------------------------------------------------------------------
def rejim_dizileri(kapanis: Any, ms_yon: Any | None = None) -> dict[str, np.ndarray]:
    """Her günlük bar için rejim kodu: −1 düşüş, +1 yükseliş, 0 kararsız, `nan` geçmiş yetersiz.

    `j` günündeki kod yalnız `kapanis[: j + 1]` kullanır (nedensel).
    """
    c = np.asarray(kapanis, dtype=float)
    n = len(c)

    def getiri(pencere: int) -> np.ndarray:
        out = np.full(n, np.nan)
        if n > pencere:
            out[pencere:] = np.sign(c[pencere:] / c[:-pencere] - 1.0)
        return out

    def ortalama(pencere: int) -> np.ndarray:
        out = np.full(n, np.nan)
        if n >= pencere:
            kumulatif = np.cumsum(np.insert(c, 0, 0.0))
            out[pencere - 1 :] = (kumulatif[pencere:] - kumulatif[:-pencere]) / pencere
        return out

    def konum(ort: np.ndarray) -> np.ndarray:
        return np.where(np.isnan(ort), np.nan, np.sign(c - ort))

    o20, o50 = ortalama(20), ortalama(50)
    egim = np.full(n, np.nan)
    if n > 5:
        egim[5:] = np.sign(o20[5:] - o20[:-5])
    trend = np.where(
        np.isnan(egim),
        np.nan,
        np.where((c < o20) & (egim < 0), float(DUSUS), np.where((c > o20) & (egim > 0), float(YUKSELIS), float(KARARSIZ))),
    )
    sonuc = {
        "getiri_10": getiri(10),
        "getiri_20": getiri(20),
        "getiri_60": getiri(60),
        "sma_20": konum(o20),
        "sma_50": konum(o50),
        "trend_20": trend,
    }
    if ms_yon is not None:
        sonuc["ms_dis"] = np.sign(np.asarray(ms_yon, dtype=float))
    return sonuc


def getiri_yuzde(kapanis: Any, pencere: int) -> np.ndarray:
    """`pencere` günlük ham getiri (%); geçmiş yetersizse `nan`."""
    c = np.asarray(kapanis, dtype=float)
    out = np.full(len(c), np.nan)
    if len(c) > pencere:
        out[pencere:] = (c[pencere:] / c[:-pencere] - 1.0) * 100.0
    return out


def epizot_kimlikleri(kod: Any) -> np.ndarray:
    """Ardışık aynı rejim kodlu günleri tek döneme toplar; `nan` günler de kendi dönemidir."""
    k = np.nan_to_num(np.asarray(kod, dtype=float), nan=-9.0)
    if len(k) == 0:
        return np.zeros(0, dtype=int)
    return np.concatenate(([0], np.cumsum(k[1:] != k[:-1]))).astype(int)


def asof_gun(kapanis_zamanlari_ns: Any, giris_ns: Any, *, ayni_an_dahil: bool = False) -> np.ndarray:
    """Giriş anından ÖNCE kapanmış son günlük barın indeksi (yoksa −1).

    Varsayılan katıdır: girişle AYNI anda kapanan gün sayılmaz (günlük işlemde giriş, endeksin
    o günkü kapanışıyla aynı andadır). `ayni_an_dahil=True` yalnız duyarlılık kontrolü içindir.
    """
    taraf = "right" if ayni_an_dahil else "left"
    return np.searchsorted(np.asarray(kapanis_zamanlari_ns), np.asarray(giris_ns), side=taraf) - 1


def stop_oncesi_mfe_atr(df: pd.DataFrame) -> pd.Series:
    """Stop olan işlemin stop mumundan ÖNCE gördüğü en iyi nokta (giriş ATR'si); stop değilse `nan`.

    Mum çözünürlüğünde alt sınırdır: stop mumunun içinde önce yükselip sonra düşen işlem burada
    görünmez. Kaynak, sonuç anatomisinin `hedef_yolu_orani` alanıdır (hedef = `HEDEF_ATR` ATR).
    """
    stop = df["cikis_turu"].isin(("STOP", "STOP_BOSLUK"))
    return (df["hedef_yolu_orani"].astype(float) * sa.HEDEF_ATR).where(stop)


def stop_gruplarini_ekle(df: pd.DataFrame) -> pd.DataFrame:
    """`stop_mfe_atr`, `dogrudan_stop` (< 0.5 ATR), `yarim_atr_stop` (>= 0.5), `bir_atr_stop` (>= 1.0)."""
    out = df.copy()
    mfe = stop_oncesi_mfe_atr(out)
    out["stop_mfe_atr"] = mfe
    out["dogrudan_stop"] = mfe < ESIK_YARIM_ATR
    out["yarim_atr_stop"] = mfe >= ESIK_YARIM_ATR
    out["bir_atr_stop"] = mfe >= ESIK_BIR_ATR
    return out


# ---------------------------------------------------------------------------
# Endeks serisi
# ---------------------------------------------------------------------------
def endeks_gunluk() -> dict[str, Any]:
    """`XU100` günlük: kapanış zamanı (UTC ns), kapanış ve Market Structure dış yönü."""
    ham = tf_frame(ENDEKS, "1d")
    temiz, hata = prepare_causal_ohlcv(ham, symbol=ENDEKS, timeframe="1d")
    if hata and temiz.empty:
        raise ValueError(f"{ENDEKS}/1d çerçeve hazırlanamadı: {hata}")
    motor = MarketStructureEngine(MarketStructureConfig(profile="Dengeli"))
    yon: list[int] = []
    for satir in temiz[["timestamp", "open", "high", "low", "close", "volume"]].to_dict("records"):
        motor.update(satir)
        yon.append(int(motor.external_context.direction))
    return {
        "kap": pd.DatetimeIndex(temiz["timestamp"]).asi8.copy(),
        "c": temiz["close"].to_numpy(dtype=float),
        "ms_yon": np.asarray(yon, dtype=float),
    }


def rejimleri_ekle(df: pd.DataFrame, endeks: dict[str, Any], *, ayni_an_dahil: bool = False) -> pd.DataFrame:
    """Her işleme giriş anında bilinen rejim kodlarını, dönem kimliklerini ve stop gruplarını ekler."""
    out = stop_gruplarini_ekle(df)
    giris_ns = pd.to_datetime(out["bar_close_time"], utc=True).astype("int64").to_numpy()
    j = asof_gun(endeks["kap"], giris_ns, ayni_an_dahil=ayni_an_dahil)
    diziler = rejim_dizileri(endeks["c"], endeks["ms_yon"])
    yon_int = np.where(out["yon"].to_numpy() == "long", 1.0, -1.0)
    var = j >= 0
    for ad in REJIMLER:
        kod = np.full(len(out), np.nan)
        kod[var] = diziler[ad][j[var]]
        epizot = np.full(len(out), -1, dtype=int)
        epizot[var] = epizot_kimlikleri(diziler[ad])[j[var]]
        out[f"rj_{ad}"] = kod
        out[f"iliski_{ad}"] = kod * yon_int          # +1 uyumlu, −1 karşı, 0 kararsız, nan bilinmiyor
        out[f"epizot_{ad}"] = epizot
    for pencere in (20, 60):
        ham = np.full(len(out), np.nan)
        ham[var] = getiri_yuzde(endeks["c"], pencere)[j[var]]
        out[f"endeks_getiri_{pencere}"] = ham
        out[f"endeks_getiri_{pencere}_yonlu"] = ham * yon_int
    return out


# ---------------------------------------------------------------------------
# Özet
# ---------------------------------------------------------------------------
def _grup_satiri(ad: str, g: pd.DataFrame) -> dict[str, Any]:
    oz = zaman_kumesi_saglamligi(g, NET, B=B_ARALIK) if len(g) else {"en_kotu_alt": None, "kumeler": {}}
    ustler = [v["ci95_ust"] for v in oz["kumeler"].values() if v["ci95_ust"] is not None]
    kesif, dogrulama = g[g["donem"] == "kesif"], g[g["donem"] == "dogrulama"]
    return {
        "grup": ad,
        "n": len(g),
        "stop_pay": sa._pay(len(sa._stoplar(g)), len(g)),
        "dogrudan_stop_pay": sa._pay(int(g["dogrudan_stop"].sum()), len(g)),
        "yarim_atr_stop_pay": sa._pay(int(g["yarim_atr_stop"].sum()), len(g)),
        "kar_pay": sa._pay(int(g["kar"].sum()), len(g)),
        "net_ort": sa._ort(g[NET]),
        "net_toplam": sa._top(g[NET]),
        "en_kotu_alt": oz["en_kotu_alt"],
        "en_kotu_ust": max(ustler) if ustler else None,
        "kesif_n": len(kesif),
        "kesif_net": sa._ort(kesif[NET]),
        "dogrulama_n": len(dogrulama),
        "dogrulama_net": sa._ort(dogrulama[NET]),
    }


def iliski_tablosu(k: pd.DataFrame, rejim: str) -> list[dict[str, Any]]:
    """Rejim işlemin yönüne göre: karşı / uyumlu / kararsız / bilinmiyor."""
    iliski = k[f"iliski_{rejim}"]
    return [
        _grup_satiri("KARSI", k[iliski == -1]),
        _grup_satiri("UYUMLU", k[iliski == 1]),
        _grup_satiri("KARARSIZ", k[iliski == 0]),
        _grup_satiri("BILINMIYOR", k[iliski.isna()]),
    ]


def yon_rejim_tablosu(k: pd.DataFrame, rejim: str) -> list[dict[str, Any]]:
    """Yön × ham rejim (düşüş / yükseliş): filtrelerin dört hücresi."""
    rj = k[f"rj_{rejim}"]
    return [
        _grup_satiri(f"{yon} / {'DUSUS' if kod == DUSUS else 'YUKSELIS'}", k[(k["yon"] == yon) & (rj == kod)])
        for yon in ("long", "short")
        for kod in (DUSUS, YUKSELIS)
    ]


def filtre_karari(tumu: dict[str, Any], kesif: dict[str, Any], dogrulama: dict[str, Any]) -> str:
    """`surec_olcum.varyant_ozeti` ile aynı merdiven; `fayda` = elenen işlemin −net R'si."""
    donem_ince = min(kesif["elenen_n"], dogrulama["elenen_n"]) < MIN_N
    if tumu["elenen_n"] < MIN_N or not kesif["n"] or not dogrulama["n"]:
        return "SAYILMAZ_N<30"
    if (tumu["fayda_en_kotu_ust"] if tumu["fayda_en_kotu_ust"] is not None else 1) < 0:
        return "ZARARLI"
    if kesif["fayda_ort"] <= 0 or dogrulama["fayda_ort"] <= 0:
        return "GECMEDI"
    if donem_ince:
        return "ZAYIF_ARTI"
    if (kesif["fayda_en_kotu_alt"] or -1) > 0 and (dogrulama["fayda_en_kotu_alt"] or -1) > 0:
        return "GECTI"
    if (tumu["fayda_en_kotu_alt"] or -1) > 0:
        return "UMUT_VAR"
    return "ZAYIF_ARTI"


def _fayda_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    """Kümenin BÜTÜN işlemleri üzerinden işlem başına fayda (elenmeyenlerde 0) ve en kötü aralığı."""
    if k.empty:
        return {"n": 0, "elenen_n": 0, "fayda_ort": 0.0, "fayda_toplam": 0.0, "fayda_en_kotu_alt": None, "fayda_en_kotu_ust": None}
    oz = zaman_kumesi_saglamligi(k, "fayda", B=B_ARALIK)
    ustler = [v["ci95_ust"] for v in oz["kumeler"].values() if v["ci95_ust"] is not None]
    return {
        "n": len(k),
        "elenen_n": int(k["elenen"].sum()),
        "fayda_ort": round(float(k["fayda"].mean()), 6),
        "fayda_toplam": round(float(k["fayda"].sum()), 2),
        "fayda_en_kotu_alt": oz["en_kotu_alt"],
        "fayda_en_kotu_ust": max(ustler) if ustler else None,
    }


def filtre_ozeti(k: pd.DataFrame, rejim: str, filtre: str) -> dict[str, Any]:
    """Bir (rejim tanımı, filtre) çiftinin elediği işlemler ve kabul kararı."""
    aciklama, kural = FILTRELER[filtre]
    maske = pd.Series(np.asarray(kural(k["yon"].to_numpy(), k[f"rj_{rejim}"].to_numpy()), dtype=bool), index=k.index)
    calisma = k.assign(elenen=maske, fayda=np.where(maske, -k[NET].to_numpy(), 0.0))
    elenen, kalan = calisma[maske], calisma[~maske]
    tumu = _fayda_ozeti(calisma)
    kesif = _fayda_ozeti(calisma[calisma["donem"] == "kesif"])
    dogrulama = _fayda_ozeti(calisma[calisma["donem"] == "dogrulama"])
    # Bağımsız gözlem: elenen işlemlerin düştüğü ayrı rejim dönemleri.
    donemler = elenen.groupby(f"epizot_{rejim}")[NET].agg(["size", "sum"]) if len(elenen) else pd.DataFrame(columns=["size", "sum"])
    return {
        "rejim": rejim,
        "filtre": filtre,
        "aciklama": aciklama,
        "karar": filtre_karari(tumu, kesif, dogrulama),
        "elenen": _grup_satiri("ELENEN", elenen),
        "kalan": _grup_satiri("KALAN", kalan),
        "fayda": {"tumu": tumu, "kesif": kesif, "dogrulama": dogrulama},
        "elenen_dogrudan_stop_n": int(elenen["dogrudan_stop"].sum()),
        "toplam_dogrudan_stop_n": int(k["dogrudan_stop"].sum()),
        "elenen_yarim_atr_stop_n": int(elenen["yarim_atr_stop"].sum()),
        "toplam_yarim_atr_stop_n": int(k["yarim_atr_stop"].sum()),
        "elenen_kazanan_n": int(elenen["kar"].sum()),
        "toplam_kazanan_n": int(k["kar"].sum()),
        "donem_n": int(len(donemler)),
        "zararda_donem_n": int((donemler["sum"] < 0).sum()) if len(donemler) else 0,
        "en_buyuk_donem_payi": sa._pay(int(donemler["size"].max()), len(elenen)) if len(donemler) else None,
    }


def kademe_tablosu(k: pd.DataFrame, pencere: int) -> list[dict[str, Any]]:
    """Girişten önceki `pencere` günlük endeks getirisi, işlemin yönüne göre kovalanmış.

    Her kademe önce bütün işlemler, sonra long ve short ayrı ayrı verilir: "long için ters"
    endeksin düştüğü, "short için ters" endeksin yükseldiği durumdur.
    """
    kova = pd.cut(k[f"endeks_getiri_{pencere}_yonlu"].astype(float), list(KADEME_SINIR), labels=list(KADEME_AD)).astype(object)
    satirlar: list[dict[str, Any]] = []
    for ad in KADEME_AD:
        satirlar.append(_grup_satiri(ad, k[kova == ad]))
        for yon in ("long", "short"):
            satirlar.append(_grup_satiri(f"{ad} — yalnız {yon}", k[(kova == ad) & (k["yon"] == yon)]))
    return satirlar + [_grup_satiri("BILINMIYOR", k[kova.isna()])]


def kume_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    return {
        "baz": _grup_satiri("TUMU", k),
        "rejimler": {
            ad: {
                "aciklama": REJIMLER[ad],
                "iliski": iliski_tablosu(k, ad),
                "yon_rejim": yon_rejim_tablosu(k, ad),
                "filtreler": [filtre_ozeti(k, ad, f) for f in FILTRELER],
            }
            for ad in REJIMLER
        },
        "kademe": {str(p): kademe_tablosu(k, p) for p in (20, 60)},
    }


def karar_sayimi(kumeler: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Küme başına karar etiketi dağılımı (bütün rejim × filtre varyantları)."""
    sayim: dict[str, dict[str, int]] = {}
    for kume, v in kumeler.items():
        s: dict[str, int] = {}
        for rv in v["rejimler"].values():
            for r in rv["filtreler"]:
                s[r["karar"]] = s.get(r["karar"], 0) + 1
        sayim[kume] = dict(sorted(s.items()))
    return sayim


def duyarlilik_ozeti(asil: dict[str, Any], diger: dict[str, Any]) -> dict[str, Any]:
    """Girişle aynı anda kapanan endeks günü de sayılsaydı kararlar nasıl değişirdi?"""
    degisen = 0
    for kume, v in asil.items():
        for ad, rv in v["rejimler"].items():
            for x, y in zip(rv["filtreler"], diger[kume]["rejimler"][ad]["filtreler"]):
                degisen += int(x["karar"] != y["karar"])
    sayim = karar_sayimi(diger)
    return {
        "degisen_karar_n": degisen,
        "karar_sayimi": sayim,
        "gecen_n": sum(s.get("GECTI", 0) + s.get("UMUT_VAR", 0) for s in sayim.values()),
    }


def ozet_uret(df: pd.DataFrame, endeks: dict[str, Any]) -> dict[str, Any]:
    diziler = rejim_dizileri(endeks["c"], endeks["ms_yon"])
    gunler: dict[str, Any] = {}
    for ad in REJIMLER:
        kod = diziler[ad]
        epizot = epizot_kimlikleri(kod)
        gunler[ad] = {
            "dusus_gun": int((kod == DUSUS).sum()),
            "yukselis_gun": int((kod == YUKSELIS).sum()),
            "kararsiz_gun": int((kod == KARARSIZ).sum()),
            "bilinmeyen_gun": int(np.isnan(kod).sum()),
            "dusus_donem": int(len(set(epizot[kod == DUSUS]))),
            "yukselis_donem": int(len(set(epizot[kod == YUKSELIS]))),
        }
    return {
        "meta": {
            "islem_n": int(len(df)),
            "endeks": ENDEKS,
            "endeks_gun_n": int(len(endeks["c"])),
            "endeks_ilk_gun": str(pd.Timestamp(int(endeks["kap"][0]), tz="UTC").tz_convert("Europe/Istanbul").date()),
            "endeks_son_gun": str(pd.Timestamp(int(endeks["kap"][-1]), tz="UTC").tz_convert("Europe/Istanbul").date()),
            "rejim_tanimlari": REJIMLER,
            "filtreler": {ad: aciklama for ad, (aciklama, _) in FILTRELER.items()},
            "ana_rejim": ANA_REJIM,
            "gunler": gunler,
            "min_n": MIN_N,
        },
        "kumeler": {ad: kume_ozeti(df[maske(df)]) for ad, maske in sa.KUMELER.items()},
    }


# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------
_f, _yz = sa._f, sa._yz
ILISKI_AD = {"KARSI": "Endeks işleme karşı", "UYUMLU": "Endeks işlemle aynı yönde", "KARARSIZ": "Kararsız", "BILINMIYOR": "Geçmiş yetersiz"}


def _aralik(r: dict[str, Any]) -> str:
    return f"[{_f(r['en_kotu_alt'])}, {_f(r['en_kotu_ust'])}]"


def _grup_md(satirlar: list[dict[str, Any]], baslik: str, adlar: dict[str, str] | None = None) -> list[str]:
    s = [
        f"| {baslik} | N | Stop | Doğrudan stop | 0.5 ATR görüp stop | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) |",
        "|---|---:|---:|---:|---:|---:|---:|---|---:|---:|",
    ]
    for r in satirlar:
        if not r["n"]:
            continue
        ad = (adlar or {}).get(r["grup"], r["grup"])
        s.append(
            f"| {ad} | {r['n']} | {_yz(r['stop_pay'])} | {_yz(r['dogrudan_stop_pay'])} | {_yz(r['yarim_atr_stop_pay'])} | {_yz(r['kar_pay'])} | "
            f"{_f(r['net_ort'])} | {_aralik(r)} | {_f(r['kesif_net'])} ({r['kesif_n']}) | {_f(r['dogrulama_net'])} ({r['dogrulama_n']}) |"
        )
    return s


def _filtre_md(v: dict[str, Any], filtre: str) -> list[str]:
    s = [
        "| Rejim tanımı | Elenen | Elenenin net R | Keşif (n) | Doğrulama (n) | Toplam fayda R | Fayda en kötü GA (R/işlem) | Kalan: N / net R | "
        "Elenen doğrudan stop | Elenen kazanan | Ayrı dönem (zararda) | Karar |",
        "|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    for ad, rv in v["rejimler"].items():
        r = next(x for x in rv["filtreler"] if x["filtre"] == filtre)
        e, k, fy = r["elenen"], r["kalan"], r["fayda"]["tumu"]
        s.append(
            f"| `{ad}` | {e['n']} | {_f(e['net_ort'])} | {_f(e['kesif_net'])} ({e['kesif_n']}) | {_f(e['dogrulama_net'])} ({e['dogrulama_n']}) | "
            f"{_f(fy['fayda_toplam'], 1)} | [{_f(fy['fayda_en_kotu_alt'])}, {_f(fy['fayda_en_kotu_ust'])}] | {k['n']} / {_f(k['net_ort'])} | "
            f"{r['elenen_dogrudan_stop_n']} / {r['toplam_dogrudan_stop_n']} | {r['elenen_kazanan_n']} / {r['toplam_kazanan_n']} | "
            f"{r['donem_n']} ({r['zararda_donem_n']}) | **{r['karar']}** |"
        )
    return s


def _kisa_ozet_md(ozet: dict[str, Any]) -> list[str]:
    m = ozet["meta"]
    ilk = next(iter(ozet["kumeler"]))
    v = ozet["kumeler"][ilk]
    ana = v["rejimler"][m["ana_rejim"]]
    il = {r["grup"]: r for r in ana["iliski"]}
    sayim = karar_sayimi(ozet["kumeler"])
    n_varyant = len(REJIMLER) * len(FILTRELER)
    gecen = {k: s.get("GECTI", 0) + s.get("UMUT_VAR", 0) for k, s in sayim.items()}
    s = [
        f"- **Soru:** girişte bilinen uzun vadeli endeks rejimi, doğrudan stop olanları ayırıyor mu? Ana tanım `{m['ana_rejim']}` "
        f"({REJIMLER[m['ana_rejim']].lower()}).",
        f"- **{sa.KUME_KISA[ilk]}, endeks işleme karşıyken:** `{il['KARSI']['n']}` işlem; stop `{_yz(il['KARSI']['stop_pay'])}`, doğrudan stop "
        f"`{_yz(il['KARSI']['dogrudan_stop_pay'])}`, net `{_f(il['KARSI']['net_ort'])} R` {_aralik(il['KARSI'])}.",
        f"- **{sa.KUME_KISA[ilk]}, endeks işlemle aynı yöndeyken:** `{il['UYUMLU']['n']}` işlem; stop `{_yz(il['UYUMLU']['stop_pay'])}`, doğrudan stop "
        f"`{_yz(il['UYUMLU']['dogrudan_stop_pay'])}`, net `{_f(il['UYUMLU']['net_ort'])} R` {_aralik(il['UYUMLU'])}.",
        f"- **Filtre kararları** (`{len(REJIMLER)}` rejim tanımı × `{len(FILTRELER)}` filtre = `{n_varyant}` varyant; `GECTI` ya da `UMUT_VAR` alan): "
        + "; ".join(f"{sa.KUME_KISA[k]} `{gecen[k]}`" for k in ozet["kumeler"])
        + ". Dağılım: "
        + "; ".join(f"{sa.KUME_KISA[k]} " + ", ".join(f"{a} {b}" for a, b in sorted(s.items())) for k, s in sayim.items())
        + ".",
        f"- **Bağımsız gözlem azlığı:** arşiv `{m['endeks_gun_n']}` endeks günü. `{m['ana_rejim']}` tanımıyla yalnız "
        f"`{m['gunler'][m['ana_rejim']]['dusus_donem']}` ayrı düşüş dönemi ve `{m['gunler'][m['ana_rejim']]['yukselis_donem']}` ayrı yükseliş dönemi var.",
    ]
    sert = []
    for kume, kv in ozet["kumeler"].items():
        satir = {x["grup"]: x for x in kv["kademe"]["60"]}
        r, lo, sh = satir[KADEME_AD[0]], satir[f"{KADEME_AD[0]} — yalnız long"], satir[f"{KADEME_AD[0]} — yalnız short"]
        sert.append(
            f"{sa.KUME_KISA[kume]} `{r['n']}` işlem, net `{_f(r['net_ort'])} R` {_aralik(r)}, keşif `{_f(r['kesif_net'])}` / doğrulama `{_f(r['dogrulama_net'])}` "
            f"(long `{lo['n']}` işlem `{_f(lo['net_ort'])}`; short `{sh['n']}` işlem `{_f(sh['net_ort'])}` {_aralik(sh)})"
        )
    s.append(
        "- **Kademeli tabloda öne çıkan hücre (ön-kayıtlı filtre değil, betimleyici):** endeks son 60 günde işlemin tersine %5'ten fazla gitmişse → "
        + "; ".join(sert)
        + ". \"Long\" satırı endeksin 60 günde %5'ten fazla DÜŞTÜĞÜ, \"short\" satırı %5'ten fazla YÜKSELDİĞİ durumdur. "
        "Aralık sıfırı içeriyorsa kural değil, gölge deftere adaydır."
    )
    dy = ozet.get("duyarlilik")
    if dy:
        s.append(
            f"- **Duyarlılık:** girişle aynı anda kapanan endeks günü de sayılırsa `{dy['degisen_karar_n']}` karar etiketi değişiyor; "
            f"`GECTI` ya da `UMUT_VAR` alan varyant sayısı `{dy['gecen_n']}`."
        )
    return s


def _markdown(ozet: dict[str, Any]) -> str:
    m = ozet["meta"]
    s: list[str] = [
        "# Gölge v2 — Endeks Rejimi Filtresi: \"Endeks Uzun Süredir Düşüyorsa İşlem Yok\"",
        "",
        "> Üretici: `python -m research.golge_v2_endeks_filtresi`. Bu dosya elle düzenlenmez.",
        "",
        f"- Kapsam: `4h + 1d` birincil işlemler (sansürsüz, veri karantinası dışı). İşlem: `{m['islem_n']}`. Sonuçlar ana CSV'den okunur; yarış yeniden koşulmaz.",
        f"- Endeks: `{m['endeks']}` günlük, `{m['endeks_ilk_gun']}` – `{m['endeks_son_gun']}` (`{m['endeks_gun_n']}` gün). Rejim yalnız girişten ÖNCE kapanmış "
        "günlerden hesaplanır; aynı günün kapanışı kullanılmaz.",
        "",
        f"**Okuma kılavuzu.** `Doğrudan stop`: stop olan ve stop mumundan önce `{ESIK_YARIM_ATR:g} ATR` kârı hiç görmemiş işlem (doğrudan düşen ya da "
        f"çok az yükselip düşen). `0.5 ATR görüp stop`: stoptan önce en az `{ESIK_YARIM_ATR:g} ATR` kâr görmüş olan. İkisinin toplamı stop oranıdır; mum "
        "çözünürlüğünde ölçülür (stop mumunun içi görülmez). `Fayda`: elenen işlemin net R'sinin ters işaretlisi; "
        "elenen işlemler zarar ediyorsa pozitiftir. `Toplam fayda R`: filtre uygulansaydı toplam net R'nin değişimi. `Fayda en kötü GA`: işlem başına "
        "faydanın (elenmeyenlerde 0) sembol / gün / hafta / ay kümeli %95 aralıklarının en düşük alt ve en yüksek üst sınırı. `Ayrı dönem`: elenen "
        "işlemlerin düştüğü ayrı rejim dönemi sayısı; parantez içi, elenen işlemlerin toplamda zarar ettiği dönem sayısı.",
        "",
        "**Kabul kuralı.** `GECTI`: fayda keşif ve doğrulamada pozitif, iki dönemde de elenen işlem ≥ 30 ve iki dönemde de en kötü alt sınır sıfırın "
        "üstünde. `UMUT_VAR`: aynı, ama alt sınır yalnız havuzda sıfırın üstünde. `ZAYIF_ARTI`: iki dönemde de pozitif ama aralık sıfırı içeriyor ya da "
        "bir dönemde elenen işlem < 30. `GECMEDI`: en az bir dönemde fayda pozitif değil (elenen işlemler o dönemde kâr etmiş). `ZARARLI`: havuzda en "
        "kötü üst sınır bile negatif. `SAYILMAZ_N<30`: elenen işlem 30'dan az.",
        "",
        "**Sınırlar.** Rejim bir zaman değişkenidir; aynı gün açılan işlemler aynı rejimi taşır ve bir dönem haftalarca sürer. İki yıllık arşivde ayrı "
        "dönem sayısı azdır, bu yüzden hafta ve ay kümeli aralıklar bile belirsizliği olduğundan dar gösterebilir. "
        f"`{len(REJIMLER)}` tanım × `{len(FILTRELER)}` filtre × 3 küme sınandı; çoklu karşılaştırma düzeltmesi yok. Short sonuçları açığa satışın mümkün olduğunu varsayar.",
        "",
        "## Kısa özet",
        "",
    ]
    s += _kisa_ozet_md(ozet)
    s += [
        "",
        "## Rejim tanımları ve arşivde kapladıkları yer",
        "",
        "| Tanım | Düşüş koşulu | Düşüş günü | Yükseliş günü | Kararsız | Geçmiş yetersiz | Ayrı düşüş dönemi | Ayrı yükseliş dönemi |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for ad, aciklama in REJIMLER.items():
        g = m["gunler"][ad]
        s.append(
            f"| `{ad}` | {aciklama} | {g['dusus_gun']} | {g['yukselis_gun']} | {g['kararsiz_gun']} | {g['bilinmeyen_gun']} | {g['dusus_donem']} | {g['yukselis_donem']} |"
        )
    for kume, v in ozet["kumeler"].items():
        baz = v["baz"]
        s += [
            "",
            f"## {kume} — {baz['n']} işlem",
            "",
            f"Baz: stop `{_yz(baz['stop_pay'])}`, doğrudan stop `{_yz(baz['dogrudan_stop_pay'])}`, 0.5 ATR görüp stop `{_yz(baz['yarim_atr_stop_pay'])}`, "
            f"net `{_f(baz['net_ort'])} R`, toplam `{_f(baz['net_toplam'], 1)} R`.",
            "",
            "### 1. Rejim işlemin yönüne göre",
            "",
            "Long işlem için düşüş rejimi \"karşı\", short işlem için yükseliş rejimi \"karşı\"dır.",
        ]
        for ad, rv in v["rejimler"].items():
            s += ["", f"**`{ad}`** — {rv['aciklama']}:", ""] + _grup_md(rv["iliski"], "Rejim", ILISKI_AD)
        s += ["", "### 2. Yön × rejim (ana tanım)", "", f"`{m['ana_rejim']}`:", ""] + _grup_md(v["rejimler"][m["ana_rejim"]]["yon_rejim"], "Yön / rejim")
        s += ["", "### 3. Filtreler"]
        for filtre, (aciklama, _) in FILTRELER.items():
            s += ["", f"**{aciklama}** (`{filtre}`):", ""] + _filtre_md(v, filtre)
        s += [
            "",
            "### 4. Kademeli bakış: girişten önceki endeks getirisi, işlemin yönüne göre",
            "",
            "Betimleyicidir; kademeler ön-kayıtlı filtre değildir ve kabul merdiveninden geçmez. \"Ters\": long için endeks düşmüş, short için yükselmiş.",
        ]
        for pencere in (20, 60):
            s += ["", f"Son `{pencere}` gün:", ""] + _grup_md(v["kademe"][str(pencere)], f"Son {pencere} günde endeks")
    return "\n".join(s) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gölge v2 endeks rejimi filtresi")
    ap.add_argument("--girdi", type=Path, default=sa.VARSAYILAN_GIRDI, help="mod0_baz.csv.gz dosyasının bulunduğu dizin")
    ap.add_argument("--cikti", type=Path, default=None, help="varsayılan: <girdi>/endeks_filtresi")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args(argv)
    cikti = args.cikti or (args.girdi / "endeks_filtresi")
    endeks = endeks_gunluk()
    anatomi = sa.anatomiyi_cikar(sa.islemleri_yukle(args.girdi), workers=args.workers)
    df = rejimleri_ekle(anatomi, endeks)
    ozet = ozet_uret(df, endeks)
    diger = ozet_uret(rejimleri_ekle(anatomi, endeks, ayni_an_dahil=True), endeks)
    ozet["duyarlilik"] = duyarlilik_ozeti(ozet["kumeler"], diger["kumeler"])
    cikti.mkdir(parents=True, exist_ok=True)
    kolonlar = ["olay_id", "sembol", "tf", "yon", "donem", "kalite_katmani", "bar_close_time", NET, "cikis_turu", "stop_mfe_atr", "dogrudan_stop", "yarim_atr_stop", "bir_atr_stop"]
    kolonlar += [c for c in df.columns if c.startswith(("rj_", "iliski_", "epizot_", "endeks_getiri_"))]
    df[kolonlar].to_csv(cikti / "islemler.csv.gz", index=False)
    (cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    (cikti / "RAPOR.md").write_text(_markdown(ozet), encoding="utf-8")
    sayim = karar_sayimi(ozet["kumeler"])
    print(f"Tamamlandi -> {cikti} | islem={len(df)} | kararlar: {sayim}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
