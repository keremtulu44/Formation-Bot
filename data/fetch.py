# data/fetch.py — yfinance sağlayıcı hattı (Faz 8).

import pandas as pd
import numpy as np
from collections import deque
from datetime import date, datetime, timedelta, time as dt_time
import logging
import math
import os
import pickle
import tempfile
import threading
from importlib import metadata as _metadata
from contextlib import nullcontext
from typing import Callable, Dict, List, Optional, Tuple

from config import (
    ISTANBUL_TZ, BIST_OPEN, BIST_CLOSE, DEQUE_MAXLEN,
    DATA_DIR, SEED_DATA_DIR, MARKET_SUFFIX, yahoo_ticker_for_symbol,
    PROVIDER_SYMBOL_FALLBACK, sembol_turu,
    CANDLE_CLOSE_MINUTE, SCAN_DELAY_AFTER_CLOSE_MIN, TARAMA_PENCERE_SONU,
    BIST_TATILLER, BIST_YARIM_GUNLER,
    VERI_YOK_MODU_ESIK_DK, SPLIT_SUREKLILIK_ESIK_PCT, BAR_BOSLUK_ESIK_SAAT,
    GUNLUK_FETCH_PERIOD, GUNLUK_DEQUE_MAXLEN,
    FULL_1H_FETCH_PERIOD, ROUTINE_1H_FETCH_PERIOD, FULL_1H_FETCH_STALE_DAYS,
    BOSLUK_TAMIR_TEKRAR_DK,
    ALLOW_TRUSTED_PICKLE_CACHE,
    TV_YEDEK_AKTIF, TV_GERCEK_4S_AKTIF, TV_EXCHANGE, TV_BAR_SAYISI,
    TV_ZAMAN_ASIMI_SN, TV_ARALIK, TV_SEMBOL_TURLERI,
)

import data as _pkg  # geç bağlama (plan §3)


# ------------------------------------------------- SAĞLAYICI ZİNCİRİ / DURUM --
# Yahoo birincil, tvDatafeed reaktif yedek. Durum /health üzerinden görünür;
# hiçbir veri uydurulmaz. Sayaçlar süreç içi gözlemseldir, kalıcı depoya yazmaz.
_SAGLAYICI_KILIT = threading.Lock()
_SAGLAYICI_DURUM: Dict[str, object] = {
    "yahoo_basari": 0, "yahoo_hata": 0,
    "tv_basari": 0, "tv_hata": 0, "yok": 0,
    "son_kaynak": None, "son_kaynak_by_symbol": {},
    "yahoo_son_basari": None, "yahoo_son_hata": None,
    "tv_son_basari": None, "tv_son_hata": None,
}


def _saglayici_zamani() -> str:
    return datetime.now(ISTANBUL_TZ).isoformat()


def _saglayici_kaydet(stock: str, kaynak: str, hata: str = "") -> None:
    """Kaynak başarı/hata sayacını ve son durumu güncelle (kilitli, ağ yok)."""
    anahtar = str(stock or "?").strip().upper()
    # Durum sözlüğü kısa önek kullanır: tvdatafeed -> tv_*. Yanlış önek
    # sayaçları görünmez kılardı (regresyon: test_tv_yahoo_uretim_zinciri).
    on_ek = "tv" if kaynak == "tvdatafeed" else kaynak
    with _SAGLAYICI_KILIT:
        if hata:
            _SAGLAYICI_DURUM[f"{on_ek}_hata"] = int(
                _SAGLAYICI_DURUM.get(f"{on_ek}_hata") or 0) + 1
            _SAGLAYICI_DURUM[f"{on_ek}_son_hata"] = str(hata)[:200]
        else:
            _SAGLAYICI_DURUM[f"{on_ek}_basari"] = int(
                _SAGLAYICI_DURUM.get(f"{on_ek}_basari") or 0) + 1
            _SAGLAYICI_DURUM[f"{on_ek}_son_basari"] = _saglayici_zamani()
            if kaynak in ("yahoo", "tvdatafeed"):
                _SAGLAYICI_DURUM["son_kaynak"] = kaynak
                _SAGLAYICI_DURUM["son_kaynak_by_symbol"][anahtar] = kaynak


