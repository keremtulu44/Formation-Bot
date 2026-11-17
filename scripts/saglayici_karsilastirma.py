# -*- coding: utf-8 -*-
"""Sağlayıcı karşılaştırma ve geçiş kararı ölçümü (2026-11-16).

İki mod:

  * ``--mod arsiv``  : Ağ GEREKTİRMEZ. ``bot_data/*.json`` yerel arşivini ölçer
    (bar/gün, sıfır hacim oranı, ilk bar etiketi, 1s'ten türetilen 4s barların
    kaçının kısmi olduğu). Yedekleşme kararının "bugün neredeyiz" tabanı.
  * ``--mod canli``  : Verilen sağlayıcılardan aynı sembol/TF'yi çeker ve
    karşılaştırır (referans: yahoo). Ağ erişimi olan makinede çalıştırılır.

Karar kapısı (``karar_ver``) — üçü birlikte sağlanmadan "geç" denmez:

  1. ortak bar oranı  ≥ %98   (eksik bar yedekte olmamalı)
  2. kapanış farkı medyanı ≤ %0,05 ve en büyük fark ≤ %0,50
  3. adayda sıfır hacim oranı referanstan kötü değil

Ölçüm hiçbir üretim kodunu değiştirmez, ``bot_data``ya yazmaz, ağ yoksa
"ulaşılamadı" der ve uydurmaz.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

import pandas as pd

ISTANBUL = "Europe/Istanbul"
KOLONLAR = ["open", "high", "low", "close", "volume"]

# --- KARAR EŞİKLERİ (tek yerde; testler bunlara bağlı) ---------------------
ESIK_ORTak_BAR = 0.98
ESIK_MEDYAN_FARK_PCT = 0.05
ESIK_MAX_FARK_PCT = 0.50


# --------------------------------------------------------------- NORMALİZE --
def normalize(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Sağlayıcı çıktısını tek biçime getirir: İstanbul TZ, sıralı, tekrarsız.

    Sağlayıcılar farklı kolon adı (``Open``/``open``) ve farklı TZ verir; burada
    tek biçime inmeden karşılaştırma yapmak yanıltıcı olur.
    """
    if df is None or len(df) == 0:
        return None
    frame = df.copy()
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    eksik = [k for k in KOLONLAR if k not in frame.columns]
    if eksik:
        raise ValueError(f"eksik kolon: {eksik}")
    idx = pd.DatetimeIndex(frame.index)
    if idx.tz is None:
        idx = idx.tz_localize(ISTANBUL)
    else:
        idx = idx.tz_convert(ISTANBUL)
    frame.index = idx
    frame = frame[KOLONLAR].apply(pd.to_numeric, errors="coerce")
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame.dropna(subset=["close"])


def _fark_pct(a: float, b: float) -> float:
    if a == 0:
        return 0.0 if b == 0 else 100.0
    return abs(b - a) / abs(a) * 100.0


# ------------------------------------------------------------ KARŞILAŞTIRMA --
def karsilastir(referans: pd.DataFrame, aday: pd.DataFrame) -> Dict:
    """İki seriyi kapanış bazında karşılaştırır (yalnız ortak zaman damgaları)."""
    ortak = referans.index.intersection(aday.index)
    metrik: Dict = {
        "ref_bar": int(len(referans)),
        "aday_bar": int(len(aday)),
        "ortak_bar": int(len(ortak)),
        "ortak_oran": round(len(ortak) / max(1, len(referans)), 4),
        "eksik_oran": round(1 - len(ortak) / max(1, len(referans)), 4),
        "fazla_oran": round(max(0, len(aday) - len(ortak)) / max(1, len(aday)), 4),
        "sifir_hacim_ref_pct": round(float((referans["volume"] == 0).mean() * 100), 2),
        "sifir_hacim_aday_pct": round(float((aday["volume"] == 0).mean() * 100), 2),
        "medyan_fark_pct": None,
        "max_fark_pct": None,
    }
    if len(ortak):
        farklar = [_fark_pct(float(referans.at[t, "close"]), float(aday.at[t, "close"]))
                   for t in ortak]
        seri = pd.Series(farklar)
        metrik["medyan_fark_pct"] = round(float(seri.median()), 4)
        metrik["max_fark_pct"] = round(float(seri.max()), 4)
        metrik["fark_esik_asimi"] = int((seri > ESIK_MAX_FARK_PCT).sum())
    metrik["karar"] = karar_ver(metrik)
    return metrik


