from . import models, wizard


def _l10n_om_hr_payroll_post_install(env):
    env.ref('base.om')._adapt_work_entry_types_to_country()


def _l10n_om_hr_payroll_uninstall_hook(env):
    env['hr.payroll.payment.report.wizard'].sudo().search([
        ('export_format', '=', 'l10n_om_wps')
    ]).export_format = 'csv'
