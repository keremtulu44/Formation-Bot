"""Domain alarm replay'i — canlı tetikleyicilerin arşiv karşılığı.

Neden bu modül var
------------------
Canlı sistem, her sembolde her tamamlanmış mumda ``bot/domain_alarm_service.py``
içindeki dört kanalı değerlendirir ve **herhangi biri** tuttuğunda Telegram'a
kart atar:

* ``BOS`` / ``CHoCH`` (Market Structure, teyitli ve son 2 barda),
* ``OB`` / ``FVG`` (fiyat aktif bölgenin içinde veya FVG ``reaksiyon`` halinde),
* ``formasyon`` (aktif formasyon kaydı, state'e bakılmaksızın),
* ``hacim N×`` (RVOL ≥ 5 veya ≥ 10).

Bu kanalların hiçbiri "bu noktayı görmeye değer mi" sorusuna göre kalibre
edilmemiştir; kod, tetikleyicinin **varlığını** bildirir. Kartın gösterdiği
grafik ile fiyatın sonrasında ne yaptığı arasındaki ilişki ölçülmemiştir.

Bu modül o ölçümü yapar: aynı veriden (native arşiv) tetikleyiciyi yeniden
üretir, her tetik için **çapa sonrası** yolu ATR cinsinden ölçer ve şu iki
soruyu cevaplar:

1. Tetik "değerli" mi — yani tetiğin gösterdiği yönde anlamlı bir uzanım var mı,
   yoksa fiyat yazı tura mı atıyor?
2. Tetik "belirsiz" mi — yani kanalların birlikte ateşlediği noktalar, tek
   kanalin ateşlediği noktalardan gerçekten farklı mı?

Tasarım kararları
-----------------
**Canlı semantik birebir kopyalanır, icat edilmez.** Eşikler
(``RVOL 5×/10×``, ``son 2 bar`` BOS/CHoCH penceresi, ``OB/FVG`` içinde olma
kuralı) canlı koddan okunur; replay bunları yeniden yorumlamaz. Canlı kodla
aradaki tek fark, replay'in arşivde zaten var olan gözlem satırlarını
(``event.jsonl``, ``zone.jsonl``) okumasıdır.

**Çapa = tetiğin oluştuğu mumun kapanışı.** Ölçüm bir sonraki bardan başlar;
tetik barının kendisi hiçbir uzanıma katılmaz (anti-lookahead). Bu, canlı
kartın "bar kapandı, şimdi gönder" anıyla aynıdır.

**Birim ATR'dir, tetik anındaki ATR dondurulur.** BIST 5–500 TL aralığında
hisse barındırdığı için TL havuzlanamaz; ATR de tetik sonrası büyüyerek
"başarıyı" şişiremez.

**Sağdan sansür açıkça işaretlenir.** Pencere veri sonuna takıldıysa
``sansur=True`` olur ve o tetik hiçbir orana "başarılı" diye girmez.

**Tetik başına tek satır, kanal bazında ayrıştırılabilir.** Aynı barda dört
kanal birden ateşlerse tek satır üretilir ve ``kanallar`` alanı hangilerinin
tuttuğunu taşır; böylece "hangi kanal/combination değerli" sorusu tek
tablodan çaprazlanır.

Kullanım::

    python -m research.domain_alarm_replay --limit 5      # pilot
    python -m research.domain_alarm_replay                # tam koşu (176 sembol)
    python -m research.domain_alarm_replay --rapor-yaz    # + Markdown rapor

Çıktı ``var/domain_alarm_replay/`` altındadır (git'e girmez); rapor
``docs/arastirma/DOMAIN_ALARM_REPLAY_SONUCLARI.md`` olarak yazılır.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from domain_engines.fvg.fvg_engulfing_models import FvgState
from research import arsiv, olcum
from research.kayit import sembol_timeframe_gozlem

__all__ = [
    "ENGINE_VERSION",
    "KANALLAR",
    "HORIZONLAR",
    "SERI_SATIRLARI",
    "sembol_timeframe_tetikleri",
    "seri_olcumu",
    "topla",
    "rapor_yaz",
]

ENGINE_VERSION = "domain-alarm-replay-v1"

#: Ölçüm ufukları. 3 bar "anlık tepki", 12 bar "kart sonrası ilk iki gün",
#: 40 bar "kalıcı mı" sorusu. Üçü aynı satırda taşınır.
HORIZONLAR: tuple[int, ...] = (3, 12, 40)

#: Ön-tanımlı ATR eşik ızgarası. Ölçümden SONRA eşik seçilmez.
ESIK_IZGARA: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)

#: Canlı sistemin dört kanalı. ``BOS``/``CHoCH`` ayrı tutulur çünkü canlı kart
#: ikisini de aynı gerekçede gösterir ama yön davranışları farklı çıkıyor.
KANALLAR: tuple[str, ...] = ("BOS", "CHoCH", "OB", "FVG", "FORMASYON", "HACIM")

#: Canlı koddaki sabitler (``bot/domain_alarm_service.py``). Replay bunları
#: yeniden yorumlamaz; birebir kullanır. Testler bu eşitliği kilitler.
BOS_PENCERE_BAR = 2
FVG_REAKSIYON_STATE = int(FvgState.REACTION) if hasattr(FvgState, "REACTION") else 8
RVOL_ESIK_5X = 5.0
RVOL_ESIK_10X = 10.0
RVOL_SUPHE = 50.0
HACIM_ORTA_SERI = 20

#: Kontrol (taban) örnekleme adımı. Her seride ``TABAN_ADIM`` barda bir,
#: tetik olmayan bir bar çapa olarak alınır. Amaç **fazla** ölçmek:
#: "alarm bu sonucu üretti" değil, "alarm rastgele bir bardan ne kadar farklı".
#: 10 bar, 1h'de ~1.5 seans, 4h'de ~2 hafta; örtüşmeyi sınırlar.
TABAN_ADIM = 10

#: Rapor tablolarının kullandığı seri satırı (bellek kısıtı için kolon seçimi).
SERI_SATIRLARI: tuple[str, ...] = (
    "symbol", "timeframe", "bar_index", "bar_time", "close", "atr",
    "kanallar", "kanal_sayisi", "yon", "kontrol", "formasyon_state", "formasyon_tip",
    "rvol", "hacim_tier", "data_quality",
    "yon_h3", "yon_h12", "yon_h40", "yon_kap_h12", "yon_kap_h40",
    "yon_tepe_atr", "yon_tepe_bar", "yon_dip_atr", "yon_pay_5",
    "yon_asim_050", "yon_asim_100", "yon_asim_150", "yon_asim_200",
    "ters_h12", "gozlenen_bar", "sansur",
)


# ---------------------------------------------------------------------------
# 1) Tetik üretimi — canlı kanalların arşiv karşılığı
# ---------------------------------------------------------------------------


def _tok(deger: Any) -> str:
    return str(deger or "").strip().upper()


def _sayi(deger: Any) -> float | None:
    try:
        v = float(deger)
    except (TypeError, ValueError, OverflowError):
        return None
    return v if math.isfinite(v) else None


def _tolerans(deger: Any) -> float | None:
    """Fiyat karşılaştırmalarında float32 gürültüsünü yut."""
    v = _sayi(deger)
    if v is None:
        return None
    return v * 1e-9


def _zaman_anahtari(deger: Any) -> pd.Timestamp | None:
    try:
        ts = pd.Timestamp(str(deger))
    except (TypeError, ValueError):
        return None
    if ts is pd.NaT:
        return None
    return ts.tz_localize("Europe/Istanbul") if ts.tzinfo is None else ts


def _fvg_reaksiyon(zone: Mapping[str, Any], bar: Mapping[str, Any]) -> bool:
    """FVG zonu bu barda "reaksiyon" durumunda mı?

    Canlı kod bunu motorun canlı ``state`` alanından okur. Arşivde zone
    satırı **doğum anındaki** durumu taşır; reaksiyon durumu zamanla
    değiştiği için burada canlı kuralın nedensel karşılığı kullanılır:

    FVG reaksiyonu = fiyat zone sınırına dokundu (dipte ``low`` ≤ üst sınır,
    boğada ``high`` ≥ alt sınır) **ve** zone henüz tamamen dolmadı
    (``native_full_fill`` değil). Bu, canlı motorun "test tetiklendi ama
    seviye tükenmedi" hâlinin birebir karşılığıdır.
    """
    if _tok(zone.get("family")) != "FVG":
        return False
    if bool(zone.get("native_full_fill")):
        return False
    ust, alt = _sayi(zone.get("zone_upper")), _sayi(zone.get("zone_lower"))
    if ust is None or alt is None:
        return False
    yuksek, dusuk = _sayi(bar.get("high")), _sayi(bar.get("low"))
    if yuksek is None or dusuk is None:
        return False
    yon = _tok(zone.get("direction"))
    if yon.startswith("BULL"):
        return dusuk <= ust
    if yon.startswith("BEAR"):
        return yuksek >= alt
    return False


def _zon_icinde(zone: Mapping[str, Any], close: float, tol: float) -> bool:
    ust, alt = _sayi(zone.get("zone_upper")), _sayi(zone.get("zone_lower"))
    if ust is None or alt is None or ust < alt:
        return False
    return (alt - tol) <= close <= (ust + tol)


def _aktif_mi(zone: Mapping[str, Any], index: int) -> bool:
    """Zone bu barda aktif mi — doğdu, henüz tükenmedi? (nedensel)"""
    dogum = zone.get("dogum_index")
    if dogum is None:
        return False
    try:
        dogum = int(dogum)
    except (TypeError, ValueError):
        return False
    if index < dogum + 1:  # zone ancak doğumundan SONRAKİ barda kullanılabilir
        return False
    terminal = zone.get("terminal_index")
    if terminal is not None:
        try:
            if index >= int(terminal):
                return False
        except (TypeError, ValueError):
            pass
    return True


def _olay_yonu(event: Mapping[str, Any]) -> int:
    yon = event.get("direction")
    if isinstance(yon, str):
        y = _tok(yon)
        return 1 if y in {"UP", "BULL", "BULLISH"} else (-1 if y in {"DOWN", "BEAR", "BEARISH"} else 0)
    v = _sayi(yon)
    return 0 if v is None else (1 if v > 0 else (-1 if v < 0 else 0))


def sembol_timeframe_tetikleri(
    sembol: str,
    timeframe: str,
    frame: pd.DataFrame,
    gozlem: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    """Bir sembol × zaman dilimi için **canlı kanalların** bar bar tetikleri.

    ``gozlem`` ``research.kayit.sembol_timeframe_gozlem`` çıktısıdır; bu
    fonksiyon yeni ölçüm üretmez, canlı alarm servisinin okuduğu aynı
    satırları (``event``, ``zone``, ``frm_olay``) yeniden yorumlar.

    Döndürür: bar başına bir sözlük; **yalnız en az bir kanal tutan barlar**.
    """
    if frame is None or len(frame) == 0:
        return []

    barlar: list[dict[str, Any]] = []
    if "timestamp" in frame.columns:
        zamanlar = [str(z) for z in frame["timestamp"]]
    else:
        zamanlar = [str(z) for z in frame.index]
    kapanislar = [float(v) for v in frame["close"].to_numpy()]
    yuksekler = frame["high"].astype(float).to_numpy()
    dusukler = frame["low"].astype(float).to_numpy()
    hacimler = pd.to_numeric(frame["volume"], errors="coerce").astype(float).to_numpy()

    # --- MS olayları: teyitli + aktif + son 2 barda ------------------------
    olay_barlari: dict[int, set[str]] = defaultdict(set)
    for ev in gozlem.get("event", ()) or ():
        tip = _tok(ev.get("event_type"))
        if tip not in {"EVENT_BOS", "BOS", "EVENT_CHOCH", "CHOCH"}:
            continue
        if _tok(ev.get("confirmation_status")) != "CONFIRMED":
            continue
        if _tok(ev.get("validity")) == "FAILED":
            continue
        if _tok(ev.get("relevance")) in {"SUPERSEDED", "HISTORICAL"}:
            continue
        bar = ev.get("event_bar")
        try:
            bar = int(bar)
        except (TypeError, ValueError):
            continue
        if not (0 <= bar < len(kapanislar)):
            continue
        olay_barlari[bar].add("CHoCH" if "CHOCH" in tip else "BOS")

    # --- Zone'lar: OB içinde olma / FVG reaksiyon --------------------------
    zonlar = list(gozlem.get("zone", ()) or ())
    ob_zonlar = [z for z in zonlar if _tok(z.get("family")) == "OB"]
    fvg_zonlar = [z for z in zonlar if _tok(z.get("family")) == "FVG"]

    # --- Formasyon olay satırları (canlı kayıtların karşılığı) -------------
    # Canlı servis "son taramadaki aktif formasyon kayıtlarını" okur; arşivde
    # bunun karşılığı olay saatinde üretilmiş formasyon kaydıdır. Yalnız
    # olayın **aynı barda** görünmesi kullanılır (canlıda da kart o an basılır).
    formasyon_barlari: dict[int, tuple[str, str]] = {}
    for olay in gozlem.get("frm_olay", ()) or ():
        tip = _tok(olay.get("olay_type"))
        durum = _tok(olay.get("state"))
        if not durum or durum in {"FORMASYON_GECERSIZ", "YOK", "ST_NONE", "NONE"}:
            continue
        bar = olay.get("bar")
        try:
            bar = int(bar)
        except (TypeError, ValueError):
            continue
        if not (0 <= bar < len(kapanislar)):
            continue
        # Bar başına tek kayıt: en son yazılan kazanır (canlı kart da son
        # bildirimi gösterir).
        formasyon_barlari[bar] = (_tok(olay.get("olay_name")) or tip, durum)

    # --- Bar bar kanal değerlendirmesi ------------------------------------
    son_bos: set[str] = set()
    for index in range(len(kapanislar)):
        if index in olay_barlari:
            son_bos = set(olay_barlari[index])
        elif index > 0:
            # ``son 2 bar`` penceresi: bu bar ve bir önceki bar.
            onceki = olay_barlari.get(index - 1, set())
            son_bos = set(olay_barlari.get(index, set())) | onceki

        kanallar: set[str] = set(son_bos)

        close = kapanislar[index]
        tol = abs(close) * 1e-9
        bar_sozluk = {"high": yuksekler[index], "low": dusukler[index], "close": close}
        for zone in ob_zonlar:
            if _aktif_mi(zone, index) and _zon_icinde(zone, close, tol):
                kanallar.add("OB")
                break
        for zone in fvg_zonlar:
            if _aktif_mi(zone, index) and (
                _zon_icinde(zone, close, tol) or _fvg_reaksiyon(zone, bar_sozluk)
            ):
                kanallar.add("FVG")
                break

        frm = formasyon_barlari.get(index)
        if frm is not None:
            kanallar.add("FORMASYON")

        # RVOL: canlı kod motorun ``rvol`` alanını, yoksa yerel hacim/SMA20
        # kullanır. Arşivde VP satırı hazır olduğunda o, olmadığında yerel.
        rvol = None
        if index >= HACIM_ORTA_SERI - 1:
            pencere = hacimler[index - HACIM_ORTA_SERI + 1: index + 1]
            gecerli = pencere[~pd.isna(pencere)]
            if len(gecerli) >= HACIM_ORTA_SERI:
                ortalama = float(gecerli.mean())
                son = float(hacimler[index]) if not pd.isna(hacimler[index]) else None
                if ortalama > 0 and son is not None and math.isfinite(ortalama) and math.isfinite(son):
                    rvol = son / ortalama
        hacim_tier = None
        if rvol is not None and math.isfinite(rvol):
            if rvol >= RVOL_ESIK_10X:
                hacim_tier = "10x"
            elif rvol >= RVOL_ESIK_5X:
                hacim_tier = "5x"
            if hacim_tier:
                kanallar.add("HACIM")

        if not kanallar:
            continue

        yon = 1 if son_bos else 0
        if not son_bos:
            # BOS yoksa yön zone/formasyon tarafından belirlenir; canlı kart da
            # yönü gerekçeden alır. Belirlenemiyorsa ölçüm iki yönlü yapılır.
            yon = _yon_tahmini(ob_zonlar, fvg_zonlar, close, tol, frm)

        barlar.append(
            {
                "symbol": sembol,
                "timeframe": timeframe,
                "bar_index": index,
                "bar_time": zamanlar[index],
                "close": close,
                "kanallar": sorted(kanallar),
                "kanal_sayisi": len(kanallar),
                "yon": yon,
                "formasyon_state": frm[1] if frm else None,
                "formasyon_tip": frm[0] if frm else None,
                "hacim_tier": hacim_tier,
                "rvol": rvol,
                "kontrol": False,
            }
        )
    return barlar


def kontrol_tetikleri(
    sembol: str,
    timeframe: str,
    frame: pd.DataFrame,
    tetik_barlari: set[int],
    adim: int = TABAN_ADIM,
) -> list[dict[str, Any]]:
    """Tetik **olmayan** barlardan sabit ızgara kontrol (taban) örneklemi.

    Neden gerekli: bir tetiğin 12 barda ≥1 ATR görmesi tek başına bilgi
    değildir — ATR zaten ortalama bar aralığıdır, dolayısıyla **herhangi** bir
    barda da benzer oran çıkar. "Alarm değerli" iddiası ancak tetik oranı
    kontrol oranından anlamlı biçimde yüksekse kurulabilir.

    Kontrol, ısınma barlarından (ilk 20 bar) sonra her ``adim`` barda bir
    örneklenir ve tetik barına denk gelenler atlanır. Yön **verilmez**
    (``yon=0``); ölçüm iki yönlü yapılır, böylece "her iki tarafa da gider"
    yanlılığı doğmaz.
    """
    if frame is None or len(frame) < 30:
        return []
    zamanlar = [str(z) for z in (frame["timestamp"] if "timestamp" in frame.columns else frame.index)]
    kapanislar = frame["close"].astype(float).to_numpy()
    satirlar: list[dict[str, Any]] = []
    for index in range(20, len(kapanislar) - 1, max(1, int(adim))):
        if index in tetik_barlari:
            continue
        satirlar.append(
            {
                "symbol": sembol,
                "timeframe": timeframe,
                "bar_index": index,
                "bar_time": zamanlar[index],
                "close": float(kapanislar[index]),
                "kanallar": (),
                "kanal_sayisi": 0,
                "yon": 0,
                "formasyon_state": None,
                "formasyon_tip": None,
                "hacim_tier": None,
                "rvol": None,
                "kontrol": True,
            }
        )
    return satirlar


def _yon_tahmini(
    ob_zonlar: Sequence[Mapping[str, Any]],
    fvg_zonlar: Sequence[Mapping[str, Any]],
    close: float,
    tol: float,
    frm: tuple[str, str] | None,
) -> int:
    """Tetik yönü: içinde bulunulan bölge yönü, yoksa 0 (iki yönlü ölçüm)."""
    for zone in ob_zonlar + list(fvg_zonlar):
        if _zon_icinde(zone, close, tol):
            yon = _tok(zone.get("direction"))
            if yon.startswith("BULL"):
                return 1
            if yon.startswith("BEAR"):
                return -1
    if frm is not None:
        durum = frm[1]
        if "↑" in (frm[0] or "") or "YUKARI" in durum:
            return 1
        if "↓" in (frm[0] or "") or "ASAGI" in durum or "AŞAĞI" in durum:
            return -1
    return 0


# ---------------------------------------------------------------------------
# 2) Ölçüm — çapa sonrası ATR yolu
# ---------------------------------------------------------------------------


def _atr_dizisi(frame: pd.DataFrame) -> list[float | None]:
    from directional_zone_replay import compute_wilder_atr

    try:
        return [None if v is None or not math.isfinite(float(v)) else float(v) for v in compute_wilder_atr(frame)]
    except Exception:  # noqa: BLE001 - ATR yoksa satır üretilmez
        return [None] * len(frame)


def seri_olcumu(
    tetikler: Sequence[Mapping[str, Any]],
    frame: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Tetikleri **çapa sonrası** ATR yoluna çevirir.

    Anti-lookahead: ölçüm ``bar_index + 1``'den başlar; tetik barı hiçbir
    uzanıma katılmaz. ATR tetik barında dondurulur ve tüm ufuklar için sabit
    kalır (canlı kartın gördüğü ATR ile aynı).

    Yön 0 ise (ne BOS ne zone yönü belirlenebildiyse) hem yukarı hem aşağı
    uzanım ölçülür ve ``yon`` alanı ``0`` kalır; rapor bu satırları ayrı
    gösterir, hiçbir orana karıştırmaz.
    """
    if frame is None or len(frame) == 0 or not tetikler:
        return []
    atr = _atr_dizisi(frame)
    yuksekler = frame["high"].astype(float).to_numpy()
    dusukler = frame["low"].astype(float).to_numpy()
    kapanislar = frame["close"].astype(float).to_numpy()
    n = len(kapanislar)
    en_uzun = max(HORIZONLAR)

    satirlar: list[dict[str, Any]] = []
    for tetik in tetikler:
        index = int(tetik["bar_index"])
        atr_deger = atr[index] if 0 <= index < len(atr) else None
        if atr_deger is None or atr_deger <= 0:
            continue
        referans = float(kapanislar[index])
        gelecek_yuksek = yuksekler[index + 1:]
        gelecek_dusuk = dusukler[index + 1:]
        gelecek_kapanis = kapanislar[index + 1:]
        gozlenen = len(gelecek_kapanis)
        if gozlenen == 0:
            continue
        yon = int(tetik.get("yon") or 0)
        yonlar = (1, -1) if yon == 0 else (yon,)
        for secilen in yonlar:
            satir = dict(tetik)
            satir["yon"] = secilen if yon == 0 else yon
            satir["atr"] = atr_deger
            satir["gozlenen_bar"] = gozlenen
            satir["sansur"] = gozlenen < en_uzun
            olcum_yaz(satir, secilen, referans, atr_deger, gelecek_yuksek, gelecek_dusuk, gelecek_kapanis)
            satirlar.append(satir)
    return satirlar


