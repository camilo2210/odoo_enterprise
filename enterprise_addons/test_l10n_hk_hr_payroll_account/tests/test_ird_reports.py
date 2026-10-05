# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule
from codecs import BOM_UTF8
from freezegun import freeze_time
from lxml import etree

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import file_open
from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestIrdReports(TestL10NHkHrPayrollAccountCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_two = cls._setup_employee(
            country=cls.env.ref('base.hk'),
            structure_type=cls.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2021, 12, 1),
                'contract_date_start': date(2021, 12, 1),
                'wage': 20000.0,
                'identification_id': 'Z683365A',
                'l10n_hk_internet': 200.0,
            },
            employee_fields={
                'private_phone': '+852 9865 1234',
                'private_email': 'defghi@address.ik',
                'private_street': 'Address Line',
                'private_state_id': cls.env.ref('base.state_hk_hk').id,
                'l10n_hk_has_postal_address': True,
                'l10n_hk_postal_street': 'Postal Address Line',
                'l10n_hk_postal_street2': 'Postal Address Line 2',
                'l10n_hk_postal_city': 'Postal City',
                'l10n_hk_postal_zip': '000001',
                'l10n_hk_postal_state_id': cls.env.ref('base.state_hk_kln').id,
                'l10n_hk_postal_country_id': cls.env.ref('base.hk').id,
                'birthday': date(2002, 2, 2),
                'l10n_hk_surname': 'AU-YEUNG',
                'l10n_hk_given_name': 'FUNG',
                'l10n_hk_name_in_chinese': '歐陽 峰',
                'sex': 'male',
                'marital': 'married',
                'job_title': 'HR Manager',
                'spouse_complete_name': 'NATALIE CHAN',
                'l10n_hk_spouse_identification_id': 'Z1234567',
            }
        )
        cls.env['l10n_hk.rental'].create({
            'name': 'Their flat',
            'employee_id': cls.employee_two.id,
            'date_start': date(2021, 12, 1),
            'address': '1 That one road, This building, The block, This one room',
            'valid_up_to_date': date(2029, 12, 1),
            'amount': 8000,
            'nature': 'FLAT/HOUSE',
            'state': 'confirmed',
        })
        cls.employee.write({
            'name': "Test Employee",
            'private_phone': '+852 2851 4813',
            'l10n_hk_surname': 'NATALIE',
            'l10n_hk_given_name': 'CHAN',
            'identification_id': 'Z1234567',
            'private_street': 'Another Address Line',
            'private_state_id': cls.env.ref('base.state_hk_hk').id,
            'l10n_hk_has_postal_address': True,
            'l10n_hk_postal_street': 'Other Postal Address Line',
            'l10n_hk_postal_street2': 'Other Postal Address Line 2',
            'l10n_hk_postal_city': 'Other Postal City',
            'l10n_hk_postal_zip': '000002',
            'l10n_hk_postal_state_id': cls.env.ref('base.state_hk_nt').id,
            'l10n_hk_postal_country_id': cls.env.ref('base.hk').id,
            'sex': 'female',
            'marital': 'married',
            'job_title': 'Experience Developer',
            'spouse_complete_name': 'AU-YEUNG FUNG',
            'l10n_hk_spouse_identification_id': 'Z683365A',
        })
        cls.version.write({
            'date_version': date(2017, 1, 1),
            'contract_date_start': date(2017, 1, 1),
        })
        cls.env['l10n_hk.rental'].create({
            'name': 'Their flat',
            'employee_id': cls.employee.id,
            'date_start': date(2023, 1, 1),
            'address': '1 That one road, This building, The block, This one room',
            'valid_up_to_date': date(2029, 12, 1),
            'amount': 8000,
            'nature': 'FLAT/HOUSE',
            'state': 'confirmed',
        })
        cls.env.company.write({
            'l10n_hk_employer_name': 'Odoo S.A.',
            'l10n_hk_employer_file_number': '123-12345678',
        })
        # Doesn't make sense in real life, but to test it makes our life easier.
        rule = cls.env.ref('l10n_hk_hr_payroll.cap57_employees_salary_fixed_commission')
        rule.input_usage_employee = True
        cls.employee.version_id._set_property_input_value('COMMISSION', 10000)
        cls.employee_two.version_id._set_property_input_value('COMMISSION', 10000)
        cls._make_test_RAP()
        # Invalidate the employee cache to force the recomputation of the rental_id. Needed when testing IR56E first, as it relies on it.
        (cls.employee_two.version_id | cls.employee.version_id).invalidate_recordset(fnames=['l10n_hk_rental_id'])

    def _assert_file_encoding(self, raw_data):
        self.assertTrue(
            raw_data.startswith(BOM_UTF8),
            "The UTF-8 BOM is missing!",
        )
        expected_header = b'<?xml version=\'1.0\' encoding=\'UTF-8\''
        self.assertTrue(
            raw_data[3:].startswith(expected_header),
            "Header mismatch or incorrect capitalization after the BOM.",
        )

    @classmethod
    def _make_test_RAP(cls):
        """ Set up three extra RAP rules so that can be used to test the RAP system. """
        sal_deduction = cls.env.ref('l10n_hk_hr_payroll.cap57_employees_salary_reimbursement')
        rap_categories = cls.env.ref('l10n_hk_hr_payroll.ALLOWANCE_RAP')
        sal_deduction.copy({
            'name': 'Lunch Allowance',
            'code': 'LUNCH',
            'category_ids': [Command.set(rap_categories.ids)],
        })
        sal_deduction.copy({
            "name": "Dinner Allowance",
            "code": "DINNER",
            'category_ids': [Command.set(rap_categories.ids)],
        })
        sal_deduction.copy({
            "name": "Breakfast Allowance",
            "code": "BREAKFAST",
            'category_ids': [Command.set(rap_categories.ids)],
        })

    def _prepare_test_payruns(self, with_pension=True, start=date(2024, 4, 1), end=date(2025, 3, 31)):
        """ Set up one year of payruns for the test company. """
        extra_properties_amounts = {
            "BACKPAY": 2500,
            "LEAVE_ENCASHMENT": 5000,
            "DIRECTOR_FEE": 7500,
            "RETIREMENT_PAY": 10000,
            # Pension pay should only be used for IR56B, in 56G/F it will cause inconsistencies.
            # This is because pension payout is special, only for employees that are already retired.
            "PENSION_PAYOUT": 12500 if with_pension else 0,
            "OVERSEAS_PAY": 15000,
            "TAX_PAID_BY_EMP": 17500,
            "EDU_ALLOWANCE": 20000,
            "SHARE_OPTIONS": 22500,
            "REFERRAL_FEE": 25000,
            "END_OF_YEAR_PAYMENT": 27500,
            "BREAKFAST": 1000,
            "LUNCH": 2000,
            "DINNER": 3000,
        }
        payruns_data = []
        for dt in rrule(MONTHLY, dtstart=start, until=end):
            payruns_data.append({
                'date_start': dt,
                'date_end': dt + relativedelta(day=31),
                'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
            })

        payruns = self.env['hr.payslip.run'].create(payruns_data)
        for i, payrun in enumerate(payruns.sorted('date_end asc')):
            payrun._generate_payslips()
            if i == 0:
                chan_slip = payrun.slip_ids.filtered(lambda s: s.employee_id == self.employee)
                chan_slip._set_input_values(extra_properties_amounts)
                chan_slip.compute_sheet()
        payruns.action_validate()

    def _assert_report_totals(self, xml_tree, recipient_tag='Employee', excludedTags=None):
        """
        Assert that the amounts in the XML, when summed, matches with the totals.
        """
        excludedTags = excludedTags or []
        calculated_batch_total = 0
        xml_batch_total = int(xml_tree.find(".//TotIncomeBatch").text or 0)
        for emp in xml_tree.findall(f".//{recipient_tag}"):
            xml_emp_total = int(emp.find("TotalIncome").text or 0)
            calculated_emp_sum = sum(
                int(child.text)
                for child in emp
                if child.tag.startswith("AmtOf")
                and child.text
                and child.text.isdigit()
                and child.tag not in excludedTags
            )
            self.assertEqual(
                calculated_emp_sum,
                xml_emp_total,
                f"Math mismatch for employee {emp.find('GivenName').text}",
            )
            calculated_batch_total += xml_emp_total

        self.assertEqual(
            calculated_batch_total,
            xml_batch_total,
            "Batch total does not match the sum of individual employee totals.",
        )

    # --------------------------------
    # IR56B
    # --------------------------------

    @freeze_time('2025-04-20')
    def test_ir56b(self):
        """ Generate a ir56b report for the two test employees, it is filled with as many fields as we support. """
        self._prepare_test_payruns()
        ir56b = self.env['l10n_hk.ir56b'].create({
            'start_year': '2024',
            'start_month': '4',
            'end_year': '2025',
            'end_month': '3',
            'year_of_employer_return': '2025',
            'name_of_signer': 'Marc Admin',
            'designation_of_signer': 'Mr.',
        })
        ir56b.action_generate_declarations()
        self.assertEqual(len(ir56b.line_ids), 2)
        ir56b.action_generate_xml()
        message = self.env['mail.message'].search([
            ('model', '=', ir56b._name),
            ('res_id', '=', ir56b.id),
            ('attachment_ids', '!=', False),
        ])
        self.assertEqual(message.preview, 'The IRD reports were successfully generated.')
        with file_open("test_l10n_hk_hr_payroll_account/data/expected_xmls/ir56b.xml", "rt") as f:
            expected_xml = etree.fromstring(f.read().encode())
        self.assertXmlTreeEqual(etree.fromstring(message.attachment_ids.raw.content), expected_xml)
        self._assert_report_totals(expected_xml)
        self._assert_file_encoding(message.attachment_ids.raw.content)

    @freeze_time('2025-04-20')
    def test_ir56b_multiple_versions(self):
        """ Generate a ir56b report for the two test employees, it is filled with as many fields as we support. """
        self.employee.create_version(values={'date_version': date(2025, 1, 1)})
        self._prepare_test_payruns()
        ir56b = self.env['l10n_hk.ir56b'].create({
            'start_year': '2024',
            'start_month': '4',
            'end_year': '2025',
            'end_month': '3',
            'year_of_employer_return': '2025',
            'name_of_signer': 'Marc Admin',
            'designation_of_signer': 'Mr.',
        })
        ir56b.action_generate_declarations()
        self.assertEqual(len(ir56b.line_ids), 2)
        ir56b.action_generate_xml()
        message = self.env['mail.message'].search([
            ('model', '=', ir56b._name),
            ('res_id', '=', ir56b.id),
            ('attachment_ids', '!=', False),
        ])
        self.assertEqual(message.preview, 'The IRD reports were successfully generated.')
        with file_open("test_l10n_hk_hr_payroll_account/data/expected_xmls/ir56b.xml", "rt") as f:
            expected_xml = etree.fromstring(f.read().encode())
        self.assertXmlTreeEqual(etree.fromstring(message.attachment_ids.raw.content), expected_xml)
        self._assert_report_totals(expected_xml)

    @freeze_time('2021-12-20')
    def test_ir56e(self):
        """ Generate the ir56e for the employee_two and validate it. """
        ir56e = self.env['l10n_hk.ir56e'].create({
            'name_of_signer': 'Marc Admin',
            'designation_of_signer': 'Mr.',
        })
        ir56e.action_generate_declarations()
        self.assertEqual(len(ir56e.line_ids), 1)
        ir56e.action_generate_xml()
        message = self.env['mail.message'].search([
            ('model', '=', ir56e._name),
            ('res_id', '=', ir56e.id),
            ('attachment_ids', '!=', False),
        ])
        self.assertEqual(message.preview, 'The IRD reports were successfully generated.')
        with file_open("test_l10n_hk_hr_payroll_account/data/expected_xmls/ir56e.xml", "rt") as f:
            expected_xml = etree.fromstring(f.read().encode())
        self.assertXmlTreeEqual(etree.fromstring(message.attachment_ids.raw.content), expected_xml)
        self._assert_file_encoding(message.attachment_ids.raw.content)

    def test_ir56e_multiple_contracts_no_gap(self):
        """ Test the use case of an employee renewing their contract; the ir56e should NOT pick them up again as new hire """
        with freeze_time('2021-12-20'):
            ir56e = self.env['l10n_hk.ir56e'].create({
                'name_of_signer': 'Marc Admin',
                'designation_of_signer': 'Mr.',
            })
            ir56e.action_generate_declarations()
            self.assertEqual(len(ir56e.line_ids), 1)
            self.assertEqual(ir56e.line_ids.employee_id, self.employee_two)
        with freeze_time('2025-01-15'):
            self.employee_two.contract_date_end = date(2024, 12, 31)
            self.employee_two.create_contract(date=date(2025, 1, 1))
            ir56e = self.env['l10n_hk.ir56e'].create({
                'name_of_signer': 'Marc Admin',
                'designation_of_signer': 'Mr.',
            })
            with self.assertRaises(UserError):
                ir56e.action_generate_declarations()  # the employment is continuous, so it shouldn't pick them up

    def test_ir56e_multiple_contracts_gap(self):
        """ Test the use case of an employee renewing their contract after a one month pause; they are considered NEW hire. """
        with freeze_time('2021-12-20'):
            ir56e = self.env['l10n_hk.ir56e'].create({
                'name_of_signer': 'Marc Admin',
                'designation_of_signer': 'Mr.',
            })
            ir56e.action_generate_declarations()
            self.assertEqual(len(ir56e.line_ids), 1)
            self.assertEqual(ir56e.line_ids.employee_id, self.employee_two)
        with freeze_time('2025-01-15'):
            self.employee_two.contract_date_end = date(2024, 12, 1)
            self.employee_two.create_contract(date=date(2025, 1, 1))
            ir56e = self.env['l10n_hk.ir56e'].create({
                'name_of_signer': 'Marc Admin',
                'designation_of_signer': 'Mr.',
            })
            ir56e.action_generate_declarations()
            self.assertEqual(len(ir56e.line_ids), 1)
            self.assertEqual(ir56e.line_ids.employee_id, self.employee_two)

    @freeze_time('2025-2-28')
    def test_ir56f(self):
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 3, 31),
            'departure_reason_id': self.env.ref('hr.departure_resigned').id,
            'l10n_hk_leaving_hk': False,
        }])
        self._prepare_test_payruns(with_pension=False)
        ir56f = self.env['l10n_hk.ir56f'].create({
            'name_of_signer': 'Marc Admin',
            'designation_of_signer': 'Mr.',
        })
        ir56f.action_generate_declarations()
        self.assertEqual(len(ir56f.line_ids), 1)
        ir56f.action_generate_xml()
        message = self.env['mail.message'].search([
            ('model', '=', ir56f._name),
            ('res_id', '=', ir56f.id),
            ('attachment_ids', '!=', False),
        ])
        self.assertEqual(message.preview, 'The IRD reports were successfully generated.')
        with file_open("test_l10n_hk_hr_payroll_account/data/expected_xmls/ir56f.xml", "rt") as f:
            expected_xml = etree.fromstring(f.read().encode())
        self.assertXmlTreeEqual(etree.fromstring(message.attachment_ids.raw.content), expected_xml)
        self._assert_report_totals(expected_xml)
        self._assert_file_encoding(message.attachment_ids.raw.content)

    def test_ir56f_multiple_contracts_no_gap(self):
        """ Test the use case of an employee renewing their contract; the ir56f should NOT pick them up as departing employee """
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee_two.id,
            'dismissal_date': date(2024, 12, 31),
            'l10n_hk_leaving_hk': False,
        }]).action_register()
        self.employee_two.create_contract(date=date(2025, 1, 1))

        with freeze_time('2024-11-30'):
            ir56f = self.env['l10n_hk.ir56f'].create({
                'name_of_signer': 'Marc Admin',
                'designation_of_signer': 'Mr.',
                'start_year': 2024,
            })
            with self.assertRaises(UserError):
                ir56f.action_generate_declarations()  # the employment is continuous, so it shouldn't pick them up

    def test_ir56f_multiple_contracts_gap(self):
        """ Test the use case of an employee renewing their contract after a one month pause; they are considered as departing employees. """
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee_two.id,
            'dismissal_date': date(2024, 12, 31),
            'l10n_hk_leaving_hk': False,
        }]).action_register()
        self.employee_two.create_contract(date=date(2025, 2, 1))

        with freeze_time('2024-11-30'):
            ir56f = self.env['l10n_hk.ir56f'].create({
                'name_of_signer': 'Marc Admin',
                'designation_of_signer': 'Mr.',
                'start_year': 2024,
            })
            ir56f.action_generate_declarations()
            self.assertEqual(len(ir56f.line_ids), 1)
            self.assertEqual(ir56f.line_ids.employee_id, self.employee_two)

    @freeze_time('2025-2-28')
    def test_ir56g(self):
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 3, 31),
            'l10n_hk_leaving_hk': True,
        }])  # Created in the future; the departure date and l10n_hk_leaving_hk will be set already.
        self._prepare_test_payruns(with_pension=False)
        ir56g = self.env['l10n_hk.ir56g'].create({
            'name_of_signer': 'Marc Admin',
            'designation_of_signer': 'Mr.',
        })
        ir56g.action_generate_declarations()
        self.assertEqual(len(ir56g.line_ids), 1)
        self.env['l10n_hk.ir56g.line'].create({
            'employee_id': self.employee.id,
            'sheet_id': ir56g.id,
            'leave_hk_date': date(2025, 4, 1),
            'is_salary_tax_borne': True,
            'has_money_payable_held_under_ird': True,
            'amount_money_payable': 123456,
            'reason_no_money_payable': '',
            'reason_departure': '4',
            'other_reason_departure': 'Fell down a hole',
            'will_return_hk': True,
            'date_return': date(2026, 1, 1),
            'has_non_exercised_stock_options': True,
            'amount_non_exercised_stock_options': 25,
            'date_grant': date(2025, 1, 1),
            'tax_file_section': '123',
            'tax_file_prn': '456789123',
        })

        ir56g.action_generate_xml()
        message = self.env['mail.message'].search([
            ('model', '=', ir56g._name),
            ('res_id', '=', ir56g.id),
            ('attachment_ids', '!=', False),
        ])
        self.assertEqual(message.preview, 'The IRD reports were successfully generated.')
        with file_open("test_l10n_hk_hr_payroll_account/data/expected_xmls/ir56g.xml", "rt") as f:
            expected_xml = etree.fromstring(f.read().encode())
        self.assertXmlTreeEqual(etree.fromstring(message.attachment_ids.raw.content), expected_xml)
        self._assert_report_totals(expected_xml)
        self._assert_file_encoding(message.attachment_ids.raw.content)

    def test_ir56g_multiple_contracts_no_gap(self):
        """ Test the use case of an employee renewing their contract; the ir56g should NOT pick them up as departing employee """
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2024, 12, 31),
            'l10n_hk_leaving_hk': True,
        }]).action_register()  # We register the departure before continuing.
        self.employee.create_contract(date=date(2025, 1, 1))

        with freeze_time('2024-11-30'):
            ir56g = self.env['l10n_hk.ir56g'].create({
                'name_of_signer': 'Marc Admin',
                'designation_of_signer': 'Mr.',
                'start_year': 2024,
            })
            with self.assertRaises(UserError):
                ir56g.action_generate_declarations()  # the employment is continuous, so it shouldn't pick them up

    def test_ir56g_multiple_contracts_gap(self):
        """ Test the use case of an employee renewing their contract after a one month pause; they are considered as departing employees. """
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2024, 12, 31),
            'l10n_hk_leaving_hk': True,
        }]).action_register()  # We register the departure before continuing.
        self.employee.create_contract(date=date(2025, 2, 1))

        with freeze_time('2024-11-30'):
            ir56g = self.env['l10n_hk.ir56g'].create({
                'name_of_signer': 'Marc Admin',
                'designation_of_signer': 'Mr.',
                'start_year': 2024,
            })
            ir56g.action_generate_declarations()
            self.assertEqual(len(ir56g.line_ids), 1)
            self.assertEqual(ir56g.line_ids.employee_id, self.employee)

    @freeze_time('2026-02-01')
    def test_global_reimbursement_and_deduction(self):
        """Test whether GLOBAL_REIMBURSEMENT and GLOBAL_DEDUCTION are computed correctly and flow into IR56 AmtOfSalary."""
        # Expire the class-level rental so HRA doesn't appear on the Jan 2026 payslip.
        self.employee.l10n_hk_rental_id.valid_up_to_date = date(2025, 12, 31)
        self.employee.version_id._set_property_input_value('COMMISSION', 0)

        payslip = self._generate_payslip(
            date(2026, 1, 1),
            date(2026, 1, 31),
        )
        payslip._set_input_values({
            'GLOBAL_REIMBURSEMENT': 1000.0,
            'GLOBAL_DEDUCTION': 500.0,
        })
        payslip.compute_sheet()
        self._validate_payslip(payslip, {
            'BASIC': 20000.0,
            'ALW.INT': 200.0,
            'GLOBAL_REIMBURSEMENT': 1000.0,
            'GLOBAL_DEDUCTION': -500.0,
            '713_GROSS': 20700.0,
            'GROSS': 20700.0,
            'EEMC': -1035.0,
            'ERMC': -1035.0,
            'NET': 19665.0,
            'MEA': 19665.0,
        })
        payslip.action_payslip_done()

        ir56b = self.env['l10n_hk.ir56b'].create({
            'start_year': 2025,
            'start_month': '4',
            'end_year': 2026,
            'end_month': '3',
            'name_of_signer': 'Test Signer',
            'designation_of_signer': 'Manager',
            'type_of_form': 'O',
        })
        ir56b.action_generate_declarations()
        data = ir56b._get_rendering_data(self.employee)
        self.assertNotIn('error', data, data.get('error'))
        self.assertEqual(data['employees_data'][0]['AmtOfSalary'], 20500)

        departure = self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2026, 1, 31),
            'departure_reason_id': self.env.ref('hr.departure_resigned').id,
            'l10n_hk_leaving_hk': False,
        }])
        departure.action_register()
        ir56f = self.env['l10n_hk.ir56f'].create({
            'start_year': 2025,
            'start_month': '4',
            'end_year': 2026,
            'end_month': '1',
            'name_of_signer': 'Test Signer',
            'designation_of_signer': 'Manager',
        })
        ir56f.line_ids = [Command.create({
            'employee_id': self.employee.id,
            'res_model': 'l10n_hk.ir56f',
            'res_id': ir56f.id,
        })]
        data = ir56f._get_rendering_data(self.employee)
        self.assertNotIn('error', data, data.get('error'))
        self.assertEqual(data['employees_data'][0]['AmtOfSalary'], 20500)

        self.employee.l10n_hk_leaving_hk = True
        ir56g = self.env['l10n_hk.ir56g'].create({
            'start_year': 2025,
            'start_month': '4',
            'end_year': 2026,
            'end_month': '1',
            'name_of_signer': 'Test Signer',
            'designation_of_signer': 'Manager',
        })
        ir56g.action_generate_declarations()
        self.env['l10n_hk.ir56g.line'].create({
            'employee_id': self.employee.id,
            'sheet_id': ir56g.id,
            'leave_hk_date': date(2025, 4, 1),
            'is_salary_tax_borne': True,
            'has_money_payable_held_under_ird': True,
            'amount_money_payable': 123456,
            'reason_no_money_payable': '',
            'reason_departure': '4',
            'other_reason_departure': 'Fell down a hole',
            'will_return_hk': True,
            'date_return': date(2026, 1, 1),
            'has_non_exercised_stock_options': True,
            'amount_non_exercised_stock_options': 25,
            'date_grant': date(2025, 1, 1),
            'tax_file_section': '123',
            'tax_file_prn': '456789123',
        })
        data = ir56g._get_rendering_data(self.employee)
        self.assertNotIn('error', data, data.get('error'))
        self.assertEqual(data['employees_data'][0]['AmtOfSalary'], 20500)

    @freeze_time('2026-2-28')
    def test_termination_pay(self):
        """
        Assert that termination pay payslips are properly picked in the IRD reports, and correctly affecting the amounts.
        LSP/SP are non-taxable and should not affect the report, but PILON should appear in AmtOfBpEtc and affect the totals.
        """
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2026, 3, 31),
            'departure_reason_id': self.env.ref('hr.departure_retired').id,
            'l10n_hk_leaving_hk': False,
        }])
        self._prepare_test_payruns(with_pension=False, start=date(2025, 4, 1), end=date(2026, 3, 31))
        # The last payslip has a LSP, we manually set the month of notice.
        termination_payslip = self.employee.slip_ids[0]
        termination_payslip.action_payslip_draft()
        termination_payslip._set_input_value('PAYMENT_IN_LIEU_OF_NOTICE', 2)
        termination_payslip.action_validate()  # LSP => 138698.63, PIL => 70249.75
        ir56f = self.env['l10n_hk.ir56f'].create({
            'name_of_signer': 'Marc Admin',
            'designation_of_signer': 'Mr.',
        })
        ir56f.action_generate_declarations()
        self.assertEqual(len(ir56f.line_ids), 1)
        ir56f.action_generate_xml()
        message = self.env['mail.message'].search([
            ('model', '=', ir56f._name),
            ('res_id', '=', ir56f.id),
            ('attachment_ids', '!=', False),
        ])
        self.assertEqual(message.preview, 'The IRD reports were successfully generated.')
        with file_open("test_l10n_hk_hr_payroll_account/data/expected_xmls/ir56f_with_termination.xml", "rt") as f:
            expected_xml = etree.fromstring(f.read().encode())
        self.assertXmlTreeEqual(etree.fromstring(message.attachment_ids.raw.content), expected_xml)
        self._assert_report_totals(expected_xml)

    @freeze_time('2025-04-20')
    def test_ir56m(self):
        """Test Subcontracting Fees, XML payload, and Mutual Exclusion."""
        non_employee = self._setup_employee(
            country=self.env.ref('base.hk'),
            structure_type=self.env.ref('l10n_hk_hr_payroll.structure_type_non_employee_cap57'),
            resource_calendar=self.resource_calendar,
            contract_fields={
                'date_version': date(2024, 4, 1),
                'contract_date_start': date(2024, 4, 1),
                'employee_type_id': self.env.ref('l10n_hk_hr_payroll.l10n_hk_contract_type_non_employee').id,
                'wage': 0.0,
                'identification_id': 'V7367309'
            },
            employee_fields={
                'name': 'NON EM PLOYEE',
                'l10n_hk_surname': 'NON',
                'l10n_hk_given_name': 'EM PLOYEE',
                'l10n_hk_name_in_chinese': '陳大文',
                'sex': 'male',
                'marital': 'married',
                'spouse_complete_name': 'WONG, MEI MEI',
                'l10n_hk_spouse_identification_id': 'S2766142',
                'private_phone': '+852 2345 0052',
                'private_street': 'FLAT A, 8/F.',
                'private_street2': 'HAPPY GARDEN',
                'private_city': '1 HAPPY ROAD',
                'private_state_id': self.env.ref('base.state_hk_kln').id,
                'job_title': 'CONSULTANT',
            }
        )
        payslip_ne = self.env['hr.payslip'].create({
            'employee_id': non_employee.id,
            'struct_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_non_employee_salary').id,
            'date_from': date(2024, 4, 1),
            'date_to': date(2024, 4, 30),
        })
        inputs = {
            'SUBCON_FEE': 300000,
            'COMMISSION': 1000,
            'WRITER_FEE': 2000,
            'ARTIST_FEE': 3000,
            'ROYALTIES': 4000,
            'CONSULT_FEE': 5000,
            'SERVICE_FEE': 6000,
            'OTHER': 8000,
            'WITHHELD': 49350,
        }
        payslip_ne._set_input_values(inputs)
        payslip_ne.compute_sheet()
        payslip_ne.action_payslip_done()

        company_contractor = self._setup_employee(
            country=self.env.ref('base.hk'),
            structure_type=self.env.ref('l10n_hk_hr_payroll.structure_type_non_employee_cap57'),
            resource_calendar=self.resource_calendar,
            contract_fields={
                'date_version': date(2024, 4, 1),
                'contract_date_start': date(2024, 4, 1),
                'employee_type_id': self.env.ref('l10n_hk_hr_payroll.l10n_hk_contract_type_contractor').id,
                'wage': 0.0,
            },
            employee_fields={
                'name': 'Contractor Corp',
                'l10n_hk_surname': 'Corp',
                'l10n_hk_given_name': 'Con Tractor',
                'private_street': '123 Business Rd',
                'private_city': 'Kowloon',
                'private_state_id': self.env.ref('base.state_hk_kln').id,
                'private_phone': '+852 2345 6789',
                'sex': 'male',
            },
            work_contact_fields={
                'vat': '87654321',
                'name': 'Contractor Corp Ltd.',
            },
        )

        payslip_cc = self.env['hr.payslip'].create({
            'employee_id': company_contractor.id,
            'struct_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_non_employee_salary').id,
            'date_from': date(2024, 4, 1),
            'date_to': date(2024, 4, 30),
        })
        payslip_cc._set_input_value('SUBCON_FEE', 200001)
        payslip_cc.compute_sheet()
        payslip_cc.action_payslip_done()

        ir56m = self.env['l10n_hk.ir56m'].create({
            'start_year': 2024,
            'start_month': '4',
            'end_year': 2025,
            'end_month': '3',
            'type_of_form': 'O',
            'name_of_signer': 'LEE, MAN MAN',
            'designation_of_signer': 'DIRECTOR',
        })
        ir56m.action_generate_declarations()
        ir56m.action_generate_xml()
        message = self.env['mail.message'].search([
            ('model', '=', ir56m._name),
            ('res_id', '=', ir56m.id),
            ('attachment_ids', '!=', False),
        ])

        with file_open('test_l10n_hk_hr_payroll_account/data/expected_xmls/ir56m.xml', 'rt') as f:
            expected_xml = etree.fromstring(f.read().encode())
        self.assertXmlTreeEqual(etree.fromstring(message.attachment_ids.raw.content), expected_xml)
        self._assert_report_totals(expected_xml, recipient_tag='Recipient', excludedTags=['AmtOfSumWithheld'])

    @freeze_time('2025-3-15')
    def test_ir56f_warning_and_date_of_return(self):
        """ Assert that we correctly warn about a missing reason of departure and that the date of return is correct for the ir56f. """
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 3, 31),
            'departure_reason_id': self.env.ref('l10n_hk_hr_payroll.hr_departure_reason_other').id,
            'l10n_hk_leaving_hk': False,
        }])
        self._prepare_test_payruns(with_pension=False)
        ir56f = self.env['l10n_hk.ir56f'].create({
            'name_of_signer': 'Marc Admin',
            'designation_of_signer': 'Mr.',
        })
        ir56f.action_generate_declarations()
        data = ir56f._get_rendering_data(self.employee)
        self.assertEqual(data['error'], "\nThe following employees don't have a reason set for their departure of type 'Other': Test Employee")
        self.employee.departure_description = '<div data-oe-version="2.0">Reason</div>'  # Simulate the content of a HTML field to assert the sanitization.
        data = ir56f._get_rendering_data(self.employee)
        self.assertEqual(data['employees_data'][0]['RTN_ASS_YR'], 2025)
        self.employee.departure_date = date(2025, 4, 1)
        data = ir56f._get_rendering_data(self.employee)
        self.assertEqual(data['employees_data'][0]['RTN_ASS_YR'], 2026)

    def test_ir56e_year_of_return(self):
        """ Assert that the year of return in 56E correctly follows the tax year. """
        ir56e = self.env['l10n_hk.ir56e'].create({
            'name_of_signer': 'Marc Admin',
            'designation_of_signer': 'Mr.',
        })
        ir56e.submission_date = date(2021, 12, 20)
        ir56e.action_generate_declarations()
        data = ir56e._get_rendering_data(self.employee_two)
        self.assertEqual(data['employees_data'][0]['RTN_ASS_YR'], 2022)

        ir56e.submission_date = date(2021, 4, 1)
        self.employee.contract_date_start = date(2021, 3, 1)
        ir56e.action_generate_declarations()
        data = ir56e._get_rendering_data(self.employee)
        self.assertEqual(data['employees_data'][0]['RTN_ASS_YR'], 2021)

    @freeze_time('2025-3-15')
    def test_ir56g_date_of_return(self):
        """ Assert that the year of return in 56G correctly follows the tax year. """
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 3, 31),
            'departure_reason_id': self.env.ref('l10n_hk_hr_payroll.hr_departure_reason_other').id,
            'l10n_hk_leaving_hk': True,
        }])
        self._prepare_test_payruns(with_pension=False)
        ir56g = self.env['l10n_hk.ir56g'].create({
            'name_of_signer': 'Marc Admin',
            'designation_of_signer': 'Mr.',
        })
        ir56g.action_generate_declarations()
        self.env['l10n_hk.ir56g.line'].create({
            'employee_id': self.employee.id,
            'sheet_id': ir56g.id,
            'leave_hk_date': date(2025, 4, 1),
            'is_salary_tax_borne': True,
            'has_money_payable_held_under_ird': True,
            'amount_money_payable': 123456,
            'reason_no_money_payable': '',
            'reason_departure': '4',
            'other_reason_departure': 'Fell down a hole',
            'will_return_hk': True,
            'date_return': date(2026, 1, 1),
            'has_non_exercised_stock_options': True,
            'amount_non_exercised_stock_options': 25,
            'date_grant': date(2025, 1, 1),
            'tax_file_section': '123',
            'tax_file_prn': '456789123',
        })
        data = ir56g._get_rendering_data(self.employee)
        self.assertEqual(data['employees_data'][0]['RTN_ASS_YR'], 2025)
        self.employee.departure_date = date(2025, 4, 1)
        data = ir56g._get_rendering_data(self.employee)
        self.assertEqual(data['employees_data'][0]['RTN_ASS_YR'], 2026)

    @freeze_time('2025-04-20')
    def test_ir56b_adjust(self):
        """ Assert that a 56B with the adjustment type correctly pull the type of form from the declaration line. """
        self._prepare_test_payruns()
        ir56b = self.env['l10n_hk.ir56b'].create({
            'start_year': '2024',
            'start_month': '4',
            'end_year': '2025',
            'end_month': '3',
            'year_of_employer_return': '2025',
            'name_of_signer': 'Marc Admin',
            'designation_of_signer': 'Mr.',
            'type_of_form': 'ARS',
        })
        ir56b.action_generate_declarations()
        ir56b.line_ids.filtered(lambda l: l.employee_id == self.employee).l10n_hk_hr_payroll_type_of_form = 'S'
        data = ir56b._get_rendering_data(self.employee | self.employee_two)
        employee_data = next(iter(d for d in data['employees_data'] if d['employee'] == self.employee))
        employee_two_data = next(iter(d for d in data['employees_data'] if d['employee'] == self.employee_two))
        self.assertEqual(employee_data['TypeOfForm'], 'S')
        self.assertEqual(employee_two_data['TypeOfForm'], 'A')
