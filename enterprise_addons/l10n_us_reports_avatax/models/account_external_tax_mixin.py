import copy

from odoo import models

# Map Avatax jurisdictionType -> account.tax.l10n_us_jurisdiction_type
L10N_US_JURISDICTION_TYPES = {
    'State': 'state',
    'County': 'county',
    'City': 'city',
    'Special': 'special',
}
# Suffix of a 0% variant tax -> field linking it back to its taxable parent
L10N_US_VARIANT_SUFFIXES = {
    ' (Exempt)': 'l10n_us_exempt_parent_tax_id',
    ' (Non-Taxable)': 'l10n_us_nontaxable_parent_tax_id',
}


class AccountExternalTaxMixin(models.AbstractModel):
    _inherit = 'account.external.tax.mixin'

    def _l10n_us_reports_set_jurisdiction(self, tax_vals, tax_detail):
        """ Set the jurisdiction type and state on the tax based on
        Avatax's response. County and city are not set because
        Avatax tax naming convention allows for a rate to be shared
        amongst counties and cities.
        """
        jurisdiction_type = L10N_US_JURISDICTION_TYPES.get(tax_detail.get('jurisdictionType'))
        if not jurisdiction_type:
            return
        tax_vals['l10n_us_jurisdiction_type'] = jurisdiction_type
        tax_vals['l10n_us_state_id'] = self._l10n_us_reports_get_state(tax_detail.get('region')).id

    def _l10n_us_reports_get_state(self, code):
        if not code:
            return self.env['res.country.state']
        return self.env['res.country.state'].search([
            ('country_id.code', '=', 'US'), ('code', '=', code)], limit=1)

    def _l10n_us_reports_link_variant_taxes(self, company, parent_vals_by_variant_name):
        """ Link each 0% exempt / non-taxable variant tax to the taxable jurisdiction rate."""
        Tax = self.env['account.tax'].with_context(active_test=False)
        variants = Tax.search([
            *Tax._check_company_domain(company),
            ('name', 'in', list(parent_vals_by_variant_name)),
        ])
        for variant in variants:
            for suffix, field in L10N_US_VARIANT_SUFFIXES.items():
                if not variant.name.endswith(suffix) or variant[field]:
                    continue
                parent = Tax.search([
                    *Tax._check_company_domain(company),
                    ('name', '=', parent_vals_by_variant_name[variant.name]['name']),
                    ('type_tax_use', '=', variant.type_tax_use),
                ], limit=1)
                if not parent:
                    parent = Tax.sudo().create({
                        **parent_vals_by_variant_name[variant.name],
                        'type_tax_use': variant.type_tax_use,
                        'tax_group_id': variant.tax_group_id.id,
                    })
                variant.sudo()[field] = parent.id
                break

    def _extract_tax_values_from_avatax_detail(self, service_params, line_details, tax_detail):
        tax_group_vals, tax_vals, amounts = super()._extract_tax_values_from_avatax_detail(
            service_params, line_details, tax_detail)

        company = service_params['line_data'][0]['base_line']['record'].company_id
        if company.account_fiscal_country_id.code != 'US':
            return tax_group_vals, tax_vals, amounts

        self._l10n_us_reports_set_jurisdiction(tax_vals, tax_detail)

        if tax_detail.get('exemptAmount') or tax_detail.get('nonTaxableAmount'):
            suffix = None
            if tax_detail.get('exemptAmount'):
                suffix = ' (Exempt)'
            elif tax_detail.get('nonTaxableAmount'):
                suffix = ' (Non-Taxable)'
            if suffix:
                # keep the taxable jurisdiction rate, to create the parent from if it is not found
                tax_vals['__l10n_us_parent_vals'] = copy.deepcopy(tax_vals)
                tax_vals['name'] = f"{tax_vals['name']}{suffix}"
                tax_vals['amount'] = 0

        return tax_group_vals, tax_vals, amounts

    def _process_external_taxes(self, company, base_line_with_tax_values, tax_key_field, search_archived_taxes=False):
        parent_vals_by_variant_name = {}
        for _base_line, tax_values_list in base_line_with_tax_values:
            for _group_vals, tax_vals, _amounts in tax_values_list:
                if parent_vals := tax_vals.pop('__l10n_us_parent_vals', None):
                    parent_vals_by_variant_name[tax_vals['name']] = parent_vals

        res = super()._process_external_taxes(company, base_line_with_tax_values, tax_key_field, search_archived_taxes)
        if parent_vals_by_variant_name:
            self._l10n_us_reports_link_variant_taxes(company, parent_vals_by_variant_name)
        return res
