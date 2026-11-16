"""Kayıtlı Stabil ok replay'inden (events.csv.gz) ok kalitesi analizi.

Kullanım: python scripts/stabil_ok_kalite_analizi.py [events.csv.gz yolu]

Yalnız kayıtlı replay'i okur; ağ/Telegram yok. Ölçü: 8 bar içinde
MFE < 0,5 ATR = "zayıf tepki". Çıktı gözlemsel grup karşılaştırmasıdır;
nedensellik/filtre kanıtı değildir (örtüşen pencereler, ortak tarih şokları).
"""
import sys

import pandas as pd

YOL = sys.argv[1] if len(sys.argv) > 1 else (
    "docs/arastirma/stabil_ok_replay_2026_11_05/events.csv.gz")


def grup(df, kolon):
    g = df.groupby(kolon).agg(
        n=("weak_mfe_8", "size"),
        zayif=("weak_mfe_8", "mean"),
        once_yukari=("first_1atr_8", lambda s: (s == "UP_FIRST").mean()),
        medyan_kapanis=("return_atr_8", "median"))
    g["zayif"] = (g["zayif"] * 100).round(1)
    g["once_yukari"] = (g["once_yukari"] * 100).round(1)
    return g.round(2)


def main():
    df = pd.read_csv(YOL)
    up = df[(df.event_class == "UP_ARROW") & (df.status_8 == "VALID")]
    print(f"Geçerli ▲ (8 bar): {len(up)}  ·  baz zayıf oran: "
          f"%{up.weak_mfe_8.mean() * 100:.1f}")
    for kolon, baslik in (("kind", "Ok türü"), ("regime_proxy", "Destek rejimi"),
                          ("volume_bucket", "Hacim kovası (20 bar oranı)"),
                          ("fvg_ahead", "Öndeki FVG"), ("ob_ahead", "Öndeki OB")):
        print(f"\n--- {baslik} ---")
        print(grup(up, kolon).to_string())
    # Aday filtrelerin dürüst testi: veri desteklemiyorsa raporda öyle yazar.
    adaylar = {
        "hacim >= 1,2": up.volume_ratio20 >= 1.2,
        "gövde >= 0,6 ATR": up.body_atr >= 0.6,
        "süpürme hariç": up.kind != "intrabar_sweep_reclaim",
        "çizgiye 0,1-0,5 ATR": up.distance_atr.between(0.1, 0.5),
    }
    print("\n--- Aday fikirler (baz: %24,9 zayıf) ---")
    for ad, maske in adaylar.items():
        s = up[maske]
        print(f"{ad}: n={len(s)}  zayıf %{s.weak_mfe_8.mean() * 100:.1f}  "
              f"+1 ATR önce %{(s.first_1atr_8 == 'UP_FIRST').mean() * 100:.1f}")


if __name__ == "__main__":
    main()
