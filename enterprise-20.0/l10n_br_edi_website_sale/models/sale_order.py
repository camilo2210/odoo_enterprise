# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def set_delivery_line(self, carrier, amount):
        """Override. Copy over the default transporter and freight model from the delivery method configuration."""
        res = super().set_delivery_line(carrier, amount)
        for order in self:
            order.l10n_br_edi_transporter_id = carrier.l10n_br_edi_transporter_id
            order.l10n_br_edi_freight_model = carrier.l10n_br_edi_freight_model
        return res

    @api.depends('website_id')
    def _compute_l10n_br_presence(self):
        # Override.
        super()._compute_l10n_br_presence()
        for order in self:
            if order.website_id:
                order.l10n_br_presence = '2'

    def _prepare_invoice(self):
        # Override
        res = super()._prepare_invoice()
        res['l10n_br_presence'] = self.l10n_br_presence
        return res
