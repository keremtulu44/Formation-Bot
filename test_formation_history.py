"""Faz 2.0 / 2.1 / 2.2 — Field & Event Contract + History Registry testleri.

KAPSAM VE SINIRLAR (Faz 2 taahhüdü)
------------------------------------
Bu testler yalnız *history altyapısını* doğrular. Aşağıdakiler burada
DOKUNULMAZ ve testler mevcut haliyle kullanır:

  * formasyon matematiği, geometri, kalite eşikleri
  * `identity_compatible` / `continuity_score` (60 eşiği dahil)
  * lifecycle state makinesi ve geçişleri
  * `formation_identity.py` (Faz 1 anchor'ü) — geriye dönük uyumluluk
  * karne yazımı ve `sinyal_sonucu`

Senaryolar:
  S — Sözleşme      : 85 alanın tamamı sınıflandırılır, belirsiz kalmaz
  R — Registry      : yaz/oku, atomik yazma, bozuk dosya toleransı
  K — Kimlik        : sliding window'da stable_id korunur (temel kabul kriteri)
  Ç — Çoklu         : aynı pencerede iki formasyon ayrı kimlik alır
  Y — Yanlış eşleşme: farklı formation YENİ stable_id alır (mutasyonla kanıtlanır)
  T — Terminal      : terminal kimliği yeni formasyona ASLA taşınmaz
  O — Olay          : olaylar stable_id taşır, replay'de şişmez

Çalıştırma:  python3 -m pytest test_formation_history.py -q
"""

import json
import os
import uuid

import pandas as pd
import pytest

import patterns.lifecycle as L
from patterns.candidate import PatternCandidate
from patterns.lifecycle import PatternLifecycleManager, _new_stable_id, _parse_stock_tf
from state import formation_history as fh


def _gercek_motor(idx, key):
    """Fake motor yerine GERCEK ArgentEngine: `continuity_score`'un
    `min_touch_gap`/`pivot_len`/`safe_atr` gibi alanlara ihtiyaci vardir.
    Gercek motor kullanmak testin entegrasyonu dogru olcmesini saglar."""
    from patterns.lifecycle import ArgentEngine
    eng = ArgentEngine(profile="Dengeli")
    eng._key = key
    eng.index_values = idx
    eng.bar_index = len(idx) - 1
    return eng


def _coklu_formasyon(seedler=(21, 77, 133)):
    """Ust uste binen, farkli geometrili birkac formation (ayrik dogum barlari)."""
    parcalar = []
    for i, sd in enumerate(seedler):
        d = _kanalli_pennant(n_bars=48, upper_k=-0.06 - 0.02 * i,
                             lower_k=0.06 + 0.03 * i, seed=sd)
        d = d.copy()
        d.index = d.index + pd.Timedelta(hours=48 * i)
        parcalar.append(d)
    return pd.concat(parcalar)


def test_coklu_formasyon_kayan_pencerede_kimlik_korunur():
    """Ayni pencerede BIRDEN FAZLA canli formation varsa hepsi kimligini korur.

    Faz 1'in tek slot'lu anchor'u yalnizca TEK formasyonu takip edebilir;
    pencere kaydikca 2. formation yeni UUID aliyordu. Faz 2.1'in registry'si
    (stock,tf) basina birden fazla kayit tasidigi icin bu cozulur.

    Bu test, duzeltme geri alindiginda BASARISIZ olur (mutasyonla kanitlanmistir):
    registry kapaliyken kayit sayisi her pencerede 2 artar, acikken sabit kalir.
    """
    df = _coklu_formasyon()
    mgr = _mgr()
    key = "ASELS_1h"
    onceki, korunan = {}, 0
    for basla in range(0, 30, 10):
        pen = df.iloc[basla: basla + 140].copy()
        if len(pen) < 80:
            break
        mgr.scan(key, pen, tam_yeniden=True)
        simdi = _penceredeki_kimlikler(pen, "ASELS", "1h")
        for anahtar, sid in onceki.items():
            if anahtar in simdi:
                assert simdi[anahtar] == sid, (
                    "Coklu formasyonda kimlik kaybi (%s): %s -> %s"
                    % (anahtar, sid, simdi[anahtar]))
                korunan += 1
        if simdi:
            onceki = simdi
    assert len(onceki) >= 2, "Ayni pencerede 2+ formation bekleniyordu: %s" % onceki
    assert korunan >= 2, (
        "Kayan pencerede yalnizca %d kimlik korundu; Faz 1 tek slot'lu anchor'u "
        "yalnizca bir formasyonu korur" % korunan)


def test_kayan_pencerede_kayit_sayisi_kontrolsuz_artmaz():
    """Kayan pencerede defter kaydi kontrolsuz SEKILDE buyumemeli.

    Faz 1'de her pencere kaymasinda ayni fiziksel formation icin yeni kayit
    aciliyordu (2 -> 4 -> 6). Faz 2.1'de yalnizca yeniden siniflandirma
    (Flama -> Ucgen) bir ek kayit hakeder; o da bir kez olur.
    """
    df = _coklu_formasyon()
    mgr = _mgr()
    key = "GARAN_1h"
    sayilar = []
    for basla in range(0, 30, 10):
        pen = df.iloc[basla: basla + 140].copy()
        if len(pen) < 80:
            break
        mgr.scan(key, pen, tam_yeniden=True)
        defter = fh.yukle("GARAN", "1h")
        sayilar.append(len(fh.kayitlar(defter)))
    assert len(sayilar) >= 2, "Senaryo kurulamadi"
    artislar = [b - a for a, b in zip(sayilar, sayilar[1:])]
    assert all(a <= 1 for a in artislar), (
        "Defter her pencerede asiri buyudu: %s (artislar %s)" % (sayilar, artislar))

from state import formation_schema as fs


