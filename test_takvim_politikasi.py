"""Aşama 3 — Hafta sonu / configured-calendar davranış matrisi.

Bu dosya statik config kayıtlarının fonksiyonlara nasıl uygulandığını kilitler;
resmî BIST takviminin doğruluğunu bağımsız olarak kanıtlamaz. Politika kararı
kullanıcıya raporla bırakıldı
(ASAMA4_CANLIYA_HAZIRLIK_PLANI.md). Senaryo → kanıt eşlemesi raporun Aşama 4
bölümündedir; main_loop içi inline zamanlayıcı koşulları refactor gerektirmedikçe
KOD kanıtıyla (satır referansı) belgelenir.
"""

from datetime import date, datetime, time, timedelta

import pandas as pd
import pytest

import config
import main as main_module
from data import (
    bist_tatil_adi,
    is_bist_open,
    seans_kapanis_saati,
    time_until_next_open,
    son_kapanan_mum_ani,
    tarama_animi_mi,
    tarama_penceresi_acik_mi,
    veri_yok_modu_acik_mi,
)
from patterns import PatternLifecycleManager
from telegram_alert_flow import DeferredAlertBuffer

from test_live_data_flow import (
    FakeDeferredAlerts,
    FakeLiveState,
    FakeNotifier,
    sentetik_1h,
    sifirla_daily_stats,
    temel_monkeypatch,
)

IST = config.ISTANBUL_TZ
CUMARTESI = IST.localize(datetime(2026, 10, 10, 12, 35))   # 2026-10-10 Cumartesi
PAZAR = IST.localize(datetime(2026, 10, 11, 12, 35))       # 2026-10-11 Pazar
TATIL = IST.localize(datetime(2026, 10, 29, 12, 35))       # config'te tatil kaydı bulunan tarih
YARIM_GUN = IST.localize(datetime(2026, 10, 28, 12, 35))   # config'te 13:00 kapanışlı kayıt
YARIM_GUN_SONRASI = IST.localize(datetime(2026, 10, 28, 14, 35))
NORMAL_GUN = IST.localize(datetime(2026, 10, 8, 12, 35))   # Perşembe, seans içi
CUMA = IST.localize(datetime(2026, 10, 9, 17, 45))         # configured normal-day schedule


def test_normal_islem_gunu_pencere_acik_ve_tarama_ani_hesaplanir():
    assert bist_tatil_adi(NORMAL_GUN) is None
    assert tarama_penceresi_acik_mi(NORMAL_GUN) is True
    kapanis = son_kapanan_mum_ani(NORMAL_GUN)
    assert kapanis is not None and kapanis.date() == NORMAL_GUN.date()


def test_cumartesi_pazar_tarama_ve_veri_yok_modu_kapali():
    """Senaryo 2-3: hafta sonu otomatik tarama yok; 'veri yok modu' da tetiklenmez
    (pencere zaten kapalı). Ana döngü scan_all_stocks'a ulaşamaz (KOD: main_loop
    yalnız tarama_penceresi_acik_mi True iken taramayı çağırır)."""
    for hafta_sonu in (CUMARTESI, PAZAR):
        assert tarama_penceresi_acik_mi(hafta_sonu) is False
        assert tarama_animi_mi(hafta_sonu, None) is False
        assert veri_yok_modu_acik_mi(hafta_sonu, 30 * 60) is False


def test_configured_tatil_ve_yarim_gun_penceresi():
    """Senaryo 4-5: configured holiday closes scanning; configured half-day uses 13:00.

    This asserts code behavior for static entries, not their official calendar accuracy.
    """
    assert bist_tatil_adi(TATIL) == "Cumhuriyet Bayramı"
    assert tarama_penceresi_acik_mi(TATIL) is False
    assert seans_kapanis_saati(YARIM_GUN) == time(13, 0)
    assert tarama_penceresi_acik_mi(YARIM_GUN) is True            # 12:35 → hâlâ açık
    assert tarama_penceresi_acik_mi(YARIM_GUN_SONRASI) is False   # 14:35 → kapandı


