# data/replay.py — seans/zaman takvimi + mum/resample motoru (Faz 8).

import pandas as pd
import numpy as np
from collections import deque
from datetime import date, datetime, timedelta, time as dt_time
import logging
import math
import os
import pickle
import tempfile
from typing import Dict, List, Optional, Tuple

from config import (
    ISTANBUL_TZ, BIST_OPEN, BIST_CLOSE, DEQUE_MAXLEN,
    DATA_DIR, SEED_DATA_DIR, MARKET_SUFFIX, yahoo_ticker_for_symbol,
    PROVIDER_SYMBOL_FALLBACK,
    CANDLE_CLOSE_MINUTE, SCAN_DELAY_AFTER_CLOSE_MIN, TARAMA_PENCERE_SONU,
    BIST_TATILLER, BIST_YARIM_GUNLER,
    VERI_YOK_MODU_ESIK_DK, SPLIT_SUREKLILIK_ESIK_PCT, BAR_BOSLUK_ESIK_SAAT,
    GUNLUK_FETCH_PERIOD, GUNLUK_DEQUE_MAXLEN,
    FULL_1H_FETCH_PERIOD, ROUTINE_1H_FETCH_PERIOD, FULL_1H_FETCH_STALE_DAYS,
    ALLOW_TRUSTED_PICKLE_CACHE,
)

import data as _pkg  # geç bağlama (plan §3)

def bist_tatil_adi(d) -> Optional[str]:
    """Configured BIST_TATILLER girdisi varsa adını, yoksa None döner.

    Takvimin resmî doğruluğu burada doğrulanmaz. Kod tatil varsayımıyla Yahoo
    fetch/tarama davranışını değiştirir; yıllık resmî takvim kontrolü gerekir.
    Neden? Takvimde tatil olarak işaretlenen günlerde kod fetch/tarama yapmaz;
    aksi durumda mevcut akış gereksiz istek ve eski-veri uyarısı üretebilir.
    Tatil takvimi bu iki sorunu birden keser.
    """
    return BIST_TATILLER.get(d.date() if isinstance(d, datetime) else d)


def yarim_gun_kapanisi(d) -> Optional[Tuple[str, dt_time]]:
    """Yarım günse (açıklama, kapanış saati), değilse None. Örnek: 19 Mart 2026 -> 13:00."""
    anahtar = d.date() if isinstance(d, datetime) else d
    return BIST_YARIM_GUNLER.get(anahtar)


def seans_kapanis_saati(d=None) -> dt_time:
    """O günün seans kapanış saati (yarım günde 13:00, normalde 18:30).

    Günlük (1d) mumun tamamlanma saatidir: kapanış fiyatı/müzayede oturduktan
    sonraki güvenli an.
    """
    if d is None:
        d = datetime.now(ISTANBUL_TZ)
    yg = yarim_gun_kapanisi(d)
    return yg[1] if yg else _pkg.GUNLUK_MUM_KAPANIS_SAATI


def seans_sonu_saati(d=None) -> dt_time:
    """Seansın GERÇEK bitiş saati (intraday barların kesme sınırı).

    Normal gün 18:00 (Yahoo regular period end ölçümü), yarım gün 13:00.
    Günlük mumdan farkı: 18:30 takas/müzayede payıdır; intraday bar 17:30'da
    biter ve 18:00'de kesin kapanmıştır.
    """
    if d is None:
        d = datetime.now(ISTANBUL_TZ)
    yg = yarim_gun_kapanisi(d)
    return yg[1] if yg else _pkg.INTRADAY_SEANS_SONU_SAATI


def is_bist_open(now: Optional[datetime] = None) -> bool:
    """
    BIST açık mı?
    - Hafta içi mi?
    - Saat 09:50-18:10 arası mı? (İstanbul)
    Neden? Bot sadece seans saatlerinde CPU harcasın, dışında uyusun
    """
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    else:
        # Eğer naive datetime gelirse Istanbul'a çevir
        if now.tzinfo is None:
            now = ISTANBUL_TZ.localize(now)
        else:
            now = now.astimezone(ISTANBUL_TZ)
    
    # Hafta sonu veya statik takvimde configured tatil kaydı mı?
    if now.weekday() >= 5 or bist_tatil_adi(now) is not None:
        return False

    # Yarım seans normal 18:10 sınırına kadar açık sayılmaz; gerçek kapanış
    # günün takviminden alınır. Böylece kapalı günlerde main loop 0 sn bekleyip
    # CPU'yu döndürmez.
    current_time = now.time()
    kapanis = min(BIST_CLOSE, seans_kapanis_saati(now))
    return BIST_OPEN <= current_time <= kapanis


