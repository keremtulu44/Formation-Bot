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
import tempfile
import time
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
    "doldurma": {"golge_esik_orani": 0.18, "golge": 0.14, "golge_ince": 0.05},
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

# Alarm çizgisinin kalınlığı durumdndan gelir (§2.6): halka açık durumlar kalın.
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


# --------------------------------------------------------------- anlık görüntü


def anlik_goruntu(cift: Any = None, tf: str = "1h", cerceve: Any = None, *,
                  sonuclar: Optional[Mapping[str, Any]] = None,
                  alarm_turu: Optional[str] = None, alarm_bar: Optional[int] = None,
                  sembol: str = "", zaman_damgasi: Any = None,
                  simdi: Optional[datetime] = None,
                  kare_mum: Optional[int] = None) -> dict[str, Any]:
    """Tarama anındaki veriyi çizilebilir sözlüğe kopyalar (§2, §14.1).

    `cift`: kartın beslendiği formasyon kaydı (`PatternCandidate` veya payload
    sözlüğü). `sonuclar`: `run_domain_engines` çıktısı — G1'de yalnız *varlığı*
    not edilir (G2 zone'ları, G3 yapı/şerit buradan okunur); motor çağrılmaz.
    `alarm_turu` `aday/kritik/teyit/retest/gecersiz/ihlal`, `alarm_bar` çerçeve
    değeri mum indeksi. Hiçbiri zorunlu değil: verisi olmayan katman çizilmez.
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
    if sonuclar:
        # G2/G3 bu veriyi kullanacak; G1'de çizilmiyor → dürüstçe not (sessiz kabahat yok).
        goruntu["uyarilar"].append("bölge/yapı verisi bu fazda çizilmedi (G2/G3)")
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
        aralik = _yatay_aralik(kapanis + yuksek + dusuk, ek_y)
        ax.set_ylim(*aralik)
        ax.set_xlim(-0.6, n - 0.4)
        butce = _butce_px(genislik)
        cap = max(0.6, olcu["px_bar"] * float(SABITLER["mum_genislik_orani"]))

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
        if ax_serit is not None:
            _serit_ciz(ax_serit, goruntu, n)
        metin = _metinler(goruntu, meta, genislik, eksik, yalnizca_mumlar, etiket_detay)
        _, _, y_gri, y_kirmizi = _alt_yerlesim(len(metin["dipnotlar"]),
                                              len(metin.get("notlar") or []),
                                              len(metin["lejant"]))
        metin["_y"] = {"lejant": alt_yerlesimi, "gri": [alt_yerlesimi - 0.0235 * (i + 1)
                                                        for i in range(len(y_gri))],
                       "kirmizi": [alt_yerlesimi - 0.0235 * (len(y_gri) + i + 1)
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
        ax.annotate(etiket, xy=(n - 1, ax.get_ylim()[1]), xytext=(-2, -2),
                    textcoords="offset points", ha="right", va="top",
                    fontsize=SABITLER["etiket_pt"], color=PALET["temas"], zorder=7,
                    bbox=dict(facecolor=PALET["zemin"], edgecolor="none", alpha=0.6, pad=1.0))
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


def _alt_yerlesim(kirmizi: int, gri: int, lejant_satir: int = 1) -> tuple[float, float, list[float], list[float]]:
    """Kare altındaki yazı bloğunun yerleşimi: lejant → gri notlar → kırmızı uyarılar.

    Neden tek yer: lejant ile dipnotların üst üste binmesi ilk çizimde görüldü;
    aks payı artık burada hesaplanır, eksen alta oraya göre çekilir.
    """
    adim = 0.0235
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


def _serit_ciz(ax, goruntu: Mapping[str, Any], n: int) -> None:
    """Katılım şeridi kulvarı (G3'te dolar, §2.1): yalnız spike'lar çizilir."""
    serit = goruntu.get("serit") or {}
    degerler = [None if v is None else float(v) for v in list(serit.get("degerler") or [])[:n]]
    ax.set_yticks([])
    ax.set_xlim(-0.6, n - 0.4)
    if not any(v is not None for v in degerler):
        return
    esik = float(serit.get("esik") or SABITLER["serit_esik"])
    spike = [i for i, v in enumerate(degerler) if v is not None and v >= esik]
    taban = max((v for v in degerler if v is not None), default=1.0)
    ax.set_ylim(0.0, max(esik * 1.15, taban * 1.25))
    if spike:
        ax.bar(spike, [degerler[i] for i in spike], width=0.62, color=PALET["serit"], zorder=3)
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
    if goruntu.get("zone"):
        oge.append("OB yeşil · FVG mavi · 4s/1g")
    if goruntu.get("serit"):
        oge.append("şerit: rvol(20) · yerel hesap")
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
        fig.text(0.5, float(y["lejant"]) - i * 0.0215, satir, ha="center", va="top",
                 color=PALET["eksen"], fontsize=float(metin.get("lejant_punto",
                                                                SABITLER["lejant_pt"])))
    for i, satir in enumerate(metin.get("notlar") or []):
        fig.text(0.5, float(y["gri"][i]), satir, ha="center", va="top",
                 color=PALET["eksen"], fontsize=SABITLER["dipnot_pt"], alpha=0.85)
    for i, satir in enumerate(metin["dipnotlar"]):
        fig.text(0.5, float(y["kirmizi"][i]), satir, ha="center", va="top",
                 color=PALET["ihlal"], fontsize=SABITLER["dipnot_pt"])


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
        "zone": goruntu.get("zone") or {"cizilen": 0, "elenen": 0},
        "olay": goruntu.get("olay") or {"cizilen": 0, "elenen": 0},
        "serit": goruntu.get("serit") or {"acik": False, "esik": None, "spike": []},
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
