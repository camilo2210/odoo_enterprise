# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import tagged
from odoo.addons.pos_hr.tests.test_frontend import TestPosHrHttpCommon

from datetime import datetime, timedelta


class TestPosPlanningHttpCommon(TestPosHrHttpCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_admin.write({
            "group_ids": [Command.link(cls.env.ref('planning.group_planning_manager').id)]
        })
        cls.emp3.write({"name": "Pos Employee3", "pin": "1234"})

        resource_ids = [cls.emp1.resource_id.id, cls.emp2.resource_id.id]
        cls.role = cls.env['planning.role'].sudo().create({
            'name': 'PoS role',
            'resource_ids': [(6, 0, resource_ids)],
            'pos_config_ids': [(6, 0, cls.main_pos_config.ids)]
        })

        """
            Slot Setup:
            Assume current date and time is: June 4, 2025 at 12:00 PM

            - slot1:
                Assigned to emp1
                Start: June 4, 2025 at 11:00 AM (1 hour before current time)
                End:   June 5, 2025 at 1:00 PM (1 day and 1 hour after current time)
                This slot covers a continuous range from today to tomorrow, used to check if the system detects
                valid shift time across current and next day.

            - slot2:
                Assigned to emp2
                Start: June 4, 2025 at 10:00 AM (2 hours before current time)
                End:   June 7, 2025 at 1:00 PM (3 days and 1 hour after current time)
                This slot is used to test the system's behavior when a recurring valid shift exists for 3 consecutive days.
        """

        cls.slot1 = cls.env['planning.slot'].sudo().create({
            'resource_ids': cls.emp1.resource_id.ids,
            'start_datetime': datetime.now() - timedelta(hours=1),
            'end_datetime': datetime.now() + timedelta(days=1) + timedelta(hours=1),
        })

        cls.slot2 = cls.env['planning.slot'].sudo().create({
            'resource_ids': cls.emp2.resource_id.ids,
            'start_datetime': datetime.now() - timedelta(hours=2),
            'end_datetime': datetime.now() + timedelta(days=3) + timedelta(hours=1),
        })


@tagged("post_install", "-at_install")
class TestUi(TestPosPlanningHttpCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_pos_planning_tour_with_available_slots(self):
        """
            Test POS planning behavior when valid employee slots are available.

            For example: slot2
            This test sets up a planning slot that starts two hours before the current time today
            and ends one hour after the current time, repeating daily for the next three days.

            For instance, if the current time is 12:00 PM, the planning slot will be from 10:00 AM to 1:00 PM
            each day. The test verifies that POS correctly identifies valid shifts within this time
            window for each of the three days.

            If slots are available then POS log-in screen will show available slots employees with subtitle (planning 10:00 AM - 1:00 PM).
        """
        self.slot1.action_send()
        self.slot2.action_send()
        self.start_pos_tour("test_pos_planning_tour_with_available_slots", login="pos_admin")
