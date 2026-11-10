# -*- coding: utf-8 -*-
"""Faz 3 — gölge zincir uçtan uca duman testi (gerçek arşiv, 1 seri).

Koşum yavaş olduğu için tek sembol × tek TF; üretim koşusu `research/golge_zincir.py`.
Doğrular: uçtan uca defter yazılır, saatler 1970'e düşmez, tipler şemada,
hata yok, plan/sonuç kayıtları şema uyumlu.
"""

import json

import pytest

from senaryo.defter import GolgeDefter
from senaryo.modeller import KAYIT_TIPLERI


@pytest.mark.slow
def test_golge_zincir_ucus_duman(tmp_path, capsys):
    from research.golge_zincir import main

    cikti = tmp_path / "golge"
    rc = main(["--semboller", "AEFES", "--tf", "4h", "--cikti", str(cikti)])
    assert rc == 0

    ozet = json.loads((cikti / "ozet.json").read_text(encoding="utf-8"))
    assert ozet["seri_sayisi"] == 1
    assert ozet["hata_sayisi"] == 0, ozet["hatalar"][:3]

    kayitlar, bozuk = GolgeDefter.oku(cikti / "golge_defter.jsonl")
    assert bozuk == 0
    assert len(kayitlar) > 100                      # bildirim+hukum akışı var
    assert all(k["tip"] in KAYIT_TIPLERI for k in kayitlar)

    # saatler gerçek bar zamanı (1970'e düşme yasağı)
    for k in kayitlar[:500]:
        assert k["t"].startswith("20"), k["t"]

    # en az bir hüküm yazıldı; UYGUN varsa plan/sonuç zinciri şema uyumlu
    hukumler = [k for k in kayitlar if k["tip"] == "hukum"]
    assert hukumler
    planlar = [k for k in kayitlar if k["tip"] == "plan"]
    for p in planlar:
        assert p["stop"] < p["giris"] < p["hedef"]
        assert p["R"] >= 1.2
        assert p["bilinmeyenler"]
        assert p["donem"] in ("kesif", "dogrulama")
    sonuclar = [k for k in kayitlar if k["tip"] == "sonuc"]
    plan_ids = {p["plan_id"] for p in planlar}
    assert all(s["plan_id"] in plan_ids for s in sonuclar)
    assert all(s["sonuc"] in ("hedef", "stop", "yok", "zaman") for s in sonuclar)
