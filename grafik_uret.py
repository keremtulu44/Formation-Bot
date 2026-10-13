# -*- coding: utf-8 -*-
"""Grafik CLI'ı — gerçek önbellekten tek kare üretir (G1 doğrulama aracı).

Neden ayrı betik: bot'un çizim yolu motoru YENİDEN ÇALIŞTIRMAZ (§14.2) ve kareyi
kaynağında denetlemek gerekir. Bu araç aynı zinciri kurar: önbellek →
`data.resample_ohlcv` → `grafik.anlik_goruntu` → `grafik.ciz`. Formasyon
kaydı `--formasyon` ile verilmezse kare mumlarla çizilir ve `uyarilar` bunu yazar
(uydurma formasyon çizilmez).

Örnekler:
    python grafik_uret.py --hisse AKBNK --tf 1h --mum 180 --cikti /tmp/a.png
    python grafik_uret.py --hisse THYAO --tum-tf --json
    python grafik_uret.py --hisse AKBNK --tf 1d --demo --mum 180

`--demo`: önbellekte derin günlük veri yokken (bu depo `bot_data/*_gunluk.json`
içermez) 500 barlık GüNLÜK çerçeveyi sentetik üretir. Neden `bot_data/` içine
dosya yazmıyoruz: o dizin canlı botun okuduğu önbellektir, sentetik veri oraya
karışırsa gerçek taramayı zehirler (§22'de kayıtlı sapma).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ISTANBUL_TZ = timezone(timedelta(hours=3))
TF_LISTESI = ("1h", "2h", "4h", "1d")


def _veri_dizini(secenek: str | None) -> str:
    if secenek:
        return str(Path(sekenek).expanduser())
    return os.environ.get("DATA_DIR") or str(Path(__file__).resolve().parent / "bot_data")


def _cerceve_yukle(hisse: str, tf: str, veri_dizin: str, demo: bool):
    """Önbellekten (veya --demo) çizim çerçevesini getirir.

    `1d` için `to_gunluk_dataframe` (derin, ~500 bar) denenir; yoksa 1s
    önbelleğinden `resample_ohlcv` ile üretilir — ölçüm: 360 × 1s → ~44 bar,
    yani bu depo için günlük kadraj YÜZEYSEL kalır (§18.6).
    """
    from data import StockDequeManager, resample_ohlcv

    yonetici = StockDequeManager(data_dir=veri_dizin)
    anahtar = hisse.upper().replace(".IS", "")   # önbellek adı: AKBNK.json
    df_1s = yonetici.to_dataframe(anahtar)
    if tf == "1d":
        df_1g = yonetici.to_gunluk_dataframe(anahtar)
        if df_1g is not None and len(df_1g) > 1:
            return df_1g, "bot_data/günlük"
    if df_1s is None or len(df_1s) < 5:
        if not demo:
            raise SystemExit(f"veri yok: {veri_dizin}/{anahtar}.json okunamadı "
                             f"(--demo ile sentetik çerçeve çizilir)")
        return _demo_cerceve(500 if tf == "1d" else 360), "demo"
    if tf == "1h":
        return df_1s, "bot_data/1s"
    return resample_ohlcv(df_1s, tf), f"resample({tf})"


def _demo_cerceve(bar_sayisi: int):
    """Deterministik sentetik günlük çerçeve (yalnız CLI/sim; önbelleğe yazılmaz)."""
    import pandas as pd
    import random

    rastgele = random.Random(7)
    kapanislar: list[float] = []
    fiyat = 60.0
    gun = datetime(2025, 1, 2, 9, 30, tzinfo=ISTANBUL_TZ)
    zamanlar, satirlar = [], []
    acilis = fiyat
    for _ in range(bar_sayisi):
        while gun.weekday() > 4:
            gun += timedelta(days=1)
        dalga = 0.004 * (1 if (len(kapanislar) // 40) % 2 == 0 else -1)
        fiyat = max(1.0, fiyat * (1 + rastgele.gauss(dalga, 0.014)))
        yuksek = max(acilis, fiyat) * 1.007
        dusuk = min(acilis, fiyat) * 0.993
        satirlar.append({"open": round(acilis, 2), "high": round(yuksek, 2),
                         "low": round(dusuk, 2), "close": round(fiyat, 2),
                         "volume": float(1_000_000 + rastgele.randint(0, 4_000_000))})
        kapanislar.append(fiyat)
        zamanlar.append(gun)
        acilis = fiyat
        gun = gun + timedelta(days=1)
    df = pd.DataFrame(satirlar, index=pd.DatetimeIndex(zamanlar, name="timestamp"))
    return df


def _formasyon_yukle(yol: str | None, cerceve) -> tuple[dict | None, list[str]]:
    """`--formasyon` JSON'unu okur; yoksa None + uyarı (sessiz kabahat yok)."""
    if not yol:
        return None, ["formasyon verisi verilmedi: bant/işaret çizilmedi"]
    dosya = Path(yol).expanduser()
    if not dosya.exists():
        return None, [f"formasyon dosyası yok: {dosya}"]
    try:
        kayit = json.loads(dosya.read_text(encoding="utf-8"))
    except (OSError, ValueError) as hata:
        return None, [f"formasyon dosyası okunamadı: {type(hata).__name__}"]
    n = len(cerceve)
    # JSON'da bar indeksi yoksa son kapanan muma sabitlenir: kart da alarm
    # bilgisini kapanan bardan okuyor, CLI'da uydurma indeks üretilmez.
    kayit.setdefault("end_bar", n - 1)
    return kayit, []


