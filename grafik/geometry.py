# grafik/geometry.py — bölge/havuz/ölçüm geometrisi (Faz 2).

from __future__ import annotations

import io
import textwrap
import logging
import math
import os
import shutil
import tempfile
import time
import uuid
import threading
from functools import wraps
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional, Sequence

from reporting.format import sayi
import chart_experience as deneyim
from telegram_measure import SATIR_BUTCE, genislik as _genislik_16

import grafik as _pkg  # yamalı adlar için geç bağlama (plan §3)

log = logging.getLogger("grafik")  # eski kayıt adıyla aynı (__name__ yerine)

from grafik.core import (  # noqa: F401
    PALET,
    SABITLER,
    _BOLGE_TAMAM,
    _FVG_YOK_TFLAR,
    _alan,
    _alan_var,
    _durum_adi,
    _gercek,
    _kayit_listesi,
    _tam,
    _tarih,
    _wilder_atr,
    _yon,
)

def _bant_temaslari(yuksek: Sequence[Optional[float]], dusuk: Sequence[Optional[float]],
                    alt: float, ust: float, sol: int, sag: int) -> list[int]:
    """Bandı delen mum indeksleri — `zone_scoring._touch_episodes` ile AYNI kural.

    Neden yerel fonksiyon: motor temas *sayısını* (`upper_touches/lower_touches`)
    ve episode ARALIĞINI veriyor; çizim tekil mum listesi istiyor. Kural
    uydurulmadı, repo'nun kendi tanımı (`low <= ust and high >= alt`) kullanıldı.
    """
    bulun: list[int] = []
    for i in range(max(0, int(sol)), min(int(sag), len(yuksek), len(dusuk))):
        y, d = yuksek[i], dusuk[i]
        if y is None or d is None:
            continue
        if d <= ust and y >= alt:
            bulun.append(i)
    return bulun


def _bolge(tip: str, yon: int, alt: float, ust: float, kaynak: Optional[int],
           durum: Optional[str] = None, skor: Optional[float] = None,
           doluluk: Optional[float] = None, zaman: Any = None,
           gap: Optional[float] = None, *, kayit_kaynagi: Optional[str] = None,
           tamamlandi: bool = False,
           mitigated: Optional[float] = None) -> Optional[dict[str, Any]]:
    """Tek bir bölge kaydı (§1): motorun verdiği sınırlar, uydurma yok.

    FAZ 3 §A: OB kayıtlarına `mitigated_percentage` (temas/doluluk oranı, **yüzde**)
    eklenir — kutunun hangi yüzdesi tükendi, hangi kısmı canlı kaldı? Oran, motorun
    kendi `fill_boundary`'sinden hesaplanır (`OrderBlockRecord.fill_ratio` formülü,
    bkz. `domain_engines/order_block/order_block_engine.py`); uydurma geometri yok.
    """
    if alt is None or ust is None:
        return None
    if alt > ust:
        alt, ust = ust, alt
    if doluluk is not None:
        doluluk = max(0.0, min(1.0, float(doluluk)))
    if mitigated is not None:
        mitigated = round(max(0.0, min(100.0, float(mitigated))), 1)
    return {"tip": tip, "yon": 1 if yon >= 0 else -1, "alt": float(alt), "ust": float(ust),
            "kaynak": kaynak, "durum": durum, "skor": skor, "doluluk": doluluk,
            "mitigated_percentage": mitigated,
            "zaman": _tarih(zaman).isoformat() if _tarih(zaman) else None, "gap": gap,
            "kayit_kaynagi": kayit_kaynagi, "tamamlandi": bool(tamamlandi)}


