# grafik/markers.py — olay/ok/rozet/metin işaretleri (Faz 2).
# Not: _rvol_rozetleri burada (indicators↔markers döngüsü kırmak için).

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
    _ALARM_KALIN,
    _AY,
    _gercek,
    _ikon,
    _metin_px,
    _ortam_sayi,
    _tam,
    sag_bosluk_mum,
)
from grafik.geometry import (  # noqa: F401
    _formasyon_serileri,
    _mum_kutulari_px,
)
from grafik.indicators import (  # noqa: F401
    _grafik_dis_yapi,
    _grafik_zone,
    _rvol_katı,
)
from grafik.panels import (  # noqa: F401
    _ALT_ADIM,
)

def _rvol_rozetleri(ax, goruntu: Mapping[str, Any], n: int,
                    dusuk: Sequence[Optional[float]],
                    yuksek: Sequence[Optional[float]] = (),
                    fig: Any = None) -> dict[str, int]:
    """Sıra dışı hacim mumlarının altına YÖNLÜ RVOL rozeti basar (FAZ 1 + 2026-10-16).

    İki yön, iki eşik:
      * `⚡↑ x2,5` — RVOL > `rvol_rozet_esik` (2,0×): hacim PATLAMASI (bolluk, teyit).
      * `⚡↓ x0,5` — RVOL ≤ `rvol_rozet_esik_dusuk` (0,5×): hacim KURUMASI (ilgi yok).
    Yön yalnız okla taşınır; renk (yeşil/kırmızı) ikinci kanaldır (§0.4.1: renk
    tek başına bilgi taşımaz). Hacimsiz bar (`v = 0`/None) rozetlenmez — o bilgi
    kare altı dipnotunda (`veri: N bar hacimsiz`) durur, uydurma sayı yazılmaz.

    Sıralama `|log(RVOL)|` mantığıyla yapılır: patlamada `v`, kurumada `1/v`
    "sertlik"tir; en sert `rvol_rozet_maks` mum işaretlenir (iki yön toplamı).
    Değerler görünüm penceresine hizalıdır (0 = ilk görünen mum). Rozet mumun
    DÜŞÜĞünün 12 px altına oturur (gövde/fitil okunurluğu bozulmaz).

    Komşuluk yarıçapı BAR'dan değil PİKSELDEN hesaplanır: rozet ≈56 px, 120
    mumluk karede px/bar ≈ 5,8 → rozet ±5 barı kapsar. Sabit ±4 bar kullanılınca
    kutunun kenarı komşu gövdenin 1 px yanına düşüyor ve `mum_cakisan` kapısı
    haklı olarak kırmızı yanıyordu (ölçüm: GARAN 4s `⚡↓ x0,13` · TUPRS 4s).

    Kuruma rozeti TAVANLIDIR: `rvol_rozet_dusus_maks` (2) — kullanıcı isteği
    ("çok fazla etiket olmamalı"). En sert iki kuruma yazılır; patlamalar kalan
    yeri doldurur.

    TAZELİK ÖNCELİĞİ (kullanıcı, 2026-10-16): rozet yalnız geçmişi filtrelemez —
    HER YÖNÜN **EN TAZE** uygun mumu rozet alır. Yerleşim sırasında önde olduğu
    için onu ne aralık kuralı ne bütçe düşürebilir. Ölçüm (kural öncesi): son
    mumun rozeti dört gerçek karede de düşüyordu (GARAN 4s son bar x0,16 ·
    THYAO x0,18 · AKBNK x0,17) — yani yeni gelen sinyal gecikiyordu.

    Dönen: `{"artis": n, "dusus": m, "taze_artis": bar|None, "taze_dusus": bar|None}`
    — sessiz kayıp yok; sayaçlar `meta["serit"]`e yazılır.
    """
    serit = goruntu.get("serit") or {}
    degerler = list(serit.get("degerler") or [])
    # Eşikler ortamla ayarlanabilir (`GRAFIK_OLAY_MAKS` ile aynı desen): dağıtımda
    # 0,5× çok gürültülü gelirse operatör tek değişkenle sıkılaştırır.
    esik = float(_ortam_sayi("GRAFIK_RVOL_ROZET_ESIK", float(SABITLER["rvol_rozet_esik"])))
    esik_dusuk = float(_ortam_sayi("GRAFIK_RVOL_ROZET_ESIK_DUSUK",
                                   float(SABITLER["rvol_rozet_esik_dusuk"])))
    maks = int(SABITLER["rvol_rozet_maks"])
    # Rozet genişliği ~40 px ≙ 6-7 bar (1080 px / 80 mum); 7 bar aralık yeter.
    min_ara = max(4, int(SABITLER["rvol_rozet_ara"]))
    # Pivot etiketi (HH/HL/LH/LL) olan mumda rozet ALTTA onunla çakışır (ölçüm:
    # `LL` + `⚡ x3,6` üst üste) → o mumlarda rozet fitilin ÜSTÜNE taşınır.
    _pivot_bar = set()
    for b in ((goruntu.get("olay") or {}).get("swinglar") or []):
        try:
            _pivot_bar.add(int(b.get("bar")))
        except (TypeError, ValueError):
            continue
    # Komşuluk yarıçapı: rozetin yatay yarısı (px) ÷ px/bar, üstüne 1 bar emniyet.
    # Ölçüm (fig) yoksa sabit 5 bar: eski ±4'ten geniş, rozet genişliğini kapsar.
    _genis_px = 56.0
    if fig is not None:
        try:
            _genis_px = max(_genis_px, float(_metin_px(fig, "⚡↑ x12,34", 8.0)))
        except Exception:  # noqa: S110 - ölçüm süsü; başarısızsa sabit 5 bar kalır / pragma: no cover
            pass
    try:
        _sol, _sag = ax.get_xlim()
        _px_bar = float(ax.get_window_extent().width) / max(1e-6, float(_sag - _sol))
    except Exception:                         # pragma: no cover
        _px_bar = 9.0
    yaricap = max(4, int(math.ceil(0.5 * _genis_px / max(1e-6, _px_bar))) + 1)
    # ARALIK DA PİKSELDEN (2026-10-23, mobil ölçümü): sabit 7 bar, dar karede
    # (px/bar ≈ 4,5) rozet genişliğinin YARISINI bile karşılamıyor; iki komşu
    # rozet üst üste biniyordu (`⚡↑ x5,57` + `x3,65` tek çip gibi okunuyordu).
    # İki rozetin merkez uzaklığı en az rozet genişliği kadar olmalı.
    min_ara = max(min_ara, 2 * yaricap - 1)

    # Rozet, karedeki rehber ÇİZGİLERİN üstüne oturunca okunmuyor (ölçüm: bayrak
    # kartında `⚡↑ x2,17` alt bant doğrusunun, flama kartında `⚡↑ x4,08` FVG kutu
    # kenarının, `⚡↑ x2,08` bant öncesi kesikli uzantının üstünde). Çizgiye
    # yakınsa rozet çizgiden uzağa itilir (mum referansı ve yön rengi korunur).
    _cizgi_sabit: list[float] = []
    _alarm_v = _gercek((goruntu.get("alarm") or {}).get("deger"))
    if _alarm_v is not None:
        _cizgi_sabit.append(float(_alarm_v))
    _kritik_v = _gercek(((goruntu.get("olay") or {}).get("kritik") or {}).get("seviye"))
    if _kritik_v is not None:
        _cizgi_sabit.append(float(_kritik_v))
    for b in ((goruntu.get("olay") or {}).get("seviyeler") or []):
        v = _gercek(b.get("fiyat"))
        if v is not None:
            _cizgi_sabit.append(float(v))
    for b in (_grafik_zone(goruntu.get("zone") or {}).get("cizilen") or []):
        _cizgi_sabit.extend([float(b["alt"]), float(b["ust"])])
    _bant_serileri = _formasyon_serileri(goruntu.get("formasyon") or {},
                                         int(goruntu.get("sol") or 0), n)
    try:
        _ylo, _yhi = ax.get_ylim()
        _px_veri = (float(_yhi) - float(_ylo)) / max(1e-6, float(ax.get_window_extent().height))
    except Exception:                     # pragma: no cover - ölçüm süsü
        _px_veri = 0.0

    artislar: list[tuple[float, int, float, int]] = []
    dususler: list[tuple[float, int, float, int]] = []
    for i, v in enumerate(degerler[:n]):
        ham = _gercek(v)
        if ham is None or ham <= 0.0:      # hacimsiz bar: dipnotta bildirilir
            continue
        if ham > esik:
            artislar.append((float(ham), i, float(ham), 1))
        elif ham <= esik_dusuk:
            dususler.append((1.0 / float(ham), i, float(ham), -1))
    artislar.sort(key=lambda t: (-t[0], t[1]))
    dususler.sort(key=lambda t: (-t[0], t[1]))
    # --- TAZELİK ÖNCELİĞİ ---------------------------------------------------------
    # Kullanıcı: "bu sistem sadece geçmişi filtreler, yeni geleni geciktirebilir".
    # Kural: her yönün EN TAZE uygun mumu rozet alır; eskiler kalan yerleri
    # sertliğe göre doldurur. Taze adaylar listede ÖNDE olduğu için ne aralık
    # kuralı ne bütçe onları düşürebilir (aralık çakışmasında düşen ESKİ olur).
    taze_artis = max(artislar, key=lambda t: t[1]) if artislar else None
    taze_dusus = max(dususler, key=lambda t: t[1]) if dususler else None
    artislar = [t for t in artislar if t is not taze_artis]
    dususler = [t for t in dususler if t is not taze_dusus]
    # Bütçe: kuruma kotası `rvol_rozet_dusus_maks` (kullanıcı: "en fazla 2") —
    # taze kuruma kota içinde GARANTİ; kalan yerler en sert ESKİ kurumalara.
    # Toplam `rvol_rozet_maks`: patlamalar kalan yeri doldurur, böylece birkaç
    # sert kuruma belirgin bir hacim patlamasını kareden atamaz. HAVUZ KIRPILMAZ:
    # aralık kuralı adayları eledikçe sıradaki mum devreye girmeli (kırpma +
    # aralık birlikte rozet sayısını 8'den 2'ye düşürüyordu).
    dusus_maks = max(0, int(_ortam_sayi("GRAFIK_RVOL_ROZET_DUSUS_MAKS",
                                        float(SABITLER["rvol_rozet_dusus_maks"]))))
    # Kota 0 = "kuruma rozeti kapalı": tazelik garantisi de kotaya uyar (kapalıyken
    # taze kuruma da yazılmaz) — kaçış kapısı sürpriz üretmez.
    taze_dusus_kota = taze_dusus if dusus_maks > 0 else None
    kalan_dusus = max(0, dusus_maks - (1 if taze_dusus_kota is not None else 0))
    taze = [t for t in (taze_artis, taze_dusus_kota) if t is not None]
    adaylar = taze + sorted(artislar + dususler[:kalan_dusus],
                            key=lambda t: (-t[0], t[1]))
    cizilen = 0
    sayac = {"artis": 0, "dusus": 0}
    yerlesik: list[int] = []
    cizilen_bar: set[int] = set()
    for sertlik, i, deger, yon in adaylar:
        if cizilen >= maks:
            break
        # Bitişik mumlarda rozetler yatayda üst üste biner (ölçüm: iki komşu bar
        # `⚡ x2,2 ⚡ x2,3`). Aynı bölgede EN SERT hacim kalır; en az `min_ara`
        # bar aralık bırakılır — okunurluk hacim bilgisinden önce gelir.
        if any(abs(i - j) < min_ara for j in yerlesik):
            continue
        yerlesik.append(i)
        # Rozet mumun ALTINA oturur; çakışma ölçümü (kalite kapısı) temiz kalsın
        # diye referans, komşu mumların (±2 bar) EN DÜŞÜK fitili — komşu fitil
        # rozetin üstüne binmez (ölçüm: 7 rozet çakışıyordu).
        # Rozet ~40 px geniş: komşuluk yatayda ±4 bar (4s karesinde ~8 bar yer kaplar).
        komsu = [float(v) for v in dusuk[max(0, i - yaricap):i + yaricap + 1]
                 if v is not None]
        if not komsu:
            continue
        ustte = any(abs(i - pb) <= 1 for pb in _pivot_bar)
        if ustte and len(yuksek) > i:
            _kom_y = [float(v) for v in yuksek[max(0, i - yaricap):i + yaricap + 1]
                      if v is not None]
            if not _kom_y:
                continue
            # Pivot yazısı da aynı yerde (fitilin 11 px altında): rozet onu
            # örtmesin diye daha yukarıdan başlar (11 px yazı + 11 px ofset ≈ 30).
            y, ofs_y, va = max(_kom_y), 30, "bottom"
        else:
            y, ofs_y, va = min(komsu), -13, "top"
        # Kare DIŞINA taşma denetimi (piksel): alt kenara yakın mumda rozet x ekseni
        # etiketlerine biner (ölçüm: `17 Eyl` üstünde `⚡ x3,6`) → fitilin ÜSTÜNE alınır.
        try:
            _y_px = float(ax.transData.transform((float(i), float(y)))[1])
            _alt_px = float(ax.patch.get_window_extent().y0)
            if va == "top" and (_y_px - 32.0) < _alt_px:
                _kom_y = [float(v) for v in (yuksek or dusuk)[max(0, i - yaricap):
                                                             i + yaricap + 1]
                          if v is not None]
                if _kom_y:
                    y, ofs_y, va = max(_kom_y), 13, "bottom"
        except Exception:  # noqa: S110 - ölçüm süsü rozeti düşürmez / pragma: no cover
            pass
        # Rehber çizgiden UZAĞA it: rozet merkezi (veri biriminde) hesaplanır,
        # çizgiye 16 px'ten yakınsa rozetin bulunduğu tarafa doğru kaydırılır.
        # İki geçiş: bir çizgiden kaçış başka bir çizgiye düşürebilir.
        if _px_veri > 0.0:
            _cizgiler = list(_cizgi_sabit)
            for _seri in _bant_serileri.values():
                if 0 <= i < len(_seri):
                    _cizgiler.append(float(_seri[i]))
            y_c = float(y) + ofs_y * _px_veri
            for _ in range(2):
                for L in _cizgiler:
                    if abs(y_c - L) < 16.0 * _px_veri:
                        y_c = (L - 16.0 * _px_veri) if ofs_y < 0 else (L + 16.0 * _px_veri)
            y_c = max(y_c, float(ax.get_ylim()[0]) + 8.0 * _px_veri)
            y = y_c - ofs_y * _px_veri
        ax.annotate(f"⚡{'↑' if yon > 0 else '↓'} x{_rvol_katı(deger)}",
                    xy=(float(i), float(y)),
                    xytext=(0, ofs_y), textcoords="offset points", ha="center",
                    va=va, fontsize=8.0,
                    color=PALET["mum_yukselen"] if yon > 0 else PALET["mum_dusen"],
                    zorder=7, annotation_clip=False,
                    bbox=dict(boxstyle="round,pad=0.18", facecolor=PALET["chip_zemin"],
                              edgecolor=(PALET["mum_yukselen"] if yon > 0
                                         else PALET["mum_dusen"]),
                              linewidth=0.6, alpha=0.9))
        cizilen += 1
        cizilen_bar.add(int(i))
        sayac["artis" if yon > 0 else "dusus"] += 1
    # Taze rozet GERÇEKTEN çizildi mi: yerleşim sırası önde olduğu için beklenen
    # "evet"; yine de varsayım değil ÖLÇÜM — çizilen bar kümesinden okunur.
    return {"artis": sayac["artis"], "dusus": sayac["dusus"],
            "taze_artis": (int(taze_artis[1]) if taze_artis is not None
                           and int(taze_artis[1]) in cizilen_bar else None),
            "taze_dusus": (int(taze_dusus[1]) if taze_dusus is not None
                           and int(taze_dusus[1]) in cizilen_bar else None)}