def _tv_kurulum_bilgisi() -> Tuple[bool, Optional[str]]:
    """Kurulu TV dağıtımını doğrula; import/ağ yapmadan yalnız metadata okur."""
    for ad, surumler in (("tradingview-datafeed", ("2.1.1",)),
                         ("tvdatafeed", ("2.1.0",))):
        try:
            surum = _metadata.version(ad)
        except _metadata.PackageNotFoundError:
            continue
        return surum in surumler, f"{ad}=={surum}"
    return False, None


def saglayici_durumu() -> Dict[str, object]:
    """/health için gözlemsel sağlayıcı özeti; asla istisna fırlatmaz."""
    kurulu, dagitim = _tv_kurulum_bilgisi()
    with _SAGLAYICI_KILIT:
        ozet = dict(_SAGLAYICI_DURUM)
        ozet["son_kaynak_by_symbol"] = dict(
            _SAGLAYICI_DURUM["son_kaynak_by_symbol"])
    ozet.update({
        "tv_aktif": bool(TV_YEDEK_AKTIF),
        "tv_gercek_4s_aktif": bool(TV_GERCEK_4S_AKTIF),
        "tv_kurulu": kurulu,
        "tv_dagitim": dagitim,
        "tv_exchange": TV_EXCHANGE,
        "tv_zaman_asimi_sn": TV_ZAMAN_ASIMI_SN,
        "yahoo_birincil": True,
    })
    return ozet


def son_veri_kaynagi(stock: str) -> Optional[str]:
    """Sembol için son başarılı kaynak: 'yahoo' / 'tvdatafeed' / None."""
    with _SAGLAYICI_KILIT:
        return _SAGLAYICI_DURUM["son_kaynak_by_symbol"].get(
            str(stock or "").strip().upper())


def _tv_bar_sayisi(period: str, tf: str) -> int:
    """Kısa '5d' ön yükleme için gereksiz 500 bar isteme."""
    metin = str(period or "").strip().lower()
    if metin.startswith("5d") or metin.startswith("1d"):
        return min(TV_BAR_SAYISI, 60 if tf == "1h" else 30)
    return TV_BAR_SAYISI