def _ob_mitigated(kayit: Any, alt: Optional[float], ust: Optional[float]) -> Optional[float]:
    """OB'nin TÜKETİLME yüzdesi (0-100): motorun `fill_boundary`'sinden (FAZ 3 §A).

    `OrderBlockRecord.fill_ratio` ile birebir aynı formül: boğa kutusunda üstten
    aşağı inen temas, ayı kutusunda alttan yukarı çıkan temas oranı. Alanlar
    yoksa/bozuksa `None` döner ve kutu tek parça çizilir (uydurma oran yazılmaz).
    """
    if alt is None or ust is None:
        return None
    try:
        yuk = float(ust) - float(alt)
        if yuk <= 0:
            return None
        sinir = _gercek(_alan(kayit, "fill_boundary"))
        if sinir is None:
            return None
        bullish = bool(_alan(kayit, "bullish"))
        oran = ((float(ust) - float(sinir)) / yuk if bullish
                else (float(sinir) - float(alt)) / yuk)
    except Exception:
        return None
    return max(0.0, min(100.0, oran * 100.0))


def _zone_renk(b: Mapping[str, Any]) -> str:
    """Kutunun rengi TİP + YÖN'den (FAZ 3 §2 paleti).

    OB boğa zümrüt yeşili / ayı mercan kırmızısı; FVG boğa turkuaz / ayı mor.
    FVG ile OB aynı renk grubunda görünmez; ayrım kontur stiliyle de taşınır.
    """
    tip = str(b.get("tip") or "")
    yon = int(b.get("yon") or 1)
    if tip == "ob":
        return PALET["ob_bull"] if yon >= 0 else PALET["ob_bear"]
    if tip == "fvg":
        return PALET["fvg_bull"] if yon >= 0 else PALET["fvg_bear"]
    return PALET["engulf"]


def _zone_kalan_orani(yon: int, dol: Optional[float]) -> Optional[float]:
    """Kutunun CANLI (dolmamış) oranı: doluluk (0-1) → kalan (1-0).

    `None` → doluluk bilinmiyor; kutu "taze" kabul edilir (yüzde yazılmaz).
    """
    if dol is None:
        return None
    return max(0.0, min(1.0, 1.0 - float(dol)))


def _zone_durum_onceligi(bolge: Mapping[str, Any]) -> int:
    """Aktif alanı adaydan, adayı da tamamlanmış tarihçeden önce tut."""
    if bolge.get("tamamlandi"):
        return 2
    durum = str(bolge.get("durum") or "").upper()
    if durum in _BOLGE_TAMAM:
        return 2
    if durum == "CANDIDATE":
        return 1
    return 0


