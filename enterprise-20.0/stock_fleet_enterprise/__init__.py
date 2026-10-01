# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models


def uninstall_hook(env):
    action = env.ref('stock.stock_picking_batch_action')
    action.write({
        'view_mode': 'list,kanban,form',
        'views': [(False, "list"), (False, "kanban"), (False, "form")]
    })
