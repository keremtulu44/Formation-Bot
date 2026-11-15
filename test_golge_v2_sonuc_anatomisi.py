"""Gölge v2 sonuç anatomisi: yol yürüyücü, sınıflandırıcılar ve özetin iç tutarlılığı."""

from __future__ import annotations

import json
import random
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from research import golge_v2_sonuc_anatomisi as sa
from research.golge_v2_sonuc_anatomisi import (
    ESIK_AZ_KAR,
    ESIK_BIR_R,
    ESIK_KAR,
    KUMELER,
    ZARAR_YOLLARI,
    cikis_turu,
    stop_sonrasi,
    stop_yolu,
    yolu_yuru,
    zarar_yolu,
)
from senaryo_v2.yaris import _tek_yarisi_simule_et

# Long: giriş 100, stop 90 (risk 10), hedef 120 (+2 R). Mum = (açılış, yüksek, düşük, kapanış).
LONG = dict(yon=1, giris=100.0, stop=90.0, hedef=120.0)
SHORT = dict(yon=-1, giris=100.0, stop=110.0, hedef=80.0)


# ---------------------------------------------------------------------------
# Yol yürüyücü
# ---------------------------------------------------------------------------
def test_stop_cikisinda_mfe_stop_mumunu_saymaz():
    # 2. mum önce 119'a çıkmış olabilir ama aynı mumda stopu da gördü: sıra bilinmez.
    yol = yolu_yuru([(100, 106, 98, 105), (105, 119, 89, 95)], **LONG)
    assert (yol.neden, yol.cikis_k, yol.cikis_fiyat) == ("STOP", 2, 90.0)
    assert yol.mfe_r == pytest.approx(0.6) and yol.mfe_k == 1      # yalnız 1. mumun 106'sı
    assert yol.mae_r == pytest.approx(1.0)
    assert yol.cikis_mumu_lehte_r == pytest.approx(1.9)            # üst sınır olarak ayrıca tutulur
    assert yol.ayni_mumda_hedef is False


def test_acilis_boslugu_stopu_acilistan_doldurur_ve_kayip_bir_r_den_buyuktur():
    yol = yolu_yuru([(100, 104, 99, 103), (85, 88, 80, 82)], **LONG)
    assert (yol.neden, yol.cikis_k, yol.cikis_fiyat) == ("STOP_GAP", 2, 85.0)
    assert yol.mae_r == pytest.approx(1.5)
    assert yol.mfe_r == pytest.approx(0.4)


def test_stop_ile_hedef_ayni_mumda_ise_stop_kazanir_ve_isaretlenir():
    yol = yolu_yuru([(100, 125, 85, 110)], **LONG)
    assert (yol.neden, yol.cikis_k) == ("STOP", 1)
    assert yol.ayni_mumda_hedef is True
    assert yol.mfe_r == 0.0 and yol.mfe_k is None                  # ilk mumda stop: önce görülen kâr yok


def test_hedef_cikisinda_mfe_hedefin_r_sidir_ve_mae_hedef_mumunu_saymaz():
    yol = yolu_yuru([(100, 103, 94, 101), (101, 121, 91, 118)], **LONG)
    assert (yol.neden, yol.cikis_k, yol.cikis_fiyat) == ("HEDEF", 2, 120.0)
    assert yol.mfe_r == pytest.approx(2.0) and yol.mfe_k == 2
    assert yol.mae_r == pytest.approx(0.6)                         # hedef mumunun 91'i sayılmaz


def test_sure_dolunca_son_kapanista_cikar_ve_butun_mumlar_sayilir():
    yol = yolu_yuru([(100, 108, 97, 104), (104, 112, 95, 99)], **LONG)
    assert (yol.neden, yol.cikis_k, yol.cikis_fiyat) == ("ZAMAN_STOPU", 2, 99.0)
    assert yol.mfe_r == pytest.approx(1.2) and yol.mfe_k == 2
    assert yol.mae_r == pytest.approx(0.5)


def test_short_simetriktir():
    yol = yolu_yuru([(100, 102, 93, 96), (96, 111, 95, 108)], **SHORT)
    assert (yol.neden, yol.cikis_k, yol.cikis_fiyat) == ("STOP", 2, 110.0)
    assert yol.mfe_r == pytest.approx(0.7)
    bosluk = yolu_yuru([(112, 115, 111, 114)], **SHORT)
    assert (bosluk.neden, bosluk.cikis_fiyat) == ("STOP_GAP", 112.0)
    hedef = yolu_yuru([(100, 101, 79, 81)], **SHORT)
    assert (hedef.neden, hedef.cikis_fiyat) == ("HEDEF", 80.0)


