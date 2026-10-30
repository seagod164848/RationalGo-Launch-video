# Showcase video

`showcase.mp4`: 40 s, 1080×1920 (Reels/Stories), silent. Add a music bed in CapCut or Canva.

Scenes: 186 CT registrations yesterday → holding LLCs filtered → top 100 → research card
(license since 1999, no reviews, no site) → their site scrolling with callouts → personalised
video with the 90% real / 10% AI timeline → inbox + Instagram → "Claim it · $499" → "Claimed ✓"
→ "100 personalised websites. Every morning."

The hero business, *Shoreline Pipe & Heat / Mike Russo*, is **fictional** (the site is a real
pipeline render with the names swapped). Don't put a real lead's name in public marketing
without their consent. The scrolling names in scene 2 are real public filings from 28 Oct 2026.

Re-render after editing `showcase.html` (each frame is a pure function of `render(t)`):

```bash
node render.js 30 && ffmpeg -y -framerate 30 -i frames/%04d.jpg -c:v libx264 -crf 18 -pix_fmt yuv420p -movflags +faststart showcase.mp4
node render.js 30 7.5 22.5   # just stills at those times, into stills/
```

## Same piece in Claude Motion

Paste this into Claude Motion, attach `site.png` (the tall site screenshot), and send the export
to Canva from there:

> 40-second vertical (9:16) product showcase for RationalGo, dark navy background (#0b0d10 → #16202c),
> warm yellow accent (#ffc857), serif headlines (Fraunces) and Inter body. Six scenes:
> 1. (0–4.5s) Eyebrow "YESTERDAY IN CONNECTICUT"; a huge number counts 0 → 186; "new businesses registered." then "Every single one with an email on file."
> 2. (4.5–10s) ~28 business-name pills drift upward in two columns. Headline "186 names." → "Landlords & holding LLCs out." (7 pills get struck through and fade) → "Top 100 make the cut." (one pill, "Shoreline Pipe & Heat LLC", turns yellow and grows).
> 3. (10–16s) "Step 1 · Research / We study them like a client." A card "Shoreline Pipe & Heat LLC, East Haven, CT" then five fact rows slide in: Owner: Mike Russo · CT P-1 Plumbing Contractor: since 1999 · Heating & cooling license: since 1996 · Google reviews: none yet · Website: none. Then: "27 years on the tools. Now it's his name on the truck."
> 4. (16–23s) "Step 2 · Build / Then we build their website." A phone rises; inside, the attached site screenshot scrolls hero → services → packages → about → service area. Yellow sticker labels pop on: "Their services", "Claim it · $499", "Local SEO + schema", "Real towns they serve".
> 5. (23–30s) "Step 3 · Video / And record a video just for them." Phone split: site on top, founder on the bottom; a caption types out "Shoreline Pipe & Heat". Under it a timeline bar, mostly grey with two short yellow slots: "90% real you · 10% their name, AI lip-synced".
> 6. (30–35.5s) "Step 4 · Deliver / It lands in their inbox and their feed." An email card ("Mike, I built Shoreline Pipe & Heat a website") then an Instagram Sponsored card ("Your video, retargeted to you"). A yellow pill button "Claim it · $499" gets pressed and turns green: "Claimed ✓".
> End (35.5–40s): "100 personalised websites. Every morning." (second line in yellow), small "RationalGo" below.
> Motion: smooth ease-out entrances, 0.4s fades, no hard cuts, upbeat minimal electronic music at 112 bpm.
