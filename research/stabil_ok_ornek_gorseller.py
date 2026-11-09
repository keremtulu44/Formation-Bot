"""Destek + direnç katmanını BİRLİKTE çizen örnek görseller.

Neden ayrı bir üretici: `research/replay_egitim._soru_goruntusu` yalnız
`stabil` (destek) motorunu çalıştırıyor; canlı `/grafik` yolunda ayrıca
`resistance_for_chart` ile `stabil_direnc` ekleniyor. Bu yüzden replay
görsellerinde direnç katmanı hiç görünmüyordu. Burada iki katman da
hesaplanıp aynı kareye konuyor; çizim yine normal `grafik.ciz` hattından geçer.

Kullanım:
    PYTHONPATH=. .venv/bin/python research/stabil_ok_ornek_gorseller.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import grafik
import grafik_uret
from data import mum_kapanis_anlari
from domain_engines.runner import run_domain_engines, run_stabil_domain
from domain_engines.stabil.chart_bridge import resistance_for_chart
from research.arsiv import tf_frame
from research.replay_egitim import TFS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/gorseller/ok_duzeltme_2026_11_08"

#: (sembol, gün, kısa ad) — 10 farklı sembol, günlük grafik
ORNEKLER = (
    ("AEFES", "2025-09-19", "aefes_uzak_uyari"),
    ("AGHOL", "2025-04-01", "aghol_ust_uste"),
    ("AGROT", "2025-03-28", "agrot_uc_atr"),
    ("AKSEN", "2026-03-06", "aksen_tekrar"),
    ("SISE", "2026-10-02", "sise_kademe"),
    ("THYAO", "2026-09-21", "thyao_gun_ici"),
    ("CEMAS", "2026-08-06", "cemas_yogun"),
    ("ALARK", "2025-05-22", "alark_bes_bar"),
    ("GARAN", "2026-09-21", "garan_dikey"),
    ("AKBNK", "2026-03-23", "akbnk_geri_alim"),
)


def _kare(sembol: str, gun: str, tf: str = "1d") -> dict:
    frames = {t: tf_frame(sembol, t) for t in TFS}
    closes = {t: mum_kapanis_anlari(f.index, t).tz_convert("UTC") for t, f in frames.items()}
    hedef = pd.Timestamp(gun, tz="Europe/Istanbul").tz_convert("UTC")
    p = int(closes[tf].searchsorted(hedef, side="right") - 1)
    cutoff = closes[tf][p]
    history = frames[tf].iloc[max(0, p + 1 - 900):p + 1].copy(deep=True)
    candidate, state, warning = grafik_uret._formasyon_tara_ayrintili(history, tf)
    domains = run_domain_engines(sembol, tf, history, isolated=True)
    daily_history, h4_history, kesim = grafik_uret.stabil_baglami_arsivden(frames, cutoff)
    domains["stabil"] = run_stabil_domain(
        sembol, tf, history, daily_frame=daily_history, h4_frame=h4_history,
        as_of_close=kesim, isolated=True,
    )
    # Replay yolunda eksik olan katman:
    domains["stabil_direnc"] = resistance_for_chart(
        sembol, tf, history, daily_frame=daily_history, hourly_frame=h4_history, as_of_close=kesim,
    )
    snap = grafik.anlik_goruntu(
        candidate, tf, history, sonuclar=domains, sembol=sembol,
        simdi=cutoff.to_pydatetime(), veri_kaynagi="arşiv", tarihsel=True, etiket_detay=False,
    )
    if state and snap.get("formasyon"):
        snap["formasyon"]["state"] = state
    if warning:
        snap["uyarilar"] = list(snap.get("uyarilar") or []) + list(warning)
    return snap


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    kayitlar = []
    for sembol, gun, slug in ORNEKLER:
        try:
            snap = _kare(sembol, gun)
        except Exception as exc:  # noqa: BLE001
            print(f"{sembol} {gun}: HATA {type(exc).__name__}: {exc}")
            continue
        yol = OUT / f"ikikatman_{slug}.png"
        yazildi, meta = grafik.ciz(snap, "1d", secenekler={
            "cikti": str(yol), "etiket_detay": False, "serit": None,
        })
        ciz = (meta or {}).get("cizgiler") or {}
        d = ciz.get("stabil") or {}
        r = ciz.get("stabil_direnc") or {}
        print(f"{sembol} {gun}: destek={bool(d.get('cizildi'))} direnc={bool(r.get('cizildi'))} "
              f"| destek_ok={d.get('reclaim_isaret', 0)}+{d.get('momentum_isaret', 0)}+{d.get('dikey_deneme_isaret', 0)} "
              f"direnc_ok={r.get('donus_isaret', 0)}+{r.get('momentum_isaret', 0)}+{r.get('dikey_deneme_isaret', 0)}")
        kayitlar.append(dict(sembol=sembol, gun=gun, dosya=yol.name,
                             destek_cizildi=bool(d.get("cizildi")), direnc_cizildi=bool(r.get("cizildi"))))
    (OUT / "ikikatman_ornekler.json").write_text(
        json.dumps(kayitlar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(kayitlar)} görsel yazıldı -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
