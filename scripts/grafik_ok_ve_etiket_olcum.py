# -*- coding: utf-8 -*-
"""Stabil ok işaretleri + eksen yazıları için piksel ölçümü (2026-11-16 incelemesi).

Neden: `grafik` katmanının kendi kalite kapısı (`_mum_cakisma_say`) YALNIZ yazıları
ölçer; `▲`/`○` işaretleri `PathCollection` olduğu için kapıya hiç girmez. Yeni ok
kademeleri (boyut/dolgu/halka) bu yüzden ölçüsüz kaldı. Bu betik boşluğu kapatır:

* her işaretin piksel yarıçapını `s` (pt²) → px çevirisiyle hesaplar,
* işaretin kendi mumuyla ve KOMŞU mumlarla temasını ayrı ayrı sayar,
* işaretin ait olduğu mumun dibine dikey mesafesini ölçer,
* x ekseni tarih etiketlerinin birbiriyle çakışmasını sayar.

Girdi: yerel `backfill_data/` arşivi (ağ yok). Çıktı: satır başına bir sembol/TF.
Kare üretimi `grafik.ciz` üzerinden gider — yani ÖLÇÜLEN ŞEY canlı yolun kendisi.

Kullanım:
    python -m scripts.grafik_ok_ve_etiket_olcum
    python -m scripts.grafik_ok_ve_etiket_olcum --pencere 120 --png-dizin /tmp/kareler
"""

from __future__ import annotations

import argparse
import contextlib
import math
import os
from types import SimpleNamespace

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

import grafik
from domain_engines.stabil import (
    build_single_pass_history,
    evaluate_bar_behaviors,
    project_support_to_bar_closes,
)
from grafik.tarama import _stabil_verisi
from research.arsiv import tf_frame

# Ölçüm için seçilmiş sembol/TF/kadraj üçlüleri: birden çok kademe ve bağlam
# sınıfı aynı tabloda görünsün diye (VAKBN 1G: güçlü + zayıf + süpürme;
# TURSG: boş ok tabanı; TTKOM 1G: eksen etiketi çakışması gözlenen kare).
VARSAYILAN_VAKA = (
    ("VAKBN", "1d"), ("TURSG", "1d"), ("ULKER", "1d"), ("TTKOM", "1d"),
    ("GARAN", "1d"), ("AKBNK", "1d"), ("EREGL", "1d"),
    ("TTKOM", "4h"), ("TUPRS", "4h"), ("TURSG", "4h"), ("XU100", "4h"), ("SISE", "4h"),
)

_AYAR = {"fig": None}


@contextlib.contextmanager
def figur_yakala():
    """`grafik.ciz` diske yazarken figürü elimizde tutar (ölçüm için).

    Yama YALNIZ bu kapsam içinde yaşar: betik içe aktarıldığında global
    `Figure.savefig` değişmez (başka bir testin çizimini bozmaz).
    """
    orijinal = Figure.savefig

    def kaydet_ve_yakala(self, *args, **kwargs):
        _AYAR["fig"] = self
        return orijinal(self, *args, **kwargs)

    _AYAR["fig"] = None          # her kapsam kendi figürünü yakalar (önceki kalmasın)
    Figure.savefig = kaydet_ve_yakala
    try:
        yield _AYAR
    finally:
        Figure.savefig = orijinal


