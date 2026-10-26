# grafik/panels.py — alt/sağ panel, şerit ve lejant (Faz 2).
# Not: _zone_metni panels'de (panels↔render döngüsü kırmak için).

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
    _BOLGE_ARA,
    _BOLGE_TAMAM,
    _FVG_YOK_TFLAR,
    _MOD,
    _gercek,
    _ikon,
    _kirp,
    _olcu_px,
    _sigar_mi,
    _tam,
)
from grafik.geometry import (  # noqa: F401
    _zone_renk,
)
from grafik.indicators import (  # noqa: F401
    _grafik_dis_yapi,
    _grafik_yapi_metni,
    _grafik_zone,
)
from grafik.overlays import (  # noqa: F401
    formasyon_durum_etiketi,
)

def _zone_metni(b: Mapping[str, Any]) -> str:
    """Kutu etiketi TEK kaynaktan: `OB↓ %70` / `FVG↑`.

    Doluluk lifecycle `maximum_fill_ratio` alanından; eski ham şemada destekli
    fallback alanlarından okunur. Aday, küçük `?` ile işaretlenir. **GÖRSEL-5:**
    `qNN` etiketi KALDIRILDI — lejantta açıklaması
    olmayan bir koddu (ölçüm: çizilen 56 kutu etiketinin 21'i `qNN`di); kalite
    bilgisi mesaj tarafında `kalite 84/100` olarak zaten yazılı, kutu etiketi ise
    "hangi kutu, ne kadarı dolu" sorusunu cevaplar. Hem kutu içi yazı hem şerit
    yedeği bu metni kullanır (iki yerde ayrışmasın).
    """
    if str(b.get("tip")) not in ("ob", "fvg"):
        return ""
    ad = {"ob": "OB", "fvg": "FVG"}[str(b.get("tip"))]
    metin = f"{ad}{'↑' if int(b.get('yon') or 1) >= 0 else '↓'}"
    metin += " · " + deneyim.zone_status(b)
    dol = _gercek(b.get("doluluk"))
    if str(b.get("tip")) == "ob" and dol is not None:
        metin += f" · dolum %{sayi(dol * 100.0, 0)}"
    return metin


def _zone_sag_adaylari(zone: Mapping[str, Any], n: int,
                       yalniz: Optional[Sequence[Mapping[str, Any]]] = None) -> list[dict[str, Any]]:
    """Görünür OB/FVG bölgelerinin sağ şerit fiyat aralığı etiketleri.

    Etiket artık öncelikle kutunun İÇİNDE (bkz. `_zone_ciz`); kutu çok ince/dar
    olduğunda okunamayacağı için şeride taşınır ve kutunun sağ kenarından çıkan
    ince kılavuz çizgisiyle bağlanır. `yalniz` verilmezse tüm kutular yedeklenir
    (doğrudan çağıran testler için eski davranış).
    """
    cikti: list[dict[str, Any]] = []
    kaynak = list(zone.get("cizilen") or []) if yalniz is None else list(yalniz)
    for b in kaynak:
        if str(b.get("tip")) not in ("ob", "fvg"):
            continue
        cikti.append({"kaynak": "zone", "x": float(n) - 0.4, "y": (float(b["alt"]) + float(b["ust"])) / 2.0,
                      "metin": _zone_metni(b) + "\n" + sayi(float(b["alt"])) + "–" + sayi(float(b["ust"])),
                      "fiyat_araligi": (float(b["alt"]), float(b["ust"])), "renk": _zone_renk(b),
                      "sabit": False, "oncelik": 2, "bg": None,
                      "kilavuz_x": float(b.get("x1", n - 1)),
                      "yeni": float(b.get("x1", n - 1))})
    return cikti


def _sag_sirali_yerlesim(sabit, diger, lo, hi, bosluk: float = 0.0):
    """Bounded ordered placement; fixed last price never moves. Copy on success.

    `bosluk`: çipler arası ASGARİ nefes payı (veri biriminde). Bu paketleme
    önceden etiketleri TAM TEMAS ederek diziyordu (`edge + yari_h`) ve öncelikli
    yerleşimin üzerine yazdığı için payı geri alıyordu; pay burada da uygulanır,
    sabit "son fiyat" çipine olan mesafe dahil.
    """
    if len(sabit) != 1:
        return False
    fixed = sabit[0]
    moving = [a for a in diger if a.get("yy") is not None]
    below = sorted((a for a in moving if a["y"] < fixed["y"]), key=lambda a: a["y"])
    above = sorted((a for a in moving if a["y"] >= fixed["y"]), key=lambda a: a["y"])

    def pack(items, lower, upper):
        positions, edge = [], lower
        for a in items:
            center = max(float(a["y"]), edge + a["_yari_h"] + bosluk)
            positions.append(center)
            edge = center + a["_yari_h"]
        edge = upper
        for i in range(len(items) - 1, -1, -1):
            positions[i] = min(positions[i], edge - items[i]["_yari_h"] - bosluk)
            edge = positions[i] - items[i]["_yari_h"]
        if items and positions[0] - items[0]["_yari_h"] < lower - 1e-9:
            return None
        return positions

    low_positions = pack(below, lo, fixed["y"] - fixed["_yari_h"] - bosluk)
    high_positions = pack(above, fixed["y"] + fixed["_yari_h"] + bosluk, hi)
    if low_positions is None or high_positions is None:
        return False  # preserve tested priority fallback on physically overfull sides
    for a, y in zip(below + above, low_positions + high_positions):
        a["yy"] = y
    return True


