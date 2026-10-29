"""SQLite lead store. One row per registered business; each stage writes its
output as a JSON blob so stages can be re-run independently."""
import json
import sqlite3
import threading
from datetime import datetime, timezone

from . import config

STAGES = ["ingested", "segmented", "enriched", "dossier", "site", "video", "outreach"]

SCHEMA = """
create table if not exists leads (
  id text primary key,            -- CT registry business id
  registered_on text,
  name text,
  email text,
  stage text,
  vertical text,
  score real,
  selected integer default 0,     -- picked into the daily 100
  slug text,
  registry json, principals json, licenses json,
  segment json, enrichment json, dossier json,
  site_url text, video_path text, outreach json,
  gaps json default '[]',
  claimed_at text,
  updated_at text
);
create index if not exists leads_day on leads(registered_on, selected);
"""

_lock = threading.Lock()  # stages fan out over threads; sqlite writes are serialised here

JSON_COLS = {"registry", "principals", "licenses", "segment", "enrichment", "dossier", "outreach", "gaps"}


def connect():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def upsert(db, lead_id, **fields):
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    for k in JSON_COLS & fields.keys():
        fields[k] = json.dumps(fields[k])
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    updates = ", ".join(f"{k}=excluded.{k}" for k in fields if k != "stage")
    if "stage" in fields:  # stages only advance: re-running `site` must not hide a finished video from `outreach`
        rank = " ".join(f"when '{s}' then {i}" for i, s in enumerate(STAGES))
        updates += (f", stage=case when (case excluded.stage {rank} end) > (case leads.stage {rank} else -1 end)"
                    f" then excluded.stage else leads.stage end")
    with _lock:
        db.execute(
            f"insert into leads (id, {cols}) values (?, {marks}) on conflict(id) do update set {updates}",
            [lead_id, *fields.values()],
        )
        db.commit()


def row_to_lead(row):
    lead = dict(row)
    for k in JSON_COLS:
        if lead.get(k):
            lead[k] = json.loads(lead[k])
    lead["gaps"] = lead.get("gaps") or []
    return lead


def leads(db, where="1=1", params=()):
    with _lock:
        rows = db.execute(f"select * from leads where {where} order by score desc", params).fetchall()
    return [row_to_lead(r) for r in rows]


def add_gap(db, lead, gap):
    if gap not in lead["gaps"]:
        lead["gaps"].append(gap)
        upsert(db, lead["id"], gaps=lead["gaps"])
