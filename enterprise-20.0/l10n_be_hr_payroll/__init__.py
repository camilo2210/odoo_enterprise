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
