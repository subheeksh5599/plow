#!/usr/bin/env python3
"""Render the Plow demo video (1920x1080@30) — PIL frames piped to ffmpeg.

Scenes: quote cold-open -> title -> terminal scan/rank -> terminal gated deposit
(recorded real run) -> terminal DENY -> evidence slate -> outro. Narration audio
from docs/demo/sNN.mp3 drives per-scene durations; captions burned in.
"""
import glob
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 30
DEMO = os.path.join(os.path.dirname(__file__), "..", "docs", "demo")
OUT = os.path.join(DEMO, "plow-demo.mp4")

NAVY = (13, 37, 61)
TEXT = (215, 224, 234)
DIM = (138, 155, 176)
GREEN = (110, 231, 160)
PINK = (255, 179, 230)
PURPLE = (185, 185, 249)
YELLOW = (255, 215, 110)
WHITE = (245, 248, 252)
MAGENTA_LIGHT = (255, 215, 239)

MONO = glob.glob("/usr/share/fonts/TTF/JetBrainsMonoNerdFontMono-*.ttf") or ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]
SANS_BOLD = glob.glob("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf") or ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def mono(size):
    return ImageFont.truetype(MONO[0], size)


def sans(size):
    return ImageFont.truetype(SANS_BOLD[0], size)


def scene_duration(audio: str, min_s: float, pad: float = 1.4) -> float:
    if not os.path.exists(audio):
        return min_s
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio],
        capture_output=True, text=True,
    )
    return max(min_s, float(out.stdout.strip()) + pad)


# ---------------------------------------------------------------- frames
def frame_base():
    img = Image.new("RGB", (W, H), NAVY)
    return img, ImageDraw.Draw(img)


def caption(draw, text, y=952):
    f = sans(26)
    box = draw.textbbox((0, 0), text, font=f)
    tw = box[2] - box[0]
    x = (W - tw) // 2
    draw.rounded_rectangle([x - 28, y - 8, x + tw + 28, y + 52], radius=10, fill=(9, 22, 38, 0))
    draw.rectangle([0, y, W, y + 44], fill=(9, 22, 38))
    draw.text((x, y), text, font=f, fill=WHITE)


