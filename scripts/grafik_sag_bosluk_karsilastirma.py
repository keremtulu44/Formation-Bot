# -*- coding: utf-8 -*-
"""Sağ boşluk karşılaştırma sayfası: aynı kareyi birkaç oranla çizip tek PNG'de dizer.

2026-10-16 kullanıcı kararı: sağ boşluk eksen genişliğinin %10-20'si (varsayılan
%15) ve `GRAFIK_SAG_BOSLUK_ORANI` ile değiştirilebilir. Bu script kararı GÖZLE
doğrulamak için: her satır bir oran, her kolon bir kare (hisse:TF). Kareler
`grafik_uret.kare_uret` ile ÜRETİLİR — botun/`/grafik` komutunun çizdiği yolun
aynısı (uydurma kare yok, §0.12k).

Kullanım:
    python scripts/grafik_sag_bosluk_karsilastirma.py \\
        --kare GARAN:1h --kare AKBNK:4h --oranlar 0.10,0.15,0.20 \\
        --cikti /tmp/sag_bosluk.png --zone

Notlar:
    * Oran 0 → boşluk kapanır (eski görünüm) karşılaştırmaya "kapalı" satırı ekler.
    * `GRAFIK_SAG_BOSLUK_ORANI` açıkça verildiği için kırpma UYGULANMAZ; pencere
      yalnız otomatik kuralda geçerlidir (bkz. `grafik.sag_bosluk_mum`).
    * Geçici kareler `--gecici` dizinine yazılır (varsayılan: sistem geçici dizini).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

_BASLIK_YUKSEKLIGI = 34           # her satırın üstündeki oran şeridi (px)
_KENAR = 8


def _oran_etiketleri(oranlar: list[float]) -> list[tuple[str, str]]:
    """`(env değeri, satır başlığı)`. Gerçek mum sayısı stdout'a yazılır (kareye göre değişir)."""
    import grafik

    alt = float(grafik.SABITLER["sag_bosluk_orani_min"])
    ust = float(grafik.SABITLER["sag_bosluk_orani_maks"])
    satirlar: list[tuple[str, str]] = []
    for oran in oranlar:
        ham = f"{oran:g}" if oran > 0 else "0"
        if oran <= 0:
            satirlar.append((ham, "sağ boşluk KAPALI (eski görünüm)"))
            continue
        pencere = alt <= oran <= ust
        satirlar.append((ham, f"sağ boşluk %{oran * 100:.0f} · eksen genişliğinin"
                              + ("" if pencere else "  (kabul penceresi dışı)")))
    return satirlar


