#!/usr/bin/env python3
"""Çapraz piyasa Replay'i için Termux'ta günlük ham verileri indir.

Ayrı klasöre yazar; mevcut backfill_data, canlı bot, Supabase ve Telegram'a
DOKUNMAZ. Spot ve vadeli metal serileri ayrıdır, gram fiyatı burada türetilmez.
Yahoo bar_time değerleri mum ETİKETİDİR, gerçek kapanış zamanı değildir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
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


def _validated_frame(frame):
    """Bozuk/naive saatli veya geçersiz OHLC verisi arşive başarılı diye girmez."""
    import numpy as np
    import pandas as pd

    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
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
    if ((frame.high < frame[["open", "close", "low"]].max(axis=1)) |
            (frame.low > frame[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("OHLC yüksek/düşük tutarsızlığı var")
    # Kur/spot hacmi güvenilir olmayabilir; eksik hacim sıfırla değiştirilmez.
    if ((frame.volume.dropna() < 0) | ~np.isfinite(frame.volume.dropna())).any():
        raise ValueError("hacimde negatif veya sonsuz değer var")
    return frame


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
            log(f"  OK    {symbol:8} {ticker:12} {rec['rows']:5} bar  {rec['first_label']} → {rec['last_label']}")
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
        try:
            if raw is None:
                if transient:
                    tempo.gecici_hata(error)
                raise ValueError(error or "Yahoo boş veri döndürdü")
            frame = _validated_frame(raw)
            source_tz = str(frame.index.tz)
            frame = frame.tz_convert("Europe/Istanbul")
            rows = yb._csv_gz_yaz(path, frame)
            manifest["series"][symbol] = {
                "status": "ok", "ticker": ticker, "kind": kind, "currency": currency,
                "interval": "1d", "period": period, "auto_adjust": False,
                "provider_timezone": source_tz, "rows": rows,
                "first_label": str(frame.index[0]), "last_label": str(frame.index[-1]),
                "last_bar_may_be_incomplete": True, "closed_at_verified": False,
                "quality": yb._kalite_raporu(frame), "sha256": _hash(path), "downloaded_at": _utc_now(),
            }
            tempo.basarili()
            log(f"  OK: {rows} bar | {frame.index[0]} → {frame.index[-1]}")
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
