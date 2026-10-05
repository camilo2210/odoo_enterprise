# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from zoneinfo import ZoneInfo
from dateutil.relativedelta import relativedelta

from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon
from odoo.tests.common import tagged, freeze_time
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon
from odoo.tools.float_utils import float_compare


@tagged('post_install', '-at_install', 'declarations_validation')
class TestDeclarationsValidation(TestPayslipValidationCommon, TestBelgiumCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids |= cls.env.ref('hr.group_hr_manager') | cls.env.ref("hr_payroll.group_hr_payroll_officer")
        cls.company_data['company'].write({
            'vat': 'BE0897223670',
            'phone': '0471098765',
            'street': 'Test street',
            'city': 'Test city',
            'zip': '8292',
        })
        cls.company_data['company'].current_payroll_config_id.write({
            'l10n_be_company_number': '0123456749',
            'l10n_be_revenue_code': '1234',
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010').id,
        })

        cls.env.user.tz = 'Europe/Brussels'

        cls.EMPLOYEES_COUNT = 5

        cls.resource_calendar_38_hours_per_week = cls.env['resource.calendar'].sudo().create([{
            'name': "Test Calendar : 38 Hours/Week",
            'company_id': cls.env.company.id,
            'hours_per_day': 7.6,
            'hours_per_week': 38.0,
            'full_time_required_hours': 38.0,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': cls.env.ref('hr_work_entry.be_work_entry_type_attendance').id

            }) for dayofweek, hour_from, hour_to in [
                ("0", 8.0, 12.0),
                ("0", 13.0, 16.6),
                ("1", 8.0, 12.0),
                ("1", 13.0, 16.6),
                ("2", 8.0, 12.0),
                ("2", 13.0, 16.6),
                ("3", 8.0, 12.0),
                ("3", 13.0, 16.6),
                ("4", 8.0, 12.0),
                ("4", 13.0, 16.6),
            ]],
        }])

        cls.work_contacts = cls.env['res.partner'].create([{
            'name': f"Test Work Contact {i}",
        } for i in range(cls.EMPLOYEES_COUNT)])

        brand = cls.env['fleet.vehicle.model.brand'].sudo().create([{
            'name': "Test Brand"
        }])

        model = cls.env['fleet.vehicle.model'].sudo().create([{
            'name': "Test Model",
            'brand_id': brand.id
        }])

        with freeze_time('2020-10-08'):
            cars = cls.env['fleet.vehicle'].sudo().create([{
                'name': f"Test Car {i}",
                'license_plate': f"TEST{i}",
                'driver_id': cls.work_contacts[i].id,
                'company_id': cls.env.company.id,
                'model_id': model.id,
                'contract_date_start': datetime.date(2020, 10, 8),
                'co2': 88.0,
                'car_value': 38000.0,
                'fuel_type': "diesel",
                'acquisition_date': datetime.date(2020, 1, 1)
            } for i in range(cls.EMPLOYEES_COUNT)])

        cls.env['fleet.vehicle.log.contract'].sudo().create([{
            'name': f"Test Contract {i}",
            'vehicle_id': cars[i].id,
            'company_id': cls.env.company.id,
            'start_date': datetime.date(2020, 10, 8),
            'expiration_date': datetime.date(2021, 10, 8),
            'state': "open",
            'cost_generated': 0.0,
            'cost_frequency': "monthly",
            'recurring_cost_amount_depreciated': 450.0
        } for i in range(cls.EMPLOYEES_COUNT)])

        cls.employees = cls.env['hr.employee'].create([{
            'name': f"Test Employee {i}",
            'work_contact_id': cls.work_contacts[i].id,
            'private_street': 'Employee Street %s' % i,
            'private_zip': f'100{i}',
            'private_city': f'Employee City {i}',
            'private_country_id': cls.env.ref('base.be').id,
            'resource_calendar_id': cls.resource_calendar_38_hours_per_week.id,
            'company_id': cls.env.company.id,
            'distance_home_work': 75,
            'certificate': 'master',
            'niss': '91072800%s' % i + str(97 - int('91072800%s' % i) % 97),
            'car_id': cars[i].id,
            'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
            'contract_date_start': datetime.date(2018, 12, 31),
            'date_version': datetime.date(2018, 12, 31),
            'wage': 2650.0 + i * 100,
            'transport_mode_car': True,
            'fuel_card': 150.0,
            'internet': 38.0,
            'mobile': 30.0,
            'meal_voucher_amount': 7.45,
            'ip_wage_rate': 0.25,
            'rd_percentage': 1.0,
            'l10n_be_lsa_monthly_misc_base_amount': 150,
            'l10n_be_joint_committee_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'lang': 'fr_BE',
        } for i in range(cls.EMPLOYEES_COUNT)])

        cls.company_executive_employee = cls.env['hr.employee'].create([{
            'name': "Company Executive",
            'private_street': 'Employee Street',
            'private_zip': '100',
            'private_city': 'Employee City',
            'private_country_id': cls.env.ref('base.be').id,
            'resource_calendar_id': cls.resource_calendar_38_hours_per_week.id,
            'company_id': cls.env.company.id,
            'certificate': 'master',
            'niss': '91072800%s' % 5 + str(97 - int('91072800%s' % 5) % 97),
            'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
            'contract_date_start': datetime.date(2018, 12, 31),
            'date_version': datetime.date(2018, 12, 31),
            'wage': 5000,
            'l10n_be_joint_committee_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_999').id,
            'lang': 'fr_BE',
        }])

        cls.contracts = cls.employees.version_id

        cls.batch = cls.env['hr.payslip.run'].create({
            'name': 'History Batch',
            'date_start': datetime.date(2021, 1, 1),
            'date_end': datetime.date(2021, 12, 31),
            'company_id': cls.env.company.id,
            'structure_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
        })

        # Janvier 2021: Salary + Commissions
        # Février 2021: Salary
        # Mars 2021: Salary (10 unpaid days)
        # Avril 2021: Salary + Warrants (2 payslips)
        # Mai 2021: Salary (20 legal days)
        # Juin 2021: Salary + Double Holiday Pay (2 payslips)
        # Juillet 2021: Salary + Commissions
        # Aout 2021: Salary
        # Septembre 2021: Salary
        # Octobre 2021: Salary + Commissions
        # Novembre 2021: Salary
        # Décembre 2021: Salary (recup de decembre) + 13eme mois (2 payslips)
        cls.journal = cls.env['account.journal'].search([('type', '=', 'general')], limit=1)

        # Janvier 2021: Salary + Commissions
        cls.january_2021 = cls.env['hr.payslip'].create([{
            'name': f'Payslip Jan 2021 {i}',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 1, 1),
            'date_to': datetime.datetime(2021, 1, 31),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])
        for payslip in cls.january_2021:
            payslip._set_input_value('COMMISSION', 2000)

        # Février 2021: Salary
        cls.february_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip Feb 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 2, 1),
            'date_to': datetime.datetime(2021, 2, 28),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])

        # Mars 2021: Salary (10 unpaid days)
        cls.march_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip Mar 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 3, 1),
            'date_to': datetime.datetime(2021, 3, 31),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])

        # Avril 2021: Salary + Warrants (2 payslips)
        cls.april_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip Apr 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 4, 1),
            'date_to': datetime.datetime(2021, 4, 30),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])

        cls.warrant_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip Warrant 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 4, 1),
            'date_to': datetime.datetime(2021, 4, 30),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_structure_warrant').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])
        for payslip in cls.warrant_2021:
            payslip._set_input_value('WARRANT_WITHOUT_ONSS', 2000)

        # Mai 2021: Salary (20 legal days)
        cls.may_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip May 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 5, 1),
            'date_to': datetime.datetime(2021, 5, 31),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])

        # Juin 2021: Salary + Double Holiday Pay (2 payslips)
        cls.june_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip Jun 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 6, 1),
            'date_to': datetime.datetime(2021, 6, 30),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])

        cls.double_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip Double 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 6, 1),
            'date_to': datetime.datetime(2021, 6, 30),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])

        # Juillet 2021: Salary + Commissions
        cls.july_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip Jul 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 7, 1),
            'date_to': datetime.datetime(2021, 7, 31),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])
        for payslip in cls.july_2021:
            payslip._set_input_value('COMMISSION', 2000)

        # Aout 2021: Salary
        cls.august_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip Aug 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 8, 1),
            'date_to': datetime.datetime(2021, 8, 31),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])

        # Septembre 2021: Salary
        cls.september_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip Sep 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 9, 1),
            'date_to': datetime.datetime(2021, 9, 30),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])

        # Octobre 2021: Salary + Commissions
        cls.october_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip Oct 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 10, 1),
            'date_to': datetime.datetime(2021, 10, 31),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])
        for payslip in cls.october_2021:
            payslip._set_input_value('COMMISSION', 2000)

        # Novembre 2021: Salary
        cls.november_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip Nov 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 11, 1),
            'date_to': datetime.datetime(2021, 11, 30),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])

        # Décembre 2021: Salary + 13eme mois (2 payslips)
        cls.december_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip Dec 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 12, 1),
            'date_to': datetime.datetime(2021, 12, 31),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])
        for payslip in cls.december_2021:
            payslip._set_input_values({
                'SIMPLE_DECEMBER': 150,
                'DOUBLE_DECEMBER_BASIC': 100,
            })
            payslip.compute_sheet()

        cls.thirteen_2021 = cls.env['hr.payslip'].create([{
            'name': 'Payslip Thirteen Month 2021',
            'version_id': cls.contracts[i].id,
            'date_from': datetime.datetime(2021, 12, 1),
            'date_to': datetime.datetime(2021, 12, 31),
            'employee_id': cls.employees[i].id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
            'payslip_run_id': cls.batch.id,
        } for i in range(cls.EMPLOYEES_COUNT)])

        cls.company_executive_payslips = cls.env['hr.payslip'].create([{
            'name': f'Payslip CE {i}',
            'date_from': datetime.datetime(2025, i, 1),
            'date_to': datetime.datetime(2025, i, 1) + relativedelta(day=31),
            'employee_id': cls.company_executive_employee.id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': cls.env.company.id,
            'journal_id': cls.journal.id,
        } for i in range(1, 13)])

        all_payslips = cls.january_2021 + cls.february_2021 + cls.march_2021 + cls.april_2021 + \
                       cls.warrant_2021 + cls.may_2021 + cls.june_2021 + cls.double_2021 + \
                       cls.july_2021 + cls.august_2021 + cls.september_2021 + cls.october_2021 + \
                       cls.november_2021 + cls.december_2021 + cls.thirteen_2021 + cls.company_executive_payslips
        all_payslips.action_refresh_from_work_entries()
        # Clear review state before validation (simulates payroll officer approval)
        cls.employees.write({'review_state': '1_reviewed'})
        all_payslips.action_payslip_done()

        # Activate the benefit
        cls.env['hr.contract.salary.benefit'].with_context(active_test=False).search([('res_field_id.name', '=', 'l10n_be_lsa_monthly_misc_base_amount')]).active = True

        cls.exemption_rate = cls.env['hr.rule.parameter']._get_parameter_from_code('l10n_be_extra_hours_exemption_rate', raise_if_not_found=True)
        cls.extra_hours_employee = cls.env['hr.employee'].create({
            'name': 'Extra Normal',
            'company_id': cls.env.company.id,
            'contract_date_start': datetime.date(2026, 1, 1),
            'date_version': datetime.date(2026, 1, 1),
            'hourly_wage': 30,
            'wage_type': 'hourly',
            'lang': 'fr_BE',
        })
        cls.volo150_type = cls.env.ref('hr_work_entry.l10n_be_work_entry_type_voluntary_overtime_150')
        cls.volo200_type = cls.env.ref('hr_work_entry.l10n_be_work_entry_type_voluntary_overtime_200')
        cls.overtime_type = cls.env.ref('hr_work_entry.be_work_entry_type_overtime')
        cls.overtime_type.write({
            'requires_allocation': False,
            'is_extra_hours': True,
            'amount_rate': 1.5,
        })
        cls.be_attendance_type = cls.env.ref('hr_work_entry.be_work_entry_type_attendance')

    def validate_results(self, declaration, results):
        fields_to_validate = [
            'pp_amount_10',
            'pp_amount_13',
            'pp_amount_18',
            'pp_amount_20',
            'pp_amount_30',
            'pp_amount_32',
            'pp_amount_33',
            'pp_amount_34',
            'pp_amount_44',
            'pp_amount_55',
            'taxable_amount_10',
            'taxable_amount_13',
            'taxable_amount_18',
            'taxable_amount_20',
            'taxable_amount_30',
            'taxable_amount_32',
            'taxable_amount_33',
            'taxable_amount_34',
            'taxable_amount_44',
            'taxable_amount_55',
            'deducted_amount',
            'deducted_amount_32',
            'deducted_amount_33',
            'deducted_amount_34',
            'deducted_amount_44',
            'deducted_amount_55',
            'capped_amount_34',
        ]
        error = []
        for field_name in fields_to_validate:
            declaration_value = declaration[field_name]
            if field_name not in results:
                error.append("Missing Checked Line: '%s' - %s," % (field_name, declaration_value))
                continue
            value = results[field_name]
            if float_compare(declaration_value, value, 2):
                error.append("Code: %s - Expected: %s - Reality: %s" % (field_name, value, declaration_value))
        if error:
            error.append("Declaration Actual Values: ")
            error.append("{")
            for field_name in fields_to_validate:
                error.append("    '%s': %s," % (field_name, declaration[field_name]))
            error.append("}")
        self.assertEqual(len(error), 0, '\n' + '\n'.join(error))

    def test_274_declaration(self):
        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2021,
            'month': '1',
        })
        declaration_results = {
            'pp_amount_10': 5749.45,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 0.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 5749.45,
            'pp_amount_34': 0.0,
            'pp_amount_44': 0.0,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 18789.87,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 18789.87,
            'taxable_amount_34': 0.0,
            'taxable_amount_44': 0.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 4599.55,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 4599.55,
            'deducted_amount_34': 0.0,
            'deducted_amount_44': 0.0,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 0.0,
        }
        self.validate_results(declaration, declaration_results)

    def test_274_declaration_warrant(self):
        # Check warrants are included
        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2021,
            'month': '4',
        })
        declaration_results = {
            'pp_amount_10': 2412.88,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 0.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 1576.98,
            'pp_amount_34': 0.0,
            'pp_amount_44': 0.0,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 11872.12,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 10072.12,
            'taxable_amount_34': 0.0,
            'taxable_amount_44': 0.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 1261.58,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 1261.58,
            'deducted_amount_34': 0.0,
            'deducted_amount_44': 0.0,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 0.0,
        }
        self.validate_results(declaration, declaration_results)

    def test_274_declaration_cap(self):
        # Check bachelors are capped based on other employees
        self.employees[:3].write({'certificate': 'bachelor'})
        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2021,
            'month': '1',
        })
        declaration_results = {
            'pp_amount_10': 5749.45,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 0.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 2393.67,
            'pp_amount_34': 3355.78,
            'pp_amount_44': 0.0,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 18789.87,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 7711.54,
            'taxable_amount_34': 11078.33,
            'taxable_amount_44': 0.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 2393.66,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 1914.93,
            'deducted_amount_34': 2684.62,
            'deducted_amount_44': 0.0,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 478.73,
        }
        self.validate_results(declaration, declaration_results)

    def test_274_declaration_december(self):
        # Check december pay recuperation
        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2021,
            'month': '12',
        })
        declaration_results = {
            'pp_amount_10': 7639.22,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 0.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 7825.57,
            'pp_amount_34': 0.0,
            'pp_amount_44': 0.0,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 23575.92,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 23575.92,
            'taxable_amount_34': 0.0,
            'taxable_amount_44': 0.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 6260.46,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 6260.46,
            'deducted_amount_34': 0.0,
            'deducted_amount_44': 0.0,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 0.0,
        }

        self.validate_results(declaration, declaration_results)

    def test_274_rd_exemption_DHP(self):
        emp_rd = self.employees[0]
        emp_rd.contract_date_end = datetime.date(2021, 12, 31)
        self.env['hr.version'].create({
            'employee_id': emp_rd.id,
            'date_version': datetime.date(2022, 1, 1),
            'contract_date_start': datetime.date(2022, 1, 1),
            'contract_date_end': datetime.date(2022, 6, 30),
            'wage': 3500.0,
            'rd_percentage': 0.2,
        })
        self.env['hr.version'].create({
            'employee_id': emp_rd.id,
            'date_version': datetime.date(2022, 7, 1),
            'contract_date_start': datetime.date(2022, 7, 1),
            'contract_date_end': datetime.date(2022, 12, 31),
            'wage': 3500.0,
            'rd_percentage': 0.8,
        })
        self.env['hr.version'].create({
            'employee_id': emp_rd.id,
            'contract_date_start': datetime.date(2023, 1, 1),
            'wage': 3500.0,
            'rd_percentage': 1.0,
        })

        dhp_payslip = self.env['hr.payslip'].create({
            'name': 'R&D DHP Payslip Jun 2023',
            'version_id': emp_rd.version_id.id,
            'date_from': datetime.datetime(2023, 6, 1),
            'date_to': datetime.datetime(2023, 6, 30),
            'employee_id': emp_rd.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'company_id': self.env.company.id,
        })
        self.assertAlmostEqual(emp_rd._get_average_rd_percentage("BEDOUBLE", datetime.datetime(2023, 6, 1)), 0.502, 3)

        dhp_payslip.compute_sheet()
        dhp_payslip.action_payslip_done()

        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2023,
            'month': '6',
        })

        expected_declaration_results = {
            'pp_amount_10': 0.0,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 0.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 1200.13,
            'pp_amount_34': 0.0,
            'pp_amount_44': 0.0,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 2831.17,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 2831.17,
            'taxable_amount_34': 0.0,
            'taxable_amount_44': 0.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 482.42,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 482.42,
            'deducted_amount_34': 0.0,
            'deducted_amount_44': 0.0,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 0.0,
        }

        self.validate_results(declaration, expected_declaration_results)

    def test_274_rd_exemption_13_months(self):
        emp_rd = self.employees[0]
        emp_rd.contract_date_end = datetime.date(2021, 12, 31)

        self.env['hr.version'].create({
            'employee_id': emp_rd.id,
            'date_version': datetime.date(2022, 1, 1),
            'contract_date_start': datetime.date(2022, 1, 1),
            'contract_date_end': datetime.date(2022, 6, 30),
            'wage': 3500.0,
            'rd_percentage': 0.4,
        })
        self.env['hr.version'].create({
            'employee_id': emp_rd.id,
            'date_version': datetime.date(2022, 7, 1),
            'contract_date_start': datetime.date(2022, 7, 1),
            'contract_date_end': datetime.date(2022, 12, 31),
            'wage': 3500.0,
            'rd_percentage': 1.0,
        })

        thirteen_payslip = self.env['hr.payslip'].create({
            'name': 'R&D 13th Month Payslip Dec 2022',
            'version_id': emp_rd.version_id.id,
            'date_from': datetime.datetime(2022, 12, 1),
            'date_to': datetime.datetime(2022, 12, 31),
            'employee_id': emp_rd.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month').id,
            'company_id': self.env.company.id,
        })

        structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month')
        self.assertAlmostEqual(emp_rd._get_average_rd_percentage(structure.code, datetime.date(2022, 12, 1)), 0.702, 3)

        thirteen_payslip.compute_sheet()
        thirteen_payslip.action_payslip_done()

        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2022,
            'month': '12',
        })

        expected_declaration_results = {
            'pp_amount_10': 1412.96,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 0.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 1412.96,
            'pp_amount_34': 0.0,
            'pp_amount_44': 0.0,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 3042.55,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 3042.55,
            'taxable_amount_34': 0.0,
            'taxable_amount_44': 0.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 794.04,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 794.04,
            'deducted_amount_34': 0.0,
            'deducted_amount_44': 0.0,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 0.0,
        }

        self.validate_results(declaration, expected_declaration_results)

    def test_274_rd_exemption_term_holidays(self):
        emp_rd = self.env['hr.employee'].create({
            'name': "R&D Employee",
            'work_contact_id': self.work_contacts[1].id,
            'private_street': 'foo',
            'private_zip': '100',
            'private_country_id': self.env.ref('base.be').id,
            'resource_calendar_id': self.resource_calendar_38_hours_per_week.id,
            'company_id': self.env.company.id,
            'distance_home_work': 75,
            'certificate': 'master',
            'niss': '85073003328',
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'contract_date_start': datetime.date(2020, 1, 1),
            'date_version': datetime.date(2020, 1, 1),
            'wage': 5000,
            'rd_percentage': 0.7,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'lang': 'fr_BE',
        })

        self.env['hr.version'].create({
            'employee_id': emp_rd.id,
            'date_version': datetime.date(2020, 6, 1),
            'wage': 5000.0,
            'rd_percentage': 0.5,
        })

        self.env['hr.leave.allocation'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_legal_leave').id,
            'number_of_days': 20,
            'employee_id': emp_rd.id,
            'date_from': datetime.date(2021, 1, 1),
            'date_to': datetime.date(2021, 12, 31),
        }).action_approve()

        departure = self.env['hr.employee.departure'].create({
            'employee_id': emp_rd.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': datetime.datetime(2021, 9, 1),
            'l10n_be_notice_respect': 'without'
        })
        departure._generate_termination_holidays()

        struct_n_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays')
        struct_n1_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays')

        self.assertAlmostEqual(emp_rd._get_average_rd_percentage(struct_n_id.code, datetime.datetime(2021, 9, 1)), 0.5, 3)
        self.assertAlmostEqual(emp_rd._get_average_rd_percentage(struct_n1_id.code, datetime.datetime(2021, 9, 1)), 0.583, 3)

        departure_payslip_n = self.env['hr.payslip'].search([
            ('employee_id', '=', emp_rd.id),
            ('struct_id', '=', struct_n_id.id),
        ])
        departure_payslip_n1 = self.env['hr.payslip'].search([
            ('employee_id', '=', emp_rd.id),
            ('struct_id', '=', struct_n1_id.id),
        ])

        departure_payslip_n.compute_sheet()
        departure_payslip_n1.compute_sheet()
        departure_payslip_n.action_payslip_done()
        departure_payslip_n1.action_payslip_done()

        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2021,
            'month': '9',
        })

        expected_declaration_results = {
            'pp_amount_10': 2478.2,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 0.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 2478.2,
            'pp_amount_34': 0.0,
            'pp_amount_44': 0.0,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 11758.44,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 11758.44,
            'taxable_amount_34': 0.0,
            'taxable_amount_44': 0.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 1681.82,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 1681.82,
            'deducted_amount_34': 0.0,
            'deducted_amount_44': 0.0,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 0.0,
        }

        self.validate_results(declaration, expected_declaration_results)

    def test_274_rd_exemption_term_fees(self):
        emp_rd = self.employees[0]
        emp_rd.contract_date_end = datetime.date(2021, 12, 31)

        self.env['hr.version'].create({
            'employee_id': emp_rd.id,
            'date_version': datetime.date(2022, 1, 1),
            'contract_date_start': datetime.date(2022, 1, 1),
            'contract_date_end': datetime.date(2022, 3, 31),
            'wage': 3500.0,
            'rd_percentage': 0.2,
        })
        self.env['hr.version'].create({
            'employee_id': emp_rd.id,
            'date_version': datetime.date(2022, 4, 1),
            'contract_date_start': datetime.date(2022, 4, 1),
            'wage': 3500.0,
            'rd_percentage': 0.8,
        })
        departure = self.env['hr.employee.departure'].create({
            'employee_id': emp_rd.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': datetime.datetime(2022, 9, 1),
            'l10n_be_notice_respect': 'without'
        })
        departure._generate_termination_payslip()

        structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        term_payslip = self.env['hr.payslip'].search([
            ('employee_id', '=', emp_rd.id),
            ('struct_id', '=', structure.id),
        ])
        self.assertAlmostEqual(emp_rd._get_average_rd_percentage(structure.code, datetime.date(2022, 9, 1)), 0.719, 3)

        term_payslip.compute_sheet()
        term_payslip.action_payslip_done()

        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2022,
            'month': '9',
        })

        expected_declaration_results = {
            'pp_amount_10': 1326.78,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 0.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 1326.78,
            'pp_amount_34': 0.0,
            'pp_amount_44': 0.0,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 11089.4,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 11089.4,
            'taxable_amount_34': 0.0,
            'taxable_amount_44': 0.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 763.3,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 763.3,
            'deducted_amount_34': 0.0,
            'deducted_amount_44': 0.0,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 0.0,
        }

        self.validate_results(declaration, expected_declaration_results)

    def test_274_declaration_export(self):
        # Check exported data are the same than the computed fields
        def _to_eurocent(amount):
            return '%s' % int(amount * 100)

        self.employees[:3].write({'certificate': 'bachelor'})
        self.employees[3].write({'certificate': 'doctor'})

        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2021,
            'month': '1',
        })
        declaration_results = {
            'pp_amount_10': 5749.45,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 0.0,
            'pp_amount_32': 1178.78,
            'pp_amount_33': 1214.89,
            'pp_amount_34': 3355.78,
            'pp_amount_44': 0.0,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 18789.87,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 3823.17,
            'taxable_amount_33': 3888.37,
            'taxable_amount_34': 11078.33,
            'taxable_amount_44': 0.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 2393.66,
            'deducted_amount_32': 943.02,
            'deducted_amount_33': 971.91,
            'deducted_amount_34': 2684.62,
            'deducted_amount_44': 0.0,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 478.73,
        }
        self.validate_results(declaration, declaration_results)

        declaration_data = declaration._get_rendering_data()
        for data in declaration_data['declarations']:
            declaration_type = data['revenue_nature']
            suffix = '_%s' % (declaration_type)

            xml_taxable = data['taxable_revenue']
            if declaration_type == 56:
                field_taxable = declaration.sme_taxable_amount
            elif declaration_type in (60, 61):
                field_taxable = declaration.taxable_amount_10
            else:
                field_taxable = declaration['taxable_amount' + suffix]
            self.assertEqual(xml_taxable, _to_eurocent(field_taxable))

            xml_pp = data['prepayment']
            if declaration_type in [10, 13, 18, 20, 30]:
                field_pp = declaration['pp_amount' + suffix]
                self.assertEqual(xml_pp, _to_eurocent(field_pp))
            elif declaration_type == 34:
                field_pp = -declaration.capped_amount_34
                self.assertTrue(int(xml_pp) / 100.0 - field_pp <= 0.01)
            elif declaration_type == 56:
                field_pp = -declaration.sme_exempted_amount
                self.assertEqual(xml_pp, _to_eurocent(field_pp))
            elif declaration_type in (60, 61):
                field_pp = -declaration.startup_exempted_amount
                self.assertEqual(xml_pp, _to_eurocent(field_pp))
            else:
                field_pp = -declaration['deducted_amount' + suffix]
                self.assertEqual(xml_pp, _to_eurocent(field_pp))

    def test_declarations_equivalence(self):
        # Check that the sum of all the 274.10 sheets over the year = 281.10
        declarations_274 = self.env['l10n_be.274_xx'].create([{
            'year': 2021,
            'month': str(i),
        } for i in range(1, 13)])
        total_declared_pp = sum(declarations_274.mapped('pp_amount_10'))

        declaration_281_xx = self.env['l10n_be.281_xx'].create({
            'year': '2021',
        })
        declaration_281 = declaration_281_xx.l10n_be_281_10_ids
        data_281 = declaration_281._get_rendering_data(self.employees)
        declared_pp = data_281['sum_withholding']
        self.assertAlmostEqual(total_declared_pp, declared_pp, places=2)

    def test_281_10_comeback(self):
        # Check that we use the old first_version_date instead of
        # the new one
        self.assertEqual(self.employees[0]._get_first_version_date(), datetime.date(2018, 12, 31))
        self.contracts[0].write({
            'contract_date_end': datetime.date(2021, 12, 31),
        })
        self.contracts[0].copy({
            'name': "New Contract For Payslip Test 0",
            'date_version': datetime.date(2022, 3, 1),
            'contract_date_start': datetime.date(2022, 3, 1),
            'contract_date_end': False,
        })
        self.assertEqual(self.employees[0]._get_first_version_date(), datetime.date(2022, 3, 1))
        declaration_281_xx = self.env['l10n_be.281_xx'].create({
            'year': '2021',
        })
        declaration_281 = declaration_281_xx.l10n_be_281_10_ids
        data_281 = declaration_281._get_rendering_data(self.employees)
        for employee_data in data_281['employees_data']:
            if employee_data['f2011_nationaalnr'] == self.employees[0].niss:
                self.assertEqual(employee_data['f10_2055_datumvanindienstt'], '31-12-2018')

    def test_281_10_departure(self):
        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': self.employees[0].id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': datetime.date(2021, 12, 30),
            'l10n_be_notice_respect': 'without',
            'departure_description': 'foo',
            'action_date': datetime.date(2021, 12, 31),
        })
        departure_notice.action_register()
        departure_payslips = departure_notice._generate_termination_payslip()
        departure_payslips += departure_notice._generate_termination_holidays()

        # Termination Fees
        struct_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        termination_fees = departure_payslips.filtered(lambda dep: dep.struct_id == struct_id)
        termination_fees.compute_sheet()
        termination_fees.employee_id.write({'review_state': '1_reviewed'})
        termination_fees.action_payslip_done()

        # Holiday Attests
        holiday_pays = departure_payslips - termination_fees
        holiday_pays.employee_id.write({'review_state': '1_reviewed'})
        holiday_pays.action_payslip_done()

        # 281.10 Declaration
        declaration_281_xx = self.env['l10n_be.281_xx'].create({
            'year': '2021',
        })
        declaration_281 = declaration_281_xx.l10n_be_281_10_ids
        data_281 = declaration_281._get_rendering_data(self.employees)
        for employee_data in data_281['employees_data']:
            if employee_data['f2011_nationaalnr'] == self.employees[0].niss:
                self.assertEqual(
                    employee_data['f10_2063_vervroegdvakantieg'],
                    holiday_pays._get_line_values(['HOLIDAY_TERM_GROSS'], compute_sum=True)['HOLIDAY_TERM_GROSS']['sum']['total'])
                self.assertEqual(
                    employee_data['f10_2065_opzeggingsreclasseringsverg'],
                    termination_fees._get_line_values(['TERM_GROSS'], compute_sum=True)['TERM_GROSS']['sum']['total'])

    def test_notice_duration_fired(self):
        self.contracts[0].contract_date_start = datetime.date(2014, 1, 1)
        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': self.employees[0].id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': datetime.date(2044, 6, 1),
            'l10n_be_notice_respect': 'with',
            'departure_description': 'foo',
        })

        self.assertEqual(departure_notice.l10n_be_notice_period_start, datetime.date(2044, 6, 6))
        # Seniority is 30 years and 5 months
        # Duration should be 72 weeks
        self.assertEqual(departure_notice.departure_date, datetime.date(2045, 10, 22))

    def test_startup_exemption_calculation(self):
        self.company_data['company'].current_payroll_config_id.exemption_sme_status = 'startup'
        self.company_data['company'].write({
            'l10n_be_cbe_inscription': datetime.date(2020, 1, 1)
        })
        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2021,
            'month': '1',
        })

        expected_exemption = declaration.pp_amount_10 * 0.10
        self.assertAlmostEqual(declaration.startup_exempted_amount, expected_exemption, places=2)

        data = declaration._get_rendering_data()
        revenues = [d['revenue_nature'] for d in data['declarations']]
        self.assertIn(60, revenues, "Revenue nature 60 (Startup) must be present in XML data")

    def test_micro_enterprise_exemption_calculation(self):
        self.company_data['company'].current_payroll_config_id.exemption_sme_status = 'micro'
        self.company_data['company'].write({
            'l10n_be_cbe_inscription': datetime.date(2020, 1, 1)
        })
        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2021,
            'month': '1',
        })

        expected_exemption = declaration.pp_amount_10 * 0.20
        self.assertAlmostEqual(declaration.startup_exempted_amount, expected_exemption, places=2)

        data = declaration._get_rendering_data()
        revenues = [d['revenue_nature'] for d in data['declarations']]
        self.assertIn(61, revenues, "Revenue nature 61 (Micro-enterprise) must be present in XML data")

    def test_startup_exemption_expired(self):
        self.company_data['company'].current_payroll_config_id.exemption_sme_status = 'startup'
        self.company_data['company'].write({
            'l10n_be_cbe_inscription': datetime.date(2010, 1, 1)
        })
        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2021,
            'month': '1',
        })

        self.assertTrue(declaration.is_cbe_expired)
        self.assertEqual(declaration.startup_exempted_amount, 0.0, "Exempted amount must be 0 after 48 months")
        self.assertEqual(declaration.startup_amount_to_pay, 0.0)

        data = declaration._get_rendering_data()
        revenues = [d['revenue_nature'] for d in data['declarations']]
        self.assertNotIn(60, revenues)
        self.assertNotIn(61, revenues)

    def test_no_exemption_when_no_status_configured(self):
        self.company_data['company'].current_payroll_config_id.exemption_sme_status = False
        self.company_data['company'].write({
            'l10n_be_cbe_inscription': datetime.date(2020, 1, 1)
        })
        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2021,
            'month': '1',
        })

        self.assertFalse(declaration.is_cbe_expired, "Company should be active (under 48 months)")
        self.assertEqual(declaration.startup_exempted_amount, 0.0, "Exempted amount must be 0 if no status is set")
        self.assertEqual(declaration.startup_amount_to_pay, 0.0)

        data = declaration._get_rendering_data()
        revenues = [d['revenue_nature'] for d in data['declarations']]
        self.assertNotIn(60, revenues, "Nature 60 should not be present without startup status")
        self.assertNotIn(61, revenues, "Nature 61 should not be present without micro status")

    def test_company_executive_declaration(self):
        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2025,
            'month': '1',
        })
        declaration_results = {
            'pp_amount_10': 0.0,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 1209.49,
            'pp_amount_30': 0.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 0.0,
            'pp_amount_34': 0.0,
            'pp_amount_44': 0.0,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 0.0,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 5000.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 0.0,
            'taxable_amount_34': 0.0,
            'taxable_amount_44': 0.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 0.0,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 0.0,
            'deducted_amount_34': 0.0,
            'deducted_amount_44': 0.0,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 0.0,
        }
        self.validate_results(declaration, declaration_results)

    def test_13_declarations(self):
        unemployment_calendar = self.env['resource.calendar'].sudo().create([{
            'name': "Test Calendar : Economic Unemployment Partial",
            'company_id': self.env.company.id,
            'hours_per_day': 7.6,
            'hours_per_week': 38.0,
            'days_per_week': 5.0,
            'full_time_required_hours': 38.0,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_economic_unemployment').id
            }) for dayofweek, hour_from, hour_to in [
                ("0", 8.0, 12.0),
                ("0", 13.0, 16.6),
                ("1", 8.0, 12.0),
                ("1", 13.0, 16.6),
                ("2", 8.0, 12.0),
                ("2", 13.0, 16.6),
            ]] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_attendance').id
            }) for dayofweek, hour_from, hour_to in [
                ("3", 8.0, 12.0),
                ("3", 13.0, 16.6),
                ("4", 8.0, 12.0),
                ("4", 13.0, 16.6),
            ]],
        }])
        unemployment_employee = self.env['hr.employee'].create([{
            'name': "unemployment employee",
            'private_street': 'Employee Street',
            'private_zip': '100',
            'private_city': 'Employee City',
            'private_country_id': self.env.ref('base.be').id,
            'resource_calendar_id': unemployment_calendar.id,
            'company_id': self.env.company.id,
            'niss': '85073003328',
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'contract_date_start': datetime.date(2025, 12, 31),
            'date_version': datetime.date(2025, 12, 31),
            'wage': 5000,
            'lang': 'fr_BE',
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
        }])
        payslips = self.env['hr.payslip'].create([{
            'name': f'Payslip Unemployment {i}',
            'date_from': datetime.datetime(2026, i, 1),
            'date_to': datetime.datetime(2026, i, 1) + relativedelta(day=31),
            'employee_id': unemployment_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.env.company.id,
            # 'journal_id': self.journal.id,
        } for i in range(1, 13)])

        for p in payslips:
            p._set_input_value('EUC_CP200', 5)
        payslips.compute_sheet()
        payslips.action_payslip_done()

        unemployment_days = sum(p.worked_days_line_ids.filtered(lambda l: l.work_entry_type_id.l10n_be_economic_unemployment).number_of_days for p in payslips)
        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2026,
            'month': '1',
        })
        declaration_results = {
            'pp_amount_10': 169.6,
            'pp_amount_13': 16.05,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 0.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 0.0,
            'pp_amount_34': 0.0,
            'pp_amount_44': 0.0,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 2006.07,
            'taxable_amount_13': 60.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 0.0,
            'taxable_amount_34': 0.0,
            'taxable_amount_44': 0.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 0.0,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 0.0,
            'deducted_amount_34': 0.0,
            'deducted_amount_44': 0.0,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 0.0,
        }
        self.validate_results(declaration, declaration_results)

        declaration = self.env['l10n_be.281_xx'].create({
            'year': 2026,
        })
        declaration = declaration.l10n_be_281_13_ids
        data_281 = declaration._get_rendering_data(unemployment_employee)
        self.assertIn(unemployment_employee.niss, {emp_data['f2011_nationaalnr'] for emp_data in data_281['employees_data']})
        for employee_data in data_281['employees_data']:
            if employee_data['f2011_nationaalnr'] == unemployment_employee.niss:
                self.assertAlmostEqual(employee_data['f13_2060_bedrag'], 780)  # allocations
                self.assertAlmostEqual(employee_data['f13_2078_bedrijfsvoorheffing'], 208.68)  # tax
                self.assertAlmostEqual(employee_data['f13_2089_werkloosheidzonder'], unemployment_days)  # number of days

    def _run_extra_hours_payslip(self, name, rule_vals_list, attendance_periods, date_from, date_to):
        employee_domain = f"[('id', '=', {self.extra_hours_employee.id})]"
        rules = self.env['hr.time.rule'].sudo().create([
            dict(rule_vals, employee_domain=employee_domain)
            for rule_vals in rule_vals_list
        ])
        # attendance_periods is a list of (check_in, check_out) pairs in the employee's
        # local timezone.
        tz = ZoneInfo(self.extra_hours_employee.sudo()._get_tz())
        for check_in_local, check_out_local in attendance_periods:
            check_in = check_in_local.replace(tzinfo=tz).astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
            check_out = check_out_local.replace(tzinfo=tz).astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
            self.env['hr.attendance'].sudo().create({
                'employee_id': self.extra_hours_employee.id,
                'check_in': check_in,
                'check_out': check_out,
            })
        payslip = self.env['hr.payslip'].create([{
            'name': name,
            'version_id': self.extra_hours_employee.version_id.id,
            'date_from': date_from,
            'date_to': date_to,
            'employee_id': self.extra_hours_employee.id,
            'company_id': self.env.company.id,
        }])
        payslip.compute_sheet()
        payslip.action_payslip_done()
        return payslip, rules

    def test_extra_hours_44_CP_200(self):
        self.env.ref('l10n_be_hr_payroll.l10n_be_time_rule_sunday').sudo().write({'active': False})

        self.extra_hours_employee.l10n_be_joint_committee_id = self.env.ref(
            'l10n_be_hr_payroll.l10n_be_joint_committee_200')

        # First period: voluntary + overtime hours on working days only (Mon-Fri, no weekends).
        _, jan_rules = self._run_extra_hours_payslip(
            name="Payslip Jan 2026",
            rule_vals_list=[
                {
                    'name': 'Voluntary hours',
                    'working_hours_mode': 'day',
                    'work_entry_type_id': self.volo200_type.id,
                    'condition_work_entry_type_ids': [(4, self.be_attendance_type.id)],
                    'timing_start': 0,
                    'timing_stop': 12,
                    'apply_saturday': False,
                    'apply_sunday': False,
                },
                {
                    'name': 'Overtime hours',
                    'working_hours_mode': 'day',
                    'work_entry_type_id': self.overtime_type.id,
                    'condition_work_entry_type_ids': [(4, self.be_attendance_type.id)],
                    'timing_start': 12,
                    'timing_stop': 24,
                    'apply_saturday': False,
                    'apply_sunday': False,
                },
            ],
            # working days Jan 1(Thu),2(Fri),5-9(Mon-Fri): 7 days x 24h local each
            attendance_periods=[
                (datetime.datetime(2026, 1, 1, 0, 0), datetime.datetime(2026, 1, 2, 0, 0)),   # Jan 1 Thu
                (datetime.datetime(2026, 1, 2, 0, 0), datetime.datetime(2026, 1, 3, 0, 0)),   # Jan 2 Fri
                (datetime.datetime(2026, 1, 5, 0, 0), datetime.datetime(2026, 1, 6, 0, 0)),   # Jan 5 Mon
                (datetime.datetime(2026, 1, 6, 0, 0), datetime.datetime(2026, 1, 7, 0, 0)),   # Jan 6 Tue
                (datetime.datetime(2026, 1, 7, 0, 0), datetime.datetime(2026, 1, 8, 0, 0)),   # Jan 7 Wed
                (datetime.datetime(2026, 1, 8, 0, 0), datetime.datetime(2026, 1, 9, 0, 0)),   # Jan 8 Thu
                (datetime.datetime(2026, 1, 9, 0, 0), datetime.datetime(2026, 1, 10, 0, 0)),  # Jan 9 Fri
            ],
            date_from=datetime.datetime(2026, 1, 1),
            date_to=datetime.datetime(2026, 1, 31),
        )
        declaration = self.env['l10n_be.274_xx'].create({'year': 2026, 'month': '1'})
        # Rules fire Mon-Fri only. 7 working days, each full local day:
        # Jan 1,2,5,6,7,8,9:
        #   VOLOT200 (timing 0-12h): 12h per day -> 7x12 = 84h   amount = 84x30x2.0 = 5040€
        #   040.00 (timing 12-24h): 12h per day -> 7x12 = 84h   amount = 84x30x1.5 = 3780€
        #
        # calendar 002.00:
        #   Jan 12-30 Mon-Fri (15 days): 15x7.6 = 114h   amount = 114x30 = 3420€
        # BASIC  = categories['REMUNERATION_BASE'] = 002.00(3420) + 040.00(3780) = 7200€
        # VOLOT200 salary rule = 5040€
        # SALARY = 7200 + 5040 = 12240€
        # ONSS   = 12240 x 13.07% = 1599.77€
        # taxable_amount_10 = GROSS = 12240 - 1599.77 = 10640.23€
        # GROSS.Y = 10640.23 x 12 = 127682.76; after forfait (6070): 121612.76€
        # annual tax (Y.P.P) = 58071.34; marital deduction = 2987.98
        # PPTOTAL (before P.P.DEDEH) = (58071.34 - 2987.98) / 12 = 4590.28€
        # P.P.DEDEH (P.P.DEDEH withholding reduction for extra hours):
        #   VOLOT200 (84h, 200% rate -> premium rate 100% >= 50% -> tier2 57.75%):
        #     base = 84 x 30 = 2520€; deduction = 2520 x 0.5775 = 1455.30€
        #   040.00 (84h, 150% rate -> premium rate 50% >= 50% -> tier2 57.75%):
        #     base = 84 x 30 = 2520€; deduction = 2520 x 0.5775 = 1455.30€
        #   total P.P.DEDEH = 2910.60€
        # pp_amount_10 = PPTOTAL = 4590.28 - 2910.60 = 1679.68€
        #
        # taxable_amount_44 (274_44 overtime exemption):
        #   VOLOT200: 84h x 30€ = 2520€; 040.00: 84h x 30€ = 2520€
        #   total = 5040€  (168h < 180h annual cap)
        # deducted_amount_44 = 5040 x 41.25% = 2079.0€
        declaration_results = {
            'pp_amount_10': 1679.68,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 0.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 0.0,
            'pp_amount_34': 0.0,
            'pp_amount_44': 1679.68,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 10640.23,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 0.0,
            'taxable_amount_34': 0.0,
            'taxable_amount_44': 5040.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 2079.0,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 0.0,
            'deducted_amount_34': 0.0,
            'deducted_amount_44': 2079.0,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 0.0,
        }

        self.validate_results(declaration, declaration_results)

        # Jan used 84h VOLOT200 + 84h 040.00 = 168h -> 12h remain under the 180h annual cap
        jan_rules.unlink()
        self._run_extra_hours_payslip(
            name="Payslip Feb 2026",
            rule_vals_list=[
                {
                    'name': 'Free Rule',
                    'working_hours_mode': 'day',
                    'work_entry_type_id': self.volo150_type.id,
                    'condition_work_entry_type_ids': [(4, self.be_attendance_type.id)],
                    'timing_start': 0,
                    'timing_stop': 12,
                    'apply_saturday': False,
                    'apply_sunday': False,
                },
                {
                    'name': 'Paid Rule',
                    'working_hours_mode': 'day',
                    'work_entry_type_id': self.overtime_type.id,
                    'condition_work_entry_type_ids': [(4, self.be_attendance_type.id)],
                    'timing_start': 12,
                    'timing_stop': 24,
                    'apply_saturday': False,
                    'apply_sunday': False,
                },
            ],
            # working days Feb 2-6, 9-13, 16-20 (Mon-Fri): 15 days x 24h local each
            attendance_periods=[
                (datetime.datetime(2026, 2, 2, 0, 0), datetime.datetime(2026, 2, 3, 0, 0)),   # Feb 2 Mon
                (datetime.datetime(2026, 2, 3, 0, 0), datetime.datetime(2026, 2, 4, 0, 0)),   # Feb 3 Tue
                (datetime.datetime(2026, 2, 4, 0, 0), datetime.datetime(2026, 2, 5, 0, 0)),   # Feb 4 Wed
                (datetime.datetime(2026, 2, 5, 0, 0), datetime.datetime(2026, 2, 6, 0, 0)),   # Feb 5 Thu
                (datetime.datetime(2026, 2, 6, 0, 0), datetime.datetime(2026, 2, 7, 0, 0)),   # Feb 6 Fri
                (datetime.datetime(2026, 2, 9, 0, 0), datetime.datetime(2026, 2, 10, 0, 0)),  # Feb 9 Mon
                (datetime.datetime(2026, 2, 10, 0, 0), datetime.datetime(2026, 2, 11, 0, 0)),  # Feb 10 Tue
                (datetime.datetime(2026, 2, 11, 0, 0), datetime.datetime(2026, 2, 12, 0, 0)),  # Feb 11 Wed
                (datetime.datetime(2026, 2, 12, 0, 0), datetime.datetime(2026, 2, 13, 0, 0)),  # Feb 12 Thu
                (datetime.datetime(2026, 2, 13, 0, 0), datetime.datetime(2026, 2, 14, 0, 0)),  # Feb 13 Fri
                (datetime.datetime(2026, 2, 16, 0, 0), datetime.datetime(2026, 2, 17, 0, 0)),  # Feb 16 Mon
                (datetime.datetime(2026, 2, 17, 0, 0), datetime.datetime(2026, 2, 18, 0, 0)),  # Feb 17 Tue
                (datetime.datetime(2026, 2, 18, 0, 0), datetime.datetime(2026, 2, 19, 0, 0)),  # Feb 18 Wed
                (datetime.datetime(2026, 2, 19, 0, 0), datetime.datetime(2026, 2, 20, 0, 0)),  # Feb 19 Thu
                (datetime.datetime(2026, 2, 20, 0, 0), datetime.datetime(2026, 2, 21, 0, 0)),  # Feb 20 Fri
            ],
            date_from=datetime.datetime(2026, 2, 1),
            date_to=datetime.datetime(2026, 2, 28),
        )
        declaration = self.env['l10n_be.274_xx'].create({'year': 2026, 'month': '2'})
        # Each attendance spans 00:00-24:00 CET local. Rules fire Mon-Fri only.
        # 15 working days Feb 2-20, each full local day:
        #   VOLOT150 (timing 0-12h): 12h per day -> 15x12 = 180h   amount = 180x30x1.5 = 8100€
        #   040.00 (timing 12-24h): 12h per day -> 15x12 = 180h   amount = 180x30x1.5 = 8100€
        #
        # 002.00 (no weekend attendance -> 0h; calendar for unattended Mon-Fri):
        #   Feb 23-27 Mon-Fri (5 days): 5x7.6 = 38h   amount = 38x30 = 1140€
        #
        # BASIC  = 002.00(1140) + 040.00(8100) = 9240€
        # VOLOT150 salary rule = 8100€
        # SALARY = 9240 + 8100 = 17340€
        # ONSS   = 17340 x 13.07% = 2266.34€
        # taxable_amount_10 = GROSS = 17340 - 2266.34 = 15073.66€
        # GROSS.Y = 15073.66 x 12 = 180883.92; after forfait (6070): 174813.92€
        # annual tax (Y.P.P) = 86526.00; marital deduction = 2987.98
        # PPTOTAL (before P.P.DEDEH) = (86526.00 - 2987.98) / 12 = 6962.17€
        # P.P.DEDEH (annual cap=360h; Jan consumed 168h -> 192h remaining):
        #   VOLOT150 (180h, tier2 57.75%): base = 180 x 30 = 5400€; deduction = 3118.50€
        #   040.00 (min(180, 12 remaining cap) = 12h, tier2): base = 12 x 30 = 360€; deduction = 207.90€
        #   total P.P.DEDEH = 3326.40€
        # pp_amount_10 = PPTOTAL = 6962.17 - 3326.40 = 3635.77€
        #
        # taxable_amount_44: annual cap = 180h; Jan used 84+84=168h -> 12h remain
        #   Feb exempt hours capped at 12h -> 12x30 = 360€
        # deducted_amount_44 = 360 x 41.25% = 148.5€
        declaration_results = {
            'pp_amount_10': 3635.77,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 0.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 0.0,
            'pp_amount_34': 0.0,
            'pp_amount_44': 3635.77,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 15073.66,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 0.0,
            'taxable_amount_34': 0.0,
            'taxable_amount_44': 360.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 148.5,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 0.0,
            'deducted_amount_34': 0.0,
            'deducted_amount_44': 148.5,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 0.0,
        }

        self.validate_results(declaration, declaration_results)

    def test_extra_hours_55_CP_302(self):
        self.env.ref('l10n_be_hr_payroll.l10n_be_time_rule_sunday').sudo().write({'active': False})
        self.env.ref('l10n_be_hr_payroll.l10n_be_time_rule_night_cp302').sudo().write({'active': False})

        self.extra_hours_employee.l10n_be_joint_committee_id = self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302')
        self._run_extra_hours_payslip(
            name="Payslip Jan 2026",
            rule_vals_list=[
                {
                    'name': 'Overtime hours',
                    'working_hours_mode': 'day',
                    'work_entry_type_id': self.overtime_type.id,
                    'condition_work_entry_type_ids': [(4, self.be_attendance_type.id)],
                    'timing_start': 0,
                    'timing_stop': 12,
                    'apply_saturday': False,
                    'apply_sunday': False,
                },
            ],
            # working days Jan 1(Thu),2(Fri),5-9,12-16,19(Mon): 13 days x 24h local each
            attendance_periods=[
                (datetime.datetime(2026, 1, 1, 0, 0), datetime.datetime(2026, 1, 2, 0, 0)),   # Jan 1 Thu
                (datetime.datetime(2026, 1, 2, 0, 0), datetime.datetime(2026, 1, 3, 0, 0)),   # Jan 2 Fri
                (datetime.datetime(2026, 1, 5, 0, 0), datetime.datetime(2026, 1, 6, 0, 0)),   # Jan 5 Mon
                (datetime.datetime(2026, 1, 6, 0, 0), datetime.datetime(2026, 1, 7, 0, 0)),   # Jan 6 Tue
                (datetime.datetime(2026, 1, 7, 0, 0), datetime.datetime(2026, 1, 8, 0, 0)),   # Jan 7 Wed
                (datetime.datetime(2026, 1, 8, 0, 0), datetime.datetime(2026, 1, 9, 0, 0)),   # Jan 8 Thu
                (datetime.datetime(2026, 1, 9, 0, 0), datetime.datetime(2026, 1, 10, 0, 0)),  # Jan 9 Fri
                (datetime.datetime(2026, 1, 12, 0, 0), datetime.datetime(2026, 1, 13, 0, 0)),  # Jan 12 Mon
                (datetime.datetime(2026, 1, 13, 0, 0), datetime.datetime(2026, 1, 14, 0, 0)),  # Jan 13 Tue
                (datetime.datetime(2026, 1, 14, 0, 0), datetime.datetime(2026, 1, 15, 0, 0)),  # Jan 14 Wed
                (datetime.datetime(2026, 1, 15, 0, 0), datetime.datetime(2026, 1, 16, 0, 0)),  # Jan 15 Thu
                (datetime.datetime(2026, 1, 16, 0, 0), datetime.datetime(2026, 1, 17, 0, 0)),  # Jan 16 Fri
                (datetime.datetime(2026, 1, 19, 0, 0), datetime.datetime(2026, 1, 20, 0, 0)),  # Jan 19 Mon
            ],
            date_from=datetime.datetime(2026, 1, 1),
            date_to=datetime.datetime(2026, 1, 31),
        )

        # Each attendance spans 00:00-24:00 CET local. Rule fires Mon-Fri (0-12h only).
        # 13 working days Jan 1,2,5-9,12-16,19, each full local day:
        #   040.00 (timing 0-12h): 12h per day -> 13x12 = 156h   amount = 156x30x1.5 = 7020€
        #   (afternoon 12-24h unmatched -> stays as 002.00 from attendance)
        #
        # 002.00:
        #   attended PM (12-24h, 13 working days): 13x12 = 156h
        #   calendar Mon-Fri with no attendance: Jan 21-30 Mon-Fri (8 days, not 9):
        #     Jan 19 attendance check_out = Jan 19 23:00 UTC = Jan 20 00:00 CET touches Jan 20,
        #     so the payslip treats Jan 20 as "covered" -> only Jan 21-30 Mon-Fri contribute.
        #     Jan 21(Wed), 22, 23(Fri), 26(Mon), 27, 28, 29, 30(Fri) = 8x7.6 = 60.8h
        #   002.00 = 156 + 60.8 = 216.8h   amount = 216.8x30 = 6504€
        #   (no weekend attendance -> 0h from weekends)
        #
        # BASIC  = SALARY = 002.00(6504) + 040.00(7020) = 13524€
        # ONSS   = 13524 x 13.07% = 1767.59€
        # taxable_amount_10 = GROSS = 13524 - 1767.59 = 11756.41€
        # GROSS.Y = 11756.41 x 12 = 141076.92; after forfait (6070): 135006.92€
        # annual tax (Y.P.P) = 65237.32; marital deduction = 2987.98
        # PPTOTAL (before P.P.DEDEH) = (65237.32 - 2987.98) / 12 = 5187.44€
        # P.P.DEDEH (040.00 156h, tier2 57.75%, cap=360h no prior validated payslips):
        #   base = 156 x 30 = 4680€; deduction = 4680 x 0.5775 = 2702.70€
        # pp_amount_10 = PPTOTAL = 5187.44 - 2702.70 = 2484.74€
        #
        # taxable_amount_55 (274_55 overtime exemption):
        #   040.00 = 156h; cap = 60h (no white cash register) or 90h (with)
        #   no cash register:  60h x 30€ = 1800€; deducted = 1800 x 41.25% = 742.5€
        #   with cash register: 90h x 30€ = 2700€; deducted = 2700 x 41.25% = 1113.75€
        base_results = {
            'pp_amount_10': 2484.74,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 0.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 0.0,
            'pp_amount_34': 0.0,
            'pp_amount_44': 0.0,
            'pp_amount_55': 2484.74,
            'taxable_amount_10': 11756.41,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 0.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 0.0,
            'taxable_amount_34': 0.0,
            'taxable_amount_44': 0.0,
            'taxable_amount_55': 1800.0,
            'deducted_amount': 742.5,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 0.0,
            'deducted_amount_34': 0.0,
            'deducted_amount_44': 0.0,
            'deducted_amount_55': 742.5,
            'capped_amount_34': 0.0,
        }

        # Test the 60h/year exemption limit for companies without a white cash register
        self.env.company.l10n_be_has_white_cash_register = False
        declaration = self.env['l10n_be.274_xx'].create({'year': 2026, 'month': '1'})
        self.validate_results(declaration, {
            **base_results,
            'taxable_amount_55': 1800.0,
            'deducted_amount': 742.5,
            'deducted_amount_55': 742.5,
        })

        # Test the 90h/year exemption limit for companies with a white cash register
        self.env.company.l10n_be_has_white_cash_register = True
        declaration = self.env['l10n_be.274_xx'].create({'year': 2026, 'month': '1'})
        self.validate_results(declaration, {
            **base_results,
            'taxable_amount_55': 2700.0,
            'deducted_amount': 1113.75,
            'deducted_amount_55': 1113.75,
        })

    def test_30_declarations(self):
        employee_tokens = self.employees[0]
        employee_tokens.write({'l10n_be_include_employee_in_281_30': True})
        payslips = self.env['hr.payslip'].create([{
            'name': f'Payslip Tokens {i}',
            'date_from': datetime.datetime(2026, i, 1),
            'date_to': datetime.datetime(2026, i, 1) + relativedelta(day=31),
            'employee_id': employee_tokens.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.env.company.id,
        } for i in range(1, 13)])

        for p in payslips:
            p._set_input_value('PRESENCE_TOKEN', 2000)
        payslips.compute_sheet()
        payslips.action_payslip_done()

        declaration = self.env['l10n_be.274_xx'].create({
            'year': 2026,
            'month': '1',
        })
        declaration_results = {
            'pp_amount_10': 0.0,
            'pp_amount_13': 0.0,
            'pp_amount_18': 0.0,
            'pp_amount_20': 0.0,
            'pp_amount_30': 747.0,
            'pp_amount_32': 0.0,
            'pp_amount_33': 113.74,
            'pp_amount_34': 0.0,
            'pp_amount_44': 0.0,
            'pp_amount_55': 0.0,
            'taxable_amount_10': 0.0,
            'taxable_amount_13': 0.0,
            'taxable_amount_18': 0.0,
            'taxable_amount_20': 0.0,
            'taxable_amount_30': 2000.0,
            'taxable_amount_32': 0.0,
            'taxable_amount_33': 2070.2,
            'taxable_amount_34': 0.0,
            'taxable_amount_44': 0.0,
            'taxable_amount_55': 0.0,
            'deducted_amount': 90.99,
            'deducted_amount_32': 0.0,
            'deducted_amount_33': 90.99,
            'deducted_amount_34': 0.0,
            'deducted_amount_44': 0.0,
            'deducted_amount_55': 0.0,
            'capped_amount_34': 0.0,
        }
        self.validate_results(declaration, declaration_results)

        declaration = self.env['l10n_be.281_xx'].create({
            'year': 2026,
        })
        declaration = declaration.l10n_be_281_30_ids
        data_281 = declaration._get_rendering_data(self.employees[0])
        self.assertIn(self.employees[0].niss, {emp_data['f2011_nationaalnr'] for emp_data in data_281['employees_data']})
        for employee_data in data_281['employees_data']:
            if employee_data['f2011_nationaalnr'] == self.employees[0].niss:
                self.assertAlmostEqual(employee_data['f30_2063_bedrijfsvoorheffing'], 11154.67, places=2)
                self.assertAlmostEqual(employee_data['f30_2064_presentiegelden'], 24000.0, places=2)
                self.assertAlmostEqual(employee_data['f30_2086_bedrag'], 2046.03, places=2)
