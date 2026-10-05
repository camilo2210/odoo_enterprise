# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare
from datetime import date

KODE_PTKP_MAPPING = {
    'tk0': 'a',
    'tk1': 'a',
    'k0': 'a',
    'tk2': 'b',
    'tk3': 'b',
    'k1': 'b',
    'k2': 'b',
    'k3': 'c',
}


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    l10n_id_include_pkp_ptkp = fields.Boolean(
        compute="_compute_l10n_id_include_pkp_ptkp", store=True, readonly=False)  # include the PTKP/PKP computation

    def _l10n_id_get_historical_categorical_total(self, codes):
        """ Get the total amount of specific category among the contract's taxes history that has been validated
        within a certain year"""
        date_start = date(self.date_to.year, 1, 1)
        payslips = self.env['hr.payslip'].search([
            ('date_to', '>', date_start),
            ('date_to', '<', self.date_to),
            ('state', 'in', ['validated', 'paid']),
            ('employee_id', '=', self.employee_id.id)
        ])
        vals = payslips._get_line_values(codes, compute_sum=True)
        return sum(vals[code]['sum']['total'] for code in codes)

    def _l10n_id_get_pph21_amount(self, amount):
        """ Find the right percentage to apply depending on the GROSS amount of the payslip"""
        category_type = KODE_PTKP_MAPPING[self.employee_id.l10n_id_kode_ptkp]
        rule_param = 'l10n_id_pph21_'
        if self.version_id.l10n_id_payroll_type == 'gross_up':
            rule_param += 'gross_up_'
        ranges = self._rule_parameter(rule_param + 'percentage_' + category_type)
        for line in ranges:
            if amount < line[1]:
                return line[2]

    def _l10n_id_get_end_total_pph_amount(self):
        """ Getting the accumulated PPH21 amount over the course of a year (from start of year/contract)"""
        return self._l10n_id_get_historical_categorical_total(['PPH21'])

    def _l10n_id_get_gross_accumulated(self):
        # gross_lines = self._l10n_id_get_historical_categorical_total_lines(['GROSS'])
        date_start = date(self.date_to.year, 1, 1)
        payslips = self.env['hr.payslip'].search([
            ('date_to', '>', date_start),
            ('date_to', '<', self.date_to),
            ('state', 'in', ['validated', 'paid']),
            ('employee_id', '=', self.employee_id.id)
        ])
        vals = payslips._get_line_values(['GROSS'])['GROSS']
        gross_lines = [vals[i]['total'] for i in payslips.ids]

        sum_gross = 0
        monthly_threshold = self._rule_parameter('l10n_id_biaya_jabatan_salary_threshold') / 12
        percent = self._rule_parameter('l10n_id_biaya_jabatan_percent')
        for line in gross_lines:
            amount = line * percent / 100
            sum_gross += min(amount, monthly_threshold)

        return sum_gross

    def _l10n_id_get_total_gross(self):
        """ Get the total GROSS accumulated before the current payslip"""
        return self._l10n_id_get_historical_categorical_total(['GROSS'])

    def _l10n_id_get_total_jht(self):
        """ Get the total JHT accumulated before the current payslip"""
        return self._l10n_id_get_historical_categorical_total(['JHT'])

    def _l10n_id_get_total_jp(self):
        """ Get the total JP accumulated before the current payslip"""
        return self._l10n_id_get_historical_categorical_total(['JP'])

    def _l10n_id_is_bpjs_kesehatan_deferred(self):
        """Return whether this payslip defers BPJS Kesehatan to the next month."""
        self.ensure_one()
        join_date = self.employee_id.first_contract_date
        return bool(
            join_date
            and join_date.day > self._rule_parameter('l10n_id_bpjs_kesehatan_cutoff_day')
            and self.date_from <= join_date <= self.date_to
        )

    def _l10n_id_get_bpjs_kesehatan_arrears_base(self):
        """Return the previous payslip's capped BASIC wage for BPJS arrears, or 0.0."""
        self.ensure_one()
        previous_payslip = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self.company_id.id),
            ('state', '!=', 'cancel'),
            ('date_to', '<', self.date_from),
        ], order='date_to desc', limit=1)
        if not previous_payslip or not previous_payslip._l10n_id_is_bpjs_kesehatan_deferred():
            return 0.0
        basic = previous_payslip._get_line_values(['BASIC'])['BASIC'][previous_payslip.id]['total']
        return min(basic, self._rule_parameter('l10n_id_bpjs_salary_threshold'))

    def _get_localdict(self, work_entries=None):
        """ Cache the BPJS Kesehatan deferral data, as the salary rules need it multiple times. """
        res = super()._get_localdict(work_entries)
        if self.country_code == 'ID':
            res.update({
                'l10n_id_bpjs_kesehatan_deferred': self._l10n_id_is_bpjs_kesehatan_deferred(),
                'l10n_id_bpjs_kesehatan_arrears_base': self._l10n_id_get_bpjs_kesehatan_arrears_base(),
            })
        return res

    @api.depends('date_from', 'date_to', 'version_id.contract_date_start', 'version_id.contract_date_end')
    def _compute_l10n_id_include_pkp_ptkp(self):
        """ by default, if it's end of year/end of contract, set to True"""
        for slip in self:
            slip.l10n_id_include_pkp_ptkp = (
                slip.date_to and (
                    (slip.date_to.month == 12) or
                    (
                        slip.version_id.contract_date_end and
                        slip.version_id.contract_date_end.month == slip.date_to.month and
                        slip.version_id.contract_date_end.year == slip.date_to.year
                    )
                )
            )

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_id_hr_payroll', [
                'data/hr_rule_parameter_data.xml',
                'data/hr_salary_rule_data.xml',
            ])]

    def _get_payslip_lines(self, force_categories_by_code=None):
        """ In grossup the formula is similar to trial and error where it will loop the calculation over and over again until
        the tax allowance(taken from pph21 previous iteration) is equal with pph21 current iteration
        """
        grossup_id_slips = self.filtered(lambda x: x.country_code == "ID" and x.version_id.l10n_id_payroll_type == 'gross_up')
        res = super(HrPayslip, self - grossup_id_slips)._get_payslip_lines(force_categories_by_code=force_categories_by_code)

        # Separate the payslip that use grossup calculation and process it per payslip
        for slip in grossup_id_slips:
            precision = slip.currency_id.decimal_places
            slip_lines = super(HrPayslip, slip)._get_payslip_lines(force_categories_by_code=force_categories_by_code)

            def get_vals(lines):
                # Use to get specific line result to calculate or check looping condition
                return {l['code']: l['total'] for l in lines if l['code'] in ('TAXALW', 'PPH21', 'BASE_GROSS_UP', 'GROSS')}

            v = get_vals(slip_lines)
            # Condition checking
            while (float_compare(v.get('TAXALW', 0), -v.get('PPH21', 0), precision) != 0 or float_compare(v.get('BASE_GROSS_UP', 0) + v.get('TAXALW', 0), v.get('GROSS', 0), precision) != 0):
                tax_alw = -v.get('PPH21', 0)
                # Use context to pass the previous PPH21 value to be used by tax_allowance value in the new iteration
                slip_lines = super(HrPayslip, slip.with_context(override_tax_alw=tax_alw))._get_payslip_lines(force_categories_by_code=force_categories_by_code)
                v = get_vals(slip_lines)
            res.extend(slip_lines)
        return res

    def _l10n_id_get_payslip_report_data(self):
        """ Group the payslip lines into the Income/Deduction/Benefits blocks shown on the
        Indonesian payslip PDF and compute each block total, plus the take home pay (NET) and
        taxable salary (GROSS) figures. """
        self.ensure_one()
        income_cat = self.env.ref('l10n_id_hr_payroll.l10n_id_income_parent_category')
        deduction_cat = self.env.ref('l10n_id_hr_payroll.l10n_id_deduction_parent_category')
        benefits_cat = self.env.ref('l10n_id_hr_payroll.l10n_id_benefits_parent_category')

        def visible_lines(category):
            return self.line_ids.filtered(
                lambda line: category in line.salary_rule_id.category_ids and (
                    line.appears_on_payslip == 'always'
                    or (line.appears_on_payslip == 'non_zero' and round(line.total, 2) != 0)
                )
            )

        income_lines = visible_lines(income_cat)
        deduction_lines = visible_lines(deduction_cat)
        benefits_lines = visible_lines(benefits_cat)

        return {
            'income_lines': income_lines,
            'income_total': sum(income_lines.mapped('total')),
            'deduction_lines': deduction_lines,
            'deduction_total': sum(deduction_lines.mapped('total')),
            'benefits_lines': benefits_lines,
            'benefits_total': sum(benefits_lines.mapped('total')),
            'taxable_line_codes': {
                'BASIC', 'FIXED_ALW', 'TAXALW', 'BPJS_KESEHATAN_EMP',
                'BPJS_JKK', 'BPJS_JKM', 'BPJS_Kesehatan',
            },
            'net': sum(self.line_ids.filtered(lambda line: line.code == 'NET').mapped('total')),
            'taxable': sum(self.line_ids.filtered(lambda line: line.code == 'GROSS').mapped('total')),
        }