def _tv_yedek_dene(
    stock: str, tf: str, period: str = "60d"
) -> Tuple[Optional[pd.DataFrame], str]:
    """Yahoo veri döndürmediğinde tvDatafeed'den OHLCV çeker.

    DÖNÜŞ: (frame|None, hata). Hiçbir durumda uydurulmuş/sentetik bar üretmez.
    Süreç TZ'si değiştirilmez; WS istemcisi ortak modülde `finally` ile kapanır;
    tüm çağrı `TV_ZAMAN_ASIMI_SN` ile sınırlıdır (anonim WS takılmasın).
    """
    if not TV_YEDEK_AKTIF:
        return None, "TV yedeği kapalı (TV_YEDEK_AKTIF=0)"
    if sembol_turu(stock) not in TV_SEMBOL_TURLERI:
        return None, "TV yalnız BIST hisse/endeks için (makro atlandı)"
    anahtar = str(tf or "").strip().lower()
    if anahtar not in TV_ARALIK:
        return None, f"TV aralığı desteklenmiyor: {tf!r}"

    sembol = str(stock or "").strip().upper()
    sonuc: Dict[str, object] = {}

    def _cek() -> None:
        try:
            from scripts import tvdatafeed_client as tv_client
            sonuc["frame"] = tv_client.get_hist(
                symbol=sembol, exchange=TV_EXCHANGE,
                interval=TV_ARALIK[anahtar],
                n_bars=_tv_bar_sayisi(period, anahtar))
        except Exception as exc:  # noqa: BLE001 - ağ/import hatası rapora düşsün
            sonuc["hata"] = f"{type(exc).__name__}: {exc}"

    isci = threading.Thread(target=_cek, daemon=True,
                            name=f"tv-{sembol}-{anahtar}")
    isci.start()
    isci.join(TV_ZAMAN_ASIMI_SN)
    if isci.is_alive():
        return None, f"TV zaman aşımı ({TV_ZAMAN_ASIMI_SN} sn)"
    if "hata" in sonuc:
        return None, str(sonuc["hata"])

    ham = sonuc.get("frame")
    if ham is None or not isinstance(ham, pd.DataFrame) or ham.empty:
        return None, "TV boş veya geçersiz sağlayıcı verisi"
    cerceve = ham.copy()
    cerceve.columns = [str(c).strip().lower() for c in cerceve.columns]
    if "symbol" in cerceve.columns:
        cerceve = cerceve.drop(columns=["symbol"])
    if not isinstance(cerceve.index, pd.DatetimeIndex):
        return None, "TV geçerli zaman indeksi döndürmedi"
    if cerceve.index.tz is None:
        # Ortak istemci 2.1.x'in naive yerel duvar saatini tzlocal() ile GERÇEK
        # UTC'ye çevirir; üretim hattına yalnızca tz-aware UTC gelmelidir.
        # Burada naive kalmışsa sözleşme bozulmuştur: ortam TZ'sine göre
        # uydurma dönüşüm DST / yanlış bar üretir → fail-closed.
        return None, "TV naive zaman damgası reddedildi (istemci UTC-aware dönmeli)"
    cerceve.index = cerceve.index.tz_convert(ISTANBUL_TZ)
    temiz = _saglayici_ohlcv_temizle(cerceve, stock=stock, timeframe=anahtar)
    if temiz is None or temiz.empty:
        return None, "TV geçerli OHLCV mumu döndürmedi"
    temiz.attrs.update({
        "veri_kaynagi": "tvdatafeed",
        "provider_symbol": sembol,
        "provider_fallback": True,
        "gercek_bar": True,
        "gercek_4h": anahtar == "4h",
        "tv_exchange": TV_EXCHANGE,
    })
    return temiz, ""


def _veri_zinciri(
    stock: str,
    period: str,
    tf: str,
    *,
    frame_validator: Optional[Callable] = None,
    request_context: Optional[Callable] = None,
) -> Tuple[Optional[pd.DataFrame], bool, str]:
    """Yahoo birincil → TV reaktif yedek → (None, retryable, gerekçe).

    TV yalnızca Yahoo hiç veri döndürmediğinde çağrılır. Yahoo GEÇİCİ hata
    verdiyse `retryable` korunur (mevcut tek yeniden deneme sözleşmesi bozulmaz);
    TV o anda kurtarırsa veri geldiği için yeniden denemeye gerek kalmaz.
    """
    try:
        frame, retryable, reason = _fetch_yfinance_adaylari(
            stock, period, tf, frame_validator=frame_validator,
            request_context=request_context)
    except Exception as exc:  # noqa: BLE001 - sağlayıcı hatası rapora düşsün
        frame = None
        retryable = yfinance_error_is_retryable(exc)
        reason = f"{type(exc).__name__}: {exc}"

    if frame is not None and len(frame):
        frame.attrs["veri_kaynagi"] = "yahoo"
        frame.attrs["saglayici_zinciri"] = ["yahoo"]
        frame.attrs["gercek_bar"] = False
        _saglayici_kaydet(stock, "yahoo")
        return frame, False, ""

    _saglayici_kaydet(stock, "yahoo", reason)
    tv, tv_hata = _tv_yedek_dene(stock, tf, period)
    if tv is None:
        _saglayici_kaydet(stock, "tvdatafeed", tv_hata)
        with _SAGLAYICI_KILIT:
            _SAGLAYICI_DURUM["yok"] = int(_SAGLAYICI_DURUM["yok"]) + 1
            _SAGLAYICI_DURUM["son_kaynak_by_symbol"].pop(
                str(stock or "").strip().upper(), None)
        return None, retryable, f"{reason} | tv: {tv_hata}"

    if frame_validator is not None:
        try:
            degerlendirme = frame_validator(tv)
            if isinstance(degerlendirme, tuple):
                kabul, neden = bool(degerlendirme[0]), str(degerlendirme[1] or "")
            else:
                kabul, neden = bool(degerlendirme), ""
        except Exception as exc:  # noqa: BLE001
            kabul, neden = False, f"tazelik doğrulaması {type(exc).__name__}"
        if not kabul:
            _saglayici_kaydet(stock, "tvdatafeed", neden)
            return None, retryable, f"{reason} | tv: {neden or 'tazelik doğrulaması'}"

    tv.attrs["saglayici_zinciri"] = ["yahoo", "tvdatafeed"]
    _saglayici_kaydet(stock, "tvdatafeed")
    _pkg.logger.warning(
        "%s: Yahoo %s veri döndürmedi (%s); tvDatafeed yedeği kullanıldı "
        "(%d bar). Kaynak etiketi: tvdatafeed",
        stock, tf, reason[:160], len(tv))
    return tv, False, ""


