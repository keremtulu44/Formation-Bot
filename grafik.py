# -*- coding: utf-8 -*-
"""Grafik katmanı — G1 iskeleti (sözleşme: docs/tasarim/GRAFIK_TASARIM.md §2/§3/§5/§17).

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
    engellemez (§4). Türkçe ondalık virgülü de kabul edilir (`1,5` = `1.5`):
    dağıtım arayüzünde değer virgülle yazılabiliyor (`GRAFIK_YAZI` ile aynı kural).
    """
    try:
        ham = (os.environ.get(ad) or "").strip().replace(",", ".")
        return float(ham) if ham else float(varsayilan)
    except (TypeError, ValueError):
        return float(varsayilan)


# §5'teki sabit bloğun birebir hali; sayılar §17 ölçümlerinden.
class _ModKapsami(threading.local):
    """Mod kapsamı (thread-local): renk körü paleti + yazı ölçeği + sade mod.

    Neden `threading.local`: aynı anda iki kare çizilebilir (tarama + gönderim
    işçisi); global mutasyon birinin rengini diğerine sızdırırdı.
    """

    def __init__(self) -> None:
        self.palet: Optional[dict[str, str]] = None
        self.yazi_olcek: float = 1.0
        self.sade: bool = False
        self.mobil: bool = False


_MOD = _ModKapsami()

# Renk körü (deuteranopia) modu: mum/şerit/katılım renkleri mavi-turuncu çiftine
# geçer. Şekil kanalı KORUNUR (yükselen BOŞ, düşen DOLU) — renk körlüğünde tek
# ayrım renk olmasın kuralı (GÖRSEL-3) burada da geçerli.
_PALET_RENK_KORUGU: dict[str, str] = {
    "mum_yukselen": "#4da3ff", "mum_yukselen_ic": "#12395c",
    "mum_dusen": "#f5a05a", "mum_dusen_ic": "#f5a05a",
    "serit_yuk": "#3f8fd0", "serit_dus": "#d98b4a",
    "son_yuk": "#4da3ff", "son_dus": "#f5a05a",
}


def _mod_kapsami(secenekler: Optional[Mapping[str, Any]] = None):
    """`with _mod_kapsami(secenekler):` — modları ayarlar, çıkışta temizler."""
    import contextlib

    @contextlib.contextmanager
    def _kapsam():
        onceki = (_MOD.palet, _MOD.yazi_olcek, _MOD.sade, _MOD.mobil)
        sec = dict(secenekler or {})
        _MOD.palet = dict(_PALET_RENK_KORUGU) if sec.get("renk_korugu") else None
        try:
            olcek = float(sec.get("yazi_olcek") or 1.0)
        except (TypeError, ValueError):
            olcek = 1.0
        _MOD.yazi_olcek = min(2.0, max(1.0, olcek))
        _MOD.sade = bool(sec.get("sade"))
        _MOD.mobil = bool(sec.get("mobil"))
        try:
            yield
        finally:
            _MOD.palet, _MOD.yazi_olcek, _MOD.sade, _MOD.mobil = onceki

    return _kapsam()


class _PaletSarmalayici(Mapping):
    """`PALET[...]` okumalarını mod kapsamına göre yönlendirir (çağrı yeri değişmez)."""

    def __init__(self, taban: dict[str, Any]) -> None:
        self._taban = taban

    def _birlesik(self) -> dict[str, Any]:
        if not _MOD.palet:
            return self._taban
        return {**self._taban, **_MOD.palet}

    def __getitem__(self, anahtar: str) -> Any:
        aktif = _MOD.palet
        if aktif and anahtar in aktif:
            return aktif[anahtar]
        return self._taban[anahtar]

    def get(self, anahtar: str, varsayilan: Any = None) -> Any:
        try:
            return self[anahtar]
        except KeyError:
            return varsayilan

    def __iter__(self):
        return iter(self._birlesik())

    def __len__(self) -> int:
        return len(self._birlesik())


class _SabitlerSarmalayici(Mapping):
    """`SABITLER[...]` + `--buyuk-yazi` ölçeği (`*_pt` anahtarları).

    Ölçek yalnız yazı puntolarına uygulanır; dpi/kalınlık/kadraj gibi ölçülere
    dokunulmaz (kare geometrisi değişmez, yalnız metin büyür).
    """

    _OLCEKLI_SONEK = "_pt"

    def __init__(self, taban: dict[str, Any]) -> None:
        self._taban = taban

    def __getitem__(self, anahtar: str) -> Any:
        deger = self._taban[anahtar]
        if _MOD.mobil and anahtar == "sag_serit_px":
            return 210.0
        olcek = _MOD.yazi_olcek
        if (olcek != 1.0 and isinstance(anahtar, str)
                and anahtar.endswith(self._OLCEKLI_SONEK)
                and isinstance(deger, (int, float)) and not isinstance(deger, bool)):
            return float(deger) * olcek
        return deger

    def get(self, anahtar: str, varsayilan: Any = None) -> Any:
        try:
            return self[anahtar]
        except KeyError:
            return varsayilan

    def __iter__(self):
        return iter(self._taban)

    def __len__(self) -> int:
        return len(self._taban)


