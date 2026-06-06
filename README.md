
  US CENSUS BUREAU INTEGRATION FOR DJANGO-CRM
  Neighborhood demographic data on Company, Contact, and Lead profiles


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


--------------------------------------------------------------------------------
WHAT DATA IS DISPLAYED
--------------------------------------------------------------------------------

The panel shows seven data points for the census tract surrounding the
record's address. A census tract is a subdivision of a county, typically
covering 1,200 to 8,000 residents — fine enough to describe the specific
neighborhood a business or contact is located in.

  Field                    Source variable    Description
  ─────────────────────────────────────────────────────────────────────────────
  Median Household Income  B19013_001E        Annual household income at the
                                              50th percentile for the tract.
                                              Reported in US dollars.

  Tract Population         B03002_001E        Total population of the census
                                              tract. Also serves as the
                                              denominator for all percentages.

  % Non-Hispanic White     B03002_003E        Share of tract residents who
                                              identify as White alone and
                                              not Hispanic or Latino.

  % Non-Hispanic Black     B03002_004E        Share of tract residents who
                                              identify as Black or African
                                              American alone and not Hispanic
                                              or Latino.

  % Non-Hispanic Asian     B03002_006E        Share of tract residents who
                                              identify as Asian alone and not
                                              Hispanic or Latino.

  % Hispanic or Latino     B03002_012E        Share of tract residents who
                                              identify as Hispanic or Latino
                                              of any race.

  FIPS codes               (internal)         State (2-digit), county
                                              (3-digit), and tract (6-digit)
                                              codes shown in small text below
                                              the metrics. Useful for manual
                                              verification against census.gov.


WHY TABLE B03002 FOR RACE/ETHNICITY?
  The standard race table (B02001) counts Hispanic/Latino individuals inside
  the White, Black, and Asian categories, which causes double-counting. Table
  B03002 "Hispanic or Latino Origin by Race" separates Hispanic/Latino identity
  first, then counts non-Hispanic populations within each race. This is the
  technically correct approach for clean, non-overlapping percentages.


WHAT IS NOT COLLECTED
  - Individual-level data of any kind. All figures are tract-level aggregates.
  - Age distribution, education levels, housing values, employment status.
    These can be added later by extending ACS_VARIABLES in census_utils.py.
  - Data for non-US addresses. Records whose Country field is not United States
    are marked as processed immediately with all census fields left null.


--------------------------------------------------------------------------------
HOW THE DATA IS FETCHED (TWO-STEP FLOW)
--------------------------------------------------------------------------------

The Census Bureau's data API does not accept casual geographic strings like
"Atlanta, GA" or "30301." It requires Federal Information Processing Series
(FIPS) codes. This integration resolves them automatically in two steps.

STEP 1 — Census Geocoder API
  Endpoint: geocoding.geo.census.gov/geocoder/geographies/address
  Input:    Street address, city, state, ZIP (all from the CRM record)
  Output:   State FIPS (2 digits), County FIPS (3 digits), Tract FIPS (6 digits)
  Free:     Yes. No API key required. No rate limit documented.
  Example:
    Input  → "191 Peachtree St NW", city="Atlanta", state="GA"
    Output → state="13", county="121", tract="002000"

  Georgia's state FIPS is 13. The geocoder resolves the county and tract
  automatically from the street address — you never look up place codes
  manually. The Atlanta "place FIPS" of 04000 is not used here because
  census tract is a finer and more accurate geography for address-level data.

STEP 2 — ACS 5-Year Data API
  Endpoint: api.census.gov/data/2022/acs/acs5
  Input:    State, county, and tract FIPS codes from Step 1
  Output:   The seven demographic variables listed above
  Free:     Yes. Works without an API key up to roughly 500 requests per day
            per IP address. A free key removes this limit.
  Example:
    Request → ?get=B19013_001E,B03002_001E,...&for=tract:002000&in=state:13 county:121
    Returns → [["B19013_001E","B03002_001E",...],["72500","4821",...]]

WHY ACS 5-YEAR AND NOT 1-YEAR?
  The 1-year ACS is only published for geographic areas with 65,000 or more
  residents. Most census tracts are far smaller than that. The 5-year ACS is
  published for every tract in the country, making it the only option for
  address-level demographic data.


--------------------------------------------------------------------------------
HOW JIT LOADING WORKS
--------------------------------------------------------------------------------