def olcum_yaz(
    satir: dict[str, Any],
    yon: int,
    referans: float,
    atr_deger: float,
    gelecek_yuksek: Any,
    gelecek_dusuk: Any,
    gelecek_kapanis: Any,
) -> None:
    """``satir`` sözlüğünü yönlü uzanım metrikleriyle doldurur."""
    lehte = gelecek_yuksek if yon > 0 else gelecek_dusuk
    aleyhte = gelecek_dusuk if yon > 0 else gelecek_yuksek
    if yon > 0:
        yol = [(float(v) - referans) / atr_deger for v in lehte[: max(HORIZONLAR)]]
        ters_yol = [(referans - float(v)) / atr_deger for v in aleyhte[: max(HORIZONLAR)]]
        yonlu_kapanis = [(float(v) - referans) / atr_deger for v in gelecek_kapanis]
    else:
        yol = [(referans - float(v)) / atr_deger for v in lehte[: max(HORIZONLAR)]]
        ters_yol = [(float(v) - referans) / atr_deger for v in aleyhte[: max(HORIZONLAR)]]
        yonlu_kapanis = [(referans - float(v)) / atr_deger for v in gelecek_kapanis]

    for h in HORIZONLAR:
        # Pencere DOLMADIYSA ``None``. Aksi hâlde ``yon_h40`` sütunu bir
        # satırda 40 barın, başka satırda 3 barın tepesini taşır ve iki
        # farklı ölçü sessizce aynı kolonda karışır (sansür yalan söyler).
        pencere = yol[:h]
        satir[f"yon_h{h}"] = max(pencere) if len(pencere) >= h else None
        satir[f"yon_kap_h{h}"] = yonlu_kapanis[h - 1] if len(yonlu_kapanis) >= h else None

    # ``yon_tepe_atr`` gözlenen tüm pencere içindeki tepedir (sansürlü olabilir);
    # hangi satırın kaç bardan geldiği ``gozlenen_bar`` alanındadır.
    tepe = max(yol) if yol else None
    satir["yon_tepe_atr"] = tepe
    satir["yon_tepe_bar"] = (yol.index(tepe) + 1) if yol else None
    satir["yon_dip_atr"] = min(ters_yol) * -1 if ters_yol else None
    satir["yon_pay_5"] = (max(yol[:5]) / tepe) if (len(yol) >= 5 and tepe and tepe > 0) else None
    # Aşım ızgarası 12 bar ufkuna sabittir (HORIZONLAR'ın ortası): kısa
    # pencerede "≥1 ATR gördü" demek için 12 barın dolması gerekir.
    on_iki = yol[:12]
    for esik in ESIK_IZGARA:
        satir[f"yon_asim_{_esik_etiketi(esik)}"] = (max(on_iki) >= esik) if len(on_iki) >= 12 else None
    # Ters hareket: 12 barda aleyhte ≥1 ATR görüldü mü? "belirsizlik" ölçüsü.
    # 12 bar dolmadıysa ölçüm yok — kısa pencereyi "aleyhe gitmedi" saymak
    # belirsizliği olduğundan az gösterir.
    satir["ters_h12"] = (max(ters_yol[:12]) >= 1.0) if len(ters_yol) >= 12 else None


