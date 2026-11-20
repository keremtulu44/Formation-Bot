"""Aralık KONİSİ grafiği — "yön oku" yerine ölçümün söylediğini çizen prototip.

Sorun: mevcut kartlarda alarm sonrası yön oku (▲/▼) var. Ölçüm ise şunu
söylüyor: tetiklerin **%30,5'i 12 barda iki yöne de ≥1 ATR** görüyor ve medyan
tepe ≈ medyan dip (3,19 vs 3,1 ATR). Yani ok, ölçümün yalan söylediği tek şey.

Bu modül okun yerine üç şey çizer:

1. **Konili aralık** — tetikten sonraki N bar için medyan lehte/aleyhte ATR
   yolu (kalın bant = %80 kapsama, ince çizgi = medyan).
2. **Tekrar sayısı** — bölgeye kaçıncı temas (Stabil: 2. iyi, 3.+ kötü;
   FVG: tek kullanımlık → 2. temasta çizgi griye düşer).
3. **Bağlam ölçüleri** — sıkışma / koşu / ATR yüzdelik, sıfat değil sayı olarak.

Kullanım::

    python -m research.koni_grafik --sembol ASELS --tf 4h --bar -120 \\
        --cikti var/koni/asels_4h.png

Bu **araştırma prototipi**dir: canlı çizim hattını (`grafik/render.py`)
değiştirmez, ayrı bir PNG üretir. Canlıya alınması kullanıcı kararıdır.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

#: Koninin çizildiği ufuk (bar).
KONI_BAR = 12
#: Kalın bandın kapsama oranı (yüzdelik).
BANT_P = 0.80


def _matplotlib() -> Any:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt
    except ImportError as exc:  # pragma: no cover - ortam eksikliği
        raise SystemExit("matplotlib gerekli: pip install matplotlib") from exc


def koni_yolu(ornekler: Sequence[tuple[Sequence[float], Sequence[float]]]) -> dict[str, list[float]]:
    """Geçmiş tetiklerin ATR yollarından koni istatistikleri.

    ``ornekler``: her eleman ``(yukari, asagi)``; ikisi de ATR cinsinden
    bar bar uzanım (yukarı: high-close, aşağı: close-low). İkisi AYRI
    hesaplanır — piyasa simetrik değil ve ölçüm de bunu gösteriyor.
    """
    if not ornekler:
        return {"yuk_med": [], "yuk_p80": [], "asg_med": [], "asg_p80": [], "n": 0}
    yuk = pd.DataFrame([list(o[0]) for o in ornekler])
    asg = pd.DataFrame([list(o[1]) for o in ornekler])
    ust_p = 1 - (1 - BANT_P) / 2  # %90 (tek taraflı %80 kapsama)
    return {
        "yuk_med": yuk.median(axis=0).tolist(),
        "yuk_p80": yuk.quantile(ust_p, axis=0).tolist(),
        "asg_med": asg.median(axis=0).tolist(),
        "asg_p80": asg.quantile(ust_p, axis=0).tolist(),
        "n": len(ornekler),
    }


def ciz(
    frame: pd.DataFrame,
    tetik_index: int,
    cikti: Path,
    *,
    sembol: str = "",
    tf: str = "",
    temas: int = 1,
    baglam: dict[str, Any] | None = None,
    atr: float | None = None,
) -> Path:
    plt = _matplotlib()
    from matplotlib.patches import Polygon  # yerel import: matplotlib zorunlu değil

    n = len(frame)
    if not (0 <= tetik_index < n):
        raise SystemExit(f"tetik_index aralık dışı: {tetik_index} (bar sayısı {n})")

    # --- Koniyi TARİHSEL tetiklerden kur (lookahead yok: koni, tetikten ÖNCE
    # oluşmuş tetiklerin sonraki 12 barıyla hesaplanır; bu bir prototiptir ve
    # rapor bunu açıkça yazar).
    atr_serisi = _atr(frame)
    atr_deger = float(atr) if atr else float(atr_serisi.iloc[tetik_index])
    yuksekler = frame["high"].astype(float).to_numpy()
    dusukler = frame["low"].astype(float).to_numpy()
    kapanislar = frame["close"].astype(float).to_numpy()
    ornekler: list[tuple[list[float], list[float]]] = []
    pencere = 200
    for i in range(max(0, tetik_index - pencere), tetik_index):
        if i + KONI_BAR >= n:
            continue
        a = float(atr_serisi.iloc[i])
        if not math.isfinite(a) or a <= 0:
            continue
        ref = float(kapanislar[i])
        ornekler.append((
            [(float(yuksekler[i + k]) - ref) / a for k in range(1, KONI_BAR + 1)],
            [(ref - float(dusukler[i + k])) / a for k in range(1, KONI_BAR + 1)],
        ))
    koni = koni_yolu(ornekler)

    gorunum = 60
    bas = max(0, tetik_index - gorunum)
    parca = frame.iloc[bas: tetik_index + KONI_BAR + 12]
    x = list(range(len(parca)))
    ofset = tetik_index - bas

    fig, ax = plt.subplots(figsize=(11, 6), dpi=110)
    for i, (_, satir) in enumerate(parca.iterrows()):
        renk = "#26a69a" if float(satir["close"]) >= float(satir["open"]) else "#ef5350"
        ax.plot([i, i], [float(satir["low"]), float(satir["high"])], color=renk, lw=0.8)
        ax.plot(
            [i - 0.28, i + 0.28],
            [float(satir["open"]), float(satir["open"])],
            color=renk, lw=0.8,
        )
        ax.plot(
            [i - 0.28, i + 0.28],
            [float(satir["close"]), float(satir["close"])],
            color=renk, lw=0.8,
        )

    referans = float(frame["close"].iloc[tetik_index])
    ax.axvline(ofset, color="#888888", ls="--", lw=1)
    ax.annotate(
        f"tetik · {temas}. temas" if temas else "tetik",
        xy=(ofset, referans), xytext=(ofset + 0.5, referans),
        fontsize=9, color="#444444", va="center",
    )

    # --- Konİ: referanstan başlar, iki yöne AYRI açılır
    if koni["yuk_med"]:
        xs = list(range(ofset + 1, ofset + 1 + len(koni["yuk_med"])))
        ust = [referans + v * atr_deger for v in koni["yuk_p80"]]
        alt = [referans - v * atr_deger for v in koni["asg_p80"]]
        ax.add_patch(Polygon(
            list(zip(xs, ust)) + list(zip(reversed(xs), reversed(alt))),
            closed=True, facecolor="#5c6bc0", alpha=0.16, edgecolor="none",
            label=f"%80 aralık (n={koni['n']})",
        ))
        ax.plot(xs, [referans + v * atr_deger for v in koni["yuk_med"]],
                color="#3949ab", lw=1.6, label="medyan yukarı")
        ax.plot(xs, [referans - v * atr_deger for v in koni["asg_med"]],
                color="#8e24aa", lw=1.6, label="medyan aşağı")
        # 12. barda değerler — ok yerine iki sayı
        ax.annotate(
            f"+{koni['yuk_med'][-1]:.1f} ATR",
            xy=(xs[-1], referans + koni["yuk_med"][-1] * atr_deger),
            xytext=(4, 4), textcoords="offset points", fontsize=8.5, color="#3949ab",
        )
        ax.annotate(
            f"−{koni['asg_med'][-1]:.1f} ATR",
            xy=(xs[-1], referans - koni["asg_med"][-1] * atr_deger),
            xytext=(4, -10), textcoords="offset points", fontsize=8.5, color="#8e24aa",
        )

    # --- Bağlam kutusu: sıfat değil sayı
    b = baglam or {}
    satirlar = [f"{sembol} · {tf}"]
    if atr_deger:
        satirlar.append(f"ATR {atr_deger:.2f}")
    for anahtar, etiket, bicim in (
        ("sikisma", "sıkışma", "{:.2f}"),
        ("gunici_kosu", "koşu", "{:+.2f} ATR"),
        ("atr_yuzdelik", "ATR yüzdelik", "%{:.0f}"),
        ("seans", "seans", "{}:00"),
    ):
        if b.get(anahtar) is not None:
            try:
                satirlar.append(f"{etiket} " + bicim.format(float(b[anahtar])))
            except (TypeError, ValueError):
                pass
    satirlar.append("→ yön değil, ARALIK")
    if koni["yuk_med"]:
        satirlar.append(
            f"12 bar medyan: +{koni['yuk_med'][-1]:.1f} / −{koni['asg_med'][-1]:.1f} ATR"
        )
    ax.text(
        0.012, 0.985, "\n".join(satirlar), transform=ax.transAxes, va="top", ha="left",
        fontsize=8.5, family="monospace", color="#333333",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.85, edgecolor="#cccccc"),
    )

    ax.set_title("Aralık konisi — ok yerine ölçüm", fontsize=11, color="#222222")
    ax.set_ylabel("fiyat")
    ax.grid(alpha=0.15)
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    cikti.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(cikti)
    plt.close(fig)
    return cikti


def _atr(frame: pd.DataFrame, periyot: int = 14) -> pd.Series:
    yuksek = frame["high"].astype(float)
    dusuk = frame["low"].astype(float)
    kapanis = frame["close"].astype(float)
    onceki = kapanis.shift(1)
    tr = pd.concat([yuksek - dusuk, (yuksek - onceki).abs(), (dusuk - onceki).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / periyot, adjust=False).mean()


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Aralık konisi grafik prototipi")
    p.add_argument("--sembol", required=True)
    p.add_argument("--tf", default="4h")
    p.add_argument("--bar", type=int, default=-120, help="tetik barı (negatif = sondan)")
    p.add_argument("--cikti", default="var/koni/ornek.png")
    p.add_argument("--temas", type=int, default=1)
    args = p.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import research.arsiv as arsiv

    frame = arsiv.tf_frame(args.sembol.upper(), args.tf, legacy_resample=False)
    indeks = args.bar if args.bar >= 0 else len(frame) + args.bar
    cikti = ciz(frame, indeks, Path(args.cikti), sembol=args.sembol.upper(), tf=args.tf, temas=args.temas)
    print(f"[png] {cikti}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
