# -*- coding: utf-8 -*-
"""Görsel düzeltme regresyonları (mum genişliği, çift hacim notu, formasyon taraması).

Kök nedenler:
  * `_kare_ciz` mum gövde genişliğini `px_bar × 0,62` (piksel) olarak veri
    birimine (bar indeksi) veriyordu → gövdeler 3,7–5,6 bar genişliğinde çizilip
    komşularının üstüne biniyordu. Gövde genişliği artık bar aralığının 0,62'si.
  * Hacimsiz bar uyarısı hem kırmızı dipnotta hem gri notta basılıyordu.
  * CLI formasyonu hiç bulmuyordu (`--formasyon` yoksa bant çizilmiyordu);
    `--formasyon-tara` botun canlı tarama kapısını kullanır.

Testler bot_data/ önbelleğine YAZMAZ; yalnız okur.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

import grafik
import grafik_uret

IST = timezone(timedelta(hours=3))


def _mum_listesi(n: int, tf: str = "1h"):
    """Düz sentetik seri: her mum 1 birim yukarı; sıfır hacimli 3 bar içerir."""
    import pandas as pd

    zamanlar = [datetime(2026, 9, 1, 9, 30, tzinfo=IST) + timedelta(hours=i) for i in range(n)]
    satirlar = []
    fiyat = 50.0
    for i in range(n):
        a = fiyat
        k = fiyat + (0.6 if i % 2 == 0 else -0.6)
        satirlar.append({"open": a, "high": max(a, k) + 0.3, "low": min(a, k) - 0.3,
                         "close": k, "volume": 0.0 if i in (5, 6, 7) else 1000.0 + i})
        fiyat = k
    return pd.DataFrame(satirlar, index=pd.DatetimeIndex(zamanlar, name="timestamp"))


def test_govde_genisligi_veri_birimi_bar_araligi_orani():
    """Gövde genişliği 0,62 bar; piksel değeri veri birimine SIZMAZ."""
    ax = mock.MagicMock()
    grafik._mumlar_ciz(ax, [1.0, 2.0], [2.0, 3.0], [0.5, 1.5], [2.0, 1.0],
                       grafik.SABITLER["mum_genislik_orani"], (0.0, 5.0))
    genislikler = [c.kwargs["width"] for c in ax.bar.call_args_list]
    assert genislikler, "gövde çizilmedi"
    assert all(abs(w - 0.62) < 1e-9 for w in genislikler)
    # fitil sabit kalınlıkta, gövdeye bağlı değil
    fitil = [c.kwargs["linewidth"] for c in ax.plot.call_args_list]
    assert fitil and all(abs(x - grafik.SABITLER["fitil_pt"]) < 1e-9 for x in fitil)


@pytest.mark.parametrize("n", [60, 180, 360])
def test_kare_ciz_govde_genisligi_kare_olcusunden_bagimsiz(tmp_path, n):
    """Asıl regresyon: `_kare_ciz` gövde genişliğini px/bar'dan türetmemeli.

    Eski kodda `cap = px_bar × 0,62` idi (n=180'de 3,7; n=60'ta 11,1 bar).
    Çizim fonksiyonu dinlenir; her kare boyutunda 0,62 beklenir.
    """
    df = _mum_listesi(n)
    goruntu = grafik.anlik_goruntu(None, "1h", df, sembol="TEST")
    gorulen = []
    orijinal = grafik._mumlar_ciz

    def dinle(ax, acilis, yuksek, dusuk, kapanis, cap, aralik):
        gorulen.append(cap)
        return orijinal(ax, acilis, yuksek, dusuk, kapanis, cap, aralik)

    with mock.patch.object(grafik, "_mumlar_ciz", side_effect=dinle):
        yol, meta = grafik.ciz(goruntu, "1h", {"cikti": str(tmp_path / f"t{n}.png")})
    assert yol is not None
    assert gorulen and all(abs(c - 0.62) < 1e-9 for c in gorulen), gorulen


def test_hacimsiz_uyari_tek_kez_basilir():
    """Aynı sayı (hacimsiz) dipnotta ve notta ikinci kez yazılmaz."""
    goruntu = {
        "sembol": "TEST", "tf": "1h", "tf_kisa": "1s", "son_bar_ts": None, "son_kapanis": 1.0,
        "formasyon": {}, "alarm": {}, "budama": [], "uyarilar": [], "notlar": [],
        "zone": {}, "serit": {"hacimsiz": 3, "yetersiz": False, "degerler": []},
        "olay": {}, "yapı_satırı": "",
    }
    meta = {"mum_sayisi": 10, "hacimsiz_bar": 3}
    metin = grafik._metinler(goruntu, meta, 1080, [], False)
    tum = metin["dipnotlar"] + metin["notlar"]
    sayim = sum(1 for satir in tum if "bar hacimsiz" in satir)
    assert sayim == 1, tum


def test_formasyon_tara_bulunamazsa_uydurma_yok():
    """Kullanılabilir formasyon yoksa bant/işaret yok, uyarı açık yazılır."""
    df = _mum_listesi(60)
    aday, uyari = grafik_uret._formasyon_tara(df)
    assert aday is None
    assert uyari and "kullanılabilir formasyon yok" in uyari[0]


def test_formasyon_tara_canli_kapi_ile_ALARK_4s():
    """Botun canlı kapısı ALARK 4s'de formasyon bulur; CLI aynı adayı verir."""
    df, _kaynak = grafik_uret.cerceve_getir("ALARK", "4h", "bot_data")
    from data import tamamlanmis_mumlar

    df = tamamlanmis_mumlar(df, "4h").copy(deep=True)
    aday, uyari = grafik_uret._formasyon_tara(df)
    assert aday is not None and not uyari
    assert getattr(aday, "pattern_type", "") == "Alçalan Üçgen"
    assert aday.start_bar is not None and 0 <= aday.start_bar < len(df)


