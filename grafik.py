# -*- coding: utf-8 -*-
"""Grafik katmanı — G1 iskeleti (sözleşme: GRAFIK_TASARIM.md §2/§3/§5/§17).

Neden bu modül: kart "kapanış 302,48 > 295,00" diyor; kritik mesafe ve retest
toleransı telefonda mum başına ~1 piksele iniyor. Kullanıcının sorduğu üç soru
("bant nerede başlıyor, hangi mumlara dokundu, yapı nerede kırıldı") kartta
sayısal olarak var ama görsel olarak yok. Bu modül kareyi üretir.

Sözleşme:
  * `anlik_goruntu(cift, tf, cerceve, ...)` tarama anındaki motor çıktısını
    **kopyalar** (saf fonksiyon; matplotlib istemez) → köprü payload'a buradan
    eklenir (§14.1).
  * `ciz(goruntu, tf, secenekler) -> (png_yolu, meta)` **hesap yapmaz**: motoru
    yeniden çalıştırmaz, deque'a dokunmaz (§14.2/§14.3). `son_bar_ts` uyuşmazsa
    çizim reddedilir.
  * matplotlib TEMBEL yüklenir (`_pyplot_getir()`): `TELEGRAM_GRAFIK=yok` iken bu
    modülü import etmek hiçbir çizim bağımlılığı yüklemez (§7).
  * Sayılar `reporting.format.sayi()` ile yazılır → Türkçe virgül (G0, §15).
  * Yazı genişliği `telegram_measure.genislik()` ile ölçülür → kartla aynı metrik
    (§6.4); hiçbir yazı Mumların üstüne sarmaz, sığmazsa `…` ile kırpılır ve
    `meta["metin"]["kesilen"]`'e yazılır.
"""

from __future__ import annotations

import io
import logging
import math
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional, Sequence

from reporting.format import sayi
from telegram_measure import SATIR_BUTCE, genislik as _genislik_16

try:  # yalnız kapanmış mum kuralı (§0.6); zincir koparsa kural devre dışı kalır
    from data import bar_kapandi_mi as _bar_kapandi_mi
except Exception:  # pragma: no cover - bağımlılık yoksa da import edilebilsin
    _bar_kapandi_mi = None

try:  # alarm etiketi gerçek state metninden (§0.12z) — yeni sözcük icat edilmez
    from notifier import PUBLIC_STATE_ETIKET as _STATE_ETIKET
    from notifier import _tr_tarih as _tarih_tr
except Exception:  # pragma: no cover
    _STATE_ETIKET = {}
    _tarih_tr = None

try:  # TF kısaltması mevcut eşlemeden alınır, yenisi yazılmaz (§14.5)
    from notification_context import TIMEFRAME_LABELS as _TF_KISA
except Exception:  # pragma: no cover
    _TF_KISA = {"1h": "1s", "2h": "2s", "4h": "4s", "1d": "1g"}

log = logging.getLogger(__name__)

# ------------------------------------------------------------------- sabitler


def _ortam_sayi(ad: str, varsayilan: float) -> float:
    """Env okuması ÇAĞRI ANINDA yapılır (`config.py` sabitleri import'ta donuyor).

    Neden: §6.1 kadraj testleri `os.environ` ile oynar; import zamanında okunan
    değer bunu göremezdi. Bozuk değer varsayılana düşer — grafik alarmı asla
    engellemez (§4).
    """
    try:
        ham = (os.environ.get(ad) or "").strip()
        return float(ham) if ham else float(varsayilan)
    except (TypeError, ValueError):
        return float(varsayilan)


# §5'teki sabit bloğun birebir hali; sayılar §17 ölçümlerinden.
SABITLER: dict[str, Any] = {
    # kare ölçüleri (§17.1-2: bar_px 4→6, tavan 2160→1440; §0.12q oran 4:3)
    "genislik_taban": 1080,
    "yukseklik": 810,
    "bar_px": 6,
    "genislik_tavan": 1440,
    "mum_min_px": 5.0,        # px/bar altına düşerse → çizgi + alan (§17.14)
    "dpi": 100,
    # kadraj (§2: sol = max(0, min(bas_bar - 8, n - GRAFIK_MUM_MAKS)))
    "kare_mum": 180,
    "kare_once_pay": 8,
    "kadraj_cerceve": {"1h": 180, "2h": 180, "4h": 180, "1d": 180},   # §0.16: 60 değil
    # zone'lar (G2'de çizilir; sayılar §0.9)
    "zone_ust": {"1h": 3, "2h": 3, "4h": 2, "1d": 1},
    "zone_alt": {"1h": 3, "2h": 3, "4h": 2, "1d": 1},
    "diverans_mum": 15,
    # katılım şeridi (G3'te çizilir; §2.1)
    "serit": "rvol20",
    "serit_esik": 1.5,
    "serit_maks": 12,
    "hacim_uzunluk": 20,
    "serit_kulvar_orani": 0.143,      # 1/7 — §17.4 ayrı üst kulvar
    "son_mum_isaret": 15,             # §0.12a: `!` yalnız son 15 mum
    # yapı (G3, §2.2): onaylı+geçerli en yeni 6 BOS/CHoCH; swing etiketi kapaklı
    "olay_maks": 6,
    "swing_maks": 10,
    "yapi_alpha": {"teyitli": 1.0, "kirik": 0.2, "aday": 0.45},   # §0.4.1 satırı
    # ortak
    "dipnot": "sorun",                # §0.12w: dipnot yalnız veri sorunu varsa
    "lejant": True,                   # §0.12v: her karede tek gri satır
    "katmanlar": ("formasyon", "ob", "fvg", "ms", "serit"),
    "etiket_detay": False,            # §2.6: evidence_text ancak istenirse
    "drift_tolersans_bar": 0,
    "meta_jsonl": None,               # §13 (v1 yok)
    "gorsel_aralik_sn": "mevcut pacing yardımcısı",
    # yazı boyutları (pt; dpi=100 → px = pt × 100 / 72)
    "baslik_pt": 10.5,
    "durum_pt": 9.5,
    "eksen_pt": 9.0,
    "etiket_pt": 9.0,
    "lejant_pt": 9.0,
    "dipnot_pt": 9.0,
    # çizim incelikleri (spike ölçümü, §17)
    "mum_genislik_orani": 0.62,
    "temas_radyus": 4.2,
    "temas_isaret_maks": 24,     # kalabalık karede yalnız en yeni N temas işaretlenir
    "isaret_boyut": 5.4,
    "cizgi_kalinlik": {"formasyon": 1.6, "alarm_kritik": 2.2, "alarm_normal": 1.1,
                       "projeksiyon": 1.1, "grid": 0.7},
    "doldurma": {"golge_esik_orani": 0.18, "golge": 0.14, "golge_ince": 0.05,
                 "ob": 0.14, "fvg": 0.12, "eng": 0.0, "ince": 0.05},
    "zone_kalinlik": {"kenar": 0.9, "vurgu": 2.0},
    "zone_yazi_pt": 8.0,        # kutu etiketi; çakışma ölçümü de bu puntoyu kullanır
    # yazı bütçesi (§22'de kaydı: kart satır bütçesinin kare ölçeğe çevrilmişi)
    "metin_carpani": 0.82,            # genislik() 16 px tabanlı; kare içi yazı 13,2 px
    "etiket_maks_px": 300.0,          # kare içi etiket tavanı (~%28 kare genişliği)
}

# §0.4.1 kalıcı palet — renk tek başına bilgi taşımaz, her katmanın yazısı da var.
PALET = {
    "zemin": "#101418",
    "metin": "#e8e8e8",
    "eksen": "#9aa0a6",
    "grid": "#2a2f35",
    "mum_yukselen": "#e3e6e8",
    "mum_dusen": "#8d949a",
    "ob": "#2bb673",
    "fvg": "#42a5f5",
    "engulf": "#b388ff",
    "formasyon": "#f5f5f5",
    "temas": "#e8e8e8",
    "swing": "#90a4ae",
    "sinif": "#b0bec5",
    "olay": "#ff8a65",
    "serit": "#80cbc4",
    "ihlal": "#ef5350",
    "alarm": "#b8bec4",
    "golge": "#ffffff",
}

# Alarm çizgisinin kalınlığı durumundan gelir (§2.6): halka açık durumlar kalın.
# §0.12l: `1s` ve `2s` karelerinde FVG çizilmez — `zone_scoring.FVG_TIMEFRAMES`
# {2h,4h,1d} + `enable_2h_fvg=False`: canlı yolda `2s`de de FVG üretilmiyor.
_FVG_YOK_TFLAR = frozenset({"1h", "2h"})

# Kutu dolgusu motorun durumundan gelir (§3: state → solid/mitigated/hatched).
# Enum SAYISI değil ADI kullanılıyor: motor değerleri kaydırsa çizim yanlış
# anlama düşmesin (bilinmeyen ad = kontur, uydurma dolgu yok).
_BOLGE_DOLU = frozenset({"ACTIVE", "FIRST_TEST", "DEEP_TEST", "REACTION",
                         "CONTINUATION_CONFIRMED"})
_BOLGE_ARA = frozenset({"CANDIDATE", "PARTIAL_FILL", "PARTIAL_RETRACE", "WEAKENED"})

_ALARM_KALIN = {
    "KIRILIM_TEYITLI": "alarm_kritik",
    "RETEST_BASARILI": "alarm_kritik",
    "KIRILIM_GECERSIZLESTI": "alarm_kritik",
    "KIRILIM_HAZIRLIGI": "alarm_normal",
}

# §0.12l: 1s/2s karelerinde FVG çizilmez — `zone_scoring.FVG_TIMEFRAMES` ile aynı küme.
_FVG_TIMEFRAMES = frozenset({"2h", "4h", "1d"})

_AY = {1: "Oca", 2: "Şub", 3: "Mar", 4: "Nis", 5: "May", 6: "Haz",
       7: "Tem", 8: "Ağu", 9: "Eyl", 10: "Eki", 11: "Kas", 12: "Ara"}


def grafik_aktif_mi() -> bool:
    """Kill-switch (§5): `TELEGRAM_GRAFIK=yok` (veya boş) ise hiçbir kare üretilmez.

    Neden env'den ve çağrı anında: anahtarı değiştirmek için süreci yeniden
    başlatmak gerekmesin; `deploy_check` de aynı okumayı yapar (G4).
    """
    return (os.environ.get("TELEGRAM_GRAFIK") or "yok").strip().lower() != "yok"


def grafik_kare_adedi() -> int:
    """`TELEGRAM_GRAFIK_ADET` (1-4, §5): alarm başına en fazla kare."""
    adet = int(_ortam_sayi("TELEGRAM_GRAFIK_ADET", 4))
    return max(1, min(4, adet))


def kare_mum_tavani(tf: str) -> int:
    """`GRAFIK_MUM_MAKS` (§5): kadraj tavanı; formasyon eskiyse kalkar (§0.12b)."""
    varsayilan = int(SABITLER["kadraj_cerceve"].get(str(tf), SABITLER["kare_mum"]))
    return max(2, int(_ortam_sayi("GRAFIK_MUM_MAKS", varsayilan)))


# ------------------------------------------------------ girdi okuma yardımcıları


def _alan(nesne: Any, ad: str, varsayilan: Any = None) -> Any:
    """Sözlük/nesne ayrımı yapmadan alan oku (`notification_context._field` ile aynı fikir).

    Neden: `cift` canlı yolda `PatternCandidate`, kart payload'ında ve test
    kayıtlarında sözlük. İki yolu ayrı ayrı sarmalamak yerine tek okuma noktası.
    """
    if nesne is None:
        return varsayilan
    if isinstance(nesne, Mapping):
        deger = nesne.get(ad, varsayilan)
        return varsayilan if deger is None else deger
    return getattr(nesne, ad, varsayilan)


def _gercek(deger: Any) -> Optional[float]:
    """SONLU float; değilse None. (Grafik uydurulmuş/bozuk sayı çizmez.)"""
    try:
        x = float(deger)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _tam(deger: Any) -> Optional[int]:
    try:
        x = float(deger)
    except (TypeError, ValueError):
        return None
    return int(x) if math.isfinite(x) else None


def _tarih(deger: Any) -> Optional[datetime]:
    """Timestamp → `datetime`; okunamazsa None (çizim bunu atlar, çökmez)."""
    if deger is None or isinstance(deger, datetime):
        return deger
    ham = deger.item() if hasattr(deger, "item") else deger
    if hasattr(ham, "to_pydatetime"):
        try:
            return ham.to_pydatetime()
        except Exception:  # pragma: no cover
            return None
    metin = str(ham).strip()
    if not metin or metin in {"NaT", "None"}:
        return None
    try:
        return datetime.fromisoformat(metin.replace("Z", "+00:00"))
    except ValueError:
        return None


def _tarih_metni(dt: Optional[datetime]) -> str:
    """Kısa Türkçe tarih (`13 Eki 15:30`); mesajlardaki `_tr_tarih` ile aynı biçim."""
    if dt is None:
        return "—"
    if _tarih_tr is not None:
        try:
            return _tarih_tr(dt)
        except Exception:  # pragma: no cover - notifier biçimi değişirse düşüş
            pass
    return f"{dt.day:02d} {_AY.get(dt.month, '')} {dt:%H:%M}"


_KOLONLAR = {
    "acilis": ("acilis", "open", "o"),
    "yuksek": ("yuksek", "high", "h"),
    "dusuk": ("dusuk", "low", "l"),
    "kapanis": ("kapanis", "close", "c"),
    "hacim": ("hacim", "volume", "v"),
}
_ZAMAN_ANAHTARLARI = ("zaman", "timestamp", "time", "date", "index")


def _cerceve_ayristir(cerceve: Any) -> dict[str, list[Any]]:
    """Çerçeveyi {zaman, acilis, ..., hacim} listelerine çevirir.

    Üç girdi biçimi de gerçek: canlı yol `data.resample_ohlcv()` çıktısı
    (DataFrame), `bot_data/<SEM>.json` kayıt listesi, testlerin kurduğu kolon
    sözlüğü. pandas'e yeni bağımlılık eklememek için `.index/.columns` varsa
    onunla yetiniyoruz (pandas'ı import etmiyoruz).
    """
    if cerceve is None:
        return {}

    def sayilar(deger: Any) -> list[Optional[float]]:
        if deger is None:
            return []
        if hasattr(deger, "tolist"):
            deger = deger.tolist()
        try:
            return [_gercek(x) for x in list(deger)]
        except TypeError:
            return []

    def anahtar_bul(adaylar: Sequence[str], anahtarlar: Mapping[str, Any]) -> Any:
        for ad in adaylar:
            if ad in anahtarlar:
                return anahtarlar[ad]
        return None

    if hasattr(cerceve, "columns") and hasattr(cerceve, "index"):      # DataFrame
        esleme = {str(k).lower(): k for k in cerceve.columns}
        zaman = list(cerceve.index)
        cikti: dict[str, list[Any]] = {"zaman": [_tarih(z) for z in zaman]}
        for ad, adaylar in _KOLONLAR.items():
            anahtar = anahtar_bul(adaylar, esleme)
            cikti[ad] = sayilar(None if anahtar is None else cerceve[anahtar])
        return cikti

    if isinstance(cerceve, Mapping):
        esleme = {str(k).lower(): k for k in cerceve}
        zaman_anahtar = anahtar_bul(_ZAMAN_ANAHTARLARI, esleme)
        cikti = {"zaman": ([_tarih(z) for z in list(cerceve[zaman_anahtar])]
                           if zaman_anahtar is not None else [])}
        for ad, adaylar in _KOLONLAR.items():
            anahtar = anahtar_bul(adaylar, esleme)
            cikti[ad] = sayilar(cerceve[anahtar] if anahtar is not None else None)
        return cikti

    if isinstance(cerceve, Sequence) and not isinstance(cerceve, (str, bytes)):
        kayitlar = [x for x in cerceve if isinstance(x, Mapping)]
        if not kayitlar:
            return {}
        zamanlar: list[Any] = []
        sutunlar: dict[str, list[Any]] = {ad: [] for ad in _KOLONLAR}
        for kayit in kayitlar:
            kucuk = {str(k).lower(): v for k, v in kayit.items()}
            zamanlar.append(_tarih(kucuk.get(anahtar_bul(_ZAMAN_ANAHTARLARI, kucuk)
                                             if anahtar_bul(_ZAMAN_ANAHTARLARI, kucuk) else "",
                                             None) if anahtar_bul(_ZAMAN_ANAHTARLARI, kucuk) else None))
            for ad, adaylar in _KOLONLAR.items():
                anahtar = anahtar_bul(adaylar, kucuk)
                sutunlar[ad].append(kucuk.get(anahtar) if anahtar else None)
        return {"zaman": zamanlar, **{ad: sayilar(v) for ad, v in sutunlar.items()}}

    return {}


