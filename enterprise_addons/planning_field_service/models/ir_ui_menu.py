# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _load_menus_blacklist(self):
        res = super()._load_menus_blacklist()
        if self.env.user.has_group('planning.group_planning_manager'):
            res.append(self.env.ref('planning_field_service.planning_menu_planning_all').id)
        if self.env.user.has_group('planning.group_planning_user'):
            res.append(self.env.ref('planning_field_service.planning_menu_my_planning_internal_user').id)
        return res