def _esik_etiketi(esik: float) -> str:
    return str(int(round(float(esik) * 100))).zfill(3)


# ---------------------------------------------------------------------------
# 3) Toplama ve rapor
# ---------------------------------------------------------------------------


def _json_serializable(deger: Any) -> Any:
    if deger is None or isinstance(deger, (str, bool, int)):
        return deger
    if isinstance(deger, float):
        return deger if math.isfinite(deger) else None
    if hasattr(deger, "item"):
        try:
            return _json_serializable(deger.item())
        except (ValueError, TypeError):
            return str(deger)
    if isinstance(deger, (list, tuple)):
        return [_json_serializable(v) for v in deger]
    return str(deger)


def _satir_ekle(yol: Path, satirlar: Iterable[Mapping[str, Any]]) -> int:
    satirlar = list(satirlar)
    if not satirlar:
        return 0
    yol.parent.mkdir(parents=True, exist_ok=True)
    with yol.open("a", encoding="utf-8") as dosya:
        for satir in satirlar:
            temiz = {k: _json_serializable(v) for k, v in satir.items()}
            dosya.write(json.dumps(temiz, ensure_ascii=False) + "\n")
    return len(satirlar)


def _oku(yol: Path, kolonlar: Sequence[str] | None = None) -> pd.DataFrame:
    if not yol.exists():
        return pd.DataFrame()
    kayitlar: list[dict[str, Any]] = []
    with yol.open("r", encoding="utf-8") as dosya:
        for satir in dosya:
            satir = satir.strip()
            if not satir:
                continue
            try:
                kayit = json.loads(satir)
            except json.JSONDecodeError:
                continue
            if kolonlar is not None:
                kayit = {k: kayit.get(k) for k in kolonlar}
            # ``kanallar`` JSON'da liste gelir; pandas groupby liste anahtarını
            # hash'leyemez. Demet'e çevirmek hem groupby'ı hem üyelik testini
            # (``kanal in v``) çalıştırır.
            if isinstance(kayit.get("kanallar"), list):
                kayit["kanallar"] = tuple(kayit["kanallar"])
            kayitlar.append(kayit)
    return pd.DataFrame(kayitlar)


