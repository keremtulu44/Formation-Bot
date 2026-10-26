#!/usr/bin/env python3
"""BIST derin geçmiş çekicisi — Termux'ta tek başına çalışan BAĞIMSIZ araç.

NEDEN AYRI BİR ARAÇ
-------------------
Ana bot 51 sembolü 60 günlük kayan pencereyle canlı tarar ve `DEQUE_MAXLEN=360`
Pine/TradingView uyumu bozulmasın diye bilerek büyütülmez (config.py:225-229).
Araştırma veri setinin ihtiyaç duyduğu derinlik (varsayılan 365 gün) canlı yolu
riske atmadan, YALNIZ arşive yazan bağımsız bir çekimle sağlanır.

Bu araç NE YAPMAZ: Supabase'e bağlanmaz, Telegram'a dokunmaz, .env okumaz,
domain motorlarını çalıştırmaz, formasyon/zone üretmez, bildirim göndermez.
Yalnız Yahoo'dan OHLCV çeker ve diske CSV.gz olarak yazar.

Bağımlılık: yfinance + pandas (Termux'ta pandas `pkg install python-pandas`
ile gelir, pip ile DEĞİL — aarch64 derleme hatası; bkz. requirements-termux.txt).
İkisi de YALNIZ ihtiyaç anında import edilir, böylece `--help` ve liste modları
bağımlılık kurulu olmadan da çalışır.

BAN KORUMASI
------------
1. İstekler tek iş parçacığında ve SERİ atılır (paralel istek yok); grup içi kısa
   ara + grup sonrası uzun mola. Tempo mantığı ana botla aynıdır (scan_pacer.py).
2. Ardışık geçici hata (429/timeout/5xx) görülünce tempo KENDİLİĞİNDEN yavaşlar
   ve uzun soğuma molası verilir.
3. Kalıcı hatalar (404 / "symbol not found" / "no data found") TEKRAR DENENMEZ;
   gereksiz istek atılmaz. Ayrım `yfinance_error_is_retryable` (data.py:1724)
   mantığının bağımsız kopyasıdır.
4. Yarım kalırsa kaldığı yerden devam eder: başarılı sembol/atılım çifti atlanır
   (`--zorla` ile baştan çeker). Termux'ta süreç öldürülürse bu kritiktir.

ÇIKTI
-----
    <hedef>/<SEMBOL>_1h.csv.gz     bar_time,open,high,low,close,volume
    <hedef>/<SEMBOL>_1d.csv.gz     aynı biçim
    <hedef>/manifest.json          sembol başına durum/satır/aralık/hata/süre
    <hedef>/probe_sonucu.json      (--probe) Yahoo geçerlilik raporu

`bar_time` METİNDİR: 'YYYY-MM-DD HH:MM:SS+03:00' (Europe/Istanbul).
Neden TEXT: supabase_schema.sql'deki kritik uyarı — timestamptz PostgREST'ten
ISO 'T' ayraçlı döner ve string eşitliği arayan konum bulma sessizce kaçar.
Aynı disiplin arşivde de korunur.

Neden auto_adjust=False: yfinance varsayılanı True'dur ve geçmiş OHLC'yi
temettü/splite göre YENİDEN ayarlar; TradingView/Pine ham fiyat kullanır.
Bu parametre daha önce düşmüştü ve tüm geçmiş kaymıştı (data.py:1757-1762).

KULLANIM (Termux)
    python scripts/backfill/yahoo_backfill.py --probe
    python scripts/backfill/yahoo_backfill.py --limit 10
    python scripts/backfill/yahoo_backfill.py
    python scripts/backfill/yahoo_backfill.py --retry-failed
    python scripts/backfill/yahoo_backfill.py --semboller THYAO,GARAN --period-1h 730d
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
) -> Dict[str, Any]:
    """Bir (sembol, interval) çiftini dener; manifest girdisi döner."""
    basladi = time.monotonic()
    ticker = ticker_for(sembol)
    son_sebep = ""
    for girisim in range(1, max(1, deneme) + 1):
        if tempo.dur:
            return {
                "sembol": sembol, "interval": interval, "durum": "durduruldu",
                "ticker": ticker, "hata": "tempo ban koruması koşuyu durdurdu",
                "deneme": girisim - 1, "sure_sn": round(time.monotonic() - basladi, 1),
            }
        tempo.bekle()
        df, sebep, gecici = _ham_cek(ticker, period, interval)
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
                    return {
                        "sembol": sembol, "interval": interval, "durum": "yazma_hatasi",
                        "ticker": ticker, "hata": f"{type(exc).__name__}: {exc}",
                        "deneme": girisim, "sure_sn": round(time.monotonic() - basladi, 1),
                    }
                tempo.basarili()
                ilk, son = str(df.index[0]), str(df.index[-1])
                log(f"  ✅ {sembol:<7} {interval:<3} {satir:>5} bar  {ilk[:10]} → {son[:16]}")
                return {
                    "sembol": sembol, "interval": interval, "durum": "ok",
                    "ticker": ticker, "dosya": yol.name, "satir": satir,
                    "period": period, "ilk_bar": ilk, "son_bar": son,
                    "kalite": _kalite_raporu(df), "deneme": girisim,
                    "sure_sn": round(time.monotonic() - basladi, 1),
                }

        son_sebep = sebep or "boş veri"
        if gecici:
            tempo.gecici_hata(son_sebep)
            if girisim < deneme:
                bekleme = random.uniform(30.0, 60.0) * girisim
                log(f"  ⏳ {sembol} {interval}: geçici hata, {bekleme:.0f} sn sonra {girisim+1}. deneme ({son_sebep[:70]})")
                time.sleep(bekleme)
            continue
        # Kalıcı hata: tekrar deneme, isteği boşa harcama
        log(f"  ❌ {sembol:<7} {interval:<3} KALICI: {son_sebep[:90]}")
        return {
            "sembol": sembol, "interval": interval, "durum": "kalici_basarisiz",
            "ticker": ticker, "hata": son_sebep, "deneme": girisim,
            "sure_sn": round(time.monotonic() - basladi, 1),
        }

    log(f"  ⚠️ {sembol:<7} {interval:<3} denemeler tükendi: {son_sebep[:90]}")
    return {
        "sembol": sembol, "interval": interval, "durum": "gecici_basarisiz",
        "ticker": ticker, "hata": son_sebep, "deneme": deneme,
        "sure_sn": round(time.monotonic() - basladi, 1),
    }


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


def anahtar(sembol: str, interval: str) -> str:
    return f"{sembol}:{interval}"


def atlanmali_mi(onceki: Optional[Dict[str, Any]], dosya: Path, *, zorla: bool) -> bool:
    """Bu (sembol, interval) çifti yeniden çekilmeli mi, atlanmalı mı?

    Atlama koşulu ÜÇLÜ: manifest kaydı `ok` VE dosya diskte gerçekten var VE
    `--zorla` verilmemiş. Neden dosya da kontrol ediliyor: manifest yazıldıktan
    sonra dosya silinmiş/bozulmuş olabilir (Termux'ta depolama temizliği yaygın);
    yalnız manifest'e güvenmek "çekilmiş görünen ama diskte olmayan" veri üretir.

    `--retry-failed` bu fonksiyonu DEĞİŞTİRMEZ: o bayrak yalnız başarısız
    kayıtları seçer, başarılı olanlar yine atlanır.
    """
    if zorla:
        return False
    if not onceki or onceki.get("durum") != "ok":
        return False
    return bool(dosya.exists())


# -----------------------------------------------------------------------------
# Probe — hangi semboller Yahoo'da gerçekten var
# -----------------------------------------------------------------------------
def probe(semboller: Sequence[str], hedef: Path, tempo: Tempo, *, log=print) -> Dict[str, Any]:
    """Sembol başına TEK ucuz istekle geçerlilik testi (5d/1d).

    Neden ayrı mod: havuz doğrulanmamış ve BIST100 bileşimi değişiyor. Probe
    404'leri ve boş dönenleri önceden eler; asıl çekimde boşa istek atılmaz.
    """
    sonuc: Dict[str, Any] = {"gecerli": [], "gecersiz": {}, "tarih": _simdi_iso()}
    for i, sembol in enumerate(semboller, 1):
        tempo.bekle()
        df, sebep, gecici = _ham_cek(ticker_for(sembol), "5d", "1d")
        tempo.istek_bitti()
        if df is not None and len(df) > 0:
            tempo.basarili()
            sonuc["gecerli"].append(sembol)
            log(f"  [{i}/{len(semboller)}] ✅ {sembol}")
        else:
            if gecici:
                tempo.gecici_hata(sebep)
            sonuc["gecersiz"][sembol] = sebep[:160]
            log(f"  [{i}/{len(semboller)}] ❌ {sembol}: {sebep[:80]}")
        if tempo.dur:
            sonuc["uyari"] = "tempo ban koruması probe'u erken durdurdu"
            break
    sonuc["gecerli_sayisi"] = len(sonuc["gecerli"])
    sonuc["gecersiz_sayisi"] = len(sonuc["gecersiz"])
    hedef.mkdir(parents=True, exist_ok=True)
    with open(hedef / "probe_sonucu.json", "w", encoding="utf-8") as fh:
        json.dump(sonuc, fh, ensure_ascii=False, indent=1, sort_keys=True)
    # Doğrulanmış liste — asıl çekime doğrudan beslenebilir
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
def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="BIST derin geçmiş çekicisi (yalnız Yahoo -> disk; Supabase/Telegram yok).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--hedef", default=VARSAYILAN_HEDEF, help=f"çıktı dizini (varsayılan: {VARSAYILAN_HEDEF})")
    p.add_argument("--probe", action="store_true", help="yalnız geçerlilik testi (sembol başına 1 ucuz istek)")
    p.add_argument("--semboller", default="", help="virgülle ayrılmış sembol listesi (havuz/liste yerine)")
    p.add_argument("--liste-dosyasi", default="", help="sembol listesini dosyadan oku (örn. dogrulanmis_semboller.txt)")
    p.add_argument("--limit", type=int, default=0, help="yalnız ilk N sembol (pilot için)")
    p.add_argument("--period-1h", default=VARSAYILAN_PERIOD_1H, help="1h geçmişi (varsayılan 365d; Yahoo üst sınırı ~730d)")
    p.add_argument("--period-1d", default=VARSAYILAN_PERIOD_1D, help="1d geçmişi (varsayılan 2y)")
    p.add_argument("--interval", default="1h,1d", help="çekilecek aralıklar (varsayılan: 1h,1d)")
    p.add_argument("--deneme", type=int, default=3, help="geçici hatada azami deneme (varsayılan 3)")
    p.add_argument("--retry-failed", action="store_true", help="yalnız manifest'te başarısız olanları dene")
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
    tempo = Tempo(grup=args.grup, log=log)

    if args.wake_lock:
        _wake_lock(log)

    log("=" * 68)
    log("BIST DERİN GEÇMİŞ ÇEKİCİSİ — yalnız Yahoo -> disk")
    log("=" * 68)
    log(f"Hedef dizin : {hedef.resolve()}")
    log(f"Sembol      : {len(semboller)} ({semboller[0]} ... {semboller[-1]})")
    log(f"Aralıklar   : {intervals}")
    if not args.probe:
        log(f"Period      : 1h={args.period_1h}  1d={args.period_1d}")
    log(f"Tempo       : grup={args.grup}, istek arası {ISTEK_ARA_MIN_SN}-{ISTEK_ARA_MAX_SN} sn, "
        f"grup molası {GRUP_MOLA_MIN_SN:.0f}-{GRUP_MOLA_MAX_SN:.0f} sn")
    tahmini = len(semboller) * (1 if args.probe else len(intervals))
    log(f"Tahmini istek: {tahmini}  (~{tahmini/args.grup*(args.grup*1.2+12.5)/60:.0f} dk)")
    log("")

    if args.probe:
        probe(semboller, hedef, tempo, log=log)
        return 1 if tempo.dur else 0

    manifest = manifest_oku(hedef)
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
            if atlanmali_mi(onceki, dosya, zorla=args.zorla):
                log(f"  ⏭️  {interval}: zaten çekilmiş ({(onceki or {}).get('satir')} bar) — atlandı")
                sayac["atlandi"] += 1
                continue
            period = args.period_1h if interval == "1h" else args.period_1d
            kayit = sembol_cek(sembol, interval, period, hedef, tempo, deneme=args.deneme, log=log)
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
            # Her adımda yaz: Termux'ta süreç ölürse ilerleme kaybolmaz
            manifest["kayitlar"] = kayitlar
            manifest_yaz(hedef, manifest)

    sure = round(time.monotonic() - kosu_basladi, 1)
    ozet = {
        "basladi": _simdi_iso(), "sure_sn": sure, "mod": "backfill",
        "sembol_sayisi": len(semboller), "araliklar": intervals,
        "period_1h": args.period_1h, "period_1d": args.period_1d,
        "sonuclar": sayac, "toplam_istek": tempo.toplam_istek,
        "soguma_sayisi": tempo.soguma_sayisi, "ban_korumasi_durdurdu": tempo.dur,
    }
    manifest["kosular"].append(ozet)
    manifest["son_kosu"] = ozet
    manifest_yaz(hedef, manifest)

    log("")
    log("=" * 68)
    log("KOŞU ÖZETİ")
    log("=" * 68)
    log(f"Süre        : {sure/60:.1f} dk   Toplam istek: {tempo.toplam_istek}")
    log(f"Başarılı    : {sayac['ok']}")
    log(f"Atlanan     : {sayac['atlandi']} (zaten çekilmiş)")
    log(f"Kalıcı hata : {sayac['kalici']} (404/sembol yok — tekrar denenmedi)")
    log(f"Geçici hata : {sayac['gecici']} (--retry-failed ile yeniden dene)")
    if tempo.soguma_sayisi:
        log(f"Soğuma      : {tempo.soguma_sayisi} kez (ban koruması devreye girdi)")
    if tempo.dur:
        log("⚠️  KOŞU BAN KORUMASIYLA DURDURULDU. Birkaç saat bekleyip --retry-failed koş.")

    kirli = [
        (k, v.get("kalite", {})) for k, v in kayitlar.items()
        if v.get("durum") == "ok" and v.get("kalite", {}).get("split_sicramasi_adayi", 0) > 0
    ]
    if kirli:
        log(f"\n⚠️  {len(kirli)} kayıtta %10 üzeri fiyat sıçraması (split/temettü adayı):")
        for k, kal in kirli[:15]:
            log(f"     {k}: {kal.get('split_sicramasi_adayi')} bar")

    log(f"\nManifest    : {hedef/'manifest.json'}")
    log("Sonraki adım: docs/kurulum/TERMUX_BACKFILL.md — commit & push")
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