def _sag_ciz(ax, fig, adaylar: Sequence[dict[str, Any]], n: int,
             aralik: Sequence[float], *, x_kenar: Optional[float] = None) -> dict[str, Any]:
    """Sağ fiyat şeridi: etiketleri eksenin DIŞINDA, son mumun sağında yerleştirir.

    Kural: sabit öğe (son kapanış) önce yerini alır; diğerleri öncelik ve seviyeye
    göre en yakın boş dikey konuma itilir. Hiçbir etiket sessizce atılmaz: yalnız
    şerit dolduğunda (en düşük öncelikli) düşer ve `atlanan_kaynak` ile sayılır.
    Yazı genişliği şerit içine kırpılır (`…`), mum alanına taşmaz.
    """
    sonuc: dict[str, Any] = {"yerlesen": 0, "atlanan": 0, "atlanan_kaynak": {},
                             "eledi_kaynak": {}, "birlesik": 0, "birlesen_kutu": 0,
                             "kaydirilan": 0, "lider": 0}
    # Eksenin sağ kenarı: boşluk yokken `n - 0.4`, boşlukla `n - 0.4 + boşluk`.
    # Etiketler bu kenarın DIŞINDA (sağ panelde) durur; boşluğun içine girmez.
    x_kenar = (float(n) - 0.4) if x_kenar is None else float(x_kenar)
    adaylar = [a for a in adaylar if not a.get("elendi")]   # kalabalık denetimi
    if not adaylar:
        return sonuc
    lo, hi = float(aralik[0]), float(aralik[1])
    kutu = ax.get_position()
    fig_w, fig_h = fig.get_size_inches()
    dpi = float(fig.dpi)
    yukseklik_px = float(kutu.height) * float(fig_h) * dpi
    if yukseklik_px <= 0 or hi <= lo:
        return sonuc
    px_birim = yukseklik_px / (hi - lo)
    yazi_px = float(SABITLER["sag_serit_yazi_pt"]) * dpi / 72.0
    adim = float(SABITLER.get("sag_etiket_adim", 1.45))
    h = yazi_px * adim / px_birim           # etiket yüksekliği (çip payı dahil), veri biriminde
    # Asgari NEFES PAYI: çipler yalnız "üst üste binmesin" değil, birbirine
    # DEĞMESİN de (kullanıcı: "bazısı çok yakın oluyor"). Pay SABİT DEĞİL,
    # şeridin KARŞILAYABİLECEĞİ kadar: dar karede sabit pay etiket DÜŞÜRÜRDÜ
    # ("hiçbir etiket sessizce atılmaz" kuralı önce gelir) — yer varsa tam pay,
    # daralmışsa küçülür, şerit doluysa sıfıra iner.
    bosluk_istenen = h * float(SABITLER.get("sag_etiket_bosluk", 0.0))
    butce = float(SABITLER["sag_serit_px"]) - 14.0
    for a in adaylar:
        if a.get("fiyat_araligi"):
            alt, ust = a["fiyat_araligi"]
            baslik = str(a["metin"]).rsplit("\n", 1)[0]
            fiyat = sayi(alt) + "–" + sayi(ust)
            # Large prices get their own lines rather than an ellipsis.
            baslik_satir = []
            for parca in baslik.split(" · "):
                if baslik_satir and _sigar_mi(baslik_satir[-1] + " · " + parca, butce):
                    baslik_satir[-1] += " · " + parca
                else:
                    baslik_satir.append(parca)
            a["metin"] = "\n".join(baslik_satir) + "\n" + (fiyat if _sigar_mi(fiyat, butce) else sayi(alt) + "\n–" + sayi(ust))
        a["_yari_h"] = h * (1 + str(a["metin"]).count("\n")) / 2.0
    # Pay bütçesi: toplam çip yüksekliği + (adet-1) pay ≤ şerit yüksekliği.
    talep = sum(2.0 * float(a["_yari_h"]) for a in adaylar)
    bosluk = max(0.0, min(bosluk_istenen,
                         ((hi - lo) - talep) / max(1, len(adaylar) - 1)))
    sabit = [a for a in adaylar if a.get("sabit")]
    diger = sorted((a for a in adaylar if not a.get("sabit")),
                   key=lambda a: (-int(a.get("oncelik", 0)), float(a["y"])))
    # GÖRSEL-5 (okunurluk): AYNI seviyedeki kutu çipleri TEK çipte birleşir
    # (`OB↓ · FVG↑ %38`). Kutu bölgeleri komşu olduğunda şeritte üst üste binen
    # iki-üç çip yerine tek satır kalır. Yalnız `zone` kaynağı birleşir; `kritik`,
    # `alarm` ve son fiyat kendi çipinde kalır (anlamları ayrı).
    _birlesik: list[dict[str, Any]] = []
    for a in diger:
        if str(a.get("kaynak")) != "zone" or a.get("elendi") or a.get("fiyat_araligi"):
            _birlesik.append(a)
            continue
        hedef = None
        for b in _birlesik:
            if (str(b.get("kaynak")) == "zone" and not b.get("fiyat_araligi") and not b.get("_birlesik_dolu")
                    and abs(float(b["y"]) - float(a["y"])) <= h * 0.75):
                hedef = b
                break
        if hedef is None:
            a["_parcalar"] = [str(a.get("metin"))]
            a["_sayi"] = 1
            _birlesik.append(a)
        else:
            hedef["_parcalar"].append(str(a.get("metin")))
            hedef["_sayi"] = int(hedef.get("_sayi", 1)) + 1
            # Birleşen çip kutuların ORTASINA oturur (kılavuz çizgisi ortak).
            hedef["y"] = (float(hedef["y"]) + float(a["y"])) / 2.0
            if hedef.get("_sayi", 0) >= 3:
                hedef["_birlesik_dolu"] = True
    for a in _birlesik:
        if a.get("_sayi", 1) > 1:
            sonuc["birlesik"] = int(sonuc["birlesik"]) + 1
            sonuc["birlesen_kutu"] = int(sonuc["birlesen_kutu"]) + int(a["_sayi"]) - 1
            metin = " · ".join(a["_parcalar"])
            # Aynı tip birden fazla kez geçiyorsa sayıyla kısalt: `OB↓ · OB↑ ×2`.
            if len(set(a["_parcalar"])) < len(a["_parcalar"]):
                ilk = sorted(set(a["_parcalar"]))[0]
                metin = f"{ilk} · … ×{len(a['_parcalar'])}"
            a["metin"] = metin
            a["birlesik"] = int(a["_sayi"])
    diger = _birlesik
    # Sabit "son fiyat" ile AYNI bantta kalan swing çipi atlanır: aynı sayıyı iki
    # kez yazmak okunurluğu bozar (ölçüm: THYAO 1s'te `PH 290,50` ile son fiyat
    # `290,50` üst üste bindi). Son fiyat sabittir ve seviyeyi zaten söyler;
    # PH/PL okuması grafikteki ince seviye çizgisi + lejantla sürer. Atlamalar
    # SAYILIR (`atlanan_kaynak`) — sessiz kayıp yok.
    _son_y = [float(x["y"]) for x in sabit]
    if _son_y:
        _kalan = []
        for a in diger:
            if (str(a.get("kaynak")) == "swing"
                    and any(abs(float(a["y"]) - y) <= h * 0.75 for y in _son_y)):
                kaynak = str(a.get("kaynak") or "?")
                sonuc["atlanan_kaynak"][kaynak] = sonuc["atlanan_kaynak"].get(kaynak, 0) + 1
                a["yy"] = None
                continue
            _kalan.append(a)
        diger = _kalan
    def _yerlestir(bosluk_degeri: float) -> dict[str, Any]:
        yerlesik: list[float] = []
        yukseklikler: list[float] = []
        yer: dict[str, Any] = {"yerlesen": 0, "atlanan_kaynak": {}, "kaydirilan": 0}
        for a in sabit:
            a["yy"] = float(a["y"])
            yerlesik.append(a["yy"])
            yukseklikler.append(a["_yari_h"])
            yer["yerlesen"] += 1
        for a in diger:
            d = float(a["y"])
            yari = a["_yari_h"]
            adaylar_y = [d] + [p + sg * (yari + ph) for p, ph in zip(yerlesik, yukseklikler) for sg in (1.0, -1.0)]
            secim = None
            for c in sorted(adaylar_y, key=lambda c: abs(c - d)):
                if c < lo + yari or c > hi - yari:
                    continue
                if all(abs(c - p) >= (yari + ph) * 0.999 + bosluk_degeri
                       for p, ph in zip(yerlesik, yukseklikler)):
                    secim = c
                    break
            if secim is None:
                kaynak = str(a.get("kaynak") or "?")
                yer["atlanan_kaynak"][kaynak] = yer["atlanan_kaynak"].get(kaynak, 0) + 1
                a["yy"] = None
                continue
            a["yy"] = secim
            yerlesik.append(secim)
            yukseklikler.append(yari)
            yer["yerlesen"] += 1
        # Greedy priority placement can invert the price order (e.g. a 297 FVG
        # below a 288 OB). Repack around the fixed last-price chip when both
        # sides fit, retaining all exact ranges and linking displaced chips to
        # true levels.
        yer["sirali"] = _sag_sirali_yerlesim(sabit, diger, lo, hi, bosluk_degeri)
        yer["kaydirilan"] = sum(1 for a in sabit + diger if a.get("yy") is not None
                                and abs(float(a["yy"]) - float(a["y"])) > h * .25)
        return yer

    # Nefes payı BEST-EFFORT: paylı yerleşim etiket DÜŞÜRÜYORSA ve paysız
    # yerleşim düşürmüyorsa paysız kazanır — "hiçbir etiket sessizce atılmaz"
    # kuralı nefes payından önce gelir (dar karede pay etiket yutuyordu).
    yer = _yerlestir(bosluk)
    if sum(yer["atlanan_kaynak"].values()):
        paysiz = _yerlestir(0.0)
        if sum(paysiz["atlanan_kaynak"].values()) < sum(yer["atlanan_kaynak"].values()):
            yer = paysiz
    sonuc["yerlesen"] += yer["yerlesen"]
    sonuc["atlanan_kaynak"].update(yer["atlanan_kaynak"])
    sonuc["kaydirilan"] = yer["kaydirilan"]
    sonuc["sirali"] = yer["sirali"]
    butce = float(SABITLER["sag_serit_px"]) - 14.0
    # Kutu etiketleri (OB/FVG) şeride ince KILAVUZ çizgisiyle bağlanır: kutu
    # kadrajın solunda olsa bile yazının hangi kutuya ait olduğu görünür kalır
    # ("sağdaki yazılar alakasız" geri bildirimi — görsel-3).
    if bool(SABITLER.get("sag_kilavuz", True)):
        for a in sabit + diger:
            x0 = _gercek(a.get("kilavuz_x"))
            if x0 is None or a.get("yy") is None:
                continue
            x0 = max(0.0, min(float(x0) + 0.5, x_kenar))
            if x0 >= x_kenar - 0.2:
                continue
            stil = dict(a.get("kilavuz_stil") or {})
            ax.plot([x0, x_kenar], [float(a["y"]), float(a["y"])],
                    color=a["renk"], linewidth=float(stil.get("lw", 0.6)),
                    alpha=float(stil.get("alpha", 0.3)),
                    linestyle=stil.get("ls", (0, (1, 2.5))), zorder=1.5, clip_on=False)
    for a in sabit + diger:
        if a.get("yy") is None:
            continue
        metin = "\n".join(_kirp(line, butce)[0] for line in str(a["metin"]).split("\n"))
        kw: dict[str, Any] = {}
        if a.get("bg"):        # son fiyat: dolu çip (yön rengi), koyu yazı, kalın
            kw["bbox"] = dict(boxstyle="round,pad=0.28", facecolor=a["bg"], edgecolor="none")
            kw["fontweight"] = "bold"
        else:                  # katman etiketi: koyu çip + katman renginde kenar/yazı
            kw["bbox"] = dict(boxstyle="round,pad=0.26", facecolor=PALET["chip_zemin"],
                              edgecolor=a["renk"], linewidth=0.7, alpha=0.95)
        # FAZ 4 §1 (Label Collision / Y-Offset): etiket çakışmayı önlemek için
        # kaydırıldıysa GERÇEK seviyeye KESİKLİ lider çizgiyle bağlanır — okuyucu
        # "bu yazı hangi seviyeye ait" sorusunu kaybetmez.
        if abs(float(a["yy"]) - float(a["y"])) > 0.25 * h:
            kw["arrowprops"] = dict(arrowstyle="-", color=a["renk"], lw=0.7, alpha=0.55,
                                    linestyle=(0, (2, 2)), shrinkA=0, shrinkB=0)
            sonuc["lider"] = int(sonuc.get("lider") or 0) + 1
        ax.annotate(metin, xy=(x_kenar, float(a["y"])), xytext=(x_kenar + 0.22, float(a["yy"])),
                    textcoords="data", ha="left", va="center",
                    fontsize=float(SABITLER["sag_serit_yazi_pt"]), color=a["renk"],
                    zorder=8, annotation_clip=False, **kw)
    sonuc["atlanan"] = sum(sonuc["atlanan_kaynak"].values())
    return sonuc


