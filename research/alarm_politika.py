"""Alarm POLİTİKASI replay'i — "hangi kural daha iyi?" sorusunu sayıyla cevaplar.

Mevcut ``domain_alarm_replay.py`` **canlı davranışı** ölçer (bugün gönderilen
kart ne yapıyor). Bu modül ondan farklı bir soru sorar:

    "Kuralı değiştirsem ne olurdu?"

Aynı tetik satırlarını (``tetikler.jsonl``) farklı politikalardan geçirir ve
her politika için üç şeyi yan yana koyar:

1. **Sıklık** — sembol/gün başına kaç kart çıkıyor (alarm yorgunluğu).
2. **İsabet** — çıkan kartların ne kadarı ≥1 ATR hareket görüyor (taban farkı).
3. **Hatırlama** — "iyi" tetiklerin (≥1,5 ATR) yüzde kaçı hâlâ yakalanıyor.

Üçüncü sütun olmadan politika tartışması eksik kalır: her politika isabeti
artırır, çünkü az kart basar. Asıl soru **neyi kaybettiğidir**.

Kullanım::

    python -m research.alarm_politika --cikti var/domain_alarm_replay \\
        --rapor docs/arastirma/ALARM_POLITIKA_SONUCLARI.md

Not: Bu modül **hiçbir canlı ayarı değiştirmez** ve canlı kodu import etmez;
yalnız replay JSONL'ini okur. Politika tanımları burada veridir, kural değil.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import pandas as pd

COOLDOWN_BAR = 6

#: Tek bir tetiğin "hareket gördü" sayılması için gereken eşik (ATR).
HAREKET_ESIK = 1.0
#: "İyi tetik" tanımı — politika hatırlaması bunun üzerinden ölçülür.
IYI_ESIK = 1.5

#: Zaman dilimi → gün başına bar (BIST seansı ~9,5 saat; 1d = 1 bar).
BAR_GUN = {"1h": 9.5, "2h": 4.75, "4h": 2.375, "1d": 1.0}


# ---------------------------------------------------------------------------
# Politika tanımları
# ---------------------------------------------------------------------------

#: Ölçülen katkısı +1,7 pp'nin altında kalan kanallar (CHoCH +0,9, BOS −2,0).
#: Tek başına bunlar kart basmaz; yalnız hacim/formasyon eşliğinde basar.
YALNIZ_OB_FVG_BOS = {"OB", "FVG", "BOS", "CHoCH"}


def _kanallar(t: Mapping[str, Any]) -> tuple[str, ...]:
    k = t.get("kanallar") or ()
    return tuple(sorted(str(x) for x in k))


def _hacim(t: Mapping[str, Any]) -> str:
    return str(t.get("hacim_tier") or "")


def _bagl(t: Mapping[str, Any], ad: str, varsayilan: float = 0.0) -> float:
    try:
        v = float(t.get(ad))
        return v if math.isfinite(v) else varsayilan
    except (TypeError, ValueError, OverflowError):
        return varsayilan


def p_canli(t: Mapping[str, Any]) -> bool:
    """P0 · Bugünkü kural: herhangi bir kanal ateşlediyse kart."""
    return True


def p_bos_sustur(t: Mapping[str, Any]) -> bool:
    """P1 · BOS tek başına ise basma (ölçülen katkı −2,0 pp)."""
    k = _kanallar(t)
    return not (len(k) == 1 and k[0] == "BOS")


def p_yalniz_hacim(t: Mapping[str, Any]) -> bool:
    """P2 · Yalnız hacim kademesi ≥5× (ölçülen en güçlü tek kanal)."""
    return _hacim(t) in {"5x", "10×", "10x"}


def p_katman(t: Mapping[str, Any]) -> bool:
    """P3 · Katmanlı: zayıf kanallar yalnız hacim/formasyonla birlikte.

    Ölçüm: OB +1,7 · FVG +2,8 (zayıf ama pozitif), BOS −2,0 · CHoCH +0,9.
    Tek başına bunlar kart basmaz; FORMASYON veya HACİM eşliğinde basar.
    """
    k = _kanallar(t)
    if not k:
        return False
    hacim = _hacim(t) in {"5x", "10×", "10x"}
    formasyon = "FORMASYON" in k
    if hacim:
        return True
    if formasyon:
        # Formasyon + gürültü kanalı birlikteyse de bas (kanıt: +2,9 pp temel).
        return True
    # Yalnız OB / FVG / BOS / CHoCH → sessiz katman.
    return not set(k) <= YALNIZ_OB_FVG_BOS


def p_katman_baglam(t: Mapping[str, Any]) -> bool:
    """P4 · P3 + bağlam: sıkışma genişliyor veya koşu yukarı (ölçülen +5,0/+4,7 pp)."""
    if not p_katman(t):
        return False
    kosu = _bagl(t, "bagl_gunici_kosu")
    sikisma = _bagl(t, "bagl_sikisma", 1.0)
    if _hacim(t) in {"5x", "10×", "10x"}:
        return True
    return kosu >= 1.0 or sikisma >= 1.0


def p_baglam(t: Mapping[str, Any]) -> bool:
    """P6 · Kanalı hiç eleme; yalnız bağlam: sıkışma genişliyor veya koşu yukarı.

    Ölçüm kanal seçiminin zayıf (+1,7…+2,8 pp), bağlamın daha güçlü olduğunu
    gösteriyor (sıkışma geniş +5,0 pp, koşu yukarı +4,7 pp). Bu politika o
    iddiayı doğrudan test eder: aynı kanallar, farklı eleme ölçütü.
    """
    kosu = _bagl(t, "bagl_gunici_kosu")
    sikisma = _bagl(t, "bagl_sikisma", 1.0)
    return kosu >= 1.0 or sikisma >= 1.0


def p_baglam_veya_hacim(t: Mapping[str, Any]) -> bool:
    """P7 · P6 + hacim ≥5× (hacim kendi başına yeter)."""
    return p_baglam(t) or _hacim(t) in {"5x", "10×", "10x"}


def p_katman_seans(t: Mapping[str, Any]) -> bool:
    """P5 · P3 + seans: yalnız 09–10 ve 17 (ölçülen en iyi iki saat)."""
    if not p_katman(t):
        return False
    try:
        saat = int(t.get("bagl_seans_saati"))
    except (TypeError, ValueError):
        return False
    return saat in {9, 17}


POLITIKALAR: list[tuple[str, str, Callable[[Mapping[str, Any]], bool]]] = [
    ("P0", "canlı kural (her kanal)", p_canli),
    ("P1", "P0 − tek başına BOS", p_bos_sustur),
    ("P2", "yalnız hacim ≥5×", p_yalniz_hacim),
    ("P3", "katman: yalnız OB/FVG/BOS → sessiz", p_katman),
    ("P4", "P3 + bağlam (sıkışma/koşu)", p_katman_baglam),
    ("P5", "P3 + seans (09–10, 17)", p_katman_seans),
    ("P6", "yalnız bağlam (sıkışma/koşu)", p_baglam),
    ("P7", "P6 + hacim ≥5×", p_baglam_veya_hacim),
]


# ---------------------------------------------------------------------------
# Veri
# ---------------------------------------------------------------------------

def _bayrak(deger: Any) -> bool:
    """``yon_asim_100`` gibi sütunlar bool ya da 0/1 gelir; ikisini de kabul et."""
    if isinstance(deger, str):
        return deger.strip().lower() in {"true", "1", "1.0", "evet"}
    try:
        return bool(deger) and not (isinstance(deger, float) and math.isnan(deger))
    except (TypeError, ValueError):
        return False


def oku(cikti: Path) -> pd.DataFrame:
    yol = cikti / "tetikler.jsonl"
    if not yol.exists():
        raise SystemExit(f"Replay çıktısı yok: {yol} (önce domain_alarm_replay koş)")
    satirlar = []
    with open(yol, "r", encoding="utf-8") as f:
        for cizgi in f:
            cizgi = cizgi.strip()
            if cizgi:
                satirlar.append(json.loads(cizgi))
    df = pd.DataFrame(satirlar)
    if df.empty:
        raise SystemExit("Replay çıktısı boş.")
    for kolon in ("yon_tepe_atr", "yon_dip_atr", "ters_h12", "yon_asim_100", "yon_asim_150"):
        if kolon in df:
            df[kolon] = pd.to_numeric(df[kolon], errors="coerce")
    # İki farklı "hareket" tanımı var, ikisi de raporlanır:
    #  * ``hareket``    — YÖNLÜ: kartın söylediği yönde ≥1 ATR (arşiv raporuyla aynı ölçü).
    #  * ``hareket_iki`` — herhangi bir yöne ≥1 ATR (daha kaba; tabanı %80'e çıkarır ve
    #    farkları sıkıştırır). Tek başına kullanılmamalı.
    df["hareket"] = df.get("yon_asim_100").map(_bayrak)
    df["iyi"] = df.get("yon_asim_150").map(_bayrak)
    df["hareket_iki"] = (df["yon_tepe_atr"] >= HAREKET_ESIK) | (df["yon_dip_atr"] >= HAREKET_ESIK)
    return df


def _cooldown(secili: pd.DataFrame, bar: int = COOLDOWN_BAR) -> pd.DataFrame:
    """Sembol/TF başına ``bar`` bar sessizlik (canlı dedup kuralı)."""
    if secili.empty:
        return secili
    kalan: list[int] = []
    son: dict[tuple[str, str], int] = {}
    for idx, satir in secili.sort_values(["symbol", "timeframe", "bar_index"]).iterrows():
        anahtar = (str(satir["symbol"]), str(satir["timeframe"]))
        indeks = int(satir["bar_index"])
        onceki = son.get(anahtar)
        if onceki is not None and indeks - onceki < bar:
            continue
        son[anahtar] = indeks
        kalan.append(idx)
    return secili.loc[kalan]


def _gun_sayisi(df: pd.DataFrame, meta: pd.DataFrame | None = None) -> float:
    """Toplam (sembol × gün) — ``meta.jsonl``deki GERÇEK bar sayısından.

    DİKKAT: tetik satırı sayısı bar sayısı değildir. Önceki sürüm ``len(grup)``
    kullanıyordu ve kart/gün oranını ~3 kat şişiriyordu (bir seride 3.253 bar
    var ama yalnız ~800 tetik satırı). Bu düzeltme, "günde kaç kart" sorusunun
    cevabını değiştirir; bu yüzden ayrıca test edilir.
    """
    if meta is not None and len(meta):
        gun = 0.0
        for _, satir in meta.iterrows():
            tf = str(satir.get("timeframe"))
            try:
                bar = int(satir.get("bar_sayisi"))
            except (TypeError, ValueError):
                continue
            gun += bar / BAR_GUN.get(tf, 1.0)
        return max(gun, 1.0)
    # meta yoksa: seri başına tetik satırından kaba tahmin (üst sınır).
    toplam = 0.0
    for (_, tf), grup in df.groupby(["symbol", "timeframe"]):
        toplam += len(grup) / BAR_GUN.get(str(tf), 1.0)
    return max(toplam, 1.0)


# ---------------------------------------------------------------------------
# Ölçüm
# ---------------------------------------------------------------------------

def politika_tablosu(df: pd.DataFrame, taban: pd.DataFrame,
                     meta: pd.DataFrame | None = None) -> list[dict[str, Any]]:
    """Her politika için sıklık/isabet/hatırlama. Eksik sütunlar sessizce 0 olur."""
    for kare in (df, taban):
        for kolon, varsayilan in (("hareket", False), ("iyi", False), ("hareket_iki", False),
                                  ("kontrol", False), ("hacim_tier", None)):
            if kolon not in kare:
                kare[kolon] = varsayilan
    taban_oran = float(taban["hareket"].mean()) if len(taban) else float("nan")
    ham = df[df.get("kontrol", False) == False]  # noqa: E712 - açık karşılaştırma
    iyi_toplam = float(ham["iyi"].sum())
    gun = _gun_sayisi(ham, meta)

    satirlar: list[dict[str, Any]] = []
    for kod, ad, fn in POLITIKALAR:
        mask = ham.apply(fn, axis=1) if len(ham) else pd.Series(dtype=bool)
        secili = ham[mask]
        gonderilen = _cooldown(secili)
        n = len(gonderilen)
        if n == 0:
            satirlar.append({"kod": kod, "ad": ad, "n": 0})
            continue
        oran = float(gonderilen["hareket"].mean())
        iyi = float(gonderilen["iyi"].sum())
        satirlar.append({
            "kod": kod,
            "ad": ad,
            "n": n,
            "gunluk": n / gun,
            "hareket": oran,
            "fark_pp": (oran - taban_oran) * 100.0,
            "iki": float(gonderilen["hareket_iki"].mean()),
            "iyi": iyi,
            "hatirlama": iyi / iyi_toplam if iyi_toplam else float("nan"),
            "basilan_pay": n / max(len(ham), 1),
            "wilson": wilson_alt(oran, n),
        })
    return satirlar


#: Ufuk × eşik ızgarası. Replay JSONL'inde hazır duruyor (``yon_h3``,
#: ``yon_h12``, ``yon_h40``) — ek koşu GEREKMEZ. Kanal ayrışması burada test
#: edilir: farklı ufuk/eşikte kanallar birbirinden ayrılıyor mu?
IZGARA: tuple[tuple[int, float], ...] = (
    (3, 0.5), (3, 1.0), (3, 1.5),
    (12, 1.0), (12, 1.5), (12, 2.0),
    (40, 2.0), (40, 3.0),
)


def _ufuk_orani(grup: pd.DataFrame, ufuk: int, esik: float) -> float | None:
    kolon = f"yon_h{ufuk}"
    if kolon not in grup or len(grup) == 0:
        return None
    seri = pd.to_numeric(grup[kolon], errors="coerce")
    seri = seri[seri.notna()]
    if len(seri) == 0:
        return None
    return float((seri >= esik).mean())


def izgara_tablosu(df: pd.DataFrame, taban: pd.DataFrame) -> list[dict[str, Any]]:
    """Kanal × (ufuk, eşik) — kanallar hangi ölçüde ayrışıyor?

    ``DOMAIN_ALARM_REPLAY.md`` yalnız 12 bar ölçüsünü raporluyor. Orada tüm
    kanallar %64–%72 aralığında kalıyor. Bu tablo, **başka ufuk/eşiklerde**
    ayrışmanın büyüyüp büyümediğini gösterir. Büyümüyorsa "kanal seçimi
    önemsiz" hükmü kesinleşir; büyüyorsa katmanlama savunulabilir olur.
    """
    satirlar: list[dict[str, Any]] = []
    ham = df[df.get("kontrol", False) == False]  # noqa: E712
    kn = ham["kanallar"].map(
        lambda v: str(v[0]) if isinstance(v, (list, tuple)) and v else "YOK"
    )
    for kanal in ("HACIM", "FORMASYON", "FVG", "OB", "BOS", "CHoCH"):
        grup = ham[kn == kanal]
        if len(grup) < 50:
            continue
        satir: dict[str, Any] = {"kanal": kanal, "n": len(grup)}
        for ufuk, esik in IZGARA:
            satir[f"{ufuk}b_{esik}"] = _ufuk_orani(grup, ufuk, esik)
        satirlar.append(satir)
    if taban is not None and len(taban):
        tab: dict[str, Any] = {"kanal": "TABAN", "n": len(taban)}
        for ufuk, esik in IZGARA:
            tab[f"{ufuk}b_{esik}"] = _ufuk_orani(taban, ufuk, esik)
        satirlar.append(tab)
    return satirlar


def wilson_alt(p: float, n: int, z: float = 1.96) -> float:
    """Wilson alt sınırı — küçük n'li politikaların şansını ayıklar."""
    if n <= 0:
        return float("nan")
    payda = 1.0 + z * z / n
    merkez = p + z * z / (2 * n)
    yayilim = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0))
    return max((merkez - yayilim) / payda, 0.0)


