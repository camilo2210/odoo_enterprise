# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import markupsafe

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang, format_date, get_lang
from odoo.tools.translate import _
from odoo.tools import html2plaintext, plaintext2html


class AccountFollowupReport(models.AbstractModel):
    _name = 'account.followup.report'
    _description = "Follow-up Report"

    ####################################################
    # REPORT COMPUTATION - TEMPLATE RENDERING
    ####################################################

    def get_followup_report_html(self, options):
        """
        Return the html of the followup report, based on the report options.
        """
        template = 'account_followup.template_followup_report'
        partner = self.env['res.partner'].browse(options['partner_id'])
        render_values = {
            'doc': partner,
            'lang': partner.lang or get_lang(self.env).code,
            'options': options,
            'context': self.env.context,
        }
        return self.env['ir.qweb']._render(template, render_values)

    def _get_followup_report_options(self, partner, options=None):
        """
        Compute the report options for a given partner.
        """
        options = options or {}
        options.update({
            'partner_id': partner.id,
            'followup_line': options.get('followup_line', partner.followup_line_id),
            'context': self.env.context,
        })
        return options

    ####################################################
    # DEFAULT BODY AND EMAIL SUBJECT
    ####################################################

    @api.model
    def _get_rendered_body(self, partner_id, template_src, default_body, **kwargs):
        """ Returns the body that can be rendered by the template_src, or if None, returns the default_body.
        kwargs can contain any keyword argument supported by the *_render_template* function
        """
        if template_src:
            return self.env['mail.composer.mixin'].sudo()._render_template(template_src, 'res.partner', [partner_id], **kwargs)[partner_id]

        return default_body

    @api.model
    def _get_sms_body(self, options):
        # Manual follow-up: return body from options
        if options.get('sms_body'):
            return options.get('sms_body')

        partner = self.env['res.partner'].browse(options.get('partner_id'))
        followup_line = options.get('followup_line', partner.followup_line_id)
        sms_template = options.get('sms_template') or followup_line.sms_template_id
        template_src = sms_template.with_context(lang=partner.lang or self.env.user.lang).body

        partner_followup_responsible_id = partner._get_followup_responsible()
        responsible_signature = html2plaintext(partner_followup_responsible_id.signature or partner_followup_responsible_id.name)
        self = self.with_context(lang=partner.lang or self.env.user.lang)
        default_body = _("Dear client, we kindly remind you that you still have unpaid invoices. Please check them and take appropriate action. %s", responsible_signature)

        return self._get_rendered_body(partner.id, template_src, default_body, options={'post_process': True})

    @api.model
    def _get_email_from(self, options):
        partner = self.env['res.partner'].browse(options.get('partner_id'))
        # For manual followups, get the email_from from the selected template in the send & print wizard.
        if options.get('email_from'):
            followup_email_from = options['email_from']
        # For automatic followups, get it from mail template on the followup line.
        else:
            followup_line = options.get('followup_line') or partner.followup_line_id
            mail_template = options.get('mail_template') or followup_line.mail_template_id
            followup_email_from = mail_template.email_from
        # The _render_template() function formats the email content. It handles cases where the email_from value
        # is a template that needs evaluation. For instance, "{{ object._get_followup_responsible().email_formatted }}".
        return self.env['mail.composer.mixin'].sudo()._render_template(followup_email_from, 'res.partner', [partner.id])[partner.id] or None

    @api.model
    def _get_email_reply_to(self, options):
        partner = self.env['res.partner'].browse(options.get('partner_id'))
        followup_line = options.get('followup_line', partner.followup_line_id)
        mail_template = options.get('mail_template', followup_line.mail_template_id)
        # if template has no reply-to set, fall back to default reply-to, otherwise
        # it will be set to False and behave unexpectedly
        if mail_template.reply_to:
            followup_reply_to = mail_template.reply_to
        else:
            followup_reply_to = self._notify_get_reply_to()[False]
        return followup_reply_to

    @api.model
    def _get_main_body(self, options):
        # Manual follow-up: return body from options
        if options.get('body'):
            return options.get('body')

        partner = self.env['res.partner'].browse(options.get('partner_id'))
        followup_line = options.get('followup_line', partner.followup_line_id)
        mail_template = options.get('mail_template', followup_line.mail_template_id)
        template_src = None
        if mail_template:
            template_src = mail_template.with_context(lang=partner.lang or self.env.user.lang).body_html

        partner_followup_responsible_id = partner._get_followup_responsible()
        responsible_signature = partner_followup_responsible_id.signature or partner_followup_responsible_id.name
        self = self.with_context(lang=partner.lang or self.env.user.lang)
        default_body = _("""Dear %s,


Exception made if there was a mistake of ours, it seems that the following amount stays unpaid. Please, take appropriate measures in order to carry out this payment in the next 8 days.

Would your payment have been carried out after this mail was sent, please ignore this message. Do not hesitate to contact our accounting department.

Best Regards,

""", partner.name)

        default_body_html = plaintext2html(default_body) + responsible_signature  # responsible_signature is an html field
        return self._get_rendered_body(partner.id, template_src, default_body_html, engine='qweb', options={'post_process': True})

    @api.model
    def _get_email_subject(self, options):
        # Manual follow-up: return body from options
        if options.get('email_subject'):
            return options.get('email_subject')

        partner = self.env['res.partner'].browse(options.get('partner_id'))
        followup_line = options.get('followup_line', partner.followup_line_id)
        mail_template = options.get('mail_template', followup_line.mail_template_id)
        template_src = None
        if mail_template:
            template_src = mail_template.with_context(lang=partner.lang or self.env.user.lang).subject

        partner_name = partner.name
        company_name = self.env.company.name
        self = self.with_context(lang=partner.lang or self.env.user.lang)
        default_body = _("%(company)s Payment Reminder - %(partner)s", company=company_name, partner=partner_name)

        return self._get_rendered_body(partner.id, template_src, default_body, options={'post_process': True})

    @api.model
    def _get_email_recipients(self, options):
        if options.get('email_recipient_ids'):
            return options.get('email_recipient_ids')

        partner = self.env['res.partner'].browse(options.get('partner_id'))
        recipients = partner._get_all_followup_contacts() or partner
        followup_line = options.get('followup_line', recipients.followup_line_id)
        mail_template = options.get('mail_template', followup_line.mail_template_id)
        if mail_template:
            rendered_values = mail_template._generate_template_recipients(
                res_ids=[partner.id],
                render_fields={'partner_to', 'email_cc', 'partner_cc', 'email_to'},
                allow_suggested=True,
                find_or_create_partners=True
            )[partner.id]
            recipients |= partner.browse(rendered_values.get('partner_ids'))
            recipients |= partner.browse(rendered_values.get('partner_cc_ids'))
        return recipients

    ####################################################
    # EXPORT
    ####################################################

    @api.model
    def _send_sms(self, options):
        """
        Send by SMS the followup to the customer
        """
        partner = self.env['res.partner'].browse(options.get('partner_id'))
        followup_contacts = partner._get_all_followup_contacts() or partner
        sent_at_least_once = False
        for to_send_partner in followup_contacts:
            sms_number = to_send_partner.phone
            if sms_number:
                sms_body = self.with_context(lang=partner.lang or self.env.user.lang)._get_sms_body(options)
                partner._message_sms(
                    body=sms_body,
                    partner_ids=partner.ids,
                    sms_pid_to_number={partner.id: sms_number},
                )
                sent_at_least_once = True
        if not sent_at_least_once:
            raise UserError(_("You are trying to send an SMS, but no follow-up contact has any mobile/phone number set for customer '%s'", partner.name))

    @api.model
    def _send_email(self, options):
        """
        Send by email the followup to the customer's followup contacts
        """
        partner = self.env['res.partner'].browse(options.get('partner_id'))
        sent_at_least_once = False
        for to_send_partner in self._get_email_recipients(options):
            email = to_send_partner.email
            if email and email.strip():
                self = self.with_context(lang=partner.lang or self.env.user.lang)
                body_html = self.with_context(mail=True).get_followup_report_html(options)
                attachment_ids = options.get('attachment_ids')

                # If the follow-up was executed manually, the author_id will be set to the ID of the current logged-in user.
                # Otherwise, if the follow-up is automatic, the author_id will be the followup responsible or OdooBot.
                author_id = options.get('author_id', partner._get_followup_responsible().partner_id.id)

                partner.with_context(mail_post_autofollow=True, lang=partner.lang or self.env.user.lang).message_post(
                    partner_ids=[to_send_partner.id],
                    author_id=author_id,
                    email_from=self._get_email_from(options),
                    body=body_html,
                    subject=self._get_email_subject(options),
                    reply_to=self._get_email_reply_to(options),
                    model_description=_('payment reminder'),
                    notify_author=True,
                    email_layout_xmlid='mail.mail_notification_light',
                    attachment_ids=attachment_ids,
                    subtype_id=self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
                )
                sent_at_least_once = True

        if not sent_at_least_once:
            raise UserError(_("You are trying to send an Email, but no follow-up contact has any email address set for customer '%s'", partner.name))