# --- sentetik veri üreticileri (test_stable_identity.py ile aynı yapı) -----

def _df_yap(close, start="2026-01-05 09:30", freq="h"):
    return pd.DataFrame(
        {"open": [c - 0.02 for c in close], "high": [c + 0.15 for c in close],
         "low": [c - 0.15 for c in close], "close": close,
         "volume": [3_000_000] * len(close)},
        index=pd.date_range(start=start, periods=len(close), freq=freq,
                            tz="Europe/Istanbul"))


def _kanalli_pennant(n_bars=48, upper_k=-0.06, lower_k=0.06, pole_bars=12,
                     asagi=False, seed=21):
    import numpy as np
    np.random.seed(seed)
    close = []
    for i in range(n_bars):
        if i <= 4:
            c = 92.0
        elif i == 5:
            c = 90.5 if not asagi else 108.0
        elif i == 6:
            c = 89.2 if not asagi else 118.0
        elif i == 7:
            c = 88.4 if not asagi else 124.0
        elif i == 8:
            c = 88.0 if not asagi else 128.0
        elif i <= 8 + pole_bars:
            adim = (38.0 if not asagi else -40.0) / pole_bars
            c = (88.0 if not asagi else 128.0) + (i - 8) * adim
        else:
            p = i - 8 - pole_bars
            if asagi:
                ul, ll = 95.0 + p * upper_k, 89.0 + p * lower_k
            else:
                ul, ll = 126.0 + p * upper_k, 122.0 + p * lower_k
            pos = p % 8
            c = ul - 0.05 if pos == 6 else (ll + 0.05 if pos == 2 else (ul + ll) * 0.5)
        close.append(c + np.random.randn() * 0.02)
    return _df_yap(close)


def _iki_formasyon(seed1=21, seed2=77):
    d1 = _kanalli_pennant(n_bars=48, upper_k=-0.06, lower_k=0.06, seed=seed1)
    d2 = _kanalli_pennant(n_bars=48, upper_k=-0.001, lower_k=0.15, seed=seed2)
    d2 = d2.copy()
    d2.index = d2.index + pd.Timedelta(hours=len(d1))
    return pd.concat([d1, d2])


def _mgr():
    return PatternLifecycleManager(profile="Dengeli")


def _kayit_eslestir(mgr, key, df, data_dir=None):
    """Defterdeki kayıtlarla, o scan'de doğan formation'ların eşleşmesini döndürür."""
    stock, tf = _parse_stock_tf(key)
    defter = fh.yukle(stock, tf, data_dir)
    return fh.kayitlar(defter)


# =====================================================================
# S — SÖZLEŞME (Faz 2.0)
# =====================================================================

def test_butun_alanlar_siniflandirilmis():
    """PatternCandidate'ın 85 alanının TAMAMI bir sınıfa atanmış olmalı.

    'İncelenmeli' boşluğu bırakılmaz: eksik ya da fazla alan varsa test kızar.
    """
    import dataclasses
    gercek = {f.name for f in dataclasses.fields(PatternCandidate)}
    assert gercek == fs.ALL_FIELDS
    assert len(gercek) == 85
    assert not (gercek - fs.ALL_FIELDS), "Sınıflandırılmamış alan kaldı"
    assert not (fs.ALL_FIELDS - gercek), "Olmayan alan sınıflandırılmış"


def test_her_alanin_sinifi_tek_ve_belirli():
    """Her alan için `alan_sinifi` None dönmemeli (belirsizlik yasak)."""
    for alan in sorted(fs.ALL_FIELDS):
        sinif = fs.alan_sinifi(alan)
        assert sinif in fs.SINIFLAR, "%s için sınıf belirsiz: %r" % (alan, sinif)


def test_sinif_cakismasi_yalnizca_raw_quality():
    """`raw_quality` bilinçli olarak iki sınıfta; başka çakışma olmamalı."""
    cakismalar = (fs.IDENTITY_FIELDS & fs.STATE_FIELDS
                  | fs.IDENTITY_FIELDS & fs.BREAKOUT_FIELDS
                  | fs.STATE_FIELDS & fs.BREAKOUT_FIELDS
                  | fs.IDENTITY_FIELDS & fs.TRANSIENT_FIELDS
                  | fs.STATE_FIELDS & fs.TRANSIENT_FIELDS
                  | fs.BREAKOUT_FIELDS & fs.TRANSIENT_FIELDS)
    assert cakismalar == {"raw_quality"}


def test_transient_alanlar_hicbir_snapshotta_yazilmaz():
    """TRANSIENT alanlar asla serileştirilmemeli (per-bar dump yasağı)."""
    aday = PatternCandidate()
    aday.valid = True
    aday.identity = 7
    aday.selection_score = 55.0
    aday.historical_close_violations = 3
    aday.violation_geometry_key = ("a", "b")
    for snap in (fs.dogum_snapshot(aday), fs.geometri_snapshot(aday),
                 fs.kirilim_snapshot(aday)):
        for alan in fs.TRANSIENT_FIELDS:
            assert alan not in snap["alanlar"], "%s sızdı" % alan


def test_serileştirme_json_guvenli():
    """Timestamp / numpy / None -> JSON-safe; exception üretmez."""
    import numpy as np
    assert fs.json_guvenli(None) is None
    assert fs.json_guvenli(True) is True
    assert fs.json_guvenli(np.float64(1.5)) == 1.5
    assert fs.json_guvenli(np.int64(3)) == 3
    ts = pd.Timestamp("2026-01-08 05:30:00+03:00")
    assert isinstance(fs.json_guvenli(ts), str)
    # Bilinmeyen tip sessizce str'e iner, patlamaz.
    class Tuhaf:
        pass
    assert isinstance(fs.json_guvenli(Tuhaf()), str)