def test_market_open_holiday_weekend_and_half_day_edges():
    normal_open = IST.localize(datetime(2026, 10, 8, 9, 50))
    normal_closed = IST.localize(datetime(2026, 10, 8, 18, 11))
    assert is_bist_open(normal_open) is True
    assert is_bist_open(normal_closed) is False
    assert is_bist_open(TATIL) is False
    assert is_bist_open(CUMARTESI) is False
    assert is_bist_open(IST.localize(datetime(2026, 10, 28, 12, 59))) is True
    assert is_bist_open(IST.localize(datetime(2026, 10, 28, 13, 1))) is False


def test_half_day_first_scan_waits_for_configured_first_close():
    before_first_close = IST.localize(datetime(2026, 10, 28, 9, 50))
    before_first_scan = IST.localize(datetime(2026, 10, 28, 10, 34))
    first_scan = IST.localize(datetime(2026, 10, 28, 10, 35))

    assert son_kapanan_mum_ani(before_first_close) is None
    assert tarama_animi_mi(before_first_close, None) is False
    assert son_kapanan_mum_ani(before_first_scan) == IST.localize(
        datetime(2026, 10, 28, 10, 30)
    )
    assert tarama_animi_mi(before_first_scan, None) is False
    assert son_kapanan_mum_ani(first_scan) == IST.localize(datetime(2026, 10, 28, 10, 30))
    assert tarama_animi_mi(first_scan, None) is True


def test_next_open_skips_weekend_holiday_and_uses_today_before_open():
    before_open = IST.localize(datetime(2026, 10, 8, 9, 0))
    assert time_until_next_open(before_open) == pytest.approx(50 * 60)

    after_half_day_close = IST.localize(datetime(2026, 10, 28, 14, 0))
    friday_open = IST.localize(datetime(2026, 10, 30, 9, 50))
    assert time_until_next_open(after_half_day_close) == pytest.approx(
        (friday_open - after_half_day_close).total_seconds()
    )

    friday_after_close = IST.localize(datetime(2026, 10, 9, 18, 11))
    monday_open = IST.localize(datetime(2026, 10, 12, 9, 50))
    assert time_until_next_open(friday_after_close) == pytest.approx(
        (monday_open - friday_after_close).total_seconds()
    )


def test_pazar_gecisi_watch_bufferi_gun_degisimiyle_temizlenir():
    """Senaryo 7-9: watch/digest tamponunda ayrı TTL yok; İSTANBUL gün değişimi
    doğal TTL'dir. Cumartesi observe edilen aday pazartesi listelerde çıkmaz ve
    cuma snapshot'ı pazartesi restore edilmez (stale-day reddi)."""
    tampon = DeferredAlertBuffer()
    kayit = {"stock": "THYAO", "timeframe": "1h", "pattern_name": "Yükselen Üçgen",
             "state": "KIRILIM_ADAYI", "quality": 85.0}
    tampon.observe("THYAO", "1h", kayit, CUMARTESI)
    assert len(tampon.items(CUMARTESI)) == 1
    pazartesi = IST.localize(datetime(2026, 10, 12, 9, 0))
    assert tampon.items(pazartesi) == []                 # gün değişimi temizledi
    snapshot_cuma = tampon.snapshot(CUMARTESI)
    assert tampon.restore(snapshot_cuma, pazartesi) == 0  # eski gün snapshot'ı reddedilir


def test_istanbul_tz_dst_kullanmaz_sabit_utc3():
    """Senaryo 11: Europe/Istanbul 2016'dan beri DST kullanmaz; kışın/yazın offset
    sabittir. Zamanlanmış görevler pytz üzerinden bu sabit takvime bağlanır."""
    kis = IST.localize(datetime(2026, 1, 15, 12, 0)).utcoffset()
    yaz = IST.localize(datetime(2026, 7, 15, 12, 0)).utcoffset()
    assert kis == yaz == timedelta(hours=3)


