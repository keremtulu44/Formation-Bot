"""Demo render, gerçek cache okuma ve asenkron DM teslimi ayrı sözleşmelerdir."""
import json
import os
import threading
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
    yield n, metinler, fotolar, threadler
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
    monkeypatch.setattr(R, "run_domain_engines", lambda s, tf, frame: cagrilar.append((s, tf)) or {})
    n, metinler, fotolar, threadler = is_ortami
    yanit = M._komut_grafik("SEM 4s sade")
    assert "isteği alındı" in yanit and "sade görünüm" in yanit
    assert not fotolar and not threadler
    bitir(yanit, threadler)
    assert cagrilar == [("SEM", "4h")]
    assert metinler == []                    # başarıda ayrı metin yok (albüm yanıttır)
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
    assert len(fotolar) == 1 and not metinler
    assert (" · sade" in fotolar[0][1]) is (beklenen is True)


def test_eksik_cache_kabulden_sonra_acik_hata(is_ortami):
    n, metinler, fotolar, threadler = is_ortami
    bitir(M._komut_grafik("SEM 4s"), threadler)
    assert "tamamlanamadı" in metinler[-1] and "veri yok" in metinler[-1]
    assert "güvenli bağımsız" in metinler[-1] and not fotolar


def test_eski_cache_sahte_basari_vermez(is_ortami, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(Path(__file__).parent / "bot_data"))
    n, metinler, fotolar, threadler = is_ortami
    bitir(M._komut_grafik("AKBNK 4s"), threadler)
    assert "cache eski" in metinler[-1] and "Bitti" not in metinler[-1]
    assert not fotolar


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
