from odoo.tests import tagged, HttpCase, loaded_demo_data


@tagged('post_install', '-at_install')
class TestPlanningFieldServiceUi(HttpCase):
    def test_planning_field_service_onboarding_tour(self):
        # Set default layout to check if the action returned by `action_send_report` is the report action
        if loaded_demo_data(self.env):
            self.skipTest("The tour cannot work with demo data.")
        self.env.company.external_report_layout_id = self.env.ref('web.external_layout_standard').id
        admin_user = self.env['res.users'].search([('login', '=', 'admin'), ('email', '=', False)])
        if admin_user:  # make sure the admin user has an email set.
            admin_user.email = "admin@test.com"
        self.start_tour('/odoo', 'planning_field_service_tour', login='admin')
