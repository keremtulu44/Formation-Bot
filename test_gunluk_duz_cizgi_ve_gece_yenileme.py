"""1D grafik düz çizgi (flat-line) onarımı ve 02:00 TSİ Supabase-kayıtsız gece mum temizliği testleri."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

import config
from config import ISTANBUL_TZ
from data import (
    StockDequeManager,
    gunluk_bolunme_normalize_et,
    ohlcv_girdi_sorunlari,
    resample_ohlcv,
    sureklilik_sorunlari_bul,
)
from data.fetch import _saglayici_ohlcv_temizle
import grafik_uret


class _YasakSupabaseStore:
    """Gece 02:00 mum temizliğinde Supabase'e dokunulursa anında patlar."""

    writable = True

    def upsert(self, *args, **kwargs):
        raise AssertionError(f"Supabase upsert çağrılmamalıydı: {args}")

    def get(self, *args, **kwargs):
        raise AssertionError(f"Supabase get çağrılmamalıydı: {args}")


def test_saglayici_ohlcv_temizle_nan_hacim_bozuk_satir_ve_bist_tatil_barini_iyilestirir():
    idx = pd.date_range("2026-10-26", periods=5, freq="1D", tz=ISTANBUL_TZ)
    ham = pd.DataFrame(
        {
            "open": [34.10, 34.25, np.nan, 34.40, 34.55],
            "high": [34.30, 34.24999, 34.50, 34.60, 34.55],  # 2. satır float32 kayması, 5. satır düz
            "low": [34.05, 34.10, 34.20, 34.35, 34.55],
            "close": [34.22, 34.25, 34.40, 34.52, 34.55],
            "volume": [np.nan, np.nan, np.nan, np.nan, 0.0],
        },
        index=idx,
    )

    # FX/endeks (makro) serisinde tüm NaN hacimler 0.0 yapılır; tekil NaN OHLC satırı düşer.
    temiz_fx = _saglayici_ohlcv_temizle(ham, stock="USDTRY", timeframe="1d")
    assert temiz_fx is not None
    assert len(temiz_fx) == 4
    assert ohlcv_girdi_sorunlari(temiz_fx) == []
    assert (temiz_fx["volume"] == 0.0).all()

    # BIST hissesinde (KONTR) ek olarak 0 hacimli ve O=H=L=C sahte tatil barı da ayıklanır.
    ham_bist = ham.copy()
    ham_bist["volume"] = [1_200_000.0, 950_000.0, 800_000.0, 1_100_000.0, 0.0]
    temiz_bist = _saglayici_ohlcv_temizle(ham_bist, stock="KONTR", timeframe="1d")
    assert temiz_bist is not None
    assert len(temiz_bist) == 3
    assert ohlcv_girdi_sorunlari(temiz_bist) == []
    assert float((temiz_bist["high"] - temiz_bist["low"]).min()) > 0.0


def test_resample_gunluk_istanbul_gece_yarisi_kovalar_ve_cumartesi_tasmasini_atar():
    # Cuma gün içi barlar + Cumartesi 00:00 TSİ tek düz FX kapanış taşması (UTC 21:00 Cuma)
    ts_ist = [
        ISTANBUL_TZ.localize(datetime(2026, 10, 23, 10, 0)),
        ISTANBUL_TZ.localize(datetime(2026, 10, 23, 14, 0)),
        ISTANBUL_TZ.localize(datetime(2026, 10, 23, 23, 0)),
        ISTANBUL_TZ.localize(datetime(2026, 10, 24, 0, 0)),  # Cumartesi tek düz bar
    ]
    idx_utc = pd.DatetimeIndex([t.astimezone(pd.Timestamp.now("UTC").tz) for t in ts_ist])
    df_1h = pd.DataFrame(
        {
            "open": [34.10, 34.20, 34.35, 34.40],
            "high": [34.25, 34.45, 34.50, 34.40],
            "low": [34.05, 34.15, 34.30, 34.40],
            "close": [34.20, 34.35, 34.40, 34.40],
            "volume": [0.0, 0.0, 0.0, 0.0],
        },
        index=idx_utc,
    )

    gunluk = resample_ohlcv(df_1h, "1d")
    assert str(gunluk.index.tz) == str(idx_utc.tz)
    assert len(gunluk) == 1  # Cumartesi tek-bar düz taşma atıldı
    tek = gunluk.iloc[0]
    assert float(tek["open"]) == pytest.approx(34.10)
    assert float(tek["high"]) == pytest.approx(34.50)
    assert float(tek["low"]) == pytest.approx(34.05)
    assert float(tek["close"]) == pytest.approx(34.40)


