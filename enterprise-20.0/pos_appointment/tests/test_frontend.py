# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import timedelta
from freezegun import freeze_time

from odoo import fields
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.pos_appointment.tests.test_pos_appointment_flow import (
    CommonPosAppointmentTest,
)


@tagged('post_install', '-at_install')
class TestFrontend(CommonPosAppointmentTest, TestPointOfSaleHttpCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.main_pos_config.write({
            'module_pos_appointment': True,
            'appointment_type_id': cls.reservation_appointment.id,
        })

    def test_appointment_kanban_view_date_filter(self):
        self.start_pos_tour('test_appointment_kanban_view_date_filter')

    def test_appointment_gantt_filters_reset(self):
        morning_time = fields.Datetime.now().replace(hour=6, minute=0)
        with freeze_time(morning_time):
            self.env['calendar.event'].create({
                'name': 'Morning Booking',
                'start': morning_time,
                'stop': morning_time + timedelta(hours=2),
                'appointment_type_id': self.reservation_appointment.id,
            })
            self.main_pos_config.with_user(self.pos_admin).open_ui()
            self.start_pos_tour('test_appointment_gantt_filters_reset')
