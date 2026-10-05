from odoo.addons.planning_field_service_sale_timesheet.tests.common import TestPlanningFieldServiceSaleTimesheetCommon


class TestProjectTimesheetForecastFieldServiceSaleCommon(TestPlanningFieldServiceSaleTimesheetCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.task = cls.env['project.task'].with_context({'mail_create_nolog': True}).create({
            'name': 'Field Service task',
            'user_ids': cls.project_user,
            'project_id': cls.field_service_project.id,
         })
