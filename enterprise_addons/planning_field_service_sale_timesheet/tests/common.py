# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo.tests import new_test_user

from odoo.addons.planning_field_service.tests.common import TestPlanningFieldServiceCommon
from odoo.addons.sale_timesheet.tests.common import TestCommonSaleTimesheet


class TestPlanningFieldServiceSaleTimesheetCommon(TestPlanningFieldServiceCommon, TestCommonSaleTimesheet):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_user = new_test_user(cls.env, 'Project user', groups='project.group_project_user')
        cls.project_manager = new_test_user(cls.env, 'Project admin', groups='project.group_project_manager')

        cls.employee_user2 = cls.env['hr.employee'].create({
            'name': 'Employee User 2',
            'hourly_cost': 15,
        })

        cls.employee_user3 = cls.env['hr.employee'].create({
            'name': 'Employee User 3',
            'hourly_cost': 15,
        })

        cls.field_service_project = cls.env['project.project'].create({
            'name': 'Field Service',
            'allow_billable': True,
            'allow_timesheets': True,
            'company_id': cls.env.company.id,
        })

        cls.partner_1 = cls.env['res.partner'].create({'name': 'A Test Partner 1'})

        cls.service_product_ordered = cls.env['product.product'].create({
            'name': 'Individual Workplace',
            'list_price': 885.0,
            'type': 'service',
            'invoice_policy': 'order',
            'taxes_id': False,
        })

        cls.service_product_delivered = cls.env['product.product'].create({
            'name': 'Acoustic Bloc Screens',
            'list_price': 2950.0,
            'type': 'service',
            'invoice_policy': 'delivery',
            'taxes_id': False,
        })

        cls.consu_product_delivered = cls.env['product.product'].create({
            'name': 'Consommable product delivery',
            'list_price': 40,
            'type': 'consu',
            'invoice_policy': 'delivery',
        })

        cls.consu_product_ordered = cls.env['product.product'].create({
            'name': 'Consommable product ordered',
            'list_price': 50.5,
            'type': 'consu',
            'invoice_policy': 'order',
        })

        cls.service_timesheet = cls.env['product.product'].create({
            'name': 'service timesheet',
            'type': 'service',
            'service_policy': 'delivered_timesheet',
        })

        cls.planning_service_product = cls.env['product.product'].create({
            'name': 'Planning service product',
            'type': 'service',
            'planning_enabled': True,
        })

    def set_field_service_project(self, project, intervention):
        if 'project_id' in intervention._fields:
            # Then project_timesheet_forecast_field_service_sale module is installed.
            intervention.project_id = project
        else:
            self.env['res.config.settings'].create({'planning_project_id': project.id}).execute()