def fetch_tv_4h(stock: str) -> Optional[pd.DataFrame]:
    """TradingView GERÇEK 4s barları (türetilmiş 4s yerine kullanılmak üzere).

    Yalnızca TV yedeğinin kullanıldığı sembollerde, tarama katmanı tarafından
    çağrılır. Kapalıysa/kurulu değilse None döner; üretim akışı bozulmaz.
    """
    if not TV_GERCEK_4S_AKTIF or son_veri_kaynagi(stock) != "tvdatafeed":
        return None
    frame, hata = _tv_yedek_dene(stock, "4h", "60d")
    if frame is None:
        _saglayici_kaydet(stock, "tvdatafeed", f"gerçek 4s: {hata}")
        _pkg.logger.warning("%s: gerçek 4s alınamadı (%s); türetilmiş 4s kullanılacak",
                            stock, hata)
        return None
    _saglayici_kaydet(stock, "tvdatafeed")
    return frame


def _saglayici_ohlcv_temizle(
    df: Optional[pd.DataFrame],
    *,
    stock: str = "",
    timeframe: str = "1h",
) -> Optional[pd.DataFrame]:
    """Sağlayıcıdan gelen ham OHLCV tablosundaki münferit bozuk/tatil satırlarını ayıklar.

    Yahoo Finance bazı sembollerde (ör. USDTRY=X, XU050.IS, tatil günleri veya
    yeni açılan yarım barlar) 500 satırın içine 1-2 adet NaN OHLC, NaN hacim,
    float32 yuvarlama kayması veya resmî tatilde 0-hacimli düz çizgi satırı
    bırakabiliyor. Tek bir bozuk satır yüzünden tüm geçmişin reddedilmesini
    önlemek için sağlayıcı çıkışında yalnızca geçerli satırlar korunur; tüm
    tablo bozuksa None döner ve üst katman normal hata yolunu izler.

    SESSİZ ELEME YOK (2026-11-16): ayıklanan satır sayıları `attrs` içinde
    (`ham_satir`, `reddedilen_satir`, `hayalet_satir`) çağırana taşınır; fetch
    katmanı bunları uyarı olarak loglar. Önceden 500 satırın 30'u elense bile
    hiçbir iz kalmıyordu — "eksik çekilip geçilme" tam olarak buydu.
    """
    if df is None or len(df) == 0:
        return None
    gerekli = ["open", "high", "low", "close", "volume"]
    if not all(c in df.columns for c in gerekli):
        return None

    ham_satir = int(len(df))
    hayalet_sayisi = 0
    calis = df[gerekli].copy()
    for col in ("open", "high", "low", "close"):
        calis[col] = pd.to_numeric(calis[col], errors="coerce")
    calis["volume"] = pd.to_numeric(calis["volume"], errors="coerce").fillna(0.0)

    fiyat_mat = calis[["open", "high", "low", "close"]].to_numpy(dtype=float)
    hacim_dizi = calis["volume"].to_numpy(dtype=float)
    sonlu_maske = np.isfinite(fiyat_mat).all(axis=1) & np.isfinite(hacim_dizi)
    pozitif_maske = (fiyat_mat > 0.0).all(axis=1) & (hacim_dizi >= 0.0)
    gecerli_maske = sonlu_maske & pozitif_maske
    if not bool(gecerli_maske.any()):
        return None
    calis = calis.loc[gecerli_maske].copy()

    o = calis["open"].to_numpy(dtype=float)
    h = calis["high"].to_numpy(dtype=float)
    l = calis["low"].to_numpy(dtype=float)
    c = calis["close"].to_numpy(dtype=float)
    ust_zarf = np.maximum(o, c)
    alt_zarf = np.minimum(o, c)
    tol = np.maximum(np.abs(c) * 1e-4, 1e-6)

    # Küçük float32->float64 yuvarlama taşmalarını zarfa oturt; gerçek bozuk satırları ele.
    h_duz = np.where((h < ust_zarf) & ((ust_zarf - h) <= tol), ust_zarf, h)
    l_duz = np.where((l > alt_zarf) & ((l - alt_zarf) <= tol), alt_zarf, l)
    calis["high"] = h_duz
    calis["low"] = l_duz

    ohlc_uyumlu = (h_duz >= l_duz) & (h_duz >= ust_zarf) & (l_duz <= alt_zarf)
    if not bool(ohlc_uyumlu.all()):
        calis = calis.loc[ohlc_uyumlu].copy()
    if calis.empty:
        return None

    # BIST hisse/endeks günlük serilerinde sağlayıcının işlem olmayan günlerde
    # ürettiği 0-hacimli düz çizgi (O=H=L=C, V=0) hayalet barları ayıkla.
    if (
        str(timeframe).strip().lower() == "1d"
        and sembol_turu(stock) != "makro"
        and isinstance(calis.index, pd.DatetimeIndex)
    ):
        duz_bar = (calis["high"] - calis["low"]).abs() <= 1e-9
        sifir_hacim = calis["volume"] <= 0.0
        hayalet = duz_bar & sifir_hacim
        if bool(hayalet.any()) and bool((~hayalet).any()):
            hayalet_sayisi = int(hayalet.sum())
            calis = calis.loc[~hayalet].copy()

    if len(calis) <= 0:
        return None
    calis.attrs["ham_satir"] = ham_satir
    calis.attrs["hayalet_satir"] = hayalet_sayisi
    calis.attrs["reddedilen_satir"] = ham_satir - len(calis)
    return calis