SABITLER_TABAN: dict[str, Any] = {
    # kare ölçüleri (§17.1-2: bar_px 4→6, tavan 2160→1440; §0.12q oran 4:3)
    "genislik_taban": 1080,
    "yukseklik": 810,
    "bar_px": 6,
    "genislik_tavan": 1440,
    "mum_min_px": 5.0,        # px/bar altına düşerse → çizgi + alan (§17.14)
    "dpi": 100,
    # kadraj (FAZ 2 / kullanıcı planı 2026-10-15): TF matrisi — formasyon YOKKEN
    # gösterilecek MUM sayısı. 1g 62 (makro trend), 4s 68, 2s 74, 1s 80 (düşük
    # zaman dilimi gürültüsünü engeller, iç yapıyı netleştirir).
    "kare_mum": 80,
    "kare_once_pay": 10,          # FAZ 2: formasyon öncesi 10 mum sol tampon
    "kadraj_cerceve": {"1h": 80, "2h": 74, "4h": 68, "1d": 62},
    "kadraj_formasyon_min": 35,   # FAZ 2 Kural A alt sınırı
    # 2026-10-23 (kullanıcı: "çizimi kısa tutuyor, formasyonun neresinden
    # kırıldığı görünmüyor"): üst sınır 85 → 180. 85 mum, 90-100 barlık bir
    # formasyonun ilk üçte birini kareden atıyordu; kırılımın geldiği taban ve
    # daralmanın boyu görünmüyordu. Gerçek tavan piksel bütçesidir
    # (`genislik_tavan / bar_px` = 240 mum, bar başına 6 px); 180 mumda kare
    # 1080 px genişlikte kalır ve px/bar 6'nın altına inmez.
    "kadraj_formasyon_maks": 180,
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
    # FAZ 1 (kullanıcı planı): geliştirici metinleri (lejant, `bölge: …`,
    # `veri: N bar hacimsiz`) ve alt hacim paneli KAREDEN çıkarıldı. Bu bilgiler
    # `meta["metin"]`den Telegram metin kartının altına dipnot olarak gider
    # (`notifier._grafik_basligi`). Kazanılan dikey alan mumlara kalır.
    "lejant": True,                   # metin listesi meta'da üretilir (çizim: kare_lejant)
    "kare_lejant": False,             # kare içine lejant çizilsin mi (eski görünüm)
    "hacim_paneli": False,            # alt hacim kulvarı çizilsin mi (eski görünüm)
    "rvol_rozet_esik": 2.0,           # ⚡↑ rozeti: RVOL bu eşiğin ÜSTÜNDEYSE mum altına
    # 2026-10-16 (kullanıcı): rozet artık İKİ YÖNLÜ. `⚡↑ x2,5` hacim patlaması,
    # `⚡↓ x0,5` hacim kuruması. Yön oku metnin kendisinde (renk tek kanal değil).
    "rvol_rozet_esik_dusuk": 0.5,     # ⚡↓ rozeti: RVOL bu eşiğin ALTINDA veya EŞİTSE
    # Kullanıcı (2026-10-16): "çok fazla etiket olmamalı, en fazla 2 tane
    # ekleyebiliriz". Kuruma rozeti kare başına 2'yi geçmez (ölçüm: sakin 4s
    # karesinde ↓7'ye kadar çıkıp kare rozet kalabalığına dönüyordu); en sert
    # iki kuruma seçilir. Patlamalar kalan yeri doldurur (`rvol_rozet_maks`).
    "rvol_rozet_dusus_maks": 2,
    # Toplam tavan 8 → 6 (kullanıcı, 2026-10-16: "yine 3-6 kalsın"). Tazelik
    # garantisi bir rozet daha ekleyebildiği için ölçülen üst sınır 7'ye çıkmıştı
    # (AKBNK 4s 120 mum); tavan 6 ile kare başına rozet 3-6 aralığında kalır.
    "rvol_rozet_maks": 6,
    "rvol_rozet_ara": 7,              # iki rozet arasında en az bar (üst üste binmesin)
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
    "mum_genislik_orani": 0.62,       # gövde genişliği, bar aralığının oranı (veri birimi)
    "fitil_pt": 0.85,
    "govde_kenar_pt": 0.7,
    "isaret_boyut": 5.4,
    "cizgi_kalinlik": {"formasyon": 2.0, "alarm_kritik": 2.2, "alarm_normal": 1.1,
                       "projeksiyon": 1.1, "grid": 0.7, "hedef": 1.2,
                       # Direk bant çizgisinden BELİRGİN kalın: impuls bacağı tek
                       # bakışta "dik hareket" okunmalı (kullanıcı: "direk gözükmüyor").
                       "direk": 3.4},
    # GÖRSEL-6 (kullanıcı: "OB/FVG renkleri tam belirgin değil, şeffaflığını biraz
    # azalt, ama çok abartma"): dolgu %9/%8 → %16/%15 (≈1,8×). Neon DEĞİL: kutu
    # dolgusu hâlâ yarı saydam, mum okunurluğu korunur; kalın/ince kutu kademesi
    # (`ince`) ve pasif yarıya inme kuralı aynen sürer.
    # GÖRSEL-8 (kullanıcı): "OB'nin koyu tarafı doldurulmuş taraf oluyor, açık
    # renkli taraf doldurulmamış taraf — tam tersi olmasını istiyorum." Ton yönü
    # döndü: KUTU (doldurulmamış kalan alan) KOYU, DOLAN KISIM AÇIK.
    # `dolan_orani`: dolan bandın alfası = kutu alfası × oran (taban `dolan_taban`).
    # Kullanıcı: "arttır biraz görünsün ama soluk olsun dolmayana göre" → oran 0,50
    # (dolan bant = kalan alanın YARISI: görünür ama belirgin şekilde soluk).
    # FAZ 3 §2 (kullanıcı paleti): TAZE OB dolgusu canlı (0,25), KISMEN DOLMUŞ OB'de
    # kalan açık alan 0,12'ye iner ve DOLAN bant mat griye döner (0,08) — "neresi
    # tüketildi, neresi hâlâ canlı" tek bakışta ayrılır. FVG doluluk hesabı yapmaz:
    # tek ton (0,15) turkuaz/mor, kesikli ince kontur.
    "doldurma": {"golge_esik_orani": 0.18, "golge": 0.07, "golge_ince": 0.04,
                 "ob": 0.16, "fvg": 0.15, "eng": 0.0, "ince": 0.07,
                 "ob_taze": 0.25, "ob_kalan": 0.12, "ob_dolan": 0.08,
                 "kapanan": 0.02,      # tamamlanmış/geçersiz kutu: yalnız silik iz
                 "dolan_orani": 0.50, "dolan_taban": 0.03},
    # GÖRSEL-4: 2,0 pt kalın vurgu "havada çubuk" gibiydi → 1,3. GÖRSEL-6: kenar
    # 0,8 → 0,9 (kutu sınırı bir tık daha belirgin; vurgu çubuğu değişmedi).
    "zone_kalinlik": {"kenar": 0.9, "vurgu": 1.3},
    "zone_yazi_pt": 8.0,        # kutu etiketi (kutunun İÇİNDE, GÖRSEL-4)
    "olay_yazi_pt": 8.0,        # BOS/CHoCH etiketi (mumun yanında, GÖRSEL-4)
    # yazı bütçesi (§22'de kaydı: kart satır bütçesinin kare ölçeğe çevrilmişi)
    "metin_carpani": 0.82,            # genislik() 16 px tabanlı; kare içi yazı 13,2 px
    "etiket_maks_px": 300.0,          # kare içi etiket tavanı (~%28 kare genişliği)
    # sağ fiyat şeridi (görsel-2/3): eksenin dışında; PANEL zeminli, etiketler çipli
    "sag_serit_px": 158,
    "sag_serit_yazi_pt": 8.5,
    "sag_etiket_adim": 1.75,          # etiket satır yüksekliği çarpanı (çip payı dahil)
    # Çipler arası ASGARİ NEFES PAYI (etiket yüksekliğinin oranı). Eski kural
    # yalnız "üst üste binmesin" diyordu: ayrılık = yarı yükseklikler toplamı
    # olduğundan iki çip birbirine DEĞEBİLİYORDU (kullanıcı: "bazısı çok yakın
    # oluyor" — `alarm 38,52` ile son fiyat `38,46` yapışıyordu). Pay, çip
    # kenarları arasında görünür boşluk bırakır; sığmayan etiket eskisi gibi
    # SAYILARAK düşer (`atlanan_kaynak`), sessiz kayıp olmaz.
    "sag_etiket_bosluk": 0.30,
    "sag_kilavuz": True,              # kutudan şeride ince kılavuz çizgisi (ilişki görünsün)
    # Şerit kalabalık denetimi (GÖRSEL-3): kaynak başına azami etiket. Hepsini
    # dizmek teknik olarak sığıyor ama okunmuyordu (GARAN 1s: 13 etiket).
    # Dış rol cetvelinde dört ayrı seviye olabilir (PH/PL/WH/WL); dördünü de
    # koru, iç swing okları sağ şeridi tüketmez.
    "sag_etiket_maks": {"zone": 3, "olay": 3, "alarm": 1, "swing": 4},
    "kadraj_pay_orani": 0.06,         # yapı seviyesi: candle aralığının bu oranı dışındaysa çizilmez
    # Sağ boşluk: son mumun sağında kalan boş alan. Fiyat etiketleri, seviye
    # çizgileri ve 🎯 hedef kutusu mumların üzerine değil bu alana çizilir; bant
    # çizgileri, OB/FVG kutuları ve aktif BOS/CHoCH hedefi buraya kadar uzar.
    #
    # 2026-10-16 (kullanıcı): boşluk artık EKSEN GENİŞLİĞİNİN YÜZDESİ — hedef
    # %15, kabul penceresi %10-20 (`sag_bosluk_orani_min/maks`). Sabit mum
    # sayısı pencereyi mum sayısına göre kaydırıyordu: 80 mumluk 1s karesinde 15
    # mum %16, 35 mumluk formasyon karesinde ise %30 oluyordu (aşırı boş).
    # Yüzde kuralı her karede aynı görsel oranı verir.
    "sag_bosluk_orani": 0.15,
    "sag_bosluk_orani_min": 0.10,     # aşağı kırpma: etiketler sığsın
    "sag_bosluk_orani_maks": 0.20,    # yukarı kırpma: mumlar daralmasın
    # Yalnız `GRAFIK_SAG_BOSLUK_MUM` verilirse kullanılan sabit mum sayısı ve
    # bozuk değerde düşülen varsayılan.
    "sag_bosluk_mum": 15,
    "sag_bosluk_yuzde": 5.3,          # eski oran yolu: `GRAFIK_SAG_BOSLUK` verilirse

    "ust_ayrac": True,                # başlık bloğunun altında ince ayraç çizgisi
    # FAZ 4 §5: formasyon iç alanı KARARTILMAZ (şeffaf) — yalnız üst/alt sınır
    # çizgileri belirgin (2,0 pt). Eski 0,06'lık bant dolgusu koyu zeminde leke
    # gibi duruyordu ve mum okunurluğunu düşürüyordu.
    "formasyon_dolgu_alpha": 0.03,
    # FAZ 3 §A: OB doluluk eşikleri + FAZ 4 §4 hedef (ölçülü hareket) projeksiyonu
    "ob_taze_esik": 0.02,             # bu oranın altı "taze" (fresh) OB sayılır
    "hedef_aktif": True,              # teyitli alarmda 🎯 hedef projeksiyonu çizilsin mi
    "swing_etiket_ofset_px": 11.0,    # FAZ 4 §6: HH/HL/LH/LL fitile 10-15 px uzak
}
SABITLER = _SabitlerSarmalayici(SABITLER_TABAN)

# §0.4.1 kalıcı palet — renk tek başına bilgi taşımaz, her katmanın yazısı da var.
#
# GÖRSEL-3 (2026-10-14): yükselen mum YEŞİL, düşen mum KIRMIZI. Neon yok: iki ton
# da orta doygunlukta (teal-yeşil / tuğla kırmızı), zemin koyu slate. Bilgi ikinci
# kanaldan da taşınır: yükselen içi BOŞ (saydam yeşil dolgu), düşen DOLU — renk
# körlüğünde de okunur (§0.4.1 kuralı: "renk tek başına bilgi taşımaz").
PALET_TABAN = {
    # zemin / panel: mum alanı ile şerit kulvarları birbirinden ayrılsın
    "zemin": "#0f151c",
    "panel": "#151d27",
    "panel_kenar": "#243040",
    "metin": "#e9eef5",
    "eksen": "#93a1b1",
    "grid": "#212c39",
    "grid_vurgu": "#2f3d4d",
    # mumlar: yükselen = yeşil (içi boş, saydam yeşil dolgu) · düşen = kırmızı (dolu)
    "mum_yukselen": "#31b184",
    "mum_yukselen_ic": "#134237",
    "mum_dusen": "#e05c58",
    # bölgeler (mumların ardında; §0.4.1 renkleri korunur, ton koyu zemine çekildi)
    "ob": "#2bb673",
    "fvg": "#3f9dec",
    "engulf": "#a78bfa",
    # FAZ 3 §2 paleti: OB boğa/ayı ve FVG boğa/ayı AYRI renk grupları — OB (yeşil/
    # kırmızı) ile FVG (turkuaz/mor) karışmaz; ayrım yalnız renkle değil, kontur
    # stiliyle de taşınır (OB düz, FVG kesikli).
    "ob_bull": "#10B981",     # Zümrüt yeşili
    "ob_bear": "#EF4444",     # Mercan kırmızısı
    "fvg_bull": "#06B6D4",    # Turkuaz
    "fvg_bear": "#8B5CF6",    # Mor
    "dolan": "#9CA3AF",       # Mat gri: dolan/tüketilen alan
    "hedef": "#22d3ee",       # 🎯 hedef kutusu (projeksiyon)
    # formasyon bandı: sıcak kum/amber — mum ve yapı katmanlarından ayrışır
    "formasyon": "#e0b96a",
    "formasyon_dolgu": "#e0b96a",
    # Direk (pole): bant renginden AYRI okunması gerekir — bant çizgisiyle aynı
    # renkte olsa "çizginin kalınlaşmış hali" gibi görünür, impuls bacağı
    # kaybolurdu. Turuncu-amber: bant (kum sarısı) ve mumlardan ayrışır.
    "direk": "#ff9d3c",
    "direk_dolgu": "#ff9d3c",
    "temas": "#f0d9a8",
    "swing": "#8ba0b4",
    "sinif": "#9fb0c0",
    "olay": "#f0885c",
    "serit_yuk": "#2f9e8a",
    "serit_dus": "#cf5f5f",
    "serit": "#7fb3ac",
    "ihlal": "#ef5350",
    "alarm": "#a9b6c4",
    "golge": "#8fa8c8",
    "chip_zemin": "#111922",
}
PALET = _PaletSarmalayici(PALET_TABAN)

# Alarm çizgisinin kalınlığı durumundan gelir (§2.6): halka açık durumlar kalın.
# §0.12l: `1s` ve `2s` karelerinde FVG çizilmez — `zone_scoring.FVG_TIMEFRAMES`
# {2h,4h,1d} + `enable_2h_fvg=False`: canlı yolda `2s`de de FVG üretilmiyor.
_FVG_YOK_TFLAR = frozenset({"1h", "2h"})

