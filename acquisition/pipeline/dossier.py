"""Turns raw registry + enrichment into the one document everything downstream reads:
site copy, SEO, the two spoken video slots, and a private brief for the founder.

Hard rule: no invented facts. Testimonials are re-checked against the source review
text after the model returns, and anything not found verbatim is dropped.
"""
import json

from . import config
from .enrich import brand_name

THEMES = ["harbor", "forest", "terracotta", "charcoal", "blush", "slate"]
SCHEMA_TYPES = {
    "home_services": "HomeAndConstructionBusiness", "real_estate": "RealEstateAgent", "beauty_wellness": "HealthAndBeautyBusiness",
    "food": "FoodEstablishment", "d2c": "Store", "auto": "AutomotiveBusiness", "health": "MedicalBusiness",
    "events_creative": "ProfessionalService", "professional": "ProfessionalService", "logistics": "LocalBusiness",
    "other": "LocalBusiness",
}

DOSSIER_TOOL = {
    "name": "write_dossier",
    "description": "Structured research dossier and website copy for one business.",
    "input_schema": {
        "type": "object",
        "required": ["spoken_name", "what_they_do_spoken", "hero_headline", "hero_sub", "about", "services",
                     "service_areas", "trust_points", "testimonials", "faq", "seo", "theme", "founder_brief",
                     "confidence"],
        "properties": {
            "spoken_name": {"type": "string", "description": "Business name as a person would say it aloud, no LLC/Inc."},
            "what_they_do_spoken": {"type": "string", "description": "<= 8 words, said in the video right after the name, "
                                    "e.g. 'pressure washing here in New London'. Natural speech, no jargon."},
            "hero_headline": {"type": "string", "description": "<= 9 words. Specific to what they do and where."},
            "hero_sub": {"type": "string", "description": "1 sentence."},
            "about": {"type": "string", "description": "2 short paragraphs, only from facts provided. Mention the "
                      "owner by first name if known. No invented history."},
            "services": {"type": "array", "items": {"type": "object", "required": ["name", "description"], "properties": {
                "name": {"type": "string"}, "description": {"type": "string"}}}},
            "packages": {"type": "array", "description": "3 packages (good/better/best) with realistic CT market "
                         "starting prices. They are labelled as sample pricing on the preview.",
                         "items": {"type": "object", "required": ["name", "price", "includes"], "properties": {
                             "name": {"type": "string"}, "price": {"type": "string"},
                             "includes": {"type": "array", "items": {"type": "string"}},
                             "featured": {"type": "boolean"}}}},
            "service_areas": {"type": "array", "items": {"type": "string"},
                              "description": "Their town plus 5-8 real neighbouring CT towns they would plausibly serve."},
            "trust_points": {"type": "array", "items": {"type": "string"},
                             "description": "Only verifiable facts: license + year, Google rating, years active, owner-operated, etc."},
            "testimonials": {"type": "array", "description": "Up to 4 VERBATIM excerpts (one or two sentences) copied "
                             "exactly from the reviews provided. Empty if no reviews.",
                             "items": {"type": "object", "required": ["quote", "author", "source"], "properties": {
                                 "quote": {"type": "string"}, "author": {"type": "string"},
                                 "rating": {"type": "number"}, "source": {"type": "string"}}}},
            "review_themes": {"type": "array", "items": {"type": "string"},
                              "description": "What customers consistently praise, 2-4 words each. Empty if no reviews."},
            "faq": {"type": "array", "items": {"type": "object", "required": ["q", "a"], "properties": {
                "q": {"type": "string"}, "a": {"type": "string"}}}},
            "seo": {"type": "object", "required": ["title", "meta_description", "keywords"], "properties": {
                "title": {"type": "string", "description": "<= 60 chars, service + town + brand"},
                "meta_description": {"type": "string", "description": "<= 155 chars"},
                "keywords": {"type": "array", "items": {"type": "string"}, "description": "8-15 local-intent keywords"}}},
            "theme": {"type": "string", "enum": THEMES},
            "founder_brief": {"type": "string", "description": "Private notes for the founder: who these people are, "
                              "what they did before, the sharpest personal angle for outreach. Cite sources."},
            "confidence": {"type": "number", "description": "0-1: how sure we are what this business actually does."},
        },
    },
}

PROMPT = """You are researching a Connecticut business that registered with the Secretary of State on {day}.
We are building them a website as a gift preview, which they can claim for ${price}. The site has to feel like we
truly understand their business: their actual services, their towns, what their customers say about them.

Rules:
- Use ONLY facts in the data below. If something is unknown, leave it out rather than guess.
- Testimonials must be copied verbatim from the review texts provided. Never write or paraphrase one.
- Services: if the data shows what they actually do, use that. Otherwise list the standard services for
  their NAICS category, phrased plainly; the owner edits them after claiming.
- Write for their customers, not for them. Local, warm, specific. No buzzwords ("elevate", "seamless", "unparalleled").
- Vertical-specific: home services -> emergency/response time, licensed & insured, free estimates. Real estate ->
  neighbourhoods, recent listings/sales, buyer + seller paths. D2C -> products and brand story. Food -> menu,
  hours, location. Beauty -> services menu and booking.

DATA:
{data}"""


