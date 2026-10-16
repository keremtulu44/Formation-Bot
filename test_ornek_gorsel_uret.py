# -*- coding: utf-8 -*-
"""Örnek görsel üretim sistemi regresyonu.

Kapsam (ağ yok, motor ÇALIŞMAZ — sentetik kayıtlar yalnız ÇİZİM zincirini besler):
  1. Katalogdaki her senaryo PNG üretir; red yok, boş kare yok.
  2. Manşet senaryolarda alarm çizgisi kadraj içindedir ve formasyon bantları çizilir.
  3. Determinizm: aynı senaryo iki kez → aynı `girdi_ozeti` (piksel hash'ine
     bağlanmıyoruz, §12.19).
  4. bot_data koruması: sentetik çıktı canlı önbellek dizinine yazılamaz.
  5. Dürüst etiket: güven şeridi `demo · sentetik` der; kare kendini gerçek
     veri gibi göstermez.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent
_SCRIPT = KOK / "scripts" / "ornek_gorsel_uret.py"


@pytest.fixture(scope="module")
def sistem():
    """`scripts/` paket olmadığı için yoldan yüklenir (grafik_onizleme ile aynı zorunluluk)."""
    spec = importlib.util.spec_from_file_location("ornek_gorsel_uret", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("ornek_gorsel_uret", mod)
    spec.loader.exec_module(mod)
    return mod


def test_katalog_degil_bos_ve_tum_senaryolar_uretilir(sistem, tmp_path):
    for ad, uretici in sistem.SENARYOLAR.items():
        sonuc = sistem.kare_uret(ad, tmp_path / f"{ad}.png")
        assert sonuc.get("hata") is None, ad
        assert sonuc["yol"], f"{ad}: PNG üretilemedi"
        meta = sonuc["meta"]
        assert not meta.get("red"), f"{ad}: çizim reddedildi: {meta.get('uyarilar')}"
        assert int(meta["mum_sayisi"]) >= 35, f"{ad}: kadraj anlamsız derecede küçük"
        assert Path(sonuc["yol"]).stat().st_size > 10_000, f"{ad}: PNG şüpheli küçük"


def test_manset_alarm_cizgisi_ve_bantlar_cizilir(sistem, tmp_path):
    for ad in sistem.MANSITLER:
        sonuc = sistem.kare_uret(ad, tmp_path / f"{ad}.png")
        cizgiler = sonuc["meta"]["cizgiler"]
        alarm = cizgiler.get("alarm") or {}
        assert alarm.get("deger") is not None, f"{ad}: alarm çizgisi yok"
        assert alarm.get("bar_disarida") is False, f"{ad}: alarm mumu kadraj dışında"
        assert cizgiler.get("formasyon_ust") is not None, f"{ad}: üst bant çizilmedi"
        assert cizgiler.get("formasyon_alt") is not None, f"{ad}: alt bant çizilmedi"


def test_determinizm_ayni_girdi_ozeti(sistem, tmp_path):
    for ad in sistem.MANSITLER:
        a = sistem.kare_uret(ad, tmp_path / f"{ad}_a.png")["meta"]
        b = sistem.kare_uret(ad, tmp_path / f"{ad}_b.png")["meta"]
        assert a["girdi_ozeti"] == b["girdi_ozeti"], f"{ad}: girdi özeti sabit değil"


def test_bot_data_icine_yazamaz(sistem):
    yer_ici = KOK / "bot_data" / "ornek.png"
    sonuc = sistem.kare_uret("ucgen_teyit", yer_ici)
    assert sonuc.get("hata") and "bot_data" in sonuc["hata"]
    assert not yer_ici.exists()


def test_guven_seridi_sentetik_etiketi_tasir(sistem, tmp_path):
    sonuc = sistem.kare_uret("bayrak_aday", tmp_path / "b.png")
    guven = sonuc["meta"].get("guven") or {}
    assert "sentetik" in str(guven.get("kaynak", ""))
    satirlar = " · ".join(str(s) for s in (sonuc["meta"].get("guven_satirlari") or []))
    assert "demo · sentetik" in satirlar


def test_bilinmeyen_senaryo_hata_doner(sistem, tmp_path):
    sonuc = sistem.kare_uret("boyle_bir_senaryo_yok", tmp_path / "x.png")
    assert sonuc.get("hata")
