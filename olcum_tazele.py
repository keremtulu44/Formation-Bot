# -*- coding: utf-8 -*-
"""Gece ölçüm tazeleme — yalnız ÖNERİ üretir.

NE YAPAR
--------
Gece, iki soruyu yeniden sorar ve cevabı tek paragraflık öneriye çevirir:

  1. **İleri test**: "kama + üst TF aynı yönde" bayrağı, bayraksız uyarılardan
     ölçülebilir biçimde fazla veriyor mu? (`ileri_test` defteri / tablosu)
  2. **Arşiv sağlığı**: ölçümün dayandığı tablolar gerçekten doluyor mu?
     (`f2_formations`, `f2_events`, `f2_outcome_links`, `f2_snapshots`)

NE YAPMAZ
---------
* Hiçbir eşiği, kartı, sıralamayı DEĞİŞTİRMEZ. Çıktı "öneri"dir; uygulama
  kullanıcı onayıyla.
* Mesaj GÖNDERMEZ (gece mesajı yasak). Sonuç loga ve `gece_raporu` tablosuna
  yazılır.
* Veri yoksa "veri yok" der. Sıfır gözlemle yorum üretmez.

NEDEN ARŞİV SAĞLIĞI DA VAR
--------------------------
2026-10-25 denetimi: `f2_formations` 1.126 satır ama `f2_events`,
`f2_outcome_links` ve `f2_snapshots` **boş**. Yani üretimde kırılım olaylarının
arşivi tutulmuyor; araştırma tabloları repoda (offline) üretilmiş. Bu sessiz bir
körlük: "arşivden ölçüyoruz" cümlesi üretimde doğru değil. Modül her gece bunu
söyler ki unutulmasın.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import ileri_test as it

logger = logging.getLogger(__name__)

#: Arşiv sağlığı için sayılan tablolar (sıra: en kritik üstte).
ARSIV_TABLOLARI = ("f2_formations", "f2_events", "f2_outcome_links", "f2_snapshots")


def _tablo_sayisi(store, tablo: str) -> Optional[int]:
    """PostgREST ile satır sayısı. Erişim yoksa `None` (uydurma sayı yok)."""
    if store is None:
        return None
    try:
        cevap = store.request_table(tablo, "GET",
                                    params={"select": "*", "limit": "1"},
                                    headers={"Prefer": "count=exact"})
    except Exception as exc:  # noqa: BLE001
        logger.debug("Arşiv sayımı alınamadı (%s): %s", tablo, exc)
        return None
    if cevap is None:
        return None
    aralik = str(getattr(cevap, "headers", {}).get("Content-Range") or "")
    # Biçim: "0-0/1126"  (boş tabloda "*/0")
    if "/" in aralik:
        kuyruk = aralik.rsplit("/", 1)[-1].strip()
        try:
            return int(kuyruk)
        except ValueError:
            return None
    return None


def arsiv_sagligi(store) -> Dict[str, Any]:
    """Ölçümün dayandığı tabloların durumu: doluluk + sessiz körlük uyarısı."""
    sayilar = {tablo: _tablo_sayisi(store, tablo) for tablo in ARSIV_TABLOLARI}
    uyarilar: List[str] = []
    if sayilar.get("f2_events") == 0:
        uyarilar.append("f2_events boş: kırılım olayları arşivlenmiyor")
    if sayilar.get("f2_outcome_links") == 0:
        uyarilar.append("f2_outcome_links boş: olay-sonuç bağı tutulmuyor")
    if sayilar.get("f2_snapshots") == 0:
        uyarilar.append("f2_snapshots boş: faz anlık görüntüsü yok")
    forms = sayilar.get("f2_formations")
    if forms is not None and forms == 0:
        uyarilar.append("f2_formations boş: formasyon arşivi hiç yazılmıyor")
    return {"sayilar": sayilar, "uyarilar": uyarilar}


def _grup_istatistigi(kayitlar: Optional[List[Dict]], store) -> Dict[str, Any]:
    """Bayraklı/bayraksız grup ortalamaları: önce yerel defter, sonra tablo.

    Yerel defter (JSON) birincil kaynak; tablo yalnız yedek/karşılaştırma.
    """
    bayrakli: List[float] = []
    digerleri: List[float] = []
    for kayit in kayitlar or []:
        sonuc = kayit.get("sonuc")
        if not isinstance(sonuc, dict):
            continue
        try:
            yuzde = float(sonuc.get("yuzde"))
        except (TypeError, ValueError):
            continue
        (bayrakli if kayit.get("bayrak") else digerleri).append(yuzde)
    if bayrakli or digerleri:
        return {"kaynak": "defter", "bayrakli": bayrakli, "diger": digerleri}

    # Defter boşsa (yeni kurulum/restart) tablodan oku.
    if store is not None:
        try:
            cevap = store.request_table("v_ileri_test_ozet", "GET",
                                        params={"select": "*"})
            if cevap is not None:
                satirlar = cevap.json() if callable(getattr(cevap, "json", None)) else None
                for satir in satirlar or []:
                    try:
                        n = int(satir.get("n") or 0)
                        ort = float(satir.get("ortalama_yuzde"))
                    except (TypeError, ValueError, AttributeError):
                        continue
                    hedef = bayrakli if satir.get("bayrak") else digerleri
                    hedef.extend([ort] * max(0, n))
                if bayrakli or digerleri:
                    return {"kaynak": "tablo", "bayrakli": bayrakli, "diger": digerleri}
        except Exception as exc:  # noqa: BLE001 - tablo yoksa yerel yeterli
            logger.debug("v_ileri_test_ozet okunamadı: %s", exc)
    return {"kaynak": "yok", "bayrakli": [], "diger": []}


def _ort(degerler: List[float]) -> Optional[float]:
    return sum(degerler) / len(degerler) if degerler else None


def tazele(*, store=None, kayitlar: Optional[List[Dict]] = None,
           simdi=None) -> Dict[str, Any]:
    """Gece ölçüm tazelemesi. Döner: {"karar", "metin", "veri"} — değişiklik YOK."""
    if kayitlar is None:
        try:
            kayitlar = it.defter_yukle(store=store).get("kayitlar") or []
        except Exception as exc:  # noqa: BLE001
            logger.debug("İleri test defteri okunamadı: %s", exc)
            kayitlar = []

    grup = _grup_istatistigi(kayitlar, store)
    n_b, n_d = len(grup["bayrakli"]), len(grup["diger"])
    ort_b, ort_d = _ort(grup["bayrakli"]), _ort(grup["diger"])
    saglik = arsiv_sagligi(store)

    veri = {
        "kaynak": grup["kaynak"],
        "n_bayrakli": n_b,
        "n_diger": n_d,
        "ort_bayrakli": None if ort_b is None else round(ort_b, 3),
        "ort_diger": None if ort_d is None else round(ort_d, 3),
        "esik": it.ESIK_FAZLA_PUAN,
        "min_gozlem": it.MIN_GOZLEM,
        "arsiv": saglik,
    }

    if n_b < it.MIN_GOZLEM or n_d < it.MIN_GOZLEM:
        karar = "yetersiz"
        metin = (f"Ölçüm: yetersiz veri (bayraklı {n_b}, diğer {n_d}; "
                 f"grup başına {it.MIN_GOZLEM} gerekli). Öneri üretilmedi.")
    else:
        fazla = round((ort_b or 0.0) - (ort_d or 0.0), 3)
        veri["fazla"] = fazla
        if fazla >= it.ESIK_FAZLA_PUAN:
            karar = "bayrak_kalsin"
            metin = (f"Ölçüm: bayraklı grup {fazla:+.2f} yüzde puanı fazla "
                     f"(eşik +{it.ESIK_FAZLA_PUAN:g}) → bayrak kalsın önerisi.")
        else:
            karar = "bayrak_kaldirilsin"
            metin = (f"Ölçüm: fazla {fazla:+.2f} yüzde puanı, eşik "
                     f"+{it.ESIK_FAZLA_PUAN:g} → bayrak kaldırılsın önerisi.")
    veri["karar"] = karar

    if saglik["uyarilar"]:
        metin += " Arşiv: " + "; ".join(saglik["uyarilar"]) + "."
    return {"karar": karar, "metin": metin, "veri": veri}
