"""▲ oklarında denetim bayrakları gerçekten "kötü haber" mi? — replay ölçümü.

SORU (ölçümden ÖNCE sabitlendi)
------------------------------
K1/K2 (dolu ▲) oklarında `research/stabil_ok_denetimi` bayraklarından hangisi
ileri getiriyi **anlamlı biçimde bozuyor**? Bayrak sadece bir etiket mi, yoksa
kural mı olmalı?

KÜTLE
-----
Günlük (1d) grafik, `backfill_data/*_1d.csv.gz` içindeki TÜM semboller
(≥300 bar). Yalnız **dolu ▲** (close_reclaim + intrabar_sweep_reclaim).
Momentum (M1/M2) ve ◇/▼ bu ölçümün dışında.

ÖLÇÜT (birincil)
----------------
Giriş = okun barı kapanışı. Ufuk = 16 bar. Nedensel ATR14(bar).
İlk dokunma: kapanış ≥ giriş + 1 ATR → UP · kapanış ≤ giriş − 1 ATR → DOWN.
`yön isabeti` = UP / (UP + DOWN); çözülmeyenler (NEITHER) payı ayrıca raporlanır.

EŞİKLER (kilitli)
-----------------
Hücre kullanılabilir: nK ≥ 50 **ve** nD ≥ 20 (aksi hâlde "yetersiz-n", karar yok).
"Kötü haber" iddiası için: liftK ≤ −6 puan **ve** liftD ≤ −1 puan **ve**
her iki kümede tek taraflı Fisher p < 0,006 (8 bayrak → Bonferroni 0,05/8).

BÖLÜNME
-------
`sha256(sembol) % 10 < 6` → keşif, kalanı doğrulama (sözleşme §2.7 ile aynı).

REPLAY
------
    PYTHONPATH=. .venv/bin/python research/stabil_ok_bayrak_replay.py
    → /tmp/ok_bayrak_oklar.csv (her ok) · /tmp/ok_bayrak_ozet.csv (bayrak özeti)
"""
from __future__ import annotations

import glob
import hashlib
import math
import os
from collections import Counter

import numpy as np
import pandas as pd

from domain_engines.stabil.signals import _causal_atr14
from domain_engines.stabil.runtime import evaluate_stabil_symbol
from research.stabil_ok_denetimi import denetle

UFUK = 16
BAYRAKLAR = ("GOVDESIZ", "SESSIZ", "KADEME_ASAGI", "TEKRAR", "YORGUN", "UZAK",
             "REJIM_YOK", "ALTI_BOS")
ALFA = 0.006
LIMIT = int(os.environ.get("LIMIT", "0")) or None


def kesif(sembol: str) -> bool:
    return int(hashlib.sha256(sembol.encode()).hexdigest(), 16) % 10 < 6


def fisher_kucuk(a: int, n1: int, b: int, n2: int) -> float:
    """Tek taraflı: P(X ≤ a) — a = bayraklı grupta UP sayısı (hipergeometrik)."""
    toplam_up, toplam_n = a + b, n1 + n2
    if toplam_n == 0 or n1 == 0:
        return 1.0
    payda = math.comb(toplam_n, n1)
    p = 0.0
    for x in range(0, min(a, toplam_up) + 1):
        if toplam_up - x <= n2 and n1 - x <= n1:
            p += math.comb(toplam_up, x) * math.comb(toplam_n - toplam_up, n1 - x) / payda
    return min(1.0, p)


