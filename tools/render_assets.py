#!/usr/bin/env python3
"""Optional maintainer artwork tool. Requires Pillow; the toolkit itself does not."""
from pathlib import Path
import subprocess
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def font(size, bold=False, mono=False):
    candidates = (["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"] if mono else
                  ["C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def main():
    ASSETS.mkdir(exist_ok=True)
    canvas = Image.new("RGB", (1280, 640), "#f3f0e8")
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((50, 44, 118, 112), radius=18, fill="#e16b34")
    d.text((64, 55), ">_", font=font(32, True), fill="#fff9f0")
    d.text((140, 65), "A SMALL STARTER FOR CODING AGENTS", font=font(22, True), fill="#595e58")
    d.text((58, 146), "New project.", font=font(79, True), fill="#192e29")
    d.text((58, 238), "Less deja vu.", font=font(79, True), fill="#192e29")
    d.text((63, 355), "One prompt. Shared context. Verifiable work.", font=font(26), fill="#58635d")
    cards = [("01", "SHARED MEMORY", "Resume with the current state."),
             ("02", "HONEST CHECKS", "A failed check stays a failure."),
             ("03", "LESSONS THAT EXPIRE", "Retire advice when it goes stale.")]
    for i, (number, title, subtitle) in enumerate(cards):
        y = 145 + i * 105
        d.rounded_rectangle((777, y, 1220, y + 88), radius=15, fill="#ffffff")
        d.text((797, y + 17), number, font=font(26, True), fill="#c65e2e")
        d.text((850, y + 16), title, font=font(20, True), fill="#192e29")
        d.text((850, y + 47), subtitle, font=font(18), fill="#58635d")
    d.rounded_rectangle((50, 463, 1230, 588), radius=22, fill="#192e29")
    d.text((80, 483), "Agent Project Starter", font=font(48, True), fill="#fff9f0")
    d.text((84, 548), "PYTHON STANDARD LIBRARY  /  EN + ZH  /  MIT", font=font(17, True), fill="#a7c7b7")
    canvas.save(ASSETS / "social-preview.png", optimize=True)

    result = subprocess.run([sys.executable, str(ROOT / "tools/demo.py")], text=True, encoding="utf-8",
                            capture_output=True, timeout=30, check=True)
    lines = result.stdout.strip().splitlines()
    frames = []
    for visible in range(1, len(lines) + 1):
        frame = Image.new("RGB", (1080, 540), "#10241f")
        draw = ImageDraw.Draw(frame)
        draw.rounded_rectangle((20, 20, 1060, 520), radius=18, fill="#172f29")
        for x, color in [(45, "#f27d72"), (68, "#e8c46a"), (91, "#73c6a2")]:
            draw.ellipse((x, 41, x + 12, 53), fill=color)
        draw.text((127, 35), "OFFLINE DEMO / ACTUAL COMMAND OUTPUT", font=font(16, True), fill="#afcbbf")
        draw.text((47, 87), "$ python3 tools/demo.py", font=font(22, mono=True), fill="#ffffff")
        y = 135
        for line in lines[:visible]:
            for wrapped in textwrap.wrap(line, width=90):
                draw.text((47, y), wrapped, font=font(18, mono=True), fill="#a4e4bd" if "passed" in line else "#d9e5df")
                y += 26
            y += 10
        draw.text((47, 482), "Disposable project. No API keys. No installs. No network.", font=font(17), fill="#98b9aa")
        frames.append(frame)
    frames[0].save(ASSETS / "demo.gif", save_all=True, append_images=frames[1:],
                   duration=[1100] * (len(frames) - 1) + [3500], loop=0, optimize=True)
    print("Rendered original banner and replay of the verified demo output.")


if __name__ == "__main__":
    main()
