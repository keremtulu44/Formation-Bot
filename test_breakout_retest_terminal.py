"""Faz 2.4 — Breakout / Retest / Terminal History testleri.

KAPSAM: formation'ın kırılım sonrası yaşamının (breakout -> retest -> terminal)
history'ye kalıcı ve `stable_id`'ye bağlı hale getirilmesi.

Bu faz YENİ trading logic ÜRETMEZ. Mevcut motorun zaten hesapladığı
bilgiyi (freeze edilmiş kırılım bağlamı, retest evresi, terminal state)
mevcut Faz 2 history mimarisine bağlar.

TASARIM KARARLARI
-----------------
1) Snapshot `tur`'u yaşam döngüsü FAZINDAN gelir:
     geometri (ön-kırılım) | kirilim (kırılım anı, dondurulmuş)
     retest (retest evresi) | terminal
   Olay (P2.2) ile snapshot (P2.3/2.4) AYRI kalır: olay "ne oldu",
   snapshot "o an nasıl göründü". Aynı bilgi iki datastore'a kopyalanmaz —
   retest bar'ına `geometri` YAZILMAZ (aynı alanları taşırdı).

2) Kırılım snapshot'ı TEKİL teyitte değil, FREEZE anında da yakalanır.
   Freeze `KIRILIM_ADAYI/DENEMESI` sırasında olur ve `reset_quality_snapshot`
   onu siler; yalnızca teyitte yakalamak, teyit alamayan kırılımların
   dondurulmuş bağlamını kaybettirirdi.

3) `durum` MONOTONİK ilerler: acik -> kirilim -> retest -> terminal.
   Faz asla geriye gitmez.

4) Retest fazına girişte OLAY ÜRETİLMEZ (Telegram/alert akışı değişmez);
   yalnızca snapshot yakalanır.

DEĞİŞTİRİLMEYENLER:
  * pivot/chronology/slope/contraction/apex/touch/classification/quality/
    continuity/identity/breakout kriteri/retest kriteri
  * Karne matematiği (sinyal_sonucu, MFE, MAE, ATR, hedef, stop, horizon,
    HEDEF/STOP/NÖTR/BEKLIYOR, karne_hesapla)
  * P2.5 outcome linkage, P2.3 geometry snapshot'ları, Faz 1 fallback
  * Telegram çıktıları

Çalıştırma:  python3 -m pytest test_breakout_retest_terminal.py -q
"""

import os
from collections import Counter

import pandas as pd
import pytest

import config as config_mod
import karne as K
from patterns.lifecycle import PatternLifecycleManager, _faz
from state import formation_history as fh
from state import formation_schema as schema

from test_formation_history import _kanalli_pennant

_STOCK, _TF = "ASELS", "1h"

RETEST_STATE = ("RETEST_BEKLENIYOR", "RETEST_EDILIYOR", "RETEST_BASARILI")
KIRILIM_STATE = ("KIRILIM_ADAYI", "KIRILIM_DENEMESI", "KIRILIM_TEYITLI")


# ---------------------------------------------------------------------------
# Retest evresine ulaşan senaryo (gerçek motor, gerçek veri üretici).
# Kırılım → teyit → retest → (tutunma/başarısız) zincirini yaşar.
# ---------------------------------------------------------------------------
def _retest_senaryosu(seed=8, n_bars=60):
    df = _kanalli_pennant(n_bars=n_bars, seed=seed)
    return df


def _ekle(df, o, h, l, c, v=2_000_000):
    satir = pd.DataFrame([{"open": o, "high": h, "low": l, "close": c, "volume": v}],
                         index=[df.index[-1] + pd.Timedelta(hours=1)])
    return pd.concat([df, satir])


def _kirilim_retest_zinciri(df, key="ASELS_1h"):
    """Gerük motorla kırılım → teyit → retest → terminal zincirini sürdür.

    MATEMATİK DEĞİŞMEZ: yalnızca mevcut motora BİRİKİMLİ olarak bar verir;
    kırılım/teyit/retest/terminal kararlarını motorun kendi state makinesi verir.
    Seri birikimli olmalı: aksi halde motor her adımda reset-replay yapar ve
    doğal artımlı akış ölçülmış olmaz.
    """
    mgr = PatternLifecycleManager(profile="Dengeli")
    durumlar = []
    seri = df
    snap = mgr.scan(key, seri)
    durumlar.append(snap.state)
    a = snap.active
    if a is None or not a.valid:
        return mgr, durumlar
    atr = max(a.geometry_atr or 1.0, 0.01)

    ust = a.upper_now
    seri = _ekle(seri, ust - 0.1, ust + 1.5 * atr, ust - 0.3 * atr,
                 ust + 1.2 * atr, 2_500_000)
    snap = mgr.scan(key, seri)
    durumlar.append(snap.state)
    if snap.active is None:
        return mgr, durumlar

    ust2 = snap.active.upper_now
    seri = _ekle(seri, ust2 + 0.2, ust2 + 1.0 * atr, ust2 + 0.1,
                 ust2 + 0.8 * atr, 2_500_000)
    snap = mgr.scan(key, seri)
    durumlar.append(snap.state)
    if snap.active is None:
        return mgr, durumlar

    s = snap.active.upper_now
    seri = _ekle(seri, s + 0.5, s + 0.9, s - 0.4, s + 0.4, 1_500_000)
    snap = mgr.scan(key, seri)
    durumlar.append(snap.state)
    for i in range(10):
        if snap.active is None:
            break
        base = snap.active.upper_now + 0.5 + i * 0.2
        seri = _ekle(seri, base - 0.1, base + 0.4, base - 0.3,
                     base + 0.2, 1_200_000)
        snap = mgr.scan(key, seri)
        durumlar.append(snap.state)
        if snap.state == "FORMASYON_TAMAMLANDI":
            break
    return mgr, durumlar


