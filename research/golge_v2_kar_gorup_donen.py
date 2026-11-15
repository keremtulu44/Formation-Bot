"""Gölge v2 — kâr görüp dönenler: 0.5 / 1 ATR gördükten sonra stop olan işlemlerin domain dökümü.

Soru: stoptan önce en az 0.5 ATR (ve 1 ATR) kâr görmüş işlemler neden döndü?

Üç ayrı okuma verilir; birbirine karıştırılmamalıdır:

1. EŞİK ANI (ileriye dönük, adil). İşlemin 0.5 / 1 ATR'yi ilk gördüğü mumun KAPANIŞINDA domainler
   ne gösteriyordu ve sonrasında ne oldu? O an sonuç bilinmez; aynı eşiği görüp hedefe giden
   işlemler doğal kontrol grubudur. Bir gözlem ancak burada stop oranını ayırıyorsa "döneceğini
   önceden söylüyor" denebilir. Her gözlem için ayrıca "o kapanışta karar verip sonraki açılışta
   çıkılsaydı" karşı-olgusu hesaplanır: stop oranını ayırmak, ona göre çıkmanın kazandırdığı
   anlamına gelmez (aynı gözlemi görüp hedefe gidenlerin kârı da kesilir).
2. EŞİKTEN SONRA (yarı adil). Eşik mumundan çıkışa kadar görülen olaylar; stop olanlarla hedefe
   gidenler yan yana. Uzun yaşayan işlem hem daha çok olay görür hem daha sık stop olur; bu
   tablo olayları olduğundan kötü gösterir.
3. TEPEDEN STOPA (geriye dönük, betimleyici). Stop olanlarda tepe mumunda ve tepe ile stop arasında
   ne görüldü; her işleme sabit öncelikle TEK bir "birincil gözlem" atanır. Bu bir neden-sonuç
   kanıtı değildir: aynı gözlem hedefe gidenlerde de bulunabilir (1 ve 2 bunu gösterir).

Ölçüler ATR cinsindendir (giriş anındaki ATR; hedef 2 ATR). "Tepe" ve "eşik" çıkış mumundan ÖNCEKİ
mumlardan okunur: stop mumunun içinde önce yükselip sonra düşen işlem görünmez (alt sınır).
Engel seviyeleri her zaman ilgili mumdan ÖNCEKİ kapanışta bilinen seviyelerdir.

Eşikler, birincil gözlem sırası ve eşik anı gözlemlerinin 20'si ölçümden önce sabitlendi. İlk
koşudan sonra domain kapsamını tamamlamak için 4 gözlem (`SONRADAN_EKLENEN`) ve çıkış karşı-olgusu
eklendi; raporda † ile işaretlidir. Bundan sonra gözlem ya da eşik eklemek ölçümü geçersiz kılar.
Çoklu karşılaştırma düzeltmesi yapılmaz; tek tek satırlar değil, keşif / doğrulama tutarlılığı ve
kümeler arası tekrar okunmalıdır.

İşlemler `research/golge_v2_sonuc_anatomisi.py` ile aynıdır; yarış yeniden koşulmaz, yalnız
domain serileri yeniden kurulur (2 işçiyle yaklaşık 4 dk).

Kullanım::

    python -m research.golge_v2_kar_gorup_donen [--girdi D] [--cikti D] [--workers 2]
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from research import golge_v2_endeks_filtresi as ef
from research import golge_v2_sonuc_anatomisi as sa
from senaryo_v2.adaptor import hazirla_gunluk_baglam, seriyi_hazirla
from senaryo_v2.modeller import BLOK_MIN_HEIGHT_ATR, VP_MAX_TERS_BASINC, VP_MIN_RVOL, BarDurum
from senaryo_v2.rapor import surec_izini_coz

NET = sa.NET
MIN_N: int = 30
B_ARALIK: int = 400
TOHUM: int = 20261114
ESIKLER: dict[str, float] = {"yarim": ef.ESIK_YARIM_ATR, "bir": ef.ESIK_BIR_ATR}
ESIK_AD: dict[str, str] = {"yarim": "0.5 ATR", "bir": "1 ATR"}
YAKIN_ATR: float = 0.25            # tepe bir seviyeye bu kadar yaklaşıp değmediyse "dibinde kaldı"
ENGEL_ONDE_ATR: float = 0.5        # kapanışın önünde bu kadar yakında engel varsa "önü kapalı"
ENDEKS_ESIK: float = sa.ENDEKS_ESIK_YUZDE
RVOL_YUKSEK: float = 2.0
DAR_STOP_ATR: float = 1.0
ZAYIF_SONUC = frozenset({"VERY_HIGH_EFFORT_WEAK_RESULT", "HIGH_EFFORT_WEAK_RESULT"})
# Süreç sözlüğünün (`senaryo_v2.surec.OLAY_KUTBU`) aleyhte saydığı formasyon etiketleri.
FRM_BOZULMA = frozenset({"FRM_RETEST", "FRM_BASARISIZ", "FRM_KARSI_KIRILIM", "FRM_TEYITSIZ"})
ALANLAR: tuple[str, ...] = ("stabil", "ms", "blok")
ALAN_AD: dict[str, str] = {"stabil": "Stabil", "ms": "Market Structure", "blok": "OB / FVG"}
_SIRA: dict[str, int] = {"": 0, "YAKIN": 1, "ASILDI": 2, "RED": 3}
SONUCLAR: tuple[tuple[str, str], ...] = (
    ("STOP", "Stop oldu"),
    ("HEDEF", "Hedefe gitti"),
    ("SURE_KAR", "Süre doldu, kârda"),
    ("SURE_ZARAR", "Süre doldu, zararda"),
    ("TEZ_IPTAL", "Tez iptali"),
)
# Eşik anı tablosuna ilk koşudan SONRA, domain kapsamını tamamlamak için eklenen gözlemler (raporda † ile işaretlenir).
SONRADAN_EKLENEN: frozenset[str] = frozenset({"BLOK_DISARIDAN", "BLOK_ICERIDE", "MS_SUPURME_TERS", "FRM_BOZUK"})
GOZLEM_N: int = 24                 # eşik anı tablosundaki gözlem sayısı (karşılaştırma tabanı `HER_ISLEM` hariç)
# Birincil gözlem önceliği (sabit, ön-kayıtlı). Son satır "hiçbiri"dir.
NEDENLER: tuple[tuple[str, str], ...] = (
    ("ENGEL", "Tepe mumu bilinen bir karşı seviyeye / banda değdi, kapanışla aşamadı"),
    ("ENGEL_YAKIN", f"Tepe, bilinen bir karşı seviyenin {YAKIN_ATR:g} ATR dibinde kaldı (değmedi)"),
    ("ENDEKS", f"Tepe kapanışından stop mumuna endeks işlemin tersine en az %{ENDEKS_ESIK:g} gitti"),
    ("YAPI", "Hissenin kendi yapısı bozuldu (ters BOS/CHoCH, tez seviyesinin içine kapanış ya da formasyon bozulması)"),
    ("HACIM", "Ters hacim baskısı ya da tepede yüksek çaba – zayıf sonuç"),
    ("BOSLUK", "Stop bir açılış boşluğuyla geldi"),
    ("ACIKLANAMAYAN", "Yukarıdakilerin hiçbiri görülmedi"),
)


# ---------------------------------------------------------------------------
# Engeller (saf)
# ---------------------------------------------------------------------------
def karsi_seviyeler(b: BarDurum, d: int) -> list[tuple[float, str]]:
    """Bar kapanışında bilinen karşı yön çizgi seviyeleri: (fiyat, alan).

    Kaynaklar `senaryo_v2.plan.karsit_yapisal_hedef` ile aynıdır; yalnız 0.35 ATR alt sınırı yoktur.
    """
    out: list[tuple[float, str]] = []
    if d == 1:
        if b.r_level is not None and b.r_validity in ("ACTIVE", "BREACHED"):
            out.append((float(b.r_level), "stabil"))
        tekil, diziler = (b.ms_weak_high, b.ms_protected_high), (b.ms_unbroken_highs, b.ms_down_broken_levels)
    else:
        if b.s_level is not None and b.s_validity in ("ACTIVE", "BREACHED"):
            out.append((float(b.s_level), "stabil"))
        tekil, diziler = (b.ms_weak_low, b.ms_protected_low), (b.ms_unbroken_lows, b.ms_up_broken_levels)
    out += [(float(x), "ms") for x in tekil if x is not None]
    out += [(float(x), "ms") for dizi in diziler for x in dizi]
    return out


def karsi_bantlar(b: BarDurum, d: int) -> list[tuple[float, float]]:
    """Karşı yönlü OB/FVG bantları: (işleme yakın kenar, uzak kenar). Çok ince bantlar sayılmaz."""
    bantlar = b.blok_bear if d == 1 else b.blok_bull
    gecerli = [z for z in bantlar if z.height_atr >= BLOK_MIN_HEIGHT_ATR]
    return [(float(z.lower), float(z.upper)) if d == 1 else (float(z.upper), float(z.lower)) for z in gecerli]


def onde_engel(b: BarDurum, d: int, fiyat: float, atr: float) -> dict[str, float | None]:
    """`fiyat`ın önündeki en yakın karşı engel, alan alan (ATR). Bandın içindeyse 0, yoksa `None`."""
    en_yakin: dict[str, float | None] = dict.fromkeys(ALANLAR)

    def isle(alan: str, uzaklik: float) -> None:
        if en_yakin[alan] is None or uzaklik < en_yakin[alan]:
            en_yakin[alan] = uzaklik

    for seviye, alan in karsi_seviyeler(b, d):
        uzaklik = d * (seviye - fiyat) / atr
        if uzaklik > 0:
            isle(alan, uzaklik)
    for yakin, uzak in karsi_bantlar(b, d):
        if d * (uzak - fiyat) > 0:                      # bant tamamen geride değil
            isle("blok", max(d * (yakin - fiyat) / atr, 0.0))
    return en_yakin


def mum_engel_durumu(onceki: BarDurum, b: BarDurum, d: int, atr: float) -> dict[str, str]:
    """Mum, ÖNCEKİ kapanışta bilinen karşı engelle ne yaptı? alan -> "RED" | "ASILDI" | "YAKIN" | "".

    RED: lehte ucu engele değdi, kapanış aşamadı. ASILDI: kapanış engelin ötesinde.
    YAKIN: değmedi ama `YAKIN_ATR` kadar yaklaştı. Bir alanda birden çok engel varsa RED önceliklidir.
    """
    uc = float(b.high if d == 1 else b.low)
    durum = dict.fromkeys(ALANLAR, "")

    def isle(alan: str, yeni: str) -> None:
        if _SIRA[yeni] > _SIRA[durum[alan]]:
            durum[alan] = yeni

    for seviye, alan in karsi_seviyeler(onceki, d):
        if d * (seviye - onceki.close) <= 0:            # seviye zaten geride
            continue
        if d * (uc - seviye) >= 0:
            isle(alan, "ASILDI" if d * (b.close - seviye) > 0 else "RED")
        elif d * (seviye - uc) <= YAKIN_ATR * atr:
            isle(alan, "YAKIN")
    for yakin, uzak in karsi_bantlar(onceki, d):
        if d * (uzak - onceki.close) <= 0:              # bant tamamen geride
            continue
        if d * (uc - yakin) >= 0:
            isle("blok", "ASILDI" if d * (b.close - uzak) >= 0 else "RED")
        elif d * (yakin - uc) <= YAKIN_ATR * atr:
            isle("blok", "YAKIN")
    return durum


def bant_temasi(onceki: BarDurum, b: BarDurum, d: int) -> tuple[bool, bool]:
    """Mumun aşamadığı karşı bantlar: (banda dışarıdan gelip takıldı, önceki kapanışta zaten bandın içindeydi).

    `mum_engel_durumu` ikisini de "RED" sayar (sistemin `BLOK_DUVAR` etiketi de öyledir). Bu ayrım
    "bandın kenarından döndü" ile "geniş bir karşı bandın içinde yaşıyor"u birbirinden ayırır.
    """
    uc = float(b.high if d == 1 else b.low)
    disaridan = iceride = False
    for yakin, uzak in karsi_bantlar(onceki, d):
        if d * (uzak - onceki.close) <= 0:                          # bant tamamen geride
            continue
        if d * (uc - yakin) < 0 or d * (b.close - uzak) >= 0:       # değmedi ya da kapanışla aştı
            continue
        if d * (yakin - onceki.close) > 0:
            disaridan = True
        else:
            iceride = True
    return disaridan, iceride


def formasyon_bozuk_mu(iz: dict[int, tuple[str, ...]], k: int) -> bool:
    """Süreç izine göre girişten sonraki `k`. kapanışta işlemin formasyonu bozulmuş durumda mı?

    İz yalnız durum GEÇİŞLERİNİ taşır; geçerli durum `k`'ye kadarki son formasyon etiketidir.
    Girişte zaten retest durumunda olan işlem (geçiş yok) bozulmuş sayılmaz.
    """
    son = ""
    for adim in sorted(iz):
        if adim > k:
            break
        for etiket in iz[adim]:
            if etiket.startswith("FRM_"):
                son = etiket
    return son in FRM_BOZULMA


def ters_yapi_kirilimi(b: BarDurum, d: int) -> tuple[bool, bool]:
    """Bu kapanışta işlemin tersine (dış, iç) BOS/CHoCH var mı?"""
    dis = ic = False
    for olay in b.ms_olaylar:
        kapsam, tip, yon = olay.split(":")
        if tip in ("BOS", "CHOCH") and int(yon) == -d:
            if kapsam == "EXT":
                dis = True
            else:
                ic = True
    return dis, ic


def ters_supurme(b: BarDurum, d: int) -> bool:
    """Bu kapanışta Market Structure motoru işlemin tersine süpürme (SWEEP) ya da sahte kırılım bildirdi mi?

    Long için: fiyat bir tepe seviyesinin üstüne çıkıp geri kapandı (ayı yönlü süpürme).
    """
    for olay in b.ms_olaylar:
        _, tip, yon = olay.split(":")
        if tip in ("SWEEP", "FALSE_BREAK") and int(yon) == -d:
            return True
    return False


# ---------------------------------------------------------------------------
# İşlem özellikleri
# ---------------------------------------------------------------------------
def _yuv(x: float | None) -> float | None:
    return None if x is None else round(float(x), 4)


def an_goruntusu(onceki: BarDurum, b: BarDurum, *, d: int, giris: float, atr: float, seviye: float | None) -> dict[str, Any]:
    """Bir mumun kapanışında bilinen domain durumu (işlemin yönüne göre)."""
    uc = float(b.high if d == 1 else b.low)
    aralik = float(b.high) - float(b.low)
    durum = mum_engel_durumu(onceki, b, d, atr)
    onde = [v for v in onde_engel(b, d, float(b.close), atr).values() if v is not None]
    vp = bool(b.vp_volume_usable)
    dis, ic = ters_yapi_kirilimi(b, d)
    bant_disaridan, bant_iceride = bant_temasi(onceki, b, d)
    return {
        "acik_atr": _yuv(d * (b.close - giris) / atr),
        "geri_verme_atr": _yuv(d * (uc - b.close) / atr),
        "fitil": bool(aralik > 0 and d * (uc - b.close) / aralik >= 0.5),
        **durum,
        "blok_disaridan": bant_disaridan,
        "blok_iceride": bant_iceride,
        "engel_onde_atr": _yuv(min(onde)) if onde else None,
        "rvol": _yuv(b.vp_rvol) if vp and b.vp_rvol is not None else None,
        "baski": _yuv(d * float(b.vp_pressure_5)) if vp and b.vp_pressure_5 is not None else None,
        "zayif_sonuc": bool(vp and b.vp_effort_result_class in ZAYIF_SONUC),
        "ms_dis": d * int(b.ms_ext_dir),
        "ms_ic": d * int(b.ms_int_dir),
        "seviye_ici": bool(seviye is not None and d * (b.close - seviye) < 0),
        "ters_ms": bool(dis or ic),
        "ters_supurme": ters_supurme(b, d),
    }


def pencere_olaylari(
    barlar: Sequence[BarDurum], i: int, ka: int, kb: int, *, d: int, atr: float, seviye: float | None, iz: dict[int, tuple[str, ...]]
) -> dict[str, bool]:
    """Girişten sonraki `ka..kb` kapanışlarında (uçlar dahil) görülen aleyhte olaylar."""
    out = {"engel_red": False, "ters_ms_dis": False, "ters_ms_ic": False, "ters_supurme": False, "seviye_ici": False}
    etiketler: set[str] = set()
    for k in range(ka, kb + 1):
        b = barlar[i + k]
        dis, ic = ters_yapi_kirilimi(b, d)
        out["ters_ms_dis"] |= dis
        out["ters_ms_ic"] |= ic
        out["ters_supurme"] |= ters_supurme(b, d)
        out["seviye_ici"] |= bool(seviye is not None and d * (b.close - seviye) < 0)
        out["engel_red"] |= "RED" in mum_engel_durumu(barlar[i + k - 1], b, d, atr).values()
        etiketler.update(iz.get(k, ()))
    out["frm_bozulma"] = bool(etiketler & FRM_BOZULMA)
    out["vp_ters"] = "VP_TERS_BASKI" in etiketler
    return out


def yol_esikleri(lehte_atr: Sequence[float]) -> tuple[float, int, dict[str, int | None]]:
    """Çıkış mumundan önceki mumların lehte uçlarından (ATR): (en iyi, tepe mumu, eşik mumları).

    `lehte_atr[0]` girişten sonraki ilk mumdur; mum sayaçları 1'den başlar. Tepe, en iyinin
    İLK görüldüğü mumdur; hiç lehte gitmediyse tepe mumu 0'dır.
    """
    mfe, k_tepe = 0.0, 0
    k_esik: dict[str, int | None] = dict.fromkeys(ESIKLER)
    for k, v in enumerate(lehte_atr, start=1):
        if v > mfe:
            mfe, k_tepe = float(v), k
        for ad, esik in ESIKLER.items():
            if k_esik[ad] is None and v >= esik:
                k_esik[ad] = k
    return mfe, k_tepe, k_esik


def islem_ozellikleri(r: dict[str, Any], barlar: Sequence[BarDurum], endeks: dict[str, np.ndarray] | None) -> dict[str, Any]:
    """Bir işlemin eşik anı, eşikten sonrası ve (stop ise) tepeden stopa domain dökümü."""
    oid = str(r["olay_id"])
    i = int(r["bar_index"])
    d = 1 if r["yon"] == "long" else -1
    giris, stop, atr = float(r["giris_gercek"]), float(r["stop"]), float(r["atr_tf"])
    b0 = barlar[i]
    if str(b0.bar_close_time) != str(r["bar_close_time"]) or abs(float(b0.close) - giris) > 1e-7:
        raise ValueError(f"{oid}: olay barı domain serisiyle hizalı değil")
    k_cikis = int(r["bar_20_intra_iptal"])
    seviye = None if pd.isna(r.get("zemin_tavan")) else float(r["zemin_tavan"])
    iz = dict(surec_izini_coz(r.get("surec_izi")))
    stop_mu = r["cikis_turu"] in ("STOP", "STOP_BOSLUK")
    risk_atr = abs(giris - stop) / atr
    ortak = {"d": d, "atr": atr, "seviye": seviye}

    def kapanis_ns(k: int) -> int:
        return int(pd.Timestamp(barlar[i + k].bar_close_time).value)

    def endeks_yuzde(ka: int, kb: int) -> float | None:
        if endeks is None:
            return None
        e0, e1 = sa._asof_kapanis(endeks, kapanis_ns(ka)), sa._asof_kapanis(endeks, kapanis_ns(kb))
        return _yuv(d * (e1 / e0 - 1.0) * 100.0) if e0 and e1 else None

    lehte = [d * (float(barlar[i + k].high if d == 1 else barlar[i + k].low) - giris) / atr for k in range(1, k_cikis)]
    mfe, k_tepe, k_esik = yol_esikleri(lehte)
    if stop_mu and abs(mfe - float(r["hedef_yolu_orani"]) * sa.HEDEF_ATR) > 3e-4:
        raise ValueError(f"{oid}: stop öncesi en iyi nokta sonuç anatomisiyle uyuşmuyor")

    kayit: dict[str, Any] = {"olay_id": oid, "yol_mfe_atr": _yuv(mfe), "k_tepe": k_tepe, "k_cikis": k_cikis, "risk_atr": _yuv(risk_atr)}
    for alan, uzaklik in onde_engel(b0, d, giris, atr).items():
        kayit[f"engel_giris_{alan}_atr"] = _yuv(uzaklik)
    for ad, k in k_esik.items():
        kayit[f"k_{ad}"] = k
        if k is None:
            continue
        an = an_goruntusu(barlar[i + k - 1], barlar[i + k], giris=giris, **ortak)
        an["endeks"] = endeks_yuzde(0, k)
        an["frm_bozuk"] = formasyon_bozuk_mu(iz, k)
        # Eşik mumu kapanışında karar verilip SONRAKİ açılışta çıkılsaydı (k < k_cikis olduğundan o mum vardır).
        an["sonraki_acilis_atr"] = _yuv(d * (float(barlar[i + k + 1].open) - giris) / atr)
        kayit.update({f"{a}_{ad}": v for a, v in an.items()})
        sonra = pencere_olaylari(barlar, i, k, k_cikis - 1, iz=iz, **ortak)
        kayit.update({f"sonra_{a}_{ad}": v for a, v in sonra.items()})
        kayit[f"sonra_endeks_{ad}"] = endeks_yuzde(k, k_cikis)
    if stop_mu and k_tepe >= 1:
        an = an_goruntusu(barlar[i + k_tepe - 1], barlar[i + k_tepe], giris=giris, **ortak)
        an["frm_bozuk"] = formasyon_bozuk_mu(iz, k_tepe)
        kayit.update({f"{a}_tepe": v for a, v in an.items()})
        ara = pencere_olaylari(barlar, i, k_tepe, k_cikis - 1, iz=iz, **ortak)
        kayit.update({f"ara_{a}": v for a, v in ara.items()})
        kayit["endeks_tepe_stop"] = endeks_yuzde(k_tepe, k_cikis)
        kayit["tepe_stop_mum"] = k_cikis - k_tepe
        kayit["donus_atr"] = _yuv(mfe + risk_atr)
        kayit["son_kapanis_atr"] = _yuv(d * (barlar[i + k_cikis - 1].close - giris) / atr)
        kayit["stop_mumu_ters_ms"] = any(ters_yapi_kirilimi(barlar[i + k_cikis], d))
    return kayit


def _sembol_isle(is_: tuple[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    sembol, satirlar = is_
    baglam = hazirla_gunluk_baglam(sembol)
    seriler: dict[str, Sequence[BarDurum]] = {}
    sonuc: list[dict[str, Any]] = []
    for r in satirlar:
        tf = str(r["tf"])
        if tf not in seriler:
            seri = seriyi_hazirla(sembol, tf, gunluk_baglam=baglam, bloklari_yukle=True)
            if seri.domain_hatali:
                raise RuntimeError(f"{sembol}/{tf}: domain serisi hatalı; ana koşuda bu seriden işlem çıkmamalıydı")
            seriler[tf] = seri.barlar
        endeks = None if sembol in (sa.ENDEKS, "XU30") else sa._endeks("1d" if tf == "1d" else "1h")
        sonuc.append(islem_ozellikleri(r, seriler[tf], endeks))
    return sonuc


def ozellik_tablosu(df: pd.DataFrame, *, workers: int = 2) -> pd.DataFrame:
    """Her işlem için domain özellikleri (işlem başına bir satır). Domain serilerini yeniden kurar."""
    isler = [(str(s), g.to_dict("records")) for s, g in df.groupby("sembol", sort=True)]
    if workers <= 1:
        parcalar = [_sembol_isle(x) for x in isler]
    else:
        with ProcessPoolExecutor(max_workers=workers) as havuz:
            parcalar = list(havuz.map(_sembol_isle, isler, chunksize=2))
    return pd.DataFrame([x for p in parcalar for x in p])


def ozellikleri_ekle(df: pd.DataFrame, ek: pd.DataFrame) -> pd.DataFrame:
    """Özellik tablosunu anatomi tablosuna bire bir bağlar (sıra korunur)."""
    if len(ek) != len(df) or ek["olay_id"].nunique() != len(df) or set(ek["olay_id"]) != set(df["olay_id"]):
        raise ValueError("Özellik satırları işlemlerle bire bir eşleşmiyor")
    cakisan = sorted((set(ek.columns) & set(df.columns)) - {"olay_id"})
    if cakisan:
        raise ValueError(f"Özellik kolonları anatomi kolonlarıyla çakışıyor: {cakisan}")
    return df.merge(ek, on="olay_id", how="left", validate="one_to_one")


# ---------------------------------------------------------------------------
# Özet
# ---------------------------------------------------------------------------
def _b(seri: pd.Series) -> pd.Series:
    """Bayrak kolonu: yalnız `True` olanlar (boş / bilinmeyen = hayır)."""
    return seri.eq(True)


def _pay(a: int | float, b: int | float) -> float | None:
    return round(float(a) / float(b), 6) if b else None


def hazirla(df: pd.DataFrame) -> pd.DataFrame:
    """Sonuç sınıfı, ATR'li stop grupları ve girişteki en yakın engel kolonlarını ekler; tutarlılığı denetler."""
    out = ef.stop_gruplarini_ekle(df)
    tur = out["cikis_turu"]
    stop = tur.isin(("STOP", "STOP_BOSLUK"))
    kar = _b(out["kar"])
    out["sonuc"] = np.select(
        [stop, tur == "HEDEF", (tur == "SURE") & kar, tur == "SURE"], ["STOP", "HEDEF", "SURE_KAR", "SURE_ZARAR"], default="TEZ_IPTAL"
    )
    for ad in ESIKLER:
        # Tek doğruluk kaynağı sonuç anatomisidir; mumdan okunan eşik onunla aynı grubu vermeli.
        if not ((out[f"k_{ad}"].notna() & stop) == out[f"{ad}_atr_stop"]).all():
            raise ValueError(f"{ESIK_AD[ad]} grubu sonuç anatomisiyle uyuşmuyor")
    engel = out[[f"engel_giris_{a}_atr" for a in ALANLAR]].astype(float)
    out["engel_giris_atr"] = engel.min(axis=1)
    for ad in ESIKLER:
        # Eşik mumunun kapanışında karar, sonraki açılışta çıkış: aynı masrafla net R ve gerçekleşenle farkı.
        erken = out[f"sonraki_acilis_atr_{ad}"].astype(float) / out["risk_atr"].astype(float) - out["masraf_r"].astype(float)
        out[f"erken_cikis_fark_{ad}"] = erken - out[NET].astype(float)
    return out


