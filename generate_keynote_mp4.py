import os
import math
import subprocess
import wave
import struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
OUT_DIR = r"c:\Users\ganes\OneDrive\QORE\frontend\public"
DIST_DIR = r"c:\Users\ganes\OneDrive\QORE\frontend\dist"
OUT_MP4 = os.path.join(OUT_DIR, "qore_keynote_walkthrough.mp4")
DIST_MP4 = os.path.join(DIST_DIR, "qore_keynote_walkthrough.mp4")

PRESENTER_IMG_PATH = os.path.join(OUT_DIR, "presenter_keynote.jpg")
GESTURE_IMG_PATH = os.path.join(OUT_DIR, "presenter_keynote_gesture.jpg")

WIDTH = 1280
HEIGHT = 720
FPS = 24
DURATION = 20 # 20 second broadcast demo reel
TOTAL_FRAMES = DURATION * FPS

print(f"Generating Keynote MP4: {TOTAL_FRAMES} frames @ {FPS} fps...")

# Load presenter images
img_presenter = Image.open(PRESENTER_IMG_PATH).convert("RGB").resize((WIDTH, HEIGHT))
img_gesture = Image.open(GESTURE_IMG_PATH).convert("RGB").resize((WIDTH, HEIGHT))

# Pre-generate Audio (44.1kHz stereo)
SAMPLE_RATE = 44100
t_audio = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
audio_samples = np.zeros(len(t_audio))

# Upbeat 120 BPM Keynote Synth Chords & Beats
bpm = 120
beat_len = 60.0 / bpm

for i in range(int(DURATION / beat_len)):
    beat_t = i * beat_len
    idx_start = int(beat_t * SAMPLE_RATE)
    # Kick on beats 0, 2
    if i % 2 == 0:
        kick_dur = 0.12
        kick_n = int(kick_dur * SAMPLE_RATE)
        kt = np.linspace(0, kick_dur, kick_n)
        k_freq = np.linspace(150, 40, kick_n)
        kick_wave = np.sin(2 * np.pi * k_freq * kt) * np.exp(-kt * 25) * 0.35
        if idx_start + kick_n <= len(audio_samples):
            audio_samples[idx_start:idx_start+kick_n] += kick_wave

    # Snare on beats 1, 3
    if i % 2 == 1:
        snare_dur = 0.14
        snare_n = int(snare_dur * SAMPLE_RATE)
        st = np.linspace(0, snare_dur, snare_n)
        snare_wave = (np.random.rand(snare_n) * 2 - 1) * np.exp(-st * 20) * 0.2
        if idx_start + snare_n <= len(audio_samples):
            audio_samples[idx_start:idx_start+snare_n] += snare_wave

# Synth Chords
chords = [
    [220, 261.6, 329.6], # Am
    [174.6, 220, 261.6], # F
    [261.6, 329.6, 392],  # C
    [196, 246.9, 293.7]  # G
]
for step in range(int(DURATION / (beat_len * 2))):
    c_idx = step % len(chords)
    chord = chords[c_idx]
    c_start = int(step * beat_len * 2 * SAMPLE_RATE)
    c_len = int(beat_len * 2 * SAMPLE_RATE)
    ct = np.linspace(0, beat_len * 2, c_len)
    chord_wave = np.zeros(c_len)
    for f in chord:
        chord_wave += np.sin(2 * np.pi * f * ct) * 0.08
    chord_wave *= np.exp(-ct * 1.2)
    if c_start + c_len <= len(audio_samples):
        audio_samples[c_start:c_start+c_len] += chord_wave

# Normalize audio to 16-bit PCM
audio_samples = np.clip(audio_samples, -0.95, 0.95)
audio_int16 = (audio_samples * 32767).astype(np.int16)

WAV_PATH = "keynote_temp.wav"
with wave.open(WAV_PATH, "w") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(audio_int16.tobytes())

