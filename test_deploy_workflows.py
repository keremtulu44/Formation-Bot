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
