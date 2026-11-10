# -*- coding: utf-8 -*-
"""Faz6 kalibrasyonu — teyit kurallarını ÇEVRİMDIŞI karşılaştır.

Girdi: kalibrasyon defteri (30 sembol) + UYGUN ∧ geometri tetikleri.
Aday kurallar (hepsi devamlılık; BOS/CHOCH YOK):

* **V1 (yayımlanan):** zemin altı kapanış yok(3) + yeni dip yok(2) + mom3≤0,5
* **V2 (test+hold):** son5 barda zemin **test edilmiş** (low ≤ zemin+0,35 ATR)
  ∧ kapanışlar zemin üstü ∧ giriş kapanışı pencere dibinde değil (geri dönüldü)
* **V3:** V2 + zirve-kovalama sınırı (giriş, son10 bardaki kapanış zirvesine
  ≤0,3 ATR mesafede ise elenir)
* **V4:** V3 + son5 barda zemin altına kapanış yok (muhtemazâr ekleme)

Ölçüt (FAZ6 §3'e göre, şimdi kaydediliyor): retention ≥%40 · erken payı
<mevcut30,5%'in altı (hedef <20%) · stop payı <34% · beklenti (bağımsız
yarış) yükselmeli. Seçim: ölçütleri **en çok** karşılayan varyant.

Not: boşluk (20 bar) offline zincirlenmez — adaylar arası tutarlı kıyaslama
için tüm varyantlarda aynı yaklaşım kullanılır.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research.arsiv import tf_frame  # noqa: E402

DEFTER = Path("docs/arastirma/sonuclar/golge_zincir_faz6kal/golge_defter.jsonl")
W = 10      # kvadrant penceresi
H = 10      # yarış
TEST_P = 5  # test penceresi
TEST_TOL = 0.35
PEAK_TOL = 0.3
MOM3 = 0.5


def yaris(closes, giris_i, giris, stop, hedef, atr):
    for k in range(1, H + 1):
        j = giris_i + k
        if j >= len(closes):
            return "yok", 0.0
        c = closes[j]
        if c <= stop:
            return "stop", -(giris - stop) / atr
        if c >= hedef:
            return "hedef", (hedef - giris) / atr
    return "zaman", (closes[min(giris_i + H, len(closes) - 1)] - giris) / atr


def kvadrant(dip_k, dus_k):
    if dip_k > 1.0 and dus_k > 1.0:
        return "yuksekten"
    if dip_k > 1.0:
        return "gec"
    if dus_k > 1.0:
        return "erken"
    return "iyi"


def main() -> int:
    kayitlar = []
    with DEFTER.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("tip") == "zincir_ozet" and d.get("tur") == "tetik":
                kayitlar.append(d)

    kapanislar: dict[tuple[str, str], list[float]] = {}
    dusukler: dict[tuple[str, str], list[float]] = {}

    def veri(s, tf):
        if (s, tf) not in kapanislar:
            fr = tf_frame(s, tf)
            kapanislar[(s, tf)] = [float(x) for x in fr["close"].tolist()]
            dusukler[(s, tf)] = [float(x) for x in fr["low"].tolist()]
        return kapanislar[(s, tf)], dusukler[(s, tf)]

    adaylar = [d for d in kayitlar
               if d.get("hukum") == "UYGUN" and d.get("geometri")]
    print(f"aday (UYGUN ∧ geometri): {len(adaylar)}")

    sonuclar: dict[str, dict] = {}

    def varyant_sec(varyant, closes, lows, i, atr, giris, zemin):
        """True = bu aday varyanttan geçer."""
        if varyant == "HEPSI":
            return True
        # V1: yayımlanan kural (zemin close3 + yeni dip yok + mom3≤0,5)
        if varyant == "V1":
            if any(closes[j] < zemin for j in range(i - 2, i + 1)):
                return False
            onceki = lows[i - 2:i]
            if onceki and lows[i] < min(onceki):
                return False
            if (closes[i] - closes[i - 3]) / atr > MOM3:
                return False
            return True
        # V5: yeni-dip kuralı YOK (yıkanmayı kesen kural çıkarıldı)
        if varyant == "V5":
            if any(closes[j] < zemin for j in range(i - 2, i + 1)):
                return False
            if (closes[i] - closes[i - 3]) / atr > MOM3:
                return False
            return True
        # V6: sadece zemin close + zirve-kovalama (mom3 yerine zirve mesafesi)
        if varyant == "V6":
            if any(closes[j] < zemin for j in range(i - 4, i + 1)):
                return False
            if (max(closes[i - 9:i + 1]) - giris) / atr <= PEAK_TOL:
                return False
            return True
        # T<n>[tol][P][M]: test+hold penceresi varyantları
        #   T10 = test penceresi10 · tol eki (05/075) · P = zirve cap · M = mom3 cap
        if varyant.startswith("T"):
            kod = varyant[1:]
            tol = TEST_TOL
            if "05" in kod:
                T = int(kod.split("05")[0])
                tol = 0.50
            elif "75" in kod:
                T = int(kod.split("75")[0])
                tol = 0.75
            else:
                T = int(kod)
            pencere_low = min(lows[i - (T - 1):i + 1])
            test = pencere_low <= zemin + tol * atr
            hold = all(closes[j] >= zemin for j in range(i - (T - 1), i + 1))
            geri_donus = closes[i] > min(closes[i - (T - 1):i + 1])
            if not (test and hold and geri_donus):
                return False
            if "P" in kod:   # zirve-kovalama cap
                if (max(closes[i - 9:i + 1]) - giris) / atr <= PEAK_TOL:
                    return False
            if "M" in kod:   # mom3 cap
                if (closes[i] - closes[i - 3]) / atr > MOM3:
                    return False
            return True
        raise KeyError(varyant)

    for varyant in ("HEPSI", "V1", "T10", "T1005", "T1005P", "T1005M",
                    "T1005PM", "T1075", "T1075P", "T1505", "T505"):
        gecen = []
        for d in adaylar:
            closes, lows = veri(d["sembol"], d["tf"])
            i = int(d["bar_index"])
            atr, giris = float(d["atr"]), float(d["giris"])
            zemin = (max(float(d["destek"]), float(d["band_lo"]))
                     if d.get("destek") is not None else float(d["band_lo"]))
            if i < 15 or i < W:
                continue
            if varyant_sec(varyant, closes, lows, i, atr, giris, zemin):
                gecen.append(d)

        # kvadrant + bağımsız yarış
        kv = Counter()
        son = Counter()
        pnl = 0.0
        n = 0
        for d in gecen:
            closes, _ = veri(d["sembol"], d["tf"])
            i = int(d["bar_index"])
            atr, giris = float(d["atr"]), float(d["giris"])
            prev = closes[max(0, i - W):i]
            nxt = closes[i + 1:min(len(closes), i + 1 + W)]
            dip_k = max(0.0, (giris - (min(prev) if prev else giris)) / atr)
            dus_k = max(0.0, (giris - (min(nxt) if nxt else giris)) / atr)
            kv[kvadrant(dip_k, dus_k)] += 1
            s, p = yaris(closes, i, giris, float(d["stop"]), float(d["hedef"]), atr)
            son[s] += 1
            pnl += p
            n += 1
        sonuclar[varyant] = {
            "gecen": n,
            "retention_yuzde": round(n / len(adaylar) * 100, 1) if adaylar else 0,
            "kv": {k: round(v / n * 100, 1) for k, v in kv.most_common()} if n else {},
            "sonuc": dict(son.most_common()),
            "beklenti_atr": round(pnl / n, 4) if n else None,
            "stop_yuzde": round(son.get("stop", 0) / n * 100, 1) if n else None,
        }

    for v, r in sonuclar.items():
        print(f"{v:<6} n={r['gecen']:>4} ret={r['retention_yuzde']:>5}% "
              f"stop={r['stop_yuzde']}% bek={r['beklenti_atr']} kv={r['kv']}")
    out = Path("/tmp/faz6_kalibrasyon_varyantlar.json")
    out.write_text(json.dumps(sonuclar, ensure_ascii=False, indent=1))
    print("yazıldı:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
