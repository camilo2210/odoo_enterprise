# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon
from odoo.fields import Command
from odoo.tools import BinaryBytes


class TestL10NHkHrPayrollAccountCommon(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setup_armageddon_tax(cls, tax_name, company_data):
        # Hong Kong doesn't have any tax, so this methods will throw errors if we don't return None
        return None

    @classmethod
    @TestPayslipValidationCommon.setup_country('hk')
    def setUpClass(cls):
        super().setUpClass()

        payroll_manager = cls.env.ref('hr_payroll.group_hr_payroll_manager')
        cls.env.user.group_ids |= payroll_manager

        cls.resource_calendar = cls.env['resource.calendar'].create({
            'name': "Test Calendar : 40 Hours/Week",
            'company_id': cls.env.company.id,
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
                (0, 0, {'dayofweek': '5', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_hk_work_entry_type_weekend').id}),
                (0, 0, {'dayofweek': '5', 'hour_from': 13, 'hour_to': 17.0, 'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_hk_work_entry_type_weekend').id}),
                (0, 0, {'dayofweek': '6', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_hk_work_entry_type_weekend').id}),
                (0, 0, {'dayofweek': '6', 'hour_from': 13, 'hour_to': 17.0, 'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_hk_work_entry_type_weekend').id}),
            ]
        })

        cls._setup_common(
            country=cls.env.ref('base.hk'),
            structure=cls.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary'),
            structure_type=cls.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
            resource_calendar=cls.resource_calendar,
            version_fields={
                'date_version': date(2023, 1, 1),
                'contract_date_start': date(2023, 1, 1),
                'wage': 20000.0,
                'l10n_hk_internet': 200.0,
            },
            employee_fields={
                'marital': "single",
            }
        )

        # Set up a test MPF scheme,... and set it on the employee
        cls.mpf_scheme = cls.env['l10n_hk.mpf.scheme'].with_company(cls.env.company).create({
            'name': 'Mandatory Provident Fund Scheme',
            'registration_number': 'MT00298',
            'employer_account_number': '123456789012',
            'payroll_group_ids': [Command.create({
                'name': 'Staff - Monthly',
                'group_id': 'MLY',
                'contribution_frequency': 'monthly',
                'company_id': cls.env.company.id,
                'is_default': True,
            })],
        })
        cls.member_class = cls.env['l10n_hk.member.class'].with_company(cls.env.company).create({
            'name': 'GT1',
            'company_id': cls.env.company.id,
            'scheme_id': cls.mpf_scheme.id,
            'definition_of_service': 'date_of_employment',
            'contribution_type_ids': [Command.create({
                'contribution_type': 'employee',
                'contribution_option': 'top_up',
                'amount': 5,
                'definition_of_income': 'relevant_wages',
            }), Command.create({
                'contribution_type': 'employer',
                'contribution_option': 'match',
            })],
        })

        admin = cls.env['res.users'].search([('login', '=', 'admin')])
        admin.company_ids |= cls.env.company

        cls.env.user.tz = 'Asia/Hong_Kong'

    @classmethod
    def _setup_employee(cls, country, structure_type, resource_calendar, contract_fields=False, employee_fields=False, work_contact_fields=False):
        """ Simple helper to create a new employee. """
        work_contact = cls.env["res.partner"].create({
            "name": country.code.upper() + " Employee",
            "company_id": cls.env.company.id,
            **(work_contact_fields or {}),
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
    def _create_new_version(cls, employee, new_version_date, contract_fields=None):
        """ Simple helper to create a new version and contract at a given date. """
        contract_fields = contract_fields or {}
        new_version = employee.version_id.copy(
            default={
                'date_version': new_version_date,
                **contract_fields,
            }
        )
        return new_version

    @classmethod
    def _set_test_employee(cls, employee):
        """ Helper that sets some variables in self, so that _generate_payslip picks the intended employee. """
        cls.employee = employee
        cls.version = employee.version_id
        cls.structure = employee.structure_id

    # Empf Helpers

    def _create_payrun_and_report(self, date_start, date_end, validate_report=True, payrun_data=None):
        payslip_run = self.env['hr.payslip.run'].create({
            'name': "Test Payslip Run",
            'date_start': date_start,
            'date_end': date_end,
            'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
            'l10n_hk_payroll_scheme_id': self.mpf_scheme.id,
            **(payrun_data or {}),
        })
        payslip_run._generate_payslips()
        payslip_run.action_validate()

        report = payslip_run.l10n_hk_payroll_empf_report_id
        if validate_report:
            report.action_validate()
        return report

    def _create_empf_report(self, date_start, date_end, validate_report=True):
        report = self.env['l10n_hk.empf.contribution.report'].create([{
            'contribution_period_start': date_start,
            'contribution_period_end': date_end,
            'scheme_id': self.mpf_scheme.id,
        }])
        if validate_report:
            report.action_validate()
        return report

    def _get_csv_reports_per_type(self, report, report_type=None):
        """
        Helper to get csv for each type of report for the given report.
        Optionally, the report type can be provided if only this specific type is tested, in which case we return the
        attachment corresponding to this type right away.
        """
        existing_csv_reports = self.env["ir.attachment"].search(
            [
                ("res_id", "=", report.id),
                ("res_model", "=", "l10n_hk.empf.contribution.report"),
            ]
        )
        csv_reports_per_type = {
           'new_employees': None,
           'contributions': None,
           'terminated_employees': None,
        }
        for csv_report in existing_csv_reports:
            for label in csv_reports_per_type:
                if label in csv_report.name:
                    csv_reports_per_type[label] = csv_report

        return csv_reports_per_type[report_type] if report_type else csv_reports_per_type

    def _create_test_rental(self, employee, override_vals=None):
        """
        Very simply create a test draft rental with a given address to easy testing.
        The rental is created and then returned with_user as the employee.
        """
        override_vals = override_vals or {}
        return self.env['l10n_hk.rental'].create({
            # Address
            'state_id': self.env.ref('base.state_hk_hk').id,
            'district': 'Central & Western',
            'street': '58 Stanley St',
            'building': 'Oriental House',
            'block': 'A',
            'floor': '10',
            'flat': '3',
            # Rental description
            'landlord_name': 'Mr Landlord',
            'nature': 'FLAT/HOUSE',
            'amount': 8000,
            'lease_type': 'reimbursement',
            'date_start': date(2025, 1, 1),
            # Other info
            'employee_id': employee.id,
            'company_id': employee.company_id.id,
            'lease_agreement_file': BinaryBytes(b'file'),
            'stamped_duty_file': BinaryBytes(b'file'),
            **override_vals,
        })
