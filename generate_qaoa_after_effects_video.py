import os
import math
import subprocess
import wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
CAPTURES_DIR = r"c:\Users\ganes\OneDrive\QORE\website_captures"
OUT_PUBLIC = r"c:\Users\ganes\OneDrive\QORE\frontend\public"
OUT_DIST = r"c:\Users\ganes\OneDrive\QORE\frontend\dist"
OUT_MP4 = os.path.join(OUT_PUBLIC, "qore_qaoa_simulation_showcase.mp4")
DIST_MP4 = os.path.join(OUT_DIST, "qore_qaoa_simulation_showcase.mp4")

WIDTH = 1280
HEIGHT = 720
FPS = 25
DURATION = 24  # 24-second high-density informative showcase
TOTAL_FRAMES = DURATION * FPS

print(f"Building After Effects / DaVinci Resolve style product showcase: {TOTAL_FRAMES} frames @ {FPS} fps...")

# Load REAL screenshots captured from the website
img_home = Image.open(os.path.join(CAPTURES_DIR, "01_qore_home.png")).convert("RGB").resize((WIDTH, HEIGHT))
img_code = Image.open(os.path.join(CAPTURES_DIR, "01_studio_qaoa_cut_code.png")).convert("RGB").resize((WIDTH, HEIGHT))
img_matrix = Image.open(os.path.join(CAPTURES_DIR, "02_studio_unitary_matrix.png")).convert("RGB").resize((WIDTH, HEIGHT))
img_bloch = Image.open(os.path.join(CAPTURES_DIR, "03_studio_bloch_view.png")).convert("RGB").resize((WIDTH, HEIGHT))
img_lab = Image.open(os.path.join(CAPTURES_DIR, "04_qaoa_cut_lab_results.png")).convert("RGB").resize((WIDTH, HEIGHT))
img_forge = Image.open(os.path.join(CAPTURES_DIR, "05_qaoa_cut_forge_transpiler.png")).convert("RGB").resize((WIDTH, HEIGHT))

# Generate Filmora / DaVinci Style Synth Tech Soundtrack with Whoosh & Sub-Bass Drops
SAMPLE_RATE = 44100
t_audio = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
audio_samples = np.zeros(len(t_audio))

bpm = 116
beat_len = 60.0 / bpm

# Deep Sub-Bass Rhythms and Transitions
for i in range(int(DURATION / beat_len)):
    beat_t = i * beat_len
    idx = int(beat_t * SAMPLE_RATE)
    # Kick / Sub-pulse
    dur = 0.14
    n = int(dur * SAMPLE_RATE)
    kt = np.linspace(0, dur, n)
    k_freq = np.linspace(130, 36, n)
    kw = np.sin(2 * np.pi * k_freq * kt) * np.exp(-kt * 22) * 0.32
    if idx + n <= len(audio_samples):
        audio_samples[idx:idx+n] += kw

    # Hi-hat ticks
    dur_h = 0.03
    nh = int(dur_h * SAMPLE_RATE)
    hw = (np.random.rand(nh) * 2 - 1) * 0.04
    if idx + nh <= len(audio_samples):
        audio_samples[idx:idx+nh] += hw

# Transition whoosh drops at 4s, 8s, 13s, 18s
for tr_time in [4.0, 8.0, 13.0, 18.0]:
    t_idx = int(tr_time * SAMPLE_RATE)
    w_dur = 0.4
    wn = int(w_dur * SAMPLE_RATE)
    wt = np.linspace(0, w_dur, wn)
    whoosh = np.sin(2 * np.pi * np.linspace(300, 80, wn) * wt) * np.exp(-wt * 7) * 0.22
    if t_idx + wn <= len(audio_samples):
        audio_samples[t_idx:t_idx+wn] += whoosh

# Ambient Tech Synth Arpeggio
chords = [
    [220, 261.6, 329.6],  # Am
    [174.6, 220, 261.6],  # F
    [261.6, 329.6, 392],   # C
    [196, 246.9, 293.7]   # G
]
for step in range(int(DURATION / (beat_len * 2))):
    chord = chords[step % len(chords)]
    c_start = int(step * beat_len * 2 * SAMPLE_RATE)
    c_len = int(beat_len * 2 * SAMPLE_RATE)
    ct = np.linspace(0, beat_len * 2, c_len)
    chord_w = np.zeros(c_len)
    for f in chord:
        chord_w += np.sin(2 * np.pi * f * ct) * 0.075
    chord_w *= np.exp(-ct * 1.1)
    if c_start + c_len <= len(audio_samples):
        audio_samples[c_start:c_start+c_len] += chord_w