def saglayici_adaylari(stock: str) -> List[str]:
    """Sembolün sağlayıcı adları: önce birincil, sonra varsa yedek.

    Neden: bazı ürünler tek bir sağlayıcı serisiyle güvenilir değil. Özellikle
    `XAUUSD`/`XAGUSD` gibi parite adları: spot seri yoksa vadeli seri (GC=F/SI=F)
    aynı ons fiyatını izler. Sessiz veri boşluğu yerine yedeğe düşülür ve hangi
    serinin kullanıldığı loga yazılır — kullanıcı hangi fiyatı gördüğünü bilir.
    """
    anahtar = str(stock or "").strip().upper()
    birincil = yahoo_ticker_for_symbol(stock)
    yedek = PROVIDER_SYMBOL_FALLBACK.get(anahtar)
    if yedek and yedek != birincil:
        return [birincil, yedek]
    return [birincil]


def _fetch_yfinance_adaylari(
    stock: str,
    period: str,
    interval: str,
    *,
    frame_validator: Optional[Callable] = None,
    request_context: Optional[Callable] = None,
):
    """Adayları doğrula; geçici sağlayıcı hatasında ikinci seriye yüklenme.

    Spot ve vadeli aynı enstrüman değildir. Normal taramada yedek yalnız
    birincil seri boş/geçersiz olduğunda denenir; geçici (ağ) hatada yedeğe
    geçilmez, `retryable=True` ile çağırana yeniden denetilir. Grafik için isteğe bağlı
    ``frame_validator`` bayat ama yapısal olarak geçerli birincil seriyi de
    reddedebilir; böylece taze bir yedek varsa ona geçilir. ``request_context``
    sağlayıcı adayı başına ortak Yahoo pacer'ını uygular.
    """
    import contextlib
    import io
    import yfinance as yf

    reasons = []
    for sira, ticker in enumerate(saglayici_adaylari(stock)):
        captured = io.StringIO()
        try:
            context = request_context(ticker) if callable(request_context) else nullcontext()
            with context:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(captured):
                    ham = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
            if ham is None or ham.empty:
                reason = captured.getvalue().strip() or "Yahoo boş veri döndürdü"
            else:
                ham = ham.rename(columns=str.lower)
                if not isinstance(ham.index, pd.DatetimeIndex):
                    reason = "Sağlayıcı geçerli zaman indeksi döndürmedi"
                else:
                    if ham.index.tz is None:
                        ham.index = ham.index.tz_localize("UTC").tz_convert(ISTANBUL_TZ)
                    else:
                        ham.index = ham.index.tz_convert(ISTANBUL_TZ)
                    temiz = _saglayici_ohlcv_temizle(ham, stock=stock, timeframe=interval)
                    if temiz is not None and not temiz.empty:
                        # Sessiz eleme yok: sağlayıcı yanıtından satır atıldıysa görünür olsun.
                        # (Bozuk satır yüzünden tüm geçmişi reddetmek yerine kısmi kabul
                        # ediyoruz; ama kullanıcı kaç mumun neden düştüğünü bilmeli.)
                        _reddedilen = int(temiz.attrs.get("reddedilen_satir") or 0)
                        if _reddedilen > 0:
                            _pkg.logger.warning(
                                "%s: sağlayıcı %s %s yanıtında %d/%d satır elendi "
                                "(%d hayalet gün, kalan %d mum); seri eksik olabilir",
                                stock,
                                ticker,
                                interval,
                                _reddedilen,
                                int(temiz.attrs.get("ham_satir") or len(temiz)),
                                int(temiz.attrs.get("hayalet_satir") or 0),
                                len(temiz),
                            )
                        kabul, dogrulama_nedeni = True, ""
                        if frame_validator is not None:
                            try:
                                sonuc = frame_validator(temiz)
                                if isinstance(sonuc, tuple):
                                    kabul, dogrulama_nedeni = bool(sonuc[0]), str(sonuc[1] or "")
                                else:
                                    kabul = bool(sonuc)
                            except Exception as exc:  # doğrulama hatası fallback'e izin verir
                                kabul = False
                                dogrulama_nedeni = f"grafik tazelik doğrulaması {type(exc).__name__} ile başarısız"
                        if kabul:
                            temiz.attrs["provider_symbol"] = ticker
                            temiz.attrs["provider_fallback"] = bool(sira)
                            if sira:
                                _pkg.logger.warning("%s: yedek sağlayıcı serisi kullanıldı (%s); spot ile aynı enstrüman olmayabilir", stock, ticker)
                            return temiz, False, ""
                        reason = dogrulama_nedeni or "Grafik tazelik doğrulamasını geçemedi"
                    else:
                        reason = "Sağlayıcı geçerli OHLCV mumu döndürmedi"
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
        retryable = yfinance_error_is_retryable(reason)
        reasons.append(f"{ticker}: {reason}")
        if retryable:
            # Geçici hata: YEDEĞE GEÇİLMEZ, çağıran yeniden dener (sözleşme
            # `test_grafik_veri_guvenilirligi.py::test_gecici_hatada_yedek_istegi_yok`).
            # Gerekçe: ağ hatası anında vadeli/spot seriyi sessizce değiştirmek
            # yanıltıcıdır. Bu yüzden "eksik kalma" riski yeniden-deneme
            # tarafında çözülür (bkz. başarısız 1D denemesinde kısa soğuma).
            return None, True, "; ".join(reasons)
        _pkg.logger.info("%s: sağlayıcı %s %s başarısız: %s", stock, ticker, interval, reason)
    return None, False, "; ".join(reasons)