def _zone_havuzu(sonuclar: Optional[Mapping[str, Any]], tf: str, son_kapanis: Optional[float],
                 sol: int, sag: int, cerceve: Any = None) -> dict[str, Any]:
    """Görsel bölge havuzu: yalnız OB ve FVG lifecycle kayıtları.

    Engulfing motor verisi grafik katmanına hiç alınmaz.
    Lifecycle verisi varsa FVG ham oluşum listesiyle karıştırılmaz. Tamamlanmış lifecycle
    kayıtları zayıf/tarihi çizgiyle tutulur; eski motor şekillerinde raw oluşum
    alanlarına kontrollü fallback yapılır. Motorlara yazılmaz.
    """
    havuz: list[dict[str, Any]] = []
    hata: list[str] = []
    cikarim: dict[str, Any] = {
        "ob": 0, "fvg": 0, "eng": 0,
        "ob_source": "yok", "fvg_source": "yok", "eng_source": "yok",
        "ob_active": 0, "fvg_active": 0, "fvg_completed": 0,
        "eng_active": 0, "eng_completed": 0,
        "fvg_raw": 0, "eng_raw": 0, "duplicates_removed": 0,
    }
    if not sonuclar:
        return {}
    atr = _wilder_atr(cerceve)

    ob = sonuclar.get("order_block") if isinstance(sonuclar, Mapping) else _alan(sonuclar, "order_block")
    if ob is not None:
        try:
            detay = _alan(ob, "details", {}) or {}
            if _alan_var(detay, "active_records"):
                kayitlar = _kayit_listesi(_alan(detay, "active_records"))
                ob_kayit_kaynagi = "active_records"
            else:
                # Eski/harici sonuç şekli için uyumluluk fallback'i.
                kayitlar = _kayit_listesi(_alan(detay, "records", []))
                ob_kayit_kaynagi = "records_legacy"
            cikarim["ob"] = cikarim["ob_active"] = len(kayitlar)
            cikarim["ob_source"] = ob_kayit_kaynagi
            export = _alan(ob, "export")
            dolular: dict[int, Optional[float]] = {}
            for taraf in ("bull", "bear"):
                yan = _alan(export, taraf) if export is not None else None
                kaynak = _tam(_alan(yan, "source_bar"))
                if kaynak is not None:
                    dolular[kaynak] = _gercek(_alan(yan, "fill"))
            for kayit in kayitlar:
                kaynak = _tam(_alan(kayit, "source_index"))
                alt_k, ust_k = _gercek(_alan(kayit, "bottom")), _gercek(_alan(kayit, "top"))
                # FAZ 3 §A: `mitigated_percentage` motoun kendi sınırından
                # (`fill_boundary`) hesaplanır — kayıt yalnız export'tan gelen
                # `fill` oranını taşıyorsa o kullanılır, yoksa alan boş kalır.
                _export_fill = dolular.get(kaynak) if kaynak is not None else None
                if _export_fill is not None:
                    mit = max(0.0, min(100.0, float(_export_fill) * 100.0))
                else:
                    mit = _ob_mitigated(kayit, alt_k, ust_k)
                bolge = _bolge("ob", 1 if _alan(kayit, "bullish") else -1,
                               alt_k, ust_k,
                               kaynak, skor=_gercek(_alan(kayit, "base_score")),
                               doluluk=(mit / 100.0 if mit is not None else None),
                               mitigated=mit,
                               zaman=_alan(kayit, "source_time"),
                               kayit_kaynagi=ob_kayit_kaynagi)
                if bolge:
                    havuz.append(bolge)
        except Exception as h:
            log.warning("grafik: OB bölgeleri okunamadı (%s)", h)
            hata.append("ob")

    fvg = sonuclar.get("fvg") if isinstance(sonuclar, Mapping) else _alan(sonuclar, "fvg")
    if fvg is not None and str(tf) not in _FVG_YOK_TFLAR:
        try:
            detay = _alan(fvg, "details", {}) or {}
            raw_fvg = _kayit_listesi(_alan(detay, "fvg_formations", []))
            fvg_keys = ("active_bullish_fvg", "active_bearish_fvg", "completed_fvg")
            fvg_lifecycle = any(_alan_var(detay, key) for key in fvg_keys)

            def oran(kayit: Any, alanlar: Sequence[str]) -> Optional[float]:
                for alan in alanlar:
                    deger = _gercek(_alan(kayit, alan))
                    if deger is not None:
                        return deger
                return None

            fvg_kayitlari: list[tuple[Any, bool, str]] = []
            if fvg_lifecycle:
                fvg_active: list[Any] = []
                for key in fvg_keys[:2]:
                    fvg_active.extend(_kayit_listesi(_alan(detay, key)))
                fvg_completed = _kayit_listesi(_alan(detay, "completed_fvg"))
                cikarim["fvg_active"] = len(fvg_active)
                cikarim["fvg_completed"] = len(fvg_completed)
                fvg_kayitlari.extend((kayit, False, "active_lifecycle") for kayit in fvg_active)
                fvg_kayitlari.extend((kayit, True, "completed_lifecycle") for kayit in fvg_completed)
                cikarim["fvg_source"] = "lifecycle"
            else:
                cikarim["fvg_raw"] = len(raw_fvg)
                fvg_kayitlari.extend((kayit, False, "raw_formation") for kayit in raw_fvg)
                cikarim["fvg_source"] = "raw_fallback"
            cikarim["fvg"] = len(fvg_kayitlari)
            for kayit, tamamlandi, kayit_kaynagi in fvg_kayitlari:
                yon = _yon(_alan(kayit, "direction"))
                if yon == 0:
                    continue
                bolge = _bolge("fvg", yon,
                               _gercek(_alan(kayit, "lower_boundary")),
                               _gercek(_alan(kayit, "upper_boundary")),
                               _tam(_alan(kayit, "formation_index")),
                               durum=_durum_adi(_alan(kayit, "state")),
                               skor=_gercek(_alan(kayit, "quality")),
                               # FvgFormation.close_fill_ratio tek başına doluluk
                               # değildir; lifecycle maximum_fill_ratio önceliklidir.
                               doluluk=oran(kayit, ("maximum_fill_ratio", "wick_fill_ratio",
                                                   "close_fill_ratio")),
                               zaman=_alan(kayit, "formation_time"),
                               gap=_gercek(_alan(kayit, "gap_size")),
                               kayit_kaynagi=kayit_kaynagi, tamamlandi=tamamlandi)
                if bolge:
                    havuz.append(bolge)

        except Exception as h:
            log.warning("grafik: FVG bölgeleri okunamadı (%s)", h)
            hata.append("fvg")
    elif fvg is not None:
        # §0.12l: 1s/2s karesinde FVG katmanı çizilmez (motor da üretmiyor).
        cikarim["fvg_tf_yok"] = 1

    # Aynı motor kaydının/geometry'nin iki kez aktarılması mükerrer kutu üretmesin.
    benzersiz: dict[tuple[Any, ...], dict[str, Any]] = {}
    for bolge in havuz:
        kimlik = (bolge["tip"], bolge["yon"], round(bolge["alt"], 8),
                  round(bolge["ust"], 8), bolge["kaynak"])
        onceki = benzersiz.get(kimlik)
        if onceki is None:
            benzersiz[kimlik] = bolge
            continue
        cikarim["duplicates_removed"] += 1
        if _zone_durum_onceligi(bolge) < _zone_durum_onceligi(onceki):
            benzersiz[kimlik] = bolge
    havuz = list(benzersiz.values())

    if not havuz:
        return {"cizilen": [], "elenen": 0, "kaynak_disi": 0, "kapak": dict(
            _kapak_sayilari(tf)), "sirala": "bölge yok", "cikarim": cikarim,
            "hata": sorted(set(hata))}

    for b in havuz:
        merkez = (b["alt"] + b["ust"]) / 2.0
        b["merkez"] = merkez
        b["taraf"] = "ust" if (son_kapanis is None or merkez >= son_kapanis) else "alt"
        b["mesafe"] = abs(merkez - son_kapanis) if son_kapanis is not None else 0.0
        b["mesafe_atr"] = (b["mesafe"] / atr) if (atr and son_kapanis is not None) else None
    # Önce aktif, sonra aday, en son tamamlanmış/tarihi kayıt; her grupta en
    # yakın kutu ve eşitlikte daha yeni `kaynak` kazanır.
    anahtar = (lambda b: (_zone_durum_onceligi(b),
                          b["mesafe_atr"] if b["mesafe_atr"] is not None else b["mesafe"],
                          -(b["kaynak"] if b["kaynak"] is not None else -1)))
    havuz.sort(key=anahtar)
    ust_k, alt_k = _kapak_sayilari(tf)["ust"], _kapak_sayilari(tf)["alt"]
    secilen: list[dict[str, Any]] = []
    # İki slot varsa en yakın aktif FVG için bir görünürlük payı ayır.
    for taraf, kapasite in (("ust", ust_k), ("alt", alt_k)):
        taraf_kayitlari = [b for b in havuz if b["taraf"] == taraf]
        ayrilan: list[dict[str, Any]] = []
        if kapasite >= 2:
            for tip in ("fvg",):
                aday = next((b for b in taraf_kayitlari
                             if b["tip"] == tip and _zone_durum_onceligi(b) < 2), None)
                if aday is not None and aday not in ayrilan:
                    ayrilan.append(aday)
        taraf_secilen = ayrilan[:kapasite]
        for b in taraf_kayitlari:
            if len(taraf_secilen) >= kapasite:
                break
            if b not in taraf_secilen:
                taraf_secilen.append(b)
        secilen.extend(taraf_secilen)
    elenen = max(0, len(havuz) - len(secilen))
    for b in havuz:
        b["vurgu"] = "alt" if int(b["yon"]) >= 0 else "ust"   # §0.12r (kayatta karar)
        b["x0"], b["x1"] = 0, max(0, int(sag) - int(sol) - 1)
        if b["kaynak"] is not None:
            b["x0"] = max(0, min(int(b["kaynak"]) - int(sol), b["x1"]))
    # Çizim/rapor sırası: taraf, sonra yakınlık (meta okunur kalsın)
    secilen.sort(key=lambda b: (b["taraf"], b["mesafe"], int(b["kaynak"] or 0)))
    return {"cizilen": secilen, "tum": havuz, "elenen": elenen,
            "kaynak_disi": sum(1 for b in secilen if b["kaynak"] is not None
                               and int(b["kaynak"]) < int(sol)),
            "kapak": {"ust": ust_k, "alt": alt_k},
            "sirala": ("mesafe/ATR" if atr else "mesafe (ATR yok → ham fiyat)"),
            "atr": atr, "cikarim": cikarim, "hata": sorted(set(hata))}


