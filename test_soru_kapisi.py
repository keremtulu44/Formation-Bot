# -*- coding: utf-8 -*-
"""Yayın kapısı (research/soru_kapisi): altın toplam, tutarlılık, kova."""
import json
from pathlib import Path

from research import soru_kapisi


def _yaz(dizin: Path, kategori: str, satirlar):
    (dizin / f"{kategori}.jsonl").write_text(
        "\n".join(json.dumps(s, ensure_ascii=False) for s in satirlar) + "\n",
        encoding="utf-8")


def _altin(tmp_path, **ek):
    golden = {k: 1 for k in soru_kapisi._KATEGORILER}
    golden_brentsiz = dict(golden)
    golden.update(ek)
    golden_brentsiz.update(ek)
    return golden, golden_brentsiz


def test_altin_toplam_gecer(tmp_path):
    for kategori in soru_kapisi._KATEGORILER:
        _yaz(tmp_path, kategori, [{"symbol": "TEST", "timeframe": "1h"}])
    golden, golden_brentsiz = _altin(tmp_path)
    assert soru_kapisi.altin_toplam_kontrol([str(tmp_path)], golden, golden_brentsiz) == []


def test_altin_toplam_fark(tmp_path):
    for kategori in soru_kapisi._KATEGORILER:
        _yaz(tmp_path, kategori, [{"symbol": "TEST"}])
    golden, golden_brentsiz = _altin(tmp_path, zone=2)  # zone için altın 2
    # yalnız BRENT'siz tarafı 1 kalmalı → hata
    hatalar = soru_kapisi.altin_toplam_kontrol([str(tmp_path)], golden, golden_brentsiz)
    assert any("BRENT'siz zone" in h for h in hatalar)


def test_brent_filtre(tmp_path):
    for kategori in soru_kapisi._KATEGORILER:
        _yaz(tmp_path, kategori, [{"symbol": "TEST"}, {"symbol": "BRENT"}])
    golden = {k: 2 for k in soru_kapisi._KATEGORILER}
    golden_brentsiz = {k: 1 for k in soru_kapisi._KATEGORILER}
    assert soru_kapisi.altin_toplam_kontrol([str(tmp_path)], golden, golden_brentsiz) == []
    # BRENT satırı sayılmasın diye değil — filtre doğru mu?
    assert soru_kapisi._sayaclar([str(tmp_path)], True)["zone"] == 1


def test_tutarlilik_gecer(tmp_path):
    _yaz(tmp_path, "meta", [
        {"symbol": "A", "timeframe": "1h", "formasyon_sayisi": 2},
        {"symbol": "B", "timeframe": "4h", "formasyon_sayisi": 1},
    ])
    _yaz(tmp_path, "frm", [
        {"terminal_state": "FORMASYON_TAMAMLANDI", "frm_faz_gecis_sayisi": 3},
        {"terminal_state": "FORMASYON_TAMAMLANDI", "frm_faz_gecis_sayisi": 5},
        {"terminal_state": "BASARISIZ_KIRILIM", "frm_faz_gecis_sayisi": 0},
    ])
    assert soru_kapisi.tutarlilik_kontrol([str(tmp_path)]) == []


def test_tutarlilik_s27_ve_toplam(tmp_path):
    _yaz(tmp_path, "meta", [
        {"symbol": "A", "timeframe": "1h", "formasyon_sayisi": 1},
    ])
    _yaz(tmp_path, "frm", [
        {"terminal_state": "FORMASYON_TAMAMLANDI", "frm_faz_gecis_sayisi": 3},
        {"terminal_state": "FORMASYON_TAMAMLANDI", "frm_faz_gecis_sayisi": 1},  # ihlal
    ])
    hatalar = soru_kapisi.tutarlilik_kontrol([str(tmp_path)])
    assert any("S27" in h for h in hatalar)
    assert any("formasyon_sayisi" in h for h in hatalar)  # Σ=1 != frm=2
    assert not any("tekil seri" in h for h in hatalar)


def test_kova_karsilastir(tmp_path):
    sonuc = tmp_path / "sonuc.json"
    sonuc.write_text(json.dumps({
        "S01": {"karar": "RED — kapandı, yayımlanmaz"},
        "S02": {"karar": "YAZILIR: kart metnine yazılır"},
        "S14": {"karar": "KARAR YOK (n<30)"},
    }, ensure_ascii=False), encoding="utf-8")
    dagilim = soru_kapisi.kova_dagilimi(sonuc)
    assert dagilim == {"S01": "red", "S02": "canli", "S14": "yok"}
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"kovalar": dagilim}, ensure_ascii=False),
                        encoding="utf-8")
    assert soru_kapisi.kova_karsilastir(sonuc, baseline) == []
    # baseline kayar → fark
    kaymis = dict(dagilim); kaymis["S01"] = "canli"
    baseline.write_text(json.dumps({"kovalar": kaymis}, ensure_ascii=False),
                        encoding="utf-8")
    hatalar = soru_kapisi.kova_karsilastir(sonuc, baseline)
    assert hatalar and "S01" in hatalar[0]


def test_cli_kova_yaz(tmp_path):
    sonuc = tmp_path / "sonuc.json"
    sonuc.write_text(json.dumps({"S01": {"karar": "RED"}}, ensure_ascii=False),
                     encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    kod = soru_kapisi.main(["--cikti", str(tmp_path), "--sonuc", str(sonuc),
                            "--kova", str(baseline), "--kova-yaz"])
    assert kod == 0 and baseline.exists()
