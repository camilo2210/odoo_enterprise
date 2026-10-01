from odoo.tests.common import tagged, TransactionCase


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrLeaveAllocation(TransactionCase):

    def setUp(self):
        super().setUp()

        self.jc = self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302')
        self.work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_death_close_family')
        self.parameter = self.env['hr.rule.parameter']._get_parameter_from_code('leave_durations_by_jc', raise_if_not_found=False) or {}
        self.assertTrue(self.parameter, "Rule parameter should exist")
        self.assertIn('007.21', self.parameter, "Bereavement leave (Code '007.21') config should be defined in parameter")
        self.assertIn(
            '302',
            self.parameter['007.21'],
            "JC 302 should be configured for Bereavement leave"
        )

        self.employee = self.env['hr.employee'].create({
            'name': 'Martin Employeeston',
            'l10n_be_joint_committee_id': self.jc.id,
        })

    def test_allocation_within_limit(self):
        allocation = self.env['hr.leave.allocation'].create({
            'name': 'Test Allocation OK',
            'employee_id': self.employee.id,
            'work_entry_type_id': self.work_entry_type.id,
            'number_of_days': 3,
        })

        self.assertFalse(
            allocation._check_max_duration_exceeded()[0],
            "Allocation should not exceed max duration"
        )

        self.assertFalse(
            allocation.jc_allocation_info,
            "No warning message should be set"
        )

    def test_allocation_exceeds_limit(self):
        allocation = self.env['hr.leave.allocation'].create({
            'name': 'Test Allocation Exceeded',
            'employee_id': self.employee.id,
            'work_entry_type_id': self.work_entry_type.id,
            'number_of_days': 15,
        })

        self.assertTrue(
            allocation._check_max_duration_exceeded()[0],
            "Allocation should exceed max duration"
        )

        self.assertTrue(
            allocation.jc_allocation_info,
            "Warning message should be set"
        )

    def test_get_allocations_with_exceeded_duration(self):
        alloc_ok = self.env['hr.leave.allocation'].create({
            'name': 'OK Allocation',
            'employee_id': self.employee.id,
            'work_entry_type_id': self.work_entry_type.id,
            'number_of_days': 2,
        })

        alloc_bad = self.env['hr.leave.allocation'].create({
            'name': 'Bad Allocation',
            'employee_id': self.employee.id,
            'work_entry_type_id': self.work_entry_type.id,
            'number_of_days': 12,
        })

        allocations = alloc_ok | alloc_bad
        exceeded_allocations = allocations.filtered(lambda a: a._check_max_duration_exceeded()[0])

        self.assertIn(
            alloc_bad,
            exceeded_allocations,
            "Exceeded allocation should be returned"
        )

        self.assertNotIn(
            alloc_ok,
            exceeded_allocations,
            "Valid allocation should NOT be returned"
        )
