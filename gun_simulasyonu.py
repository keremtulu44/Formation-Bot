#!/usr/bin/env python3
"""1 GÜNLÜK SİMÜLASYON (replay) — botu gerçek cache verisiyle baştan sona çalıştırır.

Ne yapar:
  * `bot_data/` içindeki GERÇEK 1H barları kullanılır (ağ yok, Yahoo yok).
  * Seçilen işlem günü saat 09:00'dan 20:10'a kadar SANAL saat ilerletilir:
    her mum kapanışında gerçek `main_loop` taraması çalışır, 09:55 sabah notu,
    18:45 kapanış özeti ve 20:00 gün sonu analizi gerçek kod yollarından geçer.
  * Telegram'a giden HER mesaj (DM + grup) yakalanır; ağa hiç çıkılmaz.
  * Sonuçta: kaç mesaj çıktı, hangi saatte, hangi formatta → Markdown rapor.

Kullanım:
    .venv/bin/python gun_simulasyonu.py                      # cache'teki son gün
    .venv/bin/python gun_simulasyonu.py --gun 2026-09-25
    .venv/bin/python gun_simulasyonu.py --gun 2026-09-25 --cikti rapor.md
    .venv/bin/python gun_simulasyonu.py --liste              # cache'teki günler

Neden ayrı bir araç: canlı bot saatler sürer ve ağa bağlıdır; bu araç aynı kod
yollarını sanal saatle dakikalar içinde koşturur, böylece "günde kaç mesaj
çıkıyor, formatlar nasıl görünüyor" sorusu ölçümle yanıtlanır.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
import time
import types
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

REPO = Path(__file__).resolve().parent
ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")   # config import'undan bağımsız (env kuralı)
CACHE_DIR = REPO / "bot_data"
TUM_TF = ("1h", "2h", "4h", "1d")

# --- sanal saat -------------------------------------------------------------

_GERCEK_DATETIME = datetime
_SIMDI: list[datetime] = [datetime(2026, 9, 25, 9, 0)]
_BITIS: list[datetime] = [datetime(2026, 9, 25, 20, 10)]
_DURDUR = {"fn": None, "adim_sayaci": 0, "azami_adim": 400_000}
_HIZ = [10.0]   # gerçek uykular sanal saatte HIZ katı hızlı ilerler


class SanalDatetime(_GERCEK_DATETIME):
    """datetime.now() sanal saat döndürür; diğer tüm davranış gerçek datetime."""

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        simdi = _SIMDI[0]
        if tz is None:
            return simdi.replace(tzinfo=None)
        return simdi.astimezone(tz)

    @classmethod
    def utcnow(cls):  # type: ignore[override]
        return _SIMDI[0].astimezone(timezone.utc).replace(tzinfo=None)

    @classmethod
    def today(cls):  # type: ignore[override]
        return cls.now()


def sanal_zaman_kur() -> None:
    """Yüklü TÜM modüllerde `datetime`/`time` referanslarını sanal saate bağlar."""
    import datetime as dt_mod

    dt_mod.datetime = SanalDatetime  # `import datetime; datetime.datetime.now()`
    for mod in list(sys.modules.values()):
        if getattr(mod, "datetime", None) is _GERCEK_DATETIME:
            setattr(mod, "datetime", SanalDatetime)

    gercek_sleep = time.sleep

    def sanal_sleep(sn):
        try:
            sn = float(sn)
        except (TypeError, ValueError):
            sn = 0.0
        _SIMDI[0] = _SIMDI[0] + timedelta(seconds=sn * _HIZ[0])
        _DURDUR["adim_sayaci"] += 1
        if _SIMDI[0] >= _BITIS[0] or _DURDUR["adim_sayaci"] > _DURDUR["azami_adim"]:
            if _DURDUR["fn"] is not None:
                _DURDUR["fn"]()
        if sn > 3600:  # çok uzun beklemelerde CPU'yu boşa yakma
            gercek_sleep(0.001)

    time.sleep = sanal_sleep
    time.time = lambda: _SIMDI[0].timestamp()  # type: ignore[assignment]
    time.monotonic = lambda: _SIMDI[0].timestamp()  # type: ignore[assignment]


# --- telegram kaydedici (ağ yok) -------------------------------------------

class Yanit:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"ok": True, "result": True}
        self.text = json.dumps(self._payload, ensure_ascii=False)

    def json(self):
        return self._payload


class Kayitci:
    def __init__(self, dm_id: str, grup_id: str):
        self.dm_id = dm_id
        self.grup_id = grup_id
        self.mesajlar: list[dict] = []      # gerçekten gönderilenler
        self.ham_istekler: list[dict] = []

    def _hedef(self, chat_id) -> str:
        cid = str(chat_id or "")
        if cid == str(self.dm_id):
            return "DM"
        if cid == str(self.grup_id):
            return "GRUP"
        return f"BILINMEYEN({cid})"

    def post(self, url, json=None, params=None, timeout=None, **kw):
        govde = dict(json or params or {})
        if "sendMessage" in str(url):
            self.mesajlar.append({
                "zaman": _SIMDI[0],
                "hedef": self._hedef(govde.get("chat_id")),
                "metin": govde.get("text", ""),
            })
        else:
            self.ham_istekler.append({"url": str(url), "govde": govde})
        return Yanit(200, {"ok": True, "result": {"message_id": len(self.mesajlar)}})

    def get(self, url, params=None, timeout=None, **kw):
        if "getMe" in str(url):
            return Yanit(200, {"ok": True, "result": {"username": "simulasyon_bot", "id": 1}})
        # getUpdates: boş sonuç (komut katmanı simülasyonda kapalı ama olsa da ağ yok)
        return Yanit(200, {"ok": True, "result": []})


class SahteSession:
    def __init__(self, kayitci: Kayitci):
        self._k = kayitci

    def post(self, url, json=None, params=None, timeout=None, **kw):
        return self._k.post(url, json=json, params=params, timeout=timeout)

    def get(self, url, params=None, timeout=None, **kw):
        return self._k.get(url, params=params, timeout=timeout)

    def close(self):
        return None


def requests_yamasi(kayitci: Kayitci):
    mod = types.ModuleType("requests")
    mod.post = kayitci.post
    mod.get = kayitci.get
    mod.Session = lambda: SahteSession(kayitci)

    class RequestException(Exception):
        pass

    mod.RequestException = RequestException
    mod.exceptions = types.SimpleNamespace(RequestException=RequestException,
                                           Timeout=RequestException,
                                           ConnectionError=RequestException)
    sys.modules["requests"] = mod
    return mod


# --- veri beslemesi --------------------------------------------------------

class Feed:
    """Cache'teki 1H barları, SANAL saate göre 'şimdiye kadar kapanmış' olanları verir."""

    def __init__(self):
        self.cache: dict[str, pd.DataFrame] = {}
        self._yukle()

    def _yukle(self):
        import config  # noqa: F401  (DATA_DIR env'i import'tan önce kuruldu)

        eksik = []
        for dosya in sorted(CACHE_DIR.glob("*.json")):
            stock = dosya.stem
            try:
                ham = json.loads(dosya.read_text(encoding="utf-8"))
            except Exception:
                continue
            satirlar = []
            for c in ham:
                try:
                    satirlar.append({
                        "timestamp": pd.Timestamp(c["timestamp"]),
                        "open": float(c["open"]), "high": float(c["high"]),
                        "low": float(c["low"]), "close": float(c["close"]),
                        "volume": float(c.get("volume") or 0),
                    })
                except Exception:
                    continue
            if len(satirlar) < 50:
                eksik.append(stock)
                continue
            df = pd.DataFrame(satirlar).set_index("timestamp").sort_index()
            if df.index.tz is None:
                df.index = df.index.tz_localize("Europe/Istanbul")
            else:
                df.index = df.index.tz_convert("Europe/Istanbul")
            self.cache[stock] = df
        if eksik:
            logging.warning("Cache'i kısa olan hisseler atlandı: %s", ", ".join(eksik))

    def gunler(self) -> list[date]:
        gunler = set()
        for df in self.cache.values():
            gunler.update({ts.date() for ts in df.index})
        return sorted(gunler)

    def _kesit(self, df: pd.DataFrame, tf: str, simdi: datetime) -> pd.DataFrame:
        from data import mum_kapanis_anlari

        # Naive verilirse İstanbul'a sabitle (Default saat dilimi karşılaştırması
        # tz-aware endeksle TypeError verirdi).
        if simdi.tzinfo is None:
            simdi = simdi.replace(tzinfo=ISTANBUL_TZ)
        kapanislar = mum_kapanis_anlari(df.index, tf)
        return df[kapanislar <= pd.Timestamp(simdi)]

    def fetch_1h(self, stock, period=None, with_status=False):
        df = self.cache.get(stock)
        if df is None:
            return (None, False, "cache yok") if with_status else None
        kesit = self._kesit(df, "1h", _SIMDI[0])
        if len(kesit) < 50:
            return (None, False, "yeterli bar yok") if with_status else None
        return (kesit, False, "") if with_status else kesit

    def fetch_last_bar(self, stock):
        df = self.cache.get(stock)
        if df is None:
            return None
        kesit = self._kesit(df, "1h", _SIMDI[0])
        return None if kesit.empty else kesit.tail(30)

    def fetch_1d(self, stock, period=None):
        from data import mum_kapanis_anlari, resample_ohlcv

        df = self.cache.get(stock)
        if df is None:
            return None
        gunluk = resample_ohlcv(df, "1D")
        kesit = self._kesit(gunluk, "1d", _SIMDI[0])
        return kesit if len(kesit) >= 30 else None

    def tohumla(self, data_dir: Path, gun: date) -> int:
        """DATA_DIR'e 'sim günü ÖNCESİ' barları yazar (gelecek veri sızmasın)."""
        yazilan = 0
        for stock, df in self.cache.items():
            gecmis = df[df.index.date < gun]
            if len(gecmis) < 50:
                continue
            kayitlar = []
            for ts, row in gecmis.iterrows():
                kayitlar.append({
                    "timestamp": ts.isoformat(),
                    "open": float(row["open"]), "high": float(row["high"]),
                    "low": float(row["low"]), "close": float(row["close"]),
                    "volume": float(row["volume"]),
                })
            (data_dir / f"{stock}.json").write_text(
                json.dumps(kayitlar, ensure_ascii=False), encoding="utf-8")
            yazilan += 1
        return yazilan