# Kutu çizgisi/dolgusu motor durum ADINDAN gelir; enum numarasına bağlanmaz.
# Tamamlanan lifecycle kayıtları soluk/kesik, adaylar noktalı; aktif kayıtlar
# belirgin kalır. `PARTIAL_*` ve `WEAKENED` aktif lifecycle aşamalarıdır.
_BOLGE_DOLU = frozenset({"ACTIVE", "FIRST_TEST", "PARTIAL_FILL", "DEEP_TEST",
                         "FAILED_REACTION", "PARTIAL_RETRACE", "WEAKENED"})
_BOLGE_ARA = frozenset({"CANDIDATE"})
_BOLGE_TAMAM = frozenset({"FULL_FILL", "REACTION", "INVALID", "SUPERSEDED",
                          "CONTINUATION_CONFIRMED", "EXPIRED"})

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


def _ortam_bayrak(ad: str, varsayilan: bool = False) -> bool:
    """`GRAFIK_*` bayrağı: 1/true/evet/açık → True; boş/tanımsız → varsayılan."""
    ham = str(os.environ.get(ad, "")).strip().lower()
    if not ham:
        return bool(varsayilan)
    return ham in ("1", "true", "evet", "açık", "acik", "yes", "on")


def sag_bosluk_mum(n: int) -> int:
    """Son mumun sağındaki BOŞ alan, bar sayısı olarak; 0 = kapalı, eski görünüm.

    Kural (2026-10-16, kullanıcı kararı): boşluk **eksen genişliğinin yüzdesidir**.
    Hedef %15, kabul penceresi %10-20 (`sag_bosluk_orani_min/maks`). Her karede aynı
    görsel oran çıkar: 80 mumluk 1s karesinde ≈14 mum, 35 mumluk formasyon karesinde
    ≈6 mum. (Eski sabit "15 mum" kuralı formasyon karesinde %30'a çıkıyordu.)

    Fiyat etiketleri, seviye çizgileri, 🎯 hedef kutusu ve aktif kırılım çizgileri
    mumların üzerine değil bu alana çizilir.

    Öncelik sırası (hepsi ortam değişkeniyle, açıkça verilirse):
      1. `GRAFIK_SAG_BOSLUK_MUM`  → sabit mum sayısı (0 → eski görünüm)
      2. `GRAFIK_SAG_BOSLUK`      → eski oran yolu (eksen yüzdesi, kırpılmaz)
      3. `GRAFIK_SAG_BOSLUK_ORANI`→ yeni yüzde kuralı (açıkça verilirse kırpılmaz)
      4. varsayılan               → %15, [%10, %20] penceresine kırpılır

    Eksen `n + 0,2 + g` bar genişliğindedir (xlim −0,6 … n−0,4+g); oran `g / (n + 0,2 + g)`.
    Bozuk/uç değer asla çizimi engellemez: NaN varsayılana, fazlası en yakın sınıra düşer.
    """
    if int(n) <= 0:
        return 0
    if "GRAFIK_SAG_BOSLUK_MUM" in os.environ:
        adet = _ortam_sayi("GRAFIK_SAG_BOSLUK_MUM", float(SABITLER["sag_bosluk_mum"]))
        if not math.isfinite(adet):
            adet = float(SABITLER["sag_bosluk_mum"])
        return max(0, min(40, int(round(adet))))
    if (os.environ.get("GRAFIK_SAG_BOSLUK") or "").strip():
        yuzde = _ortam_sayi("GRAFIK_SAG_BOSLUK", float(SABITLER["sag_bosluk_yuzde"]))
        if not math.isfinite(yuzde):
            yuzde = float(SABITLER["sag_bosluk_yuzde"])
        pay = max(0.0, min(15.0, yuzde)) / 100.0
        if pay <= 0.0:
            return 0
        return max(1, int(round(pay * (int(n) + 0.2) / (1.0 - pay))))
    # Yeni varsayılan yol: eksen yüzdesi, %10-20 penceresine kırpılır.
    acik = "GRAFIK_SAG_BOSLUK_ORANI" in os.environ
    oran = _ortam_sayi("GRAFIK_SAG_BOSLUK_ORANI", float(SABITLER["sag_bosluk_orani"]))
    if not math.isfinite(oran):
        oran = float(SABITLER["sag_bosluk_orani"])
        acik = False
    if not acik:                                   # yalnız otomatik kuralda kırp
        oran = min(max(oran, float(SABITLER["sag_bosluk_orani_min"])),
                   float(SABITLER["sag_bosluk_orani_maks"]))
    oran = max(0.0, min(0.80, oran))
    if oran <= 0.0:
        return 0
    return max(1, int(round(oran * (int(n) + 0.2) / (1.0 - oran))))


def kare_mum_tavani(tf: str) -> int:
    """Formasyon YOKKEN gösterilecek mum sayısı (FAZ 2 TF matrisi; `GRAFIK_MUM_MAKS`)."""
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


def _alan_var(nesne: Any, ad: str) -> bool:
    """Alan yokluğu ile değeri `None` olan lifecycle alanını ayır."""
    return ad in nesne if isinstance(nesne, Mapping) else hasattr(nesne, ad)


def _kayit_listesi(deger: Any) -> list[Any]:
    """Tek lifecycle kaydı, tuple/list ve `None` girdilerini tek biçime getir."""
    if deger is None:
        return []
    if isinstance(deger, (list, tuple)):
        return list(deger)
    return [deger]


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
        except Exception:  # noqa: S110 - bilinçli düşüş: notifier biçimi değişirse manuel biçime geçilir / pragma: no cover
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
              once_pay: Optional[int] = None,
              tf: Optional[str] = None) -> tuple[int, int, bool]:
    """(sol, sag, kirpildi) — FAZ 2 akıllı kadraj (viewpoint zoom) kuralı.

    Kural A (formasyon VARSA): kadraj formasyona odaklanır —
    `formasyon mumu + 10 mum sol tampon`. Pencere, formasyonun TAMAMINI
    göstermeye çalışır (kullanıcı 2026-10-23: "çizimi kısa tutuyor, formasyonun
    neresinden kırıldığı görünmüyor"); üst sınır `kadraj_formasyon_maks` (180)
    ve piksel bütçesidir (`genislik_tavan / bar_px` = 240 mum → okunurluk için
    180'de durulur). Kısa formasyonda fark sola eklenir; 180'den uzun formasyonda
    sağ (güncel) taraf gösterilir ve `kirpildi=True` ile `budama`ya yazılır.
    Kural B (formasyon YOKSA): TF matrisi (`kadraj_cerceve`: 1g 62 · 4s 68 ·
    2s 74 · 1s 80) kullanılır.

    Pencere formasyonun ilk mumuna sabitlenir, geriye MS için uzatılmaz (§0.15).
    Dönen `sag` her zaman `n`dir; sağ boşluk eksen sınırında ayrıca eklenir
    (`sag_bosluk_mum`).
    """
    n = max(0, int(n))
    if n <= 0:
        return 0, 0, False
    carsi = max(1, int(kare_mum if kare_mum else kare_mum_tavani(str(tf or "1h"))))
    pay = int(SABITLER["kare_once_pay"] if once_pay is None else once_pay)
    bas = _tam(formasyon_basi)
    if bas is None or bas < 0:
        return max(0, n - carsi), n, False
    # Kural A — formasyon odaklı kadraj. Tavan artık 85 DEĞİL: 85 mum, 90-100
    # barlık bir üçgenin ilk bölümünü (dolayısıyla kırılımın geldiği tabanı ve
    # daralmanın ne kadar olduğunu) kareden atıyordu. Tavan PİKSEL bütçesinden
    # türetilir: `genislik_tavan / bar_px` (1440/6 = 240 mum) ve okunurluk için
    # 240'ın altında tutulur; `kadraj_formasyon_maks` bu tavanı aşağı çeker.
    # Çağıran AÇIKÇA bir pencere verdiyse (`--mum`) o daha dar olabilir, geçmez.
    alt = int(SABITLER["kadraj_formasyon_min"])
    maks = int(SABITLER["kadraj_formasyon_maks"])
    try:
        _bar_px = max(1.0, float(SABITLER["bar_px"]))
        _piksel = int(float(SABITLER["genislik_tavan"]) / _bar_px)
        maks = max(alt, min(maks, _piksel))
    except (TypeError, ValueError):      # pragma: no cover - sabit bozulursa kırpma
        pass
    if kare_mum:
        maks = max(alt, min(maks, int(kare_mum)))
    istenen = max(1, n - int(bas)) + pay
    toplam = max(2, max(alt, min(maks, istenen)))
    sol = max(0, min(int(bas) - pay, n - toplam))
    kirpildi = False
    if n - sol > toplam:                        # formasyon tavandan uzun: sağı göster
        sol = max(0, n - toplam)
        kirpildi = True
    return sol, n, kirpildi


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
           gap: Optional[float] = None, *, kayit_kaynagi: Optional[str] = None,
           tamamlandi: bool = False,
           mitigated: Optional[float] = None) -> Optional[dict[str, Any]]:
    """Tek bir bölge kaydı (§1): motorun verdiği sınırlar, uydurma yok.

    FAZ 3 §A: OB kayıtlarına `mitigated_percentage` (temas/doluluk oranı, **yüzde**)
    eklenir — kutunun hangi yüzdesi tükendi, hangi kısmı canlı kaldı? Oran, motorun
    kendi `fill_boundary`'sinden hesaplanır (`OrderBlockRecord.fill_ratio` formülü,
    bkz. `domain_engines/order_block/order_block_engine.py`); uydurma geometri yok.
    """
    if alt is None or ust is None:
        return None
    if alt > ust:
        alt, ust = ust, alt
    if doluluk is not None:
        doluluk = max(0.0, min(1.0, float(doluluk)))
    if mitigated is not None:
        mitigated = round(max(0.0, min(100.0, float(mitigated))), 1)
    return {"tip": tip, "yon": 1 if yon >= 0 else -1, "alt": float(alt), "ust": float(ust),
            "kaynak": kaynak, "durum": durum, "skor": skor, "doluluk": doluluk,
            "mitigated_percentage": mitigated,
            "zaman": _tarih(zaman).isoformat() if _tarih(zaman) else None, "gap": gap,
            "kayit_kaynagi": kayit_kaynagi, "tamamlandi": bool(tamamlandi)}


