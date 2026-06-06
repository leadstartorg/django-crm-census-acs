"""
Census Bureau data utility for DjangoCRM.

Two-step flow:
  1. Census Geocoder API  →  raw address  →  state FIPS + tract FIPS
  2. ACS 5-Year Data API  →  FIPS codes  →  demographic / income metrics

Why FIPS codes?
  The Census Data API does NOT accept free-form geographic strings such as
  "Atlanta, GA". All queries are keyed on Federal Information Processing
  Series (FIPS) codes – e.g. Georgia = "13", Atlanta place FIPS = "04000".
  The Geocoder step converts a human address into those codes automatically,
  so callers never need to look them up manually.

Why ACS 5-Year (not 1-Year)?
  ACS 5-year estimates are available for every geography down to census tract
  level, whereas 1-year estimates are only published for areas with ≥65 000
  population.  Tract-level precision is needed to describe a specific address.

Why table B03002?
  B03002 "Hispanic or Latino Origin by Race" is the canonical table for
  race/ethnicity because it cleanly separates Hispanic/Latino identity from
  non-Hispanic White / Black / Asian categories, avoiding the double-counting
  that occurs with the simpler B02001 table.

JIT / Lazy-loading pattern:
  `fetch_census_data_for_obj()` is called from the detail-view.  It checks
  `is_census_processed` first; if already True it returns immediately, so the
  DB hit is the only cost on every subsequent page view.  On the very first
  view it calls the two external APIs, writes results to the object, sets the
  flag, and saves – all in one `update_fields` call to minimise DB writes.
"""

import logging
import urllib.parse
from typing import Optional

import urllib.request
import json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ACS variable codes
# ---------------------------------------------------------------------------
# B19013_001E  Median household income (dollars)
# B03002_001E  Total population                          (B03002 denominator)
# B03002_003E  Non-Hispanic White alone
# B03002_004E  Non-Hispanic Black / African-American alone
# B03002_006E  Non-Hispanic Asian alone
# B03002_012E  Hispanic or Latino (of any race)

ACS_VARIABLES = (
    "B19013_001E",
    "B03002_001E",
    "B03002_003E",
    "B03002_004E",
    "B03002_006E",
    "B03002_012E",
)

GEOCODER_URL = (
    "https://geocoding.geo.census.gov/geocoder/geographies/address"
    "?benchmark=Public_AR_Current"
    "&vintage=Current_Current"
    "&layers=Census%20Tracts"
    "&format=json"
)

ACS_URL_TEMPLATE = (
    "https://api.census.gov/data/2022/acs/acs5"
    "?get={variables}"
    "&for=tract:{tract}"
    "&in=state:{state}%20county:{county}"
    "&key={api_key}"
)

ACS_URL_TEMPLATE_NO_KEY = (
    "https://api.census.gov/data/2022/acs/acs5"
    "?get={variables}"
    "&for=tract:{tract}"
    "&in=state:{state}%20county:{county}"
)

# ---------------------------------------------------------------------------
# Step 1 – Geocoder
# ---------------------------------------------------------------------------


def geocode_address(
    street: str,
    city: str = "",
    state: str = "",
    zipcode: str = "",
) -> Optional[dict]:
    """
    Call the Census Geocoder to convert a raw address into FIPS codes.

    Returns a dict with keys:
        state   – 2-digit state FIPS  (e.g. "13" for Georgia)
        county  – 3-digit county FIPS (e.g. "121" for Fulton County)
        tract   – 6-digit census tract FIPS
    or None if geocoding fails / address not matched.
    """
    if not street:
        return None

    params = urllib.parse.urlencode({
        "street": street,
        "city": city,
        "state": state,
        "zip": zipcode,
    })
    url = f"{GEOCODER_URL}&{params}"

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        logger.warning("Census Geocoder request failed: %s", exc)
        return None

    try:
        matches = data["result"]["addressMatches"]
        if not matches:
            logger.info("Census Geocoder: no match for address '%s, %s, %s'",
                        street, city, state)
            return None
        geo = matches[0]["geographies"]["Census Tracts"][0]
        return {
            "state": geo["STATE"],
            "county": geo["COUNTY"],
            "tract": geo["TRACT"],
        }
    except (KeyError, IndexError) as exc:
        logger.warning("Census Geocoder response parse error: %s | data: %s",
                       exc, data)
        return None


# ---------------------------------------------------------------------------
# Step 2 – ACS 5-Year Data
# ---------------------------------------------------------------------------


