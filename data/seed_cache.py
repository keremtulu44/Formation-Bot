# data/seed_cache.py — atomik yazma + deque/seed cache (Faz 8).
# Yamalı yüzey (DATA_DIR, SEED_DATA_DIR, ALLOW_TRUSTED_PICKLE_CACHE,
# StockDequeManager, _atomic_pickle_write) data/__init__.py'nden _pkg.X okunur.

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

from data.replay import (  # noqa: F401
    _istanbul_zaman,
    bist_tatil_adi,
    seans_kapanis_saati,
)
from data.backfill import (  # noqa: F401
    _cache_barlari_birlestir,
    _karisik_timestamp_zaman_dilimi,
    _ohlcv_kayit_sorunlari,
    _temiz_1d_cache_kayitlari,
    _temiz_1h_cache_kayitlari,
    ohlcv_girdi_sorunlari,
    sureklilik_sorunlari_bul,
)

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


class StockDequeManager:
    """
    Her hisse için 360 mumluk deque tutar
    Neden deque? maxlen=360 ile en eski otomatik silinir, rolling window
    Neden kalıcı? Bot restart olursa diskten yükle, 60 gün veriyi tekrar çekme
    """
    def __init__(self, maxlen: int = DEQUE_MAXLEN, data_dir: str = _pkg.DATA_DIR,
                 persistent_store=None):
        self.maxlen = maxlen
        self.data_dir = data_dir
        self.persistent_store = persistent_store
        # Komutlar analizle eşzamanlı okuyabilir: kısa önbellek kopyalama ve
        # deque'yi değiştirme bölümlerini koru; ağ/hesaplamayı kilit altında tutma.
        self._cache_lock = threading.RLock()
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

        _pkg.logger.info(f"Deque manager başlatıldı - maxlen={maxlen}, dir={data_dir}")

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
                    _pkg.logger.warning("%s yerel günlük fetch zamanı bozuk; atlandı", stock)
        except (OSError, ValueError, UnicodeError) as exc:
            _pkg.logger.warning("Yerel günlük fetch deneme kaydı okunamadı: %s", exc)

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
            _pkg.logger.error("Günlük fetch deneme zamanı yerel diske yazılamadı: %s", exc)
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
                    _pkg.logger.warning(
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
                    _pkg.logger.warning(
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
                    _pkg.logger.warning("%s Supabase günlük fetch zamanı bozuk; atlandı", stock)
        if remote_attempt_newer:
            self._gunluk_fetch_attempts_kaydet()

        _pkg.logger.info(
            f"Supabase cache yüklendi: 1H={len(self.deques)}, 1D={len(self.gunluk_deques)}, "
            f"günlük fetch denemesi={len(self._gunluk_fetch_attempts)}"
        )

    def get_deque(self, stock: str) -> deque:
        """Hisse için deque al, yoksa oluştur."""
        with self._cache_lock:
            if stock not in self.deques:
                # Eşzamanlı ilk okuma ve tarama birbirinin deque'sini ezmesin.
                loaded = self.load_from_disk(stock)
                if loaded is not None:
                    self.deques[stock] = loaded
                    _pkg.logger.info(f"{stock} deque diskten yüklendi - {len(loaded)} mum")
                else:
                    self.deques[stock] = deque(maxlen=self.maxlen)
                    _pkg.logger.info(f"{stock} için yeni deque oluşturuldu")
            return self.deques[stock]
    
    def append_candle(self, stock: str, candle: dict) -> bool:
        """Validate and append one canonicalized candle without bypassing the OHLCV boundary."""
        sorunlar = _ohlcv_kayit_sorunlari(candle)
        if sorunlar:
            _pkg.logger.error("%s tekil mum reddedildi (%s)", stock, ", ".join(sorunlar))
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
            _pkg.logger.error("%s tekil mum reddedildi (kanonikleştirme: %s)", stock, type(exc).__name__)
            return False
        dq = self.get_deque(stock)
        with self._cache_lock:
            if _karisik_timestamp_zaman_dilimi(list(dq) + [normalized]):
                _pkg.logger.error("%s tekil mum reddedildi (cache zaman dilimi karışık)", stock)
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
            _pkg.logger.error(
                f"{stock}: gelen OHLCV frame geçersiz ({', '.join(girdi_sorunlari)}); "
                "deque güncellenmedi, mevcut veri korundu"
            )
            self.sureklilik_sorunlari[stock] = [{
                "tip": "gecersiz_girdi",
                "mesaj": f"girdi doğrulaması: {', '.join(girdi_sorunlari)}",
            }]
            return False
        dq = self.get_deque(stock)
        with self._cache_lock:
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
            _pkg.logger.error(
                "%s: birleştirilen cache'te naive/aware timestamp karışımı; deque korunuyor",
                stock,
            )
            self.sureklilik_sorunlari[stock] = [{
                "tip": "gecersiz_girdi",
                "mesaj": "timestamp zaman dilimi karışık",
            }]
            return False
        tumu = sorted(birlesik.values(), key=lambda c: c['timestamp'])
        with self._cache_lock:
            dq.clear()
            dq.extend(tumu[-self.maxlen:])
        _pkg.logger.info(f"{stock}: {yeni} yeni / {guncellenen} güncellenen mum (geldi {len(df)}, toplam {len(dq)})")
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
                _pkg.logger.warning(f"{stock}: {s_['mesaj']}")
            if any(s_['tip'] == 'split' for s_ in sorunlar):
                _pkg.logger.error(
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
        with self._cache_lock:
            data = list(dq)
        if not data:
            return None

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
                    _pkg._atomic_pickle_write(pkl_path, data_list)
                except Exception as exc:
                    # JSON is already durable and remains the default load path.
                    _pkg.logger.warning("%s optional pickle cache yazılamadı (%s)", stock, type(exc).__name__)

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
                        _pkg.logger.warning(
                            "%s 1H Supabase cache yazma başarısız%s; yerel JSON kopyası var",
                            stock,
                            f" ({remote_error})" if remote_error else "",
                        )
                else:
                    self.uzak_yazma_atlanan += 1


            _pkg.logger.debug(
                "%s deque diske kaydedildi - %s + %s (%d mum)",
                stock, pkl_path, json_path, len(data_list),
            )
            return remote_saved
        except Exception as exc:
            _pkg.logger.error("%s yerel cache diske kaydedilemedi (%s)", stock, type(exc).__name__)
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
                    _pkg.logger.warning(
                        "%s 1H JSON cache: %d bozuk/geçersiz kayıt atlandı",
                        stock, skipped,
                    )
                _pkg.logger.debug("%s JSON cache'ten yüklendi: %d mum", stock, len(bars))
                return deque(bars[-self.maxlen:], maxlen=self.maxlen)
            except (OSError, UnicodeError, ValueError) as exc:
                _pkg.logger.warning(
                    "%s JSON cache okunamadı (%s)", stock, type(exc).__name__
                )

        if not os.path.exists(pkl_path):
            return None
        if not _pkg.ALLOW_TRUSTED_PICKLE_CACHE:
            _pkg.logger.warning(
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
                _pkg.logger.warning(
                    "%s legacy pickle cache: %d bozuk/geçersiz kayıt atlandı",
                    stock, skipped,
                )
            _pkg.logger.info("%s eski pickle dosyasından yüklendi: %d mum (JSON yok)", stock, len(bars))
            return deque(bars[-self.maxlen:], maxlen=self.maxlen)
        except Exception as exc:  # noqa: BLE001 - yalnızca açık trusted-cache opt-in
            _pkg.logger.warning("%s güvenilir pickle cache okunamadı (%s)", stock, type(exc).__name__)
            return None

    def _gunluk_dosya(self, stock: str) -> str:
        return os.path.join(self.data_dir, f"{stock}_gunluk.json")

    def get_gunluk_deque(self, stock: str) -> deque:
        """1D (günlük) deque al, yoksa diskten yükle / oluştur."""
        with self._cache_lock:
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
                            _pkg.logger.warning(
                                "%s günlük JSON cache: %d bozuk/geçersiz kayıt atlandı",
                                stock, skipped,
                            )
                        dq = deque(
                            yuklenen[-GUNLUK_DEQUE_MAXLEN:], maxlen=GUNLUK_DEQUE_MAXLEN
                        )
                        _pkg.logger.info("%s günlük deque diskten yüklendi - %d bar", stock, len(dq))
                    except Exception as exc:
                        _pkg.logger.warning(
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
            _pkg.logger.error(
                "%s: gelen günlük OHLCV frame geçersiz (%s); günlük deque korunuyor",
                stock, ", ".join(sorunlar),
            )
            return False
        dq = self.get_gunluk_deque(stock)
        with self._cache_lock:
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
        with self._cache_lock:
            dq.clear()
            dq.extend(tumu[-GUNLUK_DEQUE_MAXLEN:])
        _pkg.logger.info(f"{stock}: {yeni} yeni / {guncellenen} güncellenen GÜNLÜK mum "
                    f"(toplam {len(dq)} bar)")
        return True

    def to_gunluk_dataframe(self, stock: str) -> Optional[pd.DataFrame]:
        dq = self.get_gunluk_deque(stock)
        with self._cache_lock:
            data = list(dq)
        if not data:
            return None
        df = pd.DataFrame(data)
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
                _pkg.logger.warning(
                    "Günlük fetch deneme durumu uzak saklayıcıya yazılamadı (%s)",
                    type(exc).__name__,
                )
            else:
                if not remote_saved:
                    _pkg.logger.warning("Günlük fetch deneme durumu uzak saklayıcı tarafından reddedildi")

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
                    _pkg.logger.warning("%s günlük Supabase cache yazılamadı (%s)", stock, type(exc).__name__)
                    return False
                if not remote_saved:
                    _pkg.logger.warning("%s günlük Supabase cache yazma başarısız; yerel kopya var", stock)
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
        yedek = os.path.join(_pkg.SEED_DATA_DIR, dosya_adi)
        farkli = os.path.abspath(yedek) != os.path.abspath(yol)
        if farkli and os.path.exists(yedek):
            _pkg.logger.debug(f"{dosya_adi}: veri dizininde yok, repo seed yedeği kullanılıyor")
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
                _pkg.logger.error("%s 1H cache kayıt hatası (%s)", stock, type(exc).__name__)
        for stock in list(self.gunluk_deques):
            try:
                daily_failed += not self.save_gunluk_to_disk(stock)
            except Exception as exc:
                daily_failed += 1
                _pkg.logger.error("%s 1D cache kayıt hatası (%s)", stock, type(exc).__name__)
        failed = hourly_failed + daily_failed
        if failed:
            _pkg.logger.warning(
                "Cache kayıtları tamamlandı ancak %d/%d seri için tüm kalıcı "
                "hedefler doğrulanmadı (1H=%d, 1D=%d)",
                failed, len(self.deques) + len(self.gunluk_deques),
                hourly_failed, daily_failed,
            )
            return False
        _pkg.logger.info(
            "Tüm deque'ler kalıcı depolara kaydedildi - %d hisse (+%d günlük)",
            len(self.deques), len(self.gunluk_deques),
        )
        return True


