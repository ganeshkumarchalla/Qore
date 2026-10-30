"""
QORE Autonomous Frontend Health & Bug Audit Engine
Validates frontend build, TypeScript integrity, UI styling constraints,
API contract adherence, and zero-exposure security protocols.
"""

import os
import sys
import json
import glob
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = WORKSPACE_ROOT / "frontend"
EVIDENCE_DIR = WORKSPACE_ROOT / "evidence"
REPORT_MD = EVIDENCE_DIR / "frontend_health_report.md"
REPORT_JSON = EVIDENCE_DIR / "frontend_health_report.json"

def find_node_executable() -> str:
    """Locate node.exe on the host system."""
    # Check PATH first
    import shutil
    node_path = shutil.which("node")
    if node_path and os.path.exists(node_path):
        return node_path
    
    # Check known local runtimes
    candidates = [
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Users\ganes\AppData\Local\OpenAI\Codex\runtimes\cua_node\2b841c3d44b123ec\bin\node.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
            
    # Glob search in local appdata if not found
    app_data = os.environ.get("LOCALAPPDATA", "")
    if app_data:
        matches = glob.glob(os.path.join(app_data, "OpenAI", "**", "node.exe"), recursive=True)
        if matches:
            return matches[0]
            
    return "node"

def check_typescript_compilation(node_bin: str) -> dict:
    """Run TypeScript compiler in noEmit mode."""
    tsc_script = FRONTEND_DIR / "node_modules" / "typescript" / "bin" / "tsc"
    tsconfig = FRONTEND_DIR / "tsconfig.json"
    
    if not tsc_script.exists():
        return {
            "name": "TypeScript Type-Check",
            "passed": False,
            "error": f"tsc script not found at {tsc_script}",
            "details": []
        }
        
    cmd = [node_bin, str(tsc_script), "--noEmit", "-p", str(tsconfig)]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
            timeout=60
        )
        passed = (proc.returncode == 0)
        output_lines = [line.strip() for line in (proc.stdout + proc.stderr).splitlines() if line.strip()]
        return {
            "name": "TypeScript Type-Check",
            "passed": passed,
            "returncode": proc.returncode,
            "output": output_lines[:50],
            "error": "" if passed else "TypeScript compilation errors detected."
        }
    except Exception as e:
        return {
            "name": "TypeScript Type-Check",
            "passed": False,
            "error": str(e)
        }

def check_vite_build(node_bin: str) -> dict:
    """Run Vite production build."""
    vite_script = FRONTEND_DIR / "node_modules" / "vite" / "bin" / "vite.js"
    
    if not vite_script.exists():
        return {
            "name": "Vite Production Build",
            "passed": False,
            "error": f"vite script not found at {vite_script}"
        }
        
    try:
        # Audit a fresh build without replacing a developer's existing dist/ tree.
        with tempfile.TemporaryDirectory(prefix="qore-frontend-audit-") as build_dir:
            proc = subprocess.run(
                [node_bin, str(vite_script), "build", str(FRONTEND_DIR), "--outDir", build_dir],
                cwd=str(FRONTEND_DIR),
                capture_output=True,
                text=True,
                timeout=120
            )
        passed = (proc.returncode == 0)
        output_lines = [line.strip() for line in (proc.stdout + proc.stderr).splitlines() if line.strip()]
        return {
            "name": "Vite Production Build",
            "passed": passed,
            "returncode": proc.returncode,
            "output_summary": output_lines[-15:] if output_lines else [],
            "error": "" if passed else "Vite build failed."
        }
    except Exception as e:
        return {
            "name": "Vite Production Build",
            "passed": False,
            "error": str(e)
        }

def check_client_secret_isolation() -> dict:
    """Verify no API keys or backend secrets are leaked into frontend files."""
    frontend_src = FRONTEND_DIR / "src"
    findings = []
    
    # Disallowed tokens in client files
    secret_patterns = [
        re.compile(r"AIzaSy[A-Za-z0-9_-]{33}"),
        re.compile(r"VITE_[A-Z_]*KEY"),
        re.compile(r"sk-[A-Za-z0-9]{32,}"),
        re.compile(r"bearer\s+[\w-]{30,}", re.IGNORECASE)
    ]
    
    for root, _, files in os.walk(frontend_src):
        for f in files:
            if f.endswith((".ts", ".tsx", ".js", ".jsx", ".html", ".css")):
                file_path = Path(root) / f
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    for pat in secret_patterns:
                        matches = pat.findall(content)
                        if matches:
                            findings.append({
                                "file": str(file_path.relative_to(WORKSPACE_ROOT)),
                                "matches": [m[:6] + "...[REDACTED]" for m in matches]
                            })
                except Exception as e:
                    findings.append({
                        "file": str(file_path.relative_to(WORKSPACE_ROOT)),
                        "error": str(e)
                    })
                    
    passed = len(findings) == 0
    return {
        "name": "Client Secret Isolation (Zero-Exposure)",
        "passed": passed,
        "violations": findings,
        "error": "" if passed else f"Found {len(findings)} secret exposure violations in frontend/src."
    }

