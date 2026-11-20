#!/usr/bin/env python3
"""Native 2h/4h dosyalarını 1h ile karşılaştırır: aynı barı mı anlatıyorlar?

Neden gerekli
-------------
``NATIVE_VERI_GELISI_2026-11-19.md`` "resample yok" diyor ve ``manifest.json``
``resample_kullanildi=False`` yazıyor. Bu, 2h/4h rakamlarının **sağlayıcıdan
native** geldiğini kanıtlar — ama **1h ile tutarlı** olduğunu kanıtlamaz.
Ayrı kaynak (TradingView) ve ayrı kova çapası kullanıldığı için iki dosya aynı
barın farklı bir yorumunu taşıyabilir. Bu araç farkı ölçer, çünkü:

* Kırılım/teyit, zone ve alarm kararları **kapanış** ve **high/low** üzerinden
  verilir; %0,3'lük bir kapanış farkı 1 ATR'lik bir eşiği nadiren ama tam
  sınırda tetiklenen sinyalleri düzenli olarak çevirir.
* 2h/4h'ye dayanan **her** sayının güvenilirliği bu farkla sınırlıdır.

Ölçüm
-----
1h'den yalnız **referans** kova üretilir (kovalar İstanbul 09:00–19:00 seansına
hizalı: 2h için 09/11/13/15/17, 4h için 09/13/17). 1h hacmi 0 olan kovalar
(Yahoo'nun 09:30 "hayalet" barı) referanstan çıkarılır. Sonra native dosya ile
kapanış/hacim karşılaştırılır.

Kullanım::

    python -m research.native_tutarlilik                # özet tablo
    python -m research.native_tutarlilik --rapor docs/denetim/NATIVE_TUTARLILIK.md
"""

from __future__ import annotations

import argparse
import glob
import math
import os
from pathlib import Path
from typing import Sequence

import pandas as pd

#: 2h/4h kovalarının İstanbul saatine göre sol kenarı.
KOVA_OFFSET = {"2h": "-1h", "4h": "9h"}
#: Bu eşiğin üstündeki ortalama fark "farklı seri" sayılır.
UYUMSUZ_ESIK = 0.5
#: Anlamlı sayı üretmek için gereken en az ortak bar.
MIN_ORTak_BAR = 200

SONUC_KOLONLARI = (
    "symbol", "timeframe", "ortak_bar", "native_bar", "medyan_fark_pct",
    "p95_fark_pct", "max_fark_pct", "fark_05_pay_pct", "birebir_pay_pct",
    "hacim_medyan_fark_pct", "uyumsuz",
)


def _yukle(yol: Path) -> pd.DataFrame:
    df = pd.read_csv(yol, compression="gzip")
    zaman = pd.to_datetime(df.pop("bar_time"), utc=True, errors="coerce")
    df.index = pd.DatetimeIndex(zaman.dt.tz_convert("Europe/Istanbul"), name="timestamp")
    return df


def _referans(hourly: pd.DataFrame, tf: str) -> pd.DataFrame:
    """1h serisinden yalnız KARŞILAŞTIRMA için kova üretir (türetim değil)."""
    kova = hourly.resample(
        tf, label="left", closed="left", origin="start_day", offset=KOVA_OFFSET[tf]
    ).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    kova = kova.dropna(subset=["close"])
    # 1h hacmi 0 olan barlar (Yahoo'nun 09:30 "hayalet" barı) FİYAT taşır:
    # high/low'u gerçek seansın fitilidir, bu yüzden kovadan çıkarılmaz —
    # çıkarılsaydı kova fitilsiz kalır ve fark yapay olarak büyürdü. Yalnız
    # kovanın TAMAMI hacimsizse (gerçekten işlem görmemiş) kıyas dışı bırakılır.
    return kova[kova["volume"].fillna(0) > 0]


def sembol_karsilastir(sembol: str, tf: str, kok: Path) -> dict | None:
    native_yol = kok / f"{sembol}_{tf}.csv.gz"
    saatlik_yol = kok / f"{sembol}_1h.csv.gz"
    if not (native_yol.exists() and saatlik_yol.exists()):
        return None
    native = _yukle(native_yol)
    ref = _referans(_yukle(saatlik_yol), tf)
    ortak = native.index.intersection(ref.index)
    if len(ortak) < MIN_ORTak_BAR:
        return None
    q = native.loc[ortak, "close"].astype(float)
    r = ref.loc[ortak, "close"].astype(float)
    fark = (q / r - 1).abs() * 100
    hacim_q = native.loc[ortak, "volume"].astype(float)
    hacim_r = ref.loc[ortak, "volume"].astype(float)
    hacim_fark = ((hacim_q - hacim_r).abs() / hacim_r.replace(0, math.nan)) * 100
    return {
        "symbol": sembol,
        "timeframe": tf,
        "ortak_bar": int(len(ortak)),
        "native_bar": int(len(native)),
        "medyan_fark_pct": round(float(fark.median()), 4),
        "p95_fark_pct": round(float(fark.quantile(0.95)), 4),
        "max_fark_pct": round(float(fark.max()), 4),
        "fark_05_pay_pct": round(float((fark > 0.5).mean() * 100), 2),
        "birebir_pay_pct": round(float((fark < 1e-6).mean() * 100), 2),
        "hacim_medyan_fark_pct": round(float(hacim_fark.median()), 2)
        if hacim_fark.notna().any() else None,
        "uyumsuz": bool(fark.median() > UYUMSUZ_ESIK),
    }


