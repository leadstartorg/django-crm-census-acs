US CENSUS BUREAU INTEGRATION FOR DJANGO-CRM  —  v2
  Neighborhood demographic data on Company, Contact, and Lead profiles
================================================================================


OVERVIEW
--------
This feature adds US Census Bureau demographic data to the DjangoCRM admin
interface for three models: Company, Contact, and Lead.

When a CRM user opens a record's detail page for the first time, the system
quietly calls two free Census Bureau APIs, writes the results to the local
database, and displays them in a collapsed fieldset labeled "Area Demographics
(US Census Bureau)." Every subsequent visit reads from the local database
with no external calls at all.

No data is fetched during bulk imports. Records imported via CSV, Excel, or
any upstream API remain untouched until someone actually opens that profile.

v2 expands from 6 demographic metrics to 15, organized into 8 topic sections.


--------------------------------------------------------------------------------
WHAT DATA IS DISPLAYED  (15 data points across 8 sections)
--------------------------------------------------------------------------------

All data is at the census tract level — a subdivision of a county typically
covering 1,200 to 8,000 residents, fine enough to describe the specific
neighborhood a business or contact is located in.

  SECTION 1 — Population & Age
  ─────────────────────────────────────────────────────────────────────────────
  Field                    ACS Variable       Description
  Tract population         B01003_001E        Total population of the tract.
  Median age               B01002_001E        Median age of tract residents.


  SECTION 2 — Race / Ethnicity
  ─────────────────────────────────────────────────────────────────────────────
  % Non-Hispanic White     B03002_003E        Share identifying as White alone,
                                              not Hispanic or Latino.
  % Non-Hispanic Black     B03002_004E        Share identifying as Black or
                                              African American alone, not
                                              Hispanic or Latino.
  % Non-Hispanic Asian     B03002_006E        Share identifying as Asian alone,
                                              not Hispanic or Latino.
  % Hispanic or Latino     B03002_012E        Share identifying as Hispanic or
                                              Latino of any race.
  Denominator              B03002_001E        Total population (race table).

  WHY TABLE B03002 AND NOT B02001?
    B02001 counts Hispanic/Latino individuals inside the White, Black, and
    Asian buckets, causing double-counting. B03002 separates Hispanic/Latino
    identity first, then counts non-Hispanic populations within each race.
    This produces clean, non-overlapping percentages.


  SECTION 3 — Income & Poverty
  ─────────────────────────────────────────────────────────────────────────────
  Median household income  B19013_001E        Annual household income at the
                                              50th percentile. US dollars.
  Per capita income        B19301_001E        Total income divided by total
                                              population. US dollars.
  % below poverty level    B17001_002E        Share of the population whose
                           B17001_001E        income falls below the federal
                                              poverty threshold.


  SECTION 4 — Education
  ─────────────────────────────────────────────────────────────────────────────
  % bachelor's or higher   B15003_022E        Combined share of residents 25+
                           B15003_023E        who hold a bachelor's, master's,
                           B15003_024E        professional school, or doctoral
                           B15003_025E        degree.
                           B15003_001E        (denominator: pop 25+)


  SECTION 5 — Employment
  ─────────────────────────────────────────────────────────────────────────────
  Unemployment rate        B23025_005E        Share of the civilian labor force
                           B23025_002E        that is actively unemployed.


  SECTION 6 — Housing
  ─────────────────────────────────────────────────────────────────────────────
  Median home value        B25077_001E        Median value of owner-occupied
                                              housing units. US dollars.
  % owner-occupied         B25003_002E        Share of occupied housing units
                           B25003_001E        that are owner-occupied (vs.
                                              renter-occupied).


  SECTION 7 — Commuting
  ─────────────────────────────────────────────────────────────────────────────
  Mean commute time        B08136_001E        Average one-way travel time to
                           B08301_001E        work in minutes, derived from
                                              aggregate commute time ÷ workers.


  SECTION 8 — Language
  ─────────────────────────────────────────────────────────────────────────────
  % limited English        B16004_004E        Share of residents age 5+ who
                           B16004_026E        speak English less than "very
                           B16004_048E        well." Sums across three age
                           B16004_001E        bands (5–17, 18–64, 65+).


  SECTION 9 — Health Insurance
  ─────────────────────────────────────────────────────────────────────────────
  % without insurance      B27001_*           Share of the population with no
                           B27001_001E        health insurance coverage. Derived
                                              by summing 18 uninsured age/sex
                                              band variables (male and female,
                                              9 age groups each).

  Internal FIPS codes (state 2-digit / county 3-digit / tract 6-digit) are
  displayed in small text below the panel for manual verification at census.gov.


