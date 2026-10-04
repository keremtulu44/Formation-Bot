"""Faz 2.6 Regression & Integration Testleri: Durable Mirror, Queue, Hydration & Repository.

Kapsam (Gereksinim 27):
    A. Schema: Tablo şeması, TEXT bar_time ve unique dedup kısıtları
    B. Mirror: Yeni formation, snapshot, event ve outcome satırlarının üretimi
    C. Idempotency: Duplicate kayıt gönderiminde tekillik
    D. Terminal amplification: Tekrarlanan taramada sahte disk/mirror yazımı yok
    E. Supabase down: Supabase erişilemezken bot ve local history kesintisiz çalışır
    F. Queue: Bellek/disk kuyruğu, restart kurtarma, tavan koruması ve backoff
    G. Hydration (EN KRİTİK): Local history yokken Supabase'ten hydrate edilen kayıt
       eslestir() tarafından aynı stable_id ile eşleştirilir; len(unique(sid)) == 1
    H. bar_time regression: TEXT formatı birebir korunur (kesinlikle ISO 'T' yapılmaz)
    I. Type regression: BAR_ALANLARI int tip güvenliği ve identity_compatible uyumu
    J. Multi-formation: Çoklu formasyon sahiplik izolasyonu ve hydrate tutarlılığı
    K. Terminal: Terminal formation eslestir() ile re-attach edilmez; yeniye yeni SID
    L. Restart: Supabase recovery sonrası zincir stable_id sahipliği korunur
    M. Repository: LocalFormationRepository temel API testleri
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional
from unittest import mock

import pandas as pd
import pytest

import config as config_mod
import karne as K
from patterns.lifecycle import PatternLifecycleManager
from state import formation_history as fh
from state import formation_schema as schema
from state.formation_mirror import (
    BAR_ALANLARI,
    KUYRUK_DOSYA_ADI,
    FormationMirrorQueue,
    LocalFormationRepository,
    defter_fingerprint,
    extract_diff,
    get_mirror_queue,
    hydrate_stock_tf,
    mirror_kaydet,
)
from test_breakout_retest_terminal import (
    _STOCK,
    _TF,
    _iki_tam_zincir,
    _kirilim_retest_zinciri,
    _retest_senaryosu,
    ortam,  # noqa: F401
)


class FakeSupabaseResponse:
    def __init__(self, data: Any, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data


class FakeSupabaseStore:
    """Supabase REST API'sini simüle eden in-memory mock store."""

    def __init__(self):
        self.enabled = True
        self.tables: Dict[str, List[Dict[str, Any]]] = {
            "f2_formations": [],
            "f2_snapshots": [],
            "f2_events": [],
            "f2_outcome_links": [],
        }
        self.call_history: List[Dict[str, Any]] = []

    def request_table(self, table_name: str, method: str, *, params=None, json=None, headers=None):
        self.call_history.append({
            "table": table_name,
            "method": method,
            "params": params,
            "json": json,
            "headers": headers,
        })
        if not self.enabled:
            return None

        if method == "POST":
            # on_conflict dedup simülasyonu
            table = self.tables.setdefault(table_name, [])
            rows = json if isinstance(json, list) else [json]
            for row in rows:
                if table_name == "f2_formations":
                    # PK: stable_id -> upsert/merge
                    idx = next((i for i, r in enumerate(table) if r["stable_id"] == row["stable_id"]), None)
                    if idx is not None:
                        table[idx].update(row)
                    else:
                        table.append(dict(row))
                elif table_name == "f2_snapshots":
                    # Unique: (stable_id, tur, bar_time) -> ignore-duplicates
                    exists = any(
                        r["stable_id"] == row["stable_id"]
                        and r["tur"] == row["tur"]
                        and r["bar_time"] == row["bar_time"]
                        for r in table
                    )
                    if not exists:
                        table.append(dict(row))
                elif table_name == "f2_events":
                    # Unique: (stable_id, type, name, bar, bar_time) -> ignore-duplicates
                    exists = any(
                        r["stable_id"] == row["stable_id"]
                        and r["type"] == row["type"]
                        and r["name"] == row["name"]
                        and r["bar"] == row["bar"]
                        and r["bar_time"] == row["bar_time"]
                        for r in table
                    )
                    if not exists:
                        table.append(dict(row))
                elif table_name == "f2_outcome_links":
                    # PK: stable_id -> merge-duplicates
                    idx = next((i for i, r in enumerate(table) if r["stable_id"] == row["stable_id"]), None)
                    if idx is not None:
                        table[idx].update(row)
                    else:
                        table.append(dict(row))
            return FakeSupabaseResponse([], status_code=201)

        elif method == "GET":
            table = self.tables.get(table_name, [])
            filtered = list(table)
            if params:
                if "stock" in params:
                    val = params["stock"].replace("eq.", "")
                    filtered = [r for r in filtered if r.get("stock") == val]
                if "timeframe" in params:
                    val = params["timeframe"].replace("eq.", "")
                    filtered = [r for r in filtered if r.get("timeframe") == val]
                if "stable_id" in params and params["stable_id"].startswith("in.("):
                    sids = params["stable_id"][4:-1].split(",")
                    filtered = [r for r in filtered if r.get("stable_id") in sids]
            return FakeSupabaseResponse(filtered, status_code=200)

        return FakeSupabaseResponse([], status_code=200)


