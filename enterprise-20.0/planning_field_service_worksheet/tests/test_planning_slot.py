# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo.tests import tagged
from odoo.addons.planning_field_service.tests.common import TestPlanningFieldServiceCommon


@tagged('post_install', '-at_install')
class TestPlanningSlot(TestPlanningFieldServiceCommon):
    def test_action_send_report(self):
        self.env['res.config.settings'].create({'group_field_service_allow_customer_report': False}).execute()
        action = self.intervention.action_send_report()
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'display_notification')
        self.assertDictEqual(
            action['params'],
            {
                'message': 'There are no reports to send.',
                'sticky': False,
                'type': 'danger',
            },
            "No report should be sent since the intervention is not yet completed and the customer report feature is not enabled"
        )

        self.env['res.config.settings'].create({'group_field_service_allow_customer_report': True}).execute()
        action = self.intervention.action_send_report()
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'display_notification')
        self.assertDictEqual(
            action['params'],
            {
                'message': 'There are no reports to send.',
                'sticky': False,
                'type': 'danger',
            },
            "No report should be sent since the intervention is not yet completed"
        )

        self.intervention.state = '4_completed'
        report_action = self.intervention._get_send_report_action()
        self.assertEqual(report_action['type'], 'ir.actions.act_window')
        self.assertEqual(report_action['res_model'], 'mail.compose.message')
        self.assertEqual(report_action['target'], 'new')
        self.assertDictEqual(
            report_action['context'],
            {
                'default_composition_mode': 'comment',
                'default_model': 'planning.slot',
                'default_res_ids': self.intervention.ids,
                'default_template_id': self.env.ref('planning_field_service.mail_template_data_intervention_report').id,
            },
            "The action should be the one to send a report"
        )

        worksheet_template = self.env['worksheet.template'].create({
            'name': 'New worksheet',
            'res_model': 'planning.slot',
            'worksheet_properties_definition': [{
                'name': 'a', 'type': 'char', 'string': 'Serial Number', 'default': False,
            }],
        })
        self.intervention.worksheet_template_id = worksheet_template.id
        self.env.company.external_report_layout_id = False  # make sure no layout exists
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'display_notification')
        self.assertDictEqual(
            action['params'],
            {
                'message': 'There are no reports to send.',
                'sticky': False,
                'type': 'danger',
            },
            "No report should be sent since the worksheet inside the intervention is not yet filled in"
        )
        self.intervention.worksheet_properties = {'a': 'b'}
        action = self.intervention.action_send_report()
        self.assertDictEqual(
            action['context']['report_action'],
            report_action,
            "The action returned should be the report one"
        )

    def test_action_sign_report(self):
        self.env['res.config.settings'].create({'group_field_service_allow_customer_report': True}).execute()
        self.intervention.state = '4_completed'
        worksheet_template = self.env['worksheet.template'].create({
            'name': 'New worksheet',
            'res_model': 'planning.slot',
            'worksheet_properties_definition': [{
                'name': 'a', 'type': 'char', 'string': 'Serial Number', 'default': False,
            }],
        })
        self.intervention.worksheet_template_id = worksheet_template
        self.intervention.worksheet_properties = {'a': 'b'}
        action = self.intervention.action_sign_report()
        action_preview_worksheet = self.intervention.action_preview_worksheet()
        self.assertIn(
            action_preview_worksheet["url"],
            action["url"],
            "The action returned should be the redirection to intervention inside portal."
        )
        self.assertIn(
            "is_sign_report=true",
            action["url"],
            "The sign report action should add the is_sign_report flag to the URL."
        )
