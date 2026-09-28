#!/usr/bin/env python3
"""Download every generated clip and cut the rough edit.

Usage:  python3 edit/assemble.py          (needs ffmpeg on PATH and `pip install pillow`)
Output: edit/out/before_sunrise_roughcut.mp4

Generated media URLs expire (Hailuo ~9h, Gemini ~7d), so run this soon after
generation or re-generate from the prompts in edit/manifest.json.
"""
import json
import pathlib
import subprocess
import urllib.request

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "edit" / "out"
CLIPS = OUT / "clips"
W, H, FPS = 1920, 1080, 24


def run(*args):
    subprocess.run(args, check=True)


def fetch(url, dest):
    if not dest.exists():
        print("↓", dest.name)
        urllib.request.urlretrieve(url, dest)
    return dest


def normalise(src, dest, seconds, fade_in=0.4, fade_out=0.4):
    """Scale/crop to 1080p, fixed fps, trimmed, with short fades so hard cuts breathe."""
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
        f"fade=t=in:st=0:d={fade_in},fade=t=out:st={seconds - fade_out}:d={fade_out},format=yuv420p"
    )
    run("ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-t", str(seconds),
        "-vf", vf, "-an", "-c:v", "libx264", "-crf", "18", str(dest))


def font(size):
    for name in ("Inter-Regular.ttf", "Helvetica.ttc", "Arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def notification_png(text, dest):
    """A phone-style notification card: R.go working in the background of her day."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = W - 820, 60, W - 60, 190
    d.rounded_rectangle((x0, y0, x1, y1), radius=28, fill=(22, 24, 28, 215))
    d.text((x0 + 36, y0 + 26), "R.go", font=font(26), fill=(255, 122, 69))
    d.text((x0 + 36, y0 + 66), text, font=font(32), fill=(245, 245, 245))
    img.save(dest)


def caption(src, dest, text):
    card = dest.with_suffix(".png")
    notification_png(text, card)
    run("ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-loop", "1", "-i", str(card),
        "-filter_complex", "[1]format=rgba,fade=t=in:st=0.6:d=0.3:alpha=1[n];[0][n]overlay=0:0:shortest=1",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(dest))


def end_card(dest, line, url, seconds):
    img = Image.new("RGB", (W, H), "black")
    d = ImageDraw.Draw(img)
    for text, f, fill, y in ((line, font(56), "white", H // 2 - 70), (url, font(40), (255, 122, 69), H // 2 + 20)):
        d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)
    png = dest.with_suffix(".png")
    img.save(png)
    run("ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(png), "-t", str(seconds),
        "-vf", f"fps={FPS},fade=t=in:st=0:d=0.8,format=yuv420p", "-c:v", "libx264", "-crf", "18", str(dest))


def main():
    manifest = json.loads((ROOT / "edit" / "manifest.json").read_text())
    CLIPS.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, shot in enumerate(manifest["timeline"]):
        name = f"{i:02d}_{shot['id']}"
        if shot["kind"] == "optional":
            raw = ROOT / shot["file"]
            if not raw.exists():
                print("– skipping", shot["id"], "(not downloaded)")
                continue
        elif shot["kind"] == "screen":
            raw = ROOT / shot["file"]
        else:
            raw = fetch(shot["video_url"], CLIPS / f"{name}_raw.mp4")
        norm = CLIPS / f"{name}.mp4"
        normalise(raw, norm, shot["seconds"])
        if shot.get("notification"):
            capped = CLIPS / f"{name}_cap.mp4"
            caption(norm, capped, shot["notification"])
            norm = capped
        parts.append(norm)

    end = CLIPS / "99_end.mp4"
    card = manifest["end_card"]
    end_card(end, card["line"], card["url"], card["seconds"])
    parts.append(end)

    listfile = OUT / "concat.txt"
    listfile.write_text("".join(f"file '{p}'\n" for p in parts))
    final = OUT / "before_sunrise_roughcut.mp4"
    run("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listfile),
        "-c", "copy", str(final))
    print("✓", final)


if __name__ == "__main__":
    main()
