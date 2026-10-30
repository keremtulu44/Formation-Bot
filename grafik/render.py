# grafik/render.py — kare çizim hattı (Faz 2).
# Not: _guven_satirlari/_guven_ciz burada (render↔kare döngüsü kırmak için).

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
    _AY,
    _BOLGE_ARA,
    _BOLGE_DOLU,
    _BOLGE_TAMAM,
    _MOD,
    _alan,
    _butce_px,
    _gercek,
    _kare_olcu,
    _mod_kapsami,
    _ortam_bayrak,
    _ortam_sayi,
    _pyplot_getir,
    _seri_cizim,
    _tarih,
    sag_bosluk_mum,
)
from grafik.geometry import (  # noqa: F401
    _mum_kutulari_px,
    _yatay_aralik,
    _zone_renk,
)
from grafik.indicators import (  # noqa: F401
    _grafik_dis_yapi,
    _grafik_yapi_metni,
    _grafik_zone,
    _mum_cakisma_say,
)
from grafik.overlays import (  # noqa: F401
    _formasyon_ciz,
    _gecersiz_katmani,
)
from grafik.panels import (  # noqa: F401
    _ALT_ADIM,
    _alt_yerlesim,
    _metinler,
    _sag_ciz,
    _sag_ele,
    _sag_panel,
    _serit_ciz,
    _zone_metni,
    _zone_sag_adaylari,
)
from grafik.markers import (  # noqa: F401
    _alarm_ciz,
    _kutu_yazisi_koy,
    _kutu_yazisi_sigar,
    _metin_ciz,
    _olay_ciz,
    _rvol_rozetleri,
    _tik_etiketleri,
    _zone_etiket_engeller,
)
from grafik.tarama import (  # noqa: F401
    _atom_yaz,
    _meta_kur,
    _olay_meta,
    _zone_meta,
    girdi_ozeti,
)

@_seri_cizim
def ciz(goruntu: Mapping[str, Any], tf: Optional[str] = None,
        secenekler: Optional[Mapping[str, Any]] = None) -> tuple[Optional[str], dict[str, Any]]:
    """Kareyi üretir: `(png_yolu, meta)`. Yol `None` → görsel yok, metin yine gider.

    Hesap yapmaz (§14.2): girdi `anlik_goruntu()`nun kopyasıdır. Katman hatası
    çizimi durdurmaz: tam çizim denenir, olmazsa "yalnızca mumlar" (çökme modu)
    ve `eksik:` dipnotu (§2.9). Beklenen son bar uyuşmazsa hiç çizmez (§14.3).
    """
    # Also sanitize snapshots persisted before engulfing was removed.
    goruntu = {**goruntu, "zone": _grafik_zone(goruntu.get("zone") or {}),
               "olay": _grafik_dis_yapi(goruntu.get("olay") or {}),
               "yapı_satırı": _grafik_yapi_metni(goruntu.get("yapı_satırı") or "")}
    baslangic = time.perf_counter()
    secenekler = dict(secenekler or {})
    # Canlı akış modları ENV'den de açılabilir (telefonda okunurluk): GRAFIK_SADE=1,
    # GRAFIK_RENK_KORUGU=1, GRAFIK_YAZI=1.25. CLI bayrağı env'i EZER (açık istek kazanır).
    if "sade" not in secenekler:
        secenekler["sade"] = _ortam_bayrak("GRAFIK_SADE")
    if "renk_korugu" not in secenekler:
        secenekler["renk_korugu"] = _ortam_bayrak("GRAFIK_RENK_KORUGU")
    if "yazi_olcek" not in secenekler and os.environ.get("GRAFIK_YAZI"):
        try:
            secenekler["yazi_olcek"] = float(str(os.environ["GRAFIK_YAZI"]).replace(",", "."))
        except (TypeError, ValueError):
            pass
    tf = str(tf or goruntu.get("tf") or "1h")
    mobil = bool(secenekler.get("mobil", _ortam_bayrak("GRAFIK_MOBIL")))
    secenekler["mobil"] = mobil
    if mobil:
        secenekler["yazi_olcek"] = max(1.35, float(secenekler.get("yazi_olcek") or 1.0))
    kaynak_goruntu = goruntu
    # Sonuç karesinde fiyat değişse de soru anındaki bölgeler ve yapı aynı
    # kalmalı; normal grafikler her zamanki gibi görünüm filtresinden geçer.
    if not (goruntu.get("replay") or {}).get("hazir_gorunum"):
        goruntu = deneyim.prepare_view(goruntu, str(secenekler.get("gorunum") or
                                       os.environ.get("GRAFIK_GORUNUM") or "odak"),
                                       max_distance_atr=max(.1, _ortam_sayi("GRAFIK_ODAK_MESAFE_ATR", 3.0)))
    ayrinti = deneyim.detail_payload(kaynak_goruntu, goruntu)
    olcu = _kare_olcu(goruntu)
    # Sabit mobil genişlik uzun sonuçlarda mumları çok sıkıştırır. Yalnız o
    # sonuç karesinde yeterli genişliği koru; normal çizimleri değiştirme.
    if mobil and (goruntu.get("replay") or {}).get("asama") == "sonuc" and olcu["bar"] > 150:
        mobil = False
        secenekler["mobil"] = False
    if mobil:
        olcu = {**olcu, "genislik": 780, "yukseklik": 1100,
                "px_bar": 780 / max(1, olcu["bar"])}
    meta = _meta_kur(goruntu, tf, olcu)
    meta["guven"] = dict(goruntu.get("guven") or {})
    meta["gorunum"] = dict(goruntu.get("gorunum") or {})
    meta["ayrinti"] = ayrinti
    meta["grafik_politikasi"] = deneyim.POLICY
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
        bayt, ek = _kare_ciz_modlu(goruntu, tf, olcu, meta, secenekler,
                                   yalnizca_mumlar=False)
    except Exception as hata:
        # §4: görsel hiçbir koşulda alarmı engellemez → hata yutulur, kat çöker.
        log.warning("grafik: tam çizim başarısız (%s: %s)", type(hata).__name__, hata)
        meta["uyarilar"] = list(meta["uyarilar"]) + [
            f"çökme modu: {type(hata).__name__}: {hata}"]
        bayt, ek = None, {"cekme": False, "hata": f"{type(hata).__name__}: {hata}"}
    if bayt is None:
        meta["uyarilar"] = list(meta["uyarilar"]) + ["çökme modu: yalnız mumlar çizildi"]
        try:
            bayt, ek2 = _kare_ciz_modlu(goruntu, tf, olcu, meta, secenekler,
                                        yalnizca_mumlar=True)
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