def test_dogum_snapshot_identity_alanlarini_tasir():
    """Doğum snapshot'ı IDENTITY alanlarını taşır (direk alanları dahil)."""
    aday = PatternCandidate()
    aday.valid = True
    aday.stable_id = "sid-1"
    aday.family = "Flama"
    aday.classic_dir = 1
    aday.has_pole = True
    aday.pole_quality = 71.5
    aday.upper_slope = -0.06
    snap = fs.dogum_snapshot(aday, bar_time="2026-01-08 05:30:00+03:00")
    a = snap["alanlar"]
    assert a["stable_id"] == "sid-1"
    assert a["family"] == "Flama"
    assert a["classic_dir"] == 1
    assert a["has_pole"] is True
    assert a["pole_quality"] == 71.5
    assert a["upper_slope"] == -0.06
    assert snap["bar_time"] == "2026-01-08 05:30:00+03:00"


def test_persisted_today_gercekten_bugun_persist_ediliyor():
    """`PERSISTED_TODAY` listesi boş değil ve sınıflandırmayla örtüşür.

    İddia: bu alanlar bugün diske yazılıyor (anchor + formasyon_kaydi).
    Test, listenin somut olduğunu ve sınıflandırılmış alanlarla çakıştığını
    doğrular; böylece 'incelenmeli' listesi tahmin değil ölçüme dayanır.
    """
    assert fs.PERSISTED_TODAY, "PERSISTED_TODAY boş kaldı"
    assert fs.PERSISTED_TODAY <= fs.ALL_FIELDS
    assert fs.PERSISTED_TODAY & fs.TRANSIENT_FIELDS == set(), \
        "TRANSIENT bir alan 'bugün persist ediliyor' diye işaretlenmiş"


def test_incelenmeli_listesi_tahmin_degil():
    """`INCELENMELI` = sınıflandırılmış ama bugün yazılmayanların tamamı."""
    beklenen = ((fs.IDENTITY_FIELDS | fs.STATE_FIELDS | fs.BREAKOUT_FIELDS)
                - fs.PERSISTED_TODAY)
    assert fs.INCELENMELI == beklenen
    assert not (fs.INCELENMELI & fs.PERSISTED_TODAY)
    # Bugün yazılmayan identity/state alanları gerçekten var (Faz 2.3 işi).
    assert "upper_slope" in fs.INCELENMELI
    assert "pole_quality" in fs.INCELENMELI
    assert "geometry_score" in fs.INCELENMELI


def test_anchor_alanlari_persisted_today_ile_ortusur():
    """Faz 1 anchor'ünün yazdığı alanlar PERSISTED_TODAY ile örtüşmeli."""
    from state import formation_identity as fid
    anchor = {"stable_id": "s", "stock": "A", "timeframe": "1h", "family": "Flama",
              "classic_dir": 1, "pattern_type": "Boğa Flaması", "start_bar": 5,
              "apex_bar": 30, "hb1": 5, "hb2": 19, "hp1": 100.0, "hp2": 101.0,
              "lb1": 5, "lb2": 19, "lp1": 95.0, "lp2": 96.0,
              "birth_bar_time": "2026-01-08 05:30:00+03:00"}
    aday_alanlari = {k for k in anchor if k in fs.ALL_FIELDS}
    assert aday_alanlari <= fs.PERSISTED_TODAY, \
        "Anchor yazıyor ama PERSISTED_TODAY eksik: %s" % (aday_alanlari - fs.PERSISTED_TODAY)


# =====================================================================
# R — REGISTRY (Faz 2.1)
# =====================================================================

def test_defter_yaz_okunur_roundtrip():
    stock, tf = "ASELS", "1h"
    defter = fh.bos_defter(stock, tf)
    defter["kayitlar"]["sid-a"] = {"stable_id": "sid-a", "durum": fh.DURUM_ACIK}
    assert fh.kaydet(defter) is True
    geri = fh.yukle(stock, tf)
    assert set(geri["kayitlar"]) == {"sid-a"}
    assert geri["kayitlar"]["sid-a"]["durum"] == fh.DURUM_ACIK
    assert geri["stock"] == stock and geri["timeframe"] == tf
    assert os.path.exists(fh.yol(stock, tf))


def test_atomik_yazma_yarim_dosya_birakmaz():
    """Yazma sonunda tmp dosya kalmaz; yalnızca final dosya görülür."""
    stock, tf = "GARAN", "2h"
    defter = fh.bos_defter(stock, tf)
    defter["kayitlar"]["s1"] = {"stable_id": "s1", "durum": fh.DURUM_ACIK}
    fh.kaydet(defter)
    klasor = os.path.dirname(fh.yol(stock, tf))
    artan = [f for f in os.listdir(klasor) if ".tmp." in f]
    assert artan == [], "Atomik yazma tmp dosya bıraktı: %s" % artan


def test_bozuk_dosya_defteri_durdurmaz():
    """Bozuk JSON -> boş defter. Bot ÇALIŞMAYA DEVAM EDER (exception yok)."""
    stock, tf = "THYAO", "4h"
    dosya = fh.yol(stock, tf)
    os.makedirs(os.path.dirname(dosya), exist_ok=True)
    with open(dosya, "w", encoding="utf-8") as f:
        f.write("{bu gecerli json degil!!!")
    defter = fh.yukle(stock, tf)
    assert defter["kayitlar"] == {}
    assert defter["stock"] == stock
    # Yazma hâlâ çalışır (kendini onarır).
    defter["kayitlar"]["x"] = {"stable_id": "x", "durum": fh.DURUM_ACIK}
    assert fh.kaydet(defter) is True
    assert set(fh.yukle(stock, tf)["kayitlar"]) == {"x"}


