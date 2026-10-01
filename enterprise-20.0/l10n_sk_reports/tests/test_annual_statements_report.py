# Part of Odoo. See LICENSE file for full copyright and licensing details.
from freezegun import freeze_time
import base64

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.tests import tagged
from odoo.tools import file_open


@tagged('post_install_l10n', 'post_install', '-at_install')
class SlovakiaAnnualStatementsTest(TestAccountReportsCommon):
    _test_user_groups = None  # FIXME list needed groups

    def setUp(self):
        super().setUp()
        company = self.env.company
        company.name = 'Slovakian Company'
        company.income_tax_id = '1234567890'
        company.partner_id.additional_identifiers = {'SK_EN': '12345678'}
        company.zip = '81101'
        company.city = 'Bratislava'
        company.l10n_sk_nace_code = '12345'
        company.totals_below_sections = False

    @freeze_time('2025-12-31')
    def test_generate_l10n_sk_annual_statement_xml(self):
        report = self.env.ref('l10n_sk_reports.l10n_sk_reports_bs_pl')
        options = self._generate_options(report, date_from='2025-01-01', date_to='2025-12-31')
        generated_xml = self.env['l10n_sk.annual.statements.report.handler']._build_xml(options, 'regular', None)
        with file_open('l10n_sk_reports/tests/test_files/UZPODv14_export.xml', 'rb') as expected_xml_file:
            expected_xml = expected_xml_file.read()
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(base64.b64decode(generated_xml)),
            self.get_xml_tree_from_string(expected_xml),
        )