def _kare_ciz_modlu(goruntu: Mapping[str, Any], tf: str, olcu: Mapping[str, Any],
                    meta: Mapping[str, Any], secenekler: Mapping[str, Any], *,
                    yalnizca_mumlar: bool):
    """Mod kapsamı içinde çizer (GÖRSEL-5): `--renk-korugu`, `--buyuk-yazi`, `--sade`.

    Neden burada: `PALET`/`SABITLER` çizim boyunca onlarca yerden okunuyor; kapsam
    thread-local olduğu için iki paralel kare (tarama + gönderim işçisi) birbirinin
    modunu görmez. Çökme modu (`yalnizca_mumlar`) da aynı kapsamdan geçer.
    """
    with _mod_kapsami(secenekler):
        return _pkg._kare_ciz(goruntu, tf, olcu, meta, secenekler,
                         yalnizca_mumlar=yalnizca_mumlar)


def _kare_ciz(goruntu: Mapping[str, Any], tf: str, olcu: Mapping[str, Any],
              meta: Mapping[str, Any], secenekler: Mapping[str, Any], *,
              yalnizca_mumlar: bool) -> tuple[Optional[bytes], dict[str, Any]]:
    """Asıl çizim → `(png_baytı, meta_ekleri)`. Dosyaya yazmak `ciz`'in işi."""
    eksik: list[str] = list(meta.get("eksik_katmanlar") or [])
    budama: list[str] = list(meta.get("budama") or [])
    # GÖRSEL-5 `--sade`: yalnız mum + formasyon bandı + kritik/son fiyat kalır.
    # Katmanlar VERİDEN kesilir (çizim fonksiyonları koşul yığınıyla şişmesin);
    # kesilen katman `eksik`e YAZILMAZ — bu bilinçli bir okuma modu, veri kusuru değil.
    sade = bool(secenekler.get("sade"))
    _sade_atlanan = 0
    if sade:
        # meta DÜRÜST kalır: "4 kutu vardı, sade modda çizilmedi" (0 çizildi ama
        # atlanan sayısı görünür → sessiz kayıp yok).
        _sade_atlanan = len((meta.get("ayrinti") or {}).get("bolgeler") or []) or int((meta.get("zone") or {}).get("cizilen") or 0)
        meta["zone"] = _zone_meta(None)
        gorunum = {**(goruntu.get("gorunum") or {}), "mod": "sade", "gosterilen": 0,
                   "gizlenen": int((goruntu.get("gorunum") or {}).get("toplam") or 0)}
        meta["gorunum"] = gorunum
        meta.setdefault("ayrinti", {})["gorunum"] = dict(gorunum)
        for z in meta["ayrinti"].get("bolgeler", []):
            z["gorunur"], z["gorunum_nedeni"] = False, "sade görünüm"
        goruntu = {**goruntu, "zone": {}, "serit": {}, "temas": [], "isaretler": [],
                   "gorunum": gorunum, "sade": True}
        _olay_sade = dict(goruntu.get("olay") or {})
        goruntu["olay"] = {**_olay_sade, "swinglar": [], "seviyeler": [], "olaylar": []}
    n = int(olcu["bar"])
    etiket_detay = bool(secenekler.get("etiket_detay", SABITLER["etiket_detay"]))
    # FAZ 1: alt hacim paneli VARSAYILAN OLARAK ÇİZİLMEZ (kazanılan ~%20 dikey
    # alan ana panele verilir); RVOL bilgisi mum altındaki ⚡ rozetiyle taşınır.
    # `GRAFIK_HACIM_PANELI=1` (veya `serit=True`) eski kulvarı geri getirir.
    # `serit` seçeneği: True → paneli ZORLA aç (eski görünüm/CLI bayrağı),
    # False → zorla kapat, verilmemişse env/varsayılan (FAZ 1: kapalı).
    if "serit" in secenekler:
        serit_istendi = bool(secenekler.get("serit"))
    else:
        serit_istendi = _ortam_bayrak("GRAFIK_HACIM_PANELI", bool(SABITLER["hacim_paneli"]))
    serit_istendi = bool(serit_istendi and goruntu.get("serit") and not sade)
    # FAZ 1: kare içi lejant/dipnot bloğu kaldırıldı. Metin yine üretilir ve
    # `meta["metin"]`den kart altı dipnotuna gider (notifier._grafik_basligi).
    alt_blok = bool(secenekler.get("kare_lejant", _ortam_bayrak("GRAFIK_LEJANT_KARE",
                                                               SABITLER["kare_lejant"])))
    plt, fig = None, None
    kalite = None
    try:
        plt = _pyplot_getir()
        dpi = int(SABITLER["dpi"])
        genislik, yukseklik = int(olcu["genislik"]), int(olcu["yukseklik"])
        # Üst blok satır başına 0,031 yiyor: iki satır bugün olduğu yer (0,855),
        # üçüncü satır (L11 yapı satırı) eksene değmesin diye eksen 0,031 daha iner.
        metin = _metinler(goruntu, meta, genislik, eksik, yalnizca_mumlar, etiket_detay)
        # `sag_ayri_satir`: rozetlerle sığmayan "son mum …" yazısı KENDİ satırına
        # iner → üst blok bir satır daha yer ister (aksi hâlde eksene değer).
        ust = (0.855 if metin["satirlar"] else 0.885) - 0.031 * max(
            0, len(metin["satirlar"]) - 2) - (0.031 if metin.get("sag_ayri_satir") else 0.0)
        sol_kenar, sag_metin = (0.12 if _MOD.mobil else 0.075), 0.985
        sag_kenar = (sag_metin * genislik - float(SABITLER["sag_serit_px"])) / genislik
        if alt_blok:
            alt, y_lejant, _, _ = _alt_yerlesim(len(metin["dipnotlar"]) + 2,
                                               len(metin.get("notlar") or []),
                                               len(metin["lejant"]))
        else:
            # Yazı bloğu yok → eksen karenin dibine iner (FAZ 1: alan mumlara).
            alt, y_lejant = 0.028, None
        guven_satirlari = _guven_satirlari(goruntu, genislik, yalnizca_mumlar)
        guven_adim = float(SABITLER["dipnot_pt"]) * dpi / 72.0 * 1.55 / yukseklik
        guven_alt = 0.055 + guven_adim * len(guven_satirlari)
        if alt_blok:
            alt += guven_alt
            y_lejant += guven_alt
        else:
            alt = max(alt, guven_alt)
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
            # Şerit kulvarı hafif PANEL zemini: iki kulvar bir bakışta ayrılır.
            a.set_facecolor(PALET["zemin"] if a is ax else PALET["panel"])
            a.tick_params(colors=PALET["eksen"], labelsize=SABITLER["eksen_pt"], length=0, pad=2)
            for kenar in a.spines.values():
                kenar.set_color(PALET["panel_kenar"] if a is ax_serit else PALET["grid"])
                kenar.set_linewidth(0.6)
        for a, adlar in ((ax, ("top", "right")), (ax_serit, ("right", "bottom"))):
            if a is None:
                continue
            for ad in adlar:
                a.spines[ad].set_visible(False)
        if ax_serit is not None:
            # Şerit kulvarının ÜST kenarı: iki kulvarı ayıran ince panel çizgisi.
            ax_serit.spines["top"].set_color(PALET["panel_kenar"])
            ax_serit.spines["top"].set_linewidth(0.7)
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
        if alarm.get("hedef") is not None:
            ek_y.append(float(alarm["hedef"]))     # FAZ 4 §4: 🎯 hedef kadrajda kalsın
        zone = goruntu.get("zone") or {}
        for b in (_grafik_zone(zone).get("cizilen") or []):
            ek_y.extend([float(b["alt"]), float(b["ust"])])
        _olay_src = goruntu.get("olay") or {}
        for b in (_olay_src.get("swinglar") or []):        # iç pivot okları
            v = _gercek(b.get("fiyat"))
            if v is not None:
                ek_y.append(v)
        for b in (_olay_src.get("seviyeler") or []):       # dış PH/PL/WH/WL cetveli
            v = _gercek(b.get("fiyat"))
            if v is not None:
                ek_y.append(v)
        # BOS/CHoCH/kritik seviyeleri: yalnız mum aralığına yakınsa çizilir ve
        # aralığı genişletir. Eski ve uzak seviyeler (ör. 3 hafta önceki kırılım
        # 8% üstte) eskiden tüm grafiği sıkıştırıyordu; şimdi sayılır, çizilmez.
        replay = goruntu.get("replay") or {}
        kesit = replay.get("kesit") if replay.get("asama") == "sonuc" else None
        # Olayların kadraja alınıp alınmaması soru anındaki mumlarla belirlenir;
        # sonuç mumları ancak sonrasında fiyat ekseninin genişlemesini sağlar.
        olay_son = int(kesit) + 1 if kesit is not None else n
        ham = [float(v) for v in (kapanis[:olay_son] + yuksek[:olay_son]
                                  + dusuk[:olay_son]) if v is not None]
        taban = ham + ek_y
        t_lo, t_hi = (min(taban), max(taban)) if taban else (0.0, 1.0)
        kadraj_pay = float(SABITLER["kadraj_pay_orani"]) * max(t_hi - t_lo, 1e-9)
        kadrajda = (lambda v: t_lo - kadraj_pay <= v <= t_hi + kadraj_pay)
        kabul_olaylar, kadraj_disi = [], 0
        for b in (_olay_src.get("olaylar") or []):
            v = _gercek(b.get("seviye"))
            if v is None:
                continue
            if kadrajda(v):
                kabul_olaylar.append(b)
                ek_y.append(v)
            else:
                kadraj_disi += 1
        kritik_ham = dict(_olay_src.get("kritik") or {})
        kritik_kabul: dict[str, Any] = {}
        if kritik_ham.get("seviye") is not None:
            if kadrajda(float(kritik_ham["seviye"])):
                kritik_kabul = kritik_ham
                ek_y.append(float(kritik_ham["seviye"]))
            else:
                kadraj_disi += 1
        goruntu = {**goruntu, "olay": {**_olay_src, "olaylar": kabul_olaylar,
                                       "kritik": kritik_kabul}}
        # Bant doğruları y-aralığını BELİRLEMEZ (2026-10-23 ölçümü): seriyi
        # olduğu gibi aralığa katmak, bandın fiyattan kopuk bölümünü (üçgenin
        # geriye uzanan tabanı, dik yükselen alt çizgi) da hesaba katıyor ve
        # mumları sıkıştırıyordu — AKBNK 1s'te mumlar kare yüksekliğinin yalnız
        # %29'una sığıyordu. Aralık MUM + kutu + seviye + alarm + bandın
        # `upper_now/lower_now` (son bardaki gerçek) değerlerinden kurulur;
        # bandın kadraj dışına taşan kısmı `_formasyon_ciz` içinde kesilir
        # (uydurma geometri yok, çizgi yalnız görünür aralıkta).
        aralik = _yatay_aralik(kapanis + yuksek + dusuk, ek_y)
        ax.set_ylim(*aralik)
        meta["kare"]["y_araligi"] = [round(aralik[0], 6), round(aralik[1], 6)]
        # Bölge etiketleri sağa taşabiliyor → eksene NEFES PAYI eklenir (veri
        # kırpılmaz; son mum her zaman görünür kalır, §0.13).
        sag_bosluk = sag_bosluk_mum(n)      # son mumun sağındaki BOŞ alan (bar; eksen payı)
        ax.set_xlim(-0.6, n - 0.4 + sag_bosluk)
        meta["kare"]["x_siniri"] = [-0.6, round(n - 0.4 + sag_bosluk, 3)]
        meta["kare"]["sag_bosluk"] = int(sag_bosluk)
        meta["kare"]["sag_bosluk_yuzde"] = round(
            100.0 * sag_bosluk / (n + 0.2 + sag_bosluk), 2)
        butce = _butce_px(genislik)
        katman_n = max(1, min(n, int(kesit) + 1)) if kesit is not None else n
        katman_bosluk = 0 if kesit is not None else sag_bosluk
        if kesit is not None:
            sinir = float(katman_n) - 0.5
            if katman_n < n:
                ax.axvspan(sinir, n - 0.5, color=PALET["panel"], alpha=0.3, zorder=0)
            ax.axvline(sinir, color=PALET["eksen"], linewidth=1.0,
                       linestyle=(0, (4, 3)), alpha=0.85, zorder=3)
            ax.annotate("TAHMİN ANI", (sinir, 1), xycoords=ax.get_xaxis_transform(),
                        xytext=(4, -5), textcoords="offset points", ha="left",
                        va="top", fontsize=7, color=PALET["eksen"], zorder=6)
        sayac_rozet: dict[str, Any] = {"artis": 0, "dusus": 0,
                                       "taze_artis": None, "taze_dusus": None}
        # Mum gövde genişliği VERİ birimindedir (x = bar indeksi, komşu barlar
        # arası 1,0). Eskiden `px_bar × 0,62` yazılıyordu: px/bar = 6 iken gövde
        # 3,7 bar genişliğinde çiziliyor, komşu mumların üstüne biniyordu.
        cap = float(SABITLER["mum_genislik_orani"])

        sag_adaylar: list[dict[str, Any]] = []
        # Mum kutuları (piksel) bir kez: kutu içi yazı ve olay etiketi yerleşimi
        # aynı ölçümü kullanır (GÖRSEL-4).
        try:
            mum_kutulari = _mum_kutulari_px(ax, acilis, yuksek, dusuk, kapanis, cap)
        except Exception:
            mum_kutulari = None
        # --- bölge kutuları mumların ARDINDA (bilgi zemini; §0.4.1) ---
        if not yalnizca_mumlar and (zone.get("cizilen") or []):
            try:
                zone_ozet = _zone_ciz(ax, zone, katman_n, aralik, sag_adaylar,
                                      kutular=mum_kutulari, sag_bosluk=katman_bosluk,
                                      engel_y=_zone_etiket_engeller(goruntu)) or {}
                meta["zone"]["etiket_ic"] = int(zone_ozet.get("ic") or 0)
                meta["zone"]["etiket_serit"] = int(zone_ozet.get("serit") or 0)
                # GÖRSEL-5: bilgi artık geometride de var — sayaçlar sessiz kayıp olmasın.
                meta["zone"]["dolgu"] = int(zone_ozet.get("dolgu") or 0)
                meta["zone"]["orta"] = int(zone_ozet.get("orta") or 0)
                meta["zone"]["kunye"] = int(zone_ozet.get("kunye") or 0)
            except Exception as hata:
                log.warning("grafik: bölge katmanı çizilemedi (%s)", hata)
                eksik.append("zone")

        # --- yapı katmanı: swing + BOS/CHoCH + kritik (§2.2) ---
        olay_ozet = {"swing": 0, "etiket_atlandi": 0, "kritik": 0,
                     "kritik_atlandi": 0, "capa": 0, "phpl_serit": 0,
                     "whwl_serit": 0, "seviye": 0}
        if not yalnizca_mumlar and (goruntu.get("olay") or {}):
            try:
                olay_ozet.update(_olay_ciz(ax, goruntu, katman_n, sag_adaylar,
                                           kutular=mum_kutulari,
                                           sag_bosluk=katman_bosluk) or {})
            except Exception as hata:
                log.warning("grafik: yapı katmanı çizilemedi (%s)", hata)
                eksik.append("ms")
                olay_ozet["hata"] = "cizim"
        meta["olay"] = _olay_meta(goruntu.get("olay"), olay_ozet)
        meta["olay"]["kadraj_disi"] = int(kadraj_disi)
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
            _pkg._mumlar_ciz(ax, acilis, yuksek, dusuk, kapanis, cap, aralik)
            # FAZ 1: hacim paneli kaldırıldı — sıra dışı hacim mumun ALTINA yönlü
            # rozetle yazılır: `⚡↑ x2,5` patlama (RVOL > 2,0×), `⚡↓ x0,5` kuruma
            # (RVOL ≤ 0,5×). Panelin %20'lik dikey alanı ana grafiğe kaldı; bilgi
            # kaybı yok (RVOL sayısı ve YÖNÜ rozette okunur).
            try:
                sayac_rozet = _rvol_rozetleri(ax, goruntu, n, dusuk, yuksek, fig=fig)
            except Exception as hata:
                log.debug("grafik: rvol rozetleri çizilemedi (%s)", hata)

        if not yalnizca_mumlar:
            try:
                meta["cizgiler"]["formasyon"] = _pkg._formasyon_ciz(
                    ax, goruntu, katman_n, butce, metin, sag_bosluk=katman_bosluk,
                    aralik=aralik, yuksek=yuksek[:katman_n], dusuk=dusuk[:katman_n])
            except Exception as hata:
                log.warning("grafik: formasyon katmanı çizilemedi (%s)", hata)
                eksik.append("formasyon")
            try:
                _alarm_ciz(ax, alarm, n, butce, sag_adaylar)
            except Exception as hata:
                log.warning("grafik: alarm katmanı çizilemedi (%s)", hata)
                eksik.append("alarm")
            try:
                _gecersiz_katmani(ax, goruntu, alarm, sag_adaylar, n)
            except Exception as hata:
                log.warning("grafik: geçersizlik katmanı çizilemedi (%s)", hata)
                eksik.append("geçersizlik")
        else:
            eksik = sorted(set(eksik) | {"formasyon", "alarm", "temas"})

        sag_ozet: dict[str, Any] = {"yerlesen": 0, "atlanan": 0, "atlanan_kaynak": {}}
        # Sağ şerit PANELİ: etiketler koyu bir kulvarda toplanır (ilişki görünür).
        if not yalnizca_mumlar:
            _sag_panel(fig, ax, sag_kenar, sag_metin, alt_ax=ax_serit)
        if not yalnizca_mumlar and kapanis and kapanis[-1] is not None:
            son = float(kapanis[-1])
            yukari = acilis[-1] is None or float(kapanis[-1]) >= float(acilis[-1])
            # Son fiyat çizgisi de MUMUN yönünde renklenir (eskiden hep yükselen
            # rengindeydi: düşen kapanışta grafik yanlış renk ima ediyordu).
            ax.axhline(son, color=PALET["mum_yukselen"] if yukari else PALET["mum_dusen"],
                       linewidth=0.7, linestyle=(0, (1, 3)), alpha=0.5, zorder=1)
            sag_adaylar.append({"kaynak": "son", "x": float(n) - 0.4, "y": son,
                                "metin": sayi(son), "renk": PALET["zemin"],
                                "bg": PALET["mum_yukselen"] if yukari else PALET["mum_dusen"],
                                "sabit": True, "oncelik": 9})
        if not yalnizca_mumlar:
            _son_kapanis = (_gercek(kapanis[-1]) if kapanis and kapanis[-1] is not None else None)
            elenen = _sag_ele(sag_adaylar, _son_kapanis)
            sag_ozet = _pkg._sag_ciz(ax, fig, sag_adaylar, n, aralik,
                                x_kenar=n - 0.4 + sag_bosluk)
            sag_ozet["eledi_kaynak"] = elenen
        meta["mod"] = {"sade": bool(sade), "renk_korugu": bool(_MOD.palet),
                       "yazi_olcek": round(float(_MOD.yazi_olcek), 3), "mobil": bool(_MOD.mobil),
                       "atlanan_kutu": int(_sade_atlanan)}
        meta["sag"] = {"yerlesen": sag_ozet["yerlesen"], "atlanan": sag_ozet["atlanan"],
                       # FAZ 4 §1: çakışma önleyici kaydırma ve lider çizgisi sayıları
                       "kaydirilan": int(sag_ozet.get("kaydirilan") or 0),
                       "lider": int(sag_ozet.get("lider") or 0),
                       "sirali": bool(sag_ozet.get("sirali")),
                       "eledi_kaynak": dict(sag_ozet.get("eledi_kaynak") or {}),
                       # GÖRSEL-6: kaynak bazında ATLANAN çipler de görünür olsun
                       # (son fiyatla aynı banttaki PH/PL + sığmayanlar).
                       "atlanan_kaynak": dict(sag_ozet.get("atlanan_kaynak") or {}),
                       # GÖRSEL-5: aynı seviyedeki kutu çipleri tek çipte birleşti.
                       "birlesik": int(sag_ozet.get("birlesik") or 0),
                       "birlesen_kutu": int(sag_ozet.get("birlesen_kutu") or 0)}
        meta["zone"]["etiket_atlandi"] = int(sag_ozet["atlanan_kaynak"].get("zone", 0))
        meta["olay"]["etiket_atlandi"] = int(sag_ozet["atlanan_kaynak"].get("olay", 0))
        if replay:
            # Gerçek zamanlar motorlarda kalır; eksene hiçbir tarih/saat çıkmaz.
            ax.set_xticks([])
            if ax_serit is not None:
                ax_serit.set_xticks([])
        else:
            _tik_etiketleri(ax, zamanlar, str(goruntu.get("tf") or tf))
        ax.yaxis.grid(True, linestyle=":", color=PALET["grid"],
                      linewidth=SABITLER["cizgi_kalinlik"]["grid"])
        ax.set_axisbelow(True)
        from matplotlib.ticker import FuncFormatter
        ax.yaxis.set_major_formatter(FuncFormatter(lambda _v, _p: sayi(_v)))
        # `acik` = kulvar gerçekten çizildi mi (`--serit-yok`/katman hatası → False)
        meta["serit"]["acik"] = ax_serit is not None
        # FAZ 1 (2026-10-16 güncellemesi): hacim verisi artık kulvarda değil mum
        # altındaki YÖNLÜ ⚡ rozetinde yaşar — `rozet` toplamı, `rozet_artis`
        # (patlama) ve `rozet_dusus` (kuruma) sayaçları meta'da durur.
        meta["serit"]["rozet"] = int(sayac_rozet.get("artis", 0)
                                       + sayac_rozet.get("dusus", 0))
        meta["serit"]["rozet_artis"] = int(sayac_rozet.get("artis", 0))
        meta["serit"]["rozet_dusus"] = int(sayac_rozet.get("dusus", 0))
        # Tazelik önceliği izleri: en yeni uygun mumun rozeti çizildiyse barı.
        meta["serit"]["rozet_taze_artis"] = sayac_rozet.get("taze_artis")
        meta["serit"]["rozet_taze_dusus"] = sayac_rozet.get("taze_dusus")
        meta["serit"]["panel"] = bool(ax_serit is not None)
        if ax_serit is not None:
            _serit_ciz(ax_serit, goruntu, n, sag_bosluk=sag_bosluk)
        metin = _metinler(goruntu, meta, genislik, eksik, yalnizca_mumlar, etiket_detay)
        if alt_blok and alt_yerlesimi is not None:
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
        _pkg._metin_ciz(fig, metin, sol_kenar, sag_metin, ust, alt_blok=alt_blok)
        _guven_ciz(fig, guven_satirlari, guven_adim, guven_alt)
        meta["guven_satirlari"] = guven_satirlari
        kalite = _mum_cakisma_say(fig, ax, acilis, yuksek, dusuk, kapanis, cap)

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
            except Exception:  # noqa: S110 - teardown; kapanış hatası çizim sonucunu etkilemez / pragma: no cover
                pass

    return bayt, {"kalite": kalite, "eksik_katmanlar": sorted(set(eksik)), "budama": budama,
                  "lejant_satir": len(metin["lejant"]),
                  "lejant_atlanan": int(metin.get("lejant_atlanan") or 0),
                  "metin": metin, "cekme": bool(yalnizca_mumlar or olcu["cekme"]),
                  "serit_acik": serit_istendi, "hata": None}


