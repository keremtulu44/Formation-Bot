# -*- coding: utf-8 -*-
"""Adım 0: mevcut replay çıktısında ayırt edici özellik taraması.

Replay YOK, üretim kodu YOK. `var/replay/gozlemler.csv` okunur.

Sorun: hangi değişken "kırılım devam etti mi" sorusunu gerçekten ayırıyor?

Bölme disiplini (kritik): yan yana iki zaman bloğu neredeyse aynı dönemdir;
"ilk 100 / sonraki 100" gerçek bir sınav değildir. Bu yüzden üç ayrı bölme
kullanılır ve bir özellik AD?Y olabilmesi için AYRIK SEMBOL bölmesinde ve
UZAK DÖNEM bölmesinde aynı yönde çıkması gerekir:

  S  — sembol bölmesi: semboller hash ile ikiye ayrılır (tam ayrık,
       aynı piyasa dönemi).
  Z  — uzak dönem: ilk bölüm ile son bölüm arasında 5 hafta BO?LUK bırakılır;
       boşluktaki gözlemler tamamen atılır (24-48 barlık ileri bakan etiket
       sınırı kirletmesin).
  Y  — yan yana blok (kasıtlı "yanlış" yöntem): ilk %50 / son %50. Bunu,
       kullanıcının uyardığı tuzağı göstermek için hesaplıyoruz; karar
       verirken KULLANILMAZ.

Kullanım:
    python scripts/puan_tarama.py
    python scripts/puan_tarama.py --girdi var/replay/gozlemler.csv --leh 2 --ters 1 --ufuk 24
"""

from __future__ import annotations

import argparse
import sys
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from puan_analiz import etiketle  # noqa: E402


