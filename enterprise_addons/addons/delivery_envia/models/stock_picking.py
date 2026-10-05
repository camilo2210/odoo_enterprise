# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_carrier_name(self):
        """Override of stock_delivery to return the actual carrier code for Envia shipments."""
        if self.carrier_id.delivery_type == 'envia' and self.carrier_id.envia_carrier_code:
            return self.carrier_id.envia_carrier_code
        return super()._get_carrier_name()

    def _send_confirmation_email(self):
        """Override of stock_delivery to mark the label request that follows as the automatic one."""
        return super(StockPicking, self.with_context(envia_auto_ship=True))._send_confirmation_email()

    def send_to_shipper(self):
        """Override of stock_delivery to let a transfer validate while its NF-e is pending."""
        if self.env.context.get('envia_auto_ship') and self._envia_needs_l10n_br_edi() and self._l10n_br_has_missing_nfe_packages():
            self.message_post(body=self.env._(
                "Validated transfer without NF-e linked. Envia.com label not generated. Create/link "
                "NF-e and click 'Send to Shipper' to generate the label.",
            ))
            return None
        return super().send_to_shipper()

    def _envia_needs_l10n_br_edi(self):
        """All of the NFe data requires the module installed so guard against it empty"""
        self.ensure_one()
        return (
            self.carrier_id.delivery_type == 'envia'
            and not self.is_return_picking
            and self._envia_get_origin_partner().country_id.code == 'BR'
            and self.env['ir.module.module']._get('l10n_br_edi_stock').state == 'installed'
        )

    def _envia_get_origin_partner(self):
        """Helper to find the ship_from partner"""
        self.ensure_one()
        return self.picking_type_id.warehouse_id.partner_id or self.company_id.partner_id