def test_bos_ve_eksik_dosya():
    assert fh.yukle("YOKHISSE", "1h")["kayitlar"] == {}
    stock, tf = "YOKHISSE", "1h"
    dosya = fh.yol(stock, tf)
    os.makedirs(os.path.dirname(dosya), exist_ok=True)
    with open(dosya, "w", encoding="utf-8") as f:
        f.write("")
    assert fh.yukle(stock, tf)["kayitlar"] == {}
    # Liste biçiminde (dict değil) içerik de güvenle boş deftere iner.
    with open(dosya, "w", encoding="utf-8") as f:
        f.write("[1, 2, 3]")
    assert fh.yukle(stock, tf)["kayitlar"] == {}


def test_olaylar_stable_id_tasir():
    """Olaylar stable_id taşır ve DEFTERDE `time` JSON-safe olur.

    Not: motorun bellek içi olay listesi `time` için ham Timestamp taşır
    (Faz 1 davranışı, DEĞİŞTİRİLMEZ). JSON-safe'liğin taahhüdü yazma
    katmanındadır: `fh.olay_ekle` kopyayı indirger.
    """
    df = _kanalli_pennant(n_bars=60, seed=3)
    mgr = _mgr()
    key = "ASELS_1h"
    snap = mgr.scan(key, df, tam_yeniden=True)
    olaylar = [e for e in (snap.events or []) if e.get("type") == "NEW_PATTERN"]
    assert olaylar, "NEW_PATTERN olayı üretilmedi"
    for ev in olaylar:
        assert ev.get("stable_id"), "Olay stable_id taşımıyor: %r" % ev
        # Motorun anahtar adları değişmedi.
        for anahtar in ("type", "name", "bar", "time", "state"):
            assert anahtar in ev, "Anahtar kayboldu: %s" % anahtar
    # Deftere yazılan kopya JSON-safe olmalı.
    defter = fh.yukle("ASELS", "1h")
    yazilan = [o for r in fh.kayitlar(defter) for o in r.get("olaylar", [])]
    assert yazilan, "Olaylar deftere yazılmadı"
    for o in yazilan:
        assert isinstance(o.get("time"), (str, type(None))), \
            "Defterde ham Timestamp kaldı: %r" % o.get("time")
        assert o.get("stable_id"), "Defterdeki olay stable_id taşımıyor"


def test_olay_replayde_sismez():
    """Aynı tarama tekrarlandığında olay iki kez yazılmaz."""
    df = _kanalli_pennant(n_bars=60, seed=5)
    mgr = _mgr()
    key = "GARAN_1h"
    snap = mgr.scan(key, df, tam_yeniden=True)
    ilk = len([e for e in (snap.events or []) if e.get("stable_id")])
    assert ilk > 0
    mgr.scan(key, df, tam_yeniden=True)   # aynı veri, tam replay
    mgr.scan(key, df, tam_yeniden=True)
    defter = fh.yukle("GARAN", "1h")
    toplam = sum(len(r.get("olaylar", [])) for r in fh.kayitlar(defter))
    assert toplam == ilk, "Replay olayları çoğalttı: %d -> %d" % (ilk, toplam)


def test_olay_bilinen_formasyona_baglanir():
    """Doğum bu turda yazılmayan bir olay için iskelet kayıt açılmaz."""
    defter = fh.bos_defter("X", "1h")
    ek = fh.olay_ekle(defter, [{"type": "NEW_PATTERN", "name": "x", "bar": 1,
                                "time": "t", "stable_id": "bilinmeyen"}])
    assert ek == 0
    assert defter["kayitlar"] == {}


def test_retention_siniri_asilmaz():
    """Defter sınırlı büyür; sonsuz büyüme yasak."""
    stock, tf = "PETKM", "1h"
    defter = fh.bos_defter(stock, tf)
    for i in range(fh.MAX_KAYIT + 25):
        sid = "sid-%03d" % i
        defter["kayitlar"][sid] = {"stable_id": sid, "durum": fh.DURUM_ACIK,
                                   "ilk_gorulme": "2026-01-01T00:00:%02d" % (i % 60)}
    silinen = fh._retention_temizle(defter)
    assert silinen == 25
    assert len(defter["kayitlar"]) == fh.MAX_KAYIT
    # En yeniler korunur.
    assert "sid-%03d" % (fh.MAX_KAYIT + 24) in defter["kayitlar"]


def test_retention_sonucu_baglanmis_kaydi_silmez():
    """Sonucu bağlanmış (outcome) kayıt retention tarafından silinmez."""
    stock, tf = "PETKM", "2h"
    defter = fh.bos_defter(stock, tf)
    defter["kayitlar"]["sonuclu"] = {
        "stable_id": "sonuclu", "durum": fh.DURUM_TERMINAL,
        "ilk_gorulme": "2026-01-01T00:00:00", "sonuc": {"durum": "HEDEF"}}
    for i in range(fh.MAX_KAYIT + 5):
        sid = "s%03d" % i
        defter["kayitlar"][sid] = {"stable_id": sid, "durum": fh.DURUM_ACIK,
                                   "ilk_gorulme": "2026-02-01T00:00:%02d" % (i % 60)}
    fh._retention_temizle(defter)
    assert "sonuclu" in defter["kayitlar"], "Sonucu bağlı kayıt silindi"


# =====================================================================
# K — KİMLİK: sliding window'da stable_id korunur (TEMEL KRİTER)
# =====================================================================

def _kayan_pencere_sidleri(df, mgr, key, adim=10, uzunluk=360):
    """Kayan pencerelerde doğan stable_id kümelerini döndürür."""
    kumeler = []
    for basla in range(0, 40, adim):
        pen = df.iloc[basla: basla + uzunluk].copy()
        if len(pen) < 80:
            break
        snap = mgr.scan(key, pen, tam_yeniden=True)
        sids = {e.get("stable_id") for e in (snap.events or []) if e.get("stable_id")}
        kumeler.append((basla, sids, snap))
    return kumeler