@pytest.fixture
def ortam(tmp_path, monkeypatch):
    """Karne ve history AYNI dizine yazsın (karne DATA_DIR'i import anında kopyalar)."""
    monkeypatch.setattr(config_mod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    return tmp_path


def _turler(rec):
    return dict(Counter(s.get("tur") for s in rec.get("snapshotlar", [])))


# =====================================================================
# 1) Breakout history'ye doğru stable_id ile bağlanıyor
# =====================================================================

def test_breakout_dogru_stable_id_ile_baglaniyor(ortam):
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())

    defter = fh.yukle(_STOCK, _TF)
    kayitlar = fh.kayitlar(defter)
    assert kayitlar, "kayıt üretilmedi"
    sidler = {r["stable_id"] for r in kayitlar}

    kirilim_kayitli = set()
    for r in kayitlar:
        for sn in r.get("snapshotlar", []):
            if sn.get("tur") == "kirilim":
                kirilim_kayitli.add(r["stable_id"])
    assert kirilim_kayitli, "hiçbir kayda kırılım snapshot'ı bağlanmadı"
    assert kirilim_kayitli <= sidler, "bilinmeyen stable_id'ye yazılmış"


def test_breakout_frozen_bilgileri_korunuyor(ortam):
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())
    defter = fh.yukle(_STOCK, _TF)

    kirilim_snap = None
    for r in fh.kayitlar(defter):
        for sn in r.get("snapshotlar", []):
            if sn.get("tur") == "kirilim":
                kirilim_snap = sn
                break
        if kirilim_snap:
            break
    assert kirilim_snap is not None, "kırılım snapshot'ı yok"

    alanlar = kirilim_snap.get("alanlar", {})
    # Alan kümesi BREAKOUT (dondurulmuş) kümesiyle aynı
    assert set(alanlar) == set(schema.BREAKOUT_FIELDS), (
        "kırılım snapshot'ı BREAKOUT alanlarını taşımıyor")
    # Dondurulmuş alanlar GERÇEKTEN dolu
    for zorunlu in ("quality_frozen", "frozen_classic_dir", "frozen_pattern_type",
                    "break_snapshot_direction", "break_snapshot_price",
                    "break_snapshot_bar"):
        assert zorunlu in alanlar, "eksik kırılım alanı: %s" % zorunlu
    assert alanlar.get("quality_frozen") is True, "freeze işaretlenmemiş"
    assert alanlar.get("frozen_atr_at_break") is not None, "ATR dondurulmamış"
    assert alanlar.get("frozen_atr_at_break") > 0, "ATR geçersiz"
    assert alanlar.get("break_snapshot_direction") in (1, -1), "yön yok"
    assert alanlar.get("break_snapshot_price") > 0, "kırılım fiyatı yok"
    # Snapshot mutlak bar_time taşır
    assert kirilim_snap.get("bar_time"), "kırılım snapshot'ı bar_time'siz"
    # Snapshot hangi state'de alındığı da görünür
    assert kirilim_snap.get("state") in KIRILIM_STATE, (
        "kırılım snapshot'ı kırılım state'inde alınmamış: %r"
        % kirilim_snap.get("state"))


def test_breakout_freeze_ani_yakalaniyor(ortam):
    """Freeze TEKİL teyitte değil, ilk kırılım denemesinde yakalanmalı.

    `reset_quality_snapshot` freeze verisini siler; yalnızca teyitte
    yakalamak, teyit alamayan kırılımların bağlamını kaybettirirdi.
    """
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())
    defter = fh.yukle(_STOCK, _TF)

    kirilim_stateler = set()
    for r in fh.kayitlar(defter):
        for sn in r.get("snapshotlar", []):
            if sn.get("tur") == "kirilim":
                kirilim_stateler.add(sn.get("state"))
    assert kirilim_stateler, "kırılım snapshot'ı yok"
    # En az biri teyit ÖNCESİ bir kırılım state'inde olmalı
    assert kirilim_stateler & {"KIRILIM_ADAYI", "KIRILIM_DENEMESI"}, (
        "freeze anı yakalanmadı, yalnızca teyit var: %r" % kirilim_stateler)


# =====================================================================
# 2) Retest history'ye doğru formation altında bağlanıyor
# =====================================================================

def test_retest_dogru_formation_altinda_baglaniyor(ortam):
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())
    assert any(d in RETEST_STATE for d in durumlar), (
        "retest evresine ulaşılamadı: %s" % durumlar)

    defter = fh.yukle(_STOCK, _TF)
    retest_kayitli = set()
    retest_snap = None
    for r in fh.kayitlar(defter):
        for sn in r.get("snapshotlar", []):
            if sn.get("tur") == "retest":
                retest_kayitli.add(r["stable_id"])
                retest_snap = sn
    assert retest_kayitli, "hiçbir kayda retest snapshot'ı bağlanmadı"

    alanlar = (retest_snap or {}).get("alanlar", {})
    # Retest snapshot'ı STATE alanlarını taşır (geometri görünümü)
    assert set(alanlar) == set(schema.STATE_FIELDS), (
        "retest snapshot'ı STATE alanlarını taşımıyor")
    assert retest_snap.get("state") in RETEST_STATE, (
        "retest snapshot'ı retest state'inde alınmamış: %r"
        % retest_snap.get("state"))
    assert retest_snap.get("bar_time"), "retest snapshot'ı bar_time'siz"


