"""Render canlı veri akışı denetimi: cache ↔ sağlayıcı seçimi izole testleri.

Kapsam (TELEGRAM_PRODUCT_AND_LIVE_READINESS_AUDIT.md düzeltmesi):
  1. Temiz başlangıçta 48 hissenin sağlayıcıdan yüklenmesi.
  2. bot_data'da 28 hisse varken eksik 20 hissenin canlı veriden işlenmesi.
  3. Sağlayıcıdan veri çekilemezse seans içi/dışı davranış ve kapsam raporu.
  4. Eski cache ile taze canlı verinin birleştirme/tercih kuralı.
  5. Kısmi veri başarısızlığında tarama kapsamının raporlanması.

Gerçek Yahoo/Telegram/Supabase çağrısı YOKTUR: fetch_yfinance_1h/1d sahte
veri döndürür, notifier/store sahtedir, disk izolesi pytest tmp_path'dir.
"""

import copy
import math
from contextlib import nullcontext
from datetime import datetime, timedelta

import pandas as pd
import pytest

import config
import main as main_module
from data import (
    FULL_1H_FETCH_PERIOD,
    ROUTINE_1H_FETCH_PERIOD,
    StockDequeManager,
)
from patterns import PatternLifecycleManager

IST = config.ISTANBUL_TZ

# GitHub'da bilinçli olarak tutulan 28 hisselik bot_data önbelleği
# (git ls-files bot_data ile doğrulandı).
CACHED_28 = [
    "AKBNK", "ALARK", "ASELS", "BIMAS", "DOHOL", "EKGYO", "EREGL", "FROTO",
    "GARAN", "GUBRF", "HALKB", "HEKTS", "ISCTR", "KCHOL", "KRDMD", "PETKM",
    "PGSUS", "SAHOL", "SASA", "SISE", "TAVHL", "TCELL", "THYAO", "TOASO",
    "TTKOM", "TUPRS", "VAKBN", "YKBNK",
]
MISSING_20 = sorted(set(config.ACTIVE_STOCKS) - set(CACHED_28))


# ---------------------------------------------------------------- sahteler ---
class FakePacer:
    """YahooRequestPacer yerine geçer; bekleme yapmaz."""

    def request(self, _label):
        return nullcontext()

    def reset_batch(self):
        return None


class FakeLiveState:
    def __init__(self):
        self.calls = []
        self._status = {}

    def begin_scan(self, now, **kwargs):
        self.calls.append(("begin", kwargs.copy()))

    def finish_scan(self, now, **kwargs):
        self.calls.append(("finish", kwargs.copy()))
        self._status.update({"son_tarama_durumu": "tamamlandi"})
        self._status.update(kwargs)

    def fail_scan(self, mesaj, now, **kwargs):
        self.calls.append(("fail", mesaj, kwargs.copy()))
        self._status.update({"son_tarama_durumu": "basarisiz", "fail_mesaj": mesaj})
        self._status.update(kwargs)

    def record_formation(self, kayit):
        self.calls.append(("formation", kayit.get("stock"), kayit.get("timeframe")))

    def mark_alert_sent(self, *a, **k):
        return None

    def status(self):
        return dict(self._status)


class FakeDeferredAlerts:
    def observe(self, *a, **k):
        return None

    def items(self, *a, **k):
        return []

    def snapshot(self, *a, **k):
        return {}

    def mark_reported(self, *a, **k):
        return None


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, alert_data, *a, **k):
        self.sent.append(alert_data)
        return True

    def persist_watch_state(self, *a, **k):
        return True

    def kap_durumu(self):
        return {"kapali": False}


