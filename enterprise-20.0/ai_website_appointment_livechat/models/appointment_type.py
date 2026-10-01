# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.tools import is_html_empty


class AppointmentType(models.Model):
    _name = 'appointment.type'
    _inherit = ['appointment.type', 'ai.preview.card.mixin']

    def _ai_get_preview_cards_render_context(self):
        website = self.env.website
        if not website:
            return False
        # Check the current website appointment view to render the corresponding template
        view = 'website_appointment.opt_appointments_index_pictures'
        template = (
            'website_appointment.appointments_pictures'
            if website.is_view_active(view)
            else 'website_appointment.appointments_cards'
        )
        cards = [
            {
                'appointment_types': appointment,
                'is_html_empty': is_html_empty,
                'is_sample': False,
            }
            for appointment in self
        ]
        # Keep `o_appointment_index` class so appointment preview CSS scoped under
        # `.o_appointment_index .o_ai_preview_cards` applies correctly.
        return (template, cards, 'o_appointment_index')
