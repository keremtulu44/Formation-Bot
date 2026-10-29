#!/usr/bin/env python3
"""Çapraz piyasa Replay'i için Termux'ta günlük ham verileri indir.

Ayrı klasöre yazar; mevcut backfill_data, canlı bot, Supabase ve Telegram'a
DOKUNMAZ. Spot ve vadeli metal serileri ayrıdır, gram fiyatı burada türetilmez.
Yahoo bar_time değerleri mum ETİKETİDİR, gerçek kapanış zamanı değildir.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.backfill import yahoo_backfill as yb  # noqa: E402

# Sembol -> (Yahoo ticker, varlık türü, para birimi). Spot/futures asla
# birbirinin yerine otomatik geçirilmez; araştırmacı veri kaynağını seçer.
SERILER = {
    "XU100": ("XU100.IS", "bist_endeks", "TRY"),
    "XU30": ("XU030.IS", "bist_endeks", "TRY"),
    "XU50": ("XU050.IS", "bist_endeks", "TRY"),
    "XBANK": ("XBANK.IS", "bist_endeks", "TRY"),
    "XUSIN": ("XUSIN.IS", "bist_endeks", "TRY"),
    "XUTUM": ("XUTUM.IS", "bist_endeks", "TRY"),
    "BRENT": ("BZ=F", "petrol_vadeli", "USD"),
    "USDTRY": ("USDTRY=X", "kur", "TRY_per_USD"),
    "XAUUSD": ("XAUUSD=X", "altin_spot", "USD_per_troy_ounce"),
    "XAGUSD": ("XAGUSD=X", "gumus_spot", "USD_per_troy_ounce"),
    "XAU_FUT": ("GC=F", "altin_vadeli", "USD_per_troy_ounce"),
    "XAG_FUT": ("SI=F", "gumus_vadeli", "USD_per_troy_ounce"),
}
DEFAULT_DIR = ROOT / "capraz_piyasa_data"
SCHEMA = "capraz-piyasa-ham-v1"
STOOQ_SPOT = {"XAUUSD": "xauusd", "XAGUSD": "xagusd"}
# Yahoo'da bu endeksler bazen tek mum döner. Aynı sembolü önce başka
# dönemlerle dene; BIST50 yerine başka bir endeksi ASLA geçirme.
KISA_YAHOO_YEDEK = {"XU50", "XUTUM"}


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_manifest(path):
    if not path.exists():
        return {"schema": SCHEMA, "series": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"manifest okunamadı; veri güvenliği için durduruldu: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("series"), dict):
        raise ValueError("manifest formatı tanınmıyor; veri güvenliği için durduruldu")
    return data


def _write_manifest(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def _invalid_ohlc_mask(frame):
    return ((frame.high < frame[["open", "close", "low"]].max(axis=1)) |
            (frame.low > frame[["open", "close", "high"]].min(axis=1)))


def _validated_frame(frame, *, allow_date_only=False, allow_invalid_ohlc=False):
    """Geçersiz OHLC yalnız açık izinle ham ve bayraklı arşive girer."""
    import numpy as np
    import pandas as pd

    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("geçerli tarih indeksi yok")
    if frame.index.tz is None:
        if not allow_date_only or not (frame.index == frame.index.normalize()).all():
            raise ValueError("zaman dilimi bilinmiyor; günlük etiket güvenle kaydedilemiyor")
    if frame.index.has_duplicates or frame.index.hasnans:
        raise ValueError("yinelenen veya boş zaman etiketi var")
    cols = ["open", "high", "low", "close", "volume"]
    if not set(cols).issubset(frame.columns):
        raise ValueError("OHLCV kolonları eksik")
    frame = frame[cols].copy().sort_index()
    for col in cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    prices = frame[["open", "high", "low", "close"]]
    if len(frame) < 60:
        raise ValueError(f"en az 60 günlük bar gerekli, gelen: {len(frame)}")
    if not np.isfinite(prices.to_numpy()).all() or (prices <= 0).any().any():
        raise ValueError("fiyatlarda boş, sonsuz veya sıfır/negatif değer var")
    if _invalid_ohlc_mask(frame).any() and not allow_invalid_ohlc:
        raise ValueError("OHLC yüksek/düşük tutarsızlığı var")
    # Kur/spot hacmi güvenilir olmayabilir; eksik hacim sıfırla değiştirilmez.
    if ((frame.volume.dropna() < 0) | ~np.isfinite(frame.volume.dropna())).any():
        raise ValueError("hacimde negatif veya sonsuz değer var")
    return frame


def _stooq_cek(symbol, period):
    """Stooq'un günlük XAU/USD veya XAG/USD CSV'si; tarih SADECE etikettir.

    Zaman dilimi ve kapanış anı API çıktısında yoktur, bu yüzden uydurulmaz.
    Ağ/erişim/CAPTCHA kaynaklı hata açıkça dönülür, vadeliye geçilmez.
    """
    import pandas as pd
    import requests

    try:
        response = requests.get(
            "https://stooq.com/q/d/l/", params={"s": symbol, "i": "d"}, timeout=30,
            headers={"User-Agent": "Formation-Bot research/1.0"},
        )
        response.raise_for_status()
        frame = pd.read_csv(io.StringIO(response.text))
        frame.columns = [str(c).strip().lower() for c in frame.columns]
        required = {"date", "open", "high", "low", "close"}
        if not required.issubset(frame.columns):
            raise ValueError("CSV yok/eksik; erişim kısıtı, CAPTCHA veya boş veri olabilir")
        frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
        frame = frame.set_index("date").sort_index()
        if period != "max":
            start = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize() - pd.DateOffset(years=int(period[:-1]))
            frame = frame[frame.index >= start]
        if "volume" not in frame.columns:
            frame["volume"] = float("nan")
        return _validated_frame(frame, allow_date_only=True), ""
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        return None, f"Stooq verisi alınamadı: {type(exc).__name__}: {str(exc)[:200]}"


def _tradingview_cek(symbol, period):
    """BIST endeksi için anonim TradingView yedeği (opsiyonel bağımlılık).

    tvDatafeed 2.1.1 POSIX zamanlarını datetime.fromtimestamp ile yerel naive
    zaman olarak verir. Tek iş parçacıklı CLI'da TZ=UTC altında okuyup TZ'yi
    geri alıyoruz. Saat etiketi yine gerçek mum kapanışı olarak kullanılamaz.
    """
    import importlib.metadata
    import pandas as pd

    try:
        if importlib.metadata.version("tradingview-datafeed") != "2.1.1":
            raise ValueError("yalnız tradingview-datafeed==2.1.1 doğrulandı")
        from tvDatafeed import Interval, TvDatafeed
    except (ImportError, importlib.metadata.PackageNotFoundError, ValueError) as exc:
        return None, f"TradingView yedeği yok: {exc}; pip install tradingview-datafeed==2.1.1"
    if not hasattr(time, "tzset"):
        return None, "TradingView yedeği: güvenli UTC zaman ayarı desteklenmiyor"
    original_tz = os.environ.get("TZ")
    client = None
    try:
        os.environ["TZ"] = "UTC"
        time.tzset()
        client = TvDatafeed()  # Anonim: kullanıcı adı, parola veya token istenmez.
        bars = {"2y": 800, "5y": 1600, "10y": 3000, "max": 5000}[period]
        data = client.get_hist(symbol=symbol, exchange="BIST", interval=Interval.in_daily, n_bars=bars)
        if data is None or not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("boş veya geçersiz endeks verisi")
        if data.index.tz is not None:
            raise ValueError("beklenmeyen saat formatı; otomatik dönüştürülmedi")
        data = data.copy()
        data.index = data.index.tz_localize("UTC")
        if period != "max":
            start = pd.Timestamp.now(tz="UTC").normalize() - pd.DateOffset(years=int(period[:-1]))
            data = data[data.index >= start]
        return _validated_frame(data), ""
    except Exception as exc:  # noqa: BLE001 - üçüncü taraf ağ kütüphanesi hataları CLI'da raporlanır
        return None, f"TradingView verisi alınamadı: {type(exc).__name__}: {str(exc)[:200]}"
    finally:
        try:
            if client is not None and getattr(client, "ws", None) is not None:
                client.ws.close()
        except Exception:  # noqa: BLE001, S110 - bağlantı kapanışı veri sonucunu değiştirmemeli
            pass
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()


def _record_ok(record, path, ticker, period):
    if not isinstance(record, dict) or record.get("status") != "ok":
        return False
    if record.get("ticker") != ticker or record.get("period") != period or not path.is_file():
        return False
    try:
        return _hash(path) == record.get("sha256")
    except OSError:
        return False


def durum(hedef, manifest, period=None, *, log=print):
    """Eksiksiz ve checksum doğrulanmış çıktıları raporlar; ağ kullanmaz."""
    missing = []
    for symbol, (ticker, _, _) in SERILER.items():
        rec = manifest["series"].get(symbol)
        expected_period = period or (rec.get("period") if isinstance(rec, dict) else None)
        path = hedef / f"{symbol}_1d.csv.gz"
        if _record_ok(rec, path, ticker, expected_period):
            provider = rec.get("provider", "yahoo")
            actual = rec.get("provider_symbol", ticker)
            log(f"  OK    {symbol:8} {actual:12} ({provider}) {rec['rows']:5} bar  {rec['first_label']} → {rec['last_label']}")
            if rec.get("partial_history"):
                missing.append(symbol)
                log(f"        KAPSAM EKSİK: istenen {rec['period']}, sorgu {rec['download_period']}, "
                    f"gerçek aralık {rec.get('coverage_days', '?')} gün; yenilemeyle tekrar dene.")
            bad = rec.get("quality", {}).get("invalid_ohlc_count", 0)
            if bad:
                log(f"        UYARI: {bad} tutarsız OHLC mumu ham olarak korundu; ATR için kullanmadan önce filtrelenmeli.")
            if rec.get("last_error"):
                log(f"        Son yenileme başarısız; eski veri korunuyor: {rec['last_error']}")
        else:
            missing.append(symbol)
            reason = rec.get("last_error", "dosya veya doğrulanmış manifest yok") if isinstance(rec, dict) else "henüz çekilmedi"
            log(f"  EKSİK {symbol:8} {ticker:12} {reason}")
    log(f"\n{len(SERILER) - len(missing)}/{len(SERILER)} seri doğrulandı; eksik: {', '.join(missing) or 'yok'}")
    return missing


def cek(hedef, period, *, yenile=False, log=print, tempo=None):
    manifest_path = hedef / "manifest.json"
    manifest = _read_manifest(manifest_path)
    tempo = tempo or yb.Tempo(grup=6, log=log)
    failed_this_run = []
    manifest["notice"] = (
        "Ham günlük Yahoo OHLCV; bar_time mum etiketi, kapanış veya kullanılabilirlik zamanı değildir. "
        "Son mum tamamlanmamış olabilir. Spot/vadeli ayrı, gram/TL türetilmemiştir."
    )
    for symbol, (ticker, kind, currency) in SERILER.items():
        if tempo.dur:
            log("İstek hızı koruması devreye girdi; daha sonra aynı komutla devam edin.")
            break
        path = hedef / f"{symbol}_1d.csv.gz"
        prev = manifest["series"].get(symbol)
        if not yenile and _record_ok(prev, path, ticker, period):
            log(f"ATLANDI {symbol}: önceki veri ve checksum doğrulandı")
            continue
        if path.exists() and not yenile:
            log(f"UYARI {symbol}: mevcut dosya doğrulanamadı veya dönem değişti; üzerine yazılmadı (--yenile).")
            continue
        log(f"ÇEKİLİYOR {symbol}: {ticker} ({period}, 1d)")
        tempo.bekle()
        raw, error, transient = yb._ham_cek(ticker, period, "1d")
        tempo.istek_bitti()
        provider, actual_symbol, download_period = "yahoo", ticker, period
        yahoo_error = error
        try:
            if symbol in KISA_YAHOO_YEDEK and not transient and (raw is None or len(raw) < 60):
                # Farklı endeks yerine aynı ticker'a farklı dönemlerle yeniden sor.
                for fallback_period in (p for p in ("max", "5y", "2y") if p != period):
                    log(f"  Yahoo {ticker}: yeterli bar yok; aynı sembol {fallback_period} ile deneniyor.")
                    tempo.bekle()
                    alt, alt_error, alt_transient = yb._ham_cek(ticker, fallback_period, "1d")
                    tempo.istek_bitti()
                    if alt_transient:
                        error, transient, raw = alt_error, True, None
                        break
                    if alt is not None and len(alt) >= 60:
                        raw, error, download_period = alt, "", fallback_period
                        break
                if not transient and (raw is None or len(raw) < 60):
                    tv_symbol = {"XU50": "XU050", "XUTUM": "XUTUM"}[symbol]
                    log(f"  Yahoo geçmişi yetersiz; TradingView BIST:{tv_symbol} deneniyor.")
                    tempo.bekle()
                    tv_raw, tv_error = _tradingview_cek(tv_symbol, period)
                    tempo.istek_bitti()
                    if tv_raw is not None:
                        raw, error, download_period = tv_raw, "", period
                        provider, actual_symbol = "tradingview", f"BIST:{tv_symbol}"
                    else:
                        error = f"Yahoo yeterli geçmiş vermedi | {tv_error}"
                        raw = None
            if symbol in STOOQ_SPOT and raw is None and not transient:
                log(f"  Yahoo spot erişilemedi; Stooq {STOOQ_SPOT[symbol]} deneniyor (vadeliye çevrilmez).")
                tempo.bekle()
                raw, stooq_error = _stooq_cek(STOOQ_SPOT[symbol], period)
                tempo.istek_bitti()
                if raw is not None:
                    provider, actual_symbol = "stooq", STOOQ_SPOT[symbol]
                else:
                    error = f"Yahoo: {yahoo_error[:180]} | {stooq_error[:180]}"
            if raw is None:
                if transient:
                    tempo.gecici_hata(error)
                raise ValueError(error or "Sağlayıcı boş veri döndürdü")
            frame = _validated_frame(raw, allow_date_only=(provider == "stooq"),
                                     allow_invalid_ohlc=(symbol == "USDTRY"))
            source_tz = str(frame.index.tz) if frame.index.tz is not None else None
            if source_tz:
                frame = frame.tz_convert("Europe/Istanbul")
            bad_labels = [str(x) for x in frame.index[_invalid_ohlc_mask(frame)]]
            quality = yb._kalite_raporu(frame)
            quality.update({"invalid_ohlc_count": len(bad_labels), "invalid_ohlc_labels": bad_labels,
                            "atr_ready": not bool(bad_labels)})
            first, last = str(frame.index[0]), str(frame.index[-1])
            if provider == "stooq":
                # Sadece YYYY-MM-DD: Stooq kapanış saati/zaman dilimi sağlamaz.
                frame.index = frame.index.strftime("%Y-%m-%d")
                first, last = frame.index[0], frame.index[-1]
            rows = yb._csv_gz_yaz(path, frame)
            import pandas as pd
            coverage_days = (pd.Timestamp(last).date() - pd.Timestamp(first).date()).days
            # Dönem etiketi 'max' olsa da sağlayıcı az geçmiş döndürebilir.
            # 45 günlük pay, hafta sonu ve tatillerin uç tarihlerdeki kaymasını tolere eder.
            partial = ((download_period != "max" and period == "max") or
                       (period != "max" and download_period != "max" and
                        int(download_period[:-1]) < int(period[:-1])) or
                       (period != "max" and coverage_days < int(int(period[:-1]) * 365.25) - 45))
            manifest["series"][symbol] = {
                "status": "ok", "ticker": ticker, "kind": kind, "currency": currency,
                "provider": provider, "provider_symbol": actual_symbol,
                "interval": "1d", "period": period, "download_period": download_period,
                "partial_history": partial, "coverage_days": coverage_days,
                "auto_adjust": False if provider == "yahoo" else None,
                "adjustment_note": ("tvdatafeed requests splits adjustment" if provider == "tradingview"
                                    else "unadjusted Yahoo" if provider == "yahoo" else "unknown Stooq"),
                "volume_note": ("tvDatafeed may replace missing volume with 0" if provider == "tradingview"
                                else "zero or missing volume may be non-informative"),
                "provider_timezone": source_tz, "rows": rows,
                "first_label": first, "last_label": last,
                "last_bar_may_be_incomplete": True, "closed_at_verified": False,
                "quality": quality, "sha256": _hash(path), "downloaded_at": _utc_now(),
            }
            tempo.basarili()
            log(f"  OK: {rows} bar | {first} → {last} | kaynak: {provider}/{actual_symbol}")
            if bad_labels:
                log(f"  UYARI: {len(bad_labels)} tutarsız OHLC mumu ham kaydedildi; ATR'den önce filtre şart.")
            if partial:
                log(f"  UYARI: İstenen {period} yerine {download_period} kapsamı bulundu.")
        except (ValueError, OSError, TypeError) as exc:
            failed_this_run.append(symbol)
            # Yenilemede eski başarı kaydı ve dosyayı koru; hata ayrı not edilir.
            old = dict(prev) if isinstance(prev, dict) else {"status": "error", "ticker": ticker, "period": period}
            old["last_error"] = str(exc)[:300]
            old["last_error_at"] = _utc_now()
            manifest["series"][symbol] = old
            log(f"  HATA {symbol}: {str(exc)[:200]}")
        _write_manifest(manifest_path, manifest)
    log("\n--- Arşiv durumu ---")
    missing = durum(hedef, manifest, period, log=log)
    if missing:
        log("Eksik seriler var; bağlantıyı kontrol edip aynı komutu tekrar çalıştırın.")
    if failed_this_run:
        log(f"Bu koşuda başarısız: {', '.join(failed_this_run)} (varsa eski doğrulanmış veri korundu).")
    log(f"Çıktı: {hedef}")
    return 1 if missing or failed_this_run or tempo.dur else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hedef", type=Path, default=DEFAULT_DIR, help="ayrı çıktı klasörü")
    parser.add_argument("--period", default="5y", choices=("2y", "5y", "10y", "max"), help="günlük geçmiş (varsayılan 5y)")
    parser.add_argument("--yenile", action="store_true", help="mevcut serileri yeniden çek; geçerli veri yoksa eskiyi koru")
    parser.add_argument("--durum", action="store_true", help="yalnız yerel manifest ve SHA-256 doğrula; ağ yok")
    args = parser.parse_args(argv)
    hedef = args.hedef.resolve()
    # Asıl arşive veya onun altına yanlışlıkla yazmayı önle.
    original = (ROOT / "backfill_data").resolve()
    if hedef == original or original in hedef.parents or hedef == ROOT:
        parser.error("hedef repo kökü veya backfill_data olamaz; ayrı bir klasör seçin")
    try:
        manifest = _read_manifest(hedef / "manifest.json")
        if args.durum:
            return 1 if durum(hedef, manifest) else 0
        return cek(hedef, args.period, yenile=args.yenile)
    except (ValueError, OSError) as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