def test_gunluk_bolunme_normalize_et_bedelsizi_olcekler_taban_serisine_dokunmaz():
    idx = pd.date_range("2026-09-01", periods=10, freq="1B", tz=ISTANBUL_TZ)
    # 1:4 bölünme (100 -> 25, tek adımda %75 düşüş ve kalıcı)
    fiyat_bolunme = [96.0, 98.0, 100.0, 102.0, 100.0, 25.0, 25.4, 24.8, 25.2, 25.6]
    df_bolunme = pd.DataFrame(
        {
            "open": [p * 0.99 for p in fiyat_bolunme],
            "high": [p * 1.02 for p in fiyat_bolunme],
            "low": [p * 0.98 for p in fiyat_bolunme],
            "close": fiyat_bolunme,
            "volume": [1_000_000.0] * len(fiyat_bolunme),
        },
        index=idx,
    )
    norm_df, duzeltilen = gunluk_bolunme_normalize_et(df_bolunme)
    assert duzeltilen == 1
    # Gece aşırı bölünme oranı yeni günün açılışı / önceki kapanış (24.75 / 100 = 0.2475):
    assert float(norm_df["close"].iloc[4]) == pytest.approx(24.75, rel=1e-3)
    assert float(norm_df["high"].max()) < 27.0

    # Gece aşırı BIST bölünmesi sureklilik_sorunlari_bul tarafından da tespit edilmeli:
    kayitlar = [
        {
            "timestamp": ts,
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": float(r.volume),
        }
        for ts, r in df_bolunme.iterrows()
    ]
    sorunlar = sureklilik_sorunlari_bul(kayitlar)
    assert any(s["tip"] == "split" for s in sorunlar)

    # Ardışık -%9.9 taban serisi (HEDEF benzeri) bölünme DEĞİLDİR; ölçeklenmemeli:
    fiyat_taban = [100.0]
    for _ in range(9):
        fiyat_taban.append(round(fiyat_taban[-1] * 0.901, 4))
    df_taban = pd.DataFrame(
        {
            "open": fiyat_taban,
            "high": [p * 1.01 for p in fiyat_taban],
            "low": [p * 0.99 for p in fiyat_taban],
            "close": fiyat_taban,
            "volume": [500_000.0] * len(fiyat_taban),
        },
        index=idx,
    )
    norm_taban, duzeltilen_taban = gunluk_bolunme_normalize_et(df_taban)
    assert duzeltilen_taban == 0
    assert float(norm_taban["close"].iloc[0]) == pytest.approx(100.0)


