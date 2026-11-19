#!/usr/bin/env python3
"""BIST derin geçmiş çekicisi — NATIVE 1h/2h/4h/1d (Termux, bağımsız araç).

NEDEN AYRI BİR ARAÇ
-------------------
Ana bot 51 sembolü 60 günlük kayan pencereyle canlı tarar ve ``DEQUE_MAXLEN=360``
Pine/TradingView uyumu bozulmasın diye bilerek büyütülmez. Araştırma arşivinin
ihtiyaç duyduğu derinlik, canlı yolu riske atmadan yalnız diske yazan bu
çekimle sağlanır.

KAYNAK PLANI (2026-11-18)
-------------------------
Yahoo ``2h``/``4h`` intervalini desteklemez. 170+ sembol için 1h'den büyük
zaman dilimlerini türetmek hacim/fiyat kayması üretiyordu; artık dört zaman
dilimi de **native** çekilir:

    1h  -> Yahoo       (auto_adjust=False, ham OHLCV)
    2h  -> TradingView (tvDatafeed, in_2_hour, gerçek bar)
    4h  -> TradingView (tvDatafeed, in_4_hour, gerçek bar)
    1d  -> Yahoo       (auto_adjust=False, native günlük)

2h/4h için ``resample_ohlcv`` KESİNLİKLE çağrılmaz. ``BRENT`` gibi BIST
exchange'inde karşılığı olmayan makro semboller probe'da elenir; dört native
dosyası tamamlanmayan sembol replay'e alınmaz.

Bu araç NE YAPMAZ: Supabase'e bağlanmaz, Telegram'a dokunmaz, ``.env`` okumaz,
domain motorlarını çalıştırmaz, formasyon/zone üretmez, bildirim göndermez.
Yalnız iki sağlayıcıdan OHLCV çeker ve diske ``CSV.gz`` yazar.

Bağımlılık: yfinance + pandas (Termux'ta ``pkg install python-pandas``) ve
doğrulanmış ``tradingview-datafeed==2.1.1`` + ``websocket-client==1.9.2``.
Ağır modüller yalnız ihtiyaç anında import edilir; ``--help``/liste modları
çıplak yorumlayıcıda çalışır.

BAN KORUMASI
------------
İstekler tek iş parçacığında ve SERİ atılır; grup içi kısa ara + grup sonrası
uzun mola. Ardışık geçici hata (429/timeout/WS kopması/5xx) tempoyu yavaşlatır
ve uzun soğuma verir. Kalıcı hatalar (404 / sembol yok / doğrulanmamış kurulum)
tekrar denenmez. Yarım kalırsa başarılı ``(sembol, interval, kaynak)`` çifti
atlanır; ``--zorla`` ile baştan çekilir.

ÇIKTI
-----
    <hedef>/<SEMBOL>_1h.csv.gz ... _2h.csv.gz ... _4h.csv.gz ... _1d.csv.gz
    <hedef>/manifest.json          sembol başına durum/satır/kaynak/TF/native/kalite
    <hedef>/probe_sonucu.json      iki sağlayıcının geçerlilik + dağıtım raporu
    <hedef>/dogrulanmis_semboller.txt   yalnız dört native kaynakta da geçerli semboller
    <hedef>/kaynak_raporu.json     TF x kaynak x durum özeti + eksik native dosyalar

``bar_time`` METİNDİR: ``YYYY-MM-DD HH:MM:SS+03:00`` (Europe/Istanbul). Sayılar
``repr()`` ile tam round-trip; NaN/inf boş hücre; yazım atomik. Yahoo'da
``auto_adjust=False`` temettü/split yeniden ayarını kapatır (Pine ham fiyat).

KULLANIM (Termux)
    python scripts/backfill/yahoo_backfill.py --probe
    python scripts/backfill/yahoo_backfill.py --limit 10
    python scripts/backfill/yahoo_backfill.py
    python scripts/backfill/yahoo_backfill.py --retry-failed
    python scripts/backfill/yahoo_backfill.py --semboller THYAO,GARAN --tv-bar-sayisi 1500
"""

from __future__ import annotations

import argparse
import gzip
import io
import contextlib
import csv
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# --- ÇIKTI BİÇİMİ SÖZLEŞMESİ -------------------------------------------------
CSV_ALANLAR = ("bar_time", "open", "high", "low", "close", "volume")
ISTANBUL_OFFSET_SAAT = 3  # Europe/Istanbul, DST'siz kış/yaz +03:00 (BIST)
VARSAYILAN_HEDEF = "backfill_data"
VARSAYILAN_PERIOD_1H = "365d"
VARSAYILAN_PERIOD_1D = "2y"
VARSAYILAN_ARALIKLAR: Tuple[str, ...] = ("1h", "2h", "4h", "1d")
VARSAYILAN_TV_BAR_SAYISI = 1500  # 2h ~1.3 yıl, 4h ~2.5 yıl BIST seansı

# --- TEMPO (ana bot sabitleriyle aynı mantık; config.py:84-95) ----------------
ISTEK_ARA_MIN_SN = 0.9
ISTEK_ARA_MAX_SN = 1.5
GRUP_BOYUTU = 10
GRUP_MOLA_MIN_SN = 10.0
GRUP_MOLA_MAX_SN = 15.0
SOGUMA_ESIK_ARDISIK_HATA = 3   # bu kadar ardışık geçici hata -> uzun mola + tempo x2
SOGUMA_SURESI_SN = 300.0       # 5 dk (soğuma sayısı ile çarpılır)
AZAMI_SOGUMA = 3               # üst üste 3 soğuma -> koşuyu durdur (ban yemektense bırak)
AZAMI_TEMPO_CARPANI = 4.0      # istek aralıkları en fazla 4 katına çıkar

