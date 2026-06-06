"""
Census Bureau data utility for DjangoCRM — EXPANDED v2.

15 data points across 8 topic areas:
  1. Population & Age        – total pop, median age
  2. Race / Ethnicity        – White, Black, Asian, Hispanic
  3. Income                  – median household, per capita, poverty rate
  4. Education               – % bachelor's degree or higher
  5. Employment              – unemployment rate
  6. Housing                 – median home value, % owner-occupied
  7. Commuting               – mean travel time to work
  8. Language                – % speak English less than "very well"
  9. Health Insurance        – % without health insurance

ACS variable reference:
  B01003_001E  Total population
  B01002_001E  Median age
  B03002_003E  Non-Hispanic White alone
  B03002_004E  Non-Hispanic Black / African-American alone
  B03002_006E  Non-Hispanic Asian alone
  B03002_012E  Hispanic or Latino (of any race)
  B03002_001E  Race/ethnicity denominator
  B19013_001E  Median household income
  B19301_001E  Per capita income
  B17001_002E  Population below poverty level
  B17001_001E  Poverty denominator
  B15003_022E  Bachelor's degree
  B15003_023E  Master's degree
  B15003_024E  Professional school degree
  B15003_025E  Doctorate degree
  B15003_001E  Education denominator (pop 25+)
  B23025_005E  Unemployed (civilian labor force)
  B23025_002E  Civilian labor force (employment denominator)
  B25077_001E  Median home value
  B25003_002E  Owner-occupied housing units
  B25003_001E  Housing tenure denominator
  B08136_001E  Aggregate travel time to work (minutes)
  B08301_001E  Workers 16+ (commute denominator)
  B16004_004E  Speak English less than very well, age 5-17
  B16004_026E  Speak English less than very well, age 18-64
  B16004_048E  Speak English less than very well, age 65+
  B16004_001E  Language denominator
  B27001_005E  No health insurance, male under 6
  B27001_008E  No health insurance, male 6-18
  ... (see ACS_VARIABLES tuple below for full list)
"""

import logging
import urllib.parse
from typing import Optional
import urllib.request
import json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ACS variable codes — all 15 data points
# ---------------------------------------------------------------------------