def _mumlar_ciz(ax, acilis, yuksek, dusuk, kapanis, cap: float,
                aralik: Sequence[float]) -> None:
    """Fitil + gövde. Gövde yüksekliği sıfır olan (açılış=kapanış) mum görünür kalsın.

    GÖRSEL-3: yükselen mum YEŞİL ve içi BOŞ (saydam yeşil dolgu), düşen mum
    KIRMIZI ve DOLU. Dolgu saydamlığı sayesinde içi boş gövde koyu zeminde de
    "boş" okunur; doluluk farkı renk körlüğünde ikinci kanal olur.
    """
    min_govde = max((aralik[1] - aralik[0]) * 0.0015, 1e-9)
    for i in range(len(kapanis)):
        a, k, y, d = acilis[i], kapanis[i], yuksek[i], dusuk[i]
        if None in (a, k, y, d):
            continue
        yukselen = k >= a
        renk = PALET["mum_yukselen"] if yukselen else PALET["mum_dusen"]
        # Fitil kalınlığı sabit ~1,2 px (0,85 pt @ 100 dpi): gövdeyle orantılı
        # değil, okunurluk için sabit; gövde kenarı ~1 px.
        ax.plot([i, i], [d, y], color=renk, linewidth=float(SABITLER["fitil_pt"]),
                solid_capstyle="butt", zorder=2)
        taban, tavan = sorted((a, k))
        ax.bar([i], [max(tavan - taban, min_govde)], bottom=taban, width=cap,
               facecolor=(PALET["mum_yukselen_ic"] if yukselen else renk),
               edgecolor=renk, linewidth=float(SABITLER["govde_kenar_pt"]), zorder=3)


