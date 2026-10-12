"""P0 — MUM KAPANIŞ PENCERESİ regresyon testleri (2 Eki 2026).

Ölçülen gerçekler (Yahoo chart API, THYAO.IS; meta.currentTradingPeriod.regular):
  * Seans 09:30–18:00; 1H barları SOL etiketli: 09:30, 10:30, ... 17:30.
  * Bar ömrü = etiket + TF süresi; GÜNÜN SON kovası seans sonunda kesilir.

Bu dosya üç eski hatayı kilitler:
  1) 1h için "+30 dk" kuralı -> :00–:29 arası taramalar (restart/telafi) HENÜZ
     KAPANMAMIŞ barı kapanmış sayıp bildirim üretebiliyordu.
  2) 2h/4h kovaları seans sonunda kesilmiyordu -> günün son kovası (17:30)
     18:35 taramasında hiç analiz edilmiyordu (2h son kova 15:30, 4h 13:30).
  3) 1d mumu sabit 18:30'da tamamlanıyordu -> yarım günde (arefe, 13:00)
     günlük mum o gün hiç analiz edilmiyordu.

Çalıştırma: python -m pytest test_mum_kapanis_penceresi.py -q
"""

from datetime import datetime, time as dt_time

import pandas as pd
import pytest

import data as data_mod
from data import (StockDequeManager, bar_kapandi_mi, mum_kapanis_ani,
                  mum_kapanis_anlari, resample_all_timeframes, resample_ohlcv,
                  seans_sonu_saati, tamamlanmis_mumlar)

IST = data_mod.ISTANBUL_TZ


def t(yil, ay, gun, saat=0, dakika=0):
    """İstanbul saat diliminde sabit bir an."""
    return IST.localize(datetime(yil, ay, gun, saat, dakika))


@pytest.fixture(scope="module")
def df_1h():
    """Gerçek THYAO 1H cache'i (360 bar / 40 seans)."""
    df = StockDequeManager().to_dataframe("THYAO")
    if df is None or len(df) < 100:
        pytest.skip("THYAO 1H cache yok")
    return df


@pytest.fixture(scope="module")
def tf_serileri(df_1h):
    return resample_all_timeframes(df_1h)


def _son(seri, tf, an):
    sub = tamamlanmis_mumlar(seri, tf, now=an)
    assert sub is not None and len(sub) > 0, f"{tf} için tamamlanmış mum kalmadı"
    return sub.index[-1]


# --- 1) 1H: kısmi mum ASLA kapanmış sayılmaz ------------------------------

def test_1h_13_05_kismi_bar_verilmez(df_1h):
    """13:05'te 12:30 etiketli bar henüz kapanmadı (13:30'da kapanır)."""
    son = _son(df_1h, "1h", t(2026, 9, 25, 13, 5))
    assert son.strftime("%H:%M") == "11:30", f"kısmi bar sızdı: {son}"


@pytest.mark.parametrize("an, beklenen", [
    # Tarama anı :35 -> bir önceki saatte kapanan bar (değişmedi)
    ((2026, 9, 25, 10, 35), "09:30"),
    ((2026, 9, 25, 11, 35), "10:30"),
    ((2026, 9, 25, 13, 35), "12:30"),
    ((2026, 9, 25, 17, 35), "16:30"),
    # Seans sonu: 17:30 barı 18:00'de kapanır
    ((2026, 9, 25, 17, 59), "16:30"),
    ((2026, 9, 25, 18, 0), "17:30"),
    ((2026, 9, 25, 18, 35), "17:30"),
])
def test_1h_kapanis_anlari(df_1h, an, beklenen):
    son = _son(df_1h, "1h", t(*an))
    assert son.strftime("%H:%M") == beklenen


def test_mum_kapanis_ani_1h_bir_saat_sonra():
    """Bar ömrü 1 saattir (eski +30 dk kuralı değil); günün sonu 18:00'de kesilir."""
    assert mum_kapanis_ani(t(2026, 9, 25, 10, 30), "1h").strftime("%H:%M") == "11:30"
    assert mum_kapanis_ani(t(2026, 9, 25, 12, 30), "1h").strftime("%H:%M") == "13:30"
    assert mum_kapanis_ani(t(2026, 9, 25, 17, 30), "1h").strftime("%H:%M") == "18:00"


