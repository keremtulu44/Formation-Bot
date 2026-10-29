"""REPLAY SORU SETİ (S01–S32) cevap motoru.

``docs/arastirma/REPLAY_SORU_SETI_2026-10-29.md`` belgesindeki 32 soruyu
``arastirma_kosu`` JSONL çıktıları üzerinden hesaplar ve şunları üretir:

* ``docs/arastirma/REPLAY_SORU_YANITLARI_*.md`` — soru başına VERİ / TABLO /
  ANA SAYI / KARAR bloklu Markdown raporu.
* ``<cikti>/soru_seti_sonuclari.json`` — eşik kararlarının makine okunur özeti.

Sözleşme (soru seti §0): anti-lookahead çapalar, ATR birimi, sansür satırı
düşürmez, n + sansür% + güven etiketi her tabloda, C5 ölçüm eşikleri sabit,
gruplama kovaları soru metninde önde tanımlı, karar eşiği ≥12 / 5–12 / <5 pp.

Kullanım::

    python -m research.soru_cevaplama \\
        --cikti arastirma_cikti_p1 --cikti arastirma_cikti_p2 \\
        --rapor docs/arastirma/REPLAY_SORU_YANITLARI_2026-10-29.md

``--cikti`` verilmezse ``arastirma_cikti_p1/_p2`` varsa onlar, yoksa
``arastirma_cikti`` kullanılır. ``--soru S05,S24`` ile tek soru tekrarı yapılır.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

import pandas as pd

# ---------------------------------------------------------------------------
# Sözleşme yardimcilari (§0)
# ---------------------------------------------------------------------------

OLCULEMEDI = "OLCULEMEDI"
CALISTI = "CALISTI"

ZAMAN_BICIMI = "%Y-%m-%d %H:%M:%S%z"  # K1: Europe ISO 'T' yok

# Soru setindeki karar esikleri (§0), puan = percentage point (pp)
ESIK_YAZILIR = 12.0
ESIK_METIN = 5.0

TERMINAL_DURUMLAR = (
    "FORMASYON_TAMAMLANDI",
    "BASARISIZ_KIRILIM",
    "FORMASYON_GECERSIZ",
    "KIRILIM_TEYIT_ALAMADI",
)


def guven(n: float) -> str:
    """§0 C4 güven etiketi."""
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return "YOK"
    n = int(n)
    if n >= 30:
        return "YETERLI"
    if n >= 15:
        return "KISMI"
    return "ZAYIF"


def _fmt(x: Any, basamak: int = 1) -> str:
    if x is None:
        return "-"
    try:
        if isinstance(x, float) and math.isnan(x):
            return "-"
        return f"{float(x):.{basamak}f}"
    except (TypeError, ValueError):
        return str(x)


def _pp(x: Any, basamak: int = 1) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{float(x):+.{basamak}f}"


def karar_ver(fark_pp: float | None, n1: int, n2: int, sansur1: float, sansur2: float) -> str:
    """§0 karar esik uygulamasi: ≥12 YAZILIR, 5–12 METIN, <5 RED."""
    if n1 < 30 or n2 < 30:
        return f"KARAR YOK (guven: {guven(min(n1, n2))}; n1={n1}, n2={n2})"
    if sansur1 > 20 or sansur2 > 20:
        return f"Gozlem notu (sansur>20%: {max(sansur1, sansur2):.1f}%)"
    if fark_pp is None:
        return "KARAR YOK (hesaplanamadi)"
    if abs(fark_pp) >= ESIK_YAZILIR:
        yon = "artis" if fark_pp > 0 else "azalis"
        return f"YAZILIR (fark={_pp(fark_pp)}pp, {yon}, n={n1}/{n2}, sansur<=20%)"
    if abs(fark_pp) >= ESIK_METIN:
        return f"YALNIZ KART METNI (fark={_pp(fark_pp)}pp, n={n1}/{n2})"
    return f"RED (fark={_pp(fark_pp)}pp, |fark|<5)"


def md_table(basliklar: Sequence[str], satirlar: Sequence[Sequence[Any]]) -> str:
    lines = ["| " + " | ".join(str(b) for b in basliklar) + " |",
             "| " + " | ".join("---" for _ in basliklar) + " |"]
    for s in satirlar:
        lines.append("| " + " | ".join(str(v) for v in s) + " |")
    return "\n".join(lines)


def sinif_tablosu(
    df: pd.DataFrame,
    gruplar: Sequence[str],
    sinif_kolonu: str = "yon_tepki_sinifi",
    siniflar: Sequence[str] = (CALISTI, "AZ", "YOK", "TERS"),
) -> pd.DataFrame:
    """Grup başına: toplam n, ölçülen n, sansür%, sınıf yüzdeleri (§0 C3/C3b)."""
    rows = []
    for anahtar, g in df.groupby(list(gruplar), observed=True, dropna=False):
        if not isinstance(anahtar, tuple):
            anahtar = (anahtar,)
        n_top = len(g)
        olculen = g[g[sinif_kolonu].notna() & (g[sinif_kolonu] != OLCULEMEDI)]
        n_olc = len(olculen)
        sansur = 100.0 * (n_top - n_olc) / n_top if n_top else float("nan")
        rec: dict[str, Any] = dict(zip(gruplar, anahtar))
        rec.update({
            "n": n_top,
            "n_olculen": n_olc,
            "sansur_pct": sansur,
            "guven": guven(n_olc),
        })
        for s in siniflar:
            rec[s] = 100.0 * int((olculen[sinif_kolonu] == s).sum()) / n_olc if n_olc else float("nan")
        rows.append(rec)
    return pd.DataFrame(rows)


def calisti_fark(tablo: pd.DataFrame, kolon: str = CALISTI, **eslesme: Any) -> tuple[float | None, int, int, float, float]:
    """İki satır ( eşleşen gruplar ) arasındaki CALISTI farkı + n'ler + sansürler."""
    sec = tablo.copy()
    for k, v in eslesme.items():
        if isinstance(v, (list, tuple, set)):
            sec = sec[sec[k].isin(v)]
        else:
            sec = sec[sec[k] == v]
    if len(sec) != 2:
        return None, 0, 0, 100.0, 100.0
    a, b = sec.iloc[0], sec.iloc[1]
    return (
        float(a[kolon] - b[kolon]),
        int(a["n_olculen"]),
        int(b["n_olculen"]),
        float(a["sansur_pct"]),
        float(b["sansur_pct"]),
    )