# ============================================================================
# A. SCHEMA & TEXT bar_time
# ============================================================================

def test_supabase_schema_sql_bar_time_ve_constraints():
    """SQL şema dosyasında bar_time kolonlarının TEXT olduğu ve unique kısıtları doğrulanır."""
    with open("supabase_schema.sql", "r", encoding="utf-8") as f:
        sql = f.read()

    assert "dogum_bar_time     text" in sql or "dogum_bar_time text" in sql, "dogum_bar_time TEXT olmalıdır"
    assert "bar_time                   text not null" in sql or "bar_time text not null" in sql, "snapshot bar_time TEXT olmalıdır"
    assert "bar_time   text" in sql or "bar_time text" in sql, "event bar_time TEXT olmalıdır"
    assert "timestamptz" not in sql.split("dogum_bar_time")[1].split("\n")[0], "dogum_bar_time kesinlikle timestamptz olmamalıdır"

    # Unique constraint kontrolü
    assert "f2_snapshots_dedup_tek unique (stable_id, tur, bar_time)" in sql
    assert "f2_events_dedup_tek unique (stable_id, type, name, bar, bar_time)" in sql


# ============================================================================
# B. MIRROR DIFF EXTRACTION
# ============================================================================

def test_mirror_extract_diff_yapisi(ortam):
    """Yerel defterden çıkarılan diff 4 tablo için doğru ve kayıpsız olmalıdır."""
    df = _retest_senaryosu()
    mgr, _ = _kirilim_retest_zinciri(df)
    defter = fh.yukle(_STOCK, _TF)

    diff = extract_diff(defter)
    assert len(diff["f2_formations"]) == 1
    form = diff["f2_formations"][0]
    sid = form["stable_id"]

    assert form["stock"] == _STOCK
    assert form["timeframe"] == _TF
    assert form["family"] in ("Pennant", "Flama")
    assert isinstance(form["dogum_bar_time"], str)
    assert " " in form["dogum_bar_time"], "bar_time string formatında boşluk olmalıdır"
    assert isinstance(form["dogum_bar_index"], int)
    assert form["raw_quality"] is not None

    # Snapshot kontrolü
    assert len(diff["f2_snapshots"]) >= 4
    for s in diff["f2_snapshots"]:
        assert s["stable_id"] == sid
        assert s["tur"] in ("geometri", "kirilim", "retest", "terminal")
        assert isinstance(s["bar_time"], str)
        assert isinstance(s["alanlar"], dict)

    # Event kontrolü
    assert len(diff["f2_events"]) >= 1
    for ev in diff["f2_events"]:
        assert ev["stable_id"] == sid
        assert ev["type"] is not None
        assert ev["name"] is not None


# ============================================================================
# C. IDEMPOTENCY
# ============================================================================