def test_bar_kapandi_mi_kapisi():
    # 13:05'te 12:30 barı kapanmadı -> push kapısı kapalı
    assert bar_kapandi_mi(t(2026, 9, 25, 12, 30), "1h", now=t(2026, 9, 25, 13, 5)) is False
    assert bar_kapandi_mi(t(2026, 9, 25, 12, 30), "1h", now=t(2026, 9, 25, 13, 35)) is True
    assert bar_kapandi_mi(None, "1h") is False


# --- 2) 2H/4H: günün son kovası seans sonunda kapanır --------------------

@pytest.mark.parametrize("tf, beklenen_saat", [("2h", "17:30"), ("4h", "17:30")])
def test_gunun_son_kovasi_18_35_analiz_edilir(tf_serileri, tf, beklenen_saat):
    """Eski hata: 2h 15:30 / 4h 13:30'da kalıyordu, günün kapanışı kayıptı."""
    son = _son(tf_serileri[tf], tf, t(2026, 9, 25, 18, 35))
    assert son.strftime("%H:%M") == beklenen_saat


def test_4h_kapanis_anlari():
    # 13:30 kovası 17:30'da, 17:30 kovası seans sonunda (18:00) kapanır
    assert mum_kapanis_ani(t(2026, 9, 25, 13, 30), "4h").strftime("%H:%M") == "17:30"
    assert mum_kapanis_ani(t(2026, 9, 25, 17, 30), "4h").strftime("%H:%M") == "18:00"
    assert bar_kapandi_mi(t(2026, 9, 25, 17, 30), "4h", now=t(2026, 9, 25, 18, 35)) is True
    assert bar_kapandi_mi(t(2026, 9, 25, 17, 30), "4h", now=t(2026, 9, 25, 18, 0)) is True


def test_2h_kapanis_anlari():
    assert mum_kapanis_ani(t(2026, 9, 25, 15, 30), "2h").strftime("%H:%M") == "17:30"
    assert mum_kapanis_ani(t(2026, 9, 25, 17, 30), "2h").strftime("%H:%M") == "18:00"
    # 13:35'te 13:30 kovası henüz kapanmadı (15:30'da kapanır)
    assert bar_kapandi_mi(t(2026, 9, 25, 13, 30), "2h", now=t(2026, 9, 25, 13, 35)) is False


# --- 3) 1D: yarım günde seans kapanışı (13:00) ---------------------------

def _gunluk_seri(gunler):
    idx = pd.DatetimeIndex([t(g[0], g[1], g[2]) for g in gunler])
    return pd.DataFrame({"open": [100.0] * len(gunler), "high": [101.0] * len(gunler),
                         "low": [99.0] * len(gunler), "close": [100.5] * len(gunler),
                         "volume": [1000] * len(gunler)}, index=idx)


def test_yarim_gunde_gunluk_mum_13_00_de_tamamlanir():
    seri = _gunluk_seri([(2026, 3, 18), (2026, 3, 19)])
    # 19 Mart = yarım gün (Ramazan Bayramı arefesi, kapanış 13:00)
    assert seans_sonu_saati(t(2026, 3, 19)).strftime("%H:%M") == "13:00"
    assert len(tamamlanmis_mumlar(seri, "1d", now=t(2026, 3, 19, 12, 59))) == 1
    sub = tamamlanmis_mumlar(seri, "1d", now=t(2026, 3, 19, 13, 5))
    assert len(sub) == 2 and sub.index[-1].strftime("%d %b") == "19 Mar"
    assert mum_kapanis_ani(t(2026, 3, 19), "1d").strftime("%H:%M") == "13:00"


def test_normal_gunde_gunluk_mum_18_30_da_tamamlanir(df_1h):
    """Mevcut davranış korunur: 18:29'da dün, 18:35'te bugün."""
    gunluk = resample_all_timeframes(df_1h)["1d"]
    assert tamamlanmis_mumlar(gunluk, "1d", now=t(2026, 9, 25, 18, 29)).index[-1].strftime("%d") == "24"
    assert tamamlanmis_mumlar(gunluk, "1d", now=t(2026, 9, 25, 18, 35)).index[-1].strftime("%d") == "25"