def _cizgi_ve_alan(ax, kapanis, aralik: Sequence[float]) -> None:
    """Çökme/`çizgi modu`: kapanış çizgisi + basamaklı alan (§17.8 denemesi).

    Renk NÖTR (ne yeşil ne kırmızı): bu modda gövde yok, dolayısıyla yön bilgisi
    mumdan gelmiyor — renk yön ima ETMEMELİ.
    """
    xs = [i for i, v in enumerate(kapanis) if v is not None]
    if not xs:
        return
    ys = [kapanis[i] for i in xs]
    ax.plot(xs, ys, color=PALET["metin"], linewidth=1.0, zorder=3)
    ax.fill_between(xs, aralik[0], ys, step="mid", color=PALET["golge"], alpha=0.07, zorder=1)


def _zone_kunye(b: Mapping[str, Any]) -> str:
    """Kutu künyesi: oluşum tarihi (`12 Eyl`) — bölgenin yaşı karar vericidir.

    Motor alanı `source_time` (OB) / `formation_time` (FVG). Alan yoksa boş döner
    ve kutu tek satır etiketle çizilir (uydurma tarih yazılmaz).
    """
    ham = b.get("zaman")
    if not ham:
        return ""
    try:
        dt = datetime.fromisoformat(str(ham))
    except (TypeError, ValueError):
        return ""
    return f"{dt.day:02d} {_AY.get(dt.month, '')}".strip()