def _f(deger: float | None, basamak: int = 2) -> str:
    if deger is None or (isinstance(deger, float) and not math.isfinite(deger)):
        return "—"
    return f"{deger:.{basamak}f}".replace(".", ",")


def _oku_meta(cikti: Path) -> pd.DataFrame | None:
    yol = cikti / "meta.jsonl"
    if not yol.exists():
        return None
    satirlar = [json.loads(l) for l in yol.read_text(encoding="utf-8").splitlines() if l.strip()]
    return pd.DataFrame(satirlar) if satirlar else None


def rapor(df: pd.DataFrame, taban: pd.DataFrame, meta: pd.DataFrame | None = None,
          baslik: bool = True) -> str:
    tablo = politika_tablosu(df, taban, meta)
    taban_oran = float(taban["hareket"].mean()) * 100.0 if len(taban) else float("nan")
    satir = ("| politika | ne yapar | kart | kart/gün | ≥1 ATR (yönlü) | Wilson alt | taban farkı "
             "| ≥1 ATR (iki yön) | iyi yakalama | hamın %'si |")
    cizgi = "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    govde = [
        f"| **{r['kod']}** | {r['ad']} | {r['n']:,} | {_f(r.get('gunluk'))} | "
        f"%{_f((r.get('hareket') or 0) * 100, 1)} | "
        f"%{_f((r.get('wilson') or 0) * 100, 1)} | "
        f"{('+' if (r.get('fark_pp') or 0) >= 0 else '')}{_f(r.get('fark_pp'), 1)} pp | "
        f"%{_f((r.get('iki') or 0) * 100, 1)} | "
        f"%{_f((r.get('hatirlama') or 0) * 100, 1)} | "
        f"%{_f((r.get('basilan_pay') or 0) * 100, 1)} |"
        for r in tablo
    ]
    govde_satirlari = [
        f"Taban (alarmsız bar): **%{_f(taban_oran, 1)}** · tetik satırı: "
        f"**{len(df[df.get('kontrol', False) == False]):,}** · taban satırı: **{len(taban):,}**",
        "",
        satir,
        cizgi,
        *govde,
        "",
        "- **≥1 ATR (yönlü)**: kartın söylediği yönde 12 bar içinde ≥1 ATR. Arşiv raporuyla",
        "  aynı ölçü (orada taban %64,1 / tetik %66,5).",
        "- **taban farkı**: aynı verideki alarmsız barlara göre fark. Tek başına yeterli değil;",
        "  az kart basan politika bu sütunu otomatik yükseltir.",
        "- **iyi yakalama**: ≥1,5 ATR hareket eden tetiklerin politika sonrası hâlâ basılan payı.",
        "  Bu sütun, politikanın **ne kaybettiğini** gösterir.",
        f"- Cooldown: {COOLDOWN_BAR} bar (canlı kural). Kart sayıları cooldown SONRASI.",
    ]
    if not baslik:
        return "\n".join(govde_satirlari)
    return "\n".join(["# Politika karşılaştırması", ""] + govde_satirlari)


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Alarm politikası karşılaştırması (replay JSONL'den)")
    p.add_argument("--cikti", default="var/domain_alarm_replay")
    p.add_argument("--rapor", default="docs/arastirma/ALARM_POLITIKA_SONUCLARI.md")
    args = p.parse_args(argv)

    df = oku(Path(args.cikti))
    meta = _oku_meta(Path(args.cikti))
    taban = df[df.get("kontrol", False) == True]  # noqa: E712
    metin = rapor(df, taban, meta)
    yol = Path(args.rapor)
    yol.parent.mkdir(parents=True, exist_ok=True)
    # ELLE YAZILAN BÖLÜMLERİ KORU: dosyada ``<!-- URETILEN:BASLANGIC -->``
    # işareti varsa yalnız o blok yenilenir. Aksi hâlde analiz/karar bölümleri
    # (4.5, 4.6, 5.5 gibi) her koşuda silinir — bu bir kez yaşandı.
    ESKI_BAS, ESKI_SON = "<!-- URETILEN:BASLANGIC -->", "<!-- URETILEN:BITIS -->"
    if yol.exists():
        eski = yol.read_text(encoding="utf-8")
        if ESKI_BAS in eski and ESKI_SON in eski:
            bas = eski.index(ESKI_BAS) + len(ESKI_BAS)
            son = eski.index(ESKI_SON)
            eski = eski[:bas] + "\n\n" + rapor(df, taban, meta, baslik=False) + "\n\n" + eski[son:]
            yol.write_text(eski, encoding="utf-8")
            print(f"[rapor] {yol} (yalniz URETILEN blogu yenilendi)")
            print(metin)
            return 0
    yaz = f"{ESKI_BAS}\n\n{metin}\n\n{ESKI_SON}\n"
    yol.write_text(yaz, encoding="utf-8")
    print(metin)
    print(f"\n[rapor] {yol} ({len(metin)} karakter)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
