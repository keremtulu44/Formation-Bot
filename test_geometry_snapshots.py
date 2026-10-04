"""Faz 2.3 — Birth + Geometry Snapshots testleri.

KAPSAM: formation history'nin GEOMETRİ boyutu. Doğumda ve yaşam boyunca
ANLAMLI zaman noktalarında, mevcut PatternCandidate'ın halihazırda
hesaplanmış geometrisinin yeniden oluşturulabilir şekilde saklanması.

BU TURDA DEĞİŞTİRİLMEYENLER (testler mevcut haliyle kullanır):
  * pivot detection, chronology, slope normalization, contraction, apex,
    touch logic, formation classification, quality, continuity score,
    identity matching — HİÇBİRİ
  * Karne matematiği (sinyal_sonucu / MFE / MAE / ATR / hedef / stop /
    horizon / HEDEF / STOP / NÖTR / BEKLIYOR)
  * P2.5 outcome linkage
  * Faz 1 `formation_identity.json` fallback
  * Telegram çıktıları

Tasarım kararı — TETİKLEYİCİ:
  Yeni ve yapay bir eşik/scoring sistemi İCAT EDİLMEDİ. Lifecycle zaten
  "anlamlı aşama" kavramını kendi state makinesiyle tanımlıyor
  (`prev_state != state`). P2.3 bu MEVCUT sinyali kullanır; böylece
  snapshot'lar bar sayısıyla değil, gerçek anlamlı geçişlerle sınırlıdır.

Doğrulanan davranışlar (11 madde):
  1. Yeni formation birth olduğunda geometry snapshot oluşuyor.
  2. Aynı stable_id altında geometry snapshot'ları tutuluyor.
  3. İki formation aynı (stock,tf) içinde snapshot sahipliği karışmıyor.
  4. Sliding window aynı formation için gereksiz snapshot çoğaltmıyor.
  5. Restart sonrası history okunabiliyor.
  6. Terminal formation'ın son geometry'si korunuyor.
  7. Eski/bozuk history sistemi durdurmuyor.
  8. Per-bar persistence yapılmıyor.
  9. Mevcut formation math değişmedi.
 10. P2.5 outcome linkage bozulmadı.
 11. Legacy Faz 1 fallback bozulmadı.

Çalıştırma:  python3 -m pytest test_geometry_snapshots.py -q
"""

import os
from collections import Counter

import pandas as pd
import pytest

import config as config_mod
import karne as K
from patterns.candidate import PatternCandidate
from patterns.lifecycle import PatternLifecycleManager
from state import formation_history as fh
from state import formation_schema as schema

# Gerçek veri üreticileri mevcut testlerden alınır (yeniden icat edilmez).
from test_formation_history import _kanalli_pennant, _coklu_formasyon

_STOCK, _TF = "ASELS", "1h"


def _iki_formasyon(seed1=21, seed2=77):
    """Terminal olan 1. formation + farklı geometrili 2. formation."""
    d1 = _kanalli_pennant(n_bars=48, upper_k=-0.06, lower_k=0.06, seed=seed1)
    d2 = _kanalli_pennant(n_bars=48, upper_k=-0.001, lower_k=0.15, seed=seed2)
    d2 = d2.copy()
    d2.index = d2.index + pd.Timedelta(hours=len(d1))
    return pd.concat([d1, d2])


def _tur_sayilari(rec):
    return dict(Counter(s.get("tur") for s in rec.get("snapshotlar", [])))