# ------------------------------------------------------------------ yardımcı -
def sentetik_1h(n_bars, end_at, base=100.0):
    """Düzgün sinüs dalgalı, süreklilik sorunu olmayan sentetik 1H OHLCV."""
    idx = pd.date_range(end=end_at, periods=n_bars, freq="h", tz="Europe/Istanbul")
    closes = [base + 0.8 * math.sin(i / 4.0) + 0.01 * i for i in range(n_bars)]
    rows = []
    prev = closes[0]
    for i, close in enumerate(closes):
        op = prev
        hi = max(op, close) + 0.2
        lo = min(op, close) - 0.2
        rows.append({"open": op, "high": hi, "low": lo, "close": close,
                     "volume": 1000.0 + i})
        prev = close
    return pd.DataFrame(rows, index=idx)


def sifirla_daily_stats(monkeypatch):
    fresh = copy.deepcopy(main_module.daily_stats)
    for key in ("stocks_scanned", "patterns_found", "alerts_sent", "errors",
                "fetch_ok", "fetch_failures", "fetch_retries",
                "fetch_retry_recovered", "stale_stocks", "split_atlanan"):
        fresh[key] = 0
    fresh["max_bar_age_min"] = None
    fresh["data_stale"] = False
    fresh["veri_yok_modu"] = False
    monkeypatch.setattr(main_module, "daily_stats", fresh)
    return fresh


def temel_monkeypatch(monkeypatch, live_state, heartbeat_kayit, fetch_1h, fetch_1d=None):
    monkeypatch.setattr(main_module, "last_run_stats", {}, raising=False)
    monkeypatch.setattr(main_module, "_live_state", live_state)
    monkeypatch.setattr(main_module, "_deferred_alert_buffer", FakeDeferredAlerts())
    monkeypatch.setattr(main_module, "_supabase_store_ref", None)
    monkeypatch.setattr(main_module, "_deque_manager_ref", None)
    monkeypatch.setattr(main_module, "_shutdown_requested", False)
    monkeypatch.setattr(main_module, "create_yahoo_pacer", lambda: FakePacer())
    monkeypatch.setattr(main_module, "reset_daily_if_needed", lambda: None)
    monkeypatch.setattr(
        main_module, "write_heartbeat",
        lambda **kwargs: heartbeat_kayit.append(kwargs),
    )
    monkeypatch.setattr(main_module, "son_tarama_kaydet", lambda: None)

    cagri_1h = []

    def sahte_fetch_1h(stock, period=FULL_1H_FETCH_PERIOD, with_status=False):
        cagri_1h.append((stock, period))
        sonuc = fetch_1h(stock, period)
        if isinstance(sonuc, tuple):
            return sonuc
        return (sonuc, False, "")

    monkeypatch.setattr(main_module, "fetch_yfinance_1h", sahte_fetch_1h)

    cagri_1d = []

    def sahte_fetch_1d(stock, period=None):
        cagri_1d.append(stock)
        return fetch_1d(stock) if fetch_1d else None

    monkeypatch.setattr(main_module, "fetch_yfinance_1d", sahte_fetch_1d)
    monkeypatch.setattr(
        main_module, "_load_domain_runner",
        lambda: lambda symbol, timeframe, frame, *, profile: None,
    )
    return cagri_1h, cagri_1d


def on_yukle(mgr, stocks, end_at, n_bars=55):
    for stock in stocks:
        mgr.append_dataframe(stock, sentetik_1h(n_bars, end_at))
        mgr.save_to_disk(stock)


# -------------------------------------------------------------------- testler -
def test_aktif_evren_48_ve_repo_cache_28():
    """Evren ACTIVE_STOCKS (48); repo'daki bot_data 28 hissedir; 20 sembol cache dışı."""
    assert len(config.ACTIVE_STOCKS) == 48
    assert len(set(config.ACTIVE_STOCKS)) == 48
    assert len(CACHED_28) == 28
    assert set(CACHED_28).issubset(set(config.ACTIVE_STOCKS))
    assert len(MISSING_20) == 20


