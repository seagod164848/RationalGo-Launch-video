"""Vertical classification + ICP scoring. Picks the daily 100 out of ~200 registrations.

Rules first (NAICS is on ~70% of records), Claude only for the leftovers. Roughly a
third of daily filings are landlord/holding LLCs that will never buy a website, and
they are filtered out here before any money is spent on enrichment or video.
"""
import json
import re

import requests

from . import config

# vertical -> (NAICS prefixes, name keywords, base value)
VERTICALS = {
    "home_services": (
        ["2361", "2381", "2382", "2383", "2389", "56172", "56173", "56174", "56179", "5617", "81149", "56291"],
        r"plumb|electric|hvac|heating|cooling|roof|paint|remodel|renovat|construct|contract|landscap|lawn|tree|"
        r"clean|maid|janitor|handyman|carpent|floor|tile|mason|paving|fence|pool|pest|junk|haul|moving|movers|"
        r"wash|power ?wash|gutter|siding|window|drywall|septic|excavat|snow|chimney|restoration",
        40,
    ),
    "real_estate": (
        ["53121", "531390", "531311", "531312", "531320"],
        r"realty|real estate|homes? group|properties group|realtor|brokerage|property management",
        35,
    ),
    "beauty_wellness": (
        ["8121", "713940", "62139", "446", "456"],
        r"salon|hair|barber|nail|lash|brow|beauty|spa|esthetic|massage|wax|tattoo|fitness|yoga|pilates|gym|"
        r"training|wellness|med ?spa",
        32,
    ),
    "food": (
        ["7225", "7223", "311", "3121", "4452"],
        r"kitchen|cafe|coffee|bakery|bake|pizza|grill|catering|food|eats|taco|burger|deli|bistro|bar\b|brew|"
        r"tavern|truck|sweets|cake|juice",
        30,
    ),
    "d2c": (
        ["4552", "458", "459", "4541", "4551", "339", "3152", "3256", "3116", "4491"],
        r"apparel|clothing|boutique|candle|soap|skincare|cosmetic|jewel|shop|store|goods|co\.$|brand|design|"
        r"collection|wear|gifts?",
        30,
    ),
    "auto": (["8111", "4411", "4413", "488410", "811192"], r"auto|motor|car ?(wash|care)|detail|tire|collision|towing", 30),
    "health": (["6211", "6212", "6213", "6214", "6216", "6219", "6241", "6244"],
               r"therapy|counsel|dental|chiro|clinic|health|care\b|home care|daycare|pediatric", 26),
    "events_creative": (["7115", "7111", "54192", "5414", "81292", "8129"],
                        r"photo|video|film|studio|media|events?|wedding|dj\b|entertain|art|design|music", 24),
    "professional": (["5411", "5412", "5416", "5413", "5418", "5242", "5239", "6116", "5419"],
                     r"consult|law|legal|account|cpa|tax|bookkeep|insurance|financial|advis|marketing|agency|"
                     r"coach|tutor|academy|staffing|solutions|services", 22),
    "logistics": (["484", "4853", "4854", "4921", "4931"], r"logistics|transport|trucking|freight|courier|delivery", 15),
}

SKIP_NAICS = ["531110", "531120", "531190", "551112", "551111", "5311", "525", "623110", "5132", "5182"]
SKIP_NAME = re.compile(
    r"holding|propert(y|ies)\b(?! management)|investments?|capital|ventures?|realty holdings|equities|"
    r"acquisition|assets?|trust\b|fund\b|partners lp|enterprises? holdings|land\b|\d+\s+\w+\s+(st|street|ave|avenue|rd|road|ln|lane|dr|drive)\b",
    re.I,
)
FILER_EMAIL = re.compile(r"law|legal|attorney|esq|registered.?agent|incfile|legalzoom|northwest|zenbusiness|"
                         r"bizfilings|corporat|ctcorp|cogency|filing|tax|cpa", re.I)
FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com", "live.com",
             "msn.com", "comcast.net", "me.com", "protonmail.com", "sbcglobal.net", "optonline.net", "cox.net"}


def naics_code(record):
    m = re.search(r"\((\d{4,6})\)", record.get("naics_code") or "")
    return m.group(1) if m else None


