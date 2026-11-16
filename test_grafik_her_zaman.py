# -*- coding: utf-8 -*-
"""`/grafik` HER ZAMAN çalışmalı: seans başı, seans içi, gece, hafta sonu, tatil.

Kilitlenen sözleşme (2026-11-16):
  * Tazelik ölçütü "son kapanış kaç dakika önceydi" DEĞİL, "seans takvimine göre
    kapanmış olması gereken son mumun kaç dakika gerisindeyiz" (gecikme).
  * Böylece seansın ilk saatlerinde (dünün son mumu hâlâ en güncel kapanışken)
    ve günlük grafikte günün günlük mumu kapanmadan (18:30) veri "bayat"
    sayılmaz; sağlayıcı kapalı olsa bile cache'ten kare üretilir.
  * Gerçekten geride kalmış cache (birkaç seans eksik) HÂLÂ reddedilir.
  * Sağlayıcının geçici hatası (429/timeout/503) tek istekte pes etmez:
    sınırlı yeniden deneme vardır (yedek seriye geçiş YOK).
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import config
import data
import grafik
import main as M

IST = config.ISTANBUL_TZ


def _T(*args) -> datetime:
    return IST.localize(datetime(*args))


def _seri(son_gun, gun_sayisi: int = 10) -> pd.DataFrame:
    """BIST seans saatlerinde (09:30..17:30) 1H barlar; `son_gun` dahil."""
    parcalar = []
    gun = son_gun - timedelta(days=gun_sayisi - 1)
    while gun <= son_gun:
        if gun.weekday() < 5:
            idx = pd.date_range(f"{gun} 09:30", f"{gun} 17:30", freq="h", tz=IST)
            parcalar.append(pd.DataFrame(
                {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000.0},
                index=idx,
            ))
        gun += timedelta(days=1)
    return pd.concat(parcalar)


def _gunluk_seri(son_gun, gun_sayisi: int = 120) -> pd.DataFrame:
    gunler = [son_gun - timedelta(days=i) for i in range(gun_sayisi)][::-1]
    idx = pd.DatetimeIndex([IST.localize(datetime.combine(g, dt_time(18, 0))) for g in gunler])
    return pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000.0},
        index=idx,
    )


@pytest.fixture
def ortam(monkeypatch, tmp_path):
    """`/grafik` komut ortamı: dosya/PNG yakalanır, gerçek sağlayıcı yasak."""
    metinler, fotolar, threadler = [], [], []
    asil = threading.Thread

    class _Thread(asil):
        def __init__(self, *args, **kwargs):
            asil.__init__(self, *args, **kwargs)
            if kwargs.get("name") == "grafik-istegi":
                threadler.append(self)

    monkeypatch.setattr(M.threading, "Thread", _Thread)

    def _foto(yol, caption=""):
        assert Path(yol).exists()
        fotolar.append((yol, caption))
        return True, ""

    def _toplu(paketler):
        sonuc = []
        for yol, caption in paketler:
            ok, _ = notifier.grafik_dosya_gonder(yol, caption=caption)
            sonuc.append(bool(ok))
        return sonuc

    notifier = SimpleNamespace(
        enabled=True, token="test-secret",
        send_text=lambda m: (metinler.append(m) or True, ""),
        grafik_dosya_gonder=_foto, grafik_toplu_gonder=_toplu,
    )
    monkeypatch.setattr(M, "_notifier_ref", notifier)
    monkeypatch.setattr(M, "_deque_manager_ref", None)
    monkeypatch.setattr(grafik, "kare_yolu", lambda *a: str(tmp_path / "kare.png"))
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))

    def _yasak(*_a, **_k):
        pytest.fail("bu senaryoda gerçek sağlayıcıya çıkılmamalı")

    for mod in (data, M):
        monkeypatch.setattr(mod, "fetch_yfinance_1h", _yasak)
        monkeypatch.setattr(mod, "fetch_yfinance_1d", _yasak)
    monkeypatch.setattr(M, "fetch_yfinance_chart_data",
                        lambda *a, **k: (None, False, "testte sağlayıcı kapalı"))
    M._grafik_yenileme_durum.clear()
    yield tmp_path, metinler, fotolar, threadler
    M._grafik_yenileme_durum.clear()
    for t in threadler:
        t.join(20)
    M._grafik_aktif_is.clear()


def _cache_yaz(dizin: Path, hisse: str, df: pd.DataFrame, *, gunluk: bool = False) -> None:
    yonetici = data.StockDequeManager(data_dir=str(dizin))
    if gunluk:
        yonetici.append_gunluk_dataframe(hisse, df)
        yonetici.save_gunluk_to_disk(hisse, persist_remote=False)
    else:
        yonetici.append_dataframe(hisse, df)
        yonetici.save_to_disk(hisse, persist_remote=False)


def _saat_dondur(monkeypatch, an: datetime) -> None:
    class _DT(datetime):
        @classmethod
        def now(cls, tz=None):
            return an.astimezone(tz) if tz is not None else an.replace(tzinfo=None)

    monkeypatch.setattr(M, "datetime", _DT)


def _bitir(yanit, threadler):
    yanit.baslat()
    for t in threadler:
        t.join(30)
        assert not t.is_alive()


# --------------------------------------------------------------- birim kapı --
@pytest.mark.parametrize("tf", ["1h", "2h", "4h", "1d"])
def test_seans_ilk_dakikalarinda_veri_bayat_sayilmaz(tf):
    """Seans açıkken dünün son mumu en güncel kapanıştır: bayat DENMEZ."""
    son_cuma = IST.localize(datetime(2026, 11, 13))
    frame = _seri(son_cuma.date())
    simdi = _T(2026, 11, 16, 10, 5)          # Pazartesi, seans açık, ilk saat
    durum = M._grafik_cache_tazelik_durumu(frame, tf, simdi)
    assert durum["taze"] is True, durum["aciklama"]
    assert durum["yas_dk"] > 1000             # yaş hâlâ büyük; ölçüt gecikme
    assert durum["gecikme_dk"] is not None


def test_gercekten_geride_kalan_cache_hala_reddedilir():
    """İki seans eksik cache bayat SAYILMAYA devam eder (negatif kontrol)."""
    son_carsamba = IST.localize(datetime(2026, 11, 11))
    frame = _seri(son_carsamba.date())
    simdi = _T(2026, 11, 16, 12, 0)          # Pazartesi; Cuma ve Pazartesi eksik
    durum = M._grafik_cache_tazelik_durumu(frame, "1h", simdi)
    assert durum["taze"] is False
    assert "geride" in durum["aciklama"]


def test_beklenen_son_kapanis_takvimi_izler():
    """Hafta sonu/tatil beklenen kapanışı ileri taşımaz; yarım gün 13:00."""
    cuma = M.beklenen_son_kapanis_ani("1h", _T(2026, 11, 14, 14, 0))   # Cumartesi
    assert cuma == _T(2026, 11, 13, 18, 0)
    # 2026-10-29 Cumhuriyet Bayramı → o gün mum kapanışı beklenmez; arife günü
    # (2026-10-28) YARIM GÜN olduğu için seans 13:00'te biter.
    tatil = M.beklenen_son_kapanis_ani("1h", _T(2026, 10, 29, 15, 0))
    assert tatil == _T(2026, 10, 28, 13, 0)
    assert M.beklenen_son_kapanis_ani("4h", _T(2026, 10, 29, 15, 0)) == _T(2026, 10, 28, 13, 0)


# ------------------------------------------------------- uçtan uca /grafik --
def test_seans_basinda_saglayici_kapaliyken_cache_ten_kare_uretilir(ortam, monkeypatch):
    """10:05 Pazartesi + sağlayıcı kapalı + dünün cache'i → KARE üretilmeli."""
    dizin, metinler, fotolar, threadler = ortam
    _cache_yaz(dizin, "SEM", _seri(IST.localize(datetime(2026, 11, 13)).date()))
    _saat_dondur(monkeypatch, _T(2026, 11, 16, 10, 5))

    yanit = M._komut_grafik("SEM 1s sade")
    _bitir(yanit, threadler)

    assert fotolar, f"kare üretilmedi; metinler={metinler}"
    assert not any("veri yok" in m.lower() for m in metinler)


