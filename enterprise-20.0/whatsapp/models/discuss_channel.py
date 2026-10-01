# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from datetime import timedelta
from markupsafe import Markup

from odoo import api, Command, fields, models, tools, _
from odoo.addons.mail.tools.discuss import Store
from odoo.addons.whatsapp.tools import phone_validation as wa_phone_validation
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)


def is_whatsapp_channel(channel):
    """Predicate to filter channels for which the channel type is 'whatsapp'.

    :returns: Whether the channel is a whatsapp channel.
    :rtype: bool
    """
    return channel.channel_type == "whatsapp"


class DiscussChannel(models.Model):
    """ Support WhatsApp Channels, used for discussion with a specific
    whasapp number """
    _inherit = 'discuss.channel'

    channel_type = fields.Selection(selection_add=[("whatsapp", "WhatsApp")], ondelete={"whatsapp": "cascade"})
    whatsapp_number = fields.Char(string="Phone Number")
    whatsapp_channel_valid_until = fields.Datetime(string="WhatsApp Channel Valid Until Datetime", compute="_compute_whatsapp_channel_valid_until")
    last_wa_mail_message_id = fields.Many2one(comodel_name="mail.message", string="Last WA Partner Mail Message", index='btree_not_null')
    whatsapp_partner_id = fields.Many2one(comodel_name='res.partner', string="WhatsApp Partner", index='btree_not_null')
    wa_account_id = fields.Many2one(comodel_name='whatsapp.account', string="WhatsApp Business Account")
    whatsapp_channel_active = fields.Boolean('Is Whatsapp Channel Active', compute="_compute_whatsapp_channel_active")
    whatsapp_channel_blocked = fields.Boolean(string='Is WhatsApp Channel Blocked', compute="_compute_whatsapp_channel_blocked")

    _group_public_id_check = models.Constraint(
        "CHECK (channel_type = 'channel' OR channel_type = 'whatsapp' OR group_public_id IS NULL)",
        "Group authorization and group auto-subscription are only supported on channels and whatsapp.",
    )

    @api.depends('whatsapp_partner_id', 'whatsapp_number')
    def _compute_display_name(self):
        whatsapp_channels = self.filtered('whatsapp_partner_id')
        for channel in whatsapp_channels:
            partner = channel.whatsapp_partner_id
            number = channel.whatsapp_number or partner.phone
            partner_name = partner.name if partner.name != partner.phone else False
            channel.display_name = f'{partner_name} ({number})' if partner_name and number else (partner_name or number)
        super(DiscussChannel, self - whatsapp_channels)._compute_display_name()

    @api.constrains(lambda self: self.env['discuss.channel']._check_whatsapp_number_contains_fields())
    def _check_whatsapp_number(self):
        # constraint to check the whatsapp number for channel with type 'whatsapp'
        missing_number = self.filtered(lambda channel: channel.channel_type == 'whatsapp' and not channel.whatsapp_number)
        if missing_number:
            raise ValidationError(
                _("A phone number is required for WhatsApp channels %(channel_names)s",
                  channel_names=', '.join(missing_number.mapped('display_name'))
                ))

    @api.model
    def _check_whatsapp_number_contains_fields(self):
        """To be overriden in identifiers module, to avoid overwriting constrains fields."""
        return ['channel_type', 'whatsapp_number']

    # INHERITED CONSTRAINTS

    @api.constrains('group_public_id', 'group_ids')
    def _constraint_group_id_channel(self):
        valid_channels = self.filtered(lambda channel: channel.channel_type == 'whatsapp')
        super(DiscussChannel, self - valid_channels)._constraint_group_id_channel()

    # NEW COMPUTES

    @api.depends('last_wa_mail_message_id')
    def _compute_whatsapp_channel_valid_until(self):
        for channel in self:
            channel.whatsapp_channel_valid_until = channel.last_wa_mail_message_id.create_date + timedelta(hours=24) \
                if channel.channel_type == "whatsapp" and channel.last_wa_mail_message_id else False

    @api.depends('whatsapp_channel_valid_until')
    def _compute_whatsapp_channel_active(self):
        for channel in self:
            channel.whatsapp_channel_active = channel.whatsapp_channel_valid_until and \
                channel.whatsapp_channel_valid_until > fields.Datetime.now()

    def _compute_whatsapp_channel_blocked(self):
        wa_channels = self.filtered(lambda channel: channel.channel_type == 'whatsapp')
        (self - wa_channels).whatsapp_channel_blocked = False
        if not wa_channels:
            return

        formatted_numbers = {
            c.id: wa_phone_validation.wa_phone_format_for_blacklist(c.whatsapp_number)
            for c in wa_channels
        }
        blocklist_records = self.env['whatsapp.blocklist'].sudo().search([
            ('wa_account_id', 'in', wa_channels.mapped('wa_account_id').ids),
            ('number', 'in', list(formatted_numbers.values())),
        ])
        blocked_set = {(rec.wa_account_id.id, rec.number) for rec in blocklist_records}
        for channel in wa_channels:
            channel.whatsapp_channel_blocked = (channel.wa_account_id.id, formatted_numbers[channel.id]) in blocked_set

    # INHERITED COMPUTES

    def _compute_group_public_id(self):
        wa_channels = self.filtered(lambda channel: channel.channel_type == "whatsapp")
        wa_channels.filtered(lambda channel: not channel.group_public_id).group_public_id = self.env.ref('base.group_user')
        super(DiscussChannel, self - wa_channels)._compute_group_public_id()

    # ------------------------------------------------------------
    # MAILING
    # ------------------------------------------------------------

    def _get_notify_valid_parameters(self):
        if self.channel_type == 'whatsapp':
            return super()._get_notify_valid_parameters() | {'whatsapp_inbound_msg_uid', 'wa_interactive_id'}
        return super()._get_notify_valid_parameters()

    def _notify_thread(self, message, **kwargs):
        parent_msg_id = kwargs.pop('parent_msg_id') if 'parent_msg_id' in kwargs else False
        # WhatsApp msg must exist before notify to ensure it's included in notifications.
        if (wa_msg_uid := kwargs.get('whatsapp_inbound_msg_uid')) and self.channel_type == 'whatsapp':
            self.env['whatsapp.message'].create(
                self._get_inbound_whatsapp_message_values_from_mail_message(message, wa_msg_uid, parent_msg_id)
            )
        return super()._notify_thread(message, **kwargs)

    def _get_inbound_whatsapp_message_values_from_mail_message(self, mail_message, whatsapp_message_uid, parent_msg_id=False):
        self.ensure_one()
        message_values = {
            'mail_message_id': mail_message.id,
            'message_type': 'inbound',
            'msg_uid': whatsapp_message_uid,
            'parent_id': parent_msg_id,
            'state': 'received',
            'wa_account_id': self.wa_account_id.id,
        }
        if self.whatsapp_number:
            message_values['mobile_number'] = f'+{self.whatsapp_number}'
        return message_values

    def message_post(self, *args, body='', attachment_ids=None, message_type='notification', parent_id=False, **kwargs):
        valid_parent_id = False
        if parent_id and self.whatsapp_number:
            parent_wa_msg = self.env['mail.message'].browse(parent_id).wa_message_ids
            if (
                parent_wa_msg and len(parent_wa_msg) == 1 and
                parent_wa_msg.message_type == "outbound" and  # replying to an outgoing wa
                parent_wa_msg.mobile_number_formatted == self.whatsapp_number  # same recipient
            ):
                valid_parent_id = parent_id

        if message_type != 'whatsapp_message' or self.channel_type != 'whatsapp':
            message = super().message_post(
                *args, body=body, attachment_ids=attachment_ids,
                message_type=message_type, parent_id=parent_id, **kwargs
            )
            if valid_parent_id:
                message.parent_id = valid_parent_id
            return message

        messages = None
        if not kwargs.get('whatsapp_inbound_msg_uid') and attachment_ids and body and not tools.is_html_empty(body):
            audio_types = self.env['whatsapp.message']._SUPPORTED_ATTACHMENT_TYPE['audio']
            attachment_records = self.env['ir.attachment'].browse(attachment_ids)
            audio_attachments = attachment_records.filtered(lambda x: x.mimetype in audio_types)

            if audio_attachments:
                body_message = super().message_post(
                    *args, message_type=message_type, body=body,
                    attachment_ids=(attachment_records - audio_attachments).ids,
                    parent_id=parent_id, **kwargs,
                )
                audio_message = super().message_post(
                    *args, message_type=message_type, attachment_ids=audio_attachments.ids,
                    parent_id=parent_id, **kwargs,
                )
                messages = body_message + audio_message
        if not messages:
            messages = super().message_post(
                *args, body=body, message_type=message_type, attachment_ids=attachment_ids,
                parent_id=parent_id, **kwargs,
            )

        whatsapp_message_vals = []
        wa_interactive_id = kwargs.get('wa_interactive_id')
        for new_msg in messages:
            if not new_msg.wa_message_ids:
                vals = self._get_outbound_whatsapp_message_values_from_mail_message(new_msg)
                if wa_interactive_id:
                    vals['wa_interactive_id'] = wa_interactive_id
                whatsapp_message_vals.append(vals)
        if messages.author_id == self.whatsapp_partner_id:
            self.last_wa_mail_message_id = new_msg
            Store(bus_channel=self).add(self, ["whatsapp_channel_valid_until"])
        if whatsapp_message_vals:
            self.env['whatsapp.message'].create(whatsapp_message_vals)._send_message()

        if valid_parent_id:
            messages.parent_id = valid_parent_id

        # only return the non-audio message if there are two, as we don't expect to post two messages
        return messages[0]

    def _get_outbound_whatsapp_message_values_from_mail_message(self, mail_message):
        self.ensure_one()
        vals = {
            'body': mail_message.body,
            'mail_message_id': mail_message.id,
            'message_type': 'outbound',
            'wa_account_id': self.wa_account_id.id,
        }
        if number := (self.whatsapp_number and f'+{self.whatsapp_number}') or self.whatsapp_partner_id.phone_sanitized:
            vals['mobile_number'] = number
        return vals

    # ------------------------------------------------------------
    # CONTROLLERS
    # ------------------------------------------------------------

    def _get_whatsapp_channel_domain(self, identifiers):
        """ Search domain for the channel matching the given identifiers (extended per identifier type). """
        if number := identifiers.get('number'):
            return fields.Domain('whatsapp_number', '=', self._get_whatsapp_channel_format_number(number))
        return fields.Domain.FALSE

    def _get_whatsapp_channel_create_values(self, identifiers, wa_account_id=None, sender_name=False):
        default_name = (
            sender_name or
            (identifiers.get('number') and self.env['res.partner']._format_wa_phone(identifiers['number'])) or
            identifiers.get('wa_id') or
            identifiers.get('bsuid')
        )
        wa_partner = self.env['res.partner']._find_or_create_from_whatsapp_identifiers(identifiers, default_name, wa_account_id)
        number = identifiers.get('number')
        wa_number = self._get_whatsapp_channel_format_number(number) if number else False
        recipient_name = wa_partner.name if wa_partner.name != wa_partner.phone else False
        if wa_number:
            name = f'{recipient_name} ({wa_number})' if recipient_name else wa_number
        else:
            name = recipient_name or default_name
        create_vals = {
            'name': name,
            'channel_type': 'whatsapp',
            'wa_account_id': wa_account_id.id,
            'whatsapp_partner_id': wa_partner.id,
        }
        if wa_number:
            create_vals['whatsapp_number'] = wa_number
        return create_vals

    def _get_whatsapp_channel_format_number(self, whatsapp_number):
        # be somewhat defensive with number, as it is used in various flows afterwards
        # notably in 'message_post' for the number, and called by '_process_messages'
        base_number = whatsapp_number if whatsapp_number.startswith('+') else f'+{whatsapp_number}'
        wa_number = base_number.lstrip('+')
        wa_formatted = wa_phone_validation.wa_phone_format(
            self.env.company,
            number=base_number,
            force_format="WHATSAPP",
            raise_exception=False,
        ) or wa_number
        return wa_formatted

    def _get_whatsapp_channel(self, whatsapp_number, wa_account_id, sender_name=False, create_if_not_found=False, related_message=False):
        """ Find or create a whatsapp channel from a phone number.

        Backward-compatible wrapper; prefer `_get_whatsapp_channel_from_identifiers`.

        :param str whatsapp_number: whatsapp phone number of the customer. It should
          be formatted according to whatsapp standards, aka {country_code}{national_number}.

        :returns: whatsapp discussion discuss.channel
        """
        return self._get_whatsapp_channel_from_identifiers(
            wa_account_id, {'number': whatsapp_number}, sender_name=sender_name,
            create_if_not_found=create_if_not_found, related_message=related_message,
        )

    def _get_whatsapp_channel_from_identifiers(self, wa_account_id, identifiers, sender_name=False, create_if_not_found=False, related_message=False):
        channel_domain = self._get_whatsapp_channel_domain(identifiers)
        if not channel_domain:
            return self.env['discuss.channel']
        related_record = False
        responsible_partners = self.env['res.partner']
        channel_domain = channel_domain + [
            ('wa_account_id', '=', wa_account_id.id)
        ]
        if related_message:
            related_record = self.env[related_message.model].browse(related_message.res_id)
            responsible_partners = related_record._whatsapp_get_responsible(
                related_message=related_message,
                related_record=related_record,
                whatsapp_account=wa_account_id,
            ).partner_id

        channel = self.sudo().search(channel_domain, order='create_date desc', limit=1)
        if responsible_partners:
            channel = channel.filtered(lambda c: all(r in c.channel_member_ids.partner_id for r in responsible_partners))

        partners_to_notify = responsible_partners
        if not channel and create_if_not_found:
            create_vals = self._get_whatsapp_channel_create_values(identifiers, wa_account_id=wa_account_id, sender_name=sender_name)
            channel = self.sudo().with_context(tools.clean_context(self.env.context)).create(create_vals)
            partners_to_notify |= channel.whatsapp_partner_id
            if related_message:
                # Add message in channel about the related document
                info = _("Related %(model_name)s: ", model_name=self.env['ir.model']._get(related_message.model).display_name)
                url = Markup('{base_url}/odoo/{model}/{res_id}').format(
                    base_url=self.get_base_url(), model=related_message.model, res_id=related_message.res_id)
                related_record_name = related_message.record_name
                channel.message_post(
                    body=Markup('<p>{info}<a target="_blank" href="{url}">{related_record_name}</a></p>').format(
                        info=info, url=url, related_record_name=related_record_name),
                    message_type='comment',
                    author_id=self.env.ref('base.partner_root').id,
                    subtype_xmlid='mail.mt_note',
                )
                if hasattr(related_record, 'message_post'):
                    # Add notification in document about the new message and related channel
                    info = _("A new WhatsApp channel is created for this document")
                    url = Markup('{base_url}/odoo/discuss.channel/{channel_id}').format(
                        base_url=self.get_base_url(), channel_id=channel.id)
                    related_record.message_post(
                        author_id=self.env.ref('base.partner_root').id,
                        body=Markup('<p>{info} <a target="_blank" class="o_whatsapp_channel_redirect"'
                                    'data-oe-id="{channel_id}" href="{url}">{channel_name}</a></p>').format(
                                        info=info, url=url, channel_id=channel.id, channel_name=channel.display_name),
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
            if partners_to_notify == channel.whatsapp_partner_id and wa_account_id.notify_user_ids.partner_id:
                partners_to_notify |= wa_account_id.notify_user_ids.partner_id
            channel.channel_member_ids = [Command.clear()] + [Command.create({'partner_id': partner.id}) for partner in partners_to_notify]
            channel._broadcast(partners_to_notify.user_ids)
        return channel

    # ------------------------------------------------------------
    # OVERRIDE
    # ------------------------------------------------------------

    def _phone_get_number_fields(self):
        return ['whatsapp_number']

    def _store_channel_fields(self, res: Store.FieldList):
        super()._store_channel_fields(res)
        res.one("group_public_id", ["full_name"], predicate=is_whatsapp_channel)
        res.attr("whatsapp_channel_blocked", predicate=is_whatsapp_channel)
        res.attr("whatsapp_channel_valid_until", predicate=is_whatsapp_channel)
        res.one("whatsapp_partner_id", [], predicate=is_whatsapp_channel)
        # sudo: discuss.channel - reading wa_account_id is allowed for multi-company users
        res.one("wa_account_id", ["name"], predicate=is_whatsapp_channel, sudo=True)

    def _types_allowing_seen_infos(self):
        return super()._types_allowing_seen_infos() + ["whatsapp"]

    def _types_allowing_unfollow(self):
        return super()._types_allowing_unfollow() + ["whatsapp"]
