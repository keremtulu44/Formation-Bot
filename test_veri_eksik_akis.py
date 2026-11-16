# -*- coding: utf-8 -*-
"""Veri çekme hattında "eksik çekilip geçilme" sözleşmeleri (2026-11-16).

Kapsam:
 1. `seans_ici_bosluk_sayisi`: aynı seans içindeki eksik 1H mumlarını sayar,
    gece/hafta sonu aralıklarını saymaz.
 2. Boşluk tamiri: cache'te seans içi delik varken tarama rutin 5 günlük
    pencereyle YETİNMEZ, tam pencere (60d) ister; soğuma sonrası tekrar dener.
 3. Sağlayıcı yanıtı OHLCV doğrulamasında reddedilirse cache güncellenmez ve
    bu "taze veri" sayılmaz (sessiz geçilme yok).
 4. Günlük (1D) append reddedilirse "günlük veri tazelendi" YAZILMAZ.
 5. Sağlayıcı çıkışında elenen satırlar `attrs` ile görünür olur.
"""
from __future__ import annotations

import copy
from contextlib import nullcontext
from datetime import datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

import bot.scan as scan_module
import config
import main as main_module
from data import (
    BOSLUK_TAMIR_TEKRAR_DK,
    FULL_1H_FETCH_PERIOD,
    ROUTINE_1H_FETCH_PERIOD,
    StockDequeManager,
    seans_ici_bosluk_sayisi,
)
from data.fetch import _saglayici_ohlcv_temizle

IST = config.ISTANBUL_TZ


# ------------------------------------------------------------------ yardımcı -
def _seri(baslangic: str, adet: int, *, atla=(), base: float = 100.0) -> pd.DataFrame:
    """1H OHLCV serisi; `atla` indeksleri atlanır (kasıtlı seans içi boşluk)."""
    simdi = pd.Timestamp(baslangic, tz=IST)
    satirlar = []
    for i in range(adet):
        if i in set(atla):
            continue
        ts = simdi + pd.Timedelta(hours=i)
        satirlar.append(
            {
                "open": base,
                "high": base + 1.0,
                "low": base - 1.0,
                "close": base + 0.5,
                "volume": 1000.0,
            }
        )
        satirlar[-1]["ts"] = ts
    df = pd.DataFrame(satirlar).set_index("ts")
    return df[["open", "high", "low", "close", "volume"]]


def _cok_gunlu_seri(gun_sayisi: int = 15, *, bosluk_gun_once: int | None = None,
                    simdi: datetime | None = None, base: float = 100.0) -> pd.DataFrame:
    """Son barı `simdi - 1 saat` olan, seans saatlerine (10:00-18:00) oturan seri.

    `bosluk_gun_once` verilirse o günün 13:00-15:00 mumları atlanır (aynı seans
    içi delik); böylece rutin 5 günlük pencerenin DIŞINDA kalan boşluk modellenir.
    """
    simdi = simdi or datetime.now(IST)
    bugun = pd.Timestamp(simdi).normalize()
    parcalar = []
    for geri in range(gun_sayisi, 0, -1):
        gun = bugun - pd.Timedelta(days=geri)
        atla = {3, 4} if bosluk_gun_once is not None and geri == bosluk_gun_once else set()
        parcalar.append(_seri(f"{gun.date()} 10:00", 9, atla=atla, base=base))
    # Bugün: seans içindeki kapanmış mumlar (10:00'dan itibaren, gelecek yok)
    bugun_parca = _seri(f"{bugun.date()} 10:00", 9, base=base)
    bugun_parca = bugun_parca[bugun_parca.index < pd.Timestamp(simdi)]
    parcalar.append(bugun_parca[bugun_parca.index >= bugun + pd.Timedelta(hours=10)])
    return pd.concat(parcalar)


def _bozuk_seri(baslangic: str, adet: int, *, base: float = 100.0) -> pd.DataFrame:
    """OHLCV sözleşmesini ihlal eden (high < low) satır içeren seri."""
    df = _seri(baslangic, adet, base=base)
    df.iloc[-1, df.columns.get_loc("high")] = 1.0   # high < low -> append reddeder
    return df


class _Pacer:
    def request(self, _label):
        return nullcontext()

    def reset_batch(self):
        return None


class _LiveState:
    def __init__(self):
        self.status_cagrilari = []

    def begin_scan(self, *_a, **_k):
        return None

    def update_scan_progress(self, *_a, **_k):
        return None

    def record_formation(self, *_a, **_k):
        return None

    def mark_alert_sent(self, *_a, **_k):
        return None

    def finish_scan(self, *_a, **k):
        self.status_cagrilari.append(("finish", k))

    def fail_scan(self, message, *_a, **k):
        self.status_cagrilari.append(("fail", message))

    def status(self):
        return {}