def build(lead):
    reg = lead["registry"]
    enr = lead.get("enrichment") or {}
    payload = {
        "legal_name": lead["name"],
        "vertical": lead["vertical"],
        "naics": reg.get("naics_code"),
        "address": reg.get("mailing_address"),
        "town": enr.get("town"),
        "owners": lead.get("principals"),
        "licenses": lead.get("licenses"),
        "ownership_flags": {k: reg.get(k) for k in ("woman_owned_organization", "veteran_owned_organization",
                                                     "minority_owned_organization")},
        "google_business_profile": enr.get("google"),
        "web_research": enr.get("research"),
        "socials": enr.get("socials"),
        "zillow": enr.get("zillow"),
        "products": enr.get("products"),
    }
    if config.ANTHROPIC_API_KEY:
        d = _claude(lead, payload)
    else:
        d = _fallback(lead, payload)
    d["schema_type"] = SCHEMA_TYPES.get(lead["vertical"], "LocalBusiness")
    d["testimonials"] = _verified_testimonials(d.get("testimonials", []), enr.get("google", {}).get("reviews", []))
    return d


def _claude(lead, payload):
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=config.DOSSIER_MODEL,
        max_tokens=8000,
        tools=[DOSSIER_TOOL],
        tool_choice={"type": "tool", "name": "write_dossier"},
        messages=[{"role": "user", "content": PROMPT.format(
            day=lead["registered_on"], price=config.CLAIM_PRICE_USD, data=json.dumps(payload, indent=1, default=str))}],
    )
    return next(b for b in msg.content if b.type == "tool_use").input


def _verified_testimonials(items, reviews):
    corpus = [" ".join((r.get("text") or "").split()) for r in reviews]
    keep = []
    for t in items:
        q = " ".join(t.get("quote", "").strip().strip('"“”').split())
        if q and any(q.rstrip(".…") in c for c in corpus):
            keep.append({**t, "quote": q})
    return keep


# ---------------------------------------------------------------- no-LLM fallback (keeps the pipeline runnable)
GENERIC_SERVICES = {
    "home_services": [("Free on-site estimates", "We come out, look at the job and give you a written price."),
                      ("Repairs", "Fast fixes done right the first time."),
                      ("Installations", "New installs with clean, code-compliant work."),
                      ("Maintenance plans", "Seasonal check-ups that prevent the expensive surprises.")],
    "real_estate": [("Buying a home", "Local guidance from first showing to closing."),
                    ("Selling your home", "Pricing, staging advice and marketing that gets offers."),
                    ("Free home valuation", "Know what your home is worth in today's market.")],
    "beauty_wellness": [("Signature services", "Our most-booked treatments."), ("New client consult", "Tell us what you want."),
                        ("Packages", "Save with a series.")],
    "food": [("Menu", "Made fresh daily."), ("Catering", "Feed the office, the party or the family."),
             ("Order ahead", "Skip the line.")],
    "d2c": [("Shop the collection", "Made with care, shipped fast."), ("Gifts", "Something they'll actually keep."),
            ("Wholesale", "Stock us in your store.")],
}


def _fallback(lead, payload):
    brand = brand_name(lead["name"])
    town = payload.get("town") or "Connecticut"
    naics = (payload.get("naics") or "").split(" (")[0] or "Local business"
    svcs = GENERIC_SERVICES.get(lead["vertical"], [(naics, f"{naics} for {town} and nearby towns."),
                                                   ("Free consultation", "Tell us what you need.")])
    g = payload.get("google_business_profile") or {}
    trust = [f'{l["credential"].title()} since {l["issued"][:4]}' for l in (payload.get("licenses") or []) if l.get("issued")]
    if g.get("rating"):
        trust.append(f'{g["rating"]}★ on Google ({g["review_count"]} reviews)')
    trust.append("Locally owned in " + town)
    owner = next((p.get("firstname") for p in payload.get("owners") or [] if p.get("firstname")), None)
    return {
        "spoken_name": brand,
        "what_they_do_spoken": f"{naics.lower()} in {town}",
        "hero_headline": f"{naics} in {town}, done right",
        "hero_sub": f"{brand} serves {town} and the surrounding towns.",
        "about": f"{brand} is a {town}-based {naics.lower()} business"
                 + (f" run by {owner}." if owner else ".") + "\n\nWe keep it simple: show up, do great work, stand behind it.",
        "services": [{"name": n, "description": d} for n, d in svcs],
        "packages": [],
        "service_areas": [town],
        "trust_points": trust,
        "testimonials": [{"quote": r["text"][:220], "author": r["author"], "rating": r.get("rating"), "source": "Google"}
                         for r in g.get("reviews", []) if (r.get("rating") or 0) >= 4][:3],
        "review_themes": [],
        "faq": [{"q": f"Do you serve {town}?", "a": f"Yes. {town} is home base."}],
        "seo": {"title": f"{naics} in {town}, CT | {brand}"[:60],
                "meta_description": f"{brand}: {naics.lower()} in {town}, Connecticut. Call for a free quote."[:155],
                "keywords": [f"{naics.lower()} {town.lower()} ct", f"{naics.lower()} near me", brand.lower()]},
        "theme": {"home_services": "harbor", "real_estate": "charcoal", "beauty_wellness": "blush",
                  "food": "terracotta", "d2c": "slate"}.get(lead["vertical"], "forest"),
        "founder_brief": "Fallback dossier (no ANTHROPIC_API_KEY). Copy is generic; review before sending.",
        "confidence": 0.3,
    }
