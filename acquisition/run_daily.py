#!/usr/bin/env python3
"""Daily acquisition run: CT registrations -> pick 100 -> research -> site -> video -> outreach.

  python3 run_daily.py                       # yesterday's registrations, all stages
  python3 run_daily.py --day 2026-10-28 --limit 5 --stages ingest,segment,enrich,dossier,site
  python3 run_daily.py --lead 001eq00001gLO0EAAW --stages dossier,site,video   # redo one lead

Each stage is idempotent and only touches leads that reached the previous one, so a
failed run can simply be re-run.
"""
import argparse
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from pipeline import config, ct_data, dossier, enrich, outreach, segment, site_builder, store, video

ALL = ["ingest", "segment", "enrich", "dossier", "site", "video", "outreach"]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def parallel(fn, items, workers=8):
    def safe(x):
        try:
            return fn(x)
        except Exception:  # one bad lead must not sink the other 99
            log(f"  ! {x.get('name', x)}: {traceback.format_exc(limit=2)}")
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(safe, items))


def ingest(db, day):
    recs = ct_data.registrations(day)
    people = ct_data.principals([r["id"] for r in recs])
    for r in recs:
        store.upsert(db, r["id"], registered_on=day, name=r["name"], email=r.get("business_email_address"),
                     stage="ingested", registry=r, principals=people.get(r["id"], []))
    log(f"ingest: {len(recs)} registrations on {day}")


def segment_day(db, day, limit):
    leads = store.leads(db, "registered_on=?", (day,))
    unplaced = []
    for l in leads:
        v, _ = segment.rule_vertical(l["registry"])
        l["vertical"] = v
        if v is None:
            unplaced.append(l["registry"])
    for lid, v in segment.llm_verticals(unplaced).items():
        next(l for l in leads if l["id"] == lid)["vertical"] = v

    def score_one(l):
        v = l["vertical"] or "other"
        lic = []
        if v != "skip":
            for p in l["principals"][:3]:
                lic += ct_data.licenses_for(p, l["name"])
        v = segment.vertical_from_licenses(v, lic)
        site = segment.existing_website(l["email"]) if v != "skip" else None
        s, why = segment.score(l["registry"], v, lic, l["principals"], site)
        if v == "skip":
            s, why = -999, ["skip_vertical"]
        store.upsert(db, l["id"], vertical=v, licenses=lic, score=s, stage="segmented",
                     segment={"why": why, "existing_site": site})
        return s
    parallel(score_one, leads)
    db.execute("update leads set selected=0 where registered_on=?", (day,))
    ranked = store.leads(db, "registered_on=? and score > 15", (day,))
    for i, l in enumerate(ranked):
        store.upsert(db, l["id"], selected=int(i < limit))
    log(f"segment: {len(ranked)} qualified of {len(leads)}, selected {min(limit, len(ranked))}")


def selected(db, day, lead_id, stage_done):
    if lead_id:
        return store.leads(db, "id=?", (lead_id,))
    want = store.STAGES[store.STAGES.index(stage_done):]
    marks = ",".join("?" for _ in want)
    return store.leads(db, f"registered_on=? and selected=1 and stage in ({marks})", (day, *want))


def enrich_stage(db, leads):
    def one(l):
        data, gaps = enrich.enrich(l)
        store.upsert(db, l["id"], enrichment=data, stage="enriched", gaps=sorted(set(l["gaps"]) | set(gaps)))
    parallel(one, leads)
    log(f"enrich: {len(leads)}")


def dossier_stage(db, leads):
    def one(l):
        d = dossier.build(l)
        store.upsert(db, l["id"], dossier=d, stage="dossier", slug=l.get("slug") or site_builder.slugify(l["name"]))
    parallel(one, leads, workers=4)
    log(f"dossier: {len(leads)}")


def site_stage(db, leads):
    for l in leads:
        slug, url = site_builder.build(l)
        store.upsert(db, l["id"], slug=slug, site_url=url, stage="site")
    site_builder.write_root_files()
    site_builder.deploy()
    log(f"site: {len(leads)} -> {config.OUT / 'sites'}")


def video_stage(db, leads):
    tls = {l["id"]: video.timeline_for(l["vertical"], bool(l["dossier"].get("testimonials"))) for l in leads}
    jobs = {l["id"]: video.prepare_slots(l, tls[l["id"]]) for l in leads}
    if any(jobs.values()):
        site_builder.deploy()  # lipsync API pulls slot audio + master clips by public URL
    def one(l):
        synced = video.run_lipsync(l, jobs[l["id"]]) if jobs[l["id"]] else None
        final = video.compose(l, synced)
        store.upsert(db, l["id"], video_path=str(final), stage="video")
    parallel(one, leads, workers=3)
    site_builder.deploy()
    log(f"video: {len(leads)}")


def outreach_stage(db, leads, day):
    for l in leads:
        if not l.get("video_path"):
            continue
        watch = outreach.write_watch_page(l)
        res = outreach.queue_email(l) | {"watch_url": watch}
        store.upsert(db, l["id"], outreach=res, stage="outreach")
    # Feed carries every lead from the last 14 days so retargeting keeps working after the email.
    since = (date.fromisoformat(day) - timedelta(days=14)).isoformat()
    recent = store.leads(db, "registered_on>=? and video_path is not null and claimed_at is null", (since,))
    outreach.write_catalog_feed(recent)
    site_builder.deploy()
    outreach.upload_audience(leads)
    log(f"outreach: {len(leads)} queued; catalog feed has {len(recent)} items")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=(date.today() - timedelta(days=1)).isoformat())
    ap.add_argument("--limit", type=int, default=config.DAILY_TARGET)
    ap.add_argument("--stages", default=",".join(ALL))
    ap.add_argument("--lead", help="run stages for one lead id only")
    a = ap.parse_args()
    stages = a.stages.split(",")
    db = store.connect()

    if "ingest" in stages and not a.lead:
        ingest(db, a.day)
    if "segment" in stages and not a.lead:
        segment_day(db, a.day, a.limit)
    if "enrich" in stages:
        enrich_stage(db, selected(db, a.day, a.lead, "segmented"))
    if "dossier" in stages:
        dossier_stage(db, selected(db, a.day, a.lead, "enriched"))
    if "site" in stages:
        site_stage(db, selected(db, a.day, a.lead, "dossier"))
    if "video" in stages:
        video_stage(db, selected(db, a.day, a.lead, "site"))
    if "outreach" in stages:
        outreach_stage(db, selected(db, a.day, a.lead, "video"), a.day)


if __name__ == "__main__":
    main()
