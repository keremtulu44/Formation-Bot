# --- DATA LAYER ---
# BIST veri katmanı - deque, resampling, BIST saat kontrolü
# Türkçe açıklamalar: Her fonksiyon ne yapar, neden?

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
    CANDLE_CLOSE_MINUTE, SCAN_DELAY_AFTER_CLOSE_MIN, TARAMA_PENCERE_SONU,
    BIST_TATILLER, BIST_YARIM_GUNLER,
    VERI_YOK_MODU_ESIK_DK, SPLIT_SUREKLILIK_ESIK_PCT, BAR_BOSLUK_ESIK_SAAT,
    GUNLUK_FETCH_PERIOD, GUNLUK_DEQUE_MAXLEN,
    FULL_1H_FETCH_PERIOD, ROUTINE_1H_FETCH_PERIOD, FULL_1H_FETCH_STALE_DAYS,
    ALLOW_TRUSTED_PICKLE_CACHE,
)

logger = logging.getLogger(__name__)


def _atomic_write(path: str, mode: str, writer, *, encoding: Optional[str] = None) -> None:
    """Write a sibling temp file, fsync it, and atomically replace one cache file."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=directory
    )
    fd_open = True
    try:
        if "b" in mode:
            stream = os.fdopen(fd, mode)
        else:
            stream = os.fdopen(fd, mode, encoding=encoding or "utf-8")
        fd_open = False
        with stream:
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        if fd_open:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass


def _atomic_json_write(path: str, payload, *, indent=None) -> None:
    import json

    _atomic_write(
        path,
        "w",
        lambda stream: json.dump(payload, stream, ensure_ascii=False, indent=indent),
        encoding="utf-8",
    )


def _atomic_pickle_write(path: str, payload) -> None:
    _atomic_write(path, "wb", lambda stream: pickle.dump(payload, stream))


# Timeframe -> pandas süre etiketi (tamamlanmis_mumlar filtresi için)
TF_SURELERI = {"1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D"}

# --- MUM KAPANIŞ KURALI (P0 düzeltmesi, 2 Eki 2026) -------------------------
# ÖLÇÜM (Yahoo chart API, THYAO.IS; meta.currentTradingPeriod.regular):
#   * Seans 09:30–18:00, barlar SOL etiketli (etiket = bar BAŞI): 09:30, 10:30, ... 17:30.
#   * Bir barın ömrü = etiket + TF süresi. GÜNÜN SON barı/kovası seans sonunda KESİLİR
#     (17:30 etiketli kova 18:00'de kapanır; 4 saatlikte bu 30 dakikalık kovadır —
#     TradingView'in BIST 4h grafiğinde de aynı).
#
# ESKİ HATA 1: 1h için "+30 dk" kullanılıyordu -> 10:30 barı 11:00'de "kapandı"
#   sayılıyordu. Normal :35 taramaları doğru barı görüyordu ama :00–:29 arasında
#   tetiklenen bir tarama (restart / kaçırılan tarama telafisi / çok uzun tur)
#   HENÜZ KAPANMAMIŞ 1h mumunu kapanmış sayıp bildirim üretebiliyordu.
# ESKİ HATA 2: 2h/4h için kesme yoktu -> günün son kovası (17:30) "+2sa/+4sa" kuralıyla
#   19:30/21:30'a kadar "yarım" kalıyor, 18:35 taramasında hiç analiz edilmiyordu
#   (ölçüm: 2h son kova 15:30, 4h son kova 13:30). Günün kapanış saati kayıptı.
# ESKİ HATA 3: 1d mumu sabit 18:30'da tamamlanıyordu; yarım günde (arefe, 13:00 kapanış)
#   mum 18:30'a kadar "yarım" kalıyor ve o gün günlük bildirim hiç gitmiyordu.
TF_BAR_SURELERI = {
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
    "4h": timedelta(hours=4),
}
# Günlük (1d) mum: 00:00 etiketli, seans kapanışında tamamlanır (normal 18:30, yarım gün 13:00).
GUNLUK_MUM_KAPANIS_SAATI = dt_time(18, 30)  # BIST seans kapanışı + takas payı (1H ölçümünden)
# Seansın GERÇEK bitiş saati (intraday barların kesme sınırı): normal gün 18:00, yarım gün 13:00.
# Ölçüm: Yahoo regular period 09:30–18:00; kapanış müzayedesi fiyatı ~18:09'da oluşur.
INTRADAY_SEANS_SONU_SAATI = dt_time(18, 0)

# === BIST SAAT KONTROLÜ ===

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
    return yg[1] if yg else GUNLUK_MUM_KAPANIS_SAATI


def seans_sonu_saati(d=None) -> dt_time:
    """Seansın GERÇEK bitiş saati (intraday barların kesme sınırı).

    Normal gün 18:00 (Yahoo regular period end ölçümü), yarım gün 13:00.
    Günlük mumdan farkı: 18:30 takas/müzayede payıdır; intraday bar 17:30'da
    biter ve 18:00'de kesin kapanmıştır.
    """
    if d is None:
        d = datetime.now(ISTANBUL_TZ)
    yg = yarim_gun_kapanisi(d)
    return yg[1] if yg else INTRADAY_SEANS_SONU_SAATI


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


# === DEQUE YÖNETİMİ ===

def ohlcv_girdi_sorunlari(df) -> List[str]:
    """Sağlayıcıdan gelen OHLCV frame'ini analiz öncesi doğrula (TEK SINIR).

    Doğrulama sınırı append kapısıdır: `append_dataframe` ve
    `append_gunluk_dataframe` geçersiz frame'i deque'ye HİÇ yazmaz; böylece
    formation ve domain motorları ile disk/Supabase kalıcılığı bozuk veriden
    korunur. Kural sözleşmesi:
      - Sıfır hacim mevcut doğrulama sözleşmesinde GEÇERLİDİR; bu kural tek başına
        Yahoo .IS sağlayıcısının ilk-bar davranışını kanıtlamaz.
      - Negatif hacim, NaN/sonlu olmayan herhangi bir alan, imkânsız OHLC
        ilişkisi (high<low, high<max(open,close), low>min(open,close)) ve
        <=0 fiyatlar geçersizdir.
      - Duplicate/sırasız timestamp burada REDDEDİLMEZ: append timestamp bazlı
        tekilleştirir ve sıralar (idempotent birleştirme sözleşmesi korunur).
      - Kapanmamış/gelecek mum burada elemeNMEZ: `tamamlanmis_mumlar` analiz
        katmanında filtreler (çift doğrulama çoğaltması yapılmaz).
    Dönen liste boşsa frame kabul edilir; doluysa sorun tiplerini verir.
    """
    if df is None or len(df) == 0:
        return ["bos_frame"]
    gerekli = ("open", "high", "low", "close", "volume")
    eksik = [sutun for sutun in gerekli if sutun not in getattr(df, "columns", ())]
    if eksik:
        return ["eksik_sutun:" + ",".join(eksik)]
    try:
        farkli_tz = set()
        for raw_timestamp in df.index:
            if not isinstance(raw_timestamp, (str, datetime, np.datetime64, pd.Timestamp)):
                return ["gecersiz_timestamp"]
            parsed_timestamp = pd.Timestamp(raw_timestamp)
            if pd.isna(parsed_timestamp):
                return ["gecersiz_timestamp"]
            farkli_tz.add(parsed_timestamp.tzinfo is not None)
        if len(farkli_tz) > 1:
            return ["karisik_zaman_dilimi"]
    except (TypeError, ValueError, OverflowError, AttributeError):
        return ["gecersiz_timestamp"]
    try:
        o = pd.to_numeric(df["open"], errors="coerce").to_numpy(dtype=float)
        h = pd.to_numeric(df["high"], errors="coerce").to_numpy(dtype=float)
        l = pd.to_numeric(df["low"], errors="coerce").to_numpy(dtype=float)
        c = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
        v = pd.to_numeric(df["volume"], errors="coerce").to_numpy(dtype=float)
    except (TypeError, ValueError, AttributeError):
        return ["sayisal_olmayan"]

    sorunlar: List[str] = []
    fiyatlar = (o, h, l, c)
    if any(int(np.isnan(dizi).sum()) for dizi in fiyatlar + (v,)):
        sorunlar.append("nan_deger")
    sonlu = fiyatlar + (v,)
    if any(int(np.isinf(dizi).sum()) for dizi in sonlu):
        sorunlar.append("sonsuza_deger")
    if sorunlar:
        # NaN/Inf ile geometri karşılaştırması güvenilir değil; önce bunlar raporlanır.
        return sorted(sorunlar)
    if int((h < l).sum()):
        sorunlar.append("high_lt_low")
    if int((h < np.maximum(o, c)).sum()):
        sorunlar.append("high_tutarsiz")
    if int((l > np.minimum(o, c)).sum()):
        sorunlar.append("low_tutarsiz")
    if any(int((dizi <= 0).sum()) for dizi in fiyatlar):
        sorunlar.append("gecersiz_fiyat")
    if int((v < 0).sum()):
        sorunlar.append("negatif_hacim")
    return sorted(sorunlar)


def _ohlcv_kayit_sorunlari(candle: dict) -> List[str]:
    """Validate one persisted/provider candle with the same OHLCV contract."""
    if not isinstance(candle, dict):
        return ["bozuk_kayit"]
    if "timestamp" not in candle:
        return ["gecersiz_timestamp"]
    raw_timestamp = candle.get("timestamp")
    if not isinstance(raw_timestamp, (str, datetime, np.datetime64, pd.Timestamp)):
        return ["gecersiz_timestamp"]
    try:
        if pd.isna(pd.Timestamp(raw_timestamp)):
            return ["gecersiz_timestamp"]
        values = [float(candle[key]) for key in ("open", "high", "low", "close", "volume")]
    except (KeyError, TypeError, ValueError, OverflowError):
        return ["eksik_veya_sayisal_olmayan_ohlcv"]
    if not all(math.isfinite(value) for value in values):
        return ["sonlu_olmayan_ohlcv"]
    o, h, l, c, v = values
    sorunlar = []
    if h < l:
        sorunlar.append("high_lt_low")
    if h < max(o, c):
        sorunlar.append("high_tutarsiz")
    if l > min(o, c):
        sorunlar.append("low_tutarsiz")
    if min(o, h, l, c) <= 0:
        sorunlar.append("gecersiz_fiyat")
    if v < 0:
        sorunlar.append("negatif_hacim")
    return sorunlar


def _karisik_timestamp_zaman_dilimi(bars: List[dict]) -> bool:
    """Naive and timezone-aware labels cannot be safely sorted/merged together."""
    aware = set()
    for candle in bars:
        try:
            aware.add(pd.Timestamp(candle["timestamp"]).tzinfo is not None)
        except (KeyError, TypeError, ValueError, OverflowError):
            return True
    return len(aware) > 1


def _temiz_1h_cache_kayitlari(raw):
    """Parse and filter untrusted persisted 1H JSON/pickle/Supabase records."""
    if not isinstance(raw, (list, tuple, deque)):
        return [], 1
    valid, skipped = [], 0
    for value in raw:
        if not isinstance(value, dict):
            skipped += 1
            continue
        timestamp = value.get("timestamp")
        if not isinstance(timestamp, (str, datetime, np.datetime64, pd.Timestamp)):
            skipped += 1
            continue
        try:
            timestamp = pd.Timestamp(timestamp)
            if pd.isna(timestamp):
                raise ValueError("invalid timestamp")
            if timestamp.tzinfo is not None:
                timestamp = timestamp.tz_convert(ISTANBUL_TZ)
            candle = {
                "timestamp": timestamp,
                "open": float(value["open"]),
                "high": float(value["high"]),
                "low": float(value["low"]),
                "close": float(value["close"]),
                "volume": float(value["volume"]),
            }
        except (KeyError, TypeError, ValueError, OverflowError):
            skipped += 1
            continue
        if _ohlcv_kayit_sorunlari(candle):
            skipped += 1
            continue
        valid.append(candle)
    if _karisik_timestamp_zaman_dilimi(valid):
        return [], skipped + len(valid)
    try:
        valid.sort(key=lambda candle: candle["timestamp"])
    except (TypeError, ValueError):
        return [], skipped + len(valid)
    return valid, skipped


def _temiz_1d_cache_kayitlari(raw):
    """Parse daily cache rows, normalize labels to Istanbul, then validate OHLCV."""
    if not isinstance(raw, (list, tuple, deque)):
        return [], 1
    valid, skipped = [], 0
    for value in raw:
        if not isinstance(value, dict):
            skipped += 1
            continue
        raw_timestamp = value.get("timestamp")
        if not isinstance(raw_timestamp, (str, datetime, np.datetime64, pd.Timestamp)):
            skipped += 1
            continue
        try:
            timestamp = pd.Timestamp(raw_timestamp)
            if pd.isna(timestamp):
                raise ValueError("invalid timestamp")
            timestamp = (
                ISTANBUL_TZ.localize(timestamp.to_pydatetime())
                if timestamp.tzinfo is None else timestamp.tz_convert(ISTANBUL_TZ)
            )
            candle = {
                "timestamp": timestamp,
                "open": float(value["open"]),
                "high": float(value["high"]),
                "low": float(value["low"]),
                "close": float(value["close"]),
                "volume": float(value["volume"]),
            }
        except (KeyError, TypeError, ValueError, OverflowError):
            skipped += 1
            continue
        if _ohlcv_kayit_sorunlari(candle):
            skipped += 1
            continue
        valid.append(candle)
    valid.sort(key=lambda candle: candle["timestamp"])
    return valid, skipped


def _cache_barlari_birlestir(remote_bars, local_bars, maxlen, stock, timeframe):
    """Merge valid cache copies, letting the copy with the later tail win revisions.

    Supabase is the tie-breaker when both copies end at the same candle. The
    local copy wins overlapping timestamps only when its latest timestamp is
    newer; this recovers locally persisted candles after a failed remote upsert
    without changing normal Supabase precedence for equally fresh copies.
    """
    remote_bars = list(remote_bars or [])
    local_bars = list(local_bars or [])
    if not remote_bars:
        return local_bars[-maxlen:]
    if not local_bars:
        return remote_bars[-maxlen:]
    if _karisik_timestamp_zaman_dilimi(remote_bars + local_bars):
        logger.warning(
            "%s %s Supabase/yerel cache zaman dilimleri uyuşmuyor; "
            "güvenli sıralama yapılamadığı için Supabase kopyası korundu",
            stock, timeframe,
        )
        return remote_bars[-maxlen:]

    try:
        local_latest = max(bar["timestamp"] for bar in local_bars)
        remote_latest = max(bar["timestamp"] for bar in remote_bars)
        local_is_newer = local_latest > remote_latest
    except (KeyError, TypeError, ValueError, OverflowError):
        logger.warning(
            "%s %s Supabase/yerel cache zamanları karşılaştırılamadı; "
            "Supabase kopyası korundu",
            stock, timeframe,
        )
        return remote_bars[-maxlen:]

    preferred, secondary = (
        (local_bars, remote_bars) if local_is_newer else (remote_bars, local_bars)
    )
    by_timestamp = {bar["timestamp"]: dict(bar) for bar in preferred}
    for bar in secondary:
        by_timestamp.setdefault(bar["timestamp"], dict(bar))
    try:
        merged = sorted(by_timestamp.values(), key=lambda bar: bar["timestamp"])
    except (KeyError, TypeError, ValueError):
        logger.warning(
            "%s %s Supabase/yerel cache birleştirilemedi; Supabase kopyası korundu",
            stock, timeframe,
        )
        return remote_bars[-maxlen:]
    return merged[-maxlen:]


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


class StockDequeManager:
    """
    Her hisse için 360 mumluk deque tutar
    Neden deque? maxlen=360 ile en eski otomatik silinir, rolling window
    Neden kalıcı? Bot restart olursa diskten yükle, 60 gün veriyi tekrar çekme
    """
    def __init__(self, maxlen: int = DEQUE_MAXLEN, data_dir: str = DATA_DIR,
                 persistent_store=None):
        self.maxlen = maxlen
        self.data_dir = data_dir
        self.persistent_store = persistent_store
        self.deques: Dict[str, deque] = {}
        # 1D (günlük) derin veri: 1H penceresinden BAĞIMSIZ (~500 bar).
        # Neden ayrı? 1H deque 360 bar = ~40 iş günü; resample 1D sadece ~40 bar
        # verir ve 1D formasyon penceresi (20-60 bar) marjinal kalır. 1H'yi
        # büyütmek Pine uyumunu bozabileceği için günlük veri ayrı ve derin tutulur.
        self.gunluk_deques: Dict[str, deque] = {}
        # Günlük endpoint, tamamlanmamış seans mumunu aynı gün döndürmeyebilir.
        # Başarısız/henüz güncellenmemiş veriyi her saat tekrar istememek için cooldown.
        self._gunluk_fetch_attempts: Dict[str, datetime] = {}
        self._gunluk_attempt_path = os.path.join(self.data_dir, "gunluk_fetch_attempts.json")
        # Son tespit edilen veri sorunları (split / bar boşluğu) - main.py okur
        self.sureklilik_sorunlari: Dict[str, List[Dict]] = {}
        # --- yazma amplifikasyonu koruması (Batch 6 / B5) ---
        # Supabase'e aynı içerik ikinci kez gönderilmesin: son gönderilen verinin
        # parmak izi (len, son bar zamanı, son kapanış). Disk yazımı her zaman
        # yapılır (yerel kurtarma), uzak yazım yalnız içerik değiştiğinde.
        self._uzak_ozet: Dict[str, tuple] = {}
        self._gunluk_uzak_ozet: Dict[str, tuple] = {}
        self.uzak_yazma_atlanan = 0   # telemetri: kaç UPSERT gereksizdi
        self.uzak_yazma_yapilan = 0   # telemetri: kaç UPSERT gönderildi
        
        # Data dir oluştur ve yerel günlük fetch cooldown'unu restore et.
        os.makedirs(data_dir, exist_ok=True)
        self._gunluk_fetch_attempts_yukle()

        logger.info(f"Deque manager başlatıldı - maxlen={maxlen}, dir={data_dir}")

    def _gunluk_fetch_attempts_yukle(self) -> None:
        if not os.path.exists(self._gunluk_attempt_path):
            return
        try:
            import json
            from dateutil import parser as date_parser
            with open(self._gunluk_attempt_path, "r", encoding="utf-8") as stream:
                payload = json.load(stream)
            if not isinstance(payload, dict):
                raise ValueError("beklenen sözlük biçimi değil")
            for stock, raw_time in payload.items():
                if not isinstance(stock, str) or not isinstance(raw_time, str):
                    continue
                try:
                    parsed = date_parser.isoparse(raw_time)
                    self._gunluk_fetch_attempts[stock] = (
                        ISTANBUL_TZ.localize(parsed) if parsed.tzinfo is None
                        else parsed.astimezone(ISTANBUL_TZ)
                    )
                except (TypeError, ValueError, OverflowError):
                    logger.warning("%s yerel günlük fetch zamanı bozuk; atlandı", stock)
        except (OSError, ValueError, UnicodeError) as exc:
            logger.warning("Yerel günlük fetch deneme kaydı okunamadı: %s", exc)

    def _gunluk_fetch_attempts_kaydet(self) -> bool:
        from datetime import timezone
        payload = {
            stock: (
                value.astimezone(timezone.utc).isoformat()
                if value.tzinfo is not None else value.isoformat()
            )
            for stock, value in self._gunluk_fetch_attempts.items()
        }
        try:
            _atomic_json_write(self._gunluk_attempt_path, payload)
            return True
        except Exception as exc:
            logger.error("Günlük fetch deneme zamanı yerel diske yazılamadı: %s", exc)
            return False

    def hydrate_from_supabase(self, stocks, rows) -> None:
        """Remote/local cache'i birleştir; en yeni mum yerel kopyayı da korur."""
        if not isinstance(rows, dict):
            return
        from dateutil import parser as date_parser

        for stock in stocks:
            hourly = rows.get(f"cache:1h:{stock}")
            if isinstance(hourly, list) and hourly:
                remote_bars, skipped = _temiz_1h_cache_kayitlari(hourly)
                if skipped:
                    logger.warning(
                        "%s 1H Supabase cache: %d bozuk/geçersiz kayıt atlandı",
                        stock, skipped,
                    )
                if remote_bars:
                    local_deque = self.deques.get(stock)
                    if not local_deque:
                        local_deque = self.load_from_disk(stock)
                    local_bars = list(local_deque) if local_deque else []
                    bars = _cache_barlari_birlestir(
                        remote_bars, local_bars, self.maxlen, stock, "1H"
                    )
                    self.deques[stock] = deque(bars, maxlen=self.maxlen)

            daily = rows.get(f"cache:1d:{stock}")
            if isinstance(daily, list) and daily:
                remote_bars, skipped = _temiz_1d_cache_kayitlari(daily)
                if skipped:
                    logger.warning(
                        "%s 1D Supabase cache: %d bozuk/geçersiz kayıt atlandı",
                        stock, skipped,
                    )
                if remote_bars:
                    local_deque = self.gunluk_deques.get(stock)
                    if local_deque is None:
                        local_deque = self.get_gunluk_deque(stock)
                    bars = _cache_barlari_birlestir(
                        remote_bars, list(local_deque), GUNLUK_DEQUE_MAXLEN,
                        stock, "1D",
                    )
                    self.gunluk_deques[stock] = deque(
                        bars, maxlen=GUNLUK_DEQUE_MAXLEN
                    )

        attempts = rows.get("state:daily_fetch_attempts")
        remote_attempt_newer = False
        if isinstance(attempts, dict):
            for stock, iso_time in attempts.items():
                if not isinstance(stock, str) or not isinstance(iso_time, str):
                    continue
                try:
                    parsed = date_parser.isoparse(iso_time)
                    if parsed.tzinfo is None:
                        parsed = ISTANBUL_TZ.localize(parsed)
                    # Preserve an aware remote offset (the Supabase payload is UTC
                    # by convention); comparisons remain instant-aware, and disk
                    # persistence serializes UTC separately.
                    local = self._gunluk_fetch_attempts.get(stock)
                    if local is None or parsed > local:
                        self._gunluk_fetch_attempts[stock] = parsed
                        remote_attempt_newer = True
                except (TypeError, ValueError, OverflowError):
                    logger.warning("%s Supabase günlük fetch zamanı bozuk; atlandı", stock)
        if remote_attempt_newer:
            self._gunluk_fetch_attempts_kaydet()

        logger.info(
            f"Supabase cache yüklendi: 1H={len(self.deques)}, 1D={len(self.gunluk_deques)}, "
            f"günlük fetch denemesi={len(self._gunluk_fetch_attempts)}"
        )

    def get_deque(self, stock: str) -> deque:
        """Hisse için deque al, yoksa oluştur"""
        if stock not in self.deques:
            # Diskten yüklemeyi dene
            loaded = self.load_from_disk(stock)
            if loaded is not None:
                self.deques[stock] = loaded
                logger.info(f"{stock} deque diskten yüklendi - {len(loaded)} mum")
            else:
                self.deques[stock] = deque(maxlen=self.maxlen)
                logger.info(f"{stock} için yeni deque oluşturuldu")
        return self.deques[stock]
    
    def append_candle(self, stock: str, candle: dict) -> bool:
        """Validate and append one canonicalized candle without bypassing the OHLCV boundary."""
        sorunlar = _ohlcv_kayit_sorunlari(candle)
        if sorunlar:
            logger.error("%s tekil mum reddedildi (%s)", stock, ", ".join(sorunlar))
            return False
        try:
            timestamp = pd.Timestamp(candle["timestamp"])
            if pd.isna(timestamp):
                raise ValueError("NaT timestamp")
            if timestamp.tzinfo is not None:
                timestamp = timestamp.tz_convert(ISTANBUL_TZ)
            normalized = dict(candle)
            normalized["timestamp"] = timestamp
            for field in ("open", "high", "low", "close", "volume"):
                normalized[field] = float(candle[field])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            logger.error("%s tekil mum reddedildi (kanonikleştirme: %s)", stock, type(exc).__name__)
            return False
        dq = self.get_deque(stock)
        if _karisik_timestamp_zaman_dilimi(list(dq) + [normalized]):
            logger.error("%s tekil mum reddedildi (cache zaman dilimi karışık)", stock)
            return False
        dq.append(normalized)
        return True
    
    def append_dataframe(self, stock: str, df: pd.DataFrame) -> bool:
        """DataFrame'den toplu ekle — timestamp bazlı TEKİLLEŞTİRİLMİŞ (idempotent).
        Aynı zamana sahip mum varsa yeni değerler yazılır (taze kazınır),
        pencere taşarsa en eski düşer (maxlen FIFO). Böylece aynı 60d penceresi
        tekrar çekilip eklense bile deque bozulmaz.
        DÖNÜŞ: True = birleştirme yapıldı; False = frame geçersiz OHLCV içeriyor
        (deque DOKUNULMADI; eski veri korundu). Geçerlilik sözleşmesi:
        ohlcv_girdi_sorunlari()."""
        girdi_sorunlari = ohlcv_girdi_sorunlari(df)
        if girdi_sorunlari:
            logger.error(
                f"{stock}: gelen OHLCV frame geçersiz ({', '.join(girdi_sorunlari)}); "
                "deque güncellenmedi, mevcut veri korundu"
            )
            self.sureklilik_sorunlari[stock] = [{
                "tip": "gecersiz_girdi",
                "mesaj": f"girdi doğrulaması: {', '.join(girdi_sorunlari)}",
            }]
            return False
        dq = self.get_deque(stock)
        birlesik: Dict[datetime, dict] = {c['timestamp']: c for c in dq}
        yeni = 0
        guncellenen = 0
        for idx, row in df.iterrows():
            ts = idx if isinstance(idx, datetime) else pd.to_datetime(idx)
            candle = {
                'timestamp': ts,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row.get('volume', 0))
            }
            if ts in birlesik:
                guncellenen += 1
            else:
                yeni += 1
            birlesik[ts] = candle
        if _karisik_timestamp_zaman_dilimi(list(birlesik.values())):
            logger.error(
                "%s: birleştirilen cache'te naive/aware timestamp karışımı; deque korunuyor",
                stock,
            )
            self.sureklilik_sorunlari[stock] = [{
                "tip": "gecersiz_girdi",
                "mesaj": "timestamp zaman dilimi karışık",
            }]
            return False
        tumu = sorted(birlesik.values(), key=lambda c: c['timestamp'])
        dq.clear()
        for c in tumu[-self.maxlen:]:
            dq.append(c)
        logger.info(f"{stock}: {yeni} yeni / {guncellenen} güncellenen mum (geldi {len(df)}, toplam {len(dq)})")
        # --- SPLIT / SÜREKLİLİK KONTROLÜ (FAZ 2) ---
        # Ham (auto_adjust=False) seride split/bedelsiz ani zıplama üretir -> pivot,
        # sınır ve kırılım sinyali sahte olur. Tespit edilirse deque sıfırlanır:
        # sahte sinyal üretmek yerine bot 360 yeni bar biriktirip temiz başlar.
        # NOT: split tespitinde deque SIFIRLANMAZ. Neden? Eşik normal gürültünün
        # (%9.97) çok üstünde olsa da gelecekte %12lik haber şoku yanlış pozitif
        # yaparsa hisse 40 gün kör kalır. Bunun yerine sorun kaydedilir ve main.py
        # o hisseyi o taramada ANALİZ ETMEZ (sahte sinyal üretmez), kullanıcı
        # logdan görüp müdahale eder (veri yenileme / düzeltme).
        sorunlar = sureklilik_sorunlari_bul(dq)
        if sorunlar:
            self.sureklilik_sorunlari[stock] = sorunlar
            for s_ in sorunlar:
                logger.warning(f"{stock}: {s_['mesaj']}")
            if any(s_['tip'] == 'split' for s_ in sorunlar):
                logger.error(
                    f"{stock}: SPLIT/BEDELSİZ tespit edildi - bu hisse bu tur ANALİZ EDİLMEYECEK "
                    f"(ham seride sahte kırılım sinyali riski). Veriyi yenilemek/düzeltmek için "
                    f"elle müdahale gerekir; düzeltilene kadar sessiz kalır."
                )
        else:
            self.sureklilik_sorunlari.pop(stock, None)
        return True
    
    def to_dataframe(self, stock: str) -> Optional[pd.DataFrame]:
        """Deque'yi DataFrame'e çevir - pattern tespiti için"""
        dq = self.get_deque(stock)  # Diskten yüklemeyi de dene
        if len(dq) == 0:
            return None
        data = list(dq)
        
        # Timestamp'e göre sırala
        data_sorted = sorted(data, key=lambda x: x['timestamp'])
        
        df = pd.DataFrame(data_sorted)
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)

        # Nihai sigorta: karışık tz sınıfları (ör. tarihsel Supabase hydrate
        # verisi dateutil.tzoffset; taze Yahoo verisi pytz.Timestamp) set_index'te
        # object-Index üretir; resample ve tamamlanmis_mumlar bu dizinle çöker
        # (canlı 0/48 olayı). Tarihsel zehirli veriyi zararsız kılmak için dizin
        # tek kova altında toplanır: UTC üzerinden okunup İstanbul'a basılır.
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, utc=True).tz_convert(ISTANBUL_TZ)

        # Sütun sırası
        df = df[['open', 'high', 'low', 'close', 'volume']]
        
        return df
    
    def save_to_disk(self, stock: str) -> bool:
        """Save the JSON restart cache and report whether all configured stores succeeded."""
        if stock not in self.deques:
            return False

        pkl_path = os.path.join(self.data_dir, f"{stock}.pkl")
        json_path = os.path.join(self.data_dir, f"{stock}.json")

        try:
            data_list = list(self.deques[stock])

            # JSON is the default/safe restart format; build it before the optional
            # legacy pickle so the canonical cache survives a pickle write failure.
            json_data = []
            for candle in data_list:
                json_candle = candle.copy()
                ts = json_candle.get("timestamp")
                if ts is not None:
                    json_candle["timestamp"] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
                json_data.append(json_candle)

            _atomic_json_write(json_path, json_data, indent=2)
            # Pickle yalnız açıkça istendiğinde (varsayılan: kapalı) — pickle
            # yüklemek kod çalıştırabilir, bu yüzden repoda tutulmaz.
            if os.environ.get("PICKLE_CACHE", "").strip().lower() in ("1", "true", "yes", "on"):
                try:
                    _atomic_pickle_write(pkl_path, data_list)
                except Exception as exc:
                    # JSON is already durable and remains the default load path.
                    logger.warning("%s optional pickle cache yazılamadı (%s)", stock, type(exc).__name__)

            remote_saved = True
            remote_error = None
            if self.persistent_store is not None:
                # İçerik değişmediyse UPSERT atlanır (tarama başına ~48 gereksiz
                # istek + ~2 MB gidiyordu). Kapanış/timestamp değişince yazılır.
                ozet = self._veri_ozeti(data_list)
                remote_error = None
                if self._uzak_ozet.get(stock) != ozet:
                    try:
                        remote_saved = bool(
                            self.persistent_store.upsert(f"cache:1h:{stock}", json_data)
                        )
                    except Exception as exc:
                        remote_saved = False
                        remote_error = type(exc).__name__
                    if remote_saved:
                        self._uzak_ozet[stock] = ozet
                        self.uzak_yazma_yapilan += 1
                    else:
                        logger.warning(
                            "%s 1H Supabase cache yazma başarısız%s; yerel JSON kopyası var",
                            stock,
                            f" ({remote_error})" if remote_error else "",
                        )
                else:
                    self.uzak_yazma_atlanan += 1


            logger.debug(
                "%s deque diske kaydedildi - %s + %s (%d mum)",
                stock, pkl_path, json_path, len(data_list),
            )
            return remote_saved
        except Exception as exc:
            logger.error("%s yerel cache diske kaydedilemedi (%s)", stock, type(exc).__name__)
            return False
    
    def load_from_disk(self, stock: str) -> Optional[deque]:
        """Load validated JSON first; legacy pickle is opt-in because unpickling executes code.

        Okuma yolu `_okuma_yolu` üzerinden gider: DATA_DIR'de yoksa repodaki seed
        (SEED_DATA_DIR) yalnız OKUMA için kullanılır, yazımlar hep DATA_DIR'e gider.
        """
        json_path = self._okuma_yolu(f"{stock}.json")
        pkl_path = self._okuma_yolu(f"{stock}.pkl")

        # JSON birincil (A8): pickle yalnızca açık opt-in ile okunan yedek biçimdir.
        if os.path.exists(json_path):
            try:
                import json
                with open(json_path, "r", encoding="utf-8") as stream:
                    raw = json.load(stream)
                bars, skipped = _temiz_1h_cache_kayitlari(raw)
                if skipped:
                    logger.warning(
                        "%s 1H JSON cache: %d bozuk/geçersiz kayıt atlandı",
                        stock, skipped,
                    )
                logger.debug("%s JSON cache'ten yüklendi: %d mum", stock, len(bars))
                return deque(bars[-self.maxlen:], maxlen=self.maxlen)
            except (OSError, UnicodeError, ValueError) as exc:
                logger.warning(
                    "%s JSON cache okunamadı (%s)", stock, type(exc).__name__
                )

        if not os.path.exists(pkl_path):
            return None
        if not ALLOW_TRUSTED_PICKLE_CACHE:
            logger.warning(
                "%s için JSON cache yok/geçersiz; legacy pickle yüklemesi kapalı "
                "(yalnızca güvenilir dosyalar için ALLOW_TRUSTED_PICKLE_CACHE=1)",
                stock,
            )
            return None

        # Opt-in only: pickle input must be fully trusted. Never use this path for
        # downloaded/imported cache files; a pickle can execute arbitrary code.
        try:
            with open(pkl_path, "rb") as stream:
                raw = pickle.load(stream)
            bars, skipped = _temiz_1h_cache_kayitlari(raw)
            if skipped:
                logger.warning(
                    "%s legacy pickle cache: %d bozuk/geçersiz kayıt atlandı",
                    stock, skipped,
                )
            logger.info("%s eski pickle dosyasından yüklendi: %d mum (JSON yok)", stock, len(bars))
            return deque(bars[-self.maxlen:], maxlen=self.maxlen)
        except Exception as exc:  # noqa: BLE001 - yalnızca açık trusted-cache opt-in
            logger.warning("%s güvenilir pickle cache okunamadı (%s)", stock, type(exc).__name__)
            return None

    def _gunluk_dosya(self, stock: str) -> str:
        return os.path.join(self.data_dir, f"{stock}_gunluk.json")

    def get_gunluk_deque(self, stock: str) -> deque:
        """1D (günlük) deque al, yoksa diskten yükle / oluştur."""
        if stock not in self.gunluk_deques:
            # Yazma yolu DATA_DIR; okuma gerekirse repo seed'ine düşer (C4).
            yol = self._okuma_yolu(f"{stock}_gunluk.json")
            dq = None
            if os.path.exists(yol):
                try:
                    import json
                    with open(yol, "r", encoding="utf-8") as stream:
                        raw = json.load(stream)
                    yuklenen, skipped = _temiz_1d_cache_kayitlari(raw)
                    if skipped:
                        logger.warning(
                            "%s günlük JSON cache: %d bozuk/geçersiz kayıt atlandı",
                            stock, skipped,
                        )
                    dq = deque(
                        yuklenen[-GUNLUK_DEQUE_MAXLEN:], maxlen=GUNLUK_DEQUE_MAXLEN
                    )
                    logger.info("%s günlük deque diskten yüklendi - %d bar", stock, len(dq))
                except Exception as exc:
                    logger.warning(
                        "%s günlük cache okunamadı (%s) - yeniden çekilecek",
                        stock, type(exc).__name__,
                    )
                    dq = None
            if dq is None:
                dq = deque(maxlen=GUNLUK_DEQUE_MAXLEN)
            self.gunluk_deques[stock] = dq
        return self.gunluk_deques[stock]

    def append_gunluk_dataframe(self, stock: str, df: pd.DataFrame) -> bool:
        """1H ile aynı OHLCV kapısı ve idempotent timestamp birleştirmesi."""
        sorunlar = ohlcv_girdi_sorunlari(df)
        if sorunlar:
            logger.error(
                "%s: gelen günlük OHLCV frame geçersiz (%s); günlük deque korunuyor",
                stock, ", ".join(sorunlar),
            )
            return False
        dq = self.get_gunluk_deque(stock)
        birlesik = {c["timestamp"]: c for c in dq}
        yeni = guncellenen = 0
        for idx, row in df.iterrows():
            ts = idx if isinstance(idx, datetime) else pd.to_datetime(idx)
            if ts.tzinfo is None:
                ts = ISTANBUL_TZ.localize(ts)
            else:
                ts = ts.tz_convert(ISTANBUL_TZ)
            candle = {"timestamp": ts, "open": float(row["open"]), "high": float(row["high"]),
                      "low": float(row["low"]), "close": float(row["close"]),
                      "volume": float(row.get("volume", 0))}
            if ts in birlesik:
                guncellenen += 1
            else:
                yeni += 1
            birlesik[ts] = candle
        tumu = sorted(birlesik.values(), key=lambda c: c["timestamp"])
        dq.clear()
        for c in tumu[-GUNLUK_DEQUE_MAXLEN:]:
            dq.append(c)
        logger.info(f"{stock}: {yeni} yeni / {guncellenen} güncellenen GÜNLÜK mum "
                    f"(toplam {len(dq)} bar)")
        return True

    def to_gunluk_dataframe(self, stock: str) -> Optional[pd.DataFrame]:
        dq = self.get_gunluk_deque(stock)
        if len(dq) == 0:
            return None
        df = pd.DataFrame(list(dq))
        df.set_index("timestamp", inplace=True)
        # to_dataframe ile aynı tz sigortası (tarihsel karma-tz veri güvenliği)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, utc=True).tz_convert(ISTANBUL_TZ)
        return df

    def gunluk_veri_eksik_mi(self, stock: str, now: Optional[datetime] = None) -> bool:
        """Günlük veri eksik/eskiyse ve cooldown dolduysa True -> fetch gerekir.

        Intraday Yahoo yanıtında bugünün günlük mumu henüz olmayabilir. Aynı 50
        sembolü her saat 2 yıllık günlük geçmişle tekrar istememek için başarısız
        denemeleri 6 saat soğutur; kapanıştan sonra bir kez daha tazeler.
        """
        if now is None:
            now = datetime.now(ISTANBUL_TZ)
        elif now.tzinfo is None:
            now = ISTANBUL_TZ.localize(now)
        else:
            now = now.astimezone(ISTANBUL_TZ)

        df = self.to_gunluk_dataframe(stock)
        son_gun = None
        if df is not None and len(df) >= 30:
            son = df.index[-1]
            son = son.tz_convert(ISTANBUL_TZ) if son.tzinfo else ISTANBUL_TZ.localize(son)
            son_gun = son.date()

        last_attempt = self._gunluk_fetch_attempts.get(stock)
        if last_attempt is not None:
            if last_attempt.tzinfo is None:
                last_attempt = ISTANBUL_TZ.localize(last_attempt)
            else:
                last_attempt = last_attempt.astimezone(ISTANBUL_TZ)

        kapanis = seans_kapanis_saati(now)
        kapanis_ani = now.replace(hour=kapanis.hour, minute=kapanis.minute,
                                  second=0, microsecond=0)
        kapanis_sonrasi = (
            now.weekday() < 5 and bist_tatil_adi(now) is None and now >= kapanis_ani
        )
        bugun_kapanis_sonrasi_denendi = (
            last_attempt is not None
            and last_attempt.date() == now.date()
            and last_attempt >= kapanis_ani
        )

        # Bugün alınan günlük mum seans içi indiyse kapanıştan sonra bir kez
        # tazele; diskte zaten bugüne ait veri varsa (fetch zamanı bilinmiyorsa)
        # tekrar çekmeden önce onu geçerli kabul et.
        kapanis_ici_deneme_var = (
            last_attempt is not None
            and last_attempt.date() == now.date()
            and last_attempt < kapanis_ani
        )
        if (kapanis_sonrasi and not bugun_kapanis_sonrasi_denendi
                and (son_gun is None or son_gun < now.date() or kapanis_ici_deneme_var)):
            return True
        if son_gun is not None and son_gun >= now.date():
            return False

        if last_attempt is not None and now - last_attempt < timedelta(hours=6):
            return False
        return True

    def gunluk_fetch_denemesi_kaydet(self, stock: str, now: Optional[datetime] = None,
                                      *, persist: bool = True) -> None:
        """Başarılı veya başarısız günlük fetch denemesinin zamanını kaydet.

        ``persist=False`` yalnızca bu süreçte tekrar fetch'i yavaşlatır. Yeni
        günlük cache kalıcı yazılamadıysa, kalıcı cooldown yazmak yeniden
        başlatma sonrası eksik verinin tekrar alınmasını yanlışlıkla engeller.
        """
        if now is None:
            now = datetime.now(ISTANBUL_TZ)
        elif now.tzinfo is None:
            now = ISTANBUL_TZ.localize(now)
        else:
            now = now.astimezone(ISTANBUL_TZ)
        self._gunluk_fetch_attempts[stock] = now
        if not persist:
            return
        self._gunluk_fetch_attempts_kaydet()
        if self.persistent_store is not None:
            from datetime import timezone
            attempts = {
                key: value.astimezone(timezone.utc).isoformat()
                if value.tzinfo is not None else value.isoformat()
                for key, value in self._gunluk_fetch_attempts.items()
            }
            try:
                remote_saved = self.persistent_store.upsert("state:daily_fetch_attempts", attempts)
            except Exception as exc:
                # The atomic local attempt snapshot is already the recovery source;
                # a remote adapter failure must not turn a usable daily cache into
                # a failed symbol scan. Avoid exception text: adapters may embed URLs.
                logger.warning(
                    "Günlük fetch deneme durumu uzak saklayıcıya yazılamadı (%s)",
                    type(exc).__name__,
                )
            else:
                if not remote_saved:
                    logger.warning("Günlük fetch deneme durumu uzak saklayıcı tarafından reddedildi")

    def save_gunluk_to_disk(self, stock: str) -> bool:
        """Save local JSON and report whether configured durable stores accepted it."""
        dq = self.get_gunluk_deque(stock)
        os.makedirs(self.data_dir, exist_ok=True)
        payload = [{"timestamp": c["timestamp"].isoformat(), "open": c["open"],
                    "high": c["high"], "low": c["low"], "close": c["close"],
                    "volume": c["volume"]} for c in dq]
        _atomic_json_write(self._gunluk_dosya(stock), payload)
        if self.persistent_store is not None:
            # Günlük seri günde bir değişir; tarama başına 48 kez yazmak ~2,4 MB
            # gereksiz trafikti. İçerik değişmediyse gönderilmez.
            ozet = self._veri_ozeti(payload)
            if self._gunluk_uzak_ozet.get(stock) == ozet:
                self.uzak_yazma_atlanan += 1
            else:
                try:
                    remote_saved = bool(self.persistent_store.upsert(f"cache:1d:{stock}", payload))
                except Exception as exc:
                    logger.warning("%s günlük Supabase cache yazılamadı (%s)", stock, type(exc).__name__)
                    return False
                if not remote_saved:
                    logger.warning("%s günlük Supabase cache yazma başarısız; yerel kopya var", stock)
                    return False
                self._gunluk_uzak_ozet[stock] = ozet
                self.uzak_yazma_yapilan += 1
        return True

    def son_bar_yasi_dk(self, stock: str, now: Optional[datetime] = None) -> Optional[float]:
        """Bu hissenin cache'indeki en yeni 1H mumun yaşı (dakika). Veri yoksa None.
        Veri-yok modu (tatil / Yahoo arızası) tespiti için kullanılır."""
        df = self.to_dataframe(stock)
        if df is None or len(df) == 0:
            return None
        if now is None:
            now = datetime.now(ISTANBUL_TZ)
        if now.tzinfo is None:
            now = ISTANBUL_TZ.localize(now)
        son = _istanbul_zaman(df.index[-1])
        return (now - son).total_seconds() / 60.0

    # --- C4: veri dizini (repo dışı) + repo seed yedeği ---------------------
    def _okuma_yolu(self, dosya_adi: str) -> str:
        """Okuma için yol: DATA_DIR'de yoksa repodaki örnek veriye (SEED_DATA_DIR) bak.

        Yalnız OKUMA içindir; yazımlar her zaman DATA_DIR'e gider, böylece canlı
        sunucuda `git pull` repo içindeki veriyi ezmez/çakışmaz.
        """
        yol = os.path.join(self.data_dir, dosya_adi)
        if os.path.exists(yol):
            return yol
        yedek = os.path.join(SEED_DATA_DIR, dosya_adi)
        farkli = os.path.abspath(yedek) != os.path.abspath(yol)
        if farkli and os.path.exists(yedek):
            logger.debug(f"{dosya_adi}: veri dizininde yok, repo seed yedeği kullanılıyor")
            return yedek
        return yol

    @staticmethod
    def _veri_ozeti(data_list) -> tuple:
        """Uzak yazım gerekip gerekmediğini anlamak için ucuz parmak izi."""
        if not data_list:
            return (0, None, None)
        son = data_list[-1] if isinstance(data_list[-1], dict) else {}
        return (len(data_list), str(son.get("timestamp")), son.get("close"))

    def uzak_yazma_durumu(self) -> Dict:
        """B5 telemetrisi: kaç uzak yazım yapıldı, kaçı gereksizdi."""
        return {
            "yapilan": self.uzak_yazma_yapilan,
            "atlanan": self.uzak_yazma_atlanan,
            "izlenen_1h": len(self._uzak_ozet),
            "izlenen_1d": len(self._gunluk_uzak_ozet),
        }

    def save_all(self) -> bool:
        """Save all caches, isolating per-series errors and reporting durable failures."""
        hourly_failed = 0
        daily_failed = 0
        for stock in list(self.deques):
            try:
                hourly_failed += not self.save_to_disk(stock)
            except Exception as exc:
                hourly_failed += 1
                logger.error("%s 1H cache kayıt hatası (%s)", stock, type(exc).__name__)
        for stock in list(self.gunluk_deques):
            try:
                daily_failed += not self.save_gunluk_to_disk(stock)
            except Exception as exc:
                daily_failed += 1
                logger.error("%s 1D cache kayıt hatası (%s)", stock, type(exc).__name__)
        failed = hourly_failed + daily_failed
        if failed:
            logger.warning(
                "Cache kayıtları tamamlandı ancak %d/%d seri için tüm kalıcı "
                "hedefler doğrulanmadı (1H=%d, 1D=%d)",
                failed, len(self.deques) + len(self.gunluk_deques),
                hourly_failed, daily_failed,
            )
            return False
        logger.info(
            "Tüm deque'ler kalıcı depolara kaydedildi - %d hisse (+%d günlük)",
            len(self.deques), len(self.gunluk_deques),
        )
        return True

