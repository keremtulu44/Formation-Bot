# -*- coding: utf-8 -*-
"""Örnek görsel üretim sistemi — DEMO senaryo katalogundan alarm kartı karesi üretir.

Neden var: botun Telegram'a gönderdiği karelerin nasıl göründüğünü botu
çalıştırmadan ve canlı veri beklemeden görmek gerek — yeni katılımcıya tanıtım,
kanal açılış paketi, görsel değişiklik sonrası kontrol. Bu betik projenin KENDİ
çizim zincirini kullanır (`grafik.anlik_goruntu` → `grafik.ciz`, §14.2: motor
ÇALIŞTIRILMAZ, hesap eklenmez), bu yüzden üretilen kare canlı kareyle AYNI
görünümde olur; ayrı bir "demo çizicisi" yok.

Kurallar (scripts/grafik_onizleme.py ve grafik_uret.py --demo ile aynı sözleşme):
  * Veri SENTETİK ve deterministiktir (tohumlu rastgelelik); gerçek piyasa
    verisi değildir, sembol her senaryoda "DEMO"'dur.
  * `bot_data/` içine ASLA yazılmaz (canlı önbelleği sentetik veriyle zehirlemek
    §22'de kayıtlı sapma); çıktı yolu/dizini reddedilir.
  * Kapanış kuralı tek kaynaktan gelir: `simdi`, son barın KAPANIŞ anından
    90 sn sonradır (`data.mum_kapanis_ani`) → açık bar düşürmesi yaşamaz.

Kullanım:
    python scripts/ornek_gorsel_uret.py --liste
    python scripts/ornek_gorsel_uret.py                     # iki manşet senaryo
    python scripts/ornek_gorsel_uret.py --senaryo hepsi     # tüm katalog
    python scripts/ornek_gorsel_uret.py --senaryo bayrak_aday --mobil
    python scripts/ornek_gorsel_uret.py --senaryo hepsi --json

Çıktı varsayılan yeri: docs/ornek_galeri/ornek_<senaryo>_<tf>.png
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

import grafik  # noqa: E402
from domain_engines.fvg.fvg_engulfing_models import FvgDirection, FvgState  # noqa: E402
from domain_engines.market_structure.models import Direction  # noqa: E402

IST = timezone(timedelta(hours=3))
TF_DOSYA = {"1h": "1s", "2h": "2s", "4h": "4s", "1d": "1g"}
VARSAYILAN_DIZIN = KOK / "docs" / "ornek_galeri"


# ------------------------------------------------------------------ yardımcılar

def _seans_etiketleri(n: int, tf: str, ilk: datetime) -> list[datetime]:
    """BIST seans etiketleri (test_grafik_iskelet._seans_zamanlari ile aynı şema).

    1s: 09:30…17:30 (günde 9 mum) · 2s: 09:30,11:30,…,17:30 · 4s: 09:30,13:30 ·
    1g: iş günü başına bir bar. Neden önemli: `data.bar_kapandi_mi` kapanışı
    etikete göre hesaplar; düz 24 saatlik dizim son barı yanlış düşürür.
    """
    if tf == "1d":
        gun, cikti = ilk, []
        while len(cikti) < n:
            if gun.weekday() < 5:
                cikti.append(gun.replace(hour=9, minute=30))
            gun += timedelta(days=1)
        return cikti
    saatler = {"1h": [9, 10, 11, 12, 13, 14, 15, 16, 17],
               "2h": [9, 11, 13, 15, 17], "4h": [9, 13]}[tf]
    gun, cikti = ilk, []
    while len(cikti) < n:
        if gun.weekday() < 5:
            for s in saatler:
                if len(cikti) >= n:
                    break
                cikti.append(gun.replace(hour=s, minute=30))
        gun += timedelta(days=1)
    return cikti


def _simdi(zamanlar: list[datetime], tf: str) -> datetime:
    """Son barın kapanış anı + 90 sn (tek kaynak: `data.mum_kapanis_ani`).

    Neden böyle: `anlik_goruntu` açık barı çizimden düşürür (§0.6); "şimdi"yi
    son etikete bağlayınca son mum sessizce kaybolur. Kapanış anını projenin
    kendi fonksiyonundan almak tatil/yarım gün kurallarını da doğru getirir.
    """
    from data import mum_kapanis_ani

    kapanis = mum_kapanis_ani(zamanlar[-1], tf)
    return (kapanis or zamanlar[-1]).to_pydatetime() + timedelta(seconds=90)


class _Yapici:
    """Deterministik mum üretici: gövde verilir, fitil tohumlu titremeyle şekillenir.

    `fitil` gövdenin her iki yanına eklenecek ortalama taşma; tohumlu rastgelelik
    her çalıştırmada AYNI kareyi üretir (piksel değil `girdi_ozeti` determinizmi,
    §12.19). Bütün senaryolar aynı sınıfı kullanır → görsel dil tek kalır.
    """

    def __init__(self, tohum: int):
        self._rastgele = random.Random(tohum)
        self.acilis: list[float] = []
        self.yuksek: list[float] = []
        self.dusuk: list[float] = []
        self.kapanis: list[float] = []
        self.hacim: list[float] = []

    def mum(self, acilis: float, kapanis: float, hacim: float = 1_500_000,
            fitil: float = 0.18, govde_bagla: bool = True):
        """Tek mum ekler; `govde_bagla` ise açılış önceki kapanışa yapışır."""
        if govde_bagla and self.kapanis:
            acilis = self.kapanis[-1] * 0.998 + acilis * 0.002
        govde_ust, govde_alt = max(acilis, kapanis), min(acilis, kapanis)
        ust = govde_ust + fitil * (0.6 + 0.8 * self._rastgele.random())
        alt = govde_alt - fitil * (0.6 + 0.8 * self._rastgele.random())
        self.acilis.append(round(acilis, 2))
        self.yuksek.append(round(ust, 2))
        self.dusuk.append(round(alt, 2))
        self.kapanis.append(round(kapanis, 2))
        self.hacim.append(float(round(hacim)))

    def cerceve(self, zamanlar: list[datetime]) -> dict[str, list]:
        """`grafik.anlik_goruntu`nin beklediği kolon sözlüğü (pandas gerekmez)."""
        return {"zaman": zamanlar, "acilis": self.acilis, "yuksek": self.yuksek,
                "dusuk": self.dusuk, "kapanis": self.kapanis, "hacim": self.hacim}


# ------------------------------------------------------------ motor kayıt kalıpları
# Alan adları canlı motor kayıtlarıyla birebir (grafik yalnız OKUR, çağırmaz):
# OB → OrderBlockRecord, FVG → FvgFormation, olay → dış yapı event_history'si.

def _ob(kaynak_bar: int, alt: float, ust: float, *, bullish: bool, skor: float = 2.0,
        doluluk: float = 0.0):
    """Sentetik `OrderBlockRecord`; `fill_boundary` doluluk yüzdesini taşır."""
    yukseklik = float(ust) - float(alt)
    sinir = (float(ust) - yukseklik * float(doluluk)) if bullish else \
            (float(alt) + yukseklik * float(doluluk))
    return SimpleNamespace(source_index=int(kaynak_bar), source_time=None,
                           top=float(ust), bottom=float(alt), bullish=bool(bullish),
                           base_score=float(skor), anchor_high=float(ust),
                           anchor_low=float(alt), imbalance_end_index=None,
                           fill_boundary=sinir)


def _fvg(kaynak_bar: int, alt: float, ust: float, *, direction: int,
         durum: str = "ACTIVE", kalite: float = 85.0, doluluk: float = 0.0):
    """Sentetik `FvgFormation`; durum adları `FvgState` üye adlarıyla aynı."""
    return SimpleNamespace(formation_index=int(kaynak_bar), formation_time=None,
                           lower_boundary=float(alt), upper_boundary=float(ust),
                           direction=FvgDirection(direction),
                           state=FvgState[durum],
                           gap_size=round(float(ust) - float(alt), 2),
                           gap_atr=round((float(ust) - float(alt)) / 1.4, 3),
                           formation_atr=1.4, quality=float(kalite),
                           maximum_fill_ratio=float(doluluk),
                           close_fill_ratio=float(doluluk))


def _olay_kaydi(*, tur: str, yon: str, bar: int, seviye: float, pivot_bar: int,
                kimlik: int, nitelik: float, yas: int, kanit: str = "",
                aday_bar: int | None = None):
    """Sentetik dış yapı olayı (BOS/CHoCH) — onaylı ve geçerli.

    `direction` gerçek `Direction` enum'unu taşır: grafik `.name`'den "UP"
    okur, kart biçimlendirici sayısal değeri okur — aynı kayıt iki yüzeyi de
    doğru besler (§14.1: iki ayrı temsil yok).
    """
    return SimpleNamespace(scope="EXTERNAL", event_type=f"EVENT_{tur}",
                           event_uid=f"demo-{kimlik}",
                           event_bar=int(bar), candidate_bar=aday_bar,
                           origin_source_bar=int(pivot_bar), origin_price=float(seviye),
                           direction=Direction.UP if yon == "ust" else Direction.DOWN,
                           broken_level=float(seviye), identity=int(kimlik),
                           quality=float(nitelik), age_bars=int(yas),
                           confirmation_status="CONFIRMED", validity="VALID",
                           relevance="CURRENT", evidence_text=kanit, timestamp="")


def _swing(*, rol: str, fiyat: float, bar: int, durum: str = "ACTIVE"):
    return SimpleNamespace(structural_role=rol, state=durum, broken=False,
                           price=float(fiyat), source_bar=int(bar))


def _sonuclar(ob=(), fvg=(), olaylar=(), swingler=(), seviyeler=None,
              dis_durum="STATE_BULLISH", ic_durum=None):
    """`run_domain_engines` çıktısı BİÇİMİNDE sözlük (grafik yalnız okur).

    `data_quality="OK"` güven şeridinin motor hazırlık satırını ("hazır") besler;
    alan yoksa şerit "hazırlık bilinmiyor" der — örnek kartta yanlış izlenim
    olur. `dis_durum` dış yapı durum adıdır (`STATE_BULLISH` gibi); kart üst
    satırındaki yapı özeti (◈ … yapı: dış ↑) buradan gelir. `seviyeler` dış
    PH/PL/WH/WL export seviyelerini taşır.
    """
    seviyeler = seviyeler or {}
    yon_sayi = 1 if "BULLISH" in dis_durum or "TRANSITION_UP" in dis_durum else (
        -1 if "BEARISH" in dis_durum or "TRANSITION_DOWN" in dis_durum else 0)
    return {"order_block": SimpleNamespace(
                data_quality="OK", error=None, skipped=False,
                details={"active_records": list(ob), "records": list(ob)}),
            "fvg": SimpleNamespace(
                data_quality="OK", error=None, skipped=False,
                details={"fvg_formations": list(fvg), "engulfing_formations": []}),
            "volume_participation": SimpleNamespace(
                data_quality="OK", error=None, skipped=False,
                details={"latest_metrics": SimpleNamespace(
                    data_ready=True, volume_usable=True, capital_usable=True)}),
            "market_structure": SimpleNamespace(
                data_quality="OK", error=None, skipped=False,
                details={"external_swings": list(swingler),
                         "event_history": list(olaylar)},
                export=SimpleNamespace(
                    events=list(olaylar),
                    latest_external_event=olaylar[-1] if olaylar else None,
                    latest_internal_event=None,
                    external_scope=SimpleNamespace(
                        scope="EXTERNAL", state=dis_durum,
                        direction=Direction(yon_sayi), quality=80.0,
                        evidence_text="", conflict_text=""),
                    internal_scope=(SimpleNamespace(
                        scope="INTERNAL", state=ic_durum,
                        direction=Direction(yon_sayi), quality=70.0,
                        evidence_text="", conflict_text="") if ic_durum else None),
                    external_state=None, internal_state=None,
                    external_protected_high=seviyeler.get("protected_high"),
                    external_protected_low=seviyeler.get("protected_low"),
                    external_weak_high=seviyeler.get("weak_high"),
                    external_weak_low=seviyeler.get("weak_low")))}


# ------------------------------------------------------------------- senaryolar
# Her senaryo: sentetik çerçeve + formasyon kaydı + bölge/yapı katmanları.
# Kayıtlar canlı motordan çıkabilecek alan DEĞERLERİNİ taşır; saha dışı
# uydurma alan yok (§14.1). Sembol hep "DEMO".

def _senaryo_ucgen_teyit():
    """Simetrik Üçgen · 1g · KIRILIM_TEYITLI — tam katmanlı manşet kartı.

    Yükseliş bağlamı → daralan üçgen (üst düşen, alt yükselen) → kapanışla
    teyitli yukarı kırılım + devam. Bölge (OB/FVG), dış yapı (BOS/CHoCH + PH/PL)
    ve kanıt etiketi katmanlarının HEPSİ açıktır: kartın en dolu hali.
    """
    n, tf = 150, "1d"
    zamanlar = _seans_etiketleri(n, tf, datetime(2026, 5, 4, 9, 30, tzinfo=IST))
    y = _Yapici(11)

    # 0..79 — yükseliş bağlamı 44 → 56
    for i in range(80):
        kapanis = 44.0 + 12.0 * (i / 79) ** 1.15 + 0.55 * math.sin(i / 6.5)
        y.mum(kapanis - 0.12, kapanis, 1_200_000 + 9_000 * i)

    # 80..129 — daralan üçgen
    baslangic, egim = 80, 0.052

    def ust_bant(t):
        return 56.30 - egim * (t - baslangic)

    def alt_bant(t):
        return 49.70 + egim * (t - baslangic)

    for t in range(baslangic, 130):
        ust, alt = ust_bant(t), alt_bant(t)
        f = (math.sin((t - baslangic) * math.pi / 7.0) + 1.0) / 2.0
        kapanis = alt + (ust - alt) * (0.18 + 0.64 * f) \
            + (y._rastgele.random() - 0.5) * 0.16
        fitil = 0.30 if f > 0.92 or f < 0.08 else 0.18   # uçlarda banta dokunan fitil
        y.mum(kapanis - 0.08, kapanis, 900_000 + 6_000 * (t - baslangic), fitil=fitil)

    # 130 — TEYİT barı: bant üstünde güçlü kapanış, hacim patlaması
    teyit_kapanis = round(ust_bant(130) + 0.56, 2)
    y.mum(ust_bant(130) - 0.30, teyit_kapanis, 5_600_000, fitil=0.22)
    # 131..149 — devam hareketi 54.3 → 56.1
    for i in range(131, n):
        kapanis = teyit_kapanis + 1.80 * ((i - 130) / (n - 130)) ** 0.8 \
            + 0.16 * math.sin(i / 3.1)
        y.mum(kapanis - 0.10, kapanis, 2_600_000 - 9_000 * (i - 131))

    cift = {"pattern_name": "Simetrik Üçgen", "state": "KIRILIM_TEYITLI",
            "quality": 87.5, "contraction": 0.26, "start_bar": baslangic,
            "end_bar": 130, "apex_bar": 143, "upper_now": round(ust_bant(130), 2),
            "lower_now": round(alt_bant(130), 2), "upper_touches": 4, "lower_touches": 4,
            "hb1": baslangic, "hp1": round(ust_bant(baslangic), 2),
            "hb2": 130, "hp2": round(ust_bant(130), 2),
            "lb1": baslangic, "lp1": round(alt_bant(baslangic), 2),
            "lb2": 130, "lp2": round(alt_bant(130), 2),
            "break_price": round(ust_bant(130), 2), "candle_close_price": teyit_kapanis,
            "break_dir": 1, "progress": 0.79,
            "evidence_text": "üst bant 4 · alt bant 4 temas · daralma %74 · "
                             "teyit barı RVOL 2,6"}
    sonuclar = _sonuclar(
        ob=[_ob(129, 53.00, 54.05, bullish=True, skor=2.0),
            _ob(74, 56.90, 57.90, bullish=False, skor=1.0, doluluk=0.35)],
        fvg=[_fvg(131, 54.90, 55.60, direction=1, durum="ACTIVE", kalite=84.0),
             _fvg(102, 56.30, 56.95, direction=-1, durum="PARTIAL_FILL",
                  kalite=71.0, doluluk=0.45)],
        olaylar=[_olay_kaydi(tur="BOS", yon="ust", bar=130, seviye=round(ust_bant(130), 2),
                             pivot_bar=112, kimlik=41, nitelik=82, yas=0,
                             kanit="kapanış 54,34 > 53,80"),
                 _olay_kaydi(tur="CHOCH", yon="alt", bar=92, seviye=51.20,
                             pivot_bar=88, kimlik=37, nitelik=70, yas=38),
                 _olay_kaydi(tur="BOS", yon="ust", bar=60, seviye=51.90,
                             pivot_bar=44, kimlik=29, nitelik=76, yas=70)],
        swingler=[_swing(rol="PROTECTED_HIGH", fiyat=58.10, bar=76),
                  _swing(rol="PROTECTED_LOW", fiyat=48.90, bar=88),
                  _swing(rol="WEAK_HIGH", fiyat=55.90, bar=108),
                  _swing(rol="WEAK_LOW", fiyat=50.80, bar=96)],
        seviyeler={"protected_high": 58.10, "protected_low": 48.90,
                   "weak_high": 55.90, "weak_low": 50.80})
    return {"tf": tf, "cerceve": y.cerceve(zamanlar), "cift": cift,
            "sonuclar": sonuclar, "alarm_turu": "teyit", "alarm_bar": 130,
            "etiket_detay": True, "simdi": _simdi(zamanlar, tf),
            "aciklama": "Tam katmanlı teyit kartı: bölge + dış yapı + kanıt etiketi"}


def _senaryo_bayrak_aday():
    """Boğa Bayrağı · 4s · KIRILIM_ADAYI — direk + bayrak, kırılım öncesi.

    Yatay bağlam → dik yükseliş direği (hacim patlaması) → aşağı eğimli,
    daralan bayrak kanalı → üst banda yükselen kapanışlar. Kırılım HENÜZ
    yok: kart "kırılım adayı" hâliyle çizilir (kritik seviye vurgulu).
    """
    n, tf = 210, "4h"
    zamanlar = _seans_etiketleri(n, tf, datetime(2026, 4, 1, 9, 30, tzinfo=IST))
    y = _Yapici(23)

    # 0..159 — yatay/yavaş yükselen bağlam 30 → 33.5
    for i in range(160):
        kapanis = 30.0 + 3.5 * (i / 159) + 0.42 * math.sin(i / 8.0)
        y.mum(kapanis - 0.07, kapanis, 700_000 + 4_000 * i)

    # 160..172 — direk: 33.5 → 39.9, hacim giderek artar
    for i in range(160, 173):
        pay = (i - 160) / 12
        kapanis = 33.5 + 6.4 * pay ** 0.85
        y.mum(kapanis - 0.25, kapanis, 1_600_000 + 4_200_000 * pay, fitil=0.16)

    # 173..205 — bayrak: aşağı eğimli daralan kanal
    def kanal(t):
        orta = 39.90 - 0.052 * (t - 173)
        yarim = 0.78 - 0.008 * (t - 173)
        return orta + yarim, orta - yarim          # üst, alt

    for t in range(173, 206):
        ust, alt = kanal(t)
        f = (math.sin((t - 173) * math.pi / 5.0) + 1.0) / 2.0
        kapanis = alt + (ust - alt) * (0.22 + 0.56 * f) \
            + (y._rastgele.random() - 0.5) * 0.10
        y.mum(kapanis - 0.05, kapanis, 900_000 - 2_500 * (t - 173), fitil=0.14)

    # 206..209 — üst banda yürüyen kapanışlar (aday baskısı)
    for i, ek in enumerate((0.02, 0.10, 0.17, 0.21)):
        ust, _ = kanal(206 + i)
        kapanis = min(ust - 0.06, 37.60 + 0.55 * i + ek)
        y.mum(kapanis - 0.09, kapanis, 1_500_000 + 260_000 * i, fitil=0.13)

    ust_bas, alt_bas = kanal(173)
    ust_simdi, alt_simdi = kanal(209)
    cift = {"pattern_name": "Boğa Bayrağı", "state": "KIRILIM_ADAYI",
            "quality": 79.0, "contraction": 0.33, "start_bar": 173, "end_bar": 209,
            "upper_now": round(ust_simdi, 2), "lower_now": round(alt_simdi, 2),
            "hb1": 173, "hp1": round(ust_bas, 2), "hb2": 209, "hp2": round(ust_simdi, 2),
            "lb1": 173, "lp1": round(alt_bas, 2), "lb2": 209, "lp2": round(alt_simdi, 2),
            "upper_touches": 3, "lower_touches": 3, "direction": 1,
            "critical_price_level": round(ust_simdi, 2), "progress": 0.68,
            "evidence_text": "direk +%19 · kanal daralması %33 · son 4 bar üst banda"}
    sonuclar = _sonuclar(
        ob=[_ob(166, 35.60, 36.45, bullish=True, skor=2.0, doluluk=0.30),
            _ob(171, 39.55, 40.30, bullish=False, skor=1.0)],
        fvg=[_fvg(165, 36.60, 37.40, direction=1, durum="ACTIVE", kalite=88.0),
             _fvg(158, 33.80, 34.55, direction=1, durum="FIRST_TEST",
                  kalite=76.0, doluluk=0.20)],
        olaylar=[_olay_kaydi(tur="BOS", yon="ust", bar=171, seviye=39.10,
                             pivot_bar=161, kimlik=53, nitelik=79, yas=38,
                             kanit="direk içinde seri üst kırılım"),
                 _olay_kaydi(tur="CHOCH", yon="ust", bar=164, seviye=32.90,
                             pivot_bar=152, kimlik=48, nitelik=72, yas=45)],
        swingler=[_swing(rol="PROTECTED_HIGH", fiyat=39.90, bar=172),
                  _swing(rol="PROTECTED_LOW", fiyat=31.20, bar=90),
                  _swing(rol="WEAK_LOW", fiyat=32.40, bar=118)],
        seviyeler={"protected_high": 39.90, "protected_low": 31.20,
                   "weak_low": 32.40})
    return {"tf": tf, "cerceve": y.cerceve(zamanlar), "cift": cift,
            "sonuclar": sonuclar, "alarm_turu": "aday", "alarm_bar": 209,
            "etiket_detay": False, "simdi": _simdi(zamanlar, tf),
            "aciklama": "Aday kartı: direk FVG'si + kanal içi kritik seviye vurgusu"}


def _senaryo_flama_teyit():
    """Boğa Flaması · 4s · KIRILIM_TEYITLI — direk + küçük simetrik flama, teyitli."""
    n, tf = 170, "4h"
    zamanlar = _seans_etiketleri(n, tf, datetime(2026, 3, 2, 9, 30, tzinfo=IST))
    y = _Yapici(31)

    for i in range(60):     # bağlam 40 → 42
        kapanis = 40.0 + 2.0 * (i / 59) + 0.25 * math.sin(i / 7.0)
        y.mum(kapanis - 0.05, kapanis, 650_000 + 3_000 * i)
    for i in range(60, 75):  # direk 42 → 49
        pay = (i - 60) / 14
        kapanis = 42.0 + 7.0 * pay ** 0.9
        y.mum(kapanis - 0.28, kapanis, 1_400_000 + 3_800_000 * pay, fitil=0.18)
    for t in range(75, 111):  # flama: 48,30↔47,00'ten 47,44↔47,20'ye daralan
        ust = 48.30 - 0.024 * (t - 75)
        alt = 47.00 + 0.0055 * (t - 75)
        f = (math.sin((t - 75) * math.pi / 4.0) + 1.0) / 2.0
        kapanis = alt + (ust - alt) * (0.25 + 0.50 * f) \
            + (y._rastgele.random() - 0.5) * 0.07
        y.mum(kapanis - 0.04, kapanis, 800_000, fitil=0.12)
    ust_teyit = round(48.30 - 0.024 * 36, 2)             # 111. barda üst bant = 47,44
    teyit = round(ust_teyit + 0.85, 2)                   # 48,29 — bant üstü kapanış
    y.mum(teyit - 0.55, teyit, 3_900_000, fitil=0.20)    # 111 — teyit barı
    for i in range(112, n):                              # devam 48.3 → 49.3
        kapanis = teyit + 1.0 * ((i - 111) / (n - 111)) ** 0.85 + 0.08 * math.sin(i / 4.0)
        y.mum(kapanis - 0.08, kapanis, 1_900_000 - 6_000 * (i - 112))

    cift = {"pattern_name": "Boğa Flaması", "state": "KIRILIM_TEYITLI",
            "quality": 83.0, "contraction": 0.22, "start_bar": 75, "end_bar": 111,
            "apex_bar": 168, "upper_now": ust_teyit, "lower_now": 47.20,
            "hb1": 75, "hp1": 47.88, "hb2": 111, "hp2": ust_teyit,
            "lb1": 75, "lp1": 47.00, "lb2": 111, "lp2": 47.20,
            "upper_touches": 3, "lower_touches": 3, "break_price": ust_teyit,
            "candle_close_price": teyit, "break_dir": 1, "direction": 1,
            "progress": 0.74, "evidence_text": "flama 36 bar · teyit RVOL 3,1"}
    sonuclar = _sonuclar(
        ob=[_ob(110, 47.55, 48.25, bullish=True, skor=2.0)],
        fvg=[_fvg(110, 48.05, 48.70, direction=1, durum="ACTIVE", kalite=86.0),
             _fvg(96, 44.90, 45.60, direction=1, durum="PARTIAL_FILL",
                  kalite=69.0, doluluk=0.55)],
        olaylar=[_olay_kaydi(tur="BOS", yon="ust", bar=111, seviye=ust_teyit,
                             pivot_bar=95, kimlik=22, nitelik=81, yas=0,
                             kanit="kapanış 48,29 > 47,44")],
        swingler=[_swing(rol="PROTECTED_HIGH", fiyat=49.00, bar=74),
                  _swing(rol="PROTECTED_LOW", fiyat=41.60, bar=52)],
        seviyeler={"protected_high": 49.00, "protected_low": 41.60})
    return {"tf": tf, "cerceve": y.cerceve(zamanlar), "cift": cift,
            "sonuclar": sonuclar, "alarm_turu": "teyit", "alarm_bar": 111,
            "etiket_detay": False, "simdi": _simdi(zamanlar, tf),
            "aciklama": "Flama teyit kartı: direk kaynaklı FVG + teyit barı işaretli"}


def _senaryo_kama_hazirlik():
    """Yükselen Kama · 1g · KIRILIM_HAZIRLIGI — apex'e yaklaşan sıkışma (aday)."""
    n, tf = 130, "1d"
    zamanlar = _seans_etiketleri(n, tf, datetime(2026, 6, 1, 9, 30, tzinfo=IST))
    y = _Yapici(47)

    for i in range(60):     # bağlam 29 → 33
        kapanis = 29.0 + 4.0 * (i / 59) + 0.35 * math.sin(i / 6.0)
        y.mum(kapanis - 0.08, kapanis, 800_000 + 5_000 * i)
    for t in range(60, n):   # kama: alt bant hızlı, üst bant yavaş yükselir
        ust = 36.50 + 0.055 * (t - 60)
        alt = 30.50 + 0.1383 * (t - 60)
        f = (math.sin((t - 60) * math.pi / 6.0) + 1.0) / 2.0
        kapanis = alt + (ust - alt) * (0.30 + 0.42 * f) \
            + (y._rastgele.random() - 0.5) * 0.12
        fitil = 0.26 if f > 0.9 or f < 0.1 else 0.16
        y.mum(kapanis - 0.06, kapanis, 700_000, fitil=fitil)

    ust_simdi = round(36.50 + 0.055 * 69, 2)              # 40,30
    alt_simdi = round(30.50 + 0.1383 * 69, 2)             # 40,04
    cift = {"pattern_name": "Yükselen Kama", "state": "KIRILIM_HAZIRLIGI",
            "quality": 74.0, "contraction": 0.38, "start_bar": 60, "end_bar": 129,
            "apex_bar": 131, "upper_now": ust_simdi, "lower_now": alt_simdi,
            "hb1": 60, "hp1": 36.50, "hb2": 129, "hp2": ust_simdi,
            "lb1": 60, "lp1": 30.50, "lb2": 129, "lp2": alt_simdi,
            "upper_touches": 4, "lower_touches": 5,
            "critical_price_level": alt_simdi, "progress": 0.94,
            "evidence_text": "apex'e 2 bar · daralma %62"}
    sonuclar = _sonuclar(
        ob=[_ob(122, 40.60, 41.40, bullish=False, skor=2.0)],
        fvg=[_fvg(115, 40.45, 41.15, direction=-1, durum="ACTIVE", kalite=77.0)],
        olaylar=[_olay_kaydi(tur="BOS", yon="ust", bar=88, seviye=34.60,
                             pivot_bar=76, kimlik=17, nitelik=73, yas=41)],
        swingler=[_swing(rol="PROTECTED_LOW", fiyat=30.40, bar=66),
                  _swing(rol="WEAK_HIGH", fiyat=38.90, bar=104)])
    return {"tf": tf, "cerceve": y.cerceve(zamanlar), "cift": cift,
            "sonuclar": sonuclar, "alarm_turu": "aday", "alarm_bar": 129,
            "etiket_detay": False, "simdi": _simdi(zamanlar, tf),
            "aciklama": "Sıkışma/aday kartı: apex yakını, kritik seviye alt bantta"}


