# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
from datetime import date

from odoo import fields
from odoo.tests import tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWpsReport(TestPayslipContractBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ae_company = cls.env['res.company'].create({
            'name': 'AE',
            'city': 'Dubai',
            'country_id': cls.env.ref('base.ae').id,
            'l10n_ae_employer_code': '987654321',
        })

        cls.uae_employee_structure = cls.env.ref(
            "l10n_ae_hr_payroll.uae_employee_payroll_structure"
        )

        cls.employee_rambo = cls.env["hr.employee"].create(
            {
                "name": "Test Employee Rambo",
                "contract_date_start": date(2025, 6, 22),
                "date_version": date(2025, 6, 22),
                "wage": 5000.0,
                "country_id": cls.env.ref("base.ae").id,
                "identification_id": "AE1344",
                "structure_type_id": cls.uae_employee_structure.type_id.id,
            }
        )

        cls.partner_bank_account = cls.env['res.partner.bank'].create({
            'account_number': "9876543210",
            'partner_id': cls.employee_rambo.work_contact_id.id,
            'allow_out_payment': True,
            'bank_name': "Dubai Bank",
            'bank_bic': 'DEBIDUI',
            'clearing_label_id': cls.env.ref('base.clearing_label_ae').id,
            'clearing_number': '123456789',
        })
        cls.company_bank_account = cls.env['res.partner.bank'].create({
            'account_number': "0011223344",
            'partner_id': cls.ae_company.partner_id.id,
            'allow_out_payment': True,
            'bank_name': "Dubai Bank",
            'bank_bic': 'DEBIDUI',
            'clearing_label_id': cls.env.ref('base.clearing_label_ae').id,
            'clearing_number': '123456789',
        })
        cls.ae_company.write({'l10n_ae_bank_account_id': cls.company_bank_account.id})
        cls.employee_rambo.primary_bank_account_id = cls.partner_bank_account.id

        (
            cls.env.ref('hr_work_entry.uae_work_entry_type_unpaid_leave') +
            cls.env.ref('hr_work_entry.uae_work_entry_type_sick_leave') +
            cls.env.ref('hr_work_entry.uae_hr_work_entry_type_out_of_contract')
        ).requires_allocation = False

        cls.unpaid_leave = cls.env['hr.leave'].create({
            'name': 'Unpaid Leave',
            'employee_id': cls.employee_rambo.id,
            'work_entry_type_id': cls.env.ref('hr_work_entry.uae_work_entry_type_unpaid_leave').id,
            'request_date_from': date(2025, 8, 4),
            'request_date_to': date(2025, 8, 4),
        })

        cls.sick_leave = cls.env['hr.leave'].create({
            'name': 'Sick Time off',
            'employee_id': cls.employee_rambo.id,
            'work_entry_type_id': cls.env.ref('hr_work_entry.uae_work_entry_type_sick_leave').id,
            'request_date_from': date(2025, 8, 6),
            'request_date_to': date(2025, 8, 6),
        })
        cls.out_contract = cls.env['hr.leave'].create({
            'name': 'OC',
            'employee_id': cls.employee_rambo.id,
            'work_entry_type_id': cls.env.ref('hr_work_entry.uae_hr_work_entry_type_out_of_contract').id,
            'request_date_from': date(2025, 8, 8),
            'request_date_to': date(2025, 8, 8),
        })
        cls.rambo_payslip = cls.env['hr.payslip'].create({
            'name': 'Payslip of Rambo',
            'employee_id': cls.employee_rambo.id,
            'version_id': cls.employee_rambo.version_id.id,
            'struct_id': cls.uae_employee_structure.id,
            'date_from': date(2025, 7, 1),
            'date_to': date(2025, 7, 30)
        })
        cls.rambo_payslip_2 = cls.env['hr.payslip'].create({
            'name': 'Payslip 2 of Rambo',
            'employee_id': cls.employee_rambo.id,
            'version_id': cls.employee_rambo.version_id.id,
            'struct_id': cls.uae_employee_structure.id,
            'date_from': date(2025, 8, 1),
            'date_to': date(2025, 8, 30)
        })
        cls.rambo_payslip_run = cls.env['hr.payslip.run'].create({
            'name': 'Test Batch',
            'date_start': date(2025, 7, 1),
            'date_end': date(2025, 8, 30),
            'structure_id': cls.uae_employee_structure.id,
        })

        cls.rambo_payslip.payslip_run_id = cls.rambo_payslip_run
        cls.rambo_payslip_2.payslip_run_id = cls.rambo_payslip_run
        cls.rambo_payslip_run.action_confirm()
        cls.rambo_payslip_run.action_validate()

    def test_wps_report_generation(self):
        now = fields.Datetime.now()
        wizard = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': [self.rambo_payslip.id, self.rambo_payslip_2.id],
            'payslip_run_id': self.rambo_payslip_run.id,
            'export_format': 'csv',
        })
        wizard.generate_payment_report()
        wps_data = self.rambo_payslip_run.slip_ids._l10n_ae_get_wps_data()
        edr_1, edr_2 = wps_data  # Testing format/leave days EDR records
        employee_unique_id = edr_1[1]
        bank_routing_code = edr_1[2]
        leave_days_for_period_july = edr_1[-1]
        leave_days_for_period_august = edr_2[-1]
        self.assertEqual(len(employee_unique_id), 14)
        self.assertEqual(len(bank_routing_code), 9)
        self.assertEqual(leave_days_for_period_august, 3)  # Because the employee had sick leave, unpaid leaves, and Out of Contract entry days.
        self.assertEqual(leave_days_for_period_july, 0)
        create_time = now.replace(tzinfo=datetime.UTC).astimezone(self.env.tz)
        scr_records = wizard._l10n_ae_get_wps_footer(create_time)  # Test SCR records
        for record in scr_records[1:]:
            employer_code = record[1]
            file_creation_time = record[4]
            self.assertEqual(len(employer_code), 15)
            self.assertEqual(len(file_creation_time.split(':')), 3)