def _kutu_yazisi_sigar(ax, b: Mapping[str, Any], x0: int, x1: int, n: int,
                       aralik: Sequence[float], metin: str) -> bool:
    """Kutu içi yazı kutuya sığar mı? (piksel ölçümü; sığmazsa şerit yedeği devreye girer.)

    Yatay: en GENİŞ satır kutu genişliğinden küçük olmalı (kutu kenarlarını aşmasın).
    Dikey: kutu yüksekliği satır sayısını almalı (ince FVG'lerde yazı taşardı).
    Çok satırlı metin (künye satırı) desteklenir — satır sayısı kadar yer ister.
    Ölçüm hata verirse `False` döner → güvenli taraf: şerit yedeği kullanılır.
    """
    try:
        kutu_px = ax.get_window_extent()
        bar_px = float(kutu_px.width) / max(1.0, float(n))
        yukseklik_px = float(kutu_px.height)
    except Exception:
        return False
    genislik_px = max(1.0, float(x1 - x0 + 1)) * bar_px
    # Yazı genişliği kart metriğinden (16 px taban) kutu puntosuna çevrilir.
    punto_px = float(SABITLER["zone_yazi_pt"]) * float(SABITLER["dpi"]) / 72.0
    satirlar = str(metin).split("\n") or [""]
    tahmin_px = max(_genislik_16(satir) for satir in satirlar) * punto_px / 16.0
    if tahmin_px + 6.0 > genislik_px:
        return False
    try:
        aralik_px = yukseklik_px / max(1e-9, float(aralik[1]) - float(aralik[0]))
        kutu_yuk_px = (float(b["ust"]) - float(b["alt"])) * aralik_px
    except Exception:
        return False
    return kutu_yuk_px >= punto_px * len(satirlar) + 5.0


