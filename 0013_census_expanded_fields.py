"""
Migration 0013 — Add expanded census fields to Company, Contact, Lead.

New fields (10 additional data points beyond 0012):
  census_median_age           – median age of tract residents
  census_per_capita_income    – per capita income (USD)
  census_pct_poverty          – % population below poverty level
  census_pct_college          – % with bachelor's degree or higher
  census_pct_unemployed       – unemployment rate
  census_median_home_value    – median home value (USD)
  census_pct_owner_occupied   – % owner-occupied housing units
  census_mean_commute_minutes – mean travel time to work (minutes)
  census_pct_limited_english  – % with limited English proficiency
  census_pct_uninsured        – % without health insurance
"""

from django.db import migrations, models

NEW_FIELDS = [
    ("census_median_age",          models.DecimalField(blank=True, null=True, max_digits=4, decimal_places=1, verbose_name="Median age")),
    ("census_per_capita_income",   models.IntegerField(blank=True, null=True, verbose_name="Per capita income")),
    ("census_pct_poverty",         models.DecimalField(blank=True, null=True, max_digits=5, decimal_places=1, verbose_name="% below poverty level")),
    ("census_pct_college",         models.DecimalField(blank=True, null=True, max_digits=5, decimal_places=1, verbose_name="% bachelor's degree or higher")),
    ("census_pct_unemployed",      models.DecimalField(blank=True, null=True, max_digits=5, decimal_places=1, verbose_name="Unemployment rate %")),
    ("census_median_home_value",   models.IntegerField(blank=True, null=True, verbose_name="Median home value")),
    ("census_pct_owner_occupied",  models.DecimalField(blank=True, null=True, max_digits=5, decimal_places=1, verbose_name="% owner-occupied housing")),
    ("census_mean_commute_minutes",models.DecimalField(blank=True, null=True, max_digits=5, decimal_places=1, verbose_name="Mean commute (minutes)")),
    ("census_pct_limited_english", models.DecimalField(blank=True, null=True, max_digits=5, decimal_places=1, verbose_name="% limited English proficiency")),
    ("census_pct_uninsured",       models.DecimalField(blank=True, null=True, max_digits=5, decimal_places=1, verbose_name="% without health insurance")),
]

MODELS = ["company", "contact", "lead"]


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0012_census_data_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name=model,
            name=field_name,
            field=field_instance,
        )
        for model in MODELS
        for field_name, field_instance in NEW_FIELDS
    ]
