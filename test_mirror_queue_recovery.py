"""Render taraması sırasında mirror taşması ve kurtarma regresyonları."""

import json

from state.formation_mirror import FormationMirrorQueue, KUYRUK_DOSYA_ADI
from test_p2_6_mirror import FakeSupabaseResponse, FakeSupabaseStore


def test_tekrarlanan_defter_satirlari_birlesir_ve_son_deger_gonderilir(tmp_path):
    q = FormationMirrorQueue(data_dir=str(tmp_path))
    for version in range(200):
        q.enqueue_diff({
            "f2_formations": [{"stable_id": "s1", "durum": str(version)}],
            "f2_snapshots": [{"stable_id": "s1", "tur": "geo", "bar_time": "t1"}],
            "f2_events": [{"stable_id": "s1", "type": "x", "name": "n", "bar": 1, "bar_time": "t1"}],
        })
    assert q.size() == 3
    store = FakeSupabaseStore()
    assert q.flush(store) == 3
    assert store.tables["f2_formations"][0]["durum"] == "199"
    assert q.size() == 0
    # An identical, confirmed row is not transmitted again in this process.
    assert q.enqueue_diff({"f2_formations": [{"stable_id": "s1", "durum": "199"}]}) == 0
    assert q.size() == 0


def test_cevrimdisi_besbin_uzeri_kayit_atilmaz_yeniden_acilir(tmp_path):
    q = FormationMirrorQueue(data_dir=str(tmp_path))
    rows = [{"stable_id": f"s{i}", "stock": "T", "timeframe": "1h"} for i in range(5100)]
    q.enqueue_diff({"f2_formations": rows})
    assert q.size() == 5100
    q2 = FormationMirrorQueue(data_dir=str(tmp_path))
    assert q2.size() == 5100
    store = FakeSupabaseStore()
    assert q2.flush(store, max_batches=1) == 100
    assert q2.size() == 5000
    assert len(store.tables["f2_formations"]) == 100


def test_kuyruk_yazma_hatasinda_defter_tekrar_denenebilir(tmp_path, monkeypatch):
    q = FormationMirrorQueue(data_dir=str(tmp_path))
    defter = {"stock": "T", "timeframe": "1h", "kayitlar": {
        "s1": {"durum": "acik", "dogum": {"alanlar": {}}}}}
    original = q.enqueue_diff
    monkeypatch.setattr(q, "enqueue_diff", lambda _diff: (_ for _ in ()).throw(OSError("disk")))
    try:
        q.enqueue_from_defter(defter)
    except OSError:
        pass
    else:
        raise AssertionError("disk arızası bekleniyordu")
    monkeypatch.setattr(q, "enqueue_diff", original)
    assert q.enqueue_from_defter(defter) == 1
    assert q.size() == 1


def test_eski_json_kuyrugu_bir_kez_aktarilir(tmp_path):
    legacy = tmp_path / KUYRUK_DOSYA_ADI
    legacy.write_text(json.dumps({"f2_formations": [{"stable_id": "old"}]}), encoding="utf-8")
    q = FormationMirrorQueue(data_dir=str(tmp_path))
    assert q.size() == 1
    store = FakeSupabaseStore()
    assert q.flush(store) == 1
    assert legacy.exists()  # geçiş doğrulanmadan eski dosyaya dokunulmaz
    assert FormationMirrorQueue(data_dir=str(tmp_path)).size() == 0


def test_bekleyen_ebeveyn_gonderilmeden_cocuk_gonderilmez(tmp_path, monkeypatch):
    import state.formation_mirror as mirror

    monkeypatch.setattr(mirror, "FLUSH_BATCH_SIZE", 2)
    q = FormationMirrorQueue(data_dir=str(tmp_path))
    q.enqueue_diff({
        "f2_formations": [{"stable_id": f"s{i}"} for i in range(4)],
        "f2_snapshots": [{"stable_id": f"s{i}", "tur": "geo", "bar_time": "t"} for i in range(4)],
    })

    class ParentCheckingStore(FakeSupabaseStore):
        def request_table(self, table_name, method, *, params=None, json=None, headers=None):
            if table_name == "f2_snapshots":
                ids = {row["stable_id"] for row in self.tables["f2_formations"]}
                assert all(row["stable_id"] in ids for row in json)
            return super().request_table(table_name, method, params=params, json=json, headers=headers)

    store = ParentCheckingStore()
    q.flush(store, max_batches=1)
    assert len(store.tables["f2_formations"]) == 2
    assert len(store.tables["f2_snapshots"]) == 2
    q.flush(store, max_batches=1)
    assert q.size() == 0
    assert len(store.tables["f2_snapshots"]) == 4


def test_hata_sonrasi_satirlar_korunur_ve_tekrar_gonderilir(tmp_path):
    class FailOnce(FakeSupabaseStore):
        def __init__(self):
            super().__init__()
            self.failed = False

        def request_table(self, table_name, method, *, params=None, json=None, headers=None):
            if not self.failed:
                self.failed = True
                return FakeSupabaseResponse({}, status_code=400)
            return super().request_table(table_name, method, params=params, json=json, headers=headers)

    q = FormationMirrorQueue(data_dir=str(tmp_path))
    q.enqueue_diff({"f2_formations": [{"stable_id": "s1"}]})
    store = FailOnce()
    assert q.flush(store) == 0
    assert q.status()["son_hata"] == {"tablo": "f2_formations", "durum": 400, "batch": 1}
    assert q.status()["tablolar"] == {"f2_formations": 1}
    assert FormationMirrorQueue(data_dir=str(tmp_path)).size() == 1
    q._retry_after = 0
    assert q.flush(store) == 1
    assert q.size() == 0
    assert q.status() == {"bekleyen": 0, "tablolar": {}, "gonderilen": 1, "son_hata": None}
