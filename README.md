# RationalGo launch film: "Before Sunrise"

A ~75s film about **Maya**, a New Yorker who gets an idea outside an apparel store in Times Square and starts her clothing brand **ALBA** with R.go. The film follows her day, not the software; R.go shows up only as glances at a laptop or a buzzing phone.

| Path | What |
|------|------|
| `story/SCRIPT.md` | Character, beat sheet, VO, screen-capture shot list |
| `edit/manifest.json` | Timeline: every shot, its keyframe, generated clip URL, and the prompt used |
| `edit/assemble.py` | Downloads the clips and cuts `edit/out/before_sunrise_roughcut.mp4` (needs `ffmpeg` + `pip install pillow`) |
| `edit/animatic.html` | Plays the timeline in a browser straight from the generated URLs (`python3 -m http.server`, then open `/edit/animatic.html`) |
| `screens/mock.html` | Mock R.go screens (`?scene=prompt\|site\|suppliers\|book\|social`) |
| `screens/renders/` | Those mock screens recorded to 1080p mp4 plus stills |

## Make the rough cut

```bash
python3 edit/assemble.py
```

Hailuo video URLs expire about **9 hours** after generation, and Gemini keyframe URLs about **7 days** after. If they have expired, regenerate them with the prompts in `edit/manifest.json` (see `treg call` in each entry).

The Runway Gen-4.5 establishing shot (`gen-vid-1790612870-TU1RaCA4bp5G8fjHrt14`) is only reachable with an authenticated retrieve call:

```bash
treg call openrouter.video-gen.result.retrieve --method GET --data '{"id":"gen-vid-1790612870-TU1RaCA4bp5G8fjHrt14"}' > edit/out/clips/runway_timessq.mp4
```

## Swapping in real screen flows

Each mock in `screens/renders/*.mp4` is a stand-in for a real capture from rationalgo.ai. To swap one in, record the flow (shot list in `story/SCRIPT.md`) at 16:9, save it over the matching file in `screens/renders/`, and re-run `assemble.py`.

## Still to do
- Real R.go screen captures that replace the mocks.
- Voice-over record (5 lines, in `SCRIPT.md`) and a music bed (sparse piano).
- Grade pass so the AI shots and screen shots sit in the same palette.
