"""Senaryo motoru — gölge zincir paketi (yan okuyucu, canlı karar değiştirmez).

Bu paket ana sisteme dokunmaz: yalnızca mevcut motor çıktılarını okur,
bildiri → TYR → plan kartı → simülasyon → ölçüm zincirini üretir.
Tek çıktı yeri gölge defterdir (sözleşme §1).
"""

from .modeller import Bildirim, Hukum, IslemSonucu, PlanKaydi
from .defter import GolgeDefter
from .zaman import as_of, son_kapanis, ust_tf_kapandi_mi

__all__ = [
    "Bildirim",
    "Hukum",
    "IslemSonucu",
    "PlanKaydi",
    "GolgeDefter",
    "as_of",
    "son_kapanis",
    "ust_tf_kapandi_mi",
]
