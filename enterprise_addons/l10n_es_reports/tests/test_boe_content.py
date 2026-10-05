from freezegun import freeze_time
from unittest.mock import patch
import odoo.release

from odoo.addons.l10n_es_reports.tests.common import TestEsAccountReportsCommon
from odoo.tools import file_open
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nEsBOEContent(TestEsAccountReportsCommon):
    _test_user_groups = None  # FIXME list needed groups

    @freeze_time('2025-02-15')
    def test_boe_generation_modelo_111(self):
        self.init_invoice(
            'in_invoice',
            partner=self.spanish_partner,
            amounts=[10000],
            invoice_date='2025-01-31',
            taxes=self.spanish_test_tax,
            post=True)
        report = self.env.ref('l10n_es.mod_111')
        options = self._generate_options(report, '2025-01-01', '2025-01-31')
        with patch.object(odoo.release, 'version', '19.1a1'):
            generated_111_boe = self._get_report_boe(report, 111, options).get('file_content')
        with file_open("l10n_es_reports/tests/data/expected_mod111.txt", "rt") as f:
            expected_boe = f.read()
        self.assertEqual(generated_111_boe, expected_boe.strip())

    @freeze_time('2025-02-15')
    def test_boe_generation_modelo_115(self):
        self.init_invoice(
            'in_invoice',
            partner=self.spanish_partner,
            amounts=[20000],
            invoice_date='2025-01-31',
            taxes=self.spanish_test_tax, post=True)
        report = self.env.ref('l10n_es.mod_115')
        options = self._generate_options(report, '2025-01-01', '2025-01-31')
        with patch.object(odoo.release, 'version', '19.1a1'):
            generated_115_boe = self._get_report_boe(report, 115, options).get('file_content')
        with file_open("l10n_es_reports/tests/data/expected_mod115.txt", "rt") as f:
            expected_boe = f.read()
        self.assertEqual(generated_115_boe, expected_boe.strip())

    @freeze_time('2025-04-15')
    def test_boe_generation_modelo_303(self):
        self.init_invoice(
            'out_invoice',
            partner=self.spanish_partner,
            amounts=[50000],
            invoice_date='2025-01-31',
            taxes=self.spanish_test_tax,
            post=True
        )

        self.init_invoice(
            'in_invoice',
            partner=self.spanish_partner,
            amounts=[10000],
            invoice_date='2025-01-31',
            taxes=self.spanish_test_tax,
            post=True
        )

        report = self.env.ref('l10n_es.mod_303')
        options = self._generate_options(report, '2025-01-01', '2025-01-31')
        with patch.object(odoo.release, 'version', '19.1a1'):
            generated_303_boe = self._get_report_boe(report, 303, options).get('file_content')
        with file_open("l10n_es_reports/tests/data/expected_mod303.txt", "rt") as f:
            expected_boe = f.read()

        self.assertEqual(generated_303_boe, expected_boe.strip())
