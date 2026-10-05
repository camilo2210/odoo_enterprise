# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import controllers
from . import models
from . import wizard
from . import report


def _init_company_payroll_config(env):
    """Ensures that all companies have at least one payroll configuration, which is required for the proper functioning of the module."""
    configs_by_company = dict(env['payroll.config.settings'].with_context(active_test=False)._read_group([],
            groupby=['company_id'], aggregates=['id:recordset']))
    for company in env['res.company'].search([]):
        if not company.payroll_config_ids:
            existing_configs = configs_by_company.get(company)
            if existing_configs:
                company.sudo().payroll_config_ids = [(4, config.id) for config in existing_configs]
            else:
                company.sudo().create_payroll_config()


def _post_init_hook(env):
    _init_company_payroll_config(env)


def uninstall_hook(env):
    if access := env.ref('hr.access_hr_employee_departure', raise_if_not_found=False):
        access.active = True

    if action := env.ref('hr.action_hr_employee_departure', raise_if_not_found=False):
        action.group_ids = env.ref('hr.group_hr_user')
