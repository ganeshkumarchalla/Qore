"""Refresh the small, attributed brand marks used in QORE documentation.

This script reads public brand files only. It never loads project configuration.
Run from the project root with the project Python environment.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

import httpx

HERE = Path(__file__).resolve().parent
LOGOS = HERE / "logos"
LOGOS.mkdir(parents=True, exist_ok=True)
records = []


def save(name, content, source, license_name, guidelines, color=None):
    path = LOGOS / name
    path.write_bytes(content)
    records.append({"file": name, "source": source, "license": license_name,
                    "brand_guidelines": guidelines, "sha256": hashlib.sha256(content).hexdigest(),
                    "display_color": color, "retrieved": "2026-10-25"})


with httpx.Client(follow_redirects=True, timeout=45) as client:
    def get(url):
        response = client.get(url)
        response.raise_for_status()
        return response.content

    archive_url = "https://cdn.openai.com/brand/OpenAI-Logos-2025.zip"
    archive = zipfile.ZipFile(io.BytesIO(get(archive_url)))
    blossom = next(name for name in archive.namelist()
                   if name.endswith("/OpenAI-white-monoblossom.svg") and not name.startswith("__MACOSX"))
    save("openai.svg", archive.read(blossom), archive_url,
         "OpenAI trademark; supplied official brand asset", "https://openai.com/brand/")
    antigravity = "https://antigravity.google/assets/image/brand/antigravity-icon__full-color.svg"
    save("antigravity.svg", get(antigravity), antigravity,
         "Google trademark; supplied official press asset", "https://antigravity.google/press")
    for slug, color in (("canva", "00C4CC"), ("figma", "F24E1E"), ("supabase", "3FCF8E"),
                        ("github", "FFFFFF"), ("render", "FFFFFF"), ("docker", "2496ED")):
        url = f"https://raw.githubusercontent.com/simple-icons/simple-icons/13.21.0/icons/{slug}.svg"
        raw = get(url)
        content = raw.decode("utf-8").replace("<svg ", f'<svg fill="#{color}" ', 1).encode("utf-8")
        save(slug + ".svg", content, url, "CC0-1.0 (Simple Icons); underlying trademarks retained",
             "https://github.com/simple-icons/simple-icons/blob/develop/DISCLAIMER.md", color)
    powershell = "https://raw.githubusercontent.com/PowerShell/PowerShell/master/assets/powershell_128.svg"
    save("powershell.svg", get(powershell), powershell,
         "MIT (PowerShell repository); Microsoft trademark retained", "https://github.com/PowerShell/PowerShell/blob/master/LICENSE.txt")
    save("simple-icons-LICENSE.txt", get("https://raw.githubusercontent.com/simple-icons/simple-icons/develop/LICENSE.md"),
         "https://github.com/simple-icons/simple-icons/blob/develop/LICENSE.md", "CC0-1.0", "https://simpleicons.org/")

(LOGOS / "sources.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
print(f"Saved {len(records) - 1} attributed brand marks and license metadata.")
