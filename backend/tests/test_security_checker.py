"""Secret scanner regressions use generated, nonfunctional fixture credentials."""

import base64
import importlib.util
import json
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location("qore_security_checker", Path(__file__).resolve().parents[2] / "scripts" / "security_checker.py")
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)


def fixture_jwt(role):
    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
    return ".".join((encode({"alg": "HS256", "typ": "JWT"}), encode({"role": role, "iss": "synthetic-fixture"}), "nonfunctional_signature_fixture"))


def test_masking_never_preserves_any_part_of_a_credential():
    for value in ("tiny", "long-fixture-value-123456789", ""):
        assert scanner.mask_secret(value) == "[REDACTED]"


@pytest.mark.parametrize("name", ["Dockerfile", "Dockerfile.runtime", "Containerfile", ".env.production", ".env.example"])
def test_extensionless_build_and_environment_configurations_are_scanned(tmp_path, name):
    credential = "sb_" + "secret_" + "fixture" * 8
    (tmp_path / name).write_text("ENV PRIVATE_PROVIDER_KEY=" + credential, encoding="utf-8")
    findings = scanner.SecretScannerAgent().run(tmp_path)
    assert findings and all(item.severity == "CRITICAL" for item in findings)
    serialized = json.dumps([item.to_dict() for item in findings])
    assert credential not in serialized and credential[:8] not in serialized
    assert "[REDACTED]" in serialized


def test_legacy_service_role_jwt_is_detected_but_public_role_is_not(tmp_path):
    privileged, public = fixture_jwt("service_role"), fixture_jwt("anon")
    (tmp_path / "Dockerfile").write_text("ENV KEY=" + privileged + "\nENV PUBLIC_KEY=" + public, encoding="utf-8")
    findings = scanner.SecretScannerAgent().run(tmp_path)
    assert len(findings) == 1 and "Service Role JWT" in findings[0].title
    serialized = json.dumps(findings[0].to_dict())
    assert privileged not in serialized and public not in serialized


def test_invalid_jwt_does_not_crash_and_test_files_are_not_blanket_exempt(tmp_path):
    tests = tmp_path / "backend" / "tests"
    tests.mkdir(parents=True)
    credential = "AIza" + "example" * 5
    (tests / "unsafe_fixture.py").write_text("KEY='" + credential + "'\nBAD='eyJinvalid.invalid_payload.invalid_signature'", encoding="utf-8")
    findings = scanner.SecretScannerAgent().run(tmp_path)
    assert len(findings) == 1 and "Google" in findings[0].title


