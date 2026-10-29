# -*- coding: utf-8 -*-
"""Yayın/ölçüm kapısı — golden toplamlar + tutarlılık + §6 kova bazeline.

Üç kapı (2026-10-29 kararı):

1. **Altın toplamlar (reconciliation)**: her kategori tablosunun satır sayısı
   sabittir (708-seri koşusu; BRENT'li ve BRENT'siz). Sayı değiştiyse koşu
   kırılmıştır → yayın durur.
2. **Tutarlılık (invariant)**: `Σ meta.formasyon_sayisi == frm satır sayısı`,
   seri kümesi birebir, `FORMASYON_TAMAMLANDI ⇒ frm_faz_gecis_sayisi ≥ 3` (S27).
3. **Kova-baseline**: `soru_seti_sonuclari.json` içindeki her kararın §6 kovası
   (`karar_kovasi`) bazeline (SORU_KOVA_BASELINE_*.json) göre değişti mi —
   değiştiyse yayın DURAR (kanun kırılmıştır; KOLON_SOZLUGU §18 ile birlikte
   okunur).

Kullanım:

    .venv/bin/python -m research.soru_kapisi \\
        --cikti arastirma_cikti_p1 arastirma_cikti_p2 \\
        --sonuc arastirma_cikti/soru_seti_sonuclari.json \\
        --kova docs/arastirma/SORU_KOVA_BASELINE_2026-10-29.json

İlk üretim (baseline yazmak): `--kova-yaz`. Çıkış kodu 0 = kapı açık.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

# 708-seri koşusunun altın toplamları (2026-10-29, p1+p2, h12 dâhil).
GOLDEN_TOPLAM: Dict[str, int] = {
    "zone": 189_171,
    "dokunus": 243_256,
    "swing": 416_685,
    "event": 202_938,
    "frm": 34_455,
    "frm_olay": 232_792,
    "meta": 708,
}
GOLDEN_BRENTSIZ: Dict[str, int] = {
    "zone": 187_046,
    "dokunus": 240_484,
    "swing": 412_045,
    "event": 200_028,
    "frm": 33_964,
    "frm_olay": 229_785,
    "meta": 704,
}
_BRENT = "BRENT"
_KATEGORILER = tuple(GOLDEN_TOPLAM)

# §6 kova başlığı → kısa ad (baseline JSON bu kısa adları kullanır).
KOVA_KISA = {
    "CANLIYA YAZILIR (kart/rozet/kuyruk/filtre)": "canli",
    "YALNIZ KART METNİ (5–12 pp / dipnot)": "kart",
    "RED / hipotez çöktü (yeni kural açılmaz)": "red",
    "KARAR YOK / HATA (n<30, sansür>20%, o hücrede karar yok)": "yok",
    "Gözlem / yapısal bulgu (kurala dönüşmez)": "gozlem",
}


def _satirlar(dizinler: Sequence[str], kategori: str) -> List[str]:
    """Kategori jsonl dosyalarının satırları (p1+p2, BRENT filtresi yok)."""
    satirlar: List[str] = []
    for dizin in dizinler:
        for yol in sorted(glob.glob(str(Path(dizin) / f"{kategori}.jsonl"))):
            with open(yol, encoding="utf-8") as f:
                satirlar.extend(f.read().splitlines())
    return [s for s in satirlar if s.strip()]


def _sayaclar(dizinler: Sequence[str], brent_siz: bool) -> Dict[str, int]:
    sayac: Dict[str, int] = {}
    for kategori in _KATEGORILER:
        satirlar = _satirlar(dizinler, kategori)
        if brent_siz:
            satirlar = [s for s in satirlar if _BRENT not in s]
        sayac[kategori] = len(satirlar)
    return sayac


def altin_toplam_kontrol(dizinler: Sequence[str],
                         golden: Mapping[str, int] | None = None,
                         golden_brentsiz: Mapping[str, int] | None = None
                         ) -> List[str]:
    """Tablo satır sayıları altın değerlerle birebir mı? → hata listesi."""
    hatalar: List[str] = []
    g = dict(golden if golden is not None else GOLDEN_TOPLAM)
    gb = dict(golden_brentsiz if golden_brentsiz is not None else GOLDEN_BRENTSIZ)
    for brent_siz, beklenen in ((False, g), (True, gb)):
        ad = "BRENT'siz" if brent_siz else "BRENT dâhil"
        gercek = _sayaclar(dizinler, brent_siz)
        for kategori, beklenen_sayi in beklenen.items():
            if gercek.get(kategori) != beklenen_sayi:
                hatalar.append(
                    f"{ad} {kategori}: {gercek.get(kategori)} != altın {beklenen_sayi}")
    return hatalar


def tutarlilik_kontrol(dizinler: Sequence[str],
                       beklenen_seri: int | None = None) -> List[str]:
    """Mantar içi tutarlılıklar (S27 dâhil) → hata listesi."""
    import json as _json

    hatalar: List[str] = []
    frm_sayi = 0
    formasyon_toplam = 0
    meta_sayi = 0
    seri_kume: set = set()
    tamamlanmis_eksik_gecis = 0
    for dizin in dizinler:
        # meta: formasyon_sayisi toplamı + seri kümesi
        for satir in _satirlar([dizin], "meta"):
            try:
                r = _json.loads(satir)
            except ValueError:
                hatalar.append(f"meta JSON bozuk: {satir[:80]}")
                continue
            meta_sayi += 1
            formasyon_toplam += int(r.get("formasyon_sayisi") or 0)
            seri_kume.add((r.get("symbol"), r.get("timeframe")))
        # frm: satır sayısı + S27 (TAMAMLANDI ⇒ faz geçişi ≥ 3)
        for satir in _satirlar([dizin], "frm"):
            try:
                r = _json.loads(satir)
            except ValueError:
                hatalar.append(f"frm JSON bozuk: {satir[:80]}")
                continue
            frm_sayi += 1
            if str(r.get("terminal_state")) == "FORMASYON_TAMAMLANDI":
                if int(r.get("frm_faz_gecis_sayisi") or 0) < 3:
                    tamamlanmis_eksik_gecis += 1
    if frm_sayi != formasyon_toplam:
        hatalar.append(
            f"Σ meta.formasyon_sayisi ({formasyon_toplam}) != frm satır ({frm_sayi})")
    if meta_sayi != len(seri_kume):
        hatalar.append(
            f"meta satır ({meta_sayi}) != tekil seri ({len(seri_kume)})")
    if beklenen_seri is not None and meta_sayi != beklenen_seri:
        hatalar.append(f"meta satır ({meta_sayi}) != beklenen seri ({beklenen_seri})")
    if tamamlanmis_eksik_gecis:
        hatalar.append(
            f"S27: FORMASYON_TAMAMLANDI ama faz geçişi <3 olan {tamamlanmis_eksik_gecis} satır")
    return hatalar


def kova_dagilimi(sonuc_json: Path) -> Dict[str, str]:
    """soru_seti_sonuclari.json → {S-id: kısa kova adı}."""
    from research.soru_cevaplama import karar_kovasi

    veri = json.loads(Path(sonuc_json).read_text(encoding="utf-8"))
    dagilim: Dict[str, str] = {}
    for sid, kayit in sorted(veri.items()):
        baslik = KOVA_KISA.get(karar_kovasi(str(kayit.get("karar", ""))))
        if baslik is None:
            raise ValueError(f"Bilinmeyen kova başlığı: {sid}")
        dagilim[sid] = baslik
    return dagilim


def kova_karsilastir(sonuc_json: Path, baseline_json: Path) -> List[str]:
    """§6 kovaları baseline ile birebir mı? → fark listesi."""
    gercek = kova_dagilimi(sonuc_json)
    beklenen = json.loads(Path(baseline_json).read_text(encoding="utf-8"))["kovalar"]
    hatalar: List[str] = []
    for sid in sorted(set(gercek) | set(beklenen)):
        a, b = gercek.get(sid), beklenen.get(sid)
        if a != b:
            hatalar.append(f"kova değişti {sid}: {b} → {a}")
    return hatalar


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Yayın kapısı: altın toplam + tutarlılık + kova")
    p.add_argument("--cikti", nargs="+",
                   default=["arastirma_cikti_p1", "arastirma_cikti_p2"],
                   help="replay çıktı dizinleri")
    p.add_argument("--sonuc", default="arastirma_cikti/soru_seti_sonuclari.json")
    p.add_argument("--kova", default="docs/arastirma/SORU_KOVA_BASELINE_2026-10-29.json")
    p.add_argument("--kova-yaz", action="store_true",
                   help="mevcut sonucu baseline olarak yaz (ilk üretim)")
    p.add_argument("--seri", type=int, default=708,
                   help="beklenen seri sayısı (0 = kontrol yok)")
    args = p.parse_args(argv)

    sonuc_yol = Path(args.sonuc)
    if args.kova_yaz:
        if not sonuc_yol.exists():
            print(f"[kapı] sonuç yok: {sonuc_yol}", file=sys.stderr)
            return 2
        dagilim = kova_dagilimi(sonuc_yol)
        hedef = Path(args.kova)
        hedef.parent.mkdir(parents=True, exist_ok=True)
        hedef.write_text(
            json.dumps({"kaynak": str(sonuc_yol), "tarih": "2026-10-29",
                        "kovalar": dagilim}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"[kapı] baseline yazıldı: {hedef} ({len(dagilim)} soru)")
        return 0

    hatalar: List[str] = []
    hatalar += altin_toplam_kontrol(args.cikti)
    hatalar += tutarlilik_kontrol(args.cikti, beklenen_seri=args.seri or None)
    kova_yol = Path(args.kova)
    if kova_yol.exists():
        hatalar += kova_karsilastir(sonuc_yol, kova_yol)
    else:
        hatalar.append(f"baseline yok: {kova_yol} (önce --kova-yaz)")

    if hatalar:
        print(f"[kapı] KAPALI — {len(hatalar)} hata:")
        for h in hatalar:
            print(f"  - {h}")
        return 1
    print("[kapı] AÇIK — altın toplamlar, tutarlılık ve kova bazelinesi birebir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