def test_mirror_idempotency_duplicate_kayitlar(ortam):
    """Aynı diff 1x, 2x, 5x gönderildiğinde Supabase'te tek kayıt kalır."""
    df = _retest_senaryosu()
    mgr, _ = _kirilim_retest_zinciri(df)
    defter = fh.yukle(_STOCK, _TF)
    diff = extract_diff(defter)

    store = FakeSupabaseStore()
    queue = FormationMirrorQueue(data_dir=config_mod.DATA_DIR)

    # 5 kez ekle ve flush et
    for _ in range(5):
        queue.enqueue_diff(diff)
        queue.flush(store)

    assert len(store.tables["f2_formations"]) == 1
    # Snapshot sayısı orijinal tekil snapshot sayısına eşit olmalıdır
    ozgun_snap_sayisi = len(diff["f2_snapshots"])
    assert len(store.tables["f2_snapshots"]) == ozgun_snap_sayisi
    ozgun_event_sayisi = len(diff["f2_events"])
    assert len(store.tables["f2_events"]) == ozgun_event_sayisi


# ============================================================================
# D. TERMINAL WRITE AMPLIFICATION
# ============================================================================

def test_terminal_formation_repeated_scan_amplification_yok(ortam):
    """Aynı terminal formation 5 kez tekrar tarandığında 0 disk yazımı üretir."""
    df = _retest_senaryosu()
    mgr, durumlar = _kirilim_retest_zinciri(df)
    assert "FORMASYON_TAMAMLANDI" in durumlar

    sayac = {"kaydet": 0}
    gercek_kaydet = fh.kaydet

    def sayan(d, dd=None):
        sayac["kaydet"] += 1
        return gercek_kaydet(d, dd)

    with mock.patch.object(fh, "kaydet", sayan):
        for _ in range(5):
            mgr.scan(f"{_STOCK}_{_TF}", df, tam_yeniden=True)

    assert sayac["kaydet"] == 0, (
        "Terminal formation her taramada tekrar yazıldı: %d yazma" % sayac["kaydet"]
    )


# ============================================================================
# E. SUPABASE DOWN / ISOLATION
# ============================================================================

def test_supabase_down_iken_bot_kesintisiz_calisir(ortam):
    """Supabase tamamen kapalı/hata veriyorken bot ve local history kesintisiz çalışır."""
    df = _retest_senaryosu()
    store = FakeSupabaseStore()
    store.enabled = False  # Down

    # mirror_kaydet exception fırlatmamalı
    defter = fh.bos_defter(_STOCK, _TF)
    res = mirror_kaydet(defter, store=store, data_dir=config_mod.DATA_DIR)
    assert res == 0

    # Motor çalışmaya devam eder
    mgr, durumlar = _kirilim_retest_zinciri(df)
    assert "FORMASYON_TAMAMLANDI" in durumlar

    # Local history başarıyla yazılmıştır
    rec = fh.kayitlar(fh.yukle(_STOCK, _TF))[0]
    assert rec["durum"] == fh.DURUM_TERMINAL


# ============================================================================
# F. QUEUE: BELLEK, DISK, TAVAN VE RECOVERY
# ============================================================================

def test_queue_bellek_disk_ve_recovery(ortam):
    """Kuyruk diske kaydedilir, süreç yeniden başladığında diskten geri yüklenir."""
    data_dir = config_mod.DATA_DIR
    q1 = FormationMirrorQueue(data_dir=data_dir)
    diff = {
        "f2_formations": [{"stable_id": "test-1", "stock": "THYAO", "timeframe": "1h"}],
        "f2_snapshots": [],
        "f2_events": [],
        "f2_outcome_links": [],
    }
    q1.enqueue_diff(diff)
    assert q1.size() == 1
    assert os.path.isfile(os.path.join(data_dir, KUYRUK_DOSYA_ADI))

    # Yeni queue nesnesi diskten kurtarmalı
    q2 = FormationMirrorQueue(data_dir=data_dir)
    assert q2.size() == 1

    # Flush sonrası boşalmalı
    store = FakeSupabaseStore()
    gonderilen = q2.flush(store)
    assert gonderilen == 1
    assert q2.size() == 0
    assert len(store.tables["f2_formations"]) == 1


def test_queue_tavan_asimi_guvenligi(ortam):
    """Kuyruk MAX_QUEUE_ITEMS sınırını aşarsa en eskileri atar, botu asla çökertmez."""
    q = FormationMirrorQueue(data_dir=config_mod.DATA_DIR)
    # Tavanı geçici olarak küçük tut
    with mock.patch("state.formation_mirror.MAX_QUEUE_ITEMS", 10):
        fazla_diff = {
            "f2_formations": [{"stable_id": f"s-{i}", "stock": "ASELS", "timeframe": "1h"} for i in range(25)],
            "f2_snapshots": [],
            "f2_events": [],
            "f2_outcome_links": [],
        }
        q.enqueue_diff(fazla_diff)
        assert q.size() <= 10


