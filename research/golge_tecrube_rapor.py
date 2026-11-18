"""FAZ9 Tur A raporları — Cümle Sicili + Sahne Ölçümü + FAZ8 değişmezlik kanıtı.

Girdi:
* FAZ9-A gölge defteri (``sonuclar/golge_zincir_faz9a/golge_defter.jsonl``)
  — plan kayıtlarında ``sahneler`` ve ``aktif_bildirimler`` (FAZ9 A1/A2)
* FAZ8 referans ``olcum_faz8/plan_sonuc.csv`` — değişmezlik karşılaştırması

Çıktı: ``docs/arastirma/faz9_tecrube/CUMLE_SICILI_SAHNE.md``

Kurallar: n≥30 satır; n<30 "nadir — yorum yok"; tek satır tek taban;
karar vermez, yalnız ölçer (sözleşme §B4 tohumu).

Kullanım: python research/golge_tecrube_rapor.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

DEFTER = KOK / "sonuclar/golge_zincir_faz9a/golge_defter.jsonl"
FAZ8_CSV = KOK / "docs/arastirma/sonuclar/golge_zincir/olcum_faz8/plan_sonuc.csv"
CIKTI = KOK / "docs/arastirma/faz9_tecrube/CUMLE_SICILI_SAHNE.md"
N_ESIK = 30


def defter_oku(yol: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    planlar: dict[str, dict] = {}
    sonuclar: dict[str, dict] = {}
    with yol.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            tip = d.get("tip")
            if tip == "plan":
                planlar[d["plan_id"]] = d
            elif tip == "sonuc":
                sonuclar[d["plan_id"]] = d
    return planlar, sonuclar


def satirlar(planlar: dict[str, dict], sonuclar: dict[str, dict]) -> list[dict[str, Any]]:
    out = []
    for pid, p in planlar.items():
        s = sonuclar.get(pid)
        if s is None or s.get("sonuc") == "yok":
            continue
        out.append({
            "plan_id": pid,
            "sembol": p.get("sembol"), "tf": p.get("tf"), "donem": p.get("donem"),
            "sonuc": s["sonuc"], "pnl": float(s.get("pnl_atr") or 0),
            "sahneler": tuple(p.get("sahneler") or ()),
            "baglam": tuple(p.get("aktif_bildirimler") or ()),
        })
    return out


def md_tablo(basliklar: list[str], satirlar_: list[list]) -> str:
    l = ["| " + " | ".join(basliklar) + " |",
         "|" + "|".join("---" for _ in basliklar) + "|"]
    for r in satirlar_:
        l.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(l)


def ozet_satiri(ad: str, g: list[dict]) -> list:
    n = len(g)
    sc = Counter(x["sonuc"] for x in g)
    net = sum(x["pnl"] for x in g)
    karli = sum(1 for x in g if x["pnl"] > 0)
    return [ad, n, sc.get("hedef", 0), sc.get("stop", 0), sc.get("zaman", 0),
            f"%{round(100 * karli / n)}", f"{net:+.1f}",
            f"{net / n:+.3f}"]


def main() -> int:
    if not DEFTER.exists():
        sys.exit(f"defter yok: {DEFTER}")
    planlar, sonuclar = defter_oku(DEFTER)
    sat = satirlar(planlar, sonuclar)

    # ---------- 0) FAZ8 değişmezlik kanıtı ----------
    faz8 = {r["plan_id"]: r for r in csv.DictReader(FAZ8_CSV.open(encoding="utf-8"))}
    id_f8, id_f9 = set(faz8), set(x["plan_id"] for x in sat)
    farkli_sonuc = []
    pnl_fark = []
    for x in sat:
        r = faz8.get(x["plan_id"])
        if r is None:
            continue
        if r["sonuc"] != x["sonuc"]:
            farkli_sonuc.append(x["plan_id"])
        pnl_fark.append(abs(float(r["pnl_atr"]) - x["pnl"]))

    n = len(sat)
    karli = sum(1 for x in sat if x["pnl"] > 0)
    net = sum(x["pnl"] for x in sat)
    sc = Counter(x["sonuc"] for x in sat)

    b: list[str] = []
    b.append("# FAZ9-A — Cümle Sicili & Sahne Ölçümü (Tur A: karar değişmedi)\n")
    b.append(f"*Defter: FAZ9-A replay (ana50) · n={n} plan · "
             f"sonuç {sc.get('hedef', 0)}/{sc.get('stop', 0)}/{sc.get('zaman', 0)} · "
             f"kârlı %{round(100 * karli / n)} · net {net:+.1f}A*")

    b.append("\n## 0) Değişmezlik kanıtı (FAZ8 ile birebir)\n")
    b.append(md_tablo(["kontrol", "sonuç"], [
        ["plan kümesi", f"{len(id_f9)} vs FAZ8 {len(id_f8)} → "
         f"{'BİREBİR ✓' if id_f9 == id_f8 else f'FARKLI ✗ ({len(id_f9 ^ id_f8)} farklı)'}"],
        ["plan başına sonuç farkı", f"{len(farkli_sonuc)} adet"
         + (" ✓" if not farkli_sonuc else f" ✗ örnek: {farkli_sonuc[:5]}")],
        ["pnl mutlak fark (ort)", f"{(sum(pnl_fark) / len(pnl_fark)):.6f} ATR"
         + (" ✓" if pnl_fark and max(pnl_fark) < 1e-6 else "")],
    ]))

    # ---------- 1) Cümle sicili ----------
    b.append("\n## 1) Cümle sicili — kim hangi iddiayla geldi, nasıl bitti (n≥30)\n")
    b.append("Her satır = tetikte **aktif** olan bir cümle (iddia); FAZ9 A1 kaydı. "
             "Kâr = işlem başına ortalama pnl.\n")
    iddia_grup: dict[str, list[dict]] = defaultdict(list)
    for x in sat:
        for jb in x["baglam"]:
            try:
                c = json.loads(jb)
            except json.JSONDecodeError:
                continue
            iddia_grup[f"{c.get('kim')}:{c.get('iddia')}"].append(x)
    satirlar_ = []
    nadir = []
    for k, g in sorted(iddia_grup.items(), key=lambda kv: -len(kv[1])):
        if len(g) >= N_ESIK:
            satirlar_.append(ozet_satiri(k, g))
        else:
            nadir.append(f"{k}({len(g)})")
    b.append(md_tablo(["iddia (kim:id)", "n", "hedef", "stop", "zaman",
                       "kârlı", "net", "işlem başı"], satirlar_))
    if nadir:
        b.append(f"\n*Nadir (n<30, yorum yok): {', '.join(nadir[:12])}"
                 + (" …" if len(nadir) > 12 else "") + "*")

    # ---------- 2) Koşul-kelimeleri ----------
    b.append("\n## 2) Cümle KOŞULU öbekleri (kosul metni ilk40 karakter, n≥30)\n")
    kosul_grup: dict[str, list[dict]] = defaultdict(list)
    for x in sat:
        for jb in x["baglam"]:
            try:
                c = json.loads(jb)
            except json.JSONDecodeError:
                continue
            kosul_grup[f"{c.get('kim')}:{str(c.get('kosul', ''))[:40]}"].append(x)
    satirlar_ = [ozet_satiri(k, g) for k, g in
                 sorted(kosul_grup.items(), key=lambda kv: -len(kv[1]))
                 if len(g) >= N_ESIK]
    b.append(md_tablo(["kim:kosul(40)", "n", "hedef", "stop", "zaman",
                       "kârlı", "net", "işlem başı"], satirlar_[:24]))

    # ---------- 3) Sahne ölçümü ----------
    b.append("\n## 3) Sahne ölçümü — etiket × sonuç (n≥30; etiket = kayıt, filtre değil)\n")
    sahne_grup: dict[str, list[dict]] = defaultdict(list)
    etiket_sayac: Counter = Counter()
    for x in sat:
        for t in x["sahneler"]:
            sahne_grup[t].append(x)
            etiket_sayac[t] += 1
        if not x["sahneler"]:
            etiket_sayac["(etiketsiz)"] += 1
    satirlar_ = [ozet_satiri(k, g) for k, g in
                 sorted(sahne_grup.items(), key=lambda kv: -len(kv[1]))
                 if len(g) >= N_ESIK]
    baseline = ozet_satiri("TÜMÜ (baseline)", sat)
    b.append(md_tablo(["sahne", "n", "hedef", "stop", "zaman",
                       "kârlı", "net", "işlem başı"], [baseline] + satirlar_))
    nadir_s = [f"{k}({len(g)})" for k, g in sahne_grup.items() if len(g) < N_ESIK]
    if nadir_s:
        b.append(f"\n*Nadir sahneler (n<30): {', '.join(sorted(nadir_s))}*")
    b.append(f"\n*Etiket sayısı dağılımı: {dict(etiket_sayac.most_common())}*")

    # ---------- 4) İkili-sahne (çift etiket) ----------
    b.append("\n## 4) Çift-kesişim sahneleri (n≥30, en sık6)\n")
    cift: dict[tuple, list[dict]] = defaultdict(list)
    for x in sat:
        ts = tuple(sorted(x["sahneler"]))
        for i in range(len(ts)):
            for j in range(i + 1, len(ts)):
                cift[(ts[i], ts[j])].append(x)
    satirlar_ = [ozet_satiri(f"{a} ∧ {c}", g) for (a, c), g in
                 sorted(cift.items(), key=lambda kv: -len(kv[1]))
                 if len(g) >= N_ESIK][:6]
    b.append(md_tablo(["sahne çifti", "n", "hedef", "stop", "zaman",
                       "kârlı", "net", "işlem başı"], satirlar_))

    # ---------- 5) Yorum sınırı ----------
    b.append("\n---\n## 5) Yorum kuralları\n")
    b.append("- Bu rapor **karar vermez** (sözleşme): aday listesidir; her aday "
             "ayrı ön-kayıt + kapı ister (FAZ8 usulü).\n"
             "- n<30 sayılmaz; n<300 nadirdir, yalnız sayı basılır.\n"
             "- Aleyhte satır da tecrübedir (envanter §I usulü).\n"
             "- FAZ9 A1/A2 **karar değiştirmedi** (bölüm0 kanıtı) — herhangi bir "
             "fark bu raporun değil, replay determinizminin sorunudur.")

    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    CIKTI.write_text("\n".join(b), encoding="utf-8")
    print(f"yazıldı: {CIKTI} (n={n})")
    print(f"değişmezlik: id_eslesme={id_f9 == id_f8}, sonuc_farki={len(farkli_sonuc)}, "
          f"pnl_maks_fark={max(pnl_fark) if pnl_fark else '—'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