def fetch_yfinance_chart_data(
    stock: str,
    interval: str,
    period: str,
    *,
    frame_validator: Optional[Callable] = None,
    request_context: Optional[Callable] = None,
):
    """`/grafik` için pacing ve tazelik doğrulamalı tek sembol fetch'i.

    Dönen sözleşme `(DataFrame|None, retryable, reason)` biçimindedir; eski
    1H/1D cache yolları etkilenmez. Birincil seri yapı olarak geçerli ama stale
    ise validator reddeder ve varsa kaynak yedeği ayrıca denenir.
    """
    tf = str(interval or "").strip().lower()
    if tf not in ("1h", "1d"):
        raise ValueError("Grafik fetch interval yalnızca 1h veya 1d olabilir")
    return _veri_zinciri(
        stock,
        period,
        tf,
        frame_validator=frame_validator,
        request_context=request_context,
    )


def fetch_yfinance_1d(stock: str, period: str = GUNLUK_FETCH_PERIOD) -> Optional[pd.DataFrame]:
    """Günlük derin OHLCV geçmişini sağlayıcıdan çeker (Yahoo → TV yedek)."""
    try:
        frame, _retryable, _reason = _veri_zinciri(stock, period, "1d")
        return frame
    except Exception as exc:
        _pkg.logger.debug("%s 1D fetch hatası: %s", stock, exc)
        return None


