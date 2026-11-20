"""Katmanlı alarm KARTI — ölçümün söylediğini yazan, süslemeyen kart.

Bugünkü kart bir "olay bildirimi": tetiklendi, şu kanallar ateşledi, şu seviye.
Ölçüm ise şunu gösteriyor (bkz. ``ALARM_POLITIKA_SONUCLARI.md``):

* Kaç kanalın ateşlediği **değer taşımıyor**; HACIM tek başına %71,6 iken
  HACIM+OB %67,9 — kombinasyon seyreltıyor.
* "Teyit/onay" kelimeleri ölçümle **çelişiyor** (hacimli temaslar daha kötü tepki
  veriyor: Q4 %61,4 < Q1 %66,9).
* Yön iddiası ölçümle çelişiyor: tetiklerin %30,5'i iki yöne de ≥1 ATR görüyor.

Bu modül kartı **yeniden çerçeveler**: seviye iddiası yerine ölçülmüş aralık,
kanal sayısı yerine nadirlik ve bağlam. Metin üretir; göndermez.

Kullanım::

    from research.alarm_karti import kart_metni
    print(kart_metni(aday))

Bu bir **prototip**tir: ``bot/domain_alarm_service.py`` içindeki canlı kart
biçimleyicisi değiştirilmedi. Canlıya almak kullanıcı kararıdır.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

#: Ölçülen taban farkları (pp). Replay'den geliyor; kartta "neden bu kart" sorusunu
#: cevaplamak için yazılır. Sayı değişirse burası da değişmeli — tek kaynak burasıdır.
KANAL_FARK_PP = {
    "HACIM": 7.3,
    "FORMASYON": 2.9,
    "FVG": 2.8,
    "OB": 1.7,
    "CHoCH": 0.9,
    "BOS": -2.0,
}

#: Aynı ölçüm: alarmlı barlar %66,5 · alarmsız barlar %64,1 (yönlü ≥1 ATR, 12 bar).
TABAN = 64.1
TETIK = 66.5

KATMAN_ADI = {
    3: "GRAFİK + KART",
    2: "KART",
    1: "ÖZET",
}


def _t(deger: Any, ondalik: int = 2, isaret: bool = False) -> str:
    try:
        v = float(deger)
    except (TypeError, ValueError, OverflowError):
        return "—"
    kalip = f"{v:+.{ondalik}f}" if isaret else f"{v:.{ondalik}f}"
    return kalip.replace(".", ",")


def katman(aday: Mapping[str, Any]) -> int:
    """Kartın hangi katmanda gideceğini ölçüme göre belirler.

    * 3 → grafik: hacim ≥5× **veya** formasyon eşliği, üstüne seans 09/17.
    * 2 → kart: hacim ≥5× veya formasyon eşliği.
    * 1 → özet: yalnız OB/FVG (tek başına gürültü katmanı).
    """
    kanallar = {str(k) for k in (aday.get("kanallar") or aday.get("reasons") or ())}
    hacim = str(aday.get("hacim_tier") or "") in {"5x", "5×", "10x", "10×"}
    formasyon = any("FORMASYON" in k for k in kanallar)
    guclu = hacim or formasyon
    if not guclu:
        return 1
    try:
        saat = int(aday.get("bagl_seans_saati"))
    except (TypeError, ValueError):
        saat = None
    return 3 if saat in {9, 17} else 2


def nadirlik(aday: Mapping[str, Any]) -> str:
    """Kanalın ölçülmüş katkısını **sayı** olarak yazar; sıfat kullanmaz."""
    kanallar = [str(k) for k in (aday.get("kanallar") or ())]
    if not kanallar:
        return "kanal yok"
    en_iyi = max(kanallar, key=lambda k: KANAL_FARK_PP.get(k.split("_")[0], 0.0))
    anahtar = en_iyi.split("_")[0]
    fark = KANAL_FARK_PP.get(anahtar)
    if fark is None:
        return f"{en_iyi}"
    return f"{anahtar} {_t(fark, 1, isaret=True)} pp"


def kart_metni(aday: Mapping[str, Any], *, koni: Mapping[str, Any] | None = None) -> str:
    """Katmanlı kart metni. ``koni`` verilirse aralık satırı eklenir."""
    k = katman(aday)
    baslik = {"3": "📐", "2": "🔔", "1": "·"}[str(k)]
    kanallar = ", ".join(str(x) for x in (aday.get("kanallar") or ())) or "—"
    satirlar: list[str] = [
        f"{baslik} {aday.get('symbol', '?')} · {aday.get('timeframe', '?')} · {KATMAN_ADI[k]}",
        f"kapanış {_t(aday.get('close_price'))} · ATR {_t(aday.get('atr'))}",
    ]

    # 1) Neden bu kart: kanal sayısı değil, ölçülmüş katkı
    satirlar.append(f"kanal: {kanallar}")

    # 2) Aralık: yön iddiası yok
    if koni:
        def _son(anahtar: str) -> Any:
            deger = koni.get(anahtar)
            if isinstance(deger, (list, tuple)):
                return deger[-1] if deger else None
            return deger

        satirlar.append(
            f"12 bar medyan: +{_t(_son('yuk_med'))} / −{_t(_son('asg_med'))} ATR "
            f"(%80: +{_t(_son('yuk_p80'))} / −{_t(_son('asg_p80'))})"
        )
        satirlar.append("yön yok — iki yöne de açık")
    else:
        satirlar.append(f"tarihsel: tetik %{_t(TETIK, 1)} vs taban %{_t(TABAN, 1)}")

    # 3) Bağlam: sıfat değil ölçü
    baglam = []
    for anahtar, etiket in (
        ("bagl_sikisma", "sıkışma"),
        ("bagl_gunici_kosu", "koşu"),
        ("bagl_atr_yuzdelik", "ATR%"),
    ):
        if aday.get(anahtar) is not None:
            isaret = anahtar == "bagl_gunici_kosu"
            ondalik = 0 if anahtar == "bagl_atr_yuzdelik" else 2
            baglam.append(f"{etiket} {_t(aday[anahtar], ondalik, isaret)}")
    if baglam:
        satirlar.append(" · ".join(baglam))

    # 4) Tekrar: kanal ailesine göre davranış
    temas = aday.get("temas")
    if temas:
        satirlar.append(f"{temas}. temas (2. iyi · 3.+ tükenmiş)")

    satirlar.append("ölçüm: yön değil, oynaklık")
    return "\n".join(satirlar)


def ozet_metni(adaylar: Sequence[Mapping[str, Any]], *, gun: str = "") -> str:
    """Katman 1 — günlük tek özet. Kart başına bir satır, en fazla 12 satır."""
    if not adaylar:
        return ""
    sirali = sorted(adaylar, key=lambda a: -max(
        (KANAL_FARK_PP.get(str(k).split("_")[0], 0.0) for k in (a.get("kanallar") or ())),
        default=0.0,
    ))
    satirlar = [f"📋 Günlük özet{(' · ' + gun) if gun else ''} ({len(sirali)} sembol)"]
    for a in sirali[:12]:
        kanal = nadirlik(a)
        satirlar.append(f"· {a.get('symbol', '?')} {a.get('timeframe', '')} — {kanal}")
    if len(sirali) > 12:
        satirlar.append(f"… +{len(sirali) - 12}")
    return "\n".join(satirlar)
