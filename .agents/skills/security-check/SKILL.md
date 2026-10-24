---
name: security-check
description: Run multi-agent security audit on QORE project files, detect secret leakage, verify .gitignore, audit IDE settings, and ensure environment safety.
---

# QORE Multi-Agent Security Audit Skill

Use this skill to audit and harden the security of the QORE workspace, ensuring no sensitive credentials, API keys, private keys, or environment files are exposed to external users or repositories.

## Workflow

1. Execute the multi-agent security scanner:
   ```powershell
   & "C:\Users\ganes\OneDrive\QORE\.venv\Scripts\python.exe" "C:\Users\ganes\OneDrive\QORE\scripts\security_checker.py" --check
   ```

2. Review the generated audit reports:
   - Markdown summary: [security_report.md](file:///C:/Users/ganes/OneDrive/QORE/evidence/security_report.md)
   - Structured JSON: `evidence/security_report.json`

3. If security deficiencies are found, apply automated hardening fixes:
   ```powershell
   & "C:\Users\ganes\OneDrive\QORE\.venv\Scripts\python.exe" "C:\Users\ganes\OneDrive\QORE\scripts\security_checker.py" --fix
   ```

4. Verify that:
   - `.env` is never committed or exposed in frontend bundles.
   - All `VITE_*` variables remain free of server-side secrets.
   - `.gitignore` retains exclusion of all `.env*`, database, and certificate files.
