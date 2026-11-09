"""◇ ikinci seyreltme turu — ölçüm (2026-11-08).

SORU (ölçümden ÖNCE kilitlendi)
-------------------------------
§10'da zayıf ◇ soğuması 3 → 20 bar yapıldı (737 → 486, −%34). Kalan 486 ◇'in
**297'si hâlâ zayıf**. İkinci bir tur, zayıf ◇'e dokunarak (güçlü ◇, ▲ ve
momentum ASLA) anlamlı bir kazanç daha verir mi — ve bedeli ne?

Bu script KURAL UYGULAMAZ. Üretim kodu bugünkü hâlinde kalır; tüm seçenekler
olay akışı üzerinde **simüle** edilir. Karar, aşağıdaki eşiklerle verilir.

KÜTLE
-----
Günlük (1d), `backfill_data/*_1d.csv.gz` ilk 50 sembol (alfabetik, ≥300 bar) —
§10 ile AYNI kütle (24.549 bar) ki 737 → 486 sayıları birebir karşılaştırılabilsin.

OLAY ÇIKARIMI
-------------
`evaluate_stabil_symbol(..., daily_frame=d)` iki kez koşar:
  * `soğuma = 20` (bugünkü üretim)  → 486 beklentisi
  * `soğuma = 0`  (filtresiz akış)  → her aday deneme, güçlü + zayıf
Mesafe kapısı (1,80 ATR) her iki koşuda da AYNEN yürürlükte: bu ölçüm yalnız
**tekrar soğumasını** değiştirir, yeni bir mesafe/kalite kapısı eklemez.

Sınıflar: GÜÇLÜ = close_reclaim · intrabar_sweep_reclaim · upward_rebase_momentum ·
long_base_breakout.  ZAYIF = weak_reclaim · touch_from_below.
Güçlü ◇ her kuralda **her zaman** basılır (kullanıcı kuralı).

SİMÜLE EDİLEN KURALLAR
----------------------
S0  zayıf soğuma 20 bar                (bugünkü üretim — kontrol)
S1  zayıf soğuma 30 bar
S2  zayıf soğuma 40 bar
S3  zayıf ◇ seviye başına 1            (destek seviyesi değişince sıfırlanır)
S4  zayıf ◇ yalnız hacimli deneme      (rvol ≥ 1,0; soğuma 20 aynen)
S5  20 bar soğuma + seviye başına 1

ÖLÇÜTLER (her kural için)
-------------------------
toplam ◇ · güçlü ◇ · zayıf ◇ · sembol başına medyan / en yoğun · ◇'süz kalan
sembol sayısı · atılan zayıf ◇'lerin **öncü oranı** (o ◇'den sonra 20 bar içinde
bir ▲ oku geldiyse "öncü": atılanların bilgi taşıyıp taşımadığını gösterir).

KARAR EŞİKLERİ (kilitli — ölçümden önce yazıldı)
-----------------------------------------------
Bir kural "anlamlı ikinci tur" sayılır ancak şu DÖRDÜ birden sağlanırsa:
  1. toplam ◇ ≤ 389  (bugünkü 486'dan en az %20 ek kazanç)
  2. yeni ◇'süz sembol yok (kural, bugün ◇ taşıyan bir sembolü ◇'süz bırakmaz)
  3. güçlü ◇ = kontrol ile birebir aynı (güçlüye dokunulmaz)
  4. atılan zayıf ◇'lerin öncü oranı ≤ %40
Aksi hâlde o kural **uygulanmaz**; sonuç "ölçüldü, eşik geçilmedi" diye raporlanır.

REPLAY
------
    PYTHONPATH=. .venv/bin/python research/stabil_cizgi_seyreltme_olcum.py
    → /tmp/ok_cizgi_ikinci_tur.csv (kural özeti) · /tmp/ok_cizgi_olaylar.csv (olaylar)
"""
from __future__ import annotations

import glob
import os

import pandas as pd

from domain_engines.stabil import resistance as resistance_mod
from domain_engines.stabil import signals as signals_mod
from domain_engines.stabil.runtime import evaluate_stabil_symbol

