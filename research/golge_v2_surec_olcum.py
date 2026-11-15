"""Gölge v2 işlem-içi süreç ölçümü — "görmek" ile "davranmak" arasındaki farkı ölçer.

Yarış motoru artık açık işlemi her kapanışta gözlüyor (`senaryo_v2/surec.py`). Bu koşucu,
o gözlemlerin bir yönetim kuralına dönüştürülmeye değip değmediğini iki ayrı yoldan ölçer:

1. **İleri beklenti.** Bir süreç etiketi işlem açıkken ilk kez görüldüğü kapanıştan sonra
   işlemde KALMANIN brüt getirisi (R). Etiketin nihai sonuçla ilişkisi sonuç-koşulludur
   ("çıkıştan önceki son tez durumu SINANIYOR olan işlemlerin neredeyse hepsi stop oldu" bir
   çıkış gerekçesi değildir: stopa giden yol zaten oradan geçer); doğru soru "o kapanıştan
   sonra kalmak para kaybettirir mi?" sorusudur. Aynı yaştaki bütün açık işlemlerin koşulsuz
   ileri beklentisi de yanında verilir.
2. **Eşleşmiş replay.** Aynı işlemler, aynı giriş / stop / hedef; tek fark işlem-içi
   politikadır. Çıkış politikaları iki uygulama fiyatıyla ölçülür: sinyal barının kapanışı
   (iyimser) ve bir sonraki barın açılışı (uygulanabilir). Kabul için ikincisi sayılır.

Sözleşme §5 / T4: korunma kuralı önce gölge defterde yarışır; n<30 sayılmaz. Bu rapor
keşif niteliğindedir: tek arşiv, çok sayıda aday. Buradan çıkan hiçbir kural canlıya
geçmez; en fazla ileriye dönük gölge defterde izlenecek aday üretir.

Kullanım::

    python -m research.golge_v2_surec_olcum --workers 2 [--cache-dir D] [--cikti D] [--limit N]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import functools
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import time
from typing import Any

import numpy as np
import pandas as pd

from research.golge_v2 import KOK, _evren_oku, _veri_ozeti, kod_ozeti
from senaryo_v2.adaptor import hazirla_gunluk_baglam, seriyi_hazirla
from senaryo_v2.modeller import MAX_BEKLEME_LIMIT, TAMPON_VARSAYILAN_ATR, UFUK_VARSAYILAN_BAR
from senaryo_v2.olaylar import aday_olaylari_cikar
from senaryo_v2.plan import plan_karti_olustur
from senaryo_v2.rapor import kume_bootstrap_ozet, surec_izini_coz, zaman_kumesi_saglamligi
from senaryo_v2.surec import (
    TEZ_BOZULDU,
    TEZ_KISA,
    TEZ_SINANIYOR,
    TEZ_TEYITLI,
    HedefteIzSur,
    HedefteYapiIzSur,
    KarKoruma,
    OlaydaCik,
    SurecGozcusu,
    SurecPolitikasi,
    TezDurumundaCik,
    surec_ozetle,
)
from senaryo_v2.yaris import surecli_yaris

VARSAYILAN_CIKTI = KOK / "docs/arastirma/sonuclar/golge_v2/surec_olcum"
ANA_MOD0_CSV = KOK / "docs/arastirma/sonuclar/golge_v2/mod0_baz.csv.gz"
TFS: tuple[str, ...] = ("4h", "1d")
HEDEF_ATR: float = 2.0
MASRAF_ORAN: float = 0.0030          # 30 bps gidiş-dönüş (ana rapordaki `net15`)
MIN_N: int = 30                      # sözleşme: n<30 sayılmaz
DONEMLER: tuple[str, ...] = ("tumu", "kesif", "dogrulama")
A_KATMANLARI = ("A_ARTI", "A_CEKIRDEK")

KUMELER: dict[str, Any] = {
    "D7_A_Arti": lambda df: df["kalite_katmani"] == "A_ARTI",
    "D6_A_Cekirdek_Veya_Arti": lambda df: df["kalite_katmani"].isin(A_KATMANLARI),
    "D1_Birincil": lambda df: df["sinyal_sinifi"] == "BIRINCIL",
}

_MS_TERS_KIRILIM = frozenset({"MS_EXT_BOS_TERS", "MS_EXT_CHOCH_TERS", "MS_INT_BOS_TERS", "MS_INT_CHOCH_TERS"})

# Ön-kayıtlı varyant listesi: ad -> (aile, politikalar, çıkış modu, açıklama).
# Liste bilerek kısadır; sonuç görüldükten sonra varyant eklemek ölçümü geçersiz kılar.
VARYANTLAR: dict[str, tuple[str, tuple[SurecPolitikasi, ...], str, str]] = {}


def _cikis_varyanti(ad: str, politika: SurecPolitikasi, aciklama: str, *, kapanis_da: bool = False) -> None:
    VARYANTLAR[f"{ad}_acilis"] = ("cikis", (politika,), "sonraki_acilis", aciklama + " → sonraki açılışta çık")
    if kapanis_da:
        VARYANTLAR[f"{ad}_kapanis"] = ("cikis", (politika,), "kapanis", aciklama + " → aynı kapanışta çık (iyimser)")


_cikis_varyanti("seviye_ici", OlaydaCik(frozenset({"SEVIYE_ICI"}), "SEVIYE_CIKIS"), "Kapanış tez seviyesinin ters tarafında", kapanis_da=True)
_cikis_varyanti("tez_bozuldu", TezDurumundaCik(frozenset({TEZ_BOZULDU}), "TEZ_BOZULDU"), "Tez BOZULDU", kapanis_da=True)
_cikis_varyanti("frm_retest", OlaydaCik(frozenset({"FRM_RETEST"}), "RETEST_CIKIS"), "Formasyon RETEST_EDILIYOR", kapanis_da=True)
_cikis_varyanti("ters_kapanis", OlaydaCik(frozenset({"FIYAT_TERS_KAPANIS"}), "TERS_KAPANIS_CIKIS"), "İlk ters kapanış")
_cikis_varyanti("blok_duvar", OlaydaCik(frozenset({"BLOK_DUVAR"}), "DUVAR_CIKIS"), "Karşı OB/FVG bandında ret")
_cikis_varyanti("sr_red", OlaydaCik(frozenset({"SR_KARSI_RED"}), "SR_RED_CIKIS"), "Karşı Stabil çizgisinde ret")
_cikis_varyanti("vp_ters", OlaydaCik(frozenset({"VP_TERS_BASKI"}), "VP_CIKIS"), "Ters hacim baskısı")
_cikis_varyanti("ms_ters", OlaydaCik(_MS_TERS_KIRILIM, "MS_TERS_CIKIS"), "Ters yapı kırılımı (iç/dış BOS-CHoCH)")
_cikis_varyanti("aday_karsi", OlaydaCik(frozenset({"ADAY_KARSI"}), "KARSI_ADAY_CIKIS"), "Sistemin kendi karşı yön adayı")
VARYANTLAR["kar_1_0"] = ("koruma", (KarKoruma(1.0, 0.0),), "kapanis", "+1R görülünce stop başa baş")
VARYANTLAR["kar_1_025"] = ("koruma", (KarKoruma(1.0, 0.25),), "kapanis", "+1R görülünce stop +0.25R")
VARYANTLAR["kar_15_05"] = ("koruma", (KarKoruma(1.5, 0.5),), "kapanis", "+1.5R görülünce stop +0.5R")
VARYANTLAR["hedef_kilit_10"] = ("hedef", (HedefteIzSur(kilit_atr=1.0),), "kapanis", "Hedefte çıkma; +1.0 ATR kilitle, ufka taşı")
VARYANTLAR["hedef_kilit_15"] = ("hedef", (HedefteIzSur(kilit_atr=1.5),), "kapanis", "Hedefte çıkma; +1.5 ATR kilitle, ufka taşı")
VARYANTLAR["hedef_iz_15"] = ("hedef", (HedefteIzSur(kilit_atr=1.0, iz_atr=1.5),), "kapanis", "Hedefte çıkma; +1.0 ATR kilit + 1.5 ATR kapanış izi")
VARYANTLAR["hedef_iz_10"] = ("hedef", (HedefteIzSur(kilit_atr=1.5, iz_atr=1.0),), "kapanis", "Hedefte çıkma; +1.5 ATR kilit + 1.0 ATR kapanış izi")
VARYANTLAR["hedef_yapi"] = ("hedef", (HedefteYapiIzSur(kilit_atr=1.0, tampon_atr=0.10),), "kapanis", "Hedefte çıkma; +1.0 ATR kilit + iç yapı korunan seviye izi")

AILE_ADI = {"cikis": "Aleyhte gözlemde çıkış", "koruma": "Kâr koruma (stop taşıma)", "hedef": "Hedefte çıkmayıp iz sürme"}


@functools.lru_cache(maxsize=1)
def _olcum_ozeti() -> str:
    h = hashlib.sha256(kod_ozeti().encode("utf-8"))
    h.update(Path(__file__).read_bytes())
    return h.hexdigest()[:12]


# ---------------------------------------------------------------------------
# Sembol işçisi
# ---------------------------------------------------------------------------
def _sembol_isle(sembol: str) -> list[dict[str, Any]]:
    baglam = hazirla_gunluk_baglam(sembol)
    satirlar: list[dict[str, Any]] = []
    for tf in TFS:
        seri = seriyi_hazirla(sembol, tf, gunluk_baglam=baglam, bloklari_yukle=True)
        if seri.domain_hatali:
            continue
        barlar = seri.barlar
        olaylar = list(aday_olaylari_cikar(seri))
        bar_olaylari: dict[int, list[Any]] = defaultdict(list)
        for o in olaylar:
            bar_olaylari[o.bar_index].append(o)

        for o in olaylar:
            if not (o.sinyal_sinifi == "BIRINCIL" or o.kalite_katmani in A_KATMANLARI):
                continue
            i = o.bar_index
            if i + UFUK_VARSAYILAN_BAR > len(barlar) - 1:
                continue  # sansürlü: ufuk arşivin dışında
            if seri.karantina_nedeni(i, ileri_bar=MAX_BEKLEME_LIMIT + UFUK_VARSAYILAN_BAR):
                continue
            plan = plan_karti_olustur(o, barlar[i], mod="mod0", tampon_atr=TAMPON_VARSAYILAN_ATR)
            giris, stop, atr = float(plan.giris), float(plan.stop), float(o.atr_tf)
            risk = abs(giris - stop)
            if risk <= 1e-9 or atr <= 0:
                continue
            d = 1.0 if o.yon == "long" else -1.0
            hedef = giris + d * HEDEF_ATR * atr
            # Ana koşucuyla aynı masraf tanımı (risk ATR'si 4 haneye yuvarlanır).
            masraf_r = MASRAF_ORAN * giris / max(round(risk / atr, 4) * atr, 1e-6)

            def kos(politikalar: tuple[SurecPolitikasi, ...] = (), cikis_modu: str = "kapanis"):
                gozcu = SurecGozcusu(
                    barlar,
                    yon=o.yon,
                    giris=giris,
                    risk=risk,
                    atr_baz=atr,
                    tez_seviyesi=o.zemin_tavan,
                    frm_stable_id=barlar[i].frm_stable_id,
                    dolum_idx=i,
                    olay_bar_idx=i,
                    bar_olaylari=bar_olaylari,
                    kendi_olay_id=o.olay_id,
                )
                return surecli_yaris(
                    barlar,
                    olay_bar_idx=i,
                    dolum_idx=i,
                    start_scan_idx=i + 1,
                    yon=o.yon,
                    giris=giris,
                    stop=stop,
                    hedef=hedef,
                    atr_baz=atr,
                    ufuk_bar=UFUK_VARSAYILAN_BAR,
                    intrabar=True,
                    tez_iptal=True,
                    gozcu=gozcu,
                    politikalar=politikalar,
                    cikis_modu=cikis_modu,
                )

            baz = kos()
            if baz.pnl_r is None:
                continue
            ozet = surec_ozetle(baz.gozlemler, mfe_r=baz.mfe_r, mae_r=baz.mae_r, mfe_bar=baz.mfe_bar)
            satir: dict[str, Any] = {
                "olay_id": o.olay_id,
                "sembol": o.sembol,
                "tf": o.tf,
                "yon": o.yon,
                "donem": o.donem,
                "bar_close_time": o.bar_close_time,
                "sinyal_sinifi": o.sinyal_sinifi,
                "kalite_katmani": o.kalite_katmani,
                "masraf_r": round(masraf_r, 6),
                "baz_brut": baz.pnl_r,
                "baz_net": round(baz.pnl_r - masraf_r, 4),
                "baz_neden": baz.neden,
                "baz_bar": baz.cozulme_offset,
                "baz_mfe_r": ozet.mfe_r,
                "baz_mae_r": ozet.mae_r,
                "tez_yolu": ozet.tez_yolu,
                "surec_izi": ozet.olay_izi,
                # Her kapanıştaki açık R (k=1..gözlem_n): ileri beklenti bundan türetilir.
                "acik_r_yolu": "|".join(f"{g.acik_r:.4f}" for g in baz.gozlemler),
            }
            for ad, (_aile, politikalar, cikis_modu, _aciklama) in VARYANTLAR.items():
                iz = kos(politikalar, cikis_modu)
                satir[f"{ad}_net"] = round(iz.pnl_r - masraf_r, 4)
                satir[f"{ad}_neden"] = iz.neden
                satir[f"{ad}_bar"] = iz.cozulme_offset
            satirlar.append(satir)
    return satirlar


def _sembol_onbellekli(sembol: str, cache_dir: Path | None) -> list[dict[str, Any]]:
    if cache_dir is None:
        return _sembol_isle(sembol)
    cache_dir.mkdir(parents=True, exist_ok=True)
    yol = cache_dir / f"surec__{sembol}__{_olcum_ozeti()}_{_veri_ozeti(sembol)}.pkl.gz"
    if yol.exists():
        with gzip.open(yol, "rb") as f:
            return pickle.load(f)
    sonuc = _sembol_isle(sembol)
    gecici = yol.with_name(yol.name + ".tmp")
    with gzip.open(gecici, "wb") as f:
        pickle.dump(sonuc, f, protocol=pickle.HIGHEST_PROTOCOL)
    gecici.replace(yol)
    return sonuc


# ---------------------------------------------------------------------------
# İstatistik
# ---------------------------------------------------------------------------
def _donem_alt(df: pd.DataFrame, donem: str) -> pd.DataFrame:
    return df if donem == "tumu" else df[df["donem"] == donem]


def _aralik_ozeti(df: pd.DataFrame, kolon: str) -> dict[str, Any]:
    """Ortalama + dört küme tanımının (sembol/gün/hafta/ay) en kötü alt ve en kötü üst sınırı."""
    oz = zaman_kumesi_saglamligi(df, kolon, B=800)
    ustler = [k["ci95_ust"] for k in oz["kumeler"].values() if k["ci95_ust"] is not None]
    sembol = oz["kumeler"].get("sembol", {})
    return {
        "n": oz["n"],
        "ort": oz["ort"],
        "sembol_ga": [sembol.get("ci95_alt"), sembol.get("ci95_ust")],
        "en_kotu_alt": oz["en_kotu_alt"],
        "en_kotu_ust": max(ustler) if ustler else None,
        "hepsinde_pozitif": oz["hepsinde_pozitif"],
    }


def ileri_beklenti_tablosu(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Etiket ilk görüldüğü kapanıştan sonra işlemde KALMANIN brüt R'si.

    `ileri_r = nihai brüt R − o kapanıştaki açık R`. `kosulsuz_r`, aynı yaşta (aynı k'da)
    açık olan BÜTÜN işlemlerin ileri beklentisidir (etiketi taşıyanlar dahil; fark bu yüzden
    sıfıra doğru yanlıdır); `fark = ileri − koşulsuz` etiketin taşıdığı bilgidir.

    İki ayrı soru, iki ayrı bayrak:

    * `bilgi` — etiket bir şey söylüyor mu? `fark`'ın en kötü aralığı sıfırı dışlıyorsa
      `KOTU` / `IYI`.
    * `cikis_adayi` — etiket çıkış gerekçesi olabilir mi? Yalnız `ileri_r`'nin KENDİSİ
      negatifse: koşulsuzdan düşük ama pozitif bir beklenti "ortalamadan kötü" demektir,
      "çık" demek değildir.
    """
    kayitlar: list[dict[str, Any]] = []
    yas_toplam: dict[int, list[float]] = defaultdict(list)
    for r in df.to_dict("records"):
        yol = [float(x) for x in r["acik_r_yolu"].split("|")] if r["acik_r_yolu"] else []
        for k, acik in enumerate(yol, 1):
            yas_toplam[k].append(r["baz_brut"] - acik)
        ilk: dict[str, int] = {}
        for k, etiketler in surec_izini_coz(r["surec_izi"]):
            for e in etiketler:
                ilk.setdefault(e, k)
        for kisa, durum in ((TEZ_KISA[TEZ_SINANIYOR], "TEZ=SINANIYOR"), (TEZ_KISA[TEZ_BOZULDU], "TEZ=BOZULDU"), (TEZ_KISA[TEZ_TEYITLI], "TEZ=TEYITLI")):
            konum = r["tez_yolu"].find(kisa)
            if konum >= 0:
                ilk[durum] = konum + 1
        for e, k in ilk.items():
            if 1 <= k <= len(yol):
                kayitlar.append(
                    {
                        "etiket": e,
                        "sembol": r["sembol"],
                        "donem": r["donem"],
                        "bar_close_time": r["bar_close_time"],
                        "k": k,
                        "acik_r": yol[k - 1],
                        "ileri_r": r["baz_brut"] - yol[k - 1],
                    }
                )
    if not kayitlar:
        return []
    kosulsuz = {k: float(np.mean(v)) for k, v in yas_toplam.items()}
    uzun = pd.DataFrame(kayitlar)
    uzun["kosulsuz_r"] = uzun["k"].map(kosulsuz)
    uzun["fark_r"] = uzun["ileri_r"] - uzun["kosulsuz_r"]

    tablo: list[dict[str, Any]] = []
    for etiket, grp in uzun.groupby("etiket", sort=True):
        ileri = _aralik_ozeti(grp, "ileri_r")
        fark = _aralik_ozeti(grp, "fark_r")
        satir = {
            "etiket": etiket,
            "n": int(len(grp)),
            "sayilir": bool(len(grp) >= MIN_N),
            "medyan_k": float(grp["k"].median()),
            "ort_acik_r": round(float(grp["acik_r"].mean()), 4),
            "ileri_r": ileri["ort"],
            "ileri_en_kotu_alt": ileri["en_kotu_alt"],
            "ileri_en_kotu_ust": ileri["en_kotu_ust"],
            "kosulsuz_r": round(float(grp["kosulsuz_r"].mean()), 4),
            "fark_r": fark["ort"],
            "fark_en_kotu_alt": fark["en_kotu_alt"],
            "fark_en_kotu_ust": fark["en_kotu_ust"],
        }
        for donem in ("kesif", "dogrulama"):
            alt = grp[grp["donem"] == donem]
            satir[f"{donem}_n"] = int(len(alt))
            satir[f"{donem}_ileri_r"] = round(float(alt["ileri_r"].mean()), 4) if len(alt) else None
        # Dönem hücresi de n<30 ise sayılmaz: "iki dönemde de" iddiası iki dolu hücre ister.
        iki_donem_dolu = min(satir["kesif_n"], satir["dogrulama_n"]) >= MIN_N
        satir["iki_donemde_negatif"] = bool(
            satir["sayilir"] and iki_donem_dolu and satir["kesif_ileri_r"] < 0 and satir["dogrulama_ileri_r"] < 0
        )
        # Bilgi: etiketten sonra kalmak, aynı yaştaki sıradan işlemde kalmaktan ayırt edilebilir mi?
        if not satir["sayilir"] or fark["en_kotu_alt"] is None:
            satir["bilgi"] = ""
        elif fark["en_kotu_ust"] < 0:
            satir["bilgi"] = "KOTU"
        elif fark["en_kotu_alt"] > 0:
            satir["bilgi"] = "IYI"
        else:
            satir["bilgi"] = ""
        # Çıkış adayı: kalmanın KENDİSİ zarar (en kötü üst sınır < 0) ve bu iki dönemde de görülüyor.
        satir["cikis_adayi"] = bool(
            satir["iki_donemde_negatif"] and ileri["en_kotu_ust"] is not None and ileri["en_kotu_ust"] < 0
        )
        tablo.append(satir)
    tablo.sort(key=lambda s: (s["ileri_r"] if s["ileri_r"] is not None else 0.0, s["etiket"]))
    return tablo