def goruntu_uret(sembol: str, tf: str, pencere: int) -> dict:
    """Gerçek arşivden mum + gerçek motor çıktısından stabil katmanı üretir."""
    hist = build_single_pass_history(sembol, tf_frame(sembol, "1d"), tf_frame(sembol, "4h"))
    frame = hist.daily_frame if tf == "1d" else hist.h4_frame
    zamanlar_ts = hist.daily_close_times if tf == "1d" else hist.h4_close_times
    projeksiyon = project_support_to_bar_closes(zamanlar_ts, hist.support_timeline)
    davranislar = list(evaluate_bar_behaviors(sembol, tf, frame, projeksiyon,
                                             hist.support_timeline))
    n = len(frame)
    sol = max(0, n - pencere)
    zamanlar = [t.to_pydatetime() if hasattr(t, "to_pydatetime") else t
                for t in zamanlar_ts[sol:n]]
    stabil = _stabil_verisi(
        {"stabil": SimpleNamespace(error=None, skipped=False, details={
            "bar_projection": projeksiyon[:n], "bar_behaviors": davranislar[:n]})},
        tf, sol, n, zamanlar)
    kesit = slice(sol, n)
    return {
        "sembol": sembol, "tf": tf, "tf_kisa": {"4h": "4S", "1d": "1G"}.get(tf, tf),
        "zamanlar": zamanlar,
        "acilis": [float(x) for x in frame["open"].to_numpy()[kesit]],
        "kapanis": [float(x) for x in frame["close"].to_numpy()[kesit]],
        "yuksek": [float(x) for x in frame["high"].to_numpy()[kesit]],
        "dusuk": [float(x) for x in frame["low"].to_numpy()[kesit]],
        "hacim": [float(x) for x in frame["volume"].to_numpy()[kesit]],
        "son_bar_ts": str(zamanlar_ts[n - 1]), "son_bar_kapali": True,
        "son_kapanis": float(frame["close"].to_numpy()[n - 1]),
        "zone": {}, "olay": {}, "formasyon": {}, "alarm": {}, "serit": {},
        "stabil": stabil,
    }


def mum_ekseni(fig):
    """Mumların çizildiği ekseni bulur (sağ şerit ayrı eksendir)."""
    for eksen in fig.axes:
        if any(str(c.get_gid() or "").startswith("grafik-stabil-step")
               for c in eksen.collections):
            return eksen
    return max(fig.axes, key=lambda e: len(e.patches))


def _kutu(eksen, listeler):
    arr = np.array([k for liste in listeler for k in liste], float)
    p0 = eksen.transData.transform(arr[:, 0:2])
    p1 = eksen.transData.transform(arr[:, 2:4])
    return np.hstack([np.minimum(p0, p1), np.maximum(p0, p1)])


def olc(fig, goruntu: dict) -> dict:
    """İşaret–mum teması, dikey mesafe ve eksen etiketi çakışmasını ölçer."""
    eksen = mum_ekseni(fig)
    dpi = float(fig.dpi)
    n = len(goruntu["kapanis"])
    govde_gen = 0.62  # SABITLER["mum_genislik_orani"]
    govde = [(i - govde_gen / 2, min(goruntu["acilis"][i], goruntu["kapanis"][i]),
              i + govde_gen / 2, max(goruntu["acilis"][i], goruntu["kapanis"][i]))
             for i in range(n)]
    fitil = [(i - 0.25, goruntu["dusuk"][i], i + 0.25, goruntu["yuksek"][i])
             for i in range(n)]
    mum = _kutu(eksen, (govde, fitil))
    sahip = np.array([i for i in range(n)] * 2)

    sonuc = {"isaret": 0, "kendi_temas": 0, "komsu_temas": 0, "dikey_px": [],
             "gid": {}, "x_etiket": 0, "x_etiket_cakisma": 0}
    for koleksiyon in eksen.collections:
        gid = str(koleksiyon.get_gid() or "")
        # step/stepline çizgi koleksiyonları işaret değildir; `get_sizes` yalnız
        # PathCollection'da vardır (scatter işaretleri).
        if not gid.startswith("grafik-stabil") or "step" in gid or not hasattr(koleksiyon, "get_sizes"):
            continue
        noktalar = np.asarray(koleksiyon.get_offsets(), float)
        if noktalar.size == 0 or noktalar.ndim != 2:
            continue
        yari_cap = (math.sqrt(float(np.atleast_1d(koleksiyon.get_sizes())[0])) / 2.0) * dpi / 72.0
        sonuc["gid"][gid] = len(noktalar)
        for bx, by in noktalar:
            sonuc["isaret"] += 1
            px, py = eksen.transData.transform((bx, by))
            temas = ((mum[:, 0] <= px + yari_cap) & (mum[:, 2] >= px - yari_cap)
                     & (mum[:, 1] <= py + yari_cap) & (mum[:, 3] >= py - yari_cap))
            bar = int(round(float(bx)))
            if temas.any():
                if bool(temas[sahip == bar].any()):
                    sonuc["kendi_temas"] += 1
                if bool(temas[sahip != bar].any()):
                    sonuc["komsu_temas"] += 1
            if 0 <= bar < n:
                dib = eksen.transData.transform((bar, goruntu["dusuk"][bar]))[1]
                sonuc["dikey_px"].append(abs(dib - py))

    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    olcu = canvas.get_renderer()
    etiketler = [t.get_window_extent(olcu)
                 for eksen_i in fig.axes for t in eksen_i.get_xticklabels()
                 if t.get_text().strip()]
    sonuc["x_etiket"] = len(etiketler)
    for i in range(len(etiketler)):
        for j in range(i + 1, len(etiketler)):
            b1, b2 = etiketler[i], etiketler[j]
            if (b1.x1 > b2.x0 + 0.5 and b2.x1 > b1.x0 + 0.5
                    and b1.y1 > b2.y0 + 0.5 and b2.y1 > b1.y0 + 0.5):
                sonuc["x_etiket_cakisma"] += 1
    sonuc["dikey_medyan_px"] = (round(float(np.median(sonuc["dikey_px"])), 1)
                                if sonuc["dikey_px"] else None)
    return sonuc


