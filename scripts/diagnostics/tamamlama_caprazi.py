"""Tamamlanma çaprazı — "sınıra yaklaşırsa tamamlanır mı?" sorusunun ölçümü.

## Neden var

Kart 2026-10-22'ye kadar yalnız "tuttu %76" gibi **koşulsuz** bir oran basıyordu.
Kullanıcı koşullu cümle istedi: *"formasyonun tamamlanması % şu kadar düşerse
tamamlanır şeklinde ekleyelim"* — yani **fiyat sınıra yaklaştığında** sonucun ne
olduğu. Bu cümle ölçülmeden karta yazılmaz (kullanıcı kararı: "onaysız
yazılmaz"); bu betik ölçümü üretir.

## Ölçüm

Girdi: `scripts/backfill/arastirma_kosu.py` çıktısındaki `frm.jsonl`
(formasyon başına bir satır). Kullanılan kolonlar:

* `frm_yakinlik_ust_fitil_atr` / `frm_yakinlik_alt_fitil_atr` — doğumdan
  kırılıma kadar sınıra **en çok** yaklaşma (ATR). 0 = fitil çizgiye değdi.
  Bkz. `docs/arastirma/KOLON_SOZLUGU.md` §13.5 (anti-dairesellik: ölçüm
  çapaya kadar, sonuç çapadan sonra).
* `terminal_state` — `FORMASYON_TAMAMLANDI` = "kırılım teyit aldı ve bandın
  içine dönmedi" (**"hedefe ulaştı" DEĞİL**, `patterns/lifecycle.py`).
* `bitis_sebebi` — `TERMINAL` ya da `VERI_SONU`. **Açık (VERI_SONU) satırlar
  dışlanır**: henüz bitmemiş bir formasyonu "tamamlanmadı" saymak oranı
  olduğundan düşük gösterir (sağdan sansür). Dışlanan sayı raporlanır.

Çıktı: her eşik için "en az bir kez sınıra ≤ E ATR yaklaşan" formasyonların
tamamlanma payı, karşılaştırma grubu (hiç yaklaşmayan) ve Wilson %95 aralığı.

## Kullanım

    .venv/bin/python scripts/diagnostics/tamamlama_caprazi.py \
        --dizin /tmp/arastirma_tam/4h --dizin /tmp/arastirma_tam/1d

    # JSON çıktı (karta gömülecek sayıyı seçmek için)
    .venv/bin/python scripts/diagnostics/tamamlama_caprazi.py --dizin ... --json
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable

TAMAM = "FORMASYON_TAMAMLANDI"

#: Yakınlık eşikleri (ATR). `YAKINLIK_IZGARA` ile aynı: 0,50 · 1,00 · 1,50 · 2,00.
ESIKLER = (0.5, 1.0, 1.5, 2.0)


def wilson(basari: int, n: int) -> tuple[float, float]:
    """Wilson %95 güven aralığı — küçük n'lerde normal yaklaşımdan dürüst."""
    if n <= 0:
        return (float("nan"), float("nan"))
    z = 1.959963984540054
    p = basari / n
    payda = 1 + z * z / n
    merkez = (p + z * z / (2 * n)) / payda
    yari = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / payda
    return (max(0.0, merkez - yari) * 100.0, min(1.0, merkez + yari) * 100.0)


def satirlari_oku(dizinler: Iterable[str | Path]) -> tuple[list[dict], dict[str, int]]:
    """`frm.jsonl` satırlarını okur; sayaç açık/boş/bozuk satırları raporlar."""
    sayac = {"satir": 0, "acik_veri_sonu": 0, "bozuk": 0}
    satirlar: list[dict] = []
    for dizin in dizinler:
        yol = Path(dizin) / "frm.jsonl"
        if not yol.exists():
            continue
        with yol.open(encoding="utf-8") as akis:
            for ham in akis:
                ham = ham.strip()
                if not ham:
                    continue
                sayac["satir"] += 1
                try:
                    kayit = json.loads(ham)
                except json.JSONDecodeError:
                    sayac["bozuk"] += 1
                    continue
                if kayit.get("bitis_sebebi") != "TERMINAL":
                    sayac["acik_veri_sonu"] += 1
                    continue
                satirlar.append(kayit)
    return satirlar, sayac


