from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    last_reminder = fields.Date(
        string='Last Reminder',
        copy=False,
        readonly=True,
        help="Date when reminder was last sent via email.",
    )
    last_auto_reminder = fields.Date(
        string='Last Automatic Reminder',
        copy=False,
        readonly=True,
        help="This field helps with automatic reminder sending date calculations when the reminder is belated",
    )

    def manual_reminder_action(self):
        wizard = self.env['account_followup.manual_reminder'].create([{
            'move_ids': self.filtered(lambda m: m.move_type == 'out_invoice' and m.amount_residual > 0).ids,
            'template_id': self.env.ref(
                'account_followup.mail_template_partner_payment_kind_reminder',
                raise_if_not_found=False
            ).id,
        }])

        return wizard._get_records_action(name=self.env._('Send Reminders'), target='new')
