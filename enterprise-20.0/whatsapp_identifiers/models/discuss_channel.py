from odoo import models
from odoo.fields import Domain


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    def _check_whatsapp_number(self):
        missing_bsuid_wa_channels = self.filtered(
            lambda channel: (
                channel.channel_type == 'whatsapp' and
                not channel.whatsapp_partner_id.with_context(whatsapp_account_id=channel.wa_account_id).wa_bsuid
            )
        )
        super(DiscussChannel, missing_bsuid_wa_channels)._check_whatsapp_number()

    def _check_whatsapp_number_contains_fields(self):
        return ['whatsapp_partner_id', 'wa_account_id']

    def _get_whatsapp_channel_domain(self, identifiers):
        # extend the lookup so a channel can also be matched by its partner's bsuid/wa_id
        domain = Domain.FALSE
        if number_domain := super()._get_whatsapp_channel_domain(identifiers):
            domain |= number_domain
        if bsuid := identifiers.get('bsuid'):
            domain |= Domain('whatsapp_partner_id.wa_bsuid_ids.bsuid', '=', bsuid)
        if wa_id := identifiers.get('wa_id'):
            domain |= Domain('whatsapp_partner_id.wa_id', '=', wa_id)
        return domain

    def _get_inbound_whatsapp_message_values_from_mail_message(self, mail_message, whatsapp_message_uid, parent_msg_id=False):
        message_vals = super()._get_inbound_whatsapp_message_values_from_mail_message(mail_message, whatsapp_message_uid, parent_msg_id=parent_msg_id)
        if bsuid := self.whatsapp_partner_id.with_context(whatsapp_account_id=self.wa_account_id).wa_bsuid:
            message_vals['recipient_wa_bsuid'] = bsuid
        return message_vals

    def _get_outbound_whatsapp_message_values_from_mail_message(self, mail_message):
        vals = super()._get_outbound_whatsapp_message_values_from_mail_message(mail_message)
        if bsuid := self.whatsapp_partner_id.with_context(whatsapp_account_id=self.wa_account_id).wa_bsuid:
            vals['recipient_wa_bsuid'] = bsuid
        return vals
