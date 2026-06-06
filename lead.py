from django.db import models
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from common.models import Base1
from crm.models.base_contact import BaseContact
from crm.models.base_contact import BaseCounterparty


class Lead(BaseCounterparty, BaseContact, Base1):
    class Meta:
        verbose_name = _("Lead")
        verbose_name_plural = _("Leads")

    disqualified = models.BooleanField(
        default=False,
        verbose_name=_("Disqualified"),
    )
    company_name = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name=_("Company name"),
    )
    website = models.URLField(
        max_length=200, blank=True, default=''
    )

    company_phone = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name=_("Company phone"),
    )
    company_address = models.TextField(
        blank=True, default='',
        verbose_name=_("Company address"),
    )
    company_email = models.EmailField(
        blank=True, default='',
        verbose_name=_("Company email"),
    )
    type = models.ForeignKey(
        'ClientType', 
        blank=True, 
        null=True, 
        on_delete=models.SET_NULL,
        verbose_name=_("Type of company")
    )
    industry = models.ManyToManyField(
        'Industry', 
        blank=True,
        verbose_name=_("Industry of company")
    )
    contact = models.ForeignKey(
        'Contact', blank=True, null=True, on_delete=models.CASCADE,
        verbose_name=_("Contact")
    )
    company = models.ForeignKey(
        'Company', blank=True, null=True, on_delete=models.CASCADE,
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

    def __str__(self):
        if self.company_name:
            return f"{self.full_name}, {self.company_name}," \
                   f" {self.country}"
        return self.full_name

    def get_absolute_url(self):
        return reverse('admin:crm_lead_change', args=(self.id,))

    @property
    def full_name(self):
        full_name = ' '.join(filter(
            None, 
            (self.first_name, self.middle_name, self.last_name)
        ))
        if self.disqualified:
            full_name = f"({_('Disqualified')}) {full_name}"
        return full_name