def test_ignored_real_env_is_not_opened_but_client_env_and_variants_are_checked(tmp_path, monkeypatch):
    credential = "sb_" + "secret_" + "fixture" * 8
    local = tmp_path / ".env"
    local.write_text("private local configuration", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".env\n.env.*\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("KEY=" + credential, encoding="utf-8")
    client = tmp_path / "frontend"
    client.mkdir()
    (client / ".env").write_text("VITE_PRIVATE_KEY=" + credential, encoding="utf-8")
    original = Path.read_text

    def guarded(path, *args, **kwargs):
        if path == local:
            pytest.fail("Ignored server .env contents must not be opened")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    findings = scanner.SecretScannerAgent().run(tmp_path)
    files = {item.file_path.replace("\\", "/") for item in findings}
    assert ".env" not in files and ".env.local" in files and "frontend/.env" in files
    assert any("VITE_" in item.title for item in findings)


def test_generated_browser_media_and_build_trees_are_pruned(tmp_path):
    credential = "sb_" + "secret_" + "fixture" * 8
    for name in ("temp_edge_profile", "node_modules", "dist", "media", "website_captures"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "Dockerfile").write_text("ENV KEY=" + credential, encoding="utf-8")
    assert scanner.SecretScannerAgent().run(tmp_path) == []


def test_unreadable_source_is_a_finding_instead_of_a_silent_pass(tmp_path, monkeypatch):
    path = tmp_path / "backend.py"
    path.write_text("# source", encoding="utf-8")
    original = Path.read_text

    def denied(candidate, *args, **kwargs):
        if candidate == path:
            raise PermissionError("sensitive diagnostic must not be repeated")
        return original(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", denied)
    findings = scanner.SecretScannerAgent().run(tmp_path)
    assert len(findings) == 1 and findings[0].severity == "HIGH"
    assert "sensitive diagnostic" not in json.dumps(findings[0].to_dict())


def test_report_and_exit_status_do_not_claim_success_for_high_findings(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(scanner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(scanner.sys, "argv", ["security_checker.py", "--check"])
    with pytest.raises(SystemExit) as result:
        scanner.main()
    assert result.value.code == 1
    report = json.loads((tmp_path / "evidence" / "security_report.json").read_text(encoding="utf-8"))
    assert report["summary"]["status"] == "ACTION_REQUIRED"
    assert "PASS (0 leaks)" not in (tmp_path / "evidence" / "security_report.md").read_text(encoding="utf-8")
    assert "ACTION REQUIRED" in capsys.readouterr().out


def test_daily_aggregation_retains_counts_without_unknown_secret_formats():
    spec = importlib.util.spec_from_file_location("qore_daily_quality", Path(__file__).resolve().parents[2] / "scripts" / "daily_quality_report.py")
    daily = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daily)
    marker = "sensitive-format-the-redactor-does-not-know"
    summary = daily.safe_output_summary(marker + "\n17 passed, 2 skipped\n")
    assert summary == {"captured_lines": 2, "raw_output_retained": False, "passed": 17, "skipped": 2}
    assert marker not in json.dumps(summary)


def test_frontend_audit_retains_counts_without_raw_build_output_or_secret_matches(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("qore_frontend_auditor", Path(__file__).resolve().parents[2] / "scripts" / "frontend_auditor.py")
    auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auditor)
    frontend = tmp_path / "frontend"
    (frontend / "src").mkdir(parents=True)
    tsc = frontend / "node_modules" / "typescript" / "bin" / "tsc"
    tsc.parent.mkdir(parents=True)
    tsc.touch()
    (frontend / "tsconfig.json").write_text("{}", encoding="utf-8")
    fixture = "AIzaSy" + "A" * 33
    (frontend / "src" / "fixture.ts").write_text(fixture, encoding="utf-8")
    monkeypatch.setattr(auditor, "FRONTEND_DIR", frontend)
    monkeypatch.setattr(auditor, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(auditor.subprocess, "run", lambda *args, **kwargs: type("Run", (), {"returncode": 1, "stdout": fixture, "stderr": ""})())

    checks = [auditor.check_typescript_compilation("node"), auditor.check_client_secret_isolation()]
    assert checks[0]["diagnostic_count"] == 1
    assert checks[1]["violations"][0]["match_count"] == 1
    assert fixture not in json.dumps(checks)
    assert fixture[:8] not in json.dumps(checks)
    checks[0]["error"] = fixture
    checks[1]["unmatched_routes"] = [fixture]

    monkeypatch.setattr(auditor, "EVIDENCE_DIR", tmp_path / "evidence")
    monkeypatch.setattr(auditor, "REPORT_JSON", tmp_path / "evidence" / "frontend_health_report.json")
    monkeypatch.setattr(auditor, "REPORT_MD", tmp_path / "evidence" / "frontend_health_report.md")
    auditor.generate_reports({"timestamp": "fixture", "status": "DEGRADED", "passed_checks": 0, "total_checks": 2, "node_binary": "node", "checks": checks})
    for report in (auditor.REPORT_JSON, auditor.REPORT_MD):
        assert fixture not in report.read_text(encoding="utf-8")


def test_daily_children_cannot_inherit_provider_credentials(monkeypatch):
    spec = importlib.util.spec_from_file_location("qore_daily_environment", Path(__file__).resolve().parents[2] / "scripts" / "daily_quality_report.py")
    daily = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daily)
    for key in ("SUPABASE_SERVICE_ROLE_KEY", "GEMINI_API_KEY", "CUSTOM_ACCESS_TOKEN", "QORE_REQUIRE_AUTH", "RENDER"):
        monkeypatch.setenv(key, "synthetic-fixture-value")
    environment = daily.isolated_environment()
    assert not {"SUPABASE_SERVICE_ROLE_KEY", "GEMINI_API_KEY", "CUSTOM_ACCESS_TOKEN", "QORE_REQUIRE_AUTH", "RENDER"}.intersection(environment)
    assert environment["QORE_STORAGE"] == "sqlite"


def test_daily_timeout_is_bounded_and_does_not_retain_child_output():
    spec = importlib.util.spec_from_file_location("qore_daily_timeout", Path(__file__).resolve().parents[2] / "scripts" / "daily_quality_report.py")
    daily = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daily)
    marker = "unknown-sensitive-diagnostic-format"
    stage = {"name": "Synthetic timeout", "timeout": .2,
             "command": [daily.sys.executable, "-c", f"import time; print({marker!r}, flush=True); time.sleep(10)"]}
    result = daily.run_stage(stage, daily.isolated_environment())
    assert result["passed"] is False and result["timed_out"] is True
    assert result["elapsed_seconds"] < 5
    assert marker not in json.dumps(result)
    assert result["output"]["raw_output_retained"] is False
