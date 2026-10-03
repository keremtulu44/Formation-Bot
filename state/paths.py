"""Batch 8 / C2 (8.4) — Kalıcılık YOLLARI ve snapshot yardımcıları.

Saf yardımcılar: dosya adları, yol üretimi, kayıt zamanı okuma ve iki kopyadan
(Supabase / yerel dosya) en yenisini seçme. Canlı durum okumaz.
"""

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

SON_TARAMA_DOSYA = "son_tarama.json"
SON_TARAMA_SUPABASE_KEY = "state:son_tarama"

DIGEST_PENDING_SUPABASE_KEY = "state:digest_pending"
DIGEST_PENDING_DOSYA = "telegram_digest_pending.json"


def son_tarama_data_dir(data_dir=None):
    if data_dir is None:
        from config import DATA_DIR
        return DATA_DIR
    return data_dir


def son_tarama_yolu(data_dir=None):
    return os.path.join(son_tarama_data_dir(data_dir), SON_TARAMA_DOSYA)


def digest_pending_yolu(data_dir=None) -> str:
    from config import DATA_DIR
    return os.path.join(data_dir or DATA_DIR, DIGEST_PENDING_DOSYA)


def kayit_zamani(veri) -> datetime | None:
    if not isinstance(veri, dict):
        return None
    try:
        return datetime.fromisoformat(veri.get("kayit_zamani"))
    except (TypeError, ValueError):
        return None


def yeni_snapshot(*adaylar):
    """Geçerli kopyalardan en yenisini seçer; bozuk kopya diğerini gölgelemez."""
    secilen = None
    for aday in adaylar:
        if not isinstance(aday, dict) or not isinstance(aday.get("formations"), list):
            continue
        if secilen is None:
            secilen = aday
            continue
        yeni_zaman, eski_zaman = kayit_zamani(aday), kayit_zamani(secilen)
        if yeni_zaman is None:
            continue
        if eski_zaman is None:
            secilen = aday
            continue
        try:
            if yeni_zaman > eski_zaman:
                secilen = aday
        except TypeError:
            # Eski naive kayıt ile timezone-aware kayıt karşılaştırılamazsa
            # mevcut tercih korunur (aday sırası: Supabase, yerel dosya).
            pass
    return secilen


# Haftalık doğruluk karnesi defteri (karne.py) — yerel dosya + opsiyonel uzak yedek.
KARNE_DEFTERI_DOSYA = "karne_defteri.json"
KARNE_DEFTERI_SUPABASE_KEY = "state:karne_defteri"


def karne_defteri_yolu(data_dir=None) -> str:
    from config import DATA_DIR
    return os.path.join(data_dir or DATA_DIR, KARNE_DEFTERI_DOSYA)


# Gönderim gün işaretleri: "gün sonu analizi bugün yapıldı mı?" gibi bayraklar.
# Neden kalıcı: damga yalnız bellekte tutulunca süreç yeniden başlayınca aynı iş
# (ör. 20:00 paneli) aynı gün ikinci kez çalışıyor ve mesaj tekrarlanıyordu.
GONDERIM_DURUMU_DOSYA = "gonderim_durumu.json"


def gonderim_durumu_yolu(data_dir=None) -> str:
    from config import DATA_DIR
    return os.path.join(data_dir or DATA_DIR, GONDERIM_DURUMU_DOSYA)


# Faz 2.1: çoklu formasyon history defteri — (stock,tf) başına bir dosya.
# `bot_data/{STOCK}.json` yazım kuralı taklit edilir; tek slot'lu
# formation_identity.json yerine birden fazla formasyonu taşıyabilir.
FORMATION_HISTORY_ALT_DOSYA = "formation_history"


def formation_history_yolu(stock, tf, data_dir=None) -> str:
    from config import DATA_DIR
    return os.path.join(data_dir or DATA_DIR, FORMATION_HISTORY_ALT_DOSYA,
                        "{}_{}.json".format(stock, tf))