def tarama_penceresi_acik_mi(now: Optional[datetime] = None) -> bool:
    """
    Bot şu an TARAMA yapmalı mı? (is_bist_open'tan farklı: configured seans
    kapanışı ve gecikmeden sonra son planlı tarama için ek pay verir.)

    Bu, yalnızca mevcut BIST_OPEN / statik tatil takvimi / CANDLE_CLOSE_MINUTE
    ayarlarının aritmetiğini uygular. Yahoo .IS 1H start/end timestamp sözleşmesi
    ve takvimin resmî doğruluğu bu checkout'ta bağımsız/live kaynakla doğrulanmadı.

    Hafta içi + BIST_OPEN..configured kapanış + gecikme/pay arası.
    """
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    else:
        if now.tzinfo is None:
            now = ISTANBUL_TZ.localize(now)
        else:
            now = now.astimezone(ISTANBUL_TZ)

    if now.weekday() >= 5:  # 5=Cumartesi, 6=Pazar
        return False

    # Resmî tatil: hiç tarama yapma (gereksiz fetch + yanlış "VERİ ESKİ" alarmı yok)
    tatil = bist_tatil_adi(now)
    if tatil:
        return False

    current_time = now.time()
    kapanis = seans_kapanis_saati(now)
    # kapanış + tarama gecikmesi + pay (time + timedelta doğrudan toplanamaz)
    pencere_sonu = (now.replace(hour=kapanis.hour, minute=kapanis.minute, second=0, microsecond=0)
                    + timedelta(minutes=SCAN_DELAY_AFTER_CLOSE_MIN + 5))
    return BIST_OPEN <= current_time <= pencere_sonu.time()


def islem_gunu_mu(now: Optional[datetime] = None) -> bool:
    """Bugün BIST işlem günü mü? (hafta içi VE resmî tatil değil)

    NEDEN AYRI: günlük özetler ve gün sonu analizi seans saatine bağlı değildir
    (09:55/18:45/20:00 hedefleri piyasa kapalıyken de saati gelir). Bu kontrol
    olmadan cumartesi/pazar ve resmî tatillerde kanala "öne çıkan formasyon
    olmadı" mesajı gidiyor, gece analizi boşuna tam evren taraması yapıyordu.

    Not: tarama kararı bu fonksiyona değil `tarama_animi_mi`'ye bağlıdır; burada
    yalnız "takvim işlem günü mü" sorusu cevaplanır.
    """
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    elif now.tzinfo is None:
        now = ISTANBUL_TZ.localize(now)
    else:
        now = now.astimezone(ISTANBUL_TZ)
    if now.weekday() >= 5:
        return False
    return bist_tatil_adi(now) is None


def sonraki_islem_gunu(baslangic) -> date:
    """Hafta sonu ve resmî tatilleri atlayarak bir sonraki işlem gününü bulur.

    Neden ayrı fonksiyon: ana döngü "BIST kapalı" dalında uyku süresini buradan
    alıyor. Tatil günü `is_bist_open` (tatili bilmez) True döndüğü için uyku 0'a
    düşüyor ve döngü boş dönüyordu (ölçüm: ~21.500 log satırı/sn; bir tatil günü
    ~600 milyon satır). Tatil atlanarak uyku en az bir sonraki seansa kalır.
    """
    aday = baslangic.date() if isinstance(baslangic, datetime) else baslangic
    for _ in range(60):  # takvim bozuksa bile sonsuz döngü olmasın
        aday = aday + timedelta(days=1)
        if aday.weekday() < 5 and bist_tatil_adi(aday) is None:
            return aday
    return aday