def _zone_ciz(ax, zone: Mapping[str, Any], n: int, aralik: Sequence[float],
              sag: Optional[list] = None,
              kutular: Any = None, *, sag_bosluk: int = 0,
              engel_y: Sequence[float] = ()) -> dict[str, int]:
    """Yalnız OB/FVG kutuları + KUTU İÇİ yazı. Dönüş: sayaç sözlüğü.

    FAZ 3 §1/§2 kuralları (kullanıcı planı 2026-10-15):
      * TAZE OB (doluluk ≈ 0): canlı dolgu (%25), belirgin DÜZ dış çizgi.
      * KISMEN DOLMUŞ OB: kalan açık alan %12 canlı renkte kalır, DOLAN bant mat
        griye (`PALET["dolan"]`, %8) döner; dış çizgi kesiklidir ve sınır çizgisi
        "ne kadarı tükendi" cetvelini verir.
      * KIRILMIŞ/GEÇERSİZ OB: kutu boşalır, yalnız çok silik bir iz kalır.
      * FVG: doluluk hesabı YAPILMAZ — aktif dengesizlik bölgesi olarak tek ton
        (boğa turkuaz / ayı mor) + ince kesikli kontur; OB ile karışmaz.
    Etiket kutunun İÇİNDE (`OB↓ %41`): "hangi kutu, ne kadarı dolu" kutunun kendinde.
    Yazı sığmazsa (kutu çok ince/dar) etiket sağ şeride yedeklenir ve `sag` listesine
    eklenir; hiçbir etiket sessizce düşmez.

    Kalın kenar boğada ALT, ayıda ÜST kenarda (§0.12r): boğa/ayı ayrımı renk
    değiştirmeden de okunur.

    `kutular` verilirse (mum piksel kutuları) ve `engel_y` yapısal yatay çizgileri
    bildirirse, yazı kutu içinde çakışmasız konuma kaydırılır; mümkün değilse
    en az çakışan konum veya sağ şerit yedeği seçilir.
    """
    from matplotlib.patches import Rectangle

    renk = {"ob": PALET["ob"], "fvg": PALET["fvg"], "eng": PALET["engulf"]}
    gorunur = max(1e-9, float(aralik[1]) - float(aralik[0]))
    dolgu = SABITLER["doldurma"]
    kalinlik = SABITLER["zone_kalinlik"]
    ic, seride = 0, []
    dolgu_sayisi, orta_sayisi, kunye_sayisi = 0, 0, 0
    # Kutu yüksekliği PİKSEL cinsinden ölçülür (orta çizgi/ince kutu kararı).
    try:
        _ax_px = ax.get_window_extent()
        _px_birim = float(_ax_px.height) / max(1e-9, gorunur)
    except Exception:
        _px_birim = 0.0
    for b in (_grafik_zone(zone).get("cizilen") or []):
        alt, ust = float(b["alt"]), float(b["ust"])
        x0, x1 = int(b.get("x0") or 0), int(b.get("x1", n - 1))
        # Son muma kadar uzanan kutu sağ boşluğa da uzar (kutu "devam eder").
        if x1 >= n - 1:
            x1 = x1 + int(sag_bosluk)
        genislik_cizgi = max(1.0, x1 - x0 + 1.0)
        yukseklik = max(ust - alt, gorunur * 0.0015)
        durum = str(b.get("durum") or "").upper()
        tamamlandi = bool(b.get("tamamlandi")) or durum in _BOLGE_TAMAM
        aday = durum in _BOLGE_ARA
        _renk_b = _zone_renk(b)                  # FAZ 3 §2: tip + yön → renk grubu
        # FAZ 3 §A: doluluk artık `mitigated_percentage` ile de gelebilir.
        dol = _gercek(b.get("doluluk"))
        if dol is None:
            for _alan in ("mitigated_percentage", "mitigation", "fill_ratio"):
                _mp = _gercek(b.get(_alan))
                if _mp is None:
                    continue
                dol = max(0.0, min(1.0, (_mp / 100.0) if _mp > 1.0 else _mp))
                break
        _taze_esik = float(SABITLER["ob_taze_esik"])
        _td = str(b["tip"])
        taze = bool(_td == "ob" and (dol is None or dol <= _taze_esik))
        kismen = bool(_td == "ob" and not taze and not tamamlandi)
        # KALAN (hâlâ canlı) alanın alfası — FAZ 3 §2 paleti:
        #   taze OB %25 · kısmen dolmuş OB %12 · FVG %15 (doluluk hesabı yapmaz)
        if b["tip"] == "ob":
            temel_dolgu = float(dolgu["ob_kalan"] if kismen else dolgu["ob_taze"])
        else:
            temel_dolgu = float(dolgu["fvg"])
        if yukseklik / gorunur > float(dolgu["golge_esik_orani"]):
            saydam = float(dolgu["ince"])          # çok yüksek kutu: dolgu daha da açık
        elif aday:
            saydam = temel_dolgu * 0.35
        elif tamamlandi:
            # Geçersizleşen/kırılan kutu: içi BOŞALIR, yalnız silik bir iz kalır.
            saydam = float(dolgu["kapanan"])
        elif durum and durum not in _BOLGE_DOLU:
            saydam = temel_dolgu * 0.5
        else:
            saydam = temel_dolgu
        if b["tip"] == "eng":
            saydam = 0.0                         # engulfing alanı: yalnız sınır çizgisi
        kenar_alfa = 0.30 if tamamlandi else (0.58 if aday else 0.92)
        if taze:
            kenar_alfa = 1.0                     # taze OB: belirgin düz dış çizgi
        if durum and durum not in _BOLGE_DOLU and not (aday or tamamlandi):
            kenar_alfa = 0.72                    # bilinmeyen durum: nötr kontur
        # --- GÖRSEL-8 · TON YÖNÜ -------------------------------------------
        # Kutu artık TEK parça dolgu değil: doldurulmamış (kalan) alan KOYU tonda,
        # DOLAN bant AÇIK tonda çizilir. Çerçeve dolgusuz ayrı bir dikdörtgen.
        # Uçlarda (%0 / %100) bant yoktur; kutu tek parça koyu kalır.
        # DOLAN bant: mat gri (FAZ 3 §2) — "neresi tükendi" canlı renkteki kalan
        # alandan ayrılır. FVG doluluk HESABI YAPMAZ: tek ton, kesikli ince kontur.
        yuk_span = max(ust - alt, gorunur * 0.0015)
        bolunur = (dol is not None and b["tip"] == "ob" and not tamamlandi
                   and _taze_esik < dol <= 0.98)
        parcalar: list[tuple[float, float, float, str]] = []
        sinir = None
        if bolunur:
            # Dolan bant HER ZAMAN kalan alandan soluk kalır (`dolan ≤ kalan×0,75`):
            # çok yüksek kutuda kalan alan `ince` tonuna düşse bile sıralama korunur.
            gri = min(float(dolgu["ob_dolan"]), float(saydam) * 0.75)
            if int(b.get("yon") or 1) >= 0:            # boğa: dolgu ÜSTTEN aşağı
                d_alt, d_ust = ust - yuk_span * dol, ust
                sinir = d_alt
                parcalar = [(d_alt, d_ust, gri, PALET["dolan"]), (alt, d_alt, saydam, _renk_b)]
            else:                                      # ayı: dolgu ALTTAN yukarı
                d_alt, d_ust = alt, alt + yuk_span * dol
                sinir = d_ust
                parcalar = [(d_alt, d_ust, gri, PALET["dolan"]), (d_ust, ust, saydam, _renk_b)]
        else:
            parcalar = [(alt, ust, saydam, _renk_b)]
        for p_alt, p_ust, p_alfa, p_renk in parcalar:
            if p_ust - p_alt <= 0:
                continue
            ax.add_patch(Rectangle((x0 - 0.5, p_alt), genislik_cizgi,
                                   max(p_ust - p_alt, gorunur * 0.0008),
                                   facecolor=p_renk, alpha=p_alfa,
                                   edgecolor="none", zorder=1))
        # Kontur stili bilgiyi renkten BAĞIMSIZ taşır (FAZ 3):
        #   taze OB  → düz (solid) belirgin sınır
        #   kısmen   → kesikli (dolmuş bölge var)
        #   FVG      → ince kesikli (aralık, kutu değil)
        #   aday     → noktalı · tamamlanan → soluk uzun kesik
        if tamamlandi:
            kenar_stili = (0, (4, 3))
        elif aday:
            kenar_stili = (0, (1, 2))
        elif b["tip"] == "fvg":
            kenar_stili = (0, (3, 3))
        elif b["tip"] == "eng":
            kenar_stili = (0, (4, 3))
        elif kismen:
            kenar_stili = (0, (4, 3))
        else:
            kenar_stili = "solid"
        ax.add_patch(Rectangle((x0 - 0.5, alt), genislik_cizgi, yukseklik,
                               facecolor="none", edgecolor=_renk_b,
                               linewidth=float(kalinlik["kenar"]), alpha=kenar_alfa,
                               linestyle=kenar_stili, zorder=1.05))
        # Dolan bandın SINIR çizgisi: "%X dolu" bilgisinin geometrisi (cetvel).
        if sinir is not None:
            ax.plot([x0 - 0.5, x0 - 0.5 + genislik_cizgi], [sinir, sinir],
                    color=PALET["dolan"], linewidth=1.0, alpha=0.9,
                    solid_capstyle="butt", zorder=1.6)
        y_vurgu = alt if b.get("vurgu", "alt") == "alt" else ust   # §0.12r
        ax.plot([x0 - 0.5, x0 - 0.5 + genislik_cizgi], [y_vurgu, y_vurgu],
                color=_renk_b, linewidth=float(kalinlik["vurgu"]),
                alpha=kenar_alfa, solid_capstyle="butt", zorder=2)
        # --- DOLULUK CETVELİ (GÖRSEL-5): motorun dolgu yönüyle AYNI geometri ---
        # Boğa kutuda dolgu üstten aşağı, ayı kutuda alttan yukarı ilerler (bkz.
        # modül başlığı: OB `fill_ratio`, FVG `wick_fill_ratio` formülleri).
        # Dolan kısım daha koyu tonda + sınır ÇİZGİSİ: "%X dolu" bilgisi hem
        # sayı hem GEOMETRİ olarak görünür (kullanıcı: "hem cetvel hem %").
        # (GÖRSEL-8) Dolan bant + sınır çizgisi yukarıda çizildi; burada sayaç.
        if bolunur:
            dolgu_sayisi += 1
        # --- %50 ORTA ÇİZGİSİ (FVG): bölgenin yarısı "consequent encroachment" ---
        # Yalnız okunabilecek kadar yüksek FVG kutularında; ince kutuda gürültü olur.
        if b["tip"] == "fvg" and _px_birim and (yukseklik * _px_birim) >= 8.0:
            yorta = (alt + ust) / 2.0
            orta_alpha = 0.4 if not (aday or tamamlandi) else 0.4 * kenar_alfa
            ax.plot([x0 - 0.5, x0 - 0.5 + genislik_cizgi], [yorta, yorta],
                    color=_renk_b, linewidth=0.6, alpha=orta_alpha,
                    linestyle=(0, (1, 2)), zorder=1.5)
            orta_sayisi += 1
        if not zone.get("etiket_ic", True):
            continue
        # --- kutu İÇİ etiket (GÖRSEL-4): "hangi kutu, ne kadar dolu" kutuda yazılı ---
        metin = _zone_metni(b)
        kunye = _zone_kunye(b)
        # Künye (oluşum tarihi) ikinci satıra YALNIZ sığıyorsa girer; sığmıyorsa
        # tek satırla devam edilir — yazı hiçbir durumda kutudan taşmaz.
        iki = f"{metin}\n{kunye}" if kunye else ""
        if iki and _kutu_yazisi_sigar(ax, b, x0, x1, n + sag_bosluk, aralik, iki):
            kunye_sayisi += 1
        else:
            iki = metin
        if _kutu_yazisi_sigar(ax, b, x0, x1, n + sag_bosluk, aralik, iki) and _kutu_yazisi_koy(
                ax, b, x0, x1, n + sag_bosluk, aralik, iki, _renk_b, kutular,
                engel_y=engel_y):
            ic += 1
        else:
            seride.append({**b, "x1": x1})
    fiyat_kayitlari = [{**b, "x1": int(b.get("x1", n - 1)) +
                        (int(sag_bosluk) if int(b.get("x1", n - 1)) >= n - 1 else 0)}
                       for b in (_grafik_zone(zone).get("cizilen") or [])]
    araliklar = _zone_sag_adaylari(zone, n, yalniz=fiyat_kayitlari)
    if sag is not None:
        sag.extend(araliklar)
    return {"ic": ic, "serit": len(araliklar), "dolgu": dolgu_sayisi,
            "orta": orta_sayisi, "kunye": kunye_sayisi}