class HizliPacer:
    """Canlı pacing'i (Yahoo) atlar: simülasyonda ağ yok, beklemenin anlamı yok."""

    class _Ctx:
        def __enter__(self):
            return None

        def __exit__(self, *a):
            return False

    def request(self, ad=None):
        return HizliPacer._Ctx()

    def reset_batch(self):
        return None

    def __getattr__(self, ad):
        return lambda *a, **k: None


# --- simülasyon ------------------------------------------------------------

def simule_et(args) -> dict:
    # ÖNEMLİ: config DATA_DIR'i import anında sabitler; env en başta kurulmalı.
    if args.veri_dir:
        gecici = Path(args.veri_dir)
        gecici.mkdir(parents=True, exist_ok=True)
    else:
        gecici = Path(tempfile.mkdtemp(prefix="sim-bot-"))
    dm_id = "42424242"
    grup_id = "-1009999999999"
    os.environ.update({
        "DATA_DIR": str(gecici / "data"),
        "SEED_DATA_DIR": str(gecici / "data"),   # repo seed'i (tam cache) sızmasın
        "TELEGRAM_BOT_TOKEN": "1234567890:SIMULASYONsimulasyonSIMULASYON1234567",
        "TELEGRAM_CHAT_ID": dm_id,
        "TELEGRAM_GROUP_ID": grup_id,
        "BOT_PROFILE": os.environ.get("BOT_PROFILE", "Dengeli"),
        "LOG_LEVEL": args.log_seviyesi,
    })
    os.environ.pop("TELEGRAM_CHANNEL_ID", None)
    os.environ.pop("TELEGRAM_WEBHOOK_SECRET", None)
    for anahtar in list(os.environ):
        if anahtar.startswith("SUPABASE"):
            os.environ.pop(anahtar, None)
    (gecici / "data").mkdir(parents=True, exist_ok=True)

    feed = Feed()
    gunler = feed.gunler()
    if not feed.cache:
        raise SystemExit("bot_data/ içinde kullanılabilir cache yok.")
    if args.liste:
        print("Cache'teki işlem günleri:")
        for g in gunler:
            print(f"  {g}  ({'son gün' if g == gunler[-1] else ''})")
        raise SystemExit(0)

    gun = date.fromisoformat(args.gun) if args.gun else gunler[-1]
    if gun not in gunler:
        raise SystemExit(f"{gun} cache'te yok. --liste ile günleri görebilirsin.")
    baslangic = datetime.combine(gun, datetime.strptime(args.baslangic, "%H:%M").time())
    bitis = datetime.combine(gun, datetime.strptime(args.bitis, "%H:%M").time())

    tohum = feed.tohumla(gecici / "data", gun)

    # --- modüller (env'den SONRA) ---
    import config
    import data as data_mod
    import main as main_mod
    import notifier as notifier_mod

    # Evren: cache'i olmayan hisseler (ağ yok) simde analiz edilemez. Varsayılan
    # olarak yalnız cache kapsamındaki hisselerle koşarız ki gün, üretimdeki
    # "tüm hisseler geldi" durumuna benzesin. --evren tum ile 48 hisse zorlanır.
    evren_notu = ""
    if args.evren == "cache" and feed.cache:
        kullanilabilir = [s_ for s_ in config.ACTIVE_STOCKS if s_ in feed.cache]
        if kullanilabilir and len(kullanilabilir) != len(config.ACTIVE_STOCKS):
            orijinal = config.ACTIVE_STOCKS
            for mod in list(sys.modules.values()):
                if getattr(mod, "ACTIVE_STOCKS", None) is orijinal:
                    setattr(mod, "ACTIVE_STOCKS", kullanilabilir)
            config.ACTIVE_STOCKS = kullanilabilir
            evren_notu = (f"cache kapsamı {len(kullanilabilir)}/"
                          f"{len(orijinal)} hisse (eksikler ağ olmadığı için dışarıda)")

    config.DATA_DIR = str(gecici / "data")
    config.SEED_DATA_DIR = str(gecici / "data")  # seed sızmasını kapat

    kayitci = Kayitci(dm_id, grup_id)
    requests_yamasi(kayitci)

    _SIMDI[0] = config.ISTANBUL_TZ.localize(baslangic)
    _BITIS[0] = config.ISTANBUL_TZ.localize(bitis)
    _HIZ[0] = max(1.0, float(args.hiz))
    sanal_zaman_kur()

    # Ağ katmanları: veri beslemesi + pacing + komut/webhook katmanı kapatılır.
    main_mod.fetch_yfinance_1h = feed.fetch_1h
    main_mod.fetch_yfinance_1d = feed.fetch_1d
    main_mod.fetch_last_bar = feed.fetch_last_bar
    main_mod.create_yahoo_pacer = lambda: HizliPacer()
    main_mod._telegram_komut_katmanini_kur = lambda notifier, isleyici=None: "kapali"
    # Ana döngünün beklemesi Event.wait ile 1 sn'lik dilimlerde yapılıyor (gerçek
    # zaman). Simülasyonda bekleme = sanal saatin ilerlemesi; gerçek CPU beklemez.
    def _sanal_bekle(saniye, *a, **k):
        _SIMDI[0] = _SIMDI[0] + timedelta(seconds=float(saniye or 0) * _HIZ[0])
        _DURDUR["adim_sayaci"] += 1
        if _SIMDI[0] >= _BITIS[0] or _DURDUR["adim_sayaci"] > _DURDUR["azami_adim"]:
            if _DURDUR["fn"] is not None:
                _DURDUR["fn"]()
        return False

    main_mod._bekle_veya_tarama = _sanal_bekle
    main_mod._telegram_set_webhook = lambda *a, **k: False
    main_mod._telegram_delete_webhook = lambda *a, **k: False
    data_mod.fetch_yfinance_1h = feed.fetch_1h
    data_mod.fetch_yfinance_1d = feed.fetch_1d

    log_yolu = Path(args.log) if args.log else (gecici / "simulasyon.log")
    _log_kur(log_yolu, args.log_seviyesi)

    # --- koşum ---
    main_mod._shutdown_requested = False
    _DURDUR["fn"] = lambda: setattr(main_mod, "_shutdown_requested", True)
    _DURDUR["adim_sayaci"] = 0

    basladi = time.time()  # NOT: yamadan sonra bu sanal saat; gerçek süre ayrı ölçülür
    gercek_baslangic = _GERCEK_DATETIME.now()
    hata = None
    try:
        main_mod.main_loop()
    except SystemExit:
        pass
    except Exception as exc:  # noqa: BLE001 - simülasyon hatası raporlansın
        hata = f"{type(exc).__name__}: {exc}"
        logging.exception("Simülasyon çöktü")
    gercek_sure = (_GERCEK_DATETIME.now() - gercek_baslangic).total_seconds()

    # --- rapor ---
    ds = dict(main_mod.daily_stats)
    try:
        nd = main_mod._notifier_ref.gonderim_durumu()
    except Exception:
        nd = {}
    rapor = _rapor_yaz(args, kayitci, feed, gun, baslangic, bitis, ds, nd,
                       tohum, log_yolu, gercek_sure, hata, len(config.ACTIVE_STOCKS),
                       evren_notu, str(gecici / "data"))
    return rapor


