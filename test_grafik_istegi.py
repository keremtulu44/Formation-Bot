"""Demo render, gerçek cache okuma ve asenkron DM teslimi ayrı sözleşmelerdir."""
import json
import os
import threading
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
from types import SimpleNamespace

import pytest
import config
import data
import grafik
import grafik_uret as U
import main as M
from telegram_commands import TelegramCommandListener, ArkaPlanYaniti


@pytest.fixture
def is_ortami(monkeypatch, tmp_path):
    metinler, fotolar, threadler = [], [], []
    asil = threading.Thread
    class thread(asil):
        def __init__(self, *args, **kwargs):
            asil.__init__(self, *args, **kwargs)
            if kwargs.get("name") == "grafik-istegi":
                threadler.append(self)
    monkeypatch.setattr(M.threading, "Thread", thread)
    def foto(yol, caption=""):
        assert Path(yol).exists()
        fotolar.append((yol, caption))
        return True, ""
    def toplu(paketler):
        # Üretim `grafik_toplu_gonder` sözleşmesi: kareleri sırayla `grafik_dosya_gonder`
        # ile yollar (test yüzeyi kare başına kaydı tutar) ve her dosyayı siler.
        sonuc = []
        for yol, caption in paketler:
            try:
                ok, _aciklama = n.grafik_dosya_gonder(yol, caption=caption)
            finally:
                try:
                    os.remove(yol)
                except OSError:
                    pass
            sonuc.append(bool(ok))
        return sonuc
    n = SimpleNamespace(enabled=True, token="test-secret",
                        send_text=lambda m: (metinler.append(m) or True, ""),
                        grafik_dosya_gonder=foto, grafik_toplu_gonder=toplu)
    monkeypatch.setattr(M, "_notifier_ref", n)
    monkeypatch.setattr(M, "_deque_manager_ref", None)
    monkeypatch.setattr(grafik, "kare_yolu", lambda *a: str(tmp_path / "tek.png"))
    def yasak(*a, **k):
        pytest.fail("gerçek sağlayıcıya çıkılmamalı")
    for mod in (data, M):
        monkeypatch.setattr(mod, "fetch_yfinance_1h", yasak)
        monkeypatch.setattr(mod, "fetch_yfinance_1d", yasak)
    monkeypatch.setattr(M, "fetch_yfinance_chart_data",
                        lambda *a, **k: (None, False, "testte sağlayıcı kapalı"))
    M._grafik_yenileme_durum.clear()
    yield n, metinler, fotolar, threadler
    M._grafik_yenileme_durum.clear()
    for t in threadler:
        t.join(20)
        assert not t.is_alive()
    M._grafik_aktif_is.clear()


def bitir(yanit, threadler):
    yanit.baslat()
    for t in threadler:
        t.join(20)
        assert not t.is_alive()


