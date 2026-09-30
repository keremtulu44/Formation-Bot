"""Batch 6: yazma amplifikasyonu (B5), sır hijyeni + rate limit (A7), pickle (A8),
çoklu örnek koruması (B10).

Ağ yok; Supabase yerine sayaçlı sahte store, HTTP yerine doğrudan handler testi.
"""

import json
import threading
from datetime import datetime, timedelta

import pytest

import main as main_mod
from config import ISTANBUL_TZ
from data import StockDequeManager
from health_server import _HealthHandler, start_render_health_server
from notifier import TelegramNotifier
from supabase_store import SupabaseStore


# --- B5: yazma amplifikasyonu --------------------------------------------

class _SayacStore:
    def __init__(self):
        self.istekler = []          # (key, bayt)
    @property
    def istek(self):
        return len(self.istekler)
    @property
    def bayt(self):
        return sum(b for _k, b in self.istekler)
    def upsert(self, key, payload):
        self.istekler.append((key, len(json.dumps(payload, default=str, ensure_ascii=False).encode())))
        return True
    def get_many(self, keys):
        return {}


def _mum(ts, fiyat):
    return {"timestamp": ts, "open": fiyat, "high": fiyat + 1, "low": fiyat - 1,
            "close": fiyat, "volume": 1000}


def _manager(tmp_path, store, hisse=4, bar=40):
    mgr = StockDequeManager(data_dir=str(tmp_path), persistent_store=store)
    taban = datetime(2026, 9, 1, 10, 0, tzinfo=ISTANBUL_TZ)
    for i in range(hisse):
        sym = f"SYM{i}"
        mgr.deques[sym] = type(mgr.deques.get(sym) or __import__("collections").deque())(
            [_mum(taban + timedelta(minutes=35 * j), 100 + j * 0.1) for j in range(bar)],
            maxlen=mgr.maxlen)
        mgr.gunluk_deques[sym] = type(mgr.deques[sym])(
            [_mum(taban + timedelta(days=j), 100 + j) for j in range(30)], maxlen=500)
    return mgr


def test_ayni_icerik_uzak_yazima_gitmez(tmp_path):
    store = _SayacStore()
    mgr = _manager(tmp_path, store)
    for sym in list(mgr.deques):
        mgr.save_to_disk(sym)
        mgr.save_gunluk_to_disk(sym)
    ilk_istek = store.istek
    assert ilk_istek == 8, "ilk yazımda her hisse için 1H + 1D gider"

    store.istekler.clear()
    for sym in list(mgr.deques):          # değişiklik yok → hiç yazım olmamalı
        mgr.save_to_disk(sym)
        mgr.save_gunluk_to_disk(sym)
    assert store.istek == 0
    assert mgr.uzak_yazma_durumu()["atlanan"] == 8


def test_veri_degisince_yalniz_degisen_cache_yazilir(tmp_path):
    store = _SayacStore()
    mgr = _manager(tmp_path, store)
    for sym in list(mgr.deques):
        mgr.save_to_disk(sym)
        mgr.save_gunluk_to_disk(sym)
    store.istekler.clear()
    onceki_yapilan = mgr.uzak_yazma_durumu()["yapilan"]

    sym = "SYM0"
    son = list(mgr.deques[sym])[-1]
    yeni = dict(son, timestamp=son["timestamp"] + timedelta(minutes=35), close=son["close"] + 0.4)
    mgr.deques[sym].append(yeni)
    mgr.save_to_disk(sym)
    mgr.save_gunluk_to_disk(sym)         # günlük seri değişmedi
    assert [k for k, _ in store.istekler] == ["cache:1h:SYM0"]
    assert mgr.uzak_yazma_durumu()["yapilan"] == onceki_yapilan + 1