# ------------------------------------------------------------------- kadraj


def _kadrajla(n: int, formasyon_basi: Optional[int], kare_mum: Optional[int] = None,
              once_pay: Optional[int] = None) -> tuple[int, int, bool]:
    """(sol, sag, tavan_kalkti) — §2 kadraj kuralı.

    Pencere formasyonun ilk mumuna sabitlenir, geriye MS için uzatılmaz (§0.15);
    formasyon `kare_mum`'dan eskiyse tavan kalkar (§0.12b) ve `budama`'ya yazılır.
    """
    n = max(0, int(n))
    if n <= 0:
        return 0, 0, False
    kare = max(1, int(kare_mum if kare_mum else SABITLER["kare_mum"]))
    pay = int(SABITLER["kare_once_pay"] if once_pay is None else once_pay)
    sol_tavan = max(0, n - kare)
    bas = _tam(formasyon_basi)
    if bas is not None and bas >= 0:
        sol = max(0, min(bas - pay, sol_tavan))
    else:
        sol = sol_tavan
    tavan_kalkti = bool(bas is not None and bas >= 0 and sol < sol_tavan)
    return sol, n, tavan_kalkti


def _bant_temaslari(yuksek: Sequence[Optional[float]], dusuk: Sequence[Optional[float]],
                    alt: float, ust: float, sol: int, sag: int) -> list[int]:
    """Bandı delen mum indeksleri — `zone_scoring._touch_episodes` ile AYNI kural.

    Neden yerel fonksiyon: motor temas *sayısını* (`upper_touches/lower_touches`)
    ve episode ARALIĞINI veriyor; çizim tekil mum listesi istiyor. Kural
    uydurulmadı, repo'nun kendi tanımı (`low <= ust and high >= alt`) kullanıldı.
    """
    bulun: list[int] = []
    for i in range(max(0, int(sol)), min(int(sag), len(yuksek), len(dusuk))):
        y, d = yuksek[i], dusuk[i]
        if y is None or d is None:
            continue
        if d <= ust and y >= alt:
            bulun.append(i)
    return bulun


# --------------------------------------------------------------- bölge havuzu (G2)


def _wilder_atr(cerceve: Any) -> Optional[float]:
    """Çerçevenin son ATR'si — `zone_scoring.wilder_atr` ile AYNI tanım (14 bar).

    Neden bu: §0.8 mesafeyi ATR'ye böler; motor OB kayıtlarında ATR vermiyor
    (§17.12). Depoda tek ATR tanımı `zone_scoring`'de ve SAF bir fonksiyon —
    motor durumu ilerletmiyor, yani §14.2 yasağı ihlal edilmiyor. Uzunluk
    `zone_scoring.ATR_LENGTH`'ten alınır (sayı kopyalanmaz). Okunamazsa None
    dönür ve sıra ham fiyat mesafesine düşer (kare bunu `sirala` ile söyler).
    """
    try:
        from zone_scoring import ATR_LENGTH, wilder_atr
    except Exception:  # pragma: no cover - bağımlılık yoksa mesafe ham kalır
        return None
    try:
        import pandas as pd
        if isinstance(cerceve, pd.DataFrame):
            frame = cerceve
        elif isinstance(cerceve, Mapping):
            frame = pd.DataFrame({"high": cerceve.get("yuksek") or cerceve.get("high"),
                                  "low": cerceve.get("dusuk") or cerceve.get("low"),
                                  "close": cerceve.get("kapanis") or cerceve.get("close")})
        else:
            frame = pd.DataFrame(list(cerceve or []))
        seri = wilder_atr(frame, ATR_LENGTH)
        for deger in reversed(list(seri)):
            x = _gercek(deger)
            if x is not None and x > 0:
                return x
    except Exception as hata:  # pragma: no cover - veri biçimi şaşırtırsa mesafe ham
        log.debug("grafik: ATR okunamadı (%s)", hata)
    return None


def _bolge(tip: str, yon: int, alt: float, ust: float, kaynak: Optional[int],
           durum: Optional[str] = None, skor: Optional[float] = None,
           doluluk: Optional[float] = None, zaman: Any = None,
           gap: Optional[float] = None) -> Optional[dict[str, Any]]:
    """Tek bir bölge kaydı (§1): motorun verdiği sınırlar, uydurma yok."""
    if alt is None or ust is None:
        return None
    if alt > ust:
        alt, ust = ust, alt
    return {"tip": tip, "yon": 1 if yon >= 0 else -1, "alt": float(alt), "ust": float(ust),
            "kaynak": kaynak, "durum": durum, "skor": skor, "doluluk": doluluk,
            "zaman": _tarih(zaman).isoformat() if _tarih(zaman) else None, "gap": gap}


def _yon(deger: Any, varsayilan: int = 1) -> int:
    """Yön: `Direction`/`FvgDirection` (IntEnum) veya sayı → +1 / -1.

    Motor enum nesnesi verebilir; `.value` okunur ki sayıya gömülü kalmayalım
    (bilinmeyen → varsayılan, uydurma değil).
    """
    deger = getattr(deger, "value", deger)
    try:
        return -1 if int(deger) < 0 else 1
    except (TypeError, ValueError):
        return 1 if varsayilan >= 0 else -1


def _ad(deger: Any) -> str:
    """Enum/str karışık alanları düz isimle oku (`HIGH`, `EVENT_BOS`, `True`)."""
    if deger is None:
        return ""
    return str(getattr(deger, "name", deger))


def _durum_adi(deger: Any) -> Optional[str]:
    ad = getattr(deger, "name", None)
    if ad:
        return str(ad)
    metin = str(deger or "").strip()
    return metin or None


def _zone_havuzu(sonuclar: Optional[Mapping[str, Any]], tf: str, son_kapanis: Optional[float],
                 sol: int, sag: int, cerceve: Any = None) -> dict[str, Any]:
    """OB + FVG + engulfing TEK HAVUZDA, son kapanışa yakınlığa göre (§0.8/§0.9).

    Kapak TF'ye göre (`zone_ust`/`zone_alt`): 1s 3+3 · 2s 3+3 · 4s 2+2 · 1g 1+1.
    Eşitlikte daha yeni `kaynak` kazanır. Kapanışa göre taraf: kutu merkezi
    kapanışın üstündeyse "üst", altındaysa "alt".
    """
    havuz: list[dict[str, Any]] = []
    hata: list[str] = []
    cikarim = {"ob": 0, "fvg": 0, "eng": 0}
    if not sonuclar:
        return {}
    atr = _wilder_atr(cerceve)

    ob = sonuclar.get("order_block") if isinstance(sonuclar, Mapping) else _alan(sonuclar, "order_block")
    if ob is not None:
        try:
            detay = _alan(ob, "details", {}) or {}
            kayitlar = list(_alan(detay, "records", []) or [])
            cikarim["ob"] = len(kayitlar)
            export = _alan(ob, "export")
            dolular = {}
            for taraf in ("bull", "bear"):
                yan = _alan(export, taraf) if export is not None else None
                kaynak = _tam(_alan(yan, "source_bar"))
                if kaynak is not None:
                    dolular[kaynak] = _gercek(_alan(yan, "fill"))
            for kayit in kayitlar:
                kaynak = _tam(_alan(kayit, "source_index"))
                bolge = _bolge("ob", 1 if _alan(kayit, "bullish") else -1,
                               _gercek(_alan(kayit, "bottom")), _gercek(_alan(kayit, "top")),
                               kaynak, skor=_gercek(_alan(kayit, "base_score")),
                               doluluk=dolular.get(kaynak) if kaynak is not None else None,
                               zaman=_alan(kayit, "source_time"))
                if bolge:
                    havuz.append(bolge)
        except Exception as h:
            log.warning("grafik: OB bölgeleri okunamadı (%s)", h)
            hata.append("ob")

    fvg = sonuclar.get("fvg") if isinstance(sonuclar, Mapping) else _alan(sonuclar, "fvg")
    if fvg is not None and str(tf) not in _FVG_YOK_TFLAR:
        try:
            detay = _alan(fvg, "details", {}) or {}
            kayitlar = list(_alan(detay, "fvg_formations", []) or [])
            cikarim["fvg"] = len(kayitlar)
            for kayit in kayitlar:
                bolge = _bolge("fvg", _yon(_alan(kayit, "direction")), 
                               _gercek(_alan(kayit, "lower_boundary")),
                               _gercek(_alan(kayit, "upper_boundary")),
                               _tam(_alan(kayit, "formation_index")),
                               durum=_durum_adi(_alan(kayit, "state")),
                               skor=_gercek(_alan(kayit, "quality")),
                               doluluk=_gercek(_alan(kayit, "close_fill_ratio")),
                               zaman=_alan(kayit, "formation_time"),
                               gap=_gercek(_alan(kayit, "gap_size")))
                if bolge:
                    havuz.append(bolge)
            eng = list(_alan(detay, "engulfing_formations", []) or [])
            cikarim["eng"] = len(eng)
            for kayit in eng:
                alt = _gercek(_alan(kayit, "formation_low"))
                ust = _gercek(_alan(kayit, "formation_high"))
                if alt is None or ust is None:
                    alt, ust = _gercek(_alan(kayit, "lower_boundary")), _gercek(_alan(kayit, "upper_boundary"))
                bolge = _bolge("eng", _yon(_alan(kayit, "direction")), alt, ust,
                               _tam(_alan(kayit, "formation_index")),
                               durum=_durum_adi(_alan(kayit, "state")),
                               skor=_gercek(_alan(kayit, "quality")),
                               zaman=_alan(kayit, "formation_time"))
                if bolge:
                    havuz.append(bolge)
        except Exception as h:
            log.warning("grafik: FVG/engulfing bölgeleri okunamadı (%s)", h)
            hata.append("fvg")
    elif fvg is not None:
        # §0.12l: 1s/2s karesinde FVG katmanı çizilmez (motor da üretmiyor).
        cikarim["fvg_tf_yok"] = 1

    if not havuz:
        return {"cizilen": [], "elenen": 0, "kaynak_disi": 0, "kapak": dict(
            _kapak_sayilari(tf)), "sirala": "bölge yok", "cikarim": cikarim,
            "hata": sorted(set(hata))}

    for b in havuz:
        merkez = (b["alt"] + b["ust"]) / 2.0
        b["merkez"] = merkez
        b["taraf"] = "ust" if (son_kapanis is None or merkez >= son_kapanis) else "alt"
        b["mesafe"] = abs(merkez - son_kapanis) if son_kapanis is not None else 0.0
        b["mesafe_atr"] = (b["mesafe"] / atr) if (atr and son_kapanis is not None) else None
    # EN YAKIN önce: `-mesafe` değil `mesafe` sırası — ters çevirmek kapakların
    # en uzak kutuları tutmasına yol açardı (testte yakalandı). Eşitlikte yeni
    # `kaynak` kazanır (§0.8).
    anahtar = (lambda b: (b["mesafe_atr"] if b["mesafe_atr"] is not None else b["mesafe"],
                          -(b["kaynak"] if b["kaynak"] is not None else -1)))
    havuz.sort(key=anahtar)
    ust_k, alt_k = _kapak_sayilari(tf)["ust"], _kapak_sayilari(tf)["alt"]
    secilen, elenen = [], 0
    sayac = {"ust": 0, "alt": 0}
    for b in havuz:
        taraf = b["taraf"]
        kapasite = ust_k if taraf == "ust" else alt_k
        if sayac[taraf] >= kapasite:
            elenen += 1
            continue
        sayac[taraf] += 1
        b["vurgu"] = "alt" if int(b["yon"]) >= 0 else "ust"   # §0.12r (kayatta karar)
        b["x0"], b["x1"] = 0, max(0, int(sag) - int(sol) - 1)
        if b["kaynak"] is not None:
            b["x0"] = max(0, min(int(b["kaynak"]) - int(sol), b["x1"]))
        secilen.append(b)
    # Çizim/rapor sırası: taraf, sonra yakınlık (meta okunur kalsın)
    secilen.sort(key=lambda b: (b["taraf"], b["mesafe"], int(b["kaynak"] or 0)))
    return {"cizilen": secilen, "elenen": elenen,
            "kaynak_disi": sum(1 for b in secilen if b["kaynak"] is not None
                               and int(b["kaynak"]) < int(sol)),
            "kapak": {"ust": ust_k, "alt": alt_k},
            "sirala": ("mesafe/ATR" if atr else "mesafe (ATR yok → ham fiyat)"),
            "atr": atr, "cikarim": cikarim, "hata": sorted(set(hata))}


def _kapak_sayilari(tf: str) -> dict[str, int]:
    ust = SABITLER["zone_ust"].get(str(tf), 3)
    alt = SABITLER["zone_alt"].get(str(tf), 3)
    return {"ust": int(ust), "alt": int(alt)}


# --------------------------------------------------------------- anlık görüntü


