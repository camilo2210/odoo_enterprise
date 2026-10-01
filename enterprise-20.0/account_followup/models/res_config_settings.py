from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    automatic_invoice_reminder = fields.Boolean(string="Automatic Invoice Reminders", related='company_id.automatic_invoice_reminder', readonly=False)

    def action_open_invoice_reminders(self):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Automatic invoices reminders'),
            'res_model': 'account_followup.followup.line',
            'view_mode': 'list,form',
            'path': 'automatic-reminder',
        }

    def set_values(self):
        res = super().set_values()

        if not self.automatic_invoice_reminder:
            return res

        followup_cron_sudo = self.sudo().env.ref('account_followup.ir_cron_follow_up', raise_if_not_found=False)
        if followup_cron_sudo and not followup_cron_sudo.active:
            followup_cron_sudo.active = True

        company_id = self.env.company.id
        # Check if already exists for this company
        if self.env['account_followup.followup.line'].sudo().search_count([('company_id', '=', company_id)], limit=1):
            return res

        templates = [
            (7, 'account_followup.mail_template_partner_payment_kind_reminder'),
            (15, 'account_followup.mail_template_partner_payment_second_reminder'),
            (30, 'account_followup.mail_template_partner_payment_last_reminder'),
        ]
        vals_list = [
            {
                'delay': delay,
                'company_id': company_id,
                'send_email': True,
                'mail_template_id': template.id,
            }
            for delay, xmlid in templates
            if (template := self.env.ref(xmlid, raise_if_not_found=False))
        ]

        if vals_list:
            self.env['account_followup.followup.line'].create(vals_list)

        return res