def _penceredeki_kimlikler(pen, stock, tf):
    """Pencerede hâlâ var olan formation'ları (doğum barı, family) -> sid eşler.

    Doğum barı pencereden çıkmış kayıtlar hariç tutulur: onlar artık
    yeniden tespit edilemez (güvenlik kuralı 1).
    """
    defter = fh.yukle(stock, tf)
    simdi = {}
    for rec in fh.kayitlar(defter):
        d = rec.get("dogum") or {}
        bt, bi = d.get("bar_time"), d.get("bar_index")
        if bt is None or not isinstance(bi, int):
            continue
        konum = None
        for i in range(len(pen.index)):
            if str(pen.index[i]) == str(bt):
                konum = i
                break
        if konum is None:
            continue
        fam = (d.get("alanlar") or {}).get("family")
        simdi[(str(bt), fam)] = rec["stable_id"]
    return simdi


def test_sliding_window_kimlik_korunur():
    """Aynı formation kayan pencerede tekrar tespit edilince stable_id KORUNUR.

    Bu, Faz 2.1'in temel kabul kriteridir: pencere her taramada ötelenir ve
    bar indeksleri kayar; kimlik buna rağmen sabit kalmalıdır.

    Anahtar (doğum barı, family) çiftidir çünkü aynı fiziksel formasyon
    pencere kenarında yeniden SINIFLANDIRILABİLİR (Flama -> Üçgen). Bu,
    PHASE2_TASARIM_NOTLARI.md §3'te dokümante edilmiş ve KABUL EDİLMİŞ
    davranıştır: `identity_compatible` matematik olduğu için değiştirilmez,
    yeniden sınıflandırma yeni stable_id hakeder.
    """
    df = _kanalli_pennant(n_bars=430, seed=11)
    mgr = _mgr()
    key = "ASELS_1h"
    onceki, korunan, uretilen = {}, 0, 0
    for basla in range(0, 40, 10):
        pen = df.iloc[basla: basla + 360].copy()
        if len(pen) < 80:
            break
        mgr.scan(key, pen, tam_yeniden=True)
        simdi = _penceredeki_kimlikler(pen, "ASELS", "1h")
        uretilen += len(simdi)
        for anahtar, sid in onceki.items():
            if anahtar in simdi:
                assert simdi[anahtar] == sid, (
                    "Aynı fiziksel formasyonun kimliği değişti (%s): %s -> %s"
                    % (anahtar, sid, simdi[anahtar]))
                korunan += 1
        if simdi:
            onceki = simdi
    assert uretilen > 0, "Hiç formation üretilmedi"
    assert korunan >= 1, "Kayan pencerede hiçbir kimlik korunamadı"


def test_sliding_window_kopya_kayit_olusturmaz():
    """Aynı fiziksel formation için kayan pencerede KOPYA kayıt oluşmaz.

    Faz 1'in en büyük açığı buydu: pencere kaydıkça aynı formation yeni
    UUID alıyor ve defter şişiyordu. Bar-time alignment bunu çözer.
    """
    df = _kanalli_pennant(n_bars=430, seed=11)
    mgr = _mgr()
    key = "ASELS_1h"
    for basla in range(0, 40, 10):
        pen = df.iloc[basla: basla + 360].copy()
        if len(pen) < 80:
            break
        mgr.scan(key, pen, tam_yeniden=True)
    defter = fh.yukle("ASELS", "1h")
    # Doğum barına göre grupla: aynı fiziksel formation en fazla bir kez
    # görünmeli (yeniden sınıflandırma bir kez olabilir).
    from collections import Counter
    dogum_sayisi = Counter()
    for rec in fh.kayitlar(defter):
        dogum_sayisi[(rec.get("dogum") or {}).get("bar_time")] += 1
    assert dogum_sayisi, "Kayıt üretilmedi"
    cok = {k: v for k, v in dogum_sayisi.items() if v > 2}
    assert not cok, "Aynı doğum barı için çok fazla kayıt (kopya): %s" % cok


def test_yeniden_siniflandirma_yeni_sid_hakeder():
    """Flama -> Üçgen yeniden sınıflandırması YENİ stable_id üretir.

    Bu dokümante edilmiş ve bilinçli davranışdır: `identity_compatible`
    formasyon matematiğidir ve Faz 2 onu DEĞİŞTİRMEZ. Yeniden
    sınıflandırmayı aynı kimlikte tutmanın yolu matematik değil, ileride
    eklenecek yumuşak `related_to` bağıdır.
    """
    df = _kanalli_pennant(n_bars=430, seed=11)
    mgr = _mgr()
    key = "ASELS_1h"
    gorulen = []
    for basla in range(0, 40, 10):
        pen = df.iloc[basla: basla + 360].copy()
        if len(pen) < 80:
            break
        snap = mgr.scan(key, pen, tam_yeniden=True)
        defter = fh.yukle("ASELS", "1h")
        gorulen.append(_penceredeki_kimlikler(pen, "ASELS", "1h"))
    # Aynı doğum barı, FARKLI family -> farklı sid olmalı.
    tum = {}
    for k in gorulen:
        tum.update(k)
    ayni_dogum = {}
    for (bt, fam), sid in tum.items():
        ayni_dogum.setdefault(bt, set()).add(fam)
    yeniden = {bt: f for bt, f in ayni_dogum.items() if len(f) > 1}
    if yeniden:
        # Yeniden sınıflandırma varsa, her family ayrı sid taşımalı.
        for bt, famlar in yeniden.items():
            sidler = {tum[(bt, f)] for f in famlar}
            assert len(sidler) == len(famlar), \
                "Yeniden sınıflandırma aynı sid'i paylaştı: %s" % yeniden