def anlik_goruntu(cift: Any = None, tf: str = "1h", cerceve: Any = None, *,
                  sonuclar: Optional[Mapping[str, Any]] = None,
                  alarm_turu: Optional[str] = None, alarm_bar: Optional[int] = None,
                  sembol: str = "", zaman_damgasi: Any = None,
                  simdi: Optional[datetime] = None,
                  kare_mum: Optional[int] = None,
                  etiket_detay: Optional[bool] = None) -> dict[str, Any]:
    """Tarama anındaki veriyi çizilebilir sözlüğe kopyalar (§2, §14.1).

    `cift`: kartın beslendiği formasyon kaydı (`PatternCandidate` veya payload
    sözlüğü). `sonuclar`: `run_domain_engines` çıktısı — G1'de yalnız *varlığı*
    not edilir (G2 zone'ları, G3 yapı/şerit buradan okunur); motor çağrılmaz.
    `alarm_turu` `aday/kritik/teyit/retest/gecersiz/ihlal`, `alarm_bar` çerçeve
    değeri mum indeksi. Hiçbiri zorunlu değil: verisi olmayan katman çizilmez.
    `etiket_detay` None ise `SABITLER["etiket_detay"]` (§2.6: `evidence_text`
    ancak istenirse karenin içine yazılır).
    """
    tf = str(tf or "1h")
    veri = _cerceve_ayristir(cerceve)
    zamanlar = [_tarih(z) for z in (veri.get("zaman") or [])]
    sutun = {ad: list(veri.get(ad) or []) for ad in ("acilis", "yuksek", "dusuk", "kapanis", "hacim")}
    n = min([len(zamanlar)] + [len(v) for v in sutun.values() if v] or [0])
    uyari: list[str] = []

    # --- yalnız kapanmış mumlar (§0.6): son bar kapalı değilse çizime girmez.
    son_bar_kapali = True
    goruntu_not = ""
    if n and zamanlar[-1] is not None and _bar_kapandi_mi is not None:
        try:
            son_bar_kapali = bool(_bar_kapandi_mi(zamanlar[-1], tf, now=simdi))
        except Exception:  # pragma: no cover - zamanlama yardımcısı takılırsa çiz
            son_bar_kapali = True
    if n and not son_bar_kapali:
        n -= 1
        zamanlar = zamanlar[:n]
        sutun = {ad: v[:n] for ad, v in sutun.items()}
        # Açık bar çizilmemesi normal (§0.6) → dipnot değil, meta'da durur.
        goruntu_not = "son bar açıktı: çizime alınmadı"

    formasyon = _formasyon_kopyala(cift)
    durum = str(formasyon.get("state") or "")
    if alarm_turu is None:
        alarm_turu = _ALARM_TURU.get(durum)

    kare = int(kare_mum if kare_mum else kare_mum_tavani(tf))
    sol, sag, tavan_kalkti = _kadrajla(n, formasyon.get("start_bar"), kare)
    goruntu: dict[str, Any] = {
        "surum": 1,
        "sembol": str(sembol or "").upper(),
        "tf": tf,
        "tf_kisa": _TF_KISA.get(tf, tf),
        "zaman_damgasi": (str(zaman_damgasi) if zaman_damgasi is not None
                          else (zamanlar[-1].isoformat() if zamanlar and zamanlar[-1] else None)),
        "son_bar_ts": zamanlar[-1].isoformat() if n and zamanlar and zamanlar[-1] else None,
        "son_kapanis": (sutun["kapanis"][-1] if n and sutun["kapanis"] else None),
        "son_bar_kapali": son_bar_kapali,
        "bar_sayisi": n,
        "kare_mum": kare,
        "sol": sol,
        "sag": sag,
        "tavan_kalkti": tavan_kalkti,
        "zamanlar": zamanlar[sol:sag],
        **{ad: v[sol:sag] for ad, v in sutun.items()},
        "formasyon": formasyon,
        "alarm": None,
        "temas": [],
        "hacimsiz_bar": sum(1 for x in sutun["hacim"][sol:sag] if x is None or x <= 0),
        "budama": [],
        "eksik_katmanlar": [],
        "notlar": [],           # meta'da durur, karenin altına yazılmaz (§0.6 normal durum)
        "uyarilar": uyari,
        "zone": None,     # G2: {"cizilen": n, "elenen": n}
        "olay": None,     # G3: {"cizilen": n, "elenen": n}
        "serit": None,    # G3: {"degerler": [...], "esik": x, "kaynak": "..."}
    }
    if tavan_kalkti:
        yas = n - int(formasyon["start_bar"])
        goruntu["budama"].append(
            f"kadraj: formasyon {yas} barlık → GRAFIK_MUM_MAKS={kare} kaldırıldı")
    if _alan(cift, "violation_history_truncated"):
        goruntu["uyarilar"].append("ihlal geçmişi kırpılmış: sayılar eksik görünebilir")
    goruntu["zone"] = _zone_havuzu(sonuclar, tf, goruntu["son_kapanis"], sol, sag, cerceve)
    if goruntu["zone"].get("hata"):
        goruntu["eksik_katmanlar"] = sorted(set(goruntu["eksik_katmanlar"])
                                            | set(goruntu["zone"]["hata"]))
    # Şerit çerçeveden TÜRETİLİR (yerel rvol için motor gerekmez); motor serisi
    # varsa o kullanılır (§2.1). Yapı katmanı `sonuclar` olmadan var olamaz.
    if n and sag:
        try:
            goruntu["serit"] = _serit_verisi(sonuclar, sutun["hacim"], sol, sag, n)
        except Exception as hata:
            log.warning("grafik: şerit katmanı kurulamadı (%s)", hata)
            goruntu["eksik_katmanlar"].append("serit")
    goruntu["olay"] = _olay_verisi(sonuclar, sol, sag,
                                  bool(SABITLER["etiket_detay"]) if etiket_detay is None
                                  else bool(etiket_detay))
    if (goruntu["olay"] or {}).get("hata"):
        goruntu["eksik_katmanlar"] = sorted(set(goruntu["eksik_katmanlar"])
                                            | set(goruntu["olay"]["hata"]))
    # `sonuclar` yoksa bölge/yapı katmanları YOKTUR — bu veri bozukluğu değil
    # (§0.12w: dipnot yalnız veri sorununa); izi `meta["zone"]["sirala"]` ve
    # `meta["olay"]` sıfırlarında taşınır.
    if not n or not sag:
        goruntu["uyarilar"].append("kare boş: çizim yok")
        return goruntu

    # --- temas mumları (§2.4) — bant verisi varsa.
    alt, ust = formasyon.get("lower_now"), formasyon.get("upper_now")
    if alt is not None and ust is not None:
        try:
            goruntu["temas"] = [i - sol for i in
                                _bant_temaslari(sutun["yuksek"], sutun["dusuk"], alt, ust, sol, sag)]
        except Exception as hata:  # pragma: no cover - katman çizimi durdurmaz (§2.9)
            log.warning("grafik: temas hesabı başarısız (%s)", hata)
            goruntu["eksik_katmanlar"].append("temas")
    elif formasyon:
        goruntu["uyarilar"].append("bant verisi yok: temas işaretlenmedi")
    tavan = int(SABITLER["temas_isaret_maks"])
    temas = goruntu["temas"]
    goruntu["temas_isaret"] = temas if len(temas) <= tavan else temas[-tavan:]
    if len(temas) > tavan:
        goruntu["budama"].append(
            f"temas işareti {tavan}'e indirildi (bant {len(temas)} mumu sardı)")
    goruntu["isaretler"] = _isaret_listesi(formasyon, goruntu["kapanis"], goruntu["yuksek"],
                                           sol, sag - sol)

    if goruntu_not:
        goruntu["notlar"].append(goruntu_not)
    goruntu["alarm"] = _alarm_kopyala(cift, alarm_turu, alarm_bar, sol, sag, goruntu)
    if (goruntu["alarm"] or {}).get("bar_disarida"):
        # Alarm mumu kadraj dışında kaldı: çizilmemesi bilgi kaybıdır → bildirilir.
        goruntu["uyarilar"].append("alarm mumu kadraj dışında: mum işaretlenmedi")
    return goruntu


_FORMASYON_METIN = ("pattern_name", "pattern_type", "state", "frozen_pattern_type",
                    "evidence_text")
_FORMASYON_SAYI = ("quality", "effective_quality", "contraction", "start_bar", "end_bar",
                    "apex_bar", "known_bar", "upper_now", "lower_now", "upper_slope",
                    "lower_slope", "upper_touches", "lower_touches", "break_price",
                    "critical_price_level", "candle_close_price", "close_price",
                    "direction", "break_dir", "progress", "start_width", "current_width")


def _formasyon_kopyala(cift: Any) -> dict[str, Any]:
    """Kartın gösterdiği formasyon alanlarını kopyalar (§1: yalnız gerçek alanlar)."""
    cikti: dict[str, Any] = {}
    for ad in _FORMASYON_METIN:
        deger = _alan(cift, ad)
        if deger is not None and str(deger).strip():
            cikti[ad] = str(deger)
    for ad in _FORMASYON_SAYI:
        ham = _alan(cift, ad)
        tamsayi_mi = ad.endswith(("_bar", "_touches", "direction", "break_dir"))
        deger = _tam(ham) if tamsayi_mi else _gercek(ham)
        if deger is not None:
            cikti[ad] = deger
    for ad in ("pattern_name", "pattern_type", "frozen_pattern_type"):
        deger = cikti.get(ad)
        if deger and deger not in {"Yok"}:
            cikti["ad"] = deger
            break
    return cikti


_ALARM_TURU = {
    # Yalnız motorun ürettiği durumlar (§0.12z: yeni sözcük yok).
    "KIRILIM_HAZIRLIGI": "aday",
    "KIRILIM_ADAYI": "aday",
    "KIRILIM_TEYITLI": "teyit",
    "RETEST_BASARILI": "retest",
    "KIRILIM_GECERSIZLESTI": "gecersiz",
    "KIRILIM_GECERSIZ": "gecersiz",
}

_TUR_ETIKET = {
    "aday": "kırılım adayı",
    "kritik": "kritik seviye",
    "teyit": "kapanışla teyitli kırılım",
    "retest": "kapanışla başarılı retest",
    "gecersiz": "önceki teyitli kırılım geçersizleşti",
    "ihlal": "bant ihlali",
}


def _isaret_listesi(formasyon: Mapping[str, Any], kapanis: Sequence[Optional[float]],
                    yuksek: Sequence[Optional[float]], sol: int, uzunluk: int) -> list[dict[str, Any]]:
    """Bant başlangıcı/bitişi/apex için mum kayıtları (§2.3).

    Kare-değeri indeks + gerçek fiyat; `anlik_goruntu`da üretilir ki çizim tarafı
    veri üretmesin ve alt yazı bloğunun yüksekliği baştan bilinsin.
    """
    kayitlar: list[dict[str, Any]] = []
    for ad, anahtar, kolon in (("bant başlangıcı", "start_bar", kapanis),
                               ("bant bitişi", "end_bar", kapanis),
                               ("apex", "apex_bar", yuksek)):
        bar = formasyon.get(anahtar)
        if bar is None:
            continue
        i = int(bar) - int(sol)
        if not (0 <= i < int(uzunluk)) or i >= len(kolon):
            continue
        kayitlar.append({"ad": ad, "bar": int(bar), "y": kolon[i]})
    return kayitlar


def _alarm_kopyala(cift: Any, alarm_turu: Optional[str], alarm_bar: Optional[int],
                   sol: int, sag: int, goruntu: Mapping[str, Any]) -> Optional[dict[str, Any]]:
    """Alarm mumu + seviye çizgisi tanımı; motorun sayısı birebir taşınır (§2.6)."""
    tur = (str(alarm_turu or "").strip().lower() or None)
    durum = str(_alan(cift, "state", "") or "")
    deger = _gercek(_alan(cift, "break_price"))
    if deger is None:
        deger = _gercek(_alan(cift, "critical_price_level"))
    if tur is None and deger is None and not durum:
        return None
    bar = _tam(alarm_bar)
    bar_kaynak = "alarm_bar"
    if bar is None:
        bar = _tam(_alan(cift, "end_bar"))
        bar_kaynak = "end_bar"
    disarida = False
    if bar is not None and not (sol <= bar < sag):
        disarida = True
        bar = None
    return {
        "tur": tur or _ALARM_TURU.get(durum),
        "deger": deger,
        "bar": bar,
        "bar_kaynak": bar_kaynak if bar is not None else None,
        "bar_disarida": disarida,
        "durum": durum or None,
        "etiket": _STATE_ETIKET.get(durum) or _TUR_ETIKET.get(tur or "", "") or None,
        "kapanis": _gercek(_alan(cift, "candle_close_price") or _alan(cift, "close_price")),
    }


# ------------------------------------------------------------------- çizim yolu

_PLOT = None      # tembel `matplotlib.pyplot`
_PLT_KURULDU = False


def _pyplot_getir():
    """`matplotlib.pyplot`'u ilk ihtiyaçta yükler (Agg, başsız ortam).

    Neden tembel: `TELEGRAM_GRAFIK=yok` iken bu modülü import eden sürecin (bot,
    testler, CLI) matplotlib/pillow çekmesini istemiyoruz (§7). `MPLCONFIGDIR` de
    burada ayarlanır: ev dizini yazılamayan konteynerlerde ilk import font
    önbelleği yazmaya çalışıp hata veriyor.
    """
    global _PLOT, _PLT_KURULDU
    if _PLOT is None:
        os.environ.setdefault("MPLCONFIGDIR",
                              os.path.join(tempfile.gettempdir(), "formation-bot-mpl"))
        import matplotlib
        if not _PLT_KURULDU:
            matplotlib.use("Agg")
            _PLT_KURULDU = True
        import matplotlib.pyplot as plt
        _PLOT = plt
    return _PLOT


def _kare_olcu(goruntu: Mapping[str, Any]) -> dict[str, Any]:
    """`genislik = clamp(bar × 6 px, 1080, 1440)`, `yukseklik = 810`, dpi 100 (§2)."""
    bar = max(1, len(goruntu.get("zamanlar") or []))
    taban = float(SABITLER["genislik_taban"])
    tavan = float(SABITLER["genislik_tavan"])
    genislik = min(tavan, max(taban, bar * float(SABITLER["bar_px"])))
    px_bar = genislik / bar
    return {"genislik": int(round(genislik)), "yukseklik": int(round(float(SABITLER["yukseklik"]))),
            "bar": bar, "px_bar": px_bar, "cekme": px_bar < float(SABITLER["mum_min_px"])}


def _butce_px(goruntu_genislik: float) -> float:
    """Kare içi tek etiketin tavanı: `etiket_maks_px` ve karenin %28'i (§22 kaydı)."""
    return min(float(SABITLER["etiket_maks_px"]), 0.28 * float(goruntu_genislik))


def _sigar_mi(metin: str, butce_px: float) -> bool:
    return _genislik_16(metin) * float(SABITLER["metin_carpani"]) <= float(butce_px)


def _kirp(metin: str, butce_px: float) -> tuple[str, bool]:
    """Bütçeye sığmayan yazı `…` ile kırpılır; kırpılan meta'ya yazılır (§2.9)."""
    metin = str(metin or "")
    if not metin or _sigar_mi(metin, butce_px):
        return metin, False
    for uzunluk in range(len(metin), 0, -1):
        aday = metin[:uzunluk].rstrip() + "…"
        if _sigar_mi(aday, butce_px):
            return aday, True
    return "…", True


def _yatay_aralik(degerler: Iterable[Optional[float]], ek: Iterable[Optional[float]] = (),
                  mum_genisligi: float = 0.0) -> tuple[float, float]:
    """Çizilen her şeyin min/maksı + %4 pay (§0.13); tek seviyede çökmesin diye taban pay."""
    tum = [float(x) for x in list(degerler) + list(ek)
           if x is not None and math.isfinite(float(x))]
    if not tum:
        return 0.0, 1.0
    alt, ust = min(tum), max(tum)
    aciklik = max(ust - alt, abs(ust) * 0.02, 0.5)
    pay = 0.04 * aciklik
    return alt - pay, ust + pay


