# Acquisition engine: CT new businesses → personalised site → personalised video → $499 claim

Every morning: pull yesterday's Connecticut business registrations, keep the ~100 that
would actually buy a website, research each one properly, build them a real site, record
a personalised video walking them through it (90% your real footage, only their name and
"what they do" generated), and put it in front of them by email and Instagram.

```
CT registry (data.ct.gov) ──► segment + score ──► enrich ──► dossier (Claude) ──► site ──► video ──► outreach
 ~150–250/day, ~all have      drop holding/       Google     copy, SEO, the      static    master take   email (Instantly)
 a business email             landlord LLCs,      reviews,   two spoken slots,   page per  + 2 lip-sync  + IG catalog retargeting
                              check CT licenses,  founder    founder brief       business  slots + site  + cohort audience
                              pick top 100        research,                                scroll
                                                  Zillow / Shopify
```

## Run it

```bash
cd acquisition
pip install -r requirements.txt          # Node + Playwright + ffmpeg also needed for the video stage
cp .env.example .env                     # fill in whatever keys you have; every stage degrades gracefully
python3 run_daily.py                     # yesterday's registrations, all stages
python3 run_daily.py --day 2026-10-28 --limit 5 --stages ingest,segment,enrich,dossier,site
python3 run_daily.py --lead <ct_business_id> --stages dossier,site,video   # redo one business
```

Outputs land in `out/`: `leads.db` (SQLite, every stage's JSON per lead), `sites/<slug>/`
(the site, `video.mp4`, `poster.jpg`, `preview.gif`, `watch/`), `sites/_feeds/catalog.csv`.
`.github/workflows/acquisition-daily.yml` runs it at 06:00 ET.

**Tested on 28 Oct 2026, with no paid keys:** 141 registrations → 19 dropped as holding/landlord
LLCs → 92 qualified → top 5 run through every stage. See `examples/` for the top lead's site and
video (stand-in footage until you record your master take).

## Stage by stage

### 1. Ingest (`pipeline/ct_data.py`): free, no key
Three public CT datasets via the Socrata API:

| Dataset | What we take |
|---|---|
| `n7gp-d28j` Business Master | name, NAICS code, address, **`business_email_address`** (filled on nearly every new filing) |
| `ka36-64k6` Principals | the people behind it (first/last name, home town), joined on `business_id` |
| `ngch-56tr` DCP Licenses | every state license with **issue date**: plumbing P-1, HIC, electrical, real-estate, hair, CPA... |

The license join is the most valuable signal in the whole pipeline. A brand-new LLC has no
web footprint, but its owner often has decades of licensed history. The top lead on the test
day, *Skull and Homes Company LLC*, had zero Google results, but its owner has held a P-1
unlimited plumbing contractor license since 1999. That's the hook for the site and the video.

### 2. Segment + score (`pipeline/segment.py`)
- **Vertical** from NAICS rules → name keywords → owner's license (vague "Garnet LLC" + active
  HIC = contractor) → one batched Claude Haiku call for the leftovers.
- **Drops** (~30% of filings): lessors of residential buildings, holding companies, "123 Main St
  LLC", trusts, and filings whose email is the lawyer's or the filing service's.
- **Score**: vertical value + active relevant license (+20) + licensed before 2022 (+8, an
  existing operator with history to pull) + free-mail address (+10, no site yet) + local owner;
  minus an existing live website on their email domain (−25). Top 100 with score > 15 are selected.

### 3. Enrich (`pipeline/enrich.py`)
Searches on **both the LLC name and the owner's name**, since the reviews usually belong to the
person's previous sole-proprietorship.

| Source | Used for | Key |
|---|---|---|
| Google Places API (New) | rating, up to 5 reviews, hours, phone, photos | `GOOGLE_PLACES_API_KEY` |
| Serper (Google SERP) | founder history, LinkedIn/IG/FB/Yelp/Zillow profiles, press | `SERPER_API_KEY` |
| Zillow via RapidAPI | **real estate**: the agent's active + sold listings | `ZILLOW_RAPIDAPI_KEY` |
| Shopify `/products.json` | **D2C**: real products, prices, images from their store | none |

Each lead records what was missing (`gaps`), e.g. `no_reviews`, and the site and video adapt to it.

### 4. Dossier (`pipeline/dossier.py`): Claude
One structured call per lead produces: hero copy, services, 3 packages, service-area towns,
trust points, FAQ, SEO title/description/keywords, theme, **`spoken_name`** and
**`what_they_do_spoken`** (the two video slots), and a private **founder brief** with the
personal angle for outreach. Rules baked in:
- Facts only from the data. Testimonials must be verbatim and are **re-verified against the
  source reviews in code**; anything paraphrased is dropped.
- Vertical playbooks: home services → licensed/insured, free estimates, emergency; real estate →
  listings, buyer/seller paths; D2C → products and story; food → menu, hours; beauty → booking.

`examples/skull-and-homes-company.dossier.json` shows the target quality.

### 5. Site (`pipeline/site_builder.py`, `templates/site.html.j2`)
One static, fast, mobile-first page per business, with sections that appear only when the data exists
(reviews, Zillow listings, Shopify products, packages, hours). SEO:
- `<title>`/meta/keywords/OG/geo tags from the dossier; service × town copy in the footer.
- JSON-LD: the right schema.org subtype (`Plumber`, `RealEstateAgent`, `Store`...) with
  address, `areaServed`, `hasOfferCatalog`, `sameAs` socials, plus `FAQPage`.
