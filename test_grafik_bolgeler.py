# -*- coding: utf-8 -*-
"""G2 bölge testleri — OB/FVG/engulfing kutuları (§3, §6.1, §6.2).

Motor `details` kayıtlarının ALAN ADLARI burada `types.SimpleNamespace` ile
taklit ediliyor; alan adları koddan doğrulandı:
  `OrderBlockRecord(source_index, source_time, top, bottom, bullish, base_score,
   anchor_high, anchor_low, imbalance_end_index, fill_boundary)` (domain_engines/
   order_block), `OrderBlockSideExport(state, top, bottom, fill, source_bar)`,
  `FvgLifecycleRecord(direction, state, lower_boundary, upper_boundary, gap_size,
   gap_atr, formation_atr, formation_index, formation_time, quality,
   close_fill_ratio, ...)` ve `EngulfingLifecycleRecord(... formation_low/high,
   formation_index, state, quality ...)` (domain_engines/fvg/fvg_engulfing_final.py).
Motoru ÇAĞIRAN tek test alt süreçte (`grafik_uret.py --zone`) çalışır:
`_advance_incremental_engine` sembol+TF durumunu ilerlettiği için pytest sürecinde
motor çağırmak parite testlerini bozar (§14.2).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import grafik
from test_grafik_iskelet import _cerceve, _cift

IST = timezone(timedelta(hours=3))
ZAMAN = datetime(2026, 12, 1, 9, 0, tzinfo=IST)
REPO = Path(__file__).resolve().parent


def _ob(index, alt, ust, bullish=True, skor=2):
    return SimpleNamespace(source_index=index, source_time=None, top=ust, bottom=alt,
                           bullish=bullish, base_score=skor, anchor_high=ust,
                           anchor_low=alt, imbalance_end_index=None, fill_boundary=alt)


def _fvg(index, alt, ust, direction=1, durum="ACTIVE", kalite=88.0, doluluk=0.0, gap=1.5):
    return SimpleNamespace(formation_index=index, formation_time=None, lower_boundary=alt,
                           upper_boundary=ust, direction=SimpleNamespace(value=direction),
                           state=SimpleNamespace(name=durum), gap_size=gap,
                           gap_atr=gap / 1.5, formation_atr=1.5, quality=kalite,
                           close_fill_ratio=doluluk)


def _eng(index, alt, ust, direction=1, durum="ACTIVE", kalite=70.0):
    return SimpleNamespace(formation_index=index, formation_time=None, formation_low=alt,
                           formation_high=ust, lower_boundary=alt, upper_boundary=ust,
                           direction=SimpleNamespace(value=direction),
                           state=SimpleNamespace(name=durum), quality=kalite)


def _sonuclar(ob_kayitlari=(), fvg_kayitlari=(), eng_kayitlari=(), export=None):
    ob = SimpleNamespace(export=export, details={"records": list(ob_kayitlari),
                                                 "active_records": list(ob_kayitlari)})
    fvg = SimpleNamespace(details={"fvg_formations": list(fvg_kayitlari),
                                   "engulfing_formations": list(eng_kayitlari)})
    return {"order_block": ob, "fvg": fvg}


# ------------------------------------------------------- havuz, sıralama, kapak


def test_havuz_tek_ve_kapak_tf_gore():
    # kapanış ~55: üst tarafta 5, alt tarafta 4 kutu (merkez mesafeleri artar)
    usttekiler = [_ob(10 + k, 58 + 5 * k, 60 + 5 * k, bullish=False) for k in range(1, 6)]
    alttakiler = [_ob(40 - k, 52 - 5 * k, 54 - 5 * k) for k in range(1, 5)]
    sonuclar = _sonuclar(ob_kayitlari=usttekiler + alttakiler)
    cerceve = _cerceve(80, "1h", taban=55.0, yon=0.0)
    g = grafik.anlik_goruntu(None, "1h", cerceve, sonuclar=sonuclar, simdi=ZAMAN)
    zone = g["zone"]
    assert zone["kapak"] == {"ust": 3, "alt": 3}
    assert len(zone["cizilen"]) == 6 and zone["elenen"] == 3
    taraflar = [b["taraf"] for b in zone["cizilen"]]
    assert taraflar.count("ust") == 3 and taraflar.count("alt") == 3
    # yakınlık sırası: her taraf kendi içinde en yakından başlar
    for taraf in ("ust", "alt"):
        mesafeler = [b["mesafe"] for b in zone["cizilen"] if b["taraf"] == taraf]
        assert mesafeler == sorted(mesafeler)
    # 4s 2+2, 1g 1+1 (§0.9)
    assert grafik._kapak_sayilari("4h") == {"ust": 2, "alt": 2}
    assert grafik._kapak_sayilari("1d") == {"ust": 1, "alt": 1}


def test_ob_ve_fvg_ayni_yarisi_kazaniyor():
    """Confluence birlikte değerlendirilir (§0.8): yakın FVG, uzak OB'yi iter."""
    sonuclar = _sonuclar(ob_kayitlari=[_ob(10, 66.0, 67.0, bullish=False)],
                         fvg_kayitlari=[_fvg(11, 61.5, 62.5)])
    cerceve = _cerceve(60, "4h", taban=60.0, yon=0.0)
    g = grafik.anlik_goruntu(None, "4h", cerceve, sonuclar=sonuclar, simdi=ZAMAN)
    tipler = [b["tip"] for b in g["zone"]["cizilen"]]
    assert tipler.count("fvg") == 1 and tipler.count("ob") == 1
    # kapanış 60'da: ikisi de "üst" taraf; kapak 2 → ikisi de sığar
    assert {b["taraf"] for b in g["zone"]["cizilen"]} == {"ust"}


