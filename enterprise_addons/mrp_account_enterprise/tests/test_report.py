# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo.addons.mrp_account.tests.common import TestBomPriceOperationCommon
from odoo.tests import tagged
from freezegun import freeze_time


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestReportsCommon(TestBomPriceOperationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @freeze_time('2022-05-28')
    def test_mrp_avg_cost_calculation(self):
        """
            Check that the average cost is calculated based on the quantity produced in each MO

            1:/ MO1:
                - qty to produce: 10 units
                - work_order duration: 300
                unit_component_cost = (12 * 200 + 60 * 10 + 12 * 100 + 57 * 25) + (50 * 3)) = 5625
                unit_duration = 300 / 10 = 30
                unit_workcenter_cost = 100 * 30'unit_duration' = 50
                unit_cost = 5623 + 50 = 5675

            2:/ MO2:
                - update plywood_sheet cost to: $300
                - qty to produce: 20 units
                - work order duration: 600
                unit_component_cost = (12 * 300 + 60 * 10 + 12 * 100 + 57 * 25) + (50 * 3)) = 6825
                unit_duration = 600 / 20 = 30
                unit_workcenter_cost = 100 * 30'unit_duration' = 50
                unit_cost = 6825 + 50 = 6875

            total_qty_produced = 30
            avg_unit_component_cost = ((5625 * 10) + (6825 * 20)) / 30 = $6425
            avg_unit_workcenter_cost = ((50*20) + (50*10)) / 30 = $50
            avg_unit_duration = (600 + 300) / 30 = 30
            avg_unit_cost = avg_unit_component_cost + avg_unit_workcenter_cost = $6475
        """
        self.table_head.categ_id = self.category_avco
        self.bom_2.type = 'normal'
        self.bom_2.uom_id = self.uom

        # MO_1
        mo_1 = self._create_mo(self.bom_2, 10)
        mo_1.button_plan()
        wo = mo_1.workorder_ids
        wo.button_start()
        wo.duration = 100  # 3 wo * 100 = 300
        wo.qty_producing = 10

        mo_1.button_mark_done()

        # Advance one second so the price update and MO2 are strictly after MO1's
        # valuation, instead of sharing MO1's timestamp under the frozen date.
        with freeze_time(datetime.now() + timedelta(seconds=1)):
            self.plywood_sheet.standard_price = 300
            # MO_2
            self.glass.standard_price = 30
            mo_2 = self._create_mo(self.bom_2, 20)
            mo_2.button_plan()
            wo = mo_2.workorder_ids
            wo.button_start()
            wo.duration = 200
            wo.qty_producing = 20

            mo_2.button_mark_done()

        # must flush else SQL request in report is not accurate
        self.env.flush_all()

        report = self.env['mrp.report']._read_group(
            [('product_id', '=', self.table_head.id)],
            aggregates=['unit_cost:avg', 'unit_component_cost:avg', 'unit_workcenter_cost:avg', 'unit_duration:avg'],
        )[0]
        unit_cost, unit_component_cost, unit_workcenter_cost, unit_duration = report
        self.assertEqual(self.company.currency_id.round(unit_cost), 6475)
        self.assertEqual(self.company.currency_id.round(unit_component_cost), 6425)
        self.assertEqual(self.company.currency_id.round(unit_workcenter_cost), 50)
        self.assertEqual(self.company.currency_id.round(unit_duration), 30)

    def test_report_uom_conversion_quantities_and_costs(self):
        """Ensure mrp.report correctly handles UoM conversions when aggregating MOs.
            Scenario:
            - Product with UoM = Unit
            - BoM: 1 unit of component C1 with cost = $10

            Create two MOs with different UoMs:
            - MO1 in Dozen (produce 1 dozen = 12 units)
            - MO2 in Unit (produce 1 unit)

            The report should:
            - Convert all quantities into the product's UoM (Unit)
            - Keep consistent unit costs across MOs
            - Aggregate quantities correctly

            Expected:
            - Total produced quantity = 13 units
            - Unit cost = $10
        """
        # Set component cost
        self.bom_2.type = 'normal'
        self.bom_2.uom_id = self.env.ref('uom.product_uom_unit').id
        self.bom_2.bom_line_ids = self.bom_2.bom_line_ids[0]
        self.bom_2.bom_line_ids.product_id.standard_price = 10
        self.bom_2.bom_line_ids.product_qty = 1
        self.bom_2.operation_ids = False  # Remove operation to simplify the test and focus on UoM conversion
        # Mo1: Dozen
        mo = self.env['mrp.production'].create({
            'bom_id': self.bom_2.id,
            'uom_id': self.env.ref('uom.product_uom_dozen').id,
            'product_qty': 1,
        })
        mo.action_confirm()
        mo.move_raw_ids.quantity = 12
        mo.move_raw_ids.picked = True
        mo.button_mark_done()
        self.assertEqual(mo.state, 'done')
        # must flush else SQL request in report is not accurate
        self.env.flush_all()
        report = self.env['mrp.report']._read_group(
            [('product_id', '=', self.bom_2.product_id.id)],
            aggregates=['unit_cost:avg', 'unit_component_cost:avg', 'qty_produced:sum'],
        )[0]
        unit_cost, unit_component_cost, qty_produced = report
        self.assertEqual(unit_cost, 10)
        self.assertEqual(unit_component_cost, 10)
        self.assertEqual(qty_produced, 12)
        # Mo2: Unit
        mo_2 = self.env['mrp.production'].create({
            'bom_id': self.bom_2.id,
        })
        mo_2.action_confirm()
        mo_2.move_raw_ids.quantity = 1
        mo_2.move_raw_ids.picked = True
        mo_2.button_mark_done()
        self.assertEqual(mo_2.state, 'done')
        self.env.flush_all()
        report = self.env['mrp.report']._read_group(
            [('product_id', '=', self.bom_2.product_id.id)],
            aggregates=['unit_cost:avg', 'unit_component_cost:avg', 'qty_produced:sum'],
        )[0]
        unit_cost, unit_component_cost, qty_produced = report
        self.assertEqual(unit_cost, 10)
        self.assertEqual(unit_component_cost, 10)
        self.assertEqual(qty_produced, 13)
