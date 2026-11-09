"""Sağ şerit: metin kesilmez, rol ve fiyat bağı korunur."""
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import pytest
import grafik
from grafik.panels import _sag_metni_sar


def axes():
    fig = Figure(figsize=(10.8,8.1),dpi=100)
    FigureCanvasAgg(fig)
    ax = fig.add_axes([.075,.1,.75,.8])
    ax.set_xlim(-.5,60)
    ax.set_ylim(90,120)
    return fig, ax


@pytest.mark.parametrize('scale', [1.0, 1.35])
def test_long_label_wraps_without_ellipsis_and_fits(scale):
    text='kritik 123456789,98 · CHoCH · uzun_açıklama_bilgisi'
    with grafik._mod_kapsami({'yazi_olcek':scale}):
        wrapped = _sag_metni_sar(text, 144)
        assert '…' not in wrapped
        assert ''.join(wrapped.split()) == ''.join(text.split())
        assert all(grafik._olcu_px(line, grafik.SABITLER['sag_serit_yazi_pt']) <= 144
                   for line in wrapped.splitlines())


def test_merged_labels_keep_every_original_part_without_ellipsis():
    fig,ax=axes()
    chips=[{'kaynak':'zone','y':100+i*.02,'metin':text,'renk':'#abcdef', 'oncelik':2}
           for i,text in enumerate(['OB↑ dolum %10','OB↑ dolum %10','FVG↓ aktif'])]
    result=grafik._sag_ciz(ax,fig,chips,60,(90,120))
    assert result['birlesik']==1 and result['atlanan']==0
    label=ax.texts[-1].get_text().replace('\n',' ')
    assert label.count('OB↑ dolum %10')==2 and 'FVG↓ aktif' in label and '…' not in label


def test_support_and_resistance_have_coloured_outlines_and_last_price_filled():
    fig,ax=axes()
    chips=[{'kaynak':'stabil','y':95,'metin':'Destek 95,00','renk':'#00bb88','bg':'#111922'},
           {'kaynak':'stabil_direnc','y':115,'metin':'Direnç 115,00','renk':'#dd8844','bg':'#111922'},
           {'kaynak':'son','y':105,'metin':'105,00','renk':'#111111','bg':'#00bb88','sabit':True}]
    res=grafik._sag_ciz(ax,fig,chips,60,(90,120))
    assert res['atlanan']==0
    fig.canvas.draw()
    assert len(ax.texts)==3
    for a in ax.texts:
        assert a.get_bbox_patch() is not None
    assert ax.texts[0].get_bbox_patch().get_facecolor() != ax.texts[1].get_bbox_patch().get_facecolor()