def test_heartbeat_throttle_ve_dedupe(tmp_path, monkeypatch):
    monkeypatch.setattr(main_mod, "_supabase_store_ref", _SayacStore())
    monkeypatch.setattr(main_mod, "_deque_manager_ref", None)
    monkeypatch.setattr(main_mod, "_son_heartbeat_zamani", 0.0)
    monkeypatch.setattr(main_mod, "_son_heartbeat_icerik", None)
    monkeypatch.setattr(main_mod, "_son_heartbeat_uzak_zamani", 0.0)
    store = main_mod._supabase_store_ref
    n = TelegramNotifier()

    for _ in range(20):                  # per-hisse çağrılar (eski hâlde 20 yazım)
        main_mod.write_heartbeat(data_dir=str(tmp_path), notifier=n)
    assert store.istek == 1, "içerik sabitken Supabase'e tek yazım"
    assert (tmp_path / "heartbeat.json").exists(), "yerel dosya (canlılık) yazılmalı"

    veri = json.loads((tmp_path / "heartbeat.json").read_text(encoding="utf-8"))
    assert "cift_ornek" in veri and "aday_hunisi" in veri


def test_heartbeat_force_ve_icerik_degisimi(tmp_path, monkeypatch):
    monkeypatch.setattr(main_mod, "_supabase_store_ref", _SayacStore())
    monkeypatch.setattr(main_mod, "_deque_manager_ref", None)
    monkeypatch.setattr(main_mod, "_son_heartbeat_zamani", 0.0)
    monkeypatch.setattr(main_mod, "_son_heartbeat_icerik", None)
    monkeypatch.setattr(main_mod, "_son_heartbeat_uzak_zamani", 0.0)
    store = main_mod._supabase_store_ref

    main_mod.write_heartbeat(data_dir=str(tmp_path), force=True)
    main_mod.write_heartbeat(data_dir=str(tmp_path), force=True)
    assert store.istek == 2, "force her çağrıda yazar"

    main_mod.write_heartbeat(data_dir=str(tmp_path), force=False)
    assert store.istek == 2, "throttle penceresinde ek yazım yok"


# --- A8: pickle ----------------------------------------------------------

def test_json_birincil_pickle_yazilmaz(tmp_path, monkeypatch):
    monkeypatch.delenv("PICKLE_CACHE", raising=False)
    mgr = StockDequeManager(data_dir=str(tmp_path))
    mgr.deques["THYAO"] = __import__("collections").deque(
        [_mum(datetime(2026, 9, 1, 10, 0, tzinfo=ISTANBUL_TZ), 100)], maxlen=mgr.maxlen)
    mgr.save_to_disk("THYAO")
    assert (tmp_path / "THYAO.json").exists()
    assert not (tmp_path / "THYAO.pkl").exists(), "varsayılanda pickle yazılmaz"


def test_eski_pickle_yedek_olarak_okunur(tmp_path, monkeypatch):
    import pickle
    from collections import deque
    # C4 seed yedeği devrede olmasın: repo bot_data/ dosyaları testi kirletmesin.
    monkeypatch.setattr("data.SEED_DATA_DIR", str(tmp_path / "seed"))
    mgr = StockDequeManager(data_dir=str(tmp_path))
    veri = [_mum(datetime(2026, 9, 1, 10, 0, tzinfo=ISTANBUL_TZ), 101)]
    (tmp_path / "GARAN.pkl").write_bytes(pickle.dumps(veri))
    dq = mgr.load_from_disk("GARAN")      # JSON yok → pickle yedeği
    assert dq is not None and len(dq) == 1
    assert dq[0]["close"] == 101


def test_seed_yedegi_repo_verisini_okur(tmp_path, monkeypatch):
    """C4: DATA_DIR boşsa repo seed'i (bot_data) yalnız OKUMA için kullanılır."""
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "AKBNK.json").write_text(json.dumps([
        {"timestamp": "2026-09-01T10:00:00+03:00", "open": 1, "high": 2, "low": 0.5,
         "close": 1.5, "volume": 10}
    ]), encoding="utf-8")
    monkeypatch.setattr("data.SEED_DATA_DIR", str(seed))
    mgr = StockDequeManager(data_dir=str(tmp_path / "veri"))
    dq = mgr.load_from_disk("AKBNK")
    assert dq is not None and len(dq) == 1
    assert not (tmp_path / "veri" / "AKBNK.json").exists(), "seed okuması yazmaya dönüşmemeli"


