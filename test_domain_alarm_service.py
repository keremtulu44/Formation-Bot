"""Yeni domain tetiklemeli kanal regresyonları (2026-11-03 kararı).

Eski formasyon/4S Stabil kartları ve replay çıktıları bu dosyada değiştirilmez;
testler yeni kanalın ayrı dispatch, native basamaklı destek, -3 ATR alt sınırı,
OR tetikleyiciler ve hacim veri kalitesi davranışını kilitler.
"""

from __future__ import annotations

import inspect
import re
import sys
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

import config
from notifier.util import TF_KISA, _KART_MAKS_SATIR, _px_butce
from telegram_measure import genislik
from bot.domain_alarm_service import (
    DomainAlarmCandidate,
    dispatch_domain_alarm_candidates,
    evaluate_domain_alarm_candidates,
    format_domain_alarm_card,
    format_domain_alarm_summary_card,
)

ISTANBUL_TZ = config.ISTANBUL_TZ
SIMDI = pd.Timestamp("2026-11-03 19:00", tz=ISTANBUL_TZ).to_pydatetime()


@pytest.fixture(autouse=True)
def _yeni_kanal_acik(monkeypatch):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_DM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_PUBLIC", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_DIST_ATR_ALT", -3.0)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_HACIM_5X", 5.0)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_HACIM_10X", 10.0)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_HACIM_SUPHE", 50.0)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_TAZE_DK", 10000)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_COOLDOWN_BAR", 6)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_TEKIL_UST_SINIR", 3)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_IMMEDIATE_TEKRAR", True)
    monkeypatch.setattr(config, "MAKRO_ALARM", False)
    monkeypatch.setattr(
        config, "ALERT_STATES",
        ("KIRILIM_TEYITLI", "RETEST_BASARILI", "KIRILIM_GECERSIZLESTI"),
    )


def _frame(close: float = 100.0) -> pd.DataFrame:
    index = pd.date_range(
        "2026-09-25 10:00", periods=40, freq="D", tz=ISTANBUL_TZ
    )
    return pd.DataFrame(
        {
            "open": [close - 1.0] * 40,
            "high": [close + 1.0] * 40,
            "low": [close - 2.0] * 40,
            "close": [close] * 40,
            "volume": [1000.0] * 40,
        },
        index=index,
    )


def _behavior(*, dist_atr: float, support: float, close: float = 100.0):
    return SimpleNamespace(
        dist_atr=dist_atr,
        support_level=support,
        close_price=close,
        pct_vs_support=(close - support) / support if support else 0.0,
        unchanged_days=30,
        touch_count=1,
        vol_ratio=1.2,
        reclaim_kind=None,
        momentum_kind=None,
        weak_reclaim=False,
        fixed_support=support,
        regime="LONG_HORIZONTAL",
    )


def _stabil(*, dist_atr: float, support: float, close: float = 100.0,
            relation: str = "destek üstünde"):
    bhv = _behavior(dist_atr=dist_atr, support=support, close=close)
    return SimpleNamespace(
        skipped=False,
        error=None,
        data_quality="OK",
        details={
            "latest_behavior": bhv,
            "latest_support_relation": relation,
            "bar_projection": [SimpleNamespace(support_level=support)],
        },
        result=None,
        export=None,
    )


def _bos_event(bar: int = 39) -> SimpleNamespace:
    return SimpleNamespace(
        event_uid="bos-1",
        scope="EXTERNAL",
        event_type="EVENT_BOS",
        event_bar=bar,
        broken_level=95.0,
        confirmation_status="CONFIRMED",
        validity="VALID",
        relevance="ACTIVE",
        is_active=True,
        direction=1,
    )


