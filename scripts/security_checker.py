#!/usr/bin/env python3
"""
QORE Multi-Agent Security Audit & Hardening Engine
Checks user project files, prevents credential leakage, audits IDE/environment configuration,
and generates structured compliance reports.
"""

import os
import sys
import re
import json
import argparse
import base64
import fnmatch
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

# Root directory of QORE
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Files and directories to skip from secret scanning
IGNORED_DIRS = {
    ".venv", "venv", "node_modules", ".git", ".pytest_cache", ".tmp",
    "dist", "build", "__pycache__", ".idea", ".cache", "evidence",
    "temp_edge_profile", "browser_profiles", "playwright-report", "test-results",
    "website_captures", "media", "Pictures", "video_assets", "screen_recordings",
}

IGNORED_FILES = {
    "package-lock.json", "requirements-lock.txt", "security_report.json"
}

def mask_secret(val: str) -> str:
    """Mask secret value so it is never exposed in logs or reports."""
    return "[REDACTED]"


def project_files(root: Path):
    """Prune generated/private browser trees before traversing their contents."""
    for directory, folders, files in os.walk(root, followlinks=False):
        folders[:] = [name for name in folders if name not in IGNORED_DIRS
                      and not (Path(directory) / name).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                yield path


def ignored_local_env(path: Path, root: Path) -> bool:
    """Skip an ignored server .env without opening it; client .env is audited."""
    if path.name != ".env" or "frontend" in path.relative_to(root).parts:
        return False
    if (root / ".git").exists():
        try:
            result = subprocess.run(["git", "check-ignore", "--quiet", "--", str(path.relative_to(root))],
                                    cwd=root, capture_output=True, timeout=5,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False
    ignore = root / ".gitignore"
    if not ignore.exists():
        return False
    relative = path.relative_to(root).as_posix()
    ignored = False
    for line in ignore.read_text(encoding="utf-8", errors="ignore").splitlines():
        pattern = line.strip()
        if not pattern or pattern.startswith("#"):
            continue
        negate = pattern.startswith("!")
        pattern = pattern.lstrip("!").lstrip("/")
        if fnmatch.fnmatch(relative, pattern) or ("/" not in pattern and fnmatch.fnmatch(path.name, pattern)):
            ignored = not negate
    return ignored


class Finding:
    def __init__(self, agent: str, severity: str, title: str, description: str, file_path: str = "", recommendation: str = "", can_fix: bool = False):
        self.agent = agent
        self.severity = severity  # CRITICAL, HIGH, MEDIUM, LOW, INFO
        self.title = title
        self.description = description
        self.file_path = file_path
        self.recommendation = recommendation
        self.can_fix = can_fix

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "recommendation": self.recommendation,
            "can_fix": self.can_fix
        }


# ==============================================================================
# Agent 1: Secret & Credential Leakage Scanner Agent
# ==============================================================================
class SecretScannerAgent:
    NAME = "Secrets & Credentials Agent"

    SECRET_PATTERNS = [
        (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "Google / Gemini API Key"),
        (re.compile(r"sk-(?:proj-|svcacct-)?[a-zA-Z0-9_-]{20,}"), "OpenAI API Key"),
        (re.compile(r"sb_secret_[A-Za-z0-9_-]{20,}"), "Supabase Secret Key"),
        (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS Access Key ID"),
        (re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}"), "GitHub Token"),
        (re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"), "Private Key Certificate"),
        (re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}"), "Slack API Token"),
        (re.compile(r"(?:postgres|mysql|mongodb|redis)://[^:\s]+:[^@\s]+@[^\s]+"), "Database Connection URL with Credentials"),
        (re.compile(r"(?:password|passwd|secret_key|api_secret)\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.IGNORECASE), "Hardcoded Secret / Password Assignment"),
    ]

    JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{8,}\b")
    SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml", ".toml", ".md", ".sh", ".ps1", ".html", ".ini", ".cfg", ".conf", ".xml", ".sql", ".tf", ".properties"}

    @classmethod
    def credential_matches(cls, content):
        for pattern, description in cls.SECRET_PATTERNS:
            for match in pattern.finditer(content):
                value = match.group(0)
                # Explicit fixture/placeholder password assignments are not live
                # credentials. Never exempt structured key tokens merely because
                # the token happens to contain a word such as "example".
                if description == "Hardcoded Secret / Password Assignment":
                    literal = re.search(r"['\"]([^'\"]+)['\"]$", value)
                    if literal and literal.group(1).lower().startswith(("your_", "<", "fixture-", "test-", "example-", "not-a-real-")):
                        continue
                yield description, value, content.count("\n", 0, match.start()) + 1
        for match in cls.JWT_PATTERN.finditer(content):
            token = match.group(0)
            payload = token.split(".")[1]
            if len(payload) > 16384:
                continue
            try:
                decoded = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            except (ValueError, UnicodeError):
                continue
            if isinstance(decoded, dict) and decoded.get("role") == "service_role":
                yield "Supabase Service Role JWT", token, content.count("\n", 0, match.start()) + 1

    def run(self, root: Path) -> List[Finding]:
        findings = []
        for path in project_files(root):
            if path.name in IGNORED_FILES or ignored_local_env(path, root):
                continue
            is_config = path.name.startswith(".env") or path.name.lower().startswith(("dockerfile", "containerfile"))
            if path.suffix.lower() not in self.SOURCE_SUFFIXES and not is_config:
                continue
            relative = str(path.relative_to(root))
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                findings.append(Finding(self.NAME, "HIGH", "Source/configuration could not be scanned",
                    "The file was unreadable. Its contents have not been certified as free of secrets.", relative,
                    "Restore read access and rerun the audit."))
                continue
            for description, value, line in self.credential_matches(content):
                findings.append(Finding(self.NAME, "CRITICAL",
                    "Real Secret in .env.example" if path.name == ".env.example" else f"Potential Hardcoded {description}",
                    f"Found {description} at line {line}: {mask_secret(value)}", relative,
                    "Remove the credential from source/configuration, rotate it if exposed, and use server environment configuration."))
            if "frontend" in path.relative_to(root).parts:
                for match in re.finditer(r"VITE_[A-Z0-9_]*(?:KEY|SECRET|TOKEN|AUTH)\s*[:=]\s*['\"]?([^'\"\s,;]+)", content, re.IGNORECASE):
                    value = match.group(1)
                    if len(value) > 8 and not value.lower().startswith(("your_", "<", "placeholder")):
                        findings.append(Finding(self.NAME, "CRITICAL", "Client-Side Secret Exposure via VITE_ Variable",
                            f"A credential-like VITE_ value is exposed to client builds: {mask_secret(value)}", relative,
                            "Keep sensitive keys on the backend and route authenticated requests through /api."))
        return findings


# ==============================================================================
# Agent 2: File Safety & Git Exposure Agent
# ==============================================================================
class FileExposureAgent:
    NAME = "File Safety & Git Exposure Agent"

    REQUIRED_IGNORE_PATTERNS = [
        (".env", "Root environment configuration (.env)"),
        (".env.*", "Environment variations (.env.local, .env.production)"),
        ("*.pem", "Privacy-enhanced mail certificates (*.pem)"),
        ("*.key", "Private cryptographic keys (*.key)"),
        ("data/", "Application SQLite and local state database files (data/)"),
        ("*.sqlite", "SQLite database files (*.sqlite)"),
        ("*.sqlite3", "SQLite database files (*.sqlite3)"),
        ("*.sqlite*", "SQLite journals and database variants (*.sqlite*)"),
        ("*.db", "Database files (*.db)"),
        ("*.swp", "Editor swap files (*.swp)"),
        ("*.bak", "Editor backup files (*.bak)"),
        ("credentials.json", "OAuth / Service account credentials (credentials.json)"),
    ]

    def run(self, root: Path) -> List[Finding]:
        findings = []
        gitignore_path = root / ".gitignore"

        # 1. Check .gitignore presence and coverage
        if not gitignore_path.exists():
            findings.append(Finding(
                agent=self.NAME,
                severity="CRITICAL",
                title="Missing .gitignore File",
                description="No .gitignore found at repository root. Sensitive files and virtual environments may be exposed to version control.",
                file_path=".gitignore",
                recommendation="Create a comprehensive .gitignore file.",
                can_fix=True
            ))
        else:
            lines = [line.strip() for line in gitignore_path.read_text(encoding="utf-8", errors="ignore").splitlines()]
            for pattern, desc in self.REQUIRED_IGNORE_PATTERNS:
                if pattern not in lines and not any(p.startswith(pattern) for p in lines):
                    findings.append(Finding(
                        agent=self.NAME,
                        severity="HIGH",
                        title=f"Unprotected Sensitive File Pattern in .gitignore: {pattern}",
                        description=f"{desc} is not explicitly excluded in .gitignore.",
                        file_path=".gitignore",
                        recommendation=f"Add '{pattern}' to .gitignore to prevent accidental commit/push.",
                        can_fix=True
                    ))

        # 2. Check for dangerous leftover or swap files
        for p in project_files(root):
            lower_name = p.name.lower()
            if lower_name.endswith((".bak", ".swp", ".orig", ".tmp", "~")) and not p.parts[len(root.parts):][0] == ".tmp":
                findings.append(Finding(
                    agent=self.NAME,
                    severity="MEDIUM",
                    title="Exposed Editor Backup / Swap File",
                    description=f"Temporary backup file found: {p.name}",
                    file_path=str(p.relative_to(root)),
                    recommendation="Remove backup/swap files to avoid exposing previous code versions or deleted secrets."
                ))

        # Git membership is inspected by name only; no credential file is read.
        if (root / ".git").exists():
            try:
                result = subprocess.run(["git", "ls-files", "--cached", "-z"], cwd=root,
                    capture_output=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                if result.returncode != 0:
                    raise OSError("Git inventory unavailable")
                for tracked in result.stdout.decode("utf-8", errors="replace").split("\0"):
                    name = Path(tracked).name
                    if name == ".env" or (name.startswith(".env.") and name != ".env.example") or name.endswith((".pem", ".key", ".db", ".sqlite", ".sqlite3")) or name == "credentials.json":
                        findings.append(Finding(self.NAME, "HIGH", "Sensitive file is tracked by Git",
                            "A sensitive configuration/database/credential path is present in Git's index; ignore rules do not untrack it.",
                            tracked, "Remove the sensitive file from version control while preserving the local file; rotate any exposed credentials."))
            except (OSError, subprocess.TimeoutExpired):
                findings.append(Finding(self.NAME, "HIGH", "Git exposure inventory unavailable",
                    "Tracked credential paths could not be audited.", ".git", "Restore Git access and rerun the audit."))

        # 3. Check .env file presence and permissions
        env_file = root / ".env"
        if env_file.exists():
            # Ensure .env is not world-writable or placed in public static folder
            if "frontend" in env_file.parts or "dist" in env_file.parts:
                findings.append(Finding(
                    agent=self.NAME,
                    severity="CRITICAL",
                    title=".env File in Public Web Directory",
                    description=f".env located in static web folder: {env_file}",
                    file_path=str(env_file.relative_to(root)),
                    recommendation="Move .env to the root directory only and ensure it is never in frontend."
                ))
            # On POSIX systems, check permissions (e.g., 0600 or 0640)
            if hasattr(os, "stat") and os.name != "nt":
                mode = env_file.stat().st_mode
                if mode & 0o007:
                    findings.append(Finding(
                        agent=self.NAME,
                        severity="HIGH",
                        title="Insecure .env File Permissions",
                        description=f".env file has overly permissive world access ({oct(mode)}).",
                        file_path=".env",
                        recommendation="Restrict permissions to 0600 or 0640 (chmod 600 .env)."
                    ))

        return findings

    def fix(self, root: Path) -> List[str]:
        actions = []
        gitignore_path = root / ".gitignore"
        lines = []
        if gitignore_path.exists():
            lines = gitignore_path.read_text(encoding="utf-8", errors="ignore").splitlines()

        added = []
        for pattern, _ in self.REQUIRED_IGNORE_PATTERNS:
            if pattern not in lines:
                added.append(pattern)

        if added:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\n# Security Audit Auto-Hardening\n")
                for p in added:
                    f.write(f"{p}\n")
            actions.append(f"Appended {len(added)} missing security patterns to .gitignore")

        return actions


# ==============================================================================
# Agent 3: IDE & Environment Hardening Agent
# ==============================================================================
class IDEEnvironmentAgent:
    NAME = "IDE & Environment Hardening Agent"

    def run(self, root: Path) -> List[Finding]:
        findings = []
        vscode_dir = root / ".vscode"
        settings_path = vscode_dir / "settings.json"

        if not settings_path.exists():
            findings.append(Finding(
                agent=self.NAME,
                severity="MEDIUM",
                title="Missing Hardened IDE Settings (.vscode/settings.json)",
                description="Workspace does not have explicit VS Code / Antigravity trust and telemetry restrictions configured.",
                file_path=".vscode/settings.json",
                recommendation="Create .vscode/settings.json with workspace trust enabled, search exclusion for secrets, and telemetry disabled.",
                can_fix=True
            ))
        else:
            try:
                settings = json.loads(settings_path.read_text(encoding="utf-8", errors="ignore"))
                if not settings.get("security.workspace.trust.enabled", False):
                    findings.append(Finding(
                        agent=self.NAME,
                        severity="MEDIUM",
                        title="Workspace Trust Disabled in IDE",
                        description="'security.workspace.trust.enabled' is not set to true.",
                        file_path=".vscode/settings.json",
                        recommendation="Set 'security.workspace.trust.enabled': true to prevent untrusted script execution.",
                        can_fix=True
                    ))
                if settings.get("telemetry.telemetryLevel") != "off":
                    findings.append(Finding(
                        agent=self.NAME,
                        severity="LOW",
                        title="Editor Telemetry Enabled",
                        description="Editor telemetry is not disabled, which could transmit diagnostic fragments.",
                        file_path=".vscode/settings.json",
                        recommendation="Set 'telemetry.telemetryLevel': 'off' in .vscode/settings.json.",
                        can_fix=True
                    ))
            except Exception as e:
                findings.append(Finding(
                    agent=self.NAME,
                    severity="LOW",
                    title="Invalid .vscode/settings.json Format",
                    description=f"Could not parse settings.json: {e}",
                    file_path=".vscode/settings.json",
                    recommendation="Ensure settings.json is valid JSON."
                ))

        # Check AGENTS.md rules file exists
        agents_md = root / "AGENTS.md"
        if not agents_md.exists():
            findings.append(Finding(
                agent=self.NAME,
                severity="MEDIUM",
                title="Missing Workspace Agent Security Rules (AGENTS.md)",
                description="AGENTS.md is missing; AI coding assistants do not have persistent security directives for this project.",
                file_path="AGENTS.md",
                recommendation="Create AGENTS.md with zero-exposure secret rules and safe file guidelines.",
                can_fix=True
            ))

        return findings

    def fix(self, root: Path) -> List[str]:
        actions = []
        vscode_dir = root / ".vscode"
        vscode_dir.mkdir(parents=True, exist_ok=True)
        settings_path = vscode_dir / "settings.json"

        settings = {}
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
            except Exception:
                settings = {}

        updated = False
        if not settings.get("security.workspace.trust.enabled"):
            settings["security.workspace.trust.enabled"] = True
            settings["security.workspace.trust.startupPrompt"] = "always"
            updated = True

        if settings.get("telemetry.telemetryLevel") != "off":
            settings["telemetry.telemetryLevel"] = "off"
            updated = True

        search_exclude = settings.get("search.exclude", {})
        for pattern in ["**/.env*", "**/*.pem", "**/*.key", "**/.venv", "**/data/*.sqlite3"]:
            if pattern not in search_exclude:
                search_exclude[pattern] = True
                updated = True
        settings["search.exclude"] = search_exclude

        if updated:
            settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
            actions.append("Configured secure settings in .vscode/settings.json")

        return actions


# ==============================================================================
# Agent 4: Config & Dependency Security Agent
# ==============================================================================
class ConfigAuditAgent:
    NAME = "Config & Dependency Security Agent"

    def run(self, root: Path) -> List[Finding]:
        findings = []

        # 1. Audit CORS configuration in backend
        main_py = root / "backend" / "qore" / "main.py"
        if main_py.exists():
            content = main_py.read_text(encoding="utf-8", errors="ignore")
            if 'allow_origins=["*"]' in content and "allow_credentials=True" in content:
                findings.append(Finding(
                    agent=self.NAME,
                    severity="HIGH",
                    title="Insecure Wildcard CORS with Credentials",
                    description="CORS allows '*' origin combined with credentials, enabling cross-origin authenticated attacks.",
                    file_path="backend/qore/main.py",
                    recommendation="Specify explicit trusted origins (e.g., http://127.0.0.1:5173) instead of '*' when credentials are true."
                ))

        # 2. Check requirements-lock.txt for known vulnerable flags
        lock_file = root / "requirements-lock.txt"
        if lock_file.exists():
            content = lock_file.read_text(encoding="utf-8", errors="ignore")
            # Verify lock file has hashes or pinned versions
            unpinned = [line for line in content.splitlines() if line.strip() and not line.strip().startswith("#") and "==" not in line and "@" not in line]
            if len(unpinned) > 5:
                findings.append(Finding(
                    agent=self.NAME,
                    severity="LOW",
                    title="Unpinned Python Dependencies",
                    description=f"{len(unpinned)} dependencies in requirements-lock.txt are not strictly pinned.",
                    file_path="requirements-lock.txt",
                    recommendation="Pin exact package versions to ensure reproducible and tamper-free builds."
                ))

        return findings


# ==============================================================================
# Coordinator / Security Engine Runner
# ==============================================================================
class SecurityCoordinator:
    def __init__(self, root: Path):
        self.root = root
        self.agents = [
            SecretScannerAgent(),
            FileExposureAgent(),
            IDEEnvironmentAgent(),
            ConfigAuditAgent()
        ]

    def audit(self) -> List[Finding]:
        all_findings = []
        for agent in self.agents:
            all_findings.extend(agent.run(self.root))
        return all_findings

    def fix(self) -> List[str]:
        actions = []
        for agent in self.agents:
            if hasattr(agent, "fix"):
                actions.extend(agent.fix(self.root))
        return actions

    def generate_reports(self, findings: List[Finding]) -> tuple[Path, Path]:
        evidence_dir = self.root / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)

        json_path = evidence_dir / "security_report.json"
        md_path = evidence_dir / "security_report.md"

        severity_counts = {
            "CRITICAL": sum(1 for f in findings if f.severity == "CRITICAL"),
            "HIGH": sum(1 for f in findings if f.severity == "HIGH"),
            "MEDIUM": sum(1 for f in findings if f.severity == "MEDIUM"),
            "LOW": sum(1 for f in findings if f.severity == "LOW"),
            "INFO": sum(1 for f in findings if f.severity == "INFO")
        }

        report_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_root": str(self.root),
            "summary": {
                "total_findings": len(findings),
                "severity_counts": severity_counts,
                "status": "PASSED" if severity_counts["CRITICAL"] == 0 and severity_counts["HIGH"] == 0 else "ACTION_REQUIRED"
            },
            "findings": [f.to_dict() for f in findings]
        }

        json_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

        # Generate Human-Readable Markdown
        status_badge = "🟢 SECURE" if report_data["summary"]["status"] == "PASSED" else "🔴 ACTION REQUIRED"
        md_lines = [
            f"# QORE Security & File Safety Audit Report",
            f"",
            f"**Execution Timestamp:** {report_data['timestamp']}  ",
            f"**Audit Status:** {status_badge}  ",
            f"**Target Directory:** `{self.root}`  ",
            f"",
            f"## Severity Summary",
            f"",
            f"| Severity | Count |",
            f"| :--- | :--- |",
            f"| 🚨 **CRITICAL** | {severity_counts['CRITICAL']} |",
            f"| ⚠️ **HIGH** | {severity_counts['HIGH']} |",
            f"| 🟡 **MEDIUM** | {severity_counts['MEDIUM']} |",
            f"| ℹ️ **LOW / INFO** | {severity_counts['LOW'] + severity_counts['INFO']} |",
            f"| **TOTAL** | **{len(findings)}** |",
            f"",
            f"---",
            f"",
            f"## Multi-Agent Audit Scope & Verification Checklist",
            f"",
            f"| Subsystem / Agent | Verification Focus | Status |",
            f"| :--- | :--- | :--- |",
            f"| **Secrets & Credentials Agent** | Source, Dockerfiles, environment examples/variants, frontend variables, modern keys and privileged JWTs | {'FINDINGS' if any(f.agent == SecretScannerAgent.NAME for f in findings) else 'No findings in scanned scope'} |",
            f"| **File Safety & Git Exposure Agent** | Ignore rules, tracked sensitive paths, backups, local environment placement and POSIX permissions | {'FINDINGS' if any(f.agent == FileExposureAgent.NAME for f in findings) else 'No findings in scanned scope'} |",
            f"| **File Permissions & ACLs** | Windows ACLs require a separate host permission inspection | Not verified by this scanner |",
            f"| **IDE & Environment Hardening Agent** | Workspace Trust and telemetry configuration | {'FINDINGS' if any(f.agent == IDEEnvironmentAgent.NAME for f in findings) else 'No findings in scanned scope'} |",
            f"| **Config & Dependency Security Agent** | Credentialed wildcard CORS and dependency pinning heuristics | {'FINDINGS' if any(f.agent == ConfigAuditAgent.NAME for f in findings) else 'No findings in scanned scope'} |",
            f"",
            f"---",
            f"",
            f"## Multi-Agent Findings",
            f""
        ]

        if not findings:
            md_lines.append("✅ **No security deficiencies detected!** All project files, environment configurations, and IDE settings meet security standards.")
        else:
            for idx, f in enumerate(findings, 1):
                icon = "🚨" if f.severity == "CRITICAL" else "⚠️" if f.severity == "HIGH" else "🟡" if f.severity == "MEDIUM" else "ℹ️"
                md_lines.extend([
                    f"### {idx}. {icon} [{f.severity}] {f.title}",
                    f"- **Agent:** {f.agent}",
                    f"- **File:** `{f.file_path or 'Project-wide'}`",
                    f"- **Description:** {f.description}",
                    f"- **Recommendation:** {f.recommendation}",
                    f"- **Auto-fixable:** {'Yes' if f.can_fix else 'No'}",
                    f""
                ])

        md_path.write_text("\n".join(md_lines), encoding="utf-8")
        return json_path, md_path


def main():
    parser = argparse.ArgumentParser(description="QORE Multi-Agent Security Audit Engine")
    parser.add_argument("--check", action="store_true", default=True, help="Run security audit and generate report")
    parser.add_argument("--fix", action="store_true", help="Automatically apply security hardening fixes")
    parser.add_argument("--json", action="store_true", help="Output JSON results to stdout")
    args = parser.parse_args()

    coordinator = SecurityCoordinator(PROJECT_ROOT)

    if args.fix:
        actions = coordinator.fix()
        print(f"Applied {len(actions)} security hardening action(s):")
        for a in actions:
            print(f" - {a}")
        print()

    findings = coordinator.audit()
    json_path, md_path = coordinator.generate_reports(findings)

    if args.json:
        print(json_path.read_text(encoding="utf-8"))
    else:
        critical = sum(1 for f in findings if f.severity == "CRITICAL")
        high = sum(1 for f in findings if f.severity == "HIGH")
        medium = sum(1 for f in findings if f.severity == "MEDIUM")
        low = sum(1 for f in findings if f.severity == "LOW")

        print("=" * 60)
        print("QORE MULTI-AGENT SECURITY AUDIT COMPLETE")
        print("=" * 60)
        print(f"Target:   {PROJECT_ROOT}")
        print(f"Status:   {'PASSED' if critical == 0 and high == 0 else 'ACTION REQUIRED'}")
        print(f"Findings: Critical={critical}, High={high}, Medium={medium}, Low={low}")
        print(f"Reports:  {md_path}")
        print(f"          {json_path}")
        print("=" * 60)

    # Match ACTION_REQUIRED status; a high-severity exposure must fail CI too.
    if any(f.severity in {"CRITICAL", "HIGH"} for f in findings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