def _log_kur(log_yolu: Path, seviye: str) -> None:
    log_yolu.parent.mkdir(parents=True, exist_ok=True)
    kok = logging.getLogger()
    kok.handlers = []
    kok.setLevel(logging.DEBUG)
    dosya = logging.FileHandler(log_yolu, encoding="utf-8")
    dosya.setLevel(logging.DEBUG)
    dosya.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    kok.addHandler(dosya)
    konsol = logging.StreamHandler(sys.stderr)
    konsol.setLevel(getattr(logging, seviye.upper(), logging.WARNING))
    konsol.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    kok.addHandler(konsol)


def _mesaj_turu(hedef: str, metin: str) -> str:
    ilk = (metin or "").splitlines()[0] if metin else ""
    if hedef == "GRUP":
        if "Formasyon bülteni" in ilk:
            return "GRUP bülten"
        if "kapanış" in ilk or "sabah notu" in ilk:
            return "GRUP özet"
        return "GRUP diğer"
    if "Günlük Özet" in ilk:
        return "DM özet"
    if "GÜN SONU ANALİZİ" in ilk:
        return "DM gün sonu panel"
    if "TARAMA" in ilk.upper():
        return "DM tarama raporu"
    return "DM alarm"


def _rapor_yaz(args, kayitci: Kayitci, feed: Feed, gun: date, baslangic: datetime,
               bitis: datetime, ds: dict, nd: dict, tohum: int, log_yolu: Path,
               gercek_sure: float, hata, hisse_sayisi: int, evren_notu: str = "",
               veri_dir: str = "") -> dict:
    satirlar: list[str] = []
    ekle = satirlar.append
    mesajlar = kayitci.mesajlar
    dm = [m for m in mesajlar if m["hedef"] == "DM"]
    grup = [m for m in mesajlar if m["hedef"] == "GRUP"]

    ekle(f"# 1 Günlük Simülasyon Raporu — {gun.strftime('%d.%m.%Y')}")
    ekle("")
    ekle(f"- **Pencere:** {baslangic:%H:%M} → {bitis:%H:%M} (sanal saat)")
    ekle(f"- **Evren:** {hisse_sayisi} hisse × 4 zaman dilimi (1h/2h/4h/1d), cache: `bot_data/`")
    if evren_notu:
        ekle(f"- **Evren kapsamı:** {evren_notu}")
    if veri_dir:
        ekle(f"- **Sim veri dizini:** `{veri_dir}` (günler zincirlenebilsin diye korunur)")
    ekle(f"- **Tohumlanan geçmiş:** {tohum} hisse (sim günü öncesi barlar)")
    ekle(f"- **Gerçek çalışma süresi:** {gercek_sure:.1f} sn · log: `{log_yolu}`")
    ekle(f"- **Mod:** ağ yok — Telegram çağrıları yakalandı, Yahoo yerine cache beslemesi")
    if hata:
        ekle(f"- ⚠️ **Simülasyon hatası:** {hata}")
    ekle("")

    ekle("## 1) Mesaj sayıları")
    ekle("")
    ekle("| Kanal | Adet |")
    ekle("|---|---|")
    ekle(f"| **Telegram DM (kişisel)** | **{len(dm)}** |")
    ekle(f"| **Public grup** | **{len(grup)}** |")
    ekle(f"| Toplam | {len(mesajlar)} |")
    ekle("")
    turler: dict[str, int] = {}
    for m in mesajlar:
        t = _mesaj_turu(m["hedef"], m["metin"])
        turler[t] = turler.get(t, 0) + 1
    if turler:
        ekle("Tür bazında:")
        ekle("")
        ekle("| Tür | Adet |")
        ekle("|---|---|")
        for t, n in sorted(turler.items(), key=lambda x: -x[1]):
            ekle(f"| {t} | {n} |")
        ekle("")

    # Saatlik dağılım + grup bütçe kontrolü
    ekle("## 2) Saatlik dağılım (grup bütçesi ≤6/saat, ≤25/gün)")
    ekle("")
    ekle("| Saat | DM | Grup |")
    ekle("|---|---|---|")
    saatler = {}
    for m in mesajlar:
        s = m["zaman"].strftime("%H")
        d = saatler.setdefault(s, {"DM": 0, "GRUP": 0})
        d[m["hedef"]] = d.get(m["hedef"], 0) + 1
    for s in sorted(saatler):
        ekle(f"| {s}:00 | {saatler[s].get('DM', 0)} | {saatler[s].get('GRUP', 0)} |")
    ekle("")
    en_yogun = max((v.get("GRUP", 0) for v in saatler.values()), default=0)
    ekle(f"- En yoğun saatte grup mesajı: **{en_yogun}** "
         f"({'✅ sınır içinde' if en_yogun <= 6 else '❌ SINIR AŞILDI'})")
    ekle(f"- Günlük grup toplamı: **{len(grup)}** "
         f"({'✅ sınır içinde' if len(grup) <= 25 else '❌ SINIR AŞILDI'})")
    ekle("")

    ekle("## 3) Botun sayaçları (gün sonu)")
    ekle("")
    ekle("| Sayaç | Değer |")
    ekle("|---|---|")
    for anahtar in ("tarama_sayisi", "stocks_scanned", "alerts_attempted", "alerts_sent",
                    "alerts_deferred", "alerts_below_threshold", "alerts_engel_cooldown",
                    "alerts_engel_kap", "alerts_engel_tekrar", "alerts_kuyruk",
                    "fetch_ok", "fetch_failures", "max_bar_age_min", "errors"):
        if anahtar in ds:
            ekle(f"| {anahtar} | {ds.get(anahtar)} |")
    for anahtar in ("public_gonderilen", "public_hatasi", "public_engel", "public_kuyruk",
                    "public_kuyruk_tasmasi", "gonderilen", "engellenen", "hata"):
        if anahtar in nd:
            ekle(f"| notifier:{anahtar} | {nd.get(anahtar)} |")
    ekle("")

    # Grup içerik denetimi: onaylanan politikada gruba GİTMEMESİ gerekenler
    YASAK = ["/panel", "/durum", "/tara", "/karne", "defter", "📁", "MOCK",
             "Diğer izleme adayları", "kuyruk", "Traceback", "None",
             "alarm eşiğinin altında", "saatlik kap", "cooldown"]
    ihlaller = []
    for m in grup:
        for y in YASAK:
            if y.lower() in m["metin"].lower():
                ihlaller.append((m["zaman"], y, m["metin"].splitlines()[0][:60]))
    ekle("## 4) Grup içerik denetimi (yasaklı içerik)")
    ekle("")
    ekle("Grup mesajlarında aranan yasaklı ifadeler: "
         + ", ".join(f"`{y}`" for y in YASAK))
    ekle("")
    if ihlaller:
        ekle(f"❌ **{len(ihlaller)} ihlal bulundu:**")
        ekle("")
        for z, y, ilk in ihlaller:
            ekle(f"- {z:%H:%M:%S} · `{y}` · {ilk}")
    else:
        ekle("✅ **İhlal yok** — grup mesajlarında iç işletim/teknik içerik çıkmadı.")
    ekle("")

    ekle("## 5) Kronolojik akış")
    ekle("")
    ekle("| Saat | Kanal | Tür | Uzunluk | İlk satır |")
    ekle("|---|---|---|---|---|")
    for m in mesajlar:
        ilk = (m["metin"].splitlines() or [""])[0]
        ekle(f"| {m['zaman']:%H:%M:%S} | {m['hedef']} | {_mesaj_turu(m['hedef'], m['metin'])} | "
             f"{len(m['metin'])} kr | {ilk[:70]} |")
    ekle("")

    ekle("## 6) Mesajların TAM metni")
    ekle("")
    for m in mesajlar:
        imza = "👤 DM" if m["hedef"] == "DM" else "📣 GRUP"
        ekle(f"### {m['zaman']:%H:%M:%S} — {imza} — {_mesaj_turu(m['hedef'], m['metin'])}")
        ekle("")
        ekle("```")
        ekle(m["metin"])
        ekle("```")
        ekle("")

    metin = "\n".join(satirlar)
    cikti = Path(args.cikti) if args.cikti else (REPO / f"SIMULASYON_{gun.isoformat()}.md")
    cikti.write_text(metin, encoding="utf-8")

    print(f"\n=== SİMÜLASYON BİTTİ — {gun} ===")
    print(f"DM mesajı        : {len(dm)}")
    print(f"Grup mesajı      : {len(grup)}")
    print(f"Toplam           : {len(mesajlar)}")
    print(f"Tarama turu      : {ds.get('tarama_sayisi')}")
    print(f"Grup bütçesi     : en yoğun saat {en_yogun}/6 · gün {len(grup)}/25")
    print(f"Rapor            : {cikti}")
    print(f"Log              : {log_yolu}")
    if hata:
        print(f"⚠️  Hata: {hata}")
    # geçici veri dizinini bırak (log yolu rapora yazıldı)
    return {"cikti": str(cikti), "dm": len(dm), "grup": len(grup),
            "tarama": ds.get("tarama_sayisi"), "hata": hata}


