"""Gölge defter — atomik JSONL kayıt (karne/outcome_link kalıbı, yan okuyucu).

Kurallar:
* Her satır tek ``write`` + ``flush`` ile yazılır (satır atomikliği);
* Kayıt ya ``modeller`` dataclass'ı ya da ``tip`` alanı olan dict'tir;
  ``tip`` kümesi dışı kayıt **yazılmaz**;
* Bozuk satır okumada atlanır (defter bütünlüğü bozulmaz);
* Bu dosya canlıya gitmez; tek çıktı yeri gölge defter + rapordur.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from .modeller import KAYIT_TIPLERI, Bildirim, Hukum, IslemSonucu, PlanKaydi

_MODELLER = (Bildirim, Hukum, PlanKaydi, IslemSonucu)


class GolgeDefter:
    """JSONL gölge defteri (append-only)."""

    def __init__(self, yol: str | Path) -> None:
        self.yol = Path(yol)
        self.yol.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.yol, "a", encoding="utf-8")  # noqa: SIM115 — yaşam döngüsü yöneticisi açıkça
        self._sayac: Counter[str] = Counter()

    # --- yazım ------------------------------------------------------------
    def yaz(self, kayit: Mapping[str, Any] | Any) -> None:
        if isinstance(kayit, _MODELLER):
            veri = kayit.to_dict()
        elif isinstance(kayit, Mapping):
            veri = dict(kayit)
        else:
            raise TypeError(f"desteklenmeyen kayit tipi: {type(kayit)!r}")
        tip = veri.get("tip")
        if tip not in KAYIT_TIPLERI:
            raise ValueError(f"tip kumesi disi: {tip!r}")
        satir = json.dumps(veri, ensure_ascii=False, separators=(",", ":"),
                           sort_keys=True)
        if "\n" in satir:
            raise ValueError("JSON satiri new-line iceremez")
        self._fh.write(satir + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self._sayac[tip] += 1

    def yaz_coklu(self, kayitlar: Iterable[Any]) -> int:
        n = 0
        for k in kayitlar:
            self.yaz(k)
            n += 1
        return n

    # --- okuma ------------------------------------------------------------
    @staticmethod
    def oku(yol: str | Path) -> tuple[list[dict[str, Any]], int]:
        """Tüm satırları okur; bozuk satırları atlar → (kayitlar, bozuk_sayisi)."""
        kayitlar: list[dict[str, Any]] = []
        bozuk = 0
        p = Path(yol)
        if not p.exists():
            return kayitlar, bozuk
        with open(p, encoding="utf-8") as fh:
            for satir in fh:
                satir = satir.strip()
                if not satir:
                    continue
                try:
                    veri = json.loads(satir)
                except json.JSONDecodeError:
                    bozuk += 1
                    continue
                if not isinstance(veri, dict) or veri.get("tip") not in KAYIT_TIPLERI:
                    bozuk += 1
                    continue
                kayitlar.append(veri)
        return kayitlar, bozuk

    def sayac(self) -> dict[str, int]:
        return dict(self._sayac)

    # --- yaşam döngüsü ----------------------------------------------------
    def kapat(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> "GolgeDefter":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.kapat()

    def __iter__(self) -> Iterator[dict[str, Any]]:
        kayitlar, _ = self.oku(self.yol)
        return iter(kayitlar)
