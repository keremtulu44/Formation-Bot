"""Grafik katmanı paketi (Faz 2) — G1 iskeleti.

grafik.py 2026-10-26'da grafik/ paketine bölündü (modülerleştirme planı,
docs/tasarim/MODULERLESTIRME_PLANI_2026-10-26.md). Dış API AYNI: `import grafik`
sonrası grafik.X aynı nesne/fonksiyonlar.

YAMA YÜZEYİ (test_patch_yuzeyi.py): grafik.kareyi_yaz, grafik.kare_yolu,
grafik.tempfile, grafik.shutil — kare.py'deki tanımlar burada yeniden dışa
aktarılır; `monkeypatch.setattr(grafik, "kareyi_yaz", ...)` aynen çalışır.

Not: `log` kaydı "grafik" adıyla (eski __name__ ile aynı) tutulur.
"""

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

try:  # yalnız kapanmış mum kuralı (§0.6); zincir koparsa kural devre dışı kalır
    from data import bar_kapandi_mi as _bar_kapandi_mi
except Exception:  # pragma: no cover - bağımlılık yoksa da import edilebilsin
    _bar_kapandi_mi = None

try:  # alarm etiketi gerçek state metninden (§0.12z) — yeni sözcük icat edilmez
    from notifier import PUBLIC_STATE_ETIKET as _STATE_ETIKET
    from notifier import _tr_tarih as _tarih_tr
except Exception:  # pragma: no cover
    _STATE_ETIKET = {}
    _tarih_tr = None

try:  # TF kısaltması mevcut eşlemeden alınır, yenisi yazılmaz (§14.5)
    from notification_context import TIMEFRAME_LABELS as _TF_KISA
except Exception:  # pragma: no cover
    _TF_KISA = {"1h": "1s", "2h": "2s", "4h": "4s", "1d": "1g"}


log = logging.getLogger("grafik")

from grafik.core import (  # noqa: F401
    PALET,
    PALET_TABAN,
    SABITLER,
    SABITLER_TABAN,
    _ALARM_KALIN,
    _AY,
    _BOLGE_ARA,
    _BOLGE_DOLU,
    _BOLGE_TAMAM,
    _CIZIM_KILIDI,
    _FVG_TIMEFRAMES,
    _FVG_YOK_TFLAR,
    _IKONLAR,
    _IKON_ONBELLEK,
    _KOLONLAR,
    _MOD,
    _ModKapsami,
    _OLCU_FIG,
    _PALET_RENK_KORUGU,
    _PLOT,
    _PLT_KURULDU,
    _PaletSarmalayici,
    _SabitlerSarmalayici,
    _ZAMAN_ANAHTARLARI,
    _ad,
    _alan,
    _alan_var,
    _butce_px,
    _cerceve_ayristir,
    _durum_adi,
    _font_emoji_var,
    _gercek,
    _ikon,
    _kadrajla,
    _kare_olcu,
    _kayit_listesi,
    _kirp,
    _metin_px,
    _mod_kapsami,
    _olcu_figir,
    _olcu_px,
    _ortam_bayrak,
    _ortam_sayi,
    _pyplot_getir,
    _rozet_px,
    _seri_cizim,
    _sigar_mi,
    _tam,
    _tarih,
    _tarih_metni,
    _wilder_atr,
    _yon,
    grafik_aktif_mi,
    grafik_kare_adedi,
    kare_mum_tavani,
    sag_bosluk_mum,
)
from grafik.geometry import (  # noqa: F401
    _bant_temaslari,
    _bolge,
    _formasyon_araligi,
    _formasyon_serileri,
    _gorunur_parcalar,
    _kapak_sayilari,
    _mum_kutulari_px,
    _ob_mitigated,
    _swing_ofseti,
    _yatay_aralik,
    _zone_durum_onceligi,
    _zone_havuzu,
    _zone_kalan_orani,
    _zone_renk,
)
from grafik.indicators import (  # noqa: F401
    _grafik_dis_yapi,
    _grafik_yapi_metni,
    _grafik_zone,
    _mum_cakisma_say,
    _rvol_katı,
)
from grafik.overlays import (  # noqa: F401
    ALARM_TURU_ESLEME,
    FORMASYON_DURUM_ETIKET,
    _ALARM_TURU,
    _CAPA_TAM,
    _FORMASYON_BOOL,
    _FORMASYON_METIN,
    _FORMASYON_SAYI,
    _POLE_TAM,
    _TUR_ETIKET,
    _alarm_kopyala,
    _direk_ciz,
    _formasyon_ciz,
    _formasyon_kopyala,
    _gecersiz_katmani,
    _isaret_listesi,
    alarm_turu_bul,
    formasyon_durum_etiketi,
)
from grafik.panels import (  # noqa: F401
    _ALT_ADIM,
    _LEJANT_DUSUK,
    _LEJANT_KORU,
    _alt_yerlesim,
    _lejant,
    _lejant_satirlar,
    _metinler,
    _sag_ciz,
    _sag_ele,
    _sag_panel,
    _sag_sirali_yerlesim,
    _serit_ciz,
    _zone_metni,
    _zone_sag_adaylari,
)
from grafik.markers import (  # noqa: F401
    _alarm_ciz,
    _kutu_yazisi_koy,
    _kutu_yazisi_sigar,
    _metin_ciz,
    _olay_ciz,
    _olay_yazi_koy,
    _projeksiyon_ciz,
    _rozet_ciz,
    _rvol_rozetleri,
    _tik_etiketleri,
    _zone_etiket_engeller,
)
from grafik.tarama import (  # noqa: F401
    _atom_yaz,
    _meta_kur,
    _olay_meta,
    _olay_verisi,
    _serit_meta,
    _serit_verisi,
    _yapı_satırı,
    _zone_meta,
    anlik_goruntu,
    girdi_ozeti,
)
from grafik.render import (  # noqa: F401
    _cizgi_ve_alan,
    _guven_ciz,
    _guven_satirlari,
    _kare_ciz,
    _kare_ciz_modlu,
    _mumlar_ciz,
    _zone_ciz,
    _zone_kunye,
    ciz,
)
from grafik.kare import (  # noqa: F401
    DISK_MIN_BOS_MB,
    KARE_DESEN,
    KARE_OMR_SN,
    _MOTOR_ANAHTARLARI,
    _TEK_KARE_ALARM,
    _sonuc_sec,
    _zaman_bul,
    bayat_kareleri_supur,
    disk_uygun_mu,
    kare_listesi,
    kare_yolu,
    kareyi_yaz,
)
