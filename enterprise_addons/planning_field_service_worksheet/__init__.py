# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import report
from . import controllers


def post_init(env):
    if 'under_warranty' not in env['planning.slot']._fields:
        env['res.config.settings'].create({'group_field_service_allow_customer_report': True}).execute()


def uninstall_hook(env):
    IrModule = env['ir.module.module']
    planning_field_service_module = IrModule._get('planning_field_service')
    if planning_field_service_module.state == 'installed' and IrModule._get('planning_field_service_sale_timesheet').state == 'uninstalled':
        env['res.config.settings'].create({'group_field_service_allow_customer_report': False}).execute()