def _senaryo_ucgen_gecersiz():
    """Alçalan Üçgen · 1g · KIRILIM_GECERSIZLESTI — yalançı kırılım (sahte çıkış)."""
    n, tf = 150, "1d"
    zamanlar = _seans_etiketleri(n, tf, datetime(2026, 5, 4, 9, 30, tzinfo=IST))
    y = _Yapici(59)

    for i in range(75):     # bağlam 57 → 52 (düşüş)
        kapanis = 57.0 - 5.0 * (i / 74) + 0.45 * math.sin(i / 6.0)
        y.mum(kapanis - 0.10, kapanis, 1_100_000 + 5_000 * i)
    for t in range(75, 128):  # alçalan üçgen: taban düz 51, tavan düşen
        ust = 57.00 - 0.09 * (t - 75)
        alt = 51.00
        f = (math.sin((t - 75) * math.pi / 6.0) + 1.0) / 2.0
        kapanis = alt + (ust - alt) * (0.16 + 0.66 * f) \
            + (y._rastgele.random() - 0.5) * 0.14
        fitil = 0.24 if f > 0.9 or f < 0.1 else 0.16
        y.mum(kapanis - 0.07, kapanis, 850_000, fitil=fitil)
    ust_kirilim = round(57.00 - 0.09 * 53, 2)            # 128. barda üst bant = 52,23
    # 128 — teyit edilmiş gibi görünen kırılım…
    y.mum(ust_kirilim - 0.18, 52.62, 3_800_000, fitil=0.20)
    # 129..134 — …ama geri düşer: 3 ardışık kapanış bant altında → geçersizleşme
    for i, kapanis in enumerate((51.85, 51.40, 50.90, 50.35, 49.85, 49.40)):
        y.mum(kapanis + 0.25, kapanis, 2_400_000 + 320_000 * i, fitil=0.28)
    for i in range(135, n):  # kalan barlar: 49.4 → 48.6 sürüklenme
        kapanis = 49.40 - 0.80 * ((i - 134) / (n - 134)) - 0.10 * math.sin(i / 3.0)
        y.mum(kapanis + 0.15, kapanis, 1_300_000)

    cift = {"pattern_name": "Alçalan Üçgen", "state": "KIRILIM_GECERSIZLESTI",
            "quality": 71.0, "contraction": 0.31, "start_bar": 75, "end_bar": 128,
            "apex_bar": 147, "upper_now": ust_kirilim, "lower_now": 51.00,
            "hb1": 75, "hp1": 57.00, "hb2": 128, "hp2": ust_kirilim,
            "lb1": 75, "lp1": 51.00, "lb2": 128, "lp2": 51.00,
            "upper_touches": 4, "lower_touches": 5, "break_price": ust_kirilim,
            "candle_close_price": 52.62, "break_dir": 1,
            "evidence_text": "teyit sonrası 3 ardışık kapanış bant altında"}
    sonuclar = _sonuclar(
        ob=[_ob(127, 50.70, 51.55, bullish=True, skor=2.0, doluluk=1.0),
            _ob(80, 55.80, 56.70, bullish=False, skor=1.0, doluluk=0.80)],
        fvg=[_fvg(131, 50.20, 50.95, direction=-1, durum="ACTIVE", kalite=80.0)],
        olaylar=[_olay_kaydi(tur="CHOCH", yon="alt", bar=132, seviye=51.00,
                             pivot_bar=128, kimlik=64, nitelik=68, yas=17,
                             kanit="kapanış 50,90 < 51,00")],
        swingler=[_swing(rol="WEAK_HIGH", fiyat=52.62, bar=128)],
        dis_durum="STATE_BEARISH")
    return {"tf": tf, "cerceve": y.cerceve(zamanlar), "cift": cift,
            "sonuclar": sonuclar, "alarm_turu": "gecersiz", "alarm_bar": 132,
            "etiket_detay": True, "simdi": _simdi(zamanlar, tf),
            "aciklama": "Geçersizleşme kartı: yalançı kırılım, karşı delil vurgulu"}


