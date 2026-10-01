# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import TestPlanningFieldServiceCommon


@tagged('post_install', '-at_install')
class TestBaseDocumentLayout(TestPlanningFieldServiceCommon):
    def test_get_preview_template(self):
        DocumentLayout = self.env['base.document.layout']
        self.assertEqual(
            DocumentLayout._get_preview_template(),
            "web.report_invoice_wizard_preview",
            "The template should be the default one since there is no active_model and active_id inside the context."
        )
        self.assertEqual(
            DocumentLayout.with_context(active_model='foo.bar', active_id=self.intervention.id)._get_preview_template(),
            "web.report_invoice_wizard_preview",
            "The template should be the default one since the active_model is not `planning.slot` model name."
        )
        self.assertEqual(
            DocumentLayout.with_context(active_model='planning.slot')._get_preview_template(),
            "web.report_invoice_wizard_preview",
            "The template should be the default one since the active_id is not defined in the context."
        )

        # Add context to be able to check the override
        DocumentLayout = DocumentLayout.with_context(active_model='planning.slot', active_id=self.intervention.id)
        self.assertEqual(
            DocumentLayout._get_preview_template(),
            "planning_field_service.worksheet_custom_preview",
            "The template should be the planning_field_service one since the active_model is `planning.slot` and active_id is defined."
        )

    def test_get_render_information(self):
        DocumentLayout = self.env['base.document.layout'].with_context(active_model='planning.slot', active_id=self.intervention.id)
        document_layout = DocumentLayout.new()
        styles = document_layout._get_asset_style()
        render_information = document_layout._get_render_information(styles)
        self.assertEqual(render_information['doc'], self.intervention)