def seans_ici_bosluk_sayisi(cached: Optional[pd.DataFrame]) -> int:
    """Cache'te AYNI seans içindeki 1H mum boşluklarını say (eksik çekilmiş bar).

    Neden: rutin pencere yalnız son 5 günü indirir. Cache'te daha eski bir
    seans içi delik varsa (sağlayıcı kesintisi, yarım kalan fetch, bozuk
    append) bu pencere onu ASLA kapatmaz; bot da delikli seriyle formasyon
    hesaplamaya devam eder. Boşluk sayısı, fetch penceresini tam (60d) seçip
    deliği onarmak için kullanılır.

    Eşik `BAR_BOSLUK_ESIK_SAAT`tir (1,5 saat): 1H mumlar 1 saat arayla gelir,
    bu yüzden 1,5 saati aşan aynı-gün aralığı en az bir eksik mum demektir.
    Gece/hafta sonu aralıkları farklı güne düştüğü için sayılmaz.
    """
    if cached is None or len(cached) < 3:
        return 0
    try:
        idx = pd.DatetimeIndex(pd.to_datetime(cached.index))
    except (TypeError, ValueError):
        return 0
    if len(idx) < 3:
        return 0
    if idx.tz is None:
        idx = idx.tz_localize(ISTANBUL_TZ)
    idx = idx.sort_values()
    fark = idx[1:] - idx[:-1]
    ayni_gun = np.array([a.date() == b.date() for a, b in zip(idx[:-1], idx[1:])])
    esik = pd.Timedelta(hours=float(BAR_BOSLUK_ESIK_SAAT))
    return int(np.count_nonzero(ayni_gun & (fark > esik)))


def select_yfinance_1h_period(
    cached: Optional[pd.DataFrame],
    now: Optional[datetime] = None,
) -> str:
    """Cache'e göre 1H fetch penceresini seç.

    İlk/boş cache veya 5 günden eski cache tam geçmiş alır. Sağlıklı ve yakın
    cache için son 5 günlük pencere yeterlidir; append_dataframe zaman bazında
    tekilleştirdiği için bu pencereyi güvenle birleştirebiliriz.
    """
    if cached is None or len(cached) < 50:
        return FULL_1H_FETCH_PERIOD

    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    elif now.tzinfo is None:
        now = ISTANBUL_TZ.localize(now)
    else:
        now = now.astimezone(ISTANBUL_TZ)

    latest = pd.Timestamp(cached.index[-1])
    if latest.tzinfo is None:
        latest = ISTANBUL_TZ.localize(latest.to_pydatetime())
    else:
        latest = latest.tz_convert(ISTANBUL_TZ)

    age_days = (now - latest.to_pydatetime()).total_seconds() / 86400.0
    if age_days > FULL_1H_FETCH_STALE_DAYS:
        return FULL_1H_FETCH_PERIOD
    return ROUTINE_1H_FETCH_PERIOD