def slate_frame(lines, big=92, mid=34, spacing=None, center_y=430):
    """lines: list of (text, fontsize, color)."""
    img, draw = frame_base()
    spacing = spacing or big // 2
    y = center_y
    for text, size, color in lines:
        f = sans(size)
        box = draw.textbbox((0, 0), text, font=f)
        draw.text(((W - (box[2] - box[0])) // 2, y), text, font=f, fill=color)
        y += size + spacing
    return img


def terminal_frame(lines, visible_chars, cursor, typed_all, title="plow — scan → rank → gate → deposit"):
    """lines: list of (segments, hold_s) where segments = [(text, color), ...]."""
    img, draw = frame_base()
    # title bar
    draw.rectangle([0, 0, W, 52], fill=(20, 44, 70))
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        draw.ellipse([150 + i * 26, 20, 166 + i * 26, 36], fill=c)
    draw.text((240, 16), title, font=mono(20), fill=(138, 155, 176))
    # terminal area
    x0, y0 = 150, 110
    f = mono(28)
    y = y0
    remaining = visible_chars
    for segs, hold in lines:
        line_len = sum(len(t) for t, _ in segs)
        take = min(remaining, line_len)
        remaining -= take
        x = x0
        for text, color in segs:
            if take <= 0:
                break
            part = text[:take]
            draw.text((x, y), part, font=f, fill=color)
            x += draw.textlength(part, font=f)
            take -= len(part)
        y += 44
        if remaining <= 0:
            break
    # prompt + cursor
    px, py = x0, y
    draw.text((px, py), "$ ", font=f, fill=DIM)
    if cursor:
        draw.rectangle([px + draw.textlength("$ ", font=f), py, px + draw.textlength("$ ", font=f) + 18, py + 36], fill=PURPLE)
    return img


def evidence_frame():
    img, draw = frame_base()
    rows = [
        ("Run", "Action", "Transaction", "Status", DIM),
        ("01", "Mint 10,000 MockUSDC seed", "0x6bdf4521…32b6", "sponsored", GREEN),
        ("02", "Approve exact 1,000 (PREFILL-07)", "0x6724cd07…5a2c", "sponsored", GREEN),
        ("03", "Deposit ALLOW → venue", "0x4fae07dd…f326", "sponsored", GREEN),
        ("04", "Deposit ALLOW → venue", "0xc137e53f…e6c8", "sponsored", GREEN),
        ("05", "Deposit DENY (unlisted venue)", "zero txs", "blocked", PINK),
        ("06", "verify_position read-back", "2,000 sUSDS", "verified", GREEN),
    ]
    f = mono(30)
    draw.text((150, 140), "Transactions, not mockups", font=sans(56), fill=WHITE)
    cols = [150, 360, 1150, 1500]
    y = 280
    for row in rows:
        for (txt, cx) in zip(row, cols):
            color = row[4] if len(row) == 5 else DIM
            if row is rows[0]:
                color = DIM
            draw.text((cx, y), txt, font=f, fill=color)
        y += 56
    draw.text((150, y + 30), "Every hash status 1 on Etherscan · 2,000 sUSDS confirmed onchain", font=mono(30), fill=GREEN)
    return img


# ---------------------------------------------------------------- scenes
def render_scene(name, frames_iter, duration, audio_in, audio_out):
    n = int(round(duration * FPS))
    cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        os.path.join(DEMO, f"scene_{name}.mp4"),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    last = None
    i = 0
    for frame in frames_iter:
        if i >= n:
            break
        last = frame
        proc.stdin.write(frame.tobytes())
        i += 1
    # pad any shortfall with the last frame so the scene is exactly n frames
    if last is not None:
        while i < n:
            proc.stdin.write(last.tobytes())
            i += 1
    proc.stdin.close()
    proc.wait()
    # pad narration to scene duration -> wav
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", audio_in, "-ar", "44100", "-ac", "1", "-af", "apad", "-t", f"{duration:.3f}", audio_out],
        check=True,
    )


def typing_frames(lines, cps=42, hold_end=4.0, title="plow — scan → rank → gate → deposit"):
    """Yield frames while lines type in, then hold with a blinking cursor."""
    total_chars = sum(sum(len(t) for t, _ in segs) for segs, _ in lines)
    total_frames = int((total_chars / cps) * FPS)
    cursor_on = True
    cursor_toggle = 18
    typed = 0
    for fi in range(total_frames):
        cursor_on = (fi // cursor_toggle) % 2 == 0
        yield terminal_frame(lines, typed, cursor_on, False, title)
        typed = min(total_chars, typed + max(1, round(cps / FPS)))
    # hold with blinking cursor on fresh prompt
    hold = int(hold_end * FPS)
    for fi in range(hold):
        yield terminal_frame(lines, total_chars, (fi // cursor_toggle) % 2 == 0, True, title)


def static_frames(img):
    while True:
        yield img


# ---------------------------------------------------------------- scene content
S1 = [("KeeperHub's own scan-to-automate spec stops at the read.", 0)]
S1_QUOTE = [
    ('"Read-only: Yes. No deposit/approve/write node is produced.', 40, WHITE),
    ("The auto-deposit write path is the deferred Phase 999.1", 40, MAGENTA_LIGHT),
    ('backlog item and is out of scope here."', 40, MAGENTA_LIGHT),
    ("KeeperHub — specs/scan-apy-yield-suggestions.md", 24, DIM),
]
S2 = [("PLOW", 0), ("The write path for agent-executed yield", 0), ("policy-gated · sponsored · verified", 0)]

S3_LINES = [
    ([("$ plow scan ", DIM), ("0x1776D4D751d97c85845bF54e6CE364CEc62D4bBf", YELLOW), (" --chain sepolia", DIM)], 0.0),
    ([("✓ ", GREEN), ("read idle ", PURPLE), ("USDC", WHITE), ("     18,000.00", GREEN), ("  @ ", WHITE), ("0x032b4f813F…8dd9", YELLOW)], 0.0),
    ([("→ ", PURPLE), ("1 position(s) on sepolia", WHITE)], 0.0),
    ([("→ ", PURPLE), ("rank venues (defillama yields, live)", WHITE)], 0.0),
    ([("  1. ", YELLOW), ("Mock Spark", WHITE), ("          4.03%", GREEN), ("  apy · DefiLlama live", DIM)], 0.0),
    ([("  2. ", YELLOW), ("Mock Sky Savings", WHITE), ("    3.52%", GREEN), ("  apy · DefiLlama live", DIM)], 0.0),
    ([("  3. ", YELLOW), ("Mock Aave V3", WHITE), ("        3.46%", GREEN), ("  apy · DefiLlama live", DIM)], 0.0),
]

S4_LINES = [
    ([("$ plow deposit ", DIM), ("--venue mock-sky --amount 1000", YELLOW)], 0.0),
    ([("· ", PURPLE), ("gate  venue allowlisted ", WHITE), ("✓", GREEN), ("  simulate: wouldRevert=false ", WHITE), ("✓", GREEN)], 0.0),
    ([("· ", PURPLE), ("approve exact 1,000.00 (no max-uint)   → ", WHITE), ("sponsored ", GREEN), ("0x6724cd07ffd…5a2c", YELLOW)], 2.0),
    ([("· ", PURPLE), ("deposit 1,000.00 → mock-sky            → ", WHITE), ("sponsored ", GREEN), ("0xc137e53fb1a…e6c8", YELLOW)], 2.0),
    ([("✓ ", GREEN), ("verify balanceOf = ", PURPLE), ("2,000.00", GREEN), (" sUSDS · onchain read", WHITE)], 0.0),
    ([("✓ ", GREEN), ("audit  ", PURPLE), ("{decision:ALLOW, gas:sponsored, outcome:landed, ts:…}", WHITE)], 0.0),
]

S5_LINES = [
    ([("$ plow deposit ", DIM), ("--venue unlisted-venue --amount 100", YELLOW)], 0.0),
    ([("✗ ", PINK), ("DENY  ", WHITE), ("venue unlisted-venue disabled", PINK), (" · ", WHITE), ("zero transactions broadcast", PINK)], 0.0),
]

S7 = [("PLOW", 0), ("the write path KeeperHub deferred, executed", 0), ("github.com/subheeksh5599/plow · plow-beta.vercel.app", 0), ("policy-gated · sponsored · verified · audited", 0)]


def main():
    os.makedirs(DEMO, exist_ok=True)
    # rename test audio to s01
    test = os.path.join(DEMO, "tts-test.mp3")
    s01 = os.path.join(DEMO, "s01.mp3")
    if os.path.exists(test) and not os.path.exists(s01):
        os.rename(test, s01)

    scenes = []

    d = scene_duration(os.path.join(DEMO, "s01.mp3"), 8.0)
    img = slate_frame(S1_QUOTE, big=40, mid=24, spacing=18, center_y=400)
    caption(ImageDraw.Draw(img), "KeeperHub's own scan-to-automate spec stops at the read.")
    scenes.append(("s1", static_frames(img), d, "s01"))

    d = scene_duration(os.path.join(DEMO, "s02.mp3"), 6.0)
    img = slate_frame([("PLOW", 150, WHITE), ("The write path for agent-executed yield", 44, TEXT), ("policy-gated · sponsored · verified", 30, PURPLE)], big=150, mid=44, spacing=14, center_y=380)
    caption(ImageDraw.Draw(img), "Plow is the write path. Policy-gated. Sponsored. Verified.")
    scenes.append(("s2", static_frames(img), d, "s02"))

    d = scene_duration(os.path.join(DEMO, "s03.mp3"), 22.0, pad=2.0)
    cap_img, cap_draw = frame_base()
    scenes.append(("s3", typing_frames(S3_LINES, cps=44, hold_end=6.0), d, "s03"))

    d = scene_duration(os.path.join(DEMO, "s04.mp3"), 40.0, pad=2.5)
    scenes.append(("s4", typing_frames(S4_LINES, cps=34, hold_end=9.0), d, "s04"))

    d = scene_duration(os.path.join(DEMO, "s05.mp3"), 14.0, pad=2.0)
    scenes.append(("s5", typing_frames(S5_LINES, cps=30, hold_end=7.0, title="plow — out of policy"), d, "s05"))

    d = scene_duration(os.path.join(DEMO, "s06.mp3"), 24.0, pad=2.0)
    img = evidence_frame()
    caption(ImageDraw.Draw(img), "Six runs. Four sponsored. One denial. Every hash verifies.")
    scenes.append(("s6", static_frames(img), d, "s06"))

    d = scene_duration(os.path.join(DEMO, "s07.mp3"), 12.0, pad=2.0)
    img = slate_frame([("PLOW", 130, WHITE), ("the write path KeeperHub deferred, executed", 38, TEXT), ("github.com/subheeksh5599/plow · plow-beta.vercel.app", 26, PURPLE), ("policy-gated · sponsored · verified · audited", 24, DIM)], big=130, mid=38, spacing=12, center_y=360)
    caption(ImageDraw.Draw(img), "Plow. The write path KeeperHub deferred, executed.")
    scenes.append(("s7", static_frames(img), d, "s07"))

    # render scenes + audio
    total = 0.0
    for name, frames, dur, audio in scenes:
        print(f"render {name}: {dur:.1f}s")
        render_scene(name, frames, dur, os.path.join(DEMO, f"{audio}.mp3"), os.path.join(DEMO, f"p{name}.wav"))
        total += dur

    # concat video
    with open(os.path.join(DEMO, "list.txt"), "w") as f:
        for name, *_ in scenes:
            f.write(f"file 'scene_{name}.mp4'\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(DEMO, "list.txt"), "-c", "copy", os.path.join(DEMO, "video_raw.mp4")], check=True)
    # concat audio
    with open(os.path.join(DEMO, "alist.txt"), "w") as f:
        for name, *_ in scenes:
            f.write(f"file 'p{name}.wav'\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(DEMO, "alist.txt"), "-c", "copy", os.path.join(DEMO, "audio_full.wav")], check=True)
    # mux
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(DEMO, "video_raw.mp4"), "-i", os.path.join(DEMO, "audio_full.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", OUT], check=True)
    print(f"\nDONE: {OUT}  ({total:.1f}s)")


if __name__ == "__main__":
    main()