def test_gunluk_grafik_gun_icinde_calisir(ortam, monkeypatch):
    """1G: günün günlük mumu 18:30'da kapanır; gün içinde de kare üretilmeli."""
    dizin, metinler, fotolar, threadler = ortam
    _cache_yaz(dizin, "SEM", _seri(IST.localize(datetime(2026, 11, 13)).date()))
    _cache_yaz(dizin, "SEM", _gunluk_seri(IST.localize(datetime(2026, 11, 13)).date()), gunluk=True)
    _saat_dondur(monkeypatch, _T(2026, 11, 16, 12, 0))

    yanit = M._komut_grafik("SEM 1g sade")
    _bitir(yanit, threadler)

    assert fotolar, f"1g kare üretilmedi; metinler={metinler}"


def test_gecici_saglayici_hatasi_yeniden_denenir(monkeypatch, tmp_path):
    """429/timeout tek istekte pes etmez: aynı sembol sınırlı kez yeniden denenir."""
    monkeypatch.setattr(M.time, "sleep", lambda *_a, **_k: None)
    cagri = {"n": 0}
    # Sağlayıcı ikinci denemede GÜNCEL veri döndürür (Pazartesi 11:30'a kadar).
    gecerli = pd.concat([
        _seri(IST.localize(datetime(2026, 11, 13)).date()),
        pd.DataFrame(
            {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000.0},
            index=pd.date_range("2026-11-16 09:30", "2026-11-16 11:30", freq="h", tz=IST),
        ),
    ])

    def _fetch(*_a, **_k):
        cagri["n"] += 1
        if cagri["n"] == 1:
            return None, True, "429 Too Many Requests"
        return gecerli, False, ""

    monkeypatch.setattr(M, "fetch_yfinance_chart_data", _fetch)
    monkeypatch.setattr(M, "create_yahoo_pacer", lambda: SimpleNamespace(
        request=lambda *_a, **_k: __import__("contextlib").nullcontext()))

    class _Yonetici:
        def to_dataframe(self, _s):
            return None

        def append_dataframe(self, _s, _f):
            return True

        def save_to_disk(self, _s, **_k):
            return True

    sonuc = M._grafik_tazele("SEM", "1h", _Yonetici(), now=_T(2026, 11, 16, 12, 0))
    assert sonuc["ok"] is True, sonuc
    assert cagri["n"] == 2


def test_kalici_hatada_yeniden_deneme_sinirlidir(monkeypatch):
    """Geçici olmayan hata (sembol yok) yeniden denenmez."""
    cagri = {"n": 0}
    monkeypatch.setattr(M.time, "sleep", lambda *_a, **_k: None)

    def _fetch(*_a, **_k):
        cagri["n"] += 1
        return None, False, "possibly delisted"

    monkeypatch.setattr(M, "fetch_yfinance_chart_data", _fetch)
    monkeypatch.setattr(M, "create_yahoo_pacer", lambda: SimpleNamespace(
        request=lambda *_a, **_k: __import__("contextlib").nullcontext()))

    class _Yonetici:
        def to_dataframe(self, _s):
            return None

    sonuc = M._grafik_tazele("YOK", "1h", _Yonetici(), now=_T(2026, 11, 16, 12, 0))
    assert sonuc["ok"] is False
    assert cagri["n"] == 1