def time_until_next_open(now: Optional[datetime] = None) -> float:
    """Bir sonraki açılışa kadar kaç saniye? Uyku için.

    Sözleşme: tarama penceresi KAPALIYSA dönen değer HER ZAMAN > 0'dır ve gerçek
    sonraki seansa işaret eder; pencere açıkken 0. Ana döngünün kapalı dalı bu
    değerle uyuduğu için 0 dönmesi boş döngü (CPU + log fırtınası) demektir.
    Tatil/hafta sonu atlanır; yarım günde pencere kapandıktan sonra da bir sonraki
    işlem gününe atlanır.
    """
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    if now.tzinfo is None:
        now = ISTANBUL_TZ.localize(now)
    else:
        now = now.astimezone(ISTANBUL_TZ)

    # Pencere açıkken beklenecek bir şey yok (ana döngü zaten tarama dalına girer).
    if tarama_penceresi_acik_mi(now):
        return 0.0

    # Bugün geçerli bir işlem günü ve açılıştan önceyse bugünün açılışını seç;
    # aksi halde bir sonraki takvim gününden başla. Resmî tatiller de atlanır.
    aday = now.date()
    bugun_islem_gunu = aday.weekday() < 5 and bist_tatil_adi(aday) is None
    if not (bugun_islem_gunu and now.time() < BIST_OPEN):
        aday += timedelta(days=1)

    while aday.weekday() >= 5 or bist_tatil_adi(aday) is not None:
        aday += timedelta(days=1)

    next_open = ISTANBUL_TZ.localize(
        datetime.combine(aday, BIST_OPEN)
    )
    return max((next_open - now).total_seconds(), 0.0)


def time_until_next_candle_close(now: Optional[datetime] = None) -> float:
    """Configured close-minute + delay'e göre bir sonraki taramaya kadar bekle.

    CANDLE_CLOSE_MINUTE mevcut :30 kuralını korur. Yahoo Finance 1H timestamp'inin
    start/end etiket sözleşmesi bu checkout'ta bağımsız olarak doğrulanmadığından,
    bu hesaplama provider davranışının kanıtı olarak yorumlanmamalıdır.
    """
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    if now.tzinfo is None:
        now = ISTANBUL_TZ.localize(now)
    else:
        now = now.astimezone(ISTANBUL_TZ)

    # Bu saatin (veya bir sonraki saatin) yapılandırılmış :30 checkpoint'i
    kapanis = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=CANDLE_CLOSE_MINUTE)
    if kapanis <= now:
        kapanis += timedelta(hours=1)

    # Mum kapanışı + gecikme = tarama anı
    tarama = kapanis + timedelta(minutes=SCAN_DELAY_AFTER_CLOSE_MIN)

    # Mevcut yapılandırılmış son tarama hedefi (normal günde :35 varsayımı).
    # Bu aritmetik sağlayıcının mum timestamp sözleşmesini kanıtlamaz.
    son_tarama = now.replace(hour=TARAMA_PENCERE_SONU.hour,
                             minute=TARAMA_PENCERE_SONU.minute - SCAN_DELAY_AFTER_CLOSE_MIN,
                             second=0, microsecond=0)
    if tarama > son_tarama:
        if now < son_tarama:
            tarama = son_tarama
        elif now.time() <= TARAMA_PENCERE_SONU:
            # Son tarama anındayız (18:35-18:40) -> hemen tara.
            # Bu kontrol olmadan ana döngü "1dk'den fazla bekle" dalına düşüp günün
            # son taramasını uyuyarak geçiyordu.
            return 0.0

    return (tarama - now).total_seconds()


def son_kapanan_mum_ani(now: Optional[datetime] = None) -> Optional[datetime]:
    """Mevcut configured :30 close-minute kuralındaki en son 1H kapanış anı.

    Bu yardımcı provider label semantiğini kanıtlamaz; yfinance timestamp
    sözleşmesi doğrulanana kadar var olan planlama davranışı korunur.
    """
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    if now.tzinfo is None:
        now = ISTANBUL_TZ.localize(now)
    else:
        now = now.astimezone(ISTANBUL_TZ)

    # Mevcut konfigürasyondaki ilk kapanış hedefi 10:30'dur; normal ve yarım
    # seansın ikisi de bundan önce bir mumu/taramayı uygun saymaz.
    ilk_kapanis = (now.replace(hour=BIST_OPEN.hour, minute=BIST_OPEN.minute, second=0, microsecond=0)
                   + timedelta(minutes=40))
    # Mevcut takvim yarım günü 13:00 olarak yapılandırır; :30 kuralında son etiket 12:30 olur.
    yg = yarim_gun_kapanisi(now)
    if yg:
        kapanis = now.replace(hour=yg[1].hour, minute=yg[1].minute, second=0, microsecond=0)
        if now < kapanis:
            kapanis = (now.replace(minute=0, second=0, microsecond=0)
                       + timedelta(minutes=CANDLE_CLOSE_MINUTE))
            if kapanis > now:
                kapanis -= timedelta(hours=1)
        if kapanis < ilk_kapanis:
            return None
        return kapanis

    kapanis = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=CANDLE_CLOSE_MINUTE)
    if kapanis > now:
        kapanis -= timedelta(hours=1)
    if kapanis < ilk_kapanis:
        return None
    return kapanis


