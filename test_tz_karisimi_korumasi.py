"""Regresyon testleri: karışık tz sınıfları ("canlı 0/48" olayı).

Olay: `hydrate_from_supabase` 1S kolu `dateutil.parse` (tzoffset) döndürüyor;
taze Yahoo barları pytz olduğundan deque iki tz sınıfıyla doluyordu.
`to_dataframe` bu karışımdan object-Index üretiyor, `resample_ohlcv` hatayı
yutuyor ve `tamamlanmis_mumlar` "'Index' object has no attribute 'tz'" ile
her hisseyi hatalı sayıyordu (fetch 48/48 olmasına rağmen 0/48 hesaplama).

Bu dosya şunları kilitler:
1) Hydrate ettiği her timestamp'i tek tz sınıfına (İstanbul/pytz) normalize eder.
2) Tarihsel "zehirli" (tz sınıfı karışık) bir deque bile artık geçerli
   DatetimeIndex + tamamlanan resample/tamamlanmis üretir; tarama çökmez.
"""
from collections import deque
from datetime import datetime

import pandas as pd
from dateutil import parser as date_parser

from config import ISTANBUL_TZ
from data import StockDequeManager, resample_all_timeframes, tamamlanmis_mumlar

STOK = "TZREGRESYON"


def _seans_saatleri(gunler):
    """(gun, saat) çiftleri: 09:30..17:30 BIST 1H etiketleri."""
    return [(gun, saat) for gun in gunler for saat in range(9, 18)]


def _bar(ts, fiyat):
    return {"timestamp": ts, "open": fiyat, "high": round(fiyat * 1.001, 2),
            "low": round(fiyat * 0.999, 2), "close": fiyat, "volume": 1000.0}


def _lerp_liste(saatler, ts_uret, ilk=100.0):
    fiyat = ilk
    out = []
    for s in saatler:
        fiyat = round(fiyat * 1.0005, 2)
        out.append(_bar(ts_uret(s), fiyat))
    return out


def test_hydrate_1s_timestamp_tek_tz_sinifi(tmp_path):
    """Supabase 1S satırları hydrate sonrası pandas Timestamp + İstanbul/pytz."""
    mgr = StockDequeManager(data_dir=str(tmp_path))
    satirlar = []
    for gun, saat in _seans_saatleri((29, 30)):
        satirlar.append({"timestamp": f"2026-09-{gun:02d}T{saat:02d}:30:00+03:00",
                         "open": 100.0, "high": 100.1, "low": 99.9,
                         "close": 100.0, "volume": 5})
    mgr.hydrate_from_supabase([STOK], {"cache:1h:" + STOK: satirlar})

    dq = mgr.get_deque(STOK)
    assert len(dq) == len(satirlar)
    for bar in dq:
        ts = bar["timestamp"]
        assert isinstance(ts, pd.Timestamp)
        assert ts.tzinfo is not None
        # dateutil.tzoffset/pytz.FixedOffset DEĞİL; gerçek bölge saati (Europe/Istanbul)
        assert "tzoffset" not in type(ts.tzinfo).__name__.lower()
        assert "FixedOffset" not in type(ts.tzinfo).__name__
        # frame tarafına da tek sınıf yetişir
    df = mgr.to_dataframe(STOK)
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.tz is not None


def test_tarihsel_zehirli_karisik_deque_yine_tarar(tmp_path):
    """Normalize edilmemiş geçmiş veri (dateutil.tzoffset) + taze pytz fetch:
    eski canlı kırılmanın birebir durumu — artık çökmemeli, tarama tamamlanmalı."""
    mgr = StockDequeManager(data_dir=str(tmp_path))

    # Eski zehirli satırlar: dateutil.tzoffset nesnesi olarak belleğe düşmüşte
    eski = _lerp_liste(
        _seans_saatleri((28, 29)),
        lambda s: date_parser.parse(f"2026-09-{s[0]:02d}T{s[1]:02d}:30:00+03:00"),
    )
    mgr.deques[STOK] = deque(eski, maxlen=mgr.maxlen)

    # Taze Yahoo barları: pytz İstanbul DatetimeIndex (fetch normalizasyonu gibi)
    yeni_saat = _seans_saatleri((30,))
    idx = pd.DatetimeIndex([ISTANBUL_TZ.localize(datetime(2026, 9, g, h, 30))
                            for (g, h) in yeni_saat])
    fiyat = eski[-1]["close"]
    satirlar = []
    for _ in yeni_saat:
        fiyat = round(fiyat * 1.0005, 2)
        satirlar.append({"open": fiyat, "high": round(fiyat * 1.001, 2),
                         "low": round(fiyat * 0.999, 2), "close": fiyat,
                         "volume": 1000.0})
    taze = pd.DataFrame(satirlar, index=idx)
    mgr.append_dataframe(STOK, taze)

    df = mgr.to_dataframe(STOK)
    # Nihai sigorta çalıştı: object-Index yerine tek kova DatetimeIndex
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.tz is not None
    # dedupe: eski(18) + yeni(9) — günler kesişmiyor → 27 bar
    assert len(df) == len(eski) + len(yeni_saat)

    tfs = resample_all_timeframes(df)  # eskiden burada object-Index hata üretirdi
    assert not tfs["1h"].empty and not tfs["2h"].empty and not tfs["1d"].empty

    temiz = tamamlanmis_mumlar(df, "1h")  # eskiden AttributeError: 'Index' object has no attribute 'tz'
    assert isinstance(temiz, pd.DataFrame)
    assert len(temiz) > 0


def test_tamamlanmis_mumlar_object_index_savunmasi():
    """Slot savunması: doğrudan karma-tz object-Index verilirse de çökmez."""
    tarihler = [date_parser.parse("2026-09-29T09:30:00+03:00"),
                date_parser.parse("2026-09-29T10:30:00+03:00"),
                ISTANBUL_TZ.localize(datetime(2026, 9, 29, 11, 30)),
                ISTANBUL_TZ.localize(datetime(2026, 9, 29, 12, 30))]
    df = pd.DataFrame({"open": [1, 1, 1, 1.0], "high": [1.1, 1.1, 1.1, 1.1],
                       "low": [0.9, 0.9, 0.9, 0.9], "close": [1.0, 1.0, 1.0, 1.0],
                       "volume": [1.0, 1.0, 1.0, 1.0]},
                      index=pd.Index(tarihler, dtype=object))
    out = tamamlanmis_mumlar(df, "1h")
    assert isinstance(out, pd.DataFrame)
    assert isinstance(out.index, pd.DatetimeIndex)


def test_tarihsel_zehirli_gunluk_deque_yine_tarar(tmp_path):
    """Günlük taraf için de aynı object-Index sigortası."""
    mgr = StockDequeManager(data_dir=str(tmp_path))
    eski = [_bar(date_parser.parse(f"2026-09-{gun:02d}T00:00:00+03:00"), 100.0 + gun)
            for gun in range(25, 29)]
    yeni = [_bar(ISTANBUL_TZ.localize(datetime(2026, 9, gun, 0, 0)), 100.0 + gun)
            for gun in range(29, 31)]
    mgr.gunluk_deques[STOK] = deque(eski + yeni, maxlen=600)
    df = mgr.to_gunluk_dataframe(STOK)
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.tz is not None