def _senaryo_ucgen_retest():
    """Yükselen Üçgen · 4s · RETEST_BASARILI — kırılım sonrası banta dönüş tutundu."""
    n, tf = 180, "4h"
    zamanlar = _seans_etiketleri(n, tf, datetime(2026, 2, 2, 9, 30, tzinfo=IST))
    y = _Yapici(71)

    for i in range(80):     # bağlam 39 → 43
        kapanis = 39.0 + 4.0 * (i / 79) + 0.35 * math.sin(i / 7.0)
        y.mum(kapanis - 0.07, kapanis, 750_000 + 4_000 * i)
    for t in range(80, 150):  # yükselen üçgen: tavan düz 45,8; taban yükselen
        ust, alt = 45.80, 41.50 + 0.062 * (t - 80)
        f = (math.sin((t - 80) * math.pi / 6.0) + 1.0) / 2.0
        kapanis = alt + (ust - alt) * (0.18 + 0.64 * f) \
            + (y._rastgele.random() - 0.5) * 0.12
        fitil = 0.24 if f > 0.9 or f < 0.1 else 0.15
        y.mum(kapanis - 0.06, kapanis, 800_000, fitil=fitil)
    y.mum(45.35, 46.42, 3_400_000, fitil=0.20)            # 150 — teyitli kırılım
    for i, kapanis in enumerate((46.15, 46.30, 46.05, 45.95, 45.88, 45.92,
                                 45.85, 45.98)):            # 151..158 — ilerleme
        y.mum(kapanis - 0.18, kapanis, 1_700_000 - 90_000 * i)
    # 159..165 — banda DÖNÜŞ (retest): 46.02 → 45.86 teğet
    for i, kapanis in enumerate((46.02, 45.96, 45.90, 45.88, 45.86, 45.90, 45.95)):
        y.mum(kapanis + 0.12, kapanis, 1_150_000, fitil=0.30)
    y.mum(45.90, 46.14, 2_100_000, fitil=0.18)            # 166 — RETEST_BASARILI
    for i in range(167, n):                                # 167..179 — devam 46.1 → 47.0
        kapanis = 46.14 + 0.90 * ((i - 166) / (n - 166)) + 0.08 * math.sin(i / 3.4)
        y.mum(kapanis - 0.09, kapanis, 1_400_000)

    cift = {"pattern_name": "Yükselen Üçgen", "state": "RETEST_BASARILI",
            "quality": 85.0, "contraction": 0.29, "start_bar": 80, "end_bar": 150,
            "apex_bar": 165, "upper_now": 45.80, "lower_now": 45.42,
            "hb1": 80, "hp1": 45.80, "hb2": 150, "hp2": 45.80,
            "lb1": 80, "lp1": 41.50, "lb2": 150, "lp2": 45.84,
            "upper_touches": 5, "lower_touches": 4, "break_price": 45.80,
            "candle_close_price": 46.42, "break_dir": 1,
            "evidence_text": "retest kapanışı 46,14 > 45,80 · dip 45,86 tutundu"}
    sonuclar = _sonuclar(
        ob=[_ob(149, 45.30, 45.85, bullish=True, skor=2.0),
            _ob(96, 44.10, 44.85, bullish=True, skor=1.0, doluluk=0.65)],
        fvg=[_fvg(149, 45.92, 46.48, direction=1, durum="ACTIVE", kalite=82.0),
             _fvg(120, 43.30, 43.95, direction=1, durum="DEEP_TEST",
                  kalite=64.0, doluluk=0.80)],
        olaylar=[_olay_kaydi(tur="BOS", yon="ust", bar=150, seviye=45.80,
                             pivot_bar=138, kimlik=88, nitelik=84, yas=16,
                             kanit="kapanış 46,42 > 45,80"),
                 _olay_kaydi(tur="BOS", yon="ust", bar=118, seviye=44.20,
                             pivot_bar=104, kimlik=77, nitelik=71, yas=48)],
        swingler=[_swing(rol="PROTECTED_HIGH", fiyat=45.80, bar=136),
                  _swing(rol="PROTECTED_LOW", fiyat=41.40, bar=88),
                  _swing(rol="WEAK_LOW", fiyat=43.10, bar=116)],
        seviyeler={"protected_high": 45.80, "protected_low": 41.40,
                   "weak_low": 43.10})
    return {"tf": tf, "cerceve": y.cerceve(zamanlar), "cift": cift,
            "sonuclar": sonuclar, "alarm_turu": "retest", "alarm_bar": 166,
            "etiket_detay": False, "simdi": _simdi(zamanlar, tf),
            "aciklama": "Retest kartı: kırılım sonrası dönüş, FVG desteği görünür"}