def _kapak_sayilari(tf: str) -> dict[str, int]:
    ust = SABITLER["zone_ust"].get(str(tf), 3)
    alt = SABITLER["zone_alt"].get(str(tf), 3)
    return {"ust": int(ust), "alt": int(alt)}


def _yatay_aralik(degerler: Iterable[Optional[float]], ek: Iterable[Optional[float]] = (),
                  mum_genisligi: float = 0.0) -> tuple[float, float]:
    """Çizilen her şeyin min/maksı + %4 pay (§0.13); tek seviyede çökmesin diye taban pay."""
    tum = [float(x) for x in list(degerler) + list(ek)
           if x is not None and math.isfinite(float(x))]
    if not tum:
        return 0.0, 1.0
    alt, ust = min(tum), max(tum)
    aciklik = max(ust - alt, abs(ust) * 0.02, 0.5)
    pay = 0.04 * aciklik
    return alt - pay, ust + pay


def _formasyon_araligi(formasyon: Mapping[str, Any], sol: int, n: int,
                       sag_bosluk: int) -> tuple[int, int, Optional[int]]:
    """Bant çizgisinin çizileceği bar aralığı: `(x0, bitis, apex_i)`.

    APEX biliniyorsa çizim apex'te BİTER. Daralan bantta iki doğru apex'te
    kesişir; apex'in ÖTESİNE uzatmak ters dönen (X çizen) uydurma geometri olur
    ve çizgiler havada asılı kalır. Eski kod apex'i yalnız sağ boşluğa düştüğünde
    kısaltıyordu: apex geçmişte kaldığında doğrular tepeyi aşıp kesişiyordu
    (kullanıcı geri bildirimi: "kırpılıyormuş gibi").
    """
    bas = formasyon.get("start_bar")
    x0 = 0
    if bas is not None and int(bas) - sol >= 0:
        x0 = min(int(bas) - sol, max(0, n - 1))
    bitis = n + max(0, int(sag_bosluk))
    apex_i = None
    if formasyon.get("apex_bar") is not None:
        apex_i = int(formasyon["apex_bar"]) - sol
        if apex_i >= x0:
            bitis = max(x0 + 1, min(bitis, apex_i + 1))
    # ÇÖZÜLMÜŞ formasyonda bant GEÇMİŞTİR: teyit/retest/geçersizleşme kartında
    # `end_bar` kırılım mumudur; bandı onun ötesine uzatmak "hâlâ sürüyor" yalanı
    # olur ve doğrular kesişmişse havada X çizer. Yalnız son mumdan ÖNCE biten
    # bant kısılır — oluşmakta olan formasyonda (`end_bar` == son mum) sağ
    # boşluktaki projeksiyon aynen kalır.
    bit = _tam(formasyon.get("end_bar"))
    if bit is not None and bit - sol < n - 1:
        bitis = max(x0 + 1, min(bitis, bit - sol + 1))
    # GEOMETRİK KESİŞİM: beyan edilen `apex_bar` motorun yuvarlamasıyla iki
    # doğrunun gerçek kesişiminden sapabiliyor (flama örneğinde 168 ↔ ~124);
    # sapma kalırsa doğrular tepeyi aşıp ters dönüyordu. Kesişim barı doğrudan
    # motorun çapa noktalarından çözülür ve çizim orada biter. Paralel bantta
    # (bayrak) kesişim yoktur → uzatma korunur.
    ust_ca = [formasyon.get(k) for k in ("hb1", "hp1", "hb2", "hp2")]
    alt_ca = [formasyon.get(k) for k in ("lb1", "lp1", "lb2", "lp2")]
    if all(v is not None for v in ust_ca) and all(v is not None for v in alt_ca):
        b1, p1, b2, p2 = (float(v) for v in ust_ca)
        c1, q1, c2, q2 = (float(v) for v in alt_ca)
        mu = (p2 - p1) / (b2 - b1) if b2 != b1 else 0.0
        ma = (q2 - q1) / (c2 - c1) if c2 != c1 else 0.0
        if abs(mu - ma) > 1e-12:
            i_kes = ((q1 - ma * c1) - (p1 - mu * b1)) / (mu - ma)
            if x0 < i_kes < bitis:
                bitis = max(x0 + 1, min(bitis, int(i_kes) + 1))
                apex_i = int(i_kes) if apex_i is None else apex_i
    return x0, bitis, apex_i