def test_cerceve_getir_xagusd_uzlasma_duz_mumlarini_1h_ile_onarir_ve_1d_png_duz_cizgi_olmaz(tmp_path: Path):
    yonetici = StockDequeManager(data_dir=str(tmp_path))

    # 120 iş günü 1D XAGUSD: son 3 mum Yahoo vadeli uzlaşma düz çizgisi (O=H=L=C)
    gunler = pd.date_range("2026-05-11", periods=120, freq="1B", tz=ISTANBUL_TZ)
    baz = 55.0 + 2.5 * np.sin(np.linspace(0.0, 5.0 * np.pi, 120))
    df_1d = pd.DataFrame(
        {
            "open": baz - 0.3,
            "high": baz + 0.7,
            "low": baz - 0.6,
            "close": baz + 0.1,
            "volume": [10_000.0] * 120,
        },
        index=gunler,
    )
    for son_i in (-3, -2, -1):
        uzlasma = float(baz[son_i])
        for alan in ("open", "high", "low", "close"):
            df_1d.iloc[son_i, df_1d.columns.get_loc(alan)] = uzlasma
    assert yonetici.append_gunluk_dataframe("XAGUSD", df_1d)
    yonetici.save_gunluk_to_disk("XAGUSD", persist_remote=False)

    # Son 45 iş günü için 1H mumları (hem son 3 düz uzlaşma gününü onarır hem 4H Stabil'i besler)
    saatler = []
    for g in gunler[-45:]:
        for s in (9, 13, 17, 21):
            saatler.append(g.replace(hour=s, minute=0))
    idx_1h = pd.DatetimeIndex(saatler)
    baz_1h = np.linspace(54.0, 58.4, len(idx_1h))
    df_1h = pd.DataFrame(
        {
            "open": baz_1h - 0.25,
            "high": baz_1h + 0.65,
            "low": baz_1h - 0.55,
            "close": baz_1h + 0.15,
            "volume": [2_500.0] * len(idx_1h),
        },
        index=idx_1h,
    )
    assert yonetici.append_dataframe("XAGUSD", df_1h)
    yonetici.save_to_disk("XAGUSD", persist_remote=False)

    onarilmis_1d, _ = grafik_uret.cerceve_getir("XAGUSD", "1d", str(tmp_path), yonetici=yonetici)
    son_uc_aralik = (onarilmis_1d["high"].iloc[-3:] - onarilmis_1d["low"].iloc[-3:]).to_numpy()
    assert (son_uc_aralik > 0.8).all()

    png_yolu = tmp_path / "xagusd_1d.png"
    uret = grafik_uret.kare_uret(
        "XAGUSD",
        "1d",
        veri_dizin=str(tmp_path),
        cikti=str(png_yolu),
        yonetici=yonetici,
        zone=True,
        simdi=ISTANBUL_TZ.localize(datetime(2026, 11, 2, 12, 0)),
    )
    assert Path(uret["yol"]).exists()
    assert Path(uret["yol"]).stat().st_size > 15_000

    # BIST sembolünde (AKBNK) izole veri_dizin ile kare_uret(zone=True) Stabil basamak çizgisini de üretmeli:
    gunler_bist = pd.date_range("2025-10-20", periods=260, freq="1B", tz=ISTANBUL_TZ)
    baz_bist = 55.0 + 4.0 * np.sin(np.linspace(0.0, 8.0 * np.pi, 260)) + np.linspace(0.0, 6.0, 260)
    df_bist_1d = pd.DataFrame(
        {
            "open": baz_bist - 0.3,
            "high": baz_bist + 0.8,
            "low": baz_bist - 0.7,
            "close": baz_bist + 0.2,
            "volume": [1_500_000.0] * 260,
        },
        index=gunler_bist,
    )
    saatler_bist = [g.replace(hour=s, minute=30) for g in gunler_bist[-45:] for s in (9, 11, 13, 15, 17)]
    b_1h = np.linspace(float(baz_bist[-45]), float(baz_bist[-1]), len(saatler_bist))
    df_bist_1h = pd.DataFrame(
        {
            "open": b_1h - 0.2,
            "high": b_1h + 0.5,
            "low": b_1h - 0.4,
            "close": b_1h + 0.1,
            "volume": [250_000.0] * len(saatler_bist),
        },
        index=pd.DatetimeIndex(saatler_bist),
    )
    assert yonetici.append_gunluk_dataframe("AKBNK", df_bist_1d)
    assert yonetici.append_dataframe("AKBNK", df_bist_1h)
    uret_bist = grafik_uret.kare_uret(
        "AKBNK",
        "1d",
        veri_dizin=str(tmp_path),
        cikti=str(tmp_path / "akbnk_1d.png"),
        yonetici=yonetici,
        zone=True,
        simdi=ISTANBUL_TZ.localize(datetime(2026, 11, 2, 12, 0)),
    )
    assert (uret_bist["meta"].get("cizgiler") or {}).get("stabil", {}).get("gorunur_bar", 0) > 0


def test_odak_gorunumunde_uzak_dis_seviye_y_eksenini_sisirip_mumlari_duz_cizgi_yapmaz(tmp_path: Path):
    import grafik

    n = 40
    baz = [25.0 + 0.25 * np.sin(i / 3.0) for i in range(n)]
    zamanlar = list(pd.date_range("2026-09-01", periods=n, freq="1B", tz=ISTANBUL_TZ))
    goruntu = {
        "hisse": "SKBNK",
        "tf": "1d",
        "gorunum": {"mod": "odak"},
        "zamanlar": zamanlar,
        "acilis": [v - 0.15 for v in baz],
        "yuksek": [v + 0.35 for v in baz],
        "dusuk": [v - 0.30 for v in baz],
        "kapanis": [v + 0.10 for v in baz],
        "hacim": [1_000_000.0] * n,
        "olay": {
            "olaylar": [],
            "swinglar": [{"bar": 5, "yon": "ust", "sinif": "SH", "durum": "teyitli", "fiyat": 420.0}],
            "seviyeler": [{"ad": "WH", "fiyat": 420.0, "stil": "kesikli"}],
            "kritik": {},
        },
    }
    png_yolu = tmp_path / "skbnk_odak.png"
    yol, meta = grafik.ciz(goruntu, "1d", {"cikti": str(png_yolu)})
    assert yol
    alt, ust = meta["kare"]["y_araligi"]
    assert ust < 30.0
    assert alt > 22.0


