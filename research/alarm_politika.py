"""Ağsız alarm politikası karşılaştırması (P0/P6; isteğe bağlı sekiz politika).

Aynı adayları ve cooldown kararlarını korur. Eski ölçüler yalnız tarihsel
karşılaştırma içindir. Seans yükü için seri bazında bar envanteri gereklidir.
Kullanım ve pilot sınırları: docs/arastirma/ALARM_POLITIKA_PILOTU.md.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
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


_YUKSEK_HACIM_KADEMELERI = frozenset({"5×", "5x", "10×", "10x"})


def p_yalniz_hacim(t: Mapping[str, Any]) -> bool:
    """P2 · Yalnız hacim kademesi ≥5× (ölçülen en güçlü tek kanal)."""
    return _hacim(t) in _YUKSEK_HACIM_KADEMELERI


def p_katman(t: Mapping[str, Any]) -> bool:
    """P3 · Katmanlı: zayıf kanallar yalnız hacim/formasyonla birlikte.

    Ölçüm: OB +1,7 · FVG +2,8 (zayıf ama pozitif), BOS −2,0 · CHoCH +0,9.
    Tek başına bunlar kart basmaz; FORMASYON veya HACİM eşliğinde basar.
    """
    k = _kanallar(t)
    if not k:
        return False
    hacim = _hacim(t) in _YUKSEK_HACIM_KADEMELERI
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
    if _hacim(t) in _YUKSEK_HACIM_KADEMELERI:
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
    return p_baglam(t) or _hacim(t) in _YUKSEK_HACIM_KADEMELERI


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


def oku(cikti: Path, semboller: set[str] | None = None) -> pd.DataFrame:
    yol = cikti / "tetikler.jsonl"
    if not yol.exists():
        raise SystemExit(f"Replay çıktısı yok: {yol} (önce domain_alarm_replay koş)")
    satirlar = []
    with open(yol, "r", encoding="utf-8") as f:
        for cizgi in f:
            cizgi = cizgi.strip()
            if cizgi:
                row = json.loads(cizgi)
                if semboller is None or row["symbol"] in semboller:
                    satirlar.append(row)
    df = pd.DataFrame(satirlar)
    if df.empty:
        raise SystemExit("Replay çıktısı boş.")
    # Üreticide 12 mum tamamlanmadan bayrak null'dır; bool(null) başarısızlık değildir.
    for kaynak, hedef in (("yon_asim_100", "hareket"), ("yon_asim_150", "iyi"), ("ters_h12", "ters")):
        ham = df[kaynak]
        df[hedef] = ham.map(_bayrak).astype("boolean").mask(ham.isna())
    df["hareket_iki"] = df["hareket"] | df["ters"]  # herhangi bir yöne, aynı 12 bar
    df["eski_iki"] = (df["yon_tepe_atr"] >= 1) | (df["yon_dip_atr"] >= 1)
    df["seans"] = pd.to_datetime(df["bar_time"], utc=True).dt.tz_convert("Europe/Istanbul").dt.date.astype(str)
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

def politika_tablosu(df: pd.DataFrame, taban: pd.DataFrame, *, seanslar=None, politikalar=POLITIKALAR):
    """Cooldown tüm geçmişte çalışır; yalnız sonuç ve yük seçili seanslarda sayılır."""
    def pencerede(rows):
        return rows if seanslar is None else rows[rows["seans"].isin(seanslar)]

    ham = df[~df["kontrol"]]
    adaylar = pencerede(ham)
    iyi_toplam = adaylar["iyi"].sum()
    taban_oran = pencerede(taban)["hareket"].mean()
    sonuc = []
    for kod, ad, kural in politikalar:
        secili = ham.loc[ham.apply(kural, axis=1).astype(bool)] if len(ham) else ham
        kart = pencerede(_cooldown(secili))
        n = len(kart)
        olculen = int(kart["hareket"].count())
        oran = float(kart["hareket"].dropna().mean()) if olculen else math.nan
        r = {
            "kod": kod, "ad": ad, "n": n,
            "olculen": olculen, "eksik": n - olculen,
            "hareket": oran, "wilson": wilson_alt(oran, olculen),
            "fark_pp": (oran - float(taban_oran)) * 100 if pd.notna(taban_oran) else math.nan,
            "iki": float(kart["hareket_iki"].mean()) if kart["hareket_iki"].count() else math.nan,
            "hatirlama": kart["iyi"].sum() / iyi_toplam if iyi_toplam else math.nan,
            "basilan_pay": n / len(adaylar) if len(adaylar) else math.nan,
            "eski_hareket": kart["hareket"].fillna(False).mean() if n else math.nan,
            "eski_iki": kart["eski_iki"].mean() if n and "eski_iki" in kart else math.nan,
        }
        if seanslar is not None:
            yuk = kart.groupby("seans").size().reindex(sorted(seanslar), fill_value=0)
            r.update(gunluk=yuk.mean(), tipik=yuk.median(), zirve=int(yuk.max()), zirve_gun=yuk.idxmax())
        sonuc.append(r)
    return sonuc


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


def seans_kapsami(meta, semboller, ilk, son):
    """Tam seri setini doğrula; kart çıkmayan seansları bar envanterinden al."""
    from research.arsiv import ARASTIRMA_TIMEFRAMELERI

    sec = meta[meta["symbol"].isin(semboller)]
    beklenen = {(s, tf) for s in semboller for tf in ARASTIRMA_TIMEFRAMELERI}
    if len(sec) != len(beklenen) or set(zip(sec.symbol, sec.timeframe)) != beklenen:
        raise ValueError("Aktif native evrende eksik veya tekrarlı seri var.")
    if not all(isinstance(m, dict) and m for m in sec.seans_bar_sayilari):
        raise ValueError("Seans bar envanteri eksik veya geçersiz.")
    # Replay sıfır gelecek barı olan son çapa için satır üretmez. Son,
    # kısmi olabilecek seansı yük hesabına sokma; 1–11 barlık sonuçlar kalır.
    gunler = set.intersection(*(set(m) - {max(m)} for m in sec.seans_bar_sayilari))
    ortak = sorted(g for g in gunler if ilk <= g <= son)
    if not ortak:
        raise ValueError("Seçilen aralıkta ortak seans yok.")
    return ortak


def rapor(df, meta, ilk, son, aktif, native, *, tum_politikalar=False):
    semboller = set(aktif) & set(native)
    if not semboller:
        raise ValueError("Native arşivde aktif sembol yok.")
    seanslar = seans_kapsami(meta, semboller, ilk, son)
    df = df[df.symbol.isin(semboller)]
    tablo = politika_tablosu(df, df[df.kontrol], seanslar=seanslar,
                             politikalar=[p for p in POLITIKALAR if tum_politikalar or p[0] in {"P0", "P6"}])
    # v1'in yaklaşık seri-günü paydasını aynı pencere/evrende yeniden hesapla.
    envanter = meta[meta.symbol.isin(semboller)].copy()
    envanter["bar_sayisi"] = envanter.seans_bar_sayilari.map(lambda m: sum(m[g] for g in seanslar))
    seri_gun = _gun_sayisi(df, envanter)
    satir = ["# Alarm politikası: aynı örneklemde eski ve düzeltilmiş ölçüm", "",
             f"{seanslar[0]} – {seanslar[-1]} · {len(seanslar)} ortak İstanbul seansı · "
             f"{len(semboller)}/{len(set(aktif))} aktif sembol × 4 native zaman dilimi.",
             "Arşiv dışında: " + (", ".join(sorted(set(aktif)-semboller)) or "yok") + ".", "",
             "| Politika | Kart | Eski kart/seri-günü | Kart/seans ort. (medyan) | En yoğun seans | Ölçülen / henüz ölçülemeyen | Yönlü ≥1 ATR eski → yeni | Herhangi yöne ≥1 ATR eski → yeni | Güçlü tetik yakalama |",
             "|---|---:|---:|---:|---|---:|---:|---:|---:|"]
    def yuzde(oran):
        return _f(100 * oran, 1) + "%" if math.isfinite(oran) else "—"

    for r in tablo:
        satir.append(f"| {r['kod']} | {r['n']} | {_f(r['n']/seri_gun)} | {_f(r['gunluk'])} ({_f(r['tipik'],1)}) | "
                     f"{r['zirve']} ({r['zirve_gun']}) | {r['olculen']} / {r['eksik']} | "
                     f"{yuzde(r['eski_hareket'])} → {yuzde(r['hareket'])} | {yuzde(r['eski_iki'])} → {yuzde(r['iki'])} | {yuzde(r['hatirlama'])} |")
    satir += ["", "P0: her tetik; P6: mevcut bağlam filtresi. İki hesapta aynı kartlar; filtre eşikleri değişmedi. "
              "Eski yönlü hesap boş sonucu başarısız, eski yönsüz hesap 40 bara kadar uzanımı kullanır. "
              "Yeni ikisi de 12 mum kullanır. Ufku dolmayan kart sıklığa dahil, isabete dahil değil.", "",
              "Güçlü yakalama = gönderilen ≥1,5 ATR yönlü tetik / tüm ölçülen ≥1,5 ATR yönlü tetikler (12 bar). "
              "Cooldown sembol ve periyot başına 6 bar; pencere öncesi geçmiş korunur. Replay'in yönsüz tetikten ürettiği iki yön satırı bağımsız işlem değildir.", "",
              "Seanslar tetiklerden değil, tüm kapsanan serilerde bar gözlenen İstanbul tarihlerinden gelir; sıfır kartlı günler dahildir. "
              "Eski seri-günü ile yeni kanal toplamının birimleri farklıdır. Sayılar potansiyel karttır; canlı teslimat, getiri veya canlıdaki türetilmiş mumların doğrulaması değildir."]
    return "\n".join(satir) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    from config import ACTIVE_STOCKS
    from research.arsiv import arsiv_sembolleri

    p = argparse.ArgumentParser(description="Aktif native evrende P0/P6 karşılaştırması")
    p.add_argument("--cikti", default="var/domain_alarm_replay")
    p.add_argument("--ilk", required=True, type=date.fromisoformat, help="İlk seans YYYY-MM-DD")
    p.add_argument("--son", required=True, type=date.fromisoformat, help="Son seans YYYY-MM-DD")
    p.add_argument("--rapor", default="var/alarm_politika_v2.md")
    p.add_argument("--tum-politikalar", action="store_true", help="P0–P7 tamamını karşılaştır")
    args = p.parse_args(argv)
    kok = Path(args.cikti)
    meta = _oku_meta(kok)
    if meta is None or "seans_bar_sayilari" not in meta:
        p.error("Seans envanteri yok; replay'i yeni bir çıktı dizininde üretin.")
    native = arsiv_sembolleri(native_only=True)
    veri = oku(kok, set(ACTIVE_STOCKS) & set(native))
    metin = rapor(veri, meta, args.ilk.isoformat(), args.son.isoformat(), ACTIVE_STOCKS, native,
                  tum_politikalar=args.tum_politikalar)
    yol = Path(args.rapor)
    if yol.exists() and "<!-- URETILEN:BASLANGIC -->" in yol.read_text(encoding="utf-8"):
        p.error("Bu dosyada elle yazılmış tarihsel analiz var; ayrı bir --rapor yolu seçin.")
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(metin, encoding="utf-8")
    print(metin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
