# grafik/overlays.py — formasyon iskelet/çizgi/kalıp katmanı (Faz 2).

from __future__ import annotations

import io
import textwrap
import logging
import math
import os
import shutil
import tempfile
import time
import uuid
import threading
from functools import wraps
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional, Sequence

from reporting.format import sayi
import chart_experience as deneyim
from telegram_measure import SATIR_BUTCE, genislik as _genislik_16

import grafik as _pkg  # yamalı adlar için geç bağlama (plan §3)

log = logging.getLogger("grafik")  # eski kayıt adıyla aynı (__name__ yerine)

from grafik.core import (  # noqa: F401
    PALET,
    SABITLER,
    _STATE_ETIKET,
    _alan,
    _gercek,
    _tam,
)
from grafik.geometry import (  # noqa: F401
    _formasyon_araligi,
    _formasyon_serileri,
    _gorunur_parcalar,
)

# Formasyon durumu → kısa Türkçe etiket (başlık ve /grafik altyazısı). Bilinmeyen
# durum etiketsiz kalır; ham motor adı kullanıcıya yazılmaz.
FORMASYON_DURUM_ETIKET = {
    "ADAY_OLUSUYOR": "aday oluşuyor",
    "GEOMETRI_ADAYI": "geometri adayı",
    "FORMASYON_TANIMLANDI": "tanımlandı",
    "OLGUNLASIYOR": "olgunlaşıyor",
    "SIKISMA_GUCLENIYOR": "sıkışma güçleniyor",
    "KIRILIM_HAZIRLIGI": "kırılım hazırlığı",
    "KIRILIM_DENEMESI": "kırılım denemesi",
    "KIRILIM_ADAYI": "kırılım adayı",
    "KIRILIM_TEYITLI": "kırılım teyitli",
    "RETEST_BEKLENIYOR": "retest bekleniyor",
    "RETEST_EDILIYOR": "retest ediliyor",
    "RETEST_BASARILI": "retest başarılı",
    "FORMASYON_TAMAMLANDI": "tamamlandı",
    "BASARISIZ_KIRILIM": "kırılım başarısız",
    "KIRILIM_TEYIT_ALAMADI": "teyit alınamadı",
    "FORMASYON_ZAYIFLADI": "zayıfladı",
    "FORMASYON_GECERSIZ": "geçersiz",
}


def formasyon_durum_etiketi(durum: Any) -> str:
    """Durum kodunun Türkçe etiketi; bilinmiyorsa boş (ham kod yazılmaz)."""
    return FORMASYON_DURUM_ETIKET.get(str(durum or "").strip().upper(), "")


_FORMASYON_METIN = ("pattern_name", "pattern_type", "state", "frozen_pattern_type",
                    "evidence_text")


_FORMASYON_SAYI = ("quality", "effective_quality", "raw_quality", "contraction", "start_bar", "end_bar",
                    "apex_bar", "known_bar", "upper_now", "lower_now", "upper_slope",
                    "lower_slope", "upper_touches", "lower_touches", "break_price",
                    "critical_price_level", "candle_close_price", "close_price",
                    "direction", "break_dir", "progress", "start_width", "current_width",
                    "hb1", "hp1", "hb2", "hp2", "lb1", "lp1", "lb2", "lp2",
                    # Direk (pole): bayrak/flama impuls bacağı. Motorda
                    # hesaplanıyordu ama karta HİÇ kopyalanmadığı için grafikte
                    # çizilemiyordu (`canli_tarama` çıktısı "DIREK gorunmeli"
                    # derken). Yalnız gerçek motor alanları kopyalanır (§1).
                    "pole_dir", "pole_duration", "pole_magnitude", "pole_quality")


_FORMASYON_BOOL = ("has_pole",)


_CAPA_TAM = ("hb1", "hb2", "lb1", "lb2")   # bar indeksleri; fiyatlar float kalır


_POLE_TAM = ("pole_dir", "pole_duration")  # yön (-1/0/1) ve bar adedi tamsayı


def _formasyon_kopyala(cift: Any) -> dict[str, Any]:
    """Kartın gösterdiği formasyon alanlarını kopyalar (§1: yalnız gerçek alanlar)."""
    cikti: dict[str, Any] = {}
    for ad in _FORMASYON_BOOL:
        ham = _alan(cift, ad)
        if ham is not None:
            cikti[ad] = bool(ham)
    for ad in _FORMASYON_METIN:
        deger = _alan(cift, ad)
        if deger is not None and str(deger).strip():
            cikti[ad] = str(deger)
    for ad in _FORMASYON_SAYI:
        ham = _alan(cift, ad)
        tamsayi_mi = (ad.endswith(("_bar", "_touches", "direction", "break_dir"))
                      or ad in _CAPA_TAM or ad in _POLE_TAM)
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


