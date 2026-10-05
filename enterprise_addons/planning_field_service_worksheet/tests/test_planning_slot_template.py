from odoo.tests import Form, TransactionCase


class TestPlanningSlotTemplate(TransactionCase):

    def test_set_worksheet_template_on_slot_template(self):
        worksheet_template_1, worksheet_template_2 = self.env['worksheet.template'].create([
            {
                'name': 'New worksheet 1',
                'res_model': 'planning.slot',
            },
            {
                'name': 'New worksheet 2',
                'res_model': 'planning.slot',
            },
        ])
        template_1, template_2, template_3 = self.env['planning.slot.template'].create([
            {'worksheet_template_id': worksheet_template_1.id},
            {'worksheet_template_id': worksheet_template_2.id},
            {'worksheet_template_id': False},
        ])

        with Form(self.env['planning.slot']) as slot:
            # Check available templates on worksheet_template_1
            slot.worksheet_template_id = worksheet_template_1
            self.assertIn(template_1.id, slot.template_autocomplete_ids.ids, "Template with the same worksheet should be suggested.")
            self.assertNotIn(template_2.id, slot.template_autocomplete_ids.ids, "Template with another worksheet should not be suggested.")
            self.assertIn(template_3.id, slot.template_autocomplete_ids.ids, "Template with no worksheet should be suggested.")
            # Check available templates on worksheet_template_2
            slot.worksheet_template_id = worksheet_template_2
            self.assertNotIn(template_1.id, slot.template_autocomplete_ids.ids, "Template with another worksheet should not be suggested.")
            self.assertIn(template_2.id, slot.template_autocomplete_ids.ids, "Template with the same worksheet should be suggested.")
            self.assertIn(template_3.id, slot.template_autocomplete_ids.ids, "Template with no worksheet should be suggested.")
            # Check available templates when no worksheet template is selected
            slot.worksheet_template_id = self.env['worksheet.template']
            self.assertIn(template_1.id, slot.template_autocomplete_ids.ids, "All templates should be suggested when no worksheet is set.")
            self.assertIn(template_2.id, slot.template_autocomplete_ids.ids, "All templates should be suggested when no worksheet is set.")
            self.assertIn(template_3.id, slot.template_autocomplete_ids.ids, "All templates should be suggested when no worksheet is set.")
            # Select a template and check that that worksheet template is correctly set on the shift
            slot.template_id = template_1
            self.assertEqual(slot.worksheet_template_id, worksheet_template_1)

    def test_slot_template_company_check_with_worksheet_template(self):
        worksheet_template = self.env['worksheet.template'].create({
            'name': 'Worksheet template',
            'res_model': 'planning.slot',
            'company_id': self.env.company.id,
        })
        template = self.env['planning.slot.template'].create({
            'company_id': self.env.company.id,
            'worksheet_template_id': worksheet_template.id,
        })
        company_2 = self.env['res.company'].create({'name': 'Company 2'})
        with Form(template) as slot_template:
            slot_template.company_id = company_2
            self.assertFalse(slot_template.worksheet_template_id, 'The worksheet template should be unset when the company is changed to a company that is different from the one of the worksheet template')
