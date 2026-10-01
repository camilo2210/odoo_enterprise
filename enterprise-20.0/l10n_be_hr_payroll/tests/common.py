# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from datetime import date
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
from random import randint, randrange
import uuid

from odoo import SUPERUSER_ID
from odoo.fields import Command
from odoo.tests.common import TransactionCase
from odoo.tools import file_open


class TestBelgiumCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('fr_BE')
        cls.env.user.lang = 'fr_BE'
        cls.env.company.payroll_config_ids[-1].write({
            'onss_importance_code': '1',
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010').id,
            'l10n_be_main_joint_committee': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
        })
        cls.load_onss_rates()
        cls.env['res.lang']._activate_lang('fr_BE')
        cls.env.user.lang = 'fr_BE'
        # Activate the JC200 & JC302 & JC999
        jcs_to_activate = cls.env['l10n.be.joint.committee'].with_context(active_test=False).search([('egov3_code', 'in', ('200', '302', '999'))])
        jcs_to_activate.write({'active': True})

    @classmethod
    def load_onss_rates(cls):
        def load(folder, codes):
            cls.env['hr.rule.parameter'].with_user(SUPERUSER_ID).search([
                ('code', 'in', [f'l10n_be_{folder}_{code}' for code in codes])
            ]).unlink()
            for code in codes:
                rule_parameter = cls.env['hr.rule.parameter'].with_user(SUPERUSER_ID).create({
                    'name': f'ONSS Rates: {code}',
                    'code': f'l10n_be_{folder}_{code}',
                    'country_id': cls.env.ref('base.be').id,
                })
                cls.env['hr.rule.parameter.value'].with_user(SUPERUSER_ID).create({
                    'parameter_value': json.load(file_open(f'l10n_be_hr_payroll/tests/data/{folder}/{code}.json')),
                    'rule_parameter_id': rule_parameter.id,
                    'date_from': date(2000, 1, 1),
                })

        load('onss_rates', [
            '010_015_1', '010_027_1', '010_253_0', '010_255_0', '010_256_0', '010_260_0', '010_260_3', '010_260_4',
            '010_260_5', '010_260_6', '010_260_7', '010_261_0', '010_439_0', '010_450_0', '010_484_0', '010_495_0',
            '010_809_0', '010_809_2', '010_809_4', '010_809_5', '010_810_0', '010_811_0', '010_811_2', '010_812_1',
            '010_812_2', '010_812_3', '010_831_0', '010_840_0', '010_841_0', '010_847_0', '010_852_0', '010_855_0',
            '010_856_0', '010_857_0', '010_859_0', '010_863_0', '010_865_0', '010_868_0', '010_869_0', '010_878_0',
            '010_888_0', '010_889_0', '017_015_1', '017_253_0', '017_255_0', '017_256_0', '017_450_0', '017_484_0',
            '017_800_0', '017_800_2', '017_809_4', '017_809_5', '017_810_0', '017_820_0', '017_820_5', '017_825_0',
            '017_825_8', '017_830_0', '017_830_5', '017_835_0', '017_835_1', '017_840_0', '017_841_0', '017_855_0',
            '017_859_0', '048_015_1', '048_253_0', '048_255_0', '048_256_0', '048_450_0', '048_484_0', '048_809_0',
            '048_809_4', '048_809_5', '048_810_0', '048_825_1', '048_825_2', '048_835_0', '048_835_1', '048_835_8',
            '048_840_0', '048_841_0', '048_855_0', '048_859_0', '010_046_1',
        ])
        load('onss_combinations', [
            '010_015', '010_027', '010_046', '010_439', '010_484', '010_495', '017_015', '017_484', '048_015', '048_484',
        ])