def test_dizin_ortak_config_ve_goreli_yol(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATA_DIR", "baska-cwd")  # import sonrası değişim config'i ayırmasın
    assert U._veri_dizini(None) == str(tmp_path)
    assert U._veri_dizini("cache") == str(Path(config.__file__).parent / "cache")


def test_demo_cache_okumaz_yazmaz_png_uretir(monkeypatch, tmp_path):
    def yasak(*a, **k):
        pytest.fail("demo veri katmanına dokunmamalı")
    monkeypatch.setattr(data, "StockDequeManager", yasak)
    sonuc = U.kare_uret("SEM", "4h", demo=True, cikti=str(tmp_path / "demo.png"))
    assert sonuc["kaynak"] == "demo (sentetik)"
    assert Path(sonuc["yol"]).read_bytes().startswith(b"\x89PNG")
    assert not list(tmp_path.glob("*.json"))


def test_demo_bot_data_yazimini_reddeder(tmp_path):
    sonuc = U.kare_uret("SEM", "4h", demo=True,
                       cikti=str(tmp_path / "bot_data" / "demo.png"))
    assert "yazılamaz" in sonuc["hata"]
    assert not (tmp_path / "bot_data").exists()


def test_gercek_cache_aktif_dizini_seedden_once_okur(monkeypatch, tmp_path):
    # Gerçek kayıtlar yalnız tmp'ye kopyalanır; synthetic/gerçek yollar karışmaz.
    raw = json.loads((Path(__file__).parent / "bot_data/AKBNK.json").read_text())
    aktif, seed = tmp_path / "aktif", tmp_path / "seed"
    aktif.mkdir(); seed.mkdir()
    (aktif / "SEM.json").write_text(json.dumps(raw[-80:]))
    (seed / "SEM.json").write_text(json.dumps(raw))
    monkeypatch.setattr(data, "SEED_DATA_DIR", str(seed))
    monkeypatch.setattr(config, "DATA_DIR", str(aktif))
    frame, kaynak = U.cerceve_getir("SEM", "1h", U._veri_dizini(None))
    assert len(frame) == 80 and kaynak == str(aktif / "SEM.json")
    (aktif / "SEM.json").unlink()
    frame, kaynak = U.cerceve_getir("SEM", "1h", str(aktif))
    assert len(frame) == 360 and kaynak == str(seed / "SEM.json")


def test_bellek_disk_olmayan_sembol_icin_kullanilir(is_ortami, monkeypatch, tmp_path):
    from collections import deque
    raw = json.loads((Path(__file__).parent / "bot_data/AKBNK.json").read_text())
    bars, _ = data._temiz_1h_cache_kayitlari(raw)
    yonetici = data.StockDequeManager(data_dir=str(tmp_path / "live"))
    yonetici.deques["SEM"] = deque(bars)
    monkeypatch.setattr(M, "_deque_manager_ref", yonetici)
    monkeypatch.setattr(M, "_cache_verisi_kullanilabilir", lambda *a: True)
    import domain_engines.runner as R
    cagrilar = []
    monkeypatch.setattr(R, "run_domain_engines", lambda s, tf, frame, **kwargs: cagrilar.append((s, tf)) or {})
    n, metinler, fotolar, threadler = is_ortami
    yanit = M._komut_grafik("SEM 4s sade")
    assert "isteği alındı" in yanit and "sade görünüm" in yanit
    assert not fotolar and not threadler
    bitir(yanit, threadler)
    assert cagrilar == [("SEM", "4h")]
    # 2026-10-23: hisse adını taşıyan tek özet metni albümden sonra gider.
    assert len(metinler) == 1 and metinler[0].splitlines()[0] == "📈 SEM · grafik hazır"
    assert len(fotolar) == 1 and not Path(fotolar[0][0]).exists()
    assert fotolar[0][1].startswith("SEM · 4s · sade")
    assert not (tmp_path / "live/SEM.json").exists()


@pytest.mark.parametrize(("arguman", "beklenen"), [
    ("SEM 4s sade", True),
    ("SEM 4s detay", False),
    ("SEM 4s", None),
])
def test_telegram_grafik_gorunum_secimini_ureticiye_aktarir(
        is_ortami, monkeypatch, arguman, beklenen):
    n, metinler, fotolar, threadler = is_ortami
    gorunumler = []

    def uret(_hisse, _tf, **secenekler):
        gorunumler.append(secenekler.get("sade"))
        yol = secenekler["cikti"]
        Path(yol).write_bytes(b"png")
        return {"yol": yol, "meta": {"mum_sayisi": 20,
                                      "son_bar_ts": "2026-10-15T18:00:00+03:00",
                                      "mod": {"sade": secenekler.get("sade") is True}}}

    monkeypatch.setattr(U, "kare_uret", uret)
    bitir(M._komut_grafik(arguman), threadler)
    assert gorunumler == [beklenen]
    assert len(fotolar) == 1 and len(metinler) == 1
    assert metinler[0].splitlines()[0] == "📈 SEM · grafik hazır"
    assert (" · sade" in fotolar[0][1]) is (beklenen is True)


def test_eksik_cache_kabulden_sonra_acik_hata(is_ortami):
    n, metinler, fotolar, threadler = is_ortami
    bitir(M._komut_grafik("SEM 4s"), threadler)
    assert "tamamlanamadı" in metinler[-1] and "veri yok" in metinler[-1]
    assert "Yenileme denemesi" in metinler[-1] and "testte sağlayıcı kapalı" in metinler[-1]
    assert not fotolar


def test_eski_cache_sahte_basari_vermez(is_ortami, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(Path(__file__).parent / "bot_data"))
    n, metinler, fotolar, threadler = is_ortami
    bitir(M._komut_grafik("AKBNK 4s"), threadler)
    assert "cache eski" in metinler[-1] and "Bitti" not in metinler[-1]
    assert not fotolar


def _bist_saatlik_frame(start_date, end_date, now):
    import pandas as pd

    tz = config.ISTANBUL_TZ
    indexes = []
    gun = start_date
    while gun <= end_date:
        if gun.weekday() < 5:
            for saat in range(9, 18):
                ts = tz.localize(datetime.combine(gun, dt_time(saat, 30)))
                if ts + timedelta(hours=1) <= now:
                    indexes.append(ts)
        gun += timedelta(days=1)
    anchor = datetime(2026, 1, 1).date()
    closes = [100.0 + (ts.date() - anchor).days * 0.01 + ts.hour * 0.001
              for ts in indexes]
    return pd.DataFrame({
        "open": [v - 0.02 for v in closes],
        "high": [v + 0.05 for v in closes],
        "low": [v - 0.05 for v in closes],
        "close": closes,
        "volume": [1000.0] * len(closes),
    }, index=pd.DatetimeIndex(indexes))


def _gunluk_test_frame(now):
    import pandas as pd

    tz = config.ISTANBUL_TZ
    last_day = now.date() - timedelta(days=1)
    dates = pd.date_range(end=last_day, periods=45, freq="B", tz=tz)
    closes = [100.0 + sira * 0.1 for sira in range(len(dates))]
    return pd.DataFrame({
        "open": [v - 0.1 for v in closes],
        "high": [v + 0.2 for v in closes],
        "low": [v - 0.2 for v in closes],
        "close": closes,
        "volume": [1000.0] * len(closes),
    }, index=dates)


def test_grafik_tazeletir_1h_bir_kez_ve_2s_4s_ayni_cachei_kullanir(
        is_ortami, monkeypatch, tmp_path):
    from contextlib import contextmanager

    from data import StockDequeManager, tamamlanmis_mumlar

    sabit_now = config.ISTANBUL_TZ.localize(datetime(2026, 11, 5, 14, 35))

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return sabit_now if tz is not None else sabit_now.replace(tzinfo=None)

    monkeypatch.setattr(M, "datetime", FrozenDateTime)
    monkeypatch.setattr(M, "tarama_penceresi_acik_mi", lambda _now: True)
    cache = tmp_path / "grafik-cache"
    cache.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", str(cache))
    manager = StockDequeManager(data_dir=str(cache))
    manager.persistent_store = SimpleNamespace(
        upsert=lambda *_a, **_k: pytest.fail("grafik yenilemesi uzak cache'e yazmamalı"))
    bayat = _bist_saatlik_frame(
        sabit_now.date() - timedelta(days=65),
        sabit_now.date() - timedelta(days=35),
        sabit_now,
    )
    taze = _bist_saatlik_frame(
        sabit_now.date() - timedelta(days=45), sabit_now.date(), sabit_now)
    assert manager.append_dataframe("SEM", bayat)
    assert manager.append_gunluk_dataframe("SEM", _gunluk_test_frame(sabit_now))
    monkeypatch.setattr(M, "_deque_manager_ref", manager)

    calls = []

    def refresh(stock, interval, period, *, frame_validator, request_context):
        calls.append((stock, interval, period))
        assert interval == "1h" and period == "60d"
        kabul, neden = frame_validator(taze)
        assert kabul, neden
        taze.attrs["provider_symbol"] = "SEM.IS"
        return taze, False, ""

    monkeypatch.setattr(M, "fetch_yfinance_chart_data", refresh)
    @contextmanager
    def no_wait(_label=""):
        yield
    monkeypatch.setattr(M, "create_yahoo_pacer", lambda: SimpleNamespace(request=no_wait))

    def kare_uret(hisse, tf, **options):
        frame, source = U.cerceve_getir(
            hisse, tf, options["veri_dizin"], yonetici=options["yonetici"])
        closed = tamamlanmis_mumlar(frame, tf, now=options["simdi"])
        options["tazelik_kontrol"](closed, source)
        Path(options["cikti"]).write_bytes(b"png")
        return {"yol": options["cikti"], "kaynak": source,
                "meta": {"mum_sayisi": len(closed),
                         "son_bar_ts": closed.index[-1].isoformat()}}

    monkeypatch.setattr(U, "kare_uret", kare_uret)
    monkeypatch.setattr(grafik, "kare_yolu", lambda _h, tf: str(cache / f"{tf}.png"))
    n, metinler, fotolar, threadler = is_ortami
    bitir(M._komut_grafik("SEM"), threadler)

    assert calls == [("SEM", "1h", "60d")]
    assert len(fotolar) == 4 and len(metinler) == 1
    assert manager.to_dataframe("SEM").index[-1] == taze.index[-1]
    assert (cache / "SEM.json").exists()
    assert not (cache / "SEM_gunluk.json").exists()


def test_grafik_1d_yaklasik_23_saatlik_gunluk_mumu_bayat_saymaz(monkeypatch):
    import pandas as pd

    tz = config.ISTANBUL_TZ
    son_etiket = tz.localize(datetime(2026, 11, 4, 8, 0))
    kapanis = M.mum_kapanis_ani(son_etiket, "1d")
    simdi = kapanis + timedelta(minutes=1388)
    indexes = pd.DatetimeIndex([son_etiket - timedelta(days=1), son_etiket])
    frame = pd.DataFrame({
        "open": [1.0, 1.0], "high": [1.1, 1.1], "low": [0.9, 0.9],
        "close": [1.0, 1.0], "volume": [100.0, 100.0],
    }, index=indexes)
    monkeypatch.setattr(M, "tarama_penceresi_acik_mi", lambda _now: True)

    durum = M._grafik_cache_tazelik_durumu(frame, "1d", simdi)
    assert durum["yas_dk"] == pytest.approx(1388.0)
    assert durum["taze"]
    assert M._grafik_tazelik_esigi_dk("1d", True) == 1560
    assert M._grafik_tazelik_esigi_dk("1h", True) == 120


def test_grafik_tazeleme_1d_ayri_derin_cachei_yazar(monkeypatch, tmp_path):
    import pandas as pd

    from data import StockDequeManager

    tz = config.ISTANBUL_TZ
    simdi = tz.localize(datetime(2026, 11, 5, 14, 35))
    manager = StockDequeManager(data_dir=str(tmp_path))
    manager.persistent_store = SimpleNamespace(
        upsert=lambda *_a, **_k: pytest.fail("grafik yenilemesi uzak cache'e yazmamalı"))
    dates = pd.date_range(end=simdi.date(), periods=90, freq="D", tz=tz) + timedelta(hours=8)

    def gunluk_frame(indexes, start=30.0):
        closes = [start + sira * 0.01 for sira in range(len(indexes))]
        return pd.DataFrame({
            "open": [v - 0.02 for v in closes], "high": [v + 0.05 for v in closes],
            "low": [v - 0.05 for v in closes], "close": closes,
            "volume": [0.0] * len(closes),
        }, index=indexes)

    manager.append_gunluk_dataframe("XAGUSD", gunluk_frame(dates[:-1]))
    calls = []

    def refresh(stock, interval, period, *, frame_validator, request_context):
        calls.append((stock, interval, period))
        assert frame_validator(gunluk_frame(dates))[0]
        return gunluk_frame(dates), False, ""

    monkeypatch.setattr(M, "fetch_yfinance_chart_data", refresh)
    result = M._grafik_tazele("XAGUSD", "1d", manager, now=simdi)

    assert result["ok"] and result["persisted"]
    assert calls == [("XAGUSD", "1d", config.GUNLUK_FETCH_PERIOD)]
    assert manager.to_gunluk_dataframe("XAGUSD").index[-1] == dates[-1]
    assert (tmp_path / "XAGUSD_gunluk.json").exists()
    assert not (tmp_path / "XAGUSD.json").exists()


def test_grafik_yenileme_hatasi_iki_dakika_sogutulur(monkeypatch, tmp_path):
    from data import StockDequeManager

    manager = StockDequeManager(data_dir=str(tmp_path))
    calls = []
    monkeypatch.setattr(M, "fetch_yfinance_chart_data",
                        lambda *a, **k: calls.append(a) or (None, False, "test hata"))
    M._grafik_yenileme_durum.clear()

    ilk = M._grafik_tazele("COOLDOWN", "1h", manager)
    ikinci = M._grafik_tazele("COOLDOWN", "4h", manager)

    assert not ilk["ok"] and "test hata" in ilk["detail"]
    assert not ikinci["ok"] and "bekleme sınırı" in ikinci["detail"]
    assert len(calls) == 1
    M._grafik_yenileme_durum.clear()


def test_cakisan_istekler_ve_farkli_is_sinirli(is_ortami):
    ilk = M._komut_grafik("SEM 4s")
    assert isinstance(ilk, ArkaPlanYaniti)
    assert "zaten" in M._komut_grafik("SEM 4h")
    assert "Başka grafik" in M._komut_grafik("THYAO 1s")
    assert "zaten" in M._komut_grafik("SEM")


@pytest.mark.parametrize("sonuc", ["foto_hata", "foto_istisna", "uretim_istisna", "red"])
def test_hata_yollarinda_png_temizlenir(is_ortami, monkeypatch, sonuc):
    n, metinler, fotolar, threadler = is_ortami
    def uret(s, tf, **k):
        Path(k["cikti"]).write_bytes(b"png")
        if sonuc == "uretim_istisna":
            raise RuntimeError("üretim patladı")
        return {"yol": None if sonuc == "red" else k["cikti"],
                "meta": {"uyarilar": ["çizim reddi"]}}
    monkeypatch.setattr(U, "kare_uret", uret)
    def foto(*a, **k):
        if sonuc == "foto_istisna":
            raise RuntimeError("foto patladı")
        return False, "HTTP 400 test-secret"
    n.grafik_dosya_gonder = foto
    bitir(M._komut_grafik("SEM 4s"), threadler)
    assert not Path(grafik.kare_yolu("SEM", "4h")).exists()
    assert "tamamlanamadı" in metinler[-1] and "Bitti" not in metinler[-1]
    assert "test-secret" not in metinler[-1]


def test_hedef_asiminda_asama_bildirilir_listener_bloklanmaz(is_ortami, monkeypatch):
    n, metinler, fotolar, threadler = is_ortami
    girdi, birak, gecikme = threading.Event(), threading.Event(), threading.Event()
    asil_send = n.send_text
    def send(m):
        r = asil_send(m)
        if "hedefi aşıldı" in m:
            gecikme.set()
        return r
    n.send_text = send
    def uret(s, tf, **k):
        k["asama"]("testte yavaş motor")
        girdi.set()
        assert birak.wait(5)
        return {"yol": None, "hata": "test veri hatası"}
    monkeypatch.setattr(U, "kare_uret", uret)
    monkeypatch.setattr(M, "_GRAFIK_HEDEF_SN", .02)
    yanit = M._komut_grafik("SEM 4s")
    yanit.baslat()
    try:
        assert girdi.wait(5) and gecikme.wait(5)
        assert "testte yavaş motor" in metinler[0] and "henüz bitmedi" in metinler[0]
        assert "Bitti" not in metinler[0]
    finally:
        birak.set()
        for t in threadler:
            t.join(10)
    assert "tamamlanamadı" in metinler[-1]


def test_listener_kabul_tesliminden_sonra_baslatir_ve_retry_tekildir(is_ortami, monkeypatch):
    n, metinler, fotolar, threadler = is_ortami
    siralama = []
    teslim = [False, True]
    def sender(update_id, text):
        siralama.append("kabul")
        return teslim.pop(0)
    monkeypatch.setattr(M, "_grafik_isi_calistir", lambda *a: siralama.append("iş"))
    listener = TelegramCommandListener("test", "42", {"grafik": M._komut_grafik},
        response_sender=sender, komutlari_yoksay=lambda: True)
    update = {"update_id": 7, "message": {"chat": {"id": 42}, "text": "/grafik SEM 4s"}}
    assert listener.handle_update(update) is None
    assert not threadler and siralama == ["kabul"]
    assert "isteği alındı" in listener.handle_update(update)
    for t in threadler:
        t.join(5)
    assert siralama == ["kabul", "kabul", "iş"]
    listener.handle_update(update)
    assert len(threadler) == 1



def test_bolge_gorunumu_ve_mobil_ureticiye_aktarilir(is_ortami, monkeypatch):
    import grafik_uret
    calls = []
    def uret(_hisse, _tf, **options):
        calls.append(options)
        Path(options["cikti"]).write_bytes(b"png")
        return {"yol": options["cikti"], "meta": {"mum_sayisi": 20}}
    monkeypatch.setattr(grafik_uret, "kare_uret", uret)
    _n, _metin, photos, threads = is_ortami
    bitir(M._komut_grafik("SEM 4s baglam mobil"), threads)
    assert calls[0]["gorunum"] == "baglam" and calls[0]["mobil"] is True
    assert len(photos) == 1