def _sonuclar(
    *,
    dist_atr: float = 1.0,
    support: float = 90.0,
    close: float = 100.0,
    relation: str = "destek üstünde",
    rvol: float = 1.0,
    bos: bool = False,
    ob_tepki: bool = False,
    fvg_reaksiyon: bool = False,
) -> dict:
    ms_events = [_bos_event()] if bos else []
    ob_bull = (
        SimpleNamespace(top=105.0, bottom=95.0, state=None)
        if ob_tepki else
        SimpleNamespace(top=120.0, bottom=115.0, state=None)
    )
    fvg_bull = (
        SimpleNamespace(top=110.0, bottom=90.0, state=8)
        if fvg_reaksiyon else
        SimpleNamespace(top=130.0, bottom=125.0, state=2)
    )
    return {
        "1d": {
            "stabil": _stabil(
                dist_atr=dist_atr, support=support, close=close, relation=relation
            ),
            "market_structure": SimpleNamespace(
                skipped=False,
                error=None,
                export=SimpleNamespace(events=ms_events),
            ),
            "volume_participation": SimpleNamespace(
                skipped=False,
                error=None,
                export=SimpleNamespace(rvol=rvol),
                details={
                    "latest_metrics": SimpleNamespace(volume_usable=True),
                },
            ),
            "order_block": SimpleNamespace(
                skipped=False,
                error=None,
                export=SimpleNamespace(
                    bull=ob_bull,
                    bear=SimpleNamespace(top=150.0, bottom=145.0, state=None),
                ),
            ),
            "fvg": SimpleNamespace(
                skipped=False,
                error=None,
                export=SimpleNamespace(
                    bull_fvg=fvg_bull,
                    bear_fvg=SimpleNamespace(
                        top=160.0, bottom=155.0, state=3
                    ),
                ),
            ),
        }
    }


def _aday(symbol: str = "ASTOR", **kwargs) -> DomainAlarmCandidate:
    return DomainAlarmCandidate(
        symbol=symbol,
        timeframe=kwargs.get("timeframe", "1d"),
        bar_open=kwargs.get("bar_open", "2026-11-03T10:00:00+03:00"),
        bar_close=kwargs.get("bar_close", "2026-11-03T18:30:00+03:00"),
        bar_label=kwargs.get("bar_label", "03.11 18:30"),
        bar_index=kwargs.get("bar_index", 39),
        close_price=kwargs.get("close_price", 100.0),
        support_level=kwargs.get("support_level", 90.0),
        dist_atr=kwargs.get("dist_atr", 1.0),
        relation=kwargs.get("relation", "destek üstünde"),
        reasons=kwargs.get("reasons", ("BOS ↑", "hacim 5× (6,0×)")),
        volume_rvol=kwargs.get("volume_rvol", 6.0),
        volume_tier=kwargs.get("volume_tier", "5×"),
        volume_source=kwargs.get("volume_source", "motor"),
        data_quality=kwargs.get("data_quality", "OK"),
        card_lines=kwargs.get("card_lines", ("Stabil destek: 90,00",)),
        rank_score=kwargs.get("rank_score", 4.0),
        grafik_verisi=kwargs.get("grafik_verisi"),
        grafik_verisi_public=kwargs.get("grafik_verisi_public"),
    )


class _Notifier:
    def __init__(self):
        self.enabled = True
        self.public_enabled = True
        self.dm: list[str] = []
        self.public: list[str] = []
        self.grafik_kuyruk: list = []
        self.public_grafik: list = []

    def send_text(self, text: str):
        self.dm.append(text)
        return True

    def send_to_public(self, text: str):
        self.public.append(text)
        return True

    def grafik_kuyruga_ekle(self, data, *, gonder=False):
        self.grafik_kuyruk.append((data, gonder))
        return len((data.get("grafik_verisi") or {}).get("goruntular") or [])

    def public_grafik_bagla(self, kayit, veri):
        self.public_grafik.append((kayit, veri))
        return len(veri.get("goruntular") or [])


def _degerlendir(results: dict, **kwargs) -> list[DomainAlarmCandidate]:
    frame = _frame(close=kwargs.pop("close", 100.0))
    return evaluate_domain_alarm_candidates(
        "ASTOR",
        {"1d": frame},
        {"1d": frame},
        results,
        SIMDI,
        bar_metni_fn=lambda tf, acilis, kapanis: "03.11 18:30",
        **kwargs,
    )


# 1) HARD alt sınır: -3 ATR'nin ALTINA inilmesin; üst serbest.
def test_dist_atr_alt_sinir_hard_ust_serbest():
    asagi = _degerlendir(_sonuclar(dist_atr=-3.1, rvol=6.0))
    assert asagi == []

    yukari = _degerlendir(_sonuclar(dist_atr=5.0, rvol=6.0))
    assert len(yukari) == 1
    assert yukari[0].dist_atr == 5.0
    kart = format_domain_alarm_card(yukari[0])
    assert "Koşul:" not in kart
    assert "üst sınır yok" not in kart