def _medyan(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float(s.median()) if len(s) else float("nan")


def _pay(s: pd.Series) -> float:
    """True payı (bool/object); ölçülebilir (notna) payda üzerinden %."""
    s = s.dropna()
    if not len(s):
        return float("nan")
    t = s.map(lambda v: bool(v) if isinstance(v, (bool,)) else (str(v).upper() == "TRUE" if v is not None else False))
    return 100.0 * float(t.sum()) / len(s)


def _pct_of(s: pd.Series, deger: Any) -> float:
    s = s.dropna()
    if not len(s):
        return float("nan")
    return 100.0 * float((s == deger).sum()) / len(s)


# ---------------------------------------------------------------------------
# Veri yükleme
# ---------------------------------------------------------------------------

KOLONLAR: dict[str, tuple[str, ...] | None] = {
    "zone": (
        "zone_id", "symbol", "timeframe", "family", "direction", "beklenen_yon",
        "dogum_bar_time", "dogum_index", "atr_at_birth", "yukseklik_atr",
        "yukseklik_kovasi", "native_terminal_state", "native_terminal_reason",
        "native_terminal_category", "terminal_index", "sansur", "temas_var",
        "config_hash", "engine_version",
    ),
    "dokunus": (
        "episode_id", "zone_id", "symbol", "timeframe", "family", "direction",
        "beklenen_yon", "dokunus_no", "dokunus_baslangic_bar_time",
        "dokunus_bitis_bar_time", "dokunus_baslangic_index", "dokunus_bitis_index",
        "dokunus_bar_sayisi", "sonraki_epizot_index", "arrival_side",
        "approach_direction", "dokunulan_kenar", "kenar_olcum_yonu",
        "atr_at_touch", "yukseklik_atr", "yukseklik_kovasi", "sansur_pencere",
        "sansur_terminal", "native_terminal_category", "terminal_dokunusta",
        "yon_h10", "yon_h12", "yon_h10_sansur", "yon_h12_sansur",
        "yon_h10_kapanis_atr", "yon_h12_kapanis_atr", "yon_h10_decay",
        "yon_h12_decay", "yon_tepe_atr", "yon_tepe_bar", "yon_dip_atr",
        "yon_pay_1", "yon_pay_3", "yon_pay_5", "yon_uzun_sansur",
        "yon_uzun_tepe_atr", "yon_tepki_sinifi", "kenar_tepki_sinifi",
        "kenar_olculmedi", "vp_data_ready", "vp_volume_usable", "vp_capital_usable",
        "vp_rvol", "vp_volume_z_score", "vp_volume_percent_rank", "vp_volume_slope",
        "vp_rtv", "vp_directional_value_pressure_5", "vp_directional_value_pressure_10",
        "vp_net_progress_atr", "vp_directional_efficiency", "vp_volume_result_efficiency",
        "vp_capital_result_efficiency", "vp_effort_result_class",
        "repoh10_window_status", "repoh12_window_status",
        "repoh10_window_complete", "repoh12_window_complete",
        "repoh10_full_window_favorable_excursion_atr",
        "repoh12_full_window_favorable_excursion_atr",
        "repoh12_favorable_excursion_before_native_terminal_atr",
        "repoh12_active_target_eligible",
        "repoh12_native_terminal_within_full_horizon",
        "repoh10_next_same_zone_touch_in_window",
        "repoh12_next_same_zone_touch_in_window",
        "config_hash", "engine_version",
    )
    + tuple(
        f"repoh{h}_target_{e}_atr_{a}"
        for h in (10, 12)
        for e in ("0p5", "1p0", "1p1p5")
        for a in (
            "hit_full_window", "hit_before_native_terminal",
            "possible_on_terminal_bar", "hit_only_after_terminal",
            "active_zone_category",
        )
    ),
    "swing": (
        "symbol", "timeframe", "scope", "identity", "side", "rol_uci", "swing_class",
        "structural_role_final", "rol", "rol_ilk_bar", "rol_son_bar", "rol_sure_bar",
        "rol_kapanis", "price", "confirm_bar", "capa_bar", "atr_at_capa",
        "prominence_atr", "distance_atr", "quality", "broken", "broken_bar",
        "bars_to_break", "bars_to_break_sansur", "bars_to_break_from_rol",
        "kirilim_bar", "kirilim_atr", "engelledi_015", "engelledi_025", "engelledi_050",
        "deneme_bar_025", "deneme_epizot_025", "max_yaklasma_atr", "red_magnitude_atr",
        "gecildi", "sansur", "olculmedi", "vp_data_ready", "vp_volume_usable",
        "vp_rvol", "vp_rtv", "vp_volume_result_efficiency", "vp_directional_efficiency",
        "config_hash", "engine_version",
    ),
    "event": (
        "symbol", "event_uid", "identity", "scope", "event_type", "direction", "candidate_bar",
        "event_bar", "onay_gecikmesi_bar", "broken_level", "broken_swing_identity",
        "origin_price", "quality", "confirmation_status", "validity", "relevance",
        "outcome", "bos_maturity", "age_bars", "confirmed_by", "failed_by",
        "devamlilik_sinifi", "referans_kapanis", "atr_at_event", "gozlenen_bar",
        "sansur", "ters_h12", "uyum", "olculmedi",
        "config_hash", "engine_version",
    )
    + tuple(
        f"devam_{k}"
        for k in (
            "h10", "h12", "h10_sansur", "h12_sansur", "h10_kapanis_atr", "h12_kapanis_atr",
            "h10_decay", "h12_decay", "tepe_atr", "tepe_bar", "dip_atr",
            "pay_1", "pay_3", "pay_5", "uzun_sansur", "uzun_tepe_atr",
        )
    ),
    "frm": None,       # 34k satır: tüm kolonlar
    "frm_olay": None,  # tüm kolonlar
    "meta": None,
}

_KATEGORI_YUKLEYICI: dict[str, Callable[..., pd.DataFrame]] = {}


_KATEGORI_KATEGORILER = (
    "family", "scope", "yon_tepki_sinifi", "kenar_tepki_sinifi",
    "devamlilik_sinifi", "event_type", "pattern_type", "rol",
    "rol_kapanis", "yukseklik_kovasi", "timeframe", "arrival_side",
)


def kategorileri_oku(kategoriler: Sequence[str], dizinler: Sequence[Path]) -> dict[str, pd.DataFrame]:
    """JSONL kategorilerini parça parça okuyup DataFrame'e indirger.

    ``pd.read_json(lines=True, chunksize=…)`` kullanılır: satır satır dict
    listesi kurmadan (3 GB makinada dokunus ~243k × ~190 alan OOM riski)
    tip tahmini pandas'ın C yolunda yapılır. ``KOLONLAR`` tanımlıysa yalnız
    o alanlar (eksik alanlar None doldurulur) tutulur.
    """
    out: dict[str, pd.DataFrame] = {}
    for kat in kategoriler:
        kolonlar = KOLONLAR.get(kat)
        parcalar: list[pd.DataFrame] = []
        for d in dizinler:
            yol = Path(d) / f"{kat}.jsonl"
            if not yol.exists():
                continue
            for chunk in pd.read_json(yol, lines=True, chunksize=50_000, convert_dates=False):
                if kolonlar is not None:
                    for eksik in kolonlar:
                        if eksik not in chunk.columns:
                            chunk[eksik] = None
                    chunk = chunk[list(kolonlar)]
                parcalar.append(chunk)
        df = (pd.concat(parcalar, ignore_index=True) if parcalar else pd.DataFrame())
        for cat in _KATEGORI_KATEGORILER:
            if cat in df.columns:
                df[cat] = df[cat].astype("category")
        out[kat] = df
        print(f"[oku] {kat}: {len(df)} satır, {len(df.columns)} kolon "
              f"({len(dizinler)} dizin)", flush=True)
    return out


# ---------------------------------------------------------------------------
# Yardımcılar: gruplama kovaları (soru metinlerinde önde tanımlı)
# ---------------------------------------------------------------------------

def _kovala(s: pd.Series, araliklar: Sequence[tuple[float, float, str]]) -> pd.Series:
    """[(alt, ust, etiket)]: alt <= x < ust (None/NaN → 'yok')."""
    import numpy as np
    deger = pd.to_numeric(s, errors="coerce")
    etiket = pd.Series(pd.NA, index=s.index, dtype="object")
    for alt, ust, lab in araliklar:
        maske = (deger >= alt) & (deger < ust)
        etiket[maske] = lab
    return etiket.fillna("yok")


def _tepki_mi(df: pd.DataFrame) -> pd.DataFrame:
    """C3 payda temizliği: ölçülebilir tepki satırları."""
    return df[df["yon_tepki_sinifi"].notna() & (df["yon_tepki_sinifi"] != OLCULEMEDI)]


def _tum_tf_family_tablosu(
    df: pd.DataFrame,
    deger_kolonu: str,
    fillna: str = "-",
) -> pd.DataFrame:
    """TF (satır) × family (sütun) pivotu; hücre = deger_kolonu (ör. %)."""
    p = df.pivot_table(index="timeframe", columns="family", values=deger_kolonu,
                       aggfunc="first", observed=True)
    return p.fillna(fillna)


# ---------------------------------------------------------------------------
# Bölüm yükleyicileri (bellek: bölüm bölüm yükle, kullan, bırak)
# ---------------------------------------------------------------------------

class Yukleyici:
    def __init__(self, dizinler: Sequence[Path]):
        self.dizinler = list(dizinler)
        self._onbellek: dict[str, pd.DataFrame] = {}

    def al(self, *kategori: str) -> dict[str, pd.DataFrame]:
        eksik = [k for k in kategori if k not in self._onbellek]
        if eksik:
            veri = kategorileri_oku(eksik, self.dizinler)
            self._onbellek.update(veri)
        return {k: self._onbellek[k] for k in kategori}

    def birak(self, *kategori: str) -> None:
        for k in kategori:
            self._onbellek.pop(k, None)
        gc.collect()


# ---------------------------------------------------------------------------
# §1 — ZONE / TEMAS (S01–S15)
# ---------------------------------------------------------------------------

def s01(y: Yukleyici) -> dict[str, Any]:
    zone = y.al("zone")["zone"]
    dok = y.al("dokunus")["dokunus"]
    ilk = dok[dok["dokunus_no"] == 1].copy()
    ilk = ilk.merge(
        zone[["zone_id", "timeframe", "family", "dogum_index"]],
        on="zone_id", how="left", suffixes=("", "_z"),
    )
    ilk["yas_bar"] = pd.to_numeric(ilk["dokunus_baslangic_index"], errors="coerce") - pd.to_numeric(
        ilk["dogum_index"], errors="coerce")
    ilk = ilk[ilk["yas_bar"] >= 0]
    ilk["yas_kova"] = ilk["yas_bar"].map(
        lambda v: "0-10" if v <= 10 else ("10-20" if v <= 20 else ("<40" if v < 40 else ">=40"))
        if pd.notna(v) else "yok")
    olc = _tepki_mi(ilk)
    t = sinif_tablosu(olc, ["timeframe", "family", "yas_kova"])
    # ana karşılaştırma: <=10 vs >=40 (family havuzu)
    p = t.pivot_table(index="family", columns="yas_kova", values=CALISTI, observed=True)
    n_p = t.pivot_table(index="family", columns="yas_kova", values="n_olculen", observed=True)
    sonuc = {}
    satirlar = []
    for fam in sorted(str(f) for f in p.index):
        a = p.loc[fam].get("0-10", float("nan"))
        b = p.loc[fam].get(">=40", float("nan"))
        na = int(n_p.loc[fam].get("0-10", 0) or 0)
        nb = int(n_p.loc[fam].get(">=40", 0) or 0)
        fark = (a - b) if (pd.notna(a) and pd.notna(b)) else None
        kv = karar_ver(fark, na, nb, 0.0, 0.0)
        satirlar.append([fam, _fmt(a), na, _fmt(b), nb, _pp(fark), kv])
        sonuc[fam] = kv
    # TF×family tutarlılığı: hangi hücrelerde ≤10 > ≥40
    hucre = t.pivot_table(index=["timeframe", "family"], columns="yas_kova",
                          values=CALISTI, observed=True)
    ayt = hucre.get("0-10"), hucre.get(">=40")
    hucre_sayisi, ayni_yon = 0, 0
    if ayt[0] is not None and ayt[1] is not None:
        bir = pd.concat([ayt[0], ayt[1]], axis=1).dropna()
        hucre_sayisi = len(bir)
        ayni_yon = int((bir["0-10"] > bir[">=40"]).sum())
    return {
        "id": "S01", "baslik": "Taze zone (yaş kovası)",
        "veri": f"dokunus_no=1: {len(ilk)} epizod (yas>=0); ölçülebilir: {len(olc)}; "
                f"sansür(OLCULEMEDI)%={100*(len(ilk)-len(olc))/max(len(ilk),1):.1f}",
        "tablo": md_table(
            ["family", "CALISTI%(<=10 bar)", "n", "CALISTI%(>=40 bar)", "n", "fark pp", "karar"],
            satirlar),
        "ana": f"TF×family hücrelerinde <=10 > >=40 yönü: {ayni_yon}/{hucre_sayisi} hücre",
        "karar": "; ".join(f"{k}: {v}" for k, v in sonuc.items()),
        "notlar": ["Yaş kovası sınırları: [0,10], (10,20], (20,40), [40,inf); "
                   "1h FVG yok → 7 TF×family hücresi (OB×4 + FVG×3)."],
    }


def s02(y: Yukleyici) -> dict[str, Any]:
    zone = y.al("zone")["zone"]
    dok = y.al("dokunus")["dokunus"]
    d = dok.merge(zone[["zone_id", "atr_at_birth"]], on="zone_id", how="left")
    d["rejim_orani"] = pd.to_numeric(d["atr_at_touch"], errors="coerce") / pd.to_numeric(
        d["atr_at_birth"], errors="coerce")
    d["rejim_kova"] = _kovala(d["rejim_orani"], [
        (-1e9, 0.8, "<0.8"), (0.8, 1.2, "0.8-1.2"), (1.2, 1.5, "1.2-1.5"), (1.5, 1e9, ">=1.5")])
    olc = _tepki_mi(d[d["rejim_kova"] != "yok"])
    t = sinif_tablosu(olc, ["family", "rejim_kova"])
    satirlar = []
    sonuc = {}
    for fam in sorted(str(f) for f in t["family"].dropna().unique()):
        sec = t[t["family"] == fam]
        p = sec.set_index("rejim_kova")
        a, b = p[CALISTI].get(">=1.5", float("nan")), p[CALISTI].get("0.8-1.2", float("nan"))
        na, nb = int(p["n_olculen"].get(">=1.5", 0) or 0), int(p["n_olculen"].get("0.8-1.2", 0) or 0)
        sa = float(p["sansur_pct"].get(">=1.5", float("nan")))  # varsayılan nan; `or` asla yok! (0.0 sansür geçerli)
        sb = float(p["sansur_pct"].get("0.8-1.2", float("nan")))
        fark = (a - b) if (pd.notna(a) and pd.notna(b)) else None
        kv = karar_ver(fark, na, nb, sa, sb)
        satirlar.append([fam, _fmt(a), na, _fmt(b), nb, _pp(fark), kv])
        sonuc[fam] = kv
    med = _medyan(d["rejim_orani"])
    p90 = float(pd.to_numeric(d["rejim_orani"], errors="coerce").quantile(0.9))
    return {
        "id": "S02", "baslik": "Rejim kayması (atr_at_touch / atr_at_birth)",
        "veri": f"rejim_orani dolu satır: {d['rejim_orani'].notna().sum()}; ölçülebilir: {len(olc)}",
        "tablo": md_table(
            ["family", "CALISTI%(>=1.5)", "n", "CALISTI%(0.8-1.2)", "n", "fark pp", "karar"],
            satirlar)
        + "\n\n" + md_table(
            ["rejim kovası (havuz)", "n", "olçülen", "sansür%", "CALISTI%", "AZ%", "YOK%", "TERS%"],
            [[r["rejim_kova"], r["n"], r["n_olculen"], _fmt(r["sansur_pct"]),
              _fmt(r[CALISTI]), _fmt(r["AZ"]), _fmt(r["YOK"]), _fmt(r["TERS"])]
             for _, r in sinif_tablosu(olc, ["rejim_kova"]).iterrows()]),
        "ana": f"rejim_orani medyan={_fmt(med,2)}, p90={_fmt(p90,2)} (kart eşik adayı)",
        "karar": "; ".join(f"{k}: {v}" for k, v in sonuc.items()),
        "notlar": ["Yükseklik_atr doğumda ölçülür; rejim>=1.5'te kart cümlesi askıya kuralına bağlanır."],
    }


def s03(y: Yukleyici) -> dict[str, Any]:
    dok = y.al("dokunus")["dokunus"].copy()
    dok["olculesiz"] = (dok["kenar_tepki_sinifi"] == OLCULEMEDI).fillna(False)
    dok["kenarsiz"] = dok["dokunulan_kenar"].isin(["TUM_ZONE", "ZONE_ICI"])
    t = dok.groupby(["yukseklik_kovasi", "timeframe", "family"], observed=True).agg(
        n=("episode_id", "size"),
        olculesiz_pct=("olculesiz", lambda s: 100.0 * s.mean()),
        kenarsiz_pct=("kenarsiz", lambda s: 100.0 * s.mean()),
    ).reset_index()
    ana = dok.groupby("yukseklik_kovasi", observed=True).agg(
        n=("episode_id", "size"), olculesiz_pct=("olculesiz", lambda s: 100.0 * s.mean()),
        kenarsiz_pct=("kenarsiz", lambda s: 100.0 * s.mean())).reset_index()
    satirlar = [[r["yukseklik_kovasi"], r["n"], _fmt(r["olculesiz_pct"]),
                 _fmt(r["kenarsiz_pct"]), guven(r["n"])] for _, r in ana.iterrows()]
    # hücre tablosu: kova × TF×family (OLCULEMEDI%)
    p = t.pivot_table(index="yukseklik_kovasi", columns=["timeframe", "family"],
                      values="olculesiz_pct", observed=True)
    karar_huc = {}
    for kova in ("0-0.5", ">=2"):
        row = ana[ana["yukseklik_kovasi"] == kova]
        if len(row):
            karar_huc[kova] = float(row["olculesiz_pct"].iloc[0])
    d0, d2 = karar_huc.get("0-0.5"), karar_huc.get(">=2")
    karar = "KARAR YOK"
    if d0 is not None and d2 is not None:
        e = "kural" if d0 >= 40 else ("uyari" if d0 >= 20 else "kural-yok")
        karar = (f"0-0.5 ATR'de OLCULEMEDI={_fmt(d0)}% → {e}; "
                 f">=2 ATR'de {_fmt(d2)}% (karşılaştırma)")
    return {
        "id": "S03", "baslik": "Kenar ölçülemezliği (yükseklik kovası)",
        "veri": f"tüm epizodlar: {len(dok)}; kenar_tepki_sinifi=OLCULEMEDI: "
                f"{int(dok['olculesiz'].sum())} ({100*dok['olculesiz'].mean():.1f}%)",
        "tablo": md_table(["yükseklik kovası", "n", "OLCULEMEDI%", "TUM_ZONE/ZONE_ICI%", "güven"],
                          satirlar)
        + "\n\n" + p.round(1).to_markdown(),
        "ana": karar,
        "karar": karar,
        "notlar": ["GECERSIZ kenar ayrı sayılır (dokunulan_kenar=GECERSIZ); "
                   "kenar_olcum_yonu bu satırlarda None."],
    }


def s04(y: Yukleyici) -> dict[str, Any]:
    dok = y.al("dokunus")["dokunus"]
    dok = dok.copy()
    dok["sure_kova"] = _kovala(dok["dokunus_bar_sayisi"], [
        (1, 2, "1"), (2, 4, "2-3"), (4, 7, "4-6"), (7, 1e9, ">=7")])
    olc = _tepki_mi(dok[dok["sure_kova"] != "yok"])
    t = sinif_tablosu(olc, ["family", "sure_kova"])
    tepe = olc.groupby(["family", "sure_kova"], observed=True)["yon_tepe_atr"].median().reset_index()
    p = t.pivot_table(index="family", columns="sure_kova", values=CALISTI, observed=True)
    n = t.pivot_table(index="family", columns="sure_kova", values="n_olculen", observed=True)
    satirlar = []
    sonuc = {}
    for fam in sorted(str(f) for f in p.index):
        a, b = p.loc[fam].get("1", float("nan")), p.loc[fam].get(">=7", float("nan"))
        na, nb = int(n.loc[fam].get("1", 0) or 0), int(n.loc[fam].get(">=7", 0) or 0)
        fark = (a - b) if (pd.notna(a) and pd.notna(b)) else None
        kv = karar_ver(fark, na, nb, 0, 0)
        satirlar.append([fam, _fmt(a), na, _fmt(b), nb, _pp(fark), kv])
        sonuc[fam] = kv
    tepe_md = md_table(["family", "süre kovası", "medyan yon_tepe_atr"],
                       [[r["family"], r["sure_kova"], _fmt(r["yon_tepe_atr"], 2)]
                        for _, r in tepe.iterrows()])
    return {
        "id": "S04", "baslik": "Temas süresi (dokun-kaç vs sürtünme)",
        "veri": f"ölçülebilir epizod: {len(olc)} / {len(dok)} (sansür%="
                f"{100*(len(dok)-len(olc))/max(len(dok),1):.1f})",
        "tablo": md_table(["family", "CALISTI%(1 bar)", "n", "CALISTI%(>=7)", "n", "fark pp", "karar"],
                          satirlar) + "\n\n" + tepe_md,
        "ana": "; ".join(f"{k}: {v}" for k, v in sonuc.items()),
        "karar": "; ".join(f"{k}: {v}" for k, v in sonuc.items()),
        "notlar": ["yon_dip_atr negatif korunur (S05 stop sorusuyla birlikte okunur)."],
    }


def s05(y: Yukleyici) -> dict[str, Any]:
    dok = y.al("dokunus")["dokunus"]
    d = _tepki_mi(dok[dok["yon_tepki_sinifi"] == CALISTI]).copy()
    tepe = pd.to_numeric(d["yon_tepe_atr"], errors="coerce")
    dip = pd.to_numeric(d["yon_dip_atr"], errors="coerce")
    d["oran"] = dip.abs() / tepe
    d = d[d["oran"].notna()]
    d["yol_kova"] = _kovala(d["oran"], [(-1e9, 0.25, "<0.25"), (0.25, 0.5, "0.25-0.5"),
                                        (0.5, 1.0, "0.5-1"), (1.0, 1e9, ">=1")])
    d["agir"] = d["oran"] >= 0.5
    t = d.groupby(["family", "yukseklik_kovasi"], observed=True).agg(
        n=("agir", "size"), agir_pay=("agir", lambda s: 100.0 * s.mean())).reset_index()
    t["karar"] = t["agir_pay"].map(
        lambda v: "stop kuralı" if v >= 25 else ("sığ yol koru" if v < 15 else "gözlem"))
    genel = d["agir"].mean() * 100
    sat = [[r["family"], r["yukseklik_kovasi"], r["n"], _fmt(r["agir_pay"]), r["karar"]]
           for _, r in t.iterrows()]
    dip_m, dip_p90 = _medyan(dip), float(dip.quantile(0.9))
    return {
        "id": "S05", "baslik": "Yol acısı (|dip|/tepe, CALISTI temaslarda)",
        "veri": f"CALISTI + oran ölçülebilir: {len(d)}",
        "tablo": md_table(["family", "yükseklik", "n", "|dip|/tepe>=0.5 %", "eşik kararı"], sat)
        + f"\n\nHavuz: medyan dip={_fmt(dip_m,2)} ATR, p90 dip={_fmt(dip_p90,2)} ATR, "
          f"genel >=0.5 payı={_fmt(genel)}%",
        "ana": (f"Genel ağır-yol payı {_fmt(genel)}% "
                f"({'eşiği aşıyor' if genel >= 25 else 'altında'})"),
        "karar": f"{'STOP KURALI (havuz)' if genel >= 25 else 'gözlem/hafif'} — hücreler tabloda",
        "notlar": ["oran eşikleri ESIK_IZGARA içinden (0.25/0.5/1.0)."],
    }


def s06(y: Yukleyici) -> dict[str, Any]:
    dok = y.al("dokunus")["dokunus"]
    d = dok[
        (dok["yon_h10"].notna()) & (dok["yon_h12"].notna())
        & (dok["yon_h10_sansur"] == False)  # noqa: E712
        & (dok["yon_h12_sansur"] == False)   # noqa: E712
    ].copy()
    d["delta"] = pd.to_numeric(d["yon_h12"], errors="coerce") - pd.to_numeric(d["yon_h10"], errors="coerce")

    def _sinif(v):
        if pd.isna(v):
            return OLCULEMEDI
        v = float(v)
        if v < 0:
            return "TERS"
        if v >= 1.0:
            return CALISTI
        if v >= 0.25:
            return "AZ"
        return "YOK"

    d["cls10"] = d["yon_h10"].map(_sinif)
    d["cls12"] = d["yon_h12"].map(_sinif)
    rows = []
    farklar: list[float] = []
    for (tf, fam), g in d.groupby(["timeframe", "family"], observed=True):
        c10 = (g["cls10"] == CALISTI).mean() * 100
        c12 = (g["cls12"] == CALISTI).mean() * 100
        gecis = ((g["cls10"] != CALISTI) & (g["cls12"] == CALISTI)).mean() * 100
        dpp = float(c12 - c10)
        farklar.append(dpp)
        rows.append([tf, fam, len(g), _fmt(g["delta"].median(), 3), _fmt(c10), _fmt(c12),
                     _pp(dpp), _fmt(gecis)])
    # yön kırılımı (direction)
    yon_rows = []
    for (fam, yon), g in d.groupby(["family", "direction"], observed=True):
        yon_rows.append([fam, yon, len(g), _fmt(g["delta"].median(), 3)])
    delta_med = _medyan(d["delta"])
    en_buyuk_dpp = max((abs(x) for x in farklar), default=0.0)
    kulak = pd.DataFrame(rows, columns=["tf", "family", "n", "Δmedyan(12−10)",
                                        "CALISTI%@10", "CALISTI%@12", "Δpp", "geçiş%"])
    tavsiye = "12 bar" if (abs(delta_med) >= 0.15 and en_buyuk_dpp >= 3) else "10 bar"
    return {
        "id": "S06", "baslik": "Horizon 10 vs 12",
        "veri": f"her iki horizon tam dolu (sansur=False): {len(d)}",
        "tablo": kulak.to_markdown(index=False)
        + "\n\n" + md_table(["family", "direction", "n", "Δmedyan"], yon_rows),
        "ana": f"Δ medyan (havuz)={_fmt(delta_med,3)} ATR; en büyük |Δpp|={_fmt(en_buyuk_dpp,1)}",
        "karar": f"TAVSİYE: {tavsiye} (eşik: Δmedyan>=0.15 ATR ve Δpp>=3)",
        "notlar": ["Sınıf geçişi: yon_h10 ve yon_h12 üzerindeki ön-tanımlı tepki sınıfı farkı."],
    }


def s07(y: Yukleyici) -> dict[str, Any]:
    dok = y.al("dokunus")["dokunus"]
    dok = dok.copy()
    dok["no_kova"] = dok["dokunus_no"].map(
        lambda v: "1" if v == 1 else ("2" if v == 2 else ("3+" if pd.notna(v) and v >= 3 else "yok")))
    dok["terminal"] = dok["terminal_dokunusta"].map(lambda v: bool(v) if isinstance(v, bool) else False)
    dok["nat"] = dok["repoh12_window_status"].fillna("") == "NATIVE_TERMINAL_ON_TOUCH"
    t = dok.groupby(["timeframe", "family"], observed=True).agg(
        n=("episode_id", "size"), terminal_pct=("terminal", lambda s: 100.0 * s.mean()),
        nat_pct=("nat", lambda s: 100.0 * s.mean())).reset_index()
    t["guven"] = t["n"].map(guven)
    no_t = dok.groupby(["family", "no_kova"], observed=True)["terminal"].mean().mul(100).reset_index()
    kova_t = dok.groupby(["family", "yukseklik_kovasi"], observed=True)["terminal"].mean().mul(100).reset_index()
    genel = 100.0 * dok["terminal"].mean()
    nat_genel = 100.0 * dok["nat"].mean()
    esik = "kural zorunlu" if genel >= 10 else ("uyarı" if genel >= 5 else "yalnız not")
    return {
        "id": "S07", "baslik": "Temas anında terminal (terminal_dokunusta)",
        "veri": f"tüm epizodlar: {len(dok)}; terminal_dokunusta=True: {int(dok['terminal'].sum())}",
        "tablo": t.round(1).to_markdown(index=False)
        + "\n\nno_kova × terminal%:\n" + no_t.pivot_table(
            index="family", columns="no_kova", values="terminal", observed=True).round(1).to_markdown()
        + "\n\nyükseklik × terminal%:\n" + kova_t.pivot_table(
            index="family", columns="yukseklik_kovasi", values="terminal", observed=True).round(1).to_markdown(),
        "ana": f"havuz terminal_dokunusta={_fmt(genel)}%; "
               f"NATIVE_TERMINAL_ON_TOUCH(repoh12)={_fmt(nat_genel)}%",
        "karar": f"{esik} (havuz {_fmt(genel)}% vs eşik 10/5/5)",
        "notlar": ["repoh12_window_status != COMPLETE satırlarından kart üretilmez (C3)."],
    }


def s08(y: Yukleyici) -> dict[str, Any]:
    dok = y.al("dokunus")["dokunus"]
    kategoriler = ["HIT_BEFORE_NATIVE_TERMINAL", "AMBIGUOUS_ON_TERMINAL_BAR",
                   "HIT_ONLY_AFTER_NATIVE_TERMINAL", "NOT_REACHED"]
    satirlar = []
    kararlar = {}
    for hedef in ("0p5", "1p0", "1p1p5"):
        kol = f"repoh12_target_{hedef}_atr_active_zone_category"
        d = dok[dok[kol].notna() & (dok[kol] != "NOT_EVALUABLE")]
        for fam, g in d.groupby("family", observed=True):
            n = len(g)
            pay = {k: 100.0 * float((g[kol] == k).sum()) / n for k in kategoriler} if n else {}
            satirlar.append([hedef.replace("p", "."), fam, n,
                             _fmt(pay.get(kategoriler[0])), _fmt(pay.get(kategoriler[1])),
                             _fmt(pay.get(kategoriler[2])), _fmt(pay.get(kategoriler[3])),
                             guven(n)])
            if hedef == "1p0":
                kararlar[fam] = pay.get(kategoriler[2], float("nan"))
    karar_md = "; ".join(
        f"{k}: HIT_ONLY_AFTER={_fmt(v)}% → " +
        ("kural+karne" if v >= 15 else ("kart dipnotu" if v >= 5 else "yok"))
        for k, v in kararlar.items())
    # TF dökümü (1p0)
    d1 = dok[dok["repoh12_target_1p0_atr_active_zone_category"].notna()
             & (dok["repoh12_target_1p0_atr_active_zone_category"] != "NOT_EVALUABLE")]
    tf_t = (d1.assign(hit=d1["repoh12_target_1p0_atr_active_zone_category"]
                      == "HIT_ONLY_AFTER_NATIVE_TERMINAL")
              .groupby(["timeframe", "family"], observed=True)
              .agg(n=("hit", "size"), only_after=("hit", lambda s: 100.0 * s.mean()))
              .reset_index())
    return {
        "id": "S08", "baslik": "Hedef zone yaşarken mi vuruluyor (repoh12, 1.0 ATR)",
        "veri": f"değerlendirilebilir epizodlar (kategori!=NOT_EVALUABLE); 1p0: {len(d1)}",
        "tablo": md_table(["hedef", "family", "n", "HIT_BEFORE%", "AMBIGUOUS%", "ONLY_AFTER%",
                           "NOT_REACHED%", "güven"], satirlar)
        + "\n\n1p0 TF×family ONLY_AFTER%:\n" + tf_t.round(1).to_markdown(index=False),
        "ana": karar_md,
        "karar": karar_md,
        "notlar": ["Bu blok kayit.py repoh genişletmesiyle (§8-E1) dokunus satırına geldi."],
    }


def s09(y: Yukleyici) -> dict[str, Any]:
    dok = y.al("dokunus")["dokunus"]
    kol = "repoh12_target_1p0_atr_active_zone_category"
    dok = dok.copy()
    dok["amb"] = dok[kol] == "AMBIGUOUS_ON_TERMINAL_BAR"
    dok["onc"] = dok[kol] == "HIT_BEFORE_NATIVE_TERMINAL"
    d = dok[dok[kol].notna() & (dok[kol] != "NOT_EVALUABLE")]
    rows = []
    for (fam, kova), g in d.groupby(["family", "yukseklik_kovasi"], observed=True):
        n = len(g)
        amb = 100.0 * g["amb"].mean()
        kat1 = 100.0 * g["onc"].mean()
        kat2 = 100.0 * (g["onc"] | g["amb"]).mean()
        rows.append([fam, kova, n, _fmt(amb), _fmt(kat1), _fmt(kat2), _pp(kat2 - kat1),
                     "YETERLİ dusurulur" if amb > 5 else "koru"])
    tablo = md_table(["family", "yükseklik", "n", "AMBIGUOUS%", "kural A: BEFORE%",
                      "kural B: BEFORE+AMB%", "fark pp", "güven etiketi"], rows)
    farklar = []
    for r in rows:
        try:
            farklar.append(abs(float(str(r[6]).replace("+", ""))))
        except (TypeError, ValueError):
            pass
    maks = max(farklar) if farklar else 0.0
    return {
        "id": "S09", "baslik": "Belirsizlik payı (AMBIGUOUS_ON_TERMINAL_BAR)",
        "veri": f"1p0 değerlendirebilir: {len(d)}",
        "tablo": tablo,
        "ana": f"iki sayım kuralı farkı en yüksek {maks:.1f} pp",
        "karar": ("güven etiketi düşürmesi zorunlu (>=5 pp)" if maks >= 5
                  else "etiket korunur (<5 pp)"),
        "notlar": [],
    }


def s10(y: Yukleyici) -> dict[str, Any]:
    dok = y.al("dokunus")["dokunus"]
    kapi = (dok["vp_data_ready"].fillna(False) == True) & (dok["vp_volume_usable"].fillna(False) == True)  # noqa: E712
    d = dok[kapi]
    olc = _tepki_mi(d)
    t = sinif_tablosu(olc, ["family", "vp_effort_result_class"])
    zayif = ["HIGH_EFFORT_WEAK_RESULT", "VERY_HIGH_EFFORT_WEAK_RESULT"]
    guclu = ["HIGH_EFFORT_STRONG_RESULT"]
    t2 = sinif_tablosu(olc, ["family"])
    satirlar = []
    sonuc = {}
    for fam in sorted(str(f) for f in t["family"].dropna().unique()):
        sec = t[t["family"] == fam]
        z = sec[sec["vp_effort_result_class"].isin(zayif)]
        g = sec[sec["vp_effort_result_class"].isin(guclu)]
        pz = (z[CALISTI] * z["n_olculen"]).sum() / max(z["n_olculen"].sum(), 1)
        pg = (g[CALISTI] * g["n_olculen"]).sum() / max(g["n_olculen"].sum(), 1)
        nz, ng = int(z["n_olculen"].sum()), int(g["n_olculen"].sum())
        fark = pz - pg if (nz and ng) else None
        kv = karar_ver(fark, nz, ng, 0, 0)
        satirlar.append([fam, _fmt(pz), nz, _fmt(pg), ng, _pp(fark), kv])
        sonuc[fam] = kv
    matris = olc.pivot_table(index="vp_effort_result_class", columns="family",
                             values="yon_tepki_sinifi",
                             aggfunc=lambda s: 100.0 * (s == CALISTI).mean(),
                             observed=True)
    n_mat = olc.pivot_table(index="vp_effort_result_class", columns="family",
                            values="yon_tepki_sinifi", aggfunc="size", observed=True)
    kapali = 100.0 - 100.0 * kapi.mean()
    return {
        "id": "S10", "baslik": "Efor–sonuç uçurumu (effort_result_class)",
        "veri": f"kapıdan geçen (ready&usable): {int(kapi.sum())}; ölçülebilir tepki: {len(olc)}; "
                f"kapalı oran: {kapali:.1f}%",
        "tablo": md_table(["family", "CALISTI% WEAK(h10+h11)", "n", "CALISTI% STRONG(h9)",
                           "n", "fark pp", "karar"], satirlar)
        + "\n\nsınıf × family CALISTI%:\n" + matris.round(1).to_markdown()
        + "\n\n(n)\n" + n_mat.to_markdown(),
        "ana": "; ".join(f"{k}: {v}" for k, v in sonuc.items()),
        "karar": "; ".join(f"{k}: {v}" for k, v in sonuc.items()),
        "notlar": ["WEAK = HIGH_EFFORT_WEAK_RESULT + VERY_HIGH_EFFORT_WEAK_RESULT (§8-E5)."],
    }


def s11(y: Yukleyici) -> dict[str, Any]:
    dok = y.al("dokunus")["dokunus"]
    d = dok.copy()
    p = pd.to_numeric(d["vp_directional_value_pressure_5"], errors="coerce")
    yukari = d["direction"].map(lambda v: str(v).lower() == "bullish")
    d["baski"] = pd.NA
    d.loc[p.isna(), "baski"] = pd.NA
    d.loc[p.notna() & yukari & (p > 0), "baski"] = "uyumlu"
    d.loc[p.notna() & yukari & (p < 0), "baski"] = "ters"
    d.loc[p.notna() & (~yukari) & (p < 0), "baski"] = "uyumlu"
    d.loc[p.notna() & (~yukari) & (p > 0), "baski"] = "ters"
    d.loc[p.notna() & (p == 0), "baski"] = "notr"
    d = d[d["baski"].isin(["uyumlu", "ters"])]
    olc = _tepki_mi(d)
    t = sinif_tablosu(olc, ["family", "arrival_side", "baski"])
    satirlar = []
    sonuc = {}
    for (fam, yan), g in t.groupby(["family", "arrival_side"], observed=True):
        pvt = g.set_index("baski")
        if "uyumlu" not in pvt.index or "ters" not in pvt.index:
            continue
        a = pvt.loc["uyumlu"]; b = pvt.loc["ters"]
        fark = float(a[CALISTI] - b[CALISTI])
        kv = karar_ver(fark, int(a["n_olculen"]), int(b["n_olculen"]),
                       float(a["sansur_pct"]), float(b["sansur_pct"]))
        satirlar.append([fam, yan, _fmt(a[CALISTI]), int(a["n_olculen"]),
                         _fmt(b[CALISTI]), int(b["n_olculen"]), _pp(fark), kv])
        sonuc[f"{fam}/{yan}"] = kv
    p_m = olc.groupby("baski", observed=True)["vp_directional_value_pressure_5"].median()
    return {
        "id": "S11", "baslik": "Yönlü baskı uyumu (pressure_5 vs zone yönü)",
        "veri": f"uyumlu/ters etiketli: {len(d)}; ölçülebilir: {len(olc)}",
        "tablo": md_table(["family", "arrival_side", "CALISTI% uyumlu", "n", "CALISTI% ters",
                           "n", "fark pp", "karar"], satirlar)
        + "\n\nmedyan pressure_5: " + ", ".join(f"{k}={_fmt(v,3)}" for k, v in p_m.items()),
        "ana": "; ".join(f"{k}: {v}" for k, v in list(sonuc.items())[:6]),
        "karar": "; ".join(f"{k}: {v}" for k, v in sonuc.items())[:600],
        "notlar": ["INSIDE_ZONE / ON_ZONE_BOUNDARY / NO_PREVIOUS_BAR ayrı kovada (tabloda)."],
    }


def s12(y: Yukleyici) -> dict[str, Any]:
    dok = y.al("dokunus")["dokunus"]
    kapi = (dok["vp_data_ready"].fillna(False) == True) & (dok["vp_volume_usable"].fillna(False) == True)  # noqa: E712
    d = dok[kapi].copy()
    olc = _tepki_mi(d)
    olc = olc[olc["vp_volume_percent_rank"].notna() & olc["vp_volume_z_score"].notna()]
    rq = olc["vp_volume_percent_rank"].quantile([0.25, 0.75])
    zq = olc["vp_volume_z_score"].quantile([0.25, 0.75])
    olc["rank_q"] = pd.NA
    olc.loc[olc["vp_volume_percent_rank"] <= rq.iloc[0], "rank_q"] = "Q1"
    olc.loc[olc["vp_volume_percent_rank"] >= rq.iloc[1], "rank_q"] = "Q4"
    olc["z_q"] = pd.NA
    olc.loc[olc["vp_volume_z_score"] <= zq.iloc[0], "z_q"] = "Q1"
    olc.loc[olc["vp_volume_z_score"] >= zq.iloc[1], "z_q"] = "Q4"
    hucre = olc[olc["rank_q"].notna() & olc["z_q"].notna()].copy()
    hucre["hucre"] = "R" + hucre["rank_q"].astype(str) + "Z" + hucre["z_q"].astype(str)
    rows = []
    for (fam), g in hucre.groupby("family", observed=True):
        for h, gg in g.groupby("hucre", observed=True):
            n = len(gg)
            rows.append([fam, h, n, _fmt(100.0 * (gg["yon_tepki_sinifi"] == CALISTI).mean()),
                         guven(n)])
    tablo = md_table(["family", "hücre (R=rank, Z=z)", "n", "CALISTI%", "güven"], rows)
    # Çelişki hücreleri: RQ4Z1 (yüksek rank + düşük z) ve RQ1Z4 (tersi).
    sayim = {h: int((hucre["hucre"] == h).sum())
             for h in ("RQ4Z4", "RQ4Z1", "RQ1Z4", "RQ1Z1")}
    sayim_tablo = md_table(["uç hücre", "n"], [[k, v] for k, v in sayim.items()])
    n_zit1, n_zit2 = sayim["RQ4Z1"], sayim["RQ1Z4"]
    sonuc: dict[str, tuple[float, float, int, int]] = {}
    if n_zit1 or n_zit2:
        for fam in hucre["family"].dropna().unique():
            g = hucre[hucre["family"] == fam]
            a = g[g["hucre"] == "RQ4Z1"]
            b = g[g["hucre"] == "RQ1Z4"]
            if len(a) >= 30 and len(b) >= 30:
                sonuc[fam] = (
                    100.0 * (a["yon_tepki_sinifi"] == CALISTI).mean(),
                    100.0 * (b["yon_tepki_sinifi"] == CALISTI).mean(),
                    len(a), len(b))
    if not n_zit1 and not n_zit2:
        kararlar = [
            "ÇELİŞKİ YOK (her iki zıt hücre de 0 satır): volume_percent_rank ve "
            "volume_z_score AYNI pencerenin monotone dönüşümüdür — yüksek rank ⇔ yüksek z; "
            "iki ölçüt asla ayrışmaz.",
            "SONUÇ: 'hangi ölçüt doğru' sorusu yapısal olarak boştur; kart standardı = "
            "TEK ölçüt (rvol) yeterlidir, ek ölçüt eklenmez (S12 RED: fark yok)."]
    elif not sonuc:
        kararlar = ["zıt hücreler var ama her biri n<30 → KARAR YOK (C4)"]
    else:
        kararlar = []
        for fam, (pa, pb, na, nb) in sonuc.items():
            fark = pa - pb
            kararlar.append(
                f"{fam}: RQ4Z1={_fmt(pa)}% vs RQ1Z4={_fmt(pb)}% → fark {_pp(fark)}pp "
                + ("ölçüt ayrışması → kart standardı belirlenir" if abs(fark) >= 12
                   else "fark yok/az"))
    return {
        "id": "S12", "baslik": "Hacim ölçütü çelişkisi (rank vs z)",
        "veri": f"kapıdan geçen ölçülebilir {len(olc)}; uç çeyrek kesişimi {len(hucre)}",
        "tablo": tablo + "\n\nuç hücre sayıları:\n" + sayim_tablo,
        "ana": " ".join(kararlar),
        "karar": ("RED / kart standardı: rvol tek ölçüt (çelişki yapısal olarak yok)"
                  if (not n_zit1 and not n_zit2) else
                  ("kart standardı: >=12 pp ayrışma varsa kazanan ölçüte sabitlenir"
                   if sonuc else "KARAR YOK (C4)")),
        "notlar": ["Çeyrekler içsel sıralama (run içi); zıt hücreler (RQ4Z1/RQ1Z4) "
                   "aynı pencere-monotonite nedeniyle 0 çıkabilir — bu bir bulgudur."],
    }


def s13(y: Yukleyici) -> dict[str, Any]:
    dok = y.al("dokunus")["dokunus"]
    d = dok[dok["timeframe"].astype(str) == "1h"].copy()
    d["saat"] = d["dokunus_baslangic_bar_time"].str.slice(11, 13)
    d = d[d["saat"].str.match(r"^\d{2}$", na=False)]
    d["saat"] = d["saat"].astype(int)
    olc = _tepki_mi(d[ d["saat"].between(10, 17)])
    t = sinif_tablosu(olc, ["family", "saat"])
    tablo = t.pivot_table(index="family", columns="saat", values=CALISTI, observed=True)
    ntab = t.pivot_table(index="family", columns="saat", values="n_olculen", observed=True)
    satirlar = []
    sonuc = {}
    for fam in sorted(str(f) for f in tablo.index):
        erken = [tablo.loc[fam].get(s) for s in (10,)]
        gec = [tablo.loc[fam].get(s) for s in (17,)]
        ref = [tablo.loc[fam].get(s) for s in (12, 13, 14)]
        ref = [x for x in ref if pd.notna(x)]
        if not ref:
            continue
        refm = sum(ref) / len(ref)
        a = erken[0] if erken and pd.notna(erken[0]) else float("nan")
        b = gec[0] if gec and pd.notna(gec[0]) else float("nan")
        n_a = int(ntab.loc[fam].get(10, 0) or 0); n_b = int(ntab.loc[fam].get(17, 0) or 0)
        n_r = int(sum(int(ntab.loc[fam].get(s, 0) or 0) for s in (12, 13, 14)))
        fark_a, fark_b = (a - refm), (b - refm)
        satirlar.append([fam, _fmt(a), n_a, _fmt(b), n_b, _fmt(refm), n_r,
                         _pp(fark_a), _pp(fark_b)])
        en_kotu = min(x for x in tablo.loc[fam].dropna())
        en_iyi = max(x for x in tablo.loc[fam].dropna())
        sonuc[fam] = en_iyi - en_kotu
    karar = "; ".join(
        f"{k}: en_iyi−en_kötü {_pp(v)}pp → " +
        ("süzgeç" if v >= 12 else ("kart metni" if v >= 5 else "yok"))
        for k, v in sonuc.items())
    return {
        "id": "S13", "baslik": "Saat dilimi etkisi (1h, Europe/Istanbul)",
        "veri": f"1h epizod (10–17 arası saat): {len(olc)}",
        "tablo": md_table(["family", "CALISTI% 10:00", "n", "CALISTI% 17:00", "n",
                           "ref 12–15 ort.", "n", "Δ10 pp", "Δ17 pp"], satirlar)
        + "\n\ntüm saatler:\n" + tablo.round(1).to_markdown(),
        "ana": karar,
        "karar": karar,
        "notlar": ["1d'de saat anlamsız → kapsam 1h."],
    }


def s14(y: Yukleyici) -> dict[str, Any]:
    dok, meta = y.al("dokunus", "meta")["dokunus"], y.al("meta")["meta"]
    usable = (dok["vp_data_ready"].fillna(False) == True) & (dok["vp_volume_usable"].fillna(False) == True)  # noqa: E712
    t = dok.assign(kapi=usable).groupby(["timeframe", "family"], observed=True).agg(
        n=("episode_id", "size"), kapali_pct=("kapi", lambda s: 100.0 * (~s).mean())).reset_index()
    t["guven"] = t["n"].map(guven)
    q = meta["vp_data_quality"].value_counts(dropna=False)
    t_g30 = t[t["n"] >= 30]
    en_kotu = float((t_g30 if len(t_g30) else t)["kapali_pct"].max())
    return {
        "id": "S14", "baslik": "Hacim veri kapısı",
        "veri": f"epizod: {len(dok)}; run_meta: {len(meta)}",
        "tablo": t.round(1).to_markdown(index=False)
        + "\n\nvp_data_quality (run_meta): "
        + ", ".join(f"{k}={v}" for k, v in q.items()),
        "ana": f"en kötü hücre kapanı {en_kotu:.1f}%",
        "karar": ("S10–S12 geçersiz hücre yok (en kötü <20%)" if en_kotu < 20
                  else f"S10–S12 için kapalı hücreler var (max {en_kotu:.1f}%) → o hücrelerde karar yok"),
        "notlar": [],
    }


def s15(y: Yukleyici) -> dict[str, Any]:
    dok = y.al("dokunus")["dokunus"]
    d = dok[(dok["repoh12_window_complete"].fillna(False) == True)].copy()  # noqa: E712
    d["no_kova"] = d["dokunus_no"].map(lambda v: "1" if v == 1 else ("2" if v == 2 else "3+"))
    d["bayrak"] = d["repoh12_next_same_zone_touch_in_window"].fillna(False) == True  # noqa: E712
    d = d[d["yon_tepki_sinifi"].isin([CALISTI, "YOK"])]
    rows = []
    sonuc = {}
    for (fam, no), g in d.groupby(["family", "no_kova"], observed=True):
        a = g[g["yon_tepki_sinifi"] == CALISTI]
        b = g[g["yon_tepki_sinifi"] == "YOK"]
        if len(a) < 15 or len(b) < 15:
            continue
        pa, pb = 100.0 * a["bayrak"].mean(), 100.0 * b["bayrak"].mean()
        fark = pa - pb
        kv = karar_ver(fark, len(a), len(b), 0, 0)
        rows.append([fam, no, _fmt(pa), len(a), _fmt(pb), len(b), _pp(fark), kv])
        sonuc[f"{fam}/no{no}"] = kv
    bayraklilar = d[d["bayrak"] & (d["yon_tepki_sinifi"] == CALISTI)]
    bosluk = (pd.to_numeric(bayraklilar["sonraki_epizot_index"], errors="coerce")
              - pd.to_numeric(bayraklilar["dokunus_baslangic_index"], errors="coerce")).median()
    return {
        "id": "S15", "baslik": "Zone tekrar ziyareti",
        "veri": f"repoh12 tam pencere + CALISTI/YOK: {len(d)}; bayraklı: {int(d['bayrak'].sum())}",
        "tablo": md_table(["family", "dokunus_no", "CALISTI'de bayrak%", "n", "YOK'ta bayrak%",
                           "n", "fark pp", "karar"], rows),
        "ana": f"dönüş gecikmesi medyanı (bayraklı CALISTI): {bosluk} bar",
        "karar": "; ".join(f"{k}: {v}" for k, v in sonuc.items())[:600],
        "notlar": ["Bayrak repoh12_next_same_zone_touch_in_window; pencere tam değilse False (kod sözleşmesi)."],
    }


# ---------------------------------------------------------------------------
# §2 — MS SWING (S16–S21)
# ---------------------------------------------------------------------------

def _scope_sec(swing: pd.DataFrame) -> pd.DataFrame:
    s = swing.copy()
    s["scope"] = s["scope"].astype(str).str.upper()
    return s


def s16(y: Yukleyici) -> dict[str, Any]:
    sw = _scope_sec(y.al("swing")["swing"])
    d = sw[sw["rol"].isin(["PH", "PL"]) & sw["engelledi_025"].notna()].copy()
    d["sure_kova"] = _kovala(d["rol_sure_bar"], [
        (1, 6, "1-5"), (6, 11, "6-10"), (11, 21, "11-20"), (21, 1e9, ">=21")])
    d = d[d["sure_kova"] != "yok"]
    rows = []
    sonuc = {}
    for (scope, side, kova), g in d.groupby(["scope", "side", "sure_kova"], observed=True):
        true_pay = 100.0 * (g["engelledi_025"] == True).mean()  # noqa: E712
        none_pay = 100.0 * g["engelledi_025"].isna().mean()
        rows.append([scope, side, kova, len(g), _fmt(true_pay), _fmt(none_pay), guven(len(g))])
    t = pd.DataFrame(rows, columns=["scope", "side", "kova", "n", "engelledi%", "sansür%", "güven"])
    for scope in ("EXTERNAL", "INTERNAL"):
        for side in ("HIGH", "LOW"):
            sec = t[(t["scope"] == scope) & (t["side"] == side)].set_index("kova")
            if ">=21" in sec.index and "1-5" in sec.index:
                a, b = sec.loc[">=21"], sec.loc["1-5"]
                fark = float(a["engelledi%"]) - float(b["engelledi%"])
                sonuc[f"{scope}/{side}"] = (fark, int(a["n"]), int(b["n"]))
    return {
        "id": "S16", "baslik": "Rol süresi → koruma (PH/PL)",
        "veri": f"PH/PL + engelledi_025 dolu: {len(d)} rol aralığı",
        "tablo": md_table(["scope", "side", "rol süresi", "n", "engelledi_025=True%",
                           "sansür(None)%", "güven"], rows),
        "ana": "; ".join(
            f"{k}: fark {_pp(v[0])}pp (n={v[1]}/{v[2]}) → " + karar_ver(v[0], v[1], v[2], 0, 0)
            for k, v in sonuc.items()),
        "karar": "; ".join(
            f"{k}:{karar_ver(v[0], v[1], v[2], 0, 0).split(' (')[0]}" for k, v in sonuc.items()),
        "notlar": ["scope/side büyük harf gerçek değerler (§8-E7)."],
    }


def s17(y: Yukleyici) -> dict[str, Any]:
    sw = _scope_sec(y.al("swing")["swing"])
    d = sw[sw["engelledi_025"].notna() & sw["prominence_atr"].notna()].copy()
    d["prom_kova"] = _kovala(d["prominence_atr"], [
        (0, 0.5, "0-0.5"), (0.5, 1, "0.5-1"), (1, 2, "1-2"), (2, 1e9, ">=2")])
    d = d[d["prom_kova"] != "yok"]
    rows = []
    sonuc = {}
    for (scope, side), g in d.groupby(["scope", "side"], observed=True):
        pvt = g.groupby("prom_kova", observed=True)["engelledi_025"].apply(
            lambda s: 100.0 * (s == True).mean())  # noqa: E712
        n_pvt = g.groupby("prom_kova", observed=True).size()
        for kova in pvt.index:
            rows.append([scope, side, kova, int(n_pvt[kova]), _fmt(pvt[kova]), guven(int(n_pvt[kova]))])
        if ">=2" in pvt.index and "0-0.5" in pvt.index:
            fark = float(pvt[">=2"]) - float(pvt["0-0.5"])
            sonuc[f"{scope}/{side}"] = (fark, int(n_pvt[">=2"]), int(n_pvt["0-0.5"]))
    return {
        "id": "S17", "baslik": "Belirginlik → koruma",
        "veri": f"prominence + engelledi dolu: {len(d)}",
        "tablo": md_table(["scope", "side", "prominence", "n", "engelledi=True%", "güven"], rows),
        "ana": "; ".join(f"{k}: >=2 vs <0.5 fark {_pp(v[0])}pp" for k, v in sonuc.items()),
        "karar": "; ".join(
            f"{k}:{karar_ver(v[0], v[1], v[2], 0, 0).split(' (')[0]}" for k, v in sonuc.items()),
        "notlar": ["Kovalar yükseklik kovası sınırlarıyla aynı."],
    }


def s18(y: Yukleyici) -> dict[str, Any]:
    sw = _scope_sec(y.al("swing")["swing"])
    d = sw[sw["capa_bar"].notna() & sw["confirm_bar"].notna() & sw["engelledi_025"].notna()].copy()
    d["gecikme"] = pd.to_numeric(d["capa_bar"], errors="coerce") - pd.to_numeric(d["confirm_bar"], errors="coerce")
    d["gec_kova"] = _kovala(d["gecikme"], [(-1e9, 2, "0-1"), (2, 5, "2-4"), (5, 1e9, ">=5")])
    d = d[d["gec_kova"] != "yok"]
    rows = []
    sonuc = {}
    for scope, g in d.groupby("scope", observed=True):
        pvt = g.groupby("gec_kova", observed=True)["engelledi_025"].apply(
            lambda s: 100.0 * (s == True).mean())  # noqa: E712
        n_pvt = g.groupby("gec_kova", observed=True).size()
        for kova in pvt.index:
            rows.append([scope, kova, int(n_pvt[kova]), _fmt(pvt[kova]), guven(int(n_pvt[kova]))])
        if ">=5" in pvt.index and "0-1" in pvt.index:
            sonuc[scope] = (float(pvt["0-1"]) - float(pvt[">=5"]),
                            int(n_pvt["0-1"]), int(n_pvt[">=5"]))
    rol_atanmadi = 100.0 * (sw["rol_kapanis"].astype(str) == "ROL_ATANMADI").mean()
    return {
        "id": "S18", "baslik": "Geç rol ataması",
        "veri": f"capa+confirm+engelledi dolu: {len(d)} (ROL_ATANMADI hariç; havuzda "
                f"%{_fmt(rol_atanmadi)} )",
        "tablo": md_table(["scope", "atama gecikmesi", "n", "engelledi=True%", "güven"], rows),
        "ana": "; ".join(f"{scope}: 0-1 vs >=5 fark {_pp(v[0])}pp" for scope, v in sonuc.items()),
        "karar": "; ".join(
            f"{scope}:{karar_ver(v[0], v[1], v[2], 0, 0).split(' (')[0]}" for scope, v in sonuc.items()),
        "notlar": ["gecikme = capa_bar − confirm_bar (rol atama anı − onay)."],
    }


def s19(y: Yukleyici) -> dict[str, Any]:
    sw = _scope_sec(y.al("swing")["swing"])
    rows = []
    turler = ["DEVREDILDI", "TEMIZLENDI", "VERI_SONU_SANSURLU", "ROL_ATANMADI"]
    for (scope, side), g in sw.groupby(["scope", "side"], observed=True):
        n = len(g)
        for tur in turler:
            pay = 100.0 * float((g["rol_kapanis"].astype(str) == tur).sum()) / n
            alt = g[g["rol_kapanis"].astype(str) == tur]
            brk = 100.0 * float((alt["broken"] == True).sum()) / max(len(alt), 1)  # noqa: E712
            med = _medyan(alt["rol_sure_bar"])
            rows.append([scope, side, tur, len(alt), _fmt(pay), _fmt(brk), _fmt(med, 1)])
    # rol bazlı (ana soru: DEVREDILDI payı PH'de ne)
    rol_rows = []
    for (scope, rol), g in sw[sw["rol"].notna()].groupby(["scope", "rol"], observed=True):
        n = len(g)
        dev = 100.0 * float((g["rol_kapanis"].astype(str) == "DEVREDILDI").sum()) / n
        rol_rows.append([scope, rol, n, _fmt(dev), guven(n)])
    genel_dev = 100.0 * float((sw["rol_kapanis"].astype(str) == "DEVREDILDI").sum()) / len(sw)
    return {
        "id": "S19", "baslik": "Rol kapanış türü (DEVREDILDI / TEMIZLENDI / …)",
        "veri": f"tüm rol aralıkları: {len(sw)}",
        "tablo": md_table(["scope", "side", "kapanış", "n", "pay%", "broken%", "medyan süre"], rows)
        + "\n\nrol × DEVREDILDI payı:\n" + md_table(["scope", "rol", "n", "DEVREDILDI%", "güven"],
                                                    rol_rows),
        "ana": f"havuz DEVREDILDI payı {_fmt(genel_dev)}% (eşik: >=25 kart cümlesi, <10 koru)",
        "karar": ("DEVREDILDI kart cümlesi yazılır" if genel_dev >= 25
                  else ("gözlem" if genel_dev >= 10 else "engellendi ifadesi korunur")),
        "notlar": ["'KIRILDI' kapanış türü YOK; kırılım ayrı alandır (broken). §8-E6."],
    }


def s20(y: Yukleyici) -> dict[str, Any]:
    sw = _scope_sec(y.al("swing")["swing"])
    d = sw[(sw["broken"] == True)].copy()  # noqa: E712
    d["bt_kova"] = _kovala(d["bars_to_break"], [
        (1, 2, "1"), (2, 4, "2-3"), (4, 7, "4-6"), (7, 1e9, ">=7")])
    rows = []
    sonuc = {}
    for (scope, side), g in d.groupby(["scope", "side"], observed=True):
        olc = g[g["kirilim_atr"].notna()]
        med_asim = _medyan(olc["kirilim_atr"])
        med_bt = _medyan(g["bars_to_break"])
        sig = 100.0 * (olc["kirilim_atr"] < 0.25).mean() if len(olc) else float("nan")
        sansur = 100.0 * (1 - len(olc) / len(g)) if len(g) else float("nan")
        rows.append([scope, side, len(g), len(olc), _fmt(sansur), _fmt(med_asim, 3),
                     _fmt(med_bt, 1), _fmt(sig), guven(len(olc))])
        sonuc[f"{scope}/{side}"] = sig
    bt_t = d.assign(k=d["bt_kova"]).groupby(["scope", "k"], observed=True).size().unstack(fill_value=0)
    internal_sig = sonuc.get("INTERNAL/HIGH"), sonuc.get("INTERNAL/LOW")
    karar = []
    for side in ("HIGH", "LOW"):
        s = sonuc.get(f"INTERNAL/{side}")
        e = sonuc.get(f"EXTERNAL/{side}")
        if s is not None and not (isinstance(s, float) and math.isnan(s)):
            karar.append(f"{side}: INTERNAL sığ kırılım {_fmt(s)}% "
                         f"→ " + ("kural" if s >= 40 else ("uyarı" if s >= 25 else "kural-red")))
    return {
        "id": "S20", "baslik": "İç yapı kırılımı sığ mı (kirilim_atr < 0.25)",
        "veri": f"broken=True: {len(d)}",
        "tablo": md_table(["scope", "side", "n", "olçülen", "sansür%", "medyan aşım ATR",
                           "medyan bars_to_break", "sığ% (<0.25)", "güven"], rows)
        + "\n\nbars_to_break kovası dağılımı:\n" + bt_t.to_markdown(),
        "ana": " | ".join(karar),
        "karar": " | ".join(karar),
        "notlar": ["kirilim_bar pencere-içi 1-tabanlı konum; mutlak bar broken_bar (§8-E15)."],
    }


def s21(y: Yukleyici) -> dict[str, Any]:
    sw = _scope_sec(y.al("swing")["swing"])
    d = sw[
        sw["engelledi_025"].notna()
        & (sw["vp_data_ready"].fillna(False) == True)  # noqa: E712
        & sw["vp_volume_result_efficiency"].notna()
    ].copy()
    rows = []
    sonuc = {}
    for scope, g in d.groupby("scope", observed=True):
        q = g["vp_volume_result_efficiency"].quantile([0.25, 0.5, 0.75])
        g["cq"] = pd.cut(g["vp_volume_result_efficiency"],
                         [-1e18, q.iloc[0], q.iloc[1], q.iloc[2], 1e18],
                         labels=["Q1", "Q2", "Q3", "Q4"])
        pvt = g.groupby("cq", observed=True)["engelledi_025"].apply(
            lambda s: 100.0 * (s == True).mean())  # noqa: E712
        n_pvt = g.groupby("cq", observed=True).size()
        for lab in ("Q1", "Q2", "Q3", "Q4"):
            if lab in pvt.index:
                rows.append([scope, lab, int(n_pvt[lab]), _fmt(pvt[lab]), guven(int(n_pvt[lab]))])
        if "Q4" in pvt.index and "Q1" in pvt.index:
            sonuc[scope] = (float(pvt["Q4"]) - float(pvt["Q1"]),
                            int(n_pvt["Q4"]), int(n_pvt["Q1"]))
    return {
        "id": "S21", "baslik": "Rol atama hacmi → koruma (verimlilik çeyrekleri)",
        "veri": f"vp_ready + engelledi dolu: {len(d)}",
        "tablo": md_table(["scope", "çeyrek", "n", "engelledi=True%", "güven"], rows),
        "ana": "; ".join(f"{k}: Q4−Q1 {_pp(v[0])}pp" for k, v in sonuc.items()),
        "karar": "; ".join(
            f"{k}:{karar_ver(v[0], v[1], v[2], 0, 0).split(' (')[0]}" for k, v in sonuc.items()),
        "notlar": ["Çeyrekler scope içi içsel sıralama (run içi)."],
    }


# ---------------------------------------------------------------------------
# §3 — MS OLAY (S22–S26)
# ---------------------------------------------------------------------------

def _event_sec(event: pd.DataFrame) -> pd.DataFrame:
    e = event.copy()
    e["event_type"] = e["event_type"].astype(str)
    e["scope"] = e["scope"].astype(str).str.upper()
    return e


def s22(y: Yukleyici) -> dict[str, Any]:
    ev = _event_sec(y.al("event")["event"])
    d = ev[ev["event_type"].isin(["EVENT_BOS", "EVENT_CHOCH"])
           & ev["bos_maturity"].notna()
           & ev["devamlilik_sinifi"].notna() & (ev["devamlilik_sinifi"] != OLCULEMEDI)]
    rows = []
    matrisler = []
    sonuc = {}
    for (scope, tip), g in d.groupby(["scope", "event_type"], observed=True):
        pvt = g.groupby("bos_maturity", observed=True).apply(
            lambda x: pd.Series({
                "n": len(x),
                "CALISTI%": 100.0 * (x["devamlilik_sinifi"] == CALISTI).mean(),
                "sansur%": 100.0 * (x["devamlilik_sinifi"] == OLCULEMEDI).mean(),
            }), include_groups=False)
        matrisler.append(f"**{scope} · {tip}**\n\n" + pvt.round(1).to_markdown())
        idx = pvt.index
        if "INITIAL_STRUCTURE" in idx and "CONTINUATION" in idx:
            a = pvt.loc["INITIAL_STRUCTURE"]; b = pvt.loc["CONTINUATION"]
            fark = float(a["CALISTI%"]) - float(b["CALISTI%"])
            sonuc[f"{scope}/{tip}"] = (fark, int(a["n"]), int(b["n"]))
            rows.append([scope, tip, int(a["n"]), _fmt(a["CALISTI%"]), int(b["n"]),
                         _fmt(b["CALISTI%"]), _pp(fark),
                         karar_ver(fark, int(a["n"]), int(b["n"]), float(a["sansur%"]),
                                   float(b["sansur%"]))])
    # tam matris: scope × maturity × devamlilik (BOS havuz)
    bos = d[d["event_type"] == "EVENT_BOS"]
    tam = (bos.groupby(["scope", "bos_maturity", "devamlilik_sinifi"], observed=True)
           .size().unstack(fill_value=0))
    return {
        "id": "S22", "baslik": "Olgunluk → devamlılık (BOS/CHOCH)",
        "veri": f"olgunluk+devamlılık dolu olay: {len(d)} (toplam {len(ev)})",
        "tablo": md_table(["scope", "tip", "n INITIAL", "CALISTI% INITIAL", "n CONT",
                           "CALISTI% CONT", "fark pp", "karar"], rows)
        + "\n\nBOS dağılımı:\n" + tam.to_markdown(),
        "ana": "; ".join(f"{k}: {_pp(v[0])}pp" for k, v in sonuc.items()),
        "karar": "; ".join(
            f"{k}:{karar_ver(v[0], v[1], v[2], 0, 0).split(' (')[0]}" for k, v in sonuc.items()),
        "notlar": ["bos_maturity: NOT_APPLICABLE/INITIAL_STRUCTURE/TRANSITION_CONFIRMATION/CONTINUATION."],
    }


def s23(y: Yukleyici) -> dict[str, Any]:
    ev = _event_sec(y.al("event")["event"])
    d = ev[ev["onay_gecikmesi_bar"].notna()].copy()
    d["gec_kova"] = _kovala(d["onay_gecikmesi_bar"], [
        (-1e9, 2, "0-1"), (2, 4, "2-3"), (4, 1e9, ">=4")])
    d = d[d["gec_kova"] != "yok"]
    rows = []
    sonuc = {}
    for (scope, tip), g in d.groupby(["scope", "event_type"], observed=True):
        med = {}
        nes = {}
        for kova, gg in g.groupby("gec_kova", observed=True):
            med[kova] = _medyan(gg["devam_h12"])
            nes[kova] = len(gg)
        cal = {}
        for kova, gg in g.groupby("gec_kova", observed=True):
            olc = gg[gg["devamlilik_sinifi"] != OLCULEMEDI]
            cal[kova] = 100.0 * (olc["devamlilik_sinifi"] == CALISTI).mean() if len(olc) else float("nan")
        if "0-1" in med and ">=4" in med:
            dm = med[">=4"] - med["0-1"]
            dc = (cal.get(">=4", float("nan")) - cal.get("0-1", float("nan")))
            rows.append([scope, tip, nes.get("0-1", 0), _fmt(med.get("0-1"), 2),
                         nes.get(">=4", 0), _fmt(med.get(">=4"), 2), _fmt(dm, 2),
                         _fmt(dc), _pp(dc) if pd.notna(dc) else "-"])
            sonuc[f"{scope}/{tip}"] = (dm, dc, nes.get("0-1", 0), nes.get(">=4", 0))
    esik_md = []
    for k, (dm, dc, n1, n2) in sonuc.items():
        esik_ast = (abs(dm) >= 0.25 or (pd.notna(dc) and abs(dc) >= 12)) and n1 >= 30 and n2 >= 30
        if not esik_ast:
            esik_md.append(f"{k}: Δmedyan={_fmt(dm,2)} ATR, ΔCALISTI={_pp(dc)}pp → kart dipnotu")
            continue
        ters = (dm > 0) and (pd.isna(dc) or dc > 0)  # geç onaylılar daha iyi → hipotez ters
        esik_md.append(
            f"{k}: Δmedyan={_fmt(dm,2)} ATR, ΔCALISTI={_pp(dc)}pp → "
            + ("RED: hipotez ters (geç onaylılar daha iyi; gecikme cezası kurulmaz)"
               if ters else "uyarı + öncelik düşürmesi (geç onay zararlı)"))
    return {
        "id": "S23", "baslik": "Onay gecikmesi → devamlılık",
        "veri": f"onay_gecikmesi dolu: {len(d)}",
        "tablo": md_table(["scope", "tip", "n 0-1", "medyan devam_h12", "n >=4",
                           "medyan devam_h12", "Δ medyan", "CALISTI% fark", "pp"], rows),
        "ana": " | ".join(esik_md),
        "karar": " | ".join(esik_md),
        "notlar": ["event_bar yoksa gecikme None → kapsam dışı (§8-E13b)."],
    }


def s24(y: Yukleyici) -> dict[str, Any]:
    ev = _event_sec(y.al("event")["event"])
    d = ev[ev["ters_h12"].notna()]
    rows = []
    sonuc = {}
    for (scope, tip), g in d.groupby(["scope", "event_type"], observed=True):
        n = len(g)
        pay = 100.0 * float((pd.to_numeric(g["ters_h12"], errors="coerce") >= 1.0).sum()) / n
        med = _medyan(g["ters_h12"])
        rows.append([scope, tip, n, _fmt(med, 2), _fmt(pay), guven(n)])
        sonuc[f"{scope}/{tip}"] = (med, pay, n)
    t = pd.DataFrame(rows, columns=["scope", "tip", "n", "medyan ters_h12", "ters>=1.0%", "güven"])
    esik = []
    for scope in t["scope"].dropna().unique():
        bos = t[(t["scope"] == scope) & (t["tip"] == "EVENT_BOS")]
        for tip in ("EVENT_SWEEP", "EVENT_FALSE_BREAK", "EVENT_CHOCH"):
            alt = t[(t["scope"] == scope) & (t["tip"] == tip)]
            if len(bos) and len(alt):
                b, a = bos.iloc[0], alt.iloc[0]
                fark = float(a["ters>=1.0%"]) - float(b["ters>=1.0%"])
                if int(a["n"]) >= 15 and int(b["n"]) >= 15:
                    esik.append(f"{scope} {tip} vs BOS: {_pp(fark)}pp → " +
                                ("kontra kart açılır" if fark >= 12 else
                                 ("yalnız uyarı" if fark >= 5 else "kontra reddedilir")))
    return {
        "id": "S24", "baslik": "Sahte kırılım/süpürme kontra sinyali",
        "veri": f"ters_h12 dolu: {len(d)}",
        "tablo": md_table(["scope", "tip", "n", "medyan ters_h12", "ters>=1.0%", "güven"], rows),
        "ana": " | ".join(esik) or "yeterli kesişim yok (C4)",
        "karar": " | ".join(esik) or "kapsam dışı (n<15)",
        "notlar": ["ters_h12: olay yönünün TERSİNE 12 bar maksimum (negatif korunur)."],
    }


def s25(y: Yukleyici) -> dict[str, Any]:
    ev = _event_sec(y.al("event")["event"])
    rows = []
    for (scope, tip), g in ev.groupby(["scope", "event_type"], observed=True):
        n = len(g)
        for rel in ("CURRENT", "SUPERSEDED", "HISTORICAL"):
            pay = 100.0 * float((g["relevance"] == rel).sum()) / n
            rows.append([scope, tip, rel, _fmt(pay), n if rel == "CURRENT" else ""])
    sup = ev[ev["relevance"] == "SUPERSEDED"]
    med_yas_havuz = _medyan(ev["age_bars"])  # tüm olaylar (havuz); sup ile karıştırılmamalı
    bos_sup = []
    for scope, g in ev[ev["event_type"] == "EVENT_BOS"].groupby("scope", observed=True):
        pay = 100.0 * float((g["relevance"] == "SUPERSEDED").sum()) / len(g)
        kar = ("bastırma kuralı" if pay >= 20 else ("uyarı" if pay >= 10 else "kural gereksiz"))
        bos_sup.append(f"{scope} BOS: SUPERSEDED {pay:.1f}% → {kar}")
    return {
        "id": "S25", "baslik": "Olay ezilmesi (relevance)",
        "veri": f"tüm olaylar: {len(ev)}; SUPERSEDED: {len(sup)}",
        "tablo": md_table(["scope", "tip", "relevance", "pay%", "not"], rows),
        "ana": f"SUPERSEDED olayların seri-sonu yaşı medyan={_medyan(sup['age_bars']) if len(sup) else '-'} "
               f"bar (tüm olaylar havuz medyanı {med_yas_havuz:.0f})",
        "karar": " | ".join(bos_sup),
        "notlar": ["age_bars = event_bar'dan serinin sonuna süre (ledger'da EZİLME ANINDA donmaz); "
                   "'ezilme süresi' olarak okunmamalı — ezilme hızını relevance payları verir (BOS %93–96)."],
    }


def s26(y: Yukleyici) -> dict[str, Any]:
    ev = _event_sec(y.al("event")["event"])
    d = ev[(ev["event_type"] == "EVENT_BOS") & ev["devam_pay_1"].notna()].copy()
    d["pay_kova"] = _kovala(pd.to_numeric(d["devam_pay_1"], errors="coerce"), [
        (-1e9, 0.3, "<0.3"), (0.3, 0.8, "0.3-0.8"), (0.8, 1.01, ">=0.8")])
    d = d[d["pay_kova"] != "yok"]
    rows = []
    sonuc = {}
    for scope, g in d.groupby("scope", observed=True):
        pvt = {}
        for kova, gg in g.groupby("pay_kova", observed=True):
            olc = gg[gg["devamlilik_sinifi"] != OLCULEMEDI]
            pvt[kova] = (100.0 * (olc["devamlilik_sinifi"] == CALISTI).mean(), len(olc))
            rows.append([scope, kova, len(gg), _fmt(pvt[kova][0]), pvt[kova][1],
                         guven(pvt[kova][1])])
        if ">=0.8" in pvt and "<0.3" in pvt:
            sonuc[scope] = (pvt[">=0.8"][0] - pvt["<0.3"][0],
                            pvt[">=0.8"][1], pvt["<0.3"][1])
    ani = 100.0 * (pd.to_numeric(d["devam_pay_1"], errors="coerce") >= 0.8).mean()
    med_tepe = _medyan(d["devam_tepe_bar"])
    med_pay3 = _medyan(d["devam_pay_3"])
    return {
        "id": "S26", "baslik": "Kırılım hızı (ani kırılım, BOS)",
        "veri": f"pay_1 dolu BOS: {len(d)}",
        "tablo": md_table(["scope", "pay_1 kovası", "n", "CALISTI%", "n_olçülen", "güven"], rows),
        "ana": f"pay_1>=0.8 payı={_fmt(ani)}%; medyan tepe bar={_medyan(d['devam_tepe_bar']):.0f}; "
               f"hareketin ort. %{_fmt(100*med_pay3,0)}'i ilk 3 barda (medyan pay_3)",
        "karar": "; ".join(f"{k}: fark {_pp(v[0])}pp → " +
                           karar_ver(v[0], v[1], v[2], 0, 0).split(" (")[0]
                           for k, v in sonuc.items()),
        "notlar": ["Mekanizma (kayit.py): h12 = bar+1'den itibaren 12 bar; devam_pay_1 ≥0.8 ise "
                   "tepe zaten 1. bara kilitlenmiş → CALISTI yalnızca o ilk barın ≥1.0 ATR olmasıyla "
                   "gelir. Fark büyük ölçüde TANIMSAL; kart metninde yön 'ilk barda tükenmiş/uzanım "
                   "sınırlı' dilinde yazılır, 'devam etmez' genellemesi kurulmaz."],
    }


# ---------------------------------------------------------------------------
# §4 — FORMASYON (S27–S30)
# ---------------------------------------------------------------------------

def s27(y: Yukleyici) -> dict[str, Any]:
    frm = y.al("frm")["frm"]
    d = frm.copy()
    d["gecis_kova"] = _kovala(d["frm_faz_gecis_sayisi"], [
        (-1e9, 3, "<=2"), (3, 6, "3-5"), (6, 1e9, ">=6")])
    d = d[d["gecis_kova"] != "yok"]
    rows = []
    for (tf, kova), g in d.groupby(["timeframe", "gecis_kova"], observed=True):
        n = len(g)
        tam = 100.0 * float((g["terminal_state"] == "FORMASYON_TAMAMLANDI").sum()) / n
        acik = 100.0 * float((g["acik"] == True).sum()) / n  # noqa: E712
        rows.append([tf, kova, n, _fmt(tam), _fmt(acik), guven(n)])

    def _tam_orani(g: pd.DataFrame) -> float:
        return 100.0 * float((g["terminal_state"] == "FORMASYON_TAMAMLANDI").sum()) / max(len(g), 1)

    # İSTENEN kontrast (soru seti ekseninde): <=2 taban vs >=6
    sonuc: dict[str, tuple[float, int, int]] = {}
    for tf, g in d.groupby("timeframe", observed=True):
        a = g[g["gecis_kova"] == "<=2"]
        b = g[g["gecis_kova"] == ">=6"]
        if len(a) and len(b):
            sonuc[tf] = (_tam_orani(a) - _tam_orani(b), len(a), len(b))
    # GERÇEK çırpınma kontrastı: 3-5 vs >=6 (kapalı satırlar; açık sansürü hariç)
    dk = d[d["acik"] == False]  # noqa: E712
    gercek: dict[str, tuple[float, int, int]] = {}
    for tf, g in dk.groupby("timeframe", observed=True):
        a = g[g["gecis_kova"] == "3-5"]
        b = g[g["gecis_kova"] == ">=6"]
        if len(a) >= 30 and len(b) >= 30:
            gercek[tf] = (_tam_orani(a) - _tam_orani(b), len(a), len(b))
    a_h, b_h = dk[dk["gecis_kova"] == "3-5"], dk[dk["gecis_kova"] == ">=6"]
    fark_h = _tam_orani(a_h) - _tam_orani(b_h) if len(a_h) and len(b_h) else float("nan")
    # <=2 kovası yapısal kontrolü
    g2 = d[d["gecis_kova"] == "<=2"]
    tam2 = _tam_orani(g2)
    pay2 = (100.0 * float((g2["terminal_state"] == "BASARISIZ_KIRILIM").sum()) / len(g2)
            if len(g2) else float("nan"))

    tip_rows = []
    for (tip, kova), g in d.groupby(["pattern_type", "gecis_kova"], observed=True):
        if len(g) >= 30:
            tam = 100.0 * float((g["terminal_state"] == "FORMASYON_TAMAMLANDI").sum()) / len(g)
            tip_rows.append([tip, kova, len(g), _fmt(tam)])
    dagilim = d.groupby(["gecis_kova", "terminal_state"], observed=True).size().unstack(fill_value=0)
    # karar: seti eşiği (≥12 yayınlama / 5–12 uyarı / <5 RED) GERÇEK eksende uygulanır
    if pd.isna(fark_h):
        kv = "KARAR YOK (3-5/>=6 yeterli n yok)"
    elif abs(fark_h) < 5:
        kv = ("RED (yapısal): '6+ yayınlanmaz' kuralı KURULMAZ — çırpınma kontrastı 3-5 vs ≥6 = "
              f"{_pp(fark_h)}pp (<5); ≤2 tabanı TAMAMLANDI üretemez (TAMAMLANDI %{_fmt(tam2)}, "
              f"BASARISIZ_KIRILIM %{_fmt(pay2)})")
    elif abs(fark_h) < 12:
        kv = (f"uyarı düzeyi: 3-5 vs ≥6 = {_pp(fark_h)}pp (5–12) — yalnız karne notu, filtre yok"
              + (f"; istenen ≤2 tabanlı kontrast {_pp(list(sonuc.values())[0][0])}pp yapısal şişirilmiş"
                 if sonuc else ""))
    else:
        kv = (f"YAZILIR: 3-5 vs ≥6 = {_pp(fark_h)}pp (≥12); ≤2 tabanı ayrıca yapısal not "
              f"(TAMAMLANDI %{_fmt(tam2)})")
    return {
        "id": "S27", "baslik": "Faz çırpınması → sonuç",
        "veri": f"frm: {len(frm)} (kova dışı: {len(frm) - len(d)}); bu bölüm {len(d)}; "
                f"kapalı (sansürsüz) {len(dk)}",
        "tablo": md_table(["tf", "geçiş", "n", "TAMAMLANDI%", "açık%", "güven"], rows)
        + "\n\nkova × terminal_state:\n" + dagilim.to_markdown()
        + "\n\n(n>=30 tip hücreleri)\n" + md_table(["pattern_type", "geçiş", "n", "TAMAMLANDI%"],
                                                   tip_rows),
        "ana": ("İSTENEN (≤2 vs ≥6, tüm satır): "
                + "; ".join(f"{tf}: {_pp(v[0])}pp (n={v[1]}/{v[2]})" for tf, v in sonuc.items())
                + f" | GERÇEK çırpınma (3-5 vs ≥6, kapalı): havuz {_pp(fark_h)}pp; "
                + "; ".join(f"{tf} {_pp(v[0])}pp" for tf, v in gercek.items())
                + f" | ≤2 kovası: TAMAMLANDI %{_fmt(tam2)} (n={len(g2)}), "
                f"BASARISIZ_KIRILIM %{_fmt(pay2)}"),
        "karar": kv,
        "notlar": [
            "YAPISAL: TAMAMLANDI yoluna ulaşmak için faz geçişi zorunludur — ≤2 kovası "
            "erken-kapanış kovasıdır (BASARISIZ_KIRILIM/GEÇERSIZ ağırlıklı), çırpınma ölçmez. "
            "Soru setindeki ≤2 TABANI bu yüzden yanıltıcı; eksen 3-5 vs ≥6 olmalıdır.",
            "C4: tip×TF hücreleri n<30 ise yalnız birleşik n raporlanır.",
        ],
    }


def s28(y: Yukleyici) -> dict[str, Any]:
    frm, ol, meta = y.al("frm", "frm_olay", "meta")["frm"], y.al("frm_olay")["frm_olay"], y.al("meta")["meta"]
    rows = []
    for (tip, tf), g in frm.groupby(["pattern_type", "timeframe"], observed=True):
        n = len(g)
        acik = 100.0 * float((g["acik"] == True).sum()) / n
        rows.append([tip, tf, n, _fmt(acik),
                     _fmt(_medyan(g[g["acik"] == True]["omur_bar"]), 0) if (g["acik"] == True).any() else "-",  # noqa: E712
                     _fmt(_medyan(g[g["acik"] == False]["omur_bar"]), 0) if (g["acik"] == False).any() else "-",  # noqa: E712
                     guven(n)])
    # son olayı terminal olmayan stable_id payı
    ol2 = ol.sort_values(["symbol", "timeframe", "stable_id", "bar"])
    son = ol2.groupby(["symbol", "timeframe", "stable_id"], observed=True).tail(1)
    yarim = 100.0 * float((~son["state"].isin(TERMINAL_DURUMLAR)).sum()) / max(len(son), 1)
    acik_pay = 100.0 * float((frm["acik"] == True).sum()) / len(frm)  # noqa: E712
    meta_frm = meta["formasyon_sayisi"].sum() if "formasyon_sayisi" in meta else float("nan")
    tutarli = abs(float(meta_frm) - len(frm)) < 1e-6
    en_kotu = max((r[3] for r in rows if isinstance(r[3], str) and r[3] != "-" and r[2] >= 30),
                  key=lambda x: float(x), default="0")
    return {
        "id": "S28", "baslik": "Açık örneklem payı (acik + yarım segment)",
        "veri": f"frm={len(frm)}, frm_olay={len(ol)}, stable_id (son olay satırı)={len(son)}",
        "tablo": md_table(["pattern_type", "tf", "n", "açık%", "medyan ömür (açık)",
                           "medyan ömür (kapalı)", "güven"], rows),
        "ana": f"havuz açık %{_fmt(acik_pay)}; son olayı terminal olmayan stable_id %{_fmt(yarim)}; "
               f"meta.formasyon_sayisi={meta_frm:.0f} ↔ frm={len(frm)} tutarlı={'EVET' if tutarli else 'HAYIR'}",
        "karar": (f"en yüksek hücre açık %{en_kotu} → " +
                  ("o hücre soruları KISMI" if float(en_kotu) >= 30 else "payda düzeltmesi yeterli")),
        "notlar": ["Terminal set (§8-E11): " + ", ".join(TERMINAL_DURUMLAR)],
    }


def s29(y: Yukleyici) -> dict[str, Any]:
    frm = y.al("frm")["frm"]
    d = frm[frm["frm_teyit_sonrasi_mfe_atr"].notna() & frm["frm_teyit_sonrasi_mae_atr"].notna()].copy()
    d["ezildi"] = d["frm_pivot_ezilme_var"].fillna(False) == True  # noqa: E712
    rows = []
    sonuc = {}
    for (ez, den), g in d.groupby(["ezildi", "frm_kirilim_deneme_var"], observed=True):
        mfe = _medyan(g["frm_teyit_sonrasi_mfe_atr"])
        mae = _medyan(g["frm_teyit_sonrasi_mae_atr"])
        oran = (mae / mfe * 100) if (mfe and mfe > 0) else float("nan")
        rows.append([str(ez), str(den), len(g), _fmt(mfe, 2), _fmt(mae, 2), _fmt(oran), guven(len(g))])
    # ana: ezilme T vs F (havuz, deneme bağımsız)
    a = d[d["ezildi"]]; b = d[~d["ezildi"]]
    mfe_a, mfe_b = _medyan(a["frm_teyit_sonrasi_mfe_atr"]), _medyan(b["frm_teyit_sonrasi_mfe_atr"])
    oran_a = (_medyan(a["frm_teyit_sonrasi_mae_atr"]) / mfe_a * 100) if mfe_a else float("nan")
    oran_b = (_medyan(b["frm_teyit_sonrasi_mae_atr"]) / mfe_b * 100) if mfe_b else float("nan")
    fark_mfe = mfe_a - mfe_b
    fark_oran = oran_a - oran_b
    kar = ("uyarı + öncelik düşürmesi" if ((fark_mfe <= -0.25 or fark_oran >= 15)
                                           and len(a) >= 30 and len(b) >= 30) else "yalnız gözlem")
    # tip hücreleri (n>=30)
    tip_rows = []
    for tip, g in d.groupby("pattern_type", observed=True):
        if len(g) < 30:
            continue
        ga, gb = g[g["ezildi"]], g[~g["ezildi"]]
        if len(ga) >= 15 and len(gb) >= 15:
            tip_rows.append([tip, len(ga), _fmt(_medyan(ga["frm_teyit_sonrasi_mfe_atr"]), 2),
                             len(gb), _fmt(_medyan(gb["frm_teyit_sonrasi_mfe_atr"]), 2)])
    return {
        "id": "S29", "baslik": "Pivot ezilmesi → teyit sonrası getiri",
        "veri": f"mfe+mae dolu (teyitli): {len(d)}; ezilen: {int(a['ezildi'].sum()) if 'ezildi' in a else len(a)}",
        "tablo": md_table(["ezildi", "deneme_var", "n", "medyan MFE", "medyan MAE",
                           "MAE/MFE%", "güven"], rows)
        + "\n\ntip×ezilme (MFE):\n" + md_table(["pattern_type", "n ezilen", "MFE",
                                                 "n ezilmeyen", "MFE"], tip_rows),
        "ana": f"ezilen MFE={_fmt(mfe_a,2)} vs değil={_fmt(mfe_b,2)} (Δ={_fmt(fark_mfe,2)} ATR); "
               f"MAE/MFE {_fmt(oran_a)}% vs {_fmt(oran_b)}% (Δ={_fmt(fark_oran)}pp)",
        "karar": kar,
        "notlar": [],
    }


def s30(y: Yukleyici) -> dict[str, Any]:
    frm = y.al("frm")["frm"]
    d = frm[frm["frm_teyit_sonrasi_mfe_atr"].notna() & frm["frm_teyit_sonrasi_mfe_uzun_atr"].notna()].copy()
    d = d[pd.to_numeric(d["frm_teyit_sonrasi_mfe_atr"], errors="coerce") > 0]
    d["oran"] = (pd.to_numeric(d["frm_teyit_sonrasi_mfe_uzun_atr"], errors="coerce")
                 / pd.to_numeric(d["frm_teyit_sonrasi_mfe_atr"], errors="coerce"))
    d["sonra"] = (pd.to_numeric(d["frm_teyit_sonrasi_mfe_uzun_atr"], errors="coerce")
                  > pd.to_numeric(d["frm_teyit_sonrasi_mfe_atr"], errors="coerce"))
    rows = []
    sonuc = {}
    for tip, g in d.groupby("pattern_type", observed=True):
        n = len(g)
        med = _medyan(g["oran"])
        p90 = float(g["oran"].quantile(0.9))
        sonra = 100.0 * float(g["sonra"].mean())
        rows.append([tip, n, _fmt(med, 2), _fmt(p90, 2),
                     _fmt(_medyan(g["frm_teyit_sonrasi_mfe_atr"]), 2),
                     _fmt(_medyan(g["frm_teyit_sonrasi_mfe_uzun_atr"]), 2),
                     _fmt(sonra), guven(n)])
        if n >= 30:
            sonuc[tip] = med
    med_h = _medyan(d["oran"])
    tavsiye = ("kart hedefi uzun pencereye" if med_h >= 1.5
               else ("12 bar yeterli" if med_h < 1.2 else "arada → hücre bazında"))
    return {
        "id": "S30", "baslik": "12 bar yeterli mi (MFE_uzun / MFE)",
        "veri": f"mfe + mfe_uzun dolu, mfe>0: {len(d)}",
        "tablo": md_table(["pattern_type", "n", "medyan oran", "p90", "medyan MFE(12)",
                           "medyan MFE(40)", "tepe sonra% (mfe_uzun>mfe)", "güven"], rows),
        "ana": f"havuz medyan oran={_fmt(med_h,2)}; tepe sonrada oluşan pay %{_fmt(100*d['sonra'].mean())}",
        "karar": tavsiye + " (eşik: >=1.5 uzun, <1.2 kısa)",
        "notlar": ["break_confirmation_strength destek medyanıdır (§8-E12); gruplama değişkeni değil.",
                   "Eşitliğin kaynağı: formasyon.py'de `sonra` etkin ömürle (anti-dairesellik "
                   "kesiği, _TERMINAL) sınırlıdır; teyitten sonra terminal barına kadar "
                   "yalnızca birkaç bar kalır, 40-bar pencere ancak uzun açık dönemlerde "
                   "açılır — bu yüzden oran ~1.0."],
    }


# ---------------------------------------------------------------------------
# §5 — KESİT (S31–S32)
# ---------------------------------------------------------------------------

def s31(y: Yukleyici) -> dict[str, Any]:
    dok, ev = y.al("dokunus", "event")["dokunus"], y.al("event")["event"]
    sonuclar = []
    # ZONE bloğu: sembol bazlı CALISTI
    d = _tepki_mi(dok)
    d = d.assign(c=(d["yon_tepki_sinifi"] == CALISTI).astype(float))
    for (tf, fam), g in d.groupby(["timeframe", "family"], observed=True):
        sem = g.groupby("symbol", observed=True)["c"].agg(["mean", "size"])
        sem = sem[sem["size"] >= 30]
        if len(sem) < 10:
            sonuclar.append([tf, fam, len(sem), "-", "-", "-", "n<10 sembol (KISMI)"])
            continue
        p10, p50, p90 = (sem["mean"].quantile([0.1, 0.5, 0.9]) * 100)
        sonuclar.append([tf, fam, len(sem), _fmt(p10), _fmt(p50), _fmt(p90), _pp(p90 - p10)])
    # MS bloğu: scope bazlı
    e = ev[ev["devamlilik_sinifi"].notna() & (ev["devamlilik_sinifi"] != OLCULEMEDI)].copy()
    e = e.assign(c=(e["devamlilik_sinifi"] == CALISTI).astype(float))
    ms_rows = []
    for scope, g in e.groupby("scope", observed=True):
        sem = g.groupby("symbol", observed=True)["c"].agg(["mean", "size"])
        sem = sem[sem["size"] >= 30]
        if len(sem) < 10:
            ms_rows.append([scope, len(sem), "-", "-", "-", "n<10"])
            continue
        p10, p50, p90 = (sem["mean"].quantile([0.1, 0.5, 0.9]) * 100)
        ms_rows.append([scope, len(sem), _fmt(p10), _fmt(p50), _fmt(p90), _pp(p90 - p10)])
    # uç semboller (1h OB)
    uc = ""
    g = d[(d["timeframe"].astype(str) == "1h") & (d["family"].astype(str) == "OB")]
    sem = g.groupby("symbol", observed=True)["c"].agg(["mean", "size"])
    sem = sem[sem["size"] >= 30].sort_values("mean")
    if len(sem):
        en = sem.head(5).reset_index()
        kotu = sem.tail(5).reset_index()
        uc = ("en düşük 5: " + ", ".join(f"{r.symbol}({100 * r.mean:.0f}%)"
                                         for r in en.itertuples())
              + " · en yüksek 5: " + ", ".join(f"{r.symbol}({100 * r.mean:.0f}%)"
                                              for r in kotu.itertuples()))
    genislik = max((float(r[6]) for r in sonuclar
                    if isinstance(r[6], str) and r[6].startswith(("+", "-"))), default=0.0)
    return {
        "id": "S31", "baslik": "Semboller arası yayılım (p10–p90)",
        "veri": f"zone ölçülebilir sembol-grupları (n>=30 semboller); MS: {len(ms_rows)} scope",
        "tablo": md_table(["tf", "family", "n sembol", "p10", "medyan", "p90", "p90−p10"],
                          sonuclar)
        + "\n\nMS:\n" + md_table(["scope", "n sembol", "p10", "medyan", "p90", "p90−p10"], ms_rows),
        "ana": f"en geniş p90−p10={_fmt(genislik)}pp; {uc}",
        "karar": ("karneye sembol aralığı + uç sembol süzgeci" if genislik >= 20
                  else ("global oran + aralık notu" if genislik >= 10 else "global oran yeterli")),
        "notlar": ["n<30 semboller dışlanmadı, yalnızca güven etiketi alır (C4)."],
    }


def s32(y: Yukleyici) -> dict[str, Any]:
    from research import arsiv

    dok = y.al("dokunus")["dokunus"]
    dok = dok[dok["dokunus_bitis_index"].notna()].copy()
    dok["dokunus_bitis_index"] = dok["dokunus_bitis_index"].astype(int)

    # (symbol,tf) başına K5 bayrak dizileri
    bayrak_dizi: dict[tuple[str, str], dict[str, list[bool]]] = {}
    bar_sayisi: dict[tuple[str, str], int] = {}
    split_pay: dict[str, list[int]] = {}
    sifir_saat: dict[str, dict[int, int]] = {}
    for sem in sorted(dok["symbol"].astype(str).unique()):
        for tf in ("1h", "2h", "4h", "1d"):
            alt = dok[(dok["symbol"].astype(str) == sem) & (dok["timeframe"].astype(str) == tf)]
            if not len(alt):
                continue
            try:
                frame = arsiv.tf_frame(sem, tf)
            except Exception:  # noqa: BLE001 — soru-cevap hattı sembol izolasyonu
                continue
            n = len(frame)
            split = [False] * n
            sifir = [False] * n
            nan = [False] * n
            onceki = None
            saatler = frame.index.tz_convert("Europe/Istanbul").hour if isinstance(
                frame.index, pd.DatetimeIndex) and frame.index.tz is not None else None
            for i, row in enumerate(frame.itertuples(index=False)):
                acilis = float(row.open) if pd.notna(row.open) else float("nan")
                if (onceki is not None and onceki > 0 and math.isfinite(acilis)
                        and abs(acilis - onceki) / onceki > 0.10):
                    split[i] = True
                sifir[i] = bool(pd.notna(row.volume) and float(row.volume) == 0.0)
                if sifir[i] and saatler is not None:
                    h = int(saatler[i])
                    dd = sifir_saat.setdefault(tf, {})
                    dd[h] = dd.get(h, 0) + 1
                nan[i] = any(pd.isna(getattr(row, k)) for k in ("open", "high", "low", "close"))
                if pd.notna(row.close) and math.isfinite(float(row.close)):
                    onceki = float(row.close)
            bayrak_dizi[(sem, tf)] = {"split": split, "sifir": sifir, "nan": nan}
            bar_sayisi[(sem, tf)] = n
            sp = split_pay.setdefault(tf, [0, 0])
            sp[0] += sum(split); sp[1] += n
            arsiv._OBELLEK.clear()
    rows = []
    sem_split: dict[str, list[int]] = {}
    kirli_toplam = 0
    for (sem, tf), g in dok.groupby(
            [dok["symbol"].astype(str), dok["timeframe"].astype(str)], observed=True):
        dizi = bayrak_dizi.get((sem, tf))
        if dizi is None:
            continue
        n = bar_sayisi[(sem, tf)]
        kirli = {"split": 0, "sifir": 0, "nan": 0, "herhangi": 0}
        for _, row in g.iterrows():
            bas = int(row["dokunus_bitis_index"]) + 1
            son = min(bas + 12, n)
            v = {"split": False, "sifir": False, "nan": False}
            for i in range(bas, min(son, n)):
                for k in v:
                    if dizi[k][i]:
                        v[k] = True
            if any(v.values()):
                kirli_toplam += 1
            for k in ("split", "sifir", "nan"):
                if v[k]:
                    kirli[k] += 1
            if v["split"]:
                sp = sem_split.setdefault(sem, [0, 0]); sp[0] += 1
            rows.append({"symbol": sem, "timeframe": tf, "family": str(row["family"]),
                         "n": 1, "kirli_split": int(v["split"]), "kirli_sifir": int(v["sifir"]),
                         "kirli_nan": int(v["nan"]),
                         "kirli": int(any(v.values()))})
    df = pd.DataFrame(rows)
    t = df.groupby(["timeframe", "family"], observed=True).agg(
        n=("n", "size"), split_pct=("kirli_split", lambda s: 100.0 * s.mean()),
        sifir_pct=("kirli_sifir", lambda s: 100.0 * s.mean()),
        nan_pct=("kirli_nan", lambda s: 100.0 * s.mean()),
        kirli_pct=("kirli", lambda s: 100.0 * s.mean())).reset_index()
    en_kotu = float(t["kirli_pct"].max())
    karar = ("kural + karne ayrımı" if en_kotu >= 2
             else ("yalnız not" if en_kotu >= 0.5 else "kural gereksiz"))
    split_md = ", ".join(f"{tf}: {100*a/max(b,1):.3f}%" for tf, (a, b) in sorted(split_pay.items()))
    sifir_md = "; ".join(
        f"{tf}: " + ", ".join(f"{h:02d}:00={c}" for h, c in sorted(dd.items(), key=lambda x: -x[1])[:3])
        for tf, dd in sorted(sifir_saat.items()) if dd)
    return {
        "id": "S32", "baslik": "Kirli bar penceresi (K5, 12 bar sonrası)",
        "veri": f"penceresi hesaplanan epizod: {len(df)}; bayraklı epizod: {kirli_toplam} "
               f"({100*kirli_toplam/max(len(df),1):.2f}%)",
        "tablo": t.round(3).to_markdown(index=False)
        + f"\n\nbar-seviyesi split_adayi: {split_md}\n\nsıfır-hacimli bar saatleri: {sifir_md}",
        "ana": f"en kötü hücre kirli pencere %{en_kotu:.2f}",
        "karar": karar,
        "notlar": ["K5 bayrakları JSONL'de yok → arşiv çerçevelerinden üretildi (§8-E13).",
                   "1h sıfır-hacim yığını 09:30 açılış öncesi bar kaynaklıdır (yapısal, "
                   "fiyat boşluğu değil); split payları çok düşük. FAYDA kuralı split için "
                   "geçerli, sıfır-hacim ayrı hücrede raporlanır."],
    }


SORULAR: dict[str, Callable[[Yukleyici], dict[str, Any]]] = {
    "S01": s01, "S02": s02, "S03": s03, "S04": s04, "S05": s05, "S06": s06,
    "S07": s07, "S08": s08, "S09": s09, "S10": s10, "S11": s11, "S12": s12,
    "S13": s13, "S14": s14, "S15": s15, "S16": s16, "S17": s17, "S18": s18,
    "S19": s19, "S20": s20, "S21": s21, "S22": s22, "S23": s23, "S24": s24,
    "S25": s25, "S26": s26, "S27": s27, "S28": s28, "S29": s29, "S30": s30,
    "S31": s31, "S32": s32,
}

# Soru başına bölüm (rapor düzeni)
BOLUMLER = [
    ("§1 ZONE / TEMAS EPİZODU", [f"S{i:02d}" for i in range(1, 16)]),
    ("§2 MS SWING", [f"S{i:02d}" for i in range(16, 22)]),
    ("§3 MS OLAY", [f"S{i:02d}" for i in range(22, 27)]),
    ("§4 FORMASYON", [f"S{i:02d}" for i in range(27, 31)]),
    ("§5 KESİT / VERİ KAPISI", ["S31", "S32"]),
]


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="REPLAY soru seti S01–S32 cevap motoru")
    p.add_argument("--cikti", action="append", default=[],
                   help="JSONL çıktı dizini (tekrarlanabilir)")
    p.add_argument("--rapor", default="docs/arastirma/REPLAY_SORU_YANITLARI_2026-10-29.md")
    p.add_argument("--json", default="", help="makine okunur özet (boşsa <ilk cikti>/soru_seti_sonuclari.json)")
    p.add_argument("--soru", default="", help="virgülle alt küme (örn. S05,S24)")
    args = p.parse_args(argv)

    dizinler = [Path(d) for d in args.cikti]
    if not dizinler:
        varsayilan = [Path("arastirma_cikti_p1"), Path("arastirma_cikti_p2")]
        dizinler = [d for d in varsayilan if d.exists()] or [Path("arastirma_cikti")]
    dizinler = [d for d in dizinler if d.exists()]
    if not dizinler:
        print("HATA: çıktı dizini bulunamadı", file=sys.stderr)
        return 2
    secili = [s.strip().upper() for s in args.soru.split(",") if s.strip()] or list(SORULAR)

    print(f"[soru-cevaplama] dizinler: {', '.join(map(str, dizinler))} · soru: {len(secili)}",
          flush=True)
    y = Yukleyici(dizinler)
    sonuclar: list[dict[str, Any]] = []
    for sid in secili:
        fonk = SORULAR.get(sid)
        if fonk is None:
            print(f"[atla] bilinmeyen soru {sid}", flush=True)
            continue
        try:
            r = fonk(y)
            sonuclar.append(r)
            print(f"[{sid}] tamam — {r['ana'][:160]}", flush=True)
        except Exception as exc:  # noqa: BLE001 — soru izolasyonu
            sonuclar.append({"id": sid, "baslik": "HATA", "veri": "-", "tablo": "-",
                             "ana": f"{type(exc).__name__}: {exc}", "karar": "HATA"})
            print(f"[{sid}] HATA: {type(exc).__name__}: {exc}", flush=True)
        # bellek: bölüm geçişlerinde büyük kategorileri bırak
        if sid in ("S15", "S21", "S26", "S30"):
            y.birak("dokunus", "zone", "swing", "event", "frm", "frm_olay")

    # --- rapor ---
    basliklar = [
        "# REPLAY SORU SETİ YANITLARI — S01–S32",
        "",
        f"Üreten: ``python -m research.soru_cevaplama`` · girdi: {', '.join(map(str, dizinler))}",
        "Sözleşme: docs/arastirma/REPLAY_SORU_SETI_2026-10-29.md (§0 C1–C8, karar ≥12/5–12/<5 pp)",
        "",
        "> Her blok: VERİ (n + sansür) → TABLO → ANA SAYI → KARAR (ön-kayıtlı eşikle).",
        "> KARAR = YAZILIR / YALNIZ KART METNİ / RED / KARAR YOK (n<30) / gözlem (sansür>20%).",
        "",
    ]
    for bolum, sidler in BOLUMLER:
        sec = [r for r in sonuclar if r["id"] in sidler]
        if not sec:
            continue
        basliklar.append(f"## {bolum}")
        basliklar.append("")
        for r in sec:
            basliklar += [
                f"### {r['id']} · {r['baslik']}",
                "",
                f"- **VERİ**: {r['veri']}",
                "",
                r["tablo"],
                "",
                f"- **ANA SAYI**: {r['ana']}",
                f"- **KARAR**: {r['karar']}",
            ]
            if r.get("notlar"):
                basliklar.append(f"- **Notlar**: {'; '.join(r['notlar'])}")
            basliklar.append("")
    # canlı bileşen özeti (§6 karar eşlemesi) — tüm karar sınıfları
    basliklar += ["## §6 KARAR ÖZETİ (canlı bileşen eşlemesiyle)", ""]
    import re as _re

    def _sinif(k: str) -> str:
        kk = k.upper()
        # açık yazılmış canlı kararlar — bir soruda tek bir hücre bile yazıyorsa önce o
        for anahtar in ("YAZILIR", "ZORUNLU", "STOP KURALI", "KURAL+KARNE", "KURAL + KARNE",
                        "BASTIRMA KURALI", "TAVSİYE"):
            if anahtar in kk:
                return "CANLIYA YAZILIR (kart/rozet/kuyruk/filtre)"
        if "HATA" in kk or "KARAR YOK" in kk:
            return "KARAR YOK / HATA (n<30, sansür>20%, o hücrede karar yok)"
        # kelime sınırı: kural-red / reddedilir / :RED — "DEVREDILDI" ile karışmasın
        if _re.search(r"(^|[^A-ZĞÜŞİÖÇ])RED([^A-ZĞÜŞİÖÇ]|$)", kk) or "REDD" in kk:
            return "RED / hipotez çöktü (yeni kural açılmaz)"
        if "→ KURAL" in kk:
            return "CANLIYA YAZILIR (kart/rozet/kuyruk/filtre)"
        if "KART METN" in kk or "METN" in kk:
            return "YALNIZ KART METNİ (5–12 pp / dipnot)"
        return "Gözlem / yapısal bulgu (kurala dönüşmez)"

    kovalar: dict[str, list[tuple[str, str]]] = {
        "CANLIYA YAZILIR (kart/rozet/kuyruk/filtre)": [],
        "YALNIZ KART METNİ (5–12 pp / dipnot)": [],
        "RED / hipotez çöktü (yeni kural açılmaz)": [],
        "KARAR YOK / HATA (n<30, sansür>20%, o hücrede karar yok)": [],
        "Gözlem / yapısal bulgu (kurala dönüşmez)": [],
    }
    for r in sonuclar:
        kovalar[_sinif(str(r.get("karar", "")))].append((r["id"], str(r.get("karar", ""))))
    for baslik, maddeler in kovalar.items():
        basliklar.append(f"### {baslik} — {len(maddeler)} madde")
        basliklar.append("")
        for sid, k in maddeler:
            basliklar.append(f"- **{sid}**: {k[:260]}")
        basliklar.append("")
    basliklar += ["> Kart/rozet/filtre yalnız 'CANLIYA YAZILIR' maddelerine yazılır (§0 eşik sözleşmesi).",
                  "> RED maddeleri mevcut kararlardan da çıkarılmaz; yalnız yeni kural AÇILMAZ.", ""]

    yol = Path(args.rapor)
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text("\n".join(basliklar), encoding="utf-8")
    print(f"[rapor] {yol} ({yol.stat().st_size} bayt)", flush=True)

    json_yol = Path(args.json) if args.json else dizinler[0] / "soru_seti_sonuclari.json"
    json_yol.parent.mkdir(parents=True, exist_ok=True)
    ozet = {r["id"]: {"baslik": r["baslik"], "ana": r["ana"], "karar": r["karar"]}
            for r in sonuclar}
    json_yol.write_text(json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[json] {json_yol}", flush=True)
    hata = sum(1 for r in sonuclar if r["baslik"] == "HATA")
    return 1 if hata else 0


if __name__ == "__main__":
    raise SystemExit(main())
