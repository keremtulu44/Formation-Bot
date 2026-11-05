import json
from datetime import datetime, timedelta

import config
import main as main_mod


IST = config.ISTANBUL_TZ


def test_render_runtime_captures_last_heartbeat_and_marks_possible_sleep(tmp_path, monkeypatch):
    now = IST.localize(datetime(2026, 11, 4, 12, 30))
    previous = now - timedelta(minutes=28)
    path = tmp_path / "heartbeat.json"
    path.write_text(json.dumps({"last_scan": previous.isoformat()}), encoding="utf-8")
    monkeypatch.setattr(main_mod, "_heartbeat_yolu", lambda: str(path))

    state = main_mod._render_runtime_status_init(now=now)

    assert state["started_at"] == now.isoformat()
    assert state["previous_heartbeat_at"] == previous.isoformat()
    assert state["estimated_gap_seconds"] == 28 * 60
    assert state["possible_sleep_or_restart"] is True
    assert state["previous_heartbeat_source"] == "local heartbeat.json"


def test_render_runtime_without_previous_heartbeat_reports_unknown(tmp_path, monkeypatch):
    path = tmp_path / "missing-heartbeat.json"
    monkeypatch.setattr(main_mod, "_heartbeat_yolu", lambda: str(path))
    now = IST.localize(datetime(2026, 11, 4, 12, 30))

    state = main_mod._render_runtime_status_init(now=now)

    assert state["previous_heartbeat_at"] is None
    assert state["estimated_gap_seconds"] is None
    assert state["possible_sleep_or_restart"] is False


def test_render_command_reports_estimated_gap_data_and_image_mode(monkeypatch):
    started = IST.localize(datetime(2026, 11, 4, 12, 0))
    previous = started - timedelta(minutes=35)
    monkeypatch.setattr(main_mod, "_shutdown_requested", False)
    monkeypatch.setattr(main_mod, "_startup_ready", True)
    monkeypatch.setattr(main_mod, "_render_runtime_status", {
        "started_at": started.isoformat(),
        "started_monotonic": main_mod.time.monotonic() - 3600,
        "previous_heartbeat_at": previous.isoformat(),
        "estimated_gap_seconds": 35 * 60,
        "sleep_gap_threshold_seconds": 15 * 60,
        "possible_sleep_or_restart": True,
    })
    monkeypatch.setattr(main_mod._live_state, "status", lambda: {
        "son_tarama_veri_zamani": "2026-11-04T11:30:00+03:00",
        "son_tarama_taze_veri": 55,
        "son_tarama_beklenen_hisse": 57,
        "son_tarama_fetch_hatasi": 2,
        "son_tarama_en_eski_veri_yasi_dk": 75.0,
    })
    monkeypatch.setattr(main_mod, "last_run_stats", {}, raising=False)
    monkeypatch.setattr(config, "TELEGRAM_GRAFIK", "yok")

    reply = main_mod._komut_render("")

    assert "uyandı/başladı" in reply
    assert "Olası uyku/kesinti" in reply
    assert "son heartbeat" in reply
    assert "En yeni 1s cache mum etiketi" in reply
    assert "1sa 15dk" in reply
    assert "Alarm görselleri: kapalı" in reply
    assert "TELEGRAM_GRAFIK=yok" in reply


def test_render_and_sleep_aliases_are_read_only_public_commands():
    assert main_mod.TELEGRAM_KOMUTLARI["render"] is main_mod._komut_render
    assert main_mod.TELEGRAM_KOMUTLARI["uyku"] is main_mod._komut_render
    assert "render" in main_mod._public_komut_adlari()
    assert "uyku" in main_mod._public_komut_adlari()
