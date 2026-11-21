"""scripts/politika_parite_kontrol.py

Canlı `_baglam_sikisma_kosu` (bot/domain_alarm_service.py) ile replay
`baglam_satiri`'nin (research/domain_alarm_replay.py) **aynı bar için aynı
sikisma/kosu** ürettiğini native arşiv üzerinde doğrular.

Kullanım:
    python -m scripts.politika_parite_kontrol [--sembol 20] [--tf 4h]

Neden: politika canlıya alındığında replay'de ölçülen 97 → 36 kart düşüşünün
gerçekten aynı eşiklerle oluştuğunu kanıtlamak için. Fark varsa filtre canlıda
replay'den farklı davranır ve ölçüm kâğıt üzerinde kalır.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from bot.domain_alarm_service import _baglam_sikisma_kosu
from research.arsiv import ham_frame
from research.domain_alarm_replay import _atr_dizisi, baglam_satiri


def _seriler(limit: int) -> list[tuple[str, str, Path]]:
    """backfill_data/SEMBOL_TF.csv.gz → (sembol, tf, yol)."""
    kok = Path("backfill_data")
    bulunan: list[tuple[str, str, Path]] = []
    for dosya in sorted(kok.glob("*.csv.gz")):
        govde = dosya.name[: -len(".csv.gz")]
        if "_" not in govde:
            continue
        sembol, tf = govde.rsplit("_", 1)
        if tf not in ("1h", "2h", "4h", "1d"):
            continue
        bulunan.append((sembol, tf, dosya))
    return bulunan[:limit]


def kontrol(limit: int = 20) -> dict:
    farklar: list[dict] = []
    karsilastirilan = 0
    for sembol, tf, yol in _seriler(limit):
        try:
            frame = ham_frame(sembol, tf)
        except Exception as exc:  # noqa: BLE001 - eksik dosya kontrolü durdurmasın
            farklar.append({"seri": f"{sembol}/{tf}", "hata": str(exc)})
            continue
        if frame is None or len(frame) < 60:
            continue
        index = len(frame) - 1
        canli_sik, canli_kosu = _baglam_sikisma_kosu(frame)
        replay = baglam_satiri(frame, index, _atr_dizisi(frame))
        replay_sik = replay.get("bagl_sikisma")
        replay_kosu = replay.get("bagl_gunici_kosu")
        karsilastirilan += 1
        for ad, canli, beklenen in (
            ("sikisma", canli_sik, replay_sik),
            ("kosu", canli_kosu, replay_kosu),
        ):
            ayni = (
                (canli is None and beklenen is None)
                or (
                    canli is not None
                    and beklenen is not None
                    and abs(float(canli) - float(beklenen)) <= 1e-3
                )
            )
            if not ayni:
                farklar.append(
                    {
                        "seri": f"{sembol}/{tf}",
                        "alan": ad,
                        "canli": canli,
                        "replay": beklenen,
                        "bar": index,
                    }
                )
    return {"karsilastirilan": karsilastirilan, "fark": len(farklar), "detay": farklar[:20]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seri", type=int, default=40, help="karşılaştırılacak seri sayısı")
    args = ap.parse_args()
    sonuc = kontrol(args.seri)
    print(json.dumps(sonuc, ensure_ascii=False, indent=2))
    return 0 if sonuc["fark"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
