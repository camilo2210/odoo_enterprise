# Part of Odoo. See LICENSE file for full copyright and licensing details.

from contextlib import contextmanager
from unittest.mock import patch

from odoo import Command
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


class TestL10nEsVATBooksPosCommon(TestPoSCommon, TestAccountReportsCommon):
    """Common test class for VAT Books with POS orders."""

    @classmethod
    @TestAccountReportsCommon.setup_chart_template('es_pymes')
    def setUpClass(cls):
        super().setUpClass()
        cls.maxDiff = None

        cls.company.sudo().write({
            'country_id': cls.env.ref('base.es').id,
            'l10n_es_reports_iae_group': 'A036533',
        })

        company_id = cls.company.id
        cls.tax21_goods = cls.env.ref(f'account.{company_id}_account_tax_template_s_iva21b')
        cls.tax10_goods = cls.env.ref(f'account.{company_id}_account_tax_template_s_iva10b')

        cls.partner_spanish = cls.env['res.partner'].create({
            'country_id': cls.env.ref('base.es').id,
            'name': 'Spanish Partner',
            'vat': 'ES59962470K',
        })
        cls.partner_eu = cls.env['res.partner'].create({
            'country_id': cls.env.ref('base.fr').id,
            'name': 'French Partner',
            'vat': 'FR23334175221',
        })
        cls.partner_intl = cls.env['res.partner'].create({
            'country_id': cls.env.ref('base.us').id,
            'name': 'US Company',
            'vat': 'US66655598K',
        })
        cls.partner_no_vat = cls.env['res.partner'].create({
            'country_id': cls.env.ref('base.es').id,
            'name': 'Spanish Partner No VAT',
        })

        cls.product_10 = cls.env['product.product'].create({
            'name': 'vat_books_pos_product_10',
            'default_code': 'product_vat_books_10',
            'lst_price': 100.0,
            'property_account_income_id': cls.company_data['default_account_revenue'].id,
            'property_account_expense_id': cls.company_data['default_account_expense'].id,
            'taxes_id': [Command.set(cls.tax10_goods.ids)],
            'company_id': cls.company.id,
            'available_in_pos': True,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'vat_books_pos_product',
            'default_code': 'product_vat_books',
            'lst_price': 100.0,
            'property_account_income_id': cls.company_data['default_account_revenue'].id,
            'property_account_expense_id': cls.company_data['default_account_expense'].id,
            'taxes_id': [Command.set(cls.tax21_goods.ids)],
            'company_id': cls.company.id,
            'available_in_pos': True,
        })

    @contextmanager
    def with_pos_session(self):
        session = self.open_new_session(0.0)
        yield session
        cash_pm = self.config._get_cash_payment_method()
        session.close_session_from_ui({
            cash_pm.id: 0,
        })

    @contextmanager
    def with_pos_edi_mode(self, mode='tbai'):
        company_model = self.env.registry['res.company']

        def _l10n_es_get_pos_edi_mode(company):
            company.ensure_one()
            return mode

        with patch.object(company_model, '_l10n_es_get_pos_edi_mode', _l10n_es_get_pos_edi_mode):
            yield

    def get_vat_book_sheet_line_vals(self, date_from='2024-01-01', date_to='2024-12-31'):
        options = {'date': {'date_from': date_from, 'date_to': date_to}}
        with self.with_pos_edi_mode():
            return self.get_pos_sheet_line_vals(options)

    def get_pos_sheet_line_vals(self, options):
        if not self.env.company._l10n_es_get_pos_edi_mode():
            return []
        report = self.env['l10n_es.vat.books.report.handler']
        return [
            line_vals
            for pos_order_ids in report._l10n_es_libros_iter_pos_order_batches(options)
            for pos_order in self.env['pos.order'].browse(pos_order_ids)
            for line_vals in report._l10n_es_libros_get_pos_order_sheet_line_vals(pos_order)
        ]

    def get_pos_closing_sheet_line_vals(self, date_from='2024-01-01', date_to='2024-12-31'):
        report_obj = self.env.ref('account.generic_tax_report')
        options = self._generate_options(report_obj, date_from, date_to)
        domain = report_obj._get_options_domain(options, 'strict_range') + [
            ('move_id.pos_session_ids', '!=', False),
        ]
        lines = self.env['account.move.line'].search(domain)
        handler = self.env['l10n_es.vat.books.report.handler']
        inc_line_vals, _exp = handler._l10n_es_libros_get_sheet_line_vals(lines)
        return [lv for move_vals in inc_line_vals.values() for lv in move_vals.values()]

    def _create_pos_order(self, **kwargs):
        """Create a single POS order inside a new session and return it."""
        with self.with_pos_session():
            order_data = self.create_ui_order_data(**kwargs)
            results = self.env['pos.order'].sync_from_ui([order_data])
            return self.env['pos.order'].browse(results['pos.order'][0]['id'])

    def _create_pos_orders(self, orders_data):
        """Create multiple POS orders in a single session and return them."""
        with self.with_pos_session():
            results = self.env['pos.order'].sync_from_ui([
                self.create_ui_order_data(**od)
                for od in orders_data
            ])
            return self.env['pos.order'].browse([r['id'] for r in results['pos.order']])