def rule_vertical(record):
    code = naics_code(record)
    name = record.get("name", "")
    if code and any(code.startswith(p) for p in SKIP_NAICS):
        # Lessor/holding NAICS, unless the name clearly describes an operating business.
        for v, (_, kw, _) in VERTICALS.items():
            if v != "real_estate" and re.search(kw, name, re.I):
                return v, "name_override"
        return "skip", "naics"
    if code:
        for v, (prefixes, _, _) in VERTICALS.items():
            if any(code.startswith(p) for p in prefixes):
                return v, "naics"
    for v, (_, kw, _) in VERTICALS.items():
        if re.search(kw, name, re.I):
            return v, "name"
    return None, None


def llm_verticals(records):
    """Batch-classify records rules couldn't place. One cheap call for the whole day."""
    if not records or not config.ANTHROPIC_API_KEY:
        return {}
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    items = [{"id": r["id"], "name": r["name"], "naics": r.get("naics_code"), "email": r.get("business_email_address"),
              "city": r.get("billingcity")} for r in records]
    msg = client.messages.create(
        model=config.SEGMENT_MODEL,
        max_tokens=4000,
        tools=[{
            "name": "classify",
            "description": "Assign each business a vertical.",
            "input_schema": {
                "type": "object",
                "properties": {"results": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "vertical": {"type": "string", "enum": [*VERTICALS, "skip", "other"]},
                    },
                    "required": ["id", "vertical"],
                }}},
                "required": ["results"],
            },
        }],
        tool_choice={"type": "tool", "name": "classify"},
        messages=[{"role": "user", "content":
                   "These Connecticut businesses registered today. Classify each into a vertical. Use 'skip' for "
                   "holding companies, single-property landlord LLCs, trusts, investment vehicles and anything that "
                   "would not want a customer-facing website. Use 'other' if it is an operating business but fits "
                   "no vertical.\n\n" + json.dumps(items)}],
    )
    block = next(b for b in msg.content if b.type == "tool_use")
    return {r["id"]: r["vertical"] for r in block.input["results"]}


def existing_website(email):
    """If they mail from their own domain, see whether a real site is already up there."""
    domain = (email or "").split("@")[-1].lower()
    if not domain or domain in FREE_MAIL:
        return None
    for url in (f"https://{domain}", f"https://www.{domain}"):
        try:
            r = requests.get(url, timeout=8, allow_redirects=True)
            body = r.text.lower()
            parked = any(s in body for s in ("domain is for sale", "parked", "coming soon", "godaddy", "this domain"))
            if r.ok and len(body) > 3000 and not parked:
                return url
        except requests.RequestException:
            continue
    return None


def vertical_from_licenses(vertical, licenses):
    """A vague name ('Garnet LLC') whose owner holds an active HIC is a contractor."""
    if vertical in (None, "other", "professional", "logistics", "events_creative"):
        for l in licenses:
            if l["live"] and l.get("vertical") and l["vertical"] != vertical:
                return l["vertical"]
    return vertical


def score(record, vertical, licenses, principals, site):
    email = (record.get("business_email_address") or "").lower()
    s, why = 0, []
    if vertical in VERTICALS:
        s += VERTICALS[vertical][2]
        why.append(f"vertical:{vertical}")
    elif vertical == "other":
        s += 12
    live = [l for l in licenses if l["live"] and l.get("vertical") == vertical]
    if live:
        s += 20
        why.append("licensed_operator")
    if any(l["issued"] < "2022" for l in licenses if l.get("vertical") == vertical):
        s += 8
        why.append("established_operator")  # already in the trade before incorporating: has reviews/history to pull
    if not email:
        s -= 100
        why.append("no_email")
    elif FILER_EMAIL.search(email):
        s -= 40
        why.append("email_is_filer_or_attorney")
    elif email.split("@")[-1] in FREE_MAIL:
        s += 10
        why.append("free_mail_no_site")
    if site:
        s -= 25
        why.append("already_has_site")
    if SKIP_NAME.search(record.get("name", "")):
        s -= 30
        why.append("holding_like_name")
    if any(p.get("firstname") for p in principals) and any(
            (p.get("residence_state") or p.get("business_state")) == "CT" for p in principals):
        s += 5
        why.append("local_owner")
    return s, why
