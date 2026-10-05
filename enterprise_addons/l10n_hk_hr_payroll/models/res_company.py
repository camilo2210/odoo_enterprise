# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_hk_autopay_partner_bank_id = fields.Many2one(string="Autopay Account", comodel_name='res.partner.bank', copy=False)
    l10n_hk_employer_name = fields.Char("Employer's Name shown on reports", compute='_compute_l10n_hk_employer_name', store=True, readonly=False)
    l10n_hk_employer_file_number = fields.Char("Employer's File Number")
    l10n_hk_eoy_pay_month = fields.Selection(
        string="End of Year Payments Month",
        help="If set, End of Year Payments will be included in the payslip of the chose month.\nLeave empty to manually choose when to include it in each payslip.",
        selection=[
            ('1', 'January'),
            ('2', 'February'),
            ('3', 'March'),
            ('4', 'April'),
            ('5', 'May'),
            ('6', 'June'),
            ('7', 'July'),
            ('8', 'August'),
            ('9', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December')
        ],
        default='12',
    )

    @api.constrains("l10n_hk_employer_file_number")
    def _check_l10n_hk_employer_file_number(self):
        for company in self:
            if not company.l10n_hk_employer_file_number:
                continue
            file_number = company.l10n_hk_employer_file_number.strip()
            if len(file_number) != 12 or file_number[3] != '-':
                raise UserError(company.env._("The Employer's File Number must be in the format of EEN-12345678."))

    @api.depends("name")
    def _compute_l10n_hk_employer_name(self):
        for company in self:
            company.l10n_hk_employer_name = company.l10n_hk_employer_name or company.name

    def _prepare_resource_calendar_values(self):
        """
        Override to set the default calendar to
        40 hours/week for Hong Kong companies
        """
        vals = super()._prepare_resource_calendar_values()
        if self.country_id.code == 'HK':
            vals.update({
                'name': self.env._('40 hours/week - %s', self.name),
                'full_time_required_hours': 40.0,
                'attendance_ids': [
                    (0, 0, {'dayofweek': '0', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '1', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '2', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '3', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '4', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '5', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0,
                            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_hk_work_entry_type_weekend').id}),
                    (0, 0, {'dayofweek': '6', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0,
                            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_hk_work_entry_type_weekend').id}),
                ],
            })
        return vals
