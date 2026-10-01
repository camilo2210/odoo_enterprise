from odoo.tests import tagged

from odoo.addons.hr_timesheet.tests.test_timesheet import TestCommonTimesheet
from odoo.addons.sale_timesheet.tests.common import TestCommonSaleTimesheet


@tagged('-at_install', 'post_install')
class TestTimesheet(TestCommonTimesheet, TestCommonSaleTimesheet):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.grid_start_date = "2020-01-01"
        cls.grid_stop_date = "2020-01-31"

    def _get_kpi_data(self, user):
        with self.with_user(user.login):
            return self.env['account.analytic.line'].get_kpi_data(self.grid_start_date, self.grid_stop_date)

    def test_get_kpi_data_user_without_timesheet_access(self):
        user_without_timesheet_access = self.env['res.users'].create({
            'name': 'User without Timesheet access',
            'login': 'base_user',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        data = self._get_kpi_data(user_without_timesheet_access)
        self.assertFalse(data, "No data should be retrieved if the user does not have Timesheet access")

    def test_get_kpi_data_show_rates_disabled(self):
        self.env.company.write({
            'timesheet_show_rates': False,
        })
        data = self._get_kpi_data(self.user_employee)
        self.assertIn('worked_time', data, "Worked time should be included even if rates are not shown")
        self.assertIn('billable_time', data, "Billable time should be included even if rates are not shown")
        self.assertIn('uom', data, "UOM should be included even if rates are not shown")

    def test_get_kpi_data_show_rates_enabled_and_user_has_no_billable_time_target(self):
        self.env.company.write({
            'timesheet_show_rates': True,
        })
        self.user_employee.employee_id.write({
            'billable_time_target': 0.0,
        })
        data = self._get_kpi_data(self.user_employee)
        self.assertIn('worked_time', data, "Worked time should be included even if rates are not shown")
        self.assertIn('billable_time', data, "Billable time should be included even if rates are not shown")
        self.assertIn('uom', data, "UOM should be included even if rates are not shown")

    def test_get_kpi_data_show_rates_enabled_and_user_has_a_billable_time_target(self):
        uom = self.env['uom.uom'].search([('name', '=', 'Days')])
        self.env.company.write({
            'timesheet_encode_uom_id': uom.id,
            'timesheet_show_rates': True,
        })
        billable_time_target = 150.0
        self.user_employee.employee_id.write({
            'billable_time_target': billable_time_target,
        })

        so_line = self.env['sale.order.line'].search([
            '&', ('order_id', '=', self.so.id), ('product_id', '=', self.product_delivery_timesheet3.id)
        ])
        task = self.env['project.task'].search([('sale_line_id', '=', so_line.id)])
        project = self.env['project.project'].search([('sale_line_id', '=', so_line.id)])
        timesheet_1, timesheet_2, timesheet_3 = self.env['account.analytic.line'].create([
            {
                'name': "Non billable timesheet",
                'project_id': self.project_non_billable.id,
                'employee_id': self.user_employee.employee_id.id,
                'unit_amount': 10.0,
                'date': "2020-01-09",
            },
            {
                'name': "Billable timesheet 1",
                'project_id': project.id,
                'task_id': task.id,
                'employee_id': self.user_employee.employee_id.id,
                'unit_amount': 20.0,
                'date': "2020-01-18",
            },
            {
                'name': "Billable timesheet 2",
                'project_id': project.id,
                'task_id': task.id,
                'employee_id': self.user_employee.employee_id.id,
                'unit_amount': 10.0,
                'date': "2020-01-26",
            },
        ])

        data = self._get_kpi_data(self.user_employee)
        self.assertIn('worked_time', data, "Worked time should be included if rates are shown")
        self.assertIn('billable_time', data, "Billable time should be included if rates are shown")
        self.assertIn('uom', data, "UOM should be included if rates are shown")
        self.assertIn('billable_time_target', data, "Billable time target should be included if rates are shown")
        self.assertIn('billing_rate', data, "Billing rate should be included if rates are shown")

        worked_time = timesheet_1.unit_amount + timesheet_2.unit_amount + timesheet_3.unit_amount
        billable_time = timesheet_2.unit_amount + timesheet_3.unit_amount
        expected_data = {
            'worked_time': worked_time,
            'billable_time': billable_time,
            'uom': uom.name,
            'billable_time_target': billable_time_target,
            'billing_rate': billable_time / billable_time_target,
        }
        self.assertDictEqual(data, expected_data)

    def test_compute_is_billable(self):
        self.env.user.employee_ids = self.env['hr.employee'].create({'user_id': self.env.uid})
        Timesheet = self.env['account.analytic.line']
        Task = self.env['project.task']
        task = Task.with_context(default_project_id=self.project_template.id).create({
            'name': 'first task',
            'partner_id': self.partner_b.id,
            'allocated_hours': 48,
            'sale_line_id': self.so.order_line[0].id,
        })

        self.project_template.allow_billable = True
        self.timesheet = Timesheet.create({
            'project_id': self.project_template.id,
            'task_id': task.id,
            'name': 'my first timesheet',
            'unit_amount': 30,
        })
        self.assertEqual(self.timesheet.so_line, task.sale_line_id)
        self.assertTrue(self.timesheet.is_billable, "is_billable follows so_line ")
        self.timesheet.is_billable = False
        self.assertFalse(self.timesheet.so_line, "os_line is False when is_billable is set to False")
