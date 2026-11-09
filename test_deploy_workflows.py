"""Workflow bash'lerini ağ kullanmadan gerçek kabukta sınar."""
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent


def script(path, marker):
    content = (ROOT / path).read_text(encoding="utf-8")
    section = content.split(marker, 1)[1].split("        run: |\n", 1)[1]
    lines = []
    for line in section.splitlines():
        if line and not line.startswith("          "):
            break
        lines.append(line)
    return textwrap.dedent("\n".join(lines))


def run_sh(tmp_path, body, **extra):
    env = {**os.environ, "GITHUB_OUTPUT": str(tmp_path / "output"),
           "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"), **extra}
    return subprocess.run(["bash", "-c", body], env=env, text=True,
                          capture_output=True, timeout=10)


@pytest.mark.parametrize("start,end,now,expected", [
    ("0800", "2300", "1200", "true"), ("0800", "2300", "0200", "false"),
    ("2200", "0200", "0100", "true"), ("2200", "0200", "1200", "false"),
    ("0800", "2300", "2300", "true"),
])
def test_keepalive_window(tmp_path, start, end, now, expected):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    date = bin_dir / "date"
    date.write_text(f'#!/bin/bash\ncase "$1" in +%H%M) echo {now};; +%u) echo 3;; *) echo test;; esac\n')
    date.chmod(0o755)
    body = script(".github/workflows/keepalive.yml", "- name: Zaman penceresi")
    body = body.replace("${{ github.event_name }}", "schedule").replace("${{ github.event.inputs.force }}", "false")
    result = run_sh(tmp_path, body, PATH=f"{bin_dir}:{os.environ['PATH']}",
                    WINDOW_START=start, WINDOW_END=end, ALWAYS="", WEEKDAYS_ONLY="")
    assert result.returncode == 0, result.stderr
    assert f"in_window={expected}" in (tmp_path / "output").read_text()


@pytest.mark.parametrize("invalid", ["2400", "1260", "abc", "8", "000x"])
def test_keepalive_invalid_window_fails(tmp_path, invalid):
    body = script(".github/workflows/keepalive.yml", "- name: Zaman penceresi")
    body = body.replace("${{ github.event_name }}", "schedule").replace("${{ github.event.inputs.force }}", "false")
    result = run_sh(tmp_path, body, WINDOW_START=invalid, WINDOW_END="2300", ALWAYS="", WEEKDAYS_ONLY="")
    assert result.returncode != 0


@pytest.mark.parametrize("response,exit_code,expected", [
    ('{"status":"ok"}', 0, 0), ('{"status":"bayat"}', 0, 1),
    ('{"status":"not-ok"}', 0, 1), ('not-json', 0, 1), ('{"status":"ok"}', 28, 1),
])
def test_keepalive_response_validation(tmp_path, response, exit_code, expected):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text('#!/bin/bash\nprintf "%s" "$FAKE_BODY" > /tmp/health.json\nprintf 200\nexit "$FAKE_EXIT"\n')
    curl.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/bash\nexit 0\n")
    sleep.chmod(0o755)
    body = script(".github/workflows/keepalive.yml", "- name: GET /health")
    result = run_sh(tmp_path, body, PATH=f"{bin_dir}:{os.environ['PATH']}",
                    DISPATCH_URL="", SECRET_URL="", VAR_URL="https://example.invalid/health",
                    FAKE_BODY=response, FAKE_EXIT=str(exit_code))
    assert result.returncode == expected, result.stdout + result.stderr
    if exit_code:
        assert "HTTP 000" in result.stdout and "200000" not in result.stdout


def test_skipped_keepalive_is_explicit_in_job_summary(tmp_path):
    workflow = (ROOT / ".github/workflows/keepalive.yml").read_text(encoding="utf-8")
    assert "if: steps.window.outputs.in_window == 'false'" in workflow
    body = script(".github/workflows/keepalive.yml", "- name: Ping atlandı (pencere dışında)")
    result = run_sh(tmp_path, body)
    assert result.returncode == 0
    assert "GET /health çalıştırılmadı" in (tmp_path / "summary").read_text(encoding="utf-8")


def test_manual_deploy_requires_main_and_secret(tmp_path):
    body = script(".github/workflows/deploy.yml", "- name: Manuel deploy tetikle")
    assert run_sh(tmp_path, body, REF="refs/heads/main", HOOK="").returncode != 0
    assert run_sh(tmp_path, body, REF="refs/heads/feature", HOOK="x").returncode != 0
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
    assert "  push:" not in workflow
    assert "hook_url:" not in workflow


