from datetime import date
from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_eco_vouchers')
class TestPayrollEcoVouchers(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure CP200 and CP302 configuration
        cls.cp200 = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200')
        cls.cp302 = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302')

        cls.test_contracts.write({'l10n_be_joint_committee_id': cls.cp200.id})
        cls.john_contracts.write({'l10n_be_joint_committee_id': cls.cp200.id})

    def test_eco_vouchers_cp200(self):
        # CP200 pays in June (Month 6). George has full contracts for the ref period.
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee_test.id,
            'version_id': self.employee_test.version_id.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
            'company_id': self.belgian_company.id,
        })
        payslip.compute_sheet()

        line = payslip.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS')
        self.assertTrue(line, "Eco Voucher line should be present in June for CP200")
        # George worked full year -> 250
        self.assertEqual(line.amount, 250.0)

    def test_eco_vouchers_cp200_part_time(self):
        # 50% work rate employee
        part_time_emp = self.create_employee({
            'name': 'Part Time CP200',
            'resource_calendar_id': self.resource_calendar_mid_time.id,  # 50%
            'l10n_be_joint_committee_id': self.cp200.id,
            'contract_date_start': date(2023, 1, 1),
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': part_time_emp.id,
            'version_id': part_time_emp.version_id.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
            'company_id': self.belgian_company.id,
        })
        payslip.compute_sheet()

        line = payslip.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS')
        self.assertTrue(line)
        # 50% work rate -> tier >= 50% -> 150. Worked full year -> 150.0
        self.assertEqual(line.amount, 150.0)

    def test_eco_vouchers_proration(self):
        # Employee started mid-year (e.g., Jan 1st for a June payment)
        # Ref period: June 2024 - May 2025
        # Worked: Jan 2025 - May 2025 (5 months = ~151 days)
        new_emp = self.create_employee({
            'name': 'New Employee',
            'l10n_be_joint_committee_id': self.cp200.id,
            'contract_date_start': date(2025, 1, 1),
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': new_emp.id,
            'version_id': new_emp.version_id.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
            'company_id': self.belgian_company.id,
        })
        payslip.compute_sheet()

        line = payslip.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS')
        self.assertTrue(line)
        # 1 Jan 2025 to 31 May 2025 = 108 working days, out of the 260 the
        # calendar theoretically schedules over the reference period
        # 108 / 260 * 250 = 103.85...
        self.assertAlmostEqual(line.amount, 108 / 260 * 250, delta=1.0)

    def test_eco_vouchers_cp302(self):
        # CP302 Month 12
        emp = self.create_employee({
            'name': 'CP302 Emp',
            'l10n_be_joint_committee_id': self.cp302.id,
            'contract_date_start': date(2024, 1, 1),
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp302_4').id,
            })

        payslip = self.env['hr.payslip'].create({
            'employee_id': emp.id,
            'version_id': emp.version_id.id,
            'date_from': date(2025, 12, 1),
            'date_to': date(2025, 12, 31),
            'company_id': self.belgian_company.id,
        })
        payslip.compute_sheet()

        line = payslip.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS')
        self.assertTrue(line)
        self.assertEqual(line.amount, 250.0)

    def test_eco_vouchers_already_paid(self):
        # Pay once in June
        payslip1 = self.env['hr.payslip'].create({
            'employee_id': self.employee_test.id,
            'version_id': self.employee_test.version_id.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 15),
            'company_id': self.belgian_company.id,
        })
        payslip1.compute_sheet()
        payslip1.action_payslip_done()
        line = payslip1.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS')
        self.assertTrue(line)

        # Pay again diff payslip same month
        payslip2 = self.env['hr.payslip'].create({
            'employee_id': self.employee_test.id,
            'version_id': self.employee_test.version_id.id,
            'date_from': date(2025, 6, 16),
            'date_to': date(2025, 6, 30),
            'company_id': self.belgian_company.id,
        })
        payslip2.compute_sheet()

        line = payslip2.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS')
        self.assertFalse(line, "Should not pay twice")

    def test_eco_vouchers_transition_1(self):
        """
        Employee transitions from CP302 to CP200 in Oct 2025
        Setup history
        Jan 2024 - Sep 2025: CP302
        Oct 2025 - ...: CP200
        """
        emp = self.create_employee({
            'name': 'Transition Emp',
            'l10n_be_joint_committee_id': self.cp302.id,
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': date(2025, 9, 30),
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp302_4').id,
        })

        version_cp200 = emp.create_version({
            'date_version': date(2025, 10, 1),
            'contract_date_start': date(2025, 10, 1),
            'l10n_be_joint_committee_id': self.cp200.id,
        })

        # 1. Pay in Dec 2025 (CP302 month)
        # Ref period: Dec 2024 - Nov 2025
        # CP302 portion: Dec - Sep (304 days)
        payslip_dec = self.env['hr.payslip'].create({
            'employee_id': emp.id,
            'version_id': version_cp200.id,
            'date_from': date(2025, 12, 1),
            'date_to': date(2025, 12, 31),
            'company_id': self.belgian_company.id,
        })
        payslip_dec.compute_sheet()
        line_dec = payslip_dec.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS')
        self.assertTrue(line_dec)
        # Expected amount: 304 / 365 * 250 = 208.22...
        self.assertAlmostEqual(line_dec.amount, 304 / 365 * 250, delta=1.0)
        payslip_dec.action_payslip_done()

        # 2. Pay in June 2026 (CP200 month)
        # Ref period: June 2025 - May 2026
        # CP200 portion: Oct 2025 - May 2026 (243 days)
        payslip_june = self.env['hr.payslip'].create({
            'employee_id': emp.id,
            'version_id': version_cp200.id,
            'date_from': date(2026, 6, 1),
            'date_to': date(2026, 6, 30),
            'company_id': self.belgian_company.id,
        })
        payslip_june.compute_sheet()
        line_june = payslip_june.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS')
        self.assertTrue(line_june)
        # 1 Oct 2025 to 31 May 2026 = 173 working days, out of the 260 the
        # calendar theoretically schedules over the reference period
        # Expected amount: 173 / 260 * 250 = 166.35...
        self.assertAlmostEqual(line_june.amount, 173 / 260 * 250, delta=1.0)

    def test_eco_vouchers_transition_2(self):
        """
        Employee transitions from CP200 to CP302 in Oct 2025
        Setup history
        Jan 2024 - Sep 2025: CP200
        Oct 2025 - ...: CP302
        """
        emp = self.create_employee({
            'name': 'Transition Inverse Emp',
            'l10n_be_joint_committee_id': self.cp200.id,
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': date(2025, 9, 30),
        })

        version_cp302 = emp.create_version({
            'date_version': date(2025, 10, 1),
            'contract_date_start': date(2025, 10, 1),
            'l10n_be_joint_committee_id': self.cp302.id,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp302_4').id,
        })

        # 1. Pay in June 2025 (CP200 month)
        # Ref period: June 2024 - May 2025
        # Full CP200
        payslip_june_25 = self.env['hr.payslip'].create({
            'employee_id': emp.id,
            'version_id': emp.version_ids[0].id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
            'company_id': self.belgian_company.id,
        })
        payslip_june_25.compute_sheet()
        line_june_25 = payslip_june_25.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS')
        self.assertTrue(line_june_25)
        self.assertEqual(line_june_25.amount, 250.0)
        payslip_june_25.action_payslip_done()

        # 2. Pay in Dec 2025 (CP302 month)
        # Ref period: Dec 2024 - Nov 2025
        # CP302 portion: Oct - Nov (61 days)
        payslip_dec = self.env['hr.payslip'].create({
            'employee_id': emp.id,
            'version_id': version_cp302.id,
            'date_from': date(2025, 12, 1),
            'date_to': date(2025, 12, 31),
            'company_id': self.belgian_company.id,
        })
        payslip_dec.compute_sheet()
        line_dec = payslip_dec.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS')
        self.assertTrue(line_dec)
        # Oct (31) + Nov (30) = 61 days
        # Expected amount: 61 / 365 * 250 = 41.78...
        self.assertAlmostEqual(line_dec.amount, 61 / 365 * 250, delta=1.0)
        payslip_dec.action_payslip_done()

        # 3. Pay in June 2026 (CP200 month)
        # Ref period: June 2025 - May 2026
        # CP200 portion: June 2025 - Sep 2025 (122 days)
        payslip_june_26 = self.env['hr.payslip'].create({
            'employee_id': emp.id,
            'version_id': version_cp302.id,
            'date_from': date(2026, 6, 1),
            'date_to': date(2026, 6, 30),
            'company_id': self.belgian_company.id,
        })
        payslip_june_26.compute_sheet()
        line_june_26 = payslip_june_26.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS')
        self.assertTrue(line_june_26)
        # 1 June 2025 to 30 Sep 2025 = 87 working days, out of the 260 the
        # calendar theoretically schedules over the reference period
        # Expected amount: 87 / 260 * 250 = 83.65...
        self.assertAlmostEqual(line_june_26.amount, 87 / 260 * 250, delta=1.0)

    def test_eco_vouchers_capped(self):
        # Employee with >100% work rate
        over_time_emp = self.create_employee({
            'name': 'Over Time Emp',
            'l10n_be_joint_committee_id': self.cp302.id,
            'contract_date_start': date(2024, 1, 1),
            'resource_calendar_id': self.env['resource.calendar'].create({
                'name': 'Overtime Calendar',
                'hours_per_week': 45.6,
                'full_time_required_hours': 38,  # 45.6 / 38.0 = 120%
            }).id,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp302_4').id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': over_time_emp.id,
            'version_id': over_time_emp.version_id.id,
            'date_from': date(2025, 12, 1),
            'date_to': date(2025, 12, 31),
            'company_id': self.belgian_company.id,
        })
        payslip.compute_sheet()

        line = payslip.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS')
        self.assertTrue(line)
        # Should be exactly 250, not 1.2 * 250 = 300
        self.assertEqual(line.amount, 250.0)

    def test_eco_vouchers_departing_employee(self):
        """
        Employee (CP200, pays in June) leaves in March. Their last payslip is in March, which is not the normal
        JC month, but eco vouchers rule triggers since they have departure_date falls within the payslip period.
        """
        emp = self.create_employee({
            'name': 'Departing CP200 Emp',
            'l10n_be_joint_committee_id': self.cp200.id,
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': date(2025, 3, 31),
        })
        emp.departure_date = date(2025, 3, 31)

        payslip = self.env['hr.payslip'].create({
            'employee_id': emp.id,
            'version_id': emp.version_id.id,
            'date_from': date(2025, 3, 1),
            'date_to': date(2025, 3, 31),
            'company_id': self.belgian_company.id,
        })
        payslip.compute_sheet()

        line = payslip.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS')
        self.assertTrue(line, "Eco Vouchers should be paid on the last payslip for a departing employee")
        # Ref period: June 2024 - May 2025 (CP200)
        # Worked: June 1, 2024 to Mar 31, 2025 = 216 working days, out of the 260
        # the calendar theoretically schedules over the reference period
        # Expected amount: 216 / 260 * 250 = 207.69...
        self.assertAlmostEqual(line.amount, 216 / 260 * 250, delta=1.0)

    def test_eco_vouchers_departing_no_double_pay(self):
        """
        Departing employee whose last payslip is in June (the normal CP200 month).
        Eco-vouchers should only be paid once
        """
        emp = self.create_employee({
            'name': 'Departing CP200 Emp June',
            'l10n_be_joint_committee_id': self.cp200.id,
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': date(2025, 6, 15),
        })
        emp.departure_date = date(2025, 6, 15)

        # First payslip: paid and validated
        payslip1 = self.env['hr.payslip'].create({
            'employee_id': emp.id,
            'version_id': emp.version_id.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 15),
            'company_id': self.belgian_company.id,
        })
        payslip1.compute_sheet()
        payslip1.action_payslip_done()
        self.assertTrue(payslip1.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS'))

        # Second payslip in the same month — should NOT pay again
        payslip2 = self.env['hr.payslip'].create({
            'employee_id': emp.id,
            'version_id': emp.version_id.id,
            'date_from': date(2025, 6, 16),
            'date_to': date(2025, 6, 30),
            'company_id': self.belgian_company.id,
        })
        payslip2.compute_sheet()
        self.assertFalse(
            payslip2.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS'),
            "Should not pay eco-vouchers twice in the same month"
        )

    def test_eco_vouchers_wizard_batch_id(self):
        """
        The wizard can be opened from a payslip batch
        (action_l10n_be_eco_vouchers passes 'batch_id' in the context).
        In that case, only the ECOVOUCHERS lines of payslips belonging to that
        batch should be listed, even if they are still in draft state.
        Outside of that context, the wizard keeps its normal company/year-wide
        behaviour and only considers validated/paid payslips.
        """
        batch = self.env['hr.payslip.run'].create({
            'name': 'Batch',
            'date_start': date(2025, 6, 1),
            'date_end': date(2025, 6, 30),
            'company_id': self.belgian_company.id,
            'structure_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
        })

        # Payslip inside the batch, left in draft state
        batch_payslip = self.env['hr.payslip'].create({
            'name': 'June Payslip (Batch)',
            'employee_id': self.employee_test.id,
            'version_id': self.employee_test.version_id.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
            'company_id': self.belgian_company.id,
            'payslip_run_id': batch.id,
        })
        batch_payslip.compute_sheet()
        self.assertTrue(
            batch_payslip.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS'),
            "Eco Voucher line should be present on the batch payslip",
        )

        # Payslip of another employee, validated, but not part of the batch
        other_emp = self.create_employee({
            'name': 'Other Employee',
            'l10n_be_joint_committee_id': self.cp200.id,
            'contract_date_start': date(2023, 1, 1),
        })
        other_payslip = self.env['hr.payslip'].create({
            'name': 'June Payslip Other',
            'employee_id': other_emp.id,
            'version_id': other_emp.version_id.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
            'company_id': self.belgian_company.id,
        })
        other_payslip.compute_sheet()
        other_payslip.action_payslip_done()

        # Without batch_id: normal year/company search, only validated/paid slips count
        wizard_default = self.env['l10n.be.eco.vouchers.wizard'].with_company(self.belgian_company).create({
            'company_id': self.belgian_company.id,
            'reference_year': '2025',
        })
        self.assertEqual(
            wizard_default.line_ids.employee_id, other_emp,
            "Without a batch context, only the validated payslip's employee should be listed",
        )

        # With batch_id: only the batch's slip counts, regardless of its (draft) state
        wizard_batch = self.env['l10n.be.eco.vouchers.wizard'].with_company(self.belgian_company).with_context(
            batch_id=batch.id
        ).create({
            'company_id': self.belgian_company.id,
            'reference_year': '2025',
        })
        self.assertEqual(
            wizard_batch.line_ids.employee_id, self.employee_test,
            "With a batch context, only employees from that batch's payslips should be listed",
        )
