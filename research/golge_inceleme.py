# -*- coding: utf-8 -*-
"""Giriş–çıkış incelemesi: nerede alındı/çıkıldı, hangi kapı izni kapattı?

Girdi: tam koşu defteri (`golge_defter.jsonl`) + arşiv kapanışları.
Çıktı: `inceleme_ozet.json` + okunur özet (stdout).

Ölçümler (close tabanlı, ATR normalize, pencere ±10 bar, H=10):

* **Giriş kvadrantı** — dip kaçış (girişin önceki10 bardaki dipten farkı) ×
  giriş sonrası düşüş (sonraki10 barda dipte ne kadar kalındı):
  iyi zamanlama / geç girdi (dibi kaçırdı) / erken girdi (düştü) / yüksekten
  alıp düştü.
* **Çıkış kvadrantı** — çıkış, işlem+sonrası bandın neresinde (dip/orta/tepe),
  tepeden geri verilen, satış sonrası koşu (erken satıldı / stop sonrası
  toparlanma), zaman çıkışında hedefe kalan.
* **Engel kapıları** — geçerli geometri ama plan açılmayan tetikler:
  TYR gerekçe kategorisi (BEKLE/RET sebebi) veya20-bar boşluk; her kategori
  için **bağımsız karşıt-olgu yarış** (örtüşmezlik yok, kaba) → "şu kapı
  izni vermeseydi ne olurdu".
* **Geometri red nedenleri** — kart'sız tetikler offline yeniden hesap:
  destek yok / stop çok yakın / stop çok uzak / hedef yok veya R<1,2.
* **Hüküm gücü** — planların girişteki `lehte` sayacı ve UYGUN gerekçesindeki
  desteğe mesafe ile sonuç ilişkisi.

Anti-lookahead: yalnız defter + giriş anına kadar bilinen alanlar; karşıt-olgu
yarışları **gelecek barları okuyan** aynı yarış kurallarıyla (ölçüm amaçlı).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KOK = Path(__file__).resolve().parent.parent
VARSAYILAN_DEFTER = KOK / "docs/arastirma/sonuclar/golge_zincir/golge_defter.jsonl"
VARSAYILAN_CIKTI = KOK / "docs/arastirma/sonuclar/golge_zincir/inceleme_ozet.json"
H = 10                 # zaman stopu / karşıt-olgu yarış penceresi
W = 10                 # giriş-çıkış zamanlama penceresi (± bar)


# --- yardımcılar ------------------------------------------------------------

def gerekce_kategori(g: str | None) -> str:
    if not g:
        return "bilinmiyor"
    if g.startswith("G1 kapandi"):
        return "RET · G1 kapandı (tez öldü)"
    if g.startswith("planda ters"):
        return "RET · planda ters yapı geldi"
    if g.startswith("G1 kapisi"):
        return "BEKLE · G1 kapısı kapalı (motor susar)"
    if g.startswith("taze karsi"):
        return "BEKLE · taze karşıt MS uyarısı sürüyor"
    if g.startswith("celiski"):
        return "BEKLE · çelişki > 1"
    if g.startswith("olgunluk"):
        return "BEKLE · olgunluk yok (desteğe mesafe > 1 ATR)"
    return f"diğer · {g[:48]}"


def yaris(closes: list[float], giris_i: int, giris: float, stop: float,
          hedef: float, atr: float) -> tuple[str, int, float]:
    """Koşucuyla aynı bar-bar yarış (close, eşitlik→stop, H=10, veri biterse yok)."""
    mae = 0.0
    for k in range(1, H + 1):
        j = giris_i + k
        if j >= len(closes):
            return "yok", k, 0.0
        c = closes[j]
        mae = min(mae, (c - giris) / atr)
        if c <= stop:
            return "stop", k, -(giris - stop) / atr
        if c >= hedef:
            return "hedef", k, (hedef - giris) / atr
    return "zaman", H, (closes[min(giris_i + H, len(closes) - 1)] - giris) / atr


def kvadrant(dip_kacis: float, dusus: float) -> str:
    if dip_kacis > 1.0 and dusus > 1.0:
        return "yuksekten_girdi_ve_dustu"
    if dip_kacis > 1.0:
        return "gec_girdi_dibi_kacirdi"
    if dusus > 1.0:
        return "erken_girdi_dustu"
    return "iyi_zamanlama"


# --- defter tarama ----------------------------------------------------------

def defter_tara(defter_yolu: Path) -> dict[str, Any]:
    planlar: dict[str, dict] = {}
    sonuclar: dict[str, dict] = {}
    tetik_geometri: list[dict] = []
    plan_atr: dict[str, float] = {}      # plan_id → tetikteki ATR (kayıtta yok)
    geo_sayim = Counter()
    geo_red = Counter()
    son_hukum: dict[tuple[str, str], tuple[str, str]] = {}   # (s,tf) → (hukum, gerekce)

    with defter_yolu.open(encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            tip = d.get("tip")
            if tip == "hukum":
                son_hukum[(d["sembol"], d["tf"])] = (d["hukum"], d.get("gerekce", ""))
            elif tip == "plan":
                d["_gerekce"] = None
                planlar[d["plan_id"]] = d
            elif tip == "sonuc":
                sonuclar[d["plan_id"]] = d
            elif tip == "zincir_ozet" and d.get("tur") == "tetik":
                if d.get("geometri"):
                    h, g = son_hukum.get((d["sembol"], d["tf"]), (None, None))
                    d["_gerekce"] = g if h == d.get("hukum") else None
                    tetik_geometri.append(d)
                    if d.get("plan_id") and d.get("atr"):
                        plan_atr[d["plan_id"]] = float(d["atr"])
                else:
                    geo_sayim["toplam"] += 1
                    geo_red[_geometri_red_nedeni(d)] += 1

    # plan girişindeki hüküm bilgisi
    for pid, p in planlar.items():
        s = p.get("hukum_satiri", "")
        p["_lehte"] = None
        if "lehte" in s:
            try:
                p["_lehte"] = int(s.split("·")[1].strip().split()[0])
            except (IndexError, ValueError):
                pass
        # UYGUN gerekcesindeki mesafe (aktif hüküm kaydından)
        # (plan barındaki son hukum zaten UYGUN; gerekce tetikle eşleşir)

    return {"planlar": planlar, "sonuclar": sonuclar,
            "tetik_geometri": tetik_geometri, "plan_atr": plan_atr,
            "geo_sayim": geo_sayim, "geo_red": geo_red}


def _geometri_red_nedeni(d: dict) -> str:
    destek = d.get("destek")
    band_lo = d.get("band_lo")
    giris = d.get("giris")
    atr = d.get("atr")
    if destek is None or band_lo is None or not atr:
        return "destek veya bant yok (G1/G5 yapısal)"
    zemin = max(float(destek), float(band_lo))
    stop = zemin - 0.10 * atr
    m = float(giris) - stop
    if m < 0.5 * atr:
        return "stop çok yakın (<0,5 ATR)"
    if m > 2.5 * atr:
        return "stop çok uzak (>2,5 ATR)"
    return "hedef adayı yok veya R<1,2 (karşıt yapı)"


# --- ana analiz -------------------------------------------------------------

def analiz(defter_yolu: Path) -> dict[str, Any]:
    from research.arsiv import tf_frame   # noqa: PLC0415

    t = defter_tara(defter_yolu)
    planlar, sonuclar = t["planlar"], t["sonuclar"]
    tetikler = t["tetik_geometri"]
    plan_atr: dict[str, float] = t["plan_atr"]

    # kapanışlar — planı olan ve karşıt-olgu yarışı gereken seriler
    kapanislar: dict[tuple[str, str], list[float]] = {}

    def kapanis(s: str, tf: str) -> list[float]:
        key = (s, tf)
        if key not in kapanislar:
            frame = tf_frame(s, tf)
            kapanislar[key] = [float(x) for x in frame["close"].tolist()]
        return kapanislar[key]

    def ortalama(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 3) if xs else None

    def dagilim(xs: list[float]) -> dict[str, Any]:
        if not xs:
            return {"n": 0, "ort": None, "p50": None, "p90": None}
        s = sorted(xs)
        return {"n": len(s), "ort": round(sum(s) / len(s), 3),
                "p50": s[len(s) // 2], "p90": s[min(len(s) - 1, int(len(s) * 0.9))]}

    # ----------1) plan giriş/çıkış zamanlaması ----------
    giris_kv = Counter()
    giris_kv_sonuc: dict[str, Counter] = defaultdict(Counter)
    cikis_kv = Counter()
    cikis_kv_sonuc: dict[str, Counter] = defaultdict(Counter)
    lehte_sonuc: dict[str, Counter] = defaultdict(Counter)
    erken_satis: list[float] = []          # hedef çıkışında sonrası koşu (ATR)
    geri_verilen: list[float] = []
    stop_toparlanma: list[float] = []
    stop_dogrulandi = 0
    stop_toparlandi = 0
    zaman_kalan: list[float] = []
    giris_metrikler: dict[str, list[float]] = defaultdict(list)
    en_kotu: list[dict] = []
    censored = 0
    veri_yok = 0

    for pid, p in planlar.items():
        s = sonuclar.get(pid)
        if s is None or s.get("sonuc") == "yok":
            censored += 1
            continue
        closes = kapanis(p["sembol"], p["tf"])
        e = int(p["bar_index"])
        atr = plan_atr.get(pid)
        if not atr:
            veri_yok += 1
            continue
        atr = float(atr)
        if e + 1 >= len(closes):
            veri_yok += 1
            continue
        x = e + int(s.get("cozunme_bar") or H)
        x = min(x, len(closes) - 1)

        # --- giriş ---
        prev = closes[max(0, e - W):e]
        nxt = closes[e + 1:min(len(closes), e + 1 + W)]
        dip_kacis = max(0.0, (float(p["giris"]) - (min(prev) if prev else float(p["giris"]))) / atr)
        dusus = max(0.0, (float(p["giris"]) - (min(nxt) if nxt else float(p["giris"]))) / atr)
        kv = kvadrant(dip_kacis, dusus)
        giris_kv[kv] += 1
        giris_kv_sonuc[kv][s["sonuc"]] += 1
        giris_metrikler["dip_kacis"].append(round(dip_kacis, 3))
        giris_metrikler["dusus"].append(round(dusus, 3))

        # --- çıkış ---
        window = closes[e:min(len(closes), x + W + 1)]
        if window:
            lo, hi = min(window), max(window)
            rng = hi - lo
            cikis_yuzde = (closes[x] - lo) / rng if rng > 0 else 0.5
            yk = ("tepede_satti" if cikis_yuzde >= 0.8
                  else "dibe_satti" if cikis_yuzde <= 0.2 else "orta_yerde")
            cikis_kv[yk] += 1
            cikis_kv_sonuc[yk][s["sonuc"]] += 1

        after = closes[x + 1:min(len(closes), x + 1 + W)]
        peak_trade = max(closes[e:x + 1]) if x >= e else closes[e]
        if s["sonuc"] == "hedef":
            if after:
                erken_satis.append(round((max(after) - closes[x]) / atr, 3))
            geri_verilen.append(round((peak_trade - closes[x]) / atr, 3))
        elif s["sonuc"] == "stop":
            if after:
                rec = (max(after) - closes[x]) / atr
                stop_toparlanma.append(round(rec, 3))
                if min(after) <= float(p["stop"]):
                    stop_dogrulandi += 1          # stop sonrası devam etti
                elif rec >= 0.5:
                    stop_toparlandi += 1          # stop sonrası toparlandı
                else:
                    stop_dogrulandi += 1          # belirsiz → nötr say
            else:
                stop_dogrulandi += 1
        else:  # zaman
            if after:
                geri_verilen.append(round((peak_trade - closes[x]) / atr, 3))
            zaman_kalan.append(round((float(p["hedef"]) - closes[x]) / atr, 3))

        # --- hüküm gücü ---
        if p.get("_lehte") is not None:
            lehte_sonuc[str(p["_lehte"])][s["sonuc"]] += 1

        pnl = float(s.get("pnl_atr") or 0)
        en_kotu.append({"plan_id": pid, "sonuc": s["sonuc"], "pnl_atr": round(pnl, 3),
                        "tf": p["tf"], "donem": p["donem"]})

    en_kotu.sort(key=lambda r: r["pnl_atr"])

    # hedef mesafesi (ATR) — plan + tetik ATR eşleşmesi
    hedef_mesafe: list[float] = []
    hedef_mesafe_zaman: list[float] = []
    for pid, p in planlar.items():
        a = plan_atr.get(pid)
        if not a:
            continue
        m = (float(p["hedef"]) - float(p["giris"])) / a
        hedef_mesafe.append(m)
        s = sonuclar.get(pid)
        if s and s.get("sonuc") == "zaman":
            hedef_mesafe_zaman.append(m)
    hedef_mesafe.sort()
    hedef_mesafe_ozet = dict(
        dagilim(hedef_mesafe),
        max=round(hedef_mesafe[-1], 1) if hedef_mesafe else None,
        on_suz_atr_uzerinde=sum(1 for m in hedef_mesafe if m > 10),
        zaman_alt_kume=dagilim(sorted(hedef_mesafe_zaman)),
    )

    # ----------2) engelli geometrik tetikler (kapı analizi) ----------
    engel: dict[str, dict[str, Any]] = {}
    for d in tetikler:
        if d.get("plan_id"):
            continue                      # plan açıldı, engel değil
        if d.get("hukum") == "UYGUN":
            # Faz6: teyit alanı defterde — False ise giriş teyidi kesti,
            # True ise20-bar boşluk; alan yoksa (eski defter) boşluk say.
            if d.get("teyit") is False:
                kategori = "Faz6 giriş teyidi (devamlılık)"
            else:
                kategori = "20-bar boşluk (üst üste tetik)"
        else:
            kategori = gerekce_kategori(d.get("_gerekce")) or (
                f"{d.get('hukum')} · gerekce eşleşmedi")
        k = engel.setdefault(kategori, {
            "n": 0, "pnl_sum": 0.0, "sonuc": Counter(), "kv": Counter(),
            "ornekler": []})
        k["n"] += 1
        closes = kapanis(d["sembol"], d["tf"])
        # kaçan tetiğin giriş yeri (aynı ±10 bar kvadrantı)
        e = int(d["bar_index"])
        atr_d, giris_d = float(d["atr"]), float(d["giris"])
        prev = closes[max(0, e - W):e]
        nxt = closes[e + 1:min(len(closes), e + 1 + W)]
        dip_k = max(0.0, (giris_d - (min(prev) if prev else giris_d)) / atr_d)
        dus_k = max(0.0, (giris_d - (min(nxt) if nxt else giris_d)) / atr_d)
        k["kv"][kvadrant(dip_k, dus_k)] += 1
        # karşıt-olgu: aynı yarış, bağımsız (örtüşmezlik yok)
        sonuc, _k, pnl = yaris(closes, e, giris_d,
                               float(d["stop"]), float(d["hedef"]), atr_d)
        k["pnl_sum"] += pnl
        k["sonuc"][sonuc] += 1
        if len(k["ornekler"]) < 3 and sonuc == "hedef":
            k["ornekler"].append(d["plan_id"] or f"{d['sembol']}-{d['tf']}-{e}")

    # plan açılmayan UYGUN-boşluk sayısını ayrıca doğru say (plan_id yoksa)
    # ----------3) özet ----------
    def oran(c: Counter) -> dict[str, int]:
        return dict(c.most_common())

    ozet: dict[str, Any] = {
        "kapsam": {
            "plan": len(planlar), "sonuc": len(sonuclar),
            "geometri_gecerli_tetik": len(tetikler),
            "geometri_red_toplam": t["geo_sayim"].get("toplam", 0),
            "censored": censored, "veri_yok": veri_yok,
        },
        "giris_kvadrant": oran(giris_kv),
        "giris_kvadrant_sonuc": {k: oran(v) for k, v in giris_kv_sonuc.items()},
        "giris_metrikler": {k: {"ort": ortalama(v), "p50": sorted(v)[len(v) // 2],
                                "p90": sorted(v)[int(len(v) * 0.9)]}
                            for k, v in giris_metrikler.items()},
        "cikis_kvadrant": oran(cikis_kv),
        "cikis_kvadrant_sonuc": {k: oran(v) for k, v in cikis_kv_sonuc.items()},
        "erken_satis": dict(dagilim(erken_satis),
                           toplam_birakilan_atr=round(sum(erken_satis), 1)),
        "geri_verilen": dagilim(geri_verilen),
        "stop_kalitesi": {
            "dogrulandi_devam_etti": stop_dogrulandi,
            "toparlandi_geri_geldi": stop_toparlandi,
            "toparlanma": dagilim(stop_toparlanma),
        },
        "zaman_cikisi": dict(dagilim(zaman_kalan),
                             hedefe_kalan_notu="medyan esas; ortalama uç değerlerle şişer"),
        "hedef_mesafe_atr": hedef_mesafe_ozet,
        "lehte_gucu": {k: oran(v) for k, v in sorted(lehte_sonuc.items())},
        "kapilar": {
            k: {"n": v["n"], "karsi_olgu_beklenti_atr": round(v["pnl_sum"] / v["n"], 4),
                "toplam_pnl_atr": round(v["pnl_sum"], 1),
                "sonuc": oran(v["sonuc"]), "giris_kvadrant": oran(v["kv"]),
                "ornekler": v["ornekler"]}
            for k, v in sorted(engel.items(), key=lambda kv: -kv[1]["n"])},
        "geometri_red": oran(t["geo_red"]),
        "en_kotu_10": en_kotu[:10],
        "sinirlamalar": [
            "tetik ÖNCESİ kapılar (bant/tepki onayı yoksa tetik hiç yazılmaz) defterde yok — ölçülemedi",
            "karşıt-olgu yarışları bağımsızdır (örtüşmezlik uygulanmaz); kaba üstel",
            "close tabanlı (dip/tepe low-high değil) — koşucuyla tutarlılık için",
        ],
    }
    return ozet


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Giriş-çıkış ve kapı incelemesi")
    p.add_argument("--defter", default=str(VARSAYILAN_DEFTER))
    p.add_argument("--cikti", default=str(VARSAYILAN_CIKTI))
    args = p.parse_args(argv)

    ozet = analiz(Path(args.defter))
    cikti = Path(args.cikti)
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_text(json.dumps(ozet, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(json.dumps({k: v for k, v in ozet.items() if k != "en_kotu_10"},
                     ensure_ascii=False, indent=1))
    print(f"yazıldı: {cikti}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
