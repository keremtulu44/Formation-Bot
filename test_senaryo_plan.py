# -*- coding: utf-8 -*-
"""Faz 3 — plan kartı kuralları (stop bandı, R eşiği, bilinmeyenler, saflık)."""

import pytest

from senaryo.modeller import PlanKaydi
from senaryo.plan_karti import plan_karti_uret

T = "2026-11-05T15:00:00+03:00"


def _plan(**d):
    taban = dict(
        plan_id="ASELS-4h-100", sembol="ASELS", tf="4h", t=T,
        bar_index=100, donem="kesif", giris=100.0, atr=1.0,
        destek=98.0, band=(98.5, 100.2), karsit_yapilar=[103.0],
        hukum_satiri="UYGUN · 4 lehte · 0 celişki",
    )
    taban.update(d)
    return plan_karti_uret(**taban)


def test_mutlu_yol():
    p = _plan()
    assert p is not None
    # zemin = max(destek=98, band_lo=98.5) = 98.5 → stop = 98.5 − 0,1
    assert p.stop == pytest.approx(98.4)
    assert p.hedef == 103.0
    assert p.R == pytest.approx((103 - 100) / (100 - 98.4), rel=1e-3)
    assert p.R >= 1.2
    assert p.donem == "kesif" and p.bar_index == 100
    assert p.bilinmeyenler                          # dürüstlük satırı dolu


def test_uzak_destek_stopu_sisirmez():
    # destek çok uzak olsa bile bandın alt sınırı yakın hattır → kart var
    p = _plan(destek=90.0, band=(98.5, 100.2))
    assert p is not None and p.stop == pytest.approx(98.4)


def test_r_esigi_alti_kart_yok():
    assert _plan(karsit_yapilar=[101.5]) is None   # R ≈ 0,63 < 1,2


def test_stop_mesafesi_bandi_disi():
    # geniş band (alt sınır çok uzak) → stop 2,5 ATR'den geniş → kart yok
    assert _plan(destek=94.0, band=(95.0, 100.2)) is None
    # destek çok yakın → stop 0,5 ATR'den dar → kart yok
    assert _plan(destek=99.8, band=(99.75, 100.2)) is None


def test_destek_yoksa_kart_yok():
    assert _plan(destek=None) is None


def test_bant_yoksa_kart_yok():
    assert _plan(band=None) is None


def test_karsit_bos_ya_da_giris_altinda():
    assert _plan(karsit_yapilar=[]) is None
    # yalnız girişin altındaki seviyeler hedef olamaz → aday yok
    assert _plan(karsit_yapilar=[95.0, 99.0]) is None


def test_en_yakin_karsit_secilir_ve_siralanir():
    p = _plan(karsit_yapilar=[105.0, 103.0, 110.0])
    assert p.hedef == 103.0                        # en yakın karşıt yapı


def test_atr_sifir_ya_da_giris_gecersiz():
    assert _plan(atr=0.0) is None
    assert _plan(atr=float("nan")) is None
    assert _plan(giris=0.0) is None


def test_saflik():
    a, b = _plan(), _plan()
    assert a.to_dict() == b.to_dict()


def test_kayit_modeliyle_tutarli():
    p = _plan()
    # PlanKaydi doğrulaması (R tutarlılığı, bilinmeyenler) içeride döner
    PlanKaydi.from_dict(p.to_dict())


# --- FAZ9 B-turu (opt-in bayraklar) -----------------------------------------
def test_b3_ek_aday_en_yakini_kazanir():
    p = _plan(karsit_yapilar=[103.0], ek_adaylar=[102.0])
    assert p is not None and p.hedef == 102.0
    assert p.R == pytest.approx((102 - 100) / (100 - 98.4), rel=1e-3)


def test_b3_ek_aday_r_esiginde_karti_duser():
    # en yakın aday formasyon üst sınırı → R < 1,2 → kart yok (gizli filtre etkisi)
    assert _plan(karsit_yapilar=[103.0], ek_adaylar=[101.5]) is None


def test_b4_karakterli_stop_dikey_yukselende_genis():
    p = _plan(karakterli_stop=True, karakter="REBASED_HIGHER")
    assert p is not None
    # zemin 98.5; tampon 0,10 → 0,30 ATR → stop 98.2
    assert p.stop == pytest.approx(98.2)


def test_b4_bayrak_kapali_ve_diger_karakterler_ayni():
    # bayrak kapalı → karakter ne olursa olsun varsayılan0,10
    p1 = _plan(karakterli_stop=False, karakter="REBASED_HIGHER")
    assert p1 is not None and p1.stop == pytest.approx(98.4)
    # bayrak açık ama karakter farklı → yine varsayılan
    p2 = _plan(karakterli_stop=True, karakter="NONE")
    assert p2 is not None and p2.stop == pytest.approx(98.4)