def _formasyon_serileri(formasyon: Mapping[str, Any], sol: int,
                        bitis: int) -> dict[str, list[float]]:
    """Motorun iki çapa noktasından geçen bant doğrularını bar bar değerlendirir.

    Yeni geometri ÜRETİLMEZ: `f_line_price` motorun kendi doğrusudur (`hb1/hp1` +
    `hb2/hp2` üst, `lb1/lp1` + `lb2/lp2` alt). Çapa yoksa eski yatay çizgiye
    düşülür. Kadraj hesabı ile çizim bu AYNI seriyi paylaşır — iki yerde ayrı
    hesap farklı geometri üretirdi.
    """
    from patterns.mathutil import f_line_price
    seriler: dict[str, list[float]] = {}
    adet = max(0, int(bitis))
    for ust_mu in (True, False):
        deger = formasyon.get("upper_now") if ust_mu else formasyon.get("lower_now")
        if deger is None:
            continue
        ad = "ust" if ust_mu else "alt"
        ca = ("hb1", "hp1", "hb2", "hp2") if ust_mu else ("lb1", "lp1", "lb2", "lp2")
        capa = [formasyon.get(k) for k in ca]
        if any(v is None for v in capa):
            seriler[ad] = [float(deger)] * adet
            continue
        b1, p1, b2, p2 = capa
        seriler[ad] = [f_line_price(int(b1), float(p1), int(b2), float(p2), i + sol)
                       for i in range(adet)]
    return seriler