def main():
    ap = argparse.ArgumentParser(description="Botu 1 günlük gerçek cache verisiyle koşturur")
    ap.add_argument("--gun", help="YYYY-MM-DD (varsayılan: cache'teki son işlem günü)")
    ap.add_argument("--baslangic", default="09:00", help="sanal saat başlangıcı (varsayılan 09:00)")
    ap.add_argument("--bitis", default="20:10", help="sanal saat bitişi (varsayılan 20:10)")
    ap.add_argument("--cikti", help="rapor dosyası (varsayılan SIMULASYON_<gün>.md)")
    ap.add_argument("--log", help="log dosyası (varsayılan geçici dizin)")
    ap.add_argument("--log-seviyesi", default="WARNING", help="konsol log seviyesi")
    ap.add_argument("--hiz", type=float, default=1.0,
                    help="sanal saat hızı: beklemeler bu katla hızlı ilerler (varsayılan 1)")
    ap.add_argument("--evren", choices=("cache", "tum"), default="cache",
                    help="cache: yalnız verisi olan hisseler (varsayılan), tum: 48 hisse")
    ap.add_argument("--veri-dir", help="kalıcı sim veri dizini (günleri zincirlemek için)")
    ap.add_argument("--liste", action="store_true", help="cache'teki günleri listele ve çık")
    args = ap.parse_args()
    simule_et(args)


if __name__ == "__main__":
    main()
