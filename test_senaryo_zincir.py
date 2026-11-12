# -*- coding: utf-8 -*-
"""Faz 2 — G1–G5 adaptör testleri (as-of, gelecek yasağı, bildiri şeması)."""

from types import SimpleNamespace

import pandas as pd

from senaryo.modeller import Bildirim
from senaryo.zincir import (
    G1Durum,
    G2Durum,
    G5Durum,
    MSUyari,
    bildirim_uret,
    g1_durumu,
    g2_durumu,
    g5_durumu,
    ms_uyarilari,
)

T = "2026-11-05T15:00:00+03:00"


class _SahteGecmis:
    """Duck-typed StabilSinglePassHistory (yalnız as-of sorgu yöntemi)."""

    def __init__(self, snap, daily_state="UP", ready=True):
        self._snap = snap
        self._daily = SimpleNamespace(state=daily_state, data_ready=ready)

    def support_at(self, t):
        return 3, self._snap

    def trend_at(self, t):
        return SimpleNamespace(daily=self._daily)


def _snap(**d):
    taban = dict(
        validity="ACTIVE", support_level=100.0, support_confirmed_at="2026-10-01",
        dynamics="FLAT", progression="SAME", distance_atr=0.8,
        events=(SimpleNamespace(event_type="SUPPORT_CONFIRMED"),),
    )
    taban.update(d)
    return SimpleNamespace(**taban)


# --- G1 ---------------------------------------------------------------------
def test_g1_aktif_zemin_kapi_acik():
    g1 = g1_durumu(_SahteGecmis(_snap()), T)
    assert g1.kapi_acik and not g1.kapali
    assert g1.destek == 100.0
    assert g1.mesafe_atr == 0.8
    assert g1.olaylar == ("SUPPORT_CONFIRMED",)


def test_g1_breached_kapandi():
    g1 = g1_durumu(_SahteGecmis(_snap(validity="BREACHED", distance_atr=-0.3)), T)
    assert g1.kapali and not g1.kapi_acik


def test_g1_desteksiz_sesiz_kapali_degil():
    g1 = g1_durumu(_SahteGecmis(_snap(validity="NO_SUPPORT", support_level=None,
                                      support_confirmed_at=None, distance_atr=None)), T)
    assert not g1.kapi_acik and not g1.kapali  # belirsiz → sus, RET değil


# --- G2 ---------------------------------------------------------------------
def _frm(dogum=10, son=50, daralma=0.3, mesafe_alt=2.0):
    return [{
        "stable_id": "s1", "pattern_type": "ASYMETRIK_UCTURGEN", "family": "triangle",
        "dogum_bar": dogum, "olcum_son_bar": son,
        "daralma_orani": daralma, "progress_son": 0.4,
        "frm_yakinlik_alt_kapanis_atr": mesafe_alt,
        "frm_yakinlik_ust_kapanis_atr": 1.5,
    }]


def test_g2_yasam_penceresi():
    assert not g2_durumu(_frm(), 5).aktif        # doğum öncesi
    assert g2_durumu(_frm(), 20).aktif
    assert not g2_durumu(_frm(), 60).aktif       # ölçüm sonu sonrası


def test_g2_olgunluk_daralma_veya_mesafe():
    assert not g2_durumu(_frm(daralma=0.3, mesafe_alt=2.0), 20).olgun
    assert g2_durumu(_frm(daralma=0.6), 20).olgun
    assert g2_durumu(_frm(mesafe_alt=0.5), 20).olgun


def test_g2_yoksa_bos_durum():
    d = g2_durumu([], 10)
    assert not d.aktif and d.tip == ""


# --- G3 ---------------------------------------------------------------------
def _olay(bar, tip="EVENT_BOS", yon=-1, seviye=99.0):
    return SimpleNamespace(event_bar=bar, event_type=tip, direction=yon,
                           broken_level=seviye)


def test_ms_gelecek_olay_okunmaz():
    olaylar = [_olay(12)]  # i=10 → gelecek
    assert ms_uyarilari(olaylar, 10) == []


def test_ms_tazelik_ve_yon():
    olaylar = [_olay(8, "EVENT_CHOCH", -1), _olay(2, "EVENT_BOS", 1), _olay(1)]
    u = ms_uyarilari(olaylar, 10)  # yaş: 2, 8, 9
    assert len(u) == 3
    assert u[0].tip == "CHOCH" and u[0].yon == "down" and u[0].taze
    assert not u[1].taze and u[1].yon == "up"
    assert u[2].yas_bar == 9 and not u[2].taze