class TestPayrollCommon(TestBelgiumCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with freeze_time('2023-01-01'):
            today = date.today()

            cls.belgian_company = cls.create_belgian_company()
            cls.multibranch_company = cls.create_multibranch_company(depth=3)

            cls.belgian_company.resource_calendar_id = cls.env['resource.calendar'].create({
                'attendance_ids': [
                    (0, 0,
                     {
                         'dayofweek': weekday,
                         'hour_from': hour_from,
                         'hour_to': hour_to,
                     })
                    for weekday in ['0', '1', '2', '3', '4']
                    for hour_from, hour_to in [(8, 12), (13, 16.6)]
                ],
                'name': 'Standard 38h/week',
                'full_time_required_hours': 38
            })

            cls.env.user.company_ids |= cls.belgian_company
            cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.belgian_company.ids))

            cls.holiday_work_entry_types = cls.env['hr.work.entry.type'].create({
                'name': 'Paid Time Off',
                'code': 'Paid Time Off TEST',
                'requires_allocation': True,
                'employee_requests': False,
                'allocation_validation_type': 'hr',
                'leave_validation_type': 'both',
                'request_unit': 'day',
                'unit_of_measure': 'day',
            })

            cls.resource_calendar = cls.env['resource.calendar'].create({
                'name': 'Test Calendar',
                'company_id': cls.belgian_company.id,
                'hours_per_day': 7.6,
                'hours_per_week': 38,
                'full_time_required_hours': 38,
            })

            cls.resource_calendar_40 = cls.env['resource.calendar'].create({
                'name': 'Standard 40h/week',
                'company_id': cls.belgian_company.id,
                'full_time_required_hours': 40,
                'attendance_ids': [
                    Command.create({'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                    Command.create({'dayofweek': '0', 'hour_from': 13, 'hour_to': 17}),
                    Command.create({'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                    Command.create({'dayofweek': '1', 'hour_from': 13, 'hour_to': 17}),
                    Command.create({'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                    Command.create({'dayofweek': '2', 'hour_from': 13, 'hour_to': 17}),
                    Command.create({'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                    Command.create({'dayofweek': '3', 'hour_from': 13, 'hour_to': 17}),
                    Command.create({'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                    Command.create({'dayofweek': '4', 'hour_from': 13, 'hour_to': 17}),
                ],
            })

            cls.resource_calendar_mid_time = cls.resource_calendar.copy({
                'name': 'Calendar (Mid-Time)',
                'full_time_required_hours': 38,
                'attendance_ids': [
                    (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.5}),
                    (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.5}),
                    (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12})
                ]
            })

            cls.resource_calendar_4_5 = cls.resource_calendar.copy({
                'name': 'Calendar (4 / 5)',
                'full_time_required_hours': 38,
                'attendance_ids': [
                    (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6}),
                    (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6}),
                    (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16.6}),
                    (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.6})
                ]
            })

            cls.resource_calendar_9_10 = cls.resource_calendar.copy({
                'name': 'Calendar (9 / 10)',
                'full_time_required_hours': 38,
                'attendance_ids': [
                    (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6}),
                    (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6}),
                    (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16.5}),
                    (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.5}),
                    (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                ]
            })

            cls.resource_calendar_30_hours_per_week = cls.resource_calendar.copy({
                'name': 'Calendar 30 Hours/Week',
                'full_time_required_hours': 38,
                'attendance_ids': [
                    (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.5}),
                    (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.5}),
                    (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16.5}),
                    (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.5})
                ]
            })

            cls.belgian_company.resource_calendar_id = cls.env['resource.calendar'].create({
                'attendance_ids': [
                    (0, 0,
                        {
                            'dayofweek': weekday,
                            'hour_from': hour_from,
                            'hour_to': hour_to,
                        })
                    for weekday in ['0', '1', '2', '3', '4']
                    for hour_from, hour_to in [(8, 12), (13, 16.6)]
                ],
                'name': 'Standard 40h/week',
                'reference_calendar_id': cls.resource_calendar.id,
            })

            cls.worker_code_id = cls.env['l10n.be.worker.code'].search([('dmfa_code', '=', '495')])
            cls.employee_georges = cls.create_employee({
                'name': 'Georges',
                'date_version': date(today.year - 2, 1, 1),
                'contract_date_start': date(today.year - 2, 1, 1),
                'contract_date_end': date(today.year - 2, 12, 31),
                'l10n_be_worker_code_id': cls.worker_code_id.id,
                'l10n_be_dimona_category': 'oth',
            })

            cls.georges_contracts = cls.employee_georges.version_id
            cls.georges_contracts |= cls.employee_georges.create_version({
                'date_version': date(today.year - 1, 1, 1),
                'contract_date_start': date(today.year - 1, 1, 1),
                'contract_date_end': date(today.year - 1, 5, 31),
                'resource_calendar_id': cls.resource_calendar_mid_time.id,
                'wage': 1250,
            })

            cls.georges_contracts |= cls.employee_georges.create_version({
                'date_version': date(today.year - 1, 6, 1),
                'contract_date_start': date(today.year - 1, 6, 1),
                'contract_date_end': date(today.year - 1, 8, 31),
                'resource_calendar_id': cls.resource_calendar.id,
            })

            cls.georges_contracts |= cls.employee_georges.create_version({
                'date_version': date(today.year - 1, 9, 1),
                'contract_date_start': date(today.year - 1, 9, 1),
                'contract_date_end': date(today.year - 1, 12, 31),
                'resource_calendar_id': cls.resource_calendar_4_5.id,
                'wage': 2500 * 4 / 5,
            })

            cls.georges_contracts |= cls.employee_georges.create_version({
                'date_version': date(today.year, 1, 1),
                'contract_date_start': date(today.year, 1, 1),
                'contract_date_end': False,
                'resource_calendar_id': cls.resource_calendar_4_5.id,
                'wage': 2500 * 4 / 5,
            })

            cls.employee_john = cls.create_employee_with_benefits({
                'name': 'John Doe',
                'date_version': date(today.year - 2, 1, 1),
                'contract_date_start': date(today.year - 2, 1, 1),
                'contract_date_end': date(today.year - 2, 12, 31),
                'l10n_be_worker_code_id': cls.worker_code_id.id,
                'l10n_be_dimona_category': 'oth',
            })

            cls.john_contracts = cls.employee_john.version_id
            cls.john_contracts |= cls.employee_john.create_version({
                'date_version': date(today.year - 1, 1, 1),
                'contract_date_start': date(today.year - 1, 1, 1),
                'contract_date_end': date(today.year - 1, 3, 31)
            })

            cls.john_contracts |= cls.employee_john.create_version({
                'date_version': date(today.year - 1, 4, 1),
                'contract_date_start': date(today.year - 1, 4, 1),
                'contract_date_end': date(today.year - 1, 6, 30),
                'resource_calendar_id': cls.resource_calendar_9_10.id,
            })

            cls.john_contracts |= cls.employee_john.create_version({
                'date_version': date(today.year - 1, 7, 1),
                'contract_date_start': date(today.year - 1, 7, 1),
                'contract_date_end': date(today.year - 1, 9, 30),
                'resource_calendar_id': cls.resource_calendar_4_5.id,
            })

            cls.john_contracts |= cls.employee_john.create_version({
                'date_version': date(today.year - 1, 10, 1),
                'contract_date_start': date(today.year - 1, 10, 1),
                'contract_date_end': False,
                'resource_calendar_id': cls.resource_calendar_mid_time.id,
            })

            cls.employee_a = cls.create_employee({
                'name': 'A',
                'date_version': date(today.year - 1, 1, 1),
                'contract_date_start': date(today.year - 1, 1, 1),
                'contract_date_end': False,
                'l10n_be_worker_code_id': cls.worker_code_id.id,
                'l10n_be_dimona_category': 'oth',
            })

            cls.a_contracts = cls.employee_a.version_id
            cls.employee_test = cls.create_employee({
                'name': 'Employee Test',
                'date_version': date(2017, 1, 1),
                'contract_date_start': date(2017, 1, 1),
                'contract_date_end': False,
                'l10n_be_scale_seniority': 8,
                'l10n_be_worker_code_id': cls.worker_code_id.id,
                'l10n_be_dimona_category': 'oth',
            })

            cls.test_contracts = cls.employee_test.version_id

            cls.employee_with_attestation = cls.create_employee({
                'name': 'Employee With Attestation',
                'date_version': date(today.year - 1, 10, 1),
                'contract_date_start': date(today.year - 1, 10, 1),
                'contract_date_end': date(today.year - 1, 12, 31),
                'l10n_be_worker_code_id': cls.worker_code_id.id,
                'l10n_be_dimona_category': 'oth',
            })

            cls.employee_with_attestation.l10n_be_holiday_attest_ids = [
                Command.create({
                    "date_from": date(today.year - 1, 1, 1),
                    "date_to": date(today.year - 1, 3, 31),
                    "prev_work_hours_per_week": 19,
                    "prev_reference_work_hours_per_week": 38,
                    "prev_work_days_per_week": 5,
                    "prev_simple_holiday_pay_paid": 0,
                    "prev_double_holiday_pay_paid": 1000,
                }),
            ]

            cls.employee_with_attestation_contracts = cls.employee_with_attestation.version_id

            cls.employee_withholding_taxes = cls.env["hr.employee"].create({
                    'name': 'EmployeeWithholdingTaxes',
                    'resource_calendar_id': cls.resource_calendar.id,
                    'company_id': cls.belgian_company.id,
                    'internet': False,
                    'mobile': False,
                    'meal_voucher_amount': 0,
                    'wage': 2500,
                    'date_version': date(today.year - 2, 1, 1),
                    'contract_date_start': date(today.year - 2, 1, 1),
                    'contract_date_end': False,
                    'marital': 'single',
                    'sex': 'male',
                })

            cls.employee_withholding_taxes_contracts = cls.employee_withholding_taxes.version_id
            cls.employee_withholding_taxes_contracts['wage'] = 2500
            cls.employee_withholding_taxes_payslip = cls.env['hr.payslip'].create({
                'name': "EmployeeWithholdingTaxes' Payslip",
                'employee_id': cls.employee_withholding_taxes.id,
                'version_id': cls.employee_withholding_taxes_contracts.id,
            })

            # Activate the JC200 & JC302 & JC999
            jcs_to_activate = cls.env['l10n.be.joint.committee'].with_context(active_test=False).search([('egov3_code', 'in', ('200', '302', '999'))])
            jcs_to_activate.write({'active': True})

    @classmethod
    def create_employee(cls, values=None):
        """
        Creates one or multiple employees
        :return: recordset ['res.employee']
        """

        default_values = {
            'private_country_id': cls.env.ref('base.be').id,
            'resource_calendar_id': cls.resource_calendar.id,
            'company_id': cls.belgian_company.id,

            # Payroll context
            'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
            'l10n_be_joint_committee_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'l10n_be_salary_scale_id': cls.env.ref('l10n_be_hr_payroll.cp200_b').id,
            'date_version': date.today(),
            'contract_date_start': date.today(),
            'contract_date_end': False,
            'lang': 'fr_BE',

            # Personal
            'name': uuid.uuid4().hex,
            'sex': "male",
            'marital': "single",
            'spouse_fiscal_status': "without_income",
            'disabled': False,
            'disabled_spouse_bool': False,
            'l10n_be_resident_situation': 'resident',
            'disabled_children_number': 0,
            'other_dependents': 0,
            'other_disabled_juniors_dependent': 0,
            'wage': 2500.0,
            'hourly_wage': 0.0,
        }

        if values is None:
            values = [{}]

        # allows to pass a single dict or a list of dict as parameter
        if isinstance(values, dict):
            values = [values]

        employees_to_create = []
        for specific_values in values:
            employee_values = default_values.copy()
            employee_values.update(specific_values)
            employees_to_create.append(employee_values)
        employees = cls.env['hr.employee'].create(employees_to_create)
        return employees

    @classmethod
    def create_employee_with_benefits(cls, values):
        default_values = {
            'commission_on_target': 0.0,
            'fuel_card': 150.0,
            'internet': 38.0,
            'meal_voucher_amount': 7.45,
            'l10n_be_lsa_monthly_pro_other_amount': 150,
            'mobile': 30.0,
            'laptop': 0.0,
            'ip_wage_rate': 0,
            'has_bicycle': False,
        }
        default_values.update(values)
        employee = cls.create_employee(default_values)
        return employee

    @classmethod
    def create_belgian_company(cls, values={}):
        default_values = {
            'name': f'Belgian Company - {uuid.uuid4().hex}',
            'country_id': cls.env.ref('base.be').id,
            'currency_id': cls.env.ref('base.EUR').id,
            'onss_expeditor_number': '123456',
            'street': 'Rue du Paradis',
            'zip': '5310',
            'city': 'Éghezée',
            'vat': 'BE0897223670',
            'phone': '061928374',
            'payroll_config_ids': [(0, 0, {
                'date_version': date(2000, 1, 1),
                'date_start': date(2000, 1, 1),
                'l10n_be_company_number': '0897223670',
                'l10n_be_revenue_code': '1293',
                'onss_registration_number': '225321202',
                'l10n_be_main_joint_committee': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
                'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010').id,
            })],
        }
        default_values.update(values)
        company = cls.env['res.company'].create(default_values)
        return company

    @classmethod
    def create_multibranch_company(cls, depth):
        """
        :return: a list of N nested companies.
        Company at index 0 is the root company.
        """
        companies = cls.env['res.company']
        suffix = uuid.uuid4().hex[:10]
        for i in range(depth):
            companies |= cls.create_belgian_company({
                'name': f'Company level {i} - group {suffix}',
                'parent_id': companies[i - 1].id if i > 0 else False,
            })
        return companies

    @classmethod
    def create_and_validate_payslips(cls, employees, year, months, vals={}):
        batch_values = []

        assert isinstance(months, (list, tuple, int))
        assert isinstance(year, int)
        if isinstance(months, int):
            months = [months]

        for employee in employees:
            for month in months:
                date_from = date(year, month, 1)
                date_to = date_from + relativedelta(months=1, days=-1)
                current_payslip_values = {
                    'name': f'Payslip {employee.name} {year} {month}',
                    'employee_id': employee.id,
                    'company_id': employee.company_id.id,
                    'date_from': date_from,
                    'date_to': date_to,
                    'version_id': employee.version_id.id,
                }
                current_payslip_values.update(vals)
                batch_values.append(current_payslip_values)

        payslips = cls.env['hr.payslip'].create(batch_values)
        payslips.compute_sheet()
        payslips.action_payslip_done()
        payslips.action_payslip_paid()
        return payslips

    def generate_fake_niss(self):
        start_year = 1960
        end_year = 2025
        year = randint(start_year, end_year)
        month = randint(1, 12)
        day = randint(1, 28)

        daily_counter = randrange(1, 998)

        base_str = f"{str(year)[2:]}{month:02d}{day:02d}{daily_counter:03d}"
        base_int = int(base_str)

        if year >= 2000:
            base_int_for_checksum = int(f"2{base_str}")
        else:
            base_int_for_checksum = base_int
        checksum = 97 - (base_int_for_checksum % 97)

        return f"{base_str}{checksum:02d}"
