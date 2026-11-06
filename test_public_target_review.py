"""Offline safety checks for a channel-to-group transition."""
import json

import notifier as notifier_mod
from public_target_review import PublicTargetReview, target_key
from state import persistence


def _event(tf="1h"):
    return {"stock_name": "THYAO", "timeframe": tf, "state": "KIRILIM_TEYITLI",
            "pattern_name": "Üçgen", "formation_id": "fid-1", "break_dir": 1,
            "confidence_score": 90}


def _make(monkeypatch, root, target):
    monkeypatch.setattr(notifier_mod, "DATA_DIR", str(root))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("TELEGRAM_GROUP_ID", target)
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)
    return notifier_mod.TelegramNotifier()


def test_changed_public_target_quarantines_old_queue_and_history(monkeypatch, tmp_path):
    monkeypatch.setattr("config.DATA_DIR", str(tmp_path))
    old = _make(monkeypatch, tmp_path, "@EskiKanal")
    assert old.public_kuyruk(_event())
    old._public_gun_sayac = 3
    assert old._public_durum_kaydet()

    group = _make(monkeypatch, tmp_path, "https://t.me/FormationBot1")
    assert group.public_chat_id == "@FormationBot1" and group.public_enabled
    assert group._public_kuyruk == [] and group._public_gun_sayac == 0
    report = group.gonderim_durumu()["public_hedef_inceleme"]
    assert report == {"available": True, "archives": 1}
    saved = json.loads((tmp_path / "telegram_public_target_review.json").read_text())
    snapshot = saved["archives"][0]["public_state"]
    assert snapshot["target"] == "@EskiKanal" and snapshot["kuyruk"][0]["stock_name"] == "THYAO"
    assert not group._delivery.public_duplicate(_event("4h"))
    assert group.public_kuyruk(_event("4h"))

    # Same target restart keeps its own queue/history and does not re-archive.
    again = _make(monkeypatch, tmp_path, "@formationbot1")
    assert len(again._public_kuyruk) == 1
    assert again._delivery.public_duplicate(_event("1h"))
    assert again._public_target_review.status()["archives"] == 1


def test_legacy_targetless_public_queue_is_retained_but_not_replayed(monkeypatch, tmp_path):
    monkeypatch.setattr("config.DATA_DIR", str(tmp_path))
    legacy = {"gun_sayac": 2, "kuyruk": [_event()], "alert_muhurlari": {"old": "2026-11-06T12:00:00+03:00"}}
    assert persistence.gunluk_durum_guncelle({"public": legacy}, data_dir=str(tmp_path))
    group = _make(monkeypatch, tmp_path, "@FormationBot1")
    assert group._public_kuyruk == [] and group._public_target_review.status()["archives"] == 1
    archive = json.loads((tmp_path / "telegram_public_target_review.json").read_text())
    assert archive["archives"][0]["public_state"] == legacy
    assert persistence.gunluk_durum_yukle(data_dir=str(tmp_path))["public"]["target"] == "@FormationBot1"


def test_failed_review_write_keeps_original_state_and_stops_public(monkeypatch, tmp_path):
    monkeypatch.setattr("config.DATA_DIR", str(tmp_path))
    old = {"target": "@old", "kuyruk": [_event()], "gun_sayac": 1}
    assert persistence.gunluk_durum_guncelle({"public": old}, data_dir=str(tmp_path))
    monkeypatch.setattr(PublicTargetReview, "archive", lambda *_args: False)
    group = _make(monkeypatch, tmp_path, "@FormationBot1")
    assert not group.public_enabled and not group._public_state_writable
    assert persistence.gunluk_durum_yukle(data_dir=str(tmp_path))["public"] == old
    assert not group.public_kuyruk(_event("4h"))
    assert not group._public_durum_kaydet()


def test_failed_new_target_checkpoint_disables_public_even_after_archive(monkeypatch, tmp_path):
    monkeypatch.setattr("config.DATA_DIR", str(tmp_path))
    old = {"target": "@old", "kuyruk": [_event()]}
    assert persistence.gunluk_durum_guncelle({"public": old}, data_dir=str(tmp_path))
    monkeypatch.setattr(persistence, "gunluk_durum_guncelle", lambda *_a, **_k: False)
    group = _make(monkeypatch, tmp_path, "@FormationBot1")
    assert not group.public_enabled and not group._public_state_writable
    assert group._public_target_review.status()["archives"] == 1
    assert persistence.gunluk_durum_yukle(data_dir=str(tmp_path))["public"] == old


def test_review_file_is_atomic_idempotent_and_corruption_is_not_overwritten(tmp_path):
    archive = PublicTargetReview(tmp_path)
    snapshot = {"target": "@old", "kuyruk": [_event()]}
    assert archive.archive(snapshot, "@FormationBot1")
    assert archive.archive(snapshot, "https://t.me/formationbot1")
    assert archive.status()["archives"] == 1
    archive.path.write_text("not json")
    broken = PublicTargetReview(tmp_path)
    assert not broken.available and not broken.archive(snapshot, "@another")
    assert archive.path.read_text() == "not json"


def test_target_comparison_distinguishes_numeric_ids_and_normalizes_usernames():
    assert target_key("https://t.me/FormationBot1/") == target_key("@formationbot1")
    assert target_key("-100123") == "-100123"
    assert target_key("-100123") != target_key("-100456")