def test_xauusd_retest_grafikte_bant_ve_durum_ile_gosterilir(monkeypatch, tmp_path):
    """Sahte snapshot sadece çizim köprüsünü sınar; gerçek TV verisi değildir."""
    from types import SimpleNamespace
    import patterns.lifecycle as lifecycle_module
    from patterns.candidate import PatternCandidate
    from patterns.mathutil import f_line_price

    frame = _mum_listesi(100)
    upper, lower = (10, 54., 60, 51.), (10, 48., 60, 48.5)
    aday = PatternCandidate(valid=True, family="Üçgen", pattern_type="Alçalan Üçgen",
                            start_bar=10, end_bar=60, hb1=upper[0], hp1=upper[1],
                            hb2=upper[2], hp2=upper[3], lb1=lower[0], lp1=lower[1],
                            lb2=lower[2], lp2=lower[3],
                            upper_now=f_line_price(*upper, 99),
                            lower_now=f_line_price(*lower, 99),
                            quality_frozen=True, frozen_raw_quality=89.4)
    class Motor:
        def __init__(self, *_args, **_kwargs): pass
        def process(self, _df):
            return SimpleNamespace(active=aday, state="RETEST_BEKLENIYOR",
                                   effective_quality=89.4)
    monkeypatch.setattr(lifecycle_module, "ArgentEngine", Motor)
    monkeypatch.setattr(grafik_uret, "cerceve_getir", lambda *_a, **_k: (frame, "test"))
    sonuc = grafik_uret.kare_uret("XAUUSD", "1d", formasyon_tara=True,
                                cikti=str(tmp_path / "retest.png"))
    assert sonuc["yol"]
    assert sonuc["meta"]["formasyon_ad"] == "Alçalan Üçgen"
    assert sonuc["meta"]["formasyon_durum"] == "RETEST_BEKLENIYOR"
    assert sonuc["meta"]["cizgiler"]["formasyon"]["bar"] > 0