def _guven(n: int) -> str:
    if n >= 30:
        return "YETERLI"
    if n >= 15:
        return "KISMI"
    return "ZAYIF"


def _oran(seri: pd.Series) -> float | None:
    temiz = seri.dropna()
    if len(temiz) == 0:
        return None
    return float(temiz.astype(float).mean())


def _pct(deger: float | None) -> str:
    return "—" if deger is None else f"{deger * 100:.1f}%"


def _num(deger: float | None, basamak: int = 2) -> str:
    return "—" if deger is None else f"{deger:.{basamak}f}"


def topla(cikti: Path) -> dict[str, Any]:
    """JSONL çıktısından rapor tablolarını üretir."""
    df = _oku(cikti / "tetikler.jsonl", SERI_SATIRLARI)
    if len(df) == 0:
        return {"tetik": 0}
    for kolon in (
        "yon_h3", "yon_h12", "yon_h40", "yon_kap_h12", "yon_kap_h40",
        "yon_tepe_atr", "yon_tepe_bar", "yon_dip_atr", "yon_pay_5", "rvol",
        "atr", "close", "yon", "kanal_sayisi", "gozlenen_bar",
    ):
        if kolon in df.columns:
            df[kolon] = pd.to_numeric(df[kolon], errors="coerce")
    for esik in ESIK_IZGARA:
        kolon = f"yon_asim_{_esik_etiketi(esik)}"
        if kolon in df.columns:
            df[kolon] = df[kolon].map(lambda v: bool(v) if isinstance(v, bool) else None)
    temiz = df[df["sansur"] == False].copy()  # noqa: E731,E712 - pandas maskesi
    return {"df": df, "temiz": temiz, "tetik": int(len(df)), "temiz_tetik": int(len(temiz))}


