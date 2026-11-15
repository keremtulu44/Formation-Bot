"""Gölge v2 (Shadow v2) — nedensel, simetrik (Long + Short), sığ bağlamlı plan değerlendirme paketi.

Bu paket canlı ürüne (`bot/`, `patterns/`, `grafik/`, `notifier/`, `domain_engines/`, `data/`)
ve v1 gölge motoruna (`senaryo/`) kesinlikle dokunmaz; yalnızca araştırma ve ablasyon içindir.
"""

from typing import Any

from .modeller import (
    BOS_TAZELIK_PENCERE,
    FREN_ARDISIK_STOP,
    KESIM_TARIHI,
    KOPUKLUK_ESIK_ORAN,
    KOPUKLUK_KARANTINA_BAR,
    MAX_BEKLEME_LIMIT,
    MS_BAYAT_ESIK_ATR,
    RUNWAY_MIN_ATR,
    SIKISMA_MIN_ATR,
    TAMPON_VARSAYILAN_ATR,
    TEZ_IPTAL_BAR,
    TF_LISTESI,
    UFUK_VARSAYILAN_BAR,
    AdayOlay,
    BarDurum,
    BlokBand,
    PlanKartV2,
    SeriVerisi,
    YarisSonucuV2,
)

# İşlem-içi süreç izleme adları `senaryo_v2.surec` / `senaryo_v2.yaris` içinde yaşar. Bu
# modüller formasyon paketini yüklediği için buradan TEMBEL dışa açılır: `import senaryo_v2`
# hafif kalır, `from senaryo_v2 import SurecGozcusu` yine çalışır.
_TEMBEL_ADLAR: dict[str, str] = {
    "SEVIYE_BOZULMA_BAR": "surec",
    "TEZ_BEKLIYOR": "surec",
    "TEZ_TEYITLI": "surec",
    "TEZ_SINANIYOR": "surec",
    "TEZ_BOZULDU": "surec",
    "OLAY_KUTBU": "surec",
    "olay_kutbu": "surec",
    "SurecGozcusu": "surec",
    "SurecGozlem": "surec",
    "SurecOzeti": "surec",
    "SurecKarari": "surec",
    "SurecPolitikasi": "surec",
    "YonetimDurumu": "surec",
    "OlaydaCik": "surec",
    "TezDurumundaCik": "surec",
    "KarKoruma": "surec",
    "HedefteIzSur": "surec",
    "HedefteYapiIzSur": "surec",
    "surec_ozetle": "surec",
    "YarisIzi": "yaris",
    "surecli_yaris": "yaris",
    "yarisi_yurut": "yaris",
    "fren_etiketle": "yaris",
}


def __getattr__(ad: str) -> Any:
    modul = _TEMBEL_ADLAR.get(ad)
    if modul is None:
        raise AttributeError(f"module {__name__!r} has no attribute {ad!r}")
    from importlib import import_module

    deger = getattr(import_module(f"{__name__}.{modul}"), ad)
    globals()[ad] = deger
    return deger


__all__ = [
    "BOS_TAZELIK_PENCERE",
    "FREN_ARDISIK_STOP",
    "KESIM_TARIHI",
    "KOPUKLUK_ESIK_ORAN",
    "KOPUKLUK_KARANTINA_BAR",
    "MAX_BEKLEME_LIMIT",
    "MS_BAYAT_ESIK_ATR",
    "RUNWAY_MIN_ATR",
    "SIKISMA_MIN_ATR",
    "TAMPON_VARSAYILAN_ATR",
    "TEZ_IPTAL_BAR",
    "TF_LISTESI",
    "UFUK_VARSAYILAN_BAR",
    "AdayOlay",
    "BarDurum",
    "BlokBand",
    "PlanKartV2",
    "SeriVerisi",
    "YarisSonucuV2",
    *_TEMBEL_ADLAR,
]
