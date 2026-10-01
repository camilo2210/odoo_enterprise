from odoo import models
from odoo.exceptions import UserError
from odoo.tools import formatLang


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _prepare_invoice_vals(self):
        move_vals = super()._prepare_invoice_vals()
        if self.config_id.is_guatemalan_company and self.company_id.l10n_gt_edi_phrase_ids:
            move_vals['l10n_gt_edi_phrase_ids'] = self.company_id.l10n_gt_edi_phrase_ids.ids
        return move_vals

    def _generate_pos_order_invoice(self):
        if self.config_id.is_guatemalan_company:
            refunds_without_invoice = self.filtered(
                lambda order: order.is_refund_or_negative() and not order.refunded_order_id.is_singly_invoiced
            )
            if refunds_without_invoice:
                raise UserError(self.env._(
                    "The order linked to this refund has not been electronically invoiced. "
                    "Please make sure the original order has an electronic invoice before "
                    "trying to create an electronic credit note for this refund.\n"
                    "%(orders)s", orders="\n".join([f"{o.name} ({o.pos_reference})" for o in refunds_without_invoice])
                ))

            # Unidentified customers restriction
            commercial_partner = self.partner_id.commercial_partner_id
            is_partner_cf = (
                commercial_partner.id == self.env.ref('l10n_gt_edi.final_consumer').id
            )
            is_unidentified_customer = is_partner_cf or not (
                commercial_partner and commercial_partner._get_preferred_legal_entity_identifier_vals()
            )
            total_amount = sum(self.mapped('amount_total'))
            limit = self.config_id.l10n_gt_final_consumer_limit

            if is_unidentified_customer and total_amount > limit:
                raise UserError(self.env._(
                    "This order exceeds the maximum amount allowed for an unidentified customer.\n"
                    "Maximum allowed amount: %(limit)s\n"
                    "Please select a customer with a valid Identification Type and Number before continuing.\n"
                    "%(orders)s",
                    orders="\n".join([f"{o.name} ({o.pos_reference})" for o in self]),
                    limit=formatLang(self.env, limit, currency_obj=self.currency_id),
                ))

        return super()._generate_pos_order_invoice()
