# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo.fields import Date
from dateutil.relativedelta import relativedelta
from . import models
from . import wizard

_logger = logging.getLogger(__name__)


def generate_payslips(env):
    """ Generate demo payslips for the Belgian demo company during post-install. """
    demo_company = env.ref('base.demo_company_be', raise_if_not_found=False)
    has_duplicates = env['hr.payslip'].sudo().search([('employee_id.name', '=', 'Marian Weaver')], limit=1)
    if not demo_company or has_duplicates:
        return
    _logger.info('Generating payruns')

    langs = env['res.lang'].with_context(active_test=False).search([('code', 'in', ['fr_BE', 'nl_BE'])])
    for lang in langs:
        if not lang.active:
            env['base.language.install'].create({'lang_ids': [(6, 0, lang.ids)]}).lang_install()

    payslip_values = []
    # Produces 10 monthly runs, from 2 months ago back to 11 months ago.
    for i in range(2, 12):
        date_start = Date.today() - relativedelta(months=i, day=1)
        date_end = Date.today() - relativedelta(months=i, day=31)
        payslip_values.append({
            'name': date_start.strftime('%B %Y'),
            'date_start': date_start,
            'date_end': date_end,
            'company_id': demo_company.id,
            'structure_id': env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
        })

    # Process the payslip runs month by month.
    payslip_runs = env['hr.payslip.run'].with_company(demo_company).with_context(tracking_disable=True).create(payslip_values)
    for run in payslip_runs:
        _logger.info('Processing demo payslip run: %s', run.name)
        run._generate_payslips()
        run.action_validate()