def _gorunur_parcalar(xs: Sequence[float], ys: Sequence[float],
                      aralik: Optional[Sequence[float]]) -> list[tuple[list[float], list[float]]]:
    """Seriyi, y-aralığının İÇİNDE kalan kesintisiz parçalara böler.

    Neden: bant doğrusu fiyattan kopuk bölgede (üçgenin geriye uzanan tabanı,
    dik yükselen alt çizgi) karenin altına/üstüne taşıyor. Geometri korunur
    (noktalar `f_line_price`tan gelir) ama **kadraj dışı parça çizilmez** —
    eksen kenarında sert kesilen, anlamsız bir çizgi kalmaz. `aralik` yoksa
    seri olduğu gibi döner (birim testleri ve kare-dışı çağrılar eski davranışı
    görür).
    """
    if aralik is None or len(aralik) < 2:
        return [(list(xs), list(ys))]
    lo, hi = float(aralik[0]), float(aralik[1])
    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
        return [(list(xs), list(ys))]
    parcalar: list[tuple[list[float], list[float]]] = []
    xs_p: list[float] = []
    ys_p: list[float] = []
    for x, y in zip(xs, ys):
        if y is None or not math.isfinite(float(y)) or not (lo <= float(y) <= hi):
            if xs_p:
                parcalar.append((xs_p, ys_p))
                xs_p, ys_p = [], []
            continue
        xs_p.append(float(x))
        ys_p.append(float(y))
    if xs_p:
        parcalar.append((xs_p, ys_p))
    return parcalar


