"""
Seed logo_url for catalogue_vendor and catalogue_product.

For each vendor:
  1. Look up a known public domain from VENDOR_DOMAINS.
  2. Try Clearbit Logo API (https://logo.clearbit.com/<domain>) — returns PNG.
  3. On success: save PNG to apps/tenant/public/logos/<slug>.png,
                 set logo_url = '/logos/<slug>.png'.
  4. On failure or missing domain: generate a minimal SVG monogram,
                 save to apps/tenant/public/logos/<slug>.svg,
                 set logo_url = '/logos/<slug>.svg'.

Products inherit their vendor's logo_url (products in this catalogue are
identified by vendor brand; no product-specific logos exist in the seed).

The "SmokeVendor-*" dev artifact is skipped (logo_url stays NULL).

Idempotent: re-running overwrites logo files and re-applies DB values.
"""

from __future__ import annotations

import re
import time
import urllib.request
import urllib.error
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import CatalogueVendor, CatalogueProduct
from scripts.seed.common import make_engine, _find_root

# ── Project paths ────────────────────────────────────────────────────────────

PROJECT_ROOT = _find_root(Path(__file__).resolve())
LOGOS_DIR = PROJECT_ROOT / "apps" / "tenant" / "public" / "logos"

# ── Domain mapping (vendor name → Clearbit-compatible domain) ────────────────

VENDOR_DOMAINS: dict[str, str] = {
    "ABBYY":                          "abbyy.com",
    "Adobe":                          "adobe.com",
    "Amazon Web Services":            "aws.amazon.com",
    "Anthropic":                      "anthropic.com",
    "Atlassian":                      "atlassian.com",
    "Box":                            "box.com",
    "Checkr":                         "checkr.com",
    "Cohere":                         "cohere.com",
    "Copy.ai":                        "copy.ai",
    "CrowdStrike":                    "crowdstrike.com",
    "Darktrace":                      "darktrace.com",
    "Databricks":                     "databricks.com",
    "DeepL":                          "deepl.com",
    "Eightfold AI":                   "eightfold.ai",
    "ElevenLabs":                     "elevenlabs.io",
    "Fireflies.ai":                   "fireflies.ai",
    "Freshworks":                     "freshworks.com",
    "Glean":                          "glean.com",
    "Gong":                           "gong.io",
    "Google":                         "google.com",
    "Grammarly":                      "grammarly.com",
    "Guru":                           "getguru.com",
    "Harvey AI":                      "harvey.ai",
    "HireVue":                        "hirevue.com",
    "HubSpot":                        "hubspot.com",
    "IBM":                            "ibm.com",
    "Intercom":                       "intercom.com",
    "Jasper":                         "jasper.ai",
    "Leena AI":                       "leena.ai",
    "LexisNexis":                     "lexisnexis.com",
    "Microsoft":                      "microsoft.com",
    "Midjourney":                     "midjourney.com",
    "Mistral AI":                     "mistral.ai",
    "Moveworks":                      "moveworks.com",
    "Notion":                         "notion.so",
    "OpenAI":                         "openai.com",
    "Oracle":                         "oracle.com",
    "Otter.ai":                       "otter.ai",
    "Outreach":                       "outreach.io",
    "Palantir Technologies":          "palantir.com",
    "Paradox":                        "paradox.ai",
    "Pendo":                          "pendo.io",
    "Perplexity AI":                  "perplexity.ai",
    "Phenom People":                  "phenom.com",
    "Relativity":                     "relativity.com",
    "Runway":                         "runwayml.com",
    "Salesforce":                     "salesforce.com",
    "SAP":                            "sap.com",
    "Scale AI":                       "scale.com",
    "ServiceNow":                     "servicenow.com",
    "Slack Technologies (Salesforce)":"slack.com",
    "Snowflake":                      "snowflake.com",
    "Stability AI":                   "stability.ai",
    "Synthesia":                      "synthesia.io",
    "Textio":                         "textio.com",
    "ThoughtSpot":                    "thoughtspot.com",
    "UiPath":                         "uipath.com",
    "Workday":                        "workday.com",
    "Writer":                         "writer.com",
    "Zendesk":                        "zendesk.com",
    "Zoom":                           "zoom.us",
}

