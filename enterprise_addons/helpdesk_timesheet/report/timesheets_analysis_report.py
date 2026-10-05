# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import SQL


class TimesheetsAnalysisReport(models.Model):
    _inherit = "timesheets.analysis.report"

    helpdesk_ticket_id = fields.Many2one("helpdesk.ticket", "Helpdesk Ticket", readonly=True)

    @api.model
    def _select(self):
        return SQL("""%s,
                A.helpdesk_ticket_id AS helpdesk_ticket_id
        """, super()._select())