def test_gece_0200_mum_temizligi_supabase_kayitsiz_calisir_ve_kirik_mumlari_temizler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import main as main_mod
    from domain_engines import runner as domain_runner

    assert config.NIGHTLY_CANDLE_REFRESH_HOUR == 2
    assert config.NIGHTLY_CANDLE_REFRESH_MINUTE == 0

    yasak_store = _YasakSupabaseStore()
    yonetici = StockDequeManager(data_dir=str(tmp_path), persistent_store=yasak_store)

    # AKBNK başlangıçta eksik 1H (yalnız 20 bar) ve düz mumlarla kirlenmiş 1D içeriyor.
    kirli_1h_idx = pd.date_range("2026-10-20 10:00", periods=20, freq="1h", tz=ISTANBUL_TZ)
    kirli_1h = pd.DataFrame(
        {
            "open": [50.0] * 20,
            "high": [50.5] * 20,
            "low": [49.5] * 20,
            "close": [50.2] * 20,
            "volume": [100_000.0] * 20,
        },
        index=kirli_1h_idx,
    )
    yonetici.append_dataframe("AKBNK", kirli_1h)

    kirli_1d_idx = pd.date_range("2026-05-01", periods=110, freq="1B", tz=ISTANBUL_TZ)
    kirli_1d = pd.DataFrame(
        {
            "open": [50.0] * 110,
            "high": [50.0 if i >= 100 else 51.0 for i in range(110)],
            "low": [50.0 if i >= 100 else 49.0 for i in range(110)],
            "close": [50.0] * 110,
            "volume": [200_000.0] * 110,
        },
        index=kirli_1d_idx,
    )
    yonetici.append_gunluk_dataframe("AKBNK", kirli_1d)

    # GARAN mevcut sağlam veriye sahip; gece çekiminde geçici hata alırsa korunmalı.
    saglam_1h_idx = pd.date_range("2026-09-15 10:00", periods=120, freq="1h", tz=ISTANBUL_TZ)
    saglam_1h = pd.DataFrame(
        {
            "open": np.linspace(100.0, 110.0, 120),
            "high": np.linspace(100.8, 110.8, 120),
            "low": np.linspace(99.4, 109.4, 120),
            "close": np.linspace(100.3, 110.3, 120),
            "volume": [250_000.0] * 120,
        },
        index=saglam_1h_idx,
    )
    saglam_1d_idx = pd.date_range("2025-11-03", periods=220, freq="1B", tz=ISTANBUL_TZ)
    saglam_1d = pd.DataFrame(
        {
            "open": np.linspace(80.0, 110.0, 220),
            "high": np.linspace(81.0, 111.0, 220),
            "low": np.linspace(79.0, 109.0, 220),
            "close": np.linspace(80.5, 110.5, 220),
            "volume": [1_500_000.0] * 220,
        },
        index=saglam_1d_idx,
    )
    yonetici.append_dataframe("GARAN", saglam_1h)
    yonetici.append_gunluk_dataframe("GARAN", saglam_1d)

    ilk_denetim = yonetici.denetle_mum_butunlugu(["AKBNK", "GARAN"])
    assert "AKBNK" in ilk_denetim["eksik_1h"]
    assert "AKBNK" in ilk_denetim["duz_mum_1d"]
    assert "GARAN" not in ilk_denetim["sorunlu_semboller"]

    # Taze, eksiksiz AKBNK 1H ve 1D verisi; GARAN için geçici ağ hatası simülasyonu.
    taze_akbnk_1h = saglam_1h.copy()
    taze_akbnk_1d = saglam_1d.copy()

    def sahte_fetch_1h_paced(stocks, pacer, phase, periods=None):
        return {"AKBNK": taze_akbnk_1h}, {"GARAN": "timeout"}, 1, 0

    def sahte_fetch_1d(stock):
        if stock == "AKBNK":
            return taze_akbnk_1d
        return None

    monkeypatch.setattr(main_mod, "fetch_1h_stocks_paced", sahte_fetch_1h_paced)
    monkeypatch.setattr(main_mod, "fetch_yfinance_1d", sahte_fetch_1d)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))

    # Sahte artımlı OB/FVG durumu koyalım; AKBNK yenilenince temizlenmeli, GARAN kalmalı.
    domain_runner._incremental_states_by_series[("AKBNK", "4h")] = {"order_block": MagicMock()}
    domain_runner._incremental_states_by_series[("GARAN", "4h")] = {"order_block": MagicMock()}

    sahte_pacer = MagicMock()
    sahte_pacer.request.return_value.__enter__.return_value = None
    sahte_pacer.request.return_value.__exit__.return_value = False

    ozet = main_mod.gece_mum_temizligi_ve_yenileme(
        yonetici,
        sahte_pacer,
        stocks=["AKBNK", "GARAN"],
    )

    assert ozet["supabase_yazimi"] == 0
    assert ozet["yenilenen_1h"] == 1
    assert ozet["yenilenen_1d"] == 1
    assert ozet["korunan_1h"] == 1
    assert ozet["korunan_1d"] == 1
    assert ozet["sonraki_denetim"]["sorunlu_sembol_sayisi"] == 0

    # AKBNK tamamen taze veriyle değişti, eski kirli 2026-10-20 barları ve düz mumlar silindi:
    yeni_akbnk_1h = yonetici.to_dataframe("AKBNK")
    yeni_akbnk_1d = yonetici.to_gunluk_dataframe("AKBNK")
    assert yeni_akbnk_1h is not None and len(yeni_akbnk_1h) == 120
    assert yeni_akbnk_1d is not None and len(yeni_akbnk_1d) == 220
    assert (tmp_path / "AKBNK.json").exists()
    assert (tmp_path / "AKBNK_gunluk.json").exists()

    # GARAN geçici hataya rağmen silinmedi:
    assert len(yonetici.to_dataframe("GARAN")) == 120
    assert len(yonetici.to_gunluk_dataframe("GARAN")) == 220

    # Artımlı domain durumları yalnız yenilenen sembol için sıfırlandı:
    assert ("AKBNK", "4h") not in domain_runner._incremental_states_by_series
    assert ("GARAN", "4h") in domain_runner._incremental_states_by_series
    domain_runner.reset_incremental_domain_states()

    # Yerel 02:00 gün damgası yazılıp okunabilmeli (yine Supabase'siz):
    bugun = datetime(2026, 11, 2).date()
    main_mod._gece_mum_yenileme_son_gun_kaydet(bugun)
    assert main_mod._gece_mum_yenileme_son_gun_oku() == bugun


