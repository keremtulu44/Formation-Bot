# -*- coding: utf-8 -*-
"""TV/datafeed belgelerinin kodla çelişmemesi için statik sözleşmeler."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _metin(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_plan_uygulama_durumunu_ve_paket_gercegini_acik_yazar():
    metin = _metin("docs/tasarim/VERI_KAYNAGI_VE_TF_PLANI_2026-11-16.md")

    assert "Uygulama durumu (2026-11-18" in metin
    assert "üretim `data/fetch.py` hattına uygulandı" in metin
    assert "henüz uygulanmadı" not in metin
    assert "tradingview-datafeed==2.1.1" in metin
    assert "rongardF/tvdatafeed@e6f6aaa7de43" in metin
    assert "tvDataFeed PyPI'de yok" not in metin
    assert "Adayda sıfır hacim" in metin
    assert "veri_saglayicilari" in metin


def test_yerel_kurulum_uretici_hattini_dogru_tarif_eder():
    metin = _metin("docs/kurulum/LOCAL_SETUP.md")

    assert "borsapy fallback" not in metin
    assert "python data.py" not in metin
    assert "python -m data" in metin
    assert "tradingview-datafeed==2.1.1" in metin
    assert "PyPI'de yok, git'ten kurulur" not in metin


def test_canli_requirements_tv_yedegini_pinler_ve_aciklar():
    """TV artık deploy zincirinde: iki requirements dosyası da aynı pinleri taşır."""
    for rel in ("requirements.txt", "requirements-deploy.txt"):
        metin = _metin(rel)
        assert "tradingview-datafeed==2.1.1" in metin
        assert "websocket-client==1.9.2" in metin
        assert "TV_YEDEK_AKTIF" in metin
        assert "PyPI paketi" in metin and ("YOK" in metin or "yok" in metin)
        assert "deploy bağımlılığı DEĞİLDİR" not in metin
        assert "canlı bağımlılık zincirine girmez" not in metin


def test_yerel_kurulum_tv_yedegini_uretim_hatti_olarak_anlatir():
    metin = _metin("docs/kurulum/LOCAL_SETUP.md")
    assert "Üretim canlı veri yolu değildir" not in metin
    assert "TV_YEDEK_AKTIF=1" in metin
    assert 'frame.attrs["veri_kaynagi"]' in metin
