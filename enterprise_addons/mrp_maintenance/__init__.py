# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from odoo.fields import Domain


def uninstall_hook(env):
    action = env.ref(
        'maintenance_enterprise.maintenance_request_action_view_gantt_equipment',
        raise_if_not_found=False
    )
    if action:
        action.write({'domain': Domain.TRUE})