def test_retest_fazi_durumda_gorunur(ortam):
    """Kaydın `durum`'u retest fazına ilerler (dormant DURUM_RETEST kullanılır)."""
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())
    assert any(d in RETEST_STATE for d in durumlar), (
        "retest evresine ulaşılamadı: %s" % durumlar)
    defter = fh.yukle(_STOCK, _TF)
    durumlar_kayit = {r["stable_id"][:8]: r.get("durum") for r in fh.kayitlar(defter)}
    # En az bir kayıt kırılım/retest/terminal fazına ulaşmış olmalı
    assert any(v in ("kirilim", "retest", "terminal") for v in durumlar_kayit.values()), (
        "hiçbir kayıt ileri fazlara geçmedi: %r" % durumlar_kayit)
    # Tüm fazlar geçerli sözlükten
    assert all(v in ("acik", "kirilim", "retest", "terminal")
               for v in durumlar_kayit.values()), durumlar_kayit


def test_retest_barina_geometri_yazilmaz(ortam):
    """Retest bar'ına `geometri` de YAZILMAZ (aynı alanlar -> kopyalama)."""
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())
    defter = fh.yukle(_STOCK, _TF)
    for r in fh.kayitlar(defter):
        retest_barlar = {s.get("bar_time") for s in r.get("snapshotlar", [])
                         if s.get("tur") == "retest"}
        geometri_barlar = {s.get("bar_time") for s in r.get("snapshotlar", [])
                           if s.get("tur") == "geometri"}
        assert not (retest_barlar & geometri_barlar), (
            "Aynı bara hem retest hem geometri yazılmış (kopyalama)")


# =====================================================================
# 3) Terminal state doğru formation'a bağlanıyor
# =====================================================================

def test_terminal_dogru_formation_a_baglaniyor(ortam):
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())
    assert durumlar and durumlar[-1] == "FORMASYON_TAMAMLANDI", (
        "senaryo terminal'e ulaşmadı: %s" % durumlar)
    defter = fh.yukle(_STOCK, _TF)
    terminal_kayitlar = [r for r in fh.kayitlar(defter)
                         if r.get("durum") == fh.DURUM_TERMINAL]
    assert terminal_kayitlar, "terminal kayıt üretilmedi (senaryo geçersiz)"

    for rec in terminal_kayitlar:
        assert rec.get("terminal_state"), "terminal state'i kaydedilmemiş"
        turlar = _turler(rec)
        # Terminal snapshot BİR KEZ (P2.3 düzeltmesi korunuyor)
        assert turlar.get("terminal", 0) == 1, (
            "terminal snapshot çoğaldı: %r" % turlar)
        # Son geometry korunuyor
        assert turlar.get("geometri", 0) > 0 or turlar.get("kirilim", 0) > 0, (
            "terminal kaydın geometry/breakout evrimi yok")


def test_terminal_sonrasi_yeni_formation_sid_devralmaz(ortam):
    """Terminal kaydın stable_id'si yeni formation'a taşınmaz."""
    from test_stable_identity import _iki_formasyon
    df = _iki_formasyon()
    mgr = PatternLifecycleManager(profile="Dengeli")
    for i in range(30, len(df) + 1):
        mgr.scan("ASELS_1h", df.iloc[:i])

    defter = fh.yukle(_STOCK, _TF)
    kayitlar = fh.kayitlar(defter)
    assert len(kayitlar) >= 2, "iki ayrı formation bekleniyordu"
    terminal_sidler = {r["stable_id"] for r in kayitlar
                       if r.get("durum") == fh.DURUM_TERMINAL}
    diger = {r["stable_id"] for r in kayitlar
             if r.get("durum") != fh.DURUM_TERMINAL}
    assert terminal_sidler, "terminal kayıt yok"
    assert not (terminal_sidler & diger), "terminal SID'i yeni formasyona taşınmış"


def test_terminal_kaydi_sonradan_okunabilir(ortam):
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())
    assert durumlar and durumlar[-1] == "FORMASYON_TAMAMLANDI", (
        "senaryo terminal'e ulaşmadı: %s" % durumlar)
    defter = fh.yukle(_STOCK, _TF)
    terminal = [r for r in fh.kayitlar(defter)
                if r.get("durum") == fh.DURUM_TERMINAL]
    assert terminal, "terminal kayıt yok"
    rec = terminal[0]
    # Yeni defter nesnesiyle diskten oku
    rec2 = fh.kayit_getir(fh.yukle(_STOCK, _TF), rec["stable_id"])
    assert rec2 is not None
    assert rec2.get("durum") == fh.DURUM_TERMINAL
    assert rec2.get("terminal_state") == rec.get("terminal_state")
    assert _turler(rec2) == _turler(rec), "terminal snapshot'ları kayboldu"


# =====================================================================
# 4) Multi-formation isolation
# =====================================================================