def _kume_kodlari(df: pd.DataFrame) -> dict[str, np.ndarray]:
    gun = df["bar_close_time"].astype(str).str[:10]
    iso = pd.to_datetime(gun).dt.isocalendar()
    return {
        "sembol": df["sembol"].to_numpy(),
        "gun": gun.to_numpy(),
        "hafta": (iso["year"].astype(str) + "-" + iso["week"].astype(str)).to_numpy(),
        "ay": gun.str[:7].to_numpy(),
    }


def fark_araligi(kodlar: dict[str, np.ndarray], f: np.ndarray, y: np.ndarray, *, B: int = B_ARALIK) -> tuple[float | None, float | None]:
    """`y` ortalamasının (özellik var − yok) farkı için en kötü %95 aralık: sembol/gün/hafta/ay kümeli."""
    f = np.asarray(f, dtype=float)
    y = np.asarray(y, dtype=float)
    altlar: list[float] = []
    ustler: list[float] = []
    for kod in kodlar.values():
        _, ters = np.unique(kod, return_inverse=True)
        m = int(ters.max()) + 1 if len(ters) else 0
        if m < 2:
            continue
        toplam = np.zeros((m, 4))
        for sutun, deger in enumerate((f, f * y, 1.0 - f, (1.0 - f) * y)):
            np.add.at(toplam[:, sutun], ters, deger)
        agirlik = np.random.default_rng(TOHUM).multinomial(m, np.full(m, 1.0 / m), size=B)
        t = agirlik @ toplam
        gecerli = (t[:, 0] > 0) & (t[:, 2] > 0)
        if gecerli.sum() < B // 2:
            continue
        fark = t[gecerli, 1] / t[gecerli, 0] - t[gecerli, 3] / t[gecerli, 2]
        alt, ust = np.percentile(fark, [2.5, 97.5])
        altlar.append(float(alt))
        ustler.append(float(ust))
    return (round(min(altlar), 6), round(max(ustler), 6)) if altlar else (None, None)