# --- BIST ADAY HAVUZU --------------------------------------------------------
# DİKKAT: BU LİSTE DOĞRULANMAMIŞTIR. BIST100 bileşimi çeyreklik değişir ve bu
# araç yazılırken canlı kaynakla teyit edilemedi. Yahoo bazı BIST sembollerini
# taşımıyor (bilinen örnek: KOZAL.IS / KOZAA.IS -> HTTP 404, data.py:1755 notu).
# DOĞRU KULLANIM: önce `--probe` koş, Yahoo'nun gerçekten servis ettiği
# sembolleri içeren doğrulanmış listeyi üret, sonra çekimi o listeyle yap.
# Havuz bilerek ~100'den geniştir; probe sonrası eleme ile hedef boyuta inilir.
BIST_ADAY_HAVUZU: Tuple[str, ...] = (
    # Ana botun canlı evreni (48 hisse) — Yahoo'da çalıştığı bilinen çekirdek
    "THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK", "KCHOL", "SAHOL", "EREGL", "SISE", "BIMAS",
    "ASELS", "TUPRS", "FROTO", "TOASO", "KRDMD", "PETKM", "PGSUS", "SASA", "HEKTS", "GUBRF",
    "EKGYO", "HALKB", "VAKBN", "TCELL", "TTKOM", "TAVHL", "DOHOL", "ALARK", "ARCLK", "ENKAI",
    "ODAS", "ASTOR", "KONTR", "SMRTG", "CWENE", "SNGYO", "ISMEN", "SKBNK", "TSKB", "TTRAK",
    "OTKAR", "AKSA", "AKSEN", "AYDEM", "BRSAN", "CIMSA", "DOAS", "EGEEN",
    # Havuz genişletmesi — DOĞRULANMADI, probe ile elenmeli
    "AEFES", "AGHOL", "AKCNS", "AKFGY", "AKFYE", "ALBRK", "ALFAS", "ALGYO", "ANSGR", "ARDYZ",
    "AVPGY", "BERA", "BIOEN", "BJKAS", "BTCIM", "CANTE", "CCOLA", "CLEBI", "DOAR", "ECILC",
    "ECZYT", "ENERY", "EUPWR", "FENER", "GESAN", "GLYHO", "GSRAY", "GWIND", "ISGYO", "IZENR",
    "KARSN", "KCAER", "KLSER", "KMPUR", "KORDS", "KZBGY", "MAVI", "MGROS", "MIATK", "MPARK",
    "OYAKC", "PASEU", "QUAGR", "REEDR", "SDTTR", "SELEC", "TKFEN", "TURSG", "ULKER", "VESBE",
    "VESTL", "YEOTK", "ZOREN", "AGROT", "ALTNY", "ARZUM", "BAHSK", "BEGYO", "BOBET", "BRKVY",
    "BURCE", "CEMAS", "CEMTS", "CVKMD", "DAPGM", "DARDL", "DENGE", "DERIM", "DEVA", "DIRIT",
    "DMSAS", "DOCO", "DOFER", "DYOBY", "EBEBK", "EFOR", "ENSRI", "ERBOS", "ERSU", "ESCAR",
    "ESEN", "FONET", "GARFA", "GOLTS", "GRSEL", "GRTHO", "GTZYO", "HATEK", "HATSN", "HEDEF",
    "HKTM", "HTKMK", "IDEAS", "IHEVA", "IPEKE", "IZDMC", "KFEIN", "KIMMR", "KLGYO", "KLSRN",
    "KONYA", "KRGYO", "KRTEK", "KUTPO", "LMKDC", "MAGEN", "MAKTK", "MARMR", "MARTI", "MEDTR",
    "MEGAP", "METRO", "MRSHL", "NETAS", "NIBAS", "OBAMS", "OFSYM", "OZGYO", "OZKGY", "OZSUB",
    "PAMEL", "PAPIL", "PEKGY", "PENTA", "RTALB", "SAYAS", "SELVA", "SEYKM", "SNICA", "SOKE",
    "TEKYO", "TUKAS", "ULUUN", "VERUS", "YYAPI",
    # Endeks ve emtia (ana botun evrenindeki gibi; PROVIDER_SYMBOL_MAP ile eşlenir)
    "XU100", "XU30", "BRENT",
)

# config.py import edilemezse kullanılacak asgari eşleme (config.py:47-53 kopyası)
YEDEK_SAGLAYICI_ESLEMESI: Dict[str, str] = {
    "XU100": "XU100.IS",
    "XU30": "XU030.IS",
    "XU030": "XU030.IS",
    "BRENT": "BZ=F",
}
YEDEK_MARKET_SUFFIX = ".IS"


# -----------------------------------------------------------------------------
# Sağlayıcı sembol eşlemesi — TEK KAYNAK config.py'dir; import edilemezse yedek
# -----------------------------------------------------------------------------
def _ticker_cozucu_yukle():
    """config.yahoo_ticker_for_symbol'ı dene, olmazsa yerel kopyayı döndür.

    Neden lazy: Termux'ta config.py `pytz` ister. pytz yoksa araç tamamen
    çalışmaz olmamalı; eşlemenin yerel kopyasıyla devam etmeli.
    """
    try:
        from config import yahoo_ticker_for_symbol  # type: ignore

        return yahoo_ticker_for_symbol, "config.py"
    except Exception:
        def yerel(stock: str) -> str:
            key = str(stock or "").strip().upper()
            if key in YEDEK_SAGLAYICI_ESLEMESI:
                return YEDEK_SAGLAYICI_ESLEMESI[key]
            if any(ch in key for ch in ("=", "^", ".")):
                return key
            return key + YEDEK_MARKET_SUFFIX

        return yerel, "yerel yedek eşleme"


def ticker_for(symbol: str) -> str:
    cozucu, _ = _ticker_cozucu_yukle()
    return cozucu(symbol)


def _native_kaynak_yukle():
    """Kaynak planı/TV yardımcısını lazy yükler; repo kökünü sys.path'e ekler.

    Neden: script doğrudan ``python scripts/backfill/yahoo_backfill.py`` ile
    çalıştığında ``sys.path[0]`` script dizinidir. ``scripts`` namespace
    paketinin bulunması için repo kökü eklenmelidir. Modül seviyesinde ağır
    import yapılmaz.
    """
    kok = str(Path(__file__).resolve().parents[2])
    if kok not in sys.path:
        sys.path.insert(0, kok)
    try:
        from scripts.backfill import native_kaynak
    except Exception as exc:  # noqa: BLE001 - kurulum hatası rapora düşsün
        raise RuntimeError(f"native_kaynak yüklenemedi: {exc}") from exc
    return native_kaynak


