"""Build the standalone, searchable QORE documentation from first-party Markdown.

Only documentation and explicitly allowed image assets are copied. No application
data, environment files, compiled IDE bundle, or account information is read.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import stat
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / ("content" if (ROOT / "content").is_dir() else "docs")
EXCLUDED = {"FRONTEND_AGENT_GUIDELINES.md", "ENGINEERING_REPORT.md"}
GROUPS = {"guides": "Start here", "features": "Workspace features", "reference": "Technical reference",
          "operations": "Operate QORE", "quantum": "Quantum computing"}

CSS = r'''
:root{color-scheme:dark;--bg:#101821;--panel:#192530;--line:#b5cde522;--text:#edf4fc;--muted:#b0c2d5;--accent:#98c2e2;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:88px}body{margin:0;color:var(--text);background:radial-gradient(ellipse at 85% 0,#24445b65,transparent 55%),var(--bg);font-size:15.5px;line-height:1.8}button,input{font:inherit}a{color:#b6daf4;text-underline-offset:4px}a:focus-visible,button:focus-visible,input:focus-visible,summary:focus-visible{outline:2px solid #beddf4;outline-offset:4px}button{cursor:pointer;color:inherit}header{height:65px;position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:18px;padding:0 25px;background:#14202dde;border-bottom:1px solid var(--line);backdrop-filter:blur(24px)}.brand{display:flex;align-items:center;gap:12px;color:var(--text);text-decoration:none;letter-spacing:.1em;font-size:14px;font-weight:750}.brand img{width:29px;height:29px}.brand small{font-size:11px;color:var(--muted);letter-spacing:.16em}.icon-button{display:grid;place-items:center;width:35px;height:35px;border-radius:11px;background:#c7dff30a;border:1px solid var(--line);flex-shrink:0}.header-link{margin-left:auto;font-size:13px;text-decoration:none;white-space:nowrap}.search{position:relative;width:min(340px,35vw);margin-left:auto}.search input{width:100%;background:#0f1925;border:1px solid var(--line);border-radius:11px;padding:8px 13px;color:var(--text);font-size:13px}.search-results{position:absolute;top:46px;right:0;width:min(480px,88vw);max-height:65vh;overflow:auto;padding:9px;background:#1a2838fa;border:1px solid #afcce047;border-radius:16px;box-shadow:0 20px 70px #0009}.search-results:empty{display:none}.search-results a{display:block;padding:12px;text-decoration:none;border-radius:10px}.search-results a:hover{background:#b5d9ef12}.search-results strong{display:block;color:#f0f6ff;font-size:14px}.search-results span{display:block;font-size:12px;color:var(--muted);line-height:1.6}.shell{display:grid;grid-template-columns:282px minmax(0,1fr);transition:grid-template-columns .22s ease}.sidebar{position:sticky;top:65px;height:calc(100dvh - 65px);overflow:auto;padding:26px 15px 38px;border-right:1px solid var(--line);background:#121e29aa;min-width:0}.sidebar details{margin-bottom:14px}.sidebar summary{cursor:pointer;color:#cedceb;font-size:11px;letter-spacing:.13em;text-transform:uppercase;font-weight:750;padding:8px}.sidebar a{display:block;color:#b6c8da;text-decoration:none;font-size:12.5px;line-height:1.55;border-radius:9px;padding:8px 11px;margin:2px 0;overflow-wrap:anywhere}.sidebar a:hover,.sidebar a.active{background:#a4cbe514;color:#f1f8ff}.sidebar a.active{box-shadow:inset 2px 0 var(--accent)}.sidebar-title{color:#869eb6;font-size:11px;letter-spacing:.13em;margin:0 9px 18px}.main-shell{min-width:0;display:grid;grid-template-columns:minmax(0,940px) 190px;gap:48px;padding:50px 44px 80px;justify-content:center}.article{min-width:0;max-width:940px}.breadcrumb{color:#8facbf;font-size:11px;letter-spacing:.13em;text-transform:uppercase;font-weight:700}.article h1{font-size:clamp(32px,4.3vw,49px);letter-spacing:-.045em;line-height:1.16;font-weight:650;margin:16px 0 20px}.article h2{font-size:27px;line-height:1.3;letter-spacing:-.025em;margin:47px 0 18px;font-weight:630}.article h3{font-size:20px;line-height:1.4;letter-spacing:-.02em;margin:32px 0 13px;font-weight:650}.article h4{font-size:16px;margin:25px 0 10px}.article p,.article li{color:#c1cfde}.article p{margin:15px 0}.article strong{color:#edf5ff}.lead{font-size:17px;line-height:1.8;color:#b8cee2!important}.article li{margin:8px 0}.article blockquote{margin:25px 0;padding:12px 22px;background:#a4c8e20d;border-left:3px solid #91b8d5;border-radius:0 14px 14px 0}.article pre{position:relative;overflow:auto;max-width:100%;padding:22px;background:#0a131f;border:1px solid var(--line);border-radius:15px;font-size:12.5px;line-height:1.8;color:#bbd9ef}.article code{font-family:"Cascadia Code","SFMono-Regular",Consolas,monospace;font-size:.86em;background:#c6def00d;padding:2px 5px;border-radius:5px;overflow-wrap:anywhere}.article pre code{padding:0;background:transparent;font-size:inherit;overflow-wrap:normal}.article img{max-width:100%;height:auto;border-radius:16px}.table-wrap{overflow:auto;max-width:100%;border:1px solid var(--line);border-radius:14px;margin:24px 0}.article table{width:100%;border-collapse:collapse;font-size:13px}.article th,.article td{padding:12px 15px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;min-width:110px}.article th{background:#a0c6e00b;color:#e4effa}.article hr{border:0;border-top:1px solid var(--line);margin:40px 0}.toc{position:sticky;top:101px;height:fit-content;max-height:calc(100dvh - 125px);overflow:auto;font-size:11.5px;color:#a2b9cd;border-left:1px solid var(--line);padding-left:17px}.toc a{display:block;text-decoration:none;padding:5px 0;color:#a2b9cd;line-height:1.5}.toc a:hover{color:#eef6ff}.toc h2{font-size:10px;letter-spacing:.15em;margin:0 0 12px}.next-pages{display:flex;gap:15px;justify-content:space-between;border-top:1px solid var(--line);padding-top:26px;margin-top:48px}.next-pages a{max-width:47%;padding:13px 17px;border:1px solid var(--line);border-radius:13px;text-decoration:none;font-size:12px}.footer-note{color:#87a1ba;font-size:11px;margin-top:25px}.concept{padding:23px;margin:28px 0;border:1px solid #b7d6ee2a;border-radius:21px;background:linear-gradient(120deg,#8fbbdb15,#94a2cb0a);overflow:hidden}.concept small{font-size:10px;letter-spacing:.16em;color:#9dbed8;font-weight:750}.concept-track{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:18px 0}.concept-step{flex:1;min-width:0;text-align:center;padding:12px 6px;border:1px solid var(--line);border-radius:11px;background:#0e19248c;color:#bed4e7;font-size:11px;font-weight:650;animation:step-pulse 5s ease infinite;animation-delay:calc(var(--i)*.9s)}.concept-arrow{color:#86b4d4;animation:arrow-flow 2s ease infinite}.concept p{font-size:12px;line-height:1.7;margin:10px 0 0;color:#a9bfd2}.topic-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:28px 0}.topic-card{padding:22px;border:1px solid var(--line);border-radius:17px;background:#bbd5ef07;text-decoration:none;transition:background .2s,transform .2s}.topic-card:hover{background:#bbd5ef11;transform:translateY(-2px)}.topic-card strong{display:block;font-size:16px;margin-bottom:7px}.topic-card span{display:block;font-size:12px;color:#a6bfd4;line-height:1.7}.nav-collapsed .shell{grid-template-columns:0 minmax(0,1fr)}.nav-collapsed .sidebar{visibility:hidden;padding:0;opacity:0}.skip{position:fixed;top:-100px;left:20px;z-index:100;background:#263b50;padding:12px}.skip:focus{top:12px}.copy-code{float:right;position:sticky;top:0;right:0;margin:-8px -8px 6px 10px;padding:4px 9px;border:1px solid var(--line);border-radius:7px;background:#203044;font-size:10px}.docs-menu-backdrop{display:none}@keyframes step-pulse{0%,23%,100%{border-color:#b5cde522;box-shadow:none}10%{border-color:#aed6ef88;box-shadow:0 0 20px #8ebbd51a;color:#f1f8ff}}@keyframes arrow-flow{50%{transform:translateX(3px);opacity:.45}}@media(min-width:1700px){.main-shell{padding-top:65px;gap:65px}}@media(max-width:1250px){.toc{display:none}.main-shell{grid-template-columns:minmax(0,900px);padding:38px 32px 65px}}@media(max-width:900px){.shell{display:block}.sidebar{position:fixed;top:65px;left:0;bottom:0;width:282px;z-index:35;background:#172332f7;backdrop-filter:blur(22px);transform:translateX(-100%);transition:transform .2s}.nav-open .sidebar{transform:translateX(0)}.nav-open .docs-menu-backdrop{display:block;position:fixed;inset:65px 0 0;z-index:30;background:#0007;border:0}.main-shell{padding:35px 25px 60px}.search{width:min(330px,43vw)}header{padding:0 17px;gap:13px}.brand small{display:none}.header-link{font-size:12px;margin-left:0}.concept{padding:18px}.concept-track{gap:5px}.concept-step{font-size:10px}}@media(max-width:480px){body{font-size:15px}header{gap:10px;padding:0 12px}.brand{font-size:12px;gap:7px;letter-spacing:.08em}.brand img{width:24px;height:24px}.header-link{display:none}.search{margin-left:auto;width:42vw}.search input{font-size:12px;padding:8px}.main-shell{padding:30px 19px 55px}.article h1{font-size:34px}.article h2{font-size:24px}.topic-grid{grid-template-columns:1fr}.concept-arrow{display:none}.concept-track{display:grid;grid-template-columns:1fr 1fr}.article pre{padding:17px;font-size:11.5px}.next-pages{gap:10px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*:before,*:after{animation:none!important;transition:none!important}}
'''

JS = r'''
const root=document.documentElement, toggle=document.querySelector('[data-nav-toggle]'), sidebar=document.querySelector('.sidebar');
const mobile=matchMedia('(max-width:900px)');
function setNav(open){if(mobile.matches){root.classList.remove('nav-collapsed');root.classList.toggle('nav-open',open);toggle.setAttribute('aria-expanded',String(open));}else{root.classList.remove('nav-open');root.classList.toggle('nav-collapsed',!open);toggle.setAttribute('aria-expanded',String(open));try{localStorage.setItem('qore_docs_navigation',open?'open':'closed')}catch{}}}
function restoreNavigation(){root.classList.remove('nav-open','nav-collapsed');let open=!mobile.matches;try{if(!mobile.matches)open=localStorage.getItem('qore_docs_navigation')!=='closed'}catch{}setNav(open)}
restoreNavigation();mobile.addEventListener('change',restoreNavigation);
toggle.addEventListener('click',()=>setNav(mobile.matches?!root.classList.contains('nav-open'):root.classList.contains('nav-collapsed')));
document.querySelector('.docs-menu-backdrop').addEventListener('click',()=>setNav(false));
document.addEventListener('keydown',event=>{if(event.key==='Escape'){if(mobile.matches){setNav(false);toggle.focus();}document.querySelector('.search-results').replaceChildren();}if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();document.querySelector('#docs-search').focus()}});
const input=document.querySelector('#docs-search'), results=document.querySelector('.search-results');let pages;
input.addEventListener('input',async()=>{const query=input.value.trim().toLowerCase();results.replaceChildren();if(query.length<2)return;try{pages??=await fetch('search-index.json').then(r=>r.json());if(input.value.trim().toLowerCase()!==query)return;const matches=pages.filter(page=>(page.title+' '+page.text).toLowerCase().includes(query)).slice(0,9);for(const page of matches){const link=document.createElement('a'),title=document.createElement('strong'),snippet=document.createElement('span');link.href=page.url;title.textContent=page.title;const at=page.text.toLowerCase().indexOf(query);snippet.textContent=page.text.slice(Math.max(0,at-50),Math.max(0,at-50)+155)+'…';link.append(title,snippet);results.append(link)}if(!matches.length){const note=document.createElement('p');note.textContent='No matching page. Try a feature or API name.';results.append(note)}}catch{const note=document.createElement('p');note.textContent='Search is unavailable. Use the topic navigation.';results.append(note)}});
document.addEventListener('click',event=>{if(!event.target.closest('.search'))results.replaceChildren()});
for(const pre of document.querySelectorAll('pre')){const button=document.createElement('button');button.className='copy-code';button.type='button';button.textContent='Copy';button.setAttribute('aria-label','Copy code example');button.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(pre.querySelector('code').textContent);button.textContent='Copied';setTimeout(()=>button.textContent='Copy',1400)}catch{button.textContent='Select text to copy'}});pre.prepend(button)}
'''


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "section"


def plain(value):
    return re.sub(r"\s+", " ", re.sub(r"[`#*\[\]<>]", "", value)).strip()


def build(destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    # Remove only generated public artifacts so deleted/renamed source pages do
    # not remain live. Repository metadata and hand-authored build files stay.
    for generated in destination.glob("*.html"):
        generated.unlink()
    for name in ("search-index.json", "sitemap.xml", "robots.txt"):
        target = destination / name
        if target.exists():
            target.unlink()
    for name in ("assets", "content"):
        target = destination / name
        if target.is_dir():
            def clear_readonly(operation, path, _error):
                Path(path).chmod(stat.S_IWRITE)
                operation(path)
            shutil.rmtree(target, onexc=clear_readonly)
    assets = destination / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "site.css").write_text(CSS, encoding="utf-8")
    (assets / "site.js").write_text(JS, encoding="utf-8")
    logo = ROOT / "frontend/public/favicon.svg"
    if logo.exists(): shutil.copyfile(logo, assets / "qore.svg")
    for source in DOCS.rglob("*"):
        if source.is_file() and source.suffix.lower() in {".svg", ".png", ".gif", ".webp"}:
            relative = source.relative_to(DOCS)
            target = destination / relative if relative.parts[0] == "assets" else assets / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    pages = []
    for source in sorted(DOCS.rglob("*.md")):
        if source.name in EXCLUDED:
            continue
        text = source.read_text(encoding="utf-8")
        archived_source = destination / "content" / source.relative_to(DOCS)
        archived_source.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != archived_source.resolve(): shutil.copyfile(source, archived_source)
        title = re.search(r"^#\s+(.+)", text, re.M)
        title = title.group(1).strip() if title else source.stem.replace("-", " ").replace("_", " ").title()
        relative = source.relative_to(DOCS)
        url = slug(str(relative.with_suffix("")).replace("\\", "-")) + ".html"
        group = GROUPS.get(relative.parts[0], "Project reference")
        paragraphs = [plain(p) for p in text.split("\n\n") if p.strip() and not p.lstrip().startswith(("#", "```", "-", "|"))]
        description = next((p[:180] for p in paragraphs if len(p) > 45), title + " in the QORE development workspace.")
        pages.append({"source": source, "title": title, "text": text, "url": url, "group": group, "description": description})
    md = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])
    lookup = {str(page["source"].resolve()): page["url"] for page in pages}

    def render(page, text):
        headings, counts = [], {}
        tokens = md.parse(re.sub(r"^#\s+[^\n]+\n?", "", text, count=1))
        for index, token in enumerate(tokens):
            if token.type == "heading_open":
                label = tokens[index + 1].content
                key = slug(label); counts[key] = counts.get(key, 0) + 1
                ident = key + (f"-{counts[key]}" if counts[key] > 1 else "")
                token.attrSet("id", ident)
                if token.tag in {"h2", "h3"}: headings.append((label, ident))
            if token.type == "inline":
                for child in token.children or []:
                    attribute = "src" if child.type == "image" else "href" if child.type == "link_open" else None
                    if not attribute: continue
                    value = child.attrGet(attribute) or ""
                    if value.startswith(("http:", "https:", "mailto:", "#")): continue
                    path, _, fragment = value.partition("#")
                    resolved = (page["source"].parent / path).resolve()
                    if str(resolved) in lookup: child.attrSet(attribute, lookup[str(resolved)] + ("#" + fragment if fragment else ""))
                    elif resolved.is_relative_to(DOCS) and resolved.suffix.lower() in {".svg", ".gif", ".png", ".webp"}:
                        relative = resolved.relative_to(DOCS)
                        child.attrSet(attribute, relative.as_posix() if relative.parts[0] == "assets" else "assets/" + relative.as_posix())
                    elif resolved.is_relative_to(ROOT):
                        child.attrSet(attribute, "https://github.com/ganeshkumarchalla/Qore/blob/main/" + resolved.relative_to(ROOT).as_posix())
        content = md.renderer.render(tokens, md.options, {})
        content = content.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
        return content, headings

    def document(title, group, description, content, current="index.html", headings=(), previous=None, following=None):
        nav = '<p class="sidebar-title">QORE DOCUMENTATION</p><a href="index.html"' + (' class="active"' if current == "index.html" else '') + '>Overview</a>'
        for name in list(GROUPS.values()) + ["Project reference"]:
            section = [p for p in pages if p["group"] == name]
            if not section: continue
            nav += '<details open><summary>' + html.escape(name) + '</summary>' + ''.join('<a href="' + p['url'] + '"' + (' class="active" aria-current="page"' if current == p['url'] else '') + '>' + html.escape(p['title']) + '</a>' for p in section) + '</details>'
        toc = '<aside class="toc" aria-label="On this page"><h2>ON THIS PAGE</h2>' + ''.join('<a href="#' + ident + '">' + html.escape(label) + '</a>' for label, ident in headings) + '</aside>'
        steps = ['Write', 'Save', 'Explore', 'Verify', 'Keep evidence']
        if any(word in title.lower() for word in ('file', 'trash', 'workspace', 'explorer')): steps = ['Create', 'Save to database', 'Delete', '48-hour Trash', 'Restore']
        elif any(word in title.lower() for word in ('auth', 'identity')): steps = ['Open workspace', 'Receive browser scope', 'Create source', 'Run safely', 'Keep evidence']
        elif any(word in title.lower() for word in ('forge', 'transpil', 'optim')): steps = ['Inspect source', 'Compile candidate', 'Check equivalence', 'Review evidence', 'Apply explicitly']
        elif any(word in title.lower() for word in ('ledger', 'snapshot', 'experiment')): steps = ['Run circuit', 'Capture source', 'Freeze settings', 'Keep evidence', 'Restore context']
        elif any(word in title.lower() for word in ('lab', 'bloch', 'measurement', 'noise', 'probabil')): steps = ['Prepare state', 'Evolve amplitudes', 'Sample shots', 'Compare evidence', 'Inspect limitations']
        elif group == 'Quantum computing': steps = ['State', 'Phase', 'Gates', 'Interference', 'Measurement']
        diagram = '<div class="concept"><small>CONCEPT AT A GLANCE</small><div class="concept-track">' + '<span class="concept-arrow" aria-hidden="true">→</span>'.join('<span class="concept-step" style="--i:' + str(i) + '">' + value + '</span>' for i, value in enumerate(steps)) + '</div><p>Conceptual workflow. Numerical evidence and save status come from your actual QORE session.</p></div>'
        pager = '<div class="next-pages">' + ('<a href="' + previous['url'] + '">← ' + html.escape(previous['title']) + '</a>' if previous else '<span></span>') + ('<a href="' + following['url'] + '">' + html.escape(following['title']) + ' →</a>' if following else '') + '</div>'
        return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#101821"><title>' + html.escape(title) + ' · QORE Documentation</title><meta name="description" content="' + html.escape(description, quote=True) + '"><link rel="canonical" href="https://qoredocs.vercel.app/' + current + '"><link rel="icon" href="assets/qore.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/site.css"><script src="assets/site.js" defer></script></head><body><a class="skip" href="#main">Skip to content</a><header><button class="icon-button" type="button" data-nav-toggle aria-label="Toggle documentation navigation" aria-controls="docs-sidebar" aria-expanded="true">☰</button><a class="brand" href="index.html"><img src="assets/qore.svg" alt="" width="29" height="29">QORE <small>DOCS</small></a><div class="search"><label for="docs-search" hidden>Search documentation</label><input id="docs-search" type="search" placeholder="Search the docs · Ctrl K" autocomplete="off"><div class="search-results" role="status"></div></div><a class="header-link" href="https://qore-bmh1.onrender.com/" rel="noopener">Open Studio ↗</a></header><button class="docs-menu-backdrop" type="button" aria-label="Close documentation navigation"></button><div class="shell"><nav class="sidebar" id="docs-sidebar" aria-label="Documentation topics">' + nav + '</nav><div class="main-shell"><main class="article" id="main"><span class="breadcrumb">' + html.escape(group) + '</span><h1>' + html.escape(title) + '</h1><p class="lead">' + html.escape(description) + '</p>' + diagram + content + pager + '<p class="footer-note">QORE reference · Bounded simulation, inspectable evidence, account-free browser workspace.</p></main>' + toc + '</div></div></body></html>'

    index = '<h2 id="start">Build a reliable quantum workflow</h2><p>Start immediately in an account-free browser workspace. Create your own files or choose the explicit three-qubit starter, explore the state in Lab, review a compiler candidate in Forge, and preserve immutable experiment evidence.</p><div class="topic-grid">'
    for page in pages:
        index += '<a class="topic-card" href="' + page['url'] + '"><strong>' + html.escape(page['title']) + '</strong><span>' + html.escape(page['description']) + '</span></a>'
    index += '</div><h2 id="scope">Understand the scope</h2><p>QORE supports a bounded circuit-building subset of Qiskit and OpenQASM 2, with explicit size and operation limits. It does not execute arbitrary Python or imply quantum-hardware access. Active files have no automatic expiry; deleted file content is recoverable for 48 hours.</p>'
    (destination / 'index.html').write_text(document('A clear guide to QORE', 'Product documentation', 'Learn the workspace, quantum concepts, supported syntax, data lifecycle, API, security model, deployment, and operating practices through dedicated reference pages.', index, headings=[('Start here', 'start'), ('Supported scope', 'scope')]), encoding='utf-8')
    for number, page in enumerate(pages):
        content, headings = render(page, page['text'])
        (destination / page['url']).write_text(document(page['title'], page['group'], page['description'], content, page['url'], headings,
            pages[number-1] if number else None, pages[number+1] if number+1 < len(pages) else None), encoding='utf-8')
    # Keep established incoming URLs useful while new topics have their own pages.
    aliases = {'getting-started.html': ('getting-started', 'quickstart'), 'quantum-lab.html': ('lab', 'simulation'),
        'simulation.html': ('simulation',), 'forge.html': ('forge',), 'ledger.html': ('ledger',),
        'architecture.html': ('architecture',), 'runtime.html': ('runtime', 'limits'), 'security.html': ('security',),
        'terminal.html': ('terminal',), 'visualizations.html': ('visual', 'bloch'), 'full-reference.html': ('api', 'reference')}
    for alias, terms in aliases.items():
        if any(p['url'] == alias for p in pages): continue
        target = next((p['url'] for term in terms for p in pages if term in p['url']), 'index.html')
        (destination / alias).write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex,follow"><meta http-equiv="refresh" content="0;url=' + target + '"><title>QORE Documentation</title></head><body><a href="' + target + '">Open the updated QORE reference</a></body></html>', encoding='utf-8')
    search = [{'title': p['title'], 'url': p['url'], 'text': plain(p['text'])} for p in pages]
    (destination / 'search-index.json').write_text(json.dumps(search, ensure_ascii=False), encoding='utf-8')
    urls = ['index.html'] + [page['url'] for page in pages]
    (destination / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join('<url><loc>https://qoredocs.vercel.app/' + url + '</loc></url>' for url in urls) + '</urlset>', encoding='utf-8')
    (destination / 'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: https://qoredocs.vercel.app/sitemap.xml\n', encoding='utf-8')
    print(json.dumps({'output': str(destination), 'pages': len(pages) + 1, 'searchable_topics': len(search)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Existing/new standalone documentation checkout or build directory')
    build(parser.parse_args().output.resolve())
