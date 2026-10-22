"""Formasyon sorularının cevap kartları — `frm`/`frm_olay` tablolarından.

Girdi: `arastirma_cikti/frm.jsonl` + `frm_olay.jsonl` (koşu çıktısı).
Çıktı: `docs/arastirma/FORMASYON_SONUCLARI.md` — FRM-01…20 için cevap kartı.

Kart biçimi `YASAM_TABLOSU.md` §1'deki sözleşmedir:
    SORU / AŞAMA / ANA ÇİZGİ / ÇIKTI / TABAN / YAN SÜTUN / KARAR

İstatistik kuralları (kullanıcı sözleşmesi):
* `n < 50` → sayı yazılmaz, "ölçüm yok (n=X)".
* Oranlarda **Wilson %95 GA**; farklarda **küme bootstrap** (küme = sembol).
  Aynı sembolün 4 zaman dilimi bağımsız gözlem değildir; küme bootstrap bunu
  hesaba katar.
* GA sıfırı içeriyorsa → "fark yok". Yorum yapılmaz.
* Keşif, ayrı pencerede tekrar test edilmeden "bulgu" sayılmaz; bu rapor
  **tanımlayıcı** katmandır (L1).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

__all__ = ["rapor_uret", "main"]

B = 400          # bootstrap tekrarı
SEED = 20261021
MIN_N = 50

#: Kartların dokunduğu kolonlar — eksikse None ile eklenir (kolon yokluğu 0 değildir).
_GEREKLI = (
    "symbol", "timeframe", "stable_id", "pattern_type", "family", "has_pole",
    "pole_dir", "pole_magnitude", "raw_quality_dogum", "geometry_atr_dogum",
    "daralma_orani", "frm_faz_geometri_bar", "frm_dogum_rol_ucu",
    "frm_dogum_ph_atr", "frm_dogum_pl_atr", "kirilim_var", "terminal_state",
    "acik", "omur_bar", "frm_kirilim_deneme", "frm_kirilim_teyitli_var",
    "frm_kirilim_ms_uyum", "break_gecikme_bar", "break_volume_score",
    "retest_var", "retest_gecikme_bar", "retest_derinlik_atr",
    "frm_teyit_sonrasi_mfe_atr", "frm_teyit_sonrasi_mae_atr",
    "frm_yakinlik_ust_fitil_atr", "frm_yakinlik_alt_fitil_atr",
    "frm_kirilim_zone_var", "frm_vp_rvol_dogum", "frm_vp_rvol_olgunlasma",
    "frm_vp_rvol_retest", "frm_vp_usable_dogum", "frm_vp_usable_retest",
    "frm_teyit_ms_bos_ayni_bar", "frm_teyit_ms_bos_ayni_yon",
    "frm_teyit_ms_bos_gecikme_bar", "frm_gecersiz_state", "bitis_sebebi",
    "dogum_bar_time",
)


# ---------------------------------------------------------------- yardımcılar

def _oku(yol: Path) -> list[dict[str, Any]]:
    if not yol.exists():
        return []
    satirlar = []
    with yol.open(encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    satirlar.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
    return satirlar


def _sayi(deger: Any) -> float | None:
    if deger is None or isinstance(deger, bool):
        return None
    try:
        v = float(deger)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    payda = 1 + z * z / n
    merkez = (p + z * z / (2 * n)) / payda
    yari = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0)) / payda
    return max(0.0, merkez - yari), min(1.0, merkez + yari)


def _yuzde(x: float | None) -> str:
    return "—" if x is None else f"%{100 * x:.1f}"


def _isaretli(x: float) -> str:
    return f"{x * 100:+.1f}".replace(".", ",")


def _medyan(degerler: Sequence[float]) -> float | None:
    temiz = [v for v in degerler if v is not None and math.isfinite(v)]
    return float(np.median(temiz)) if temiz else None


def _ceyrek(degerler: Sequence[float]) -> tuple[float, float] | None:
    temiz = [v for v in degerler if v is not None and math.isfinite(v)]
    if len(temiz) < 5:
        return None
    return float(np.percentile(temiz, 25)), float(np.percentile(temiz, 75))


def _mask(seri: Any) -> Any:
    """Üç değerli bool kolonu maskeye çevirir (NaN → False).

    ``fillna(False).astype(bool)`` pandas 2.2'de object downcast uyarısı
    üretir; nullable ``boolean`` üzerinden aynı sonucu sessizce verir.
    """
    return seri.astype("boolean").fillna(False).astype(bool)


def _fark_metni(df: Any, mask_a: Any, mask_b: Any, etiket_a: str = "A",
                etiket_b: str = "B") -> str:
    """İki oranın farkı + küme bootstrap GA'sı, tek satır metin."""
    ga = _fark_ga(df, mask_a, mask_b)
    pa = float(df.loc[mask_a, "_ok"].mean())
    pb = float(df.loc[mask_b, "_ok"].mean())
    fark = pa - pb
    if ga is None:
        return f"fark {f'{fark * 100:+.1f}'.replace('-', '−')} puan (GA ölçülemedi)"
    karar = "fark var" if (ga[0] > 0.0 or ga[1] < 0.0) else "fark yok"
    _y = lambda v: f"{v * 100:+.1f}".replace("-", "−")  # noqa: E731
    return (f"fark {_y(fark)} puan (GA {_y(ga[0])}…{_y(ga[1])}) · {karar}")


def _fark_ga(df: Any, mask_a: Any, mask_b: Any, sutun: str = "symbol",
             B: int = B, seed: int = SEED) -> tuple[float, float] | None:
    """İki oranın farkı için küme bootstrap %95 GA."""
    a = df[mask_a]
    b = df[mask_b]
    if len(a) == 0 or len(b) == 0:
        return None
    kumeler = sorted(set(a[sutun].astype(str)) | set(b[sutun].astype(str)))
    if len(kumeler) < 5:
        return None
    rng = np.random.default_rng(seed)
    ga = {k: g for k, g in a.groupby(a[sutun].astype(str))}
    gb = {k: g for k, g in b.groupby(b[sutun].astype(str))}
    farklar = []
    for _ in range(B):
        secim = rng.choice(kumeler, size=len(kumeler), replace=True)
        pa = dad = pb = dbd = 0
        for k in secim:
            ga_k = ga.get(k)
            if ga_k is not None and len(ga_k):
                pa += int(ga_k["_ok"].sum())
                dad += len(ga_k)
            gb_k = gb.get(k)
            if gb_k is not None and len(gb_k):
                pb += int(gb_k["_ok"].sum())
                dbd += len(gb_k)
        if dad and dbd:
            farklar.append(pa / dad - pb / dbd)
    if not farklar:
        return None
    return float(np.percentile(farklar, 2.5)), float(np.percentile(farklar, 97.5))