def tara(kok: Path | str | None = None, timeframeler: Sequence[str] = ("2h", "4h")) -> pd.DataFrame:
    kok = Path(kok) if kok else Path(__file__).resolve().parents[1] / "backfill_data"
    satirlar = []
    for tf in timeframeler:
        for yol in sorted(glob.glob(str(kok / f"*_{tf}.csv.gz"))):
            sembol = os.path.basename(yol).replace(f"_{tf}.csv.gz", "")
            try:
                satir = sembol_karsilastir(sembol, tf, kok)
            except Exception:  # noqa: BLE001 - tek sembol taramayı durdurmasın
                continue
            if satir is not None:
                satirlar.append(satir)
    if not satirlar:
        return pd.DataFrame(columns=SONUC_KOLONLARI)
    return pd.DataFrame(satirlar)


def rapor_yaz(df: pd.DataFrame, yol: Path) -> str:
    satirlar = [
        "# Native 2h/4h ↔ 1h tutarlılığı",
        "",
        "> Üreten: `python -m research.native_tutarlilik`",
        "> Amaç: native dosyaların **1h ile aynı barı** anlatıp anlatmadığını ölçmek.",
        "",
        "Bu bir resample karşılaştırması **değildir**: hiçbir sayı 1h'den türetilmedi,",
        "yalnız iki bağımsız serinin aynı mumu ne kadar farklı kapattığı ölçüldü.",
        "",
    ]
    if df is None or len(df) == 0:
        satirlar.append("Karşılaştırılabilir sembol bulunamadı.")
        metin = "\n".join(satirlar) + "\n"
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(metin, encoding="utf-8")
        return metin

    for tf, grup in df.groupby("timeframe"):
        uyumsuz = grup[grup["uyumsuz"]]
        satirlar += [
            f"## {tf} — {len(grup)} sembol",
            "",
            f"- Kapanış |fark| **medyanı**: {grup['medyan_fark_pct'].median():.3f}% "
            f"(sembol p95 medyanı {grup['p95_fark_pct'].median():.3f}%)",
            f"- Birebir aynı kapanış: sembollerin medyanı **%{grup['birebir_pay_pct'].median():.1f}**",
            f"- Barların >%0,5 fark ettiği oran (sembol medyanı): **%{grup['fark_05_pay_pct'].median():.1f}**",
            f"- Uyumsuz sembol (medyan fark > %{UYUMSUZ_ESIK}): **{len(uyumsuz)}** "
            f"(%{100 * len(uyumsuz) / len(grup):.1f})",
            "",
        ]
        if len(uyumsuz):
            satirlar += [
                "| sembol | ortak bar | medyan fark | p95 | birebir |",
                "|---|---:|---:|---:|---:|",
            ]
            for satir in uyumsuz.sort_values("medyan_fark_pct", ascending=False).itertuples():
                satirlar.append(
                    f"| {satir.symbol} | {satir.ortak_bar} | {satir.medyan_fark_pct:.2f}% | "
                    f"{satir.p95_fark_pct:.2f}% | %{satir.birebir_pay_pct:.1f} |"
                )
            satirlar.append("")
    satirlar += [
        "## Nasıl okunur",
        "",
        "- %0,3 civarı medyan fark **beklenen** düzeydir: kova çapası (09:00 vs 09:30) ve",
        "  sağlayıcı fiyat kaynağı farkı. Bu düzeyde 2h/4h sayıları kullanılabilir;",
        "  ancak tam eşik sınırında tetiklenen sinyaller iki seride farklı sonuç verir.",
        "- **%1 üstü** fark, o sembolde 2h/4h analizinin 1h ile çeliştiğini gösterir;",
        "  o sembolün 2h/4h sayıları raporda ayrıca işaretlenmeli.",
        "- Bu araç karar vermez; hangi sembolde hangi zaman dilimine güvenilebileceğini",
        "  gösteren bir **veri kalitesi** ölçümüdür.",
        "",
    ]
    metin = "\n".join(satirlar) + "\n"
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(metin, encoding="utf-8")
    return metin


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Native 2h/4h ↔ 1h tutarlılık taraması")
    p.add_argument("--kok", default="", help="arşiv dizini (varsayılan backfill_data)")
    p.add_argument("--timeframe", default="2h,4h")
    p.add_argument("--csv", default="", help="ham sonucu CSV'ye yaz")
    p.add_argument("--rapor", default="", help="Markdown rapor yaz")
    args = p.parse_args(argv)

    tfs = [t.strip() for t in args.timeframe.split(",") if t.strip()]
    df = tara(args.kok or None, tfs)
    if len(df) == 0:
        print("[tutarlilik] karşılaştırılabilir sembol yok")
        return 1
    for tf, grup in df.groupby("timeframe"):
        print(
            f"[{tf}] sembol={len(grup)} · medyan |fark|={grup['medyan_fark_pct'].median():.3f}% · "
            f"p95={grup['p95_fark_pct'].median():.3f}% · uyumsuz={int(grup['uyumsuz'].sum())}"
        )
    if args.csv:
        Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.csv, index=False)
        print(f"[csv] {args.csv}")
    if args.rapor:
        metin = rapor_yaz(df, Path(args.rapor))
        print(f"[rapor] {args.rapor} ({len(metin)} karakter)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
