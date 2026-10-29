"""Runtime config. Everything optional: a stage whose key is missing degrades
to a no-op (and records that gap on the lead) instead of failing the run."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.getenv("ACQ_OUT", ROOT / "out"))
DB_PATH = Path(os.getenv("ACQ_DB", OUT / "leads.db"))


def _load_dotenv():
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()


def env(name, default=None):
    v = os.getenv(name, default)
    return v if v not in ("", None) else default


# Volume
DAILY_TARGET = int(env("DAILY_TARGET", "100"))

# Brand / offer
AGENCY_NAME = env("AGENCY_NAME", "RationalGo")
FOUNDER_NAME = env("FOUNDER_NAME", "Varun")
CLAIM_PRICE_USD = int(env("CLAIM_PRICE_USD", "499"))
PREVIEW_BASE_URL = env("PREVIEW_BASE_URL", "https://preview.example.com")  # sites live at {base}/{slug}/
STRIPE_PAYMENT_LINK = env("STRIPE_PAYMENT_LINK")  # $499 Payment Link; we append ?client_reference_id={lead_id}

# Providers (all optional)
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
DOSSIER_MODEL = env("DOSSIER_MODEL", "claude-opus-5-5")
SEGMENT_MODEL = env("SEGMENT_MODEL", "claude-haiku-5-5")
GOOGLE_PLACES_API_KEY = env("GOOGLE_PLACES_API_KEY")
SERPER_API_KEY = env("SERPER_API_KEY")  # Google web search for founder/business research
ZILLOW_RAPIDAPI_KEY = env("ZILLOW_RAPIDAPI_KEY")
ZILLOW_RAPIDAPI_HOST = env("ZILLOW_RAPIDAPI_HOST", "zillow-com1.p.rapidapi.com")
ELEVENLABS_API_KEY = env("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = env("ELEVENLABS_VOICE_ID")  # your cloned voice
SYNC_API_KEY = env("SYNC_API_KEY")  # sync.so lipsync
SYNC_MODEL = env("SYNC_MODEL", "lipsync-2")
PUBLIC_ASSET_BASE = env("PUBLIC_ASSET_BASE")  # where out/ is reachable over https (lipsync API fetches by URL)
CLOUDFLARE_PAGES_PROJECT = env("CLOUDFLARE_PAGES_PROJECT")
INSTANTLY_API_KEY = env("INSTANTLY_API_KEY")
INSTANTLY_CAMPAIGN_ID = env("INSTANTLY_CAMPAIGN_ID")
POSTAL_ADDRESS = env("POSTAL_ADDRESS", "")  # CAN-SPAM requires a physical address in every email
META_ACCESS_TOKEN = env("META_ACCESS_TOKEN")
META_AD_ACCOUNT_ID = env("META_AD_ACCOUNT_ID")
META_PIXEL_ID = env("META_PIXEL_ID")
META_CATALOG_ID = env("META_CATALOG_ID")