def _karar(ga: tuple[float, float] | None) -> str:
    if ga is None:
        return "ölçüm yok (küme sayısı yetersiz)"
    if ga[0] <= 0.0 <= ga[1]:
        return "fark yok (GA sıfırı içeriyor)"
    return "fark var (GA sıfırı içermiyor)"


def _kart(soru: str, asama: str, cizgi: str, cikti: str, taban: str,
          yan: str, karar: str) -> str:
    return (f"**SORU**      : {soru}\n"
            f"**AŞAMA**     : {asama}\n"
            f"**ANA ÇİZGİ** : {cizgi}\n"
            f"**ÇIKTI**     : {cikti}\n"
            f"**TABAN**     : {taban}\n"
            f"**YAN SÜTUN** : {yan}\n"
            f"**KARAR**     : {karar}\n")


def _olcum_yok(nedeni: str) -> str:
    return f"**KARAR**     : ölçüm yok — {nedeni}\n"


def _tablo(basliklar: Sequence[str], satirlar: Iterable[Sequence[Any]]) -> str:
    out = ["| " + " | ".join(basliklar) + " |",
           "|" + "|".join("---" for _ in basliklar) + "|"]
    for s in satirlar:
        out.append("| " + " | ".join("" if v is None else str(v) for v in s) + " |")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- kart üretici

def _kart_01(df: Any) -> str:
    """FRM-01 — öncül hareket (direk) var mı, yönü ne?"""
    n = len(df)
    if n < MIN_N:
        return "### FRM-01 · Öncül hareket\n\n" + _olcum_yok(f"n={n}") + "\n"
    oncul = [_sayi(v) for v in df["frm_oncul_getiri_20bar_atr"]]
    temiz = [v for v in oncul if v is not None]
    var = _mask(df["has_pole"])
    k = int(var.sum())
    lo, hi = _wilson(k, n)
    if len(temiz) < MIN_N:
        cikti = f"direk (pole) oranı {_yuzde(k / n)} · öncül getiri ölçülemedi"
    else:
        pozitif = sum(1 for v in temiz if v > 0)
        lo2, hi2 = _wilson(pozitif, len(temiz))
        cek = _ceyrek(temiz)
        cikti = (f"son 20 bar getirisi medyan {np.median(temiz):+.2f} ATR"
                 + (f" (ÇGA {cek[0]:+.2f}–{cek[1]:+.2f})" if cek else "")
                 + f" · yukarı olanlar {_yuzde(pozitif / len(temiz))} "
                   f"(GA {_yuzde(lo2)}–{_yuzde(hi2)})"
                 + f" · direk (pole) tabanlı {_yuzde(k / n)} (GA {_yuzde(lo)}–{_yuzde(hi)})")
    return ("### FRM-01 · Öncül hareket\n\n" + _kart(
        "FRM-01 · Formasyon doğmadan önce öncül hareket var mıydı, yönü neydi?",
        "S0 (doğum öncesi)",
        "doğumdan önceki 20 barın getirisi (ATR) + direk (pole) varlığı",
        cikti,
        f"tüm formasyonlar (n={n}, öncül getiri n={len(temiz)})",
        "— (ana çıktı zaten doğum öncesi)",
        "tanımlayıcı; eşik yok") + "\n")


def _kart_02(df: Any) -> str:
    n = len(df)
    if n < MIN_N:
        return "### FRM-02 · Tip / kalite / genişlik\n\n" + _olcum_yok(f"n={n}") + "\n"
    tip = df["pattern_type"].fillna("?").value_counts()
    satirlar = []
    for ad, adet in tip.head(8).items():
        alt = df[df["pattern_type"] == ad]
        satirlar.append([ad, len(alt), _yuzde(len(alt) / n),
                         f"{_medyan([_sayi(v) for v in alt['raw_quality_dogum']]) or 0:.0f}",
                         f"{_medyan([_sayi(v) for v in alt['geometry_atr_dogum']]) or 0:.2f}"])
    return ("### FRM-02 · Tip, kalite ve doğum genişliği\n\n" + _kart(
        "FRM-02 · Hangi formasyon tipi ne sıklıkta doğuyor, kalitesi ve boyu ne?",
        "S1 (doğum)",
        "formasyon tipi",
        "dağılım + tip başına medyan kalite/genişlik",
        f"tüm formasyonlar (n={n})",
        "n<50 tipler yalnız sayım; oran yorumu yok",
        "tanımlayıcı; eşik yok") + "\n" +
        _tablo(["tip", "n", "pay", "medyan kalite", "medyan genişlik (ATR)"], satirlar) + "\n")


