# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard


def _l10n_sa_hr_payroll_post_install(env):
    env.ref('base.sa')._adapt_work_entry_types_to_country()


def _l10n_sa_hr_payroll_uninstall_hook(env):
    env['hr.payroll.payment.report.wizard'].sudo().search([
        ('export_format', '=', 'l10n_sa_wps')
    ]).export_format = 'csv'