def test_temiz_baslangicta_48_hisse_saglayicidan_yuklenir(tmp_path, monkeypatch):
    """Senaryo 1: boş cache -> tarama tüm 48 sembol için tam pencere (60d) ister."""
    live_state = FakeLiveState()
    stats = sifirla_daily_stats(monkeypatch)
    heartbeat = []

    def sahte_1h(stock, period):
        return sentetik_1h(60, datetime.now(IST) - pd.Timedelta(minutes=100))

    cagri_1h, _ = temel_monkeypatch(monkeypatch, live_state, heartbeat, sahte_1h)
    monkeypatch.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_: False)

    mgr = StockDequeManager(data_dir=str(tmp_path / "bot_data"))
    lifecycle = PatternLifecycleManager(profile=config.PROFILE)

    result = main_module.scan_all_stocks(
        mgr, lifecycle, FakeNotifier(), send_alerts=False
    )

    # 48 sembolün TAMAMI için fetch isteği gitmiş; hepsi tam pencere.
    assert sorted(s for s, _ in cagri_1h) == sorted(config.ACTIVE_STOCKS)
    assert all(p == FULL_1H_FETCH_PERIOD for _, p in cagri_1h)
    # Canlı veri disk önbelleğine yazılmış (48 hisse).
    kayitli = {p.stem for p in (tmp_path / "bot_data").glob("*.pkl")}
    assert kayitli == set(config.ACTIVE_STOCKS)
    # Kapsam: 48/48 işlendi, evren 28'e daralmadı.
    assert result["status"] == "tamamlandi"
    assert result["requested"] == 48
    assert result["processed"] == 48
    assert result["fresh_fetch"] == 48
    assert result["fetch_failures"] == 0
    assert stats["fetch_ok"] == 48


def test_cache_28_iken_eksik_20_canli_veriden_yuklenir(tmp_path, monkeypatch):
    """Senaryo 2: 28 taze cache + 20 boş -> tarama evreni yine 48; eksikler 60d ister,
    28 olanlar 5d rutin pencere ister; tarama sonunda 48'in tamamı analizli."""
    live_state = FakeLiveState()
    stats = sifirla_daily_stats(monkeypatch)
    heartbeat = []
    donen = {
        stock: sentetik_1h(60, datetime.now(IST) - pd.Timedelta(minutes=100))
        for stock in config.ACTIVE_STOCKS
    }

    def sahte_1h(stock, period):
        return donen[stock].copy()

    cagri_1h, _ = temel_monkeypatch(monkeypatch, live_state, heartbeat, sahte_1h)
    monkeypatch.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_: False)

    mgr = StockDequeManager(data_dir=str(tmp_path / "bot_data"))
    on_yukle(mgr, CACHED_28, datetime.now(IST) - pd.Timedelta(minutes=100))
    lifecycle = PatternLifecycleManager(profile=config.PROFILE)

    result = main_module.scan_all_stocks(
        mgr, lifecycle, FakeNotifier(), send_alerts=False
    )

    # Fetch evreni 48; pencere seçimi cache durumuna göre.
    assert sorted(s for s, _ in cagri_1h) == sorted(config.ACTIVE_STOCKS)
    period_map = dict(cagri_1h)
    assert {s for s, p in cagri_1h if p == FULL_1H_FETCH_PERIOD} == set(MISSING_20)
    assert {s for s, p in cagri_1h if p == ROUTINE_1H_FETCH_PERIOD} == set(CACHED_28)
    # Cache'te hiç olmayan 20 hisse canlı veriden yüklendi ve analiz edildi.
    for stock in MISSING_20:
        df = mgr.to_dataframe(stock)
        assert df is not None and len(df) >= 50, stock
    assert result["status"] == "tamamlandi"
    assert result["requested"] == 48 and result["processed"] == 48
    assert result["fresh_fetch"] == 48
    # Evren 28 sembole daralmadı: taramaACTIVE_STOCKS üzerinden koştu.
    assert stats["stocks_scanned"] == 48