def main(argv: list[str] | None = None) -> int:
    ay = argparse.ArgumentParser(description="Sağ boşluk oranı karşılaştırma sayfası.")
    ay.add_argument("--kare", action="append", required=True, metavar="HISSE:TF",
                    help="karşılaştırılacak kare (tekrarlanabilir), örn. GARAN:1h")
    ay.add_argument("--oranlar", default="0.10,0.15,0.20",
                    help="eksen yüzdesi listesi (0 = kapalı), virgülle")
    ay.add_argument("--cikti", default="/tmp/sag_bosluk_karsilastirma.png")
    ay.add_argument("--gecici", default=None, help="ara karelerin dizini")
    ay.add_argument("--zone", action="store_true", help="domain motorlarını çalıştır")
    ay.add_argument("--veri-dizin", dest="veri_dizin", default=None)
    ay.add_argument("--olcek", type=float, default=0.62, help="sayfa küçültme oranı")
    sec = ay.parse_args(argv)

    from PIL import Image, ImageDraw, ImageFont
    from matplotlib import font_manager

    import grafik_uret

    oranlar: list[float] = []
    for parca in str(sec.oranlar).split(","):
        parca = parca.strip()
        if parca:
            oranlar.append(max(0.0, min(0.8, float(parca))))
    if not oranlar:
        print("oran yok", file=sys.stderr)
        return 2

    kareler: list[tuple[str, str]] = []
    for ham in sec.kare:
        hisse, _, tf = str(ham).partition(":")
        kareler.append((hisse.strip().upper(), (tf or "4h").strip()))
    gecici = Path(sec.gecici) if sec.gecici else Path(tempfile.gettempdir()) / "sag_bosluk"
    gecici.mkdir(parents=True, exist_ok=True)

    eski = os.environ.get("GRAFIK_SAG_BOSLUK_ORANI")
    satirlar: list[tuple[str, list[str]]] = []
    try:
        for oran in oranlar:
            os.environ["GRAFIK_SAG_BOSLUK_ORANI"] = f"{oran:g}"
            yollar: list[str] = []
            for hisse, tf in kareler:
                yol = str(gecici / f"{hisse}_{tf}_{oran:g}.png")
                sonuc = grafik_uret.kare_uret(hisse, tf, veri_dizin=sec.veri_dizin,
                                              zone=sec.zone, cikti=yol)
                if not sonuc.get("yol"):
                    print(f"HATA {hisse} {tf} @%{oran * 100:.0f}: {sonuc.get('hata')}",
                          file=sys.stderr)
                    return 1
                k = sonuc["meta"]["kare"]
                print(f"{hisse} {tf} @%{oran * 100:>4.0f}: {k['sag_bosluk']} mum boşluk "
                      f"(eksenin %{k['sag_bosluk_yuzde']:.1f}'i)")
                yollar.append(yol)
            satirlar.append((f"{oran:g}", yollar))
    finally:
        if eski is None:
            os.environ.pop("GRAFIK_SAG_BOSLUK_ORANI", None)
        else:
            os.environ["GRAFIK_SAG_BOSLUK_ORANI"] = eski

    # Sayfa: satır = oran, kolon = kare; her satırın üstünde başlık şeridi.
    kare_x, kare_y = Image.open(satirlar[0][1][0]).size
    adet = len(kareler)
    olcek = max(0.2, min(1.0, float(sec.olcek)))
    kw, kh = int(kare_x * olcek), int(kare_y * olcek)
    gen = _KENAR + adet * (kw + _KENAR)
    yuk = _KENAR + len(satirlar) * (kh + _BASLIK_YUKSEKLIGI + _KENAR)
    sayfa = Image.new("RGB", (gen, yuk), (9, 12, 17))
    ciz = ImageDraw.Draw(sayfa)
    try:
        yol_yazi = font_manager.findfont("DejaVu Sans", fallback_to_default=True)
        yazi = ImageFont.truetype(yol_yazi, 17)
    except Exception:                                   # yazı tipi yoksa çizim sürer
        yazi = ImageFont.load_default()

    for satir, (oran_ham, yollar) in enumerate(satirlar):
        y = _KENAR + satir * (kh + _BASLIK_YUKSEKLIGI + _KENAR) + _BASLIK_YUKSEKLIGI
        etiket = _oran_etiketleri([float(oran_ham)])[0][1]
        ciz.text((_KENAR + 4, y - _BASLIK_YUKSEKLIGI + 8), etiket,
                 fill=(233, 238, 245), font=yazi)
        for kolon, yol in enumerate(yollar):
            gorsel = Image.open(yol).convert("RGB").resize((kw, kh), Image.LANCZOS)
            x = _KENAR + kolon * (kw + _KENAR)
            sayfa.paste(gorsel, (x, y))
            ciz.rectangle([x - 1, y - 1, x + kw, y + kh], outline=(36, 48, 64))
        hisseler = " · ".join(f"{h} {tf}" for h, tf in kareler)
        gen_baslik = ciz.textlength(hisseler, font=yazi)
        ciz.text((gen - _KENAR - gen_baslik, y - _BASLIK_YUKSEKLIGI + 8), hisseler,
                 fill=(147, 161, 177), font=yazi)

    sayfa.save(sec.cikti)
    print("sayfa:", sec.cikti, sayfa.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