def _kutu_yazisi_koy(ax, b: Mapping[str, Any], x0: int, x1: int, n: int,
                     aralik: Sequence[float], metin: str, renk: str,
                     kutular: Any = None, engel_y: Sequence[float] = ()) -> bool:
    """Kutu içi yazıyı mum, yatay seviye ve önceki zone etiketi gözeterek koy.

    Adaylar kutunun İÇİNDE kalır (yatay: sol/orta/sağ; dikey: orta ve kenara
    yakın). Gerçek genişlik `get_window_extent` ile okunur; kutuya sığmayan aday
    elenir. Önce yatay seviye/başka zone yazısı ile çakışmayan, sonra mumla en az
    çakışan yer seçilir. Hiçbiri sığmıyorsa `False` → sağ şerit yedeği kullanılır.
    """
    from matplotlib import patheffects

    def _yaz(xa: float, ya: float, ha: str) -> Any:
        return ax.text(xa, ya, metin, ha=ha, va="center", gid="kutu-ici",
                       fontsize=float(SABITLER["zone_yazi_pt"]),
                       color=renk, zorder=5, clip_on=False,
                       path_effects=[patheffects.withStroke(linewidth=2.0,
                                                            foreground=PALET["zemin"])])

    alt, ust = float(b["alt"]), float(b["ust"])
    orta = (alt + ust) / 2.0
    y_aday = [orta, alt + (ust - alt) * 0.32, ust - (ust - alt) * 0.32]
    x_aday = [((x0 + x1) / 2.0, "center"), (x0 + 0.1, "left"), (x1 - 0.1, "right")]
    try:
        renderer = ax.figure.canvas.get_renderer()
        kx0, ky0 = ax.transData.transform((float(x0) - 0.5, alt))
        kx1, ky1 = ax.transData.transform((float(x1) + 0.5, ust))
        kutu = (min(kx0, kx1), min(ky0, ky1), max(kx0, kx1), max(ky0, ky1))
    except Exception:
        renderer, kutu = None, None
    en_iyi = None
    try:
        renderer = ax.figure.canvas.get_renderer() if renderer is None else renderer
        engel_px = [float(ax.transData.transform((0.0, float(y)))[1]) for y in engel_y
                    if _gercek(y) is not None]
        onceki_yazilar = [t.get_window_extent(renderer) for t in ax.texts
                          if t.get_visible() and str(t.get_gid() or "").endswith("-ici")]
    except Exception:
        engel_px, onceki_yazilar = [], []
    for ya in y_aday:
        for xa, ha in x_aday:
            yazi = _yaz(xa, ya, ha)
            if renderer is None:
                return True                      # ölçüm yok: ilk aday (orta) yeter
            try:
                bb = yazi.get_window_extent(renderer)
            except Exception:
                return True
            # kutuya sığmıyor mu? (kenarları aşan aday elenir)
            if kutu is not None and (bb.x0 < kutu[0] - 1.0 or bb.x1 > kutu[2] + 1.0
                                     or bb.y0 < kutu[1] - 1.0 or bb.y1 > kutu[3] + 1.0):
                yazi.remove()
                continue
            alan = 0.0
            if kutular is not None and len(kutular):
                for cx0, cy0, cx1, cy1 in kutular:
                    ow = max(0.0, min(bb.x1, cx1) - max(bb.x0, cx0))
                    oh = max(0.0, min(bb.y1, cy1) - max(bb.y0, cy0))
                    alan += ow * oh
            seviye_cakisma = sum(1 for yy in engel_px if bb.y0 - 1.5 <= yy <= bb.y1 + 1.5)
            etiket_cakisma = sum(1 for ob in onceki_yazilar
                                 if bb.x0 < ob.x1 and bb.x1 > ob.x0
                                 and bb.y0 < ob.y1 and bb.y1 > ob.y0)
            # Yazı–yazı çakışmasının ALANI da mum alanından ÖNCE gelir: iki kutu
            # etiketi üst üste binerse ikisi de okunmaz (ölçüm: `OB↑ %54 dolu` ile
            # `OB↑ · taze` aynı satıra düşüyordu). Mum fitiline değmek tolere edilir.
            etiket_alani = sum(max(0.0, min(bb.x1, ob.x1) - max(bb.x0, ob.x0))
                               * max(0.0, min(bb.y1, ob.y1) - max(bb.y0, ob.y0))
                               for ob in onceki_yazilar)
            skor = (seviye_cakisma, etiket_cakisma, etiket_alani, alan)
            if skor == (0, 0, 0, 0):
                return True
            if en_iyi is None or skor < en_iyi[0]:
                en_iyi = (skor, xa, ya, ha)
            yazi.remove()
    if en_iyi is None:
        return False                             # hiçbir aday kutuya sığmadı
    _, xa, ya, ha = en_iyi
    _yaz(xa, ya, ha)
    return True