def test_gecersiz_girdi_reddedilir():
    with pytest.raises(ValueError):
        yolu_yuru([], **LONG)
    with pytest.raises(ValueError):
        yolu_yuru([(100, 101, 99, 100)], yon=1, giris=100.0, stop=105.0, hedef=120.0)   # stop yanlış tarafta
    with pytest.raises(ValueError):
        yolu_yuru([(100, 101, 99, 100)], yon=0, giris=100.0, stop=90.0, hedef=120.0)


def test_yuruyucu_motorla_ayni_sonucu_verir_rastgele_yollarda():
    """Anatomi motorun bar içi sırasını kopyalar; ikisi ayrışırsa rapor başka işlemleri anlatır."""
    rng = random.Random(7)
    for _ in range(400):
        yon = rng.choice((1, -1))
        giris, risk = 100.0, rng.uniform(1.0, 6.0)
        stop, hedef = giris - yon * risk, giris + yon * rng.uniform(2.0, 9.0)
        fiyat, mumlar = giris, []
        for _ in range(10):
            acilis = fiyat + rng.gauss(0, 1.5)
            kapanis = acilis + rng.gauss(0, 2.5)
            yuksek = max(acilis, kapanis) + abs(rng.gauss(0, 1.5))
            dusuk = min(acilis, kapanis) - abs(rng.gauss(0, 1.5))
            mumlar.append((acilis, yuksek, dusuk, kapanis))
            fiyat = kapanis
        yol = yolu_yuru(mumlar, yon=yon, giris=giris, stop=stop, hedef=hedef)
        barlar = [NS(open=giris, high=giris, low=giris, close=giris, ms_bos_down_now=False, ms_bos_up_now=False)] + [
            NS(open=o, high=h, low=l, close=c, ms_bos_down_now=False, ms_bos_up_now=False) for o, h, l, c in mumlar
        ]
        _, pnl_r, neden, ofset = _tek_yarisi_simule_et(
            tuple(barlar), olay_bar_idx=0, dolum_idx=0, start_scan_idx=1, yon="long" if yon == 1 else "short",
            giris=giris, stop=stop, hedef=hedef, atr_baz=1.0, ufuk_bar=10, intrabar=True, tez_iptal=False,
        )
        assert (yol.neden, yol.cikis_k) == (neden, ofset)
        assert yon * (yol.cikis_fiyat - giris) / risk == pytest.approx(pnl_r, abs=1e-4)


# ---------------------------------------------------------------------------
# Sınıflandırıcılar
# ---------------------------------------------------------------------------
def test_cikis_turu_ana_csv_nedenlerini_kapsar_ve_bilinmeyeni_reddeder():
    assert [cikis_turu(n) for n in ("HEDEF", "STOP", "STOP_GAP", "ZAMAN_STOPU", "TEZ_IPTAL_BOS")] == [
        "HEDEF", "STOP", "STOP_BOSLUK", "SURE", "TEZ_IPTAL",
    ]
    with pytest.raises(ValueError):
        cikis_turu("SANSURLU")


def test_stop_yolu_esikleri_alt_siniri_icerir_ve_ilk_mum_once_gelir():
    assert stop_yolu(0.0, 1) == "ILK_MUM"
    assert stop_yolu(ESIK_AZ_KAR - 1e-9, 3) == "KAR_GORMEDI"
    assert stop_yolu(ESIK_AZ_KAR, 3) == "AZ_KAR"
    assert stop_yolu(ESIK_KAR, 3) == "KAR_GORDU"
    assert stop_yolu(ESIK_BIR_R, 3) == "BIR_R_GORDU"