JIT stands for Just-In-Time. Instead of fetching data when a record is created
or imported, this integration fetches it on the first time someone actually
opens that record's profile page. Here is the exact sequence:

  1. A CRM user clicks into a Company, Contact, or Lead record.

  2. Django Admin calls change_view() for that record.

  3. change_view() calls fetch_census_data_for_obj(obj) before rendering.

  4. Inside that function, the first line checks is_census_processed.
       - If True  → return immediately. One DB read. Done. Page loads fast.
       - If False → continue to the two API calls below.

  5. The address fields are assembled from the record (with fallback logic
     for Contacts and Leads that may have incomplete address data).

  6. The Census Geocoder API is called to get FIPS codes.

  7. The ACS 5-Year API is called with those FIPS codes to get metrics.

  8. All results are written to the record in a single
     obj.save(update_fields=[...]) call.

  9. is_census_processed is set to True in the same save call.

 10. The page renders with fresh data. Every future visit skips to step 4
     and exits immediately.

THE EDGE CASE — INVALID OR MISSING ADDRESSES
  If the Geocoder cannot match the address (step 6 returns nothing), or the
  ACS API returns no data (step 7 returns nothing), the function still sets
  is_census_processed = True before returning. This means the system will not
  retry the external APIs on the next page view. All census fields remain null.
  The admin panel shows: "No census data available for this address."

  This prevents a record with a bad address from triggering two external HTTP
  requests every single time someone opens it.


--------------------------------------------------------------------------------
ADDRESS RESOLUTION PRIORITY
--------------------------------------------------------------------------------

Each model type has slightly different address fields. The utility resolves
them in this order:

  COMPANY
    Uses: address, city_name, region
    No fallback — companies are expected to have their own address.

  CONTACT
    Uses: address, city_name, region
    Fallback: if address is blank, inherits address, city_name, and region
    from the linked Company record.

  LEAD
    Uses: address, city_name, region (personal address fields)
    Fallback: if address is blank, uses company_address (the lead's company
    address field, which is separate from the personal address fields).


--------------------------------------------------------------------------------
FILES CHANGED
--------------------------------------------------------------------------------

  NEW FILE
  crm/utils/census_utils.py
    Standalone utility. Contains all API logic, address resolution, and the
    admin display renderer. No model imports at module level (uses local
    imports inside functions to avoid Django's circular import problem).

    Functions:
      geocode_address(street, city, state, zipcode) → dict | None
      fetch_acs_data(state, county, tract, api_key)  → dict | None
      fetch_census_data_for_obj(obj)                 → bool
      render_census_panel(obj)                       → str (HTML)

  NEW FILE
  crm/migrations/0012_census_data_fields.py
    Adds 10 database columns to Company, Contact, and Lead:
      is_census_processed   BooleanField  default=False
      census_state_fips     CharField     max_length=2
      census_county_fips    CharField     max_length=3
      census_tract          CharField     max_length=6
      census_median_income  IntegerField  null=True
      census_population     IntegerField  null=True
      census_pct_white      DecimalField  5 digits, 1 decimal place, null=True
      census_pct_black      DecimalField  5 digits, 1 decimal place, null=True
      census_pct_asian      DecimalField  5 digits, 1 decimal place, null=True
      census_pct_hispanic   DecimalField  5 digits, 1 decimal place, null=True

  MODIFIED
  crm/models/company.py
  crm/models/contact.py
  crm/models/lead.py
    All 10 census fields declared on each model, placed after the last
    ForeignKey field in each file. No changes to existing fields or methods.

  MODIFIED
  crm/site/companyadmin.py
  crm/site/contactadmin.py
  crm/site/leadadmin.py
    Three identical additions in each file:
      1. Import fetch_census_data_for_obj and render_census_panel
      2. JIT trigger at the top of change_view()
      3. 'census_data_panel' added to readonly_fields
      4. Collapsed fieldset "Area Demographics (US Census Bureau)" appended
         to get_fieldsets(), after the "Additional information" section
      5. census_data_panel() display callable added to the class


--------------------------------------------------------------------------------
INSTALLATION
--------------------------------------------------------------------------------

  1. Drop the files into your project matching the paths above.

  2. Run the migration:
       python manage.py migrate crm

  3. Optional — add a free Census API key to webcrm/settings.py:
       CENSUS_API_KEY = "your_key_here"

     Without a key the APIs still work, but you are limited to roughly 500
     requests per day per server IP address. Get a free key at:
       https://api.census.gov/data/key_signup.html

  4. Open any Company, Contact, or Lead record that has a US street address.
     Scroll to the bottom of the form and expand "Area Demographics (US Census
     Bureau)" to see the data.

  No third-party Python packages required. The integration uses only Python's
  standard library (urllib, json) and Django's built-in ORM.


