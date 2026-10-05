# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re
import datetime
from io import BytesIO

from dateutil.relativedelta import relativedelta
from odoo import Command
from freezegun import freeze_time
from odoo.tests import HttpCase, tagged, new_test_user
from odoo.addons.hr_payroll.tests.common import TestPayslipBase
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.exceptions import UserError
from odoo.tests import tagged, Form
from odoo.tools.pdf import PdfReader


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestPayslipFlow(TestPayslipBase, HttpCase):

    def test_payslip_state_display(self):
        """ Testing payslip state_display """

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id
        })

        self.assertEqual(payslip.state_display, '03_draft', 'State should be in draft as it\'s new')

        payslip.error_count = 1
        self.assertEqual(payslip.state_display, '01_error', 'state_display should show error')

        payslip.error_count = 0
        payslip.warning_count = 1
        self.assertEqual(payslip.state_display, '02_warning', 'state_display should show warning')

        payslip.action_payslip_done()
        self.assertEqual(payslip.state_display, '04_validated', 'state_display should show validated')

        payslip.action_payslip_paid()
        self.assertEqual(payslip.state_display, '05_paid', 'state_display should show paid')

        payslip.action_payslip_cancel()
        self.assertEqual(payslip.state_display, '06_cancel', 'state_display should show cancel')

    def test_action_open_employee_calendar_uses_the_base_gantt_by_default(self):
        """A non-Belgian payslip keeps the base employee calendar, not a country-specific one."""
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
        })
        action = payslip.action_open_employee_calendar()
        views = {view_type: view_id for view_id, view_type in action['views']}
        expected_gantt = self.env.ref('hr_holidays_gantt.hr_leave_gantt_view_payroll')
        self.assertEqual(views['gantt'], expected_gantt.id)

    def test_00_payslip_flow(self):
        """ Testing payslip flow and report printing """

        # I create an employee Payslip
        richard_payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'date_from': datetime.date(2026, 8, 1),
            'date_to': datetime.date(2026, 8, 31),
        })

        payslip_input = self.env['hr.payslip.input'].search([('payslip_id', '=', richard_payslip.id)])
        # I assign the amount to Input data
        payslip_input.write({'amount': 5.0})

        # I verify the payslip is in draft state
        self.assertEqual(richard_payslip.state, 'draft', 'State not changed!')

        richard_payslip.compute_sheet()

        # Then I click on the 'Confirm' button on payslip
        richard_payslip.action_payslip_done()

        # I verify that the payslip is in validated state
        self.assertEqual(richard_payslip.state, 'validated', 'State not changed!')

        # Then I click on the 'Mark as paid' button on payslip
        richard_payslip.action_payslip_paid()

        # I verify that the payslip is in paid state
        self.assertEqual(richard_payslip.state, 'paid', 'State not changed!')

        # I want to check refund payslip so I click on refund button.
        richard_payslip.refund_sheet()

        # I check on new payslip Credit Note is checked or not.
        payslip_refund = self.env['hr.payslip'].search([('origin_payslip_id', '=', richard_payslip.id), ('credit_note', '=', True), ('is_refund_payslip', '=', True)])
        self.assertTrue(bool(payslip_refund), "Payslip not refunded!")
        self._validate_worked_days(payslip_refund, {'002.00': (-21.0, -168.0, -5000.33)})

        old_net = payslip_refund.net_wage
        payslip_refund.compute_sheet()
        # Compute sheet should have no impact on refunded payslips
        self.assertNotAlmostEqual(old_net, 0)
        self.assertAlmostEqual(payslip_refund.net_wage, old_net)
        self._validate_worked_days(payslip_refund, {'002.00': (-21.0, -168.0, -5000.33)})

        payslip_refund.action_payslip_done()
        payslip_refund.write({'state': 'draft'})
        # Resetting payslip state to draft should have no impact on refunded payslips
        self.assertAlmostEqual(payslip_refund.net_wage, old_net)
        self._validate_worked_days(payslip_refund, {'002.00': (-21.0, -168.0, -5000.33)})

        # I want to generate a payslip from Payslip run.
        payslip_run = self.env['hr.payslip.run'].create({
            'date_end': '2011-09-30',
            'date_start': '2011-09-01',
            'name': 'Payslip for Employee',
            'structure_id': self.developer_pay_structure.id,
        })

        # I create record for generating the payslip for this Payslip run.

        # The contract of Richard starts in 2018, the payrun is for 2011, no valid versions can be found.
        # So the generate_payslip without versions must raise an error
        with self.assertRaises(UserError):
            payslip_run._generate_payslips()

    def test_01_batch_with_specific_structure(self):
        """ Generate payslips for the employee whose running contract is based on the same Salary Structure Type"""

        specific_structure_type = self.env['hr.payroll.structure.type'].create({
            'name': 'Structure Type Test'
        })

        specific_structure = self.env['hr.payroll.structure'].create({
            'name': 'End of the Year Bonus - Test',
            'type_id': specific_structure_type.id,
        })

        # 13th month pay
        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'structure_id': specific_structure.id,
            'name': 'End of the year bonus',
        })

        with self.assertRaises(UserError):
            payslip_run._generate_payslips()

        # Update the structure type and generate payslips again
        specific_structure_type.default_struct_id = specific_structure.id
        self.richard_emp.version_ids[0].structure_type_id = specific_structure_type.id

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'structure_id': specific_structure.id,
            'name': 'Batch for Structure',
        })

        payslip_run._generate_payslips()

        self.richard_emp.structure_type_id = specific_structure_type.id

        self.assertTrue(payslip_run.slip_ids)
        self.assertTrue(self.richard_emp.id in payslip_run.slip_ids.employee_id.ids)

        self.assertEqual(len(payslip_run.slip_ids), 1)
        self.assertEqual(payslip_run.slip_ids.struct_id.id, specific_structure.id)

    def test_03_payslip_batch_with_payment_process(self):
        '''
            Test to check if some payslips in the batch are already paid,
            the batch status can be updated to 'paid' without affecting
            those already paid payslips.
        '''
        start = datetime.date.today() + relativedelta(years=-1, month=8, day=1)
        end = datetime.date.today() + relativedelta(years=-1, month=8, day=31)

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': start,
            'date_end': end,
            'name': 'Payment Test',
            'structure_id': self.developer_pay_structure.id,
        })

        richard_payslip = payslip_run._generate_payslips()
        self.assertEqual(len(payslip_run.slip_ids), 1)
        payslip_run.action_validate()
        # Mark the first payslip as paid and store the paid date
        payslip_run.action_paid()
        paid_date = richard_payslip.paid_date

        jules_bank_acc = self.env['res.partner.bank'].create({
            'account_number': 'BE00111122225555',
            "partner_id": self.jules_emp.work_contact_id.id,
            "allow_out_payment": True,
        })
        self.jules_emp.bank_account_ids = [Command.link(jules_bank_acc.id)]

        self.jules_emp.version_id.write({
            'date_version': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'name': 'Contract for Jules',
            'wage': 5000.33,
            'employee_id': self.jules_emp.id,
            'structure_type_id': self.structure_type.id,
        })

        jules_payslip = self.env['hr.payslip'].create({
            'employee_id': self.jules_emp.id,
            'date_from': start,
            'date_to': end,
            'payslip_run_id': payslip_run.id,
        })
        jules_payslip.action_validate()

        self.assertEqual(len(payslip_run.slip_ids), 2)
        self.assertEqual(payslip_run.state, "02_close", 'All payslips are not paid')
        self.assertEqual(richard_payslip.state, 'paid', 'State not changed!')

        with freeze_time(datetime.date.today() + relativedelta(days=1)):
            payslip_run.action_paid()

        self.assertEqual(payslip_run.state, '03_paid', 'All payslips are paid')
        self.assertTrue(all(payslip.state == 'paid' for payslip in payslip_run.slip_ids), 'Each payslips should be paid')
        self.assertEqual(richard_payslip.paid_date, paid_date, 'payslip paid date should not be changed')

    def test_04_payslip_batch_wizard_for_employee_selection_mode(self):
        '''
            Test employee_ids selection in batch payslip generating wizard
            based on employee selection mode fields
        '''
        self.richard_emp.version_id.contract_date_end = False
        self.jules_emp.version_id.write({
            'date_version': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'name': 'Contract for Jules',
            'wage': 5000.33,
            'employee_id': self.jules_emp.id,
        })

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'name': 'Payment Test',
            'structure_id': self.developer_pay_structure.id,
        })
        self.assertEqual(payslip_run.version_ids, self.richard_emp.version_id | self.jules_emp.version_id, "Versions should be filled at the creation")

        payslip_run._generate_payslips()

        self.assertEqual(len(payslip_run.slip_ids.employee_id.ids), 2)
        self.assertEqual(payslip_run.slip_ids.employee_id, self.richard_emp | self.jules_emp)

    def test_08_payslip_batch_wizard_for_structure_type_selection_mode_with_multiple_contract(self):
        structure_typeA, structure_typeB = self.env['hr.payroll.structure.type'].create([
            {'name': 'Test A'},
            {'name': 'Test B'},
        ])

        structureA, structureB = self.env['hr.payroll.structure'].create([
            {
                'name': 'Test structure A',
                'type_id': structure_typeA.id,
            },
            {
                'name': 'Test structure B',
                'type_id': structure_typeB.id,
            },
        ])

        employee_timmy, employee_gerard, employee_michel = self.env['hr.employee'].create([
            {
                'name': 'Timmy',
                'sex': 'male',
                'birthday': '1984-05-01',
                'date_version': datetime.date.today() + relativedelta(years=-1, month=1, day=1),
                'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=1, day=1),
                'contract_date_end': datetime.date.today() + relativedelta(years=-1, month=3, day=15),
                'wage': 5000.33,
                'structure_type_id': structure_typeA.id,
            },
            {
                'name': 'Gerard',
                'sex': 'male',
                'birthday': '1964-01-23',
                'date_version': datetime.date.today() + relativedelta(years=-1, month=1, day=1),
                'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=1, day=1),
                'wage': 5000.33,
                'structure_type_id': structure_typeA.id,
            },
            {
                'name': 'Michel',
                'sex': 'male',
                'birthday': '1975-10-06',
                'date_version': datetime.date.today() + relativedelta(years=-1, month=1, day=1),
                'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=1, day=1),
                'wage': 7000.33,
                'structure_type_id': structure_typeB.id,
            },
        ])

        employee_timmy.create_version({
            'date_version': datetime.date.today() + relativedelta(years=-1, month=3, day=16),
            'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=3, day=16),
            'contract_date_end': datetime.date.today() + relativedelta(years=1, month=3, day=31),
            'wage': 7000.33,
            'employee_id': employee_timmy.id,
            'structure_type_id': structure_typeB.id,
        })

        payslip_runA, payslip_runB, payslip_runC = self.env['hr.payslip.run'].create([
            {
                'date_start': datetime.date.today() + relativedelta(years=-1, month=2, day=1),
                'date_end': datetime.date.today() + relativedelta(years=-1, month=2, day=31),
                'structure_id': structureA.id,
                'name': 'Payslip RUN A'
            },
            {
                'date_start': datetime.date.today() + relativedelta(years=-1, month=4, day=1),
                'date_end': datetime.date.today() + relativedelta(years=-1, month=4, day=31),
                'structure_id': structureB.id,
                'name': 'Payslip RUN B'
            },
            {
                'date_start': datetime.date.today() + relativedelta(years=-1, month=3, day=1),
                'date_end': datetime.date.today() + relativedelta(years=-1, month=3, day=31),
                'structure_id': structureB.id,
                'name': 'Payslip RUN C'
            },
        ])

        # Batch A for only structure A
        # For february YEAR-1
        # Expected employees/contracts
        # Timmy  contract with struct A (YEAR-1/01/01 -> YEAR-1/03/15)
        # Gerard contract with struct A (YEAR-1/01/01 -> no end date )
        payslip_runA._generate_payslips()
        self.assertEqual(len(payslip_runA.slip_ids), 2)
        self.assertEqual(payslip_runA.slip_ids.version_id, employee_timmy.version_ids[0] | employee_gerard.version_id)
        self.assertEqual(payslip_runA.slip_ids.struct_id, structureA)

        # Batch B for only structure B
        # For april YEAR-1
        # Expected employees/contracts
        # Timmy  contract with struc B (YEAR-1/03/16 -> no end date)
        # Michel contract with struc B (YEAR-1/01/01 -> no end date)
        payslip_runB._generate_payslips()
        self.assertEqual(len(payslip_runB.slip_ids), 2)
        self.assertEqual(payslip_runB.slip_ids.version_id, employee_timmy.version_ids[1] | employee_michel.version_id)
        self.assertEqual(payslip_runB.slip_ids.struct_id, structureB)

        # Batch C for only structure B
        # For march YEAR-1
        # Expected employees/contracts
        # Timmy contract with structure B (YEAR-1/03/16 -> no end date )
        # Michel contract with structure B (YEAR-1/01/01 -> no end date )
        payslip_runC._generate_payslips()
        self.assertEqual(len(payslip_runC.slip_ids.ids), 2)
        self.assertEqual(payslip_runC.slip_ids.version_id, employee_timmy.version_ids[1] | employee_michel.version_id)
        self.assertEqual(payslip_runC.slip_ids.struct_id, structureB)

    def test_09_payslip_creation_with_employee_without_contract(self):
        employee = self.env['hr.employee'].create({
            'name': 'Johnny',
        })
        payslip_form = Form(self.env['hr.payslip'])
        payslip_form.employee_id = employee
        payslip_form.save()
        self.assertTrue(payslip_form)

    def test_10_related_payslip_not_flagged_as_duplicate(self):
        """Refund/Correction payslips must NOT be treated as duplicates."""

        original = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'struct_id': self.richard_emp.structure_type_id.default_struct_id.id,
            'date_from': datetime.date(2025, 12, 1),
            'date_to': datetime.date(2025, 12, 31),
        })

        original.compute_sheet()
        original.action_payslip_done()
        related = original.related_payslip_ids
        refund = related.filtered(lambda p: p.is_refund_payslip)
        correction = related - refund

        def get_issues(payslip):
            return (payslip.issues or {}).values()

        issues = get_issues(refund)
        self.assertFalse(
            any("Duplicate payslips" in (i.get('message') or "") for i in issues),
            "Refund payslip incorrectly flagged as duplicate."
        )

        correction_issues = get_issues(correction)
        self.assertFalse(
            any("Duplicate payslips" in (i.get('message') or "") for i in correction_issues),
            "Correction payslip incorrectly flagged as duplicate."
        )

        duplicate = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'struct_id': original.struct_id.id,
            'date_from': original.date_from,
            'date_to': original.date_to,
        })
        duplicate_issues = get_issues(duplicate)
        self.assertTrue(
            any("Duplicate payslips" in (i.get('message') or "") for i in duplicate_issues),
            "Unrelated duplicate payslip should still trigger the warning."
        )

    def test_payslip_run_creation_message(self):
        """ A payslip generated from a pay run gets a single creation message naming that pay run. """
        self.jules_emp.version_id.write({
            'date_version': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'name': 'Contract for Jules',
            'wage': 5000.33,
            'employee_id': self.jules_emp.id,
        })

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'name': 'Payrun Message Test',
        })

        new_payslips = payslip_run._generate_payslips()

        self.assertEqual(len(new_payslips), 2)
        for payslip in new_payslips:
            self.assertEqual(len(payslip.message_ids), 1, "The pay run name goes into the creation message, no extra message is posted")
            self.assertIn(
                'Payslip created from the pay run Payrun Message Test by %s' % self.env.user.name,
                payslip.message_ids.body,
            )

    def test_payslip_creation_message_without_pay_run(self):
        """ A payslip created outside a pay run names the user who created it. """
        payslip = self.env['hr.payslip'].create({
            'name': 'Standalone Payslip',
            'employee_id': self.richard_emp.id,
            'date_from': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_to': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
        })

        self.assertEqual(len(payslip.message_ids), 1)
        self.assertIn('Payslip created by %s' % self.env.user.name, payslip.message_ids.body)
        self.assertNotIn('from the pay run', payslip.message_ids.body)

    def test_payslip_run_creation_message_disabled(self):
        """ The creation message is not generated at all when the config parameter is set. """
        self.env['ir.config_parameter'].sudo().set_bool('hr_payroll.payslip_run_creation_no_message', True)

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'name': 'Payrun Message Disabled Test',
            'structure_id': self.developer_pay_structure.id,
        })

        new_payslips = payslip_run._generate_payslips()

        self.assertEqual(len(new_payslips), 1)
        self.assertFalse(new_payslips.message_ids)

    def test_04_cancel_a_done_payslip_with_payroll_admin(self):
        """Cancel a validated payslip using a new user with Payroll Admin access."""
        test_user = mail_new_test_user(
            self.env, name="Test user", login="test_user",
            groups="hr_payroll.group_hr_payroll_manager"
        )
        richard_payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
        })
        richard_payslip.action_payslip_done()
        self.assertEqual(richard_payslip.state, 'validated')
        richard_payslip.with_user(test_user).action_payslip_cancel()
        self.assertEqual(richard_payslip.state, 'cancel')

    def test_hr_payslip_without_date_to(self):
        """Ensure payslip creation fails if date_to is missing."""
        employee = self.env['hr.employee'].create({
            'name': 'Jethalal Gada',
            'date_version': '2025-10-01',
            'contract_date_start': '2025-10-01',
        })

        payslip_form = Form(self.env['hr.payslip'])
        payslip_form.employee_id = employee
        payslip_form.date_to = False
        with self.assertRaises(AssertionError):
            payslip_form.save()
        self.assertTrue(payslip_form)

    def test_06_pay_run_payslip_name(self):
        """
        This test checks that the name of the payslip contains the name and the period for which the pay run is
        being run.
        """
        payslip_run = self.env['hr.payslip.run'].create({
            'date_end': '2025-11-30',
            'date_start': '2025-11-01',
            'name': 'Payslip for Employee',
            'structure_id': self.developer_pay_structure.id,
        })
        payslip_run._generate_payslips()
        self.assertEqual(payslip_run.slip_ids.name, 'Payslip - Richard - November 2025')

    def test_payslip_print_creates_attachment(self):
        payroll_user = new_test_user(
            self.env,
            login="payroll_user",
            password="payroll_user",
            groups="hr_payroll.group_hr_payroll_user",
        )
        payslip = self.env["hr.payslip"].create({
            "employee_id": self.richard_emp.id,
        })
        payslip.compute_sheet()

        # to be sure that we've generated attachments only from this test
        self.env["ir.attachment"].search([
            ("res_model", "=", "hr.payslip"),
            ("res_id", "=", payslip.id),
        ]).unlink()

        payslip_reports = payslip._get_pdf_reports()
        expected_attachment_count = sum(len(slips) for slips in payslip_reports.values())
        self.assertGreater(expected_attachment_count, 0)
        self.authenticate(payroll_user.login, "payroll_user")
        self.update_session_context(force_report_rendering=True)

        response = self.url_open(
            f"/print/payslips?list_ids={payslip.id}",
            allow_redirects=False,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/pdf", response.headers.get("Content-Type", ""))

        attachments = self.env["ir.attachment"].search([
            ("res_model", "=", "hr.payslip"),
            ("res_id", "=", payslip.id),
        ])
        self.assertEqual(len(attachments), expected_attachment_count)

        for attachment in attachments:
            self.assertTrue(attachment.raw.content.startswith(b"%PDF"))
            PdfReader(BytesIO(attachment.raw))  # must parse as valid PDF

    def test_negative_net_warning_logic(self):
        """
        Test that the warning 'Net pay is zero or negative.'
        only appears if the structure actually contains a NET rule.
        """
        structure_type = self.env['hr.payroll.structure.type'].create({
            'name': 'Test Type',
        })

        basic_category = self.env.ref('hr_payroll.BASIC')
        ded_category = self.env.ref('hr_payroll.DED')
        net_category = self.env.ref('hr_payroll.NET')

        struct_regular = self.env['hr.payroll.structure'].create({
            'name': 'Regular Pay (With Net Rule)',
            'type_id': structure_type.id,
            'rule_ids': [
                (0, 0, {
                    'name': 'Basic Salary',
                    'sequence': 1,
                    'code': 'BASIC',
                    'category_ids': [(4, basic_category.id)],
                    'condition_select': 'none',
                    'amount_select': 'code',
                    'amount_python_compute': 'result = 1000.0',
                }),
                (0, 0, {
                    'name': 'Huge Deduction',
                    'sequence': 10,
                    'code': 'DEDUCTION',
                    'category_ids': [(4, ded_category.id)],
                    'condition_select': 'none',
                    'amount_select': 'code',
                    'amount_python_compute': 'result = -2000.0',
                }),
                (0, 0, {
                    'name': 'Net Salary',
                    'sequence': 100,
                    'code': 'NET',
                    'category_ids': [(4, net_category.id)],
                    'condition_select': 'none',
                    'amount_select': 'code',
                    'amount_python_compute': "result = categories['BASIC'] + categories['DED']",
                })
            ]
        })

        employee = self.env['hr.employee'].create({'name': 'Test Negative Net Employee'})
        self.env['hr.version'].create({
            'employee_id': employee.id,
            'structure_type_id': structure_type.id,
            'date_version': datetime.date.today() - relativedelta(months=1),
            'contract_date_start': datetime.date.today() - relativedelta(months=1),
            'wage': 1000.0,
        })

        payslip_regular = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'struct_id': struct_regular.id,
        })
        payslip_regular.compute_sheet()

        self.assertLess(payslip_regular.net_wage, 0.0)

        payslip_regular._compute_issues()
        issues_regular = payslip_regular.issues or {}
        warning_messages_regular = [i['message'] for i in issues_regular.values()]

        self.assertTrue(
            any("Net pay is zero or negative." in msg for msg in warning_messages_regular),
            f"Warning did NOT appear. Found messages: {warning_messages_regular}"
        )

    def test_10_translation_title_multiple_employee_payslip(self):
        self.env['res.lang']._activate_lang('it_IT')

        self.richard_emp.write({
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': datetime.date.today() + relativedelta(years=2),
            'wage': 6000.33,
        })
        self.jules_emp.write({
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': datetime.date.today() + relativedelta(years=2),
            'wage': 6000.33,
            'structure_type_id': self.structure_type.id,
        })
        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date(2026, 8, 1),
            'date_end': datetime.date(2026, 8, 31),
            'name': 'Payment Test',
            'structure_id': self.developer_pay_structure.id,
        })

        payslip_run._generate_payslips()
        richard_slip = payslip_run.slip_ids.filtered(lambda s: s.employee_id == self.richard_emp)
        jules_slip = payslip_run.slip_ids.filtered(lambda s: s.employee_id == self.jules_emp)
        self.assertEqual(richard_slip.with_context(lang='en_US').name, 'Payslip - Richard - August 2026')
        self.assertEqual(jules_slip.with_context(lang='it_IT').name, 'Busta paga - Jules - agosto 2026')

    def test_employee_data_updated_warning_logic(self):
        with freeze_time("2020-11-28"):
            payslip = self.env['hr.payslip'].create({
                'employee_id': self.richard_emp.id,
                'date_from': datetime.date(2020, 11, 1),
                'date_to': datetime.date(2020, 11, 30),
            })
            payslip.compute_sheet()
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

        # Update employee data
        with freeze_time("2020-11-29"):
            self.richard_emp.write({
                'wage': self.richard_emp.wage + 1200.0,
            })

        payslip._compute_issues()
        issues = payslip.issues or {}
        warning_messages = [i['message'] for i in issues.values()]

        self.assertTrue(
            any("The employee has been updated." in msg for msg in warning_messages),
            f"Warning did NOT appear. Found messages: {warning_messages}"
        )

    def test_new_employee_version_warning_logic(self):
        with freeze_time("2020-11-28"):
            payslip = self.env['hr.payslip'].create({
                'employee_id': self.richard_emp.id,
                'date_from': datetime.date(2020, 11, 1),
                'date_to': datetime.date(2020, 11, 30),
            })
            payslip.compute_sheet()
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

        # Update employee data
        with freeze_time('2020-11-29'):
            self.richard_emp.sudo().create_version({
                'date_version': datetime.date(2020, 11, 1),
                'contract_date_start': self.richard_emp.contract_date_start,
                'contract_date_end': self.richard_emp.contract_date_end,
                'wage': self.richard_emp.wage + 1200.0,
            })

        payslip._compute_issues()
        issues = payslip.issues or {}
        warning_messages = [i['message'] for i in issues.values()]

        self.assertTrue(
            any("Employee's version has changed." in msg for msg in warning_messages),
            f"Warning did NOT appear. Found messages: {warning_messages}"
        )

    def test_payslip_duplicate_warning_ignores_different_contract(self):
        """
        Test that the duplicate payslip warning does not appear when the existing payslips for the period
        are linked to a different contract than the one on the payslip being computed.
        """
        structure_type = self.env['hr.payroll.structure.type'].create({
            'name': 'Test Type',
        })
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
        })
        contract1 = self.env['hr.version'].create({
            'employee_id': employee.id,
            'structure_type_id': structure_type.id,
            'date_version': datetime.date(2025, 3, 1),
            'contract_date_start': datetime.date(2025, 3, 1),
            'contract_date_end': datetime.date(2025, 3, 15),
            'wage': 1000.0,
        })
        contract2 = self.env['hr.version'].create({
            'employee_id': employee.id,
            'structure_type_id': structure_type.id,
            'date_version': datetime.date(2025, 3, 16),
            'contract_date_start': datetime.date(2025, 3, 16),
            'wage': 1000.0,
        })

        payslip_with_contract_1 = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'struct_id': self.structure_type.default_struct_id.id,
            'date_from': datetime.date(2025, 3, 1),
            'date_to': datetime.date(2025, 3, 31),
            'version_id': contract1.id,
        })
        payslip_with_contract_1.compute_sheet()
        payslip_with_contract_1.action_payslip_done()

        payslip_with_contract_2 = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'struct_id': self.structure_type.default_struct_id.id,
            'date_from': datetime.date(2025, 3, 1),
            'date_to': datetime.date(2025, 3, 31),
            'version_id': contract2.id,
        })
        payslip_with_contract_2.compute_sheet()

        issues = payslip_with_contract_2.issues or {}
        warning_messages = [i['message'] for i in issues.values()]
        self.assertFalse(
            any("Duplicate payslips" in msg for msg in warning_messages),
            f"Warning incorrectly appeared. Found messages: {warning_messages}"
        )
        payslip_with_contract_2.action_payslip_done()

        # Payslips linked to the same contract should still trigger the warning
        payslip2_with_contract2 = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'struct_id': self.structure_type.default_struct_id.id,
            'date_from': datetime.date(2025, 3, 1),
            'date_to': datetime.date(2025, 3, 31),
            'version_id': contract2.id,
        })
        payslip2_with_contract2.compute_sheet()

        issues = payslip2_with_contract2.issues or {}
        warning_messages = [i['message'] for i in issues.values()]
        self.assertTrue(
            any("Duplicate payslips" in msg for msg in warning_messages),
            f"Warning did NOT appear. Found messages: {warning_messages}"
        )

    def test_action_move_to_off_cycle_multiple_payslips(self):
        """
        Test that sending multiple payslips to off-cycle from the list view
        processes each payslip individually without raising an Expected
        singleton error.
        """
        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date(2026, 8, 1),
            'date_end': datetime.date(2026, 8, 31),
            'name': 'Payment Test',
            'structure_id': self.developer_pay_structure.id,
        })

        richard_payslip = payslip_run._generate_payslips()

        jules_payslip = self.env['hr.payslip'].create({
            'employee_id': self.jules_emp.id,
            'date_from': datetime.date(2026, 8, 1),
            'date_to': datetime.date(2026, 8, 31),
            'payslip_run_id': payslip_run.id,
        })

        self.assertEqual(len(payslip_run.slip_ids), 2)

        (richard_payslip | jules_payslip).action_move_to_off_cycle()

        self.assertFalse(richard_payslip.payslip_run_id)
        self.assertFalse(jules_payslip.payslip_run_id)


@tagged('-at_install', 'post_install')
class TestPayslipUi(HttpCase):
    def test_tour_date_input(self):
        """Test payslip form date input."""
        self.start_tour("/odoo", 'hr_payroll_form_view_date_input_tour', login='admin')


@tagged('post_install_l10n')
class TestPayslipLocalizations(HttpCase):

    def test_all_localizations_override_get_data_files_to_update(self):
        installed_locas = {
            module.name
            for module in self.env["ir.module.module"].search([
                ("name", "=like", "l10n_%_hr_payroll"),
                ("state", "=", "installed"),
            ])
            if re.fullmatch(r"l10n_[a-z]{2}_hr_payroll", module.name)
        }

        res = self.env['hr.payslip']._get_data_files_to_update()
        registered_locas = {module_name for module_name, _ in res}

        missing_override = installed_locas - registered_locas

        self.assertFalse(
            missing_override,
            f"The following localization modules must be included in '_get_data_files_to_update()':\n"
            f"{', '.join(missing_override)}"
        )
