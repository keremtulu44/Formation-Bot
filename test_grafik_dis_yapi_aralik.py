"""No internal graphics; complete, non-merging OB/FVG price range chips."""
from copy import deepcopy

import pytest
import grafik
from test_grafik_gorsel4 import _bolge, _eksen
from test_grafik_iskelet import _goruntu


@pytest.mark.parametrize("header,expected", [
    ("4s yapı: dış ↓geçiş · iç ↑trend", "4s yapı: dış ↓geçiş"),
    ("4s yapı: iç ↑trend", ""), ("CHoCH ↑ 72,20 · iç", ""),
    ("CHoCH ↑ 72,20 · dış+iç", "CHoCH ↑ 72,20 · dış"),
])
def test_internal_scope_is_removed_from_legacy_headers(header, expected):
    assert grafik._grafik_yapi_metni(header) == expected


def test_legacy_internal_does_not_affect_axis_labels_legend_or_metadata(tmp_path):
    snapshot = _goruntu()
    snapshot["yapı_satırı"] = "1s yapı: iç ↑trend"
    snapshot["olay"] = {"swinglar": [{"bar": 20, "fiyat": 9999., "yon": "ust",
        "sinif": "HH", "durum": "teyitli"}], "olaylar": [], "seviyeler": [],
        "cizilen": 1, "kapak": {"swing": 10}}
    before = deepcopy(snapshot)
    path, meta = grafik.ciz(snapshot, "1h", {"cikti": str(tmp_path / "external.png")})
    assert path
    assert meta["olay"]["swing"] == 0 and meta["olay"]["cizilen"] == 0
    assert meta["kare"]["y_araligi"][1] < 9999
    text = str(meta.get("metin") or {})
    assert "iç " not in text and "HH" not in text
    assert snapshot == before


@pytest.mark.parametrize("kind", ["ob", "fvg"])
def test_range_chip_is_always_created_even_when_inside_title_fits(kind):
    fig, ax = _eksen()
    zone = {"cizilen": [_bolge(tip=kind, alt=100.25, ust=102.75, doluluk=0.4)]}
    right = []
    summary = grafik._zone_ciz(ax, zone, 60, (90, 115), right)
    assert summary["ic"] == 1
    assert len(right) == 1 and right[0]["fiyat_araligi"] == (100.25, 102.75)
    assert "100,25–102,75" in right[0]["metin"]
    grafik._sag_ciz(ax, fig, right, 60, (90, 115))
    assert any("100,25–102,75" in t.get_text() for t in ax.texts)


def test_distinct_nearby_ranges_do_not_merge_or_get_capped():
    fig, ax = _eksen()
    zone = {"cizilen": [_bolge(tip="ob" if i % 2 else "fvg", alt=100+i*.1,
                              ust=101+i*.1) for i in range(6)]}
    candidates = grafik._zone_sag_adaylari(zone, 60)
    assert grafik._sag_ele(candidates, 100.5) == {}
    result = grafik._sag_ciz(ax, fig, candidates, 60, (90, 115))
    assert result["birlesik"] == 0 and result["yerlesen"] == 6
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    FigureCanvasAgg(fig)
    fig.canvas.draw()
    boxes = [t.get_bbox_patch().get_window_extent(fig.canvas.get_renderer()) for t in ax.texts]
    for i, first in enumerate(boxes):
        assert all(not first.overlaps(second) for second in boxes[i+1:])


def test_large_range_wraps_without_losing_either_bound():
    fig, ax = _eksen(alt=10000, ust=20000)
    candidates = grafik._zone_sag_adaylari({"cizilen": [
        _bolge(alt=12345.67, ust=18901.23)]}, 60)
    result = grafik._sag_ciz(ax, fig, candidates, 60, (10000, 20000))
    assert result["yerlesen"] == 1
    label = ax.texts[-1].get_text()
    assert grafik.sayi(12345.67) in label and grafik.sayi(18901.23) in label and "…" not in label