def ciz(goruntu: Mapping[str, Any], tf: Optional[str] = None,
        secenekler: Optional[Mapping[str, Any]] = None) -> tuple[Optional[str], dict[str, Any]]:
    """Kareyi üretir: `(png_yolu, meta)`. Yol `None` → görsel yok, metin yine gider.

    Hesap yapmaz (§14.2): girdi `anlik_goruntu()`nun kopyasıdır. Katman hatası
    çizimi durdurmaz: tam çizim denenir, olmazsa "yalnızca mumlar" (çökme modu)
    ve `eksik:` dipnotu (§2.9). Beklenen son bar uyuşmazsa hiç çizmez (§14.3).
    """
    baslangic = time.perf_counter()
    secenekler = dict(secenekler or {})
    tf = str(tf or goruntu.get("tf") or "1h")
    olcu = _kare_olcu(goruntu)
    meta = _meta_kur(goruntu, tf, olcu)
    meta["girdi_ozeti"] = girdi_ozeti(goruntu)

    def bitir(png_yolu: Optional[str]) -> tuple[Optional[str], dict[str, Any]]:
        meta["sure_ms"] = round((time.perf_counter() - baslangic) * 1000, 1)
        return png_yolu, meta

    beklenen = secenekler.get("beklenen_son_bar_ts")
    if beklenen and goruntu.get("son_bar_ts"):
        if _tarih(beklenen) != _tarih(goruntu["son_bar_ts"]):
            meta["uyarilar"] = list(meta["uyarilar"]) + [
                "kaydi: son bar uyuşmadı (tarama → gönderim arasında yeni mum), çizim reddedildi"]
            meta["red"] = True
            return bitir(None)

    if olcu["bar"] < 2:
        meta["uyarilar"] = list(meta["uyarilar"]) + ["kare boş / tek mum: PNG üretilemedi"]
        meta["red"] = True
        return bitir(None)

    hedef = secenekler.get("cikti") or os.path.join(
        tempfile.gettempdir(), f"formation_bot_grafik_{goruntu.get('sembol') or 'sembol'}_{tf}.png")
    ek: dict[str, Any] = {}
    try:
        bayt, ek = _kare_ciz(goruntu, tf, olcu, meta, secenekler, yalnizca_mumlar=False)
    except Exception as hata:
        # §4: görsel hiçbir koşulda alarmı engellemez → hata yutulur, kat çöker.
        log.warning("grafik: tam çizim başarısız (%s: %s)", type(hata).__name__, hata)
        meta["uyarilar"] = list(meta["uyarilar"]) + [
            f"çökme modu: {type(hata).__name__}: {hata}"]
        bayt, ek = None, {"cekme": False, "hata": f"{type(hata).__name__}: {hata}"}
    if bayt is None:
        meta["uyarilar"] = list(meta["uyarilar"]) + ["çökme modu: yalnız mumlar çizildi"]
        try:
            bayt, ek2 = _kare_ciz(goruntu, tf, olcu, meta, secenekler, yalnizca_mumlar=True)
        except Exception as hata:
            log.warning("grafik: çökme modu da başarısız (%s)", hata)
            bayt, ek2 = None, {"hata": f"{type(hata).__name__}: {hata}"}
        ek = {**ek, **ek2, "cekme": True}
    if ek.get("hata"):
        meta["uyarilar"] = list(meta["uyarilar"]) + [f"çizim hatası: {ek['hata']}"]
    meta.update({k: v for k, v in ek.items() if v is not None})
    if bayt is None:
        meta["red"] = True
        return bitir(None)
    try:
        _atom_yaz(str(hedef), bayt)
    except OSError as hata:
        log.warning("grafik: PNG yazılamadı (%s)", hata)
        meta["uyarilar"] = list(meta["uyarilar"]) + [f"PNG yazılamadı: {type(hata).__name__}"]
        meta["red"] = True
        return bitir(None)
    meta["png_kb"] = round(len(bayt) / 1024.0, 1)
    meta["yol"] = str(hedef)
    return bitir(str(hedef))


def _kare_ciz(goruntu: Mapping[str, Any], tf: str, olcu: Mapping[str, Any],
              meta: Mapping[str, Any], secenekler: Mapping[str, Any], *,
              yalnizca_mumlar: bool) -> tuple[Optional[bytes], dict[str, Any]]:
    """Asıl çizim → `(png_baytı, meta_ekleri)`. Dosyaya yazmak `ciz`'in işi."""
    eksik: list[str] = list(meta.get("eksik_katmanlar") or [])
    budama: list[str] = list(meta.get("budama") or [])
    n = int(olcu["bar"])
    etiket_detay = bool(secenekler.get("etiket_detay", SABITLER["etiket_detay"]))
    serit_istendi = bool(secenekler.get("serit", True)) and bool(goruntu.get("serit"))
    plt, fig = None, None
    try:
        plt = _pyplot_getir()
        dpi = int(SABITLER["dpi"])
        genislik, yukseklik = int(olcu["genislik"]), int(olcu["yukseklik"])
        # Alt blok iki kez kurulur: ilki eksen alta ne kadar pay ayıracığını bulmak
        # için, ikincisi ÇİZİM bittikten sonra (bir katmanın çizimi patlarsa `eksik:`
        # yazısı ancak o zaman bilinir — §2.9 dipnotu bu yüzden sondan kurulur).
        metin = _metinler(goruntu, meta, genislik, eksik, yalnizca_mumlar, etiket_detay)
        ust = 0.855 if metin["satirlar"] else 0.885
        sol_kenar, sag_kenar = 0.075, 0.985
        alt, y_lejant, _, _ = _alt_yerlesim(len(metin["dipnotlar"]) + 2,
                                           len(metin.get("notlar") or []),
                                           len(metin["lejant"]))
        alt_yerlesimi = y_lejant

        fig = plt.figure(figsize=(genislik / float(dpi), yukseklik / float(dpi)), dpi=dpi)
        fig.patch.set_facecolor(PALET["zemin"])
        if serit_istendi:
            from matplotlib.gridspec import GridSpec
            oran = max(0.08, min(0.30, float(SABITLER["serit_kulvar_orani"]) / (1.0 - float(SABITLER["serit_kulvar_orani"]))))
            gs = GridSpec(2, 1, height_ratios=[1.0, oran], hspace=0.05,
                          left=sol_kenar, right=sag_kenar, top=ust, bottom=alt, figure=fig)
            ax = fig.add_subplot(gs[0])
            ax_serit = fig.add_subplot(gs[1], sharex=ax)
        else:
            ax = fig.add_axes([sol_kenar, alt, sag_kenar - sol_kenar, ust - alt])
            ax_serit = None
        for a in (ax, ax_serit):
            if a is None:
                continue
            a.set_facecolor(PALET["zemin"])
            a.tick_params(colors=PALET["eksen"], labelsize=SABITLER["eksen_pt"], length=0, pad=2)
            for kenar in a.spines.values():
                kenar.set_color(PALET["grid"])
                kenar.set_linewidth(0.6)
        for a, adlar in ((ax, ("top", "right")), (ax_serit, ("top", "right", "bottom"))):
            if a is None:
                continue
            for ad in adlar:
                a.spines[ad].set_visible(False)
        if ax_serit is not None:
            ax.tick_params(labelbottom=False)

        zamanlar = list(goruntu.get("zamanlar") or [])[:n]
        acilis, yuksek, dusuk, kapanis = (list(goruntu["acilis"][:n]), list(goruntu["yuksek"][:n]),
                                         list(goruntu["dusuk"][:n]), list(goruntu["kapanis"][:n]))
        formasyon = goruntu.get("formasyon") or {}
        alarm = goruntu.get("alarm") or {}
        ek_y: list[float] = []
        for ad in ("upper_now", "lower_now"):
            if formasyon.get(ad) is not None:
                ek_y.append(float(formasyon[ad]))
        if alarm.get("deger") is not None:
            ek_y.append(float(alarm["deger"]))
        zone = goruntu.get("zone") or {}
        for b in (zone.get("cizilen") or []):
            ek_y.extend([float(b["alt"]), float(b["ust"])])
        # yapı uçları da aralığa girsin: swing noktası / kritik çizgisi kesilmesin
        _olay_src = goruntu.get("olay") or {}
        for b in (list(_olay_src.get("swinglar") or []) + list(_olay_src.get("olaylar") or [])):
            v = _gercek(b.get("fiyat") if b.get("fiyat") is not None else b.get("seviye"))
            if v is not None:
                ek_y.append(v)
        if (_olay_src.get("kritik") or {}).get("seviye") is not None:
            ek_y.append(float(_olay_src["kritik"]["seviye"]))
        aralik = _yatay_aralik(kapanis + yuksek + dusuk, ek_y)
        ax.set_ylim(*aralik)
        meta["kare"]["y_araligi"] = [round(aralik[0], 6), round(aralik[1], 6)]
        # Bölge etiketleri sağa taşabiliyor → eksene NEFES PAYI eklenir (veri
        # kırpılmaz; son mum her zaman görünür kalır, §0.13).
        sag_bosluk = 6.0 if (zone.get("cizilen") or []) else 0.0
        ax.set_xlim(-0.6, n - 0.4 + sag_bosluk)
        meta["kare"]["x_siniri"] = [-0.6, round(n - 0.4 + sag_bosluk, 3)]
        butce = _butce_px(genislik)
        cap = max(0.6, olcu["px_bar"] * float(SABITLER["mum_genislik_orani"]))

        # --- bölge kutuları mumların ARDINDA (bilgi zemini; §0.4.1) ---
        if not yalnizca_mumlar and (zone.get("cizilen") or []):
            try:
                meta["zone"]["etiket_atlandi"] = _zone_ciz(ax, zone, n, aralik)
            except Exception as hata:
                log.warning("grafik: bölge katmanı çizilemedi (%s)", hata)
                eksik.append("zone")

        # --- yapı katmanı: swing + BOS/CHoCH + kritik (§2.2) ---
        olay_ozet = {"swing": 0, "etiket_atlandi": 0, "kritik": 0, "kritik_atlandi": 0,
                     "capa": 0}
        if not yalnizca_mumlar and (goruntu.get("olay") or {}):
            try:
                olay_ozet.update(_olay_ciz(ax, goruntu, n) or {})
            except Exception as hata:
                log.warning("grafik: yapı katmanı çizilemedi (%s)", hata)
                eksik.append("ms")
                olay_ozet["hata"] = "cizim"
        meta["olay"] = _olay_meta(goruntu.get("olay"), olay_ozet)
        # `cizgiler["kritik"]` §2'nin seviye sözleşmesidir: çizgi GERÇEKTEN çizildiyse
        # sayısı taşır (alarm çizgisiyle çakışıp çizilmediyse None kalır).
        _kritik = (goruntu.get("olay") or {}).get("kritik") or {}
        meta["cizgiler"]["kritik"] = (_gercek(_kritik.get("seviye"))
                                      if meta["olay"].get("kritik_cizildi") else None)

        # --- mumlar: yükselen içi boş, düşen dolu (§0.4.1) ---
        if olcu["cekme"] or yalnizca_mumlar:
            _cizgi_ve_alan(ax, kapanis, aralik)
            budama.append(("çizgi + alan: %.1f px/bar < %g (§17.14)"
                           % (olcu["px_bar"], SABITLER["mum_min_px"])) if olcu["cekme"]
                          else "çizgi + alan: katman hatası (çökme modu)")
        else:
            _mumlar_ciz(ax, acilis, yuksek, dusuk, kapanis, cap, aralik)

        if not yalnizca_mumlar:
            try:
                _formasyon_ciz(ax, goruntu, n, butce, metin)
            except Exception as hata:
                log.warning("grafik: formasyon katmanı çizilemedi (%s)", hata)
                eksik.append("formasyon")
            try:
                _alarm_ciz(ax, alarm, n, butce)
            except Exception as hata:
                log.warning("grafik: alarm katmanı çizilemedi (%s)", hata)
                eksik.append("alarm")
        else:
            eksik = sorted(set(eksik) | {"formasyon", "alarm", "temas"})

        _tik_etiketleri(ax, zamanlar, str(goruntu.get("tf") or tf))
        ax.yaxis.grid(True, linestyle=":", color=PALET["grid"],
                      linewidth=SABITLER["cizgi_kalinlik"]["grid"])
        ax.set_axisbelow(True)
        from matplotlib.ticker import FuncFormatter
        ax.yaxis.set_major_formatter(FuncFormatter(lambda _v, _p: sayi(_v)))
        # `acik` = kulvar gerçekten çizildi mi (`--serit-yok`/katman hatası → False)
        meta["serit"]["acik"] = ax_serit is not None
        if ax_serit is not None:
            _serit_ciz(ax_serit, goruntu, n)
        metin = _metinler(goruntu, meta, genislik, eksik, yalnizca_mumlar, etiket_detay)
        _, _, y_gri, y_kirmizi = _alt_yerlesim(len(metin["dipnotlar"]),
                                              len(metin.get("notlar") or []),
                                              len(metin["lejant"]))
        # Gri/kırmızı blok LEJANT bloğunun ALTINA başlar: çok satırlı lejant ile
        # dipnot çakışması ölçüldü (0,0215 adımla 0,0235 adımlık rezerv uyuşmuyordu).
        _lejant_uzunluk = max(1, len(metin["lejant"]))
        _taban = alt_yerlesimi - _ALT_ADIM * (_lejant_uzunluk - 1)
        metin["_y"] = {"lejant": alt_yerlesimi,
                       "gri": [_taban - _ALT_ADIM * (i + 1) for i in range(len(y_gri))],
                       "kirmizi": [_taban - _ALT_ADIM * (len(y_gri) + i + 1)
                                   for i in range(len(y_kirmizi))]}
        _metin_ciz(fig, metin, sol_kenar, sag_kenar, ust)

        tampon = io.BytesIO()
        fig.savefig(tampon, format="png", dpi=dpi, facecolor=PALET["zemin"],
                    metadata={"Software": None})    # §6.5: bayt kararlılığı
        bayt = tampon.getvalue()
    except Exception as hata:
        log.warning("grafik: çizim başarısız (%s: %s)", type(hata).__name__, hata)
        if yalnizca_mumlar:
            return None, {"cekme": False, "hata": f"{type(hata).__name__}: {hata}"}
        return None, {"cekme": False, "hata": f"{type(hata).__name__}: {hata}",
                      "eksik_katmanlar": sorted(set(eksik) | {"cizim"}), "budama": budama}
    finally:
        if plt is not None and fig is not None:
            try:
                plt.close(fig)      # §6.5: RAM büyümesin
            except Exception:  # pragma: no cover
                pass

    return bayt, {"eksik_katmanlar": sorted(set(eksik)), "budama": budama,
                  "lejant_satir": len(metin["lejant"]),
                  "lejant_atlanan": int(metin.get("lejant_atlanan") or 0),
                  "metin": metin, "cekme": bool(yalnizca_mumlar or olcu["cekme"]),
                  "serit_acik": serit_istendi, "hata": None}


def _mumlar_ciz(ax, acilis, yuksek, dusuk, kapanis, cap: float,
                aralik: Sequence[float]) -> None:
    """Fitil + gövde. Gövde yüksekliği sıfır olan (açılış=kapanış) mum görünür kalsın."""
    min_govde = max((aralik[1] - aralik[0]) * 0.0015, 1e-9)
    for i in range(len(kapanis)):
        a, k, y, d = acilis[i], kapanis[i], yuksek[i], dusuk[i]
        if None in (a, k, y, d):
            continue
        yukselen = k >= a
        renk = PALET["mum_yukselen"] if yukselen else PALET["mum_dusen"]
        ax.plot([i, i], [d, y], color=renk, linewidth=max(0.6, cap * 0.16),
                solid_capstyle="butt", zorder=2)
        taban, tavan = sorted((a, k))
        ax.bar([i], [max(tavan - taban, min_govde)], bottom=taban, width=cap,
               facecolor=(PALET["zemin"] if yukselen else renk), edgecolor=renk,
               linewidth=0.9, zorder=3)


def _cizgi_ve_alan(ax, kapanis, aralik: Sequence[float]) -> None:
    """Çökme/`çizgi modu`: kapanış çizgisi + basamaklı alan (§17.8 denemesi)."""
    xs = [i for i, v in enumerate(kapanis) if v is not None]
    if not xs:
        return
    ys = [kapanis[i] for i in xs]
    ax.plot(xs, ys, color=PALET["mum_yukselen"], linewidth=0.9, zorder=3)
    ax.fill_between(xs, aralik[0], ys, step="mid", color=PALET["golge"], alpha=0.05, zorder=1)