def tarama_animi_mi(now: Optional[datetime] = None,
                    son_taranan_kapanis: Optional[datetime] = None) -> bool:
    """
    Şu an tarama YAPILMALI MI?

    Kural: configured CANDLE_CLOSE_MINUTE + gecikme ayarıyla tarama anı hesaplanır.
    Sağlayıcı timestamp sözleşmesi doğrulanmadığından :30 bu kurulum varsayımıdır.
    Aynı kapanış iki kez taranmasın diye `son_taranan_kapanis` verilir.

    Ana döngü bunu kullanır: böylece eski "saat başı + 5 dk" mantığı (5 dk'lik uyku
    evreleri hedefi ıskaladığı için çoğu tarama saatini hiç yakalamıyordu)
    ve 18:35'te üst üste tekrar eden tarama fırtınası ortadan kalkar.
    """
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    if now.tzinfo is None:
        now = ISTANBUL_TZ.localize(now)
    else:
        now = now.astimezone(ISTANBUL_TZ)

    if now.weekday() >= 5:
        return False
    if bist_tatil_adi(now):
        return False  # configured tatil: tarama yok (takvim doğruluğu harici kaynak gerektirir)

    kapanis = son_kapanan_mum_ani(now)
    if kapanis is None:
        return False
    # Sadece bugünün seansına ait mumlar (dünkü son mumu yeniden taramayalım)
    if kapanis.date() != now.date():
        return False
    hedef = kapanis + timedelta(minutes=SCAN_DELAY_AFTER_CLOSE_MIN)
    if now < hedef:
        return False
    if son_taranan_kapanis is not None and kapanis <= son_taranan_kapanis:
        return False
    return True


def veri_yok_modu_acik_mi(now: Optional[datetime] = None,
                          son_bar_yasi_dk: Optional[float] = None) -> bool:
    """
    Bugün için piyasa verisi gelmiyor mu? (tatil / Yahoo arızası / bilinmeyen durum)

    Ne zaman True?
      - Takvimde tatil DEĞİL (tatil zaten tarama_penceresi_acik_mi'da elendi),
      - Seans içindeyiz,
      - En yeni cache 1H timestamp'i VERI_YOK_MODU_ESIK_DK (20 saat) yaşında veya daha eski.
        Bu yaş hesabı etiketlere dayanır; provider etiketinin mum başlangıcı/sonu
        olduğu ve seans içi gerçekliği bu doğrulama turunda canlı veride ölçülmedi.

    Neden gerekli? Faz 1 tazelik uyarısı tatillerde ve veri arızasında her turda
    bağırırdı (ölçüm: günde 270 satır). Bu modda tarama ATLANIR (gereksiz fetch de
    yok) ve tek satır log + heartbeat alanı ile görünür olur.
    """
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    if now.tzinfo is None:
        now = ISTANBUL_TZ.localize(now)
    else:
        now = now.astimezone(ISTANBUL_TZ)

    if son_bar_yasi_dk is None or son_bar_yasi_dk < VERI_YOK_MODU_ESIK_DK:
        return False
    if not tarama_penceresi_acik_mi(now):
        return False
    return bist_tatil_adi(now) is None


