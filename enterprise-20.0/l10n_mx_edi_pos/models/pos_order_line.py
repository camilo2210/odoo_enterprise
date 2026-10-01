from odoo import api, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    @api.constrains('refunded_orderline_id', 'price_subtotal')
    def _l10n_mx_edi_constrains_refunded_orderline_id(self):
        self.order_id._l10n_mx_edi_constrains_amount_total()

    def _l10n_mx_edi_cfdi_lines(self):
        """ Filter the order lines to be considered when creating the CFDI.

        :return: A recordset of order lines.
        """
        return self.filtered(lambda line: not line.order_id.currency_id.is_zero(line.price_unit * line.qty))

    def _prepare_base_lines_for_taxes_computation(self):
        # EXTENDS 'point_of_sale'
        base_lines = super()._prepare_base_lines_for_taxes_computation()
        for index, line in enumerate(self):
            if (
                line.order_id.country_code == 'MX'
                and line.order_id.is_refund_or_negative()
                and line.company_id.l10n_mx_income_return_discount_account_id
            ):
                base_lines[index]['account_id'] = line.company_id.l10n_mx_income_return_discount_account_id
            elif (
                line.order_id.country_code == 'MX'
                and line.order_id.session_id.state == 'closed'
                and line.company_id.l10n_mx_income_re_invoicing_account_id
            ):
                base_lines[index]['account_id'] = line.company_id.l10n_mx_income_re_invoicing_account_id

        return base_lines