def _sag_ele(adaylar: Sequence[dict[str, Any]],
             son: Optional[float]) -> dict[str, int]:
    """Şerit kalabalık denetimi (GÖRSEL-3): kaynak başına azami etiket.

    Neden: GARAN 1s karesinde 13 etiket şeride dizildi — teknik olarak sığıyordu
    ama okunmuyordu ("sağdaki yazılar alakasız" geri bildirimi). Sıralama:
    `oncelik` (son fiyat > alarm > kritik > yapı > kutu) → son kapanışa yakınlık
    → yenilik. ELENEN aday silinmez: `elendi` işaretlenir ve sayısı
    `meta["sag"]["eledi_kaynak"]`a yazılır (sessiz kayıp yok, §0.12 ruhu).
    """
    maks = dict(SABITLER.get("sag_etiket_maks") or {})
    if not maks:
        return {}
    gruplar: dict[str, list[dict[str, Any]]] = {}
    for a in adaylar:
        if a.get("sabit") or a.get("fiyat_araligi"):
            continue
        gruplar.setdefault(str(a.get("kaynak") or "?"), []).append(a)
    elenen: dict[str, int] = {}
    for kaynak, grup in gruplar.items():
        limit = int(maks.get(kaynak, len(grup)))
        if len(grup) <= limit:
            continue

        def anahtar(a: dict[str, Any]) -> tuple[float, float, float]:
            yakinlik = abs(float(a["y"]) - float(son)) if son is not None else 0.0
            return (-int(a.get("oncelik", 0)), yakinlik, -float(a.get("yeni") or 0.0))

        grup.sort(key=anahtar)
        for a in grup[limit:]:
            a["elendi"] = True
        elenen[kaynak] = len(grup) - limit
    return elenen