def _zone_etiket_engeller(goruntu: Mapping[str, Any]) -> list[float]:
    """Kutu etiketi yerleşiminde geçilecek fiyat seviyelerini döndür."""
    seviyeler: list[float] = []

    def ekle(deger: Any) -> None:
        fiyat = _gercek(deger)
        if fiyat is not None:
            seviyeler.append(fiyat)

    formasyon = goruntu.get("formasyon") or {}
    ekle(formasyon.get("upper_now"))
    ekle(formasyon.get("lower_now"))
    ekle(goruntu.get("son_kapanis"))
    alarm = goruntu.get("alarm") or {}
    ekle(alarm.get("deger"))
    ekle(alarm.get("teyit_siniri"))
    olay = goruntu.get("olay") or {}
    for kayit in (olay.get("seviyeler") or []):
        ekle(kayit.get("fiyat"))
    for kayit in (olay.get("olaylar") or []):
        ekle(kayit.get("seviye"))
    ekle((olay.get("kritik") or {}).get("seviye"))
    return seviyeler


def _alarm_ciz(ax, alarm: Mapping[str, Any], n: int, butce: float,
               sag: Optional[list] = None) -> None:
    """Alarm mumu: kesikli düşey çizgi; seviye: kesikli yatay çizgi (§2.6).

    Yazı (`alarm 67,20`) sağ fiyat şeridine gider; kapanış karşılaştırması başlık
    satırında (`_metinler`) yazılır — mum üstünde yazı kalmaz (görsel-2).
    """
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
    # GÖRSEL-7: teyit geçersizleştiyse kırılan seviye ARTIK GEÇERLİ DEĞİL; çizgi
    # soluk + kesik, çip metni `✕ eski seviye …`. Aksi hâlde kare, "hâlâ geçerli
    # bir seviye" yanılgısı veriyordu (kullanıcı şikâyeti: anlamsız `× 3,5`).
    gecersiz = str(alarm.get("tur") or "") == "gecersiz"
    hedef = _gercek(alarm.get("hedef"))
    _cizgi = True
    if gecersiz:
        try:
            _teyit = float(alarm.get("teyit_siniri"))
            _alt_y, _ust_y = (float(v) for v in ax.get_ylim())
            # Kare yüksekliği 0,02 ≈ 12 px (810 px'lik karede): bu aralıktan yakın iki
            # yatay çizgi tek kalın çizgi gibi görünür, ayrımı okuyucu kaybeder.
            _cizgi = abs(float(deger) - _teyit) >= (_ust_y - _alt_y) * 0.02
        except (TypeError, ValueError):
            _cizgi = True
    if _cizgi:
        ax.axhline(float(deger), color=PALET["alarm"],
                   linestyle=(0, (2, 4)) if gecersiz else (0, (5, 4)),
                   linewidth=kalin, alpha=0.55 if gecersiz else None, zorder=4)
    if sag is not None:
        sag.append({"kaynak": "alarm", "x": float(n) - 0.4, "y": float(deger),
                    "metin": (f"✕ eski seviye {sayi(deger)}" if gecersiz
                              else f"alarm {sayi(deger)}"),
                    "renk": PALET["eksen"] if gecersiz else PALET["alarm"],
                    "sabit": False, "oncelik": 6, "bg": None, "yeni": float(n)})
    # FAZ 4 §4: TEYİTLİ alarmda hedef projeksiyonu (sağ boşluğa kesikli ok + kutu).
    if not gecersiz and hedef is not None:
        try:
            _projeksiyon_ciz(ax, alarm, n)
        except Exception as hata:  # projeksiyon süsü alarm karesini düşürmesin
            log.debug("grafik: hedef projeksiyonu çizilemedi (%s)", hata)