# ============================================================================
# G. HYDRATION — EN KRİTİK E2E REGRESSION TESTİ
# ============================================================================

def test_hydration_local_yok_supabase_var_eslestir_ayni_sid(ortam):
    """EN KRİTİK GEREKSİNİM:
    1. Formation sürülür ve Supabase'e aktarılır.
    2. Local history TAMAMEN silinir (redeploy simülasyonu).
    3. Supabase'ten hydrate edilir.
    4. Yeni taramada eslestir() AYNI stable_id'yi bulur.
    5. len(unique(stable_id)) == 1.
    """
    df = _retest_senaryosu()
    mgr = PatternLifecycleManager(profile="Dengeli")
    snap1 = mgr.scan(f"{_STOCK}_{_TF}", df)
    assert snap1.active is not None and snap1.active.valid
    orijinal_sid = snap1.active.stable_id
    assert orijinal_sid is not None

    # 1) Supabase'e mirror et
    defter = fh.yukle(_STOCK, _TF)
    diff = extract_diff(defter)
    store = FakeSupabaseStore()
    queue = FormationMirrorQueue(data_dir=config_mod.DATA_DIR)
    queue.enqueue_diff(diff)
    queue.flush(store)
    assert len(store.tables["f2_formations"]) == 1

    # 2) Local history'yi tamamen yok et
    yerel_dosya = fh.yol(_STOCK, _TF, config_mod.DATA_DIR)
    assert os.path.isfile(yerel_dosya)
    os.remove(yerel_dosya)
    assert not os.path.isfile(yerel_dosya)

    # 3) Supabase'ten hydrate et
    yuklenen = hydrate_stock_tf(_STOCK, _TF, store=store, data_dir=config_mod.DATA_DIR)
    assert yuklenen == 1
    assert os.path.isfile(yerel_dosya)

    # Hydrate edilen kaydı incele: bar_time TEXT ve bar_index int olmalıdır
    defter_hydrated = fh.yukle(_STOCK, _TF)
    rec_hydrated = fh.kayit_getir(defter_hydrated, orijinal_sid)
    assert rec_hydrated is not None
    assert isinstance(rec_hydrated["dogum"]["bar_time"], str)
    assert isinstance(rec_hydrated["dogum"]["bar_index"], int)
    assert " " in rec_hydrated["dogum"]["bar_time"]

    # 4) Yeni tarama yap (sıfırdan kurulmuş motor ile, 1 yeni bar eklenerek)
    son_bar = df.iloc[-1]
    yeni_satir = pd.DataFrame([{
        "open": son_bar["open"], "high": son_bar["high"],
        "low": son_bar["low"], "close": son_bar["close"], "volume": son_bar["volume"]
    }], index=[df.index[-1] + pd.Timedelta(hours=1)])
    df_yeni = pd.concat([df, yeni_satir])

    mgr_yeni = PatternLifecycleManager(profile="Dengeli")
    snap2 = mgr_yeni.scan(f"{_STOCK}_{_TF}", df_yeni)

    # 5) Eşleşen SID orijinal SID ile BİREBİR AYNI OLMALIDIR!
    assert snap2.active is not None and snap2.active.valid
    yeni_sid = snap2.active.stable_id
    assert yeni_sid == orijinal_sid, (
        "Hydration sonrası SID eşleşmesi bozuldu! Orijinal: %s, Yeni: %s"
        % (orijinal_sid, yeni_sid)
    )

    # Tüm yaşam döngüsündeki tekil SID sayısı tam olarak 1 olmalıdır
    assert len({orijinal_sid, yeni_sid}) == 1


# ============================================================================
# H. bar_time REGRESSION
# ============================================================================

