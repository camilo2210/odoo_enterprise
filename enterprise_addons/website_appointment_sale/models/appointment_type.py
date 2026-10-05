from odoo import models


class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    def _has_accessory_products(self):
        self.ensure_one()
        return bool(self.product_id.product_tmpl_id.accessory_product_ids)