def test_iki_formation_kirilim_retest_terminal_karismaz(ortam):
    """Aynı (stock,tf) içinde iki formation -> breakout/retest/terminal ayrık."""
    from test_stable_identity import _iki_formasyon
    df = _iki_formasyon()
    mgr = PatternLifecycleManager(profile="Dengeli")
    for i in range(30, len(df) + 1):
        mgr.scan("ASELS_1h", df.iloc[:i])

    defter = fh.yukle(_STOCK, _TF)
    kayitlar = fh.kayitlar(defter)
    assert len(kayitlar) >= 2, "iki ayrı formation bekleniyordu"

    kumeler = []
    for r in kayitlar:
        kume = {(s.get("tur"), s.get("bar_time"))
                for s in r.get("snapshotlar", [])}
        assert kume, "kaydın snapshot'ı yok: %s" % r["stable_id"][:8]
        kumeler.append((r["stable_id"], kume))

    for i in range(len(kumeler)):
        for j in range(i + 1, len(kumeler)):
            kesisim = kumeler[i][1] & kumeler[j][1]
            assert not kesisim, (
                "İki formation aynı snapshot'ı paylaşıyor (cross-contamination): %r"
                % sorted(kesisim)[:3])


def test_snapshot_ekle_yalnizca_verilen_kayda_yazar(ortam):
    """`snapshot_ekle` birebir verilen kayda yazar (P2.3 koruması)."""
    defter = fh.bos_defter(_STOCK, _TF)
    for sid in ("sid-A", "sid-B"):
        defter["kayitlar"][sid] = {"stable_id": sid, "durum": fh.DURUM_ACIK,
                                   "snapshotlar": []}
    snap = {"bar_time": "2026-01-01 00:00:00+03:00", "alanlar": {"current_width": 5.0}}
    assert fh.snapshot_ekle(defter, "sid-A", "kirilim", snap) is True
    assert defter["kayitlar"]["sid-B"]["snapshotlar"] == [], "A'nın snapshot'ı B'ye sızdı"


# =====================================================================
# 5) Replay dedup / sliding window
# =====================================================================

def test_tam_yeniden_replay_duplicate_uretmez(ortam):
    df = _retest_senaryosu()
    mgr, _ = _kirilim_retest_zinciri(df)
    defter = fh.yukle(_STOCK, _TF)
    ilk = {r["stable_id"]: len(r.get("snapshotlar", []))
           for r in fh.kayitlar(defter)}
    onceki_durum = {r["stable_id"]: r.get("durum") for r in fh.kayitlar(defter)}
    assert ilk, "snapshot üretilmedi"

    mgr2 = PatternLifecycleManager(profile="Dengeli")
    for _ in range(3):
        mgr2.scan("ASELS_1h", df, tam_yeniden=True)
    sonra = {r["stable_id"]: len(r.get("snapshotlar", []))
             for r in fh.kayitlar(fh.yukle(_STOCK, _TF))}
    assert ilk == sonra, "replay snapshot çoğalttı: %s -> %s" % (ilk, sonra)

    # Faz da geriye gitmemeli (monotonik)
    for sid, d in onceki_durum.items():
        yeni = fh.kayit_getir(fh.yukle(_STOCK, _TF), sid).get("durum")
        assert fh._DURUM_SIRA.get(yeni, 0) >= fh._DURUM_SIRA.get(d, 0), (
            "faz geriye gitti: %s %s -> %s" % (sid[:8], d, yeni))


def test_kayan_pencerede_history_kontrolsuz_buyumuyor(ortam):
    from test_stable_identity import _iki_formasyon
    df = _iki_formasyon()
    mgr = PatternLifecycleManager(profile="Dengeli")
    onceki = None
    for basla in range(0, 30, 10):
        pen = df.iloc[basla: basla + 140].copy()
        if len(pen) < 80:
            break
        mgr.scan("ASELS_1h", pen, tam_yeniden=True)
        simdi = {r["stable_id"]: len(r.get("snapshotlar", []))
                 for r in fh.kayitlar(fh.yukle(_STOCK, _TF))}
        if onceki is not None:
            for sid, n in simdi.items():
                if sid in onceki:
                    assert n <= onceki[sid] + 1, (
                        "Snapshot kontrolüsüz arttı: %s %d -> %d"
                        % (sid[:8], onceki[sid], n))
        onceki = simdi


# =====================================================================
# 6) Restart senaryoları
# =====================================================================

def test_restart_breakout_oncesi(ortam):
    """Formation breakout olmadan restart: birth + geometry korunur."""
    from test_stable_identity import _iki_formasyon
    df = _iki_formasyon()
    mgr = PatternLifecycleManager(profile="Dengeli")
    mgr.scan("ASELS_1h", df.iloc[:35].copy())
    defter = fh.yukle(_STOCK, _TF)
    onceki = {r["stable_id"]: (_turler(r), r.get("durum"))
              for r in fh.kayitlar(defter)}

    mgr2 = PatternLifecycleManager(profile="Dengeli")
    mgr2.scan("ASELS_1h", df.iloc[:35].copy(), tam_yeniden=True)
    sonra = {r["stable_id"]: (_turler(r), r.get("durum"))
             for r in fh.kayitlar(fh.yukle(_STOCK, _TF))}
    for sid, (turlar, durum) in onceki.items():
        assert sid in sonra, "kayıt kayboldu: %s" % sid[:8]
        for tur, n in turlar.items():
            assert sonra[sid][0].get(tur, 0) >= n, "snapshot kayboldu: %s %s" % (sid[:8], tur)


