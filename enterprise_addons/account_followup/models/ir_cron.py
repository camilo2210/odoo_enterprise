from odoo import models
from odoo.exceptions import RedirectWarning


class IrCron(models.Model):
    _inherit = 'ir.cron'

    def write(self, vals):
        for record in self:
            if vals.get('active') \
                and not any(comp.automatic_invoice_reminder for comp in self.env.companies) \
                and (reminder_cron := self.env.ref('account_followup.ir_cron_follow_up', raise_if_not_found=False)) \
                and reminder_cron.id == record.id:
                raise RedirectWarning(
                    message=self.env._("You cannot activate this action because 'Automatic Invoice Reminders' are disabled."),
                    action=self.env.ref('account.action_account_config').id,
                    button_text=self.env._("Go to Settings"),
                    additional_context={'module': 'account'},
                )

        return super().write(vals)
