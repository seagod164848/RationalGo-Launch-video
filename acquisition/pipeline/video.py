"""Personalised 9:16 video: ~90% your real recording, ~10% generated.

Inputs
  video/master/<vertical>.mp4   one real take per vertical (fallback: default.mp4), recorded per video/SCRIPT.md
  video/timelines/<vertical>.json   where the slots and screen-share windows are in that take

Segment types in a timeline
  face    : your recording, untouched
  slot    : your recording, mouth re-synced to new audio (cloned voice says the business name / what they do)
  screen  : their site scrolling on top, your recording (face crop) underneath; audio is your real take

Without ELEVENLABS/SYNC keys, slots fall back to your untouched take with the text burned in as a
caption, so the whole edit can be previewed for free.
"""
import json
import shutil
import subprocess
import time
from pathlib import Path

import requests

from . import config

ROOT = config.ROOT / "video"
W, H, FPS = 1080, 1920, 30
FONT = next((p for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                         "/System/Library/Fonts/Supplemental/Arial Bold.ttf") if Path(p).exists()), None)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def ffmpeg(*args):
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args])


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def timeline_for(vertical, has_reviews):
    for name in (f"{vertical}{'' if has_reviews else '_noreviews'}", vertical, "default"):
        p = ROOT / "timelines" / f"{name}.json"
        if p.exists():
            tl = json.loads(p.read_text())
            tl["master"] = str(ROOT / tl["master"])
            return tl
    raise FileNotFoundError("video/timelines/default.json missing")


ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
FILL = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"


# ---------------------------------------------------------------- slots: cloned voice + lipsync
def tts(text, prev_text, next_text, dest):
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": config.ELEVENLABS_API_KEY},
        # previous/next text make the phrase land with the same intonation as the surrounding real speech
        json={"text": text, "model_id": "eleven_multilingual_v2", "previous_text": prev_text, "next_text": next_text,
              "voice_settings": {"stability": 0.5, "similarity_boost": 0.9, "style": 0.2}},
        timeout=60,
    )
    r.raise_for_status()
    dest.write_bytes(r.content)


def public_url(path):
    base = config.PUBLIC_ASSET_BASE or config.PREVIEW_BASE_URL
    return f"{base.rstrip('/')}/{Path(path).relative_to(config.OUT / 'sites').as_posix()}"


