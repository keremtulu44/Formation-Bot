"""Offline regressions for missing public alerts and operator diagnostics."""
from datetime import datetime, timedelta

import config
import main as main_mod
import notifier as notifier_mod
import notifier.api as notifier_api
import state.persistence as persistence


def _notifier(monkeypatch, tmp_path, *, states=None, public=True):
    monkeypatch.setattr(notifier_mod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(persistence, "gunluk_durum_yukle", lambda: {})
    monkeypatch.setattr(persistence, "gunluk_durum_guncelle", lambda *_: None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-10012345" if public else "")
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)
    if states is not None:
        monkeypatch.setattr(config, "PUBLIC_STATES", states)
    return notifier_mod.TelegramNotifier()


def _event(state="KIRILIM_TEYITLI", tf="4h", q=90, **extra):
    data = {"stock_name": "THYAO", "timeframe": tf, "state": state,
            "pattern_name": "Alçalan Üçgen", "confidence_score": q,
            "break_dir": 1, "formation_id": "fixture-id"}
    data.update(extra)
    return data


def test_old_deploy_guide_config_only_allows_retests_and_warns(monkeypatch, tmp_path, caplog):
    n = _notifier(monkeypatch, tmp_path,
                  states=["FORMASYON_TAMAMLANDI", "RETEST_BASARILI"])
    assert n.public_states == {"RETEST_BASARILI"}
    assert not n.should_send_to_public(_event())
    assert n.should_send_to_public(_event(state="RETEST_BASARILI"))
    assert not n.should_send_to_public(_event(state="KIRILIM_GECERSIZLESTI"))
    assert "Public state filtresi" in caplog.text
    assert not n.public_kuyruk(_event())
    assert n.gonderim_durumu()["public_filtre_sayac"]["state"] == 1


def test_public_quality_and_dedup_reasons_visible_without_changing_policy(monkeypatch, tmp_path):
    n = _notifier(monkeypatch, tmp_path)
    n.public_min_quality = 80
    assert not n.public_kuyruk(_event(tf="1d", q=75))
    assert n.public_filtre_sayac["kalite"] == 1
    n.public_min_quality = 0
    assert n.public_kuyruk(_event(tf="1d", q=75))
    assert not n.public_kuyruk(_event(tf="1d", q=75))
    assert n.public_filtre_sayac["tekrar"] == 1
    monkeypatch.setattr(main_mod, "_notifier_ref", n)
    durum = main_mod._komut_durum("")
    assert "Filtre (süreçteki denemeler)" in durum
    assert "kalite 1" in durum and "tekrar 1" in durum
    assert "Metin bütçesi: saat" in durum


def test_public_disabled_is_explicit_in_status(monkeypatch, tmp_path):
    n = _notifier(monkeypatch, tmp_path, public=False)
    assert n.enabled and not n.public_enabled
    assert not n.public_kuyruk(_event())
    assert n.public_filtre_sayac["hedef_yok"] == 1
    monkeypatch.setattr(main_mod, "_notifier_ref", n)
    assert "Public hedef kapalı" in main_mod._komut_durum("")


def test_dm_outbox_early_duplicate_can_recover_missing_public(monkeypatch, tmp_path):
    n = _notifier(monkeypatch, tmp_path)
    monkeypatch.setattr(n._delivery, "already_done", lambda _: True)
    prepared = []

    def prepare(data):
        prepared.append(True)
        assert n.public_kuyruk(data)

    data = _event()
    assert n.send_with_prepare(dict(data), before_send=prepare) is False
    assert prepared == [True] and len(n._public_kuyruk) == 1
    # It is already queued for this exact destination: no new prep or duplicate.
    assert n.send_with_prepare(dict(data), before_send=prepare) is False
    assert prepared == [True] and len(n._public_kuyruk) == 1


def test_restored_public_hourly_timestamps_accept_legacy_naive_dates(monkeypatch, tmp_path):
    now = datetime.now(config.ISTANBUL_TZ)
    monkeypatch.setattr(persistence, "gunluk_durum_yukle", lambda: {
        "public": {"saatlik_ts": [(now - timedelta(minutes=5)).replace(tzinfo=None).isoformat()]}
    })
    monkeypatch.setattr(persistence, "gunluk_durum_guncelle", lambda *_: None)
    monkeypatch.setattr(notifier_mod, "DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-10012345")
    n = notifier_mod.TelegramNotifier()
    assert n._public_kap_gec()
    assert n.gonderim_durumu()["public_saatlik"] == 1


def test_public_continuity_filter_reason(monkeypatch, tmp_path):
    n = _notifier(monkeypatch, tmp_path)
    monkeypatch.setattr(notifier_api, "PUBLIC_MIN_DEVLAMLILIK", 55)
    monkeypatch.setattr(notifier_api, "devamlilik_puani", lambda _: 40)
    assert not n.public_kuyruk(_event())
    assert n.public_filtre_sayac["devamlilik"] == 1
    # An invalidation is never suppressed by quality/continuity thresholds.
    assert n.should_send_to_public(_event(state="KIRILIM_GECERSIZLESTI", q=1))
