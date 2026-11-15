"""Gölge v2 işlem-içi süreç izleme testleri: gözcü, tez durumu, politikalar, yarış düzeltmeleri."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random

import pandas as pd
import pytest

from patterns.constants import (
    ST_BREAK_CANDIDATE,
    ST_BREAK_CONFIRMED,
    ST_BREAK_FAILED,
    ST_RETEST_OK,
    ST_RETESTING,
)
from senaryo_v2.adaptor import _ms_olay_etiketleri, karantina_araliklari, kopukluk_barlarini_bul
from senaryo_v2.modeller import BlokBand, SeriVerisi
from senaryo_v2.mtf_yonetim import (
    ManagementBar,
    ManagementConfig,
    Snapshot,
    mtf_signal,
    simulate_management,
)
from senaryo_v2.olaylar import aday_olaylari_cikar
from senaryo_v2.plan import plan_karti_olustur
from senaryo_v2.rapor import surec_izini_coz, surec_ozeti_uret, zaman_kumesi_saglamligi
from senaryo_v2.surec import (
    TEZ_BEKLIYOR,
    TEZ_BOZULDU,
    TEZ_SINANIYOR,
    TEZ_TEYITLI,
    HedefteIzSur,
    HedefteYapiIzSur,
    KarKoruma,
    OlaydaCik,
    SurecGozcusu,
    TezDurumundaCik,
    olay_kutbu,
)
from senaryo_v2.yaris import _tek_yarisi_simule_et, fren_etiketle, surecli_yaris, yarisi_yurut
from test_golge_v2_birim import _bar


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _gozcu(barlar, *, yon="long", giris=100.0, risk=2.0, seviye=99.0, frm_id="", dolum_idx=0, **kw):
    return SurecGozcusu(
        barlar,
        yon=yon,
        giris=giris,
        risk=risk,
        atr_baz=2.0,
        tez_seviyesi=seviye,
        frm_stable_id=frm_id,
        dolum_idx=dolum_idx,
        **kw,
    )


def _yaris(barlar, *, yon="long", giris=100.0, stop=98.0, hedef=104.0, politikalar=(), gozcu=True, **kw):
    g = _gozcu(barlar, yon=yon, giris=giris, risk=abs(giris - stop)) if gozcu else None
    varsayilan = dict(olay_bar_idx=0, dolum_idx=0, start_scan_idx=1, atr_baz=2.0, ufuk_bar=10, intrabar=True, tez_iptal=True)
    varsayilan.update(kw)
    return surecli_yaris(barlar, yon=yon, giris=giris, stop=stop, hedef=hedef, gozcu=g, politikalar=politikalar, **varsayilan)


def _sakin(i: int, c: float = 100.5):
    """Stopa da hedefe de değmeyen, tez seviyesinin (99.0) üstünde kapanan bar."""
    return _bar(i, o=c, h=c + 0.5, l=c - 0.5, c=c)


def _eski_motor(barlar, *, dolum_idx, yon, giris, stop, hedef, atr_baz, ufuk_bar, intrabar):
    """Süreç izlemeden ÖNCEKİ yarış döngüsünün (tez iptali kapalı) bağımsız yeniden yazımı."""
    n = len(barlar)
    d = 1 if yon == "long" else -1
    risk = abs(giris - stop)
    bitis = min(n - 1, dolum_idx + ufuk_bar)
    for k in range(dolum_idx + 1, bitis + 1):
        b = barlar[k]
        cikis = None
        neden = ""
        if intrabar:
            if d * (b.open - stop) <= 0:
                cikis, neden = b.open, "STOP_GAP"
            elif d * ((b.low if d == 1 else b.high) - stop) <= 0:
                cikis, neden = stop, "STOP"
            elif d * ((b.high if d == 1 else b.low) - hedef) >= 0:
                cikis, neden = hedef, "HEDEF"
        else:
            if d * (b.close - stop) <= 0:
                cikis, neden = b.close, "STOP_CLOSE"
            elif d * (b.close - hedef) >= 0:
                cikis, neden = b.close, "HEDEF"
        if cikis is not None:
            pnl = d * (cikis - giris)
            return round(pnl / atr_baz, 4), round(pnl / risk, 4), neden, k - dolum_idx
    pnl = d * (barlar[bitis].close - giris)
    neden = "SANSURLU" if dolum_idx + ufuk_bar > n - 1 else "ZAMAN_STOPU"
    return round(pnl / atr_baz, 4), round(pnl / risk, 4), neden, bitis - dolum_idx


def _rastgele_barlar(rng: random.Random, n: int = 16):
    barlar = []
    fiyat = 100.0
    for i in range(n):
        acilis = fiyat + rng.uniform(-0.8, 0.8)
        kapanis = acilis + rng.uniform(-1.6, 1.6)
        yuksek = max(acilis, kapanis) + rng.uniform(0.0, 1.2)
        dusuk = min(acilis, kapanis) - rng.uniform(0.0, 1.2)
        barlar.append(_bar(i, o=acilis, h=yuksek, l=dusuk, c=kapanis))
        fiyat = kapanis
    return tuple(barlar)


# ---------------------------------------------------------------------------
# Gözcü: tez durumu ve etiketler
# ---------------------------------------------------------------------------
def test_tez_seviyesi_ici_kapanis_sinar_iki_ardisik_kapanis_bozar_ve_bozulma_kalicidir():
    barlar = (
        _sakin(0, 100.0),
        _sakin(1, 100.5),                              # seviyenin üstünde
        _bar(2, o=100.0, h=100.2, l=98.6, c=98.9),     # 99.0 altında kapanış -> sınama
        _bar(3, o=98.9, h=99.4, l=98.5, c=98.8),       # ikinci ardışık -> bozuldu
        _bar(4, o=99.0, h=101.5, l=98.9, c=101.0),     # geri alındı ama tez ölü kalır
    )
    g = _gozcu(barlar)
    gozlemler = [g.gozle(k, stop=98.0, hedef=104.0) for k in range(1, 5)]

    assert [x.tez for x in gozlemler] == [TEZ_BEKLIYOR, TEZ_SINANIYOR, TEZ_BOZULDU, TEZ_BOZULDU]
    assert "SEVIYE_ICI" not in gozlemler[0].olaylar
    assert "SEVIYE_ICI" in gozlemler[1].olaylar and "SEVIYE_ICI" in gozlemler[2].olaylar
    assert "SEVIYE_GERI_ALINDI" in gozlemler[3].olaylar
    assert gozlemler[1].aleyhte >= 1 and gozlemler[3].lehte >= 1


def test_tek_ici_kapanis_geri_alinirsa_tez_bozulmaz():
    barlar = (
        _sakin(0, 100.0),
        _bar(1, o=100.0, h=100.2, l=98.6, c=98.9),
        _sakin(2, 100.4),
        _bar(3, o=100.0, h=100.2, l=98.6, c=98.9),
        _sakin(4, 100.4),
    )
    g = _gozcu(barlar)
    durumlar = [g.gozle(k, stop=98.0, hedef=104.0).tez for k in range(1, 5)]
    assert durumlar == [TEZ_SINANIYOR, TEZ_BEKLIYOR, TEZ_SINANIYOR, TEZ_BEKLIYOR]


def test_short_tez_seviyesi_simetriktir():
    barlar = (
        _sakin(0, 100.0),
        _bar(1, o=100.0, h=101.4, l=99.8, c=101.2),   # short: seviye 101.0 üstünde kapanış
        _bar(2, o=101.2, h=101.6, l=100.9, c=101.3),
    )
    g = _gozcu(barlar, yon="short", seviye=101.0)
    durumlar = [g.gozle(k, stop=102.0, hedef=96.0).tez for k in (1, 2)]
    assert durumlar == [TEZ_SINANIYOR, TEZ_BOZULDU]


def test_formasyon_yasam_dongusu_etiketleri_ve_tez_yolu():
    def frm(i, durum, *, kimlik="f1", yon=1, c=100.5):
        return _bar(i, o=c, h=c + 0.4, l=c - 0.4, c=c, frm_aktif=True, frm_stable_id=kimlik, frm_state=durum, frm_break_dir=yon)

    barlar = (
        frm(0, ST_BREAK_CANDIDATE),
        frm(1, ST_BREAK_CANDIDATE),     # değişim yok -> etiket yok
        frm(2, ST_BREAK_CONFIRMED),     # teyit
        frm(3, ST_RETESTING),           # retest sürüyor -> sınama
        frm(4, ST_RETEST_OK),           # retest başarılı -> yeniden teyitli
        frm(5, ST_BREAK_FAILED),        # başarısız kırılım -> bozuldu
        frm(6, ST_BREAK_CANDIDATE, kimlik="f2"),  # başka formasyon -> kayıp
        frm(7, ST_BREAK_CONFIRMED, kimlik="f2"),  # kayıptan sonra formasyon okunmaz
    )
    g = _gozcu(barlar, seviye=None, frm_id="f1")
    gozlemler = [g.gozle(k, stop=98.0, hedef=104.0) for k in range(1, 8)]
    frm_etiketleri = [tuple(e for e in x.olaylar if e.startswith("FRM_")) for x in gozlemler]

    assert frm_etiketleri == [(), ("FRM_TEYIT",), ("FRM_RETEST",), ("FRM_RETEST_OK",), ("FRM_BASARISIZ",), ("FRM_KAYIP",), ()]
    assert [x.tez for x in gozlemler] == [
        TEZ_BEKLIYOR, TEZ_TEYITLI, TEZ_SINANIYOR, TEZ_TEYITLI, TEZ_BOZULDU, TEZ_BOZULDU, TEZ_BOZULDU,
    ]


def test_gec_teyitli_giriste_tez_olay_barinda_teyitli_baslar():
    def frm(i, durum):
        return _bar(i, o=100.5, h=100.9, l=100.1, c=100.5, frm_aktif=True, frm_stable_id="f1", frm_state=durum, frm_break_dir=1)

    barlar = (frm(0, ST_BREAK_CONFIRMED), frm(1, ST_BREAK_CONFIRMED))
    g = _gozcu(barlar, seviye=None, frm_id="f1")
    assert g.gozle(1, stop=98.0, hedef=104.0).tez == TEZ_TEYITLI


def test_market_structure_olaylari_yone_gore_etiketlenir_ve_ters_dis_kirilim_tezi_bozar():
    assert _ms_olay_etiketleri(
        ["EXTERNAL:EVENT_BOS:1:7", "INTERNAL:EVENT_SWEEP:-1:9", "SWING:HIGH:3", "EXTERNAL:EVENT_CHOCH:-1:8"]
    ) == ("EXT:BOS:+1", "INT:SWEEP:-1", "EXT:CHOCH:-1")

    barlar = (
        _sakin(0, 100.0),
        replace(_sakin(1), ms_olaylar=("INT:SWEEP:-1", "INT:BOS:+1")),
        replace(_sakin(2), ms_olaylar=("INT:CHOCH:-1",)),
        replace(_sakin(3), ms_olaylar=("EXT:CHOCH:-1",)),
    )
    g = _gozcu(barlar, seviye=None)
    g1, g2, g3 = (g.gozle(k, stop=98.0, hedef=104.0) for k in (1, 2, 3))

    assert {"MS_INT_SWEEP_TERS", "MS_INT_BOS_LEHTE"} <= set(g1.olaylar) and g1.tez == TEZ_TEYITLI
    # İç yapının ters kırılımı tezi bozmaz (yalnız kayda girer); dış yapınınki bozar.
    assert "MS_INT_CHOCH_TERS" in g2.olaylar and g2.tez == TEZ_TEYITLI
    assert "MS_EXT_CHOCH_TERS" in g3.olaylar and g3.tez == TEZ_BOZULDU

    # Short için aynı olaylar ters kutupla okunur.
    g_short = _gozcu(barlar, yon="short", seviye=None)
    assert "MS_INT_SWEEP_LEHTE" in g_short.gozle(1, stop=102.0, hedef=96.0).olaylar
    assert olay_kutbu("MS_EXT_CHOCH_TERS") == -1 and olay_kutbu("MS_INT_BOS_LEHTE") == 1
    assert olay_kutbu("ADAY_KARSI_BIRINCIL") == -1 and olay_kutbu("BILINMEYEN") == 0


def test_stabil_blok_ve_hacim_katmanlari_islem_sirasinda_okunur():
    duvar = BlokBand(family="OB", direction="bearish", lower=101.0, upper=102.5, available_index=0, height_atr=0.75, touch_count_asof=0)
    barlar = (
        _bar(0, o=100.0, h=100.5, l=99.5, c=100.0, blok_bear=(duvar,)),
        # Banda değdi, kapanışla aşamadı; karşı Stabil dirence (101.4) değdi, aşamadı.
        _bar(1, o=100.0, h=101.6, l=99.8, c=100.8, r_level=101.4, blok_bear=(duvar,),
             vp_volume_usable=True, vp_pressure_5=-0.30, vp_rvol=0.5),
        # Bandı ve direnci kapanışla aştı; hacim lehe döndü.
        _bar(2, o=100.8, h=103.2, l=100.7, c=103.0, r_level=101.4, vp_volume_usable=True, vp_pressure_5=0.30, vp_rvol=1.6),
    )
    g = _gozcu(barlar, seviye=None)
    g1 = g.gozle(1, stop=98.0, hedef=110.0)
    g2 = g.gozle(2, stop=98.0, hedef=110.0)

    # Bar 1'in tepesi (101.6) +0.8R: yarım R ilk kez burada görülür; +1R bir sonraki barda.
    assert {"BLOK_DUVAR", "SR_KARSI_RED", "VP_TERS_BASKI", "VP_DUSUK_KATILIM", "FIYAT_YARIM_R"} <= set(g1.olaylar)
    assert {"BLOK_ASILDI", "SR_KARSI_ASILDI", "VP_LEHTE_BASKI", "FIYAT_BIR_R"} <= set(g2.olaylar)
    assert "FIYAT_YARIM_R" not in g2.olaylar and "FIYAT_BIR_R" not in g1.olaylar
    assert g2.acik_r == pytest.approx(1.5) and g2.hedef_mesafe_atr == pytest.approx(3.5)


def test_islem_sirasinda_dogan_aday_olaylar_kayda_girer():
    class _Aday:
        def __init__(self, olay_id, yon, sinif):
            self.olay_id, self.yon, self.sinyal_sinifi = olay_id, yon, sinif

    barlar = (_sakin(0, 100.0), _sakin(1), _sakin(2))
    bar_olaylari = {1: [_Aday("kendi", "long", "BIRINCIL"), _Aday("x", "short", "BIRINCIL")], 2: [_Aday("y", "long", "IKINCIL")]}
    g = _gozcu(barlar, seviye=None, bar_olaylari=bar_olaylari, kendi_olay_id="kendi")
    g1 = g.gozle(1, stop=98.0, hedef=104.0)
    g2 = g.gozle(2, stop=98.0, hedef=104.0)

    assert {"ADAY_KARSI", "ADAY_KARSI_BIRINCIL"} <= set(g1.olaylar) and "ADAY_LEHTE" not in g1.olaylar
    assert "ADAY_LEHTE" in g2.olaylar and "ADAY_LEHTE_BIRINCIL" not in g2.olaylar


def test_gozlem_nedenseldir_gelecek_barlar_gecmis_gozlemi_degistirmez():
    rng = random.Random(7)
    for _ in range(40):
        barlar = _rastgele_barlar(rng, 14)
        giris = barlar[0].close
        tam = _yaris(barlar, giris=giris, stop=giris - 50.0, hedef=giris + 50.0)
        for kesim in (3, 6, 9):
            kesik = _yaris(barlar[: kesim + 1], giris=giris, stop=giris - 50.0, hedef=giris + 50.0)
            assert kesik.gozlemler == tam.gozlemler[:kesim]


# ---------------------------------------------------------------------------
# Yarış motoru: gözcü sonucu değiştirmez; politikalar belirli zaman sırasıyla işler
# ---------------------------------------------------------------------------
def test_gozcu_ve_politikasiz_yaris_eski_motorla_birebir_aynidir():
    rng = random.Random(42)
    for _ in range(300):
        barlar = _rastgele_barlar(rng)
        giris = barlar[0].close
        yon = rng.choice(["long", "short"])
        d = 1 if yon == "long" else -1
        stop = giris - d * rng.uniform(0.6, 2.5)
        hedef = giris + d * rng.uniform(1.0, 4.0)
        for intrabar in (True, False):
            ortak = dict(dolum_idx=0, yon=yon, giris=giris, stop=stop, hedef=hedef, atr_baz=2.0, ufuk_bar=10, intrabar=intrabar)
            beklenen = _eski_motor(barlar, **ortak)
            sig = _tek_yarisi_simule_et(barlar, olay_bar_idx=0, start_scan_idx=1, tez_iptal=True, **ortak)
            izli = surecli_yaris(
                barlar, olay_bar_idx=0, start_scan_idx=1, tez_iptal=True,
                gozcu=_gozcu(barlar, yon=yon, giris=giris, risk=abs(giris - stop)), **ortak,
            )
            assert sig == beklenen
            assert (izli.pnl_atr, izli.pnl_r, izli.neden, izli.cozulme_offset) == beklenen


def test_cikisa_kadar_mfe_mae_cikistan_sonraki_yolu_saymaz():
    barlar = [_bar(k) for k in range(21)]
    barlar[20] = _bar(20, c=100.0, s_level=99.0, atr=2.0, s_reclaim_kind="intrabar_sweep_reclaim")
    barlar.append(_bar(21, o=100.0, h=101.0, l=99.4, c=100.8))
    barlar.append(_bar(22, o=100.8, h=104.5, l=100.6, c=104.2))      # 2.0 ATR hedef (104.0) burada dolar
    barlar.append(_bar(23, o=104.2, h=112.0, l=90.0, c=100.0))        # çıkıştan SONRA: sayılmamalı
    barlar.extend(_bar(k) for k in range(24, 34))
    seri = SeriVerisi(sembol="TEST", tf="4h", barlar=tuple(barlar))
    olay = aday_olaylari_cikar(seri, min_warmup_bar=20)[0]
    plan = plan_karti_olustur(olay, barlar[20], mod="mod0", tampon_atr=0.50)
    sonuc = yarisi_yurut(seri, olay, plan, ufuk_bar=10)

    assert sonuc.neden_20_intra_iptal == "HEDEF" and sonuc.bar_20_intra_iptal == 2
    assert sonuc.surec is not None
    assert sonuc.surec.gozlem_n == 1 and sonuc.surec.tez_yolu == "B"
    assert sonuc.surec.mfe_r == pytest.approx(2.0)      # hedef fiyatı; 112.0 değil
    assert sonuc.surec.mae_r == pytest.approx(0.3)      # 99.4; 90.0 değil
    assert sonuc.mfe_atr == pytest.approx(6.0)          # eski alan: stopsuz tam ufuk yolu


def test_ilk_barda_bar_ici_cikista_gozlem_yoktur():
    barlar = (_sakin(0, 100.0), _bar(1, o=100.0, h=100.4, l=97.5, c=98.2), _sakin(2))
    iz = _yaris(barlar)
    assert iz.neden == "STOP" and iz.gozlemler == ()
    assert iz.mae_r == pytest.approx(1.0) and iz.mfe_r == 0.0


def test_tez_iptali_ayni_bardaki_bar_ici_hedefi_ezemez():
    hedef_ve_bos = _bar(1, o=100.0, h=104.5, l=99.5, c=99.8, ms_bos_down_now=True)
    iz = _yaris((_sakin(0, 100.0), hedef_ve_bos, _sakin(2)), gozcu=False)
    assert iz.neden == "HEDEF" and iz.pnl_atr == pytest.approx(2.0)

    yalniz_bos = _bar(1, o=100.0, h=101.0, l=99.5, c=99.8, ms_bos_down_now=True)
    iz = _yaris((_sakin(0, 100.0), yalniz_bos, _sakin(2)), gozcu=False)
    assert iz.neden == "TEZ_IPTAL_BOS" and iz.pnl_atr == pytest.approx(-0.1)


def test_tasinan_stop_sonraki_bardan_gecerlidir_ve_yalniz_lehe_tasinir():
    koruma = KarKoruma(tetik_r=1.0, kilit_r=0.25)   # +1R görülünce stop giriş + 0.25R = 100.5
    barlar = (
        _sakin(0, 100.0),
        # +1R (102.0) görülür ve AYNI barda 100.2'ye iner: yeni stop bu barda işlemez.
        _bar(1, o=100.0, h=102.3, l=100.2, c=101.5),
        _bar(2, o=101.5, h=101.8, l=100.4, c=101.0),   # 100.5 koruma stopu burada çalışır
        _sakin(3),
    )
    iz = _yaris(barlar, politikalar=(koruma,))
    assert iz.neden == "IZ_STOP" and iz.cozulme_offset == 2
    assert iz.pnl_r == pytest.approx(0.25) and iz.stop_tasindi and iz.stop_son == pytest.approx(100.5)

    # Politikasız aynı yol zaman stopuna gider: koruma sonucu değiştirdi.
    assert _yaris(barlar, ufuk_bar=3).neden == "ZAMAN_STOPU"

    # Koruma stopunun altına boşlukla açılış: kilit garanti değildir, açılıştan çıkılır.
    bosluk = barlar[:2] + (_bar(2, o=99.0, h=99.5, l=98.5, c=99.2), _sakin(3))
    iz = _yaris(bosluk, politikalar=(koruma,))
    assert iz.neden == "IZ_STOP_GAP" and iz.pnl_r == pytest.approx(-0.5)

    # Stop asla geriye taşınmaz: daha gevşek bir kilit mevcut stopu düşürmez.
    gevsek = KarKoruma(tetik_r=1.0, kilit_r=0.10)
    iz = _yaris(barlar, politikalar=(koruma, gevsek))
    assert iz.stop_son == pytest.approx(100.5)


def test_stop_ile_hedef_ayni_barda_ise_stop_kazanir_politika_olsa_da():
    barlar = (_sakin(0, 100.0), _bar(1, o=100.0, h=104.5, l=97.5, c=103.0), _sakin(2))
    iz = _yaris(barlar, politikalar=(HedefteIzSur(kilit_atr=1.0),))
    assert iz.neden == "STOP" and iz.pnl_r == pytest.approx(-1.0) and not iz.hedef_goruldu


def test_hedefte_iz_sur_hedefi_kaldirir_kilidi_sonraki_bardan_uygular():
    barlar = (
        _sakin(0, 100.0),
        _bar(1, o=100.0, h=104.6, l=99.6, c=104.2),    # 2.0 ATR hedefe değdi: çıkma, kilitle (102.0)
        _bar(2, o=104.2, h=107.0, l=103.5, c=106.5),
        _bar(3, o=106.5, h=106.8, l=101.5, c=102.2),   # kilide (102.0) değdi
        _sakin(4),
    )
    iz = _yaris(barlar, politikalar=(HedefteIzSur(kilit_atr=1.0),))
    assert iz.hedef_goruldu and iz.neden == "IZ_STOP" and iz.cozulme_offset == 3
    assert iz.pnl_atr == pytest.approx(1.0)
    assert iz.mfe_r == pytest.approx(3.5)              # 107.0: hedeften sonra görülen yol da sayılır

    # İz mesafesi verilirse stop en iyi kapanışın `iz_atr` gerisine çekilir (106.5 - 2.0 = 104.5).
    iz = _yaris(barlar, politikalar=(HedefteIzSur(kilit_atr=1.0, iz_atr=1.0),))
    assert iz.neden == "IZ_STOP" and iz.pnl_atr == pytest.approx(2.25) and iz.stop_son == pytest.approx(104.5)

    # Politikasız aynı yol hedefte kapanır.
    baz = _yaris(barlar)
    assert baz.neden == "HEDEF" and baz.pnl_atr == pytest.approx(2.0) and baz.cozulme_offset == 1


def test_hedefte_yapi_iz_sur_ic_yapinin_korunan_dibini_izler():
    barlar = (
        _sakin(0, 100.0),
        replace(_bar(1, o=100.0, h=104.6, l=99.6, c=104.2), ms_int_protected_low=101.0),
        replace(_bar(2, o=104.2, h=107.0, l=103.8, c=106.5), ms_int_protected_low=105.0),  # iz: 105.0 - 0.2 = 104.8
        _bar(3, o=106.5, h=106.8, l=104.5, c=105.0),
        _sakin(4),
    )
    iz = _yaris(barlar, politikalar=(HedefteYapiIzSur(kilit_atr=1.0, tampon_atr=0.10),))
    assert iz.neden == "IZ_STOP" and iz.cozulme_offset == 3 and iz.stop_son == pytest.approx(104.8)
    assert iz.pnl_atr == pytest.approx(2.4)


def test_hedefte_yapi_iz_sur_fiyatin_ters_tarafindaki_bayat_seviyeyi_iz_saymaz():
    # Motor, kırıldığı hâlde yeniden atanmamış ya da bölünme öncesinden kalmış bir seviyeyi
    # "korunan dip" diye bildirebilir (kapanış 106.5 iken 150.0). Bu bir iz değildir: stop
    # kapanışın ötesine konursa işlem sonraki açılışta kapanırdı.
    def barlar(seviye_2):
        return (
            _sakin(0, 100.0),
            _bar(1, o=100.0, h=104.6, l=99.6, c=104.2),
            replace(_bar(2, o=104.2, h=107.0, l=103.8, c=106.5), ms_int_protected_low=seviye_2),
            _bar(3, o=106.5, h=106.8, l=104.5, c=105.0),
            _bar(4, o=105.0, h=105.5, l=104.6, c=105.2),
        )

    politika = (HedefteYapiIzSur(kilit_atr=1.0, tampon_atr=0.10),)
    bayat = _yaris(barlar(150.0), politikalar=politika, ufuk_bar=4)
    kilit = _yaris(barlar(None), politikalar=(HedefteIzSur(kilit_atr=1.0),), ufuk_bar=4)
    assert bayat.neden == kilit.neden == "ZAMAN_STOPU" and bayat.stop_son == pytest.approx(102.0)
    assert bayat.pnl_atr == kilit.pnl_atr == pytest.approx(2.6)
    # Kapanışın hemen altındaki geçerli seviye ise izlenir (106.5 > 106.3 - 0.2).
    gecerli = _yaris(barlar(106.3), politikalar=politika, ufuk_bar=4)
    assert gecerli.neden == "IZ_STOP" and gecerli.stop_son == pytest.approx(106.1)


def test_politika_cikisi_kapanista_veya_sonraki_acilista_uygulanir():
    barlar = (
        _sakin(0, 100.0),
        _bar(1, o=100.0, h=100.3, l=98.6, c=98.9),     # tez seviyesi (99.0) altında kapanış
        _bar(2, o=98.4, h=101.0, l=98.2, c=100.9),     # kötü açılış
        _sakin(3),
    )
    politika = (OlaydaCik(frozenset({"SEVIYE_ICI"}), "SEVIYE_CIKIS"),)

    kapanista = _yaris(barlar, politikalar=politika, cikis_modu="kapanis")
    assert kapanista.neden == "SEVIYE_CIKIS" and kapanista.cozulme_offset == 1
    assert kapanista.pnl_atr == pytest.approx(-0.55)

    acilista = _yaris(barlar, politikalar=politika, cikis_modu="sonraki_acilis")
    assert acilista.neden == "SEVIYE_CIKIS" and acilista.cozulme_offset == 2
    assert acilista.pnl_atr == pytest.approx(-0.8)

    # Karar verildikten sonra son bar kalmadıysa işlem ufuk kapanışında biter.
    son_barda = _yaris(barlar[:2], politikalar=politika, cikis_modu="sonraki_acilis")
    assert son_barda.neden == "SANSURLU" and son_barda.pnl_atr == pytest.approx(-0.55)

    tez_politikasi = (TezDurumundaCik(frozenset({TEZ_BOZULDU}), "TEZ_BOZULDU"),)
    assert _yaris(barlar, politikalar=tez_politikasi, ufuk_bar=3).neden == "ZAMAN_STOPU"   # tek iç kapanış bozmaz


def test_politika_gozcu_olmadan_ve_bilinmeyen_cikis_modu_reddedilir():
    barlar = (_sakin(0, 100.0), _sakin(1))
    with pytest.raises(ValueError):
        _yaris(barlar, politikalar=(KarKoruma(1.0),), gozcu=False)
    with pytest.raises(ValueError):
        _yaris(barlar, cikis_modu="gun_sonu")
    with pytest.raises(ValueError):
        KarKoruma(tetik_r=0.5, kilit_r=0.5)


# ---------------------------------------------------------------------------
# Mod 2 düzeltmeleri
# ---------------------------------------------------------------------------
def _mod2_kurulum(sonraki_barlar):
    band = BlokBand(family="FVG", direction="bullish", lower=98.2, upper=99.5, available_index=18, height_atr=0.65, touch_count_asof=0)
    barlar = [_bar(k, l=99.8) for k in range(20)]
    barlar.append(_bar(20, c=100.0, s_level=99.0, atr=2.0, s_reclaim_kind="intrabar_sweep_reclaim", blok_bull=(band,)))
    barlar.extend(sonraki_barlar)
    barlar.extend(_bar(k, o=100.2, h=100.9, l=99.8, c=100.5) for k in range(len(barlar), 40))
    seri = SeriVerisi(sembol="TEST", tf="4h", barlar=tuple(barlar))
    olay = aday_olaylari_cikar(seri, min_warmup_bar=20)[0]
    plan = plan_karti_olustur(olay, barlar[20], mod="mod2", tampon_atr=0.50)
    assert plan.limit_fiyat == pytest.approx(99.5) and plan.stop == pytest.approx(98.0)
    return seri, olay, plan


def test_mod2_bosluklu_dolumda_r_paydasi_planlanan_risktir():
    # Limit 99.5, stop 98.0 (planlanan risk 1.5). Açılış 98.1: emir daha iyi fiyattan dolar,
    # gerçek risk 0.1'e düşer. Eski payda (0.1) aynı işlemi +59R gösteriyordu.
    seri, olay, plan = _mod2_kurulum([
        _bar(21, o=98.1, h=99.0, l=98.05, c=98.9),
        _bar(22, o=98.9, h=104.5, l=98.8, c=104.0),
    ])
    sonuc = yarisi_yurut(seri, olay, plan, ufuk_bar=10)

    assert sonuc.dolduruldu and sonuc.giris_gercek == pytest.approx(98.1)
    assert sonuc.risk_gercek_atr == pytest.approx(0.05) and sonuc.risk_r_atr == pytest.approx(0.75)
    assert sonuc.neden_20_intra_iptal == "HEDEF"
    assert sonuc.pnl_20_intra_iptal_atr == pytest.approx(2.0)
    assert sonuc.pnl_20_intra_iptal_r == pytest.approx(4.0 / 1.5, abs=1e-4)


def test_mod2_dolum_barinda_stop_cikis_ofseti_dolumdan_sayilir_fren_dogru_bari_kullanir():
    seri, olay, plan = _mod2_kurulum([
        _bar(21, o=100.2, h=100.9, l=99.8, c=100.5),
        _bar(22, o=100.0, h=100.4, l=97.0, c=97.5),     # hem limit hem stop: dolum barında stop
    ])
    sonuc = yarisi_yurut(seri, olay, plan, ufuk_bar=10)

    assert sonuc.neden_15_intra_iptal == "STOP_DOLUM_BARI"
    assert sonuc.dolum_bar_offset == 2
    # Çıkış barı = olay + dolum ofseti + çıkış ofseti = 22. Eskiden çıkış ofseti de 2 yazıldığı
    # için fren bu stopu 24. barda kapanmış sayıyordu.
    assert sonuc.bar_15_intra_iptal == 0 and sonuc.bar_20_intra_iptal == 0
    assert sonuc.pnl_15_intra_iptal_r == pytest.approx(-1.0)
    # Kapanış-stoplu varyant dolum barının kapanışını da sınar (97.5 < 98.0).
    assert sonuc.neden_15_close_iptal == "STOP_CLOSE"
    assert sonuc.pnl_15_close_iptal_atr == pytest.approx(-1.0)


def test_mod2_bekleyen_limit_ters_dis_kirilimla_iptal_edilir():
    seri, olay, plan = _mod2_kurulum([
        _bar(21, o=100.2, h=100.9, l=99.8, c=100.0, ms_bos_down_now=True),   # dolmadan tez öldü
        _bar(22, o=100.0, h=100.4, l=99.2, c=100.2),                         # limit burada dolardı
    ])
    sonuc = yarisi_yurut(seri, olay, plan, ufuk_bar=10)
    assert not sonuc.dolduruldu and sonuc.neden_20_intra_iptal == "LIMIT_IPTAL_BOS"
    assert sonuc.surec is None

    # Kırılım dolumla AYNI barda kapanırsa dolum geri alınmaz; tez iptali o barın kapanışında işler.
    seri, olay, plan = _mod2_kurulum([_bar(21, o=100.0, h=100.4, l=99.2, c=99.3, ms_bos_down_now=True)])
    sonuc = yarisi_yurut(seri, olay, plan, ufuk_bar=10)
    assert sonuc.dolduruldu and sonuc.neden_20_intra_iptal == "TEZ_IPTAL_BOS"
    assert sonuc.bar_20_intra_iptal == 0 and sonuc.pnl_20_intra_iptal_atr == pytest.approx(-0.1)


def test_mod2_tez_iptal_penceresi_dolumdan_sayilir_ve_dolum_bari_kapanisi_gozlenir():
    seri, olay, plan = _mod2_kurulum([
        _bar(21, o=100.2, h=100.9, l=99.8, c=100.5),
        _bar(22, o=100.2, h=100.9, l=99.8, c=100.5),
        _bar(23, o=100.0, h=100.4, l=99.2, c=100.1),                          # dolum (olay + 3)
        _bar(24, o=100.1, h=100.6, l=99.6, c=100.2),
        _bar(25, o=100.2, h=100.4, l=99.0, c=99.2, ms_bos_down_now=True),     # dolum + 2
    ])
    sonuc = yarisi_yurut(seri, olay, plan, ufuk_bar=10)

    # Eski pencere olay barından sayılıyordu: 3. barda dolan emir hiç korunmuyordu.
    assert sonuc.dolum_bar_offset == 3
    assert sonuc.neden_20_intra_iptal == "TEZ_IPTAL_BOS" and sonuc.bar_20_intra_iptal == 2
    assert sonuc.neden_15_intra_ham == "ZAMAN_STOPU"
    # Dolum barının kapanışı (k=0) ve sonraki kapanış (k=1) gözlendi; iptal barı gözlenmez.
    assert sonuc.surec is not None and sonuc.surec.gozlem_n == 2
    # Dolum barının dolumdan önceki uçları işleme ait olmayabilir: MFE yalnız kapanıştan.
    assert sonuc.surec.mfe_r == pytest.approx((100.6 - 99.5) / 1.5, abs=1e-4)


def test_mod0_sonuclari_surec_izleme_acik_kapali_aynidir():
    barlar = [_bar(k) for k in range(60)]
    for idx in (20, 22, 24, 26, 27, 40):
        barlar[idx] = _bar(idx, c=100.0, s_level=99.0, atr=2.0, s_reclaim_kind="intrabar_sweep_reclaim")
    for s_idx in (21, 23, 25):
        barlar[s_idx] = _bar(s_idx, o=99.5, h=100.0, l=97.0, c=97.5)
    seri = SeriVerisi(sembol="TEST", tf="4h", barlar=tuple(barlar))
    olaylar = list(aday_olaylari_cikar(seri, min_warmup_bar=20))
    assert olaylar
    acik, kapali = {}, {}
    for o in olaylar:
        p = plan_karti_olustur(o, barlar[o.bar_index], mod="mod0", tampon_atr=0.50)
        acik[o.olay_id] = yarisi_yurut(seri, o, p, ufuk_bar=10)
        kapali[o.olay_id] = yarisi_yurut(seri, o, p, ufuk_bar=10, surec_izle=False)
        assert kapali[o.olay_id].surec is None
        assert replace(acik[o.olay_id], surec=None) == kapali[o.olay_id]
    assert fren_etiketle(olaylar, acik) == fren_etiketle(olaylar, kapali)


# ---------------------------------------------------------------------------
# Veri karantinası
# ---------------------------------------------------------------------------
def test_kopukluk_tespiti_nedenseldir_ve_esigi_asan_acilisi_isaretler():
    acilis = [10.0, 10.1, 5.0, 5.1, 5.7, 5.6]
    kapanis = [10.0, 10.2, 5.1, 5.2, 5.6, 5.7]
    assert kopukluk_barlarini_bul(acilis, kapanis) == (2,)                    # -51%; +9.6% eşik altı
    assert kopukluk_barlarini_bul(acilis, kapanis, esik_oran=0.09) == (2, 4)
    for kesim in range(1, len(acilis) + 1):
        tam = kopukluk_barlarini_bul(acilis, kapanis)
        assert kopukluk_barlarini_bul(acilis[:kesim], kapanis[:kesim]) == tuple(i for i in tam if i < kesim)
    assert kopukluk_barlarini_bul([1.0, float("nan"), 0.0], [1.0, 1.0, 1.0]) == ()


def test_karantina_etiketi_yalniz_takvim_konumuna_bakar():
    seri = SeriVerisi(
        sembol="TEST", tf="1d", barlar=(), kopukluk_barlari=(50,),
        kopukluk_gorunur_barlari=(50,), kirli_araliklar=((50, 110),),
    )
    assert seri.karantina_nedeni(30, ileri_bar=13) == ""
    assert seri.karantina_nedeni(37, ileri_bar=13) == "KOPUKLUK_ILERI"     # 50, pencerenin son barı
    assert seri.karantina_nedeni(36, ileri_bar=13) == ""
    assert seri.karantina_nedeni(50, ileri_bar=13) == "KOPUKLUK_GERI"      # kopukluk barının kendisi
    assert seri.karantina_nedeni(110, ileri_bar=13) == "KOPUKLUK_GERI"
    assert seri.karantina_nedeni(111, ileri_bar=13) == ""
    iki = replace(seri, kopukluk_gorunur_barlari=(50, 70), kirli_araliklar=((50, 110), (70, 130)))
    assert iki.karantina_nedeni(60, ileri_bar=13) == "KOPUKLUK_GERI+ILERI"
    assert not seri.domain_hatali and replace(seri, vp_hatali=True).domain_hatali


def test_gunluk_kopukluk_alt_zaman_dilimine_kapanis_zamaniyla_tasinir():
    # 4 saatlik eksen: günde iki bar (13:30, 18:00). Günlük eksen: her gün 18:30.
    gunler = pd.date_range("2026-01-05", periods=8, freq="D", tz="Europe/Istanbul")
    gunluk = [g + pd.Timedelta(hours=18, minutes=30) for g in gunler]
    dort_saat = [g + pd.Timedelta(hours=h, minutes=m) for g in gunler for h, m in ((13, 30), (18, 0))]

    # Günlük 3. bar (4. gün, kapanış 18:30) kopuk. Günlük bağlam (Stabil S/R, ATR_1d) alt zaman
    # dilimine as-of taşınır: o günlük barı İLK gören 4s barı ertesi günün ilk barıdır (indeks 8).
    # Kopukluk gününün kendi 4s barları (6, 7) günlük bağlamı hâlâ kopukluk öncesinden okur;
    # onları bu TF'nin KENDİ kopukluğu (varsa) kapsar.
    gorunur, kirli = karantina_araliklari(dort_saat, (), gunluk, (3,), geri_bar=2)
    assert gorunur == (8,)
    # Kirli bağlam 2 GÜNLÜK bar sürer: günlük 5. barı ilk gören 4s barına (indeks 12) kadar, dahil.
    assert kirli == ((8, 12),)
    # Bu TF'nin kendi kopukluğu kendi bar sayısıyla ölçülür; iki kaynak ayrı ayrı izlenir.
    gorunur, kirli = karantina_araliklari(dort_saat, (6,), gunluk, (3,), geri_bar=2)
    assert gorunur == (6, 8) and kirli == ((6, 8), (8, 12))
    # Günlük TF'de kopukluk barı kendisidir (aynı kapanış zamanı).
    assert karantina_araliklari(gunluk, (3,), gunluk, (3,), geri_bar=2) == ((3,), ((3, 5),))
    # Pencere serinin sonunu aşarsa son bara kırpılır; pencere 0 yalnız kopukluk barını tutar.
    assert karantina_araliklari(dort_saat, (14,), gunluk, (), geri_bar=60) == ((14,), ((14, 15),))
    assert karantina_araliklari(dort_saat, (2,), gunluk, (), geri_bar=0) == ((2,), ((2, 2),))
    # Son günün günlük kopukluğunu gören bir 4s barı henüz yoktur: hiçbir şey işaretlenmez.
    assert karantina_araliklari(dort_saat, (), gunluk, (7,), geri_bar=2) == ((), ())
    # Nedensel: kopukluk kendisinden ÖNCEKİ barları kirletmez.
    seri = SeriVerisi(sembol="T", tf="4h", barlar=(), kopukluk_gorunur_barlari=(8,), kirli_araliklar=((8, 12),))
    assert seri.karantina_nedeni(7, ileri_bar=0) == "" and seri.karantina_nedeni(8, ileri_bar=0) == "KOPUKLUK_GERI"
    assert seri.karantina_nedeni(12, ileri_bar=0) == "KOPUKLUK_GERI" and seri.karantina_nedeni(13, ileri_bar=0) == ""


def test_ms_bayatlik_bayragi_korunan_seviye_fiyatin_bir_atr_gerisindeyse_yanar():
    # ATR 2.0: korunan dip 110 iken kapanış 100.5 (9.5 > 2.0) -> motor seviyeyi hâlâ koruyor sanıyor.
    assert replace(_bar(0, c=100.5), ms_protected_low=110.0).ms_dis_bayat
    assert replace(_bar(0, c=100.5), ms_protected_high=90.0).ms_dis_bayat
    # 1 ATR'ye kadar aşım kırılım onayı bekleyen olağan durumdur; seviye yoksa bayrak yanmaz.
    assert not replace(_bar(0, c=100.5), ms_protected_low=102.4).ms_dis_bayat
    assert not replace(_bar(0, c=100.5), ms_protected_high=98.6).ms_dis_bayat
    assert not replace(_bar(0, c=100.5), ms_protected_low=95.0, ms_protected_high=105.0).ms_dis_bayat
    assert not _bar(0, c=100.5).ms_dis_bayat


def test_karantina_duyarliligi_secenekleri_ayni_olaylardan_alt_kume_cikarir():
    import numpy as np

    from research.golge_v2_karantina_duyarlilik import SINIRSIZ, _secenek_adi, duyarlilik_tablosu

    olaylar = pd.DataFrame(
        {
            "olay_id": [f"o{i}" for i in range(8)],
            "sembol": ["A", "A", "A", "A", "B", "B", "B", "B"],
            "tf": ["4h"] * 6 + ["1h", "2h"],                      # son ikisi 4h+1d dışı: hiçbir kümeye girmez
            "donem": ["kesif", "kesif", "dogrulama", "dogrulama"] * 2,
            "kalite_katmani": ["A_ARTI", "A_CEKIRDEK", "A_ARTI", "B_ADAY", "A_ARTI", "A_ARTI", "A_ARTI", "A_ARTI"],
            "sinyal_sinifi": ["BIRINCIL"] * 8,
            "net15_20_r": [1.0, -1.0, 2.0, 0.5, -1.0, 3.0, 9.0, 9.0],
        }
    )
    bayrak = {0: np.zeros(8, dtype=bool), SINIRSIZ: np.array([0, 0, 1, 1, 0, 0, 0, 0], dtype=bool)}
    kopuk_sembol = np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=bool)
    tablo = {(r["kume"], r["karantina"], r["donem"]): r for r in duyarlilik_tablosu(olaylar, bayrak, kopuk_sembol)}

    assert _secenek_adi(60) == "geri_60" and _secenek_adi(SINIRSIZ) == "geri_sinirsiz"
    assert tablo[("D7_A_Arti", "karantinasiz", "tumu")]["n"] == 4            # o0, o2, o4, o5
    assert tablo[("D7_A_Arti", "karantinasiz", "tumu")]["ort"] == pytest.approx(1.25)
    assert tablo[("D7_A_Arti", "geri_0", "tumu")]["cikan"] == 0
    d7 = tablo[("D7_A_Arti", "geri_sinirsiz", "tumu")]
    assert d7["n"] == 3 and d7["cikan"] == 1 and d7["ort"] == pytest.approx(1.0)
    assert tablo[("D7_A_Arti", "geri_sinirsiz", "dogrulama")]["n"] == 0
    assert tablo[("D6_A_Cekirdek_Veya_Arti", "sembol_disi", "tumu")]["n"] == 2   # yalnız B'nin 4h olayları
    assert tablo[("D1_Birincil", "sembol_disi", "tumu")]["cikan"] == 4


# ---------------------------------------------------------------------------
# Rapor yardımcıları
# ---------------------------------------------------------------------------
def test_zaman_kumesi_sembol_kumesinin_gizledigi_belirsizligi_gosterir():
    # 30 sembol, her biri iki günde birer işlem: 1. gün herkes +1.0, 2. gün herkes -0.5.
    satirlar = []
    for s in range(30):
        satirlar.append({"sembol": f"S{s:02d}", "bar_close_time": "2026-05-04T18:30:00+03:00", "r": 1.0})
        satirlar.append({"sembol": f"S{s:02d}", "bar_close_time": "2026-05-12T18:30:00+03:00", "r": -0.5})
    oz = zaman_kumesi_saglamligi(pd.DataFrame(satirlar), "r", B=400)

    assert oz["n"] == 60 and oz["ort"] == pytest.approx(0.25)
    assert oz["kumeler"]["sembol"]["ci95_alt"] == pytest.approx(0.25)       # her sembol aynı: "kesin" görünür
    assert oz["kumeler"]["gun"]["kume_n"] == 2 and oz["kumeler"]["gun"]["ci95_alt"] == pytest.approx(-0.5)
    assert oz["kumeler"]["hafta"]["kume_n"] == 2
    # Tek ay kümesi belirsizlik ölçemez: aralık verilmez ve "hepsinde pozitif" sayılmaz.
    assert oz["kumeler"]["ay"]["kume_n"] == 1 and oz["kumeler"]["ay"]["ci95_alt"] is None
    assert oz["en_kotu_alt"] == pytest.approx(-0.5) and oz["hepsinde_pozitif"] is False
    assert zaman_kumesi_saglamligi(pd.DataFrame(), "r")["hepsinde_pozitif"] is False


def test_surec_ozeti_betimleyici_tabloyu_uretir():
    assert surec_izini_coz("1:FRM_TEYIT,VP_LEHTE_BASKI|3:SEVIYE_ICI") == [
        (1, ("FRM_TEYIT", "VP_LEHTE_BASKI")), (3, ("SEVIYE_ICI",)),
    ]
    assert surec_izini_coz("") == [] and surec_izini_coz(float("nan")) == []
    df = pd.DataFrame([
        dict(net15_20_r=1.4, neden_20_intra_iptal="HEDEF", surec_gozlem_n=2, surec_mfe_r=1.5, surec_mae_r=0.2,
             surec_tez_son="TEYITLI", surec_izi="1:FRM_TEYIT|2:FIYAT_BIR_R"),
        dict(net15_20_r=-1.1, neden_20_intra_iptal="STOP", surec_gozlem_n=3, surec_mfe_r=0.7, surec_mae_r=1.0,
             surec_tez_son="BOZULDU", surec_izi="1:FRM_TEYIT|2:SEVIYE_ICI|3:SEVIYE_ICI"),
        dict(net15_20_r=-1.2, neden_20_intra_iptal="STOP_GAP", surec_gozlem_n=0, surec_mfe_r=0.0, surec_mae_r=1.1,
             surec_tez_son="", surec_izi=""),
    ])
    oz = surec_ozeti_uret(df)
    assert oz["n"] == 3 and oz["gozlemsiz_n"] == 1 and oz["stop_n"] == 2
    assert oz["stop_once_yarim_r_gordu"] == pytest.approx(0.5) and oz["stop_once_bir_r_gordu"] == 0.0
    assert {r["tez_son"] for r in oz["tez_son"]} == {"TEYITLI", "BOZULDU", "GOZLEM_YOK"}
    etiket = {r["etiket"]: r for r in oz["etiketler"]}
    assert etiket["FRM_TEYIT"]["islem_n"] == 2 and etiket["SEVIYE_ICI"]["islem_n"] == 1
    assert etiket["SEVIYE_ICI"]["medyan_ilk_bar"] == 2.0
    assert surec_ozeti_uret(pd.DataFrame()) == {}


def test_onbellek_anahtari_tf_listesine_ve_koda_baglidir():
    from research import golge_v2

    kok = Path("/tmp/onbellek")
    a = golge_v2.onbellek_yolu(kok, "AEFES", ("4h", "1d"))
    b = golge_v2.onbellek_yolu(kok, "AEFES", ("1h", "2h", "4h", "1d"))
    assert a != b and a == golge_v2.onbellek_yolu(kok, "AEFES", ("4h", "1d"))
    assert golge_v2.kod_ozeti() in a.name and a.name.startswith("AEFES__4h-1d__")


# ---------------------------------------------------------------------------
# MTF yönetim çekirdeği
# ---------------------------------------------------------------------------
def test_mtf_kalici_4s_durumu_sabah_saatlerinde_de_gorunur():
    simdi = datetime(2026, 1, 6, 11, 30, tzinfo=timezone.utc)
    iki = Snapshot(simdi, 99, 100, 1, 0, 0)                                   # taze 2s ters hareket
    dun_4s = Snapshot(simdi - timedelta(hours=17, minutes=30), 99, 99, 1, 0, -1)  # dünkü son 4s mumu

    assert not mtf_signal(simdi, 1, iki, None, dun_4s, two_mode="price", four_mode="state").signal
    assert mtf_signal(simdi, 1, iki, None, dun_4s, two_mode="price", four_mode="state", four_state_kalici=True).signal
    # Kalıcılık yalnız DURUM içindir: fiyat modunda tazelik şartı sürer; gelecekteki snapshot asla geçerli değil.
    assert not mtf_signal(simdi, 1, iki, None, dun_4s, two_mode="price", four_mode="price", four_state_kalici=True).signal
    gelecek = Snapshot(simdi + timedelta(hours=1), 99, 99, 1, 0, -1)
    assert not mtf_signal(simdi, 1, iki, None, gelecek, two_mode="price", four_mode="state", four_state_kalici=True).signal


def test_mtf_koruma_stopu_ilk_stoptan_ayirt_edilir():
    t = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)
    cfg = ManagementConfig(protect_trigger_r=1, protect_lock_r=0.25)
    barlar = [ManagementBar(t, 100, 112, 99, 105), ManagementBar(t + timedelta(hours=1), 105, 110, 99, 101)]
    korumali = simulate_management(barlar, entry=100, stop=90, target=120, direction=1, cfg=cfg)
    assert korumali.reason == "STOP" and korumali.gross_r == 0.25 and korumali.stop_moved

    barlar[0] = ManagementBar(t, 100, 121, 89, 100)
    ilk_stop = simulate_management(barlar, entry=100, stop=90, target=120, direction=1, cfg=cfg)
    assert ilk_stop.reason == "STOP" and ilk_stop.gross_r == -1 and not ilk_stop.stop_moved


# ---------------------------------------------------------------------------
# Süreç ölçüm koşucusu (ileri beklenti + eşleşmiş replay istatistiği)
# ---------------------------------------------------------------------------
def test_ileri_beklenti_kalmanin_getirisini_ve_ayni_yastaki_kosulsuzu_verir():
    from research.golge_v2_surec_olcum import ileri_beklenti_tablosu

    df = pd.DataFrame([
        dict(sembol="S1", donem="kesif", bar_close_time="2026-01-05T18:30:00+03:00", baz_brut=2.0,
             acik_r_yolu="0.5000|1.0000", surec_izi="1:X|2:X,Y", tez_yolu="BT"),
        dict(sembol="S2", donem="dogrulama", bar_close_time="2026-05-05T18:30:00+03:00", baz_brut=-1.0,
             acik_r_yolu="-0.5000", surec_izi="1:X", tez_yolu="S"),
        dict(sembol="S3", donem="kesif", bar_close_time="2026-01-06T18:30:00+03:00", baz_brut=-1.0,
             acik_r_yolu="", surec_izi="", tez_yolu=""),          # ilk barda stop: gözlem yok
    ])
    tablo = {r["etiket"]: r for r in ileri_beklenti_tablosu(df)}

    # X ilk kez k=1'de görülür (S1'de ikinci görülüşü sayılmaz): kalmak +1.5 ve -0.5 getirdi.
    assert tablo["X"]["n"] == 2 and tablo["X"]["ileri_r"] == pytest.approx(0.5)
    assert tablo["X"]["kosulsuz_r"] == pytest.approx(0.5) and tablo["X"]["fark_r"] == pytest.approx(0.0)
    assert tablo["X"]["kesif_ileri_r"] == pytest.approx(1.5) and tablo["X"]["dogrulama_ileri_r"] == pytest.approx(-0.5)
    assert tablo["Y"]["n"] == 1 and tablo["Y"]["ileri_r"] == pytest.approx(1.0) and tablo["Y"]["ort_acik_r"] == pytest.approx(1.0)
    assert tablo["TEZ=TEYITLI"]["medyan_k"] == 2.0 and tablo["TEZ=SINANIYOR"]["ileri_r"] == pytest.approx(-0.5)
    assert not any(r["sayilir"] or r["cikis_adayi"] for r in tablo.values())     # n < 30
    assert ileri_beklenti_tablosu(df.iloc[2:]) == []


def test_ileri_beklenti_bilgi_ile_cikis_adayini_ayirir():
    from research.golge_v2_surec_olcum import ileri_beklenti_tablosu

    # 40 sembol × 2 dönem. KOTU: kalmak +0.2 getirir ama aynı yaştaki sıradan işlem +1.0 getirir
    # (bilgi taşır, çıkış gerekçesi değil). ZARAR: kalmak iki dönemde de -0.5 (çıkış adayı).
    satirlar = []
    for i in range(40):
        for d, donem in enumerate(("kesif", "dogrulama")):
            gun = pd.Timestamp("2025-06-02" if d == 0 else "2026-04-06") + pd.Timedelta(days=7 * i)
            ortak = dict(sembol=f"S{i:02d}", donem=donem, bar_close_time=gun.strftime("%Y-%m-%dT18:30:00+03:00"), tez_yolu="B")
            oynama = 0.01 * (i % 5)
            satirlar.append(dict(ortak, baz_brut=1.0 + oynama, acik_r_yolu="0.0000", surec_izi="1:SIRADAN"))
            satirlar.append(dict(ortak, baz_brut=0.2 + oynama, acik_r_yolu="0.0000", surec_izi="1:KOTU"))
            satirlar.append(dict(ortak, baz_brut=-0.5 - oynama, acik_r_yolu="0.0000", surec_izi="1:ZARAR"))
    tablo = {r["etiket"]: r for r in ileri_beklenti_tablosu(pd.DataFrame(satirlar))}

    assert tablo["KOTU"]["bilgi"] == "KOTU" and tablo["KOTU"]["ileri_r"] > 0
    assert not tablo["KOTU"]["cikis_adayi"] and not tablo["KOTU"]["iki_donemde_negatif"]
    assert tablo["ZARAR"]["bilgi"] == "KOTU" and tablo["ZARAR"]["iki_donemde_negatif"] and tablo["ZARAR"]["cikis_adayi"]
    assert tablo["SIRADAN"]["bilgi"] == "IYI" and not tablo["SIRADAN"]["cikis_adayi"]
    assert tablo["ZARAR"]["kesif_n"] == tablo["ZARAR"]["dogrulama_n"] == 40


def test_varyant_karari_iki_donemde_de_dayaniklilik_ister():
    from research.golge_v2_surec_olcum import VARYANTLAR, varyant_ozeti

    assert len(VARYANTLAR) == 20 and all(v[2] in ("kapanis", "sonraki_acilis") for v in VARYANTLAR.values())
    # Uygulanabilir çıkış fiyatı her çıkış varyantında vardır; iyimser kapanış fiyatı yalnız üç adayda.
    assert sum(1 for v in VARYANTLAR.values() if v[0] == "cikis" and v[2] == "sonraki_acilis") == 9

    def kume(kesif_fark: float, dogrulama_fark: float, etkilenen_her: int = 2) -> pd.DataFrame:
        satirlar = []
        for i in range(120):
            donem = "kesif" if i % 2 == 0 else "dogrulama"
            gun = pd.Timestamp("2025-06-02" if donem == "kesif" else "2026-04-06") + pd.Timedelta(days=3 * (i // 2))
            baz = 1.0 if i % 3 else -1.0
            etkilenir = i % etkilenen_her == 0 or etkilenen_her == 1
            fark = (kesif_fark if donem == "kesif" else dogrulama_fark) * (0.5 + (i % 5) / 4) if etkilenir else 0.0
            satirlar.append(dict(
                sembol=f"S{i % 30:02d}", donem=donem, bar_close_time=gun.strftime("%Y-%m-%dT18:30:00+03:00"),
                baz_net=baz, baz_neden="HEDEF" if baz > 0 else "STOP", baz_bar=3,
                kar_1_0_net=baz + fark, kar_1_0_neden="IZ_STOP" if etkilenir else ("HEDEF" if baz > 0 else "STOP"), kar_1_0_bar=3,
            ))
        return pd.DataFrame(satirlar)

    iyi = varyant_ozeti(kume(0.3, 0.3, etkilenen_her=1), "kar_1_0")
    assert iyi["karar"] == "GECTI" and iyi["donemler"]["tumu"]["etkilenen"] == 120
    assert iyi["donemler"]["kesif"]["fark_en_kotu_alt"] > 0 and iyi["donemler"]["dogrulama"]["fark_en_kotu_alt"] > 0

    # Yalnız bir dönemde iyileşen kural geçmez; iki dönemde de kötüleşen zararlıdır.
    assert varyant_ozeti(kume(0.3, -0.3, etkilenen_her=1), "kar_1_0")["karar"] == "GECMEDI"
    assert varyant_ozeti(kume(-0.3, -0.3, etkilenen_her=1), "kar_1_0")["karar"] == "ZARARLI"

    az = kume(0.3, 0.3, etkilenen_her=1).head(20)
    assert varyant_ozeti(az, "kar_1_0")["karar"] == "SAYILMAZ_N<30"

    # Havuzda n >= 30 olsa da dönem hücresi n < 30 ise "iki dönemde de dayanıklı" denemez.
    ince = varyant_ozeti(kume(0.3, 0.3, etkilenen_her=1).head(50), "kar_1_0")
    assert ince["donemler"]["tumu"]["etkilenen"] == 50 and ince["donemler"]["kesif"]["etkilenen"] == 25
    assert ince["donem_ince"] and ince["karar"] == "ZAYIF_ARTI"


@pytest.mark.slow
def test_kosucu_ayni_girdiyle_bayt_bayt_ayni_ciktiyi_uretir(tmp_path):
    """İki işçili koşu, satır sırası işçilerin bitiş sırasına bağlı olmadan aynı CSV'yi vermeli."""
    from research import golge_v2

    ciktilar = []
    for ad in ("a", "b"):
        cikti = tmp_path / ad
        argv = ["--start", "64", "--end", "66", "--tfs", "4h", "1d", "--workers", "2", "--cikti", str(cikti)]
        if ad == "b":
            argv += ["--cache-dir", str(tmp_path / "onbellek")]
        assert golge_v2.main(argv) == 0
        ciktilar.append(cikti)

    for dosya in ("mod0_baz.csv.gz", "mod1_blok_stop.csv.gz", "mod2_blok_limit.csv.gz", "duyarlilik.csv.gz"):
        a = pd.read_csv(ciktilar[0] / dosya)
        b = pd.read_csv(ciktilar[1] / dosya)
        pd.testing.assert_frame_equal(a, b)
    mod0 = pd.read_csv(ciktilar[0] / "mod0_baz.csv.gz")
    # Satırlar evren sırasındadır: her sembol tek bir bitişik blok oluşturur.
    blok_baslangici = mod0["sembol"] != mod0["sembol"].shift()
    assert int(blok_baslangici.sum()) == mod0["sembol"].nunique() == 2
    for kolon in ("veri_karantina", "karantina_nedeni", "risk_r_atr", "bar_20_intra_iptal", "surec_gozlem_n",
                  "surec_mfe_r", "surec_mae_r", "surec_tez_son", "surec_tez_yolu", "surec_izi"):
        assert kolon in mod0.columns
    dolan = mod0[~mod0["sansurlu"]]
    assert dolan["surec_gozlem_n"].notna().all()
    # Çıkışa kadar MFE, stopsuz tam ufuk MFE'sinden büyük olamaz (R -> ATR çevrilerek).
    # Gözcünün MFE'si 0'dan başlar; fiyat girişin üstünü hiç görmediyse saf yol MFE'si negatiftir.
    assert ((dolan["surec_mfe_r"] * dolan["risk_r_atr"]) <= dolan["mfe_atr"].clip(lower=0.0) + 1e-3).all()
    rapor = (ciktilar[0] / "RAPOR_GOLGE_V2.md").read_text(encoding="utf-8")
    for baslik in ("## 7. Veri Karantinası", "## 8. Kabul Kararının Küme Tanımına Dayanıklılığı"):
        assert baslik in rapor
    # Önbellek anahtarı kod + TF + veri özetini taşır; ikinci koşu aynı sonucu önbellekten de verir.
    assert len(list((tmp_path / "onbellek").glob("*__4h-1d__*.pkl.gz"))) == 2
