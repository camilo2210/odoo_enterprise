# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard


def _l10n_ae_hr_payroll_post_install(env):
    env.ref('base.ae')._adapt_work_entry_types_to_country()


def _l10n_ae_hr_payroll_uninstall_hook(env):
    env['hr.payroll.payment.report.wizard'].sudo().search([
        ('export_format', 'in', ('l10n_ae_wps', 'l10n_ae_wps_xlsx'))
    ]).export_format = 'csv'