def _kart_03(df: Any) -> str:
    alt = df[df["frm_dogum_rol_ucu"].notna()]
    n = len(alt)
    if n < MIN_N:
        return ("### FRM-03 · Doğumda en yakın destek/direnç mesafesi\n\n"
                + _olcum_yok(f"n={n} (MS rolü olan formasyon)") + "\n")
    def kova(v):
        if v is None:
            return None
        if v < 0.5:
            return "<0.5"
        if v < 1.0:
            return "0.5–1"
        if v < 2.0:
            return "1–2"
        if v < 3.0:
            return "2–3"
        return "≥3"
    alt = alt.copy()
    alt["_mesafe"] = [
        _sayi(p) if _sayi(p) is not None else (None if _sayi(l) is None else _sayi(l))
        for p, l in zip(alt["frm_dogum_ph_atr"], alt["frm_dogum_pl_atr"])]
    alt = alt[alt["_mesafe"].notna()]
    alt["_kova"] = alt["_mesafe"].map(kova)
    alt["_ok"] = _mask(alt["kirilim_var"])
    satirlar = []
    for kova_ad in ("<0.5", "0.5–1", "1–2", "2–3", "≥3"):
        g = alt[alt["_kova"] == kova_ad]
        if len(g) < 10:
            satirlar.append([kova_ad, len(g), "—", "—"])
            continue
        lo, hi = _wilson(int(g["_ok"].sum()), len(g))
        satirlar.append([kova_ad, len(g), _yuzde(g["_ok"].mean()),
                         f"{_yuzde(lo)}–{_yuzde(hi)}"])
    return ("### FRM-03 · Doğumda en yakın korunan seviye ne kadar uzakta?\n\n" + _kart(
        "FRM-03 · Formasyon doğduğunda en yakın PH/PL seviyesi kaç ATR uzakta?",
        "S1 (doğum)",
        "mesafe kovası (<0.5 · 0.5–1 · 1–2 · 2–3 · ≥3 ATR)",
        "kova başına formasyon sayısı + kırılıma varma oranı",
        f"MS rolü açık olan formasyonlar (n={n})",
        "rol ucu PH/PL",
        "tanımlayıcı; kırılım oranı sütunu keşif niteliğinde") + "\n" +
        _tablo(["mesafe", "n", "kırılım oranı", "GA"], satirlar) + "\n")


def _kart_04(df: Any) -> str:
    n = len(df)
    if n < MIN_N:
        return "### FRM-04 · Daralma\n\n" + _olcum_yok(f"n={n}") + "\n"
    dar = [_sayi(v) for v in df["daralma_orani"]]
    med = _medyan(dar)
    cey = _ceyrek(dar)
    sure = _medyan([_sayi(v) for v in df["frm_faz_geometri_bar"]])
    return ("### FRM-04 · Daralma ne kadar, kaç barda?\n\n" + _kart(
        "FRM-04 · Formasyon kırılıma kadar ne kadar daralıyor ve kaç bar sürüyor?",
        "S2 (olgunlaşma)",
        "daralma oranı: 1 − genişlik(son gözlem barı)/genişlik(doğum)",
        (f"medyan daralma {_yuzde(med)}"
         + (f" (ÇGA {_yuzde(cey[0])}–{_yuzde(cey[1])})" if cey else "")
         + f" · geometri fazı medyan {sure:.0f} bar" if med is not None and sure else "—"),
        f"tüm formasyonlar (n={n})",
        "geometri fazı kısa: formasyon apeksine yakın doğuyor",
        "tanımlayıcı; eşik yok") + "\n")


def _kart_05(df: Any) -> str:
    gecerli = df[_mask(df["frm_vp_usable_dogum"])]
    n = len(gecerli)
    if n < MIN_N:
        return "### FRM-05 · Sıkışmada hacim kurudu mu?\n\n" + _olcum_yok(f"n={n}") + "\n"
    dogum = [_sayi(v) for v in gecerli["frm_vp_rvol_dogum"]]
    olgun = [_sayi(v) for v in gecerli["frm_vp_rvol_olgunlasma"]]
    cift = [(a, b) for a, b in zip(dogum, olgun) if a is not None and b is not None]
    if len(cift) < MIN_N:
        return "### FRM-05 · Sıkışmada hacim kurudu mu?\n\n" + _olcum_yok(f"eşleşmiş n={len(cift)}") + "\n"
    fark = [b - a for a, b in cift]
    med = float(np.median(fark))
    negatif = sum(1 for f in fark if f < 0)
    ayni = sum(1 for f in fark if f == 0)
    lo, hi = _wilson(negatif, len(fark))
    # Pencere ayrışmıyorsa "kuruma" testi yapılamaz: motor olgunlaşma
    # örneğini doğumla aynı bardan alıyor (geometri fazı medyan 1 bar).
    if ayni / len(fark) > 0.5:
        return ("### FRM-05 · Sıkışmada hacim kurudu mu?\n\n" + _kart(
            "FRM-05 · Doğumdan olgunlaşmaya rvol düşüyor mu?",
            "S2 (olgunlaşma)",
            "rvol(olgunlaşma) − rvol(doğum)",
            f"ölçüm yok · eşleşen çift {len(fark)} (vp olgunlaşma kapsaması düşük) · "
            f"%{100 * ayni / len(fark):.1f}'inde iki bar birebir aynı",
            f"hacmi kullanılabilir formasyonlar (n={len(fark)})",
            "yan sütun: rvol · ana çıktı değil",
            "ölçüm yok (olgunlaşma penceresi doğumla aynı bar)") + "\n")
    return ("### FRM-05 · Sıkışmada hacim kurudu mu?\n\n" + _kart(
        "FRM-05 · Doğumdan olgunlaşmaya rvol düşüyor mu?",
        "S2 (olgunlaşma)",
        "rvol(olgunlaşma) − rvol(doğum)",
        f"medyan fark {med:+.3f} · düşenlerin oranı {_yuzde(negatif / len(fark))} "
        f"(GA {_yuzde(lo)}–{_yuzde(hi)})",
        f"hacmi kullanılabilir formasyonlar (n={len(fark)})",
        "yan sütun: rvol · ana çıktı değil",
        "tanımlayıcı") + "\n")


