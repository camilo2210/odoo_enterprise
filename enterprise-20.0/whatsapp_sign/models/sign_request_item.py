# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields
from odoo.exceptions import ValidationError


class SignRequestItem(models.Model):
    _inherit = 'sign.request.item'

    sign_link = fields.Char(string="Sign Link", groups="base.group_system")
    document_link = fields.Char(compute='_compute_document_link', compute_sudo=True, string="Document Link", groups="base.group_system")
    attachments_download_link = fields.Char(compute='_compute_attachments_download_link', string="Attachments Download Link", groups="base.group_system")

    def _get_sudo_access_fields(self):
        """ Returns a list of fields that require `sudo` access.

        :return: A list of strings, where each string is the name of a field that requires `sudo` access
        :rtype: list
        """
        return ['sign_link', 'document_link', 'attachments_download_link', 'sign_request_id.refuser_partner.name']

    @api.constrains('partner_id')
    def _check_partner_id(self):
        """
        Checks if the partner of a `sign.request.item` has a valid phone number, which is necessary for sending messages via WhatsApp.
        """
        for sri in self:
            if sri.sign_request_id.send_channel == 'whatsapp' and not sri.partner_id.phone:
                raise ValidationError(
                    self.env._(
                        "In sign request '%(ref)s', signer '%(signer)s' does not have a phone number, which is required to send messages via WhatsApp.",
                        ref=sri.sign_request_id.reference,
                        signer=sri.partner_id.display_name
                    )
                )

    @api.depends('sign_request_id.access_token')
    def _compute_attachments_download_link(self):
        """ Computes the download link for sign request attachments.

        If no attachment download link is available, the field will be set to "-",
        which will be concatenated as a hyphen in the WhatsApp message.
        """
        for sri in self:
            if sri.sign_request_id.attachment_ids and len(sri.sign_request_id.attachment_ids) > 0:
                partial_url = "sign/download/attachments/%(request_id)s/%(access_token)s" % {
                    'request_id': sri.sign_request_id.id,
                    'access_token': sri.sign_request_id.access_token,
                }
                sri.attachments_download_link = f"{sri.get_base_url()}/{partial_url}"
            else:
                sri.attachments_download_link = "-"

    @api.depends('access_token', 'sign_request_id.access_token')
    def _compute_document_link(self):
        """
        Generates a URL for viewing the signature document(s) associated with the sign request.
        """
        for sri in self:
            access_token = sri.access_token or sri.sign_request_id.access_token
            sub_route = 'sign/document/%s/%s' % (sri.sign_request_id.id, access_token)
            sri.document_link = f"{sri.sign_request_id.get_base_url()}/{sub_route}"

    def _get_whatsapp_safe_fields(self):
        return {
            'partner_id.phone', 'display_name', 'create_uid.partner_id.name',
            'sign_request_id.reference', 'sign_link', 'sign_request_id.raw_optional_message',
            'sign_request_id.validity', 'attachments_download_link', 'sign_request_id.reference',
            'sign_request_id.signers_name', 'document_link', 'sign_request_id.refuser_partner.name',
            'sign_request_id.refusal_reason'
        }

    def _send_signature_access_message(self):
        """ Sends a message to the signer(s) to grant them access to a document.
        This method first checks if the preferred communication channel is WhatsApp and if a valid template exists.
        If not, it defaults to using the parent method to send an email.
        For each `sign.request.item` in the current recordset, it generates a unique signing link, writes it to the item's `sign_link` field, and then creates and sends a WhatsApp message using the pre-configured template.

        :return: The result of the parent method if the message is sent via email, otherwise None
        """

        non_whatsapp_items = self.env['sign.request.item']
        for sign_request_item in self:
            company = sign_request_item.sign_request_id.communication_company_id
            is_whatsapp = sign_request_item.sign_request_id.send_channel == 'whatsapp'
            misconfiguration = is_whatsapp and not (company and company._check_if_whatsapp_sign_is_enabled())
            if misconfiguration:
                sign_request_item.sign_request_id.send_channel = 'email'
            if misconfiguration or not is_whatsapp:
                non_whatsapp_items |= sign_request_item
                continue

            # The sign link is calculated and assigned here to ensure the expiration time reflects the exact moment the sign request was sent
            sign_link, _ = sign_request_item._get_sign_and_cancel_links(sign_request_item)
            sign_request_item.sudo().sign_link = sign_link  # sudo write to avoid ACL restrictions on sign_link

            wa_template = company.sign_send_request_wa_template_id
            whatsapp_composer = self.env['whatsapp.composer'].with_context({'active_id': sign_request_item.id}).create({
                'wa_template_id': wa_template.id,
                'res_model': 'sign.request.item'
            })
            whatsapp_composer.sudo()._send_whatsapp_template(force_send_by_cron=True)
            sign_request_item.is_mail_sent = True

        if non_whatsapp_items:
            return super(SignRequestItem, non_whatsapp_items)._send_signature_access_message()