# -----------------------------------------------------------------------------
# Hata sınıflandırması — data.py:1724 yfinance_error_is_retryable'ın bağımsız
# kopyası. Kalıcı hatalar tekrar denenmez (gereksiz istek = ban riski).
# -----------------------------------------------------------------------------
KALICI_ISARETLER = (
    "404", "possibly delisted", "may be delisted", "no data found",
    "no timezone found", "symbol not found", "not found",
)
# NOT: data.py:1737'deki listede "remote disconnected" (ayrık, boşluklu) var;
# ama Python exception adı RemoteDisconnected -> lower() sonrası BİTİŞİK olur ve
# o işaret hiç eşleşmez. Yani ana botta bu hata sınıfı kalıcı sayılıp yeniden
# denenmiyor olabilir. Burada bitişik biçim ve diğer urllib3/ağ adları eklenmiştir.
GECICI_ISARETLER = (
    # rate limit / HTTP
    "429", "too many requests", "rate limit", "ratelimit", "rate limited",
    "yfratelimit", "500", "502", "503", "504", "service unavailable",
    "bad gateway", "gateway timeout", "server error", "internal server error",
    # zaman aşımı
    "timeout", "timed out", "readtimeout", "connecttimeout",
    # bağlantı / socket — hem ayrık hem bitişik exception adları
    "connection", "connectionreset", "connectionaborted", "connection aborted",
    "connection reset", "brokenpipe", "broken pipe", "remotedisconnected",
    "remote disconnected", "remote end closed", "network is unreachable",
    "temporarily unavailable", "temporary unavailable",
    # urllib3 / requests sarmalayıcıları
    "max retries exceeded", "maxretriesexceeded", "newconnectionerror",
    "failed to establish a new connection", "chunkedencodingerror",
    "incompleteread", "incomplete read", "protocolerror", "sslerror",
    "eof occurred", "temporarily", "temporary failure", "name resolution",
    "nameresolutionerror", "getaddrinfo",
)


def hata_gecici_mi(metin: str) -> bool:
    """Geçici (tekrar denenebilir) mi, kalıcı mı? Bilinmeyen -> kalıcı sayılır.

    Bilinmeyeni kalıcı saymak bilinçli: sonsuz yeniden deneme döngüsüyle ban
    yemek, bir sembolü atlamaktan daha kötüdür. Kullanıcı `--retry-failed` ile
    elle yeniden dener.
    """
    t = str(metin or "").lower()
    if any(m in t for m in KALICI_ISARETLER):
        return False
    return any(m in t for m in GECICI_ISARETLER)


# -----------------------------------------------------------------------------
# Uyarlanabilir tempo — scan_pacer.py mantığı + ardışık hatada kendini yavaşlatma
# -----------------------------------------------------------------------------
class Tempo:
    """Seri istek temposu; ardışık geçici hatada çarpanı ve soğumayı artırır.

    `sleep_fn`/`uniform_fn` enjekte edilebilir: scan_pacer.py ile aynı desen.
    Neden: ban korumasının eşik davranışı (çarpan artışı, soğuma, durdurma)
    gerçek 5 dakikalık molalar beklemeden test edilebilmelidir.
    """

    def __init__(
        self,
        *,
        grup: int = GRUP_BOYUTU,
        log=print,
        sleep_fn=time.sleep,
        uniform_fn=random.uniform,
        monotonic_fn=time.monotonic,
        soguma_suresi_sn: float = SOGUMA_SURESI_SN,
    ) -> None:
        self.grup = max(1, grup)
        self._log = log
        self._sleep = sleep_fn
        self._uniform = uniform_fn
        self._monotonic = monotonic_fn
        self.soguma_suresi_sn = soguma_suresi_sn
        self.carpan = 1.0
        self._grup_icinde = 0
        self._son_bitis: Optional[float] = None
        self.ardisik_gecici_hata = 0
        self.soguma_sayisi = 0
        self.toplam_istek = 0
        self.dur = False
        self.beklenen_sn = 0.0  # test/ölçüm: toplam ne kadar beklendi

    def _uyu(self, saniye: float) -> None:
        if saniye > 0:
            self.beklenen_sn += saniye
            self._sleep(saniye)

    def bekle(self) -> None:
        """Bir istek ATILMADAN önce gerekli molayı verir."""
        if self._grup_icinde >= self.grup:
            mola = self._uniform(GRUP_MOLA_MIN_SN, GRUP_MOLA_MAX_SN) * self.carpan
            self._log(f"  [tempo] grup tamam ({self.grup} istek) -> {mola:.1f} sn mola")
            self._uyu(mola)
            self._grup_icinde = 0
        elif self._son_bitis is not None:
            hedef = self._uniform(ISTEK_ARA_MIN_SN, ISTEK_ARA_MAX_SN) * self.carpan
            kalan = hedef - (self._monotonic() - self._son_bitis)
            self._uyu(max(0.0, kalan))
        self._grup_icinde += 1
        self.toplam_istek += 1

    def istek_bitti(self) -> None:
        self._son_bitis = self._monotonic()

    def basarili(self) -> None:
        self.ardisik_gecici_hata = 0
        if self.carpan != 1.0:
            self._log("  [tempo] hata serisi bitti; çarpan 1.0'a döndü")
            self.carpan = 1.0

    def gecici_hata(self, sebep: str) -> None:
        """Ardışık geçici hatada tempo x2; eşik aşılınca uzun soğuma."""
        self.ardisik_gecici_hata += 1
        self.carpan = min(AZAMI_TEMPO_CARPANI, self.carpan * 2.0)
        self._log(
            f"  [tempo] geçici hata ({sebep[:60]}); "
            f"ardışık={self.ardisik_gecici_hata} çarpan={self.carpan:.1f}"
        )
        if self.ardisik_gecici_hata >= SOGUMA_ESIK_ARDISIK_HATA:
            self.soguma_sayisi += 1
            if self.soguma_sayisi > AZAMI_SOGUMA:
                self.dur = True
                self._log(
                    f"  [tempo] {AZAMI_SOGUMA} soğuma aşıldı -> BAN RİSKİ. Koşu durduruluyor; "
                    "birkaç saat sonra --retry-failed ile devam et."
                )
                return
            sure = self.soguma_suresi_sn * self.soguma_sayisi
            self._log(f"  [tempo] UZUN SOĞUMA: {sure/60:.1f} dk bekleniyor (ban koruması)")
            self._uyu(sure)
            self.ardisik_gecici_hata = 0


