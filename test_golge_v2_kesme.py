"""Gölge v2 anti-lookahead (prefix truncation) ve izolasyon denetim testleri."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from research.arsiv import tf_frame
from senaryo_v2.adaptor import seriyi_hazirla
from senaryo_v2.modeller import MAX_BEKLEME_LIMIT, UFUK_VARSAYILAN_BAR
from senaryo_v2.olaylar import aday_olaylari_cikar
from senaryo_v2.plan import plan_karti_olustur
from senaryo_v2.yaris import yarisi_yurut


@pytest.mark.parametrize("sembol,tf", [("AEFES", "4h"), ("AEFES", "1d"), ("THYAO", "4h"), ("THYAO", "1h")])
def test_gercek_arsivde_prefix_kesme_degismezligi(sembol: str, tf: str):
    """2026-04-01'de kesilen gerçek arşiv serisi ile tam seri birebir aynı bar/olay/plan üretmelidir."""
    cut = pd.Timestamp("2026-04-01", tz="Europe/Istanbul")
    d_full = tf_frame(sembol, "1d")
    t_full = tf_frame(sembol, tf)

    d_cut = d_full[d_full.index.tz_convert("Europe/Istanbul") < cut]
    t_cut = t_full[t_full.index.tz_convert("Europe/Istanbul") < cut]

    seri_full = seriyi_hazirla(sembol, tf, raw_frame=t_full, daily_raw=d_full, bloklari_yukle=True)
    seri_cut = seriyi_hazirla(sembol, tf, raw_frame=t_cut, daily_raw=d_cut, bloklari_yukle=True)

    assert not seri_full.r_hatali and not seri_full.ms_hatali and not seri_full.frm_hatali and not seri_full.vp_hatali
    assert not seri_cut.r_hatali and not seri_cut.ms_hatali and not seri_cut.frm_hatali and not seri_cut.vp_hatali
    assert len(seri_cut.barlar) > 50

    for b_cut, b_full in zip(seri_cut.barlar, seri_full.barlar[: len(seri_cut.barlar)]):
        assert b_cut == b_full, f"{sembol}/{tf} bar {b_cut.i} ({b_cut.bar_close_time}) farkli!"

    olay_full = [o for o in aday_olaylari_cikar(seri_full) if o.bar_index < len(seri_cut.barlar)]
    olay_cut = list(aday_olaylari_cikar(seri_cut))
    assert olay_cut == olay_full

    def _bar_olaylari(olaylar):
        harita: dict[int, list] = {}
        for o in olaylar:
            harita.setdefault(o.bar_index, []).append(o)
        return harita

    bo_cut, bo_full = _bar_olaylari(olay_cut), _bar_olaylari(aday_olaylari_cikar(seri_full))
    pencere = MAX_BEKLEME_LIMIT + UFUK_VARSAYILAN_BAR
    yarisan = 0
    for o_cut, o_full in zip(olay_cut, olay_full):
        for mod in ("mod0", "mod1", "mod2"):
            p_cut = plan_karti_olustur(o_cut, seri_cut.barlar[o_cut.bar_index], mod=mod)
            p_full = plan_karti_olustur(o_full, seri_full.barlar[o_full.bar_index], mod=mod)
            assert p_cut == p_full
            # Penceresi kesimden önce biten işlemde yarış ve işlem-içi süreç kaydı (gözlemler,
            # tez yolu, çıkışa kadar MFE/MAE) kesimden sonraki veriden etkilenmemelidir.
            if o_cut.bar_index + pencere < len(seri_cut.barlar):
                s_cut = yarisi_yurut(seri_cut, o_cut, p_cut, bar_olaylari=bo_cut)
                s_full = yarisi_yurut(seri_full, o_full, p_full, bar_olaylari=bo_full)
                assert s_cut == s_full, f"{sembol}/{tf} {o_cut.olay_id} {mod} yaris/surec farkli!"
                yarisan += 1
    assert yarisan > 0

    # Veri kopukluğu bayrağı da nedenseldir: kesik seride görülen kopukluklar tam seridekilerin önekidir.
    assert seri_cut.kopukluk_barlari == tuple(i for i in seri_full.kopukluk_barlari if i < len(seri_cut.barlar))


def test_ana_urun_ve_v1_izolasyon_temizligi():
    """Asıl ürün klasörleri ve senaryo v1 kesinlikle senaryo_v2 içe aktarmamalıdır."""
    kok = Path(__file__).resolve().parent
    korunan = ("bot", "patterns", "grafik", "notifier", "domain_engines", "data", "analytics", "reporting", "transport", "senaryo")
    for klasor in korunan:
        d = kok / klasor
        if not d.exists():
            continue
        for py_path in d.rglob("*.py"):
            txt = py_path.read_text(encoding="utf-8", errors="ignore")
            assert "senaryo_v2" not in txt, f"Izolasyon ihlali: {py_path}"
