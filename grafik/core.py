# grafik/core.py — ortam/sabitler/palet/ölçü çekirdeği (Faz 2).
# Yamalı yüzey (grafik.kareyi_yaz, grafik.kare_yolu, grafik.tempfile, grafik.shutil)
# grafik/__init__.py'de; bkz. docs/tasarim/MODULERLESTIRME_PLANI_2026-10-26.md.

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

import grafik as _pkg  # yamalı adlar için geç bağlama (plan §3)

log = logging.getLogger("grafik")  # eski kayıt adıyla aynı (__name__ yerine)

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


_CIZIM_KILIDI = threading.RLock()


def _seri_cizim(fn):
    @wraps(fn)
    def kilitli(*args, **kwargs):
        # pyplot global durumu thread-safe değil: otomatik/manuel çizimler seri.
        with _CIZIM_KILIDI:
            return fn(*args, **kwargs)
    return kilitli


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


