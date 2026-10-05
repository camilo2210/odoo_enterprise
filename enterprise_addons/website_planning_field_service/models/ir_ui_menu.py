from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _load_menus_blacklist(self):
        res = super()._load_menus_blacklist()
        if not any(company.website_planning_field_service for company in self.env.companies):
            res.append(self.env.ref('website_planning_field_service.planning_slot_menu_service_requests').id)
        return res
