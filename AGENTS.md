# QORE Workspace Security & Agent Guidelines

This project implements strict multi-agent security and privacy protocols. All agents, automated workflows, and developer tools operating within `c:\Users\ganes\OneDrive\QORE` must adhere to these policies.

---

## 1. Zero-Exposure Secret Policy
* **Never Output Secrets**: Never print, log, return, or include contents of `.env`, API keys (`GEMINI_API_KEY`, etc.), bearer tokens, private keys, or passwords in chat responses, error messages, logs, or reports.
* **Redaction Mandatory**: Any tool output or report that touches secrets must display redacted masks (e.g. `AIzaSy...[REDACTED]`).
* **Client/Frontend Isolation**: Never place backend API keys or secrets in `frontend/` files or prefix them with `VITE_`. In Vite, `VITE_*` environment variables are baked into static client bundles sent to browsers. All AI and sensitive requests must route through the backend (`backend/qore/`).

## 2. File Safety & Version Control
* **Ignore Protection**: Ensure `.env`, `.env.*`, certificates (`*.pem`, `*.key`), databases (`*.db`, `*.sqlite*`), and credential files are strictly listed in `.gitignore`.
* **No Accidental Staging**: Before committing or sharing files, verify untracked sensitive files are not staged or exposed.
* **Temporary & Backup Files**: Clean up and ignore editor swap files (`*.swp`), backups (`*.bak`), and system metadata (`.DS_Store`, `Thumbs.db`).

## 3. IDE & Environment Hardening
* **Workspace Trust**: Maintain active workspace trust (`security.workspace.trust.enabled: true`) in `.vscode/settings.json`.
* **Search & Index Exclusion**: Sensitive files (`.env*`, `.venv/`, credentials) must be excluded from IDE file watchers and search indexes.
* **Telemetry Disabled**: Ensure editor telemetry is disabled to prevent accidental diagnostic data transmission.

## 4. Multi-Agent Automated Security Auditing
* Run the security audit engine at `scripts/security_checker.py` using the project's Python virtual environment:
  ```powershell
  & "C:\Users\ganes\OneDrive\QORE\.venv\Scripts\python.exe" scripts/security_checker.py --check
  ```
* Automated audit reports are generated under `evidence/security_report.md` and `evidence/security_report.json`.

## 5. Frontend Quality, UI Resilience & Multi-Agent Guidelines
* All agents and subagents modifying UI, styles, or frontend code must strictly adhere to `docs/FRONTEND_AGENT_GUIDELINES.md`.
* Run the frontend health audit engine using the project's Python virtual environment:
  ```powershell
  & "C:\Users\ganes\OneDrive\QORE\.venv\Scripts\python.exe" scripts/frontend_auditor.py
  ```
* Automated frontend health reports are generated under `evidence/frontend_health_report.md` and `evidence/frontend_health_report.json`.
* Subagents must consult the Frontend Autonomous Agent's standards before modifying components, state structures, or API contracts.

