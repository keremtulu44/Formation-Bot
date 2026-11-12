# -*- coding: utf-8 -*-
"""FAZ9-C kalıcı boru-hattı kesme testi (dış denetim maddesi).

Çerçeve N'de kesilirse, kesim noktasından önceki tüm kayıtlar (bildirim,
hüküm, tetik, plan, sonuç) birebir aynı kalmalı. G1 (as-of geçmiş), G2 (as-of
diziler), G5 (as-of tepki/doluluk), MS, karsit (as-of onay) sayesinde
boru-hattı tam as-of olmalı.

2026-11-12 denetçi notu üzerine parametreldi: 3 sembol × 3 TF (arşiv
`backfill_data/` repo'da commit'lidir — temiz klon/CI dahil her yerde koşar).
"""

import json

import pytest

from domain_engines.stabil import build_single_pass_history
from research.arsiv import tf_frame
from research.golge_zincir import Sayac, seri_hazirla, seri_kosu
from senaryo.defter import GolgeDefter

KOMBOL = [(s, tf)
          for s in ("AEFES", "EREGL", "GARAN")
          for tf in ("1h", "4h", "1d")]


@pytest.mark.slow
@pytest.mark.parametrize("sembol,tf", KOMBOL)
def test_kesme_testi_kayitlar_degismez(tmp_path, sembol, tf):
    frame = tf_frame(sembol, tf)
    n = len(frame)
    N = int(n * 0.6)
    assert N > 100, f"seri kısa: {n} (<167 bar — kesim anlamsız)"
    import pandas as pd
    from directional_zone_replay import _normalize_frame
    kesim_idx = int(N * 0.7) - 1          # kesif payı: donem farkı da eşitlenir
    cutoff_t = pd.Timestamp(
        _normalize_frame(frame).at[kesim_idx, "timestamp"]
    ).isoformat()

    gunluk = tf_frame(sembol, "1d")
    h4 = tf_frame(sembol, "4h")
    hist = build_single_pass_history(sembol, gunluk, h4)

    def kos(cerceve: object, yol) -> list[dict]:
        hazir = seri_hazirla(sembol, tf, cerceve)
        sayac = Sayac()
        with GolgeDefter(yol) as defter:
            seri_kosu(hazir, hist, defter, sayac)
        kayitlar, bozuk = GolgeDefter.oku(yol)
        assert bozuk == 0
        return [k for k in kayitlar if str(k.get("t", "")) <= cutoff_t]

    tam = kos(frame, tmp_path / "tam.jsonl")
    kesilmis = kos(frame.iloc[:N], tmp_path / "kesim.jsonl")

    assert tam, "tam koşuda kayıt yok"
    a = [json.dumps(k, sort_keys=True, ensure_ascii=False, default=str) for k in tam]
    b = [json.dumps(k, sort_keys=True, ensure_ascii=False, default=str) for k in kesilmis]
    fark_var = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    assert len(a) == len(b), f"kayıt sayısı değişti: {len(a)} vs {len(b)}"
    assert not fark_var, (
        f"ilk fark index {fark_var[0]}:\nTAM: {a[fark_var[0]][:400]}\n"
        f"KESİM: {b[fark_var[0]][:400]}"
    )