# 2) Native basamaklı destek: tetik anındaki güncel seviye/ilişki okunur.
def test_tetik_anindaki_native_basamakli_destek_ve_iliski():
    birinci = _degerlendir(
        _sonuclar(dist_atr=1.0, support=90.0, relation="destek üstünde", rvol=6.0)
    )[0]
    ikinci = _degerlendir(
        _sonuclar(dist_atr=-0.5, support=94.0, relation="destekte", rvol=6.0)
    )[0]

    assert birinci.support_level == 90.0
    assert birinci.relation == "destek üstünde"
    assert "90,00" in " ".join(birinci.card_lines)

    assert ikinci.support_level == 94.0
    assert ikinci.relation == "destekte"
    assert "94,00" in " ".join(ikinci.card_lines)
    assert ikinci.dist_atr >= -3.0  # üst sınır olmadan sığ sarkma da geçer


# 3) Hacim hard AND değil; kendi başına bildirim üretir.
def test_hacim_kendi_basina_tetikler_domain_sarti_yok():
    cands = _degerlendir(_sonuclar(dist_atr=0.5, rvol=6.0))
    assert len(cands) == 1
    assert cands[0].volume_tier == "5×"
    assert any("hacim 5×" in r for r in cands[0].reasons)
    assert not any("BOS" in r for r in cands[0].reasons)


# 4) Aynı barda iki sebep -> tek kart, iki sebep; DM + public aynı yeni kart.
def test_ayni_bar_iki_sebep_tek_kart_iki_kanal(tmp_path):
    cands = _degerlendir(_sonuclar(dist_atr=1.0, rvol=6.0, bos=True))
    assert len(cands) == 1
    assert any("BOS" in r for r in cands[0].reasons)
    assert any("hacim 5×" in r for r in cands[0].reasons)

    notifier = _Notifier()
    ozet = dispatch_domain_alarm_candidates(
        cands, notifier, state_path=str(tmp_path / "yeni.json")
    )
    assert ozet["tekil_gonderilen"] == 1
    assert len(notifier.dm) == 1
    assert len(notifier.public) == 1
    kart = format_domain_alarm_card(cands[0])
    assert "🆕 YENİ" in kart
    assert "BOS" in kart and "hacim 5×" in kart
    assert notifier.dm[0] == notifier.public[0]
    assert not notifier.grafik_kuyruk
    assert not notifier.public_grafik


def test_ayni_bar_ve_cooldown_tekrar_bastirilir(tmp_path):
    cand = _aday()
    notifier = _Notifier()
    state_path = str(tmp_path / "yeni.json")

    birinci = dispatch_domain_alarm_candidates([cand], notifier, state_path=state_path)
    ikinci = dispatch_domain_alarm_candidates([cand], notifier, state_path=state_path)

    assert birinci["tekil_gonderilen"] == 1
    assert ikinci["tekil_gonderilen"] == 0
    assert ikinci["filtrelendi"] == 1
    assert len(notifier.dm) == 1 and len(notifier.public) == 1


# 5) Formasyon OR kaynağı; anlık push state'i de yeni karta dahil, eski alarm korunur.
def test_formasyon_dahil_anlik_state_tekrar_acik():
    kayitlar = [
        {
            "timeframe": "1d",
            "pattern_name": "Yükselen Üçgen",
            "state": "SIKISMA_GUCLENIYOR",
            "notification_state": "SIKISMA_GUCLENIYOR",
            "quality": 80.0,
            "min_quality": 60.0,
        },
        {
            "timeframe": "1d",
            "pattern_name": "Kama",
            "state": "KIRILIM_TEYITLI",
            "notification_state": "KIRILIM_TEYITLI",
            "quality": 90.0,
            "min_quality": 60.0,
        },
    ]
    cands = _degerlendir(
        _sonuclar(dist_atr=1.0, rvol=6.0),
        formasyon_kayitlari=kayitlar,
    )
    assert len(cands) == 1
    sebep_metni = " | ".join(cands[0].reasons)
    assert "formasyon: Yükselen Üçgen" in sebep_metni
    assert "formasyon: Kama" in sebep_metni


