# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, timedelta

from odoo.tests import tagged

from .test_common import TestCommon


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestPlanningLeaves(TestCommon):
    def test_recurrency_public_holiday(self):
        # Create a public holiday
        self.employee_bert.resource_calendar_id = self.calendar
        self.env['resource.calendar.leaves'].create({
            'name': 'Public holiday',
            'calendar_id': self.calendar.id,
            'date_from': datetime(2024, 3, 13, 7, 0),
            'date_to': datetime(2024, 3, 13, 16, 0),
        })
        occuring_slot = self.env['planning.slot'].create({  # this should land on a Monday
            'start_datetime': self.random_monday_date + timedelta(hours=8),
            'end_datetime': self.random_monday_date + timedelta(hours=10),
            'resource_ids': self.resource_bert.ids,
            'repeat': True,
            'repeat_type': 'until',
            'repeat_until': datetime(2024, 3, 15, 17, 0),
            'repeat_interval': 1,
            'repeat_unit': 'day',
        })

        self.assertEqual(
            len(occuring_slot.recurrency_id.slot_ids),
            5,
            'All 5 recurring shifts should be generated.'
        )
        self.assertEqual(
            len(occuring_slot.recurrency_id.slot_ids.filtered(lambda s: s.resource_ids == self.resource_bert)),
            4,
            'Since one of the recurring shifts land on a public holiday, it won\'t be assigned to Bert.'
        )

    def test_recurrency_employee_leave(self):
        leave = self.env['hr.leave'].sudo().create({
            'work_entry_type_id': self.work_entry_type.id,
            'employee_id': self.employee_bert.id,
            'request_date_from': '2024-03-13',
            'request_date_to': '2024-03-13',
        })  # time off should land on Wednesday
        leave.action_approve()

        occuring_slot = self.env['planning.slot'].create({  # this should land on a Monday
            'start_datetime': self.random_monday_date + timedelta(hours=8),
            'end_datetime': self.random_monday_date + timedelta(hours=10),
            'resource_ids': self.resource_bert.ids,
            'repeat': True,
            'repeat_type': 'until',
            'repeat_until': datetime(2024, 3, 15, 17, 0),
            'repeat_interval': 1,
            'repeat_unit': 'day',
        })

        self.assertEqual(
            len(occuring_slot.recurrency_id.slot_ids),
            5,
            'All recurrent slots should be generated.'
        )
        self.assertEqual(
            len([slot for slot in occuring_slot.recurrency_id.slot_ids if slot.resource_ids]),
            4,
            'Four out of the five slots should have been normally generated and assigned to resource bert, since he is available on those dates.'
        )
        self.assertFalse(
            occuring_slot.recurrency_id.slot_ids[2].resource_ids,
            'Since the resource is on time-off on Wednesday, the recurring shift will be generated as an open shift.'
        )
