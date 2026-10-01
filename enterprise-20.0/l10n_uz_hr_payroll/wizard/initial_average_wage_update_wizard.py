from markupsafe import Markup

from odoo import fields, models


class L10nUzAverageMonthlyWageUpdateWizard(models.TransientModel):
    _name = "l10n.uz.average.monthly.wage.update.wizard"
    _description = "Wizard to Update Initial Average Wage"

    version_id = fields.Many2one("hr.version", required=True, readonly=True)
    currency_id = fields.Many2one(related="version_id.currency_id")
    current_initial_wage = fields.Monetary(
        related="version_id.l10n_uz_initial_average_monthly_wage",
        string="Current Initial Wage",
        readonly=True,
    )
    new_initial_wage = fields.Monetary(
        string="New Initial Wage",
        currency_field="currency_id",
        default=0.0,
        required=True,
    )
    reason = fields.Text(string="Reason for Adjustment", required=True)

    def action_apply(self):
        self.ensure_one()
        self.version_id.l10n_uz_initial_average_monthly_wage = self.new_initial_wage

        message_body = Markup(
            "<strong>Initial Average Monthly Wage Updated</strong><br/>"
            "<ul>"
            "<li><b>Previous Value:</b> %s</li>"
            "<li><b>New Value:</b> %s</li>"
            "<li><b>Reason:</b> %s</li>"
            "</ul>"
        ) % (self.current_initial_wage, self.new_initial_wage, self.reason)

        if self.version_id.employee_id:
            self.version_id.employee_id.message_post(
                body=message_body,
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )

        return {'type': 'ir.actions.act_window_close'}