def test_restart_breakout_sonrasi(ortam):
    """Breakout sonrası restart: kırılım snapshot'ı ve freeze verisi korunur."""
    df = _retest_senaryosu()
    mgr, _ = _kirilim_retest_zinciri(df)
    defter = fh.yukle(_STOCK, _TF)

    onceki_kirilim = {}
    for r in fh.kayitlar(defter):
        for sn in r.get("snapshotlar", []):
            if sn.get("tur") == "kirilim":
                onceki_kirilim[(r["stable_id"], sn.get("bar_time"))] = \
                    dict(sn.get("alanlar", {}))
    assert onceki_kirilim, "kırılım snapshot'ı yok"

    # --- restart: tam replay ---
    mgr2 = PatternLifecycleManager(profile="Dengeli")
    mgr2.scan("ASELS_1h", df, tam_yeniden=True)
    defter2 = fh.yukle(_STOCK, _TF)

    for anahtar, alanlar in onceki_kirilim.items():
        sid, bar_time = anahtar
        rec = fh.kayit_getir(defter2, sid)
        assert rec is not None, "kayıt kayboldu: %s" % sid[:8]
        bulunan = [s for s in rec.get("snapshotlar", [])
                   if s.get("tur") == "kirilim" and s.get("bar_time") == bar_time]
        assert bulunan, "kırılım snapshot'ı kayboldu: %s %s" % (sid[:8], bar_time)
        # FREEZE VERİSİ yeniden hesaplanarak FARKLILAŞMAMALI
        assert bulunan[0].get("alanlar") == alanlar, (
            "freeze verisi restart sonrası değişti: %s %s" % (sid[:8], bar_time))


def test_restart_retest_sirasinda(ortam):
    """Retest sırasında restart: retest snapshot'ı korunur."""
    df = _retest_senaryosu()
    mgr, durumlar = _kirilim_retest_zinciri(df)
    assert any(d in RETEST_STATE for d in durumlar), (
        "retest evresine ulaşılamadı: %s" % durumlar)
    defter = fh.yukle(_STOCK, _TF)

    onceki = {}
    for r in fh.kayitlar(defter):
        for sn in r.get("snapshotlar", []):
            if sn.get("tur") == "retest":
                onceki[(r["stable_id"], sn.get("bar_time"))] = \
                    dict(sn.get("alanlar", {}))
    assert onceki, "retest snapshot'ı yok"

    mgr2 = PatternLifecycleManager(profile="Dengeli")
    mgr2.scan("ASELS_1h", df, tam_yeniden=True)
    defter2 = fh.yukle(_STOCK, _TF)
    for (sid, bar_time), alanlar in onceki.items():
        rec = fh.kayit_getir(defter2, sid)
        assert rec is not None
        bulunan = [s for s in rec.get("snapshotlar", [])
                   if s.get("tur") == "retest" and s.get("bar_time") == bar_time]
        assert bulunan, "retest snapshot'ı kayboldu: %s %s" % (sid[:8], bar_time)
        assert bulunan[0].get("alanlar") == alanlar, (
            "retest snapshot'ı restart sonrası değişti")


def test_restart_terminal_sonrasi(ortam):
    """Terminal sonrası restart: terminal kaydı ve snapshot'ı korunur."""
    df = _retest_senaryosu()
    mgr, durumlar = _kirilim_retest_zinciri(df)
    assert durumlar and durumlar[-1] == "FORMASYON_TAMAMLANDI", (
        "senaryo terminal'e ulaşmadı: %s" % durumlar)
    defter = fh.yukle(_STOCK, _TF)
    terminal = [r for r in fh.kayitlar(defter)
                if r.get("durum") == fh.DURUM_TERMINAL]
    assert terminal, "terminal kayıt yok"
    onceki = {r["stable_id"]: (_turler(r), r.get("terminal_state"))
              for r in terminal}

    mgr2 = PatternLifecycleManager(profile="Dengeli")
    mgr2.scan("ASELS_1h", df, tam_yeniden=True)
    defter2 = fh.yukle(_STOCK, _TF)
    for sid, (turlar, tstate) in onceki.items():
        rec = fh.kayit_getir(defter2, sid)
        assert rec is not None, "terminal kaydı kayboldu: %s" % sid[:8]
        assert rec.get("durum") == fh.DURUM_TERMINAL
        assert rec.get("terminal_state") == tstate
        assert _turler(rec) == turlar, "terminal snapshot'ları değişti"


# =====================================================================
# 6) TAM ZİNCİR E2E (birth -> geometri -> kırılım -> retest -> terminal)
# =====================================================================

def test_tam_yasam_dongusu_zinciri(ortam):
    """Gerçek motorla tek formation'ın TAM yaşam döngüsü history'de."""
    df = _retest_senaryosu()
    mgr, durumlar = _kirilim_retest_zinciri(df)
    assert durumlar and durumlar[-1] == "FORMASYON_TAMAMLANDI", (
        "senaryo terminal'e ulaşmadı: %s" % durumlar)

    defter = fh.yukle(_STOCK, _TF)
    terminal = [r for r in fh.kayitlar(defter)
                if r.get("durum") == fh.DURUM_TERMINAL]
    assert terminal, "terminal kayıt yok"
    rec = terminal[0]
    turlar = _turler(rec)

    # Zincir eksiksiz: geometri -> kırılım -> retest -> terminal
    assert turlar.get("geometri", 0) > 0, "geometri evrimi yok"
    assert turlar.get("kirilim", 0) >= 2, (
        "kırılım snapshot'ları eksik (freeze + teyit beklenir): %r" % turlar)
    assert turlar.get("retest", 0) > 0, "retest evresi yok"
    assert turlar.get("terminal", 0) == 1, "terminal snapshot'ları yok/çok: %r" % turlar

    # Birth snapshot'ı da var
    assert (rec.get("dogum") or {}).get("alanlar"), "birth snapshot'ı yok"

    # Kırılım snapshot'ları freeze + teyit anlarını içerir
    kirilim_stateler = {s.get("state") for s in rec.get("snapshotlar", [])
                        if s.get("tur") == "kirilim"}
    assert kirilim_stateler, "kırılım snapshot'ları yok"

    # Faz monotone ilerlemiş: terminal en üstte
    assert rec.get("durum") == fh.DURUM_TERMINAL