def test_stabil_komutu_bolunme_normalize_ve_now_tutarliligi(tmp_path):
    """`/stabil` önbellek okuyucusu bölünmüş 1D seriyi normalize etmeli ve `now` kesimine uymalıdır."""
    from bot.stabil_service import _symbol_frames_from_cache

    yonetici = StockDequeManager(data_dir=str(tmp_path), persistent_store=None)
    idx = pd.bdate_range("2025-11-03", periods=120, tz=ISTANBUL_TZ)
    fiyatlar = np.full(120, 50.0, dtype=float)
    fiyatlar[70:] = 10.0  # 5:1 bedelsiz bölünme
    df_1d = pd.DataFrame(
        {
            "open": fiyatlar * 0.995,
            "high": fiyatlar * 1.015,
            "low": fiyatlar * 0.985,
            "close": fiyatlar,
            "volume": np.full(120, 500_000.0),
        },
        index=idx,
    )
    assert yonetici.replace_gunluk_dataframe("SKBNK", df_1d)

    kesim = idx[99].to_pydatetime().replace(hour=19, minute=0)
    _, okunan_1d = _symbol_frames_from_cache("SKBNK", yonetici, kesim)
    assert okunan_1d is not None
    # `now` kesimi sonrası 20 bar dışarıda kalmalı:
    assert len(okunan_1d) == 100
    # Bölünme öncesi 50 TL barları ~10 TL ölçeğine indirilmiş olmalı:
    assert float(okunan_1d["high"].max()) < 12.0


def test_stabil_dm_hatasinda_kapali_public_mock_true_yutmaz(monkeypatch):
    """DM açık ama public kapalıyken DM ağ hatası olursa sinyal sahte True ile yutulmamalı."""
    import bot.stabil_service as st_srv

    class SahteBildirici:
        enabled = True
        public_enabled = False

        def send_text(self, _text):
            return False

        def send_to_public(self, _text):
            # Gerçek TelegramNotifier.send_to_public public_enabled=False iken True döner
            return True

    monkeypatch.setattr(config, "STABIL_ALARM_DM", True)
    monkeypatch.setattr(config, "STABIL_ALARM_PUBLIC", True)
    assert st_srv._deliver_stabil_message(SahteBildirici(), "deneme") is False


