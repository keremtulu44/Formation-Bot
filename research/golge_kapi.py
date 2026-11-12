"""T3 kapısı — önceden kayıtlı eşiklerin değerlendirilmesi (plan belgesi §4).

Eşikler **plan belgesinde sonuç okunmadan önce** yazıldı ve bu modülde koda
gömülüdür; sonuçlara göre değiştirilemez (anti-lookahead, kendi kararıma bile
güvenilmeksizin). Çıktı ``kapi_karari.json``: her eşik için (esik, değer,
geçti) + tek karar.

**Her durumda canlıya bağlantı yok.** GEÇTİ yalnız kanıt birikimi sayılır
(kırmızı çizgi 8); GEÇMEDİ gölge defterde kalır.

Kullanım:
    python research/golge_kapi.py                  # varsayılan ölçümden
    python research/golge_kapi.py --olcum YOL.json
Çıkış kodu: 0 = kapı geçti, 2 = geçmedi, 1 = hata.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

KOK = Path(__file__).resolve().parent.parent
VARSAYILAN_OLCUM = KOK / "docs/arastirma/sonuclar/golge_zincir/olcum_ozet.json"
VARSAYILAN_CIKTI = KOK / "docs/arastirma/sonuclar/golge_zincir/kapi_karari.json"

# --- önceden kayıtlı eşikler (plan belgesi §4; değişiklik = belge ihlali) ---
ESIKLER = (
    ("K1", "doğrulamada UYGUN plan n", ">=", 50, "K1_dogrulama_uygun_n"),
    ("K2", "UYGUN − kör koşullu hedef (puan)", ">=", 5.0, "K2_kor_farki_puan"),
    ("K3", "doğrulama beklentisi (maliyet 0)", ">", 0.0, "K3_dogrulama_beklenti"),
    ("K4", "G1 kapalıyken plan oranı (%)", "<=", 5.0, "K4_g1_kapali_plan_orani"),
    ("K5", "RET sonrası plan ihlali", "==", 0, "K5_ret_sonrasi_plan_ihlal"),
    ("K6a", "keşif beklentisi", ">", 0.0, "K6_kesif_beklenti"),
    ("K6b", "doğrulama beklentisi", ">", 0.0, "K6_dogrulama_beklenti"),
)


def kapi_degerlendir(kapi_girdisi: dict[str, Any]) -> dict[str, Any]:
    """Saf değerlendirme: girdi değişmezse karar değişmez."""
    satirlar = []
    hepsi_gecti = True
    for kod, aciklama, op, esik, anahtar in ESIKLER:
        deger = kapi_girdisi.get(anahtar)
        if deger is None:
            gecti = False
        elif op == ">=":
            gecti = float(deger) >= esik
        elif op == ">":
            gecti = float(deger) > esik
        elif op == "<=":
            gecti = float(deger) <= esik
        elif op == "==":
            gecti = float(deger) == esik
        else:  # noqa: LE001 — sabit sözlük
            raise ValueError(f"bilinmeyen operatör {op!r}")
        hepsi_gecti = hepsi_gecti and bool(gecti)
        satirlar.append({
            "kod": kod, "esik": f"{op} {esik}", "aciklama": aciklama,
            "deger": deger, "gecti": bool(gecti),
        })
    return {
        "karar": "GEÇTİ" if hepsi_gecti else "GEÇMEDİ",
        "gecen": sum(1 for s in satirlar if s["gecti"]),
        "toplam_esik": len(satirlar),
        "esikler": satirlar,
        "not": ("Kanıt birikimi; canlıya bağlantı yok (kırmızı çizgi 8). "
                "Eşikler koşumdan ÖNCE plan belgesinde sabitlendi."),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="T3 kapısı")
    p.add_argument("--olcum", default=str(VARSAYILAN_OLCUM))
    p.add_argument("--cikti", default=str(VARSAYILAN_CIKTI))
    args = p.parse_args(argv)

    yol = Path(args.olcum)
    if not yol.exists():
        print(f"ölçüm bulunamadı: {yol}", file=sys.stderr)
        return 1
    olcum = json.loads(yol.read_text(encoding="utf-8"))
    girdi = olcum.get("kapi_girdisi")
    if not isinstance(girdi, dict):
        print("ölçümde 'kapi_girdisi' yok", file=sys.stderr)
        return 1

    karar = kapi_degerlendir(girdi)
    karar["olcum_dosyasi"] = str(yol)
    # Determinizm/görünürlük: ölçümde varsa kapı kararına da taşınır
    # (rapor katmanı — kapı eşiklerine dokunmaz).
    for ek in ("pasaport", "ga95"):
        if ek in olcum:
            karar[ek] = olcum[ek]
    cikti = Path(args.cikti)
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_text(json.dumps(karar, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(json.dumps(karar, ensure_ascii=False, indent=2))
    return 0 if karar["karar"] == "GEÇTİ" else 2


if __name__ == "__main__":
    raise SystemExit(main())
