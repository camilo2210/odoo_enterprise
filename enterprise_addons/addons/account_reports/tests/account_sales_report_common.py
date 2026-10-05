# -*- coding: utf-8 -*-
from odoo import fields
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


class AccountSalesReportCommon(TestAccountReportsCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a.write({
            'name': 'Partner A',
            'country_id': cls.env.ref('base.fr').id,
            "vat": "FR23334175221",
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'Partner B',
            'country_id': cls.env.ref('base.be').id,
            "vat": "BE0477472701",
        })
        cls.company.partner_id.update({
            'email': 'jsmith@mail.com',
            'phone': '+32475123456',
        })

    def _create_invoices(self, data, is_refund=False):
        move_vals_list = []
        for move_data in data:
            partner, tax, price_unit = move_data[:3]
            partner_shipping_id = move_data[3] if len(move_data) > 3 else None

            move_vals_list.append({
                'move_type': 'out_refund' if is_refund else 'out_invoice',
                'partner_id': partner.id,
                'partner_shipping_id': partner_shipping_id.id if partner_shipping_id else None,
                'invoice_date': fields.Date.from_string('2019-12-01'),
                'invoice_line_ids': [
                    (0, 0, {
                        'name': 'line_1',
                        'price_unit': price_unit,
                        'quantity': 1.0,
                        'account_id': self.company_data['default_account_revenue'].id,
                        'tax_ids': [(6, 0, tax.ids)],
                    }),
                ],
            })
        moves = self.env['account.move'].create(move_vals_list)
        moves.action_post()