def _projeksiyon_ciz(ax, alarm: Mapping[str, Any], n: int) -> bool:
    """Teyitli alarmda sağdaki boşluğa kesikli ok + `🎯 Hedef` kutusu (FAZ 4 §4).

    Neden: teyitli kırılımda kullanıcının bir sonraki sorusu "hedef neresi?".
    Kutu, son mumun SAĞINDAKİ boşlukta durur (mumların üzerine yazı binmez);
    ok, kırılım mumundan/seviyeden hedefe uzanır. Hedef yalnız motordan gelen
    ölçülü hareket (`_alarm_kopyala`: seviye + formasyon yüksekliği) varsa çizilir;
    yoksa fonksiyon hiç çağrılmaz/döner — uydurma seviye gösterilmez.
    """
    hedef = _gercek(alarm.get("hedef"))
    if hedef is None:
        return False
    yon = int(_gercek(alarm.get("yon")) or 0)
    if yon == 0:
        return False
    seviye = _gercek(alarm.get("deger"))
    bar = _tam(alarm.get("bar"))
    sag_kenar = float(n) - 0.4 + float(sag_bosluk_mum(n))
    x0 = float(bar) if (bar is not None and 0 <= int(bar) < n) else float(n) - 1.0
    # Kutu: sağ boşluğun son %70'inde, hedef seviyesini saran ince bant.
    alt_y, ust_y = (float(v) for v in ax.get_ylim())
    bant = max((ust_y - alt_y) * 0.012, 1e-9)
    kutu_x0 = float(n) - 0.6 + max(0.0, float(sag_bosluk_mum(n)) * 0.25)
    kutu_gen = max(0.6, sag_kenar - kutu_x0)
    from matplotlib.patches import Rectangle
    ax.add_patch(Rectangle((kutu_x0, float(hedef) - bant / 2.0), kutu_gen, bant,
                           facecolor=PALET["hedef"], alpha=0.14, edgecolor=PALET["hedef"],
                           linewidth=float(SABITLER["cizgi_kalinlik"]["hedef"]),
                           linestyle=(0, (3, 2)), zorder=4.5, clip_on=False))
    y0 = seviye if seviye is not None else float(hedef) - yon * abs(ust_y - alt_y) * 0.05
    ax.annotate("", xy=(kutu_x0, float(hedef)), xytext=(x0, float(y0)),
                arrowprops=dict(arrowstyle="-|>", color=PALET["hedef"], lw=1.2,
                                linestyle=(0, (4, 3)), alpha=0.85, shrinkA=0, shrinkB=0),
                zorder=5, annotation_clip=False)
    ax.annotate(f"{_ikon('hedef')} Hedef {sayi(float(hedef))}".strip(),
                xy=(kutu_x0 + kutu_gen, float(hedef)),
                xytext=(-4, -1), textcoords="offset points", ha="right", va="top",
                fontsize=float(SABITLER["sag_serit_yazi_pt"]), color=PALET["hedef"],
                zorder=9, annotation_clip=False,
                bbox=dict(boxstyle="round,pad=0.24", facecolor=PALET["chip_zemin"],
                          edgecolor=PALET["hedef"], linewidth=0.7, alpha=0.95))
    return True


