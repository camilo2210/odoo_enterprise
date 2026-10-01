# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_fiscal_period')
class TestPayrollFiscalPeriod(TestPayrollCommon):
    """The fiscal period a remuneration is declared in is not always its pay period."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        with freeze_time('2025-12-01'):
            cls.employee = cls.create_employee_with_benefits({
                'name': 'Fiscal Period Employee',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
                'wage': 3000.0,
                'niss': '/',
                'private_street': 'Rue du Test 1',
                'private_zip': '1000',
                'private_city': 'Brussels',
            })
            cls.late_employee = cls.create_employee_with_benefits({
                'name': 'Late Payslip Employee',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
                'wage': 2800.0,
                'niss': '/',
                'private_street': 'Rue du Test 2',
                'private_zip': '1000',
                'private_city': 'Brussels',
            })

    def _create_payslip(self, employee, month, year=2026):
        date_from = date(year, month, 1)
        return self.env['hr.payslip'].create({
            'name': f'Payslip {month:02d}/{year} - {employee.name}',
            'employee_id': employee.id,
            'company_id': employee.company_id.id,
            'struct_id': self.structure.id,
            'version_id': employee.version_id.id,
            'date_from': date_from,
            'date_to': date_from + relativedelta(months=1, day=1, days=-1),
        })

    def _validate_payslip(self, employee, month, on_date, year=2026):
        with freeze_time(on_date):
            payslip = self._create_payslip(employee, month, year=year)
            payslip.compute_sheet()
            payslip.action_payslip_done()
        return payslip

    def _create_274(self, month, year=2026):
        return self.env['l10n_be.274_xx'].create({
            'year': year,
            'month': str(month),
            'company_id': self.employee.company_id.id,
        })

    def _line_domain(self, month, year=2026):
        date_from = date(year, month, 1)
        return self.env['hr.payslip']._l10n_be_get_fiscal_line_domain(
            date_from, date_from + relativedelta(months=1, day=1, days=-1))

    # ------------------------------------------------------------------
    # Attachment of the amounts
    # ------------------------------------------------------------------

    def test_fiscal_date_defaults_to_the_pay_period(self):
        payslip = self._validate_payslip(self.employee, 1, '2026-01-28')
        self.assertEqual(
            payslip.l10n_be_fiscal_date, date(2026, 1, 31),
            "A payslip confirmed within its own pay period is fiscally attached to it")

    def test_benefits_in_kind_are_attached_to_the_pay_period(self):
        payslip = self._validate_payslip(self.employee, 1, '2026-01-28')
        benefits = payslip.line_ids.filtered(lambda line: line.code in ['ATN.INT', 'ATN.MOB'])
        self.assertTrue(benefits, "The employee has an internet and a mobile benefit in kind")
        self.assertTrue(
            all(benefits.mapped('l10n_be_follow_pay_period')),
            "Benefits in kind must stay attached to the pay period")
        self.assertFalse(
            payslip.line_ids.filtered(lambda line: line.code == 'GROSS').l10n_be_follow_pay_period,
            "Any other remuneration follows the fiscal period of its payslip")

    def test_attachment_can_be_pinned_by_hand(self):
        payslip = self._create_payslip(self.employee, 1)
        payslip.compute_sheet()
        gross = payslip.line_ids.filtered(lambda line: line.code == 'GROSS')
        gross.l10n_be_follow_pay_period = True
        payslip.action_payslip_done()
        self.assertTrue(
            gross.l10n_be_follow_pay_period,
            "A remuneration pinned to the pay period by hand keeps its attachment")

    # ------------------------------------------------------------------
    # A declaration never hides a payslip from another declaration
    # ------------------------------------------------------------------

    def test_a_filed_274_does_not_hide_the_payslip_from_the_annual_recaps(self):
        """Each declaration stream sees every payslip of its own period.

        The 274.XX is the monthly withholding tax declaration, the 273S is cumulative over the
        year and the 281.XX is the annual recapitulation: they all report the same payslip.
        """
        payslip = self._validate_payslip(self.employee, 1, '2026-01-28')
        sheet = self._create_274(1)
        self.assertIn(payslip, sheet._get_valid_payslips())
        sheet.action_generate_xml()
        self.assertEqual(sheet.state, 'ready')

        self.assertIn(
            payslip, sheet._get_valid_payslips(),
            "Regenerating a declaration must yield the same content")

        declaration_281 = self.env['l10n_be.281_xx'].create({
            'year': '2026',
            'company_id': self.employee.company_id.id,
        })
        report_281_10 = declaration_281.l10n_be_281_10_ids[:1]
        report_281_10.action_generate_declarations()
        self.assertIn(
            self.employee, report_281_10.line_ids.employee_id,
            "The 281.10 of the year must still report a payslip already declared on a 274.XX")

    def _file_274(self, month, reference, year=2026):
        sheet = self._create_274(month, year=year)
        sheet.action_generate_xml()
        sheet.belcotax_reference = reference
        sheet.action_mark_done()
        return sheet

    def test_a_modification_leaves_out_what_the_original_declared(self):
        """A corrective 274.XX only declares what its predecessors left out of the period."""
        january = self._validate_payslip(self.employee, 1, '2026-01-28')
        original = self._create_274(1)
        self.assertIn(january, original._get_valid_payslips())
        original.action_generate_xml()
        self.assertEqual(original.state, 'ready')
        with self.assertRaises(UserError, msg="A declaration is filed against a Belcotax reference"):
            original.action_mark_done()
        original.belcotax_reference = '274-2026-01'
        original.action_mark_done()
        self.assertEqual(original.state, 'done')
        self.assertIn(january, original.payslip_ids)

        modification = self.env['l10n_be.274_xx'].create({
            'year': 2026,
            'month': '1',
            'company_id': self.employee.company_id.id,
            'declaration_type': 'modification',
            'parent_id': original.id,
        })
        self.assertNotIn(
            january, modification._get_valid_payslips(),
            "A payslip the original already declared must stay out of the modification")

        late = self._validate_payslip(self.late_employee, 1, '2026-03-10')
        self.assertIn(
            late, modification._get_valid_payslips(),
            "A payslip that arrived after the original was filed still belongs to the modification")

    def test_a_filed_declaration_asks_for_a_correction(self):
        self._validate_payslip(self.employee, 1, '2026-01-28')
        original = self._file_274(1, '274-2026-01')
        self.assertFalse(original.is_correction_needed)

        self._validate_payslip(self.late_employee, 1, '2026-03-10')
        self.assertTrue(
            original.is_correction_needed,
            "A payslip landing on an already filed period makes that declaration stale")

    # ------------------------------------------------------------------
    # Late payslips
    # ------------------------------------------------------------------

    def test_late_payslip_is_deferred_to_the_confirmation_period(self):
        self._validate_payslip(self.employee, 1, '2026-01-28')
        self._create_274(1).action_generate_xml()

        late = self._validate_payslip(self.late_employee, 1, '2026-03-10')
        self.assertEqual(
            late.l10n_be_fiscal_date, date(2026, 3, 10),
            "January is already declared, so the remuneration is attached to March")

        self.assertIn(late, self._create_274(3)._get_valid_payslips())

        january = late._get_line_values(['GROSS', 'ATN.INT'], extra_domain=self._line_domain(1))
        march = late._get_line_values(['GROSS', 'ATN.INT'], extra_domain=self._line_domain(3))
        self.assertEqual(january['GROSS'][late.id]['total'], 0.0)
        self.assertNotEqual(march['GROSS'][late.id]['total'], 0.0)
        self.assertNotEqual(
            january['ATN.INT'][late.id]['total'], 0.0,
            "The benefit in kind stays declared in the pay period")
        self.assertEqual(march['ATN.INT'][late.id]['total'], 0.0)

    def test_payslip_of_an_undeclared_period_keeps_its_pay_period(self):
        late = self._validate_payslip(self.late_employee, 1, '2026-03-10')
        self.assertEqual(
            late.l10n_be_fiscal_date, date(2026, 1, 31),
            "Nothing was declared for January yet, so the remuneration stays attached to it")

    # ------------------------------------------------------------------
    # Corrections
    # ------------------------------------------------------------------

    def _correct(self, payslip, on_date):
        with freeze_time(on_date):
            refunds = payslip._action_refund_payslips()
            corrections = payslip._action_correct_payslips()
            corrections.action_payslip_done()
        return refunds, corrections

    def test_correction_increase_is_declared_in_the_fiscal_period(self):
        january = self._validate_payslip(self.employee, 1, '2026-01-28')
        self._create_274(1).action_generate_xml()

        self.employee.version_id.wage = 3500.0
        refunds, corrections = self._correct(january, '2026-03-10')

        self.assertEqual(
            corrections.l10n_be_fiscal_date, date(2026, 3, 10),
            "An increase is declared in the fiscal period, as it is paid now")
        self.assertEqual(
            refunds.l10n_be_fiscal_date, corrections.l10n_be_fiscal_date,
            "The refund follows the correction, so that both halves land in the same declaration")
        self.assertIn(corrections, self._create_274(3)._get_valid_payslips())

    def test_correction_decrease_is_declared_in_the_pay_period(self):
        january = self._validate_payslip(self.employee, 1, '2026-01-28')
        self._create_274(1).action_generate_xml()

        self.employee.version_id.wage = 2600.0
        refunds, corrections = self._correct(january, '2026-03-10')

        self.assertEqual(
            corrections.l10n_be_fiscal_date, date(2026, 1, 31),
            "A decrease goes back to the pay period, a negative amount would be refused")
        self.assertEqual(refunds.l10n_be_fiscal_date, corrections.l10n_be_fiscal_date)

        march = corrections._get_line_values(['GROSS'], extra_domain=self._line_domain(3))
        self.assertEqual(march['GROSS'][corrections.id]['total'], 0.0)
        january_values = corrections._get_line_values(['GROSS'], extra_domain=self._line_domain(1))
        self.assertNotEqual(january_values['GROSS'][corrections.id]['total'], 0.0)

    def test_a_correction_never_rewrites_the_attachment_of_its_lines(self):
        """The period of a correction is a property of the payslip, not of its lines.

        A line keeps the attachment its salary rule gives it, so a benefit in kind stays
        declared in the pay period whichever period the payslip itself ends up in.
        """
        january = self._validate_payslip(self.employee, 1, '2026-01-28')
        self._create_274(1).action_generate_xml()

        self.employee.version_id.electricity_amount = 100.0
        _, corrections = self._correct(january, '2026-03-10')

        self.assertNotEqual(
            corrections._get_line_values(['ATN_ELEC'])['ATN_ELEC'][corrections.id]['total'], 0.0,
            "The correction brings a new benefit in kind")
        self.assertFalse(
            corrections.line_ids.filtered(lambda line: line.code == 'GROSS').l10n_be_follow_pay_period,
            "A correction leaves the attachment of a taxable salary line alone")
        self.assertTrue(
            corrections.line_ids.filtered(lambda line: line.code == 'ATN_ELEC').l10n_be_follow_pay_period,
            "A benefit in kind keeps the attachment of its salary rule")

        january_values = corrections._get_line_values(['ATN_ELEC'], extra_domain=self._line_domain(1))
        self.assertNotEqual(
            january_values['ATN_ELEC'][corrections.id]['total'], 0.0,
            "The benefit in kind is declared in the pay period it belongs to")

    def test_a_deferred_payslip_declares_its_benefits_in_kind_in_its_pay_period(self):
        """Raise a benefit in kind, correct months later: the benefit stays in the pay period.

        The declaration rebuilds its taxable base from the amounts it is made of, so the benefit
        follows its own attachment instead of riding along inside the taxable salary aggregate.
        """
        january = self._validate_payslip(self.employee, 1, '2026-01-28')
        self._file_274(1, '274-2026-01')

        self.employee.version_id.electricity_amount = 100.0
        _, corrections = self._correct(january, '2026-03-10')
        self.assertEqual(corrections.l10n_be_fiscal_date, date(2026, 3, 10))

        base = self.env['hr.payslip']._get_gross_wage_base_categories()['GROSS']
        january_base = corrections._l10n_be_get_declaration_base(base, date(2026, 1, 1), date(2026, 1, 31))
        march_base = corrections._l10n_be_get_declaration_base(base, date(2026, 3, 1), date(2026, 3, 31))
        gross = corrections._get_line_values(['GROSS'])['GROSS'][corrections.id]['total']

        benefits = corrections.line_ids.filtered('l10n_be_follow_pay_period')
        self.assertAlmostEqual(
            january_base[corrections.id], sum(benefits.mapped('total')), 2,
            "January declares exactly the amounts attached to the pay period")
        self.assertAlmostEqual(
            january_base[corrections.id] + march_base[corrections.id], gross, 2,
            "The taxable salary is split across the two periods, nothing lost nor counted twice")

    def test_a_declaration_base_matches_the_aggregate_it_replaces(self):
        """With nothing deferred, rebuilding the base gives the aggregate line to the cent."""
        payslip = self._validate_payslip(self.employee, 1, '2026-01-28')
        base = self.env['hr.payslip']._get_gross_wage_base_categories()['GROSS']
        rebuilt = payslip._l10n_be_get_declaration_base(base, date(2026, 1, 1), date(2026, 1, 31))
        gross = payslip._get_line_values(['GROSS'])['GROSS'][payslip.id]['total']
        self.assertAlmostEqual(rebuilt[payslip.id], gross, 2)

    def test_the_fiscal_period_still_declares_what_the_modification_left_out(self):
        """A modification declares the pay period half; the fiscal period keeps the other half."""
        january = self._validate_payslip(self.employee, 1, '2026-01-28')
        original = self._file_274(1, '274-2026-01')

        self.employee.version_id.electricity_amount = 100.0
        refunds, corrections = self._correct(january, '2026-09-10')
        self.assertEqual(corrections.l10n_be_fiscal_date, date(2026, 9, 10))

        modification = self.env['l10n_be.274_xx'].create({
            'year': 2026, 'month': '1',
            'company_id': self.employee.company_id.id,
            'declaration_type': 'modification',
            'parent_id': original.id,
        })
        self.assertIn(corrections, modification._get_valid_payslips(),
                      "The pay period half of the correction belongs to the January modification")
        modification.action_generate_xml()
        modification.belcotax_reference = '274-2026-01-M1'
        modification.action_mark_done()

        september = self._create_274(9)
        self.assertIn(corrections, september._get_valid_payslips(),
                      "The fiscal period half of the correction belongs to September")
        self.assertIn(refunds, september._get_valid_payslips())

        base = self.env['hr.payslip']._get_gross_wage_base_categories()['GROSS']
        september_base = (corrections | refunds)._l10n_be_get_declaration_base(
            base, date(2026, 9, 1), date(2026, 9, 30))
        self.assertNotEqual(sum(september_base.values()), 0.0,
                            "September declares the taxable delta brought by the correction")

    def test_a_draft_declaration_picks_up_payslips_created_after_it(self):
        """A draft 274.XX must reflect payroll as it stands now, not as it stood when created."""
        january = self._validate_payslip(self.employee, 1, '2026-01-28')
        self._file_274(1, '274-2026-01')

        september = self._create_274(9)
        self.assertFalse(september._get_valid_payslips(), "Nothing is attached to September yet")
        september.line_ids  # force the stored computation while the period is still empty

        self.employee.version_id.electricity_amount = 100.0
        _, corrections = self._correct(january, '2026-09-10')
        self.assertEqual(corrections.l10n_be_fiscal_date, date(2026, 9, 10))

        september.action_generate_xml()
        self.assertIn(corrections, september.payslip_ids,
                      "Generating a declaration must declare payroll as it stands now")

    def test_a_fiscal_period_without_a_declaration_is_flagged(self):
        """The check that replaces a "period to report" flag: amounts attached to a period that
        no 274.XX declares yet, asked of the payslips rather than stored on them."""
        warning = self.env['hr.payroll.warning']
        company = self.employee.company_id
        september = (date(2026, 9, 1), date(2026, 9, 30))

        january = self._validate_payslip(self.employee, 1, '2026-01-28')
        self._file_274(1, '274-2026-01')
        self.assertFalse(
            warning._l10n_be_is_period_undeclared(company, *september),
            "Nothing is attached to September yet")

        self.employee.version_id.electricity_amount = 100.0
        _, corrections = self._correct(january, '2026-09-10')
        self.assertEqual(corrections.l10n_be_fiscal_date, date(2026, 9, 10))
        self.assertTrue(
            warning._l10n_be_is_period_undeclared(company, *september),
            "The correction left amounts attached to September and no declaration covers it")

        self._file_274(9, '274-2026-09')
        self.assertFalse(
            warning._l10n_be_is_period_undeclared(company, *september),
            "Once September is declared there is nothing left to flag")

    def test_a_refund_on_its_own_stays_in_the_period_it_reverses(self):
        """A revert with no correction is a pure decrease: it must not land alone in the fiscal
        period, where it would be declared as a negative amount."""
        january = self._validate_payslip(self.employee, 1, '2026-01-28')
        self._file_274(1, '274-2026-01')

        with freeze_time('2026-09-10'):
            refunds = january._action_refund_payslips()

        self.assertEqual(
            refunds.l10n_be_fiscal_date, date(2026, 1, 31),
            "A refund reverses the period it was declared in")
        self.assertNotIn(refunds, self._create_274(9)._get_valid_payslips(),
                         "September must not declare a lone negative")

    def test_a_reversal_mirrors_the_shift_exemption_of_its_origin(self):
        """A reversal reverses what its origin declared, it does not earn an exemption of its own.

        Every hour of a reversal is negated, so assessing its eligibility on its own figures lands
        on the wrong side of the "at least a third of the hours" comparison.
        """
        january = self._validate_payslip(self.employee, 1, '2026-01-28')
        sheet = self._create_274(1)

        with freeze_time('2026-09-10'):
            refunds = january._action_refund_payslips()

        origin_eligible, origin_exemption = sheet._get_team_shift_exemption_vals(january)
        refund_eligible, refund_exemption = sheet._get_team_shift_exemption_vals(refunds)
        self.assertEqual(refund_eligible, origin_eligible,
                         "A reversal is eligible exactly when the payslip it reverses was")
        self.assertAlmostEqual(refund_exemption, -origin_exemption, 2,
                               "A reversal reverses the exemption of its origin")
        self.assertEqual(
            sheet._is_team_exemption_eligible(refunds), sheet._is_team_exemption_eligible(january))

    def test_a_rule_policy_decides_the_attachment_of_its_amounts(self):
        """The four policies, resolved per line against the delta the amount brings.

        Outside of a correction nothing was declared for the amount yet, so the delta is the
        amount itself: a virtual correction of zero.
        """
        rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_atn_electricity')
        self.employee.version_id.electricity_amount = 100.0

        def attachment(policy):
            rule.l10n_be_follow_pay_period = policy
            payslip = self._create_payslip(self.employee, 2)
            payslip.compute_sheet()
            line = payslip.line_ids.filtered(lambda line: line.code == 'ATN_ELEC')
            self.assertTrue(line and line.total > 0)
            return line.l10n_be_follow_pay_period

        self.assertTrue(attachment('always'))
        self.assertFalse(attachment('never'))
        self.assertTrue(attachment('positive'), "A positive amount is a positive delta against nothing")
        self.assertFalse(attachment('negative'))

    def test_a_reversal_takes_the_attachment_of_its_correction(self):
        """Both halves of a delta land in the same declaration.

        A reversal is computed before its correction exists, so it cannot resolve a delta of its
        own; it takes the one its counterpart resolved.
        """
        self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_atn_electricity').l10n_be_follow_pay_period = 'negative'
        self.employee.version_id.electricity_amount = 100.0
        january = self._validate_payslip(self.employee, 1, '2026-01-28')
        self._file_274(1, '274-2026-01')

        self.employee.version_id.electricity_amount = 40.0
        refunds, corrections = self._correct(january, '2026-09-10')

        correction_line = corrections.line_ids.filtered(lambda line: line.code == 'ATN_ELEC')
        refund_line = refunds.line_ids.filtered(lambda line: line.code == 'ATN_ELEC')
        self.assertTrue(
            correction_line.l10n_be_follow_pay_period,
            "The benefit went down, so its delta is negative and it goes back to the pay period")
        self.assertEqual(
            refund_line.l10n_be_follow_pay_period, correction_line.l10n_be_follow_pay_period,
            "The reversal follows the attachment of the correction replacing it")
