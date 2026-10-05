from odoo import fields, models
from odoo.tools import SQL


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    followup_line_id = fields.Many2one(comodel_name='account_followup.followup.line', string='Reminder Level', copy=False)
    followup_overdue = fields.Boolean(compute='_compute_followup_overdue', compute_sql='_compute_sql_followup_overdue', compute_sudo=True)
    invoice_origin = fields.Char(related='move_id.invoice_origin')

    def _compute_followup_overdue(self):
        now = fields.Date.context_today(self)
        for aml in self:
            aml.followup_overdue = aml.date_maturity and aml.date_maturity < now

    def _compute_sql_followup_overdue(self, table):
        return SQL(
            "%(date_maturity)s IS NOT NULL AND %(date_maturity)s < %(current_date)s",
            date_maturity=table.date_maturity,
            current_date=fields.Date.context_today(self),
        )