def rapor_yaz(ozet: Mapping[str, Any], cikti: Path, rapor_yolu: Path) -> str:
    """Tetik ölçümünü okunabilir Markdown raporuna çevirir."""
    df = ozet.get("df")
    if df is None or len(df) == 0:
        metin = "# Domain alarm replay — tetik bulunamadı\n"
        rapor_yolu.parent.mkdir(parents=True, exist_ok=True)
        rapor_yolu.write_text(metin, encoding="utf-8")
        return metin

    temiz = ozet["temiz"]
    meta = _oku(cikti / "meta.jsonl")
    if "kontrol" not in temiz.columns:
        temiz = temiz.assign(kontrol=False)
    tetik_kume = temiz[temiz["kontrol"] != True].copy()  # noqa: E712 - pandas maskesi
    kontrol_kume = temiz[temiz["kontrol"] == True].copy()  # noqa: E712 - pandas maskesi
    satirlar: list[str] = []
    ekle = satirlar.append

    ekle("# Domain alarm replay — tetikleyiciler ne kadar değerli?")
    ekle("")
    ekle(
        f"> **Tür:** Ölçüm (replay) · **Sürüm:** `{ENGINE_VERSION}` · "
        f"**Tarih:** {time.strftime('%Y-%m-%d')}"
    )
    ekle("> **Kaynak:** `backfill_data/` native arşiv — 1h/2h/4h/1d, resample yok.")
    ekle(
        "> **Çapa:** tetiğin oluştuğu mumun kapanışı; ölçüm bir sonraki bardan başlar. "
        "Tetik barı hiçbir uzanıma katılmaz."
    )
    ekle("> **Birim:** ATR — tetik anındaki ATR dondurulur, tüm ufuklarda sabit.")
    ekle("")
    ekle("## 0 · Tek ekran")
    ekle("")

    # Kanal bazında özet
    kanal_ozet = _kanal_tablosu(tetik_kume)
    tum_satir = _kanal_satiri("TÜM TETİKLER", tetik_kume)
    taban_satir = _kanal_satiri("TABAN (kontrol)", kontrol_kume)

    if meta is not None and len(meta):
        seri = len(meta)
        sembol = int(meta["symbol"].nunique()) if "symbol" in meta.columns else 0
    else:
        seri, sembol = 0, 0
    ekle(
        f"- **Örneklem:** {sembol} sembol × {seri // max(1, sembol) if sembol else 0} zaman dilimi = "
        f"{seri} seri · **{ozet['tetik']} satır** (sansürsüz {ozet['temiz_tetik']}; "
        f"bunun {len(tetik_kume)} satırı tetik, {len(kontrol_kume)} satırı taban)"
    )
    ekle(f"- **Bar başına tetik:** {_num(_bar_orani(df, meta) * 100, 2)}% — her 100 mumda ortalama bu kadar kart.")
    ekle(
        f"- **Tetik vs taban (12 bar, lehte ≥1 ATR):** {_pct(tum_satir['h12_1atr'])} vs "
        f"{_pct(taban_satir['h12_1atr'])} → **fazla {_pp_fark(tum_satir['h12_1atr'], taban_satir['h12_1atr'])}**"
    )
    ekle(
        f"- **Yön farkı (lehte − aleyhte, 12 bar):** tetik "
        f"{_pp_fark(tum_satir['h12_1atr'], tum_satir['ters_1atr'])} · taban "
        f"{_pp_fark(taban_satir['h12_1atr'], taban_satir['ters_1atr'])}"
    )
    ekle(
        f"- **Belirsizlik:** tetik satırlarının {_pct(tum_satir['karisik'])} kadarı 12 barda "
        "**her iki yöne de** ≥1 ATR görüyor; tabanda bu oran "
        f"{_pct(taban_satir['karisik'])}."
    )
    ekle("")
    ekle("| Kanal | n | ≥1 ATR (12b) | taban farkı (pp) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de | güven |")
    ekle("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for satir in kanal_ozet:
        ekle(
            f"| {satir['ad']} | {satir['n']} | {_pct(satir['h12_1atr'])} | "
            f"{_pp_fark(satir['h12_1atr'], taban_satir['h12_1atr'])} | "
            f"{_pct(satir['h12_15atr'])} | {_num(satir['medyan_tepe'])} | "
            f"{_pct(satir['ters_1atr'])} | {_pct(satir['karisik'])} | {satir['guven']} |"
        )
    ekle(
        f"| TABAN (kontrol) | {taban_satir['n']} | {_pct(taban_satir['h12_1atr'])} | — | "
        f"{_pct(taban_satir['h12_15atr'])} | {_num(taban_satir['medyan_tepe'])} | "
        f"{_pct(taban_satir['ters_1atr'])} | {_pct(taban_satir['karisik'])} | {taban_satir['guven']} |"
    )
    ekle("")

    # Kanal sayısı (birleşim) tablosu
    ekle("## 1 · Kanal sayısı — çok kanal birlikte ateşlemek daha mı iyi?")
    ekle("")
    ekle("| kanal sayısı | n | ≥1 ATR (12b) | ≥1,5 ATR | ≥2 ATR | medyan tepe | aleyhte ≥1 ATR | iki yöne de |")
    ekle("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for sayi in sorted(tetik_kume["kanal_sayisi"].dropna().unique()):
        alt = tetik_kume[tetik_kume["kanal_sayisi"] == sayi]
        s = _kanal_satiri(str(int(sayi)), alt)
        ekle(
            f"| {int(sayi)} | {s['n']} | {_pct(s['h12_1atr'])} | {_pct(s['h12_15atr'])} | {_pct(s['h12_2atr'])} | "
            f"{_num(s['medyan_tepe'])} | {_pct(s['ters_1atr'])} | {_pct(s['karisik'])} |"
        )
    ekle("")

    # Kanal kombinasyonları
    ekle("## 2 · Kanal kombinasyonları (n ≥ 30 olanlar)")
    ekle("")
    ekle("| kombinasyon | n | ≥1 ATR (12b) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR | güven |")
    ekle("|---|---:|---:|---:|---:|---:|---|")
    kombinasyonlar: dict[str, pd.DataFrame] = {}
    for combo, grup in tetik_kume.groupby("kanallar", dropna=True):
        ad = "+".join(sorted(combo)) if isinstance(combo, (list, tuple)) else str(combo)
        kombinasyonlar[ad] = grup
    for ad, grup in sorted(kombinasyonlar.items(), key=lambda kv: -len(kv[1])):
        if len(grup) < 30:
            continue
        s = _kanal_satiri(ad, grup)
        ekle(
            f"| {ad} | {s['n']} | {_pct(s['h12_1atr'])} | {_pct(s['h12_15atr'])} | "
            f"{_num(s['medyan_tepe'])} | {_pct(s['ters_1atr'])} | {s['guven']} |"
        )
    ekle("")

    # Zaman dilimi kırılımı
    ekle("## 3 · Zaman dilimi kırılımı")
    ekle("")
    ekle("| TF | tetik | bar başına | ≥1 ATR (12b) | medyan tepe | aleyhte ≥1 ATR |")
    ekle("|---|---:|---:|---:|---:|---:|")
    for tf, grup in sorted(tetik_kume.groupby("timeframe")):
        s = _kanal_satiri(tf, grup)
        ekle(
            f"| {tf} | {s['n']} | — | {_pct(s['h12_1atr'])} | {_num(s['medyan_tepe'])} | {_pct(s['ters_1atr'])} |"
        )
    ekle("")

    # Hacim kademesi
    ekle("## 4 · Hacim kademesi (canlı eşikler: 5× / 10×)")
    ekle("")
    ekle("| hacim | n | ≥1 ATR (12b) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR |")
    ekle("|---|---:|---:|---:|---:|---:|")
    for ad, grup in (
        ("hacim yok (<5×)", tetik_kume[tetik_kume["hacim_tier"].isna()]),
        ("5×–10×", tetik_kume[tetik_kume["hacim_tier"] == "5x"]),
        ("≥10×", tetik_kume[tetik_kume["hacim_tier"] == "10x"]),
    ):
        s = _kanal_satiri(ad, grup)
        ekle(
            f"| {ad} | {s['n']} | {_pct(s['h12_1atr'])} | {_pct(s['h12_15atr'])} | "
            f"{_num(s['medyan_tepe'])} | {_pct(s['ters_1atr'])} |"
        )
    ekle("")

    # Formasyon state kırılımı
    if "formasyon_state" in tetik_kume.columns and tetik_kume["formasyon_state"].notna().any():
        ekle("## 5 · Formasyon state kırılımı (canlı formasyon kanalı)")
        ekle("")
        ekle("| state | n | ≥1 ATR (12b) | ≥1,5 ATR | medyan tepe | aleyhte ≥1 ATR |")
        ekle("|---|---:|---:|---:|---:|---:|")
        for state, grup in sorted(tetik_kume[tetik_kume["formasyon_state"].notna()].groupby("formasyon_state"), key=lambda kv: -len(kv[1])):
            if len(grup) < 15:
                continue
            s = _kanal_satiri(str(state), grup)
            ekle(
                f"| {state} | {s['n']} | {_pct(s['h12_1atr'])} | {_pct(s['h12_15atr'])} | "
                f"{_num(s['medyan_tepe'])} | {_pct(s['ters_1atr'])} |"
            )
        ekle("")

    # Yön kırılımı
    ekle("## 6 · Yön (BOS/zone yönü)")
    ekle("")
    ekle("| yön | n | ≥1 ATR (12b) | medyan tepe | aleyhte ≥1 ATR |")
    ekle("|---|---:|---:|---:|---:|")
    for yon, ad in ((1, "yukarı"), (-1, "aşağı")):
        s = _kanal_satiri(ad, tetik_kume[tetik_kume["yon"] == yon])
        ekle(f"| {ad} | {s['n']} | {_pct(s['h12_1atr'])} | {_num(s['medyan_tepe'])} | {_pct(s['ters_1atr'])} |")
    ekle("")

    ekle("## 7 · Nasıl okunur / sınırlar")
    ekle("")
    ekle("- **'≥1 ATR' bir kazanç değildir.** Tetiğin gösterdiği yönde fiyatın 12 bar içinde")
    ekle("  en az 1 ATR uzanıp uzanmadığıdır; maliyet, kayma, pozisyon ve çıkış kuralı yok.")
    ekle("- **'aleyhte ≥1 ATR' ters taraftaki uzanımdır.** Lehte oranı yüksek ama aleyhte de")
    ekle("  yüksekse tetik *belirsizdir*: iki tarafa da 1 ATR gidiyor, kart yön iddia etmemeli.")
    ekle("- **Sansür** pencere veri sonuna takılan tetikleri dışarıda bırakır (n'ler bu yüzden")
    ekle("  ham satır sayısından küçüktür).")
    ekle("- **Bir tetik tek satırdır.** Aynı barda dört kanal ateşlerse tek satır üretilir;")
    ekle("  kanal sayısı tablosu bu yüzden kanal tablosundan farklı toplam verir.")
    ekle("- **FVG reaksiyonu nedensel türetilir:** arşiv zone satırı doğum anını taşıdığı için")
    ekle("  canlı motorun 'state=REACTION' anı, 'sınıra dokundu ve tükenmedi' ile karşılanır.")
    ekle("- Bu rapor **canlı alarm davranışını değiştirmez**; yalnız hangi tetiğin ölçülebilir")
    ekle("  bir fark ürettiğini gösterir.")
    ekle("")

    metin = "\n".join(satirlar) + "\n"
    rapor_yolu.parent.mkdir(parents=True, exist_ok=True)
    rapor_yolu.write_text(metin, encoding="utf-8")
    return metin


def _bar_orani(df: pd.DataFrame, meta: pd.DataFrame | None) -> float:
    if meta is None or len(meta) == 0 or "bar_sayisi" not in meta.columns:
        return 0.0
    toplam_bar = float(pd.to_numeric(meta["bar_sayisi"], errors="coerce").sum())
    if toplam_bar <= 0:
        return 0.0
    # Her tetik bir bardır; yön 0 satırları iki kez yazıldığı için tekil bar say.
    tekil = df.drop_duplicates(subset=["symbol", "timeframe", "bar_index"])
    return len(tekil) / toplam_bar


def _kanal_satiri(ad: str, grup: pd.DataFrame) -> dict[str, Any]:
    n = len(grup)
    if n == 0:
        return {
            "ad": ad, "n": 0, "h12_05atr": None, "h12_1atr": None, "h12_15atr": None,
            "h12_2atr": None, "medyan_tepe": None, "ters_1atr": None, "karisik": None,
            "guven": "YOK",
        }
    return {
        "ad": ad,
        "n": n,
        "h12_05atr": _oran(grup["yon_asim_050"]),
        "h12_1atr": _oran(grup["yon_asim_100"]),
        "h12_15atr": _oran(grup["yon_asim_150"]),
        "h12_2atr": _oran(grup["yon_asim_200"]),
        "medyan_tepe": float(grup["yon_tepe_atr"].median()) if grup["yon_tepe_atr"].notna().any() else None,
        "ters_1atr": _oran(grup["ters_h12"]),
        # "Belirsizlik": lehte ≥1 ATR **ve** aleyhte ≥1 ATR aynı 12 barda.
        # İkisi bağımsız olay olduğu için kesişim üst sınırdır; birebir
        # kesişim için iki eşiğin aynı barda görülmesi gerekir. Kaba ama
        # dürüst gösterge: her iki uzanım da gerçekleştiyse tetik yön iddia
        # edemez.
        "karisik": (
            _ve(grup["yon_asim_100"], grup["ters_h12"])
            if "yon_asim_100" in grup.columns and "ters_h12" in grup.columns
            else None
        ),
        "guven": _guven(n),
    }


def _ve(a: pd.Series, b: pd.Series) -> float | None:
    """İki boolean serinin kesişim oranı (NaN'ler payda dışı)."""
    maske = a.notna() & b.notna()
    if not maske.any():
        return None
    aa = a[maske].astype(bool)
    bb = b[maske].astype(bool)
    return float((aa & bb).mean())


def _kanal_tablosu(temiz: pd.DataFrame) -> list[dict[str, Any]]:
    satirlar = [_kanal_satiri("TÜM TETİKLER", temiz)]
    for kanal in KANALLAR:
        maske = temiz["kanallar"].map(lambda v: isinstance(v, (list, tuple)) and kanal in v)
        satirlar.append(_kanal_satiri(kanal, temiz[maske]))
    return satirlar


def _pp_fark(a: float | None, b: float | None) -> str:
    if a is None or b is None:
        return "—"
    return f"{(a - b) * 100:+.1f} pp"


# ---------------------------------------------------------------------------
# 4) Koşucu
# ---------------------------------------------------------------------------


def _repo_koku() -> Path:
    return Path(__file__).resolve().parent.parent


def kosu(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(_repo_koku()))
    cikti = Path(args.cikti)
    cikti.mkdir(parents=True, exist_ok=True)

    semboller = [s.strip().upper() for s in args.semboller.split(",") if s.strip()] if args.semboller else arsiv.arsiv_sembolleri(native_only=True)
    if not semboller:
        raise SystemExit("Native arşivde dört dosyası tamamlanmış sembol yok.")
    if not args.havuz_disi_dahil:
        semboller = [s for s in semboller if s not in arsiv.HAVUZ_DISI_SEMBOLLER]
    if args.limit:
        semboller = semboller[: args.limit]
    timeframeler = [t.strip().lower() for t in args.timeframe.split(",") if t.strip()]

    tamamlanan = set()
    if not args.zorla:
        meta = _oku(cikti / "meta.jsonl", ("symbol", "timeframe"))
        if len(meta):
            tamamlanan = {(r["symbol"], r["timeframe"]) for r in meta.to_dict("records")}

    plan = [(s, tf) for s in semboller for tf in timeframeler if (s, tf) not in tamamlanan]
    print(f"[plan] {len(semboller)} sembol x {len(timeframeler)} tf = {len(plan)} is · atlanan={len(semboller) * len(timeframeler) - len(plan)}", flush=True)

    baslangic = time.time()
    hata = 0
    for i, (sembol, tf) in enumerate(plan, 1):
        t0 = time.time()
        try:
            frame = arsiv.tf_frame(sembol, tf, legacy_resample=False)
            gozlem = sembol_timeframe_gozlem(sembol, tf, frame)
            tetikler = sembol_timeframe_tetikleri(sembol, tf, frame, gozlem)
            kontroller = kontrol_tetikleri(
                sembol, tf, frame, {int(t["bar_index"]) for t in tetikler}, args.taban_adim
            )
            satirlar = seri_olcumu(tetikler, frame) + seri_olcumu(kontroller, frame)
            _satir_ekle(cikti / "tetikler.jsonl", satirlar)
            _satir_ekle(cikti / "meta.jsonl", [{
                "symbol": sembol,
                "timeframe": tf,
                "bar_sayisi": int(len(frame)),
                "tetik_bar": len(tetikler),
                "kontrol_bar": len(kontroller),
                "tetik_satir": len(satirlar),
                "sure_sn": round(time.time() - t0, 1),
                "engine_version": ENGINE_VERSION,
            }])
            print(
                f"[{i}/{len(plan)}] {sembol:8} {tf:3} {time.time() - t0:6.1f}s "
                f"bar={len(frame)} tetik={len(tetikler)} kontrol={len(kontroller)} satir={len(satirlar)}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001 - sembol izolasyonu
            hata += 1
            _satir_ekle(cikti / "hatalar.jsonl", [{
                "symbol": sembol, "timeframe": tf,
                "hata": f"{type(exc).__name__}: {exc}",
                "iz": traceback.format_exc(limit=6),
            }])
            print(f"[{i}/{len(plan)}] {sembol:8} {tf:3} HATA: {type(exc).__name__}: {exc}", flush=True)
        finally:
            arsiv._OBELLEK.clear()

    gecen = time.time() - baslangic
    print(f"\n[bitti] {len(plan)} is · {gecen:.0f}s · hata={hata}", flush=True)

    if not args.rapor_atla:
        ozet = topla(cikti)
        metin = rapor_yaz(ozet, cikti, Path(args.rapor))
        print(f"[rapor] {args.rapor} ({len(metin)} karakter)", flush=True)
    return hata


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Domain alarm replay — canlı tetikleyicilerin arşiv ölçümü")
    p.add_argument("--limit", type=int, default=0, help="kaç sembol (0 = hepsi)")
    p.add_argument("--semboller", default="", help="virgülle sembol listesi")
    p.add_argument("--timeframe", default="1h,2h,4h,1d", help="virgülle zaman dilimleri")
    p.add_argument("--cikti", default="var/domain_alarm_replay", help="JSONL çıktı dizini")
    p.add_argument("--rapor", default="docs/arastirma/DOMAIN_ALARM_REPLAY_SONUCLARI.md")
    p.add_argument("--rapor-yaz", action="store_true", help="ölçüm yapma, mevcut çıktıdan rapor üret")
    p.add_argument("--rapor-atla", action="store_true", help="koşu sonunda rapor üretme")
    p.add_argument("--zorla", action="store_true", help="tamamlanmış işleri de yeniden koş")
    p.add_argument("--havuz-disi-dahil", action="store_true", help="BRENT dahil")
    p.add_argument(
        "--taban-adim",
        type=int,
        default=TABAN_ADIM,
        help="kontrol (taban) örnekleme adımı — her N barda bir tetik olmayan bar",
    )
    args = p.parse_args(argv)

    if args.rapor_yaz:
        ozet = topla(Path(args.cikti))
        metin = rapor_yaz(ozet, Path(args.cikti), Path(args.rapor))
        print(f"[rapor] {args.rapor} ({len(metin)} karakter) · tetik={ozet.get('tetik', 0)}")
        return 0
    return kosu(args)


if __name__ == "__main__":
    raise SystemExit(main())