# === VERİ SÜREKLİLİK / SPLIT KONTROLÜ ===

def yuvarlak_orana_yakin_mi(yuzde: float, tolerans: float = 1.0) -> Optional[float]:
    """
    Zıplama yüzdesi bir SPLIT oranına yakın mı? (2:1 -> %50, 3:1 -> %33.3, 5:1 -> %20 ...)

    Neden? Haber şoku da tek barda %15 yapabilir ama split oranları yuvarlaktır.
    Yuvarlak oran = split/bedelsiz (kalıcı, tüm geçmişi etkiler);
    yuvarlak olmayan = tek barlık fiyat şoku (geçici).
    Oranı döner (örn. 2.0), değilse None.
    """
    for oran in (2, 3, 4, 5, 6, 7, 8, 9, 10, 20):
        beklenen = (1 - 1 / oran) * 100  # 2:1 -> %50
        if abs(yuzde - beklenen) <= tolerans:
            return float(oran)
    return None


def sureklilik_sorunlari_bul(dq) -> List[Dict]:
    """
    Deque'daki mumlarda veri bütünlüğü sorunu ara.

    Üç kontrol (config'teki ölçülmüş eşiklerle):
      1) split/bedelsiz: SEANS İÇİ ve NORMAL aralıklı (≈1 saat) iki mumda
         |open[i+1]-close[i]|/close[i] > %10 VE oran yuvarlak (2:1, 3:1, 5:1...).
      2) eksik veri: aynı seans içinde 1.5 saatten fazla boşluk (1 mum atlaması).
      3) fiyat şoku: %10 üstü ama yuvarlak olmayan zıplama (haber/tek olay).

    Neden gerekli? auto_adjust=False (Pine uyumu için) HAM seri verir; split olan
    hissede fiyat aniden yarıya iner ve motor bunu "kırılım" sanıp sahte alarm
    üretir. Gece/hafta sonu boşlukları (15-60 saat) DOĞALDIR, onlar sayılmaz.
    """
    sorunlar: List[Dict] = []
    if dq is None or len(dq) < 3:
        return sorunlar

    onceki = None
    for c in dq:
        ts = _istanbul_zaman(c['timestamp'])
        if onceki is not None:
            onceki_ts, onceki_kapanis, onceki_gun = onceki
            bosluk_saat = (ts - onceki_ts).total_seconds() / 3600.0
            if ts.date() == onceki_gun:  # sadece aynı seans içi
                if bosluk_saat > BAR_BOSLUK_ESIK_SAAT:
                    sorunlar.append({
                        'tip': 'bosluk',
                        'mesaj': (f"SEANS İÇİ EKSİK VERİ: {onceki_ts.strftime('%d %b %H:%M')} ile "
                                  f"{ts.strftime('%H:%M')} arasında {bosluk_saat:.1f} saat boşluk"),
                        'zamandar': ts, 'yuzde': round(bosluk_saat, 2),
                    })
                elif onceki_kapanis > 0:
                    # Zıplama kontrolü SADECE normal aralıkta (boşlukta fiyat
                    # normalde hareket eder, onu split sanmak yanlış pozitiftir)
                    ziplama = abs(c['open'] - onceki_kapanis) / onceki_kapanis * 100.0
                    if ziplama > SPLIT_SUREKLILIK_ESIK_PCT:
                        oran = yuvarlak_orana_yakin_mi(ziplama)
                        if oran:
                            sorunlar.append({
                                'tip': 'split',
                                'mesaj': (f"FİYAT SÜREKLİLİĞİ İHLALİ (SPLIT/BEDELSİZ ~{oran:.0f}:1): "
                                          f"{ts.strftime('%d %b %H:%M')} mumu önceki kapanışa göre "
                                          f"%{ziplama:.1f} zıplamış ({onceki_kapanis:.2f} -> "
                                          f"{c['open']:.2f})"),
                                'zamandar': ts, 'yuzde': round(ziplama, 2), 'oran': oran,
                            })
                        else:
                            sorunlar.append({
                                'tip': 'sok',
                                'mesaj': (f"FİYAT ŞOKU (split değil): {ts.strftime('%d %b %H:%M')} mumu "
                                          f"%{ziplama:.1f} zıplamış ({onceki_kapanis:.2f} -> "
                                          f"{c['open']:.2f}) - tek barlık hareket, oran yuvarlak değil"),
                                'zamandar': ts, 'yuzde': round(ziplama, 2),
                            })
        onceki = (ts, c['close'], ts.date())
    return sorunlar


