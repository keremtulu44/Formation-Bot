# -*- coding: utf-8 -*-
"""Faz 1 — gölge defter testleri (atomik yazım, şema doğrulama, bozuk satır)."""

import json

import pytest

from senaryo.defter import GolgeDefter
from senaryo.modeller import Bildirim, Hukum, IslemSonucu, PlanKaydi


def _bildirim(**tz) -> Bildirim:
    taban = dict(
        sembol="ASELS", tf="1h", t="2026-11-09T10:00:00+03:00",
        kim="ms", iddia="uyari", kosul="taze asagi BOS, yon uyumsuz",
        kaynak="ARASTIRMA_SONUCLARI MS devam · n=15947",
        gecerlilik_bar=5,
    )
    taban.update(tz)
    return Bildirim(**taban)


def test_yaz_oku_tur(tmp_path):
    yol = tmp_path / "golge_defter.jsonl"
    with GolgeDefter(yol) as d:
        d.yaz(_bildirim())
        d.yaz(Hukum(sembol="ASELS", tf="1h", t="2026-11-09T11:00:00+03:00",
                    hukum="BEKLE", lehte=1, celisi=1,
                    gerekce="G1 onaysiz, MS taze uyari suruyor"))
        d.yaz({"tip": "sessizlik", "sembol": "ASELS", "tf": "1h",
               "t": "2026-11-09T12:00:00+03:00", "not": "g1 pending"})
        sayac = d.sayac()
    kayitlar, bozuk = GolgeDefter.oku(yol)
    assert sayac == {"bildirim": 1, "hukum": 1, "sessizlik": 1}
    assert bozuk == 0
    assert len(kayitlar) == 3
    assert kayitlar[0]["kim"] == "ms"
    assert kayitlar[1]["satir"] == "BEKLE · 1 lehte · 1 celişki"


def test_tip_kumesi_disi_yazilmaz(tmp_path):
    yol = tmp_path / "d.jsonl"
    with GolgeDefter(yol) as d:
        with pytest.raises(ValueError, match="tip"):
            d.yaz({"tip": "sinyal", "sembol": "X"})
    kayitlar, _ = GolgeDefter.oku(yol)
    assert kayitlar == []


def test_kaynaksiz_bildirim_reddedilir(tmp_path):
    yol = tmp_path / "d.jsonl"
    with GolgeDefter(yol) as d:
        with pytest.raises(ValueError, match="n="):
            d.yaz(_bildirim(kaynak="ARASTIRMA_SONUCLARI — kanit yok"))
    assert GolgeDefter.oku(yol)[0] == []


def test_bozuk_satir_atlanir(tmp_path):
    yol = tmp_path / "d.jsonl"
    with GolgeDefter(yol) as d:
        d.yaz(_bildirim())
    with open(yol, encoding="utf-8") as fh:
        icerik = fh.read()
    with open(yol, "w", encoding="utf-8") as fh:
        fh.write("{bozuk json\n" + icerik + '{"tip":"tanimasiz"}\n')
    kayitlar, bozuk = GolgeDefter.oku(yol)
    assert bozuk == 2
    assert len(kayitlar) == 1


def test_bilinmeyensiz_plan_reddedilir():
    with pytest.raises(ValueError, match="bilinmeyenler"):
        PlanKaydi(
            plan_id="p1", sembol="ASELS", tf="1h", t="2026-11-09T10:00:00+03:00",
            yon="long", giris=100.0, band_lo=99.5, band_hi=100.2,
            stop=97.0, hedef=108.0, R=round((108 - 100) / (100 - 97), 4),
            bilinmeyenler=(),
        )


def test_plan_R_tutarsizligi_reddedilir():
    with pytest.raises(ValueError, match="R tutarsiz"):
        PlanKaydi(
            plan_id="p1", sembol="ASELS", tf="1h", t="2026-11-09T10:00:00+03:00",
            yon="long", giris=100.0, band_lo=99.5, band_hi=100.2,
            stop=97.0, hedef=108.0, R=9.9,
            bilinmeyenler=("direnç tepkisi ölçülmüş değil",),
        )


def test_hukum_sayac_negatif_reddedilir():
    with pytest.raises(ValueError):
        Hukum(sembol="X", tf="1h", t="2026-11-09T10:00:00+03:00",
              hukum="UYGUN", lehte=-1, celisi=0, gerekce="x")


def test_sonuc_sansurde_cozunme_bari_yok():
    with pytest.raises(ValueError, match="sansur"):
        IslemSonucu(plan_id="p1", sembol="X", tf="1h",
                    t="2026-11-09T10:00:00+03:00", sonuc="yok",
                    cozunme_bar=3)


def test_bildirim_sifat_icermez_kosul_zorunlu():
    with pytest.raises(ValueError, match="kosul"):
        _bildirim(kosul="  ")
    b = _bildirim()
    # alanlar ölçülü: iddia/kaynak/gecerlilik var; sıfat alanı yok
    d = b.to_dict()
    assert "sifat" not in d
    assert d["gecerlilik_bar"] == 5
    assert json.dumps(d, ensure_ascii=False)  # serileştirilebilir