def _kart_06(df: Any) -> str:
    """FRM-06 — yakınlık dozu → kırılım oranı (dairesellik yok: yakınlık kırılım öncesi)."""
    alt = df[df["frm_yakinlik_ust_fitil_atr"].notna() | df["frm_yakinlik_alt_fitil_atr"].notna()].copy()
    n = len(alt)
    if n < MIN_N:
        return "### FRM-06 · Yakınlık → kırılım\n\n" + _olcum_yok(f"n={n}") + "\n"
    alt["_yakin"] = [min([v for v in (_sayi(a), _sayi(b)) if v is not None], default=None)
                     for a, b in zip(alt["frm_yakinlik_ust_fitil_atr"], alt["frm_yakinlik_alt_fitil_atr"])]
    alt = alt[alt["_yakin"].notna()].copy()
    alt["_ok"] = _mask(alt["kirilim_var"])
    kovalar = [(0.0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, float("inf"))]
    satirlar = []
    for alt_s, ust_s in kovalar:
        g = alt[(alt["_yakin"] >= alt_s) & (alt["_yakin"] < ust_s)]
        ad = f"{alt_s:g}–{ust_s:g}" if math.isfinite(ust_s) else f"≥{alt_s:g}"
        if len(g) < 10:
            satirlar.append([ad, len(g), "—", "—"])
            continue
        lo, hi = _wilson(int(g["_ok"].sum()), len(g))
        satirlar.append([ad, len(g), _yuzde(g["_ok"].mean()), f"{_yuzde(lo)}–{_yuzde(hi)}"])
    return ("### FRM-06 · Direnç yakınlığı kırılım oranını artırıyor mu?\n\n" + _kart(
        "FRM-06 · Sınıra en çok yaklaşma (kırılım ÖNCESİ) kırılım oranını değiştiriyor mu?",
        "S3 (hazırlık)",
        "min uzaklık kovası (fitil, ATR)",
        "kova başına kırılıma varma oranı",
        f"tüm formasyonlar (n={len(alt)})",
        "—",
        "tanımlayıcı; doz-yanıt eğrisi") + "\n" +
        _tablo(["min uzaklık", "n", "kırılım oranı", "GA"], satirlar) + "\n")


def _kart_07(df: Any) -> str:
    n = len(df)
    if n < MIN_N:
        return "### FRM-07 · Kırılım denemesi\n\n" + _olcum_yok(f"n={n}") + "\n"
    dagilim = df["frm_kirilim_deneme"].fillna(0).astype(int).value_counts().sort_index()
    satirlar = [[int(k), int(v), _yuzde(v / n)] for k, v in dagilim.items()]
    med = _medyan([_sayi(v) for v in df["frm_kirilim_deneme"]])
    return ("### FRM-07 · Kaç deneme yapılıyor?\n\n" + _kart(
        "FRM-07 · Bir formasyon kırılımı kaç kez deniyor?",
        "S4 (deneme)",
        "kırılım fazına giriş epizodu (KIRILIM_DENEMESI + KIRILIM_ADAYI)",
        f"dağılım (medyan {med:.0f} deneme)",
        f"tüm formasyonlar (n={n})",
        "zayıf deneme (yalnız KIRILIM_DENEMESI) ayrı kolonda",
        "tanımlayıcı") + "\n" +
        _tablo(["deneme", "n", "pay"], satirlar) + "\n")


def _kart_08(df: Any) -> str:
    alt = df[df["frm_kirilim_ms_uyum"].notna()]
    n = len(alt)
    if n < MIN_N:
        return "### FRM-08 · Kırılım yönü ↔ rol tarafı\n\n" + _olcum_yok(f"n={n}") + "\n"
    ok = alt["frm_kirilim_ms_uyum"].astype(bool)
    k = int(ok.sum())
    lo, hi = _wilson(k, n)
    return ("### FRM-08 · Kırılım yönü en yakın seviyenin tarafıyla uyumlu mu?\n\n" + _kart(
        "FRM-08 · Kırılım, en yakın korunan seviyeye doğru mu oluyor?",
        "S4 (deneme)",
        "uyum: yukarı kırılım + üstte PH / aşağı kırılım + altta PL",
        f"uyum oranı {_yuzde(k / n)} (GA {_yuzde(lo)}–{_yuzde(hi)})",
        f"kırılımı olan ve MS rolü açık formasyonlar (n={n})",
        "—",
        "tanımlayıcı") + "\n")


def _kart_09(df: Any) -> str:
    gecikme = [_sayi(v) for v in df["break_gecikme_bar"]]
    temiz = [v for v in gecikme if v is not None]
    if len(temiz) < MIN_N:
        return "### FRM-09 · Teyit gecikmesi\n\n" + _olcum_yok(f"n={len(temiz)}") + "\n"
    cey = _ceyrek(temiz)
    return ("### FRM-09 · Teyit ne kadar gecikiyor?\n\n" + _kart(
        "FRM-09 · Kırılım anından teyide kaç bar geçiyor?",
        "S5 (teyit)",
        "bar gecikmesi",
        f"medyan {np.median(temiz):.0f} bar"
        + (f" (ÇGA {cey[0]:.0f}–{cey[1]:.0f})" if cey else ""),
        f"teyit alan formasyonlar (n={len(temiz)})",
        "—",
        "tanımlayıcı") + "\n")


def _kart_10(df: Any) -> str:
    alt = df[df["frm_teyit_sonrasi_mfe_atr"].notna()].copy()
    n = len(alt)
    if n < MIN_N:
        return "### FRM-10 · Teyit barı hacmi\n\n" + _olcum_yok(f"n={n}") + "\n"
    alt["_hedef"] = alt["frm_teyit_sonrasi_mfe_atr"].map(lambda v: (_sayi(v) or 0) >= 1.0)
    hacim = [_sayi(v) for v in alt["break_volume_score"]]
    if sum(1 for v in hacim if v is not None) < MIN_N:
        return "### FRM-10 · Teyit barı hacmi\n\n" + _olcum_yok("break_volume_score boş") + "\n"
    alt["_hacim"] = hacim
    alt = alt[alt["_hacim"].notna()].copy()
    alt["_kova"] = np.where(alt["_hacim"] >= 75, "Q4 (≥75)",
                            np.where(alt["_hacim"] >= 50, "Q3 (50–75)",
                                     np.where(alt["_hacim"] >= 25, "Q2 (25–50)", "Q1 (<25)")))
    satirlar = []
    for kova in ("Q1 (<25)", "Q2 (25–50)", "Q3 (50–75)", "Q4 (≥75)"):
        g = alt[alt["_kova"] == kova]
        if len(g) < 10:
            satirlar.append([kova, len(g), "—", "—"])
            continue
        lo, hi = _wilson(int(g["_hedef"].sum()), len(g))
        satirlar.append([kova, len(g), _yuzde(g["_hedef"].mean()), f"{_yuzde(lo)}–{_yuzde(hi)}"])
    return ("### FRM-10 · Teyit barı hacmi: teyit mi, tuzak mı?\n\n" + _kart(
        "FRM-10 · Teyit barındaki hacim, teyit sonrası ≥1 ATR hareketi değiştiriyor mu?",
        "S5 (teyit)",
        "hacim skoru kovası",
        "kova başına ≥1 ATR MFE oranı (12 bar)",
        f"teyit alan formasyonlar (n={len(alt)})",
        "yan sütun: hacim — ana çıktı değil",
        "tanımlayıcı; zone'da bulunan 'Q4 zayıf' bulgusuyla karşılaştırılacak") + "\n" +
        _tablo(["hacim kovası", "n", "≥1 ATR oranı", "GA"], satirlar) + "\n")


