# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta
from itertools import zip_longest
from freezegun import freeze_time

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import Form, tagged, new_test_user
from .tools import mock_skip_stp_api_calls


@tagged("post_install_l10n", "post_install", "-at_install", "superstream")
class TestPayrollSuperStream(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('au')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_manager')
        cls.startClassPatcher(freeze_time(date(2023, 9, 1)))
        cls.account_21400 = cls.env['account.account'].search([
            ('company_ids', '=', cls.company_data['company'].id),
            ('code', '=', 21400)
        ])
        cls.australian_company = cls.company_data['company']
        cls.australian_company.write({
            "name": "My Superstream Australian Company",
            "country_id": cls.env.ref("base.au").id,
            "currency_id": cls.env.ref("base.AUD").id,
            "vat": '85658499097',
            "l10n_au_bms_id": "ODOO-TEST-BMS",
            "l10n_au_branch_code": "1",
            "email": "company@test.com",
            "phone": "123456789",
            "zip": "2000",
        })
        cls.env['l10n_au.stp'].search([]).unlink()
        cls.env['ir.sequence'].create({
            'name': 'STP Sequence',
            'code': 'stp.transaction',
            'prefix': 'PAYEVENT0004',
            'padding': 10,
            'number_next': 1,
        })
        clearing_house = cls.env.ref('l10n_au_hr_payroll_account.res_partner_clearing_house')
        clearing_house.with_company(cls.australian_company).property_account_payable_id = cls.account_21400
        bank_account = cls.env['res.partner.bank'].create({
            "bank_name": "Commonwealth Bank of Australia",
            "bank_bic": "CTBAAU2S",
            "country_id": cls.env.ref("base.au").id,
            "account_number": '12344321',
            "clearing_label_id": cls.env.ref('base.clearing_label_au').id,
            "clearing_number": '123456',
            "company_id": cls.australian_company.id,
            "partner_id": cls.australian_company.partner_id.id,
        })
        cls.journal_id = cls.env["account.journal"].create({
            "name": "Payslip Bank",
            "type": "bank",
            "aba_fic": "CBA",
            "aba_user_spec": "Test Ltd",
            "aba_user_number": "111111",
            "company_id": cls.australian_company.id,
            "bank_account_id": bank_account.id,
        })
        pay_method_line = cls.journal_id._get_available_payment_method_lines('outbound').filtered(
            lambda x: x.code == 'manual')
        pay_method_line.payment_account_id = cls.inbound_payment_method_line.payment_account_id
        cls.employee = cls.env['hr.employee'].create({
            'company_id': cls.australian_company.id,
            'resource_calendar_id': cls.australian_company.resource_calendar_id.id,
            'name': 'Roger Federer',
            'work_phone': '123456789',
            'work_email': 'roger@gmail.com',
            'private_street': 'Australian Street',
            'private_city': 'Sydney',
            "private_state_id": cls.env.ref("base.state_au_2").id,
            "private_zip": "2000",
            "private_country_id": cls.env.ref("base.au").id,
            'private_phone': '123456789',
            'private_email': 'roger@gmail.com',
            'birthday':  date(1970, 3, 21),
            'l10n_au_tfn_declaration': 'provided',
            'l10n_au_tfn': '999999661',
            'l10n_au_training_loan': True,
            'l10n_au_nat_3093_amount': 150,
            'l10n_au_child_support_garnishee_amount': 0.1,
            'l10n_au_child_support_deduction': 150,
            'l10n_au_payroll_id': 'odoo_f47ac10b_001',
            'sex': 'male',
            'date_version': date(1975, 1, 1),
            'contract_date_start': date(1975, 1, 1),
            'wage': 5000,
            'l10n_au_yearly_wage': 60000,
            'structure_type_id': cls.env.ref('l10n_au_hr_payroll.structure_type_schedule_1').id,
            'l10n_au_leave_loading': 'regular',
            'l10n_au_leave_loading_rate': 5,
            'l10n_au_workplace_giving': 100,
            'l10n_au_salary_sacrifice_superannuation': 20,
            'l10n_au_salary_sacrifice_other': 20,
        })

        cls.super_fund = cls.env['l10n_au.super.fund'].create({
            'name': 'Fund A',
            'abn': '2345678912',
            'address_id': cls.env['res.partner'].create({'name': "Fund A Partner"}).id,
            'usi': "2345678912"
        })
        smsf_partner = cls.env['res.partner'].create({'name': "Fund B"})
        cls.super_fund_smsf = cls.env['l10n_au.super.fund'].create({
            'name': 'Fund B',
            'abn': '2345678913',
            'fund_type': 'SMSF',
            'bank_account_id': cls.env['res.partner.bank'].create({
                "account_number": '12344322',
                "clearing_label_id": cls.env.ref('base.clearing_label_au').id,
                "clearing_number": '123-457',
                "company_id": cls.australian_company.id,
                "partner_id": smsf_partner.id,
            }).id,
            'address_id': smsf_partner.id,
            'esa': '12344322',
        })
        cls.super_account_a = cls.env['l10n_au.super.account'].create({
            "date_from": date(2023, 6, 1),
            "employee_id": cls.employee.id,
            "fund_id": cls.super_fund.id,
            # "member_nbr": 1231234123,
        })
        cls.payslips = cls.env['hr.payslip'].create([
            {
                'company_id': cls.australian_company.id,
                'employee_id': cls.employee.id,
                'name': 'Roger Payslip August',
                'date_from': date(2023, 8, 1),
                'date_to': date(2023, 8, 31),
            }, {
                'company_id': cls.australian_company.id,
                'employee_id': cls.employee.id,
                'name': 'Roger Payslip September',
                'date_from': date(2023, 9, 1),
                'date_to': date(2023, 9, 30),
            }
        ])
        cls.employee_user = new_test_user(cls.env, login='mel', groups='hr.group_hr_manager')
        cls.australian_company.l10n_au_hr_super_responsible_id = cls.env["hr.employee"].create({
            "name": "Mel Gibson",
            "resource_calendar_id": cls.australian_company.resource_calendar_id.id,
            "company_id": cls.australian_company.id,
            "private_street": "1 Test Street",
            "private_city": "Sydney",
            "private_state_id": cls.env.ref("base.state_au_2").id,
            "private_zip": "2000",
            "private_country_id": cls.env.ref("base.au").id,
            "private_email": "mel@test.com",
            "private_phone": "123456789",
            "work_phone": "123456789",
            "work_email": "mel@test.com",
            "birthday": date.today() - relativedelta(years=22),
            # fields modified in the tests
            "marital": "single",
            "l10n_au_tfn_declaration": "provided",
            "l10n_au_tfn": "999999661",
            "l10n_au_tax_free_threshold": True,
            "is_non_resident": False,
            "l10n_au_training_loan": False,
            "l10n_au_nat_3093_amount": 0,
            "l10n_au_child_support_garnishee_amount": 0,
            "l10n_au_medicare_exemption": "X",
            "l10n_au_medicare_surcharge": "X",
            "l10n_au_medicare_reduction": "X",
            "l10n_au_child_support_deduction": 0,
            # "l10n_au_previous_payroll_id": "odoo_f47ac10b_001",
            "user_id": cls.employee_user.id,
        })
        cls.australian_company.l10n_au_stp_responsible_id = cls.australian_company.l10n_au_hr_super_responsible_id

    def _test_super_stream(self, superstream, expected_saff_lines: list, payment_total: float):
        superstream.journal_id = self.journal_id
        superstream.action_confirm()
        values = superstream.prepare_rendering_data()
        for expected_line, saff_line in zip_longest(expected_saff_lines, values[3:]):
            assert expected_line and saff_line, (
                    "%s payslip lines expected by the test, but %s were found in the payslip."
                    % (len(expected_line), len(saff_line.line_ids)))
            # Superstream SAFF requires 133 columns
            self.assertEqual(133, len(saff_line),
                "Expected %s Columns but found %s in the payslip." % (133, len(saff_line)))
            for expected_val, saff_val, header in zip_longest(expected_line, saff_line, values[2]):
                self.assertEqual(expected_val, saff_val, "%s was expected but %s is found at header %s!" % (expected_val, saff_val, header))

        # Post Payslip Journal Entries
        superstream.l10n_au_super_stream_lines.payslip_id.move_id._post(False)

        superstream.action_register_super_payment()
        payment_values = [{
            "payment_type": 'outbound',
            "amount": payment_total,
            'destination_account_id': self.account_21400.id
        }]
        self.assertRecordValues(superstream.payment_id, payment_values)

        # Check reconciled
        domain = [('account_id', '=', self.account_21400.id)]
        should_be_reconciled = (superstream.l10n_au_super_stream_lines.payslip_id.move_id.line_ids + superstream.payment_id.move_id.line_ids).filtered_domain(domain)
        self.assertTrue(should_be_reconciled.full_reconcile_id)
        self.assertRecordValues(should_be_reconciled,
                        [{'amount_residual': 0.0, 'amount_residual_currency': 0.0, 'reconciled': True}] * len(should_be_reconciled))

    def get_expected_lines(self, super_values: list):
        """Returns values formatted for SAFF file

        Args:
            super_values (list, optional): Requires list of dict with super_guarantee, super_concessional, annual_salary, start_date, end_date.

        Returns:
            list: returns a list of lists where each list represents one line
        """
        lines = []
        for idx, value in enumerate(super_values):
            total = value.get('super_concessional') + value.get('super_guarantee')
            fund = self.super_fund_smsf if value.get('smsf_fund', False) else self.super_fund
            lines.append([idx, "85658499097", "abn", "", "", "", "My Superstream Australian Company", "Gibson", "Mel", "", "mel@test.com", "123456789", "85658499097", "My Superstream Australian Company", "123456", "12344321",
            "My Superstream Australian Company", fund.abn, fund.usi or "", fund.display_name, fund.esa or "", "DirectDebit", "2023-09-01", "", "", total, fund.bank_account_id._get_clearing_number('AU') or "", fund.bank_account_id.account_number or "",
            fund.bank_account_id.partner_id.name or "", "85658499097", "", "My Superstream Australian Company", "", "999999661", "", "",
            "Federer", "Roger", "", "1", "1970-03-21", "RES", "Australian Street", "", "", "", "Sydney", "2000", "NSW", "AU", "roger@gmail.com", "123456789", "123456789", "", self.employee.l10n_au_payroll_id,
            "", "", value.get('start_date'), value.get('end_date'), value.get('super_guarantee'), "", "", value.get('super_concessional'), "", "", "", "", "1975-01-01", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
            "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
            "", "", "", "", "", "", "", "", ""])
        return lines

    @mock_skip_stp_api_calls()
    def test_00_saff_file_headers(self):
        self.payslips.compute_sheet()
        self.payslips.action_payslip_done()
        superstream = self.payslips._get_superstreams()
        superstream.journal_id = self.journal_id
        superstream.action_confirm()

        values = superstream.prepare_rendering_data()
        header = ["", "1.0", "Negatives Supported", "False", "File ID", "SAFF0000000001"]
        categories = ["Line ID", "Header", "", "", "", "Sender", "", "", "", "", "", "", "Payer", "", "", "", "", "Payee/Receiver", "", "", "", "", "", "", "", "", "", "",
                  "", "Employer", "", "", "", "Super Fund Member Common", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
                  "Super Fund Member Contributions", "", "", "", "", "", "", "", "", "", "Super Fund Member Registration", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
                  "", "Defined Benefits Contributions", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "SuperDefined Benefit Registration", "", "", "", "", "", "", "", "",
                  "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]
        details = ["ID", "SourceEntityID", "SourceEntityIDType", "SourceElectronicServiceAddress", "ElectronicErrorMessaging", "ABN", "Organisational Name Text", "Family Name",
                  "Given Name", "Other Given Name", "E-mail Address Text", "Telephone Minimal Number", "ABN", "Organisational Name Text", "BSB Number", "Account Number",
                  "Account Name Text", "ABN", "USI", "Organisational Name Text", "TargetElectronicServiceAddress", "Payment Method Code", "Transaction Date",
                  "Payment/Customer Reference Number", "Bpay Biller Code", "Payment Amount", "BSB Number", "Account Number", "Account Name Text", "ABN", "Location ID",
                  "Organisational Name Text", "Superannuation Fund Generated Employer Identifier", "TFN", "Person Name Title Text", "Person Name Suffix text", "Family Name",
                  "Given Name", "Other Given Name", "Sex Code", "Birth Date", "Address Usage Code", "Address Details Line 1 Text", "Address Details Line 2 Text",
                  "Address Details Line 3 Text", "Address Details Line 4 Text", "Locality Name Text", "Postcode Text", "State or Territory Code", "Country Code",
                  "E-mail Address Text", "Telephone Minimal Number Landline", "Telephone Minimal Number Mobile", "Member Client Identifier", "Payroll Number Identifier",
                  "Employment End Date", "Employment End Reason Text", "Pay Period Start Date", "Pay Period End Date", "Superannuation Guarantee Amount",
                  "Award or Productivity Amount", "Personal Contributions Amount", "Salary Sacrificed Amount", "Voluntary Amount", "Spouse Contributions Amount",
                  "Child Contributions Amount", "Other Third Party Contributions Amount", "Employment Start Date", "At Work Indicator", "Annual Salary for Benefits Amount",
                  "Annual Salary for Contributions Amount", "Annual Salary for Contributions Effective Start Date", "Annual Salary for Contributions Effective End Date",
                  "Annual Salary for Insurance Amount", "Weekly Hours Worked Number", "Occupation Description", "Insurance Opt Out Indicator", "Fund Registration Date",
                  "Benefit Category Text", "Employment Status Code", "Super Contribution Commence Date", "Super Contribution Cease Date",
                  "Member Registration Amendment Reason Text", "Defined Benefit Member Pre Tax Contribution", "Defined Benefit Member Post Tax Contribution",
                  "Defined Benefit Employer Contribution", "Defined Benefit Notional Member Pre Tax Contribution", "Defined Benefit Notional Member Post Tax Contribution",
                  "Defined Benefit Notional Employer Contribution", "Ordinary Time Earnings", "Actual Periodic Salary or Wages Earned", "Superannuable Allowances Paid",
                  "Notional Superannuable Allowances", "Service Fraction", "Service Fraction Effective Date", "Full Time Hours", "Contracted Hours", "Actual Hours Paid",
                  "Employee Location Identifier", "Service Fraction", "Service Fraction Start Date", "Service Fraction End Date", "Defined Benefit Employer Rate",
                  "Defined Benefit Employer Rate Start Date", "Defined Benefit Employer Rate End Date", "Defined Benefit Member Rate", "Defined Benefit Member Rate Start Date",
                  "Defined Benefit Member Rate End Date", "Defined Benefit Annual Salary 1", "Defined Benefit Annual Salary 1 Start Date",
                  "Defined Benefit Annual Salary 1 End Date", "Defined Benefit Annual Salary 2", "Defined Benefit Annual Salary 2 Start Date",
                  "Defined Benefit Annual Salary 2 End Date", "Defined Benefit Annual Salary 3", "Defined Benefit Annual Salary 3 Start Date",
                  "Defined Benefit Annual Salary 3 End Date", "Defined Benefit Annual Salary 4", "Defined Benefit Annual Salary 4 Start Date",
                  "Defined Benefit Annual Salary 4 End Date", "Defined Benefit Annual Salary 5", "Defined Benefit Annual Salary 5 Start Date",
                  "Defined Benefit Annual Salary 5 End Date", "Leave Without Pay Code", "Leave Without Pay Code Start Date", "Leave Without Pay Code End Date",
                  "Annual Salary for Insurance Effective Date", "Annual Salary for Benefits Effective Date", "Employee Status Effective Date",
                  "Employee Benefit Category Effective Date", "Employee Location Identifier", "Employee Location Identifier Start Date", "Employee Location Identifier End Date"]

        self.assertListEqual(values[0][:-1], header[:-1])  # don't compare the sequence number
        self.assertListEqual(values[1], categories)
        self.assertListEqual(values[2], details)

    @mock_skip_stp_api_calls()
    def test_01_autogenerated_super_stream(self):
        self.payslips.compute_sheet()
        self.payslips.action_payslip_done()
        superstream = self.payslips._get_superstreams()

        expected_lines = self.get_expected_lines([
            {"super_guarantee": 550,
             "super_concessional": 20,
             "start_date": "2023-08-01",
             "end_date": "2023-08-31"},
            {"super_guarantee": 550,
             "super_concessional": 20,
             "start_date": "2023-09-01",
             "end_date": "2023-09-30"}
        ])

        self._test_super_stream(superstream, expected_lines, 1140)

    @mock_skip_stp_api_calls()
    def test_02_super_stream_manually(self):
        self.payslips.compute_sheet()
        self.payslips.action_payslip_done()

        # Remove autogenerated superstream
        self.payslips._get_superstreams().unlink()

        # Create new superstream
        superstream_form = Form(self.env["l10n_au.super.stream"].with_company(self.australian_company))
        superstream_form.journal_id = self.journal_id
        for payslip in self.payslips:
            with superstream_form.l10n_au_super_stream_lines.new() as line:
                line.payslip_id = payslip
                line.employee_id = payslip.employee_id
                line.sender_id = self.australian_company.l10n_au_hr_super_responsible_id
                line.super_account_id = self.super_account_a

        superstream = superstream_form.save()
        superstream.action_confirm()
        expected_lines = self.get_expected_lines([
            {"super_guarantee": 550,
             "super_concessional": 20,
             "start_date": "2023-08-01",
             "end_date": "2023-08-31"},
            {"super_guarantee": 550,
             "super_concessional": 20,
             "start_date": "2023-09-01",
             "end_date": "2023-09-30"}
        ])

        self._test_super_stream(superstream, expected_lines, 1140)

    @mock_skip_stp_api_calls()
    def test_03_super_stream_multi_account(self):
        # Set proportion for account A
        self.super_account_a.proportion = 0.4
        # Create another account
        self.env['l10n_au.super.account'].create({
            "date_from": date(2023, 6, 1),
            "employee_id": self.employee.id,
            "fund_id": self.super_fund_smsf.id,
            "proportion": 0.6,
        })

        self.payslips.compute_sheet()
        self.payslips.action_payslip_done()
        superstream = self.payslips._get_superstreams()

        expected_lines = self.get_expected_lines([
            {"super_guarantee": 220,
             "super_concessional": 8,
             "start_date": "2023-08-01",
             "end_date": "2023-08-31"},
            {"super_guarantee": 330,
             "super_concessional": 12,
             "start_date": "2023-08-01",
             "end_date": "2023-08-31",
             "smsf_fund": True},
            {"super_guarantee": 220,
             "super_concessional": 8,
             "start_date": "2023-09-01",
             "end_date": "2023-09-30"},
            {"super_guarantee": 330,
             "super_concessional": 12,
             "start_date": "2023-09-01",
             "end_date": "2023-09-30",
             "smsf_fund": True}
        ])

        self._test_super_stream(superstream, expected_lines, 1140)

    @mock_skip_stp_api_calls()
    def test_04_super_account_dates(self):
        """ Tests second superaccount with 100% proportion """
        # deactivate account A
        self.super_account_a.account_active = False
        # Create another account for 100% proportion
        self.env['l10n_au.super.account'].create({
            "date_from": date(2023, 9, 1),
            "employee_id": self.employee.id,
            "fund_id": self.super_fund.id,
        })
        slip = self.payslips[1]
        slip.compute_sheet()
        slip.action_payslip_done()
        superstream = slip._get_superstreams()

        expected_lines = self.get_expected_lines([
            {"super_guarantee": 550,
             "super_concessional": 20,
             "start_date": "2023-09-01",
             "end_date": "2023-09-30"}
        ])
        self._test_super_stream(superstream, expected_lines, 570)

    def test_remove_source_entity_id_type_on_super_stream(self):
        """Test that removing the source entity id type from the Super Contributions."""
        superstream_form = Form(self.env["l10n_au.super.stream"])
        superstream_form.source_entity_id_type = False

        self.assertFalse(superstream_form.source_entity_id)

    @freeze_time("2026-07-31")
    @mock_skip_stp_api_calls()
    def test_payday_super_separate_superstreams(self):
        self.employee.write({
            'contract_date_start': "2026-01-01",
            'contract_date_end': "2026-12-31",
        })
        batch_1 = self.env["hr.payslip.run"].create(
                    {
                        "date_start": "2026-07-02",
                        "date_end": "2026-07-15",
                        "name": "January Batch",
                        "company_id": self.company.id,
                        "structure_id": self.env.ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular').id,
                    }
                )
        batch_1._generate_payslips()
        batch_1.slip_ids.compute_sheet()
        batch_1.action_validate()
        superstream_1 = batch_1.slip_ids._get_superstreams()

        self.assertEqual(len(superstream_1), 1, "First payrun should create exactly one superstream")
        self.assertEqual(superstream_1.state, "draft")

        batch_2 = self.env["hr.payslip.run"].create(
                    {
                        "date_start": "2026-07-16",
                        "date_end": "2026-07-31",
                        "name": "January Batch",
                        "company_id": self.company.id,
                        "structure_id": self.env.ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular').id,
                    }
                )
        batch_2._generate_payslips()
        batch_2.slip_ids.compute_sheet()
        batch_2.action_validate()
        superstream_2 = batch_2.slip_ids._get_superstreams()

        self.assertEqual(len(superstream_2), 1, "Second payrun should create its own superstream")
        self.assertNotEqual(
            superstream_1, superstream_2,
            "Second payrun must not be merged into the first draft superstream",
        )

    def _create_payslip_for_period(self, date_from, date_to):
        return self.env['hr.payslip'].create({
            'company_id': self.australian_company.id,
            'employee_id': self.employee.id,
            'date_from': date_from,
            'date_to': date_to,
        })

    @mock_skip_stp_api_calls()
    @freeze_time(date(2026, 6, 15))
    def test_amending_payslip_after_super_stream_paid(self):
        """
        Amending a payslip via a Full File Replacement after its super stream has been
        paid and STP submitted should create a new super stream covering the delta
        of the missed super contribution.

        Runs against the current date so the active ATO rules apply. The payslip
        covers the current pay period so the wizard resolves to FFR.
        """
        # Discard setUp payslips so the auto-created STP only covers the new slip
        self.payslips.unlink()
        today = date.today()
        slip = self._create_payslip_for_period(today.replace(day=1), today + relativedelta(day=31))
        slip.compute_sheet()
        slip.action_payslip_done()

        # Pay the original super stream
        superstream = slip._get_superstreams()
        superstream.journal_id = self.journal_id
        superstream.action_confirm()
        slip.move_id.action_post()
        superstream.action_register_super_payment()
        self.assertEqual(superstream.state, 'done')

        # Submit STP so the payslip is locked under FFR rules
        stp = self.env["l10n_au.stp"].search([("payslip_ids", "in", slip.id)])
        self.assertTrue(stp, "An STP record should be created when the payslip is validated")
        stp.submit_date = today
        submit_wizard = self.env['l10n_au.stp.submit'].create({
            'l10n_au_stp_id': stp.id,
            'stp_terms': True,
        })
        submit_wizard.action_submit()
        self.assertEqual(stp.state, 'sent')

        # Run the FFR wizard to reset the payslip for amendment
        action = stp.action_replace_file()
        ffr_wizard = self.env["l10n_au.stp.ffr.wizard"].with_context(action['context']).create({})
        self.assertEqual(ffr_wizard.amendment_type, 'ffr',
                         "Wizard should resolve to FFR while the pay period is current")
        ffr_wizard.ffr_payslip_ids.write({"to_reset": True})
        ffr_wizard.action_create_ffr()
        self.assertEqual(slip.state, 'draft', "Payslip should be reset to draft after FFR")

        # Amend the payslip with an extra bonus and re-validate
        self.env['hr.payslip.input'].create({
            'payslip_id': slip.id,
            'salary_rule_id': self.env.ref('l10n_au_hr_payroll.input_bonus_commissions').id,
            'amount': 1000,
        })
        slip.compute_sheet()
        slip.action_payslip_done()

        # A second super stream covering only the delta should be created
        new_superstream = slip._get_superstreams() - superstream
        self.assertEqual(len(new_superstream), 1, "A new super stream should be created for the delta")
        new_lines = new_superstream.l10n_au_super_stream_lines
        self.assertEqual(len(new_lines), 1, "The new super stream should only contain the delta line of the amended payslip")
        self.assertEqual(new_lines.payslip_id, slip, "The new super stream should not contain lines for other payslips")
        self.assertRecordValues(new_lines, [{
            'superannuation_guarantee_amount': 120,
            'award_or_productivity_amount': 0,
            'salary_sacrificed_amount': 0,
            'voluntary_amount': 0,
            'amount_total': 120,
        }])

        # Both the original and the FFR report should declare the full YTD super
        # amount, the delta is only deducted on the super stream record.
        ffr_stp = self.env["l10n_au.stp"].search([("payslip_ids", "in", slip.id), ("ffr", "=", True)])
        self.assertEqual(len(ffr_stp), 1, "An FFR STP record should be created for the amended payslip")
        full_super = slip._get_line_values(['SUPER'], vals_list=['total'])['SUPER'][slip.id]['total']
        self.assertEqual(
            full_super,
            superstream.l10n_au_super_stream_lines['superannuation_guarantee_amount'] + 120,
            "The recomputed SUPER line should hold the full amount, not the delta",
        )
        ffr_stp.submit_date = today
        for report in stp + ffr_stp:
            contributions = report._get_rendering_data()[1][0]["SuperannuationContributionCollection"]
            super_liability = next(c for c in contributions if c["EntitlementTypeC"] == "L")
            self.assertEqual(
                super_liability["EmployerContributionsYearToDateA"],
                full_super,
                "STP report %s should declare the full YTD super liability" % report.name,
            )

    @mock_skip_stp_api_calls()
    @freeze_time(date(2026, 6, 15))
    def test_unamended_payslip_creates_no_zero_super_stream(self):
        """
        Re-validating a payslip without any change after an FFR reset should not
        create a new super stream, since the full super contribution has already
        been paid and the delta is zero.
        """
        # Discard setUp payslips so the auto-created STP only covers the new slip
        self.payslips.unlink()
        today = date.today()
        slip = self._create_payslip_for_period(today.replace(day=1), today + relativedelta(day=31))
        slip.compute_sheet()
        slip.action_payslip_done()

        # Pay the original super stream
        superstream = slip._get_superstreams()
        superstream.journal_id = self.journal_id
        superstream.action_confirm()
        slip.move_id.action_post()
        superstream.action_register_super_payment()
        self.assertEqual(superstream.state, 'done')

        # Submit STP and reset the payslip through the FFR wizard
        stp = self.env["l10n_au.stp"].search([("payslip_ids", "in", slip.id)])
        stp.submit_date = today
        submit_wizard = self.env['l10n_au.stp.submit'].create({
            'l10n_au_stp_id': stp.id,
            'stp_terms': True,
        })
        submit_wizard.action_submit()

        action = stp.action_replace_file()
        ffr_wizard = self.env["l10n_au.stp.ffr.wizard"].with_context(action['context']).create({})
        ffr_wizard.ffr_payslip_ids.write({"to_reset": True})
        ffr_wizard.action_create_ffr()

        # Re-validate without amending: the super delta is zero
        slip.compute_sheet()
        slip.action_payslip_done()
        self.assertEqual(
            slip._get_superstreams(), superstream,
            "No new super stream should be created when the super contribution is already fully paid",
        )
        self.assertFalse(
            self.env["l10n_au.super.stream"].search([("state", "=", "draft"), ("company_id", "=", self.australian_company.id)]),
            "No empty draft super stream should be left behind for a zero delta",
        )

    @mock_skip_stp_api_calls()
    @freeze_time(date(2026, 6, 15))
    def test_amending_payslip_after_super_stream_paid_update_event(self):
        """
        With two payslips/STPs submitted, amending the older (first) one via the
        FFR wizard should resolve to an Update Event because a newer submit STP
        exists. It should:
          - keep both original submit STPs intact (no FFR replacement),
          - create a new STP record of type "update" for the amended payslip,
          - generate a delta super stream covering the missed super contribution.
        """
        # Discard setUp payslips so the auto-created STPs only cover the new slips
        self.payslips.unlink()
        today = date.today()
        # Two past periods: two months ago and previous month
        first_of_this_month = today.replace(day=1)
        period2_end = first_of_this_month - relativedelta(days=1)
        period2_start = period2_end.replace(day=1)
        period1_end = period2_start - relativedelta(days=1)
        period1_start = period1_end.replace(day=1)

        slips = []
        stps = []
        for idx, (start, end) in enumerate([(period1_start, period1_end), (period2_start, period2_end)]):
            slip = self._create_payslip_for_period(start, end)
            slip.compute_sheet()
            slip.action_payslip_done()

            superstream = slip._get_superstreams()
            superstream.journal_id = self.journal_id
            superstream.action_confirm()
            slip.move_id.action_post()
            superstream.action_register_super_payment()
            self.assertEqual(superstream.state, 'done')

            stp = self.env["l10n_au.stp"].search([("payslip_ids", "in", slip.id)])
            # Stagger submit_date so the second STP is the most recent
            stp.submit_date = end + relativedelta(days=1)
            submit_wizard = self.env['l10n_au.stp.submit'].create({
                'l10n_au_stp_id': stp.id,
                'stp_terms': True,
            })
            submit_wizard.action_submit()
            self.assertEqual(stp.state, 'sent')
            slips.append(slip)
            stps.append(stp)

        first_slip, second_slip = slips
        first_stp, second_stp = stps
        first_superstream = first_slip._get_superstreams()

        # Amending the older STP should auto-resolve to Update Event since a newer submit STP exists
        action = first_stp.action_replace_file()
        amend_wizard = self.env["l10n_au.stp.ffr.wizard"].with_context(action['context']).create({})
        self.assertEqual(amend_wizard.amendment_type, 'update',
                         "Wizard should auto-resolve to an Update Event when a newer submit STP exists")
        amend_wizard.ffr_payslip_ids.write({"to_reset": True})
        amend_wizard.action_create_ffr()

        # Both original STPs should remain sent submit events, not replaced by FFR
        self.assertEqual(first_stp.state, 'sent')
        self.assertEqual(second_stp.state, 'sent')
        self.assertFalse(first_stp.is_replaced, "First STP should not be marked as replaced when amending via update event")
        self.assertFalse(second_stp.is_replaced, "Second STP should not be impacted by amending the first")
        self.assertFalse(
            self.env["l10n_au.stp"].search_count([("previous_report_id", "=", first_stp.id), ("ffr", "=", True)]),
            "No FFR STP record should be created in the update-event amend flow",
        )
        self.assertEqual(first_slip.state, 'draft', "First payslip should be reset to draft to allow amendment")
        self.assertEqual(second_slip.state, 'validated', "Second payslip should be untouched")

        # Amend the first payslip and re-validate
        self.env['hr.payslip.input'].create({
            'payslip_id': first_slip.id,
            'salary_rule_id': self.env.ref('l10n_au_hr_payroll.input_bonus_commissions').id,
            'amount': 1000,
        })
        first_slip.compute_sheet()
        first_slip.action_payslip_done()

        # A new update-type STP should be created for the amendment of the first slip.
        # Update events track employees instead of payslips.
        update_stp = self.env["l10n_au.stp"].search([
            ("l10n_au_stp_emp.employee_id", "in", first_slip.employee_id.ids),
            ("payevent_type", "=", "update"),
            ("ffr", "=", False),
        ])
        self.assertEqual(len(update_stp), 1, "An update event STP should be created for the amended payslip")

        # A delta super stream should be created for the first slip only
        new_superstream = first_slip._get_superstreams() - first_superstream
        self.assertEqual(len(new_superstream), 1, "A delta super stream should be created for the first slip")
        new_lines = new_superstream.l10n_au_super_stream_lines
        self.assertEqual(len(new_lines), 1, "The new super stream should only contain the delta line of the amended payslip")
        self.assertEqual(new_lines.payslip_id, first_slip, "The new super stream should not contain lines of the second payslip")
        self.assertRecordValues(new_lines, [{
            'superannuation_guarantee_amount': 120,
            'award_or_productivity_amount': 0,
            'salary_sacrificed_amount': 0,
            'voluntary_amount': 0,
            'amount_total': 120,
        }])
