# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class L10nPhHrPayrollForm1601C(models.Model):
    _name = 'l10n_ph_hr_payroll.form_1601c'
    _inherit = 'l10n_ph_hr_payroll.declaration'
    _description = 'Form 1601-C'

    is_processed = fields.Boolean(readonly=True)
    remittance_date = fields.Date(string='Remittance Date', tracking=True)

    # Non-Taxable Compensation
    mwe_basic = fields.Monetary(string='15. Statutory Minimum Wage', readonly=True)
    mwe_holiday_ot = fields.Monetary(string='16. Holiday/OT/Night Shift (MWE)', readonly=True)
    non_taxable_benefits = fields.Monetary(string='17. 13th Month & Other Benefits (MWE)', readonly=True)
    de_minimis = fields.Monetary(string='18. De Minimis Benefits', readonly=True)
    mandatory_contributions = fields.Monetary(string='19. Employee Mandatory Contributions', readonly=True)
    other_non_taxable = fields.Monetary(string='20. Other Non-Taxable', readonly=True)
    total_non_taxable = fields.Monetary(string='21. Total Non-Taxable', compute='_compute_total_non_taxable')
    # Taxable Compensation & Taxes
    total_taxable = fields.Monetary(string='22. Total Taxable Compensation', readonly=True)
    taxable_exempt = fields.Monetary(string='23. Taxable (0% Tax Bracket)', readonly=True)
    taxable_taxed = fields.Monetary(string='24. Taxable (Subject to Tax)', compute='_compute_taxable_taxed')
    total_tax_withheld = fields.Monetary(string='25. Taxes Withheld', readonly=True)
    total_tax_adjustment = fields.Monetary(string='26. Adjustments (Annualization)', readonly=True)
    total_tax_withheld_for_rem = fields.Monetary(string='27. Taxes Withheld for Remittance', readonly=True)
    # Manual adjustments
    tax_previously_remitted = fields.Monetary(string='28. Tax Previously Remitted')
    other_remittances = fields.Monetary(string='29. Other Remittances')
    total_tax_remittances = fields.Monetary(string='30. Total Tax Remittances', compute='_compute_total_tax_remittances')
    tax_still_due = fields.Monetary(string='31. Tax Still Due', compute='_compute_tax_still_due')
    # Penalties
    surcharge = fields.Monetary(string='32. Surcharge')
    interest = fields.Monetary(string='33. Interest')
    compromise = fields.Monetary(string='34. Compromise')
    penalties = fields.Monetary(string='35. Total Penalties', compute='_compute_penalties')
    # Grand total
    grand_total_compensation = fields.Monetary(string='14. Total Compensation', compute='_compute_grand_total_compensation')
    total_still_due = fields.Monetary(string='36. Total Amount Still Due', compute='_compute_total_still_due')

    period_1604c_declaration_id = fields.Many2one(
        comodel_name='l10n_ph_hr_payroll.form_1604c',
    )

    @api.depends('tax_previously_remitted', 'other_remittances')
    def _compute_total_tax_remittances(self):
        for form in self:
            form.total_tax_remittances = form.tax_previously_remitted + form.other_remittances

    @api.depends('total_tax_withheld_for_rem', 'total_tax_remittances')
    def _compute_tax_still_due(self):
        for form in self:
            form.tax_still_due = form.total_tax_withheld_for_rem - form.total_tax_remittances

    @api.depends('surcharge', 'interest', 'compromise')
    def _compute_penalties(self):
        for form in self:
            form.penalties = form.surcharge + form.interest + form.compromise

    @api.depends('tax_still_due', 'penalties')
    def _compute_total_still_due(self):
        for form in self:
            form.total_still_due = form.tax_still_due + form.penalties

    @api.depends('mwe_basic', 'mwe_holiday_ot', 'non_taxable_benefits', 'de_minimis', 'mandatory_contributions', 'other_non_taxable')
    def _compute_total_non_taxable(self):
        for form in self:
            form.total_non_taxable = form.mwe_basic + form.mwe_holiday_ot + form.non_taxable_benefits + form.de_minimis + form.mandatory_contributions + form.other_non_taxable

    @api.depends('total_taxable', 'taxable_exempt')
    def _compute_taxable_taxed(self):
        for form in self:
            form.taxable_taxed = form.total_taxable - form.taxable_exempt

    @api.depends('total_non_taxable', 'total_taxable')
    def _compute_grand_total_compensation(self):
        for form in self:
            form.grand_total_compensation = form.total_non_taxable + form.total_taxable

    def _get_declaration_name(self):
        self.ensure_one()
        return self.env._("Form 1601-C")

    def action_process_declaration(self):
        """
        Round the amount to the currency's standard and optionally enforce absolute values.

        This ensures that statutory totals comply with the currency's decimal precision.
        By default, statutory tax buckets are reported as positive absolute values
        regardless of how they were calculated in the payslip, unless explicitly told
        to preserve the sign (e.g., for tax adjustments).
        """
        def _get_category_total(category_code, total_code='total', preserve_sign=False):
            """
            Helper to return formated total for a given category.
            total_code must be one of mwe, regular or total.
            """
            return self._format_value(categories_totals[category_code][total_code], preserve_sign, stringify=False)

        structures = self._get_relevant_structures()
        all_payslips = self.env['hr.payslip'].search([
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', self.period_start_date),
            ('date_to', '<=', self.period_end_date),
            ('employee_id', 'in', self.line_ids.employee_id.ids),
            ('struct_id', 'in', structures.ids),
            ('company_id', '=', self.company_id.id),
        ])
        all_lines_values = all_payslips._get_line_values(set(all_payslips.line_ids.mapped('code')), compute_sum=True)
        _, categories_totals = all_payslips._l10n_ph_hr_payroll_aggregate_totals(all_lines_values)

        # Write the basic amounts
        self.write({
            'mwe_basic': _get_category_total('PH_BASIC', 'mwe'),
            'mwe_holiday_ot': _get_category_total('OT', 'mwe'),
            'non_taxable_benefits': _get_category_total('NT_BEN', 'total'),
            'de_minimis': _get_category_total('DE_MINIMIS', 'total'),
            'mandatory_contributions': _get_category_total('MANDATORY_CONTRIBUTIONS', 'total'),
            'other_non_taxable': _get_category_total('NT_ALW', 'total'),
            'total_taxable': _get_category_total('GROSS', 'total'),
            'taxable_exempt': _get_category_total('TAXABLE_EXEMPT', 'total'),
            'total_tax_withheld': _get_category_total('WTH_TAX', 'total'),
            # These two totals need to be inverted compared to the payslips.
            'total_tax_adjustment': -_get_category_total('TAX_ANN', 'total', preserve_sign=True),
            'total_tax_withheld_for_rem': -_get_category_total('TAX', 'total', preserve_sign=True),
            'is_processed': True,
        })
