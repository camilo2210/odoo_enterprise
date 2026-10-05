# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta

from odoo.addons.test_l10n_be_hr_payroll_account.tests.test_dmfa import TestDMFA
from odoo.fields import Command
from odoo.tests import freeze_time, tagged

from odoo import fields


@tagged('post_install', '-at_install', 'dmfa', 'structural_deduction')
class TestDMFAStructuralDeduction(TestDMFA):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.belgium_monthly_payslip_structure = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        cls.belgium_thirteen_month_structure = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month')

    def _validate_dmfa_structural_deduction(self, year, quarter, payslips):
        """
        Helper to verify that Structural Deduction (code 3000) in DMFA XML report matches the amount from payslips.
        """
        dmfa_dict = self._generate_dmfa_declaration(year=str(year), quarter=str(quarter))
        natural_persons = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']
        if isinstance(natural_persons, dict):
            natural_persons = [natural_persons]

        dmfa_amount = 0
        for natural_person in natural_persons:
            worker_record = natural_person.get('WorkerRecord', {})
            occupations = worker_record.get('Occupation', [])
            if isinstance(occupations, dict):
                occupations = [occupations]

            for occ in occupations:
                deductions = occ.get('OccupationDeduction', [])
                if isinstance(deductions, dict):
                    deductions = [deductions]

                for ded in deductions:
                    if ded.get('DeductionCode') == '3000':
                        dmfa_amount += int(ded.get('DeductionAmount', 0)) / 100.0

        prev_line_values = payslips._get_line_values(['ONSS_STRUCTURAL'], compute_sum=True)
        payslip_deduction = abs(prev_line_values['ONSS_STRUCTURAL']['sum']['total'])
        self.assertAlmostEqual(
            dmfa_amount,
            payslip_deduction, 2,
            f"DMFA structural deduction ({dmfa_amount} euros) does not match expected ({payslip_deduction} euros from payslips)."
        )

    @freeze_time("2025-04-10 10:00:00")
    def test_regular_first_quarter(self):
        """
        Normal Q1 payslips with regularization.
        """
        payslips = self.env['hr.payslip'].create([{
            'version_id': self.contract.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'version_id': self.contract.id,
            'date_from': date(2025, 2, 1),
            'date_to': date(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'version_id': self.contract.id,
            'date_from': date(2025, 3, 1),
            'date_to': date(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }])

        # Need to compute and validate in order to ensure that the payslip lines are available
        for slip in payslips:
            slip.compute_sheet()
            slip.action_payslip_done()

        self._validate_payslip(payslips[0])

        self._validate_payslip(payslips[1])

        self._validate_payslip(payslips[2])

        self._validate_dmfa_structural_deduction(year=2025, quarter=1, payslips=payslips)

    @freeze_time("2025-04-10 10:00:00")
    def test_contract_end_in_february(self):
        """
        Employee contract end in February, structural deduction should be applied in February payslip.
        """
        self.employee.departure_date = date(2025, 2, 15)
        self.contract.date_end = date(2025, 2, 15)

        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 2, 1),
            'date_to': date(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
        }])

        payslips[0].compute_sheet()
        payslips[0].action_payslip_done()
        self._validate_payslip(payslips[0])

        # February payslip should be prorated since the contract ended partway through the month
        payslips[1].compute_sheet()
        payslips[1].action_payslip_done()
        self._validate_payslip(payslips[1])

        self._validate_dmfa_structural_deduction(year=2025, quarter=1, payslips=payslips)

    @freeze_time("2025-12-31 10:00:00")
    def test_13th_month_regularization(self):
        """
        Test 13th month payslip in December adds remunerations without worked hours, so the total remunerations for the quarter
        are higher, so the structural deduction should be adjusted to be lower.
        """
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Oct 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 10, 1),
            'date_to': date(2025, 10, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Nov 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 11, 1),
            'date_to': date(2025, 11, 30),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Dec 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 12, 1),
            'date_to': date(2025, 12, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'name': '13th Month 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 12, 1),
            'date_to': date(2025, 12, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_thirteen_month_structure.id,
        }])

        for slip in payslips:
            slip.compute_sheet()
            slip.action_payslip_done()

        self._validate_payslip(payslips[3])

        self._validate_dmfa_structural_deduction(year=2025, quarter=4, payslips=payslips)

    @freeze_time("2025-04-10 10:00:00")
    def test_refund_and_correct_paid_payslip(self):
        """
        Test the scenario where a payslip is paid, refunded, and then corrected with a new payslip.
        The structural deduction on the payslips should reflect the changes in the refund and correction payslips
        when computing the deduction.
        """
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 2, 1),
            'date_to': date(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Mar 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 3, 1),
            'date_to': date(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }])

        for slip in payslips:
            slip.compute_sheet()
            slip.action_payslip_done()
            slip.action_payslip_paid()

        original_march_slip = payslips[2]
        refund_slip = original_march_slip._action_refund_payslips()
        correction_slip = original_march_slip._action_correct_payslips()

        correction_slip._set_input_value('COMMISSION', 1000)
        correction_slip.compute_sheet()
        correction_slip.action_payslip_done()

        # The net structural reduction for Q1 should equal the sum across all slips:
        # Jan + Feb + Original Mar (Paid) + Refund Mar (Negative) + Correction Mar
        # Because Original + Refund = 0, the sum is effectively Jan + Feb + Correction Mar.
        all_q1_payslips = payslips | refund_slip | correction_slip

        self._validate_payslip(original_march_slip)
        self._validate_payslip(refund_slip)
        self._validate_payslip(correction_slip)

        self._validate_dmfa_structural_deduction(year=2025, quarter=1, payslips=all_q1_payslips)

    @freeze_time("2025-04-10 10:00:00")
    def test_no_remuneration(self):
        """
        In a quarter where an employee has no remunerations, the structural deduction should not
        apply the BiKs and the structural deduction should be 0.
        """
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'request_date_from': date(2025, 1, 1),
            'request_date_to': date(2025, 3, 31),
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave').id,
        })

        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 2, 1),
            'date_to': date(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Mar 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 3, 1),
            'date_to': date(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }])

        payslips.compute_sheet()
        payslips.action_payslip_done()

        structural_deduction_lines = payslips.line_ids.filtered(lambda line: line.code == "ONSS_STRUCTURAL")
        for line in structural_deduction_lines:
            self.assertEqual(0.0, line.total, f"Payslip {line.slip_id.name} has a non zero structural deduction for a quarter with no remunerations.")

        self._validate_dmfa_structural_deduction(year=2025, quarter=1, payslips=payslips)

    @freeze_time("2025-04-10 10:00:00")
    def test_contract_change_to_part_time(self):
        """
        Test employee changing from full-time to part time in the middle of a quarter.
        Since this creates a new occupation, the structural deduction should be computed as the sum of structural deductions
        for each occupation.
        """
        self.contract.date_end = date(2025, 2, 28)

        calendar_19h = self.env['resource.calendar'].create({
            'name': '19h Part Time',
            'company_id': self.belgian_company.id,
            'hours_per_day': 3.8,
            'full_time_required_hours': 38.0,
            'is_fulltime': False,
            'attendance_ids': [(0, 0, {
                'dayofweek': str(i),
                'hour_from': 8.0,
                'hour_to': 11.8,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_attendance').id
            }) for i in range(5)]
        })

        part_time_contract = self.employee.create_version({
            'name': 'Part Time Contract',
            'date_start': date(2025, 3, 1),
            'date_version': date(2025, 3, 1),
            'date_end': False,
            'wage': 1500,
            'resource_calendar_id': calendar_19h.id,
            'reference_calendar_id': self.calendar_38h.id,
        })

        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025 (Full-Time)',
            'version_id': self.contract.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025 (Full-Time)',
            'version_id': self.contract.id,
            'date_from': date(2025, 2, 1),
            'date_to': date(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Mar 2025 (Part-Time)',
            'version_id': part_time_contract.id,
            'date_from': date(2025, 3, 1),
            'date_to': date(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }])

        for payslip in payslips:
            payslip.compute_sheet()
            payslip.action_payslip_done()

        self._validate_payslip(payslips[2])

        self._validate_dmfa_structural_deduction(year=2025, quarter=1, payslips=payslips)

    @freeze_time("2025-04-10 10:00:00")
    def test_out_of_order_validation(self):
        """
        Q1 payslips computed in reverse order (i.e. March -> February -> January). February and March should add
        the adjustment/correction deduction amounts.
        """
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 2, 1),
            'date_to': date(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Mar 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 3, 1),
            'date_to': date(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }])

        # Compute and validate in reverse order
        for slip in payslips[::-1]:
            slip.compute_sheet()
            slip.action_payslip_done()

        for slip in payslips:
            self.assertTrue(slip.line_ids.filtered(lambda l: l.code == 'ONSS_STRUCTURAL'),
                             f"Structural deduction should be applied in {slip.name} since there should be a correction.")

        # March
        self._validate_payslip(payslips[2])

        # February
        self._validate_payslip(payslips[1])

        # January
        self._validate_payslip(payslips[0])

        self._validate_dmfa_structural_deduction(year=2025, quarter=1, payslips=payslips)

    def test_batch_correction(self):
        """
        Test payrun with all payslips of the quarter computed at the same time using the correction wizard.
        All new payslips in the batch will initially be in draft so they will be filtered out when
        searching for validated payslips, but they should be included in the computation.
        """
        # Create original payslips in the "paid_state" so they can be corrected
        past_date = fields.Datetime.now() - timedelta(days=5)  # need this to trigger the "has_wrong_data" field
        base_slip_vals = {
            'version_id': self.contract.id,
            'employee_id': self.employee.id,
            'struct_id': self.belgium_monthly_payslip_structure.id,
            'company_id': self.belgian_company.id,
        }

        payslips = self.env['hr.payslip'].create([{
            **base_slip_vals,
            'name': 'Payslip Jan 2025',
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
        }, {
            **base_slip_vals,
            'name': 'Payslip Feb 2025',
            'date_from': date(2025, 2, 1),
            'date_to': date(2025, 2, 28),
        }, {
            **base_slip_vals,
            'name': 'Payslip Mar 2025',
            'date_from': date(2025, 3, 1),
            'date_to': date(2025, 3, 31),
        }, {
            **base_slip_vals,
            'name': 'Payslip Mar 2025',
            'date_from': date(2025, 4, 1),
            'date_to': date(2025, 4, 30),  # including April payslip to check that the rule does not use payslips in the batch outside the quarter
        }])

        payslips.compute_sheet()
        payslips.action_payslip_done()
        payslips.action_payslip_paid()

        payslips.write({
            'done_date': past_date,
        })

        self.contract.last_modified_date = fields.Datetime.now()
        wizard = self.env['hr.payslip.correction.wizard'].create({
            'employee_ids': [Command.set([self.employee.id])],
            'payslip_ids': [Command.set([payslips[0].id])],
            'correction_choice': 'multi',
        })
        self.assertEqual(len(wizard.allowed_payslip_ids), 4, "Wizard should find all 4 payslips that should be corrected.")

        result_action = wizard.action_correct_payslips()
        all_correction_wizard_slips = self.env['hr.payslip'].search(result_action['domain'])
        corrections = all_correction_wizard_slips.filtered(lambda p: p.state == 'draft')

        self.assertEqual(len(corrections), 4, "There should be 4 correction payslips.")
        correction_payrun = corrections.payslip_run_id
        correction_payrun.action_confirm()
        corrections.action_payslip_done()

        q1_payslips = (all_correction_wizard_slips + payslips).filtered(
            lambda p: p.date_from >= date(2025, 1, 1) and p.date_to <= date(2025, 3, 31)
        )
        self._validate_dmfa_structural_deduction(year=2025, quarter=1, payslips=q1_payslips)
