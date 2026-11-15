"""Gölge v2 sonuç anatomisi — kaç işlem kazandı, kaç işlem kaybetti, kaybedenler NASIL kaybetti.

Ana rapor "ortalama kaç R" sorusunu yanıtlar. Bu betik aynı işlemleri tek tek açar:

* Kaç işlem kâr, kaç işlem zarar; nasıl kapandılar (hedef / stop / boşluklu stop / süre doldu).
* Zarar eden her işleme TEK bir kayıp yolu atanır; paylar %100'e toplanır.
* Stop olanlar stoptan önce ne kadar kâr gördü; kaçı girişten sonraki ilk mumda stop oldu.
* Stop olduktan sonra fiyat ne yaptı (stop haklı mıydı)?
* Stop olmadan kapananlar; zora girip kurtaranlar; kazananların yolu.
* Zarar hangi giriş koşullarında yoğunlaşıyor (stop mesafesi, yön, saat, piyasa, kalabalık).

Yarış yeniden KOŞULMAZ. İşlem sonuçları ana CSV'den (`mod0_baz.csv.gz`) okunur; fiyat arşivi
yalnız yolu çözmek için açılır. Her işlemde arşivden yürütülen yol, CSV'deki çıkış nedeni,
çıkış mumu ve MFE ile karşılaştırılır; stop sonrası alanlar da CSV'nin ufuk kapanışı ve saf
yol MFE'siyle sınanır. Tek bir uyuşmazlıkta betik durur. Yani buradaki sayılar ana rapordaki
işlemlerin kendisidir, benzeri değil.

İki çözünürlük kullanılır:

* **Mum** (işlemin kendi zaman dilimi; her işlemde var): stop mumunun içindeki sıra bilinmez,
  bu yüzden "stoptan önce görülen kâr" stop mumunu SAYMAZ (alt sınırdır).
* **Saat** (1s arşivi; 4s mumlar 1s'ten türediği için 4s işlemlerde birebir, günlükte
  yaklaşık): stop mumunun içi saat saat açılır. Günlük ile saatlik arşiv uyuşmuyorsa işlem
  saatlik tablolara alınmaz ve sayısı raporda yazılır.

Bu rapor BETİMLEYİCİDİR. "Stopların %X'i önce kâr gördü" bir kural değeri değildir; kural
değerini eşleşmiş replay ölçer (`research/golge_v2_surec_olcum.py`). Giriş koşulu tabloları
ilişki gösterir, neden kanıtlamaz; çok sayıda kesit olduğu için tek tek anlamlılık iddiası yok.

Kullanım::

    python -m research.golge_v2_sonuc_anatomisi [--girdi D] [--cikti D] [--workers 2]
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import functools
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from domain_engines.stabil import prepare_causal_ohlcv
from research.arsiv import tf_frame
from research.golge_v2 import KOK
from senaryo_v2.rapor import surec_izini_coz, zaman_kumesi_saglamligi

VARSAYILAN_GIRDI = KOK / "docs/arastirma/sonuclar/golge_v2"
TFS: tuple[str, ...] = ("4h", "1d")
HEDEF_ATR: float = 2.0
ENDEKS: str = "XU100"
A_KATMANLARI = ("A_ARTI", "A_CEKIRDEK")
KUMELER: dict[str, Any] = {
    "D7_A_Arti": lambda df: df["kalite_katmani"] == "A_ARTI",
    "D6_A_Cekirdek_Veya_Arti": lambda df: df["kalite_katmani"].isin(A_KATMANLARI),
    "D1_Birincil": lambda df: df["sinyal_sinifi"] == "BIRINCIL",
}
KUME_KISA = {"D7_A_Arti": "D7", "D6_A_Cekirdek_Veya_Arti": "D6", "D1_Birincil": "D1"}

# Çıkış türleri (ana CSV'deki `neden_20_intra_iptal` değerlerinden).
STOP_NEDENLERI = frozenset({"STOP", "STOP_GAP"})
# Stoptan önce görülen en iyi R'ye göre yol kovaları (alt sınır dahil).
ESIK_AZ_KAR: float = 0.25
ESIK_KAR: float = 0.5
ESIK_BIR_R: float = 1.0

# Zarar eden işlemin TEK kayıp yolu. Sıra önceliktir: ilk uyan atanır.
ZARAR_YOLLARI: tuple[tuple[str, str], ...] = (
    ("SURE_ZARAR", "Stop olmadı; süre doldu, zararda kapandı"),
    ("TEZ_IPTAL", "Stop olmadı; tez iptaliyle zararda kapandı"),
    ("BOSLUK", "Açılış boşluğu stopu atladı"),
    ("ILK_MUM", "Girişten sonraki ilk mumda stop"),
    ("KAR_GORMEDI", f"2+ mum yaşadı, +{ESIK_AZ_KAR:g} R'yi hiç görmedi"),
    ("AZ_KAR", f"+{ESIK_AZ_KAR:g}–{ESIK_KAR:g} R gördü, döndü"),
    ("KAR_GORDU", f"+{ESIK_KAR:g}–{ESIK_BIR_R:g} R gördü, geri verdi"),
    ("BIR_R_GORDU", f"+{ESIK_BIR_R:g} R ve üstünü gördü, geri verdi"),
)
ZARAR_YOLU_ADI = dict(ZARAR_YOLLARI)

# Stop olduktan sonra, işlemin özgün ufku bitene kadar fiyat ne yaptı?
STOP_SONRASI: tuple[tuple[str, str], ...] = (
    ("HEDEFE_GITTI", "Stoptan sonra özgün hedefe ulaştı"),
    ("KARDA_BITTI", "Hedefe ulaşmadı ama ufuk sonunda girişin kâr tarafında"),
    ("ZARARDA_BITTI", "Ufuk sonunda giriş ile stop arasında"),
    ("DAHA_KOTU", "Ufuk sonunda stopun da ötesinde"),
    ("UFUK_SONU", "Stop ufkun son mumunda; sonrası yok"),
)
STOP_SONRASI_ADI = dict(STOP_SONRASI)


# ---------------------------------------------------------------------------
# Yol yürüyücü (saf fonksiyon; hem işlem mumlarında hem saatlik mumlarda kullanılır)
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Yol:
    """Bir mum dizisinde stop/hedef yarışının sonucu ve çıkışa kadarki yol."""

    neden: str                 # STOP_GAP | STOP | HEDEF | ZAMAN_STOPU
    cikis_k: int               # çıkış mumunun 1'den başlayan sırası (ZAMAN_STOPU: son mum)
    cikis_fiyat: float
    mfe_r: float               # ÇIKIŞA KADAR en iyi R: stopta çıkış mumu sayılmaz, hedefte hedefin R'si
    mfe_k: int | None          # en iyi R'nin ilk görüldüğü mum sırası
    mae_r: float               # çıkışa kadar en kötü R (pozitif büyüklük); stopta çıkış fiyatı dahil
    cikis_mumu_lehte_r: float  # çıkış mumunun lehte ucu (R); mum içi sıra bilinmez
    ayni_mumda_hedef: bool     # stop çıkışında aynı mum hedefi de gördü (sıra bilinmediği için stop sayıldı)


def yolu_yuru(
    mumlar: Sequence[tuple[float, float, float, float]],
    *,
    yon: int,
    giris: float,
    stop: float,
    hedef: float,
) -> Yol:
    """Mumları (açılış, yüksek, düşük, kapanış) sırayla yürür.

    Motorla aynı sıra (`senaryo_v2/yaris.py::surecli_yaris`): açılış boşluğu stopu → stop →
    hedef; stop ile hedef aynı mumda ise sıra bilinmediğinden stop kazanır. Hiçbiri olmazsa
    son mumun kapanışında `ZAMAN_STOPU`.
    """
    if yon not in (1, -1):
        raise ValueError("yon +1 ya da -1 olmalı")
    if not mumlar:
        raise ValueError("mum dizisi boş")
    risk = abs(giris - stop)
    if risk <= 0 or yon * (giris - stop) <= 0 or yon * (hedef - giris) <= 0:
        raise ValueError("giriş / stop / hedef sırası geçersiz")

    def r(fiyat: float) -> float:
        return yon * (fiyat - giris) / risk

    mfe, mfe_k, mae = 0.0, None, 0.0
    for k, (acilis, yuksek, dusuk, _kapanis) in enumerate(mumlar, start=1):
        lehte = yuksek if yon == 1 else dusuk
        aleyhte = dusuk if yon == 1 else yuksek
        cikis: float | None = None
        neden = ""
        if yon * (acilis - stop) <= 0:
            cikis, neden = acilis, "STOP_GAP"
        elif yon * (aleyhte - stop) <= 0:
            cikis, neden = stop, "STOP"
        elif yon * (lehte - hedef) >= 0:
            cikis, neden = hedef, "HEDEF"
        if cikis is not None:
            # Çıkış mumunun geri kalanı bilinmez: MFE/MAE'ye yalnız çıkış fiyatı işlenir.
            if r(cikis) > mfe:
                mfe, mfe_k = r(cikis), k
            mae = max(mae, -r(cikis))
            return Yol(
                neden=neden,
                cikis_k=k,
                cikis_fiyat=float(cikis),
                mfe_r=mfe,
                mfe_k=mfe_k,
                mae_r=mae,
                cikis_mumu_lehte_r=r(lehte),
                ayni_mumda_hedef=bool(neden != "HEDEF" and yon * (lehte - hedef) >= 0),
            )
        if r(lehte) > mfe:
            mfe, mfe_k = r(lehte), k
        mae = max(mae, -r(aleyhte))
    son = mumlar[-1]
    return Yol("ZAMAN_STOPU", len(mumlar), float(son[3]), mfe, mfe_k, mae, r(son[1] if yon == 1 else son[2]), False)


# ---------------------------------------------------------------------------
# Sınıflandırıcılar (saf)
# ---------------------------------------------------------------------------
def cikis_turu(neden: str) -> str:
    """Ana CSV çıkış nedenini dört okunur türe indirger."""
    if neden == "HEDEF":
        return "HEDEF"
    if neden == "STOP":
        return "STOP"
    if neden == "STOP_GAP":
        return "STOP_BOSLUK"
    if neden == "ZAMAN_STOPU":
        return "SURE"
    if neden.startswith("TEZ_IPTAL"):
        return "TEZ_IPTAL"
    raise ValueError(f"Beklenmeyen çıkış nedeni: {neden}")


def stop_yolu(mfe_r: float, cikis_k: int) -> str:
    """Stop olan işlemin stoptan ÖNCEKİ yolu (boşluk ayrımı yapmaz)."""
    if cikis_k <= 1:
        return "ILK_MUM"
    if mfe_r >= ESIK_BIR_R:
        return "BIR_R_GORDU"
    if mfe_r >= ESIK_KAR:
        return "KAR_GORDU"
    if mfe_r >= ESIK_AZ_KAR:
        return "AZ_KAR"
    return "KAR_GORMEDI"


def zarar_yolu(*, net_r: float, neden: str, mfe_r: float, cikis_k: int) -> str:
    """Zarar eden işlemin tek kayıp yolu; kâr eden işlemde boş metin."""
    if not net_r < 0:
        return ""
    tur = cikis_turu(neden)
    if tur == "SURE":
        return "SURE_ZARAR"
    if tur == "TEZ_IPTAL":
        return "TEZ_IPTAL"
    if tur == "HEDEF":
        raise ValueError("Hedefe ulaşan işlem net zararda olamaz")
    if tur == "STOP_BOSLUK":
        return "BOSLUK"
    return stop_yolu(mfe_r, cikis_k)


def stop_sonrasi(*, cikis_k: int, ufuk: int, sonra_hedef: bool, ufuk_kapanis_r: float) -> str:
    """Stoptan sonra, özgün ufuk bitene kadar fiyatın yaptığı."""
    if cikis_k >= ufuk:
        return "UFUK_SONU"
    if sonra_hedef:
        return "HEDEFE_GITTI"
    if ufuk_kapanis_r > 0:
        return "KARDA_BITTI"
    if ufuk_kapanis_r > -1.0:
        return "ZARARDA_BITTI"
    return "DAHA_KOTU"


# ---------------------------------------------------------------------------
# Arşiv
# ---------------------------------------------------------------------------
def _cerceve(sembol: str, tf: str) -> dict[str, np.ndarray]:
    """Motorun gördüğü temiz seri: OHLC + mum başlangıç / kapanış zamanı (UTC ns)."""
    ham = tf_frame(sembol, tf)
    temiz, hata = prepare_causal_ohlcv(ham, symbol=sembol, timeframe=tf)
    if hata and temiz.empty:
        raise ValueError(f"{sembol}/{tf} çerçeve hazırlanamadı: {hata}")
    if len(ham) != len(temiz):
        raise ValueError(f"{sembol}/{tf}: ham ve temiz seri satırları hizalı değil")
    return {
        "bas": pd.DatetimeIndex(ham.index).asi8.copy(),
        "kap": pd.DatetimeIndex(temiz["timestamp"]).asi8.copy(),
        "o": temiz["open"].to_numpy(dtype=float),
        "h": temiz["high"].to_numpy(dtype=float),
        "l": temiz["low"].to_numpy(dtype=float),
        "c": temiz["close"].to_numpy(dtype=float),
    }


@functools.lru_cache(maxsize=4)
def _endeks(tf: str) -> dict[str, np.ndarray]:
    return _cerceve(ENDEKS, tf)


def _asof_kapanis(seri: dict[str, np.ndarray], zaman_ns: int) -> float | None:
    """`zaman_ns` anında bilinen son kapanış (kapanış zamanı <= an)."""
    j = int(np.searchsorted(seri["kap"], zaman_ns, side="right")) - 1
    return float(seri["c"][j]) if j >= 0 else None


_GUN_NS: int = 86_400 * 10**9
_TR_OFSET_NS: int = 3 * 3_600 * 10**9      # Europe/Istanbul sabit +03:00


def _yerel_gun(zaman_ns: int) -> int:
    """UTC ns zamanının İstanbul takvim günü (gün sayacı)."""
    return (zaman_ns + _TR_OFSET_NS) // _GUN_NS


def _mumlar(seri: dict[str, np.ndarray], a: int, b: int) -> list[tuple[float, float, float, float]]:
    return [(float(seri["o"][j]), float(seri["h"][j]), float(seri["l"][j]), float(seri["c"][j])) for j in range(a, b)]


# ---------------------------------------------------------------------------
# Tek işlem
# ---------------------------------------------------------------------------
def islem_anatomisi(
    r: dict[str, Any],
    seri: dict[str, np.ndarray],
    saatlik: dict[str, np.ndarray] | None,
    endeks: dict[str, np.ndarray] | None,
) -> dict[str, Any]:
    """Ana CSV'deki bir işlemin yolunu arşivden çözer ve CSV ile doğrular."""
    oid = str(r["olay_id"])
    i = int(r["bar_index"])
    ufuk = int(r["ufuk_bar"])
    d = 1 if r["yon"] == "long" else -1
    giris, stop, atr = float(r["giris_gercek"]), float(r["stop"]), float(r["atr_tf"])
    risk = abs(giris - stop)
    hedef = giris + d * HEDEF_ATR * atr
    giris_ns = int(pd.Timestamp(r["bar_close_time"]).value)
    if i + ufuk >= len(seri["c"]) or int(seri["kap"][i]) != giris_ns or abs(float(seri["c"][i]) - giris) > 1e-7:
        raise ValueError(f"{oid}: olay barı arşivle hizalı değil")

    neden = str(r["neden_20_intra_iptal"])
    cikis_k = int(r["bar_20_intra_iptal"])
    tur = cikis_turu(neden)
    mumlar = _mumlar(seri, i + 1, i + 1 + ufuk)
    if tur == "TEZ_IPTAL":
        # Kapanışta verilen yapı kararı; fiyat yolundan türetilemez. Yol CSV çıkışına kadar okunur.
        yol = yolu_yuru(mumlar[:cikis_k], yon=d, giris=giris, stop=stop, hedef=hedef)
        if yol.neden != "ZAMAN_STOPU":
            raise ValueError(f"{oid}: tez iptalinden önce stop/hedef görünüyor")
        mfe_r, mfe_k, mae_r = yol.mfe_r, yol.mfe_k, yol.mae_r
    else:
        yol = yolu_yuru(mumlar, yon=d, giris=giris, stop=stop, hedef=hedef)
        if (yol.neden, yol.cikis_k) != (neden, cikis_k):
            raise ValueError(f"{oid}: arşiv yolu {yol.neden}@{yol.cikis_k}, CSV {neden}@{cikis_k}")
        mfe_r, mfe_k, mae_r = yol.mfe_r, yol.mfe_k, yol.mae_r
        csv_mfe = r.get("surec_mfe_r")
        if csv_mfe is not None and not pd.isna(csv_mfe) and abs(float(csv_mfe) - mfe_r) > 2e-4:
            raise ValueError(f"{oid}: MFE arşivde {mfe_r:.4f}, CSV'de {float(csv_mfe):.4f}")

    def rr(fiyat: float) -> float:
        return d * (fiyat - giris) / risk

    j = i + cikis_k                      # çıkış mumunun seri indeksi
    net_r = float(r["net15_20_r"])
    brut_r = float(r["pnl_20_intra_iptal_r"])
    sonuc: dict[str, Any] = {
        "olay_id": oid,
        "cikis_turu": tur,
        "kar": bool(net_r > 0),
        "masraf_r": round(brut_r - net_r, 4),
        "hedef_r": round(HEDEF_ATR * atr / risk, 4),
        "yol_mfe_r": round(mfe_r, 4),
        "yol_mfe_k": mfe_k,
        "yol_mae_r": round(mae_r, 4),
        "hedef_yolu_orani": round(mfe_r * risk / (HEDEF_ATR * atr), 4),
        "cikis_mumu_lehte_r": round(yol.cikis_mumu_lehte_r, 4),
        "ayni_mumda_hedef": bool(yol.ayni_mumda_hedef),
        "zarar_yolu": zarar_yolu(net_r=net_r, neden=neden, mfe_r=mfe_r, cikis_k=cikis_k),
        "giris_saati": pd.Timestamp(r["bar_close_time"]).strftime("%H:%M"),
        # Çıkış mumu işlem gününün ilk mumu mu? (gece boşluğu yalnız böyle bir mumda olur)
        "cikis_mumu_gun_ilki": bool(_yerel_gun(int(seri["bas"][j])) != _yerel_gun(int(seri["bas"][j - 1]))),
        "olay_aralik_atr": round((float(seri["h"][i]) - float(seri["l"][i])) / atr, 4),
        "on_kosu_atr": round(d * (giris - float(seri["c"][i - 5])) / atr, 4) if i >= 5 else None,
    }

    # Stop sonrası: özgün ufuk bitene kadar (stop mumundan SONRAKİ mumlar).
    ufuk_kapanis_r = rr(float(seri["c"][i + ufuk]))
    sonuc["ufuk_kapanis_r"] = round(ufuk_kapanis_r, 4)
    # Bağımsız doğrulama: ana CSV ufuk kapanışını ve 10 mumluk saf yol MFE'sini ayrıca taşır.
    csv_ufuk = r.get("kapanis_h_atr")
    if csv_ufuk is not None and not pd.isna(csv_ufuk) and abs(float(csv_ufuk) - d * (float(seri["c"][i + ufuk]) - giris) / atr) > 5e-4:
        raise ValueError(f"{oid}: ufuk kapanışı CSV ile uyuşmuyor")
    if tur in ("STOP", "STOP_BOSLUK"):
        sonraki = mumlar[cikis_k:]
        sonra_hedef = any(d * ((m[1] if d == 1 else m[2]) - hedef) >= 0 for m in sonraki)
        # Stoptan önce hedef görülmedi; yani saf yol hedefi gördüyse ya stop mumunda ya sonrasında gördü.
        csv_mfe_atr = r.get("mfe_atr")
        if csv_mfe_atr is not None and not pd.isna(csv_mfe_atr) and abs(float(csv_mfe_atr) - HEDEF_ATR) > 1e-3:
            if (float(csv_mfe_atr) > HEDEF_ATR) != (sonra_hedef or yol.ayni_mumda_hedef):
                raise ValueError(f"{oid}: stop sonrası hedef teması CSV'deki saf yol MFE'siyle uyuşmuyor")
        sonuc["stop_yolu"] = stop_yolu(mfe_r, cikis_k)
        sonuc["sonra_hedef"] = bool(sonra_hedef)
        sonuc["sonra_en_iyi_r"] = round(max((rr(m[1] if d == 1 else m[2]) for m in sonraki), default=float("nan")), 4)
        sonuc["sonra_en_kotu_r"] = round(min((rr(m[2] if d == 1 else m[1]) for m in sonraki), default=float("nan")), 4)
        sonuc["stop_sonrasi"] = stop_sonrasi(cikis_k=cikis_k, ufuk=ufuk, sonra_hedef=sonra_hedef, ufuk_kapanis_r=ufuk_kapanis_r)
        sonuc["tepe_stop_arasi"] = (cikis_k - mfe_k) if mfe_k is not None else None
        # Stop mumundan ÖNCEKİ son kapanış (ilk mumda stop olduysa giriş kapanışı): işlem neredeydi?
        onceki = float(seri["c"][j - 1])
        sonuc["stop_oncesi_kapanis_r"] = round(rr(onceki), 4)
        sonuc["stop_oncesi_mesafe_atr"] = round(d * (onceki - stop) / atr, 4)
        seviye = r.get("zemin_tavan")
        if seviye is not None and not pd.isna(seviye):
            sonuc["stop_oncesi_seviye_icinde"] = bool(d * (onceki - float(seviye)) < 0)

    # Piyasa: işlem süresince ve girişten önceki 5 mumda endeks, işlemin YÖNÜNE göre (%).
    if endeks is not None and str(r["sembol"]) not in (ENDEKS, "XU30"):
        e0 = _asof_kapanis(endeks, giris_ns)
        e1 = _asof_kapanis(endeks, int(seri["kap"][j]))
        if e0 and e1:
            sonuc["endeks_islem_yuzde"] = round(d * (e1 / e0 - 1.0) * 100.0, 4)
        if i >= 5:
            eo = _asof_kapanis(endeks, int(seri["kap"][i - 5]))
            if e0 and eo:
                sonuc["endeks_on5_yuzde"] = round(d * (e0 / eo - 1.0) * 100.0, 4)

    # Saat çözünürlüğü: çıkış mumunun içini saat saat aç. Tez iptali kapanışta verilen bir
    # yapı kararıdır; stop/hedef yarışıyla yeniden üretilemez, saatlik tabloların kapsamı dışındadır.
    sonuc["saatlik_durum"] = "KAPSAM_DISI" if tur == "TEZ_IPTAL" else "VERI_YOK"
    if saatlik is not None and tur != "TEZ_IPTAL":
        sonuc.update(_saatlik_coz(seri, saatlik, i=i, j=j, ufuk=ufuk, d=d, giris=giris, stop=stop, hedef=hedef, tur=tur, giris_ns=giris_ns))
    return sonuc


