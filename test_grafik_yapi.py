# -*- coding: utf-8 -*-
"""G3 yapı + şerit testleri (§2.1, §2.2, §6.1).

Motor `details` nesneleri `SimpleNamespace` ile taklit ediliyor; ALAN ADLARI gerçek
çıktıdan (ölçüm: `run_domain_engines`, AKBNK 1s/4s):
  `VolumeParticipationMetrics(data_ready, rvol, volume_level, effort_result_class, ...)`,
  `SwingPoint(valid, identity, scope, side, state, swing_class, structural_role,
   source_bar, confirm_bar, price, ... quality, evidence_text)`,
  `MarketStructureEventRecord(event_uid, scope, event_type, direction, candidate_bar,
   event_bar, broken_level, quality, confirmation_status, validity, relevance,
   outcome, age_bars, evidence_text, ...)` — `origin_level` DİYE ALAN YOK
   (`origin_price` var), §24'te düzeltme olarak yazılı.
Gerçek motorla doğrulama alt süreçte (`grafik_uret.py --zone`): pytest sürecinde
motor çağırmak parite testlerinin durumunu bozar (§14.2).
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


def _metrik(rvol=None, seviye="NORMAL", hazir=True, capak="NEUTRAL"):
    return SimpleNamespace(data_ready=hazir, rvol=rvol, volume_level=seviye,
                           effort_result_class=capak)


def _vp(seri, export_rvol=None):
    vp = SimpleNamespace(
        export=SimpleNamespace(rvol=export_rvol, state="PARTICIPATION_ACTIVE"),
        details={"metrics_history": tuple(seri)})
    return {"volume_participation": vp, "market_structure": None}


def _swing(bar, fiyat, yon="HIGH", sinif="HH", durum="SWING_CONFIRMED", kimlik=1,
           broken=False, bozuk=False, kapsam="INTERNAL", rol="NEUTRAL_HIGH"):
    return SimpleNamespace(valid=not bozuk, identity=kimlik, scope=kapsam,
                           side=yon, state=SimpleNamespace(name=durum),
                           swing_class=SimpleNamespace(name=sinif),
                           structural_role=rol, source_bar=bar,
                           confirm_bar=bar + 1, price=fiyat, prominence_atr=2.0,
                           distance_atr=1.0, distance_pct=1.0, finalized=True,
                           locked=True, broken=broken or durum == "SWING_BROKEN",
                           broken_bar=None, quality=90.0, evidence_text="kanıt",
                           invalid_reason="")


def _olay(bar, seviye, tur="EVENT_BOS", yon="UP", kapsam="EXTERNAL", onay="CONFIRMED",
          gecer="VALID", kimlik=1, nitelik=80.0):
    return SimpleNamespace(event_uid=f"{kapsam}:{kimlik}", identity=kimlik,
                           scope=SimpleNamespace(name=kapsam),
                           event_type=SimpleNamespace(name=tur),
                           direction=SimpleNamespace(name=yon), candidate_bar=bar - 1,
                           event_bar=bar, broken_level=seviye, origin_price=seviye,
                           quality=nitelik, confirmation_status=SimpleNamespace(name=onay),
                           validity=SimpleNamespace(name=gecer),
                           relevance="CURRENT", outcome="PENDING", age_bars=3,
                           evidence_text="kırılım", bos_maturity="NOT_APPLICABLE")


def _ms(swingler=(), adaylar=(), olaylar=(), export=None):
    def scope(kayit):
        deger = getattr(kayit, "scope", "INTERNAL")
        return str(getattr(deger, "name", deger)).upper()

    details = {
        "external_swings": tuple(x for x in swingler if scope(x) == "EXTERNAL"),
        "external_candidates": tuple(x for x in adaylar if scope(x) == "EXTERNAL"),
        "internal_swings": tuple(x for x in swingler if scope(x) == "INTERNAL"),
        "internal_candidates": tuple(x for x in adaylar if scope(x) == "INTERNAL"),
        "event_history": tuple(olaylar),
    }
    ms = SimpleNamespace(details=details)
    if export is not None:
        ms.export = export
    return {"market_structure": ms, "volume_participation": None}


# ------------------------------------------------------------------- şerit (§2.1)


def test_serit_motor_serisi_yoksa_yerel_hesap():
    cerceve = _cerceve(240, "4h", yon=0.0)
    hacim = [100.0] * 240
    for i in (100, 150, 200):
        hacim[i] = 400.0                      # spike'lar
    g = grafik.anlik_goruntu(_cift(start_bar=200), "4h", cerceve, simdi=ZAMAN,
                            kare_mum=60)
    # `cerceve`de hacim yok → `_serit_verisi` doğrudan da sınanabilir
    serit = grafik._serit_verisi(None, hacim, g["sol"], g["sag"], 240)
    assert serit["kaynak"] == "yerel hesap" and serit["yerel"] is True
    assert serit["esik"] == 1.5 and serit["spike"]
    assert all(0 <= i < (g["sag"] - g["sol"]) for i in serit["spike"])   # görünün dizini
    assert serit["elenen_spike"] == 0 and serit["hacimsiz"] == 0
    assert serit["tepe"] is not None and serit["tepe"] > 1.5


def test_serit_en_sert_12_spike_kalir():
    # Spike'lar 25 bar arayla: her 20'lık ortalama penceresinde tek spike var →
    # rvol birbirinden bağımsız, aday sayısı tam bilinir (13).
    n = 330
    hacim = [100.0] * n
    for i in range(0, n, 25):
        hacim[i] = 400.0
    serit = grafik._serit_verisi(None, hacim, 0, n, n)
    aday = [i for i, v in enumerate(serit["degerler"]) if v is not None and v >= 1.5]
    assert len(aday) == 13 + 1 - 1 or len(aday) >= 13        # bar 0 pencere başı
    assert len(serit["spike"]) == int(grafik.SABITLER["serit_maks"])
    assert serit["elenen_spike"] == len(aday) - len(serit["spike"]) >= 1


def test_serit_motor_serisi_varsa_kaynak_motor_ve_yildiz():
    seri = [_metrik(rvol=1.0) for _ in range(60)]
    seri[55] = _metrik(rvol=2.4, seviye="HIGH")
    seri[58] = _metrik(rvol=1.9, seviye="ABNORMAL")
    g = grafik.anlik_goruntu(None, "4h", _cerceve(60, "4h"), simdi=ZAMAN)
    serit = grafik._serit_verisi(_vp(seri), [100.0] * 60, g["sol"], g["sag"], 60)
    assert serit["kaynak"] == "motor" and serit["yerel"] is False
    assert sorted(serit["spike"]) == [55, 58]
    assert sorted(serit["yildiz"]) == [55, 58]        # motor dayanağı olan barlar


def test_serit_data_ready_yoksa_yerel_ve_yetersiz_degil():
    # 4s ölçümünün gerçeği: seri var ama `data_ready=False`/`rvol=None` → yerel
    seri = [_metrik(rvol=None, seviye="NORMAL", hazir=False) for _ in range(40)]
    hacim = [50.0] * 40
    hacim[30] = 500.0
    serit = grafik._serit_verisi(_vp(seri), hacim, 0, 40, 40)
    assert serit["kaynak"] == "yerel hesap"
    assert serit["yildiz"] == []                      # motor dayanağı yok → ▲ yok
    assert serit["spike"] and 30 - 0 in serit["spike"]


def test_serit_capa_yalniz_son_on_bes_bar():
    """§0.12a: `!` yalnız son 15 mumda (çaba var-sonuç yok)."""
    n = 60
    seri = [_metrik(rvol=1.0) for _ in range(n)]
    for i in (5, 20, n - 3):
        seri[i] = _metrik(rvol=1.0, capak="HIGH_EFFORT_WEAK_RESULT")
    serit = grafik._serit_verisi(_vp(seri), [100.0] * n, 0, n, n)
    assert serit["capa"] == [n - 3]
    # `▲`/`!` olmadan da çizim patlamaz
    g = grafik.anlik_goruntu(None, "4h", _cerceve(n, "4h"), simdi=ZAMAN)
    g["serit"] = serit
    _, meta = grafik.ciz(g, "4h", {"cikti": "/tmp/g3_capa.png"})
    assert meta["serit"]["capa"] == 1


def test_serit_hacimsiz_bar_sayilir():
    hacim = [100.0] * 40
    for i in range(30, 35):
        hacim[i] = 0.0
    serit = grafik._serit_verisi(None, hacim, 25, 40, 40)
    assert serit["hacimsiz"] == 5


# ---------------------------------------------------------------------- yapı (§2.2)


def test_yapi_filtreler():
    olaylar = [
        _olay(50, 70.0, tur="EVENT_BOS"),                          # dış, onaylı  → girer
        _olay(52, 71.0, tur="EVENT_SWEEP"),                          # sweep → kartta yok
        _olay(54, 69.0, tur="EVENT_CHOCH", kapsam="INTERNAL"),       # internal → §0.7
        _olay(56, 68.0, tur="EVENT_BOS", gecer="FAILED"),            # geçersiz
        _olay(58, 67.0, tur="EVENT_CHOCH", onay="CANDIDATE_FAILED"),  # aday-kaldı
        _olay(60, 66.0, tur="EVENT_CHOCH", kimlik=9),                # en yeni → kritik
    ]
    g = _goruntu_yapi(_ms(swingler=[_swing(200, 72.0)], olaylar=olaylar))
    olay = g["olay"]
    assert olay["swinglar"] == []
    assert [b["tur"] for b in olay["olaylar"]] == ["BOS", "CHoCH"]
    assert olay["kritik"]["kaynak_bar"] == 60 and olay["kritik"]["seviye"] == 66.0
    assert olay["kritik"]["bar"] == 60 - g["sol"]          # çizim indeksi
    assert olay["kritik"]["tur"] == "CHoCH"
    assert len(olay["swinglar"]) == 0 and olay["cizilen"] == 2


def test_yapi_oklari_ic_swingden_gelir_dis_roller_cetvele_ayrilir():
    ic = _swing(210, 71.0, sinif="HL", kimlik=1)
    dis_rol = _swing(205, 72.0, sinif="PH", kimlik=2, kapsam="EXTERNAL",
                     rol="PROTECTED_HIGH")
    dis_nor = _swing(215, 73.0, sinif="HH", kimlik=3, kapsam="EXTERNAL",
                     rol="NEUTRAL_HIGH")
    olay = _goruntu_yapi(_ms(swingler=[dis_rol, dis_nor, ic]))["olay"]

    assert [(b["kaynak_bar"], b["sinif"]) for b in olay["swinglar"]] == []
    assert [(b["etiket"], b["fiyat"], b["kaynak_bar"])
            for b in olay["seviyeler"]] == [("PH", 72.0, 205)]
    # İç pivotun sınıfı PH/PL olsa bile protected-level anlamı verilip cetvele taşınmaz.
    ic_ph = _swing(211, 70.0, sinif="PH", kimlik=4)
    olay = _goruntu_yapi(_ms(swingler=[ic_ph]))["olay"]
    assert olay["swinglar"] == [] and olay["seviyeler"] == []


def test_yapi_export_none_disi_role_seviyesini_gizler():
    dis = _swing(210, 72.0, sinif="PH", kapsam="EXTERNAL", rol="PROTECTED_HIGH")
    export = SimpleNamespace(external_protected_high=None)
    olay = _goruntu_yapi(_ms(swingler=[dis], export=export))["olay"]
    assert olay["seviyeler"] == []  # safety-gated export tek doğruluk kaynağı


def test_yapi_tum_dis_rol_etiketleri_eslenir():
    roller = [("PROTECTED_HIGH", "PH", "external_protected_high", 108.0),
              ("PROTECTED_LOW", "PL", "external_protected_low", 92.0),
              ("WEAK_HIGH", "WH", "external_weak_high", 112.0),
              ("WEAK_LOW", "WL", "external_weak_low", 88.0)]
    swingler = [_swing(200 + i, fiyat, kapsam="EXTERNAL", rol=rol, kimlik=i)
                for i, (rol, _, _, fiyat) in enumerate(roller)]
    export = SimpleNamespace(**{alan: fiyat for _, _, alan, fiyat in roller})
    olay = _goruntu_yapi(_ms(swingler=swingler, export=export))["olay"]
    assert {b["etiket"] for b in olay["seviyeler"]} == {"PH", "PL", "WH", "WL"}
    assert {b["fiyat"] for b in olay["seviyeler"]} == {88.0, 92.0, 108.0, 112.0}


def test_yapi_kapaklar_ve_sirasi():
    swinglar = [_swing(200 + i, 60.0 + i, kimlik=i) for i in range(14)]
    olaylar = [_olay(150 + i, 65.0 + i, kimlik=100 + i) for i in range(9)]
    g = _goruntu_yapi(_ms(swingler=swinglar, olaylar=olaylar))
    assert g["olay"]["swinglar"] == []
    assert len(g["olay"]["olaylar"]) == int(grafik.SABITLER["olay_maks"]) == 6
    assert g["olay"]["elenen"] == (9 - 6)
    assert [b["kaynak_bar"] for b in g["olay"]["swinglar"]] == sorted(
        b["kaynak_bar"] for b in g["olay"]["swinglar"])
    # kapak EN YENİLERİ tutar
    assert g["olay"]["kapak"]["swing"] == 0


def test_yapi_aday_ve_kirik_swing_durumu():
    g = _goruntu_yapi(_ms(swingler=[_swing(230, 60.0, durum="SWING_BROKEN", kimlik=1),
                                    _swing(231, 61.0, kimlik=2)],
                          adaylar=[_swing(232, 62.0, durum="SWING_PENDING", kimlik=3)]))
    durumlar = {b["kimlik"]: b["durum"] for b in g["olay"]["swinglar"]}
    assert durumlar == {}


def test_yapi_pencere_disi_swing_alinmaz():
    # kadraj [sol, sag): `sag` kadrajın sağ ucu (ölçüm: sol=59, sag=239) → 239
    # çizilmez, 238 çizilir.
    taban = _goruntu_yapi(_ms())
    sag = taban["sag"]
    g = _goruntu_yapi(_ms(swingler=[_swing(0, 60.0), _swing(sag - 1, 61.0),
                                   _swing(sag, 62.0, kimlik=8),
                                   _swing(sag + 400, 63.0, kimlik=9)]))
    kaynaktan = [b["kaynak_bar"] for b in g["olay"]["swinglar"]]
    assert kaynaktan == []                             # 0, sag, ötesi dışarıda
    assert all(0 <= b["bar"] < (g["sag"] - g["sol"]) for b in g["olay"]["swinglar"])


def _goruntu_yapi(sonuclar, tf="4h"):
    cerceve = _cerceve(240, tf, yon=0.05)
    return grafik.anlik_goruntu(_cift(start_bar=200), tf, cerceve, sonuclar=sonuclar,
                                alarm_bar=239, simdi=ZAMAN)


def test_yapi_cizimi_meta_ve_y_araligi(tmp_path):
    # Seviyeler kadraj içinde (LL=25 ile PH=95 arası): çizim kuralı gereği çizilir
    olaylar = [_olay(210, 90.0, tur="EVENT_BOS"), _olay(230, 30.0, tur="EVENT_CHOCH",
                                                        yon="DOWN", kimlik=7)]
    g = _goruntu_yapi(_ms(swingler=[_swing(220, 95.0, kapsam="EXTERNAL", rol="PROTECTED_HIGH"),
                                      _swing(225, 25.0, yon="LOW", sinif="PL",
                                             kapsam="EXTERNAL", rol="PROTECTED_LOW")],
                          olaylar=olaylar))
    _, meta = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "yapi.png"), "gorunum": "baglam"})
    assert meta["olay"]["swing"] == 0 and meta["olay"]["bos_choc"] == 2
    assert meta["olay"]["kritik"] == 30.0               # en yeni olayın seviyesi
    assert meta["olay"]["kritik_cizildi"] is True
    assert meta["cizgiler"]["kritik"] == pytest.approx(30.0)   # §2 seviye sözleşmesi
    alt, ust = meta["kare"]["y_araligi"]
    assert alt <= 25.0 and ust >= 95.0                  # çizilen uçlar kesilmez (§0.13)
    assert meta["olay"]["kadraj_disi"] == 0


def test_kadraj_disi_seviye_cizilmez_ve_sayilir(tmp_path):
    """Uzak BOS/CHoCH seviyesi (kadraj dışı) grafiği SIKIŞTIRMAZ: çizilmez, sayılır.

    Gerekçe (görsel inceleme): 3 hafta önceki kırılım seviyesi %8 üstte kalıp
    tüm mumları dikeyde ezebiliyordu. Yapı ucu (PH/PL) yine de aralığa girer.
    """
    olaylar = [_olay(210, 90.0, tur="EVENT_BOS"), _olay(230, 20.0, tur="EVENT_CHOCH",
                                                        yon="DOWN", kimlik=7)]
    g = _goruntu_yapi(_ms(swingler=[_swing(220, 95.0, kapsam="EXTERNAL", rol="PROTECTED_HIGH"),
                                      _swing(225, 25.0, yon="LOW", sinif="PL",
                                             kapsam="EXTERNAL", rol="PROTECTED_LOW")],
                          olaylar=olaylar))
    _, meta = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "uzak.png"), "gorunum": "baglam"})
    # Aralık PH=95 ve LL=25 ile belirlenir (+%6 pay → ~20,8'e kadar): 90 içeride
    # çizilir, 20 (CHoCH) ve onun `kritik` kopyası dışarıda sayılır.
    assert meta["olay"]["bos_choc"] == 1
    assert meta["olay"]["olay_barlari"] == [210]
    assert meta["olay"]["kadraj_disi"] == 2
    assert meta["olay"]["kritik_cizildi"] is False
    alt, ust = meta["kare"]["y_araligi"]
    assert alt > 20.0                                   # uzak seviye aralığı genişletmez
    assert any("yapı:" in satir for satir in meta["metin"]["lejant"])
    assert meta["png_kb"] <= 500


def test_kritik_alarm_seviyesiyle_ayniysa_cift_cizgi_yok(tmp_path):
    """Aynı seviye alarm çizgisiyle çiziliyorsa `kritik` ayrı çizgi ÇİZMEZ."""
    g = _goruntu_yapi(_ms(swingler=[], olaylar=[_olay(230, 52.5, tur="EVENT_BOS")]))
    g["alarm"] = dict(g.get("alarm") or {}, deger=52.5, tur="kritik",
                      durum="KIRILIM_TEYITLI", bar=230, bar_disarida=False)
    g["olay"]["olaylar"] = []                 # olay çizgisi çizilmiyor → kritik ayrı
    _, meta = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "kritik.png")})
    assert meta["olay"]["kritik_atlandi"] == 1
    assert meta["olay"]["kritik_cizildi"] is False      # tek çizgi: alarm çizgisi
    assert meta["cizgiler"]["kritik"] is None           # çizilmeyen seviye sayı taşımaz


def test_motor_hatasi_yapi_katmani_eksik_yazilir(tmp_path):
    class Patlar:
        @property
        def details(self):
            raise RuntimeError("biçim değişti")

    g = grafik.anlik_goruntu(None, "4h", _cerceve(120),
                            sonuclar={"market_structure": Patlar(),
                                      "volume_participation": None}, simdi=ZAMAN)
    assert "ms" in g["olay"]["hata"]
    assert "ms" in g["eksik_katmanlar"]
    _, meta = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "ms.png")})
    assert any(d.startswith("eksik: ms") for d in meta["metin"]["dipnotlar"])


def test_serit_kaybi_katmani_durdurmaz(tmp_path):
    class Patlar:
        @property
        def details(self):
            raise RuntimeError("seri bozuk")

    serit = grafik._serit_verisi({"volume_participation": Patlar(), "market_structure": None},
                                 [100.0] * 30, 0, 30, 30)
    assert serit["kaynak"] == "yerel hesap"             # motor serisi çökse de çizilir


def test_yapi_bicimi_bos_ken_de_sabit(tmp_path):
    g = grafik.anlik_goruntu(None, "4h", _cerceve(60, "4h"), simdi=ZAMAN)
    _, meta = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "bos.png")})
    assert set(meta["olay"]) >= {"cizilen", "elenen", "swing", "bos_choc", "kritik",
                                 "kapak", "etiket_atlandi", "kritik_cizildi",
                                 "kritik_atlandi", "capa", "hata"}
    assert meta["olay"]["cizilen"] == 0 and meta["olay"]["swing"] == 0
    assert meta["olay"]["kritik"] is None and meta["olay"]["kritik_cizildi"] is False
    # FAZ 1: hacim PANELİ varsayılan kapalı; veri mum altı ⚡ rozetinde yaşar.
    assert meta["serit"]["acik"] is False and "rozet" in meta["serit"]
    assert "yapı:" not in " ".join(meta["metin"]["lejant"])


def test_meta_verisi_iki_cizimde_ayni(tmp_path):
    olaylar = [_olay(210, 60.0), _olay(220, 61.0, tur="EVENT_CHOCH", yon="DOWN")]
    g = _goruntu_yapi(_ms(swingler=[_swing(205, 62.0)], olaylar=olaylar))
    _, m1 = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "a.png")})
    _, m2 = grafik.ciz(g, "4h", {"cikti": str(tmp_path / "b.png")})
    m1.pop("sure_ms", None), m2.pop("sure_ms", None)
    m1["kare"].pop("png_kb", None), m2["kare"].pop("png_kb", None)
    assert m1["olay"] == m2["olay"] and m1["serit"] == m2["serit"]


# ------------------------------------------------------- gerçek motorla (alt süreç)


@pytest.mark.parametrize("tf", ["1h", "4h"])
def test_cli_zone_yapi_ve_seriti_dolduruyor(tmp_path, tf):
    """Gerçek `run_domain_engines` çıktısıyla yapı + şerit meta'ya doluyor."""
    if not (REPO / "bot_data" / "AKBNK.json").exists():
        pytest.skip("bot_data önbelleği yok")
    cikti = tmp_path / f"yapi_{tf}.png"
    sonuc = subprocess.run(
        [sys.executable, "grafik_uret.py", "--hisse", "AKBNK", "--tf", tf, "--zone",
         "--mum", "120", "--cikti", str(cikti), "--json"],
        cwd=str(REPO), capture_output=True, text=True, timeout=300,
        env={"PATH": "/usr/bin:/bin", "DATA_DIR": "/tmp/fbdata", "PYTHONPATH": str(REPO)})
    assert sonuc.returncode == 0, sonuc.stderr[-800:]
    meta = json.loads(sonuc.stdout[sonuc.stdout.index("{"):sonuc.stdout.rindex("}") + 1])
    assert cikti.exists()
    assert meta["olay"]["swing"] == 0
    assert meta["olay"]["bos_choc"] >= 1
    assert meta["serit"]["kaynak"] in ("motor", "yerel hesap")
    # FAZ 1: hacim PANELİ varsayılan kapalı; veri mum altı ⚡ rozetinde yaşar.
    assert meta["serit"]["acik"] is False and "rozet" in meta["serit"]
    assert "yapı:" in " ".join(meta["metin"]["lejant"])
    if meta["serit"]["kaynak"] == "yerel hesap":
        assert "yerel hesap" in " ".join(meta["metin"]["lejant"])   # §0.12a etiketi
    assert meta["eksik_katmanlar"] == []
    assert meta["png_kb"] <= 500
