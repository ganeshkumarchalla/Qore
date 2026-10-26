"""Rebuild QORE's GitHub-compatible animated GIFs and web SVG illustrations.

Requires Pillow; no service credentials, user projects, or network access.
All scene values are illustrative, not captured execution results.
"""
from __future__ import annotations

import html
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageChops

HERE = Path(__file__).resolve().parent
OUT = HERE / "animations"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1200, 450
INK = "#eef2f6"
MUTED = "#a9b5c3"
BLUE = "#86b7df"
GREEN = "#8bceba"
LINE = "#364655"
CARD = "#1a2733"


def font(size, bold=False, mono=False):
    names = (["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"] if mono else
             ["C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    return ImageFont.truetype(next(name for name in names if Path(name).exists()), size)


def background(height=H):
    image = Image.new("RGB", (W, height))
    pixels = image.load()
    for y in range(height):
        for x in range(W):
            light = max(0, 1 - math.hypot((x - 930) / 1000, (y - 40) / 520))
            pixels[x, y] = (int(15 + 10 * light + 2 * y / height), int(23 + 15 * light), int(32 + 21 * light))
    return image


BASE = background()


class Canvas:
    def __init__(self, height=H):
        self.image = BASE.copy() if height == H else background(height)
        self.draw = ImageDraw.Draw(self.image)
        self.svg = []
        self.height = height

    def box(self, xy, fill=CARD, outline=LINE, radius=16, width=1):
        self.draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
        x, y, right, bottom = xy
        self.svg.append(f'<rect x="{x}" y="{y}" width="{right-x}" height="{bottom-y}" rx="{radius}" fill="{fill}" stroke="{outline}" stroke-width="{width}"/>')

    def line(self, points, fill=LINE, width=2):
        self.draw.line(points, fill=fill, width=width)
        self.svg.append('<polyline points="' + ' '.join(f'{x:.2f},{y:.2f}' for x, y in points) + f'" fill="none" stroke="{fill}" stroke-width="{width}" stroke-linecap="round"/>')

    def ellipse(self, xy, fill=None, outline=LINE, width=2):
        self.draw.ellipse(xy, fill=fill, outline=outline, width=width)
        x, y, r, b = xy
        self.svg.append(f'<ellipse cx="{(x+r)/2}" cy="{(y+b)/2}" rx="{(r-x)/2}" ry="{(b-y)/2}" fill="{fill or "none"}" stroke="{outline}" stroke-width="{width}"/>')

    def text(self, xy, value, size=20, color=INK, bold=False, mono=False):
        self.draw.text(xy, value, font=font(size, bold, mono), fill=color)
        x, y = xy
        self.svg.append(f'<text x="{x}" y="{y+size*.94}" font-size="{size}" fill="{color}" font-family="{ "Consolas,monospace" if mono else "Segoe UI,Arial,sans-serif"}" font-weight="{650 if bold else 450}">{html.escape(value)}</text>')

    def finish_svg(self, name):
        motion = '<circle r="4" fill="#a8d2f2"><animateMotion dur="5s" repeatCount="indefinite" path="M 37 420 L 1163 420 L 37 420"/></circle>'
        value = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{self.height}" viewBox="0 0 {W} {self.height}" role="img" aria-label="QORE {html.escape(name)} conceptual illustration"><defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#111923"/><stop offset=".6" stop-color="#1b2b3c"/><stop offset="1" stop-color="#101821"/></linearGradient></defs><rect width="1200" height="{self.height}" rx="24" fill="url(#bg)"/>' + ''.join(self.svg) + motion + '</svg>'
        (OUT / f"{name}.svg").write_text(value, encoding="utf-8")


def title(c, chapter, heading, detail):
    c.text((38, 27), "QORE  /  " + chapter.upper(), 15, BLUE, True)
    c.text((36, 56), heading, 32, bold=True)
    c.text((38, 105), detail, 19, MUTED)
    c.line([(37, 420), (1163, 420)], LINE, 1)
    c.text((38, 429), "PRODUCT CONCEPT  ·  ILLUSTRATIVE VALUES", 10, MUTED, True)


def chip(c, x, y, text, color=GREEN):
    width = int(c.draw.textlength(text, font=font(15, True))) + 28
    c.box((x, y, x + width, y + 30), "#21343b", "#405953", 15)
    c.text((x + 14, y + 4), text, 15, color, True)


def studio(t):
    c = Canvas(); title(c, "01 · Studio", "A clear space for your next circuit.", "An empty workspace. Your files. A precise editor.")
    c.box((38, 151, 1162, 401)); c.box((51, 164, 257, 389), "#17222d", "#2e3c4b", 10)
    c.text((68, 177), "EXPLORER", 14, MUTED, True)
    for i, value in enumerate(("▾  research", "    ghz.py", "    notes.md")):
        c.text((68, 215 + 36 * i), value, 18, BLUE if i == 1 else INK, i == 1)
    rows = ["from qiskit import QuantumCircuit", "qc = QuantumCircuit(3, 3)", "qc.h(0)", "qc.cx(0, 1)", "qc.cx(1, 2)", "qc.measure([0, 1, 2], [0, 1, 2])"]
    active = int(t * len(rows)) % len(rows)
    c.box((275, 182 + active * 32, 1139, 211 + active * 32), "#263b4e", "#263b4e", 6)
    for i, value in enumerate(rows):
        c.text((290, 185 + i * 32), str(i + 1), 17, MUTED, mono=True)
        c.text((329, 185 + i * 32), value, 20, BLUE if i == 0 else INK, mono=True)
    return c


def lab(t):
    c = Canvas(); title(c, "02 · Quantum Lab", "Look inside the state.", "Measured counts, ideal probabilities, matrices, and interactive 3D qubits.")
    c.box((38, 153, 640, 400)); c.text((61, 171), "IDEAL + SAMPLED DISTRIBUTION", 14, MUTED, True)
    for i, label in enumerate(("000", "001", "010", "011", "100", "101", "110", "111")):
        height = (115 + 8 * math.sin(t * 2 * math.pi)) if i in (0, 7) else 4
        x = 76 + i * 68
        c.box((x, 345 - height, x + 29, 345), "#86b7df", "#86b7df", 5)
        c.line([(x + 35, 345), (x + 35, 225 if i in (0, 7) else 342)], GREEN, 6)
        c.text((x - 2, 358), label, 15, MUTED, mono=True)
    c.box((663, 153, 1162, 400))
    cx, cy, r = 901, 280, 98
    c.ellipse((cx-r, cy-r, cx+r, cy+r), outline=BLUE, width=2)
    c.ellipse((cx-r, cy-30, cx+r, cy+30), outline="#597b98")
    c.ellipse((cx-35, cy-r, cx+35, cy+r), outline="#597b98")
    c.line([(cx-r-26, cy), (cx+r+28, cy)], "#597b98")
    c.line([(cx, cy-r-15), (cx, cy+r+16)], "#597b98")
    theta = t*2*math.pi; x, y = cx+63*math.cos(theta), cy-70*math.sin(theta)
    c.line([(cx, cy), (x, y)], GREEN, 4); c.ellipse((x-7,y-7,x+7,y+7), GREEN, GREEN)
    c.text((cx+119,cy-8), "x", 16, MUTED); c.text((cx-5,cy-r-35), "z", 16, MUTED)
    return c


def forge(t):
    c = Canvas(); title(c, "03 · Forge", "Review a transformation with evidence.", "Compare resources. Inspect the candidate. Check the recorded equivalence scope.")
    for x, label, gates, depth in ((38,"ORIGINAL",8,6),(444,"CANDIDATE",4,3)):
        c.box((x, 160, x+386, 397)); c.text((x+23,180),label,15,MUTED,True)
        c.text((x+23,219),str(gates),56,bold=True); c.text((x+95,255),"gates",19,MUTED)
        c.text((x+23,298),f"Depth {depth}",22,BLUE,True)
        c.line([(x+24,360),(x+350,360)],LINE,7)
        c.line([(x+24,360),(x+24+int(306*(1-t)),360)],BLUE,7)
    c.box((850,160,1162,397)); c.text((875,182),"VERIFICATION",15,MUTED,True)
    chip(c,874,228,"Validated · ≤6 qubits")
    c.text((875,285),"Operator + mapping",19,bold=True)
    c.text((875,321),"Human approval to apply",16,MUTED)
    c.text((875,350),"Tolerance: 10⁻⁹",18,BLUE,True)
    return c


def ledger(t):
    c=Canvas(); title(c,"04 · Research Ledger","Keep the evidence behind a result.","Source, settings, versions, and output stay attached to an immutable snapshot.")
    labels=("SOURCE + HASH","CONFIGURATION","EXECUTION RESULT")
    details=(("Original circuit","Content identity"),("Shots · seed · method","Dependency versions"),("Counts · matrices","Validation evidence"))
    for i,(label,lines) in enumerate(zip(labels,details)):
        x=38+i*380; active=int(t*3)%3==i
        c.box((x,165,x+363,397),"#203142" if active else CARD,BLUE if active else LINE,18,2)
        c.text((x+24,187),f"0{i+1}",16,BLUE,True); c.text((x+24,226),label,20,bold=True)
        for j,line in enumerate(lines): c.text((x+24,275+j*33),line,19,MUTED)
        chip(c,x+24,342,"Snapshot preserved")
    return c


def assistant(t):
    c=Canvas(); title(c,"05 · Assistant","Ask beside your work.","A dedicated secondary sidebar, grounded in the active source and attached results.")
    c.box((38,158,747,398)); c.text((64,181),"ACTIVE CIRCUIT",15,MUTED,True)
    for i,line in enumerate(("qc.h(0)","qc.cx(0, 1)","qc.measure([0, 1], [0, 1])")):
        c.text((66,230+i*42),line,25,BLUE if i==0 else INK,mono=True)
    c.box((766,158,1162,398),"#203141", "#536a81")
    c.text((791,181),"QORE INTELLIGENCE",15,BLUE,True)
    c.text((791,224),"Why are outcomes correlated?",20,bold=True)
    c.text((791,269),"Read the circuit and evidence.",18,MUTED)
    c.text((791,302),"Propose. Inspect. Decide.",18,INK,True)
    for i in range(3):
        y=361-4*math.sin(2*math.pi*t+i)
        c.ellipse((795+i*20,y-4,803+i*20,y+4),BLUE,BLUE)
    return c


def workspace(t):
    c=Canvas(); title(c,"06 · Private Workspace","Save confidently. Recover deliberately.","Account-owned files persist across refresh. Deleted files have 48 hours in Trash.")
    c.box((38,158,598,398)); c.text((64,180),"YOUR DATABASE WORKSPACE",15,MUTED,True)
    for i,name in enumerate(("research /", "   circuit.py", "   experiment.qasm")):
        c.text((69,226+i*42),name,24,INK,i==1,mono=True)
    chip(c,351,223,"Saved",GREEN)
    c.box((620,158,1162,398)); c.text((645,180),"TRASH + UNDO",15,MUTED,True)
    c.text((646,226),"Deleted source",24,bold=True); chip(c,929,224,"48 hours")
    c.text((646,279),"Restore the last deleted file or folder.",20,MUTED)
    width=375+20*math.sin(2*math.pi*t)
    c.line([(648,342),(648+width,342)],BLUE,9)
    c.text((646,362),"Saved files have no automatic expiry.",17,GREEN,True)
    return c


def operations(t):
    c=Canvas(); title(c,"07 · Quality + Operations","A reviewable route to release.","Browser scopes, durable records, bounded workers, and repeatable engineering checks.")
    items=(("IDENTITY","Opaque browser boundary"),("DATA","Workspace isolation"),("RUNTIME","Limits + worker timeout"),("QUALITY","Tests + secret scanning"))
    for i,(label,detail) in enumerate(items):
        x=38+i*286; active=int(t*4)%4==i
        c.box((x,166,x+267,396),"#203142" if active else CARD,BLUE if active else LINE)
        c.ellipse((x+25,193,x+64,232),"#28454a","#4f8278")
        c.line([(x+36,211),(x+44,219),(x+56,204)],GREEN,3)
        c.text((x+25,260),label,18,BLUE,True)
        words=detail.split(" + ")
        for j,word in enumerate(words): c.text((x+25,301+j*30),word,18,INK,True)
    return c


def workflow(t):
    c=Canvas(); title(c,"The workflow","From a circuit to inspectable evidence.","One source identity connects the workbench, simulator, compiler, and research record.")
    names=("AUTHOR","COMPILE","SIMULATE","INSPECT","OPTIMIZE","VERIFY","PRESERVE")
    subtitles=("Studio","QORE-IR","Qiskit Aer","Quantum Lab","Forge","Operator + map","Research Ledger")
    for i,name in enumerate(names):
        x=38+i*162; active=int(t*7)%7==i
        c.box((x,192,x+150,339),"#284058" if active else CARD,BLUE if active else LINE,16,2)
        c.text((x+15,208),f"0{i+1}",15,BLUE,True)
        c.text((x+15,245),name,17,bold=True)
        c.text((x+15,286),subtitles[i],13,MUTED,True)
        if i<6: c.line([(x+151,265),(x+162,265)],BLUE,3)
    c.text((39,372),"Browser scope  ·  Persistent files  ·  48-hour Trash  ·  Optional assistant",20,MUTED)
    return c


def build_surface(t):
    c=Canvas(); title(c,"Build surface","The tools behind QORE.","Design, engineering, data, and delivery tools. Their marks identify their owners.")
    brands=(("openai","ChatGPT","Engineering"),("antigravity","Antigravity","Engineering"),("canva","Canva","Design"),("figma","Figma","Design"),("supabase","Supabase","Auth + database"),("github","GitHub","Source + CI"),("render","Render","Hosting"),("docker","Docker","Container"),("powershell","PowerShell","Developer tools"),("openai","Codex Security","Code review"))
    span=218*len(brands); shift=int(t*span)
    for repeat in (-1,0,1):
        for i,(logo,name,purpose) in enumerate(brands):
            x=38+i*218+shift+repeat*span
            if x>W or x+201<0: continue
            c.box((x,169,x+201,392),"#1c2a38",LINE,18)
            mark=Image.open(HERE/"logos"/(logo+".png")).convert("RGBA"); mark.thumbnail((85,85),Image.Resampling.LANCZOS)
            c.image.paste(mark,(int(x+100-mark.width/2),185),mark)
            c.text((x+17,289),name,20,bold=True)
            c.text((x+17,330),purpose,16,MUTED)
    return c


def export(name, painter, frames=48, duration=110):
    images=[]
    for frame in range(frames):
        c=painter(frame/frames)
        if frame==0:
            c.image.save(OUT/(name+"-poster.png"))
            if name!="build-surface": c.finish_svg(name)
        images.append(c.image.quantize(colors=112,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE))
    images[0].save(OUT/(name+".gif"),save_all=True,append_images=images[1:],duration=duration,loop=0,optimize=True,disposal=2)
    check=Image.open(OUT/(name+".gif")); unique=set()
    for frame in range(check.n_frames):
        check.seek(frame); unique.add(check.convert("RGB").tobytes())
    return {"name":name,"frames":check.n_frames,"unique_frames":len(unique),"duration_ms":frames*duration,"bytes":(OUT/(name+".gif")).stat().st_size}


if __name__=="__main__":
    report=[export(name,fn,80 if name=="build-surface" else 48) for name,fn in
            (("workflow",workflow),("studio",studio),("lab",lab),("forge",forge),("ledger",ledger),("assistant",assistant),("workspace",workspace),("operations",operations),("build-surface",build_surface))]
    (OUT/"verification.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    thumbs=[]
    for name in ("workflow","studio","lab","forge","ledger","assistant","workspace","operations","build-surface"):
        image=Image.open(OUT/(name+"-poster.png")); image.thumbnail((600,225)); thumbs.append(image)
    sheet=Image.new("RGB",(1200,225*5),(13,20,28))
    for i,thumb in enumerate(thumbs): sheet.paste(thumb,((i%2)*600,(i//2)*225))
    sheet.save(OUT/"contact-sheet.png")
    print(json.dumps(report,indent=2))