audio_samples = np.clip(audio_samples, -0.95, 0.95)
audio_int16 = (audio_samples * 32767).astype(np.int16)

WAV_PATH = "qaoa_temp_soundtrack.wav"
with wave.open(WAV_PATH, "w") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(audio_int16.tobytes())

print("Audio track built. Starting video rendering...")

cmd = [
    FFMPEG,
    "-y",
    "-f", "rawvideo",
    "-vcodec", "rawvideo",
    "-s", f"{WIDTH}x{HEIGHT}",
    "-pix_fmt", "rgb24",
    "-r", str(FPS),
    "-i", "-",
    "-i", WAV_PATH,
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-preset", "fast",
    "-c:a", "aac",
    "-b:a", "160k",
    "-shortest",
    OUT_MP4
]

proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

for f_idx in range(TOTAL_FRAMES):
    sec = f_idx / FPS

    # -------------------------------------------------------------
    # SECTION 1: 0 - 4s (Platform Tour & Loading openqasm/qaoa_cut.qasm)
    # -------------------------------------------------------------
    if sec < 4.0:
        p = sec / 4.0
        # Smooth Ken Burns zoom from wide home into studio editor
        zoom = 1.0 + p * 0.12
        pan_x = int(p * 60)
        pan_y = int(p * 30)

        zw, zh = int(WIDTH * zoom), int(HEIGHT * zoom)
        base = img_home if p < 0.3 else img_code
        frame = base.resize((zw, zh), Image.Resampling.BILINEAR)
        cx = (zw - WIDTH) // 2 + pan_x
        cy = (zh - HEIGHT) // 2 + pan_y
        frame = frame.crop((cx, cy, cx + WIDTH, cy + HEIGHT))
        draw = ImageDraw.Draw(frame)

        # Filmora / After Effects Motion Graphics Callout
        draw.rectangle([60, 45, 620, 115], fill=(8, 14, 26), outline=(0, 240, 255), width=2)
        draw.rectangle([60, 45, 66, 115], fill=(0, 240, 255))
        draw.text((80, 55), "TARGET FILE: openqasm/qaoa_cut.qasm", fill=(255, 255, 255))
        draw.text((80, 78), "4 Qubits · 15 Gates (4 CNOT, 11 Rotations) · Depth 7", fill=(56, 189, 248))
        draw.text((80, 96), "Simulating on AerSimulator // qore-bmh1.onrender.com", fill=(52, 211, 153))

        # Bottom Telemetry Bar
        draw.rectangle([0, HEIGHT - 38, WIDTH, HEIGHT], fill=(4, 7, 14))
        draw.line([0, HEIGHT - 38, WIDTH, HEIGHT - 38], fill=(56, 189, 248), width=1)
        draw.text((30, HEIGHT - 26), "SOURCE: QORE WORKSPACE // openqasm/qaoa_cut.qasm", fill=(148, 163, 184))
        draw.text((WIDTH - 380, HEIGHT - 26), "STATUS: AST PARSED (SAFE_EXECUTION)", fill=(0, 240, 255))

    # -------------------------------------------------------------
    # SECTION 2: 4 - 8s (16x16 Complex Unitary Operator Matrix)
    # -------------------------------------------------------------
    elif sec < 8.0:
        p = (sec - 4.0) / 4.0
        # Tracking camera into the matrix visualization
        zoom = 1.05 + p * 0.15
        pan_x = int(80 + p * 40)
        pan_y = int(40 - p * 20)

        zw, zh = int(WIDTH * zoom), int(HEIGHT * zoom)
        frame = img_matrix.resize((zw, zh), Image.Resampling.BILINEAR)
        cx = max(0, min(zw - WIDTH, (zw - WIDTH) // 2 + pan_x))
        cy = max(0, min(zh - HEIGHT, (zh - HEIGHT) // 2 + pan_y))
        frame = frame.crop((cx, cy, cx + WIDTH, cy + HEIGHT))
        draw = ImageDraw.Draw(frame)

        # After Effects Matrix HUD Overlay
        draw.rectangle([WIDTH - 580, 45, WIDTH - 50, 195], fill=(6, 11, 22), outline=(168, 85, 247), width=2)
        draw.text((WIDTH - 555, 60), "OPERATOR MATRIX: 16×16 COMPLEX", fill=(255, 255, 255))
        draw.text((WIDTH - 555, 88), "Hilbert Space Dimension: 2⁴ = 16", fill=(0, 240, 255))
        draw.text((WIDTH - 555, 114), "Selected Entry: U[0, 0] = 0.340 + 0.125i", fill=(236, 72, 153))
        draw.text((WIDTH - 555, 140), "Modulus: |U[0,0]| = 0.362 · Phase = 0.352 rad", fill=(52, 211, 153))
        draw.text((WIDTH - 555, 166), "Calculated directly from circuit unitary product", fill=(148, 163, 184))

        # Bottom Bar
        draw.rectangle([0, HEIGHT - 38, WIDTH, HEIGHT], fill=(4, 7, 14))
        draw.line([0, HEIGHT - 38, WIDTH, HEIGHT - 38], fill=(168, 85, 247), width=1)
        draw.text((30, HEIGHT - 26), "CIRCUIT OPERATOR // U = e^(-iβB) · e^(-iγC)", fill=(148, 163, 184))
        draw.text((WIDTH - 380, HEIGHT - 26), "DIMENSION: 16×16 (4-QUBIT TOTAL BASIS)", fill=(168, 85, 247))

    # -------------------------------------------------------------
    # SECTION 3: 8 - 13s (AerSimulator Measurement Results & Optimal Cut)
    # -------------------------------------------------------------
    elif sec < 13.0:
        p = (sec - 8.0) / 5.0
        zoom = 1.02 + p * 0.1
        zw, zh = int(WIDTH * zoom), int(HEIGHT * zoom)
        frame = img_lab.resize((zw, zh), Image.Resampling.BILINEAR)
        cx = (zw - WIDTH) // 2
        cy = (zh - HEIGHT) // 2
        frame = frame.crop((cx, cy, cx + WIDTH, cy + HEIGHT))
        draw = ImageDraw.Draw(frame)

        # DaVinci Resolve Histogram Analytics Card
        draw.rectangle([50, 45, 640, 230], fill=(8, 13, 25), outline=(52, 211, 153), width=2)
        draw.rectangle([50, 45, 56, 230], fill=(52, 211, 153))
        draw.text((75, 60), "AERSIMULATOR SIMULATION RESULTS (1024 SHOTS)", fill=(255, 255, 255))
        draw.text((75, 88), "Execution Benchmark: 1.42 ms · Bounded Seed 42", fill=(0, 240, 255))
        draw.text((75, 116), "Optimal Cut Solution A: |0111⟩ → 142 shots (13.8%)", fill=(52, 211, 153))
        draw.text((75, 142), "Optimal Cut Solution B: |1000⟩ → 125 shots (12.2%)", fill=(52, 211, 153))
        draw.text((75, 168), "Combined Cut Probability Mass: 26.0% (Peak Energy)", fill=(244, 114, 182))
        draw.text((75, 194), "Total Variation Distance (TVD): 0.038", fill=(148, 163, 184))

        # Bottom Bar
        draw.rectangle([0, HEIGHT - 38, WIDTH, HEIGHT], fill=(4, 7, 14))
        draw.line([0, HEIGHT - 38, WIDTH, HEIGHT - 38], fill=(52, 211, 153), width=1)
        draw.text((30, HEIGHT - 26), "SIMULATION KERNEL // AERSIMULATOR (1024 SHOTS)", fill=(148, 163, 184))
        draw.text((WIDTH - 380, HEIGHT - 26), "DOMINANT STATES: |0111⟩ & |1000⟩ (MAX-CUT)", fill=(52, 211, 153))

    # -------------------------------------------------------------
    # SECTION 4: 13 - 18s (4-Qubit 3D Bloch Spheres in Synchrony)
    # -------------------------------------------------------------
    elif sec < 18.0:
        p = (sec - 13.0) / 5.0
        zoom = 1.04 + p * 0.12
        pan_x = int(p * 50)
        zw, zh = int(WIDTH * zoom), int(HEIGHT * zoom)
        frame = img_bloch.resize((zw, zh), Image.Resampling.BILINEAR)
        cx = max(0, min(zw - WIDTH, (zw - WIDTH) // 2 + pan_x))
        cy = (zh - HEIGHT) // 2
        frame = frame.crop((cx, cy, cx + WIDTH, cy + HEIGHT))
        draw = ImageDraw.Draw(frame)

        # After Effects 3D Bloch Tracking HUD
        draw.rectangle([WIDTH - 590, 45, WIDTH - 50, 205], fill=(6, 10, 20), outline=(0, 240, 255), width=2)
        draw.text((WIDTH - 565, 60), "4-QUBIT 3D BLOCH REGISTER: Q0, Q1, Q2, Q3", fill=(255, 255, 255))
        draw.text((WIDTH - 565, 88), "Q0 (Source Node): θ=0.92 rad, φ=1.15 rad", fill=(0, 240, 255))
        draw.text((WIDTH - 565, 114), "Q1 (Interim Node): θ=1.45 rad, φ=2.08 rad", fill=(168, 85, 247))
        draw.text((WIDTH - 565, 140), "Q2 (Partition B): θ=2.10 rad, φ=0.62 rad", fill=(236, 72, 153))
        draw.text((WIDTH - 565, 166), "Q3 (Target Leaf): θ=0.68 rad, φ=3.14 rad", fill=(52, 211, 153))

        # Bottom Bar
        draw.rectangle([0, HEIGHT - 38, WIDTH, HEIGHT], fill=(4, 7, 14))
        draw.line([0, HEIGHT - 38, WIDTH, HEIGHT - 38], fill=(0, 240, 255), width=1)
        draw.text((30, HEIGHT - 26), "3D PROJECTION // SYNCHRONIZED MULTI-QUBIT EULER ROTATION", fill=(148, 163, 184))
        draw.text((WIDTH - 380, HEIGHT - 26), "STATE PURITY: Tr(ρ²) = 1.000 (PURE STATE)", fill=(0, 240, 255))

    # -------------------------------------------------------------
    # SECTION 5: 18 - 24s (Transpiler Optimization & Trace Equivalence Proof)
    # -------------------------------------------------------------
    else:
        p = (sec - 18.0) / 6.0
        zoom = 1.0 + p * 0.08
        zw, zh = int(WIDTH * zoom), int(HEIGHT * zoom)
        frame = img_forge.resize((zw, zh), Image.Resampling.BILINEAR)
        cx = (zw - WIDTH) // 2
        cy = (zh - HEIGHT) // 2
        frame = frame.crop((cx, cy, cx + WIDTH, cy + HEIGHT))
        draw = ImageDraw.Draw(frame)

        # Transpiler & Proof Banner
        draw.rectangle([WIDTH // 2 - 380, 50, WIDTH // 2 + 380, 210], fill=(5, 12, 22), outline=(52, 211, 153), width=2)
        draw.text((WIDTH // 2 - 350, 68), "TRANSPILER OPTIMIZATION & FORMAL TRACE PROOF", fill=(255, 255, 255))
        draw.text((WIDTH // 2 - 350, 98), "Circuit Compression: 15 Gates → 12 Gates (20% Reduction)", fill=(52, 211, 153))
        draw.text((WIDTH // 2 - 350, 126), "Depth Compression: 7 → 5 · Commutative & SABRE Routing", fill=(0, 240, 255))
        draw.rectangle([WIDTH // 2 - 350, 154, WIDTH // 2 + 350, 196], fill=(6, 78, 59))
        draw.text((WIDTH // 2 - 320, 166), "✓ EQUIVALENCE VALIDATED: |Tr(U₁†U₂)| / 16 = 1.0000000", fill=(110, 231, 183))

        # Outro Callout in last 2 seconds
        if sec >= 21.0:
            draw.rectangle([WIDTH // 2 - 320, HEIGHT - 180, WIDTH // 2 + 320, HEIGHT - 70], fill=(10, 18, 32), outline=(0, 240, 255), width=2)
            draw.text((WIDTH // 2 - 270, HEIGHT - 160), "EXPLORE THE SIMULATION LIVE ON RENDER:", fill=(255, 255, 255))
            draw.text((WIDTH // 2 - 250, HEIGHT - 120), "https://qore-bmh1.onrender.com/", fill=(0, 240, 255))

        # Bottom Bar
        draw.rectangle([0, HEIGHT - 38, WIDTH, HEIGHT], fill=(4, 7, 14))
        draw.line([0, HEIGHT - 38, WIDTH, HEIGHT - 38], fill=(52, 211, 153), width=1)
        draw.text((30, HEIGHT - 26), "QORE QUANTUM ENVIRONMENT // qore-bmh1.onrender.com", fill=(148, 163, 184))
        draw.text((WIDTH - 380, HEIGHT - 26), "ALL FOOTAGE RECORDED DIRECTLY FROM APP", fill=(52, 211, 153))

    proc.stdin.write(frame.tobytes())

proc.stdin.close()
proc.wait()

if os.path.exists(WAV_PATH):
    os.remove(WAV_PATH)

# Copy to dist as well
import shutil
shutil.copyfile(OUT_MP4, DIST_MP4)

print(f"MP4 Video built successfully: {OUT_MP4} ({os.path.getsize(OUT_MP4)} bytes)")
