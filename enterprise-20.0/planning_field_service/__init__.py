from . import controllers
from . import models
from . import report
from . import wizard

from odoo.tools.translate import StoredTranslations


def post_init_hook(env):
    if env['res.groups']._is_feature_enabled('planning.group_field_service_allow_customer_ratings'):
        rating_mail_template = env.ref('planning_field_service.rating_shift_request_email_template')
        env["ir.config_parameter"].set_int(
            'planning_field_service.rating_shift_request_mail_template_id',
            rating_mail_template.id,
        )
    env['res.company'].search([]).field_service_confirmation_mail_template_id = env.ref('planning_field_service.mail_template_data_intervention_details')


def uninstall_hook(env):
    IrModule = env['ir.module.module']
    planning_module = IrModule._get('planning')
    if planning_module.state == 'installed':
        my_planning_menuitem = env.ref('planning.planning_menu_my_planning')
        all_planning_menuitem = env.ref('planning.planning_menu_all_planning')
        (my_planning_menuitem + all_planning_menuitem).parent_id = env.ref('planning.planning_menu_planning')
        my_planning_menuitem.name = env._("My Planning")
        group = env.ref('planning.group_planning_user', raise_if_not_found=False)
        if group:
            group.comment = StoredTranslations({'en_US': "Can view all published shifts."})
