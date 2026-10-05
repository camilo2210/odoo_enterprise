# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10n_Br_Edi_PosCancelNfce(models.TransientModel):
    _name = 'l10n_br_edi_pos.cancel.nfce'
    _description = 'Cancellation of NFC-e for an order'

    order_id = fields.Many2one('pos.order', string="Order To Cancel", required=True, help="The order to be cancelled.")
    reason = fields.Char("Reason", required=True, help="The justification for cancellation of this order.")

    @api.constrains('order_id', 'reason')
    def _constrains_reason(self):
        for wizard in self:
            if not 15 <= len(wizard.reason or '') <= 255:
                raise ValidationError(self.env._("The reason must contain at least 15 characters and cannot exceed a maximum of 255 characters."))

    def _create_xml_attachment(self, response):
        return self.env['ir.attachment'].create(
            {
                'name': f'{self.order_id.name}_edi_cancel.xml',
                'raw': response['xml']['base64'],
                'res_model': 'pos.order',
                'res_id': self.order_id.id,
            }
        )

    def action_cancel(self):
        order = self.order_id
        iap_args = {
            'key': order.l10n_br_access_key,
            'message': self.reason,
        }
        response = order._l10n_br_edi_pos_cancel_invoice(iap_args)
        if error := order._l10n_br_get_error_from_response(response):
            raise ValidationError(error)
        if not response.get('xml', {}).get('base64'):
            raise ValidationError(response['status']['desc'])

        order.write({
            'l10n_br_last_avatax_status': 'cancelled',
        })

        order.message_post(
            body=self.env._("E-invoice cancelled successfully."),
            attachment_ids=self._create_xml_attachment(response).ids,
        )
