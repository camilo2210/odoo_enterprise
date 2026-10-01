from odoo.addons.hr_payroll.tests.common import TestPayslipBase
from odoo.tests.common import tagged
from datetime import date


@tagged('post_install', '-at_install')
class TestPayslipEmailSettings(TestPayslipBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company_send_on_confirm = cls.env['res.company'].create(
            {
                'name': 'Company Send on Confirm',
                'country_id': cls.env.ref('base.us').id,
            }
        )
        cls.employee_1 = cls.createEmployee("Employee 1", cls.company_send_on_confirm)
        cls.employee_2 = cls.createEmployee("Employee 2", cls.company_send_on_confirm)
        cls.company_send_on_confirm.payslip_generate_and_send_trigger = 'on_confirmed'

        cls.company_send_on_paid = cls.env['res.company'].create(
            {
                'name': 'Company Send on Paid',
                'country_id': cls.env.ref('base.us').id,
            }
        )
        cls.employee_3 = cls.createEmployee("Employee 3", cls.company_send_on_paid)
        cls.employee_4 = cls.createEmployee("Employee 4", cls.company_send_on_paid)
        cls.company_send_on_paid.payslip_generate_and_send_trigger = 'on_paid'

        cls.company_never_send = cls.env['res.company'].create(
            {
                'name': 'Company Never Send',
                'country_id': cls.env.ref('base.us').id,
            }
        )
        cls.employee_5 = cls.createEmployee("Employee 5", cls.company_never_send)
        cls.employee_6 = cls.createEmployee("Employee 6", cls.company_never_send)
        cls.company_never_send.payslip_generate_and_send_trigger = 'never'

    @classmethod
    def createEmployee(cls, employee_name, company):
        employee = cls.env['hr.employee'].create(
            {
                'name': employee_name,
                'company_id': company.id,
            }
        )
        employee.version_id.contract_date_start = date(2025, 1, 1)
        return employee

    def _create_payslip(self, employee):
        return self.env['hr.payslip'].create(
            {
                'name': f'Payslip of {employee.name}',
                'employee_id': employee.id,
                'version_id': employee.version_ids[0].id,
                'date_from': date(2025, 10, 1),
                'date_to': date(2025, 10, 31),
            }
        )

    def setUp(self):
        super().setUp()
        self.payslip_1 = self._create_payslip(self.employee_1)
        self.payslip_2 = self._create_payslip(self.employee_2)
        self.payslip_3 = self._create_payslip(self.employee_3)
        self.payslip_4 = self._create_payslip(self.employee_4)
        self.payslip_5 = self._create_payslip(self.employee_5)
        self.payslip_6 = self._create_payslip(self.employee_6)

    def _validate_payslip(self, payslip):
        payslip.with_context(payslip_generate_pdf=True).action_validate()

    def get_payslip_attachments(self, payslip):
        return self.env['ir.attachment'].search(
            [
                ('res_model', '=', payslip._name),
                ('res_id', '=', payslip.id),
            ]
        )

    def test_single_send_on_confirmed(self):
        self._validate_payslip(self.payslip_1)
        attachment = self.get_payslip_attachments(self.payslip_1)
        self.assertEqual(
            len(attachment),
            1,
            "Company Send on Confirm: Validating a payslip should have created an attachment",
        )
        self.payslip_1.action_payslip_paid()
        self.assertEqual(
            len(attachment),
            1,
            "Company Send on Confirm: Marking a payslip as paid shouldn't have created an attachment",
        )

    def test_single_send_on_paid(self):
        self._validate_payslip(self.payslip_3)
        self.assertFalse(
            self.payslip_3.queued_for_pdf,
            "Company Send on Paid: Validating a payslip shouldn't have sent an email",
        )
        self.payslip_3.action_payslip_paid()
        self.assertTrue(
            self.payslip_3.queued_for_pdf,
            "Company Send on Paid: Marking a payslip as paid should have sent an email",
        )

    def test_single_never_send(self):
        self._validate_payslip(self.payslip_5)
        self.assertFalse(
            self.payslip_5.queued_for_pdf,
            "Company Never Send: Validating a payslip shouldn't have sent an email",
        )
        self.payslip_5.action_payslip_paid()
        self.assertFalse(
            self.payslip_5.queued_for_pdf,
            "Company Never Send: Marking a payslip as paid shouldn't have sent an email",
        )

    def test_multi_send_on_confirmed(self):
        # Create payslips that are copies of 1 and 2 because 3,4,etc. don't generate pdfs
        p_3 = self.payslip_1.copy()
        p_4 = self.payslip_1.copy()
        p_5 = self.payslip_1.copy()
        p_6 = self.payslip_1.copy()
        payslips = sum([self.payslip_1, self.payslip_2,
                        p_3, p_4, p_5, p_6], self.env['hr.payslip'])
        self._validate_payslip(payslips)
        for payslip in payslips:
            self.assertTrue(
                payslip.queued_for_pdf,
                "Company Send on Confirm: Validating a payslip should have sent an email",
            )

        payslips._cron_generate_pdf()
        payslips.action_payslip_paid()

        for payslip in payslips:
            self.assertFalse(
                payslip.queued_for_pdf,
                "Company Send on Confirm: Marking a payslip as paid shouldn't have sent an email",
            )

    def test_multi_send_on_paid(self):
        payslips = sum([self.payslip_3, self.payslip_4], self.env['hr.payslip'])
        self._validate_payslip(payslips)
        for payslip in payslips:
            self.assertFalse(
                payslip.queued_for_pdf,
                "Company Send on Paid: Validating a payslip shouldn't have sent an email",
            )

        payslips._cron_generate_pdf()
        payslips.action_payslip_paid()

        for payslip in payslips:
            self.assertTrue(
                payslip.queued_for_pdf,
                "Company Send on Paid: Marking a payslip as paid should have sent an email",
            )

    def test_multi_never_send(self):
        payslips = sum([self.payslip_5, self.payslip_6], self.env['hr.payslip'])
        self._validate_payslip(payslips)
        for payslip in payslips:
            self.assertFalse(
                payslip.queued_for_pdf,
                "Company Never Send: Validating a payslip shouldn't have sent an email",
            )

        payslips._cron_generate_pdf()
        payslips.action_payslip_paid()

        for payslip in payslips:
            self.assertFalse(
                payslip.queued_for_pdf,
                "Company Never Send: Marking a payslip as paid shouldn't have sent an email",
            )

    def test_multi_company(self):
        company_send_on_confirm_payslips = sum(
            [self.payslip_1, self.payslip_2], self.env['hr.payslip']
        )
        company_send_on_paid_payslips = sum(
            [self.payslip_3, self.payslip_4], self.env['hr.payslip']
        )
        company_never_send = sum(
            [self.payslip_5, self.payslip_6], self.env['hr.payslip']
        )
        all_payslips = sum(
            [
                company_send_on_confirm_payslips,
                company_send_on_paid_payslips,
                company_never_send,
            ],
            self.env['hr.payslip'],
        )

        self._validate_payslip(all_payslips)

        for payslip in company_send_on_confirm_payslips:
            self.assertTrue(
                payslip.queued_for_pdf,
                "Company Send on Confirm: Validating a payslip should have sent an email",
            )

        for payslip in company_send_on_paid_payslips:
            self.assertFalse(
                payslip.queued_for_pdf,
                "Company Send on Paid: Validating a payslip shouldn't have sent an email",
            )

        for payslip in company_never_send:
            self.assertFalse(
                payslip.queued_for_pdf,
                "Company Never Send: Validating a payslip shouldn't have sent an email",
            )

        all_payslips._cron_generate_pdf()
        all_payslips.action_payslip_paid()

        for payslip in company_send_on_confirm_payslips:
            self.assertFalse(
                payslip.queued_for_pdf,
                "Company Send on Confirm: Marking a payslip as paid shouldn't have sent an email",
            )

        for payslip in company_send_on_paid_payslips:
            self.assertTrue(
                payslip.queued_for_pdf,
                "Company Send on Paid: Marking a payslip as paid should have sent an email",
            )

        for payslip in company_never_send:
            self.assertFalse(
                payslip.queued_for_pdf,
                "Company Never Send: Marking a payslip as paid shouldn't have sent an email",
            )