# -----------------------------------------------------------------------------
# Çekim
# -----------------------------------------------------------------------------
def _ham_cek(ticker: str, period: str, interval: str):
    """Tek Yahoo isteği. (DataFrame|None, hata_metni, gecici_mi) döner.

    stdout/stderr yakalanır: yfinance hata ayrıntısını exception yerine stderr'e
    yazabiliyor; sınıflandırma için o metne ihtiyaç var (data.py:1765 ile aynı).
    """
    try:
        import yfinance as yf
    except Exception as exc:  # noqa: BLE001
        return None, f"yfinance import edilemedi: {exc}", False

    try:
        yakalanan = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(yakalanan):
            df = yf.Ticker(ticker).history(
                period=period, interval=interval, auto_adjust=False
            )
        if df is None or len(df) == 0:
            sebep = yakalanan.getvalue().strip() or "Yahoo boş veri döndürdü"
            return None, sebep, hata_gecici_mi(sebep)
        df = df.rename(columns=str.lower)
        gerekli = ["open", "high", "low", "close", "volume"]
        eksik = [c for c in gerekli if c not in df.columns]
        if eksik:
            return None, f"eksik OHLCV sütunları: {eksik}", False
        return df[gerekli], "", False
    except Exception as exc:  # noqa: BLE001
        sebep = f"{type(exc).__name__}: {exc}"
        return None, sebep, hata_gecici_mi(sebep)


def _zaman_dilimi_normalize(df):
    """İndeksi Europe/Istanbul tz-aware yapar.

    Neden kritik: yfinance bazen UTC/naive döner; normalize edilmezse bar_time
    metni tutarsız olur ve arşivde aynı bar iki farklı anahtarla yazılır
    (data.py:1781-1790 ile aynı gerekçe).
    """
    import pandas as pd

    try:
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert("Europe/Istanbul")
        else:
            df.index = df.index.tz_convert("Europe/Istanbul")
    except Exception:
        try:
            df.index = pd.to_datetime(df.index).tz_localize("Europe/Istanbul")
        except Exception:  # noqa: BLE001, S110 - son çare; CLI'da indeks ham kalır, çağıran görür
            pass
    return df


def _kalite_raporu(df) -> Dict[str, Any]:
    """Ham bar kalitesi — kirli satır SESSİZCE DÜŞÜRÜLMEZ, raporlanır.

    Neden: arşive giren bozuk bar geri alınamaz. Sıfır hacim / NaN / split
    sıçraması gibi sorunlar sayılır ve manifest'e yazılır; eleme kararı
    kullanıcının ve ingest katmanınındır (data.py ohlcv_girdi_sorunlari ve
    SPLIT_SUREKLILIK_ESIK_PCT=10.0 aynı kaygıyla var).
    """
    toplam = int(len(df))
    nan_ohlc = int(df[["open", "high", "low", "close"]].isna().any(axis=1).sum())
    sifir_hacim = int((df["volume"].fillna(0) <= 0).sum())
    split_adayi = 0
    try:
        close = df["close"].astype(float)
        opn = df["open"].astype(float)
        onceki = close.shift(1)
        oran = ((opn - onceki).abs() / onceki.replace(0, float("nan"))) * 100.0
        split_adayi = int((oran > 10.0).sum())
    except Exception:
        split_adayi = 0
    return {
        "toplam_bar": toplam,
        "nan_ohlc": nan_ohlc,
        "sifir_hacim": sifir_hacim,
        "split_sicramasi_adayi": split_adayi,
    }


def _csv_gz_yaz(yol: Path, df) -> int:
    """bar_time METİN olarak, sabit biçimde CSV.gz yazar. Dönen satır sayısı."""
    df = df.copy()
    df.index = df.index.astype(str)  # 'YYYY-MM-DD HH:MM:SS+03:00'
    df.index.name = "bar_time"
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(yol.suffix + ".tmp")
    with gzip.open(gecici, "wt", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_ALANLAR)
        for bar_time, row in df.iterrows():
            writer.writerow([
                bar_time,
                _sayi(row.get("open")), _sayi(row.get("high")),
                _sayi(row.get("low")), _sayi(row.get("close")),
                _sayi(row.get("volume")),
            ])
    os.replace(gecici, yol)  # atomik: yarım dosya arşive girmez
    return int(len(df))


def _sayi(deger: Any) -> str:
    """Sayıyı tam geri-çevrilebilir (round-trip) biçimde metne çevirir.

    repr() Python 3'te en kısa round-trip gösterimini verir: 12.5 -> '12.5',
    1e-09 -> '1e-09'. Biçimlendirme ile basamak kaybetmek arşivde geri
    döndürülemez bir hata olur, bu yüzden yuvarlama YAPILMAZ.
    NaN/inf -> boş hücre (CSV'de 'nan' yazmak okuyucuda sayı diye patlar).
    """
    if deger is None:
        return ""
    try:
        f = float(deger)
    except (TypeError, ValueError):
        return ""
    if f != f or f in (float("inf"), float("-inf")):  # NaN / ±inf
        return ""
    return repr(f)