SEMBOL_SAYISI = 50
ONCU_BAR = 20                      # "öncü" tanımı: 20 bar içinde ▲
GUC_LU = {"close_reclaim", "intrabar_sweep_reclaim", "upward_rebase_momentum",
          "long_base_breakout"}
ZAYIF = {"weak_reclaim", "touch_from_below"}
ESIK_TOPLAM = 389
ESIK_ONCU_ORAN = 0.40


def _soguma_ayarla(bar: int) -> None:
    """Üretim sabitini iki modülde birden değiştir (resistance ismi import ediyor)."""
    signals_mod._DIKEY_UYARI_SOGUMA_BAR = bar
    resistance_mod._DIKEY_UYARI_SOGUMA_BAR = bar


def _oku(yol: str) -> pd.DataFrame:
    return (pd.read_csv(yol, compression="gzip", parse_dates=["bar_time"])
            .set_index("bar_time").reset_index()
            .rename(columns={"bar_time": "timestamp"}))


def olaylar(sembol: str, d: pd.DataFrame) -> list[dict]:
    """Filtresiz (soğuma 0) akış: her ◇ adayı + o barın ▲ durumu."""
    out = evaluate_stabil_symbol(sembol, "1d", d, daily_frame=d)
    ok_barlari = [
        b.bar_index for b in out.bar_behaviors
        if (b.reclaim_kind in {"close_reclaim", "intrabar_sweep_reclaim"})
        or b.momentum_kind
    ]
    kayit = []
    for b in out.bar_behaviors:
        tur = b.vertical_attempt_kind
        if not tur:
            continue
        kayit.append(dict(
            sembol=sembol, bar=b.bar_index, tur=tur,
            sinif="G" if tur in GUC_LU else ("Z" if tur in ZAYIF else "?"),
            seviye=round(float(b.support_level or 0.0), 2),
            rvol=float(b.vol_ratio) if b.vol_ratio is not None else float("nan"),
            ok_barlari=ok_barlari,
        ))
    return kayit


BEKLE = {"S0": 20, "S1": 30, "S2": 40, "S5": 20, "S6": 50, "S7": 60,
         "S8": 40}                                   # zayıf ◇ soğuması (bar)


def _sembol_uygula(olaylar: list[dict], kural: str) -> list[dict]:
    """Tek sembolün olay akışına kuralı uygula (soğuma sembol içinde sayılır)."""
    basilan, son_uyari, son_seviye = [], -10**9, None
    for e in sorted(olaylar, key=lambda x: x["bar"]):
        if e["sinif"] != "Z":                     # güçlü/öteki: her zaman basılır
            # Üretimde soğuma saati BASILAN her ◇ ile sıfırlanır (signals.py:425),
            # güçlü de dahil — simülasyon da bunu birebir izler.
            basilan.append(e)
            son_uyari = e["bar"]
            continue
        if e["bar"] - son_uyari < BEKLE.get(kural, 0):
            continue
        if kural in {"S3", "S5"} and son_seviye == e["seviye"]:
            continue
        if kural == "S4" and not (e["rvol"] >= 1.0):
            continue
        # S8: 40 bar soğuma, ama hacimli deneme (rvol ≥ 1,5) soğumayı deler —
        # "gerçek" deneme bilgi taşır, sıradan dokunuş taşımaz.
        if kural == "S8" and e["bar"] - son_uyari < BEKLE["S8"] and not (e["rvol"] >= 1.5):
            continue
        basilan.append(e)
        son_uyari = e["bar"]
        son_seviye = e["seviye"]
    return basilan


def uygula(kayit: list[dict], kural: str) -> list[dict]:
    """Kuralı tüm kütleye uygula — soğuma HER SEMBOLDE sıfırdan sayılır."""
    basilan: list[dict] = []
    for sembol in dict.fromkeys(e["sembol"] for e in kayit):
        basilan += _sembol_uygula([e for e in kayit if e["sembol"] == sembol], kural)
    return basilan


