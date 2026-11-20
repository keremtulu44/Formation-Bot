"""TEK BAKIŞTA ALARM GRAFİĞİ — "ne oldu, sonra ne oldu, tipik olarak ne oluyor".

Amaç: kullanıcı tek resimde kendi yorumunu yapabilsin. Bu yüzden grafik
**iddia etmez**, üç şeyi üst üste koyar:

1. **Gerçek fiyat** ve alarmın çıktığı bar (dikey çizgi).
2. **Sonrasında gerçekten ne oldu** — alarm sonrası 12 ve 40 barın tepe/dip
   seviyeleri, ATR cinsinden yazılı.
3. **Tipik olarak ne oluyor** — aynı sembol/TF'de geçmiş 200 alarmın
   sonraki 12 barından çıkan koni (medyan yukarı/aşağı + %80 aralık).

Kullanıcı ikisini karşılaştırır: "bu sefer tipik mi oldu, değil mi". Grafik
karar vermez, **karşılaştırma** verir.

Kullanım::

    python -m research.grafik_alarm --sembol GARFA --tf 4h --bar 307 \\
        --cikti var/grafik/garfa_4h.png
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

def _t(v: float, ondalik: int = 2) -> str:
    """Türkçe ondalık: 17,29 (nokta değil virgül)."""
    try:
        return f"{float(v):,.{ondalik}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    except (TypeError, ValueError):
        return "—"


KONI_BAR = 12
BANT = 0.80


def _atr(frame: pd.DataFrame, periyot: int = 14) -> pd.Series:
    y = frame["high"].astype(float)
    d = frame["low"].astype(float)
    k = frame["close"].astype(float)
    onceki = k.shift(1)
    tr = pd.concat([y - d, (y - onceki).abs(), (d - onceki).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / periyot, adjust=False).mean()


def koni(frame: pd.DataFrame, tetik: int, pencere: int = 200) -> dict[str, list[float]]:
    """Geçmiş alarm SONRASI yollar — koni için."""
    atr = _atr(frame)
    y = frame["high"].astype(float).to_numpy()
    d = frame["low"].astype(float).to_numpy()
    k = frame["close"].astype(float).to_numpy()
    n = len(frame)
    ornekler = []
    for i in range(max(0, tetik - pencere), tetik):
        if i + KONI_BAR >= n:
            continue
        a = float(atr.iloc[i])
        if not math.isfinite(a) or a <= 0:
            continue
        ref = float(k[i])
        ornekler.append((
            [(float(y[i + j]) - ref) / a for j in range(1, KONI_BAR + 1)],
            [(ref - float(d[i + j])) / a for j in range(1, KONI_BAR + 1)],
        ))
    if not ornekler:
        return {}
    yuk = pd.DataFrame([o[0] for o in ornekler])
    asg = pd.DataFrame([o[1] for o in ornekler])
    q = 1 - (1 - BANT) / 2
    return {
        "yuk_med": yuk.median(axis=0).tolist(),
        "yuk_p80": yuk.quantile(q, axis=0).tolist(),
        "asg_med": asg.median(axis=0).tolist(),
        "asg_p80": asg.quantile(q, axis=0).tolist(),
        "n": len(ornekler),
    }


def ciz(
    frame: pd.DataFrame,
    tetik: int,
    cikti: Path,
    *,
    sembol: str = "",
    tf: str = "",
    etiket: str = "",
    yon: int = 0,
    geri: int = 45,
    ileri: int = 45,
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon

    n = len(frame)
    if not 0 <= tetik < n:
        raise SystemExit(f"bar aralık dışı: {tetik} (n={n})")

    atr_seri = _atr(frame)
    atr = float(atr_seri.iloc[tetik])
    ref = float(frame["close"].iloc[tetik])
    bas = max(0, tetik - geri)
    son = min(n, tetik + ileri + 1)
    parca = frame.iloc[bas:son]
    ofset = tetik - bas
    x = list(range(len(parca)))

    fig, ax = plt.subplots(figsize=(13, 7), dpi=115)

    # --- mumlar
    for i, (_, s) in enumerate(parca.iterrows()):
        renk = "#26a69a" if float(s["close"]) >= float(s["open"]) else "#ef5350"
        ax.plot([i, i], [float(s["low"]), float(s["high"])], color=renk, lw=0.9)
        ax.plot([i - 0.3, i + 0.3], [float(s["open"])] * 2, color=renk, lw=0.9)
        ax.plot([i - 0.3, i + 0.3], [float(s["close"])] * 2, color=renk, lw=0.9)

    # --- alarm çizgisi
    ax.axvline(ofset, color="#455a64", ls="--", lw=1.4, zorder=1)
    ax.text(ofset, -0.085, "ALARM →", transform=ax.get_xaxis_transform(),
            fontsize=10, color="#455a64", fontweight="bold", va="top", ha="right")

    # --- YÖN etiketi: alarm ne dedi? Bu olmadan grafik yanlış okunur.
    yon_metni = {1: "▲ YUKARI", -1: "▼ AŞAĞI", 0: "↕ YÖNSÜZ"}.get(int(yon or 0), "↕ YÖNSÜZ")
    yon_rengi = {1: "#2e7d32", -1: "#c62828", 0: "#616161"}.get(int(yon or 0), "#616161")
    ax.annotate(
        f"alarmın dediği yön: {yon_metni}",
        xy=(0.5, 1.0), xycoords=("axes fraction", "axes fraction"),
        xytext=(0, -26), textcoords="offset points",
        fontsize=11, fontweight="bold", color=yon_rengi, ha="center", va="top",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.9, edgecolor=yon_rengi),
        zorder=8,
    )

    # --- koni (tipik davranış)
    k = koni(frame, tetik)
    if k:
        xs = list(range(ofset + 1, ofset + 1 + len(k["yuk_med"])))
        ust = [ref + v * atr for v in k["yuk_p80"]]
        alt = [ref - v * atr for v in k["asg_p80"]]
        ax.add_patch(Polygon(
            list(zip(xs, ust)) + list(zip(reversed(xs), reversed(alt))),
            closed=True, facecolor="#5c6bc0", alpha=0.14, edgecolor="none",
            zorder=0, label=f"tipik %{int(BANT*100)} aralık (geçmiş {k['n']} alarm)",
        ))
        ax.plot(xs, [ref + v * atr for v in k["yuk_med"]], color="#3949ab", lw=1.7,
                zorder=2, label="tipik: yukarı uzanım (medyan)")
        ax.plot(xs, [ref - v * atr for v in k["asg_med"]], color="#8e24aa", lw=1.7,
                zorder=2, label="tipik: aşağı uzanım (medyan)")

    # --- GERÇEKLEŞEN: alarm sonrası 12 ve 40 bar tepesi/dibi
    gelecek = frame.iloc[tetik + 1:]
    etiketler: list[tuple[float, str, str]] = []   # (y, metin, renk)
    for ufuk, renk, et in ((12, "#2e7d32", "12 bar"), (40, "#ef6c00", "40 bar")):
        dilim = gelecek.iloc[:ufuk]
        if len(dilim) < ufuk:
            continue
        tepe = float(dilim["high"].max())
        dip = float(dilim["low"].min())
        ax.axhline(tepe, color=renk, lw=1.1, ls=":", alpha=0.8, zorder=1)
        ax.axhline(dip, color=renk, lw=1.1, ls=":", alpha=0.8, zorder=1)
        etiketler.append((tepe, f"{et} tepe  +{(tepe-ref)/atr:.1f} ATR", renk))
        etiketler.append((dip, f"{et} dip  −{(ref-dip)/atr:.1f} ATR", renk))

    # --- sol üst kutu: sade dille "ne oldu"
    satirlar = [f"{sembol} · {tf}", ""]
    if etiket:
        satirlar.append(f"alarm: {etiket}")
    satirlar += [
        "",
        f"alarm fiyatı  {_t(ref)}",
        f"ATR           {_t(atr)}  ({_t(atr/ref*100,1)}%)",
        "",
    ]
    dilim12 = gelecek.iloc[:12]
    if len(dilim12) == 12:
        t12 = (float(dilim12["high"].max()) - ref) / atr
        d12 = (ref - float(dilim12["low"].min())) / atr
        satirlar.append(f"sonraki 12 bar: +{_t(t12,1)} / −{_t(d12,1)} ATR")
        satirlar.append(f"toplam oynaklık  {_t(t12+d12,1)} ATR")
        if int(yon or 0) == 1:
            sonuc = "lehte" if t12 > d12 else "ALEYHTE"
            satirlar.append(f"alarm yönünde:    {sonuc}  (lehte {_t(t12,1)} / aleyhte {_t(d12,1)})")
        elif int(yon or 0) == -1:
            sonuc = "lehte" if d12 > t12 else "ALEYHTE"
            satirlar.append(f"alarm yönünde:    {sonuc}  (lehte {_t(d12,1)} / aleyhte {_t(t12,1)})")
    satirlar += ["", "bu çizgi yorum değil:", "gerçekleşen vs tipik"]
    ax.text(
        0.010, 0.985, "\n".join(satirlar), transform=ax.transAxes, va="top", ha="left",
        fontsize=9, family="monospace", color="#263238",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.92, edgecolor="#b0bec5"),
        zorder=5,
    )

    # Çizgi etiketleri: sağ kenarda, dikeyde çakışmayı önlemek için sırayla itilir.
    etiketler.sort(key=lambda t: t[0])
    son_y = None
    for y, metin, renk in etiketler:
        if son_y is not None and y - son_y < atr * 0.5:
            y = son_y + atr * 0.5
        son_y = y
        ax.text(0.995, y, metin, transform=ax.get_yaxis_transform(),
                fontsize=8.5, color=renk, ha="right", va="center", zorder=6,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.85,
                          edgecolor="none"))

    ax.set_title("Alarmdan sonra ne oldu — ve tipik olarak ne oluyor",
                 fontsize=12, color="#1c1c1c", pad=34)
    ax.set_ylabel("fiyat")
    ax.grid(alpha=0.12)
    ax.legend(loc="lower left", fontsize=8.5, framealpha=0.92)
    ax.set_xlim(-1, len(parca))
    fig.tight_layout()
    cikti.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(cikti)
    plt.close(fig)
    return cikti


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Tek bakışta alarm grafiği")
    p.add_argument("--sembol", required=True)
    p.add_argument("--tf", default="4h")
    p.add_argument("--bar", type=int, required=True, help="alarmın çıktığı bar indeksi")
    p.add_argument("--etiket", default="", help="alarm türü (ör. KIRILIM_TEYITLI)")
    p.add_argument("--yon", type=int, default=0, help="1 yukarı, -1 aşağı, 0 yönsüz")
    p.add_argument("--cikti", default="var/grafik/alarm.png")
    args = p.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import research.arsiv as arsiv

    frame = arsiv.tf_frame(args.sembol.upper(), args.tf, legacy_resample=False)
    yol = ciz(frame, args.bar, Path(args.cikti), sembol=args.sembol.upper(),
              tf=args.tf, etiket=args.etiket, yon=args.yon)
    print(f"[png] {yol}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