def _olay_yazi_koy(ax, x: float, seviye: float, yon_ust: bool, metin: str,
                   kutular, yerlesik: list, n: int) -> bool:
    """Olay etiketini çakışmasız en iyi adaya koyar (GÖRSEL-4 ölçüm düzeltmesi).

    Neden: etiket olayın mumuna iliştiğinde (GÖRSEL-4) bazı kırılımlarda mumun
    üstüne biniyordu — ölçüm `katman_cakisan`da 4 yazı gösterdi. Aday ölçüsü
    piksel, ama GERÇEK genişlik `get_window_extent` ile okunur (tahmin 1–2 px
    sapabiliyor): adaylar denendikçe yazı ölçülür, çakışmasız ilk adayda kalınır,
    hiçbiri boş değilse EN AZ çakışan aday korunur (yazı asla kaybolmaz).
    """
    try:
        import numpy as np
        dpi = float(ax.figure.dpi)
        bar_px = max(2.0, float(ax.get_window_extent().width) / max(1.0, float(n)))
        px, py = ax.transData.transform((float(x), float(seviye)))
    except Exception:
        dpi, bar_px, px, py = 100.0, 6.0, 0.0, 0.0
        np = None

    punto_px = float(SABITLER["olay_yazi_pt"]) * dpi / 72.0
    g = max(6.0, _genislik_16(metin) * punto_px / 16.0) + 3.0   # güvenlik payı
    yuk = punto_px + 3.0
    adim = punto_px * 1.7
    # Kırılım yönünün TERSİ önce: yukarı kırılımda fiyat seviyenin üstünde kalır.
    ilk = -1.0 if yon_ust else 1.0
    # Aday sırası: önce kırılımın TERS tarafı (kademeli uzaklaşarak), sonra karşı
    # taraf. Yoğun mum bölgesinde tek yön yetmeyebiliyor (ölçüm: CHoCH↓).
    dyler = ([ilk * (yuk + i * adim) for i in range(4)]
             + [-ilk * (yuk + i * adim) for i in range(3)])
    dxler = [0.0] + [float(k) * bar_px * 1.4 * yon
                     for k in (1, 2, 3, 4) for yon in (1, -1)]

    engel_kutu = np if (np is not None and kutular is not None and len(kutular)) else None
    from matplotlib import patheffects
    try:
        renderer = ax.figure.canvas.get_renderer()
    except Exception:
        renderer = None

    def _olc(kutu) -> float:
        """Kutunun mum kutuları + yerleşik yazılarla çakışma alanı (px²)."""
        x0, y0, x1, y1 = kutu
        alan = 0.0
        if engel_kutu is not None:
            for kx0, ky0, kx1, ky1 in kutular:
                ow = max(0.0, min(x1, kx1) - max(x0, kx0))
                oh = max(0.0, min(y1, ky1) - max(y0, ky0))
                alan += ow * oh
        for (ox0, oy0, ox1, oy1) in yerlesik:          # diğer olay etiketleri
            ow = max(0.0, min(x1, ox1) - max(x0, ox0))
            oh = max(0.0, min(y1, oy1) - max(y0, oy0))
            # Yazı–yazı çakışması OKUNMAZLIK demektir: mum fitiline değmekten
            # daha ağır sayılır (ölçüm: iki komşu kutu etiketi üst üste biniyordu).
            alan += 3.0 * ow * oh
        return alan

    def _yaz(dx: float, dy: float, va: str):
        return ax.annotate(metin, xy=(x, seviye),
                           xytext=(dx * 72.0 / dpi, dy * 72.0 / dpi),
                           textcoords="offset points", ha="center", va=va,
                           fontsize=float(SABITLER["olay_yazi_pt"]), color=PALET["olay"],
                           zorder=7, annotation_clip=False, gid="olay-ici",
                           path_effects=[patheffects.withStroke(
                               linewidth=2.2, foreground=PALET["zemin"])])

    def _tahmin(dx: float, dy: float, va: str) -> tuple[float, float, float, float]:
        x0, x1 = px + dx - g / 2.0, px + dx + g / 2.0
        y0, y1 = ((py + dy - yuk, py + dy) if va == "top"
                  else (py + dy, py + dy + yuk))
        return x0, y0, x1, y1

    en_iyi = None
    for dy in dyler:
        for dx in dxler:
            va = "top" if dy < 0 else "bottom"
            yazi = _yaz(dx, dy, va)
            if renderer is None:
                yerlesik.append(_tahmin(dx, dy, va))
                return True
            try:
                bb = yazi.get_window_extent(renderer)
                kutu = (bb.x0 - 1.0, bb.y0 - 1.0, bb.x1 + 1.0, bb.y1 + 1.0)
            except Exception:
                kutu = _tahmin(dx, dy, va)
            alan = _olc(kutu)
            if alan <= 0.0:
                yerlesik.append(kutu)
                return True
            if en_iyi is None or alan < en_iyi[0]:
                en_iyi = (alan, dx, dy, va, kutu)
            yazi.remove()
    if en_iyi is None:                    # aday üretilemedi (savunma)
        return False
    _, dx, dy, va, kutu = en_iyi
    _yaz(dx, dy, va)
    yerlesik.append(kutu)
    return True