# Katalog: anahtar → üretici. MANŞET: varsayılan ikili (kullanıcı isteği).
SENARYOLAR = {
    "ucgen_teyit": _senaryo_ucgen_teyit,
    "bayrak_aday": _senaryo_bayrak_aday,
    "flama_teyit": _senaryo_flama_teyit,
    "kama_hazirlik": _senaryo_kama_hazirlik,
    "ucgen_gecersiz": _senaryo_ucgen_gecersiz,
    "ucgen_retest": _senaryo_ucgen_retest,
}

MANSITLER = ("ucgen_teyit", "bayrak_aday")


# ---------------------------------------------------------------------- üretim

def _cikti_yolu(dizin: Path, ad: str, tf: str) -> Path:
    return dizin / f"ornek_{ad}_{TF_DOSYA[tf]}.png"


def kare_uret(ad: str, cikti: str | Path, *, mobil: bool = False,
              sade: bool = False, renk_korugu: bool = False) -> dict:
    """Tek senaryo karesi üretir: senaryo → anlik_goruntu → ciz → sonuç.

    Hata fırlatmaz; `{"yol": ..., "meta": ...}` döner, çizim reddedilirse
    `yol=None` + `meta["uyarilar"]` (grafik_uret.kare_uret sözleşmesiyle aynı).
    """
    if ad not in SENARYOLAR:
        return {"hata": f"bilinmeyen senaryo: {ad} (--liste ile kataloğu görün)"}
    yol = Path(cikti).expanduser().resolve()
    if "bot_data" in yol.parts:
        return {"hata": "sentetik çıktı bot_data içine yazılamaz (canlı önbellek)"}
    s = SENARYOLAR[ad]()
    goruntu = grafik.anlik_goruntu(
        s["cift"], s["tf"], s["cerceve"], sonuclar=s["sonuclar"],
        alarm_turu=s["alarm_turu"], alarm_bar=s["alarm_bar"], sembol="DEMO",
        simdi=s["simdi"], etiket_detay=s["etiket_detay"],
        veri_kaynagi="örnek galeri (sentetik veri)")
    secenekler: dict = {"cikti": str(yol)}
    if sade:
        secenekler["sade"] = True
    if renk_korugu:
        secenekler["renk_korugu"] = True
    if mobil:
        secenekler["mobil"] = True
    png, meta = grafik.ciz(goruntu, s["tf"], secenekler=secenekler)
    return {"yol": png, "meta": meta, "aciklama": s["aciklama"], "tf": s["tf"],
            "senaryo": ad, "hata": None}