print("Audio track generated. Rendering video frames via FFmpeg pipe...")

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
    "-preset", "veryfast",
    "-c:a", "aac",
    "-b:a", "128k",
    "-shortest",
    OUT_MP4
]

proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

for f_idx in range(TOTAL_FRAMES):
    sec = f_idx / FPS
    
    # Scene 1: 0 - 4s (Studio Opening with Alex Rivera)
    if sec < 4.0:
        zoom = 1.0 + (sec / 4.0) * 0.05
        zw, zh = int(WIDTH * zoom), int(HEIGHT * zoom)
        frame = img_presenter.resize((zw, zh), Image.Resampling.BILINEAR)
        crop_x = (zw - WIDTH) // 2
        crop_y = (zh - HEIGHT) // 2
        frame = frame.crop((crop_x, crop_y, crop_x + WIDTH, crop_y + HEIGHT))
        draw = ImageDraw.Draw(frame)

        # Lower-third
        draw.rectangle([50, HEIGHT - 140, 520, HEIGHT - 60], fill=(10, 16, 30))
        draw.line([50, HEIGHT - 140, 50, HEIGHT - 60], fill=(0, 240, 255), width=5)
        draw.text((70, HEIGHT - 130), "ALEX RIVERA", fill=(255, 255, 255))
        draw.text((70, HEIGHT - 100), "Developer Advocate // QORE Quantum", fill=(0, 240, 255))
        draw.text((70, HEIGHT - 80), "LIVE KEYNOTE WALKTHROUGH", fill=(148, 163, 184))

    # Scene 2: 4 - 8s (Studio IDE & openqasm/qaoa_cut.qasm)
    elif sec < 8.0:
        frame = Image.new("RGB", (WIDTH, HEIGHT), (8, 12, 20))
        draw = ImageDraw.Draw(frame)
        
        # IDE Window
        draw.rectangle([40, 30, WIDTH - 40, HEIGHT - 30], fill=(12, 16, 28), outline=(56, 189, 248), width=1)
        draw.rectangle([40, 30, WIDTH - 40, 70], fill=(18, 24, 40))
        draw.ellipse([55, 46, 67, 58], fill=(239, 68, 68))
        draw.ellipse([75, 46, 87, 58], fill=(245, 158, 11))
        draw.ellipse([95, 46, 107, 58], fill=(16, 185, 129))
        draw.text((120, 44), "QORE STUDIO — openqasm/qaoa_cut.qasm", fill=(226, 232, 240))

        # Code lines
        code_lines = [
            "OPENQASM 2.0;",
            "include \"qelib1.inc\";",
            "qreg q[4]; creg c[4];",
            "h q[0]; h q[1]; h q[2]; h q[3];",
            "// Problem Hamiltonian (ZZ Interactions)",
            "cx q[0], q[1]; rz(0.45) q[1]; cx q[0], q[1];",
            "cx q[1], q[2]; rz(0.45) q[2]; cx q[1], q[2];",
            "// Mixer Hamiltonian",
            "rx(0.62) q[0]; rx(0.62) q[1];",
            "measure q -> c;"
        ]
        y_pos = 95
        for cl in code_lines:
            color = (244, 114, 182) if "OPENQASM" in cl or "include" in cl or "qreg" in cl else ((56, 189, 248) if "h " in cl or "cx " in cl or "rx" in cl else (148, 163, 184))
            draw.text((65, y_pos), cl, fill=color)
            y_pos += 26

        # Humanoid Presenter PiP (Picture in Picture)
        pip_w, pip_h = 240, 150
        pip_thumb = img_presenter.resize((pip_w, pip_h))
        frame.paste(pip_thumb, (WIDTH - 290, HEIGHT - 200))
        draw.rectangle([WIDTH - 290, HEIGHT - 200, WIDTH - 50, HEIGHT - 50], outline=(0, 240, 255), width=2)
        draw.text((WIDTH - 280, HEIGHT - 45), "Alex Rivera // Live", fill=(0, 240, 255))

    # Scene 3: 8 - 12s (16x16 Complex Unitary Matrix)
    elif sec < 12.0:
        frame = Image.new("RGB", (WIDTH, HEIGHT), (6, 9, 16))
        draw = ImageDraw.Draw(frame)

        draw.text((60, 40), "UNITARY OPERATOR MATRIX (16×16 COMPLEX) · dim = 2⁴", fill=(0, 240, 255))
        draw.text((60, 65), "Full QAOA Cut operator calculated in real time", fill=(148, 163, 184))

        # Draw 16x16 matrix grid
        cell_size = 28
        start_x, start_y = 60, 110
        for r in range(16):
            for c in range(16):
                val = abs(math.sin((r * 3 + c * 5) * 0.4) * 0.4 + (0.25 if r == c else 0.05))
                green = int(min(255, val * 500))
                blue = int(min(255, 120 + val * 300))
                draw.rectangle([start_x + c * cell_size, start_y + r * cell_size, start_x + (c+1) * cell_size - 2, start_y + (r+1) * cell_size - 2], fill=(10, green, blue))

        # Matrix Inspection callout
        draw.rectangle([600, 180, 1100, 360], fill=(13, 20, 36), outline=(0, 240, 255), width=2)
        draw.text((630, 210), "MATRIX ENTRY INSPECTOR: U[0, 0]", fill=(255, 255, 255))
        draw.text((630, 245), "Modulus: |U[0,0]| = 0.3404", fill=(56, 189, 248))
        draw.text((630, 275), "Phase: 0.125 rad  (e^(0.125i))", fill=(168, 85, 247))
        draw.text((630, 305), "Pauli Basis: 0.25(I⊗I⊗I⊗I) - 0.18(Z⊗Z⊗I⊗I)", fill=(52, 211, 153))

        # PiP
        pip_w, pip_h = 240, 150
        pip_thumb = img_gesture.resize((pip_w, pip_h))
        frame.paste(pip_thumb, (WIDTH - 290, HEIGHT - 200))
        draw.rectangle([WIDTH - 290, HEIGHT - 200, WIDTH - 50, HEIGHT - 50], outline=(0, 240, 255), width=2)

    # Scene 4: 12 - 16s (3D Bloch Spheres & Aer 1024 Shots)
    elif sec < 16.0:
        frame = Image.new("RGB", (WIDTH, HEIGHT), (4, 7, 14))
        draw = ImageDraw.Draw(frame)

        draw.text((60, 35), "AERSIMULATOR EXECUTION & 3D BLOCH REGISTER (Q0, Q1, Q2, Q3)", fill=(0, 240, 255))

        # Measurement histogram
        draw.rectangle([60, 80, 520, 480], fill=(10, 16, 28), outline=(56, 189, 248), width=1)
        draw.text((80, 95), "SIMULATION DISTRIBUTION (1024 SHOTS · 1.42ms)", fill=(52, 211, 153))

        states = [("|0111⟩", 82, "142 (13.8%) - Optimal Cut A"),
                  ("|1000⟩", 73, "125 (12.2%) - Optimal Cut B"),
                  ("|0000⟩", 63, "109 (10.6%)"),
                  ("|1111⟩", 61, "105 (10.2%)"),
                  ("|1001⟩", 40, "68 (6.6%)")]
        
        y_b = 135
        for s, w_pct, cnt in states:
            draw.text((80, y_b), s, fill=(129, 140, 248))
            draw.rectangle([150, y_b, 150 + int(w_pct * 2.2), y_b + 18], fill=(0, 240, 255) if "Optimal" in cnt else (56, 189, 248))
            draw.text((390, y_b), cnt, fill=(248, 250, 252))
            y_b += 45

        # 4 Bloch spheres representation
        b_x, b_y = 570, 80
        draw.rectangle([b_x, b_y, WIDTH - 60, 480], fill=(10, 16, 28), outline=(168, 85, 247), width=1)
        draw.text((b_x + 20, b_y + 15), "4-QUBIT 3D BLOCH REGISTRY (SYNCHRONIZED PERSPECTIVE)", fill=(168, 85, 247))

        sphere_centers = [
            (b_x + 150, b_y + 130, "Q0", (0, 240, 255)),
            (b_x + 450, b_y + 130, "Q1", (168, 85, 247)),
            (b_x + 150, b_y + 290, "Q2", (236, 72, 153)),
            (b_x + 450, b_y + 290, "Q3", (52, 211, 153))
        ]

        b_phase = sec * 3
        for sx, sy, q_name, col in sphere_centers:
            # Sphere circle
            draw.ellipse([sx - 55, sy - 55, sx + 55, sy + 55], outline=(56, 189, 248), width=2)
            draw.ellipse([sx - 55, sy - 18, sx + 55, sy + 18], outline=(100, 116, 139), width=1)
            draw.line([sx, sy - 65, sx, sy + 65], fill=(148, 163, 184), width=1)
            # Vector
            vx = sx + int(math.cos(b_phase) * 45)
            vy = sy - int(math.sin(b_phase) * 45)
            draw.line([sx, sy, vx, vy], fill=col, width=3)
            draw.ellipse([vx - 4, vy - 4, vx + 4, vy + 4], fill=(255, 255, 255))
            draw.text((sx - 10, sy - 75), q_name, fill=col)

        # PiP
        pip_w, pip_h = 240, 150
        pip_thumb = img_gesture.resize((pip_w, pip_h))
        frame.paste(pip_thumb, (WIDTH - 290, HEIGHT - 200))
        draw.rectangle([WIDTH - 290, HEIGHT - 200, WIDTH - 50, HEIGHT - 50], outline=(0, 240, 255), width=2)

    # Scene 5: 16 - 20s (Outro & Live Cloud Launch)
    else:
        zoom = 1.0 + ((sec - 16.0) / 4.0) * 0.04
        zw, zh = int(WIDTH * zoom), int(HEIGHT * zoom)
        frame = img_gesture.resize((zw, zh), Image.Resampling.BILINEAR)
        crop_x = (zw - WIDTH) // 2
        crop_y = (zh - HEIGHT) // 2
        frame = frame.crop((crop_x, crop_y, crop_x + WIDTH, crop_y + HEIGHT))
        draw = ImageDraw.Draw(frame)

        # Outro Banner
        draw.rectangle([WIDTH // 2 - 350, HEIGHT // 2 - 120, WIDTH // 2 + 350, HEIGHT // 2 + 120], fill=(8, 14, 26), outline=(0, 240, 255), width=2)
        draw.text((WIDTH // 2 - 280, HEIGHT // 2 - 90), "BUILD QUANTUM ALGORITHMS TODAY", fill=(255, 255, 255))
        draw.text((WIDTH // 2 - 300, HEIGHT // 2 - 50), "Browser-native IDE · AerSimulator · 3D Bloch Spheres", fill=(148, 163, 184))
        draw.rectangle([WIDTH // 2 - 240, HEIGHT // 2 + 15, WIDTH // 2 + 240, HEIGHT // 2 + 75], fill=(0, 240, 255))
        draw.text((WIDTH // 2 - 200, HEIGHT // 2 + 35), "LAUNCH LIVE: qore-bmh1.onrender.com ->", fill=(4, 8, 16))

    # Send raw RGB bytes to ffmpeg
    proc.stdin.write(frame.tobytes())

proc.stdin.close()
proc.wait()
if os.path.exists(WAV_PATH):
    os.remove(WAV_PATH)

# Copy to dist as well
import shutil
shutil.copyfile(OUT_MP4, DIST_MP4)

print(f"MP4 Video rendered successfully to {OUT_MP4} ({os.path.getsize(OUT_MP4)} bytes)")
