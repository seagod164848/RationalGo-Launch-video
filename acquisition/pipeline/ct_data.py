"""Connecticut open data (Socrata, no key needed; set SOCRATA_APP_TOKEN for higher rate limits).

  n7gp-d28j  Business Registry - Business Master   (name, NAICS, address, business_email_address)
  ka36-64k6  Business Registry - Principals        (people behind the business, joined on business_id)
  ngch-56tr  DCP State Licenses and Credentials    (HIC, plumbing, electrical, real-estate, salon... with issue dates)
"""
import re
import time

import requests

from . import config

BASE = "https://data.ct.gov/resource"
REGISTRY, PRINCIPALS, LICENSES = "n7gp-d28j", "ka36-64k6", "ngch-56tr"

# Credentials that say something a customer cares about. Everything else (notary,
# liquor brand labels, pesticide product registrations...) is noise.
USEFUL_CREDENTIALS = {
    "HIC", "HIS", "NHC",                      # home improvement / new home construction
    "PLM", "P1", "P2", "HTG", "S1", "S2",     # plumbing, heating & cooling
    "ELC", "E1", "E2",                        # electrical
    "RES", "REB", "REA",                      # real estate salesperson / broker / appraiser
    "20", "EST", "NLT", "COMB", "29", "BAR",  # hair, esthetics, nails, massage, barber
    "CPAL", "CPAC", "RSPF", "ARI", "PEN",     # CPA, tax preparer, architect, engineer
    "2", "13", "14", "46", "8", "58", "48",   # dentist, hygienist, PT, counselor, psych, LCSW, OT
    "PMCO", "PMSV",                           # pesticide applicators (lawn care, pest control)
}


def _get(dataset, params):
    headers = {}
    if tok := config.env("SOCRATA_APP_TOKEN"):
        headers["X-App-Token"] = tok
    for attempt in range(4):
        try:
            r = requests.get(f"{BASE}/{dataset}.json", params=params, headers=headers, timeout=60)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))


LIVE_STATUS = {"ACTIVE", "APPROVED", "QUALIFIED", "CURRENT"}

# Which credentials prove which vertical. Also used to re-route a vague LLC name
# ("Garnet LLC") whose owner turns out to hold an active home-improvement license.
LICENSE_VERTICAL = {
    "HIC": "home_services", "HIS": "home_services", "NHC": "home_services", "PLM": "home_services",
    "P1": "home_services", "P2": "home_services", "HTG": "home_services", "S1": "home_services",
    "S2": "home_services", "ELC": "home_services", "E1": "home_services", "E2": "home_services",
    "PMCO": "home_services", "PMSV": "home_services",
    "RES": "real_estate", "REB": "real_estate", "REA": "real_estate",
    "20": "beauty_wellness", "EST": "beauty_wellness", "NLT": "beauty_wellness", "COMB": "beauty_wellness",
    "29": "beauty_wellness", "BAR": "beauty_wellness",
    "CPAL": "professional", "CPAC": "professional", "RSPF": "professional", "ARI": "professional", "PEN": "professional",
    "2": "health", "13": "health", "14": "health", "46": "health", "8": "health", "58": "health", "48": "health",
}


def registrations(day):
    """All businesses registered on `day` (YYYY-MM-DD). ~150-250 on weekdays, ~60 on weekends."""
    return _get(REGISTRY, {
        "$where": f"date_registration='{day}T00:00:00' AND status='Active'",
        "$limit": 5000,
    })


def principals(business_ids):
    out = {}
    ids = list(business_ids)
    for i in range(0, len(ids), 100):
        chunk = ", ".join(f"'{b}'" for b in ids[i:i + 100])
        for p in _get(PRINCIPALS, {"$where": f"business_id in ({chunk})", "$limit": 5000}):
            out.setdefault(p["business_id"], []).append(p)
    return out


def _soql_str(s):
    return s.replace("'", "''").upper()


def licenses_for(principal, business_name):
    """Licenses held by this person (name + town match) or by the business itself."""
    first, last = principal.get("firstname"), principal.get("lastname")
    clauses = []
    if first and last:
        # DCP stores "FIRST M LAST"; allow a middle name/initial.
        clauses.append(f"upper(name) like '{_soql_str(first)}%{_soql_str(last)}'")
    core = re.sub(r",?\s+(LLC|L\.L\.C\.|INC\.?|CORP\.?|CO\.?|LTD\.?|LLP|PLLC)$", "", business_name.strip(), flags=re.I)
    if len(core) > 4:
        clauses.append(f"upper(name) like '{_soql_str(core)}%'")
    if not clauses:
        return []
    rows = _get(LICENSES, {"$where": " OR ".join(f"({c})" for c in clauses), "$limit": 200})
    towns = {(principal.get(k) or "").upper() for k in ("residence_city", "business_city")} - {""}
    individuals = {r.get("name") for r in rows if r.get("type") == "INDIVIDUAL"}
    keep = []
    for r in rows:
        if r.get("credentialtype") not in USEFUL_CREDENTIALS:
            continue
        # Common names collide statewide: an individual's license counts only if it's in the
        # owner's town, or if exactly one person in CT has that name.
        if r.get("type") == "INDIVIDUAL" and (r.get("city") or "").upper() not in towns and len(individuals) > 1:
            continue
        if not r.get("issuedate"):  # applications that were never granted
            continue
        keep.append({
            "credential": r.get("credential"),
            "code": r.get("fullcredentialcode"),
            "status": r.get("status"),
            "live": r.get("status") in LIVE_STATUS,
            "vertical": LICENSE_VERTICAL.get(r.get("credentialtype")),
            "issued": (r.get("issuedate") or "")[:10],
            "expires": (r.get("expirationdate") or "")[:10],
            "holder": r.get("name"),
            "city": r.get("city"),
        })
    return keep