def test_pickle_git_disinda():
    kaynak = open(".gitignore", encoding="utf-8").read()
    assert "bot_data/*.pkl" in kaynak
    # data.py okuma sırası: JSON bloğu pickle bloğundan önce gelmeli
    kod = open("data.py", encoding="utf-8").read()
    assert kod.index("# JSON birincil") < kod.index("eski pickle dosyasından yüklendi")


# --- A7: sır hijyeni + rate limit ---------------------------------------

class _SahteSunucu:
    def __init__(self, test_key="", webhook_secret="", rate_limit=0, handler=None):
        self.test_key = test_key
        self.webhook_secret = webhook_secret
        self.rate_limit_per_min = rate_limit
        self.rate_kayitlari = {}
        self.rate_kilidi = threading.Lock()
        self.test_key_query = True
        self.test_sender = lambda text: (True, "ok")
        self.webhook_handler = handler


def _istek(server, yol, *, method="GET", headers=None, govde=None):
    """_HealthHandler'ı gerçek soket olmadan çalıştırır; dönen: (kod, gövde)."""
    handler = _HealthHandler.__new__(_HealthHandler)
    handler.server = server
    handler.command = method
    handler.path = yol
    handler.headers = headers or {}
    handler.client_address = ("203.0.113.5", 12345)
    handler.rfile = __import__("io").BytesIO(govde or b"")
    yakalanan = {}

    def send_response(code, *a, **k):
        yakalanan["kod"] = code
    def send_header(k, v):
        yakalanan.setdefault("basliklar", {})[k] = v
    def end_headers():
        pass
    def write(data):
        yakalanan["govde"] = data
    handler.send_response = send_response
    handler.send_header = send_header
    handler.end_headers = end_headers
    handler.wfile = type("W", (), {"write": staticmethod(write)})()
    handler.send_error = lambda code, *a, **k: yakalanan.setdefault("kod", code)
    if method == "POST":
        handler.do_POST()
    elif method == "HEAD":
        handler.do_HEAD()
    else:
        handler.do_GET()
    return yakalanan.get("kod"), yakalanan.get("govde")


def test_test_ucu_baslikla_calisir():
    server = _SahteSunucu(test_key="gizli123")
    kod, govde = _istek(server, "/test", headers={"X-Test-Key": "gizli123"})
    assert kod == 200 and json.loads(govde)["ok"] is True

    kod, _ = _istek(server, "/test", headers={"X-Test-Key": "yanlis"})
    assert kod == 403
    kod, _ = _istek(server, "/test")
    assert kod == 403, "anahtarsız istek reddedilmeli"


def test_test_ucu_sorgu_anahtari_kapatilabilir():
    server = _SahteSunucu(test_key="gizli123")
    server.test_key_query = False
    kod, _ = _istek(server, "/test?k=gizli123")
    assert kod == 403, "TELEGRAM_TEST_KEY_QUERY=0 iken ?k= kabul edilmemeli"


def test_webhook_sirsiz_yolda_baslik_zorunlu():
    ortak = {"webhook_secret": "s3cr3t", "handler": lambda u: 200}
    server = _SahteSunucu(**ortak)
    govde = json.dumps({"update_id": 1}).encode()
    basliklar = {"Content-Length": str(len(govde)), "X-Telegram-Bot-Api-Secret-Token": "s3cr3t"}
    kod, _ = _istek(server, "/webhook", method="POST", headers=basliklar, govde=govde)
    assert kod == 200

    kod, _ = _istek(server, "/webhook", method="POST",
                    headers={"Content-Length": str(len(govde))}, govde=govde)
    assert kod == 403, "sırsız yolda başlık yoksa reddedilir"


