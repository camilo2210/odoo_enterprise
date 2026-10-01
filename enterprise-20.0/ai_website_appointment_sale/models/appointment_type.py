# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    def _ai_get_preview_metadata(self):
        """Extend preview metadata with linked product prices."""
        metadata = super()._ai_get_preview_metadata()
        appointments_with_product = self.filtered('product_id')
        if not appointments_with_product:
            return metadata

        product_id_by_appointment_id = {
            appointment.id: appointment.product_id.id
            for appointment in appointments_with_product
        }
        combo_info = (
            appointments_with_product.mapped('product_id').sudo()._resolve_product_combination_info()
        )
        for entry in metadata:
            entry.update(combo_info.get(product_id_by_appointment_id.get(entry['id']), {}))
        return metadata