--------------------------------------------------------------------------------
ADMIN PANEL STATES
--------------------------------------------------------------------------------

The census_data_panel read-only field renders one of three states:

  PENDING (is_census_processed = False)
    Shown on records that have never been opened since the migration ran.
    Message: "Census data will load on first profile view."
    Icon: hourglass

  NO DATA (is_census_processed = True, all metrics are null)
    Shown when the address could not be geocoded or ACS returned no data.
    Causes: non-US address, incomplete street address, PO box, rural area
    with no tract match, or temporary Census API outage.
    Message: "No census data available for this address."
    Icon: info

  DATA LOADED (is_census_processed = True, metrics populated)
    Shows a two-column table with all seven metrics and the raw FIPS codes
    in small text at the bottom. Styled with CRM CSS variables so it matches
    the existing admin color theme automatically in both light and dark mode.
    Footer: "Source: US Census Bureau ACS 5-Year Estimates, table B03002.
             Census tract level data."


--------------------------------------------------------------------------------
REFRESHING STALE DATA
--------------------------------------------------------------------------------

Once is_census_processed is True, the data is never re-fetched automatically.
Census ACS 5-year data is updated annually (December release each year), so
records will gradually become outdated.

To force a re-fetch for a single record, set is_census_processed = False
directly in the Django shell or admin and then open the profile page:

  from crm.models import Company
  obj = Company.objects.get(pk=123)
  obj.is_census_processed = False
  obj.save(update_fields=['is_census_processed'])

To reset all records in bulk for a full refresh:

  Company.objects.all().update(is_census_processed=False)
  Contact.objects.all().update(is_census_processed=False)
  Lead.objects.all().update(is_census_processed=False)

After running those commands, data will re-fetch the next time each record
is opened. Be mindful of API rate limits if doing this for thousands of records
at once — load will be distributed naturally across page views.


--------------------------------------------------------------------------------
EXTENDING WITH MORE CENSUS VARIABLES
--------------------------------------------------------------------------------

The ACS 5-Year API offers thousands of variables. To add more data points:

  1. Find the variable code at:
       https://api.census.gov/data/2022/acs/acs5/variables.html

  2. Add the code to ACS_VARIABLES in crm/utils/census_utils.py:
       ACS_VARIABLES = (
           "B19013_001E",   # existing
           ...
           "B15003_022E",   # example: bachelor's degree holders
       )

  3. Parse the new variable in fetch_acs_data() and add it to the return dict.

  4. Add the corresponding model field and migration.

  5. Display it in render_census_panel().

Common additions teams request:
  B15003_022E   Bachelor's degree (25+)
  B08301_001E   Total commuters
  B08301_010E   Public transit commuters
  B25077_001E   Median home value
  B25064_001E   Median gross rent
  B23025_005E   Unemployment count


--------------------------------------------------------------------------------
DATA LIMITATIONS AND ACCURACY NOTES
--------------------------------------------------------------------------------

  - All data is tract-level, not address-level. Everyone on the same block
    shares the same tract, so the metrics reflect the neighborhood, not the
    specific business or individual.

  - ACS 5-year estimates are averages over a 5-year collection period, not
    a single point in time. The 2022 dataset covers 2018 through 2022.

  - The Census Bureau assigns a margin of error to every estimate. This
    integration stores point estimates only, not confidence intervals.

  - Rural areas with very small populations may have suppressed data, in which
    case the ACS API returns -666666666 for the affected variable. The utility
    treats any negative value as zero/null to prevent nonsensical display.

  - The Geocoder matches addresses against the Census Bureau's TIGER/Line
    database. Newly constructed buildings, recently renamed streets, and some
    rural addresses may not match. These records will show "No census data
    available for this address."


--------------------------------------------------------------------------------
EXTERNAL APIS USED (BOTH FREE, NO ACCOUNT REQUIRED)
--------------------------------------------------------------------------------

  Census Geocoder
    URL:   https://geocoding.geo.census.gov/geocoder/geographies/address
    Docs:  https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html
    Key:   Not required
    Limit: Not documented; designed for developer use

  ACS 5-Year Data API
    URL:   https://api.census.gov/data/2022/acs/acs5
    Docs:  https://www.census.gov/data/developers/guidance/api-user-guide.html
    Key:   Optional. ~500 req/day/IP without key. Unlimited with free key.
    Keys:  https://api.census.gov/data/key_signup.html


================================================================================