def test_immediate_tekrar_operatörce_kapatilabilir(monkeypatch):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_IMMEDIATE_TEKRAR", False)
    kayitlar = [
        {
            "timeframe": "1d",
            "pattern_name": "Yükselen Üçgen",
            "state": "SIKISMA_GUCLENIYOR",
            "notification_state": "SIKISMA_GUCLENIYOR",
            "quality": 80.0,
            "min_quality": 60.0,
        },
        {
            "timeframe": "1d",
            "pattern_name": "Kama",
            "state": "KIRILIM_TEYITLI",
            "notification_state": "KIRILIM_TEYITLI",
            "quality": 90.0,
            "min_quality": 60.0,
        },
    ]
    cands = _degerlendir(
        _sonuclar(dist_atr=1.0, rvol=6.0),
        formasyon_kayitlari=kayitlar,
    )
    assert len(cands) == 1
    sebep_metni = " | ".join(cands[0].reasons)
    assert "formasyon: Yükselen Üçgen" in sebep_metni
    assert "Kama" not in sebep_metni


# 6) OB/FVG tepkisi OR kaynağı.
def test_ob_ve_fvg_tepkisi_ayri_sebep_olur():
    cands = _degerlendir(
        _sonuclar(dist_atr=2.0, rvol=1.0, ob_tepki=True, fvg_reaksiyon=True)
    )
    assert len(cands) == 1
    sebep_metni = " | ".join(cands[0].reasons)
    assert "OB boğa bölge tepkisi" in sebep_metni
    assert "FVG boğa reaksiyon" in sebep_metni


# 7) >=10x uç hacim: istisna + veri kalitesi/UNKNOWN kontrolü.
def test_10x_hacim_veri_kalitesi_kontrolu():
    cands = _degerlendir(_sonuclar(dist_atr=1.0, rvol=100.0))
    assert len(cands) == 1
    assert cands[0].volume_tier == "10×"
    assert cands[0].data_quality == "VERI_SUPHE"
    kart = format_domain_alarm_card(cands[0])
    kart_tek_satir = re.sub(r"\s+", " ", kart)
    assert "10×" in kart
    assert "veri kalitesi kontrolü gerekli" in kart_tek_satir


# 8) Burst: >3 aday -> 2 tekil + 1 toplu özet, hepsi state'e işaretli.
def test_burst_iki_tekil_bir_toplu_ozet(tmp_path):
    cands = [
        _aday(symbol="ASELS", rank_score=5.0),
        _aday(symbol="ASTOR", rank_score=4.0),
        _aday(symbol="BIMAS", rank_score=3.0),
        _aday(symbol="THYAO", rank_score=2.0),
    ]
    notifier = _Notifier()
    state_path = str(tmp_path / "yeni.json")
    ozet = dispatch_domain_alarm_candidates(cands, notifier, state_path=state_path)

    assert ozet["tekil_gonderilen"] == 2
    assert ozet["toplu_ozet"] == 1
    assert len(notifier.dm) == 3
    assert len(notifier.public) == 3
    assert "DOMAİN TOPLU ÖZET" in notifier.dm[-1]
    assert "🆕 YENİ" in format_domain_alarm_summary_card(cands[2:])

    import json
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)
    assert len(state["slots"]) == 4


# 9) Eski formasyon/4S kart metinlerine yeni işaret sızmaz.
def test_eski_kart_metinleri_degismedi():
    from bot import stabil_service
    from notifier.api import TelegramNotifier

    assert "🆕 YENİ" not in inspect.getsource(
        stabil_service.format_stabil_reclaim_alert_card
    )
    assert "🆕 YENİ" not in inspect.getsource(
        TelegramNotifier.format_public_tekil
    )