def test_bar_time_text_formati_bozulmaz(ortam):
    """Local bar_time 'YYYY-MM-DD HH:MM:SS+03:00' formatı remote hydrate sonrası aynı string kalır."""
    orijinal_bt = "2026-01-05 11:30:00+03:00"
    row = {
        "stable_id": "sid-bt",
        "stock": "SISE",
        "timeframe": "1h",
        "durum": "acik",
        "dogum_bar_time": orijinal_bt,
        "dogum_bar_index": 10,
        "dogum_alanlar": {"start_bar": 10, "family": "Triangle"},
    }
    store = FakeSupabaseStore()
    store.request_table("f2_formations", "POST", json=[row])

    # Hydrate et
    hydrate_stock_tf("SISE", "1h", store=store, data_dir=config_mod.DATA_DIR)
    defter = fh.yukle("SISE", "1h")
    rec = fh.kayit_getir(defter, "sid-bt")

    assert rec is not None
    assert rec["dogum"]["bar_time"] == orijinal_bt
    assert "T" not in rec["dogum"]["bar_time"].split()[0], "T ayraçlı ISO formatına dönüşmemelidir"


# ============================================================================
# I. TYPE REGRESSION (BAR_ALANLARI int)
# ============================================================================

def test_hydrate_type_regression_bar_alanlari_int(ortam):
    """Hydrate edilen veride BAR_ALANLARI int kalır, identity_compatible aritmetiği bozulmaz."""
    row = {
        "stable_id": "sid-types",
        "stock": "KCHOL",
        "timeframe": "1h",
        "durum": "acik",
        "dogum_bar_time": "2026-01-05 09:30:00+03:00",
        "dogum_bar_index": 5,
        "dogum_alanlar": {
            "start_bar": 5,
            "end_bar": 20,
            "apex_bar": 25,
            "hb1": 8, "hb2": 16,
            "lb1": 10, "lb2": 18,
            "family": "Pennant",
            "pattern_type": "Boğa Flaması",
            "classic_dir": 1,
            "raw_quality": 85.5,
        },
    }
    store = FakeSupabaseStore()
    store.request_table("f2_formations", "POST", json=[row])

    hydrate_stock_tf("KCHOL", "1h", store=store, data_dir=config_mod.DATA_DIR)
    defter = fh.yukle("KCHOL", "1h")
    rec = fh.kayit_getir(defter, "sid-types")
    alanlar = rec["dogum"]["alanlar"]

    for b_alan in BAR_ALANLARI:
        if b_alan in alanlar:
            assert isinstance(alanlar[b_alan], int), f"{b_alan} int olmalı, {type(alanlar[b_alan])} geldi"

    # _aday_kandidate testi
    aday = fh._aday_kandidate(rec, delta=3)
    assert aday.start_bar == 8
    assert aday.apex_bar == 28


# ============================================================================
# J. MULTI-FORMATION
# ============================================================================

def test_multi_formation_mirror_ve_hydrate_izolasyonu(ortam):
    """Aynı stock/timeframe'deki iki farklı formation kendi SID'lerini ve snapshot'larını izole tutar."""
    mgr, seri, kayitlar, terminal_sid_1, (d1, d2) = _iki_tam_zincir()
    assert len(kayitlar) == 2
    sid_a, sid_b = kayitlar[0]["stable_id"], kayitlar[1]["stable_id"]
    assert sid_a != sid_b

    defter = fh.yukle(_STOCK, _TF)
    diff = extract_diff(defter)
    assert len(diff["f2_formations"]) == 2

    store = FakeSupabaseStore()
    queue = FormationMirrorQueue(data_dir=config_mod.DATA_DIR)
    queue.enqueue_diff(diff)
    queue.flush(store)

    # Yerel dosyayı sil
    os.remove(fh.yol(_STOCK, _TF, config_mod.DATA_DIR))

    # Hydrate et
    hydrate_stock_tf(_STOCK, _TF, store=store, data_dir=config_mod.DATA_DIR)
    defter_hyd = fh.yukle(_STOCK, _TF)

    rec_a = fh.kayit_getir(defter_hyd, sid_a)
    rec_b = fh.kayit_getir(defter_hyd, sid_b)
    assert rec_a is not None and rec_b is not None

    # Snapshot sahiplik kontrolü
    for s in rec_a.get("snapshotlar", []):
        assert s.get("stable_id") == sid_a
    for s in rec_b.get("snapshotlar", []):
        assert s.get("stable_id") == sid_b


# ============================================================================
# K. TERMINAL ATTACH KORUMASI
# ============================================================================