# Dev artifacts: skip entirely (logo_url stays NULL).
SKIP_VENDORS: set[str] = {"SmokeVendor-cc3672"}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _slug(name: str) -> str:
    """Normalise vendor name to a URL-safe slug."""
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _initials(name: str) -> str:
    words = name.strip().split()
    return "".join(w[0].upper() for w in words[:2] if w)


def _svg_monogram(name: str) -> bytes:
    """Generate a simple 80×80 SVG monogram (neutral, no brand colours)."""
    letters = _initials(name)
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 80 80">'
        '<rect width="80" height="80" rx="8" fill="#F0F2F4"/>'
        f'<text x="40" y="52" font-family="system-ui,sans-serif" font-size="28" '
        f'font-weight="600" fill="#6B7280" text-anchor="middle">{letters}</text>'
        "</svg>"
    )
    return svg.encode("utf-8")


def _fetch_logo(domain: str, timeout: int = 6) -> bytes | None:
    """
    Return raw PNG bytes via Google's favicon service (128px), or None on failure.

    Google returns a real 128×128 PNG for any domain it has indexed.
    The response is always 200 but may be a generic globe icon for unknown
    domains; that's still acceptable (distinguishable from NULL in UI).
    """
    url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    req = urllib.request.Request(url, headers={"User-Agent": "IronTrust-seed/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                content_type = resp.headers.get("Content-Type", "")
                if "image" in content_type:
                    return resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        pass
    return None


# ── Core logic ───────────────────────────────────────────────────────────────

def _seed_vendor_logo(vendor: CatalogueVendor) -> str | None:
    """
    Download or generate the logo for one vendor.
    Returns the relative logo_url (e.g. '/logos/adobe.png') or None for skipped vendors.
    Writes the file to LOGOS_DIR.
    """
    if vendor.name in SKIP_VENDORS:
        return None

    slug = _slug(vendor.name)
    domain = VENDOR_DOMAINS.get(vendor.name)

    logo_bytes: bytes | None = None
    extension = "svg"

    if domain:
        logo_bytes = _fetch_logo(domain)
        if logo_bytes:
            extension = "png"
            print(f"    ✓ fetched   {vendor.name} ({domain})")
        else:
            print(f"    ~ fallback  {vendor.name} ({domain}) — SVG monogram")
    else:
        print(f"    ~ no domain {vendor.name} — SVG monogram")

    if logo_bytes is None:
        logo_bytes = _svg_monogram(vendor.name)

    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    dest = LOGOS_DIR / f"{slug}.{extension}"
    dest.write_bytes(logo_bytes)

    return f"/logos/{slug}.{extension}"


def main(session: Session | None = None) -> None:
    own = session is None
    if own:
        session = Session(make_engine())

    try:
        vendors = session.scalars(select(CatalogueVendor)).all()
        print(f"  Processing {len(vendors)} vendors …")

        vendor_logo: dict[str, str | None] = {}  # vendor.id → logo_url

        for vendor in vendors:
            logo_url = _seed_vendor_logo(vendor)
            vendor.logo_url = logo_url
            vendor_logo[str(vendor.id)] = logo_url
            # Clearbit asks to be polite; 200ms between requests is fine.
            time.sleep(0.2)

        session.flush()

        # Propagate vendor logo_url to all products owned by that vendor.
        products = session.scalars(select(CatalogueProduct)).all()
        for product in products:
            product.logo_url = vendor_logo.get(str(product.vendor_id))

        if own:
            session.commit()

        n_with_logo = sum(1 for v in vendor_logo.values() if v)
        print(
            f"  logos: {n_with_logo}/{len(vendors)} vendors with real/generated logo; "
            f"{len(products)} products updated"
        )
    finally:
        if own:
            session.close()


if __name__ == "__main__":
    main()
