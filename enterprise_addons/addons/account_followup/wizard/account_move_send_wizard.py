from odoo import api, fields, models

REMINDER_XML_IDS = frozenset({
    'account_followup.mail_template_invoice_payment_kind_reminder',
    'account_followup.mail_template_invoice_payment_second_reminder',
    'account_followup.mail_template_invoice_payment_last_reminder',
})


class AccountMoveSendWizard(models.TransientModel):
    _inherit = 'account.move.send.wizard'

    def _get_placeholder_mail_template_dynamic_attachments_data(self, move, mail_template, pdf_report=None):
        results = super()._get_placeholder_mail_template_dynamic_attachments_data(move, mail_template, pdf_report)
        template_xml_id = mail_template._get_external_ids().get(mail_template.id)  # _get_external_ids returns an array contains single xml_id
        if not move.is_overdue_invoice() or not REMINDER_XML_IDS.intersection(template_xml_id):
            return results
        today = fields.Date.context_today(self).strftime('%m%d%Y')
        filename = f"{today}_Customer-Statement.pdf"
        results.append({
            'id': f'placeholder_{filename}',
            'name': filename,
            'mimetype': 'application/pdf',
            'placeholder': True,
            'dynamic_followup': True,
        })
        return results

    def _generate_dynamic_reports(self, moves_data):
        super()._generate_dynamic_reports(moves_data)
        for move, move_data in moves_data.items():
            if not move.is_overdue_invoice():
                continue
            mail_attachments_widget = move_data.get('mail_attachments_widget', [])
            # Find our placeholder (and ensure user did not remove it)
            followup_placeholders = [
                att for att in mail_attachments_widget
                if att.get('dynamic_followup') and not att.get('skip')
            ]
            if not followup_placeholders:
                continue

            attachment_id = move.partner_id._get_followup_report(options=None)
            attachment = self.env['ir.attachment'].browse(attachment_id)
            move_data['mail_attachments_widget'].append({
                'id': attachment.id,
                'name': attachment.name,
                'mimetype': attachment.mimetype,
                'placeholder': False,
                'protect_from_deletion': True,
            })

    @api.model
    def _send_mail(self, move, mail_template, **kwargs):
        # If the invoice is overdue, log the message on the partner and update
        # last_reminder on the invoice; otherwise, fallback to the default flow.
        if move.is_overdue_invoice() and REMINDER_XML_IDS.intersection(mail_template._get_external_ids().get(mail_template.id)):
            move.partner_id.message_post(
                message_type='comment',
                **kwargs
            )
            move.last_reminder = fields.Date.context_today(self)
        else:
            super()._send_mail(move, mail_template, **kwargs)