def _zone_ciz(ax, zone: Mapping[str, Any], n: int, aralik: Sequence[float]) -> int:
    """→ yerleşemeyen etiket sayısı (0 = hepsi çizildi)."""
    """OB/FVG/engulfing kutuları: §0.4.1 renkleri, §0.12r kalın kenar, §0.12k doluluk.

    Kalın kenar boğada ALT, ayıda ÜST kenarda (boğa/ayı ayrımı renk değiştirmeden
    okunsun). Dolgu, kutu görünür aralığın %18'ini aşarsa seyrekleşir (§17.6);
    doluluk yazısı YALNIZ motorun verdiği kutuda (`fill` / `close_fill_ratio`) —
    yoksa kutu kontur kalır ve `%` uydurulmaz. Durum adı tanınmıyorsa kontur.
    """
    from matplotlib.patches import Rectangle

    renk = {"ob": PALET["ob"], "fvg": PALET["fvg"], "eng": PALET["engulf"]}
    etiket = {"ob": "OB", "fvg": "FVG", "eng": "ENG"}
    gorunur = max(1e-9, float(aralik[1]) - float(aralik[0]))
    dolgu = SABITLER["doldurma"]
    kalinlik = SABITLER["zone_kalinlik"]
    for b in (zone.get("cizilen") or []):
        alt, ust = float(b["alt"]), float(b["ust"])
        x0, x1 = int(b.get("x0") or 0), int(b.get("x1", n - 1))
        genislik_cizgi = max(1.0, x1 - x0 + 1.0)
        yukseklik = max(ust - alt, gorunur * 0.0015)
        durum = str(b.get("durum") or "")
        if b["tip"] == "eng":
            saydam, tarama = 0.0, None
        elif yukseklik / gorunur > float(dolgu["golge_esik_orani"]):
            saydam, tarama = float(dolgu["ince"]), ("/" if b["tip"] == "fvg" else None)
        elif durum and durum not in _BOLGE_DOLU:
            saydam = float(dolgu["ob"] if b["tip"] == "ob" else dolgu["fvg"]) * 0.5
            tarama = "/" if (durum in _BOLGE_ARA or b["tip"] == "fvg") else "\\"
        else:
            saydam = float(dolgu["ob"] if b["tip"] == "ob" else dolgu["fvg"])
            tarama = None
        ax.add_patch(Rectangle((x0 - 0.5, alt), genislik_cizgi, yukseklik,
                               facecolor=renk[b["tip"]], alpha=saydam,
                               edgecolor=renk[b["tip"]], linewidth=float(kalinlik["kenar"]),
                               linestyle=(0, (4, 3)) if b["tip"] == "eng" else "solid",
                               hatch=tarama, zorder=1))
        y_vurgu = alt if b.get("vurgu", "alt") == "alt" else ust   # §0.12r
        ax.plot([x0 - 0.5, x0 - 0.5 + genislik_cizgi], [y_vurgu, y_vurgu],
                color=renk[b["tip"]], linewidth=float(kalinlik["vurgu"]),
                solid_capstyle="butt", zorder=2)
    # Etiketler ayrı turda: iç içe kutularda yazılar çakışabiliyor (§0.13 okunur
    # kalmalı), en yakın kutunun etiketi önce yerleşir.
    return _zone_etiketleri(ax, zone)


def _yazi_olcu(ax) -> Optional[tuple[float, float, float, float, float]]:
    """(px/bar, px/birim, x_sol, y_alt, punto) — eksen ölçüsü.

    `ax.get_position()` × figür pikseli; `transData` çizim turundan ÖNCE
    yerleşimi yansıtmıyor (ölçüm: 2,8 birimlik fark 6 px çıkıyordu).
    """
    try:
        rect = ax.get_position()
        fig = ax.figure
        boyut = fig.get_size_inches()
        dpi = float(fig.dpi)
        x_sol, x_sag = (float(v) for v in ax.get_xlim())
        y_alt, y_ust = (float(v) for v in ax.get_ylim())
        pt = float(SABITLER["zone_yazi_pt"]) * dpi / 72.0
        return (float(boyut[0]) * dpi * float(rect.width) / max(1e-9, x_sag - x_sol),
                float(boyut[1]) * dpi * float(rect.height) / max(1e-9, abs(y_ust - y_alt)),
                x_sol, min(y_alt, y_ust), pt)
    except Exception:
        return None


