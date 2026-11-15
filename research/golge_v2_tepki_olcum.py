"""Gölge v2 — kâr gördükten sonra aleyhte gözleme tepki: sistem tepki verseydi ne olurdu?

`golge_v2_kar_gorup_donen` raporu, 0.5 / 1 ATR gördükten sonra stop olan işlemlerde tepe ile
stop arasında neler görüldüğünü sayar: bilinen engele takılma, tez seviyesinin içine kapanış,
formasyon bozulması, Market Structure ters süpürmesi, ters hacim. Baz sistem bunları yalnız
KAYDEDER; işlem açıkken stop, hedef, süre ve ilk mumlardaki ters yapı kırılımında tez iptali
dışında bir şey yapmaz. Bu betik "o gözlemlere tepki verilseydi" sorusunu eşleşmiş replay ile
yanıtlar.

Yöntem (`golge_v2_surec_olcum` ile aynı motor, aynı işlemler, aynı giriş / ilk stop / hedef /
masraf): işlem çıkışa kadar en az `esik` ATR gördükten sonra (aynı kapanış dahil) tetik ilk kez
yandığında TEK bir tepki verilir.

- Tepki `cik`: bir sonraki mumun açılışında çık.
- Tepki `basabas`: stopu girişe çek (bir sonraki mumdan geçerli; motor stopu yalnız lehe taşır).

Tetik kapanışı yalnız o kapanışa kadar bilinenlerle bulunur (baz yarışın gözlem dizisinden);
politika o kapanışta bir kez karar verir. Baz yarışla varyant o kapanışa kadar birebir aynıdır,
bu yüzden tetik kapanışını baz yoldan okumak çevrim içi karar vermekle eşdeğerdir.

Tetik listesi `kar_gorup_donen` tablosunun satırlarıdır ve o tablo GÖRÜLDÜKTEN SONRA yazılmıştır:
bu ölçüm ön-kayıtlı değildir. Kabul merdiveni `surec_olcum` ile aynıdır; geçen bir varyant bile
kural değil, ileriye dönük gölge defterde izlenecek adaydır.

Kullanım::

    python -m research.golge_v2_tepki_olcum [--evren evren176] [--workers 2] [--cikti D] [--limit N]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from research import golge_v2_kar_gorup_donen as kg
from research import golge_v2_sonuc_anatomisi as sa
from research import golge_v2_surec_olcum as so
from research.golge_v2 import KOK, _evren_oku, kod_ozeti
from senaryo_v2.adaptor import hazirla_gunluk_baglam, seriyi_hazirla
from senaryo_v2.modeller import MAX_BEKLEME_LIMIT, TAMPON_VARSAYILAN_ATR, UFUK_VARSAYILAN_BAR, BarDurum
from senaryo_v2.olaylar import aday_olaylari_cikar
from senaryo_v2.plan import plan_karti_olustur
from senaryo_v2.surec import SurecGozcusu, SurecGozlem, SurecKarari, SurecPolitikasi, YonetimDurumu
from senaryo_v2.yaris import YarisIzi, surecli_yaris

VARSAYILAN_CIKTI = KOK / "docs/arastirma/sonuclar/golge_v2/tepki_olcum"
SUREC_OLCUM_CSV = KOK / "docs/arastirma/sonuclar/golge_v2/surec_olcum/islemler.csv.gz"
ESIKLER: dict[str, float] = kg.ESIKLER
ESIK_AD: dict[str, str] = kg.ESIK_AD
ENDEKS_ESIK: float = kg.ENDEKS_ESIK
MIN_N: int = so.MIN_N

# Tetikler: `kar_gorup_donen` tablosunun satırları (sıra sabit). İlki karşılaştırma tabanıdır.
TETIKLER: dict[str, str] = {
    "HER_ISLEM": "Koşulsuz: eşik görüldüğü kapanışta (karşılaştırma tabanı)",
    "ENGEL": "Mum bilinen bir karşı engele değdi, kapanışla aşamadı",
    "STABIL": "… karşı Stabil seviyesi",
    "MS": "… karşı Market Structure seviyesi",
    "BLOK": "… karşı OB / FVG bandı",
    "SEVIYE_ICI": "Kapanış tez seviyesinin ters tarafında",
    "FRM": "Formasyon bozuldu (retest ediliyor / teyitsiz / başarısız / karşı kırılım)",
    "MS_SUPURME": "Market Structure ters süpürme / sahte kırılım",
    "VP_TERS": "Ters hacim baskısı",
    "ENDEKS": f"Girişten bu kapanışa endeks işlemin tersine en az %{ENDEKS_ESIK:g}",
    "HERHANGI": "Domain gözlemlerinden herhangi biri (engel, tez seviyesi, formasyon, süpürme, hacim)",
    "IKI_FARKLI": "Eşikten beri iki farklı tür domain gözlemi birikti",
}
# "Herhangi biri" ve "iki farklı tür" sayımına giren domain gözlem türleri (endeks bir domain değildir).
DOMAIN_TURLERI: tuple[str, ...] = ("ENGEL", "SEVIYE_ICI", "FRM", "MS_SUPURME", "VP_TERS")
# Tepki -> (açıklama, motorun çıkış uygulaması).
TEPKILER: dict[str, tuple[str, str]] = {
    "cik": ("Sonraki açılışta çık", "sonraki_acilis"),
    "basabas": ("Stopu girişe çek", "kapanis"),
}
# Varyant adı -> (eşik, tetik, tepki).
VARYANTLAR: dict[str, tuple[str, str, str]] = {
    f"{esik}_{tetik.lower()}_{tepki}": (esik, tetik, tepki) for esik in ESIKLER for tepki in TEPKILER for tetik in TETIKLER
}
BAZ_SONUCLARI: tuple[tuple[str, str], ...] = (("STOP", "Stop olacaklarda"), ("HEDEF", "Hedefe gideceklerde"), ("DIGER", "Süre sonu / diğer"))


# ---------------------------------------------------------------------------
# Tetikler (saf)
# ---------------------------------------------------------------------------
def bar_tetikleri(
    onceki: BarDurum, b: BarDurum, olaylar: Iterable[str], *, d: int, atr: float, endeks_yuzde: float | None
) -> frozenset[str]:
    """Bir mumun kapanışında yanan tetikler (o kapanışa kadar bilinenlerle).

    Engel okuması `kar_gorup_donen` ile aynıdır: seviyeler ÖNCEKİ kapanışta bilinenlerdir.
    `olaylar`, gözcünün o mumda ürettiği süreç etiketleridir. `endeks_yuzde`, girişten bu
    kapanışa endeksin işlem yönüne göre yüzde değişimidir (bilinmiyorsa `None`).
    """
    durum = kg.mum_engel_durumu(onceki, b, d, atr)
    yanan = {ad for ad, alan in (("STABIL", "stabil"), ("MS", "ms"), ("BLOK", "blok")) if durum[alan] == "RED"}
    if yanan:
        yanan.add("ENGEL")
    etiketler = set(olaylar)
    if "SEVIYE_ICI" in etiketler:
        yanan.add("SEVIYE_ICI")
    if etiketler & kg.FRM_BOZULMA:
        yanan.add("FRM")
    if kg.ters_supurme(b, d):
        yanan.add("MS_SUPURME")
    if "VP_TERS_BASKI" in etiketler:
        yanan.add("VP_TERS")
    if yanan.intersection(DOMAIN_TURLERI):
        yanan.add("HERHANGI")
    if endeks_yuzde is not None and endeks_yuzde <= -ENDEKS_ESIK:
        yanan.add("ENDEKS")
    return frozenset(yanan)


def tetik_izi(kapanislar: Sequence[tuple[int, float, frozenset[str]]]) -> dict[str, dict[str, int | None]]:
    """Her eşik için eşiğin ve her tetiğin ilk görüldüğü kapanış.

    `kapanislar`: işlemin sağ ulaştığı kapanışlar, sırayla — (k, o kapanışa kadar görülen en iyi
    nokta ATR, o mumda yanan tetikler). Tetik yalnız eşik görüldükten sonra (aynı kapanış dahil)
    sayılır; `IKI_FARKLI` eşikten beri biriken farklı domain türü sayısı 2'ye ulaştığında yanar.
    Dönen: `{eşik adı: {"ESIK": k | None, tetik adı: k | None}}`.
    """
    iz: dict[str, dict[str, int | None]] = {}
    for ad, esik in ESIKLER.items():
        ilk: dict[str, int | None] = dict.fromkeys(TETIKLER)
        birikim: set[str] = set()
        for k, en_iyi_atr, yanan in kapanislar:
            if en_iyi_atr < esik:
                continue
            birikim |= yanan.intersection(DOMAIN_TURLERI)
            aktif = set(yanan) | {"HER_ISLEM"}
            if len(birikim) >= 2:
                aktif.add("IKI_FARKLI")
            for tetik in aktif:
                if tetik in ilk and ilk[tetik] is None:
                    ilk[tetik] = k
        iz[ad] = {"ESIK": ilk["HER_ISLEM"], **ilk}
    return iz


@dataclass(frozen=True, slots=True)
class KapanistaTepki(SurecPolitikasi):
    """Dolumdan sonraki `k`. kapanışta bir kez tepki verir: çık ya da stopu girişe çek."""

    k: int
    tepki: str
    ad: str = "kapanista_tepki"

    def __post_init__(self) -> None:
        if self.tepki not in TEPKILER:
            raise ValueError(f"Bilinmeyen tepki: {self.tepki}")

    def kapanista(self, g: SurecGozlem, d: YonetimDurumu) -> SurecKarari | None:
        if g.k != self.k:
            return None
        if self.tepki == "cik":
            return SurecKarari(cik=True, neden="TEPKI_CIK")
        return SurecKarari(yeni_stop=d.giris)


def kapanis_dizisi(
    barlar: Sequence[BarDurum],
    gozlemler: Sequence[SurecGozlem],
    *,
    dolum_idx: int,
    cikis_k: int,
    d: int,
    giris: float,
    atr: float,
    endeks: dict[str, np.ndarray] | None,
) -> list[tuple[int, float, frozenset[str]]]:
    """Baz yarışta çıkış mumundan ÖNCEKİ her kapanış için (k, en iyi nokta ATR, yanan tetikler).

    Çıkış mumunun kapanışındaki tepki hiçbir şeyi değiştirmez (süre zaten dolmuştur); bu yüzden
    ve `kar_gorup_donen` ile aynı pencereyi kullanmak için dizi çıkış mumunda kesilir.
    """

    def endeks_kapanisi(b: BarDurum) -> float | None:
        return None if endeks is None else sa._asof_kapanis(endeks, int(pd.Timestamp(b.bar_close_time).value))

    e0 = endeks_kapanisi(barlar[dolum_idx])
    dizi: list[tuple[int, float, frozenset[str]]] = []
    en_iyi = 0.0
    for sira, g in enumerate(gozlemler, start=1):
        if g.k >= cikis_k:
            break
        if g.k != sira or g.bar_index != dolum_idx + sira:
            raise ValueError("Gözlem dizisi dolumdan itibaren ardışık değil")
        b = barlar[g.bar_index]
        en_iyi = max(en_iyi, d * (float(b.high if d == 1 else b.low) - giris) / atr)
        e1 = endeks_kapanisi(b)
        endeks_yuzde = kg._yuv(d * (e1 / e0 - 1.0) * 100.0) if e0 and e1 else None
        dizi.append((g.k, en_iyi, bar_tetikleri(barlar[g.bar_index - 1], b, g.olaylar, d=d, atr=atr, endeks_yuzde=endeks_yuzde)))
    return dizi


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------
def _sembol_isle(sembol: str) -> list[dict[str, Any]]:
    """Bir sembolün işlemlerini baz ve bütün tepki varyantlarıyla yarıştırır.

    Olay seçimi, plan, hedef ve masraf `golge_v2_surec_olcum._sembol_isle` ile aynıdır; baz
    sonuçların o koşucunun çıktısıyla eşitliği `main` içinde denetlenir.
    """
    baglam = hazirla_gunluk_baglam(sembol)
    satirlar: list[dict[str, Any]] = []
    for tf in so.TFS:
        seri = seriyi_hazirla(sembol, tf, gunluk_baglam=baglam, bloklari_yukle=True)
        if seri.domain_hatali:
            continue
        barlar = seri.barlar
        olaylar = list(aday_olaylari_cikar(seri))
        bar_olaylari: dict[int, list[Any]] = defaultdict(list)
        for o in olaylar:
            bar_olaylari[o.bar_index].append(o)
        endeks = None if sembol in (sa.ENDEKS, "XU30") else sa._endeks("1d" if tf == "1d" else "1h")

        for o in olaylar:
            if not (o.sinyal_sinifi == "BIRINCIL" or o.kalite_katmani in so.A_KATMANLARI):
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
            d = 1 if o.yon == "long" else -1
            hedef = giris + d * so.HEDEF_ATR * atr
            masraf_r = so.MASRAF_ORAN * giris / max(round(risk / atr, 4) * atr, 1e-6)

            def kos(politikalar: tuple[SurecPolitikasi, ...] = (), cikis_modu: str = "kapanis") -> YarisIzi:
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
            dizi = kapanis_dizisi(barlar, baz.gozlemler, dolum_idx=i, cikis_k=baz.cozulme_offset, d=d, giris=giris, atr=atr, endeks=endeks)
            iz = tetik_izi(dizi)
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
                "baz_net": round(baz.pnl_r - masraf_r, 4),
                "baz_neden": baz.neden,
                "baz_bar": baz.cozulme_offset,
            }
            for esik in ESIKLER:
                satir[f"k_esik_{esik}"] = iz[esik]["ESIK"]
                for tetik in TETIKLER:
                    if tetik != "HER_ISLEM":
                        satir[f"tk_{esik}_{tetik}"] = iz[esik][tetik]
            yarislar: dict[tuple[int, str], YarisIzi] = {}      # aynı kapanışta aynı tepki = aynı yarış
            for ad, (esik, tetik, tepki) in VARYANTLAR.items():
                k_tetik = iz[esik][tetik]
                if k_tetik is None:
                    sonuc = baz
                else:
                    anahtar = (k_tetik, tepki)
                    if anahtar not in yarislar:
                        yarislar[anahtar] = kos((KapanistaTepki(k_tetik, tepki),), TEPKILER[tepki][1])
                    sonuc = yarislar[anahtar]
                satir[f"{ad}_net"] = round(sonuc.pnl_r - masraf_r, 4)
                satir[f"{ad}_neden"] = sonuc.neden
                satir[f"{ad}_bar"] = sonuc.cozulme_offset
            satirlar.append(satir)
    return satirlar


# ---------------------------------------------------------------------------
# Özet
# ---------------------------------------------------------------------------
def baz_sonucu(neden: pd.Series) -> pd.Series:
    """Baz çıkış nedenini üç sınıfa indirger: STOP, HEDEF, DIGER (süre sonu, tez iptali)."""
    return pd.Series(np.select([neden.isin(sa.STOP_NEDENLERI), neden == "HEDEF"], ["STOP", "HEDEF"], default="DIGER"), index=neden.index)


def tetik_kapanisi(df: pd.DataFrame, esik: str, tetik: str) -> pd.Series:
    """Tepkinin verildiği kapanış (yoksa boş)."""
    return df[f"k_esik_{esik}"] if tetik == "HER_ISLEM" else df[f"tk_{esik}_{tetik}"]


def varyant_ozeti(kume: pd.DataFrame, ad: str) -> dict[str, Any]:
    """Eşleşmiş fark (varyant − baz), kabul kararı ve farkın baz sonuca göre dökümü."""
    esik, tetik, tepki = VARYANTLAR[ad]
    fark = (kume[f"{ad}_net"] - kume["baz_net"]).astype(float)
    etkilenen = (kume[f"{ad}_neden"] != kume["baz_neden"]) | (kume[f"{ad}_bar"] != kume["baz_bar"]) | (fark.abs() > 1e-9)
    tetiklenen = tetik_kapanisi(kume, esik, tetik).notna()
    if (etkilenen & ~tetiklenen).any():
        raise ValueError(f"{ad}: tetik yanmadan sonucu değişen işlem var")
    oz = kg.cikis_karsi_olgusu(kume, etkilenen, fark)
    sonuc = baz_sonucu(kume["baz_neden"])
    dokum = {
        s: {"n": int((etkilenen & (sonuc == s)).sum()), "toplam_r": round(float(fark[etkilenen & (sonuc == s)].sum()), 2)}
        for s, _ in BAZ_SONUCLARI
    }
    return {
        "varyant": ad,
        "esik": esik,
        "tetik": tetik,
        "tepki": tepki,
        "tetiklenen_n": int(tetiklenen.sum()),
        "etkilenen_n": oz["etkilenen_n"],
        "kesif_etkilenen_n": int((etkilenen & (kume["donem"] == "kesif")).sum()),
        "dogrulama_etkilenen_n": int((etkilenen & (kume["donem"] == "dogrulama")).sum()),
        "iyilesen_n": int((fark > 1e-9).sum()),
        "kotulesen_n": int((fark < -1e-9).sum()),
        "fark_ort": oz["kume_ort"],
        "fark_toplam": oz["kume_toplam"],
        "fark_en_kotu_alt": oz["en_kotu_alt"],
        "fark_en_kotu_ust": oz["en_kotu_ust"],
        "kesif_fark": oz["kesif_ort"],
        "dogrulama_fark": oz["dogrulama_ort"],
        "dokum": dokum,
        "karar": oz["karar"],
    }


def kume_ozeti(kume: pd.DataFrame) -> dict[str, Any]:
    return {
        "n": int(len(kume)),
        "kesif_n": int((kume["donem"] == "kesif").sum()),
        "dogrulama_n": int((kume["donem"] == "dogrulama").sum()),
        "baz_net": round(float(kume["baz_net"].mean()), 6),
        "baz_sonuc": {s: int((baz_sonucu(kume["baz_neden"]) == s).sum()) for s, _ in BAZ_SONUCLARI},
        "esik_goren": {esik: int(kume[f"k_esik_{esik}"].notna().sum()) for esik in ESIKLER},
        "varyantlar": [varyant_ozeti(kume, ad) for ad in VARYANTLAR],
    }


def surec_olcum_esitligi(df: pd.DataFrame) -> dict[str, Any]:
    """Baz sonuçlar `golge_v2_surec_olcum` çıktısıyla işlem işlem aynı mı? (dosya varsa)."""
    if not SUREC_OLCUM_CSV.is_file():
        return {"durum": "surec_olcum_csv_yok"}
    diger = pd.read_csv(SUREC_OLCUM_CSV, usecols=["olay_id", "baz_net", "baz_neden", "baz_bar"]).set_index("olay_id")
    ortak = df[df["olay_id"].isin(diger.index)]
    e = diger.loc[ortak["olay_id"]]
    farkli = (
        (np.abs(ortak["baz_net"].to_numpy() - e["baz_net"].to_numpy()) > 1e-9)
        | (ortak["baz_neden"].to_numpy() != e["baz_neden"].to_numpy())
        | (ortak["baz_bar"].to_numpy() != e["baz_bar"].to_numpy())
    )
    return {
        "durum": "karsilastirildi",
        "ortak_n": int(len(ortak)),
        "yalniz_bu_olcumde": int(len(df) - len(ortak)),
        "yalniz_surec_olcumde": int(len(diger) - len(ortak)),
        "farkli_n": int(farkli.sum()),
    }


def ozet_uret(df: pd.DataFrame, *, sembol_sayisi: int) -> dict[str, Any]:
    return {
        "meta": {
            "sembol_sayisi": int(sembol_sayisi),
            "islem_n": int(len(df)),
            "motor_ozeti": kod_ozeti()[:12],
            "esikler_atr": ESIKLER,
            "tetikler": TETIKLER,
            "domain_turleri": list(DOMAIN_TURLERI),
            "tepkiler": {ad: {"aciklama": v[0], "cikis_modu": v[1]} for ad, v in TEPKILER.items()},
            "varyant_n": len(VARYANTLAR),
            "min_n": MIN_N,
            "baz_esitligi": so._baz_esitligi(df),
            "surec_olcum_esitligi": surec_olcum_esitligi(df),
        },
        "kumeler": {ad: kume_ozeti(df[maske(df)]) for ad, maske in so.KUMELER.items() if maske(df).any()},
    }


# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------
_f, _yz = sa._f, sa._yz
GECEN: tuple[str, ...] = ("GECTI", "UMUT_VAR")


def _dokum(v: dict[str, Any], sonuc: str) -> str:
    x = v["dokum"][sonuc]
    return f"{x['n']}: {_f(x['toplam_r'], 1)} R" if x["n"] else "—"


def _varyant_md(satirlar: list[dict[str, Any]]) -> list[str]:
    s = [
        "| Tetik | Tetiklenen | Sonucu değişen | İyileşen / kötüleşen | "
        + " | ".join(f"{acik} (n: toplam)" for _, acik in BAZ_SONUCLARI)
        + " | Fark R/işlem | En kötü GA | Keşif (etk.) / doğrulama (etk.) | Toplam R | Karar |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|",
    ]
    for v in satirlar:
        s.append(
            f"| {TETIKLER[v['tetik']]} | {v['tetiklenen_n']} | {v['etkilenen_n']} | {v['iyilesen_n']} / {v['kotulesen_n']} | "
            + " | ".join(_dokum(v, x) for x, _ in BAZ_SONUCLARI)
            + f" | {_f(v['fark_ort'], 4)} | [{_f(v['fark_en_kotu_alt'], 4)}, {_f(v['fark_en_kotu_ust'], 4)}] | "
            f"{_f(v['kesif_fark'], 4)} ({v['kesif_etkilenen_n']}) / {_f(v['dogrulama_fark'], 4)} ({v['dogrulama_etkilenen_n']}) | "
            f"{_f(v['fark_toplam'], 1)} | **{v['karar']}** |"
        )
    return s


def _sec(kume: dict[str, Any], esik: str, tepki: str) -> list[dict[str, Any]]:
    return [v for v in kume["varyantlar"] if v["esik"] == esik and v["tepki"] == tepki]


def _karar_sayimi(varyantlar: list[dict[str, Any]]) -> str:
    sayim: dict[str, int] = {}
    for v in varyantlar:
        sayim[v["karar"]] = sayim.get(v["karar"], 0) + 1
    return ", ".join(f"{k} {n}" for k, n in sorted(sayim.items()))


def _iki_donemde_arti(v: dict[str, Any]) -> bool:
    return (v["kesif_fark"] or 0) > 0 and (v["dogrulama_fark"] or 0) > 0


def _kisa_ozet_md(ozet: dict[str, Any]) -> list[str]:
    ilk_ad = next(iter(ozet["kumeler"]))
    ilk = ozet["kumeler"][ilk_ad]
    kisa = sa.KUME_KISA[ilk_ad]
    s = [
        f"- **Baz sistem tepki vermiyor; yalnız kaydediyor.** {kisa}: `{ilk['n']}` işlem; baz sonuç stop `{ilk['baz_sonuc']['STOP']}`, "
        f"hedef `{ilk['baz_sonuc']['HEDEF']}`, süre sonu / diğer `{ilk['baz_sonuc']['DIGER']}`. Çıkıştan önce 0.5 ATR gören "
        f"`{ilk['esik_goren']['yarim']}`, 1 ATR gören `{ilk['esik_goren']['bir']}` işlem.",
        "- **Kabul merdivenini geçen varyant** (`"
        + f"{ozet['meta']['varyant_n']}` varyant; `GECTI` ya da `UMUT_VAR`): "
        + "; ".join(
            f"{sa.KUME_KISA[k]} `{sum(v['karar'] in GECEN for v in veri['varyantlar'])}` ({_karar_sayimi(veri['varyantlar'])})"
            for k, veri in ozet["kumeler"].items()
        )
        + ".",
    ]
    for esik in ESIKLER:
        for tepki, (acik, _) in TEPKILER.items():
            satirlar = _sec(ilk, esik, tepki)
            taban = satirlar[0]
            diger = sorted(satirlar[1:], key=lambda v: v["fark_ort"], reverse=True)
            s.append(
                f"- **{kisa}, {ESIK_AD[esik]} sonrası, tepki \"{acik.lower()}\":** koşulsuz `{_f(taban['fark_ort'], 4)} R/işlem` ({taban['karar']}). "
                f"Tetikli en iyi: `{diger[0]['tetik']}` `{_f(diger[0]['fark_ort'], 4)}` ({diger[0]['karar']}); en kötü: `{diger[-1]['tetik']}` "
                f"`{_f(diger[-1]['fark_ort'], 4)}` ({diger[-1]['karar']}). Fark iki dönemde de artı olan tetik: "
                + (", ".join(f"`{v['tetik']}`" for v in satirlar[1:] if _iki_donemde_arti(v)) or "yok")
                + "."
            )
    ornek = {v["tetik"]: v for v in _sec(ilk, "yarim", "cik")}
    s.append(
        f"- **Neden tutmuyor ({kisa}, 0.5 ATR sonrası, sonraki açılışta çık):** "
        + "; ".join(
            f"`{t}` tetiği stop olacak `{ornek[t]['dokum']['STOP']['n']}` işlemde `{_f(ornek[t]['dokum']['STOP']['toplam_r'], 1)} R` kazandırıyor, "
            f"hedefe gidecek `{ornek[t]['dokum']['HEDEF']['n']}` işlemde `{_f(ornek[t]['dokum']['HEDEF']['toplam_r'], 1)} R` kaybettiriyor"
            for t in ("ENGEL", "SEVIYE_ICI")
        )
        + ". Bir tetik ancak hedefe gidecek işlemlerde nadiren yanıyorsa işe yarar."
    )
    hepsinde = [
        ad
        for ad in VARYANTLAR
        if VARYANTLAR[ad][1] != "HER_ISLEM"
        and all(_iki_donemde_arti(next(x for x in veri["varyantlar"] if x["varyant"] == ad)) for veri in ozet["kumeler"].values())
    ]
    s.append(
        f"- **Bütün kümelerde ({', '.join(sa.KUME_KISA[k] for k in ozet['kumeler'])}) iki dönemde de artı olan varyant:** "
        + (", ".join(f"`{ad}`" for ad in hepsinde) or "yok")
        + ". Kümeler iç içe olduğu için bu, bağımsız üç doğrulama değildir."
    )
    return s


def _kumeler_arasi_md(ozet: dict[str, Any]) -> list[str]:
    kumeler = list(ozet["kumeler"])
    s = [
        "| Eşik | Tepki | Tetik | " + " | ".join(f"{sa.KUME_KISA[k]} fark (karar)" for k in kumeler) + " |",
        "|---|---|---|" + "---:|" * len(kumeler),
    ]
    for ad, (esik, tetik, tepki) in VARYANTLAR.items():
        hucreler = []
        for k in kumeler:
            v = next(x for x in ozet["kumeler"][k]["varyantlar"] if x["varyant"] == ad)
            hucreler.append(f"{_f(v['fark_ort'], 4)} ({v['karar']})")
        s.append(f"| {ESIK_AD[esik]} | {TEPKILER[tepki][0]} | {tetik} | " + " | ".join(hucreler) + " |")
    return s


def _markdown(ozet: dict[str, Any]) -> str:
    m = ozet["meta"]
    be, se = m["baz_esitligi"], m["surec_olcum_esitligi"]
    s: list[str] = [
        "# Gölge v2 — Tepki Ölçümü: Kâr Gördükten Sonra Aleyhte Gözleme Tepki Verilseydi",
        "",
        "> Üretici: `python -m research.golge_v2_tepki_olcum`. Bu dosya elle düzenlenmez.",
        "",
        f"- Evren: `{m['sembol_sayisi']}` sembol, `4h + 1d`, Mod 0, `{so.HEDEF_ATR:g} ATR` hedef, `{UFUK_VARSAYILAN_BAR}` mum ufuk, `30 bps` masraf. "
        f"İşlem: `{m['islem_n']}`; motor kod özeti `{m['motor_ozeti']}`.",
        f"- Baz eşitliği: ana rapordaki `net15_20_r` ile {so._baz_esitligi_metni(be)} "
        + (
            f"`surec_olcum` çıktısıyla `{se['ortak_n']}` ortak işlemde sonucu (net, çıkış nedeni, çıkış mumu) farklı olan `{se['farkli_n']}`; "
            f"yalnız birinde bulunan `{se['yalniz_bu_olcumde'] + se['yalniz_surec_olcumde']}`."
            if se.get("durum") == "karsilastirildi"
            else "`surec_olcum` çıktısı bulunamadı; karşılaştırılmadı."
        ),
        "",
        "**Soru.** `kar_gorup_donen` raporu, kâr görüp stop olan işlemlerde tepe ile stop arasında bilinen engele takılma, tez seviyesinin içine "
        "kapanış, formasyon bozulması, Market Structure ters süpürmesi ve ters hacim görüldüğünü sayar. Baz sistem bu gözlemleri kaydeder ama "
        "işlem açıkken stop, hedef, süre ve ilk mumlardaki ters yapı kırılımında tez iptali dışında bir şey yapmaz. "
        "Burada ölçülen: tepki verseydi ne olurdu?",
        "",
        "**Yöntem.** Eşleşmiş replay: aynı işlemler, aynı giriş, aynı ilk stop, aynı hedef, aynı masraf, aynı motor. İşlem çıkışa kadar en az "
        "0.5 ATR (ya da 1 ATR) gördükten sonra — aynı kapanış dahil — tetik ilk kez yandığında tek bir tepki verilir. `Sonraki açılışta çık`: "
        "karar mumun kapanışında, çıkış bir sonraki mumun açılışında. `Stopu girişe çek`: stop bir sonraki mumdan itibaren giriş fiyatındadır; "
        "fiyat o an girişin zarar tarafındaysa işlem sonraki açılışta kapanır. Tetikler `kar_gorup_donen` ile aynı tanımları kullanır; engel "
        "seviyeleri her zaman önceki kapanışta bilinenlerdir.",
        "",
        "**Okuma kılavuzu.** `Tetiklenen`: tepkinin verildiği işlem. `Sonucu değişen`: baza göre net R'si, çıkış nedeni ya da çıkış mumu değişen "
        "işlem (stopu girişe çekmek, fiyat girişe dönmezse hiçbir şeyi değiştirmez). `Stop olacaklarda / Hedefe gideceklerde / Süre sonu`: sonucu "
        "değişen işlemlerin BAZ sonucuna göre sayısı ve tepkinin o gruptaki toplam etkisi (R); artı = tepki kazandırdı. `Fark R/işlem`: kümedeki "
        "bütün işlemler üzerinden işlem başına net R farkı (sonucu değişmeyenlerde 0). `En kötü GA`: sembol / gün / hafta / ay kümeli %95 "
        "aralıkların en düşük alt ve en yüksek üst sınırı.",
        "",
        "**Kabul kuralı** (`surec_olcum` ile aynı merdiven). `GECTI`: fark keşif ve doğrulamada pozitif, iki dönemde de sonucu değişen işlem ≥ "
        f"{m['min_n']} ve iki dönemde de en kötü alt sınır sıfırın üstünde. `UMUT_VAR`: aynı, ama alt sınır yalnız havuzda sıfırın üstünde. "
        "`ZAYIF_ARTI`: iki dönemde de pozitif ama aralık sıfırı içeriyor ya da bir dönemde sonucu değişen işlem < 30. `GECMEDI`: en az bir "
        "dönemde fark pozitif değil. `ZARARLI`: havuzda en kötü üst sınır bile negatif. `SAYILMAZ_N<30`: sonucu değişen işlem 30'dan az.",
        "",
        "**Bu ölçüm ön-kayıtlı değildir.** Tetik listesi `kar_gorup_donen` tablosu görüldükten sonra, o tablonun satırlarından yazıldı. "
        f"`{len(ESIKLER)}` eşik × `{len(TETIKLER)}` tetik × `{len(TEPKILER)}` tepki = `{m['varyant_n']}` varyant, `{len(ozet['kumeler'])}` küme; "
        "çoklu karşılaştırma düzeltmesi yok. Geçen bir varyant bile kural değil, ileriye dönük gölge defterde izlenecek adaydır.",
        "",
        "## Kısa özet",
        "",
    ]
    s += _kisa_ozet_md(ozet)
    s += ["", "## Kümeler yan yana", "", "Üç küme iç içedir (D7 ⊂ D6 ⊂ D1); aynı yönde çıkmaları üç bağımsız doğrulama değildir.", ""]
    s += _kumeler_arasi_md(ozet)
    for kume, veri in ozet["kumeler"].items():
        s += [
            "",
            f"## {kume} — {veri['n']} işlem",
            "",
            f"Keşif `{veri['kesif_n']}`, doğrulama `{veri['dogrulama_n']}`; baz net `{_f(veri['baz_net'])} R`. Baz sonuç: stop `{veri['baz_sonuc']['STOP']}`, "
            f"hedef `{veri['baz_sonuc']['HEDEF']}`, süre sonu / diğer `{veri['baz_sonuc']['DIGER']}`.",
        ]
        for esik in ESIKLER:
            for tepki, (acik, _) in TEPKILER.items():
                s += [
                    "",
                    f"### {ESIK_AD[esik]} gördükten sonra — tepki: {acik.lower()}",
                    "",
                    f"Çıkıştan önce {ESIK_AD[esik]} gören işlem: `{veri['esik_goren'][esik]}`.",
                    "",
                ] + _varyant_md(_sec(veri, esik, tepki))
    s += [
        "",
        "## Sınırlar",
        "",
        "- Ön-kayıtlı değildir ve çok sayıda varyant sınar; tek tek satırlar değil, keşif / doğrulama tutarlılığı ve kümeler arası tekrar okunmalıdır.",
        "- Mum çözünürlüğündedir: stop ile hedef aynı mumda ise stop sayılır; girişe çekilen stop için de aynı kural geçerlidir (muhafazakâr).",
        "- İki tepki ölçüldü: tam çıkış ve stopu girişe çekme. Sabit oranlı kısmi çıkış ayrı bir ölçüm gerektirmez: masraf pozisyonla orantılı "
        "olduğundan pozisyonun bir kısmına uygulanan tepkinin farkı ve güven aralığı tam tepkininkinin aynı oranıdır; eksi olan artıya dönmez. "
        "Stopu tetik mumunun ötesine taşıma ve yeniden giriş ölçülmedi.",
        "- Tetikler `kar_gorup_donen` raporunun \"tepeden stopa\" tablosundaki satırları kapsar ama aynı pencereyi kullanmaz: o tablo tepe mumundan "
        "(ancak işlem bittikten sonra bilinir) sayar, tetik eşiğin görüldüğü kapanıştan. O tabloda sayılan her işlemde aynı gözlem tetik olarak da yanar; "
        "tetik ayrıca tepe mumu dışındaki mumlarda ve stop olmayan işlemlerde de yanar. Tek fark hacim satırındadır: tablo tepe mumundaki "
        "\"yüksek çaba – zayıf sonuç\" gözlemini de sayar; tetik yalnız ters hacim baskısı etiketidir.",
        "- Tepki işlemin kendi zaman dilimindeki mum kapanışında verilir; mum içi tepki ölçülmedi.",
        "- Endeks tetiği, endeks sembollerinin kendi işlemlerinde tanımsızdır (yanmaz).",
        "- Kâr görme şartı OLMADAN aynı süreç etiketlerinde çıkış ve kâr koruma (stopu kâra kilitleme, hedefte iz sürme) `surec_olcum` raporundadır.",
    ]
    return "\n".join(s) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gölge v2 tepki ölçümü: kâr gördükten sonra aleyhte gözleme tepki")
    ap.add_argument("--evren", choices=("evren176", "hisse174"), default="evren176")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--cikti", type=Path, default=VARSAYILAN_CIKTI)
    args = ap.parse_args(argv)

    semboller = _evren_oku(args.evren, args.limit)
    sonuc_by_sembol: dict[str, list[dict[str, Any]]] = {}
    if args.workers <= 1:
        for sym in semboller:
            sonuc_by_sembol[sym] = _sembol_isle(sym)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(_sembol_isle, sym): sym for sym in semboller}
            for i, fut in enumerate(as_completed(futs), 1):
                sonuc_by_sembol[futs[fut]] = fut.result()
                if i % 20 == 0 or i == len(semboller):
                    print(f"[{i}/{len(semboller)}] {futs[fut]}", flush=True)
    satirlar = [r for sym in semboller for r in sonuc_by_sembol[sym]]  # evren sırası: deterministik
    df = pd.DataFrame(satirlar)
    if df.empty:
        print("Ölçülecek işlem yok.", flush=True)
        return 1
    ozet = ozet_uret(df, sembol_sayisi=len(semboller))
    args.cikti.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.cikti / "islemler.csv.gz", index=False, compression="gzip")
    (args.cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.cikti / "RAPOR.md").write_text(_markdown(ozet), encoding="utf-8")
    ilk_ad = next(iter(ozet["kumeler"]))
    gecen = sum(v["karar"] in GECEN for v in ozet["kumeler"][ilk_ad]["varyantlar"])
    print(f"Tamamlandi -> {args.cikti} | islem={len(df)} | {ilk_ad}: {len(VARYANTLAR)} varyanttan gecen={gecen}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
