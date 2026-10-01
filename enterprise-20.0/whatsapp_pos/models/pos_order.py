# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, _


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _get_whatsapp_receipt_template(self):
        if self.config_id.whatsapp_enabled:
            return self.config_id.receipt_template_id
        return False

    def action_sent_receipt_on_whatsapp(self, phone, template=None):
        self.ensure_one()
        receipt_template = template or self._get_whatsapp_receipt_template()
        if not receipt_template or not phone:
            return
        filename = 'Receipt-' + self.name + '.jpg'
        ticket_image = self.order_receipt_generate_image()
        receipt = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'raw': ticket_image,
            'res_model': 'pos.order',
            'res_id': self.ids[0],
            'mimetype': 'image/jpeg',
        })
        whatsapp_composer = self.env['whatsapp.composer'].with_context({'active_id': self.id}).create(
            {
                'attachment_id': receipt.id,
                'phone': phone,
                'wa_template_id': receipt_template.id,
                'res_model': 'pos.order'
            }
        )
        whatsapp_composer._send_whatsapp_template()
        self.mobile = phone
        if not template and self.to_invoice and self.config_id.invoice_template_id:
            whatsapp_composer = self.env['whatsapp.composer'].with_context({'active_id': self.account_move.id}).create(
                {
                    'phone': phone,
                    'wa_template_id': self.config_id.invoice_template_id.id,
                    'res_model': 'account.move'
                }
            )
            # Receipt is already send so force_send_by_cron is True
            # so it's not raise error if there is any miss configuration
            whatsapp_composer._send_whatsapp_template(force_send_by_cron=True)

    def _get_whatsapp_safe_fields(self):
        return {'partner_id.name', 'name', 'company_id.name'}

    def action_send_whatsapp(self):
        return {
            'name': _('Send Whatsapp'),
            'view_mode': 'form',
            'res_model': 'whatsapp.composer',
            'type': 'ir.actions.act_window',
            'context': {'template_types': ['marketing']},
            'target': 'new'
        }