def test_baslangic_on_yuklemesi_yalniz_eksik_sembolleri_ister(tmp_path, monkeypatch):
    """main_loop başlangıç adımı: 'cache_eksik_hisseler' seçimi (mevcut None veya
    <50 bar) 20 eksik sembolü verir; İLK YÜKLEME bu 20'si için tam pencere ister."""
    mgr = StockDequeManager(data_dir=str(tmp_path / "bot_data"))
    on_yukle(mgr, CACHED_28, datetime.now(IST) - pd.Timedelta(minutes=100))

    # main_loop'taki koşulun birebir aynısı:
    cache_eksik_hisseler = []
    for stock in config.ACTIVE_STOCKS:
        mevcut = mgr.to_dataframe(stock)
        if mevcut is None or len(mevcut) < 50:
            cache_eksik_hisseler.append(stock)
    assert sorted(cache_eksik_hisseler) == MISSING_20

    cagri = []
    donen = {
        stock: sentetik_1h(60, datetime.now(IST) - pd.Timedelta(minutes=100))
        for stock in MISSING_20
    }

    def sahte_fetch(stock, period=FULL_1H_FETCH_PERIOD, with_status=False):
        cagri.append((stock, period))
        return (donen[stock].copy(), False, "")

    monkeypatch.setattr(main_module, "fetch_yfinance_1h", sahte_fetch)
    monkeypatch.setattr(main_module, "_shutdown_requested", False)

    fetched, failures, retry, recovered = main_module.fetch_1h_stocks_paced(
        cache_eksik_hisseler, FakePacer(), "İLK YÜKLEME"
    )

    assert failures == {}
    assert sorted(fetched) == MISSING_20
    # periods= verilmediği için başlangıç yüklemesi tam geçmiş penceresi kullanır.
    assert {p for _, p in cagri} == {FULL_1H_FETCH_PERIOD}
    assert len(cagri) == 20

    for stock in cache_eksik_hisseler:
        mgr.append_dataframe(stock, fetched[stock])
        mgr.save_to_disk(stock)
    kayitli = {p.stem for p in (tmp_path / "bot_data").glob("*.pkl")}
    assert kayitli == set(config.ACTIVE_STOCKS)


def test_saglayici_cokeilirse_seans_disi_cache_kullanilir_eksikler_atlanir(
    tmp_path, monkeypatch, caplog
):
    """Senaryo 3a: tüm fetch'ler başarısız + seans kapalı -> 28 taze cache ile devam,
    cache'siz 20 atlanır; sonuç 'başarılı tarama' olarak raporlanmaz."""
    live_state = FakeLiveState()
    stats = sifirla_daily_stats(monkeypatch)
    heartbeat = []

    def sahte_1h(stock, period):
        return None, False, "sahte ag hatasi"

    temel_monkeypatch(monkeypatch, live_state, heartbeat, sahte_1h)
    monkeypatch.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_: False)

    mgr = StockDequeManager(data_dir=str(tmp_path / "bot_data"))
    on_yukle(mgr, CACHED_28, datetime.now(IST) - pd.Timedelta(minutes=150))
    lifecycle = PatternLifecycleManager(profile=config.PROFILE)

    with caplog.at_level("WARNING"):
        result = main_module.scan_all_stocks(
            mgr, lifecycle, FakeNotifier(), send_alerts=False
        )

    assert result["status"] == "basarisiz"
    assert result["requested"] == 48
    assert result["processed"] == 28          # yalnız cache'i olanlar
    assert result["failed"] == 20             # cache'siz 20 açıkça eksik
    assert result["fresh_fetch"] == 0
    assert result["fetch_failures"] == 48
    assert stats["fetch_failures"] == 48
    # Kısmi tarama başarı gibi yayınlanmadı:
    fail_calls = [c for c in live_state.calls if c[0] == "fail"]
    assert fail_calls and "Eksik tarama: 28/48" in fail_calls[0][1]
    # Seans dışı cache kullanımı ve boş cache atlanması loglarda görünür:
    assert "seans dışı son mevcut cache" in caplog.text
    assert "veri yok (fetch basarisiz + cache bos)" in caplog.text
    assert "VERİ SAĞLIĞI" in caplog.text