# === RESAMPLING ===

# 2H/4H kova çapası (FAZ düzeltmesi, 2026-10-23): BIST seansinin ilk 1H
# etiketi. Çapa SABİTTİR ve İstanbul saatinde uygulanır; pencerenin ilk
# barından TÜRETİLMEZ. Türetilirse kayan 360 barlık pencerenin başı her
# saat döndükçe faz döner ve bütün 2H/4H tarihi yeniden yazılır
# (ölçüm: docs/arastirma/KOVA_FAZI_OLCUMU_2026-10-23.md — 4H senaryolarin
# yalnız %33'ü doğru fazdaydı, motorun nihai durumu %33 değişiyordu).
_SEANS_CAPASI = "9h30min"


def _bist_seans_serisi(idx_ist: pd.DatetimeIndex) -> bool:
    """Tüm barlar BIST seans saatlerinde mi? (İstanbul duvar saati 09-18)

    Kesintisiz semboller (BRENT/USDTRY/ALTIN...) gece barı da taşır; onlarda
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
            logger.warning(f"{timeframe} resample sonrası boş - {len(df)} -> 0")
            return pd.DataFrame()
        
        logger.debug(f"Resample {len(df)} 1H -> {len(df_resampled)} {timeframe}")
        return df_resampled
        
    except Exception as e:
        logger.error(f"Resample hatası {timeframe}: {e}")
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
    sure = TF_BAR_SURELERI.get(str(tf).lower())
    if sure is None:
        logger.warning(f"Bilinmeyen timeframe '{tf}' - 1h süresi varsayıldı")
        sure = TF_BAR_SURELERI["1h"]
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

# === VERİ ÇEKME (MOCK + GERÇEK İSKELET) ===

def fetch_yfinance_1d(stock: str, period: str = GUNLUK_FETCH_PERIOD) -> Optional[pd.DataFrame]:
    """Günlük (1D) OHLCV çeker — DERİN geçmiş (varsayılan 2 yıl, ~500 bar).

    Neden ayrı fonksiyon? 1H deque 360 bar = ~40 iş günü tutar; resample ile 1D
    yapılırsa sadece ~40 bar olur ve 1D formasyon penceresi (20-60 bar) marjinal
    kalır. 1H penceresini büyütmek Pine uyumunu bozabileceği için 1D verisini
    AYRI ve DERİN çekiyoruz. auto_adjust=False: 1H ile aynı gerekçe (ham fiyat).
    """
    try:
        import io
        import contextlib
        import yfinance as yf
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            ham = yf.Ticker(yahoo_ticker_for_symbol(stock)).history(period=period, interval="1d", auto_adjust=False)
        if ham is None or len(ham) == 0:
            return None
        df = ham.copy()
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(ISTANBUL_TZ)
        else:
            df.index = df.index.tz_convert(ISTANBUL_TZ)
        df.columns = [c.lower() for c in df.columns]
        return df[["open", "high", "low", "close", "volume"]]
    except Exception as e:
        logger.debug(f"{stock} 1D fetch hatası: {e}")
        return None


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
    def result(df, retryable=False, reason=""):
        return (df, retryable, reason) if with_status else df

    try:
        import io
        import contextlib
        import yfinance as yf
        captured = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(captured):
            ham = yf.Ticker(yahoo_ticker_for_symbol(stock)).history(period=period, interval="1h", auto_adjust=False)
        if ham is None or ham.empty:
            reason = captured.getvalue().strip() or "Yahoo boş veri döndürdü"
            return result(None, yfinance_error_is_retryable(reason), reason)
        ham = ham.rename(columns=str.lower)
        gerekli = ["open", "high", "low", "close", "volume"]
        if not all(c in ham.columns for c in gerekli):
            return result(None, False, "Gerekli OHLCV sütunları eksik")
        ham = ham[gerekli]
        # Zaman dilimi: deque'daki mumlar Europe/Istanbul tz-aware. yfinance genelde
        # borsa saatini verir ama bazı durumlarda UTC/naive dönebilir - normalize et,
        # yoksa dedup bozulur (aynı mum iki kez eklenir) ve tamamlanmis_mumlar şaşar.
        try:
            if ham.index.tz is None:
                ham.index = ham.index.tz_localize("UTC").tz_convert(ISTANBUL_TZ)
            else:
                ham.index = ham.index.tz_convert(ISTANBUL_TZ)
        except Exception:
            try:
                ham.index = pd.to_datetime(ham.index).tz_localize(ISTANBUL_TZ)
            except Exception:
                pass
        return result(ham)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        return result(None, yfinance_error_is_retryable(exc), reason)


def fetch_last_bar(stock: str) -> Optional[pd.DataFrame]:
    """Sabah pre-load için son 5 günlük 1h veriyi hafifçe çeker (0-latency açılış)."""
    return fetch_yfinance_1h(stock, period="5d")


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

# === TEST ===

if __name__ == "__main__":
    # C7: sahte veri üreticisi kaldırıldı; demo yalnız çevrimdışı yardımcıları
    # ve deque turunu sınar (gerçek veri için fetch_yfinance_1h/1d).
    print("=== Data.py duman testi (çevrimdışı) ===")
    print(f"BIST açık mı? {is_bist_open()}")
    print(f"Sonraki açılışa: {time_until_next_open()/3600:.2f} saat")
    print(f"Sonraki mum kapanışına: {time_until_next_candle_close()/60:.1f} dk")
    
    # Deque test: only this invocation's temporary cache is cleaned.
    with tempfile.TemporaryDirectory(prefix="formation-bot-data-test-") as test_root:
        test_data_dir = os.path.join(test_root, "cache")
        manager = StockDequeManager(maxlen=10, data_dir=test_data_dir)
        df_mock = mock_fetch_60d_1h("THYAO", 20)
        print(f"\nMock THYAO: {len(df_mock)} bar")
        print(df_mock.tail(3))

        manager.append_dataframe("THYAO", df_mock)
        df_from_deque = manager.to_dataframe("THYAO")
        print(f"\nDeque'den DataFrame: {len(df_from_deque)} bar")

        # Resample test
        resampled = resample_all_timeframes(df_from_deque)
        for tf, df in resampled.items():
            print(f"{tf}: {len(df)} bar")

    print("\nTest bitti (test-owned geçici cache temizlendi)")
