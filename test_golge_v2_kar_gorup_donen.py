"""Gölge v2 kâr görüp dönenler testleri: engel okuması, eşik mumu, birincil gözlem, fark aralığı."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import random

import numpy as np
import pandas as pd
import pytest

from research import golge_v2_endeks_filtresi as ef
from research import golge_v2_kar_gorup_donen as kg
from research import golge_v2_sonuc_anatomisi as sa
from senaryo_v2.modeller import BlokBand
from test_golge_v2_birim import _bar

KOK = Path(__file__).resolve().parent / "docs/arastirma/sonuclar/golge_v2"
CIKTI = KOK / "kar_gorup_donen"


def _temiz(i: int = 0, **kw):
    """Hiç karşı seviyesi olmayan bar; testler ihtiyacı olanı `kw` ile ekler."""
    ms = {
        "ms_weak_high": None, "ms_protected_high": None, "ms_weak_low": None, "ms_protected_low": None,
        "ms_unbroken_highs": (), "ms_unbroken_lows": (), "ms_down_broken_levels": (), "ms_up_broken_levels": (),
        "r_validity": "ACTIVE", "s_validity": "ACTIVE", "ms_olaylar": (), "ms_ext_dir": 0, "ms_int_dir": 0,
    }
    bar_kw = {k: kw.pop(k) for k in list(kw) if k in ("o", "h", "l", "c", "atr", "s_level", "r_level", "blok_bull", "blok_bear")}
    bar_kw.setdefault("s_level", None)
    bar_kw.setdefault("r_level", None)
    return replace(_bar(i, **bar_kw), **{**ms, **kw})


def _bant(alt: float, ust: float, yon: str = "bearish", h_atr: float = 0.75) -> BlokBand:
    return BlokBand(family="OB", direction=yon, lower=alt, upper=ust, available_index=0, height_atr=h_atr, touch_count_asof=0)


# ---------------------------------------------------------------------------
# Engeller
# ---------------------------------------------------------------------------
def test_karsi_seviyeler_plan_ile_ayni_kaynaklari_yone_gore_toplar():
    b = _temiz(r_level=110.0, s_level=90.0, ms_weak_high=108.0, ms_protected_high=None, ms_unbroken_highs=(105.0, 112.0),
               ms_down_broken_levels=(103.0,), ms_protected_low=92.0, ms_unbroken_lows=(95.0,), ms_up_broken_levels=(97.0,))
    assert sorted(kg.karsi_seviyeler(b, 1)) == [(103.0, "ms"), (105.0, "ms"), (108.0, "ms"), (110.0, "stabil"), (112.0, "ms")]
    assert sorted(kg.karsi_seviyeler(b, -1)) == [(90.0, "stabil"), (92.0, "ms"), (95.0, "ms"), (97.0, "ms")]
    # Geçerliliği ACTIVE / BREACHED olmayan Stabil seviyesi engel sayılmaz.
    assert kg.karsi_seviyeler(replace(b, r_validity="INVALIDATED"), 1).count((110.0, "stabil")) == 0
    assert (110.0, "stabil") in kg.karsi_seviyeler(replace(b, r_validity="BREACHED"), 1)


def test_karsi_bantlar_ince_bandi_atar_ve_yakin_kenari_one_koyar():
    b = _temiz(blok_bear=(_bant(104.0, 105.5), _bant(107.0, 107.4, h_atr=0.2)), blok_bull=(_bant(94.0, 96.0, "bullish"),))
    assert kg.karsi_bantlar(b, 1) == [(104.0, 105.5)]
    assert kg.karsi_bantlar(b, -1) == [(96.0, 94.0)]


def test_onde_engel_alan_alan_en_yakini_atr_ile_verir():
    b = _temiz(r_level=103.0, ms_unbroken_highs=(99.0, 101.0, 106.0), blok_bear=(_bant(104.0, 105.0),))
    assert kg.onde_engel(b, 1, 100.0, 2.0) == {"stabil": 1.5, "ms": 0.5, "blok": 2.0}
    # Geride kalan seviye ve bant sayılmaz; bandın içindeki fiyat için uzaklık 0'dır.
    assert kg.onde_engel(b, 1, 104.5, 2.0) == {"stabil": None, "ms": 0.75, "blok": 0.0}
    assert kg.onde_engel(b, 1, 107.0, 2.0) == {"stabil": None, "ms": None, "blok": None}
    kisa = _temiz(s_level=97.0, blok_bull=(_bant(94.0, 96.0, "bullish"),))
    assert kg.onde_engel(kisa, -1, 100.0, 2.0) == {"stabil": 1.5, "ms": None, "blok": 2.0}


@pytest.mark.parametrize(
    "h, c, beklenen",
    [
        (103.4, 102.0, "RED"),       # değdi, altında kapattı
        (103.0, 102.9, "RED"),       # tam değdi
        (104.0, 103.0, "RED"),       # kapanış seviyenin üstünde DEĞİL (eşitlik aşmak sayılmaz)
        (104.0, 103.2, "ASILDI"),    # kapanış ötesinde
        (102.6, 102.0, "YAKIN"),     # 0.2 ATR kala döndü
        (102.4, 102.0, ""),          # 0.3 ATR uzakta kaldı
    ],
)
def test_mum_engel_durumu_cizgi_seviyesi(h, c, beklenen):
    onceki = _temiz(0, c=100.0, r_level=103.0)
    assert kg.mum_engel_durumu(onceki, _temiz(1, h=h, l=99.5, c=c), 1, 2.0)["stabil"] == beklenen


def test_mum_engel_durumu_onceki_kapanista_bilinen_seviyeyi_kullanir_ve_geridekini_saymaz():
    onceki = _temiz(0, c=100.0, r_level=99.0, ms_unbroken_highs=(98.0,))
    # Seviyeler zaten kapanışın gerisinde; mum yeni seviye getirse de önceki kapanışta bilinmiyordu.
    b = _temiz(1, h=104.0, l=99.5, c=100.2, r_level=103.0, ms_unbroken_highs=(103.5,))
    assert kg.mum_engel_durumu(onceki, b, 1, 2.0) == {"stabil": "", "ms": "", "blok": ""}


def test_mum_engel_durumu_ayni_alanda_red_onceliklidir_ve_bant_kenarlarini_ayirir():
    onceki = _temiz(0, c=100.0, ms_unbroken_highs=(101.0, 103.0), blok_bear=(_bant(102.0, 104.0),))
    takildi = kg.mum_engel_durumu(onceki, _temiz(1, h=103.5, l=99.5, c=102.5), 1, 2.0)
    assert takildi == {"stabil": "", "ms": "RED", "blok": "RED"}       # 101 aşıldı, 103'te takıldı; bandın içinde kapattı
    gecti = kg.mum_engel_durumu(onceki, _temiz(1, h=104.6, l=99.5, c=104.2), 1, 2.0)
    assert gecti == {"stabil": "", "ms": "ASILDI", "blok": "ASILDI"}
    assert kg.mum_engel_durumu(onceki, _temiz(1, h=101.6, l=99.5, c=101.2), 1, 2.0)["blok"] == "YAKIN"


def test_mum_engel_durumu_short_aynasi():
    onceki = _temiz(0, c=100.0, s_level=97.0, blok_bull=(_bant(94.0, 96.0, "bullish"),))
    assert kg.mum_engel_durumu(onceki, _temiz(1, h=100.5, l=96.8, c=98.0), -1, 2.0) == {"stabil": "RED", "ms": "", "blok": ""}
    assert kg.mum_engel_durumu(onceki, _temiz(1, h=100.5, l=95.0, c=96.5), -1, 2.0) == {"stabil": "ASILDI", "ms": "", "blok": "RED"}
    assert kg.mum_engel_durumu(onceki, _temiz(1, h=100.5, l=93.0, c=93.5), -1, 2.0)["blok"] == "ASILDI"


def test_bant_temasi_disaridan_geleni_ve_zaten_icinde_olani_ayirir():
    disaridan = _temiz(0, c=100.0, blok_bear=(_bant(102.0, 104.0),))
    assert kg.bant_temasi(disaridan, _temiz(1, h=103.0, l=99.5, c=102.5), 1) == (True, False)      # banda girdi, içinde kapattı
    assert kg.bant_temasi(disaridan, _temiz(1, h=102.0, l=99.5, c=101.0), 1) == (True, False)      # kenara tam değdi, döndü
    assert kg.bant_temasi(disaridan, _temiz(1, h=101.9, l=99.5, c=101.0), 1) == (False, False)     # değmedi
    assert kg.bant_temasi(disaridan, _temiz(1, h=104.5, l=99.5, c=104.0), 1) == (False, False)     # kapanışla aştı
    iceride = _temiz(0, c=103.0, blok_bear=(_bant(102.0, 104.0),))
    assert kg.bant_temasi(iceride, _temiz(1, h=103.5, l=102.5, c=103.2), 1) == (False, True)
    assert kg.bant_temasi(iceride, _temiz(1, h=103.5, l=101.0, c=101.5), 1) == (False, True)       # aşağı çıktı; bandı aşmış sayılmaz
    ikisi = _temiz(0, c=103.0, blok_bear=(_bant(102.0, 104.0), _bant(103.4, 105.0)))
    assert kg.bant_temasi(ikisi, _temiz(1, h=103.6, l=102.5, c=103.2), 1) == (True, True)
    geride = _temiz(0, c=104.5, blok_bear=(_bant(102.0, 104.0),))
    assert kg.bant_temasi(geride, _temiz(1, h=105.0, l=103.0, c=103.5), 1) == (False, False)       # bant tamamen geride
    kisa = _temiz(0, c=100.0, blok_bull=(_bant(94.0, 96.0, "bullish"),))
    assert kg.bant_temasi(kisa, _temiz(1, h=100.5, l=95.0, c=96.5), -1) == (True, False)
    assert kg.bant_temasi(_temiz(0, c=95.0, blok_bull=(_bant(94.0, 96.0, "bullish"),)), _temiz(1, h=95.5, l=94.5, c=95.2), -1) == (False, True)


def test_bant_temasi_mum_engel_durumunun_bant_reddiyle_her_zaman_ayni_seyi_soyler():
    rng = random.Random(20261114)
    red_goruldu = 0
    for _ in range(600):
        d = rng.choice((1, -1))
        bantlar = []
        for _ in range(rng.randint(0, 3)):
            alt = round(rng.uniform(95.0, 105.0), 1)
            bantlar.append(_bant(alt, round(alt + rng.uniform(0.2, 3.0), 1), "bearish" if d == 1 else "bullish", h_atr=rng.choice((0.2, 0.8))))
        onceki = _temiz(0, c=round(rng.uniform(97.0, 103.0), 1), **{"blok_bear" if d == 1 else "blok_bull": tuple(bantlar)})
        alt, ust = sorted(round(rng.uniform(94.0, 106.0), 1) for _ in range(2))
        b = _temiz(1, h=ust, l=alt, c=round(rng.uniform(alt, ust), 1))
        red = kg.mum_engel_durumu(onceki, b, d, 2.0)["blok"] == "RED"
        assert any(kg.bant_temasi(onceki, b, d)) == red
        red_goruldu += red
    assert 50 < red_goruldu < 550


def test_formasyon_bozuk_mu_o_kapanisa_kadarki_son_formasyon_etiketine_bakar():
    iz = {1: ("FRM_TEYIT", "VP_LEHTE_BASKI"), 3: ("FRM_RETEST",), 5: ("FRM_RETEST_OK",), 7: ("SEVIYE_ICI", "FRM_BASARISIZ")}
    assert [kg.formasyon_bozuk_mu(iz, k) for k in range(0, 9)] == [False, False, False, True, True, False, False, True, True]
    assert kg.formasyon_bozuk_mu({}, 4) is False
    assert kg.formasyon_bozuk_mu({2: ("FRM_KARSI_KIRILIM",)}, 2) is True
    assert kg.formasyon_bozuk_mu({2: ("FRM_TEYITSIZ",), 3: ("FRM_KAYIP",)}, 3) is False       # formasyon izden düştü: bilinmiyor


def test_formasyon_bozulma_kumesi_surec_sozlugunun_aleyhte_formasyon_etiketleridir():
    from senaryo_v2.surec import ALEYHTE, OLAY_KUTBU

    assert kg.FRM_BOZULMA == {etiket for etiket, kutup in OLAY_KUTBU.items() if etiket.startswith("FRM_") and kutup == ALEYHTE}


def test_ters_yapi_kirilimi_yalniz_ters_yonlu_bos_ve_choch_sayar():
    assert kg.ters_yapi_kirilimi(_temiz(ms_olaylar=("EXT:BOS:-1",)), 1) == (True, False)
    assert kg.ters_yapi_kirilimi(_temiz(ms_olaylar=("INT:CHOCH:-1",)), 1) == (False, True)
    assert kg.ters_yapi_kirilimi(_temiz(ms_olaylar=("EXT:BOS:+1", "INT:CHOCH:+1")), 1) == (False, False)
    assert kg.ters_yapi_kirilimi(_temiz(ms_olaylar=("EXT:BOS:+1", "INT:CHOCH:+1")), -1) == (True, True)
    assert kg.ters_yapi_kirilimi(_temiz(ms_olaylar=("EXT:SWEEP:-1",)), 1) == (False, False)


def test_ters_supurme_motorun_ters_yonlu_supurme_ve_sahte_kirilim_olayini_sayar():
    assert kg.ters_supurme(_temiz(ms_olaylar=("EXT:SWEEP:-1",)), 1) is True
    assert kg.ters_supurme(_temiz(ms_olaylar=("INT:FALSE_BREAK:-1",)), 1) is True
    assert kg.ters_supurme(_temiz(ms_olaylar=("EXT:SWEEP:+1", "INT:BOS:-1")), 1) is False
    assert kg.ters_supurme(_temiz(ms_olaylar=("EXT:SWEEP:+1",)), -1) is True
    assert kg.ters_supurme(_temiz(), 1) is False


# ---------------------------------------------------------------------------
# Yol
# ---------------------------------------------------------------------------
def test_yol_esikleri_ilk_gorulen_mumu_ve_tepenin_ilk_mumunu_verir():
    assert kg.yol_esikleri([0.2, 0.6, 0.4, 1.2, 1.2]) == (1.2, 4, {"yarim": 2, "bir": 4})
    assert kg.yol_esikleri([0.5, 0.1]) == (0.5, 1, {"yarim": 1, "bir": None})        # eşik değeri dahildir
    assert kg.yol_esikleri([-0.3, -0.1]) == (0.0, 0, {"yarim": None, "bir": None})   # hiç lehte gitmedi
    assert kg.yol_esikleri([]) == (0.0, 0, {"yarim": None, "bir": None})


def _islem(**kw) -> dict:
    r = {
        "olay_id": "T1", "bar_index": 0, "yon": "long", "giris_gercek": 100.0, "stop": 98.0, "atr_tf": 2.0,
        "bar_20_intra_iptal": 3, "zemin_tavan": 99.0, "surec_izi": "1:FRM_TEYIT|2:VP_TERS_BASKI,FRM_RETEST",
        "cikis_turu": "STOP", "hedef_yolu_orani": 0.3,
    }
    r.update(kw)
    return r


def _yol() -> list:
    return [
        _temiz(0, c=100.0, r_level=101.0),
        _temiz(1, h=101.2, l=99.8, c=100.4, r_level=101.0),                              # 0.6 ATR gördü, Stabil'e değip döndü
        _temiz(2, o=100.3, h=100.6, l=98.6, c=98.8, r_level=101.0, ms_olaylar=("INT:CHOCH:-1", "EXT:SWEEP:-1")),   # tez seviyesinin altında kapattı
        _temiz(3, h=99.0, l=97.5, c=97.8, r_level=101.0, ms_olaylar=("EXT:BOS:-1",)),      # stop mumu
        _temiz(4, c=97.0),
    ]


def test_islem_ozellikleri_esik_tepe_ve_ara_olaylari_dogru_mumdan_okur():
    barlar = _yol()
    k = kg.islem_ozellikleri(_islem(bar_close_time=barlar[0].bar_close_time), barlar, None)
    assert (k["yol_mfe_atr"], k["k_tepe"], k["k_yarim"], k["k_bir"], k["k_cikis"]) == (0.6, 1, 1, None, 3)
    assert k["risk_atr"] == 1.0 and k["donus_atr"] == 1.6 and k["tepe_stop_mum"] == 2
    assert k["engel_giris_stabil_atr"] == 0.5 and k["engel_giris_ms_atr"] is None
    # Eşik mumu = tepe mumu: Stabil'e değdi, altında kapattı; aralığının yarısından fazlasını geri verdi.
    assert k["stabil_yarim"] == k["stabil_tepe"] == "RED"
    assert k["acik_atr_yarim"] == 0.2 and k["geri_verme_atr_yarim"] == 0.4 and k["fitil_yarim"] is True
    assert k["engel_onde_atr_yarim"] == 0.3
    assert k["sonraki_acilis_atr_yarim"] == 0.15          # eşik mumundan sonraki mumun açılışı 100.3
    assert k["frm_bozuk_yarim"] is False and k["frm_bozuk_tepe"] is False       # 1. kapanışta son etiket FRM_TEYIT; retest 2. mumda
    assert k["blok_disaridan_yarim"] is False and k["blok_iceride_yarim"] is False
    assert k["ters_supurme_yarim"] is False and k["ara_ters_supurme"] is True and k["sonra_ters_supurme_yarim"] is True
    assert k["seviye_ici_yarim"] is False and k["ters_ms_yarim"] is False
    # Tepeden stop öncesi son kapanışa (mum 1–2): iç yapı kırıldı, seviye içine kapandı, izde hacim ve formasyon etiketi var.
    assert k["ara_ters_ms_ic"] is True and k["ara_ters_ms_dis"] is False
    assert k["ara_seviye_ici"] is True and k["ara_frm_bozulma"] is True and k["ara_vp_ters"] is True and k["ara_engel_red"] is True
    assert k["son_kapanis_atr"] == -0.6
    assert k["stop_mumu_ters_ms"] is True            # stop mumundaki dış kırılım yalnız burada görünür
    assert k["sonra_ters_ms_ic_yarim"] is True
    assert "acik_atr_bir" not in k and k["endeks_tepe_stop"] is None


def test_islem_ozellikleri_hizasiz_seriyi_ve_anatomiyle_celiskiyi_reddeder():
    barlar = _yol()
    zaman = barlar[0].bar_close_time
    with pytest.raises(ValueError, match="hizalı değil"):
        kg.islem_ozellikleri(_islem(bar_close_time=zaman, giris_gercek=100.5), barlar, None)
    with pytest.raises(ValueError, match="hizalı değil"):
        kg.islem_ozellikleri(_islem(bar_close_time="2020-01-01T13:30:00+03:00"), barlar, None)
    with pytest.raises(ValueError, match="uyuşmuyor"):
        kg.islem_ozellikleri(_islem(bar_close_time=zaman, hedef_yolu_orani=0.5), barlar, None)


def test_islem_ozellikleri_hedefe_giden_islemde_tepe_dokumu_uretmez():
    barlar = _yol()
    k = kg.islem_ozellikleri(_islem(bar_close_time=barlar[0].bar_close_time, cikis_turu="HEDEF", hedef_yolu_orani=1.0), barlar, None)
    assert k["k_yarim"] == 1 and k["stabil_yarim"] == "RED"
    assert "stabil_tepe" not in k and "donus_atr" not in k


# ---------------------------------------------------------------------------
# Birincil gözlem ve fark aralığı
# ---------------------------------------------------------------------------
def test_birincil_neden_sabit_onceligi_uygular_ve_her_isleme_tek_etiket_verir():
    adlar = [a for a, _ in kg.NEDENLER[:-1]]
    satirlar = [dict.fromkeys(adlar, False)]                                  # hiçbiri
    for j, ad in enumerate(adlar):
        satirlar.append({a: (jj >= j) for jj, a in enumerate(adlar)})           # `ad` ve ondan sonrakilerin hepsi
    sonuc = kg.birincil_neden(pd.DataFrame(satirlar))
    assert sonuc.tolist() == ["ACIKLANAMAYAN", *adlar]


def test_neden_bayraklari_tepe_ve_ara_kolonlarindan_kurulur():
    g = pd.DataFrame(
        {
            "stabil_tepe": ["RED", "", "YAKIN", "", ""], "ms_tepe": ["", "ASILDI", "", "", ""], "blok_tepe": ["YAKIN", "", "", "", ""],
            "endeks_tepe_stop": [-1.0, -0.5, -0.49, np.nan, 2.0],
            "ara_ters_ms_dis": [False, False, False, True, False], "ara_ters_ms_ic": [False] * 5, "ara_seviye_ici": [False] * 5,
            "ara_frm_bozulma": [False] * 5, "ara_vp_ters": [False, False, True, False, False], "zayif_sonuc_tepe": [False] * 5,
            "cikis_turu": ["STOP", "STOP", "STOP", "STOP", "STOP_BOSLUK"],
        }
    )
    bay = kg.neden_bayraklari(g)
    assert bay["ENGEL"].tolist() == [True, False, False, False, False]
    assert bay["ENGEL_YAKIN"].tolist() == [False, False, True, False, False]      # RED varken YAKIN sayılmaz
    assert bay["ENDEKS"].tolist() == [True, True, False, False, False]
    assert kg.birincil_neden(bay).tolist() == ["ENGEL", "ENDEKS", "ENGEL_YAKIN", "YAPI", "BOSLUK"]


def _kodlar(n: int) -> dict[str, np.ndarray]:
    return {"sembol": np.arange(n) % 11, "hafta": np.arange(n) // 5}


def test_fark_araligi_gercek_farki_yakalar_farksizlikta_sifiri_icerir_ve_tekrarlanabilirdir():
    rng = np.random.default_rng(11)
    n = 400
    f = (np.arange(n) % 2 == 0).astype(float)
    ayrik = np.where(f == 1, rng.random(n) < 0.8, rng.random(n) < 0.3).astype(float)
    alt, ust = kg.fark_araligi(_kodlar(n), f, ayrik)
    assert 0.3 < alt < 0.5 < ust < 0.7
    assert kg.fark_araligi(_kodlar(n), f, ayrik) == (alt, ust)
    ayni = (rng.random(n) < 0.5).astype(float)
    alt0, ust0 = kg.fark_araligi(_kodlar(n), f, ayni)
    assert alt0 < 0 < ust0
    # Özelliğin hiç görülmediği veride aralık ölçülemez.
    assert kg.fark_araligi(_kodlar(n), np.zeros(n), ayni) == (None, None)


def _kohort(n: int = 200) -> pd.DataFrame:
    gun = pd.date_range("2025-01-06", periods=n, freq="B")
    var = np.arange(n) % 2 == 0
    stop = np.where(var, np.arange(n) % 10 < 8, np.arange(n) % 10 < 2)       # varken %80, yokken %20 stop
    return pd.DataFrame(
        {
            "sembol": [f"S{i % 9}" for i in range(n)],
            "bar_close_time": [f"{g.date()}T18:30:00+03:00" for g in gun],
            "donem": np.where(np.arange(n) < n // 2, "kesif", "dogrulama"),
            "sonuc": np.where(stop, "STOP", "HEDEF"),
            sa.NET: np.where(stop, -1.0, 1.5),
            "var": var,
            "bilinen": np.arange(n) % 4 != 3,
        }
    )


def test_ozellik_satiri_oranlari_paydayi_ve_karari_dogru_kurar():
    koh = _kohort()
    r = kg.ozellik_satiri(koh, "X", "deneme", koh["var"])
    assert (r["var_n"], r["yok_n"], r["bilinen_n"]) == (100, 100, 200)
    assert r["var_stop_pay"] == 0.8 and r["yok_stop_pay"] == 0.2 and r["fark"] == pytest.approx(0.6)
    assert r["stoplarda_pay"] == 0.8 and r["hedefte_pay"] == 0.2
    assert r["var_net"] == pytest.approx(-0.5) and r["yok_net"] == pytest.approx(1.0)
    assert r["fark_alt"] > 0 and r["karar"] == "AYIRIYOR"
    # Bilinmeyenler paydadan düşer.
    b = kg.ozellik_satiri(koh, "X", "deneme", koh["var"], koh["bilinen"])
    assert b["bilinen_n"] == 150 and b["var_n"] + b["yok_n"] == 150
    # Az görülen gözlem sayılmaz; iki dönemde yön değiştiren fark ayırmıyor sayılır.
    az = kg.ozellik_satiri(koh, "X", "deneme", pd.Series(np.arange(len(koh)) < 10, index=koh.index))
    assert az["karar"] == "SAYILMAZ_N<30" and az["fark_alt"] is None
    donen = koh.copy()
    ikinci = donen["donem"] == "dogrulama"
    donen.loc[ikinci, "sonuc"] = np.where(donen.loc[ikinci, "sonuc"] == "STOP", "HEDEF", "STOP")
    assert kg.ozellik_satiri(donen, "X", "deneme", donen["var"])["karar"] == "AYIRMIYOR"


def test_cikis_karsi_olgusu_yalniz_gozlemin_goruldugu_islemi_degistirir():
    koh = _kohort()
    fark = pd.Series(np.where(koh["var"], 0.5, np.nan), index=koh.index)      # gözlem yoksa fark bilinmez; kullanılmaz da
    c = kg.cikis_karsi_olgusu(koh, koh["var"], fark)
    assert c["etkilenen_n"] == 100 and c["etkilenen_ort"] == pytest.approx(0.5)
    assert c["kume_ort"] == pytest.approx(0.25) and c["kume_toplam"] == pytest.approx(50.0)
    assert c["kesif_ort"] == pytest.approx(0.25) and c["dogrulama_ort"] == pytest.approx(0.25)
    assert c["en_kotu_alt"] > 0 and c["karar"] == "GECTI"                     # iki dönemde 50'şer etkilenen, hepsi +0.5
    zarar = kg.cikis_karsi_olgusu(koh, koh["var"], -fark)
    assert zarar["karar"] == "ZARARLI" and zarar["kume_ort"] == pytest.approx(-0.25)
    az = kg.cikis_karsi_olgusu(koh, pd.Series(np.arange(len(koh)) < 10, index=koh.index), pd.Series(0.5, index=koh.index))
    assert az["etkilenen_n"] == 10 and az["karar"] == "SAYILMAZ_N<30"
    with pytest.raises(ValueError, match="hesaplanamıyor"):
        kg.cikis_karsi_olgusu(koh, ~koh["var"], fark)


def test_ozellikleri_ekle_bire_bir_eslesmeyen_ya_da_cakisan_tabloyu_reddeder():
    df = pd.DataFrame({"olay_id": ["a", "b", "c"], "sembol": ["S", "S", "T"]})
    ek = pd.DataFrame({"olay_id": ["c", "a", "b"], "k_tepe": [3, 1, 2]})
    out = kg.ozellikleri_ekle(df, ek)
    assert out["olay_id"].tolist() == ["a", "b", "c"] and out["k_tepe"].tolist() == [1, 2, 3]       # sıra anatomi tablosununki
    with pytest.raises(ValueError, match="bire bir"):
        kg.ozellikleri_ekle(df, ek.iloc[:2])
    with pytest.raises(ValueError, match="bire bir"):
        kg.ozellikleri_ekle(df, ek.assign(olay_id=["c", "a", "x"]))
    with pytest.raises(ValueError, match="bire bir"):
        kg.ozellikleri_ekle(df, ek.assign(olay_id=["a", "a", "b"]))
    with pytest.raises(ValueError, match="çakışıyor"):
        kg.ozellikleri_ekle(df, ek.assign(sembol="S"))


def test_hazirla_mumdan_okunan_esik_anatomiyle_celisirse_durur():
    df = pd.DataFrame(
        {
            "cikis_turu": ["STOP", "STOP", "HEDEF", "SURE", "SURE"], "hedef_yolu_orani": [0.1, 0.6, 1.0, 0.5, 0.2],
            "kar": [False, False, True, True, False], "k_yarim": [np.nan, 2, 1, 3, np.nan], "k_bir": [np.nan, 4, 2, 5, np.nan],
            "engel_giris_stabil_atr": [1.5, np.nan, np.nan, 0.4, np.nan], "engel_giris_ms_atr": [0.7, np.nan, 2.5, 0.9, np.nan],
            "engel_giris_blok_atr": [np.nan, np.nan, 3.0, 0.0, np.nan],
            "risk_atr": [1.0, 2.0, 1.0, 0.5, 1.0], "masraf_r": [0.1, 0.05, 0.1, 0.2, 0.1], sa.NET: [-1.1, -1.05, 1.9, 0.6, -0.4],
            "sonraki_acilis_atr_yarim": [np.nan, 0.4, 0.6, 0.3, np.nan], "sonraki_acilis_atr_bir": [np.nan, 1.0, 1.2, 0.8, np.nan],
        }
    )
    out = kg.hazirla(df)
    # Erken çıkış farkı = (sonraki açılış ATR / risk ATR − masraf) − gerçekleşen net R; eşiği görmeyende boş.
    np.testing.assert_allclose(out["erken_cikis_fark_yarim"][1:4], [0.2 - 0.05 + 1.05, 0.6 - 0.1 - 1.9, 0.6 - 0.2 - 0.6])
    assert out["erken_cikis_fark_yarim"][[0, 4]].isna().all()
    assert out["sonuc"].tolist() == ["STOP", "STOP", "HEDEF", "SURE_KAR", "SURE_ZARAR"]
    assert out["engel_giris_atr"].fillna(-1).tolist() == [0.7, -1, 2.5, 0.0, -1]
    assert [r["n"] for r in kg.giris_engeli_tablosu(out.assign(sembol="S", bar_close_time="2025-01-06T18:30:00+03:00", donem="kesif"))] == [2, 0, 3]
    with pytest.raises(ValueError, match="uyuşmuyor"):
        kg.hazirla(df.assign(k_yarim=[1, 2, 1, 3, np.nan]))


# ---------------------------------------------------------------------------
# Üretilmiş çıktı
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def cikti() -> tuple[dict, pd.DataFrame]:
    if not (CIKTI / "ozet.json").exists():
        pytest.skip("kar_gorup_donen çıktısı üretilmemiş")
    return json.loads((CIKTI / "ozet.json").read_text(encoding="utf-8")), pd.read_csv(CIKTI / "islemler.csv.gz", low_memory=False)


def test_cikti_birincil_gozlemler_ve_akibetler_gruplari_tam_boler(cikti):
    ozet, _ = cikti
    assert [x["neden"] for x in ozet["meta"]["nedenler"]] == [a for a, _ in kg.NEDENLER]
    for kume, v in ozet["kumeler"].items():
        assert v["dogrudan_stop_n"] + v["esikler"]["yarim"]["donus"]["n"] == v["stop_n"], kume
        assert v["esikler"]["bir"]["donus"]["n"] <= v["esikler"]["yarim"]["donus"]["n"]
        assert sum(r["n"] for r in v["giris_engeli"]) == v["n"]
        for ad, e in v["esikler"].items():
            ko, dn = e["kohort"], e["donus"]
            assert sum(s["n"] for s in ko["sonuclar"]) == ko["n"], (kume, ad)
            assert next(s["n"] for s in ko["sonuclar"] if s["sonuc"] == "STOP") == dn["n"]
            assert sum(r["birincil_n"] for r in dn["nedenler"]) == dn["n"]
            assert sum(x["n"] for a, x in dn["tepe_stop_mum"].items() if a != "medyan") == dn["n"]
            assert dn["kesif_n"] + dn["dogrulama_n"] == dn["n"]
            for r in dn["nedenler"]:
                assert r["tek_basina_n"] <= r["gorulen_n"] and r["birincil_n"] <= r["gorulen_n"]
            # Bant reddi ya dışarıdan gelir ya da zaten içindedir; ikisi birlikte bandı tam böler.
            assert dn["bant_disaridan"]["n"] + dn["bant_yalniz_iceride"]["n"] == dn["engel_alan"]["blok"]["n"]
            assert dn["engel_yalniz_bant_ici"]["n"] <= dn["bant_yalniz_iceride"]["n"]
            satir = {r["ozellik"]: r for r in ko["esik_ani"]}
            assert len(satir) - 1 == kg.GOZLEM_N == ozet["meta"]["gozlem_n"] and kg.SONRADAN_EKLENEN <= set(satir)
            assert all(r["aciklama"].endswith("†") == (r["ozellik"] in kg.SONRADAN_EKLENEN) for r in ko["esik_ani"])
            assert satir["HER_ISLEM"]["var_n"] == ko["n"] and satir["HER_ISLEM"]["cikis"]["etkilenen_n"] == ko["n"]
            assert satir["BLOK_DISARIDAN"]["var_n"] + satir["BLOK_ICERIDE"]["var_n"] == satir["BLOK_RED"]["var_n"]
            for r in ko["esik_ani"]:
                assert r["cikis"]["etkilenen_n"] == r["var_n"]
                assert r["cikis"]["karar"] in {"GECTI", "UMUT_VAR", "ZAYIF_ARTI", "GECMEDI", "ZARARLI", "SAYILMAZ_N<30"}
            for r in [*ko["esik_ani"], *ko["sonra"]]:
                assert r["var_n"] + r["yok_n"] == r["bilinen_n"] <= ko["n"]
                assert r["karar"] in {"AYIRIYOR", "ZAYIF", "AYIRMIYOR", "SAYILMAZ_N<30"}
                if r["karar"] == "AYIRIYOR":
                    assert r["fark_alt"] > 0 or r["fark_ust"] < 0


def test_cikti_rapor_ozetten_yeniden_uretilebilir_ve_bos_akibet_sutunu_gostermez(cikti):
    ozet, _ = cikti
    metin = kg._markdown(ozet)
    assert metin == (CIKTI / "RAPOR.md").read_text(encoding="utf-8")
    assert "## Kısa özet" in metin and "Kümeler yan yana" in metin
    tez_iptali_var = any(
        s["n"] for v in ozet["kumeler"].values() for e in v["esikler"].values() for s in e["kohort"]["sonuclar"] if s["sonuc"] == "TEZ_IPTAL"
    )
    assert ("| Tez iptali |" in metin) == tez_iptali_var


def test_cikti_erken_cikis_karsi_olgusu_islem_tablosundan_yeniden_hesaplanir(cikti):
    ozet, df = cikti
    d7 = df[df["kalite_katmani"] == "A_ARTI"]
    for ad in kg.ESIKLER:
        koh = d7[d7[f"k_{ad}"].notna()]
        satir = {r["ozellik"]: r for r in ozet["kumeler"]["D7_A_Arti"]["esikler"][ad]["kohort"]["esik_ani"]}
        tum = satir["HER_ISLEM"]["cikis"]
        assert koh[f"erken_cikis_fark_{ad}"].notna().all()
        assert tum["kume_toplam"] == pytest.approx(koh[f"erken_cikis_fark_{ad}"].sum(), abs=0.01)
        assert tum["etkilenen_ort"] == pytest.approx(koh[f"erken_cikis_fark_{ad}"].mean(), abs=1e-5)
        fitil = koh[koh[f"fitil_{ad}"].eq(True)]
        assert satir["FITIL"]["cikis"]["kume_toplam"] == pytest.approx(fitil[f"erken_cikis_fark_{ad}"].sum(), abs=0.01)
        assert satir["FITIL"]["var_stop_pay"] == pytest.approx((fitil["sonuc"] == "STOP").mean(), abs=1e-6)


def test_cikti_gruplar_endeks_filtresi_ve_sonuc_anatomisiyle_ayni(cikti):
    ozet, df = cikti
    assert len(df) == ozet["meta"]["islem_n"] and df["olay_id"].is_unique
    d7 = df[df["kalite_katmani"] == "A_ARTI"]
    v = ozet["kumeler"]["D7_A_Arti"]
    assert (len(d7), int((d7["sonuc"] == "STOP").sum())) == (v["n"], v["stop_n"])
    assert int(d7["yarim_atr_stop"].sum()) == v["esikler"]["yarim"]["donus"]["n"]
    # Stop olanlarda mumdan okunan en iyi nokta, anatomi kaynaklı ATR ölçüsüyle aynıdır.
    stop = df["sonuc"] == "STOP"
    assert (df.loc[stop, "yol_mfe_atr"] - df.loc[stop, "stop_mfe_atr"]).abs().max() <= 3e-4
    assert (df.loc[stop, "k_yarim"].notna() == df.loc[stop, "yarim_atr_stop"]).all()
    for dosya in ("endeks_filtresi", "sonuc_anatomisi"):
        if not (KOK / dosya / "islemler.csv.gz").exists():
            continue
        diger = pd.read_csv(KOK / dosya / "islemler.csv.gz", low_memory=False).set_index("olay_id").loc[df["olay_id"]]
        assert (diger["cikis_turu"].to_numpy() == df["cikis_turu"].to_numpy()).all()
        if dosya == "endeks_filtresi":
            assert (diger["yarim_atr_stop"].to_numpy() == df["yarim_atr_stop"].to_numpy()).all()
            assert (diger["bir_atr_stop"].to_numpy() == df["bir_atr_stop"].to_numpy()).all()
    assert ef.ESIK_YARIM_ATR == kg.ESIKLER["yarim"] and ef.ESIK_BIR_ATR == kg.ESIKLER["bir"]
