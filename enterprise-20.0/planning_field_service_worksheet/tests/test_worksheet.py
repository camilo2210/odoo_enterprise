# Part of Odoo. See LICENSE file for full copyright and licensing details
from markupsafe import Markup

from odoo.tests import Form, tagged, TransactionCase, freeze_time


@freeze_time('2025-01-01 08:00:00')
@tagged('post_install', '-at_install')
class TestWorksheet(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.worksheet_template = cls.env['worksheet.template'].create({
            'name': 'New worksheet',
            'res_model': 'planning.slot',
            'worksheet_properties_definition': [
                {'name': 'a', 'type': 'char', 'string': 'Serial Number', 'default': False},
                {'name': 'product_separator', 'type': 'separator', 'string': 'Product Info', 'fold_by_default': False},
                {'name': 'product_code', 'type': 'char', 'string': 'Product Code', 'default': False},
                {'name': 'part_separator', 'type': 'separator', 'string': 'Part Info', 'fold_by_default': False},
                {'name': 'part_number', 'type': 'integer', 'string': 'Part Number', 'default': False}
            ],
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Costumer A'})
        cls.intervention = cls.env['planning.slot'].create({
            'partner_id': cls.partner.id,
            'start_datetime': '2025-01-01 08:00:00',
            'end_datetime': '2025-01-01 12:00:00',
        })

    def test_send_reports_in_batches(self):
        """
        This test ensures that implementation of sending batches in reports is working.
        """
        self.env['res.config.settings'].create({'group_field_service_allow_customer_report': True}).execute()
        interventions = self.env['planning.slot'].create([
            {
                'partner_id': self.partner.id,
                'worksheet_template_id': self.worksheet_template.id,
                'start_datetime': '2022-01-01 00:00:00',
                'end_datetime': '2022-01-01 01:00:00',
                'state': '4_completed',
            },
            {
                'partner_id': self.partner.id,
                'worksheet_template_id': False,
                'start_datetime': '2022-01-02 00:00:00',
                'end_datetime': '2022-01-02 01:00:00',
            },
        ])
        interventions.state = '4_completed'
        interventions[0].worksheet_properties = {'a': 'b'}
        intervention_1, intervention_2 = interventions
        self.assertEqual(
            intervention_2.action_send_report()['params']['message'],
            'There are no reports to send.', 'Intervention with no report raise a toast message',
        )
        self.assertEqual(
            intervention_1.action_send_report()["context"]["report_action"]["context"]["default_res_ids"],
            intervention_1.ids,
            'Intervention with report is being sent others are ignored',
        )
        intervention_2.write({
            'worksheet_template_id': self.worksheet_template.id,
        })
        action = intervention_1.action_send_report()
        self.assertEqual(
            action["context"]["report_action"]["context"]["default_res_ids"],
            intervention_1.ids,
            'Both the interventions with reports are being sent',
        )

    def test_get_props_formatted_data_structure(self):
        """
        Verify that worksheet properties are formatted into the expected UI/PDFs data structure.
        """
        slot = self.env["planning.slot"].create({
            "partner_id": self.partner.id,
            "worksheet_template_id": self.worksheet_template.id,
            "start_datetime": "2022-01-01 00:00:00",
            "end_datetime": "2022-01-01 01:00:00",
            "state": "4_completed",
            "worksheet_properties": {
                "a": "b",
                "product_code": "PROD1",
                "part_separator": True,  # Folded separator; excluded from the formatted output.
                "part_code": "123",
            },
        })
        actual_props = slot._get_props_formatted()
        expected_props = [
            {"type": "char", "name": "Serial Number", "value": Markup("b")},
            {"type": "separator", "name": "Product Info", "value": False},
            {"type": "char", "name": "Product Code", "value": Markup("PROD1")}
        ]
        self.assertListEqual(actual_props, expected_props, "The formatted worksheet properties do not match the expected UI structure.")

    def test_set_worksheet_template_with_multi_company(self):
        """
            Verify the worksheet template based on the project company.
            Steps
                - Create a new company (TestCompany1)
                - Create a worksheet template and set up a company (TestCompany1)
                - Create project
                - Verify the worksheet template and the project company.
                - Set TestCompany1 to the project.
                - Again verify the worksheet template and the project company.
        """

        test_company = self.env['res.company'].create({
            'name': 'TestCompany1',
            'country_id': self.env.ref('base.be').id,
        })
        self.env['worksheet.template'].create({
            'name': 'test worksheet',
            'company_id': test_company.id,
            'res_model': 'planning.slot',
        })
        partner = self.env['res.partner'].create({'name': 'Customer'})

        # Prevent the use of the default worksheet, since there's no company set on it.
        self.env['worksheet.template'].search([('company_id', '=', False)]).unlink()

        with Form(self.env['planning.slot'].with_company(test_company).with_context(default_partner_id=partner.id)) as intervention_form:
            intervention_form.name = "Test Intervention"
            self.assertEqual(intervention_form.company_id, intervention_form.worksheet_template_id.company_id)
            intervention_form.company_id = test_company
            self.assertEqual(intervention_form.company_id, intervention_form.worksheet_template_id.company_id)