def test_webhook_eski_yol_geriye_donuk_calisir():
    server = _SahteSunucu(webhook_secret="s3cr3t", handler=lambda u: 200)
    govde = json.dumps({"update_id": 2}).encode()
    # Eski kayıt: sır yolda, başlık yok (secret_token sonradan eklenmiş olabilir)
    kod, _ = _istek(server, "/webhook/s3cr3t", method="POST",
                    headers={"Content-Length": str(len(govde))}, govde=govde)
    assert kod == 200
    kod, _ = _istek(server, "/webhook/yanlis", method="POST",
                    headers={"Content-Length": str(len(govde))}, govde=govde)
    assert kod == 403


def test_webhook_adresi_sir_icermez():
    adres = main_mod._telegram_webhook_url_olustur(secret="s3cr3t", render_url="https://x.onrender.com")
    assert adres == "https://x.onrender.com/webhook"
    assert "s3cr3t" not in adres
    # Eski biçim verilirse olduğu gibi korunur (geriye dönük uyumluluk)
    eski = main_mod._telegram_webhook_url_olustur(
        secret="s3cr3t", webhook_url="https://x.onrender.com/webhook/s3cr3t")
    assert eski == "https://x.onrender.com/webhook/s3cr3t"


def test_rate_limit_429_dondurur():
    server = _SahteSunucu(test_key="gizli123", rate_limit=3)
    kodlar = [_istek(server, "/test", headers={"X-Test-Key": "gizli123"})[0] for _ in range(4)]
    assert kodlar[:3] == [200, 200, 200]
    assert kodlar[3] == 429
    assert len(server.rate_kayitlari["203.0.113.5"]) == 3


def test_rate_limit_env_ile_kapatilir():
    sunucu = start_render_health_server(environ={"PORT": ""}, webhook_secret="x")
    assert sunucu is None  # PORT yok → sunucu başlamaz (yerel mod)


# --- B10: çoklu örnek koruması -------------------------------------------

class _SahteSupabase(SupabaseStore):
    def __init__(self):
        self.kayit = {}
    def get_many(self, keys):
        return {k: self.kayit.get(k) for k in keys}
    def upsert(self, key, payload):
        self.kayit[key] = payload
        return True


def test_ikinci_ornek_gorunur():
    """Tazelik karşılaştırması GERÇEK şimdiye göre yapılır (saat kayması koruması)."""
    store = _SahteSupabase()
    simdi = datetime.now(ISTANBUL_TZ)
    store.ornek_bildir("A", (simdi - timedelta(seconds=10)).isoformat())
    assert store.ornek_bildir("A", simdi.isoformat())["canli_digerleri"] == []

    # B yazar: 10 sn önce görülen A canlıdır
    sonuc = store.ornek_bildir("B", simdi.isoformat())
    assert [d["id"] for d in sonuc["canli_digerleri"]] == ["A"]

    # A'nın kaydı 1 saat öncesine düşerse (bayat) uyarı üretmez; TTL 180 sn
    store.upsert(SupabaseStore.ORNEK_ANAHTARI, {"A": (simdi - timedelta(hours=1)).isoformat()})
    sonuc = store.ornek_bildir("B", simdi.isoformat())
    assert sonuc["canli_digerleri"] == []


