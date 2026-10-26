# grafik/indicators.py — ATR/hacim/yapı göstergeleri (Faz 2).
# Not: _wilder_atr core'a alındı (geometry→indicators döngüsü kırmak için).

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

def _rvol_katı(deger: float) -> str:
    """Rozet katı metni: `x2,5` — 2 basamak yazılır, gereksiz sıfır kırpılır.

    Neden 1 basamak yetmiyor: `x0,96` tek basamakta `x1,0` olurdu, yani hacim
    KURUMASI "normal" görünürdü (yanlış bilgi). 2 basamak + sıfır kırpma hem
    kısa kalır (`x2,5` · `x0,5`) hem de 2,04 gibi eşik üstünü `x2,0` diye
    yazıp eşikle çelişmez.
    """
    tam, _, ondalik = sayi(deger, 2).partition(",")
    while len(ondalik) > 1 and ondalik.endswith("0"):
        ondalik = ondalik[:-1]
    return f"{tam},{ondalik}"


def _mum_cakisma_say(fig, ax, acilis, yuksek, dusuk, kapanis, cap: float) -> dict[str, Any]:
    """Ölçüm: hangi yazı hangi mumun gövdesi/fitili ile EKRANDA çakışıyor.

    Neden: "yazı mumun üstüne bindi mi" görsel bir soru; piksel hash'i yerine
    sayı verir. Her yazının görüntü kutusu (`get_window_extent`) ile her mumun
    gövde ve fitil kutusu (`transData`, piksel) karşılaştırılır. Yazılar sağdaki
    fiyat şeridinde (x > n-1) olduğundan doğal olarak çakışmaz; çakışma = kötü yerleşim.
    Ölçüm hata verirse `None` döner ve çizimi etkilemez.
    """
    try:
        import numpy as np
        renderer = fig.canvas.get_renderer()
        n = len(kapanis)
        govde, fitil = [], []
        for i in range(n):
            a, k, y, d = acilis[i], kapanis[i], yuksek[i], dusuk[i]
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
        gk, fk = _kutu(govde), _kutu(fitil)
        yazilar = [t for t in ax.texts if t.get_visible() and str(t.get_text()).strip()]
        # GÖRSEL-4: kutu içi (`kutu-ici`) ve olay etiketi (`olay-ici`) BİLİNÇLİ olarak
        # veri alanında durur (kullanıcı kararı: "dikdörtgenin içine yaz"). Kapı yine
        # de şerit/başlık yazıları için katı kalır; katman yazıları ayrı sayılır ve
        # `meta["kalite"]["katman_cakisan"]` ile görünür olur.
        cakisan: list[str] = []
        katman_cakisan: list[str] = []
        for t in yazilar:
            bb = t.get_window_extent(renderer)
            if bb.width <= 0 or bb.height <= 0:
                continue
            m = 1.0
            hit = False
            for kk in (gk, fk):
                if len(kk) == 0:
                    continue
                ort = ((kk[:, 0] <= bb.x1 + m) & (kk[:, 2] >= bb.x0 - m)
                       & (kk[:, 1] <= bb.y1 + m) & (kk[:, 3] >= bb.y0 - m))
                if bool(ort.any()):
                    hit = True
                    break
            if not hit:
                continue
            if str(t.get_gid() or "").endswith("-ici"):
                katman_cakisan.append(str(t.get_text())[:16])
            else:
                cakisan.append(str(t.get_text())[:16])
        return {"yazi": len(yazilar), "mum_cakisan": len(cakisan), "cakisan": cakisan[:8],
                "katman_yazi": sum(1 for t in yazilar
                                   if str(t.get_gid() or "").endswith("-ici")),
                "katman_cakisan": katman_cakisan[:8]}
    except Exception as hata:  # pragma: no cover - ölçüm çizimi bozmaz
        log.debug("grafik: çakışma ölçümü atlandı (%s)", hata)
        return None


def _grafik_yapi_metni(metin: str) -> str:
    """Remove internal scope wording from new AND previously saved chart headers."""
    baslik, ayrac, govde = str(metin or "").partition(": ")
    if not ayrac:
        govde, baslik = baslik, ""
    parcalar = [p.strip() for p in govde.split(" · ")]
    def ic(parca):
        return parca.lower() in ("iç", "internal") or parca.lower().startswith(("iç ", "internal "))
    if not ayrac and any(ic(p) for p in parcalar) and not any("dış" in p for p in parcalar):
        return ""  # an internal-only event is not an external chart headline
    parcalar = [p.replace("dış+iç", "dış") for p in parcalar if not ic(p)]
    return (baslik + ": " if baslik and parcalar else "") + " · ".join(parcalar)


def _grafik_dis_yapi(olay: Mapping[str, Any]) -> dict[str, Any]:
    if not olay:
        return {}
    dis_olaylar = [b for b in (olay.get("olaylar") or [])
                   if str(b.get("scope") or b.get("kapsam") or "EXTERNAL").upper() != "INTERNAL"]
    dis_seviyeler = [e for e in olay.get("seviyeler", [])
                     if str(e.get("scope") or "EXTERNAL").upper() == "EXTERNAL"]
    kritik = olay.get("kritik") or {}
    if str(kritik.get("scope") or kritik.get("kapsam") or "EXTERNAL").upper() == "INTERNAL":
        kritik = None
    return {**olay, "swinglar": [], "olaylar": dis_olaylar, "kritik": kritik,
            "seviyeler": dis_seviyeler,
            "zaman_cizelgesi": [e for e in olay.get("zaman_cizelgesi", dis_olaylar)
                                if str(e.get("scope") or "EXTERNAL").upper() == "EXTERNAL"],
            "cizilen": len(dis_seviyeler) + len(dis_olaylar),
            "kapak": {**(olay.get("kapak") or {}), "swing": 0}}


def _grafik_zone(zone: Mapping[str, Any]) -> dict[str, Any]:
    """Graph-only allowlist, including old queued snapshots. Never mutate engines."""
    if not zone:
        return {}
    return {**zone, "cizilen": [b for b in (zone.get("cizilen") or [])
                                if str(b.get("tip")) in ("ob", "fvg")]}