def test_yarim_gunde_2h_4h_son_kovalar_13_00_de_kapanir():
    """Arefe günü seans 13:00'te biter: 2h 11:30 ve 4h 09:30 kovaları o an kapanır."""
    saatler = pd.DatetimeIndex(pd.date_range(t(2026, 3, 19, 9, 30), t(2026, 3, 19, 12, 30), freq="1h"))
    bir_saatlik = pd.DataFrame({"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 10},
                               index=saatler)
    assert len(tamamlanmis_mumlar(resample_ohlcv(bir_saatlik, "2h"), "2h",
                                  now=t(2026, 3, 19, 12, 5))) == 1
    assert len(tamamlanmis_mumlar(resample_ohlcv(bir_saatlik, "2h"), "2h",
                                  now=t(2026, 3, 19, 13, 5))) == 2
    # 4h: 09:30 kovası ancak seans sonunda (13:00) tamamlanır
    assert len(tamamlanmis_mumlar(resample_ohlcv(bir_saatlik, "4h"), "4h",
                                  now=t(2026, 3, 19, 12, 5))) == 0
    assert len(tamamlanmis_mumlar(resample_ohlcv(bir_saatlik, "4h"), "4h",
                                  now=t(2026, 3, 19, 13, 5))) == 1


# --- 4) Tek kaynak / tutarlılık ------------------------------------------

def test_kapanis_serisi_ile_tek_bar_hesabi_ayni():
    """mum_kapanis_anlari (vektör) ile mum_kapanis_ani (tek bar) tutarlı olmalı."""
    idx = [t(2026, 9, 25, 9, 30), t(2026, 9, 25, 17, 30), t(2026, 3, 19, 11, 30)]
    dizi = mum_kapanis_anlari(pd.DatetimeIndex(idx), "4h")
    for ts, kapanis in zip(idx, dizi):
        assert mum_kapanis_ani(ts, "4h") == kapanis
    assert dizi[1].strftime("%H:%M") == "18:00"   # 17:30 -> seans sonu
    assert dizi[2].strftime("%H:%M") == "13:00"   # yarım gün, 11:30 -> 15:30 yerine 13:00


def test_bilinmeyen_timeframe_1h_varsayar_ve_loglar(caplog):
    """Bilinmeyen TF çökmez; 1h süresi varsayılır (eski davranışla uyumlu)."""
    with caplog.at_level("WARNING"):
        kapanis = mum_kapanis_ani(t(2026, 9, 25, 10, 30), "3h")
    assert kapanis.strftime("%H:%M") == "11:30"


# --- 5) Mesaj satırı: "hangi mum kapandı?" -------------------------------

def test_mesaj_mum_satiri_metinleri():
    from reporting.format import mum_kapanis_metni
    assert mum_kapanis_metni("1h", t(2026, 9, 25, 17, 30), t(2026, 9, 25, 18, 0)) == \
        "🕒 1 saatlik mum 25.09 17:30 → 18:00 kapandı"
    assert mum_kapanis_metni("4h", t(2026, 9, 25, 13, 30), t(2026, 9, 25, 17, 30)) == \
        "🕒 4 saatlik mum 25.09 13:30 → 17:30 kapandı"
    assert mum_kapanis_metni("1d", t(2026, 9, 25), t(2026, 9, 25, 18, 30)) == \
        "🕒 Günlük mum 25.09 kapanışı · 18:30"
    # Boş/geçersiz girdi metin üretimini bozmaz
    assert mum_kapanis_metni("1h", None, None) == ""
    assert mum_kapanis_metni("1h", "metin-degil", None) == ""


def test_notifier_anlik_mesaja_mum_satiri_ekler():
    from notifier import TelegramNotifier
    n = TelegramNotifier()
    veri = {
        'stock_name': 'THYAO', 'timeframe': '4h', 'pattern_name': 'Simetrik Üçgen',
        'state': 'KIRILIM_TEYITLI', 'confidence_score': 84, 'critical_price_level': 292.25,
        'upper_now': 292.25, 'lower_now': 288.0, 'break_dir': 1, 'break_strength': 79,
        'retest_seen': True,
        'bar_metni': "🕒 4 saatlik mum 25.09 13:30 → 17:30 kapandı",
    }
    mesaj = n.format_message(veri)
    assert "4 saatlik mum 25.09 13:30 → 17:30 kapandı" in mesaj
    # İzleme (digest) mesajına eklenmez: yer bütçesi orada farklı.
    veri_izleme = dict(veri, state='SIKISMA_GUCLENIYOR')
    assert "kapandı" not in n.format_message(veri_izleme)


# --- 6) main.py güvenlik kapısı: kapanmamış barla push YOK ---------------

class _SahteAday:
    pattern_type = "Simetrik Üçgen"
    upper_now = 100.0
    lower_now = 95.0
    contraction = 0.7
    upper_touches = 2
    lower_touches = 2
    break_strength = 80.0
    start_bar = 10


def _sahte_snap():
    from types import SimpleNamespace
    return SimpleNamespace(state="KIRILIM_TEYITLI", break_dir=1, log="sahte",
                           active=_SahteAday(), effective_quality=85.0,
                           bar_index=30, retest_seen=True, invalid_reason="Yok")


def test_kapanmamis_barla_push_yok(monkeypatch):
    """Kapı 'bar kapanmadı' derse anlık push üretilmez, sayaç artar.

    Gerçek akışta bu dal HİÇ çalışmaz (tamamlanmis_mumlar aynı kuralı uygular);
    test, saat/tarama kayması regresyonunda sinyalin yanlış gitmediğini kilitler.
    """
    import main as M
    from data import StockDequeManager
    from patterns import PatternLifecycleManager

    monkeypatch.setattr(M, "fetch_1h_stocks_paced", lambda *a, **k: ({}, {}, 0, 0))
    monkeypatch.setattr(M, "bar_kapandi_mi", lambda *a, **k: False)
    lm = PatternLifecycleManager()
    monkeypatch.setattr(lm, "scan", lambda *a, **k: _sahte_snap())

    gonderilen = []
    notifier = M.TelegramNotifier()
    monkeypatch.setattr(notifier, "send", lambda data, kuyrukla=True: gonderilen.append(data) or True)

    yedek = dict(M.daily_stats)
    try:
        M.scan_all_stocks(StockDequeManager(), lm, notifier,
                          stocks=["THYAO"], send_alerts=True)
        assert gonderilen == [], "kapanmamış bar ile push üretildi"
        assert M.daily_stats['alerts_bar_kapanmadi'] >= 1
    finally:
        M.daily_stats.clear()
        M.daily_stats.update(yedek)
        # Test izolasyonu: sahte taramanın LiveState kayıtlarını temizle.
        M._live_state.begin_scan(datetime.now(IST), manuel=True, beklenen_hisse=0,
                                 scope=[], replace_all=True)
        M._live_state.finish_scan()


def test_kapanmis_barla_push_uretilir(monkeypatch):
    """Kapı açıkken (bar kapandı) aynı senaryo push ÜRETİR: kapı fazla elemez."""
    import main as M
    from data import StockDequeManager
    from patterns import PatternLifecycleManager

    monkeypatch.setattr(M, "fetch_1h_stocks_paced", lambda *a, **k: ({}, {}, 0, 0))
    monkeypatch.setattr(M, "bar_kapandi_mi", lambda *a, **k: True)
    lm = PatternLifecycleManager()
    monkeypatch.setattr(lm, "scan", lambda *a, **k: _sahte_snap())

    gonderilen = []
    notifier = M.TelegramNotifier()
    monkeypatch.setattr(notifier, "send", lambda data, kuyrukla=True: gonderilen.append(data) or True)

    yedek = dict(M.daily_stats)
    try:
        M.scan_all_stocks(StockDequeManager(), lm, notifier,
                          stocks=["THYAO"], send_alerts=True)
        assert gonderilen, "kapanmış barla push üretilmedi"
        veri = gonderilen[0]
        assert veri.get('bar_kapandi') is True
        assert veri.get('bar_metni', "").startswith("🕒")
        assert veri.get('bar_kapanis') and isinstance(veri['bar_kapanis'], str)
    finally:
        M.daily_stats.clear()
        M.daily_stats.update(yedek)
        # Test izolasyonu: sahte taramanın LiveState kayıtlarını temizle.
        M._live_state.begin_scan(datetime.now(IST), manuel=True, beklenen_hisse=0,
                                 scope=[], replace_all=True)
        M._live_state.finish_scan()