def test_stabil_son_mumda_destek_yoksa_sag_eksen_cipi_basmaz(tmp_path, monkeypatch):
    """Destek geçmişte kalıp son mumlarda None olduysa sağ eksende aktif `Destek` çipi çıkmamalı."""
    import grafik

    yakalanan_adaylar = []
    orijinal_sag_ciz = grafik._sag_ciz

    def izleyen_sag_ciz(ax, fig, adaylar, *args, **kwargs):
        yakalanan_adaylar.clear()
        yakalanan_adaylar.extend(dict(a) for a in adaylar)
        return orijinal_sag_ciz(ax, fig, adaylar, *args, **kwargs)

    monkeypatch.setattr(grafik, "_sag_ciz", izleyen_sag_ciz)

    n = 60
    zamanlar = pd.bdate_range("2026-06-01", periods=n, tz=ISTANBUL_TZ)
    kapanis = [100.0 + np.sin(i / 4.0) * 2.0 for i in range(n)]
    seviyeler = [98.5 if i < 40 else None for i in range(n)]
    renkler = ["ust" if i < 40 else None for i in range(n)]
    goruntu = {
        "sembol": "AKBNK",
        "tf": "1d",
        "zamanlar": list(zamanlar),
        "acilis": [c - 0.3 for c in kapanis],
        "yuksek": [c + 0.8 for c in kapanis],
        "dusuk": [c - 0.8 for c in kapanis],
        "kapanis": kapanis,
        "hacim": [1_000_000.0] * n,
        "stabil": {
            "hazir": True,
            "seviyeler": seviyeler,
            "renkler": renkler,
            "reclaim_barlar": [],
        },
    }
    hedef = tmp_path / "stabil_kirik_son.png"
    yol, meta = grafik.ciz(goruntu, "1d", secenekler={"cikti": str(hedef)})
    assert yol is not None and hedef.exists()
    assert meta["cizgiler"]["stabil"]["cizildi"] is True
    assert not any("Destek" in str(a.get("metin", "")) for a in yakalanan_adaylar)

    # Son mumda aktif destek varsa sağ eksen adaylarında `Destek` çipi yer almalı:
    goruntu_aktif = dict(goruntu)
    goruntu_aktif["stabil"] = {
        "hazir": True,
        "seviyeler": [98.5] * n,
        "renkler": ["ust"] * n,
        "reclaim_barlar": [],
    }
    hedef_aktif = tmp_path / "stabil_aktif_son.png"
    yol2, _ = grafik.ciz(goruntu_aktif, "1d", secenekler={"cikti": str(hedef_aktif)})
    assert yol2 is not None and hedef_aktif.exists()
    assert any("Destek" in str(a.get("metin", "")) for a in yakalanan_adaylar)


def test_yuzde_elli_bedelsiz_arti_iki_tavan_normalize_edilir():
    """%50 bedelsiz (0.667x) sonrası 2 tavan (+%10, +%10 -> 0.807x) olsa da bölünme yakalanmalı."""
    idx = pd.bdate_range("2026-01-05", periods=40, tz=ISTANBUL_TZ)
    c = np.full(40, 30.0, dtype=float)
    o = np.full(40, 30.0, dtype=float)
    # 20. barda %50 bedelsiz (30 -> 20), ardından 2 tavan (22 -> 24.2):
    o[20], c[20] = 20.0, 20.0
    o[21], c[21] = 20.2, 22.0
    o[22:], c[22:] = 22.2, 24.2
    df = pd.DataFrame(
        {"open": o, "high": np.maximum(o, c) * 1.01, "low": np.minimum(o, c) * 0.99, "close": c, "volume": 100_000.0},
        index=idx,
    )
    norm_df, adet = gunluk_bolunme_normalize_et(df)
    assert adet == 1
    assert abs(float(norm_df["close"].iloc[19]) - 20.0) < 1e-6

    # Buna karşılık ertesi gün eski fiyata (30.0) dönen tek günlük sahte iğne bölünme sayılmamalı:
    c2 = np.full(40, 30.0, dtype=float)
    o2 = np.full(40, 30.0, dtype=float)
    o2[20], c2[20] = 18.0, 18.0
    df_sahte = pd.DataFrame(
        {"open": o2, "high": np.maximum(o2, c2) * 1.01, "low": np.minimum(o2, c2) * 0.99, "close": c2, "volume": 100_000.0},
        index=idx,
    )
    _, adet_sahte = gunluk_bolunme_normalize_et(df_sahte)
    assert adet_sahte == 0

