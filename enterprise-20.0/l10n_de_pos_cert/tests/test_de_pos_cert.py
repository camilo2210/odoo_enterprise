from odoo import Command
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDEPoSCert(TestPoSCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_get_cash_statement_cases_trimms_cash_reasons_to_40(self):
        self.basic_config.open_ui()
        current_session = self.basic_config.current_session_id
        current_session.try_cash_in_out(
            "in",
            10,
            "geldtransit-this is a long reason to test that 40+ cash in/out reasons will not break",
            self.partner.id,
        )

        statements = current_session.get_cash_statement_cases([])
        self.assertEqual([statement for statement in statements if len(statement['name']) > 40], [])

    def test_get_cash_statement_cases_keep_casing(self):
        self.basic_config.open_ui()
        current_session = self.basic_config.current_session_id
        current_session.set_opening_control(0, "")
        current_session.try_cash_in_out(
            "in",
            10,
            "reaSoNwithUpPerCase-reason",
            self.partner.id,
        )

        statements = current_session.get_cash_statement_cases([])
        self.assertEqual(statements[2]['type'], "ReaSoNwithUpPerCase")

    def test_cash_point_closing_buyer_of_partner_without_name(self):
        """`res.partner.name` is optional: an address contact is displayed with the name of
        its parent, so the buyer block must not be built from `name` alone."""
        self.config = self.basic_config
        self.config.open_ui()
        session = self.config.current_session_id
        parent = self.env['res.partner'].create({'name': 'Spice Mart GmbH', 'is_company': True})
        nameless_child = self.env['res.partner'].create({'parent_id': parent.id, 'type': 'delivery'})
        self.assertFalse(nameless_child.name)

        product = self.create_product('Paprika', self.categ_basic, 10.0)
        orders = self.env['pos.order']
        for partner in (parent, nameless_child):
            order = self.env['pos.order'].create({
                'company_id': self.env.company.id,
                'session_id': session.id,
                'partner_id': partner.id,
                'lines': [Command.create({
                    'name': 'OL/0001',
                    'product_id': product.id,
                    'full_product_name': product.name,
                    'price_unit': 10.0,
                    'qty': 1,
                    'tax_ids': False,
                    'price_subtotal': 10.0,
                    'price_subtotal_incl': 10.0,
                })],
                'pricelist_id': self.config.pricelist_id.id,
                'amount_paid': 10.0,
                'amount_total': 10.0,
                'amount_tax': 0.0,
                'amount_return': 0.0,
            })
            self.make_payment(order, self.cash_pm1, 10.0)
            orders |= order

        closing_data = session._get_dsfinvk_cash_point_closing_data(orders=orders, total_cash=30.0, total_bank=0)

        buyer_names = {
            transaction['head']['buyer']['buyer_export_id']: transaction['head']['buyer']['name']
            for transaction in closing_data['transactions']
        }
        self.assertEqual(buyer_names, {
            str(parent.id): 'Spice Mart GmbH',
            str(nameless_child.id): 'Spice Mart GmbH, Delivery',
        })
