# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
import logging
from markupsafe import Markup, escape

from datetime import timedelta

from odoo import models, modules, fields, api, _
from odoo.addons.phone_validation.tools import phone_validation
from odoo.addons.whatsapp.tools import phone_validation as wa_phone_validation
from odoo.addons.whatsapp.tools.retryable_codes import WHATSAPP_RETRYABLE_ERROR_CODES
from odoo.addons.whatsapp.tools.bounced_codes import BOUNCED_ERROR_CODES
from odoo.addons.whatsapp.tools.whatsapp_api import WhatsAppApi
from odoo.addons.whatsapp.tools.whatsapp_exception import WhatsAppError
from odoo.exceptions import ValidationError, UserError
from odoo.tools import frozendict, groupby, html2plaintext
from odoo.addons.mail.tools.discuss import Store

_logger = logging.getLogger(__name__)


class WhatsappMessage(models.Model):
    _name = 'whatsapp.message'
    _description = 'WhatsApp Message'
    _order = 'id desc'
    _rec_name = 'mobile_number'

    # Refer to https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media/#supported-media-types
    # for more details about supported media types
    _SUPPORTED_ATTACHMENT_TYPE = {
        'audio': ('audio/aac', 'audio/mp4', 'audio/mpeg', 'audio/amr', 'audio/ogg'),
        'document': (
            'text/plain', 'application/pdf', 'application/vnd.ms-powerpoint', 'application/msword',
            'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ),
        'image': ('image/jpeg', 'image/png'),
        'video': ('video/mp4',),
    }
    # amount of days during which a message is considered active
    # used for GC and for finding an active document channel using a recent whatsapp template message
    _ACTIVE_THRESHOLD_DAYS = 15

    mobile_number = fields.Char(string="Sent To")
    mobile_number_formatted = fields.Char(
        string="Mobile Number Formatted",
        compute="_compute_mobile_number_formatted", readonly=False, store=True)
    is_number_blocked = fields.Boolean(compute='_compute_is_number_blocked')
    message_type = fields.Selection([
        ('outbound', 'Outbound'),
        ('inbound', 'Inbound')], string="Message Type", default='outbound')
    state = fields.Selection(selection=[
        ('outgoing', 'In Queue'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('replied', 'Replied'),  # used internally
        ('received', 'Received'),
        ('error', 'Failed'),
        ('bounced', 'Bounced'),  # failure linked to number usage, different from pure whatsapp error
        ('cancel', 'Cancelled')], string="State", default='outgoing')
    failure_type = fields.Selection([
        ('account', 'Account Error'),
        ('blacklisted', 'Blacklisted Phone Number'),
        ('network', 'Network Error'),
        ('outdated_channel', 'The channel is no longer active'),
        ('phone_invalid', 'Wrong Number Format'),
        ('template', 'Template Quality Rating Too Low'),
        ('unknown', 'Unknown Error'),
        ('whatsapp_recoverable', 'Identified Error'),
        ('whatsapp_unrecoverable', 'Other Technical Error')
    ])
    failure_reason = fields.Char(string="Failure Reason", help="Usually an error message from Whatsapp")
    free_text_json = fields.Json(string="Free Text Template Parameters")
    wa_template_id = fields.Many2one(comodel_name='whatsapp.template')
    wa_interactive_id = fields.Many2one(comodel_name='whatsapp.interactive')
    msg_uid = fields.Char(string="WhatsApp Message ID")
    wa_account_id = fields.Many2one(comodel_name='whatsapp.account', string="WhatsApp Business Account")
    parent_id = fields.Many2one('whatsapp.message', 'Response To', index='btree_not_null', ondelete="set null")

    mail_message_id = fields.Many2one(comodel_name='mail.message', index=True)
    body = fields.Html(related='mail_message_id.body', string="Body")

    _unique_msg_uid = models.Constraint(
        'unique(msg_uid)',
        "Each whatsapp message should correspond to a single message uuid.",
    )

    @api.depends('mobile_number')
    def _compute_mobile_number_formatted(self):
        for message in self:
            recipient_partner = message.mail_message_id.partner_ids[0] if message.mail_message_id.partner_ids else self.env['res.partner']
            country = recipient_partner.country_id if recipient_partner.country_id else self.env.company.country_id
            formatted = wa_phone_validation.wa_phone_format(
                country,  # could take mail.message record as context but seems overkill
                number=message.mobile_number,
                country=country,
                force_format="WHATSAPP",
                raise_exception=False,
            )
            message.mobile_number_formatted = formatted or ''

    def _compute_is_number_blocked(self):
        numbers = [wa_phone_validation.wa_phone_format_for_blacklist(message.mobile_number_formatted) for message in self if message.mobile_number_formatted]
        phone_recs = self.env['phone.blacklist'].sudo().search([
            ('number', 'in', numbers),
            ('active', '=', True),
        ])
        phone_bl_numbers = phone_recs.mapped('number')
        wa_recs = self.env['whatsapp.blocklist'].sudo().search([
            ('wa_account_id', 'in', self.wa_account_id.ids),
            ('number', 'in', numbers),
        ])
        for message in self:
            if not message.mobile_number_formatted:
                message.is_number_blocked = False
                continue
            formatted_number = wa_phone_validation.wa_phone_format_for_blacklist(message.mobile_number_formatted)
            message.is_number_blocked = (
                formatted_number in phone_bl_numbers or
                formatted_number in wa_recs.filtered(lambda wa_rec: wa_rec.wa_account_id == message.wa_account_id).mapped('number')
            )

    # ------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Override to check blacklist number and also add to blacklist if user has send stop message."""
        messages = super().create(vals_list)
        for message in messages:
            body = html2plaintext(message.body)
            if message.message_type == 'inbound' and message.mobile_number_formatted:
                body_message = re.findall('([a-zA-Z]+)', body)
                message_string = "".join(i.lower() for i in body_message)
                try:
                    if message_string in self._get_opt_out_message():
                        self.env['phone.blacklist'].sudo().add(
                            number=wa_phone_validation.wa_phone_format_for_blacklist(message.mobile_number_formatted),
                            message=_("User has been opt out of receiving WhatsApp messages"),
                        )
                    else:
                        self.env['phone.blacklist'].sudo().remove(
                            number=wa_phone_validation.wa_phone_format_for_blacklist(message.mobile_number_formatted),
                            message=_("User has opted in to receiving WhatsApp messages"),
                        )
                except UserError:
                    # there was something wrong with number formatting that cannot be
                    # accepted by the blacklist -> simply skip, better be defensive
                    _logger.warning(
                        'Whatsapp: impossible to change opt-in status of %s (formatted as %s) as it is not a valid number (whatsapp.message-%s)',
                        message.mobile_number, message.mobile_number_formatted, message.id
                    )
        return messages

    @api.autovacuum
    def _gc_whatsapp_messages(self):
        """ To avoid bloating the database, we remove old whatsapp.messages that have been correctly
        received / sent and are older than 15 days.'

        We use these messages mainly to tie a customer answer to a certain document channel, but
        only do so for the last 15 days (see '_find_active_channel').

        After that period, they become non-relevant as the real content of conversations is kept
        inside discuss.channel / mail.messages (as every other discussions).

        Impact of GC when using the 'reply-to' function from the WhatsApp app as the customer:
          - We could loose the context that a message is 'a reply to' another one, implying that
          someone would reply to a message after 15 days, which is unlikely.
          (To clarify: we will still receive the message, it will just not give the 'in-reply-to'
          context anymore on the discuss channel).
          - We could also loose the "right channel" in that case, and send the message to a another
          (or a new) discuss channel, but it is again unlikely to answer more than 15 days later. """

        domain = self._get_whatsapp_gc_domain()
        self.env['whatsapp.message'].search(domain).unlink()

    def _get_whatsapp_gc_domain(self):
        date_threshold = fields.Datetime.now() - timedelta(
            days=self.env['whatsapp.message']._ACTIVE_THRESHOLD_DAYS)
        return [
            ('create_date', '<', date_threshold),
            ('state', 'not in', ['outgoing', 'error', 'cancel'])
        ]

    def _get_formatted_number(self, sanitized_number, country_code):
        """ Format a valid mobile number for whatsapp.

        Examples: ``'+919999912345'`` -> ``'919999912345'``

        :return: formatted mobile number

        TDE FIXME: remove in master
        """
        mobile_number_parse = phone_validation.phone_parse(sanitized_number, country_code)
        return f'{mobile_number_parse.country_code}{mobile_number_parse.national_number}'

    @api.model
    def _get_opt_out_message(self):
        return ['stop', 'unsubscribe', 'stop promotions']

    # ------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------

    def button_resend(self):
        """ Resend a failed message. """
        if self.filtered(lambda rec: rec.state != 'error'):
            raise UserError(_("You can not resend message which is not in failed state."))
        self._resend_failed()

    def button_cancel_send(self):
        """ Cancel a draft or outgoing message. """
        if self.filtered(lambda rec: rec.state != 'outgoing'):
            raise UserError(_("You can not cancel message which is in queue."))
        self.state = 'cancel'

    # ------------------------------------------------------------
    # SEND
    # ------------------------------------------------------------

    def _resend_failed(self):
        """Resend failed template messages and messages in active discuss channels."""
        retryable_messages = self.filtered(lambda msg: msg.state == 'error' and msg.failure_type != 'whatsapp_unrecoverable')

        # filter out outdated channel messages to avoid spamming whatsapp
        discuss_messages = retryable_messages.filtered(lambda msg: msg.mail_message_id.model == 'discuss.channel')
        discuss_channel_ids = [id_ for id_ in discuss_messages.mail_message_id.mapped('res_id') if id_]
        valid_discuss_channels = self.env['discuss.channel'].browse(discuss_channel_ids).exists().filtered(
            lambda channel: channel.whatsapp_channel_valid_until
            and channel.whatsapp_channel_valid_until >= fields.Datetime.now()  # worst case, they will fail
        )
        cancelled_discuss_messages = discuss_messages.filtered(
            lambda msg: msg.mail_message_id.res_id not in valid_discuss_channels.ids
        )
        retryable_messages = retryable_messages - cancelled_discuss_messages

        cancelled_discuss_messages.write({'state': 'cancel', 'failure_type': 'outdated_channel'})
        retryable_messages.write({'state': 'outgoing', 'failure_type': False, 'failure_reason': False})
        self.env.ref('whatsapp.ir_cron_send_whatsapp_queue')._trigger()

    def _send_cron(self):
        """ Send all outgoing messages. """
        # order by template to have more relevant duplicate detection
        # order descending so non-template messages are processed first, as they have a time limit
        records = self.search([
            ('state', '=', 'outgoing'),
        ], order='wa_template_id', limit=500)
        # should not commit during tests
        records._send_message(with_commit=not modules.module.current_test)
        if len(records) == 500:  # assumes there are more whenever search hits limit
            self.env.ref('whatsapp.ir_cron_send_whatsapp_queue')._trigger()

    def _send(self, force_send_by_cron=False):
        if len(self) <= 1 and not force_send_by_cron:
            self._send_message()
        else:
            self.env.ref('whatsapp.ir_cron_send_whatsapp_queue')._trigger()

    def _assert_recipient_identifier(self):
        if not self.mobile_number_formatted:
            raise WhatsAppError(failure_type='phone_invalid')
        return self.mobile_number_formatted

    def _get_sent_whatsapp_message_values(self, send_response):
        """Values to write on a message once successfully sent, some derived from the API response."""
        return {'state': 'sent', 'msg_uid': send_response.get('msg_uid')}

    def _send_with_identifier(self, wa_api, **send_kwargs):
        return wa_api._send_whatsapp_to_identifier(bsuid=None, number=self.mobile_number_formatted, **send_kwargs)

    def _send_message(self, with_commit=False):
        """ Prepare json data for sending messages, attachments and templates."""
        # init api
        message_to_api = {}
        for account, messages in groupby(self, lambda msg: msg.wa_account_id):
            if not account:
                # TDE note: error not handled for overrides (e.g. MA)
                messages = self.env['whatsapp.message'].concat(messages)
                messages.write({
                    'failure_type': 'unknown',
                    'failure_reason': 'Missing whatsapp account for message.',
                    'state': 'error',
                })
                self -= messages
                continue
            wa_api = WhatsAppApi(account)
            for message in messages:
                message_to_api[message] = wa_api

        sent_message_vals = set()
        for whatsapp_message in self:
            wa_api = message_to_api[whatsapp_message]
            # try to make changes with current user (notably due to ACLs), but limit
            # to internal users to avoid crash - rewrite me in master please
            if whatsapp_message.create_uid._is_internal():
                whatsapp_message = whatsapp_message.with_user(whatsapp_message.create_uid)
            if whatsapp_message.state != 'outgoing':
                _logger.info("Message state in %s state so it will not sent.", whatsapp_message.state)
                continue
            is_duplicate = False
            msg_uid = False
            try:
                parent_message_id = False
                # body would always come from plaintext2html hence the url text is already the url and references are redundant
                body = html2plaintext(whatsapp_message.body, include_references=False)
                recipient_identifier = whatsapp_message._assert_recipient_identifier()
                if whatsapp_message.mobile_number_formatted and whatsapp_message.is_number_blocked:
                    raise WhatsAppError(failure_type='blacklisted')  # noqa: TRY301

                # based on template
                if template := whatsapp_message.wa_template_id:
                    message_type = 'template'
                    if whatsapp_message.wa_template_id.status != 'approved' or whatsapp_message.wa_template_id.quality == 'red':
                        raise WhatsAppError(failure_type='template')
                    whatsapp_message.message_type = 'outbound'
                    if whatsapp_message.mail_message_id.model != whatsapp_message.wa_template_id.model:
                        raise WhatsAppError(failure_type='template')

                    RecordModel = self.env[whatsapp_message.mail_message_id.model].with_user(whatsapp_message.env.user)
                    from_record = RecordModel.browse(whatsapp_message.mail_message_id.res_id)

                    # if retrying message then we need to unlink previous attachment
                    # in case of header with report in order to generate it again
                    if whatsapp_message.wa_template_id.report_id and whatsapp_message.wa_template_id.header_type == 'document' and whatsapp_message.mail_message_id.attachment_ids:
                        whatsapp_message.mail_message_id.attachment_ids.unlink()

                    # generate sending values, components and attachments
                    send_vals, attachment = whatsapp_message.wa_template_id._get_send_template_vals(
                        record=from_record,
                        whatsapp_message=whatsapp_message,
                    )
                    # reports are considered always unique
                    if not template.report_id:
                        send_vals_without_attachments = dict(send_vals)
                        # the same attachment re-uploaded will have a different identifier
                        # TODO MASTER avoid having to upload as part of the "get template values" flow
                        if template.header_type in ('image', 'video', 'document'):
                            components = [component_vals for component_vals in send_vals['components'] if component_vals['type'] != 'header']
                            send_vals_without_attachments['components'] = components
                        unique_message_vals = (recipient_identifier, frozendict(send_vals_without_attachments))
                        if unique_message_vals not in sent_message_vals:
                            sent_message_vals.add(unique_message_vals)
                        else:
                            is_duplicate = True
                    if attachment and attachment not in whatsapp_message.mail_message_id.attachment_ids:
                        # Clone the attachment to ensure the template's attachment is not affected by message changes
                        cloned_attachment = attachment.copy({'res_model': whatsapp_message.mail_message_id.model, 'res_id': whatsapp_message.mail_message_id.res_id})
                        whatsapp_message.mail_message_id.attachment_ids = [(4, cloned_attachment.id)]
                # based on interactive template
                elif whatsapp_message.wa_interactive_id:
                    message_type = 'interactive'
                    send_vals = whatsapp_message.wa_interactive_id._prepare_send_values(
                        attachment=whatsapp_message.mail_message_id.attachment_ids[:1],
                        wa_account_id=whatsapp_message.wa_account_id,
                    )
                # no template
                elif whatsapp_message.mail_message_id.attachment_ids:
                    attachment_vals = whatsapp_message._prepare_attachment_vals(whatsapp_message.mail_message_id.attachment_ids[0], wa_account_id=whatsapp_message.wa_account_id)
                    message_type = attachment_vals.get('type')
                    send_vals = attachment_vals.get(message_type)
                    if body:
                        send_vals['caption'] = body
                else:
                    message_type = 'text'
                    send_vals = {
                        'preview_url': True,
                        'body': body,
                    }
                # Tagging parent message id if parent message is available
                if whatsapp_message.mail_message_id and whatsapp_message.mail_message_id.parent_id:
                    parent_id = whatsapp_message.mail_message_id.parent_id.wa_message_ids
                    if parent_id:
                        parent_message_id = parent_id[0].msg_uid
                if not is_duplicate:
                    send_response = whatsapp_message._send_with_identifier(
                        wa_api, message_type=message_type, send_vals=send_vals, parent_message_id=parent_message_id,
                    )
                    msg_uid = send_response.get('msg_uid')
            except WhatsAppError as we:
                whatsapp_message._handle_error(whatsapp_error_code=we.error_code, error_message=we.error_message,
                                               failure_type=we.failure_type)
            except (UserError, ValidationError) as e:
                whatsapp_message._handle_error(failure_type='unknown', error_message=str(e))
            else:
                if is_duplicate:
                    whatsapp_message.state = 'cancel'
                elif whatsapp_message.state == 'outgoing':
                    if not msg_uid:
                        whatsapp_message._handle_error(failure_type='unknown')
                    else:
                        # Message already posted for model 'discuss.channel', post message in active channel for other models
                        if message_type == 'template' and whatsapp_message.wa_template_id.model != 'discuss.channel':
                            whatsapp_message._post_message_in_active_channel()
                        whatsapp_message.write(whatsapp_message._get_sent_whatsapp_message_values(send_response))
                if with_commit:
                    self.env.cr.commit()

    def _handle_error(self, failure_type=False, whatsapp_error_code=False, error_message=False):
        """ Format and write errors on the message. """
        self.ensure_one()
        state = 'error'
        if whatsapp_error_code:
            if whatsapp_error_code in WHATSAPP_RETRYABLE_ERROR_CODES:
                failure_type = 'whatsapp_recoverable'
            else:
                failure_type = 'whatsapp_unrecoverable'
        if not failure_type:
            failure_type = 'unknown'
        if whatsapp_error_code in BOUNCED_ERROR_CODES:
            state = 'bounced'
        self.write({
            'failure_type': failure_type,
            'failure_reason': error_message,
            'state': state,
        })

    def _post_message_in_active_channel(self):
        """ Notify the active channel that someone has sent template message. """
        self.ensure_one()
        if not self.wa_template_id:
            return
        channel = self.wa_account_id._find_active_channel(self.mobile_number_formatted)
        if not channel:
            return

        # same user, different model: print full content of message into conversation
        if channel.is_member:
            body = self.body
            message_type = "comment"
            silent = False
        # diffrent user from any model: warn chat is about to be moved into a new conversation
        else:
            if self.mail_message_id.model and self.mail_message_id.res_id:
                record_name = self.mail_message_id.record_name
                url = f"{self.get_base_url()}/odoo/{self.mail_message_id.model}/{self.mail_message_id.res_id}"
                record_link = f"<a target='_blank' href='{url}'>{escape(record_name)}</a>"
            else:
                record_link = _("another document")
            body = Markup(
                _("A new template was sent on %(record_link)s.<br>"
                  "Future replies will be transferred to a new chat.",
                  record_link=record_link
            ))
            message_type = "notification"
            silent = True
        channel.sudo().message_post(
            body=body,
            message_type=message_type,
            silent=silent,
            subtype_xmlid='mail.mt_comment',
        )

    @api.model
    def _prepare_attachment_vals(self, attachment, wa_account_id):
        """ Upload the attachment to WhatsApp and return prepared values to attach to the message. """
        whatsapp_media_type = next((
            media_type
            for media_type, mimetypes
            in self._SUPPORTED_ATTACHMENT_TYPE.items()
            if attachment.mimetype in mimetypes),
            False
        )

        if not whatsapp_media_type:
            raise WhatsAppError(_("Attachment mimetype is not supported by WhatsApp: %s.", attachment.mimetype))

        # /web/content/<id> only redirects to this same signed url, and Meta seems
        # to rate limit per ASN of the host it fetches from, so let it fetch the
        # bucket directly instead of going through the instance.
        # See https://github.com/chatwoot/chatwoot/issues/13540
        if attachment.type == 'cloud_storage':
            whatsapp_media_url = attachment.with_context(
                cloud_storage_download_url_time_to_expiry=7 * 24 * 60 * 60,
            )._to_http_stream().url
            whatsapp_media_vals = {'link': whatsapp_media_url}
        elif attachment._is_remote_source():
            whatsapp_media_vals = {'link': attachment.url}
        else:
            wa_api = WhatsAppApi(wa_account_id)
            whatsapp_media_uid = wa_api._upload_whatsapp_document(attachment)
            whatsapp_media_vals = {'id': whatsapp_media_uid}

        vals = {
            'type': whatsapp_media_type,
            whatsapp_media_type: whatsapp_media_vals,
        }

        if whatsapp_media_type == 'document':
            vals[whatsapp_media_type]['filename'] = attachment.name

        return vals

    # ------------------------------------------------------------
    # CALLBACK
    # ------------------------------------------------------------

    def _process_statuses(self, value):
        """ Process status of the message like 'send', 'delivered' and 'read'."""
        mapping = {'failed': 'error', 'cancelled': 'cancel'}
        processed_message_ids = set()

        for statuses in value.get('statuses', []):
            whatsapp_message = self.env['whatsapp.message'].sudo().search([('msg_uid', '=', statuses['id'])])
            if whatsapp_message:
                whatsapp_message.state = mapping.get(statuses['status'], statuses['status'])
                processed_message_ids.add(whatsapp_message.id)
                whatsapp_message._update_message_fetched_seen()
                if statuses['status'] == 'failed':
                    error = statuses['errors'][0] if statuses.get('errors') else None
                    if error:
                        whatsapp_message._handle_error(whatsapp_error_code=error['code'],
                                                          error_message=f"{error['code']} : {error['title']}")
        return self.env['whatsapp.message'].browse(sorted(processed_message_ids, reverse=True)).sudo()

    def _update_message_fetched_seen(self):
        """ Update message status for the whatsapp recipient. """
        self.ensure_one()
        if self.mail_message_id.model != 'discuss.channel':
            return
        if self.state not in ["read", "delivered"]:
            return
        channel = self.env['discuss.channel'].browse(self.mail_message_id.res_id)
        channel_member = channel.channel_member_ids.filtered(lambda cm: cm.partner_id == channel.whatsapp_partner_id)
        if not channel_member:
            return
        channel_member = channel_member[0]
        if self.state == 'read':
            channel_member.write({
                'seen_message_id': self.mail_message_id.id,
                'last_seen_dt': fields.Datetime.now(),
            })
        Store(bus_channel=channel).add(channel_member, "_store_seen_fields")