def sembol_cek(
    sembol: str,
    interval: str,
    period: str,
    hedef: Path,
    tempo: Tempo,
    *,
    deneme: int,
    log=print,
    tv_bar_sayisi: int = VARSAYILAN_TV_BAR_SAYISI,
    tv_exchange: str = "BIST",
    kaynak: Optional[str] = None,
) -> Dict[str, Any]:
    """Bir (sembol, interval) çiftini NATIVE kaynağından dener; manifest girdisi döner."""
    nk = _native_kaynak_yukle()
    kaynak = kaynak or nk.KAYNAK_PLANI.get(interval)
    if kaynak not in ("yahoo", "tvdatafeed"):
        raise ValueError(f"desteklenmeyen kaynak/TF: {kaynak}/{interval}")
    if kaynak == "yahoo":
        provider_symbol = ticker_for(sembol)
        provider_interval = interval
    else:
        provider_symbol = nk.tv_sembol(sembol)
        provider_interval = nk.TV_ARALIK[interval]

    basladi = time.monotonic()

    def temel(durum: str, **ek: Any) -> Dict[str, Any]:
        kayit: Dict[str, Any] = {
            "sembol": sembol,
            "interval": interval,
            "durum": durum,
            "kaynak": kaynak,
            "native": True,
            "provider_symbol": provider_symbol,
            "provider_interval": provider_interval,
            "period": period if kaynak == "yahoo" else None,
            "bar_sayisi_istek": max(1, int(tv_bar_sayisi)) if kaynak == "tvdatafeed" else None,
            "tv_exchange": tv_exchange if kaynak == "tvdatafeed" else None,
            "sure_sn": round(time.monotonic() - basladi, 1),
        }
        if kaynak == "yahoo":
            kayit["ticker"] = provider_symbol
        kayit.update(ek)
        return kayit

    if provider_symbol is None:
        sebep = nk.TV_DISI_SEMBOLLER.get(str(sembol).upper(), "TV kapsam dışı")
        log(f"  ⏭️  {sembol:<7} {interval:<3} kapsam dışı: {sebep[:80]}")
        return temel("kapsam_disi", hata=sebep, deneme=0)

    son_sebep = ""
    for girisim in range(1, max(1, deneme) + 1):
        if tempo.dur:
            return temel("durduruldu", hata="tempo ban koruması koşuyu durdurdu", deneme=girisim - 1)
        tempo.bekle()
        if kaynak == "yahoo":
            df, sebep, gecici = _ham_cek(provider_symbol, period, provider_interval)
        else:
            df, sebep, gecici = nk.tv_ham_cek(
                sembol, interval, tv_bar_sayisi, exchange=tv_exchange
            )
        tempo.istek_bitti()

        if df is not None and len(df) > 0:
            df = _zaman_dilimi_normalize(df)
            if len(df) == 0:
                son_sebep = "tz normalizasyonu sonrası boş"
            else:
                yol = hedef / f"{sembol}_{interval}.csv.gz"
                try:
                    satir = _csv_gz_yaz(yol, df)
                except Exception as exc:  # noqa: BLE001
                    return temel("yazma_hatasi", hata=f"{type(exc).__name__}: {exc}", deneme=girisim)
                tempo.basarili()
                ilk, son = str(df.index[0]), str(df.index[-1])
                log(f"  ✅ {sembol:<7} {interval:<3} {kaynak:<10} {satir:>5} bar  {ilk[:10]} → {son[:16]}")
                return temel(
                    "ok",
                    dosya=yol.name,
                    satir=satir,
                    ilk_bar=ilk,
                    son_bar=son,
                    kalite=_kalite_raporu(df),
                    deneme=girisim,
                )

        son_sebep = sebep or "boş veri"
        if gecici:
            tempo.gecici_hata(son_sebep)
            if girisim < deneme:
                bekleme = random.uniform(30.0, 60.0) * girisim
                log(f"  ⏳ {sembol} {interval}/{kaynak}: geçici hata, {bekleme:.0f} sn sonra "
                    f"{girisim+1}. deneme ({son_sebep[:70]})")
                time.sleep(bekleme)
            continue
        log(f"  ❌ {sembol:<7} {interval:<3} {kaynak:<10} KALICI: {son_sebep[:90]}")
        return temel("kalici_basarisiz", hata=son_sebep, deneme=girisim)

    log(f"  ⚠️ {sembol:<7} {interval:<3} {kaynak:<10} denemeler tükendi: {son_sebep[:90]}")
    return temel("gecici_basarisiz", hata=son_sebep, deneme=deneme)


# -----------------------------------------------------------------------------
# Manifest — kaldığı yerden devam ve yalnız başarısızları yeniden deneme
# -----------------------------------------------------------------------------
def manifest_oku(hedef: Path) -> Dict[str, Any]:
    yol = hedef / "manifest.json"
    if not yol.exists():
        return {"kayitlar": {}, "kosular": []}
    try:
        with open(yol, "r", encoding="utf-8") as fh:
            veri = json.load(fh)
        if not isinstance(veri.get("kayitlar"), dict):
            veri["kayitlar"] = {}
        veri.setdefault("kosular", [])
        return veri
    except Exception:
        return {"kayitlar": {}, "kosular": [], "uyari": "manifest okunamadı, sıfırdan başlandı"}


