"""Graph-only removal of engulfing; internal pivot interpretation is unchanged."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
import grafik
from test_grafik_gorsel4 import _bolge, _eksen
from test_grafik_iskelet import _goruntu


@pytest.mark.parametrize("tf", ["1h", "2h", "4h", "1d"])
def test_legacy_engulf_snapshot_does_not_render_label_or_legend(tf, tmp_path):
    snapshot = _goruntu(tf=tf)
    snapshot["zone"] = {"cizilen": [_bolge(tip="eng", alt=1500., ust=2000.)]}
    before = deepcopy(snapshot)
    assert grafik._zone_metni(snapshot["zone"]["cizilen"][0]) == ""
    assert not any("ENG" in line for line in grafik._lejant(snapshot, False))
    path, meta = grafik.ciz(snapshot, tf, {"cikti": str(tmp_path / "no-eng.png")})
    assert path
    assert meta["zone"]["cizilen"] == 0
    assert meta["zone"]["tip"]["eng"] == 0
    assert not any("ENG" in str(line) for line in (meta.get("metin") or {}).values())
    assert snapshot == before  # no mutation of engine/snapshot history


def test_no_patch_text_or_right_axis_chip_even_for_direct_legacy_renderer():
    _, ax = _eksen()
    right = []
    grafik._zone_ciz(ax, {"cizilen": [_bolge(tip="eng")]}, 60, (90, 115), right)
    assert not ax.patches and not ax.texts and not ax.lines
    assert not right


def test_internal_pivots_are_removed_from_graph_data_and_markers():
    # Confirmed later, but drawn on source_bar and price, not confirmation bar.
    high = SimpleNamespace(source_bar=25, confirm_bar=28, price=110., side="SIDE_HIGH",
                           swing_class="LH", state="SWING_CONFIRMED")
    low = SimpleNamespace(source_bar=30, confirm_bar=33, price=95., side="SIDE_LOW",
                          swing_class="HL", state="SWING_CONFIRMED")
    external = SimpleNamespace(source_bar=26, confirm_bar=29, price=112., side="SIDE_HIGH")
    result = {"market_structure": SimpleNamespace(details={
        "internal_swings": [high, low], "internal_candidates": [],
        "external_swings": [external]})}
    data = grafik._olay_verisi(result, 20, 40)
    assert data["swinglar"] == []
    _, ax = _eksen(n=20, alt=90, ust=115)
    grafik._olay_ciz(ax, {"olay": data}, 20)
    assert not [line for line in ax.lines if line.get_marker() in ("^", "v")]
    assert not ax.texts
