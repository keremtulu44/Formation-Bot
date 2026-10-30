# -*- coding: utf-8 -*-
"""Gece önerisinin onay defteri — `/evet` · `/hayır`.

NE YAPAR
--------
Gece denetiminin (§15) ürettiği **tek** öneriyi kayıt altına alır; kullanıcı
`/evet` ya da `/hayır` dediğinde kararı yazar ve ne olup ne olmadığını açıkça
söyler.

NE YAPMAZ
---------
* Hiçbir eşiği, kartı, sıralamayı, etiketi DEĞİŞTİRMEZ. "Onay" otomatik
  uygulama değildir: karar kayda geçer, kod/config değişikliği yine elle yapılır.
  Botun kendi kendine eşik değiştirmesi bu projede yasak (bkz. §14.3, §15.3).
* Mesaj GÖNDERMEZ; yalnız komut yanıtı üretir.
* Ölçümü durdurmaz: `/hayır` "ölçme" demek değil, "bu öneriyi kabul etmiyorum"
  demektir.

TEKRAR KURALI
-------------
Yanıtlanmış bir öneri aynı metinle `TEKRAR_GUN` gün boyunca DM'e tekrar düşmez:
her gece aynı cümleyi göndermek öneriyi okunmaz hale getirir. Koşullar
değişirse (fark/karar değişirse) metin de değişir ve yeniden sorulur.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DOSYA = "gece_onerisi.json"
SUPABASE_KEY = "state:gece_onerisi"
TEKRAR_GUN = 7

KABUL = {"evet", "onay", "kabul", "e", "tamam", "ok"}
RED = {"hayir", "hayır", "red", "h", "yok"}


def dosya_yolu(data_dir: Optional[str] = None) -> str:
    if data_dir is None:
        from config import DATA_DIR
        data_dir = DATA_DIR
    return os.path.join(data_dir, DOSYA)


def _bos() -> Dict[str, Any]:
    return {"oneri": None}


def yukle(*, store=None, data_dir: Optional[str] = None) -> Dict[str, Any]:
    """Yerel dosya + Supabase yedeği. Hata çağıranı düşürmez."""
    veri = _bos()
    try:
        with open(dosya_yolu(data_dir), "r", encoding="utf-8") as dosya:
            yerel = json.load(dosya)
        if isinstance(yerel, dict):
            veri = yerel
    except (OSError, ValueError):
        pass
    if store is not None:
        try:
            uzak = (store.get_many([SUPABASE_KEY]) or {}).get(SUPABASE_KEY)
            if isinstance(uzak, dict):
                # Daha yeni karar kazanır; yerel silinmişse uzak geri getirir.
                yerel_zaman = str((veri.get("oneri") or {}).get("cevap_zamani") or "")
                uzak_zaman = str((uzak.get("oneri") or {}).get("cevap_zamani") or "")
                if veri.get("oneri") is None or uzak_zaman > yerel_zaman:
                    veri = uzak
        except Exception as exc:  # noqa: BLE001 - yedek okunamazsa yerelle devam
            logger.debug("Gece önerisi uzak yedeği okunamadı: %s", exc)
    if not isinstance(veri.get("oneri"), (dict, type(None))):
        veri["oneri"] = None
    return veri


def kaydet(oneri: Dict, *, store=None, data_dir: Optional[str] = None) -> bool:
    """Öneriyi/kararı yazar. I/O hatası çağıranı düşürmez."""
    veri = {"oneri": dict(oneri or {}), "kayit_zamani": datetime.now().isoformat(timespec="seconds")}
    yazildi = False
    try:
        yol = dosya_yolu(data_dir)
        os.makedirs(os.path.dirname(yol) or ".", exist_ok=True)
        gecici = yol + ".tmp"
        with open(gecici, "w", encoding="utf-8") as dosya:
            json.dump(veri, dosya, ensure_ascii=False)
        os.replace(gecici, yol)
        yazildi = True
    except OSError as exc:
        logger.debug("Gece önerisi yazılamadı: %s", exc)
    if store is not None and getattr(store, "writable", True):
        try:
            # Yerel dosya yazılamasa da doğrulanmış bir uzak kayıt yeterlidir.
            uzak_yazildi = bool(store.upsert(SUPABASE_KEY, veri))
            yazildi = yazildi or uzak_yazildi
        except Exception as exc:  # noqa: BLE001
            logger.debug("Gece önerisi uzak yedeğe yazılamadı: %s", exc)
    return yazildi


def bekleyen(*, store=None, data_dir: Optional[str] = None) -> Optional[Dict]:
    """Yanıt bekleyen öneri (yoksa `None`)."""
    oneri = (yukle(store=store, data_dir=data_dir) or {}).get("oneri")
    if isinstance(oneri, dict) and oneri.get("durum") == "bekliyor":
        return oneri
    return None


def _tarih(ham) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(ham))
    except (TypeError, ValueError):
        return None


def tekrar_mi(metin: str, *, store=None, data_dir: Optional[str] = None,
              simdi: Optional[datetime] = None, gun: int = TEKRAR_GUN) -> bool:
    """Aynı metin yakın zamanda yanıtlandı mı? (DM tekrarını önler)"""
    oneri = (yukle(store=store, data_dir=data_dir) or {}).get("oneri")
    if not isinstance(oneri, dict):
        return False
    if str(oneri.get("metin") or "") != str(metin or ""):
        return False
    if oneri.get("durum") not in {"onaylandi", "reddedildi"}:
        return False
    cevap = _tarih(oneri.get("cevap_zamani"))
    simdi = simdi or datetime.now()
    if cevap is None:
        return False
    if cevap.tzinfo is None and simdi.tzinfo is not None:
        cevap = cevap.replace(tzinfo=simdi.tzinfo)
    if simdi.tzinfo is None and cevap.tzinfo is not None:
        cevap = cevap.replace(tzinfo=None)
    return (simdi - cevap) <= timedelta(days=max(1, int(gun)))


def _gun_metni(oneri: Dict) -> str:
    ham = str(oneri.get("gun") or "")
    try:
        return datetime.fromisoformat(ham).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return ham or "tarih yok"


def cevapla(cevap: str, *, store=None, data_dir: Optional[str] = None,
            simdi: Optional[datetime] = None) -> str:
    """`/evet` ya da `/hayır` yanıtı. Kararı yazar, ne olduğunu söyler."""
    simdi = simdi or datetime.now()
    ham = str(cevap or "").strip().lower()
    if ham in KABUL:
        karar = "onaylandi"
    elif ham in RED:
        karar = "reddedildi"
    else:
        return "Yanıt anlaşılmadı: /evet ya da /hayır yazın."

    oneri = bekleyen(store=store, data_dir=data_dir)
    if oneri is None:
        return ("Bekleyen gece önerisi yok. Öneri yalnız sapma çıkarsa ya da ölçüm "
                "\"bayrak kaldırılsın\" derse DM'e düşer; her gece öneri üretilmez.")

    oneri = dict(oneri)
    oneri["durum"] = karar
    oneri["cevap_zamani"] = simdi.isoformat(timespec="seconds")
    if not kaydet(oneri, store=store, data_dir=data_dir):
        return ("⚠️ Karar kaydedilemedi; onay veya ret işlemi tamamlanmadı. "
                "Depolamayı kontrol edip /evet veya /hayır komutunu yeniden gönderin.")

    ozet = str(oneri.get("ozet") or oneri.get("karar") or "").strip()
    baslik = ("✅ Öneri onaylandı" if karar == "onaylandi" else "❌ Öneri reddedildi")
    satirlar = [f"{baslik} — {_gun_metni(oneri)} gece denetimi"]
    if ozet:
        satirlar.append(f"Konu: {ozet}")
    if karar == "onaylandi":
        satirlar.append("Karar kayda geçti. Bot kendiliğinden hiçbir eşiği, kartı ya da "
                        "etiketi değiştirmedi; uygulama elle yapılır.")
    else:
        satirlar.append(f"Ölçüm aynen sürer. Aynı öneri {TEKRAR_GUN} gün boyunca tekrar "
                        "sorulmaz; koşullar değişirse yeni metinle gelir.")
    return "\n".join(satirlar)
