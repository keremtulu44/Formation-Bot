"""FAZ8 zarar teşhisi — kova × domain × giriş-kvadrant kesişimi (salt replay okuma).

Girdi (koşu zaten tamamlandıysa):
* ``olcum_faz8/plan_sonuc.csv``       — plan sonuçları (pnl, mae, kova hesabı)
* ``sonuclar/golge_zincir_faz8ana50/golge_defter.jsonl`` — plan/kaynak_bildirimler
  + tetik_geometri (_gerekce, atr, g1_onaylı) kayıtları
* arşiv kapanışları (``research.arsiv.tf_frame``) — dip_kacış/düşüs kvadrantı

Amaç (kullanıcı talebi):
1) Zarar kovalarının (özellikle n=90 ve n=50) ayrıntılı profili;
2) Domain izin payı: hangi domain/iddia kayıplarda aşırı temsil ediliyor
   ("tüm zararlıların %60'ında tek domain" hipotezinin testi);
3) "Çok erken dalıyor" hipotezinin kvadrant + stop hızı + mae ile ölçümü;
4) Ortak nokta adaylarının stop-içindeki pay vs kâr-içindeki pay karşılaştırması.

Ana sisteme dokunmaz; yalnız defter+CSV+arşiv okur.

Kullanım:
    python research/golge_zarar_teshisi.py --rapor docs/arastirma/ZARAR_TESHISI_A50_2026-11-11.md
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from research.golge_inceleme import W, defter_tara, kvadrant  # noqa: E402

DEFTER = KOK / "sonuclar/golge_zincir_faz8ana50/golge_defter.jsonl"
CSV_YOL = KOK / "docs/arastirma/sonuclar/golge_zincir/olcum_faz8/plan_sonuc.csv"
VARSAYILAN_RAPOR = KOK / "docs/arastirma/ZARAR_TESHISI_A50_2026-11-11.md"

# --- kovalar (FAZ8 raporlarıyla birebir kenarlar) --------------------------
KAR_KOVALARI = [(0.0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, None)]
ZARAR_KOVALARI = [(0.0, -0.5), (-0.5, -1.0), (-1.0, -1.5), (-1.5, None)]  # None = mutlak


def kova_etiketi(pnl: float) -> str:
    if pnl >= 0:
        for lo, hi in KAR_KOVALARI:
            if hi is None or (lo <= pnl < hi):
                tag = f"kâr {lo:g}–{hi:g}A" if hi is not None else f"kâr {lo:g}A+"
                if lo == 0.0 and hi == 0.5 and pnl == 0:
                    return "başa baş (0)"
                return tag
    for lo, hi in ZARAR_KOVALARI:
        if hi is None:
            return f"zarar {lo:g}A ve altı"
        if hi <= pnl < lo:
            return f"zarar {hi:g}–{lo:g}A"
    return "?"


def ana_kova(pnl: float) -> str:
    """Raporlardaki4 ana zarar kovası + kâr/ziyan ayrımı."""
    if pnl >= 0:
        return "kâr"
    if pnl >= -0.5:
        return "zarar 0–0,5"
    if pnl >= -1.0:
        return "zarar 0,5–1"
    if pnl >= -1.5:
        return "zarar 1–1,5"
    return "zarar 1,5+"


def yuzde(pnl: float, giris: float, atr: float) -> float:
    return round(pnl * atr / giris * 100, 3) if giris else 0.0


# --- defter → tetik eşlemesi ----------------------------------------------
def tetikler_bul(defter_t: dict[str, Any]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for d in defter_t["tetik_geometri"]:
        pid = d.get("plan_id")
        if pid:
            out[pid] = d
    return out


def gerekce_ozet(g: str | None) -> dict[str, Any]:
    """UYGUN gerekçesinden zemin + mesafe çıkar."""
    if not g:
        return {"zemin": "?", "mesafe": None}
    m = re.search(r"mesafe ([0-9.]+) ATR", g)
    mesafe = float(m.group(1)) if m else None
    z = g.split(",")[0].replace("G1 ", "").strip()
    return {"zemin": z, "mesafe": mesafe}


# --- ana --------------------------------------------------------------------
def satirlari_topla() -> list[dict[str, Any]]:
    if not DEFTER.exists():
        sys.exit(f"defter yok: {DEFTER} — önce FAZ8 koşusunu yenile")
    t = defter_tara(DEFTER)
    planlar, sonuclar = t["planlar"], t["sonuclar"]
    tetik = tetikler_bul(t)
    plan_atr: dict[str, float] = t["plan_atr"]

    from research.arsiv import tf_frame  # noqa: PLC0415

    kapanis_cache: dict[tuple[str, str], list[float]] = {}
    dip_cache: dict[tuple[str, str], list[float]] = {}

    def kapanis(s: str, tf: str) -> list[float]:
        if (s, tf) not in kapanis_cache:
            kapanis_cache[(s, tf)] = [float(x) for x in tf_frame(s, tf)["close"].tolist()]
        return kapanis_cache[(s, tf)]

    def dipler(s: str, tf: str) -> list[float]:
        if (s, tf) not in dip_cache:
            dip_cache[(s, tf)] = [float(x) for x in tf_frame(s, tf)["low"].tolist()]
        return dip_cache[(s, tf)]

    satirlar: list[dict[str, Any]] = []
    with CSV_YOL.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pid = r["plan_id"]
            p = planlar.get(pid)
            s = sonuclar.get(pid)
            tg = tetik.get(pid, {})
            if p is None or s is None:
                sys.exit(f"defter'de plan/sonuç eksik: {pid}")
            atr = plan_atr.get(pid) or tg.get("atr")
            atr = float(atr)
            pnl = float(r["pnl_atr"])
            giris = float(r["giris"])

            # kvadrant (incelemeyle aynı): dip kaçış / giriş sonrası düşüş
            e = int(r["bar_index"])
            closes = kapanis(r["sembol"], r["tf"])
            prev = closes[max(0, e - W):e]
            dip_kacis = max(0.0, (giris - (min(prev) if prev else giris)) / atr)
            nxt = closes[e + 1:min(len(closes), e + 1 + W)]
            dusus = max(0.0, (giris - (min(nxt) if nxt else giris)) / atr)
            kv = kvadrant(dip_kacis, dusus)

            # --- önceden gözlenebilir ölçütler (giriş anında zaten biliniyor) ---
            stop_mesafe = (giris - float(r["stop"])) / atr
            hedef_mesafe = (float(r["hedef"]) - giris) / atr
            band_lo = float(p.get("band_lo") or 0.0)
            band_hi = float(p.get("band_hi") or 0.0)
            band_pos = ((giris - band_lo) / (band_hi - band_lo)) if band_hi > band_lo else None
            destek = tg.get("destek")
            zemin_hatti = max(float(destek), band_lo) if destek is not None else band_lo
            zemin_mesafe = (giris - zemin_hatti) / atr
            lows = dipler(r["sembol"], r["tf"])
            seg = lows[max(0, e - W):e]
            dip_yasi = (e - (max(0, e - W) + seg.index(min(seg)))) if seg else None
            mom10 = (giris - closes[e - 10]) / atr if e >= 10 else None
            mom5 = (giris - closes[e - 5]) / atr if e >= 5 else None

            # domain izinleri
            kaynak = p.get("kaynak_bildirimler") or ()
            domainler: dict[str, set[str]] = defaultdict(set)
            for girdi in kaynak:
                if ":" in girdi:
                    k, v = girdi.split(":", 1)
                    domainler[k].add(v)
            bilin = p.get("bilinmeyenler") or []
            onaysiz = any("onaysız test" in b for b in bilin)
            frm_baglam = any("formasyon üst sınırı" in b for b in bilin)

            lehte = None
            hs = r.get("hukum_satiri", "")
            if "lehte" in hs:
                try:
                    lehte = int(hs.split("·")[1].strip().split()[0])
                except (IndexError, ValueError):
                    pass

            gz = gerekce_ozet(tg.get("_gerekce"))

            satirlar.append({
                "plan_id": pid, "sembol": r["sembol"], "tf": r["tf"],
                "donem": r["donem"], "sonuc": r["sonuc"],
                "pnl": pnl, "pnl_yuzde": yuzde(pnl, giris, atr),
                "mae": float(r["mae_atr"]), "R": float(r["R"]),
                "cozunme_bar": int(r["cozunme_bar"]), "lehte": lehte,
                "kova": kova_etiketi(pnl), "ana_kova": ana_kova(pnl),
                "kvadrant": kv, "dip_kacis": round(dip_kacis, 3),
                "dusus": round(dusus, 3),
                "domainler": sorted(domainler),
                "domain_komb": tuple(sorted(f"{k}:{v}" for k, v in
                                            ((k, vv) for k, vs in domainler.items() for vv in vs))),
                "kaynak_bildirimler": tuple(sorted(kaynak)),
                "onaysiz": onaysiz, "frm_baglam": frm_baglam,
                "zemin": gz["zemin"], "mesafe": gz["mesafe"],
                "g1_onayli": tg.get("g1_onaylı"),
                "stop_mesafe": round(stop_mesafe, 3),
                "hedef_mesafe": round(hedef_mesafe, 3),
                "band_pos": round(band_pos, 3) if band_pos is not None else None,
                "zemin_mesafe": round(zemin_mesafe, 3),
                "dip_yasi": dip_yasi,
                "mom10": round(mom10, 3) if mom10 is not None else None,
                "mom5": round(mom5, 3) if mom5 is not None else None,
                "atr": atr, "giris": giris,
            })
    return satirlar


def tablo(satirlar: list[dict], anahtar: str, deger: str = "sayi") -> list[tuple]:
    """(ana_kova × özellik) sayım tablosu."""
    kolonlar = ["kâr", "zarar 0–0,5", "zarar 0,5–1", "zarar 1–1,5", "zarar 1,5+"]
    tab: dict[str, Counter] = defaultdict(Counter)
    for s in satirlar:
        v = s[anahtar]
        if isinstance(v, (list, tuple)):
            for vv in v:
                tab[f"{anahtar}={vv}"][s["ana_kova"]] += 1
        else:
            tab[f"{anahtar}={v}"][s["ana_kova"]] += 1
    rows = []
    for k in sorted(tab):
        c = tab[k]
        rows.append((k, *[c.get(x, 0) for x in kolonlar], sum(c.values())))
    return rows


def pay_testi(satirlar: list[dict], alan: str) -> list[dict]:
    """Domain/iddia payı: zarar (stop benzeri) vs kâr içindeki oran + fazla pay."""
    stop = [s for s in satirlar if s["sonuc"] == "stop"]
    hedef = [s for s in satirlar if s["sonuc"] == "hedef"]
    degerler: set[str] = set()
    for s in satirlar:
        v = s[alan]
        if isinstance(v, (list, tuple)):
            degerler.update(str(x) for x in v)
        else:
            degerler.add(str(v))
    out = []
    for d in sorted(degerler):
        def has(s):
            v = s[alan]
            return d in v if isinstance(v, (list, tuple)) else str(v) == d
        ns = sum(1 for s in stop if has(s))
        nh = sum(1 for s in hedef if has(s))
        ps = ns / len(stop) if stop else 0
        ph = nh / len(hedef) if hedef else 0
        out.append({"deger": d, "stop_n": ns, "stop_pay": round(ps, 3),
                    "hedef_n": nh, "hedef_pay": round(ph, 3),
                    "fazla_pay": round(ps - ph, 3),
                    "oran": round(ps / ph, 2) if ph else None})
    out.sort(key=lambda r: -r["fazla_pay"])
    return out


def md_tablo(basliklar: list[str], satirlar: list[list]) -> str:
    l = ["| " + " | ".join(basliklar) + " |",
         "|" + "|".join("---" for _ in basliklar) + "|"]
    for r in satirlar:
        l.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(l)


def rapor(satirlar: list[dict]) -> str:
    n = len(satirlar)
    stoplar = [s for s in satirlar if s["sonuc"] == "stop"]
    karlar = [s for s in satirlar if s["sonuc"] == "hedef"]
    zamanlar = [s for s in satirlar if s["sonuc"] == "zaman"]
    zararli = [s for s in satirlar if s["pnl"] < 0]

    b: list[str] = []
    b.append("# FAZ8 A50 — Zarar Teşhisi (kova × domain × kvadrant)\n")
    b.append(f"*Veri: plan_sonuc.csv + FAZ8 defteri (yeniden koşu) + arşiv kapanışı · "
             f"n={n} plan, {len(stoplar)} stop, {len(zamanlar)} zaman, {len(karlar)} hedef*")

    # --- 1) kova profilleri ---
    b.append("\n## 1) Kova profilleri (ana_kova bazında)\n")
    kovalar = ["kâr", "zarar 0–0,5", "zarar 0,5–1", "zarar 1–1,5", "zarar 1,5+"]
    sat = []
    for k in kovalar:
        g = [s for s in satirlar if s["ana_kova"] == k]
        if not g:
            continue
        kv_c = Counter(s["kvadrant"] for s in g)
        sat.append([
            k, len(g),
            f"{kv_c.get('erken_girdi_dustu', 0)}/{kv_c.get('iyi_zamanlama', 0)}"
            f"/{kv_c.get('gec_girdi_dibi_kacirdi', 0)}/{kv_c.get('yuksekten_girdi_ve_dustu', 0)}",
            round(sum(s["cozunme_bar"] for s in g) / len(g), 1),
            round(sum(s["mae"] for s in g) / len(g), 2),
            round(sum(s["dusus"] for s in g) / len(g), 2),
            round(sum(s["dip_kacis"] for s in g) / len(g), 2),
            round(sum(s["R"] for s in g) / len(g), 2),
            Counter(s["donem"] for s in g).most_common(1)[0][0],
            sum(1 for s in g if s["onaysiz"]),
        ])
    b.append(md_tablo(
        ["kova", "n", "kv erken/iyi/geç/yüksekten", "stop hızı (bar)", "MAE ort",
         "düşüş ort", "dipKaçış ort", "R ort", "dönem baskın", "onaysız n"], sat))

    # --- 2) kvadrant × kova ---
    b.append("\n## 2) Giriş kvadrantı × kova (‘çok erken dalıyor’ testi)\n")
    sat = []
    for kv in ["iyi_zamanlama", "erken_girdi_dustu", "gec_girdi_dibi_kacirdi",
               "yuksekten_girdi_ve_dustu"]:
        g = [s for s in satirlar if s["kvadrant"] == kv]
        if not g:
            continue
        c = Counter(s["ana_kova"] for s in g)
        sc = Counter(s["sonuc"] for s in g)
        sat.append([kv, len(g), sc.get("stop", 0),
                    f"%{round(100 * sc.get('stop', 0) / len(g))}",
                    sc.get("hedef", 0), sc.get("zaman", 0),
                    c.get("zarar 0,5–1", 0), c.get("zarar 1–1,5", 0),
                    c.get("zarar 1,5+", 0),
                    round(sum(s["pnl"] for s in g), 1)])
    b.append(md_tablo(
        ["kvadrant", "n", "stop", "stop %", "hedef", "zaman",
         "zarar.5–1", "zarar1–1.5", "zarar1.5+", "net pnl"], sat))

    # --- 3) domain pay testi ---
    b.append("\n## 3) Domain pay testi — ‘zararların %60’ında tek domain’ hipotezi\n")
    b.append("Aynı domain hem çok yaygın olabilir hem de ayırt edici olmayabilir; "
             "**fazla_pay** (stop payı − hedef payı) ayırt gücüdür.\n")
    for alan, ad in [("domainler", "domain varlığı"),
                     ("domain_komb", "domain:iddia kombinasyonu"),
                     ("kaynak_bildirimler", "tam kaynak seti (format)")]:
        b.append(f"\n### {ad}\n")
        rows = pay_testi(satirlar, alan)[:14]
        b.append(md_tablo(
            ["değer", "stop n", "stop pay", "hedef n", "hedef pay", "fazla pay", "stop/hedef oran"],
            [[r["deger"], r["stop_n"], f"%{round(100 * r['stop_pay'])}",
              r["hedef_n"], f"%{round(100 * r['hedef_pay'])}",
              f"{'+' if r['fazla_pay'] >= 0 else ''}{round(100 * r['fazla_pay'])} puan",
              r["oran"] if r["oran"] is not None else "—"] for r in rows]))

    # --- 4) hükm/zemin ---
    b.append("\n## 4) Tetik anı zemin (G1) & mesafe & lehte & onay\n")
    sat = []
    for zemin in sorted({s["zemin"] for s in satirlar}):
        g = [s for s in satirlar if s["zemin"] == zemin]
        sc = Counter(s["sonuc"] for s in g)
        sat.append([zemin, len(g), sc.get("stop", 0),
                    f"%{round(100 * sc.get('stop', 0) / len(g))}",
                    round(sum(s["pnl"] for s in g), 1)])
    b.append(md_tablo(["zemin", "n", "stop", "stop %", "net pnl"], sat))
    sat = []
    for lehte in sorted({s["lehte"] for s in satirlar}, key=lambda x: (x is None, x)):
        g = [s for s in satirlar if s["lehte"] == lehte]
        sc = Counter(s["sonuc"] for s in g)
        sat.append([f"lehte={lehte}", len(g), sc.get("stop", 0),
                    f"%{round(100 * sc.get('stop', 0) / len(g))}",
                    round(sum(s["pnl"] for s in g), 1)])
    b.append(md_tablo(["hükm gücü", "n", "stop", "stop %", "net pnl"], sat))
    for ad, kisim in [("onaylı (g1)", lambda s: not s["onaysiz"]), ("onaysız test", lambda s: s["onaysiz"])]:
        g = [s for s in satirlar if kisim(s)]
        if g:
            sc = Counter(s["sonuc"] for s in g)
            b.append(f"- **{ad}**: n={len(g)} · stop {sc.get('stop', 0)} "
                     f"(%{round(100 * sc.get('stop', 0) / len(g))}) · "
                     f"net {round(sum(s['pnl'] for s in g), 1)} ATR")

    # --- 5) sembol/tf yoğunlaşma (zarar) ---
    b.append("\n## 5) Zarar kovalarında yoğunlaşma (sembol / tf / dönem)\n")
    for kova in ["zarar 0,5–1", "zarar 1–1,5", "zarar 1,5+"]:
        g = [s for s in satirlar if s["ana_kova"] == kova]
        sym = Counter(s["sembol"] for s in g).most_common(6)
        tfc = Counter(s["tf"] for s in g)
        dnc = Counter(s["donem"] for s in g)
        b.append(f"\n**{kova}** (n={len(g)}): sembol üst6 → "
                 + ", ".join(f"{k}:{v}" for k, v in sym)
                 + f" · tf: {dict(tfc)} · dönem: {dict(dnc)}")

    # --- 6) en yaygın tam format (stop içinde) ---
    b.append("\n## 6) Stop içindeki en yaygın tam kaynak formatı\n")
    fmt = Counter("+".join(s["kaynak_bildirimler"]) for s in stoplar)
    b.append(md_tablo(["format (kaynak seti)", "stop n", "stop pay"],
                      [[k, v, f"%{round(100 * v / len(stoplar))}"] for k, v in fmt.most_common(8)]))
    fmt_k = Counter("+".join(s["kaynak_bildirimler"]) for s in karlar)
    b.append("\nHedefteki en yaygın formatlar:")
    b.append(md_tablo(["format", "hedef n", "hedef pay"],
                      [[k, v, f"%{round(100 * v / len(karlar))}"] for k, v in fmt_k.most_common(5)]))

    # --- 7) erken giriş derinlemesine ---
    b.append("\n## 7) Erken giriş kümesi derinlemesine (erken_girdi_dustu)\n")
    erken = [s for s in satirlar if s["kvadrant"] == "erken_girdi_dustu"]
    if erken:
        erken_stop = [s for s in erken if s["sonuc"] == "stop"]
        b.append(f"- n={len(erken)} · stop {len(erken_stop)} · "
                 f"stop hızı ort {round(sum(s['cozunme_bar'] for s in erken_stop) / len(erken_stop), 1)} bar · "
                 f"düşüş ort {round(sum(s['dusus'] for s in erken) / len(erken), 2)} ATR · "
                 f"net {round(sum(s['pnl'] for s in erken), 1)} ATR")
        b.append(f"- kv×domain: "
                 + ", ".join(f"{k}:{v}" for k, v in
                             Counter(d for s in erken for d in s["domainler"]).most_common()))
        top = Counter(s["sembol"] for s in erken_stop).most_common(8)
        b.append(f"- erken-stop sembolleri üst8: {top}")

    # --- 8) kâr-yan karsilastirma ---
    b.append("\n## 8) Karşılaştırma özeti (ayırt edici sinyaller)\n")
    rows = []
    for alan, ad in [("kvadrant", "giriş kvadrantı"), ("domainler", "domain"),
                     ("onaysiz", "onaysız test"), ("donem", "dönem")]:
        rows.append([ad])
        for r in pay_testi(satirlar, alan)[:3]:
            rows[-1].append(f"{r['deger']}: {r['fazla_pay'] * 100:+.0f} puan")
    b.append(md_tablo(["alan", "stop fazlası (ilk3)", "", ""], rows))

    # --- 9) ön-gözlem ölçütleri ---
    b.append("\n## 9) Önceden gözlenebilir ölçütler — ‘canlıda ayrım mümkün mü?’\n")
    b.append("Kvadrant `dusus` alanı geleceğe bakar (yalnız teşhis için). Bu tablo giriş "
             "anında **zaten bilinebilen** alanlarla kazanan/kaybeden ayrımını ölçer "
             "(R13: önce ölç, karar sonra).\n")
    olculer = [
        ("stop mesafesi (A)", "stop_mesafe"),
        ("hedef mesafesi (A)", "hedef_mesafe"),
        ("R", "R"),
        ("band konumu (0=alt,1=üst)", "band_pos"),
        ("zemin mesafesi (A)", "zemin_mesafe"),
        ("dip kaçış (A)", "dip_kacis"),
        ("dip yaşı (bar)", "dip_yasi"),
        ("momentum10 (A)", "mom10"),
        ("momentum5 (A)", "mom5"),
    ]
    kova_adlari = ["kâr", "zarar 0–0,5", "zarar 0,5–1", "zarar 1–1,5", "zarar 1,5+"]
    rows = []
    for ad, alan in olculer:
        sat = [ad]
        for k in kova_adlari:
            g = [s[alan] for s in satirlar if s["ana_kova"] == k and s[alan] is not None]
            sat.append(round(sum(g) / len(g), 2) if g else "—")
        rows.append(sat)
    b.append(md_tablo(["ölçüt (ort)", *kova_adlari], rows))
    rows = []
    for k in kova_adlari:
        g = [s for s in satirlar if s["ana_kova"] == k]
        if not g:
            continue
        taze = sum(1 for s in g if s["dip_yasi"] is not None and s["dip_yasi"] <= 3)
        dip_dustu = sum(1 for s in g if s["mom10"] is not None and s["mom10"] < -1.0)
        ust_band = sum(1 for s in g if s["band_pos"] is not None and s["band_pos"] >= 0.5)
        rows.append([k, len(g), f"%{round(100 * taze / len(g))}",
                     f"%{round(100 * dip_dustu / len(g))}",
                     f"%{round(100 * ust_band / len(g))}"])
    b.append("\nPaylar:")
    b.append(md_tablo(["kova", "n", "dip taze (≤3 bar)", "düşüş ortası (mom10<−1A)",
                       "üst bant (pos≥0,5)"], rows))

    # --- 10) aday kural taraması (offline; R13: ölç, karar sonra) ---
    b.append("\n## 10) Aday kural taraması — ‘bunu filtreleseydik’ (salt offline)\n")
    b.append("Kural uygulansaydı o işlem **açılmazdı**; ‘kalan net’ = filtreli sistem net’i. "
             "Baseline: n=412, net +175,5A, kazanç %55,8. **Uyarı:** bu tarama post-hoc "
             "çoklu-testtir — seçilecek tek kural yeni (kör) fazda kapı ile doğrulanmalı.\n")

    def f_mom(s):
        return s["mom10"] is not None and s["mom10"] < -1.0

    def f_dip(s):
        return s["dip_kacis"] < 0.5

    def f_r(s):
        return s["R"] > 5.5

    def f_stop(s):
        return s["stop_mesafe"] < 0.9

    def f_zem(s):
        return s["zemin_mesafe"] < 0.8

    kurallar = [
        ("momentum10 < −1A", f_mom),
        ("dip kaçış < 0,5A", f_dip),
        ("R > 5,5 (uzak hedef)", f_r),
        ("stop mesafesi < 0,9A", f_stop),
        ("zemin mesafesi < 0,8A", f_zem),
        ("R>5,5 ∧ dip<0,5", lambda s: f_r(s) and f_dip(s)),
        ("R>5,5 ∧ mom<−1", lambda s: f_r(s) and f_mom(s)),
        ("R>5,5 ∧ stop<0,9", lambda s: f_r(s) and f_stop(s)),
        ("dip<0,5 ∧ mom<−1", lambda s: f_dip(s) and f_mom(s)),
        ("R>5,5 ∧ dip<0,5 ∧ mom<−1", lambda s: f_r(s) and f_dip(s) and f_mom(s)),
    ]
    rows = []
    for ad, f in kurallar:
        kume = [s for s in satirlar if f(s)]
        kalan = [s for s in satirlar if not f(s)]
        if not kume or not kalan:
            continue
        kalan_net = sum(s["pnl"] for s in kalan)
        kalan_kazanc = 100 * sum(1 for s in kalan if s["pnl"] > 0) / len(kalan)
        rows.append([
            ad, len(kume),
            f"{sum(s['pnl'] for s in kume):+.1f}",
            sum(1 for s in kume if s["sonuc"] == "stop"),
            len(kalan), f"{kalan_net:+.1f}",
            f"%{kalan_kazanc:.1f}",
        ])
    b.append(md_tablo(
        ["kural (açılmaz)", "n elenir", "elenen net", "elenen stop",
         "kalan n", "kalan net", "kalan kazanç%"], rows))

    # sayısal doğrulama
    b.append(f"\n---\n*Doğrulama: n={n} · kova toplamı "
             f"{dict(Counter(s['ana_kova'] for s in satirlar))}*")
    return "\n".join(b)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapor", default=str(VARSAYILAN_RAPOR))
    ap.add_argument("--json", default="",
                    help="ham per-plan döküm JSON'u (opsiyonel)")
    args = ap.parse_args()

    satirlar = satirlari_topla()
    icerik = rapor(satirlar)
    yol = Path(args.rapor)
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(icerik, encoding="utf-8")
    print(f"rapor: {yol} ({len(satirlar)} plan)")
    if args.json:
        Path(args.json).write_text(json.dumps(satirlar, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        print(f"json: {args.json}")


if __name__ == "__main__":
    main()
