from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _inter_company_create_invoices(self):
        moves = super()._inter_company_create_invoices()
        for move in moves:
            if (
                (source_invoice := move.auto_invoice_id)
                and (sale_order := source_invoice.line_ids.sale_line_ids.order_id) and len(sale_order) == 1
                and (origin_purchase_order := sale_order.auto_purchase_order_id)
                and origin_purchase_order.company_id == move.company_id
            ):
                pol_by_product = origin_purchase_order.order_line.grouped('product_id')
                aml_by_product = move.line_ids.grouped('product_id')

                # Match all matchable POL-AML lines
                for product, po_line in pol_by_product.items():
                    po_line = po_line[0]  # in case of multiple POL with same product, only match the first one
                    matching_bill_lines = aml_by_product.get(product)
                    if matching_bill_lines:
                        matching_bill_lines.purchase_line_id = po_line.id

        return moves
