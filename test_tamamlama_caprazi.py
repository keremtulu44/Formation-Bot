"""Koşullu tamamlanma çaprazı testleri — `scripts/diagnostics/tamamlama_caprazi.py`.

Ölçüm betiği karar verir ("karta koşullu cümle yazılır mı"), bu yüzden
aritmetiği test edilir: Wilson aralığı, sağdan sansür dışlaması, aşım kovaları.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_YOL = Path(__file__).parent / "scripts" / "diagnostics" / "tamamlama_caprazi.py"
_spec = importlib.util.spec_from_file_location("tamamlama_caprazi", _YOL)
tc = importlib.util.module_from_spec(_spec)
sys.modules["tamamlama_caprazi"] = tc
_spec.loader.exec_module(tc)


def _kayit(tamam=True, ust=0.2, alt=0.2, asim=0.1, omur=13, bitis="TERMINAL"):
    return {
        "terminal_state": tc.TAMAM if tamam else "BASARISIZ_KIRILIM",
        "bitis_sebebi": bitis,
        "frm_yakinlik_ust_fitil_atr": ust,
        "frm_yakinlik_alt_fitil_atr": alt,
        "frm_asim_ust_fitil_atr": asim,
        "frm_asim_alt_fitil_atr": asim,
        "omur_bar": omur,
    }


def test_wilson_sinirlari():
    alt, ust = tc.wilson(50, 100)
    assert 39.0 < alt < 41.0 and 59.0 < ust < 61.0
    alt, ust = tc.wilson(0, 10)
    assert alt == 0.0 and ust > 20.0        # küçük n'de aralık geniş
    assert tc.wilson(0, 0)[0] != tc.wilson(0, 0)[0]      # NaN (n=0)


def test_acik_satirlar_dislanir(tmp_path):
    """`VERI_SONU` (henüz bitmemiş) satır 'tamamlanmadı' sayılmamalı."""
    yol = tmp_path / "frm.jsonl"
    satirlar = [_kayit(True), _kayit(False), _kayit(True, bitis="VERI_SONU")]
    yol.write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in satirlar))
    okunan, sayac = tc.satirlari_oku([tmp_path])
    assert len(okunan) == 2
    assert sayac["acik_veri_sonu"] == 1


def test_capraz_yaklasan_ve_yaklasmayan():
    satirlar = [_kayit(True, ust=0.1), _kayit(False, ust=0.2),
                _kayit(True, ust=3.0, alt=3.0), _kayit(False, ust=5.0, alt=5.0)]
    c = tc.capraz(satirlar, 0.5)
    assert c["yaklasan"]["n"] == 2 and c["yaklasan"]["tamam"] == 1
    assert c["yaklasan"]["oran_pct"] == 50.0
    assert c["yaklasmayan"]["n"] == 2 and c["yaklasmayan"]["tamam"] == 1


def test_capraz_olcusuz_satiri_atlar():
    kayit = _kayit(True)
    kayit["frm_yakinlik_ust_fitil_atr"] = None
    kayit["frm_yakinlik_alt_fitil_atr"] = None
    c = tc.capraz([kayit, _kayit(True, ust=0.1)], 0.5)
    assert c["yaklasan"]["n"] == 1            # ölçüsüz satır hiçbir gruba girmez


def test_asim_kovalari_toplami_korunur():
    satirlar = [_kayit(True, asim=0.1), _kayit(True, asim=0.3),
                _kayit(False, asim=0.7), _kayit(True, asim=1.5),
                _kayit(True, asim=3.0)]
    kovalar = tc.asim_caprazi(satirlar)
    assert sum(k["n"] for k in kovalar) == 5
    assert [k["n"] for k in kovalar] == [1, 1, 1, 1, 1]
    assert kovalar[-1]["oran_pct"] == 100.0