def fetch_acs_data(state: str, county: str, tract: str,
                   api_key: str = "") -> Optional[dict]:
    """
    Query ACS 5-year estimates for the given census tract.

    Returns a dict with:
        median_income        – int, median household income in USD
        population           – int, total population
        pct_white            – float, % Non-Hispanic White
        pct_black            – float, % Non-Hispanic Black
        pct_asian            – float, % Non-Hispanic Asian
        pct_hispanic         – float, % Hispanic or Latino (any race)
    or None on failure.
    """
    variables = ",".join(ACS_VARIABLES)
    if api_key:
        url = ACS_URL_TEMPLATE.format(
            variables=variables,
            state=state,
            county=county,
            tract=tract,
            api_key=api_key,
        )
    else:
        url = ACS_URL_TEMPLATE_NO_KEY.format(
            variables=variables,
            state=state,
            county=county,
            tract=tract,
        )

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            rows = json.loads(resp.read().decode())
    except Exception as exc:
        logger.warning("ACS data request failed: %s | url: %s", exc, url)
        return None

    # rows[0] = header, rows[1] = data
    if not rows or len(rows) < 2:
        logger.info("ACS returned no data for state=%s county=%s tract=%s",
                    state, county, tract)
        return None

    try:
        header = rows[0]
        values = rows[1]
        row = dict(zip(header, values))

        def safe_int(key: str) -> int:
            v = row.get(key)
            try:
                return max(int(v), 0)          # Census returns -666666666 for N/A
            except (TypeError, ValueError):
                return 0

        population = safe_int("B03002_001E")
        median_income = safe_int("B19013_001E")
        white = safe_int("B03002_003E")
        black = safe_int("B03002_004E")
        asian = safe_int("B03002_006E")
        hispanic = safe_int("B03002_012E")

        def pct(numerator: int) -> float:
            if population <= 0:
                return 0.0
            return round(numerator / population * 100, 1)

        return {
            "median_income": median_income if median_income > 0 else None,
            "population": population if population > 0 else None,
            "pct_white": pct(white),
            "pct_black": pct(black),
            "pct_asian": pct(asian),
            "pct_hispanic": pct(hispanic),
        }
    except Exception as exc:
        logger.warning("ACS data parse error: %s | rows: %s", exc, rows)
        return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def fetch_census_data_for_obj(obj) -> bool:
    """
    JIT/Lazy-load census data onto any CRM object that has census fields.

    Designed to be called from change_view BEFORE the template is rendered.
    Safe to call on every page hit – returns immediately (True) if already
    processed.  Returns False when data could not be retrieved (bad address,
    API error, non-US address, etc.), but still sets `is_census_processed`
    so we do not hammer the external API on every subsequent view of the
    same record.

    Address resolution priority:
      • Company  – uses its own address / city_name / region fields
      • Contact  – uses its own address fields (may fall back to company)
      • Lead     – uses company_address if personal address is blank
    """
    from django.conf import settings  # local import avoids circular imports

    if getattr(obj, "is_census_processed", True):
        return True                          # already done, exit fast

    # Build address parts from the object
    street = (getattr(obj, "address", "") or "").strip()
    city = (getattr(obj, "city_name", "") or "").strip()
    state_region = (getattr(obj, "region", "") or "").strip()
    zipcode = ""

    # For Lead, prefer company address if personal address is blank
    if not street and hasattr(obj, "company_address"):
        street = (obj.company_address or "").strip()

    # For Contact, inherit company address if nothing on the contact itself
    if not street and hasattr(obj, "company") and obj.company:
        street = (obj.company.address or "").strip()
        if not city:
            city = (obj.company.city_name or "").strip()
        if not state_region:
            state_region = (obj.company.region or "").strip()

    # Only attempt geocoding for US records
    country = getattr(obj, "country", None)
    if country and hasattr(country, "name"):
        country_name = (country.name or "").upper()
        if country_name and "UNITED STATES" not in country_name and "USA" not in country_name and "US" != country_name:
            _mark_processed(obj)
            return False

    if not street:
        _mark_processed(obj)
        return False

    # --- Step 1: Geocode ---
    fips = geocode_address(
        street=street,
        city=city,
        state=state_region,
        zipcode=zipcode,
    )
    if not fips:
        _mark_processed(obj)
        return False

    # --- Step 2: ACS lookup ---
    api_key = getattr(settings, "CENSUS_API_KEY", "")
    acs = fetch_acs_data(
        state=fips["state"],
        county=fips["county"],
        tract=fips["tract"],
        api_key=api_key,
    )
    if not acs:
        _mark_processed(obj)
        return False

    # --- Write results ---
    obj.census_state_fips = fips["state"]
    obj.census_county_fips = fips["county"]
    obj.census_tract = fips["tract"]
    obj.census_median_income = acs["median_income"]
    obj.census_population = acs["population"]
    obj.census_pct_white = acs["pct_white"]
    obj.census_pct_black = acs["pct_black"]
    obj.census_pct_asian = acs["pct_asian"]
    obj.census_pct_hispanic = acs["pct_hispanic"]
    obj.is_census_processed = True

    obj.save(update_fields=[
        "census_state_fips",
        "census_county_fips",
        "census_tract",
        "census_median_income",
        "census_population",
        "census_pct_white",
        "census_pct_black",
        "census_pct_asian",
        "census_pct_hispanic",
        "is_census_processed",
    ])
    return True