def test_seans_acik_eski_cache_analiz_edilmez(tmp_path, monkeypatch):
    """Senaryo 3b: seans açık + fetch başarısız -> 120 dk'dan eski cache ile sinyal
    üretilmez (güncelmiş gibi analiz yok); taze sayılan cache kullanılır."""
    live_state = FakeLiveState()
    stats = sifirla_daily_stats(monkeypatch)
    heartbeat = []
    eski_4 = CACHED_28[:4]        # 180 dk eski -> analiz dışı
    taze_24 = CACHED_28[4:]       # 60 dk eski -> kullanılabilir

    def sahte_1h(stock, period):
        return None, False, "sahte ag hatasi"

    temel_monkeypatch(monkeypatch, live_state, heartbeat, sahte_1h)
    monkeypatch.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_: True)

    mgr = StockDequeManager(data_dir=str(tmp_path / "bot_data"))
    simdi = datetime.now(IST)
    on_yukle(mgr, eski_4, simdi - pd.Timedelta(minutes=180))
    on_yukle(mgr, taze_24, simdi - pd.Timedelta(minutes=60))
    lifecycle = PatternLifecycleManager(profile=config.PROFILE)

    result = main_module.scan_all_stocks(
        mgr, lifecycle, FakeNotifier(), send_alerts=False
    )

    assert result["status"] == "basarisiz"
    assert result["processed"] == 24
    assert result["failed"] == 24            # 4 eski-cache + 20 cache'siz
    assert stats["stale_stocks"] >= 4
    # 180 dk eski 4 hisse ile formasyon hesaplanmadı:
    assert main_module._cache_verisi_kullanilabilir(180, False, True) is False
    assert main_module._cache_verisi_kullanilabilir(60, False, True) is True


def test_14_gunden_eski_cache_seans_disinda_bile_kullanilmaz(tmp_path, monkeypatch, caplog):
    """Senaryo 3c: 14 günden eski cache OFFSESSION_CACHE_MAX_AGE_DAYS sınırını aşar;
    fetch yoksa hisse analiz dışı bırakılır ('eski veriyle canlı analiz' yok)."""
    live_state = FakeLiveState()
    stats = sifirla_daily_stats(monkeypatch)
    heartbeat = []
    uc_hisse = CACHED_28[:3]

    def sahte_1h(stock, period):
        return None, False, "sahte ag hatasi"

    temel_monkeypatch(monkeypatch, live_state, heartbeat, sahte_1h)
    monkeypatch.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_: False)

    mgr = StockDequeManager(data_dir=str(tmp_path / "bot_data"))
    on_yukle(mgr, uc_hisse, datetime.now(IST) - pd.Timedelta(days=20), n_bars=55)
    lifecycle = PatternLifecycleManager(profile=config.PROFILE)

    with caplog.at_level("WARNING"):
        result = main_module.scan_all_stocks(
            mgr, lifecycle, FakeNotifier(), stocks=list(uc_hisse), send_alerts=False
        )

    assert result["status"] == "basarisiz"
    assert result["processed"] == 0
    assert result["failed"] == 3
    assert stats["stale_stocks"] == 3
    assert "analiz dışı bırakıldı" in caplog.text


