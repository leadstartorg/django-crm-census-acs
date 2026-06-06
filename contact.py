from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from common.models import Base1
from crm.models.base_contact import BaseContact
from crm.models.base_contact import BaseCounterparty


class Contact(BaseCounterparty, BaseContact, Base1):
    class Meta:
        verbose_name = _("Contact person")
        verbose_name_plural = _("Contact persons")

    company = models.ForeignKey(
        'Company', blank=False,
        null=False, on_delete=models.CASCADE,
        related_name="contacts",
        verbose_name=_("Company of contact")
    )

    # ------------------------------------------------------------------ #
    # US Census Bureau – ACS 5-Year demographic data (JIT / lazy-loaded)  #
    # ------------------------------------------------------------------ #
    is_census_processed = models.BooleanField(
        default=False,
        verbose_name=_("Census data processed"),
        help_text=_(
            "Set automatically on first profile view. Prevents repeated "
            "external API calls for the same record."
        ),
    )
    census_state_fips = models.CharField(
        max_length=2, blank=True, default='',
        verbose_name=_("Census state FIPS"),
    )
    census_county_fips = models.CharField(
        max_length=3, blank=True, default='',
        verbose_name=_("Census county FIPS"),
    )
    census_tract = models.CharField(
        max_length=6, blank=True, default='',
        verbose_name=_("Census tract"),
    )
    census_median_income = models.IntegerField(
        blank=True, null=True,
        verbose_name=_("Median household income"),
    )
    census_population = models.IntegerField(
        blank=True, null=True,
        verbose_name=_("Census tract population"),
    )
    census_pct_white = models.DecimalField(
        max_digits=5, decimal_places=1,
        blank=True, null=True,
        verbose_name=_("% Non-Hispanic White"),
    )
    census_pct_black = models.DecimalField(
        max_digits=5, decimal_places=1,
        blank=True, null=True,
        verbose_name=_("% Non-Hispanic Black"),
    )
    census_pct_asian = models.DecimalField(
        max_digits=5, decimal_places=1,
        blank=True, null=True,
        verbose_name=_("% Non-Hispanic Asian"),
    )
    census_pct_hispanic = models.DecimalField(
        max_digits=5, decimal_places=1,
        blank=True, null=True,
        verbose_name=_("% Hispanic or Latino"),
    )

    @property
    def company_country(self):
        return self.company.country

    def __str__(self):
        return f"{self.first_name} {self.last_name}, {self.company}, {self.country}"
    
    def get_absolute_url(self):  
        return reverse('admin:crm_contact_change', args=(self.id,))