def _swing_ofseti(ax, x: float, yukari: bool, yerlesik: list, n: int,
                  yazi_px: float = 14.0) -> float:
    """Grafik içi etiketin piksel ofseti; yakın (aynı yönde, x'i çakışan) etiket varsa basamaklanır.

    Neden: `HL` ile `PL` aynı barda üst üste bindi (görsel-2 ölçümü). Etiket
    genişliği kısa sınıflarda ~12–14 px, fiyatlı PH/PL etiketinde ~55 px; ikinci
    etiket birinciyle bu mesafeden yakınsa alt satıra itilir.
    """
    try:
        genislik_px = float(ax.get_window_extent().width)
        bar_px = genislik_px / max(1.0, float(n))
    except Exception:
        bar_px = 6.0
    x_px = float(x) * bar_px
    # FAZ 4 §6: HH/HL/LH/LL metni mum FİTİLİNE değmesin — taban ofset 11 px
    # (10-15 px aralığı), aynı yöndeki komşu etiket varsa basamaklanır.
    ofs = max(11.0, float(SABITLER["swing_etiket_ofset_px"]))
    adim = float(SABITLER["zone_yazi_pt"]) * 1.45 * float(ax.figure.dpi) / 72.0
    while any(yn == yukari and abs(xp - x_px) < max(14.0, float(yazi_px))
              and abs(oo - ofs) < 0.5
              for xp, yn, oo in yerlesik):
        ofs += adim * 72.0 / float(ax.figure.dpi)
    yerlesik.append((x_px, yukari, ofs))
    return ofs if yukari else -ofs


def _mum_kutulari_px(ax, acilis, yuksek, dusuk, kapanis, cap: float):
    """Mum gövde+fitil kutuları PİKSEL olarak (Nx4: x0,y0,x1,y1); numpy gerekir."""
    import numpy as np

    govde, fitil = [], []
    for i, (a, k, y, d) in enumerate(zip(acilis, kapanis, yuksek, dusuk)):
        if None in (a, k, y, d):
            continue
        govde.append((i - cap / 2.0, min(a, k), i + cap / 2.0, max(a, k)))
        fitil.append((i - 0.25, d, i + 0.25, y))
    def _kutu(liste):
        if not liste:
            return np.zeros((0, 4))
        arr = np.array(liste, dtype=float)
        p0 = ax.transData.transform(arr[:, 0:2])
        p1 = ax.transData.transform(arr[:, 2:4])
        return np.hstack([np.minimum(p0, p1), np.maximum(p0, p1)])
    return np.vstack([_kutu(govde), _kutu(fitil)]) if (govde or fitil) else np.zeros((0, 4))


