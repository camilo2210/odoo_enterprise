from odoo import models
from odoo.fields import Domain


class WhatsAppAccount(models.Model):
    _inherit = 'whatsapp.account'

    def _find_active_channel_from_whatsapp_message_values(self, whatsapp_message_values, whatsapp_contacts_values, create_if_not_found=False):
        # FIXME? should probably try to match messages to contacts instead of assuming we'll only ever get one
        sender_contact = (whatsapp_contacts_values or [{}])[0]
        from_number = whatsapp_message_values.get('from')
        identifiers = {
            'bsuid': whatsapp_message_values.get('from_user_id'),
            'number': from_number and self._format_incoming_from_number(from_number),
            'wa_id': sender_contact.get('wa_id'),
        }
        return self._find_active_channel_from_identifiers(
            identifiers,
            sender_name=sender_contact.get('profile', {}).get('name'),
            create_if_not_found=create_if_not_found,
        )

    def _get_message_identifiers_domain(self, identifiers):
        # extend the lookup so a message can also be matched by its recipient's bsuid/wa_id
        domain = Domain.FALSE
        if number_domain := super()._get_message_identifiers_domain(identifiers):
            domain |= number_domain
        if bsuid := identifiers.get('bsuid'):
            domain |= Domain('recipient_wa_bsuid', '=', bsuid)
        if wa_id := identifiers.get('wa_id'):
            domain |= Domain('recipient_wa_id', '=', wa_id)
        return domain