def main(giris: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(
        description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ayristirici.add_argument("--hisse", required=True, help="Kod, örn. AKBNK (`.IS` eklenmez)")
    ayristirici.add_argument("--tf", default="1h", choices=TF_LISTESI, help="zaman dilimi")
    ayristirici.add_argument("--mum", type=int, default=None,
                             help=f"kadraj tavanı (varsayılan grafik.SABİTLER['kare_mum'])")
    ayristirici.add_argument("--cikti", default=None, help="PNG yolu (vars: /tmp/...)")
    ayristirici.add_argument("--veri-dizin", default=None, help="önbellek dizini (DATA_DIR)")
    ayristirici.add_argument("--formasyon", default=None,
                             help="kart payload'ı biçiminde JSON: bant/işaret/alarm verisi")
    ayristirici.add_argument("--alarm-turu", default=None,
                             choices=["aday", "kritik", "teyit", "retest", "gecersiz", "ihlal"])
    ayristirici.add_argument("--serit-yok", action="store_true", help="katılım kulvarını kapat")
    ayristirici.add_argument("--etiket-detay", action="store_true",
                             help="motorun `evidence_text` satırını da yaz (§2.6)")
    ayristirici.add_argument("--tum-tf", action="store_true",
                             help="1s/2s/4s/1g için ayrı ayrı kare üret (/grafik provası)")
    ayristirici.add_argument("--demo", action="store_true",
                             help="önbellek yoksa deterministik sentetik çerçeve kullan")
    ayristirici.add_argument("--json", action="store_true", help="meta çıktısını yazdır")
    secenek = ayristirici.parse_args(giris)

    import grafik

    veri_dizin = _veri_dizini(secenek.veri_dizin)
    tfler = TF_LISTESI if secenek.tum_tf else (secenek.tf,)
    durum = 0
    for tf in tfler:
        cerceve, kaynak = _cerceve_yukle(secenek.hisse, tf, veri_dizin, secenek.demo)
        formasyon, uyarilar = _formasyon_yukle(secenek.formasyon, cerceve)
        goruntu = grafik.anlik_goruntu(formasyon, tf, cerceve, sembol=secenek.hisse,
                                       alarm_turu=secenek.alarm_turu,
                                       kare_mum=secenek.mum)
        for u in uyarilar:
            goruntu["uyarilar"].append(u)
        cikti = secenek.cikti or f"/tmp/grafik_{secenek.hisse.upper()}_{tf}.png"
        if secenek.tum_tf or len(tfler) > 1:
            cikti = str(Path(cikti).with_name(f"{Path(cikti).stem}_{tf}.png"))
        yol, meta = grafik.ciz(goruntu, tf, secenekler={
            "cikti": cikti,
            "serit": not secenek.serit_yok,
            "etiket_detay": secenek.etiket_detay,
        })
        meta["kaynak"] = kaynak
        if secenek.json:
            print(json.dumps(meta, ensure_ascii=False, indent=2, default=str))
        if yol:
            print(f"{yol}  ·  {meta['mum_sayisi']} mum  ·  {meta['png_kb']} KB  ·  "
                  f"{meta['sure_ms']} ms  ·  kaynak: {kaynak}")
        else:
            durum = 2
            print(f"çizilmedi ({tf}): " + " · ".join(meta["uyarilar"]), file=sys.stderr)
    return durum


if __name__ == "__main__":
    raise SystemExit(main())
