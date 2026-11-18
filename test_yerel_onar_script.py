# -*- coding: utf-8 -*-
"""Yerel onarım / aktif dal güvenliği için statik sözleşmeler."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ESKI_DAL = re.compile(r"arena/[0-9a-f]{8}-formation-bot")


def _metin(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8-sig")


def test_yerel_onar_aktif_dali_kullanir_ve_sabit_dal_icermez():
    metin = _metin("scripts/yerel_onar.ps1")

    assert not ESKI_DAL.search(metin), "onarım betiği eski oturum dalına sıfırlamamalı"
    assert 'git rev-parse --abbrev-ref HEAD' in metin
    assert 'git rev-list --count' in metin, "uzaktan ileride yerel commit korunmalı"
    assert 'reset --hard' in metin
    assert '--tanis-dene 0' in metin, "teşhis varsayılan olarak ağa çıkmamalı"


def test_aktif_kurulum_belgeleri_ve_script_sabit_dal_icermez():
    for rel in (
        "docs/kurulum/TERMUX_BACKFILL.md",
        "docs/kurulum/TERMUX_CAPRAZ_PIYASA.md",
        "scripts/operational/save_real_data.py",
    ):
        metin = _metin(rel)
        assert not ESKI_DAL.search(metin), f"{rel} eski Arena dalını öneriyor"
        assert "$DAL" in metin or "--show-current" in metin
