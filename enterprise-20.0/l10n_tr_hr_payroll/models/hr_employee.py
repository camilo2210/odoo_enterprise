# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    certificate = fields.Selection(
        ondelete={
            'l10n_tr_0_unknown': 'set default',
            'l10n_tr_1_illiterate': 'set default',
            'l10n_tr_2_primary_school': 'set default',
            'l10n_tr_3_middle_school': 'set default',
            'l10n_tr_4_high_school': 'set default',
            'l10n_tr_5_university': 'set default',
            'l10n_tr_6_master_degree': 'set default',
            'l10n_tr_7_doctorate': 'set default',
        },
    )
    l10n_tr_is_current_turkey_citizen = fields.Boolean(compute='_compute_l10n_tr_is_current_turkey_citizen', groups="hr.group_hr_user")
    l10n_tr_first_name = fields.Char(
        string='First Name (TR)',
        compute='_compute_l10n_tr_name',
        store=True,
        readonly=False,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_tr_last_name = fields.Char(
        string='Last Name (TR)',
        compute='_compute_l10n_tr_name',
        store=True,
        readonly=False,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_tr_graduation_year = fields.Char(readonly=False, related='version_id.l10n_tr_graduation_year', inherited=True, groups='hr_payroll.group_hr_payroll_user')
    l10n_tr_is_rd_incentive = fields.Boolean(readonly=False, related='version_id.l10n_tr_is_rd_incentive', inherited=True, groups='hr_payroll.group_hr_payroll_user')
    l10n_tr_is_ex_convict = fields.Boolean(readonly=False, related='version_id.l10n_tr_is_ex_convict', inherited=True, groups='hr_payroll.group_hr_payroll_user')
    l10n_tr_insurance_type = fields.Selection(readonly=False, related='version_id.l10n_tr_insurance_type', inherited=True, groups='hr_payroll.group_hr_payroll_user')
    l10n_tr_job_code = fields.Selection(readonly=False, related='version_id.l10n_tr_job_code', inherited=True, groups='hr_payroll.group_hr_payroll_user')
    l10n_tr_labour_sector = fields.Selection(readonly=False, related='version_id.l10n_tr_labour_sector', inherited=True, groups='hr_payroll.group_hr_payroll_user')
    l10n_tr_occupational_code = fields.Selection(readonly=False, related='version_id.l10n_tr_occupational_code', inherited=True, groups='hr_payroll.group_hr_payroll_user')
    l10n_tr_social_security_law = fields.Selection(readonly=False, related='version_id.l10n_tr_social_security_law', inherited=True, groups='hr_payroll.group_hr_payroll_user')
    l10n_tr_document_type = fields.Selection(readonly=False, related='version_id.l10n_tr_document_type', inherited=True, groups='hr_payroll.group_hr_payroll_user')
    l10n_tr_social_insurance_number = fields.Char(string="Social Insurance Number", help="Enter the employee's unique SGK registration number.", groups='hr_payroll.group_hr_payroll_user')
    l10n_tr_is_net_to_gross = fields.Boolean(
        readonly=False,
        related="version_id.l10n_tr_is_net_to_gross",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_tr_food_allowance = fields.Monetary(
        readonly=False,
        related="version_id.l10n_tr_food_allowance",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )

    @api.depends("current_version_id.country_id.code", "current_version_id.is_non_resident")
    def _compute_l10n_tr_is_current_turkey_citizen(self):
        for emp in self:
            emp.l10n_tr_is_current_turkey_citizen = (
                emp.current_version_id.country_id.code == "TR"
                and not emp.current_version_id.is_non_resident
            )

    def _l10n_tr_get_worked_duration(self):
        self.ensure_one()
        first_version_date = self._get_first_version_date()
        if not first_version_date or not self.version_id.date_end:
            return 0, 0, 0

        unpaid_hours = self.env['hr.payslip.worked_days']._read_group(
            domain=[
                ('employee_id', '=', self.id),
                ('payslip_id.state', 'in', ('validated', 'paid')),
                ('payslip_id.company_id', '=', self.company_id.id),
                ('is_paid', '=', False),
            ],
            aggregates=['number_of_hours:sum'],
        )[0][0] or 0
        hours_per_day = self._get_hours_per_day(self.contract_date_start) or 8
        unpaid_days = unpaid_hours / hours_per_day

        end_date = self.version_id.date_end + relativedelta(days=1) - relativedelta(days=unpaid_days)
        diff = relativedelta(end_date, first_version_date)
        return diff.years, diff.months, diff.days

    def _l10n_tr_get_annual_remaining_leaves(self):
        result = {}
        allocation_data = self.company_id.l10n_tr_annual_work_entry_type_id.get_allocation_data(self)
        for employee in self:
            employee_data = allocation_data.get(employee, [])
            if employee_data:
                result[employee.id] = employee_data[0][1]['remaining_leaves']
            else:
                result[employee.id] = 0
        return result

    @api.depends('name')
    def _compute_l10n_tr_name(self):
        for employee in self:
            if employee.name:
                first_name = ' '.join(employee.name.strip().split(' ')[:-1])
                last_name = employee.name.strip().split(' ')[-1]
                if not employee.l10n_tr_first_name:
                    employee.l10n_tr_first_name = first_name
                if not employee.l10n_tr_last_name:
                    employee.l10n_tr_last_name = last_name

    def _get_splitting_legal_name_countries(self):
        return super()._get_splitting_legal_name_countries() + ['TR']

    def _get_certificate_selection(self):
        if self.env.company.country_id.code != 'TR':
            return super()._get_certificate_selection()
        return [
            ('l10n_tr_0_unknown', self.env._('Unknown')),
            ('l10n_tr_1_illiterate', self.env._('Illiterate')),
            ('l10n_tr_2_primary_school', self.env._('Primary school')),
            ('l10n_tr_3_middle_school', self.env._('Middle school or Primary school (İ.Ö.O)')),
            ('l10n_tr_4_high_school', self.env._('High school or equivalent')),
            ('l10n_tr_5_university', self.env._('University or faculty')),
            ('l10n_tr_6_master_degree', self.env._('Master\'s degree')),
            ('l10n_tr_7_doctorate', self.env._('Doctorate (PhD)')),
        ]

    def _l10n_tr_get_certificate_report_value(self):
        self.ensure_one()
        certificate_report_map = {
            'l10n_tr_0_unknown': '0',
            'l10n_tr_1_illiterate': '1',
            'l10n_tr_2_primary_school': '2',
            'l10n_tr_3_middle_school': '3',
            'l10n_tr_4_high_school': '4',
            'l10n_tr_5_university': '5',
            'l10n_tr_6_master_degree': '6',
            'l10n_tr_7_doctorate': '7',
            'bachelor': '5',
            'doctor': '7',
            'graduate': '5',
            'master': '6',
            'other': '0',
        }
        return certificate_report_map.get(self.certificate, '')