def _sag_panel(fig, ax, sol_fig: float, sag_fig: float, *,
               alt_ax: Any = None) -> None:
    """Sağ fiyat şeridinin PANEL zemini (GÖRSEL-3): yazılar boşlukta yüzmesin.

    Şerit, eksenin dışında ayrı bir kulvar; koyu panel + ince sol kenar çizgisi
    eksenden ayırır. Panel eksenin `zorder`inden ÖNCE çizilir (0,4) → yazılar
    (8) hep üstte kalır; mum alanına taşmaz (eksenin sağında başlar). `alt_ax`
    verilirse panel şerit kulvarını da kapsar (iki kulvar tek panel).
    """
    try:
        from matplotlib.patches import Rectangle
        kutu = ax.get_position()
        y0, y1 = float(kutu.y0), float(kutu.y1)
        if alt_ax is not None:
            alt_kutu = alt_ax.get_position()
            y0, y1 = min(y0, float(alt_kutu.y0)), max(y1, float(alt_kutu.y1))
        x0 = min(float(sag_fig) - 0.004, float(sol_fig) + 0.002)
        if x0 <= sol_fig + 0.001:      # şerit yok denecek kadar dar → panel çizilmez
            return
        ax.add_patch(Rectangle((x0, y0), float(sag_fig) - x0, y1 - y0,
                               transform=fig.transFigure, facecolor=PALET["panel"],
                               edgecolor=PALET["panel_kenar"], linewidth=0.7,
                               zorder=0.4, clip_on=False))
        ax.plot([kutu.x1, kutu.x1], [y0, y1], transform=fig.transFigure,
                color=PALET["panel_kenar"], linewidth=0.8, zorder=0.5, clip_on=False)
    except Exception as hata:  # pragma: no cover - panel süsü çizimi engellemez
        log.debug("grafik: sağ panel çizilemedi (%s)", hata)


_LEJANT_DUSUK = ("yapı:", "şerit:", "kutular:", "FVG ·", "bant öncesi", "▨ dolan")