@pytest.mark.parametrize("ready_body,expected", [
    ('{"startup_complete": false}', 0),
    ('{"startup_complete": true}', 1),
    ('not-json', 1),
])
def test_ci_smoke_fails_on_bad_readiness_json(tmp_path, ready_body, expected):
    """CI kabuğu HTTP koduyla yetinmez; readiness gövdesi de kontrol edilir."""
    import sys

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    py = bin_dir / "python"
    py.write_text(
        '#!/bin/bash\n'
        'if [ "$1" = main.py ]; then\n'
        '  echo "Health smoke mode: provider and command loops disabled"\n'
        '  exec /bin/sleep 30\n'
        'fi\n'
        f'exec "{sys.executable}" "$@"\n'
    )
    py.chmod(0o755)
    curl = bin_dir / "curl"
    curl.write_text('''#!/bin/bash
out=''
url=''
show_code=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    -w) show_code=1; shift 2 ;;
    -m|-X|-H|-d) shift 2 ;;
    http*) url="$1"; shift ;;
    *) shift ;;
  esac
done
case "$url" in
  */ready) body="$READY_BODY"; status=503 ;;
  */test*|*/webhook*) body='{"ok": false}'; status=404 ;;
  *) body='{"status": "ok", "commit": "deadbee"}'; status=200; /bin/sleep 0.05 ;;
esac
printf '%s' "$body" > "$out"
if [ "$show_code" = 1 ]; then printf '%s' "$status"; fi
''')
    curl.chmod(0o755)
    body = script(".github/workflows/ci.yml", "- name: Render duman testi")
    result = run_sh(tmp_path, body, PATH=f"{bin_dir}:{os.environ['PATH']}",
                    RUNNER_TEMP=str(tmp_path), READY_BODY=ready_body)
    if expected:
        assert result.returncode != 0, result.stdout + result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr


def test_ci_uses_stable_runner_and_node24_actions():
    """Python 3.12 kapısı, eski Node runtime veya kayan runner imajına dayanmaz."""
    import re

    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "runs-on: ubuntu-24.04" in workflow
    for action in ("checkout", "setup-python"):
        version = re.search(rf"uses:\s*actions/{action}@v(\d+)", workflow)
        assert version and int(version.group(1)) >= 6


def test_ci_timeout_covers_slow_full_regression():
    """Gerçek arşivli tam paket 20 dakikayı geçebilir; duman testine de pay kalmalı."""
    import re

    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    timeout = re.search(r"(?m)^\s+timeout-minutes:\s*(\d+)\s*$", workflow)
    assert timeout and int(timeout.group(1)) >= 35


def test_ci_doctor_smoke_is_offline_and_checks_png_and_resistance():
    body = script(".github/workflows/ci.yml", "- name: Kurulum doktoru ve grafik")
    assert "--skip-network --grafik-test" in body
    assert "--send-test-message" not in body
    assert "Kare üretildi: AKBNK 4h" in body
    assert "scripts/ci_seed_graphics.py" in body
    assert "Stabil direnç bu karede çizildi" in body
    assert "Stabil direnç hazır ama bu karede çizilmedi" in body
    assert "Fotoğraf gönderilmedi" in body
    assert "set -euo pipefail" in body