def test_ms_esik_disi_taze_yok():
    assert all(not u.taze for u in ms_uyarilari([_olay(0)], 10, yas_esik=5))


# --- G5 ---------------------------------------------------------------------
def _frame(kapanislar):
    n = len(kapanislar)
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-11-05 10:00", periods=n, freq="1h", tz="UTC"),
        "open": kapanislar, "high": [c + 0.5 for c in kapanislar],
        "low": [c - 0.5 for c in kapanislar], "close": kapanislar,
        "volume": 1.0,
    })


def _zone(lo=99.0, hi=100.0, available=1, terminal=None, temaslar=(), dolu=0.0):
    return {
        "zone_id": "z1", "family": "OB", "direction": "bullish",
        "zone_lower": lo, "zone_upper": hi,
        "available_index": available, "native_terminal_index": terminal,
        "contact_bars": [{"index": k} for k in temaslar],
        "native_fill_ratio_at_terminal_or_asof": dolu,
    }


def test_g5_asof_aktiflik_ve_gelecek_terminal():
    f = _frame([100.0] * 10)
    z = _zone(terminal=6)
    assert g5_durumu([z], [], f, 4).bant == (99.0, 100.0)   # i=4: hâlâ yaşıyor
    assert g5_durumu([z], [], f, 7).bant is None             # i=7: ölmüş
    z2 = _zone(available=5)
    assert g5_durumu([z2], [], f, 3).bant is None            # henüz doğmadı


def test_g5_tepki_onayi_uc_bar():
    # temas bar 2; bar 4'te bandın üstüne kapanış → onay
    f = _frame([99.5, 99.4, 99.6, 99.7, 100.4, 100.2])
    z = _zone(temaslar=(2,))
    d = g5_durumu([z], [], f, 5)
    assert d.temas_bar == 2 and d.tepki_onayi
    # geç kapanış (bar 8) → onay yok
    f2 = _frame([99.5, 99.4, 99.6, 99.5, 99.5, 99.5, 99.5, 99.5, 100.4])
    z2 = _zone(temaslar=(2,))
    assert not g5_durumu([z2], [], f2, 8).tepki_onayi


def test_g5_tepki_onayi_gelecek_okumaz():
    # FAZ9-C: temas bar 4; bar 6'da gelecek kapanış bant üstü. i=5'te bu
    # gelecek görülmemeli (onay yok); i=6'da görülür (onay var).
    f = _frame([99.5, 99.4, 99.5, 99.5, 99.6, 99.7, 100.4, 100.2])
    z = _zone(temaslar=(4,))
    assert not g5_durumu([z], [], f, 5).tepki_onayi   # i=5: bar 6 gelecek
    assert g5_durumu([z], [], f, 6).tepki_onayi       # i=6: bar 6 artık geçmiş


def test_g5_tepki_onayi_temas_barinda_bos_pencere():
    # temas bar == i → pencere boş → onay yok (gelecek bar 6'ya bakılmaz)
    f = _frame([99.5, 99.4, 99.5, 99.5, 99.6, 99.7, 100.4])
    z = _zone(temaslar=(5,))
    assert not g5_durumu([z], [], f, 5).tepki_onayi
    assert g5_durumu([z], [], f, 6).tepki_onayi


def test_g5_kesme_testi_cerceve_iye_kesilince_degismez():
    # FAZ9-C kalıcı kesme testi: çerçeve N'de kesilirse i ≤ N-1 kararları
    # aynen kalmalı (g5 tamamen as-of olmalı).
    f = _frame([99.5, 99.4, 99.6, 99.7, 100.4, 100.2, 99.9, 100.1,
                99.8, 100.5, 100.3, 99.6])
    z = _zone(temaslar=(2, 5))
    for i in range(1, len(f)):
        tam = g5_durumu([z], [], f, i)
        kesilmis = g5_durumu([z], [], f.iloc[: i + 1], i)
        assert (tam.bant, tam.temas_bar, tam.tepki_onayi) == (
            kesilmis.bant, kesilmis.temas_bar, kesilmis.tepki_onayi
        ), f"i={i} kesme testi sızıntısı"


def test_g5_yon_filtresi_kisa_tezde_ayna():
    f = _frame([100.0] * 6)
    asagi = _zone(lo=99.0, hi=100.0)
    asagi["direction"] = "bearish"
    assert g5_durumu([asagi], [], f, 3, yon="long").bant is None
    assert g5_durumu([asagi], [], f, 3, yon="short").bant == (99.0, 100.0)