def cikis_karsi_olgusu(kume: pd.DataFrame, etkilenen: pd.Series, fark: pd.Series) -> dict[str, Any]:
    """Gözlemin görüldüğü işlemlerden sonraki açılışta çıkılsaydı kümenin işlem başına net R'si ne kadar değişirdi?

    `fark` = erken çıkışın net R'si − gerçekleşen net R. Gözlemin olmadığı işlemlerde değişim 0'dır.
    Kabul merdiveni `golge_v2_endeks_filtresi.filtre_karari` ile aynıdır.
    """
    e = etkilenen.reindex(kume.index).eq(True)
    fayda = fark.reindex(kume.index).astype(float).where(e, 0.0)
    if fayda.isna().any():
        raise ValueError("Erken çıkış farkı, gözlemin görüldüğü bir işlemde hesaplanamıyor")
    calisma = kume.assign(elenen=e, fayda=fayda)
    tumu = ef._fayda_ozeti(calisma)
    kesif = ef._fayda_ozeti(calisma[calisma["donem"] == "kesif"])
    dogrulama = ef._fayda_ozeti(calisma[calisma["donem"] == "dogrulama"])
    return {
        "etkilenen_n": int(e.sum()),
        "etkilenen_ort": round(float(fayda[e].mean()), 6) if e.any() else None,
        "kume_ort": tumu["fayda_ort"],
        "kume_toplam": tumu["fayda_toplam"],
        "en_kotu_alt": tumu["fayda_en_kotu_alt"],
        "en_kotu_ust": tumu["fayda_en_kotu_ust"],
        "kesif_ort": kesif["fayda_ort"],
        "dogrulama_ort": dogrulama["fayda_ort"],
        "karar": ef.filtre_karari(tumu, kesif, dogrulama),
    }


