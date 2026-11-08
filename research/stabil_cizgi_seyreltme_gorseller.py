"""◇ yapı uyarısı seyreltmesinin görseli: aynı kare, iki kod hâli.

`once`  → `HEAD` sürümü (zayıf ◇ soğuması 3 bar) — geçici modül kopyasıyla
`sonra` → çalışma ağacındaki kod (zayıf ◇ soğuması 20 bar)

▲ / momentum okları iki hâlde de AYNI olmalı; tek fark ◇ sayısıdır.

Kullanım:
    PYTHONPATH=. .venv/bin/python research/stabil_cizgi_seyreltme_gorseller.py once
    PYTHONPATH=. .venv/bin/python research/stabil_cizgi_seyreltme_gorseller.py sonra
    PYTHONPATH=. .venv/bin/python research/stabil_cizgi_seyreltme_gorseller.py karsilastir
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import grafik

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/gorseller/ok_cizgi_seyreltme_2026_11_08"
PKG = ROOT / "domain_engines/stabil"

#: (sembol, gün, kısa ad) — ◇ yoğunluğu yüksek bilinen kareler
ORNEKLER = (
    ("ALARK", "2025-05-22", "alark_yogun"),
    ("AGROT", "2025-03-28", "agrot_uc_atr"),
    ("AGHOL", "2025-04-01", "aghol_ust_uste"),
    ("CEMAS", "2026-08-06", "cemas_yogun"),
    ("AEFES", "2025-09-19", "aefes_uzak_uyari"),
)

_GECICI = (
    ("signals.py", "_signals_head_tmp.py"),
    ("resistance.py", "_resistance_head_tmp.py"),
)


def _head_kopyalari() -> list[Path]:
    yazilan: list[Path] = []
    for kaynak, hedef in _GECICI:
        metin = subprocess.run(
            ["git", "show", f"HEAD:domain_engines/stabil/{kaynak}"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
        yol = PKG / hedef
        yol.write_text(metin, encoding="utf-8")
        yazilan.append(yol)
    return yazilan


def _head_ile_calistir() -> None:
    import domain_engines.stabil.chart_bridge as bridge
    import domain_engines.stabil.signals as signals

    eski_signals = importlib.import_module("domain_engines.stabil._signals_head_tmp")
    eski_resistance = importlib.import_module("domain_engines.stabil._resistance_head_tmp")
    signals.evaluate_bar_behaviors = eski_signals.evaluate_bar_behaviors
    bridge.evaluate_stabil_resistance = eski_resistance.evaluate_stabil_resistance


def _kirp(resim):
    h, w = resim.shape[:2]
    return resim[int(h * 0.05):int(h * 0.95), int(w * 0.30):int(w * 0.82)]


def karsilastir() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt

    yazilan = 0
    for sembol, _gun, slug in ORNEKLER:
        once_yol = OUT / f"cizgi_once_{slug}.png"
        sonra_yol = OUT / f"cizgi_sonra_{slug}.png"
        if not (once_yol.exists() and sonra_yol.exists()):
            print(f"{slug}: eksik kare, atlandı")
            continue
        sekil, eksenler = plt.subplots(2, 1, figsize=(11.0, 12.4), facecolor="#0e1116")
        for eksen, yol, etiket, renk in (
            (eksenler[0], once_yol, "ÖNCE · ◇ her 3 barda bir tekrar", "#9aa7b4"),
            (eksenler[1], sonra_yol, "SONRA · ◇ 20 barda bir (~1 ay)", "#2cc98d"),
        ):
            eksen.imshow(_kirp(mpimg.imread(yol)))
            eksen.axis("off")
            eksen.set_title(etiket, color=renk, fontsize=15, pad=10, loc="left")
        sekil.suptitle(f"{sembol} — aynı kare, ▲ okları değişmedi", color="#e6edf3", fontsize=13)
        sekil.tight_layout()
        hedef = OUT / f"karsilastirma_cizgi_{slug}.png"
        sekil.savefig(hedef, dpi=115, facecolor="#0e1116")
        plt.close(sekil)
        print("yazıldı", hedef.name)
        yazilan += 1
    return 0 if yazilan else 1


def main() -> int:
    mod = (sys.argv[1] if len(sys.argv) > 1 else "sonra").strip().lower()
    if mod == "karsilastir":
        return karsilastir()
    if mod not in {"once", "sonra"}:
        raise SystemExit("kullanım: <once|sonra|karsilastir>")
    onek = f"cizgi_{mod}"
    OUT.mkdir(parents=True, exist_ok=True)

    gecici: list[Path] = []
    if mod == "once":
        gecici = _head_kopyalari()
        _head_ile_calistir()

    from research.stabil_ok_ornek_gorseller import _kare

    kayit = []
    try:
        for sembol, gun, slug in ORNEKLER:
            try:
                snap = _kare(sembol, gun)
            except Exception as exc:  # noqa: BLE001
                print(f"{sembol} {gun}: HATA {type(exc).__name__}: {exc}")
                continue
            yol = OUT / f"{onek}_{slug}.png"
            _, meta = grafik.ciz(snap, "1d", secenekler={
                "cikti": str(yol), "etiket_detay": False, "serit": None,
            })
            ciz = (meta or {}).get("cizgiler") or {}
            d = ciz.get("stabil") or {}
            r = ciz.get("stabil_direnc") or {}
            print(f"{sembol} {gun}: destek dolu={d.get('reclaim_isaret', 0)} "
                  f"momentum={d.get('momentum_isaret', 0)} ◇={d.get('dikey_deneme_isaret', 0)} | "
                  f"direnc dolu={r.get('donus_isaret', 0)} momentum={r.get('momentum_isaret', 0)} "
                  f"◇={r.get('dikey_deneme_isaret', 0)}")
            kayit.append(dict(sembol=sembol, gun=gun, dosya=yol.name,
                              destek_dolu=int(d.get("reclaim_isaret", 0)),
                              destek_momentum=int(d.get("momentum_isaret", 0)),
                              destek_cizgi=int(d.get("dikey_deneme_isaret", 0)),
                              direnc_cizgi=int(r.get("dikey_deneme_isaret", 0))))
    finally:
        for yol in gecici:
            os.remove(yol)
    (OUT / f"{onek}.json").write_text(json.dumps(kayit, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
    print(f"\n{len(kayit)} görsel -> {OUT} ({onek})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