# GÖRSEL-7: geçersizleşme maddeleri DÜŞÜRÜLMEZ. Kare yalnız iki satır taşıyabildiği
# için sıra önemli: altta kalan madde kaybolurken `✕ geçersizleştiren mum` /
# `┈ teyit sınırı` gibi karenin YENİ işaretleri her koşulda okunmalı — yoksa kare
# açıklamasız bir işaret bırakır (lejant = çizileni anlatır kuralı, §0.12v).
_LEJANT_KORU = ("✕", "┈", "│")


def _lejant_satirlar(oge: Sequence[str], kare_genislik: float) -> tuple[list[str], float, int]:
    """Lejantı kareye sığdır: (satırlar, punto, düşürülen madde sayısı).

    Ölçüm kartla aynı metrikten (`telegram_measure`) yapılır, sonra kare ölçeğine
    çevrilir. Sırasıyla: punto küçült (9,0→7,0), sonra `bol()` ile satırlara böl
    (en fazla 2), en son düşük öncelikli maddeleri düşür. Düşürülen madde sayısı
    kareye yazılır ve `meta`'ya geçer — kare, çizdiği şeyin adını saklamaz.
    """
    from telegram_measure import bol as _bol
    # Yazı ölçeği (GÖRSEL-5 `--buyuk-yazi`) bütçeyi KÜÇÜLTÜR: punto büyürse aynı
    # piksele daha az karakter sığar. Ölçek hesaba katılmazsa lejant kareden taşar.
    olcek = max(1.0, float(getattr(_MOD, "yazi_olcek", 1.0)))
    butce = kare_genislik * 0.94 / (float(SABITLER["metin_carpani"]) * olcek)
    oge = [str(x) for x in oge if x]
    atlanan = 0
    _taban_pt = float(SABITLER["lejant_pt"])
    for punto in (_taban_pt, _taban_pt * 0.94, _taban_pt * 0.88, _taban_pt * 0.82,
                  max(7.0, _taban_pt * 0.76)):
        metin = " · ".join(oge)
        if _genislik_16(metin) <= butce:
            return [metin], punto, atlanan
        satirlar = [s.strip() for s in _bol(metin, butce)]
        if len(satirlar) <= 2:
            return satirlar, punto, atlanan
    # GÖRSEL-7: taşmada ÖNCE uzun ve düşük öncelikli bilgi satırları düşer
    # (`yapı:`/`şerit:`/`kutular:`); renk şeması, bant, seviye ve geçersizleşme
    # işaretleri her koşulda kalır. Kareye `+N madde sığmadı` YAZILMAZ: okunurluğu
    # bozan bir geliştirici notuydu (ölçüm: `+6 madde sığmadı`); sayı
    # `meta["lejant_atlanan"]`da durur, sessiz kayıp yok.
    while len(oge) > 2 and _genislik_16(" · ".join(oge)) > butce * 1.02:
        korunan = [i for i, x in enumerate(oge) if str(x).startswith(_LEJANT_KORU)]
        serbest = [i for i in range(len(oge)) if i not in korunan]
        dusuk = [i for i in serbest if str(oge[i]).startswith(_LEJANT_DUSUK)]
        if dusuk:
            oge.pop(max(dusuk, key=lambda i: _genislik_16(oge[i])))
        elif serbest:
            oge.pop(max(serbest, key=lambda i: _genislik_16(oge[i])))
        else:                        # hepsi korunmuş: en sondan düşürülür
            oge.pop()
        atlanan += 1
    return _bol(" · ".join(oge), butce)[:2], max(7.0, _taban_pt * 0.76), atlanan


_ALT_ADIM = 0.0235      # kare altındaki yazı bloğunun satır adımı (figür kesiri)


def _alt_yerlesim(kirmizi: int, gri: int, lejant_satir: int = 1) -> tuple[float, float, list[float], list[float]]:
    """Kare altındaki yazı bloğunun yerleşimi: lejant → gri notlar → kırmızı uyarılar.

    Neden tek yer: lejant ile dipnotların üst üste binmesi ilk çizimde görüldü;
    aks payı artık burada hesaplanır, eksen alta oraya göre çekilir.
    """
    # Yazı ölçeği satır adımını da büyütür (aksi hâlde lejant/dipnot satırları
    # üst üste biner — GÖRSEL-5 büyük yazı modu).
    adim = _ALT_ADIM * max(1.0, float(getattr(_MOD, "yazi_olcek", 1.0)) * 0.9)
    y_lejant = 0.046 + adim * (kirmizi + gri + max(0, lejant_satir - 1))
    y_gri = [y_lejant - adim * (i + 1) for i in range(gri)]
    y_kirmizi = [y_gri[-1] - adim * (i + 1) if gri else y_lejant - adim * (i + 1)
                 for i in range(kirmizi)]
    alt = round(y_lejant + 0.026, 4)
    return alt, y_lejant, y_gri, y_kirmizi


