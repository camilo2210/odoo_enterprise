# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard


def _hr_payroll_account_iso20022_uninstall_hook(env):
    env['hr.payroll.payment.report.wizard'].sudo().search([
        ('export_format', 'in', ('sepa', 'iso20022_ch'))
    ]).export_format = 'csv'
