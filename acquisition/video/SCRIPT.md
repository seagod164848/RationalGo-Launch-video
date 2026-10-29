# Founder recording script

You record **one master take per vertical** (start with `default`; add `home_services`,
`real_estate`, `d2c` once the default converts). Each take is ~44 s. Everything you say is
used as-is **except the two slots**, which are re-voiced with your ElevenLabs clone and
lip-synced per business.

## How to shoot it

- **9:16, 1080×1920, 30 fps**, phone on a tripod at eye level. Face centred at about 40% of
  frame height (the screen-share section crops a band around it; see `face_center_y`).
- Even, soft front light. No backlight. Lip-sync quality depends mostly on a clear, well-lit mouth.
- **Slots:** say a stand-in name ("Acme Plumbing") at normal pace, then **hold still with
  your mouth closed for a beat**. Don't move your head or hands during a slot window. The
  lip-sync model re-animates the mouth there, so a steady head gives a seamless splice.
- Keep the energy of the words either side of a slot neutral, so any business name fits.
- Record 3–4 takes and keep the best. Then open it in any editor, note the timecodes, and
  update `video/timelines/default.json` (`start`/`end` of each segment).
- Clone your voice once in ElevenLabs (Professional Voice Clone, 30+ min of clean audio of
  you) and put its id in `ELEVENLABS_VOICE_ID`.

## The take (default)

| Time | Type | You say |
|---|---|---|
| 0.0–1.2 | face | "Hey," |
| 1.2–2.9 | **slot `name`** | "**Acme Plumbing**" → becomes *Skull and Homes Company* |
| 2.9–6.4 | face | "I saw you just registered with the state of Connecticut. Congrats. Not a lot of people take the leap into" |
| 6.4–8.6 | **slot `what`** | "**plumbing here in Hartford**" → becomes *plumbing and heating in East Haven* |
| 8.6–10.6 | face | "so I went ahead and built you a website. Let me show you." |
| 10.6–38.0 | screen | *(their site scrolls above you; keep talking to camera)* "Here's your homepage. Your name, your town, a free estimate button front and centre. Here are your services, written for your customers, not for Google. *(~11 s)* This is the part people actually read: what your customers say / your listings / your products. *(~16 s)* Simple packages, and you set the real prices. *(~20 s)* Your story, your license, the stuff that makes people trust you. *(~23 s)* Every town you serve, which is how you show up when someone nearby searches. *(~25 s)* And the contact form goes straight to your phone." |
| 38.0–44.0 | face | "It's yours for four ninety-nine, one time. No monthly fees. I'll put it on your domain this week. Link's right below. Talk soon." |

The screen section must stay generic ("what your customers say / your listings / your
products"), because the same take covers sites with and without reviews. The scroll
timeline jumps to whichever of those sections the site has. Once volume justifies it,
record a `home_services_noreviews` variant (the pipeline picks it automatically when a
lead has no reviews) that says "this is where your reviews will go" instead.