def _serit_ciz(ax, goruntu: Mapping[str, Any], n: int, *, sag_bosluk: int = 0) -> None:
    """Katılım şeridi kulvarı (§2.1): yalnız spike'lar çizilir.

    GÖRSEL-3: her spike kendi MUMUNUN yönünde renklenir (yükselen yeşil, düşen
    kırmızı) — hacim ile mum yönü aynı bakışta okunur. `1×` (ortalama hacim) ve
    `1,5×` (spike eşiği) referans çizgileri solda etiketlidir; böylece çubuk
    yükseklikleri "kaç kat" olarak anlaşılır, sadece kalabalık olmaz.
    """
    serit = goruntu.get("serit") or {}
    degerler = [None if v is None else float(v) for v in list(serit.get("degerler") or [])[:n]]
    ax.set_yticks([])
    # Şerit, mum ekseniyle AYNI x sınırını kullanmalı (dikey hizalama).
    zone_pay = float(sag_bosluk)      # ana eksenle AYNI sağ boşluk (sharex)
    ax.set_xlim(-0.6, n - 0.4 + zone_pay)
    if not any(v is not None for v in degerler):
        return
    esik = float(serit.get("esik") or SABITLER["serit_esik"])
    # `spike` anlık görünümde seçildi (eşik + en sert `serit_maks`); çizim yeniden
    # eleme yapmaz — §14.2 (hesap yok, kopya var).
    spike = [int(i) for i in (serit.get("spike") or []) if 0 <= int(i) < len(degerler)]
    taban = max((v for v in degerler if v is not None), default=1.0)
    ax.set_ylim(0.0, max(esik * 1.15, taban * 1.25))
    acilis = list(goruntu.get("acilis") or [])
    kapanis = list(goruntu.get("kapanis") or [])
    if spike:
        renkler = []
        for i in spike:
            a = acilis[i] if i < len(acilis) else None
            k = kapanis[i] if i < len(kapanis) else None
            yukari = a is None or k is None or float(k) >= float(a)
            renkler.append(PALET["serit_yuk"] if yukari else PALET["serit_dus"])
        ax.bar(spike, [degerler[i] for i in spike], width=0.62, color=renkler, zorder=3)
    for i in (serit.get("yildiz") or []):
        if 0 <= int(i) < len(degerler) and degerler[int(i)] is not None:
            ax.annotate("▲", xy=(float(i), degerler[int(i)]), xytext=(0, 2),
                        textcoords="offset points", ha="center", va="bottom", fontsize=7.5,
                        color=PALET["serit"], zorder=6)
    tepe = _gercek(serit.get("tepe"))
    if tepe is not None and spike:
        # TEK sayı etiketi (§17.3): en sert spike'ın çarpanı, her bara yazılmaz.
        # Çip: yazı mum/fitil üstüne binse de okunur kalır.
        ax.annotate(f"rvol ×{sayi(tepe, 1)}", xy=(float(max(spike, key=lambda i: degerler[i])), tepe),
                    xytext=(0, 9), textcoords="offset points", ha="center", va="bottom",
                    fontsize=float(SABITLER["etiket_pt"]), color=PALET["metin"], zorder=7,
                    annotation_clip=False,
                    bbox=dict(boxstyle="round,pad=0.22", facecolor=PALET["chip_zemin"],
                              edgecolor=PALET["panel_kenar"], linewidth=0.6))
    # Referans çizgileri: 1× = ortalama hacim (etiketSİZ, evrensel okuma), 1,5× =
    # spike eşiği (etiketli). Yazı kulvarın İÇİNDE ve sol kenarda: mumların üstüne
    # girmez, eksene de taşmaz.
    ax.axhline(1.0, color=PALET["grid_vurgu"], linestyle=(0, (2, 2)), linewidth=0.6,
               alpha=0.9, zorder=1)
    ax.axhline(esik, color=PALET["serit"], linestyle=(0, (3, 3)), linewidth=0.8,
               alpha=0.55, zorder=1)
    ax.annotate(f"{sayi(esik, 1)}×", xy=(-0.5, esik), xytext=(0, 2.5),
                textcoords="offset points", ha="left", va="bottom", fontsize=7.0,
                color=PALET["serit"], zorder=4, annotation_clip=False)


