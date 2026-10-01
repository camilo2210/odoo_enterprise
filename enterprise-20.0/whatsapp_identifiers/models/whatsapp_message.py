from odoo import fields, models

from odoo.addons.whatsapp.tools.whatsapp_exception import WhatsAppError


class WhatsappMessage(models.Model):
    _inherit = 'whatsapp.message'

    recipient_wa_id = fields.Char('Recipient WhatsApp ID', index='btree_not_null')
    recipient_wa_bsuid = fields.Char('Recipient Business-Scoped User ID', index='btree_not_null')

    def _process_statuses(self, value):
        """Associate wa_id to bsuid as soon as the status webhook carries the user_id contact.

        This is the earliest point where the bsuid is available when sending to a phone number.
        """
        contact_bsuid_by_wa_id = {
            contact['wa_id']: contact['user_id']
            for contact in value.get('contacts', [])
            if contact.get('wa_id') and contact.get('user_id')
        }
        if contact_bsuid_by_wa_id:
            message_uids = [status['id'] for status in value.get('statuses', [])]
            messages_by_wa_id = self.env['whatsapp.message'].sudo().search([
                ('msg_uid', 'in', message_uids),
                ('recipient_wa_id', 'in', list(contact_bsuid_by_wa_id)),
                ('recipient_wa_bsuid', '=', False),
            ]).grouped('recipient_wa_id')
            for wa_id, messages in messages_by_wa_id.items():
                messages.recipient_wa_bsuid = contact_bsuid_by_wa_id[wa_id]
        return super()._process_statuses(value)

    def _assert_recipient_identifier(self):
        try:
            return super()._assert_recipient_identifier()
        except WhatsAppError:
            if self.recipient_wa_bsuid:
                return self.recipient_wa_bsuid
            raise

    def _get_sent_whatsapp_message_values(self, send_response):
        # write wa_id along with msg_uid to save querries
        vals = super()._get_sent_whatsapp_message_values(send_response)
        if wa_id := send_response.get('wa_id'):
            vals['recipient_wa_id'] = wa_id
        return vals

    def _send_with_identifier(self, wa_api, **send_kwargs):
        # priority to sending with the number, as it is the field users will be managing
        if self.mobile_number_formatted:
            return super()._send_with_identifier(wa_api, **send_kwargs)
        if bsuid := self.recipient_wa_bsuid:
            return wa_api._send_whatsapp_to_identifier(bsuid=bsuid, number=None, **send_kwargs)
        return {}
