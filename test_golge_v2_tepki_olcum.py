"""Gölge v2 tepki ölçümü testleri: tetikler, tetik izi, tepki politikası, özet ve çıktının iç tutarlılığı."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research import golge_v2_kar_gorup_donen as kg
from research import golge_v2_tepki_olcum as tp
from test_golge_v2_birim import _bar
from test_golge_v2_kar_gorup_donen import _bant, _temiz
from test_golge_v2_surec import _yaris

KOK = Path(__file__).resolve().parent / "docs/arastirma/sonuclar/golge_v2"
CIKTI = KOK / "tepki_olcum"


# ---------------------------------------------------------------------------
# Tetikler
# ---------------------------------------------------------------------------
def _tetik(onceki, b, olaylar=(), *, d=1, endeks=None):
    return tp.bar_tetikleri(onceki, b, olaylar, d=d, atr=2.0, endeks_yuzde=endeks)


def test_bar_tetikleri_engel_alanlarini_etiketleri_ve_endeksi_ayri_ayri_okur():
    bos = _temiz(0, c=100.0)
    sakin = _temiz(1, h=100.4, l=99.6, c=100.2)
    assert _tetik(bos, sakin) == frozenset()
    stabil = _temiz(0, c=100.0, r_level=103.0)
    assert _tetik(stabil, _temiz(1, h=103.4, l=99.5, c=102.0)) == {"STABIL", "ENGEL", "HERHANGI"}
    assert _tetik(stabil, _temiz(1, h=104.0, l=99.5, c=103.5)) == frozenset()                  # kapanışla aştı: tetik değil
    ikisi = _temiz(0, c=100.0, ms_unbroken_highs=(103.0,), blok_bear=(_bant(102.0, 104.0),))
    assert _tetik(ikisi, _temiz(1, h=103.5, l=99.5, c=102.5)) == {"MS", "BLOK", "ENGEL", "HERHANGI"}
    assert _tetik(bos, sakin, ("SEVIYE_ICI", "FRM_TEYIT")) == {"SEVIYE_ICI", "HERHANGI"}
    assert _tetik(bos, sakin, ("FRM_RETEST",)) == {"FRM", "HERHANGI"}
    assert _tetik(bos, sakin, ("FRM_RETEST_OK", "VP_LEHTE_BASKI")) == frozenset()            # lehte etiketler tetik değil
    assert _tetik(bos, sakin, ("VP_TERS_BASKI",)) == {"VP_TERS", "HERHANGI"}
    supurme = _temiz(1, h=100.4, l=99.6, c=100.2, ms_olaylar=("EXT:SWEEP:-1",))
    assert _tetik(bos, supurme) == {"MS_SUPURME", "HERHANGI"}
    assert _tetik(bos, supurme, d=-1) == frozenset()                                           # short için lehte süpürme


def test_bar_tetikleri_endeks_esigi_dahildir_ve_endeks_domain_sayilmaz():
    bos, sakin = _temiz(0, c=100.0), _temiz(1, h=100.4, l=99.6, c=100.2)
    assert _tetik(bos, sakin, endeks=-0.5) == {"ENDEKS"}                # eşik dahil; HERHANGI yanmaz
    assert _tetik(bos, sakin, endeks=-0.49) == frozenset()
    assert _tetik(bos, sakin, endeks=2.0) == frozenset()
    assert _tetik(bos, sakin, ("VP_TERS_BASKI",), endeks=-1.2) == {"VP_TERS", "HERHANGI", "ENDEKS"}
    assert set(tp.DOMAIN_TURLERI) < set(tp.TETIKLER) and "ENDEKS" not in tp.DOMAIN_TURLERI


def _f(*adlar: str) -> frozenset[str]:
    return frozenset(adlar)


KAPANISLAR = [
    (1, 0.3, _f("ENGEL", "MS", "HERHANGI")),             # eşikten önce: sayılmaz
    (2, 0.6, _f()),                                        # 0.5 ATR görüldü, tetik yok
    (3, 0.6, _f("VP_TERS", "HERHANGI")),
    (4, 1.1, _f("ENDEKS")),                                # 1 ATR görüldü
    (5, 1.1, _f("SEVIYE_ICI", "HERHANGI", "ENDEKS")),
]


def test_tetik_izi_yalniz_esikten_sonraki_ilk_tetigi_sayar():
    iz = tp.tetik_izi(KAPANISLAR)
    y, b = iz["yarim"], iz["bir"]
    assert y["ESIK"] == y["HER_ISLEM"] == 2 and b["ESIK"] == b["HER_ISLEM"] == 4
    assert y["ENGEL"] is None and y["MS"] is None                        # eşikten önceki ret tetik değildir
    assert (y["VP_TERS"], y["HERHANGI"], y["ENDEKS"], y["SEVIYE_ICI"]) == (3, 3, 4, 5)
    assert y["IKI_FARKLI"] == 5                                          # hacim (3) + tez seviyesi (5)
    assert b["VP_TERS"] is None and (b["ENDEKS"], b["SEVIYE_ICI"], b["HERHANGI"]) == (4, 5, 5)
    assert b["IKI_FARKLI"] is None                                       # 1 ATR'den beri tek tür
    assert set(y) == {"ESIK", *tp.TETIKLER}


def test_tetik_izi_nedenseldir_gelecek_kapanislar_gecmis_karari_degistirmez():
    tam = tp.tetik_izi(KAPANISLAR)
    for n in range(len(KAPANISLAR) + 1):
        kismi = tp.tetik_izi(KAPANISLAR[:n])
        for esik in tp.ESIKLER:
            for tetik, k in tam[esik].items():
                assert kismi[esik][tetik] == (k if k is not None and k <= n else None), (n, esik, tetik)


def test_tetik_izi_esik_degeri_dahildir_ve_ayni_mumdaki_iki_tur_yeter():
    iz = tp.tetik_izi([(1, 0.5, _f("ENGEL", "BLOK", "VP_TERS", "HERHANGI")), (2, 1.0, _f())])
    assert iz["yarim"]["ESIK"] == 1 and iz["bir"]["ESIK"] == 2
    assert iz["yarim"]["IKI_FARKLI"] == 1                                 # engel + hacim aynı mumda
    assert iz["yarim"]["BLOK"] == 1 and iz["bir"]["BLOK"] is None
    bos = tp.tetik_izi([])
    assert all(v is None for esik in bos.values() for v in esik.values())
    # Aynı tür iki kez görülürse "iki farklı tür" sayılmaz (ENGEL alt alanları tek türdür).
    tek = tp.tetik_izi([(1, 0.6, _f("ENGEL", "MS", "HERHANGI")), (2, 0.6, _f("ENGEL", "BLOK", "STABIL", "HERHANGI"))])
    assert tek["yarim"]["IKI_FARKLI"] is None


def test_varyant_izgarasi_esik_tetik_tepki_carpimidir():
    assert len(tp.VARYANTLAR) == len(tp.ESIKLER) * len(tp.TETIKLER) * len(tp.TEPKILER) == 48
    assert set(tp.VARYANTLAR.values()) == {(e, t, r) for e in tp.ESIKLER for t in tp.TETIKLER for r in tp.TEPKILER}
    assert tp.VARYANTLAR["yarim_seviye_ici_cik"] == ("yarim", "SEVIYE_ICI", "cik")
    assert tp.ESIKLER == kg.ESIKLER and next(iter(tp.TETIKLER)) == "HER_ISLEM"


# ---------------------------------------------------------------------------
# Tepki politikası (motorla)
# ---------------------------------------------------------------------------
def _donen_yol():
    """Long 100 / stop 98 / hedef 104: önce +0.75 ATR görür, sonra girişin altına inip stop olur."""
    return [
        _bar(0, o=99.8, h=100.2, l=99.6, c=100.0),
        _bar(1, o=100.2, h=101.5, l=99.8, c=101.2),
        _bar(2, o=101.0, h=101.3, l=100.4, c=100.6),
        _bar(3, o=100.5, h=100.7, l=99.2, c=99.5),
        _bar(4, o=99.4, h=99.6, l=97.5, c=97.8),
        _bar(5, o=97.8, h=98.0, l=97.0, c=97.5),
    ]


def _tepki(barlar, k, tepki):
    return _yaris(barlar, politikalar=(tp.KapanistaTepki(k, tepki),), cikis_modu=tp.TEPKILER[tepki][1])


def test_tepki_cik_sonraki_acilista_cikar_ve_karardan_onceki_yol_bazla_aynidir():
    barlar = _donen_yol()
    baz = _yaris(barlar)
    assert (baz.neden, baz.cozulme_offset, baz.pnl_r) == ("STOP", 4, -1.0)
    for k, acilis in ((1, 101.0), (2, 100.5), (3, 99.4)):
        iz = _tepki(barlar, k, "cik")
        assert (iz.neden, iz.cozulme_offset, iz.cikis_fiyat) == ("TEPKI_CIK", k + 1, acilis)
        assert iz.gozlemler == baz.gozlemler[:k]                         # o kapanışa kadar aynı gözlemler
    # Çıkış mumunun kapanışında (işlem zaten bitmiş) tepki hiçbir şeyi değiştirmez.
    assert _tepki(barlar, 4, "cik") == baz


def test_tepki_basabas_stopu_girise_ceker_ve_sonraki_mumdan_gecerlidir():
    barlar = _donen_yol()
    for k in (1, 2):                                                     # fiyat hâlâ girişin üstünde: girişte çıkılır
        iz = _tepki(barlar, k, "basabas")
        assert (iz.neden, iz.cozulme_offset, iz.cikis_fiyat, iz.pnl_r) == ("IZ_STOP", 3, 100.0, 0.0)
        assert iz.stop_tasindi and iz.stop_son == 100.0
    # Karar anında fiyat girişin altındaysa stop fiyatın ötesinde kalır: sonraki açılışta çıkılır.
    alt = _tepki(barlar, 3, "basabas")
    assert (alt.neden, alt.cozulme_offset, alt.cikis_fiyat) == ("IZ_STOP_GAP", 4, 99.4)
    assert alt.cikis_fiyat == _tepki(barlar, 3, "cik").cikis_fiyat


def test_tepki_basabas_fiyat_girise_donmezse_sonucu_degistirmez_donerse_kazanani_keser():
    hedefe = [
        _bar(0, o=99.8, h=100.2, l=99.6, c=100.0),
        _bar(1, o=100.2, h=101.5, l=100.1, c=101.2),
        _bar(2, o=101.2, h=104.5, l=101.0, c=104.2),
    ]
    baz = _yaris(hedefe)
    assert (baz.neden, baz.pnl_r) == ("HEDEF", 2.0)
    basabas = _tepki(hedefe, 1, "basabas")
    assert (basabas.neden, basabas.pnl_r, basabas.cozulme_offset) == ("HEDEF", 2.0, 2)
    assert _tepki(hedefe, 1, "cik").pnl_r == pytest.approx(0.6)          # açılış 101.2: kazananın kârı kesilir
    # Girişe değip sonra hedefe giden işlem: baz hedef, başa baş stopu girişte keser.
    donup_giden = [
        _bar(0, o=99.8, h=100.2, l=99.6, c=100.0),
        _bar(1, o=100.2, h=101.5, l=100.1, c=101.2),
        _bar(2, o=101.0, h=101.2, l=99.7, c=100.8),
        _bar(3, o=100.9, h=104.6, l=100.7, c=104.3),
    ]
    assert _yaris(donup_giden).neden == "HEDEF"
    kesilen = _tepki(donup_giden, 1, "basabas")
    assert (kesilen.neden, kesilen.cozulme_offset, kesilen.pnl_r) == ("IZ_STOP", 2, 0.0)
    # Aynı mumda hem giriş hem hedef görülürse sıra bilinmez: stop sayılır (muhafazakâr).
    ayni_mum = [
        _bar(0, o=99.8, h=100.2, l=99.6, c=100.0),
        _bar(1, o=100.2, h=101.5, l=100.1, c=101.2),
        _bar(2, o=101.0, h=104.5, l=99.9, c=104.0),
    ]
    assert _yaris(ayni_mum).neden == "HEDEF"
    assert _tepki(ayni_mum, 1, "basabas").neden == "IZ_STOP"


def test_kapanista_tepki_bilinmeyen_tepkiyi_reddeder():
    with pytest.raises(ValueError, match="Bilinmeyen tepki"):
        tp.KapanistaTepki(1, "yarisini_sat")


def test_kapanis_dizisi_cikis_mumunda_kesilir_ve_en_iyi_noktayi_biriktirir():
    barlar = _donen_yol()
    baz = _yaris(barlar)
    dizi = tp.kapanis_dizisi(barlar, baz.gozlemler, dolum_idx=0, cikis_k=baz.cozulme_offset, d=1, giris=100.0, atr=2.0, endeks=None)
    assert [k for k, _, _ in dizi] == [1, 2, 3]                          # 4. mum çıkış mumudur
    assert [round(m, 4) for _, m, _ in dizi] == [0.75, 0.75, 0.75]       # en iyi nokta geri gitmez
    assert all(yanan == frozenset() for _, _, yanan in dizi)             # kapanışlar tez seviyesinin (99.0) üstünde
    iz = tp.tetik_izi(dizi)
    assert iz["yarim"]["ESIK"] == 1 and iz["bir"]["ESIK"] is None and iz["yarim"]["HERHANGI"] is None
    # Tez seviyesinin içine kapanan mum gözcünün etiketiyle tetik olur; karşı Stabil'e takılan mum engel tetiğidir.
    icine = [barlar[0], barlar[1], _bar(2, o=101.0, h=101.3, l=98.6, c=98.8), _bar(3, o=98.7, h=98.9, l=97.5, c=97.8)]
    baz2 = _yaris(icine)
    dizi2 = tp.kapanis_dizisi(icine, baz2.gozlemler, dolum_idx=0, cikis_k=baz2.cozulme_offset, d=1, giris=100.0, atr=2.0, endeks=None)
    assert [k for k, _, _ in dizi2] == [1, 2] and dizi2[1][2] == {"SEVIYE_ICI", "HERHANGI"}
    assert tp.tetik_izi(dizi2)["yarim"]["SEVIYE_ICI"] == 2
    takilan = [_bar(0, o=99.8, h=100.2, l=99.6, c=100.0, r_level=101.4), _bar(1, o=100.2, h=101.5, l=99.8, c=101.2, r_level=101.4), barlar[2], barlar[3], barlar[4]]
    baz3 = _yaris(takilan)
    dizi3 = tp.kapanis_dizisi(takilan, baz3.gozlemler, dolum_idx=0, cikis_k=baz3.cozulme_offset, d=1, giris=100.0, atr=2.0, endeks=None)
    assert dizi3[0][2] == {"STABIL", "ENGEL", "HERHANGI"} and tp.tetik_izi(dizi3)["yarim"]["ENGEL"] == 1
    # Süre sonunda kapanan işlemde son mumun kapanışı diziye girmez.
    yatay = [_bar(i, o=100.2, h=100.9, l=99.9, c=100.3) for i in range(12)]
    sure = _yaris(yatay)
    assert sure.neden == "ZAMAN_STOPU" and len(sure.gozlemler) == 10
    assert len(tp.kapanis_dizisi(yatay, sure.gozlemler, dolum_idx=0, cikis_k=sure.cozulme_offset, d=1, giris=100.0, atr=2.0, endeks=None)) == 9
    with pytest.raises(ValueError, match="ardışık"):
        tp.kapanis_dizisi(barlar, baz.gozlemler[1:], dolum_idx=0, cikis_k=4, d=1, giris=100.0, atr=2.0, endeks=None)


# ---------------------------------------------------------------------------
# Özet
# ---------------------------------------------------------------------------
def _sentetik(n: int = 120) -> pd.DataFrame:
    """Her işlemde tetik 2. kapanışta yanar; tepki stop olacakları +0.5 R iyileştirir, hedefe gidecekleri −1.2 R keser."""
    gun = pd.date_range("2025-01-06", periods=n, freq="B")
    i = np.arange(n)
    tetikli = i % 2 == 0
    stop = i % 4 < 2                                                      # yarısı stop, yarısı hedef
    baz = np.where(stop, -1.1, 1.9)
    fark = np.where(tetikli, np.where(stop, 0.5, -1.2), 0.0)
    df = pd.DataFrame(
        {
            "sembol": [f"S{j % 9}" for j in i],
            "donem": np.where(i < n // 2, "kesif", "dogrulama"),
            "bar_close_time": [f"{g.date()}T18:30:00+03:00" for g in gun],
            "baz_net": baz,
            "baz_neden": np.where(stop, "STOP", "HEDEF"),
            "baz_bar": 6,
        }
    )
    for esik in tp.ESIKLER:
        df[f"k_esik_{esik}"] = 1.0
        for tetik in tp.TETIKLER:
            if tetik != "HER_ISLEM":
                df[f"tk_{esik}_{tetik}"] = np.where(tetikli, 2.0, np.nan)
    ad = "yarim_seviye_ici_cik"
    df[f"{ad}_net"] = baz + fark
    df[f"{ad}_neden"] = np.where(tetikli, "TEPKI_CIK", df["baz_neden"])
    df[f"{ad}_bar"] = np.where(tetikli, 3, 6)
    return df


def test_varyant_ozeti_farki_baz_sonuca_gore_boler_ve_kazanani_kesen_tepkiyi_gecirmez():
    df = _sentetik()
    v = tp.varyant_ozeti(df, "yarim_seviye_ici_cik")
    assert (v["esik"], v["tetik"], v["tepki"]) == ("yarim", "SEVIYE_ICI", "cik")
    assert v["tetiklenen_n"] == v["etkilenen_n"] == 60 and (v["kesif_etkilenen_n"], v["dogrulama_etkilenen_n"]) == (30, 30)
    assert (v["iyilesen_n"], v["kotulesen_n"]) == (30, 30)
    assert v["dokum"] == {"STOP": {"n": 30, "toplam_r": 15.0}, "HEDEF": {"n": 30, "toplam_r": -36.0}, "DIGER": {"n": 0, "toplam_r": 0.0}}
    assert v["fark_toplam"] == pytest.approx(-21.0) and v["fark_ort"] == pytest.approx(-21.0 / 120)
    assert v["karar"] in {"GECMEDI", "ZARARLI"}
    # Aynı tepki yalnız stop olacaklara dokunsaydı geçerdi.
    hedefsiz = df.copy()
    hedef = hedefsiz["baz_neden"] == "HEDEF"
    hedefsiz.loc[hedef, "yarim_seviye_ici_cik_net"] = hedefsiz.loc[hedef, "baz_net"]
    hedefsiz.loc[hedef, "yarim_seviye_ici_cik_neden"] = "HEDEF"
    hedefsiz.loc[hedef, "yarim_seviye_ici_cik_bar"] = 6
    iyi = tp.varyant_ozeti(hedefsiz, "yarim_seviye_ici_cik")
    assert iyi["etkilenen_n"] == 30 and iyi["tetiklenen_n"] == 60 and iyi["dokum"]["HEDEF"]["n"] == 0
    assert iyi["fark_en_kotu_alt"] > 0 and iyi["karar"] == "ZAYIF_ARTI"   # dönem başına 15 işlem: 30'dan az


def test_varyant_ozeti_tetik_yanmadan_degisen_sonucu_reddeder_ve_baz_sonucu_uce_indirger():
    df = _sentetik()
    df.loc[1, "yarim_seviye_ici_cik_net"] += 0.3                           # 1. satırda tetik yok
    with pytest.raises(ValueError, match="tetik yanmadan"):
        tp.varyant_ozeti(df, "yarim_seviye_ici_cik")
    neden = pd.Series(["STOP", "STOP_GAP", "HEDEF", "ZAMAN_STOPU", "TEZ_IPTAL_BOS"])
    assert tp.baz_sonucu(neden).tolist() == ["STOP", "STOP", "HEDEF", "DIGER", "DIGER"]
    assert tp.tetik_kapanisi(df, "yarim", "HER_ISLEM").eq(1.0).all()
    assert tp.tetik_kapanisi(df, "bir", "ENGEL").notna().sum() == 60


# ---------------------------------------------------------------------------
# Üretilmiş çıktı
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def cikti() -> tuple[dict, pd.DataFrame]:
    if not (CIKTI / "ozet.json").exists():
        pytest.skip("tepki_olcum çıktısı üretilmemiş")
    return json.loads((CIKTI / "ozet.json").read_text(encoding="utf-8")), pd.read_csv(CIKTI / "islemler.csv.gz", low_memory=False)


def test_cikti_baz_sonuclar_ana_rapor_ve_surec_olcumle_islem_islem_ayni(cikti):
    ozet, df = cikti
    m = ozet["meta"]
    assert len(df) == m["islem_n"] and df["olay_id"].is_unique and m["varyant_n"] == len(tp.VARYANTLAR)
    assert m["baz_esitligi"]["durum"] == "karsilastirildi" and m["baz_esitligi"]["farkli_n"] == 0
    assert m["baz_esitligi"]["ortak_n"] == len(df) and m["baz_esitligi"]["olcumde_olup_anada_olmayan"] == 0
    se = m["surec_olcum_esitligi"]
    assert se["durum"] == "karsilastirildi"
    assert (se["ortak_n"], se["farkli_n"], se["yalniz_bu_olcumde"], se["yalniz_surec_olcumde"]) == (len(df), 0, 0, 0)


def test_cikti_cik_varyanti_tetikten_sonraki_acilista_cikar_basabas_stopu_gecmez(cikti):
    _, df = cikti
    stop = df["baz_neden"].isin(["STOP", "STOP_GAP"])
    for ad, (esik, tetik, tepki) in tp.VARYANTLAR.items():
        tk = tp.tetik_kapanisi(df, esik, tetik)
        var, yok = tk.notna(), tk.isna()
        net, neden, bar = df[f"{ad}_net"], df[f"{ad}_neden"], df[f"{ad}_bar"]
        # Tetik yanmadıysa sonuç bazla birebir aynıdır.
        assert (net[yok] == df.loc[yok, "baz_net"]).all() and (neden[yok] == df.loc[yok, "baz_neden"]).all(), ad
        assert (bar[yok] == df.loc[yok, "baz_bar"]).all(), ad
        assert (tk[var] < df.loc[var, "baz_bar"]).all(), ad                # tepki çıkış mumundan önce verilir
        if tepki == "cik":
            assert (neden[var] == "TEPKI_CIK").all() and (bar[var] == tk[var] + 1).all(), ad
        else:
            assert neden[var].isin(["IZ_STOP", "IZ_STOP_GAP"]).eq(neden[var] != df.loc[var, "baz_neden"]).all(), ad
            assert (bar[var] <= df.loc[var, "baz_bar"]).all(), ad
            giris_fiyatinda = var & (neden == "IZ_STOP")
            assert np.allclose(net[giris_fiyatinda], -df.loc[giris_fiyatinda, "masraf_r"], atol=1.5e-4), ad      # girişte çıkış: brüt 0
            bosluk = var & (neden == "IZ_STOP_GAP")
            assert (net[bosluk] <= -df.loc[bosluk, "masraf_r"] + 1.5e-4).all(), ad
            # Stop olacak işlem girişten geçmeden stopa varamaz: başa baş stopu onu hiç kötüleştirmez.
            assert neden[var & stop].isin(["IZ_STOP", "IZ_STOP_GAP"]).all(), ad
            assert (net[var & stop] >= df.loc[var & stop, "baz_net"] - 1e-9).all(), ad


def test_cikti_esik_ve_tetikler_kar_gorup_donen_ile_islem_islem_ayni(cikti):
    _, df = cikti
    yol = KOK / "kar_gorup_donen/islemler.csv.gz"
    if not yol.exists():
        pytest.skip("kar_gorup_donen çıktısı üretilmemiş")
    diger = pd.read_csv(yol, low_memory=False).set_index("olay_id").loc[df["olay_id"]].reset_index()
    for esik in tp.ESIKLER:
        k_esik = df[f"k_esik_{esik}"]
        assert (k_esik.fillna(-1).to_numpy() == diger[f"k_{esik}"].fillna(-1).to_numpy()).all(), esik
        # Eşikten çıkıştan önceki son kapanışa kadar görülen olaylar: iki betik aynı pencereyi okur.
        for tetik, kolon in (("ENGEL", "engel_red"), ("SEVIYE_ICI", "seviye_ici"), ("FRM", "frm_bozulma"), ("MS_SUPURME", "ters_supurme"), ("VP_TERS", "vp_ters")):
            assert (df[f"tk_{esik}_{tetik}"].notna().to_numpy() == diger[f"sonra_{kolon}_{esik}"].eq(True).to_numpy()).all(), (esik, tetik)
        # Eşik mumunun kendisinde yanan tetik = kar_gorup_donen'in eşik anı gözlemi.
        for tetik, alan in (("STABIL", "stabil"), ("MS", "ms"), ("BLOK", "blok")):
            esik_aninda = (df[f"tk_{esik}_{tetik}"] == k_esik).to_numpy()
            assert (esik_aninda == diger[f"{alan}_{esik}"].eq("RED").to_numpy()).all(), (esik, tetik)
        endeks_aninda = (df[f"tk_{esik}_ENDEKS"] == k_esik).to_numpy()
        assert (endeks_aninda == (diger[f"endeks_{esik}"] <= -tp.ENDEKS_ESIK).to_numpy()).all(), esik
        # Motorla ölçülen "eşik görülünce çık" farkı, mumlardan hesaplanan karşı-olguyla aynıdır.
        gordu = k_esik.notna().to_numpy()
        motor = (df[f"{esik}_her_islem_cik_net"] - df["baz_net"]).to_numpy()[gordu]
        mumdan = diger[f"erken_cikis_fark_{esik}"].to_numpy()[gordu]
        assert np.abs(motor - mumdan).max() < 2e-3 and abs(motor.sum() - mumdan.sum()) < 0.5, esik


def test_cikti_ozet_islem_tablosundan_yeniden_hesaplanir_ve_rapor_ozetten_uretilir(cikti):
    ozet, df = cikti
    assert tp._markdown(ozet) == (CIKTI / "RAPOR.md").read_text(encoding="utf-8")
    assert list(ozet["meta"]["tetikler"]) == list(tp.TETIKLER) and ozet["meta"]["esikler_atr"] == tp.ESIKLER
    maskeler = {"D7_A_Arti": df["kalite_katmani"] == "A_ARTI", "D1_Birincil": df["sinyal_sinifi"] == "BIRINCIL"}
    for kume, veri in ozet["kumeler"].items():
        assert [v["varyant"] for v in veri["varyantlar"]] == list(tp.VARYANTLAR)
        assert sum(veri["baz_sonuc"].values()) == veri["n"] == veri["kesif_n"] + veri["dogrulama_n"]
        alt = df[maskeler[kume]] if kume in maskeler else None
        for v in veri["varyantlar"]:
            assert v["etkilenen_n"] <= v["tetiklenen_n"] <= veri["esik_goren"][v["esik"]] <= veri["n"]
            assert v["iyilesen_n"] + v["kotulesen_n"] <= v["etkilenen_n"] == v["kesif_etkilenen_n"] + v["dogrulama_etkilenen_n"]
            assert sum(x["n"] for x in v["dokum"].values()) == v["etkilenen_n"]
            assert sum(x["toplam_r"] for x in v["dokum"].values()) == pytest.approx(v["fark_toplam"], abs=0.02)
            assert v["karar"] in {"GECTI", "UMUT_VAR", "ZAYIF_ARTI", "GECMEDI", "ZARARLI", "SAYILMAZ_N<30"}
            if v["tetik"] == "HER_ISLEM":
                assert v["tetiklenen_n"] == veri["esik_goren"][v["esik"]]
            if alt is not None:
                fark = alt[f"{v['varyant']}_net"] - alt["baz_net"]
                assert v["fark_toplam"] == pytest.approx(fark.sum(), abs=0.01) and veri["n"] == len(alt)
                assert v["fark_ort"] == pytest.approx(fark.mean(), abs=1e-6)
                assert v["tetiklenen_n"] == int(tp.tetik_kapanisi(alt, v["esik"], v["tetik"]).notna().sum())


def test_cikti_esigi_goren_islem_sayisi_kar_gorup_donen_ozetiyle_ayni(cikti):
    ozet, _ = cikti
    yol = KOK / "kar_gorup_donen/ozet.json"
    if not yol.exists():
        pytest.skip("kar_gorup_donen çıktısı üretilmemiş")
    diger = json.loads(yol.read_text(encoding="utf-8"))["kumeler"]
    for kume, veri in ozet["kumeler"].items():
        assert veri["n"] == diger[kume]["n"] and veri["baz_sonuc"]["STOP"] == diger[kume]["stop_n"]
        for esik in tp.ESIKLER:
            assert veri["esik_goren"][esik] == diger[kume]["esikler"][esik]["kohort"]["n"], (kume, esik)


def test_cikti_tetikler_tepeden_stopa_tablosundaki_islemleri_kapsar(cikti):
    """`kar_gorup_donen` tablosunun stop satırlarında sayılan her işlemde aynı gözlem tetik olarak da yanar.

    Tablo tepe mumundan sayar (tepe ancak işlem bittikten sonra bilinir); tetik eşiğin görüldüğü
    kapanıştan. Tetik penceresi tabloyu kapsar; fazlası tepe mumu dışındaki mumlardır.
    """
    ozet, df = cikti
    yol = KOK / "kar_gorup_donen/islemler.csv.gz"
    if not yol.exists():
        pytest.skip("kar_gorup_donen çıktısı üretilmemiş")
    diger = pd.read_csv(yol, low_memory=False).set_index("olay_id").loc[df["olay_id"]].reset_index()
    tablo = {
        "ENGEL": diger[[f"{a}_tepe" for a in kg.ALANLAR]].eq("RED").any(axis=1).to_numpy(),
        "STABIL": diger["stabil_tepe"].eq("RED").to_numpy(),
        "MS": diger["ms_tepe"].eq("RED").to_numpy(),
        "BLOK": diger["blok_tepe"].eq("RED").to_numpy(),
        "SEVIYE_ICI": diger["ara_seviye_ici"].eq(True).to_numpy(),
        "FRM": diger["ara_frm_bozulma"].eq(True).to_numpy(),
        "MS_SUPURME": diger["ara_ters_supurme"].eq(True).to_numpy(),
        "VP_TERS": diger["ara_vp_ters"].eq(True).to_numpy(),
    }
    genisleyen = 0
    for kume, maske in tp.so.KUMELER.items():
        kumede = maske(df).to_numpy()
        for esik in tp.ESIKLER:
            grup = kumede & diger[f"{esik}_atr_stop"].eq(True).to_numpy()
            assert grup.sum() >= 30, (kume, esik)
            for tetik, gorulen in tablo.items():
                yandi = df[f"tk_{esik}_{tetik}"].notna().to_numpy()
                assert not (grup & gorulen & ~yandi).any(), (kume, esik, tetik)
                genisleyen += int((grup & yandi & ~gorulen).sum())
                # "Çık" tepkisinde tetiklenen her işlemin sonucu değişir: raporun stop sütunu bu sayıdır.
                v = next(x for x in ozet["kumeler"][kume]["varyantlar"] if (x["esik"], x["tetik"], x["tepki"]) == (esik, tetik, "cik"))
                assert v["dokum"]["STOP"]["n"] == int((grup & yandi).sum()), (kume, esik, tetik)
    assert genisleyen > 0                                   # kapsama boş bir eşitlik değil: tetik penceresi gerçekten daha geniş


def test_cikti_kismi_tepki_tam_tepkinin_oranidir_isaret_degismez(cikti):
    """Pozisyonun yarısına uygulanan tepki: net = (baz + varyant) / 2. Fark ve aralık yarıya iner, işaret aynı kalır."""
    ozet, df = cikti
    d7 = df[df["kalite_katmani"] == "A_ARTI"].copy()
    tam = {v["varyant"]: v for v in ozet["kumeler"]["D7_A_Arti"]["varyantlar"]}
    adlar = [ad for ad, (esik, _, _) in tp.VARYANTLAR.items() if esik == "yarim"]
    for ad in adlar:
        d7[f"{ad}_net"] = (d7["baz_net"] + d7[f"{ad}_net"]) / 2.0
    for ad in adlar:
        yari, v = tp.varyant_ozeti(d7, ad), tam[ad]
        assert (yari["etkilenen_n"], yari["iyilesen_n"], yari["kotulesen_n"]) == (v["etkilenen_n"], v["iyilesen_n"], v["kotulesen_n"]), ad
        assert yari["fark_toplam"] == pytest.approx(v["fark_toplam"] / 2, abs=0.006), ad
        for alan in ("fark_ort", "kesif_fark", "dogrulama_fark"):
            assert yari[alan] == pytest.approx(v[alan] / 2, abs=1e-6), (ad, alan)
        for alan in ("fark_en_kotu_alt", "fark_en_kotu_ust"):
            assert yari[alan] == pytest.approx(v[alan] / 2, abs=1.01e-4), (ad, alan)      # sınırlar 4 haneye yuvarlanır
        assert yari["karar"] == v["karar"], ad


def test_cikti_tez_seviyesi_tepkisi_sartsiz_surec_olcum_kuraliyla_ayni_mumda_ayni_sonucu_verir(cikti):
    """`surec_olcum.seviye_ici_acilis` ilk olayda çıkar, tepki eşikten sonraki ilk olayda (ayrı politika sınıfları).

    İkisi aynı mumda çıkıyorsa net birebir aynıdır; şartsız kural hiçbir işlemde tepkiden geç çıkmaz.
    """
    _, df = cikti
    yol = KOK / "surec_olcum/islemler.csv.gz"
    if not yol.exists():
        pytest.skip("surec_olcum çıktısı üretilmemiş")
    surec = pd.read_csv(yol, low_memory=False).set_index("olay_id").loc[df["olay_id"]].reset_index()
    for esik in tp.ESIKLER:
        tk = df[f"tk_{esik}_SEVIYE_ICI"]
        var = tk.notna()
        ayni_mum = var & (surec["seviye_ici_acilis_bar"] == tk + 1)
        assert not (var & (surec["seviye_ici_acilis_bar"] > tk + 1)).any(), esik
        assert ayni_mum.sum() >= 0.9 * var.sum() > 100, esik
        assert (surec.loc[ayni_mum, "seviye_ici_acilis_neden"] == "SEVIYE_CIKIS").all(), esik
        assert np.abs(df.loc[ayni_mum, f"{esik}_seviye_ici_cik_net"] - surec.loc[ayni_mum, "seviye_ici_acilis_net"]).max() < 1e-9, esik