--------------------------------------------------------------------------------
HOW THE DATA IS FETCHED (TWO-STEP FLOW)
--------------------------------------------------------------------------------

The Census Bureau data API does not accept geographic strings like "Atlanta, GA"
or "30301." All queries use Federal Information Processing Series (FIPS) codes.
This integration resolves them automatically in two steps.

STEP 1 — Census Geocoder API
  Endpoint: geocoding.geo.census.gov/geocoder/geographies/address
  Input:    Street address, city, state (all from the CRM record)
  Output:   State FIPS (2 digits), County FIPS (3 digits), Tract FIPS (6 digits)
  Free:     Yes. No API key required.
  Example:
    Input  → street="1040 Huff Road NW", city="Atlanta", state="Georgia"
    Output → state="13", county="121", tract="008905"

STEP 2 — ACS 5-Year Data API
  Endpoint: api.census.gov/data/2022/acs/acs5
  Input:    State, county, and tract FIPS codes from Step 1
  Output:   All 15 demographic variables listed above
  Free:     Yes. Free API key removes the ~500 req/day/IP rate limit.
  Key:      https://api.census.gov/data/key_signup.html
  Setting:  US_CENSUS_API_KEY in application_settings secret

WHY ACS 5-YEAR AND NOT 1-YEAR?
  1-year ACS is only published for areas with 65,000+ residents. Most census
  tracts are far smaller. The 5-year ACS is published for every tract in the
  country — it is the only option for address-level demographic data.


--------------------------------------------------------------------------------
HOW JIT LOADING WORKS
--------------------------------------------------------------------------------

JIT (Just-In-Time) loads data on first profile view, not on record creation.

  1. CRM user opens a Company, Contact, or Lead record.
  2. Django Admin calls change_view() for that record.
  3. change_view() calls fetch_census_data_for_obj(obj) before rendering.
  4. The function checks is_census_processed:
       - True  → return immediately. One DB read. Page loads fast.
       - False → proceed to API calls.
  5. Address fields are assembled from the record (with fallback logic).
  6. Census Geocoder API called → returns FIPS codes.
  7. ACS 5-Year API called with FIPS codes → returns 15 metrics.
  8. All results written to the record in a single save(update_fields=[...]).
  9. is_census_processed set to True in the same save call.
 10. Page renders with data. Every future visit exits at step 4.

EDGE CASE — INVALID OR MISSING ADDRESSES
  If geocoding fails or ACS returns no data, is_census_processed is still
  set to True and all census fields remain null. The panel shows:
  "No census data available for this address."
  This prevents repeated API calls for records with bad addresses.


--------------------------------------------------------------------------------
ADDRESS RESOLUTION — CITY FIELD BEHAVIOR (IMPORTANT)
--------------------------------------------------------------------------------

DjangoCRM stores city two ways on each record:

  city         FK to City model (authoritative — set via the city picker)
  city_name    Denormalized text field (can become stale if typed manually)

The geocoder uses city.name (from the FK) as the primary source, falling back
to city_name only if the FK is not set. This prevents geocoding failures caused
by stale text in city_name that does not match the FK-linked city.

If a record shows "No census data available" despite having a valid US address,
check that the city FK is set correctly (not just the city_name text field).


--------------------------------------------------------------------------------
ADDRESS RESOLUTION PRIORITY BY MODEL
--------------------------------------------------------------------------------

  COMPANY
    Primary:  address, city FK name, region
    Fallback: none

  CONTACT
    Primary:  address, city FK name, region
    Fallback: inherits address, city FK name, and region from linked Company

  LEAD
    Primary:  address, city FK name, region
    Fallback: company_address field (separate from personal address fields)
    Note:     Contact and Company fallbacks also applied if both are blank