def test_aktif_formation_sid_kayan_pencerede_sabit():
    """Motorun takip ettiği aktif formation'ın stable_id'si kayan pencerede sabit.

    Yeniden sınıflandırma (family değişimi) istisnadır ve ayrı testle
    korunur; burada family sabit kalan durumda kimlik değişmemelidir.
    """
    df = _kanalli_pennant(n_bars=430, seed=13)
    mgr = _mgr()
    key = "THYAO_1h"
    gorulen = []
    for basla in range(0, 40, 10):
        pen = df.iloc[basla: basla + 360].copy()
        if len(pen) < 80:
            break
        mgr.scan(key, pen, tam_yeniden=True)
        eng = mgr.get_engine(key)
        if eng.active.valid and eng.active.stable_id:
            gorilen = (eng.active.stable_id, eng.active.family)
            gorulen.append(gorilen)
    assert gorilen if False else gorulen, "Aktif formation hiç üretilmedi"
    # (sid, family) çifti: aynı family altında sid değişmemeli.
    family_gorulen = {}
    for sid, fam in gorulen:
        if fam in family_gorulen:
            assert family_gorulen[fam] == sid, (
                "Aktif formation kimliği değişti (%s): %s -> %s"
                % (fam, family_gorulen[fam], sid))
        family_gorulen[fam] = sid


def test_iki_formasyon_ayri_kimlik_alir():
    """Aynı pencerede iki farklı formation, iki farklı stable_id alır."""
    df = _iki_formasyon()
    mgr = _mgr()
    key = "ASELS_1h"
    snap = mgr.scan(key, df, tam_yeniden=True)
    sids = {e.get("stable_id") for e in (snap.events or []) if e.get("stable_id")}
    assert len(sids) >= 2, "İki formasyon aynı kimliği paylaştı: %s" % sids
    defter = fh.yukle("ASELS", "1h")
    assert len(fh.kayitlar(defter)) >= 2
    for rec in fh.kayitlar(defter):
        assert rec.get("dogum", {}).get("bar_time"), "Doğum bar_time yazılmadı"
        assert isinstance(rec["dogum"].get("bar_index"), int), "Doğum bar_index yazılmadı"


def test_ayni_scan_ayni_sid_iki_candidate_atanamaz():
    """Bir scan içinde aynı stable_id iki farklı candidate'a atanamaz."""
    df = _iki_formasyon()
    mgr = _mgr()
    key = "ISCTR_1h"
    snap = mgr.scan(key, df, tam_yeniden=True)
    sids = [e.get("stable_id") for e in (snap.events or []) if e.get("stable_id")]
    assert sids
    # Doğum olayları (NEW_PATTERN) birebir ayrık kimlikler taşımalı.
    dogumlar = [e["stable_id"] for e in (snap.events or []) if e.get("type") == "NEW_PATTERN"]
    assert len(dogumlar) == len(set(dogumlar)), \
        "Aynı scan'de iki doğum aynı stable_id aldı: %s" % dogumlar


def test_restart_kimlik_korunur():
    """Yeni manager (restart) aynı veriyle aynı stable_id'leri üretir."""
    df = _kanalli_pennant(n_bars=120, seed=17)
    key = "GARAN_1h"
    m1 = _mgr()
    snap1 = m1.scan(key, df, tam_yeniden=True)
    sids1 = sorted({e.get("stable_id") for e in (snap1.events or []) if e.get("stable_id")})
    assert sids1
    m2 = _mgr()          # restart: tamamen yeni manager + motorlar
    snap2 = m2.scan(key, df, tam_yeniden=True)
    sids2 = sorted({e.get("stable_id") for e in (snap2.events or []) if e.get("stable_id")})
    assert sids2 == sids1, "Restart kimliği kaybetti: %s -> %s" % (sids1, sids2)


def test_restart_sonrasi_kayan_pencerede_kimlik_korunur():
    """Restart'tan sonra pencere kaydırılsa da kimlik korunur."""
    df = _kanalli_pennant(n_bars=430, seed=19)
    key = "EREGL_1h"
    m1 = _mgr()
    pen = df.iloc[:360].copy()
    snap1 = m1.scan(key, pen, tam_yeniden=True)
    ilk = _penceredeki_kimlikler(pen, "EREGL", "1h")
    assert ilk
    m2 = _mgr()   # restart
    pen2 = df.iloc[10:370].copy()
    snap2 = m2.scan(key, pen2, tam_yeniden=True)
    sonra = _penceredeki_kimlikler(pen2, "EREGL", "1h")
    for anahtar, sid in ilk.items():
        if anahtar in sonra:
            assert sonra[anahtar] == sid, (
                "Restart sonrası kimlik kaybı (%s): %s -> %s"
                % (anahtar, sid, sonra[anahtar]))


# =====================================================================
# Y — YANLIŞ EŞLEŞME GÜVENLİĞİ
# =====================================================================

def test_farkli_formation_yeni_sid_alir():
    """Gerçekten farklı bir formation YENİ stable_id alır (yanlış birleşme yok)."""
    df = _iki_formasyon()
    mgr = _mgr()
    key = "ASELS_1h"
    snap = mgr.scan(key, df, tam_yeniden=True)
    dogumlar = [e["stable_id"] for e in (snap.events or []) if e.get("type") == "NEW_PATTERN"]
    assert len(dogumlar) >= 2
    assert len(set(dogumlar)) == len(dogumlar)


