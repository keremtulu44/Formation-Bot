"""Batch 8 / C2 (8.4) — Kalıcılık: son tarama + 18:45 digest tamponu.

`main.py`'deki kaydet/yükle fonksiyonları canlı durumu global olarak okuyordu;
burada durum (LiveState / DeferredAlertBuffer) ve store PARAMETRE olarak alınır.
main.py'deki `son_tarama_kaydet`, `son_tarama_yukle`, `digest_tamponu_kaydet`,
`digest_tamponu_yukle` artık bu fonksiyonlara delege eden ince adaptörlerdir.

Davranış aynı: Supabase + dosya bağımsız denenir, hiçbir I/O hatası botu
durdurmaz; iki kopyadan en yeni kayıt zamanlı olan seçilir.
"""

import json
import logging
import os
from datetime import datetime

from config import ISTANBUL_TZ
from state.paths import (
    DIGEST_PENDING_SUPABASE_KEY,
    KARNE_DEFTERI_SUPABASE_KEY,
    SON_TARAMA_SUPABASE_KEY,
    digest_pending_yolu,
    kayit_zamani,
    son_tarama_data_dir,
    son_tarama_yolu,
    yeni_snapshot,
)

logger = logging.getLogger(__name__)


def son_tarama_kaydet(live_state, store=None, data_dir=None) -> bool:
    """Son listeyi iki yere bağımsız kaydeder; hiçbir I/O hatası botu durdurmaz."""
    try:
        veri = live_state.snapshot()
        formasyon_sayisi = len(veri["formations"])
    except Exception as exc:
        logger.warning("Son tarama kopyası alınamadı: %s", exc)
        return False

    dosya_var, supabase_var = False, False
    gecici_yol = None
    try:
        yol = son_tarama_yolu(data_dir)
        os.makedirs(son_tarama_data_dir(data_dir), exist_ok=True)
        gecici_yol = yol + ".tmp"
        with open(gecici_yol, "w", encoding="utf-8") as dosya:
            json.dump(veri, dosya, ensure_ascii=False, indent=2, default=str)
        os.replace(gecici_yol, yol)
        dosya_var = True
    except Exception as exc:
        logger.warning("Son tarama dosyaya kaydedilemedi: %s", exc)
    finally:
        if gecici_yol is not None:
            try:
                os.remove(gecici_yol)
            except FileNotFoundError:
                pass  # Başarılı os.replace geçici dosyayı zaten kaldırır.
            except Exception as exc:
                logger.warning("Son tarama geçici dosyası temizlenemedi: %s", exc)

    if store is not None:
        try:
            supabase_var = bool(store.upsert(SON_TARAMA_SUPABASE_KEY, veri))
        except Exception as exc:
            logger.warning("Son tarama Supabase'e kaydedilemedi: %s", exc)
    logger.info(
        "Son tarama kaydedildi: %d formasyon (supabase=%s, dosya=%s)",
        formasyon_sayisi, "var" if supabase_var else "yok", "var" if dosya_var else "yok",
    )
    return dosya_var or supabase_var


def son_tarama_yukle(live_state, store=None, data_dir=None) -> int:
    """Supabase/yerel dosyanın en yenisini yükler; ilk kurulumda sessizce 0 döner."""
    uzak_veri, yerel_veri = None, None
    if store is not None:
        try:
            satirlar = store.get_many([SON_TARAMA_SUPABASE_KEY])
            if isinstance(satirlar, dict):
                uzak_veri = satirlar.get(SON_TARAMA_SUPABASE_KEY)
        except Exception as exc:
            logger.warning("Son tarama Supabase'den okunamadı: %s", exc)
    try:
        with open(son_tarama_yolu(data_dir), encoding="utf-8") as dosya:
            yerel_veri = json.load(dosya)
    except (FileNotFoundError, ValueError, UnicodeError):
        pass  # İlk kurulum/bozuk JSON: diğer kopya varsa onu kullan.
    except Exception as exc:
        logger.warning("Son tarama dosyadan okunamadı: %s", exc)

    try:
        veri = yeni_snapshot(uzak_veri, yerel_veri)
        if veri is None:
            return 0
        sayi = live_state.hydrate(veri)
        if sayi or not veri["formations"]:
            kaynak = "Supabase" if veri is uzak_veri else "yerel dosya"
            logger.info(
                "Kayıtlı son tarama yüklendi (%s): %d formasyon, tarama zamanı %s",
                kaynak, sayi, live_state.status().get("son_tarama_bitis") or "—",
            )
        return sayi
    except Exception as exc:
        logger.warning("Son tarama kaydı yüklenemedi: %s", exc)
        return 0


