# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.ai_website_livechat.tests.common import AIPreviewCardCase
from odoo.addons.appointment.tests.common import AppointmentCommon


class TestAIAppointmentPreviewCards(AIPreviewCardCase, AppointmentCommon):
    def test_appointment_preview_card_renders(self):
        appointment = self.apt_type_bxls_2days
        appointment.is_published = True
        self.assertPreviewCardsRender(appointment, [appointment.name], expected_count=1)