def _mark_processed(obj) -> None:
    """Mark the object as processed even when no data was found.

    This prevents the API from being called again on the next page view
    for records with invalid or non-US addresses (the edge case described
    in the spec).
    """
    obj.is_census_processed = True
    obj.save(update_fields=["is_census_processed"])


# ---------------------------------------------------------------------------
# Admin display helper – shared across CompanyAdmin, ContactAdmin, LeadAdmin
# ---------------------------------------------------------------------------

def render_census_panel(obj) -> str:
    """
    Return an HTML string for the admin read-only census panel.

    Renders a compact two-column table styled with CRM CSS variables so it
    looks native to the DjangoCRM admin UI.  Shows a 'pending' message when
    the data has not been loaded yet (is_census_processed = False).
    """
    from django.utils.safestring import mark_safe
    from django.utils.translation import gettext as _

    if not getattr(obj, 'is_census_processed', False):
        return mark_safe(
            '<span style="color: var(--body-quiet-color);">'
            '<i class="material-icons" style="font-size:16px;vertical-align:middle;">'
            'hourglass_empty</i>&nbsp;'
            + _('Census data will load on first profile view.')
            + '</span>'
        )

    income = getattr(obj, 'census_median_income', None)
    population = getattr(obj, 'census_population', None)
    pct_white = getattr(obj, 'census_pct_white', None)
    pct_black = getattr(obj, 'census_pct_black', None)
    pct_asian = getattr(obj, 'census_pct_asian', None)
    pct_hispanic = getattr(obj, 'census_pct_hispanic', None)
    state_fips = getattr(obj, 'census_state_fips', '') or ''
    county_fips = getattr(obj, 'census_county_fips', '') or ''
    tract = getattr(obj, 'census_tract', '') or ''

    if not any([income, population, pct_white, pct_black, pct_asian, pct_hispanic]):
        return mark_safe(
            '<span style="color: var(--body-quiet-color);">'
            '<i class="material-icons" style="font-size:16px;vertical-align:middle;">'
            'info_outline</i>&nbsp;'
            + _('No census data available for this address.')
            + '</span>'
        )

    def fmt_pct(val):
        return f'{val}%' if val is not None else '—'

    def fmt_int(val, prefix=''):
        if val is None:
            return '—'
        return f'{prefix}{val:,}'

    fips_str = ''
    if state_fips or county_fips or tract:
        fips_str = (
            f'<tr><td style="color:var(--body-quiet-color);padding:2px 12px 2px 0;">'
            f'<small>{_("FIPS")}</small></td>'
            f'<td><small>state&nbsp;{state_fips}&nbsp;/ '
            f'county&nbsp;{county_fips}&nbsp;/ tract&nbsp;{tract}</small></td></tr>'
        )

    html = (
        '<table style="border-collapse:collapse;font-size:0.9em;">'
        '<tbody>'
        f'<tr>'
        f'<td style="color:var(--body-quiet-color);padding:4px 12px 4px 0;">'
        f'{_("Median household income")}</td>'
        f'<td><strong>{fmt_int(income, "$")}</strong></td>'
        f'</tr>'
        f'<tr>'
        f'<td style="color:var(--body-quiet-color);padding:4px 12px 4px 0;">'
        f'{_("Tract population")}</td>'
        f'<td>{fmt_int(population)}</td>'
        f'</tr>'
        f'<tr>'
        f'<td style="color:var(--body-quiet-color);padding:4px 12px 4px 0;">'
        f'{_("Non-Hispanic White")}</td>'
        f'<td>{fmt_pct(pct_white)}</td>'
        f'</tr>'
        f'<tr>'
        f'<td style="color:var(--body-quiet-color);padding:4px 12px 4px 0;">'
        f'{_("Non-Hispanic Black")}</td>'
        f'<td>{fmt_pct(pct_black)}</td>'
        f'</tr>'
        f'<tr>'
        f'<td style="color:var(--body-quiet-color);padding:4px 12px 4px 0;">'
        f'{_("Non-Hispanic Asian")}</td>'
        f'<td>{fmt_pct(pct_asian)}</td>'
        f'</tr>'
        f'<tr>'
        f'<td style="color:var(--body-quiet-color);padding:4px 12px 4px 0;">'
        f'{_("Hispanic or Latino")}</td>'
        f'<td>{fmt_pct(pct_hispanic)}</td>'
        f'</tr>'
        f'{fips_str}'
        '</tbody></table>'
        '<p style="margin-top:6px;font-size:0.8em;color:var(--body-quiet-color);">'
        + _('Source: US Census Bureau ACS 5-Year Estimates, table B03002. Census tract level data.')
        + '</p>'
    )
    return mark_safe(html)