def ozellik_satiri(koh: pd.DataFrame, ad: str, aciklama: str, maske: pd.Series, bilinen: pd.Series | None = None) -> dict[str, Any]:
    """Kohortta bir gözlemin varlığına göre sonraki stop oranı ve aradaki farkın dayanıklılığı."""
    alt = koh if bilinen is None else koh[bilinen.reindex(koh.index).eq(True)]
    f = maske.reindex(alt.index).eq(True).to_numpy()
    y = (alt["sonuc"] == "STOP").to_numpy(dtype=float)
    hedef = (alt["sonuc"] == "HEDEF").to_numpy()
    net = alt[NET].to_numpy(dtype=float)
    n1, n0 = int(f.sum()), int((~f).sum())

    def fark(m: np.ndarray) -> float | None:
        return round(float(y[m & f].mean() - y[m & ~f].mean()), 6) if (m & f).any() and (m & ~f).any() else None

    tumu = np.ones(len(alt), dtype=bool)
    kesif, dogrulama = (alt["donem"] == "kesif").to_numpy(), (alt["donem"] == "dogrulama").to_numpy()
    fk, fd = fark(kesif), fark(dogrulama)
    yeterli = n1 >= MIN_N and n0 >= MIN_N
    ga_alt, ga_ust = fark_araligi(_kume_kodlari(alt), f, y) if yeterli else (None, None)
    if not yeterli:
        karar = "SAYILMAZ_N<30"
    elif fk is None or fd is None or fk * fd <= 0:
        karar = "AYIRMIYOR"
    elif ga_alt is not None and (ga_alt > 0 or ga_ust < 0):
        karar = "AYIRIYOR"
    else:
        karar = "ZAYIF"
    return {
        "ozellik": ad,
        "aciklama": aciklama,
        "bilinen_n": len(alt),
        "var_n": n1,
        "yok_n": n0,
        "var_stop_pay": _pay(y[f].sum(), n1),
        "yok_stop_pay": _pay(y[~f].sum(), n0),
        "fark": fark(tumu),
        "fark_alt": ga_alt,
        "fark_ust": ga_ust,
        "kesif_fark": fk,
        "dogrulama_fark": fd,
        "var_net": round(float(net[f].mean()), 6) if n1 else None,
        "yok_net": round(float(net[~f].mean()), 6) if n0 else None,
        "stoplarda_pay": _pay(f[y == 1].sum(), int((y == 1).sum())),
        "hedefte_pay": _pay(f[hedef].sum(), int(hedef.sum())),
        "karar": karar,
    }


def esik_ani_tablosu(k: pd.DataFrame, ad: str) -> list[dict[str, Any]]:
    """Eşik mumunun kapanışında bilinen gözlemler (ön-kayıtlı liste) ve o gözlemde çıkmanın karşı-olgusu.

    `k` bütün kümedir; kohort (eşiği çıkış mumundan önce görenler) içinden seçilir.
    """
    koh = k[k[f"k_{ad}"].notna()]

    def kol(ad_: str) -> pd.Series:
        return koh[f"{ad_}_{ad}"]

    durum = koh[[f"{a}_{ad}" for a in ALANLAR]]
    red = durum.eq("RED").any(axis=1)
    rvol, baski, endeks, onde = kol("rvol").astype(float), kol("baski").astype(float), kol("endeks").astype(float), kol("engel_onde_atr").astype(float)
    acik = kol("acik_atr").astype(float)
    rejim = koh["iliski_getiri_20"].astype(float)
    tanimlar: list[tuple[str, str, pd.Series, pd.Series | None]] = [
        ("HER_ISLEM", "Eşiği gören her işlem (karşılaştırma tabanı)", pd.Series(True, index=koh.index), None),
        ("ENGEL_RED", "Eşik mumu bilinen bir karşı engele değdi, kapanışla aşamadı", red, None),
        ("STABIL_RED", "… karşı Stabil seviyesine değip aşamadı", kol("stabil").eq("RED"), None),
        ("MS_RED", "… karşı Market Structure seviyesine değip aşamadı", kol("ms").eq("RED"), None),
        ("BLOK_RED", "… karşı OB / FVG bandına değip aşamadı", kol("blok").eq("RED"), None),
        ("BLOK_DISARIDAN", "… … banda dışarıdan gelip takıldı †", _b(kol("blok_disaridan")), None),
        ("BLOK_ICERIDE", "… … önceki kapanışta zaten bandın içindeydi, çıkamadı †", _b(kol("blok_iceride")) & ~_b(kol("blok_disaridan")), None),
        ("ENGEL_ASILDI", "Eşik mumu bir karşı engeli kapanışla aştı (takıldığı engel yok)", durum.eq("ASILDI").any(axis=1) & ~red, None),
        ("ENGEL_ONDE", f"Kapanışın önünde en çok {ENGEL_ONDE_ATR:g} ATR'de karşı engel var", onde <= ENGEL_ONDE_ATR, None),
        ("HEDEF_ONCESI_ENGEL", "Kapanış ile hedef arasında karşı engel var", onde < (sa.HEDEF_ATR - acik), None),
        ("ESIK_ALTI_KAPANIS", "Eşiği mum içinde gördü ama altında kapattı", acik < ESIKLER[ad], None),
        ("FITIL", "Mum, aralığının en az yarısını geri verip kapattı", _b(kol("fitil")), None),
        ("DUSUK_HACIM", f"Göreli hacim {VP_MIN_RVOL:g}'in altında", rvol < VP_MIN_RVOL, rvol.notna()),
        ("YUKSEK_HACIM", f"Göreli hacim en az {RVOL_YUKSEK:g}", rvol >= RVOL_YUKSEK, rvol.notna()),
        ("TERS_BASKI", f"Hacim baskısı işlemin tersine (< −{VP_MAX_TERS_BASINC:g})", baski < -VP_MAX_TERS_BASINC, baski.notna()),
        ("ZAYIF_SONUC", "Hacim sınıfı: yüksek çaba – zayıf sonuç", _b(kol("zayif_sonuc")), None),
        ("MS_SUPURME_TERS", "Market Structure motoru ters süpürme / sahte kırılım bildirdi †", _b(kol("ters_supurme")), None),
        ("MS_DIS_TERS", "Dış piyasa yapısı işlemin tersinde", kol("ms_dis") == -1, None),
        ("MS_IC_TERS", "İç piyasa yapısı işlemin tersinde", kol("ms_ic") == -1, None),
        ("SEVIYE_ICI", "Kapanış tez seviyesinin ters tarafında", _b(kol("seviye_ici")), None),
        ("FRM_BOZUK", "Formasyon girişten sonra aleyhte duruma geçti ve hâlâ orada (retest ediliyor / teyitsiz / başarısız / karşı kırılım) †", _b(kol("frm_bozuk")), None),
        ("ENDEKS_TERS", f"Girişten bu kapanışa endeks işlemin tersine en az %{ENDEKS_ESIK:g}", endeks <= -ENDEKS_ESIK, endeks.notna()),
        ("ILK_MUM", "Eşik, girişten sonraki ilk mumda görüldü", koh[f"k_{ad}"] == 1, None),
        ("DAR_STOP", f"Stop uzaklığı en çok {DAR_STOP_ATR:g} ATR", koh["risk_atr"].astype(float) <= DAR_STOP_ATR, None),
        ("REJIM_KARSI", "Girişte 20 günlük endeks rejimi işleme karşı", rejim == -1, rejim.notna()),
    ]
    if len(tanimlar) - 1 != GOZLEM_N or not SONRADAN_EKLENEN <= {a for a, *_ in tanimlar}:
        raise RuntimeError("Eşik anı gözlem listesi ile GOZLEM_N / SONRADAN_EKLENEN uyuşmuyor")
    satirlar = []
    for a, acik_, m, b in tanimlar:
        satir = ozellik_satiri(koh, a, acik_, m, b)
        var = m.eq(True) if b is None else (m.eq(True) & b.eq(True))
        satir["cikis"] = cikis_karsi_olgusu(k, var, k[f"erken_cikis_fark_{ad}"])
        satirlar.append(satir)
    return satirlar