def _yon(deger: Any, varsayilan: int = 0) -> int:
    """Yön: `Direction`/`FvgDirection` (IntEnum) veya sayı → +1 / -1 / bilinmiyor.

    Motor enum nesnesi verebilir; `.value` okunur. `NONE`/bozuk yönü bullish
    saymak yerine 0 döndürerek yanlış tarafa kutu uydurmayı önler.
    """
    deger = getattr(deger, "value", deger)
    try:
        sayi = int(deger)
        return -1 if sayi < 0 else (1 if sayi > 0 else 0)
    except (TypeError, ValueError):
        return -1 if varsayilan < 0 else (1 if varsayilan > 0 else 0)


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


def _ob_mitigated(kayit: Any, alt: Optional[float], ust: Optional[float]) -> Optional[float]:
    """OB'nin TÜKETİLME yüzdesi (0-100): motorun `fill_boundary`'sinden (FAZ 3 §A).

    `OrderBlockRecord.fill_ratio` ile birebir aynı formül: boğa kutusunda üstten
    aşağı inen temas, ayı kutusunda alttan yukarı çıkan temas oranı. Alanlar
    yoksa/bozuksa `None` döner ve kutu tek parça çizilir (uydurma oran yazılmaz).
    """
    if alt is None or ust is None:
        return None
    try:
        yuk = float(ust) - float(alt)
        if yuk <= 0:
            return None
        sinir = _gercek(_alan(kayit, "fill_boundary"))
        if sinir is None:
            return None
        bullish = bool(_alan(kayit, "bullish"))
        oran = ((float(ust) - float(sinir)) / yuk if bullish
                else (float(sinir) - float(alt)) / yuk)
    except Exception:
        return None
    return max(0.0, min(100.0, oran * 100.0))


def _zone_renk(b: Mapping[str, Any]) -> str:
    """Kutunun rengi TİP + YÖN'den (FAZ 3 §2 paleti).

    OB boğa zümrüt yeşili / ayı mercan kırmızısı; FVG boğa turkuaz / ayı mor.
    FVG ile OB aynı renk grubunda görünmez; ayrım kontur stiliyle de taşınır.
    """
    tip = str(b.get("tip") or "")
    yon = int(b.get("yon") or 1)
    if tip == "ob":
        return PALET["ob_bull"] if yon >= 0 else PALET["ob_bear"]
    if tip == "fvg":
        return PALET["fvg_bull"] if yon >= 0 else PALET["fvg_bear"]
    return PALET["engulf"]


def _zone_kalan_orani(yon: int, dol: Optional[float]) -> Optional[float]:
    """Kutunun CANLI (dolmamış) oranı: doluluk (0-1) → kalan (1-0).

    `None` → doluluk bilinmiyor; kutu "taze" kabul edilir (yüzde yazılmaz).
    """
    if dol is None:
        return None
    return max(0.0, min(1.0, 1.0 - float(dol)))


def _zone_durum_onceligi(bolge: Mapping[str, Any]) -> int:
    """Aktif alanı adaydan, adayı da tamamlanmış tarihçeden önce tut."""
    if bolge.get("tamamlandi"):
        return 2
    durum = str(bolge.get("durum") or "").upper()
    if durum in _BOLGE_TAMAM:
        return 2
    if durum == "CANDIDATE":
        return 1
    return 0


def _zone_havuzu(sonuclar: Optional[Mapping[str, Any]], tf: str, son_kapanis: Optional[float],
                 sol: int, sag: int, cerceve: Any = None) -> dict[str, Any]:
    """Görsel bölge havuzu: yalnız OB ve FVG lifecycle kayıtları.

    Engulfing motor verisi grafik katmanına hiç alınmaz.
    Lifecycle verisi varsa FVG ham oluşum listesiyle karıştırılmaz. Tamamlanmış lifecycle
    kayıtları zayıf/tarihi çizgiyle tutulur; eski motor şekillerinde raw oluşum
    alanlarına kontrollü fallback yapılır. Motorlara yazılmaz.
    """
    havuz: list[dict[str, Any]] = []
    hata: list[str] = []
    cikarim: dict[str, Any] = {
        "ob": 0, "fvg": 0, "eng": 0,
        "ob_source": "yok", "fvg_source": "yok", "eng_source": "yok",
        "ob_active": 0, "fvg_active": 0, "fvg_completed": 0,
        "eng_active": 0, "eng_completed": 0,
        "fvg_raw": 0, "eng_raw": 0, "duplicates_removed": 0,
    }
    if not sonuclar:
        return {}
    atr = _wilder_atr(cerceve)

    ob = sonuclar.get("order_block") if isinstance(sonuclar, Mapping) else _alan(sonuclar, "order_block")
    if ob is not None:
        try:
            detay = _alan(ob, "details", {}) or {}
            if _alan_var(detay, "active_records"):
                kayitlar = _kayit_listesi(_alan(detay, "active_records"))
                ob_kayit_kaynagi = "active_records"
            else:
                # Eski/harici sonuç şekli için uyumluluk fallback'i.
                kayitlar = _kayit_listesi(_alan(detay, "records", []))
                ob_kayit_kaynagi = "records_legacy"
            cikarim["ob"] = cikarim["ob_active"] = len(kayitlar)
            cikarim["ob_source"] = ob_kayit_kaynagi
            export = _alan(ob, "export")
            dolular: dict[int, Optional[float]] = {}
            for taraf in ("bull", "bear"):
                yan = _alan(export, taraf) if export is not None else None
                kaynak = _tam(_alan(yan, "source_bar"))
                if kaynak is not None:
                    dolular[kaynak] = _gercek(_alan(yan, "fill"))
            for kayit in kayitlar:
                kaynak = _tam(_alan(kayit, "source_index"))
                alt_k, ust_k = _gercek(_alan(kayit, "bottom")), _gercek(_alan(kayit, "top"))
                # FAZ 3 §A: `mitigated_percentage` motoun kendi sınırından
                # (`fill_boundary`) hesaplanır — kayıt yalnız export'tan gelen
                # `fill` oranını taşıyorsa o kullanılır, yoksa alan boş kalır.
                _export_fill = dolular.get(kaynak) if kaynak is not None else None
                if _export_fill is not None:
                    mit = max(0.0, min(100.0, float(_export_fill) * 100.0))
                else:
                    mit = _ob_mitigated(kayit, alt_k, ust_k)
                bolge = _bolge("ob", 1 if _alan(kayit, "bullish") else -1,
                               alt_k, ust_k,
                               kaynak, skor=_gercek(_alan(kayit, "base_score")),
                               doluluk=(mit / 100.0 if mit is not None else None),
                               mitigated=mit,
                               zaman=_alan(kayit, "source_time"),
                               kayit_kaynagi=ob_kayit_kaynagi)
                if bolge:
                    havuz.append(bolge)
        except Exception as h:
            log.warning("grafik: OB bölgeleri okunamadı (%s)", h)
            hata.append("ob")

    fvg = sonuclar.get("fvg") if isinstance(sonuclar, Mapping) else _alan(sonuclar, "fvg")
    if fvg is not None and str(tf) not in _FVG_YOK_TFLAR:
        try:
            detay = _alan(fvg, "details", {}) or {}
            raw_fvg = _kayit_listesi(_alan(detay, "fvg_formations", []))
            fvg_keys = ("active_bullish_fvg", "active_bearish_fvg", "completed_fvg")
            fvg_lifecycle = any(_alan_var(detay, key) for key in fvg_keys)

            def oran(kayit: Any, alanlar: Sequence[str]) -> Optional[float]:
                for alan in alanlar:
                    deger = _gercek(_alan(kayit, alan))
                    if deger is not None:
                        return deger
                return None

            fvg_kayitlari: list[tuple[Any, bool, str]] = []
            if fvg_lifecycle:
                fvg_active: list[Any] = []
                for key in fvg_keys[:2]:
                    fvg_active.extend(_kayit_listesi(_alan(detay, key)))
                fvg_completed = _kayit_listesi(_alan(detay, "completed_fvg"))
                cikarim["fvg_active"] = len(fvg_active)
                cikarim["fvg_completed"] = len(fvg_completed)
                fvg_kayitlari.extend((kayit, False, "active_lifecycle") for kayit in fvg_active)
                fvg_kayitlari.extend((kayit, True, "completed_lifecycle") for kayit in fvg_completed)
                cikarim["fvg_source"] = "lifecycle"
            else:
                cikarim["fvg_raw"] = len(raw_fvg)
                fvg_kayitlari.extend((kayit, False, "raw_formation") for kayit in raw_fvg)
                cikarim["fvg_source"] = "raw_fallback"
            cikarim["fvg"] = len(fvg_kayitlari)
            for kayit, tamamlandi, kayit_kaynagi in fvg_kayitlari:
                yon = _yon(_alan(kayit, "direction"))
                if yon == 0:
                    continue
                bolge = _bolge("fvg", yon,
                               _gercek(_alan(kayit, "lower_boundary")),
                               _gercek(_alan(kayit, "upper_boundary")),
                               _tam(_alan(kayit, "formation_index")),
                               durum=_durum_adi(_alan(kayit, "state")),
                               skor=_gercek(_alan(kayit, "quality")),
                               # FvgFormation.close_fill_ratio tek başına doluluk
                               # değildir; lifecycle maximum_fill_ratio önceliklidir.
                               doluluk=oran(kayit, ("maximum_fill_ratio", "wick_fill_ratio",
                                                   "close_fill_ratio")),
                               zaman=_alan(kayit, "formation_time"),
                               gap=_gercek(_alan(kayit, "gap_size")),
                               kayit_kaynagi=kayit_kaynagi, tamamlandi=tamamlandi)
                if bolge:
                    havuz.append(bolge)

        except Exception as h:
            log.warning("grafik: FVG bölgeleri okunamadı (%s)", h)
            hata.append("fvg")
    elif fvg is not None:
        # §0.12l: 1s/2s karesinde FVG katmanı çizilmez (motor da üretmiyor).
        cikarim["fvg_tf_yok"] = 1

    # Aynı motor kaydının/geometry'nin iki kez aktarılması mükerrer kutu üretmesin.
    benzersiz: dict[tuple[Any, ...], dict[str, Any]] = {}
    for bolge in havuz:
        kimlik = (bolge["tip"], bolge["yon"], round(bolge["alt"], 8),
                  round(bolge["ust"], 8), bolge["kaynak"])
        onceki = benzersiz.get(kimlik)
        if onceki is None:
            benzersiz[kimlik] = bolge
            continue
        cikarim["duplicates_removed"] += 1
        if _zone_durum_onceligi(bolge) < _zone_durum_onceligi(onceki):
            benzersiz[kimlik] = bolge
    havuz = list(benzersiz.values())

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
    # Önce aktif, sonra aday, en son tamamlanmış/tarihi kayıt; her grupta en
    # yakın kutu ve eşitlikte daha yeni `kaynak` kazanır.
    anahtar = (lambda b: (_zone_durum_onceligi(b),
                          b["mesafe_atr"] if b["mesafe_atr"] is not None else b["mesafe"],
                          -(b["kaynak"] if b["kaynak"] is not None else -1)))
    havuz.sort(key=anahtar)
    ust_k, alt_k = _kapak_sayilari(tf)["ust"], _kapak_sayilari(tf)["alt"]
    secilen: list[dict[str, Any]] = []
    # İki slot varsa en yakın aktif FVG için bir görünürlük payı ayır.
    for taraf, kapasite in (("ust", ust_k), ("alt", alt_k)):
        taraf_kayitlari = [b for b in havuz if b["taraf"] == taraf]
        ayrilan: list[dict[str, Any]] = []
        if kapasite >= 2:
            for tip in ("fvg",):
                aday = next((b for b in taraf_kayitlari
                             if b["tip"] == tip and _zone_durum_onceligi(b) < 2), None)
                if aday is not None and aday not in ayrilan:
                    ayrilan.append(aday)
        taraf_secilen = ayrilan[:kapasite]
        for b in taraf_kayitlari:
            if len(taraf_secilen) >= kapasite:
                break
            if b not in taraf_secilen:
                taraf_secilen.append(b)
        secilen.extend(taraf_secilen)
    elenen = max(0, len(havuz) - len(secilen))
    for b in havuz:
        b["vurgu"] = "alt" if int(b["yon"]) >= 0 else "ust"   # §0.12r (kayatta karar)
        b["x0"], b["x1"] = 0, max(0, int(sag) - int(sol) - 1)
        if b["kaynak"] is not None:
            b["x0"] = max(0, min(int(b["kaynak"]) - int(sol), b["x1"]))
    # Çizim/rapor sırası: taraf, sonra yakınlık (meta okunur kalsın)
    secilen.sort(key=lambda b: (b["taraf"], b["mesafe"], int(b["kaynak"] or 0)))
    return {"cizilen": secilen, "tum": havuz, "elenen": elenen,
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
                  etiket_detay: Optional[bool] = None,
                  veri_kaynagi: Optional[str] = None,
                  tarihsel: bool = False) -> dict[str, Any]:
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
    sol, sag, tavan_kalkti = _kadrajla(n, formasyon.get("start_bar"), kare_mum, tf=tf)
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
            f"kadraj: formasyon {yas} barlık → {sag - sol} mumluk pencereye kırpıldı")
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
    for e in ((goruntu["olay"] or {}).get("zaman_cizelgesi", []) +
              (goruntu["olay"] or {}).get("seviyeler", [])):
        idx = e.get("kaynak_bar")
        if not e.get("zaman") and idx is not None and 0 <= idx < len(zamanlar):
            e["zaman"] = zamanlar[idx].isoformat() if zamanlar[idx] else None
    if (goruntu["olay"] or {}).get("hata"):
        goruntu["eksik_katmanlar"] = sorted(set(goruntu["eksik_katmanlar"])
                                            | set(goruntu["olay"]["hata"]))
    # `sonuclar` yoksa bölge/yapı katmanları YOKTUR — bu veri bozukluğu değil
    # (§0.12w: dipnot yalnız veri sorununa); izi `meta["zone"]["sirala"]` ve
    # `meta["olay"]` sıfırlarında taşınır.
    goruntu["guven"] = deneyim.trust_payload(
        goruntu, sonuclar, now=simdi or datetime.now().astimezone(),
        source=veri_kaynagi, historical=tarihsel,
        anchor=zamanlar[0] if zamanlar else None)
    if not n or not sag:
        goruntu["uyarilar"].append("kare boş: çizim yok")
        return goruntu

    # --- kartın yapı satırı (L11): üst blokta gri satır olarak çizilir. Metin
    # `notification_context`ten GELİYOR (kartın kendi biçimleyicisi), burada yeni
    # cümle kurulmuyor → kare ile kart ayrışamaz.
    goruntu["yapı_satırı"] = _yapı_satırı(sonuclar, tf, goruntu.get("son_kapanis"))

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
        goruntu["uyarilar"].append("bant verisi yok: temas adedi hesaplanamadı")
    # Temas noktaları sayı olarak korunur; grafikteki daire işaretleri kaldırıldı.
    goruntu["temas_isaret"] = []
    goruntu["isaretler"] = _isaret_listesi(formasyon, goruntu["kapanis"], goruntu["yuksek"],
                                           sol, sag - sol)

    if goruntu_not:
        goruntu["notlar"].append(goruntu_not)
    goruntu["alarm"] = _alarm_kopyala(cift, alarm_turu, alarm_bar, sol, sag, goruntu)
    if (goruntu["alarm"] or {}).get("bar_disarida"):
        # Alarm mumu kadraj dışında kaldı: çizilmemesi bilgi kaybıdır → bildirilir.
        goruntu["uyarilar"].append("alarm mumu kadraj dışında: mum işaretlenmedi")
    return goruntu


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


