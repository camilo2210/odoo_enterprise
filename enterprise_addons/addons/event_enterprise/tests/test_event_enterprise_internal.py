from datetime import datetime

from odoo.addons.event.tests.test_event_internals import TestEventInternalsCommon
from odoo.tests import tagged


@tagged('event_registration', 'post_install', '-at_install')
class TestEventEnterpriseInternals(TestEventInternalsCommon):

    def test_registration_dates_update_on_event_date_change_and_slots(self):
        """Test that stored event_begin_date updates when event dates are modified,
        and that registration dates use slot dates when event has slots"""
        new_begin = datetime(2024, 9, 1, 10, 0, 0)
        new_end = datetime(2024, 9, 5, 18, 0, 0)
        registration = self._create_registrations(self.event_0, 1)
        self.event_0.write({
            'date_begin': new_begin,
            'date_end': new_end,
        })

        self.assertRecordValues(registration, [{
            'event_begin_date': new_begin,
            'event_end_date': new_end,
        }])

        registration.unlink()
        self.event_0.is_multi_slots = True
        slot = self.env['event.slot'].create({
            'event_id': self.event_0.id,
            'date': self.event_0.date_begin.date(),
            'start_hour': 14.0,
            'end_hour': 16.0,
        })
        registration = self._create_registrations_for_slot_and_ticket(event=self.event_0, slot=slot, ticket=False, count=1)

        # Verify registration uses slot dates, not event dates
        self.assertRecordValues(registration, [{
            'event_begin_date': slot.start_datetime,
            'event_end_date': slot.end_datetime,
        }])

        slot.write({'start_hour': 12.5, 'end_hour': 14.5})
        registration.invalidate_recordset(['event_begin_date', 'event_end_date'])

        self.assertRecordValues(registration, [{
            'event_begin_date': slot.start_datetime,
            'event_end_date': slot.end_datetime,
        }])
