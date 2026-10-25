# -*- coding: utf-8 -*-
"""Canlı–replay tutarlılık denetimi sözleşmesi.

SALT HESAP: ağ yok, gerçek motor yok. Motor ve veri kaynağı enjekte edilir.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

import tutarlilik as T


class SahteAday:
    def __init__(self, desen="Yükselen Kama", aile="Kama",
                 ust=100.0, alt=95.0, dondurulmus=100.0):
        self.pattern_type = desen
        self.family = aile
        self.upper_now = ust
        self.lower_now = alt
        self.frozen_upper_boundary_at_break = dondurulmus
        self.frozen_lower_boundary_at_break = alt


class SahteSnap:
    def __init__(self, aktif=None, yon=1, durum="KIRILIM_TEYITLI"):
        self.active = aktif
        self.break_dir = yon
        self.state = durum


def _df(bitis="2026-10-20T17:00:00+03:00", adet=120):
    son = pd.Timestamp(bitis)
    idx = pd.date_range(end=son, periods=adet, freq="h")
    return pd.DataFrame({"open": [100.0] * adet, "high": [101.0] * adet,
                         "low": [99.0] * adet, "close": [100.5] * adet}, index=idx)


def _kayit(**ek):
    veri = {"sembol": "THYAO", "tf": "1h", "desen": "Yükselen Kama", "yon": 1,
            "giris": 100.0, "durum": "KIRILIM_TEYITLI",
            "bar": "2026-10-20T17:00:00+03:00"}
    veri.update(ek)
    return veri


@pytest.mark.parametrize("durum", ["KIRILIM_TEYITLI", "RETEST_BASARILI"])
def test_seviye_main_ile_ayni(durum):
    """Denetimdeki seviye kuralı `main._alert_break_level` ile birebir olmalı."""
    import main

    aday = SahteAday(dondurulmus=101.5, ust=100.0)
    assert T.seviye(aday, 1, durum) == main._alert_break_level(aday, 1, durum)
    # dondurulmuş sınır yoksa üst/alt sınıra düşer
    aday2 = SahteAday(dondurulmus=None, ust=100.0)
    assert T.seviye(aday2, 1, "KIRILIM_TEYITLI") == main._alert_break_level(
        aday2, 1, "KIRILIM_TEYITLI")


def test_veri_yoksa_hukum_yok():
    assert T.denetle(_kayit(), None)["sonuc"] == "veri_yok"
    assert T.denetle(_kayit(), pd.DataFrame())["sonuc"] == "veri_yok"
    # 60 bardan kısa seri replay için yetersiz
    assert T.denetle(_kayit(), _df(adet=30))["sonuc"] == "veri_yok"


def test_ayni_uyari_replayde_de_ayni():
    motor = lambda tf: type("M", (), {"process": lambda self, df, tam_yeniden=False:  # noqa: E731
                                      SahteSnap(SahteAday(dondurulmus=100.0))})()
    sonuc = T.denetle(_kayit(), _df(), motor_kur=motor)
    assert sonuc["sonuc"] == "ayni"
    assert sonuc["bulunan"]["desen"] == "Yükselen Kama"


def test_desen_sapmasi_yakalanir():
    motor = lambda tf: type("M", (), {"process": lambda self, df, tam_yeniden=False:  # noqa: E731
                                      SahteSnap(SahteAday(desen="Alçalan Üçgen",
                                                          aile="Üçgen"))})()
    sonuc = T.denetle(_kayit(), _df(), motor_kur=motor)
    assert sonuc["sonuc"] == "sapma"
    assert "desen" in sonuc["neden"]


def test_yon_sapmasi_yakalanir():
    motor = lambda tf: type("M", (), {"process": lambda self, df, tam_yeniden=False:  # noqa: E731
                                      SahteSnap(SahteAday(), yon=-1)})()
    sonuc = T.denetle(_kayit(), _df(), motor_kur=motor)
    assert sonuc["sonuc"] == "sapma" and "yön" in sonuc["neden"]


def test_seviye_sapmasi_toleransli():
    # %0,3 fark: tolerans içinde → aynı
    motor = lambda tf: type("M", (), {"process": lambda self, df, tam_yeniden=False:  # noqa: E731
                                      SahteSnap(SahteAday(dondurulmus=100.3))})()
    assert T.denetle(_kayit(), _df(), motor_kur=motor)["sonuc"] == "ayni"
    # %2 fark: sapma
    motor2 = lambda tf: type("M", (), {"process": lambda self, df, tam_yeniden=False:  # noqa: E731
                                       SahteSnap(SahteAday(dondurulmus=102.0))})()
    sonuc = T.denetle(_kayit(), _df(), motor_kur=motor2)
    assert sonuc["sonuc"] == "sapma" and "seviye" in sonuc["neden"]


def test_replayde_formasyon_yoksa_sapma():
    motor = lambda tf: type("M", (), {"process": lambda self, df, tam_yeniden=False:  # noqa: E731
                                      SahteSnap(None)})()
    sonuc = T.denetle(_kayit(), _df(), motor_kur=motor)
    assert sonuc["sonuc"] == "sapma" and "aktif formasyon yok" in sonuc["neden"]


def test_motor_hatasi_denetimi_dusurmez():
    def patlayan(_tf):
        raise RuntimeError("motor çöktü")
    sonuc = T.denetle(_kayit(), _df(), motor_kur=patlayan)
    assert sonuc["sonuc"] == "veri_yok" and "motor hatası" in sonuc["neden"]


def test_gece_denetimi_sayar_ve_onbellek_kullanir():
    cagri = []

    def getir(sembol, tf):
        cagri.append((sembol, tf))
        return _df()

    kayitlar = [_kayit(), _kayit(desen="Alçalan Üçgen", bar="2026-10-20T16:00:00+03:00")]
    motor = lambda tf: type("M", (), {"process": lambda self, df, tam_yeniden=False:  # noqa: E731
                                      SahteSnap(SahteAday(dondurulmus=100.0))})()
    sonuc = T.gunluk(kayitlar, getir=getir, simdi=datetime.fromisoformat(
        "2026-10-21T20:00:00+03:00"), motor_kur=motor)
    assert sonuc["kontrol"] == 2
    assert sonuc["ayni"] == 1 and sonuc["sapma"] == 1
    assert cagri == [("THYAO", "1h")]           # aynı sembol/tf tek kez indirilir
    assert sonuc["sapmalar"][0]["neden"]


def test_gece_denetimi_eski_kayitlari_atlar():
    sonuc = T.gunluk([_kayit(bar="2026-01-01T10:00:00+03:00")],
                     getir=lambda s, t: _df(),
                     simdi=datetime.fromisoformat("2026-10-21T20:00:00+03:00"))
    assert sonuc["kontrol"] == 0
    assert "denetlenecek uyarı yok" in T.ozet(sonuc)


def test_ozet_sapmayi_tek_satirda_soyler():
    sonuc = {"kontrol": 3, "ayni": 2, "sapma": 1, "veri_yok": 0,
             "sapmalar": [{"sembol": "THYAO", "tf": "1h", "bar": "x",
                           "neden": "desen: A → B"}]}
    metin = T.ozet(sonuc)
    assert "sapma 1" in metin and "THYAO" in metin


def test_butce_asilirsa_kalan_kayit_ertelenir():
    """Gece işi taramayı bekletmez: süre bütçesi dolunca kalanlar ertelenir."""
    kayitlar = [_kayit(bar=f"2026-10-20T{h:02d}:00:00+03:00") for h in range(10, 18)]
    motor = lambda tf: type("M", (), {"process": lambda self, df, tam_yeniden=False:  # noqa: E731
                                      SahteSnap(SahteAday(dondurulmus=100.0))})()
    sonuc = T.gunluk(kayitlar, getir=lambda s, t: _df(),
                     simdi=datetime.fromisoformat("2026-10-21T20:00:00+03:00"),
                     motor_kur=motor, butce_sn=-1)   # bütçe zaten aşılmış
    assert sonuc["kontrol"] == 0 and sonuc["kalan"] == 8
    assert "ertelendi" in T.ozet(sonuc)