- No self-served `aggregateRating`, which Google ignores and can penalise.
- **Previews are `noindex`** (meta + `X-Robots-Tag` + robots.txt) until claimed, so we never
  outrank or impersonate the business in search. Indexing switches on when it moves to their domain.

All sites deploy as one Cloudflare Pages project: `preview.yourdomain.com/<slug>/`.

### 6. Video (`pipeline/video.py`, `video/SCRIPT.md`, `video/timelines/*.json`)
You record **one ~44 s master take per vertical** (script in `video/SCRIPT.md`). The timeline
marks three kinds of segment:

| Segment | What happens |
|---|---|
| `face` | your take, untouched |
| `slot` | ElevenLabs (your cloned voice) says the business name / what they do, with the surrounding sentence passed as context so the intonation matches. sync.so `lipsync-2` re-animates your mouth on that window only, and the name is captioned on screen |
| `screen` | their site scrolls in the top 60% while you talk in the bottom 40%. Scroll keyframes target section ids, so "this is where your reviews are" lands on reviews, or on listings or products if that's what this site has |

The site is captured as one tall phone-width screenshot (Playwright) and scrolled with ffmpeg,
which is sharp and deterministic. Outputs: `video.mp4` (1080×1920), `poster.jpg`, and a
3-second `preview.gif` for email. With no ElevenLabs/sync.so keys, slots fall back to your
raw take plus a caption, so you can preview the edit for free.

### 7. Outreach (`pipeline/outreach.py`)
**An Instagram ad per business isn't possible.** Meta won't deliver to a custom audience
smaller than ~100 matched people, and there's no way to pin a creative to one person in an
uploaded list. So the delivery is:

1. **Email, the 1:1 channel.** Each lead is pushed to an Instantly campaign with variables
   `{{watch_url}}`, `{{gif_url}}`, `{{site_url}}`, `{{town}}`. The watch page has their video,
   their site and the $499 Stripe button. Instantly is used because SES/Resend-style senders
   forbid cold email. Copy is below.
2. **Instagram retargeting with *their own* video.** Every lead is an item in a Meta catalog
   (`_feeds/catalog.csv`, a scheduled feed) whose `video[0].url` is their personalised video.
   The pixel on their site and watch page fires `ViewContent` with their lead id, so an
   Advantage+ catalog ad retargets each visitor with the item they viewed, which is their own
   video. This is how the Instagram half of the idea works within Meta's rules.
3. **Cohort prospecting.** Hashed emails, names and ZIPs go to one rolling custom audience
   (`upload_audience`). Run a generic "We already built a website for your new CT business,
   check your inbox" ad to it.

#### Email copy (paste into the Instantly campaign)
> **Subject:** {{firstName}}, I built {{companyName}} a website
>
> Hi {{firstName}},
>
> Saw {{companyName}} just registered with the state. Congrats. I put together a site for you
> and recorded a quick walkthrough:
>
> [![preview]({{gif_url}})]({{watch_url}})
>
> It's already built for {{personalization}}. If you like it, it's yours for $499 one-time,
> on your domain this week. If not, no worries; just ignore this.
>
> Varun
>
> *Reply "no thanks" and I won't email again. {{postal_address}}*

Follow-ups: day 3 (bump with the site link), day 7 (bump with one specific detail from the dossier).

## What you need to set up

| # | Thing | Why |
|---|---|---|
| 1 | Record the master take (`video/SCRIPT.md`), replace `video/master/default.mp4`, re-mark `timelines/default.json` | the 90% that's really you |
| 2 | ElevenLabs Professional Voice Clone → `ELEVENLABS_VOICE_ID` | the name slots |
| 3 | sync.so API key | lip-sync |
| 4 | Anthropic key | dossier + segmentation |
| 5 | Google Places key, Serper key, (RapidAPI Zillow for realtors) | depth of research |
| 6 | Cloudflare Pages project on `preview.<yourdomain>` | hosting sites and videos (lipsync fetches by URL) |
| 7 | Stripe Payment Link for $499 (pass-through `client_reference_id` = lead id) | the claim button |
| 8 | Instantly account + 3–5 warmed secondary sending domains (~30 emails/inbox/day) | 100 emails a day without burning your main domain |
| 9 | Meta pixel, catalog (scheduled feed → `/_feeds/catalog.csv`), ad account token | IG retargeting + cohort ads |
| 10 | `POSTAL_ADDRESS` | CAN-SPAM requires it in every email |

## Things to watch

- **Reviews are usually missing** for day-old LLCs. The pipeline searches by owner name too and
  stays honest when nothing turns up. Record a `<vertical>_noreviews` master once volume allows.
- **Google reviews** are shown with attribution and a link back to Google, per the Places API
  terms. Refresh before handover; don't cache them indefinitely.
- **Zillow** has no public API. The RapidAPI wrapper is a third party, so check its terms. Long term,
  pull via the agent's MLS/IDX feed once they claim the site.
- **Sample pricing** is clearly labelled on previews; the owner sets real prices on claim.
- **Unsubscribes** go in `out/suppression.txt` (checked before every send). Sync it with Instantly's.
- **Video costs** scale with lip-sync seconds (~4 s per lead); everything else is per-call pennies.

## Next to build
- Claim fulfilment: Stripe webhook → mark `claimed_at` → remove the banner, flip to `index`,
  connect their domain, generate per-service and per-town landing pages for SEO.
- Weekend backfill: carry unselected qualified leads into the next day's 100.
- Reply handling: route Instantly replies to you with the lead's founder brief attached.
