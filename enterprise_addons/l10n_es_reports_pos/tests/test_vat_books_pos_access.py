# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from freezegun import freeze_time

from odoo.tests import tagged

from .common import TestL10nEsVATBooksPosCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestVATBooksPosAccess(TestL10nEsVATBooksPosCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.fakenow = datetime.datetime(2024, 1, 1)
        cls.startClassPatcher(freeze_time(cls.fakenow))

    def _export_as(self, user):
        report = self.env.ref('account.generic_tax_report')
        options = self._generate_options(report, '2024-01-01', '2024-12-31')
        self.env.invalidate_all()
        handler = self.env['l10n_es.vat.books.report.handler'].with_user(user)
        return handler.export_libros_de_iva(options)

    def test_vat_books_export_as_accounting_user(self):
        """Test that a user with accounting-only access is able to export the
           VAT books report succesfully in Non-EDI mode
        """
        self._create_pos_order(
            customer=self.partner_spanish,
            pos_order_lines_ui_args=[(self.product, 1.0)],
            payments=[(self.bank_pm1, 121.0)],
        )
        result = self._export_as(self.simple_accountman)
        self.assertEqual(result['file_type'], 'xlsx')
        self.assertTrue(result['file_content'])

    def test_vat_books_export_as_accounting_user_edi(self):
        """Test that a user with accounting-only access is able to export the
           VAT books report succesfully in Tbai/Verificatu mode
        """
        self._create_pos_order(
            customer=self.partner_spanish,
            pos_order_lines_ui_args=[(self.product, 1.0)],
            payments=[(self.bank_pm1, 121.0)],
        )
        with self.with_pos_edi_mode():
            result = self._export_as(self.simple_accountman)
        self.assertEqual(result['file_type'], 'xlsx')
        self.assertTrue(result['file_content'])