def auc(y: pd.Series, x: pd.Series) -> float:
    m = y.notna() & x.notna()
    yy, xx = y[m].to_numpy(float), x[m].to_numpy(float)
    if len(yy) < 50 or yy.min() == yy.max():
        return float("nan")
    r = pd.Series(xx).rank().to_numpy()
    n1 = yy.sum()
    n0 = len(yy) - n1
    return float((r[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def bootstrap_auc(df: pd.DataFrame, ycol: str, xcol: str, tekrar: int = 300,
                  tohum: int = 11) -> Tuple[float, float, float]:
    s = df[["sembol", ycol, xcol]].dropna()
    a = auc(s[ycol], s[xcol])
    if not np.isfinite(a) or len(s) < 200:
        return a, float("nan"), float("nan")
    rng = np.random.default_rng(tohum)
    gruplar = {k: g for k, g in s.groupby("sembol")}
    adlar = np.array(list(gruplar))
    deger = []
    for _ in range(tekrar):
        sec = rng.choice(adlar, size=len(adlar), replace=True)
        p = pd.concat([gruplar[k] for k in sec], ignore_index=True)
        v = auc(p[ycol], p[xcol])
        if np.isfinite(v):
            deger.append(v)
    if len(deger) < 20:
        return a, float("nan"), float("nan")
    return a, float(np.percentile(deger, 2.5)), float(np.percentile(deger, 97.5))


def ozellikler(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["yas"] = d.bar - d.dogum_bar
    d["temas_toplam"] = d.ust_temas.fillna(0) + d.alt_temas.fillna(0)
    d["atr_yuzde"] = d.atr / d.giris * 100.0
    d["tarih"] = pd.to_datetime(d.zaman, errors="coerce", utc=True)
    saat = d.tarih.dt.hour + d.tarih.dt.minute / 60.0
    d["saat"] = saat.where(d.tf != "1d")            # 1g'de saat anlamsız
    d["gun"] = d.tarih.dt.dayofweek.astype(float)
    d["yon_uzun"] = (d.yon == 1).astype(float)
    return d


ADAYLAR = [
    ("kalite", "puan (mevcut)"),
    ("guc", "kırılım gücü"),
    ("guc_govde", "güç: gövde"),
    ("guc_kapanis", "güç: kapanış"),
    ("guc_nufuz", "güç: nüfuz"),
    ("guc_genisleme", "güç: genişleme"),
    ("guc_hacim", "güç: hacim"),
    ("geometri", "geometri"),
    ("egim", "eğim şekli"),
    ("temas_puan", "temas puanı"),
    ("temas_toplam", "temas sayısı"),
    ("ust_temas", "üst temas"),
    ("alt_temas", "alt temas"),
    ("daralma_puan", "daralma puanı"),
    ("daralma", "daralma oranı"),
    ("olgunluk", "olgunluk"),
    ("ilerleme", "ilerleme"),
    ("ihlal_cezasi", "ihlal cezası"),
    ("direk", "direk kalitesi"),
    ("sure_orani", "süre oranı"),
    ("yas", "formasyon yaşı"),
    ("bant_mesafe_atr", "seviyeye mesafe (ATR)"),
    ("dogum_mesafe_atr", "doğumda mesafe (ATR)"),
    ("atr_yuzde", "ATR / fiyat (%)"),
    ("saat", "seans saati"),
    ("gun", "haftanın günü"),
    ("yon_uzun", "yön (uzun=1)"),
]


def bolmeler(d: pd.DataFrame) -> Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]:
    d = d.sort_values("tarih")
    # --- S: ayrık sembol (hash ile deterministik 50/50)
    h = d.sembol.apply(lambda s: zlib.crc32(s.encode()) % 2)
    S = (d[h == 0], d[h == 1])
    # --- Z: uzak dönem + boşluk
    kes = d.tarih.quantile(0.70)
    bosluk = pd.Timedelta(days=35)
    Z = (d[d.tarih < kes - bosluk], d[d.tarih > kes + bosluk])
    # --- Y: yan yana blok (kasıtlı yanlış yöntem)
    n = len(d) // 2
    Y = (d.iloc[:n], d.iloc[n:])
    return {"S": S, "Z": Z, "Y": Y}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Adım 0 özellik taraması")
    ap.add_argument("--girdi", default="var/replay/gozlemler.csv")
    ap.add_argument("--leh", type=float, default=2.0)
    ap.add_argument("--ters", type=float, default=1.0)
    ap.add_argument("--ufuk", type=int, default=24)
    ap.add_argument("--rapor", default="var/replay/tarama.md")
    args = ap.parse_args(argv)

    yol = Path(args.girdi)
    if not yol.is_absolute():
        yol = REPO / yol
    d = pd.read_csv(yol)
    d = d[d.pencere_tam == 1]
    d = ozellikler(d)
    d["y"] = etiketle(d, args.leh, args.ters, args.ufuk)
    d = d[d.y.notna()].copy()

    b = bolmeler(d)
    satir: List[str] = []
    satir.append(f"# Adım 0 · ayırt edici özellik taraması\n")
    satir.append(f"Etiket: lehte {args.leh:g} ATR / ters {args.ters:g} ATR / {args.ufuk} bar · "
                 f"gözlem {len(d)} · taban %{d.y.mean()*100:.1f}\n")
    for ad, (tr, te) in b.items():
        satir.append(f"- **{ad}**: keşif n={len(tr)} taban %{tr.y.mean()*100:.1f} · "
                     f"doğrulama n={len(te)} taban %{te.y.mean()*100:.1f}")
    satir.append("")

    satir.append("## Tek değişken AUC\n")
    satir.append("| değişken | S keşif | S doğrulama | Z keşif | Z doğrulama | Y keşif | Y doğrulama |")
    satir.append("|---|---|---|---|---|---|---|")
    sonuc = []
    for k, etiket in ADAYLAR:
        if k not in d or d[k].notna().sum() < 500:
            continue
        sat = []
        for ad in ("S", "Z", "Y"):
            tr, te = b[ad]
            sat.append(auc(tr.y, tr[k]))
            sat.append(auc(te.y, te[k]))
        satir.append(f"| {etiket} | " + " | ".join("—" if not np.isfinite(v) else f"{v:.3f}"
                                                   for v in sat) + " |")
        sonuc.append((k, etiket, sat))

    # --- aday seçimi: S ve Z'de aynı yönde, eşiği geçen
    satir.append("\n## Adaylar (S ve Z'de aynı yönde)\n")
    satir.append("| değişken | S keşif | S doğrula | Z keşif | Z doğrula | yön | holdout ort. |")
    satir.append("|---|---|---|---|---|---|---|")
    adaylar = []
    for k, etiket, s in sonuc:
        sS_tr, sS_te, sZ_tr, sZ_te = s[0], s[1], s[2], s[3]
        if not all(np.isfinite(v) for v in (sS_tr, sS_te, sZ_tr, sZ_te)):
            continue
        yon = np.sign(sS_tr - 0.5)
        tutarli = (np.sign(sS_te - 0.5) == yon == np.sign(sZ_tr - 0.5) == np.sign(sZ_te - 0.5))
        guc_min = min(abs(sS_tr - 0.5), abs(sS_te - 0.5), abs(sZ_tr - 0.5), abs(sZ_te - 0.5))
        if tutarli and guc_min >= 0.008:
            tut = (sS_te + sZ_te) / 2
            adaylar.append((k, etiket, yon, tut, guc_min))
            satir.append(f"| {etiket} | {sS_tr:.3f} | {sS_te:.3f} | {sZ_tr:.3f} | {sZ_te:.3f} | "
                         f"{'yüksek=iyi' if yon>0 else 'düşük=iyi'} | {tut:.3f} |")
    if not adaylar:
        satir.append("| — | — | — | — | — | — | — |")

    # --- iyi/kötü profil: standardize fark (Cohen d), keşifte seç doğrulamada bak
    satir.append("\n## İyi formasyonlar kötülerden neyle ayrılıyor? (Cohen d)\n")
    satir.append("d > 0: devam edenlerde daha yüksek. Keşif = S keşif, Doğrulama = Z doğrulama.\n")
    satir.append("| değişken | d (S keşif) | d (Z doğrulama) | işaret tutuyor |")
    satir.append("|---|---|---|---|")
    tr, te = b["S"]
    tz = b["Z"][1]
    for k, etiket in ADAYLAR:
        if k not in d or d[k].notna().sum() < 500:
            continue
        def cohen(x: pd.DataFrame) -> float:
            g = x[[k, "y"]].dropna()
            if len(g) < 100 or g.y.nunique() < 2:
                return float("nan")
            a = g[g.y == 1][k]
            c = g[g.y == 0][k]
            sp = np.sqrt((a.var() + c.var()) / 2)
            return float((a.mean() - c.mean()) / sp) if sp > 0 else float("nan")
        ds, dz = cohen(tr), cohen(tz)
        if not (np.isfinite(ds) and np.isfinite(dz)):
            continue
        satir.append(f"| {etiket} | {ds:+.3f} | {dz:+.3f} | "
                     f"{'evet' if np.sign(ds)==np.sign(dz) and abs(dz)>0.02 else 'hayır'} |")

    # --- eşik etkisi: aynı sayıda bildirimde devam oranı
    satir.append("\n## Ürün sınavı: aynı sayıda bildirimde devam oranı\n")
    satir.append("En iyi %50'lik dilim seçildiğinde (keşifte kesme noktası belirlenir, "
                 "doğrulamada uygulanır):\n")
    satir.append("| değişken | keşif kesme | doğrulama kapsam | doğrulama devam | taban | fark |")
    satir.append("|---|---|---|---|---|---|")
    for k, etiket, yon, tut, _g in adaylar[:6]:
        tr, te = b["S"]
        kes = tr[k].median()
        sec = te[te[k] >= kes] if yon > 0 else te[te[k] <= kes]
        if len(sec) < 100:
            continue
        satir.append(f"| {etiket} | {kes:.3g} | %{len(sec)/len(te)*100:.0f} | "
                     f"%{sec.y.mean()*100:.1f} | %{te.y.mean()*100:.1f} | "
                     f"{(sec.y.mean()-te.y.mean())*100:+.1f} puan |")

    metin = "\n".join(satir)
    print(metin)
    p = Path(args.rapor)
    if not p.is_absolute():
        p = REPO / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(metin, encoding="utf-8")
    print(f"\nRapor: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