def _kart_11(df: Any) -> str:
    """FRM-11 — teyit ile MS BOS aynı barda mı?"""
    alt = df[df["frm_teyit_ms_bos_gecikme_bar"].notna()].copy()
    n = len(alt)
    if n < MIN_N:
        return ("### FRM-11 · Teyit ↔ MS BOS\n\n"
                + _olcum_yok(f"eşleşen n={n}") + "\n")
    ayni = _mask(alt["frm_teyit_ms_bos_ayni_bar"])
    k = int(ayni.sum())
    lo, hi = _wilson(k, n)
    ayni_yon = _mask(alt["frm_teyit_ms_bos_ayni_yon"])
    gecikme = [_sayi(v) for v in alt["frm_teyit_ms_bos_gecikme_bar"]]
    med = _medyan([abs(v) for v in gecikme if v is not None])
    return ("### FRM-11 · Teyit ile MS BOS aynı barda mı?\n\n" + _kart(
        "FRM-11 · Formasyon teyidi ile yapısal BOS aynı anda mı oluyor?",
        "S5 (teyit)",
        "aynı bar (|gecikme| ≤ 10 bar içinde en yakın BOS)",
        f"aynı bar oranı {_yuzde(k / n)} (GA {_yuzde(lo)}–{_yuzde(hi)}) · "
        f"aynı bar + aynı yön {_yuzde(int(ayni_yon.sum()) / n)} · "
        f"medyan |gecikme| {med:.0f} bar" if med is not None else f"aynı bar oranı {_yuzde(k / n)}",
        f"teyit alan ve ±10 bar içinde BOS bulunan formasyonlar (n={n})",
        "—",
        "tanımlayıcı") + "\n")


def _kart_12(df: Any) -> str:
    n = len(df)
    if n < MIN_N:
        return "### FRM-12 · Retest oranı\n\n" + _olcum_yok(f"n={n}") + "\n"
    teyit = df[_mask(df["frm_kirilim_teyitli_var"])]
    nt = len(teyit)
    if nt < MIN_N:
        return "### FRM-12 · Retest oranı\n\n" + _olcum_yok(f"teyitli n={nt}") + "\n"
    k = int(_mask(teyit["retest_var"]).sum())
    lo, hi = _wilson(k, nt)
    gecikme = _medyan([_sayi(v) for v in teyit["retest_gecikme_bar"]])
    return ("### FRM-12 · Retest oranı ne, kaç barda geliyor?\n\n" + _kart(
        "FRM-12 · Teyitten sonra retest geliyor mu, kaç barda?",
        "S6 (retest)",
        "retest var/yok",
        f"retest oranı {_yuzde(k / nt)} (GA {_yuzde(lo)}–{_yuzde(hi)}) · "
        f"medyan gecikme {gecikme:.0f} bar" if gecikme is not None else f"retest oranı {_yuzde(k / nt)}",
        f"teyit alan formasyonlar (n={nt})",
        "retest = RETEST_BASARILI state'i (motorun kendi tanımı)",
        "tanımlayıcı") + "\n")


def _kart_13(df: Any) -> str:
    # Taban yalnız **başarılı retest** (retest_var). Retest fazına girip
    # seviyeyi geri alamayan formasyonların derinliği "0" gibi görünüyordu
    # ve "<0.25" kovasını şişiriyordu; onlar retest değil, kırılımın geri
    # çökmesidir.
    alt = df[_mask(df["retest_var"]) & df["retest_derinlik_atr"].notna()
             & df["frm_teyit_sonrasi_mfe_atr"].notna()].copy()
    n = len(alt)
    if n < MIN_N:
        return "### FRM-13 · Retest derinliği\n\n" + _olcum_yok(f"n={n}") + "\n"
    alt["_hedef"] = alt["frm_teyit_sonrasi_mfe_atr"].map(lambda v: (_sayi(v) or 0) >= 1.0)
    alt["_kova"] = np.where(alt["retest_derinlik_atr"] >= 0.5, "≥0.5 ATR",
                            np.where(alt["retest_derinlik_atr"] >= 0.25, "0.25–0.5", "<0.25"))
    satirlar = []
    for kova in ("<0.25", "0.25–0.5", "≥0.5 ATR"):
        g = alt[alt["_kova"] == kova]
        if len(g) < 10:
            satirlar.append([kova, len(g), "—", "—"])
            continue
        lo, hi = _wilson(int(g["_hedef"].sum()), len(g))
        satirlar.append([kova, len(g), _yuzde(g["_hedef"].mean()), f"{_yuzde(lo)}–{_yuzde(hi)}"])
    return ("### FRM-13 · Retest derinliği başarıyı değiştiriyor mu?\n\n" + _kart(
        "FRM-13 · Retest sırasında sınıra geri dönüş derinliği ≥1 ATR hareketi değiştiriyor mu?",
        "S6 (retest)",
        "derinlik kovası (ATR)",
        "kova başına ≥1 ATR MFE oranı",
        f"başarılı retest gören teyitli formasyonlar (n={n})",
        "retest fazına girip geri alamayanlar paydada yok",
        "tanımlayıcı") + "\n" +
        _tablo(["derinlik", "n", "≥1 ATR oranı", "GA"], satirlar) + "\n")