def _metinler(goruntu: Mapping[str, Any], meta: Mapping[str, Any], genislik: int,
              eksik: Sequence[str], yalnizca_mumlar: bool,
              etiket_detay: bool = False) -> dict[str, Any]:
    """Başlık + durum satırı + lejant + koşullu dipnotlar (§0.12v/w, §2.9)."""
    formasyon = goruntu.get("formasyon") or {}
    alarm = goruntu.get("alarm") or {}
    n = int(meta.get("mum_sayisi") or 0)
    baslik = f"{goruntu.get('sembol') or '—'} · {goruntu.get('tf_kisa') or goruntu.get('tf')} · {n} mum"
    sag = "son mum " + deneyim.date_text(goruntu.get("son_bar_ts"),
                                              daily=str(goruntu.get("tf")) == "1d")
    if goruntu.get("son_kapanis") is not None:
        sag += f" · {sayi(goruntu['son_kapanis'])}"
    satirlar: list[str] = []
    if alarm.get("etiket"):
        satirlar.append(f"alarm: {alarm['etiket']}")
    # FAZ 4 §2 (Pills / Badges): sol üstteki düz metinler yarı saydam yuvarlatılmış
    # rozetlere dönüştürülür: `[ 📈 ALARK · 4S ]` `[ 📐 Yükselen Üçgen (%83) ]`.
    # İçerik TEK kaynaktan kurulur (aşağıdaki `bilgi` satırı artık formasyon
    # adını/durumunu TEKRAR yazmaz — bilgi rozetlerde durur).
    pill_listesi: list[dict[str, Any]] = []
    q = formasyon.get("quality")
    if q is None:
        q = formasyon.get("effective_quality")
    if q is None:
        q = formasyon.get("raw_quality")
    _sembol_pill = str(goruntu.get("sembol") or "—").upper()
    _tf_pill = str(goruntu.get("tf_kisa") or goruntu.get("tf") or "").upper()
    pill_listesi.append({"metin": f"{_sembol_pill} · {_tf_pill}", "ikon": "sembol",
                         "renk": PALET["metin"], "dolgu": PALET["panel"],
                         "kenar": PALET["panel_kenar"]})
    if formasyon.get("ad"):
        _ad_pill = f"{formasyon['ad']}"
        if q is not None:
            _ad_pill += f" · kalite {int(round(float(q)))}/100"
        pill_listesi.append({"metin": _ad_pill, "ikon": "formasyon",
                             "renk": PALET["formasyon"],
                             "dolgu": PALET["formasyon"], "kenar": PALET["formasyon"]})
    _durum_pill = formasyon_durum_etiketi(formasyon.get("state"))
    if _durum_pill:
        pill_listesi.append({"metin": _durum_pill, "renk": PALET["eksen"],
                             "dolgu": PALET["panel"], "kenar": PALET["panel_kenar"]})
    bilgi: list[str] = []
    if formasyon.get("contraction") is not None:
        # kartla aynı biçim: `notifier.py:309` → `_yuzde(contraction*100, 0)`
        bilgi.append(f"daralma %{sayi(float(formasyon['contraction']) * 100.0, 0)}")
    # BANT TEMASI: kart `temas üst 2 / alt 3` diye AYRI sayar; karede tek sayı
    # yazmak kartla çelişiyordu (üçgen karesinde "bant teması 39" gibi, iki
    # sınırın toplamı olan bir sayı). Formasyon kaydındaki gerçek alanlar
    # (`upper_touches`/`lower_touches`) varsa onlar yazılır — kare ile kart
    # aynı sayıyı söyler. Alan yoksa tek toplam, "toplam" diye ETİKETLENİR.
    _ust_t = _tam(formasyon.get("upper_touches"))
    _alt_t = _tam(formasyon.get("lower_touches"))
    if _ust_t is not None or _alt_t is not None:
        # 2026-10-23: kart dili (`· üste 2, alta 2 kez değdi`) kareye de geçti;
        # `temas üst 2 / alt 2` jargondu.
        bilgi.append(f"üste {_ust_t if _ust_t is not None else '—'},"
                     f" alta {_alt_t if _alt_t is not None else '—'} kez değdi")
    elif formasyon.get("upper_now") is not None or formasyon.get("lower_now") is not None:
        bilgi.append(f"bant toplam {len(goruntu.get('temas') or [])} kez değdi")
    if alarm.get("deger") is not None:
        # `seviye` hangi seviye? Kart `· kırılan 65,97` diyor; kare de öyle.
        parca = f"kırılan {sayi(alarm['deger'])}"
        if alarm.get("kapanis") is not None:
            fark = float(alarm["kapanis"]) - float(alarm["deger"])
            # Ölçü yüzde olarak yazılır (kart da `+%1,7` diyor); sıfıra bölme yok.
            taban = abs(float(alarm["deger"])) or 1.0
            yuzde = abs(fark) / taban * 100.0
            parca += (f" · kapanış {sayi(alarm['kapanis'])} "
                      f"· %{sayi(yuzde, 1)} {'üstünde' if fark >= 0 else 'altında'}")
        bilgi.append(parca)
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
    # L11: yapı satırı SONRA gelir ve ÜÇÜNCÜ satırla kapanır — dördüncü satır üst
    # bloğu eksenlere taşırırdı (ölçüm: y=0,844 < `ust`=0,855), o yüzden yer yoksa
    # çizilmez ve `kesilen`de görünür (sessiz kayıp yok).
    motor = _grafik_yapi_metni(goruntu.get("yapı_satırı") or "")
    if motor and not yalnizca_mumlar and len(satirlar) < 3:
        yeni_satir, k = _kirp(motor, genislik * 0.88)
        satirlar.append(yeni_satir)
        if k:
            kesilen.append(yeni_satir)
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
    # Hacimsiz bar sayısı yukarıdaki dipnotta zaten yazılı (aynı pencere, aynı
    # sayı); burada ikinci kez yazılmaz.
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
    # GÖRSEL-7: `lejant: N madde sığmadı` kırmızı dipnotu KALDIRILDI. Kareye
    # yazılan bu not okuyucuya hiçbir şey söylemiyordu (madde zaten çizilmemiş);
    # sayı `meta["lejant_atlanan"]`da makine okunur biçimde durur.
    lejantlar, lejant_punto, lejant_atlanan = _lejant_satirlar(
        _lejant(goruntu, yalnizca_mumlar), genislik)
    # BAŞLIK ÇAKIŞMASI (2026-10-23, mobil ölçümü): rozetler + sağdaki "son mum …"
    # yazısı dar karede aynı satıra sığmıyor; "son mum" bilgi satırının ÜSTÜNE
    # biniyordu. Genişlikler GERÇEK renderer ölçümünden gelir (`_olcu_px`);
    # sığmıyorsa sağ yazı KENDİ satırına iner (satır sayısı burada belli olur ki
    # eksen üst sınırı ona göre ayrılsın).
    sag_ayri = False
    if not yalnizca_mumlar:
        try:
            rozet_px = sum(_olcu_px(f"{_ikon(str(p.get('ikon') or ''))} "
                                    f"{p.get('metin') or ''}".strip(),
                                    float(SABITLER["baslik_pt"])) + 22.0
                           for p in pill_listesi[:4])
            sag_px = _olcu_px(sag, float(SABITLER["durum_pt"])) + 12.0
            # Sol/sağ kenar boşlukları da düşülür (rozetler `sol_kenar`dan başlar).
            sag_ayri = (rozet_px + sag_px + 18.0) > float(genislik) * 0.94
        except Exception:      # pragma: no cover - ölçüm süsü
            sag_ayri = False
    return {"baslik": baslik, "sag": sag, "sag_ayri_satir": sag_ayri,
            "satirlar": satirlar,
            "pill_listesi": ([] if yalnizca_mumlar else pill_listesi),
            "lejant": lejantlar, "lejant_punto": lejant_punto,
            "lejant_atlanan": lejant_atlanan,
            "dipnotlar": dipnotlar[:4], "notlar": notlar[:4], "kesilen": kesilen,
            "butce": SATIR_BUTCE, "genislik": genislik}


