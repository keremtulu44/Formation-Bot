#!/usr/bin/env python3
"""Read-only GitHub Actions keepalive cadence and step audit.

Run in the repository with ``python scripts/keepalive_audit.py`` or specify
``--repo OWNER/REPO``. Only workflow/run/job metadata is read via the logged-in
``gh`` CLI; it never reads secrets, downloads raw logs, or pings Render. Exit 1
means observed cadence is worse than the threshold; 2 means the audit is
incomplete. Green job conclusions are never treated as successful HTTP pings.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ISTANBUL = ZoneInfo("Europe/Istanbul")
UTC = timezone.utc


class AuditError(Exception):
    pass


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(UTC) if result.tzinfo is not None else None
    except ValueError:
        return None


def gh_json(endpoint):
    try:
        call = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True,
                              timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AuditError(f"GitHub metadata sorgusu çalışmadı ({type(exc).__name__})") from exc
    if call.returncode:
        # Avoid printing gh stderr: it may contain paths or other sensitive details.
        raise AuditError("GitHub metadata sorgusu başarısız; gh erişim/yetkisini kontrol edin")
    try:
        return json.loads(call.stdout)
    except ValueError as exc:
        raise AuditError("GitHub geçersiz metadata döndürdü") from exc


def analyze_runs(payload, *, since=None, threshold_minutes=15.0, now=None):
    if not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list):
        raise AuditError("workflow_runs listesi bulunamadı")
    selected, invalid = [], 0
    for run in payload["workflow_runs"]:
        if not isinstance(run, dict) or run.get("event") != "schedule":
            continue
        stamp = timestamp(run.get("run_started_at")) or timestamp(run.get("created_at"))
        if stamp is None:
            invalid += 1
            continue
        if since is None or stamp >= since:
            selected.append((stamp, run))
    selected.sort(key=lambda item: item[0])
    gaps = [(right[0] - left[0]).total_seconds() / 60 for left, right in zip(selected, selected[1:])]
    now = now or datetime.now(UTC)
    latest_age = (now - selected[-1][0]).total_seconds() / 60 if selected else None

    # Count ONLY windows completely covered by the sample's first/last starts.
    # A start in the window does not prove GET was executed, or even which
    # workflow revision/config was active; job steps must be checked separately.
    windows = []
    if selected:
        first = selected[0][0].astimezone(ISTANBUL)
        last = selected[-1][0].astimezone(ISTANBUL)
        day = first.date()
        while day <= last.date():
            lo = datetime.combine(day, time(2, 0), tzinfo=ISTANBUL)
            hi = datetime.combine(day, time(2, 21), tzinfo=ISTANBUL)
            if first <= lo and last >= hi:
                count = sum(lo <= stamp.astimezone(ISTANBUL) < hi for stamp, _ in selected)
                windows.append((day.isoformat(), count))
            day += timedelta(days=1)

    return {
        "selected": selected, "invalid": invalid, "gaps": gaps,
        "median_gap": statistics.median(gaps) if gaps else None,
        "max_gap": max(gaps) if gaps else None,
        "over_threshold": sum(gap > threshold_minutes for gap in gaps),
        "latest_age": latest_age, "windows": windows,
        "conclusions": Counter(str(run.get("conclusion") or run.get("status") or "unknown")
                               for _, run in selected),
    }


def health_step(jobs_payload):
    """Return step conclusion, never infer it from the job conclusion."""
    if not isinstance(jobs_payload, dict) or not isinstance(jobs_payload.get("jobs"), list):
        return "unknown"
    found = []
    for job in jobs_payload["jobs"]:
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict) and step.get("name") == "GET /health":
                found.append(str(step.get("conclusion") or step.get("status") or "unknown"))
    return ",".join(found) if found else "missing"


def parser():
    p = argparse.ArgumentParser(description="GitHub keepalive zamanlamasını salt okunur denetle")
    p.add_argument("--repo", help="OWNER/REPO; boşsa gh mevcut repoyu kullanır")
    p.add_argument("--limit", type=int, default=100, help="en fazla 100 schedule koşusu (varsayılan: 100)")
    p.add_argument("--sample-jobs", type=int, default=12, help="adımları ayrıca kontrol edilecek son koşu sayısı; 0 = yok")
    p.add_argument("--max-gap-minutes", type=float, default=15, help="uyarı eşiği, dakika (varsayılan: 15)")
    p.add_argument("--since", help="yalnız bu ISO-8601 UTC/offset anından sonraki koşular")
    p.add_argument("--input", type=Path, help="çevrimdışı workflow runs JSON dosyası; jobs API çağrılmaz")
    p.add_argument("--workflow-state", help="--input için biliniyorsa workflow durumu; aksi halde unknown")
    p.add_argument("--now", help="tekrarlanabilir test için timezone içeren ISO-8601 anı")
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if not 2 <= args.limit <= 100 or not 0 <= args.sample_jobs <= args.limit:
        p.error("--limit 2..100 ve --sample-jobs 0..limit olmalı")
    if not 0 < args.max_gap_minutes < 100000:
        p.error("--max-gap-minutes pozitif ve sonlu olmalı")
    if args.repo and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        p.error("--repo OWNER/REPO biçiminde olmalı")
    since, now = timestamp(args.since), timestamp(args.now)
    if (args.since and since is None) or (args.now and now is None):
        p.error("--since ve --now timezone içeren ISO-8601 olmalı")
    repo = args.repo or "{owner}/{repo}"
    root = f"repos/{repo}/actions"
    try:
        if args.input:
            try:
                data = json.loads(args.input.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise AuditError(f"Metadata dosyası okunamadı ({type(exc).__name__})") from exc
            state = args.workflow_state or "unknown"
        else:
            workflow = gh_json(f"{root}/workflows/keepalive.yml")
            state = workflow.get("state", "unknown") if isinstance(workflow, dict) else "unknown"
            data = gh_json(f"{root}/workflows/keepalive.yml/runs?event=schedule&per_page={args.limit}")
        report = analyze_runs(data, since=since, threshold_minutes=args.max_gap_minutes, now=now)
    except AuditError as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 2

    rows = report["selected"]
    print(f"Workflow durumu: {state} | schedule koşusu: {len(rows)}")
    if rows:
        print(f"Aralık (UTC): {rows[0][0].isoformat()} → {rows[-1][0].isoformat()}")
        print("Job sonuçları (HTTP kanıtı değildir): " + ", ".join(
            f"{key}={value}" for key, value in sorted(report["conclusions"].items())))
    if report["gaps"]:
        print(f"Başlangıç aralığı: medyan={report['median_gap']:.1f} dk, "
              f"maksimum={report['max_gap']:.1f} dk, "
              f">{args.max_gap_minutes:g} dk={report['over_threshold']}/{len(report['gaps'])}")
        print(f"Son schedule başlangıcından bu yana: {report['latest_age']:.1f} dk")
    else:
        print("UYARI: Aralık hesabı için en az iki geçerli schedule koşusu gerekli.")
    windows = report["windows"]
    if windows:
        no_starts = sum(count == 0 for _, count in windows)
        print(f"02:00–02:20 İstanbul: örneklemi tam kapsanan {len(windows)} gecenin "
              f"{no_starts} tanesinde schedule başlangıcı yok")
        print("  Önceki workflow sürümü/özel ayarlar ve job adımı ayrıca doğrulanmalıdır.")
    if report["invalid"]:
        print(f"UYARI: {report['invalid']} koşunun zamanı okunamadı.")

    incomplete = report["invalid"] > 0 or state == "unknown" or len(rows) < 2
    ping_failure = False
    if args.input:
        print("Çevrimdışı veri: güncel workflow/job adımları sorgulanmadı.")
    elif args.sample_jobs:
        outcomes = Counter()
        for _, run in reversed(rows[-args.sample_jobs:]):
            run_id = run.get("id")
            if not isinstance(run_id, int) or run_id <= 0:
                outcome = "unknown"
            else:
                try:
                    outcome = health_step(gh_json(f"{root}/runs/{run_id}/jobs?per_page=100"))
                except AuditError:
                    outcome = "unknown"
            outcomes[outcome] += 1
        print("Örneklenen GET /health adımları: " + ", ".join(
            f"{key}={value}" for key, value in sorted(outcomes.items())))
        observed_steps = {item for key in outcomes for item in key.split(",")}
        if observed_steps & {"unknown", "missing", "queued", "in_progress", "pending", "waiting"}:
            incomplete = True
        ping_failure = bool(observed_steps & {"failure", "timed_out", "cancelled", "action_required"})
    else:
        print("Job adımları sorgulanmadı; HTTP ping kanıtı yok.")
    print("Not: Yeşil job veya schedule başlangıcı HTTP ping, hedef kimliği, "
          "bot hazır oluşu ya da gelecekteki çalışma garantisi değildir.")

    violated = state not in ("active", "unknown") or report["over_threshold"] > 0 or ping_failure
    if report["latest_age"] is not None:
        if report["latest_age"] < -2:
            incomplete = True
            print("UYARI: Son koşu sistem saatinden ileride.")
        elif report["latest_age"] > args.max_gap_minutes:
            violated = True
    if violated:
        print("SONUÇ: Cadence, workflow durumu veya örneklenen ping adımı sorunlu; "
              "bağımsız izleme/uyandırma gerekir.")
        return 1
    if incomplete:
        print("SONUÇ: Kanıt eksik; sağlıklı kabul edilemez.")
        return 2
    print("SONUÇ: Örneklenen schedule aralıkları eşik içinde; bu gelecek için garanti değildir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
