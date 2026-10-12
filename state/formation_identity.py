"""Phase 1 — Persistent Formation Identity anchor store.

Her ``(stock, timeframe)`` için son aktif formation'un kalıcı kimlik anchor'unu
saklar. Bot restart olduğunda ``ArgentEngine`` aynı formation'ı yeniden tespit
ettiğinde bu anchor ile eşleştirip eski ``stable_id``'yi yeniden bağlar.

Kapsam: yalnız Formation Identity. Formation matematiği, geometri, kalite,
continuity_score ve lifecycle state geçişleri burada dokunulmaz; yalnızca
``identity_compatible`` + ``continuity_score`` (mevcut eşiklerle) kullanılır.

Anchor'da saklananlar: stable_id + (stock, timeframe) + formation'ı yeniden
eşleştirmek için gerekli MINIMUM yapı (pivot çekirdeği, family, yön, başlangıç
barı). Kalite/geometri/anlık fiyat alanları bilinçli olarak persist edilmez.
"""
import json
import os
import threading
from typing import Any, Dict, Optional

_DOSYA = "formation_identity.json"
_lock = threading.Lock()


def _yol(data_dir: Optional[str] = None) -> str:
    if data_dir is None:
        from config import DATA_DIR
        data_dir = DATA_DIR
    return os.path.join(data_dir, _DOSYA)


def _yukle(data_dir: Optional[str] = None) -> Dict[str, Any]:
    """Tüm anchor haritasını okur: ``{"STOCK|TF": {anchor...}, ...}``."""
    try:
        with open(_yol(data_dir), "r", encoding="utf-8") as f:
            veri = json.load(f)
        return veri if isinstance(veri, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _kaydet(veri: Dict[str, Any], data_dir: Optional[str] = None) -> None:
    """Atomik yazım (tmp + os.replace); hiçbir I/O hatası yukarı sızmaz."""
    try:
        yol = _yol(data_dir)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        gecici = yol + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2, default=str)
        os.replace(gecici, yol)
    except OSError:
        pass


def load_anchor(stock: str, tf: str, data_dir: Optional[str] = None) -> Optional[dict]:
    """(stock, tf) için saklı anchor'u döndürür; yoksa None."""
    return _yukle(data_dir).get(f"{stock}|{tf}")


def save_anchor(anchor: dict, data_dir: Optional[str] = None) -> bool:
    """Anchor'u (stock, tf) anahtarıyla kaydeder. Eksik anahtar olursa yazmaz."""
    if not anchor.get("stock") or not anchor.get("timeframe") or not anchor.get("stable_id"):
        return False
    with _lock:
        veri = _yukle(data_dir)
        veri[f"{anchor['stock']}|{anchor['timeframe']}"] = anchor
        _kaydet(veri, data_dir)
    return True