def _olay_ciz(ax, goruntu: Mapping[str, Any], n: int,
              sag: Optional[list] = None, kutular: Any = None, *,
              sag_bosluk: int = 0) -> dict[str, int]:
    """Yalnız dış PH/PL/WH/WL cetveli ve dış BOS/CHoCH çizgileri.

    Renkler §0.4.1: swing `#90a4ae` (α: teyitli 1,0 · kırık 0,2 · aday 0,45),
    olay `#ff8a65`. `kritik`, seçilen son dış olayın `broken_level`ıdır; alarm
    seviyesiyle aynıysa çift çizilmez. `!` işaretleri hacim şeridinden gelir.
    """
    olay = _grafik_dis_yapi(goruntu.get("olay") or {})
    swinglar = []  # internal pivots are intentionally hidden, including legacy inputs
    seviyeler = list(olay.get("seviyeler") or [])
    olaylar = list(olay.get("olaylar") or [])
    alarm = goruntu.get("alarm") or {}
    sayac = {"swing": 0, "etiket": 0, "kritik_atlandi": 0,
             "phpl_serit": 0, "whwl_serit": 0, "seviye": 0}
    yerlesik_swing: list[tuple[float, bool, float]] = []
    yerlesik_olay: list[tuple[float, float, float, float]] = []   # piksel kutular
    kritik_eslesdi = False
    if not swinglar and not seviyeler and not olaylar and not (olay.get("kritik") or {}):
        return sayac
    zamanlar = list(goruntu.get("zamanlar") or [])
    dusuk = [float(v) for v in (list(goruntu.get("dusuk") or [])[:n])]
    # Olay etiketi yerleşimi için mum kutuları (gövde+fitil, piksel). Çağıran
    # (`_kare_ciz`) zaten hesapladıysa tekrar hesaplanmaz.
    mum_kutulari = kutular
    if olaylar and mum_kutulari is None:
        try:
            mum_kutulari = _mum_kutulari_px(
                ax, [float(v) for v in (list(goruntu.get("acilis") or [])[:n])],
                [float(v) for v in (list(goruntu.get("yuksek") or [])[:n])], dusuk,
                [float(v) for v in (list(goruntu.get("kapanis") or [])[:n])],
                float(SABITLER["mum_genislik_orani"]))
        except Exception:
            mum_kutulari = None
    # Dış yapının aktif rol seviyeleri yatay kılavuz + sağ cetvel çipi olur.
    # Kaynağı görünür pencerenin solundaysa çizgi pencere kenarından devam eder;
    # eski dış pivot oku çizilmez ve iç ok katmanıyla karışmaz.
    for b in seviyeler:
        y = _gercek(b.get("fiyat"))
        if y is None:
            continue
        kaynak_x = _gercek(b.get("bar"))
        x0 = max(0.0, min(float(max(0, n - 1)),
                          float(kaynak_x) if kaynak_x is not None else 0.0))
        x1 = float(n) - 0.4 + float(sag_bosluk)
        ax.plot([x0, x1], [y, y], color=PALET["sinif"], linewidth=0.8,
                linestyle=(0, (1, 3)), alpha=0.38, zorder=2)
        etiket = str(b.get("etiket") or "")
        if sag is not None:
            sag.append({"kaynak": "swing", "x": float(n) - 0.4, "y": y,
                        "metin": f"{etiket} {sayi(y, 2)}", "renk": PALET["sinif"],
                        "sabit": False, "oncelik": 4, "bg": None,
                        "yeni": float(b.get("kaynak_bar") if b.get("kaynak_bar") is not None else -1)})
        if etiket in ("PH", "PL"):
            sayac["phpl_serit"] += 1
        elif etiket in ("WH", "WL"):
            sayac["whwl_serit"] += 1
        sayac["seviye"] += 1
    kritik_bilgi = olay.get("kritik") or {}
    kritik_bar = _tam(kritik_bilgi.get("bar"))
    kritik_seviye = _gercek(kritik_bilgi.get("seviye"))
    kritik_eslesdi = False
    etiket_ic = 0
    # Yaş kademesi: en YENİ olay 0. sırada (solma buna göre).
    _bar_sirali = sorted({int(b["bar"]) for b in olaylar if b.get("bar") is not None},
                         reverse=True)
    olay_sirasi = {bar: i for i, bar in enumerate(_bar_sirali)}
    for b in olaylar:
        x, seviye = float(b["bar"]), _gercek(b.get("seviye"))
        if seviye is None:
            continue
        yon_ust = b.get("yon") == "ust"
        etiket = f"{b.get('tur') or 'BOS'}{'↑' if yon_ust else '↓'}"
        vurgu = (kritik_bar is not None and kritik_seviye is not None
                 and int(b["bar"]) == kritik_bar and abs(seviye - kritik_seviye) < 1e-9)
        if vurgu:
            # kritik değer AYRI şerit etiketi olur: "CHoCH↓ · kritik 411,00" şerit
            # genişliğini aşıp kesiliyordu (görsel-2); iki etiket dikeyde ayrışır.
            kritik_eslesdi = True
            if sag is not None:
                sag.append({"kaynak": "olay", "x": float(n) - 0.4, "y": seviye,
                            "metin": f"kritik {sayi(seviye, 2)} · {b.get('tur') or 'dış olay'}", "renk": PALET["olay"],
                            "sabit": False, "oncelik": 5, "bg": None,
                            "yeni": float(b["bar"])})
        ax.plot([x], [seviye], marker="^" if yon_ust else "v", ms=6.0, linestyle="none",
                color=PALET["olay"], zorder=6)
        # GÖRSEL-5 (okunurluk): BOS kesikli, CHoCH NOKTALI — iki olay türü aynı
        # görünümde değil; ayrıca alfa olayın YAŞINA göre azalır (en yeni en koyu),
        # böylece "hangi kırılım yeni?" sorusu çizginin renginden okunur.
        # CHoCH NOKTALI (`":"`), BOS kesikli: matplotlib dash demetlerini içeride
        # `'--'`e normalleştirdiği için stil ayrımı ancak adlandırılmış desenle
        # hem görünür hem ölçülebilir oluyor.
        _stil = ":" if str(b.get("tur") or "BOS").upper().startswith("CHO") else (0, (3, 2))
        if vurgu:
            _alfa = 0.9
        else:
            _sira = int(olay_sirasi.get(int(b["bar"]), 0))
            _toplam = max(1, len(olay_sirasi) - 1)
            _alfa = max(0.38, 0.85 - 0.5 * (_sira / float(_toplam)))
        # FAZ 3 §4.2: çizgi ekranın solundan sağına UZATILMAZ. Pivot noktasından
        # (motorun `origin_source_bar`ı) başlar ve fiyatın seviyeyi KIRDIĞI mumda
        # sonlanır. Yalnız kırılmamış AKTİF hedef (en güncel, `kritik`) sağdaki
        # boşluğa kadar uzar — "hedef hâlâ geçerli" bilgisi budur.
        _pivot_x = _gercek(b.get("pivot_bar"))
        x0 = x
        if _pivot_x is not None and 0.0 <= float(_pivot_x) <= x:
            x0 = float(_pivot_x)
        x1 = (float(n - 1) + float(sag_bosluk)) if vurgu else x
        ax.plot([x0, max(x0, x1)], [seviye, seviye], color=PALET["olay"],
                linewidth=1.4 if vurgu else 0.9, linestyle=_stil,
                alpha=_alfa, zorder=3 if vurgu else 2)
        # GÖRSEL-4 kullanıcı kararı: BOS/CHoCH için FİYAT değil MUM KONUMU önemli
        # → etiket sağ fiyat şeridine değil, olayın mumuna ilişir. Yerleşim
        # 2 boyutlu aranır (`_olay_yazi_yeri`): önce kırılımın ters tarafı, olmazsa
        # yana kaydırma — mum kutusuyla çakışmayan ilk aday; hepsi doluysa en az
        # çakışan (yazı asla kaybolmaz). Koyu kontur okunabilirliği tamamlar.
        if _olay_yazi_koy(ax, x, seviye, yon_ust, etiket,
                          mum_kutulari, yerlesik_olay, n + sag_bosluk):
            etiket_ic += 1
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
            # FAZ 3 §4.2: bu da bir HEDEF çizgisidir — soldan başlamaz; motorun
            # pivot barı varsa oradan, yoksa kırılım mumundan sağa uzar.
            _kaynak_x = _gercek(kritik.get("pivot_bar"))
            if _kaynak_x is None:
                _kaynak_x = _gercek(kritik.get("bar"))
            x0k = max(0.0, min(float(n) - 1.0, float(_kaynak_x if _kaynak_x is not None else 0)))
            ax.plot([x0k, float(n - 1) + float(sag_bosluk)], [seviye, seviye],
                    color=PALET["olay"], linewidth=1.3, linestyle=(0, (6, 3)),
                    alpha=0.85, zorder=3)
            if sag is not None:
                sag.append({"kaynak": "olay", "x": float(n) - 0.4, "y": seviye,
                            "metin": f"kritik {sayi(seviye, 2)} · {kritik.get('tur') or 'dış olay'}", "renk": PALET["olay"],
                            "sabit": False, "oncelik": 5, "bg": None, "yeni": float(n)})
    sayac["etiket"] = 0      # yazılar sağ şeritte; yerleşim `_sag_ciz`de
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
            "kritik_atlandi": sayac["kritik_atlandi"], "capa": len(serit.get("capa") or []),
            "etiket_ic": etiket_ic,
            "phpl_serit": int(sayac.get("phpl_serit") or 0),
            "whwl_serit": int(sayac.get("whwl_serit") or 0),
            "seviye": int(sayac.get("seviye") or 0)}


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
    # ETİKET YOĞUNLUĞU PİKSELE GÖRE (2026-10-23): sabit "en fazla 8" kuralı,
    # dar karelerde (mobil: eksen ~465 px, punto 1,35×) tarihleri üst üste
    # bindiriyordu ("10 Eyl14 Eyl"). Sığan sayı eksen genişliğinden hesaplanır:
    # her etiket kendi genişliği + nefes payı kadar yer ister.
    sinir = 8
    try:
        eksen_px = float(ax.get_window_extent().width)
        en_uzun = max((t for _, t in aday), key=len)
        etiket_px = _metin_px(ax.figure, en_uzun, float(SABITLER["eksen_pt"]))
        if eksen_px > 1 and etiket_px > 1:
            sinir = max(2, min(sinir, int(eksen_px / (etiket_px * 1.35 + 8.0))))
    except Exception as hata:      # pragma: no cover - ölçüm süsü, 8 sınırı kalır
        log.debug("grafik: tick yoğunluğu ölçülemedi (%s)", hata)
    if len(aday) > sinir:
        adim = math.ceil(len(aday) / float(sinir))
        aday = [x for j, x in enumerate(aday) if j % adim == 0][:sinir]
    ax.set_xticks([i for i, _ in aday])
    ax.set_xticklabels([t for _, t in aday], rotation=0, fontsize=SABITLER["eksen_pt"])