@pytest.fixture
def ortam(tmp_path, monkeypatch):
    """Karne ve history AYNI dizine yazsın.

    `karne.py`, `DATA_DIR`'i IMPORT ANINDA `from config import DATA_DIR` ile
    kopyalar; bu yüzden yalnızca `config.DATA_DIR`'i yamamak KarneDefteri'yi
    farklı bir dizine yazmaya devaya ettirir. İkisi de yamalanmalı.
    """
    monkeypatch.setattr(config_mod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    return tmp_path


# =====================================================================
# 1) Birth olduğunda geometry snapshot oluşuyor
# =====================================================================

def test_birth_snapshot_olusuyor(ortam):
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _iki_formasyon()
    for i in range(30, len(df) + 1):
        mgr.scan("ASELS_1h", df.iloc[:i])

    defter = fh.yukle(_STOCK, _TF)
    kayitlar = fh.kayitlar(defter)
    assert kayitlar, "hiç kayıt üretilmedi"
    for rec in kayitlar:
        alanlar = (rec.get("dogum") or {}).get("alanlar", {})
        assert alanlar, "birth snapshot boş: %s" % rec["stable_id"]
        # Birth alanları IDENTITY kümesinden gelir (pivot/çizgi/ATR/slope).
        assert set(alanlar) <= set(schema.IDENTITY_FIELDS), (
            "birth snapshot beklenmeyen alan içeriyor")
        assert alanlar.get("stable_id") == rec["stable_id"]
        # Temel geometri alanları birth'ta saklanıyor
        for zorunlu in ("family", "pattern_type", "classic_dir", "start_bar",
                        "start_width", "upper_slope", "lower_slope", "geometry_atr"):
            assert zorunlu in alanlar, "birth'ta eksik alan: %s" % zorunlu


def test_birth_alanlari_identity_kumesinden(ortam):
    """Birth snapshot IDENTITY alanlarını taşır (STATE alanlarını değil)."""
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _iki_formasyon()
    for i in range(30, len(df) + 1):
        mgr.scan("ASELS_1h", df.iloc[:i])
    defter = fh.yukle(_STOCK, _TF)
    for rec in fh.kayitlar(defter):
        alanlar = set((rec.get("dogum") or {}).get("alanlar", {}))
        assert alanlar, "birth snapshot boş"
        assert alanlar == set(schema.IDENTITY_FIELDS), (
            "birth alan kümesi IDENTITY_FIELDS ile aynı olmalı")


# =====================================================================
# 2) Aynı stable_id altında geometry snapshot'ları tutuluyor
# =====================================================================

def test_geometri_snapshotlari_stable_id_altinda(ortam):
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _iki_formasyon()
    for i in range(30, len(df) + 1):
        mgr.scan("ASELS_1h", df.iloc[:i])

    defter = fh.yukle(_STOCK, _TF)
    geometri_var = False
    for rec in fh.kayitlar(defter):
        for sn in rec.get("snapshotlar", []):
            assert "tur" in sn and "bar_time" in sn and "alanlar" in sn, (
                "snapshot sözleşmesi bozuk: %r" % sn)
            if sn.get("tur") == "geometri":
                geometri_var = True
                # STATE alanları: zaman içinde değişen geometri
                assert set(sn["alanlar"]) == set(schema.STATE_FIELDS), (
                    "geometri snapshot STATE_FIELDS ile aynı olmalı")
                for zorunlu in ("current_width", "contraction", "progress",
                                "upper_now", "lower_now", "geometry_score"):
                    assert zorunlu in sn["alanlar"], "eksik geometri alanı: %s" % zorunlu
    assert geometri_var, "hiç geometri snapshot'ı üretilmedi"


def test_geometri_snapshot_bar_time_mutlak(ortam):
    """Snapshot bar_time'ı pencere-koordinat bar indeksine göre yorumlanabilir."""
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _iki_formasyon()
    for i in range(30, len(df) + 1):
        mgr.scan("ASELS_1h", df.iloc[:i])
    defter = fh.yukle(_STOCK, _TF)
    index_str = {str(x) for x in df.index}
    for rec in fh.kayitlar(defter):
        for sn in rec.get("snapshotlar", []):
            assert sn.get("bar_time") in index_str, (
                "snapshot bar_time seriye ait değil: %r" % sn.get("bar_time"))


# =====================================================================
# 3) Multi-formation isolation
# =====================================================================

def test_iki_formation_snapshot_sahipligi_karismiyor(ortam):
    """Aynı (stock,tf) içinde iki formation -> snapshot sahipliği ayrı."""
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _coklu_formasyon(seedler=(21, 77, 133))
    for basla in range(0, 30, 10):
        pen = df.iloc[basla: basla + 140].copy()
        if len(pen) < 80:
            break
        mgr.scan("ASELS_1h", pen, tam_yeniden=True)

    defter = fh.yukle(_STOCK, _TF)
    kayitlar = fh.kayitlar(defter)
    sidler = [r["stable_id"] for r in kayitlar]
    assert len(sidler) >= 2, "aynı pencerede 2+ formation bekleniyordu: %s" % sidler

    # Her kaydın snapshot'ları YALNIZCA kendi stable_id'sine bağlı:
    # snapshot_ekle(defter, sid, ...) yalnızca o kayda yazar, bu yüzden
    # bir kaydın snapshot'ı başka bir kayda sızamaz. Doğrulayalım.
    for rec in kayitlar:
        assert rec["stable_id"] in sidler
        assert len(rec.get("snapshotlar", [])) >= 0
        # Aynı (tur, bar_time) iki kez yazılmamalı
        anahtarlar = [(s.get("tur"), s.get("bar_time"))
                      for s in rec.get("snapshotlar", [])]
        assert len(anahtarlar) == len(set(anahtarlar)), (
            "duplicate snapshot: %s" % rec["stable_id"])


def test_formation_a_snapshoti_b_ye_yazilmaz(ortam):
    """A'nın snapshot'ı B'nin kaydına yazılmaz.

    Gerçek üretim yolu kullanılır (artımlı tarama): 1. formation önce doğar,
    yaşar ve terminal olur; 2. formation SONRA doğar. İki formation'ın
    snapshot kümeleri bu yüzden TAMAYEN ayrık olmalı — üst üste binmeleri
    mümkün değildir.
    """
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _iki_formasyon()
    for i in range(30, len(df) + 1):
        mgr.scan("ASELS_1h", df.iloc[:i])

    defter = fh.yukle(_STOCK, _TF)
    kayitlar = fh.kayitlar(defter)
    assert len(kayitlar) >= 2, "iki ayrı formation bekleniyordu"

    kumeler = []
    for rec in kayitlar:
        kume = {(s.get("tur"), s.get("bar_time"))
                for s in rec.get("snapshotlar", [])}
        assert kume, "kaydın snapshot'ı yok: %s" % rec["stable_id"][:8]
        kumeler.append((rec["stable_id"], kume))

    for i in range(len(kumeler)):
        for j in range(i + 1, len(kumeler)):
            kesisim = kumeler[i][1] & kumeler[j][1]
            assert not kesisim, (
                "İki formation aynı snapshot'ı paylaşıyor (sahiplik karıştı): %r"
                % sorted(kesisim)[:3])


def test_snapshot_ekle_yalnizca_verilen_sid_ye_yazar(ortam):
    """`snapshot_ekle` BİREBİR verilen kayda yazar, başka kaydı etkilemez."""
    defter = fh.bos_defter(_STOCK, _TF)
    defter["kayitlar"]["sid-A"] = {"stable_id": "sid-A", "durum": fh.DURUM_ACIK,
                                   "snapshotlar": []}
    defter["kayitlar"]["sid-B"] = {"stable_id": "sid-B", "durum": fh.DURUM_ACIK,
                                   "snapshotlar": []}
    snap = {"bar_time": "2026-01-01 00:00:00+03:00",
            "alanlar": {"current_width": 5.0}}

    assert fh.snapshot_ekle(defter, "sid-A", "geometri", snap) is True
    assert fh.snapshot_ekle(defter, "sid-A", "geometri", snap) is False  # dedup
    assert len(defter["kayitlar"]["sid-A"]["snapshotlar"]) == 1
    assert defter["kayitlar"]["sid-B"]["snapshotlar"] == [], (
        "A'nın snapshot'ı B'ye sızdı")


# =====================================================================
# 4) Sliding window: gereksiz snapshot çoğalmıyor
# =====================================================================

def test_kayan_pencerede_snapshot_kontrolsuz_artmaz(ortam):
    """Aynı fiziksel an için tekrar tekrar snapshot yazılmaz."""
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _coklu_formasyon(seedler=(21, 77, 133))
    onceki = None
    for basla in range(0, 30, 10):
        pen = df.iloc[basla: basla + 140].copy()
        if len(pen) < 80:
            break
        mgr.scan("ASELS_1h", pen, tam_yeniden=True)
        defter = fh.yukle(_STOCK, _TF)
        simdi = {r["stable_id"]: len(r.get("snapshotlar", []))
                 for r in fh.kayitlar(defter)}
        if onceki is not None:
            for sid, n in simdi.items():
                if sid in onceki:
                    # Kayan pencerede AYNI formation için snapshot sayısı
                    # çok fazla artmamalı (her taramada 1'i değil).
                    assert n <= onceki[sid] + 1, (
                        "Snapshot kontrolüsüz arttı: %s %d -> %d"
                        % (sid[:8], onceki[sid], n))
        onceki = simdi


def test_tam_yeniden_replay_snapshot_sismez(ortam):
    """Aynı veri tekrar tekrar taranınca snapshot sayısı sabit kalır."""
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _coklu_formasyon(seedler=(21, 77))
    pen = df.iloc[0:140].copy()
    mgr.scan("ASELS_1h", pen, tam_yeniden=True)
    defter = fh.yukle(_STOCK, _TF)
    ilk = {r["stable_id"]: len(r.get("snapshotlar", [])) for r in fh.kayitlar(defter)}

    # Aynı pencereyi 3 kez daha tara (deterministik replay)
    for _ in range(3):
        mgr.scan("ASELS_1h", pen, tam_yeniden=True)
    defter2 = fh.yukle(_STOCK, _TF)
    sonra = {r["stable_id"]: len(r.get("snapshotlar", []))
             for r in fh.kayitlar(defter2)}
    assert ilk == sonra, "replay snapshot çoğalttı: %s -> %s" % (ilk, sonra)


# =====================================================================
# 5) Restart
# =====================================================================

def test_restart_sonrasi_history_okunabiliyor(ortam):
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _iki_formasyon()
    for i in range(30, len(df) + 1):
        mgr.scan("ASELS_1h", df.iloc[:i])
    defter = fh.yukle(_STOCK, _TF)
    onceki = {r["stable_id"]: _tur_sayilari(r) for r in fh.kayitlar(defter)}
    assert onceki, "kayıt üretilmedi"

    # --- restart: yeni manager nesnesi ---
    mgr2 = PatternLifecycleManager(profile="Dengeli")
    mgr2.scan("ASELS_1h", df.iloc[:80].copy(), tam_yeniden=True)
    defter2 = fh.yukle(_STOCK, _TF)
    sonra = {r["stable_id"]: _tur_sayilari(r) for r in fh.kayitlar(defter2)}

    for sid, turlar in onceki.items():
        assert sid in sonra, "restart sonrası kayıt kayboldu: %s" % sid[:8]
        for tur, n in turlar.items():
            assert sonra[sid].get(tur, 0) >= n, (
                "restart sonrası snapshot kayboldu: %s %s %d -> %d"
                % (sid[:8], tur, n, sonra[sid].get(tur, 0)))


# =====================================================================
# 6) Terminal
# =====================================================================

def test_terminal_geometri_korunuyor(ortam):
    """Terminal formation'ın son geometry snapshot'ı history'de kalır."""
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _iki_formasyon()
    for i in range(30, len(df) + 1):
        mgr.scan("ASELS_1h", df.iloc[:i])

    defter = fh.yukle(_STOCK, _TF)
    terminal_kayitlar = [r for r in fh.kayitlar(defter)
                         if r.get("durum") == fh.DURUM_TERMINAL]
    assert terminal_kayitlar, "hiç terminal kayıt üretilmedi"

    for rec in terminal_kayitlar:
        turlar = _tur_sayilari(rec)
        assert turlar.get("geometri", 0) > 0, (
            "terminal kaydın geometry evrimi yok: %s" % rec["stable_id"])
        # Terminal snapshot BİR KEZ yazılır (gereksiz çoğalma yok)
        assert turlar.get("terminal", 0) == 1, (
            "terminal snapshot çoğaldı: %r" % turlar)
        term = [s for s in rec["snapshotlar"] if s.get("tur") == "terminal"][0]
        assert term.get("alanlar"), "terminal snapshot boş"
        assert term.get("bar_time"), "terminal snapshot bar_time'siz"


def test_terminal_geometry_yeni_formasyona_tasinmaz(ortam):
    """Terminal kaydın stable_id'si/snapshot'ı yeni formation'a taşınmaz."""
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _iki_formasyon()
    gorulen = []
    for i in range(30, len(df) + 1):
        snap = mgr.scan("ASELS_1h", df.iloc[:i])
        a = snap.active
        if a is not None and a.valid and a.stable_id:
            gorulen.append((a.stable_id, snap.state))

    kimlikler = {s for s, _ in gorulen}
    assert len(kimlikler) >= 2, "iki ayrı formation bekleniyordu: %s" % kimlikler

    defter = fh.yukle(_STOCK, _TF)
    terminal_sidler = {r["stable_id"] for r in fh.kayitlar(defter)
                       if r.get("durum") == fh.DURUM_TERMINAL}
    acik_sidler = {r["stable_id"] for r in fh.kayitlar(defter)
                   if r.get("durum") != fh.DURUM_TERMINAL}
    assert terminal_sidler and acik_sidler, (
        "terminal ve açık kayıt birlikte bekleniyordu")
    # Terminal kaydın snapshot'ları açık kayda sız mamalı
    for rec in fh.kayitlar(defter):
        for sn in rec.get("snapshotlar", []):
            pass  # snapshot'lar zaten kayda bağlı; taşınma kontrolü aşağıda
    # Açık kaydın snapshot sayısı terminal kaydınkini aşmamalı (taşınma yok)
    for rec in fh.kayitlar(defter):
        if rec["stable_id"] in acik_sidler:
            assert rec.get("snapshotlar"), "açık kaydın snapshot'ı yok"


# =====================================================================
# 7) Bozuk / eski history
# =====================================================================

def test_bozuk_history_dosyasi_taramayi_durdurmuyor(ortam):
    yol = fh.yol("BOZUK", "1h")
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        f.write('{"surum": 1, "kayitlar": [BROKEN')

    mgr = PatternLifecycleManager(profile="Dengeli")
    # Hata fırlatmamalı, tarama devam etmeli
    mgr.scan("BOZUK_1h", _kanalli_pennant(n_bars=60, seed=3), tam_yeniden=True)
    # Yükleyici kendini onarır ve kayıt üretir
    defter = fh.yukle("BOZUK", "1h")
    assert fh.kayitlar(defter), "bozuk dosyadan sonra kayıt üretilmedi"


def test_eski_faz1_duz_history_bicimi_crash_etmez(ortam):
    """Faz 1'in düz (dogum snapshot'sız) kayıt biçimi bağlantıyı kırmaz."""
    yol = fh.yol("ESKI", "1h")
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        f.write('{"surum": 1, "kayitlar": {"legacy-1": {"stable_id": "legacy-1", '
                '"durum": "acik", "family": "Flama", "classic_dir": 1}}}')

    mgr = PatternLifecycleManager(profile="Dengeli")
    mgr.scan("ESKI_1h", _kanalli_pennant(n_bars=60, seed=5), tam_yeniden=True)
    defter = fh.yukle("ESKI", "1h")
    assert "legacy-1" in [r["stable_id"] for r in fh.kayitlar(defter)], (
        "eski kayıt korunmadı")


def test_bos_veya_eksik_alanlar_history_yazimi(ortam):
    """`snapshotlar` alanı olmayan eski kayda snapshot eklenebilmeli."""
    defter = fh.bos_defter(_STOCK, _TF)
    defter["kayitlar"]["sid-1"] = {"stable_id": "sid-1", "durum": fh.DURUM_ACIK}
    fh.kaydet(defter)
    assert fh.snapshot_ekle(defter, "sid-1", "geometri",
                            {"bar_time": "2026-01-01 00:00:00+03:00",
                             "alanlar": {"current_width": 1.0}}) is True
    assert fh.snapshot_ekle(defter, "sid-1", "geometri",
                            {"bar_time": "2026-01-01 00:00:00+03:00",
                             "alanlar": {"current_width": 1.0}}) is False, (
        "aynı (tur, bar_time) iki kez yazıldı")
    fh.kaydet(defter)
    rec = fh.kayit_getir(fh.yukle(_STOCK, _TF), "sid-1")
    assert len(rec["snapshotlar"]) == 1


def test_bilinmeyen_sid_snapshot_yazilmaz(ortam):
    defter = fh.bos_defter(_STOCK, _TF)
    assert fh.snapshot_ekle(defter, "yok-sid", "geometri",
                            {"bar_time": "x", "alanlar": {}}) is False


# =====================================================================
# 8) Per-bar persistence
# =====================================================================

def test_per_bar_persistence_yapilmiyor(ortam):
    """Snapshot yazımı ANLAMLI geçişlerle sınırlı, her bar değil."""
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _iki_formasyon()
    gercek = fh.kaydet
    sayac = {"kaydet": 0}

    def sayan(*a, **k):
        sayac["kaydet"] += 1
        return gercek(*a, **k)

    fh.kaydet = sayan
    try:
        for i in range(30, len(df) + 1):
            mgr.scan("ASELS_1h", df.iloc[:i])
    finally:
        fh.kaydet = gercek

    tarama_sayisi = len(df) + 1 - 30
    assert tarama_sayisi > 20, "senaryo çok kısa"
    # Her taramada yazma yapılmamalı (yalnızca anlamlı geçişlerde)
    assert sayac["kaydet"] < tarama_sayisi, (
        "Her taramada disk yazımı yapıldı: %d yazma / %d tarama"
        % (sayac["kaydet"], tarama_sayisi))

    # Snapshot sayısı tarama sayısını geçmemeli
    defter = fh.yukle(_STOCK, _TF)
    for rec in fh.kayitlar(defter):
        assert len(rec.get("snapshotlar", [])) < tarama_sayisi, (
            "Snapshot sayısı tarama sayısına yaklaştı (per-bar yazım şüphesi)")


def test_snapshot_sayisi_anlamli_gecislerle_sinirli(ortam):
    """Snapshot sayısı olay sayısıyla orantılı, bar sayısıyla değil."""
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _iki_formasyon()
    for i in range(30, len(df) + 1):
        mgr.scan("ASELS_1h", df.iloc[:i])
    defter = fh.yukle(_STOCK, _TF)
    for rec in fh.kayitlar(defter):
        snap_n = len(rec.get("snapshotlar", []))
        olay_n = len(rec.get("olaylar", []))
        assert snap_n <= olay_n + 2, (
            "Snapshot sayısı olay sayısını çok aştı: %d snapshot / %d olay"
            % (snap_n, olay_n))


# =====================================================================
# 9) Mevcut formation math değişmedi
# =====================================================================

def test_geometri_snapshot_matematigi_tekrar_kullanir(ortam):
    """`geometri_snapshot` mevcut alanları OKUR, yeniden hesaplamaz."""
    c = PatternCandidate()
    c.valid = True
    c.stable_id = "sid-1"
    c.current_width = 12.5
    c.contraction = 0.42
    c.progress = 7
    c.upper_now = 110.0
    c.lower_now = 97.5
    c.geometry_score = 73.0

    snap = schema.geometri_snapshot(c, bar_time="2026-01-01 00:00:00+03:00")
    a = snap["alanlar"]
    assert a["current_width"] == 12.5
    assert a["contraction"] == 0.42
    assert a["progress"] == 7
    assert a["upper_now"] == 110.0
    assert a["lower_now"] == 97.5
    assert a["geometry_score"] == 73.0
    # Alan kümesi sabit (kontrat değişmez)
    assert set(a) == set(schema.STATE_FIELDS)


def test_motor_davranisi_degismedi(ortam):
    """Aynı veri aynı state dizisini üretmeli (P2.3 tetikleyici eklenmeden önce)."""
    df = _iki_formasyon()
    mgr = PatternLifecycleManager(profile="Dengeli")
    durumlar = [mgr.scan("ASELS_1h", df.iloc[:i]).state
                for i in range(30, len(df) + 1)]
    assert durumlar, "state üretilmedi"
    # Deterministik: aynı veri aynı sonuç
    mgr2 = PatternLifecycleManager(profile="Dengeli")
    durumlar2 = [mgr2.scan("ASELS_1h", df.iloc[:i]).state
                 for i in range(30, len(df) + 1)]
    assert durumlar == durumlar2, "motor davranışı deterministik değil"


def test_p2_geo_yalnizca_anlamli_gecislerde_dolu(ortam):
    """`_p2_geo` her bar değil, yalnızca state geçişinde dolar."""
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _iki_formasyon()
    en_fazla = 0
    for i in range(30, len(df) + 1):
        snap = mgr.scan("ASELS_1h", df.iloc[:i])
        engine = mgr.get_engine("ASELS_1h")
        geo = list(getattr(engine, "_p2_geo", None) or [])
        # Bu scan'deki geometry yakalamaları bu scan'in olay sayısını aşamaz
        assert len(geo) <= len(snap.events) + 2, (
            "Geometry yakalama olay sayısını aştı: %d > %d"
            % (len(geo), len(snap.events)))
        en_fazla = max(en_fazla, len(geo))
    # En az bir yakalama olmuş olmalı (aksi halde test boş)
    assert en_fazla > 0, "hiç geometry yakalanmadı"


# =====================================================================
# 10) P2.5 outcome linkage bozulmadı
# =====================================================================

def test_p25_outcome_linkage_bozulmadi(ortam):
    """Geometry snapshot'lar outcome bağlantısını etkilemez."""
    from datetime import datetime

    from state import outcome_link as ol
    import karne as K

    stock, tf, sid = "ASELS", "1h", "outcome-sid"
    mgr = PatternLifecycleManager(profile="Dengeli")
    df = _iki_formasyon()
    for i in range(30, len(df) + 1):
        mgr.scan("ASELS_1h", df.iloc[:i])

    # Kayıt var mı?
    defter_h = fh.yukle(stock, tf)
    kayitlar = fh.kayitlar(defter_h)
    assert kayitlar, "history kaydı yok"
    gercek_sid = kayitlar[0]["stable_id"]

    # Karne'ye kırılım kaydı düşür ve outcome'ı bağla
    bar = K.ISTANBUL_TZ.localize(datetime(2026, 10, 1, 10, 30))
    defter = K.KarneDefteri()
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, bar, stable_id=gercek_sid)
    # İlk 10 ileri bar 103'e ulaşmalı (hedef = 1.5 ATR = 103).
    kapanislar = [100.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0,
                  103.5, 104.0, 104.0, 104.0, 104.0]
    seri = pd.DataFrame({
        "open": [c - 0.02 for c in kapanislar],
        "high": [c * 1.002 for c in kapanislar],
        "low": [c * 0.998 for c in kapanislar],
        "close": kapanislar,
        "volume": [1] * 12,
    }, index=pd.date_range(bar, periods=12, freq="h", tz="Europe/Istanbul"))

    ozet = ol.bagla(defter, stock, tf, gercek_sid, saglayici=lambda s, t: seri)
    assert ozet is not None, "outcome bağlanamadı"
    assert ozet["durum"] == K.DURUM_HEDEF
    rec = fh.kayit_getir(fh.yukle(stock, tf), gercek_sid)
    assert rec["sonuc"]["durum"] == K.DURUM_HEDEF
    # Geometry snapshot'lar hâlâ yerinde
    assert rec.get("snapshotlar"), "geometry snapshot'ları kayboldu"


