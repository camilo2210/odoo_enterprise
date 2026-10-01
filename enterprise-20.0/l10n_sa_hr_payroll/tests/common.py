from odoo.addons.hr_payroll.tests.common import TestPayrollBase
from odoo.tests.common import tagged
from datetime import date


@tagged("post_install", "post_install_l10n", "-at_install", "payslips_validation")
class TestSACommon(TestPayrollBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls._setup_common(
            country=cls.env.ref("base.sa"),
            structure=cls.env.ref(
                "l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure"
            ),
            structure_type=cls.env.ref(
                "l10n_sa_hr_payroll.ksa_employee_payroll_structure_type"
            ),
        )

        cls.sa_company = cls.env['res.company'].create({
            'name': 'Saudi Arabia Company',
            'country_id': cls.env.ref('base.sa').id,
        })

        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.sa_company.ids))
        cls.env.company.tz = 'Asia/Riyadh'
        cls.env.user.tz = 'Asia/Riyadh'

        cls.saudi_work_contact = cls.env["res.partner"].create(
            {
                "name": "KSA Local Employee",
                "company_id": cls.env.company.id,
            }
        )

        cls.saudi_employee = cls.env["hr.employee"].create(
            {
                "name": "KSA Local Employee",
                "address_id": cls.saudi_work_contact.id,
                "company_id": cls.env.company.id,
                "country_id": cls.env.ref("base.sa").id,
                "structure_type_id": cls.env.ref(
                    "l10n_sa_hr_payroll.ksa_employee_payroll_structure_type"
                ).id,
                "resource_calendar_id": cls.resource_calendar.id,
                "tz": "Asia/Riyadh",
                "date_version": date(2024, 1, 1),
                "contract_date_start": date(2024, 1, 1),
                "wage": 12000,
                "l10n_sa_housing_allowance": 1000,
                "l10n_sa_transportation_allowance": 200,
                "l10n_sa_other_allowances": 500,
                "l10n_sa_number_of_days": 21,
                "l10n_sa_company_social_insurance_percentage": 0.09,
                "l10n_sa_company_oh_insurance_percentage": 0.0075,
                "l10n_sa_company_unemployment_insurance_percentage": 0.02,
                "l10n_sa_employee_social_insurance_percentage": 0.09,
                "l10n_sa_employee_oh_insurance_percentage": 0.0025,
                "l10n_sa_employee_unemployment_insurance_percentage": 0.005,
                "l10n_sa_iqama_annual_amount": 6000.0,
                "l10n_sa_medical_insurance_annual_amount": 4800.0,
                "l10n_sa_work_permit_annual_amount": 3600.0,
            }
        )

        cls.sa_full_week_calendar = cls.env['resource.calendar'].create({
            'name': 'Calender Days 40h/week',
            'attendance_ids': [
                    (0, 0, {'dayofweek': '6', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '0', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '1', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '2', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '3', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '4', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0, 'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_sa_work_entry_type_weekend').id}),
                    (0, 0, {'dayofweek': '5', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0, 'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_sa_work_entry_type_weekend').id}),
            ]
        })