def _kart_14(df: Any) -> str:
    alt = df[_mask(df["retest_var"]) & df["frm_teyit_sonrasi_mfe_atr"].notna()
             & df["frm_vp_rvol_retest"].notna()].copy()
    n = len(alt)
    if n < MIN_N:
        return "### FRM-14 · Retest hacmi\n\n" + _olcum_yok(f"n={n}") + "\n"
    alt["_hedef"] = alt["frm_teyit_sonrasi_mfe_atr"].map(lambda v: (_sayi(v) or 0) >= 1.0)
    rvol = [_sayi(v) for v in alt["frm_vp_rvol_retest"]]
    alt["_rvol"] = rvol
    alt = alt[alt["_rvol"].notna()].copy()
    if len(alt) < MIN_N:
        return "### FRM-14 · Retest hacmi\n\n" + _olcum_yok(f"rvol dolu n={len(alt)}") + "\n"
    med = float(np.median(alt["_rvol"]))
    alt["_grup"] = np.where(alt["_rvol"] >= med, "rvol ≥ medyan", "rvol < medyan")
    satirlar = []
    for grup in ("rvol < medyan", "rvol ≥ medyan"):
        g = alt[alt["_grup"] == grup]
        lo, hi = _wilson(int(g["_hedef"].sum()), len(g))
        satirlar.append([grup, len(g), _yuzde(g["_hedef"].mean()), f"{_yuzde(lo)}–{_yuzde(hi)}"])
    return ("### FRM-14 · Retest hacmi düşükse başarı artıyor mu?\n\n" + _kart(
        "FRM-14 · Retest barındaki rvol, teyit sonrası hareketi değiştiriyor mu?",
        "S6 (retest)",
        "rvol medyan bölmesi",
        "grup başına ≥1 ATR MFE oranı · "
        + _fark_metni(alt.assign(_ok=alt["_hedef"].astype(int)),
                      alt["_grup"] == "rvol ≥ medyan", alt["_grup"] == "rvol < medyan"),
        f"başarılı retest gören ve rvol'ü ölçülebilen formasyonlar (n={len(alt)})",
        "yan sütun: hacim",
        "tanımlayıcı") + "\n" +
        _tablo(["grup", "n", "≥1 ATR oranı", "GA"], satirlar) + "\n")


def _kart_15(df: Any) -> str:
    """FRM-15 — sonuç dağılımı.

    Payda **yalnız terminal** formasyonlardır. Motorun elinden çıkan (daha iyi
    aday geldiği için değiştirilen) ve veri sonuna kadar açık kalan formasyonlar
    "ölüm" değildir; ayrı sayılır (sansür).
    """
    n = len(df)
    if n < MIN_N:
        return "### FRM-15 · Sonuç dağılımı\n\n" + _olcum_yok(f"n={n}") + "\n"
    bitis = df.get("bitis_sebebi")
    if bitis is None:
        bitis = np.where(df["terminal_state"].isin(
            ["FORMASYON_TAMAMLANDI", "BASARISIZ_KIRILIM", "FORMASYON_GECERSIZ"]),
            "TERMINAL", "DIGER")
        bitis = __import__("pandas").Series(bitis, index=df.index)
    terminal = df[bitis == "TERMINAL"]
    nt = len(terminal)
    if nt < MIN_N:
        return "### FRM-15 · Sonuç dağılımı\n\n" + _olcum_yok(f"terminal n={nt}") + "\n"
    dagilim = terminal["terminal_state"].value_counts()
    satirlar = []
    for ad, adet in dagilim.items():
        lo, hi = _wilson(int(adet), nt)
        satirlar.append([ad, int(adet), _yuzde(adet / nt), f"{_yuzde(lo)}–{_yuzde(hi)}"])
    degisen = int((bitis == "YERINE_GECEN").sum())
    acik = int((bitis == "VERI_SONU").sum())
    return ("### FRM-15 · Sonuç dağılımı (yaşam tablosunun son satırı)\n\n" + _kart(
        "FRM-15 · Formasyonlar nasıl ölüyor?",
        "S7 (sonuç)",
        "terminal state",
        "dağılım + GA",
        f"ölümle biten formasyonlar (n={nt})",
        f"sansür: değiştirilen {degisen} · veri sonu {acik} (paydaya girmez)",
        "tanımlayıcı") + "\n" +
        _tablo(["terminal state", "n", "pay", "GA"], satirlar) + "\n")


def _kart_16(df: Any) -> str:
    tamam = df[df["terminal_state"] == "FORMASYON_TAMAMLANDI"]
    n = len(tamam)
    if n < MIN_N:
        return "### FRM-16 · Tamamlanma süresi\n\n" + _olcum_yok(f"n={n}") + "\n"
    sure = _medyan([_sayi(v) for v in tamam["omur_bar"]])
    mfe = _medyan([_sayi(v) for v in tamam["frm_teyit_sonrasi_mfe_atr"]])
    cey = _ceyrek([_sayi(v) for v in tamam["frm_teyit_sonrasi_mfe_atr"]])
    return ("### FRM-16 · Tamamlanma süresi ve hareket\n\n" + _kart(
        "FRM-16 · Tamamlanan formasyon ne kadar sürüyor ve teyitten sonra ne kadar gidiyor?",
        "S7 (sonuç)",
        "ömür (bar) · teyit sonrası MFE (ATR, 12 bar)",
        f"medyan ömür {sure:.0f} bar · medyan MFE {mfe:.2f} ATR"
        + (f" (ÇGA {cey[0]:.2f}–{cey[1]:.2f})" if cey else ""),
        f"tamamlanan formasyonlar (n={n})",
        "uzun pencere (40 bar) ayrı kolonda",
        "tanımlayıcı") + "\n")


