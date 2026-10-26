# --- TELEGRAM NOTIFIER - İNSANLAŞTIRMA V2 + KANAL MODELİ (paket, Faz 1) ---
# notifier.py 2026-10-26'da notifier/ paketine bölündü (modülerleştirme planı,
# docs/tasarim/MODULERLESTIRME_PLANI_2026-10-26.md). Dış API AYNI:
# `from notifier import TelegramNotifier, devamlilik_puani` çalışır.
#
# YAMA YÜZEYİ (test_patch_yuzeyi.py): yamalanan config kopyaları AŞAĞIDA,
# bu dosyada durur; alt modüller bunları `_pkg.X` ile çağrı anında okur.
# Böylece `monkeypatch.setattr(notifier, "DATA_DIR", ...)` gibi yamalar
# aynen çalışmaya devam eder (plan §3).

import os
import logging
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config import (ACTIVE_STOCKS, DATA_DIR, ISTANBUL_TZ, TELEGRAM_MAX_MESAJ_SAAT,
                    TELEGRAM_MAX_MESAJ_GUN,
                    TELEGRAM_ALERT_STYLE, TELEGRAM_ALERT_MAX_KARAKTER, TELEGRAM_SATIR_PX,
                    TELEGRAM_KART_SUZGEC,
                    TELEGRAM_DM_DEGISIM_KAPISI, TELEGRAM_KANAL_GECERSIZ_KAPISI,
                    ACIL_KUYRUK_LIMIT, ACIL_KUYRUK_TTL_DK, ALERT_STATES, WATCH_STATES,
                    TERMINAL_TAZE_BAR,
                    ALERT_MIN_QUALITY, ALERT_MIN_QUALITY_GLOBAL,
                    PUBLIC_MAX_MESAJ_SAAT, PUBLIC_MAX_MESAJ_GUN, PUBLIC_MIN_ARALIK_SN,
                    PUBLIC_MIN_QUALITY_TF, PUBLIC_MIN_DEVLAMLILIK, DM_MIN_DEVLAMLILIK,
                    DEVLAMLILIK_AKTIF)
# Telefon satır bütçesi ölçeri (bağımlılıksız, PIL yok). Eski "satır ≤ 70 karakter"
# kuralı Türkçe/rakam genişliklerini hesaba katmadığı için 25 Eyl akışında 120
# satır telefonda sarmalanmıştı; artık piksel bütçesi kullanılıyor.
from telegram_measure import (SATIR_BUTCE, bol as _satir_bol,
                              genislik, genislik as _satir_px, metni_sigdir)
# Watch adaylarının state'ini Türkçe basmak için TEK KAYNAK sözlük (reporting
# katmanı da aynısını kullanır; böylece alarm mesajı ile /panel aynı dili konuşur).
from reporting.format import STATE_TR, sayi as _format_sayi
# Devamlılık puanı ARTIK KARTTA YOK (§11–§12): 0–100 puan tek bayraktan iyi
# çıkmadı, ondan türeyen "yüksek/normal/zayıf" etiketi de ölçümün taşımadığı bir
# hükümdü. Puan yalnız log/sıralama/gölge kayıt içinde yaşıyor. Geometri
# (confidence_score) artık yalnız bildirim eşiğini besler, kartta okunmaz.
# Ölçüm: docs/arastirma/FAZLA_ANALIZI_2026-10-25.md, PUANLAMA_MIMARISI_2026-10-25.md
import devamlilik as _dev
# Günlük public durumu (bütçe sayaçları + gönderilememiş kuyruk) restart'ta
# korunsun diye kalıcılık katmanı kullanılır (canlı denetim: ikisi de kayboluyordu).
from state import persistence as _state_persistence

from secrets_redaction import redact_sensitive_text



logger = logging.getLogger("notifier")

# Alt modüller (tek yönlü: util → format_* → api).
from notifier.util import (  # noqa: F401,E501  (dış API + format/api iç kullanımı)
    CONFIRMED_PUBLIC_STATES,
    KRITIK_STATELER,
    PATTERN_EMOJI,
    PUBLIC_STATE_ETIKET,
    TF_EVENT_HUMAN,
    TF_HUMAN,
    TF_KISA,
    _AY_KISALTMALARI,
    _ENGEL_SAYACLAR,
    _FORMATION_ALERT_MUHR_TTL_SAAT,
    _KART_AYLAR,
    _KART_MAKS_SATIR,
    _KART_OLAY,
    _KART_OLAY_KISA,
    _KART_UST_TF,
    _KART_UST_TF_SOZ,
    _KART_YON,
    _PUBLIC_MAX_METIN,
    _TF_BAR_SAAT,
    _dm_anahtar,
    _dm_imza,
    _env_temizle,
    _evren_ozeti,
    _format_price,
    _format_price_tl,
    _grafik_basligi,
    _grafik_dipnotu,
    _grafik_salteri_acik,
    _istanbul,
    _kirp,
    _kuyruk_verisi,
    _muhur_ttl_saat,
    _px_butce,
    _satir,
    _sayı,
    _summary_int,
    _tr_tarih,
    _yon_kisa,
    _yon_metni,
    _yuzde,
    telegram_hata_ipucu,
    token_bicimi_uygun_mu,
)
from notifier.format_kart import (  # noqa: F401
    _format_lifecycle_alert,
    _format_lifecycle_alert_kart,
    _format_lifecycle_alert_kart_sade,
    _format_lifecycle_alert_klasik,
    _kart_bant,
    _kart_daralma,
    _kart_esik,
    _kart_esik_px,
    _kart_mum_damgasi,
    _kart_sigan,
    _kart_suzgec_aktif,
    _kart_temas,
    _kart_yas_metni,
    _quality_grade,
    devamlilik_puani,
    quality_comment,
    quality_emoji,
)
from notifier.format_summary import (  # noqa: F401
    _public_izleme_adaylari,
    _summary_last_full_scan,
    _summary_lifecycle_counts,
)
from notifier.api import TelegramNotifier  # noqa: F401