def test_g5_yoksa_bos_blok_engellemez():
    f = _frame([100.0] * 3)
    d = g5_durumu([], [], f, 1)
    assert d.bant is None and not d.tepki_onayi


# --- Bildiri üretimi --------------------------------------------------------
def _durumlar():
    g1 = G1Durum(t=T, zemin="ACTIVE", destek=100.0, onayli=True,
                 dinamik="FLAT", ilerleme="SAME", mesafe_atr=0.8,
                 trend_gunluk="UP", trend_hazir=True, kapali=False)
    g2 = G2Durum(aktif=True, tip="UCGEN", daralma=0.6, olgun=True)
    ms = (MSUyari(tip="BOS", yon="down", yas_bar=1, taze=True),)
    g5 = G5Durum(bant=(99.2, 100.1), zone_id="z1", aile="OB",
                 temas_bar=8, tepki_onayi=True)
    return g1, g2, ms, g5


def test_bildirimler_sema_uyumlu_ve_kaynakli():
    g1, g2, ms, g5 = _durumlar()
    bl = bildirim_uret(sembol="ASELS", tf="1h", t=T, g1=g1, g2=g2,
                       ms_olaylari=ms, g5=g5)
    assert len(bl) == 4
    assert all(isinstance(b, Bildirim) for b in bl)  # şema doğrulaması içeride
    kimseler = [b.kim for b in bl]
    assert kimseler == ["stabil", "formasyon", "ms", "blok"]  # sıra sabit
    assert all("n=" in b.kaynak for b in bl)


def test_bildirimlerde_gelecek_yok_ve_sessizlik_yazilir():
    # G1 belirsiz → stabil "bekle" bildirimi yine yazılır (kırmızı çizgi 7)
    g1 = G1Durum(t=T, zemin="NO_SUPPORT", kapali=False)
    bl = bildirim_uret(sembol="X", tf="1h", t=T, g1=g1, g2=G2Durum(),
                       ms_olaylari=(), g5=G5Durum())
    assert len(bl) == 1
    assert bl[0].kim == "stabil" and bl[0].iddia == "bekle"


def test_taze_olmayan_ms_yazilmaz():
    g1, g2, _, g5 = _durumlar()
    eski = (MSUyari(tip="BOS", yon="down", yas_bar=9, taze=False),)
    bl = bildirim_uret(sembol="X", tf="1h", t=T, g1=g1, g2=g2,
                       ms_olaylari=eski, g5=g5)
    assert not any(b.kim == "ms" for b in bl)


def test_blok_yoksa_bildirim_yok_zincir_devam():
    g1, g2, ms, _ = _durumlar()
    bl = bildirim_uret(sembol="X", tf="1h", t=T, g1=g1, g2=g2,
                       ms_olaylari=ms, g5=G5Durum())
    assert not any(b.kim == "blok" for b in bl)
    assert len(bl) == 3


# --- FAZ9-C as-of (dış denetim düzeltmeleri) --------------------------------
def test_g2_asof_gelecek_okumaz():
    # tam-seri alanları olgun gösterirken (daralma0.6/mesafe0.5), i=20'de
    # as-of değerler (0.3 / 2.0) olgun KILMAZ — gelecek okuma kapatıldı
    satir = _frm(daralma=0.6, mesafe_alt=0.5)
    satir[0].update({
        "asof_bar": [12, 20, 30],
        "asof_daralma": [0.1, 0.3, 0.6],
        "asof_ust_kap": [2.0, 1.5, 1.5],
        "asof_alt_kap": [2.5, 2.0, 0.5],
    })
    d = g2_durumu(satir, 20)
    assert d.aktif and not d.olgun
    assert d.daralma == 0.3 and d.mesafe_alt_atr == 2.0
    # i=30: as-of dizisi gerçekten olgunluğa ulaşıyor
    d2 = g2_durumu(satir, 30)
    assert d2.olgun and d2.daralma == 0.6
    # as-of dizi varken tam-seri alanına asla düşülmez (i=12)
    d3 = g2_durumu(satir, 12)
    assert d3.daralma == 0.1 and not d3.olgun


def test_g5_dolu_terminal_gelecek_okumaz():
    f = _frame([100.0] * 10)
    # terminal (ölüm barı) gelecekte: eski kod True üretirdi (407/412 sızıntısı)
    z = _zone(terminal=6, dolu=0.0)
    assert not g5_durumu([z], [], f, 4).dolu
    # as-of doluluk oranı yüksekse True (ölüm barı gereksiz)
    z2 = _zone(terminal=None, dolu=0.9)
    assert g5_durumu([z2], [], f, 4).dolu
