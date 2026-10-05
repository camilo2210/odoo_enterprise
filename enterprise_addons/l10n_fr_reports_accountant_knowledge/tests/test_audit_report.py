from lxml import html
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nFrAuditReport(TestAccountReportsCommon):

    @classmethod
    @TestAccountReportsCommon.setup_country('fr_comp')
    def setUpClass(cls):
        super().setUpClass()

    def test_fiscal_template_variables(self):
        self.env['account.report.external.value'].create({
            'company_id': self.company_data['company'].id,
            'target_report_expression_id': self.env.ref('l10n_fr_reports.l10n_fr_2033_E_1_1_expr').id,
            'name': 'Average headcount',
            'date': fields.Date.from_string('2025-12-31'),
            'value': 37,
        })
        audit_report = self.env['audit.report'].new({
            'company_id': self.company_data['company'].id,
            'start_date': fields.Date.from_string('2025-01-01'),
            'end_date': fields.Date.from_string('2025-12-31'),
        })

        values = audit_report._get_l10n_fr_knowledge_report_data()

        self.assertEqual(values['average headcount'], '37')
        self.assertEqual(set(values), {
            'gross goodwill',
            'gross inventory',
            'share capital',
            'extraordinary income',
            'extraordinary expenses',
            'research tax credit',
            'average headcount',
        })

    def test_fiscal_template_variables_for_overseas_france(self):
        company = self.company_data['company']
        company.account_fiscal_country_id = self.env.ref('base.gp')
        audit_report = self.env['audit.report'].new({
            'company_id': company.id,
            'start_date': fields.Date.from_string('2025-01-01'),
            'end_date': fields.Date.from_string('2025-12-31'),
        })

        self.assertTrue(audit_report._get_l10n_fr_knowledge_report_data())

    def test_attestation_selection_is_required(self):
        annual_report_template = self.env.ref(
            'l10n_fr_reports_accountant_knowledge.l10n_fr_accountant_knowledge_article_template_annual_report')
        audit_report = self.env['audit.report'].create({
            'title': 'French annual report',
            'company_id': self.company_data['company'].id,
            'start_date': fields.Date.from_string('2025-01-01'),
            'end_date': fields.Date.from_string('2025-12-31'),
            'knowledge_template_article_id': annual_report_template.id,
        })
        attestation_template = self.env.ref(
            'l10n_fr_reports_accountant_knowledge.l10n_fr_accountant_knowledge_article_template_attestation')
        attestation = self.env['knowledge.article'].search([
            ('id', 'child_of', audit_report.knowledge_article_id.id),
            ('origin_template_id', '=', attestation_template.id),
        ])
        audit_report.knowledge_article_id._check_l10n_fr_attestation_selection('1')

        fragment = html.fragment_fromstring(attestation.body, create_parent=True)
        for section in fragment.xpath('.//*[@data-embedded="foldableSection"]'):
            section.classes.add('d-print-none')
        attestation.body = ''.join(
            html.tostring(child, encoding='unicode') for child in fragment.getchildren())
        with self.assertRaisesRegex(UserError, 'Select at least one attestation'):
            audit_report.knowledge_article_id._check_l10n_fr_attestation_selection('1')