def test_main_coklu_ornek_uyarisi_heartbeate_yazilir(tmp_path, monkeypatch):
    store = _SahteSupabase()
    store.kayit[SupabaseStore.ORNEK_ANAHTARI] = {
        "diger-ornek": datetime.now(ISTANBUL_TZ).isoformat(),
    }
    monkeypatch.setattr(main_mod, "_supabase_store_ref", store)
    monkeypatch.setattr(main_mod, "_deque_manager_ref", None)
    monkeypatch.setattr(main_mod, "_cift_ornek_durumu",
                        {"instance_id": "ben", "son_kontrol": None, "canli_digerleri": [], "uyari": False})

    durum = main_mod._tekil_ornek_kontrolu(store, force=True)
    assert durum["uyari"] is True
    assert durum["canli_digerleri"][0]["id"] == "diger-ornek"

    main_mod._son_heartbeat_zamani = 0.0
    main_mod._son_heartbeat_icerik = None
    main_mod._son_heartbeat_uzak_zamani = 0.0
    main_mod.write_heartbeat(data_dir=str(tmp_path), force=True)
    veri = json.loads((tmp_path / "heartbeat.json").read_text(encoding="utf-8"))
    assert veri["cift_ornek"]["uyari"] is True


def test_supabase_erisilemezse_kontrol_sessiz(monkeypatch):
    class _Kirik:
        def ornek_bildir(self, *a, **k):
            raise RuntimeError("supabase yok")
    monkeypatch.setattr(main_mod, "_cift_ornek_durumu",
                        {"instance_id": "ben", "son_kontrol": None, "canli_digerleri": [], "uyari": False})
    durum = main_mod._tekil_ornek_kontrolu(_Kirik(), force=True)
    assert durum["uyari"] is False, "ağ hatası uyarı üretmemeli (yanlış alarm olmasın)"


# --- Batch 8 / C2: raporlama katmanı ayrımı ---------------------------------
def test_reporting_katmani_main_import_etmez():
    """8.1: `reporting/format.py` saf olmalı; main'i (döngü) import etmemeli."""
    import ast
    kaynak = open("reporting/format.py", encoding="utf-8").read()
    agac = ast.parse(kaynak)
    moduller = set()
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            moduller.update(a.name.split(".")[0] for a in dugum.names)
        elif isinstance(dugum, ast.ImportFrom) and dugum.module:
            moduller.add(dugum.module.split(".")[0])
    assert "main" not in moduller
    assert "live_state" not in moduller, "raporlama canlı durumu okumaz, parametre alır"


def test_main_aliaslari_raporlama_katmanini_gosterir():
    """Eski iç adlar korunuyor ama artık reporting'ten geliyor (davranış aynı)."""
    import reporting.format as fmt
    assert main_mod._sayi is fmt.sayi
    assert main_mod._panel_aday_puani is fmt.panel_aday_puani
    assert main_mod._format_deferred_alert_summary is fmt.format_deferred_alert_summary


def test_panel_metinleri_tasima_sonrasi_ayni():
    kayitlar = [
        {"stock": "THYAO", "timeframe": "1h", "pattern_name": "Yükselen Üçgen",
         "state": "KIRILIM_TEYITLI", "quality": 88.0, "critical_price": 312.5,
         "upper_touches": 2, "lower_touches": 2, "contraction": 0.9, "mtf_destek": True},
        {"stock": "GARAN", "timeframe": "1d", "pattern_name": "Flama",
         "state": "SIKISMA_GUCLENIYOR", "quality": 74.0, "critical_price": 55.0,
         "upper_touches": 1, "lower_touches": 1, "contraction": 0.5},
    ]
    ozet = main_mod._format_deferred_alert_summary(kayitlar, toplam=21)
    assert "(2/21 gösteriliyor)" in ozet
    assert "… 19 aday daha (tam liste: /formasyonlar)" in ozet
    satirlar = main_mod._panel_kritik_listesi(kayitlar)
    assert satirlar[0].startswith("🔥 TOP 12")
    assert "THYAO 1h Yükselen Üçgen" in satirlar[1], "kompozit puan sıralaması bozulmamalı"


# --- Batch 8 / C2: import yan etkisi (logging) kaldırıldı --------------------
def _main_agaci():
    import ast
    return ast.parse(open("main.py", encoding="utf-8").read())


