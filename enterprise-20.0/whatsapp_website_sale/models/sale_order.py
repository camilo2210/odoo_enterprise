# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cart_recovery_whatsapp_sent = fields.Boolean(string="Cart recovery WhatsApp already sent")

    def _whatsapp_get_portal_url(self):
        self.ensure_one()
        if self.env.context.get('whatsapp_use_cart_recovery_url'):
            self._portal_ensure_token()
            return f"/shop/cart?id={self.id}&access_token={self.access_token}"
        return super()._whatsapp_get_portal_url()

    def action_confirm(self):
        res = super().action_confirm()
        for order in self.filtered(lambda o: o.website_id.wa_sale_template_id):
            whatsapp_composer = self.env['whatsapp.composer'].with_context({'active_id': order.id}).create(
                {
                    'wa_template_id': order.website_id.wa_sale_template_id.id,
                    'res_model': 'sale.order'
                }
            )
            whatsapp_composer.sudo()._send_whatsapp_template(force_send_by_cron=True)
        return res

    def _get_cart_recovery_template_whatsapp(self):
        """ Returns the WhatsApp template to use for abandoned cart recovery via WhatsApp.

        If the website has a specific template set, it will be used.
        Otherwise, it will fallback to the default template.
        If no template is found, it will return an empty recordset.
        """
        self.ensure_one()
        website = self.website_id
        template = website.wa_sale_cart_recovery_template_id
        template = template or self.env.ref(
            'whatsapp_website_sale.whatsapp_template_abandoned_cart',
            raise_if_not_found=False
        )
        return template or self.env["whatsapp.template"]

    def _cart_recovery_whatsapp_send(self):
        sent_orders = self.env['sale.order']
        for template, sale_orders in self.grouped(
            lambda order: order._get_cart_recovery_template_whatsapp()
        ).items():
            if template:
                whatsapp_composer = (
                    self
                    .env['whatsapp.composer']
                    .with_context(whatsapp_use_cart_recovery_url=True)
                    .create({
                        'batch_mode': True,
                        'wa_template_id': template.id,
                        'res_model': 'sale.order',
                        'res_ids': sale_orders.ids,
                    })
                )
                whatsapp_composer.sudo()._send_whatsapp_template(force_send_by_cron=True)
                sent_orders += sale_orders
        sent_orders.write({'cart_recovery_whatsapp_sent': True})