def _saatlik_coz(
    seri: dict[str, np.ndarray],
    saatlik: dict[str, np.ndarray],
    *,
    i: int,
    j: int,
    ufuk: int,
    d: int,
    giris: float,
    stop: float,
    hedef: float,
    tur: str,
    giris_ns: int,
) -> dict[str, Any]:
    """İşlemi saatlik mumlarla yeniden yürür; çıkış mumunun içindeki sırayı çözer."""
    a = int(np.searchsorted(saatlik["bas"], giris_ns, side="left"))
    b = int(np.searchsorted(saatlik["kap"], int(seri["kap"][i + ufuk]), side="right"))
    # Çıkış mumuna kadar her işlem mumunun içinde en az bir saatlik mum olmalı.
    for m in range(i + 1, j + 1):
        ma = int(np.searchsorted(saatlik["bas"], int(seri["bas"][m]), side="left"))
        mb = int(np.searchsorted(saatlik["kap"], int(seri["kap"][m]), side="right"))
        if mb <= ma:
            return {"saatlik_durum": "VERI_YOK"}
    if b <= a:
        return {"saatlik_durum": "VERI_YOK"}
    ja = int(np.searchsorted(saatlik["bas"], int(seri["bas"][j]), side="left"))
    jb = int(np.searchsorted(saatlik["kap"], int(seri["kap"][j]), side="right"))
    yol = yolu_yuru(_mumlar(saatlik, a, b), yon=d, giris=giris, stop=stop, hedef=hedef)
    idx = a + yol.cikis_k - 1
    cikis_mumunda = ja <= idx < jb
    stop_mu = tur in ("STOP", "STOP_BOSLUK")
    if tur == "SURE":
        durum = "AYNI" if yol.neden == "ZAMAN_STOPU" else "TUTARSIZ"
    elif not cikis_mumunda or yol.neden == "ZAMAN_STOPU":
        durum = "TUTARSIZ"
    elif stop_mu and yol.neden in STOP_NEDENLERI:
        durum = "AYNI"
    elif stop_mu and yol.neden == "HEDEF":
        durum = "ONCE_HEDEF"       # aynı mumda önce hedef görülmüş; mum çözünürlüğünde stop sayıldı
    elif tur == "HEDEF" and yol.neden == "HEDEF":
        durum = "AYNI"
    else:
        durum = "TUTARSIZ"
    sonuc: dict[str, Any] = {"saatlik_durum": durum}
    if durum == "AYNI" and tur != "SURE":
        risk = abs(giris - stop)
        once = _mumlar(saatlik, ja, idx)      # çıkış mumunun, çıkış saatinden ÖNCEKİ saatleri
        sonuc.update(
            {
                "saat_mfe_r": round(yol.mfe_r, 4),
                "saat_cikis_sira": int(yol.cikis_k),            # girişten sonraki kaçıncı saat
                "cikis_mumu_saat_sira": int(idx - ja + 1),      # çıkış mumunun kaçıncı saati
                "cikis_mumu_saat_n": int(jb - ja),
                "cikis_mumu_once_lehte_r": round(
                    max((d * ((m[1] if d == 1 else m[2]) - giris) / risk for m in once), default=0.0), 4
                ),
                "saat_bosluk": bool(yol.neden == "STOP_GAP"),
            }
        )
    return sonuc


