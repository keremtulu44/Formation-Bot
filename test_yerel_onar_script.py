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


def test_termux_backfill_cikis_komutu_interaktif_oturumu_kapatmaz():
    """`exit 1` yalnızca `bash -s` alt kabuğunda olmalı; Termux kapanmamalı.

    2026-11-19: Kullanıcı Enter'a basınca oturumun kapandığını bildirdi. Sebep
    interaktif kabukta çalışan hata kontrolünün `exit 1` ile oturumun kendisini
    bitirmesiydi. Aktif kurulum dokümanı blokları `bash -s <<'SH' ... SH`
    sarmalına alındı; bu test sarmalın ve bash sözdiziminin korunmasını kilitler.
    """
    import re
    import subprocess

    metin = _metin("docs/kurulum/TERMUX_BACKFILL.md")
    bloklar = re.findall(r"```bash\n(.*?)\n```", metin, re.S)
    dis = re.sub(r"```bash\n(.*?)\n```", "", metin, flags=re.S)
    assert "exit 1" not in dis, "kod bloğu dışında interaktif çıkış komutu kaldı"

    sarmalilar = [b for b in bloklar if "bash -s <<'SH'" in b]
    assert sarmalilar, "güvenli alt kabuk sarmalı yok"
    for blok in bloklar:
        if "exit 1" in blok:
            assert "bash -s <<'SH'" in blok, "sarmalanmamış çıkış komutu var"
    for blok in sarmalilar:
        assert "\nSH\n" in blok or blok.endswith("\nSH"), "SH ayracı eksik"
        sonuc = subprocess.run(
            ["bash", "-n"], input=blok, text=True, capture_output=True, timeout=30
        )
        assert sonuc.returncode == 0, f"bash -n hatası: {sonuc.stderr[:300]}"
