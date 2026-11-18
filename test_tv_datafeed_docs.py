# -*- coding: utf-8 -*-
"""TV/datafeed belgelerinin kodla çelişmemesi için statik sözleşmeler."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _metin(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_plan_uygulama_durumunu_ve_paket_gercegini_acik_yazar():
    metin = _metin("docs/tasarim/VERI_KAYNAGI_VE_TF_PLANI_2026-11-16.md")

    assert "Uygulama durumu (2026-11-18)" in metin
    assert "henüz uygulanmadı" in metin
    assert "tradingview-datafeed==2.1.1" in metin
    assert "rongardF/tvdatafeed@e6f6aaa7de43" in metin
    assert "tvDataFeed PyPI'de yok" not in metin
    assert "Adayda sıfır hacim" in metin


def test_yerel_kurulum_uretici_hattini_dogru_tarif_eder():
    metin = _metin("docs/kurulum/LOCAL_SETUP.md")

    assert "borsapy fallback" not in metin
    assert "python data.py" not in metin
    assert "python -m data" in metin
    assert "tradingview-datafeed==2.1.1" in metin
    assert "PyPI'de yok, git'ten kurulur" not in metin


def test_canli_requirements_yorumu_pypi_catallisini_bilir():
    for rel in ("requirements.txt", "requirements-deploy.txt"):
        metin = _metin(rel)
        assert "ADIYLA PyPI paketi yok" in metin
        assert "tradingview-datafeed==2.1.1" in metin
        assert "deploy bağımlılığı DEĞİLDİR" in metin or "canlı bağımlılık zincirine girmez" in metin
