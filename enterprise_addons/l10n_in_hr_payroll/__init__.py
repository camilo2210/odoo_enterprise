# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import report
from . import wizard
from . import controller


def _l10n_in_hr_payroll_post_install(env):
    env.ref('base.in')._adapt_work_entry_types_to_country()


def _l10n_in_hr_payroll_uninstall_hook(env):
    env['hr.payroll.payment.report.wizard'].sudo().search([
        ('export_format', 'in', ('advice', 'enet'))
    ]).export_format = 'csv'