def test_cuma_formasyonu_hafta_sonu_ozetinde_guncel_gibi_gorunur():
    """Senaryo 14 (RİSK KANITI): watch/immediate bildirimler tarama/tazelik kapılı
    iken, scheduled özet _live_state kayıtlarını veri YAŞI kontrolü yapmadan özetler.
    Cumadaki formasyon kaydı cumartesi özetinde aynen listelenir. Bu, kullanıcı
    kararı bekleyen politika bulgusudur — bu test yalnızca davranışı sabitler."""
    class CumartesiState(FakeLiveState):
        """Cumadan kalma kayıt; _build_active_formations_for_summary bu kaynağı
        veri yaşı sorgulamadan okur (main.py: get_formations yolu)."""
        def get_formations(self):
            return [{
                "stock": "THYAO", "timeframe": "1h",
                "pattern_name": "Yükselen Üçgen", "state": "SIKISMA_GUCLENIYOR",
                "quality": 85.0, "bar_time": str(CUMA),  # cuma içi zaman damgası
            }]

    live_state = CumartesiState()
    pytest_monkey = pytest.MonkeyPatch()
    try:
        sifirla_daily_stats(pytest_monkey)  # Aynı test patch'iyle izole et ve geri al.
        temel_monkeypatch(pytest_monkey, live_state, [], lambda s, p: None)
        lifecycle = PatternLifecycleManager(profile=config.PROFILE)
        eski_live_state = main_module._live_state
        main_module._live_state = live_state
        try:
            ozet_formasyonlari = main_module._build_active_formations_for_summary(lifecycle)
        finally:
            main_module._live_state = eski_live_state
        # Davranış kanıtı: veri yaşı sorgulanmadan cuma kaydı özete girer.
        assert any(kayit.get("stock_name") == "THYAO" for kayit in ozet_formasyonlari)
    finally:
        pytest_monkey.undo()


def test_post_close_zamanlayici_guardi_yok_kod_duzeysinde(tmp_path):
    """Senaryo 6 (KOD kanıtı): 20:00 post-close bloğu main_loop içinde yalnızca
    'now.time() >= post_close_analysis_time' koşuluna bakar; weekday/tatil guard'ı
    yoktur (main.py: 'GÜN SONU TAM EVREN ANALİZİ' bloğu). scan_all_stocks'un kendisi
    de pencere sorgulamadan 48 sembolün tamamını fetch eder → cumartesi 20:05'te
    zamanlayıcı çalışırsa sağlayıcıya 48 istek gider. Aşağıda scan davranışının
    kendisi kanıtlanır (zamanlayıcı inline koşulu refactor gerektirir, test edilmez)."""
    live_state = FakeLiveState()
    pytest_monkey = pytest.MonkeyPatch()
    try:
        sifirla_daily_stats(pytest_monkey)
        cumartesi_gece = CUMARTESI.replace(hour=20, minute=5)

        class SabitDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cumartesi_gece.astimezone(tz) if tz else cumartesi_gece.replace(tzinfo=None)

        pytest_monkey.setattr(main_module, "datetime", SabitDatetime)
        pytest_monkey.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_: False)
        cagri = []

        def sahte_1h(stock, period):
            cagri.append(stock)
            return None, False, "sahte ag hatasi"

        temel_monkeypatch(pytest_monkey, live_state, [], sahte_1h)
        from test_live_data_flow import FakePacer
        from data import StockDequeManager
        mgr = StockDequeManager(data_dir=str(tmp_path / "postclose-data"))
        result = main_module.scan_all_stocks(
            mgr, PatternLifecycleManager(profile=config.PROFILE), FakeNotifier(),
            send_alerts=False,
        )
        # Cumartesi geceydi; pencere kapalıydı; yine de tüm evren istendi:
        assert len(cagri) == len(config.ACTIVE_STOCKS)
        assert result["fetch_failures"] == len(config.ACTIVE_STOCKS)
    finally:
        pytest_monkey.undo()