_CIZIM_KILIDI = threading.RLock()


def _seri_cizim(fn):
    @wraps(fn)
    def kilitli(*args, **kwargs):
        # pyplot global durumu thread-safe değil: otomatik/manuel çizimler seri.
        with _CIZIM_KILIDI:
            return fn(*args, **kwargs)
    return kilitli


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
    goruntu = deneyim.prepare_view(goruntu, str(secenekler.get("gorunum") or
                                   os.environ.get("GRAFIK_GORUNUM") or "odak"),
                                   max_distance_atr=max(.1, _ortam_sayi("GRAFIK_ODAK_MESAFE_ATR", 3.0)))
    ayrinti = deneyim.detail_payload(kaynak_goruntu, goruntu)
    olcu = _kare_olcu(goruntu)
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
        return _kare_ciz(goruntu, tf, olcu, meta, secenekler,
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
        ham = [float(v) for v in (kapanis + yuksek + dusuk) if v is not None]
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
                zone_ozet = _zone_ciz(ax, zone, n, aralik, sag_adaylar,
                                      kutular=mum_kutulari, sag_bosluk=sag_bosluk,
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
                olay_ozet.update(_olay_ciz(ax, goruntu, n, sag_adaylar,
                                           kutular=mum_kutulari,
                                           sag_bosluk=sag_bosluk) or {})
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
            _mumlar_ciz(ax, acilis, yuksek, dusuk, kapanis, cap, aralik)
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
                meta["cizgiler"]["formasyon"] = _formasyon_ciz(
                    ax, goruntu, n, butce, metin, sag_bosluk=sag_bosluk,
                    aralik=aralik, yuksek=yuksek, dusuk=dusuk)
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
            sag_ozet = _sag_ciz(ax, fig, sag_adaylar, n, aralik,
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
        _metin_ciz(fig, metin, sol_kenar, sag_metin, ust, alt_blok=alt_blok)
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


def _rvol_katı(deger: float) -> str:
    """Rozet katı metni: `x2,5` — 2 basamak yazılır, gereksiz sıfır kırpılır.

    Neden 1 basamak yetmiyor: `x0,96` tek basamakta `x1,0` olurdu, yani hacim
    KURUMASI "normal" görünürdü (yanlış bilgi). 2 basamak + sıfır kırpma hem
    kısa kalır (`x2,5` · `x0,5`) hem de 2,04 gibi eşik üstünü `x2,0` diye
    yazıp eşikle çelişmez.
    """
    tam, _, ondalik = sayi(deger, 2).partition(",")
    while len(ondalik) > 1 and ondalik.endswith("0"):
        ondalik = ondalik[:-1]
    return f"{tam},{ondalik}"


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


def _mum_cakisma_say(fig, ax, acilis, yuksek, dusuk, kapanis, cap: float) -> dict[str, Any]:
    """Ölçüm: hangi yazı hangi mumun gövdesi/fitili ile EKRANDA çakışıyor.

    Neden: "yazı mumun üstüne bindi mi" görsel bir soru; piksel hash'i yerine
    sayı verir. Her yazının görüntü kutusu (`get_window_extent`) ile her mumun
    gövde ve fitil kutusu (`transData`, piksel) karşılaştırılır. Yazılar sağdaki
    fiyat şeridinde (x > n-1) olduğundan doğal olarak çakışmaz; çakışma = kötü yerleşim.
    Ölçüm hata verirse `None` döner ve çizimi etkilemez.
    """
    try:
        import numpy as np
        renderer = fig.canvas.get_renderer()
        n = len(kapanis)
        govde, fitil = [], []
        for i in range(n):
            a, k, y, d = acilis[i], kapanis[i], yuksek[i], dusuk[i]
            if None in (a, k, y, d):
                continue
            govde.append((i - cap / 2.0, min(a, k), i + cap / 2.0, max(a, k)))
            fitil.append((i - 0.25, d, i + 0.25, y))
        def _kutu(liste):
            if not liste:
                return np.zeros((0, 4))
            arr = np.array(liste, dtype=float)
            p0 = ax.transData.transform(arr[:, 0:2])
            p1 = ax.transData.transform(arr[:, 2:4])
            return np.hstack([np.minimum(p0, p1), np.maximum(p0, p1)])
        gk, fk = _kutu(govde), _kutu(fitil)
        yazilar = [t for t in ax.texts if t.get_visible() and str(t.get_text()).strip()]
        # GÖRSEL-4: kutu içi (`kutu-ici`) ve olay etiketi (`olay-ici`) BİLİNÇLİ olarak
        # veri alanında durur (kullanıcı kararı: "dikdörtgenin içine yaz"). Kapı yine
        # de şerit/başlık yazıları için katı kalır; katman yazıları ayrı sayılır ve
        # `meta["kalite"]["katman_cakisan"]` ile görünür olur.
        cakisan: list[str] = []
        katman_cakisan: list[str] = []
        for t in yazilar:
            bb = t.get_window_extent(renderer)
            if bb.width <= 0 or bb.height <= 0:
                continue
            m = 1.0
            hit = False
            for kk in (gk, fk):
                if len(kk) == 0:
                    continue
                ort = ((kk[:, 0] <= bb.x1 + m) & (kk[:, 2] >= bb.x0 - m)
                       & (kk[:, 1] <= bb.y1 + m) & (kk[:, 3] >= bb.y0 - m))
                if bool(ort.any()):
                    hit = True
                    break
            if not hit:
                continue
            if str(t.get_gid() or "").endswith("-ici"):
                katman_cakisan.append(str(t.get_text())[:16])
            else:
                cakisan.append(str(t.get_text())[:16])
        return {"yazi": len(yazilar), "mum_cakisan": len(cakisan), "cakisan": cakisan[:8],
                "katman_yazi": sum(1 for t in yazilar
                                   if str(t.get_gid() or "").endswith("-ici")),
                "katman_cakisan": katman_cakisan[:8]}
    except Exception as hata:  # pragma: no cover - ölçüm çizimi bozmaz
        log.debug("grafik: çakışma ölçümü atlandı (%s)", hata)
        return None


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


def _grafik_yapi_metni(metin: str) -> str:
    """Remove internal scope wording from new AND previously saved chart headers."""
    baslik, ayrac, govde = str(metin or "").partition(": ")
    if not ayrac:
        govde, baslik = baslik, ""
    parcalar = [p.strip() for p in govde.split(" · ")]
    def ic(parca):
        return parca.lower() in ("iç", "internal") or parca.lower().startswith(("iç ", "internal "))
    if not ayrac and any(ic(p) for p in parcalar) and not any("dış" in p for p in parcalar):
        return ""  # an internal-only event is not an external chart headline
    parcalar = [p.replace("dış+iç", "dış") for p in parcalar if not ic(p)]
    return (baslik + ": " if baslik and parcalar else "") + " · ".join(parcalar)


def _grafik_dis_yapi(olay: Mapping[str, Any]) -> dict[str, Any]:
    if not olay:
        return {}
    dis_olaylar = [b for b in (olay.get("olaylar") or [])
                   if str(b.get("scope") or b.get("kapsam") or "EXTERNAL").upper() != "INTERNAL"]
    dis_seviyeler = [e for e in olay.get("seviyeler", [])
                     if str(e.get("scope") or "EXTERNAL").upper() == "EXTERNAL"]
    kritik = olay.get("kritik") or {}
    if str(kritik.get("scope") or kritik.get("kapsam") or "EXTERNAL").upper() == "INTERNAL":
        kritik = None
    return {**olay, "swinglar": [], "olaylar": dis_olaylar, "kritik": kritik,
            "seviyeler": dis_seviyeler,
            "zaman_cizelgesi": [e for e in olay.get("zaman_cizelgesi", dis_olaylar)
                                if str(e.get("scope") or "EXTERNAL").upper() == "EXTERNAL"],
            "cizilen": len(dis_seviyeler) + len(dis_olaylar),
            "kapak": {**(olay.get("kapak") or {}), "swing": 0}}


def _grafik_zone(zone: Mapping[str, Any]) -> dict[str, Any]:
    """Graph-only allowlist, including old queued snapshots. Never mutate engines."""
    if not zone:
        return {}
    return {**zone, "cizilen": [b for b in (zone.get("cizilen") or [])
                                if str(b.get("tip")) in ("ob", "fvg")]}


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


def _formasyon_araligi(formasyon: Mapping[str, Any], sol: int, n: int,
                       sag_bosluk: int) -> tuple[int, int, Optional[int]]:
    """Bant çizgisinin çizileceği bar aralığı: `(x0, bitis, apex_i)`.

    APEX biliniyorsa çizim apex'te BİTER. Daralan bantta iki doğru apex'te
    kesişir; apex'in ÖTESİNE uzatmak ters dönen (X çizen) uydurma geometri olur
    ve çizgiler havada asılı kalır. Eski kod apex'i yalnız sağ boşluğa düştüğünde
    kısaltıyordu: apex geçmişte kaldığında doğrular tepeyi aşıp kesişiyordu
    (kullanıcı geri bildirimi: "kırpılıyormuş gibi").
    """
    bas = formasyon.get("start_bar")
    x0 = 0
    if bas is not None and int(bas) - sol >= 0:
        x0 = min(int(bas) - sol, max(0, n - 1))
    bitis = n + max(0, int(sag_bosluk))
    apex_i = None
    if formasyon.get("apex_bar") is not None:
        apex_i = int(formasyon["apex_bar"]) - sol
        if apex_i >= x0:
            bitis = max(x0 + 1, min(bitis, apex_i + 1))
    # ÇÖZÜLMÜŞ formasyonda bant GEÇMİŞTİR: teyit/retest/geçersizleşme kartında
    # `end_bar` kırılım mumudur; bandı onun ötesine uzatmak "hâlâ sürüyor" yalanı
    # olur ve doğrular kesişmişse havada X çizer. Yalnız son mumdan ÖNCE biten
    # bant kısılır — oluşmakta olan formasyonda (`end_bar` == son mum) sağ
    # boşluktaki projeksiyon aynen kalır.
    bit = _tam(formasyon.get("end_bar"))
    if bit is not None and bit - sol < n - 1:
        bitis = max(x0 + 1, min(bitis, bit - sol + 1))
    # GEOMETRİK KESİŞİM: beyan edilen `apex_bar` motorun yuvarlamasıyla iki
    # doğrunun gerçek kesişiminden sapabiliyor (flama örneğinde 168 ↔ ~124);
    # sapma kalırsa doğrular tepeyi aşıp ters dönüyordu. Kesişim barı doğrudan
    # motorun çapa noktalarından çözülür ve çizim orada biter. Paralel bantta
    # (bayrak) kesişim yoktur → uzatma korunur.
    ust_ca = [formasyon.get(k) for k in ("hb1", "hp1", "hb2", "hp2")]
    alt_ca = [formasyon.get(k) for k in ("lb1", "lp1", "lb2", "lp2")]
    if all(v is not None for v in ust_ca) and all(v is not None for v in alt_ca):
        b1, p1, b2, p2 = (float(v) for v in ust_ca)
        c1, q1, c2, q2 = (float(v) for v in alt_ca)
        mu = (p2 - p1) / (b2 - b1) if b2 != b1 else 0.0
        ma = (q2 - q1) / (c2 - c1) if c2 != c1 else 0.0
        if abs(mu - ma) > 1e-12:
            i_kes = ((q1 - ma * c1) - (p1 - mu * b1)) / (mu - ma)
            if x0 < i_kes < bitis:
                bitis = max(x0 + 1, min(bitis, int(i_kes) + 1))
                apex_i = int(i_kes) if apex_i is None else apex_i
    return x0, bitis, apex_i


def _formasyon_serileri(formasyon: Mapping[str, Any], sol: int,
                        bitis: int) -> dict[str, list[float]]:
    """Motorun iki çapa noktasından geçen bant doğrularını bar bar değerlendirir.

    Yeni geometri ÜRETİLMEZ: `f_line_price` motorun kendi doğrusudur (`hb1/hp1` +
    `hb2/hp2` üst, `lb1/lp1` + `lb2/lp2` alt). Çapa yoksa eski yatay çizgiye
    düşülür. Kadraj hesabı ile çizim bu AYNI seriyi paylaşır — iki yerde ayrı
    hesap farklı geometri üretirdi.
    """
    from patterns.mathutil import f_line_price
    seriler: dict[str, list[float]] = {}
    adet = max(0, int(bitis))
    for ust_mu in (True, False):
        deger = formasyon.get("upper_now") if ust_mu else formasyon.get("lower_now")
        if deger is None:
            continue
        ad = "ust" if ust_mu else "alt"
        ca = ("hb1", "hp1", "hb2", "hp2") if ust_mu else ("lb1", "lp1", "lb2", "lp2")
        capa = [formasyon.get(k) for k in ca]
        if any(v is None for v in capa):
            seriler[ad] = [float(deger)] * adet
            continue
        b1, p1, b2, p2 = capa
        seriler[ad] = [f_line_price(int(b1), float(p1), int(b2), float(p2), i + sol)
                       for i in range(adet)]
    return seriler


def _gorunur_parcalar(xs: Sequence[float], ys: Sequence[float],
                      aralik: Optional[Sequence[float]]) -> list[tuple[list[float], list[float]]]:
    """Seriyi, y-aralığının İÇİNDE kalan kesintisiz parçalara böler.

    Neden: bant doğrusu fiyattan kopuk bölgede (üçgenin geriye uzanan tabanı,
    dik yükselen alt çizgi) karenin altına/üstüne taşıyor. Geometri korunur
    (noktalar `f_line_price`tan gelir) ama **kadraj dışı parça çizilmez** —
    eksen kenarında sert kesilen, anlamsız bir çizgi kalmaz. `aralik` yoksa
    seri olduğu gibi döner (birim testleri ve kare-dışı çağrılar eski davranışı
    görür).
    """
    if aralik is None or len(aralik) < 2:
        return [(list(xs), list(ys))]
    lo, hi = float(aralik[0]), float(aralik[1])
    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
        return [(list(xs), list(ys))]
    parcalar: list[tuple[list[float], list[float]]] = []
    xs_p: list[float] = []
    ys_p: list[float] = []
    for x, y in zip(xs, ys):
        if y is None or not math.isfinite(float(y)) or not (lo <= float(y) <= hi):
            if xs_p:
                parcalar.append((xs_p, ys_p))
                xs_p, ys_p = [], []
            continue
        xs_p.append(float(x))
        ys_p.append(float(y))
    if xs_p:
        parcalar.append((xs_p, ys_p))
    return parcalar


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


def _swing_ofseti(ax, x: float, yukari: bool, yerlesik: list, n: int,
                  yazi_px: float = 14.0) -> float:
    """Grafik içi etiketin piksel ofseti; yakın (aynı yönde, x'i çakışan) etiket varsa basamaklanır.

    Neden: `HL` ile `PL` aynı barda üst üste bindi (görsel-2 ölçümü). Etiket
    genişliği kısa sınıflarda ~12–14 px, fiyatlı PH/PL etiketinde ~55 px; ikinci
    etiket birinciyle bu mesafeden yakınsa alt satıra itilir.
    """
    try:
        genislik_px = float(ax.get_window_extent().width)
        bar_px = genislik_px / max(1.0, float(n))
    except Exception:
        bar_px = 6.0
    x_px = float(x) * bar_px
    # FAZ 4 §6: HH/HL/LH/LL metni mum FİTİLİNE değmesin — taban ofset 11 px
    # (10-15 px aralığı), aynı yöndeki komşu etiket varsa basamaklanır.
    ofs = max(11.0, float(SABITLER["swing_etiket_ofset_px"]))
    adim = float(SABITLER["zone_yazi_pt"]) * 1.45 * float(ax.figure.dpi) / 72.0
    while any(yn == yukari and abs(xp - x_px) < max(14.0, float(yazi_px))
              and abs(oo - ofs) < 0.5
              for xp, yn, oo in yerlesik):
        ofs += adim * 72.0 / float(ax.figure.dpi)
    yerlesik.append((x_px, yukari, ofs))
    return ofs if yukari else -ofs


def _mum_kutulari_px(ax, acilis, yuksek, dusuk, kapanis, cap: float):
    """Mum gövde+fitil kutuları PİKSEL olarak (Nx4: x0,y0,x1,y1); numpy gerekir."""
    import numpy as np

    govde, fitil = [], []
    for i, (a, k, y, d) in enumerate(zip(acilis, kapanis, yuksek, dusuk)):
        if None in (a, k, y, d):
            continue
        govde.append((i - cap / 2.0, min(a, k), i + cap / 2.0, max(a, k)))
        fitil.append((i - 0.25, d, i + 0.25, y))
    def _kutu(liste):
        if not liste:
            return np.zeros((0, 4))
        arr = np.array(liste, dtype=float)
        p0 = ax.transData.transform(arr[:, 0:2])
        p1 = ax.transData.transform(arr[:, 2:4])
        return np.hstack([np.minimum(p0, p1), np.maximum(p0, p1)])
    return np.vstack([_kutu(govde), _kutu(fitil)]) if (govde or fitil) else np.zeros((0, 4))


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


# Kare içi ikonlar: kullanıcı isteği EMOJİ (📈 📐 🎯) ama DejaVu Sans'ta bu
# kodlar YOK — çizilirse "tofu" kutusu olur ve yazı okunmaz. Bu yüzden ikon
# FONT KAPSAMASINA göre seçilir: font emojiyi taşıyorsa (Noto Emoji kurulu)
# emoji, taşımıyorsa aynı anlamı veren geometrik işaret kullanılır.
_IKONLAR: dict[str, tuple[str, str]] = {
    "sembol": ("📈", "◆"),       # hisse · zaman dilimi rozeti
    "formasyon": ("📐", "◈"),    # formasyon adı + kalite rozeti
    "hedef": ("🎯", "◎"),        # 🎯 hedef kutusu
}
_IKON_ONBELLEK: dict[str, str] = {}


def _ikon(anahtar: str) -> str:
    """Rozet ikonu: emoji fontta VARSA emoji, yoksa geometrik yedek (`◆ ◈ ◎`)."""
    emoji, yedek = _IKONLAR.get(str(anahtar), ("", ""))
    if not emoji:
        return ""
    if anahtar in _IKON_ONBELLEK:
        return _IKON_ONBELLEK[anahtar]
    secili = emoji if _font_emoji_var(emoji) else yedek
    _IKON_ONBELLEK[anahtar] = secili
    return secili


def _font_emoji_var(emoji: str) -> bool:
    """Aktif matplotlib fontu bu emojiyi içeriyor mu? (tofu kutusu koruması).

    `.ttc`/okunamayan font ya da eksik `fontTools` → `False` (geometrik yedek
    kullanılır). Aile LİSTE olarak verilir: fontconfig desen ayrıştırıcısı
    `"sans-serif"` gibi genel adları tek başına kabul etmiyor.
    """
    try:
        from matplotlib import font_manager, rcParams
        from fontTools.ttLib import TTFont

        aile = list(rcParams.get("font.family") or ["sans-serif"])
        dosya = list(rcParams.get("font.sans-serif") or [])[:1]
        yol = font_manager.findfont(font_manager.FontProperties(
            family=(dosya or None) if dosya else aile))
        cmap: set[int] = set()
        with TTFont(str(yol), fontNumber=0) as yazi:
            for tablo in yazi["cmap"].tables:
                cmap |= set(tablo.cmap.keys())
        return ord(emoji) in cmap
    except Exception:      # font okunamazsa: yedek işaret (tofu çizilmez)
        return False


_OLCU_FIG = None


def _olcu_figir():
    """Ölçüm için tek, yeniden kullanılan Agg figürü (pyplot'a DOKUNMAZ).

    Neden ayrı: `_metinler` başlık yerleşimini kare çizilmeden ÖNCE karara
    bağlıyor (eksen üst sınırı buna bağlı) ve o anda elde bir figür yok. Kalıcı
    bir ölçüm figürü, tahmini (`_rozet_px`) gerçek renderer genişliğine çevirir:
    tahminle 3 rozet + sağ yazı dar karede 1-2 px şaşıp üst üste biniyordu.
    """
    global _OLCU_FIG
    if _OLCU_FIG is None:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        fig = Figure(figsize=(10.8, 1.0), dpi=float(SABITLER["dpi"]))
        FigureCanvasAgg(fig)
        _OLCU_FIG = fig
    return _OLCU_FIG


def _olcu_px(metin: str, yazi_pt: float) -> float:
    """Metnin gerçek piksel genişliği (kalıcı ölçüm figüründen)."""
    try:
        return _metin_px(_olcu_figir(), str(metin), float(yazi_pt))
    except Exception:                       # pragma: no cover - ölçüm süsü
        return _rozet_px(metin, yazi_pt)


def _rozet_px(metin: str, yazi_pt: float) -> float:
    """Rozetin yatay genişliği (piksel) — TAHMİN; gerçek ölçüm `_metin_px`te."""
    punto_px = float(yazi_pt) * float(SABITLER["dpi"]) / 72.0
    return _genislik_16(str(metin)) * (punto_px / 16.0) * float(SABITLER["metin_carpani"])


def _metin_px(fig, metin: str, yazi_pt: float) -> float:
    """Metnin GERÇEK piksel genişliği (renderer'dan); ölçülemezse tahmine düşer.

    Neden gerçek ölçüm: rozetler (Pills) sol kenardan diziliyor; tahmin 1-2 px
    şaşsa da 3 rozet üst üste biner (ölçüm: `Simetrik Üçgen (%88)` ile durum
    rozeti çakıştı). Font yoksa `_rozet_px` tahmini tek başına yeter.
    """
    gecici = None
    try:
        gecici = fig.text(0.0, -0.5, metin, fontsize=float(yazi_pt))
        gen = float(gecici.get_window_extent(renderer=fig.canvas.get_renderer()).width)
    except Exception:                       # pragma: no cover - ölçüm süsü
        gen = float(_rozet_px(metin, yazi_pt))
    finally:
        if gecici is not None:
            try:
                gecici.remove()
            except Exception:  # noqa: S110 - teardown; geçici metin temizliği / pragma: no cover
                pass
    return max(4.0, gen)


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


def _yapı_satırı(sonuclar: Any, tf: str, son_kapanis: Optional[float]) -> str:
    """Kartın `🏗 Piyasa Yapısı` bloğunun İLK satırı, birebir (yalnız `• ` öneki düşer).

    Neden biçimleyiciyi yeniden kullanıyoruz: karenin karttan farklı bir cümle
    kurmaması gerekiyor (§14.1 "uydurma alan yok"). Motor hiç yoksa/ayrıksa `''`
    döner ve DIPNOT YAZILMAZ — yokluk zaten `meta["eksik_katmanlar"]`da (`ms`).
    Biçimlendirme hatası kareyi asla düşürmez (§2.9).
    """
    if not sonuclar:
        return ""
    try:
        from notification_context import domain_bolumleri

        # 2026-10-23: kare başlığı da KART diliyle konuşur (`1g yön yukarı
        # (iç ve dış yapı)`); klasik metin `1g yapı: dış yükseliş` jargondu.
        # `klasik` biçim geri dönüş yolu olarak `notification_context`te duruyor.
        bolumler = domain_bolumleri({tf: sonuclar}, son_kapanis, stil="kart",
                                    alarm_tf=tf)
        satirlar = (bolumler.get("yapi_ozet") or bolumler.get("yapi") or [])
    except Exception as hata:  # noqa: BLE001 - kart satırı kareyi engellemez
        log.debug("grafik: yapı satırı alınamadı (%s: %s)", type(hata).__name__, hata)
        return ""
    if not satirlar:
        return ""
    satir = str(satirlar[0]).strip().lstrip("◈•").strip()
    return _grafik_yapi_metni(satir)


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
    """Yalnız dış PH/PL/WH/WL seviyeleri + dış BOS·CHoCH.

    Internal swing ve adaylar grafiğe alınmaz. Sağ cetveldeki PH/PL/WH/WL
    dış scope'un güvenli export seviyeleridir;
    motor export'u yoksa yalnız rolü açıkça atanmış external swing'lerden türetilir.
    Olay çizgileri ayrı sözleşme olarak EXTERNAL, onaylı ve geçerli BOS/CHoCH'tur.
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

    # Internal pivots/candidates are not part of the chart contract.
    swinglar: list[dict[str, Any]] = []
    swing_maks = 0
    olay_maks = int(_ortam_sayi("GRAFIK_OLAY_MAKS", SABITLER["olay_maks"]))
    elenen = 0

    # Seviyelerde önce motorun safety-gated export'unu kullan. Eski/yalın sonuç
    # nesneleri export taşımıyorsa, aynı rolü taşıyan dış swing'lerden geri dönüş
    # sağlanır. Sırf swing_class PH/PL olduğu için korunan seviye üretme.
    roller = {
        "PROTECTED_HIGH": ("PH", "external_protected_high"),
        "PROTECTED_LOW": ("PL", "external_protected_low"),
        "WEAK_HIGH": ("WH", "external_weak_high"),
        "WEAK_LOW": ("WL", "external_weak_low"),
    }
    dis_kayitlar: dict[str, dict[str, Any]] = {}
    for b in (_alan(detay, "external_swings", ()) or ()):
        rol = _ad(_alan(b, "structural_role"))
        if rol not in roller:
            continue
        ham_durum = _ad(_alan(b, "state"))
        if "BROKEN" in ham_durum or bool(_alan(b, "broken")):
            continue
        fiyat = _gercek(_alan(b, "price"))
        if fiyat is None:
            continue
        bar = _tam(_alan(b, "source_bar"))
        onceki = dis_kayitlar.get(rol)
        if onceki is not None and (bar is None or
                                   (onceki.get("kaynak_bar") is not None and
                                    int(bar) <= int(onceki["kaynak_bar"]))):
            continue
        etiket, _ = roller[rol]
        dis_kayitlar[rol] = {"bar": (bar - sol) if bar is not None else None,
                             "kaynak_bar": bar, "fiyat": fiyat,
                             "etiket": etiket, "rol": rol,
                             "yon": "ust" if rol.endswith("HIGH") else "alt"}

    export = _alan(ms, "export")
    seviyeler: list[dict[str, Any]] = []
    for rol, (etiket, export_alan) in roller.items():
        # Export nesnesi varsa o tek doğruluk kaynağıdır; None seviyeyi çizme.
        export_fiyat = _gercek(_alan(export, export_alan)) if export is not None else None
        if export is not None and export_fiyat is None:
            continue
        kayit = dis_kayitlar.get(rol)
        if export is None and kayit is None:
            continue
        seviye = dict(kayit or {"bar": None, "kaynak_bar": None,
                               "etiket": etiket, "rol": rol,
                               "yon": "ust" if rol.endswith("HIGH") else "alt"})
        if export_fiyat is not None:
            seviye["fiyat"] = export_fiyat
        if seviye.get("fiyat") is None:
            continue
        seviyeler.append(seviye)

    zaman_cizelgesi = []
    for e in (_alan(detay, "event_history", ()) or ()):
        if _ad(_alan(e, "scope")) != "EXTERNAL":
            continue
        bar = _tam(_alan(e, "event_bar"))
        zaman_cizelgesi.append({"scope": "EXTERNAL", "kaynak_bar": bar,
            "tur": _ad(_alan(e, "event_type")).replace("EVENT_", ""),
            "yon": _ad(_alan(e, "direction")), "seviye": _gercek(_alan(e, "broken_level")),
            "zaman": str(_alan(e, "timestamp") or _alan(e, "event_time") or "") or None,
            "yas": _tam(_alan(e, "age_bars")), "teyit": _ad(_alan(e, "confirmation_status")),
            "gecerlilik": _ad(_alan(e, "validity")), "guncellik": _ad(_alan(e, "relevance"))})
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
        # FAZ 3 §4.2 (Line Truncation): kırılım çizgisi "oluştuğu pivot"tan
        # başlar. Pivot barı motorun kendi alanıdır (`origin_source_bar`);
        # uydurulmaz, yoksa çizgi kırılım mumundan başlar (eski davranış).
        _pivot = _tam(_alan(b, "origin_source_bar"))
        olaylar.append({"bar": bar - sol, "kaynak_bar": bar,
                        "aday_bar": (_tam(_alan(b, "candidate_bar")) - sol)
                        if _tam(_alan(b, "candidate_bar")) is not None else None,
                        "pivot_bar": (_pivot - sol) if _pivot is not None else None,
                        "pivot_kaynak_bar": _pivot,
                        "pivot_fiyat": _gercek(_alan(b, "origin_price")),
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
                     "yon": son_olay["yon"],
                     "pivot_bar": son_olay.get("pivot_bar"),
                     "pivot_kaynak_bar": son_olay.get("pivot_kaynak_bar")}
    return {"swinglar": swinglar, "seviyeler": seviyeler,
            "zaman_cizelgesi": zaman_cizelgesi,
            "olaylar": olaylar, "kritik": kritik,
            "cizilen": len(swinglar) + len(seviyeler) + len(olaylar),
            "elenen": elenen + olay_elenen,
            "kapak": {"swing": swing_maks, "olay": olay_maks},
            "hata": []}


def _zone_meta(zone: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """`meta["zone"]`: §2'deki `{cizilen, elenen}` + G2 izleri (test yüzeyi)."""
    # Alanlar her durumda AYNI biçimde döner (§13 JSONL okuyucusu dalgalanmasın):
    # boşsa sayaçlar 0, `sirala` "zone verisi yok" (motorlar hiç çağrılmadı).
    if not zone:
        return {"cizilen": 0, "elenen": 0, "tip": {"ob": 0, "fvg": 0, "eng": 0},
                "kaynak_disi": 0, "kapak": {}, "sirala": "zone verisi yok", "atr": None,
                "cikarim": {}, "hata": [], "kayitlar": [], "etiket_atlandi": 0,
                "etiket_ic": 0, "etiket_serit": 0,
                "dolgu": 0, "orta": 0, "kunye": 0}
    kayitlar = list(_grafik_zone(zone).get("cizilen") or [])
    return {"cizilen": len(kayitlar), "elenen": int(zone.get("elenen") or 0),
            "tip": {t: sum(1 for b in kayitlar if b["tip"] == t) for t in ("ob", "fvg", "eng")},
            "kaynak_disi": int(zone.get("kaynak_disi") or 0),
            "kapak": dict(zone.get("kapak") or {}), "sirala": zone.get("sirala"),
            "atr": zone.get("atr"), "cikarim": dict(zone.get("cikarim") or {}),
            "hata": list(zone.get("hata") or []),
            "etiket_atlandi": int(zone.get("etiket_atlandi") or 0),
            # GÖRSEL-4: etiket kutunun İÇİNDE mi (`etiket_ic`) yoksa kutu sığmadığı
            # için sağ şerit yedeğine mi taşındı (`etiket_serit`)?
            "etiket_ic": int(zone.get("etiket_ic") or 0),
            "etiket_serit": int(zone.get("etiket_serit") or 0),
            # GÖRSEL-5: doluluk cetveli / %50 orta çizgisi / künye sayaçları.
            "dolgu": int(zone.get("dolgu") or 0),
            "orta": int(zone.get("orta") or 0),
            "kunye": int(zone.get("kunye") or 0),
            "kayitlar": [{k: b.get(k) for k in ("tip", "yon", "alt", "ust", "mum_alt", "mum_ust",
                                                "kaynak", "kayit_kaynagi", "tamamlandi", "taraf",
                                                "durum", "doluluk", "mitigated_percentage", "gap",
                                                "x0", "x1", "mesafe", "mesafe_atr", "vurgu", "zaman")}
                         for b in kayitlar]}


def _olay_meta(olay: Optional[Mapping[str, Any]], ozet: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
    """`meta["olay"]`: §2'deki `{cizilen, elenen}` + G3 izleri (§13 biçimi)."""
    ozet = dict(ozet or {})
    olay = _grafik_dis_yapi(olay or {})
    if not olay:
        return {"cizilen": 0, "elenen": 0, "swing": 0, "dis_seviye": 0,
                "bos_choc": 0, "kritik": None, "kapak": {}, "etiket_atlandi": 0,
                "kritik_cizildi": False, "kritik_atlandi": 0, "capa": 0,
                "hata": [], "phpl_serit": 0, "whwl_serit": 0}
    return {"cizilen": int(olay.get("cizilen") or 0), "elenen": int(olay.get("elenen") or 0),
            "swing": 0,
            "dis_seviye": len(olay.get("seviyeler") or []),
            "bos_choc": len(olay.get("olaylar") or []),
            "kritik": (olay.get("kritik") or {}).get("seviye"),
            "kapak": dict(olay.get("kapak") or {}),
            "olay_barlari": [b.get("kaynak_bar") for b in (olay.get("olaylar") or [])],
            "etiket_atlandi": int(ozet.get("etiket_atlandi") or 0),
            "kritik_cizildi": bool(ozet.get("kritik")),
            "kritik_atlandi": int(ozet.get("kritik_atlandi") or 0),
            "capa": int(ozet.get("capa") or 0),
            "phpl_serit": int(ozet.get("phpl_serit") or 0),
            "whwl_serit": int(ozet.get("whwl_serit") or 0),
            "hata": list(olay.get("hata") or [])}


def _serit_meta(serit: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """`meta["serit"]`: `{acik, esik, spike}` (§2) + kaynak/hacimsiz izleri."""
    if not serit:
        return {"acik": False, "esik": None, "spike": [], "kaynak": "yok", "yerel": False,
                "hacimsiz": 0, "elenen_spike": 0, "capa": 0, "yetersiz": False,
                "uzunluk": None, "rozet": 0, "rozet_artis": 0, "rozet_dusus": 0,
                "rozet_taze_artis": None, "rozet_taze_dusus": None}
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
    try:
        with open(gecici, "wb") as akis:
            akis.write(veri)
        os.replace(gecici, yol)
    finally:
        try:
            os.remove(gecici)
        except OSError:
            pass


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


# Alarm türleri: geçersizleşmede TEK kare (geçersizleşen TF), diğer olaylarda
# `TELEGRAM_GRAFIK_ADET`. GÖRSEL-4 kullanıcı kararı: "geçersizleşince görsel
# sadece geçersizleşen timeframede gelecek" — diğer TF'lerde o karede çizilecek
# bant/alarm YOK, yani üç ek kare neredeyse boş gidiyordu.
_TEK_KARE_ALARM = frozenset({"gecersiz"})


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
    `alarm_turu="gecersiz"` (geçersizleşme) istisnadır: yalnız birincil TF'nin
    karesi üretilir (GÖRSEL-4).

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
    if str(alarm_turu or "").strip().lower() in _TEK_KARE_ALARM:
        ek_cerceveler = {}
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
    yol = None
    try:
        yol, meta = ciz(goruntu, tf, secenekler={
            "cikti": hedef,
            "serit": serit,
            "beklenen_son_bar_ts": beklenen_son_bar_ts,
        })
        return yol, meta
    finally:
        if yol is None:
            try:
                os.remove(hedef)
            except OSError:
                pass


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
