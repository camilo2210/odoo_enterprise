# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import report
from . import wizard
from . import controllers


def _l10n_be_hr_payroll_post_install(env):
    env.ref('base.be')._adapt_work_entry_types_to_country()
    env['l10n.be.joint.committee'].search([]).write({'active': False})
    env['hr.salary.rule'].search([('country_id', '=', env.ref('base.be').id)]).write({'active': False})
    env['hr.payroll.structure'].search([('country_id', '=', env.ref('base.be').id)]).write({'active': False})
    env['hr.payroll.warning'].search([('country_id', '=', env.ref('base.be').id)]).write({'active': False})
    env['hr.salary.rule.category'].search([('country_id', '=', env.ref('base.be').id)]).write({'active': False})

    belgian_companies_without_work_location = env['res.company'].search([]).filtered(
        lambda company: company.country_id == env.ref('base.be')
        and not env['hr.work.location'].search_count([('company_id', '=', company.id)], limit=1))
    env['hr.work.location'].create([{
        'name': env._('Office'),
        'company_id': company.id,
        'location_type': 'office',
    } for company in belgian_companies_without_work_location])