def _rozet_ciz(fig, x: float, y: float, kayit: Mapping[str, Any],
               yazi_pt: float, genislik_px: Optional[float] = None) -> float:
    """Tek UI rozeti (Pills/Badges, FAZ 4 §2): yarı saydam, yuvarlatılmış çip.

    Sol üstteki düz metinlerin yerini alır; arka plan yarı saydam olduğu için
    koyu zeminde "yapışkan etiket" gibi durmaz. Tüketilen x konumunu (figür
    kesiri) döner — rozetler soldan sağa dizilir, kareyi aşarsa çizilmez.
    """
    metin = str(kayit.get("metin") or "")
    if not metin:
        return x
    ikon = _ikon(str(kayit.get("ikon") or ""))
    if ikon:
        metin = f"{ikon} {metin}"
    pad = 0.010                                    # rozetler arası boşluk (kesir)
    yazi_pt = float(yazi_pt)
    # Genişlik VERİLDİYSE o (çağıran bir kez ölçer), yoksa gerçek renderer ölçümü.
    if genislik_px is None:
        genislik_px = _metin_px(fig, metin, yazi_pt)
    try:
        fig_px = float(fig.get_size_inches()[0]) * float(fig.dpi)
    except Exception:                              # pragma: no cover
        fig_px = float(SABITLER["genislik_taban"] or 1080)
    gen = (float(genislik_px) + 22.0) / max(1.0, fig_px)
    if x + gen > 0.985:
        return x
    fig.text(x, y, metin, ha="left", va="top", fontsize=yazi_pt,
             color=kayit.get("renk") or PALET["metin"],
             bbox=dict(boxstyle="round,pad=0.42", facecolor=kayit.get("dolgu") or PALET["panel"],
                       edgecolor=kayit.get("kenar") or PALET["panel_kenar"],
                       linewidth=0.7, alpha=0.55),
             zorder=10, clip_on=False)
    return x + gen + pad


def _metin_ciz(fig, metin: Mapping[str, Any], sol_kenar: float, sag_kenar: float,
               ust: float, *, alt_blok: bool = True) -> None:
    """Kare üstü yazı bloğu; alt blok yalnız `alt_blok` açıkken (eski görünüm).

    FAZ 1: lejant + gri not + kırmızı uyarı satırları kareden ÇIKARILDI (aynı
    bilgiler `meta["metin"]`den Telegram kartının altına dipnot olarak gider).
    FAZ 4 §2: başlık satırı düz metin değil, yarı saydam rozetlerdir.
    """
    y = 1.0 - 0.032
    rozetler = list(metin.get("pill_listesi") or [])
    x = float(sol_kenar)
    if rozetler:
        for kayit in rozetler[:4]:
            x = _rozet_ciz(fig, x, y, kayit, SABITLER["baslik_pt"])
    else:
        fig.text(sol_kenar, y, metin["baslik"], ha="left", va="top", color=PALET["metin"],
                 fontsize=SABITLER["baslik_pt"], fontweight="bold")
    try:
        fig_px = float(fig.get_size_inches()[0]) * float(fig.dpi)
        sag_gen = (_metin_px(fig, str(metin.get("sag") or ""), SABITLER["durum_pt"]) + 12.0) / max(1.0, fig_px)
    except Exception:
        sag_gen = 0.22
    # Sağ yazı ("son mum …") rozetlerle aynı satıra sığmıyorsa ALT satıra iner:
    # bilgi satırlarının ÜSTÜNE binmesi (mobil ölçümü) engellenir — sıra artık
    # rozet satırı → bilgi satırları → sağ yazı. Karar `_metinler`de ölçülerek
    # verilir (`sag_ayri_satir`), eksen üst sınırı da ona göre ayrılır.
    ayri = bool(metin.get("sag_ayri_satir"))
    if not ayri:
        y_sag = (y - 0.040) if (rozetler and x > float(sag_kenar) - sag_gen - 0.015) else y
        fig.text(sag_kenar, y_sag, metin["sag"], ha="right", va="top", color=PALET["eksen"],
                 fontsize=SABITLER["durum_pt"])
    y -= 0.040
    for satir in metin["satirlar"]:
        fig.text(sol_kenar, y, satir, ha="left", va="top", color=PALET["eksen"],
                 fontsize=SABITLER["durum_pt"])
        y -= 0.031
    if ayri:
        fig.text(sag_kenar, y, metin["sag"], ha="right", va="top", color=PALET["eksen"],
                 fontsize=SABITLER["durum_pt"])
    # Başlık bloğu ile grafik arasında ince AYRAÇ (GÖRSEL-3): üst yazılar kareye
    # "yapışık" görünmesin, okuma alanı net bir dikdörtgen olsun.
    if bool(SABITLER.get("ust_ayrac", True)):
        try:
            from matplotlib.lines import Line2D
            y_ayrac = float(ust) + 0.010
            fig.add_artist(Line2D([sol_kenar, sag_kenar], [y_ayrac, y_ayrac],
                                  transform=fig.transFigure, color=PALET["panel_kenar"],
                                  linewidth=0.8, zorder=0.6))
        except Exception as hata:  # pragma: no cover - süs çizimi kareyi düşürmez
            log.debug("grafik: üst ayraç çizilemedi (%s)", hata)
    if not alt_blok:
        # FAZ 1: kare altındaki lejant/gri/kırmızı blok çizilmez (kart dipnotuna
        # taşındı) — eksen dibe kadar indi, kazanılan alan mumlara kaldı.
        return
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