def test_terminal_kimlik_yeni_formasyona_tasinmaz():
    """Terminal bir kaydın stable_id'si yeni formasyona asla bağlanmaz."""
    stock, tf = "ASELS", "1h"
    defter = fh.bos_defter(stock, tf)
    defter["kayitlar"]["terminal-sid"] = {
        "stable_id": "terminal-sid", "durum": fh.DURUM_TERMINAL,
        "terminal_state": "FORMASYON_TAMAMLANDI",
        "dogum": {"bar_time": "2026-01-08 05:30:00+03:00", "bar_index": 10,
                  "alanlar": {"family": "Flama", "classic_dir": 1,
                              "pattern_type": "Boğa Flaması", "start_bar": 10,
                              "geometry_atr": 1.0}}}
    fh.kaydet(defter)

    # Aynı doğum barı pencerede olsa bile terminal kayıt eşleşmemeli.
    import pandas as pd
    from datetime import timedelta
    idx = pd.date_range("2026-01-08 05:30", periods=40, freq="h", tz="Europe/Istanbul")
    df = pd.DataFrame({"open": [100.0] * 40, "high": [100.5] * 40,
                       "low": [99.5] * 40, "close": [100.0] * 40,
                       "volume": [1_000_000] * 40}, index=idx)

    aday = PatternCandidate()
    aday.valid = True
    aday.family = "Flama"
    aday.classic_dir = 1
    aday.pattern_type = "Boğa Flaması"
    aday.start_bar = 10
    aday.geometry_atr = 1.0
    assert fh.eslestir(_gercek_motor(idx, "%s_%s" % (stock, tf)), aday, stock=stock, tf=tf) is None


def test_dogum_bari_pencerede_degilse_eslesme_yok():
    """Doğum barı pencerede yoksa eşleşme denenmez (güvenlik kuralı 1)."""
    stock, tf = "ASELS", "1h"
    defter = fh.bos_defter(stock, tf)
    defter["kayitlar"]["sid-a"] = {
        "stable_id": "sid-a", "durum": fh.DURUM_ACIK,
        "dogum": {"bar_time": "2020-01-01 00:00:00+03:00", "bar_index": 5,
                  "alanlar": {"family": "Flama", "classic_dir": 1,
                              "pattern_type": "Boğa Flaması", "start_bar": 5,
                              "geometry_atr": 1.0}}}
    fh.kaydet(defter)
    import pandas as pd
    idx = pd.date_range("2026-01-08 05:30", periods=40, freq="h", tz="Europe/Istanbul")
    df = pd.DataFrame({"open": [100.0] * 40, "high": [100.5] * 40,
                       "low": [99.5] * 40, "close": [100.0] * 40,
                       "volume": [1_000_000] * 40}, index=idx)

    aday = PatternCandidate()
    aday.valid = True
    aday.family = "Flama"
    aday.classic_dir = 1
    aday.pattern_type = "Boğa Flaması"
    aday.start_bar = 30
    aday.geometry_atr = 1.0
    assert fh.eslestir(_gercek_motor(idx, "%s_%s" % (stock, tf)), aday, stock=stock, tf=tf) is None


def test_faz1_anchor_bicimi_matcher_tarafindan_degerlendirilmez():
    """Faz 1 anchor biçimi (düz alanlar) yeni matcher tarafından yutulmaz."""
    stock, tf = "ASELS", "1h"
    defter = fh.bos_defter(stock, tf)
    # Faz 1 biçimi: düz alanlar, `dogum` yok.
    defter["kayitlar"]["eski"] = {
        "stable_id": "eski", "durum": fh.DURUM_ACIK,
        "family": "Flama", "classic_dir": 1, "pattern_type": "Boğa Flaması",
        "start_bar": 5, "birth_bar_time": "2026-01-08 05:30:00+03:00"}
    fh.kaydet(defter)
    import pandas as pd
    idx = pd.date_range("2026-01-08 05:30", periods=40, freq="h", tz="Europe/Istanbul")

    aday = PatternCandidate()
    aday.valid = True
    aday.family = "Flama"
    aday.classic_dir = 1
    aday.pattern_type = "Boğa Flaması"
    aday.start_bar = 5
    aday.geometry_atr = 1.0
    # `dogum` olmadığı için atlanır -> Faz 1 yolu devrede kalır.
    assert fh.eslestir(_gercek_motor(idx, "%s_%s" % (stock, tf)), aday, stock=stock, tf=tf) is None


def test_registry_bossa_faz1_davranisi_aynen_devam_eder():
    """Registry boşken davranış, Faz 1'in kendi kuralıyla aynı olmalı."""
    df = _kanalli_pennant(n_bars=120, seed=23)
    key = "GARAN_1h"
    mgr = _mgr()
    snap = mgr.scan(key, df, tam_yeniden=True)
    dogumlar = [e["stable_id"] for e in (snap.events or []) if e.get("type") == "NEW_PATTERN"]
    for sid in dogumlar:
        try:
            uuid.UUID(str(sid))
        except (ValueError, AttributeError, TypeError):
            pytest.fail("Yeni stable_id UUID değil: %r" % sid)


def test_history_yazimi_botu_durdurmaz():
    """Yazım hatası botu durdurmaz (exception sızmaz)."""
    df = _kanalli_pennant(n_bars=60, seed=29)
    mgr = _mgr()
    key = "ASELS_1h"
    asil = fh.kaydet
    fh.kaydet = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk dolu"))
    try:
        snap = mgr.scan(key, df, tam_yeniden=True)   # hata yutulmalı
        assert snap is not None
    finally:
        fh.kaydet = asil


# =====================================================================
# MUTASYON TESTLERİ — düzeltmenin gerçekten gerekli olduğunun kanıtı
# =====================================================================

