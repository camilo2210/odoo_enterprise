# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _name = 'pos.order'
    _inherit = 'pos.order'

    def _send_order(self):
        self.ensure_one()
        if not self._should_send_to_preparation():
            return super()._send_order()

        if not self.config_id.preparation_printer_ids.proxy_obox_id or self.source != 'mobile':
            # Only create an obox job if the printer is linked to an obox and the order is from a mobile
            # source. Otherwise, we just send the order to the kitchen printer directly.
            return super()._send_order()

        receipts = self._order_change_receipt_generate_receipts()
        for printer, data in receipts.items():
            if not printer.proxy_obox_id:
                continue

            for receipt in data:
                self._create_obox_print_job(printer, receipt)

        return super()._send_order()

    def _create_obox_print_job(self, printer, xml):
        self.ensure_one()
        self.config_id.sudo().env['obox.queue'].create({
            'obox_id': printer.proxy_obox_id.id,
            'pos_order_id': self.id,
            'payload': {
                'url': f"http://{printer.printer_ip}/cgi-bin/epos/service.cgi?devid=local_printer&timeout=10000",
                'method': 'POST',
                'payload': xml
            },
        })

    def _send_self_order_receipt(self):
        for order in self:
            if (
                order.nb_print == 0
                and order.source == "mobile"
                and order.state == "paid"
                and order.config_id.iface_print_auto
            ):
                printers = order.config_id.receipt_printer_ids.filtered("proxy_obox_id")
                if not printers:
                    continue

                try:
                    xml = order.sudo()._order_receipt_generate_raster()
                except Exception as e:  # noqa: BLE001
                    _logger.warning("Failed to generate receipt for order %s: %s", order.name, e)
                    continue

                for printer in printers:
                    order._create_obox_print_job(printer, xml)

                order.nb_print += 1
        return super()._send_self_order_receipt()
