"""Per-vertical research. Every source is optional and returns {} when its key is
missing, so a lead always gets *a* site; it just has fewer sections.

Reality check that shapes this module: a business registered yesterday usually has
no reviews under its new legal name. The reviews, listings and history belong to the
*person*, who was often already working as a sole proprietor or under a DBA. So we
search on the principal's name as well as the LLC name, and keep whichever hit
matches the address/town.
"""
import re
from difflib import SequenceMatcher

import requests

from . import config

LEGAL_SUFFIX = re.compile(r",?\s+(LLC|L\.L\.C\.|INC\.?|CORP\.?|CORPORATION|CO\.?|LTD\.?|LLP|PLLC|PC)\.?$", re.I)

VERTICAL_QUERY_HINT = {
    "home_services": "contractor", "real_estate": "realtor", "beauty_wellness": "salon",
    "food": "restaurant", "d2c": "shop", "auto": "auto", "health": "clinic",
    "events_creative": "studio", "professional": "", "logistics": "", "other": "",
}


def brand_name(legal):
    return LEGAL_SUFFIX.sub("", legal.strip()).strip()


def _similar(a, b):
    return SequenceMatcher(None, brand_name(a).lower(), brand_name(b).lower()).ratio()


# ---------------------------------------------------------------- Google Places (New)
PLACES_FIELDS = ("places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,"
                 "places.reviews,places.websiteUri,places.nationalPhoneNumber,places.regularOpeningHours,"
                 "places.primaryTypeDisplayName,places.photos,places.googleMapsUri,places.editorialSummary")


def google_place(queries, town):
    if not config.GOOGLE_PLACES_API_KEY:
        return {}
    for q, target in queries:
        r = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={"X-Goog-Api-Key": config.GOOGLE_PLACES_API_KEY, "X-Goog-FieldMask": PLACES_FIELDS},
            json={"textQuery": q, "locationBias": {"circle": {"center": {"latitude": 41.6, "longitude": -72.7},
                                                              "radius": 50000}}},
            timeout=30,
        )
        if not r.ok:
            continue
        for p in r.json().get("places", []):
            name = p.get("displayName", {}).get("text", "")
            addr = p.get("formattedAddress", "")
            # Accept when the name matches, or when it's in the same town and the target (person) name appears.
            if _similar(name, target) > 0.72 or (town and town.lower() in addr.lower() and
                                                   target.split()[-1].lower() in name.lower()):
                return {
                    "place_id": p["id"],
                    "name": name,
                    "address": addr,
                    "rating": p.get("rating"),
                    "review_count": p.get("userRatingCount", 0),
                    "maps_url": p.get("googleMapsUri"),
                    "website": p.get("websiteUri"),
                    "phone": p.get("nationalPhoneNumber"),
                    "category": (p.get("primaryTypeDisplayName") or {}).get("text"),
                    "summary": (p.get("editorialSummary") or {}).get("text"),
                    "hours": (p.get("regularOpeningHours") or {}).get("weekdayDescriptions"),
                    "reviews": [{
                        "author": rv.get("authorAttribution", {}).get("displayName"),
                        "rating": rv.get("rating"),
                        "text": (rv.get("originalText") or rv.get("text") or {}).get("text", ""),
                        "when": rv.get("relativePublishTimeDescription"),
                        "source": "Google",
                    } for rv in p.get("reviews", [])],
                    "photos": [f"https://places.googleapis.com/v1/{ph['name']}/media?maxWidthPx=1600"
                               for ph in p.get("photos", [])[:6]],
                    "matched_on": q,
                }
    return {}


# ---------------------------------------------------------------- Web search (Serper = Google SERP)
def web_search(q, num=8):
    if not config.SERPER_API_KEY:
        return []
    r = requests.post("https://google.serper.dev/search", headers={"X-API-KEY": config.SERPER_API_KEY},
                      json={"q": q, "gl": "us", "num": num}, timeout=30)
    if not r.ok:
        return []
    return [{"title": o.get("title"), "url": o.get("link"), "snippet": o.get("snippet")}
            for o in r.json().get("organic", [])]


def founder_research(principals, brand, town, vertical):
    """What the people behind it have done before: LinkedIn, prior businesses, press, socials."""
    out = {"business": web_search(f'"{brand}" {town} CT')}
    for p in principals[:2]:
        full = f'{p.get("firstname", "")} {p.get("lastname", "")}'.strip()
        if not full:
            continue
        hint = VERTICAL_QUERY_HINT.get(vertical, "")
        out[full] = (web_search(f'"{full}" {town} Connecticut {hint}') +
                     web_search(f'"{full}" {hint} site:linkedin.com OR site:instagram.com OR site:facebook.com', 5))
    return out