def _kart_17(df: Any) -> str:
    basarisiz = df[df["terminal_state"] == "BASARISIZ_KIRILIM"]
    n = len(basarisiz)
    if n < MIN_N:
        return "### FRM-17 · Başarısız kırılım\n\n" + _olcum_yok(f"n={n}") + "\n"
    mae = _medyan([_sayi(v) for v in basarisiz["frm_teyit_sonrasi_mae_atr"]])
    cey = _ceyrek([_sayi(v) for v in basarisiz["frm_teyit_sonrasi_mae_atr"]])
    return ("### FRM-17 · Başarısız kırılım ne kadar geri dönüyor?\n\n" + _kart(
        "FRM-17 · Başarısız kırılımda teyit sonrası ters hareket ne kadar?",
        "S7 (sonuç)",
        "MAE (ATR, 12 bar)",
        f"medyan {mae:.2f} ATR" + (f" (ÇGA {cey[0]:.2f}–{cey[1]:.2f})" if cey else ""),
        f"başarısız kırılımlar (n={n})",
        "—",
        "tanımlayıcı") + "\n")


def _kart_18(df: Any, olay: list[dict[str, Any]]) -> str:
    """FRM-18 — geçersizleşme hangi aşamada?

    Kaynak **trace** (`frm_gecersiz_state`): olayın kendi `state` alanı, olay
    üretildiği andaki nihai state'i taşır ve INVALID için her zaman
    `FORMASYON_GECERSIZ` olur — bilgi taşımaz.
    """
    gec = df[df["terminal_state"] == "FORMASYON_GECERSIZ"]
    n = len(gec)
    bilinmeyen = int(gec["frm_gecersiz_state"].isna().sum())
    zayif = sum(1 for o in olay if o.get("olay_type") == "WEAK")
    if n < MIN_N:
        return ("### FRM-18 · Geçersizleşme hangi aşamada?\n\n"
                + _olcum_yok(f"geçersizleşen n={n}") + "\n")
    # `frm_gecersiz_state` boş = GECERSIZ'e ilk barda girilmiş: formasyon
    # doğduğu barda ölüyor (ömür 1 bar). "Bilinmeyen" demek yanlış etiketti.
    dagilim = gec["frm_gecersiz_state"].where(
        gec["frm_gecersiz_state"].notna(), "DOĞUMDA (ömür 1 bar)").value_counts()
    satirlar = [[str(k), int(v), _yuzde(v / n)] for k, v in dagilim.items()]
    return ("### FRM-18 · Geçersizleşme hangi aşamada oluyor?\n\n" + _kart(
        "FRM-18 · Formasyon hangi aşamada geçersizleşiyor?",
        "S7 (sonuç)",
        "geçersizleşmeden ÖNCEKİ state",
        "dağılım",
        f"geçersizleşen formasyonlar (n={n}) · ayrıca WEAK olayı: {zayif}",
        f"doğumda ölen {bilinmeyen} (paydada; ayrı satır)",
        "tanımlayıcı") + "\n" +
        _tablo(["önceki state", "n", "pay"], satirlar) + "\n")


def _kart_19(df: Any) -> str:
    alt = df[_mask(df["kirilim_var"]) & df["frm_kirilim_zone_var"].notna()].copy()
    n = len(alt)
    if n < MIN_N:
        return "### FRM-19 · Kırılımda OB/FVG\n\n" + _olcum_yok(f"n={n}") + "\n"
    alt["_ok"] = alt["terminal_state"] == "FORMASYON_TAMAMLANDI"
    zone_var = _mask(alt["frm_kirilim_zone_var"])
    if int(zone_var.sum()) < 20 or int((~zone_var).sum()) < 20:
        return "### FRM-19 · Kırılımda OB/FVG\n\n" + _olcum_yok("karşılaştırma hücresi küçük") + "\n"
    satirlar = []
    for ad, mask in (("zone var", zone_var), ("zone yok", ~zone_var)):
        g = alt[mask]
        lo, hi = _wilson(int(g["_ok"].sum()), len(g))
        satirlar.append([ad, len(g), _yuzde(g["_ok"].mean()), f"{_yuzde(lo)}–{_yuzde(hi)}"])
    ga = _fark_ga(alt.assign(_ok=alt["_ok"].astype(int)), zone_var, ~zone_var)
    # OB ve FVG ayrı: soru "OB/FVG" diye birleşikti ama kırılımda bulunma
    # sıklıkları çok farklı (OB ~%35, FVG ~%2.7) — birleşik sayı OB'yi anlatır.
    yan = []
    for ad, sutun in (("OB var", "frm_kirilim_ob_var"), ("FVG var", "frm_kirilim_fvg_var")):
        if sutun not in alt.columns:
            continue
        m = _mask(alt[sutun])
        if int(m.sum()) < 10 or int((~m).sum()) < 10:
            yan.append([ad, int(m.sum()), "—", "—"])
            continue
        yan.append([ad, int(m.sum()), _yuzde(alt.loc[m, "_ok"].mean()),
                    _fark_metni(alt.assign(_ok=alt["_ok"].astype(int)), m, ~m)])
    return ("### FRM-19 · Kırılım noktasında OB/FVG var mı?\n\n" + _kart(
        "FRM-19 · Kırılım anında fiyat canlı bir OB/FVG zone'u içindeyse sonuç değişiyor mu?",
        "Çapraz",
        "zone var / yok",
        "tamamlanma oranı · " + _fark_metni(alt.assign(_ok=alt["_ok"].astype(int)), zone_var, ~zone_var),
        f"kırılımı olan formasyonlar (n={len(alt)})",
        "OB ve FVG ayrı ayrı (bağımsız kolonlar) altta",
        _karar(ga)) + "\n" +
        _tablo(["grup", "n", "tamamlanma", "GA"], satirlar) + "\n" +
        (_tablo(["ayrıştırma (yan sütun)", "n", "tamamlanma", "fark (GA)"], yan) + "\n"
         if yan else ""))