def digest_tamponu_kaydet(tampon, store=None, data_dir=None, son_digest_gun=None) -> bool:
    """Bekleyen gün içi aday tamponunu Supabase + diske yazar (Batch 5 / B3).

    Neden: tampon yalnız bellekteydi; 18:45'ten önce restart olursa gün içi
    adaylar sessizce kayboluyordu. Yazma sıklığı ana döngüde seyreltilir
    (kaydet_gerekirse), böylece tarama başına yüzlerce yazma oluşmaz.
    """
    veri = tampon.snapshot()
    veri["son_digest_gun"] = son_digest_gun
    veri["kayit_zamani"] = datetime.now(ISTANBUL_TZ).isoformat()
    dosya_var, uzak_var = False, False
    try:
        yol = digest_pending_yolu(data_dir)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        gecici = yol + ".tmp"
        with open(gecici, "w", encoding="utf-8") as dosya:
            json.dump(veri, dosya, ensure_ascii=False, indent=2, default=str)
        os.replace(gecici, yol)
        dosya_var = True
    except Exception as exc:
        logger.warning("Digest tamponu dosyaya kaydedilemedi: %s", exc)
    if store is not None:
        try:
            uzak_var = bool(store.upsert(DIGEST_PENDING_SUPABASE_KEY, veri))
        except Exception as exc:
            logger.warning("Digest tamponu Supabase'e kaydedilemedi: %s", exc)
    return dosya_var or uzak_var


def digest_tamponu_yukle(tampon, store=None, data_dir=None):
    """En yeni digest tamponunu (Supabase > disk) yükler.

    Döner: (yüklenen aday sayısı, kayıttaki `son_digest_gun` ya da None).
    Çağıran taraf (main), ikinci değeri doluysa kendi globalini günceller.
    """
    uzak_veri, yerel_veri = None, None
    if store is not None:
        try:
            satirlar = store.get_many([DIGEST_PENDING_SUPABASE_KEY])
            if isinstance(satirlar, dict):
                uzak_veri = satirlar.get(DIGEST_PENDING_SUPABASE_KEY)
        except Exception as exc:
            logger.warning("Digest tamponu Supabase'den okunamadı: %s", exc)
    try:
        with open(digest_pending_yolu(data_dir), encoding="utf-8") as dosya:
            yerel_veri = json.load(dosya)
    except (FileNotFoundError, ValueError, UnicodeError):
        pass
    except Exception as exc:
        logger.warning("Digest tamponu dosyadan okunamadı: %s", exc)

    adaylar = [v for v in (uzak_veri, yerel_veri) if isinstance(v, dict)]
    veri = max(adaylar, key=lambda v: kayit_zamani(v) or datetime.min.replace(tzinfo=ISTANBUL_TZ),
               default=None)
    if veri is None:
        return 0, None
    sayi = tampon.yukle(veri)
    son_digest_gun = None
    if veri.get("son_digest_gun"):
        son_digest_gun = str(veri["son_digest_gun"]).strip() or None
    logger.info(
        "Digest tamponu yüklendi: %d bekleyen aday (gün=%s, son digest=%s)",
        sayi, tampon.gun(), son_digest_gun,
    )
    return sayi, son_digest_gun


# --- HAFTALIK KARNE DEFTERİ (yerel dosya + opsiyonel uzak yedek) -------------
# Kural: Supabase KURULU DEĞİLSE davranış değişmez; yerel dosya tek başına yeter.
# Supabase varsa yalnız yedek/taşıma amaçlı kullanılır (Render /tmp silinmesine karşı).

def karne_defteri_yukle(defter, store=None) -> int:
    """Uzak yedek varsa yerel defterle birleştirir. Eklenen kayıt sayısını döner."""
    if store is None:
        return 0
    try:
        satirlar = store.get_many([KARNE_DEFTERI_SUPABASE_KEY])
        uzak = satirlar.get(KARNE_DEFTERI_SUPABASE_KEY) if isinstance(satirlar, dict) else None
    except Exception as exc:  # noqa: BLE001 - yedek okunamazsa karne yerelle çalışır
        logger.debug("Karne defteri uzak yedeği okunamadı: %s", exc)
        return 0
    if not isinstance(uzak, dict):
        return 0
    try:
        eklenen = defter.birlestir(uzak)
        if eklenen:
            logger.info("Karne defteri uzak yedekten birleştirildi: +%d kayıt", eklenen)
        return eklenen
    except Exception as exc:  # noqa: BLE001
        logger.warning("Karne defteri birleştirilemedi: %s", exc)
        return 0


def karne_defteri_kaydet(defter, store=None) -> bool:
    """Defteri uzak yedeğe yazar (yerel dosya `KarneDefteri.kaydet` ile zaten yazıldı)."""
    if store is None:
        return False
    try:
        return bool(store.upsert(KARNE_DEFTERI_SUPABASE_KEY, defter.snapshot()))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Karne defteri uzak yedeğe yazılamadı: %s", exc)
        return False
