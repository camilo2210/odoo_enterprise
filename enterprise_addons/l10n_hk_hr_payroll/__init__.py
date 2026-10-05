# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import controllers
from . import models
from . import report
from . import wizards


def _l10n_hk_hr_payroll_post_install(env):
    env.ref('base.hk')._adapt_work_entry_types_to_country()


def _l10n_hk_hr_payroll_uninstall_hook(env):
    env['hr.payroll.payment.report.wizard'].sudo().search([
        ('export_format', 'in', ('l10n_hk_mri', 'l10n_hk_boc', 'l10n_hk_boc_non_payment', 'l10n_hk_bea_csv'))
    ]).export_format = 'csv'
