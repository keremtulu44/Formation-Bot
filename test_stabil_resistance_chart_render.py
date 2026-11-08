"""Rendering and coexistence tests for the independent resistance overlay."""
from __future__ import annotations

import matplotlib.colors as colors
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

import grafik
from data import mum_kapanis_anlari, resample_ohlcv
from domain_engines.stabil.chart_bridge import resistance_for_chart
from grafik.core import _mod_kapsami
from grafik.render import _stabil_ciz, _stabil_direnc_ciz
from test_stabil_resistance_chart_bridge import _frames


def _ax():
    fig = Figure(figsize=(8, 5), dpi=100)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.set_xlim(-0.5, 5.5)
    ax.set_ylim(95, 105)
    return fig, ax


def _layer():
    return {"hazir": True, "durum": "READY", "neden": None,
            "seviyeler": [100, 100, 100.01, 100.01, 101, 101],
            "renkler": ["alt", "alt", "ust", "ust", "alt", "alt"],
            "donus_barlar": [2], "momentum_barlar": [3],
            "dikey_barlar": [4], "dikey_deneme_barlar": [4],
            "son_seviye": 101, "son_renk": "alt"}


def test_reverse_colors_distinct_dashed_line_and_all_arrow_shapes():
    _, ax = _ax()
    chips = []
    info = _stabil_direnc_ciz(ax, {"stabil_direnc": _layer()}, 6, (95, 105), kadrajda=True,
                               dusuk=[99] * 6, yuksek=[102] * 6, sag_adaylar=chips)
    assert info["cizildi"] and info["gorunur_bar"] == 6
    assert (info["donus_isaret"], info["momentum_isaret"], info["dikey_deneme_isaret"]) == (1, 1, 1)
    items = {c.get_gid(): c for c in ax.collections}
    line = items["grafik-stabil-direnc-stepline"]
    assert [colors.to_hex(c) for c in line.get_colors()] == [
        grafik.PALET["stabil_direnc"], grafik.PALET["stabil_direnc_kirik"], grafik.PALET["stabil_direnc"]
    ]
    assert line.get_linestyles()[0][1] is not None  # dashed, distinguishable from solid support
    assert len(items["grafik-stabil-direnc-donus"].get_facecolors()) == 1
    assert len(items["grafik-stabil-direnc-momentum"].get_facecolors()) == 0
    assert len(items["grafik-stabil-direnc-dikey-deneme"].get_facecolors()) == 0
    assert colors.to_hex(items["grafik-stabil-direnc-donus"].get_facecolors()[0]) == grafik.PALET["stabil_direnc"]
    assert colors.to_hex(items["grafik-stabil-direnc-dikey-deneme"].get_edgecolors()[0]) == grafik.PALET["stabil_direnc"]
    assert [(x["kaynak"], x["metin"]) for x in chips] == [("stabil_direnc", "Direnç 101,00")]


def test_step_is_not_a_new_vertical_signal_and_missing_bar_breaks_line():
    _, ax = _ax()
    layer = _layer()
    layer.update({"seviyeler": [100, 101, None, 102, 102, 102],
                  "renkler": ["alt", "alt", None, "ust", "ust", "ust"],
                  "donus_barlar": [1], "momentum_barlar": [], "dikey_barlar": [],
                  "dikey_deneme_barlar": []})
    info = _stabil_direnc_ciz(ax, {"stabil_direnc": layer}, 6, (95, 105),
                               dusuk=[99] * 6, yuksek=[103] * 6)
    assert info["donus_isaret"] == 1 and info["dikey_deneme_isaret"] == 0
    line = next(c for c in ax.collections if c.get_gid() == "grafik-stabil-direnc-stepline")
    assert len(line.get_segments()) == 3  # changed level + explicit missing bar split
    steps = next(c for c in ax.collections if c.get_gid() == "grafik-stabil-direnc-step")
    assert len(steps.get_segments()) == 1  # never connect across the missing bar


