# -*- coding: utf-8 -*-
"""`scripts/grafik_ok_ve_etiket_olcum.py` ölçüm aracının sözleşmesi.

Neden test: araç canlı çizim yolunu (`grafik.ciz`) ölçtüğü için sessizce çürürse
"işaret çakışması yok" gibi yanlış bir güvence verir. Burada iki şey kilitleniyor:
(1) uçtan uca koşu sayı üretiyor, (2) `Figure.savefig` yaması kapsam dışına sızmıyor.
"""
from __future__ import annotations

from matplotlib.figure import Figure

from scripts.grafik_ok_ve_etiket_olcum import VARSAYILAN_VAKA, figur_yakala, main


def test_olcum_uctan_uca_sayi_uretir(capsys):
    """Gerçek arşiv + gerçek motor: satır ve TOPLAM çıktısı; işaret varsa geometri ölçülür."""
    assert any(s == "VAKBN" and tf == "1d" for s, tf in VARSAYILAN_VAKA)
    assert main(["--pencere", "120", "--sembol", "VAKBN"]) == 0
    cikti = capsys.readouterr().out
    assert "VAKBN" in cikti and "TOPLAM kare=1" in cikti
    # VAKBN 1G/120'de ok var (replay kademesi + bağlam halkası); kendi mumuna değmemeli.
    assert "işaret= " in cikti or "işaret=" in cikti
    assert "kendi= 0" in cikti or "kendi_mumu=0" in cikti


def test_figur_yamasi_kapsam_disina_sizmaz():
    """Yama yalnız `figur_yakala()` içinde yaşar: içe aktarma global çizimi bozmaz."""
    onceki = Figure.savefig
    with figur_yakala() as yakalanan:
        assert Figure.savefig is not onceki
        assert yakalanan == {"fig": None}
    assert Figure.savefig is onceki