def main() -> int:
    dosyalar = sorted(glob.glob("backfill_data/*_1d.csv.gz"))
    if LIMIT:
        dosyalar = dosyalar[:LIMIT]
    satirlar = []
    atlanan = 0
    for yol in dosyalar:
        sembol = os.path.basename(yol).split("_")[0]
        try:
            d = (pd.read_csv(yol, compression="gzip", parse_dates=["bar_time"])
                 .set_index("bar_time").reset_index().rename(columns={"bar_time": "timestamp"}))
            if len(d) < 300:
                continue
            out = evaluate_stabil_symbol(sembol, "1d", d, daily_frame=d)
        except Exception:
            atlanan += 1
            continue
        if len(out.bar_behaviors) != len(d):
            atlanan += 1
            continue
        atr = _causal_atr14(d["high"].to_numpy(float), d["low"].to_numpy(float),
                            d["close"].to_numpy(float), period=14)
        kapanis = d["close"].to_numpy(float)
        n = len(d)
        for k in denetle(out.bar_behaviors):
            if k.ok != "▲" or k.kural_adi not in {"K1", "K2"}:
                continue
            i = k.bar_index
            if i + 1 >= n or not np.isfinite(atr[i]) or atr[i] <= 0:
                continue
            giris, birim = kapanis[i], float(atr[i])
            sonuc, bar = "NEITHER", None
            for j in range(1, min(UFUK, n - i - 1) + 1):
                if kapanis[i + j] >= giris + birim:
                    sonuc, bar = "UP", j
                    break
                if kapanis[i + j] <= giris - birim:
                    sonuc, bar = "DOWN", j
                    break
            satirlar.append(dict(
                sembol=sembol, zaman=str(k.bar_close_time)[:16], kural=k.kural_adi,
                bolum="K" if kesif(sembol) else "D", sonuc=sonuc, bar=bar,
                mesafe=k.mesafe_atr, govde=k.govde_atr, rvol=k.rvol,
                **{b: (b in k.bayraklar) for b in BAYRAKLAR},
            ))
    df = pd.DataFrame(satirlar)
    df.to_csv("/tmp/ok_bayrak_oklar.csv", index=False)
    print(f"sembol {len(dosyalar) - atlanan}/{len(dosyalar)} · ok {len(df)} "
          f"· atlanan {atlanan}")

    ozet = []
    for bolum in ("K", "D"):
        alt = df[(df.bolum == bolum) & (df.sonuc != "NEITHER")]
        taban = 100 * (alt.sonuc == "UP").mean() if len(alt) else float("nan")
        print(f"\n[{bolum}] çözülen {len(alt)} · NEITHER %{100*(df[df.bolum==bolum].sonuc=='NEITHER').mean():.1f}"
              f" · TABAN UP %{taban:.1f}")
        for b in BAYRAKLAR:
            var = alt[alt[b]]
            yok = alt[~alt[b]]
            if len(var) == 0:
                continue
            up_v = int((var.sonuc == "UP").sum())
            up_y = int((yok.sonuc == "UP").sum())
            p = fisher_kucuk(up_v, len(var), up_y, len(yok))
            oran = 100 * up_v / len(var)
            ozet.append((b, bolum, len(var), oran, oran - taban, p))
    oz = pd.DataFrame(ozet, columns=["bayrak", "bolum", "n", "UP%", "lift", "p"])
    oz.to_csv("/tmp/ok_bayrak_ozet.csv", index=False)
    print("\n=== BAYRAK ÖZETİ (yalnız çözülen oklar) ===")
    for b in BAYRAKLAR:
        k = oz[(oz.bayrak == b) & (oz.bolum == "K")]
        d = oz[(oz.bayrak == b) & (oz.bolum == "D")]
        if k.empty:
            continue
        kk, dd = k.iloc[0], (d.iloc[0] if not d.empty else None)
        karar = "yetersiz-n"
        if kk.n >= 50 and dd is not None and dd.n >= 20:
            kotu = kk.lift <= -6 and dd.lift <= -1 and kk.p < ALFA and dd.p < ALFA
            karar = "KÖTÜ HABER" if kotu else "fark yok"
        print(f"{b:12s} nK={int(kk.n):4d} liftK={kk.lift:+5.1f} pK={kk.p:.4f} | "
              f"nD={int(dd.n) if dd is not None else 0:4d} "
              f"liftD={dd.lift:+5.1f} pD={dd.p:.4f} | {karar}" if dd is not None else
              f"{b:12s} nK={int(kk.n):4d} liftK={kk.lift:+5.1f} | doğrulamada yok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