def main(argv: list[str] | None = None) -> int:
    ayar = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayar.add_argument("--pencere", type=int, default=200, help="karedeki mum sayısı (varsayılan 200)")
    ayar.add_argument("--png-dizin", default=None,
                      help="verilirse kareler bu dizine PNG olarak da yazılır")
    ayar.add_argument("--sembol", default=None,
                      help="yalnız bu sembolü ölç (varsayılan: seçilmiş 12 vaka)")
    secim = ayar.parse_args(argv)
    if secim.png_dizin:
        os.makedirs(secim.png_dizin, exist_ok=True)

    vakalar = [v for v in VARSAYILAN_VAKA if secim.sembol is None or v[0] == secim.sembol]
    toplam = {"isaret": 0, "kendi": 0, "komsu": 0, "cakisma": 0, "kare": 0}
    for sembol, tf in vakalar:
        goruntu = goruntu_uret(sembol, tf, secim.pencere)
        cikti = (os.path.join(secim.png_dizin, f"{sembol}_{tf}.png")
                 if secim.png_dizin else os.path.join("/tmp", f"olcum_{sembol}_{tf}.png"))
        with figur_yakala() as yakalanan:
            yol, meta = grafik.ciz(goruntu, tf, {"cikti": cikti})
            fig = yakalanan["fig"]
        if not yol or fig is None:
            print(f"{sembol:7s} {tf}: kare üretilemedi")
            continue
        o = olc(fig, goruntu)
        toplam["isaret"] += o["isaret"]
        toplam["kendi"] += o["kendi_temas"]
        toplam["komsu"] += o["komsu_temas"]
        toplam["cakisma"] += o["x_etiket_cakisma"]
        toplam["kare"] += 1
        print(f"{sembol:7s} {tf} işaret={o['isaret']:3d} kendi={o['kendi_temas']:2d} "
              f"komşu={o['komsu_temas']:2d} dikey_medyan={o['dikey_medyan_px']}px "
              f"x_etiket_çakışma={o['x_etiket_cakisma']}/{o['x_etiket']} "
              f"kademeler={o['gid']}")
        if not secim.png_dizin:
            try:
                os.remove(cikti)
            except OSError:
                pass
    print(f"TOPLAM kare={toplam['kare']} işaret={toplam['isaret']} "
          f"kendi_mumu={toplam['kendi']} komşu_mum={toplam['komsu']} "
          f"x_etiket_çakışma={toplam['cakisma']}")
    return 0


if __name__ == "__main__":  # pragma: no cover - ölçüm aracı
    raise SystemExit(main())