def _sayi(deger: Any) -> float | None:
    if deger is None:
        return None
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return None
    return sayi if math.isfinite(sayi) else None


def yaklasma(kayit: dict) -> tuple[float | None, float | None]:
    """(üst sınıra en çok yaklaşma, alt sınıra en çok yaklaşma) — ATR."""
    return (_sayi(kayit.get("frm_yakinlik_ust_fitil_atr")),
            _sayi(kayit.get("frm_yakinlik_alt_fitil_atr")))


def capraz(satirlar: list[dict], esik: float) -> dict[str, Any]:
    """Tek eşik için 2×2 çapraz: yaklaştı mı × tamamlandı mı."""
    yakin_tamam = yakin_toplam = 0
    uzak_tamam = uzak_toplam = 0
    yakin_omur: list[int] = []
    for kayit in satirlar:
        ust, alt = yaklasma(kayit)
        en_yakin = min([x for x in (ust, alt) if x is not None], default=None)
        if en_yakin is None:
            continue                      # mesafe ölçülmemiş: ne lehte ne aleyhte
        tamam = kayit.get("terminal_state") == TAMAM
        if en_yakin <= esik:
            yakin_toplam += 1
            yakin_tamam += int(tamam)
            if tamam:
                try:
                    yakin_omur.append(int(kayit.get("omur_bar")))
                except (TypeError, ValueError):
                    pass
        else:
            uzak_toplam += 1
            uzak_tamam += int(tamam)

    def _ozet(basari: int, n: int) -> dict[str, Any]:
        alt_ci, ust_ci = wilson(basari, n)
        return {"n": n, "tamam": basari,
                "oran_pct": round(basari / n * 100.0, 1) if n else None,
                "ga95": [round(alt_ci, 1), round(ust_ci, 1)] if n else None}

    yakin_omur.sort()
    medyan_omur = (yakin_omur[len(yakin_omur) // 2] if yakin_omur else None)
    return {
        "esik_atr": esik,
        "yaklasan": _ozet(yakin_tamam, yakin_toplam),
        "yaklasmayan": _ozet(uzak_tamam, uzak_toplam),
        "medyan_omur_mum": medyan_omur,
    }


#: Aşım kovaları (ATR): sınırın ne kadar ötesine gitti. Yakınlıktan farkı:
#: "yaklaştı mı" sorusunun cevabı neredeyse her formasyonda EVET (%93), bu
#: yüzden ayrıştırıcı değil; "ne kadar aştı" ise değişiyor.
ASIM_KOVALARI = ((0.01, 0.25), (0.25, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, float("inf")))


def asim_caprazi(satirlar: list[dict]) -> list[dict[str, Any]]:
    """Aşım kovası × tamamlanma: "sınırı şu kadar aşarsa sonuç ne olur".

    Aşım (`frm_asim_*_fitil_atr`) formasyonun ömrü boyunca sınırı **en fazla**
    ne kadar aştığıdır. Kova, formasyonun kendi ölçüsüdür; sonuç
    (`terminal_state`) ondan bağımsız okunur.
    """
    sonuc: list[dict[str, Any]] = []
    for alt, ust in ASIM_KOVALARI:
        grup = []
        for kayit in satirlar:
            degerler = [_sayi(kayit.get("frm_asim_ust_fitil_atr")),
                        _sayi(kayit.get("frm_asim_alt_fitil_atr"))]
            asim = max([x for x in degerler if x is not None], default=None)
            if asim is None or not (alt <= asim < ust):
                continue
            grup.append(kayit)
        tamam = sum(1 for k in grup if k.get("terminal_state") == TAMAM)
        alt_ci, ust_ci = wilson(tamam, len(grup))
        sonuc.append({
            "asim_atr": [alt, (ust if ust != float("inf") else None)],
            "n": len(grup), "tamam": tamam,
            "oran_pct": round(tamam / len(grup) * 100.0, 1) if grup else None,
            "ga95": [round(alt_ci, 1), round(ust_ci, 1)] if grup else None,
        })
    return sonuc


def main(argv: list[str] | None = None) -> int:
    ayar = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayar.add_argument("--dizin", action="append", default=[],
                      help="arastirma çıktı dizini (birden çok verilebilir)")
    ayar.add_argument("--esik", type=str, default="",
                      help="virgülle ATR eşikleri (varsayılan 0.5,1.0,1.5,2.0)")
    ayar.add_argument("--asim", action="store_true",
                      help="yakınlık yerine aşım kovalarını ölç "
                           "(sınırın ne kadar ötesine gitti)")
    ayar.add_argument("--json", action="store_true", help="JSON çıktı")
    secim = ayar.parse_args(argv)

    esikler = ([float(x) for x in secim.esik.split(",") if x.strip()]
               if secim.esik else list(ESIKLER))
    dizinler = secim.dizin or ["arastirma_cikti"]
    satirlar, sayac = satirlari_oku(dizinler)
    sonuc = {
        "dizinler": [str(d) for d in dizinler],
        "kayit": sayac,
        "kapanmis_formasyon": len(satirlar),
        "caprazlar": [capraz(satirlar, e) for e in esikler],
        "asim_kovalari": asim_caprazi(satirlar),
    }
    if secim.json:
        print(json.dumps(sonuc, ensure_ascii=False, indent=2))
        return 0

    print(f"dizin: {', '.join(sonuc['dizinler'])}")
    print(f"okunan satır {sayac['satir']} · açık (VERI_SONU, dışlandı) "
          f"{sayac['acik_veri_sonu']} · bozuk {sayac['bozuk']}")
    print(f"kapanmış formasyon: {len(satirlar)}\n")
    print(f"{'eşik':>6} | {'yaklaşan n':>10} {'tamam %':>8} {'GA95':>16} "
          f"| {'yaklaşmayan n':>13} {'tamam %':>8} | medyan ömür")
    for c in sonuc["caprazlar"]:
        y, u = c["yaklasan"], c["yaklasmayan"]
        ga = f"[{y['ga95'][0]:.1f}; {y['ga95'][1]:.1f}]" if y["ga95"] else "-"
        print(f"{c['esik_atr']:>6.2f} | {y['n']:>10} "
              f"{(y['oran_pct'] if y['oran_pct'] is not None else float('nan')):>8.1f} "
              f"{ga:>16} | {u['n']:>13} "
              f"{(u['oran_pct'] if u['oran_pct'] is not None else float('nan')):>8.1f} "
              f"| {c['medyan_omur_mum']}")
    if secim.asim:
        print(f"\n{'aşım ATR':>14} | {'n':>6} {'tamam':>6} {'%':>6} {'GA95':>16}")
        for k in sonuc["asim_kovalari"]:
            aralik = (f"{k['asim_atr'][0]:.2f}–{k['asim_atr'][1]:.2f}"
                      if k["asim_atr"][1] is not None
                      else f"≥{k['asim_atr'][0]:.2f}")
            ga = f"[{k['ga95'][0]:.1f}; {k['ga95'][1]:.1f}]" if k["ga95"] else "-"
            oran = f"{k['oran_pct']:.1f}" if k["oran_pct"] is not None else "-"
            print(f"{aralik:>14} | {k['n']:>6} {k['tamam']:>6} {oran:>6} {ga:>16}")
    print("\nNot: `tamamlandı` = kırılım teyit aldı ve banda dönmedi "
          "(hedefe ulaştı demek değil). Açık satırlar dışlandı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
