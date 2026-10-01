from odoo import models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _prepare_invoice_vals(self):
        # EXTENDS 'point_of_sale'
        vals = super()._prepare_invoice_vals()
        if self.company_id.country_id.code == 'EC':
            if len(self.payment_ids) > 1:
                vals['l10n_ec_sri_payment_id'] = self.env['l10n_ec.sri.payment'].search([("code", "=", "mpm")]).id
            elif self.payment_ids:
                vals['l10n_ec_sri_payment_id'] = self.payment_ids.payment_method_id.l10n_ec_sri_payment_id.id
            else:
                vals['l10n_ec_sri_payment_id'] = self.env['l10n_ec.sri.payment'].search([("code", "=", "01")]).id
        return vals

    def _generate_pos_order_invoice(self):
        if self.company_id.account_fiscal_country_id.code == 'EC':
            if sum(self.mapped('amount_total')) > self.config_id.l10n_ec_consumer_final_limit and self.partner_id.vat == "9999999999999":
                raise UserError(self.env._(
                    "Following order(s) exceeds the maximum amount allowed for an unidentified consumer.\n"
                    "Please select the real customer with a valid RUC/ID before continuing:\n\n"
                    "%(orders_name)s", orders_name="\n".join(self.mapped('name'))
                ))
        return super()._generate_pos_order_invoice()
