from datetime import datetime, timedelta, UTC
from freezegun import freeze_time
from zoneinfo import ZoneInfo

from odoo.addons.appointment.tests.common import AppointmentCommon
from odoo.tests import tagged, users


@tagged('appointment_leave')
@tagged('at_install', '-post_install')  # LEGACY at_install
class AppointmentLeaveTest(AppointmentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.start_leave = cls.reference_monday + timedelta(hours=2)  # 02/14/2022 9am
        cls.stop_leave = cls.reference_monday + timedelta(hours=5)  # 02/14/2022 12pm
        # Creating new appointments and resources to ensure they are not associated
        # with any existing data and provide a clean schedule for comparison.
        cls.resource_1, cls.resource_2 = cls.env['appointment.resource'].create([{
            'capacity': 1,
            'name': 'Resource 1',
        }, {
            'capacity': 1,
            'name': 'Resource 2',
        }])
        # Appointment types
        # Slots = Mondays and Tuesdays from 8am -> 2pm
        leave_apt_values = {
            'appointment_tz': 'UTC',
            'appointment_duration': 1,
            'category': 'recurring',
            'max_schedule_days': 15,
            'slot_ids': [
                (0, False, {'weekday': weekday,
                            'start_hour': hour,
                            'end_hour': hour + 1,
                           })
                for weekday in range(1, 3)
                for hour in range(8, 14)
            ],
        }
        resource_apt_type_values = {
            **leave_apt_values,
            'name': 'Resource Appt Type',
            'schedule_based_on': 'resources',
            'resource_ids': [(4, cls.resource_1.id), (4, cls.resource_2.id)],
        }
        user_apt_type_values = {
            **leave_apt_values,
            'name': 'User Appt Type',
            'schedule_based_on': 'users',
            'staff_user_ids': [(4, cls.apt_manager.id), (4, cls.apt_user.id)],
        }
        [
            cls.resource_apt_type_1,
            cls.resource_apt_type_2,
            cls.user_apt_type_1,
            cls.user_apt_type_2,
        ] = cls.env['appointment.type'].create([
            resource_apt_type_values,
            resource_apt_type_values,
            user_apt_type_values,
            user_apt_type_values,
        ])
        # Slots
        cls.base_slots_months = [{
            'name_formated': 'February 2022',
            'month_date': datetime(2022, 2, 14),
            'weeks_count': 5,
        }]
        cls.base_slots = {
            'enddate': cls.global_slots_enddate,  # last day of last week of February
            'startdate': cls.reference_now_monthweekstart,  # starts on a Sunday, first week containing Feb day
            'slots_start_hours': list(range(8, 14)),  # hours from 8am to 2pm
            'slots_startdate': cls.reference_monday.date(),  # considering slots from 02/14/2022 + 2 weeks
            'slots_enddate': cls.reference_monday.date() + timedelta(days=14),
            'slots_weekdays_nowork': range(2, 7),  # only on Monday/Tuesday (0, 1)
        }
        cls.leave_slots = {
            **cls.base_slots,
            'slots_day_specific': {
                cls.reference_monday.date(): [
                    {'start': 8, 'end': 9},
                    {'start': 12, 'end': 13},
                    {'start': 13, 'end': 14},
                ],  # leaves on 9am - 12am
             },
        }

    # --------------------------------------
    # Utils
    # --------------------------------------

    def _assert_initial_slots(self):
        """ Asserting that every appointment types initial slots are the same. """
        self._check_slots(self.user_apt_type_1, self.base_slots)
        self._check_slots(self.user_apt_type_2, self.base_slots)
        self._check_slots(self.resource_apt_type_1, self.base_slots)
        self._check_slots(self.resource_apt_type_2, self.base_slots)

    def _check_slots(self, apt_type, expected_slots, filter_users=None, filter_resources=None, tz='UTC'):
        """ Verifying slots for the given appointment type and timezone.
        Only for the given users/resources if there're some specified.
        """
        with freeze_time(self.reference_now):
            slots = apt_type._get_appointment_slots(tz, filter_users, filter_resources)
        self.assertSlots(slots, self.base_slots_months, expected_slots)

    def _init_leaves(self):
        """ Initialize some leaves for testing. """
        vals = {
            'date_from': self.start_leave,
            'date_to': self.stop_leave,
        }
        leaves = self.env['appointment.leave'].create([
            {**vals, 'leave_type': 'appointments'},
            {**vals, 'leave_type': 'appointments', 'appointment_type_ids': self.user_apt_type_1},
            {**vals, 'leave_type': 'appointments', 'appointment_type_ids': self.user_apt_type_1 + self.resource_apt_type_1},
            {**vals, 'leave_type': 'users', 'user_ids': self.apt_user},
            {**vals, 'leave_type': 'users', 'user_ids': self.apt_user, 'appointment_type_ids': self.user_apt_type_1},
            {**vals, 'leave_type': 'users', 'user_ids': self.apt_user + self.apt_manager, 'appointment_type_ids': self.user_apt_type_1 + self.user_apt_type_2},
            {**vals, 'leave_type': 'resources', 'resource_ids': self.resource_1},
            {**vals, 'leave_type': 'resources', 'resource_ids': self.resource_1, 'appointment_type_ids': self.resource_apt_type_1},
            {**vals, 'leave_type': 'resources', 'resource_ids': self.resource_1 + self.resource_2, 'appointment_type_ids': self.resource_apt_type_1 + self.resource_apt_type_2},
        ])
        return leaves

    # --------------------------------------
    # Tests
    # --------------------------------------

    @users('apt_manager')
    def test_leave_after_appointment_deletion(self):
        """ Deleting an appointment type should remove all the leaves
        that were exclusively restricted to this appointment.
        """
        leaves = self._init_leaves()
        leaves_to_unlink = leaves.filtered(lambda leave: self.user_apt_type_1 == leave.appointment_type_ids)
        self.assertTrue(bool(leaves_to_unlink.exists()))
        # Unlink appointment type
        self.user_apt_type_1.unlink()
        self.assertFalse(bool(leaves_to_unlink.exists()))
        self.assertTrue(all(leave.exists() for leave in leaves - leaves_to_unlink))

    @users('apt_manager')
    def test_leave_after_resource_deletion(self):
        """ Deleting a resource should remove all the leaves that were exclusively set on this resource. """
        leaves = self._init_leaves()
        leaves_to_unlink = leaves.filtered(lambda leave: self.resource_1 == leave.resource_ids)
        self.assertTrue(bool(leaves_to_unlink.exists()))
        # Unlink resource
        self.resource_1.unlink()
        self.assertFalse(bool(leaves_to_unlink.exists()))
        self.assertTrue(all(leave.exists() for leave in leaves - leaves_to_unlink))

    @users('apt_manager')
    def test_leave_after_user_deletion(self):
        """ Deleting a user should remove all the leaves that were exclusively set on this user. """
        leaves = self._init_leaves()
        leaves_to_unlink = leaves.filtered(lambda leave: self.apt_user == leave.user_ids)
        self.assertTrue(bool(leaves_to_unlink.exists()))
        # Unlink user
        self.apt_user.unlink()
        self.assertFalse(bool(leaves_to_unlink.exists()))
        self.assertTrue(all(leave.exists() for leave in leaves - leaves_to_unlink))

    @users('apt_manager')
    def test_leave_based_on_appointments(self):
        self._assert_initial_slots()
        # Creating an appointment leave for a specific appointment type
        leave = self.env['appointment.leave'].create({
            'appointment_type_ids': [(4, self.user_apt_type_1.id)],
            'date_from': self.start_leave,
            'date_to': self.stop_leave,
            'leave_type': 'appointments',
        })
        # This appointment type should be unavailable during the leave
        self._check_slots(self.user_apt_type_1, self.leave_slots)
        # Other appointment types should still have the same slots
        self._check_slots(self.user_apt_type_2, self.base_slots)
        self._check_slots(self.resource_apt_type_1, self.base_slots)
        self._check_slots(self.resource_apt_type_2, self.base_slots)
        # Removing the appointment_type_ids on the leave should apply the leave on every appointment types
        leave.write({'appointment_type_ids': False})
        self._check_slots(self.user_apt_type_1, self.leave_slots)
        self._check_slots(self.user_apt_type_2, self.leave_slots)
        self._check_slots(self.resource_apt_type_1, self.leave_slots)
        self._check_slots(self.resource_apt_type_2, self.leave_slots)

    @users('apt_manager')
    def test_leave_based_on_resources(self):
        self._assert_initial_slots()
        # Creating an appointment leave for a specific resource and appointment
        leave = self.env['appointment.leave'].create({
            'appointment_type_ids': [(4, self.resource_apt_type_1.id)],
            'date_from': self.start_leave,
            'date_to': self.stop_leave,
            'leave_type': 'resources',
            'resource_ids': [(4, self.resource_1.id)],
        })
        # Only this resource for this appointment type should have the leave
        self._check_slots(self.resource_apt_type_1, self.leave_slots, filter_resources=self.resource_1)
        # Other resource and appointment types shouldn't be impacted
        self._check_slots(self.user_apt_type_1, self.base_slots)
        self._check_slots(self.user_apt_type_2, self.base_slots)
        self._check_slots(self.resource_apt_type_1, self.base_slots, filter_resources=self.resource_2)
        self._check_slots(self.resource_apt_type_2, self.base_slots)
        # Removing the appointment type on the leave should set the resource on leave for all its appointments
        leave.write({'appointment_type_ids': False})
        self._check_slots(self.resource_apt_type_1, self.leave_slots, filter_resources=self.resource_1)
        self._check_slots(self.resource_apt_type_2, self.leave_slots, filter_resources=self.resource_1)
        # Other resource should not be impacted
        self._check_slots(self.resource_apt_type_1, self.base_slots, filter_resources=self.resource_2)
        self._check_slots(self.resource_apt_type_2, self.base_slots, filter_resources=self.resource_2)

    @users('apt_manager')
    def test_leave_based_on_users(self):
        self._assert_initial_slots()
        # Creating an appointment leave for a specific user and appointment
        leave = self.env['appointment.leave'].create({
            'appointment_type_ids': [(4, self.user_apt_type_1.id)],
            'date_from': self.start_leave,
            'date_to': self.stop_leave,
            'leave_type': 'users',
            'user_ids': [(4, self.apt_manager.id)],
        })
        # Only this user for this appointment type should have the leave
        self._check_slots(self.user_apt_type_1, self.leave_slots, filter_users=self.apt_manager)
        # Other user and appointment types shouldn't be impacted
        self._check_slots(self.user_apt_type_1, self.base_slots, filter_users=self.apt_user)
        self._check_slots(self.user_apt_type_2, self.base_slots)
        self._check_slots(self.resource_apt_type_1, self.base_slots)
        self._check_slots(self.resource_apt_type_2, self.base_slots)
        # Removing the appointment type on the leave should set the user on leave for all its appointments
        leave.write({'appointment_type_ids': False})
        self._check_slots(self.user_apt_type_1, self.leave_slots, filter_users=self.apt_manager)
        self._check_slots(self.user_apt_type_2, self.leave_slots, filter_users=self.apt_manager)
        # Other user should not be impacted
        self._check_slots(self.user_apt_type_1, self.base_slots, filter_users=self.apt_user)
        self._check_slots(self.user_apt_type_2, self.base_slots, filter_users=self.apt_user)

    @users('apt_manager')
    def test_leave_recurring_appointments_different_timezones(self):
        """ If a leave is set on recurring appointment types using different timezones,
        check that the leave dates initially created using the user tz are
        correctly shifted per appointment type.
        NB: On the leave date, the Europe/Brussels timezone was in CET meaning GMT+1
        """
        # Set 2 appointment types on different timezones
        self.user_apt_type_1.write({'appointment_tz': 'Europe/Brussels'})  # GMT+1
        self.user_apt_type_2.write({'appointment_tz': 'Europe/Moscow'})  # GMT+3
        # Their slots in their respective timezones should be the same
        self._check_slots(self.user_apt_type_1, self.base_slots, tz='Europe/Brussels')
        self._check_slots(self.user_apt_type_2, self.base_slots, tz='Europe/Moscow')
        # Create a leave on both appointment types from tz 'Europe/Brussels'
        # 9am-12pm Europe/Brussels GMT+1, storing 8am-11am UTC
        self.env['appointment.leave'].create({
            'appointment_type_ids': [(4, self.user_apt_type_1.id), (4, self.user_apt_type_2.id)],
            'date_from': self.start_leave.replace(tzinfo=ZoneInfo('Europe/Brussels')).astimezone(UTC).replace(tzinfo=None),
            'date_to': self.stop_leave.replace(tzinfo=ZoneInfo('Europe/Brussels')).astimezone(UTC).replace(tzinfo=None),
            'leave_type': 'appointments',
        })
        # Requested tz = 'Europe/Brussels'
        # Expected leave (9am-12pm)
        self._check_slots(self.user_apt_type_1, self.leave_slots, tz='Europe/Brussels')  # 8am-2pm, leave on 9am-12pm
        self._check_slots(
            self.user_apt_type_2,
            {
                **self.base_slots,
                'slots_start_hours': list(range(6, 12)),  # 6am-12pm Europe/Brussels (= 8-2pm Moscow apt tz)
                'slots_day_specific': {
                    self.reference_monday.date(): [  # leave on 9am-12pm
                        {'start': 6, 'end': 7},
                        {'start': 7, 'end': 8},
                        {'start': 8, 'end': 9},
                    ],
                },
            },
            tz='Europe/Brussels',
        )
        # Requested tz = 'Europe/Moscow'
        # Expected leave (11am-2pm)
        self._check_slots(
            self.user_apt_type_1,
            {
                **self.base_slots,
                'slots_start_hours': list(range(10, 16)),  # 10am-4pm Europe/Moscow (= 8-2pm Brussels apt tz)
                'slots_day_specific': {
                    self.reference_monday.date(): [  # leave on 11am-2pm
                        {'start': 10, 'end': 11},
                        {'start': 14, 'end': 15},
                        {'start': 15, 'end': 16},
                    ],
                },
            },
            tz='Europe/Moscow',
        )
        self._check_slots(
            self.user_apt_type_2,
            {
                **self.base_slots,  # 8am-2pm
                'slots_day_specific': {
                    self.reference_monday.date(): [  # leave on 11am-2pm
                        {'start': 8, 'end': 9},
                        {'start': 9, 'end': 10},
                        {'start': 10, 'end': 11},
                    ],
                },
            },
            tz='Europe/Moscow',
        )
