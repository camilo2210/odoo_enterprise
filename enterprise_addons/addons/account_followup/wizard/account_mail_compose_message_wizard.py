from odoo import fields, models

REMINDER_XML_IDS = frozenset({
            'account_followup.mail_template_invoice_payment_kind_reminder',
            'account_followup.mail_template_invoice_payment_second_reminder',
            'account_followup.mail_template_invoice_payment_last_reminder',
})


class MailComposeMessage(models.TransientModel):
    _name = 'mail.compose.message'
    _inherit = ['mail.compose.message']

    cached_followup_attachment_id = fields.Many2one(
        'ir.attachment',
        string="Cached Followup Report",
        help="Caches the generated followup report to prevent recalculation when switching templates.",
        compute='_compute_cached_followup_attachment_id',
    )

    def _compute_cached_followup_attachment_id(self):
        for composer in self:
            if composer.model == 'account.move' and composer.res_ids and composer.partner_ids:
                move = composer.env[composer.model].browse(composer._evaluate_res_ids())
                if move.is_overdue_invoice():
                    composer.cached_followup_attachment_id = move.partner_id._get_followup_report(None)
                else:
                    composer.cached_followup_attachment_id = False
            else:
                composer.cached_followup_attachment_id = False

    def _compute_attachment_ids(self):
        # EXTENDS
        super()._compute_attachment_ids()

        for composer in self:
            if composer.model != 'account.move':
                return
            move = composer.env[composer.model].browse(composer._evaluate_res_ids())
            if not move.is_overdue_invoice():
                return
            if composer.template_id.get_external_id().get(composer.template_id.id) in REMINDER_XML_IDS:
                composer.attachment_ids += composer.cached_followup_attachment_id
            else:
                composer.attachment_ids = composer.attachment_ids._origin - composer.cached_followup_attachment_id