ACS_VARIABLES = (
    # Population & Age
    "B01003_001E",   # Total population
    "B01002_001E",   # Median age

    # Race / Ethnicity (B03002 avoids double-counting)
    "B03002_001E",   # Total (denominator)
    "B03002_003E",   # Non-Hispanic White
    "B03002_004E",   # Non-Hispanic Black
    "B03002_006E",   # Non-Hispanic Asian
    "B03002_012E",   # Hispanic or Latino

    # Income & Poverty
    "B19013_001E",   # Median household income
    "B19301_001E",   # Per capita income
    "B17001_001E",   # Poverty status denominator
    "B17001_002E",   # Below poverty level

    # Education (pop 25+)
    "B15003_001E",   # Education denominator
    "B15003_022E",   # Bachelor's degree
    "B15003_023E",   # Master's degree
    "B15003_024E",   # Professional school degree
    "B15003_025E",   # Doctorate degree

    # Employment
    "B23025_002E",   # Civilian labor force
    "B23025_005E",   # Unemployed

    # Housing
    "B25077_001E",   # Median home value
    "B25003_001E",   # Housing tenure denominator
    "B25003_002E",   # Owner-occupied

    # Commuting
    "B08136_001E",   # Aggregate travel time to work (minutes)
    "B08301_001E",   # Workers 16+ who commute

    # Language
    "B16004_001E",   # Language denominator (pop 5+)
    "B16004_004E",   # English < very well, age 5-17
    "B16004_026E",   # English < very well, age 18-64
    "B16004_048E",   # English < very well, age 65+

    # Health Insurance (uninsured — sum of male + female age bands)
    "B27001_001E",   # Health insurance denominator
    "B27001_005E",   # No insurance male <6
    "B27001_008E",   # No insurance male 6-18
    "B27001_011E",   # No insurance male 19-25
    "B27001_014E",   # No insurance male 26-34
    "B27001_017E",   # No insurance male 35-44
    "B27001_020E",   # No insurance male 45-54
    "B27001_023E",   # No insurance male 55-64
    "B27001_026E",   # No insurance male 65-74
    "B27001_029E",   # No insurance male 75+
    "B27001_033E",   # No insurance female <6
    "B27001_036E",   # No insurance female 6-18
    "B27001_039E",   # No insurance female 19-25
    "B27001_042E",   # No insurance female 26-34
    "B27001_045E",   # No insurance female 35-44
    "B27001_048E",   # No insurance female 45-54
    "B27001_051E",   # No insurance female 55-64
    "B27001_054E",   # No insurance female 65-74
    "B27001_057E",   # No insurance female 75+
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
# Step 1 — Geocoder
# ---------------------------------------------------------------------------

def geocode_address(
    street: str,
    city: str = "",
    state: str = "",
    zipcode: str = "",
) -> Optional[dict]:
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
            logger.info("Census Geocoder: no match for '%s, %s, %s'",
                        street, city, state)
            return None
        geo = matches[0]["geographies"]["Census Tracts"][0]
        return {
            "state": geo["STATE"],
            "county": geo["COUNTY"],
            "tract": geo["TRACT"],
        }
    except (KeyError, IndexError) as exc:
        logger.warning("Census Geocoder parse error: %s | data: %s", exc, data)
        return None


# ---------------------------------------------------------------------------
# Step 2 — ACS 5-Year Data
# ---------------------------------------------------------------------------

def fetch_acs_data(state: str, county: str, tract: str,
                   api_key: str = "") -> Optional[dict]:
    variables = ",".join(ACS_VARIABLES)
    if api_key:
        url = ACS_URL_TEMPLATE.format(
            variables=variables, state=state,
            county=county, tract=tract, api_key=api_key,
        )
    else:
        url = ACS_URL_TEMPLATE_NO_KEY.format(
            variables=variables, state=state,
            county=county, tract=tract,
        )

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            rows = json.loads(resp.read().decode())
    except Exception as exc:
        logger.warning("ACS data request failed: %s | url: %s", exc, url)
        return None

    if not rows or len(rows) < 2:
        return None

    try:
        header = rows[0]
        values = rows[1]
        row = dict(zip(header, values))

        def safe_int(key: str) -> int:
            v = row.get(key)
            try:
                result = int(v)
                return max(result, 0)   # Census uses -666666666 for N/A
            except (TypeError, ValueError):
                return 0

        def safe_float(key: str) -> float:
            v = row.get(key)
            try:
                result = float(v)
                return max(result, 0.0)
            except (TypeError, ValueError):
                return 0.0

        def pct(numerator: int, denominator: int) -> Optional[float]:
            if denominator <= 0:
                return None
            return round(numerator / denominator * 100, 1)

        # Population & Age
        population = safe_int("B01003_001E")
        median_age = safe_float("B01002_001E") or None

        # Race / Ethnicity
        race_total = safe_int("B03002_001E")
        white = safe_int("B03002_003E")
        black = safe_int("B03002_004E")
        asian = safe_int("B03002_006E")
        hispanic = safe_int("B03002_012E")

        # Income & Poverty
        median_income = safe_int("B19013_001E") or None
        per_capita_income = safe_int("B19301_001E") or None
        poverty_denom = safe_int("B17001_001E")
        poverty_count = safe_int("B17001_002E")

        # Education
        edu_denom = safe_int("B15003_001E")
        college = (safe_int("B15003_022E") + safe_int("B15003_023E") +
                   safe_int("B15003_024E") + safe_int("B15003_025E"))

        # Employment
        labor_force = safe_int("B23025_002E")
        unemployed = safe_int("B23025_005E")

        # Housing
        median_home_value = safe_int("B25077_001E") or None
        housing_denom = safe_int("B25003_001E")
        owner_occupied = safe_int("B25003_002E")

        # Commuting
        agg_commute = safe_int("B08136_001E")
        commuters = safe_int("B08301_001E")
        mean_commute = round(agg_commute / commuters, 1) if commuters > 0 else None

        # Language
        lang_denom = safe_int("B16004_001E")
        limited_english = (safe_int("B16004_004E") +
                           safe_int("B16004_026E") +
                           safe_int("B16004_048E"))

        # Health Insurance — sum all uninsured age/sex bands
        hi_denom = safe_int("B27001_001E")
        uninsured = sum(safe_int(v) for v in [
            "B27001_005E", "B27001_008E", "B27001_011E", "B27001_014E",
            "B27001_017E", "B27001_020E", "B27001_023E", "B27001_026E",
            "B27001_029E", "B27001_033E", "B27001_036E", "B27001_039E",
            "B27001_042E", "B27001_045E", "B27001_048E", "B27001_051E",
            "B27001_054E", "B27001_057E",
        ] if v in row)

        return {
            # Population & Age
            "population": population or None,
            "median_age": median_age,
            # Race / Ethnicity
            "pct_white": pct(white, race_total),
            "pct_black": pct(black, race_total),
            "pct_asian": pct(asian, race_total),
            "pct_hispanic": pct(hispanic, race_total),
            # Income
            "median_income": median_income,
            "per_capita_income": per_capita_income,
            "pct_poverty": pct(poverty_count, poverty_denom),
            # Education
            "pct_college": pct(college, edu_denom),
            # Employment
            "pct_unemployed": pct(unemployed, labor_force),
            # Housing
            "median_home_value": median_home_value,
            "pct_owner_occupied": pct(owner_occupied, housing_denom),
            # Commuting
            "mean_commute_minutes": mean_commute,
            # Language
            "pct_limited_english": pct(limited_english, lang_denom),
            # Health Insurance
            "pct_uninsured": pct(uninsured, hi_denom),
        }

    except Exception as exc:
        logger.warning("ACS data parse error: %s | rows: %s", exc, rows)
        return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def fetch_census_data_for_obj(obj) -> bool:
    from django.conf import settings

    if getattr(obj, "is_census_processed", True):
        return True

    # Build address — prefer city FK over city_name text field
    street = (getattr(obj, "address", "") or "").strip()

    city_obj = getattr(obj, "city", None)
    if city_obj and hasattr(city_obj, "name"):
        city = (city_obj.name or "").strip()
    else:
        city = (getattr(obj, "city_name", "") or "").strip()

    state_region = (getattr(obj, "region", "") or "").strip()
    zipcode = ""

    if not street and hasattr(obj, "company_address"):
        street = (obj.company_address or "").strip()

    if not street and hasattr(obj, "company") and obj.company:
        street = (obj.company.address or "").strip()
        if not city:
            city_obj2 = getattr(obj.company, "city", None)
            city = (city_obj2.name if city_obj2 and hasattr(city_obj2, "name")
                    else obj.company.city_name or "").strip()
        if not state_region:
            state_region = (obj.company.region or "").strip()

    # US-only
    country = getattr(obj, "country", None)
    if country and hasattr(country, "name"):
        country_name = (country.name or "").upper()
        if country_name and "UNITED STATES" not in country_name and "USA" not in country_name and country_name != "US":
            _mark_processed(obj)
            return False

    if not street:
        _mark_processed(obj)
        return False

    fips = geocode_address(street=street, city=city, state=state_region, zipcode=zipcode)
    if not fips:
        _mark_processed(obj)
        return False

    api_key = getattr(settings, "US_CENSUS_API_KEY", "") or getattr(settings, "CENSUS_API_KEY", "")
    acs = fetch_acs_data(state=fips["state"], county=fips["county"],
                         tract=fips["tract"], api_key=api_key)
    if not acs:
        _mark_processed(obj)
        return False

    # Write all 15+ fields
    obj.census_state_fips = fips["state"]
    obj.census_county_fips = fips["county"]
    obj.census_tract = fips["tract"]
    obj.census_median_income = acs["median_income"]
    obj.census_population = acs["population"]
    obj.census_pct_white = acs["pct_white"]
    obj.census_pct_black = acs["pct_black"]
    obj.census_pct_asian = acs["pct_asian"]
    obj.census_pct_hispanic = acs["pct_hispanic"]
    # New fields (migration 0013 adds these)
    obj.census_median_age = acs["median_age"]
    obj.census_per_capita_income = acs["per_capita_income"]
    obj.census_pct_poverty = acs["pct_poverty"]
    obj.census_pct_college = acs["pct_college"]
    obj.census_pct_unemployed = acs["pct_unemployed"]
    obj.census_median_home_value = acs["median_home_value"]
    obj.census_pct_owner_occupied = acs["pct_owner_occupied"]
    obj.census_mean_commute_minutes = acs["mean_commute_minutes"]
    obj.census_pct_limited_english = acs["pct_limited_english"]
    obj.census_pct_uninsured = acs["pct_uninsured"]
    obj.is_census_processed = True

    obj.save(update_fields=[
        "census_state_fips", "census_county_fips", "census_tract",
        "census_median_income", "census_population",
        "census_pct_white", "census_pct_black", "census_pct_asian", "census_pct_hispanic",
        "census_median_age", "census_per_capita_income", "census_pct_poverty",
        "census_pct_college", "census_pct_unemployed",
        "census_median_home_value", "census_pct_owner_occupied",
        "census_mean_commute_minutes", "census_pct_limited_english",
        "census_pct_uninsured",
        "is_census_processed",
    ])
    return True


def _mark_processed(obj) -> None:
    obj.is_census_processed = True
    obj.save(update_fields=["is_census_processed"])


# ---------------------------------------------------------------------------
# Admin display panel
# ---------------------------------------------------------------------------

def render_census_panel(obj) -> str:
    from django.utils.safestring import mark_safe
    from django.utils.translation import gettext as _

    if not getattr(obj, "is_census_processed", False):
        return mark_safe(
            '<span style="color: var(--body-quiet-color);">'
            '<i class="material-icons" style="font-size:16px;vertical-align:middle;">'
            "hourglass_empty</i>&nbsp;"
            + _("Census data will load on first profile view.")
            + "</span>"
        )

    def g(field):
        return getattr(obj, field, None)

    # Check if any data present
    if not any([g("census_median_income"), g("census_population"), g("census_pct_white")]):
        return mark_safe(
            '<span style="color: var(--body-quiet-color);">'
            '<i class="material-icons" style="font-size:16px;vertical-align:middle;">'
            "info_outline</i>&nbsp;"
            + _("No census data available for this address.")
            + "</span>"
        )

    def fmt_usd(val):
        return f"${val:,}" if val else "—"

    def fmt_pct(val):
        return f"{val}%" if val is not None else "—"

    def fmt_num(val):
        return f"{val:,}" if val else "—"

    def fmt_val(val, suffix=""):
        return f"{val}{suffix}" if val is not None else "—"

    state_fips = g("census_state_fips") or ""
    county_fips = g("census_county_fips") or ""
    tract = g("census_tract") or ""

    rows = [
        # Section: Population & Age
        ("section", "Population & Age"),
        (_("Tract population"),        fmt_num(g("census_population"))),
        (_("Median age"),              fmt_val(g("census_median_age"), " yrs")),
        # Section: Race / Ethnicity
        ("section", "Race / Ethnicity"),
        (_("Non-Hispanic White"),      fmt_pct(g("census_pct_white"))),
        (_("Non-Hispanic Black"),      fmt_pct(g("census_pct_black"))),
        (_("Non-Hispanic Asian"),      fmt_pct(g("census_pct_asian"))),
        (_("Hispanic or Latino"),      fmt_pct(g("census_pct_hispanic"))),
        # Section: Income & Poverty
        ("section", "Income & Poverty"),
        (_("Median household income"), fmt_usd(g("census_median_income"))),
        (_("Per capita income"),       fmt_usd(g("census_per_capita_income"))),
        (_("Below poverty level"),     fmt_pct(g("census_pct_poverty"))),
        # Section: Education
        ("section", "Education"),
        (_("Bachelor's degree or higher"), fmt_pct(g("census_pct_college"))),
        # Section: Employment
        ("section", "Employment"),
        (_("Unemployment rate"),       fmt_pct(g("census_pct_unemployed"))),
        # Section: Housing
        ("section", "Housing"),
        (_("Median home value"),       fmt_usd(g("census_median_home_value"))),
        (_("Owner-occupied"),          fmt_pct(g("census_pct_owner_occupied"))),
        # Section: Commuting
        ("section", "Commuting"),
        (_("Mean commute time"),       fmt_val(g("census_mean_commute_minutes"), " min")),
        # Section: Language
        ("section", "Language"),
        (_("Limited English proficiency"), fmt_pct(g("census_pct_limited_english"))),
        # Section: Health Insurance
        ("section", "Health Insurance"),
        (_("Without health insurance"), fmt_pct(g("census_pct_uninsured"))),
    ]

    html_rows = ""
    for row in rows:
        if row[0] == "section":
            html_rows += (
                f'<tr><td colspan="2" style="padding:8px 0 2px 0;'
                f'font-weight:bold;font-size:0.8em;text-transform:uppercase;'
                f'letter-spacing:0.05em;color:var(--primary-fg);'
                f'border-top:1px solid var(--border-color);">{row[1]}</td></tr>'
            )
        else:
            label, value = row
            html_rows += (
                f'<tr>'
                f'<td style="color:var(--body-quiet-color);padding:3px 16px 3px 0;'
                f'white-space:nowrap;">{label}</td>'
                f'<td style="font-weight:500;">{value}</td>'
                f'</tr>'
            )

    fips_str = ""
    if state_fips or county_fips or tract:
        fips_str = (
            f'<tr><td colspan="2" style="padding-top:8px;font-size:0.75em;'
            f'color:var(--body-quiet-color);">'
            f'FIPS: state {state_fips} / county {county_fips} / tract {tract}'
            f"</td></tr>"
        )

    html = (
        '<table style="border-collapse:collapse;font-size:0.9em;width:100%;max-width:480px;">'
        f"<tbody>{html_rows}{fips_str}</tbody></table>"
        '<p style="margin-top:6px;font-size:0.75em;color:var(--body-quiet-color);">'
        + _("Source: US Census Bureau ACS 5-Year Estimates (2022). Census tract level.")
        + "</p>"
    )
    return mark_safe(html)