# 2026-10-23: kare başlığı kart diliyle aynı sözcükleri kullanır
# (`KIRILIM · kapanış onaylı`, `SEVİYE KORUNDU`, `KIRILIM İPTAL`).
_TUR_ETIKET = {
    "aday": "kırılım adayı",
    "kritik": "kritik seviye",
    "teyit": "kırılım · kapanış onaylı",
    "retest": "kırılan seviye tuttu",
    "gecersiz": "kırılım iptal · banda döndü",
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
    bar_mutlak = bar
    if bar is not None:
        # ÇERÇEVE → PENCERE dönüşümü (2026-10-23'te bulunan hata): `alarm_bar`
        # çerçevenin MUTLAK bar indeksidir; kare ise `[sol, sag)` penceresini
        # çizer. Dönüşüm yapılmadığı için alarm düşey çizgisi yalnız mutlak
        # indeks tesadüfen pencereye düştüğünde çiziliyordu ve `_gecersiz_katmani`
        # yanlış muma bakıyordu (kırılım mumu işareti sessizce kayboluyordu).
        if sol <= bar < sag:
            bar = int(bar) - int(sol)
        else:
            disarida = True
            bar = None
    try:
        yon = int(_alan(cift, "break_dir") or 0)
    except (TypeError, ValueError):
        yon = 0
    if yon == 0:
        # Motor yön vermediyse durum adından çıkarılır (`AŞAĞI TEYİTLİ` gibi);
        # çıkarılamazsa 0 kalır ve teyit sınırı ÇİZİLMEZ (uydurma yok).
        _durum = durum.upper()
        if "ASAGI" in _durum or "AŞAĞI" in _durum:
            yon = -1
        elif "YUKARI" in _durum or "YÜKSELİŞ" in _durum:
            yon = 1
    # Geçersizleşme eşiği KURAL GÜNCEL BANDI okur — `notifier`daki `× geçersiz`
    # satırıyla birebir aynı kural: yukarı kırılım için bant üstü, aşağı kırılım
    # için bant altı sınırı; ikisi de kırılan sınırın kendisidir, yönle seçilir.
    _formasyon = dict(goruntu.get("formasyon") or {})
    # Yön BİLİNMİYORSA eşik de çizilmez: "hangi sınır" sorusunun cevabı yoksa
    # tahmin yürütmek yanlış seviye gösterir (uydurma yok kuralı).
    _teyit = None
    if yon > 0:
        _teyit = _gercek(_formasyon.get("upper_now"))
    elif yon < 0:
        _teyit = _gercek(_formasyon.get("lower_now"))
    # FAZ 4 §4: TEYİTLİ alarmlarda 🎯 hedef projeksiyonu. Hedef = kırılan seviye +
    # yön × formasyon yüksekliği (klasik "measured move"; bant genişliği motorun
    # kendi `current_width`/`start_width` alanından gelir). Yön ya da genişlik
    # bilinmiyorsa hedef ÜRETİLMEZ — uydurma seviye çizilmez.
    hedef = None
    if str(tur or _ALARM_TURU.get(durum) or "") in ("teyit", "retest") and deger is not None:
        genislik = _gercek(_formasyon.get("current_width"))
        if genislik is None:
            genislik = _gercek(_formasyon.get("start_width"))
        if genislik and float(genislik) > 0 and yon != 0:
            hedef = float(deger) + float(yon) * float(genislik)
    return {
        "tur": tur or _ALARM_TURU.get(durum),
        "deger": deger,
        "hedef": hedef,
        "yon": yon,
        "teyit_siniri": _teyit,
        "bar": bar,                       # pencere içi (0 = ilk çizilen mum)
        "bar_mutlak": bar_mutlak,         # çerçeve indeksi (izlenebilirlik)
        "bar_kaynak": bar_kaynak if bar is not None else None,
        "bar_disarida": disarida,
        "durum": durum or None,
        "etiket": _STATE_ETIKET.get(durum) or _TUR_ETIKET.get(tur or "", "") or None,
        "kapanis": _gercek(_alan(cift, "candle_close_price") or _alan(cift, "close_price")),
    }


def _gecersiz_katmani(ax, goruntu: Mapping[str, Any], alarm: Mapping[str, Any],
                      sag: Optional[list], n: int) -> None:
    """Geçersizleşme karesinin İKİ yeni işareti (GÖRSEL-7).

    Neden gerekli: kart "teyit sınırı 38,79 üstü kapanış" diyordu ama kare bu
    sınırı ve onu kapatan mumu göstermiyordu — okuyucu "hangi mum, hangi seviye"
    sorusunu metinden kurmak zorundaydı. Kare ana okuma, metin yalnız görünmeyeni
    söyler kuralı gereği ikisi de BURADA çizilir:

    1. `┈ teyit sınırı`: noktalı yatay kılavuz + sağ çip `× 38,79 üstü kapanış`
       (alarm turuncusu; bant amberiyle karışmaz — bant zaten amber kalır).
    2. `✕ geçersizleştiren mum`: sınırı kapatan mumun işareti; mum eksenin alt
       yarısındaysa ÜSTÜNE, üst yarısındaysa ALTINA yazılır (kırpılmaz, mum
       gövdesine değmez).

    Alarm turu `gecersiz` değilse HİÇBİR ŞEY çizilmez (normal alarmda sınır
    çizilmez — henüz geçersizleşme olayı yok).
    """
    if str(alarm.get("tur") or "") != "gecersiz":
        return
    teyit = alarm.get("teyit_siniri")
    if teyit is not None:
        try:
            teyit = float(teyit)
            ax.axhline(teyit, color=PALET["olay"], linestyle=(0, (1, 3)),
                       linewidth=0.9, alpha=0.9, zorder=4)
            if sag is not None:
                yon = int(alarm.get("yon") or 0)
                sag.append({"kaynak": "gecersiz", "x": float(n) - 0.4, "y": teyit,
                            "metin": f"× {sayi(teyit)} {'altı' if yon > 0 else 'üstü'} kapanış",
                            "renk": PALET["olay"], "sabit": False, "oncelik": 5,
                            "bg": None, "yeni": float(n)})
        except (TypeError, ValueError):
            pass
    bar = alarm.get("bar")
    if bar is None:
        return
    try:
        bar = int(bar)
        dusukler = [float(v) for v in (goruntu.get("dusuk") or [])]
        yuksekler = [float(v) for v in (goruntu.get("yuksek") or [])]
        if not (0 <= bar < len(dusukler)):
            return
        alt, ust = ax.get_ylim()
        orta = (float(alt) + float(ust)) / 2.0
        asagi = dusukler[bar] <= orta          # mum alt yarıda → işaret ÜSTÜNE
        y = yuksekler[bar] if asagi else dusukler[bar]
        efekt = None
        try:
            from matplotlib import patheffects
            efekt = [patheffects.withStroke(linewidth=2.2, foreground=PALET["zemin"])]
        except Exception:  # pragma: no cover - süs; işaret yine çizilir
            efekt = None
        ax.annotate("✕", (bar, y), xytext=(0, 10 if asagi else -17),
                    textcoords="offset points", ha="center",
                    va="bottom" if asagi else "top", color=PALET["olay"],
                    fontsize=float(SABITLER["durum_pt"]) * 1.5, fontweight="bold",
                    zorder=6, clip_on=False, annotation_clip=False,
                    path_effects=efekt)
    except Exception as hata:  # pragma: no cover - işaret süsü kareyi düşürmez
        log.debug("grafik: geçersizleştiren mum işareti çizilemedi (%s)", hata)


def _direk_ciz(ax, formasyon: Mapping[str, Any], x0: int, *,
               yuksek: Optional[Sequence[Optional[float]]] = None,
               dusuk: Optional[Sequence[Optional[float]]] = None) -> bool:
    """Bayrak/flama DİREĞİ (pole): formasyon öncesi impuls bacağı çizilir.

    Direk motorda hesaplanıyordu (`has_pole`, `pole_dir`, `pole_duration`) ama
    karta HİÇ çizilmiyordu; `canli_tarama` çıktısı "DIREK gorunmeli" derken
    grafikte direk yoktu. GEOMETRİ MUMDAN OKUNUR: direk penceresi
    `[start_bar - pole_duration, start_bar)` aralığıdır; yön yukarıysa pencerenin
    en düşük DİBİNDEN en yüksek TEPESİNE (aşağıysa tersine) kalın çizgi + ok ucu
    çekilir, pencere hafif bantla işaretlenir. Yeni fiyat üretilmez.
    """
    if not formasyon.get("has_pole"):
        return False
    sure = int(_tam(formasyon.get("pole_duration")) or 0)
    yon = int(_tam(formasyon.get("pole_dir")) or 0)
    if sure <= 0 or yon not in (1, -1) or x0 <= 0 or not dusuk or not yuksek:
        return False
    p1 = min(int(x0), len(dusuk), len(yuksek))     # direk bant başlangıcında biter
    p0 = max(0, p1 - sure)
    uclar = [(i, float(dusuk[i]), float(yuksek[i])) for i in range(p0, p1)
             if _gercek(dusuk[i]) is not None and _gercek(yuksek[i]) is not None]
    if not uclar:
        return False
    if yon == 1:                                   # yükselen direk: dip → tepe
        bas = min(uclar, key=lambda t: t[1])
        bit = max(uclar, key=lambda t: t[2])
        i_bas, y_bas, i_bit, y_bit = bas[0], bas[1], bit[0], bit[2]
    else:                                          # düşen direk: tepe → dip
        bas = max(uclar, key=lambda t: t[2])
        bit = min(uclar, key=lambda t: t[1])
        i_bas, y_bas, i_bit, y_bit = bas[0], bas[2], bit[0], bit[1]
    # Pencere bandı: "hangi barlar direk" sorusu mumların ARDINDA hafif dolguyla
    ax.fill_betweenx((min(y_bas, y_bit), max(y_bas, y_bit)), p0 - 0.5, p1 - 0.5,
                     color=PALET["direk_dolgu"], alpha=0.13, linewidth=0.0, zorder=1.1)
    ax.plot([i_bas, i_bit], [y_bas, y_bit], color=PALET["direk"],
            linewidth=float(SABITLER["cizgi_kalinlik"]["direk"]),
            solid_capstyle="round", alpha=0.95, zorder=5)
    ax.plot([i_bit], [y_bit], marker="^" if yon == 1 else "v", markersize=7.0,
            linestyle="none", color=PALET["direk"], zorder=6)
    return True


def _formasyon_ciz(ax, goruntu: Mapping[str, Any], n: int, butce: float,
                   metin: dict[str, Any], *, sag_bosluk: int = 0,
                   aralik: Optional[Sequence[float]] = None,
                   yuksek: Optional[Sequence[Optional[float]]] = None,
                   dusuk: Optional[Sequence[Optional[float]]] = None) -> None:
    """Bant sınırları + direk + son muma projeksiyon + start/bitiş/apex işaretleri.

    Eğim: önceden sınır düz çizilirdi (yalnız "şu anki" değer biliniyordu), bu
    yanıltıcıydı (yükselen üçgenin alt sınırı yükselirken yatay görünüyordu). Şimdi
    motorun iki çapa noktasından (`hb1/hp1/hb2/hp2`, `lb1/lp1/lb2/lp2`) geçen
    doğrusu `f_line_price` ile her bar için değerlendirilir: yeni geometri
    üretilmez, motorun kendi doğrusu çizilir. Çapa yoksa yatay yedek kullanılır.
    """
    formasyon = goruntu.get("formasyon") or {}
    if formasyon.get("upper_now") is None and formasyon.get("lower_now") is None:
        # Formasyon kaydı hiç yoksa bu bir hata değil (kare mumlardan oluşur);
        # kayıt var ama bant sayısı yoksa §2.9 gereği `eksik: formasyon` yazılır.
        if formasyon:
            raise ValueError("bant verisi yok")
        return
    sol = int(goruntu.get("sol") or 0)
    kalin = SABITLER["cizgi_kalinlik"]["formasyon"]
    # Sağ boşluk: aynı doğrular `bitis`e kadar, TEK ve kesiksiz çizgi olarak uzar
    # (bant çizgisinin devamı; ayrı bir "projeksiyon" görünümü yok). Daralan bantta
    # çizgiler apex'te kesişir ve çizim ORADA biter — apex geride kalmışsa da
    # uzatma yok (bkz. `_formasyon_araligi`).
    x0, bitis, apex_i = _formasyon_araligi(formasyon, sol, n, sag_bosluk)
    _direk_ciz(ax, formasyon, x0, yuksek=yuksek, dusuk=dusuk)
    seriler = _formasyon_serileri(formasyon, sol, bitis)
    # Kırpma sayaçları: y-aralığı dışında kaldığı için çizilmeyen bar sayısı.
    # Sessiz kayıp yok — `meta["cizgiler"]["formasyon"]["kirpilan"]`a yazılır.
    kirpilan = {"ust": 0, "alt": 0}
    # Bant arası çok hafif dolgu (GÖRSEL-3): "hangi aralıkta sıkışıyor" tek bakışta
    # görünür; saydamlık mumların okunurluğunu bozmaz, mumların ARDINDA kalır.
    if "ust" in seriler and "alt" in seriler:
        xs_bant = list(range(x0, bitis))
        ust_s, alt_s = seriler["ust"][x0:bitis], seriler["alt"][x0:bitis]
        if any(u > a for u, a in zip(ust_s, alt_s)):
            ax.fill_between(xs_bant, alt_s, ust_s, color=PALET["formasyon_dolgu"],
                            alpha=float(SABITLER["formasyon_dolgu_alpha"]),
                            linewidth=0.0, zorder=0.9)
    for anahtar in ("ust", "alt"):
        if anahtar not in seriler:
            continue
        degerler = seriler[anahtar]
        xs = list(range(x0, bitis))          # bitis == n iken eski çizgi (sağ boşluk yok)
        # Y-ARALIĞI KISITI (2026-10-23): doğru, karenin y-aralığının dışına
        # çıktığı yerde ÇİZİLMEZ. Eskiden seri y-aralığına katılarak çizgi
        # görünür tutuluyordu ama bedeli mumların sıkışmasıydı (fiyattan kopuk
        # bant uzantısı tüm kareyi aşağı çekiyordu). Artık aralık mumdan kurulur;
        # görünür aralığa giren parçalar kesintisiz, dışına taşanlar hiç çizilmez
        # — doğrunun geometrisi değişmez, yalnız kadraj dışı atlanır.
        parcalar = _gorunur_parcalar(xs, degerler[x0:bitis], aralik)
        kirpilan[anahtar] = max(0, len(xs) - sum(len(p[0]) for p in parcalar))
        for prca_xs, prca_ys in parcalar:
            ax.plot(prca_xs, prca_ys, color=PALET["formasyon"], linewidth=kalin,
                    solid_capstyle="butt", zorder=4)
        if x0 > 0:      # bant öncesi: aynı doğrunun geriye kesikli uzantısı (§0.12e)
            # KADRAJ KISITI: uzantı eksen sınırının dışına çıkarsa çizgi kenarda
            # SERT KIRPILIYOR ("kırpılıyormuş gibi" geri bildirimi — dik bantta
            # uzantı üst/alt kenardan taşıyordu). Yalnız kadraj içinde kalan
            # bölüm çizilir; hiçbiri kalmıyorsa uzantı çizilmez.
            lo = float(aralik[0]) if aralik else None
            hi = float(aralik[1]) if aralik else None
            bas_i = 0
            while bas_i < x0 and lo is not None and hi is not None \
                    and not (lo <= degerler[bas_i] <= hi):
                bas_i += 1
            if bas_i < x0:
                xs0 = list(range(bas_i, x0 + 1))
                ax.plot(xs0, degerler[bas_i:x0 + 1], color=PALET["formasyon"],
                        linewidth=SABITLER["cizgi_kalinlik"]["projeksiyon"],
                        linestyle=(0, (3, 3)), alpha=0.7, zorder=4)
    # başlangıç / bitiş / apex işaretleri (§2.3) — mumun KAPANIŞına sabitlenir,
    # fiyatta hiçbir hesap üretilmez (ofset yalnız piksel cinsindendir).
    isaretler = list(goruntu.get("isaretler") or [])
    # Apex SAĞ BOŞLUĞA düşüyorsa (son mumun ilerisinde) veri katmanı onu üretemez
    # (kapanışına sabitlenecek mum yok): ✕, iki doğrunun kesiştiği noktaya motorun
    # kendi doğru denklemiyle konur. Doğrulardan biri yoksa çizilmez.
    if (apex_i is not None and n <= apex_i < bitis
            and "ust" in seriler and "alt" in seriler
            and not any(k.get("ad") == "apex" for k in isaretler)):
        isaretler.append({"ad": "apex", "bar": int(formasyon["apex_bar"]),
                          "y": (seriler["ust"][apex_i] + seriler["alt"][apex_i]) / 2.0})
    for isaret_kaydi in isaretler:
        i = int(isaret_kaydi["bar"]) - sol
        if not (0 <= i < bitis):
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
    # Bant temasları başlıkta adet olarak kalır; mum üstü daireler çizilmez.
    return {"kirpilan": kirpilan, "bar": int(bitis - x0),
            "apex_bar": (int(formasyon["apex_bar"]) if formasyon.get("apex_bar") is not None else None)}


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