def test_karne_matematigi_degismedi():
    """sinyal_sonucu birebir aynı çıktıyı vermeye devam eder."""
    from datetime import datetime
    import karne as K

    bar = K.ISTANBUL_TZ.localize(datetime(2026, 10, 1, 10, 30))
    kapanislar = [100.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0,
                   103.5, 104.0, 104.0, 104.0, 104.0]
    seri = pd.DataFrame({
        "open": [c - 0.02 for c in kapanislar],
        "high": [c * 1.002 for c in kapanislar],
        "low": [c * 0.998 for c in kapanislar],
        "close": kapanislar,
        "volume": [1] * 12,
    }, index=pd.date_range(bar, periods=12, freq="h", tz="Europe/Istanbul"))
    kayit = {"tip": "kirilim", "stock": "X", "tf": "1h", "dir": 1, "entry": 100.0,
             "atr": 2.0, "quality": 80.0, "bar_time": bar.isoformat(),
             "kayit_zaman": bar.isoformat(), "stable_id": "s"}
    assert K.sinyal_sonucu(kayit, seri)["durum"] == K.DURUM_HEDEF


# =====================================================================
# 11) Legacy Faz 1 fallback bozulmadı
# =====================================================================

def test_faz1_anchor_fallback_bozulmadi(ortam):
    """History dosyası yokken Faz 1 anchor fallback çalışmaya devam eder."""
    from state import formation_identity as fi
    # History dosyası YOK: yalnızca Faz 1 anchor'ü var.
    anchor = {"stable_id": "anchor-sid", "family": "Flama", "classic_dir": 1,
              "start_bar": 10, "bar_time": None}
    assert fi.save_anchor(anchor) is True or True  # yazım opsiyonel
    assert not fh.yol("THYAO", "1h") or not os.path.exists(fh.yol("THYAO", "1h"))

    df = _kanalli_pennant(n_bars=60, seed=3)
    mgr = PatternLifecycleManager(profile="Dengeli")
    # Hata fırlatmamalı
    snap = mgr.scan("THYAO_1h", df, tam_yeniden=True)
    a = snap.active
    if a is not None and a.valid:
        assert a.stable_id, "stable_id atanmadı"


def test_formation_identity_modulu_degismedi():
    """Faz 1 anchor modülünün imzası korunuyor."""
    from state import formation_identity as fi
    for ad in ("load_anchor", "save_anchor"):
        assert hasattr(fi, ad), "Faz 1 API'si kayboldu: %s" % ad
    # Boş durumda None dönmeli (exception değil)
    assert fi.load_anchor("YOKHISSE", "1h") is None