class _Deferred:
    def observe(self, *_a, **_k):
        return None

    def snapshot(self, *_a, **_k):
        return {}


class _Notifier:
    def send(self, *_a, **_k):
        return True

    def send_to_public(self, *_a, **_k):
        return True

    def persist_watch_state(self, *_a, **_k):
        return True

    def stabil_bekleyen_iptal(self, *_a, **_k):
        return True

    def public_bosalt(self):
        return None


class _Lifecycle:
    def scan(self, key, _frame, *, tam_yeniden):
        return SimpleNamespace(state="ST_NONE", break_dir=None, log="", active=None)


def _tarama_kur(monkeypatch, tmp_path, *, fetch_frames, daily_frame=None, now=None):
    """scan_all_stocks için asgari sahte ortam; `fetch_1h_stocks_paced` yakalanır."""
    now = now or datetime.now(IST)

    class _DT(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz is not None else now.replace(tzinfo=None)

    cagrilar = {"periods": None}

    def sahte_fetch(stocks, _pacer, _phase, periods=None):
        cagrilar["periods"] = dict(periods or {})
        return (
            {s: fetch_frames[s] for s in stocks if s in fetch_frames},
            {s: "sahte hata" for s in stocks if s not in fetch_frames},
            0,
            0,
        )

    monkeypatch.setattr(main_module, "datetime", _DT)
    monkeypatch.setattr(main_module, "daily_stats", copy.deepcopy(main_module.daily_stats))
    monkeypatch.setattr(main_module, "last_run_stats", {})
    monkeypatch.setattr(main_module, "_live_state", _LiveState())
    monkeypatch.setattr(main_module, "_deferred_alert_buffer", _Deferred())
    monkeypatch.setattr(main_module, "_supabase_store_ref", None)
    monkeypatch.setattr(main_module, "_deque_manager_ref", None)
    monkeypatch.setattr(main_module, "_shutdown_requested", False)
    monkeypatch.setattr(main_module, "reset_daily_if_needed", lambda: None)
    monkeypatch.setattr(main_module, "create_yahoo_pacer", lambda: _Pacer())
    monkeypatch.setattr(main_module, "fetch_1h_stocks_paced", sahte_fetch)
    # bot/scan.py 1D fonksiyonu `_pkg.` üzerinden DEĞİL, kendi bağlı adıyla
    # çağırıyor; testte ağa çıkılmaması için iki yüzey birlikte yamalanmalı.
    monkeypatch.setattr(main_module, "fetch_yfinance_1d", lambda *_a, **_k: daily_frame)
    monkeypatch.setattr(scan_module, "fetch_yfinance_1d", lambda *_a, **_k: daily_frame)
    monkeypatch.setattr(main_module, "write_heartbeat", lambda **_k: None)
    monkeypatch.setattr(main_module, "son_tarama_kaydet", lambda: None)
    monkeypatch.setattr(main_module, "_load_domain_runner", lambda: None)
    monkeypatch.setattr(main_module, "tamamlanmis_mumlar", lambda frame, _tf: frame)
    return cagrilar


# -------------------------------------------------------------------- birim --
def test_seans_ici_bosluk_temiz_seride_yok():
    df = _seri("2026-11-03 10:00", 9)
    assert seans_ici_bosluk_sayisi(df) == 0


def test_seans_ici_bosluk_eksik_mumda_sayilir():
    # 10:00-12:00 arası bir mum eksik (2 saatlik aynı-gün aralığı)
    df = _seri("2026-11-03 10:00", 9, atla=(2,))
    assert seans_ici_bosluk_sayisi(df) == 1


def test_seans_ici_bosluk_gece_ve_hafta_sonunu_saymaz():
    cuma = _seri("2026-11-06 10:00", 9)          # Cuma 10:00-18:00
    pazartesi = _seri("2026-11-09 10:00", 9)     # Pazartesi 10:00-18:00
    birlesik = pd.concat([cuma, pazartesi])
    assert seans_ici_bosluk_sayisi(birlesik) == 0


def test_seans_ici_bosluk_bos_ve_kisa_seride_sifir():
    assert seans_ici_bosluk_sayisi(None) == 0
    assert seans_ici_bosluk_sayisi(_seri("2026-11-03 10:00", 2)) == 0
    assert seans_ici_bosluk_sayisi(pd.DataFrame()) == 0


def test_bosluk_tamir_sogumasi(tmp_path):
    mgr = StockDequeManager(data_dir=str(tmp_path))
    simdi = IST.localize(datetime(2026, 11, 3, 12, 0))

    assert mgr.bosluk_tamir_uygun_mu("THYAO", simdi) is True
    mgr.bosluk_tamir_kaydet("THYAO", simdi)
    assert mgr.bosluk_tamir_uygun_mu("THYAO", simdi + timedelta(minutes=30)) is False
    assert mgr.bosluk_tamir_uygun_mu(
        "THYAO", simdi + timedelta(minutes=BOSLUK_TAMIR_TEKRAR_DK + 1)
    ) is True


def test_saglayici_temizleme_elenen_satirlari_bildirir():
    idx = pd.date_range("2026-09-01", periods=6, freq="D", tz=IST)
    df = pd.DataFrame(
        {
            "open": [10.0] * 6,
            "high": [11.0] * 6,
            "low": [9.0] * 6,
            "close": [10.0] * 6,
            "volume": [100.0] * 6,
        },
        index=idx,
    )
    df.iloc[1, df.columns.get_loc("close")] = float("nan")     # bozuk satır
    df.iloc[3, :] = [10.0, 10.0, 10.0, 10.0, 0.0]              # hayalet tatil günü

    temiz = _saglayici_ohlcv_temizle(df, stock="THYAO", timeframe="1d")

    assert temiz is not None
    assert temiz.attrs["ham_satir"] == 6
    assert temiz.attrs["reddedilen_satir"] == 2
    assert temiz.attrs["hayalet_satir"] == 1
    assert len(temiz) == 4


# ------------------------------------------------------------------- tarama --
def test_cache_boslugu_tam_pencereyle_tamir_ister(tmp_path, monkeypatch):
    """Seans içi delik varken rutin 5d YETMEZ: tam pencere istenir ve onarır."""
    simdi = datetime.now(IST).replace(minute=5, second=0, microsecond=0)
    cache = _cok_gunlu_seri(15, bosluk_gun_once=10, simdi=simdi)
    assert seans_ici_bosluk_sayisi(cache) == 1
    assert len(cache) >= 50

    mgr = StockDequeManager(data_dir=str(tmp_path))
    mgr.append_dataframe("THYAO", cache)
    assert any(x["tip"] == "bosluk" for x in mgr.sureklilik_sorunlari.get("THYAO", []))

    # Gerçek 60d yanıtı deliği de içerir: eksik iki mum taze yanıtta bulunur.
    taze = _cok_gunlu_seri(15, simdi=simdi)

    cagrilar = _tarama_kur(monkeypatch, tmp_path, fetch_frames={"THYAO": taze}, now=simdi)
    main_module.scan_all_stocks(
        mgr, _Lifecycle(), _Notifier(), stocks=["THYAO"], send_alerts=False
    )

    assert cagrilar["periods"]["THYAO"] == FULL_1H_FETCH_PERIOD
    assert main_module.daily_stats["bosluk_tamir_fetch"] == 1
    assert seans_ici_bosluk_sayisi(mgr.to_dataframe("THYAO")) == 0
    assert not any(x["tip"] == "bosluk" for x in mgr.sureklilik_sorunlari.get("THYAO", []))

    # Onarımdan sonra ikinci tur yine rutin pencereye döner (gereksiz 60d yok).
    main_module.scan_all_stocks(
        mgr, _Lifecycle(), _Notifier(), stocks=["THYAO"], send_alerts=False
    )
    assert cagrilar["periods"]["THYAO"] == ROUTINE_1H_FETCH_PERIOD


def test_kalici_delikte_tamir_sogumaya_girer(tmp_path, monkeypatch):
    """Sağlayıcı deliği kapatamıyorsa her turda 60d indirilmez (soğuma)."""
    simdi = datetime.now(IST).replace(minute=5, second=0, microsecond=0)
    cache = _cok_gunlu_seri(15, bosluk_gun_once=10, simdi=simdi)
    mgr = StockDequeManager(data_dir=str(tmp_path))
    mgr.append_dataframe("THYAO", cache)

    # Sağlayıcı deliği İÇERMEYEN taze yanıt döndürüyor (kalıcı veri deliği).
    taze = _seri((simdi - pd.Timedelta(hours=3)).strftime("%Y-%m-%d %H:%M"), 1)
    cagrilar = _tarama_kur(monkeypatch, tmp_path, fetch_frames={"THYAO": taze}, now=simdi)

    main_module.scan_all_stocks(
        mgr, _Lifecycle(), _Notifier(), stocks=["THYAO"], send_alerts=False
    )
    assert cagrilar["periods"]["THYAO"] == FULL_1H_FETCH_PERIOD
    assert seans_ici_bosluk_sayisi(mgr.to_dataframe("THYAO")) == 1

    main_module.scan_all_stocks(
        mgr, _Lifecycle(), _Notifier(), stocks=["THYAO"], send_alerts=False
    )
    assert cagrilar["periods"]["THYAO"] == ROUTINE_1H_FETCH_PERIOD
    assert main_module.daily_stats["bosluk_tamir_fetch"] == 1


def test_bosluklu_analiz_uyari_ve_sayac(tmp_path, monkeypatch, caplog):
    """Delik kapatılamadıysa analiz sessizce sürmez: uyarı + sayaç."""
    simdi = datetime.now(IST).replace(minute=5, second=0, microsecond=0)
    cache = _cok_gunlu_seri(15, bosluk_gun_once=10, simdi=simdi)
    mgr = StockDequeManager(data_dir=str(tmp_path))
    mgr.append_dataframe("THYAO", cache)
    mgr.bosluk_tamir_kaydet("THYAO", simdi)          # tamir soğumada
    monkeypatch.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_a, **_k: False)

    _tarama_kur(
        monkeypatch,
        tmp_path,
        fetch_frames={"THYAO": _seri((simdi - pd.Timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"), 1)},
        now=simdi,
    )
    caplog.set_level("DEBUG")
    main_module.scan_all_stocks(
        mgr, _Lifecycle(), _Notifier(), stocks=["THYAO"], send_alerts=False
    )

    assert "seans içi boşluk" in caplog.text
    assert main_module.daily_stats["bosluklu_analiz"] >= 1


def test_reddedilen_1h_append_taze_veri_sayilmaz(tmp_path, monkeypatch, caplog):
    simdi = datetime.now(IST).replace(minute=5, second=0, microsecond=0)
    mgr = StockDequeManager(data_dir=str(tmp_path))
    mgr.append_dataframe("THYAO", _cok_gunlu_seri(15, simdi=simdi))
    onceki_bar = len(mgr.to_dataframe("THYAO"))

    bozuk = _bozuk_seri((simdi - pd.Timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"), 2)
    _tarama_kur(monkeypatch, tmp_path, fetch_frames={"THYAO": bozuk}, now=simdi)
    caplog.set_level("DEBUG")
    main_module.scan_all_stocks(
        mgr, _Lifecycle(), _Notifier(), stocks=["THYAO"], send_alerts=False
    )

    assert main_module.daily_stats["cache_reddi"] >= 1
    assert "REDDEDİLDİ" in caplog.text
    assert len(mgr.to_dataframe("THYAO")) == onceki_bar   # bozuk satır sızmadı


def test_reddedilen_gunluk_append_tazelendi_logu_yazmaz(tmp_path, monkeypatch, caplog):
    simdi = datetime.now(IST).replace(minute=5, second=0, microsecond=0)
    mgr = StockDequeManager(data_dir=str(tmp_path))
    mgr.append_dataframe("THYAO", _cok_gunlu_seri(15, simdi=simdi))
    bozuk_gunluk = _bozuk_seri((simdi - pd.Timedelta(days=120)).strftime("%Y-%m-%d"), 40)

    _tarama_kur(
        monkeypatch,
        tmp_path,
        fetch_frames={"THYAO": _seri((simdi - pd.Timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"), 1)},
        daily_frame=bozuk_gunluk,
        now=simdi,
    )
    caplog.set_level("DEBUG")
    main_module.scan_all_stocks(
        mgr, _Lifecycle(), _Notifier(), stocks=["THYAO"], send_alerts=False
    )

    assert "günlük veri tazelendi" not in caplog.text
    assert main_module.daily_stats["cache_reddi"] >= 1
    assert mgr.to_gunluk_dataframe("THYAO") is None


# ------------------------------------------------ eksik seans ve 1D soğuma --
def test_eksik_seans_gun_boslugu_olarak_yakalanir():
    """Bir seansın tamamı eksikse (farklı güne düşen aralık) da uyarı üretilir."""
    from data.backfill import sureklilik_sorunlari_bul

    seri = _cok_gunlu_seri(15, simdi=datetime.now(IST))
    # Bir HAFTA İÇİ seansın tamamını düşür (sessizce hiç çekilmemiş gün senaryosu)
    hafta_ici = sorted({ts.date() for ts in seri.index if ts.weekday() < 5})
    hedef_gun = hafta_ici[-8]
    eksik = seri[seri.index.date != hedef_gun]
    assert len(eksik) == len(seri) - 9

    kayitlar = [
        {"timestamp": ts.to_pydatetime(), "open": float(r.open), "high": float(r.high),
         "low": float(r.low), "close": float(r.close), "volume": float(r.volume)}
        for ts, r in eksik.iterrows()
    ]
    sorunlar = sureklilik_sorunlari_bul(kayitlar)
    gun_bosluklari = [s for s in sorunlar if s["tip"] == "gun_boslugu"]

    assert len(gun_bosluklari) == 1
    assert "EKSİK SEANS" in gun_bosluklari[0]["mesaj"]


def test_normal_gece_ve_hafta_sonu_gun_boslugu_uretmez():
    from data.backfill import sureklilik_sorunlari_bul

    seri = _cok_gunlu_seri(10, simdi=datetime.now(IST))
    kayitlar = [
        {"timestamp": ts.to_pydatetime(), "open": float(r.open), "high": float(r.high),
         "low": float(r.low), "close": float(r.close), "volume": float(r.volume)}
        for ts, r in seri.iterrows()
    ]
    sorunlar = sureklilik_sorunlari_bul(kayitlar)
    assert not [s for s in sorunlar if s["tip"] in ("bosluk", "gun_boslugu")]


def test_gunluk_fetch_hatasi_alti_saat_kilitlemez(tmp_path):
    """Başarısız 1D denemesi 6 saatlik cooldown yazmaz; kısa soğuma uygular."""
    mgr = StockDequeManager(data_dir=str(tmp_path))
    simdi = IST.localize(datetime(2026, 11, 16, 13, 30))

    mgr.gunluk_fetch_denemesi_kaydet("THYAO", simdi, basarili=False, persist=False)
    assert mgr.gunluk_veri_eksik_mi("THYAO", simdi + timedelta(minutes=5)) is False
    assert mgr.gunluk_veri_eksik_mi(
        "THYAO", simdi + timedelta(minutes=config.GUNLUK_FETCH_HATA_TEKRAR_DK + 1)
    ) is True
    # Hatalı deneme başarılı cooldown'a YAZILMADI
    assert "THYAO" not in mgr._gunluk_fetch_attempts

    # Başarılı deneme eski davranışı korur: kapanış sonrası (19:00) 6 saat bekleme
    aksam = IST.localize(datetime(2026, 11, 16, 19, 0))
    mgr.gunluk_fetch_denemesi_kaydet("THYAO", aksam, persist=False)
    assert mgr.gunluk_veri_eksik_mi("THYAO", aksam + timedelta(hours=5)) is False
    assert mgr.gunluk_veri_eksik_mi("THYAO", aksam + timedelta(hours=7)) is True


def test_resmi_tatil_gunleri_gun_boslugu_uretmez():
    """Ardışık resmî tatil günleri (ör. Kurban Bayramı) eksik veri SANILMAZ."""
    from data.backfill import sureklilik_sorunlari_bul

    tatiller = sorted(config.BIST_TATILLER)
    ardisik = None
    for i in range(len(tatiller) - 1):
        if (tatiller[i + 1] - tatiller[i]).days == 1:
            ardisik = {tatiller[i], tatiller[i + 1]}
            if i + 2 < len(tatiller) and (tatiller[i + 2] - tatiller[i + 1]).days == 1:
                ardisik.add(tatiller[i + 2])
            break
    assert ardisik, "BIST_TATILLER içinde ardışık tatil bulunamadı"

    simdi = datetime(2026, 6, 10, 17, 0, tzinfo=IST)
    bugun = pd.Timestamp(simdi).normalize()
    parcalar = []
    for geri in range(30, 0, -1):
        gun = bugun - pd.Timedelta(days=geri)
        if gun.date() in ardisik or gun.weekday() >= 5:
            continue
        idx = pd.date_range(f"{gun.date()} 10:00", periods=9, freq="h", tz=IST)
        parcalar.append(pd.DataFrame(
            {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000.0},
            index=idx,
        ))
    seri = pd.concat(parcalar)
    kayitlar = [
        {"timestamp": ts.to_pydatetime(), "open": float(r.open), "high": float(r.high),
         "low": float(r.low), "close": float(r.close), "volume": float(r.volume)}
        for ts, r in seri.iterrows()
    ]
    sorunlar = sureklilik_sorunlari_bul(kayitlar)
    assert not [s for s in sorunlar if s["tip"] in ("bosluk", "gun_boslugu")]