def test_saglayici_eski_bar_donerse_analiz_devam_eder_ama_isaretlenir(
    tmp_path, monkeypatch, caplog
):
    """Fetch 'başarılı' ama gelen en yeni bar 8 saat eski (sağlayıcı gecikmesi):
    seans açıkken analiz devam eder; ama sessiz değil - VERİ ESKİ uyarısı,
    stale_stocks/data_stale sayacı ve data_asof eski mum zamanı ile raporlanır."""
    live_state = FakeLiveState()
    stats = sifirla_daily_stats(monkeypatch)
    heartbeat = []
    sabit_simdi = IST.localize(datetime(2026, 10, 8, 14, 0))  # perşembe, seans içi

    class SabitDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return sabit_simdi.astimezone(tz)
            return sabit_simdi.replace(tzinfo=None)

    monkeypatch.setattr(main_module, "datetime", SabitDatetime)
    donen = sentetik_1h(60, sabit_simdi - pd.Timedelta(hours=8))

    def sahte_1h(stock, period):
        return donen.copy()

    temel_monkeypatch(monkeypatch, live_state, heartbeat, sahte_1h)
    monkeypatch.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_: True)

    mgr = StockDequeManager(data_dir=str(tmp_path / "bot_data"))
    lifecycle = PatternLifecycleManager(profile=config.PROFILE)

    with caplog.at_level("WARNING"):
        result = main_module.scan_all_stocks(
            mgr, lifecycle, FakeNotifier(), stocks=["THYAO"], send_alerts=False
        )

    assert result["status"] == "tamamlandi"
    assert result["processed"] == 1
    assert stats["stale_stocks"] == 1
    assert stats["data_stale"] is True
    assert "formasyonlar eski veriyle hesaplanıyor" in caplog.text
    # data_asof eski mum; Telegram çıktıları bu zamanı 'veri yaşı' ile gösterir.
    beklenen_asof = sabit_simdi - timedelta(hours=8)
    assert datetime.fromisoformat(result["data_asof"]) == beklenen_asof
    satir = main_module._veri_durumu_satiri(
        result["data_asof"], fresh_fetch=1, requested=1, fetch_failures=0,
        oldest_age_minutes=result["oldest_bar_age_minutes"],
    )
    assert "08.10.2026 06:00" in satir and "veri yaşı 8sa" in satir


def test_eski_cache_ve_taze_canli_veri_birlesiminde_canli_kazanir(tmp_path, monkeypatch):
    """Senaryo 4: 20 günlük cache + taze fetch -> append timestamp bazlı birleştirir,
    en yeni mumlar canlı veriden gelir; pencere seçimi 20 gün eski cache'te tam (60d)."""
    live_state = FakeLiveState()
    stats = sifirla_daily_stats(monkeypatch)
    heartbeat = []
    simdi = datetime.now(IST)
    eski_cache = sentetik_1h(55, simdi - pd.Timedelta(days=20), base=50.0)
    taze = sentetik_1h(60, simdi - pd.Timedelta(minutes=100), base=60.0)

    def sahte_1h(stock, period):
        return taze.copy()

    cagri_1h, _ = temel_monkeypatch(monkeypatch, live_state, heartbeat, sahte_1h)
    monkeypatch.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_: False)

    mgr = StockDequeManager(data_dir=str(tmp_path / "bot_data"))
    mgr.append_dataframe("THYAO", eski_cache)
    # 20 gün eski cache 5 günlük tazelik eşiğini aşar -> tam pencere:
    assert main_module.select_yfinance_1h_period(mgr.to_dataframe("THYAO"), simdi) \
        == FULL_1H_FETCH_PERIOD

    lifecycle = PatternLifecycleManager(profile=config.PROFILE)
    result = main_module.scan_all_stocks(
        mgr, lifecycle, FakeNotifier(), stocks=["THYAO"], send_alerts=False
    )

    assert [p for _, p in cagri_1h] == [FULL_1H_FETCH_PERIOD]
    assert result["fresh_fetch"] == 1
    birlesik = mgr.to_dataframe("THYAO")
    assert len(birlesik) == 115                     # 55 eski + 60 taze, kayıp yok
    assert birlesik.index[-1] == pd.Timestamp(taze.index[-1])   # en yeni canlıdan
    assert float(birlesik["close"].iloc[-1]) == float(taze["close"].iloc[-1])
    # Eski geçmiş korunur (pencere içinde): ilk mum hâlâ eski cache'ten.
    assert birlesik.index[0] == pd.Timestamp(eski_cache.index[0])


