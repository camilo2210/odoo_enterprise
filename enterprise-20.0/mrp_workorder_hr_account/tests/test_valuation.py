# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time

from odoo.addons.mrp_account.tests.common import TestBomPriceOperationCommon
from odoo.tests import tagged, Form

from datetime import datetime, timedelta

PRICE = 1637.51


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestMrpWorkorderHrValuation(TestBomPriceOperationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Jean Michel',
            'hourly_cost': 100,
        })

        cls.workcenter.employee_costs_hour = 50

        cls.workcenter.employee_ids = [(4, cls.employee.id)]
        cls.now = datetime.now()
        cls.mo = cls._create_mo(cls.bom_1, 1)
        with Form(cls.mo) as mo_form:
            mo_form.qty_producing = 1

        # Register a productivity of one hour
        cls.workorder = cls.mo.workorder_ids[0]
        cls.env['mrp.workcenter.productivity'].create({
            'employee_id': cls.employee.id,
            'workcenter_id': cls.workcenter.id,
            'workorder_id': cls.workorder.id,
            'date_start': cls.now,
            'date_end': cls.now + timedelta(hours=1),
            'loss_id': cls.env.ref('mrp.block_reason7').id,
        })

    def assert_employee_cost(self, expected_employee_cost):
        value = self.mo.company_id.currency_id.round((PRICE + expected_employee_cost) * (1 - 0.13))
        self.assertEqual(self.mo.move_finished_ids[0].value, value)

    def test_workcenter_employee_cost_impacting_on_valuation_1(self):
        """
            When the employee's *cost per hour* is set on the employee's form, it
            must override the workcenter's *employee cost per hour* for AVCO/FIFO
            products. However, if the employee's cost per hour is zero, then the
            workcenter's employee cost per hour should be used on valuations.
        """
        self.mo.button_mark_done()
        self.assert_employee_cost(100)

    def test_workcenter_employee_cost_impacting_on_valuation_2(self):
        # 1.2) hourly_cost not set on employee's form
        self.employee.hourly_cost = 0
        self.assertEqual(self.workorder.time_ids.total_cost, 50)
        self.workorder.button_finish()
        self.mo.button_mark_done()
        self.assert_employee_cost(50)  # must use workcenter's costs_hour

    def test_workcenter_employee_cost_impacting_on_valuation_3(self):
        self.dining_table.categ_id = self.category_avco

        self.workorder.button_finish()
        self.mo.button_mark_done()
        self.assert_employee_cost(100)

    def test_workcenter_employee_cost_impacting_on_valuation_4(self):
        self.dining_table.categ_id = self.category_avco
        self.employee.hourly_cost = 0
        self.assertEqual(self.workorder.time_ids.total_cost, 50)
        self.workorder.button_finish()
        self.mo.button_mark_done()
        self.assert_employee_cost(50)  # must use workcenter's costs_hour

    def test_workcenter_employee_cost_impacting_on_valuation_5(self):
        self.dining_table.categ_id = self.category_avco
        self.workorder.button_finish()
        self.mo.button_mark_done()
        self.assertEqual(self.mo.state, 'done')
        productivity = self.mo.workorder_ids.time_ids[0]
        self.assertEqual(productivity.employee_cost, 100)
        self.assertEqual(productivity.total_cost, 100)
        self.employee.hourly_cost = 50
        self.assertEqual(productivity.employee_cost, 100, 'The productivity employee cost must remain unchanged after done the MO')
        self.assertEqual(productivity.total_cost, 100, 'Productivity time cost must remain unchanged after done the MO')

    @freeze_time('2020-01-01 08:00:00')
    def test_cost_calculation_multiple_employees_same_workcenter(self):
        self.dining_table.categ_id = self.category_avco
        self.workcenter.costs_hour = 35
        employee1, employee2 = self.employee, self.env['hr.employee'].create({
            'name': 'employee 2',
            'hourly_cost': 40
        })
        employee1.hourly_cost = 15
        workorder = self.mo.workorder_ids[1]
        ymd = {'year': 2020, 'month': 1, 'day': 1}
        # emp1 works (08:00 until 09:30) and (11:30 until 12:00)
        self.env['mrp.workcenter.productivity'].create([{
            'employee_id': employee1.id,
            'workcenter_id': self.workcenter.id,
            'workorder_id': workorder.id,
            'date_start': start,
            'date_end': end,
            'loss_id': self.ref('mrp.block_reason7'),
        } for start, end in (
            (datetime(**ymd, hour=8), datetime(**ymd, hour=9, minute=30)),
            (datetime(**ymd, hour=11, minute=30), datetime(**ymd, hour=12)),
        )])
        # emp2 works (08:30:00 until 09:30) and (10:30 until 11:30)
        self.env['mrp.workcenter.productivity'].create([{
            'employee_id': employee2.id,
            'workcenter_id': self.workcenter.id,
            'workorder_id': workorder.id,
            'date_start': start,
            'date_end': end,
            'loss_id': self.ref('mrp.block_reason7'),
        } for start, end in (
            (datetime(**ymd, hour=8, minute=30), datetime(**ymd, hour=9, minute=30)),
            (datetime(**ymd, hour=10, minute=30), datetime(**ymd, hour=11, minute=30)),
        )])
        # => workcenter is operated from: [08:00 - 09:30] and [10:30 - 12:00] = 180 minutes
        # we should get a workcenter cost like: ($35 / hour * 1.5 hours) + ($35 / hour * 1.5 hours) = $105.0
        workorder.button_finish()
        self.mo.button_mark_done()
        # SVL value derived like:
        #   emp1 total cost        + emp2 total cost        + workcenter costs
        # = ($15 / hour * 2 hours) + ($40 / hour * 2 hours) + ($105.0)
        # = $215.0
        self.assertEqual(workorder._cal_cost(), 215.0)

    def test_wip_accounting_01(self):
        """
        This test runs a WIP accounting for a workorder currently runnning.
        """
        with freeze_time('2027-09-01 10:00:00'):
            mo = self._create_mo(self.bom_1, 1)
        # post a WIP for a valid MO - no WO time completed, but time running, no valuated components consumed => nothing to debit/credit
        with freeze_time('2027-10-01 10:00:00'):
            mo.workorder_ids[0].start_employee(self.employee.id)
        with freeze_time('2027-10-01 10:30:00'):
            wizard = Form(self.env['mrp.account.wip.accounting'].with_context({'active_ids': [mo.id]}))
            wizard.save().confirm()
        wip_empty_entries = self.env['account.move'].search([('ref', 'ilike', 'WIP - ' + mo.name)])
        self.assertEqual(len(wip_empty_entries), 2, "Should be 2 journal entries: 1 for the WIP accounting + 1 for their reversals")
        self.assertEqual(wip_empty_entries[0].wip_production_count, 1, "WIP MOs should be linked to entries even if no 'done' work")