def socials_from(results):
    found = {}
    for hits in results.values():
        for h in hits:
            u = h.get("url") or ""
            for net in ("instagram.com", "facebook.com", "linkedin.com", "tiktok.com", "yelp.com", "zillow.com",
                        "realtor.com", "houzz.com", "angi.com", "thumbtack.com", "etsy.com"):
                if net in u and net not in found:
                    found[net] = u
    return found


# ---------------------------------------------------------------- Real estate: listings
def zillow_listings(agent_name, town):
    """Zillow has no public listings API. This calls a third-party wrapper on RapidAPI
    (default: zillow-com1). Check that provider's terms before production use; MLS/IDX via a
    broker is the clean long-term source once the agent claims the site."""
    if not config.ZILLOW_RAPIDAPI_KEY:
        return {}
    h = {"X-RapidAPI-Key": config.ZILLOW_RAPIDAPI_KEY, "X-RapidAPI-Host": config.ZILLOW_RAPIDAPI_HOST}
    base = f"https://{config.ZILLOW_RAPIDAPI_HOST}"
    try:
        found = requests.get(f"{base}/searchAgent", headers=h, params={"location": f"{town}, CT", "name": agent_name},
                             timeout=30).json()
        agents = found.get("agents") or found.get("results") or []
        if not agents:
            return {}
        agent = agents[0]
        uname = agent.get("username") or agent.get("encodedZuid")
        listings = requests.get(f"{base}/agentActiveListings", headers=h, params={"username": uname}, timeout=30).json()
        sold = requests.get(f"{base}/agentPastSales", headers=h, params={"username": uname}, timeout=30).json()
    except (requests.RequestException, ValueError):
        return {}

    def norm(items):
        return [{"address": i.get("address") or i.get("streetAddress"), "price": i.get("price"),
                 "beds": i.get("bedrooms"), "baths": i.get("bathrooms"), "sqft": i.get("livingArea"),
                 "photo": i.get("imgSrc") or i.get("image"), "url": i.get("detailUrl"),
                 "status": i.get("homeStatus"), "date": i.get("soldDate")} for i in (items or [])[:9]]

    return {"profile": agent, "active": norm(listings.get("listings")), "sold": norm(sold.get("pastSales"))}


# ---------------------------------------------------------------- D2C: existing catalog
def storefront_products(domain_or_url):
    """Shopify exposes /products.json on every store. Pulls real product names, prices, images."""
    if not domain_or_url:
        return []
    base = domain_or_url if domain_or_url.startswith("http") else f"https://{domain_or_url}"
    try:
        r = requests.get(base.rstrip("/") + "/products.json?limit=12", timeout=15)
        prods = r.json().get("products", []) if r.ok else []
    except (requests.RequestException, ValueError):
        return []
    return [{"title": p["title"], "price": (p.get("variants") or [{}])[0].get("price"),
             "image": (p.get("images") or [{}])[0].get("src"),
             "description": re.sub("<[^>]+>", " ", p.get("body_html") or "")[:300]} for p in prods]


# ---------------------------------------------------------------- orchestrate
def enrich(lead):
    reg, principals = lead["registry"], lead["principals"] or []
    brand = brand_name(lead["name"])
    town = (reg.get("billingcity") or "").title()
    vertical = lead["vertical"]
    people = [f'{p.get("firstname", "")} {p.get("lastname", "")}'.strip() for p in principals if p.get("firstname")]
    hint = VERTICAL_QUERY_HINT.get(vertical, "")

    queries = [(f"{brand} {town} CT", brand)] + [(f"{n} {hint} {town} CT", n) for n in people[:2]]
    data = {"brand": brand, "town": town, "people": people, "google": google_place(queries, town)}
    data["research"] = founder_research(principals, brand, town, vertical)
    data["socials"] = socials_from(data["research"])

    if vertical == "real_estate" and people:
        data["zillow"] = zillow_listings(people[0], town)
    if vertical == "d2c":
        site = data["google"].get("website") or (lead.get("segment") or {}).get("existing_site")
        email_domain = (reg.get("business_email_address") or "").split("@")[-1]
        data["products"] = storefront_products(site) or storefront_products(email_domain)

    gaps = []
    if not config.GOOGLE_PLACES_API_KEY:
        gaps.append("google_places_key_missing")
    elif not data["google"]:
        gaps.append("no_google_profile")
    elif not data["google"].get("reviews"):
        gaps.append("no_reviews")
    if not config.SERPER_API_KEY:
        gaps.append("web_search_key_missing")
    if vertical == "real_estate" and not data.get("zillow"):
        gaps.append("no_listings")
    return data, gaps
