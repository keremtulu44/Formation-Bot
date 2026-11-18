"""§15 HARİTA: giriş-anı özellikleri × plan sonuçları (karar değil, harita).

Özellikler (§15.1,3 ile kilitli): mesafe_atr · hukum_yasi · son_ok_yasi.
Kovalar: sonuç-kör çeyrekler (özellik değeriyle, pnl'ye bakılmadan).
Okuma kuralı: §15.3 (≥15pp + her iki dönem aynı yön) — kapı değil.

Kullanım:
    PYTHONPATH=. python research/harita_giris_zamanlama.py \
        [--plan <csv>] [--defter <jsonl>] [--cikti <dir>]
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import sys
import time
from pathlib import Path

import pandas as pd

from data import resample_ohlcv
from domain_engines.stabil.runtime import evaluate_stabil_symbol
from research.stabil_ok_denetimi import denetle

ROOT = Path(__file__).resolve().parents[1]
VARSAYILAN_PLAN = (ROOT / "docs/arastirma/sonuclar/golge_zincir/"
                   "faz9d_baz_176/olcum/plan_sonuc.csv")
VARSAYILAN_DEFTER = (ROOT / "docs/arastirma/sonuclar/golge_zincir/"
                     "faz9d_baz_176/golge_defter.jsonl")
VARSAYILAN_CIKTI = (ROOT / "docs/arastirma/sonuclar/golge_zincir/"
                    "harita_giris_zamanlama")
OK_KURALLARI = ("K1", "K2", "U1")  # §15.1 (M1/M2 hariç)
OZELLIKLER = ("mesafe_atr", "hukum_yasi", "son_ok_yasi")


def _utc(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_convert("UTC") if t.tzinfo else t.tz_localize("UTC")


def sembol_verisi(sembol: str):
    """(dist_map, oklar, stamps) — tek evaluate geçişi."""
    d = (pd.read_csv(ROOT / f"backfill_data/{sembol}_1d.csv.gz",
                     compression="gzip", parse_dates=["bar_time"])
         .set_index("bar_time").reset_index()
         .rename(columns={"bar_time": "timestamp"}))
    h = (pd.read_csv(ROOT / f"backfill_data/{sembol}_1h.csv.gz",
                     compression="gzip", parse_dates=["bar_time"])
         .set_index("bar_time"))
    h4 = (resample_ohlcv(h, "4h").reset_index()
          .rename(columns={"bar_time": "timestamp"}))
    out = evaluate_stabil_symbol(sembol, "4h", h4,
                                 daily_frame=d, h4_frame=h4)
    dist_map: dict[pd.Timestamp, float] = {}
    for b in out.bar_behaviors:
        dist = getattr(b, "dist_atr", None)
        if dist is not None:
            dist_map[_utc(b.bar_close_time)] = float(dist)
    oklar = {_utc(k.bar_close_time) for k in denetle(out.bar_behaviors)
             if k.kural_adi in OK_KURALLARI}
    h2 = resample_ohlcv(h, "2h").reset_index()
    stamps = {
        "1h": sorted(_utc(t) for t in h.index),
        "2h": sorted(_utc(t) for t in h2["bar_time"]),
        "4h": sorted(_utc(t) for t in h4["timestamp"]),
        "1d": sorted(_utc(t) for t in d["timestamp"]),
    }
    return dist_map, oklar, stamps


def hukum_uygun_zamanlari(defter_yol: Path) -> dict[str, list[pd.Timestamp]]:
    """Defteri tek geçişte okur; UYGUN hukum değişimlerini sembole böler."""
    olaylar: dict[str, list[pd.Timestamp]] = {}
    son_sembol: str | None = None
    with open(defter_yol, encoding="utf-8") as f:
        for line in f:
            try:
                k = json.loads(line)
            except Exception:
                continue
            s = k.get("sembol") or son_sembol
            if s:
                son_sembol = s
            if k.get("tip") == "hukum" and k.get("hukum") == "UYGUN" and s:
                olaylar.setdefault(s, []).append(_utc(k["t"]))
    return {s: sorted(v) for s, v in olaylar.items()}


def en_yakin_indeks(seri: list[pd.Timestamp], t: pd.Timestamp) -> int | None:
    i = bisect.bisect_right(seri, t) - 1
    return i if i >= 0 else None


def ceyreklere_bol(degerler: list[float]) -> list[int]:
    """Sonuç-kör çeyrekler: eşit sıklık, konum bazlı (beraberlikler
    karar-sızırır: sıralama yalnız özellik değeri + orijinal sıra)."""
    n = len(degerler)
    if n == 0:
        return []
    sira = sorted(range(n), key=lambda i: (degerler[i], i))
    kova = [0] * n
    for poz, idx in enumerate(sira):
        kova[idx] = min(3, poz * 4 // n) + 1
    return kova


def tablo(df: pd.DataFrame, ozellik: str) -> list[dict]:
    satirlar = []
    alt = df.dropna(subset=[ozellik])
    for (kova, donem), g in alt.groupby(["kova_" + ozellik, "donem"]):
        n = len(g)
        kaz = int((g["pnl"] > 0).sum())
        kay = g[g["pnl"] < 0]["pnl"].sum()
        poz = g[g["pnl"] > 0]["pnl"].sum()
        satirlar.append({
            "ozellik": ozellik, "kova": int(kova), "donem": donem, "n": n,
            "karli_yuzde": round(100 * kaz / n, 1) if n else None,
            "stop_orani": round(100 * float((g["sonuc"] == "stop").sum()) / n, 1)
            if n else None,
            "net_atr": round(float(g["pnl"].sum()), 2),
            "PF": round(float(poz / abs(kay)), 2) if kay else None,
            "beklenti_atr": round(float(g["pnl"].mean()), 4) if n else None,
        })
    return satirlar


def sinyal_kontrolu(rapor: list[dict], ozellik: str) -> dict:
    """§15.3: her dönemde en iyi−en kötü ≥15pp VE Q4−Q1 yönü aynı."""
    sonuc = {"ozellik": ozellik}
    yonler = {}
    for donem in ("kesif", "dogrulama"):
        alt = [r for r in rapor if r["ozellik"] == ozellik
               and r["donem"] == donem and r["karli_yuzde"] is not None]
        if len(alt) < 4:
            sonuc[donem] = "yetersiz kova"
            continue
        deger = {r["kova"]: r["karli_yuzde"] for r in alt}
        en_iyi = max(deger.values())
        en_kotu = min(deger.values())
        fark = round(en_iyi - en_kotu, 1)
        q4_q1 = round(deger.get(4, 0) - deger.get(1, 0), 1)
        yonler[donem] = q4_q1
        sonuc[donem] = {"en_iyi_en_kotu_pp": fark, "Q4-Q1_pp": q4_q1}
    if all(isinstance(sonuc.get(d), dict) for d in ("kesif", "dogrulama")):
        esit_yon = (yonler["kesif"] > 0) == (yonler["dogrulama"] > 0)
        buyuk = all(sonuc[d]["en_iyi_en_kotu_pp"] >= 15.0
                    for d in ("kesif", "dogrulama"))
        sonuc["sinyal"] = bool(esit_yon and buyuk)
    else:
        sonuc["sinyal"] = None
    return sonuc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=str(VARSAYILAN_PLAN))
    ap.add_argument("--defter", default=str(VARSAYILAN_DEFTER))
    ap.add_argument("--cikti", default=str(VARSAYILAN_CIKTI))
    args = ap.parse_args()
    cikti = Path(args.cikti)
    cikti.mkdir(parents=True, exist_ok=True)

    planlar = list(csv.DictReader(open(args.plan, encoding="utf-8")))
    semboller = sorted({p["sembol"] for p in planlar})
    print(f"plan={len(planlar)} sembol={len(semboller)}", flush=True)

    uygun = hukum_uygun_zamanlari(Path(args.defter))
    print(f"UYGUN hukum olayı: {sum(len(v) for v in uygun.values())} "
          f"({len(uygun)} sembol)", flush=True)

    veri: dict[str, tuple] = {}
    t0 = time.time()
    for i, s in enumerate(semboller, 1):
        for _ in range(3):
            try:
                veri[s] = sembol_verisi(s)
                break
            except Exception as hata:
                veri[s] = ({}, set(), {})
                son_hata = hata
        else:
            print(f"  {s}: ATLANDI {son_hata!r}", flush=True)
        if i % 20 == 0:
            print(f"  {i}/{len(semboller)} · {time.time()-t0:.0f}s", flush=True)

    satirlar = []
    for p in planlar:
        dist_map, oklar, stamps = veri.get(p["sembol"], ({}, set(), {}))
        t = _utc(p["t"])
        seri = stamps.get(p["tf"], [])

        #1) mesafe_atr: girişten önceki son4h davranışı
        mesafe = None
        if dist_map:
            zamanlar = sorted(dist_map)
            j = bisect.bisect_right(zamanlar, t) - 1
            if j >= 0:
                mesafe = dist_map[zamanlar[j]]

        #2) hukum_yasi: son UYGUN değişiminden beri plan-TF bar sayısı
        hyasi = None
        olaylar = uygun.get(p["sembol"], [])
        if seri and olaylar:
            k = bisect.bisect_right(olaylar, t) - 1
            if k >= 0:
                i_t = en_yakin_indeks(seri, t)
                i_u = en_yakin_indeks(seri, olaylar[k])
                if i_t is not None and i_u is not None:
                    hyasi = float(i_t - i_u)

        #3) son_ok_yasi: en yakın K1/K2/U1'e mutlak bar mesafesi (plan TF)
        okyas = None
        if oklar and seri:
            i_t = en_yakin_indeks(seri, t)
            if i_t is not None:
                en_kucuk = None
                for o in oklar:
                    i_o = en_yakin_indeks(seri, o)
                    if i_o is None:
                        continue
                    f = abs(i_t - i_o)
                    en_kucuk = f if en_kucuk is None else min(en_kucuk, f)
                okyas = float(en_kucuk) if en_kucuk is not None else None

        satirlar.append({
            "plan_id": p["plan_id"], "sembol": p["sembol"], "tf": p["tf"],
            "donem": p["donem"], "sonuc": p["sonuc"],
            "pnl_atr": p["pnl_atr"],
            "mesafe_atr": mesafe, "hukum_yasi": hyasi, "son_ok_yasi": okyas,
        })

    df = pd.DataFrame(satirlar)
    df["pnl"] = df["pnl_atr"].astype(float)

    # sonuç-kör çeyrekler (özellik başına; NaN ayrı sayılır)
    dagilim = {}
    for oz in OZELLIKLER:
        dolu = df[oz].notna()
        degerler = [float(x) for x in df.loc[dolu, oz]]
        df.loc[dolu, "kova_" + oz] = ceyreklere_bol(degerler)
        sirali = sorted(degerler)
        dagilim[oz] = {
            "dolu": int(dolu.sum()), "bos": int((~dolu).sum()),
            "farkli_deger": len(set(degerler)),
            "min": sirali[0] if sirali else None,
            "medyan": sirali[len(sirali) // 2] if sirali else None,
            "maks": sirali[-1] if sirali else None,
        }
        print(f"{oz}: dolu={dagilim[oz]['dolu']} boş={dagilim[oz]['bos']} "
              f"farklı={dagilim[oz]['farkli_deger']} "
              f"medyan={dagilim[oz]['medyan']}")

    rapor: list[dict] = []
    for oz in OZELLIKLER:
        rapor.extend(tablo(df, oz))
    sinyaller = [sinyal_kontrolu(rapor, oz) for oz in OZELLIKLER]

    df.to_csv(cikti / "harita_plan_ozellik.csv", index=False)
    (cikti / "ozet.json").write_text(
        json.dumps({"dagilim": dagilim, "tablo": rapor, "sinyal": sinyaller},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    for oz in OZELLIKLER:
        print(f"\n=== {oz} ===")
        for r in [x for x in rapor if x["ozellik"] == oz]:
            print(f"  Q{r['kova']} {r['donem']:<10} n={r['n']:<4} "
                  f"kârlı%={r['karli_yuzde']} stop%={r['stop_orani']} "
                  f"net={r['net_atr']} PF={r['PF']}")
    print("\nSİNYALLER:", json.dumps(sinyaller, ensure_ascii=False))
    print(f"yazıldı: {cikti}/harita_plan_ozellik.csv, ozet.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
