# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date, time, datetime
from zoneinfo import ZoneInfo

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


class TestL10NPhHrPayrollCommon(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('ph')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_manager')

        cls.work_add_partner = cls.env['res.partner'].create({
            'name': 'Philippines Office',
            'street': '232 Juan Luna Street',
            'street2': 'Room 703, Padilla Delos Reyes Building',
            'city': 'Manila',
            'state_id': cls.env.ref('base.state_ph_01').id,
            'country_id': cls.env.ref('base.ph').id,
            'company_id': cls.env.company.id,
        })
        cls.work_location = cls.env['hr.work.location'].create({
            'name': 'Seventh Floor, Unit 3',
            'location_type': 'office',
            'address_id': cls.work_add_partner.id,
            'company_id': cls.env.company.id,
            'l10n_ph_hr_payroll_min_daily_wage': 695.00,
        })
        cls.company.write({
            'name': 'My Philippines Company Inc.',
            'street': '12th Floor, Tower 1, Ayala Triangle',
            'street2': 'Ayala Avenue, Brgy. Bel-Air',
            'city': 'Makati City',
            'zip': '1226',
            'vat': '123-456-789-000',
            'state_id': cls.env.ref('base.state_ph_01').id,
        })

        cls.env.user.company_ids |= cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))

        cls.resource_calendar = cls.env['resource.calendar'].create({
            'name': "Test Calendar : 40 Hours/Week",
            'company_id': cls.company.id,
            'hours_per_day': 8.0,
            'hours_per_week': 40,
            'full_time_required_hours': 40,
            'attendance_ids': [
                (5, 0, 0),
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 17.0}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 17.0}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 17.0}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 17.0}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 17.0}),
            ]
        })
        cls.env.company.write({
            'resource_calendar_id': cls.resource_calendar.id,
            'country_id': cls.env.ref('base.ph').id,
            'tz': 'Asia/Manila',
        })

        cls.country = cls.env.ref('base.ph')
        cls.tz = 'Asia/Manila'
        cls.env.user.tz = cls.tz
        cls.car = None
        cls.structure_type = cls.env.ref('l10n_ph_hr_payroll.structure_type_employee_ph')

    @classmethod
    def _setup_employee(cls, country, structure_type, resource_calendar, contract_fields=False, employee_fields=False):
        """ Simple helper to create a new employee. """
        work_contact = cls.env["res.partner"].create({
            "name": country.code.upper() + " Employee",
            "company_id": cls.env.company.id,
        })

        employee = (
            cls.env["hr.employee"]
            .sudo()
            .create(
                {
                    "name": country.code.upper() + " Employee",
                    "work_contact_id": work_contact.id,
                    "address_id": work_contact.id,
                    "resource_calendar_id": resource_calendar.id,
                    "company_id": cls.env.company.id,
                    "country_id": country.id,
                    "structure_type_id": structure_type.id,
                    "contract_date_start": date(2016, 1, 1),
                    "date_version": date(2016, 1, 1),
                    "wage": 1000.0,
                    **(employee_fields or {}),
                }
            )
            .sudo(False)
        )

        contract = employee.sudo().version_id
        if contract_fields:
            contract.write(contract_fields)

        return employee

    @classmethod
    def _set_test_employee(cls, employee):
        """ Helper that sets some variables in self, so that _generate_payslip picks the intended employee. """
        cls.employee = employee
        cls.version = employee.version_id
        cls.structure = employee.structure_id

    def _make_work_entry(self, work_entry_type, work_entry_date, hour_from, hour_to):
        """
        Create a work entry of the given type, for the given day.
        Use _set_test_employee first so that the correct employee is set.
        """
        work_entry_type = self.env.ref(f'hr_work_entry.{work_entry_type}')
        work_entry_date = datetime.combine(work_entry_date, time.min, ZoneInfo(self.tz))

        leave = self.env['hr.leave'].create([{
            'name': work_entry_type.name,
            'employee_id': self.employee.id,
            'work_entry_type_id': work_entry_type.id,
            'request_date_from': work_entry_date,
            'request_date_to': work_entry_date,
            'company_id': self.env.company.id,
            'request_hour_from': hour_from,
            'request_hour_to': hour_to,
        }])
        if leave.state != 'validate':
            leave.action_approve()

    def _make_holiday(self, work_entry_type, holiday_date_from, holiday_date_to=None):
        """
        Create a work entry of the given type, for the given day.
        Use _set_test_employee first so that the correct employee is set.

        Note that we ignore any time provided in holiday_date_from and holiday_date_to; and will automatically force
        it to match the regular PH work day in the manila time zone (8am to 5pm)
        """
        holiday_date_to = holiday_date_to or holiday_date_from

        date_from = datetime.combine(holiday_date_from, time.min, tzinfo=ZoneInfo(self.tz)).astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        date_to = datetime.combine(holiday_date_to, time.max, tzinfo=ZoneInfo(self.tz)).astimezone(ZoneInfo('UTC')).replace(tzinfo=None)

        self.env['resource.calendar.leaves'].create({
            'name': 'Public Holiday',
            'date_from': date_from,
            'date_to': date_to,
            'calendar_id': self.resource_calendar.id,
            'work_entry_type_id': self.env.ref(f'hr_work_entry.{work_entry_type}').id,
            'count_as': 'absence',
        })

    def _set_night_shift(self):
        """ Small helper that sets a night shift on Tuesdays for tests needing them. """
        self.resource_calendar.attendance_ids = [
            (5, 0, 0),
            (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
            (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 17.0}),
            (0, 0, {'dayofweek': '1', 'hour_from': 21, 'hour_to': 24, 'work_entry_type_id': self.env.ref('hr_work_entry.l10n_ph_hr_payroll_ns').id}),
            (0, 0, {'dayofweek': '2', 'hour_from': 1, 'hour_to': 6, 'work_entry_type_id': self.env.ref('hr_work_entry.l10n_ph_hr_payroll_ns').id}),
            (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
            (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 17.0}),
            (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
            (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 17.0}),
            (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
            (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 17.0}),
        ]
