"""Deploy şalteri ve grafik doktoru: ağ/gerçek Telegram olmadan regresyonlar."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import deploy_check
import grafik
import grafik_uret
import notifier
from grafik_ayar import otomatik_grafik_acik

ROOT = Path(__file__).resolve().parent


@pytest.mark.parametrize("value,expected", [
    (None, False), ("", False), ("   ", False), ("yok", False),
    ("0", False), (" FALSE ", False), ("off", False), ("no", False),
    ("none", False), ("hayir", False), ("HAYIR", False), ("hayır", False),
    ("kapali", False), ("KAPALI", False), ("kapalı", False),
    ("alarm", True), ("1", True), ("true", True), ("on", True),
    ("yes", True), ("evet", True), ("Açık", True),
    ("eski-bilinmeyen-deger", True),  # mevcut kullanıcılar için geriye uyum
])
def test_switch_and_doctor_agree(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("TELEGRAM_GRAFIK", raising=False)
    else:
        monkeypatch.setenv("TELEGRAM_GRAFIK", value)
    assert otomatik_grafik_acik(value) is expected
    assert grafik.grafik_aktif_mi() is expected
    assert notifier._grafik_salteri_acik() is expected

    rows = []
    monkeypatch.setattr(deploy_check, "satir", lambda level, title, detail="": rows.append((level, title, detail)))
    deploy_check.kontrol_env({}, canli_mod=False)
    title = "Otomatik alarm grafikleri açık" if expected else "Otomatik alarm grafikleri kapalı"
    assert any(level == deploy_check.OK and message == title for level, message, _ in rows)
    assert any("değeri tanınmıyor" in message for _, message, _ in rows) is (value == "eski-bilinmeyen-deger")


@pytest.mark.parametrize("value,expected", [(None, False), ("  ", False), ("false", False),
                                           ("kapalı", False), ("alarm", True),
                                           ("yes", True), ("bilinmeyen", True)])
def test_startup_config_value_has_same_switch_interpretation(value, expected):
    # config.py araştırma manifestinde kayıtlıdır; tarihsel kaynak değişmeden
    # mevcut config yazımları da ortak yorumlayıcıyla tutarlı kalır.
    env = dict(os.environ)
    if value is None:
        env.pop("TELEGRAM_GRAFIK", None)
    else:
        env["TELEGRAM_GRAFIK"] = value
    command = ("import config; from grafik_ayar import otomatik_grafik_acik; "
               "print(otomatik_grafik_acik(config.TELEGRAM_GRAFIK))")
    result = subprocess.run([sys.executable, "-c", command],
                            cwd=ROOT, env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(expected)


def test_disabled_alias_never_prepares_automatic_chart(monkeypatch):
    import grafik.kare as kare

    monkeypatch.setenv("TELEGRAM_GRAFIK", "false")
    monkeypatch.setattr(kare, "_sonuc_sec", lambda *_a, **_kw: pytest.fail("kapalı şalterde kare hazırlanmamalı"))
    output = grafik.kare_listesi(None, "4h", object(), sembol="AKBNK")
    assert output["goruntular"] == []


@pytest.mark.parametrize("layer,level,title", [
    (None, deploy_check.WARN, "Stabil direnç durumu raporlanmadı"),
    ({"hazir": False, "durum": "DATA_ERROR", "neden": "missing_source"},
     deploy_check.WARN, "Stabil direnç bu karede hazır değil"),
    ({"hazir": True, "cizildi": False}, deploy_check.WARN, "Stabil direnç hazır ama bu karede çizilmedi"),
    ({"hazir": True, "cizildi": True}, deploy_check.OK, "Stabil direnç bu karede çizildi"),
    ({"hazir": "true", "cizildi": "true"}, deploy_check.WARN, "Stabil direnç bu karede hazır değil"),
])
def test_graphic_smoke_reports_actual_resistance_state(monkeypatch, layer, level, title):
    rows = []
    monkeypatch.setattr(deploy_check, "satir", lambda kind, name, detail="": rows.append((kind, name, detail)))
    metadata = {"png_kb": 75, "mum_sayisi": 68, "sure_ms": 400,
                "cizgiler": {} if layer is None else {"stabil_direnc": layer}}
    monkeypatch.setattr(grafik_uret, "kare_uret", lambda *_a, **_kw: {
        "yol": "/tmp/offline-only-test.png", "meta": metadata, "kaynak": "sahte",
    })
    deploy_check.kontrol_grafik("", "", False)
    assert any(kind == deploy_check.OK and "Kare üretildi" in name for kind, name, _ in rows)
    assert any(kind == level and name == title for kind, name, _ in rows)
    assert any(name == "Fotoğraf gönderilmedi" for _, name, _ in rows)


def test_graphic_smoke_redacts_secrets_from_resistance_reason(monkeypatch):
    rows = []
    monkeypatch.setattr(deploy_check, "satir", lambda kind, name, detail="": rows.append((kind, name, detail)))
    deploy_check._direnc_dumanini_raporla(
        {"cizgiler": {"stabil_direnc": {"hazir": False, "neden": "bad 123:secret chat 6789"}}},
        "123:secret", "6789",
    )
    assert rows[0][0] == deploy_check.WARN
    assert "123:secret" not in rows[0][2] and "6789" not in rows[0][2]
