"""Build QORE Web Desktop executables and Windows installer package."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_SRC = ROOT / "desktop"
OUT_DIR = ROOT / "dist" / "desktop"
CSC_CANDIDATES = [
    Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
    Path(r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"),
]


def find_csc() -> Path:
    for candidate in CSC_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not find .NET Framework csc.exe compiler on this Windows host.")


def find_node() -> str:
    found = shutil.which("node")
    if found:
        return found
    for pattern in (
        Path(r"C:\Program Files\nodejs\node.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI",
    ):
        if pattern.is_file():
            return str(pattern)
        if pattern.is_dir():
            matches = sorted(pattern.rglob("node.exe"))
            if matches:
                return str(matches[-1])
    raise FileNotFoundError("Could not locate node.exe to build frontend/dist.")


def build_frontend() -> None:
    node_bin = find_node()
    vite_js = ROOT / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    if not vite_js.exists():
        raise FileNotFoundError(f"Vite binary missing at {vite_js}")
    subprocess.run([node_bin, str(vite_js), "build"], cwd=ROOT / "frontend", check=True)


def ensure_ai_model() -> None:
    model_path = ROOT / "backend" / "qore" / "qore_ai_model.joblib"
    if not model_path.exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "train_qore_ai.py")], cwd=ROOT, check=True)


def build_bundle_zip(desktop_exe: Path, setup_exe: Path, zip_path: Path) -> None:
    skip_dirs = {"__pycache__", ".pytest_cache", "tests"}
    readme_txt = (
        "QORE Desktop for Windows\r\n"
        "========================\r\n\r\n"
        "1. Extract all files from this archive.\r\n"
        "2. Double-click QORE-Setup.exe to run the interactive installation wizard.\r\n"
        "   (Or run: QORE-Setup.exe /SILENT /DIR=\"%LOCALAPPDATA%\\Programs\\QORE\")\r\n"
        "3. Launch QORE Desktop from the Desktop shortcut or QORE-Desktop.exe.\r\n"
    )
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(setup_exe, "QORE-Setup.exe")
        zf.write(desktop_exe, "QORE-Desktop.exe")
        zf.writestr("README-INSTALL.txt", readme_txt)
        for top_file in ("pyproject.toml", "requirements.txt"):
            fpath = ROOT / top_file
            if fpath.is_file():
                zf.write(fpath, top_file)
        for folder in (ROOT / "backend", ROOT / "frontend" / "dist"):
            for root, dirs, files in os.walk(folder):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                for fname in files:
                    if fname.endswith(".pyc"):
                        continue
                    full = Path(root) / fname
                    rel = full.relative_to(ROOT).as_posix()
                    zf.write(full, rel)


def compile_exe(csc: Path, source: Path, output_exe: Path) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(csc),
        "/nologo",
        "/target:winexe",
        "/optimize+",
        f"/out:{output_exe}",
        "/reference:System.dll",
        "/reference:System.Drawing.dll",
        "/reference:System.Windows.Forms.dll",
        str(source),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> dict[str, object]:
    ensure_ai_model()
    build_frontend()
    csc = find_csc()

    desktop_exe = OUT_DIR / "QORE-Desktop.exe"
    setup_exe = OUT_DIR / "QORE-Setup.exe"
    bundle_zip = OUT_DIR / "QORE-Windows-Desktop.zip"

    compile_exe(csc, DESKTOP_SRC / "QoreDesktop.cs", desktop_exe)
    compile_exe(csc, DESKTOP_SRC / "QoreInstaller.cs", setup_exe)
    build_bundle_zip(desktop_exe, setup_exe, bundle_zip)

    summary = {
        "status": "built",
        "csc": str(csc),
        "desktop_exe": str(desktop_exe),
        "desktop_exe_bytes": desktop_exe.stat().st_size,
        "setup_exe": str(setup_exe),
        "setup_exe_bytes": setup_exe.stat().st_size,
        "bundle_zip": str(bundle_zip),
        "bundle_zip_bytes": bundle_zip.stat().st_size,
        "bundle_zip_sha256": hashlib.sha256(bundle_zip.read_bytes()).hexdigest(),
        "ai_model_present": (ROOT / "backend" / "qore" / "qore_ai_model.joblib").exists(),
        "frontend_dist_present": (ROOT / "frontend" / "dist" / "index.html").exists(),
    }
    (OUT_DIR / "installer-manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