def _kart_20(df: Any) -> str:
    alt = df[_mask(df["kirilim_var"]) & df["frm_kirilim_ms_uyum"].notna()].copy()
    n = len(alt)
    if n < MIN_N:
        return "### FRM-20 · Formasyon yönü ↔ MS\n\n" + _olcum_yok(f"n={n}") + "\n"
    alt["_ok"] = alt["terminal_state"] == "FORMASYON_TAMAMLANDI"
    uyum = alt["frm_kirilim_ms_uyum"].astype(bool)
    satirlar = []
    for ad, mask in (("uyumlu", uyum), ("uyumsuz", ~uyum)):
        g = alt[mask]
        if len(g) < 10:
            satirlar.append([ad, len(g), "—", "—"])
            continue
        lo, hi = _wilson(int(g["_ok"].sum()), len(g))
        satirlar.append([ad, len(g), _yuzde(g["_ok"].mean()), f"{_yuzde(lo)}–{_yuzde(hi)}"])
    ga = _fark_ga(alt.assign(_ok=alt["_ok"].astype(int)), uyum, ~uyum) if len(alt[~uyum]) else None
    return ("### FRM-20 · Formasyon yönü ile MS yönü uyumu\n\n" + _kart(
        "FRM-20 · Kırılım yönü en yakın rol seviyesine doğruysa sonuç değişiyor mu?",
        "Çapraz",
        "uyumlu / uyumsuz",
        "tamamlanma oranı · " + _fark_metni(alt.assign(_ok=alt["_ok"].astype(int)), uyum, ~uyum)
        if len(alt[~uyum]) else "tamamlanma oranı",
        f"kırılımı olan ve MS rolü açık formasyonlar (n={n})",
        "—",
        _karar(ga)) + "\n" +
        _tablo(["grup", "n", "tamamlanma", "GA"], satirlar) + "\n")


def _kapsam(df: Any, olay: list[dict[str, Any]]) -> str:
    n = len(df)
    seri = df.groupby(["symbol", "timeframe"]).ngroups if n else 0
    sembol = df["symbol"].nunique() if n else 0
    tarih = [str(v) for v in df["dogum_bar_time"].dropna()] if n else []
    acik = int(_mask(df["acik"]).sum()) if n else 0
    return _tablo(
        ["Kalem", "Değer"],
        [["Seri (sembol × TF)", seri],
         ["Sembol", sembol],
         ["Formasyon", n],
         ["Formasyon olayı", len(olay)],
         ["Hâlâ açık (sansürlü)", acik],
         ["Doğum aralığı", f"{min(tarih)[:10]} → {max(tarih)[:10]}" if tarih else "—"]])


def rapor_uret(cikti: Path, rapor: Path) -> str:
    frm = _oku(cikti / "frm.jsonl")
    olay = _oku(cikti / "frm_olay.jsonl")
    if not frm:
        raise SystemExit(f"frm.jsonl boş veya yok: {cikti}")

    import pandas as pd

    df = pd.DataFrame(frm)
    # Kolon sözlüğü sözleşmesi: eksik kolon "0" değildir. Eski/yeni koşu
    # karışırsa eksik kolon None olarak eklenir ve ilgili kart "ölçüm yok" der.
    for sutun in _GEREKLI:
        if sutun not in df.columns:
            df[sutun] = None
    # Yalnızca GERÇEKTEN bool olan kolonlar zorlanır. `frm_kirilim_ms_uyum` ve
    # `frm_kirilim_zone_var` üç değerlidir: None = "kırılım yok" demektir ve
    # False'a çevrilirse payda şişer (kolon sözlüğü K4).
    for sutun in ("kirilim_var", "acik", "terminal_mi", "has_pole", "retest_var",
                  "frm_kirilim_teyitli_var", "frm_vp_usable_dogum",
                  "frm_vp_usable_retest"):
        if sutun in df.columns:
            df[sutun] = df[sutun].astype("boolean").fillna(False).astype(bool)

    bolumler = [
        "# Formasyon Sonuçları — FRM-01…20 cevap kartları\n",
        "> **Durum:** üretilen rapor · **Katman:** L1 tanımlayıcı ölçüm (kural değişikliği yok)\n"
        "> **Kaynak:** `arastirma_cikti/frm.jsonl` + `frm_olay.jsonl`\n"
        "> **Kolon sözlüğü:** [KOLON_SOZLUGU.md](KOLON_SOZLUGU.md) §13 · "
        "**Soru sicili:** [YASAM_TABLOSU.md](YASAM_TABLOSU.md) §4.1\n",
        "## Kapsam\n",
        _kapsam(df, olay),
        "\n## Okuma kuralları\n",
        "- `n < 50` → sayı yazılmaz, **ölçüm yok**.\n"
        "- Oranlarda **Wilson %95 GA**; farklarda **sembol küme bootstrap**.\n"
        "- \"fark var\" yalnız GA sıfırı içermediğinde yazılır.\n"
        "- Bunlar **tanımlayıcı** bulgulardır; ayrı pencerede tekrar test edilmeden "
        "kural hâline gelmez.\n",
        "\n---\n\n## S0–S1 · Doğum\n",
        _kart_01(df), _kart_02(df), _kart_03(df),
        "\n---\n\n## S2 · Olgunlaşma\n",
        _kart_04(df), _kart_05(df),
        "\n---\n\n## S3–S4 · Hazırlık ve deneme\n",
        _kart_06(df), _kart_07(df), _kart_08(df),
        "\n---\n\n## S5 · Teyit\n",
        _kart_09(df), _kart_10(df), _kart_11(df),
        "\n---\n\n## S6 · Retest\n",
        _kart_12(df), _kart_13(df), _kart_14(df),
        "\n---\n\n## S7 · Sonuç\n",
        _kart_15(df), _kart_16(df), _kart_17(df), _kart_18(df, olay),
        "\n---\n\n## Çapraz\n",
        _kart_19(df), _kart_20(df),
    ]
    metin = "\n".join(str(b) for b in bolumler if b)
    rapor.parent.mkdir(parents=True, exist_ok=True)
    rapor.write_text(metin, encoding="utf-8")
    return metin


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Formasyon cevap kartlarını üretir.")
    ap.add_argument("--cikti", default="arastirma_cikti")
    ap.add_argument("--rapor", default="docs/arastirma/FORMASYON_SONUCLARI.md")
    args = ap.parse_args(argv)
    metin = rapor_uret(Path(args.cikti), Path(args.rapor))
    print(f"[frm-rapor] yazıldı: {args.rapor} ({len(metin)} karakter)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