def test_zarar_yolu_tek_ve_oncelik_sirasiyla_atanir():
    assert zarar_yolu(net_r=0.4, neden="ZAMAN_STOPU", mfe_r=0.9, cikis_k=10) == ""           # kâr eden işlem
    assert zarar_yolu(net_r=-0.2, neden="ZAMAN_STOPU", mfe_r=0.9, cikis_k=10) == "SURE_ZARAR"
    assert zarar_yolu(net_r=-0.6, neden="TEZ_IPTAL_BOS", mfe_r=0.1, cikis_k=2) == "TEZ_IPTAL"
    # Boşluk, öncesinde ne görülmüş olursa olsun ve ilk mumda bile olsa kendi satırındadır.
    assert zarar_yolu(net_r=-1.4, neden="STOP_GAP", mfe_r=1.3, cikis_k=4) == "BOSLUK"
    assert zarar_yolu(net_r=-1.4, neden="STOP_GAP", mfe_r=0.0, cikis_k=1) == "BOSLUK"
    assert zarar_yolu(net_r=-1.1, neden="STOP", mfe_r=0.0, cikis_k=1) == "ILK_MUM"
    assert zarar_yolu(net_r=-1.1, neden="STOP", mfe_r=0.7, cikis_k=5) == "KAR_GORDU"
    with pytest.raises(ValueError):
        zarar_yolu(net_r=-0.1, neden="HEDEF", mfe_r=2.0, cikis_k=3)
    assert {zarar_yolu(net_r=-1.0, neden=n, mfe_r=m, cikis_k=k) for n, m, k in (
        ("ZAMAN_STOPU", 0, 10), ("TEZ_IPTAL_BOS", 0, 2), ("STOP_GAP", 0, 2), ("STOP", 0, 1),
        ("STOP", 0.1, 2), ("STOP", 0.3, 2), ("STOP", 0.6, 2), ("STOP", 1.2, 2),
    )} == {kod for kod, _ in ZARAR_YOLLARI}


def test_stop_sonrasi_siniflari():
    assert stop_sonrasi(cikis_k=10, ufuk=10, sonra_hedef=False, ufuk_kapanis_r=-2.0) == "UFUK_SONU"
    assert stop_sonrasi(cikis_k=3, ufuk=10, sonra_hedef=True, ufuk_kapanis_r=-2.0) == "HEDEFE_GITTI"
    assert stop_sonrasi(cikis_k=3, ufuk=10, sonra_hedef=False, ufuk_kapanis_r=0.2) == "KARDA_BITTI"
    assert stop_sonrasi(cikis_k=3, ufuk=10, sonra_hedef=False, ufuk_kapanis_r=-0.4) == "ZARARDA_BITTI"
    assert stop_sonrasi(cikis_k=3, ufuk=10, sonra_hedef=False, ufuk_kapanis_r=-1.0) == "DAHA_KOTU"


# ---------------------------------------------------------------------------
# Gerçek arşiv: küçük bir alt küme
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def alt_kume() -> pd.DataFrame:
    df = sa.islemleri_yukle(sa.VARSAYILAN_GIRDI)
    semboller = sorted(df["sembol"].unique())[:6]
    return sa.anatomiyi_cikar(df[df["sembol"].isin(semboller)].reset_index(drop=True), workers=1)


def test_arsiv_yolu_ana_csv_ile_ayni_ve_alanlar_tutarli(alt_kume):
    df = alt_kume            # `anatomiyi_cikar` tek bir uyuşmazlıkta durur; buraya gelindiyse yol CSV ile aynı
    assert len(df) > 50 and df["olay_id"].is_unique
    assert (df["zarar_yolu"] != "").equals(df["net15_20_r"] < 0)
    stop = df["cikis_turu"].isin(("STOP", "STOP_BOSLUK"))
    assert (df.loc[stop, "yol_mfe_r"] - df.loc[stop, "surec_mfe_r"]).abs().max() < 2e-4
    # Stop mumu başlarken fiyat stopun doğru tarafındadır; ilk mumda stop olanda son kapanış giriştir.
    assert (df.loc[stop, "stop_oncesi_mesafe_atr"] > 0).all()
    assert (df.loc[stop & (df["bar_20_intra_iptal"] == 1), "stop_oncesi_kapanis_r"] == 0).all()
    # 4s mumlar 1s arşivinden türediği için saat çözünürlüğü 4s işlemlerde birebir tutmalıdır.
    dort = df[(df["tf"] == "4h") & (df["saatlik_durum"] != "KAPSAM_DISI")]
    assert dort["saatlik_durum"].isin(("AYNI", "ONCE_HEDEF")).all()
    ayni = df[stop & (df["saatlik_durum"] == "AYNI") & (df["tf"] == "4h")]
    assert (ayni["saat_mfe_r"] >= ayni["yol_mfe_r"] - 1e-9).all()      # saat, mumun gördüğünden azını göremez


