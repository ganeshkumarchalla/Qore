"""Run the local daily quality baseline without publishing or contacting services.

Child output is captured in memory and never copied to logs or reports. Only
numeric test summaries, return codes, and structured report status are retained.
This is deliberately stronger than attempting to redact unknown secret formats.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"


def isolated_environment():
    environment = dict(os.environ)
    for name in list(environment):
        upper = name.upper()
        if (upper.startswith(("SUPABASE_", "GEMINI_", "GOOGLE_", "OPENAI_", "ANTHROPIC_", "AWS_", "AZURE_"))
                or upper.endswith(("_API_KEY", "_ACCESS_TOKEN", "_REFRESH_TOKEN", "_SECRET_KEY", "_PASSWORD"))
                or upper in {"QORE_ENV", "QORE_REQUIRE_AUTH", "RENDER", "RENDER_EXTERNAL_URL"}):
            environment.pop(name, None)
    environment.update(QORE_STORAGE="sqlite", PYTHONIOENCODING="utf-8", PYTEST_CURRENT_TEST="isolated_daily_quality")
    return environment


def safe_output_summary(output):
    """Return counts only, even when a child prints an unknown credential type."""
    summary = {"captured_lines": len(output.splitlines()), "raw_output_retained": False}
    for label in ("passed", "failed", "skipped", "errors"):
        matches = re.findall(r"\b(\d+) " + label + r"\b", output)
        if matches:
            summary[label] = int(matches[-1])
    return summary


def stop_process_tree(process):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.kill()


def run_stage(stage, environment):
    started = time.perf_counter()
    started_wall = time.time()
    result = {"name": stage["name"], "timeout_seconds": stage["timeout"], "passed": False}
    output = ""
    process = None
    try:
        flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
        process = subprocess.Popen(stage["command"], cwd=ROOT, env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            creationflags=flags, start_new_session=os.name != "nt")
        try:
            output, _ = process.communicate(timeout=stage["timeout"])
            result.update(returncode=process.returncode, passed=process.returncode == 0, timed_out=False)
        except subprocess.TimeoutExpired:
            stop_process_tree(process)
            output, _ = process.communicate(timeout=15)
            result.update(returncode=process.returncode, timed_out=True, error="Stage exceeded its bounded execution time.")
    except (OSError, subprocess.SubprocessError):
        if process and process.poll() is None:
            try:
                stop_process_tree(process)
            except (OSError, subprocess.SubprocessError):
                pass
        result["error"] = "Stage could not complete. Inspect its local structured report or rerun the named check."
    result["output"] = safe_output_summary(output)
    result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    if stage.get("report"):
        path = EVIDENCE / stage["report"]
        result["report"] = str(path.relative_to(ROOT))
        try:
            if path.stat().st_mtime < started_wall - 1:
                raise ValueError("Stale report")
            report = json.loads(path.read_text(encoding="utf-8"))
            status = report.get("status") or report.get("summary", {}).get("status")
            result["reported_status"] = status if status in {"PASSED", "ACTION_REQUIRED", "HEALTHY", "UNHEALTHY", "passed", "failed"} else "unknown"
            result["passed"] = result["passed"] and status == stage["expected_status"]
            if isinstance(report.get("passed_checks"), int) and isinstance(report.get("total_checks"), int):
                result["checks_passed"], result["checks_total"] = report["passed_checks"], report.get("total_checks")
            if isinstance(report.get("passed"), int) and isinstance(report.get("failed"), int):
                result["checks_passed"], result["checks_failed"] = report["passed"], report.get("failed")
            if "summary" in report:
                counts = report["summary"].get("severity_counts", {})
                result["findings"] = {severity: counts[severity] for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO") if isinstance(counts.get(severity), int)}
        except (OSError, ValueError, TypeError, AttributeError):
            result["passed"] = False
            result["error"] = "A fresh, valid structured report was not produced."
    return result


def main():
    EVIDENCE.mkdir(exist_ok=True)
    environment = isolated_environment()
    stages = [
        {"name": "Security and secret exposure", "command": [sys.executable, "scripts/security_checker.py", "--check"], "timeout": 120,
         "report": "security_report.json", "expected_status": "PASSED"},
        {"name": "Frontend health and production build", "command": [sys.executable, "scripts/frontend_auditor.py"], "timeout": 180,
         "report": "frontend_health_report.json", "expected_status": "HEALTHY"},
        {"name": "Backend and security regression suite", "command": [sys.executable, "-m", "pytest", "backend/tests", "-q"], "timeout": 600},
        {"name": "Real quantum and ledger acceptance", "command": [sys.executable, "scripts/production_acceptance.py"], "timeout": 180,
         "report": "production_acceptance.json", "expected_status": "passed"},
    ]
    results = []
    for stage in stages:
        print("Running: " + stage["name"], flush=True)
        result = run_stage(stage, environment)
        results.append(result)
        print(("PASS: " if result["passed"] else "FAIL: ") + stage["name"], flush=True)
    report = {"recorded_at": datetime.now(timezone.utc).isoformat(), "status": "passed" if all(item["passed"] for item in results) else "action_required",
              "stages_passed": sum(item["passed"] for item in results), "stages_total": len(results), "stages": results,
              "privacy": "No raw child output is retained. Only counts, statuses, timings, and report locations are aggregated. Provider credentials are removed from child environments.",
              "operations": "Local verification only. No push, deployment, dependency installation, provider call, or live-user data modification is performed.",
              "scope": "A daily regression baseline, supplemented by the scheduled specialist reviews. Passing is not a penetration test, SEO ranking guarantee, load test, hardware validation, or proof of universal Qiskit compatibility."}
    path = EVIDENCE / "daily_quality_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# QORE daily quality baseline", "", f"Result: **{report['status'].upper()}** — {report['stages_passed']}/{report['stages_total']} stages passed.", "", "| Stage | Result | Seconds |", "| --- | --- | ---: |"]
    lines.extend(f"| {item['name']} | {'PASS' if item['passed'] else 'ACTION REQUIRED'} | {item['elapsed_seconds']} |" for item in results)
    lines.extend(["", report["privacy"], "", report["operations"], "", report["scope"], "", "Detailed machine-readable metrics are stored in `daily_quality_report.json`; individual report locations are included there."])
    (EVIDENCE / "daily_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "stages_passed": report["stages_passed"], "stages_total": report["stages_total"], "report": str(path)}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