def test_mutasyon_bar_time_alignment_kaldirilinca_kimlik_kaybolur(monkeypatch):
    """Bar-time alignment olmadan kayan pencerede kimlik KAYBOLUR.

    Bu test, Faz 2.1'in tek gerçekten gerekli mimari eklemesinin
    bar-time alignment olduğunu kanıtlar: hizalamayı devre dışı bırakınca
    kayma telafi edilemez ve churn başlar.
    """
    asil = fh._konum_bul

    def _hizalama_yok(index_values, bar_time):
        # Hizalama yapılmıyor gibi davran: doğum barı "bulunamaz".
        return None

    monkeypatch.setattr(fh, "_konum_bul", _hizalama_yok)
    df = _kanalli_pennant(n_bars=430, seed=31)
    mgr = _mgr()
    key = "ASELS_1h"
    kumeler = _kayan_pencere_sidleri(df, mgr, key)
    ilk = kumeler[0][1]
    assert ilk
    bozuldu = any(k[1] != ilk for k in kumeler[1:])
    assert bozuldu, "Hizalama olmadan da kimlik korundu — düzeltme gereksiz olurdu"
    monkeypatch.setattr(fh, "_konum_bul", asil)


def test_mutasyon_esik_kaldirilinca_yanlis_birlesme_olur(monkeypatch):
    """Eşik (continuity_score >= 60) kaldılırsa yanlış birleşme mümkün olur.

    Güvenlik kuralı 1'in somut kanıtı: eşik olmadan farklı geometriler
    birleşir. Eşik AYNEN korunur; bu test onun neden var olduğunu gösterir.
    """
    stock, tf = "ASELS", "1h"
    defter = fh.bos_defter(stock, tf)
    # Doğum barı pencerede; family uyumlu AMA geometri tamamen farklı.
    defter["kayitlar"]["baska"] = {
        "stable_id": "baska", "durum": fh.DURUM_ACIK,
        "dogum": {"bar_time": "2026-01-08 05:30:00+03:00", "bar_index": 10,
                  "alanlar": {"family": "Flama", "classic_dir": 1,
                              "pattern_type": "Boğa Flaması",
                              "start_bar": 10, "geometry_atr": 1.0,
                              "hb1": 10, "hb2": 25, "hp1": 200.0, "hp2": 260.0,
                              "lb1": 10, "lb2": 25, "lp1": 180.0, "lp2": 240.0}}}
    fh.kaydet(defter)
    import pandas as pd
    idx = pd.date_range("2026-01-08 05:30", periods=40, freq="h", tz="Europe/Istanbul")

    # Farklı geometrili aday (üst sınır 100, kayıttaki 200).
    aday = PatternCandidate()
    aday.valid = True
    aday.family = "Flama"
    aday.classic_dir = 1
    aday.pattern_type = "Boğa Flaması"
    aday.start_bar = 10
    aday.geometry_atr = 1.0
    aday.hb1, aday.hb2 = 10, 25
    aday.hp1, aday.hp2 = 100.0, 100.0
    aday.lb1, aday.lb2 = 10, 25
    aday.lp1, aday.lp2 = 99.0, 99.0

    # Gerçek (eşikli) davranış: eşleşme YOK.
    assert fh.eslestir(_gercek_motor(idx, "%s_%s" % (stock, tf)), aday, stock=stock, tf=tf) is None

    # Mutasyon: eşik 0'a çekilirse yanlış birleşme olur (kanıt).
    import patterns.selection as sel
    asil_skor = sel.continuity_score
    monkeypatch.setattr(fh, "eslestir", fh.eslestir)  # yer tutucu
    monkeypatch.setattr("patterns.selection.continuity_score",
                        lambda *a, **k: 999.0)
    assert fh.eslestir(_gercek_motor(idx, "%s_%s" % (stock, tf)), aday, stock=stock, tf=tf) == "baska"
    monkeypatch.setattr("patterns.selection.continuity_score", asil_skor)


def _tam_geometrili_aday(bar=0):
    a = PatternCandidate()
    a.valid = True
    a.family = "Flama"
    a.classic_dir = 1
    a.pattern_type = "Boğa Flaması"
    a.start_bar = bar
    a.geometry_atr = 1.0
    a.hb1, a.hb2 = bar, bar + 15
    a.hp1, a.hp2 = 100.0, 101.0
    a.lb1, a.lb2 = bar, bar + 15
    a.lp1, a.lp2 = 95.0, 96.0
    return a


def test_mutasyon_kullanilan_korumasi_kaldirilinca_cift_atama(monkeypatch):
    """`kullanilan` koruması olmadan aynı sid iki kez atanabilir."""
    stock, tf = "ASELS", "1h"
    defter = fh.bos_defter(stock, tf)
    defter["kayitlar"]["tek"] = {
        "stable_id": "tek", "durum": fh.DURUM_ACIK,
        "dogum": {"bar_time": "2026-01-08 05:30:00+03:00", "bar_index": 0,
                  "alanlar": {"family": "Flama", "classic_dir": 1,
                              "pattern_type": "Boğa Flaması", "start_bar": 0,
                              "geometry_atr": 1.0,
                              "hb1": 0, "hb2": 15, "hp1": 100.0, "hp2": 101.0,
                              "lb1": 0, "lb2": 15, "lp1": 95.0, "lp2": 96.0}}}
    fh.kaydet(defter)
    import pandas as pd
    idx = pd.date_range("2026-01-08 05:30", periods=40, freq="h", tz="Europe/Istanbul")

    m = _gercek_motor(idx, "%s_%s" % (stock, tf))
    # 1. eşleşme: izinli.
    assert fh.eslestir(m, _tam_geometrili_aday(), stock=stock, tf=tf) == "tek"
    # 2. eşleşme: `kullanilan` ile engellenir (deterministik "ilk gelen alır").
    assert fh.eslestir(m, _tam_geometrili_aday(), kullanilan={"tek"},
                       stock=stock, tf=tf) is None
    # Korumasız: iki kez aynı sid döner -> bir scan'de çift atama riski.
    assert fh.eslestir(m, _tam_geometrili_aday(), stock=stock, tf=tf) == "tek"
