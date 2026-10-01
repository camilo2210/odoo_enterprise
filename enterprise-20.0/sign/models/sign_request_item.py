# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import binascii
import logging
import requests
import uuid

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from hashlib import sha256
from markupsafe import Markup
from random import randint
from werkzeug.urls import url_quote, url_encode

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import consteq, email_normalize, formataddr, groupby, get_lang, html2plaintext, is_html_empty, plaintext2html
from odoo.tools.misc import hmac
from odoo.tools.urls import urljoin as url_join
from odoo.tools.mail import email_split_and_format
from odoo.addons.iap.tools import iap_tools

_logger = logging.getLogger(__name__)

QES_IAP_SERVICE_NAME = 'sign_qes'
# How many times a signature is collected without being usable before the attempt is given
# up. The service cannot tell that what it produced does not arrive whole, so nothing but
# this stops the same one being asked for on every page the signer opens
MAX_EXTERNAL_SIGNATURE_FAILURES = 5
QES_DEFAULT_HOST = 'https://sign.api.odoo.com'
QES_HOST_TIMEOUT = 15
QES_HOST_UPLOAD_TIMEOUT = 120


class SignRequestItem(models.Model):
    _name = 'sign.request.item'
    _description = "Signature Request Item"
    _inherit = ['portal.mixin', 'mail.track.mixin']
    _rec_name = 'partner_id'

    def _default_access_token(self):
        return str(uuid.uuid4())

    def _get_mail_link(self, email, subject):
        return "mailto:%s?subject=%s" % (url_quote(email), url_quote(subject))

    # this display_name (with sudo) is used for many2many_tags especially the partner_id is private
    display_name = fields.Char(compute_sudo=True)

    partner_id = fields.Many2one('res.partner', string="Signer", ondelete='restrict', index='btree_not_null')
    sign_request_id = fields.Many2one('sign.request', string="Signature Request", ondelete='cascade', required=True, copy=False, index=True)
    sign_item_value_ids = fields.One2many('sign.request.item.value', 'sign_request_item_id', string="Value")
    reference = fields.Char(related='sign_request_id.reference', string="Document Name")
    mail_sent_order = fields.Integer(default=1)
    communication_company_id = fields.Many2one(related='sign_request_id.communication_company_id')

    access_token = fields.Char(required=True, default=_default_access_token, readonly=True, copy=False, groups="base.group_system")
    access_via_link = fields.Boolean('Accessed Through Token', copy=False)
    role_id = fields.Many2one('sign.item.role', string="Role", required=True, index=True, readonly=True)
    sms_number = fields.Char(related='partner_id.phone', readonly=False, depends=(['partner_id']), store=True, copy=False)
    sms_token = fields.Char('SMS Token', readonly=True, copy=False)
    external_signature_session_token = fields.Char('External Signature Session Token', readonly=True, copy=False, groups="base.group_system",
        help="Session token returned by the external signing service.")
    external_signature_failures = fields.Integer(readonly=True, copy=False,
        help="How many times a signature came back for this signer without being usable. The "
             "service has no way of knowing, so it would keep handing back the same one.")
    signed_without_extra_auth = fields.Boolean('Signed Without Extra Authentication', default=False, readonly=True, copy=False)

    signature = fields.Binary(attachment=True, copy=False)
    frame_hash = fields.Char(size=256, compute='_compute_frame_hash')
    signing_date = fields.Date('Signed on', readonly=True, copy=False)

    state = fields.Selection([
        ("sent", "To Sign"),
        ("completed", "Signed"),
        ("canceled", "Cancelled"),
    ], readonly=True, default="sent", copy=False, index=True)
    color = fields.Integer(compute='_compute_color')

    signer_email = fields.Char(string='Email', compute="_compute_email", store=True, readonly=False, tracking=True)
    is_mail_sent = fields.Boolean(readonly=True, copy=False, help="The signature mail has been sent.")
    change_authorized = fields.Boolean(related='role_id.change_authorized')
    auth_method = fields.Selection(related='role_id.auth_method')

    latitude = fields.Float(digits=(10, 7), copy=False)
    longitude = fields.Float(digits=(10, 7), copy=False)

    @api.constrains('signer_email')
    def _check_signer_email_validity(self):
        invalid_items = self.filtered(lambda sri: sri.partner_id and not email_split_and_format(sri.signer_email))
        if invalid_items:
            raise ValidationError(self.env._(
                "The following signers are missing an email address:\n%s",
                ", ".join(invalid_items.partner_id.mapped('display_name')),
            ))

    @api.constrains('sign_request_id', 'partner_id', 'role_id')
    def _check_signers_validity(self):
        # this check allows one signer to be False, which is used to "share" a sign template
        self.sign_request_id._check_signers_roles_validity()
        self.sign_request_id._check_signers_partners_validity()

    @api.depends('signer_email')
    def _compute_frame_hash(self):
        db_uuid = self.env['ir.config_parameter'].sudo().get_str('database.uuid')
        for sri in self:
            if sri.partner_id:
                sri.frame_hash = sha256((sri.signer_email + db_uuid).encode()).hexdigest()
            else:
                sri.frame_hash = ''

    @api.depends('partner_id.name')
    def _compute_display_name(self):
        for sri in self:
            sri.display_name = sri.partner_id.display_name if sri.partner_id else _('Public User')

    def write(self, vals):
        if 'signer_email' in vals:
            for request in self.sign_request_id:
                child_items = self.filtered(lambda item: item.sign_request_id == request)
                request._track_record(child_items, ['signer_email'])
        if vals.get('partner_id') is False:
            raise UserError(_("You need to define a signatory"))
        request_items_reassigned = self.env['sign.request.item']
        if vals.get('partner_id'):
            request_items_reassigned |= self.filtered(lambda sri: sri.partner_id and sri.partner_id.id != vals['partner_id'])
            if any(sri.state != 'sent'
                   or sri.sign_request_id.state != 'sent'
                   or (sri.partner_id and not sri.role_id.change_authorized)
                   or sri.sign_request_id.state == 'shared'
                   for sri in request_items_reassigned):
                raise UserError(_("You cannot reassign this signatory"))
            new_sign_partner = self.env['res.partner'].browse(vals.get('partner_id'))
            for request_item in request_items_reassigned:
                sign_request = request_item.sign_request_id
                old_sign_user = request_item.partner_id.user_ids[:1]
                # remove old activities for internal users if they are no longer one of the unsigned signers of their sign requests
                if old_sign_user and old_sign_user.has_group('sign.group_sign_user') and \
                        not sign_request.request_item_ids.filtered(
                            lambda sri: sri.partner_id == request_item.partner_id and sri.state == 'sent' and sri not in request_items_reassigned):
                    sign_request.activity_unlink(['sign.mail_activity_data_signature_request'], user_id=old_sign_user.id)
                # create logs
                sign_request.message_post(
                    body=_('The contact of %(role)s has been changed from %(old_partner)s to %(new_partner)s.',
                           role=request_item.role_id.name, old_partner=request_item.partner_id.name, new_partner=new_sign_partner.name))

            # add new followers
            request_items_reassigned.sign_request_id.message_subscribe(partner_ids=[vals.get('partner_id')])
            # add new activities for internal users
            new_sign_user = self.env['res.users'].search([
                ('partner_id', '=', vals.get('partner_id')),
                ('all_group_ids', 'in', [self.env.ref('sign.group_sign_user').id])
            ], limit=1)
            if new_sign_user:
                activity_ids = set(request_items_reassigned.sign_request_id.activity_search(['sign.mail_activity_data_signature_request'], user_id=new_sign_user.id).mapped('res_id'))
                request_items_reassigned.sign_request_id.filtered(lambda sr: sr.id not in activity_ids)._schedule_activity(new_sign_user)

        if vals.get('signer_email') and not self.env.user.has_group('sign.group_sign_manager') and self.env.user != self.create_uid:
            raise UserError(_("You cannot change the email of a signatory"))

        res = super().write(vals)

        # change access token
        for request_item in request_items_reassigned.filtered(lambda sri: sri.is_mail_sent):
            request_item.sudo().update({'access_token': self._default_access_token()})
            if request_item.is_mail_sent and request_item.state == 'sent':
                request_item.send_signature_accesses()

        return res

    def _cancel(self, no_access=True):
        """ Cancel a SignRequestItem. It can only be used in the SignRequest.cancel or SignRequest._refuse
        :param bool no_access: Whether the sign request item cannot be accessed by the previous link in the email
        """
        for request_item in self:
            request_item_sudo = request_item.sudo()
            if request_item_sudo.external_signature_session_token:
                request_item_sudo._cancel_external_signature()
            request_item.write({
                'state': 'canceled' if request_item.state == 'sent' else request_item.state,
                'signing_date': fields.Date.context_today(self) if request_item.state == 'sent' else request_item.signing_date,
                'is_mail_sent': False if no_access else request_item.is_mail_sent,
            })
            request_item_sudo.write({'access_token': self._default_access_token() if no_access else request_item.access_token})

    def _refuse(self, request_state, refusal_reason, refusal_name="", refusal_email=""):
        """ Refuse a sign request item with 'sent' or 'shared' states. """
        self.ensure_one()
        if not self.env.su:
            raise UserError(_("This function can only be called with sudo."))

        # Get the post message according to the logged user.
        refuse_user = self.partner_id.user_ids[:1]
        # If refusing with a signed user, we use the user as the refuser.
        if not refuse_user and self.env.user and not self.env.user.is_public:
            refuse_user = self.env.user
        if refuse_user:
            message_post = _(
                "The signature has been refused by %(partner)s (%(role)s).",
                partner=self.partner_id.name,
                role=self.role_id.name
            )
        else:
            message_post = _(
                "The signature has been refused by %(name)s with email (%(email)s).",
                name=refusal_name,
                email=refusal_email,
            )
        refusal_reason = _("No specified reason") if not refusal_reason or refusal_reason.isspace() else refusal_reason
        reason_label = self.env._("Refusal reason:")
        message_post = Markup(
            '{}<br/><strong>{}</strong> <span style="white-space: pre-wrap;">{}</span>'
        ).format(message_post, reason_label, refusal_reason)

        if self.state == 'sent' and request_state == 'sent':
            self._refuse_sent(refuse_user, message_post, refusal_reason)
        elif self.state == 'sent' and request_state == 'shared':
            self._refuse_shared(refuse_user, message_post, refusal_name, refusal_email)
        else:
            raise UserError(_("This sign request item cannot be refused"))

    def _refuse_sent(self, refuse_user, message_post, refusal_reason):
        """ Refuse requests that were sent directly to the signers ('sent' state).
        The cancelling flow happens directly in the refused sign request. """
        self.env['sign.log'].create({'sign_request_item_id': self.id, 'action': 'refuse'})
        self.write({'signing_date': fields.Date.context_today(self), 'state': 'canceled'})

        # Mark the activity as done for the refuser.
        if refuse_user and refuse_user.has_group('sign.group_sign_user'):
            self.sign_request_id.activity_feedback(['mail.mail_activity_data_todo'], user_id=refuse_user.id)

        self.sign_request_id._track_set_log_author(self.env.ref('base.partner_root'))
        self.sign_request_id.message_post(body=message_post, author_id=self.env.ref('base.partner_root').id)
        self.sign_request_id._refuse(self.partner_id, refusal_reason)

    def _refuse_shared(self, refuse_user, message_post, refusal_name="", refusal_email=""):
        """ Refuse requests that were shared by a shared link ('shared' state).
        The request is duplicated and its copy is cancelled, allowing other users to also refuse it.
        Public users can also refuse the request by disclosing their identity (name and email). """
        user_identified = bool(refusal_name and refusal_email)
        if not refuse_user and not user_identified:
            raise UserError(_("The public user must identify itself for the refusal."))

        # Duplicate the sign request, allowing other users to also refuse it.
        request_copy_values = self.sign_request_id.copy_data()[0]
        request_copy_values['state'] = 'shared'
        new_request = self.env['sign.request'].create(request_copy_values)
        new_sign_request_item = new_request.request_item_ids

        # Do the refuse action in the request item and set the copied request as cancelled.
        self.env['sign.log'].create({'sign_request_item_id': new_sign_request_item.id, 'action': 'refuse'})
        new_sign_request_item.write({'signing_date': fields.Date.context_today(new_sign_request_item), 'state': 'canceled'})
        new_request._track_set_log_author(self.env.ref('base.partner_root'))
        new_request.state = "canceled"

        # Mark the activity as done for the refuser.
        if refuse_user and refuse_user.has_group('sign.group_sign_user'):
            new_sign_request_item.sign_request_id.activity_feedback(['mail.mail_activity_data_todo'], user_id=refuse_user.id)
        new_sign_request_item.sign_request_id.message_post(body=message_post, author_id=self.env.ref('base.partner_root').id)

        # Link the refusal partner to the cancelled request, it is used for easying the identification.
        refusal_partner = refuse_user.partner_id or self.env['res.partner'].search([('email', '=', refusal_email)], limit=1)
        if not refusal_partner:
            refusal_partner = self.env['res.partner'].create({'name': refusal_name, 'email': refusal_email})
        new_sign_request_item.partner_id = refusal_partner

    def _get_url_parameters(self, signer, expiry_link_timestamp):
        return url_encode({
                'timestamp': expiry_link_timestamp,
                'exp': signer._generate_expiry_signature(signer.id, expiry_link_timestamp)
            })

    def _get_access_token(self, signer):
        return signer.sudo().access_token

    def _get_sign_and_cancel_links(self, signer):
        expiry_link_timestamp = signer._generate_expiry_link_timestamp()
        url_params = self._get_url_parameters(signer, expiry_link_timestamp)
        partial_url = "sign/document/mail/%(request_id)s/%(access_token)s?%(url_params)s" % {
            'request_id': signer.sign_request_id.id,
            'access_token': self._get_access_token(signer),
            'url_params': url_params
        }
        link_sign = url_join(signer.get_base_url(), partial_url)
        company = self.communication_company_id
        if 'website_id' in company and company.website_id.domain:
            link_sign = url_join(company.website_id.domain, partial_url)
        link_cancel = link_sign + '&refuseDocument=1'

        return link_sign, link_cancel

    def _send_signature_access_message(self):
        for signer in self:
            signer_email_normalized = email_normalize(signer.signer_email or '')
            signer_lang = get_lang(self.env, lang_code=signer.partner_id.lang).code
            # We hide the validity information if it is the default (6 month from the create_date)
            has_default_validity = signer.sign_request_id.validity and signer.sign_request_id.validity - relativedelta(months=6) == signer.sign_request_id.create_date.date()
            link_sign, link_cancel = self._get_sign_and_cancel_links(signer)
            body = self.env['ir.qweb']._render('sign.sign_template_mail_request', {
                'record': signer,
                'link': link_sign,
                'link_cancel': link_cancel,
                'subject': signer.sign_request_id.subject,
                'body': signer.sign_request_id.message if not is_html_empty(signer.sign_request_id.message) else False,
                'use_sign_terms': self.env['ir.config_parameter'].sudo().get_bool('sign.use_sign_terms'),
                'user_signature': signer.create_uid.signature,
                'show_validity': signer.sign_request_id.validity and not has_default_validity,
            }, lang=signer_lang, minimal_qcontext=True)

            attachment_ids = signer.sign_request_id.attachment_ids.ids
            self.env['sign.request'].with_context(lang=signer.partner_id.lang or self.env.lang)._message_send_mail(
                body,
                record_name=signer.sign_request_id.reference,
                notif_values={
                    'model_description': _('Signature Request'),
                    'company': signer.communication_company_id or signer.sign_request_id.create_uid.company_id,
                    'partner': signer.partner_id,
                },
                mail_values={
                    'author_id': signer.create_uid.partner_id.id,
                    'email_from': signer.create_uid.email_formatted,
                    'email_to': formataddr((signer.partner_id.name, signer_email_normalized)),
                    'subject': signer.sign_request_id.subject,
                    'attachment_ids': attachment_ids,
                    'auto_delete': True,
                },
                force_send=self.env.context.get('force_send', True),  # only force_send if not from cron
                scheduled_date=signer.sign_request_id.scheduled_date,
            )
            signer.is_mail_sent = True

    def _is_pending_signer(self):
        """ Whether the request is waiting on this signer to sign. """
        self.ensure_one()
        return self in self.sign_request_id._get_next_sign_request_items()

    def sign(self, signature, **kwargs):
        """ Sign sign request items at once.
        :param signature: dictionary containing signature values and corresponding ids
        """
        self.ensure_one()
        if not self.env.su:
            raise UserError(_("This function can only be called with sudo."))
        elif self.state != 'sent' or self.sign_request_id.state != 'sent':
            raise UserError(_("This sign request item cannot be signed"))
        elif self.sign_request_id.validity and self.sign_request_id.validity < fields.Date.context_today(self):
            raise UserError(_('This sign request is not valid anymore'))

        if self.role_id.requires_external_signature:
            if self._get_documents_awaiting_external_signature():
                # their values are frozen behind their certificate. A new attempt must not change
                # what they are about to sign, rejecting the pending signature is what frees them
                return None
            # this signer signs the document themselves, so they are completed only once their
            # signature is embedded, which a later attempt or a batch job may be what does it
            self._sign(signature, validation_required=True, **kwargs)
            if self._is_applied_on_every_external_document():
                # the signature is approved and already embedded
                self._post_fill_request_item()
            return None

        self._sign(signature, **kwargs)

    def _sign(self, signature, **kwargs):
        """ Stores the sign request item values.
        :param signature: dictionary containing signature values and corresponding ids / signature image
        :param validation_required: boolean indicating whether the sign request item will after a further validation process or now
        """
        self.ensure_one()
        if not self.env.su:
            raise UserError(_("This function can only be called with sudo."))
        elif self.state != 'sent' or self.sign_request_id.state != 'sent':
            raise UserError(_("This sign request item cannot be signed"))
        elif self.sign_request_id.validity and self.sign_request_id.validity < fields.Date.context_today(self):
            raise UserError(_('This sign request is not valid anymore'))
        elif self not in self.sign_request_id._get_next_sign_request_items() and any(
                self.sign_request_id.request_item_ids.role_id.mapped('requires_external_signature')):
            # Enforce a signing order whenever a sign request includes external signers
            raise UserError(self.env._("The signers before you have not signed yet."))

        # Constant items are populated automatically and cannot be modified by the signer,
        # so they are excluded from required field validation.
        required_ids = set(self.sign_request_id.template_id.sign_item_ids.filtered(
            lambda r: r.responsible_id.id == self.role_id.id and r.required and not r.constant).ids)
        signature_ids = {int(k) for k in signature} if isinstance(signature, dict) else set()
        if not (required_ids <= signature_ids):  # Security check
            raise UserError(_("Some required items are not filled"))
        if self.state != 'sent' or self.sign_request_id.state != 'sent':
            raise UserError(_("This sign request item cannot be filled"))
        if not self.env.su:
            raise UserError(_("This function can only be called with sudo."))
        self._fill(signature, **kwargs)
        if not kwargs.get('validation_required', False):
            self._post_fill_request_item()

    def _send_no_credits_email(self):
        partner_lang = get_lang(self.env, lang_code=self.create_uid.partner_id.lang).code
        body = self.env['ir.qweb']._render('sign.sign_template_mail_not_enough_credits', {
            'record': self,
            'recipient_name': self.create_uid.name,
            'subject': '%s signed' % self.reference,
            'signer': self.partner_id,
            'auth_method': dict(self.role_id._fields['auth_method']._description_selection(self.env))[self.role_id.auth_method]
        }, lang=partner_lang, minimal_qcontext=True)

        self.env['sign.request'].with_context(lang=self.create_uid.lang or self.env.lang)._message_send_mail(
            body,
            record_name=self.reference,
            notif_values={
                'model_description': 'signature',
                'company': self.communication_company_id or self.create_uid.company_id,
                'partner': self.create_uid.partner_id,
            },
            mail_values={
                'author_id': self.create_uid.partner_id.id,
                'email_from': self.create_uid.email_formatted,
                'email_to': self.create_uid.email_formatted,
                'subject': _('%s: missing credits for extra-authentication', self.reference)
            },
            force_send=True,
        )

    def _post_fill_request_item(self):
        self.env['sign.log'].create({'sign_request_item_id': self.id, 'action': 'sign'})
        self.write({'signing_date': fields.Date.context_today(self), 'state': 'completed'})
        if self.signed_without_extra_auth:
            self._send_no_credits_email()

        # mark signature as done in next activity
        if not self.sign_request_id.request_item_ids.filtered(lambda sri: sri.partner_id == self.partner_id and sri.state == 'sent'):
            sign_user = self.partner_id.user_ids[:1]
            if sign_user and sign_user.has_group('sign.group_sign_user'):
                self.sign_request_id.activity_feedback(['sign.mail_activity_data_signature_request'], user_id=sign_user.id)
        sign_request = self.sign_request_id
        if any(sign_request._get_next_sign_request_items().role_id.mapped('requires_external_signature')):
            # Stamp the accumulated values now so the sealing signer's request does not
            # wait for this process while opening the signing view.
            try:
                sign_request._get_signing_documents()._apply_completed_items()
            except Exception:  # noqa: BLE001
                _logger.warning("Deferred value stamping failed for sign request %s", sign_request.id, exc_info=True)
        if all(sri.state == 'completed' for sri in sign_request.request_item_ids):
            sign_request._sign()
        elif all(sri.state == 'completed' for sri in sign_request.request_item_ids.filtered(lambda sri: sri.mail_sent_order == self.mail_sent_order)):
            sign_request.send_signature_accesses()

    def _fill(self, signature, **kwargs):
        """ Stores the sign request item values. (Can be used to pre-fill the document as a hack)
        :param signature: dictionary containing signature values and corresponding ids / signature image
        """
        self.ensure_one()
        authorised_ids = set(self.sign_request_id.template_id.sign_item_ids.filtered(lambda r: r.responsible_id.id == self.role_id.id).ids)
        signature_ids = {int(k) for k in signature} if isinstance(signature, dict) else set()
        if not (signature_ids <= authorised_ids):
            raise UserError(_("Some unauthorised items are filled"))

        if not isinstance(signature, dict):
            self.signature = signature
        else:
            SignItemValue = self.env['sign.request.item.value']
            sign_request = self.sign_request_id
            new_item_values_list = []
            item_values_dict = {str(sign_item_value.sign_item_id.id): sign_item_value for sign_item_value in self.sign_item_value_ids}
            signature_item_ids = set(sign_request.template_id.sign_item_ids.filtered(lambda r: r.type_id.item_type == 'signature').ids)
            for itemId in signature:
                frame = kwargs.get('frame', False)
                if frame and itemId in frame:
                    frame_value = frame[itemId].get('frameValue', False)
                    frame_has_hash = bool(frame[itemId].get('frameHash', False))
                else:
                    frame_value = False
                    frame_has_hash = False
                if itemId not in item_values_dict:
                    new_item_values_list.append({'sign_item_id': int(itemId), 'sign_request_id': sign_request.id,
                                                 'value': signature[itemId], 'frame_value': frame_value,
                                                 'frame_has_hash': frame_has_hash, 'sign_request_item_id': self.id})
                else:
                    item_values_dict[itemId].write({
                        'value': signature[itemId], 'frame_value': frame_value, 'frame_has_hash': frame_has_hash
                    })
                if int(itemId) in signature_item_ids:
                    self.signature = signature[itemId][signature[itemId].find(',') + 1:]
            SignItemValue.create(new_item_values_list)

    def send_signature_accesses(self):
        self.sign_request_id._check_senders_validity()
        users = self.partner_id.user_ids
        user_ids = set(users.sudo().search([('all_group_ids', 'in', self.env.ref('sign.group_sign_user').id), ('id', 'in', users.ids)]).ids)
        for sign_request, sign_request_items_list in groupby(self, lambda sri: sri.sign_request_id):
            notified_users = [sri.partner_id.user_ids[:1]
                              for sri in sign_request_items_list
                              if not sri.is_mail_sent and sri.state == 'sent' and sri.partner_id.user_ids[:1].id in user_ids]
            sign_request._schedule_activity(notified_users)
            body = _("The signature mail has been sent to: ")
            receiver_names = ["%s(%s)" % (sri.partner_id.name, sri.role_id.name) for sri in sign_request_items_list]
            body += ', '.join(receiver_names)
            if not is_html_empty(sign_request.message):
                body += sign_request.message
            if not sign_request.communication_company_id:
                sign_request.communication_company_id = self.env.company
            sign_request.message_post(body=body)
        self._send_signature_access_message()

    def _get_user_signature(self, signature_type='sign_signature'):
        """ Gets the user's stored sign_signature/sign_initials (needs sudo permission)
            :param str signature_type: 'sign_signature' or 'sign_initials'
            :returns bytes or False
        """
        self.ensure_one()
        sign_user = self.partner_id.user_ids[:1]
        current_user_sign = False
        if self.env.user._is_public() or sign_user and sign_user == self.env.user:
            current_user_sign = True
        if current_user_sign and signature_type in ['sign_signature', 'sign_initials']:
            return sign_user[signature_type].content
        return False

    def _get_user_signature_frame(self, signature_type='sign_signature_frame'):
        """ Gets the user's stored sign_signature/sign_initials (needs sudo permission)
            :param str signature_type: 'sign_signature' or 'sign_initials'
            :returns bytes or False
        """
        self.ensure_one()
        sign_user = self.partner_id.user_ids[:1]
        if sign_user and signature_type in ['sign_signature_frame', 'sign_initials_frame']:
            return sign_user[signature_type].content
        return False

    def _reset_sms_token(self):
        for record in self:
            record.sms_token = randint(100000, 999999)

    def _send_sms(self):
        self._reset_sms_token()
        sms_values = [{'body': _('Your confirmation code is %s', rec.sms_token), 'number': rec.sms_number} for rec in self]
        self.env['sms.sms'].sudo().create(sms_values).send()

    def _compute_access_url(self):
        super()._compute_access_url()
        for signature_request in self:
            signature_request.access_url = '/my/signature/%s' % signature_request.id

    @api.model
    def _generate_expiry_link_timestamp(self):
        duration = self.env['ir.config_parameter'].sudo().get_int('sign.link_expiry_duration') or 360
        expiry_date = fields.Datetime.now() + timedelta(hours=duration)
        return int(expiry_date.timestamp())

    @api.model
    def _generate_expiry_signature(self, sign_request_item_id, timestamp):
        return hmac(self.env(su=True), "sign_expiration", (timestamp, sign_request_item_id))

    def _validate_expiry(self, exp_timestamp, exp_hash):
        """ Validates if the expiry code is still valid
        :param float exp_timestamp: a timestamp provided by the user in the URL params
        :param str exp_hash: code provided in the URL to be checked
        """
        self.ensure_one()
        if not (exp_timestamp and exp_hash):
            return False
        exp_timestamp = int(exp_timestamp)
        now = fields.Datetime.now().timestamp()
        if now > exp_timestamp:
            return False
        return consteq(exp_hash, self._generate_expiry_signature(self.id, exp_timestamp))

    @api.depends('state')
    def _compute_color(self):
        color_map = {"canceled": 0,
                     "sent": 0,
                     "completed": 10}
        for sign_request_item in self:
            sign_request_item.color = color_map[sign_request_item.state]

    @api.depends('partner_id.email')
    def _compute_email(self):
        for sign_request_item in self.filtered(lambda sri: sri.state == "sent" or not sri.signer_email):
            sign_request_item.signer_email = sign_request_item.partner_id.email_normalized

    def _get_auto_field_target_record(self, item_type_sudo):
        """Determine the target record for a given sign.item.type."""
        linked_model = item_type_sudo.model_id.model

        if linked_model == 'res.partner':
            return self.partner_id

        linked_record_sudo = self.sign_request_id.reference_doc  # self has sudo privilege so the linked record is sudoed too
        # Ensure the linked record's model matches what the item type expects
        if linked_record_sudo and linked_record_sudo._name == linked_model:
            ir_model = self.env['ir.model'].sudo()._get(linked_record_sudo._name)
            if ir_model and ir_model.is_mail_thread:
                return linked_record_sudo

        return None

    def _get_auto_field_value(self, item_type):
        """ Return the automatic value of a sign item based on the linked model and partner access
        :return: str: auto_value
        """
        self.ensure_one()
        item_type_sudo = self.env['sign.item.type'].sudo().browse(item_type['id'])

        # For custom sign item types without model_id and auto_field, fetch last value from previous signatures.
        if item_type_sudo.custom and not item_type_sudo.auto_field and not item_type_sudo.model_id and self.partner_id:
            # Get the last value used by this partner for this item type.
            last_value = self.env['sign.request.item.value'].sudo().search([
                ('sign_request_item_id.partner_id', '=', self.partner_id.id),
                ('sign_request_item_id.state', '=', 'completed'),
                ('sign_item_id.type_id', '=', item_type_sudo.id),
                ('value', '!=', False),
            ], order='id desc', limit=1)

            if last_value:
                return last_value.value or ''

        if item_type_sudo.item_type == "stamp":
            return self._get_stamp_value()

        record = self._get_auto_field_target_record(item_type_sudo)
        if not record:
            return ''

        try:
            field_record_sudo = self.env['ir.model.fields'].sudo()
            target_record, target_field = self._resolve_auto_field_path(record, item_type_sudo.auto_field or '')
            if target_field:
                field_record_sudo = field_record_sudo._get(target_record._name, target_field)
            auto_field = record.mapped(item_type['auto_field'])
            auto_value = auto_field[0] if auto_field and not isinstance(auto_field, models.BaseModel) else self._get_falsy_value(record, item_type_sudo.auto_field)
            auto_value = self._get_auto_field_custom_value(field_record_sudo=field_record_sudo, item_type_sudo=item_type_sudo, record=record, auto_value=auto_value)
        except (KeyError, TypeError):
            auto_value = ""
        return auto_value

    def _get_auto_field_custom_value(self, field_record_sudo=None, item_type_sudo=None, record=None, auto_value=''):
        """ Override to retrieve automatic value following other logic for specific models"""
        self.ensure_one()
        if field_record_sudo and field_record_sudo.ttype == 'html':
            auto_value = html2plaintext(auto_value)
        if isinstance(auto_value, float):
            auto_value = round(auto_value, 2)
        return auto_value

    @api.model
    def _resolve_auto_field_path(self, record, field_path):
        """ Resolves a dot-notation path into a singleton target record and the final field name. """

        # Walk the path schema to ensure we never traverse a x2m field.
        current_model = self.env[record._name]
        for fname in field_path.split('.'):
            field = current_model._fields.get(fname)
            if not field or field.type in ('one2many', 'many2many'):
                return None, None
            if field.relational:
                current_model = self.env[field.comodel_name]

        if '.' not in field_path:
            return record, field_path

        # Split once from the right to separate the relation path from the final field
        # e.g., 'company_id.country_id.code' -> ['company_id.country_id', 'code']
        relation_path, final_field = field_path.rsplit('.', 1)

        target_records = record.mapped(relation_path)

        # if the relation is empty (len == 0)
        if len(target_records) != 1:
            return None, None

        return target_records, final_field

    @api.model
    def _get_falsy_value(self, record, auto_field):
        """" When the automatic value is falsy, return the appropriate value according to the auto_field
        """
        if not auto_field or not isinstance(auto_field, str):
            return ""
        relation_and_value = auto_field.rsplit('.', 1)
        if len(relation_and_value) == 1:
            # There is no relational field, fallback on the value (which is falsy)
            auto_value = record[relation_and_value[0]]
        else:
            # relational field exists, we need to get the default value of the related record
            relation, field = relation_and_value
            # We know that the relationship point to a single record with a falsy value
            other_record = record.mapped(relation)
            auto_value = other_record[field]
            field_record_sudo = self.env['ir.model.fields'].sudo()._get(other_record._name, field)
            field_instance = fields.Field._by_type__[field_record_sudo.ttype]
            if auto_value is False and field_instance.is_text or field_instance.type == 'selection':
                auto_value = ""
        return auto_value

    @api.model
    def _parse_auto_field_value(self, field_record_sudo, record, value, item_type_sudo=None, lang_code=None):
        """Format, parse, or cast the raw value from a signature item before writing it back.
        This method handles specific data conversions to ensure database integrity:

        * Parses localized string dates into ``datetime.date`` objects for 'date' fields.
        * Dynamically casts all other field types (Integer, Float, Boolean, etc.)
          using the ORM's native ``convert_to_cache`` method.

        :param recordset field_record_sudo: ``ir.model.fields`` record of the target Odoo field.
        :param recordset record: The target Odoo record being updated.
        :param str value: The raw string value entered by the signer.
        :param recordset item_type_sudo: ``sign.item.type`` record of the signed item.
        :param str lang_code: language code to be used to format data fields
        :return: The safely formatted or casted value, or ``None`` if the input is empty
                 or fails type validation.
        :rtype: Any
        :raises ValueError: If the value cannot be parsed or cast to the target field type
                    (e.g., an invalid date format or invalid integer literal).
        :raises TypeError: If the value is of an inappropriate type for the target conversion operation.
        """
        if not field_record_sudo:
            return value

        if isinstance(value, str):
            value = value.strip()

        # If the target is an HTML field, convert the plain text string into safe HTML
        if field_record_sudo.ttype == 'html':
            value = plaintext2html(value)
        elif field_record_sudo.ttype == 'date':
            # get user's dynamic localized format
            lang_code = lang_code or self.env.context.get('lang')
            lang_record = self.env['res.lang']._lang_get(lang_code)
            value = datetime.strptime(value, lang_record.date_format).date()
        else:
            # Generic Automatic Casting for all other types (Int, Float, Bool, Char, etc.)
            field_name = field_record_sudo.name
            odoo_field = record._fields[field_name]
            value = odoo_field.convert_to_cache(value, record)

        return value

    def _get_stamp_value(self):
        """
        Return the formatted stamp value (company name, address, phone) for the partner.

        :returns: str Company name and phone separated by a newline, or an empty string if not found.
        """
        partner = self.with_context(show_address=1).partner_id
        company_address = None

        if partner:
            if partner.parent_id:
                # Partner has a parent → use parent company
                company_address = partner.parent_id
            elif partner.is_company:
                # Partner is a standalone company → use itself (commercial partner)
                company_address = partner.commercial_partner_id
            elif partner.user_ids and partner.user_ids[0].company_id:
                # Partner is an individual user → use their company partner
                company_address = partner.user_ids[0].company_id.partner_id

        if not company_address:
            return ''

        return self.env._(
            "%(company_address)s\n%(phone)s", company_address=company_address.display_name, phone=company_address.phone or ""
        )

    # ------------------------------------------------------------------
    # QES helpers
    # ------------------------------------------------------------------

    def _get_documents_awaiting_external_signature(self):
        """ The documents frozen behind this signer's own signature, waiting for the
        external service producing it.

        A signing order is enforced on requests holding an external signer, so the only
        documents frozen while this signer holds a session are their own.
        """
        self.ensure_one()
        if not self._is_pending_signer():
            return self.env['sign.request.document']
        return self.sign_request_id.request_document_ids.filtered(
            lambda document: document.state == 'awaiting_signature')

    def _is_applied_on_every_external_document(self):
        """ Whether everything this signer contributes is on the file of every document of
        the request (their stamped values, and their own signature when they produce one).
        """
        self.ensure_one()
        return not self._get_documents_awaiting_external_signature() and all(
            self in document.applied_item_ids
            for document in self.sign_request_id._get_signing_documents())

    def _freeze_documents_for_external_signature(self):
        """ Freezes every document this signer still has to sign, so what they review at the
        service is what their signature seals. Documents already frozen are sent as they are,
        so reopening a session does not refreeze bytes.

        :return: [{'document_id': int, 'name': str, 'file': base64 str, 'hash': str}] for the
            signing service, or None when they cannot be frozen.
        """
        self.ensure_one()
        own_frozen_documents = self._get_documents_awaiting_external_signature()
        documents = []
        for document in self.sign_request_id._get_signing_documents():
            if self in document.applied_item_ids:
                # already carries this signer's signature, a safety net for a partial delivery
                continue
            if document.state == 'awaiting_signature' and document not in own_frozen_documents:
                return None  # frozen by another signer
            if document.state != 'awaiting_signature':
                document._freeze_for_external_signature(self)
            frozen_raw = bytes(document.frozen_file)
            documents.append({
                'document_id': document.id,
                'name': document.document_id.name,
                'file': base64.b64encode(frozen_raw).decode(),
                # The signing server verifies it, so a document corrupted during upload is never signed
                'hash': sha256(frozen_raw).hexdigest(),
            })
        return documents

    def _apply_external_signatures(self, documents):
        """ Applies the signatures the service produced and completes the signer once every
        document carries theirs.

        Every document is sealed together or none is, so the answers this signer submitted
        are never sealed on some of their documents and not the others. An incomplete
        delivery is left for a later attempt to collect again.

        :param documents: [{'document_id': int, 'signature_increment': base64 str, 'hash': str}]
        """
        self.ensure_one()
        frozen_documents = self._get_documents_awaiting_external_signature()
        frozen_by_id = {document.id: document for document in frozen_documents}
        increments = {}
        try:
            for entry in documents or []:
                document = frozen_by_id.get(entry['document_id'])
                if not document:
                    continue
                increment = base64.b64decode(entry['signature_increment'])
                if sha256(bytes(document.frozen_file) + increment).hexdigest() != entry['hash']:
                    continue  # the signature did not survive the way back
                increments[document] = increment
        except (KeyError, TypeError, binascii.Error):
            _logger.warning("Unreadable signature delivery for sign request item %s", self.id, exc_info=True)
        if len(increments) != len(frozen_documents):
            self.external_signature_failures += 1
            _logger.warning(
                "Collected %s of the %s signed documents of sign request item %s, applying none of them",
                len(increments), len(frozen_documents), self.id)
            if self.external_signature_failures >= MAX_EXTERNAL_SIGNATURE_FAILURES:
                # the service cannot know its signature does not arrive usable here, so it
                # would hand back the same one for as long as this signer keeps asking
                _logger.error(
                    "Gave up the signature of sign request item %s after %s unusable deliveries",
                    self.id, self.external_signature_failures)
                self._cancel_external_signature()
            return
        for document, increment in increments.items():
            document._finalize_external_signature(self, increment)
        # Check that this signer is the one the request waits on, otherwise, nothing is frozen
        # for them and there is nothing for them to complete.
        if self.state == 'sent' and self._is_applied_on_every_external_document():
            self._post_fill_request_item()

    def _has_stale_external_signature(self, signature):
        """ Whether the documents frozen for this signer no longer carry what they are
        submitting, so a signature made on them would seal answers they changed since. """
        self.ensure_one()
        if not self._get_documents_awaiting_external_signature() or not isinstance(signature, dict):
            return False
        stored_values = {str(value.sign_item_id.id): value.value for value in self.sign_item_value_ids}
        return any(stored_values.get(item_id) != value for item_id, value in signature.items())

    def _sign_externally(self, signature, **kwargs):
        """ Stores what the signer is submitting and returns where they have to go for the
        service to produce their signature.

        :return: A sign route response, carrying the ``authorization_url`` to continue at
            when there is a step left for the signer.
        """
        self.ensure_one()
        if self._has_stale_external_signature(signature):
            self._cancel_external_signature()
            if self._get_documents_awaiting_external_signature():
                # the signing service kept the session because they approved it already, so what they
                # changed since cannot be part of the signature it is making
                return {'success': False, 'message': self.env._(
                    "You already approved this document, so the changes you just made cannot be "
                    "part of the signature being produced.")}
        self._sync_external_signature()
        if self.state != 'sent':
            return {'success': True}  # their signature was collected, there is nothing left to sign

        self.sign(signature, **kwargs)  # sign method will skip in case the documents were already frozen

        documents = self._freeze_documents_for_external_signature()
        if documents is None:
            return {'success': False, 'message': self.env._(
                "This document is being signed by another signer. Please try again later.")}

        signing = self._get_external_signature_url(documents)
        if signing.get('url'):
            return {'success': True, 'authorization_url': signing['url']}
        if not self.external_signature_session_token:
            # no session was opened, so the documents are let go of rather than left frozen
            # waiting on one that does not exist
            self._cancel_external_signature()
        return {'success': False, 'message': signing.get('message')}

    def _qes_host_call(self, route, timeout=QES_HOST_TIMEOUT, **params):
        """ Calls the qualified signature host about this signer's session.

        Answers with a mapping whatever the host replied, so reading a key off it never raises.

        :param timeout: maximum time to wait for the host to respond.
            This should account for the time required to process the session's documents.
        :raise requests.RequestException: when the host could not be reached
        """
        self.ensure_one()
        endpoint = self.env['ir.config_parameter'].sudo().get_str('sign.qes_endpoint') or QES_DEFAULT_HOST
        provider = self.role_id._get_external_signature_provider()
        return iap_tools.iap_jsonrpc(
            url_join(endpoint, '/qes/v1/%s/session/%s' % (provider, route)),
            params={'sign_request_id': self.sign_request_id.id, **params},
            timeout=timeout,
        ) or {}

    def _get_external_signature_url(self, documents=None):
        """ Where to send this signer so the service produces their signature.

        Without documents, this only resumes an existing session and does not open a new one.
        The frozen documents are what create a new session and define the content shown by the
        service throughout that session.

        :param documents: [{'document_id': int, 'name': str, 'file': base64 str, 'hash': str}]
        :return: ``{'url': str}`` to send the signer to, or ``{'message': str}``
        """
        self.ensure_one()
        try:
            if self.external_signature_session_token:
                # they left the flow and came back, so they carry on from where they stopped
                resumed = self._qes_host_call('resume', session_token=self.external_signature_session_token)
                if resumed.get('signing_url'):
                    return {'url': resumed['signing_url']}
                if resumed.get('status') == 'approved':
                    # they already approved, so this signature is on its way and starting
                    # another one would make them approve the same documents twice
                    return {'message': self.env._(
                        "Your signature is being finalized. Please try again in a moment.")}
            if not documents:
                return {}  # nothing left to carry on, and nothing to open a session with
            account = self.env['iap.account'].sudo().get(QES_IAP_SERVICE_NAME)
            if not account.account_token:
                return {'message': self.env._("The signature service could not be found.")}
            # no session exists or the resume call expired it, so create one
            opened = self._qes_host_call(
                'open',
                timeout=QES_HOST_UPLOAD_TIMEOUT,
                iap_account_token=account.account_token,
                signer_access_token=self.access_token,
                database_url=self.get_base_url(),
                lang=self.partner_id.lang or self.env.lang or self.env.company.partner_id.lang or 'en_US',
                documents=documents,
            )
        except requests.RequestException:
            return {'message': self.env._("The signature service could not be reached. Please try again later.")}
        if opened.get('session_token') and opened.get('signing_url'):
            self.external_signature_session_token = opened['session_token']
            return {'url': opened['signing_url']}
        return {'message': opened.get('message')}

    def _sync_external_signature(self):
        """ Brings the local state up to date with what the service reports.

        Once the signer has approved, their signature is collected and applied to the frozen
        documents. A session the service has given up on is let go of here as well.

        It is called whenever the flow has to move forward without asking the signer for
        anything. This is when they open their document, when they click to sign, and from the
        reminder cron.
        """
        self.ensure_one()
        if not self.external_signature_session_token:
            return
        try:
            response = self._qes_host_call('status', session_token=self.external_signature_session_token)
        except requests.RequestException:
            # nothing here can act on it, and the signer must not be held up by it
            _logger.warning("Could not reach the signature service about sign request item %s", self.id)
            return

        if response.get('status') == 'signed':
            self._apply_external_signatures(response.get('documents'))
        elif response.get('status') in ('none', 'expired'):
            # the service has nothing left to give up, so the session is only released here
            self.external_signature_session_token = False
            self._get_documents_awaiting_external_signature()._discard_pending_signature()

    def _cancel_external_signature(self):
        """ Gives up the signing session this signer opened at the service, without refusing
        the document, so they stay free to sign it again or to refuse it.

        The session is let go of locally whether or not the service could be told, so giving
        up never depends on it answering. A session the service keeps is kept here too, so a
        signature the signer already approved stays collectable.
        """
        self.ensure_one()
        frozen_documents = self._get_documents_awaiting_external_signature()
        if not frozen_documents:
            return None
        if self.external_signature_session_token:
            try:
                rejected = self._qes_host_call('reject', session_token=self.external_signature_session_token)
            except requests.RequestException:
                # the service ends the session on its own, and this signer is not made to wait
                # for it to answer before they can sign or refuse again
                _logger.warning("Could not give up the signature session of sign request item %s", self.id)
            else:
                if rejected.get('status') not in ('none', 'expired'):
                    # the host didn't reject the session, which means there is still a valid signature to collect
                    return None
        # Reset the failure counter so the next attempt starts clean
        self.write({'external_signature_session_token': False, 'external_signature_failures': 0})
        frozen_documents._discard_pending_signature()
