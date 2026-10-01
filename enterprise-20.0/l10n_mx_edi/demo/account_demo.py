from odoo import models, Command

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    def _get_partner_demo_data_ref(self):
        return {
            'base.demo_company_mx': {
                'customer': 'l10n_mx_edi.demo_partner_quadrum_1',
                'factor': 'l10n_mx_edi.demo_partner_quadrum_2'
            },
            'base.demo_company_2_mx': {
                'customer': 'l10n_mx_edi.demo_partner_sapien_1',
                'factor': 'l10n_mx_edi.demo_partner_sapien_2'
            }
        }

    @template(template='mx', model='account.move', demo=True)
    def _l10n_mx_edi_get_demo_data_move(self):
        xml_id = self.env.company.get_external_id().get(self.env.company.id)
        partner_refs = self._get_partner_demo_data_ref()
        if xml_id not in partner_refs:
            return {}

        customer_ref = self._get_partner_demo_data_ref()[xml_id]['customer']
        return {
            self.company_xmlid('demo_invoice_mx_1'): {
                'move_type': 'out_invoice',
                'partner_id': customer_ref,
                'invoice_line_ids': [
                    Command.create({'product_id': 'product.consu_delivery_02', 'price_unit': 3000.0, 'quantity': 1}),
                ],
            },
            self.company_xmlid('demo_invoice_mx_2'): {
                'move_type': 'out_invoice',
                'partner_id': customer_ref,
                'invoice_line_ids': [
                    Command.create({'product_id': 'product.consu_delivery_02', 'price_unit': 3000.0, 'quantity': 2}),
                ],
            },
        }

    @template(template='mx', model='account.bank.statement.line', demo=True)
    def _l10n_mx_edi_get_demo_data_transactions(self):
        xml_id = self.env.company.get_external_id().get(self.env.company.id)
        partner_refs = self._get_partner_demo_data_ref()
        if xml_id not in partner_refs:
            return {}

        factor_ref = self._get_partner_demo_data_ref()[xml_id]['factor']
        return {
            self.company_xmlid('demo_mx_bank_statement_line_1'): {
                    'partner_id': factor_ref,
                    'payment_ref': 'PBANK/01/01',
                    'amount': 9000,
                    'journal_id': 'bank',
            },
        }