def _guven_satirlari(goruntu, genislik, fallback=False):
    """Always-visible essential semantics; independent of technical legend."""
    guven = goruntu.get("guven") or {}
    rows = deneyim.trust_lines(goruntu)
    rows += ["RVOL ↑ hacim artışı / ↓ kuruması · Dolum yüzdesi başarı olasılığı değildir."]
    view = goruntu.get("gorunum") or {}
    rows.append(f"{str(view.get('mod', 'odak')).capitalize()} · {view.get('gosterilen', 0)}/{view.get('toplam', 0)} bölge · "
                f"{view.get('gizlenen', 0)} gizli · {view.get('uzak_seviye', 0)} uzak seviye (ayrıntıda)")
    if view.get("mod") == "odak" and view.get("gosterilen") == 0:
        rows.append("Odakta gösterilecek yakın aktif bölge yok; geçmiş/uzak kayıtlar bağlamda.")
    replay = goruntu.get("replay") or {}
    if replay:
        rows.append("EĞİTİM · tarihler gizli · analiz ve çizimler soru anına aittir.")
        if replay.get("asama") == "sonuc":
            rows.append("Kesikli çizgi: tahmin anı · sağında açılan mumlar.")
    else:
        rows.append("Analiz: " + deneyim.date_text(guven.get("analiz_zamani")))
    if fallback:
        rows[3] = "Çizimde bölge katmanları gösterilemedi; ayrıntı verisi korunuyor."
        rows.insert(0, "ÇİZİM SINIRLI: yalnız mumlar; analiz katmanları gösterilemedi.")
    if int(goruntu.get("hacimsiz_bar") or 0):
        rows.append(f"Veri uyarısı: {goruntu['hacimsiz_bar']} görünür mum hacimsiz.")
    width = max(35, int(genislik * .9 / (6.4 * _MOD.yazi_olcek)))
    return [part for row in rows for part in textwrap.wrap(row, width=width, break_long_words=False)]


def _guven_ciz(fig, satirlar, adim, alt):
    # Start below tick labels; allocate before axes construction, never overpaint.
    y = alt - .045
    for i, line in enumerate(satirlar):
        artist = fig.text(.075, y - i * adim, line, ha="left", va="top",
                          fontsize=SABITLER["dipnot_pt"], color=PALET["eksen"])
        artist.set_gid("grafik-guven")