def manifest_yaz(hedef: Path, veri: Dict[str, Any]) -> None:
    hedef.mkdir(parents=True, exist_ok=True)
    yol = hedef / "manifest.json"
    gecici = yol.with_suffix(".json.tmp")
    with open(gecici, "w", encoding="utf-8") as fh:
        json.dump(veri, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(gecici, yol)


def json_yaz(yol: Path, veri: Dict[str, Any]) -> None:
    """Manifest dışındaki raporlar için atomik JSON yazımı."""
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(yol.suffix + ".tmp")
    with open(gecici, "w", encoding="utf-8") as fh:
        json.dump(veri, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(gecici, yol)


def anahtar(sembol: str, interval: str) -> str:
    return f"{sembol}:{interval}"


def atlanmali_mi(
    onceki: Optional[Dict[str, Any]],
    dosya: Path,
    *,
    zorla: bool,
    beklenen_kaynak: Optional[str] = None,
) -> bool:
    """Bu (sembol, interval, kaynak) çifti yeniden çekilmeli mi, atlanmalı mı?

    Atlama koşulu: manifest kaydı ``ok`` + ``native=True`` + beklenen kaynakla
    aynı + dosya diskte gerçekten var + ``--zorla`` yok. Eski türetimli/ kaynak
    etiketsiz kayıtlar BİLEREK yeniden çekilir; aksi halde 1h'den resample
    edilmiş eski veri native arşivde kalabilir.
    """
    if zorla:
        return False
    if not onceki or onceki.get("durum") != "ok":
        return False
    if onceki.get("native") is not True:
        return False
    if beklenen_kaynak is not None and onceki.get("kaynak") != beklenen_kaynak:
        return False
    return bool(dosya.exists())


# -----------------------------------------------------------------------------
# Probe — hangi semboller Yahoo'da gerçekten var
# -----------------------------------------------------------------------------
def probe(
    semboller: Sequence[str],
    hedef: Path,
    tempo: Tempo,
    *,
    log=print,
    tv_bar_sayisi: int = 5,
    tv_exchange: str = "BIST",
) -> Dict[str, Any]:
    """Her sembol için Yahoo 1d + TradingView native 4h geçerlilik testi.

    Yalnız İKİ kaynak da veri döndürürse sembol ``dogrulanmis_semboller.txt``
    listesine girer. Böylece tam çekimde 2h/4h için boşa WS isteği atılmaz ve
    dört native dosyası olmayan sembol replay'e sokulmaz.
    """
    nk = _native_kaynak_yukle()
    sonuc: Dict[str, Any] = {
        "tarih": _simdi_iso(),
        "mod": "native-karma",
        "kaynak_plani": nk.KAYNAK_PLANI,
        "kaynak_plani_ozeti": nk.kaynak_plani_ozeti(),
        "tv_dagitim": nk.tv_hazirlik_raporu(),
        "yahoo_probe": "5d/1d",
        "tv_probe": f"{max(1, int(tv_bar_sayisi))} bar/4h/{tv_exchange}",
        "gecerli": [],
        "gecersiz": {},
        "kaynak_ozeti": {},
    }
    for i, sembol in enumerate(semboller, 1):
        tempo.bekle()
        yahoo_df, yahoo_sebep, yahoo_gecici = _ham_cek(ticker_for(sembol), "5d", "1d")
        tempo.istek_bitti()
        if yahoo_gecici:
            tempo.gecici_hata(f"yahoo: {yahoo_sebep}")

        tempo.bekle()
        tv_df, tv_sebep, tv_gecici = nk.tv_ham_cek(
            sembol, "4h", tv_bar_sayisi, exchange=tv_exchange
        )
        tempo.istek_bitti()
        if tv_gecici:
            tempo.gecici_hata(f"tv: {tv_sebep}")

        yahoo_ok = yahoo_df is not None and len(yahoo_df) > 0
        tv_ok = tv_df is not None and len(tv_df) > 0
        sonuc["kaynak_ozeti"][sembol] = {
            "yahoo": "ok" if yahoo_ok else yahoo_sebep[:160],
            "tvdatafeed": "ok" if tv_ok else tv_sebep[:160],
        }
        if yahoo_ok and tv_ok:
            tempo.basarili()
            sonuc["gecerli"].append(sembol)
            log(f"  [{i}/{len(semboller)}] ✅ {sembol} (yahoo + tv native)")
        else:
            sonuc["gecersiz"][sembol] = (
                f"yahoo: {yahoo_sebep[:100] or 'ok'} | tv: {tv_sebep[:100] or 'ok'}"
            )
            log(f"  [{i}/{len(semboller)}] ❌ {sembol}: {sonuc['gecersiz'][sembol][:110]}")
        if tempo.dur:
            sonuc["uyari"] = "tempo ban koruması probe'u erken durdurdu"
            break
    sonuc["gecerli_sayisi"] = len(sonuc["gecerli"])
    sonuc["gecersiz_sayisi"] = len(sonuc["gecersiz"])
    hedef.mkdir(parents=True, exist_ok=True)
    json_yaz(hedef / "probe_sonucu.json", sonuc)
    with open(hedef / "dogrulanmis_semboller.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(sonuc["gecerli"]) + ("\n" if sonuc["gecerli"] else ""))
    log(f"\nProbe bitti: {sonuc['gecerli_sayisi']} geçerli, {sonuc['gecersiz_sayisi']} geçersiz")
    log(f"  -> {hedef/'dogrulanmis_semboller.txt'}")
    return sonuc


def _simdi_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -----------------------------------------------------------------------------
# Sembol listesi çözümü
# -----------------------------------------------------------------------------
def sembol_listesi_coz(args) -> List[str]:
    if args.semboller:
        return [s.strip().upper() for s in args.semboller.split(",") if s.strip()]
    if args.liste_dosyasi:
        yol = Path(args.liste_dosyasi)
        if not yol.exists():
            print(f"HATA: liste dosyası yok: {yol}", file=sys.stderr)
            sys.exit(2)
        return sorted({
            satir.strip().upper()
            for satir in yol.read_text(encoding="utf-8").splitlines()
            if satir.strip() and not satir.strip().startswith("#")
        })
    # Varsayılan: probe sonucu varsa ONU kullan (doğrulanmış liste), yoksa havuz
    hedef = Path(args.hedef)
    dogrulanmis = hedef / "dogrulanmis_semboller.txt"
    if dogrulanmis.exists() and not args.probe:
        liste = sorted({
            s.strip().upper()
            for s in dogrulanmis.read_text(encoding="utf-8").splitlines()
            if s.strip()
        })
        if liste:
            print(f"[liste] probe sonucu kullanılıyor: {len(liste)} doğrulanmış sembol")
            return liste
    print(f"[liste] DOĞRULANMAMIŞ aday havuzu kullanılıyor: {len(BIST_ADAY_HAVUZU)} sembol")
    print("        Öneri: önce --probe koş, geçerli listeyi üret.")
    return list(BIST_ADAY_HAVUZU)


# -----------------------------------------------------------------------------
# Kaynak raporu — TF x kaynak x durum + eksik native dosyalar
# -----------------------------------------------------------------------------
def kaynak_raporu_olustur(
    hedef: Path,
    kayitlar: Dict[str, Any],
    intervals: Sequence[str],
    tv_hazirlik: Dict[str, Any],
) -> Dict[str, Any]:
    """Manifest + disk üzerinden kaynak/TF etiketli denetim raporu üretir."""
    nk = _native_kaynak_yukle()
    semboller = sorted({
        str(v.get("sembol")) for v in kayitlar.values() if v.get("sembol")
    })
    beklenen = [
        hedef / f"{sembol}_{tf}.csv.gz"
        for sembol in semboller
        for tf in VARSAYILAN_ARALIKLAR
    ]
    eksik = [str(yol.relative_to(hedef)) for yol in beklenen if not yol.exists()]
    durumlar: Dict[str, int] = {}
    for kayit in kayitlar.values():
        anahtar = "|".join(str(kayit.get(k, "?")) for k in ("interval", "kaynak", "durum"))
        durumlar[anahtar] = durumlar.get(anahtar, 0) + 1
    return {
        "tarih": _simdi_iso(),
        "surum": "native-1",
        "arsiv_modu": "native",
        "native_zorunlu": True,
        "zaman_dilimleri": list(VARSAYILAN_ARALIKLAR),
        "bu_kosu_araliklari": list(intervals),
        "kaynak_plani": nk.KAYNAK_PLANI,
        "kaynak_plani_ozeti": nk.kaynak_plani_ozeti(),
        "tv_dagitim": tv_hazirlik,
        "sembol_sayisi": len(semboller),
        "beklenen_dosya_sayisi": len(beklenen),
        "diskteki_dosya_sayisi": len(beklenen) - len(eksik),
        "eksik_dosya_sayisi": len(eksik),
        "eksik_dosyalar": eksik[:200],
        "kayit_durum_ozeti": durumlar,
        "resample_kullanildi": False,
    }


# -----------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    nk = _native_kaynak_yukle()
    p = argparse.ArgumentParser(
        description="BIST derin geçmiş çekicisi (Yahoo 1h/1d + TradingView native 2h/4h -> disk).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--hedef", default=VARSAYILAN_HEDEF, help=f"çıktı dizini (varsayılan: {VARSAYILAN_HEDEF})")
    p.add_argument("--probe", action="store_true", help="Yahoo + TV native geçerlilik testi")
    p.add_argument("--semboller", default="", help="virgülle ayrılmış sembol listesi")
    p.add_argument("--liste-dosyasi", default="", help="sembol listesini dosyadan oku")
    p.add_argument("--limit", type=int, default=0, help="yalnız ilk N sembol (pilot için)")
    p.add_argument("--period-1h", default=VARSAYILAN_PERIOD_1H, help="Yahoo 1h geçmişi (varsayılan 365d)")
    p.add_argument("--period-1d", default=VARSAYILAN_PERIOD_1D, help="Yahoo 1d geçmişi (varsayılan 2y)")
    p.add_argument("--interval", default=",".join(VARSAYILAN_ARALIKLAR),
                   help="çekilecek NATIVE aralıklar (varsayılan: 1h,2h,4h,1d)")
    p.add_argument("--tv-bar-sayisi", type=int, default=VARSAYILAN_TV_BAR_SAYISI,
                   help=f"TV 2h/4h istenen bar sayısı (varsayılan {VARSAYILAN_TV_BAR_SAYISI})")
    p.add_argument("--tv-exchange", default=nk.TV_VARSAYILAN_EXCHANGE,
                   help=f"TradingView exchange (varsayılan: {nk.TV_VARSAYILAN_EXCHANGE})")
    p.add_argument("--deneme", type=int, default=3, help="geçici hatada azami deneme")
    p.add_argument("--retry-failed", action="store_true", help="yalnız başarısız/eksik kayıtları dene")
    p.add_argument("--zorla", action="store_true", help="başarılı kayıtları da yeniden çek")
    p.add_argument("--grup", type=int, default=GRUP_BOYUTU, help=f"molalar arası istek sayısı (varsayılan {GRUP_BOYUTU})")
    p.add_argument("--wake-lock", action="store_true", help="Termux'ta ekran kilidi/uyku engelini dene")
    args = p.parse_args(argv)

    hedef = Path(args.hedef)
    hedef.mkdir(parents=True, exist_ok=True)

    def log(mesaj: str = "") -> None:
        print(mesaj, flush=True)

    semboller = sembol_listesi_coz(args)
    if args.limit > 0:
        semboller = semboller[: args.limit]
    if not semboller:
        log("HATA: boş sembol listesi")
        return 2

    intervals = [i.strip().lower() for i in args.interval.split(",") if i.strip()]
    gecersiz = [i for i in intervals if i not in nk.KAYNAK_PLANI]
    if gecersiz:
        log(f"HATA: desteklenmeyen aralıklar: {gecersiz}. Geçerli: {list(nk.KAYNAK_PLANI)}")
        return 2
    if args.tv_bar_sayisi <= 0:
        log("HATA: --tv-bar-sayisi > 0 olmalı")
        return 2

    tv_gerekli = any(nk.KAYNAK_PLANI[i] == "tvdatafeed" for i in intervals)
    tv_hazirlik = (
        nk.tv_hazirlik_raporu()
        if tv_gerekli
        else {"hazir": True, "dagitim": "kullanilmadi", "surum": "-"}
    )
    if tv_gerekli and not tv_hazirlik.get("hazir"):
        log("HATA: TradingView native 2h/4h için doğrulanmış kurulum yok:")
        log(f"  {tv_hazirlik.get('hata')}")
        log("  python -m pip install tradingview-datafeed==2.1.1 websocket-client==1.9.2")
        return 2

    tempo = Tempo(grup=args.grup, log=log)
    if args.wake_lock:
        _wake_lock(log)

    log("=" * 72)
    log("BIST DERİN GEÇMİŞ ÇEKİCİSİ — NATIVE Yahoo + TradingView -> disk")
    log("=" * 72)
    log(f"Hedef dizin : {hedef.resolve()}")
    log(f"Sembol      : {len(semboller)} ({semboller[0]} ... {semboller[-1]})")
    log(f"Aralıklar   : {intervals}")
    log(f"Kaynak      : {', '.join(f'{tf}={nk.KAYNAK_PLANI[tf]}' for tf in intervals)}")
    log(f"TV dağıtım  : {tv_hazirlik.get('dagitim')}=={tv_hazirlik.get('surum')} "
        f"(hazır={tv_hazirlik.get('hazir')})")
    if not args.probe:
        log(f"Period/bar  : Yahoo 1h={args.period_1h} 1d={args.period_1d} · "
            f"TV 2h/4h={args.tv_bar_sayisi} bar")
    log(f"Tempo       : grup={args.grup}, istek arası {ISTEK_ARA_MIN_SN}-{ISTEK_ARA_MAX_SN} sn, "
        f"grup molası {GRUP_MOLA_MIN_SN:.0f}-{GRUP_MOLA_MAX_SN:.0f} sn")
    tahmini = len(semboller) * (2 if args.probe else len(intervals))
    log(f"Tahmini istek: {tahmini}  (~{tahmini/args.grup*(args.grup*1.2+12.5)/60:.0f} dk)")
    log("")

    if args.probe:
        probe(semboller, hedef, tempo, log=log,
              tv_bar_sayisi=args.tv_bar_sayisi, tv_exchange=args.tv_exchange)
        return 1 if tempo.dur else 0

    manifest = manifest_oku(hedef)
    manifest.update({
        "surum": "native-1",
        "arsiv_modu": "native",
        "native_zorunlu": True,
        "zaman_dilimleri": list(VARSAYILAN_ARALIKLAR),
        "kaynak_plani": nk.KAYNAK_PLANI,
        "kaynak_plani_ozeti": nk.kaynak_plani_ozeti(),
        "tv_dagitim": tv_hazirlik,
    })
    kayitlar: Dict[str, Any] = manifest["kayitlar"]
    kosu_basladi = time.monotonic()
    sayac = {"ok": 0, "atlandi": 0, "kalici": 0, "gecici": 0, "diger": 0}

    for i, sembol in enumerate(semboller, 1):
        if tempo.dur:
            log(f"\n[{i}/{len(semboller)}] Ban koruması koşuyu durdurdu; kalanlar işlenmedi.")
            break
        log(f"[{i}/{len(semboller)}] {sembol}")
        for interval in intervals:
            k = anahtar(sembol, interval)
            onceki = kayitlar.get(k)
            dosya = hedef / f"{sembol}_{interval}.csv.gz"
            beklenen_kaynak = nk.KAYNAK_PLANI[interval]
            if args.retry_failed and onceki and onceki.get("durum") in ("ok", "kapsam_disi"):
                log(f"  ⏭️  {interval}: önceki kayıt terminal ({onceki.get('durum')}) — atlandı")
                sayac["atlandi"] += 1
                continue
            if atlanmali_mi(onceki, dosya, zorla=args.zorla, beklenen_kaynak=beklenen_kaynak):
                log(f"  ⏭️  {interval}: native {beklenen_kaynak} çekilmiş "
                    f"({(onceki or {}).get('satir')} bar) — atlandı")
                sayac["atlandi"] += 1
                continue
            period = args.period_1h if interval == "1h" else args.period_1d
            kayit = sembol_cek(
                sembol, interval, period, hedef, tempo,
                deneme=args.deneme, log=log,
                tv_bar_sayisi=args.tv_bar_sayisi,
                tv_exchange=args.tv_exchange,
                kaynak=beklenen_kaynak,
            )
            kayit["zaman"] = _simdi_iso()
            kayitlar[k] = kayit
            durum = kayit["durum"]
            if durum == "ok":
                sayac["ok"] += 1
            elif durum == "kalici_basarisiz":
                sayac["kalici"] += 1
            elif durum == "gecici_basarisiz":
                sayac["gecici"] += 1
            else:
                sayac["diger"] += 1
            manifest["kayitlar"] = kayitlar
            manifest_yaz(hedef, manifest)

    sure = round(time.monotonic() - kosu_basladi, 1)
    ozet = {
        "basladi": _simdi_iso(), "sure_sn": sure, "mod": "native-backfill",
        "sembol_sayisi": len(semboller), "araliklar": intervals,
        "kaynak_plani": {tf: nk.KAYNAK_PLANI[tf] for tf in intervals},
        "period_1h": args.period_1h, "period_1d": args.period_1d,
        "tv_bar_sayisi": args.tv_bar_sayisi, "tv_exchange": args.tv_exchange,
        "tv_dagitim": tv_hazirlik,
        "sonuclar": sayac, "toplam_istek": tempo.toplam_istek,
        "soguma_sayisi": tempo.soguma_sayisi, "ban_korumasi_durdurdu": tempo.dur,
    }
    manifest["kosular"].append(ozet)
    manifest["son_kosu"] = ozet
    manifest_yaz(hedef, manifest)

    rapor = kaynak_raporu_olustur(hedef, kayitlar, intervals, tv_hazirlik)
    json_yaz(hedef / "kaynak_raporu.json", rapor)

    log("")
    log("=" * 72)
    log("KOŞU ÖZETİ — NATIVE 1h/2h/4h/1d")
    log("=" * 72)
    log(f"Süre        : {sure/60:.1f} dk   Toplam istek: {tempo.toplam_istek}")
    log(f"Başarılı    : {sayac['ok']}")
    log(f"Atlanan     : {sayac['atlandi']}")
    log(f"Kalıcı hata : {sayac['kalici']}")
    log(f"Geçici hata : {sayac['gecici']} (--retry-failed ile yeniden dene)")
    log(f"Diğer       : {sayac['diger']} (kapsam dışı/yazma/durduruldu)")
    log(f"Eksik dosya : {rapor['eksik_dosya_sayisi']} / {rapor['beklenen_dosya_sayisi']}")
    if tempo.soguma_sayisi:
        log(f"Soğuma      : {tempo.soguma_sayisi} kez (ban koruması devreye girdi)")
    if tempo.dur:
        log("⚠️  KOŞU BAN KORUMASIYLA DURDURULDU. Birkaç saat bekleyip --retry-failed koş.")
    if rapor["eksik_dosya_sayisi"]:
        log("⚠️  Dört native dosyası tamamlanmayan semboller replay'e ALINMAMALIDIR.")

    kirli = [
        (k, v.get("kalite", {})) for k, v in kayitlar.items()
        if v.get("durum") == "ok" and v.get("kalite", {}).get("split_sicramasi_adayi", 0) > 0
    ]
    if kirli:
        log(f"\n⚠️  {len(kirli)} kayıtta %10 üzeri fiyat sıçraması (split/temettü adayı):")
        for k, kal in kirli[:15]:
            log(f"     {k}: {kal.get('split_sicramasi_adayi')} bar")

    log(f"\nManifest    : {hedef/'manifest.json'}")
    log(f"Kaynak raporu: {hedef/'kaynak_raporu.json'}")
    log("Sonraki adım: docs/kurulum/TERMUX_BACKFILL.md — doğrulama, commit & push")
    return 1 if tempo.dur else 0


def _wake_lock(log) -> None:
    """Termux'ta cihazın uyuyup koşuyu öldürmesini engellemeyi dene (best effort)."""
    try:
        import subprocess

        subprocess.run(["termux-wake-lock"], check=False, timeout=15,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("[termux] wake-lock istendi (cihaz uyursa çekim kesilmez)")
    except Exception as exc:  # noqa: BLE001
        log(f"[termux] wake-lock atlandı: {type(exc).__name__}")


if __name__ == "__main__":
    sys.exit(main())