def _sembol_isle(is_: tuple[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    sembol, satirlar = is_
    seriler: dict[str, dict[str, np.ndarray]] = {}
    try:
        saatlik: dict[str, np.ndarray] | None = _cerceve(sembol, "1h")
    except (FileNotFoundError, ValueError):
        saatlik = None
    sonuc: list[dict[str, Any]] = []
    for r in satirlar:
        tf = str(r["tf"])
        if tf not in seriler:
            seriler[tf] = _cerceve(sembol, tf)
        # Endeks, işlemin zaman dilimine uygun seriden okunur (günlük işlem → günlük endeks).
        endeks = _endeks("1d" if tf == "1d" else "1h")
        sonuc.append(islem_anatomisi(r, seriler[tf], saatlik, endeks))
    return sonuc


# ---------------------------------------------------------------------------
# Veri
# ---------------------------------------------------------------------------
CSV_KOLONLARI: tuple[str, ...] = (
    "olay_id", "sembol", "varlik_turu", "tf", "bar_index", "bar_close_time", "donem", "yon",
    "sinyal_sinifi", "kalite_katmani", "frm_pattern_type", "giris_gercek", "stop", "atr_tf",
    "risk_r_atr", "ufuk_bar", "zemin_tavan", "is_kisa_1800", "vp_rvol", "sansurlu", "veri_karantina",
    "pnl_20_intra_iptal_r", "net15_20_r", "neden_20_intra_iptal", "bar_20_intra_iptal",
    "mfe_atr", "kapanis_h_atr",
    "surec_gozlem_n", "surec_mfe_r", "surec_mae_r", "surec_mfe_bar", "surec_tez_son",
    "surec_tez_yolu", "surec_izi",
)


def islemleri_yukle(girdi: Path) -> pd.DataFrame:
    """Ana rapordaki `4h + 1d` birincil işlemler (sansürsüz, veri karantinası dışı)."""
    df = pd.read_csv(girdi / "mod0_baz.csv.gz", usecols=list(CSV_KOLONLARI), low_memory=False)
    df = df[(~df["sansurlu"].astype(bool)) & (~df["veri_karantina"].astype(bool))]
    df = df[df["tf"].isin(TFS) & (df["sinyal_sinifi"] == "BIRINCIL")]
    return df.reset_index(drop=True)


def ayni_gun_yon_sayaci(df: pd.DataFrame) -> pd.Series:
    """Aynı takvim günü, aynı yönde, bu işlemin giriş anına KADAR açılmış işlem sayısı (kendisi dahil).

    Nedenseldir: aynı gün daha geç açılan işlemler sayılmaz; aynı anda açılanlar sayılır.
    """
    zaman = pd.to_datetime(df["bar_close_time"], utc=True)
    gun = df["bar_close_time"].astype(str).str[:10]
    return zaman.groupby([gun, df["yon"]]).rank(method="max").astype(int)


def anatomiyi_cikar(df: pd.DataFrame, *, workers: int = 2) -> pd.DataFrame:
    """Her işleme yol alanlarını ekler (sıra korunur)."""
    isler = [(str(s), g.to_dict("records")) for s, g in df.groupby("sembol", sort=True)]
    if workers <= 1:
        parcalar = [_sembol_isle(x) for x in isler]
    else:
        with ProcessPoolExecutor(max_workers=workers) as havuz:
            parcalar = list(havuz.map(_sembol_isle, isler, chunksize=4))
    yol = pd.DataFrame([x for p in parcalar for x in p])
    if len(yol) != len(df) or yol["olay_id"].nunique() != len(df):
        raise ValueError("Anatomi satır sayısı işlem sayısıyla uyuşmuyor")
    out = df.merge(yol, on="olay_id", how="left", validate="one_to_one")
    out["gun"] = out["bar_close_time"].astype(str).str[:10]
    out["ayni_gun_yon_n"] = ayni_gun_yon_sayaci(out)
    return out


# ---------------------------------------------------------------------------
# Özet
# ---------------------------------------------------------------------------
DONEMLER: tuple[str, ...] = ("kesif", "dogrulama")
KAR_ESIKLERI: tuple[float, ...] = (ESIK_AZ_KAR, ESIK_KAR, ESIK_BIR_R, 1.5)
HEDEF_YOLU_ESIKLERI: tuple[float, ...] = (0.5, 0.75, 0.9)
ZOR_ESIKLERI: tuple[float, ...] = (0.25, 0.5, 0.75)
DAR_STOP_ATR: float = 1.0            # "dar stop": stop mesafesi <= 1 ATR
ENDEKS_ESIK_YUZDE: float = 0.5       # endeks bu kadardan az oynadıysa "yatay"
KOSUL_MIN_N: int = 10
B_ARALIK: int = 600

CIKIS_SIRASI: tuple[tuple[str, str], ...] = (
    ("HEDEF", "Hedefe ulaştı"),
    ("STOP", "Stop oldu"),
    ("STOP_BOSLUK", "Açılış boşluğuyla stop oldu"),
    ("SURE", "Süre doldu (ne stop ne hedef)"),
    ("TEZ_IPTAL", "Tez iptaliyle kapandı"),
)
# Stoptan önce görülen işlem-içi etiketler (kutbu `senaryo_v2/surec.py::OLAY_KUTBU`'nda).
UYARI_ETIKETLERI: tuple[tuple[str, str], ...] = (
    ("SEVIYE_ICI", "Kapanış tez seviyesinin ters tarafında"),
    ("FRM_RETEST", "Formasyon retest ediliyor"),
    ("FRM_BASARISIZ", "Formasyon: başarısız kırılım"),
    ("FIYAT_ZARARDA", "Kapanış girişin zarar tarafında"),
    ("FIYAT_TERS_KAPANIS", "Ters yönlü kapanış"),
    ("SR_KARSI_RED", "Karşı Stabil çizgisinde ret"),
    ("BLOK_DUVAR", "Karşı OB/FVG bandında ret"),
    ("VP_TERS_BASKI", "Ters hacim baskısı"),
    ("MS_TERS", "Ters yönlü yapı olayı (iç/dış; sweep dahil)"),
    ("ADAY_KARSI", "Sistemin kendi karşı yön adayı"),
    ("FRM_TEYIT", "Formasyon kırılımı teyit aldı (lehte)"),
)
TEZ_SIRASI: tuple[tuple[str, str], ...] = (
    ("GOZLEM_YOK", "Hiç kapanış görülmedi (ilk mumda çıkış)"),
    ("BEKLIYOR", "Tez henüz teyit almamıştı"),
    ("TEYITLI", "Tez teyitliydi"),
    ("SINANIYOR", "Tez sınanıyordu"),
    ("BOZULDU", "Tez bozulmuştu"),
)
NET, BRUT, BAR = "net15_20_r", "pnl_20_intra_iptal_r", "bar_20_intra_iptal"


# Özet değerleri 6 ondalıkla saklanır; rapor bir kez yuvarlar (çift yuvarlama son haneyi kaydırır).
def _pay(a: int | float, b: int | float) -> float | None:
    return round(float(a) / float(b), 6) if b else None


def _ort(seri: pd.Series, nd: int = 6) -> float | None:
    seri = seri.dropna()
    return round(float(seri.mean()), nd) if len(seri) else None


def _medyan(seri: pd.Series, nd: int = 6) -> float | None:
    seri = seri.dropna()
    return round(float(seri.median()), nd) if len(seri) else None


def _top(seri: pd.Series) -> float:
    return round(float(seri.sum()), 2)


def _stoplar(k: pd.DataFrame) -> pd.DataFrame:
    return k[k["cikis_turu"].isin(("STOP", "STOP_BOSLUK"))]


def _kovala(deger: pd.Series, sinirlar: Sequence[float], adlar: Sequence[str]) -> list[dict[str, Any]]:
    """(sinir[i], sinir[i+1]] aralıklarındaki adetler; sıra korunur."""
    kova = pd.cut(deger.astype(float), list(sinirlar), labels=list(adlar))
    toplam = int(kova.notna().sum())
    return [{"aralik": ad, "n": int((kova == ad).sum()), "pay": _pay(int((kova == ad).sum()), toplam)} for ad in adlar]


def genel_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    n = len(k)
    kar, zarar = k[k["kar"]], k[~k["kar"]]
    kaz, kay = _ort(kar[NET]), _ort(zarar[NET])
    brut_top, masraf_top = _top(k[BRUT]), _top(k["masraf_r"])
    donem = {}
    for d in DONEMLER:
        g = k[k["donem"] == d]
        donem[d] = {
            "n": len(g),
            "kar_pay": _pay(int(g["kar"].sum()), len(g)),
            "stop_pay": _pay(len(_stoplar(g)), len(g)),
            "hedef_pay": _pay(int((g["cikis_turu"] == "HEDEF").sum()), len(g)),
            "net_ort": _ort(g[NET]),
        }
    return {
        "n": n,
        "kar_n": len(kar),
        "zarar_n": len(zarar),
        "kar_pay": _pay(len(kar), n),
        "net_ort": _ort(k[NET]),
        "brut_ort": _ort(k[BRUT]),
        "masraf_ort": _ort(k["masraf_r"]),
        "net_toplam": _top(k[NET]),
        "brut_toplam": brut_top,
        "masraf_toplam": masraf_top,
        "masraf_brut_payi": _pay(masraf_top, brut_top) if brut_top > 0 else None,
        "kazanan_ort_net": kaz,
        "kaybeden_ort_net": kay,
        "kazanan_toplam_net": _top(kar[NET]),
        "kaybeden_toplam_net": _top(zarar[NET]),
        "kazanc_kayip_orani": round(kaz / abs(kay), 6) if kaz and kay else None,
        # Bu ortalama kazanç/kayıpla sıfır beklenti için gereken kâr eden işlem oranı.
        "basabas_kar_pay": round(abs(kay) / (kaz + abs(kay)), 6) if kaz and kay else None,
        "brutte_arti_nette_zarar_n": int(((k[BRUT] >= 0) & (k[NET] < 0)).sum()),
        "risk_atr_medyan": _medyan(k["risk_r_atr"]),
        "hedef_r_medyan": _medyan(k["hedef_r"]),
        "donem": donem,
    }


def cikis_ozeti(k: pd.DataFrame) -> list[dict[str, Any]]:
    satirlar = []
    for tur, ad in CIKIS_SIRASI:
        g = k[k["cikis_turu"] == tur]
        if g.empty:
            continue
        satirlar.append(
            {
                "tur": tur,
                "ad": ad,
                "n": len(g),
                "pay": _pay(len(g), len(k)),
                "kar_n": int(g["kar"].sum()),
                "zarar_n": int((~g["kar"]).sum()),
                "net_ort": _ort(g[NET]),
                "net_toplam": _top(g[NET]),
                "bar_medyan": _medyan(g[BAR]),
            }
        )
    if sum(r["n"] for r in satirlar) != len(k):
        raise ValueError("Çıkış türleri işlemlerin tamamını kapsamıyor")
    return satirlar


def zarar_yollari_ozeti(k: pd.DataFrame) -> list[dict[str, Any]]:
    zarar = k[~k["kar"]]
    toplam = float(zarar[NET].sum())
    satirlar = []
    for kod, ad in ZARAR_YOLLARI:
        g = zarar[zarar["zarar_yolu"] == kod]
        if g.empty and kod == "TEZ_IPTAL":
            continue
        satirlar.append(
            {
                "kod": kod,
                "ad": ad,
                "n": len(g),
                "zarar_payi": _pay(len(g), len(zarar)),
                "islem_payi": _pay(len(g), len(k)),
                "net_ort": _ort(g[NET]),
                "net_toplam": _top(g[NET]),
                "zarar_toplam_payi": _pay(float(g[NET].sum()), toplam),
            }
        )
    if sum(r["n"] for r in satirlar) != len(zarar):
        raise ValueError("Kayıp yolları zarar eden işlemlerin tamamını kapsamıyor")
    return satirlar


def stop_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    s = _stoplar(k)
    n = len(s)
    coz = s[s["saatlik_durum"] == "AYNI"]
    return {
        "n": n,
        "islem_payi": _pay(n, len(k)),
        "zarar_payi": _pay(n, int((~k["kar"]).sum())),
        "bosluk_n": int((s["cikis_turu"] == "STOP_BOSLUK").sum()),
        "bar": _kovala(s[BAR], (0, 1, 3, 6, 100), ("1. mum", "2–3. mum", "4–6. mum", "7–10. mum")),
        "bar_medyan": _medyan(s[BAR]),
        # Mum: stop mumu sayılmaz (alt sınır). Saat: stop saatinden önceki bütün saatler.
        "once_kar": [
            {
                "esik": e,
                "mum_n": int((s["yol_mfe_r"] >= e).sum()),
                "mum_pay": _pay(int((s["yol_mfe_r"] >= e).sum()), n),
                "saat_n": int((coz["saat_mfe_r"] >= e).sum()),
                "saat_pay": _pay(int((coz["saat_mfe_r"] >= e).sum()), len(coz)),
                "saat_kumesinde_mum_n": int((coz["yol_mfe_r"] >= e).sum()),
            }
            for e in KAR_ESIKLERI
        ],
        "hic_lehte_gormedi_n": int((s["yol_mfe_r"] <= 0).sum()),
        "hedef_yolu": [
            {"esik": e, "n": int((s["hedef_yolu_orani"] >= e).sum()), "pay": _pay(int((s["hedef_yolu_orani"] >= e).sum()), n)}
            for e in HEDEF_YOLU_ESIKLERI
        ],
        "ayni_mumda_hedef_n": int(s["ayni_mumda_hedef"].sum()),
        "saatlik": {
            "cozulen_n": len(coz),
            "durum": {str(a): int(b) for a, b in s["saatlik_durum"].value_counts().items()},
        },
    }


def ilk_mum_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    s = _stoplar(k)
    f = s[s[BAR] == 1]
    n = len(f)
    coz = f[f["saatlik_durum"] == "AYNI"]
    dar = k["risk_r_atr"] <= DAR_STOP_ATR
    k_ilk = k["cikis_turu"].isin(("STOP", "STOP_BOSLUK")) & (k[BAR] == 1)
    slot = k["tf"].astype(str) + " " + k["giris_saati"].astype(str)
    return {
        "n": n,
        "stop_payi": _pay(n, len(s)),
        "islem_payi": _pay(n, len(k)),
        "bosluk_n": int((f["cikis_turu"] == "STOP_BOSLUK").sum()),
        "dar_stop_esik_atr": DAR_STOP_ATR,
        "dar_stop_n": int((f["risk_r_atr"] <= DAR_STOP_ATR).sum()),
        "dar_stop_pay": _pay(int((f["risk_r_atr"] <= DAR_STOP_ATR).sum()), n),
        "dar_stoplu_islem_n": int(dar.sum()),
        "dar_stoplu_islemde_oran": _pay(int((k_ilk & dar).sum()), int(dar.sum())),
        "genis_stoplu_islemde_oran": _pay(int((k_ilk & ~dar).sum()), int((~dar).sum())),
        "giris": [
            {"giris": str(ad), "islem_n": len(g), "ilk_mum_stop_n": int(k_ilk[g.index].sum()), "oran": _pay(int(k_ilk[g.index].sum()), len(g))}
            for ad, g in k.groupby(slot, sort=True)
            if len(g) >= KOSUL_MIN_N
        ],
        "saatlik": {
            "n": len(coz),
            "ilk_saatte_n": int((coz["cikis_mumu_saat_sira"] == 1).sum()),
            "ilk_iki_saatte_n": int((coz["cikis_mumu_saat_sira"] <= 2).sum()),
            "dogrudan_n": int((coz["saat_mfe_r"] < ESIK_AZ_KAR).sum()),
            "once_kar": [{"esik": e, "n": int((coz["saat_mfe_r"] >= e).sum())} for e in (ESIK_AZ_KAR, ESIK_KAR, ESIK_BIR_R)],
        },
    }


def bosluk_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    g = k[k["cikis_turu"] == "STOP_BOSLUK"]
    fazla = -g[BRUT] - 1.0          # stop fiyatı yerine açılıştan dolmanın ek kaybı (R)
    return {
        "n": len(g),
        "stop_payi": _pay(len(g), len(_stoplar(k))),
        "brut_ort": _ort(g[BRUT]),
        "brut_en_kotu": round(float(g[BRUT].min()), 6) if len(g) else None,
        "fazladan_kayip_ort": _ort(fazla),
        "fazladan_kayip_toplam": _top(fazla),
        "gun_ilk_mumu_n": int(g["cikis_mumu_gun_ilki"].sum()),
        "ilk_mum_n": int((g[BAR] == 1).sum()),
        "tf": {tf: int((g["tf"] == tf).sum()) for tf in TFS},
        "once_kar_n": int((g["yol_mfe_r"] >= ESIK_KAR).sum()),
    }


def geri_veren_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    s = _stoplar(k)
    g = s[s["yol_mfe_r"] >= ESIK_KAR]
    n = len(g)
    return {
        "esik": ESIK_KAR,
        "n": n,
        "stop_payi": _pay(n, len(s)),
        "bir_r_n": int((g["yol_mfe_r"] >= ESIK_BIR_R).sum()),
        "en_iyi_r_medyan": _medyan(g["yol_mfe_r"]),
        "tepe_stop_arasi": _kovala(g["tepe_stop_arasi"], (0, 1, 2, 3, 100), ("1 mum", "2 mum", "3 mum", "4+ mum")),
        "tepe_stop_medyan": _medyan(g["tepe_stop_arasi"]),
        "hedef_yolu": [
            {"esik": e, "n": int((g["hedef_yolu_orani"] >= e).sum()), "pay": _pay(int((g["hedef_yolu_orani"] >= e).sum()), n)}
            for e in HEDEF_YOLU_ESIKLERI
        ],
    }


def _etiket_var(etiketler: frozenset[str], kod: str) -> bool:
    if kod == "MS_TERS":
        return any(e.startswith("MS_") and e.endswith("_TERS") for e in etiketler)
    return kod in etiketler


def uyari_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    """Stoptan önce işlem-içi gözcü ne görmüştü? (betimleyici; sonuç-koşullu)."""
    izler = [dict(surec_izini_coz(iz)) for iz in k["surec_izi"]]
    etiketler = pd.Series([frozenset(e for et in iz.values() for e in et) for iz in izler], index=k.index)
    # Stop mumundan bir önceki kapanış (son görülen kapanış) tez seviyesinin ters tarafında mıydı?
    son_ici = pd.Series(["SEVIYE_ICI" in iz.get(int(bar) - 1, ()) for iz, bar in zip(izler, k[BAR])], index=k.index)
    gozlemli = k["surec_gozlem_n"].fillna(0) >= 1
    stop = k["cikis_turu"].isin(("STOP", "STOP_BOSLUK"))
    gs, kz = k[stop & gozlemli], k[k["kar"] & gozlemli]
    satirlar = []
    for kod, ad in UYARI_ETIKETLERI:
        a = int(etiketler[gs.index].map(lambda e: _etiket_var(e, kod)).sum())
        b = int(etiketler[kz.index].map(lambda e: _etiket_var(e, kod)).sum())
        satirlar.append({"kod": kod, "ad": ad, "stop_n": a, "stop_pay": _pay(a, len(gs)), "kazanan_n": b, "kazanan_pay": _pay(b, len(kz))})
    tez = k["surec_tez_son"].fillna("").replace("", "GOZLEM_YOK")
    stoplar = k[stop]
    hedefler = k[k["cikis_turu"] == "HEDEF"]
    tez_satirlari = [
        {
            "kod": kod,
            "ad": ad,
            "stop_n": int((tez[stoplar.index] == kod).sum()),
            "stop_pay": _pay(int((tez[stoplar.index] == kod).sum()), len(stoplar)),
            "hedef_n": int((tez[hedefler.index] == kod).sum()),
        }
        for kod, ad in TEZ_SIRASI
    ]
    seviye_goren = int(etiketler[gs.index].map(lambda e: "SEVIYE_ICI" in e).sum())
    son_ici_n = int(son_ici[gs.index].sum())
    # Aynı bayrak fiyattan da hesaplanır (gözcü etiketinden bağımsız); ikisi ayrışırsa dur.
    fiyat_ici = stoplar["stop_oncesi_seviye_icinde"].eq(True)
    if int(fiyat_ici.sum()) != son_ici_n or bool((fiyat_ici[gs.index] != son_ici[gs.index]).any()):
        raise ValueError("Stop öncesi son kapanışın seviye tarafı, etiket izinden ve fiyattan farklı çıktı")
    mesafe = stoplar["stop_oncesi_mesafe_atr"].astype(float)
    acik = stoplar["stop_oncesi_kapanis_r"].astype(float)
    return {
        "stop_n": int(stop.sum()),
        "gozlemsiz_stop_n": int((stop & ~gozlemli).sum()),
        "gozlemli_stop_n": len(gs),
        "gozlemli_kazanan_n": len(kz),
        "seviye_ici_goren_n": seviye_goren,
        "son_kapanista_seviye_ici_n": son_ici_n,
        # Son kapanış hâlâ seviyenin doğru tarafındaydı: stop mumu seviyeyi ve tamponu tek mumda geçti.
        "seviye_disindan_tek_mumda_n": len(gs) - son_ici_n,
        # Stop mumundan önceki son kapanışta (ilk mumda stop olduysa girişte) işlem neredeydi?
        "son_kapanis_r_medyan": _medyan(acik),
        "son_kapanista_karda_n": int((acik > 0).sum()),
        "son_kapanista_yarim_r_karda_n": int((acik >= ESIK_KAR).sum()),
        "stopa_mesafe_atr_medyan": _medyan(mesafe),
        "stopa_mesafe_bir_atr_alti_n": int((mesafe <= 1.0).sum()),
        "stopa_mesafe_yarim_atr_alti_n": int((mesafe <= 0.5).sum()),
        "etiketler": satirlar,
        "tez_son": tez_satirlari,
    }


def stop_sonrasi_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    s = _stoplar(k)

    def dagilim(g: pd.DataFrame) -> list[dict[str, Any]]:
        return [
            {"kod": kod, "ad": ad, "n": int((g["stop_sonrasi"] == kod).sum()), "pay": _pay(int((g["stop_sonrasi"] == kod).sum()), len(g))}
            for kod, ad in STOP_SONRASI
        ]

    ilk = s[BAR] == 1
    geri = s["yol_mfe_r"] >= ESIK_KAR
    return {
        "n": len(s),
        "tumu": dagilim(s),
        "ilk_mum": {"n": int(ilk.sum()), "dagilim": dagilim(s[ilk])},
        "kar_gormeden": {"n": int((~ilk & ~geri).sum()), "dagilim": dagilim(s[~ilk & ~geri])},
        "geri_veren": {"n": int((~ilk & geri).sum()), "dagilim": dagilim(s[~ilk & geri])},
    }


def sure_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    z = k[k["cikis_turu"] == "SURE"]
    kar, zar = z[z["kar"]], z[~z["kar"]]
    return {
        "n": len(z),
        "islem_payi": _pay(len(z), len(k)),
        "net_toplam": _top(z[NET]),
        "kar_n": len(kar),
        "kar_ort_net": _ort(kar[NET]),
        "zarar_n": len(zar),
        "zarar_ort_net": _ort(zar[NET]),
        "zararda_brut_arti_n": int((zar[BRUT] >= 0).sum()),
        "zararda_yarim_r_gormus_n": int((zar["yol_mfe_r"] >= ESIK_KAR).sum()),
        "zararda_bir_r_gormus_n": int((zar["yol_mfe_r"] >= ESIK_BIR_R).sum()),
        "karda_hedef_yolu_medyan": _medyan(kar["hedef_yolu_orani"]),
        "karda_yarim_r_aleyhte_gormus_n": int((kar["yol_mae_r"] >= 0.5).sum()),
        "yarim_r_oynamayan_n": int(((z["yol_mfe_r"] < 0.5) & (z["yol_mae_r"] < 0.5)).sum()),
    }


def kurtaran_ozeti(k: pd.DataFrame) -> list[dict[str, Any]]:
    """İşlem aleyhte bu kadar R gördükten sonra nasıl bitti? (çıkış mumunun geri kalanı sayılmaz)."""
    satirlar = []
    for e in ZOR_ESIKLERI:
        g = k[k["yol_mae_r"] >= e]
        stop_n = len(_stoplar(g))
        satirlar.append(
            {
                "esik": e,
                "goren_n": len(g),
                "stop_n": stop_n,
                "stop_pay": _pay(stop_n, len(g)),
                "kar_n": int(g["kar"].sum()),
                "kar_pay": _pay(int(g["kar"].sum()), len(g)),
                "hedef_n": int((g["cikis_turu"] == "HEDEF").sum()),
                "stopsuz_zarar_n": int((~g["kar"]).sum()) - stop_n,
            }
        )
    return satirlar


def kazanan_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    h = k[k["cikis_turu"] == "HEDEF"]
    sk = k[(k["cikis_turu"] == "SURE") & k["kar"]]
    return {
        "kar_n": int(k["kar"].sum()),
        "hedef_n": len(h),
        "hedef_ort_net": _ort(h[NET]),
        "hedef_r_ort": _ort(h["hedef_r"]),
        "ilk_mumda_hedef_n": int((h[BAR] == 1).sum()),
        "bar": _kovala(h[BAR], (0, 1, 3, 6, 100), ("1. mum", "2–3. mum", "4–6. mum", "7–10. mum")),
        "bar_medyan": _medyan(h[BAR]),
        "once_aleyhte": [
            {"esik": e, "n": int((h["yol_mae_r"] >= e).sum()), "pay": _pay(int((h["yol_mae_r"] >= e).sum()), len(h))} for e in ZOR_ESIKLERI
        ],
        "sure_karda_n": len(sk),
        "sure_karda_ort_net": _ort(sk[NET]),
    }


def _kosul_satiri(ad: str, g: pd.DataFrame) -> dict[str, Any]:
    oz = zaman_kumesi_saglamligi(g, NET, B=B_ARALIK)
    ustler = [v["ci95_ust"] for v in oz["kumeler"].values() if v["ci95_ust"] is not None]
    s = _stoplar(g)
    kesif, dogrulama = g[g["donem"] == "kesif"], g[g["donem"] == "dogrulama"]
    return {
        "kova": ad,
        "n": len(g),
        "stop_pay": _pay(len(s), len(g)),
        "ilk_mum_stop_pay": _pay(int((s[BAR] == 1).sum()), len(g)),
        "hedef_pay": _pay(int((g["cikis_turu"] == "HEDEF").sum()), len(g)),
        "kar_pay": _pay(int(g["kar"].sum()), len(g)),
        "net_ort": _ort(g[NET]),
        # Dört küme tanımının (sembol / gün / hafta / ay) en kötü alt ve en kötü üst sınırı.
        "en_kotu_alt": oz["en_kotu_alt"],
        "en_kotu_ust": max(ustler) if ustler else None,
        "kesif_n": len(kesif),
        "kesif_net": _ort(kesif[NET]),
        "dogrulama_n": len(dogrulama),
        "dogrulama_net": _ort(dogrulama[NET]),
        "hedef_r_ort": _ort(g["hedef_r"]),
        "masraf_ort": _ort(g["masraf_r"]),
    }


def kosul_tablosu(k: pd.DataFrame, anahtar: pd.Series, *, sira: Sequence[str] | None = None, min_n: int = KOSUL_MIN_N) -> dict[str, Any]:
    """Bir giriş koşuluna göre kovalar. İlişki gösterir; neden ya da kural değeri göstermez."""
    anahtar = anahtar.reindex(k.index)
    gruplar = {str(ad): g for ad, g in k.groupby(anahtar, observed=True, sort=True)}
    adlar = [a for a in (sira if sira is not None else sorted(gruplar)) if a in gruplar]
    return {
        "satirlar": [_kosul_satiri(a, gruplar[a]) for a in adlar if len(gruplar[a]) >= min_n],
        "olculemeyen_n": int(anahtar.isna().sum()),
        "kucuk_kova_n": int(sum(len(gruplar[a]) for a in adlar if len(gruplar[a]) < min_n)),
    }


def _kes(deger: pd.Series, sinirlar: Sequence[float], adlar: Sequence[str]) -> pd.Series:
    return pd.cut(deger.astype(float), list(sinirlar), labels=list(adlar)).astype(object)


RISK_SINIR = (0.0, 0.8, 1.0, 1.3, 1.7, 2.2, np.inf)
RISK_AD = ("≤ 0.8 ATR", "0.8–1.0 ATR", "1.0–1.3 ATR", "1.3–1.7 ATR", "1.7–2.2 ATR", "> 2.2 ATR")
ENDEKS_ISLEM_SINIR = (-np.inf, -2.0, -ENDEKS_ESIK_YUZDE, ENDEKS_ESIK_YUZDE, 2.0, np.inf)
ENDEKS_ISLEM_AD = ("%2'den fazla ters", "%0.5–2 ters", "yatay (±%0.5)", "%0.5–2 lehte", "%2'den fazla lehte")
ENDEKS_ON_SINIR = (-np.inf, -2.0, 0.0, 2.0, np.inf)
ENDEKS_ON_AD = ("%2'den fazla ters", "%0–2 ters", "%0–2 lehte", "%2'den fazla lehte")
KALABALIK_SINIR = (0, 1, 3, 8, np.inf)
KALABALIK_AD = ("1 (yalnız)", "2–3", "4–8", "9+")


def kosullar_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    return {
        "stop_mesafesi": kosul_tablosu(k, _kes(k["risk_r_atr"], RISK_SINIR, RISK_AD), sira=RISK_AD),
        "yon_donem": kosul_tablosu(k, k["donem"].astype(str) + " / " + k["yon"].astype(str)),
        "giris": kosul_tablosu(k, k["tf"].astype(str) + " " + k["giris_saati"].astype(str)),
        "endeks_islem": kosul_tablosu(k, _kes(k["endeks_islem_yuzde"], ENDEKS_ISLEM_SINIR, ENDEKS_ISLEM_AD), sira=ENDEKS_ISLEM_AD),
        "endeks_on": kosul_tablosu(k, _kes(k["endeks_on5_yuzde"], ENDEKS_ON_SINIR, ENDEKS_ON_AD), sira=ENDEKS_ON_AD),
        "kalabalik": kosul_tablosu(k, _kes(k["ayni_gun_yon_n"], KALABALIK_SINIR, KALABALIK_AD), sira=KALABALIK_AD),
        "formasyon": kosul_tablosu(k, k["frm_pattern_type"].astype(str), min_n=30),
    }


def piyasa_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    """Çıkış türüne göre: işlem açıkken endeks işlemin yönüne göre ne yaptı?"""

    def dagilim(g: pd.DataFrame) -> dict[str, Any]:
        x = g["endeks_islem_yuzde"].dropna()
        n = len(x)
        ters, lehte = int((x <= -ENDEKS_ESIK_YUZDE).sum()), int((x >= ENDEKS_ESIK_YUZDE).sum())
        return {
            "n": len(g),
            "olculen_n": n,
            "ters_n": ters,
            "ters_pay": _pay(ters, n),
            "yatay_n": n - ters - lehte,
            "yatay_pay": _pay(n - ters - lehte, n),
            "lehte_n": lehte,
            "lehte_pay": _pay(lehte, n),
            "ort_yuzde": _ort(x),
        }

    return {
        "esik_yuzde": ENDEKS_ESIK_YUZDE,
        "stop": dagilim(_stoplar(k)),
        "hedef": dagilim(k[k["cikis_turu"] == "HEDEF"]),
        "sure": dagilim(k[k["cikis_turu"] == "SURE"]),
    }


def dar_genis_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    """Stop mesafesi `DAR_STOP_ATR` ve altı olan işlemler ile daha geniş stoplular."""
    dar = k["risk_r_atr"] <= DAR_STOP_ATR

    def oz(g: pd.DataFrame) -> dict[str, Any]:
        s = _stoplar(g)
        return {
            "n": len(g),
            "stop_pay": _pay(len(s), len(g)),
            "ilk_mum_stop_pay": _pay(int((s[BAR] == 1).sum()), len(g)),
            "kar_pay": _pay(int(g["kar"].sum()), len(g)),
            "net_ort": _ort(g[NET]),
            "hedef_r_ort": _ort(g["hedef_r"]),
            "masraf_ort": _ort(g["masraf_r"]),
        }

    return {"esik_atr": DAR_STOP_ATR, "dar": oz(k[dar]), "genis": oz(k[~dar])}


HAFTA_UC_N: int = 5


def hafta_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    """Sonuç, işlemin AÇILDIĞI takvim haftasına göre ne kadar yoğun?"""
    iso = pd.to_datetime(k["gun"]).dt.isocalendar()
    hafta = (iso["year"].astype(str) + "-H" + iso["week"].astype(str).str.zfill(2)).to_numpy()
    satirlar = []
    for ad, g in k.groupby(hafta, sort=True):
        satirlar.append(
            {
                "hafta": str(ad),
                "n": len(g),
                "net_toplam": float(g[NET].sum()),          # ham; yuvarlama en sonda
                "stop_n": len(_stoplar(g)),
                "long_n": int((g["yon"] == "long").sum()),
                "short_n": int((g["yon"] == "short").sum()),
            }
        )
    sirali = sorted(satirlar, key=lambda r: (r["net_toplam"], r["hafta"]))
    net = float(k[NET].sum())
    en_iyi, en_kotu = sirali[-HAFTA_UC_N:][::-1], sirali[:HAFTA_UC_N]
    en_iyi_top = sum(r["net_toplam"] for r in en_iyi)
    en_kotu_top = sum(r["net_toplam"] for r in en_kotu)
    tek_yon = [r for r in satirlar if r["long_n"] == 0 or r["short_n"] == 0]

    def yuvarla(r: dict[str, Any]) -> dict[str, Any]:
        return {**r, "net_toplam": round(r["net_toplam"], 2)}

    return {
        "hafta_n": len(satirlar),
        "arti_hafta_n": sum(1 for r in satirlar if r["net_toplam"] > 0),
        "eksi_hafta_n": sum(1 for r in satirlar if r["net_toplam"] < 0),
        "arti_toplam": round(sum(r["net_toplam"] for r in satirlar if r["net_toplam"] > 0), 2),
        "eksi_toplam": round(sum(r["net_toplam"] for r in satirlar if r["net_toplam"] < 0), 2),
        "net_toplam": round(net, 2),
        "uc_n": HAFTA_UC_N,
        "en_iyi": [yuvarla(r) for r in en_iyi],
        "en_kotu": [yuvarla(r) for r in en_kotu],
        "en_iyi_toplam": round(en_iyi_top, 2),
        "en_kotu_toplam": round(en_kotu_top, 2),
        "en_iyi_haric_net": round(net - en_iyi_top, 2),
        "en_kotu_haric_net": round(net - en_kotu_top, 2),
        # Bütün işlemleri aynı yönde olan haftalar (o hafta sistem tek yöne bahis yapmıştır).
        "tek_yonlu_hafta_n": len(tek_yon),
        "tek_yonlu_haftalardaki_islem_n": sum(r["n"] for r in tek_yon),
    }


def kume_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    return {
        "genel": genel_ozeti(k),
        "cikis": cikis_ozeti(k),
        "zarar_yollari": zarar_yollari_ozeti(k),
        "stop": stop_ozeti(k),
        "ilk_mum": ilk_mum_ozeti(k),
        "bosluk": bosluk_ozeti(k),
        "geri_veren": geri_veren_ozeti(k),
        "uyari": uyari_ozeti(k),
        "stop_sonrasi": stop_sonrasi_ozeti(k),
        "sure": sure_ozeti(k),
        "kurtaran": kurtaran_ozeti(k),
        "kazanan": kazanan_ozeti(k),
        "piyasa": piyasa_ozeti(k),
        "hafta": hafta_ozeti(k),
        "dar_genis": dar_genis_ozeti(k),
        "kosullar": kosullar_ozeti(k),
    }


_ANA_KATMAN = {"D7_A_Arti": "D7_A_Arti_UyumluBOS", "D6_A_Cekirdek_Veya_Arti": "D6_A_Cekirdek_Veya_Arti", "D1_Birincil": "D1_Birincil_KirilimAdayi"}


def ana_rapor_esitligi(df: pd.DataFrame, girdi: Path) -> dict[str, Any]:
    """Bu betiğin kümeleri ana rapordaki merdiven satırlarıyla aynı mı? (N ve net ortalama)."""
    yol = girdi / "ozet_rapor.json"
    if not yol.exists():
        return {"durum": "ozet_rapor_yok"}
    merdiven = json.loads(yol.read_text(encoding="utf-8")).get("domain_merdiven_4h1d_net15", [])
    sonuc: dict[str, Any] = {"durum": "karsilastirildi", "kumeler": {}}
    for ad, maske in KUMELER.items():
        k = df[maske(df)]
        ana = next((x for x in merdiven if x.get("donem") == "tumu" and x.get("katman") == _ANA_KATMAN[ad]), None)
        if ana is None:
            raise ValueError(f"Ana raporda {_ANA_KATMAN[ad]} satırı yok")
        ayni = int(ana["n"]) == len(k) and abs(float(ana["ort"]) - float(k[NET].mean())) < 5e-4
        if not ayni:
            raise ValueError(f"{ad}: ana rapor N={ana['n']} ort={ana['ort']}, burada N={len(k)} ort={k[NET].mean():.4f}")
        sonuc["kumeler"][ad] = {"n": len(k), "net_ort": round(float(k[NET].mean()), 4)}
    return sonuc


def ozet_uret(df: pd.DataFrame, girdi: Path) -> dict[str, Any]:
    return {
        "meta": {
            "islem_n": int(len(df)),
            "tfs": list(TFS),
            "hedef_atr": HEDEF_ATR,
            "endeks": ENDEKS,
            # `islem_anatomisi` tek bir uyuşmazlıkta durur; buraya gelindiyse hepsi doğrulandı.
            "yol_csv_ile_ayni_n": int(len(df)),
            "ana_rapor_esitligi": ana_rapor_esitligi(df, girdi),
            "saatlik_durum": {
                tf: {str(a): int(b) for a, b in df[df["tf"] == tf]["saatlik_durum"].value_counts().items()} for tf in TFS
            },
            "esikler": {
                "az_kar_r": ESIK_AZ_KAR,
                "kar_r": ESIK_KAR,
                "bir_r": ESIK_BIR_R,
                "dar_stop_atr": DAR_STOP_ATR,
                "endeks_yatay_yuzde": ENDEKS_ESIK_YUZDE,
            },
        },
        "kumeler": {ad: kume_ozeti(df[maske(df)]) for ad, maske in KUMELER.items()},
    }



# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------
def _f(x: Any, nd: int = 3) -> str:
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{float(x):+.{nd}f}"


def _g(x: Any, nd: int = 3) -> str:
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{float(x):.{nd}f}"


def _yz(pay: Any) -> str:
    return "—" if pay is None else f"{100.0 * float(pay):.1f}%"


def _ny(n: int, pay: Any) -> str:
    return f"{n} ({_yz(pay)})"


def _kosul_md(tablo: dict[str, Any], baslik: str, *, donem: bool = True) -> list[str]:
    donem_baslik = " Keşif (n) | Doğrulama (n) |" if donem else ""
    s = [
        f"| {baslik} | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA |{donem_baslik} Ort. hedef R | Ort. masraf R |",
        "|---|---:|---:|---:|---:|---:|---:|---|" + ("---:|---:|" if donem else "") + "---:|---:|",
    ]
    for r in tablo["satirlar"]:
        donem_hucre = f" {_f(r['kesif_net'])} ({r['kesif_n']}) | {_f(r['dogrulama_net'])} ({r['dogrulama_n']}) |" if donem else ""
        s.append(
            f"| {r['kova']} | {r['n']} | {_yz(r['stop_pay'])} | {_yz(r['ilk_mum_stop_pay'])} | {_yz(r['hedef_pay'])} | {_yz(r['kar_pay'])} | "
            f"{_f(r['net_ort'])} | [{_f(r['en_kotu_alt'])}, {_f(r['en_kotu_ust'])}] |{donem_hucre} {_g(r['hedef_r_ort'], 2)} | {_g(r['masraf_ort'])} |"
        )
    notlar = []
    if tablo["olculemeyen_n"]:
        notlar.append(f"ölçülemeyen `{tablo['olculemeyen_n']}` işlem")
    if tablo["kucuk_kova_n"]:
        notlar.append(f"küçük kovalarda kalan `{tablo['kucuk_kova_n']}` işlem")
    if notlar:
        s += ["", "Tabloda yok: " + "; ".join(notlar) + "."]
    return s


def _kisa_ozet_md(v: dict[str, Any]) -> list[str]:
    """Bir kümenin en önemli oranları; cümleler sayılardan üretilir."""
    g, st, im, bo, uy, ss, su, py = v["genel"], v["stop"], v["ilk_mum"], v["bosluk"], v["uyari"], v["stop_sonrasi"], v["sure"], v["piyasa"]
    dg, hf = v["dar_genis"], v["hafta"]
    yarim = next(r for r in st["once_kar"] if r["esik"] == ESIK_KAR)
    bir = next(r for r in st["once_kar"] if r["esik"] == ESIK_BIR_R)
    sonra = {r["kod"]: r for r in ss["tumu"]}
    uyarisiz = uy["gozlemsiz_stop_n"] + uy["seviye_disindan_tek_mumda_n"]
    return [
        f"- **Sonuç:** `{g['n']}` işlem; kâr eden `{_ny(g['kar_n'], g['kar_pay'])}`, zarar eden `{_ny(g['zarar_n'], _pay(g['zarar_n'], g['n']))}`. "
        f"Kazanan ortalama `{_f(g['kazanan_ort_net'])} R`, kaybeden `{_f(g['kaybeden_ort_net'])} R`; işlem başına net `{_f(g['net_ort'])} R`.",
        f"- **Zarar edenler:** stop olan `{_ny(st['n'], st['zarar_payi'])}`; stop olmadan, süre dolunca zararda kapanan "
        f"`{_ny(su['zarar_n'], _pay(su['zarar_n'], g['zarar_n']))}` (ortalama `{_f(su['zarar_ort_net'])} R`).",
        f"- **Stopun hızı:** girişten sonraki ilk mumda `{_ny(im['n'], im['stop_payi'])}`; açılış boşluğuyla `{_ny(bo['n'], bo['stop_payi'])}` "
        f"(boşluk, stop başına ortalama `{_g(bo['fazladan_kayip_ort'])} R` fazladan kayıp).",
        f"- **Önce kâr, sonra stop:** stop olanların `{_ny(yarim['mum_n'], yarim['mum_pay'])}` kadarı stoptan önce en az `+{ESIK_KAR:g} R`, "
        f"`{_ny(bir['mum_n'], bir['mum_pay'])}` kadarı en az `+{ESIK_BIR_R:g} R` görmüştü (mum çözünürlüğü, alt sınır; "
        f"saat çözünürlüğünde `{_yz(yarim['saat_pay'])}` ve `{_yz(bir['saat_pay'])}`).",
        f"- **Uyarısız stop:** stopların `{_ny(uyarisiz, _pay(uyarisiz, st['n']))}` kadarında stoptan önce tez seviyesinin ters tarafında tek bir "
        f"kapanış yoktu (ilk mumda stop `{uy['gozlemsiz_stop_n']}` + son kapanışı hâlâ doğru tarafta olan `{uy['seviye_disindan_tek_mumda_n']}`).",
        f"- **Stoptan sonra:** stop olanların `{_ny(sonra['HEDEFE_GITTI']['n'], sonra['HEDEFE_GITTI']['pay'])}` kadarı stoptan sonra özgün hedefe "
        f"ulaştı; `{_ny(sonra['DAHA_KOTU']['n'], sonra['DAHA_KOTU']['pay'])}` kadarı ufuk sonunda stopun da ötesindeydi.",
        f"- **Piyasa:** stop olanların `{_yz(py['stop']['ters_pay'])}` kadarında endeks işlem süresince en az `%{ENDEKS_ESIK_YUZDE:g}` ters gitti; "
        f"hedefe ulaşanlarda bu oran `{_yz(py['hedef']['ters_pay'])}`, endeksin lehte gittiği pay `{_yz(py['hedef']['lehte_pay'])}`.",
        f"- **Stop mesafesi:** stopu `{dg['esik_atr']:g} ATR` ya da daha yakın olan `{dg['dar']['n']}` işlemin `{_yz(dg['dar']['stop_pay'])}` kadarı stop oldu "
        f"(net `{_f(dg['dar']['net_ort'])} R`); daha geniş stoplu `{dg['genis']['n']}` işlemde `{_yz(dg['genis']['stop_pay'])}` (net `{_f(dg['genis']['net_ort'])} R`).",
        f"- **Haftalar:** `{hf['hafta_n']}` haftanın en iyi `{hf['uc_n']}` tanesi `{_f(hf['en_iyi_toplam'], 1)} R` üretti; onlar olmadan toplam net "
        f"`{_f(hf['en_iyi_haric_net'], 1)} R` (hepsiyle `{_f(hf['net_toplam'], 1)} R`).",
        f"- **Masraf:** brüt toplam `{_f(g['brut_toplam'], 1)} R`, masraf `{_g(g['masraf_toplam'], 1)} R` "
        f"({'brütün `' + _yz(g['masraf_brut_payi']) + '` kadarı' if g['masraf_brut_payi'] is not None else 'brüt toplam pozitif değil'}), "
        f"net `{_f(g['net_toplam'], 1)} R`.",
    ]


def _karsilastirma_md(ozet: dict[str, Any]) -> list[str]:
    adlar = list(ozet["kumeler"])
    s = ["| Oran | " + " | ".join(KUME_KISA[a] for a in adlar) + " |", "|---|" + "---:|" * len(adlar)]

    def satir(ad: str, f: Any) -> None:
        s.append(f"| {ad} | " + " | ".join(f(ozet["kumeler"][a]) for a in adlar) + " |")

    def once(v: dict[str, Any], esik: float) -> dict[str, Any]:
        return next(r for r in v["stop"]["once_kar"] if r["esik"] == esik)

    def sonra(v: dict[str, Any], kod: str) -> dict[str, Any]:
        return next(r for r in v["stop_sonrasi"]["tumu"] if r["kod"] == kod)

    satir("İşlem", lambda v: str(v["genel"]["n"]))
    satir("Kâr eden", lambda v: _yz(v["genel"]["kar_pay"]))
    satir("İşlem başına net R", lambda v: _f(v["genel"]["net_ort"]))
    satir("İşlem başına masraf R", lambda v: _g(v["genel"]["masraf_ort"]))
    satir("Stop olan (işlemlerin payı)", lambda v: _yz(v["stop"]["islem_payi"]))
    satir("Hedefe ulaşan (işlemlerin payı)", lambda v: _yz(_pay(v["kazanan"]["hedef_n"], v["genel"]["n"])))
    satir("Süre dolan (işlemlerin payı)", lambda v: _yz(v["sure"]["islem_payi"]))
    satir("Stopların: ilk mumda", lambda v: _yz(v["ilk_mum"]["stop_payi"]))
    satir("Stopların: açılış boşluğuyla", lambda v: _yz(v["bosluk"]["stop_payi"]))
    satir(f"Stopların: önce ≥ +{ESIK_KAR:g} R gördü (mum)", lambda v: _yz(once(v, ESIK_KAR)["mum_pay"]))
    satir(f"Stopların: önce ≥ +{ESIK_BIR_R:g} R gördü (mum)", lambda v: _yz(once(v, ESIK_BIR_R)["mum_pay"]))
    satir(
        "Stopların: uyarı kapanışı yoktu",
        lambda v: _yz(_pay(v["uyari"]["gozlemsiz_stop_n"] + v["uyari"]["seviye_disindan_tek_mumda_n"], v["stop"]["n"])),
    )
    satir("Stopların: sonra hedefe gitti", lambda v: _yz(sonra(v, "HEDEFE_GITTI")["pay"]))
    satir("Stopların: ufuk sonunda stopun ötesinde", lambda v: _yz(sonra(v, "DAHA_KOTU")["pay"]))
    satir(f"Stopların: endeks ≥ %{ENDEKS_ESIK_YUZDE:g} ters", lambda v: _yz(v["piyasa"]["stop"]["ters_pay"]))
    satir(f"Hedeflerin: endeks ≥ %{ENDEKS_ESIK_YUZDE:g} ters", lambda v: _yz(v["piyasa"]["hedef"]["ters_pay"]))
    return s


def _kume_md(v: dict[str, Any]) -> list[str]:
    g, st, im, bo, gv, uy, ss, su, kz, py, ks, dg, hf = (
        v["genel"], v["stop"], v["ilk_mum"], v["bosluk"], v["geri_veren"], v["uyari"], v["stop_sonrasi"], v["sure"], v["kazanan"], v["piyasa"],
        v["kosullar"], v["dar_genis"], v["hafta"],
    )
    s: list[str] = []

    # 1
    s += [
        "### 1. Genel tablo",
        "",
        "| | İşlem | Pay | Ortalama net R | Toplam net R |",
        "|---|---:|---:|---:|---:|",
        f"| Kâr eden | {g['kar_n']} | {_yz(g['kar_pay'])} | {_f(g['kazanan_ort_net'])} | {_f(g['kazanan_toplam_net'], 1)} |",
        f"| Zarar eden | {g['zarar_n']} | {_yz(_pay(g['zarar_n'], g['n']))} | {_f(g['kaybeden_ort_net'])} | {_f(g['kaybeden_toplam_net'], 1)} |",
        f"| Tümü | {g['n']} | 100.0% | {_f(g['net_ort'])} | {_f(g['net_toplam'], 1)} |",
        "",
        f"- Brüt toplam `{_f(g['brut_toplam'], 1)} R`; masraf `{_g(g['masraf_toplam'], 1)} R` (işlem başına `{_g(g['masraf_ort'])} R`"
        + (f", brütün `{_yz(g['masraf_brut_payi'])}` kadarı" if g["masraf_brut_payi"] is not None else "")
        + f"); net `{_f(g['net_toplam'], 1)} R`.",
        f"- Ortalama kazancın ortalama kayba oranı `{_g(g['kazanc_kayip_orani'], 2)}`. Bu oranla sıfır beklenti için işlemlerin "
        f"`{_yz(g['basabas_kar_pay'])}` kadarının kâr etmesi gerekir; gerçekleşen `{_yz(g['kar_pay'])}`.",
        f"- Brütte artıda olup masraf yüzünden zarara düşen işlem: `{g['brutte_arti_nette_zarar_n']}`.",
        f"- Medyan stop mesafesi `{_g(g['risk_atr_medyan'], 2)} ATR`; hedef `{HEDEF_ATR:.1f} ATR`, yani medyan işlemde `{_g(g['hedef_r_medyan'], 2)} R`.",
        "",
        "| Dönem | İşlem | Kâr eden | Stop | Hedef | Net R |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for d in DONEMLER:
        r = g["donem"][d]
        s.append(f"| {d} | {r['n']} | {_yz(r['kar_pay'])} | {_yz(r['stop_pay'])} | {_yz(r['hedef_pay'])} | {_f(r['net_ort'])} |")

    # 2
    s += [
        "",
        "### 2. İşlemler nasıl kapandı",
        "",
        "| Çıkış | İşlem | Pay | Kârda | Zararda | Ortalama net R | Toplam net R | Medyan mum |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in v["cikis"]:
        s.append(
            f"| {r['ad']} | {r['n']} | {_yz(r['pay'])} | {r['kar_n']} | {r['zarar_n']} | {_f(r['net_ort'])} | {_f(r['net_toplam'], 1)} | {_g(r['bar_medyan'], 0)} |"
        )

    # 3
    s += [
        "",
        "### 3. Zarar edenler nasıl kaybetti",
        "",
        "Her zarar eden işlem tek satırdadır; paylar %100'e toplanır. Sıra önceliktir: boşlukla stop olan işlem, öncesinde ne "
        "görmüş olursa olsun `Açılış boşluğu` satırındadır. Kâr eşikleri stop mumundan ÖNCE görülen en iyi andır.",
        "",
        "| Kayıp yolu | İşlem | Zarar edenlerin payı | Tüm işlemlerin payı | Ortalama net R | Toplam net R | Toplam zarardaki pay |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in v["zarar_yollari"]:
        s.append(
            f"| {r['ad']} | {r['n']} | {_yz(r['zarar_payi'])} | {_yz(r['islem_payi'])} | {_f(r['net_ort'])} | {_f(r['net_toplam'], 1)} | {_yz(r['zarar_toplam_payi'])} |"
        )

    # 4
    s += [
        "",
        "### 4. Stop olanlar stoptan önce ne kadar kâr gördü",
        "",
        f"Stop olan işlem: `{_ny(st['n'], st['islem_payi'])}` (zarar edenlerin `{_yz(st['zarar_payi'])}` kadarı). "
        f"Saat çözünürlüğünde çözülen stop: `{st['saatlik']['cozulen_n']}`.",
        "",
        f"| Stoptan önce en az | Mum çözünürlüğü ({st['n']} stop) | Saat çözünürlüğü ({st['saatlik']['cozulen_n']} stop) | Aynı {st['saatlik']['cozulen_n']} stopta mum |",
        "|---|---:|---:|---:|",
    ]
    for r in st["once_kar"]:
        s.append(
            f"| +{r['esik']:g} R | {_ny(r['mum_n'], r['mum_pay'])} | {_ny(r['saat_n'], r['saat_pay'])} | "
            f"{_ny(r['saat_kumesinde_mum_n'], _pay(r['saat_kumesinde_mum_n'], st['saatlik']['cozulen_n']))} |"
        )
    s += [
        "",
        "- Kaçıncı mumda stop: " + "; ".join(f"{r['aralik']} `{_ny(r['n'], r['pay'])}`" for r in st["bar"]) + f". Medyan `{_g(st['bar_medyan'], 0)}`. mum.",
        f"- Stop mumundan önce girişin kâr tarafında tek bir fiyat görmeyen: `{_ny(st['hic_lehte_gormedi_n'], _pay(st['hic_lehte_gormedi_n'], st['n']))}` "
        "(ilk mumda stop olanlar dahil).",
        "- Hedefe ne kadar yaklaşıp döndüler: "
        + "; ".join(f"hedef yolunun en az %{100 * r['esik']:g} kadarı `{_ny(r['n'], r['pay'])}`" for r in st["hedef_yolu"])
        + ".",
        f"- Stop ile hedef aynı mumda görülen (sıra bilinmediği için stop sayılan) işlem: `{st['ayni_mumda_hedef_n']}`. "
        f"Saatlik veride önce hedefin görüldüğü stop: `{st['saatlik']['durum'].get('ONCE_HEDEF', 0)}`.",
    ]

    # 5
    sa = im["saatlik"]
    s += [
        "",
        "### 5. Girişten sonraki ilk mumda stop olanlar",
        "",
        f"- İşlem: `{im['n']}` — stopların `{_yz(im['stop_payi'])}`, bütün işlemlerin `{_yz(im['islem_payi'])}` kadarı. Açılış boşluğuyla olan: `{im['bosluk_n']}`.",
        f"- Stop mesafesi `{im['dar_stop_esik_atr']:g} ATR` ya da daha yakın olan: `{_ny(im['dar_stop_n'], im['dar_stop_pay'])}`. "
        f"Dar stoplu işlemlerin `{_yz(im['dar_stoplu_islemde_oran'])}` kadarı ilk mumda stop oldu; daha geniş stoplularda `{_yz(im['genis_stoplu_islemde_oran'])}`.",
        f"- Saat çözünürlüğünde çözülen: `{sa['n']}`. Mumun ilk saatinde stop `{sa['ilk_saatte_n']}`, ilk iki saatinde `{sa['ilk_iki_saatte_n']}`.",
        f"- Aynı `{sa['n']}` işlemde stoptan önce `+{ESIK_AZ_KAR:g} R`'yi hiç görmeyen (doğrudan stop): `{_ny(sa['dogrudan_n'], _pay(sa['dogrudan_n'], sa['n']))}`. "
        + "Önce kâr görüp aynı mumda dönen: "
        + "; ".join(f"≥ +{r['esik']:g} R `{r['n']}`" for r in sa["once_kar"])
        + ".",
        "",
        "| Giriş (zaman dilimi, olay mumunun kapanış saati) | İşlem | İlk mumda stop | Oran |",
        "|---|---:|---:|---:|",
    ]
    for r in im["giris"]:
        s.append(f"| {r['giris']} | {r['islem_n']} | {r['ilk_mum_stop_n']} | {_yz(r['oran'])} |")

    # 6
    s += [
        "",
        "### 6. Açılış boşluğuyla stop olanlar",
        "",
        f"- İşlem: `{_ny(bo['n'], bo['stop_payi'])}` (stopların payı). Zaman dilimi: " + ", ".join(f"{tf} `{n}`" for tf, n in bo["tf"].items()) + ".",
        f"- İşlem gününün ilk mumunda (gece boşluğu) olan: `{bo['gun_ilk_mumu_n']}`. Girişten sonraki ilk mumda olan: `{bo['ilk_mum_n']}`.",
        f"- Ortalama brüt sonuç `{_f(bo['brut_ort'])} R`, en kötü `{_f(bo['brut_en_kotu'])} R`. Stop fiyatı yerine açılıştan dolmanın ek kaybı "
        f"ortalama `{_g(bo['fazladan_kayip_ort'])} R`, toplam `{_g(bo['fazladan_kayip_toplam'], 1)} R`.",
        f"- Boşluktan önce en az `+{ESIK_KAR:g} R` görmüş olan: `{bo['once_kar_n']}`.",
    ]

    # 7
    s += [
        "",
        f"### 7. En az +{gv['esik']:g} R görüp stop olanlar",
        "",
        f"- İşlem: `{_ny(gv['n'], gv['stop_payi'])}` (stopların payı); bunların `{gv['bir_r_n']}` kadarı en az `+{ESIK_BIR_R:g} R` gördü. "
        f"Gördükleri en iyi anın medyanı `{_f(gv['en_iyi_r_medyan'], 2)} R`.",
        "- En iyi andan stopa kaç mum geçti: " + "; ".join(f"{r['aralik']} `{_ny(r['n'], r['pay'])}`" for r in gv["tepe_stop_arasi"]) + f". Medyan `{_g(gv['tepe_stop_medyan'], 0)}` mum.",
        "- Hedefe ne kadar yaklaşmışlardı: "
        + "; ".join(f"hedef yolunun en az %{100 * r['esik']:g} kadarı `{_ny(r['n'], r['pay'])}`" for r in gv["hedef_yolu"])
        + ".",
    ]

    # 8
    s += [
        "",
        "### 8. Stoptan önce uyarı var mıydı",
        "",
        "Stop, tez seviyesinin 0.5 ATR ötesindedir. Kapanışa bakan bir kural ancak stoptan önce seviyenin ters tarafında bir kapanış varsa devreye girebilir.",
        "",
        f"- Hiç kapanış görülmeden (ilk mumda) stop: `{_ny(uy['gozlemsiz_stop_n'], _pay(uy['gozlemsiz_stop_n'], uy['stop_n']))}`.",
        f"- Son kapanış hâlâ seviyenin doğru tarafındayken, tek mumda seviyeyi ve tamponu geçip stop: "
        f"`{_ny(uy['seviye_disindan_tek_mumda_n'], _pay(uy['seviye_disindan_tek_mumda_n'], uy['stop_n']))}`.",
        f"- Son kapanış seviyenin ters tarafındayken stop: `{_ny(uy['son_kapanista_seviye_ici_n'], _pay(uy['son_kapanista_seviye_ici_n'], uy['stop_n']))}`. "
        f"(Stoptan önce herhangi bir kapanışta seviyenin ters tarafını gören: `{uy['seviye_ici_goren_n']}`.)",
        f"- Stop mumu başlarken fiyatın stopa uzaklığı: medyan `{_g(uy['stopa_mesafe_atr_medyan'], 2)} ATR`; "
        f"`{_ny(uy['stopa_mesafe_bir_atr_alti_n'], _pay(uy['stopa_mesafe_bir_atr_alti_n'], uy['stop_n']))}` stopta 1 ATR ya da daha az, "
        f"`{_ny(uy['stopa_mesafe_yarim_atr_alti_n'], _pay(uy['stopa_mesafe_yarim_atr_alti_n'], uy['stop_n']))}` stopta 0.5 ATR ya da daha az. "
        "Yani stopların çoğu için sıradan büyüklükte tek bir ters mum yetti.",
        f"- Stop mumundan önceki son kapanışta işlemin açık sonucu: medyan `{_f(uy['son_kapanis_r_medyan'], 2)} R`; kârda olan "
        f"`{_ny(uy['son_kapanista_karda_n'], _pay(uy['son_kapanista_karda_n'], uy['stop_n']))}`, en az `+{ESIK_KAR:g} R` kârda olan "
        f"`{_ny(uy['son_kapanista_yarim_r_karda_n'], _pay(uy['son_kapanista_yarim_r_karda_n'], uy['stop_n']))}` "
        "(ilk mumda stop olanlar için giriş anı, yani 0 R).",
        "",
        "| Stoptan önceki son tez durumu | Stop | Stopların payı | Aynı durumdan hedefe giden |",
        "|---|---:|---:|---:|",
    ]
    for r in uy["tez_son"]:
        s.append(f"| {r['ad']} | {r['stop_n']} | {_yz(r['stop_pay'])} | {r['hedef_n']} |")
    s += [
        "",
        f"İşlem açıkken en az bir kapanışta görülen etiketler — en az bir kapanış görmüş `{uy['gozlemli_stop_n']}` stop ve `{uy['gozlemli_kazanan_n']}` kazanan:",
        "",
        "| Görülen | Stop olanlarda | Kâr edenlerde |",
        "|---|---:|---:|",
    ]
    for r in uy["etiketler"]:
        s.append(f"| {r['ad']} | {_ny(r['stop_n'], r['stop_pay'])} | {_ny(r['kazanan_n'], r['kazanan_pay'])} |")
    s += [
        "",
        "Bu tablo sonuç-koşulludur: stopa giden yol zaten zarardan ve çoğu kez seviyenin içinden geçer. Bir etiketin stop olanlarda sık "
        "görülmesi, o etikette çıkmanın kazandırdığını göstermez; onu `surec_olcum/RAPOR.md` ölçer.",
    ]

    # 9
    s += [
        "",
        "### 9. Stop olduktan sonra fiyat ne yaptı",
        "",
        "İşlemin özgün ufku (10 mum) bitene kadar, stop mumundan SONRAKİ mumlara bakılır. Stop mumunun kendi içindeki dönüş sayılmaz.",
        "",
        f"| Stoptan sonra | Tüm stoplar ({ss['n']}) | İlk mumda stop ({ss['ilk_mum']['n']}) | +{ESIK_KAR:g} R görmeden stop ({ss['kar_gormeden']['n']}) | +{ESIK_KAR:g} R görüp stop ({ss['geri_veren']['n']}) |",
        "|---|---:|---:|---:|---:|",
    ]
    for i, r in enumerate(ss["tumu"]):
        a, b, c = ss["ilk_mum"]["dagilim"][i], ss["kar_gormeden"]["dagilim"][i], ss["geri_veren"]["dagilim"][i]
        s.append(f"| {r['ad']} | {_ny(r['n'], r['pay'])} | {_ny(a['n'], a['pay'])} | {_ny(b['n'], b['pay'])} | {_ny(c['n'], c['pay'])} |")

    # 10
    s += [
        "",
        "### 10. Stop olmadan kapananlar (süre doldu)",
        "",
        f"- İşlem: `{_ny(su['n'], su['islem_payi'])}`; toplam net `{_f(su['net_toplam'], 1)} R`.",
        f"- Kârda kapanan `{su['kar_n']}` (ortalama `{_f(su['kar_ort_net'])} R`); zararda kapanan `{su['zarar_n']}` (ortalama `{_f(su['zarar_ort_net'])} R`).",
        f"- Zararda kapananların `{su['zararda_yarim_r_gormus_n']}` kadarı yol boyunca en az `+{ESIK_KAR:g} R`, `{su['zararda_bir_r_gormus_n']}` kadarı en az "
        f"`+{ESIK_BIR_R:g} R` görmüştü; `{su['zararda_brut_arti_n']}` kadarı brütte artıdaydı, masraf zarara çevirdi.",
        f"- Kârda kapananlar hedef yolunun medyan `%{100 * (su['karda_hedef_yolu_medyan'] or 0):.0f}` kadarını görmüştü; "
        f"`{su['karda_yarim_r_aleyhte_gormus_n']}` kadarı yol boyunca en az `0.5 R` aleyhte kalmıştı.",
        f"- İki yöne de `0.5 R` oynamadan süresi dolan: `{su['yarim_r_oynamayan_n']}`.",
    ]

    # 11
    s += [
        "",
        "### 11. Zora girip kurtaranlar",
        "",
        "İşlem aleyhte şu kadar R gördükten sonra nasıl bitti? (Çıkış mumunun geri kalanı sayılmaz; stop olan her işlem tanım gereği 1 R görür.)",
        "",
        "| Aleyhte en az | Gören işlem | Stop oldu | Kârla kapandı | Bunlardan hedefe giden | Stop olmadan zararda kapandı |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in v["kurtaran"]:
        s.append(
            f"| {r['esik']:g} R | {r['goren_n']} | {_ny(r['stop_n'], r['stop_pay'])} | {_ny(r['kar_n'], r['kar_pay'])} | {r['hedef_n']} | {r['stopsuz_zarar_n']} |"
        )

    # 12
    s += [
        "",
        "### 12. Kâr edenler nasıl kazandı",
        "",
        f"- Kâr eden `{kz['kar_n']}` işlemin `{kz['hedef_n']}` kadarı hedefe ulaştı (ortalama `{_f(kz['hedef_ort_net'])} R`; hedef ortalama `{_g(kz['hedef_r_ort'], 2)} R` uzaktaydı), "
        f"`{kz['sure_karda_n']}` kadarı süre dolunca kârda kapandı (ortalama `{_f(kz['sure_karda_ort_net'])} R`).",
        "- Hedefe kaçıncı mumda ulaşıldı: " + "; ".join(f"{r['aralik']} `{_ny(r['n'], r['pay'])}`" for r in kz["bar"]) + f". Medyan `{_g(kz['bar_medyan'], 0)}`. mum.",
        "- Hedefe ulaşanların hedeften önce aleyhte gördüğü: " + "; ".join(f"≥ {r['esik']:g} R `{_ny(r['n'], r['pay'])}`" for r in kz["once_aleyhte"]) + ".",
    ]

    # 13
    s += [
        "",
        "### 13. Piyasa işlem açıkken ne yaptı",
        "",
        f"`{ENDEKS}`, giriş anından çıkış mumunun kapanışına kadar, işlemin YÖNÜNE göre (short işlemde endeksin düşmesi lehtedir). "
        f"`±%{py['esik_yuzde']:g}` içi yatay sayılır. Endeks sembollerinin kendi işlemleri ölçülmez. Bu, giriş anında BİLİNMEYEN bir büyüklüktür.",
        "",
        "| Çıkış | Ölçülen işlem | Endeks ters | Endeks yatay | Endeks lehte | Endeksin ortalama hareketi |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for ad, anahtar in (("Stop oldu", "stop"), ("Hedefe ulaştı", "hedef"), ("Süre doldu", "sure")):
        r = py[anahtar]
        s.append(
            f"| {ad} | {r['olculen_n']} | {_ny(r['ters_n'], r['ters_pay'])} | {_ny(r['yatay_n'], r['yatay_pay'])} | {_ny(r['lehte_n'], r['lehte_pay'])} | {_f(r['ort_yuzde'], 2)}% |"
        )
    s += ["", "İşlem süresince endeksin hareketine göre:", ""] + _kosul_md(ks["endeks_islem"], "İşlem süresince endeks")
    s += ["", "Girişten ÖNCEKİ 5 mumda endeksin hareketine göre (giriş anında bilinir):", ""] + _kosul_md(ks["endeks_on"], "Girişten önce endeks")

    # 14
    s += [
        "",
        "### 14. Zarar hangi giriş koşullarında yoğunlaşıyor",
        "",
        "`En kötü GA`: net R ortalamasının sembol / gün / hafta / ay kümeli %95 aralıklarının en düşük alt ve en yüksek üst sınırı. "
        "Bu tablolar ilişki gösterir; çok sayıda kesit olduğu için tek bir satır kural gerekçesi değildir.",
        "",
        "**Stop mesafesi** (giriş ile stop arası; kırılım mumunun seviyeden ne kadar uzakta kapandığı + 0.5 ATR tampon). "
        "Hedef sabit `2.0 ATR` olduğu için dar stopta hedef R olarak uzak, geniş stopta yakındır:",
        "",
        f"- Stop mesafesi `{dg['esik_atr']:g} ATR` ya da daha yakın `{dg['dar']['n']}` işlem: stop `{_yz(dg['dar']['stop_pay'])}`, ilk mumda stop "
        f"`{_yz(dg['dar']['ilk_mum_stop_pay'])}`, kâr eden `{_yz(dg['dar']['kar_pay'])}`, net `{_f(dg['dar']['net_ort'])} R` "
        f"(hedef ortalama `{_g(dg['dar']['hedef_r_ort'], 2)} R` uzakta, masraf `{_g(dg['dar']['masraf_ort'])} R`).",
        f"- Daha geniş stoplu `{dg['genis']['n']}` işlem: stop `{_yz(dg['genis']['stop_pay'])}`, ilk mumda stop `{_yz(dg['genis']['ilk_mum_stop_pay'])}`, "
        f"kâr eden `{_yz(dg['genis']['kar_pay'])}`, net `{_f(dg['genis']['net_ort'])} R` "
        f"(hedef ortalama `{_g(dg['genis']['hedef_r_ort'], 2)} R` uzakta, masraf `{_g(dg['genis']['masraf_ort'])} R`).",
        "",
    ] + _kosul_md(ks["stop_mesafesi"], "Stop mesafesi")
    s += ["", "**Dönem / yön:**", ""] + _kosul_md(ks["yon_donem"], "Dönem / yön", donem=False)
    s += ["", "**Zaman dilimi ve olay mumunun kapanış saati:**", ""] + _kosul_md(ks["giris"], "Giriş")
    s += [
        "",
        "**Aynı gün, aynı yönde, bu işlemin girişine kadar açılmış birincil işlem sayısı** (kendisi dahil; `4h + 1d` birincil işlemler içinde):",
        "",
    ] + _kosul_md(ks["kalabalik"], "Aynı gün aynı yön")
    s += ["", "**Formasyon tipi** (en az 30 işlem):", ""] + _kosul_md(ks["formasyon"], "Formasyon")

    # 15
    s += [
        "",
        "### 15. Sonuç haftalara ne kadar yığılmış",
        "",
        "İşlemler açıldıkları takvim haftasına göre toplanır.",
        "",
        f"- Hafta: `{hf['hafta_n']}`; net artıda biten `{hf['arti_hafta_n']}` (toplam `{_f(hf['arti_toplam'], 1)} R`), "
        f"ekside biten `{hf['eksi_hafta_n']}` (toplam `{_f(hf['eksi_toplam'], 1)} R`).",
        f"- En iyi `{hf['uc_n']}` hafta toplam `{_f(hf['en_iyi_toplam'], 1)} R`; bütün işlemlerin neti `{_f(hf['net_toplam'], 1)} R`. "
        f"Bu `{hf['uc_n']}` hafta çıkarılınca kalan `{_f(hf['en_iyi_haric_net'], 1)} R`.",
        f"- En kötü `{hf['uc_n']}` hafta toplam `{_f(hf['en_kotu_toplam'], 1)} R`; bunlar çıkarılınca kalan `{_f(hf['en_kotu_haric_net'], 1)} R`.",
        f"- Bütün işlemleri aynı yönde olan hafta: `{hf['tek_yonlu_hafta_n']}` (bu haftalardaki işlem: `{hf['tek_yonlu_haftalardaki_islem_n']}`).",
        "",
        "| Hafta | İşlem | Long / short | Stop | Toplam net R |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in hf["en_iyi"] + hf["en_kotu"][::-1]:
        s.append(f"| {r['hafta']} | {r['n']} | {r['long_n']} / {r['short_n']} | {r['stop_n']} | {_f(r['net_toplam'], 1)} |")
    s += ["", f"Tablo en iyi `{hf['uc_n']}` ve en kötü `{hf['uc_n']}` haftayı gösterir."]
    return s


def _markdown(ozet: dict[str, Any]) -> str:
    m = ozet["meta"]
    sd = m["saatlik_durum"]
    ana = m["ana_rapor_esitligi"]
    ilk = next(iter(ozet["kumeler"]))
    s: list[str] = [
        "# Gölge v2 — Sonuç Anatomisi: Kim Kazandı, Kim Kaybetti, Nasıl Kaybetti",
        "",
        "> Üretici: `python -m research.golge_v2_sonuc_anatomisi`. Bu dosya elle düzenlenmez.",
        "",
        f"- Kapsam: `4h + 1d` birincil işlemler (sansürsüz, veri karantinası dışı), Mod 0, `{HEDEF_ATR:.1f} ATR` hedef, 10 mum ufuk, `30 bps` masraf. "
        f"İşlem: `{m['islem_n']}`.",
        "- Yarış yeniden koşulmadı: sonuçlar ana CSV'den okundu, yol fiyat arşivinden çözüldü. Arşivden yürütülen yol "
        f"`{m['yol_csv_ile_ayni_n']}` işlemin hepsinde CSV'deki çıkış nedeni, çıkış mumu ve MFE ile aynı; stop sonrası alanlar CSV'nin "
        "ufuk kapanışı ve 10 mumluk saf yol MFE'siyle tutarlı.",
        "- Ana raporla eşitlik (N ve net ortalama): "
        + (
            "; ".join(f"{KUME_KISA[a]} `{v['n']}` / `{_f(v['net_ort'], 4)} R`" for a, v in ana["kumeler"].items()) + " — aynı."
            if ana["durum"] == "karsilastirildi"
            else "`ozet_rapor.json` bulunamadı, karşılaştırılmadı."
        ),
        "- Saat çözünürlüğü: "
        + "; ".join(f"`{tf}` " + ", ".join(f"{a} `{b}`" for a, b in sorted(sd[tf].items())) for tf in m["tfs"])
        + ". `AYNI`: saatlik yol aynı mumda aynı sonucu veriyor. `ONCE_HEDEF`: aynı mumda saatlik veride önce hedef görülüyor. "
        "`VERI_YOK`: o tarihlerde saatlik arşiv yok. `TUTARSIZ`: günlük ve saatlik arşiv uyuşmuyor. `KAPSAM_DISI`: tez iptaliyle kapanan işlem "
        "(yapı kararı; fiyat yolundan türetilemez). Saatlik tablolara yalnız `AYNI` girer.",
        "",
        "**Okuma kılavuzu.** `R`: işlemin başlangıç riski (giriş ile stop arası). `Net`: 30 bps masraf düşülmüş. `Mum`: işlemin kendi zaman dilimindeki "
        "mum (4s işlemde 4 saatlik, günlükte günlük). Mum çözünürlüğünde stop mumunun içindeki sıra bilinmez; o yüzden \"stoptan önce görülen kâr\" stop "
        "mumunu saymaz ve alt sınırdır. Saat çözünürlüğü stop mumunun içini saat saat açar; stop saatinin kendi içi yine bilinmez.",
        "",
        "**Sınırlar.** Bu rapor betimleyicidir: olanı sayar, bir kuralın değerini ölçmez. \"Stopların şu kadarı önce kâr gördü\" stopu taşımanın "
        "kazandırdığı anlamına gelmez (ölçümü: `../surec_olcum/RAPOR.md`). Piyasa tablosu işlem bittikten sonra bilinen bir büyüklüğe bakar. "
        "Giriş koşulu tabloları ilişki gösterir; çok sayıda kesit sınandı ve çoklu karşılaştırma düzeltmesi yok. Kümeler iç içedir (D7 ⊂ D6 ⊂ D1).",
        "",
        f"## Kısa özet ({KUME_KISA[ilk]})",
        "",
    ]
    s += _kisa_ozet_md(ozet["kumeler"][ilk])
    s += ["", "## Üç kümede aynı oranlar", ""] + _karsilastirma_md(ozet)
    for ad, v in ozet["kumeler"].items():
        s += ["", f"## {ad} — {v['genel']['n']} işlem", ""] + _kume_md(v)
    return "\n".join(s) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gölge v2 sonuç anatomisi")
    ap.add_argument("--girdi", type=Path, default=VARSAYILAN_GIRDI, help="mod0_baz.csv.gz dosyasının bulunduğu dizin")
    ap.add_argument("--cikti", type=Path, default=None, help="varsayılan: <girdi>/sonuc_anatomisi")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args(argv)
    cikti = args.cikti or (args.girdi / "sonuc_anatomisi")
    df = anatomiyi_cikar(islemleri_yukle(args.girdi), workers=args.workers)
    ozet = ozet_uret(df, args.girdi)
    cikti.mkdir(parents=True, exist_ok=True)
    df.to_csv(cikti / "islemler.csv.gz", index=False)
    (cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    (cikti / "RAPOR.md").write_text(_markdown(ozet), encoding="utf-8")
    g = ozet["kumeler"]["D7_A_Arti"]["genel"]
    print(f"Tamamlandi -> {cikti} | islem={len(df)} | D7: kar={g['kar_n']} zarar={g['zarar_n']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
