"""Gölge v2 veri karantinası — geri-bakış penceresine duyarlılık.

Karantina, düzeltilmemiş kurumsal işlem / durdurma kopukluğunu (açılışın önceki kapanıştan
`KOPUKLUK_ESIK_ORAN`'dan fazla kopması) işlem penceresinde ya da son `KOPUKLUK_KARANTINA_BAR`
barlık bağlamında taşıyan olayları sonuca bakmadan ölçüm dışı bırakır. Pencere uzunluğu bir
yargıdır (ATR(14) şokunun sönmesi); bu betik aynı olay kümesinde pencereyi değiştirerek
başlık sayılarının ve kabul kapısı girdilerinin bu yargıya ne kadar bağlı olduğunu gösterir.

Yarış yeniden koşulmaz: olay sonuçları ana CSV'den okunur, yalnız karantina bayrağı her
pencere için fiyat arşivinden yeniden hesaplanır. Varsayılan pencerenin CSV'deki
`veri_karantina` kolonunu birebir yeniden ürettiği doğrulanır.

İki uç seçenek de ölçülür: `geri_sinirsiz` (bir seride ilk kopukluktan sonraki BÜTÜN olaylar;
nedensel — kopukluk görüldükten sonra o seriye bir daha güvenilmez) ve `sembol_disi`
(herhangi bir serisinde kopukluk olan sembolün bütün olayları; nedensel değil, en temiz
örneklem). İkisi de bayat domain durumu dahil kopukluktan doğabilecek her kirlenme yolunu kapatır.

Kullanım::

    python -m research.golge_v2_karantina_duyarlilik [--girdi D] [--cikti D]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from domain_engines.stabil import prepare_causal_ohlcv
from research.arsiv import tf_frame
from research.golge_v2 import KOK
from senaryo_v2.adaptor import karantina_araliklari, kopukluk_barlarini_bul
from senaryo_v2.modeller import (
    KOPUKLUK_ESIK_ORAN,
    KOPUKLUK_KARANTINA_BAR,
    MAX_BEKLEME_LIMIT,
    UFUK_VARSAYILAN_BAR,
    SeriVerisi,
)
from senaryo_v2.rapor import kume_bootstrap_ozet

VARSAYILAN_GIRDI = KOK / "docs/arastirma/sonuclar/golge_v2"
PENCERELER: tuple[int, ...] = (0, 14, 30, KOPUKLUK_KARANTINA_BAR, 120)
SINIRSIZ: int = 10**9          # "ilk kopukluktan sonraki her şey" için geri-bakış uzunluğu
ILERI_BAR: int = MAX_BEKLEME_LIMIT + UFUK_VARSAYILAN_BAR
DONEMLER: tuple[str, ...] = ("tumu", "kesif", "dogrulama")
A_KATMANLARI = ("A_ARTI", "A_CEKIRDEK")


def _temiz_seri(sembol: str, tf: str) -> pd.DataFrame:
    temiz, hata = prepare_causal_ohlcv(tf_frame(sembol, tf), symbol=sembol, timeframe=tf)
    if hata and temiz.empty:
        raise ValueError(f"{sembol}/{tf} çerçeve hazırlanamadı: {hata}")
    return temiz


def karantina_bayraklari(
    olaylar: pd.DataFrame, pencereler: tuple[int, ...] = PENCERELER + (SINIRSIZ,)
) -> tuple[dict[int, np.ndarray], np.ndarray]:
    """(geri-bakış penceresi -> olay sırasına hizalı karantina bayrağı, kopukluklu sembol bayrağı)."""
    bayrak = {L: np.zeros(len(olaylar), dtype=bool) for L in pencereler}
    kopuk_sembol = np.zeros(len(olaylar), dtype=bool)
    konum = {oid: i for i, oid in enumerate(olaylar["olay_id"])}
    for sembol, grup in olaylar.groupby("sembol", sort=False):
        gunluk = _temiz_seri(str(sembol), "1d")
        gunluk_zamanlar = list(gunluk["timestamp"])
        gunluk_kopukluk = kopukluk_barlarini_bul(gunluk["open"].to_numpy(dtype=float), gunluk["close"].to_numpy(dtype=float))
        for tf, alt in grup.groupby("tf", sort=False):
            seri = _temiz_seri(str(sembol), str(tf))
            zamanlar = list(seri["timestamp"])
            kendi = kopukluk_barlarini_bul(seri["open"].to_numpy(dtype=float), seri["close"].to_numpy(dtype=float))
            if kendi or gunluk_kopukluk:
                kopuk_sembol[[konum[oid] for oid in grup["olay_id"]]] = True
            for L in pencereler:
                gorunur, kirli = karantina_araliklari(zamanlar, kendi, gunluk_zamanlar, gunluk_kopukluk, geri_bar=L)
                if not gorunur:
                    continue
                kabuk = SeriVerisi(sembol=str(sembol), tf=str(tf), barlar=(), kopukluk_gorunur_barlari=gorunur, kirli_araliklar=kirli)
                for oid, bar_index in zip(alt["olay_id"], alt["bar_index"]):
                    if kabuk.karantina_nedeni(int(bar_index), ileri_bar=ILERI_BAR):
                        bayrak[L][konum[oid]] = True
    return bayrak, kopuk_sembol


def _secenek_adi(L: int) -> str:
    return "geri_sinirsiz" if L >= SINIRSIZ else f"geri_{L}"


def duyarlilik_tablosu(
    olaylar: pd.DataFrame,
    bayrak: dict[int, np.ndarray],
    kopuk_sembol: np.ndarray,
    *,
    deger_col: str = "net15_20_r",
) -> list[dict[str, Any]]:
    dort_gun = olaylar["tf"].isin(["4h", "1d"]).to_numpy()
    kumeler = {
        "D7_A_Arti": dort_gun & (olaylar["kalite_katmani"] == "A_ARTI").to_numpy(),
        "D6_A_Cekirdek_Veya_Arti": dort_gun & olaylar["kalite_katmani"].isin(A_KATMANLARI).to_numpy(),
        "D1_Birincil": dort_gun & (olaylar["sinyal_sinifi"] == "BIRINCIL").to_numpy(),
    }
    secenekler: list[tuple[str, np.ndarray]] = [("karantinasiz", np.zeros(len(olaylar), dtype=bool))]
    secenekler += [(_secenek_adi(L), bayrak[L]) for L in sorted(bayrak)]
    secenekler.append(("sembol_disi", kopuk_sembol))
    satirlar: list[dict[str, Any]] = []
    for kume, maske in kumeler.items():
        for ad, karantina in secenekler:
            for donem in DONEMLER:
                donem_maske = np.ones(len(olaylar), dtype=bool) if donem == "tumu" else (olaylar["donem"] == donem).to_numpy()
                oz = kume_bootstrap_ozet(olaylar[maske & ~karantina & donem_maske], deger_col, B=1000)
                satirlar.append(
                    {
                        "kume": kume,
                        "karantina": ad,
                        "donem": donem,
                        "n": oz["n"],
                        "cikan": int((maske & karantina & donem_maske).sum()),
                        "ort": None if oz["ort"] is None else round(oz["ort"], 4),
                        "ci95_alt": oz["ci95_alt"],
                        "ci95_ust": oz["ci95_ust"],
                    }
                )
    return satirlar


def _markdown(ozet: dict[str, Any]) -> str:
    m = ozet["meta"]
    s = [
        "# Gölge v2 — Veri Karantinası Penceresine Duyarlılık",
        "",
        "> Üretici: `python -m research.golge_v2_karantina_duyarlilik`. Bu dosya elle düzenlenmez.",
        "",
        f"- Kopukluk eşiği: açılış / önceki kapanış farkı `%{m['esik_oran'] * 100:.1f}` üstü; ileri pencere `{m['ileri_bar']}` bar (sabit).",
        f"- Sansürsüz olay: `{m['olay_n']}`; seçeneğe göre karantinaya giren olay: "
        + ", ".join(f"`{k}` → `{v}`" for k, v in m["karantina_olay"].items()) + ".",
        f"- Varsayılan pencere (`{m['varsayilan_geri_bar']}` bar) ana CSV'deki `veri_karantina` kolonunu birebir yeniden üretti: "
        f"`{'evet' if m['varsayilan_csv_ile_ayni'] else 'HAYIR'}`.",
        "",
        "`geri_L`: kopukluktan sonraki `L` bar (günlük kopuklukta `L` günlük bar) kirli bağlam sayılır. `geri_0` yalnız kopukluk "
        "barının kendisini ve işlem penceresine düşen kopuklukları çıkarır. `geri_sinirsiz`: bir seride ilk kopukluktan sonraki "
        "bütün olaylar çıkar. `sembol_disi`: herhangi bir serisinde kopukluk olan sembol tümüyle çıkar "
        f"(`{m['kopuk_sembol_n']}` sembol). `4h + 1d`, `Net15` R, sembol kümeli %95 GA.",
    ]
    for kume in ("D7_A_Arti", "D6_A_Cekirdek_Veya_Arti", "D1_Birincil"):
        s += ["", f"## {kume}", "", "| Karantina | Tümü N | Tümü Ort R | Tümü GA | Keşif N | Keşif Ort R | Doğrulama N | Doğrulama Ort R | Doğrulama GA |", "|---|---:|---:|---|---:|---:|---:|---:|---|"]
        for ad in [x for x in dict.fromkeys(r["karantina"] for r in ozet["tablo"])]:
            t, k, d = (next(r for r in ozet["tablo"] if r["kume"] == kume and r["karantina"] == ad and r["donem"] == donem) for donem in DONEMLER)
            s.append(
                f"| {ad} | {t['n']} | {t['ort']} | [{t['ci95_alt']}, {t['ci95_ust']}] | {k['n']} | {k['ort']} | "
                f"{d['n']} | {d['ort']} | [{d['ci95_alt']}, {d['ci95_ust']}] |"
            )
    s += [
        "",
        "## Okuma",
        "",
        "- Karantina sonuca bakmaz; yalnız kopukluğun takvim konumuna bakar. Pencere büyüdükçe çıkan olay artar.",
        "- Kabul kapısı `D6` ve `D7` doğrulama dönemi alt sınırına bakar; bu iki alt sınırın pencereyle nasıl değiştiği "
        "kapı kararının veri temizliği yargısına ne kadar bağlı olduğunu gösterir.",
        "- `geri_sinirsiz` ve `sembol_disi` örneklemi küçültür; aralığın genişlemesi yalnız kirlenmeden değil, azalan "
        "gözlem sayısından da gelir.",
    ]
    return "\n".join(s) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gölge v2 veri karantinası penceresine duyarlılık")
    ap.add_argument("--girdi", type=Path, default=VARSAYILAN_GIRDI, help="mod0_baz.csv.gz dosyasının bulunduğu dizin")
    ap.add_argument("--cikti", type=Path, default=None, help="varsayılan: <girdi>/karantina_duyarlilik")
    args = ap.parse_args(argv)
    cikti = args.cikti or (args.girdi / "karantina_duyarlilik")

    olaylar = pd.read_csv(args.girdi / "mod0_baz.csv.gz", low_memory=False)
    olaylar = olaylar[~olaylar["sansurlu"].astype(bool)].reset_index(drop=True)
    bayrak, kopuk_sembol = karantina_bayraklari(olaylar)
    ayni = None
    if "veri_karantina" in olaylar.columns:
        ayni = bool((bayrak[KOPUKLUK_KARANTINA_BAR] == olaylar["veri_karantina"].to_numpy(dtype=bool)).all())
        if not ayni:
            raise ValueError("Varsayılan pencere CSV'deki veri_karantina kolonunu yeniden üretmedi")
    ozet = {
        "meta": {
            "olay_n": int(len(olaylar)),
            "esik_oran": KOPUKLUK_ESIK_ORAN,
            "ileri_bar": ILERI_BAR,
            "varsayilan_geri_bar": KOPUKLUK_KARANTINA_BAR,
            "varsayilan_csv_ile_ayni": ayni,
            "karantina_olay": {_secenek_adi(L): int(bayrak[L].sum()) for L in sorted(bayrak)} | {"sembol_disi": int(kopuk_sembol.sum())},
            "kopuk_sembol_n": int(olaylar.loc[kopuk_sembol, "sembol"].nunique()),
        },
        "tablo": duyarlilik_tablosu(olaylar, bayrak, kopuk_sembol),
    }
    cikti.mkdir(parents=True, exist_ok=True)
    (cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    (cikti / "RAPOR.md").write_text(_markdown(ozet), encoding="utf-8")
    print(f"Tamamlandi -> {cikti} | karantina: {ozet['meta']['karantina_olay']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