def test_esitlikte_daha_yeni_kaynak_kazanir():
    ayni = [_ob(10, 70.0, 71.0, bullish=False), _ob(40, 70.0, 71.0, bullish=False)]
    cerceve = _cerceve(60, "1d", taban=60.0, yon=0.0)
    g = grafik.anlik_goruntu(None, "1d", cerceve, sonuclar=_sonuclar(ob_kayitlari=ayni),
                            simdi=ZAMAN)
    secilen = g["zone"]["cizilen"]
    assert len(secilen) == 1 and secilen[0]["kaynak"] == 40      # §0.8 eşitlik kuralı


def test_1s_ve_2s_karelerinde_fvg_cizilmez():
    """§0.12l: `1s`/`2s`de FVG çizilmez (motor da üretmiyor — kare yinede uydurmaz)."""
    cerceve = _cerceve(60, "1h", taban=60.0, yon=0.0)
    sonuclar = _sonuclar(fvg_kayitlari=[_fvg(11, 61.5, 62.5)])
    for tf in ("1h", "2h"):
        g = grafik.anlik_goruntu(None, tf, cerceve, sonuclar=sonuclar, simdi=ZAMAN)
        assert not g["zone"]["cizilen"]
        assert g["zone"]["cikarim"]["fvg_tf_yok"] == 1
    g4 = grafik.anlik_goruntu(None, "4h", cerceve, sonuclar=sonuclar, simdi=ZAMAN)
    assert len(g4["zone"]["cizilen"]) == 1


def test_doluluk_yalniz_motorun_verdigi_kutuda():
    """§0.12k: export'ta `fill` varsa yazılır; yoksa `%` UYDURULMAZ."""
    export = SimpleNamespace(
        bull=SimpleNamespace(source_bar=11, fill=0.4285, top=62.5, bottom=61.5, state=1.0),
        bear=SimpleNamespace(source_bar=None, fill=None, top=None, bottom=None, state=None))
    ob_kayitlari = [_ob(11, 61.5, 62.5), _ob(12, 63.0, 64.0)]
    cerceve = _cerceve(60, "4h", taban=60.0, yon=0.0)
    g = grafik.anlik_goruntu(None, "4h", cerceve,
                            sonuclar=_sonuclar(ob_kayitlari=ob_kayitlari, export=export),
                            simdi=ZAMAN)
    kayitlar = {b["kaynak"]: b for b in g["zone"]["cizilen"]}
    assert kayitlar[11]["doluluk"] == pytest.approx(0.4285)
    assert kayitlar[12]["doluluk"] is None
    assert g["zone"]["hata"] == []


# ------------------------------------------------------------------- hizalama


def test_kaynak_indeksi_mum_indeksine_denkler():
    """§6.2 regresyon: `source_index` resample edilmiş çerçeveyi indeksler (§1 kuralı)."""
    import pandas as pd
    from data import resample_ohlcv

    ham = _cerceve(180, "1h")
    df = pd.DataFrame({"high": ham["yuksek"], "low": ham["dusuk"], "close": ham["kapanis"],
                       "open": ham["acilis"], "volume": ham["hacim"]},
                      index=pd.DatetimeIndex(ham["zaman"], name="timestamp"))
    res = resample_ohlcv(df, "4h")
    kaynak = 3
    zaman_damgasi = res.index[kaynak]
    ob = SimpleNamespace(source_index=kaynak, source_time=zaman_damgasi, top=float(res["high"].iloc[kaynak]),
                         bottom=float(res["low"].iloc[kaynak]), bullish=True, base_score=1,
                         anchor_high=0.0, anchor_low=0.0, imbalance_end_index=None,
                         fill_boundary=0.0)
    g = grafik.anlik_goruntu(None, "4h", res, sonuclar=_sonuclar(ob_kayitlari=[ob]),
                             simdi=ZAMAN, kare_mum=180)
    kutu = g["zone"]["cizilen"][0]
    assert kutu["kaynak"] == kaynak
    assert g["zamanlar"][kutu["x0"]] == zaman_damgasi.to_pydatetime()
    assert kutu["x1"] == len(g["zamanlar"]) - 1          # kutu son muma kadar uzar
    assert kutu["vurgu"] == "alt"                          # §0.12r boğada alt kenar


