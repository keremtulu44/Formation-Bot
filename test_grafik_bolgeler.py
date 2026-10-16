# -*- coding: utf-8 -*-
"""G2 bölge testleri — OB/FVG/engulfing kutuları (§3, §6.1, §6.2).

Motor `details` kayıtlarının ALAN ADLARI burada `types.SimpleNamespace` ile
taklit ediliyor; alan adları koddan doğrulandı:
  `OrderBlockRecord(source_index, source_time, top, bottom, bullish, base_score,
   anchor_high, anchor_low, imbalance_end_index, fill_boundary)` (domain_engines/
   order_block), `OrderBlockSideExport(state, top, bottom, fill, source_bar)`,
  `FvgLifecycleRecord(direction, state, lower_boundary, upper_boundary, gap_size,
   formation_index, formation_time, quality, maximum_fill_ratio, ...)` ve
`EngulfingLifecycleRecord(lower_boundary, upper_boundary, formation_low/high,
   formation_index, state, quality ...)`; OB çizimi için `active_records`
(`domain_engines/` — yalnız şema doğrulama, motor değişikliği yok).
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


def _ob(index, alt, ust, bullish=True, skor=2, dolan=0.0):
    """Sentetik `OrderBlockRecord` — `fill_boundary` motorla AYNI kural:

    `order_block_engine` kaydı `fill_boundary=top if bullish else bottom` ile açar
    ve fiyat kutunun içine girdikçe sınırı taşır. `dolan` oranı bu yüzden
    sınırdan hesaplanır (FAZ 3 §A: `mitigated_percentage` bu alandan türetilir).
    """
    yuk = float(ust) - float(alt)
    sinir = (float(ust) - yuk * float(dolan)) if bullish else (float(alt) + yuk * float(dolan))
    return SimpleNamespace(source_index=index, source_time=None, top=ust, bottom=alt,
                           bullish=bullish, base_score=skor, anchor_high=ust,
                           anchor_low=alt, imbalance_end_index=None, fill_boundary=sinir)


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


def test_aktif_fvg_yakin_ob_kutulari_tarafindan_kapatilmaz():
    oblar = [_ob(30, 61.0, 62.0), _ob(31, 61.2, 62.2)]
    fvg = _fvg(25, 64.0, 65.0, durum="ACTIVE")
    cerceve = _cerceve(60, "4h", taban=60.0, yon=0.0)
    g = grafik.anlik_goruntu(None, "4h", cerceve,
                            sonuclar=_sonuclar(ob_kayitlari=oblar, fvg_kayitlari=[fvg]),
                            simdi=ZAMAN)
    secilen = g["zone"]["cizilen"]
    assert sum(b["tip"] == "fvg" for b in secilen) == 1
    assert sum(b["tip"] == "ob" for b in secilen) == 1
    assert g["zone"]["elenen"] == 1


def test_esitlikte_daha_yeni_kaynak_kazanir():
    ayni = [_ob(10, 70.0, 71.0, bullish=False), _ob(40, 70.0, 71.0, bullish=False)]
    cerceve = _cerceve(60, "1d", taban=60.0, yon=0.0)
    g = grafik.anlik_goruntu(None, "1d", cerceve, sonuclar=_sonuclar(ob_kayitlari=ayni),
                            simdi=ZAMAN)
    secilen = g["zone"]["cizilen"]
    assert len(secilen) == 1 and secilen[0]["kaynak"] == 40      # §0.8 eşitlik kuralı


def test_ob_cizimi_active_records_kullanir_ve_tam_ayin_geometrisini_tekillestirir():
    pasif = _ob(10, 54.0, 55.0)
    aktif = _ob(20, 60.0, 61.0)
    ob = SimpleNamespace(export=None, details={"records": [pasif, aktif],
                                                "active_records": [aktif, aktif]})
    cerceve = _cerceve(60, "4h", taban=60.0, yon=0.0)
    g = grafik.anlik_goruntu(None, "4h", cerceve, sonuclar={"order_block": ob}, simdi=ZAMAN)
    zone = g["zone"]
    assert [(b["kaynak"], b["alt"], b["ust"]) for b in zone["cizilen"]] == [(20, 60.0, 61.0)]
    assert zone["cikarim"]["ob_source"] == "active_records"
    assert zone["cikarim"]["duplicates_removed"] == 1


def test_ob_legacy_fallback_only_when_active_records_field_missing():
    ob = _ob(20, 60.0, 61.0)
    cerceve = _cerceve(60, "4h", taban=60.0, yon=0.0)
    eski = SimpleNamespace(export=None, details={"records": [ob]})
    g = grafik.anlik_goruntu(None, "4h", cerceve, sonuclar={"order_block": eski}, simdi=ZAMAN)
    assert len(g["zone"]["cizilen"]) == 1
    assert g["zone"]["cikarim"]["ob_source"] == "records_legacy"

    bos_aktif = SimpleNamespace(export=None, details={"records": [ob], "active_records": []})
    g = grafik.anlik_goruntu(None, "4h", cerceve,
                            sonuclar={"order_block": bos_aktif}, simdi=ZAMAN)
    assert g["zone"]["cizilen"] == []  # alan var ama boşsa records'tan diriltilmez
    assert g["zone"]["cikarim"]["ob_source"] == "active_records"


def test_fvg_lifecycle_kaydi_raw_listeden_ustundur_ve_doluluk_orani_dogrudur():
    aktif = SimpleNamespace(
        direction=SimpleNamespace(value=1), state=SimpleNamespace(name="ACTIVE"),
        lower_boundary=64.0, upper_boundary=66.0, formation_index=24,
        formation_time=ZAMAN, quality=83.0, gap_size=2.0,
        maximum_fill_ratio=0.42, close_fill_ratio=0.0,
    )
    # Ham kayıt kasıtlı olarak başka fiyat/indekste: lifecycle varsa çizilmemeli.
    raw = _fvg(35, 60.1, 60.5, doluluk=0.95)
    fvg = SimpleNamespace(details={
        "fvg_formations": [raw], "active_bullish_fvg": aktif,
        "active_bearish_fvg": None, "completed_fvg": (),
        "engulfing_formations": [],
    })
    cerceve = _cerceve(60, "4h", taban=60.0, yon=0.0)
    g = grafik.anlik_goruntu(None, "4h", cerceve, sonuclar={"fvg": fvg}, simdi=ZAMAN)
    fvg_bolgeleri = [b for b in g["zone"]["cizilen"] if b["tip"] == "fvg"]
    assert len(fvg_bolgeleri) == 1
    assert (fvg_bolgeleri[0]["kaynak"], fvg_bolgeleri[0]["alt"],
            fvg_bolgeleri[0]["ust"]) == (24, 64.0, 66.0)
    assert fvg_bolgeleri[0]["doluluk"] == pytest.approx(0.42)
    assert fvg_bolgeleri[0]["kayit_kaynagi"] == "active_lifecycle"
    assert g["zone"]["cikarim"]["fvg_source"] == "lifecycle"
    assert g["zone"]["cikarim"]["fvg_raw"] == 0


def test_aktif_engulfing_grafige_alinmaz():
    aktif = SimpleNamespace(
        direction=SimpleNamespace(value=-1), state=SimpleNamespace(name="ACTIVE"),
        lower_boundary=55.0, upper_boundary=56.0, formation_index=30,
        formation_low=50.0, formation_high=61.0, formation_time=ZAMAN, quality=72.0,
    )
    fvg = SimpleNamespace(details={
        "engulfing_formations": [], "active_bullish_engulfing": None,
        "active_bearish_engulfing": aktif, "completed_engulfing": (),
    })
    cerceve = _cerceve(60, "4h", taban=60.0, yon=0.0)
    g = grafik.anlik_goruntu(None, "4h", cerceve, sonuclar={"fvg": fvg}, simdi=ZAMAN)
    assert not any(b["tip"] == "eng" for b in g["zone"]["cizilen"])
    assert g["zone"]["cikarim"]["eng"] == 0


def test_tamamlanmis_engulfing_grafige_alinmaz():
    tamamlanmis = SimpleNamespace(
        direction=SimpleNamespace(value=1), state=SimpleNamespace(name="CONTINUATION_CONFIRMED"),
        lower_boundary=416.0, upper_boundary=420.75, formation_index=106,
        formation_low=415.0, formation_high=433.5, formation_time=ZAMAN, quality=97.5,
    )
    fvg = SimpleNamespace(details={
        "engulfing_formations": [], "active_bullish_engulfing": None,
        "active_bearish_engulfing": None, "completed_engulfing": [tamamlanmis],
    })
    cerceve = _cerceve(60, "4h", taban=60.0, yon=0.0)
    g = grafik.anlik_goruntu(None, "4h", cerceve, sonuclar={"fvg": fvg}, simdi=ZAMAN)
    assert not any(b["tip"] == "eng" for b in g["zone"]["cizilen"])
    assert g["zone"]["cikarim"]["eng_completed"] == 0


def test_engulf_raw_fallback_grafige_alinmaz():
    raw = SimpleNamespace(
        direction=SimpleNamespace(value=-1), state=SimpleNamespace(name="ACTIVE"),
        formation_index=29, formation_time=ZAMAN, formation_low=50.0, formation_high=61.0,
        lower_boundary=55.0, upper_boundary=56.0, quality=68.0,
    )
    cerceve = _cerceve(60, "4h", taban=60.0, yon=0.0)
    g = grafik.anlik_goruntu(None, "4h", cerceve,
                            sonuclar=_sonuclar(eng_kayitlari=[raw]), simdi=ZAMAN)
    assert not any(b["tip"] == "eng" for b in g["zone"]["cizilen"])
    assert g["zone"]["cikarim"]["eng_raw"] == 0


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


def test_doluluk_motor_kaynagindan_gelir_uydurulmaz():
    """§0.12k + FAZ 3 §A: doluluk ÖNCE export'un `fill`i, sonra kaydın kendi
    `fill_boundary`si olur; her ikisi de motordan gelir (uydurma oran yok)."""
    export = SimpleNamespace(
        bull=SimpleNamespace(source_bar=11, fill=0.4285, top=62.5, bottom=61.5, state=1.0),
        bear=SimpleNamespace(source_bar=None, fill=None, top=None, bottom=None, state=None))
    # 11: export fill'i var (0,4285) · 12: export yok, kayıt taze (boundary = top)
    # 13: export yok, ayı kaydı %40 dolu (fill_boundary = bottom + %40 × yük);
    # kapanış 60'ın ALTINDA olduğu için "alt" taraf seçimine girer (kapak 2/2).
    ob_kayitlari = [_ob(11, 61.5, 62.5), _ob(12, 63.0, 64.0),
                    _ob(13, 56.0, 57.0, bullish=False, dolan=0.4)]
    cerceve = _cerceve(60, "4h", taban=60.0, yon=0.0)
    g = grafik.anlik_goruntu(None, "4h", cerceve,
                            sonuclar=_sonuclar(ob_kayitlari=ob_kayitlari, export=export),
                            simdi=ZAMAN)
    kayitlar = {b["kaynak"]: b for b in g["zone"]["cizilen"]}
    assert kayitlar[11]["doluluk"] == pytest.approx(0.4285)
    assert kayitlar[11]["mitigated_percentage"] == pytest.approx(42.9, abs=0.05)
    assert kayitlar[12]["doluluk"] == pytest.approx(0.0)          # taze: %0
    assert kayitlar[13]["doluluk"] == pytest.approx(0.4)
    assert kayitlar[13]["mitigated_percentage"] == pytest.approx(40.0, abs=0.1)
    assert g["zone"]["hata"] == []


def test_mitigated_yuzdesi_motorun_formuluyle_ayni():
    """FAZ 3 §A: `(top - boundary)/yük` (boğa) ve `(boundary - bottom)/yük` (ayı)."""
    assert grafik._ob_mitigated(_ob(1, 100.0, 110.0, dolan=0.25), 100.0, 110.0) == 25.0
    assert grafik._ob_mitigated(_ob(2, 100.0, 110.0, bullish=False, dolan=0.6),
                                100.0, 110.0) == 60.0
    # boundary yok → oran da yok (uydurulmaz), kutu tek parça çizilir
    bos = SimpleNamespace(source_index=3, top=110.0, bottom=100.0, bullish=True)
    assert grafik._ob_mitigated(bos, 100.0, 110.0) is None


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
    _, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / "kaynak.png"), "gorunum": "baglam"})
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
    yol, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / "zone.png"), "gorunum": "baglam"})
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
    _, meta = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "capisma.png"), "gorunum": "baglam"})
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
    _, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / "zmeta.png"), "gorunum": "baglam"})
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
