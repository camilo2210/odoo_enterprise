from odoo import models


class WebsiteMenu(models.Model):
    _inherit = 'website.menu'

    def _compute_visible(self):
        super()._compute_visible()
        self.filtered(
            lambda menu: menu.url == '/service-requests'
            and not menu.website_id.company_id.website_planning_field_service
        ).is_visible = False