def varyant_ozeti(df: pd.DataFrame, ad: str) -> dict[str, Any]:
    """Eşleşmiş fark (varyant − baz) ve dönem dönem dayanıklılığı."""
    aile, _politikalar, cikis_modu, aciklama = VARYANTLAR[ad]
    calisma = df[["sembol", "donem", "bar_close_time", "baz_net"]].copy()
    calisma["fark"] = df[f"{ad}_net"] - df["baz_net"]
    calisma["etkilenen"] = (df[f"{ad}_neden"] != df["baz_neden"]) | (df[f"{ad}_bar"] != df["baz_bar"]) | (calisma["fark"].abs() > 1e-9)
    sonuc: dict[str, Any] = {"varyant": ad, "aile": aile, "cikis_modu": cikis_modu, "aciklama": aciklama, "donemler": {}}
    for donem in DONEMLER:
        alt = _donem_alt(calisma, donem)
        if alt.empty:
            sonuc["donemler"][donem] = {"n": 0}
            continue
        etk = alt[alt["etkilenen"]]
        oz = _aralik_ozeti(alt, "fark")
        sonuc["donemler"][donem] = {
            "n": int(len(alt)),
            "etkilenen": int(len(etk)),
            "baz_net": round(float(alt["baz_net"].mean()), 4),
            "varyant_net": round(float((alt["baz_net"] + alt["fark"]).mean()), 4),
            "fark": oz["ort"],
            "fark_toplam_r": round(float(alt["fark"].sum()), 2),
            "fark_sembol_ga": oz["sembol_ga"],
            "fark_en_kotu_alt": oz["en_kotu_alt"],
            "fark_en_kotu_ust": oz["en_kotu_ust"],
            # Etkilenen işlemlerde baz kazanan mıydı kaybeden mi? (kural kimi kesiyor)
            "etkilenen_baz_kazanan": int((etk["baz_net"] > 0).sum()),
            "etkilenen_baz_kaybeden": int((etk["baz_net"] <= 0).sum()),
            "iyilesen": int((etk["fark"] > 1e-9).sum()),
            "kotulesen": int((etk["fark"] < -1e-9).sum()),
        }
    t, k, d = (sonuc["donemler"][x] for x in DONEMLER)
    # Dönem hücresi de n<30 ise sayılmaz: "iki dönemde de pozitif" iddiası iki dolu hücre ister.
    donem_ince = min(k.get("etkilenen", 0), d.get("etkilenen", 0)) < MIN_N
    if t.get("etkilenen", 0) < MIN_N or not k.get("n") or not d.get("n"):
        karar = "SAYILMAZ_N<30"
    elif (t["fark_en_kotu_ust"] if t["fark_en_kotu_ust"] is not None else 1) < 0:
        karar = "ZARARLI"
    elif not (k["fark"] > 0 and d["fark"] > 0):
        karar = "GECMEDI"
    elif donem_ince:
        karar = "ZAYIF_ARTI"
    elif (k["fark_en_kotu_alt"] or -1) > 0 and (d["fark_en_kotu_alt"] or -1) > 0:
        karar = "GECTI"
    elif (t["fark_en_kotu_alt"] or -1) > 0:
        karar = "UMUT_VAR"
    else:
        karar = "ZAYIF_ARTI"
    sonuc["karar"] = karar
    sonuc["donem_ince"] = bool(donem_ince)
    return sonuc