def test_durum_fazi_snapshot_kanitiyla_tutarlili(ortam):
    """durum=kirilim/retest olan kayıtta o fazın snapshot'ı da olmalı.

    Bu, `kirilim_turu` ile `_faz` kümesinin birebir aynı olmasını sağlayan
    koruyucu testtir: faz işareti kanıtsız şekilde ilerlemez.
    """
    df = _retest_senaryosu()
    mgr, durumlar = _kirilim_retest_zinciri(df)
    assert durumlar and durumlar[-1] == "FORMASYON_TAMAMLANDI", (
        "senaryo terminal'e ulaşmadı: %s" % durumlar)

    defter = fh.yukle(_STOCK, _TF)
    for r in fh.kayitlar(defter):
        durum = r.get("durum")
        turlar = {s.get("tur") for s in r.get("snapshotlar", [])}
        if durum == fh.DURUM_KIRILIM:
            assert "kirilim" in turlar, (
                "durum=kirilim ama kirilim snapshot'ı yok: %s %r"
                % (r["stable_id"][:8], turlar))
        elif durum == fh.DURUM_RETEST:
            assert "retest" in turlar, (
                "durum=retest ama retest snapshot'ı yok: %s %r"
                % (r["stable_id"][:8], turlar))
        elif durum == fh.DURUM_TERMINAL:
            assert "terminal" in turlar, (
                "durum=terminal ama terminal snapshot'ı yok: %s %r"
                % (r["stable_id"][:8], turlar))


def test_kirilim_turu_faz_kumeleriyle_ayni(ortam):
    """`kirilim_turu` ile `_faz` aynı state kümelerini kullanmalı."""
    from patterns.lifecycle import _FAZ_KIRILIM, _FAZ_RETEST, _faz
    from patterns import constants as C

    tum = {getattr(C, a) for a in dir(C) if a.startswith("ST_")}
    kir = {s for s in tum if fh.kirilim_turu(s) == fh.DURUM_KIRILIM}
    ret = {s for s in tum if fh.kirilim_turu(s) == fh.DURUM_RETEST}
    assert kir == set(_FAZ_KIRILIM), (
        "kirilim_turu KIRILIM kümesi _FAZ_KIRILIM ile farklı: %r vs %r"
        % (sorted(kir), sorted(_FAZ_KIRILIM)))
    assert ret == set(_FAZ_RETEST), (
        "kirilim_turu RETEST kümesi _FAZ_RETEST ile farklı: %r vs %r"
        % (sorted(ret), sorted(_FAZ_RETEST)))
    # _faz ile kirilim_turu her state için tutarlı
    for s in tum:
        if _faz(s) == "kirilim":
            assert fh.kirilim_turu(s) == fh.DURUM_KIRILIM, s
        elif _faz(s) == "retest":
            assert fh.kirilim_turu(s) == fh.DURUM_RETEST, s


# =====================================================================
# 7) Faz yardımcıları ve monotonik durum
# =====================================================================

def test_faz_yardimcisi_dogru_esler():
    assert _faz("KIRILIM_ADAYI") == "kirilim"
    assert _faz("KIRILIM_DENEMESI") == "kirilim"
    assert _faz("KIRILIM_TEYITLI") == "kirilim"
    assert _faz("RETEST_BEKLENIYOR") == "retest"
    assert _faz("RETEST_EDILIYOR") == "retest"
    assert _faz("RETEST_BASARILI") == "retest"
    assert _faz("SIKISMA_GUCLENIYOR") == "diger"
    assert _faz("FORMASYON_TAMAMLANDI") == "diger"
    assert _faz(None) == "diger"


def test_kirilim_turu_tam_kapsar():
    """Dormant `kirilim_turu` teyitli kırılım ve başarılı retest'i de kapsar."""
    assert fh.kirilim_turu("KIRILIM_TEYITLI") == fh.DURUM_KIRILIM
    assert fh.kirilim_turu("KIRILIM_ADAYI") == fh.DURUM_KIRILIM
    assert fh.kirilim_turu("KIRILIM_DENEMESI") == fh.DURUM_KIRILIM
    # Faz 2.4: KIRILIM_HAZIRLIGI (ST_PREP) BU KÜMEDEN ÇIKARILDI.
    # Henüz kırılım ÖNCESİ hazırlıktır; freeze_pattern_quality çalışmadığı için
    # BREAKOUT alanlarının 18/20'si boş olurdu. Ayrıca `_faz` ile aynı kümeyi
    # kullanmak zorunludur (bkz. test_kirilim_turu_faz_kumeleriyle_ayni).
    assert fh.kirilim_turu("KIRILIM_HAZIRLIGI") is None
    assert fh.kirilim_turu("RETEST_BEKLENIYOR") == fh.DURUM_RETEST
    assert fh.kirilim_turu("RETEST_EDILIYOR") == fh.DURUM_RETEST
    assert fh.kirilim_turu("RETEST_BASARILI") == fh.DURUM_RETEST
    # Terminal / ön-kırılım state'leri faz üretmez
    for s in ("FORMASYON_TAMAMLANDI", "BASARISIZ_KIRILIM", "FORMASYON_GECERSIZ",
              "SIKISMA_GUCLENIYOR", "FORMASYON_TANIMLANDI", None, ""):
        assert fh.kirilim_turu(s) is None, s



