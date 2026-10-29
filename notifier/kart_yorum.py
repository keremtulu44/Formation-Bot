# -*- coding: utf-8 -*-
"""Kart yorum katmanı — koşullu ◇/dikkat kapıları (S01–S32 araştırma kapısı).

Sözleşme (2026-10-29, kullanıcı onayı):
  * Kart "şu an bu hissede ne var?" der. KAPISI açılan soru satırı üretir;
    kapı kapalıysa hiçbir şey yazılmaz — eski kart birebir gelir.
  * Havuz = 32 sorunun tamamı:
      ◇ yorum kapıları 10 : S15, S04, S11, S10, S16, S17, S21, S13, S31, S19
        (sıra = öncelik sırası),
      · dikkat 8         : S07 > S32 > S26 > S08 > S02 > S14 > S03 > S18
        — her kartta EN FAZLA 1,
      sessiz/RED 7       : S01, S12, S20, S22, S23, S24, S27 — satır üretmez,
      kart-dışı 7        : S05, S06, S09, S25, S28, S29, S30 — bu katmanda
        YOK (S05 stopu besler; S09, S25, S28–S30 ölçüm/denetim işidir).
  * Limit: en fazla 3 ◇ + 1 dikkat. Kapı 3'ü aşarsa öncelik sırası ve
    stok hafızası uygulanır — aynı sembolde üst üste AYNI ◇ gelmez.
  * n ve soru kodu YALNIZ üretim logunda; karta sayı/kod yazılmaz.
  * Dil: açık düz Türkçe — cümle + oran, en sade sayı ("+35 puan").
    Kriptik "+34,9 pp · n=…" biçimi yasaktır.
  * Bu katman yalnız yorum YAZAR: yeni soru/ölçüm/çalıştırma istemez, sayı
    uydurmaz — oranlar araştırma paketinden (2026-10-29 koşusu) kilitlidir.

Kapı alanları canlı payload'da henüz yok → havuzda TANIMLI ama kapalı
(``beklemede``): S07, S32, S26, S02, S03, S18 (dikkat) ve S19 (◇, rol devri
anı — S27'den ayrı: devredilerek kapanan rollerin payı %42). Field'i geldiğinde
kapı tek satırda açılır; dış AI'nın erişimi olmadığı ölçüde doygunluk.

Çalışma zamanı: yalnız ``data["kart_yorum_kapisi"]`` (canlı akış
`_attach_domain_context` yazar) + ``config.TELEGRAM_KART_YORUM`` açıksa çalışır —
testler ve harici çağrılar bu anahtarsız sessizdir.
Her satır ≤300 px (`telegram_measure.genislik`); 268,85 üstünde `_satir`
girintili devamla böler — metin hiç eksilmez, Telegram yerel sarımı olmaz.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger("notifier.kart_yorum")

MAKS_YORUM = 3          # her kartta en fazla 3 ◇
MAKS_DIKKAT = 1         # her kartta en fazla 1 dikkat
HAFIZA = 8              # sembol başına hatırlanan son ◇ sayısı
HAFIZA_TEKRAR = 2       # son N kartta gösterilen ◇ yeniden gelmez

# S31 — "sonuçları gruba göre 16 puan sapıyor" kapısının açıldığı semboller
# (2026-10-29 koşusu: puan sapması en yüksek semboller; sembol listesi
# araştırma paketine kilitli, kartta sayılmaz).
S31_SEMBOLLER = frozenset({
    "GSRAY", "ASELS", "SISE", "SASA", "XU100", "ANSGR",
    "OFSYM", "AVPGY", "AKFGY", "IHEVA",
})

# ── yardımcılar ─────────────────────────────────────────────────────────────

def _bolum_metni(bolumler: Dict, anahtar: str) -> str:
    parcalar = bolumler.get(anahtar) or []
    if not isinstance(parcalar, (list, tuple)):
        return ""
    return " ".join(str(x) for x in parcalar).lower()


def _temas(data: Dict) -> int | None:
    degerler = []
    for alan in ("upper_touches", "lower_touches"):
        v = data.get(alan)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            degerler.append(int(v))
    return max(degerler) if degerler else None


def _yas(data: Dict) -> int | None:
    v = data.get("age_bars")
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _yon(data: Dict) -> int:
    try:
        return int(data.get("break_dir") or 0)
    except (TypeError, ValueError):
        return 0


def _yon_uyumlu(metin: str, yon: int) -> bool:
    """Hacimjudgmentinin yönü, kırılım yönüyle aynı mı (S11 kapısı)."""
    if "yukarı" in metin:
        return yon >= 0
    if "aşağı" in metin:
        return yon <= 0
    return True  # yönsüz yargı ("destek korunuyor") her iki tarafta da geçerli


# ── ◇ YORUM KAPILARI (sıra = öncelik) ──────────────────────────────────────

def _k_s15(_d: Dict, ctx: Dict) -> bool:
    # İkinci gelişte tutma (S15): temas ≥2 + bölge OB (FVG'de fark RED).
    return (ctx["temas"] or 0) >= 2 and "ob" in ctx["zone"]


def _k_s04(_d: Dict, ctx: Dict) -> bool:
    # Sürtünme/vakit (S04): bölge ≥6 bar üzerinde — yeni <3 kadarda değil.
    yas = ctx["yas"]
    return yas is not None and yas >= 6


def _k_s11(_d: Dict, ctx: Dict) -> bool:
    # Hacim baskısı bu yönde (S11): yargı ile kırılım yönü uyumlu.
    return ("korunuyor" in ctx["hacim"] or "destekliyor" in ctx["hacim"]
            or "teyitli" in ctx["hacim"]) and _yon_uyumlu(ctx["hacim"], ctx["yon"])


def _k_s10(_d: Dict, ctx: Dict) -> bool:
    # OB + zayıf katılım (S10): efor var ama ilerleme zayıf → OB'de geride.
    return "ob" in ctx["zone"] and "zayıf" in ctx["hacim"]


def _k_s16(_d: Dict, ctx: Dict) -> bool:
    # Bant/rol yaşı yüksek → korumada önde (S16). Kapı, bandın canlı yaşı
    # (age_bars ≥21) ile kurulur; ölçütün resmi kovaları 1-5/6-10/11-20/≥21
    # ve en uç kova ≥21'dir.
    yas = ctx["yas"]
    return yas is not None and yas >= 21


def _k_s17(_d: Dict, ctx: Dict) -> bool:
    # Belirgin bölge/engel var → korumada önde (S17).
    return bool(ctx["engel"].strip())


def _k_s21(_d: Dict, ctx: Dict) -> bool:
    # Verimli dönem → roller korunaklı (S11 ailesi gibi katılımdan okunur).
    return "destek korunuyor" in ctx["hacim"] or "destekliyor" in ctx["hacim"]


def _k_s13(_d: Dict, ctx: Dict) -> bool:
    # TF=1h hücresi (S13): OB'de tutma saatlikte 6 puan oynuyor.
    return ctx["tf"] == "1h" and "ob" in ctx["zone"]


def _k_s31(d: Dict, ctx: Dict) -> bool:
    # Sembol ekstremleri (S31): listedeki sembole özel sapma.
    stok = str(d.get("stock_name") or "").strip().upper()
    return stok in S31_SEMBOLLER


def _k_s19(_d: Dict, ctx: Dict) -> bool:
    return False  # beklemede: rol devri anı için payload alanı yok (S27 ayrı)


# ── · DİKKAT KAPILARI (sıra = öncelik; her kartta en fazla 1) ───────────────

def _k_s07(_d: Dict, ctx: Dict) -> bool:
    return False  # beklemede: "bölge ilk temasta kapandı" verisi yok


def _k_s32(_d: Dict, ctx: Dict) -> bool:
    return False  # beklemede: hacimsiz bar payı payload'da yok


def _k_s26(_d: Dict, ctx: Dict) -> bool:
    return False  # beklemede: reaksiyon ilk barda kapanır (1-2 bar)


def _k_s08(_d: Dict, ctx: Dict) -> bool:
    # FVG hedefi bölge kapandıktan sonra (S08): FVG mevcut ve uygun aile.
    return "fvg" in ctx["zone"]


def _k_s02(_d: Dict, ctx: Dict) -> bool:
    return False  # beklemede: rejim (atr_at_touch) ayrımı payload'da yok


def _k_s14(_d: Dict, ctx: Dict) -> bool:
    # Ölçüm güveni (S14): hacim verisi bu bölgede eksik — kartta tek dikkat.
    return "yok" in ctx["hacim"]


def _k_s03(_d: Dict, ctx: Dict) -> bool:
    return False  # beklemede: sıra-korelasyon güveni (r/sr) payload'da yok


def _k_s18(_d: Dict, ctx: Dict) -> bool:
    return False  # beklemede: 3-5 bar reaksiyon ayrımı (age ≤5) için ayrı alan


# ── kayıtlar (sıra = öncelik) ───────────────────────────────────────────────
# `log` üretim loguna gömülü not (kod + n); karta asla basılmaz.

YORUMLAR = (
    {"kod": "S15", "satir": "◇ İkinci gelişte tutma 35 puan fazla",
     "gate": _k_s15, "log": "S15 n=29.283 vs 7.991 OB"},
    {"kod": "S04", "satir": "◇ Eski bölgede tutma 21 puan fazla",
     "gate": _k_s04, "log": "S04 n=45.857"},
    {"kod": "S11", "satir": "◇ Yönlü baskıda tutma 19 puan fazla",
     "gate": _k_s11, "log": "S11 n=149.676"},
    {"kod": "S10", "satir": "◇ Zayıf OB'de tutma 34 puan düşük",
     "gate": _k_s10, "log": "S10 n=15.968"},
    {"kod": "S16", "satir": "◇ Uzun duran seviye 15 puan önde",
     "gate": _k_s16, "log": "S16 n=9.321 vs 10.230"},
    {"kod": "S17", "satir": "◇ Belirgin bölgede koruma 14 fazla",
     "gate": _k_s17, "log": "S17 n=4.727"},
    {"kod": "S21", "satir": "◇ Verimli dönemde roller 12 fazla",
     "gate": _k_s21, "log": "S21 n=117.927"},
    {"kod": "S13", "satir": "◇ Saatlik OB tutması 6 puan fazla",
     "gate": _k_s13, "log": "S13 saatlik 85,9 vs 79,8"},
    {"kod": "S31", "satir": "◇ Sembol, gruba göre 16 puan saptı",
     "gate": _k_s31, "log": "S31 sapma 16,1 puan"},
    {"kod": "S19", "satir": "◇ Roller %42 devredilerek kapanır",
     "gate": _k_s19, "log": "S19 devir payı %42 — kapı alanı yok (beklemede)"},
)

DIKKATLAR = (
    {"kod": "S07", "satir": "· dikkat: bölge ilk temasta kapandı",
     "gate": _k_s07, "log": "S07 n=36.145 — kapı alanı yok (beklemede)"},
    {"kod": "S32", "satir": "· dikkat: ölçümde hacimsiz mum var",
     "gate": _k_s32, "log": "S32 payı %94,57 — kapı alanı yok (beklemede)"},
    {"kod": "S26", "satir": "· dikkat: hareket ilk barda bitti",
     "gate": _k_s26, "log": "S26 n=114.987 — kapı alanı yok (beklemede)"},
    {"kod": "S08", "satir": "· dikkat: FVG hedefi geç geliyor",
     "gate": _k_s08, "log": "S08 n=8.151"},
    {"kod": "S02", "satir": "· dikkat: rejim farklı, ölçüm farklı",
     "gate": _k_s02, "log": "S02 n=278 — kapı alanı yok (beklemede)"},
    {"kod": "S14", "satir": "· dikkat: hacim verisi eksik",
     "gate": _k_s14, "log": "S14 güven etiketi KISMI/NOT — şekle göre"},
    {"kod": "S03", "satir": "· dikkat: ölçüm güveni düşük",
     "gate": _k_s03, "log": "S03 r/sr eşiği — kapı alanı yok (beklemede)"},
    {"kod": "S18", "satir": "· dikkat: ilk tepki beş barda bitti",
     "gate": _k_s18, "log": "S18 n=34.904 — kapı alanı yok (beklemede)"},
)

# Sembol başına gösterilen son ◇ kodları (üst üste tekrar engeli).
_GOSTERILEN: Dict[str, List[str]] = {}


def sifirla() -> None:
    """Test/duruflama için stok hafızasını temizler."""
    _GOSTERILEN.clear()


def _aktif_mi() -> bool:
    import config
    return bool(getattr(config, "TELEGRAM_KART_YORUM", True))


def sec(data: Any, bolumler: Any) -> Dict[str, Any]:
    """Kapıları tara; açılan ◇ (≤3) ve dikkat (≤1) satırlarını döndürür.

    Döndürür: {"yorum": [satır], "dikkat": str | "", "kodlar": [..],
               "dikkat_kod": str | ""}. Kapı yoksa listeler boş — kart eski
    hâlde kalır. Hata durumunda asla yükselmez (kart yorum katmanı düşmez).
    """
    bos = {"yorum": [], "dikkat": "", "kodlar": [], "dikkat_kod": ""}
    try:
        if not _aktif_mi():
            return bos
        if not isinstance(data, dict) or not data.get("kart_yorum_kapisi"):
            return bos
        state = str(data.get("state") or "").strip().upper()
        if state != "KIRILIM_TEYITLI":
            return bos  # yalnız teyitli kart yorum taşır (güncelleme/eksik diğerleri)
        b = bolumler if isinstance(bolumler, dict) else {}
        ctx = {
            "hacim": _bolum_metni(b, "hacim"),
            "zone": (_bolum_metni(b, "ust") + " " + _bolum_metni(b, "alt")).strip(),
            "engel": _bolum_metni(b, "engel"),
            "temas": _temas(data),
            "yas": _yas(data),
            "yon": _yon(data),
            "tf": str(data.get("timeframe") or "").strip().lower(),
        }
        acik = [kayit for kayit in YORUMLAR if bool(kayit["gate"](data, ctx))]
        # stok hafızası: son N kartta gösterilen ◇ bu kartta gelmez
        stok = str(data.get("stock_name") or "?").upper()
        gecmis = _GOSTERILEN.get(stok, [])
        tazeler = [k for k in acik if k["kod"] not in gecmis[-HAFIZA_TEKRAR:]]
        secilen = tazeler[:MAKS_YORUM]

        dikkat_adaylari = [k for k in DIKKATLAR if bool(k["gate"](data, ctx))]
        dikkat = dikkat_adaylari[0] if dikkat_adaylari else None

        if secilen or dikkat:
            _GOSTERILEN[stok] = (gecmis + [k["kod"] for k in secilen])[-HAFIZA:]
            parcalar = [f"{k['kod']} ({k['log']})" for k in secilen]
            if dikkat:
                parcalar.append(f"dikkat {dikkat['kod']} ({dikkat['log']})")
            logger.info("kart yorumu %s: %s", stok, "; ".join(parcalar))
        return {
            "yorum": [k["satir"] for k in secilen],
            "dikkat": dikkat["satir"] if dikkat else "",
            "kodlar": [k["kod"] for k in secilen],
            "dikkat_kod": dikkat["kod"] if dikkat else "",
        }
    except Exception:  # noqa: BLE001 — yorum katmanı kartı düşürmez
        logger.exception("kart yorumu hatası (sessiz devam)")
        return bos