def ozdes_varyantlar(df: pd.DataFrame) -> list[list[str]]:
    """Bütün işlemlerde birebir aynı sonucu (net R, çıkış nedeni, çıkış barı) veren varyant grupları.

    İki varyant özdeşse aralarındaki fark (ör. yapı izi) bu örneklemde hiç devreye girmemiştir;
    ayrı iki kanıt gibi okunmamalıdır.
    """
    gruplar: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for ad in VARYANTLAR:
        imza = (tuple(df[f"{ad}_net"].round(9)), tuple(df[f"{ad}_neden"]), tuple(df[f"{ad}_bar"]))
        gruplar[imza].append(ad)
    return [g for g in gruplar.values() if len(g) > 1]


def _baz_esitligi(df: pd.DataFrame) -> dict[str, Any]:
    """Bu koşucunun baz sonucu, ana rapordaki `net15_20_r` ile aynı mı? (varsa)."""
    if not ANA_MOD0_CSV.is_file():
        return {"durum": "ana_csv_yok"}
    ana = pd.read_csv(ANA_MOD0_CSV, usecols=["olay_id", "net15_20_r"])
    ortak = df.merge(ana, on="olay_id", how="inner")
    if ortak.empty:
        return {"durum": "ortak_olay_yok"}
    fark = (ortak["baz_net"] - ortak["net15_20_r"]).abs()
    return {
        "durum": "karsilastirildi",
        "ortak_n": int(len(ortak)),
        "olcumde_olup_anada_olmayan": int(len(df) - len(ortak)),
        "max_mutlak_fark": round(float(fark.max()), 6),
        "farkli_n": int((fark > 1.5e-4).sum()),
    }


# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------
def _f(x: Any, hane: int = 4) -> str:
    return "-" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:+.{hane}f}"


def _baz_esitligi_metni(be: dict[str, Any]) -> str:
    if be.get("durum") != "karsilastirildi":
        return "ana rapor CSV'si bulunamadı; karşılaştırılmadı."
    return (
        f"`{be['ortak_n']}` ortak işlemde en büyük mutlak fark `{be['max_mutlak_fark']}` R, "
        f"farklı işlem `{be['farkli_n']}`; ana CSV'de bulunmayan işlem `{be['olcumde_olup_anada_olmayan']}`."
    )


def _markdown(ozet: dict[str, Any]) -> str:
    m = ozet["meta"]
    s: list[str] = [
        "# Gölge v2 — İşlem-İçi Süreç Ölçümü",
        "",
        "> Üretici: `python -m research.golge_v2_surec_olcum`. Bu dosya elle düzenlenmez.",
        "",
        f"- Evren: `{m['sembol_sayisi']}` sembol, `4h + 1d`, Mod 0, `2.0 ATR` hedef, 10 bar ufuk, `30 bps` masraf.",
        f"- İşlem (sansürsüz, veri karantinası dışı): `{m['islem_n']}`; kod özeti `{m['kod_ozeti']}`.",
        f"- Baz eşitliği (bu koşucunun bazı ile ana rapordaki `net15_20_r`): {_baz_esitligi_metni(m['baz_esitligi'])}",
        "",
        "**Okuma kılavuzu.** `İleri R`, etiketin ilk görüldüğü kapanıştan sonra işlemde kalmanın brüt getirisidir "
        "(pozitifse kalmak kazandırır). `Aynı yaşta koşulsuz`, aynı kapanış sayısında açık olan bütün işlemlerin ileri "
        "getirisidir; `Fark` ikisinin farkıdır ve etiketin taşıdığı bilgiyi ölçer. `Bilgi`: bu farkın en kötü aralığı "
        "sıfırı dışlıyorsa `KOTU` / `IYI`. `Çıkış adayı`: `İleri R`'nin kendisi iki dönemde de negatif ve en kötü üst "
        "sınırı sıfırın altında. Replay tablolarında `Fark`, varyantın aynı işlemlerde baza göre net R farkıdır. "
        "Aralıklar dört küme tanımının (sembol / gün / hafta / ay) **en kötüsüdür**. `n<30` sayılmaz; bu, dönem "
        "hücreleri için de geçerlidir. Çıkış politikalarında kabul için `sonraki açılış` uygulaması esas alınır; "
        "`kapanış` uygulaması iyimser üst sınırdır.",
        "",
        "**Kabul kuralı.** `GECTI`: fark hem keşif hem doğrulama döneminde pozitif, iki dönemde de etkilenen işlem ≥ 30 "
        "ve en kötü alt sınır sıfırın üstünde. `UMUT_VAR`: aynı koşullar, ama alt sınır yalnız havuzda sıfırın üstünde. "
        "`ZAYIF_ARTI`: iki dönemde de pozitif ama aralık sıfırı içeriyor ya da bir dönemde etkilenen işlem < 30. "
        "`ZARARLI`: havuzda en kötü üst sınır bile negatif. `GECMEDI`: en az bir dönemde fark pozitif değil.",
    ]
    for kume, veri in ozet["kumeler"].items():
        s += ["", f"## {kume}", "", f"İşlem: `{veri['n']}` (keşif `{veri['kesif_n']}`, doğrulama `{veri['dogrulama_n']}`); "
              f"baz net `{_f(veri['baz_net'])} R`."]
        s += [
            "",
            "### İleri beklenti (etiket ilk görüldükten sonra işlemde kalmanın brüt R'si)",
            "",
            "| Etiket | N | İlk bar | O andaki açık R | İleri R | En kötü GA | Keşif (n) | Doğrulama (n) | Aynı yaşta koşulsuz | Fark | Fark en kötü GA | Bilgi | Çıkış adayı |",
            "|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|---|---|",
        ]
        for r in veri["ileri_beklenti"]:
            if not r["sayilir"]:
                continue
            s.append(
                f"| {r['etiket']} | {r['n']} | {r['medyan_k']:g} | {_f(r['ort_acik_r'], 3)} | {_f(r['ileri_r'], 3)} | "
                f"[{_f(r['ileri_en_kotu_alt'], 3)}, {_f(r['ileri_en_kotu_ust'], 3)}] | "
                f"{_f(r['kesif_ileri_r'], 3)} ({r['kesif_n']}) | {_f(r['dogrulama_ileri_r'], 3)} ({r['dogrulama_n']}) | "
                f"{_f(r['kosulsuz_r'], 3)} | {_f(r['fark_r'], 3)} | "
                f"[{_f(r['fark_en_kotu_alt'], 3)}, {_f(r['fark_en_kotu_ust'], 3)}] | "
                f"{('**' + r['bilgi'] + '**') if r['bilgi'] else '—'} | {'**evet**' if r['cikis_adayi'] else 'hayır'} |"
            )
        atlanan = [r["etiket"] for r in veri["ileri_beklenti"] if not r["sayilir"]]
        if atlanan:
            s += ["", f"`n<{MIN_N}` olduğu için tabloya alınmayan etiketler: " + ", ".join(f"`{e}`" for e in atlanan) + "."]
        for aile, baslik in AILE_ADI.items():
            s += [
                "",
                f"### Eşleşmiş replay — {baslik}",
                "",
                "| Varyant | Etkilenen | Etkilenenlerde baz kazanan / kaybeden | Fark R (tümü) | En kötü GA | Keşif (etkilenen) | Doğrulama (etkilenen) | Toplam R | Karar |",
                "|---|---:|---:|---:|---|---:|---:|---:|---|",
            ]
            for v in veri["varyantlar"]:
                if v["aile"] != aile:
                    continue
                t, k, d = (v["donemler"][x] for x in DONEMLER)
                s.append(
                    f"| `{v['varyant']}` — {v['aciklama']} | {t['etkilenen']} | {t['etkilenen_baz_kazanan']} / {t['etkilenen_baz_kaybeden']} | "
                    f"{_f(t['fark'])} | [{_f(t['fark_en_kotu_alt'])}, {_f(t['fark_en_kotu_ust'])}] | "
                    f"{_f(k.get('fark'))} ({k.get('etkilenen', 0)}) | {_f(d.get('fark'))} ({d.get('etkilenen', 0)}) | "
                    f"{_f(t['fark_toplam_r'], 1)} | **{v['karar']}** |"
                )
    s += ["", "## Özet karar", ""]
    for kume, veri in ozet["kumeler"].items():
        def _liste(adlar: list[str]) -> str:
            return ", ".join(f"`{x}`" for x in adlar) or "yok"

        kararlar = {k: [v["varyant"] for v in veri["varyantlar"] if v["karar"] == k] for k in ("GECTI", "UMUT_VAR", "ZAYIF_ARTI", "ZARARLI")}
        s += [
            f"- **{kume}**",
            f"  - Replay: GECTI = {_liste(kararlar['GECTI'])}; UMUT_VAR = {_liste(kararlar['UMUT_VAR'])}; "
            f"ZARARLI = {_liste(kararlar['ZARARLI'])}; ZAYIF_ARTI = {_liste(kararlar['ZAYIF_ARTI'])}.",
            f"  - Etiketler: çıkış adayı = {_liste([r['etiket'] for r in veri['ileri_beklenti'] if r['cikis_adayi']])}; "
            f"bilgi `KOTU` = {_liste([r['etiket'] for r in veri['ileri_beklenti'] if r['bilgi'] == 'KOTU'])}; "
            f"bilgi `IYI` = {_liste([r['etiket'] for r in veri['ileri_beklenti'] if r['bilgi'] == 'IYI'])}; "
            f"ileri R iki dönemde de negatif (aralığa bakılmadan) = "
            f"{_liste([r['etiket'] for r in veri['ileri_beklenti'] if r['iki_donemde_negatif']])}.",
        ]
    s += [
        "",
        "## Sınırlar",
        "",
        f"- {len(VARYANTLAR)} varyant × {len(KUMELER)} küme sınandı; çoklu karşılaştırma düzeltmesi yapılmadı. "
        "`GECTI` bile yalnız ileriye dönük gölge defterde izlenecek aday demektir.",
        "- Keşif ve doğrulama dönemleri aynı arşivin iki dilimidir; baz beklenti iki dönem arasında belirgin oynar "
        "(özellikle short tarafı), bu yüzden tek dönemde görünen iyileşme rejim etkisi olabilir.",
        "- Bar içi sıra bilinmez: stop ile hedef aynı barda ise stop sayılır; taşınan stop ve politika çıkışı bir sonraki "
        "bardan itibaren işler. Hedefe değilen barda kilit o bar için geçerli değildir.",
        "- İzleme işlemin kendi zaman dilimindedir (4h / 1d barları). Alt zaman dilimiyle yönetim ayrı ölçümdür (`mtf_olcum`).",
        "- Üç küme iç içedir (`D7 ⊂ D6 ⊂ D1`); bir kuralın üç kümede de aynı yönde çıkması üç bağımsız doğrulama değildir.",
        "- `Bilgi` bayrakları da çoklu karşılaştırmaya göre düzeltilmemiştir (küme başına onlarca etiket sınanır).",
    ]
    for grup in m.get("ozdes_varyantlar", []):
        s.append(
            "- Bütün işlemlerde birebir aynı sonucu veren varyantlar: " + " = ".join(f"`{x}`" for x in grup)
            + ". Aralarındaki fark bu örneklemde hiç devreye girmedi; ayrı kanıt sayılmaz."
        )
    return "\n".join(s) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gölge v2 işlem-içi süreç ölçümü")
    ap.add_argument("--evren", choices=("evren176", "hisse174"), default="evren176")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--cache-dir", type=Path, default=None)
    ap.add_argument("--cikti", type=Path, default=VARSAYILAN_CIKTI)
    args = ap.parse_args(argv)

    semboller = _evren_oku(args.evren, args.limit)
    t0 = time.perf_counter()
    sonuc_by_sembol: dict[str, list[dict[str, Any]]] = {}
    if args.workers <= 1:
        for i, sym in enumerate(semboller, 1):
            sonuc_by_sembol[sym] = _sembol_onbellekli(sym, args.cache_dir)
            if i % 10 == 0 or i == len(semboller):
                print(f"[{i}/{len(semboller)}] {sym}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(_sembol_onbellekli, sym, args.cache_dir): sym for sym in semboller}
            for i, fut in enumerate(as_completed(futs), 1):
                sonuc_by_sembol[futs[fut]] = fut.result()
                if i % 10 == 0 or i == len(semboller):
                    print(f"[{i}/{len(semboller)}] {futs[fut]}", flush=True)

    satirlar = [r for sym in semboller for r in sonuc_by_sembol[sym]]  # evren sırası: deterministik
    df = pd.DataFrame(satirlar)
    if df.empty:
        print("Ölçülecek işlem yok.", flush=True)
        return 1
    args.cikti.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.cikti / "islemler.csv.gz", index=False, compression="gzip")

    kumeler: dict[str, Any] = {}
    for kume, maske in KUMELER.items():
        alt = df[maske(df)]
        if alt.empty:
            continue
        kumeler[kume] = {
            "n": int(len(alt)),
            "kesif_n": int((alt["donem"] == "kesif").sum()),
            "dogrulama_n": int((alt["donem"] == "dogrulama").sum()),
            "baz_net": round(float(alt["baz_net"].mean()), 4),
            "baz": {donem: kume_bootstrap_ozet(_donem_alt(alt, donem), "baz_net", B=800) for donem in DONEMLER},
            "ileri_beklenti": ileri_beklenti_tablosu(alt),
            "varyantlar": [varyant_ozeti(alt, ad) for ad in VARYANTLAR],
        }
    ozet = {
        "meta": {
            "sembol_sayisi": len(semboller),
            "islem_n": int(len(df)),
            "sure_sn": round(time.perf_counter() - t0, 1),
            "kod_ozeti": _olcum_ozeti(),
            "tfs": list(TFS),
            "hedef_atr": HEDEF_ATR,
            "ufuk_bar": UFUK_VARSAYILAN_BAR,
            "masraf_oran": MASRAF_ORAN,
            "min_n": MIN_N,
            "baz_esitligi": _baz_esitligi(df),
            "ozdes_varyantlar": ozdes_varyantlar(df),
            "varyantlar": {ad: {"aile": v[0], "cikis_modu": v[2], "aciklama": v[3]} for ad, v in VARYANTLAR.items()},
        },
        "kumeler": kumeler,
    }
    (args.cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.cikti / "RAPOR.md").write_text(_markdown(ozet), encoding="utf-8")
    print(f"Tamamlandi ({ozet['meta']['sure_sn']}s) -> {args.cikti} | islem={len(df)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
