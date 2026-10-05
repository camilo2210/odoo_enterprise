from . import controllers
from . import models
from . import report


def post_init(env):
    if 'worksheet_template_id' not in env['planning.slot']._fields:
        env['res.config.settings'].create({'group_field_service_allow_customer_report': True}).execute()
    env.companies.write({
        'travel_time_invoicing_product_id': env.ref('planning_field_service_sale_timesheet.field_service_product_travel_invoice').id,
        'planning_project_id': env.ref('planning_field_service_sale_timesheet.fsm_project').id,
    })


def uninstall_hook(env):
    IrModule = env['ir.module.module']
    planning_field_service_module = IrModule._get('planning_field_service')
    if planning_field_service_module.state == 'installed' and IrModule._get('planning_field_service_worksheet').state in ['uninstalled', 'to remove']:
        env['res.config.settings'].create({'group_field_service_allow_customer_report': False}).execute()
