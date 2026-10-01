from datetime import datetime

from odoo.tests import tagged

from odoo.addons.sale_planning.tests.common import TestCommonSalePlanning


@tagged('post_install', '-at_install')
class TestForecastReportAnalysis(TestCommonSalePlanning):
    """ Check the measures of the 'Planning & Timesheets Analysis' report.

        The report unions the planning slots (the 'planned' measures) and the
        timesheets (the 'effective' measures) of a project.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_joseph.write({
            'hourly_cost': 20.0,
            'resource_calendar_id': cls.env.company.resource_calendar_id.id,
        })
        cls.consulting_product = cls.env['product.product'].create({
            'name': 'Consulting',
            'type': 'service',
            'uom_id': cls.env.ref('uom.product_uom_hour').id,
            'invoice_policy': 'delivery',
            'service_type': 'timesheet',
            'service_tracking': 'no',
            'planning_enabled': True,
            'planning_role_id': cls.planning_role_junior.id,
            'taxes_id': False,
        })
        cls.project = cls.env['project.project'].create({
            'name': 'Consulting Project',
            'allow_timesheets': True,
            'allow_billable': True,
            'partner_id': cls.planning_partner.id,
        })
        sale_order = cls.env['sale.order'].create({'partner_id': cls.planning_partner.id})
        cls.sale_line = cls.env['sale.order.line'].create({
            'order_id': sale_order.id,
            'product_id': cls.consulting_product.id,
            'product_uom_qty': 20,
            'price_unit': 100.0,
        })
        sale_order.action_confirm()

    def _read_report(self, line_type, aggregates):
        return self.env['project.timesheet.forecast.report.analysis']._read_group(
            [('project_id', '=', self.project.id), ('line_type', '=', line_type)],
            aggregates=aggregates,
        )[0]

    def test_planned_measures(self):
        """ The planned measures spread the allocated hours of a slot over its working
            days, and value them with the cost of the employee and the price of the SOL.
        """
        self.env['planning.slot'].create([{
            'project_id': self.project.id,
            'resource_ids': self.employee_joseph.resource_id.ids,
            'start_datetime': datetime(2025, 1, 22, 8, 0),
            'end_datetime': datetime(2025, 1, 22, 17, 0),
            'sale_line_id': self.sale_line.id,
        }, {
            'project_id': self.project.id,
            'resource_ids': self.employee_joseph.resource_id.ids,
            'start_datetime': datetime(2025, 1, 23, 8, 0),
            'end_datetime': datetime(2025, 1, 23, 12, 0),
        }])
        self.env['planning.slot'].flush_model()

        hours, costs, revenues, margin, billable_hours, non_billable_hours = self._read_report('forecast', [
            'planned_hours:sum', 'planned_costs:sum', 'planned_revenues:sum',
            'planned_margin:sum', 'planned_billable_hours:sum', 'planned_non_billable_hours:sum',
        ])
        self.assertEqual(hours, 12.0, "8 hours planned on the first slot and 4 on the second one")
        self.assertEqual(costs, 240.0, "12 planned hours at a cost of 20/hour")
        self.assertEqual(revenues, 800.0, "Only the 8 hours linked to the sales order item are sold, at 100/hour")
        self.assertEqual(margin, 640.0, "800 of revenues minus the 160 of costs of the billable slot")
        self.assertEqual(billable_hours, 8.0)
        self.assertEqual(non_billable_hours, 4.0)

    def test_effective_measures(self):
        """ The effective measures come from the timesheets, valued with the cost of the
            employee and the price of the sales order item they are linked to.
        """
        self.env['account.analytic.line'].create([{
            'name': 'Billable timesheet',
            'project_id': self.project.id,
            'employee_id': self.employee_joseph.id,
            'date': datetime(2025, 1, 22),
            'unit_amount': 5.0,
            'so_line': self.sale_line.id,
            'is_so_line_edited': True,
        }, {
            'name': 'Non-billable timesheet',
            'project_id': self.project.id,
            'employee_id': self.employee_joseph.id,
            'date': datetime(2025, 1, 23),
            'unit_amount': 2.0,
            'so_line': False,
            'is_so_line_edited': True,
        }])
        self.env['account.analytic.line'].flush_model()

        hours, costs, revenues, margin, billable_hours, non_billable_hours = self._read_report('timesheet', [
            'effective_hours:sum', 'effective_costs:sum', 'effective_revenues:sum',
            'effective_margin:sum', 'effective_billable_hours:sum', 'effective_non_billable_hours:sum',
        ])
        self.assertEqual(hours, 7.0, "5 hours timesheeted on the sales order item and 2 without")
        self.assertEqual(costs, 140.0, "7 timesheeted hours at a cost of 20/hour")
        self.assertEqual(revenues, 500.0, "Only the 5 billable hours generate revenues, at 100/hour")
        self.assertEqual(margin, 400.0, "500 of revenues minus the 100 of costs of the billable timesheet")
        self.assertEqual(billable_hours, 5.0)
        self.assertEqual(non_billable_hours, 2.0)

    def test_planned_and_effective_measures_do_not_mix(self):
        """ A planning slot has no effective measure, and a timesheet no planned one. """
        self.env['planning.slot'].create({
            'project_id': self.project.id,
            'resource_ids': self.employee_joseph.resource_id.ids,
            'start_datetime': datetime(2025, 1, 22, 8, 0),
            'end_datetime': datetime(2025, 1, 22, 17, 0),
            'sale_line_id': self.sale_line.id,
        })
        self.env['account.analytic.line'].create({
            'name': 'Billable timesheet',
            'project_id': self.project.id,
            'employee_id': self.employee_joseph.id,
            'date': datetime(2025, 1, 22),
            'unit_amount': 5.0,
            'so_line': self.sale_line.id,
            'is_so_line_edited': True,
        })
        self.env['planning.slot'].flush_model()
        self.env['account.analytic.line'].flush_model()

        effective_aggregates = [
            'effective_hours:sum', 'effective_costs:sum',
            'effective_billable_hours:sum', 'effective_non_billable_hours:sum',
        ]
        planned_aggregates = [
            'planned_hours:sum', 'planned_costs:sum',
            'planned_billable_hours:sum', 'planned_non_billable_hours:sum',
        ]
        self.assertEqual(self._read_report('forecast', effective_aggregates), (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(self._read_report('timesheet', planned_aggregates), (0.0, 0.0, 0.0, 0.0))
