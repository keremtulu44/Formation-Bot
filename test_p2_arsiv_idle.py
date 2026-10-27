# -*- coding: utf-8 -*-
"""P2 — BIST KAPALI idle'da mirror flush, f2_* dolmalı"""

def test_bist_kapali_mirror_flush_var():
    import pathlib
    app = pathlib.Path("bot/app.py").read_text(encoding="utf-8")
    # BIST KAPALI dalında mirror flush çağrısı olmalı
    assert "BIST KAPALI" in app
    # P2 eklemesi: idle dalında get_mirror_queue().flush
    # En az iki flush noktası olmalı: tarama sonrası + BIST KAPALI idle
    assert app.count("get_mirror_queue().flush") >= 2, "idle mirror flush eksik"
    assert "BIST KAPALI mirror flush" in app or "mirror kuyruğu boşalt" in app.lower()


def test_mirror_queue_kalici():
    from state.formation_mirror import FormationMirrorQueue, extract_diff
    import tempfile, os
    with tempfile.TemporaryDirectory() as td:
        q = FormationMirrorQueue(data_dir=td)
        # sahte defter
        defter = {
            "stock": "AKBNK",
            "timeframe": "1h",
            "kayitlar": {
                "sid1": {
                    "durum": "acik",
                    "dogum": {"bar_time": "2026-10-27 10:00", "bar_index": 100, "alanlar": {"family": "tri", "pattern_type": "sym", "raw_quality": 0.8}},
                    "snapshotlar": [{"tur": "init", "bar_time": "2026-10-27 10:00", "bar": 100, "state": "FORMASYON_TANIMLANDI", "alanlar": {}}],
                    "olaylar": [{"type": "break", "name": "BREAK", "bar": 100, "time": "2026-10-27 10:00", "state": "KIRILIM_TEYITLI"}],
                }
            }
        }
        diff = extract_diff(defter)
        assert diff["f2_formations"], "diff üretmeli"
        ek = q.enqueue_diff(diff)
        assert ek > 0
        assert q.size() == ek
        # diske yaz ve yeniden yükle
        assert q.save_to_disk()
        q2 = FormationMirrorQueue(data_dir=td)
        assert q2.size() == ek, "restart'ta queue kaybolmamalı"


def test_f2_diff_dort_tabloyu_doldurur():
    from state.formation_mirror import extract_diff
    defter = {
        "stock": "THYAO",
        "timeframe": "4h",
        "kayitlar": {
            "sidA": {
                "durum": "acik",
                "ilk_gorulme": "2026-10-27T10:00:00+03:00",
                "son_gorulme": "2026-10-27T11:00:00+03:00",
                "dogum": {"bar_time": "2026-10-27 10:00", "bar_index": 10, "alanlar": {"family": "tri", "pattern_type": "sym", "raw_quality": 0.9, "geometry_atr": 1.1, "start_bar": 10, "classic_dir": 1}},
                "snapshotlar": [{"tur": "formation", "bar_time": "2026-10-27 10:00", "bar": 10, "state": "SIKISMA", "alanlar": {"raw_quality": 0.9}}],
                "olaylar": [{"type": "lifecycle", "name": "KIRILIM_TEYITLI", "bar": 10, "time": "2026-10-27 11:00", "state": "KIRILIM_TEYITLI", "quality": 0.85}],
                "sonuc": {"durum": "bekliyor", "deneme": 0, "outcome": {"hedef": 100}},
            }
        }
    }
    diff = extract_diff(defter)
    assert len(diff["f2_formations"]) == 1
    assert len(diff["f2_snapshots"]) == 1
    assert len(diff["f2_events"]) == 1
    assert len(diff["f2_outcome_links"]) == 1
