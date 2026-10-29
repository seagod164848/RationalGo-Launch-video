"""Renders the dossier into a static site at out/sites/{slug}/ and deploys the
whole folder (one Cloudflare Pages project, one path per business)."""
import json
import re
import subprocess
from datetime import date
from pathlib import Path

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config
from .enrich import brand_name

THEMES = {
    "harbor": {"brand": "#0f3b5c", "ink": "#0b1b28", "accent": "#ffc857", "bg": "#f7f8fa", "panel": "#ffffff"},
    "forest": {"brand": "#1f4d3a", "ink": "#0d1f17", "accent": "#e9c46a", "bg": "#f6f7f3", "panel": "#ffffff"},
    "terracotta": {"brand": "#8c3b25", "ink": "#2a0f07", "accent": "#f4d35e", "bg": "#fbf6f1", "panel": "#ffffff"},
    "charcoal": {"brand": "#1d2329", "ink": "#111111", "accent": "#d6b98c", "bg": "#f6f5f2", "panel": "#ffffff"},
    "blush": {"brand": "#7b3f55", "ink": "#2b1019", "accent": "#f6c1cc", "bg": "#fcf7f8", "panel": "#ffffff"},
    "slate": {"brand": "#2f3e57", "ink": "#0d1420", "accent": "#9ad1d4", "bg": "#f5f7fa", "panel": "#ffffff"},
}

COPY = {  # vertical -> (primary CTA, services eyebrow, services heading)
    "home_services": ("Get a free estimate", "Services", "What we do"),
    "real_estate": ("Book a free consultation", "How I help", "Buying or selling, I've got you"),
    "beauty_wellness": ("Book an appointment", "Menu", "Services"),
    "food": ("Order now", "Menu", "What we're serving"),
    "d2c": ("Shop now", "The collection", "Made for you"),
    "health": ("Request an appointment", "Care", "How we can help"),
}

env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=select_autoescape(["j2"]))


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", brand_name(name).lower()).strip("-")[:60]


def _money(v):
    try:
        return f"${float(v):,.0f}"
    except (TypeError, ValueError):
        return v or ""


def _listings(zillow):
    out = []
    for label, items in (("For sale", (zillow or {}).get("active")), ("Sold", (zillow or {}).get("sold"))):
        for i in items or []:
            specs = " · ".join(x for x in (i.get("beds") and f'{i["beds"]} bd', i.get("baths") and f'{i["baths"]} ba',
                                           i.get("sqft") and f'{int(i["sqft"]):,} sqft') if x)
            out.append({**i, "label": label, "price_fmt": _money(i.get("price")), "specs": specs})
    return out[:9]


def jsonld(lead, d, url, town, phone):
    reg = lead["registry"]
    biz = {
        "@context": "https://schema.org",
        "@type": d["schema_type"],
        "name": brand_name(lead["name"]),
        "legalName": lead["name"],
        "url": url,
        "description": d["seo"]["meta_description"],
        "address": {"@type": "PostalAddress", "streetAddress": reg.get("billingstreet"), "addressLocality": town,
                    "addressRegion": "CT", "postalCode": (reg.get("billingpostalcode") or "")[:5], "addressCountry": "US"},
        "areaServed": [{"@type": "City", "name": f"{a}, CT"} for a in d["service_areas"]],
        "hasOfferCatalog": {"@type": "OfferCatalog", "name": "Services", "itemListElement": [
            {"@type": "Offer", "itemOffered": {"@type": "Service", "name": s["name"], "description": s["description"]}}
            for s in d["services"]]},
        "foundingDate": lead["registered_on"],
    }
    if phone:
        biz["telephone"] = phone
    if sameas := [u for u in (lead.get("enrichment") or {}).get("socials", {}).values()]:
        biz["sameAs"] = sameas
    graph = [biz]
    if d.get("faq"):
        graph.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in d["faq"]]})
    # No aggregateRating: Google ignores self-served review markup on LocalBusiness and it can trigger a manual action.
    return json.dumps(graph, ensure_ascii=False)


def _download_photo(src, dest):
    if not src or not config.GOOGLE_PLACES_API_KEY:
        return False
    if dest.exists():
        return True
    try:
        r = requests.get(src, params={"key": config.GOOGLE_PLACES_API_KEY}, timeout=30)
    except requests.RequestException:
        return False
    if r.ok and r.headers.get("content-type", "").startswith("image/"):
        dest.write_bytes(r.content)
        return True
    return False


def build(lead, claimed=False):
    d = lead["dossier"]
    enr = lead.get("enrichment") or {}
    g = enr.get("google") or {}
    slug = lead.get("slug") or slugify(lead["name"])
    url = f"{config.PREVIEW_BASE_URL.rstrip('/')}/{slug}/"
    town = enr.get("town") or (lead["registry"].get("billingcity") or "").title()
    cta, eyebrow, heading = COPY.get(lead["vertical"], ("Get in touch", "Services", "What we do"))
    owner_first = next((p.get("firstname", "").title() for p in lead.get("principals") or [] if p.get("firstname")), None)
    claim = config.STRIPE_PAYMENT_LINK
    claim_url = f"{claim}?client_reference_id={lead['id']}&prefilled_email={lead['email']}" if claim else "#contact"
    ctx = dict(
        d=d, themes=THEMES, claimed=claimed, canonical=url, lead_id=lead["id"], brand=brand_name(lead["name"]),
        legal_name=lead["name"], town=town, phone=g.get("phone"), hours=g.get("hours"),
        hero_image=None,
        rating=g.get("rating"), review_count=g.get("review_count"), maps_url=g.get("maps_url"),
        listings=_listings(enr.get("zillow")), products=enr.get("products") or [],
        primary_cta=cta, services_eyebrow=eyebrow, services_heading=heading,
        about_heading=f"Meet {owner_first}" if owner_first else f"About {brand_name(lead['name'])}",
        owner_first=owner_first, claim_url=claim_url, price=config.CLAIM_PRICE_USD, agency=config.AGENCY_NAME,
        pixel_id=config.META_PIXEL_ID, year=date.today().year,
        jsonld=jsonld(lead, d, url, town, g.get("phone")).replace("</", "<\\/"),
    )
    out = config.OUT / "sites" / slug
    out.mkdir(parents=True, exist_ok=True)
    if _download_photo((g.get("photos") or [None])[0], out / "hero.jpg"):
        ctx["hero_image"] = "hero.jpg"  # never ship the Places key in public HTML
    (out / "index.html").write_text(env.get_template("site.html.j2").render(**ctx))
    return slug, url


def write_root_files():
    """robots.txt blocks crawlers from unclaimed previews; claimed sites move to their own domain."""
    root = config.OUT / "sites"
    root.mkdir(parents=True, exist_ok=True)
    (root / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    (root / "_headers").write_text("/*\n  X-Robots-Tag: noindex\n")


def deploy():
    if not config.CLOUDFLARE_PAGES_PROJECT:
        return False
    write_root_files()
    subprocess.run(["npx", "--yes", "wrangler@3", "pages", "deploy", str(config.OUT / "sites"),
                    "--project-name", config.CLOUDFLARE_PAGES_PROJECT, "--branch", "main"], check=True)
    return True