def sonra_tablosu(koh: pd.DataFrame, ad: str) -> list[dict[str, Any]]:
    """Eşik mumundan (dahil) çıkıştan önceki son kapanışa kadar görülen aleyhte olaylar."""
    def kol(ad_: str) -> pd.Series:
        return _b(koh[f"sonra_{ad_}_{ad}"])

    endeks = koh[f"sonra_endeks_{ad}"].astype(float)
    yapi = kol("ters_ms_dis") | kol("ters_ms_ic") | kol("seviye_ici") | kol("frm_bozulma")
    tanimlar: list[tuple[str, str, pd.Series, pd.Series | None]] = [
        ("SONRA_ENGEL_RED", "Bir mum karşı engele değdi, kapanışla aşamadı", kol("engel_red"), None),
        ("SONRA_ENDEKS_TERS", f"Eşik kapanışından çıkış mumuna endeks işlemin tersine en az %{ENDEKS_ESIK:g}", endeks <= -ENDEKS_ESIK, endeks.notna()),
        ("SONRA_YAPI", "Yapı bozulması (aşağıdaki dördünden en az biri)", yapi, None),
        ("SONRA_TERS_MS_DIS", "… ters dış yapı kırılımı (BOS / CHoCH)", kol("ters_ms_dis"), None),
        ("SONRA_TERS_MS_IC", "… ters iç yapı kırılımı (BOS / CHoCH)", kol("ters_ms_ic"), None),
        ("SONRA_SEVIYE_ICI", "… tez seviyesinin ters tarafında kapanış", kol("seviye_ici"), None),
        ("SONRA_FRM_BOZULMA", "… formasyon bozulması (retest / teyitsiz / başarısız / karşı kırılım)", kol("frm_bozulma"), None),
        ("SONRA_SUPURME_TERS", "Market Structure motoru ters süpürme / sahte kırılım bildirdi", kol("ters_supurme"), None),
        ("SONRA_VP_TERS", "Ters hacim baskısı", kol("vp_ters"), None),
    ]
    return [ozellik_satiri(koh, a, acik_, m, b) for a, acik_, m, b in tanimlar]


def neden_bayraklari(g: pd.DataFrame) -> pd.DataFrame:
    """Stop olan işlemlerde tepe ve tepe–stop arası gözlemler (örtüşebilir)."""
    durum = g[[f"{a}_tepe" for a in ALANLAR]]
    red = durum.eq("RED").any(axis=1)
    return pd.DataFrame(
        {
            "ENGEL": red,
            "ENGEL_YAKIN": durum.eq("YAKIN").any(axis=1) & ~red,
            "ENDEKS": g["endeks_tepe_stop"].astype(float) <= -ENDEKS_ESIK,
            "YAPI": _b(g["ara_ters_ms_dis"]) | _b(g["ara_ters_ms_ic"]) | _b(g["ara_seviye_ici"]) | _b(g["ara_frm_bozulma"]),
            "HACIM": _b(g["ara_vp_ters"]) | _b(g["zayif_sonuc_tepe"]),
            "BOSLUK": g["cikis_turu"] == "STOP_BOSLUK",
        },
        index=g.index,
    )


def birincil_neden(bayraklar: pd.DataFrame) -> pd.Series:
    """Her işleme `NEDENLER` sırasındaki ilk geçerli gözlemi atar; hiçbiri yoksa ACIKLANAMAYAN."""
    sonuc = pd.Series("ACIKLANAMAYAN", index=bayraklar.index, dtype=object)
    for ad, _ in reversed(NEDENLER[:-1]):
        sonuc[bayraklar[ad].to_numpy(dtype=bool)] = ad
    return sonuc


def donus_ozeti(k: pd.DataFrame, ad: str) -> dict[str, Any]:
    """Stoptan önce eşiği görmüş stopların tepeden stopa dökümü."""
    g = k[k[f"{ad}_atr_stop"]]
    n = len(g)
    if not n:
        return {"n": 0}
    bay = neden_bayraklari(g)
    birincil = birincil_neden(bay)
    adet = bay.sum(axis=1)
    nedenler = []
    for neden, aciklama in NEDENLER:
        hicbiri = neden == "ACIKLANAMAYAN"
        gorulen = int((adet == 0).sum()) if hicbiri else int(bay[neden].sum())
        tek = gorulen if hicbiri else int((bay[neden] & (adet == 1)).sum())
        b_n = int((birincil == neden).sum())
        nedenler.append(
            {"neden": neden, "aciklama": aciklama, "gorulen_n": gorulen, "gorulen_pay": _pay(gorulen, n), "tek_basina_n": tek, "birincil_n": b_n, "birincil_pay": _pay(b_n, n)}
        )
    mum = g["tepe_stop_mum"].astype(int)
    rvol = g["rvol_tepe"].astype(float)
    donus = g["donus_atr"].astype(float)

    def say(maske: pd.Series) -> dict[str, Any]:
        return {"n": int(maske.sum()), "pay": _pay(int(maske.sum()), n)}

    return {
        "n": n,
        "kesif_n": int((g["donem"] == "kesif").sum()),
        "dogrulama_n": int((g["donem"] == "dogrulama").sum()),
        "long_n": int((g["yon"] == "long").sum()),
        "nedenler": nedenler,
        "iki_ve_fazla_gozlem": say(adet >= 2),
        "engel_alan": {a: say(g[f"{a}_tepe"].eq("RED")) for a in ALANLAR},
        "bant_disaridan": say(_b(g["blok_disaridan_tepe"])),
        "bant_yalniz_iceride": say(_b(g["blok_iceride_tepe"]) & ~_b(g["blok_disaridan_tepe"])),
        # ENGEL bayrağı yalnız "zaten içinde olunan bant" yüzünden yanan işlemler (çizgi seviyesi ve dışarıdan bant yok).
        "engel_yalniz_bant_ici": say(
            bay["ENGEL"] & ~g["stabil_tepe"].eq("RED") & ~g["ms_tepe"].eq("RED") & ~_b(g["blok_disaridan_tepe"])
        ),
        "ayrinti": {
            "tepe_fitil": say(_b(g["fitil_tepe"])),
            "tepe_zayif_sonuc": say(_b(g["zayif_sonuc_tepe"])),
            "tepe_dusuk_hacim": {"n": int((rvol < VP_MIN_RVOL).sum()), "pay": _pay(int((rvol < VP_MIN_RVOL).sum()), int(rvol.notna().sum()))},
            "tepe_frm_bozuk": say(_b(g["frm_bozuk_tepe"])),
            "tepe_ters_supurme": say(_b(g["ters_supurme_tepe"])),
            "ara_ters_supurme": say(_b(g["ara_ters_supurme"])),
            "ara_ters_ms_dis": say(_b(g["ara_ters_ms_dis"])),
            "ara_ters_ms_ic": say(_b(g["ara_ters_ms_ic"])),
            "ara_seviye_ici": say(_b(g["ara_seviye_ici"])),
            "ara_frm_bozulma": say(_b(g["ara_frm_bozulma"])),
            "ara_vp_ters": say(_b(g["ara_vp_ters"])),
            "stop_mumu_ters_ms": say(_b(g["stop_mumu_ters_ms"])),
            "son_kapanis_karda": say(g["son_kapanis_atr"].astype(float) > 0),
        },
        "tepe_stop_mum": {"1": say(mum == 1), "2": say(mum == 2), "3": say(mum == 3), "4+": say(mum >= 4), "medyan": float(mum.median())},
        "donus_atr_medyan": round(float(donus.median()), 4),
        "donus_1_5_alti": say(donus <= 1.5),
        "donus_2_ustu": say(donus > 2.0),
    }