def test_both_layers_and_price_chips_coexist_even_at_same_price():
    _, ax = _ax()
    chips = []
    support = {"hazir": True, "seviyeler": [100] * 6, "renkler": ["ust"] * 6,
               "reclaim_barlar": [2], "momentum_barlar": [], "dikey_barlar": [],
               "dikey_deneme_barlar": [], "son_seviye": 100, "son_renk": "ust"}
    resistance = {**_layer(), "seviyeler": [100] * 6, "son_seviye": 100}
    _stabil_ciz(ax, {"stabil": support}, 6, (95, 105), kadrajda=True,
                dusuk=[99] * 6, yuksek=[101] * 6, sag_adaylar=chips)
    _stabil_direnc_ciz(ax, {"stabil_direnc": resistance}, 6, (95, 105), kadrajda=True,
                       dusuk=[99] * 6, yuksek=[101] * 6, sag_adaylar=chips)
    gids = {c.get_gid() for c in ax.collections}
    assert {"grafik-stabil-stepline", "grafik-stabil-direnc-stepline"}.issubset(gids)
    assert [c["kaynak"] for c in chips] == ["stabil", "stabil_direnc"]
    assert not grafik._sag_ele(chips, 100)  # one of each source, no silent quota elimination
    assert all(not x.get("elendi") for x in chips)


def test_colorblind_palette_and_no_stale_chip():
    _, ax = _ax()
    layer = _layer()
    layer["seviyeler"][-1] = None
    layer["renkler"][-1] = None
    chips = []
    with _mod_kapsami({"renk_korugu": True}):
        _stabil_direnc_ciz(ax, {"stabil_direnc": layer}, 6, (95, 105), kadrajda=True,
                           dusuk=[99] * 6, yuksek=[102] * 6, sag_adaylar=chips)
        line = next(c for c in ax.collections if c.get_gid() == "grafik-stabil-direnc-stepline")
        assert colors.to_hex(line.get_colors()[0]) == "#f5a05a"
        assert colors.to_hex(line.get_colors()[1]) == "#b45309"
    assert chips == []


def test_real_png_and_simple_mode_preserve_existing_chart(tmp_path):
    daily, hourly = _frames()
    target = resample_ohlcv(hourly, "4h")
    cutoff = mum_kapanis_anlari(target.index, "4h")[-1]
    result = resistance_for_chart("AKBNK", "4h", target, daily_frame=daily,
                                  hourly_frame=hourly, as_of_close=cutoff)
    snapshot = grafik.anlik_goruntu(None, "4h", target, sonuclar={"stabil_direnc": result},
                                     sembol="AKBNK", simdi=cutoff)
    path, meta = grafik.ciz(snapshot, "4h", secenekler={"cikti": str(tmp_path / "normal.png")})
    assert path and (tmp_path / "normal.png").stat().st_size > 10000
    assert meta["cizgiler"]["stabil_direnc"]["hazir"]
    assert meta["cizgiler"]["stabil_direnc"]["son_seviye"] == result.bar_projection[-1].resistance_level
    path, simple = grafik.ciz(snapshot, "4h", secenekler={"cikti": str(tmp_path / "simple.png"), "sade": True})
    assert path and simple["mod"]["sade"]
    assert not simple["cizgiler"]["stabil_direnc"]["cizildi"]


def test_legend_reports_only_visible_classifications():
    layer = _layer()
    summary = {"cizildi": True, "donus_isaret": 1, "momentum_isaret": 0, "dikey_deneme_isaret": 1}
    legend = grafik._lejant({"stabil_direnc": layer}, False, meta={"cizgiler": {"stabil_direnc": summary}})
    assert "┄ Stabil direnç" in legend
    assert "▼ direnç dönüşü (turuncu)" in legend
    assert "◇ direnç yapı uyarısı (turuncu)" in legend
    assert "▽ direnç momentumu (turuncu)" not in legend


def test_step_connector_colors_are_the_directional_mirror_of_support():
    _, ax = _ax()
    layer = _layer()
    layer.update({"seviyeler": [100, 101, 101, 100, 100, 100],
                  "renkler": ["alt"] * 6, "donus_barlar": [], "momentum_barlar": [],
                  "dikey_barlar": [], "dikey_deneme_barlar": []})
    _stabil_direnc_ciz(ax, {"stabil_direnc": layer}, 6, (95, 105), kadrajda=True)
    connector = next(c for c in ax.collections if c.get_gid() == "grafik-stabil-direnc-step")
    assert [colors.to_hex(c) for c in connector.get_colors()] == [
        grafik.PALET["stabil_direnc_kirik"], grafik.PALET["stabil_direnc"]
    ]
