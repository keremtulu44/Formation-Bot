# -*- coding: utf-8 -*-
"""Devamlılık puanı — formasyonun rastgele girişe göre fazlası.

Bu modül **saf hesap**: dosya okumaz, ağa çıkmaz, motora dokunmaz, hiçbir
kartı değiştirmez. Girdi üç bilgi, çıktı tek sayı.

NEDEN VAR
---------
Eski "formasyon kalitesi" (confidence_score) ölçüldü ve sonucu öngörmediği
görüldü: kovalar arasında fark 2 puandan az, tekdüze değil, bileşenleri
(olgunluk +4,1 / daralma −4,0) birbirini götürüyor. Kartta %76 görünen sayı,
ölçülen devam %36,1 idi. Ayrıntı: docs/arastirma/FAZLA_ANALIZI_2026-10-25.md

Yeni puan, eşleştirilmiş fazlayı ölçer:

    fazla = formasyon sonucu − (aynı sembol × TF × ay × yönde rastgele giriş)

Üç madde, hepsi ölçülmüş (7 etiket varyantı, S/Z bölmeleri, 176 sembol):

    aile           kama +4,1 · üçgen −1,9            (fark +6,1; GA +4,5…+7,8)
    aile × trend   kama & MTF4 ek +6,2               (üçgende etki yok)
    mesafe         ≤0,3 ATR +2,0 · 0,3–1 +1,0 · 1–2 0 · >2 −1,5

Her madde, **doğrulanma gücüne göre sıfıra doğru küçültülür** (KUCULTME).
Küçültme katsayıları veriye bakmadan yazıldı; dayanak doğrulama sütunu:

    aile       7/7 varyant · 6/6 bölme · 176 sembol · aynı hücrede +6,4 → 1,00
    mesafe     2/2 aile · S/Z aynı yön · 7/7 varyant                    → 0,85
    etkileşim  7/7 varyant, ama kapsam %6,8 ve MTF geçen turda hayalet  → 0,60

ÖLÇEK
-----
    50 = aynı yerde rastgele girmekle aynı
    95 = ölçülmüş en iyi hücre (kama + MTF4 + yakın giriş)
    100 yok: kimse 100 alamaz, çünkü 100 "kesin" demek olurdu.

Bu bir olasılık DEĞİLDİR. 89 puan "%89 devam" demek değil; o hücrede ölçülen
ham devam %47,1, taban %36,7 idi. Puan yalnızca *göreli* eğilim söyler.

KULLANIM
--------
    >>> devamlilik_puani("Kama", mtf_uyum=4, bant_mesafe_atr=0.2)
    95
    >>> kart_satiri("Kama", mtf_uyum=2, bant_mesafe_atr=0.7)
    'Devamlılık: iyi · 75/100'

KAPSAM DIŞI
-----------
Bayrak ve Flama aileleri arşivde 20 gözlem; ölçüm için yetersiz. Bu ailelerde
fonksiyon `None` döner ve kart satırı **yazılmaz** — uydurma bir sayı
göstermektense hiç göstermemek doğru. Yeterli gözlem birikince ölçülüp eklenir.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

# --- ölçülmüş ham etkiler (puan cinsinden) ----------------------------------
AILE_ETKI = {"Kama": 4.1, "Üçgen": -1.9}
KAPSAM_DISI_AILE = ("Bayrak", "Flama")

#: aile → (MTF eşiği, ek etki). Yalnız kamada ölçüldü; üçgende etki yok.
ETKILESIM = {"Kama": (4, 6.2)}

#: mesafe üst sınırı (ATR) → etki. Sıra önemli: ilk uyan kazanır.
MESAFE_ETKI: Tuple[Tuple[float, float], ...] = ((0.3, 2.0), (1.0, 1.0), (2.0, 0.0))
MESAFE_UZAK = -1.5

#: doğrulanma gücüne göre küçültme
KUCULTME = {"aile": 1.00, "etkilesim": 0.60, "mesafe": 0.85}

# --- ölçek -------------------------------------------------------------------
TABAN = 50.0
OLCEK = 5.0
PUAN_MIN, PUAN_MAX = 5, 95

#: (alt sınır, bant adı) — yüksekten aşağıya
BANTLAR: Tuple[Tuple[int, str], ...] = ((85, "yüksek"), (65, "iyi"), (45, "normal"), (0, "zayıf"))


def aile_coz(ad: Optional[str]) -> Optional[str]:
    """'Yükselen Kama' / 'Alçalan Üçgen' / 'Kama' → 'Kama' | 'Üçgen'.

    Kapsam dışı aile (Bayrak/Flama) ve boş değer için `None`.
    """
    if not ad:
        return None
    metin = str(ad).strip()
    for aile in AILE_ETKI:
        if aile.lower() in metin.lower():
            return aile
    return None


def mesafe_ham(bant_mesafe_atr: Optional[float]) -> float:
    """Girişin banda uzaklığı → ham etki (küçültme öncesi)."""
    try:
        x = float(bant_mesafe_atr)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if x != x:  # NaN
        return 0.0
    for ust, etki in MESAFE_ETKI:
        if x <= ust:
            return etki
    return MESAFE_UZAK


def _mtf_deger(mtf_uyum: Optional[float]) -> float:
    try:
        x = float(mtf_uyum)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return x if x == x else 0.0


def toplam_etki(aile: Optional[str],
                mtf_uyum: Optional[float] = None,
                bant_mesafe_atr: Optional[float] = None) -> Optional[float]:
    """Üç maddenin küçültülmüş toplamı (puan). Kapsam dışı ailede `None`."""
    a = aile_coz(aile)
    if a is None:
        return None
    toplam = AILE_ETKI[a] * KUCULTME["aile"]

    esik_etki = ETKILESIM.get(a)
    if esik_etki is not None and _mtf_deger(mtf_uyum) >= esik_etki[0]:
        toplam += esik_etki[1] * KUCULTME["etkilesim"]

    toplam += mesafe_ham(bant_mesafe_atr) * KUCULTME["mesafe"]
    return toplam


def devamlilik_puani(aile: Optional[str],
                     mtf_uyum: Optional[float] = None,
                     bant_mesafe_atr: Optional[float] = None) -> Optional[int]:
    """0–100 ölçeğinde tam sayı; kapsam dışı ailede `None`."""
    toplam = toplam_etki(aile, mtf_uyum, bant_mesafe_atr)
    if toplam is None:
        return None
    puan = TABAN + OLCEK * toplam
    puan = max(PUAN_MIN, min(PUAN_MAX, puan))
    return int(puan + 0.5) if puan >= 0 else -int(-puan + 0.5)


def bant(puan: Optional[int]) -> str:
    """Puan → sözel bant. Kapsam dışı için boş dize."""
    if puan is None:
        return ""
    for alt, ad in BANTLAR:
        if puan >= alt:
            return ad
    return "zayıf"


def gerekce(aile: Optional[str],
            mtf_uyum: Optional[float] = None,
            bant_mesafe_atr: Optional[float] = None) -> List[str]:
    """Kart için en fazla üç parçalık gerekçe (yalnız puanı gerçekten etkileyen).

    Parçalar uydurulmaz: her biri ya puanı yükseltir ya düşürür.
    """
    a = aile_coz(aile)
    if a is None:
        return []
    parca: List[str] = ["kama" if a == "Kama" else "üçgen"]

    esik_etki = ETKILESIM.get(a)
    if esik_etki is not None and _mtf_deger(mtf_uyum) >= esik_etki[0]:
        parca.append("trend uyumlu")
    elif esik_etki is not None:
        parca.append("trend zayıf")

    try:
        m = float(bant_mesafe_atr)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        m = None  # type: ignore[assignment]
    if m is not None and m == m:
        if m <= 0.3:
            parca.append("giriş seviyeye yakın")
        elif m > 2.0:
            parca.append("giriş seviyeden uzak")
    return parca


def kart_satiri(aile: Optional[str],
                mtf_uyum: Optional[float] = None,
                bant_mesafe_atr: Optional[float] = None) -> str:
    """Tek satır kullanıcı bilgisi. Kapsam dışı ailede boş dize (satır yok).

    Örnek: ``Devamlılık: iyi · 75/100``
    """
    p = devamlilik_puani(aile, mtf_uyum, bant_mesafe_atr)
    if p is None:
        return ""
    return f"Devamlılık: {bant(p)} · {p}/100"


def kart_gerekcesi(aile: Optional[str],
                   mtf_uyum: Optional[float] = None,
                   bant_mesafe_atr: Optional[float] = None) -> str:
    """İkinci (isteğe bağlı) satır: ``kama · trend uyumlu · giriş seviyeye yakın``."""
    return " · ".join(gerekce(aile, mtf_uyum, bant_mesafe_atr))