def _yazi_yerlestir(ax, adaylar: Sequence[tuple[float, float, str, str]]) -> int:
    """(x_bar, y_fiyat, metin, renk) listesinde çakışmayanları yazar; atlananı sayar.

    Yazı atlamak bilgiyi gizlemez: işaretin kendisi (kutu/marker/çizgi) çizili
    kalır, sayı meta'ya yazılır. Ölçü alınamazsa filtre kapatılır ve hepsi
    yazılır — yanlış eleme, üst üste binmeden daha kötü.
    """
    olcu = _yazi_olcu(ax)
    if olcu is None:
        for x, y, metin, renk in adaylar:
            ax.annotate(metin, xy=(x - 0.2, y), xytext=(1, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=float(SABITLER["zone_yazi_pt"]),
                        color=renk, zorder=7, annotation_clip=False)
        return 0
    px_bar, px_birim, x_sol, y_alt, pt = olcu
    yerlesim: list[tuple[float, float, float, float]] = []
    atlanan = 0
    for x, y, metin, renk in adaylar:
        px = (x - x_sol) * px_bar
        py = (y - y_alt) * px_birim
        genislik = _genislik_16(metin) * 1.02 + 2.0 * pt * 0.8
        yukseklik = pt * 1.45 + 2.0 * pt * 0.8
        kutu = (px, py - yukseklik / 2.0, px + genislik, py + yukseklik / 2.0)
        if any(not (kutu[2] < q[0] or kutu[0] > q[2] or kutu[3] < q[1] or kutu[1] > q[3])
               for q in yerlesim):
            atlanan += 1
            continue
        yerlesim.append(kutu)
        ax.annotate(metin, xy=(x - 0.2, y), xytext=(1, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=float(SABITLER["zone_yazi_pt"]),
                    color=renk, zorder=7, annotation_clip=False,
                    bbox=dict(facecolor=PALET["zemin"], edgecolor="none", alpha=0.8, pad=0.8))
    return atlanan


def _zone_etiketleri(ax, zone: Mapping[str, Any]) -> int:
    """Kutu etiketlerini çakışmayacak şekilde yerleştirir; yerleşmeyeni sayar.

    TEK etiket kutunun SOL kenarına yazılır (`OB↑ %70`, `FVG↑ q93`). İç içe
    kutularda yazılar çakışabiliyor → `cizilen` sırası (en yakın önce) denenir,
    çakışan yazı ATLANIR; kutunun kendisi, dolgusu ve kalın kenarı yine çizili
    olduğundan bilgi gizlenmez, sayı `meta["zone"]["etiket_atlandi"]` ile okunur.
    Ölçü hesabı `_yazi_yerlestir`de (`get_position()` × figür pikseli; `transData`
    çizim turundan önce güvenilmez — ölçüm: 2,8 birim = 6 px).
    """
    adaylar: list[tuple[float, float, str]] = []
    ad = {"ob": "OB", "fvg": "FVG", "eng": "ENG"}
    for b in (zone.get("cizilen") or []):
        x0 = float(int(b.get("x0") or 0))
        parca = []
        if b.get("doluluk") is not None:
            parca.append(f"%{sayi(float(b['doluluk']) * 100.0, 0)}")
        if b.get("skor") is not None and b["tip"] != "ob":
            parca.append(f"q{int(round(float(b['skor'])))}")
        metin = f"{ad.get(b['tip'], b['tip'])}{'↑' if int(b['yon']) >= 0 else '↓'}"
        if parca:
            metin += " " + " ".join(parca)
        adaylar.append((x0, (float(b["alt"]) + float(b["ust"])) / 2.0, metin))

    # Ölçü/çakışma hesabı ortak: `_yazi_yerlestir` (ölçü alınamazsa orada filtre kapanır).

    return _yazi_yerlestir(ax, [(x0, y, metin, PALET["metin"]) for x0, y, metin in adaylar])


def _formasyon_ciz(ax, goruntu: Mapping[str, Any], n: int, butce: float,
                   metin: dict[str, Any]) -> None:
    """Bant sınırları + son muma projeksiyon + start/bitiş/apex + temas işaretleri.

    Neden yatay çizgi: motorun bant değeri `upper_now/lower_now` "şu an"ki
    değerdir; geçmişteki eğimi yalnız `upper_slope/lower_slope` veriyor ve birim
    dönüşümünü (TL/mum) yeniden üretmek §2'nin "hesap yapma" yasağını ihlal
    eder. Bu yüzden sınır solda `start_bar`'dan itibaren düz çizilir ve
    `eğim` yazısı gerçek sayıyla etiketlenir (uydurma geometri yok).
    """
    formasyon = goruntu.get("formasyon") or {}
    ust, alt = formasyon.get("upper_now"), formasyon.get("lower_now")
    if ust is None and alt is None:
        # Formasyon kaydı hiç yoksa bu bir hata değil (kare mumlardan oluşur);
        # kayıt var ama bant sayısı yoksa §2.9 gereği `eksik: formasyon` yazılır.
        if formasyon:
            raise ValueError("bant verisi yok")
        return
    sol = int(goruntu.get("sol") or 0)
    bas = formasyon.get("start_bar")
    x0 = 0
    if bas is not None and bas - sol >= 0:
        x0 = min(int(bas) - sol, max(0, n - 1))
    kalin = SABITLER["cizgi_kalinlik"]["formasyon"]
    for deger in (ust, alt):
        if deger is None:
            continue
        ax.plot([x0, n - 1], [float(deger), float(deger)], color=PALET["formasyon"],
                linewidth=kalin, solid_capstyle="butt", zorder=4)
        if x0 > 0:      # projeksiyon değil: bant öncesi yok → kesikli uzantı (§0.12e)
            ax.plot([0, x0], [float(deger), float(deger)], color=PALET["formasyon"],
                    linewidth=SABITLER["cizgi_kalinlik"]["projeksiyon"],
                    linestyle=(0, (3, 3)), alpha=0.75, zorder=4)
    # başlangıç / bitiş / apex işaretleri (§2.3) — mumun KAPANIŞına sabitlenir,
    # fiyatta hiçbir hesap üretilmez (ofset yalnız piksel cinsindendir).
    for isaret_kaydi in (goruntu.get("isaretler") or []):
        i = int(isaret_kaydi["bar"]) - sol
        if not (0 <= i < n):
            continue
        isaret = {"bant başlangıcı": "s", "bant bitişi": "D", "apex": "x"}[isaret_kaydi["ad"]]
        deger = isaret_kaydi["y"]
        if deger is None:
            continue
        ax.annotate("", xy=(i, float(deger)), xytext=(0, -9 if isaret == "s" else 9),
                    textcoords="offset points",
                    arrowprops=dict(arrowstyle="-", color=PALET["formasyon"], lw=0.7,
                                    shrinkA=0, shrinkB=0, alpha=0.7), zorder=6)
        ax.plot([i], [float(deger)], marker=isaret, markersize=float(SABITLER["isaret_boyut"]),
                linestyle="None", markerfacecolor=PALET["formasyon"],
                markeredgecolor=PALET["zemin"], markeredgewidth=0.7, zorder=6)
    # temas mumları (§2.4): `o` + sayı. Kalabalıksa en yeni N tanesi çizilir ve
    # budama meta'ya yazılır — sayının kendisi hiçbir zaman saklanmaz.
    temas = [int(i) for i in (goruntu.get("temas") or []) if 0 <= int(i) < n]
    isaretlenecek = [int(i) for i in (goruntu.get("temas_isaret") or temas) if 0 <= int(i) < n]
    yuksekler = goruntu.get("yuksek") or []
    for i in isaretlenecek:
        y = yuksekler[i] if i < len(yuksekler) else None
        if y is None:
            continue
        ax.plot([i], [float(y)], marker="o", markersize=float(SABITLER["temas_radyus"]),
                linestyle="None", fillstyle="none", markeredgecolor=PALET["temas"],
                markeredgewidth=0.8, zorder=5)
    if temas or ust is not None:
        parcalar = [f"bant teması {len(temas)}"]
        for ad, anahtar in (("üst", "upper_touches"), ("alt", "lower_touches")):
            if formasyon.get(anahtar) is not None:
                parcalar.append(f"kart {ad} {int(formasyon[anahtar])}")
        etiket, kirp = _kirp(" · ".join(parcalar), butce)
        ax.annotate(etiket, xy=(n - 1, ax.get_ylim()[1]), xytext=(-3, -2),
                    textcoords="offset points", ha="right", va="top",
                    fontsize=SABITLER["etiket_pt"], color=PALET["temas"], zorder=7,
                    # opak kutu: satır bandın SAĞ kesikli kenarının üstünden geçiyor
                    # (ölçüm: 4s karesinde „kart alt 4" çizginin içinde kayboluyordu);
                    # yarı saydam zemin çizgiyi metnin içine basıyordu.
                    bbox=dict(facecolor=PALET["zemin"], edgecolor="none", alpha=0.95,
                              pad=1.4))
        if kirp:
            metin.setdefault("kesilen", []).append(etiket)


def _lejant_satirlar(oge: Sequence[str], kare_genislik: float) -> tuple[list[str], float, int]:
    """Lejantı kareye sığdır: (satırlar, punto, düşürülen madde sayısı).

    Ölçüm kartla aynı metrikten (`telegram_measure`) yapılır, sonra kare ölçeğine
    çevrilir. Sırasıyla: punto küçült (9,0→7,0), sonra `bol()` ile satırlara böl
    (en fazla 2), en son düşük öncelikli maddeleri düşür. Düşürülen madde sayısı
    kareye yazılır ve `meta`'ya geçer — kare, çizdiği şeyin adını saklamaz.
    """
    from telegram_measure import bol as _bol
    butce = kare_genislik * 0.94 / float(SABITLER["metin_carpani"])
    oge = [str(x) for x in oge if x]
    atlanan = 0
    for punto in (float(SABITLER["lejant_pt"]), 8.5, 8.0, 7.5, 7.0):
        metin = " · ".join(oge)
        if _genislik_16(metin) <= butce:
            return [metin], punto, atlanan
        satirlar = [s.strip() for s in _bol(metin, butce)]
        if len(satirlar) <= 2:
            return satirlar, punto, atlanan
    while len(oge) > 2 and _genislik_16(" · ".join(oge)) > butce * 1.02:
        oge = oge[:-1]
        atlanan += 1
    if atlanan:
        oge = list(oge) + [f"+{atlanan} madde sığmadı"]
    return _bol(" · ".join(oge), butce)[:2], 7.0, atlanan


_ALT_ADIM = 0.0235      # kare altındaki yazı bloğunun satır adımı (figür kesiri)


def _alt_yerlesim(kirmizi: int, gri: int, lejant_satir: int = 1) -> tuple[float, float, list[float], list[float]]:
    """Kare altındaki yazı bloğunun yerleşimi: lejant → gri notlar → kırmızı uyarılar.

    Neden tek yer: lejant ile dipnotların üst üste binmesi ilk çizimde görüldü;
    aks payı artık burada hesaplanır, eksen alta oraya göre çekilir.
    """
    adim = _ALT_ADIM
    y_lejant = 0.046 + adim * (kirmizi + gri + max(0, lejant_satir - 1))
    y_gri = [y_lejant - adim * (i + 1) for i in range(gri)]
    y_kirmizi = [y_gri[-1] - adim * (i + 1) if gri else y_lejant - adim * (i + 1)
                 for i in range(kirmizi)]
    alt = round(y_lejant + 0.026, 4)
    return alt, y_lejant, y_gri, y_kirmizi


def _alarm_ciz(ax, alarm: Mapping[str, Any], n: int, butce: float) -> None:
    """Alarm mumu: kesikli düşey çizgi; seviye: kesiksiz/kısa kesikli yatay çizgi (§2.6)."""
    if not alarm:
        return
    anahtar = _ALARM_KALIN.get(str(alarm.get("durum") or ""),
                              "alarm_kritik" if alarm.get("tur") == "gecersiz" else "alarm_normal")
    kalin = float(SABITLER["cizgi_kalinlik"].get(anahtar, 1.1))
    bar = alarm.get("bar")
    if bar is not None and 0 <= int(bar) < n:
        ax.axvline(int(bar), color=PALET["alarm"], linestyle=(0, (2, 2)), linewidth=kalin, zorder=5)
    deger = alarm.get("deger")
    if deger is None:
        return
    ax.axhline(float(deger), color=PALET["alarm"], linestyle=(0, (5, 4)), linewidth=kalin, zorder=4)
    parcalar = [f"seviye {sayi(deger)}"]
    if alarm.get("kapanis") is not None:
        parcalar.append(f"kapanış {sayi(alarm['kapanis'])}")
        fark = float(alarm["kapanis"]) - float(deger)
        parcalar.append(("üstünde" if fark >= 0 else "altında") + f" {sayi(abs(fark))}")
    metin, _ = _kirp(" · ".join(parcalar), butce)
    ustte = alarm.get("kapanis") is None or float(alarm["kapanis"]) <= float(deger)
    ax.annotate(metin, xy=(n - 1, float(deger)),
                xytext=(-3, 4 if ustte else -4), textcoords="offset points",
                ha="right", va="bottom" if ustte else "top",
                fontsize=SABITLER["etiket_pt"], color=PALET["metin"], zorder=7,
                bbox=dict(facecolor=PALET["zemin"], edgecolor="none", alpha=0.75, pad=1.2))


def _olay_ciz(ax, goruntu: Mapping[str, Any], n: int) -> dict[str, int]:
    """Yapı katmanı (§2.2): swing işaretleri + BOS/CHoCH okları + `kritik` çizgisi.

    Renkler §0.4.1: `swing` #90a4ae (α: teyitli 1,0 · kırık 0,2 · aday 0,45),
    `olay` #ff8a65. Kalın kenar gibi burada da karar veride: `durum` alanı
    `anlik_goruntu`da okundu. `kritik`, seçilen son olayın `broken_level`ıdır;
    alarm seviyesiyle aynı sayıysa ÇİZİLMEZ (tek çizgi, çift çizgi yanıltmasın)
    ve bu `budama`ya yazılır. `!` işaretleri şeritten gelir (son 15 bar kuralı
    orada), buraya mumların altına çizilir.
    """
    olay = goruntu.get("olay") or {}
    swinglar = list(olay.get("swinglar") or [])
    olaylar = list(olay.get("olaylar") or [])
    alarm = goruntu.get("alarm") or {}
    sayac = {"swing": 0, "etiket": 0, "kritik_atlandi": 0}
    kritik_eslesdi = False
    if not swinglar and not olaylar and not (olay.get("kritik") or {}):
        return sayac
    zamanlar = list(goruntu.get("zamanlar") or [])
    dusuk = [float(v) for v in (list(goruntu.get("dusuk") or [])[:n])]
    adaylar: list[tuple[float, float, str, str]] = []
    for b in swinglar:
        x, y = float(b["bar"]), _gercek(b.get("fiyat"))
        if y is None:
            continue
        alpha = float(SABITLER["yapi_alpha"].get(str(b.get("durum")), 1.0))
        isaret = "^" if b.get("yon") == "ust" else "v"
        ax.plot([x], [y], marker=isaret, ms=4.5, linestyle="none",
                color=PALET["swing"], alpha=alpha, zorder=6)
        sinif = str(b.get("sinif") or "")
        if sinif and b.get("durum") != "kirik":       # kırık swingde yazı okunmaz
            adaylar.append((x, y + (0.0 if b.get("yon") == "ust" else 0.0), sinif,
                            PALET["sinif"]))
        sayac["swing"] += 1
    kritik_bilgi = olay.get("kritik") or {}
    kritik_bar = _tam(kritik_bilgi.get("bar"))
    kritik_seviye = _gercek(kritik_bilgi.get("seviye"))
    kritik_eslesdi = False
    for b in olaylar:
        x, seviye = float(b["bar"]), _gercek(b.get("seviye"))
        if seviye is None:
            continue
        yon_ust = b.get("yon") == "ust"
        etiket = f"{b.get('tur') or 'BOS'}{'↑' if yon_ust else '↓'}"
        vurgu = (kritik_bar is not None and kritik_seviye is not None
                 and int(b["bar"]) == kritik_bar and abs(seviye - kritik_seviye) < 1e-9)
        if vurgu:
            kritik_eslesdi = True
            etiket += f" · kritik {sayi(seviye, 2)}"
        ax.plot([x], [seviye], marker="^" if yon_ust else "v", ms=6.0, linestyle="none",
                color=PALET["olay"], zorder=6)
        ax.plot([x, float(n - 1)], [seviye, seviye], color=PALET["olay"],
                linewidth=1.4 if vurgu else 0.9, linestyle=(0, (3, 2)),
                alpha=0.9 if vurgu else 0.6, zorder=3 if vurgu else 2)
        adaylar.append((x, seviye, etiket, PALET["olay"]))
    # `kritik` = son seçilen olayın seviyesi, yani ZATEN o olayın çizgisidir.
    # Ayrı çizgi çizmek aynı yere iki çizgi koymak olurdu → eşleşen olayın çizgisi
    # kalınlaştırılıp etiketi `... · kritik 67,20` yapılır; ayrı çizgi yalnız
    # olay çizgisi çizilemediğinde (kadraj dışı vb.) devreye girer.
    kritik = olay.get("kritik") or {}
    kritik_cizildi = bool(kritik.get("seviye") is not None)
    if kritik_cizildi and not kritik_eslesdi:
        seviye = float(kritik["seviye"])
        ayni = alarm.get("deger") is not None and abs(float(alarm["deger"]) - seviye) < 1e-9
        if ayni:
            sayac["kritik_atlandi"] = 1
            kritik_cizildi = False
        else:
            ax.axhline(seviye, color=PALET["olay"], linewidth=1.3, linestyle=(0, (6, 3)),
                       alpha=0.85, zorder=3)
            adaylar.append((max(0.0, float(n - 1) - 12.0), seviye,
                            f"kritik {sayi(seviye, 2)}", PALET["olay"]))
    sayac["etiket"] = _yazi_yerlestir(ax, adaylar)
    # `!` (çaba var-sonuç yok, son 15 bar) — şerit katmanının verisinden
    serit = goruntu.get("serit") or {}
    for i in (serit.get("capa") or []):
        if 0 <= int(i) < n:
            y = dusuk[int(i)] if int(i) < len(dusuk) else None
            ax.annotate("!", xy=(float(i), (y if y is not None else 0.0)), xytext=(0, -9),
                        textcoords="offset points", ha="center", va="top", fontsize=9.5,
                        color=PALET["ihlal"], zorder=7, annotation_clip=False)
    return {"swing": sayac["swing"], "etiket_atlandi": sayac["etiket"],
            "kritik": 1 if kritik_cizildi else 0,
            "kritik_atlandi": sayac["kritik_atlandi"], "capa": len(serit.get("capa") or [])}


def _serit_ciz(ax, goruntu: Mapping[str, Any], n: int) -> None:
    """Katılım şeridi kulvarı (G3'te dolar, §2.1): yalnız spike'lar çizilir."""
    serit = goruntu.get("serit") or {}
    degerler = [None if v is None else float(v) for v in list(serit.get("degerler") or [])[:n]]
    ax.set_yticks([])
    # Şerit, mum ekseniyle AYNI x sınırını kullanmalı (dikey hizalama); bölge
    # etiketleri için ayrılan nefes payı burada da korunur (§0.13).
    zone_pay = 6.0 if ((goruntu.get("zone") or {}).get("cizilen") or []) else 0.0
    ax.set_xlim(-0.6, n - 0.4 + zone_pay)
    if not any(v is not None for v in degerler):
        return
    esik = float(serit.get("esik") or SABITLER["serit_esik"])
    # `spike` anlık görünümde seçildi (eşik + en sert `serit_maks`); çizim yeniden
    # eleme yapmaz — §14.2 (hesap yok, kopya var).
    spike = [int(i) for i in (serit.get("spike") or []) if 0 <= int(i) < len(degerler)]
    taban = max((v for v in degerler if v is not None), default=1.0)
    ax.set_ylim(0.0, max(esik * 1.15, taban * 1.25))
    if spike:
        ax.bar(spike, [degerler[i] for i in spike], width=0.62, color=PALET["serit"], zorder=3)
    for i in (serit.get("yildiz") or []):
        if 0 <= int(i) < len(degerler) and degerler[int(i)] is not None:
            ax.annotate("▲", xy=(float(i), degerler[int(i)]), xytext=(0, 2),
                        textcoords="offset points", ha="center", va="bottom", fontsize=7.5,
                        color=PALET["serit"], zorder=6)
    tepe = _gercek(serit.get("tepe"))
    if tepe is not None and spike:
        # TEK sayı etiketi (§17.3): en sert spike'ın çarpanı, her bara yazılmaz.
        ax.annotate(f"×{sayi(tepe, 1)}", xy=(float(max(spike, key=lambda i: degerler[i])), tepe),
                    xytext=(0, 11), textcoords="offset points", ha="center", va="bottom",
                    fontsize=float(SABITLER["etiket_pt"]), color=PALET["serit"], zorder=7,
                    annotation_clip=False)
    ax.axhline(esik, color=PALET["serit"], linestyle=":", linewidth=0.8, alpha=0.7)


def _tik_etiketleri(ax, zamanlar: Sequence[Optional[datetime]], tf: str) -> None:
    """Tick'ler seans/ay BAŞLARINDAN, en fazla 8 etiket (§17.7).

    Zaman ekseni çizilmez (§2): ölçümde 360 barın 32 aralığı 16 s (gece), 7'si
    64 s (hafta sonu) → süre ölçeği kadrajı ~%40 yiyordu; bar indeksi + seyrek
    seans etiketi hem doğru hem ucuz. Saat yazılmıyor: seans başı zaten sabit
    (09:30) ve her etikette tekrarlamak yer israfı. `1g` karesinde ay başları.
    """
    gunluk = str(tf) == "1d"
    aday: list[tuple[int, str]] = []
    onceki_anahtar: Optional[tuple] = None
    for i, dt in enumerate(zamanlar):
        if dt is None:
            continue
        anahtar = (dt.year, dt.month) if gunluk else (dt.year, dt.month, dt.day)
        if anahtar == onceki_anahtar:
            continue
        onceki_anahtar = anahtar
        aday.append((i, f"{dt.day:02d} {_AY.get(dt.month, '')}"))
    if not aday:
        ax.set_xticks([])
        return
    if len(aday) > 8:
        adim = math.ceil(len(aday) / 8.0)
        aday = [x for j, x in enumerate(aday) if j % adim == 0][:8]
    ax.set_xticks([i for i, _ in aday])
    ax.set_xticklabels([t for _, t in aday], rotation=0, fontsize=SABITLER["eksen_pt"])


def _metinler(goruntu: Mapping[str, Any], meta: Mapping[str, Any], genislik: int,
              eksik: Sequence[str], yalnizca_mumlar: bool,
              etiket_detay: bool = False) -> dict[str, Any]:
    """Başlık + durum satırı + lejant + koşullu dipnotlar (§0.12v/w, §2.9)."""
    formasyon = goruntu.get("formasyon") or {}
    alarm = goruntu.get("alarm") or {}
    n = int(meta.get("mum_sayisi") or 0)
    baslik = f"{goruntu.get('sembol') or '—'} · {goruntu.get('tf_kisa') or goruntu.get('tf')} · {n} mum"
    sag = "son kapanan " + (_tarih_metni(_tarih(goruntu.get("son_bar_ts")))
                           if goruntu.get("son_bar_ts") else "—")
    if goruntu.get("son_kapanis") is not None:
        sag += f" · {sayi(goruntu['son_kapanis'])}"
    satirlar: list[str] = []
    if alarm.get("etiket"):
        satirlar.append(f"alarm: {alarm['etiket']}")
    bilgi: list[str] = []
    if formasyon.get("ad"):
        bilgi.append(str(formasyon["ad"]))
    q = formasyon.get("quality")
    if q is None:
        q = formasyon.get("effective_quality")
    if q is not None:
        bilgi.append(f"q{int(round(float(q)))}")
    if formasyon.get("contraction") is not None:
        # kartla aynı biçim: `notifier.py:309` → `_yuzde(contraction*100, 0)`
        bilgi.append(f"daralma %{sayi(float(formasyon['contraction']) * 100.0, 0)}")
    if alarm.get("deger") is not None:
        bilgi.append(f"seviye {sayi(alarm['deger'])}")
    if bilgi:
        satirlar.append(" · ".join(bilgi))
    if yalnizca_mumlar:
        satirlar = []
    kesilen: list[str] = []
    baslik, k = _kirp(baslik, genislik * 0.52)
    kesilen += [baslik] if k else []
    sag, k = _kirp(sag, genislik * 0.40)
    kesilen += [sag] if k else []
    satirlar2: list[str] = []
    for satir in satirlar:
        yeni, k = _kirp(satir, genislik * 0.88)
        satirlar2.append(yeni)
        if k:
            kesilen.append(yeni)
    satirlar = satirlar2
    detay = str(formasyon.get("evidence_text") or "").strip()
    if detay and not yalnizca_mumlar and etiket_detay:
        satirlar.append(_kirp(detay, genislik * 0.88)[0])
    # §2.9: dipnot YALNIZ veri bozuksa. Kalabalık/budama/gri not satırıdır.
    dipnotlar: list[str] = []
    if eksik:
        dipnotlar.append("eksik: " + " · ".join(sorted(set(eksik))))
    if int(meta.get("hacimsiz_bar") or 0) > 0:
        dipnotlar.append(f"veri: {int(meta['hacimsiz_bar'])} bar hacimsiz")
    for uyari in goruntu.get("uyarilar") or []:
        if uyari and str(uyari) not in dipnotlar:
            dipnotlar.append(str(uyari))
    notlar = [str(b) for b in (goruntu.get("budama") or []) if b]
    serit = goruntu.get("serit") or {}
    if int(serit.get("hacimsiz") or 0) > 0:
        notlar.append(f"veri: {serit['hacimsiz']} bar hacimsiz")
    if serit.get("yetersiz"):
        notlar.append("şerit: geçmiş yetersiz (motor minimum_history=150 düşürülmedi)")
    zone = goruntu.get("zone") or {}
    if int(zone.get("elenen") or 0) > 0:
        kapak = zone.get("kapak") or {}
        notlar.append(f"bölge: {zone['elenen']} kutu kapak dışında "
                      f"(üst {kapak.get('ust')} · alt {kapak.get('alt')})")
    if zone.get("kaynak_disi"):
        notlar.append(f"bölge: {zone['kaynak_disi']} kutunun başlangıcı kadraj dışında")
    notlar += [str(n) for n in (goruntu.get("notlar") or []) if n]
    if yalnizca_mumlar:
        notlar.append("yalnızca mumlar: katman çizilemedi")
    lejantlar, lejant_punto, lejant_atlanan = _lejant_satirlar(
        _lejant(goruntu, yalnizca_mumlar), genislik)
    if lejant_atlanan:
        dipnotlar.append(f"lejant: {lejant_atlanan} madde sığmadı")
    return {"baslik": baslik, "sag": sag, "satirlar": satirlar,
            "lejant": lejantlar, "lejant_punto": lejant_punto,
            "lejant_atlanan": lejant_atlanan,
            "dipnotlar": dipnotlar[:4], "notlar": notlar[:4], "kesilen": kesilen,
            "butce": SATIR_BUTCE, "genislik": genislik}


def _lejant(goruntu: Mapping[str, Any], yalnizca_mumlar: bool) -> list[str]:
    """Çizilen ne ise o (§0.12v); uydurma etiket yok — katman yoksa madde de yok."""
    if yalnizca_mumlar:
        return ["yalnızca mumlar (çökme modu)"]
    formasyon = goruntu.get("formasyon") or {}
    alarm = goruntu.get("alarm") or {}
    oge = ["mum: yalnız kapalı", "boş gövde = yükselen"]
    if formasyon.get("upper_now") is not None or formasyon.get("lower_now") is not None:
        oge.append("— formasyon bandı")
        if int(goruntu.get("sol") or 0) > 0:
            oge.append("┄ bant öncesi")
    if goruntu.get("temas"):
        oge.append("○ bant teması")
    if goruntu.get("isaretler"):
        oge += ["■ bant başlangıcı", "◆ bant bitişi", "✕ apex"]
    if alarm.get("bar") is not None:
        oge.append("│ alarm mumu")
    if alarm.get("deger") is not None:
        oge.append("─ seviye")
    zone = goruntu.get("zone") or {}
    if zone.get("cizilen"):
        _sira = {"ob": 0, "fvg": 1, "eng": 2}
        adlar = sorted({str(b.get("tip")) for b in (zone.get("cizilen") or [])},
                       key=lambda a: _sira.get(a, 9))
        oge.append("kutular (mumların ardında): " + " ".join(
            {"ob": "OB", "fvg": "FVG", "eng": "ENG"}.get(a, str(a)) for a in adlar))
        if str(goruntu.get("tf")) in _FVG_YOK_TFLAR:
            oge.append("FVG · 4s/1g")
    serit = goruntu.get("serit") or {}
    if serit.get("spike"):
        # `yerel hesap` YALNIZ yerel hesaplandığında yazılır (kullanıcı onayı,
        # tur 9); motor serisi gelirse kaynak adı yeter.
        oge.append("şerit: rvol(%s)%s" % (
            sayi(float(serit.get("uzunluk") or SABITLER["hacim_uzunluk"]), 0),
            " · yerel hesap" if serit.get("yerel") else " · motor"))
    olay = goruntu.get("olay") or {}
    if olay.get("swinglar") or olay.get("olaylar"):
        oge.append("yapı: ▲▼ PH/PL · ┄ BOS/CHoCH · ━ kritik")
    return oge


def _metin_ciz(fig, metin: Mapping[str, Any], sol_kenar: float, sag_kenar: float,
               ust: float) -> None:
    """Kare üstü yazı bloğu + altındaki lejant/gri not/kırmızı uyarı satırları."""
    y = 1.0 - 0.032
    fig.text(sol_kenar, y, metin["baslik"], ha="left", va="top", color=PALET["metin"],
             fontsize=SABITLER["baslik_pt"], fontweight="bold")
    fig.text(sag_kenar, y, metin["sag"], ha="right", va="top", color=PALET["eksen"],
             fontsize=SABITLER["durum_pt"])
    y -= 0.040
    for satir in metin["satirlar"]:
        fig.text(sol_kenar, y, satir, ha="left", va="top", color=PALET["eksen"],
                 fontsize=SABITLER["durum_pt"])
        y -= 0.031
    y = metin.get("_y") or {"lejant": 0.055, "gri": [], "kirmizi": []}
    for i, satir in enumerate(metin["lejant"]):
        fig.text(0.5, float(y["lejant"]) - i * _ALT_ADIM, satir, ha="center", va="top",
                 color=PALET["eksen"], fontsize=float(metin.get("lejant_punto",
                                                                SABITLER["lejant_pt"])))
    for i, satir in enumerate(metin.get("notlar") or []):
        fig.text(0.5, float(y["gri"][i]), satir, ha="center", va="top",
                 color=PALET["eksen"], fontsize=SABITLER["dipnot_pt"], alpha=0.85)
    for i, satir in enumerate(metin["dipnotlar"]):
        fig.text(0.5, float(y["kirmizi"][i]), satir, ha="center", va="top",
                 color=PALET["ihlal"], fontsize=SABITLER["dipnot_pt"])


def _serit_verisi(sonuclar: Optional[Mapping[str, Any]], hacimler: Sequence[Any],
                  sol: int, sag: int, n: int) -> dict[str, Any]:
    """Katılım şeridi (§2.1) — kaynak motorun BAR BAR serisi, yoksa yerel rvol.

    `vp.details["metrics_history"]` her bar için `VolumeParticipationMetrics`
    veriyor (ölçüm: 1s 360/360 dolu; `rvol`, `volume_level`, `effort_result_class`
    alanları var). Motor serisi hazır değilse (4s ölçümü: `data_ready=False`,
    export `rvol=None`) `hacim / SMA(hacim, 20)` YEREL hesaplanır ve karede
    `rvol · yerel hesap` yazılır — kullanıcı onayı bu etiketi şart koşuyor.
    Kurallar: yalnız spike (≥ `serit_esik`, en sert `serit_maks`); `▲` yalnız
    motorun `volume_level` dayanağıyla; `!` yalnız son `son_mum_isaret` (15) barda
    `HIGH/VERY_HIGH_EFFORT_WEAK_RESULT`; `hacim ≤ 0` bar çizilmez ve sayılır.
    `minimum_history=150` DÜŞÜRÜLMEZ — o yüzden 4s/1g karesinde motor serisi
    gelmeyebilir; bu "yetersiz geçmiş" olarak bildirilir, eşik düşürülmez.
    Dizinler GÖRÜNÜNE göre döner (`sol` çıkarılır): `_serit_ciz` görünüyü kullanır.
    """
    hacimler = list(hacimler or [])
    n = max(n, len(hacimler))
    uzunluk = int(SABITLER["hacim_uzunluk"])
    rvol_yerel: list[Optional[float]] = [None] * n
    pencere: list[float] = []
    toplam = 0.0
    for i in range(n):
        v = _gercek(hacimler[i]) if i < len(hacimler) else None
        pencere.append(v if v is not None else 0.0)
        toplam += v if v is not None else 0.0
        if len(pencere) > uzunluk:
            toplam -= pencere.pop(0)
        ortalama = toplam / len(pencere) if pencere else 0.0
        if v is not None and ortalama > 0:
            rvol_yerel[i] = v / ortalama

    motor: list[Optional[float]] = []
    seviye: list[str] = []
    capa: list[int] = []
    veri_hazir = False
    vp = (sonuclar.get("volume_participation") if isinstance(sonuclar, Mapping)
          else _alan(sonuclar, "volume_participation")) if sonuclar else None
    if vp is not None:
        try:
            gecmis = list(_alan(_alan(vp, "details", {}) or {}, "metrics_history", ()) or ())
            motor = [None] * len(gecmis)
            seviye = [""] * len(gecmis)
            for i, m in enumerate(gecmis):
                if bool(_alan(m, "data_ready", False)):
                    veri_hazir = True
                motor[i] = _gercek(_alan(m, "rvol"))
                seviye[i] = _ad(_alan(m, "volume_level"))
                if _ad(_alan(m, "effort_result_class")) in ("HIGH_EFFORT_WEAK_RESULT",
                                                            "VERY_HIGH_EFFORT_WEAK_RESULT"):
                    capa.append(i)
        except Exception as hata:
            log.warning("grafik: şerit serisi okunamadı (%s)", hata)
            motor, seviye, capa = [], [], []
    kaynak = ("motor" if (motor and veri_hazir) else
              "yerel hesap" if any(v is not None for v in rvol_yerel) else "yok")
    ham = list(motor) if kaynak == "motor" else list(rvol_yerel)
    ham = (ham + [None] * n)[:n]
    degerler = ham[sol:sag]
    esik = float(SABITLER["serit_esik"])
    tum = [i for i, v in enumerate(degerler) if v is not None and float(v) >= esik]
    spike = sorted(sorted(tum, key=lambda i: (-float(degerler[i]), -i))
                   [: int(SABITLER["serit_maks"])])
    yildiz = [i for i in spike if kaynak == "motor" and (sol + i) < len(seviye)
              and seviye[sol + i] in ("HIGH", "ABNORMAL")]
    capa = [i - sol for i in capa if i >= sag - int(SABITLER["son_mum_isaret"])
            and sol <= i < sag]
    hacimsiz = 0
    for i in range(sol, sag):
        v = _gercek(hacimler[i]) if i < len(hacimler) else None
        if v is None or v <= 0.0:
            hacimsiz += 1
    tepe = max((float(degerler[i]) for i in spike), default=None) if spike else None
    return {"degerler": degerler, "esik": esik, "spike": spike, "yildiz": yildiz,
            "capa": capa, "kaynak": kaynak, "hacimsiz": hacimsiz,
            "yetersiz": kaynak == "yok", "yerel": kaynak == "yerel hesap",
            "tepe": tepe, "elenen_spike": max(0, len(tum) - len(spike)),
            "uzunluk": uzunluk}


def _olay_verisi(sonuclar: Optional[Mapping[str, Any]], sol: int, sag: int,
                 etiket_detay: bool = False) -> dict[str, Any]:
    """Yapı katmanı (§2.2): yalnız EXTERNAL swing'ler + onaylı/geçerli BOS·CHoCH.

    Ölçüm (AKBNK): `external_swings` 1ste 48 · 4s 8; pencereye düşen 10 ve 7 →
    kapak `swing_maks`. `event_history`te EVENT_SWEEP/FALSE_BREAK/TRANSITION_FAIL
    de var (4s dağılımı: BOS 7 · CHoCH 3 · SWEEP 21 · FALSE_BREAK 4 ·
    TRANSITION_FAIL 1) — kart yalnız BOS/CHoCH gösterdiği için filtre:
    `scope==EXTERNAL`, `event_type∈{EVENT_BOS, EVENT_CHOCH}`,
    `confirmation_status==CONFIRMED`, `validity==VALID`, en yeni `olay_maks`.
    `kritik` = seçilen son olayın `broken_level`ı (motor alanı; `origin_level`
    diye bir alan YOK, gerçek ad `origin_price` — §24 düzeltmesi).
    """
    ms = (sonuclar.get("market_structure") if isinstance(sonuclar, Mapping)
          else _alan(sonuclar, "market_structure")) if sonuclar else None
    if ms is None:
        return {}
    try:
        detay = _alan(ms, "details", {}) or {}
    except Exception as hata:
        log.warning("grafik: yapı verisi okunamadı (%s)", hata)
        return {"hata": ["ms"]}
    swinglar: list[dict[str, Any]] = []
    for kaynak_ad, durum in (("external_swings", None), ("external_candidates", "aday")):
        for b in (_alan(detay, kaynak_ad, ()) or ()):
            bar = _tam(_alan(b, "source_bar"))
            if bar is None or not (sol <= bar < sag):
                continue
            ham_durum = _ad(_alan(b, "state"))
            durum_ = durum or ("kirik" if "BROKEN" in ham_durum or _alan(b, "broken")
                               else "teyitli")
            swinglar.append({
                # `bar` ÇİZİM (görünüm) indeksi; `kaynak_bar` çerçeve indeksi
                "bar": bar - sol, "kaynak_bar": bar,
                "onay": (_tam(_alan(b, "confirm_bar")) - sol)
                        if _tam(_alan(b, "confirm_bar")) is not None else None,
                "fiyat": _gercek(_alan(b, "price")),
                "yon": "ust" if _ad(_alan(b, "side")).endswith("HIGH") else "alt",
                "sinif": _ad(_alan(b, "swing_class")), "durum": durum_,
                "rol": _ad(_alan(b, "structural_role")),
                "kalite": _gercek(_alan(b, "quality")),
                "kimlik": _tam(_alan(b, "identity")),
                "kanit": str(_alan(b, "evidence_text") or "") if etiket_detay else ""})
    # en Yeni N: `bar` büyük olan önce; çizim bar sırasına döner
    swinglar.sort(key=lambda b: -int(b["bar"]))
    # `swing_maks` bilinçli olarak yalnız SABİTLER: §5'te sözü verilen env anahtarı
    # `GRAFIK_OLAY_MAKS`tır (kare kalabalığını asıl o belirliyor); swing sayısı onun
    # yarısı kadar bir tavan olarak sabit tutulur — 5. bir anahtar uydurulmaz.
    swing_maks = int(SABITLER["swing_maks"])
    olay_maks = int(_ortam_sayi("GRAFIK_OLAY_MAKS", SABITLER["olay_maks"]))
    elenen = max(0, len(swinglar) - swing_maks)
    swinglar = sorted(swinglar[:swing_maks], key=lambda b: int(b["bar"]))

    olaylar: list[dict[str, Any]] = []
    for b in (_alan(detay, "event_history", ()) or ()):
        if _ad(_alan(b, "scope")) != "EXTERNAL":
            continue
        tur = _ad(_alan(b, "event_type")).replace("EVENT_", "")
        if tur not in ("BOS", "CHOCH"):
            continue
        if _ad(_alan(b, "confirmation_status")) != "CONFIRMED":
            continue
        if _ad(_alan(b, "validity")) != "VALID":
            continue
        bar = _tam(_alan(b, "event_bar"))
        if bar is None:
            continue
        olaylar.append({"bar": bar - sol, "kaynak_bar": bar,
                        "aday_bar": (_tam(_alan(b, "candidate_bar")) - sol)
                        if _tam(_alan(b, "candidate_bar")) is not None else None,
                        "tur": "BOS" if tur == "BOS" else "CHoCH",
                        "yon": "ust" if _ad(_alan(b, "direction")).startswith("UP") else "alt",
                        "seviye": _gercek(_alan(b, "broken_level")),
                        "kimlik": _tam(_alan(b, "identity")),
                        "nitelik": _gercek(_alan(b, "quality")),
                        "yas": _tam(_alan(b, "age_bars")),
                        "kanit": str(_alan(b, "evidence_text") or "") if etiket_detay else ""})
    olaylar.sort(key=lambda b: -int(b["bar"]))
    olay_elenen = max(0, len(olaylar) - olay_maks)
    olaylar = sorted(olaylar[:olay_maks], key=lambda b: int(b["bar"]))
    kritik = None
    if olaylar:
        son_olay = olaylar[-1]
        if son_olay.get("seviye") is not None:
            kritik = {"seviye": son_olay["seviye"], "bar": son_olay["bar"],
                     "kaynak_bar": son_olay.get("kaynak_bar"), "tur": son_olay["tur"],
                     "yon": son_olay["yon"]}
    return {"swinglar": swinglar, "olaylar": olaylar, "kritik": kritik,
            "cizilen": len(swinglar) + len(olaylar), "elenen": elenen + olay_elenen,
            "kapak": {"swing": swing_maks, "olay": olay_maks},
            "hata": []}


def _zone_meta(zone: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """`meta["zone"]`: §2'deki `{cizilen, elenen}` + G2 izleri (test yüzeyi)."""
    # Alanlar her durumda AYNI biçimde döner (§13 JSONL okuyucusu dalgalanmasın):
    # boşsa sayaçlar 0, `sirala` "zone verisi yok" (motorlar hiç çağrılmadı).
    if not zone:
        return {"cizilen": 0, "elenen": 0, "tip": {"ob": 0, "fvg": 0, "eng": 0},
                "kaynak_disi": 0, "kapak": {}, "sirala": "zone verisi yok", "atr": None,
                "hata": [], "kayitlar": [], "etiket_atlandi": 0}
    kayitlar = list(zone.get("cizilen") or [])
    return {"cizilen": len(kayitlar), "elenen": int(zone.get("elenen") or 0),
            "tip": {t: sum(1 for b in kayitlar if b["tip"] == t) for t in ("ob", "fvg", "eng")},
            "kaynak_disi": int(zone.get("kaynak_disi") or 0),
            "kapak": dict(zone.get("kapak") or {}), "sirala": zone.get("sirala"),
            "atr": zone.get("atr"), "hata": list(zone.get("hata") or []),
            "etiket_atlandi": int(zone.get("etiket_atlandi") or 0),
            "kayitlar": [{k: b.get(k) for k in ("tip", "yon", "alt", "ust", "kaynak",
                                                "taraf", "durum", "doluluk", "x0", "x1",
                                                "mesafe", "mesafe_atr", "vurgu")}
                         for b in kayitlar]}


def _olay_meta(olay: Optional[Mapping[str, Any]], ozet: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
    """`meta["olay"]`: §2'deki `{cizilen, elenen}` + G3 izleri (§13 biçimi)."""
    ozet = dict(ozet or {})
    if not olay:
        return {"cizilen": 0, "elenen": 0, "swing": 0, "bos_choc": 0, "kritik": None,
                "kapak": {}, "etiket_atlandi": 0, "kritik_cizildi": False,
                "kritik_atlandi": 0, "capa": 0, "hata": []}
    return {"cizilen": int(olay.get("cizilen") or 0), "elenen": int(olay.get("elenen") or 0),
            "swing": len(olay.get("swinglar") or []),
            "bos_choc": len(olay.get("olaylar") or []),
            "kritik": (olay.get("kritik") or {}).get("seviye"),
            "kapak": dict(olay.get("kapak") or {}),
            "olay_barlari": [b.get("kaynak_bar") for b in (olay.get("olaylar") or [])],
            "etiket_atlandi": int(ozet.get("etiket_atlandi") or 0),
            "kritik_cizildi": bool(ozet.get("kritik")),
            "kritik_atlandi": int(ozet.get("kritik_atlandi") or 0),
            "capa": int(ozet.get("capa") or 0),
            "hata": list(olay.get("hata") or [])}


def _serit_meta(serit: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """`meta["serit"]`: `{acik, esik, spike}` (§2) + kaynak/hacimsiz izleri."""
    if not serit:
        return {"acik": False, "esik": None, "spike": [], "kaynak": "yok", "yerel": False,
                "hacimsiz": 0, "elenen_spike": 0, "capa": 0, "yetersiz": False,
                "uzunluk": None}
    return {"acik": True, "esik": serit.get("esik"), "spike": list(serit.get("spike") or []),
            "kaynak": serit.get("kaynak"), "yerel": bool(serit.get("yerel")),
            "hacimsiz": int(serit.get("hacimsiz") or 0),
            "elenen_spike": int(serit.get("elenen_spike") or 0),
            "capa": len(serit.get("capa") or []), "yetersiz": bool(serit.get("yetersiz")),
            "tepe": serit.get("tepe"), "uzunluk": serit.get("uzunluk")}


def _meta_kur(goruntu: Mapping[str, Any], tf: str, olcu: Mapping[str, Any]) -> dict[str, Any]:
    """§2'deki `meta` iskeleti — testler piksele değil bu sözlüğe bakıyor (§6.1)."""
    formasyon = goruntu.get("formasyon") or {}
    alarm = goruntu.get("alarm") or {}
    return {
        "sem": goruntu.get("sembol") or "",
        "tf": _TF_KISA.get(tf, tf),
        "mum_sayisi": int(olcu["bar"]),
        "bar_basina_px": round(float(olcu["px_bar"]), 2),
        "temas": [int(i) for i in (goruntu.get("temas") or [])],
        "temas_isaret": [int(i) for i in (goruntu.get("temas_isaret") or [])],
        "isaretler": [{"ad": x["ad"], "bar": x["bar"]} for x in (goruntu.get("isaretler") or [])],
        "cizgiler": {
            "formasyon_ust": formasyon.get("upper_now"),
            "formasyon_alt": formasyon.get("lower_now"),
            "alarm": {"deger": alarm.get("deger"), "tur": alarm.get("tur"),
                      "etiket": alarm.get("etiket"), "bar": alarm.get("bar"),
                      "durum": alarm.get("durum"), "kapanis": alarm.get("kapanis"),
                      "bar_disarida": bool(alarm.get("bar_disarida"))},
            "kritik": None,        # G3 (§0.12f)
        },
        "zone": _zone_meta(goruntu.get("zone")),
        "olay": _olay_meta(goruntu.get("olay")),
        "serit": _serit_meta(goruntu.get("serit")),
        "budama": list(goruntu.get("budama") or []),
        "notlar": list(goruntu.get("notlar") or []),
        "eksik_katmanlar": sorted(set(goruntu.get("eksik_katmanlar") or [])),
        "hacimsiz_bar": int(goruntu.get("hacimsiz_bar") or 0),
        "son_bar_ts": goruntu.get("son_bar_ts"),
        "kare": {"genislik": int(olcu["genislik"]), "yukseklik": int(olcu["yukseklik"]),
                 "sol": goruntu.get("sol"), "sag": goruntu.get("sag"),
                 "dpi": int(SABITLER["dpi"]), "cekme": bool(olcu["cekme"])},
        "uyarilar": list(goruntu.get("uyarilar") or []),
        "red": False,
        "surum": 1,
    }


def _atom_yaz(yol: str, veri: bytes) -> None:
    """Geçici dosyaya yaz + `os.replace` (§0.12p: kare /tmp'de üretilir).

    Neden atomik: gönderici kuyruğu dosyayı okurken yarı yazılmış PNG görmesin.
    """
    klasor = os.path.dirname(os.path.abspath(yol)) or "."
    os.makedirs(klasor, exist_ok=True)
    gecici = os.path.join(klasor, f".{os.path.basename(yol)}.{os.getpid()}.tmp")
    with open(gecici, "wb") as akis:
        akis.write(veri)
    os.replace(gecici, yol)


def girdi_ozeti(goruntu: Mapping[str, Any]) -> str:
    """Aynı girdi → aynı özet (§6.5: determinizm piksel hash'inde değil, meta'da)."""
    parcalar = [f"{ad}={goruntu.get(ad)}" for ad in
                 ("surum", "sembol", "tf", "son_bar_ts", "son_kapanis", "sol", "sag",
                  "bar_sayisi", "hacimsiz_bar", "tavan_kalkti")]
    parcalar.append("isaretler=" + ",".join(
        f"{x['ad']}@{x['bar']}" for x in (goruntu.get("isaretler") or [])))
    parcalar.append("notlar=" + ",".join(str(x) for x in (goruntu.get("notlar") or [])))
    parcalar.append("temas=" + ",".join(str(i) for i in (goruntu.get("temas") or [])))
    for ad in ("budama", "uyarilar", "eksik_katmanlar"):
        parcalar.append(ad + "=" + ",".join(str(x) for x in (goruntu.get(ad) or [])))
    for ad in ("formasyon", "alarm"):
        deger = goruntu.get(ad) or {}
        parcalar.append(ad + "=" + ",".join(f"{k}:{v}" for k, v in sorted(deger.items())))
    return "|".join(parcalar)


# --------------------------------------------------------------- teslim (G4, §4)
#
# Bu bölüm yalnız tarama anındaki veriyi KOPYALAYIP dosyaya yazacak yardımcıları
# içerir; motor çağırmaz (§14.2) ve hiçbir hata alarmı düşüremez (§4).

KARE_DESEN = "fb_grafik_"          # /tmp süpürme deseni (§4: bayat kare birikmesin)
KARE_OMR_SN = 6 * 3600             # açılışta bu kadar saatlik kare çöpü silinir
DISK_MIN_BOS_MB = 200              # bundan az yer varsa kare üretilmez (§4)

ALARM_TURU_ESLEME = {              # kart state'i → karenin alarm etiketi (§2.5)
    "ADAY_OLUSUYOR": "aday",
    "SIKISMA_GUCLENIYOR": "aday",
    "KIRILIM_ADAYI": "kritik",
    "KIRILIM_TEYITLI": "teyit",
    "RETEST_BASARILI": "retest",
    "KIRILIM_GECERSIZLESTI": "gecersiz",
    "FORMASYON_GECERSIZ": "gecersiz",
}


def alarm_turu_bul(state: Any) -> Optional[str]:
    """Karttaki state'i karenin alarm türüne çevirir (§2.5); tanımı yoksa None.

    Neden sözlük: `alarm_turu` karenin tek „neyi kutluyoruz" bilgisi ve kartta
    zaten var olan state'ten türetilmeli — kare için yeni bir alan uydurulmaz.
    """
    return ALARM_TURU_ESLEME.get(str(state or "").strip().upper() or None)


def kare_yolu(sembol: Any, tf: Any) -> str:
    """Geçici PNG yolu (§4): `DATA_DIR` DIŞINDA, adı uuid'li, tek kullanımlık.

    Neden /tmp: depo dizinine yazmak kalıcılık yollarını (Supabase yedeği,
    `bot_data` okuma-önce kuralı) kirletirdi; uuid ise aynı hissenin iki karesinin
    çakışmaması ve gönderimden sonra silinebilmesi için.
    """
    ad = "".join(ch for ch in str(sembol or "").upper() if ch.isalnum())[:12] or "SEM"
    tf_kisa = "".join(ch for ch in str(tf or "1h").lower() if ch.isalnum()) or "tf"
    return os.path.join(tempfile.gettempdir(),
                        f"{KARE_DESEN}{ad}_{tf_kisa}_{uuid.uuid4().hex[:8]}.png")


def bayat_kareleri_supur(simdi: Optional[float] = None) -> int:
    """Açılışta eski `fb_grafik_*.png` dosyalarını siler; silinen sayısını döner.

    Neden: gönderim yarıda kesilirse (çökme/restart) dosya /tmp'de kalıyor ve
    Render'ın sınırlı diskini doldurur. Yalnız kendi desenimize dokunur.
    """
    sayac = 0
    try:
        dizin = tempfile.gettempdir()
        simdi = time.time() if simdi is None else float(simdi)
        for ad in os.listdir(dizin):
            if not (ad.startswith(KARE_DESEN) and ad.endswith(".png")):
                continue
            yol = os.path.join(dizin, ad)
            try:
                # Yalnız OWN deseni + TTL'den eski: canlı başka bir sürecin az önce
                # yazdığı kareyi silmek gönderimi sessizce bozardı.
                if simdi - os.path.getmtime(yol) < KARE_OMR_SN:
                    continue
                os.remove(yol)
                sayac += 1
            except OSError:
                continue    # başka süreç tutuyor olabilir: sessiz geç
    except OSError as hata:   # pragma: no cover - /tmp okunamazsa sorun değil
        log.debug("grafik: bayat kare süpürülemedi (%s)", hata)
    return sayac


def disk_uygun_mu() -> bool:
    """Diskte yer var mı? Ölçülemezse EVET (üretimi keyfi engellememek için)."""
    try:
        return shutil.disk_usage(tempfile.gettempdir()).free >= DISK_MIN_BOS_MB * 1024 * 1024
    except OSError:
        return True


_MOTOR_ANAHTARLARI = ("order_block", "fvg", "market_structure", "volume_participation")


def _sonuc_sec(sonuclar: Any, tf: str, *, cikis: Optional[dict[str, Any]] = None) -> Any:
    """`sonuclar`dan bu TF'nin motor çıktısını çıkarır (iki biçim de geçerli).

    Neden çözümleyici: tarama turu sonuçları `zaman dilimi → çıktı` sözlüğü olarak
    taşınıyor (`domain_results_by_stock[sembol]`), CLI ise TEK TF'nin çıktısını
    veriyor. Köprü ilk sürümünde birincil kareye TF'yle İÇ İÇE sözlüğü geçirdi ve
    bölge/yapı katmanları SESİZCE boş kaldı — bu yüzden biçim tanınmazsa artık bir
    uyarı satırı bırakıyoruz, sessiz boş kare yok.
    """
    if not sonuclar:
        return None
    if isinstance(sonuclar, Mapping):
        if tf in sonuclar:
            return sonuclar.get(tf) or None
        if any(ad in sonuclar for ad in _MOTOR_ANAHTARLARI):
            return sonuclar                  # tek TF'lik çıktı (CLI biçimi)
        if cikis is not None:
            cikis["uyarilar"].append(f"{tf}: motor çıktıları tanınamadı (katmanlar çizilmedi)")
    return sonuclar                            # nesne biçimi: olduğu gibi ilet


def kare_listesi(cift: Any = None, tf: str = "1h", cerceve: Any = None, *,
                 sonuclar: Optional[Mapping[str, Any]] = None,
                 ek_cerceveler: Optional[Mapping[str, Any]] = None,
                 alarm_turu: Optional[str] = None, alarm_bar: Optional[int] = None,
                 sembol: str = "", zaman_damgasi: Any = None,
                 adet: Optional[int] = None,
                 simdi: Optional[datetime] = None) -> dict[str, Any]:
    """Tarama anında payload'a eklenecek kare sözlükleri (§4 köprüsü).

    Kartın beslendiği AYNI `cift`/`sonuclar` kullanılır; bu yüzden kare ile kart
    aynı veriyi anlatır. `ek_cerceveler` {tf: çerçeve} — birincil TF her zaman
    İLK karedir, kalanları `TELEGRAM_GRAFIK_ADET` kadar eklenir; fazlası kesilir
    ve `kota`da sayılır (veri kusuru değil, görüntü sınırı → dipnot yazılmaz).

    Dönüş: `{"sembol", "goruntular": [goruntu...], "kota": int, "uyarilar": [...]}`;
    kill-switch kapalıysa veya çerçeve yoksa `goruntular` boş döner (çağıran
    taraf bundan hiçbir şey kaybetmez).
    """
    cikti: dict[str, Any] = {"sembol": str(sembol or ""), "goruntular": [], "kota": 0,
                             "uyarilar": []}
    if not grafik_aktif_mi():
        return cikti
    tf = str(tf or "1h")
    sinir = int(grafik_kare_adedi() if adet is None else adet)
    plan: list[tuple[str, Any, Optional[Mapping[str, Any]]]] = [
        (tf, cerceve, _sonuc_sec(sonuclar, tf, cikis=cikti))]
    for ek_tf, ek_cerceve in (ek_cerceveler or {}).items():
        ek_tf = str(ek_tf or "")
        if not ek_tf or ek_tf == tf or ek_cerceve is None:
            continue
        plan.append((ek_tf, ek_cerceve, _sonuc_sec(sonuclar, ek_tf, cikis=cikti)))
    if len(plan) > sinir:
        cikti["kota"] = len(plan) - sinir
        plan = plan[:sinir]
    for sira, (kare_tf, kare_cerceve, kare_sonuclar) in enumerate(plan):
        birincil = sira == 0
        try:
            cikti["goruntular"].append({
                "tf": kare_tf,
                # Bant ve alarm SADECE birincil kareye çizilir: `start_bar`/
                # `alarm_bar` o çerçevenin mum indeksleridir; diğer TF'nin
                # kadrajına taşımak yanlız konum değil, sahte „bant teması" sayısı
                # de üretirdi (duman ölçümünde 1s karesi 266 temas saydı).
                "goruntu": anlik_goruntu(cift if birincil else None, kare_tf, kare_cerceve,
                                         sonuclar=kare_sonuclar,
                                         alarm_turu=alarm_turu if birincil else None,
                                         alarm_bar=alarm_bar if birincil else None,
                                         sembol=sembol,
                                         zaman_damgasi=_zaman_bul(kare_cerceve, zaman_damgasi),
                                         simdi=simdi),
            })
        except Exception as hata:   # pragma: no cover - kare alarmı düşürmesin
            log.warning("grafik: kare hazırlanamadı (%s %s): %s", sembol, kare_tf, hata)
            cikti["uyarilar"].append(f"{kare_tf}: {type(hata).__name__}")
    for kare in cikti["goruntular"][1:]:
        kare["goruntu"]["notlar"].append(
            "bant/alarm diğer zaman dilimine ait: bu karede çizilmedi (§14.1)")
    return cikti


def _zaman_bul(cerceve: Any, varsayilan: Any) -> Any:
    """Karenin „son kapanan" satırı kendi çerçevesinin son barından okunur."""
    try:
        deger = cerceve.index[-1]
        return deger if deger is not None else varsayilan
    except Exception:
        return varsayilan


def kareyi_yaz(goruntu: Mapping[str, Any], tf: str, *, serit: bool = True,
               beklenen_son_bar_ts: Any = None) -> tuple[Optional[str], dict[str, Any]]:
    """Bir kareyi diske yazar: `(yol, meta)`. Hata → `(None, meta)`; görsel alarmı
    asla engellemez (§4). Yol çağrıandan gelir: gönderim sonrası O siler.
    """
    hedef = kare_yolu(goruntu.get("sembol"), tf)
    yol, meta = ciz(goruntu, tf, secenekler={
        "cikti": hedef,
        "serit": serit,
        "beklenen_son_bar_ts": beklenen_son_bar_ts,
    })
    if yol is None:
        try:
            os.remove(hedef)
        except OSError:
            pass
    return yol, meta