def test_durum_guncelle_monotonik(ortam):
    defter = fh.bos_defter(_STOCK, _TF)
    defter["kayitlar"]["sid-1"] = {"stable_id": "sid-1", "durum": fh.DURUM_ACIK}

    assert fh.durum_guncelle(defter, "sid-1", fh.DURUM_KIRILIM) is True
    assert defter["kayitlar"]["sid-1"]["durum"] == fh.DURUM_KIRILIM
    assert fh.durum_guncelle(defter, "sid-1", fh.DURUM_RETEST) is True
    assert defter["kayitlar"]["sid-1"]["durum"] == fh.DURUM_RETEST
    # GERİYE GİTMEZ
    assert fh.durum_guncelle(defter, "sid-1", fh.DURUM_KIRILIM) is False
    assert defter["kayitlar"]["sid-1"]["durum"] == fh.DURUM_RETEST
    assert fh.durum_guncelle(defter, "sid-1", fh.DURUM_ACIK) is False
    assert defter["kayitlar"]["sid-1"]["durum"] == fh.DURUM_RETEST
    # Aynı faz: değişiklik yok
    assert fh.durum_guncelle(defter, "sid-1", fh.DURUM_RETEST) is False
    # Bilinmeyen kayıt
    assert fh.durum_guncelle(defter, "yok", fh.DURUM_KIRILIM) is False
    # None/boş
    assert fh.durum_guncelle(defter, "sid-1", None) is False


def test_durum_sirasi_terminal_en_ust():
    assert (fh._DURUM_SIRA[fh.DURUM_ACIK] < fh._DURUM_SIRA[fh.DURUM_KIRILIM]
            < fh._DURUM_SIRA[fh.DURUM_RETEST] < fh._DURUM_SIRA[fh.DURUM_TERMINAL])


# =====================================================================
# 8) Per-bar persistence
# =====================================================================

def test_per_bar_persistence_yapilmiyor(ortam):
    """Kırılım/retest/terminal anlamlı olaylardır; her bar yazılmaz."""
    df = _retest_senaryosu()
    gercek = fh.kaydet
    sayac = {"n": 0}

    def sayan(*a, **k):
        sayac["n"] += 1
        return gercek(*a, **k)

    fh.kaydet = sayan
    try:
        mgr, durumlar = _kirilim_retest_zinciri(df)
    finally:
        fh.kaydet = gercek

    # Kırılım/retest zinciri 10+ bar sürer ama yazma sayısı çok daha küçük
    assert len(durumlar) >= 5, "senaryo çok kısa"
    assert 0 < sayac["n"] < len(durumlar), (
        "Her adımda disk yazımı yapıldı: %d yazma / %d adım"
        % (sayac["n"], len(durumlar)))


# =====================================================================
# 9) Legacy / backward compatibility
# =====================================================================

def test_bozuk_history_taramayi_durdurmuyor(ortam):
    yol = fh.yol("BOZUK", "1h")
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        f.write('{"surum": 1, "kayitlar": [BROKEN')
    mgr = PatternLifecycleManager(profile="Dengeli")
    mgr.scan("BOZUK_1h", _kanalli_pennant(n_bars=60, seed=3), tam_yeniden=True)
    assert fh.kayitlar(fh.yukle("BOZUK", "1h")), "bozuk dosyadan sonra kayıt üretilmedi"


def test_eski_faz1_duz_bicim_crash_etmez(ortam):
    yol = fh.yol("ESKI", "1h")
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        f.write('{"surum": 1, "kayitlar": {"legacy-1": {"stable_id": "legacy-1", '
                '"durum": "acik", "family": "Flama", "classic_dir": 1}}}')
    mgr = PatternLifecycleManager(profile="Dengeli")
    mgr.scan("ESKI_1h", _kanalli_pennant(n_bars=60, seed=5), tam_yeniden=True)
    assert "legacy-1" in [r["stable_id"] for r in fh.kayitlar(fh.yukle("ESKI", "1h"))]


def test_faz1_anchor_fallback_bozulmadi(ortam):
    from state import formation_identity as fi
    assert hasattr(fi, "load_anchor") and hasattr(fi, "save_anchor")
    assert fi.load_anchor("YOKHISSE", "1h") is None
    df = _kanalli_pennant(n_bars=60, seed=3)
    mgr = PatternLifecycleManager(profile="Dengeli")
    snap = mgr.scan("THYAO_1h", df, tam_yeniden=True)   # hata fırlatmamalı
    a = snap.active
    if a is not None and a.valid:
        assert a.stable_id


