# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import report
from . import wizard


def _l10n_tr_hr_payroll_post_install(env):
    env.ref('base.tr')._adapt_work_entry_types_to_country()


def _l10n_tr_hr_payroll_uninstall_hook(env):
    env['hr.payroll.payment.report.wizard'].sudo().search([
        ('export_format', '=', 'muhsgk')
    ]).export_format = 'csv'
