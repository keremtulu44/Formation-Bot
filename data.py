# --- DATA LAYER ---
# BIST veri katmanı - deque, resampling, BIST saat kontrolü
# Türkçe açıklamalar: Her fonksiyon ne yapar, neden?

import pandas as pd
import numpy as np
from collections import deque
from datetime import datetime, timedelta, time as dt_time
import pytz
import time
import random
import logging
import os
import pickle
from typing import Dict, List, Optional, Tuple

from config import (
    ISTANBUL_TZ, BIST_OPEN, BIST_CLOSE, DEQUE_MAXLEN,
    RATE_LIMIT_MIN, RATE_LIMIT_MAX, DATA_DIR, ACTIVE_STOCKS,
    CANDLE_CLOSE_MINUTE, SCAN_DELAY_AFTER_CLOSE_MIN, TARAMA_PENCERE_SONU,
    STALE_BAR_UYARI_DK, TERMINAL_TAZE_BAR, BIST_TATILLER, BIST_YARIM_GUNLER,
    VERI_YOK_MODU_ESIK_DK, SPLIT_SUREKLILIK_ESIK_PCT, BAR_BOSLUK_ESIK_SAAT,
    GUNLUK_FETCH_PERIOD, GUNLUK_DEQUE_MAXLEN
)

logger = logging.getLogger(__name__)

# Timeframe -> pandas süre etiketi (tamamlanmis_mumlar filtresi için)
TF_SURELERI = {"1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D"}
# Mum kapanış anı = etiket + bu süre. 1D İSTİSNA: günlük mum 00:00 etiketli ama gerçek
# seans kapanışı 18:30'dur (ölçüldü: son 1H mum 17:30 etiketli, 18:30'da kapanıyor).
# ESKİ HATA: 1D için de "etiket + 1 gün" kullanılıyordu -> 25 Eylül'ün günlük mumu
# 26 Eylül 00:00'a kadar "yarım mum" sayılırdı, yani GÜN İÇİNDE HİÇ analiz edilmez,
# günlük formasyonlar 24 saat gecikmeyle görülürdü (ölçüm: 18:35 taramasında son
# tamamlanan 1D mum = 24 Eylül'dü).
TF_KAPANIS_SURESI = {
    "1h": timedelta(minutes=30),
    "2h": timedelta(hours=2),
    "4h": timedelta(hours=4),
}
GUNLUK_MUM_KAPANIS_SAATI = dt_time(18, 30)  # BIST seans kapanışı (1H ölçümünden)

# === BIST SAAT KONTROLÜ ===

def bist_tatil_adi(d) -> Optional[str]:
    """Verilen gün BIST resmî tatiliyse tatil adını, değilse None döner.

    Neden? Tatil gününde (örn. 29 Ekim) Yahoo yeni mum üretmez. Bot bu bilgiyi
    bilmezse: (a) 30 hisse x 9 tur boşuna fetch eder, (b) Faz 1'in tazelik uyarısı
    tatil günü HER turda "VERİ ESKİ" der -> ölçüm: günde 270 satır gürültü.
    Tatil takvimi bu iki sorunu birden keser.
    """
    return BIST_TATILLER.get(d.date() if isinstance(d, datetime) else d)


def yarim_gun_kapanisi(d) -> Optional[Tuple[str, dt_time]]:
    """Yarım günse (açıklama, kapanış saati), değilse None. Örnek: 19 Mart 2026 -> 13:00."""
    anahtar = d.date() if isinstance(d, datetime) else d
    return BIST_YARIM_GUNLER.get(anahtar)


def seans_kapanis_saati(d=None) -> dt_time:
    """O günün seans kapanış saati (yarım günde 13:00, normalde 18:30)."""
    if d is None:
        d = datetime.now(ISTANBUL_TZ)
    yg = yarim_gun_kapanisi(d)
    return yg[1] if yg else GUNLUK_MUM_KAPANIS_SAATI


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
    
    # Hafta sonu mu?
    if now.weekday() >= 5:  # 5=Cumartesi, 6=Pazar
        return False
    
    # Saat kontrolü
    current_time = now.time()
    return BIST_OPEN <= current_time <= BIST_CLOSE


