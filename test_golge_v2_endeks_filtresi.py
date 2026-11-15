"""Gölge v2 endeks rejimi filtresi testleri: nedensel rejim, stop grupları, filtre ve kabul merdiveni."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research import golge_v2_endeks_filtresi as ef
from research import golge_v2_sonuc_anatomisi as sa

CIKTI = Path(__file__).resolve().parent / "docs/arastirma/sonuclar/golge_v2/endeks_filtresi"


# ---------------------------------------------------------------------------
# Rejim
# ---------------------------------------------------------------------------
def test_rejim_yukselen_ve_dusen_seride_dogru_kod_ve_isinma_suresi():
    yukselen = np.linspace(100.0, 200.0, 80)
    r = ef.rejim_dizileri(yukselen)
    for ad, isinma in (("getiri_10", 10), ("getiri_20", 20), ("getiri_60", 60), ("sma_20", 19), ("sma_50", 49), ("trend_20", 24)):
        assert np.isnan(r[ad][:isinma]).all(), ad
        assert (r[ad][isinma:] == ef.YUKSELIS).all(), ad
    d = ef.rejim_dizileri(yukselen[::-1])
    for ad in ("getiri_10", "getiri_20", "getiri_60", "sma_20", "sma_50", "trend_20"):
        assert (d[ad][~np.isnan(d[ad])] == ef.DUSUS).all(), ad
    assert "ms_dis" not in r
    assert (ef.rejim_dizileri(yukselen, np.r_[np.zeros(40), -np.ones(40)])["ms_dis"][40:] == ef.DUSUS).all()


def test_rejim_nedenseldir_gelecek_kapanislar_gecmis_kodu_degistirmez():
    rng = np.random.default_rng(7)
    c = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, 160)))
    tam = ef.rejim_dizileri(c)
    for kesim in (61, 97, 140):
        kismi = ef.rejim_dizileri(c[:kesim])
        for ad, dizi in kismi.items():
            np.testing.assert_array_equal(dizi, tam[ad][:kesim], err_msg=f"{ad}@{kesim}")


def test_trend_20_ortalama_ile_egim_celisirse_kararsizdir():
    # Uzun yükselişten sonra sert düşüş: fiyat ortalamanın altına iner ama ortalama hâlâ yükseliyordur.
    c = np.r_[np.linspace(100.0, 160.0, 40), 140.0]
    r = ef.rejim_dizileri(c)
    assert r["sma_20"][-1] == ef.DUSUS
    assert r["trend_20"][-1] == ef.KARARSIZ


def test_getiri_yuzde_ve_epizot_kimlikleri():
    c = np.array([100.0, 110.0, 121.0, 108.9])
    np.testing.assert_allclose(ef.getiri_yuzde(c, 2)[2:], [21.0, -1.0])
    assert np.isnan(ef.getiri_yuzde(c, 2)[:2]).all()
    np.testing.assert_array_equal(ef.epizot_kimlikleri([1, 1, -1, -1, np.nan, np.nan, 1]), [0, 0, 1, 1, 2, 2, 3])
    assert len(ef.epizot_kimlikleri([])) == 0


def test_asof_gun_varsayilan_olarak_ayni_anda_kapanan_gunu_saymaz():
    kapanis = np.array([10, 20, 30])
    np.testing.assert_array_equal(ef.asof_gun(kapanis, [5, 20, 25, 99]), [-1, 0, 1, 2])
    np.testing.assert_array_equal(ef.asof_gun(kapanis, [5, 20, 25, 99], ayni_an_dahil=True), [-1, 1, 1, 2])


# ---------------------------------------------------------------------------
# Stop grupları
# ---------------------------------------------------------------------------
def test_stop_gruplari_atr_cinsindendir_ve_stoplari_tam_boler():
    df = pd.DataFrame(
        {
            "cikis_turu": ["STOP", "STOP", "STOP_BOSLUK", "STOP", "HEDEF", "SURE"],
            "hedef_yolu_orani": [0.0, 0.2499, 0.25, 0.5, 1.0, 0.6],
        }
    )
    out = ef.stop_gruplarini_ekle(df)
    np.testing.assert_allclose(out["stop_mfe_atr"][:4], [0.0, 0.4998, 0.5, 1.0])
    assert out["stop_mfe_atr"][4:].isna().all()
    assert out["dogrudan_stop"].tolist() == [True, True, False, False, False, False]
    assert out["yarim_atr_stop"].tolist() == [False, False, True, True, False, False]
    assert out["bir_atr_stop"].tolist() == [False, False, False, True, False, False]
    stop = out["cikis_turu"].isin(("STOP", "STOP_BOSLUK"))
    assert ((out["dogrudan_stop"] | out["yarim_atr_stop"]) == stop).all()
    assert not (out["dogrudan_stop"] & out["yarim_atr_stop"]).any()


# ---------------------------------------------------------------------------
# Filtre
# ---------------------------------------------------------------------------
def test_filtre_kurallari_yon_ve_rejime_gore_dogru_islemi_eler():
    yon = np.array(["long", "long", "short", "short", "long", "short"])
    rj = np.array([ef.DUSUS, ef.YUKSELIS, ef.DUSUS, ef.YUKSELIS, np.nan, ef.KARARSIZ])
    kural = {ad: np.asarray(f(yon, rj), dtype=bool).tolist() for ad, (_, f) in ef.FILTRELER.items()}
    assert kural["LONG_DUSUSTE"] == [True, False, False, False, False, False]
    assert kural["SHORT_YUKSELISTE"] == [False, False, False, True, False, False]
    assert kural["KARSI"] == [True, False, False, True, False, False]
    assert kural["DUSUSTE_HIC"] == [True, False, True, False, False, False]


def _sentetik(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    gun = pd.date_range("2025-01-06", periods=n, freq="B")
    rejim = np.where(np.arange(n) % 40 < 20, ef.DUSUS, ef.YUKSELIS).astype(float)
    yon = np.where(np.arange(n) % 2 == 0, "long", "short")
    # Düşüşteki longlar belirgin zararda; geri kalan belirgin kârda.
    karsi = (yon == "long") & (rejim == ef.DUSUS)
    net = np.where(karsi, -1.0, 0.8) + rng.normal(0.0, 0.05, n)
    stop = net < 0
    df = pd.DataFrame(
        {
            "sembol": [f"S{i % 9}" for i in range(n)],
            "bar_close_time": [f"{g.date()}T18:30:00+03:00" for g in gun],
            "donem": np.where(np.arange(n) < n // 2, "kesif", "dogrulama"),
            "yon": yon,
            sa.NET: net,
            "kar": net > 0,
            "cikis_turu": np.where(stop, "STOP", "HEDEF"),
            "hedef_yolu_orani": np.where(stop, 0.1, 1.0),
            "rj_getiri_20": rejim,
            "epizot_getiri_20": np.arange(n) // 20,
        }
    )
    return ef.stop_gruplarini_ekle(df)


def test_filtre_ozeti_elenenleri_dogru_sayar_ve_fayda_elenenin_ters_isaretlisidir():
    df = _sentetik()
    r = ef.filtre_ozeti(df, "getiri_20", "LONG_DUSUSTE")
    karsi = (df["yon"] == "long") & (df["rj_getiri_20"] == ef.DUSUS)
    assert r["elenen"]["n"] == int(karsi.sum()) == 30
    assert r["kalan"]["n"] == len(df) - 30
    assert r["fayda"]["tumu"]["fayda_toplam"] == pytest.approx(-df.loc[karsi, sa.NET].sum(), abs=0.01)
    assert r["fayda"]["tumu"]["fayda_ort"] == pytest.approx(-df.loc[karsi, sa.NET].sum() / len(df), abs=1e-6)
    assert r["elenen_dogrudan_stop_n"] == 30 and r["toplam_dogrudan_stop_n"] == 30
    assert r["elenen_kazanan_n"] == 0
    assert r["donem_n"] == 3 and r["zararda_donem_n"] == 3
    assert r["karar"] == "ZAYIF_ARTI"        # fayda iki dönemde de pozitif ama dönem başına elenen 30'dan az
    # Aynı veride kârlı işlemleri eleyen filtre zararlıdır.
    ters = ef.filtre_ozeti(df, "getiri_20", "SHORT_YUKSELISTE")
    assert ters["elenen"]["net_ort"] > 0.5 and ters["karar"] == "ZARARLI"


def _f(elenen: int, ort: float, alt: float | None, ust: float | None, n: int = 500) -> dict:
    return {"n": n, "elenen_n": elenen, "fayda_ort": ort, "fayda_toplam": ort * n, "fayda_en_kotu_alt": alt, "fayda_en_kotu_ust": ust}


@pytest.mark.parametrize(
    "tumu, kesif, dogrulama, beklenen",
    [
        (_f(20, 0.1, 0.01, 0.2), _f(10, 0.1, 0.01, 0.2), _f(10, 0.1, 0.01, 0.2), "SAYILMAZ_N<30"),
        (_f(90, -0.1, -0.2, -0.01), _f(45, -0.1, -0.2, 0.0), _f(45, -0.1, -0.2, 0.0), "ZARARLI"),
        (_f(90, 0.02, -0.05, 0.1), _f(45, 0.1, 0.0, 0.2), _f(45, -0.06, -0.2, 0.1), "GECMEDI"),
        (_f(90, 0.02, 0.01, 0.1), _f(45, 0.1, 0.01, 0.2), _f(45, 0.0, -0.2, 0.1), "GECMEDI"),
        (_f(50, 0.05, 0.01, 0.1), _f(35, 0.05, 0.01, 0.2), _f(15, 0.05, 0.01, 0.1), "ZAYIF_ARTI"),
        (_f(90, 0.05, 0.01, 0.1), _f(45, 0.05, 0.01, 0.2), _f(45, 0.05, 0.01, 0.1), "GECTI"),
        (_f(90, 0.05, 0.01, 0.1), _f(45, 0.05, -0.01, 0.2), _f(45, 0.05, 0.01, 0.1), "UMUT_VAR"),
        (_f(90, 0.05, -0.01, 0.1), _f(45, 0.05, -0.01, 0.2), _f(45, 0.05, -0.02, 0.1), "ZAYIF_ARTI"),
        (_f(90, 0.05, None, None), _f(45, 0.05, None, None), _f(45, 0.05, None, None), "ZAYIF_ARTI"),
    ],
)
def test_filtre_karari_merdiveni(tumu, kesif, dogrulama, beklenen):
    assert ef.filtre_karari(tumu, kesif, dogrulama) == beklenen


def test_kademe_tablosu_yon_yon_ayrilir_ve_toplami_korur():
    df = _sentetik()
    df["endeks_getiri_20_yonlu"] = np.tile([-8.0, -2.0, 2.0, 8.0, np.nan], len(df) // 5)
    satirlar = {r["grup"]: r for r in ef.kademe_tablosu(df, 20)}
    for ad in ef.KADEME_AD:
        assert satirlar[ad]["n"] == 24
        assert satirlar[f"{ad} — yalnız long"]["n"] + satirlar[f"{ad} — yalnız short"]["n"] == 24
    assert satirlar["BILINMIYOR"]["n"] == 24


def test_duyarlilik_ozeti_degisen_karari_sayar():
    def kume(karar: str) -> dict:
        return {"K": {"rejimler": {"a": {"filtreler": [{"karar": "GECMEDI"}, {"karar": karar}]}}}}

    assert ef.duyarlilik_ozeti(kume("GECMEDI"), kume("GECMEDI")) == {"degisen_karar_n": 0, "karar_sayimi": {"K": {"GECMEDI": 2}}, "gecen_n": 0}
    d = ef.duyarlilik_ozeti(kume("GECMEDI"), kume("UMUT_VAR"))
    assert d["degisen_karar_n"] == 1 and d["gecen_n"] == 1


# ---------------------------------------------------------------------------
# Üretilmiş çıktı
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def cikti() -> tuple[dict, pd.DataFrame]:
    if not (CIKTI / "ozet.json").exists():
        pytest.skip("endeks_filtresi çıktısı üretilmemiş")
    return json.loads((CIKTI / "ozet.json").read_text(encoding="utf-8")), pd.read_csv(CIKTI / "islemler.csv.gz")


def test_cikti_elenen_ve_kalan_kumeyi_tam_boler(cikti):
    ozet, _ = cikti
    assert set(ozet["meta"]["rejim_tanimlari"]) == set(ef.REJIMLER)
    for kume, v in ozet["kumeler"].items():
        n = v["baz"]["n"]
        for ad, rv in v["rejimler"].items():
            assert sum(r["n"] for r in rv["iliski"]) == n, (kume, ad)
            assert [r["filtre"] for r in rv["filtreler"]] == list(ef.FILTRELER)
            for r in rv["filtreler"]:
                assert r["elenen"]["n"] + r["kalan"]["n"] == n, (kume, ad, r["filtre"])
                assert r["fayda"]["tumu"]["elenen_n"] == r["elenen"]["n"]
                assert r["fayda"]["kesif"]["elenen_n"] + r["fayda"]["dogrulama"]["elenen_n"] == r["elenen"]["n"]
                assert r["zararda_donem_n"] <= r["donem_n"] <= max(r["elenen"]["n"], 0)
        for tablo in v["kademe"].values():
            assert sum(r["n"] for r in tablo if "yalnız" not in r["grup"]) == n


def test_cikti_islem_tablosu_ana_raporla_ve_stop_gruplariyla_tutarli(cikti):
    ozet, df = cikti
    assert len(df) == ozet["meta"]["islem_n"] and df["olay_id"].is_unique
    stop = df["cikis_turu"].isin(("STOP", "STOP_BOSLUK"))
    assert ((df["dogrudan_stop"] | df["yarim_atr_stop"]) == stop).all()
    assert (df.loc[df["bir_atr_stop"], "yarim_atr_stop"]).all()
    d7 = df[df["kalite_katmani"] == "A_ARTI"]
    assert len(d7) == ozet["kumeler"]["D7_A_Arti"]["baz"]["n"]
    assert d7[sa.NET].mean() == pytest.approx(ozet["kumeler"]["D7_A_Arti"]["baz"]["net_ort"], abs=1e-6)
    # Rejim kodları yalnız −1 / 0 / +1 ya da boştur; ilişki = rejim × yön.
    yon = np.where(df["yon"] == "long", 1.0, -1.0)
    for ad in ef.REJIMLER:
        kod = df[f"rj_{ad}"]
        assert set(kod.dropna().unique()) <= {-1.0, 0.0, 1.0}
        np.testing.assert_array_equal((kod * yon).fillna(9).to_numpy(), df[f"iliski_{ad}"].fillna(9).to_numpy())


def test_cikti_rapor_ozetten_yeniden_uretilebilir(cikti):
    ozet, _ = cikti
    assert ef._markdown(ozet) == (CIKTI / "RAPOR.md").read_text(encoding="utf-8")
    kararlar = [r["karar"] for v in ozet["kumeler"].values() for rv in v["rejimler"].values() for r in rv["filtreler"]]
    assert len(kararlar) == len(ozet["kumeler"]) * len(ef.REJIMLER) * len(ef.FILTRELER)
    assert set(kararlar) <= {"GECTI", "UMUT_VAR", "ZAYIF_ARTI", "GECMEDI", "ZARARLI", "SAYILMAZ_N<30"}
    # Kısa özetteki "geçen varyant" sayısı tabloların kendisinden sayılanla aynıdır.
    gecen = ef.karar_sayimi(ozet["kumeler"])
    assert all(isinstance(v, dict) for v in gecen.values())
    assert sum(sum(v.values()) for v in gecen.values()) == len(kararlar)
