"""Hacim kapısı değişikliğinin görseli: aynı kare, iki kod hâli.

Amaç: "hacim onayı kalkınca hangi ▲ geldi?" sorusunu grafikte göstermek.
Her kare için **aynı sembol/gün** kullanılır; tek fark oku üreten koddur:

* `once`  → `HEAD` sürümü (hacim kapısı açık), geçici kopya üzerinden çalışır
* `sonra` → çalışma ağacındaki kod (hacim kapısı kalkmış)

Örneklerin günü, yeni ▲ okunun **bir sonraki işlem günü**ne ayarlanmıştır; böylece
o bar kadrajın içinde (en sağda) görünür — `_kare` kesimden bir bar öncesine kadar çizer.

Kullanım:
    PYTHONPATH=. .venv/bin/python research/stabil_hacim_kapisi_gorseller.py once
    PYTHONPATH=. .venv/bin/python research/stabil_hacim_kapisi_gorseller.py sonra
    PYTHONPATH=. .venv/bin/python research/stabil_hacim_kapisi_gorseller.py karsilastir
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
OUT = ROOT / "docs/gorseller/ok_hacim_kapisi_2026_11_08"
PKG = ROOT / "domain_engines/stabil"

#: (sembol, gün, kısa ad) — gün = hacim kapısı kalkınca ▲ gelen barın SONRAKİ işlem günü
ORNEKLER = (
    ("AGHOL", "2025-01-17", "aghol_geri_alim"),
    ("ALARK", "2026-07-15", "alark_geri_alim"),
    ("CEMTS", "2025-03-26", "cemts_geri_alim"),
    ("AEFES", "2025-12-31", "aefes_supurme"),
    ("DOCO", "2026-03-18", "doco_geri_alim"),
)

_GECICI = (
    ("signals.py", "_signals_head_tmp.py"),
    ("resistance.py", "_resistance_head_tmp.py"),
)


def _head_kopyalari() -> list[Path]:
    """HEAD sürümünü paket içine geçici modül olarak yaz (göreli importlar çalışsın)."""
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
    """Üretim kodunu HEAD sürümüne çevir (süreç içinde, dosyaya dokunmadan)."""
    import domain_engines.stabil.chart_bridge as bridge
    import domain_engines.stabil.signals as signals

    eski_signals = importlib.import_module("domain_engines.stabil._signals_head_tmp")
    eski_resistance = importlib.import_module("domain_engines.stabil._resistance_head_tmp")
    signals.evaluate_bar_behaviors = eski_signals.evaluate_bar_behaviors
    bridge.evaluate_stabil_resistance = eski_resistance.evaluate_stabil_resistance


def _kirp(resim):
    """Grafiğin sağ kenarını (son ~20 bar) kırp: 1 okun farkı tam karede kayboluyor."""
    h, w = resim.shape[:2]
    return resim[int(h * 0.08):int(h * 0.94), int(w * 0.58):int(w * 0.82)]


def karsilastir() -> int:
    """`once` / `sonra` karelerini yan yana, sağ kenar büyütülmüş olarak birleştirir."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt

    yazilan = 0
    for sembol, _gun, slug in ORNEKLER:
        once_yol = OUT / f"hacim_once_{slug}.png"
        sonra_yol = OUT / f"hacim_sonra_{slug}.png"
        if not (once_yol.exists() and sonra_yol.exists()):
            print(f"{slug}: eksik kare, atlandı")
            continue
        sekil, eksenler = plt.subplots(1, 2, figsize=(12.4, 7.2), facecolor="#0e1116")
        for eksen, yol, etiket, renk in (
            (eksenler[0], once_yol, "ÖNCE · hacim şartı VAR", "#9aa7b4"),
            (eksenler[1], sonra_yol, "SONRA · hacim şartı YOK", "#2cc98d"),
        ):
            eksen.imshow(_kirp(mpimg.imread(yol)))
            eksen.axis("off")
            eksen.set_title(etiket, color=renk, fontsize=15, pad=10)
        sekil.suptitle(f"{sembol} — son barlar büyütülmüş", color="#e6edf3", fontsize=13)
        sekil.tight_layout()
        hedef = OUT / f"karsilastirma_{slug}.png"
        sekil.savefig(hedef, dpi=120, facecolor="#0e1116")
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
    onek = f"hacim_{mod}"
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
                  f"momentum={d.get('momentum_isaret', 0)} uyari={d.get('dikey_deneme_isaret', 0)} | "
                  f"direnc dolu={r.get('donus_isaret', 0)} momentum={r.get('momentum_isaret', 0)} "
                  f"uyari={r.get('dikey_deneme_isaret', 0)}")
            kayit.append(dict(sembol=sembol, gun=gun, dosya=yol.name,
                              destek_dolu=int(d.get("reclaim_isaret", 0)),
                              destek_momentum=int(d.get("momentum_isaret", 0)),
                              direnc_dolu=int(r.get("donus_isaret", 0))))
    finally:
        for yol in gecici:
            os.remove(yol)
    (OUT / f"{onek}.json").write_text(json.dumps(kayit, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
    print(f"\n{len(kayit)} görsel -> {OUT} ({onek})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