def kohort_ozeti(k: pd.DataFrame, ad: str) -> dict[str, Any]:
    """Çıkış mumundan önce eşiği görmüş bütün işlemler ve sonraki akıbetleri."""
    koh = k[k[f"k_{ad}"].notna()]
    n = len(koh)
    return {
        "n": n,
        "kume_payi": _pay(n, len(k)),
        "net_ort": round(float(koh[NET].mean()), 6) if n else None,
        "sonuclar": [
            {
                "sonuc": s,
                "aciklama": aciklama,
                "n": int((koh["sonuc"] == s).sum()),
                "pay": _pay(int((koh["sonuc"] == s).sum()), n),
                "net_ort": round(float(koh.loc[koh["sonuc"] == s, NET].mean()), 6) if (koh["sonuc"] == s).any() else None,
            }
            for s, aciklama in SONUCLAR
        ],
        "esik_ani": esik_ani_tablosu(k, ad) if n else [],
        "sonra": sonra_tablosu(koh, ad) if n else [],
    }


ENGEL_KOVALARI: tuple[str, ...] = (
    "Engel 1 ATR'den yakın",
    "Engel 1–2 ATR arasında (hedeften önce)",
    "Hedefe kadar engel yok",
)


def giris_engeli_tablosu(k: pd.DataFrame) -> list[dict[str, Any]]:
    """Girişte bilinen en yakın karşı engelin uzaklığına göre işlemin akıbeti (bütün küme).

    Hiç karşı engeli bilinmeyen işlem "hedefe kadar engel yok" kovasındadır; kovalar kümeyi tam böler.
    """
    uzaklik = k["engel_giris_atr"].astype(float)
    maskeler = (uzaklik < 1.0, (uzaklik >= 1.0) & (uzaklik < sa.HEDEF_ATR), (uzaklik >= sa.HEDEF_ATR) | uzaklik.isna())
    return [ef._grup_satiri(ad, k[maske]) for ad, maske in zip(ENGEL_KOVALARI, maskeler)]


def kume_ozeti(k: pd.DataFrame) -> dict[str, Any]:
    stop = k["sonuc"] == "STOP"
    return {
        "n": len(k),
        "stop_n": int(stop.sum()),
        "dogrudan_stop_n": int(k["dogrudan_stop"].sum()),
        "esikler": {ad: {"kohort": kohort_ozeti(k, ad), "donus": donus_ozeti(k, ad)} for ad in ESIKLER},
        "giris_engeli": giris_engeli_tablosu(k),
    }


def ozet_uret(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "meta": {
            "islem_n": int(len(df)),
            "esikler_atr": ESIKLER,
            "yakin_atr": YAKIN_ATR,
            "engel_onde_atr": ENGEL_ONDE_ATR,
            "endeks_esik_yuzde": ENDEKS_ESIK,
            "min_n": MIN_N,
            "gozlem_n": GOZLEM_N,
            "sonradan_eklenen": sorted(SONRADAN_EKLENEN),
            "nedenler": [{"neden": a, "aciklama": b} for a, b in NEDENLER],
        },
        "kumeler": {ad: kume_ozeti(df[maske(df)]) for ad, maske in sa.KUMELER.items()},
    }


# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------
_f, _yz = sa._f, sa._yz


def _ny(x: dict[str, Any]) -> str:
    return f"{x['n']} ({_yz(x['pay'])})"


def _puan(x: Any) -> str:
    return "—" if x is None else f"{100.0 * float(x):+.1f}"


def _ozellik_md(satirlar: list[dict[str, Any]], *, karar: bool) -> list[str]:
    s = [
        "| Gözlem | Var (n) | Varken stop | Yokken stop | Fark (puan) | Fark en kötü GA | Keşif / doğrulama farkı | Stoplarda | Hedefe gidenlerde | Net R: var / yok |"
        + (" Karar |" if karar else ""),
        "|---|---:|---:|---:|---:|---|---:|---:|---:|---:|" + ("---|" if karar else ""),
    ]
    for r in satirlar:
        s.append(
            f"| {r['aciklama']} | {r['var_n']} / {r['bilinen_n']} | {_yz(r['var_stop_pay'])} | {_yz(r['yok_stop_pay'])} | {_puan(r['fark'])} | "
            f"[{_puan(r['fark_alt'])}, {_puan(r['fark_ust'])}] | {_puan(r['kesif_fark'])} / {_puan(r['dogrulama_fark'])} | {_yz(r['stoplarda_pay'])} | "
            f"{_yz(r['hedefte_pay'])} | {_f(r['var_net'])} / {_f(r['yok_net'])} |" + (f" **{r['karar']}** |" if karar else "")
        )
    return s


# Tepeden stopa gözleminin, eşikten sonra tablosundaki eşdeğeri (aynı tür olay, kontrol grubuyla birlikte).
KONTROL_ESLESMESI: dict[str, str] = {"ENGEL": "SONRA_ENGEL_RED", "ENDEKS": "SONRA_ENDEKS_TERS", "YAPI": "SONRA_YAPI", "HACIM": "SONRA_VP_TERS"}


def _kontrol(es: dict[str, Any] | None) -> str:
    return f"{_yz(es['var_stop_pay'])} / {_yz(es['yok_stop_pay'])}" if es else "—"


