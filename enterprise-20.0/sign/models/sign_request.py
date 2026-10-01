# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
import time
import uuid
import logging

from werkzeug.urls import url_quote
from markupsafe import Markup
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tools import SQL, get_lang, is_html_empty, format_date, formataddr, html2plaintext
from odoo.tools.urls import urljoin as url_join

MAX_EXTERNAL_SIGNATURE_UPLOAD_SIZE = 25 * 1024 * 1024

_logger = logging.getLogger(__name__)


class SignRequest(models.Model):
    _name = 'sign.request'
    _description = "Signature Request"
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _default_access_token(self):
        return str(uuid.uuid4())

    def _get_mail_link(self, email, subject):
        return "mailto:%s?subject=%s" % (url_quote(email), url_quote(subject))

    @api.model
    def _selection_target_model(self):
        return [(model.model, model.name)
                for model in self.env['ir.model'].sudo().search([('model', '!=', 'sign.request'), ('is_mail_thread', '=', True)])]

    template_id = fields.Many2one('sign.template', string="Template", required=True, index=True)
    subject = fields.Char(string="Email Subject")
    reference = fields.Char(required=True, string="Document Name", help="This is how the document will be named in the mail")
    reference_doc = fields.Reference(string="Linked To", selection='_selection_target_model', index='btree_not_null')

    access_token = fields.Char('Security Token', required=True, default=_default_access_token, readonly=True, copy=False)
    share_link = fields.Char(string="Share Link", compute='_compute_share_link', readonly=False)
    is_shared = fields.Boolean(string="Share Request Button", compute='_compute_is_shared', inverse='_inverse_is_shared')

    request_item_ids = fields.One2many('sign.request.item', 'sign_request_id', string="Signers", copy=True)
    state = fields.Selection([
        ("shared", "Shared"),
        ("scheduled", "Scheduled"),
        ("sent", "To Sign"),
        ("signed", "Signed"),
        ("canceled", "Cancelled"),
        ("expired", "Expired"),
    ], default='sent', tracking=True, group_expand=True, copy=False, index=True)

    template_document_ids = fields.Many2many('sign.document', string="Documents", compute='_compute_template_document_ids')
    # only holds the working copies that already exist, as they are created lazily, so anything
    # about to write into a document's file wants to call _get_signing_documents() instead
    request_document_ids = fields.One2many('sign.request.document', 'sign_request_id', string="Request Documents Binaries", copy=False)
    nb_wait = fields.Integer(string="Sent Requests", compute="_compute_stats", store=True)
    nb_closed = fields.Integer(string="Completed Signatures", compute="_compute_stats", store=True)
    nb_total = fields.Integer(string="Requested Signatures", compute="_compute_stats", store=True)
    progress = fields.Char(string="Progress", compute="_compute_progress", compute_sudo=True)
    start_sign = fields.Boolean(string="Signature Started", help="At least one signer has signed the document.", compute="_compute_progress", compute_sudo=True)
    integrity = fields.Boolean(string="Integrity of the Sign request", compute='_compute_integrity', compute_sudo=True)

    active = fields.Boolean(default=True, string="Active", copy=False)
    favorited_ids = fields.Many2many('res.users', string="Favorite of")

    color = fields.Integer()
    request_item_infos = fields.Json(compute="_compute_request_item_infos")
    last_action_date = fields.Datetime(related="message_ids.create_date", readonly=True, string="Last Action Date")
    completion_date = fields.Date(string="Completion Date", compute="_compute_completion_date", compute_sudo=True, store=True)
    communication_company_id = fields.Many2one('res.company', string="Company used for communication", default=lambda self: self.env.company)

    sign_log_ids = fields.One2many('sign.log', 'sign_request_id', string="Logs", help="Activity logs linked to this request")
    template_tags = fields.Many2many('sign.template.tag', string='Tags')
    cc_partner_ids = fields.Many2many('res.partner', string='Copy to', compute='_compute_cc_partners')
    message = fields.Html('sign.message')
    message_cc = fields.Html('sign.message_cc')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments', readonly=True, copy=False, ondelete="restrict", bypass_search_access=True)
    completed_document_attachment_ids = fields.Many2many('ir.attachment', 'sign_request_completed_document_rel', string='Completed Documents', readonly=True, copy=False, ondelete="restrict", bypass_search_access=True)

    need_my_signature = fields.Boolean(compute='_compute_need_my_signature', search='_search_need_my_signature')

    validity = fields.Date(string='Valid Until')
    reminder_enabled = fields.Boolean(default=False)
    reminder = fields.Integer(string='Reminder', default=7)
    last_reminder = fields.Date(string='Last reminder', default=fields.Date.context_today)
    certificate_reference = fields.Boolean(string="Certificate Reference", default=False)

    send_channel = fields.Selection([
        ("email", "Email"),
        ("shared", "Shared Link"),
    ], string="Delivery Method", default='email', required=True)
    scheduled_date = fields.Datetime(string='Scheduled Date')

    sign_activity_ids = fields.One2many(
        'mail.activity',
        'sign_request_id',
        string='Linked Activities',
    )

    @api.depends('template_id')
    def _compute_template_document_ids(self):
        for sign_request in self:
            sign_request.template_document_ids = sign_request.template_id.sudo().document_ids

    @api.constrains('reminder_enabled', 'reminder')
    def _check_reminder(self):
        for request in self:
            if request.reminder_enabled and request.reminder <= 0:
                raise UserError(_("We can only send reminders in the future - as soon as we find a way to send reminders in the past we'll notify you.\nIn the mean time, please make sure to input a positive number of days for the reminder interval."))

    @api.depends('state')
    def _compute_is_shared(self):
        for sign_request in self:
            sign_request.is_shared = sign_request.state == 'shared'

    def _inverse_is_shared(self):
        for sign_request in self:
            if sign_request.is_shared:
                sign_request.state = 'shared'
            else:
                sign_request.state = 'sent'

    @api.depends_context('uid')
    def _compute_need_my_signature(self):
        my_partner_id = self.env.user.partner_id
        for sign_request in self:
            sign_request.need_my_signature = any(sri.partner_id.id == my_partner_id.id and sri.state == 'sent' and sri.is_mail_sent for sri in sign_request.request_item_ids)

    @api.model
    def _search_need_my_signature(self, operator, value):
        if operator != 'in':
            return NotImplemented
        my_partner_id = self.env.user.partner_id
        documents_ids = self.env['sign.request.item'].search([('partner_id', '=', my_partner_id.id), ('state', '=', 'sent'), ('is_mail_sent', '=', True)]).mapped('sign_request_id').ids
        return [('id', 'in', documents_ids)]

    @api.depends('request_item_ids.state')
    def _compute_stats(self):
        for rec in self:
            rec.nb_total = len(rec.request_item_ids)
            rec.nb_wait = len(rec.request_item_ids.filtered(lambda sri: sri.state == 'sent'))
            rec.nb_closed = rec.nb_total - rec.nb_wait

    @api.depends('request_item_ids.state')
    def _compute_progress(self):
        for rec in self:
            rec.start_sign = bool(rec.nb_closed)
            rec.progress = "{} / {}".format(rec.nb_closed, rec.nb_total)

    @api.depends('request_item_ids.state')
    def _compute_completion_date(self):
        for rec in self:
            rec.completion_date = rec.request_item_ids.sorted(key="signing_date", reverse=True)[:1].signing_date if not rec.nb_wait else None

    @api.depends('request_item_ids.state', 'request_item_ids.partner_id.name')
    def _compute_request_item_infos(self):
        for request in self:
            request.request_item_infos = [{
                'id': item.id,
                'partner_name': item.display_name,
                'state': item.state,
                'signing_date': format_date(self.env, item.signing_date) if item.signing_date else ''
            } for item in request.request_item_ids]

    @api.depends('message_follower_ids.partner_id')
    def _compute_cc_partners(self):
        for sign_request in self:
            sign_request.cc_partner_ids = sign_request.message_follower_ids.partner_id - sign_request.request_item_ids.partner_id

    @api.depends('request_item_ids.access_token', 'state')
    def _compute_share_link(self):
        self.share_link = False
        for sign_request in self.filtered(lambda sr: sr.state == 'shared'):
            sign_request.share_link = "%s/sign/document/mail/%s/%s" % (self.get_base_url(), sign_request.id, sign_request.request_item_ids[0].sudo().access_token)

    @api.model_create_multi
    def create(self, vals_list):
        sign_requests = super().create(vals_list)
        sign_requests.template_id._check_send_ready()
        for sign_request in sign_requests:
            if not sign_request.request_item_ids:
                raise ValidationError(_("A valid sign request needs at least one sign request item"))
            sign_request.template_tags = [Command.set(sign_request.template_id.tag_ids.ids)]
            sign_request.attachment_ids.write({'res_model': sign_request._name, 'res_id': sign_request.id})
            sign_request.message_subscribe(partner_ids=sign_request.request_item_ids.partner_id.ids)
            sign_request._check_and_enforce_signature_ordering()  # in case one of the signers are signing himself using external service
            sign_request._check_external_signature_documents_size()
            sign_request._populate_constant_items()
            self.env['sign.log'].sudo().create({'sign_request_id': sign_request.id, 'action': 'create'})

            if sign_request.scheduled_date:
                sign_request.state = 'scheduled'
                self.env.ref('sign.ir_cron_sign_state_action')._trigger(
                    at=sign_request.scheduled_date + timedelta(minutes=1)
                )

        if not self.env.context.get('no_sign_mail'):
            sign_requests.send_signature_accesses()
        return sign_requests

    def _populate_constant_items(self):
        self.ensure_one()
        sign_values_by_role = defaultdict(
            lambda: defaultdict(lambda: self.env['sign.item']))
        for item in self.template_id.sign_item_ids:
            if item.constant:
                sign_values_by_role[item.responsible_id][str(item.id)] = {
                    # For constant strikethrough items, use "striked" instead of item name,
                    # since item name returns "strikethrough" but we need "striked" to set the value correctly.
                    "name": item.name if item.type_id.sudo().item_type != 'strikethrough' else 'striked',
                    "type_id": item.type_id.id,
                    "auto_field": item.type_id.sudo().auto_field
                }

        if not sign_values_by_role:
            return
        for sign_request_item in self.sudo().request_item_ids:
            if sign_request_item.role_id in sign_values_by_role:
                sign_items = sign_values_by_role[sign_request_item.role_id]
                corrected_dict = sign_items.copy()
                for key, value in sign_items.items():
                    corrected_dict[key] = value["name"]
                    if value.get("auto_field"):
                        # For custom fields, the auto-fill functionality will only work when `auto_field` is defined.
                        # Because constant fields won't ever have a 'sign.request.item.value' reference to be filled.
                        corrected_dict[key] = sign_request_item.with_context(populate_constant_item=True)._get_auto_field_value({
                            "id": value.get("type_id"),
                            "auto_field": value.get("auto_field")
                        })

                sign_request_item._fill(corrected_dict)

    def write(self, vals):
        today = fields.Date.context_today(self)
        if vals.get('validity'):
            if fields.Date.from_string(vals['validity']) < today:
                vals['state'] = 'expired'
            self.sign_activity_ids.date_deadline = vals['validity']

        if vals.get('reference_doc'):
            model, rec = vals['reference_doc'].split(',')
            record = self.env[model].browse(int(rec)).exists()
            if not record or not record.has_access('read'):
                raise ValidationError(self.env._("You don't have access to the linked document."))

        return super().write(vals)

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        if 'attachment_ids' not in default:
            for request, vals in zip(self, vals_list):
                vals['attachment_ids'] = request.attachment_ids.copy().ids
        return vals_list

    def copy(self, default=None):
        sign_requests = super().copy(default)
        for old_request, new_request in zip(self, sign_requests):
            new_request.message_subscribe(partner_ids=old_request.cc_partner_ids.ids)
        return sign_requests

    @api.ondelete(at_uninstall=False)
    def _unlink_if_not_signed(self):
        """
        Raise an error if any of the records are in 'signed' state.
        """
        if any(r.state == 'signed' for r in self):
            raise UserError(_("Signed documents cannot be deleted for legal reasons. Please archive them instead."))

    @api.ondelete(at_uninstall=True)
    def _unlink_working_documents(self):
        # The working documents keep their file in an attachment, so they have to be removed
        # through the ORM. Their 'restrict' foreign key makes sure nothing skips this.
        self.request_document_ids.sudo().unlink()

    def action_archive(self):
        self.filtered(lambda sr: sr.active and sr.state == 'sent').cancel()
        return super().action_archive()

    def action_send(self):
        if len(self) != 1:
            raise UserError(self.env._("Please select only one document to send."))
        return self.template_id.open_sign_send_dialog()

    def action_save_as_template(self):
        if len(self) != 1:
            raise UserError(self.env._("Please select only one document to save as a template."))
        self.template_id.write({'active': True, 'is_one_time_request': False, 'favorited_ids': [Command.link(self.env.user.id)]})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': self.env._("Saved as a template"),
                'type': 'success',
                'next': self.env['ir.actions.act_window']._for_xml_id('sign.sign_template_action'),
            },
        }

    def _check_senders_validity(self):
        invalid_senders = self.create_uid.filtered(lambda u: not u.email_formatted)
        if invalid_senders:
            raise ValidationError(_("Please configure senders'(%s) email addresses", ', '.join(invalid_senders.mapped('name'))))

    def _check_signers_roles_validity(self):
        for sign_request in self:
            template_roles = sign_request.sudo().template_id.sign_item_ids.responsible_id
            sign_request_items = sign_request.request_item_ids
            if len(sign_request_items) != max(len(template_roles), 1) or \
                    set(sign_request_items.role_id.ids) != (set(template_roles.ids) if template_roles else set([self.env.ref('sign.sign_item_role_default').id])):
                raise ValidationError(_("You must specify one signer for each role of your sign template"))

    def _check_signers_partners_validity(self):
        for sign_request in self:
            sign_request_items = sign_request.request_item_ids
            if sign_request.state != 'shared':
                email_list = [sri.signer_email for sri in sign_request_items if sri.signer_email]
                alias_emails = self.env['mail.alias.domain'].sudo()._find_aliases(email_list)
                if alias_emails:
                    raise UserError(_("This email address is already used as a mail alias and cannot be used for signing."))
                if any(not sri.partner_id for sri in sign_request_items):
                    raise ValidationError(_("Signer(s) not set."))

    def _get_final_recipients(self):
        all_recipients = set(self.request_item_ids.mapped('signer_email')) | \
                         set(self.cc_partner_ids.filtered(lambda p: p.email_formatted).mapped('email'))
        return all_recipients

    def _get_next_sign_request_items(self):
        self.ensure_one()
        sign_request_items_sent = self.request_item_ids.filtered(lambda sri: sri.state == 'sent')
        if not sign_request_items_sent:
            return self.env['sign.request.item']
        smallest_order = min(sign_request_items_sent.mapped('mail_sent_order'))
        next_request_items = sign_request_items_sent.filtered(lambda sri: sri.mail_sent_order == smallest_order)
        return next_request_items

    def go_to_document(self):
        self.ensure_one()
        request_items = self.request_item_ids.filtered(lambda r: not r.partner_id or (r.state == 'sent' and r.partner_id.id == self.env.user.partner_id.id))
        sequenced_signature_mail = any(req.mail_sent_order > 1 for req in self.request_item_ids)

        can_sign_now = False
        if request_items:
            if not sequenced_signature_mail:
                can_sign_now = True
            else:
                # If mail_sent_order set, only allow signing if the current user is in the next batch of signers to receive the mail.
                next_items = self._get_next_sign_request_items()
                can_sign_now = self.env.user.partner_id in next_items.partner_id

        return {
            'name': self.reference,
            'type': 'ir.actions.client',
            'tag': 'sign.Document',
            'context': {
                'id': self.id,
                'token': self.access_token,
                'need_to_sign': bool(request_items),
                'create_uid': self.create_uid.id,
                'state': self.state,
                'request_item_states': {str(item.id): item.is_mail_sent for item in self.request_item_ids},
                'sequenced_signature_mail': sequenced_signature_mail,
                'can_sign_now': can_sign_now,
                'document_count': len(self.sudo().template_id.document_ids),
                'template_id': self.template_id.id,
            },
        }

    def go_to_signable_document(self, request_items=None):
        """ go to the signable document as the signers for specified request_items or the current user"""
        self.ensure_one()
        if not request_items:
            request_items = self.request_item_ids.filtered(lambda r: not r.partner_id or (r.state == 'sent' and r.partner_id.id == self.env.user.partner_id.id))
        if not request_items:
            return
        # signer may be opening the document again while an external session is still running,
        # so it catches up before deciding where they should go
        request_item_sudo = request_items[:1].sudo()
        request_item_sudo._sync_external_signature()
        if request_item_sudo.state == 'sent' and request_item_sudo.role_id.requires_external_signature:
            # their signature is still valid, so they carry on where they stopped
            signing_url = request_item_sudo._get_external_signature_url().get('url')
            if signing_url:
                return {
                    'type': 'ir.actions.act_url',
                    'url': signing_url,
                    'target': 'self',
                }
        return {
            'name': self.reference,
            'type': 'ir.actions.client',
            'tag': 'sign.SignableDocument',
            'context': {
                'id': self.id,
                'token': request_items[:1].sudo().access_token,
                'need_to_sign': True,
                'create_uid': self.create_uid.id,
                'state': self.state,
                'request_item_states': {item.id: item.is_mail_sent for item in self.request_item_ids},
                'template_editable': self.nb_closed == 0,
                'token_list': request_items[1:].sudo().mapped('access_token'),
                'name_list': [item.partner_id.name for item in request_items[1:]],
                'document_count': len(self.sudo().template_id.document_ids),
                'request_item_id_list': request_items[1:].ids,
                'reference': self.reference,
            },
        }

    def get_sign_request_documents(self):
        if not self:
            raise UserError(_('You should select at least one document to download.'))

        if len(self) == 1:
            if self.state == 'signed':
                return {
                    'name': 'Signed Document',
                    'type': 'ir.actions.act_url',
                    'url': '/sign/download/%(request_id)s/%(access_token)s/completed' % {'request_id': self.id, 'access_token': self.access_token},
                }
            else:
                return {
                    'name': 'Template Document',
                    'type': 'ir.actions.act_url',
                    'url': '/sign/download/%(request_id)s/%(access_token)s/origin' % {'request_id': self.id, 'access_token': self.access_token},
                }
        else:
            return {
                'name': 'Sign Request Documents',
                'type': 'ir.actions.act_url',
                'url': f'/sign/download/zip/{",".join(map(str, self.ids))}',
            }

    def _get_linked_record_action(self, default_action=None):
        """" Return the default action for any kind of record. This method can be override for specific kind or rec
        """
        self.ensure_one()
        if not default_action:
            default_action = {}
        # user might not have access to Action Window model
        action_rec_sudo = self.env['ir.actions.act_window'].sudo().sudo().search([
            ('res_model', '=', self.reference_doc._name),
            ('context', 'not ilike', 'active_id')], limit=1)
        if action_rec_sudo:
            action = action_rec_sudo._get_action_dict()
            action.update({
                "views": [(False, "form")],
                "view_mode":  'form',
                "res_id": self.reference_doc.id,
                "target": 'current',
            })
        else:
            action = default_action
        return action

    def get_close_values(self):
        self.ensure_one()
        # check if frontend user or backend
        action = self.env["ir.actions.actions"]._for_xml_id("sign.sign_request_action")
        result = {"action": action, "label": _("Close"), "custom_action": False}
        if self.reference_doc and self.reference_doc.exists() and self.reference_doc.has_access('read'):
            action = self._get_linked_record_action(action)
            result = {"action": action, "label": _("Back to %s", self.reference_doc._description), "custom_action": True}
        return result

    @api.depends("progress", "start_sign")
    def _compute_integrity(self):
        for document in self:
            try:
                document.integrity = self.sign_log_ids._check_document_integrity()
            except Exception:
                document.integrity = False

    def toggle_favorited(self):
        self.ensure_one()
        self.write({'favorited_ids': [(3 if self.env.user in self.favorited_ids else 4, self.env.user.id)]})

    def _refuse(self, refuser, refusal_reason):
        """ Refuse a SignRequest. It can only be used in SignRequestItem._refuse
        :param res.partner refuser: the refuser who refuse to sign
        :param str refusal_reason: the refusal reason provided by the refuser
        """
        self.ensure_one()
        if self.state != 'sent':
            raise UserError(_("This sign request cannot be refused"))
        self._check_senders_validity()
        self.cancel()

        # cancel request and activities for other unsigned users
        for user in self.request_item_ids.partner_id.user_ids.filtered(lambda u: u.has_group('sign.group_sign_user')):
            self.activity_unlink(['sign.mail_activity_data_signature_request'], user_id=user.id)

        # send emails to signers and cc_partners
        for sign_request_item in self.request_item_ids:
            self._send_refused_message(refuser, refusal_reason, sign_request_item.partner_id,
                                       access_token=sign_request_item.sudo().access_token, force_send=True, sign_request_item=sign_request_item)
        for partner in self.cc_partner_ids.filtered(lambda p: p.email_formatted) - self.request_item_ids.partner_id:
            self._send_refused_message(refuser, refusal_reason, partner)

    def _send_refused_message(self, refuser, refusal_reason, partner, access_token=None, force_send=False, sign_request_item=None):
        self.ensure_one()
        if access_token is None:
            access_token = self.access_token
        subject = _("The document %(template_name)s has been rejected by %(partner_name)s",
            template_name=self.template_id.name,
            partner_name=refuser.name,
        )
        base_url = self.get_base_url()
        partner_lang = get_lang(self.env, lang_code=partner.lang).code
        body = self.env['ir.qweb']._render('sign.sign_template_mail_refused', {
            'record': self,
            'recipient': partner,
            'refuser': refuser,
            'link': url_join(base_url, 'sign/document/%s/%s' % (self.id, access_token)),
            'subject': subject,
            'body': Markup('<p style="white-space: pre">{}</p>').format(refusal_reason),
        }, lang=partner_lang, minimal_qcontext=True)

        self.with_context(lang=partner.lang or self.env.lang)._message_send_mail(
            body,
            record_name=self.reference,
            notif_values={
                'model_description': _('Signature Refusal'),
                'company': self.communication_company_id or self.create_uid.company_id,
                'partner': partner,
            },
            mail_values={
                'subject': subject,
                **({'email_to': formataddr((sign_request_item.partner_id.name, sign_request_item.signer_email))} if sign_request_item else {}),
            },
            force_send=force_send,
        )

    def send_signature_accesses(self):
        # Send/Resend accesses for 'sent' sign.request.items by email
        today = fields.Date.context_today(self)
        allowed_request_ids = self.filtered(lambda sr: sr.state in ['scheduled', 'sent'])
        allowed_request_ids._check_senders_validity()
        for sign_request in allowed_request_ids:
            sign_request._get_next_sign_request_items().send_signature_accesses()
            sign_request.last_reminder = today
        if self.env.context.get('show_reminder_notification'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': self.env._("Reminder sent successfully"),
                    'type': 'success',
                },
            }

    @api.model
    def _cron_reminder(self):
        today = fields.Date.today()
        # find all expired sign requests and those that need a reminder
        # in one query, the code will handle them differently
        # note: archived requests are not fetched.
        self.flush_model()
        res = self.env.execute_query(SQL('''
        SELECT id
        FROM sign_request sr
        WHERE sr.state = 'sent'
        AND active = TRUE
        AND (
            sr.validity < %(today)s
            OR (sr.reminder_enabled AND sr.last_reminder + sr.reminder * ('1 day'::interval) <= %(today)s)
        )
        ''', today=today))
        request_to_send = self.env['sign.request']
        for request in self.browse(v[0] for v in res):
            if request.validity and request.validity < today:
                request.state = 'expired'
                for item in request.request_item_ids.filtered('external_signature_session_token'):
                    item._cancel_external_signature()
                request.request_document_ids._discard_pending_signature()
            else:
                request_to_send += request
        # If an external signing service already completed the signature, but the
        # signature was never synchronized back, consider the signer complete instead
        # of reminding them to sign again.
        for item in request_to_send.request_item_ids.filtered(
                lambda item: item.state == 'sent' and item.role_id.requires_external_signature):
            item._sync_external_signature()
        request_to_send.filtered(lambda request: request.state == 'sent').with_context(force_send=False).send_signature_accesses()

    @api.model
    def _cron_update_state(self):
        """
        Automatically update sign requests from 'scheduled' to 'sent'
        when their scheduled_date has passed.
        """
        self.env['sign.request'].search([
            ('state', '=', 'scheduled'),
            ('scheduled_date', '<=', fields.Datetime.now()),
            ('scheduled_date', '!=', False),
        ]).state = 'sent'

    def _sign(self):
        """ Sign a SignRequest. It can only be used in the SignRequestItem._sign """
        self.ensure_one()
        if self.state != 'sent' or any(sri.state != 'completed' for sri in self.request_item_ids):
            raise UserError(_("This sign request cannot be signed"))
        self.write({'state': 'signed'})

        if self.sign_activity_ids:
            self.sign_activity_ids._action_done()
        self._send_completed_documents()

        if self.reference_doc:
            model = self.env['ir.model']._get(self.reference_doc._name)
            if model.is_mail_thread:
                # attach a copy of the signed document to the record for easy retrieval
                attachment_values = [{
                    "name": doc.document_id.name,
                    "raw": doc.file,
                    "type": "binary",
                    "res_model": self.reference_doc._name,
                    "res_id": self.reference_doc.id
                } for doc in self._get_completed_documents()]
                self.env["ir.attachment"].with_context(no_document=True).create(attachment_values)

        self._write_auto_fields_value(self._sync_auto_field_value())

    def _sync_auto_field_value(self):
        """ Resolve values from a signed document to candidate target record updates.

        This method processes items configured with ``auto_field`` and ``auto_write``.
        To prevent data conflicts, if multiple signature items map to the same Odoo field,
        only fields with exactly one unique new value are returned.

        :return: Mapping of target records to their candidate field updates.
                 Format: {target_record: {field_name: set(values)}}
        :rtype: dict
        """
        self.ensure_one()

        items_to_update = self.sudo().template_id.sign_item_ids.filtered(
            lambda i:
            i.type_id.auto_field and
            i.type_id.auto_write and
            not i.constant
        )

        values_dict = self.env['sign.request.item.value'].sudo()._read_group(
            [('sign_item_id', 'in', items_to_update.ids), ('sign_request_id', '=', self.id)],
            groupby=['sign_item_id'],
            aggregates=['value:array_agg']
        )
        signed_values = {
            sign_item.id: values[0] for sign_item, values in values_dict
        }

        auto_fields_update = {}
        failed_fields_by_record = defaultdict(list)
        lang_code = (self.communication_company_id or self.create_uid.company_id).partner_id.lang
        for item in items_to_update:
            sign_request_item = self.request_item_ids.filtered(lambda r: r.role_id.id == item.responsible_id.id)
            # Get the base record and the raw field path (e.g. 'company_id.name')
            base_record_sudo = sign_request_item._get_auto_field_target_record(item.type_id)
            new_value = signed_values.get(item.id)
            if not base_record_sudo or not new_value:
                continue

            try:
                # Resolve the dot notation first to get the actual target record and field
                field_path = item.type_id.auto_field
                resolved_record, resolved_field = self.env['sign.request.item']._resolve_auto_field_path(base_record_sudo, field_path)
                if not resolved_record or not resolved_field:
                    raise ValueError(self.env._(  # noqa: TRY301
                        "Could not resolve auto-field path %(path)s from %(record)s",
                        path=field_path, record=base_record_sudo.display_name,
                    ))

                # Fetch the field definition from the resolved record's model
                field_record_sudo = self.env['ir.model.fields'].sudo()._get(resolved_record._name, resolved_field)

                # Format the value using the resolved record and field definition
                processed_value = self.env['sign.request.item']._parse_auto_field_value(
                    field_record_sudo=field_record_sudo,
                    item_type_sudo=item.type_id,
                    record=resolved_record,
                    value=new_value,
                    lang_code=lang_code
                )

                # Compare against the actual current value of the resolved record
                # We use `is not None` so we don't accidentally skip valid '0' integers or 'False' booleans
                if processed_value is not None and processed_value != resolved_record[resolved_field]:
                    # Group strictly by the resolved record and resolved field
                    record_fields = auto_fields_update.setdefault(resolved_record, {})
                    record_fields.setdefault(resolved_field, set()).add(processed_value)
            except Exception as e:  # noqa: BLE001
                field_label = self._humanize_auto_field_path(item.type_id.model_id.model, item.type_id.auto_field)
                failed_fields_by_record[base_record_sudo].append({
                    'old_value': self.env._("Previous value"),
                    'new_value': str(new_value),
                    'label': field_label,
                })
                _logger.warning(
                    "Sign Sync: Failed to resolve auto-field '%s' (value=%s) on %s for sign request %s. Error: %s",
                    field_label, new_value, base_record_sudo, self.id, e
                )

        for base_record, changed_fields in failed_fields_by_record.items():
            self._post_auto_field_tracking_message(
                record_to_post=self,
                message=self.env._(
                    "Failed to auto-update fields on %(record)s",
                    record=Markup("<b>%s</b>") % base_record._get_html_link(),
                ),
                changed_fields=changed_fields,
                success=False,
            )

        return auto_fields_update

    def _write_auto_fields_value(self, auto_fields_update):
        """ Apply candidate field values to their respective target records.

        Each target write is wrapped in its own ``cr.savepoint()`` so that a
        failure on one target rolls back only that write. The signature itself
        (already persisted earlier in the transaction) and the other targets'
        writes are left untouched. On failure the partial write is rolled back
        before the failure chatter message is posted, so only the chatter
        persists.

        :param dict auto_fields_update: Mapping of target records to their field updates.
                                        Format: {target_record: {field_name: set(values)}}
        """
        for target_record, fields_map in auto_fields_update.items():
            # Clean dictionary comprehension to grab only fields with exactly 1 unique change
            vals_to_write = {
                field_name: field_unique_values.pop()
                for field_name, field_unique_values in fields_map.items()
                if len(field_unique_values) == 1
            }
            if not vals_to_write:
                continue

            # Format old/new values for the chatter the same way Odoo formats
            # tracked field changes (localized numbers, currency symbol for
            # monetary, selection labels, ...). ``_create_mail_tracking_values``
            # covers every field type except ``html``. It lives on the abstract
            # ``mail.track.mixin`` but its logic is generic, so we call it off
            # the mixin class with the target record. This works
            # whether or not the target model inherits the mixin (an auto-field
            # path may resolve to a non-thread model).
            fields_info = target_record.fields_get(list(vals_to_write))
            changed_fields = []
            for fname, new_val in vals_to_write.items():
                field_info = fields_info[fname]
                old_val = target_record[fname]
                if field_info['type'] == 'html':
                    old_display = "None" if is_html_empty(old_val) else html2plaintext(old_val)
                    new_display = "None" if is_html_empty(new_val) else html2plaintext(new_val)
                else:
                    # Call it off the class so we can pass the target as ``self``,
                    # even if the target model doesn't inherit the mixin.
                    tracking_values = self.pool['mail.track.mixin']._create_mail_tracking_values(
                        target_record, old_val, new_val, fname, field_info
                    )
                    old_display = tracking_values['old_value']
                    new_display = tracking_values['new_value']
                changed_fields.append({
                    'old_value': old_display,
                    'new_value': new_display,
                    'label': field_info['string'],
                })

            # ``_track_discard`` and ``message_post`` only exist on
            # ``mail.thread`` records, a target not inheriting it has
            # neither, so guard both chatter operations on this target.
            target_is_thread = isinstance(target_record, self.pool['mail.thread'])
            try:
                sign_request_sender = self.create_uid
                # Isolate each target write so a failure rolls back only that
                # write, leaving the signature and the other targets intact.
                with self.env.cr.savepoint():
                    target_record.with_user(sign_request_sender).with_context(
                        mail_notrack=True, tracking_disable=True
                    ).write(vals_to_write)
                    if target_is_thread:
                        target_record.sudo()._track_discard()
                self._post_auto_field_tracking_message(
                    record_to_post=self,
                    message=self.env._(
                        "Auto-updated fields on %(record)s",
                        record=Markup("<b>%s</b>") % target_record._get_html_link(),
                    ),
                    changed_fields=changed_fields,
                )
                if target_is_thread:
                    self._post_auto_field_tracking_message(
                        record_to_post=target_record,
                        message=self.env._(
                            "Fields auto-updated by signing %(record)s",
                            record=Markup("<b>%s</b>") % self._get_html_link(),
                        ),
                        changed_fields=changed_fields,
                    )
            except (UserError, ValidationError, AccessError, ValueError, TypeError) as e:
                _logger.warning(
                    "Sign Sync: Failed to update auto-fields on %s with values %s. Error: %s",
                    target_record, vals_to_write, e
                )
                record_link = Markup("<b>%s</b>") % target_record._get_html_link()
                if isinstance(e, AccessError):
                    message = self.env._("Auto-update blocked: request sender lacks permission to update %(record)s", record=record_link)
                else:
                    message = self.env._("Failed to auto-update fields on %(record)s", record=record_link)
                self._post_auto_field_tracking_message(
                    record_to_post=self, message=message,
                    changed_fields=changed_fields,
                    success=False,
                )

    @api.model
    def _post_auto_field_tracking_message(self, record_to_post, message, changed_fields, success=True):
        """ Render and post an auto-field tracking message on ``record_to_post``.

        :param record_to_post: record whose chatter receives the message.
        :param message: the translated headline as ``Markup``.
        :param changed_fields: list of {'old_value', 'new_value', 'label'} dicts.
        :param success: when True, render with the success styling; otherwise
                        render with the failure styling.
        """
        if success:
            title = Markup(
                '<span class="text-muted">'
                '<i class="oi text-info me-1" data-icon="wand_stars"></i> %s'
                '</span>'
            ) % message
        else:
            title = Markup(
                '<span class="text-muted fw-bold">'
                '<i class="oi" data-icon="warning"></i> %s'
                '</span>'
            ) % message
        # TDE note: use post with source
        body = self.env['ir.qweb']._render(
            'sign.template_sign_auto_field_tracking',
            {
                'message_title': title,
                'changed_fields': changed_fields,
            }
        )
        record_to_post.sudo().message_post(body=body)

    @api.model
    def _humanize_auto_field_path(self, base_model, field_path):
        """ Translate a technical dot path (e.g. ``company_id.country_id.code``)
        into a human-readable chain using each segment's field label
        (e.g. ``Company > Country > Country Code``). Falls back to the raw
        segment when a segment cannot be resolved.
        """
        labels = []
        current_model = base_model
        for fname in field_path.split('.'):
            field = None
            if current_model and current_model in self.env:
                field = self.env[current_model]._fields.get(fname)
            if not field:
                labels.append(fname)
                break
            labels.append(field._description_string(self.env))
            current_model = field.comodel_name if field.relational else None
        return ' > '.join(labels)

    def cancel(self):
        # Exclude sign requests that are in 'signed' state as they mustn't be canceled.
        sign_requests = self.filtered(lambda request: request.state != 'signed')
        for sign_request in sign_requests:
            sign_request.write({'access_token': self._default_access_token(), 'state': 'canceled'})
        sign_requests.request_item_ids._cancel()

        # cancel activities for signers
        for user in sign_requests.request_item_ids.sudo().partner_id.user_ids.filtered(lambda u: u.has_group('sign.group_sign_user')):
            sign_requests.activity_unlink(['sign.mail_activity_data_signature_request'], user_id=user.id)
        # Avoid 'MissingError' when canceling from the activity:
        # The activity's own unlink() runs right after this and expects the record to still exist.
        if not self.env.context.get('skip_sign_activity_unlink'):
            self.sign_activity_ids.unlink()

        self.env['sign.log'].sudo().create([{'sign_request_id': sign_request.id, 'action': 'cancel'} for sign_request in sign_requests])
        sign_requests.request_document_ids.sudo().unlink()

    def _check_and_enforce_signature_ordering(self):
        """ Forces a strict signing order when any signer cryptographically signs the
        document himself, so each signature deterministically covers all previous
        signers' values. """
        for sign_request in self:
            items = sign_request.request_item_ids
            if any(items.role_id.mapped('requires_external_signature')):
                for order, item in enumerate(items.sorted(key=lambda item: (item.mail_sent_order, item.id)), start=1):
                    item.mail_sent_order = order

    def _check_external_signature_documents_size(self):
        """ Refuses a request whose documents size exceeds the signature service limit. """
        self.ensure_one()
        if not any(self.request_item_ids.role_id.mapped('requires_external_signature')):
            return
        documents_total_size = sum(self.template_id.document_ids.attachment_id.mapped('file_size'))
        if documents_total_size > MAX_EXTERNAL_SIGNATURE_UPLOAD_SIZE:
            raise UserError(self.env._(
                "The documents of this request are too large to be signed with a qualified "
                "electronic signature. They cannot exceed %s MB in total.",
                MAX_EXTERNAL_SIGNATURE_UPLOAD_SIZE // (1024 * 1024)))

    def _is_partially_signed(self):
        """ Whether some signers already signed, so the documents carry their values. """
        self.ensure_one()
        return any(item.state == 'completed' for item in self.request_item_ids)

    def _get_completed_documents(self):
        """ Retrieves all signed documents associated with the request that are in the 'completed' state. """
        return self.request_document_ids.filtered(lambda document: document.state == 'completed')

    def _get_signing_documents(self):
        """ The working copies of this request's documents, creating the ones that do not
        exist yet.

        A working copy carries the file from one signer to the next, so it is only needed
        once something has to be written into it, like stamping a signer's values, freezing the
        bytes an external signature will seal, or applying the company seal at the end. We
        create it here instead of when the request is made, ensuring that abandoned requests
        consume no resources.

        Every caller about to write into a signing document goes through this method.
        """
        self.ensure_one()
        documents = self.request_document_ids
        missing_documents = self.template_id.document_ids - documents.document_id
        if missing_documents:
            documents += self.env['sign.request.document'].create([{
                'sign_request_id': self.id,
                'document_id': document.id,
            } for document in missing_documents])
        return documents

    def _send_completed_documents(self):
        """ Send the completed document to signers and Contacts in copy with emails
        """
        self.ensure_one()
        if self.state != 'signed':
            raise UserError(_('The sign request has not been fully signed'))
        self._check_senders_validity()

        if not self._get_completed_documents():
            self._generate_completed_documents()

        signers = [{'name': signer.partner_id.name, 'email': signer.signer_email, 'id': signer.partner_id.id} for signer in self.request_item_ids]
        request_edited = any(log.action == "update" for log in self.sign_log_ids)
        for sign_request_item in self.request_item_ids:
            self._send_completed_documents_message(signers, request_edited, sign_request_item.partner_id,
                                                   access_token=sign_request_item.sudo().access_token, with_message_cc=False, force_send=True, sign_request_item=sign_request_item)

        cc_partners_valid = self.cc_partner_ids.filtered(lambda p: p.email_formatted)
        for cc_partner in cc_partners_valid:
            self._send_completed_documents_message(signers, request_edited, cc_partner)
        if cc_partners_valid:
            body = _(
                "The mail has been sent to contacts in copy: %(contacts)s",
                contacts=cc_partners_valid.mapped("name"),
            )
            if not is_html_empty(self.message_cc):
                body += self.message_cc
            self.message_post(body=body, attachment_ids=self.attachment_ids.ids + self.completed_document_attachment_ids.ids)
        if self.reference_doc:
            self.reference_doc.message_post_with_source(
                'sign.template_sign_request_completed',
                render_values={
                    'sign_request': self,
                    'document_url': url_join(self.get_base_url(), 'sign/document/%s/%s' % (self.id, self.access_token)),
                },
                # the certificate of completion is generated after the signed documents,
                # it does not belong on the linked record
                attachment_ids=self.completed_document_attachment_ids.sorted('id')[:-1].ids,
                partner_ids=cc_partners_valid.ids,
            )

    def _send_completed_documents_message(self, signers, request_edited, partner, access_token=None, with_message_cc=True, force_send=False, sign_request_item=None):
        self.ensure_one()
        if access_token is None:
            access_token = self.access_token
        partner_lang = get_lang(self.env, lang_code=partner.lang).code
        base_url = self.get_base_url()
        local_signer = {}
        if not self.request_item_ids.filtered(lambda sri: sri.is_mail_sent) and not self.write_uid._is_public():
            # if there is no mail sent, it means that the signature was done locally without sending mails to signers
            # in this case we want to specify in the email that the signature was done by the local user and not by the signer himself
            local_signer = {'name': self.create_uid.partner_id.name, 'email': self.create_uid.partner_id.email}

        body = self.env['ir.qweb']._render('sign.sign_template_mail_completed', {
            'record': self,
            'link': url_join(base_url, 'sign/document/%s/%s' % (self.id, access_token)),
            'subject': '%s signed' % self.reference,
            'body': self.message_cc if with_message_cc and not is_html_empty(self.message_cc) else False,
            'recipient_name': partner.name,
            'recipient_id': partner.id,
            'signers': signers,
            'request_edited': request_edited,
            'local_signer': local_signer,
            }, lang=partner_lang, minimal_qcontext=True)

        self.with_context(lang=partner.lang or self.env.lang)._message_send_mail(
            body,
            record_name=self.reference,
            notif_values={
                'model_description': _('Signature Completion'),
                'company': self.communication_company_id or self.create_uid.company_id,
                'partner': partner,
            },
            mail_values={
                'attachment_ids': self.attachment_ids.ids + self.completed_document_attachment_ids.ids,
                'subject': _('%s has been edited and signed', self.reference) if request_edited else _('%s has been signed', self.reference),
                **({'email_to': formataddr((sign_request_item.partner_id.name, sign_request_item.signer_email))} if sign_request_item else {}),
            },
            force_send=force_send,
        )

    @api.autovacuum
    def _gc_expired_sr(self):
        """
        Deletes all the shared sign requests which have an expired validity date
        """
        sign_request = self.env["sign.request"].search([("state", "=", "shared"), ("validity", "<", fields.Date.today())])
        sign_request.unlink()

    ##################
    # PDF Rendering  #
    ##################

    def _get_request_sender_timezone(self):
        self.ensure_one()
        return self.create_uid.tz or 'UTC'

    def _get_user_formatted_datetime(self, datetime_val):
        """
        Format a datetime in the sender's timezone, using the sender's
        preferred date/time format based on their language settings.
        """
        if datetime_val.tzinfo is None:
            datetime_val = datetime_val.replace(tzinfo=timezone.utc)
        localized = datetime_val.astimezone(ZoneInfo(self._get_request_sender_timezone()))
        lang = self.env['res.lang']._lang_get(self.create_uid.lang)
        user_date_format, user_time_format = lang.date_format, lang.time_format
        return localized.strftime(f"{user_date_format} {user_time_format}")

    def _get_final_signature_log_hash(self):
        """
        Fetch the log_hash of the final signature from the sign.log table.
        """
        self.ensure_one()
        if not self.certificate_reference:
            return False

        final_log = self.env['sign.log'].search([
            ('sign_request_id', '=', self.id),
            ('action', 'in', ['sign', 'create']),
        ], order='id DESC', limit=1)

        return final_log.log_hash if final_log else False

    def _generate_completed_documents(self):
        if self.state != 'signed':
            raise UserError(_("The completed document cannot be created because the sign request is not fully signed"))

        for record in self:
            if not record._get_completed_documents():
                record._get_signing_documents()._finalize_documents()
                attachment_ids = self.env['ir.attachment'].create([{
                    'name': document.document_id.name,
                    'raw': document.file,
                    'type': 'binary',
                    'res_model': self._name,
                    'res_id': record.id,
                } for document in record._get_completed_documents()])

                # print the report with the public user in a sudoed env
                # public user because we don't want groups to pollute the result
                # (e.g. if the current user has the group Sign Manager,
                # some private information will be sent to *all* signers)
                # sudoed env because we have checked access higher up the stack
                public_user = self.env.ref('base.public_user', raise_if_not_found=False)
                if not public_user:
                    # public user was deleted, fallback to avoid crash (info may leak)
                    public_user = self.env.user
                pdf_content, __ = self.env["ir.actions.report"].with_user(public_user).sudo()._render_qweb_pdf(
                    'sign.action_sign_request_print_logs',
                    record.id,
                    data={'format_date': format_date, 'company_id': record.communication_company_id}
                )
                attachment_log = self.env['ir.attachment'].with_context(no_document=True).create({
                    'name': self.env._("Certificate of completion - %s.pdf", time.strftime('%Y-%m-%d - %H:%M:%S')),
                    'raw': pdf_content,
                    'type': 'binary',
                    'res_model': self._name,
                    'res_id': record.id,
                })
                self.completed_document_attachment_ids = [Command.link(attachment_log.id)] + [Command.link(att.id) for att in attachment_ids]

    def _get_signing_field_name(self) -> str:
        """Generates a name for the signing field of the pdf document

        Returns:
            str: the name of the signature field
        """
        return self.communication_company_id.name

    ##################
    # Mail overrides #
    ##################

    def _message_send_mail(self, body, notif_values=None, mail_values=None, record_name=False, force_send=False, scheduled_date=False):
        """ Shortcut to sent a notification or an email. """
        notif_values = notif_values or {}
        company = notif_values.get('company')
        model_description = notif_values.get('model_description')
        partner = notif_values.get('partner')
        notification_layout_xmlid = notif_values.get('notification_layout_xmlid', 'sign.sign_mail_notification_light')

        mail_values = mail_values or {}
        if 'author_id' not in mail_values:
            mail_values['author_id'] = self.create_uid.partner_id.id
            mail_values['email_from'] = self.create_uid.email_formatted
        if 'email_to' not in mail_values:
            mail_values['email_to'] = partner.email_formatted

        if partner and len(partner.user_ids) == 1 and partner.user_ids.notification_type == "inbox":
            self.message_notify(
                attachment_ids=mail_values.get("attachment_ids"),
                author_id=self.create_uid.partner_id.id,
                body=body,
                email_from=mail_values.get("email_from"),
                force_record_name=record_name,
                force_send=force_send,
                mail_auto_delete=False,
                model_description=model_description,
                partner_ids=partner.ids,
                subject=mail_values.get("subject"),
            )

        mail_values['body_html'] = self.env['mail.render.mixin']._render_encapsulate(
            notification_layout_xmlid, body,
            context_record=self,
            add_context={
                'company': company,
                'model_description': model_description,
                'record_name': record_name,
            },
        )
        mail_values['reply_to'] = mail_values.get('email_from')
        if scheduled_date:
            mail_values['scheduled_date'] = scheduled_date
        mail = self.env['mail.mail'].sudo().create(mail_values)
        if force_send and not scheduled_date:
            mail.send_after_commit()
        return mail

    def _schedule_activity(self, sign_users):
        for user in sign_users:
            self.with_context(mail_activity_quick_update=True).activity_schedule(
                'sign.mail_activity_data_signature_request',
                user_id=user.id
            )