--------------------------------------------------------------------------------
FILES
--------------------------------------------------------------------------------

  crm/utils/census_utils.py                         MODIFIED (v2)
    All API logic, address resolution, and admin panel renderer.
    Contains: geocode_address(), fetch_acs_data(),
              fetch_census_data_for_obj(), render_census_panel()

  crm/migrations/0012_census_data_fields.py         ORIGINAL
    Adds 10 DB columns to Company, Contact, Lead:
      is_census_processed, census_state_fips, census_county_fips,
      census_tract, census_median_income, census_population,
      census_pct_white, census_pct_black, census_pct_asian, census_pct_hispanic

  crm/migrations/0013_census_expanded_fields.py     NEW (v2)
    Adds 10 additional DB columns to Company, Contact, Lead:
      census_median_age, census_per_capita_income, census_pct_poverty,
      census_pct_college, census_pct_unemployed, census_median_home_value,
      census_pct_owner_occupied, census_mean_commute_minutes,
      census_pct_limited_english, census_pct_uninsured

  crm/models/company.py                             MODIFIED
  crm/models/contact.py                             MODIFIED
  crm/models/lead.py                                MODIFIED
    All 20 census fields declared on each model.

  crm/site/companyadmin.py                          MODIFIED
  crm/site/contactadmin.py                          MODIFIED
  crm/site/leadadmin.py                             MODIFIED
    Each file has: JIT trigger in change_view(), census_data_panel readonly
    field, collapsed "Area Demographics" fieldset, census_data_panel callable.


--------------------------------------------------------------------------------
INSTALLATION / UPGRADE
--------------------------------------------------------------------------------

FRESH INSTALL (no prior census integration)
  1. Copy census_utils.py to crm/utils/census_utils.py
  2. Copy both migrations to crm/migrations/
  3. Add census fields to company.py, contact.py, lead.py
  4. Add JIT trigger + panel to companyadmin.py, contactadmin.py, leadadmin.py
  5. Run: python manage.py migrate crm
  6. Add US_CENSUS_API_KEY to your application_settings secret
  7. Open any US-address record to trigger first data load

UPGRADING FROM v1 (0012 migration already applied)
  1. Replace crm/utils/census_utils.py with the v2 version
  2. Copy 0013_census_expanded_fields.py to crm/migrations/
  3. Deploy the new code
  4. Run migration 0013 via Cloud Run job (see Deployment section below)
  5. Reset existing records to re-fetch with expanded data:
       Lead.objects.filter(is_census_processed=True).update(is_census_processed=False)
       Contact.objects.filter(is_census_processed=True).update(is_census_processed=False)
       Company.objects.filter(is_census_processed=True).update(is_census_processed=False)
  6. Open any record to trigger re-fetch with all 15 data points


--------------------------------------------------------------------------------
DEPLOYMENT ON GOOGLE CLOUD RUN
--------------------------------------------------------------------------------

This project deploys to Cloud Run (project: django-crm-sales-engine,
region: us-central1, Cloud SQL instance: myinstance).

DEPLOY CODE
  cd ~/django-sales
  gcloud run deploy django-sales-app --source . --region us-central1 \
    --project django-crm-sales-engine

RUN MIGRATIONS VIA CLOUD RUN JOB
  # Get current image digest from live revision
  IMAGE=$(gcloud run services describe django-sales-app \
    --region us-central1 --project django-crm-sales-engine \
    --format "value(spec.template.spec.containers[0].image)")

  # Create job (delete first if it exists)
  gcloud run jobs delete migrate-job --region us-central1 \
    --project django-crm-sales-engine --quiet 2>/dev/null

  gcloud run jobs create migrate-job \
    --image "$IMAGE" \
    --region us-central1 \
    --project django-crm-sales-engine \
    --set-cloudsql-instances django-crm-sales-engine:us-central1:myinstance \
    --service-account cloudrun-serviceaccount@django-crm-sales-engine.iam.gserviceaccount.com \
    --set-secrets APPLICATION_SETTINGS=application_settings:latest \
    --set-env-vars DJANGO_SETTINGS_MODULE=webcrm.settings,\
  CLOUDRUN_SERVICE_URLS=https://django-sales-app-785974500350.us-central1.run.app,\
  SITE_ID=1,DEBUG=True \
    --args "manage.py,migrate"

  gcloud run jobs execute migrate-job --region us-central1 --wait

IMPORTANT NOTES
  - All secrets live in a single Secret Manager secret: application_settings
  - The service account is cloudrun-serviceaccount@django-crm-sales-engine.iam.gserviceaccount.com
    (NOT the default compute SA — the default SA lacks Secret Manager access)
  - Cloud Run jobs do NOT inherit env vars or secrets from the Cloud Run service
    automatically; they must be re-specified on the job
  - The Census API key setting is US_CENSUS_API_KEY (not CENSUS_API_KEY)
  - city_name is a stale denormalized field; the geocoder uses city FK name