def tarama_penceresi_acik_mi(now: Optional[datetime] = None) -> bool:
    """
    Bot şu an TARAMA yapmalı mı? (is_bist_open'tan farklı: seans kapandıktan SONRA
    günün son mumunu analiz etmek için ek pay verir.)

    Neden ayrı fonksiyon? Yahoo'nun .IS 1H seansı 09:30-18:30 (ölçüldü). Günün son
    mumu (17:30 etiketli) 18:30'da kapanır. ESKİ kodda pencere 18:10'da kapandığı
    için BU MUM HİÇ ANALİZ EDİLMİYORDU. Şimdi pencere TARAMA_PENCERE_SONU'na
    (18:40) kadar açık -> son mum 18:35 taramasında görülür.

    Hafta içi + BIST_OPEN..TARAMA_PENCERE_SONU arası.
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

def time_until_next_open(now: Optional[datetime] = None) -> float:
    """Bir sonraki açılışa kadar kaç saniye? Uyku için"""
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    if now.tzinfo is None:
        now = ISTANBUL_TZ.localize(now)
    else:
        now = now.astimezone(ISTANBUL_TZ)
    
    # Eğer şu an açıksa 0 dön
    if is_bist_open(now):
        return 0.0
    
    # Sonraki iş gününü bul
    next_day = now
    while True:
        next_day = next_day + timedelta(days=1)
        if next_day.weekday() < 5:  # Hafta içi
            break
    
    # O günün 09:50'si
    next_open = next_day.replace(hour=BIST_OPEN.hour, minute=BIST_OPEN.minute, second=0, microsecond=0)
    # Eğer bugün hafta içi ve saat 09:50'den önce ise, bugün açılacak
    if now.weekday() < 5 and now.time() < BIST_OPEN:
        next_open = now.replace(hour=BIST_OPEN.hour, minute=BIST_OPEN.minute, second=0, microsecond=0)
    
    delta = (next_open - now).total_seconds()
    return max(delta, 0.0)

def time_until_next_candle_close(now: Optional[datetime] = None) -> float:
    """
    Bir sonraki TARAMA anına kadar kaç saniye? (mum kapanışı + 5 dk)

    ÖLÇÜLMÜŞ GERÇEKLİK (config.py'deki notlara bak): yfinance'in .IS 1H mumları
    :30'da kapanır (09:30, 10:30, ... 17:30 etiketli, etiket = mum BAşı) ve günün
    son mumu 18:30'da kapanır.

    ESKİ HATA: "saat başı + 5 dk" (=:05) hesaplıyordu. Mum :30'da kapandığı için
      - her tarama veriyi 35 DAKİKA geç gösteriyordu (11:05 taraması 09:30 mumunu
        görüyordu, 10:30 mumu 11:30'da kapanıyordu), ve
      - günün son mumu (18:30 kapanış) hiç analiz edilmiyordu.

    YENİ: tarama = mum kapanışı + SCAN_DELAY_AFTER_CLOSE_MIN -> :35.
    Günün son taraması: son mum 18:30 kapanır -> 18:35.
    """
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    if now.tzinfo is None:
        now = ISTANBUL_TZ.localize(now)
    else:
        now = now.astimezone(ISTANBUL_TZ)

    # Bu saatin (veya bir sonraki saatin) :30'su = mum kapanışı
    kapanis = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=CANDLE_CLOSE_MINUTE)
    if kapanis <= now:
        kapanis += timedelta(hours=1)

    # Mum kapanışı + gecikme = tarama anı
    tarama = kapanis + timedelta(minutes=SCAN_DELAY_AFTER_CLOSE_MIN)

    # Günün SON taraması: son mum 18:30'da kapanır -> 18:35'te taranmalı.
    # Eğer hesaplanan tarama bundan sonraysa ve son tarama henüz gelmediyse, ona çek.
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
    """
    Bugün EN SON kapanmış 1H mumun kapanış anı. Hiç kapanmadıysa None.

    Ölçülen seans: ilk mum 09:30 etiketli (09:30-10:30), son mum 17:30 etiketli
    (17:30-18:30). Yani kapanış anları 10:30, 11:30, ..., 18:30.
    09:30 "kapanışı" YOKTUR (ilk mum daha yeni açılmıştır) -> None döner.
    """
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    if now.tzinfo is None:
        now = ISTANBUL_TZ.localize(now)
    else:
        now = now.astimezone(ISTANBUL_TZ)

    # Yarım günde seans 13:00'te kapanır: son mum 12:30 etiketli (12:00-13:00).
    yg = yarim_gun_kapanisi(now)
    if yg:
        kapanis = now.replace(hour=yg[1].hour, minute=yg[1].minute, second=0, microsecond=0)
        if now < kapanis:
            kapanis = (now.replace(minute=0, second=0, microsecond=0)
                       + timedelta(minutes=CANDLE_CLOSE_MINUTE))
            if kapanis > now:
                kapanis -= timedelta(hours=1)
        return kapanis

    kapanis = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=CANDLE_CLOSE_MINUTE)
    if kapanis > now:
        kapanis -= timedelta(hours=1)
    # İlk gerçek kapanış 10:30'dur; ondan önceki "kapanış" bugün için geçerli değil.
    ilk_kapanis = (now.replace(hour=BIST_OPEN.hour, minute=BIST_OPEN.minute, second=0, microsecond=0)
                   + timedelta(minutes=40))
    if kapanis < ilk_kapanis:
        return None
    return kapanis


def tarama_animi_mi(now: Optional[datetime] = None,
                    son_taranan_kapanis: Optional[datetime] = None) -> bool:
    """
    Şu an tarama YAPILMALI MI?

    Kural (ölçümden): mum :30'da kapanır, kapanış + 5 dk = tarama anı (:35).
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
        return False  # resmî tatil: veri yok, tarama da yok

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
      - En yeni 1H mum VERI_YOK_MODU_ESIK_DK (20 saat) yaşında veya daha eski.
        Normal seans içi bu değer < 60 dk'dır (ölçüm); gece/hafta sonu boşluğunda
        15-60 saate çıkar ama o zaman pencere kapalıdır, bu fonksiyon çağrılmaz.

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

class StockDequeManager:
    """
    Her hisse için 360 mumluk deque tutar
    Neden deque? maxlen=360 ile en eski otomatik silinir, rolling window
    Neden kalıcı? Bot restart olursa diskten yükle, 60 gün veriyi tekrar çekme
    """
    def __init__(self, maxlen: int = DEQUE_MAXLEN, data_dir: str = DATA_DIR):
        self.maxlen = maxlen
        self.data_dir = data_dir
        self.deques: Dict[str, deque] = {}
        # 1D (günlük) derin veri: 1H penceresinden BAĞIMSIZ (~500 bar).
        # Neden ayrı? 1H deque 360 bar = ~40 iş günü; resample 1D sadece ~40 bar
        # verir ve 1D formasyon penceresi (20-60 bar) marjinal kalır. 1H'yi
        # büyütmek Pine uyumunu bozabileceği için günlük veri ayrı ve derin tutulur.
        self.gunluk_deques: Dict[str, deque] = {}
        # Son tespit edilen veri sorunları (split / bar boşluğu) - main.py okur
        self.sureklilik_sorunlari: Dict[str, List[Dict]] = {}
        
        # Data dir oluştur
        os.makedirs(data_dir, exist_ok=True)
        
        logger.info(f"Deque manager başlatıldı - maxlen={maxlen}, dir={data_dir}")
    
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
    
    def append_candle(self, stock: str, candle: dict):
        """
        Yeni mum ekle
        candle: {'open','high','low','close','volume','timestamp'}
        """
        dq = self.get_deque(stock)
        dq.append(candle)
    
    def append_dataframe(self, stock: str, df: pd.DataFrame):
        """DataFrame'den toplu ekle — timestamp bazlı TEKİLLEŞTİRİLMİŞ (idempotent).
        Aynı zamana sahip mum varsa yeni değerler yazılır (taze kazınır),
        pencere taşarsa en eski düşer (maxlen FIFO). Böylece aynı 60d penceresi
        tekrar çekilip eklense bile deque bozulmaz."""
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
        
        # Sütun sırası
        df = df[['open', 'high', 'low', 'close', 'volume']]
        
        return df
    
    def save_to_disk(self, stock: str):
        """Diske kaydet - hem pickle hem json (senin isteğin both)"""
        if stock not in self.deques:
            return
        
        # Pickle - hızlı
        pkl_path = os.path.join(self.data_dir, f"{stock}.pkl")
        # JSON - GitHub'da görünsün, human-readable
        json_path = os.path.join(self.data_dir, f"{stock}.json")
        
        try:
            data_list = list(self.deques[stock])
            
            # Pickle
            with open(pkl_path, 'wb') as f:
                pickle.dump(data_list, f)
            
            # JSON - timestamp'i string'e çevir
            json_data = []
            for candle in data_list:
                json_candle = candle.copy()
                # Timestamp'i ISO format string yap
                if 'timestamp' in json_candle:
                    ts = json_candle['timestamp']
                    if hasattr(ts, 'isoformat'):
                        json_candle['timestamp'] = ts.isoformat()
                    else:
                        json_candle['timestamp'] = str(ts)
                json_data.append(json_candle)
            
            import json
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"{stock} deque diske kaydedildi - {pkl_path} + {json_path} ({len(data_list)} mum)")
        except Exception as e:
            logger.error(f"{stock} diske kaydedilemedi: {e}")
    
    def load_from_disk(self, stock: str) -> Optional[deque]:
        """Diskten yükle - önce pickle, yoksa json"""
        pkl_path = os.path.join(self.data_dir, f"{stock}.pkl")
        json_path = os.path.join(self.data_dir, f"{stock}.json")
        
        # Önce pickle dene (hızlı)
        if os.path.exists(pkl_path):
            try:
                with open(pkl_path, 'rb') as f:
                    data = pickle.load(f)
                dq = deque(data, maxlen=self.maxlen)
                logger.debug(f"{stock} pickle'dan yüklendi: {len(dq)} mum")
                return dq
            except Exception as e:
                logger.warning(f"{stock} pickle yüklenemedi: {e}, json deneniyor")
        
        # Pickle yoksa json dene
        if os.path.exists(json_path):
            try:
                import json
                from dateutil import parser as date_parser
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                data_list = []
                for candle in json_data:
                    # Timestamp'i geri çevir
                    if 'timestamp' in candle and isinstance(candle['timestamp'], str):
                        try:
                            candle['timestamp'] = date_parser.parse(candle['timestamp'])
                        except:
                            pass
                    data_list.append(candle)
                
                dq = deque(data_list, maxlen=self.maxlen)
                logger.debug(f"{stock} json'dan yüklendi: {len(dq)} mum")
                return dq
            except Exception as e:
                logger.warning(f"{stock} json'dan yüklenemedi: {e}")
        
        return None
    
    def _gunluk_dosya(self, stock: str) -> str:
        return os.path.join(self.data_dir, f"{stock}_gunluk.json")

    def get_gunluk_deque(self, stock: str) -> deque:
        """1D (günlük) deque al, yoksa diskten yükle / oluştur."""
        if stock not in self.gunluk_deques:
            yol = self._gunluk_dosya(stock)
            dq = None
            if os.path.exists(yol):
                try:
                    import json
                    with open(yol, "r", encoding="utf-8") as f:
                        ham = json.load(f)
                    yuklenen = []
                    for c in ham:
                        ts = pd.to_datetime(c["timestamp"])
                        if ts.tzinfo is None:
                            ts = ISTANBUL_TZ.localize(ts)
                        else:
                            ts = ts.tz_convert(ISTANBUL_TZ)
                        yuklenen.append({"timestamp": ts, "open": float(c["open"]),
                                         "high": float(c["high"]), "low": float(c["low"]),
                                         "close": float(c["close"]),
                                         "volume": float(c.get("volume", 0))})
                    yuklenen.sort(key=lambda c: c["timestamp"])
                    dq = deque(yuklenen[-GUNLUK_DEQUE_MAXLEN:], maxlen=GUNLUK_DEQUE_MAXLEN)
                    logger.info(f"{stock} günlük deque diskten yüklendi - {len(dq)} bar")
                except Exception as e:
                    logger.warning(f"{stock} günlük cache okunamadı ({e}) - yeniden çekilecek")
                    dq = None
            if dq is None:
                dq = deque(maxlen=GUNLUK_DEQUE_MAXLEN)
            self.gunluk_deques[stock] = dq
        return self.gunluk_deques[stock]

    def append_gunluk_dataframe(self, stock: str, df: pd.DataFrame) -> None:
        """1H ile aynı idempotent birleştirme (timestamp bazlı tekilleştirme)."""
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

    def to_gunluk_dataframe(self, stock: str) -> Optional[pd.DataFrame]:
        dq = self.get_gunluk_deque(stock)
        if len(dq) == 0:
            return None
        df = pd.DataFrame(list(dq))
        df.set_index("timestamp", inplace=True)
        return df

    def gunluk_veri_eksik_mi(self, stock: str, now: Optional[datetime] = None) -> bool:
        """Günlük veri bugüne ait değilse (boş/eksik) True -> fetch gerekir."""
        df = self.to_gunluk_dataframe(stock)
        if df is None or len(df) < 30:
            return True
        if now is None:
            now = datetime.now(ISTANBUL_TZ)
        son = df.index[-1]
        son = son.tz_convert(ISTANBUL_TZ) if son.tzinfo else ISTANBUL_TZ.localize(son)
        # Son günlük bar bugün değilse (tatil/yarım gün dahil) eksik sayılır.
        return son.date() < now.date()

    def save_gunluk_to_disk(self, stock: str):
        dq = self.get_gunluk_deque(stock)
        os.makedirs(self.data_dir, exist_ok=True)
        import json
        with open(self._gunluk_dosya(stock), "w", encoding="utf-8") as f:
            json.dump([{"timestamp": c["timestamp"].isoformat(), "open": c["open"],
                        "high": c["high"], "low": c["low"], "close": c["close"],
                        "volume": c["volume"]} for c in dq], f, ensure_ascii=False)

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
        son = df.index[-1]
        son = son.tz_convert(ISTANBUL_TZ) if son.tzinfo else ISTANBUL_TZ.localize(son)
        return (now - son).total_seconds() / 60.0

    def save_all(self):
        """Tümünü kaydet (1H + 1D)"""
        for stock in self.deques:
            self.save_to_disk(stock)
        for stock in self.gunluk_deques:
            self.save_gunluk_to_disk(stock)
        logger.info(f"Tüm deque'ler kaydedildi - {len(self.deques)} hisse "
                    f"(+{len(self.gunluk_deques)} günlük)")

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
        ts = c['timestamp']
        ts = ts.tz_convert(ISTANBUL_TZ) if ts.tzinfo else ISTANBUL_TZ.localize(ts)
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

def resample_ohlcv(df_1h: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    1H veriyi 2H, 4H, 1D'ye çevir
    Pine'daki resample mantığı ile aynı
    
    Neden dropna? BIST seans dışı boş mumlar oluşur, onları at
    Neden session gap handling? Gece mumları olmamalı
    
    ÖNEMLİ (B1 fix): 2H/4H kovaları BIST SEANS başına (ilk 1H mumun etiketi, 09:30)
    hizalanır. Neden? Pine'daki request.security(..., "120"/"240") seans başından
    sayar; pandas'in varsayılanı gece yarısıdır. Varsayıanla BIST gününün ilk 1H mumu
    (09:30) TEK BAŞINA bir "2H mumu" oluyor ve sonraki tüm barlar 1 saat kayıyordu
    -> 2H/4H formasyonlar TradingView'dekiyle aynı pivotları üretmiyordu.
    Ölçüm: eskiden 08:00/10:00/12:00... -> şimdi 09:30/11:30/13:30... (TV ile aynı)
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
        # Kova hizası: günlük için gece yarısı (doğal), 2H/4H için SEANS başı.
        # origin=start_day + offset=<seans başı> -> kovalar 09:30'dan itibaren N saatlik.
        # Seans başını veriden çıkarıyoruz (hard-code 09:30 değil): ilk barın saati.
        offset = None
        if timeframe in ("2h", "4h") and len(df.index) > 0:
            ilk = df.index[0]
            offset = f"{ilk.hour}h{ilk.minute:02d}min"
        
        if offset:
            df_resampled = df.resample(timeframe, offset=offset).agg(available_cols)
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

def tamamlanmis_mumlar(df: pd.DataFrame, tf: str, now: Optional[datetime] = None) -> pd.DataFrame:
    """Devam eden (yarım) mumu çıkarır: kova etiketi + TF süresi > now ise o mum henüz
    kapanmamıştır ve motor verilmemelidir. Yahoo'nun etiket hizalaması ne olursa olsun
    güvenlidir — her mum kapanışından sonraki İLK taramada beslenir (Pine bar kapanışı
    mantığıyla birebir). Resample sol-etiketli olduğu için etiket+TF = kova kapanışıdır."""
    if df is None or len(df) == 0:
        return df
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    idx = df.index
    if idx.tz is None:
        idx = idx.tz_localize(ISTANBUL_TZ)
    else:
        idx = idx.tz_convert(ISTANBUL_TZ)
    sinir = pd.Timestamp(now).tz_convert(ISTANBUL_TZ) if pd.Timestamp(now).tzinfo else ISTANBUL_TZ.localize(pd.Timestamp(now))
    if tf == "1d":
        # Günlük mum 00:00 etiketli ama SEANS KAPANIŞINDA (18:30) tamamlanır.
        # "Etiket + 1 gün" kuralı günlük mumu 24 saat yarım sayardı.
        kapanis = idx.normalize() + pd.Timedelta(
            hours=GUNLUK_MUM_KAPANIS_SAATI.hour, minutes=GUNLUK_MUM_KAPANIS_SAATI.minute)
    else:
        kapanis = idx + TF_KAPANIS_SURESI.get(tf, timedelta(minutes=30))
    tamam = kapanis <= sinir
    return df[np.asarray(tamam, dtype=bool)]


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

def fetch_with_rate_limit(stock: str, fetch_func, *args, **kwargs) -> Optional[pd.DataFrame]:
    """
    Rate limit korumalı veri çekme
    - 45-50 sn bekleme
    - Hata olursa logla, None dön, crash etme
    Neden? tvdatafeed/yfinance ban yemesin, bot çökmesin
    """
    try:
        # Rate limit bekleme
        delay = random.uniform(RATE_LIMIT_MIN, RATE_LIMIT_MAX)
        logger.info(f"{stock} için {delay:.1f}sn bekleniyor (rate limit)")
        time.sleep(delay)
        
        # Veriyi çek
        df = fetch_func(stock, *args, **kwargs)
        
        if df is None or len(df) == 0:
            logger.warning(f"{stock} boş veri döndü, atlanıyor")
            return None
        
        logger.info(f"{stock} için {len(df)} mum çekildi")
        return df
        
    except Exception as e:
        logger.error(f"{stock} veri çekme hatası: {e} - atlanıyor, bot devam ediyor")
        return None

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
            ham = yf.Ticker(stock + ".IS").history(period=period, interval="1d", auto_adjust=False)
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


def fetch_yfinance_1h(stock: str, period: str = "60d") -> Optional[pd.DataFrame]:
    """yfinance'den 1h OHLCV çeker (gürültü bastırılmış). Başarısızlıkta None döner.
    Not: Yahoo bazı sembolleri taşımıyor (örn. KOZAL.IS / KOZAA.IS -> HTTP 404).

    ÖNEMLİ - auto_adjust=False: yfinance'in default'ı auto_adjust=True (v0.2.51+).
    True iken geçmiş OHLC temettü/splite göre YENİDEN AYARLANIR; TradingView/Pine ise
    ham fiyat kullanır. Bu port sırasında parametre düşmüştü -> temettü sonrası tüm
    geçmiş kayar, pivot/sınır/ATR değerleri Pine'dan sapardı. Geri konuldu.
    """
    try:
        import io
        import contextlib
        import yfinance as yf
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            ham = yf.Ticker(stock + ".IS").history(period=period, interval="1h", auto_adjust=False)
        if ham is None or ham.empty:
            return None
        ham = ham.rename(columns=str.lower)
        gerekli = ["open", "high", "low", "close", "volume"]
        if not all(c in ham.columns for c in gerekli):
            return None
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
        return ham
    except Exception:
        return None


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
    
    high = close + np.abs(np.random.randn(n_bars) * 0.2)
    low = close - np.abs(np.random.randn(n_bars) * 0.2)
    low = np.maximum(low, 0.5)
    open_ = close + np.random.randn(n_bars) * 0.1
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
    print("=== Data.py Test ===")
    
    # BIST açık mı?
    print(f"BIST açık mı? {is_bist_open()}")
    print(f"Sonraki açılışa: {time_until_next_open()/3600:.2f} saat")
    print(f"Sonraki mum kapanışına: {time_until_next_candle_close()/60:.1f} dk")
    
    # Deque test
    manager = StockDequeManager(maxlen=10, data_dir="./test_data")
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
    
    # Temizle
    import shutil
    shutil.rmtree("./test_data", ignore_errors=True)
    print("\nTest bitti")
