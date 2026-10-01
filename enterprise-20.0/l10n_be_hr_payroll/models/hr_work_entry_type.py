# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    l10n_be_egov3_code = fields.Char(string="e-Gov 3.0 Code", tracking=True)
    l10n_be_egov3_base = fields.Selection([
        ('daily', 'Daily'),
        ('periodic', 'Periodic'),
        ('both', 'Daily or periodic'),
    ], string="e-Gov 3.0 Base", default='daily', required=True, tracking=True,
    help="Benefits and absences can be declared per day (for example, 01/01/2028) or per period (for example, from 01/01/2028 to 18/01/2028 inclusive).")
    dmfa_code = fields.Char(string="DMFA code", tracking=True, help="The DMFA Code will identify the work entry in DMFA report.")
    leave_right = fields.Boolean(
        string="Paid Time Off Eligibility", default=False, tracking=True,
        help="The time type will be taken into account for the computation of the annual time off allocation")
    l10n_be_is_time_credit = fields.Boolean(
        string="Time Credit",
        default=False,
        tracking=True,
        help="Time Credit are specific time types used in the computation of the working rate in the working schedule. A Time Credit time type is considered as work.",
    )
    leave_ids = fields.One2many(
        'hr.leave',
        'work_entry_type_id',
        string='Time Off',
    )
    l10n_be_economic_unemployment = fields.Boolean(string="Economic Unemployment", default=False,
        help="The time type will make the day count as economic unemployment for relevant salary rules and benefits.")
    l10n_be_drs_risk_ids = fields.Many2many('l10n.be.drs.risk', string="DRS trigger", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_drs_nature = fields.Selection(string="DRS Nature", groups="hr_payroll.group_hr_payroll_user", selection="_get_drs_nature")

    def _get_drs_nature(self):
        # Source: https://www.socialsecurity.be/portail/glossaires/DRSONEM10.nsf/be8ba64d95a2ed0ec125686200574ff5/40dd9c2a21a94756c1258c450037b8d7/$FILE/AN2024-1-FR13.pdf
        return [
            ('1', self.env._("[1] Paid days except for the paid days referred to below")),
            ('1.1', self.env._("[1.1] Return to work during the guaranteed salary period followed by a relapse - only allowed for the Compensation sector")),
            ('1.2', self.env._("[1.2] Compensatory rest paid by a third party")),
            ('1.3', self.env._("[1.3] Incapacity for work paid by the education sector")),
            ('1.4', self.env._("[1.4] Hours outside the schedule")),
            ('1.5', self.env._("[1.5] Recovery of hours outside the schedule")),
            ('1.6', self.env._("[1.6] Absence with salary maintained")),
            ('2.1', self.env._("[2.1] Guaranteed daily salary due to incapacity for work")),
            ('2.2', self.env._("[2.2] Guaranteed daily salary for a reason other than incapacity for work")),
            ('2.3', self.env._("[2.3] Absence on the first day due to bad weather - construction sector")),
            ('2.4', self.env._("[2.4] Guaranteed remuneration for the first week")),
            ('2.5', self.env._("[2.5] Guaranteed remuneration for the second week")),
            ('2.6', self.env._("[2.6] Guaranteed monthly remuneration")),
            ('2.7', self.env._("[2.7] CBA 12bis/13bis allowance following an ordinary illness or accident")),
            ('2.8', self.env._("[2.8] Waiting day")),
            ('2.9', self.env._("[2.9] CBA 12bis/13bis allowance following a work accident or occupational disease")),
            ('3.1', self.env._("[3.1] Statutory holidays")),
            ('3.2', self.env._("[3.2] Supplementary holidays")),
            ('3.3', self.env._("[3.3] Vacation under a collective bargaining agreement made mandatory")),
            ('3.4', self.env._("[3.4] Youth/Senior holidays")),
            ('3.5', self.env._("[3.5] Additional holidays days in case of starting or resuming activity (art. 17bis Law of 28.06.1971)")),
            ('3.6', self.env._("[3.6] Vacation carried over and taken within 24 months following the holidays year")),
            ('4', self.env._("[4] Substitute days for public holidays")),
            ('5.1', self.env._("[5.1] Temporary unemployment due to lack of work resulting from economic causes")),
            ('5.2', self.env._("[5.2] Temporary unemployment due to bad weather")),
            ('5.3', self.env._("[5.3] Temporary unemployment due to a technical accident")),
            ('5.4', self.env._("[5.4] Temporary unemployment due to force majeure")),
            ('5.5', self.env._("[5.5] Temporary unemployment due to force majeure of a medical nature")),
            ('5.6', self.env._("[5.6] Temporary unemployment due to company closure for annual holidays")),
            ('5.7', self.env._("[5.7] Temporary unemployment due to company closure for holidays under a mandatory CBA")),
            ('5.8', self.env._("[5.8] Temporary unemployment due to company closure for compensatory rest under working time reduction")),
            ('5.9', self.env._("[5.9] Temporary unemployment due to strike or lock-out")),
            ('5.10', self.env._("[5.10] Temporary unemployment in case of dismissal of a protected worker")),
            ('5.11', self.env._("[5.11] Suspension days for employees due to lack of work")),
            ('6.1', self.env._("[6.1] Incapacity for work with work accident compensation under article 54 of the Work Accidents Act")),
            ('6.2', self.env._("[6.2] Any unpaid absence for illness and accident, incapacity for work due to prophylactic leave")),
            ('6.3', self.env._("[6.3] Adapted work with loss of salary in the context of incapacity for work, adapted work with loss of ion measure")),
            ('6.4', self.env._("[6.4] Complete removal from work as a maternity protection measure, maternity rest, paternity leave under the law of 16 March 1971 on labour")),
            ('6.5', self.env._("[6.5] Absence for incapacity for work for which the guaranteed salary is not paid due to temporary unemployment")),
            ('6.6', self.env._("[6.6] Absence for incapacity for work for which the guaranteed salary is not paid due to relapse")),
            ('6.7', self.env._("[6.7] Absence for incapacity for work for which the guaranteed salary is not paid due to collective annual vacation")),
            ('6.8', self.env._("[6.8] Absence for incapacity for work for which the guaranteed salary is not paid for reasons attributable to the worker (unjustified absence or refusal to submit to control)")),
            ('6.9', self.env._("[6.9] Absence for incapacity for work for which the guaranteed salary is not paid due to insufficient seon than those referred to under codes 6.5, 6.6, 6.7 and 6.8")),
            ('6.10', self.env._("[6.10] Paternity or birth leave under the law of 3 July 1978 on employment contracts (only days charged to the compensation sector) and breastfeeding break")),
            ('6.11', self.env._("[6.11] Adoption leave and foster parental leave (only days charged to the compensation sector)")),
            ('6.21', self.env._("[6.21] Unpaid absence for work accident or occupational disease during adapted work")),
            ('6.22', self.env._("[6.22] Date of definitive cessation of adapted work")),
            ('7', self.env._("[7] Absence or unpaid leave")),
            ('8', self.env._("[8] Usual days of inactivity in the occupation")),
            ('9', self.env._("[9] Days of absence for foster care")),
            ('10.1', self.env._("[10.1] Port - Unemployment")),
            ('10.2', self.env._("[10.2] Port - Unemployment subject to approval")),
            ('10.3', self.env._("[10.3] Port - Royal Decree 225")),
            ('10.4', self.env._("[10.4] Port - Paid public holiday")),
            ('10.5', self.env._("[10.5] Port - Public holiday on which work is performed")),
            ('10.6', self.env._("[10.6] Port - Replacement public holiday on which work is performed")),
            ('10.7', self.env._("[10.7] Port - Work accident - public holiday during work accident")),
            ('10.8', self.env._("[10.8] Port - Illness - paid public holiday")),
            ('10.9', self.env._("[10.9] Port - Seniority holidays")),
            ('10.10', self.env._("[10.10] Port - Additional holidays with existence security / double existence security")),
            ('10.11', self.env._("[10.11] Port - Exemption from unemployment control / holidays during a period of unemployment / additional holidays")),
            ('10.12', self.env._("[10.12] Port - Family leave")),
            ('10.13', self.env._("[10.13] Port - Short leave (petit chômage)")),
            ('10.14', self.env._("[10.14] Port - Solidarity day")),
            ('10.15', self.env._("[10.15] Port - Union leave")),
            ('10.16', self.env._("[10.16] Port - Introductory course / training")),
            ('10.17', self.env._("[10.17] Port - (Professional) training")),
            ('10.18', self.env._("[10.18] Port - Partially reduced work capacity")),
            ('10.19', self.env._("[10.19] Port - Reduced work capacity")),
            ('10.20', self.env._("[10.20] Port - Medical examination")),
            ('10.21', self.env._("[10.21] Port - Medical exemption from unemployment control")),
            ('10.22', self.env._("[10.22] Port - Vacation not taken")),
        ]

    @api.model
    def _get_critical_fields(self):
        return super()._get_critical_fields() + [
            'l10n_be_egov3_code',
            'l10n_be_egov3_base',
            'dmfa_code',
            'leave_right',
            'l10n_be_is_time_credit',
            'l10n_be_economic_unemployment',
            'l10n_be_drs_risk_ids',
            'l10n_be_drs_nature',
        ]

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_be_hr_payroll', [
                'data/hr_work_entry_type_data.xml',
            ])]

    def get_allocation_data(self, employees, target_date=None, same_year_only=False):
        """For the 3 BE hours-tracked types: expose the exact hour balance when it disagrees
        with the rounded day count, and flag a negative balance (day or
        hour)"""
        result = super().get_allocation_data(employees, target_date, same_year_only=same_year_only)
        tracked_types = self.env['hr.leave.allocation']._get_l10n_be_hours_tracked_work_entry_types()
        if not tracked_types:
            return result
        target_date = fields.Date.to_date(target_date) or fields.Date.context_today(self)

        allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', 'in', employees.ids),
            ('work_entry_type_id', 'in', tracked_types.ids),
            ('state', '=', 'validate'),
            ('date_from', '<=', target_date),
            '|', ('date_to', '=', False), ('date_to', '>=', target_date),
        ])
        hours_remaining_by_key = defaultdict(float)
        warnings_by_key = defaultdict(list)
        for allocation in allocations:
            key = (allocation.employee_id.id, allocation.work_entry_type_id.id)
            hours_remaining_by_key[key] += allocation.l10n_be_hours_remaining
            if allocation.l10n_be_negative_balance_warning:
                warnings_by_key[key].append(allocation.l10n_be_negative_balance_warning)

        for employee in employees:
            hours_per_day = employee.resource_calendar_id.hours_per_day
            if not hours_per_day:
                continue
            for _name, info, _requires_allocation, work_entry_type_id in result[employee]:
                if work_entry_type_id not in tracked_types.ids:
                    continue
                key = (employee.id, work_entry_type_id)
                hours_remaining = hours_remaining_by_key.get(key, 0)
                expected_hours = info['virtual_remaining_leaves'] * hours_per_day
                if float_compare(hours_remaining, expected_hours, precision_digits=2) != 0:
                    info['l10n_be_hours_remaining'] = hours_remaining
                if warnings_by_key.get(key):
                    info['l10n_be_negative_balance_warning'] = '\n'.join(warnings_by_key[key])
        return result