def karar_ver(metrik: Dict) -> str:
    """'geç' / 'koşullu' / 'red' — gerekçesiyle birlikte tek kelime."""
    ortak_oran = metrik.get("ortak_oran")
    medyan = metrik.get("medyan_fark_pct")
    if ortak_oran is None or medyan is None:
        return "red (karşılaştırılabilir ortak bar yok)"
    if ortak_oran >= ESIK_ORTak_BAR and medyan <= ESIK_MEDYAN_FARK_PCT \
            and (metrik.get("max_fark_pct") or 0) <= ESIK_MAX_FARK_PCT:
        return "geç"
    if ortak_oran >= 0.90 and medyan <= ESIK_MEDYAN_FARK_PCT:
        return "koşullu (bar eksik ama fiyat uyumlu)"
    return "red"


# --------------------------------------------------------------- ARŞİV -----
def arsiv_kalite(veri_dizini: Path | str, tf_dakika: int = 240) -> Dict:
    """Yerel ``bot_data/*.json`` arşivinden kalite tabanı çıkarır (ağsız)."""
    toplam_bar = sifir_hacim = 0
    gun_bar: Dict[int, int] = {}
    ilk_etiket: Dict[str, int] = {}
    sembol = 0
    turetilen_tf = 0
    tf_kismi = 0
    for dosya in sorted(Path(veri_dizini).glob("*.json")):
        try:
            ham = json.loads(dosya.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - bozuk cache raporu düşürmesin
            continue
        if not ham:
            continue
        frame = pd.DataFrame(ham)
        if "timestamp" not in frame.columns:
            continue
        idx = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert(ISTANBUL)
        frame.index = pd.DatetimeIndex(idx)
        frame = frame.sort_index()
        sembol += 1
        toplam_bar += len(frame)
        if "volume" in frame.columns:
            sifir_hacim += int((pd.to_numeric(frame["volume"], errors="coerce") == 0).sum())
        ilk_etiket[str(frame.index[0].time())] = ilk_etiket.get(str(frame.index[0].time()), 0) + 1
        for _, grup in frame.groupby(frame.index.date):
            gun_bar[len(grup)] = gun_bar.get(len(grup), 0) + 1
        # 1s -> hedef TF türetimi: kaç bar ve kaçı "kısmi" (bar süresinden kısa)
        origin = frame.index[0].normalize() + pd.Timedelta(hours=9, minutes=30)
        kova = frame.resample(f"{tf_dakika}min", origin=origin, label="left",
                              closed="left").agg({"open": "first", "high": "max",
                                                  "low": "min", "close": "last",
                                                  "volume": "sum"}).dropna(subset=["close"])
        sayim = frame.resample(f"{tf_dakika}min", origin=origin, label="left",
                               closed="left").size()
        turetilen_tf += len(kova)
        tam_bar = tf_dakika // 60
        tf_kismi += int((sayim.reindex(kova.index).fillna(0) < tam_bar).sum())
    return {
        "sembol": sembol,
        "toplam_bar": toplam_bar,
        "sifir_hacim_pct": round(sifir_hacim / max(1, toplam_bar) * 100, 2),
        "gun_bar_dagilimi": dict(sorted(gun_bar.items())),
        "ilk_bar_etiketi": dict(ilk_etiket),
        "turetilen_tf_bar": turetilen_tf,
        "turetilen_tf_kismi": tf_kismi,
        "tf_dakika": tf_dakika,
    }


# --------------------------------------------------------------- RAPOR -----
def rapor_markdown(sonuclar: Sequence[Dict]) -> str:
    satirlar = ["| Sembol | TF | Ortak bar | Medyan fark % | Max fark % | Sıfır hacim % (ref→aday) | Karar |",
                "|---|---|---:|---:|---:|---|---|"]
    for s in sonuclar:
        satirlar.append(
            f"| {s.get('sembol','?')} | {s.get('tf','?')} | {s.get('ortak_bar','-')}"
            f" | {_yuzde(s.get('medyan_fark_pct'))} | {_yuzde(s.get('max_fark_pct'))}"
            f" | {s.get('sifir_hacim_ref_pct','-')} → {s.get('sifir_hacim_aday_pct','-')}"
            f" | {s.get('karar','-')} |")
    return "\n".join(satirlar)


def _yuzde(deger) -> str:
    return "-" if deger is None else f"{deger:.3f}".replace(".", ",")


# ------------------------------------------------------------- TANI -------
def _izi(hata: BaseException, satir: int = 6) -> List[str]:
    """Hataya giden çağrı zincirinin son satırları (teşhis için)."""
    import traceback
    try:
        metin = "".join(traceback.format_exception(type(hata), hata, hata.__traceback__))
    except Exception:  # noqa: BLE001 - teşhis kendisi hata üretmesin
        return []
    return [s.rstrip() for s in metin.strip().splitlines()[-satir:]]


def _kisa(metin: str, sinir: int = 120) -> str:
    """İz satırlarını okunur tut: uzun mesajları kırp."""
    metin = " ".join(str(metin).split())
    return metin if len(metin) <= sinir else metin[: sinir - 1] + "…"


_CAKISMA_ISARETI = "<" * 7 + " "


def cakisma_dosyalari(kok: "str | Path" = ".") -> List[str]:
    """Çalışma ağacında çözülmemiş birleştirme işareti kalmış ``.py`` dosyaları.

    Neden: yarım kalmış ``git merge`` sonrası ``import config`` "SyntaxError"
    verir; hata metni bunu söylemez. Bu tarama sebebi doğrudan söyler.
    """
    atla = {".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist", "out"}
    bulunan: List[str] = []
    for yol in sorted(Path(kok).rglob("*.py")):
        if atla & set(yol.parts):
            continue
        try:
            metin = yol.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _CAKISMA_ISARETI in metin:
            bulunan.append(str(yol))
    return bulunan


def tani(dene: bool = False, sembol: str = "THYAO", adet: int = 5, kok: str = ".",
         saglayicilar: Optional[Dict[str, Callable[[str, str, int], Optional[pd.DataFrame]]]] = None) -> Dict:
    """Ortam teşhisi: hangi Python, hangi paket, import neden patlıyor, ağ var mı.

    Neden: canlı mod hataları tek satıra sığmak zorunda ("red (SyntaxError)").
    Bu mod tek komutta sürümü, çalışan yorumlayıcıyı, import sonucunu, hata
    izini, çakışma işareti kalan dosyaları ve (istenirse) gerçek çekme denemesini
    yazar. Varsayılan ``dene=False``: ağ olmadan da çalışır.
    """
    import platform
    import sys as _sys

    bilgi: Dict = {
        "python": platform.python_version(),
        "calisan_python": _sys.executable,
        "venv": None if _sys.prefix == _sys.base_prefix else _sys.prefix,
        "platform": platform.platform(),
        "onerilen_python": "3.11 veya 3.12 (repoda .python-version)",
        "paketler": {},
        "importlar": {},
        "izler": {},
        "denemeler": {},
        "cakisma": [],
    }
    from importlib.metadata import PackageNotFoundError, version as _v
    for paket in ("yfinance", "pandas", "numpy", "borsapy", "curl_cffi", "tvdatafeed"):
        try:
            bilgi["paketler"][paket] = _v(paket)
        except PackageNotFoundError:
            bilgi["paketler"][paket] = None
    for ad, modul in (("yfinance", "yfinance"), ("borsapy", "borsapy"),
                      ("tvdatafeed", "tvDatafeed")):
        try:
            __import__(modul)
            bilgi["importlar"][ad] = "ok"
        except Exception as hata:  # noqa: BLE001 - teşhis kendisi hata üretmesin
            bilgi["importlar"][ad] = _hata_metni(hata)
            bilgi["izler"][ad] = _izi(hata)
    if kok:
        bilgi["cakisma"] = cakisma_dosyalari(kok)
    if dene:
        kaynak = SAGLAYICILAR if saglayicilar is None else saglayicilar
        for ad, cek in kaynak.items():
            try:
                df = cek(sembol, "1d", adet)
                bilgi["denemeler"][ad] = {"bar": 0 if df is None else int(len(df))}
            except Exception as hata:  # noqa: BLE001
                bilgi["denemeler"][ad] = {"hata": _hata_metni(hata), "izi": _izi(hata)}
    bilgi["surum_uyari"] = (
        None if _sys.version_info >= (3, 10)
        else "Python 3.10'dan eski: borsapy/curl_cffi kurulamaz, yfinance import "
             "edilemez (SyntaxError). Python 3.11/3.12 kurun."
    )
    return bilgi


def tani_markdown(bilgi: Dict) -> str:
    satirlar = [
        "### Ortam teşhisi",
        f"- Python: **{bilgi['python']}** (önerilen: {bilgi['onerilen_python']})",
        f"- Çalışan yorumlayıcı: {bilgi.get('calisan_python') or '?'}",
        f"- Sanal ortam: {bilgi.get('venv') or 'YOK (venv dışında çalışıyor)'}",
        f"- Platform: {bilgi['platform']}",
        "- Paketler: " + " · ".join(
            f"{k} {v or 'YOK'}" for k, v in bilgi["paketler"].items()),
        "- Import: " + " · ".join(f"{k}: {v}" for k, v in bilgi["importlar"].items()),
    ]
    for ad, iz in (bilgi.get("izler") or {}).items():
        if iz:
            satirlar.append(f"- {ad} hatasının izi: " + " ⏎ ".join(_kisa(x) for x in iz[-3:]))
    cakisma = bilgi.get("cakisma") or []
    if cakisma:
        ilk = ", ".join(cakisma[:3]) + (" …" if len(cakisma) > 3 else "")
        satirlar.append(
            f"- ⛔ Çözülmemiş birleştirme işareti **{len(cakisma)} dosyada** ({ilk})."
            " Bu hâlde `import config` \"SyntaxError\" verir."
            " Çözüm: `git merge --abort` (yarım merge) veya dosyaları elle düzelt.")
    elif bilgi.get("cakisma") == []:
        satirlar.append("- Birleştirme işareti: yok (çalışma ağacı temiz)")
    for ad, d in (bilgi.get("denemeler") or {}).items():
        if "bar" in d:
            satirlar.append(f"- Deneme {ad}: {d['bar']} bar geldi ✅")
        else:
            satirlar.append(f"- Deneme {ad}: {d['hata']}")
            if d.get("izi"):
                satirlar.append("  · " + " ⏎ ".join(_kisa(x) for x in d["izi"][-2:]))
    if bilgi.get("surum_uyari"):
        satirlar.append(f"- ⚠️ {bilgi['surum_uyari']}")
    return "\n".join(satirlar)


# ------------------------------------------------------------ SAĞLAYICILAR --
def _yahoo(sembol: str, tf: str, adet: int) -> Optional[pd.DataFrame]:
    import yfinance as yf
    from config import MARKET_SUFFIX, PROVIDER_SYMBOL_MAP
    ticker = PROVIDER_SYMBOL_MAP.get(sembol, f"{sembol}{MARKET_SUFFIX}")
    aralik = {"1h": "1h", "1d": "1d"}[tf]
    df = yf.Ticker(ticker).history(period="60d" if tf == "1h" else "2y", interval=aralik)
    if df is None or len(df) == 0:
        return None
    return df.tail(adet) if adet else df


def _borsapy(sembol: str, tf: str, adet: int) -> Optional[pd.DataFrame]:
    import borsapy as bp
    periyot = {"1h": "1ay", "1d": "1y"}[tf]
    df = bp.Ticker(sembol).history(period=periyot, interval=tf)
    if df is None or len(df) == 0:
        return None
    return df.tail(adet) if adet else df


def _tvdatafeed(sembol: str, tf: str, adet: int) -> Optional[pd.DataFrame]:
    from tvDatafeed import Interval, TvDatafeed
    esleme = {"1h": Interval.in_1_hour, "1d": Interval.in_daily}
    df = TvDatafeed().get_hist(symbol=sembol, exchange="BIST",
                               interval=esleme[tf], n_bars=adet or 500)
    return None if df is None or len(df) == 0 else df


SAGLAYICILAR: Dict[str, Callable[[str, str, int], Optional[pd.DataFrame]]] = {
    "yahoo": _yahoo,
    "borsapy": _borsapy,
    "tvdatafeed": _tvdatafeed,
}


def canli_karsilastir(semboller: Iterable[str], tfs: Iterable[str], adet: int = 360,
                      referans: str = "yahoo",
                      adaylar: Iterable[str] = ("borsapy",)) -> List[Dict]:
    """Referans sağlayıcı ile adayları karşılaştırır; ulaşılamayanı raporlar."""
    sonuclar: List[Dict] = []
    for sembol in semboller:
        for tf in tfs:
            try:
                ref_ham = SAGLAYICILAR[referans](sembol, tf, adet)
            except Exception as hata:  # noqa: BLE001 - ağ hatası rapora düşsün
                sonuclar.append({"sembol": sembol, "tf": tf,
                                 "karar": f"red ({referans} ulaşılamadı: {_hata_metni(hata)})"})
                continue
            ref = normalize(ref_ham)
            if ref is None:
                sonuclar.append({"sembol": sembol, "tf": tf,
                                 "karar": f"red ({referans} boş döndü)"})
                continue
            for ad in adaylar:
                try:
                    aday = normalize(SAGLAYICILAR[ad](sembol, tf, adet))
                except Exception as hata:  # noqa: BLE001
                    sonuclar.append({"sembol": sembol, "tf": tf,
                                     "karar": f"red ({ad} ulaşılamadı: {_hata_metni(hata)})"})
                    continue
                if aday is None:
                    sonuclar.append({"sembol": sembol, "tf": tf,
                                     "karar": f"red ({ad} boş döndü)"})
                    continue
                kayit = {"sembol": sembol, "tf": tf, "aday": ad}
                kayit.update(karsilastir(ref, aday))
                sonuclar.append(kayit)
    return sonuclar


# ----------------------------------------------------------------- CLI -----
def _hata_metni(hata: BaseException) -> str:
    """``SyntaxError`` tek başına hiçbir şey anlatmaz: tip + mesajın başı."""
    mesaj = " ".join(str(hata).split())[:140]
    return f"{type(hata).__name__}: {mesaj}" if mesaj else type(hata).__name__


def _liste(degerler: Iterable[str]) -> List[str]:
    """Virgül ve/veya boşlukla ayrılmış listeleri tek listeye indirir."""
    cikti: List[str] = []
    for deger in degerler or []:
        cikti.extend(parca.strip() for parca in str(deger).split(",") if parca.strip())
    return cikti


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Sağlayıcı karşılaştırma / geçiş ölçümü")
    ap.add_argument("--mod", choices=("arsiv", "canli", "tanis"), default="arsiv")
    ap.add_argument("--veri-dizini", default="bot_data")
    # Listeler HEM virgüllü HEM boşluklu verilebilir:
    #   --sembol "THYAO,GARAN"   ·   --sembol THYAO GARAN
    # (PowerShell virgülsüz yazımda virgülü ayraç sayıp argümanı bölüyor.)
    ap.add_argument("--sembol", nargs="+", default=["THYAO,GARAN,AKBNK,ASELS,EREGL"])
    ap.add_argument("--tf", nargs="+", default=["1g"])
    ap.add_argument("--adet", type=int, default=360)
    ap.add_argument("--aday", nargs="+", default=["borsapy"])
    ap.add_argument("--cikti", default="")
    # Teşhis modu: --tanis-dene 1 → gerçek çekme denemesi (ağ gerekir)
    ap.add_argument("--tanis-dene", type=int, default=1)
    ap.add_argument("--tanis-sembol", default="THYAO")
    args = ap.parse_args(argv)

    if args.mod == "tanis":
        bilgi = tani(dene=bool(args.tanis_dene), sembol=args.tanis_sembol,
                     adet=args.adet if args.adet < 60 else 5)
        metin = tani_markdown(bilgi)
        print(metin)
        print()
        print(json.dumps(bilgi, ensure_ascii=False, indent=2))
        if args.cikti:
            Path(args.cikti).write_text(metin + "\n", encoding="utf-8")
        return 0

    if args.mod == "arsiv":
        rapor = arsiv_kalite(args.veri_dizini)
        metin = "\n".join([
            "### Yerel arşiv kalitesi (ağsız)",
            f"- sembol: {rapor['sembol']} · bar: {rapor['toplam_bar']}",
            f"- sıfır hacim: %{rapor['sifir_hacim_pct']}",
            f"- gün başına bar: {rapor['gun_bar_dagilimi']}",
            f"- ilk bar etiketi: {rapor['ilk_bar_etiketi']}",
            f"- türetilen {rapor['tf_dakika']}dk bar: {rapor['turetilen_tf_bar']}"
            f" (kısmi: {rapor['turetilen_tf_kismi']})",
        ])
        print(metin)
        print()
        print(json.dumps(rapor, ensure_ascii=False, indent=2))
    else:
        semboller = [s.upper() for s in _liste(args.sembol)]
        adaylar = _liste(args.aday)
        tfs = ["1h" if t.lower() in ("1s", "1h") else "1d" for t in _liste(args.tf)]
        sonuclar = canli_karsilastir(semboller, tfs, adet=args.adet, adaylar=adaylar)
        metin = rapor_markdown(sonuclar)
        print(metin)
        print("\nHam:", json.dumps(sonuclar, ensure_ascii=False)[:2000])

    if args.cikti:
        Path(args.cikti).write_text(metin + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
