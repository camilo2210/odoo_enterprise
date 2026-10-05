# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import controllers
from odoo import SUPERUSER_ID


def _embed_sign_post_init(env):
    """Embed the Sign action into employee document folders after module installation."""
    sign_action = env.ref('documents_sign.ir_actions_server_create_sign_template_direct')
    if folders := env['res.company'].sudo().search([]).documents_employee_folder_id.filtered("active"):
        folders.with_user(SUPERUSER_ID)._embed_action(sign_action.id)