def test_setup_logging_import_aninda_cagrilmaz():
    """8.2: `import main` log dizini açmaz; kurulum yalnız main_loop/girişte yapılır."""
    import ast
    agac = _main_agaci()
    for dugum in agac.body:                     # yalnız modül gövdesi (fonksiyonlar hariç)
        if isinstance(dugum, ast.Expr) and isinstance(dugum.value, ast.Call):
            ad = dugum.value.func
            ad = getattr(ad, "id", getattr(ad, "attr", ""))
            assert ad != "setup_logging", "import anında setup_logging() çağrılmamalı"


def test_main_loop_logging_kurulumunu_yapar():
    import ast
    agac = _main_agaci()
    main_loop = next((d for d in ast.walk(agac)
                      if isinstance(d, ast.FunctionDef) and d.name == "main_loop"), None)
    assert main_loop is not None
    cagrilar = [n.func.id for n in ast.walk(main_loop)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert "setup_logging" in cagrilar, "main_loop log kurulumunu yapmalı (yoksa dosyaya log düşmez)"


def test_setup_logging_tekrarlanabilir():
    """İkinci çağrı yeni handler eklememeli (çift log satırı olmasın)."""
    import logging
    main_mod.setup_logging()
    ilk = len(logging.getLogger().handlers)
    main_mod.setup_logging()
    assert len(logging.getLogger().handlers) == ilk


# --- Batch 8 / C2 (8.3): panel raporu bağlam ile üretilir --------------------
def test_panel_katmani_main_ve_live_state_okumaz():
    import ast
    kaynak = open("reporting/panel.py", encoding="utf-8").read()
    moduller = set()
    for dugum in ast.walk(ast.parse(kaynak)):
        if isinstance(dugum, ast.Import):
            moduller.update(a.name.split(".")[0] for a in dugum.names)
        elif isinstance(dugum, ast.ImportFrom) and dugum.module:
            moduller.add(dugum.module.split(".")[0])
    assert "main" not in moduller
    assert "live_state" not in moduller


def test_panel_raporu_baglamla_uretilebilir():
    """8.3: panel metni canlı durum olmadan, açık bağlamla üretilebilir."""
    import reporting.panel as rp
    durum = {"son_tarama_durumu": "tamamlandi", "son_tarama_hissesi": 2,
             "son_tarama_beklenen_hisse": 2}
    formations = [
        {"stock": "THYAO", "timeframe": "1h", "pattern_name": "Yükselen Üçgen",
         "state": "KIRILIM_TEYITLI", "quality": 88.0, "critical_price": 312.5,
         "upper_touches": 2, "lower_touches": 2, "contraction": 0.9, "mtf_destek": True},
    ]
    metin = rp.panel_raporu("", durum, formations, ["THYAO", "GARAN"],
                            bos_analiz_mesaji="ℹ️ boş")
    assert "📋 PANEL — 2 hisse x 4 TF" in metin
    assert "THYAO 1h 88🚀" in metin, "slot hücresi kalite + durum sembolü göstermeli"
    assert "🔥 TOP 12" in metin


def test_main_panel_adaptoru_ayni_metni_uretir(monkeypatch):
    """Adaptör, saf fonksiyonu main bağlamıyla besler (davranış aynı)."""
    import reporting.panel as rp
    monkeypatch.setattr(main_mod, "_kismi_kapsam_notu", lambda: "")
    monkeypatch.setattr(main_mod, "_bos_analiz_mesaji", lambda tamamlandi=False: "ℹ️ boş")
    beklenen = rp.panel_raporu(
        "", main_mod._live_state.status(), main_mod._live_state.formations(),
        list(main_mod.ACTIVE_STOCKS), tarama_suruyor=False,
        last_run_stats=main_mod.last_run_stats, tamamlandi=False,
        kapsam_notu="", bos_analiz_mesaji="ℹ️ boş",
    )
    assert main_mod._panel_raporu("") == beklenen