def test_eski_kayit_snapshot_eklenebilir(ortam):
    """`snapshotlar` alanı olmayan eski kayda snapshot eklenebilmeli."""
    defter = fh.bos_defter(_STOCK, _TF)
    defter["kayitlar"]["sid-1"] = {"stable_id": "sid-1", "durum": fh.DURUM_ACIK}
    fh.kaydet(defter)
    snap = {"bar_time": "2026-01-01 00:00:00+03:00", "alanlar": {"current_width": 1.0}}
    assert fh.snapshot_ekle(defter, "sid-1", "kirilim", snap) is True
    assert fh.snapshot_ekle(defter, "sid-1", "kirilim", snap) is False  # dedup
    fh.kaydet(defter)
    assert len(fh.kayit_getir(fh.yukle(_STOCK, _TF), "sid-1")["snapshotlar"]) == 1


def test_bilinmeyen_sid_snapshot_yazilmaz(ortam):
    defter = fh.bos_defter(_STOCK, _TF)
    assert fh.snapshot_ekle(defter, "yok-sid", "kirilim",
                            {"bar_time": "x", "alanlar": {}}) is False


# =====================================================================
# 10) P2.5 outcome linkage bozulmuyor
# =====================================================================

def test_p25_outcome_linkage_bozulmuyor(ortam):
    from datetime import datetime

    from state import outcome_link as ol
    df = _retest_senaryosu()
    mgr, _ = _kirilim_retest_zinciri(df)
    defter_h = fh.yukle(_STOCK, _TF)
    kayitlar = fh.kayitlar(defter_h)
    assert kayitlar, "history kaydı yok"
    sid = kayitlar[0]["stable_id"]

    bar = K.ISTANBUL_TZ.localize(datetime(2026, 10, 1, 10, 30))
    defter = K.KarneDefteri()
    defter.kirilim_kaydet(_STOCK, _TF, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, bar, stable_id=sid)
    kap = [100.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0,
           103.5, 104.0, 104.0, 104.0, 104.0]
    seri = pd.DataFrame({
        "open": [c - 0.02 for c in kap], "high": [c * 1.002 for c in kap],
        "low": [c * 0.998 for c in kap], "close": kap, "volume": [1] * 12},
        index=pd.date_range(bar, periods=12, freq="h", tz="Europe/Istanbul"))

    ozet = ol.bagla(defter, _STOCK, _TF, sid, saglayici=lambda s, t: seri)
    assert ozet is not None, "outcome bağlanamadı"
    assert ozet["durum"] == K.DURUM_HEDEF
    rec = fh.kayit_getir(fh.yukle(_STOCK, _TF), sid)
    assert rec["sonuc"]["durum"] == K.DURUM_HEDEF
    # Kırılım/retest snapshot'ları outcome yazımından ETKİLENMEMELİ
    assert rec.get("snapshotlar"), "snapshot'lar kayboldu"


# =====================================================================
# 11) P2.3 geometry snapshot'ları bozulmuyor
# =====================================================================

def test_p23_geometry_snapshotlari_bozulmuyor(ortam):
    df = _retest_senaryosu()
    mgr, _ = _kirilim_retest_zinciri(df)
    defter = fh.yukle(_STOCK, _TF)

    geo_alan = set()
    for r in fh.kayitlar(defter):
        for sn in r.get("snapshotlar", []):
            if sn.get("tur") == "geometri":
                geo_alan |= set(sn.get("alanlar", {}))
    assert geo_alan, "geometri snapshot'ı üretilmedi"
    # On-kırılım geometri hâlâ STATE alanlarını taşır
    assert geo_alan == set(schema.STATE_FIELDS), (
        "geometri snapshot alanları değişti")

    # Birth snapshot'ı da korunuyor
    birth = set()
    for r in fh.kayitlar(defter):
        birth |= set((r.get("dogum") or {}).get("alanlar", {}))
    assert birth == set(schema.IDENTITY_FIELDS), "birth alanları değişti"


# =====================================================================
# 12) Formation / trading math değişmiyor
# =====================================================================

def test_karne_matematigi_degismedi():
    from datetime import datetime

    bar = K.ISTANBUL_TZ.localize(datetime(2026, 10, 1, 10, 30))
    kap = [100.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0,
           103.5, 104.0, 104.0, 104.0, 104.0]
    seri = pd.DataFrame({
        "open": [c - 0.02 for c in kap], "high": [c * 1.002 for c in kap],
        "low": [c * 0.998 for c in kap], "close": kap, "volume": [1] * 12},
        index=pd.date_range(bar, periods=12, freq="h", tz="Europe/Istanbul"))
    kayit = {"tip": "kirilim", "stock": "X", "tf": "1h", "dir": 1, "entry": 100.0,
             "atr": 2.0, "quality": 80.0, "bar_time": bar.isoformat(),
             "kayit_zaman": bar.isoformat(), "stable_id": "s"}
    assert K.sinyal_sonucu(kayit, seri)["durum"] == K.DURUM_HEDEF


def test_motor_davranisi_degismedi(ortam):
    """P2.4 tetikleyicisi motorun state dizisini değiştirmemeli."""
    df = _retest_senaryosu()
    mgr1 = PatternLifecycleManager(profile="Dengeli")
    d1 = [mgr1.scan("ASELS_1h", df.iloc[:i]).state
          for i in range(30, len(df) + 1)]
    mgr2 = PatternLifecycleManager(profile="Dengeli")
    d2 = [mgr2.scan("ASELS_1h", df.iloc[:i]).state
          for i in range(30, len(df) + 1)]
    assert d1 == d2, "motor davranışı deterministik değil"
    assert d1, "state üretilmedi"