def test_kismi_basarisizlikta_kapsam_raporlanir(tmp_path, monkeypatch, caplog):
    """Senaryo 5: 22 sembol fetch hatası (20 cache'siz + 2 cache'li) -> işlenen 26;
    durum, heartbeat ve Telegram veri satırı dışa açık biçimde eksik kapsamı verir."""
    live_state = FakeLiveState()
    stats = sifirla_daily_stats(monkeypatch)
    heartbeat = []
    hatali_2 = CACHED_28[:2]
    gercek_heartbeat = main_module.write_heartbeat

    def sahte_1h(stock, period):
        if stock in MISSING_20 or stock in hatali_2:
            return None, False, "sahte ag hatasi"
        return sentetik_1h(60, datetime.now(IST) - pd.Timedelta(minutes=100))

    temel_monkeypatch(monkeypatch, live_state, heartbeat, sahte_1h)
    monkeypatch.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_: True)

    data_dir = tmp_path / "bot_data"
    mgr = StockDequeManager(data_dir=str(data_dir))
    simdi = datetime.now(IST)
    on_yukle(mgr, hatali_2, simdi - pd.Timedelta(minutes=180))  # eski cache -> atlanır
    on_yukle(mgr, CACHED_28[2:], simdi - pd.Timedelta(minutes=60))
    lifecycle = PatternLifecycleManager(profile=config.PROFILE)

    with caplog.at_level("WARNING"):
        result = main_module.scan_all_stocks(
            mgr, lifecycle, FakeNotifier(), send_alerts=False
        )

    assert result["status"] == "basarisiz"
    assert result["requested"] == 48
    assert result["processed"] == 26
    assert result["failed"] == 22
    assert result["fetch_failures"] == 22
    assert stats["fetch_ok"] == 26 and stats["fetch_failures"] == 22

    # Gerçek write_heartbeat, geçici data_dir ile gerçek payload üretir:
    monkeypatch.setattr(config, "DATA_DIR", str(data_dir))
    main_module._deque_manager_ref = mgr
    gercek_heartbeat(notifier=FakeNotifier())
    payload = (data_dir / "heartbeat.json").read_text(encoding="utf-8")
    assert '"fetch_failures": 22' in payload
    assert '"fetch_ok": 26' in payload
    assert '"active_stocks": 48' in payload

    # Telegram komut çıktısındaki veri durumu satırı eksik kapsamı gösterir:
    satir = main_module._veri_durumu_satiri(
        result["data_asof"], fresh_fetch=result["fresh_fetch"],
        requested=result["requested"], fetch_failures=result["fetch_failures"],
        oldest_age_minutes=result["oldest_bar_age_minutes"],
    )
    assert "başarılı fetch 26/48" in satir
    assert "fetch hatası 22" in satir
    assert "Eksik tarama: 26/48" in caplog.text


def test_tek_hisselik_istek_kismi_kapsam_notu_uretir(monkeypatch):
    """/tara THYAO gibi hisse-özel başarılı tarama, komut çıktısında kısmi kapsam
    notuyla işaretlenir (eski evren kayıtları karışmaz)."""
    live_state = FakeLiveState()
    sifirla_daily_stats(monkeypatch)
    temel_monkeypatch(monkeypatch, live_state, [], lambda s, p: None)
    live_state._status.update({
        "son_tarama_durumu": "tamamlandi",
        "son_tarama_beklenen_hisse": 10,
        "son_tarama_hissesi": 10,
    })
    not_ = main_module._kismi_kapsam_notu()
    assert "10/10 hisselik kısmi kapsamdı" in not_


def test_cache_yas_matrisi_sinirlari():
    """_cache_verisi_kullanilabilir sınır matrisi: taze veri her yaşı geçer kılar;
    seans içi 120 dk; seans dışı 14 gün üst sınır."""
    f = main_module._cache_verisi_kullanilabilir
    assert f(8 * 60, True, True) is True            # taze fetch, seans içi sınırı aşan yaşı örter
    assert f(30 * 24 * 60, True, True) is False     # ama 14 günlük üst sınır herkese geçerli
    assert f(60, False, True) is True                # seans içi taze sayılan cache
    assert f(180, False, True) is False              # seans içi eski cache
    assert f(180, False, False) is True              # seans dışı aynı değer kullanılır
    assert f(15 * 24 * 60, False, False) is False    # 14 gün üst sınır
    assert f(14 * 24 * 60 + 1, False, False) is False