def yfinance_error_is_retryable(error) -> bool:
    """Sadece geçici ağ/rate-limit hatalarını yeniden denemeye uygun say.

    Yahoo'nun desteklemediği semboller veya 404/no-data sonuçları tekrar denenmez.
    Bu ayrım, geçici hata olmayan hisselere gereksiz istek gönderilmesini önler.
    """
    text = f"{type(error).__name__} {error}".lower()
    permanent_markers = (
        "404", "possibly delisted", "may be delisted", "no data found",
        "no timezone found", "symbol not found", "not found",
    )
    if any(marker in text for marker in permanent_markers):
        return False

    transient_markers = (
        "429", "too many requests", "rate limit", "ratelimit",
        "timeout", "timed out", "connection", "temporarily unavailable",
        "502", "503", "504", "service unavailable", "bad gateway",
        "gateway timeout", "network is unreachable", "remote disconnected",
    )
    return any(marker in text for marker in transient_markers)


def fetch_yfinance_1h(
    stock: str,
    period: str = "60d",
    with_status: bool = False,
):
    """yfinance'den 1h OHLCV çeker; varsayılan olarak DataFrame veya None döner.

    with_status=True iken (DataFrame/None, geçici-hata-mı, hata-açıklaması)
    döndürür; ana tarama bunu kullanarak yalnız geçici hataları bir kez tekrarlar.
    Not: Yahoo bazı sembolleri taşımıyor (örn. KOZAL.IS / KOZAA.IS -> HTTP 404).

    ÖNEMLİ - auto_adjust=False: yfinance'in default'ı auto_adjust=True (v0.2.51+).
    True iken geçmiş OHLC temettü/splite göre YENİDEN AYARLANIR; TradingView/Pine ise
    ham fiyat kullanır. Bu port sırasında parametre düşmüştü -> temettü sonrası tüm
    geçmiş kayar, pivot/sınır/ATR değerleri Pine'dan sapardı. Geri konuldu.
    """
    # Ortak Yahoo yolu history çağrısını auto_adjust=False ile yapar; TV yedeği
    # de ham (splits-only) kapanış kullanır. İkisi aynı fiyat ölçeğindedir.
    df, retryable, reason = _veri_zinciri(stock, period, "1h")
    return (df, retryable, reason) if with_status else df


def fetch_last_bar(stock: str) -> Optional[pd.DataFrame]:
    """Sabah pre-load için son 5 günlük 1h veriyi hafifçe çeker (0-latency açılış)."""
    return _pkg.fetch_yfinance_1h(stock, period="5d")


def mock_fetch_60d_1h(stock: str, n_bars: int = 360) -> pd.DataFrame:
    """
    Mock veri çekme - gerçek API yoksa test için
    Gerçek implementasyonda burası yfinance/borsapy olacak
    """
    np.random.seed(hash(stock) % 2**32)
    
    # Son 60 iş günü ~ 360 saat
    end = datetime.now(ISTANBUL_TZ)
    # İş günlerini hesapla - basit: son 60 gün, ama hafta sonu atla
    # Şimdilik sadece hourly freq
    dates = pd.date_range(end=end, periods=n_bars, freq='h')
    
    # Random walk - hisseye göre farklı seed
    base_price = 10 + (hash(stock) % 100)  # Her hisse farklı fiyat
    close = base_price + np.cumsum(np.random.randn(n_bars) * 0.3)
    close = np.maximum(close, 1.0)  # Negatif olmasın
    
    open_ = close + np.random.randn(n_bars) * 0.1
    high = np.maximum(open_, close) + np.abs(np.random.randn(n_bars) * 0.2)
    low = np.minimum(open_, close) - np.abs(np.random.randn(n_bars) * 0.2)
    low = np.maximum(low, 0.5)
    volume = np.random.randint(100000, 5000000, n_bars)
    
    df = pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    return df


