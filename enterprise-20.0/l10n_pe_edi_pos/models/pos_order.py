from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

from odoo.addons.l10n_pe_edi.models.account_move import REFUND_REASON


class PosOrder(models.Model):
    _inherit = 'pos.order'

    l10n_pe_edi_refund_reason = fields.Selection(
        selection=REFUND_REASON,
        string="Credit Reason",
        help="It contains all possible values for the refund reason according to Catalog No. 09",
    )
    l10n_pe_edi_data = fields.Json(string="Edi Data", compute='_compute_pe_edi_data')

    @api.depends('account_move')
    def _compute_pe_edi_data(self):
        for order in self:
            if order.account_move:
                order.account_move.invalidate_recordset(fnames=['l10n_pe_edi_attachment_file'])
                order.l10n_pe_edi_data = order.account_move._l10n_pe_edi_get_extra_report_values()
            else:
                order.l10n_pe_edi_data = {}

    # -------------------------------------------------------------------------
    # OVERRIDES
    # -------------------------------------------------------------------------

    def action_pos_order_invoice(self):
        # EXTENDS 'point_of_sale'
        if self.country_code == 'PE' and self.refunded_order_id and not self.refunded_order_id.account_move:
            raise UserError(_("You cannot invoice this refund since the related order is not invoiced yet."))
        return super().action_pos_order_invoice()

    def _prepare_invoice_vals(self):
        # EXTENDS 'point_of_sale'
        vals = super()._prepare_invoice_vals()
        if all(rec.country_code == 'PE' for rec in self):
            refunded_move = self.refunded_order_id.account_move
            if len(refunded_move) > 1:
                raise UserError(_("You cannot refund several invoices at once."))
            if not all(order.refunded_order_id.account_move == refunded_move for order in self):
                raise UserError(_("You cannot consolidate refund and non-refund orders together."))
            if refunded_move:
                refund_reasons = set(self.mapped('l10n_pe_edi_refund_reason'))
                if len(refund_reasons) != 1:
                    raise UserError(_("You cannot consolidate refund orders that don't share the same refund reason."))
                vals['l10n_pe_edi_refund_reason'] = next(iter(refund_reasons))
                refunded_invoice_code = refunded_move.l10n_latam_document_type_id.code
                if refunded_invoice_code == '01':
                    # refunding a "Factura electrónica" is done through a "Nota de Crédito electrónica"
                    vals['l10n_latam_document_type_id'] = self.env.ref('l10n_pe.document_type07').id
                elif refunded_invoice_code == '03':
                    # refunding a "Boleta de venta electrónica" is done through a "Nota de Crédito Boleta electrónica"
                    vals['l10n_latam_document_type_id'] = self.env.ref('l10n_pe.document_type07b').id
        return vals

    def _generate_pos_order_invoice(self):
        if self.env.context.get('generate_pdf', True) or not all(order.country_code == 'PE' for order in self):
            return super()._generate_pos_order_invoice()

        orders_needing_invoice = self.filtered(lambda o: not o.account_move)
        result = super()._generate_pos_order_invoice()

        for order in orders_needing_invoice:
            invoice = order.account_move
            if invoice and invoice.l10n_pe_edi_is_required and not invoice._l10n_pe_edi_check_move_constraints():
                error = invoice.sudo()._l10n_pe_edi_post_invoice()
                if error and error.get('message'):
                    invoice.sudo().message_post(body=html2plaintext(error['message']))

        return result

    def read_pos_data(self, data, config):
        result = super().read_pos_data(data, config)

        if (pe_orders := self.filtered(
            lambda order: order.session_id.company_id.country_code == "PE" and order.state in ['paid', 'done'])
            ):
            result['l10n_latam.document.type'] = self.env['l10n_latam.document.type']._load_pos_data_read(pe_orders.account_move.l10n_latam_document_type_id, config)

        return result