def _istanbul_zaman(ts):
    """Timestamp'i İstanbul saatine çevirir; pandas Timestamp ve datetime uyumlu.

    Neden: seri verisi farklı kaynaklardan gelebiliyor (pickle→Timestamp, JSON/
    Supabase→datetime). Tek bir yardımcı, `tz_convert` varsayımından doğan
    AttributeError sınıfını kapatır.
    """
    if isinstance(ts, datetime) and not hasattr(ts, "tz_convert"):
        return ts.astimezone(ISTANBUL_TZ) if ts.tzinfo else ISTANBUL_TZ.localize(ts)
    if hasattr(ts, "tz_convert"):
        return ts.tz_convert(ISTANBUL_TZ) if ts.tzinfo else ts.tz_localize(ISTANBUL_TZ)
    return ISTANBUL_TZ.localize(pd.Timestamp(ts))


# 2H/4H kova çapası (FAZ düzeltmesi, 2026-10-23): BIST seansinin ilk 1H
# etiketi. Çapa SABİTTİR ve İstanbul saatinde uygulanır; pencerenin ilk
# barından TÜRETİLMEZ. Türetilirse kayan 360 barlık pencerenin başı her
# saat döndükçe faz döner ve bütün 2H/4H tarihi yeniden yazılır
# (ölçüm: docs/arastirma/KOVA_FAZI_OLCUMU_2026-10-23.md — 4H senaryolarin
# yalnız %33'ü doğru fazdaydı, motorun nihai durumu %33 değişiyordu).
_SEANS_CAPASI = "9h30min"


def _bist_seans_serisi(idx_ist: pd.DatetimeIndex) -> bool:
    """Tüm barlar BIST seans saatlerinde mi? (İstanbul duvar saati 09-18)

    Kesintisiz semboller (BRENT/USDTRY/XAUUSD...) gece barı da taşır; onlarda
    seans çapası anlamsızdır, gece yarısı çapası kullanılır. Karar serinin
    kendi saatlerinden verilir: sembol listesine bağımlılık yok, yeni
    sembol sınıfı eklenirse davranış kendiliğinden doğru kalır.
    """
    if len(idx_ist) == 0:
        return False
    saatler = idx_ist.hour
    return int(saatler.min()) >= 9 and int(saatler.max()) <= 18


def _resample_sabit_capali(df: pd.DataFrame, timeframe: str,
                           available_cols: dict) -> pd.DataFrame:
    """2H/4H resample: sabit kova çapası, İstanbul saatinde hesaplanır.

    Girdi UTC (araştırma hattı) veya başka tz ile gelebilir: kova sınırları
    İstanbul gününe göre çizilir, çıktı girdinin tz'sine geri çevrilir —
    çağıranın tz sözleşmesi bozulmaz, kova ANLARI her yolda aynıdır.
    tz'siz dizin İstanbul duvar saati sayılır (kod tabanının genel sözleşmesi).
    """
    orijinal_tz = df.index.tz
    calis = df.tz_convert(ISTANBUL_TZ) if orijinal_tz is not None else df
    # Seans serisi: 09:30 çapası (TV/Pine hizası). Kesintisiz seri:
    # İstanbul gece yarısı — en azından deterministik; eski "ilk bar"
    # davranışı kesintisiz seride de fazı saatten saate döndürüyordu.
    offset = _SEANS_CAPASI if _bist_seans_serisi(calis.index) else "0h"
    out = calis.resample(timeframe, offset=offset).agg(available_cols)
    if orijinal_tz is not None:
        out = out.tz_convert(orijinal_tz)
    return out