# 10) Yeni kart, eski sade kartın blok dili / piksel bütçesi / yasal satırı.
def test_yeni_kart_eski_kart_blok_dili_ve_satir_butcesi():
    kart = format_domain_alarm_card(_aday())
    satirlar = [l for l in kart.splitlines() if l.strip()]
    assert "\n\n" in kart
    assert satirlar[-1] == "• yatırım tavsiyesi değildir"
    assert TF_KISA["1d"] in kart
    assert "🕒" in kart
    assert "Koşul:" not in kart
    assert "üst sınır yok" not in kart
    assert "DOMAİN TETİKLEME" not in kart
    assert "Sebep:" not in kart
    assert all(genislik(l) <= _px_butce() for l in satirlar)
    assert len(satirlar) <= _KART_MAKS_SATIR


# 11) Grafik ayrı bir yoldan üretilmez: aynı kare_listesi + aynı bağlam.
def test_grafik_eski_alarm_kare_listesi_baglami_ile_uretilir(monkeypatch):
    cagrilar = []

    def kare_listesi(cift, tf, cerceve, **kwargs):
        cagrilar.append((cift, tf, cerceve, kwargs))
        adet = int(kwargs.get("adet") or 1)
        return {
            "sembol": "ASTOR",
            "goruntular": [{"tf": tf, "goruntu": {}} for _ in range(adet)],
            "kota": 0,
            "uyarilar": [],
        }

    fake = SimpleNamespace(
        grafik_aktif_mi=lambda: True,
        alarm_turu_bul=lambda state: "teyit" if state == "KIRILIM_TEYITLI" else None,
        kare_listesi=kare_listesi,
    )
    monkeypatch.setitem(sys.modules, "grafik", fake)

    frame = _frame()
    frame_4h = _frame()
    results = _sonuclar(dist_atr=1.0, rvol=6.0, bos=True)
    active = SimpleNamespace(pattern_name="Yükselen Üçgen")
    cands = evaluate_domain_alarm_candidates(
        "ASTOR",
        {"1d": frame, "4h": frame_4h},
        {"1d": frame, "4h": frame_4h},
        results,
        SIMDI,
        bar_metni_fn=lambda tf, acilis, kapanis: "03.11 18:30",
        grafik_baglami={
            "1d": {
                "cift": active,
                "state": "KIRILIM_TEYITLI",
                "alarm_bar": 39,
            }
        },
    )
    assert len(cands) == 1
    assert cands[0].grafik_verisi is not None
    assert cands[0].grafik_verisi_public is not None
    assert len(cagrilar) == 2
    assert cagrilar[0][0] is active
    assert cagrilar[0][1] == "1d"
    assert cagrilar[0][3]["sonuclar"] is results
    assert cagrilar[0][3]["alarm_turu"] == "teyit"
    assert cagrilar[0][3]["alarm_bar"] == 39
    assert "4h" in cagrilar[0][3]["ek_cerceveler"]
    assert cagrilar[1][3]["adet"] == 2
    assert cands[0].grafik_verisi_public["goruntular"][1]["rol"] == "alt"


# 12) Tekil kartın DM + public kareleri aynı payload ile eski teslim yollarına gider.
def test_yeni_kart_grafikleri_ayni_payload_ile_gider(tmp_path):
    dm_veri = {
        "sembol": "ASTOR",
        "goruntular": [{"tf": "1d", "goruntu": {}}],
    }
    pub_veri = {
        "sembol": "ASTOR",
        "goruntular": [
            {"tf": "1d", "goruntu": {}},
            {"tf": "4h", "goruntu": {}, "rol": "alt"},
        ],
    }
    cand = _aday(grafik_verisi=dm_veri, grafik_verisi_public=pub_veri)
    notifier = _Notifier()
    ozet = dispatch_domain_alarm_candidates(
        [cand], notifier, state_path=str(tmp_path / "yeni.json")
    )
    assert ozet["tekil_gonderilen"] == 1
    assert len(notifier.grafik_kuyruk) == 1
    assert len(notifier.public_grafik) == 1
    assert notifier.grafik_kuyruk[0][0]["grafik_verisi"] is dm_veri
    assert notifier.grafik_kuyruk[0][1] is True
    assert notifier.grafik_kuyruk[0][0]["state"] == "YENI_DOMAIN"
    assert notifier.public_grafik[0][1] is pub_veri
    assert notifier.public_grafik[0][0]["pattern_name"] == "DOMAİN TETİKLEME"