def ozet(ad: str, kayit: list[dict], basilan: list[dict], semboller: list[str]) -> dict:
    toplam = len(basilan)
    guclu = sum(1 for e in basilan if e["sinif"] == "G")
    zayif = sum(1 for e in basilan if e["sinif"] == "Z")
    adet = pd.Series([e["sembol"] for e in basilan]).value_counts()
    bos = sum(1 for s in semboller if adet.get(s, 0) == 0)
    kalan = {(e["sembol"], e["bar"]) for e in basilan}
    atilan = [e for e in kayit if e["sinif"] == "Z" and (e["sembol"], e["bar"]) not in kalan]
    oncu = sum(1 for e in atilan
               if any(0 < b - e["bar"] <= ONCU_BAR for b in e["ok_barlari"]))
    return dict(kural=ad, toplam=toplam, guclu=guclu, zayif=zayif,
                medyan=float(adet.median()) if len(adet) else 0.0,
                en_yogun=int(adet.max()) if len(adet) else 0,
                bost_sembol=bos,
                atilan=len(atilan), oncu=oncu,
                oncu_oran=(100 * oncu / len(atilan)) if atilan else 0.0)


def main() -> int:
    dosyalar = sorted(glob.glob("backfill_data/*_1d.csv.gz"))
    kayit: list[dict] = []
    semboller: list[str] = []
    bar_sayisi = 0
    for yol in dosyalar:
        if len(semboller) >= SEMBOL_SAYISI:
            break
        sembol = os.path.basename(yol).split("_")[0]
        try:
            d = _oku(yol)
        except Exception:
            continue
        if len(d) < 300:
            continue
        try:
            _soguma_ayarla(0)
            kayit += olaylar(sembol, d)
        except Exception:
            continue
        semboller.append(sembol)
        bar_sayisi += len(d)
    _soguma_ayarla(20)

    df = pd.DataFrame([{k: v for k, v in e.items() if k != "ok_barlari"} for e in kayit])
    df.to_csv("/tmp/ok_cizgi_olaylar.csv", index=False)
    print(f"sembol {len(semboller)} · bar {bar_sayisi} · filtresiz olay {len(df)} "
          f"(G {int((df.sinif == 'G').sum())} / Z {int((df.sinif == 'Z').sum())})")

    satirlar = []
    for kod, ad in (("S0", "S0 · 20 bar (bugün)"), ("S1", "S1 · 30 bar"),
                    ("S2", "S2 · 40 bar"), ("S6", "S6 · 50 bar"),
                    ("S7", "S7 · 60 bar"), ("S8", "S8 · 40 bar + rvol≥1,5 deler"),
                    ("S3", "S3 · seviye başına 1"),
                    ("S4", "S4 · rvol ≥ 1,0"), ("S5", "S5 · 20 bar + seviye başına 1")):
        satirlar.append(ozet(ad, kayit, uygula(kayit, kod), semboller))
    tablo = pd.DataFrame(satirlar)
    tablo.to_csv("/tmp/ok_cizgi_ikinci_tur.csv", index=False)

    print("\n=== ◇ İKİNCİ TUR (günlük, 50 sembol) ===")
    print(f"{'kural':30s} {'◇':>5s} {'güçlü':>6s} {'zayıf':>6s} {'medyan':>7s} "
          f"{'en çok':>7s} {'◇’süz':>6s} {'atılan':>7s} {'öncü%':>6s}  karar")
    kontrol = tablo.iloc[0]
    for _, r in tablo.iterrows():
        if r.kural.startswith("S0"):
            karar = "kontrol"
        else:
            gecti = (r.toplam <= ESIK_TOPLAM and r.bost_sembol <= kontrol.bost_sembol
                     and r.guclu == kontrol.guclu and r.oncu_oran <= 100 * ESIK_ONCU_ORAN)
            karar = "EŞİK GEÇTİ" if gecti else "geçmedi"
        print(f"{r.kural:30s} {int(r.toplam):5d} {int(r.guclu):6d} {int(r.zayif):6d} "
              f"{r.medyan:7.1f} {int(r.en_yogun):7d} {int(r.bost_sembol):6d} "
              f"{int(r.atilan):7d} {r.oncu_oran:6.0f}  {karar}")
    print("\neşikler: toplam ◇ ≤ %d · ◇'süz sembol = 0 · güçlü = %d · öncü oranı ≤ %%%d"
          % (ESIK_TOPLAM, int(kontrol.guclu), int(100 * ESIK_ONCU_ORAN)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
