# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    # l10n_be_hr_payroll_dimona will be dropped in master
    technical_usage = fields.Selection(selection_add=[
        ('l10n_be_hr_payroll_part_time', 'Part Time Declaration'),
        ('l10n_be_hr_payroll_dimona', 'Dimona Declaration'),
        ('l10n_be_hr_payroll_8_weeks_STO', '8 consecutive weeks of sick leave'),
    ])
