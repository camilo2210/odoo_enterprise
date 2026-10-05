from datetime import date

from freezegun import freeze_time

from odoo.tests import tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@tagged("post_install_l10n", "post_install", "-at_install")
class TestOmWpsReport(TestPayslipContractBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_om = cls.env["res.company"].create({
            "name": "Company OM",
            "country_id": cls.env.ref("base.om").id,
        })
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company_om.ids))

        cls.om_structure = cls.env.ref("l10n_om_hr_payroll.l10n_om_monthly_pay")

        # Salary payer, MOL numbers and bank account
        cls.company_om.l10n_om_company_mol_number = "1234567890"
        cls.company_om.l10n_om_salary_payer = cls.company_om.partner_id
        cls.company_om.l10n_om_salary_payer_mol_number = "1234567890"
        cls.company_bank = cls.env["res.partner.bank"].create({
            "account_number": "OM12NBOM0000000000001234",
            "partner_id": cls.company_om.partner_id.id,
            "allow_out_payment": True,
            "bank_bic": "NBOMOMRX",
        })
        cls.company_om.l10n_om_bank_account_id = cls.company_bank

        # Employee setup
        cls.richard_emp.write({
            "company_id": cls.company_om.id,
            "passport_id": "J12345678",
            "resource_calendar_id": cls.env.ref(
                "l10n_om_hr_payroll.l10n_om_resource_calendar_def_40h"
            ).id,
        })
        cls.richard_emp.version_id.write({
            "l10n_om_identification_type": "passport",
            "structure_type_id": cls.env.ref("l10n_om_hr_payroll.l10n_om_employee").id,
        })

        # Employee bank account
        cls.employee_bank = cls.env["res.partner.bank"].create({
            "account_number": "OM98NBOM0000000000005678",
            "partner_id": cls.richard_emp.work_contact_id.id,
            "allow_out_payment": True,
            "bank_bic": "NBOMOMRX",
        })
        cls.richard_emp.bank_account_ids = cls.employee_bank

        # Create payslips
        cls.payslip_1 = cls.env["hr.payslip"].create({
            "name": "Payslip 1",
            "employee_id": cls.richard_emp.id,
            "version_id": cls.richard_emp.version_id.id,
            "struct_id": cls.om_structure.id,
            "date_from": date(2025, 7, 1),
            "date_to": date(2025, 7, 31),
        })

        cls.payslip_run = cls.env["hr.payslip.run"].create({
            "name": "July 2025 Batch",
            "date_start": date(2025, 7, 1),
            "date_end": date(2025, 7, 31),
            "company_id": cls.company_om.id,
            "structure_id": cls.om_structure.id,
        })
        cls.payslip_1.payslip_run_id = cls.payslip_run
        cls.payslip_run.action_confirm()
        cls.richard_emp.write({"review_state": "1_reviewed"})
        cls.payslip_run.action_validate()

    @freeze_time("2025-08-01")
    def test_wps_report_generation(self):
        """Test that the WPS wizard generates a CSV with correct structure."""
        wizard = self.env["hr.payroll.payment.report.wizard"].create({
            "payslip_ids": [self.payslip_1.id],
            "payslip_run_id": self.payslip_run.id,
            "export_format": "l10n_om_wps",
            "l10n_om_note": "Test payment",
        })
        wizard.generate_payment_report()
        self.assertTrue(wizard.payment_report)

        employer_row = wizard._l10n_om_get_wps_employer_record()[0]
        self.assertEqual(employer_row[0], "1234567890")  # Company MOL
        self.assertEqual(employer_row[1], "1234567890")  # Payer MOL (same as company here)
        self.assertEqual(employer_row[2], "NBO")  # Bank code resolved from BIC NBOMOMRX
        self.assertEqual(employer_row[4], "2025")  # Salary year
        self.assertEqual(employer_row[5], "07")  # Salary month
        self.assertEqual(employer_row[7], 1)  # Number of records
        self.assertEqual(employer_row[8], "Salary")  # Payment type

        emp_row = self.payslip_1._l10n_om_get_wps_employee_records(note="Test payment")[0]
        self.assertEqual(emp_row[0], "P")  # Passport
        self.assertEqual(emp_row[1], "J12345678")
        self.assertEqual(emp_row[2], "Richard")
        self.assertEqual(emp_row[3], "NBOMOMRX")  # Employee BIC
        self.assertEqual(emp_row[5], "M")  # Monthly frequency
        self.assertEqual(emp_row[13], "Test payment")

    @freeze_time("2025-08-01")
    def test_wps_daily_counter_increments_and_resets(self):
        """Test that the daily WPS file counter increments on successive calls and resets each day."""
        wizard1 = self.env["hr.payroll.payment.report.wizard"].create({
            "payslip_ids": [self.payslip_1.id],
            "payslip_run_id": self.payslip_run.id,
            "effective_date": date(2025, 8, 1),
            "export_format": "l10n_om_wps",
        })
        wizard2 = self.env["hr.payroll.payment.report.wizard"].create({
            "payslip_ids": [self.payslip_1.id],
            "payslip_run_id": self.payslip_run.id,
            "effective_date": date(2025, 8, 2),
            "export_format": "l10n_om_wps",
        })
        ref1 = wizard1._get_l10n_om_wps_file_reference()
        ref2 = wizard1._get_l10n_om_wps_file_reference()
        ref3 = wizard2._get_l10n_om_wps_file_reference()
        ref4 = wizard1._get_l10n_om_wps_file_reference()
        self.assertEqual(ref1, "SIF_1234567890_NBO_20250801_001")
        self.assertTrue(ref2.endswith("002"))
        self.assertTrue(ref3.endswith("001"))
        self.assertTrue(ref4.endswith("003"))

    def test_wps_employee_salary_values(self):
        """Test that the employee record row contains correct salary values from payslip lines."""
        all_codes = ['BASIC', 'NET', 'DEDUCTION', 'SPF_EMP']
        all_line_values = self.payslip_1._get_line_values(all_codes)

        basic = all_line_values['BASIC'][self.payslip_1.id]['total']
        net = all_line_values['NET'][self.payslip_1.id]['total']
        alw_codes = self.payslip_1.struct_id.rule_ids.filtered_domain([
            ('category_ids', 'child_of', self.payslip_1.env.ref('hr_payroll.ALW').id)
        ]).mapped('code')
        extra_income = sum(
            line.total
            for line in self.payslip_1.line_ids
            if line.salary_rule_id.code in alw_codes
        )
        deduction = abs(all_line_values['DEDUCTION'][self.payslip_1.id]['total'])
        spf_emp = abs(all_line_values['SPF_EMP'][self.payslip_1.id]['total'])

        emp_row = self.payslip_1._l10n_om_get_wps_employee_records()[0]
        fmt = self.env['hr.payslip']._l10n_om_format_float

        self.assertEqual(emp_row[7], fmt(net))
        self.assertEqual(emp_row[8], fmt(basic))
        self.assertEqual(emp_row[10], fmt(extra_income))
        self.assertEqual(emp_row[11], fmt(deduction))
        self.assertEqual(emp_row[12], fmt(spf_emp))