def test_terminal_formation_hydrate_edildikten_sonra_eslestir_ile_re_attach_edilmez(ortam):
    """Terminal durumundaki kayıt eslestir() tarafından yeni candidate'a asla bağlanmaz."""
    df = _retest_senaryosu()
    mgr, durumlar = _kirilim_retest_zinciri(df)
    defter = fh.yukle(_STOCK, _TF)
    rec = fh.kayitlar(defter)[0]
    sid_terminal = rec["stable_id"]

    # Supabase'e aktar ve yereli sil
    store = FakeSupabaseStore()
    q = FormationMirrorQueue(data_dir=config_mod.DATA_DIR)
    q.enqueue_diff(extract_diff(defter))
    q.flush(store)
    os.remove(fh.yol(_STOCK, _TF, config_mod.DATA_DIR))

    # Hydrate et
    hydrate_stock_tf(_STOCK, _TF, store=store, data_dir=config_mod.DATA_DIR)

    # Yeni bir candidate için eslestir çağır
    eng = mgr.get_engine(f"{_STOCK}_{_TF}")
    candidate = mock.MagicMock()
    candidate.stable_id = None
    candidate.valid = True
    candidate.family = "Pennant"
    candidate.classic_dir = 1
    candidate.start_bar = 0

    eslesen = fh.eslestir(eng, candidate, stock=_STOCK, tf=_TF)
    assert eslesen is None, "Terminal kayıt yeni candidate'a re-attach edilmemelidir"


# ============================================================================
# L. RESTART & OUTCOME LINKAGE
# ============================================================================

def test_restart_supabase_recovery_sonrasi_outcome_linkage_korunur(ortam):
    """Outcome bağlı bir kaydın sonucu Supabase recovery sonrasında da okunabilir kalır."""
    df = _retest_senaryosu()
    mgr, _ = _kirilim_retest_zinciri(df)
    defter = fh.yukle(_STOCK, _TF)
    sid = fh.kayitlar(defter)[0]["stable_id"]

    # Outcome bağla
    fh.sonuc_bagla(defter, sid, {
        "durum": "hedef",
        "deneme": 1,
        "kaynak": "2026-01-07 10:30:00+03:00",
        "outcome": {"mfe_pct": 5.4, "mae_pct": -0.8},
    })
    fh.kaydet(defter)

    # Supabase'e mirror
    store = FakeSupabaseStore()
    q = FormationMirrorQueue(data_dir=config_mod.DATA_DIR)
    q.enqueue_diff(extract_diff(defter))
    q.flush(store)

    # Yereli sil ve hydrate et
    os.remove(fh.yol(_STOCK, _TF, config_mod.DATA_DIR))
    hydrate_stock_tf(_STOCK, _TF, store=store, data_dir=config_mod.DATA_DIR)

    rec_hyd = fh.kayit_getir(fh.yukle(_STOCK, _TF), sid)
    assert rec_hyd is not None
    assert rec_hyd.get("sonuc") is not None
    assert rec_hyd["sonuc"]["durum"] == "hedef"
    assert rec_hyd["sonuc"]["deneme"] == 1


# ============================================================================
# M. LOCAL REPOSITORY
# ============================================================================

def test_local_formation_repository_temel_api(ortam):
    """LocalFormationRepository temel okuma arayüzü fonksiyonları doğru çalışmalıdır."""
    df = _retest_senaryosu()
    mgr, _ = _kirilim_retest_zinciri(df)
    defter = fh.yukle(_STOCK, _TF)
    sid = fh.kayitlar(defter)[0]["stable_id"]

    repo = LocalFormationRepository(data_dir=config_mod.DATA_DIR)

    # 1) get_formation
    rec = repo.get_formation(sid, stock=_STOCK, timeframe=_TF)
    assert rec is not None
    assert rec["stable_id"] == sid

    # 2) get_formations
    forms = repo.get_formations(_STOCK, _TF)
    assert len(forms) == 1
    assert forms[0]["stable_id"] == sid

    # 3) get_timeline
    timeline = repo.get_timeline(sid, stock=_STOCK, timeframe=_TF)
    assert len(timeline) >= 4
    for item in timeline:
        assert item["kategori"] in ("snapshot", "olay")

    # 4) get_recent
    recent = repo.get_recent(limit=10, stock=_STOCK, timeframe=_TF)
    assert len(recent) == 1
