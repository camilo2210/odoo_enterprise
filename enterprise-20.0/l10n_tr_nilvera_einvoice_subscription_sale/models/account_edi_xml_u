from odoo import models


class AccountEdiXmlUblTr(models.AbstractModel):
    _inherit = 'account.edi.xml.ubl.tr'

    def _add_invoice_header_nodes(self, document_node, vals):
        super()._add_invoice_header_nodes(document_node, vals)
        invoice = vals['invoice']
        subscription_line = next(
            (
                line
                for line in invoice.invoice_line_ids.sorted("sequence")
                if line.product_id.recurring_invoice
                and line.deferred_start_date
                and line.deferred_end_date
            ),
            None,
        )
        if subscription_line:
            document_node['cac:InvoicePeriod'] = {
                'cbc:StartDate': {'_text': subscription_line.deferred_start_date},
                'cbc:EndDate': {'_text': subscription_line.deferred_end_date},
            }
