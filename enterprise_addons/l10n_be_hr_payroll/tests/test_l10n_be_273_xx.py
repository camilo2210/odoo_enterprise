from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nBe273Xx(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_john.version_id.ip_wage_rate = 0.25
        cls.employee_john.niss = '03062411377'

    def _get_warning(self, warning_name):
        dashboard_data = self.env['hr.payroll.warning'].get_payroll_dashboard_data()
        dashboard_warnings = self.env['hr.payroll.warning'].get_payroll_dashboard_warning_cards(dashboard_data['warning_ids'])
        return next((warning for warning in dashboard_warnings if warning['name'] == warning_name), None)

    def _create_paid_payslip(self, employee, date_from, date_to):
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            'date_from': date_from,
            'date_to': date_to,
            'company_id': self.belgian_company.id,
        })
        payslip.compute_sheet()
        payslip.action_payslip_done()
        payslip.action_payslip_paid()
        return payslip

    def _create_profit_sharing_payslip(self, employee, date_from, date_to, amount=200.0):
        ps_struct = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_profit_sharing_bonus')
        payslip = self.env['hr.payslip'].create({
            'name': f'{employee.name}\'s Profit Sharing ({date_from})',
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            'date_from': date_from,
            'date_to': date_to,
            'company_id': self.belgian_company.id,
            'struct_id': ps_struct.id,
        })
        payslip._set_input_value('PROFITSHARINGHIGH', amount)
        payslip.compute_sheet()
        payslip.action_payslip_done()
        payslip.action_payslip_paid()
        return payslip

    def _create_273_xx_report(self, year=2026, month='1', belcotax_reference=None):
        vals = {'year': year, 'month': month}
        if belcotax_reference:
            vals['belcotax_reference'] = belcotax_reference
        return self.env['l10n_be.273_xx'].create(vals)

    def test_report_is_not_up_to_date_warning(self):
        '''
        Test that when a payslip is modified after the 273.XX report generation, a warning is raised on the dashboard
        and that the warning is removed when the report is up to date again.
        '''
        employee = self.employee_john
        current_year = date.today().year
        warning_name = '273.XX report is not up to date due to changes in payslips'

        # Step 1: Create a January payslip and generate its 273.XX report, then cancel the payslip
        payslip_jan = self._create_paid_payslip(employee, date(current_year, 1, 1), date(current_year, 1, 31))
        l10n_be_273_xx_jan = self._create_273_xx_report(year=current_year, month='1', belcotax_reference=f'273XX-{current_year}-01')
        l10n_be_273_xx_jan.action_populate()
        l10n_be_273_xx_jan.action_generate()
        payslip_jan.action_payslip_cancel()

        # Step 2: Do the same for February — create payslip, generate report, then cancel the payslip
        payslip_feb = self._create_profit_sharing_payslip(employee, date(current_year, 2, 1), date(current_year, 2, 28))
        l10n_be_273_xx_feb = self._create_273_xx_report(year=current_year, month='2', belcotax_reference=f'273XX-{current_year}-02')
        l10n_be_273_xx_feb.action_populate()
        l10n_be_273_xx_feb.action_generate()
        payslip_feb.action_payslip_cancel()

        # Step 3: Both reports should be flagged as needing correction (2 warnings)
        warning = self._get_warning(warning_name)
        self.assertTrue(warning)
        self.assertEqual(warning['count'], 2)
        self.assertIn(l10n_be_273_xx_jan, warning['warning_records'])
        self.assertIn(l10n_be_273_xx_feb, warning['warning_records'])

        # Step 4: Fix January — re-confirm the payslip and regenerate the report
        payslip_jan.action_payslip_draft()
        payslip_jan.action_payslip_done()
        l10n_be_273_xx_jan.action_set_to_draft()
        l10n_be_273_xx_jan.action_populate()
        l10n_be_273_xx_jan.action_generate()
        # Only the February report should still be flagged (1 warning)
        warning = self._get_warning(warning_name)
        self.assertTrue(warning)
        self.assertEqual(warning['count'], 1)
        self.assertIn(l10n_be_273_xx_feb, warning['warning_records'])
        self.assertNotIn(l10n_be_273_xx_jan, warning['warning_records'])

        # Step 5: Fix February — re-confirm the payslip and regenerate the report
        payslip_feb.action_payslip_draft()
        payslip_feb.action_payslip_done()
        l10n_be_273_xx_feb.action_set_to_draft()
        l10n_be_273_xx_feb.action_populate()
        l10n_be_273_xx_feb.action_generate()
        # No more warnings — both reports are up to date
        self.assertFalse(self._get_warning(warning_name))

    def test_unreported_last_year_warning(self):
        '''
        Test that when payslips from last year are not included in any finalized 273.XX report,
        a warning is raised on the dashboard with the correct action pointing to the December report.
        The warning should disappear once all payslips are covered by a finalized report.
        '''
        employee = self.employee_john
        last_year = date.today().year - 1
        warning_name = '273.XX report for last year is incomplete due to missing payslips'

        # Step 1: Create payslips in November and December of last year
        self._create_paid_payslip(employee, date(last_year, 11, 1), date(last_year, 11, 30))
        self._create_profit_sharing_payslip(employee, date(last_year, 12, 1), date(last_year, 12, 31))

        # Step 2: Verify the warning exists and has the correct action (no December report yet => context with defaults)
        warning = self._get_warning(warning_name)
        self.assertTrue(warning, "Warning should exist when last year payslips are unreported")
        self.assertEqual(warning['warning_records'], self.belgian_company)
        action = warning.get('button_action', {})
        self.assertEqual(action.get('res_model'), 'l10n_be.273_xx')
        # No December report exists yet, so the action should have default context
        self.assertEqual(action.get('context', {}).get('default_year'), last_year)
        self.assertEqual(action.get('context', {}).get('default_month'), '12')

        # Step 3: Create and finalize a report covering only November — warning should persist
        report_nov = self.env['l10n_be.273_xx'].create({
            'year': last_year,
            'month': '11',
            'belcotax_reference': f'273XX-{last_year}-11',
        })
        report_nov.action_populate()
        report_nov.action_generate()
        report_nov.action_mark_as_done()

        warning = self._get_warning(warning_name)
        self.assertTrue(warning, "Warning should still exist when December payslip is unreported")

        # Step 4: Create and finalize a December report — the action should now point to this report
        report_dec = self.env['l10n_be.273_xx'].create({
            'year': last_year,
            'month': '12',
            'belcotax_reference': f'273XX-{last_year}-12',
        })
        report_dec.action_populate()
        report_dec.action_generate()
        report_dec.action_mark_as_done()

        # Step 5: All payslips are now covered by finalized reports — warning should disappear
        warning = self._get_warning(warning_name)
        self.assertFalse(warning, "Warning should not exist when all last year payslips are in finalized reports")

    # =============================================
    # UserError tests
    # =============================================

    def test_create_report_non_belgian_company(self):
        '''Creating a 273.XX report from a non-Belgian company should raise a UserError.'''
        non_be_company = self.env['res.company'].create({
            'name': 'Non-Belgian Company',
            'country_id': self.env.ref('base.us').id,
        })
        with self.assertRaises(UserError) as e:
            self.env['l10n_be.273_xx'].with_company(non_be_company).create({
                'year': 2026,
                'month': '1',
            })
        self.assertIn('This feature seems to be as exclusive as Belgian chocolates. You must be logged in to a Belgian company to use it.', str(e.exception))

    def test_populate_no_unreported_payslips(self):
        '''action_populate should raise a UserError when there are no payslips for the period.'''
        report = self._create_273_xx_report(year=2030, month='1')
        with self.assertRaises(UserError) as e:
            report.action_populate()
        self.assertIn('No unreported payslips were found for the selected period.', str(e.exception))

    def test_populate_all_payslips_already_finalized(self):
        '''action_populate should raise when all payslips are already linked to finalized reports.'''
        employee = self.employee_john
        self._create_paid_payslip(employee, date(2026, 3, 1), date(2026, 3, 31))

        # Create and finalize a first report covering March
        report_1 = self._create_273_xx_report(year=2026, month='3', belcotax_reference='273XX-2026-03')
        report_1.action_populate()
        report_1.action_generate()
        report_1.action_mark_as_done()

        # A second report for the same period should find no unreported payslips
        report_2 = self._create_273_xx_report(year=2026, month='3')
        with self.assertRaises(UserError) as e:
            report_2.action_populate()
        self.assertIn('No unreported payslips were found for the selected period.', str(e.exception))

    def test_set_to_draft_wrong_state(self):
        '''action_set_to_draft should raise a UserError when the report is not in "ready" state.'''
        employee = self.employee_john

        self._create_paid_payslip(employee, date(2026, 4, 1), date(2026, 4, 30))

        # From draft state
        report = self._create_273_xx_report(year=2026, month='4', belcotax_reference='273XX-2026-04')
        with self.assertRaises(UserError) as e_draft:
            report.action_set_to_draft()
        self.assertIn('Only reports in "Ready" state can be set to draft.', str(e_draft.exception))

        # From done state
        report.action_populate()
        report.action_generate()
        report.action_mark_as_done()
        with self.assertRaises(UserError) as e_done:
            report.action_set_to_draft()
        self.assertIn('Only reports in "Ready" state can be set to draft.', str(e_done.exception))

    def test_mark_as_done_wrong_state(self):
        '''action_mark_as_done should raise a UserError when the report is not in "ready" state.'''
        report = self._create_273_xx_report(year=2026, month='5', belcotax_reference='273XX-2026-05')
        # From draft state
        with self.assertRaises(UserError) as e:
            report.action_mark_as_done()
        self.assertIn('Only reports in "Ready" state can be marked as done.', str(e.exception))

    def test_mark_as_done_no_belcotax_reference(self):
        '''action_mark_as_done should raise a UserError when no belcotax reference is set.'''
        employee = self.employee_john

        self._create_paid_payslip(employee, date(2026, 5, 1), date(2026, 5, 31))

        report = self._create_273_xx_report(year=2026, month='5')
        report.action_populate()
        report.action_generate()
        # No belcotax_reference set
        with self.assertRaises(UserError) as e:
            report.action_mark_as_done()
        self.assertIn('The 273.XX sheet must have a Belcotax reference to be completed.', str(e.exception))

    def test_correct_wrong_state(self):
        '''action_correct should raise a UserError when the report is not in "done" state.'''
        employee = self.employee_john

        self._create_paid_payslip(employee, date(2026, 6, 1), date(2026, 6, 30))

        report = self._create_273_xx_report(year=2026, month='6', belcotax_reference='273XX-2026-06')
        report.action_populate()
        report.action_generate()
        # Report is in "ready" state, not "done"
        with self.assertRaises(UserError) as e:
            report.action_correct()
        self.assertIn('Only reports in "Done" state can be corrected.', str(e.exception))

    def test_correct_no_belcotax_reference(self):
        '''action_correct should raise a UserError when no belcotax reference is set.'''
        employee = self.employee_john

        self._create_paid_payslip(employee, date(2026, 7, 1), date(2026, 7, 31))

        report = self._create_273_xx_report(year=2026, month='7', belcotax_reference='273XX-2026-07')
        report.action_populate()
        report.action_generate()
        report.action_mark_as_done()
        # Remove the reference, then try to correct
        report.belcotax_reference = False
        with self.assertRaises(UserError) as e:
            report.action_correct()
        self.assertIn('The 273.XX sheet must have a Belcotax reference to be corrected.', str(e.exception))

    # =============================================
    # Workflow tests
    # =============================================

    def test_full_lifecycle(self):
        '''Test the happy path: draft → populate → generate (ready) → mark as done.'''
        employee = self.employee_john

        self._create_paid_payslip(employee, date(2026, 8, 1), date(2026, 8, 31))
        self._create_profit_sharing_payslip(employee, date(2026, 8, 1), date(2026, 8, 31))

        report = self._create_273_xx_report(year=2026, month='8', belcotax_reference='273XX-2026-08')
        # Initial state should be draft
        self.assertEqual(report.state, 'draft')

        # Populate and verify payslips are linked
        report.action_populate()
        self.assertTrue(report.line_273S_ids, "IP Lines should be linked after populate")
        self.assertTrue(report.line_273_part_ids, "Participation Lines should be linked after populate")

        # Generate and verify files are created and state is ready
        report.action_generate()
        self.assertEqual(report.state, 'ready')
        self.assertTrue(report.pdf_273s_file, "273S PDF file should be generated")
        self.assertTrue(report.pdf_273_part_file, "273 Part PDF file should be generated")
        self.assertTrue(report.xml_file, "XML file should be generated")

        # Mark as done
        report.action_mark_as_done()
        self.assertEqual(report.state, 'done')

    def test_set_to_draft_clears_files(self):
        '''After generate, setting to draft should clear PDF/XML files and reset state.'''
        employee = self.employee_john

        self._create_paid_payslip(employee, date(2026, 9, 1), date(2026, 9, 30))
        self._create_profit_sharing_payslip(employee, date(2026, 9, 1), date(2026, 9, 30))

        report = self._create_273_xx_report(year=2026, month='9', belcotax_reference='273XX-2026-09')
        report.action_populate()
        report.action_generate()
        self.assertTrue(report.pdf_273s_file)
        self.assertTrue(report.pdf_273_part_file)
        self.assertTrue(report.xml_file)

        report.action_set_to_draft()
        self.assertEqual(report.state, 'draft')
        self.assertFalse(report.pdf_273s_file, "273S PDF file should be cleared after set to draft")
        self.assertFalse(report.pdf_273_part_file, "273 Part PDF file should be cleared after set to draft")
        self.assertFalse(report.xml_file, "XML file should be cleared after set to draft")
        self.assertEqual(report.xml_validation_state, 'normal')

    def test_correction_flow(self):
        '''After marking as done, action_correct should return a correction action with correct defaults.'''
        employee = self.employee_john

        self._create_paid_payslip(employee, date(2026, 10, 1), date(2026, 10, 31))

        report = self._create_273_xx_report(year=2026, month='10', belcotax_reference='273XX-2026-10')
        report.action_populate()
        report.action_generate()
        report.action_mark_as_done()
        report.is_correction_needed = True

        action = report.action_correct()
        # Verify the correction action has the right defaults
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'l10n_be.273_xx')
        ctx = action['context']
        self.assertEqual(ctx['default_year'], 2026)
        self.assertEqual(ctx['default_month'], '10')
        self.assertEqual(ctx['default_type'], 'correction')
        self.assertEqual(ctx['default_origin_id'], report.id)
        # is_correction_needed should be reset
        self.assertFalse(report.is_correction_needed)

    def test_cancel_clears_data(self):
        '''action_cancel should clear files, unlink payslips, and set state to cancelled.'''
        employee = self.employee_john

        self._create_paid_payslip(employee, date(2026, 11, 1), date(2026, 11, 30))
        self._create_profit_sharing_payslip(employee, date(2026, 11, 1), date(2026, 11, 30))

        report = self._create_273_xx_report(year=2026, month='11', belcotax_reference='273XX-2026-11')
        report.action_populate()
        report.action_generate()
        self.assertTrue(report.line_273S_ids)
        self.assertTrue(report.line_273_part_ids)

        report.action_cancel()
        self.assertEqual(report.state, 'cancelled')
        self.assertFalse(report.line_273S_ids, "IP Lines should be unlinked after cancel")
        self.assertFalse(report.line_273_part_ids, "Participation Lines should be unlinked after cancel")
        self.assertFalse(report.pdf_273s_file, "273S PDF file should be cleared after cancel")
        self.assertFalse(report.pdf_273_part_file, "273 Part PDF file should be cleared after cancel")
        self.assertFalse(report.xml_file, "XML file should be cleared after cancel")

    def test_cancel_with_correction(self):
        '''action_cancel should raise a UserError if a non-cancelled correction exists, and succeed if the correction is cancelled.'''
        employee = self.employee_john

        self._create_paid_payslip(employee, date(2026, 12, 1), date(2026, 12, 31))

        report = self._create_273_xx_report(year=2026, month='12', belcotax_reference='273XX-2026-12')
        report.action_populate()
        report.action_generate()
        report.action_mark_as_done()
        report.is_correction_needed = True

        correction_action = report.action_correct()
        correction = self.env['l10n_be.273_xx'].with_context(**correction_action['context']).create({
            'year': correction_action['context']['default_year'],
            'month': correction_action['context']['default_month'],
            'origin_id': correction_action['context']['default_origin_id'],
            'type': 'correction',
        })

        with self.assertRaises(UserError) as e:
            report.action_cancel()
        self.assertIn('You cannot cancel a report that has already been corrected. Please cancel the correction report first.', str(e.exception))

        correction.action_cancel()
        report.action_cancel()
        self.assertEqual(report.state, 'cancelled')

    def test_populate_excludes_other_finalized_reports(self):
        '''action_populate should exclude payslips already in other finalized reports but include its own.'''
        employee = self.employee_john

        self._create_paid_payslip(employee, date(2026, 12, 1), date(2026, 12, 31))
        self._create_profit_sharing_payslip(employee, date(2026, 12, 1), date(2026, 12, 31))

        # Create and finalize a first report
        report_1 = self._create_273_xx_report(year=2026, month='12', belcotax_reference='273XX-2026-12')
        report_1.action_populate()
        report_1.action_generate()
        report_1.action_mark_as_done()

        # A second report should not find unreported payslips
        report_2 = self._create_273_xx_report(year=2026, month='12')
        with self.assertRaises(UserError):
            report_2.action_populate()

        # But a correction of report_1 should be able to populate (origin_id exclusion)
        report_1.is_correction_needed = True
        correction_action = report_1.action_correct()
        correction = self.env['l10n_be.273_xx'].with_context(**correction_action['context']).create({
            'year': correction_action['context']['default_year'],
            'month': correction_action['context']['default_month'],
            'origin_id': correction_action['context']['default_origin_id'],
            'type': 'correction',
        })
        # The correction should be able to populate since it excludes origin's payslips
        correction.action_populate()
        self.assertTrue(correction.line_273S_ids, "Correction report should find IP payslips from its origin")
        self.assertTrue(correction.line_273_part_ids, "Correction report should find Participation payslips from its origin")

    def test_cross_period_same_year_inclusion(self):
        '''
        Ensure that correction payslips of a previous period (same year) not taken into account
        in their respective 273.XX report are automatically included in the following report.
        '''
        employee = self.employee_john

        payslip_jan = self._create_paid_payslip(employee, date(2026, 1, 1), date(2026, 1, 31))

        report_jan = self._create_273_xx_report(year=2026, month='1', belcotax_reference='273XX-2026-01')
        report_jan.action_populate()
        report_jan.action_generate()
        report_jan.action_mark_as_done()

        wizard = self.env['hr.payslip.correction.wizard'].create({
            'employee_ids': [Command.set([employee.id])],
            'payslip_ids': [Command.set([payslip_jan.id])],
            'correction_choice': 'single',
        })
        wizard.action_correct_payslips()

        refund_jan = self.env['hr.payslip'].search([
            ('origin_payslip_id', '=', payslip_jan.id),
            ('is_refund_payslip', '=', True)
        ], limit=1)
        correction_jan = self.env['hr.payslip'].search([
            ('origin_payslip_id', '=', payslip_jan.id),
            ('is_refund_payslip', '=', False)
        ], limit=1)

        correction_jan.compute_sheet()
        correction_jan.action_payslip_done()
        correction_jan.action_payslip_paid()

        payslip_feb = self._create_paid_payslip(employee, date(2026, 2, 1), date(2026, 2, 28))

        report_feb = self._create_273_xx_report(year=2026, month='2')
        report_feb.action_populate()

        self.assertIn(refund_jan, report_feb.line_273S_ids.payslip_id)
        self.assertIn(correction_jan, report_feb.line_273S_ids.payslip_id)
        self.assertIn(payslip_feb, report_feb.line_273S_ids.payslip_id)
        self.assertNotIn(payslip_jan, report_feb.line_273S_ids.payslip_id)

    def test_cross_year_requires_correction(self):
        '''
        Ensure that correction payslips of a previous period (different year) are NOT included
        in the following year's report, but require a correction report for the previous year.
        '''
        employee = self.employee_john

        payslip_dec = self._create_paid_payslip(employee, date(2025, 12, 1), date(2025, 12, 31))

        report_dec = self._create_273_xx_report(year=2025, month='12', belcotax_reference='273XX-2025-12')
        report_dec.action_populate()
        report_dec.action_generate()
        report_dec.action_mark_as_done()

        wizard = self.env['hr.payslip.correction.wizard'].create({
            'employee_ids': [Command.set([employee.id])],
            'payslip_ids': [Command.set([payslip_dec.id])],
            'correction_choice': 'single',
        })
        wizard.action_correct_payslips()

        refund_dec = self.env['hr.payslip'].search([
            ('origin_payslip_id', '=', payslip_dec.id),
            ('is_refund_payslip', '=', True)
        ], limit=1)
        correction_dec = self.env['hr.payslip'].search([
            ('origin_payslip_id', '=', payslip_dec.id),
            ('is_refund_payslip', '=', False)
        ], limit=1)

        correction_dec.compute_sheet()
        correction_dec.action_payslip_done()
        correction_dec.action_payslip_paid()

        payslip_jan = self._create_paid_payslip(employee, date(2026, 1, 1), date(2026, 1, 31))

        report_jan = self._create_273_xx_report(year=2026, month='1')
        report_jan.action_populate()

        self.assertIn(payslip_jan, report_jan.line_273S_ids.payslip_id)
        self.assertNotIn(refund_dec, report_jan.line_273S_ids.payslip_id)
        self.assertNotIn(correction_dec, report_jan.line_273S_ids.payslip_id)

        report_dec.is_correction_needed = True
        correction_action = report_dec.action_correct()
        correction_report_dec = self.env['l10n_be.273_xx'].with_context(**correction_action['context']).create({
            'year': correction_action['context']['default_year'],
            'month': correction_action['context']['default_month'],
            'origin_id': correction_action['context']['default_origin_id'],
            'type': 'correction',
        })
        correction_report_dec.action_populate()

        self.assertIn(refund_dec, correction_report_dec.line_273S_ids.payslip_id)
        self.assertIn(correction_dec, correction_report_dec.line_273S_ids.payslip_id)

    def test_report_can_only_be_generated_from_root_company(self):
        companies = self.multibranch_company
        with self.assertRaises(UserError):
            self.env['l10n_be.273_xx'].with_company(companies[1]).create({'year': 2026, 'month': '1'})

    def test_include_child_branches_in_report(self):
        companies = self.belgian_company | self.multibranch_company
        # company 0 -> root / no child
        # company 1 (is parent of) company 2 (is parent of) company 3
        target_company = companies[1]

        employees = self.create_employee([
            {
                "name": f'Employee {company.name}',
                "company_id": company.id,
                'contract_date_start': date(2026, 1, 1),
                # relevant for 273.XX report
                'niss': self.generate_fake_niss(),
                'ip_wage_rate': .25,
            } for company in companies
        ])

        self.create_and_validate_payslips(employees=employees, year=2026, months=[1])

        report = self.env['l10n_be.273_xx'].with_company(target_company).create({
            'year': 2026,
            'month': '1',
        })
        report.action_populate()
        rendering_data = report._get_rendering_data()['declaration_273S']

        employees_reported = rendering_data['beneficiaries']
        self.assertEqual(len(employees_reported), 3, "Report should include 3 employees from company 1-2-3")

    def test_declared_amounts_come_from_the_mapping_codes(self):
        employee = self.create_employee([{
            'name': 'Employee IP',
            'company_id': self.belgian_company.id,
            'contract_date_start': date(2026, 1, 1),
            'niss': self.generate_fake_niss(),
            'ip_wage_rate': .25,
        }])

        payslips = self.create_and_validate_payslips(employees=employee, year=2026, months=[1])
        income = sum(payslips.line_ids.filtered(lambda line: line.code == 'IP').mapped('total'))
        withholding = sum(payslips.line_ids.filtered(lambda line: line.code == 'IP.DED').mapped('total'))
        self.assertTrue(income, "The payslips should hold some intellectual property income")
        self.assertTrue(withholding, "The payslips should hold some withholding tax")

        report = self._create_273_xx_report(year=2026, month='1')
        report.action_populate()
        rendering_data = report._get_rendering_data_273S()

        self.assertAlmostEqual(rendering_data['declaration']['tax_amount'], -withholding, 2)
        beneficiary = rendering_data['beneficiaries'][0]
        self.assertAlmostEqual(beneficiary['gross_amount'], income, 2)
        self.assertAlmostEqual(beneficiary['tax_amount'], withholding, 2)

    def test_beneficiary_is_kept_when_corrections_offset_income(self):
        employee = self.create_employee([{
            'name': 'Employee IP Correction',
            'company_id': self.belgian_company.id,
            'contract_date_start': date(2026, 1, 1),
            'niss': self.generate_fake_niss(),
            'ip_wage_rate': .25,
        }])
        payslips = self.create_and_validate_payslips(
            employees=employee, year=2026, months=[1, 2],
        )
        january_income = payslips.filtered(
            lambda payslip: payslip.date_from.month == 1,
        ).line_ids.filtered(lambda line: line.code == 'IP')
        february_income = payslips.filtered(
            lambda payslip: payslip.date_from.month == 2,
        ).line_ids.filtered(lambda line: line.code == 'IP')
        february_income.total = -january_income.total

        report = self._create_273_xx_report(year=2026, month='2')
        report.action_populate()
        rendering_data = report._get_rendering_data_273S()

        self.assertAlmostEqual(rendering_data['declaration']['gross_amount'], 0, 2)
        self.assertNotEqual(rendering_data['declaration']['tax_amount'], 0)
        self.assertEqual(len(rendering_data['beneficiaries']), 1)
        self.assertAlmostEqual(rendering_data['beneficiaries'][0]['gross_amount'], 0, 2)

    def test_adding_a_mapping_code_reports_it_without_a_code_change(self):
        employee = self.create_employee([{
            'name': 'Employee Extra Rule',
            'company_id': self.belgian_company.id,
            'contract_date_start': date(2026, 1, 1),
            'niss': self.generate_fake_niss(),
            'ip_wage_rate': 0,
        }])
        extra_rule = self.env['hr.salary.rule'].create({
            'name': 'Extra 273S Gross Rule',
            'code': 'IP.EXTRA',
            'sequence': 2310,
            'struct_ids': [(4, self.env.ref(
                'l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary',
            ).id)],
            'country_id': self.env.ref('base.be').id,
            'condition_select': 'none',
            'amount_select': 'fix',
            'amount_fix': 40.0,
        })
        gross_mapping = self.env.ref('l10n_be_hr_payroll.l10n_be_281_mapping_273s_gross_income')
        gross_mapping.salary_rule_ids = [Command.link(extra_rule.id)]

        payslips = self.create_and_validate_payslips(employees=employee, year=2026, months=[1])
        extra_amount = sum(payslips.line_ids.filtered(lambda line: line.code == 'IP.EXTRA').mapped('total'))
        self.assertTrue(extra_amount)

        report = self._create_273_xx_report(year=2026, month='1')
        report.action_populate()
        rendering_data = report._get_rendering_data_273S()

        self.assertAlmostEqual(rendering_data['beneficiaries'][0]['gross_amount'], extra_amount, 2)

    def test_beneficiary_is_kept_for_a_withholding_only_mapped_line(self):
        employee = self.create_employee([{
            'name': 'Employee Withholding Only',
            'company_id': self.belgian_company.id,
            'contract_date_start': date(2026, 1, 1),
            'niss': self.generate_fake_niss(),
            'ip_wage_rate': 0,
        }])
        extra_rule = self.env['hr.salary.rule'].create({
            'name': 'Extra 273S Withholding Only Rule',
            'code': 'IP.DED.EXTRA',
            'sequence': 2310,
            'struct_ids': [(4, self.env.ref(
                'l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary',
            ).id)],
            'country_id': self.env.ref('base.be').id,
            'condition_select': 'none',
            'amount_select': 'fix',
            'amount_fix': -15.0,
        })
        withholding_mapping = self.env.ref('l10n_be_hr_payroll.l10n_be_281_mapping_273s_withholding_tax')
        withholding_mapping.salary_rule_ids = [Command.link(extra_rule.id)]

        payslips = self.create_and_validate_payslips(employees=employee, year=2026, months=[1])
        withholding = sum(payslips.line_ids.filtered(lambda line: line.code == 'IP.DED.EXTRA').mapped('total'))
        self.assertTrue(withholding)

        report = self._create_273_xx_report(year=2026, month='1')
        report.action_populate()
        rendering_data = report._get_rendering_data_273S()

        self.assertEqual(len(rendering_data['beneficiaries']), 1)
        beneficiary = rendering_data['beneficiaries'][0]
        self.assertAlmostEqual(beneficiary['gross_amount'], 0, 2)
        self.assertAlmostEqual(beneficiary['tax_amount'], withholding, 2)
        self.assertAlmostEqual(rendering_data['declaration']['tax_amount'], -withholding, 2)
