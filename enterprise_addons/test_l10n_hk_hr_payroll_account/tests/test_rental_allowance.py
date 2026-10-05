# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule
from lxml import etree
from odoo.tests import freeze_time, tagged
from odoo.tools import BinaryBytes

from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestRentalAllowance(TestL10NHkHrPayrollAccountCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_user = cls.env['res.users'].create({
            'partner_id': cls.env['res.partner'].create({
                'name': cls.employee.name,
            }).id,
            'login': f'{cls.employee.name}@login.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.employee.user_id = cls.employee_user
        cls.env.company.write({
            'l10n_hk_employer_name': 'Odoo S.A.',
            'l10n_hk_employer_file_number': '123-12345678',
        })
        cls.version.employee_id.write({
            'sex': 'male',
            'private_street': 'Address Line',
            'private_state_id': cls.env.ref('base.state_hk_hk').id,
            'l10n_hk_surname': 'AU-YEUNG',
            'l10n_hk_given_name': 'FUNG',
            'l10n_hk_name_in_chinese': '歐陽 峰',
            'identification_id': 'Z683365A',
        })

    # ========================================================
    # Flow tests of setting up and generating a rental payslip
    # ========================================================

    def test_reimbursement_flow(self):
        """
        An employee register for rental allowance using the reimbursement lease type.
        This will test the flow that leads up to a running rental with a payslip.
        """
        rental = self._create_test_rental(self.version.employee_id)
        self.assertEqual(rental.state, 'draft')
        # Rental was created as expected, the HR team review and approve it. This subscribes the hr responsible and employee, and send a message.
        rental.action_confirm_rental()
        self.assertEqual(rental.message_follower_ids.partner_id, self.employee_user.partner_id | self.employee.hr_responsible_id.partner_id)
        self.assertEqual(len(rental.message_ids), 1)
        self.assertEqual(rental.state, 'confirmed')
        # Ready to go! The employee should now upload their first proof in the chatter; and HR will validate it.
        # After validating, they would update the validity date to be the end of the paid period.
        rental.valid_up_to_date = date(2025, 1, 31)
        # That done, Jan payslip would now have the rental allowance applied to it!
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {'HRA': 8000.0, 'BASIC': 12000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'EEMC': -1010.0, 'ERMC': -1010.0, 'NET': 19190.0, 'MEA': 19190.0}
        self._validate_payslip(payslip, payslip_results)

    def test_reimbursement_flow_partial(self):
        """
        An employee register for rental allowance using the reimbursement lease type.
        This will test the flow that leads up to a running rental with a payslip.
        The company set a maximum limit of 5000 to be reimbursed.
        """
        rental = self._create_test_rental(self.version.employee_id)
        rental.monthly_rent_amount = 5000
        rental.action_confirm_rental()
        rental.valid_up_to_date = date(2025, 1, 31)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        # Ensure that the limit of 5000 was applied.
        payslip_results = {'HRA': 5000.0, 'BASIC': 15000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'EEMC': -1010.0, 'ERMC': -1010.0, 'NET': 19190.0, 'MEA': 19190.0}
        self._validate_payslip(payslip, payslip_results)

    def test_reimbursement_no_proof(self):
        """
        An employee register for rental allowance using the reimbursement lease type.
        This will test the flow that leads up to a running rental with a payslip.
        The employee didn't upload a proof for this month, so no rental will be paid.
        """
        rental = self._create_test_rental(self.version.employee_id)
        rental.action_confirm_rental()
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'EEMC': -1010.0, 'ERMC': -1010.0, 'NET': 19190.0, 'MEA': 19190.0}
        self._validate_payslip(payslip, payslip_results)
        # Also validate the warning we display.
        self.assertEqual(payslip.issues['0']['action_text'], 'Rental')

    def test_reimbursement_flow_installment(self):
        """
        Test the use case of an employee paying their rent in batch (quarterly in this case).
        By setting the valid_up_to field at the end of the four months, the next few payslips will properly apply the rental.
        """
        rental = self._create_test_rental(self.version.employee_id)
        rental.action_confirm_rental()
        rental.valid_up_to_date = date(2025, 3, 31)
        # We expect 8000 as HRA in the next three months
        for dt in rrule(MONTHLY, dtstart=datetime(2025, 1, 1), until=datetime(2025, 3, 1)):
            payslip = self._generate_payslip(dt.date(), dt.date() + relativedelta(day=31))
            payslip_results = {'HRA': 8000.0, 'BASIC': 12000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'EEMC': -1010.0, 'ERMC': -1010.0, 'NET': 19190.0, 'MEA': 19190.0}
            self._validate_payslip(payslip, payslip_results)

    def test_reimbursement_two_proofs(self):
        """
        An employee register for rental allowance using the reimbursement lease type.
        He forgot to submit the proof of december, and submit twice in Jan.
        His salary can "afford" reimbursing twice in a month.
        """
        rental = self._create_test_rental(self.version.employee_id)
        rental.amount = 4000
        rental.action_confirm_rental()
        rental.valid_up_to_date = date(2025, 1, 31)
        # Uh oh, employee forgot to submit rental for dec 2024... it's ok, he can submit it with January's. HR will manually adjust the payslip.
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip._set_input_value('HRA_MANUAL', 8000)  # Two reimbursement of 4000 at once
        payslip.compute_sheet()
        payslip_results = {'HRA_MANUAL': 8000, 'HRA': 8000.0, 'BASIC': 12000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'EEMC': -1010.0, 'ERMC': -1010.0, 'NET': 19190.0, 'MEA': 19190.0}
        self._validate_payslip(payslip, payslip_results)

    def test_reimbursement_two_proofs_capped(self):
        """
        An employee register for rental allowance using the reimbursement lease type.
        He forgot to submit the proof of december, and submit twice in Jan.
        His salary cannot "afford" reimbursing twice in a month.
        """
        rental = self._create_test_rental(self.version.employee_id)
        rental.action_confirm_rental()
        rental.valid_up_to_date = date(2025, 1, 31)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip._set_input_value('HRA_MANUAL', 16000)  # Two reimbursement of 8000 at once
        payslip.compute_sheet()
        # Employee actively worked 184 hours, minimum wages in Jan 2025 were HKD $40 => minimum wages for this months were HKD$7360
        payslip_results = {'HRA_MANUAL': 16000, 'HRA': 12640.0, 'BASIC': 7360.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'EEMC': -1010.0, 'ERMC': -1010.0, 'NET': 19190.0, 'MEA': 19190.0}
        self._validate_payslip(payslip, payslip_results)

    def test_direct_payment_flow(self):
        """
        An employee register for rental allowance using the direct payment lease type.
        This will test the flow that leads up to a running rental with a payslip.
        """
        rental = self._create_test_rental(self.version.employee_id)
        rental.lease_type = 'direct_payment'
        rental.action_confirm_rental()
        # Rental has now been approved, and should appear in the payslip!
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {'HEPR': 8000.0, 'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'EEMC': -1010.0, 'ERMC': -1010.0, 'NET': 19190.0, 'MEA': 19190.0}
        self._validate_payslip(payslip, payslip_results)

    def test_co_payment_flow(self):
        """
        An employee register for rental allowance using the co payment lease type.
        This will test the flow that leads up to a running rental with a payslip.
        """
        rental = self._create_test_rental(self.version.employee_id)
        rental.lease_type = 'co_payment'
        rental.co_pay_amount = 2000
        rental.action_confirm_rental()
        # Rental has now been approved, and should appear in the payslip!
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {'HEPR': 8000, 'HC': -2000.0, 'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'EEMC': -1010.0, 'ERMC': -1010.0, 'NET': 17190.0, 'MEA': 17190.0}
        self._validate_payslip(payslip, payslip_results)

    def test_housing_allowance_flow(self):
        """
        The company provides their employee with a fixed housing allowance.
        """
        self.version._set_property_input_value('HA', 8000)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {'HA': 8000, 'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 28200.0, 'GROSS': 28200.0, 'EEMC': -1410.0, 'ERMC': -1410.0, 'NET': 26790.0, 'MEA': 26790.0}
        self._validate_payslip(payslip, payslip_results)

    def test_reminder(self):
        """
        An employee didn't upload their receipt for the month!
        We'll remind them to make sure they didn't just forget.
        """
        rental = self._create_test_rental(self.version.employee_id)
        rental.action_confirm_rental()
        with freeze_time('2026-01-31'):
            # We only remind employees if they have a rental that is actively running.
            rental.valid_up_to_date = date.today() + relativedelta(day=31, months=-1)
            rental._cron_send_reminder()
            mail = self.env['mail.mail'].search(
                domain=[('subject', '=', 'HK Employee, reminder to submit your rental proof for January 2026')],
                limit=1,
            )
            self.assertEqual(len(mail), 1)

    def test_similar_rental(self):
        """ Test creating two rentals for the same address and ensuring they're detected as 'similar' """
        second_employee = self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2021, 11, 1),
                "contract_date_start": date(2021, 11, 1),
                "wage": 28000.0,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_scheme_join_date": date(2021, 11, 1),
                "identification_id": "C6686689",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        self._create_test_rental(self.version.employee_id, {'date_end': date(2025, 1, 31)})
        rental_2 = self._create_test_rental(self.version.employee_id, {'date_start': date(2025, 2, 1)})
        # A same employee cannot have two rentals overlapping, so it doesn't make sense to consider them 'similar' in any cases.
        self.assertEqual(rental_2.similar_rentals_count, 0)
        self.assertFalse(rental_2.similar_rentals_monthly_rent_too_high)
        # On the contrary, it could happen with other employees.
        rental_3 = self._create_test_rental(second_employee, {'date_end': date(2025, 1, 15)})
        self.assertEqual(rental_3.similar_rentals_count, 1)  # Only match with rental in a matching period.
        self.assertTrue(rental_3.similar_rentals_monthly_rent_too_high)  # It's double
        rental_4 = self._create_test_rental(second_employee, {'date_start': date(2025, 1, 16)})
        self.assertEqual(rental_4.similar_rentals_count, 2)  # Both other rentals overlap
        # Rentals with no address details are skipped even if they match.
        rental_5 = self._create_test_rental(self.version.employee_id, {
            'building': '',
            'floor': '',
            'flat': '',
            'district': None,
            'state_id': None,
        })
        rental_6 = self._create_test_rental(second_employee, {
            'building': '',
            'floor': '',
            'flat': '',
            'district': None,
            'state_id': None,
        })
        self.assertEqual(rental_6.similar_rentals_count, 0)
        self.assertEqual(rental_5.similar_rentals_count, 0)

    def test_payment_proof_attachment_not_corrupted(self):
        """
        Uploading a payment proof on a rental posts a chatter message with the file attached.
        The attached bytes must match the uploaded payload, so that the audit trail
        preserves the original proof exactly as submitted by the employee.
        """
        rental = self._create_test_rental(self.version.employee_id)
        rental.action_confirm_rental()

        raw_bytes = b'\x89PNG\r\n\x1a\n\x00\x11\x22\x33\x44\x55\x66\x77'
        attachment = self.env['ir.attachment'].create({
            'name': 'proof.png',
            'raw': BinaryBytes(raw_bytes),
            'res_model': 'l10n_hk.rental',
            'res_id': rental.id,
        })
        rental.action_attach_payment_proofs(attachment_ids=[attachment.id])

        message = rental.message_ids.filtered('attachment_ids')[:1]
        self.assertEqual(len(message.attachment_ids), 1)
        self.assertEqual(message.attachment_ids.name, 'proof.png')
        self.assertEqual(message.attachment_ids.raw.content, raw_bytes)

    def test_reimbursement_flow_date_check(self):
        """
        Ensure that payslips do not pick up a running reimbursement rental if it hasn't started yet/has already ended.
        """
        rental = self._create_test_rental(self.version.employee_id)
        rental.write({
            'date_start': date(2025, 2, 1),
            'date_end': date(2025, 5, 31),
            'valid_up_to_date': date(2025, 12, 31),
        })
        rental.action_confirm_rental()

        # Case 1: Payslip ends before the rental start.
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        hra_line = payslip.line_ids.filtered(lambda line: line.salary_rule_id.code == 'HRA')
        self.assertEqual(len(hra_line), 0)
        # Case 2: Payslip starts after the rental ended.
        payslip = self._generate_payslip(date(2025, 6, 1), date(2025, 6, 30))
        hra_line = payslip.line_ids.filtered(lambda line: line.salary_rule_id.code == 'HRA')
        self.assertEqual(len(hra_line), 0)

    def test_direct_payment_flow_date_check(self):
        """
        Ensure that payslips do not pick up a running direct payment rental if it hasn't started yet/has already ended.
        """
        rental = self._create_test_rental(self.version.employee_id)
        rental.write({
            'date_start': date(2025, 2, 1),
            'date_end': date(2025, 5, 31),
            'lease_type': 'direct_payment',
        })
        rental.action_confirm_rental()

        # Case 1: Payslip ends before the rental start.
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        hepr_line = payslip.line_ids.filtered(lambda line: line.salary_rule_id.code == 'HEPR')
        self.assertEqual(len(hepr_line), 0)
        # Case 2: Payslip starts after the rental ended.
        payslip = self._generate_payslip(date(2025, 6, 1), date(2025, 6, 30))
        hepr_line = payslip.line_ids.filtered(lambda line: line.salary_rule_id.code == 'HEPR')
        self.assertEqual(len(hepr_line), 0)

    def test_co_payment_flow_date_check(self):
        """
        Ensure that payslips do not pick up a running co payment rental if it hasn't started yet/has already ended.
        """
        rental = self._create_test_rental(self.version.employee_id)
        rental.write({
            'date_start': date(2025, 2, 1),
            'date_end': date(2025, 5, 31),
            'lease_type': 'co_payment',
            'co_pay_amount': 2000,
        })
        rental.action_confirm_rental()

        # Case 1: Payslip ends before the rental start.
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        hepr_hc_lines = payslip.line_ids.filtered(lambda line: line.salary_rule_id.code in ('HEPR', 'HC'))
        self.assertEqual(len(hepr_hc_lines), 0)
        # Case 2: Payslip starts after the rental ended.
        payslip = self._generate_payslip(date(2025, 6, 1), date(2025, 6, 30))
        hepr_hc_lines = payslip.line_ids.filtered(lambda line: line.salary_rule_id.code in ('HEPR', 'HC'))
        self.assertEqual(len(hepr_hc_lines), 0)

    def test_multi_rental_setup(self):
        """
        Test the behavior of the system when multiple rentals are running at the same time (for different period of time).
        We need to make sure that the one set on the employee is the currently active one; and that the payslip always pick
        the rental matching its period.
        """
        rental_1 = self._create_test_rental(self.version.employee_id, {
            'date_start': date(2025, 9, 1),
            'date_end': date(2025, 11, 30),
            'valid_up_to_date': date(2025, 12, 31),
        })
        rental_1.action_confirm_rental()
        rental_2 = self._create_test_rental(self.version.employee_id, {
            'date_start': date(2025, 12, 1),
            'valid_up_to_date': date(2026, 12, 31),
            'amount': 10000,
        })
        rental_2.action_confirm_rental()
        # Oct payslip
        payslip = self._generate_payslip(date(2025, 10, 1), date(2025, 10, 31))
        hra_line = payslip.line_ids.filtered(lambda line: line.salary_rule_id.code == 'HRA')
        self.assertEqual(hra_line.amount, 8000)
        # Nov payslip
        payslip = self._generate_payslip(date(2025, 11, 1), date(2025, 11, 30))
        hra_line = payslip.line_ids.filtered(lambda line: line.salary_rule_id.code == 'HRA')
        self.assertEqual(hra_line.amount, 8000)
        # Dec payslip
        payslip = self._generate_payslip(date(2025, 12, 1), date(2025, 12, 31))
        hra_line = payslip.line_ids.filtered(lambda line: line.salary_rule_id.code == 'HRA')
        self.assertEqual(hra_line.amount, 10000)

    # ==========================================================================
    # Test batch confirming/resetting rentals
    # ==========================================================================

    def _create_batch_rentals(self):
        """ Create three draft rentals over consecutive periods, so that they can all be confirmed together. """
        rentals = self.env['l10n_hk.rental']
        for date_start, date_end in (
            (date(2025, 1, 1), date(2025, 3, 31)),
            (date(2025, 4, 1), date(2025, 6, 30)),
            (date(2025, 7, 1), False),
        ):
            rentals |= self._create_test_rental(self.version.employee_id, {
                'date_start': date_start,
                'date_end': date_end,
            })
        return rentals

    def test_batch_confirm_rentals(self):
        """ Test that confirming a batch confirms every draft rental, with its own approval message and followers. """
        rentals = self._create_batch_rentals()
        already_confirmed = rentals[0]
        already_confirmed.action_confirm_rental()

        rentals.action_confirm_rental()

        self.assertEqual(set(rentals.mapped('state')), {'confirmed'})
        expected_followers = self.employee_user.partner_id | self.employee.hr_responsible_id.partner_id
        for rental in rentals:
            # The already confirmed rental is skipped, so it doesn't get a duplicated approval message.
            self.assertEqual(len(rental.message_ids), 1)
            self.assertEqual(rental.message_follower_ids.partner_id, expected_followers)

    def test_batch_reset_to_draft(self):
        """ Test that resetting a batch only drafts back the confirmed rentals, and that they can be confirmed again. """
        rentals = self._create_batch_rentals()
        confirmed_rentals = rentals[:2]
        confirmed_rentals.action_confirm_rental()
        still_draft = rentals - confirmed_rentals

        rentals.action_reset_to_draft()

        self.assertEqual(set(rentals.mapped('state')), {'draft'})
        # Resetting doesn't post any message, the drafted rental only kept its approval one.
        self.assertEqual(len(still_draft.message_ids), 0)
        for rental in confirmed_rentals:
            self.assertEqual(len(rental.message_ids), 1)

        # The whole batch can be approved again, this time posting an approval message on each of them.
        rentals.action_confirm_rental()

        self.assertEqual(set(rentals.mapped('state')), {'confirmed'})
        self.assertEqual(len(still_draft.message_ids), 1)
        for rental in confirmed_rentals:
            self.assertEqual(len(rental.message_ids), 2)

    # ===========================================================================================
    # Test that for each IRD report type and each rental type, we end up with the correct report.
    # Note: Our goal is to ensure we put the correct amount in the correct key of the reports;
    # so a single payslip should be enough to validate.
    # ===========================================================================================

    def _prepare_test_ir56b(self):
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
        ir56b.action_generate_xml()
        return ir56b

    @freeze_time('2025-01-31')
    def test_ird56b_reimbursement(self):
        rental = self._create_test_rental(self.version.employee_id)
        rental.action_confirm_rental()
        rental.valid_up_to_date = date(2025, 1, 31)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        ir56b = self._prepare_test_ir56b()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56b'),
            ('res_id', '=', ir56b.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '12200')
        self.assertEqual(xml_root.find(".//TotalIncome").text, '12200')
        self.assertEqual(xml_root.find(".//RentPaidEe1").text, '24000')
        self.assertEqual(xml_root.find(".//RentRefund1").text, '8000')

    @freeze_time('2025-01-31')
    def test_ird56b_reimbursement_two_of_same_address(self):
        """ Create two test rental of the same address, in different versions, and ensure they are summed well in the report. """
        rental = self._create_test_rental(self.employee, override_vals={'date_end': date(2025, 1, 31)})
        rental.valid_up_to_date = date(2025, 1, 31)
        rental.action_confirm_rental()
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()

        rental2 = self._create_test_rental(self.employee, override_vals={'amount': 12000, 'date_start': date(2025, 2, 1)})
        rental2.valid_up_to_date = date(2025, 2, 28)
        rental2.action_confirm_rental()
        payslip2 = self._generate_payslip(date(2025, 2, 1), date(2025, 2, 28))
        payslip2.action_payslip_done()

        ir56b = self._prepare_test_ir56b()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56b'),
            ('res_id', '=', ir56b.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '20400')
        self.assertEqual(xml_root.find(".//TotalIncome").text, '20400')
        self.assertEqual(xml_root.find(".//RentPaidEe1").text, '32000')  # 8000 in jan, 12000 in feb, 12000 in march
        self.assertEqual(xml_root.find(".//RentRefund1").text, '20000')  # 8000 in jan, 12000 in feb (no payslip in march)

    @freeze_time('2025-01-31')
    def test_ird56b_direct_payment(self):
        rental = self._create_test_rental(self.version.employee_id)
        rental.lease_type = 'direct_payment'
        rental.action_confirm_rental()
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        ir56b = self._prepare_test_ir56b()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56b'),
            ('res_id', '=', ir56b.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '20200')
        self.assertEqual(xml_root.find(".//TotalIncome").text, '20200')
        self.assertEqual(xml_root.find(".//RentPaidEr1").text, '8000')

    @freeze_time('2025-01-31')
    def test_ird56b_co_payment(self):
        rental = self._create_test_rental(self.version.employee_id)
        rental.lease_type = 'co_payment'
        rental.co_pay_amount = 2000
        rental.action_confirm_rental()
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        ir56b = self._prepare_test_ir56b()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56b'),
            ('res_id', '=', ir56b.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '20200')
        self.assertEqual(xml_root.find(".//TotalIncome").text, '20200')
        self.assertEqual(xml_root.find(".//RentPaidEr1").text, '8000')
        self.assertEqual(xml_root.find(".//RentPaidErByEe1").text, '2000')

    @freeze_time('2025-01-31')
    def test_ird56b_housing_allowance(self):
        self.version._set_property_input_value('HA', 8000)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        ir56b = self._prepare_test_ir56b()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56b'),
            ('res_id', '=', ir56b.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '28200')
        self.assertEqual(xml_root.find(".//TotalIncome").text, '28200')

    def _prepare_test_ir56e(self):
        ir56e = self.env['l10n_hk.ir56e'].create({
            'name_of_signer': 'Marc Admin',
            'designation_of_signer': 'Mr.',
            'submission_date': date(2023, 2, 1),  # Our test employee started on Jan. 2023
        })
        ir56e.action_generate_declarations()
        ir56e.action_generate_xml()
        return ir56e

    @freeze_time('2025-01-31')
    def test_ir56e_reimbursement(self):
        rental = self._create_test_rental(self.version.employee_id)
        rental.action_confirm_rental()
        ir56e = self._prepare_test_ir56e()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56e'),
            ('res_id', '=', ir56e.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '12000')
        self.assertEqual(xml_root.find(".//MR_FIXED_INCOME").text, '12000')
        self.assertEqual(xml_root.find(".//MR_ALLOWANCE").text, '200')
        self.assertEqual(xml_root.find(".//RentPaidEe1").text, '8000')
        self.assertEqual(xml_root.find(".//RentRefund1").text, '8000')

    @freeze_time('2025-01-31')
    def test_ir56e_direct_payment(self):
        rental = self._create_test_rental(self.version.employee_id)
        rental.lease_type = 'direct_payment'
        rental.action_confirm_rental()
        ir56e = self._prepare_test_ir56e()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56e'),
            ('res_id', '=', ir56e.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '20000')
        self.assertEqual(xml_root.find(".//MR_FIXED_INCOME").text, '20000')
        self.assertEqual(xml_root.find(".//MR_ALLOWANCE").text, '200')
        self.assertEqual(xml_root.find(".//RentPaidEr1").text, '8000')

    @freeze_time('2025-01-31')
    def test_ir56e_co_payment(self):
        rental = self._create_test_rental(self.version.employee_id)
        rental.lease_type = 'co_payment'
        rental.co_pay_amount = 2000
        rental.action_confirm_rental()
        ir56e = self._prepare_test_ir56e()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56e'),
            ('res_id', '=', ir56e.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '20000')
        self.assertEqual(xml_root.find(".//MR_FIXED_INCOME").text, '20000')
        self.assertEqual(xml_root.find(".//MR_ALLOWANCE").text, '200')
        self.assertEqual(xml_root.find(".//RentPaidEr1").text, '8000')
        self.assertEqual(xml_root.find(".//RentPaidErByEe1").text, '2000')

    @freeze_time('2025-01-31')
    def test_ir56e_housing_allowance(self):
        self.version._set_property_input_value('HA', 8000)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        ir56e = self._prepare_test_ir56e()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56e'),
            ('res_id', '=', ir56e.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '20000')
        self.assertEqual(xml_root.find(".//MR_FIXED_INCOME").text, '20000')
        self.assertEqual(xml_root.find(".//MR_ALLOWANCE").text, '8200')

    def _prepare_test_ir56f(self):
        ir56f = self.env['l10n_hk.ir56f'].create({
            'name_of_signer': 'Marc Admin',
            'designation_of_signer': 'Mr.',
        })
        ir56f.action_generate_declarations()
        ir56f.action_generate_xml()
        return ir56f

    @freeze_time('2025-01-31')
    def test_ir56f_reimbursement(self):
        rental = self._create_test_rental(self.version.employee_id)
        rental.action_confirm_rental()
        rental.valid_up_to_date = date(2025, 1, 31)
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 2, 28),
            'departure_reason_id': self.env.ref('hr.departure_resigned').id,
            'l10n_hk_leaving_hk': False,
        }])
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        ir56f = self._prepare_test_ir56f()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56f'),
            ('res_id', '=', ir56f.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '12200')
        self.assertEqual(xml_root.find(".//TotalIncome").text, '12200')
        self.assertEqual(xml_root.find(".//RentPaidEe1").text, '16000')
        self.assertEqual(xml_root.find(".//RentRefund1").text, '8000')

    @freeze_time('2025-01-31')
    def test_ir56f_direct_payment(self):
        rental = self._create_test_rental(self.version.employee_id)
        rental.lease_type = 'direct_payment'
        rental.action_confirm_rental()
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 2, 28),
            'departure_reason_id': self.env.ref('hr.departure_resigned').id,
            'l10n_hk_leaving_hk': False,
        }])
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        ir56f = self._prepare_test_ir56f()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56f'),
            ('res_id', '=', ir56f.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '20200')
        self.assertEqual(xml_root.find(".//TotalIncome").text, '20200')
        self.assertEqual(xml_root.find(".//RentPaidEr1").text, '8000')

    @freeze_time('2025-01-31')
    def test_ir56f_co_payment(self):
        rental = self._create_test_rental(self.version.employee_id)
        rental.lease_type = 'co_payment'
        rental.co_pay_amount = 2000
        rental.action_confirm_rental()
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 2, 28),
            'departure_reason_id': self.env.ref('hr.departure_resigned').id,
            'l10n_hk_leaving_hk': False,
        }])
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        ir56f = self._prepare_test_ir56f()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56f'),
            ('res_id', '=', ir56f.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '20200')
        self.assertEqual(xml_root.find(".//TotalIncome").text, '20200')
        self.assertEqual(xml_root.find(".//RentPaidEr1").text, '8000')
        self.assertEqual(xml_root.find(".//RentPaidErByEe1").text, '2000')

    @freeze_time('2025-01-31')
    def test_ir56f_housing_allowance(self):
        self.version._set_property_input_value('HA', 8000)
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 2, 28),
            'departure_reason_id': self.env.ref('hr.departure_resigned').id,
            'l10n_hk_leaving_hk': False,
        }])
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        ir56f = self._prepare_test_ir56f()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56f'),
            ('res_id', '=', ir56f.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '28200')
        self.assertEqual(xml_root.find(".//TotalIncome").text, '28200')

    def _prepare_test_ir56g(self):
        ir56g = self.env['l10n_hk.ir56g'].create({
            'name_of_signer': 'Marc Admin',
            'designation_of_signer': 'Mr.',
        })
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
        ir56g.action_generate_declarations()
        ir56g.action_generate_xml()
        return ir56g

    @freeze_time('2025-01-31')
    def test_ir56g_reimbursement(self):
        rental = self._create_test_rental(self.version.employee_id)
        rental.action_confirm_rental()
        rental.valid_up_to_date = date(2025, 1, 31)
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 2, 28),
            'departure_reason_id': self.env.ref('hr.departure_resigned').id,
            'l10n_hk_leaving_hk': True,
        }])
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        ir56g = self._prepare_test_ir56g()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56g'),
            ('res_id', '=', ir56g.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '12200')
        self.assertEqual(xml_root.find(".//TotalIncome").text, '12200')
        self.assertEqual(xml_root.find(".//RentPaidEe1").text, '16000')
        self.assertEqual(xml_root.find(".//RentRefund1").text, '8000')

    @freeze_time('2025-01-31')
    def test_ir56g_direct_payment(self):
        rental = self._create_test_rental(self.version.employee_id)
        rental.lease_type = 'direct_payment'
        rental.action_confirm_rental()
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 2, 28),
            'departure_reason_id': self.env.ref('hr.departure_resigned').id,
            'l10n_hk_leaving_hk': True,
        }])
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        ir56g = self._prepare_test_ir56g()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56g'),
            ('res_id', '=', ir56g.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '20200')
        self.assertEqual(xml_root.find(".//TotalIncome").text, '20200')
        self.assertEqual(xml_root.find(".//RentPaidEr1").text, '8000')

    @freeze_time('2025-01-31')
    def test_ir56g_co_payment(self):
        rental = self._create_test_rental(self.version.employee_id)
        rental.lease_type = 'co_payment'
        rental.co_pay_amount = 2000
        rental.action_confirm_rental()
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 2, 28),
            'departure_reason_id': self.env.ref('hr.departure_resigned').id,
            'l10n_hk_leaving_hk': True,
        }])
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        ir56g = self._prepare_test_ir56g()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56g'),
            ('res_id', '=', ir56g.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '20200')
        self.assertEqual(xml_root.find(".//TotalIncome").text, '20200')
        self.assertEqual(xml_root.find(".//RentPaidEr1").text, '8000')
        self.assertEqual(xml_root.find(".//RentPaidErByEe1").text, '2000')

    @freeze_time('2025-01-31')
    def test_ir56g_housing_allowance(self):
        self.version._set_property_input_value('HA', 8000)
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 2, 28),
            'departure_reason_id': self.env.ref('hr.departure_resigned').id,
            'l10n_hk_leaving_hk': True,
        }])
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.action_payslip_done()
        ir56g = self._prepare_test_ir56g()
        xml_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_hk.ir56g'),
            ('res_id', '=', ir56g.id),
        ])
        xml_root = etree.fromstring(xml_attachment.raw.content)
        self.assertEqual(xml_root.find("TotIncomeBatch").text, '28200')
        self.assertEqual(xml_root.find(".//TotalIncome").text, '28200')
