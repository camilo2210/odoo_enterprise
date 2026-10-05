# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import mimetypes
import psycopg2
import re
import secrets
import string
from markupsafe import Markup

from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.addons.whatsapp.tools.whatsapp_api import WhatsAppApi
from odoo.addons.whatsapp.tools.whatsapp_exception import WhatsAppError
from odoo.modules.registry import Registry
from odoo.tools import plaintext2html
from odoo.addons.whatsapp.tools import phone_validation as wa_phone_validation

_logger = logging.getLogger(__name__)


class WhatsappAccount(models.Model):
    _name = 'whatsapp.account'
    _inherit = ['mail.thread']
    _description = 'WhatsApp Business Account'

    name = fields.Char(string="Name", tracking=1)
    active = fields.Boolean(default=True, tracking=6)

    app_uid = fields.Char(string="App ID", required=True, tracking=2)
    app_secret = fields.Char(string="App Secret", groups='whatsapp.group_whatsapp_admin')
    account_uid = fields.Char(string="Account ID", required=True, tracking=3)
    phone_uid = fields.Char(string="Phone Number ID", required=True, tracking=4)
    phone_number = fields.Char(string="Phone Number", copy=False, readonly=True,
        help="The phone number used in the Whatsapp Business Account.")
    token = fields.Char(string="Access Token", groups='whatsapp.group_whatsapp_admin')
    webhook_verify_token = fields.Char(string="Webhook Verify Token", compute='_compute_verify_token',
                                       groups='whatsapp.group_whatsapp_admin', store=True)
    callback_url = fields.Char(string="Callback URL", compute='_compute_callback_url', readonly=True, copy=False)
    proxy_webhook_url = fields.Char(string="Proxy Webhook URL", readonly=True, copy=False, groups='whatsapp.group_whatsapp_admin')
    shared_webhook_secret = fields.Char(string="Shared Webhook Secret", readonly=True, copy=False,
                                        groups='whatsapp.group_whatsapp_admin',
                                        help="The secret used to validate incoming webhook calls from the proxy.")
    debug_logging = fields.Boolean(string="Debug logging", help="Log requests in order to ease debugging")

    allowed_company_ids = fields.Many2many(
        comodel_name='res.company', string="Allowed Company",
        default=lambda self: self.env.company)
    notify_user_ids = fields.Many2many(
        comodel_name='res.users', default=lambda self: self.env.user,
        domain=[('share', '=', False)], required=True, tracking=5,
        help="Users to notify when a message is received and there is no template send in last 15 days")

    is_oauth_onboarded = fields.Boolean(string="OAuth Onboarded", readonly=True, copy=False)
    is_phone_registered = fields.Boolean(string="Phone Registered", readonly=True, copy=False)
    is_webhook_subscribed = fields.Boolean(string="Webhook Subscribed", readonly=True, copy=False)
    state = fields.Selection([
        ('connected', 'Connected'),
        ('disconnected', 'Not Connected'),
    ], compute='_compute_state', store=True, tracking=7)

    blocklist_count = fields.Integer(string="Blocklist Count", compute='_compute_blocklist_count')
    templates_count = fields.Integer(string="Message Count", compute='_compute_templates_count')

    _check_app_credentials = models.Constraint(
        """CHECK(
            COALESCE(is_oauth_onboarded, false)
            OR (COALESCE(app_secret, '') != '' AND COALESCE(token, '') != '')
        )""",
        "App Secret and Access Token are required unless the account was onboarded through OAuth.",
    )
    _phone_uid_unique = models.Constraint(
        'unique(phone_uid)',
        "The same phone number ID already exists",
    )

    @api.constrains('notify_user_ids')
    def _check_notify_user_ids(self):
        for phone in self:
            if len(phone.notify_user_ids) < 1:
                raise ValidationError(_("Users to notify is required"))

    def _compute_callback_url(self):
        for account in self:
            account.callback_url = self.get_base_url() + '/whatsapp/webhook'

    @api.depends('is_oauth_onboarded', 'is_phone_registered', 'is_webhook_subscribed')
    def _compute_state(self):
        for account in self:
            if not account.is_oauth_onboarded:
                account.state = False
            elif account.is_phone_registered and account.is_webhook_subscribed:
                account.state = 'connected'
            else:
                account.state = 'disconnected'

    @api.depends('account_uid')
    def _compute_verify_token(self):
        """ webhook_verify_token only set when record is created. Not update after that."""
        for rec in self:
            if rec.id and not rec.webhook_verify_token:
                rec.webhook_verify_token = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))

    def _compute_blocklist_count(self):
        counts = {
            account.id: count
            for account, count in self.env['whatsapp.blocklist']._read_group(
                [('wa_account_id', 'in', self.ids)],
                ['wa_account_id'],
                ['__count'],
            )
        }
        for account in self:
            account.blocklist_count = counts.get(account.id, 0)

    def _compute_templates_count(self):
        for tmpl in self:
            tmpl.templates_count = self.env['whatsapp.template'].search_count([('wa_account_id', 'in', tmpl.ids)])

    def button_disconnect(self):
        """Disconnect the WhatsApp account.

        A failed unsubscribe on Meta leaves the account untouched rather than
        half disconnected. A failed proxy cleanup is only logged, that
        registration is dead anyway once Meta stops sending.
        """
        self.ensure_one()
        self.check_access('write')
        if not self.is_oauth_onboarded:
            raise UserError(_("Only accounts connected through the onboarding can be disconnected."))
        wa_api = WhatsAppApi(self)
        try:
            wa_api._unsubscribe_webhook()
        except WhatsAppError as error:
            raise ValidationError(str(error)) from error
        try:
            wa_api._unregister_proxy_webhook()
        except WhatsAppError as error:
            _logger.warning(
                "Unable to unregister the webhook of the WhatsApp account %s [%s] on the proxy: %s",
                self.name, self.id, error,
            )

        self.write({
            'active': False,
            'is_webhook_subscribed': False,
            'proxy_webhook_url': False,
            'shared_webhook_secret': False,
            'token': False,
        })

    def button_subscribe_webhook(self):
        """Manually subscribe to webhook, in case it failed during onboarding."""
        self.ensure_one()
        try:
            self._configure_webhook()
        except WhatsAppError as error:
            raise ValidationError(str(error)) from error
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Successfully subscribed to webhook!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def button_sync_whatsapp_account_templates(self):
        """
            This method will sync all the templates of the WhatsApp Business Account.
            It will create new templates and update existing templates.
        """
        self.ensure_one()
        try:
            response = WhatsAppApi(self)._get_all_template(fetch_all=True)
            wa_phone_number = WhatsAppApi(self)._get_phone_number(self.phone_uid)
            if wa_phone_number:
                self.phone_number = wa_phone_number
        except WhatsAppError as err:
            raise ValidationError(str(err)) from err

        WhatsappTemplate = self.env['whatsapp.template']
        existing_tmpls = WhatsappTemplate.with_context(active_test=False).search([('wa_account_id', '=', self.id)])
        existing_tmpl_by_id = {t.wa_template_uid: t for t in existing_tmpls}
        template_update_count = 0
        template_create_count = 0
        if response.get('data'):
            create_vals = []
            for template in response['data']:
                existing_tmpl = existing_tmpl_by_id.get(template['id'])
                if existing_tmpl:
                    template_update_count += 1
                    existing_tmpl._update_template_from_response(template)
                else:
                    template_create_count += 1
                    create_vals.append(WhatsappTemplate._create_template_from_response(template, self))
            WhatsappTemplate.create(create_vals)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Templates synchronized!"),
                'type': 'success',
                'message': _("%(create_count)s were created, %(update_count)s were updated",
                    create_count=template_create_count, update_count=template_update_count),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def button_test_connection(self):
        """Test the connection of the WhatsApp Business Account.

        The phone number can be deregistered and the webhook subscription can be
        taken over without Meta notifying us, so the flags of an onboarded account
        are re-read from Meta instead of keeping what was stored during the
        onboarding.
        """
        self.ensure_one()
        if self.is_oauth_onboarded:
            try:
                self._refresh_account_state()
            except WhatsAppError as error:
                raise ValidationError(str(error)) from error

        wa_api = WhatsAppApi(self)
        try:
            wa_api._test_connection()
            wa_phone_number = wa_api._get_phone_number(self.phone_uid)
            if wa_phone_number:
                self.phone_number = wa_phone_number
        except WhatsAppError as e:
            raise UserError(str(e))

        failure_reason = self._get_connection_failure_reason() if self.is_oauth_onboarded else ''
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                # The credentials check reports success even when the phone is
                # unregistered or the webhook was taken over.
                'type': 'warning' if failure_reason else 'success',
                'message': failure_reason or _("Credentials look good!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_debug(self):
        """Enable debug logging."""
        self.ensure_one()
        previous_debug_state = self.debug_logging
        self.debug_logging = True
        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'type': 'warning',
                    'message': _('Enabling WhatsApp debug stops medias (pictures, videos, pdf, ...) from being received.'),
                },
            } if not previous_debug_state else None

    def action_stop_debug(self):
        """Disable debug logging."""
        self.ensure_one()
        self.debug_logging = False

    def action_open_blocklist(self):
        self.ensure_one()
        return {
            'name': _("Blocklist of %(account_name)s", account_name=self.name),
            'view_mode': 'list,form',
            'res_model': 'whatsapp.blocklist',
            'domain': [('wa_account_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_wa_account_id': self.id},
        }

    def action_open_registration_wizard(self):
        return {
            'name': _("Register Phone Number"),
            'view_mode': 'form',
            'res_model': 'whatsapp.register.phone',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {'default_wa_account_id': self.id},
        }

    def action_open_templates(self):
        self.ensure_one()
        return {
            'name': _("Templates Of %(account_name)s", account_name=self.name),
            'view_mode': 'list,form',
            'res_model': 'whatsapp.template',
            'domain': [('wa_account_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_wa_account_id': self.id},
        }

    @api.model
    def _cron_refresh_onboarded_account_state(self):
        """Refresh the onboarded accounts against Meta.

        Nothing warns us when a phone number is deregistered or when another
        provider takes the webhook over, so without this the account keeps
        showing as connected until someone tests the connection.
        """
        for account in self.search([('is_oauth_onboarded', '=', True)]):
            was_connected = account.state == 'connected'
            try:
                account._refresh_account_state()
            except (RedirectWarning, WhatsAppError) as error:
                _logger.warning(
                    "Unable to refresh the state of the WhatsApp account %s [%s]: %s",
                    account.name, account.id, error,
                )
                continue
            if was_connected and account.state != 'connected':
                account._notify_connection_lost()

    def _add_ir_log(self, name, message, func=''):
        self.ensure_one()
        self.env.flush_all()
        db_name = self.env.cr.dbname
        # Use a new cursor to avoid rollback that could be caused by an upper method
        try:
            db_registry = Registry(db_name)
            with db_registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env['ir.logging'].create({
                    'dbname': db_name,
                    'func': func,
                    'level': 'DEBUG',
                    'line': '',
                    'message': message,
                    'name': name,
                    'path': f'whatsapp.account,id={self.id},name={self.name}',
                    'type': 'server',
                })
        except psycopg2.Error:
            pass

    def _configure_webhook(self):
        """Register and subscribe the webhook for this WhatsApp account."""
        self.ensure_one()
        wa_api = WhatsAppApi(self)

        if not all((
            self.proxy_webhook_url,
            self.shared_webhook_secret,
        )):
            proxy_webhook_data = wa_api._register_proxy_webhook()
            self.write({
                'proxy_webhook_url': proxy_webhook_data['webhook_url'],
                'shared_webhook_secret': proxy_webhook_data['shared_webhook_secret'],
            })

        wa_api._subscribe_webhook()
        self.is_webhook_subscribed = True

    def _find_active_channel_from_whatsapp_message_values(self, whatsapp_message_values, whatsapp_contacts_values, create_if_not_found=False):
        self.ensure_one()
        # FIXME? should probably try to match messages to contacts instead of assuming we'll only ever get one
        sender_name = (whatsapp_contacts_values or [{}])[0].get('profile', {}).get('name')
        sender_mobile_formatted = None

        from_number = whatsapp_message_values.get('from')
        if from_number and (sender_mobile_formatted := self._format_incoming_from_number(from_number)):
            return self._find_active_channel(sender_mobile_formatted, sender_name=sender_name, create_if_not_found=create_if_not_found)
        return self.env['discuss.channel']

    def _find_active_channel(self, sender_mobile_formatted, sender_name=False, create_if_not_found=False):
        """This method will find the active channel for the given sender mobile number."""
        self.ensure_one()
        return self._find_active_channel_from_identifiers(
            {'number': sender_mobile_formatted},
            sender_name=sender_name, create_if_not_found=create_if_not_found,
        )

    def _get_message_identifiers_domain(self, identifiers):
        if identifiers.get('number'):
            return fields.Domain('mobile_number_formatted', '=', identifiers['number'])
        return fields.Domain.FALSE

    def _find_active_channel_from_identifiers(self, identifiers, sender_name=False, create_if_not_found=False):
        """Find the active channel from whatsapp 'identifiers'.

        :param identifiers: a dict of shape {'number': str, 'wa_id': str, 'bsuid': str}, or a subdict of it.
        In the base module only 'number' will be passed around.
        :param sender_name: an optional user-readable name for the sender if creating a channel and/or partner.
        If not set will default to a field value, such as the phone number, or bsuid.
        :param create_if_not_found: whether to create a channel, and implicitly whether to create a partner
        to be linked to that channel and represent the sender.
        """
        self.ensure_one()
        domain = self._get_message_identifiers_domain(identifiers) + [
            ('wa_account_id', '=', self.id),
            ('wa_template_id', '!=', False),
            ('state', 'not in', ['outgoing', 'error', 'cancel']),
        ]
        whatsapp_message = self.env['whatsapp.message'].sudo().search(domain, limit=1, order='id desc')
        channel = self.env['discuss.channel'].sudo()._get_whatsapp_channel_from_identifiers(
            wa_account_id=self,
            identifiers=identifiers,
            sender_name=sender_name,
            create_if_not_found=create_if_not_found,
            related_message=whatsapp_message.mail_message_id,
        )
        # sync any newly-learned identifiers onto the partner
        if channel_partner := channel.whatsapp_partner_id:
            channel_partner._update_from_whatsapp_identifiers(identifiers, self)
        return channel

    def _get_connection_failure_reason(self):
        """Return why the account cannot exchange messages, empty when it can."""
        self.ensure_one()
        if not self.is_phone_registered and not self.is_webhook_subscribed:
            return _("The phone number is not registered and the webhook is not pointing to Odoo, so this account can neither send nor receive messages.")
        if not self.is_phone_registered:
            return _("The phone number is not registered, so this account can neither send nor receive messages.")
        if not self.is_webhook_subscribed:
            return _("Sending still works, but the webhook is not pointing to Odoo, so incoming messages will not reach this database.")
        return ''

    def _notify_connection_lost(self):
        """Warn the users in charge of the account that it stopped working.

        The state is only refreshed once a week, so nothing else tells them
        before a customer complains that nobody answered.
        """
        self.ensure_one()
        self.message_post(
            body=self._get_connection_failure_reason(),
            message_type='notification',
            partner_ids=self.notify_user_ids.partner_id.ids,
            subtype_xmlid='mail.mt_note',
        )

    def _process_messages(self, value):
        """
            This method is used for processing messages with the values received via webhook.
            If any whatsapp message template has been sent from this account then it will find the active channel or
            create new channel with last template message sent to that number and post message in that channel.
            And if channel is not found then it will create new channel with notify user set in account and post message.
            Supported Messages
             => Text Message
             => Attachment Message with caption
             => Location Message
             => Contact Message
             => Message Reactions
        """
        if 'messages' not in value and value.get('whatsapp_business_api_data', {}).get('messages'):
            value = value['whatsapp_business_api_data']

        wa_api = WhatsAppApi(self)

        for messages in value.get('messages', []):
            parent_msg_id = False
            parent_id = False
            channel = False
            message_type = messages['type']
            if 'context' in messages and messages['context'].get('id'):
                parent_whatsapp_message = self.env['whatsapp.message'].sudo().search([('msg_uid', '=', messages['context']['id'])])
                if parent_whatsapp_message:
                    parent_msg_id = parent_whatsapp_message.id
                    parent_id = parent_whatsapp_message.mail_message_id
                if parent_id:
                    channel = self.env['discuss.channel'].sudo().search([('message_ids', 'in', parent_id.id)], limit=1)

            if not channel:
                channel = self._find_active_channel_from_whatsapp_message_values(messages, value.get('contacts'), create_if_not_found=True)
            kwargs = {
                'message_type': 'whatsapp_message',
                'author_id': channel.whatsapp_partner_id.id,
                'parent_msg_id': parent_msg_id,
                'subtype_xmlid': 'mail.mt_comment',
                'parent_id': parent_id.id if parent_id else None,
            }
            if message_type == 'text':
                kwargs['body'] = plaintext2html(messages['text']['body'])
            elif message_type == 'button':
                kwargs['body'] = messages['button']['text']
            elif message_type in ('document', 'image', 'audio', 'video', 'sticker'):
                filename = messages[message_type].get('filename')
                is_voice = messages[message_type].get('voice')
                mime_type = messages[message_type].get('mime_type')
                caption = messages[message_type].get('caption')
                datas = wa_api._get_whatsapp_document(messages[message_type]['id'])
                if not filename:
                    extension = mimetypes.guess_extension(mime_type) or ''
                    filename = message_type + extension
                kwargs['attachments'] = [(filename, datas, {'voice': is_voice})]
                if caption:
                    kwargs['body'] = plaintext2html(caption)
            elif message_type == 'location':
                url = Markup("https://maps.google.com/maps?q={latitude},{longitude}").format(
                    latitude=messages['location']['latitude'], longitude=messages['location']['longitude'])
                body = Markup('<a target="_blank" href="{url}"> <i class="oi" data-icon="location_on"/> {location_string} </a>').format(
                    url=url, location_string=_("Location"))
                if messages['location'].get('name'):
                    body += Markup("<br/>{location_name}").format(location_name=messages['location']['name'])
                if messages['location'].get('address'):
                    body += Markup("<br/>{location_address}").format(location_address=messages['location']['address'])
                kwargs['body'] = body
            elif message_type == 'contacts':
                body = ""
                for contact in messages['contacts']:
                    body += Markup("<i class='oi oi-filled' data-icon='contact_page'/> {contact_name} <br/>").format(
                        contact_name=contact.get('name', {}).get('formatted_name', ''))
                    for phone in contact.get('phones'):
                        body += Markup("{phone_type}: {phone_number}<br/>").format(
                            phone_type=phone.get('type'), phone_number=phone.get('phone'))
                kwargs['body'] = body
            elif message_type == 'reaction':
                msg_uid = messages['reaction'].get('message_id')
                whatsapp_message = self.env['whatsapp.message'].sudo().search([('msg_uid', '=', msg_uid)])
                if whatsapp_message:
                    partner_id = channel.whatsapp_partner_id
                    emoji = messages['reaction'].get('emoji')
                    whatsapp_message.mail_message_id._post_whatsapp_reaction(reaction_content=emoji, partner_id=partner_id)
                    continue
            elif message_type == 'interactive':
                interactive_message = messages['interactive']
                interactive_type = interactive_message.get('type')
                if interactive_type == 'button_reply':
                    kwargs['body'] = plaintext2html(interactive_message.get('button_reply', {}).get('title', ''))
                elif interactive_type == 'list_reply':
                    list_reply = interactive_message.get('list_reply', {})
                    title = list_reply.get('title', '')
                    description = list_reply.get('description', '')
                    kwargs['body'] = Markup('<p>{}</p>').format(title)
                    if description:
                        kwargs['body'] += Markup('<p>{}</p>').format(description)
                else:
                    _logger.warning("Unsupported whatsapp interactive message type: %s", messages)
                    continue
            else:
                _logger.warning("Unsupported whatsapp message type: %s", messages)
                continue
            channel.message_post(whatsapp_inbound_msg_uid=messages['id'], **kwargs)

    def _refresh_account_state(self):
        """Store the registration and webhook state currently set on Meta."""
        self.ensure_one()
        self.write(WhatsAppApi(self)._fetch_account_state())

    # UTILS

    @api.model
    def _format_incoming_from_number(self, from_number):
        if not from_number:
            return from_number
        cleaned_number = re.sub(r"[^\d+]", "", from_number)
        cleaned_number = "+" + re.sub(r"\D", "", cleaned_number)
        return wa_phone_validation.wa_phone_format(
            self,
            country=None,
            number=cleaned_number,
            force_format="WHATSAPP",
            raise_exception=False,
        ) or cleaned_number