@pytest.mark.parametrize("now,nightly_flag,expected", [
    ("0205", "", "true"),
    ("0220", "", "true"),
    ("0310", "", "false"),
    ("0205", "false", "false"),
])
def test_keepalive_default_wakes_for_nightly_0200_refresh(tmp_path, now, nightly_flag, expected):
    """Varsayılan keep-alive penceresi 02:00-02:20 TSİ mum temizliği için servisi uyandırır."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    date = bin_dir / "date"
    date.write_text(f'#!/bin/bash\ncase "$1" in +%H%M) echo {now};; +%u) echo 3;; *) echo test;; esac\n')
    date.chmod(0o755)
    body = script(".github/workflows/keepalive.yml", "- name: Zaman penceresi")
    body = body.replace("${{ github.event_name }}", "schedule").replace("${{ github.event.inputs.force }}", "false")
    result = run_sh(
        tmp_path,
        body,
        PATH=f"{bin_dir}:{os.environ['PATH']}",
        WINDOW_START="",
        WINDOW_END="",
        ALWAYS="",
        WEEKDAYS_ONLY="",
        NIGHTLY_REFRESH=nightly_flag,
    )
    assert result.returncode == 0, result.stderr
    assert f"in_window={expected}" in (tmp_path / "output").read_text()


def test_config_empty_stabil_env_vars_do_not_crash_boot():
    """Render'da boş bırakılan STABIL_* tamsayı env'leri import sırasında çökmemeli."""
    import sys

    env = {
        **os.environ,
        "STABIL_ALARM_COOLDOWN_BAR": "",
        "STABIL_ALARM_TEKIL_UST_SINIR": "",
        "STABIL_ALARM_TAZE_DK": "",
        "NIGHTLY_CANDLE_REFRESH_HOUR": "",
        "NIGHTLY_CANDLE_REFRESH_MINUTE": "",
    }
    res = subprocess.run(
        [sys.executable, "-c", "import config; assert config.STABIL_ALARM_COOLDOWN_BAR == 6"],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert res.returncode == 0, res.stderr


def _pinned_requirements(name):
    entries = []
    for raw_line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line:
            package, separator, version = line.partition("==")
            assert separator and package and version, line
            entries.append((package.lower(), version))
    assert len(entries) == len(dict(entries)), "duplicate direct dependency"
    return dict(entries)


def test_live_pins_keep_historical_manifest_but_upgrade_known_advisories():
    """Replay pinleri hash için sabit; canlı dosya aynı paketlerle güvenli pinleri kurar."""
    from packaging.version import Version

    historical = _pinned_requirements("requirements.txt")
    live = _pinned_requirements("requirements-deploy.txt")
    known_fixed_minimum = {
        "requests": "2.33.0",
        "python-dotenv": "1.2.2",
        "pytest": "9.0.3",
    }
    assert set(live) == set(historical)
    for package in historical.keys() - known_fixed_minimum.keys():
        assert live[package] == historical[package], package
    for package, minimum in known_fixed_minimum.items():
        assert Version(live[package]) >= Version(minimum)
        assert Version(live[package]) > Version(historical[package])


def test_render_and_ci_use_the_same_live_installer():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
    installer = "bash scripts/install_deploy_dependencies.sh"
    assert f"run: {installer}" in workflow
    assert f"buildCommand: {installer}" in blueprint
    assert "requirements-deploy.txt" in workflow  # pip cache dependency path
    assert "scripts/install_deploy_dependencies.sh" in workflow
    assert installer in (ROOT / "setup.sh").read_text(encoding="utf-8")


@pytest.mark.parametrize("failure,expected_calls", [
    ("", 3),
    ("pip==26.2", 1),
    ("requirements-deploy.txt", 2),
    ("pip check", 3),
])
def test_live_installer_order_and_failure_propagation(tmp_path, failure, expected_calls):
    """Gerçek pip çalıştırmadan sıralamayı ve kırmızı build geçişlerini test et."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_python = bin_dir / "python"
    fake_python.write_text('''#!/bin/bash
printf '%s\\n' "$*" >> "$CALLS_FILE"
if [[ -n "$FAKE_FAIL" && "$*" == *"$FAKE_FAIL"* ]]; then exit 42; fi
''', encoding="utf-8")
    fake_python.chmod(0o755)
    calls_file = tmp_path / "calls"
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/install_deploy_dependencies.sh")],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
             "CALLS_FILE": str(calls_file), "FAKE_FAIL": failure},
        capture_output=True, text=True, timeout=10,
    )
    calls = calls_file.read_text(encoding="utf-8").splitlines()
    assert len(calls) == expected_calls
    assert calls[0] == "-m pip install pip==26.2 setuptools==84.1.0"
    if expected_calls >= 2:
        assert calls[1] == "-m pip install -r requirements-deploy.txt"
    if expected_calls == 3:
        assert calls[2] == "-m pip check"
    assert result.returncode == (42 if failure else 0), result.stderr


def test_termux_minimums_do_not_allow_the_known_vulnerable_pins():
    from packaging.requirements import Requirement

    entries = {}
    for raw in (ROOT / "requirements-termux.txt").read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            requirement = Requirement(line)
            entries[requirement.name.lower()] = requirement.specifier
    assert "2.32.3" not in entries["requests"]
    assert "2.33.0" in entries["requests"]
    assert "1.0.1" not in entries["python-dotenv"]
    assert "1.2.2" in entries["python-dotenv"]


def test_doctor_ci_gate_rejects_unready_resistance(tmp_path):
    body = script(".github/workflows/ci.yml", "- name: Kurulum doktoru ve grafik")
    gate = next(line for line in body.splitlines() if "grep -Eq" in line and "Stabil direnç" in line)
    log = tmp_path / "deploy-doctor.log"
    log.write_text("⚠️ [UYARI] Stabil direnç bu karede hazır değil\n")
    result = run_sh(tmp_path, gate, RUNNER_TEMP=str(tmp_path))
    assert result.returncode != 0
    log.write_text("✅ [OK  ] Stabil direnç bu karede çizildi\n")
    assert run_sh(tmp_path, gate, RUNNER_TEMP=str(tmp_path)).returncode == 0
    log.write_text("⚠️ [UYARI] Stabil direnç hazır ama bu karede çizilmedi\n")
    assert run_sh(tmp_path, gate, RUNNER_TEMP=str(tmp_path)).returncode == 0


def test_graphics_ci_daily_seed_matches_hourly_cutoff_and_avoids_live_dir(tmp_path):
    import json
    from datetime import datetime
    from scripts.ci_seed_graphics import ROOT, main
    main(str(tmp_path))
    daily = json.loads((tmp_path / "AKBNK_gunluk.json").read_text())
    hourly = json.loads((ROOT / "bot_data/AKBNK.json").read_text())
    assert max(datetime.fromisoformat(r['timestamp']).date() for r in daily) <= max(
        datetime.fromisoformat(r['timestamp']).date() for r in hourly)
    with pytest.raises(ValueError):
        main(str(ROOT / 'bot_data'))