--------------------------------------------------------------------------------
ADMIN PANEL STATES
--------------------------------------------------------------------------------

  PENDING  (is_census_processed = False)
    The record has not been opened since the migration ran.
    Message: "Census data will load on first profile view."
    Icon:    hourglass

  NO DATA  (is_census_processed = True, all metrics null)
    Address could not be geocoded or ACS returned no data.
    Causes:  non-US address, incomplete street, PO box, new construction,
             recently renamed street, rural address without tract match,
             or temporary Census API outage.
    Message: "No census data available for this address."
    Icon:    info

  DATA LOADED  (is_census_processed = True, metrics populated)
    Two-column table with all 15 metrics organized in 8 labeled sections.
    Styled with CRM CSS variables — matches light and dark mode automatically.
    Footer: "Source: US Census Bureau ACS 5-Year Estimates (2022).
             Census tract level."


--------------------------------------------------------------------------------
REFRESHING STALE DATA
--------------------------------------------------------------------------------

ACS 5-year data is released annually each December. Once is_census_processed
is True, data is never re-fetched automatically.

SINGLE RECORD
  obj.is_census_processed = False
  obj.save(update_fields=['is_census_processed'])
  Then open the record's detail page to trigger re-fetch.

BULK RESET (all records)
  from crm.models import Company, Contact, Lead
  Company.objects.all().update(is_census_processed=False)
  Contact.objects.all().update(is_census_processed=False)
  Lead.objects.all().update(is_census_processed=False)

  Data re-fetches naturally as each record is next opened. On Cloud Run,
  run these commands via the migrate-job (update --args to manage.py,shell,-c,
  then the reset commands as a one-liner).

  Be mindful of API rate limits for large databases. At the default ~500
  requests/day/IP limit without an API key, 500 records would take one day.
  With a free Census API key (US_CENSUS_API_KEY), the limit is removed.


--------------------------------------------------------------------------------
ADDING MORE CENSUS VARIABLES
--------------------------------------------------------------------------------

  1. Find the variable code at:
       https://api.census.gov/data/2022/acs/acs5/variables.html

  2. Add the code to ACS_VARIABLES tuple in crm/utils/census_utils.py

  3. Parse it in fetch_acs_data() and add to the return dict

  4. Add the model field to company.py, contact.py, lead.py

  5. Write a new migration (next number after 0013)

  6. Add display row in render_census_panel()

  7. Add the field name to update_fields in fetch_census_data_for_obj()

Common variables to consider next:
  B25064_001E   Median gross rent
  B08301_010E   % using public transit to commute
  B11001_001E   Total households
  B25002_003E   Vacant housing units
  B08303_*      Travel time to work distribution (ranges)


--------------------------------------------------------------------------------
DATA LIMITATIONS
--------------------------------------------------------------------------------

  - Tract-level aggregates only. All residents on the same block share the
    same tract metrics. Data reflects the neighborhood, not the individual.

  - ACS 5-year estimates average data over a 5-year collection window.
    The 2022 dataset covers collection years 2018 through 2022.

  - Margin of error is not stored. Only point estimates are saved.

  - Suppressed values: the Census Bureau returns -666666666 for cells with
    insufficient sample size. The utility treats any negative value as
    zero/null to prevent nonsensical display.

  - The Geocoder matches against the Census TIGER/Line database. New
    construction, recently renamed streets, and some rural addresses may
    not match and will show "No census data available."


--------------------------------------------------------------------------------
EXTERNAL APIS (BOTH FREE, NO ACCOUNT REQUIRED FOR BASIC USE)
--------------------------------------------------------------------------------

  Census Geocoder
    URL:   https://geocoding.geo.census.gov/geocoder/geographies/address
    Docs:  https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html
    Key:   Not required
    Limit: Not documented

  ACS 5-Year Data API
    URL:   https://api.census.gov/data/2022/acs/acs5
    Docs:  https://www.census.gov/data/developers/guidance/api-user-guide.html
    Key:   Optional. ~500 req/day/IP without key. Unlimited with free key.
    Signup: https://api.census.gov/data/key_signup.html
    Setting: US_CENSUS_API_KEY in application_settings Secret Manager secret


================================================================================
  Leadstart Media, Inc. — django-crm-main  —  Census Integration v2
================================================================================
