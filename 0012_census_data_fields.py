"""
Migration 0012: Add US Census Bureau demographic fields.

Adds census fields to Company, Contact, and Lead models:

  is_census_processed  – BooleanField(default=False)
    Tracks whether a census lookup has been attempted for this record,
    regardless of whether data was found.  Prevents re-hitting the
    external API on every page view for records with bad addresses.

  census_state_fips    – 2-digit FIPS (e.g. "13" for Georgia)
  census_county_fips   – 3-digit FIPS (e.g. "121" for Fulton County)
  census_tract         – 6-digit census tract code

  census_median_income – median household income (USD)
  census_population    – total tract population

  census_pct_white     – % Non-Hispanic White    (from ACS B03002)
  census_pct_black     – % Non-Hispanic Black    (from ACS B03002)
  census_pct_asian     – % Non-Hispanic Asian    (from ACS B03002)
  census_pct_hispanic  – % Hispanic / Latino     (from ACS B03002)
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0011_contact_avatar_lead_avatar'),
    ]

    operations = [
        # ---- Company ----
        migrations.AddField(
            model_name='company',
            name='is_census_processed',
            field=models.BooleanField(
                default=False,
                verbose_name='Census data processed',
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='census_state_fips',
            field=models.CharField(
                blank=True, default='', max_length=2,
                verbose_name='Census state FIPS',
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='census_county_fips',
            field=models.CharField(
                blank=True, default='', max_length=3,
                verbose_name='Census county FIPS',
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='census_tract',
            field=models.CharField(
                blank=True, default='', max_length=6,
                verbose_name='Census tract',
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='census_median_income',
            field=models.IntegerField(
                blank=True, null=True,
                verbose_name='Median household income',
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='census_population',
            field=models.IntegerField(
                blank=True, null=True,
                verbose_name='Census tract population',
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='census_pct_white',
            field=models.DecimalField(
                blank=True, null=True,
                max_digits=5, decimal_places=1,
                verbose_name='% Non-Hispanic White',
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='census_pct_black',
            field=models.DecimalField(
                blank=True, null=True,
                max_digits=5, decimal_places=1,
                verbose_name='% Non-Hispanic Black',
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='census_pct_asian',
            field=models.DecimalField(
                blank=True, null=True,
                max_digits=5, decimal_places=1,
                verbose_name='% Non-Hispanic Asian',
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='census_pct_hispanic',
            field=models.DecimalField(
                blank=True, null=True,
                max_digits=5, decimal_places=1,
                verbose_name='% Hispanic or Latino',
            ),
        ),

        # ---- Contact ----
        migrations.AddField(
            model_name='contact',
            name='is_census_processed',
            field=models.BooleanField(
                default=False,
                verbose_name='Census data processed',
            ),
        ),
        migrations.AddField(
            model_name='contact',
            name='census_state_fips',
            field=models.CharField(
                blank=True, default='', max_length=2,
                verbose_name='Census state FIPS',
            ),
        ),
        migrations.AddField(
            model_name='contact',
            name='census_county_fips',
            field=models.CharField(
                blank=True, default='', max_length=3,
                verbose_name='Census county FIPS',
            ),
        ),
        migrations.AddField(
            model_name='contact',
            name='census_tract',
            field=models.CharField(
                blank=True, default='', max_length=6,
                verbose_name='Census tract',
            ),
        ),
        migrations.AddField(
            model_name='contact',
            name='census_median_income',
            field=models.IntegerField(
                blank=True, null=True,
                verbose_name='Median household income',
            ),
        ),
        migrations.AddField(
            model_name='contact',
            name='census_population',
            field=models.IntegerField(
                blank=True, null=True,
                verbose_name='Census tract population',
            ),
        ),
        migrations.AddField(
            model_name='contact',
            name='census_pct_white',
            field=models.DecimalField(
                blank=True, null=True,
                max_digits=5, decimal_places=1,
                verbose_name='% Non-Hispanic White',
            ),
        ),
        migrations.AddField(
            model_name='contact',
            name='census_pct_black',
            field=models.DecimalField(
                blank=True, null=True,
                max_digits=5, decimal_places=1,
                verbose_name='% Non-Hispanic Black',
            ),
        ),
        migrations.AddField(
            model_name='contact',
            name='census_pct_asian',
            field=models.DecimalField(
                blank=True, null=True,
                max_digits=5, decimal_places=1,
                verbose_name='% Non-Hispanic Asian',
            ),
        ),
        migrations.AddField(
            model_name='contact',
            name='census_pct_hispanic',
            field=models.DecimalField(
                blank=True, null=True,
                max_digits=5, decimal_places=1,
                verbose_name='% Hispanic or Latino',
            ),
        ),

        # ---- Lead ----
        migrations.AddField(
            model_name='lead',
            name='is_census_processed',
            field=models.BooleanField(
                default=False,
                verbose_name='Census data processed',
            ),
        ),
        migrations.AddField(
            model_name='lead',
            name='census_state_fips',
            field=models.CharField(
                blank=True, default='', max_length=2,
                verbose_name='Census state FIPS',
            ),
        ),
        migrations.AddField(
            model_name='lead',
            name='census_county_fips',
            field=models.CharField(
                blank=True, default='', max_length=3,
                verbose_name='Census county FIPS',
            ),
        ),
        migrations.AddField(
            model_name='lead',
            name='census_tract',
            field=models.CharField(
                blank=True, default='', max_length=6,
                verbose_name='Census tract',
            ),
        ),
        migrations.AddField(
            model_name='lead',
            name='census_median_income',
            field=models.IntegerField(
                blank=True, null=True,
                verbose_name='Median household income',
            ),
        ),
        migrations.AddField(
            model_name='lead',
            name='census_population',
            field=models.IntegerField(
                blank=True, null=True,
                verbose_name='Census tract population',
            ),
        ),
        migrations.AddField(
            model_name='lead',
            name='census_pct_white',
            field=models.DecimalField(
                blank=True, null=True,
                max_digits=5, decimal_places=1,
                verbose_name='% Non-Hispanic White',
            ),
        ),
        migrations.AddField(
            model_name='lead',
            name='census_pct_black',
            field=models.DecimalField(
                blank=True, null=True,
                max_digits=5, decimal_places=1,
                verbose_name='% Non-Hispanic Black',
            ),
        ),
        migrations.AddField(
            model_name='lead',
            name='census_pct_asian',
            field=models.DecimalField(
                blank=True, null=True,
                max_digits=5, decimal_places=1,
                verbose_name='% Non-Hispanic Asian',
            ),
        ),
        migrations.AddField(
            model_name='lead',
            name='census_pct_hispanic',
            field=models.DecimalField(
                blank=True, null=True,
                max_digits=5, decimal_places=1,
                verbose_name='% Hispanic or Latino',
            ),
        ),
    ]