def test_xauusd_tamamlanan_formasyon_grafikte_kalir(monkeypatch, tmp_path):
    """Canlı alarm snapshot'ı gizlese de Pine tamamlanan yapıyı çizer."""
    import pandas as pd
    from patterns.lifecycle import ArgentEngine

    df = pd.read_csv("capraz_piyasa_data/XAUUSD_1d.csv.gz")
    df["bar_time"] = pd.to_datetime(df["bar_time"], utc=True)
    df = df.set_index("bar_time").tail(500)
    motor = ArgentEngine("Dengeli", timeframe="1d")
    snap = motor.process(df)
    assert snap.state == "FORMASYON_TAMAMLANDI"
    assert snap.active is None  # eski tamamlanma, alarm için gizli kalır
    assert motor.active.valid
    aday, durum, uyarilar = grafik_uret._formasyon_tara_ayrintili(df, tf="1d")
    assert not uyarilar
    assert durum == "FORMASYON_TAMAMLANDI"
    assert aday.pattern_type == motor.active.pattern_type
    assert aday.hb1 == motor.active.hb1 and aday.lb2 == motor.active.lb2
    assert aday.effective_quality == pytest.approx(motor.active.frozen_raw_quality)
    goruntu = grafik.anlik_goruntu(aday, "1d", df, sembol="XAUUSD")
    assert goruntu["formasyon"]["hb1"] == motor.active.hb1
    monkeypatch.setattr(grafik_uret, "cerceve_getir", lambda *_a, **_k: (df, "arşiv"))
    sonuc = grafik_uret.kare_uret("XAUUSD", "1d", formasyon_tara=True,
                                cikti=str(tmp_path / "xauusd.png"))
    assert sonuc["yol"] and sonuc["meta"]["formasyon_ad"] == aday.pattern_type
    assert sonuc["meta"]["formasyon_durum"] == "FORMASYON_TAMAMLANDI"
    assert sonuc["meta"]["cizgiler"]["formasyon"]["bar"] > 0


@pytest.mark.parametrize("state", ["FORMASYON_GECERSIZ", "BASARISIZ_KIRILIM", "KIRILIM_TEYIT_ALAMADI"])
@pytest.mark.parametrize("age,visible", [(3, True), (4, True), (5, False)])
def test_formasyon_hayaleti_dort_bar_ile_sinirli(monkeypatch, state, age, visible):
    from types import SimpleNamespace
    import patterns.lifecycle as lifecycle_module
    from patterns.candidate import PatternCandidate

    aday = PatternCandidate(valid=True, family="Üçgen", pattern_type="Yükselen Üçgen",
                            raw_quality=45.0)
    class Motor:
        def __init__(self, *_args, **_kwargs):
            self.active = aday
            self.bar_index = 20
            self.pattern_state_bar = 20 - age
        def process(self, _df):
            # Snapshot politikasından bağımsız 4. barda da çizim yapılmalı.
            return SimpleNamespace(active=aday if age <= 3 else None, state=state,
                                   effective_quality=45.0 if age <= 3 else None)
    monkeypatch.setattr(lifecycle_module, "ArgentEngine", Motor)
    sonuc, durum, _ = grafik_uret._formasyon_tara_ayrintili(_mum_listesi(60), tf="1h")
    assert (sonuc is not None) is visible
    assert durum == (state if visible else None)


def test_formasyon_tara_cli_png_uretir(tmp_path):
    """`--formasyon-tara` ile CLI gerçek önbellekten PNG üretir (exit 0)."""
    cikti = tmp_path / "alark_4h.png"
    kod = grafik_uret.main(["--hisse", "ALARK", "--tf", "4h", "--zone", "--formasyon-tara",
                            "--veri-dizin", "bot_data", "--cikti", str(cikti)])
    assert kod == 0
    assert cikti.exists() and cikti.stat().st_size > 1000


def test_grafik_hisse_formasyon_rozetinde_kalite_puani_gorunur():
    """`/grafik hisse` yolu (`_formasyon_tara_ayrintili`) üst rozette `kalite XX/100` taşır."""
    df, _kaynak = grafik_uret.cerceve_getir("ALARK", "4h", "bot_data")
    from data import tamamlanmis_mumlar

    df = tamamlanmis_mumlar(df, "4h").copy(deep=True)
    aday, durum, uyari = grafik_uret._formasyon_tara_ayrintili(df, tf="4h")
    assert aday is not None and not uyari
    assert getattr(aday, "effective_quality", None) is not None
    goruntu = grafik.anlik_goruntu(aday, "4h", df, sembol="ALARK")
    if durum and isinstance(goruntu.get("formasyon"), dict):
        goruntu["formasyon"]["state"] = durum
    metin = grafik._metinler(goruntu, {"mum_sayisi": goruntu["bar_sayisi"]}, 1280, [], False)
    rozet_metinleri = [p["metin"] for p in metin["pill_listesi"]]
    assert any("kalite " in m and "/100" in m for m in rozet_metinleri), rozet_metinleri