def test_ozet_paylari_tam_kapsar(alt_kume):
    v = sa.kume_ozeti(alt_kume)
    g = v["genel"]
    assert g["kar_n"] + g["zarar_n"] == g["n"] == len(alt_kume)
    assert sum(r["n"] for r in v["cikis"]) == g["n"]
    assert sum(r["n"] for r in v["zarar_yollari"]) == g["zarar_n"]
    assert sum(r["n"] for r in v["stop"]["bar"]) == v["stop"]["n"]
    assert sum(r["n"] for r in v["stop_sonrasi"]["tumu"]) == v["stop"]["n"]
    uy = v["uyari"]
    assert uy["gozlemsiz_stop_n"] + uy["seviye_disindan_tek_mumda_n"] + uy["son_kapanista_seviye_ici_n"] == uy["stop_n"]
    assert sum(r["stop_n"] for r in uy["tez_son"]) == uy["stop_n"]
    for r in v["piyasa"].values():
        if isinstance(r, dict):
            assert r["ters_n"] + r["yatay_n"] + r["lehte_n"] == r["olculen_n"] <= r["n"]
    hf = v["hafta"]
    assert hf["arti_toplam"] + hf["eksi_toplam"] == pytest.approx(hf["net_toplam"], abs=0.05)
    assert v["dar_genis"]["dar"]["n"] + v["dar_genis"]["genis"]["n"] == g["n"]
    assert "Kısa özet" in sa._markdown({"meta": _sahte_meta(len(alt_kume)), "kumeler": {"D1_Birincil": v}})


def _sahte_meta(n: int) -> dict:
    return {
        "islem_n": n, "tfs": ["4h", "1d"], "yol_csv_ile_ayni_n": n, "ana_rapor_esitligi": {"durum": "ozet_rapor_yok"},
        "saatlik_durum": {"4h": {"AYNI": 1}, "1d": {"AYNI": 1}},
    }


def test_ayni_gun_sayaci_nedenseldir():
    """Aynı gün/yön sayacı yalnız o ana KADAR açılmış işlemleri sayar; sonradan açılan sayılmaz."""
    df = pd.DataFrame(
        {
            "olay_id": ["a", "b", "c", "d", "e"],
            "bar_close_time": [
                "2026-01-05T13:30:00+03:00", "2026-01-05T17:30:00+03:00", "2026-01-05T17:30:00+03:00",
                "2026-01-05T13:30:00+03:00", "2026-01-06T13:30:00+03:00",
            ],
            "yon": ["long", "long", "long", "short", "long"],
        }
    )
    sayac = dict(zip(df["olay_id"], sa.ayni_gun_yon_sayaci(df)))
    assert sayac == {"a": 1, "b": 3, "c": 3, "d": 1, "e": 1}


# ---------------------------------------------------------------------------
# Depodaki çıktı ana raporla aynı işlemleri anlatıyor mu?
# ---------------------------------------------------------------------------
def test_depodaki_anatomi_ana_raporla_ayni_kumeleri_anlatir():
    kok = sa.VARSAYILAN_GIRDI
    yol = kok / "sonuc_anatomisi" / "ozet.json"
    if not yol.exists():
        pytest.skip("sonuc_anatomisi/ozet.json üretilmemiş")
    ozet = json.loads(yol.read_text(encoding="utf-8"))
    merdiven = json.loads((kok / "ozet_rapor.json").read_text(encoding="utf-8"))["domain_merdiven_4h1d_net15"]
    for ad in KUMELER:
        ana = next(x for x in merdiven if x["donem"] == "tumu" and x["katman"] == sa._ANA_KATMAN[ad])
        g = ozet["kumeler"][ad]["genel"]
        mesaj = f"{ad}: anatomi bayat; `python -m research.golge_v2_sonuc_anatomisi` ile yeniden üretin"
        assert g["n"] == ana["n"], mesaj
        assert g["net_ort"] == pytest.approx(ana["ort"], abs=5e-4), mesaj
        assert sum(r["n"] for r in ozet["kumeler"][ad]["zarar_yollari"]) == g["zarar_n"]
