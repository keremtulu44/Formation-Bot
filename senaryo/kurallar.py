"""Sermaye/korunma kuralları — sayılarla uygulanır, hisle değil.

Üç kural (plan belgesi §6; **ölçüm katmanında** uygulanır — zincir ham veri
yazmaya devam eder):

1. **streak**: sembol×TF'de 3 üst üste stop → sıradaki işlem atlanır
   (Faz 0: "günde 2 stop" hiç tetiklenmiyordu; gerçek risk üst üste serilerde).
2. **tavan**: eşzamanlı açık işlem tavanı (giriş + H bar süresi yaklaşımı;
   kapanış önce işlenir → tavan sıkı sayılır).
3. **gun_durdur** (eski kural, teyit amaçlı): aynı günde 2 stop → gün sonu dur.

Her fonksiyon ham kayıtları alır, **kural etiketli yeni kopya** döndürür;
ham kayıt asla değiştirilmez. Özet dictleri ölçüme girer.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

STREAK_ESIK = 3
TAVAN = 3
GUN_STOP_ESIK = 2

_TF_DK = {"1h": 60, "2h": 120, "4h": 240, "1d": 1440}


def _kimlik(r: Mapping[str, Any]) -> tuple:
    return (str(r.get("sembol")), str(r.get("tf")), int(r.get("bar_index", -1)))


def _zaman(r: Mapping[str, Any]) -> datetime:
    try:
        return datetime.fromisoformat(str(r.get("t", "")))
    except ValueError:
        return datetime.min


def _sira_kronolojik(kayitlar: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(kayitlar, key=lambda r: (_zaman(r), _kimlik(r)))


def _sira_bar(kayitlar: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(kayitlar, key=lambda r: (str(r.get("sembol")), str(r.get("tf")),
                                           int(r.get("bar_index", 0))))


def streak_uygula(
    kayitlar: Sequence[Mapping[str, Any]],
    esik: int = STREAK_ESIK,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """3 üst üste stoptan sonraki işlemi atla (sembol×TF kronolojik)."""
    out: list[dict[str, Any]] = []
    ust: dict[tuple[str, str], int] = defaultdict(int)
    enbuyuk: dict[tuple[str, str], int] = defaultdict(int)
    atlanan = 0
    for r in _sira_bar(kayitlar):
        k = (str(r.get("sembol")), str(r.get("tf")))
        kayit = dict(r)
        if ust[k] >= esik:
            kayit["kural"] = "streak_atla"
            atlanan += 1
            ust[k] = 0                      # atlama sonrası sayaç sıfırlanır
        else:
            kayit["kural"] = "kural_yok"
            if r.get("sonuc") == "stop":
                ust[k] += 1
                enbuyuk[k] = max(enbuyuk[k], ust[k])
            else:
                ust[k] = 0
        out.append(kayit)
    seriler = list(enbuyuk) or [None]
    return out, {
        "kural": f"sembol×TF {esik} üst üste stop → sıradaki atla",
        "atlanan": atlanan,
        "toplam": len(out),
        "streak_3plus_seri_yuzde": round(
            100 * sum(1 for v in enbuyuk.values() if v >= esik) / max(1, len(seriler)), 2),
        "streak_maks": max(enbuyuk.values(), default=0),
    }


def gun_durdur_uygula(
    kayitlar: Sequence[Mapping[str, Any]],
    stop_esik: int = GUN_STOP_ESIK,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Aynı gün ``stop_esik`` stop → o günün kalan işlemleri atlanır."""
    out: list[dict[str, Any]] = []
    gun_stop: dict[tuple[str, str, str], int] = defaultdict(int)
    atlanan = 0
    for r in _sira_kronolojik(kayitlar):
        gun = str(r.get("t", ""))[:10]
        k = (str(r.get("sembol")), str(r.get("tf")), gun)
        kayit = dict(r)
        if gun_stop[k] >= stop_esik:
            kayit["kural"] = "gun_durdur_atla"
            atlanan += 1
        else:
            kayit["kural"] = "kural_yok"
            if r.get("sonuc") == "stop":
                gun_stop[k] += 1
        out.append(kayit)
    return out, {
        "kural": f"aynı gün {stop_esik} stop → gün sonu dur (eski kural)",
        "atlanan": atlanan,
        "toplam": len(out),
        "tetiklenen_gun_sayisi": sum(1 for v in gun_stop.values() if v >= stop_esik),
    }


def tavan_uygula(
    kayitlar: Sequence[Mapping[str, Any]],
    tavan: int = TAVAN,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Eşzamanlı açık işlem tavanı (giriş anında doluysa yeni işlem açılmaz)."""
    def sure_dk(r: Mapping[str, Any]) -> int:
        h = int(r.get("H", 10) or 10)
        return _TF_DK.get(str(r.get("tf", "1h")), 60) * h

    sirali = _sira_kronolojik(kayitlar)
    olaylar: list[tuple[datetime, int, int]] = []   # (zaman, tur, sıra); tur: 1=açılış, 0=kapanış
    for no, r in enumerate(sirali):
        bas = _zaman(r)
        olaylar.append((bas + timedelta(minutes=sure_dk(r)), 0, no))
        olaylar.append((bas, 1, no))
    olaylar.sort(key=lambda e: (e[0], e[1]))        # kapanış önce → tavan sıkı

    acik = 0
    tepe = 0
    acik_olan: set[int] = set()
    atlanan_no: set[int] = set()
    for _zaman_an, tur, no in olaylar:
        if tur == 1:
            if acik >= tavan:
                atlanan_no.add(no)
            else:
                acik += 1
                acik_olan.add(no)
                tepe = max(tepe, acik)
        else:
            if no in acik_olan:
                acik -= 1
                acik_olan.discard(no)

    atlanan_kimlik = {_kimlik(sirali[no]) for no in atlanan_no}
    out: list[dict[str, Any]] = []
    for r in _sira_bar(kayitlar):
        kayit = dict(r)
        kayit["kural"] = "tavan_atla" if _kimlik(r) in atlanan_kimlik else "kural_yok"
        out.append(kayit)
    return out, {
        "kural": f"eşzamanlı tavan {tavan}",
        "atlanan": len(atlanan_no),
        "toplam": len(out),
        "en_yuksek_eszamanli": tepe,
    }