def lipsync_submit(video_url, audio_url):
    r = requests.post("https://api.sync.so/v2/generate", headers={"x-api-key": config.SYNC_API_KEY}, json={
        "model": config.SYNC_MODEL,
        "input": [{"type": "video", "url": video_url}, {"type": "audio", "url": audio_url}],
        "options": {"sync_mode": "bounce"},  # audio longer than the window: ping-pong the video instead of freezing
    }, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


def lipsync_wait(job_id, dest, timeout_s=900):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        j = requests.get(f"https://api.sync.so/v2/generate/{job_id}", headers={"x-api-key": config.SYNC_API_KEY},
                         timeout=30).json()
        if j["status"] == "COMPLETED":
            dest.write_bytes(requests.get(j["outputUrl"], timeout=120).content)
            return True
        if j["status"] in ("FAILED", "REJECTED", "CANCELED"):
            raise RuntimeError(f"lipsync {job_id}: {j.get('error')}")
        time.sleep(10)
    raise TimeoutError(job_id)


def slot_texts(tl, dossier):
    return {s["key"]: s["text"].format(**dossier) for s in tl["segments"] if s["type"] == "slot"}


def master_slot_clip(tl, seg):
    """The untouched window from the master take; identical for every lead, so cut and host once."""
    d = config.OUT / "sites" / "_assets" / "master" / Path(tl["master"]).stem
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{seg['key']}_{seg['start']:.2f}.mp4"
    if not p.exists():
        ffmpeg("-ss", str(seg["start"]), "-to", str(seg["end"]), "-i", tl["master"], "-vf", FILL, *ENC, str(p))
    return p


def prepare_slots(lead, tl):
    """Step 1 (before deploy): write the TTS audio so the lipsync API can fetch it by URL."""
    if not (config.ELEVENLABS_API_KEY and config.ELEVENLABS_VOICE_ID and config.SYNC_API_KEY):
        return []
    adir = config.OUT / "sites" / "_assets" / lead["slug"]
    adir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for seg in tl["segments"]:
        if seg["type"] != "slot":
            continue
        text = seg["text"].format(**lead["dossier"])
        audio = adir / f"{seg['key']}.mp3"
        tts(text, seg.get("prev_text", ""), seg.get("next_text", ""), audio)
        jobs.append({"key": seg["key"], "audio": audio, "master": master_slot_clip(tl, seg)})
    return jobs


def run_lipsync(lead, jobs):
    """Step 2 (after deploy): submit all slots in parallel, then wait."""
    vdir = config.OUT / "video" / lead["slug"]
    vdir.mkdir(parents=True, exist_ok=True)
    ids = [(j, lipsync_submit(public_url(j["master"]), public_url(j["audio"]))) for j in jobs]
    out = {}
    for j, job_id in ids:
        dest = vdir / f"slot_{j['key']}.mp4"
        lipsync_wait(job_id, dest)
        out[j["key"]] = dest
    return out


# ---------------------------------------------------------------- screen-share: their site, scrolling
def capture(lead):
    vdir = config.OUT / "video" / lead["slug"]
    vdir.mkdir(parents=True, exist_ok=True)
    png = vdir / "site.png"
    run(["node", str(Path(__file__).parent / "capture_site.mjs"),
         str(config.OUT / "sites" / lead["slug"] / "index.html"), str(png)])
    return png, json.loads(png.with_suffix(".sections.json").read_text())


def scroll_expr(keyframes, sections, view_h, move=0.9):
    """ffmpeg crop-y expression: hold on each section, ease to the next over `move` seconds.
    Keyframes naming a section this site doesn't have are skipped, so the same timeline works
    whether or not the business has reviews/listings/products."""
    max_y = sections["__height"] - view_h
    pts = []
    for k in keyframes:
        if pts and k["t"] == pts[-1][0]:
            continue  # alternatives at the same moment (listings / shop / reviews): first one present wins
        if k["section"] in sections:
            pts.append((k["t"], max(0, min(max_y, sections[k["section"]] + k.get("offset", 0)))))
    if not pts:
        pts = [(0, 0)]
    expr = str(pts[-1][1])
    for (t0, y0), (t1, y1) in reversed(list(zip(pts, pts[1:]))):
        # smoothstep between t1-move and t1, holding y0 before that
        a = f"clip((t-{t1 - move:.3f})/{move},0,1)"
        ease = f"({a}*{a}*(3-2*{a}))"
        expr = f"if(lt(t,{t1:.3f}),{y0}+({y1}-{y0})*{ease},{expr})"
    return f"if(lt(t,{pts[0][0]:.3f}),{pts[0][1]},{expr})"


def render_screen(tl, seg, png, sections, dest):
    site_h = seg.get("site_height", 1180)
    face_h = H - site_h
    dur = seg["end"] - seg["start"]
    y = scroll_expr(seg.get("scroll", [{"t": 0, "section": "hero"}]), sections, site_h)
    fy = seg.get("face_center_y", 0.42)  # where your face sits in the master frame (0..1)
    graph = (
        f"[0:v]crop={W}:{site_h}:0:'{y}',setsar=1[site];"
        f"[1:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
        f"crop={W}:{face_h}:0:'max(0,min({H}-{face_h},{H}*{fy}-{face_h}/2))',setsar=1[face];"
        f"[site][face]vstack=inputs=2,drawbox=y={site_h - 3}:w={W}:h=6:color=white@0.9:t=fill[v]"
    )
    ffmpeg("-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(png),
           "-ss", str(seg["start"]), "-to", str(seg["end"]), "-i", tl["master"],
           "-filter_complex", graph, "-map", "[v]", "-map", "1:a", "-t", f"{dur:.3f}", *ENC, str(dest))


def _caption(text, workdir):
    """Name/what-they-do burned in under your face. Text goes via a file: commas, quotes and
    colons in business names would otherwise break the filtergraph."""
    if not FONT:
        return ""
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + len(word) > 22:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    lines.append(cur)
    f = Path(workdir) / f"caption_{abs(hash(text))}.txt"
    f.write_text("\n".join(lines))
    return (f",drawtext=fontfile={FONT}:textfile={f}:fontsize=62:line_spacing=14:fontcolor=white:borderw=5:"
            f"bordercolor=black@0.7:x=(w-text_w)/2:y=h*0.70")


def compose(lead, synced=None):
    """Cut every segment to an identical format, then concat."""
    d = lead["dossier"]
    has_reviews = bool(d.get("testimonials"))
    tl = timeline_for(lead["vertical"], has_reviews)
    vdir = config.OUT / "video" / lead["slug"]
    parts_dir = vdir / "parts"
    shutil.rmtree(parts_dir, ignore_errors=True)
    parts_dir.mkdir(parents=True)
    png, sections = capture(lead)
    texts = slot_texts(tl, d)
    parts = []
    for i, seg in enumerate(tl["segments"]):
        dest = parts_dir / f"{i:02d}.mp4"
        if seg["type"] == "screen":
            render_screen(tl, seg, png, sections, dest)
        elif seg["type"] == "slot" and synced and seg["key"] in synced:
            cap = _caption(texts[seg["key"]], parts_dir) if seg.get("caption", True) else ""
            ffmpeg("-i", str(synced[seg["key"]]), "-vf", FILL + cap, *ENC, str(dest))
        else:
            vf = FILL + (_caption(texts[seg["key"]], parts_dir) if seg["type"] == "slot" else "")
            ffmpeg("-ss", str(seg["start"]), "-to", str(seg["end"]), "-i", tl["master"], "-vf", vf, *ENC, str(dest))
        parts.append(dest)
    lst = parts_dir / "concat.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
    final = config.OUT / "sites" / lead["slug"] / "video.mp4"
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(final))
    _poster_and_gif(final, tl)
    return final


def _poster_and_gif(final, tl):
    """Poster frame + a 3s GIF for the email (GIFs autoplay in Gmail; video doesn't)."""
    first_screen = next((s for s in tl["segments"] if s["type"] == "screen"), None)
    start = sum(s["end"] - s["start"] for s in tl["segments"][:tl["segments"].index(first_screen)]) + 1.5 \
        if first_screen else 1.0
    ffmpeg("-ss", f"{start:.2f}", "-i", str(final), "-frames:v", "1", "-vf", "scale=720:-2", str(final.with_name("poster.jpg")))
    ffmpeg("-ss", f"{start:.2f}", "-t", "3", "-i", str(final), "-vf",
           "fps=12,scale=360:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer",
           "-loop", "0", str(final.with_name("preview.gif")))