def main(argv=None) -> int:
    ay = argparse.ArgumentParser(
        description="DEMO senaryo kataloğundan örnek alarm kartı karesi üretir "
                    "(sentetik veri, projenin kendi çizim zinciri).")
    ay.add_argument("--senaryo", default="manset",
                    help="senaryo adı, virgülle liste, 'manset' (varsayılan: "
                         + ", ".join(MANSITLER) + ") veya 'hepsi'")
    ay.add_argument("--cikti-dizin", default=str(VARSAYILAN_DIZIN),
                    help="PNG çıktı dizini (varsayılan: docs/ornek_galeri)")
    ay.add_argument("--mobil", action="store_true",
                    help="mobil boyut (780×1100, büyük yazı)")
    ay.add_argument("--sade", action="store_true",
                    help="sade görünüm (bölge/yapı katmanları kapalı)")
    ay.add_argument("--renk-korugu", action="store_true",
                    help="renk körlüğü dostu palet")
    ay.add_argument("--liste", action="store_true", help="senaryo kataloğunu listele")
    ay.add_argument("--json", action="store_true",
                    help="sonuç özetini JSON olarak da bas")
    sec = ay.parse_args(argv)

    if sec.liste:
        for ad, uretici in SENARYOLAR.items():
            isaret = " [manşet]" if ad in MANSITLER else ""
            print(f"{ad}{isaret} — {uretici().__doc__.strip().splitlines()[0]}")
        return 0

    if sec.senaryo == "hepsi":
        istek = list(SENARYOLAR)
    elif sec.senaryo == "manset":
        istek = list(MANSITLER)
    else:
        istek = [a.strip() for a in sec.senaryo.split(",") if a.strip()]
    bilinmeyen = [a for a in istek if a not in SENARYOLAR]
    if bilinmeyen:
        print(f"bilinmeyen senaryo: {', '.join(bilinmeyen)} — --liste ile kataloğu görün",
              file=sys.stderr)
        return 2

    dizin = Path(sec.cikti_dizin).expanduser().resolve()
    if "bot_data" in dizin.parts:
        print("bot_data içine sentetik çıktı yazılamaz (canlı önbellek)", file=sys.stderr)
        return 2
    dizin.mkdir(parents=True, exist_ok=True)

    ozet, kod = [], 0
    for ad in istek:
        yol = _cikti_yolu(dizin, ad, SENARYOLAR[ad]()["tf"])
        sonuc = kare_uret(ad, yol, mobil=sec.mobil, sade=sec.sade,
                          renk_korugu=sec.renk_korugu)
        if sonuc.get("hata") or not sonuc.get("yol"):
            kod = 1
            print(f"HATA {ad}: {sonuc.get('hata') or 'çizim reddedildi'} "
                  f"{sonuc.get('meta', {}).get('uyarilar', '')}", file=sys.stderr)
            continue
        meta = sonuc["meta"]
        print(f"kare: {sonuc['yol']}")
        print(f"  {sonuc['aciklama']}")
        print(f"  kadraj: {meta.get('mum_sayisi')} mum · "
              f"{meta.get('sure_ms')} ms · {meta.get('png_kb')} KB")
        zone = meta.get("zone") or {}
        print(f"  zone: {zone.get('cizilen') or 0} kutu çizildi"
              + (f" · {zone.get('sirala')}" if zone.get("sirala") else ""))
        olay = meta.get("olay") or {}
        if olay:
            print(f"  yapı: {olay.get('cizilen') or 0} dış öğe")
        uyarilar = meta.get("uyarilar") or []
        if uyarilar:
            print(f"  uyarılar: {'; '.join(str(u) for u in uyarilar)}")
        ozet.append({"senaryo": ad, "tf": sonuc["tf"], "yol": str(sonuc["yol"]),
                     "mum": meta.get("mum_sayisi"),
                     "zone": zone.get("cizilen") or 0,
                     "uyarilar": uyarilar})
    if sec.json:
        print(json.dumps(ozet, ensure_ascii=False, indent=2))
    return kod


if __name__ == "__main__":
    raise SystemExit(main())