def resample_ohlcv(df_1h: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    1H veriyi 2H, 4H, 1D'ye çevir
    Pine'daki resample mantığı ile aynı
    
    Neden dropna? BIST seans dışı boş mumlar oluşur, onları at
    Neden session gap handling? Gece mumları olmamalı
    
    ÖNEMLİ (B1 -> FAZ düzeltmesi): 2H/4H kovaları BIST SEANS başına (09:30)
    hizalanır. Neden? Pine'daki request.security(..., "120"/"240") seans başından
    sayar; pandas'in varsayılanı gece yarısıdır. Varsayıanla BIST gününün ilk 1H mumu
    (09:30) TEK BAŞINA bir "2H mumu" oluyor ve sonraki tüm barlar 1 saat kayıyordu
    -> 2H/4H formasyonlar TradingView'dekiyle aynı pivotları üretmiyordu.
    B1 çapayı "verinin ilk bari"ndan alıyordu; ilk bar her zaman seans başı
    OLMADIĞI için (kayan deque!) faz saatten saate dönüyordu. Çapa artık
    sabittir; ayrıntı ve ölçüm: docs/arastirma/KOVA_FAZI_OLCUMU_2026-10-23.md
    """
    if df_1h is None or len(df_1h) == 0:
        return pd.DataFrame()
    
    # Sütun isimleri küçük harf mi büyük mü kontrol et
    # Bizim deque open/high/low/close küçük, ama yfinance büyük olabilir
    df = df_1h.copy()
    # Normalize et - küçük harfe çevir
    df.columns = [c.lower() for c in df.columns]
    
    # Resample
    # open: first, high: max, low: min, close: last, volume: sum
    agg_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    
    # Sadece var olan sütunları agg'le
    available_cols = {k: v for k, v in agg_dict.items() if k in df.columns}
    
    try:
        # Kova hizası: günlük için gece yarısı (doğal), 2H/4H için SABİT çapa
        # (`_resample_sabit_capali`): BIST seans serisinde 09:30, kesintisiz
        # seride İstanbul gece yarısı. Çapa pencerenin ilk barından ASLA
        # türetilmez — türetilirse kayan pencere fazı saatten saate döndürür
        # ve bütün 2H/4H tarihi yeniden yazılır (FAZ düzeltmesi, 2026-10-23).
        if (timeframe in ("2h", "4h")
                and isinstance(df.index, pd.DatetimeIndex)
                and len(df.index) > 0):
            df_resampled = _resample_sabit_capali(df, timeframe, available_cols)
        else:
            df_resampled = df.resample(timeframe).agg(available_cols)
        
        # Boşları at - BIST seans dışı
        df_resampled.dropna(inplace=True)
        
        # Eğer hiç veri kalmadıysa
        if len(df_resampled) == 0:
            _pkg.logger.warning(f"{timeframe} resample sonrası boş - {len(df)} -> 0")
            return pd.DataFrame()
        
        _pkg.logger.debug(f"Resample {len(df)} 1H -> {len(df_resampled)} {timeframe}")
        return df_resampled
        
    except Exception as e:
        _pkg.logger.error(f"Resample hatası {timeframe}: {e}")
        return pd.DataFrame()


def _istanbul_dizin(idx) -> pd.DatetimeIndex:
    """Dizini Europe/Istanbul tz'li DatetimeIndex'e normalize eder (savunmalı).

    Savunma: object/karma-tz dizin küp operasyonlarında AttributeError üretir
    (idx.tz erişimi) — canlı 0/48 olayının kırılma noktası buydu. Yerel hata
    yerine tek adımda normalleştirilir; tarihsel zehirli veriler yutulmaz,
    dizin düzeltilip tarama tamamlanır.
    """
    if not isinstance(idx, pd.DatetimeIndex):
        idx = pd.DatetimeIndex(pd.to_datetime(idx, utc=True))
    if idx.tz is None:
        idx = idx.tz_localize(ISTANBUL_TZ)
    else:
        idx = idx.tz_convert(ISTANBUL_TZ)
    return idx


def _gun_kapanis_damgalari(idx: pd.DatetimeIndex, gunluk: bool) -> pd.DatetimeIndex:
    """Her barın kendi GÜNÜNE ait kapanış damgası (İstanbul tz).

    gunluk=True  -> günlük mum kuralı (normal 18:30 / yarım gün 13:00)
    gunluk=False -> seans sonu (normal 18:00 / yarım gün 13:00)
    """
    onbellek: Dict[date, dt_time] = {}
    damgalar = []
    for ts in idx:
        gun = ts.date()
        saat = onbellek.get(gun)
        if saat is None:
            saat = seans_kapanis_saati(gun) if gunluk else seans_sonu_saati(gun)
            onbellek[gun] = saat
        damgalar.append(ts.normalize() + pd.Timedelta(hours=saat.hour, minutes=saat.minute))
    return pd.DatetimeIndex(damgalar)


def mum_kapanis_anlari(idx, tf: str) -> pd.DatetimeIndex:
    """Her mumun kapandığı anı hesaplar (TEK KAYNAK, P0 kapanış kuralı).

    Kural: kapanış = etiket + TF süresi, ama o günün SEANS SONUNU aşamaz
    (17:30 etiketli 4h kovası 18:00'de kapanır; yarım günde 13:00).
    Günlük (1d) mum ise günün seans kapanışında (18:30 / yarım gün 13:00) tamamlanır.
    """
    idx = _istanbul_dizin(idx)
    if len(idx) == 0:
        return idx
    if str(tf).lower() == "1d":
        return _gun_kapanis_damgalari(idx, gunluk=True)
    sure = _pkg.TF_BAR_SURELERI.get(str(tf).lower())
    if sure is None:
        _pkg.logger.warning(f"Bilinmeyen timeframe '{tf}' - 1h süresi varsayıldı")
        sure = _pkg.TF_BAR_SURELERI["1h"]
    dogal = idx + sure
    seans_sonu = _gun_kapanis_damgalari(idx, gunluk=False)
    # Sadece seans içinde başlayıp seans sonunu AŞAN barlar kesilir (günün son 1h/2h/4h kovası);
    # 24 saatlik enstrümanlarda (örn. BRENT / BZ=F) 18:00 sonrasında başlayan barlar geri çekilmez.
    kesilecek = (idx < seans_sonu) & (dogal > seans_sonu)
    if bool(np.asarray(kesilecek, dtype=bool).any()):
        dogal = dogal.where(~np.asarray(kesilecek, dtype=bool), seans_sonu)
    return dogal


def mum_kapanis_ani(ts, tf: str) -> Optional[pd.Timestamp]:
    """Tek bir mumun (etiketli) kapandığı an. ts None ise None."""
    if ts is None:
        return None
    idx = _istanbul_dizin(pd.DatetimeIndex([pd.Timestamp(ts)]))
    kapanislar = mum_kapanis_anlari(idx, tf)
    return None if len(kapanislar) == 0 else kapanislar[0]


def bar_kapandi_mi(ts, tf: str, now: Optional[datetime] = None) -> bool:
    """Bu mum, verilen ana kadar GERÇEKTEN kapandı mı? (bildirim güvenlik kapısı).

    `tamamlanmis_mumlar` aynı kuralı kullanır; bu fonksiyon kapı/gösterim için
    tek bar üzerinde aynı hesabı yapar (tek kaynak: `mum_kapanis_anlari`).
    """
    kapanis = mum_kapanis_ani(ts, tf)
    if kapanis is None:
        return False
    sinir = pd.Timestamp(now) if now is not None else pd.Timestamp(datetime.now(ISTANBUL_TZ))
    sinir = sinir.tz_convert(ISTANBUL_TZ) if sinir.tzinfo else ISTANBUL_TZ.localize(sinir)
    return bool(kapanis <= sinir)


def tamamlanmis_mumlar(df: pd.DataFrame, tf: str, now: Optional[datetime] = None) -> pd.DataFrame:
    """Devam eden (yarım) mumu çıkarır; motoru yalnız KAPANMIŞ mumlarla besler.

    Kapanış kuralı `mum_kapanis_anlari`'dır (tek kaynak):
      * intraday: etiket + TF süresi, ama seans sonunu aşamaz
        (1h: +1 saat; 17:30 etiketli 2h/4h kovası 18:00'de kapanır; yarım gün 13:00),
      * günlük: günün seans kapanışı (normal 18:30 / yarım gün 13:00).

    Böylece Yahoo'nun etiket hizalaması ne olursa olsun her mum kapanışından
    sonraki İLK taramada beslenir (Pine bar kapanışı mantığıyla birebir) ve
    :00–:29 arası tetiklenen taramalar (restart/telafi) kısmi mumu görmez.
    """
    if df is None or len(df) == 0:
        return df
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        df.index = pd.to_datetime(df.index, utc=True)
    kapanis = mum_kapanis_anlari(df.index, tf)
    sinir = pd.Timestamp(now)
    sinir = sinir.tz_convert(ISTANBUL_TZ) if sinir.tzinfo else ISTANBUL_TZ.localize(sinir)
    tamam = np.asarray(kapanis <= sinir, dtype=bool)
    return df[tamam]


def resample_all_timeframes(df_1h: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    1H'den tüm timeframe'leri üret
    Döner: {'1h': df, '2h': df, '4h': df, '1d': df}
    """
    result = {}
    result['1h'] = df_1h
    
    for tf in ['2h', '4h', '1D']:
        resampled = resample_ohlcv(df_1h, tf)
        # Key'i normalize et: 1D -> 1d
        key = tf.lower()
        result[key] = resampled
    
    return result


