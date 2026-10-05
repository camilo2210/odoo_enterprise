# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from datetime import date, datetime

from odoo import Command, release
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestAutoPayFile(TestL10NHkHrPayrollAccountCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.address_home = cls.env['res.partner'].create([{
            'name': "Test Employee",
            'company_id': cls.env.company.id,
        }])

        cls.company_bank_account = cls.env['res.partner.bank'].create({
            'account_number': "848987654321",
            'bank_name': 'HSBC',
            'bank_bic': 'HSBCHKHHXXX',
            'clearing_label_id': cls.env.ref('base.clearing_label_hk').id,
            'clearing_number': '004',
            'partner_id': cls.env.company.partner_id.id,
            'company_id': cls.env.company.id,
        })

        cls.bank_account = cls.env['res.partner.bank'].create({
            'account_number': "1234567890",
            'bank_name': 'HSBC',
            'bank_bic': '004',
            'clearing_label_id': cls.env.ref('base.clearing_label_hk').id,
            'clearing_number': '004',
            'partner_id': cls.address_home.id,
            'company_id': cls.env.company.id,
            'holder_name': "Test Employee",
        })

        cls.env.company.write({
            'l10n_hk_autopay_partner_bank_id': cls.company_bank_account.id
        })

        cls._setup_common(
            country=cls.env.ref('base.hk'),
            structure=cls.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary'),
            structure_type=cls.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
            resource_calendar=cls.company.resource_calendar_id,
            version_fields={
                'date_version': date(2024, 3, 1),
                'contract_date_start': date(2024, 3, 1),
                'wage': 33570.0,
                'l10n_hk_internet': 200.0,
            },
            employee_fields={
                'marital': "single",
            }
        )
        cls.employee.write({
            'name': "Test Employee",
            'work_contact_id': cls.address_home.id,
            'bank_account_ids':  [Command.link(cls.bank_account.id)],
            'resource_calendar_id': cls.company.resource_calendar_id.id,
            'company_id': cls.env.company.id,
            'l10n_hk_autopay_account_type': 'bban',
            'identification_id': 'Z123456(7)'
        })

        public_holiday_to_create = [
            (datetime(2025, 5, 1), datetime(2025, 5, 1)),
            (datetime(2025, 5, 5), datetime(2025, 5, 5)),
            (datetime(2025, 5, 31), datetime(2025, 5, 31)),
        ]

        for date_from, date_to in public_holiday_to_create:
            cls.env['resource.calendar.leaves'].create([{
                'name': "Public Holiday (global)",
                'calendar_id': cls.company.resource_calendar_id.id,
                'company_id': cls.company.id,
                'date_from': date_from,
                'date_to': date_to,
                'resource_id': False,
                'count_as': "absence",
                'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_hk_work_entry_type_public_holiday').id
            }])

    def setUp(self):
        """ Setup test data """
        super().setUp()
        hk_annual_leave_allocation = self.env['hr.leave.allocation'].create({
            'name': 'HK Annual Leave Allocation',
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_hk_work_entry_type_annual_leave').id,
            'number_of_days': 10,
            'employee_id': self.employee.id,
            'state': 'confirm',
            'date_from': '2025-01-01',
        })
        hk_annual_leave_allocation.action_approve()
        self._generate_leave(self.employee, datetime(2025, 5, 8), datetime(2025, 5, 8), self.env.ref('hr_work_entry.l10n_hk_work_entry_type_annual_leave'))

        self.payrun = self.env['hr.payslip.run'].create({
            'date_start': date(2025, 5, 1),
            'date_end': date(2025, 5, 31),
            'company_id': self.env.company.id,
            'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
            'version_ids': self.employee.version_id.ids,
        })
        self.payslip = self.payrun._generate_payslips()
        commission_rule_id = self.env.ref('l10n_hk_hr_payroll.cap57_employees_salary_fixed_commission')
        self.payslip._set_input_value(commission_rule_id.code, 1917.70)
        self.payslip.compute_sheet()
        self.payrun.action_validate()

    def test_mri_autopay_file(self):
        wizard = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': [self.payslip.id],
            'payslip_run_id': self.payrun.id,
            'effective_date': date(2025, 5, 31),
            'export_format': 'l10n_hk_mri',
            'l10n_hk_autopay_payment_set_code': 'ABC',
            'l10n_hk_autopay_first_party_reference': 'PAY MAY 2025',
        })
        wizard.generate_payment_report()
        content = re.split(r'\r\n', self.payrun.payment_report.decode().strip())
        self.assertListEqual(content, [
            'PHFABCPAY MAY 202520250531848987654321SAHKD                  HKD000000100000000003310480                                                                                                                                                                                                                                                                                                                        ',
            'PD004BBAN1234567890                        00000000003310480Z1234567                           SALARY MAY 2025                    Test Employee',
        ])

    def test_boc_autopay_file(self):
        wizard = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': [self.payslip.id],
            'payslip_run_id': self.payrun.id,
            'effective_date': date(2025, 5, 31),
            'export_format': 'l10n_hk_boc',
            'l10n_hk_autopay_payment_set_code': '001',
            'l10n_hk_autopay_first_party_reference': 'PAY MAY 2025',
        })
        wizard.generate_payment_report()
        content = re.split(r'\r\n', self.payrun.payment_report.decode().strip())
        # Note: Version is dynamic here to avoid breaking on new releases.
        self.assertListEqual(content, [
            '10041234567890                     Test Employee                                                                                                                                       33104.80SALARY MAY 2025                                                                                                                                                                BBAN004',
            f'FRPT848987654321  company_1_data                                                                                                                              HKD202505310000001        33104.80001{release.version[:10]}',
        ])

    def test_boc_non_payment_autopay_file(self):
        wizard = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': [self.payslip.id],
            'payslip_run_id': self.payrun.id,
            'effective_date': date(2025, 5, 31),
            'export_format': 'l10n_hk_boc_non_payment',
            'l10n_hk_autopay_first_party_reference': 'PAY MAY 2025',
        })
        wizard.generate_payment_report()
        content = re.split(r'\r\n', self.payrun.payment_report.decode().strip())
        self.assertListEqual(content, [
            '0041234567890                     Test Employee                                                                                                                                       33104.80PAY MAY 2025                       SALARY MAY 2025                                                                                                                             BBAN004',
            'CF848987654321  company_1_data                                                                                                                              20250531000001        33104.80',
        ])

    def test_bea_autopay_file(self):
        wizard = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': [self.payslip.id],
            'payslip_run_id': self.payrun.id,
            'effective_date': date(2025, 5, 31),
            'export_format': 'l10n_hk_bea_csv',
            'l10n_hk_autopay_payment_set_code': '001',
            'l10n_hk_autopay_first_party_reference': 'PAY MAY 2025',
        })
        wizard.generate_payment_report()
        content = re.split(r'\r\n', self.payrun.payment_report.decode().strip())
        self.assertListEqual(content, [
            '1',
            'SALARY MAY 2025,0041234567890,Test Employee,33104.80',
        ])

    def test_boc_autopay_file_without_identification(self):
        """ The BOC and BEA formats don't need the employee's HKID/passport number: generating
        the report for an employee without either should not crash (see commit fixing this). """
        self.employee.write({'identification_id': False, 'passport_id': False})
        wizard = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': [self.payslip.id],
            'payslip_run_id': self.payrun.id,
            'effective_date': date(2025, 5, 31),
            'export_format': 'l10n_hk_boc',
            'l10n_hk_autopay_payment_set_code': '001',
            'l10n_hk_autopay_first_party_reference': 'PAY MAY 2025',
        })
        wizard.generate_payment_report()
        self.assertTrue(self.payrun.payment_report)

    def test_mri_autopay_file_passport_fallback_normalization(self):
        """ When the HKID is not set, the passport number is used instead and should be
        normalized (stripped, uppercased, alphanumeric only) just like the HKID is. """
        self.employee.write({'identification_id': False, 'passport_id': ' hk123456(7) '})
        wizard = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': [self.payslip.id],
            'payslip_run_id': self.payrun.id,
            'effective_date': date(2025, 5, 31),
            'export_format': 'l10n_hk_mri',
            'l10n_hk_autopay_payment_set_code': 'ABC',
            'l10n_hk_autopay_first_party_reference': 'PAY MAY 2025',
        })
        wizard.generate_payment_report()
        content = re.split(r'\r\n', self.payrun.payment_report.decode().strip())
        self.assertIn('HK1234567', content[1])

    def test_mri_autopay_file_requires_fields(self):
        """ The MRI (HSBC/Hang Seng) format requires a Payment Set Code, a First Party Reference,
        and the employee's HKID or passport number. """
        cases = [
            ('ABC', 'PAY MAY 2025', False, "identifier"),
            ('ABC', False, True, "First Party Reference"),
            (False, 'PAY MAY 2025', True, "Payment Set Code"),
        ]
        for payment_set_code, first_party_reference, has_identification, expected_error in cases:
            with self.subTest(payment_set_code=payment_set_code, first_party_reference=first_party_reference, has_identification=has_identification):
                self.employee.write({
                    'identification_id': 'Z123456(7)' if has_identification else False,
                    'passport_id': False,
                })
                wizard = self.env['hr.payroll.payment.report.wizard'].create({
                    'payslip_ids': [self.payslip.id],
                    'payslip_run_id': self.payrun.id,
                    'effective_date': date(2025, 5, 31),
                    'export_format': 'l10n_hk_mri',
                    'l10n_hk_autopay_payment_set_code': payment_set_code,
                    'l10n_hk_autopay_first_party_reference': first_party_reference,
                })
                with self.assertRaisesRegex(UserError, expected_error):
                    wizard.generate_payment_report()