def _donus_md(dn: dict[str, Any], sonra: list[dict[str, Any]]) -> list[str]:
    if not dn.get("n"):
        return ["Bu grupta işlem yok."]
    a = dn["ayrinti"]
    kontrol = {r["ozellik"]: r for r in sonra}
    s = [
        f"`{dn['n']}` işlem (keşif `{dn['kesif_n']}`, doğrulama `{dn['dogrulama_n']}`; long `{dn['long_n']}`, short `{dn['n'] - dn['long_n']}`). "
        "\"Kontrol\" sütunu aynı tür olayın eşiği gören BÜTÜN işlemlerdeki karşılığıdır: olay eşikten sonra görülünce stop oranı / görülmeyince stop oranı. "
        "İki oran yakınsa o gözlem dönüşü açıklamaz.",
        "",
        "| Gözlem | Görüldüğü işlem | Yalnız bu görüldü | Birincil gözlem (toplam %100) | Kontrol: görülünce stop / görülmeyince stop |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in dn["nedenler"]:
        s.append(
            f"| {r['aciklama']} | {r['gorulen_n']} ({_yz(r['gorulen_pay'])}) | {r['tek_basina_n']} | **{r['birincil_n']} ({_yz(r['birincil_pay'])})** | "
            f"{_kontrol(kontrol.get(KONTROL_ESLESMESI.get(r['neden'], '')))} |"
        )
    s += [
        "",
        f"- İki ya da daha çok gözlemin birlikte görüldüğü işlem: `{_ny(dn['iki_ve_fazla_gozlem'])}`.",
        "- Tepe mumunun takıldığı engel, alan alan (bir işlem birden çok alanda sayılabilir): "
        + "; ".join(f"{ALAN_AD[al]} `{_ny(dn['engel_alan'][al])}`" for al in ALANLAR)
        + ".",
        f"- OB / FVG ayrımı: banda dışarıdan gelip takılan `{_ny(dn['bant_disaridan'])}`; önceki kapanışta zaten bandın içinde olup çıkamayan "
        f"`{_ny(dn['bant_yalniz_iceride'])}`. Engel gözlemi YALNIZ \"zaten içinde olunan bant\"tan gelen işlem: `{_ny(dn['engel_yalniz_bant_ici'])}`.",
        f"- Market Structure motorunun kendi olayı — ters süpürme / sahte kırılım: tepe mumunda `{_ny(a['tepe_ters_supurme'])}`; "
        f"tepe mumundan stop öncesi son kapanışa `{_ny(a['ara_ters_supurme'])}`.",
        f"- Yapı ayrıntısı (tepe mumundan stop öncesi son kapanışa): ters dış kırılım `{_ny(a['ara_ters_ms_dis'])}`; ters iç kırılım `{_ny(a['ara_ters_ms_ic'])}`; "
        f"tez seviyesinin içine kapanış `{_ny(a['ara_seviye_ici'])}`; formasyon bozulması `{_ny(a['ara_frm_bozulma'])}` "
        f"(tepe mumunun kapanışında formasyon zaten aleyhte durumda olan `{_ny(a['tepe_frm_bozuk'])}`).",
        f"- Hacim ayrıntısı: tepe ile stop arasında ters baskı `{_ny(a['ara_vp_ters'])}`; tepede yüksek çaba – zayıf sonuç `{_ny(a['tepe_zayif_sonuc'])}`; "
        f"tepe mumunda düşük göreli hacim `{_ny(a['tepe_dusuk_hacim'])}` (hacmi bilinenler içinde).",
        f"- Tepe mumu aralığının en az yarısını geri verip kapattı (fitil): `{_ny(a['tepe_fitil'])}`. Stop mumunun kendisinde ters yapı kırılımı: "
        f"`{_ny(a['stop_mumu_ters_ms'])}` (düşüşün sonucu, habercisi değil).",
        f"- Stoptan önceki son kapanışta işlem hâlâ kârdaydı: `{_ny(a['son_kapanis_karda'])}`.",
        f"- Tepeden stopa kaç mum: 1 mum `{_ny(dn['tepe_stop_mum']['1'])}`; 2 mum `{_ny(dn['tepe_stop_mum']['2'])}`; 3 mum `{_ny(dn['tepe_stop_mum']['3'])}`; "
        f"4+ mum `{_ny(dn['tepe_stop_mum']['4+'])}`; medyan `{dn['tepe_stop_mum']['medyan']:g}`.",
        f"- Tepeden stopa gereken geri çekilme: medyan `{dn['donus_atr_medyan']:.2f} ATR`; en çok 1.5 ATR olan `{_ny(dn['donus_1_5_alti'])}`; "
        f"2 ATR'den büyük olan `{_ny(dn['donus_2_ustu'])}`.",
    ]
    return s


def _cikis_md(satirlar: list[dict[str, Any]]) -> list[str]:
    s = [
        "| Gözlem | Görüldüğü işlem | Çıkılsaydı, etkilenen işlem başına R | Kümenin işlem başına R'si | En kötü GA | Keşif / doğrulama | Toplam R | Karar |",
        "|---|---:|---:|---:|---|---:|---:|---|",
    ]
    for r in satirlar:
        c = r["cikis"]
        s.append(
            f"| {r['aciklama']} | {c['etkilenen_n']} | {_f(c['etkilenen_ort'])} | {_f(c['kume_ort'], 4)} | [{_f(c['en_kotu_alt'], 4)}, {_f(c['en_kotu_ust'], 4)}] | "
            f"{_f(c['kesif_ort'], 4)} / {_f(c['dogrulama_ort'], 4)} | {_f(c['kume_toplam'], 1)} | **{c['karar']}** |"
        )
    return s


NEDEN_KISA: dict[str, str] = {
    "ENGEL": "bilinen engele takıldı",
    "ENGEL_YAKIN": "engelin dibinde kaldı",
    "ENDEKS": "endeks tersine döndü",
    "YAPI": "hissenin yapısı bozuldu",
    "HACIM": "ters hacim",
    "BOSLUK": "boşlukla stop",
    "ACIKLANAMAYAN": "hiçbiri",
}


def _kisa_ozet_md(ozet: dict[str, Any]) -> list[str]:
    ilk = next(iter(ozet["kumeler"]))
    v = ozet["kumeler"][ilk]
    s: list[str] = [
        f"- **{sa.KUME_KISA[ilk]}: {v['n']} işlemden {v['stop_n']} tanesi stop oldu.** Bunların `{v['dogrudan_stop_n']}` tanesi stoptan önce 0.5 ATR'yi hiç görmedi; "
        f"`{v['esikler']['yarim']['donus']['n']}` tanesi en az 0.5 ATR, `{v['esikler']['bir']['donus']['n']}` tanesi en az 1 ATR gördükten sonra döndü.",
    ]
    for ad in ESIKLER:
        ko, dn = v["esikler"][ad]["kohort"], v["esikler"][ad]["donus"]
        sn = {x["sonuc"]: x for x in ko["sonuclar"]}
        s.append(
            f"- **{ESIK_AD[ad]} görüp o mumun kapanışında hâlâ açık olan {ko['n']} işlemin akıbeti:** stop `{_ny(sn['STOP'])}`, hedef `{_ny(sn['HEDEF'])}`, "
            f"süre sonunda kârda `{_ny(sn['SURE_KAR'])}`, zararda `{_ny(sn['SURE_ZARAR'])}`; bu grubun ortalaması `{_f(ko['net_ort'])} R`."
        )
        if dn.get("n"):
            s.append(
                f"- **{ESIK_AD[ad]} görüp stop olan {dn['n']} işlemde tepeden stopa ne görüldü (bir işlemde birden çoğu olabilir):** "
                + "; ".join(f"{NEDEN_KISA[r['neden']]} `{r['gorulen_n']}` ({_yz(r['gorulen_pay'])})" for r in dn["nedenler"])
                + "."
            )
            kontrol = {r["ozellik"]: r for r in ko["sonra"]}
            s.append(
                f"- **Kontrol — aynı tür olay {ESIK_AD[ad]} gören bütün işlemlerde görülünce stop oranı / görülmeyince:** "
                + "; ".join(f"{NEDEN_KISA[neden]} `{_kontrol(kontrol[es])}`" for neden, es in KONTROL_ESLESMESI.items())
                + ". İki oran yakınsa o gözlem dönüşü açıklamaz; uzak olanlar da işlem sürerken ortaya çıkar, önceden bilinmez."
            )
        satir = {r["ozellik"]: r for r in ko["esik_ani"]}
        s.append(
            f"- **{ESIK_AD[ad]} görüldüğü kapanışta bilinen engele takılmış olmak sonradan stop olmayı ayırıyor mu:** "
            + "; ".join(
                f"{etiket} `{_yz(satir[oz]['var_stop_pay'])}` / yokken `{_yz(satir[oz]['yok_stop_pay'])}` → {satir[oz]['karar']}"
                for oz, etiket in (("ENGEL_RED", "herhangi bir engel"), ("STABIL_RED", "Stabil"), ("MS_RED", "Market Structure"), ("BLOK_RED", "OB / FVG"))
            )
            + "."
        )
        ayiran = [r for r in ko["esik_ani"] if r["karar"] == "AYIRIYOR"]
        s.append(
            f"- **{ESIK_AD[ad]} görüldüğü kapanışta, sonradan stop olacakları ayıran gözlem** (`{len(ko['esik_ani']) - 1}` gözlemden): "
            + ("; ".join(f"`{r['ozellik']}` (stop `{_yz(r['var_stop_pay'])}` / yokken `{_yz(r['yok_stop_pay'])}`)" for r in ayiran) if ayiran else "yok")
            + "."
        )
        gecen = [r for r in ko["esik_ani"] if r["cikis"]["karar"] in ("GECTI", "UMUT_VAR")]
        s.append(
            f"- **{ESIK_AD[ad]}: o gözlem görülünce sonraki açılışta çıkmak kabul merdiveninden geçiyor mu:** "
            + ("; ".join(f"`{r['ozellik']}` {r['cikis']['karar']} (`{_f(r['cikis']['kume_ort'], 4)} R/işlem`)" for r in gecen) if gecen else "hiçbiri geçmiyor")
            + "."
        )
    s += ["", "**Kümeler yan yana.** Yüzdeler \"görüldüğü işlem\" paylarıdır (örtüşür); son iki sütun eşik anı tablosundandır.", ""]
    s += [
        "| Küme | Eşik | Görüp stop olan | Engele takıldı | Endeks döndü | Yapı bozuldu | Ters hacim | Hiçbiri | Eşik anında ayıran gözlem | Geçen çıkış kuralı |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for kume, kv in ozet["kumeler"].items():
        for ad in ESIKLER:
            ko, dn = kv["esikler"][ad]["kohort"], kv["esikler"][ad]["donus"]
            if not dn.get("n"):
                continue
            g = {r["neden"]: r for r in dn["nedenler"]}
            s.append(
                f"| {sa.KUME_KISA[kume]} | {ESIK_AD[ad]} | {dn['n']} | "
                + " | ".join(_yz(g[x]["gorulen_pay"]) for x in ("ENGEL", "ENDEKS", "YAPI", "HACIM", "ACIKLANAMAYAN"))
                + f" | {sum(r['karar'] == 'AYIRIYOR' for r in ko['esik_ani'])} / {len(ko['esik_ani']) - 1} | "
                f"{sum(r['cikis']['karar'] in ('GECTI', 'UMUT_VAR') for r in ko['esik_ani'])} |"
            )
    return s


def _markdown(ozet: dict[str, Any]) -> str:
    m = ozet["meta"]
    s: list[str] = [
        "# Gölge v2 — Kâr Görüp Dönenler: 0.5 / 1 ATR Gördükten Sonra Stop Olan İşlemlerin Domain Dökümü",
        "",
        "> Üretici: `python -m research.golge_v2_kar_gorup_donen`. Bu dosya elle düzenlenmez.",
        "",
        f"- Kapsam: `4h + 1d` birincil işlemler (sansürsüz, veri karantinası dışı). İşlem: `{m['islem_n']}`. Sonuçlar ana CSV'den okunur; yalnız domain serileri yeniden kurulur.",
        "- Ölçü birimi ATR'dir (giriş anındaki ATR; hedef 2 ATR). \"0.5 ATR gördü\": çıkış mumundan ÖNCEKİ bir mumun lehte ucu girişten en az 0.5 ATR uzaklaştı. "
        "Stop mumunun içinde önce yükselip sonra düşen işlemler görünmez; sayılar alt sınırdır.",
        "",
        "**Üç okuma, üç ayrı güç.** (1) *Eşik anı*: eşiğin ilk görüldüğü mumun kapanışında bilinenler ve sonrasında olanlar; aynı eşiği görüp hedefe gidenler kontrol "
        "grubudur ve tek adil karşılaştırma budur. (2) *Eşikten sonra*: eşik mumundan çıkışa kadar görülen olaylar; uzun yaşayan işlem hem daha çok olay görür hem "
        "daha sık stop olur, bu yüzden olayları olduğundan kötü gösterir. (3) *Tepeden stopa*: yalnız stop olanlara geriye dönük bakış; ne görüldüğünü anlatır, "
        "neden olduğunu kanıtlamaz.",
        "",
        "**Çıkış karşı-olgusu.** Bir gözlem stop oranını ayırsa bile ona göre çıkmak kazandırmayabilir: aynı gözlemi görüp hedefe giden işlemlerin kârı da "
        "kesilir. Bu yüzden her gözlem için \"o kapanışta karar verip sonraki açılışta çıkılsaydı\" ayrıca ölçülür; ölçüt budur.",
        "",
        "**Terimler.** *Karşı engel*: işlemin gideceği yönde, mumdan ÖNCEKİ kapanışta bilinen seviye — Stabil karşı seviyesi, Market Structure tepe/dip seviyeleri "
        f"(korunan, zayıf, kırılmamış ve ters yönde kırılmış), yüksekliği en az `{BLOK_MIN_HEIGHT_ATR:g} ATR` olan karşı OB/FVG bandı. *Değdi, aşamadı*: mumun lehte ucu "
        f"engele ulaştı, kapanış ötesine geçemedi. *Dibinde kaldı*: değmedi ama `{m['yakin_atr']:g} ATR` kadar yaklaştı. *Tez seviyesi*: işlemin dayandığı kırılım "
        "seviyesi. *Formasyon bozulması*: süreç izinde sistemin aleyhte saydığı formasyon etiketleri (retest ediliyor, teyit alamadı, başarısız, karşı kırılım). "
        "*Birincil gözlem*: bir işlemde birden çok şey görüldüyse tabloda yukarıdan aşağı ilk sıradaki sayılır; sıra ölçümden önce sabitlenmiştir. "
        "Bu sıra bir önem sırası DEĞİLDİR; hangi gözlemin gerçekten ayırdığını \"Kontrol\" sütunu ve eşik anı tablosu gösterir.",
        "",
        f"**Karar etiketleri (eşik anı tablosu).** `AYIRIYOR`: gözlem varken ve yokken stop oranı farkı keşif ve doğrulamada aynı yönde ve sembol / gün / hafta / ay kümeli "
        f"%95 aralıkların en genişi sıfırı dışlıyor. `ZAYIF`: iki dönemde aynı yönde ama aralık sıfırı içeriyor. `AYIRMIYOR`: iki dönemde yön değiştiriyor. "
        f"`SAYILMAZ_N<30`: gözlemin olduğu ya da olmadığı grup `{m['min_n']}` işlemden az. Çoklu karşılaştırma düzeltmesi yoktur.",
        "",
        f"**Gözlem listesi.** Eşik anı tablosundaki gözlemlerin `{m['gozlem_n'] - len(m['sonradan_eklenen'])}` tanesi ölçümden önce sabitlendi. † işaretli "
        f"`{len(m['sonradan_eklenen'])}` gözlem ilk koşudan sonra domain kapsamını tamamlamak için eklendi (Market Structure süpürme olayı, OB / FVG'de dışarıdan / "
        "içeriden ayrımı, formasyon durumu); \"çıkılsaydı\" karşı-olgusu da ilk koşudan sonra eklendi. Hepsi sonucundan bağımsız raporlanır; † işaretli bir "
        "satırın tek başına ayırması, ön-kayıtlı bir satırınkinden daha zayıf kanıttır.",
        "",
        "## Kısa özet",
        "",
    ]
    s += _kisa_ozet_md(ozet)
    for kume, v in ozet["kumeler"].items():
        s += ["", f"## {kume} — {v['n']} işlem, {v['stop_n']} stop", ""]
        s += [
            f"Stopların `{v['dogrudan_stop_n']}` tanesi stoptan önce 0.5 ATR'yi hiç görmedi (doğrudan / çok az yükselip düşen); "
            f"`{v['esikler']['yarim']['donus']['n']}` tanesi en az 0.5 ATR gördü; bunların `{v['esikler']['bir']['donus']['n']}` tanesi en az 1 ATR gördü.",
            "",
            "### 1. Eşiği gören işlemlerin akıbeti",
            "",
            "\"Gören işlem\": eşiği çıkış mumundan ÖNCE gören, yani o mumun kapanışında hâlâ açık olan işlem. Eşiği ilk kez çıkış mumunda gören işlemler "
            "(örneğin tek mumda hedefe giden) burada yoktur; o an verilecek bir karar olmadığı için.",
            "",
        ]
        gosterilen = [(x, acik) for x, acik in SONUCLAR if any(sn["n"] for ad in ESIKLER for sn in v["esikler"][ad]["kohort"]["sonuclar"] if sn["sonuc"] == x)]
        s += [
            "| Eşik | Gören işlem | " + " | ".join(acik for _, acik in gosterilen) + " | Grubun net R'si |",
            "|---|---:|" + "---:|" * len(gosterilen) + "---:|",
        ]
        for ad in ESIKLER:
            ko = v["esikler"][ad]["kohort"]
            sn = {x["sonuc"]: x for x in ko["sonuclar"]}
            s.append(
                f"| {ESIK_AD[ad]} | {ko['n']} ({_yz(ko['kume_payi'])}) | "
                + " | ".join(_ny(sn[x]) for x, _ in gosterilen)
                + f" | {_f(ko['net_ort'])} |"
            )
        for sira, ad in enumerate(ESIKLER, start=2):
            s += ["", f"### {sira}. Tepeden stopa: {ESIK_AD[ad]} görüp stop olanlarda ne görüldü", ""] + _donus_md(
                v["esikler"][ad]["donus"], v["esikler"][ad]["kohort"]["sonra"]
            )
        for sira, ad in enumerate(ESIKLER, start=4):
            ko = v["esikler"][ad]["kohort"]
            s += [
                "",
                f"### {sira}. Eşik anı: {ESIK_AD[ad]} ilk görüldüğü mumun kapanışında domainler",
                "",
                f"`{ko['n']}` işlem. \"Varken stop\": gözlem o kapanışta varsa işlemin sonradan stop olma oranı.",
                "",
            ] + _ozellik_md(ko["esik_ani"][1:], karar=True)
            s += [
                "",
                f"**{ESIK_AD[ad]} — o gözlem görülünce çıkılsaydı.** Karar eşik mumunun kapanışında verilir, çıkış bir sonraki mumun açılışındadır; masraf aynıdır. "
                "\"Kümenin işlem başına R'si\": gözlemin olmadığı işlemler değişmeden kalır. Kabul merdiveni endeks filtresi raporundakiyle aynıdır.",
                "",
            ] + _cikis_md(ko["esik_ani"])
        for sira, ad in enumerate(ESIKLER, start=6):
            ko = v["esikler"][ad]["kohort"]
            s += [
                "",
                f"### {sira}. Eşikten sonra: {ESIK_AD[ad]} gördükten sonra çıkışa kadar görülen olaylar",
                "",
                "Uzun yaşayan işlem daha çok olay görür; bu tablo olayları olduğundan kötü gösterir. \"Stoplarda\" ve \"Hedefe gidenlerde\" sütunlarını birlikte okuyun.",
                "",
            ] + _ozellik_md(ko["sonra"], karar=False)
        s += [
            "",
            "### 8. Girişte hedef yolundaki engel (bütün küme)",
            "",
            "Girişte bilinen en yakın karşı engelin uzaklığı; hedef 2 ATR'dedir.",
            "",
        ] + ef._grup_md(v["giris_engeli"], "Girişte en yakın karşı engel")
    return "\n".join(s) + "\n"


CIKTI_KIMLIK_KOLONLARI: tuple[str, ...] = (
    "olay_id", "sembol", "tf", "yon", "donem", "kalite_katmani", "bar_close_time", NET, "cikis_turu", "sonuc",
    "stop_mfe_atr", "dogrudan_stop", "yarim_atr_stop", "bir_atr_stop", "iliski_getiri_20", "engel_giris_atr",
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gölge v2 kâr görüp dönenlerin domain dökümü")
    ap.add_argument("--girdi", type=Path, default=sa.VARSAYILAN_GIRDI, help="mod0_baz.csv.gz dosyasının bulunduğu dizin")
    ap.add_argument("--cikti", type=Path, default=None, help="varsayılan: <girdi>/kar_gorup_donen")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args(argv)
    cikti = args.cikti or (args.girdi / "kar_gorup_donen")
    anatomi = sa.anatomiyi_cikar(sa.islemleri_yukle(args.girdi), workers=args.workers)
    taban = ef.rejimleri_ekle(anatomi, ef.endeks_gunluk())
    df = hazirla(ozellikleri_ekle(taban, ozellik_tablosu(taban, workers=args.workers)))
    ozet = ozet_uret(df)
    cikti.mkdir(parents=True, exist_ok=True)
    ozellik_kolonlari = [c for c in df.columns if c.endswith(("_yarim", "_bir", "_tepe")) or c.startswith(("ara_", "engel_giris_", "k_"))]
    ek = ["yol_mfe_atr", "risk_atr", "endeks_tepe_stop", "tepe_stop_mum", "donus_atr", "son_kapanis_atr", "stop_mumu_ters_ms"]
    kolonlar = list(dict.fromkeys([*CIKTI_KIMLIK_KOLONLARI, *ek, *ozellik_kolonlari]))
    df[kolonlar].to_csv(cikti / "islemler.csv.gz", index=False)
    (cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    (cikti / "RAPOR.md").write_text(_markdown(ozet), encoding="utf-8")
    ilk = next(iter(ozet["kumeler"].values()))
    print(
        f"Tamamlandi -> {cikti} | islem={len(df)} | {next(iter(ozet['kumeler']))}: "
        + ", ".join(f"{ESIK_AD[ad]} gorup stop={ilk['esikler'][ad]['donus']['n']}" for ad in ESIKLER),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