def _lejant(goruntu: Mapping[str, Any], yalnizca_mumlar: bool) -> list[str]:
    """Çizilen ne ise o (§0.12v); uydurma etiket yok — katman yoksa madde de yok."""
    if yalnizca_mumlar:
        return ["yalnızca mumlar (çökme modu)"]
    if goruntu.get("sade"):
        return ["sade mod: yalnız mum + formasyon bandı + kritik/son fiyat"]
    formasyon = goruntu.get("formasyon") or {}
    alarm = goruntu.get("alarm") or {}
    # Renk şeması lejantta AÇIKÇA yazılır (GÖRSEL-3): yeşil boş / kırmızı dolu.
    # Renk adları MODDAN gelir: renk körü modunda "yeşil/kırmızı" yazmak yalan
    # olurdu (lejant çizileni anlatır kuralı — §0.12v).
    if _MOD.palet:
        oge = ["kapanmış mum", "mavi boş = yükselen", "turuncu dolu = düşen"]
    else:
        oge = ["kapanmış mum", "yeşil boş = yükselen", "kırmızı dolu = düşen"]
    # GÖRSEL-5: olay çizgileri stil olarak ayrıştı; lejant da ayrı yazar (hangisi
    # görünüyorsa o madde çıkar — uydurma yok).
    _olaylar = list((goruntu.get("olay") or {}).get("olaylar") or [])
    if any(str(b.get("tur") or "").upper().startswith("CHO") for b in _olaylar):
        oge.append("┈ CHoCH dış")
    if any(not str(b.get("tur") or "").upper().startswith("CHO") for b in _olaylar):
        oge.append("┄ BOS dış")
    if formasyon.get("upper_now") is not None or formasyon.get("lower_now") is not None:
        oge.append("— formasyon bandı")
        if int(goruntu.get("sol") or 0) > 0:
            oge.append("┄ bant öncesi")
    if goruntu.get("isaretler"):
        oge += ["■ bant başı", "◆ bant sonu", "✕ apex"]
    # PH/PL/WH/WL dış scope'un aktif rol seviyeleridir; iç pivot sınıfından
    # tahmin edilmez ve yalnız gerçek seviye katmanı varsa lejanta girer.
    _seviyeler = list((goruntu.get("olay") or {}).get("seviyeler") or [])
    if _seviyeler:
        oge.append("┈ seviye (PH/PL/WH/WL sağda)")
    # GÖRSEL-7: geçersizleşme karesi kendi dilini yazar (soluk seviye + sınır).
    _gecersiz = str(alarm.get("tur") or "") == "gecersiz"
    if alarm.get("bar") is not None:
        oge.append("✕ geçersizleştiren mum" if _gecersiz else "│ alarm mumu")
    if alarm.get("deger") is not None:
        oge.append("✕ eski seviye (artık geçerli değil)" if _gecersiz else "─ seviye")
    if _gecersiz and alarm.get("teyit_siniri") is not None:
        oge.append("┈ teyit sınırı")
    zone = _grafik_zone(goruntu.get("zone") or {})
    if zone.get("cizilen"):
        _sira = {"ob": 0, "fvg": 1}
        adlar = sorted({str(b.get("tip")) for b in (zone.get("cizilen") or [])},
                       key=lambda a: _sira.get(a, 9))
        oge.append("kutular: " + " ".join(
            {"ob": "OB", "fvg": "FVG"}.get(a, str(a)) for a in adlar))
        if str(goruntu.get("tf")) in _FVG_YOK_TFLAR:
            oge.append("FVG · 4s/1g")
        # Lifecycle aşaması yalnız mevcutsa açıklanır: aday noktalarla,
        # tamamlanan alanlar soluk kesik konturla ayırt edilir.
        _kayitlar = list(zone.get("cizilen") or [])
        if any(str(b.get("durum") or "").upper() in _BOLGE_ARA for b in _kayitlar):
            oge.append("·· aday")
        if any(bool(b.get("tamamlandi")) or
               str(b.get("durum") or "").upper() in _BOLGE_TAMAM for b in _kayitlar):
            oge.append("┄ tamamlandı")
        # GÖRSEL-5: dolgu cetveli ve %50 orta çizgisi yalnız ÇİZİLDİĞİNDE yazılır.
        if any(_gercek(b.get("doluluk")) not in (None, 0.0, 1.0) for b in _kayitlar):
            oge.append("▨ dolan kısım")
        if any(str(b.get("tip")) == "fvg" for b in _kayitlar):
            oge.append("┈ %50 ortası")
    serit = goruntu.get("serit") or {}
    if serit.get("spike"):
        # `yerel hesap` YALNIZ yerel hesaplandığında yazılır (kullanıcı onayı,
        # tur 9); motor serisi gelirse kaynak adı yeter.
        oge.append("şerit: rvol(%s)%s" % (
            sayi(float(serit.get("uzunluk") or SABITLER["hacim_uzunluk"]), 0),
            " · yerel hesap" if serit.get("yerel") else " · motor"))
    olay = _grafik_dis_yapi(goruntu.get("olay") or {})
    _yapi = []
    if olay.get("olaylar"):
        _yapi.append("BOS/CHoCH dış")
    if olay.get("seviyeler"):
        _yapi.append("PH/PL/WH/WL sağda")
    if _yapi:
        # Oklar INTERNAL, kırılım çizgileri ve rol seviyeleri EXTERNAL'dır.
        oge.append("yapı: " + " · ".join(_yapi))
    return oge