def check_ui_structural_integrity() -> dict:
    """Check for common UI pitfalls: unbounded scroll areas, missing error boundaries, syntax sanity."""
    frontend_src = FRONTEND_DIR / "src"
    issues = []
    
    app_tsx = frontend_src / "App.tsx"
    if app_tsx.exists():
        content = app_tsx.read_text(encoding="utf-8", errors="ignore")
        if "ErrorBoundary" not in content and "componentDidCatch" not in content and "error" not in content.lower():
            issues.append("App.tsx lacks top-level error boundary or global error catching.")
            
    styles_css = frontend_src / "styles.css"
    if styles_css.exists():
        css_content = styles_css.read_text(encoding="utf-8", errors="ignore")
        has_scroll = any(k in css_content for k in ["overflow: auto", "overflow-y: auto", "overflow-x: auto", "overflow: scroll"])
        if not has_scroll:
            issues.append("styles.css lacks scroll container rules.")
            
    passed = len(issues) == 0
    return {
        "name": "UI Structural & Layout Integrity",
        "passed": passed,
        "issues": issues,
        "error": "" if passed else f"Found {len(issues)} structural suggestions."
    }

def check_contract_alignment() -> dict:
    """Verify that frontend API calls match endpoints declared in CONTRACT.md."""
    contract_file = WORKSPACE_ROOT / "CONTRACT.md"
    frontend_src = FRONTEND_DIR / "src"
    
    if not contract_file.exists():
        return {
            "name": "API Contract Alignment",
            "passed": False,
            "error": "CONTRACT.md not found"
        }
        
    contract_text = contract_file.read_text(encoding="utf-8")
    endpoints = re.findall(r"(?:GET|POST|PUT|DELETE)\s+`(/[^`]+)`", contract_text)
    
    # Collect frontend fetch / axios / api calls
    called_endpoints = set()
    for root, _, files in os.walk(frontend_src):
        for f in files:
            if f.endswith((".ts", ".tsx")):
                content = (Path(root) / f).read_text(encoding="utf-8", errors="ignore")
                matches = re.findall(r"['\"`](/api/[a-zA-Z0-9_\-/]+)['\"`]", content)
                called_endpoints.update(matches)
                
    unmatched = []
    for call in called_endpoints:
        # Strip query params or /api prefix for matching against contract
        route = call.replace("/api", "") if call.startswith("/api") else call
        # Check if route matches any pattern in endpoints
        matched = any(route == ep or ep.startswith(route) or route.startswith(ep.split("{")[0]) for ep in endpoints)
        if not matched:
            unmatched.append(call)
            
    passed = len(unmatched) == 0
    return {
        "name": "API Contract Alignment",
        "passed": passed,
        "contract_endpoints_count": len(endpoints),
        "frontend_endpoints_called": list(called_endpoints),
        "unmatched_routes": unmatched,
        "error": "" if passed else f"Detected calls to undocumented routes: {unmatched}"
    }

def run_all_checks() -> dict:
    """Run all frontend quality and resilience checks."""
    node_bin = find_node_executable()
    
    results = [
        check_typescript_compilation(node_bin),
        check_vite_build(node_bin),
        check_client_secret_isolation(),
        check_ui_structural_integrity(),
        check_contract_alignment()
    ]
    
    total_checks = len(results)
    passed_checks = sum(1 for r in results if r["passed"])
    status = "HEALTHY" if passed_checks == total_checks else "DEGRADED"
    
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "node_binary": node_bin,
        "checks": results
    }
    
    return summary

def generate_reports(summary: dict):
    """Write frontend health reports in evidence directory."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Write JSON
    REPORT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    
    # Write Markdown
    lines = [
        "# QORE Frontend Autonomous Health & Bug Audit Report",
        "",
        f"**Audit Timestamp**: `{summary['timestamp']}`  ",
        f"**Overall Health Status**: `{'✅ ' + summary['status'] if summary['status'] == 'HEALTHY' else '⚠️ ' + summary['status']}`  ",
        f"**Passed Checks**: `{summary['passed_checks']} / {summary['total_checks']}`  ",
        f"**Node Runtime**: `{summary['node_binary']}`  ",
        "",
        "---",
        "",
        "## Check Breakdown",
        ""
    ]
    
    for check in summary["checks"]:
        icon = "✅ PASS" if check["passed"] else "❌ FAIL"
        lines.append(f"### {icon}: {check['name']}")
        if not check["passed"]:
            lines.append(f"> **Error**: {check.get('error', 'Unknown failure')}")
        if "violations" in check and check["violations"]:
            lines.append(f"- Violations: `{json.dumps(check['violations'])}`")
        if "output_summary" in check and check["output_summary"]:
            lines.append("```text")
            lines.extend(check["output_summary"][-8:])
            lines.append("```")
        lines.append("")
        
    lines.append("---")
    lines.append("*Generated by QORE Autonomous Frontend Health Engine*")
    
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

def main():
    summary = run_all_checks()
    generate_reports(summary)
    print(f"Frontend Audit Finished: {summary['status']} ({summary['passed_checks']}/{summary['total_checks']} checks passed)")
    if summary["status"] != "HEALTHY":
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