def test_kadraj_disinda_baslayan_kutu_sol_kenardan_cizilir(tmp_path):
    cerceve = _cerceve(240, "1h", yon=0.02)
    g = _goruntu_zone(cerceve, [_ob(5, 55.0, 56.0)], tf="1h")
    kutu = g["zone"]["cizilen"][0]
    assert kutu["kaynak"] < g["sol"]
    assert kutu["x0"] == 0 and g["zone"]["kaynak_disi"] >= 1
    _, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / "kaynak.png")})
    assert any("kadraj dışında" in n for n in meta["metin"]["notlar"])


def _goruntu_zone(cerceve, ob_kayitlari, tf="1h", fvg_kayitlari=()):
    sonuclar = _sonuclar(ob_kayitlari=ob_kayitlari, fvg_kayitlari=list(fvg_kayitlari))
    return grafik.anlik_goruntu(_cift(start_bar=200), tf, cerceve, sonuclar=sonuclar,
                                alarm_bar=239, simdi=ZAMAN)


# ------------------------------------------------------------------ çizim/meta


def test_y_araligi_kutulari_icerir(tmp_path):
    """§0.13: hiçbir kutu kesilmez — yatay aralık bölge uçlarını da kapsar."""
    cerceve = _cerceve(240, "1h", yon=0.05)
    g = _goruntu_zone(cerceve, [_ob(200, 90.0, 95.0, bullish=False), _ob(210, 20.0, 25.0)])
    yol, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / "zone.png")})
    assert yol
    alt, ust = meta["kare"]["y_araligi"]
    assert alt <= 20.0 and ust >= 95.0
    assert meta["zone"]["cizilen"] >= 1 and meta["zone"]["tip"]["ob"] >= 1
    assert meta["png_kb"] <= 500


def test_bilinmeyen_durum_adi_dolgu_uydurmaz(tmp_path):
    cerceve = _cerceve(240, "1h", yon=0.05)
    # 4s kullanılıyor: 1s/2sde FVG zaten çizilmez (§0.12l) — testin konusu bu değil
    g = _goruntu_zone(cerceve, [_ob(205, 52.0, 53.5)], tf="4h",
                      fvg_kayitlari=[_fvg(210, 50.0, 51.0, durum="YENI_DURUM_X")])
    yol, meta = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "hatch.png")})
    assert yol and meta["eksik_katmanlar"] == []      # çizim sürer, katman düşmez
    assert meta["zone"]["tip"]["fvg"] == 1


def test_cakisan_etiket_kaydirilir_atlanmaz(tmp_path):
    """Aynı fiyat bandında iki kutu → iki etiket de sağ şeritte, dikeyde AYRIŞIK.

    Eski davranış (yazıyı atmak) bilgi kaybıydı; görsel incelemede kullanıcı
    \"yazı mumun üstüne biniyor\" dedi. Şimdi etiket kaydırılır, atılmaz.
    """
    cerceve = _cerceve(240, "4h", taban=60.0, yon=0.0)
    # Aynı bant, 1 bar arayla → yazılar zorunlu olarak üst üste biniyor
    g = _goruntu_zone(cerceve, [_ob(200, 59.0, 60.0), _ob(201, 59.2, 59.8)], tf="4h")
    assert len(g["zone"]["cizilen"]) == 2
    _, meta = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "capisma.png")})
    assert meta["zone"]["cizilen"] == 2               # kutular korunur
    assert meta["zone"]["etiket_atlandi"] == 0        # hiçbir etiket atılmaz
    assert meta["sag"]["yerlesen"] >= 2               # iki etiket de şeritte
    assert "zone" not in meta["eksik_katmanlar"]      # katman düşmez (§2.9)


