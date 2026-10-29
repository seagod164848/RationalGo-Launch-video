"""Getting the video in front of the owner.

Why not "one Instagram ad per business": Meta won't deliver to a custom audience of
one person (custom audiences need ~100 matched people), and there is no way to pin a
specific creative to a specific person in an uploaded list. So delivery is two-layered:

 1. Email (we have the address from the registry) -> watch page with their video,
    their site and the $499 claim button. This is the actual 1:1 channel.
 2. Instagram/Facebook via an Advantage+ catalog: every lead is a catalog item whose
    video is their personalised video. The site's pixel fires ViewContent with the lead's
    id, so anyone who opens their preview gets retargeted on Instagram with *their own*
    video. Plus a cohort audience (the week's hashed emails) for a prospecting ad.
"""
import csv
import hashlib
import html
import json

import requests

from . import config
from .enrich import brand_name

SUPPRESSION = config.OUT / "suppression.txt"  # one email per line; unsubscribes go here


def suppressed():
    return {l.strip().lower() for l in SUPPRESSION.read_text().splitlines()} if SUPPRESSION.exists() else set()


def site_url(lead):
    return f"{config.PREVIEW_BASE_URL.rstrip('/')}/{lead['slug']}/"


def write_watch_page(lead):
    """/{slug}/watch/: the landing page the email and ads point to."""
    brand = html.escape(brand_name(lead["name"]))
    base = site_url(lead)
    claim = (f"{config.STRIPE_PAYMENT_LINK}?client_reference_id={lead['id']}" if config.STRIPE_PAYMENT_LINK else base)
    pixel = ""
    if config.META_PIXEL_ID:
        pixel = (f"<script>!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?n.callMethod.apply(n,arguments):"
                 f"n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);"
                 f"t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}(window,document,'script',"
                 f"'https://connect.facebook.net/en_US/fbevents.js');fbq('init','{config.META_PIXEL_ID}');fbq('track','PageView');"
                 f"fbq('track','ViewContent',{{content_ids:['{lead['id']}'],content_type:'product'}});</script>")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>{brand}: your new website</title>{pixel}
<style>body{{margin:0;font-family:Inter,system-ui,sans-serif;background:#0e0f11;color:#fff;display:flex;flex-direction:column;align-items:center;padding:24px 16px 48px}}
h1{{font-size:24px;text-align:center;max-width:520px;line-height:1.25}}video{{width:100%;max-width:400px;border-radius:18px;background:#000;aspect-ratio:9/16}}
.row{{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-top:20px}}a{{padding:14px 22px;border-radius:999px;font-weight:600;text-decoration:none}}
.p{{background:#fff;color:#111}}.s{{border:1px solid #555;color:#fff}}small{{color:#888;margin-top:18px;text-align:center;max-width:420px}}</style></head>
<body><h1>Hey {brand}, I built you a website 👇</h1>
<video src="../video.mp4" poster="../poster.jpg" controls playsinline preload="metadata"></video>
<div class="row"><a class="p" href="{claim}">Claim it for ${config.CLAIM_PRICE_USD}</a><a class="s" href="../">See the full site</a></div>
<small>One-time ${config.CLAIM_PRICE_USD}. We connect your domain, swap in your real prices and photos, and hand it over. No subscription.</small>
</body></html>"""
    d = config.OUT / "sites" / lead["slug"] / "watch"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(page)
    return base + "watch/"


# ---------------------------------------------------------------- 1. Email via Instantly (built for cold outreach;
# transactional senders like SES/Resend forbid unsolicited mail in their AUP)
def queue_email(lead):
    if lead["email"].lower() in suppressed():
        return {"skipped": "suppressed"}
    first = next((p.get("firstname", "").title() for p in lead.get("principals") or [] if p.get("firstname")), "")
    base = site_url(lead)
    payload = {
        "campaign": config.INSTANTLY_CAMPAIGN_ID,
        "email": lead["email"],
        "first_name": first,
        "company_name": brand_name(lead["name"]),
        "personalization": lead["dossier"].get("what_they_do_spoken"),
        "custom_variables": {
            "watch_url": base + "watch/",
            "site_url": base,
            "gif_url": base + "preview.gif",
            "town": (lead.get("enrichment") or {}).get("town", ""),
            "vertical": lead["vertical"],
            "postal_address": config.POSTAL_ADDRESS,
        },
    }
    if not config.INSTANTLY_API_KEY:
        return {"dry_run": payload}
    r = requests.post("https://api.instantly.ai/api/v2/leads", json=payload,
                      headers={"Authorization": f"Bearer {config.INSTANTLY_API_KEY}"}, timeout=30)
    r.raise_for_status()
    return {"instantly_lead_id": r.json().get("id")}


# ---------------------------------------------------------------- 2a. Meta catalog (1:1 retargeting with their own video)
def write_catalog_feed(leads):
    """Hosted at {PREVIEW_BASE_URL}/_feeds/catalog.csv; set it as a scheduled daily feed on the catalog."""
    path = config.OUT / "sites" / "_feeds" / "catalog.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "title", "description", "availability", "condition", "price", "link", "image_link", "brand",
                    "video[0].url", "custom_label_0", "custom_label_1"])
        for l in leads:
            if not l.get("video_path"):
                continue
            base = site_url(l)
            b = brand_name(l["name"])
            w.writerow([l["id"], f"{b}: your website is ready"[:150],
                        f"We built {b} a website. Watch the 40s walkthrough and claim it.",
                        "in stock", "new", f"{config.CLAIM_PRICE_USD}.00 USD", base + "watch/", base + "poster.jpg",
                        b[:100], base + "video.mp4", l["vertical"], l["registered_on"]])
    return path


# ---------------------------------------------------------------- 2b. Cohort custom audience (hashed, per Meta spec)
def _h(v):
    return hashlib.sha256(v.strip().lower().encode()).hexdigest() if v else ""


def upload_audience(leads, audience_id=None):
    if not (config.META_ACCESS_TOKEN and config.META_AD_ACCOUNT_ID):
        return None
    g = "https://graph.facebook.com/v21.0"
    tok = {"access_token": config.META_ACCESS_TOKEN}
    if not audience_id:
        audience_id = config.env("META_AUDIENCE_ID")
    if not audience_id:
        r = requests.post(f"{g}/act_{config.META_AD_ACCOUNT_ID}/customaudiences", data={
            **tok, "name": "CT new registrations (rolling)", "subtype": "CUSTOM",
            "customer_file_source": "PARTNER_PROVIDED_ONLY",
            "description": "Owners of newly registered CT businesses, from the public CT business registry"})
        r.raise_for_status()
        audience_id = r.json()["id"]
    rows = []
    for l in leads:
        p = next((p for p in l.get("principals") or [] if p.get("firstname")), {})
        reg = l["registry"]
        rows.append([_h(l["email"]), _h(p.get("firstname")), _h(p.get("lastname")),
                     _h((reg.get("billingpostalcode") or "")[:5]), _h((reg.get("billingcity") or "").replace(" ", "")),
                     _h("ct"), _h("us")])
    r = requests.post(f"{g}/{audience_id}/users", data={**tok, "payload": json.dumps(
        {"schema": ["EMAIL", "FN", "LN", "ZIP", "CT", "ST", "COUNTRY"], "data": rows})})
    r.raise_for_status()
    return audience_id