def test_kutu_olsa_da_son_mum_gorunur_kalir(tmp_path):
    """Sağ nefes payı VERİYİ kırpmamalı: son mum eksen sınırının içinde (§0.13)."""
    cerceve = _cerceve(240, "1h", yon=0.05)
    g = _goruntu_zone(cerceve, [_ob(238, 55.0, 56.0, bullish=False),
                                _fvg(239, 50.0, 51.0)], tf="4h",
                      fvg_kayitlari=[_fvg(239, 50.0, 51.0)])
    _, meta = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "x.png")})
    sol, sag = meta["kare"]["x_siniri"]
    n = meta["mum_sayisi"]
    assert sol <= 0 and sag >= n - 0.4            # son bar kesilmez
    assert meta["zone"]["cizilen"] >= 1


def test_motor_hatasi_eksik_yazilir(tmp_path):
    class Patlar:
        @property
        def details(self):
            raise RuntimeError("motor biçimi değişti")

    g = grafik.anlik_goruntu(None, "1h", _cerceve(120),
                             sonuclar={"order_block": Patlar(), "fvg": None}, simdi=ZAMAN)
    assert "ob" in g["zone"]["hata"]
    assert "ob" in g["eksik_katmanlar"]
    yol, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / "hata.png")})
    assert yol and "ob" in meta["eksik_katmanlar"]
    assert any(d.startswith("eksik: ob") for d in meta["metin"]["dipnotlar"])


def test_meta_zone_alanlari_dolu(tmp_path):
    cerceve = _cerceve(240, "1h", yon=0.05)
    g = _goruntu_zone(cerceve, [_ob(201, 55.0, 56.0), _ob(202, 44.0, 45.0, bullish=False)],
                      tf="1h")
    _, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / "zmeta.png")})
    zone = meta["zone"]
    assert set(zone) >= {"cizilen", "elenen", "tip", "kaynak_disi", "kapak", "sirala",
                         "atr", "hata", "kayitlar"}
    assert zone["cizilen"] == 2 and isinstance(zone["kayitlar"][0]["mesafe"], float)
    assert zone["sirala"] in ("mesafe/ATR", "mesafe (ATR yok → ham fiyat)")
    assert "kutular" in meta["metin"]["lejant"][0] or any(
        "kutular" in satir for satir in meta["metin"]["lejant"])


def test_bolge_elenen_sayisi_not_olurak_yazilir(tmp_path):
    cerceve = _cerceve(240, "1d", yon=0.05, ilk=datetime(2026, 10, 5, 9, 30, tzinfo=IST))
    g = _goruntu_zone(cerceve, [_ob(200 + i, 55.0 + i, 56.0 + i, bullish=False) for i in range(4)],
                      tf="1d")
    assert g["zone"]["kapak"] == {"ust": 1, "alt": 1}
    assert g["zone"]["elenen"] == 3
    _, meta = grafik.ciz(g, "1d", {"cikti": str(tmp_path / "elenen.png")})
    assert any("kapak dışında" in n for n in meta["metin"]["notlar"])


# ------------------------------------------------------- gerçek motorla (alt süreç)


@pytest.mark.parametrize("tf", ["1h", "4h"])
def test_cli_zone_gercek_motor_alan_adlarini_dogruluyor(tmp_path, tf):
    """`bot_data` varsa CLI + gerçek `run_domain_engines` ile kare çizilir.

    Alt süreçte çalışıyor: motorlar sembol+TF durumunu ilerlettiği için pytest
    sürecinde çağrılmamalı (§14.2 / parite testleri).
    """
    if not (REPO / "bot_data" / "AKBNK.json").exists():
        pytest.skip("bot_data önbelleği yok")
    cikti = tmp_path / f"zone_{tf}.png"
    sonuc = subprocess.run(
        [sys.executable, "grafik_uret.py", "--hisse", "AKBNK", "--tf", tf, "--zone",
         "--mum", "120", "--cikti", str(cikti), "--json"],
        cwd=str(REPO), capture_output=True, text=True, timeout=300,
        env={"PATH": "/usr/bin:/bin", "DATA_DIR": "/tmp/fbdata",
             "PYTHONPATH": str(REPO)})
    assert sonuc.returncode == 0, sonuc.stderr[-800:]
    meta = json.loads(sonuc.stdout[sonuc.stdout.index("{"):sonuc.stdout.rindex("}") + 1])
    assert cikti.exists()
    assert meta["zone"]["sirala"] in ("mesafe/ATR", "mesafe (ATR yok → ham fiyat)")
    assert meta["zone"]["tip"]["ob"] >= 1
    if tf == "1h":
        assert meta["zone"]["tip"]["fvg"] == 0            # §0.12l motor da üretmiyor
    else:
        assert meta["eksik_katmanlar"] == []
